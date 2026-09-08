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

### Phase D: AI Execution Error Diagnosis & Self-Healing Loop
1. **Agent Error Dispatch**:
   - Docker Agent catches runtime exception in universal 7-phase guard in [`main.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/main.py#L503-L512).
   - Dispatches `POST /api/v1/execution/jobs/{job_id}/progress` with `status: "failed"` and `error_message`.
2. **Background AI Diagnosis Synthesis**:
   - Backend `update_job_progress()` sets `job.status = "failed"` and spawns `asyncio.create_task(_run_diagnosis_background(job_id))` using a fresh `AsyncSessionLocal()`.
   - `ExecutionService.diagnose_job_failure()` acquires atomic row lock (`with_for_update(skip_locked=True)`), checks pattern/regex rules, synthesizes plain-English explanation, formats copyable `docker run` command with password placeholders, and persists `job.ai_diagnosis`.
3. **UI Real-Time Rendering & Remediation**:
   - `JobExecutionBanner.tsx` 2-second polling tick fetches updated job details via `executionService.getExecutionDetails()`.
   - UI renders **AI Failure Diagnosis Card**, root cause badge, step-by-step remediation list, and 1-click **Copy Command** button.
   - User can click **`⚡ RETRY MIGRATION JOB`** to queue a fresh job attempt or switch between historical runs (`Run #1`, `Run #2`) using the run selector dropdown.

### Phase E: Docker Agent Fatal Stopping Error Reporting & UI Callout
1. **Agent Error Trapping (`main.py`)**:
   - `report_fatal_error_and_exit(message, category)` is invoked upon startup failure or unhandled crash.
   - Attempts authenticated heartbeat (`status: "error"`, `error_message`, `error_category`).
   - If token is invalid/rejected (401/403) or missing, falls back to `POST /api/v1/agents/fatal-error` with `X-Agent-ID`.
   - Terminates agent container cleanly via `os._exit(1)`.
2. **Control Plane Persistence (`agents_services.py`)**:
   - Updates `agents` table with `status = "error"`, `last_error`, `error_category`, and `last_error_at = func.now()`.
   - Broadcasts `AGENT_ERROR` via WebSocket manager.
3. **Watchdog Fallback (`check_stale_agents_and_jobs()`)**:
   - Detects abruptly killed containers (>60s missing heartbeat) and flags `error_category = "DISCONNECTED_UNEXPECTEDLY"` with descriptive diagnostics.
4. **UI Diagnostic Callout**:
   - `AgentStatusBanner.tsx` renders diagnostic callout box (`🚨 DOCKER AGENT STOPPING ERROR DETECTED`) with error category, timestamp, details, and remediation steps.
   - `DashboardPage` highlights agent card with error status and badge.
5. **Self-Healing Resolution**:
   - Upon container restart with valid parameters, `process_agent_heartbeat()` clears `last_error` and `error_category`, returning status to `online`.

### Phase F: Migration Plan Versioning & Historical Rollback Sequence
1. **Plan Refinement / Modification Trigger**:
   - In [`apps/web/components/plans/PlanBlueprintViewer.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanBlueprintViewer.tsx), user inputs refinement prompt or approves blueprint.
   - Dispatches `POST /api/v1/plans/{plan_id}/refine` or `POST /api/v1/plans/{plan_id}/approve`.
2. **Version Auto-Snapshotting**:
   - `MigrationPlanService.refine_plan()` or `approve_plan()` loads existing plan.
   - Atomically persists `MigrationPlanVersion(plan_id=plan.id, version_number=plan.current_version + 1, plan_data=new_plan_data, change_summary=summary)`.
   - Increments `plan.current_version += 1`.
3. **Version History Navigation**:
   - User navigates through version carousel in `PlanBlueprintViewer.tsx`.
   - Dispatches `GET /api/v1/plans/{plan_id}/versions` to list available snapshots.
   - User selects historical version -> `GET /api/v1/plans/{plan_id}/versions/{version_num}` retrieves exact past AST.
4. **Historical Version Activation**:
   - User clicks **"Activate This Version"** or executes historical plan.
   - Calls `POST /api/v1/plans/{plan_id}/versions/{version_num}/activate`.
   - `MigrationPlanService.rollback_to_version()` overwrites active `plan_data` on parent `MigrationPlan` with the snapshot and records a new rollback version.

### Phase G: Dynamic Agent Heartbeat Scaling, Idle Standby & Container Auto-Stop
1. **Active Heartbeat Cadence**:
   - While processing or recently active, `docker-agent` in [`apps/agent/main.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/main.py) sends `POST /api/v1/agents/heartbeat` every 20 seconds.
2. **Idle Detection**:
   - `AgentService.process_agent_heartbeat()` in [`apps/api/app/modules/agents/agents_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_services.py) checks `agent.idle_since`.
   - If `agent.idle_since` exceeds 300 seconds (5 minutes) and no jobs are queued or running, backend returns directive: `{"directive": "ENTER_IDLE_MODE", "message": "Agent idle for 300s — entering low-power standby mode."}`.
3. **Standby Mode Transition**:
   - Agent logs `[OPTION C] Heartbeat switched to STANDBY mode (5-min interval)`.
   - Throttles heartbeat frequency from 20s to 300s, conserving container CPU and network bandwidth.
4. **Wakeup on Job Assignment**:
   - When a user queues an execution job or interacts with the agent, backend directive returns `RESUME_ACTIVE_MODE`.
   - Agent immediately switches heartbeat back to 20-second cadence.
5. **Container Auto-Stop**:
   - When a migration completes and auto-stop is configured, backend returns `STOP_CONTAINER`.
   - Agent cleans up database connection pools and executes graceful container exit `os._exit(0)`.

### Phase H: Robust Multi-Source Merge Crash Recovery & Fail-Safe ETL Execution
1. **Startup Cleanup with Active Job Preservation**:
   - Agent [`ExecutionOrchestrator.run_job()`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/orchestrator.py) scans `CHECKPOINT_DIR` for `.duckdb` files.
   - Deletes stale staging files from OTHER completed/abandoned jobs, but deliberately **skips** `staging_{job_id}_*.duckdb` for the current active job ID.
2. **Leftover Staging Detection & Checkpoint Reset**:
   - If `staging_{job_id}_{target_table}.duckdb` exists when processing `target_table`, Orchestrator detects a previous crash mid-merge.
   - Calls `CheckpointManager.clear_table_checkpoints(job_id, target_table)` in [`checkpoint.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/checkpoint.py), removing stale per-source checkpoints so all sources re-stage from row 0.
   - Removes leftover DuckDB file and creates a fresh staging database, eliminating duplicate rows and missing data.
3. **Extraction Failure Guard**:
   - `SourceConnectorFactory.read_source_chunk()` in [`source_factory.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/connectors/source_factory.py) reads chunks via Keyset Pagination.
   - If network or DB permission fails mid-stream, catches error and raises `SourceReadError` instead of returning an empty DataFrame, failing the job cleanly.
4. **Fast Target Connectivity Pre-Check**:
   - `TargetWriterFactory.bulk_load()` in [`target_writer.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/writers/target_writer.py) executes `with engine.connect() as _test_conn:` before chunk iteration.
   - If target host/port/auth is unreachable, fast-fails in < 3s with `Target database connection failed for table '{table_name}'`.
5. **Write Failure Rate Verification**:
   - At completion check, if `total_failed / total_processed > 0.50`, aborts job with `RuntimeError` rather than silently declaring success.
6. **Thread-Safe Connection Disposal**:
   - In `run_job`'s `finally:` block, `dispose_all_engines()` from [`db.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/db.py) is called, closing and disposing all pooled SQLAlchemy engine connections.

## 3. Impact & Delta Analysis (AI Modifications)
- **[NEW]**: [`apps/api/alembic/versions/008_add_migration_plan_versions.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/alembic/versions/008_add_migration_plan_versions.py) - Added `migration_plan_versions` table for immutable plan history.
- **[NEW]**: [`apps/api/alembic/versions/009_add_idle_since_to_agents.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/alembic/versions/009_add_idle_since_to_agents.py) - Added `idle_since` column to `agents` table.
- **[NEW]**: [`apps/api/alembic/versions/010_add_error_fields_to_agents.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/alembic/versions/010_add_error_fields_to_agents.py) - Added `last_error`, `error_category`, and `last_error_at` columns.
- **[MODIFIED]**: [`apps/api/app/modules/migration_plans/migration_plans_models.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_models.py) - Added `MigrationPlanVersion` model and `current_version` field.
- **[MODIFIED]**: [`apps/api/app/modules/migration_plans/migration_plans_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_services.py) - Added plan version snapshotting, retrieval, and rollback logic.
- **[MODIFIED]**: [`apps/api/app/modules/migration_plans/migration_plans_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_routes.py) - Added endpoints for listing versions, viewing past versions, and activating historical plans.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_models.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_models.py) - Added mapped columns for `idle_since` and error tracking.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_services.py) - Added heartbeat scaling directives (`ENTER_IDLE_MODE`, `RESUME_ACTIVE_MODE`, `STOP_CONTAINER`), watchdog error tagging, and error clearing on reconnect.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_routes.py) - Added emergency endpoint `POST /api/v1/agents/fatal-error`.
- **[MODIFIED]**: [`apps/agent/main.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/main.py) - Added dynamic heartbeat standby throttling, container auto-stop handling, and `report_fatal_error_and_exit()`.
- **[MODIFIED]**: [`apps/agent/engine/orchestrator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/orchestrator.py) - Added source identifier validation, >50% failure rate abort check, active staging file preservation, leftover staging crash reset, and `dispose_all_engines()` in `finally:`.
- **[MODIFIED]**: [`apps/agent/engine/checkpoint.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/checkpoint.py) - Added `clear_table_checkpoints(job_id, table_name)` for clean per-table reset on resume.
- **[MODIFIED]**: [`apps/agent/engine/connectors/source_factory.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/connectors/source_factory.py) - Added `SourceReadError` exception and raised on source chunk read failure.
- **[MODIFIED]**: [`apps/agent/engine/ddl_executor.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/ddl_executor.py) - Removed blanket exception suppression in post-migration DDL to raise non-benign errors.
- **[MODIFIED]**: [`apps/agent/engine/writers/target_writer.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/writers/target_writer.py) - Added early `engine.connect()` connectivity check before row fallback loop.
- **[MODIFIED]**: [`apps/agent/engine/transformers/ast_transformer.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/transformers/ast_transformer.py) - Return `None` on empty/null values and passthrough raw string on parse failure (no current timestamp fabrication).
- **[MODIFIED]**: [`apps/agent/engine/db.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/db.py) - Added thread-safe `_ENGINE_CACHE` and `dispose_all_engines()`.
- **[MODIFIED]**: [`apps/web/components/plans/PlanBlueprintViewer.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanBlueprintViewer.tsx) - Added plan version carousel, history selector, and activation buttons.
- **[MODIFIED]**: [`apps/web/components/agents/AgentStatusBanner.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/agents/AgentStatusBanner.tsx) - Added stopping error diagnostic alert banner.
- **[MODIFIED]**: [`apps/web/app/dashboard/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/dashboard/page.tsx) - Added error badges and alert callouts on agent cards.
- **[MODIFIED]**: [`docs/DECISIONS.md`](file:///d:/GitHub/Ai_data_migration_platform/docs/DECISIONS.md) - Recorded decision entries for plan versioning, agent standby/auto-stop, and engine robustness.
- **[MODIFIED]**: [`docs/EXECUTION_FLOW.md`](file:///d:/GitHub/Ai_data_migration_platform/docs/EXECUTION_FLOW.md) - Mapped execution sequences for plan versioning, idle heartbeat lifecycle, and robust multi-source ETL recovery.


