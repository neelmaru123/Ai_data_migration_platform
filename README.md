# AI Data Migration Platform — Project Structure & Architecture Guide

An enterprise-grade, AI-assisted platform for data migration, data merging, data profiling, cleaning, and transformation.

> **Core Paradigm**:
> 
> $$\text{ONE TRANSFORMATION PLAN} \longrightarrow \text{MULTIPLE EXECUTION MODES}$$
> 
> The platform supports two execution modes driven by the **SAME** transformation plan:
> 1. **Cloud Execution Mode**: Asynchronous deterministic data streaming via Polars/DuckDB managed by background worker processes.
> 2. **Local Script Package Mode**: Self-contained generated `.zip` package containing `run.py`, `migration_plan.json`, and setup dependencies for local/on-premise execution.

---

## 1. Technology Stack

### Frontend Stack (`apps/web`)
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **State Management**: Redux Toolkit & TanStack Query (`@tanstack/react-query`)
- **Styling**: Tailwind CSS & CSS Variables
- **Interactive Visual Mapping**: React Flow (`reactflow`)
- **Icons & UI Utilities**: Lucide React (`lucide-react`), `clsx`, `tailwind-merge`

### Backend Stack (`apps/api`)
- **Language**: Python 3.11+
- **API Framework**: FastAPI & Uvicorn
- **Dependency Management**: Poetry (`pyproject.toml` & `poetry.lock`)
- **Data Validation & Schemas**: Pydantic v2 & Pydantic-Settings
- **ORM & Database**: SQLAlchemy v2 (AsyncPG driver for PostgreSQL metadata)
- **Data Processing Stack**: Polars, DuckDB, PyArrow, OpenPyXL
- **Task Queue & Workers**: Celery / RQ with Redis backend
- **AI Reasoning Engine**: Google Gemini (`google-generativeai`) with Pydantic structured output enforcement
- **Testing & Tooling**: Pytest, Pytest-Asyncio, HTTPX, Ruff

---

## 2. Monorepo Architectural Pattern

This project follows a **Feature-Wise Modular Architecture** (Domain-Driven Feature Layout).

### Key Architectural Rules
1. **Self-Contained Feature Modules**: Every feature domain lives in `apps/api/app/modules/<feature_name>/` and encapsulates its own models, schemas, services, API routes, processing engines, and background tasks.
2. **Explicit File Naming Convention**: File names inside a feature module are explicitly prefixed with the feature name (`<feature_name>_<layer>.py`) to prevent ambiguity across imports (e.g. `profiler_models.py`, `profiler_services.py`).
3. **Thin API Routes**: Routes only handle HTTP request parsing, status codes, and dependency injection. Business logic resides strictly in `*_services.py` or `*_engine.py`.
4. **No Dynamic AI Code Execution**: The AI module outputs strongly typed, Pydantic-validated JSON plans (`TransformationPlan`). Raw code execution (`exec()`, `eval()`) is strictly prohibited.

---

## 3. Directory Structure & File Roles

```text
data-migration-platform/
│
├── apps/
│   │
│   ├── web/                                  # Frontend Web Application
│   │   ├── app/                              # Next.js 14 App Router Pages
│   │   │   ├── sources/page.tsx              # Page: Data Sources management UI
│   │   │   ├── profiling/page.tsx            # Page: Dataset profiler dashboard UI
│   │   │   ├── transformation-plan/page.tsx  # Page: AI Transformation Plan review & approval UI
│   │   │   ├── execution/page.tsx            # Page: Cloud migration job monitor & local package download UI
│   │   │   ├── globals.css                   # Global Tailwind CSS styles
│   │   │   ├── layout.tsx                    # Root layout with navigation navbar
│   │   │   └── page.tsx                      # Dashboard landing page
│   │   │
│   │   ├── components/                       # Shared UI Components
│   │   │   └── navbar.tsx                    # Top navigation header component
│   │   │
│   │   ├── features/                         # Modular Frontend Feature Logic
│   │   │   ├── sources/                      # Sources state, API hooks, and modal components
│   │   │   ├── profiling/                    # Profiler charts, metrics display, and hooks
│   │   │   ├── transformation_plans/         # Plan editor, JSON viewer, and review components
│   │   │   └── execution/                    # Job progress bar and script download handlers
│   │   │
│   │   ├── Dockerfile                        # Multi-stage production container for web client
│   │   ├── package.json                      # Node.js dependencies & scripts
│   │   ├── postcss.config.js                 # PostCSS configuration
│   │   ├── tailwind.config.js                # Tailwind CSS design tokens
│   │   └── tsconfig.json                     # TypeScript compiler settings
│   │
│   └── api/                                  # Self-Contained Python Backend
│       ├── app/
│       │   │
│       │   ├── core/                         # Infrastructure & Cross-Cutting Module
│       │   │   ├── __init__.py               # Core package exports
│       │   │   ├── config.py                 # Pydantic BaseSettings (DB URLs, Redis, Gemini API key)
│       │   │   ├── db.py                     # Async SQLAlchemy engine & session dependency provider
│       │   │   ├── logging.py                # Structured JSON logging configuration
│       │   │   └── security.py               # Password hashing & credential obfuscation helpers
│       │   │
│       │   ├── modules/                      # Feature-Wise Modular Domain Layer
│       │   │   │
│       │   │   ├── users/                    # Feature 1: User & Authentication
│       │   │   │   ├── __init__.py
│       │   │   │   ├── users_models.py       # ORM: User identity database model
│       │   │   │   ├── users_schemas.py      # Schemas: User signup/login Pydantic contracts
│       │   │   │   ├── users_services.py     # Service: Auth, password verification & tenant management
│       │   │   │   └── users_routes.py       # Routes: /api/v1/users and auth HTTP endpoints
│       │   │   │
│       │   │   ├── sources/                  # Feature 2: Data Sources & Connectors
│       │   │   │   ├── sources_connectors/   # Submodule: Database & File Data Connectors
│       │   │   │   │   ├── __init__.py
│       │   │   │   │   ├── sources_connectors_base.py     # Abstract DataConnector interface
│       │   │   │   │   ├── sources_connectors_postgres.py # PostgreSQL connector driver
│       │   │   │   │   ├── sources_connectors_mssql.py    # MSSQL connector driver
│       │   │   │   │   ├── sources_connectors_csv.py      # Polars streaming CSV connector
│       │   │   │   │   ├── sources_connectors_excel.py    # Excel spreadsheet connector
│       │   │   │   │   └── sources_connectors_factory.py  # ConnectorFactory builder
│       │   │   │   ├── __init__.py
│       │   │   │   ├── sources_models.py     # ORM: DataSource & Dataset metadata models
│       │   │   │   ├── sources_schemas.py    # Schemas: Connection request & response DTOs
│       │   │   │   ├── sources_services.py   # Service: Connection testing and source registration
│       │   │   │   └── sources_routes.py     # Routes: /api/v1/sources HTTP endpoints
│       │   │   │
│       │   │   ├── profiler/                 # Feature 3: Memory-Efficient Data Profiling
│       │   │   │   ├── __init__.py
│       │   │   │   ├── profiler_engine.py    # Engine: Chunked sampling & null/unique statistics calculator
│       │   │   │   ├── profiler_models.py    # ORM: DatasetProfileModel metadata persistence
│       │   │   │   ├── profiler_schemas.py   # Schemas: DatasetProfile & ColumnMetadata DTOs
│       │   │   │   ├── profiler_services.py  # Service: Profiling job orchestration
│       │   │   │   └── profiler_routes.py    # Routes: /api/v1/datasets/{table_name}/profile endpoints
│       │   │   │
│       │   │   ├── schema_mapping/           # Feature 4: AI Schema Matching & Recommendations
│       │   │   │   ├── schema_mapping_ai/    # Submodule: AI Reasoning Abstractions
│       │   │   │   │   ├── __init__.py
│       │   │   │   │   ├── schema_mapping_ai_base.py     # Abstract AIProvider interface
│       │   │   │   │   ├── schema_mapping_ai_gemini.py   # Google Gemini provider implementation
│       │   │   │   │   └── schema_mapping_ai_planner.py  # AISchemaPlanner semantic matcher
│       │   │   │   ├── __init__.py
│       │   │   │   ├── schema_mapping_models.py  # ORM: SchemaMappingModel persistence
│       │   │   │   ├── schema_mapping_schemas.py # Schemas: ColumnMappingRule & SchemaMapping DTOs
│       │   │   │   ├── schema_mapping_services.py# Service: Mapping recommendation service
│       │   │   │   └── schema_mapping_routes.py # Routes: /api/v1/mappings endpoints
│       │   │   │
│       │   │   ├── transformation_plans/     # Feature 5: Transformation Plans & Execution Engine
│       │   │   │   ├── transformation_plans_engine/ # Submodule: Deterministic ETL Engine
│       │   │   │   │   ├── __init__.py
│       │   │   │   │   ├── transformation_plans_engine.py    # Polars/DuckDB plan execution class
│       │   │   │   │   └── transformation_plans_operations.py# Operation handlers (rename, trim, cast, deduplicate)
│       │   │   │   ├── __init__.py
│       │   │   │   ├── transformation_plans_models.py  # ORM: TransformationPlanModel persistence
│       │   │   │   ├── transformation_plans_schemas.py # Schemas: TransformationPlan & TransformationOperation specs
│       │   │   │   ├── transformation_plans_services.py# Service: Plan generation & approval workflow
│       │   │   │   └── transformation_plans_routes.py  # Routes: /api/v1/plans endpoints
│       │   │   │
│       │   │   └── execution/                # Feature 6: Execution Dispatcher & Local Script Generation
│       │   │       ├── execution_script_generator/ # Submodule: Local ZIP Package Generator
│       │   │       │   ├── __init__.py
│       │   │       │   └── execution_script_generator.py # Standalone runner ZIP packager
│       │   │       ├── __init__.py
│       │   │       ├── execution_models.py   # ORM: MigrationJobModel & ExecutionLogModel
│       │   │       ├── execution_policy.py   # Policy: Evaluation rules (CLOUD vs LOCAL_SCRIPT)
│       │   │       ├── execution_schemas.py  # Schemas: MigrationJob & ExecutionResult DTOs
│       │   │       ├── execution_services.py # Service: Job dispatcher & script builder
│       │   │       ├── execution_tasks.py    # Tasks: Redis worker background task handlers
│       │   │       └── execution_routes.py   # Routes: /api/v1/jobs & download endpoints
│       │   │
│       │   ├── __init__.py
│       │   └── main.py                       # Main FastAPI App Entry Point & Router Registry
│       │
│       ├── tests/                            # Automated Test Suites
│       │   ├── unit/                         # Unit tests for each feature module
│       │   ├── integration/                  # FastAPI integration & route tests
│       │   └── e2e/                          # End-to-end pipeline stub test
│       │
│       ├── Dockerfile                        # Multi-stage production container for API backend
│       ├── poetry.lock                       # Locked Python dependency versions
│       ├── pyproject.toml                    # Poetry project configuration & dependencies
│       └── README.md                         # Backend module documentation
│
├── infra/                                    # Infrastructure & DevOps Support
│   ├── docker/                               # Production Docker configs
│   └── scripts/                              # Database initialization & deployment scripts
│
├── docs/                                     # System Documentation
│   ├── ai_planner.md
│   ├── api.md
│   ├── connectors.md
│   ├── profiler.md
│   ├── script_generation.md
│   ├── transformation_engine.md
│   └── workers.md
│
├── docker-compose.yml                        # Docker Compose orchestrating web, api, worker, postgres, redis
├── .env.example                              # Environment variable template
├── .gitignore                                # Git ignore configuration
├── ARCHITECTURE.md                           # Comprehensive architecture specification
├── CONTRIBUTING.md                           # Developer contribution guidelines
└── README.md                                 # Monorepo root README
```

---

## 4. What Code Each File Type Must Contain

| File Type / Extension Pattern | Responsibility & Code Contents |
| :--- | :--- |
| `*_models.py` | **SQLAlchemy ORM Models**: Database table definitions (e.g. `User`, `DataSource`, `DatasetProfileModel`, `TransformationPlanModel`). Defines column types, keys, relationships, and metadata persistence. |
| `*_schemas.py` | **Pydantic Schemas & DTOs**: Request/response contracts, API payloads, and strongly typed JSON specifications (e.g. `TransformationPlan`, `ColumnMetadata`, `DataSourceCreate`). |
| `*_services.py` | **Application Services**: Business logic & orchestration between ORM models, domain engines, connectors, and AI modules. |
| `*_routes.py` | **FastAPI Route Handlers**: HTTP route endpoints (e.g., `@router.get("")`, `@router.post("")`). Must remain thin by calling services. |
| `*_engine.py` | **Processing Engines**: High-performance computations (e.g., chunked data profiling or Polars/DuckDB ETL data transformations). |
| `*_connectors/` | **Data Source Drivers**: Abstractions and drivers for reading metadata and streaming batches from database/file sources. |
| `*_ai/` | **AI Providers & Reasoning**: Gemini SDK interactions and AI column matching logic. |
| `*_tasks.py` | **Celery / RQ Worker Tasks**: Asynchronous background jobs executed outside the HTTP request/response loop. |
| `*_policy.py` | **Execution Policy Rules**: Threshold rules evaluating row counts and data size to determine `CLOUD` vs `LOCAL_SCRIPT` mode. |
| `*_script_generator/` | **Package Packager**: Generates downloadable ZIP archives containing `run.py`, `migration_plan.json`, and setup instructions for local execution. |

---

## 5. Quickstart Guide

### Running with Docker Compose (Recommended)

```bash
# 1. Copy environment variables template
cp .env.example .env

# 2. Start all services (Next.js, FastAPI, Worker, Postgres, Redis)
docker compose up --build
```

- **Frontend Application**: `http://localhost:3000`
- **FastAPI Documentation**: `http://localhost:8000/docs`
- **API Health Check**: `http://localhost:8000/api/v1/health`
