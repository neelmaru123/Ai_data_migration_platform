# AI Data Migration Platform — Project Structure & Architecture Guide

An enterprise-grade, AI-assisted platform for end-to-end database migration, multi-source data merging, schema profiling, versioned transformation planning, and zero-raw-data-cloud leakage streaming ETL.

> **Core Platform Paradigm**:
> 
> $$\text{VERSIONED TRANSFORMATION BLUEPRINT} \longrightarrow \text{ON-PREMISE DOCKER AGENT STREAMING}$$
> 
> The platform strictly decouples **Control Plane Intent** (AI-generated, Pydantic-validated JSON blueprint contracts) from **Data Plane Execution** (deterministic local Polars/DuckDB streaming executed on-premise inside customer VPCs). No raw database data ever leaves the customer network.

---

## 1. Technology Stack

### Frontend Stack (`apps/web`)
- **Framework**: Next.js 14 (App Router with Middleware route protection)
- **Language**: TypeScript
- **State Management**: Redux Toolkit (local session UI) & TanStack Query v5 (remote server cache & mutations)
- **Authentication & Security**: HTTP-only JWT cookies, Axios 401 auto-refresh queue (`services/axios.ts`), First-Frame WebSocket JSON Auth
- **Interactive Visual Mapping & UI**: React Flow (`reactflow`), Lucide React (`lucide-react`), Tailwind CSS, Spline 3D (`@splinetool/react-spline/next`), `react-hot-toast`

### Backend Control Plane Stack (`apps/api`)
- **Language**: Python 3.11+
- **API Framework**: FastAPI & Uvicorn (ASGI)
- **Dependency & Project Management**: Poetry (`pyproject.toml` & `poetry.lock`)
- **Data Validation & Schemas**: Pydantic v2 & Pydantic-Settings
- **ORM & Database**: SQLAlchemy v2 (AsyncPG driver for PostgreSQL, SQLite for fast integration tests)
- **Database Versioning & Migrations**: Alembic (Migrations `001` through `008_add_migration_plan_versions.py`)
- **Task Queue & Telemetry**: Celery / RQ with Redis backend, WebSocket Manager with active broadcast channels
- **AI Reasoning & Stateful Graph**: Google Gemini 3.5 Flash Lite (`google-generativeai`, `langchain-google-genai`), LangGraph `StateGraph` with 5-stage deterministic feasibility validator
- **Testing & Tooling**: Pytest, Pytest-Asyncio, HTTPX, Ruff

### On-Premise Docker Agent Stack (`apps/agent`)
- **ETL Engine**: Modular Python ETL Engine (`engine/connectors`, `engine/transformers`, `engine/staging`, `engine/writers`, `engine/orchestrator`, `engine/checkpoint`, `engine/ddl_executor`)
- **Data Processing Stack**: Polars (zero-copy Arrow memory engine), DuckDB (disk-backed out-of-core streaming staging for multi-source merges `staging_*.duckdb`), PyArrow, OpenPyXL, PyMongo, SQLAlchemy
- **Container Infrastructure**: Customer VPC Docker Daemon, auto-registration loop, 20s background heartbeat thread, 20s task poller, graceful signal handling (`SIGINT`/`SIGTERM`)

---

## 2. Monorepo Architectural Pattern

This project follows a **Feature-Wise Modular Architecture** (Domain-Driven Feature Layout).

### Key Architectural Rules
1. **Self-Contained Domain Modules**: Every feature domain lives in `apps/api/app/modules/<feature_name>/` and encapsulates its own models, schemas, services, API routes, processing engines, and background tasks.
2. **Explicit File Naming Convention**: File names inside a feature module are explicitly prefixed with the feature name (`<feature_name>_<layer>.py`) to prevent ambiguity across imports (e.g. `metadata_models.py`, `migration_plans_services.py`).
3. **Thin API Routes**: Routes only handle HTTP request parsing, status codes, and dependency injection. Business logic resides strictly in `*_services.py` or `*_engine.py`.
4. **Zero Dynamic AI Code Execution**: The AI module outputs strongly typed, Pydantic-validated JSON blueprints (`TransformationPlanAST`). Raw code execution (`exec()`, `eval()`) is strictly prohibited.
5. **Zero Control-Plane Storage of DB Passwords**: Customer database credentials remain strictly inside customer-hosted local Docker Agents. The control plane backend only stores logical source identities and structural catalog metadata.

---

## 3. Directory Structure & File Roles

```text
data-migration-platform/
│
├── apps/
│   │
│   ├── web/                                  # Frontend Web Application (Next.js 14 App Router)
│   │   ├── app/                              # App Pages: /login, /register, /dashboard, /agents/create, /sources, /profiling, /transformation-plan, /execution
│   │   ├── components/                       # UI components: AgentStatusBanner, SchemaCatalogViewer, PlanBlueprintViewer, JobExecutionBanner, DockerCommandOutput, TopologySelector
│   │   ├── hooks/                            # TanStack Query hooks (useAuthUser, useAgents, useMetadata, usePlanVersioning)
│   │   ├── middleware.ts                     # Next.js route protection & authentication middleware
│   │   ├── services/                         # Axios client with HTTP-only cookies, 401 refresh queue, and WebSocket manager
│   │   └── store/                            # Redux Toolkit & TanStack Query store context
│   │
│   ├── agent/                                # Customer On-Premise Docker Agent Daemon Workspace
│   │   ├── main.py                           # Daemon loop, background heartbeat thread (20s), task poller & auto-registration
│   │   ├── metadata_engine.py                # Schema introspection engine (capping schema scanning at top 500 tables by row count)
│   │   ├── execution_engine.py               # Local ETL execution facade
│   │   └── engine/                           # Modular ETL Pipeline Engine
│   │       ├── checkpoint.py                 # Isolated checkpoint state manager (job_id, target_table, source_id, source_table) & post-job cleanup
│   │       ├── connectors/                   # SourceConnectorFactory (Postgres, MySQL, SQLite, MongoDB, CSV, Excel) with Keyset Pagination
│   │       ├── db.py                         # Database helper utilities & connection pool management
│   │       ├── ddl_executor.py               # Pre-DDL target schema setup & Post-DDL foreign key execution
│   │       ├── orchestrator.py               # ExecutionOrchestrator managing multi-source merges, DuckDB staging, and status reporting
│   │       ├── progress_reporter.py          # HTTP progress reporter pushing telemetry to control plane
│   │       ├── staging/                      # DuckDB local disk staging (staging_*.duckdb) for bounded RAM (~50k row chunks) multi-source deduplication
│   │       ├── transformers/                 # ASTTransformer applying 9 column transformation types, PK strategies, regex expression sanitization, decimal precision
│   │       └── writers/                      # TargetWriterFactory executing bulk inserts (Postgres session_replication_role reset, MySQL, MongoDB write-error handling)
│   │
│   └── api/                                  # Control Plane FastAPI Backend Service
│       ├── alembic/                          # Alembic Database Migration Revisions
│       │   └── versions/                     # Migration scripts 001_initial_schema through 008_add_migration_plan_versions.py
│       │
│       ├── app/
│       │   ├── core/                         # Core infrastructure (config, db session, security, structured logging, WebSocket manager)
│       │   │
│       │   └── modules/                      # Domain-Driven Feature Modules
│       │       ├── users/                    # User identity, JWT, HTTP-only cookie auth, Google OAuth 2.0 & account isolation policy
│       │       ├── agents/                   # Docker Agent lifecycle, SHA-256 token auth, Docker CLI command generator, watchdog
│       │       ├── sources/                  # Data source registration, role categorization (source/target/both), connectors & loaders
│       │       ├── metadata/                 # Introspection snapshot storage, schema hierarchy & auto-versioning
│       │       ├── migration_plans/          # Gemini 3.5 Flash Lite planner, LangGraph StateGraph, 5-stage feasibility validator, blueprint versioning
│       │       └── execution/                # Job dispatcher, atomic task claiming (SKIP LOCKED), AI error diagnosis background LLM synthesizer, execution locks (409 Conflict)
│       │
│       ├── scripts/                          # DB Seeding & Multi-DB Simulation Test Helpers (seed_test_dbs.py)
│       ├── tests/                            # Comprehensive Test Suites (unit, integration, e2e)
│       ├── Dockerfile                        # Multi-stage production container for API backend
│       ├── poetry.lock                       # Locked Python dependency versions
│       ├── pyproject.toml                    # Poetry project configuration & dependencies
│       └── README.md                         # Backend module documentation
│
├── docs/                                     # System Documentation & Architecture Decision Records
│   ├── DECISIONS.md                          # Comprehensive Architecture Decision Log (2026-08-11 to 2026-08-27)
│   ├── EXECUTION_FLOW.md                     # End-to-End System Execution Flow & Sequence Diagrams
│   ├── LANGGRAPH_ARCHITECTURE.md             # LangGraph 9-Node StateGraph Technical Architecture
│   └── ...                                   # Additional domain guide markdown files
│
├── docker-compose.yml                        # Docker Compose orchestrating Next.js, FastAPI, Postgres, Redis
├── .env.example                              # Environment variable template
├── ARCHITECTURE.md                           # Core system architecture specification
├── CONTRIBUTING.md                           # Developer contribution guidelines
└── README.md                                 # Monorepo root README
```

---

## 4. What Code Each File Type Must Contain

| File Type / Extension Pattern | Responsibility & Code Contents |
| :--- | :--- |
| `*_models.py` | **SQLAlchemy ORM Models**: Database table definitions (e.g. `User`, `DataSource`, `MetadataSnapshot`, `MigrationPlan`, `MigrationPlanVersion`, `MigrationJob`). Defines column types, indices, FK relationships, and cascade behaviors. |
| `*_schemas.py` | **Pydantic Schemas & DTOs**: Request/response contracts, API payloads, and strongly typed JSON specifications (e.g. `TransformationPlanAST`, `ColumnMappingSpec`, `ExecutionProgressUpdate`, `AIDiagnosisResponse`). |
| `*_services.py` | **Application Services**: Business logic & orchestration between ORM models, domain engines, connectors, LangGraph state graphs, and AI diagnostic modules. |
| `*_routes.py` | **FastAPI Route Handlers**: HTTP route endpoints (`@router.get`, `@router.post`). Must remain thin by passing parsed inputs to services. |
| `*_engine/` | **Processing & Computation Engines**: Schema validation algorithms, LangGraph multi-node state graphs, Gemini LLM prompt serializers, and on-premise ETL engines. |
| `*_connectors/` & `*_loaders/` | **Data Source Readers**: Database drivers (`postgresql`, `mysql`, `mongodb`, `sqlite`) and file streamers (`csv`, `excel`). |
| `alembic/versions/` | **Database Schema Migrations**: Strictly linear schema migration scripts managing structural PostgreSQL table evolution (`001` through `008`). |

---

## 5. Core Platform Pillars & Architectural Safeguards

### 1. Zero Raw Data Cloud Egress
Database extraction, column transformations, primary key rekeying, multi-database table merging, and bulk loading execute **100% locally inside customer Docker Agents**. Only structural schema ASTs and progress counts are transmitted to the Control Plane.

### 2. LangGraph AI Blueprint Generator with Versioning & HITL Gateway
- **LangGraph 9-Node StateGraph**: Manages AI plan generation, structural schema validation, error auto-correction, and human feedback refinement.
- **5-Stage Deterministic Feasibility Validator**: Validates table/column existence, data type compatibility, pre-migration DDL statements, post-migration foreign keys, and circular FK dependencies before approval.
- **Blueprint Version History (v1, v2, ...)**: Every plan edit or natural language refinement creates a tracked `MigrationPlanVersion`. Users can inspect, revert to previous versions, or execute any past blueprint version directly from the Web UI.
- **Human-in-the-Loop Gateway**: AI plans NEVER execute automatically. Explicit human review and approval in the Web UI is strictly required.

### 3. Bounded-RAM Multi-Source Staging (`staging_*.duckdb`)
- When merging data from multiple source databases (e.g. Postgres + MySQL into Postgres target), extracted chunks are staged in a local temporary DuckDB disk file (`staging_{job_id}_{table}.duckdb`).
- Extracted Polars DataFrames are discarded from RAM, bounding peak memory consumption to ~50,000 rows per batch regardless of dataset scale (even for datasets > 100GB).
- Stale staging files are automatically cleaned up on job completion or engine startup.

### 4. AI Execution Error Diagnosis & Self-Healing UI
- When a migration job fails midway (e.g. network disconnect, port mismatch, constraint failure), an asynchronous background task invokes Gemini to analyze the traceback and target schema.
- Synthesizes plain-English root causes, step-by-step remediation instructions, and copyable CLI commands with password placeholders (`<SRC_DB_PASSWORD>`).
- Web UI (`JobExecutionBanner.tsx`) displays the diagnostic card, run history selector (`Run #1`, `Run #2`), and a **`⚡ RETRY MIGRATION JOB`** button for 1-click execution retries.

### 5. Enterprise Security & Concurrency Safeguards
- **HTTP-Only JWT Cookies & Google OAuth 2.0**: Secure authentication with strict account isolation between password users and Google OAuth users.
- **Decoupled Heartbeat Thread**: Background daemon thread in Docker Agent sends 20s heartbeats independently of ETL processing, preventing false offline warnings.
- **Atomic Task Claiming (`SKIP LOCKED`)**: Task polling uses PostgreSQL row-level locks (`.with_for_update(skip_locked=True)`) to ensure single-consumer task assignment across multi-container agent clusters.
- **First-Frame WebSocket Auth**: WebSocket client authenticates via initial JSON message (`{ "type": "auth", "token": "<jwt>" }`), eliminating JWT token exposure in URL query parameters.

---

## 6. Quickstart & Verification Guide

### 1. Running with Docker Compose (Recommended)

```bash
# 1. Copy environment variables template
cp .env.example .env

# 2. Build and start all services (Next.js, FastAPI, Postgres, Redis)
docker compose up --build
```

- **Frontend Application**: `http://localhost:3000`
- **FastAPI Documentation**: `http://localhost:8000/docs`
- **API Health Check**: `http://localhost:8000/api/v1/health`

### 2. Manual Backend Database Setup & Seeding

```bash
# Navigate to API directory
cd apps/api

# Run Alembic migrations up to head (Includes 008_add_migration_plan_versions)
poetry run alembic upgrade head

# Seed multi-database test environments (Postgres, MySQL, SQLite, Mongo)
poetry run python scripts/seed_test_dbs.py
```

### 3. Running Automated Test Suites

```bash
# Run unit tests across all domain modules
cd apps/api
poetry run pytest tests/unit/

# Test database plan versioning specifically
poetry run pytest tests/unit/test_plan_versioning.py
```

### 4. Running the On-Premise Docker Agent

```bash
docker run -d \
  --name ai-migration-agent \
  -e BACKEND_URL="http://localhost:8000" \
  -e AGENT_TOKEN="ag_live_..." \
  -e USER_EMAIL="user@example.com" \
  -e USER_PASSWORD="SecurePassword123" \
  -e SRC_DB_1_URL="postgresql://user:pass@host:5432/source_db" \
  -e DEST_DB_1_URL="postgresql://user:pass@host:5432/target_db" \
  --add-host=host.docker.internal:host-gateway \
  neelmaru123/ai-data-migration-agent:latest
```
