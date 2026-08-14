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
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_routes.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_routes.py) - Documented `POST /agents` and added `GET /agents/{agent_id}/docker-command` endpoint.
- **[MODIFIED]**: [`apps/agent/main.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent/main.py) - Added safe startup scanning and logging of configured source/destination database environments.
- **[MODIFIED]**: [`apps/api/tests/unit/test_agent_api.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_agent_api.py) - Added assertions for Docker command response and verified `GET /agents/{id}/docker-command`.
- **[UNCHANGED]**: Existing authentication, profiling, and transformation database models.



