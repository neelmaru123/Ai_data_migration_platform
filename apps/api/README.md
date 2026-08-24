# AI Data Migration Platform — Backend Service Guide (`apps/api`)

The self-contained Python backend service housing the FastAPI application layer, feature-wise domain modules, task handlers, and test suites.

## 1. Tech Stack & Dependencies

- **Language**: Python 3.11+
- **Framework**: FastAPI & Uvicorn (ASGI)
- **Package Manager**: Poetry (`pyproject.toml` & `poetry.lock`)
- **Data Validation**: Pydantic v2 & Pydantic-Settings
- **Database & ORM**: SQLAlchemy v2 (AsyncPG driver for PostgreSQL, SQLite for unit tests)
- **Data Processing**: Polars, DuckDB, PyArrow, OpenPyXL
- **Task Queue**: Celery / RQ & Redis
- **AI Engine**: Google Gemini (`google-generativeai` & `langchain-google-genai`)
- **Stateful AI Graph**: LangGraph (`langgraph`)
- **Testing**: Pytest, Pytest-Asyncio, HTTPX

---

## 2. Feature-Wise Modular Architecture

All domain features inside `apps/api/app/modules/` are structured module by module:

```text
apps/api/
├── app/
│   ├── core/                                     # Core infrastructure (config, db, logging, security, websocket)
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── logging.py
│   │   ├── security.py
│   │   └── websocket_manager.py
│   │
│   ├── modules/                                 # Feature-Wise Modular Domain Layer
│   │   │
│   │   ├── users/                               # User & Auth Feature (JWT, OAuth 2.0, Cookies)
│   │   │   ├── users_models.py
│   │   │   ├── users_schemas.py
│   │   │   ├── users_services.py
│   │   │   └── users_routes.py
│   │   │
│   │   ├── agents/                              # Docker Agent Management & Docker Commands Feature
│   │   │   ├── agents_models.py
│   │   │   ├── agents_schemas.py
│   │   │   ├── agents_services.py
│   │   │   ├── agents_command_generator.py
│   │   │   └── agents_routes.py
│   │   │
│   │   ├── sources/                             # Data Sources & File Loaders Feature
│   │   │   ├── sources_connectors/              # Postgres, MySQL, MongoDB drivers & factory
│   │   │   ├── sources_loaders/                 # CSV & Excel streaming loaders
│   │   │   ├── sources_models.py
│   │   │   ├── sources_schemas.py
│   │   │   ├── sources_services.py
│   │   │   └── sources_routes.py
│   │   │
│   │   ├── metadata/                            # Catalog Introspection & Snapshot Storage Feature
│   │   │   ├── metadata_models.py
│   │   │   ├── metadata_schemas.py
│   │   │   ├── metadata_services.py
│   │   │   └── metadata_routes.py
│   │   │
│   │   ├── migration_plans/                     # AI Blueprinting & LangGraph Validation Feature
│   │   │   ├── migration_plans_engine/          # LangGraph graph, validator & Gemini LLM planner
│   │   │   ├── migration_plans_models.py
│   │   │   ├── migration_plans_schemas.py
│   │   │   ├── migration_plans_services.py
│   │   │   └── migration_plans_routes.py
│   │   │
│   │   └── execution/                           # Migration Job Execution & Telemetry Feature
│   │       ├── execution_models.py
│   │       ├── execution_schemas.py
│   │       ├── execution_services.py
│   │       └── execution_routes.py
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
- `*_engine/`: High-performance computing routines for schema validation, LangGraph workflows, and Gemini LLM prompt generation.
- `*_connectors/`: Database & file storage reader abstractions.
