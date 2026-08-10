# AI Data Migration Platform — Backend Service Guide (`apps/api`)

The self-contained Python backend service housing the FastAPI application layer, feature-wise domain modules, task handlers, and test suites.

## 1. Tech Stack & Dependencies

- **Language**: Python 3.11+
- **Framework**: FastAPI & Uvicorn
- **Package Manager**: Poetry (`pyproject.toml` & `poetry.lock`)
- **Data Validation**: Pydantic v2 & Pydantic-Settings
- **Database & ORM**: SQLAlchemy v2 (AsyncPG driver for PostgreSQL)
- **Data Processing**: Polars, DuckDB, PyArrow, OpenPyXL
- **Task Queue**: Celery / RQ & Redis
- **AI Engine**: Google Gemini (`google-generativeai`)
- **Testing**: Pytest, Pytest-Asyncio, HTTPX

---

## 2. Feature-Wise Modular Architecture

All code inside `apps/api/app/modules/` is structured feature by feature.

```text
apps/api/
├── app/
│   ├── core/                                     # Core infrastructure (config, db, logging, security)
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── logging.py
│   │   └── security.py
│   │
│   ├── modules/                                 # Feature-Wise Modular Domain Layer
│   │   │
│   │   ├── users/                               # User & Auth Feature
│   │   │   ├── users_models.py                  # ORM: User model
│   │   │   ├── users_schemas.py                 # Schemas: User signup/login Pydantic models
│   │   │   ├── users_services.py                # Service: Password verification & user management
│   │   │   └── users_routes.py                  # Routes: /api/v1/users endpoints
│   │   │
│   │   ├── sources/                             # Data Sources & Connectors Feature
│   │   │   ├── sources_connectors/              # Drivers: Postgres, MSSQL, CSV, Excel & Factory
│   │   │   ├── sources_models.py                # ORM: DataSource & Dataset models
│   │   │   ├── sources_schemas.py               # Schemas: Connection DTOs
│   │   │   ├── sources_services.py              # Service: Source registration & connection testing
│   │   │   └── sources_routes.py                # Routes: /api/v1/sources endpoints
│   │   │
│   │   ├── profiler/                            # Data Profiling Feature
│   │   │   ├── profiler_engine.py               # Engine: Sampling & statistics calculator
│   │   │   ├── profiler_models.py               # ORM: DatasetProfileModel
│   │   │   ├── profiler_schemas.py              # Schemas: DatasetProfile & ColumnMetadata DTOs
│   │   │   ├── profiler_services.py             # Service: Profiling job orchestration
│   │   │   └── profiler_routes.py               # Routes: /api/v1/datasets/{table}/profile endpoints
│   │   │
│   │   ├── schema_mapping/                      # AI Schema Matching Feature
│   │   │   ├── schema_mapping_ai/               # AI Drivers: Gemini provider & planner
│   │   │   ├── schema_mapping_models.py         # ORM: SchemaMappingModel
│   │   │   ├── schema_mapping_schemas.py        # Schemas: ColumnMappingRule & SchemaMapping DTOs
│   │   │   ├── schema_mapping_services.py       # Service: AI mapping recommendation
│   │   │   └── schema_mapping_routes.py        # Routes: /api/v1/mappings endpoints
│   │   │
│   │   ├── transformation_plans/                # Transformation Plans & ETL Engine Feature
│   │   │   ├── transformation_plans_engine/     # Engine: Polars/DuckDB ETL plan runner & ops
│   │   │   ├── transformation_plans_models.py   # ORM: TransformationPlanModel
│   │   │   ├── transformation_plans_schemas.py  # Schemas: TransformationPlan & Operation specs
│   │   │   ├── transformation_plans_services.py # Service: Plan generation & approval workflow
│   │   │   └── transformation_plans_routes.py   # Routes: /api/v1/plans endpoints
│   │   │
│   │   └── execution/                           # Job Execution & Script Generator Feature
│   │       ├── execution_script_generator/      # Generator: Standalone ZIP package generator
│   │       ├── execution_models.py              # ORM: MigrationJobModel & ExecutionLogModel
│   │       ├── execution_policy.py              # Policy: Execution mode decision rules
│   │       ├── execution_schemas.py             # Schemas: MigrationJob DTOs
│   │       ├── execution_services.py            # Service: Job dispatcher & package builder
│   │       ├── execution_tasks.py               # Tasks: Worker task handlers
│   │       └── execution_routes.py              # Routes: /api/v1/jobs & download endpoints
│   │
│   └── main.py                                  # Application Entry Point & Module Router Registry
│
├── tests/                                       # Test Suites (unit, integration, e2e)
├── Dockerfile                                   # Multi-stage production container
└── pyproject.toml                               # Poetry dependency manager configuration
```

---

## 3. What Code Each File Contains

- `*_models.py`: SQLAlchemy ORM database table definitions.
- `*_schemas.py`: Pydantic DTOs for request payloads, responses, and JSON specs.
- `*_services.py`: Application orchestration services connecting models, engines, and APIs.
- `*_routes.py`: FastAPI HTTP endpoint declarations.
- `*_engine.py` / `*_engine/`: High-performance computing routines for profiling and Polars/DuckDB ETL operations.
- `*_connectors/`: Database & file storage reader abstractions.
- `*_ai/`: Gemini foundation model integration & structured prompt generation.
- `*_tasks.py`: Asynchronous Redis background worker tasks.
- `*_script_generator/`: Self-contained runnable Python ZIP packager.
