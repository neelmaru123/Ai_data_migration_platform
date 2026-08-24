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
