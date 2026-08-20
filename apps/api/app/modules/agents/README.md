# Module Specification: `agents`

## 1. Overview & Responsibilities
The `agents` module manages on-premise **Docker Agent Daemons**. It generates secure agent registration API tokens, tracks agent heartbeat/health status, generates Docker run commands & deployment configurations, and authenticates agent requests to the API.

---

## 2. Directory & File Inventory

| File / Subfolder | Layer / Type | Description |
| :--- | :--- | :--- |
| `agents_models.py` | Database Models | `Agent` SQLAlchemy ORM entity definition |
| `agents_schemas.py` | Schemas (DTOs) | Pydantic validation models (`AgentCreate`, `AgentUpdate`, `AgentResponse`, `AgentCommandResponse`, `AgentHeartbeatRequest`) |
| `agents_services.py` | Business Logic | `AgentService` class handling token hashing, agent lifecycle, health checks, and Docker command generation |
| `agents_command_generator.py` | Script Generator | Utilities generating customized `docker run` commands and `.env` configs for deployable agents |
| `agents_routes.py` | API Controller | FastAPI router defining endpoints for `/api/v1/agents` |
| `agents_dependencies.py` | Auth Middleware | `get_current_agent` FastAPI dependency verifying `X-Agent-Token` header against SHA-256 token hash |

---

## 3. Database Entities & Affected Tables

### Primary Tables Owned
1. **`agents`** (`Agent`)
   - **Primary Key:** `id` (`UUID`)
   - **Foreign Keys:** `user_id` → `users.id` (CASCADE)
   - **Unique Constraints:** `(user_id, agent_identifier)`, `api_token_hash`
   - **Attributes:** `name`, `agent_identifier`, `api_token_hash` (SHA-256), `status` (`online`, `offline`, `degraded`), `version`, `last_seen_at`, `created_at`, `updated_at`
   - **Cascade Relationships:**
     - `data_sources` (One-to-Many, CASCADE delete)
     - `migration_plans` (One-to-Many, SET NULL on delete)
     - `migration_jobs` (One-to-Many, SET NULL on delete)

---

## 4. Service Layer Specification (`AgentService`)

### 1. `create_agent(session, user_id, data)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `user_id` (`uuid.UUID`): Owner user UUID.
  - `data` (`AgentCreate`): Payload containing `name`, `agent_identifier`, optional `version`, and optional list of initial `data_sources`.
- **Return Value:** `AgentDetailResponse` - Detailed agent object containing the unhashed `raw_api_token` (shown once), generated Docker commands, and created data sources.
- **Business Logic:**
  1. Checks per-user `agent_identifier` uniqueness. Raises `HTTP 409 Conflict` if duplicate.
  2. Generates a secure random token `ag_live_<urlsafe_32_bytes>` and computes its SHA-256 hash using `hash_agent_token`.
  3. Instantiates `Agent` model with status `"offline"`.
  4. Flushes session to acquire `agent.id`.
  5. If initial `data_sources` list provided, iterates and adds `DataSource` ORM instances attached to `agent.id`.
  6. Commits database transaction.
  7. Calls `AgentCommandGenerator.generate_command_payload` to build ready-to-use Docker run bash and PowerShell commands.
  8. Returns `AgentDetailResponse` including the raw token and Docker command payloads.
- **Affected Tables:** `agents` (SELECT, INSERT), `data_sources` (INSERT)
- **Exceptions:**
  - `HTTPException(409 Conflict)`: Identifier already registered by user.
  - `HTTPException(500 Internal Server Error)`: If retrieval after creation fails.

---

### 2. `list_agents(session, user_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `user_id` (`uuid.UUID`): Owner user UUID.
- **Return Value:** `List[AgentResponse]` - List of agents belonging to the user with updated dynamic connectivity status.
- **Business Logic:**
  1. Executes query selecting `Agent` records matching `user_id`, eagerly loading `data_sources`.
  2. Computes dynamic connectivity status based on `last_seen_at` timestamp:
     - If `last_seen_at` is older than 2 minutes (or `None`), marks status as `"offline"`.
     - Otherwise keeps active status.
  3. Returns list of mapped DTO responses.
- **Affected Tables:** `agents` (SELECT), `data_sources` (SELECT)
- **Exceptions:** None.

---

### 3. `get_agent_by_id(session, agent_id, user_id=None)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent_id` (`uuid.UUID`): Primary key of target agent.
  - `user_id` (`Optional[uuid.UUID]`, default=`None`): Optional user ID filter for ownership validation.
- **Return Value:** `Optional[Agent]` - Agent ORM model with `data_sources` eagerly loaded, or `None`.
- **Business Logic:**
  1. Builds query selecting `Agent` by `id == agent_id`.
  2. If `user_id` provided, adds `Agent.user_id == user_id` filter clause.
  3. Uses `selectinload(Agent.data_sources)` for eager loading.
  4. Returns single scalar or `None`.
- **Affected Tables:** `agents` (SELECT), `data_sources` (SELECT)
- **Exceptions:** None.

---

### 4. `get_agent_by_identifier(session, agent_identifier)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent_identifier` (`str`): Logical identifier string of the agent.
- **Return Value:** `Optional[Agent]` - Matching `Agent` ORM model or `None`.
- **Business Logic:**
  1. Executes select filtering on `Agent.agent_identifier == agent_identifier`.
- **Affected Tables:** `agents` (SELECT)
- **Exceptions:** None.

---

### 5. `update_agent(session, agent_id, user_id, data)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent_id` (`uuid.UUID`): Agent ID to update.
  - `user_id` (`uuid.UUID`): Owner user ID.
  - `data` (`AgentUpdate`): DTO with optional `name`, `status`, `version`.
- **Return Value:** `AgentResponse` - Updated agent response DTO.
- **Business Logic:**
  1. Fetches agent via `get_agent_by_id()`. If missing, raises `HTTP 404 Not Found`.
  2. Updates specified non-null fields (`name`, `status`, `version`).
  3. Commits transaction and refreshes model.
- **Affected Tables:** `agents` (SELECT, UPDATE)
- **Exceptions:**
  - `HTTPException(404 Not Found)`: Agent does not exist or belong to user.

---

### 6. `delete_agent(session, agent_id, user_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent_id` (`uuid.UUID`): Agent ID to delete.
  - `user_id` (`uuid.UUID`): Owner user ID.
- **Return Value:** `None`
- **Business Logic:**
  1. Fetches agent via `get_agent_by_id()`. If missing, raises `HTTP 404 Not Found`.
  2. Deletes agent record from session.
  3. Commits transaction (cascading delete to attached `data_sources` and setting null on linked jobs/plans).
- **Affected Tables:** `agents` (SELECT, DELETE, cascades to `data_sources`)
- **Exceptions:**
  - `HTTPException(404 Not Found)`: Agent does not exist.

---

### 7. `heartbeat(session, agent_identifier, token, heartbeat_data)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent_identifier` (`str`): Agent identifier pinging heartbeat.
  - `token` (`str`): Raw API token provided in `X-Agent-Token` header.
  - `heartbeat_data` (`AgentHeartbeat`): DTO containing container version, metrics, and active state.
- **Return Value:** `dict` - Status summary `{"status": "ok", "agent_id": str, "timestamp": str}`.
- **Business Logic:**
  1. Hashes `token` via SHA-256 (`hash_agent_token`).
  2. Selects agent matching `agent_identifier` AND `api_token_hash == token_hash`.
  3. If agent not found, raises `HTTP 401 Unauthorized` ("Invalid agent identifier or API token").
  4. Updates `agent.last_seen_at = datetime.now(timezone.utc)`, `agent.status = "online"`, and `agent.version`.
  5. Commits transaction.
  6. Broadcasts real-time WebSocket event `agent_status_changed` to connected frontend UI clients via `manager.broadcast()`.
- **Affected Tables:** `agents` (SELECT, UPDATE)
- **Exceptions:**
  - `HTTPException(401 Unauthorized)`: Token hash mismatch or invalid agent identifier.

---

### 8. `get_docker_command(session, agent_id, user_id)`
- **Input Parameters:**
  - `session` (`AsyncSession`): Active database session.
  - `agent_id` (`uuid.UUID`): Target agent ID.
  - `user_id` (`uuid.UUID`): Owner user ID.
- **Return Value:** `AgentDockerCommandResponse` - Payload with bash/PowerShell Docker commands and environment setup instructions.
- **Business Logic:**
  1. Fetches agent via `get_agent_by_id()`. If missing, raises `HTTP 404 Not Found`.
  2. Invokes `AgentCommandGenerator.generate_command_payload(agent)` to build commands.
- **Affected Tables:** `agents` (SELECT), `data_sources` (SELECT)
- **Exceptions:**
  - `HTTPException(404 Not Found)`: Agent not found.

---

## 5. API Routes Specification (`agents_routes.py`)

| HTTP Method | Route Path | Description | Service Function Called | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/agents/register` | Register new agent and generate API token | `AgentService.create_agent` | User JWT |
| `GET` | `/api/v1/agents` | List user's registered agents | `AgentService.list_agents` | User JWT |
| `GET` | `/api/v1/agents/{agent_id}` | Get agent details and status | `AgentService.get_agent_by_id` | User JWT |
| `GET` | `/api/v1/agents/{agent_id}/docker-command` | Generate Docker run deployment command | `AgentService.get_docker_command` | User JWT |
| `POST` | `/api/v1/agents/heartbeat` | Agent daemon health & status ping | `AgentService.heartbeat` | Agent Token (`X-Agent-Token`) |
| `DELETE` | `/api/v1/agents/{agent_id}` | Unregister and delete agent | `AgentService.delete_agent` | User JWT |

---

## 6. Inter-Module Dependencies

- **Incoming Dependencies (Modules referencing `agents`):**
  - **`sources`**: Links `DataSource` records to an `Agent`.
  - **`migration_plans`**: References active `Agent` to locate attached data sources for AI plan generation.
  - **`execution`**: Assigns `MigrationJob` tasks to an `Agent`.
- **Outgoing Dependencies (`agents` calls these):**
  - **`users`**: Validates user ownership.
