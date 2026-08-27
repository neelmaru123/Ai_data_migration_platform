# On-Premise Docker Agent Daemon (`apps/agent`)

The `apps/agent` package is a standalone, customer-hosted Docker runner designed for secure, air-gapped data migration operations inside customer VPCs. It executes zero-raw-data-cloud transfers by carrying out database introspection, data streaming, AST transformations, local DuckDB staging, and bulk target database loading entirely on-premise.

---

## 1. Directory & Component Inventory

| File / Subfolder | Category | Description |
| :--- | :--- | :--- |
| `main.py` | Daemon Entry Point | Daemon loop managing environment token auto-registration, background heartbeat pings, 20s task polling, and signals (`SIGINT`/`SIGTERM`) |
| `metadata_engine.py` | Introspection Engine | On-premise schema introspection scanning PostgreSQL, MySQL, SQLite, and MongoDB document sampling (capped at top 500 tables by row count) |
| `execution_engine.py` | ETL Orchestrator | Core ETL execution pipeline including `DDLExecutor`, `TableMerger`, `TargetWriterFactory`, `CheckpointManager`, and `ProgressReporter` |
| `engine/checkpoint.py` | State Resumability | Manages chunk-level checkpoint savepoints (`checkpoint_*.json`) and post-job cleanup (`clear_job_checkpoints`) |
| `engine/orchestrator.py` | Task Orchestrator | `ExecutionOrchestrator.run_job` executing pre-DDL, data streaming, DuckDB staging startup cleanup, and post-DDL foreign key execution |
| `engine/connectors/source_factory.py` | Data Readers | `SourceConnectorFactory` reading chunks via Keyset Pagination or Offset fallback (with non-PK warning logs and engine dialect validation) |
| `engine/transformers/ast_transformer.py` | Polars/DuckDB Engine | `ASTTransformer` applying column transformations, PK resolution, DuckDB expression sanitization against SQL DDL/DML, and decimal precision casting |
| `engine/writers/target_writer.py` | Target Sinks | `TargetWriterFactory` executing bulk inserts for Postgres, MySQL, and MongoDB (enclosing Postgres `session_replication_role` in `try...finally`) |

---

## 2. Core Capabilities & Architectural Safeguards

### 1. Zero Raw Data Cloud Transfer
All extraction, transformation, multi-database merging, and target insertion execute 100% inside the customer's local network. Only structural schema ASTs and progress row counts are transmitted to the Control Plane.

### 2. Multi-Source Staging & Bounded RAM Footprint (`staging_*.duckdb`)
- When merging data from multiple source databases (e.g., combining `PostgreSQL.users` and `MySQL.legacy_users` into a single target table), transformed chunks are written to a temporary local DuckDB file (`staging_{job_id}_{table}.duckdb`).
- Extracted Polars DataFrames are immediately discarded from Python memory. Vectorized SQL deduplication runs out of DuckDB, keeping peak RAM consumption bounded to 1 chunk (~50,000 rows) regardless of dataset size.
- Startup cleanup routine automatically purges stale `staging_*.duckdb` files on container restart.

### 3. Keyset Pagination & Primary Key Safeguards
- SQL source connectors stream data using Keyset Pagination (`WHERE pk > :last_pk ORDER BY pk ASC`).
- If a source table lacks a primary key, `SourceConnectorFactory` falls back to `OFFSET` pagination and issues an explicit warning log alerting DBAs to potential offset drift during live writes.

### 4. Expression Sanitization & Decimal Precision
- Custom LLM transformation expressions in `ASTTransformer` are sanitized via regex inspection against dangerous SQL DDL/DML keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `COPY`, `ATTACH`, `TRUNCATE`, `ALTER`).
- High-precision `decimal`/`numeric` columns are preserved as `pl.Utf8` string representations to prevent micro-precision floating point rounding errors.

### 5. PostgreSQL Session Scope Reset
- PostgreSQL target writer disables foreign keys and triggers during streaming using `SET session_replication_role = 'replica'`.
- Enclosed inside a `try...finally` block to guarantee `SET session_replication_role = 'origin'` executes before releasing pooled database connections back to the pool.

### 6. Decoupled Heartbeat Thread & Deterministic Target DB Selection
- Background daemon thread (`start_heartbeat_thread`) fires heartbeats every 20 seconds independently of heavy ETL processing, preventing false offline container statuses.
- Deterministically sorts container environment keys matching `DEST_*` alphabetically and picks the primary target URL, issuing warning logs when extra destination DBs exist.

---

## 3. Execution Command & Environment Configuration

### Docker Command Syntax
```bash
docker run -d \
  --name ai-migration-agent \
  -e BACKEND_URL="http://localhost:8000" \
  -e AGENT_TOKEN="ag_live_..." \
  -e USER_EMAIL="user@example.com" \
  -e USER_PASSWORD="SecurePassword123" \
  -e SRC_DB_1_URL="postgresql://user:pass@host:5432/db1" \
  -e DEST_DB_1_URL="postgresql://user:pass@host:5432/dest_db" \
  --add-host=host.docker.internal:host-gateway \
  neelmaru123/ai-data-migration-agent:latest
```
