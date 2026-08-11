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

