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

- **[NEW]**: [`apps/api/app/modules/agents/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/agents) - Agent control plane boundary (`agents_models.py`, `agents_routes.py`, `agents_services.py`, `agents_schemas.py`).
- **[NEW]**: [`apps/agent/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent) - Standalone Docker Agent runtime project (`Dockerfile`, `main.py`, `pyproject.toml`).
- **[NEW]**: [`apps/api/alembic/versions/002_add_agents_and_agent_relationships.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/alembic/versions/002_add_agents_and_agent_relationships.py) - Migration adding `agents` table and nullable `agent_id` FK to `connections` and `migration_jobs`.
- **[NEW]**: [`apps/api/alembic/versions/003_add_google_auth_to_users.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/alembic/versions/003_add_google_auth_to_users.py) - Migration adding `google_id` column and making `password_hash` nullable in `users` table.
- **[NEW]**: [`apps/web/app/sign-in/page.tsx`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/web/app/sign-in/page.tsx) & [`apps/web/app/sign-up/page.tsx`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/web/app/sign-up/page.tsx) - Next.js authentication UI pages with dark theme and glassmorphism styling.
- **[NEW]**: [`apps/web/components/auth/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/web/components/auth) - Reusable components (`AuthLayout.tsx`, `SignInForm.tsx`, `SignUpForm.tsx`, `GoogleSignInButton.tsx`, `AuthInput.tsx`, `SplineBackground.tsx`).
- **[NEW]**: [`apps/web/lib/api.ts`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/web/lib/api.ts) - Frontend API client service for FastAPI auth integration.
- **[NEW]**: [`apps/api/tests/unit/test_google_auth.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/unit/test_google_auth.py) - Google OAuth unit test suite.
- **[NEW]**: [`apps/api/tests/integration/test_live_api_suite.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/integration/test_live_api_suite.py) - Live HTTP API call integration test suite testing all 10 auth endpoints and edge case restrictions.
- **[MODIFIED]**: [`apps/api/app/modules/users/users_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/users/users_models.py) - Made `password_hash` nullable, added `google_id` column.
- **[MODIFIED]**: [`apps/api/app/modules/users/users_services.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/users/users_services.py) - Added `get_user_by_google_id`, `get_or_create_google_user`, and strict identity isolation rules.
- **[MODIFIED]**: [`apps/api/app/modules/users/users_routes.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/users/users_routes.py) - Implemented `/auth/google/login`, `/auth/google/callback`, `/auth/google`.
- **[MODIFIED]**: [`apps/api/app/core/config.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/core/config.py) - Added `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`.
- **[MODIFIED]**: [`apps/web/app/layout.tsx`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/web/app/layout.tsx) - Imported `./globals.css` and added dark root styling.
- **[MODIFIED]**: [`apps/web/tailwind.config.js`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/web/tailwind.config.js) & [`apps/web/app/globals.css`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/web/app/globals.css) - Customized glassmorphism, brand glows, and theme colors.
