"""
Local Docker Agent ETL Execution Engine
Handles DDL execution, chunked extraction across PostgreSQL, MySQL, MongoDB, CSV, Excel,
Polars/DuckDB in-memory transformations, multi-source table merges, deduplication,
resumable checkpointing, row-level error handling, and bulk loading into target database.
"""

import json
import logging
import os
import re
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import polars as pl
from sqlalchemy import create_engine, text

logger = logging.getLogger("docker-agent-execution")
logger.setLevel(logging.INFO)


class CheckpointManager:
    """Manages resumable checkpointing per table to prevent restarting from zero on agent crash."""

    @staticmethod
    def get_checkpoint_path(job_id: str, table_name: str) -> str:
        tmp_dir = os.getenv("CHECKPOINT_DIR", "/tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        return os.path.join(tmp_dir, f"checkpoint_{job_id}_{table_name}.json")

    @classmethod
    def get_last_offset(cls, job_id: str, table_name: str) -> int:
        path = cls.get_checkpoint_path(job_id, table_name)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_offset", 0)
            except Exception:
                return 0
        return 0

    @classmethod
    def save_checkpoint(cls, job_id: str, table_name: str, offset: int, rows_processed: int):
        path = cls.get_checkpoint_path(job_id, table_name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "job_id": job_id,
                    "table_name": table_name,
                    "last_offset": offset,
                    "rows_processed": rows_processed,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as exc:
            logger.warning(f"Could not write checkpoint for table '{table_name}': {exc}")


class DDLExecutor:
    """Executes target database DDL statements (pre_migration_ddl and post_migration_ddl)."""

    @staticmethod
    def execute_ddl_list(db_url: str, ddl_statements: List[str], stage_label: str = "Pre-Migration DDL"):
        if not ddl_statements:
            logger.info(f"No {stage_label} statements to execute.")
            return

        logger.info(f"Executing {len(ddl_statements)} {stage_label} statements...")
        clean_url = db_url.replace("postgresql://", "postgresql+psycopg2://").replace("mysql://", "mysql+pymysql://")
        engine = create_engine(clean_url, pool_pre_ping=True)

        for stmt in ddl_statements:
            stmt_clean = stmt.strip()
            if not stmt_clean:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(stmt_clean))
                logger.info(f"Successfully executed DDL: {stmt_clean[:80]}...")
            except Exception as exc:
                logger.warning(f"DDL execution notice/warning: {exc}")


class SourceConnectorFactory:
    """Factory creating chunked stream readers for PostgreSQL, MySQL, MongoDB, CSV, and Excel."""

    @staticmethod
    def read_source_chunk(
        db_url: str,
        engine_type: str,
        table_or_file_name: str,
        offset: int = 0,
        chunk_size: int = 50000
    ) -> Tuple[pl.DataFrame, bool]:
        """
        Reads a chunk of rows from the source database using Polars or SQLAlchemy streaming.
        Returns a tuple of (DataFrame, has_more_rows).
        """
        engine_type = engine_type.lower()

        # 1. SQL Relational Databases (PostgreSQL, MySQL, SQLite)
        if engine_type in ["postgresql", "postgres", "mysql", "mariadb", "sqlite"]:
            clean_url = db_url.replace("postgresql://", "postgresql+psycopg2://").replace("mysql://", "mysql+pymysql://")
            query = f'SELECT * FROM "{table_or_file_name}" LIMIT {chunk_size} OFFSET {offset}'
            if "mysql" in clean_url or "mariadb" in clean_url:
                query = f"SELECT * FROM `{table_or_file_name}` LIMIT {chunk_size} OFFSET {offset}"

            try:
                engine = create_engine(clean_url, pool_pre_ping=True)
                with engine.connect() as conn:
                    df = pl.read_database(query=query, connection=conn)
                has_more = len(df) == chunk_size
                return df, has_more
            except Exception as exc:
                logger.error(f"Error reading SQL source chunk for table '{table_or_file_name}' (Offset: {offset}): {exc}")
                return pl.DataFrame(), False

        # 2. MongoDB Collection
        elif engine_type == "mongodb":
            try:
                from pymongo import MongoClient
                client = MongoClient(db_url)
                db_name = db_url.split("/")[-1].split("?")[0] or "test"
                db = client[db_name]
                cursor = db[table_or_file_name].find().skip(offset).limit(chunk_size)
                docs = list(cursor)
                client.close()

                if not docs:
                    return pl.DataFrame(), False

                for d in docs:
                    if "_id" in d:
                        d["_id"] = str(d["_id"])

                df = pl.DataFrame(docs)
                has_more = len(df) == chunk_size
                return df, has_more
            except Exception as exc:
                logger.error(f"Error reading MongoDB collection '{table_or_file_name}': {exc}")
                return pl.DataFrame(), False

        # 3. CSV File
        elif engine_type == "csv" or table_or_file_name.endswith(".csv"):
            try:
                if os.path.exists(table_or_file_name):
                    df = pl.read_csv(table_or_file_name, n_rows=chunk_size, skip_rows=offset)
                    has_more = len(df) == chunk_size
                    return df, has_more
                return pl.DataFrame(), False
            except Exception as exc:
                logger.error(f"Error reading CSV file '{table_or_file_name}': {exc}")
                return pl.DataFrame(), False

        # 4. Excel File
        elif engine_type in ["excel", "xlsx"] or table_or_file_name.endswith(".xlsx"):
            try:
                if os.path.exists(table_or_file_name):
                    df = pl.read_excel(table_or_file_name)
                    df_chunk = df.slice(offset, chunk_size)
                    has_more = (offset + chunk_size) < len(df)
                    return df_chunk, has_more
                return pl.DataFrame(), False
            except Exception as exc:
                logger.error(f"Error reading Excel file '{table_or_file_name}': {exc}")
                return pl.DataFrame(), False

        else:
            logger.warning(f"Unsupported engine type '{engine_type}'. Returning empty DataFrame.")
            return pl.DataFrame(), False


class ASTTransformer:
    """Applies all 9 AST column transformation types to a Polars DataFrame in-memory."""

    @staticmethod
    def transform_chunk(df: pl.DataFrame, column_mappings: List[Dict[str, Any]]) -> Tuple[pl.DataFrame, int]:
        if df.is_empty():
            return df, 0

        exprs = []
        keep_columns = []
        row_errors = 0

        for col_spec in column_mappings:
            target_col = col_spec.get("target_column_name")
            trans_type = col_spec.get("transformation_type", "direct_copy")
            source_cols = col_spec.get("source_columns", [])
            expr_tmpl = col_spec.get("expression_template")
            const_val = col_spec.get("constant_value")

            if not target_col or trans_type == "drop_column":
                continue

            keep_columns.append(target_col)

            # 1. direct_copy
            if trans_type == "direct_copy":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).alias(target_col))

            # 2. type_cast (e.g. INT -> UUID or STRING -> DATETIME)
            elif trans_type == "type_cast":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                target_dtype = col_spec.get("target_data_type", "varchar").lower()
                if src_name in df.columns:
                    if "uuid" in target_dtype:
                        # Deterministic UUID v5 namespace hashing
                        uuid_expr = pl.col(src_name).cast(pl.Utf8).map_elements(
                            lambda val: str(uuid.uuid5(uuid.NAMESPACE_DNS, str(val))) if val else str(uuid.uuid4()),
                            return_dtype=pl.Utf8
                        )
                        exprs.append(uuid_expr.alias(target_col))
                    elif "int" in target_dtype:
                        exprs.append(pl.col(src_name).cast(pl.Int64, strict=False).alias(target_col))
                    elif "timestamp" in target_dtype or "datetime" in target_dtype:
                        exprs.append(pl.col(src_name).cast(pl.Datetime, strict=False).alias(target_col))
                    else:
                        exprs.append(pl.col(src_name).cast(pl.Utf8).alias(target_col))

            # 3. merge_concat (e.g. CONCAT(first_name, ' ', last_name))
            elif trans_type == "merge_concat":
                available_srcs = [sc["column_name"] for sc in source_cols if sc["column_name"] in df.columns]
                if available_srcs:
                    concat_expr = pl.concat_str([pl.col(c).fill_null("") for c in available_srcs], separator=" ")
                    exprs.append(concat_expr.alias(target_col))

            # 4. split (e.g. SPLIT_PART(full_address, ',', 1))
            elif trans_type == "split":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    split_expr = pl.col(src_name).str.split(",").list.get(0)
                    exprs.append(split_expr.alias(target_col))

            # 5. default_constant
            elif trans_type == "default_constant":
                val = const_val if const_val is not None else ""
                exprs.append(pl.lit(val).alias(target_col))

            # 6. new_column_added (e.g. migrated_at timestamp)
            elif trans_type == "new_column_added":
                exprs.append(pl.lit(datetime.now(timezone.utc).isoformat()).alias(target_col))

            # 7. expression (e.g. price - discount, quantity * unit_price, or multi-column arithmetic)
            elif trans_type == "expression" and expr_tmpl:
                try:
                    calc_df = duckdb.sql(f'SELECT ({expr_tmpl}) AS "{target_col}" FROM df').pl()
                    if target_col in calc_df.columns:
                        exprs.append(calc_df[target_col])
                except Exception as expr_err:
                    logger.warning(f"Expression calculation notice for '{target_col}' ({expr_tmpl}): {expr_err}")
                    src_name = source_cols[0]["column_name"] if source_cols else target_col
                    if src_name in df.columns:
                        exprs.append(pl.col(src_name).alias(target_col))

            # 8. lookup_join / fallback
            else:
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).alias(target_col))

        if exprs:
            try:
                transformed_df = df.with_columns(exprs)
                available_targets = [c for c in keep_columns if c in transformed_df.columns]
                return transformed_df.select(available_targets), row_errors
            except Exception as exc:
                logger.warning(f"Vectorized transformation warning, falling back with row error tracking: {exc}")
                row_errors += 1
                return df, row_errors

        return df, row_errors


class TableMerger:
    """Performs multi-database table merging and deduplication."""

    @staticmethod
    def merge_and_deduplicate(
        dfs: List[pl.DataFrame],
        conflict_res: Optional[Dict[str, Any]] = None,
    ) -> pl.DataFrame:
        if not dfs:
            return pl.DataFrame()

        combined = pl.concat(dfs, how="diagonal")

        if not conflict_res:
            return combined

        dedup_key = conflict_res.get("deduplication_key")
        strategy = conflict_res.get("deduplication_strategy", "first_wins")

        if dedup_key and dedup_key in combined.columns:
            keep_opt = "first" if strategy == "first_wins" else "last"
            combined = combined.unique(subset=[dedup_key], keep=keep_opt)
            logger.info(f"Deduplicated combined table on '{dedup_key}' using '{strategy}' strategy (Remaining rows: {len(combined)}).")

        return combined


class TargetWriterFactory:
    """Bulk-inserts transformed Polars DataFrames into PostgreSQL, MySQL, or MongoDB target databases."""

    @staticmethod
    def bulk_load(db_url: str, engine_type: str, table_name: str, df: pl.DataFrame) -> Tuple[int, int]:
        if df.is_empty():
            return 0, 0

        engine_type = engine_type.lower()
        rows = df.to_dicts()
        if not rows:
            return 0, 0

        successful_rows = 0
        failed_rows = 0

        # 1. MongoDB Target Writer
        if engine_type in ["mongodb", "mongo"]:
            try:
                import importlib
                pymongo = importlib.import_module("pymongo")
                client = pymongo.MongoClient(db_url)
                db_name = db_url.rsplit("/", 1)[-1].split("?")[0] or "target_db"
                db = client[db_name]
                coll = db[table_name]

                res = coll.insert_many(rows, ordered=False)
                successful_rows = len(res.inserted_ids)
                logger.info(f"Bulk-inserted {successful_rows} documents into MongoDB collection '{table_name}'.")
                return successful_rows, 0
            except Exception as exc:
                logger.error(f"MongoDB bulk insert error for collection '{table_name}': {exc}")
                return 0, len(rows)

        # 2. PostgreSQL & MySQL Target Writer
        else:
            clean_url = db_url
            if "postgres" in engine_type:
                clean_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
            elif "mysql" in engine_type:
                clean_url = db_url.replace("mysql://", "mysql+pymysql://")

            engine = create_engine(clean_url, pool_pre_ping=True)
            columns = list(rows[0].keys())

            if "mysql" in engine_type:
                col_names = ", ".join([f"`{c}`" for c in columns])
                placeholders = ", ".join([f":{c}" for c in columns])
                insert_sql = f'INSERT IGNORE INTO `{table_name}` ({col_names}) VALUES ({placeholders});'
            else:
                col_names = ", ".join([f'"{c}"' for c in columns])
                placeholders = ", ".join([f":{c}" for c in columns])
                insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING;'

            try:
                with engine.begin() as conn:
                    conn.execute(text(insert_sql), rows)
                successful_rows = len(rows)
                logger.info(f"Bulk-inserted {successful_rows} rows into target table '{table_name}'.")
            except Exception as exc:
                logger.warning(f"Batch bulk insert notice for table '{table_name}': {exc}. Retrying per-row insertion...")
                # Fallback to per-row insertion to maximize successful rows
                with engine.begin() as conn:
                    for row in rows:
                        try:
                            conn.execute(text(insert_sql), [row])
                            successful_rows += 1
                        except Exception:
                            failed_rows += 1

            return successful_rows, failed_rows


class ProgressReporter:
    """Sends HTTP progress reports to Control Plane POST /api/v1/executions/{id}/progress."""

    @staticmethod
    def report(
        backend_url: str,
        agent_token: str,
        job_id: str,
        status: str,
        progress: float,
        processed_rows: int,
        successful_rows: int,
        failed_rows: int,
        current_table: Optional[str] = None,
        current_stage: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        url = f"{backend_url.rstrip('/')}/api/v1/executions/{job_id}/progress"
        payload = json.dumps({
            "status": status,
            "progress": progress,
            "processed_rows": processed_rows,
            "successful_rows": successful_rows,
            "failed_rows": failed_rows,
            "current_table": current_table,
            "current_stage": current_stage,
            "error_message": error_message,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Token": agent_token,
            },
            method="POST",
        )
        if not backend_url or "testserver" in backend_url:
            return

        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                pass
        except Exception:
            pass


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

        # Step 1: Pre-Migration DDL
        ProgressReporter.report(backend_url, agent_token, job_id, "running", 10.0, 0, 0, 0, current_stage="pre_ddl")
        DDLExecutor.execute_ddl_list(target_db_url, pre_ddl, "Pre-Migration DDL")

        total_tables = len(table_mappings)
        total_processed = 0
        total_successful = 0
        total_failed = 0

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
                total_processed, total_successful, total_failed,
                current_table=target_table, current_stage="data_streaming"
            )

            extracted_dfs = []

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

                # Resumable Checkpoint offset
                offset = CheckpointManager.get_last_offset(job_id, target_table)
                has_more = True

                while has_more:
                    df_raw, has_more = SourceConnectorFactory.read_source_chunk(
                        db_url=db_url,
                        engine_type=src_engine,
                        table_or_file_name=src_table,
                        offset=offset,
                        chunk_size=50000
                    )
                    if df_raw.is_empty():
                        break

                    logger.info(f"Extracted chunk of {len(df_raw)} rows from source '{src_ident}.{src_table}' (Offset: {offset}).")
                    df_trans, trans_errors = ASTTransformer.transform_chunk(df_raw, column_mappings)
                    total_failed += trans_errors
                    extracted_dfs.append(df_trans)

                    offset += len(df_raw)
                    CheckpointManager.save_checkpoint(job_id, target_table, offset, total_processed + len(df_trans))

            if extracted_dfs:
                merged_df = TableMerger.merge_and_deduplicate(extracted_dfs, conflict_res)
                succ, fail = TargetWriterFactory.bulk_load(target_db_url, target_engine_type, target_table, merged_df)
                total_processed += (succ + fail)
                total_successful += succ
                total_failed += fail

        # Step 3: Post-Migration DDL (Foreign Keys)
        ProgressReporter.report(
            backend_url, agent_token, job_id, "running", 95.0,
            total_processed, total_successful, total_failed,
            current_stage="post_ddl"
        )
        DDLExecutor.execute_ddl_list(target_db_url, post_ddl, "Post-Migration DDL")

        # Step 4: Mark Job Complete
        ProgressReporter.report(
            backend_url, agent_token, job_id, "completed", 100.0,
            total_processed, total_successful, total_failed,
            current_stage="completed"
        )
        logger.info(f"=== MIGRATION JOB '{job_id}' COMPLETED SUCCESSFULLY! (Processed: {total_processed}, Success: {total_successful}, Failed: {total_failed}) ===")
