"""
Integration Test for Live Neon PostgreSQL Database Connector
"""

import pytest
from app.modules.sources.sources_connectors import ConnectorFactory

NEON_CONFIG = {
    "host": "ep-holy-frost-aodix1li.c-2.ap-southeast-1.aws.neon.tech",
    "port": 5432,
    "username": "neondb_owner",
    "password": "npg_ZhzgawGx7T0F",
    "database_name": "neondb",
    "connection_string": (
        "postgresql+asyncpg://neondb_owner:npg_ZhzgawGx7T0F"
        "@ep-holy-frost-aodix1li.c-2.ap-southeast-1.aws.neon.tech:5432/neondb?ssl=require"
    ),
}


@pytest.mark.asyncio
async def test_live_neon_postgres_health_check():
    """Test health check connection against live Neon cloud PostgreSQL database."""
    connector = ConnectorFactory.create("postgresql", NEON_CONFIG)
    health = await connector.test_connection()

    assert health.is_healthy is True
    assert health.latency_ms > 0
    assert "PostgreSQL" in health.server_version
    assert health.database_name == "neondb"


@pytest.mark.asyncio
async def test_live_neon_postgres_schema_introspection():
    """Test full schema introspection on live Neon PostgreSQL database."""
    connector = ConnectorFactory.create("postgresql", NEON_CONFIG)
    schema = await connector.introspect_schema()

    assert schema.database_name == "neondb"
    assert "public" in schema.schemas
    assert schema.total_tables >= 10
    assert schema.total_columns > 50

    table_names = [t.table_name for t in schema.tables]
    assert "users" in table_names
    assert "blood_tests" in table_names


@pytest.mark.asyncio
async def test_live_neon_postgres_get_table_sample():
    """Test fetching row sample from 'users' table on live Neon DB."""
    connector = ConnectorFactory.create("postgresql", NEON_CONFIG)
    sample_rows = await connector.get_table_sample(table_name="users", schema_name="public", limit=5)

    assert isinstance(sample_rows, list)
    if len(sample_rows) > 0:
        row = sample_rows[0]
        assert "id" in row or "email" in row or "created_at" in row


@pytest.mark.asyncio
async def test_live_neon_postgres_stream_table_data():
    """Test streaming chunked data from 'users' table on live Neon DB."""
    connector = ConnectorFactory.create("postgresql", NEON_CONFIG)

    streamed_batches = []
    async for chunk in connector.stream_table_data(table_name="users", schema_name="public", chunk_size=2):
        streamed_batches.append(chunk)

    assert isinstance(streamed_batches, list)
    if len(streamed_batches) > 0:
        assert len(streamed_batches[0]) <= 2
