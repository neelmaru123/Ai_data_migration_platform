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




