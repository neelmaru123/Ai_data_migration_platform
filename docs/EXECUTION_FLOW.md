# Codebase Execution Flow (`EXECUTION_FLOW.md`)

This document maps entry points, call stack sequences, and module dependencies across the **AI Data Migration Platform**.

---

## 1. System Entry Points

| Entry Point Mode | Primary Entry File | Trigger / Method |
| :--- | :--- | :--- |
| **FastAPI Gateway** | [`apps/api/app/main.py:L10`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/main.py#L10) | Uvicorn ASGI server (`0.0.0.0:8000`) |
| **Web Frontend** | [`apps/web/app/execution/page.tsx:L2`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/web/app/execution/page.tsx#L2) | Next.js App Router (`localhost:3000`) |
| **Background Worker** | [`apps/api/workers/worker/main.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/docs/workers.md#L3) | Python RQ / Celery consumer loop |

---

## 2. Step-by-Step Execution Order

```text
  Web UI (Next.js)
        │
        │ HTTP POST /api/v1/execution/start
        ▼
  FastAPI Router (apps/api/app/main.py)
        │
        ├────────────────────────────────────────────────┐
        │ Mode A: Cloud Execution                        │ Mode B: Local Script Package
        ▼                                                ▼
  Enqueue Job to Redis                             Call script_generator module
        │                                                │
        ▼                                                ▼
  Worker Consumer Process                          Package standalone ZIP file
        │                                          (run.py + TransformationPlan)
        ▼                                                │
  Stream dataset via Polars/DuckDB                       ▼
        │                                          User downloads & runs locally
        ▼
  Write to Target Database
```

### Call Stack Sequence

1. **HTTP Request Ingress**: Client sends transformation configuration to FastAPI.
2. **Configuration Validation**: Pydantic schemas in `apps/api/app/modules/execution/execution_schemas.py` validate request parameters.
3. **Execution Policy Branching**:
   - **Mode A (Cloud Async)**: `execution_services.py` enqueues job into Redis (`REDIS_URL`). A background worker process picks up the task, streams data via Polars/DuckDB in `50,000` row chunks, and writes directly to target database.
   - **Mode B (Local Script Generation)**: `execution_script_generator` packages the verified `TransformationPlan` JSON, dependencies, and standalone runner script into a downloadable `.zip` ```

---

## 3. Agent Creation & Docker Command Generation Flow

```text
  Web UI (Next.js)
        │
        │ HTTP POST /api/v1/agents
        │ Payload: { name, agent_identifier, data_sources: [ {name, type, role: 'source'|'target', identifier} ] }
        ▼
  FastAPI Gateway (apps/api/app/modules/agents/agents_routes.py:create_agent)
        │
        │ 1. Validate JWT session via get_current_active_user
        │ 2. Delegate to AgentService.create_agent
        ▼
  Agent Service (apps/api/app/modules/agents/agents_services.py)
        │
        │ 1. Verify agent_identifier uniqueness
        │ 2. Generate raw API token (ag_live_...) & SHA-256 hash
        │ 3. Atomically persist Agent + attached DataSource entities
        │ 4. Invoke AgentCommandGenerator.generate_command_payload
        ▼
  Command Generator (apps/api/app/modules/agents/agents_command_generator.py)
        │
        │ 1. Parse all data_sources by role (source / target) & dialect
        │ 2. Generate URL templates with masked credential placeholders:
        │    - SRC_<ID>_URL / DEST_<ID>_URL
        │ 3. Build multi-platform outputs:
        │    - Bash command (docker run -d \ ...)
        │    - PowerShell command (docker run -d ` ...)
        │    - Single-line command
        │    - .env template
        ▼
  Response Output -> Web UI receives AgentDetailResponse with ready-to-run Docker commands
        │
        ▼
  Customer copies command -> Fills passwords locally -> Runs on local PC
        │
        ▼
  Agent boots in Docker -> Reads local env vars -> Sends heartbeat to Control Plane
```

---

## 7. Metadata Introspection & Control Plane Ingestion Flow (Phase 2)

```text
  Customer On-Premise Docker Agent (apps/agent/main.py)
        │
        │ 1. Startup handshake succeeds -> Trigger AgentMetadataEngine
        ▼
  Metadata Introspection Engine (apps/agent/metadata_engine.py)
        │
        │ 1. Introspect local DBs via SQL information_schema queries
        │ 2. Construct Schema AST: Schemas, Tables, Columns, Constraints, FK Relationships
        │ 3. HTTP POST /api/v1/metadata/sync with X-Agent-Token header
        ▼
  FastAPI Control Plane Gateway (apps/api/app/modules/metadata/metadata_routes.py:sync_agent_metadata)
        │
        │ 1. Authenticate agent token via get_current_agent dependency
        │ 2. Delegate payload to MetadataService.ingest_agent_metadata_snapshot
        ▼
  Metadata Service (apps/api/app/modules/metadata/metadata_services.py)
        │
        │ 1. Match target DataSource entity by UUID or clean identifier
        │ 2. Query latest snapshot version & compute next_version = version + 1
        │ 3. Persist MetadataSnapshot header
        │ 4. Bulk insert MetadataSchema, MetadataTable, MetadataColumn, MetadataConstraint
        │ 5. Map foreign key column IDs & insert MetadataRelationship records
        │ 6. Update DataSource status = 'profiled' & commit transaction
        │ 7. Push METADATA_PROFILED event over WebSocket via manager.broadcast_to_agent()
        ▼
  Dashboard Web UI receives WebSocket notification & renders full DB Schema Tree
```

---

## 8. Impact & Delta Analysis (Phase 2 Metadata Domain)

- **[RENAMED]**: `apps/api/app/modules/profiler/` $\rightarrow$ [`apps/api/app/modules/metadata/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/metadata) - Renamed feature module to `metadata` domain.
- **[NEW]**: [`apps/agent/metadata_engine.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent/metadata_engine.py) - Local SQL database schema introspection engine for on-premise Docker Agent.
- **[NEW]**: [`apps/api/app/modules/metadata/metadata_schemas.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/metadata/metadata_schemas.py) - Pydantic validation schemas for metadata snapshot ingestion and REST DTOs.
- **[NEW]**: [`apps/api/app/modules/metadata/metadata_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/metadata/metadata_services.py) - Business operations service handling snapshot auto-versioning, relational persistence, and WebSocket broadcasting.
- **[NEW]**: [`apps/api/app/modules/metadata/metadata_routes.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/metadata/metadata_routes.py) - REST API endpoints (`/api/v1/metadata/sync`, `/api/v1/metadata/sources/{id}/snapshots`).
- **[NEW]**: [`apps/api/tests/unit/test_metadata_api.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_metadata_api.py) - Automated test suite for metadata snapshot sync, versioning, and ownership security.
- **[NEW]**: [`apps/api/app/modules/agents/agents_command_generator.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_command_generator.py) - Dynamic CLI & environment template generator for multi-source and target migration Docker containers.
- **[NEW]**: [`apps/api/tests/unit/test_agent_command_generator.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_agent_command_generator.py) - Unit test suite for Docker command generation across database dialects and shell syntaxes.
- **[MODIFIED]**: [`apps/api/app/core/config.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/core/config.py) - Added `BACKEND_URL` and `AGENT_DOCKER_IMAGE` configuration properties.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_schemas.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_schemas.py) - Added `docker_command`, `docker_command_powershell`, `docker_command_oneline`, `env_template` to `AgentDetailResponse` and defined `AgentDockerCommandResponse`.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_services.py) - Integrated `AgentCommandGenerator` into `create_agent` and added `get_agent_docker_command`.
- **[MODIFIED]**: [`apps/agent/main.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent/main.py) - Added concurrent ThreadPoolExecutor socket checks, degraded status computation, graceful offline signal handling, and retry loop backoff.

---

## 4. Impact & Delta Analysis

- **[NEW]**: [`apps/api/app/modules/agents/agents_command_generator.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_command_generator.py) - Dynamic CLI & environment template generator for multi-source and target migration Docker containers.
- **[NEW]**: [`apps/api/tests/unit/test_agent_command_generator.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_agent_command_generator.py) - Unit test suite for Docker command generation across database dialects and shell syntaxes.
- **[MODIFIED]**: [`apps/api/app/core/config.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/core/config.py) - Added `BACKEND_URL` and `AGENT_DOCKER_IMAGE` configuration properties.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_schemas.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_schemas.py) - Added `docker_command`, `docker_command_powershell`, `docker_command_oneline`, `env_template` to `AgentDetailResponse` and defined `AgentDockerCommandResponse`.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_services.py) - Integrated `AgentCommandGenerator` into `create_agent` and added `get_agent_docker_command`.
- **[MODIFIED]**: [`apps/agent/main.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent/main.py) - Added concurrent ThreadPoolExecutor socket checks, degraded status computation, graceful offline signal handling, and retry loop backoff.
- **[MODIFIED]**: [`apps/api/app/main.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/main.py) - Replaced on_event with modern lifespan context manager and started periodic background stale watchdog task.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_models.py) - Replaced global unique constraint on `agent_identifier` with composite `UniqueConstraint("user_id", "agent_identifier")`.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_schemas.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_schemas.py) - Added `VALID_AGENT_STATUS` Literal and removed `status` from `AgentUpdate`.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_services.py) - Added per-user uniqueness check, fuzzy data source identifier matching, and `check_stale_agents_and_jobs` watchdog recovery.
- **[MODIFIED]**: [`apps/api/tests/unit/test_agent_api.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_agent_api.py) - Added comprehensive edge case validation tests (watchdog recovery, per-user uniqueness, status validation, graceful shutdown).
- **[UNCHANGED]**: Existing authentication, profiling, and transformation database models.

---

## 5. Agent Heartbeat Diagnostics & Watchdog Recovery Flow

```text
  Docker Agent (apps/agent/main.py)
        │
        │ 1. Collect configured DB URLs from env (SRC_..._URL, DEST_..._URL)
        │ 2. Execute parallel socket checks via ThreadPoolExecutor (timeout ≤ 3.5s)
        │ 3. Compute status: 'online' (all OK), 'degraded' (any failing), or 'offline' (on SIGTERM)
        ▼
  HTTP POST /api/v1/agents/heartbeat (X-Agent-Token: ag_live_...)
        │
        ▼
  FastAPI Ingress (apps/api/app/modules/agents/agents_routes.py)
        │
        │ 1. Authenticate agent via SHA-256 token hash (get_current_agent)
        │ 2. Delegate to AgentService.process_agent_heartbeat
        ▼
  Agent Service (apps/api/app/modules/agents/agents_services.py)
        │
        │ 1. Update agent.status, version, last_seen_at
        │ 2. Fuzzy match incoming reports against data_sources (pg_primary, src_pg_primary)
        │ 3. Update DataSource status ('healthy', 'ConnectionRefused', 'UnfilledPlaceholder')
        │ 4. Broadcast real-time WebSocket event (AGENT_CONNECTED / AGENT_HEARTBEAT / AGENT_STATUS_CHANGED)
        ▼
  Web UI Dashboard receives live WebSocket update (status badges & diagnostic errors update in real-time)

========================================================================================

  Background Stale Watchdog (apps/api/app/main.py -> AgentService.check_stale_agents_and_jobs)
        │
        │ Runs every 20 seconds in FastAPI Lifespan
        │ 1. Queries agents where status IN ('online', 'busy', 'degraded') AND last_seen_at < (NOW - 60s)
        │ 2. Marks stale agents as status='offline'
        │ 3. Finds any MigrationJob with status IN ('running', 'preparing') for those agents
        │ 4. Transitions orphaned jobs to status='failed', error_message='Agent disconnected or timed out'
        │ 5. Broadcasts AGENT_DISCONNECTED and JOB_FAILED over WebSockets to UI
```





---

---

# Execution Flow - Frontend Authentication & HTTP-Only Cookie Client (`apps/web`)

## 1. Entry Point & Provider Lifecycle
- **File**: [`apps/web/app/layout.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/layout.tsx#L12)
- **Wrapper**: Wraps entire App Router with [`StoreProvider`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/providers/StoreProvider.tsx#L12).
- **Initialization**: Creates singleton instances of Redux Store (`makeStore()`), TanStack Query Client (`QueryClient`), `<Toaster>` (`react-hot-toast`), and React Query DevTools in development.

## 2. API Call & Automatic Token Refresh Flow
1. **Component Trigger**: Component invokes auth query/mutation hook (e.g. `useAuthUser()` in [`useAuthUser.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/hooks/queries/useAuthUser.ts#L6)).
2. **Service Delegation**: Query function calls `authService.getMe()` in [`authService.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/authService.ts#L29).
3. **Axios Request Interceptor**: [`services/axios.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/axios.ts#L13) checks `Cookies.get('active_org_id')` and attaches header `X-Organization-Id` if set.
4. **Response / 401 Handling**:
   - If HTTP request succeeds: Returns JSON response data directly.
   - If HTTP request fails with 401:
     - Interceptor checks if request URL is `/auth/refresh` or `/auth/login` (rejects immediately to avoid infinite loops).
     - Queues concurrent requests using `failedQueue` and lock `isRefreshing = true`.
     - Issues POST to `/auth/refresh` using HTTP-only cookie credentials (`withCredentials: true`).
     - On successful renewal: Clears queue (`processQueue(null)`) and retries original request `apiClient(originalRequest)`.
     - On refresh failure: Displays toast `Session expired. Please log in again.` via `react-hot-toast` and redirects window to `/login`.
   - On 500 or Network errors: Automatically displays error toast `Network error...` or `A server error occurred...`.

## 3. Impact & Delta Analysis (Frontend Infrastructure)
- **[NEW]**: [`apps/web/.env.local`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/.env.local) - Environment configuration (`NEXT_PUBLIC_API_URL`).
- **[NEW]**: [`apps/web/services/axios.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/axios.ts) - Axios HTTP client with HTTP-only cookie credentials, `X-Organization-Id` header, 401 token refresh queue, and toast error notifications.
- **[NEW]**: [`apps/web/services/authService.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/authService.ts) - Auth service methods using `apiClient`.
- **[NEW]**: [`apps/web/store/index.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/store/index.ts) - Redux Toolkit store & custom typed hooks.
- **[NEW]**: [`apps/web/store/slices/authSlice.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/store/slices/authSlice.ts) - Redux auth slice.
- **[NEW]**: [`apps/web/store/slices/uiSlice.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/store/slices/uiSlice.ts) - Redux local UI slice.
- **[NEW]**: [`apps/web/hooks/queries/useAuthUser.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/hooks/queries/useAuthUser.ts) - TanStack Query read hook for user profile.
- **[NEW]**: [`apps/web/hooks/mutations/useAuthMutations.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/hooks/mutations/useAuthMutations.ts) - TanStack Query mutation hooks (`useLogin`, `useLogout`).
- **[NEW]**: [`apps/web/providers/StoreProvider.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/providers/StoreProvider.tsx) - Client context provider wrapping RTK + TanStack Query + Toaster + DevTools.

---

# Execution Flow - Agent Creation Wizard (`apps/web/app/agents/create`)

## 1. Entry Point
- **File**: [`apps/web/app/agents/create/page.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/agents/create/page.tsx#L12)
- **Trigger**: User navigates to `/agents/create` in browser.

## 2. Step-by-Step Execution Sequence
1. **Topology Selection (Step 1)**: User picks a migration ratio card in [`TopologySelector.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/agents/TopologySelector.tsx) (`1:1`, `2:1`, `3:1`, or `Custom N:1`). Clicking "Configure Databases" computes source count and moves state to Step 2.
2. **Database Engine & Agent Configuration (Step 2)**: Form in [`DatabaseConfigForm.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/agents/DatabaseConfigForm.tsx) captures agent metadata and database engine choices (restricted strictly to `postgresql`, `mysql`, `mongodb`, `csv`, `excel`).
3. **API Submission**: Form submit triggers `handleFormSubmit()`, invoking `agentService.createAgent()` in [`agentService.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/agentService.ts) which calls `POST /api/v1/agents`.
4. **Docker Command Generation**: Calls `agentService.generateDockerCommand()`, fetching custom `docker run` / `docker-compose.yml` snippets from `POST /api/v1/agents/{id}/docker-cmd` (or using client-side fallback).
5. **CLI Display & Live Status Monitoring (Step 3)**: [`DockerCommandOutput.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/agents/DockerCommandOutput.tsx) presents the command with copy-to-clipboard button and subscribes to WebSocket (`ws://.../api/v1/agents/ws/{id}`) to listen for live heartbeat status transition (`offline` -> `online`).

## 3. Impact & Delta Analysis (Agent Creation UI)
- **[NEW]**: [`apps/web/types/agent.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/types/agent.ts) - DTOs for agent creation, database sources, topologies, and docker command payloads.
- **[NEW]**: [`apps/web/services/agentService.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/agentService.ts) - API service with Docker command generation and WebSocket heartbeat listener.
- **[NEW]**: [`apps/web/components/agents/TopologySelector.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/agents/TopologySelector.tsx) - Interactive migration ratio card selector (`1:1`, `2:1`, `3:1`, `Custom N:1`).
- **[NEW]**: [`apps/web/components/agents/DatabaseConfigForm.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/agents/DatabaseConfigForm.tsx) - Dynamic source and destination database form with engine selection (`postgresql`, `mysql`, `mongodb`, `csv`, `excel`).
- **[NEW]**: [`apps/web/components/agents/DockerCommandOutput.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/agents/DockerCommandOutput.tsx) - Terminal command output with tabs, copy-to-clipboard, and live agent status badge.
- **[NEW]**: [`apps/web/app/agents/create/page.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/agents/create/page.tsx) - Main wizard layout page at `/agents/create`.

---

# Execution Flow - AI Migration Plan Generation & Local Execution (Phase 3 & Phase 4)

## 1. Entry Points
- **Plan Generation**: HTTP POST `/api/v1/plans/generate` in [`apps/api/app/modules/migration_plans/migration_plans_routes.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/migration_plans/migration_plans_routes.py)
- **Local Agent Run**: Docker Agent main entry point [`apps/agent/main.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent/main.py)

## 2. Step-by-Step Execution Sequence

```text
  Client (Web / Swagger / Script)
        │
        │ 1. POST /api/v1/plans/generate (agent_id, target_config)
        ▼
  FastAPI Route (migration_plans_routes.py:generate_plan)
        │
        │ 2. Fetch Agent's MetadataSnapshots for all DataSources
        │ 3. MetadataContextSerializer converts snapshots to Zero-Raw-Data Context
        ▼
  AI Plan Generator Service (migration_plans_llm.py:LLMPlanGeneratorService)
        │
        │ 4. Invokes ChatGoogleGenerativeAI (gemini-3.5-flash-lite)
        │ 5. Parses output using PydanticOutputParser(TransformationPlanAST)
        ▼
  Control Plane Persistence (migration_plans_services.py)
        │
        │ 6. Persists MigrationPlan DB record & broadcasts WebSocket event
        │ 7. Client receives complete TransformationPlanAST (DDL + ETL rules)
        ▼
  Local Docker Agent Execution (Phase 4 Pipeline)
        │
        │ 8. Local Agent receives EXECUTE_MIGRATION command
        │ 9. Target DDL Executor executes pre_migration_ddl on local target DB (db_4)
        │ 10. Polars / DuckDB reads chunks from local source DBs (db_1, db_2, db_3)
        │ 11. Applies column AST mapping (merge_concat, split, type_cast, rekey)
        │ 12. Performs in-memory multi-database table merge & email deduplication
        │ 13. Bulk-loads transformed rows directly into local target DB (db_4)
        │ 14. Executes post_migration_ddl (foreign key constraints)
        ▼
  Progress Reporting -> Docker Agent posts status & row counts back to Control Plane
```

## 3. Impact & Delta Analysis (Phase 3 & Phase 4 Modules)
- **[NEW]**: [`apps/api/app/modules/migration_plans/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/migration_plans) - Models, schemas, REST endpoints, and Gemini 3.5 Flash Lite engine.
- **[NEW]**: [`apps/api/app/modules/execution/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/execution) - Execution REST API routes (`/api/v1/plans/{plan_id}/execute`, `/api/v1/executions`, `/api/v1/agents/tasks`, `/api/v1/executions/{id}/progress`), using existing `migration_jobs` DB table.
- **[MODIFIED]**: [`apps/agent/main.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent/main.py) - Added `auto_register_agent`, `poll_and_execute_tasks` background task poller, and header-based authentication (`X-Agent-Token`).
- **[NEW]**: [`apps/agent/execution_engine.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent/execution_engine.py) - Production local ETL engine featuring `DDLExecutor`, `SourceConnectorFactory` (PostgreSQL, MySQL, MongoDB, CSV, Excel), `ASTTransformer` (all 9 transformation types), `TableMerger` (3-way merge & deduplication), `TargetWriterFactory` (PostgreSQL, MySQL, MongoDB bulk loader), `CheckpointManager` (resumable state), and `ProgressReporter`.

---

## 8. Fault Tolerance & One-Click UI Job Resumption Flow

```text
  Customer On-Premise Docker Agent (apps/agent/execution_engine.py)
        │
        │ ETL Migration encounters an anomaly (Bad Row / Network Drop / Container Crash)
        ▼
   Fault Handling Policy Branching:
        ├────────────────────────────────────────────────────────┐
        │ Scenario 1: Bad Row Data (Row Isolation)               │ Scenario 2: Network Drop / Container Crash
        ▼                                                        ▼
   Bulk insert fails -> Fallback to per-row insert          CheckpointManager saved offset (e.g. Row 850,000)
   Valid rows saved -> Bad rows logged to Dead-Letter log   Job status set to 'failed' / 'interrupted' in DB
        │                                                        │
        └──────────────────────────┬─────────────────────────────┘
                                   ▼
   ProgressReporter sends error stack trace to Control Plane (POST /api/v1/execution/{id}/progress)
                                   │
                                   ▼
   Control Plane broadcasts WebSocket event (JOB_FAILED) -> Web UI shows Red Error Card ❌
                                   │
                                   ▼
   User handles error 100% inside Web UI (NO TERMINAL COMMANDS REQUIRED):
        ├────────────────────────────────────────────────────────┐
        │ Option A: One-Click 'Resume Migration'                 │ Option B: One-Click 'Edit Plan & Retry'
        ▼                                                        ▼
   User clicks 'Resume Migration'                            User fixes mapping in UI & re-approves plan
   POST /api/v1/executions/{id}/resume                       POST /api/v1/plans/{plan_id}/execute
   Job status reset to 'queued'                              New job queued in migration_jobs table
        │                                                        │
        └──────────────────────────┬─────────────────────────────┘
                                   ▼
   Local Docker Agent Task Poller (main.py:poll_and_execute_tasks)
   Discovers queued job -> Loads CheckpointManager -> RESUMES AT ROW 850,000 INSTANTLY 🚀
```

---

## 9. Phase 5 LangGraph Stateful Agent & Feasibility Validation Flow

```text
  Web UI / API Client (migration_plans_routes.py)
        │
        │ 1. POST /api/v1/plans/generate  OR  POST /api/v1/plans/{id}/refine
        ▼
  LangGraph State Graph Engine (migration_plans_graph.py)
        │
        ├─► Node 1: serialize_context_node
        │     - Converts MetadataSnapshots to Zero-Raw-Data YAML context string
        │
        ├─► Node 2: generate_plan_ast_node
        │     - Invokes Gemini via LLMPlanGeneratorService (generates/refines AST with 3-attempt retry loop)
        │
        ├─► Node 3: validate_feasibility_node
        │     - Runs MigrationPlanValidator (5-stage schema & FK reference checks)
        │
        ├─► Conditional Router 1 (is_valid?)
        │     ├─► False & attempt_count < 3 ──► Node 4: auto_correct_ast_node (Feeds errors back to LLM, try/except guarded)
        │     ├─► False & attempt_count >= 3 ─► Node 8: explanation_generator_node (Generates diagnostic report)
        │     └─► True ───────────────────────► Node 5: human_approval_interrupt_node (Pauses Graph State)
        │
        ▼
  Human Review State (Web UI Visual Editor)
        │
        ├─► User action: Natural language prompt ─► Node 6: process_user_feedback_node (Loops to Node 2)
        ├─► User action: Direct UI edits ─────────► Node 7: process_manual_edits_node (Re-validates via Node 3)
        └─► User action: Approve Plan ────────────► Node 9: finalize_and_persist_node (Persists & Emits PLAN_GENERATED WS Event)
        │
        ▼
  Execution Guard (execution_routes.py & execution_services.py)
        │
        │ POST /api/v1/plans/{id}/execute checks:
        │ 1. plan.status == 'completed' (HITL Approved)
        │ 2. plan.is_valid == True (Schema Verified)
        │ Unapproved or invalid plans blocked with HTTP 422


---

## 10. Multi-Source Bounded ETL Execution & Outcome Verification Flow

```text
  Customer On-Premise Docker Agent (apps/agent/execution_engine.py:ExecutionOrchestrator.run_job)
        │
        ├─► 1. Checkpoint Key Isolation
        │     - Checkpoint path: checkpoint_{job_id}_{target_table}_{source_identifier}_{source_table}.json
        │     - Falls back to legacy checkpoint_{job_id}_{target_table}.json for legacy runs
        │     - Resumes each source independently from its own last_offset
        │
        ├─► 2. Multi-Source Staging & Bounded Streaming (DuckDB)
        │     - Creates temporary DuckDB staging database: staging_{job_id}_{target_table}.duckdb
        │     - As source chunks are read and transformed, appends to DuckDB with _seq_id
        │     - Discards extracted Polars DataFrames immediately (RAM stays bounded to 1 chunk ~50k rows)
        │     - Runs SQL deduplication (first_wins / last_updated_wins) out of DuckDB staging
        │     - Streams deduplicated chunks out of DuckDB into TargetWriterFactory.bulk_load
        │
        ├─► 3. Database Write Outcome Verification & Reporting
        │     - SQL Sink (Postgres/MySQL): Inspects result.rowcount to calculate exact inserted vs skipped conflict rows
        │     - Mongo Sink: Catches pymongo.errors.BulkWriteError to parse details["writeErrors"] for exact success/failure counts
        │     - ProgressReporter sends payload with successful_rows, failed_rows, and skipped_rows to Control Plane
        │
        ├─► 4. Decoupled Background Heartbeat Loop (main.py:start_heartbeat_thread)
        │     - Background daemon thread sends periodic send_heartbeat every 20s
        │     - Continues firing heartbeats during long ETL jobs (prevents false offline status)
        │     - Responds to stop_event for clean SIGINT/SIGTERM process termination
        │
        ├─► 5. Atomic Job Claiming (execution_services.py:get_pending_tasks_for_agent)
        │     - SELECT ... WHERE status = 'queued' WITH FOR UPDATE SKIP LOCKED
        │     - Atomically updates claimed job status to 'preparing' before returning
        │     - Prevents duplicate agent processes from executing the same job
        │
        ├─► 6. Exception Propagation & Backend Watchdog (execution_services.py:check_stale_jobs)
        │     - Agent-side: Top-level try/except catches fatal execution errors and sends status="failed" with error_message
        │     - Backend Watchdog: Detects jobs stuck in 'running'/'preparing' updated > 5 min ago and fails them automatically
        │
        ├─► 7. Primary Key Conflict-Resolution Strategies (execution_engine.py:ASTTransformer)
        │     - Implements keep_original, autoincrement_offset, prefix_id, and uuid_v4_rekey
        │     - Emits validator warning when rekeying PKs for multi-source merges
        │
        ├─► 8. Mongo Keyset Pagination (execution_engine.py:SourceConnectorFactory)
        │     - find({"_id": {"$gt": last_id}}).sort("_id", 1).limit(chunk_size)
        │     - Eliminates O(offset) skip drift during concurrent live writes
        │
        ├─► 9. Residual Unmapped Field Capture (execution_engine.py:ASTTransformer)
        │     - Collects unmapped document fields and serializes into extra_attributes JSON column
        │
        └─► 10. Reconciled Mongo Introspection (sources_connectors_mongodb.py)
              - 100-doc sampling + depth-3 recursive path flattening matching agent metadata engine
```
```


