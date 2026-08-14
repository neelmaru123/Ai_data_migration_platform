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
   - **Mode B (Local Script Generation)**: `execution_script_generator` packages the verified `TransformationPlan` JSON, dependencies, and standalone runner script into a downloadable `.zip` archive.
4. **Audit & Log Update**: Progress and status metrics are logged into PostgreSQL `migration_jobs` and `execution_logs` tables.

---

## 3. Impact & Delta Analysis

- **[NEW]**: [`apps/api/app/modules/sources/sources_dependencies.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_dependencies.py) - Middleware dependencies (`get_verified_agent`, `get_verified_data_source`) enforcing agent/source ownership verification.
- **[NEW]**: [`apps/api/alembic/versions/004_update_database_architecture_agent_centric.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/alembic/versions/004_update_database_architecture_agent_centric.py) - Reversible migration creating `data_sources` and `migration_plan_snapshots`, removing obsolete `connections` table.
- **[NEW]**: [`apps/api/tests/unit/test_agent_centric_db_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_agent_centric_db_models.py) - Unit test suite for 13 agent-centric DB models and cascade behavior.
- **[NEW]**: [`apps/api/tests/unit/test_agent_api.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_agent_api.py) - Unit and API integration test suite covering Agent registration, concurrent source/target DB creation, heartbeat, and ownership security.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_schemas.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_schemas.py) - Added `InitialDataSourceCreate`, `AgentCreate`, `AgentUpdate`, `AgentHeartbeat`, `AgentResponse`, `AgentDetailResponse`.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_services.py) - Implemented `AgentService` CRUD with atomic single-transaction creation of Agent + initial Source and Target DB identities.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_routes.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents/agents_routes.py) - Implemented `/agents` endpoints (`POST`, `GET`, `GET /{id}`, `PUT /{id}`, `POST /{id}/heartbeat`, `DELETE /{id}`).
- **[MODIFIED]**: [`apps/api/app/modules/sources/sources_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_models.py) - Replaced `Connection` with `DataSource` model (`id`, `agent_id`, `name`, `type`, `role`, `identifier`).
- **[MODIFIED]**: [`apps/api/app/modules/sources/sources_schemas.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_schemas.py) - Created `DataSourceCreate`, `DataSourceUpdate`, `DataSourceResponse` with Pydantic `Literal` validation for `type` and `role`.
- **[MODIFIED]**: [`apps/api/app/modules/sources/sources_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_services.py) - Updated `SourceService` for `DataSource` identity CRUD with no-op PATCH protection.
- **[MODIFIED]**: [`apps/api/app/modules/sources/sources_routes.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_routes.py) - Updated `/data-sources` endpoints with ownership verification middleware.
- **[MODIFIED]**: [`apps/api/app/modules/transformation_plans/transformation_plans_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/transformation_plans/transformation_plans_models.py) - Added `MigrationPlanSnapshot` join table and nullable `agent_id` with `ondelete="SET NULL"`.
- **[MODIFIED]**: [`apps/api/app/modules/profiler/profiler_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/profiler/profiler_models.py) - Replaced `connection_id` with `data_source_id` FK and added `created_at`/`updated_at`.
- **[MODIFIED]**: [`apps/api/tests/integration/test_db_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/integration/test_db_models.py) & [`apps/api/tests/unit/test_users_auth.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_users_auth.py) - Updated tests for `DataSource` identity model.

