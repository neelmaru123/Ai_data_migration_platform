# Module Specification: `execution`

## 1. Overview & Responsibilities
The `execution` module manages **Data Plane Migration Job Dispatch and Progress Monitoring**. It converts approved migration plan ASTs into executable python/polars scripts or instructions, dispatches them to on-premise Agent Daemons, processes real-time row progress streams, logs diagnostic migration errors, and provides AI-driven error remediation suggestions.

---

## 2. Directory & File Inventory

| File / Subfolder | Layer / Type | Description |
| :--- | :--- | :--- |
| `execution_models.py` | Database Models | `MigrationJob` and `MigrationError` SQLAlchemy ORM entity definitions |
| `execution_schemas.py` | Schemas (DTOs) | Pydantic validation models (`MigrationJobCreate`, `MigrationJobResponse`, `ExecutionProgressUpdate`, `MigrationErrorResponse`) |
| `execution_services.py` | Business Logic | `ExecutionService` class for instantiating jobs, updating row progress telemetry, handling job state transitions, and querying errors |
| `execution_routes.py` | API Controller | FastAPI router defining endpoints for `/api/v1/jobs` and `/api/v1/execution` |
| `execution_script_generator/` | Script Compiler | Compiles Transformation AST into runnable Polars execution scripts for Docker Agent daemons |

---

## 3. Database Entities & Affected Tables

### Primary Tables Owned
1. **`migration_jobs`** (`MigrationJob`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `migration_plan_id` → `migration_plans.id` (CASCADE), `agent_id` → `agents.id` (SET NULL)
   - **Attributes:** `status` (`queued`, `preparing`, `running`, `paused`, `completed`, `failed`, `cancelled`), `progress` (0.0 to 100.0), `total_rows`, `processed_rows`, `successful_rows`, `failed_rows`, `current_table`, `current_stage`, `started_at`, `completed_at`, `error_message`, `created_at`, `updated_at`

2. **`migration_errors`** (`MigrationError`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `migration_job_id` → `migration_jobs.id` (CASCADE)
   - **Attributes:** `source_table`, `source_row_identifier`, `error_type`, `error_message`, `raw_data` (JSON), `ai_suggestion`, `status` (`unresolved`, `resolved`, `ignored`, `retrying`), `retry_count`, `created_at`

### External Tables Interacted With (Read-Only)
- **`migration_plans`**: Read target config, plan AST, and validation status.
- **`agents`**: Read agent status and connection attributes.

---

## 4. Service Layer Specification (`ExecutionService`)

### 1. `create_execution_job(session, user_id, plan_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `user_id` (`uuid.UUID`): User owner UUID.
  - `plan_id` (`uuid.UUID`): Migration plan UUID to execute.
- **Return Value:** `MigrationJob` - Created execution job record initialized in `"queued"` state.
- **Business Logic:**
  1. Queries `migration_plans` by `plan_id == plan_id` AND `user_id == user_id`. If not found, raises `HTTP 404 Not Found`.
  2. Verifies plan status is `"completed"` (approved). If unapproved, raises `HTTP 422 Unprocessable Entity`.
  3. Verifies `plan.is_valid is not False`. If invalid, raises `HTTP 422 Unprocessable Entity` with validation message.
  4. Instantiates `MigrationJob` ORM model with `status="queued"`, `progress=0.0`, `agent_id=plan.agent_id`.
  5. Commits transaction and refreshes job.
  6. Broadcasts `EXECUTION_QUEUED` WebSocket message to the assigned agent daemon (`manager.broadcast_to_agent()`).
- **Affected Tables:** `migration_jobs` (INSERT), `migration_plans` (SELECT)
- **Exceptions:**
  - `HTTPException(404 Not Found)`: Plan not found or access denied.
  - `HTTPException(422 Unprocessable Entity)`: Unapproved or invalid migration plan.

---

### 2. `get_pending_tasks_for_agent(session, agent_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent_id` (`uuid.UUID`): Agent daemon UUID querying for pending execution tasks.
- **Return Value:** `List[MigrationJob]` - List of queued/preparing migration jobs assigned to the agent.
- **Business Logic:**
  1. Selects `MigrationJob` records filtering on `agent_id == agent_id` AND `status.in_(["queued", "preparing"])`.
  2. Orders jobs chronologically by `created_at asc`.
  3. Returns list of jobs for execution pickup by agent.
- **Affected Tables:** `migration_jobs` (SELECT)
- **Exceptions:** None.

---

### 3. `get_job_by_id(session, user_id, job_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `user_id` (`uuid.UUID`): User owner UUID.
  - `job_id` (`uuid.UUID`): Target job UUID.
- **Return Value:** `MigrationJob` - Matching job record.
- **Business Logic:**
  1. Joins `MigrationJob` with `MigrationPlan` filtering on `job_id == job_id` AND `MigrationPlan.user_id == user_id`.
  2. If job not found, raises `HTTP 404 Not Found`.
  3. Returns matching `MigrationJob`.
- **Affected Tables:** `migration_jobs` (SELECT), `migration_plans` (JOIN/SELECT)
- **Exceptions:**
  - `HTTPException(404 Not Found)`: Job not found or unauthorized access.

---

### 4. `list_jobs_for_user(session, user_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `user_id` (`uuid.UUID`): User owner UUID.
- **Return Value:** `List[MigrationJob]` - List of execution jobs across all migration plans owned by the user.
- **Business Logic:**
  1. Joins `MigrationJob` with `MigrationPlan` filtering on `user_id == user_id`.
  2. Orders results by `MigrationJob.created_at.desc()`.
  3. Returns list of jobs.
- **Affected Tables:** `migration_jobs` (SELECT), `migration_plans` (JOIN/SELECT)
- **Exceptions:** None.

---

### 5. `update_job_progress(session, job_id, update, agent_id=None)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `job_id` (`uuid.UUID`): Target job UUID.
  - `update` (`ExecutionProgressUpdate`): DTO from agent telemetry reporting `status`, `progress`, `total_rows`, `processed_rows`, `successful_rows`, `failed_rows`, `current_table`, `current_stage`, `error_message`.
  - `agent_id` (`Optional[uuid.UUID]`, default=`None`): Security check matching caller's agent ID.
- **Return Value:** `MigrationJob` - Updated migration job model.
- **Business Logic:**
  1. Selects `MigrationJob` by `id == job_id` (and `agent_id` match if provided). Raises `HTTP 404 Not Found` if missing.
  2. If transition to `"running"` and `started_at` is `None`, sets `started_at = UTC NOW`.
  3. If status in `["completed", "failed"]`, sets `completed_at = UTC NOW`.
  4. Updates progress metrics: `status`, `progress`, `total_rows`, `processed_rows`, `successful_rows`, `failed_rows`, `current_table`, `current_stage`, `error_message`.
  5. Commits transaction and refreshes model.
  6. Broadcasts `EXECUTION_PROGRESS` WebSocket message to connected UI clients.
- **Affected Tables:** `migration_jobs` (SELECT, UPDATE)
- **Exceptions:**
  - `HTTPException(404 Not Found)`: Job not found or agent mismatch.

---

## 5. API Routes Specification (`execution_routes.py`)

| HTTP Method | Route Path | Description | Service Function Called | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/jobs/create/{plan_id}` | Instantiate migration job from approved plan | `ExecutionService.create_execution_job` | User JWT |
| `POST` | `/api/v1/jobs/{job_id}/progress` | Agent telemetry update (progress, rows, table) | `ExecutionService.update_job_progress` | Agent Token |
| `GET` | `/api/v1/jobs/agent/pending` | Fetch pending execution tasks for agent | `ExecutionService.get_pending_tasks_for_agent` | Agent Token |
| `GET` | `/api/v1/jobs` | List user's execution jobs | `ExecutionService.list_jobs_for_user` | User JWT |
| `GET` | `/api/v1/jobs/{job_id}` | Get specific job status & progress metrics | `ExecutionService.get_job_by_id` | User JWT |

---

## 6. Inter-Module Dependencies

- **Incoming Dependencies (Modules calling `execution`):**
  - **Web UI / Front-end**: Listens to WebSocket events emitted by `execution`.
- **Outgoing Dependencies (`execution` calls these):**
  - **`migration_plans`**: Fetches AST and validation state.
  - **`agents`**: Authenticates agent progress calls and routes execution tasks.
