"""
Target database DDL statement execution module for agent engine.
"""

import logging
from typing import List
from sqlalchemy import text
import execution_engine

logger = logging.getLogger("docker-agent-execution")


class DDLExecutor:
    """Executes target database DDL statements (pre_migration_ddl and post_migration_ddl)."""

    @staticmethod
    def execute_ddl_list(db_url: str, ddl_statements: List[str], stage_label: str = "Pre-Migration DDL"):
        if not ddl_statements:
            logger.info(f"No {stage_label} statements to execute.")
            return

        logger.info(f"Executing {len(ddl_statements)} {stage_label} statements...")
        engine = execution_engine._get_engine(db_url)

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
