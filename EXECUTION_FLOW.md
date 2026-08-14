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


