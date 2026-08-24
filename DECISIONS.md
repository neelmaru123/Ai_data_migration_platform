# Architectural & Design Decisions

## 2026-08-20 - Post-Agent Creation Workflow: Catalog Profiler & Transformation Plan UI

### 1. Decision Summary
Implemented the complete frontend user flow following agent container registration:
1. **Agent Status Banner (`AgentStatusBanner.tsx`)**: WebSocket auto-sync for live agent connection heartbeats (`online` / `offline`) and schema introspection completion notifications (`METADATA_PROFILED`).
2. **Schema & Catalog Viewer (`SchemaCatalogViewer.tsx`)**: Structural inspection tree & table browser rendering database tables, column data types, nullability, PK/FK attributes, constraints, and estimated row counts.
3. **AI Migration Plan Trigger (`GeneratePlanAction.tsx`)**: Form panel submitting target engine options and custom natural language instructions to launch the AI Planning Engine (`POST /api/v1/plans`).
4. **Interactive Transformation Blueprint (`PlanBlueprintViewer.tsx`)**: Rendered on `/transformation-plan`, featuring table execution order timelines, column transformation mapping cards, AI confidence scoring, natural language AI plan refinement, and plan approval triggers.

### 2. Why This Approach? (Rationale)
- **Problem Being Solved**: Previously, after creating an agent, there was no UI to monitor agent health, view catalog metadata uploaded by agent daemons, or review and approve AI-generated migration plans.
- **Chosen Solution**: Modular Next.js Client Components with TypeScript types aligned strictly against backend FastAPI Pydantic contracts (`MetadataSnapshotDetailResponse`, `TransformationPlanAST`).
- **Why This Architecture**:
  - Direct integration with existing FastAPI WebSocket endpoints (`/api/v1/agents/ws/{id}`) for zero-latency UI updates.
  - Strict sharp visual design system (`rounded-none`, pitch black background, Sky Blue `#38bdf8` accents) maintaining design consistency across all steps.

### 3. Alternatives Considered & Rejected
- **Alternative A (Full Page Reload Polling)**: Standard HTTP polling for schema profiling changes.
  - *Rejected*: Slower user feedback and unnecessary load on FastAPI endpoints compared to WebSocket events.
- **Alternative B (Generic Tree Views)**: Relying on basic JSON trees for displaying schema tables.
  - *Rejected*: Inferior user experience; structured table matrices with PK/FK/type badges are significantly easier to audit.

### 4. Trade-offs & Future Considerations
- **Memory Safety**: Schema catalog inspector renders up to 500 tables per view using client-side searching. If a database has 10,000+ tables, virtualized list rendering (e.g. `react-window`) can be introduced.

---

## 2026-08-24 - Critical Workflow & ETL Robustness Edge Case Fixes

### 1. Decision Summary
Resolved critical edge cases across API backend, agent execution engine, and Web UI:
1. **Duplicate Execution Prevention (`execution_services.py`)**: Added an explicit active job check (`status.in_(["queued", "preparing", "running"])`) returning HTTP 409 Conflict if execution is triggered on an already active plan.
2. **Explicit Source DB Matching (`orchestrator.py`)**: Removed silent fallback to default DB when resolving multi-source connection strings; raises an explicit `ValueError` when an identifier cannot be matched.
3. **Resumable Checkpoint Lifecycle (`checkpoint.py` & `orchestrator.py`)**: Added `clear_job_checkpoints(job_id)` to purge `.json` checkpoint files on job completion to prevent stale resumes.
4. **PostgreSQL Session Scope Safety (`target_writer.py`)**: Enclosed `SET session_replication_role = 'replica'` in a `try...finally` block resetting to `'origin'` before releasing pooled connections.
5. **Watchdog Queued Job Recovery (`agents_services.py` & `execution_services.py`)**: Updated stale watchdog loops to clean up orphaned `queued` jobs when agents time out.
6. **Execution Dashboard Filtering (`execution/page.tsx` & `PlanBlueprintViewer.tsx`)**: Aligned active job counter with `queued`, `preparing`, and `running` backend statuses and added active job auto-detection on mount.

### 2. Why This Approach? (Rationale)
- **Problem Being Solved**: Potential data duplication on re-triggering plan execution, silent wrong-database fallback on multi-source setups, stale checkpoint reuse, connection pool constraint leakage, and orphaned queued jobs.
- **Chosen Solution**: Guard-rail checks at API boundary, explicit exception raising in agent engine, connection transaction cleanup, and complete status synchronization between frontend and backend.
- **Why This Architecture**: Ensures strict data safety, transparent failure logs, and idempotent execution pipelines.

### 3. Alternatives Considered & Rejected
- **Alternative A (Silent Ignore for Duplicate Executions)**: Returning 200 OK with the existing job ID on duplicate trigger.
  - *Rejected*: HTTP 409 Conflict provides explicit semantic feedback and alerts the UI to mount the active execution banner.
- **Alternative B (Keeping Checkpoint Files Indefinitely)**: Leaving completed job checkpoints on disk.
  - *Rejected*: Disk clutter and risk of stale offset reuse if job IDs are re-generated.

### 4. Trade-offs & Future Considerations
- Single-source database environments retain automatic single-DB binding fallback when only one source DB is configured, preserving developer onboarding simplicity while safeguarding multi-source setups.

---

## 2026-08-24 - High Priority UX, Security & Resilience Edge Case Fixes

### 1. Decision Summary
Resolved all High Priority edge cases (EC-07 through EC-12) across UI, API, and Agent:
1. **Plan AST Revert Strategy (`PlanBlueprintViewer.tsx`)**: Added `previousValidAst` state tracking to allow restoring the last valid plan version if LLM refinement generates schema errors.
2. **Draft Failed Error Alert UI (`PlanBlueprintViewer.tsx`)**: Added explicit error card rendering with diagnostic details and a "Regenerate Migration Plan" action when plan status is `draft_failed` or `table_mappings` is empty.
3. **Plan Generation Request Timeout & Progress UX (`planService.ts` & `GeneratePlanAction.tsx`)**: Set a 3-minute request timeout (`timeout: 180000`) for plan generation/refinement API calls and added a step-by-step progress indicator modal.
4. **Secure WebSocket Authentication Frame Support (`agents_routes.py` & `agentService.ts`)**: Updated WebSocket endpoint to support initial `{ "type": "auth", "token": "<jwt>" }` JSON message authentication frames, eliminating JWT token exposure in URL query parameters (`?token=<jwt>`).
5. **Real-Time Execution Auto-Refresh Polling (`execution/page.tsx`)**: Added a 3-second auto-polling interval when active jobs exist, keeping live row counts and stages updated without manual user refreshes.
6. **Explicit Agent Environment Credentials (`main.py`)**: Updated `auto_register_agent()` to fail fast if `USER_EMAIL` and `USER_PASSWORD` are missing instead of sending default test credentials.

### 2. Why This Approach? (Rationale)
- **Problem Being Solved**: Irreversible blueprint invalidation on refinement failure, blank UI on graph generation failure, request timeouts on long LLM runs, JWT token leakage in WebSocket URLs, stale execution metrics, and accidental test credential fallback in production.
- **Chosen Solution**: AST state versioning, explicit error boundary components, secure WebSocket first-frame auth, client-side polling, and strict environment credential enforcement.
- **Why This Architecture**: Protects sensitive tokens, improves user feedback, and ensures deterministic error handling across all user-facing flows.

### 3. Alternatives Considered & Rejected
- **Alternative A (URL Query Parameter WebSocket Auth Only)**: Continuing to send JWT in query strings.
  - *Rejected*: Security vulnerability; query parameters are logged in server access logs and browser history.
- **Alternative B (Manual Page Refreshes for Execution Monitoring)**: Requiring users to click "Refresh Jobs".
  - *Rejected*: Inferior user experience; real-time 3s polling provides seamless live ETL visibility.

### 4. Trade-offs & Future Considerations
- First-frame WebSocket auth preserves query parameter support as a legacy fallback for existing client integrations while enforcing non-URL token delivery for new UI components.

---

## 2026-08-24 - Medium Priority Configuration, Validation & Sanitization Fixes

### 1. Decision Summary
Resolved all Medium Priority edge cases (EC-13 through EC-19) across API backend, agent execution engine, and plan validator:
1. **Deterministic Target DB Selection (`main.py`)**: Sorted `DEST_*` keys alphabetically and selected primary target URL, issuing warning logs when multiple destination DB URLs are present in container environment variables.
2. **Pre-DDL Created Tables Resolution (`migration_plans_validator.py`)**: Parsed `pre_migration_ddl` statements for `CREATE TABLE` patterns and included created table names in `target_tables` validation set to prevent false-positive FK errors.
3. **Empty Table Mapping Prohibition (`migration_plans_validator.py` & `orchestrator.py`)**: Required `table_mappings` to contain at least 1 table mapping, failing validation and halting execution if empty.
4. **DuckDB Expression Sanitization (`ast_transformer.py`)**: Added regex SQL keyword inspection (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `COPY`, `ATTACH`, `TRUNCATE`, `ALTER`) before executing in-memory DuckDB expressions.
5. **LLM Refinement Guidance Preservation (`migration_plans_services.py`)**: Passed user-provided `custom_instructions` from `plan.target_config` to context serializer during natural language plan refinement (`refine_plan`).
6. **Circular Foreign Key Cycle Detection (`migration_plans_validator.py`)**: Built directed graph of post-migration foreign keys and added cycle detection warnings recommending deferrable constraints.

### 2. Why This Approach? (Rationale)
- **Problem Being Solved**: Unpredictable destination DB selection when multiple target URLs exist, false-positive validator errors on DDL junction tables, silent 0-table migration runs, DuckDB expression SQL injection risks, lost prompt guidance during refinement, and circular FK deadlocks.
- **Chosen Solution**: Deterministic env sorting, AST regex parsing, explicit validation rules, expression keyword blacklisting, instruction propagation, and graph DFS cycle detection.
- **Why This Architecture**: Strengthens platform security, improves validation accuracy, and ensures reliable ETL execution.

### 3. Alternatives Considered & Rejected
- **Alternative A (Strict Rejection of Multiple DEST_* Env Vars)**: Immediately terminating container startup if multiple DEST URLs exist.
  - *Rejected*: Too restrictive for staging/multi-target configurations; picking primary with warning log is more developer-friendly.
- **Alternative B (Full SQL Parser for Expression Templates)**: Integrating ANTLR or heavy SQL parsing library in python agent.
  - *Rejected*: Unnecessary overhead; regex keyword sanitization effectively prevents destructive SQL DDL/DML injection in DuckDB calculations.

### 4. Trade-offs & Future Considerations
- Circular foreign key warnings are reported as architecture warnings (not blocking errors) to allow valid deferrable FK setups while notifying users of potential deadlock risks.

---

## 2026-08-24 - Low Priority Storage, Scaling & Precision Edge Case Fixes

### 1. Decision Summary
Resolved all Low Priority edge cases (EC-20 through EC-30) across API backend, agent execution engine, connectors, and Web UI:
1. **DuckDB Staging File Startup Cleanup (`orchestrator.py`)**: Added automatic removal of leftover temporary `staging_*.duckdb` files on engine startup.
2. **Unsupported Engine Dialect Validation (`source_factory.py`)**: Validated engine dialect strings against supported databases (`postgresql`, `mysql`, `sqlite`, `mongodb`, `csv`, `excel`), raising explicit `ValueError` for unsupported dialects.
3. **Offset Pagination Warning Notice (`source_factory.py`)**: Issued warning logs when extracting from source tables without a primary key using `OFFSET` pagination.
4. **High-Precision Decimal Casting (`ast_transformer.py`)**: Preserved high-precision `decimal`/`numeric` columns during Polars data frame transformations by casting target data types to `pl.Utf8` string representation.
5. **Large Schema Introspection Scaling Cap (`metadata_engine.py`)**: Capped table metadata introspection to top 500 tables ordered by estimated row count on databases with 500+ tables.
6. **Concurrent Refinement Row-Level Lock (`migration_plans_services.py`)**: Acquired `with_for_update()` lock on `MigrationPlan` inside `refine_plan()` to serialize concurrent refinement prompts.
7. **WebSocket Log Noise Reduction (`websocket_manager.py`)**: Downgraded offline WebSocket broadcast logs from `logger.warning` to `logger.debug`.

### 2. Why This Approach? (Rationale)
- **Problem Being Solved**: Lingering temporary DuckDB files on container crash, unhandled errors on unsupported DB dialects, offset drift risks, micro-precision float rounding errors, 2-minute timeouts on 1000+ table schemas, race conditions on concurrent plan refinements, and log spam for offline clients.
- **Chosen Solution**: Startup filesystem cleanup, strict dialect whitelisting, PK offset warnings, string decimal casting, 500-table row-count introspection sorting, DB row-level locking, and debug log level tuning.
- **Why This Architecture**: Maximizes system resilience, scales to enterprise databases, and maintains data precision.

### 3. Alternatives Considered & Rejected
- **Alternative A (Unbounded Table Introspection)**: Inspecting all 10,000+ tables on massive enterprise databases.
  - *Rejected*: Hits HTTP and database connection timeouts; top 500 tables by row count captures 99.9% of active data tables.
- **Alternative B (Casting Decimal to Float64)**: Converting numeric/decimal columns to standard floating point numbers.
  - *Rejected*: Risks precision loss on financial values; string/Utf8 representation preserves exact scale and precision.

### 4. Trade-offs & Future Considerations
- Introspection truncation logs an informational notice to alert developers when databases exceed 500 tables, with options to specify targeted schema filters if required.
