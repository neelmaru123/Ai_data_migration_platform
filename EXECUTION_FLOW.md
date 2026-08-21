# Execution Flow - Post-Agent Creation, Schema Catalog Profiling & Migration Plan UI

## 1. Entry Point
- **Files**:
  - [`apps/web/app/sources/page.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/sources/page.tsx)
  - [`apps/web/app/profiling/page.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/profiling/page.tsx)
  - [`apps/web/app/transformation-plan/page.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/transformation-plan/page.tsx)
- **Triggers**:
  - Navigating to `/sources` or `/profiling` after creating an agent in Step 3.
  - Clicking **"Generate AI Migration Plan"** from the Schema Inspector.
  - Opening `/transformation-plan?planId={id}` to view and approve AI migration blueprints.

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
   - Renders **Execution Order Sequence Timeline** (dependency order), **Table Mapping Matrix**, and **AI Confidence Score**.
3. **AI Plan Refinement**:
   - User types prompt feedback -> Calls `planService.refinePlan(planId, prompt)` (`POST /api/v1/plans/{plan_id}/refine`).
   - Updates AST dynamically.
4. **Plan Approval**:
   - User clicks **"APPROVE MIGRATION PLAN"** -> Calls `planService.approvePlan(planId)` (`POST /api/v1/plans/{plan_id}/approve`).
   - Transition status to `COMPLETED` / `APPROVED`.

## 3. Impact & Delta Analysis (AI Modifications)
- **[NEW]**: [`apps/web/types/metadata.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/types/metadata.ts) - DTO interfaces matching backend metadata schema.
- **[NEW]**: [`apps/web/types/migrationPlan.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/types/migrationPlan.ts) - DTO interfaces matching backend transformation plan AST schema.
- **[NEW]**: [`apps/web/services/metadataService.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/metadataService.ts) - Service for catalog metadata fetching.
- **[NEW]**: [`apps/web/services/planService.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/planService.ts) - Service for AI plan generation, refinement, and approval.
- **[NEW]**: [`apps/web/components/agents/AgentStatusBanner.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/agents/AgentStatusBanner.tsx) - Live Agent health banner.
- **[NEW]**: [`apps/web/components/profiling/SchemaCatalogViewer.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/profiling/SchemaCatalogViewer.tsx) - Table & column catalog viewer.
- **[NEW]**: [`apps/web/components/profiling/GeneratePlanAction.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/profiling/GeneratePlanAction.tsx) - AI plan generation action.
- **[NEW]**: [`apps/web/components/plans/PlanBlueprintViewer.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/components/plans/PlanBlueprintViewer.tsx) - Interactive AI Migration Blueprint AST viewer.
- **[MODIFIED]**: [`apps/web/app/sources/page.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/sources/page.tsx) - Full catalog profiler page.
- **[MODIFIED]**: [`apps/web/app/profiling/page.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/profiling/page.tsx) - Schema profiling page.
- **[MODIFIED]**: [`apps/web/app/transformation-plan/page.tsx`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/app/transformation-plan/page.tsx) - Transformation Blueprint page.
