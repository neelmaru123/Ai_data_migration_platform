"""
Target database DDL statement execution module for agent engine.
"""

import logging
from typing import List
from sqlalchemy import text
from .db import _get_engine

logger = logging.getLogger("docker-agent-execution")


class DDLExecutor:
    """Executes target database DDL statements (pre_migration_ddl and post_migration_ddl)."""

    @staticmethod
    def _ensure_database_exists(db_url: str):
        """Ensures target SQL database exists before executing DDL."""
        try:
            engine = _get_engine(db_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            exc_str = str(exc)
            if "1049" in exc_str or "Unknown database" in exc_str or "does not exist" in exc_str:
                from urllib.parse import urlparse
                parsed = urlparse(db_url)
                db_name = parsed.path.lstrip('/')
                if not db_name:
                    return
                try:
                    if "mysql" in db_url.lower():
                        root_url = db_url.replace(f"/{db_name}", "/mysql")
                        root_engine = _get_engine(root_url)
                        with root_engine.begin() as conn:
                            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
                        logger.info(f"Auto-created missing MySQL target database '{db_name}'.")
                    elif "postgres" in db_url.lower():
                        root_url = db_url.replace(f"/{db_name}", "/postgres")
                        root_engine = _get_engine(root_url)
                        with root_engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
                            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                        logger.info(f"Auto-created missing PostgreSQL target database '{db_name}'.")
                except Exception as create_exc:
                    logger.warning(f"Could not auto-create target database '{db_name}': {create_exc}")

    @staticmethod
    def _sanitize_ddl_statement(stmt: str, db_url: str) -> str:
        """Sanitizes DDL statements for dialect compatibility across target databases (MySQL, SQLite, PostgreSQL)."""
        import re
        cleaned = stmt.strip()
        url_lower = db_url.lower()

        if "mysql" in url_lower:
            cleaned = re.sub(
                r'\bUUID\s+PRIMARY\s+KEY\s+DEFAULT\s+gen_random_uuid\(\)',
                'VARCHAR(36) PRIMARY KEY',
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r'\bDEFAULT\s+gen_random_uuid\(\)',
                '',
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r'\bUUID\b', 'VARCHAR(36)', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bTIMESTAMPTZ\b', 'DATETIME', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(
                r'\bTIMESTAMP\s+WITH\s+TIME\s+ZONE\b',
                'DATETIME',
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r'\bJSONB\b', 'JSON', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bSERIAL\b', 'BIGINT AUTO_INCREMENT', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bBIGSERIAL\b', 'BIGINT AUTO_INCREMENT', cleaned, flags=re.IGNORECASE)
        elif "sqlite" in url_lower:
            cleaned = re.sub(
                r'\bUUID\s+PRIMARY\s+KEY\s+DEFAULT\s+gen_random_uuid\(\)',
                'TEXT PRIMARY KEY',
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r'\bDEFAULT\s+gen_random_uuid\(\)',
                '',
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r'\bUUID\b', 'TEXT', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bTIMESTAMPTZ\b', 'TEXT', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(
                r'\bTIMESTAMP\s+WITH\s+TIME\s+ZONE\b',
                'TEXT',
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r'\bJSONB\b', 'TEXT', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bJSON\b', 'TEXT', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bSERIAL\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bBIGSERIAL\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', cleaned, flags=re.IGNORECASE)

        return cleaned

    @staticmethod
    def execute_ddl_list(db_url: str, ddl_statements: List[str], stage_label: str = "Pre-Migration DDL"):
        if not ddl_statements:
            logger.info(f"No {stage_label} statements to execute.")
            return

        if db_url.startswith("mongodb://") or db_url.startswith("mongodb+srv://") or "mongo" in db_url.lower():
            logger.info(f"MongoDB target database detected — skipping SQL DDL execution for {stage_label}.")
            return

        DDLExecutor._ensure_database_exists(db_url)

        logger.info(f"Executing {len(ddl_statements)} {stage_label} statements...")
        engine = _get_engine(db_url)

        for stmt in ddl_statements:
            stmt_clean = stmt.strip()
            if "mysql" in db_url.lower() and "create extension" in stmt_clean.lower():
                logger.warning(f"Skipping PostgreSQL-specific DDL statement on MySQL target: '{stmt_clean}'")
                continue

            if "sqlite" in db_url.lower() and "add constraint" in stmt_clean.lower():
                logger.warning(f"Skipping ALTER TABLE ADD CONSTRAINT statement on SQLite target: '{stmt_clean}'")
                continue

            stmt_sanitized = DDLExecutor._sanitize_ddl_statement(stmt_clean, db_url)

            try:
                with engine.begin() as conn:
                    conn.execute(text(stmt_sanitized))
                logger.info(f"Successfully executed DDL: {stmt_sanitized[:80]}...")
            except Exception as exc:
                exc_str = str(exc).lower()
                benign_keywords = [
                    "already exists",
                    "duplicate",
                    "if not exists",
                    "multiple primary keys",
                    "foreignkeyviolation",
                    "foreign key constraint",
                    "violates foreign key constraint",
                    "referential integrity constraint violation",
                    "cannot add or update a child row",
                ]
                if any(kw in exc_str for kw in benign_keywords) or stage_label == "Post-Migration DDL":
                    logger.warning(f"{stage_label} notice/warning for statement '{stmt_clean}': {exc}")
                else:
                    logger.error(f"{stage_label} error for statement '{stmt_clean}': {exc}")
                    raise RuntimeError(f"{stage_label} failed for statement '{stmt_clean}': {exc}")
