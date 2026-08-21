"""
Local Docker Agent ETL Execution Engine (Backwards-Compatibility Layer)
Re-exports all engine components from the modular apps.agent.engine package.
"""

from engine import db
from engine import (
    CheckpointManager,
    CHECKPOINT_DIR,
    DDLExecutor,
    ProgressReporter,
    SourceConnectorFactory,
    ASTTransformer,
    TableMerger,
    TargetWriterFactory,
    ExecutionOrchestrator,
)


def _get_engine(db_url: str):
    """Creates a SQLAlchemy engine with connection pooling (delegates to engine.db._get_engine)."""
    return db._get_engine(db_url)


def _quote_identifier(name: str, engine_type: str = "postgresql") -> str:
    """Safely quotes table and column identifiers (delegates to engine.db._quote_identifier)."""
    return db._quote_identifier(name, engine_type)


__all__ = [
    "_get_engine",
    "_quote_identifier",
    "CheckpointManager",
    "CHECKPOINT_DIR",
    "DDLExecutor",
    "ProgressReporter",
    "SourceConnectorFactory",
    "ASTTransformer",
    "TableMerger",
    "TargetWriterFactory",
    "ExecutionOrchestrator",
]
