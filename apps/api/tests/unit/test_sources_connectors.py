"""
Unit & Integration Tests for Database Connectors (PostgreSQL, MySQL, MongoDB)
"""

import pytest
from app.modules.sources.sources_connectors import (
    ConnectorFactory,
    PostgreSQLConnector,
    MySQLConnector,
    MongoDBConnector,
)


def test_connector_factory_registry():
    """Test dynamic connector registration and instantiation."""
    available = ConnectorFactory.available_types()
    assert "postgresql" in available
    assert "postgres" in available
    assert "mysql" in available
    assert "mariadb" in available
    assert "mongodb" in available
    assert "mongo" in available

    pg = ConnectorFactory.create("postgresql", {"host": "localhost", "port": 5432})
    assert isinstance(pg, PostgreSQLConnector)

    my = ConnectorFactory.create("mysql", {"host": "localhost", "port": 3306})
    assert isinstance(my, MySQLConnector)

    mongo = ConnectorFactory.create("mongodb", {"host": "localhost", "port": 27017})
    assert isinstance(mongo, MongoDBConnector)


def test_unsupported_connector_type():
    """Verify ValueError is raised for unregistered connector types."""
    with pytest.raises(ValueError) as excinfo:
        ConnectorFactory.create("oracle", {"host": "localhost"})
    assert "Unsupported database connector type 'oracle'" in str(excinfo.value)


@pytest.mark.asyncio
async def test_postgres_connector_unreachable_host():
    """Verify test_connection returns is_healthy=False for unreachable PostgreSQL host."""
    config = {
        "host": "127.0.0.1",
        "port": 59999,  # Unused port
        "username": "postgres",
        "password": "wrong_password",
        "database_name": "non_existent_db",
    }
    connector = ConnectorFactory.create("postgresql", config)
    res = await connector.test_connection()
    assert res.is_healthy is False
    assert res.error_message is not None


@pytest.mark.asyncio
async def test_mysql_connector_unreachable_host():
    """Verify test_connection returns is_healthy=False for unreachable MySQL host."""
    config = {
        "host": "127.0.0.1",
        "port": 59999,  # Unused port
        "username": "root",
        "password": "wrong_password",
        "database_name": "non_existent_db",
    }
    connector = ConnectorFactory.create("mysql", config)
    res = await connector.test_connection()
    assert res.is_healthy is False
    assert res.error_message is not None


@pytest.mark.asyncio
async def test_mongodb_connector_unreachable_host():
    """Verify test_connection returns is_healthy=False for unreachable MongoDB host."""
    config = {
        "host": "127.0.0.1",
        "port": 59999,  # Unused port
        "username": "",
        "password": "",
        "database_name": "admin",
    }
    connector = ConnectorFactory.create("mongodb", config)
    res = await connector.test_connection()
    assert res.is_healthy is False
    assert res.error_message is not None


@pytest.mark.asyncio
async def test_postgres_connector_live_local():
    """Test live PostgreSQL connection health against local Postgres instance (if running)."""
    config = {
        "host": "localhost",
        "port": 5432,
        "username": "postgres",
        "password": "postgres_password",
        "database_name": "migration_platform",
    }

    connector = ConnectorFactory.create("postgresql", config)
    res = await connector.test_connection()

    # If local PostgreSQL Docker container is running, verify healthy output
    if res.is_healthy:
        assert res.latency_ms > 0
        assert res.server_version is not None
        assert "PostgreSQL" in res.server_version
        assert res.database_name == "migration_platform"

        # Also test schema introspection on live DB
        db_meta = await connector.introspect_schema()
        assert db_meta.database_name == "migration_platform"
        assert isinstance(db_meta.tables, list)
