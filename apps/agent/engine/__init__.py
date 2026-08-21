"""
Agent Execution Engine Package Facade.
Re-exports all public engine classes and utilities for seamless modular architecture and backwards compatibility.
"""

from .db import _get_engine, _quote_identifier
from .checkpoint import CheckpointManager, CHECKPOINT_DIR
from .ddl_executor import DDLExecutor
from .progress_reporter import ProgressReporter
from .connectors.source_factory import SourceConnectorFactory
from .transformers.ast_transformer import ASTTransformer
from .staging.duckdb_staging import TableMerger
from .writers.target_writer import TargetWriterFactory
from .orchestrator import ExecutionOrchestrator

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
