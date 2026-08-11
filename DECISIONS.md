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

## [2026-08-11] - Single Source of Truth for Environment Variables

### 1. Decision Summary
Removed redundant [`apps/api/.env`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/apps/api/.env) file and centralized all environment configurations into the root [`.env`](file:///c:/Neel/AI%20DATA%20MIGRATION%20PLATFORM/.env).

### 2. Why This Approach? (Rationale)
- **Eliminates Configuration Drift**: Ensures single source of truth across Docker Compose, Next.js frontend, API backend, workers, and migration scripts.
- **Hierarchical Path Resolution**: Pydantic's `SettingsConfigDict(env_file=(".env", "../.env"))` automatically discovers the root `.env` file when API commands are run inside `apps/api/`.


