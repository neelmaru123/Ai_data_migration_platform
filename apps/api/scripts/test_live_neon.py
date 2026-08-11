"""
Test Script for Live Neon PostgreSQL Connection
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.modules.sources.sources_connectors import ConnectorFactory


async def test_neon_connection():
    host = "ep-holy-frost-aodix1li.c-2.ap-southeast-1.aws.neon.tech"
    password = "npg_ZhzgawGx7T0F"

    # Try common username / db combinations on Neon
    possible_users = ["neondb_owner", "postgres", "neondb"]
    possible_dbs = ["neondb", "postgres", "main"]

    for user in possible_users:
        for db in possible_dbs:
            conn_str = f"postgresql+asyncpg://{user}:{password}@{host}:5432/{db}?ssl=require"
            print(f"Trying: user={user}, db={db} ...")
            connector = ConnectorFactory.create("postgresql", {"connection_string": conn_str, "database_name": db})
            res = await connector.test_connection()
            if res.is_healthy:
                print(f"\n[SUCCESS] Connected to Neon PostgreSQL!")
                print(f"Server Version: {res.server_version}")
                print(f"Latency: {res.latency_ms} ms")
                print(f"Database: {res.database_name}")

                # Introspect schema
                try:
                    schema = await connector.introspect_schema()
                    print(f"Total Schemas: {len(schema.schemas)}")
                    print(f"Total Tables: {schema.total_tables}")
                    print(f"Total Columns: {schema.total_columns}")
                    for t in schema.tables:
                        print(f"  - Table: {t.schema_name}.{t.table_name} (est. rows: {t.estimated_rows}, cols: {len(t.columns)})")
                except Exception as e:
                    print(f"Introspection error: {e}")
                return user, db, conn_str
            else:
                print(f"  Failed: {res.error_message}")

    print("\nCould not find working credentials combination.")
    return None, None, None


if __name__ == "__main__":
    asyncio.run(test_neon_connection())
