"""
On-Premise Agent Database Metadata Introspection Engine
Executes native SQL introspection locally across customer databases (PostgreSQL, MySQL, SQLite)
and builds structured Schema & Table AST payloads for synchronization to the Control Plane.
"""

import logging
import re
from typing import Any, Dict, List, Optional
import urllib.parse
from sqlalchemy import create_engine, text

logger = logging.getLogger("docker-agent-metadata")


class AgentMetadataEngine:
    """Introspection engine for scanning database schemas, tables, columns, constraints, and foreign key relationships."""

    @staticmethod
    def _clean_url_for_sync_engine(url_val: str) -> str:
        """Converts async drivers (e.g. postgresql+asyncpg) to sync drivers for lightweight agent introspection."""
        cleaned = url_val.strip()
        if cleaned.startswith("postgresql+asyncpg://"):
            cleaned = "postgresql+psycopg2://" + cleaned[len("postgresql+asyncpg://") :]
        elif cleaned.startswith("mysql+aiomysql://"):
            cleaned = "mysql+pymysql://" + cleaned[len("mysql+aiomysql://") :]
        return cleaned

    @classmethod
    def introspect_database(cls, identifier: str, url_val: str) -> Optional[Dict[str, Any]]:
        """
        Executes local schema introspection on a target database URL.
        Returns a structured MetadataSnapshotSyncPayload dictionary, or None if connection fails.
        """
        if not url_val or not url_val.strip() or ("<" in url_val and ">" in url_val):
            logger.warning(f"Skipping metadata introspection for '{identifier}': connection URL is invalid or contains unfilled placeholders.")
            return None

        sync_url = cls._clean_url_for_sync_engine(url_val)
        parsed = urllib.parse.urlparse(sync_url)
        db_name = parsed.path.lstrip("/") if parsed.path else "database"
        scheme = parsed.scheme.lower() if parsed.scheme else "postgresql"

        try:
            engine = create_engine(sync_url, echo=False, pool_pre_ping=True, connect_args={"connect_timeout": 5})
            with engine.connect() as conn:
                # 1. Fetch server version string
                ver_str = "Unknown"
                try:
                    res_ver = conn.execute(text("SELECT version();"))
                    ver_str = str(res_ver.scalar() or "Unknown")
                except Exception:
                    pass

                # 2. Introspect Schemas
                schemas = ["public"]
                try:
                    res_sch = conn.execute(text("""
                        SELECT schema_name FROM information_schema.schemata
                        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'sys', 'performance_schema', 'mysql')
                        ORDER BY schema_name;
                    """))
                    schemas = [r[0] for r in res_sch.fetchall()]
                    if not schemas:
                        schemas = ["public"]
                except Exception:
                    pass

                # 3. Introspect Tables & Estimated Row Counts
                tables_raw = []
                try:
                    if "postgres" in scheme:
                        res_tbl = conn.execute(text("""
                            SELECT t.table_schema, t.table_name, t.table_type,
                                   COALESCE(c.reltuples::bigint, 0) AS estimated_rows
                            FROM information_schema.tables t
                            LEFT JOIN pg_class c ON c.relname = t.table_name
                            LEFT JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.table_schema
                            WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
                            ORDER BY t.table_schema, t.table_name;
                        """))
                    else:
                        res_tbl = conn.execute(text("""
                            SELECT table_schema, table_name, table_type, 0 AS estimated_rows
                            FROM information_schema.tables
                            WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                            ORDER BY table_schema, table_name;
                        """))
                    tables_raw = res_tbl.fetchall()
                except Exception as tbl_err:
                    logger.warning(f"Could not query information_schema.tables for '{identifier}': {tbl_err}")

                # 4. Introspect Columns
                columns_raw = []
                try:
                    res_col = conn.execute(text("""
                        SELECT table_schema, table_name, column_name, ordinal_position,
                               data_type, udt_name, is_nullable, character_maximum_length,
                               numeric_precision, numeric_scale, column_default
                        FROM information_schema.columns
                        WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'sys', 'performance_schema', 'mysql')
                        ORDER BY table_schema, table_name, ordinal_position;
                    """))
                    columns_raw = res_col.fetchall()
                except Exception as col_err:
                    logger.warning(f"Could not query information_schema.columns for '{identifier}': {col_err}")

                # 5. Introspect Primary Keys & Constraints
                pk_columns = set()
                constraints_raw = []
                try:
                    res_cst = conn.execute(text("""
                        SELECT tc.table_schema, tc.table_name, tc.constraint_name, tc.constraint_type, kcu.column_name
                        FROM information_schema.table_constraints tc
                        LEFT JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        WHERE tc.table_schema NOT IN ('pg_catalog', 'information_schema', 'sys', 'performance_schema', 'mysql');
                    """))
                    for r in res_cst.fetchall():
                        s_name, t_name, c_name, c_type, col_name = r[0], r[1], r[2], r[3], r[4]
                        if c_type.upper() == "PRIMARY KEY" and col_name:
                            pk_columns.add((s_name.lower(), t_name.lower(), col_name.lower()))
                        constraints_raw.append({
                            "schema_name": s_name,
                            "table_name": t_name,
                            "constraint_name": c_name,
                            "constraint_type": c_type.lower(),
                        })
                except Exception:
                    pass

                # 6. Introspect Foreign Key Relationships
                relationships_raw = []
                try:
                    if "postgres" in scheme:
                        res_fk = conn.execute(text("""
                            SELECT kcu.table_schema AS src_schema,
                                   kcu.table_name AS src_table,
                                   kcu.column_name AS src_column,
                                   ccu.table_schema AS tgt_schema,
                                   ccu.table_name AS tgt_table,
                                   ccu.column_name AS tgt_column
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                              ON tc.constraint_name = kcu.constraint_name
                             AND tc.table_schema = kcu.table_schema
                            JOIN information_schema.constraint_column_usage ccu
                              ON ccu.constraint_name = tc.constraint_name
                             AND ccu.table_schema = tc.table_schema
                            WHERE tc.constraint_type = 'FOREIGN KEY';
                        """))
                        for r in res_fk.fetchall():
                            relationships_raw.append({
                                "source_schema": r[0],
                                "source_table": r[1],
                                "source_column": r[2],
                                "target_schema": r[3],
                                "target_table": r[4],
                                "target_column": r[5],
                                "relationship_type": "foreign_key",
                                "confidence": 1.0,
                            })
                except Exception:
                    pass

            engine.dispose()

            # Group columns by (schema_name, table_name)
            cols_by_table: Dict[tuple, List[Dict[str, Any]]] = {}
            for c in columns_raw:
                s_name, t_name, c_name = c[0], c[1], c[2]
                ord_pos, data_type, udt_name, is_null = c[3], c[4], c[5], c[6]
                max_len, num_prec, num_scale, col_def = c[7], c[8], c[9], c[10]

                key = (s_name.lower(), t_name.lower())
                if key not in cols_by_table:
                    cols_by_table[key] = []

                is_pk = (s_name.lower(), t_name.lower(), c_name.lower()) in pk_columns

                cols_by_table[key].append({
                    "column_name": c_name,
                    "ordinal_position": ord_pos or len(cols_by_table[key]) + 1,
                    "data_type": data_type or udt_name or "varchar",
                    "native_data_type": udt_name or data_type or "varchar",
                    "nullable": (str(is_null).upper() == "YES"),
                    "is_primary_key": is_pk,
                    "is_unique": is_pk,
                    "default_value": str(col_def) if col_def is not None else None,
                    "max_length": max_len,
                    "numeric_precision": num_prec,
                    "numeric_scale": num_scale,
                })

            # Group constraints by (schema_name, table_name)
            csts_by_table: Dict[tuple, List[Dict[str, Any]]] = {}
            for cst in constraints_raw:
                key = (cst["schema_name"].lower(), cst["table_name"].lower())
                if key not in csts_by_table:
                    csts_by_table[key] = []
                csts_by_table[key].append({
                    "constraint_name": cst["constraint_name"],
                    "constraint_type": cst["constraint_type"],
                })

            # Assemble structured Tables list
            tables_payload: List[Dict[str, Any]] = []
            total_cols_count = 0
            total_rows_count = 0

            for t in tables_raw:
                s_name, t_name, t_type, est_rows = t[0], t[1], t[2], t[3]
                key = (s_name.lower(), t_name.lower())
                table_cols = cols_by_table.get(key, [])
                table_csts = csts_by_table.get(key, [])
                total_cols_count += len(table_cols)
                total_rows_count += max(0, est_rows or 0)

                tables_payload.append({
                    "schema_name": s_name,
                    "table_name": t_name,
                    "table_type": str(t_type).lower() if t_type else "table",
                    "row_count": max(0, est_rows or 0),
                    "size_bytes": 0,
                    "columns": table_cols,
                    "constraints": table_csts,
                })

            # Build final payload AST
            snapshot_payload = {
                "identifier": identifier,
                "database_name": db_name,
                "database_version": ver_str[:250] if ver_str else "Unknown",
                "total_tables": len(tables_payload),
                "total_columns": total_cols_count,
                "total_rows": total_rows_count,
                "tables": tables_payload,
                "relationships": relationships_raw,
            }

            logger.info(f"Successfully introspected database '{identifier}' (Database: {db_name}, Tables: {len(tables_payload)}, Columns: {total_cols_count}).")
            return snapshot_payload

        except Exception as exc:
            logger.error(f"Error during metadata introspection for '{identifier}': {exc}")
            return None
