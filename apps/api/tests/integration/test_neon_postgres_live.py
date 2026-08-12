"""
Integration Test for Live Neon PostgreSQL Database Connector.
Reads all database credentials strictly from environment variables.
"""

import os
import pytest
from app.modules.sources.sources_connectors import ConnectorFactory

NEON_HOST = os.getenv("NEON_HOST", "")
NEON_USER = os.getenv("NEON_USER", "")
NEON_PASSWORD = os.getenv("NEON_PASSWORD", "")
NEON_DB = os.getenv("NEON_DB", "postgres")

NEON_CONFIG = {
    "host": NEON_HOST,
    "port": int(os.getenv("NEON_PORT", 5432)),
    "username": NEON_USER,
    "password": NEON_PASSWORD,
    "database_name": NEON_DB,
    "connection_string": (
        f"postgresql+asyncpg://{NEON_USER}:{NEON_PASSWORD}@{NEON_HOST}:5432/{NEON_DB}?ssl=require"
    ) if (NEON_PASSWORD and NEON_HOST) else "",
}


@pytest.mark.skipif(not (NEON_PASSWORD and NEON_HOST), reason="NEON_HOST or NEON_PASSWORD environment variable not set")
@pytest.mark.asyncio
async def test_live_neon_postgres_health_check():
    """Test health check connection against live Neon cloud PostgreSQL database."""
    connector = ConnectorFactory.create("postgresql", NEON_CONFIG)
    health = await connector.test_connection()

    assert health.is_healthy is True
    assert health.latency_ms > 0
    assert health.server_version is not None
    assert "PostgreSQL" in health.server_version
    assert health.database_name == NEON_DB


@pytest.mark.skipif(not (NEON_PASSWORD and NEON_HOST), reason="NEON_HOST or NEON_PASSWORD environment variable not set")
@pytest.mark.asyncio
async def test_live_neon_postgres_schema_introspection():
    """Test full schema introspection on live Neon PostgreSQL database."""
    connector = ConnectorFactory.create("postgresql", NEON_CONFIG)
    schema = await connector.introspect_schema()

    assert schema.database_name == NEON_DB
    assert "public" in schema.schemas
    assert schema.total_tables >= 1
    assert schema.total_columns >= 1


@pytest.mark.skipif(not (NEON_PASSWORD and NEON_HOST), reason="NEON_HOST or NEON_PASSWORD environment variable not set")
@pytest.mark.asyncio
async def test_live_neon_postgres_get_table_sample():
    """Test fetching row sample from 'users' table on live Neon DB."""
    connector = ConnectorFactory.create("postgresql", NEON_CONFIG)
    sample_rows = await connector.get_table_sample(table_name="users", schema_name="public", limit=5)

    assert isinstance(sample_rows, list)


@pytest.mark.skipif(not (NEON_PASSWORD and NEON_HOST), reason="NEON_PASSWORD environment variable not set")
@pytest.mark.asyncio
async def test_live_neon_postgres_stream_table_data():
    """Test streaming chunked data from 'users' table on live Neon DB."""
    connector = ConnectorFactory.create("postgresql", NEON_CONFIG)

    streamed_batches = []
    async for chunk in connector.stream_table_data(table_name="users", schema_name="public", chunk_size=2):
        streamed_batches.append(chunk)

    assert isinstance(streamed_batches, list)
