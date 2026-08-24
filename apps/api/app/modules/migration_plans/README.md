# Module Specification: `migration_plans`

## 1. Overview & Responsibilities
The `migration_plans` module is the core control-plane component responsible for **AI-assisted database migration blueprinting**. It ingests database metadata snapshots, runs multi-agent LLM reasoning and validation, constructs executable Transformation Plan ASTs, and manages the lifecycle of migration plans (Draft, Validated, Approved, Executed).

---

## 2. Directory & File Inventory

| File / Subfolder | Layer / Type | Description |
| :--- | :--- | :--- |
| `migration_plans_models.py` | Database Models | `MigrationPlan` and `MigrationPlanSnapshot` SQLAlchemy ORM definitions |
| `migration_plans_schemas.py` | Schemas (DTOs) | Pydantic models for API payloads, AST structures, target DB configs, and validation responses |
| `migration_plans_services.py` | Business Logic | `MigrationPlanService` class implementing plan generation, validation, and lifecycle management |
| `migration_plans_routes.py` | API Controller | FastAPI router defining endpoints for `/api/v1/plans` |
| `migration_plans_engine/` | Sub-engine | LangGraph multi-agent workflow (`migration_plans_graph.py`), validation engine (`migration_plans_validator.py`), and LLM prompt serializer (`migration_plans_llm.py`) |

---

## 3. Database Entities & Affected Tables

### Primary Tables Owned
1. **`migration_plans`** (`MigrationPlan`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `user_id` → `users.id` (CASCADE), `agent_id` → `agents.id` (SET NULL)
   - **Attributes:** `status` (`draft`, `edited`, `completed`, `invalid`, `draft_failed`), `plan_data` (JSON AST), `target_config` (JSON), `confidence_score`, `is_valid`, `validation_errors`, `langgraph_thread_id`, `created_at`, `updated_at`

2. **`migration_plan_snapshots`** (`MigrationPlanSnapshot`)
   - **Primary Key:** Composite (`migration_plan_id`, `metadata_snapshot_id`)
   - **Description:** Many-to-Many association table linking a `MigrationPlan` to input `MetadataSnapshot` records.

### External Tables Interacted With (Read-Only/Referenced)
- **`users`** (`User`): Read/Filter plans by owner.
- **`agents`** (`Agent`): Read agent details & associated data sources.
- **`metadata_snapshots`**, **`metadata_schemas`**, **`metadata_tables`**, **`metadata_columns`**, **`metadata_constraints`**: Read source catalog metadata.
- **`data_sources`**: Read source database connections.
- **`migration_jobs`**: One-to-many child executions linked to a plan.

---

## 4. Service Layer Specification (`MigrationPlanService`)

### 1. `_fetch_latest_snapshots_for_agent(session, agent)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent` (`Agent`): Agent entity instance.
- **Return Value:** `Tuple[List[MetadataSnapshot], Dict[str, str]]` - Pair containing list of latest metadata snapshots and alias map (`data_source_id → alias`).
- **Business Logic:**
  1. Retrieves all `data_sources` attached to agent. If empty, raises `HTTP 422 Unprocessable Entity`.
  2. For each data source, assigns logical alias (`src_db_1`, `src_db_2` or custom `identifier`).
  3. Queries latest `MetadataSnapshot` (highest version) for each data source with eager preloading of schemas, tables, columns, and constraints.
  4. Returns collected snapshots and alias dictionary.
- **Affected Tables:** `metadata_snapshots`, `metadata_schemas`, `metadata_tables`, `metadata_columns`, `metadata_constraints` (SELECT)
- **Exceptions:**
  - `HTTPException(422 Unprocessable Entity)`: Agent has no attached data sources or no snapshots exist.

---

### 2. `create_plan_for_agent(session, agent, target_config)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent` (`Agent`): Agent instance attached to source databases.
  - `target_config` (`TargetDatabaseConfig`): DTO containing target database type and custom instructions.
- **Return Value:** `MigrationPlan` - Created and persisted migration plan record.
- **Business Logic:**
  1. Calls `_fetch_latest_snapshots_for_agent()` to retrieve catalog context.
  2. Initializes LangGraph multi-agent state payload.
  3. Invokes `migration_plan_graph.ainvoke(initial_state)` executing mapping, transformation generation, and feasibility assessment graph nodes.
  4. **LLM Fallback:** If LangGraph fails or gets interrupted, falls back to direct LLM AST generator (`llm_plan_generator.generate()`).
  5. Executes structural validator (`MigrationPlanValidator.validate()`).
  6. Instantiates `MigrationPlan` with generated plan AST, validation errors, confidence score, and status (`"draft"`, `"invalid"`, or `"draft_failed"`).
  7. Inserts `MigrationPlanSnapshot` join records linking plan to source snapshots.
  8. Commits database transaction and returns plan.
- **Affected Tables:** `migration_plans` (INSERT), `migration_plan_snapshots` (INSERT), `agents` (SELECT), `metadata_snapshots` (SELECT)
- **Exceptions:** None (Handles exceptions via fallback to `draft_failed`).

---

### 3. `get_plan_by_id(session, plan_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `plan_id` (`uuid.UUID`): Target plan UUID.
- **Return Value:** `Optional[MigrationPlan]` - Migration plan ORM model with `agent` and `data_sources` eagerly loaded, or `None`.
- **Business Logic:**
  1. Queries `migration_plans` table filtering by `id == plan_id`.
  2. Eagerly loads `MigrationPlan.agent` and `Agent.data_sources`.
  3. Returns scalar result or `None`.
- **Affected Tables:** `migration_plans` (SELECT), `agents` (SELECT), `data_sources` (SELECT)
- **Exceptions:** None.

---

### 4. `list_plans_for_user(session, user_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `user_id` (`uuid.UUID`): User owner UUID.
- **Return Value:** `List[MigrationPlan]` - List of migration plans owned by user, ordered newest first.
- **Business Logic:**
  1. Queries `migration_plans` table filtering on `user_id == user_id`.
  2. Orders by `created_at desc`.
- **Affected Tables:** `migration_plans` (SELECT)
- **Exceptions:** None.

---

### 5. `update_plan_data(session, plan, plan_data)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `plan` (`MigrationPlan`): Target plan ORM model.
  - `plan_data` (`Dict[str, Any]`): User-edited AST dictionary.
- **Return Value:** `MigrationPlan` - Updated migration plan.
- **Business Logic:**
  1. Updates `plan.plan_data = plan_data`.
  2. If agent attached, re-fetches snapshots and runs `MigrationPlanValidator.validate()` against edited AST.
  3. Sets `plan.is_valid` and updates status to `"edited"` (if valid) or `"invalid_edits"`.
  4. Commits session and returns plan.
- **Affected Tables:** `migration_plans` (UPDATE)
- **Exceptions:** None.

---

### 6. `refine_plan(session, plan, user_feedback)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `plan` (`MigrationPlan`): Existing plan ORM instance.
  - `user_feedback` (`str`): Natural language instructions from user describing desired adjustments.
- **Return Value:** `MigrationPlan` - Refined and validated plan.
- **Business Logic:**
  1. Verifies agent attachment (`HTTP 422` if missing).
  2. Fetches latest metadata snapshots for agent context.
  3. Invokes LLM refinement function `llm_plan_generator.refine()` with current AST and user feedback.
  4. Validates newly generated AST with `MigrationPlanValidator`.
  5. Updates `plan.plan_data`, `is_valid`, `validation_errors`, and status (`"edited"` or `"invalid_edits"`).
  6. Commits session and returns plan.
- **Affected Tables:** `migration_plans` (UPDATE)
- **Exceptions:**
  - `HTTPException(422 Unprocessable Entity)`: If plan has no attached agent.

---

### 7. `validate_plan_by_id(session, plan)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `plan` (`MigrationPlan`): Migration plan entity.
- **Return Value:** `Dict[str, Any]` - Validation result dictionary containing `is_valid`, `errors`, `warnings`, and `explanation`.
- **Business Logic:**
  1. If no agent attached, returns default valid response dictionary.
  2. Fetches latest agent metadata snapshots.
  3. Runs `MigrationPlanValidator.validate(plan.plan_data, snapshots, alias_map)`.
  4. Returns serialized validation result dictionary.
- **Affected Tables:** `metadata_snapshots` (SELECT)
- **Exceptions:** None.

---

### 8. `approve_plan(session, plan)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `plan` (`MigrationPlan`): Plan entity to approve.
- **Return Value:** `MigrationPlan` - Approved plan with status `"completed"`.
- **Business Logic:**
  1. Runs validator against `plan.plan_data`. If plan is invalid, raises `HTTP 422 Unprocessable Entity`.
  2. Updates `plan.status = "completed"`.
  3. Commits session.
  4. Broadcasts WebSocket event `PLAN_GENERATED` to agent daemon via `manager.broadcast_to_agent()`.
  5. Returns approved plan.
- **Affected Tables:** `migration_plans` (UPDATE)
- **Exceptions:**
  - `HTTPException(422 Unprocessable Entity)`: If plan fails validation checks.

---

## 5. API Routes Specification (`migration_plans_routes.py`)

| HTTP Method | Route Path | Description | Service Function Called | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/plans` | Create and generate plan for an agent | `MigrationPlanService.create_plan_for_agent` | User JWT |
| `GET` | `/api/v1/plans` | List user's migration plans | `MigrationPlanService.list_plans_for_user` | User JWT |
| `GET` | `/api/v1/plans/{plan_id}` | Get specific plan details | `MigrationPlanService.get_plan_by_id` | User JWT |
| `PUT` | `/api/v1/plans/{plan_id}` | Update plan AST manually | `MigrationPlanService.update_plan_data` | User JWT |
| `POST` | `/api/v1/plans/{plan_id}/refine` | Refine plan using natural language prompt | `MigrationPlanService.refine_plan` | User JWT |
| `POST` | `/api/v1/plans/{plan_id}/validate` | Run instant feasibility validation | `MigrationPlanService.validate_plan_by_id` | User JWT |
| `POST` | `/api/v1/plans/{plan_id}/approve` | Approve plan for execution | `MigrationPlanService.approve_plan` | User JWT |

---

## 6. Internal Engines & Sub-Components

- **`migration_plans_graph.py`**: LangGraph 9-node StateGraph workflow (`serialize_context_node`, `generate_plan_ast_node`, `validate_feasibility_node`, `auto_correct_ast_node`, `human_approval_interrupt_node`, `process_user_feedback_node`, `process_manual_edits_node`, `explanation_generator_node`, `finalize_and_persist_node`).
- **`migration_plans_validator.py`**: Deterministic Schema Validator (`MigrationPlanValidator`) executing multi-stage feasibility checks:
  - **Stage 0**: Empty Table Mapping Guard (`len(table_mappings) > 0`).
  - **Stage A**: Source Table & Alias Existence Check.
  - **Stage B**: Source Column Existence, Type Compatibility, Target Column Collision Check, and Merge Concat Length-Overflow Warning.
  - **Stage C**: Deduplication Key Validity Check.
  - **Stage D**: Foreign Key Two-Phase Hygiene Check & Pre-DDL Created Tables Parsing.
  - **Stage D2**: Circular Foreign Key Cycle Detection via Directed Graph DFS.
  - **Stage E**: Architecture Standards & Primary Key Rekeying Foreign Key Remap Warnings.
- **`migration_plans_llm.py`**: Formats zero-raw-data context, passes custom instructions, and enforces JSON Pydantic output parsing for Gemini 3.5 Flash Lite responses.

### Key Refinement & Concurrency Protections
1. **Refinement Row-Level Lock**:
   - `refine_plan()` acquires PostgreSQL `select(...).with_for_update()` row-level lock on `MigrationPlan` before invoking LLM refinement, serializing concurrent refinement requests.
2. **Refinement Guidance Preservation**:
   - `refine_plan()` passes user-provided `custom_instructions` from `plan.target_config` into `MetadataContextSerializer.serialize()` to ensure prompt instructions persist during iterative refinement runs.
3. **Active Execution Lock Check**:
   - `_check_active_execution_lock()` prevents editing or refining a plan while an active execution job (`queued`, `preparing`, `running`) is running on that plan.

---

## 7. Inter-Module Dependencies

- **Incoming Dependencies (Modules calling `migration_plans`):**
  - **`execution`**: Reads approved `migration_plans` to instantiate `migration_jobs`.
- **Outgoing Dependencies (`migration_plans` calls these):**
  - **`users`**: User authentication and ownership.
  - **`agents`**: Agent lookup and connection state.
  - **`metadata`**: Ingesting `MetadataSnapshot`, `MetadataTable`, `MetadataColumn`.
  - **`sources`**: Inspecting `DataSource` identifiers.
