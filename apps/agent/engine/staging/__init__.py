"""
Multi-source staging and deduplication package for agent execution engine.
"""
from .duckdb_staging import TableMerger

__all__ = ["TableMerger"]
