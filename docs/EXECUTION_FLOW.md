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
3. **AI Plan Refinement & Feasibility Feedback Loop**:
   - User enters natural language prompt (e.g. *"Can we do that same conversion without data loss in 12 tables?"*) in `PlanBlueprintViewer`.
   - Submits `planService.refinePlan(planId, prompt)` (`POST /api/v1/plans/{plan_id}/refine`).
   - `MigrationPlanService.refine_plan()` locks plan row with `with_for_update()` and delegates to `llm_plan_generator.refine()`.
   - LLM evaluates feasibility against source schemas and zero-data-loss rules.
   - If infeasible or rejected (e.g., merging incompatible tables):
     - LLM sets `refinement_feedback.applied = false`, `verdict = 'infeasible_rejected'`, and provides detailed technical explanation.
     - Preserves the safe 14 tables in `table_mappings` to prevent data loss.
   - If feasible:
     - Applies changes, sets `refinement_feedback.applied = true`, and describes modifications.
   - `MigrationPlanService` records a new `MigrationPlanVersion` capturing `refinement_feedback` and returns updated `PlanDetailResponse`.
   - `PlanBlueprintViewer` renders `RefinementFeedbackCard` displaying prompt echo, status badge (`[NOT FEASIBLE — PROTECTED FROM DATA LOSS]`), table deltas (`14 → 14 Preserved`), and complete AI explanation.
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

### Phase I: Deterministic Fallback UUID Generation for Safe Migration Retries
1. **Compound Seed Construction**:
   - In [`ExecutionOrchestrator.run_job()`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/orchestrator.py), before invoking the transformer, constructs `retry_seed_prefix = f"{job_id}:{target_table}:{src_ident}:{src_table}"`.
   - Passes `retry_seed_prefix` alongside `row_offset=offset` into `ASTTransformer.transform_chunk()`.
2. **Stable Fallback UUID Generation**:
   - When a row lacks a natural key or uses `uuid_v4_rekey`, or when unresolvable PK columns / missing `'id'` fields occur, `_deterministic_fallback_uuid(retry_seed_prefix, row_offset + i)` produces `str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{seed_prefix}:{row_index}"))`.
   - Re-running or retrying the exact same migration job produces identical UUIDs for the same source row position, making retries idempotent against target `ON CONFLICT DO NOTHING` / `INSERT IGNORE` tables.

### Phase J: Preflight Target Table Existing Data Advisory
1. **Target Table Inspection via Offline Snapshot**:
   - In [`ExecutionService.create_execution_job()`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_services.py), before queuing execution, calls `check_target_tables_existing_data()`.
   - Locates target `DataSource` (`role in ("target", "both")`) for the agent and retrieves its latest `MetadataSnapshot` without making a live external network request from the API.
   - For any table where `table.table_name` matches a target plan table and `table.row_count > 0`, adds an entry to `target_tables_with_existing_data`.
2. **Non-Blocking Advisory Response**:
   - Job creation continues without interruption (`status="queued"`).
   - Warnings are attached to the `MigrationJob` instance and returned in `ExecutionJobResponse` as `target_tables_with_existing_data: list[dict]`, allowing frontend clients to show informative alerts.

### Phase K: Multi-Vector Migration Readiness Signals & Granular Confidence
1. **Hierarchical Metric Derivation**:
   - In [`computePlanReadiness()`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanReadinessSignals.tsx), traverses `TransformationPlanAST.table_mappings` and `column_mappings`.
   - Computes four distinct readiness scores (0-100%): **Schema Compatibility**, **Type Compatibility**, **Relationship Mapping**, and **Data Conflict Risk**.
   - Weighs vectors into a composite `rollupScore` with classification labels (`OPTIMAL READINESS`, `HIGH READINESS`, `MODERATE READINESS`, `REVIEW ADVISED`).
2. **Fine-Grained Table and Column Confidence**:
   - [`computeTableReadiness()`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanReadinessSignals.tsx) aggregates column distributions into table-level readiness indicators for accordion headers.
   - [`computeColumnConfidence()`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanReadinessSignals.tsx) scores each individual column based on its specific transformation type (`direct_copy`: 99%, `uuid_cast`: 98%, `type_cast`: 93-96%, `expression`: 88%, `drop_column`: 80%).
3. **Execution Advisory Warning**:
   - When `create_execution_job` returns `target_tables_with_existing_data`, [`JobExecutionBanner.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/JobExecutionBanner.tsx) renders an advisory warning detailing pre-populated tables and row counts.

### Phase L: Dry Run Migration Simulation Engine (End-to-End Safe Trial)
1. **Triggering Simulation**:
   - User clicks `"⚡ Run Dry Run (Simulation)"` in [`PlanBlueprintViewer.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanBlueprintViewer.tsx).
   - Frontend calls `startPlanExecution(planId, { is_dry_run: true })` hitting `POST /api/v1/plans/{id}/execute` with `{ is_dry_run: true }`.
2. **Backend Dispatch**:
   - [`ExecutionService.create_execution_job()`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_services.py) creates a `MigrationJob` with `is_dry_run=True`, persisted in PostgreSQL/SQLite.
   - Agent daemon polls `GET /api/v1/agents/tasks` receiving `AgentTaskItemResponse` with `is_dry_run=True`.
3. **Agent Orchestrator Simulation**:
   - [`apps/agent/main.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/main.py) passes `is_dry_run` to [`ExecutionOrchestrator.run_job()`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/orchestrator.py).
   - **Pre-DDL & Post-DDL**: Completely bypassed. Target schema remains untouched.
   - **Extraction & Transformation**: Full source data streaming (`SourceConnectorFactory.read_source_chunk`) and AST transformation (`ASTTransformer.transform_chunk`) execute normally to test real-world data quality and type casting fidelity.
   - **Multi-Source Merge & Deduplication**: DuckDB staging runs to detect real primary key merge conflicts without writing to target.
   - **Target DB Write**: `TargetWriterFactory.bulk_load()` is bypassed. Would-be written rows are counted (`len(df_trans)`).
   - **Checkpoints**: Preserved without calling `CheckpointManager.clear_job_checkpoints(job_id)`.
   - **Terminal Status**: Reported as `"dry_run_completed"`.
4. **Frontend Results & Direct Re-execution**:
   - [`JobExecutionBanner.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/JobExecutionBanner.tsx) displays an amber simulation warning (`"DRY RUN SIMULATION -- NO DATA WAS WRITTEN TO TARGET DB"`).
   - Shows full statistics of simulated rows that would have succeeded or failed.
   - Renders a secondary `"⚡ EXECUTE FOR REAL"` button allowing one-click transition to live execution.

### Phase M: Execution Monitor Checkpoint Resume vs Retry & Completed Guard
1. **Failed Job State Evaluation**:
   - When `job.status === 'failed'` and `(job.processed_rows || 0) > 0`, [`JobExecutionBanner.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/JobExecutionBanner.tsx) computes `canResume = true`.
   - The action button dynamically labels as `"⚡ RESUME"` (or `"⚡ RESUME DRY RUN"`), with a tooltip confirming: *"Checkpoints will be reused: resumes execution from {processed_rows} processed rows."*
   - When `job.status === 'failed'` and `job.processed_rows === 0`, it displays `"⚡ RETRY MIGRATION JOB"`.
2. **Completed Migration Action Guard**:
   - When `job.status === 'completed'`, retry execution is disabled:
     - Renders `+ CREATE NEW MIGRATION` button (linking directly to [`/profiling`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/profiling/page.tsx)).
     - Renders disabled retry button with tooltip: *"Checkpoints will be reused when the job is completed. Create a new migration instead."*
3. **Page-Level Navigation**:
   - [`apps/web/app/execution/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/execution/page.tsx) header includes a direct `+ Create New Migration` button alongside `Refresh Jobs`.

## 3. Impact & Delta Analysis (AI Modifications)
- **[NEW]**: [`apps/api/alembic/versions/011_add_is_dry_run_to_migration_jobs.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/alembic/versions/011_add_is_dry_run_to_migration_jobs.py) - Alembic migration adding `is_dry_run` to `migration_jobs`.
- **[NEW]**: [`apps/api/tests/unit/test_execution_dry_run.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_execution_dry_run.py) - Unit tests for dry run job creation, agent task polling, and orchestrator simulation execution.
- **[NEW]**: [`apps/web/components/plans/PlanReadinessSignals.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanReadinessSignals.tsx) - 4-vector readiness calculation, Rollup badge, `TableReadinessBadge`, and `ColumnConfidenceBadge`.
- **[NEW]**: [`apps/api/tests/unit/test_bug_deterministic_retry_uuids.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_deterministic_retry_uuids.py) - Unit test suite for deterministic retry UUID generation.
- **[NEW]**: [`apps/api/tests/unit/test_execution_target_existing_data_check.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_execution_target_existing_data_check.py) - Unit test suite for preflight target tables existing data advisory check.
- **[MODIFIED]**: [`apps/api/app/modules/execution/execution_models.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_models.py) - Added `is_dry_run` column to `MigrationJob`.
- **[MODIFIED]**: [`apps/api/app/modules/execution/execution_schemas.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_schemas.py) - Added `is_dry_run` to `ExecutionStartRequest`, `ExecutionJobResponse`, and `AgentTaskItemResponse`.
- **[MODIFIED]**: [`apps/api/app/modules/execution/execution_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_routes.py) - Passes `is_dry_run` from start request to service and returns in agent task polling.
- **[MODIFIED]**: [`apps/api/app/modules/execution/execution_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_services.py) - Handles `is_dry_run` in `create_execution_job` and `"dry_run_completed"` in `update_job_progress`.
- **[MODIFIED]**: [`apps/agent/main.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/main.py) - Extracts `is_dry_run` from polled task payload and forwards to `run_job`.
- **[MODIFIED]**: [`apps/agent/engine/orchestrator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/orchestrator.py) - Implemented dry-run execution branch (skips DDL, runs AST transforms, skips target bulk load, preserves checkpoints, reports `dry_run_completed`).
- **[MODIFIED]**: [`apps/web/types/execution.ts`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/types/execution.ts) - Added `is_dry_run?: boolean` to `ExecutionJobResponse`.
- **[MODIFIED]**: [`apps/web/services/executionService.ts`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/services/executionService.ts) - Added `is_dry_run` option to `startPlanExecution()`.
- **[MODIFIED]**: [`apps/web/components/plans/PlanBlueprintViewer.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/PlanBlueprintViewer.tsx) - Added `handleDryRun()` handler and `"⚡ Run Dry Run (Simulation)"` action button.
- **[MODIFIED]**: [`apps/web/components/plans/JobExecutionBanner.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/plans/JobExecutionBanner.tsx) - Added simulation status formatting, prominent dry run banner, `canResume` check for "Resume" vs "Retry", tooltip for checkpoint reuse, disabled retry for completed jobs, and `+ CREATE NEW MIGRATION` button.
- **[MODIFIED]**: [`apps/web/app/execution/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/execution/page.tsx) - Added `+ Create New Migration` action in header.
- **[MODIFIED]**: [`docs/DECISIONS.md`](file:///d:/GitHub/Ai_data_migration_platform/docs/DECISIONS.md) - Recorded architectural decision entries for Phases L, M, and N.
- **[MODIFIED]**: [`docs/EXECUTION_FLOW.md`](file:///d:/GitHub/Ai_data_migration_platform/docs/EXECUTION_FLOW.md) - Documented Phase L, Phase M, and Phase N execution sequences and impact analysis.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_command_generator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_command_generator.py) - Generated generic `<HOST>`, `<PORT>`, `<USER>`, `<PASSWORD>`, `<NAME>` placeholders in `_get_db_url_template`.
- **[MODIFIED]**: [`apps/api/tests/unit/test_agent_command_generator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_agent_command_generator.py) - Updated assertions for generic connection placeholders.
- **[MODIFIED]**: [`apps/web/components/agents/DockerCommandOutput.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/agents/DockerCommandOutput.tsx) - Updated deployment guidance for generic connection placeholders.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_routes.py) - Added `POST /{agent_id}/regenerate-token` route.
- **[MODIFIED]**: [`apps/api/app/modules/agents/agents_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_services.py) - Added `AgentService.regenerate_agent_token`.
- **[MODIFIED]**: [`apps/web/services/agentService.ts`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/services/agentService.ts) - Added `agentService.regenerateAgentToken`.
- **[MODIFIED]**: [`apps/web/app/dashboard/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/dashboard/page.tsx) - Added first-time architecture/privacy explainer, redesigned command modal with live parameter re-entry and token regeneration flow.
- **[MODIFIED]**: [`apps/web/components/agents/DatabaseConfigForm.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/agents/DatabaseConfigForm.tsx) - Focused Phase 1 connector choices on PostgreSQL, MySQL, and MongoDB; removed CSV and Excel options.
- **[MODIFIED]**: [`apps/web/components/landing/FeaturesGrid.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/landing/FeaturesGrid.tsx) - Updated supported connectors copy and badge pills.
- **[MODIFIED]**: [`apps/web/components/profiling/SchemaCatalogViewer.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/profiling/SchemaCatalogViewer.tsx) - Added Relationships tab, in-memory table/column label resolution, and ArrowRight indicator.

---

# Execution Flow - Generic Zero-Credential Agent Command Generation (Phase N)

## 1. Entry Point
- **API Entrypoint**: `POST /api/v1/agents` or `GET /api/v1/agents/{agent_id}/docker-command` handled in [`agents_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_routes.py).
- **Service Invocation**: `AgentCommandGenerator.generate_command_payload(agent, data_sources, raw_token)` in [`agents_command_generator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_command_generator.py).

## 2. Step-by-Step Execution Sequence
1. **Placeholder Resolution**: For each linked source/target data source, `_get_db_url_template(db_type, prefix, clean_id)` constructs the connection URL template.
2. **Dialect Format Assembly**:
   - `postgresql`: `postgresql://<{prefix}_{clean_id}_USER>:<{prefix}_{clean_id}_PASSWORD>@<{prefix}_{clean_id}_HOST>:<{prefix}_{clean_id}_PORT>/<{prefix}_{clean_id}_NAME>`
   - `mysql`: `mysql+pymysql://<{prefix}_{clean_id}_USER>:<{prefix}_{clean_id}_PASSWORD>@<{prefix}_{clean_id}_HOST>:<{prefix}_{clean_id}_PORT>/<{prefix}_{clean_id}_NAME>`
   - `mongodb`: `mongodb://<{prefix}_{clean_id}_USER>:<{prefix}_{clean_id}_PASSWORD>@<{prefix}_{clean_id}_HOST>:<{prefix}_{clean_id}_PORT>/<{prefix}_{clean_id}_NAME>?authSource=admin`
   - `mssql`: `mssql+pyodbc://<{prefix}_{clean_id}_USER>:<{prefix}_{clean_id}_PASSWORD>@<{prefix}_{clean_id}_HOST>:<{prefix}_{clean_id}_PORT>/<{prefix}_{clean_id}_NAME>?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes`
3. **Command Payload Construction**: Constructs Bash multi-line, PowerShell, single-line, and `.env` formats embedding the generic URL templates.
4. **Client-Side Presentation & Local Substitution**:
   - User inputs host, port, username, database name, and SSL preference into [`DatabaseConfigForm.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/agents/DatabaseConfigForm.tsx) on Step 2.
   - Credentials are held strictly in browser state in [`apps/web/app/agents/create/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/agents/create/page.tsx) (`connectionDetailsByIdentifier`) and never sent over the network to the backend API.
   - When transitioning to Step 3, [`DockerCommandOutput.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/agents/DockerCommandOutput.tsx) calls `substituteConnectionPlaceholders()` to replace `<PREFIX_HOST>`, `<PREFIX_PORT>`, `<PREFIX_USER>`, and `<PREFIX_NAME>` with the user's typed values directly in browser memory.
   - Only `<PREFIX_PASSWORD>` remains as an explicit manual placeholder for the user to paste their password in their terminal.

---

# Execution Flow - Agent API Token Regeneration

## 1. Entry Point
- **API Endpoint**: `POST /api/v1/agents/{agent_id}/regenerate-token` in [`apps/api/app/modules/agents/agents_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_routes.py).
- **Service Handler**: `AgentService.regenerate_agent_token()` in [`apps/api/app/modules/agents/agents_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/agents/agents_services.py).
- **Security Check**: `Depends(get_verified_agent)` asserts ownership and loads linked `data_sources`.

## 2. Step-by-Step Execution Sequence
1. **Request Authorization**: `get_verified_agent` extracts `agent_id`, queries the agent from the database, and validates `agent.user_id == current_user.id` (raises `403 Forbidden` on mismatch, `404 Not Found` if missing).
2. **Token Generation & One-Way Hashing**:
   - Generates cryptographically secure token string `raw_token = f"ag_live_{secrets.token_urlsafe(32)}"`.
   - Computes SHA-256 hex digest: `token_hash = hash_agent_token(raw_token)`.
3. **Atomic Hash Mutation**:
   - Replaces `agent.api_token_hash = token_hash`.
   - Executes `session.add(agent)` and `await session.commit()`.
   - Any active container using the previous token immediately fails authentication on its next heartbeat or task poll (`401 Unauthorized`).
4. **Command Rebuilding**:
   - Reloads the agent entity with eagerly loaded `data_sources`.
   - Invokes `AgentCommandGenerator.generate_command_payload(agent, agent.data_sources, raw_token=raw_token)` to construct fresh Bash, PowerShell, single-line, and `.env` commands embedding the newly minted token.
5. **Single-Exposure Response**:
   - Constructs and returns `AgentDetailResponse` containing `api_token = raw_token`.
   - Once sent, `raw_token` is garbage-collected from backend memory and cannot be recovered again.

---

# Execution Flow - Schema Catalog Foreign-Key Relationship Resolution

## 1. Entry Point
- **Component**: [`SchemaCatalogViewer.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/profiling/SchemaCatalogViewer.tsx) loaded on the Schema Profiling page (`/profiling`).
- **Trigger**: User selects a table in the left navigation sidebar and clicks the **Relationships** tab.

## 2. Step-by-Step Execution Sequence
1. **Metadata Ingestion**: The component receives `MetadataSnapshotDetailResponse` containing `snapshot.schemas` (tables and columns) and `snapshot.relationships` (foreign-key edges).
2. **In-Memory Table Flattening**:
   ```typescript
   const allTables: { schemaName: string; table: TableResponse }[] = [];
   snapshot.schemas.forEach((schema) => {
     schema.tables.forEach((tbl) => {
       allTables.push({ schemaName: schema.schema_name, table: tbl });
     });
   });
   ```
3. **Local Name Resolution (`resolveColumnLabel`)**:
   - Accepts `(tableId: string, columnId: string)`.
   - Scans `allTables` in memory to find the table with `table.id === tableId`.
   - Looks up the column with `column.id === columnId`.
   - Returns `${table.table_name}.${column.column_name}` (or fallback `?` / `(unknown table)`).
   - Operates with **zero network latency and zero additional API requests**.
4. **Contextual Relationship Filtering**:
   - Filters `snapshot.relationships` to only include records where `r.source_table_id === selectedTable.id || r.target_table_id === selectedTable.id`.
   - Computes badge counter: `Relationships ({count})`.
5. **UI Presentation**:
   - If `count === 0`: Renders clean empty state ("No foreign-key relationships detected for this table.").
   - If `count > 0`: Renders relationship cards showing `{source_table.column} -> {target_table.column}`, relationship type badge, and confidence percentage.

---

# Execution Flow - Dashboard Session Logout & Identity Context

## 1. Entry Point
- **Component**: [`apps/web/app/dashboard/page.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/app/dashboard/page.tsx)
- **Trigger**: User clicks the **"LOGOUT"** button in the dashboard top header actions cluster.

## 2. Step-by-Step Execution Sequence
1. **User Identity Ingestion**:
   - `useAuthUser()` issues query `GET /api/v1/users/me` on initial render.
   - Syncs active user profile into Redux store (`setUser(data)`).
   - Renders active user context chip: `USER: <name/email>` with pulsing status dot.
2. **User Logout Dispatch**:
   - User clicks **`LOGOUT`**.
   - `DashboardPage.handleLogout()` sets `isLoggingOut = true` (disabling the button and updating button label to `'Logging out...'`).
   - Calls `logoutMutation.mutateAsync()`.
3. **Backend Session Termination**:
   - `useLogout()` dispatches `POST /api/v1/auth/logout` via `authService.logout()`.
   - Backend `logout_user()` executes `_clear_auth_cookies(response)`, expiring HTTP-only `access_token` and `refresh_token` cookies.
4. **Client State Purge**:
   - `useLogout()` removes client cookies `Cookies.remove('logged_in', { path: '/' })` and `Cookies.remove('active_org_id', { path: '/' })`.
   - Dispatches `logoutAction()` to Redux `authSlice` to reset `user = null` and `isAuthenticated = false`.
   - Clears TanStack Query cache via `queryClient.clear()`.
   - Displays toast notification (`Logged out successfully`).
5. **Hard Navigation**:
   - In `finally` block of `handleLogout()`, executes `window.location.href = '/login'`.
   - Browser reloads and navigates to `/login`.
   - Next.js middleware detects absence of auth cookies and blocks protected route access.

---

# Execution Flow - Relational to MongoDB Migration with Synchronized UUIDv5 Foreign Keys & BSON Types

## 1. Entry Point
- **UI Trigger**: User configures and triggers migration plan from [`apps/web/components/profiling/GeneratePlanAction.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/profiling/GeneratePlanAction.tsx) with target engine `mongodb`.
- **API Endpoint**: `POST /api/v1/plans/generate` in [`apps/api/app/modules/migration_plans/migration_plans_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_routes.py).
- **Execution Endpoint**: `POST /api/v1/plans/{plan_id}/execute` in [`apps/api/app/modules/execution/execution_routes.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_routes.py).
- **Agent Consumer**: Docker Agent task polling daemon (`poll_and_execute_tasks()`) in [`apps/agent/main.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/main.py).

## 2. Step-by-Step Execution Sequence

### Phase 1: Target Engine Auto-Detection & Prompt Formulation
1. **Frontend Auto-Detection**:
   - `GeneratePlanAction` fetches agent details via `agentService.getAgent(agentId)`.
   - Finds attached data source where `role in ('target', 'both')`. If type is `mongodb`, sets `targetType = 'mongodb'`.
2. **Backend Service Normalization**:
   - `MigrationPlanService.create_plan_for_agent()` in [`migration_plans_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_services.py) verifies target engine. If unset or default `postgresql`, auto-detects from agent's target data source (`mongodb`).
   - Ignores target-only data sources when collecting source metadata snapshots to eliminate false warning noise.
3. **LLM Blueprint Generation**:
   - `llm_plan_generator.generate()` invokes Gemini with MongoDB-specific guidance (Rule 18: schemaless collections, empty DDL, target primary key `_id` or `id`).
   - Rule 6: Whenever a parent primary key is re-keyed to `uuid`, referencing foreign keys must also be defined with `target_data_type: 'uuid'` and `transformation_type: 'type_cast'`.

### Phase 2: Deterministic FK Type Synchronization & Plan Validation
1. **Plan Validation Entry**:
   - `validate_feasibility_node()` in [`migration_plans_graph.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_engine/migration_plans_graph.py) calls `MigrationPlanValidator.validate()`.
2. **Primary Key Indexing**:
   - `MigrationPlanValidator` inspects all table mappings and indexes primary key types (`pk_type_by_table[table_name] = type`).
3. **Foreign Key Alignment**:
   - For every column ending in `_id` referencing a parent entity, if the parent's PK is `uuid`, the validator auto-synchronizes the foreign key column to:
     - `target_data_type: 'uuid'`
     - `transformation_type: 'type_cast'`
     - `ui_badge_type: 'type_cast'`
   - Updates `plan_ast_data` dictionary in-place so all persisted plans reflect this synchronized schema.

### Phase 3: Docker Agent Streaming Execution
1. **Data Extraction**:
   - `SourceConnectorFactory.read_source_chunk()` reads PostgreSQL rows in cursor batches (e.g. 1,000 rows).
2. **In-Memory Transformation ([`ast_transformer.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/transformers/ast_transformer.py))**:
   - For parent table (`categories`): Transforms `category_id: 100` $\to$ `id: uuid5(NAMESPACE_DNS, "src_db_1_100")` (`5cc524b1-...`).
   - For child tables (`products`, `orders`, `order_items`): Transforms `category_id: 100` $\to$ `category_id: uuid5(NAMESPACE_DNS, "src_db_1_100")` (`5cc524b1-...`).
   - Nullable foreign keys: Evaluates `None` as `None` (preserving relational nullability).
3. **BSON Type Sanitization & Promotion ([`target_writer.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/writers/target_writer.py))**:
   - `_sanitize_rows_for_target(rows, engine_type='mongodb')`:
     - Promotes `clean_row["_id"] = clean_row.pop("id")` so each document has only ONE `_id` primary key and no separate `id` field.
     - Decimal values $\to$ `bson.Decimal128(str(val))`.
     - Datetime / ISO strings $\to$ native `datetime.datetime` (`ISODate`).
4. **Target Sink**:
   - `MongoTargetWriter.bulk_load()` executes `collection.bulk_write([InsertOne(doc) for doc in chunk])` into MongoDB.

## 3. Impact & Delta Analysis (AI Modifications)
- **[MODIFIED]**: [`apps/agent/engine/transformers/ast_transformer.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/transformers/ast_transformer.py)
  - Added deterministic UUIDv5 transformation for columns with `target_data_type == 'uuid'` or `is_foreign_key_to_uuid` in both `direct_copy` and `type_cast`.
  - Added null preservation for nullable foreign keys.
- **[MODIFIED]**: [`apps/agent/engine/writers/target_writer.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/engine/writers/target_writer.py)
  - Promotes `id` to `_id` and drops `id` for MongoDB targets.
  - Converts Decimals to `bson.Decimal128`.
  - Preserves datetimes and converts ISO strings to native `datetime` (BSON ISODate).
- **[MODIFIED]**: [`apps/api/app/modules/migration_plans/migration_plans_engine/migration_plans_validator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_engine/migration_plans_validator.py)
  - Added PK indexing and automatic FK $\to$ UUID type synchronization.
  - Syncs AST mutations back into caller dictionary.
- **[MODIFIED]**: [`apps/api/app/modules/migration_plans/migration_plans_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_services.py)
  - Auto-detects target engine from agent data sources when default `postgresql`.
  - Skips `role == 'target'` when introspecting source databases.
- **[MODIFIED]**: [`apps/web/components/profiling/GeneratePlanAction.tsx`](file:///d:/GitHub/Ai_data_migration_platform/apps/web/components/profiling/GeneratePlanAction.tsx)
  - Auto-detects target engine from agent data sources on load.
  - Added Target Database Engine dropdown selector.
- **[NEW]**: [`apps/api/tests/unit/test_mongo_relational_uuid_fk_and_types.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_mongo_relational_uuid_fk_and_types.py)
  - Unit tests verifying UUID matching across PK/FK, BSON serialization (`Decimal128`, `ISODate`, `_id`), and validator synchronization.
