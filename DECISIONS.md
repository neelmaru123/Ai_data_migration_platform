# Architecture Decision Log (`DECISIONS.md`)

This file records all key architectural decisions, technology selections, trade-offs, and design rationale for the **AI Data Migration Platform**.

---

## [2026-08-11] - AI Data Migration Platform Foundation Architecture

### 1. Decision Summary
Decoupled **Transformation Intent** (AI-generated JSON schema contract) from **Transformation Execution** (deterministic stream engine using Polars/DuckDB). Provided two distinct execution modes: Cloud Async Workers (Mode A) and Standalone Local Script Generator Package (Mode B).

---

### 2. Why This Approach? (Rationale)

- **Problem Being Solved**: Large-scale data migrations often fail due to Out-Of-Memory (OOM) errors, non-deterministic AI code generation, data privacy restrictions, or high network egress bandwidth costs when transferring terabytes over cloud APIs.
- **Chosen Solution**: 
  1. **Strict JSON Schema Contract**: The AI engine ONLY outputs validated JSON transformation plans; arbitrary Python `exec()` or `eval()` is strictly forbidden for security and determinism.
  2. **Streaming Batch Engine**: ETL processing uses chunked cursor iterators and lazy frames in Polars/DuckDB.
  3. **Dual Execution Strategy**: Supports both cloud-hosted worker execution and downloadable on-premise execution packages.
- **Why Polars & DuckDB over Pandas**:
  - **Polars**: Zero-copy arrow memory format, multi-threaded vectorization, and `streaming=True` support for flat RAM footprint.
  - **DuckDB**: Embedded columnar SQL engine capable of handling out-of-core queries exceeding host memory size.
- **Why Redis + Async Worker Queue**: Fast API responses (HTTP 202 Accepted) offloading CPU-intensive ETL work to isolated worker processes.

---

### 3. Alternatives Considered & Rejected

- **Alternative A: Dynamic Python Script Execution (`exec()`)**
  - *Rejected*: Poses severe security vulnerabilities (remote code execution risks) and lacks determinism.
- **Alternative B: In-Memory Pandas Processing (`pd.read_sql_query`)**
  - *Rejected*: In-memory buffering loads full datasets into RAM, causing immediate worker OOM crashes on datasets > 4GB.
- **Alternative C: Direct Cloud ETL Transfer for All Datasets**
  - *Rejected*: Incompatible with air-gapped enterprise databases and creates expensive egress bandwidth costs on datasets > 500GB.

---

### 4. Trade-offs & Future Considerations

- **Trade-off**: Enforcing strict JSON schema contracts requires extra validation code compared to freeform script generation, but guarantees 100% execution safety.
- Future Considerations:
  - Add **Alembic** schema versioning for platform PostgreSQL metadata tables.
  - Implement partition checkpointing (`last_processed_id`) in `migration_jobs` to support zero-loss resumable task execution after worker crashes.

---

## [2026-08-11] - Modular PostgreSQL Control Plane ORM Model Implementation

### 1. Decision Summary
Implemented all 11 SQLAlchemy 2.x typed ORM models co-located in their respective domain feature modules inside `apps/api/app/modules/` (`users`, `sources`, `profiler`, `transformation_plans`, `execution`).

### 2. Why This Approach? (Rationale)
- **Domain-Driven Design (DDD)**: Each module owns its specific ORM models, Pydantic schemas, and API routes.
- **Cross-Dialect JSON Support**: Used `JSONB().with_variant(JSON, "sqlite")` to support both native PostgreSQL JSONB in production and SQLite in local fast integration tests.
- **Strict Cascading Foreign Keys**: Defined `ON DELETE CASCADE` across all parent-child relationships for automated referential integrity.

### 3. Trade-offs & Future Considerations
- Module schemas (`_schemas.py`) and routes (`_routes.py`) will consume these models as API features are added.

---

## [2026-08-11] - Code Audit & Model Type Refinement

### 1. Decision Summary
Applied recommended audit refinements across domain models and integration tests:
- Refined JSONB type annotations in `MigrationPlan` (`source_connection_ids`, `source_snapshot_ids`, `plan`) to `Mapped[Any]` to eliminate rigid dict constraints on generic JSON structures.
- Renamed local test variable `relationship` to `meta_rel` in [`test_db_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/tests/integration/test_db_models.py#L135) to avoid variable name shadowing with SQLAlchemy's `relationship` import.
- Cleaned unused `Numeric` import in [`profiler_models.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/profiler/profiler_models.py).

---

---

## [2026-08-11] - Separation of `sources_connectors` and `sources_loaders`

### 1. Decision Summary
Separated file loaders (`CSVFileLoader`, `ExcelFileLoader`) out of `sources_connectors` into a dedicated package [`apps/api/app/modules/sources/sources_loaders/`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/app/modules/sources/sources_loaders).

### 2. Why This Approach? (Rationale)
- **Single Responsibility Principle (SRP)**: Keeps `sources_connectors` focused strictly on database drivers (`postgresql`, `mysql`, `mongodb`) and `sources_loaders` focused strictly on file parsing and chunking (`csv`, `excel`).
- **Clean Architectural Boundaries**: Allows database connectors and file loaders to evolve independently with dedicated base classes and factory registries.

---

## [2026-08-11] - Bug Fix Round: Connectors & Loaders Hardening

### 1. Decision Summary
Fixed 12 bugs across `sources_connectors` and `sources_loaders` identified in a manual code audit. Fixes span critical memory issues, N+1 database queries, schemaless inference gaps, and resource leaks.

### 2. Why This Approach? (Rationale)
- **Problem Being Solved**: Multiple bugs ranging from critical (entire CSV file loaded into RAM before streaming) to minor (unused variable, confusing placeholder file).
- **CSV Streaming**: Replaced `pl.scan_csv().collect_batches()` (which loads entire file into memory first) with Python's `csv.DictReader` — true O(1) memory streaming. Row counting uses a fast line-count pass instead of a second full polars read.
- **Excel Streaming**: Replaced `pl.read_excel()` + `df.slice()` (full sheet loaded into RAM) with `openpyxl` `read_only=True` row iterator — constant memory regardless of sheet size.
- **PostgreSQL N+1 Query**: Replaced one `COUNT(*)` per table with a single `LEFT JOIN pg_class` query that fetches `reltuples` (PostgreSQL's native planner estimate) for all tables at once.
- **MySQL Schemas**: Replaced hardcoded `schemas=[db_name]` with a query against `information_schema.SCHEMATA` to list all visible databases.
- **MongoDB $sample**: Replaced single `find_one()` schema inference with `$sample: {size: 10}` aggregation that merges field names across 10 random documents — handles sparse/schemaless collections.
- **Engine Helper**: Extracted `_get_engine()` on Postgres and MySQL connectors with `pool_pre_ping=True` to ensure clean connection validation and reduce code duplication.

### 3. Alternatives Considered & Rejected
- **Polars `collect(streaming=True)` for CSV**: Polars' streaming mode is still experimental and not production-stable as of Polars 1.x. `csv.DictReader` is battle-tested.
- **Exact `COUNT(*)` for Postgres**: Would fix accuracy but causes N+1 round-trips (one per table). `pg_class.reltuples` is the same stat the query planner uses and is accurate enough for metadata display.
- **MongoDB: `$sample` with more docs**: Sampling more documents increases accuracy but also latency. 10 is a reasonable default for schema inference; configurable via `options` dict if needed later.

### 4. Trade-offs & Future Considerations
- CSV type inference is lost in `stream_chunks` (csv.DictReader returns all values as strings). Downstream ETL consumers should apply their own type coercion based on the schema from `introspect_schema()`.
- Excel streaming via openpyxl row iterator means no Polars dtype inference during streaming — same trade-off.
- Engine per-call pattern is intentionally stateless. For production, a connection pool manager at the service/application layer (not per-connector) would be more efficient.

---

## [2026-08-11] - User Module CRUD & HTTP-Only Cookie Authentication Architecture

### 1. Decision Summary
Implemented User domain CRUD operations and secure JWT Authentication System using HTTP-only cookies, token rotation (15-minute access token, 7-day refresh token), bcrypt password hashing, and authentication dependencies/middleware.

### 2. Why This Approach? (Rationale)
- **HTTP-Only Cookies for XSS Prevention**: Storing JWT access and refresh tokens in `httponly=True` cookies prevents JavaScript code on the client from accessing tokens directly, rendering XSS attacks ineffective for token theft.
- **Short-Lived Access Token (15 Mins) & Long-Lived Refresh Token (7 Days)**: Minimizes blast radius if an access token is compromised while offering seamless UX via automatic refresh token rotation.
- **Dedicated `/auth/refresh` Route with Token Rotation**: Calling `/auth/refresh` invalidates the previous refresh token payload and issues a new access token AND a new refresh token, resetting both HTTP-only cookies.
- **Bcrypt Password Hashing**: Passwords are salted and hashed using `bcrypt.hashpw()` before saving into the database. Plaintext passwords are never stored or logged.
- **Authorization Header Fallback**: Supports `Authorization: Bearer <token>` headers as a fallback so API clients (Postman, Swagger UI, Curl) can easily test protected endpoints alongside standard browser HTTP-only cookies.

### 3. Alternatives Considered & Rejected
- **Local Storage / Session Storage for JWT**: Rejected due to vulnerability to XSS attacks.
- **Single Long-Lived Access Token**: Rejected due to security risk; if compromised, the token remains valid for days without revocation capability.
- **Session-based DB sessions**: Rejected in favor of stateless JWT tokens to maintain stateless scalability across backend worker instances.

### 4. Trade-offs & Future Considerations
- CORS credentials must be enabled (`allow_credentials=True`) on frontend requests when transmitting cookies cross-origin.
- For production multi-domain deployments, ensure `COOKIE_SECURE=True` (HTTPS) and `COOKIE_SAMESITE="lax"` or `"none"`.

---

## [2026-08-12] - Phase 0: Docker Agent Architecture & Control Plane Integration

### 1. Decision Summary
Introduced the `Agent` domain model and service boundary in `apps/api/app/modules/agents/` and established the standalone `apps/agent/` Docker agent workspace for customer-hosted execution.

### 2. Why This Approach? (Rationale)
- **Customer Data Privacy**: Enterprise customers require running migration jobs inside their own VPCs without sharing raw data with cloud APIs.
- **Decoupled Control Plane & Data Plane**: The FastAPI backend acts as the central control plane (issuing jobs and receiving heartbeats/status), while standalone Docker agents execute data transfer locally.
- **Foreign Key Linking**: Added nullable `agent_id` FK to `connections` and `migration_jobs` tables so connections and execution jobs can optionally bind to customer-hosted Docker agents.

### 3. Alternatives Considered & Rejected
- **Direct Backend Execution Only**: Rejected because enterprise databases behind strict firewalls cannot be accessed directly by a public backend service.

---

## [2026-08-12] - Server-Side Google OAuth 2.0 & Identity Isolation Policy

### 1. Decision Summary
Implemented server-side Google OAuth 2.0 (`POST /auth/google`, `GET /auth/google/login`, `GET /auth/google/callback`) integrated with FastAPI's existing HTTP-only cookie JWT session system, enforcing strict account isolation rules between Google accounts and password accounts.

### 2. Why This Approach? (Rationale)
- **Cryptographic Token Verification**: Uses `google-auth` (`google.oauth2.id_token.verify_oauth2_token`) on the backend to verify Google ID token signatures against Google's public keys (`https://www.googleapis.com/oauth2/v3/certs`). Unverified frontend data is never trusted.
- **Unified Application Session**: Successful Google authentication converges into the exact same application session (`access_token` and `refresh_token` HTTP-only cookies), keeping frontend session logic clean and standardized.
- **Strict Identity Isolation Policy**:
  1. *Google Account Attempting Password Registration*: Rejected with `409 Conflict` ("An account with this email was created using Google Sign-In").
  2. *Google Account Attempting Password Login*: Rejected with `400 Bad Request` ("This account was created using Google Sign-In").
  3. *Unlinked Password Account Attempting Google Login*: Restricted with `409 Conflict` ("An account with this email already exists using password authentication").
  4. *Deactivated Account Attempting OAuth*: Rejected with `400 Bad Request` ("User account is deactivated").
  5. *Unverified Google Email*: Rejected with `400 Bad Request` ("Google account email is not verified").
- **Dynamic Client Component Spline Loading**: Loaded `@splinetool/react-spline/next` via `next/dynamic` with `{ ssr: false }` to prevent React 18/19 Next.js 14 client component async rendering errors.

### 3. Alternatives Considered & Rejected
- **Trusting Client User Data**: Rejected due to critical security risk (account takeover by passing arbitrary email in JSON body).
- **Separate Session System for Google Users**: Rejected to prevent maintaining parallel authentication middleware, route guards, and cookie handling.

### 4. Trade-offs & Future Considerations
- Requires configuring `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` for production Google OAuth consent screens.

---

## [2026-08-13] - Next.js Frontend State Management Architecture & HTTP-Only Cookie Axios Interceptor Setup

### 1. Decision Summary
Established the complete frontend architecture in `apps/web` (Next.js App Router). Configured Axios ([`services/axios.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/services/axios.ts)) using HTTP-only cookies (`withCredentials: true`), dynamic organization header insertion via `js-cookie` (`X-Organization-Id`), automatic token refresh on `401` status via `/auth/refresh`, user notification toasts via `react-hot-toast`, TanStack Query v5 for remote global server state, and Redux Toolkit for local client state.

### 2. Why This Approach? (Rationale)
- **HTTP-Only Cookies Security**:
  - Access and refresh tokens are managed natively via secure HTTP-only cookies, eliminating XSS vulnerabilities associated with storing tokens in `localStorage`.
- **Axios Token Refresh Interceptor (`services/axios.ts`)**:
  - Configured with `withCredentials: true`.
  - Automatically attaches `X-Organization-Id` header if `active_org_id` cookie is present.
  - Intercepts `401 Unauthorized` responses and pauses execution using `isRefreshing` lock and `failedQueue`.
  - Sends `await apiClient.post('/auth/refresh')` to seamlessly renew cookies and retry pending requests.
  - Displays user-friendly error toasts (`react-hot-toast`) on session expiration ("Session expired. Please log in again."), network failures, or 500 server errors, redirecting to `/login` when unauthenticated.
- **TanStack Query & Redux Division of Labor**:
  - **TanStack Query**: Handles remote auth query/mutation hooks ([`useAuthUser.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/hooks/queries/useAuthUser.ts), [`useAuthMutations.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/hooks/mutations/useAuthMutations.ts)).
  - **Redux Toolkit**: Maintains in-memory user session & local UI state ([`authSlice.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/store/slices/authSlice.ts), [`uiSlice.ts`](file:///c:/Users/91873/Desktop/Data_migration_tool/Ai_data_migration_platform/apps/web/store/slices/uiSlice.ts)).

### 3. Trade-offs & Future Considerations
- Eliminates manual token decoding or localStorage management on the client side.

---

## [2026-08-13] - Component-Based 3D Interactive Landing Page Implementation

### 1. Decision Summary
Built a component-based interactive Landing Page for `apps/web` featuring a full-screen dynamic Spline 3D Hero background (`https://prod.spline.design/E6eFCzHp4BkxYnO7/scene.splinecode`), followed by structured feature sections detailing AI schema intelligence, streaming ETL capabilities, Bento Grid showcase, 4-step workflow, and glassmorphic CTAs.

### 2. Why This Approach? (Rationale)
- **Dynamic 3D Spline Canvas (`SplineHeroBackground.tsx`)**: Loaded via `next/dynamic` with `{ ssr: false }` to prevent SSR hydration mismatches while offering visual wow factor. Includes a fallback glowing loader.
- **Component-Based Architecture**: Modularized into single-responsibility components (`Navbar`, `Hero`, `PlatformOverview`, `FeaturesGrid`, `WorkflowSteps`, `Footer`) in `components/landing/`.

---

## [2026-08-13] - 2-Column Split Authentication Pages (`/register` & `/login`) with React Hook Form

### 1. Decision Summary
Built the **Registration** (`/register`) and **Login** (`/login`) pages using a 2-column split layout (`AuthLayout.tsx`). The left column renders the 3D Spline scene component, while the right column hosts the reactive form rendered with `react-hook-form`, front-end validation (name, email regex, password 8–12 chars), Google authentication button, and integration with `useRegister()` and `useLogin()` hooks.

### 2. Why This Approach? (Rationale)
- **2-Column Split (`AuthLayout.tsx`)**: Offers visual consistency across `/register` and `/login` while maintaining full focus on the input form on the right pane.
- **`react-hook-form` Validation**:
  - `name`: Required, min 2 characters.
  - `email`: Required, validated via `/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i` regex.
  - `password`: Required, strictly enforced between 8 and 12 characters (`minLength: 8, maxLength: 12`).
- **Humanized Angular Design**: Styled with Plus Jakarta Sans typography, solid dark slate containers (`bg-slate-950`), and sharp borders (`rounded-sm`).





---

## [2026-08-13] - Agent-Centric Database Architecture & Credential Elimination

### 1. Decision Summary
Eliminated database credentials (`host`, `port`, `username`, `password`, `credentials_encrypted`) from the control plane backend. Dropped the obsolete `connections` table and replaced it with a lightweight `data_sources` identity table (`id`, `agent_id`, `name`, `type`, `role`, `identifier`).

### 2. Why This Approach? (Rationale)
- **Zero Control-Plane Storage of Credentials**: Customer database passwords and connection strings remain strictly inside customer-hosted local Docker Agents. The control plane backend only stores logical source identities and collected metadata history.
- **N:M Migration Plan Snapshots**: Created `migration_plan_snapshots` join table so a single `MigrationPlan` can combine metadata snapshots from multiple data sources (e.g. Postgres + MySQL into a new Postgres target).
- **Graceful Deletion Handling**: Changed `agent_id` FK on `migration_plans` to `ondelete="SET NULL"` so completed historical migration plans survive agent deregistration.

### 3. Trade-offs & Future Considerations
- Alembic migration `004_agent_centric_arch` handles schema transition with full `upgrade()` and `downgrade()` safety.

---

## [2026-08-13] - Sources & Agents Domain Security, Ownership Middleware & Roles

### 1. Decision Summary
Implemented security middleware dependencies (`sources_dependencies.py`) enforcing agent and data source ownership verification across all endpoints. Added a `role` field (`"source"`, `"target"`, `"both"`) to `data_sources`.

### 2. Why This Approach? (Rationale)
- **IDOR & Ownership Protection**: Dependencies `get_verified_agent` and `get_verified_data_source` verify that the target agent/source belongs to `current_user.id`, returning `403 Forbidden` if ownership validation fails.
- **Role Categorization**: Explicitly categorizing data sources by role (`source`, `target`, `both`) enables schema profiling on both source DBs and target DBs while allowing clear UI separation.
- **Strict Pydantic Validation**: Used Pydantic `Literal` types (`VALID_SOURCE_TYPES`, `VALID_SOURCE_ROLES`) and `min_length=1` field constraints to reject invalid inputs at the API gateway layer.

---

## [2026-08-13] - Agent Domain Module APIs & Concurrent Data Sources Creation

### 1. Decision Summary
Implemented complete Agent CRUD endpoints (`POST /agents`, `GET /agents`, `GET /agents/{id}`, `PUT /agents/{id}`, `POST /agents/{id}/heartbeat`, `DELETE /agents/{id}`) with support for atomic concurrent creation of Agent + initial Source and Destination DB identities.

### 2. Why This Approach? (Rationale)
- **Atomic Single-Transaction Setup**: When calling `POST /api/v1/agents`, the payload can include an array of initial `data_sources`. The service creates the Agent record and all attached Data Source records within a single database transaction, ensuring no partial or orphaned state occurs.
- **Periodic Heartbeat Tracking**: Endpoint `POST /agents/{id}/heartbeat` allows Docker Agents to ping status (`online`, `busy`), update `version`, and update `last_seen_at` timestamp.

---

## [2026-08-14] - Docker Command Generator & Zero-Credential Control Plane Isolation

### 1. Decision Summary
Implemented `AgentCommandGenerator` service and API response enhancements (`POST /api/v1/agents` and `GET /api/v1/agents/{id}/docker-command`) that automatically construct ready-to-run Docker CLI commands (Bash multi-line, PowerShell, single-line) and `.env` templates parameterized with the generated `AGENT_TOKEN`, `BACKEND_URL`, and credential placeholders for merging multiple source databases into a destination database.

### 2. Why This Approach? (Rationale)
- **Zero Control-Plane Storage of Sensitive DB Credentials**: Control plane never stores or requires sensitive database passwords/credentials over the network. Instead, the backend generates parameterized Docker commands with credential placeholders (`<SRC_DB_PASSWORD>`, `<DEST_DB_PASSWORD>`, `<DB_NAME>`) that the customer fills directly in their local shell environment before booting the container.
- **Multi-Platform Support**: Generates cross-platform commands formatted for standard Bash/macOS/Linux (`\`), Windows PowerShell (`` ` ``), single-line execution, and `.env` file ingestion.
- **Cross-Platform Host Routing**: Injects `--add-host=host.docker.internal:host-gateway` to guarantee seamless connectivity from the container back to host localhost services across Windows, macOS, and Linux Docker engines.
- **Multi-Source Merge Handling**: Dynamically parses all registered data sources by role (`source`, `target`, `both`) and database type (`postgresql`, `mysql`, `mongodb`, `mssql`, file loaders) generating sanitized environment variable prefixes (`SRC_<IDENTIFIER>_URL`, `DEST_<IDENTIFIER>_URL`) and single-source convenience aliases.

### 3. Alternatives Considered & Rejected
- **Alternative A: Storing DB Passwords in Backend Database**: Rejected due to enterprise security risks and compliance restrictions regarding plaintext or reversible cloud credential storage.
- **Alternative B: Pure Client-Side Command Generation**: Rejected because backend owns the API token lifecycle, configuration defaults, and database type dialect URL specifications.

### 4. Trade-offs & Future Considerations
- Returned commands contain placeholder strings (`<...>`) which require the user to fill in their real passwords locally before executing the Docker run command.

---

## [2026-08-14] - Multi-Step Agent Creation Page (1:1, 2:1, 3:1, Custom N:1) & Docker Command UI

### 1. Decision Summary
Implemented a 3-step Agent Creation wizard in `apps/web/app/agents/create/page.tsx` that guides users through migration ratio selection (`1:1`, `2:1`, `3:1`, `Custom N:1`), database engine setup (strictly restricted to `postgresql`, `mysql`, `mongodb`, `csv`, `excel`), agent registration, Docker CLI command rendering, and real-time agent connectivity monitoring over WebSocket.

### 2. Why This Approach? (Rationale)
- **Step 1: Ratio Selection (`TopologySelector.tsx`)**: Offers visual interactive cards for `1:1`, `2:1`, `3:1`, and `Custom N:1` topologies with glowing borders and dynamic source count state.
- **Step 2: Database & Engine Selection (`DatabaseConfigForm.tsx`)**: Enforces input/output database engine types strictly to `postgresql`, `mysql`, `mongodb`, `csv`, `excel`. Generates input forms for N source databases + 1 destination database.
- **Step 3: Docker Deployment CLI & Live Monitoring (`DockerCommandOutput.tsx`)**:
  - Displays generated `docker run` command and `docker-compose.yml` snippet with one-click copy button.
  - Subscribes via WebSocket to `/api/v1/agents/ws/{agent_id}` (with polling fallback) to dynamically update agent status badge from `WAITING FOR AGENT PING` to `ONLINE` as soon as the user runs the container.
- **Service Integration & Teammate API Resilience (`agentService.ts`)**: Integrates with `POST /api/v1/agents` for registration and `POST /api/v1/agents/{agent_id}/docker-cmd` for Docker command generation, with client-side fallback formatting in case the backend teammate's endpoint is still in deployment.


---

## [2026-08-14] - Complete Edge Case Hardening: Stale Watchdog, Concurrent Diagnostics & Status Immutability

### 1. Decision Summary
Fixed 14 systemic edge cases across the Docker Agent and FastAPI backend:
1. **Ghost Agent & Stale Job Watchdog**: Implemented periodic background watchdog loop in FastAPI `lifespan` detecting dead agents (>60s inactivity), transitioning them to `offline`, and automatically failing orphaned `MigrationJob` records.
2. **Concurrent Database Socket Checks**: Refactored agent health diagnostics to run across all configured databases in parallel using `concurrent.futures.ThreadPoolExecutor`, strictly bounding socket diagnostic time to $\le 3.5\text{s}$ total.
3. **Graceful Offline Signaling**: Registered `SIGINT`/`SIGTERM` handlers in the Docker Agent to dispatch a final `status: "offline"` heartbeat before container termination.
4. **Strict Schema Constraints & Status Immutability**: Enforced Pydantic `Literal["online", "offline", "busy", "degraded", "error"]` validation on heartbeats and removed `status` from user-facing `AgentUpdate` REST payload to prevent status spoofing.
5. **Per-User Identifier Uniqueness**: Changed `Agent.agent_identifier` from global unique constraint to composite `UniqueConstraint("user_id", "agent_identifier")`.
6. **Degraded Health Calculation & Fuzzy Matching**: Agent reports `status: "degraded"` when any database source is unreachable, and backend uses fuzzy identifier resolution (`src_...`, `dest_...`) to prevent dropped reports.
7. **Heartbeat Throttling & WebSocket Keepalive**: Added rate-limiting guards against rapid ping spamming and implemented WebSocket ping/pong protocol for persistent connection keepalive across proxies.

### 2. Why This Approach? (Rationale)
- **Bounded Latency**: Sequential database testing across 5+ failing databases would cause a 17.5s blocking delay, causing the agent to miss its heartbeat window and appear dead to the control plane. Concurrent threading bounds this to max 3.5s.
- **Single Source of Truth for Status**: Agent status is solely controlled by authentic agent heartbeats and the backend watchdog; users cannot manually alter status via REST API.
- **Fail-Safe Job Lifecycle**: If an on-premise Docker container crashes or loses network mid-migration, jobs don't stay in `running` state forever; the control plane auto-recovers and notifies the UI.

### 3. Alternatives Considered & Rejected
- **Alternative A: Relying Solely on Docker Exit Codes**: Rejected because the control plane has no direct access to customer on-premise Docker daemons.
- **Alternative B: Client-Side Polling Only**: Rejected because if the browser tab closes, job state remains stuck in `running` on the backend.
- **Alternative C: Sequential Socket Tests with Lower Timeouts (0.5s)**: Rejected because high-latency WAN / cloud database handshakes would produce false connection timeouts.

### 4. Trade-offs & Future Considerations
- In distributed multi-worker deployments of the API control plane, the in-memory WebSocket manager can be backed by Redis Pub/Sub (`settings.REDIS_URL`) for cross-node event distribution.

---

## [2026-08-14] - Alembic Migration 005: Agent API Tokens & DataSource Health Diagnostics

### 1. Decision Summary
Created Alembic migration [`005_add_agent_tokens_and_datasource_diagnostics.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/alembic/versions/005_add_agent_tokens_and_datasource_diagnostics.py) to synchronize all database tables with newly introduced model fields.

### 2. Why This Approach? (Rationale)
- **Model-to-Schema Synchronization**:
  1. `agents.api_token_hash`: Added `String(255)` with unique index `ix_agents_api_token_hash` for secure SHA-256 agent authentication.
  2. `agents` per-user uniqueness: Converted `agent_identifier` from global unique index to composite `UniqueConstraint("user_id", "agent_identifier", name="uq_agents_user_identifier")`.
  3. `data_sources.status`: Added `String(50)` (default `"untested"`).
  4. `data_sources.last_error`: Added nullable `String` for sanitized error messages.
  5. `data_sources.last_checked_at`: Added nullable `DateTime(timezone=True)` for health check timestamps.
- **Continuous Revision Linearity**: Verified linear migration DAG: `001_initial_schema` $\rightarrow$ `002_add_agents` $\rightarrow$ `003_add_google_auth_to_users` $\rightarrow$ `004_agent_centric_arch` $\rightarrow$ `005_agent_tokens_and_diagnostics`.

### 3. Trade-offs & Future Considerations
- Full `upgrade()` and `downgrade()` methods implemented to ensure zero data corruption during deployment rollbacks.

---

## [2026-08-17] - Phase 2: Metadata Domain Architecture & On-Premise Introspection Engine

### 1. Decision Summary
Renamed the control plane `profiler` feature module to **`metadata`** (`apps/api/app/modules/metadata/`) and implemented end-to-end database schema introspection, snapshot versioning, control plane ingestion, and real-time WebSockets:
1. **Domain Rename**: Migrated all models (`metadata_models.py`), schemas (`metadata_schemas.py`), services (`metadata_services.py`), and routes (`metadata_routes.py`) into `app/modules/metadata`.
2. **On-Premise Introspection Engine**: Implemented [`apps/agent/metadata_engine.py`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/agent/metadata_engine.py) to introspect database schemas, tables, estimated row counts, column data types, nullability, primary keys, and foreign key relationships locally inside customer VPCs.
3. **Control Plane Ingestion & Auto-Versioning**: Endpoint `POST /api/v1/metadata/sync` ingests agent payloads, auto-increments version numbers per DataSource, and bulk-persists `MetadataSnapshot`, `MetadataSchema`, `MetadataTable`, `MetadataColumn`, `MetadataConstraint`, and `MetadataRelationship` records in PostgreSQL within a single atomic database transaction.
4. **Real-Time Push Notifications**: Pushes `METADATA_PROFILED` events over WebSockets via `manager.broadcast_to_agent()` to update Next.js dashboard clients instantly.

### 2. Why This Approach? (Rationale)
- **Zero Raw Data Transfer**: Customer passwords and table data remain strictly on-premise. Only structural schema ASTs are transmitted to the control plane.
- **Atomic Hierarchy Persistence**: Flushing parent IDs (`snapshot_id`, `schema_id`, `table_id`) in a single session transaction ensures complex relational metadata is stored without orphaned records.
- **Fuzzy Identifier Resolution**: Ingestion matches data sources by UUID or clean identifier (`src_...`, `dest_...`), preventing dropped snapshots due to environment naming variations.

### 3. Trade-offs & Future Considerations
- File-based sources (CSV/Excel) currently infer schemas from top row headers; future enhancement can add deep data type sniffing for multi-gigabyte files.





