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
