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


