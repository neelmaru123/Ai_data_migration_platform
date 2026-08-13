"""
Agents Domain Services (Business logic boundary)
"""

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.agents_models import Agent


class AgentService:
    """Business operations service for Agent domain entity."""

    @staticmethod
    async def get_agent_by_id(
        session: AsyncSession, agent_id: uuid.UUID
    ) -> Optional[Agent]:
        """Fetch agent by primary key UUID."""
        stmt = select(Agent).where(Agent.id == agent_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
