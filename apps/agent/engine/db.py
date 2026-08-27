"""
Database connection pooling and identifier quoting utilities for agent execution engine.
"""

import logging
from sqlalchemy import create_engine

logger = logging.getLogger("docker-agent-execution")


def _clean_url_for_engine(db_url: str) -> str:
    cleaned = db_url.strip()
    if cleaned.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg2://" + cleaned[len("postgresql+asyncpg://") :]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg2://" + cleaned[len("postgresql://") :]
    if cleaned.startswith("mysql+aiomysql://"):
        return "mysql+pymysql://" + cleaned[len("mysql+aiomysql://") :]
    if cleaned.startswith("mysql://"):
        return "mysql+pymysql://" + cleaned[len("mysql://") :]
    return cleaned


def _get_engine(db_url: str):
    """Creates a SQLAlchemy engine with connection pooling, recycle limits, and active TCP keepalives."""
    clean_url = _clean_url_for_engine(db_url)
    connect_args = {}
    if "postgres" in clean_url:
        connect_args = {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    kwargs = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": connect_args,
    }
    if "sqlite" not in clean_url:
        kwargs["pool_timeout"] = 30
    return create_engine(clean_url, **kwargs)


def _quote_identifier(name: str, engine_type: str = "postgresql") -> str:
    """Safely quotes table and column identifiers based on database dialect."""
    if not name:
        return ""
    engine_type = engine_type.lower()
    clean_name = name.replace("`", "").replace('"', '')
    if "mysql" in engine_type or "mariadb" in engine_type:
        return f"`{clean_name}`"
    return f'"{clean_name}"'
