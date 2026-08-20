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


def _get_engine(db_url: str):
    """Creates a SQLAlchemy engine with connection pooling, recycle limits, and active TCP keepalives."""
    clean_url = db_url.replace("postgresql://", "postgresql+psycopg2://").replace("mysql://", "mysql+pymysql://")
    connect_args = {}
    if "postgres" in clean_url:
        connect_args = {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    return create_engine(
        clean_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_timeout=30,
        connect_args=connect_args,
    )


def _quote_identifier(name: str, engine_type: str = "postgresql") -> str:
    """Safely quotes table and column identifiers based on database dialect."""
    if not name:
        return ""
    engine_type = engine_type.lower()
    clean_name = name.replace("`", "").replace('"', '')
    if "mysql" in engine_type or "mariadb" in engine_type:
        return f"`{clean_name}`"
    return f'"{clean_name}"'


class CheckpointManager:
    """Manages resumable checkpointing per table and per source to prevent restarting from zero on agent crash."""

    @staticmethod
    def get_checkpoint_path(
        job_id: str,
        table_name: str,
        source_identifier: Optional[str] = None,
        source_table: Optional[str] = None,
    ) -> str:
        tmp_dir = os.getenv("CHECKPOINT_DIR", "/tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        if source_identifier or source_table:
            src_id = (source_identifier or "default").replace("/", "_").replace("\\", "_")
            src_tbl = (source_table or "default").replace("/", "_").replace("\\", "_")
            return os.path.join(tmp_dir, f"checkpoint_{job_id}_{table_name}_{src_id}_{src_tbl}.json")
        return os.path.join(tmp_dir, f"checkpoint_{job_id}_{table_name}.json")

    @classmethod
    def get_last_offset(
        cls,
        job_id: str,
        table_name: str,
        source_identifier: Optional[str] = None,
        source_table: Optional[str] = None,
    ) -> int:
        path = cls.get_checkpoint_path(job_id, table_name, source_identifier, source_table)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_offset", 0)
            except Exception as exc:
                logger.warning(f"Could not read checkpoint file '{path}': {exc}")
                return 0

        # Backward compatibility for legacy checkpoint naming without source suffix
        legacy_path = os.path.join(os.getenv("CHECKPOINT_DIR", "/tmp"), f"checkpoint_{job_id}_{table_name}.json")
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_offset", 0)
            except Exception as exc:
                logger.warning(f"Could not read legacy checkpoint file '{legacy_path}': {exc}")
                return 0
 
        return 0

    @classmethod
    def save_checkpoint(
        cls,
        job_id: str,
        table_name: str,
        offset: int,
        rows_processed: int,
        source_identifier: Optional[str] = None,
        source_table: Optional[str] = None,
    ):
        path = cls.get_checkpoint_path(job_id, table_name, source_identifier, source_table)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "job_id": job_id,
                    "table_name": table_name,
                    "source_identifier": source_identifier,
                    "source_table": source_table,
                    "last_offset": offset,
                    "rows_processed": rows_processed,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as exc:
            logger.warning(f"Could not write checkpoint for table '{table_name}' source '{source_identifier}.{source_table}': {exc}")


class DDLExecutor:
    """Executes target database DDL statements (pre_migration_ddl and post_migration_ddl)."""

    @staticmethod
    def execute_ddl_list(db_url: str, ddl_statements: List[str], stage_label: str = "Pre-Migration DDL"):
        if not ddl_statements:
            logger.info(f"No {stage_label} statements to execute.")
            return

        logger.info(f"Executing {len(ddl_statements)} {stage_label} statements...")
        engine = _get_engine(db_url)

        for stmt in ddl_statements:
            stmt_clean = stmt.strip()
            try:
                with engine.begin() as conn:
                    conn.execute(text(stmt_clean))
                logger.info(f"Successfully executed DDL: {stmt_clean[:80]}...")
            except Exception as exc:
                exc_str = str(exc).lower()
                benign_keywords = [
                    "already exists",
                    "duplicate",
                    "if not exists",
                    "multiple primary keys",
                ]
                if any(kw in exc_str for kw in benign_keywords):
                    logger.warning(f"DDL execution notice/warning: {exc}")
                else:
                    logger.error(f"DDL execution error for statement '{stmt_clean}': {exc}")
                    raise RuntimeError(f"DDL execution failed for statement '{stmt_clean}': {exc}")


class SourceConnectorFactory:
    """Factory creating chunked stream readers for PostgreSQL, MySQL, MongoDB, CSV, and Excel with Keyset Pagination support."""

    @staticmethod
    def read_source_chunk(
        db_url: str,
        engine_type: str,
        table_or_file_name: str,
        offset: int = 0,
        chunk_size: int = 50000,
        pk_col: Optional[str] = None,
        last_pk_val: Optional[Any] = None,
    ) -> Tuple[pl.DataFrame, bool, Optional[Any]]:
        """
        Reads a chunk of rows from the source database using Polars or SQLAlchemy streaming.
        Supports Keyset Pagination (WHERE pk > last_pk ORDER BY pk) to eliminate offset drift on live DBs.
        Returns a tuple of (DataFrame, has_more_rows, next_last_pk_val).
        """
        engine_type = engine_type.lower()
        quoted_table = _quote_identifier(table_or_file_name, engine_type)

        # 1. SQL Relational Databases (PostgreSQL, MySQL, SQLite)
        if engine_type in ["postgresql", "postgres", "mysql", "mariadb", "sqlite"]:
            try:
                engine = _get_engine(db_url)
                if pk_col and last_pk_val is not None:
                    quoted_pk = _quote_identifier(pk_col, engine_type)
                    query = f"SELECT * FROM {quoted_table} WHERE {quoted_pk} > :last_pk ORDER BY {quoted_pk} ASC LIMIT {chunk_size}"
                    with engine.connect() as conn:
                        df = pl.read_database(query=text(query), connection=conn, params={"last_pk": last_pk_val})
                else:
                    quoted_pk = _quote_identifier(pk_col, engine_type) if pk_col else None
                    order_by_clause = f" ORDER BY {quoted_pk} ASC" if quoted_pk else ""
                    query = f"SELECT * FROM {quoted_table}{order_by_clause} LIMIT {chunk_size} OFFSET {offset}"
                    with engine.connect() as conn:
                        df = pl.read_database(query=query, connection=conn)

                has_more = len(df) == chunk_size
                next_pk = None
                if not df.is_empty() and pk_col and pk_col in df.columns:
                    next_pk = df[pk_col][-1]

                return df, has_more, next_pk
            except Exception as exc:
                logger.error(f"Error reading SQL source chunk for table '{table_or_file_name}' (Offset: {offset}): {exc}")
                return pl.DataFrame(), False, last_pk_val

        # 2. MongoDB Collection
        elif engine_type == "mongodb":
            try:
                from pymongo import MongoClient
                from bson import ObjectId

                client = MongoClient(db_url)
                db_name = db_url.rsplit("/", 1)[-1].split("?")[0] or "test"
                db = client[db_name]

                query = {}
                if last_pk_val is not None and str(last_pk_val).strip() != "":
                    try:
                        query_id = ObjectId(str(last_pk_val))
                    except Exception:
                        query_id = str(last_pk_val)
                    query = {"_id": {"$gt": query_id}}

                cursor = db[table_or_file_name].find(query).sort("_id", 1).limit(chunk_size)
                docs = list(cursor)
                client.close()

                if not docs:
                    return pl.DataFrame(), False, last_pk_val

                next_pk = str(docs[-1]["_id"]) if "_id" in docs[-1] else last_pk_val

                for d in docs:
                    if "_id" in d:
                        d["_id"] = str(d["_id"])

                df = pl.DataFrame(docs)
                has_more = len(df) == chunk_size
                return df, has_more, next_pk
            except Exception as exc:
                logger.error(f"Error reading MongoDB collection '{table_or_file_name}': {exc}")
                return pl.DataFrame(), False, last_pk_val

        # 3. CSV File
        elif engine_type == "csv" or table_or_file_name.endswith(".csv"):
            try:
                if os.path.exists(table_or_file_name):
                    df = pl.read_csv(table_or_file_name, n_rows=chunk_size, skip_rows=offset)
                    has_more = len(df) == chunk_size
                    return df, has_more, None
                return pl.DataFrame(), False, None
            except Exception as exc:
                logger.error(f"Error reading CSV file '{table_or_file_name}': {exc}")
                return pl.DataFrame(), False, None

        # 4. Excel File
        elif engine_type in ["excel", "xlsx"] or table_or_file_name.endswith(".xlsx"):
            try:
                if os.path.exists(table_or_file_name):
                    df = pl.read_excel(table_or_file_name)
                    df_chunk = df.slice(offset, chunk_size)
                    has_more = (offset + chunk_size) < len(df)
                    return df_chunk, has_more, None
                return pl.DataFrame(), False, None
            except Exception as exc:
                logger.error(f"Error reading Excel file '{table_or_file_name}': {exc}")
                return pl.DataFrame(), False, None

        else:
            logger.warning(f"Unsupported engine type '{engine_type}'. Returning empty DataFrame.")
            return pl.DataFrame(), False, None


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

            # 2. type_cast (e.g. INT -> UUID, STRING -> DATETIME UTC, PREFIX_ID)
            elif trans_type == "type_cast":
                src_name = source_cols[0]["column_name"] if source_cols and "column_name" in source_cols[0] else target_col
                src_ident = source_cols[0].get("identifier", "source") if source_cols else "source"
                target_dtype = col_spec.get("target_data_type", "varchar").lower()
                pk_strategy = col_spec.get("primary_key_strategy", "uuid_v5")

                if src_name in df.columns:
                    if col_spec.get("is_primary_key"):
                        if pk_strategy == "keep_original":
                            if "int" in target_dtype:
                                pk_expr = pl.col(src_name).cast(pl.Int64, strict=False)
                            else:
                                pk_expr = pl.col(src_name).cast(pl.Utf8)
                        elif pk_strategy == "autoincrement_offset":
                            src_idx = col_spec.get("source_index", 0)
                            if not src_idx and src_ident:
                                nums = re.findall(r'\d+', str(src_ident))
                                if nums:
                                    src_idx = max(0, int(nums[-1]) - 1)
                            offset_val = 1_000_000_000 * int(src_idx)
                            pk_expr = (pl.col(src_name).cast(pl.Int64, strict=False) + offset_val).cast(pl.Int64)
                        elif pk_strategy == "uuid_v4_rekey":
                            pk_expr = pl.col(src_name).cast(pl.Utf8).map_elements(
                                lambda val: str(uuid.uuid4()),
                                return_dtype=pl.Utf8
                            )
                        elif pk_strategy == "prefix_id":
                            pk_expr = pl.col(src_name).cast(pl.Utf8).map_elements(
                                lambda val: f"{src_ident}_{val}" if val is not None and str(val) != "" else str(uuid.uuid4()),
                                return_dtype=pl.Utf8
                            )
                        else:
                            # Deterministic UUID v5 namespace hashing by default
                            pk_expr = pl.col(src_name).cast(pl.Utf8).map_elements(
                                lambda val: str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{src_ident}_{val}")) if val is not None and str(val) != "" else str(uuid.uuid4()),
                                return_dtype=pl.Utf8
                            )
                        exprs.append(pk_expr.alias(target_col))
                    elif "int" in target_dtype:
                        exprs.append(pl.col(src_name).cast(pl.Int64, strict=False).alias(target_col))
                    elif "timestamp" in target_dtype or "datetime" in target_dtype or "timestamptz" in target_dtype:
                        # ISO-8601 UTC normalization
                        dt_expr = (
                            pl.col(src_name)
                            .cast(pl.Utf8)
                            .str.replace(r" ", "T")
                            .str.to_datetime(strict=False)
                        )
                        exprs.append(dt_expr.alias(target_col))
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

            # 8. json_flatten (e.g. address.city -> address_city)
            elif trans_type == "json_flatten":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).cast(pl.Utf8).alias(target_col))
                elif "." in src_name:
                    parts = src_name.split(".")
                    root_col = parts[0]
                    sub_paths = parts[1:]
                    if root_col in df.columns:
                        def _extract_nested(val, paths=sub_paths):
                            curr = val
                            if hasattr(curr, "to_dict"):
                                curr = curr.to_dict()
                            for p in paths:
                                if isinstance(curr, dict):
                                    curr = curr.get(p, "")
                                elif isinstance(curr, str) and curr.startswith("{"):
                                    try:
                                        curr = json.loads(curr).get(p, "")
                                    except Exception:
                                        return ""
                                else:
                                    return ""
                            return str(curr) if curr is not None else ""

                        flatten_expr = pl.col(root_col).map_elements(
                            _extract_nested, return_dtype=pl.Utf8
                        )
                        exprs.append(flatten_expr.alias(target_col))

            # 9. json_stringify (e.g. dict/list -> JSON string / JSONB payload)
            elif trans_type == "json_stringify":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    def _safe_json_dumps(val):
                        if hasattr(val, "to_dict"):
                            val = val.to_dict()
                        elif hasattr(val, "to_list"):
                            val = val.to_list()
                        if isinstance(val, (dict, list)):
                            return json.dumps(val)
                        if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                            return val
                        if val is not None:
                            return json.dumps(val)
                        return "{}"

                    stringify_expr = pl.col(src_name).map_elements(
                        _safe_json_dumps, return_dtype=pl.Utf8
                    )
                    exprs.append(stringify_expr.alias(target_col))

            # 10. array_to_csv (e.g. tags List -> "tag1,tag2")
            elif trans_type == "array_to_csv":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    def _safe_array_to_csv(val):
                        if hasattr(val, "to_list"):
                            val = val.to_list()
                        if isinstance(val, (list, tuple, set)):
                            return ",".join(map(str, val))
                        return str(val or "")

                    csv_expr = pl.col(src_name).map_elements(
                        _safe_array_to_csv, return_dtype=pl.Utf8
                    )
                    exprs.append(csv_expr.alias(target_col))

            # 11. array_to_json (e.g. tags List -> '["tag1", "tag2"]')
            elif trans_type == "array_to_json":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    def _safe_array_to_json(val):
                        if hasattr(val, "to_list"):
                            val = val.to_list()
                        if isinstance(val, (list, tuple, set)):
                            return json.dumps(val)
                        if val is not None:
                            return json.dumps([val])
                        return "[]"

                    json_arr_expr = pl.col(src_name).map_elements(
                        _safe_array_to_json, return_dtype=pl.Utf8
                    )
                    exprs.append(json_arr_expr.alias(target_col))

            # 12. nosql_field_promote
            elif trans_type == "nosql_field_promote":
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).cast(pl.Utf8).alias(target_col))

            # 13. lookup_join / fallback
            else:
                src_name = source_cols[0]["column_name"] if source_cols else target_col
                if src_name in df.columns:
                    exprs.append(pl.col(src_name).alias(target_col))

        # Residual/unmapped field capture (Fix 9)
        mapped_src_cols = set()
        for col_spec in column_mappings:
            if col_spec.get("target_column_name") and col_spec.get("transformation_type") != "drop_column":
                for sc in col_spec.get("source_columns", []):
                    if "column_name" in sc:
                        c_name = sc["column_name"]
                        mapped_src_cols.add(c_name)
                        if "." in c_name:
                            mapped_src_cols.add(c_name.split(".")[0])

        unmapped_cols = [c for c in df.columns if c not in mapped_src_cols and c not in ("_seq_id",)]
        if unmapped_cols:
            if "extra_attributes" not in keep_columns:
                keep_columns.append("extra_attributes")

            def _serialize_residual(struct_val, cols=unmapped_cols):
                res_dict = {}
                if isinstance(struct_val, dict):
                    for k, v in struct_val.items():
                        if v is not None:
                            if hasattr(v, "to_dict"):
                                v = v.to_dict()
                            elif hasattr(v, "to_list"):
                                v = v.to_list()
                            res_dict[k] = v
                return json.dumps(res_dict) if res_dict else "{}"

            try:
                extra_attr_expr = pl.struct([pl.col(c) for c in unmapped_cols if c in df.columns]).map_elements(
                    _serialize_residual, return_dtype=pl.Utf8
                )
                exprs.append(extra_attr_expr.alias("extra_attributes"))
            except Exception as exc:
                logger.warning(f"Residual field capture warning: {exc}")

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
            # Null-Exempt Deduplication: Only unique non-null/non-empty business keys
            valid_mask = (pl.col(dedup_key).is_not_null()) & (pl.col(dedup_key).cast(pl.Utf8).str.strip_chars() != "")
            df_valid = combined.filter(valid_mask).unique(subset=[dedup_key], keep=keep_opt)
            df_nulls = combined.filter(~valid_mask)
            combined = pl.concat([df_valid, df_nulls], how="vertical")
            logger.info(f"Deduplicated combined table on '{dedup_key}' using '{strategy}' strategy (Remaining rows: {len(combined)}).")

        return combined

    @staticmethod
    def append_to_duckdb_staging(
        conn: duckdb.DuckDBPyConnection,
        staging_table_name: str,
        df: pl.DataFrame,
        start_seq: int = 0,
    ) -> int:
        if df.is_empty():
            return start_seq

        num_rows = len(df)
        seq_series = pl.Series("_seq_id", range(start_seq, start_seq + num_rows), dtype=pl.Int64)
        df_with_seq = df.with_columns(seq_series)

        conn.register("df_chunk_temp", df_with_seq)

        table_exists = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [staging_table_name]
        ).fetchone()[0] > 0

        if not table_exists:
            conn.execute(f"CREATE TABLE {staging_table_name} AS SELECT * FROM df_chunk_temp")
        else:
            existing_cols = [r[0] for r in conn.execute(f"DESCRIBE {staging_table_name}").fetchall()]
            new_cols = [c for c in df_with_seq.columns if c not in existing_cols]
            for c in new_cols:
                conn.execute(f'ALTER TABLE {staging_table_name} ADD COLUMN "{c}" VARCHAR')

            conn.execute(f"INSERT INTO {staging_table_name} BY NAME SELECT * FROM df_chunk_temp")

        conn.unregister("df_chunk_temp")
        return start_seq + num_rows

    @classmethod
    def stream_deduplicated_chunks(
        cls,
        conn: duckdb.DuckDBPyConnection,
        staging_table_name: str,
        conflict_res: Optional[Dict[str, Any]] = None,
        chunk_size: int = 50000,
    ):
        table_exists = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [staging_table_name]
        ).fetchone()[0] > 0

        if not table_exists:
            return

        cols = [r[0] for r in conn.execute(f"DESCRIBE {staging_table_name}").fetchall() if r[0] != "_seq_id"]
        if not cols:
            return

        quoted_cols = [f'"{c}"' for c in cols]
        col_select = ", ".join(quoted_cols)

        dedup_key = conflict_res.get("deduplication_key") if conflict_res else None
        strategy = conflict_res.get("deduplication_strategy", "first_wins") if conflict_res else "first_wins"

        if dedup_key and dedup_key in cols:
            quoted_key = f'"{dedup_key}"'
            order_dir = "ASC" if strategy == "first_wins" else "DESC"

            dedup_sql = f"""
                CREATE TEMP TABLE _dedup_final AS
                WITH valid_rows AS (
                    SELECT {col_select}, _seq_id,
                           ROW_NUMBER() OVER (PARTITION BY {quoted_key} ORDER BY _seq_id {order_dir}) as _rn
                    FROM {staging_table_name}
                    WHERE {quoted_key} IS NOT NULL AND TRIM(CAST({quoted_key} AS VARCHAR)) != ''
                ),
                null_rows AS (
                    SELECT {col_select}, _seq_id
                    FROM {staging_table_name}
                    WHERE {quoted_key} IS NULL OR TRIM(CAST({quoted_key} AS VARCHAR)) = ''
                )
                SELECT {col_select}, _seq_id FROM valid_rows WHERE _rn = 1
                UNION ALL
                SELECT {col_select}, _seq_id FROM null_rows
                ORDER BY _seq_id ASC
            """
            conn.execute("DROP TABLE IF EXISTS _dedup_final")
            conn.execute(dedup_sql)
            target_relation = "_dedup_final"
        else:
            target_relation = staging_table_name

        total_rows = conn.execute(f"SELECT COUNT(*) FROM {target_relation}").fetchone()[0]
        logger.info(f"Streaming {total_rows} deduplicated rows from DuckDB staging area in chunks of {chunk_size}...")

        for offset in range(0, total_rows, chunk_size):
            chunk_df = conn.execute(
                f"SELECT {col_select} FROM {target_relation} ORDER BY _seq_id ASC LIMIT {chunk_size} OFFSET {offset}"
            ).pl()
            yield chunk_df


class TargetWriterFactory:
    """Bulk-inserts transformed Polars DataFrames into PostgreSQL, MySQL, or MongoDB target databases."""

    @staticmethod
    def bulk_load(db_url: str, engine_type: str, table_name: str, df: pl.DataFrame) -> Tuple[int, int, int]:
        """
        Bulk loads a DataFrame into target DB.
        Returns a tuple of (successful_rows, failed_rows, skipped_rows).
        """
        if hasattr(df, "is_empty"):
            if df.is_empty():
                return 0, 0, 0
            rows = df.to_dicts()
        elif isinstance(df, list):
            if not df:
                return 0, 0, 0
            rows = df
        else:
            rows = list(df)
        if not rows:
            return 0, 0, 0

        successful_rows = 0
        failed_rows = 0
        skipped_rows = 0

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
                return successful_rows, 0, 0
            except Exception as exc:
                is_bulk_err = False
                try:
                    import importlib
                    pymongo = importlib.import_module("pymongo")
                    if isinstance(exc, pymongo.errors.BulkWriteError):
                        is_bulk_err = True
                except Exception:
                    pass

                if is_bulk_err or (hasattr(exc, "details") and isinstance(getattr(exc, "details"), dict)):
                    details = getattr(exc, "details", {})
                    write_errors = details.get("writeErrors", [])
                    failed_rows = len(write_errors)
                    n_inserted = details.get("nInserted", len(rows) - failed_rows)
                    successful_rows = max(0, n_inserted)
                    logger.warning(
                        f"MongoDB partial bulk insert notice for collection '{table_name}': "
                        f"{successful_rows} successful, {failed_rows} failed."
                    )
                    return successful_rows, failed_rows, 0

                logger.error(f"MongoDB bulk insert error for collection '{table_name}': {exc}")
                return 0, len(rows), 0

        # 2. PostgreSQL & MySQL Target Writer
        else:
            engine = _get_engine(db_url)
            columns = list(rows[0].keys())

            quoted_table = _quote_identifier(table_name, engine_type)
            quoted_cols = [_quote_identifier(c, engine_type) for c in columns]
            col_names = ", ".join(quoted_cols)
            placeholders = ", ".join([f":{c}" for c in columns])

            if "mysql" in engine_type:
                insert_sql = f'INSERT IGNORE INTO {quoted_table} ({col_names}) VALUES ({placeholders});'
            else:
                insert_sql = f'INSERT INTO {quoted_table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING;'

            try:
                with engine.begin() as conn:
                    result = conn.execute(text(insert_sql), rows)
                    raw_rowcount = getattr(result, "rowcount", -1)
                    if raw_rowcount >= 0:
                        successful_rows = raw_rowcount
                        skipped_rows = max(0, len(rows) - successful_rows)
                    else:
                        successful_rows = len(rows)
                        skipped_rows = 0

                logger.info(
                    f"Bulk-inserted {successful_rows} rows into target table '{table_name}' "
                    f"(Skipped due to conflict: {skipped_rows})."
                )
                return successful_rows, 0, skipped_rows
            except Exception as exc:
                logger.warning(f"Batch bulk insert notice for table '{table_name}': {exc}. Retrying per-row insertion...")
                # Fallback to per-row insertion with sample error capping and 50% abort threshold
                MAX_SAMPLE_ERRORS = 100
                ABORT_THRESHOLD_PERCENT = 0.50
                threshold_sample_size = min(1000, max(5, len(rows) // 2))

                with engine.begin() as conn:
                    for idx, row in enumerate(rows):
                        try:
                            res_row = conn.execute(text(insert_sql), [row])
                            r_cnt = getattr(res_row, "rowcount", -1)
                            if r_cnt == 0:
                                skipped_rows += 1
                            else:
                                successful_rows += 1
                        except Exception as row_exc:
                            failed_rows += 1
                            if failed_rows <= MAX_SAMPLE_ERRORS:
                                logger.warning(f"Row insertion notice in table '{table_name}' (Row #{idx}): {row_exc}")

                            if (idx + 1) >= threshold_sample_size and (failed_rows / (idx + 1)) > ABORT_THRESHOLD_PERCENT:
                                raise RuntimeError(
                                    f"Migration aborted for table '{table_name}': Error rate exceeded {ABORT_THRESHOLD_PERCENT*100:.0f}% "
                                    f"({failed_rows}/{idx+1} rows failed). Please verify target schema and column mapping specs."
                                )

                return successful_rows, failed_rows, skipped_rows


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
        skipped_rows: int = 0,
        total_rows: int = 0,
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
            "skipped_rows": skipped_rows,
            "total_rows": total_rows,
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
