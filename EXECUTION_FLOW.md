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

- **[NEW]**: [`apps/api/app/modules/users/users_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/users/users_models.py) - `User` model.
- **[NEW]**: [`apps/api/app/modules/sources/sources_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_models.py) - `Connection` model.
- **[NEW]**: [`apps/api/app/modules/profiler/profiler_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/profiler/profiler_models.py) - `MetadataSnapshot`, `MetadataSchema`, `MetadataTable`, `MetadataColumn`, `MetadataConstraint`, `MetadataRelationship` models.
- **[NEW]**: [`apps/api/app/modules/transformation_plans/transformation_plans_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/transformation_plans/transformation_plans_models.py) - `MigrationPlan` model.
- **[NEW]**: [`apps/api/app/modules/execution/execution_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/execution/execution_models.py) - `MigrationJob` and `MigrationError` models.
- **[NEW]**: [`apps/api/alembic.ini`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/alembic.ini), [`alembic/env.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/alembic/env.py), [`alembic/versions/001_initial_control_plane_schema.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/alembic/versions/001_initial_control_plane_schema.py) - Alembic migration environment and initial 11-table schema DDL script.
- **[NEW]**: [`.env`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/.env) & [`apps/api/.env`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/.env) - Environment configuration files containing `DATABASE_URL`, `REDIS_URL`, and app secrets.
- **[NEW]**: [`apps/api/app/modules/sources/sources_connectors/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_connectors) - Database connectors (`postgres`, `mysql`, `mongodb`).
- **[NEW]**: [`apps/api/app/modules/sources/sources_loaders/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_loaders) - Dedicated file loaders package (`csv`, `excel`).
- **[NEW]**: [`apps/api/app/modules/sources/sources_schemas.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_schemas.py) - Pydantic request/response validation schemas for sources.
- **[NEW]**: [`apps/api/app/modules/sources/sources_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_services.py) - Application service orchestrating connector health checks and file uploads.
- **[NEW]**: [`apps/api/app/core/security.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/core/security.py) - Bcrypt password hashing (`hash_password`, `verify_password`) and JWT token management (`create_access_token`, `create_refresh_token`, `decode_jwt_token`).
- **[NEW]**: [`apps/api/app/modules/users/users_schemas.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/users/users_schemas.py) - Pydantic schemas for `UserRegister`, `UserLogin`, `UserUpdate`, `UserResponse`, `TokenResponse`, `MessageResponse`.
- **[NEW]**: [`apps/api/app/modules/users/users_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/users/users_services.py) - Database CRUD operations (`create_user`, `authenticate_user`, `get_user_by_id`, `update_user`, `delete_user`, `list_users`).
- **[NEW]**: [`apps/api/app/modules/users/users_dependencies.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/users/users_dependencies.py) - Auth middleware dependencies (`get_current_user`, `get_current_active_user`) extracting HTTP-only cookies (`access_token`) with `Authorization: Bearer` header fallback.
- **[NEW]**: [`apps/api/app/modules/users/users_routes.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/users/users_routes.py) - FastAPI endpoints for `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/refresh` (token rotation), `/users/me` (GET, PUT, DELETE), `/users/{id}`, and `/users`.
- **[NEW]**: [`apps/api/tests/unit/test_users_auth.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_users_auth.py) - Unit and integration test suite covering password hashing, JWT encoding, HTTP-only cookies, token rotation, and User CRUD operations.
- **[MODIFIED]**: [`apps/api/app/core/config.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/core/config.py) - Added JWT and Cookie configuration options.
- **[MODIFIED]**: [`apps/api/app/main.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/main.py) - Registered `users_router` under `/api/v1`.
