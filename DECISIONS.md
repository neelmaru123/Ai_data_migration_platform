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
- **Future Considerations**:
  - Add **Alembic** schema versioning for platform PostgreSQL metadata tables.
  - Implement partition checkpointing (`last_processed_id`) in `migration_jobs` to support zero-loss resumable task execution after worker crashes.
