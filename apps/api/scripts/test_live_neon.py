"""
Test Script for Live Neon PostgreSQL Connection.
Reads database host, user, password, and db strictly from environment variables.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.modules.sources.sources_connectors import ConnectorFactory


async def test_neon_connection():
    host = os.getenv("NEON_HOST", "")
    password = os.getenv("NEON_PASSWORD", "")
    user = os.getenv("NEON_USER", "postgres")
    db = os.getenv("NEON_DB", "neondb")

    if not host or not password:
        print("Please set NEON_HOST and NEON_PASSWORD environment variables to run this live test script.")
        return

    conn_str = f"postgresql+asyncpg://{user}:{password}@{host}:5432/{db}?ssl=require"
    connector = ConnectorFactory.create("postgresql", {"connection_string": conn_str, "database_name": db})
    res = await connector.test_connection()

    if res.is_healthy:
        print(f"\n[SUCCESS] Connected to Neon PostgreSQL!")
        print(f"Server Version: {res.server_version}")
        print(f"Latency: {res.latency_ms} ms")
        print(f"Database: {res.database_name}")

        try:
            schema = await connector.introspect_schema()
            print(f"Total Schemas: {len(schema.schemas)}")
            print(f"Total Tables: {schema.total_tables}")
            print(f"Total Columns: {schema.total_columns}")
        except Exception as e:
            print(f"Introspection error: {e}")
    else:
        print(f"[FAIL] {res.error_message}")


if __name__ == "__main__":
    asyncio.run(test_neon_connection())
