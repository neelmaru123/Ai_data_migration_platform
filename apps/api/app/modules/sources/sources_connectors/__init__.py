"""
Sources Domain Connectors Sub-package
NOTE: Live database driver connectors are retained for local developer diagnostic tooling.
Control plane backend APIs do NOT store credentials or initiate live connections.
"""

from app.modules.sources.sources_connectors.sources_connectors_base import (
    BaseConnector,
    ConnectionHealthResult,
    DatabaseMetadata,
)
from app.modules.sources.sources_connectors.sources_connectors_factory import ConnectorFactory
from app.modules.sources.sources_connectors.sources_connectors_mongodb import MongoDBConnector
from app.modules.sources.sources_connectors.sources_connectors_mysql import MySQLConnector
from app.modules.sources.sources_connectors.sources_connectors_postgres import PostgreSQLConnector

__all__ = [
    "BaseConnector",
    "ConnectionHealthResult",
    "DatabaseMetadata",
    "ConnectorFactory",
    "PostgreSQLConnector",
    "MySQLConnector",
    "MongoDBConnector",
]
