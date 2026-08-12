"""
Unit & Integration Tests for File Loaders (CSV and Excel)
"""

import os
import tempfile
import openpyxl
import pytest

from app.modules.sources.sources_loaders import (
    FileLoaderFactory,
    CSVFileLoader,
    ExcelFileLoader,
)


def test_loader_factory_registration():
    """Verify CSV and Excel loaders are registered in FileLoaderFactory."""
    available = FileLoaderFactory.available_types()
    assert "csv" in available
    assert "excel" in available
    assert "xlsx" in available
    assert "xls" in available

    csv_inst = FileLoaderFactory.create("csv", "dummy.csv")
    assert isinstance(csv_inst, CSVFileLoader)

    excel_inst = FileLoaderFactory.create("excel", "dummy.xlsx")
    assert isinstance(excel_inst, ExcelFileLoader)


@pytest.mark.asyncio
async def test_csv_file_loader_full_lifecycle():
    """Test CSV loader: validate_file, introspect_schema, stream_chunks."""
    csv_content = (
        "id,name,department,salary\n"
        "101,Alice,Engineering,90000\n"
        "102,Bob,Marketing,75000\n"
        "103,Charlie,Sales,82000\n"
    )

    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".csv") as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name

    try:
        loader = FileLoaderFactory.create("csv", tmp_path)

        # 1. Validate
        val_result = await loader.validate_file()
        assert val_result.is_valid is True
        assert val_result.file_type == "csv"
        assert val_result.row_count == 3

        # 2. Introspect Schema
        schema = await loader.introspect_schema()
        assert schema.filename == os.path.basename(tmp_path)
        assert schema.total_rows == 3
        assert len(schema.columns) == 4
        col_names = [c.name for c in schema.columns]
        assert col_names == ["id", "name", "department", "salary"]
        assert len(schema.sample_rows) == 3
        assert schema.sample_rows[0]["name"] == "Alice"

        # 3. Stream Chunks (chunk_size=2)
        chunks = []
        async for chunk in loader.stream_chunks(chunk_size=2):
            chunks.append(chunk)

        assert len(chunks) == 2  # Batch 1 (2 rows), Batch 2 (1 row)
        assert len(chunks[0]) == 2
        assert len(chunks[1]) == 1
        assert chunks[0][0]["name"] == "Alice"
        assert chunks[0][1]["name"] == "Bob"
        assert chunks[1][0]["name"] == "Charlie"

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_excel_file_loader_full_lifecycle():
    """Test Excel loader (.xlsx): validate_file, introspect_schema, stream_chunks."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = tmp.name

    try:
        # Create test workbook using openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Employees"
        ws.append(["emp_id", "emp_name", "role", "active"])
        ws.append([1, "John Doe", "Developer", True])
        ws.append([2, "Jane Smith", "Designer", True])
        ws.append([3, "Alex Brown", "Manager", False])
        wb.save(tmp_path)
        wb.close()

        loader = FileLoaderFactory.create("excel", tmp_path)

        # 1. Validate
        val_result = await loader.validate_file()
        assert val_result.is_valid is True
        assert val_result.file_type == "excel"
        assert val_result.row_count == 3

        # 2. Introspect Schema
        schema = await loader.introspect_schema()
        assert schema.filename == os.path.basename(tmp_path)
        assert schema.total_rows == 3
        assert "Employees" in schema.sheet_names
        assert len(schema.columns) == 4
        col_names = [c.name for c in schema.columns]
        assert col_names == ["emp_id", "emp_name", "role", "active"]
        assert len(schema.sample_rows) == 3

        # 3. Stream Chunks (chunk_size=2)
        chunks = []
        async for chunk in loader.stream_chunks(sheet_name="Employees", chunk_size=2):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert len(chunks[0]) == 2
        assert len(chunks[1]) == 1
        assert chunks[0][0]["emp_name"] == "John Doe"
        assert chunks[0][1]["emp_name"] == "Jane Smith"
        assert chunks[1][0]["emp_name"] == "Alex Brown"

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_csv_file_loader_missing_file():
    """Verify graceful handling when CSV file path does not exist."""
    loader = FileLoaderFactory.create("csv", "non_existent_file.csv")
    val_result = await loader.validate_file()
    assert val_result.is_valid is False
    assert "File not found" in val_result.error_message

    with pytest.raises(FileNotFoundError):
        await loader.introspect_schema()

    with pytest.raises(FileNotFoundError):
        async for _ in loader.stream_chunks():
            pass
