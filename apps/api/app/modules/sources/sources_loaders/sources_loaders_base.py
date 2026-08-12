"""
Base Abstract Class and Data Structures for File Loaders
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field

from app.modules.sources.sources_connectors.sources_connectors_base import ColumnMetadata


class FileSchemaMetadata(BaseModel):
    """Metadata payload describing an uploaded CSV or Excel file structure."""
    filename: str
    file_type: str
    total_rows: int = 0
    size_bytes: int = 0
    sheet_names: List[str] = Field(default_factory=list)
    columns: List[ColumnMetadata] = Field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list)


class FileValidationResult(BaseModel):
    """Validation result payload for uploaded file format integrity."""
    is_valid: bool
    file_type: str
    encoding: str = "utf-8"
    row_count: int = 0
    error_message: Optional[str] = None


class BaseFileLoader(ABC):
    """Abstract Base Class for all File Loaders (CSV, Excel)."""

    def __init__(self, file_path: str, options: Optional[Dict[str, Any]] = None):
        self.file_path = file_path
        self.options = options or {}

    @abstractmethod
    async def validate_file(self) -> FileValidationResult:
        """Validate file integrity, headers, and encoding."""
        pass

    @abstractmethod
    async def introspect_schema(self) -> FileSchemaMetadata:
        """Extract column data types, row counts, and sample records."""
        pass

    @abstractmethod
    async def stream_chunks(
        self, sheet_name: Optional[str] = None, chunk_size: int = 10000
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """Stream file rows in chunks for migration processing."""
        yield  # type: ignore[misc]
