"""
Sources Domain Application Service
"""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources.sources_connectors import (
    ConnectorFactory,
    ConnectionHealthResult,
    DatabaseMetadata,
)
from app.modules.sources.sources_loaders import (
    FileLoaderFactory,
    FileSchemaMetadata,
)
from app.modules.sources.sources_models import Connection
from app.modules.sources.sources_schemas import ConnectionCreate


class SourceService:
    """Business logic service for managing source connections and schema profiling."""

    @staticmethod
    async def test_connection_config(
        type_name: str, config_dict: Dict[str, Any]
    ) -> ConnectionHealthResult:
        """Test database connection health using ConnectorFactory strategy."""
        connector = ConnectorFactory.create(type_name=type_name, config=config_dict)
        return await connector.test_connection()

    @staticmethod
    async def introspect_connection_schema(
        type_name: str, config_dict: Dict[str, Any]
    ) -> DatabaseMetadata:
        """Fetch complete database schema snapshot using ConnectorFactory strategy."""
        connector = ConnectorFactory.create(type_name=type_name, config=config_dict)
        return await connector.introspect_schema()

    @staticmethod
    async def inspect_uploaded_file(
        file_type: str, file_path: str
    ) -> FileSchemaMetadata:
        """Introspect uploaded CSV or Excel file structure using FileLoaderFactory strategy."""
        loader = FileLoaderFactory.create(file_type=file_type, file_path=file_path)
        return await loader.introspect_schema()

    @staticmethod
    async def create_connection(
        session: AsyncSession, user_id: uuid.UUID, data: ConnectionCreate
    ) -> Connection:
        """Create and persist a new Connection ORM model."""
        config_payload = data.config.model_dump(exclude_none=True)

        conn_obj = Connection(
            user_id=user_id,
            name=data.name,
            type=data.type.lower(),
            role=data.role.lower(),
            host=data.config.host,
            port=data.config.port,
            database_name=data.config.database_name,
            username=data.config.username,
            credentials_encrypted=data.config.password,  # Placeholder for encryption
            config=config_payload,
            status="active",
        )
        session.add(conn_obj)
        await session.commit()
        await session.refresh(conn_obj)
        return conn_obj

    @staticmethod
    async def get_all_connections(
        session: AsyncSession, user_id: uuid.UUID
    ) -> List[Connection]:
        """Fetch all connections owned by a user."""
        stmt = select(Connection).where(Connection.user_id == user_id).order_by(Connection.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())
