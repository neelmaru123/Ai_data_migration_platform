# Frontend Web Application (`apps/web`)

The `apps/web` package is the user-facing web dashboard for the **AI Data Migration Platform**. Built with Next.js 14 App Router, TypeScript, Tailwind CSS, TanStack Query v5, Redux Toolkit, and Axios, it provides real-time schema catalog browsing, AI transformation plan editing, interactive blueprint versioning, and live ETL migration execution monitoring.

---

## 1. Application Routes & Workflows

| Route Path | Page Component | Description |
| :--- | :--- | :--- |
| `/login` | `app/login/page.tsx` | 2-column split login page with 3D Spline scene, form validation, and Google OAuth 2.0 |
| `/register` | `app/register/page.tsx` | 2-column split registration page with password length enforcement and terms consent |
| `/dashboard` | `app/dashboard/page.tsx` | Platform overview, connected agents list, active sources metrics, and recent execution history |
| `/agents/create` | `app/agents/create/page.tsx` | 3-step wizard selecting migration ratio (`1:1`, `2:1`, `3:1`, `N:1`), database engines, and ready-to-run Docker CLI commands |
| `/sources` | `app/sources/page.tsx` | Agent status banner with live WebSocket connection monitoring and data source inventory |
| `/profiling` | `app/profiling/page.tsx` | Searchable schema catalog inspector rendering database tables, column types, PK/FK attributes, constraints, and AI plan trigger modal |
| `/transformation-plan` | `app/transformation-plan/page.tsx` | Interactive blueprint viewer rendering execution order sequence timelines, column transformation mapping cards, previous AST revert strategy, draft_failed error alert card, AI prompt refinement, and approval gateway |
| `/execution` | `app/execution/page.tsx` | Real-time 3s auto-polling ETL migration monitor rendering active job banners, live row progress bars, dead-letter error logs, and one-click resume/retry actions |

---

## 2. Technical Architecture & State Management

### 1. HTTP-Only Cookie Authentication & Axios Refresh Queue (`services/axios.ts`)
- **Security**: Access and refresh tokens are stored in `httponly=True` cookies, protecting session tokens from XSS attacks.
- **Organization Context**: Automatically attaches `X-Organization-Id` header from `active_org_id` cookie.
- **401 Interceptor Queue**: Intercepts HTTP 401 responses, pauses pending requests using an `isRefreshing` lock, and issues `POST /auth/refresh` to renew cookies seamlessly before retrying failed requests.
- **Toast Notifications**: Displays automated user feedback toasts (`react-hot-toast`) for network drops, 500 errors, and session expirations.

### 2. State Management Division of Labor
- **TanStack Query v5**: Handles remote server state caching, pagination, and invalidation (`useAuthUser`, `useAuthMutations`, `useAgents`, `useMetadata`).
- **Redux Toolkit**: Manages in-memory user session state (`authSlice`) and local UI state (`uiSlice`).

### 3. Real-Time WebSocket Connections (`services/agentService.ts`)
- Subscribes to `/api/v1/agents/ws/{agent_id}` to listen for live `AGENT_CONNECTED`, `AGENT_HEARTBEAT`, `METADATA_PROFILED`, and `EXECUTION_PROGRESS` signals.
- Supports **First-Frame JSON Authentication** (`{ "type": "auth", "token": "<jwt>" }`) upon WebSocket connection to eliminate JWT exposure in URL query parameters.

### 4. Interactive Transformation Blueprint & Error Recovery (`PlanBlueprintViewer.tsx`)
- **AST Revert Strategy**: Maintains `previousValidAst` state tracking, allowing users to restore the previous blueprint version if an LLM refinement produces validation errors.
- **Draft Failed Error Alert UI**: Renders explicit error card UI with diagnostic feedback and retry buttons when plan generation fails or yields 0 table mappings.
- **3-Minute Timeout & Progress UX**: Configures 180,000ms request timeout for long AI generation calls and displays a step-by-step progress indicator modal.
- **409 Conflict Concurrency Handling**: Intercepts HTTP 409 Conflict responses when triggering plan execution on an already active plan, automatically mounting the active execution progress banner.

---

## 3. Development Commands

```bash
# Install dependencies
npm install

# Start local Next.js development server
npm run dev

# Build production bundle
npm run build
```
