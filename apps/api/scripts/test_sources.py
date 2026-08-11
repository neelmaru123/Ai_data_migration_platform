"""
Interactive Diagnostic Test Script for All DB Connectors and File Loaders.
Run via:
    poetry run python scripts/test_sources.py
"""

import asyncio
import os
import sys
import tempfile
import openpyxl

# Ensure app package is in sys.path when executed directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.modules.sources.sources_connectors import ConnectorFactory
from app.modules.sources.sources_loaders import FileLoaderFactory


HEADER = "\033[95m"
OKGREEN = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"
BOLD = "\033[1m"


def print_title(text: str):
    print(f"\n{BOLD}{HEADER}{'='*60}\n {text}\n{'='*60}{ENDC}")


def print_result(name: str, success: bool, details: str = ""):
    status = f"{OKGREEN}[PASS]{ENDC}" if success else f"{WARNING}[SKIP/FAIL]{ENDC}"
    print(f"{BOLD}{name:<35}{ENDC} {status} {details}")


async def test_csv_loader():
    print_title("1. Testing CSV File Loader")
    csv_content = "id,name,role,salary\n1,Alice,Engineer,90000\n2,Bob,Manager,110000\n"
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".csv") as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name

    try:
        loader = FileLoaderFactory.create("csv", tmp_path)
        val = await loader.validate_file()
        assert val.is_valid, f"Validation failed: {val.error_message}"

        schema = await loader.introspect_schema()
        assert schema.total_rows == 2, f"Expected 2 rows, got {schema.total_rows}"
        assert len(schema.columns) == 4

        chunks = []
        async for chunk in loader.stream_chunks(chunk_size=1):
            chunks.append(chunk)
        assert len(chunks) == 2

        print_result("CSV Loader (Validation, Introspect, Stream)", True, f"Rows: {schema.total_rows}, Cols: {len(schema.columns)}")
    except Exception as e:
        print_result("CSV Loader", False, f"Error: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def test_excel_loader():
    print_title("2. Testing Excel File Loader")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = tmp.name

    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["id", "product", "price"])
        ws.append([101, "Laptop", 1200.50])
        ws.append([102, "Mouse", 25.00])
        wb.save(tmp_path)
        wb.close()

        loader = FileLoaderFactory.create("excel", tmp_path)
        val = await loader.validate_file()
        assert val.is_valid, f"Validation failed: {val.error_message}"

        schema = await loader.introspect_schema()
        assert schema.total_rows == 2
        assert len(schema.columns) == 3

        chunks = []
        async for chunk in loader.stream_chunks(chunk_size=1):
            chunks.append(chunk)
        assert len(chunks) == 2

        print_result("Excel Loader (Validation, Introspect, Stream)", True, f"Rows: {schema.total_rows}, Cols: {len(schema.columns)}")
    except Exception as e:
        print_result("Excel Loader", False, f"Error: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def test_postgres_connector():
    print_title("3. Testing PostgreSQL Database Connector")
    config = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", 5432)),
        "username": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres_password"),
        "database_name": os.getenv("POSTGRES_DB", "migration_platform"),
    }

    connector = ConnectorFactory.create("postgresql", config)
    res = await connector.test_connection()
    if res.is_healthy:
        print_result("PostgreSQL Health Check", True, f"Latency: {res.latency_ms}ms, Server: {res.server_version}")
        try:
            schema = await connector.introspect_schema()
            print_result("PostgreSQL Schema Introspection", True, f"Tables: {schema.total_tables}, Columns: {schema.total_columns}")
        except Exception as e:
            print_result("PostgreSQL Schema Introspection", False, f"Error: {e}")
    else:
        print_result("PostgreSQL Health Check", False, f"Unreachable or bad credentials ({res.error_message})")


async def test_mysql_connector():
    print_title("4. Testing MySQL Database Connector")
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", 3306)),
        "username": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "root_password"),
        "database_name": os.getenv("MYSQL_DB", "mysql"),
    }

    connector = ConnectorFactory.create("mysql", config)
    res = await connector.test_connection()
    if res.is_healthy:
        print_result("MySQL Health Check", True, f"Latency: {res.latency_ms}ms, Server: {res.server_version}")
        try:
            schema = await connector.introspect_schema()
            print_result("MySQL Schema Introspection", True, f"Tables: {schema.total_tables}, Columns: {schema.total_columns}")
        except Exception as e:
            print_result("MySQL Schema Introspection", False, f"Error: {e}")
    else:
        print_result("MySQL Health Check", False, f"Unreachable or bad credentials ({res.error_message})")


async def test_mongodb_connector():
    print_title("5. Testing MongoDB Database Connector")
    config = {
        "host": os.getenv("MONGO_HOST", "localhost"),
        "port": int(os.getenv("MONGO_PORT", 27017)),
        "username": os.getenv("MONGO_USER", ""),
        "password": os.getenv("MONGO_PASSWORD", ""),
        "database_name": os.getenv("MONGO_DB", "admin"),
    }

    connector = ConnectorFactory.create("mongodb", config)
    res = await connector.test_connection()
    if res.is_healthy:
        print_result("MongoDB Health Check", True, f"Latency: {res.latency_ms}ms, Server: {res.server_version}")
        try:
            schema = await connector.introspect_schema()
            print_result("MongoDB Schema Introspection", True, f"Collections: {schema.total_tables}")
        except Exception as e:
            print_result("MongoDB Schema Introspection", False, f"Error: {e}")
    else:
        print_result("MongoDB Health Check", False, f"Unreachable or bad credentials ({res.error_message})")


async def main():
    print(f"{BOLD}Running Sources Connectors and Loaders Diagnostic Suite...{ENDC}")
    await test_csv_loader()
    await test_excel_loader()
    await test_postgres_connector()
    await test_mysql_connector()
    await test_mongodb_connector()
    print(f"\n{BOLD}Diagnostic Run Complete!{ENDC}\n")


if __name__ == "__main__":
    asyncio.run(main())
