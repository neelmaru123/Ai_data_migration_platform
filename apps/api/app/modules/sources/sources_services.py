"""
Sources Domain Application Service (Data Sources Management)
"""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources.sources_models import DataSource
from app.modules.sources.sources_schemas import DataSourceCreate, DataSourceUpdate


class SourceService:
    """Business logic service for managing Data Sources identity."""

    @staticmethod
    async def create_data_source(
        session: AsyncSession, data: DataSourceCreate
    ) -> DataSource:
        """Create and persist a new DataSource identity."""
        source_obj = DataSource(
            agent_id=data.agent_id,
            name=data.name.strip(),
            type=data.type.lower().strip(),
            role=data.role.lower().strip(),
            identifier=data.identifier.strip(),
        )
        session.add(source_obj)
        await session.commit()
        await session.refresh(source_obj)
        return source_obj

    @staticmethod
    async def get_data_source_by_id(
        session: AsyncSession, source_id: uuid.UUID
    ) -> Optional[DataSource]:
        """Fetch data source by primary key UUID."""
        stmt = select(DataSource).where(DataSource.id == source_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_data_sources_by_agent(
        session: AsyncSession, agent_id: uuid.UUID
    ) -> List[DataSource]:
        """Fetch all data sources linked to a specific Docker Agent."""
        stmt = (
            select(DataSource)
            .where(DataSource.agent_id == agent_id)
            .order_by(DataSource.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_data_source(
        session: AsyncSession, source: DataSource, data: DataSourceUpdate
    ) -> DataSource:
        """Update data source details."""
        changed = False
        if data.name is not None and data.name.strip() != source.name:
            source.name = data.name.strip()
            changed = True
        if data.role is not None and data.role.lower().strip() != source.role:
            source.role = data.role.lower().strip()
            changed = True
        if data.identifier is not None and data.identifier.strip() != source.identifier:
            source.identifier = data.identifier.strip()
            changed = True

        if not changed:
            return source

        await session.commit()
        await session.refresh(source)
        return source

    @staticmethod
    async def delete_data_source(
        session: AsyncSession, source: DataSource
    ) -> None:
        """Delete data source identity."""
        await session.delete(source)
        await session.commit()
