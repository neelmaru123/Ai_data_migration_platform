"""
Base Abstract Classes and Data Structures for Database Connectors
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field


class ConnectionHealthResult(BaseModel):
    """Result payload returned by connector health checks."""
    is_healthy: bool
    latency_ms: float
    server_version: Optional[str] = None
    database_name: Optional[str] = None
    error_message: Optional[str] = None


class ColumnMetadata(BaseModel):
    """Metadata payload describing a single database column or field."""
    name: str
    data_type: str
    native_type: str
    nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    max_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None


class TableMetadata(BaseModel):
    """Metadata payload describing a database table or collection."""
    table_name: str
    schema_name: str = "public"
    table_type: str = "table"
    estimated_rows: int = 0
    size_bytes: int = 0
    columns: List[ColumnMetadata] = Field(default_factory=list)


class DatabaseMetadata(BaseModel):
    """Metadata payload describing an entire database schema snapshot."""
    database_name: str
    server_version: str = "unknown"
    schemas: List[str] = Field(default_factory=list)
    tables: List[TableMetadata] = Field(default_factory=list)
    total_tables: int = 0
    total_columns: int = 0


class BaseConnector(ABC):
    """Abstract Base Class for all Database Connectors (PostgreSQL, MySQL, MongoDB)."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def test_connection(self) -> ConnectionHealthResult:
        """Test connection health, network reachability, and credentials."""
        pass

    @abstractmethod
    async def introspect_schema(self) -> DatabaseMetadata:
        """Fetch complete database metadata, tables, and column schemas."""
        pass

    @abstractmethod
    async def get_table_sample(
        self, table_name: str, schema_name: str = "public", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Fetch sample rows for data preview."""
        pass

    @abstractmethod
    async def stream_table_data(
        self, table_name: str, schema_name: str = "public", chunk_size: int = 10000
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """Stream table data in chunks for ETL execution."""
        # AsyncIterator is the correct return type for async generator overrides.
        # Using AsyncGenerator here causes Pyright to infer Coroutine[AsyncGenerator]
        # which conflicts with concrete implementations that use yield.
        yield  # type: ignore[misc]
