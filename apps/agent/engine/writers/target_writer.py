"""
Target database loader module for PostgreSQL, MySQL, SQLite, and MongoDB.
"""

import logging
from typing import Tuple
import polars as pl
from sqlalchemy import text
import execution_engine

logger = logging.getLogger("docker-agent-execution")


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

        # 2. PostgreSQL, MySQL & SQLite Target Writer
        else:
            engine = execution_engine._get_engine(db_url)
            columns = list(rows[0].keys())

            quoted_table = execution_engine._quote_identifier(table_name, engine_type)
            quoted_cols = [execution_engine._quote_identifier(c, engine_type) for c in columns]
            col_names = ", ".join(quoted_cols)
            placeholders = ", ".join([f":{c}" for c in columns])

            if "mysql" in engine_type:
                insert_sql = f'INSERT IGNORE INTO {quoted_table} ({col_names}) VALUES ({placeholders});'
            elif "sqlite" in engine_type:
                insert_sql = f'INSERT OR IGNORE INTO {quoted_table} ({col_names}) VALUES ({placeholders});'
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
                        successful_rows, skipped_rows = len(rows), 0

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

                for idx, row in enumerate(rows):
                    try:
                        with engine.begin() as conn:
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
