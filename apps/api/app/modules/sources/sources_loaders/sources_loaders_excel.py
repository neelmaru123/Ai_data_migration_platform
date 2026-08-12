"""
Excel Spreadsheet File Loader Implementation powered by OpenPyXL / Polars
"""

import os
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional
import openpyxl
import polars as pl

from app.modules.sources.sources_connectors.sources_connectors_base import ColumnMetadata
from app.modules.sources.sources_loaders.sources_loaders_base import (
    BaseFileLoader,
    FileSchemaMetadata,
    FileValidationResult,
)
from app.modules.sources.sources_loaders.sources_loaders_factory import FileLoaderFactory


# Decorator order: Python applies decorators bottom-up, so all three keys
# (xls → xlsx → excel) are registered before the class is finalised.
@FileLoaderFactory.register("excel")
@FileLoaderFactory.register("xlsx")
@FileLoaderFactory.register("xls")
class ExcelFileLoader(BaseFileLoader):
    """Excel Spreadsheet Loader supporting multi-sheet discovery and row streaming."""

    def _get_sheet_names(self) -> List[str]:
        """Safely open workbook in read-only mode and return sheet name list."""
        wb = openpyxl.load_workbook(self.file_path, read_only=True)
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()

    async def validate_file(self) -> FileValidationResult:
        if not os.path.exists(self.file_path):
            return FileValidationResult(
                is_valid=False,
                file_type="excel",
                error_message=f"File not found at path '{self.file_path}'",
            )

        try:
            sheet_names = self._get_sheet_names()

            # Count rows on the first sheet to populate row_count (fix #11)
            row_count = 0
            if sheet_names:
                wb = openpyxl.load_workbook(self.file_path, read_only=True)
                try:
                    ws = wb[sheet_names[0]]
                    # max_row may be None for empty sheets
                    row_count = max(0, (ws.max_row or 1) - 1)  # subtract header
                finally:
                    wb.close()

            return FileValidationResult(
                is_valid=True,
                file_type="excel",
                encoding="binary",
                row_count=row_count,
            )
        except Exception as e:
            return FileValidationResult(
                is_valid=False,
                file_type="excel",
                error_message=f"Excel validation failed: {str(e)}",
            )

    async def introspect_schema(self) -> FileSchemaMetadata:
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found at '{self.file_path}'")

        file_size = os.path.getsize(self.file_path)
        sheet_names = self._get_sheet_names()
        target_sheet = sheet_names[0] if sheet_names else "Sheet1"

        wb = openpyxl.load_workbook(self.file_path, read_only=True, data_only=True)
        try:
            ws = wb[target_sheet]
            rows_iter = ws.iter_rows(values_only=True)

            try:
                header_raw = next(rows_iter)
                header = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(header_raw)]
            except StopIteration:
                header = []

            sample_rows: List[Dict[str, Any]] = []
            col_types: Dict[str, str] = {h: "string" for h in header}

            total_rows = 0
            for row_values in rows_iter:
                total_rows += 1
                if len(sample_rows) < 10:
                    row_dict = dict(zip(header, row_values))
                    sample_rows.append(row_dict)
                    for k, v in row_dict.items():
                        if v is not None and col_types[k] == "string":
                            col_types[k] = type(v).__name__.lower()

            columns = [
                ColumnMetadata(
                    name=h,
                    data_type=col_types.get(h, "string"),
                    native_type=col_types.get(h, "string"),
                    nullable=True,
                )
                for h in header
            ]
        finally:
            wb.close()

        return FileSchemaMetadata(
            filename=os.path.basename(self.file_path),
            file_type="excel",
            total_rows=total_rows,
            size_bytes=file_size,
            sheet_names=sheet_names,
            columns=columns,
            sample_rows=sample_rows,
        )

    async def stream_chunks(
        self, sheet_name: Optional[str] = None, chunk_size: int = 10000
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """
        Stream Excel rows in chunks using openpyxl's read_only row iterator.
        This avoids loading the entire sheet into a Polars DataFrame first,
        which would cause OOM errors on large workbooks.
        Previous implementation: pl.read_excel() → df.slice() — loaded everything into RAM.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found at '{self.file_path}'")

        # Safely resolve the sheet name — fix #4: resource leak if sheetnames[0] raises
        if not sheet_name:
            sheet_names = self._get_sheet_names()
            sheet_name = sheet_names[0] if sheet_names else "Sheet1"

        wb = openpyxl.load_workbook(self.file_path, read_only=True, data_only=True)
        try:
            ws = wb[sheet_name]
            rows_iter = ws.iter_rows(values_only=True)

            # First row is the header
            try:
                header = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(next(rows_iter))]
            except StopIteration:
                return  # Empty sheet — yield nothing

            batch: List[Dict[str, Any]] = []
            for row_values in rows_iter:
                row_dict = dict(zip(header, row_values))
                batch.append(row_dict)
                if len(batch) >= chunk_size:
                    yield batch
                    batch = []

            # Yield final partial batch
            if batch:
                yield batch
        finally:
            wb.close()
