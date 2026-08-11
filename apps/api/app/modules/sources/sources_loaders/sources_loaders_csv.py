"""
CSV File Loader Implementation powered by Polars / Python csv module
"""

import csv
import os
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional
import polars as pl

from app.modules.sources.sources_connectors.sources_connectors_base import ColumnMetadata
from app.modules.sources.sources_loaders.sources_loaders_base import (
    BaseFileLoader,
    FileSchemaMetadata,
    FileValidationResult,
)
from app.modules.sources.sources_loaders.sources_loaders_factory import FileLoaderFactory


@FileLoaderFactory.register("csv")
class CSVFileLoader(BaseFileLoader):
    """CSV File Loader supporting true memory-efficient row streaming via csv.DictReader."""

    def _count_rows(self) -> int:
        """Count total data rows by counting file lines minus the header — O(n) time, O(1) memory."""
        with open(self.file_path, "rb") as f:
            total_lines = sum(1 for _ in f)
        # Subtract 1 for the header row; guard against empty file
        return max(0, total_lines - 1)

    async def validate_file(self) -> FileValidationResult:
        if not os.path.exists(self.file_path):
            return FileValidationResult(
                is_valid=False,
                file_type="csv",
                error_message=f"File not found at path '{self.file_path}'",
            )

        try:
            # Read a small sample with Polars for a fast header / encoding check
            df = pl.read_csv(self.file_path, n_rows=100)
            row_count = self._count_rows()
            return FileValidationResult(
                is_valid=True,
                file_type="csv",
                encoding="utf-8",
                row_count=row_count,
            )
        except Exception as e:
            return FileValidationResult(
                is_valid=False,
                file_type="csv",
                error_message=f"CSV validation failed: {str(e)}",
            )

    async def introspect_schema(self) -> FileSchemaMetadata:
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found at '{self.file_path}'")

        file_size = os.path.getsize(self.file_path)

        # Single small sample read — no second full-file pass for row counting
        df_sample = pl.read_csv(self.file_path, n_rows=100)
        total_rows = self._count_rows()

        columns: List[ColumnMetadata] = []
        for col_name, dtype in df_sample.schema.items():
            dt_str = str(dtype).lower()
            columns.append(
                ColumnMetadata(
                    name=col_name,
                    data_type=dt_str,
                    native_type=dt_str,
                    nullable=True,
                )
            )

        sample_rows = df_sample.to_dicts()

        return FileSchemaMetadata(
            filename=os.path.basename(self.file_path),
            file_type="csv",
            total_rows=total_rows,
            size_bytes=file_size,
            sheet_names=["default"],
            columns=columns,
            sample_rows=sample_rows[:10],
        )

    async def stream_chunks(
        self, sheet_name: Optional[str] = None, chunk_size: int = 10000
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """
        Stream CSV rows in chunks using Python's csv.DictReader.
        This is true O(1) memory streaming — only `chunk_size` rows are ever held in memory at once.
        Previously used pl.scan_csv().collect_batches() which materialised the full file before batching.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found at '{self.file_path}'")

        encoding = self.options.get("encoding", "utf-8")

        with open(self.file_path, newline="", encoding=encoding, errors="replace") as f:
            reader = csv.DictReader(f)
            batch: List[Dict[str, Any]] = []

            for row in reader:
                batch.append(dict(row))
                if len(batch) >= chunk_size:
                    yield batch
                    batch = []

            # Yield final partial batch
            if batch:
                yield batch
