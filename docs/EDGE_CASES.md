# Migration Platform Edge-Case hardening Catalog (`EDGE_CASES.md`)

This document serves as the canonical living reference cataloging every edge case identified, hardened, and verified across the **AI Data Migration Platform** architecture.

---

## Edge Case Catalog (Fixes 1 – 12)

| Fix # | Problem Summary | Status | Files Changed | Guarding Unit Test |
| :--- | :--- | :--- | :--- | :--- |
| **Fix 1** | Multi-source merge checkpoint keying collisions causing row skipping. | **Fixed** | [`execution_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/execution_engine.py) | [`test_bug_multisource_checkpoint_key_isolation.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_multisource_checkpoint_key_isolation.py) |
| **Fix 2** | Multi-source merge memory growth and OOM crashes on large datasets. | **Fixed** | [`execution_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/execution_engine.py) | [`test_bug_multisource_merge_streaming.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_multisource_merge_streaming.py) |
| **Fix 3** | DB write outcome verification ignoring SQL conflict skips and Mongo errors. | **Fixed** | [`execution_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/execution_engine.py), [`execution_schemas.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_schemas.py) | [`test_bug_db_write_outcome_verification.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_db_write_outcome_verification.py) |
| **Fix 4** | Synchronous agent loop causing false offline/degraded status during ETL jobs. | **Fixed** | [`main.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/main.py) | [`test_bug_decouple_agent_heartbeats.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_decouple_agent_heartbeats.py) |
| **Fix 5** | Unlocked task polling allowing race conditions and duplicate job execution. | **Fixed** | [`execution_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_services.py) | [`test_bug_atomic_job_claiming.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_atomic_job_claiming.py) |
| **Fix 6** | Uncaught agent execution errors and container crashes leaving frozen progress bars. | **Fixed** | [`execution_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/execution_engine.py), [`execution_services.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/execution/execution_services.py) | [`test_bug_uncaught_execution_errors_and_watchdog.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_uncaught_execution_errors_and_watchdog.py) |
| **Fix 7** | Missing PK strategies falling back to UUID v5 and missing FK rekey warnings. | **Fixed** | [`execution_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/execution_engine.py), [`migration_plans_validator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_engine/migration_plans_validator.py) | [`test_bug_pk_conflict_resolution_strategies.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_pk_conflict_resolution_strategies.py) |
| **Fix 8** | Mongo extraction skip/limit offset drift during concurrent live writes. | **Fixed** | [`execution_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/execution_engine.py) | [`test_bug_mongo_keyset_pagination.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_mongo_keyset_pagination.py) |
| **Fix 9** | Un-sampled MongoDB fields missing from explicit AST dropped at execution time. | **Fixed** | [`execution_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/execution_engine.py) | [`test_bug_mongo_residual_field_capture.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_mongo_residual_field_capture.py) |
| **Fix 10** | Divergent Mongo introspection sampling and path flattening between API and Agent. | **Fixed** | [`sources_connectors_mongodb.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/sources/sources_connectors/sources_connectors_mongodb.py), [`metadata_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/metadata_engine.py) | [`test_bug_reconcile_mongo_introspection.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_reconcile_mongo_introspection.py) |
| **Fix 11** | SQL DDL error swallowing, hardcoded MySQL row count 0, unreachable abort threshold for small tables, unvalidated column collisions, and `merge_concat` length overflow. | **Fixed** | [`execution_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/execution_engine.py), [`metadata_engine.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/agent/metadata_engine.py), [`migration_plans_validator.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_engine/migration_plans_validator.py) | [`test_bug_fix11_ddl_and_sql_correctness.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_fix11_ddl_and_sql_correctness.py) |
| **Fix 12** | Shallow dictionary merge in `process_manual_edits_node` wiping out unedited tables. | **Fixed** | [`migration_plans_graph.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/app/modules/migration_plans/migration_plans_engine/migration_plans_graph.py) | [`test_bug_fix12_manual_edits_structural_merge.py`](file:///d:/GitHub/Ai_data_migration_platform/apps/api/tests/unit/test_bug_fix12_manual_edits_structural_merge.py) |

---

## Technical Edge-Case Details

### 1. Checkpoint Key Isolation (Fix 1)
- **Root Cause**: `CheckpointManager.get_checkpoint_path` used `checkpoint_{job_id}_{table_name}.json`.
- **Hardening**: Keys are now source-scoped: `checkpoint_{job_id}_{table_name}_{source_identifier}_{source_table}.json` with backward-compatibility fallback.

### 2. DuckDB Bounded Multi-Source Merges (Fix 2)
- **Root Cause**: Polars DataFrames were stored in an in-memory `List[pl.DataFrame]`.
- **Hardening**: Appends incoming chunks to DuckDB on disk (`staging_{job_id}_{target_table}.duckdb`) and streams deduplicated final chunks in bounded batches (~50k rows).

### 3. Verified Write Counts & Conflict Skip Reporting (Fix 3)
- **Root Cause**: Bulk write assumed `len(rows)` was inserted regardless of `ON CONFLICT DO NOTHING` rowcount.
- **Hardening**: Evaluates SQL `result.rowcount` and Mongo `BulkWriteError.details["writeErrors"]` to compute `successful_rows`, `failed_rows`, and `skipped_rows` explicitly.

### 4. Background Heartbeat Daemon (Fix 4)
- **Root Cause**: Main agent thread ran `poll_and_execute_tasks` inline, blocking heartbeats during ETL runs.
- **Hardening**: Heartbeats run in a dedicated `threading.Thread(daemon=True)` controlled by `stop_event`.

### 5. Atomic Job Claiming (Fix 5)
- **Root Cause**: Unlocked SELECT permitted multiple agent processes to claim the same queued job.
- **Hardening**: Uses `SELECT ... FOR UPDATE SKIP LOCKED` and transitions status to `preparing` within the same transaction.

### 6. Uncaught Execution Errors & Stale Watchdog (Fix 6)
- **Root Cause**: Agent container crashes left jobs stuck in `running` status forever.
- **Hardening**: Agent dispatches `status="failed"` progress report on exception; backend watchdog (`ExecutionService.check_stale_jobs`) fails jobs updated > 5 minutes ago.

### 7. Primary Key Conflict Strategies (Fix 7)
- **Root Cause**: Fall-through to UUID v5 ignored `keep_original` and `autoincrement_offset`.
- **Hardening**: Implemented `keep_original` (type cast), `autoincrement_offset` ($10^9 \times \text{src\_idx}$), `prefix_id`, `uuid_v4_rekey`. Emits Stage E FK rekey warning.

### 8. Mongo Keyset Pagination (Fix 8)
- **Root Cause**: `.skip(offset).limit(chunk_size)` caused row skipping when concurrent writes occurred.
- **Hardening**: Uses `_id`-based keyset pagination `find({"_id": {"$gt": last_id}}).sort("_id", 1)` and persists `next_pk` in checkpoints.

### 9. Residual Unmapped Field Capture (Fix 9)
- **Root Cause**: Dynamic Mongo fields missing from explicit AST mappings were discarded.
- **Hardening**: `ASTTransformer.transform_chunk` inspects unmapped document keys and serializes them into a catch-all `extra_attributes` JSON column.

### 10. Reconciled Mongo Introspection (Fix 10)
- **Root Cause**: API connector sampled 10 docs without path flattening, creating schema discrepancies with Agent metadata engine.
- **Hardening**: Reconciled API connector to sample 100 docs with depth-3 recursive path flattening and majority-vote type resolution.

### 11. SQL Gaps & Proportional Abort Safeguards (Fix 11)
- **Root Cause**: DDLExecutor swallowed genuine DDL syntax/permission errors; small tables (<1,000 rows) could not trigger 50% failure abort.
- **Hardening**: Raised exceptions on genuine DDL errors; evaluated per-row fallback abort threshold against `min(1000, max(5, len(rows) // 2))`; added target column collision error and `merge_concat` length overflow warning checks.

### 12. Structural AST Manual Edits Merge (Fix 12)
- **Root Cause**: `{**current_ast, **manual_edits}` replaced the entire `table_mappings` list on partial UI edit payloads.
- **Hardening**: Implemented deep structural identity merge matching `table_mappings` by `target_table_name` and `column_mappings` by `target_column_name`.
