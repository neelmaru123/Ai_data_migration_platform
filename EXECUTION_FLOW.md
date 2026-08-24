# Execution Flow — Schema Catalog Profiling, AI Migration Blueprinting & ETL Execution

## 1. Entry Point
- **Files**:
  - [`apps/web/app/sources/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/sources/page.tsx)
  - [`apps/web/app/profiling/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/profiling/page.tsx)
  - [`apps/web/app/transformation-plan/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/transformation-plan/page.tsx)
  - [`apps/web/app/execution/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/execution/page.tsx)
- **Triggers**:
  - Navigating to `/sources` or `/profiling` after registering a Docker agent.
  - Clicking **"Generate AI Migration Plan"** from the Schema Inspector.
  - Opening `/transformation-plan?planId={id}` to review, edit, refine, or approve AI migration blueprints.
  - Clicking **"APPROVE & EXECUTE MIGRATION"** to dispatch the migration job to the local Docker Agent.

## 2. Step-by-Step Execution Sequence

### Phase A: Live Agent Connection Monitoring & Catalog Introspection
1. **Agent List Fetch**: `SourcesPage` invokes `agentService.listAgents()` (`GET /api/v1/agents`) to fetch registered agents.
2. **WebSocket Subscription**: `AgentStatusBanner` connects to `ws://localhost:8000/api/v1/agents/ws/{agentId}?token={token}`.
3. **Live Status Signals**:
   - Agent heartbeat ping emits `AGENT_CONNECTED` / `AGENT_HEARTBEAT` -> Status pill updates to `ONLINE`.
   - Agent introspection sync emits `METADATA_PROFILED` -> Triggers catalog refetch.
4. **Metadata Catalog Rendering**:
   - `SchemaCatalogViewer` invokes `metadataService.getLatestSnapshot(sourceId)` (`GET /api/v1/metadata/sources/{source_id}/latest`).
   - Renders searchable list of tables, estimated row counts, column types, PK/FK attributes, and constraint definitions.

### Phase B: AI Migration Plan Generation & Transformation Blueprinting
1. **Plan Generation Trigger**:
   - User configures target database dialect & optional instructions in `GeneratePlanAction`.
   - Submits `planService.createPlan(agentId, targetConfig)` (`POST /api/v1/plans`).
   - Redirects to `/transformation-plan?planId={plan.id}`.
2. **Transformation Blueprint AST Visualization**:
   - `PlanBlueprintViewer` fetches plan detail via `planService.getPlan(planId)` (`GET /api/v1/plans/{plan_id}`).
   - Checks active job status via `executionService.listUserExecutions()` to mount active job banner if execution is already running.
   - Renders **Execution Order Sequence Timeline** (dependency order), **Table Mapping Matrix**, and **AI Confidence Score**.
3. **AI Plan Refinement**:
   - User types prompt feedback -> Calls `planService.refinePlan(planId, prompt)` (`POST /api/v1/plans/{plan_id}/refine`).
   - Updates AST dynamically.
4. **Plan Approval**:
   - User clicks **"APPROVE MIGRATION PLAN"** -> Calls `planService.approvePlan(planId)` (`POST /api/v1/plans/{plan_id}/approve`).
   - Transition status to `COMPLETED` / `APPROVED`.

### Phase C: Safe ETL Job Execution & Progress Monitoring
1. **Job Dispatch**:
   - `PlanBlueprintViewer` calls `executionService.startPlanExecution(planId)` (`POST /api/v1/plans/{plan_id}/execute`).
   - `ExecutionService.create_execution_job()` checks for existing active jobs (`queued`, `preparing`, `running`) on `planId` and raises HTTP `409 Conflict` if duplicate execution is attempted.
   - Queues `MigrationJob` in `queued` status and notifies Docker Agent via WebSocket `EXECUTION_QUEUED`.
2. **Task Polling & Claim**:
   - Docker Agent daemon polls `GET /api/v1/agents/tasks` (`poll_and_execute_tasks()`).
   - Backend atomically claims job with `FOR UPDATE SKIP LOCKED` and transitions status to `preparing`.
3. **ETL Migration Pipeline Execution**:
   - **Step 1 (Pre-DDL)**: `DDLExecutor.execute_ddl_list()` executes target table creation DDL. Non-benign DDL errors halt execution immediately.
   - **Step 2 (Extraction & Transformation)**: `SourceConnectorFactory.read_source_chunk()` extracts source data via Keyset Pagination. Explicit source DB URL matching prevents multi-source cross-talk. `ASTTransformer` transforms chunks in-memory via Polars. `TargetWriterFactory.bulk_load()` bulk-inserts into target DB, ensuring PostgreSQL `session_replication_role` resets to `'origin'` in `finally` blocks.
   - **Step 3 (Post-DDL)**: `DDLExecutor.execute_ddl_list()` creates foreign key constraints.
   - **Step 4 (Completion & Cleanup)**: `CheckpointManager.clear_job_checkpoints(job_id)` removes temporary checkpoint `.json` files and reports `completed` status to Control Plane.
4. **Watchdog Recovery**:
   - `check_stale_jobs()` and `check_stale_agents_and_jobs()` periodically check for orphaned `queued`, `preparing`, or `running` jobs and mark them as `failed` if the assigned agent times out.

## 3. Impact & Delta Analysis (AI Modifications)
- **[MODIFIED]**: [`apps/api/app/modules/execution/execution_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_services.py) - Added active job concurrency lock (HTTP 409) and queued status watchdog recovery.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_services.py) - Included queued jobs in dead agent watchdog recovery loop.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_routes.py) - Added first-frame JSON auth payload support for WebSockets.
- **[MODIFIED]**: [`apps/agent/main.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/main.py) - Enforced explicit environment credentials for agent auto-registration.
- **[MODIFIED]**: [`apps/agent/engine/orchestrator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/orchestrator.py) - Eliminated silent source DB fallback; added checkpoint cleanup call on completion.
- **[MODIFIED]**: [`apps/agent/engine/checkpoint.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/checkpoint.py) - Added `clear_job_checkpoints()` method.
- **[MODIFIED]**: [`apps/agent/engine/writers/target_writer.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/writers/target_writer.py) - Enclosed `session_replication_role` in `try...finally` to ensure connection pool reset to `'origin'`.
- **[MODIFIED]**: [`apps/web/services/planService.ts`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/services/planService.ts) - Added 3-minute request timeout for plan generation and refinement calls.
- **[MODIFIED]**: [`apps/web/services/agentService.ts`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/services/agentService.ts) - Updated `connectAgentWebSocket` to send auth frame on open.
- **[MODIFIED]**: [`apps/web/app/execution/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/execution/page.tsx) - Corrected active job status filter and added 3s auto-polling interval.
- **[MODIFIED]**: [`apps/web/components/plans/PlanBlueprintViewer.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanBlueprintViewer.tsx) - Added previous valid AST revert strategy, draft_failed error alert card, and 409 Conflict handler.
- **[MODIFIED]**: [`apps/web/components/profiling/GeneratePlanAction.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/profiling/GeneratePlanAction.tsx) - Added step-by-step progress indicator and duration notice during plan generation.
- **[MODIFIED]**: [`DECISIONS.md`](file:///d:/GitHub/Ai_data_migration_platform/DECISIONS.md) - Documented architectural decision log for critical & high priority edge case fixes.
- **[MODIFIED]**: [`EXECUTION_FLOW.md`](file:///d:/GitHub/Ai_data_migration_platform/EXECUTION_FLOW.md) - Updated execution sequence & delta analysis.
