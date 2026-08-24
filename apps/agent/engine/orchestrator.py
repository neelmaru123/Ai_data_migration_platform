"""
High-level ETL migration orchestrator module for agent execution engine.
"""

import logging
import os
import re
from typing import Any, Dict
import duckdb

from .checkpoint import CheckpointManager
from .ddl_executor import DDLExecutor
from .progress_reporter import ProgressReporter
from .connectors.source_factory import SourceConnectorFactory
from .transformers.ast_transformer import ASTTransformer
from .staging.duckdb_staging import TableMerger
from .writers.target_writer import TargetWriterFactory

logger = logging.getLogger("docker-agent-execution")


class ExecutionOrchestrator:
    """Main orchestrator executing local ETL migration pipeline for an AST plan."""

    @staticmethod
    def run_job(
        backend_url: str,
        agent_token: str,
        job_id: str,
        plan_ast: Dict[str, Any],
        source_db_urls: Dict[str, str],
        target_db_url: str,
        target_engine_type: str = "postgresql",
    ):
        logger.info(f"=== STARTING LOCAL ETL EXECUTION FOR JOB '{job_id}' ===")
        plan_data = plan_ast.get("plan_data", {})
        pre_ddl = plan_data.get("pre_migration_ddl", [])
        post_ddl = plan_data.get("post_migration_ddl", [])
        table_mappings = plan_data.get("table_mappings", [])

        total_tables = len(table_mappings)
        total_processed = 0
        total_successful = 0
        total_failed = 0
        total_skipped = 0

        total_estimated_rows = 0
        for tm in table_mappings:
            for st in tm.get("source_tables", []):
                total_estimated_rows += int(st.get("row_count", 0) or 0)

        try:
            # Step 1: Pre-Migration DDL
            ProgressReporter.report(
                backend_url, agent_token, job_id, "running", 10.0, 0, 0, 0, 0,
                total_rows=total_estimated_rows, current_stage="pre_ddl"
            )
            DDLExecutor.execute_ddl_list(target_db_url, pre_ddl, "Pre-Migration DDL")

            # Step 2: Data Extraction, AST Transformation, Merge, and Target Loading
            for idx, table_spec in enumerate(table_mappings, start=1):
                target_table = table_spec.get("target_table_name")
                source_tables = table_spec.get("source_tables", [])
                column_mappings = table_spec.get("column_mappings", [])
                conflict_res = table_spec.get("conflict_resolution")

                logger.info(f"Processing table [{idx}/{total_tables}]: '{target_table}'...")
                pct = 10.0 + (float(idx) / float(total_tables) * 80.0)
                ProgressReporter.report(
                    backend_url, agent_token, job_id, "running", pct,
                    total_processed, total_successful, total_failed, total_skipped,
                    total_rows=total_estimated_rows if total_estimated_rows > 0 else (total_processed or 250),
                    current_table=target_table, current_stage="data_streaming"
                )

                staging_conn = None
                staging_db_file = None
                staging_table_name = "staging_data"
                start_seq = 0

                if len(source_tables) > 1:
                    staging_dir = os.getenv("CHECKPOINT_DIR", "/tmp")
                    os.makedirs(staging_dir, exist_ok=True)
                    staging_db_file = os.path.join(staging_dir, f"staging_{job_id}_{target_table}.duckdb")
                    if os.path.exists(staging_db_file):
                        try:
                            os.remove(staging_db_file)
                        except Exception:
                            pass
                    staging_conn = duckdb.connect(staging_db_file)

                try:
                    for src_ref in source_tables:
                        src_ident = src_ref.get("identifier")
                        src_table = src_ref.get("table_name")

                        # Match source DB URL and engine type
                        db_url = None
                        if src_ident:
                            clean_id = str(src_ident).lower().strip()
                            norm_id = re.sub(r'^(src_|dest_|source_|target_)', '', clean_id)

                            # 1. Exact or normalized match
                            for k, v in source_db_urls.items():
                                k_norm = re.sub(r'^(src_|dest_|source_|target_)', '', str(k).lower().strip())
                                if str(k).lower().strip() == clean_id or k_norm == norm_id:
                                    db_url = v
                                    break

                            # 2. Numbered suffix match (e.g. "source_db_2" -> "db_2")
                            if not db_url:
                                id_numbers = re.findall(r'\d+', norm_id)
                                if id_numbers:
                                    target_num = id_numbers[-1]
                                    for k, v in source_db_urls.items():
                                        k_numbers = re.findall(r'\d+', str(k))
                                        if k_numbers and k_numbers[-1] == target_num:
                                            db_url = v
                                            break

                        if not db_url and source_db_urls:
                            db_url = list(source_db_urls.values())[0]

                        src_engine = "postgresql"
                        if db_url:
                            if "mysql" in db_url:
                                src_engine = "mysql"
                            elif "mongo" in db_url:
                                src_engine = "mongodb"
                            elif "sqlite" in db_url:
                                src_engine = "sqlite"

                        # Detect primary key column if available for keyset pagination
                        pk_col = None
                        for col in column_mappings:
                            if col.get("is_primary_key"):
                                src_cols = col.get("source_columns", [])
                                if src_cols and "column_name" in src_cols[0]:
                                    pk_col = src_cols[0]["column_name"]
                                    break

                        if src_engine == "mongodb" and not pk_col:
                            pk_col = "_id"

                        # Resumable Checkpoint offset & cursor
                        offset = CheckpointManager.get_last_offset(job_id, target_table, source_identifier=src_ident, source_table=src_table)
                        last_pk_val = None
                        has_more = True

                        while has_more:
                            df_raw, has_more, next_pk = SourceConnectorFactory.read_source_chunk(
                                db_url=db_url,
                                engine_type=src_engine,
                                table_or_file_name=src_table,
                                offset=offset,
                                chunk_size=50000,
                                pk_col=pk_col,
                                last_pk_val=last_pk_val,
                            )
                            if next_pk is not None:
                                last_pk_val = next_pk

                            if df_raw.is_empty():
                                break

                            logger.info(f"Extracted chunk of {len(df_raw)} rows from source '{src_ident}.{src_table}' (Offset: {offset}).")
                            df_trans, trans_errors = ASTTransformer.transform_chunk(df_raw, column_mappings)
                            total_failed += trans_errors

                            # If single source table, load directly to target (OOM-free streaming)
                            if len(source_tables) == 1:
                                succ, fail, skip = TargetWriterFactory.bulk_load(target_db_url, target_engine_type, target_table, df_trans)
                                total_processed += (succ + fail + skip)
                                total_successful += succ
                                total_failed += fail
                                total_skipped += skip
                            else:
                                start_seq = TableMerger.append_to_duckdb_staging(staging_conn, staging_table_name, df_trans, start_seq)

                            offset += len(df_raw)
                            CheckpointManager.save_checkpoint(job_id, target_table, offset, total_processed, source_identifier=src_ident, source_table=src_table)

                    # For multi-source merges, stream deduplicated results from DuckDB staging area in bounded batches
                    if len(source_tables) > 1 and staging_conn:
                        for chunk_df in TableMerger.stream_deduplicated_chunks(staging_conn, staging_table_name, conflict_res, chunk_size=50000):
                            succ, fail, skip = TargetWriterFactory.bulk_load(target_db_url, target_engine_type, target_table, chunk_df)
                            total_processed += (succ + fail + skip)
                            total_successful += succ
                            total_failed += fail
                            total_skipped += skip

                finally:
                    if staging_conn:
                        try:
                            staging_conn.close()
                        except Exception:
                            pass
                    if staging_db_file and os.path.exists(staging_db_file):
                        try:
                            os.remove(staging_db_file)
                        except Exception:
                            pass

            # Step 3: Post-Migration DDL (Foreign Keys)
            ProgressReporter.report(
                backend_url, agent_token, job_id, "running", 95.0,
                total_processed, total_successful, total_failed, total_skipped,
                total_rows=total_estimated_rows, current_stage="post_ddl"
            )
            DDLExecutor.execute_ddl_list(target_db_url, post_ddl, "Post-Migration DDL")

            # Step 4: Mark Job Complete
            ProgressReporter.report(
                backend_url, agent_token, job_id, "completed", 100.0,
                total_processed, total_successful, total_failed, total_skipped,
                total_rows=total_estimated_rows, current_stage="completed"
            )
            logger.info(f"=== MIGRATION JOB '{job_id}' COMPLETED SUCCESSFULLY! (Processed: {total_processed}, Success: {total_successful}, Failed: {total_failed}, Skipped: {total_skipped}) ===")

        except Exception as exc:
            err_msg = f"Migration job '{job_id}' failed: {exc}"
            logger.error(err_msg, exc_info=True)
            ProgressReporter.report(
                backend_url, agent_token, job_id, "failed", 0.0,
                total_processed, total_successful, total_failed, total_skipped,
                total_rows=total_estimated_rows, current_stage="failed", error_message=err_msg
            )
            raise
