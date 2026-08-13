"""
Agents Domain Services (Business logic & Atomic operations boundary)
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.agents_models import Agent
from app.modules.agents.agents_schemas import AgentCreate, AgentHeartbeat, AgentUpdate
from app.modules.sources.sources_models import DataSource


class AgentService:
    """Business operations service for Agent domain entity and concurrent Data Source creation."""

    @staticmethod
    async def create_agent(
        session: AsyncSession, user_id: uuid.UUID, data: AgentCreate
    ) -> Agent:
        """
        Create a new Docker Agent.
        Concurrently creates initial Data Source identities (source and destination DBs)
        in the same atomic transaction if provided.
        """
        # 1. Check for identifier uniqueness
        stmt_check = select(Agent).where(Agent.agent_identifier == data.agent_identifier.strip())
        res_check = await session.execute(stmt_check)
        if res_check.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An agent with identifier '{data.agent_identifier}' already exists.",
            )

        # 2. Instantiate Agent
        agent = Agent(
            user_id=user_id,
            name=data.name.strip(),
            agent_identifier=data.agent_identifier.strip(),
            version=data.version.strip() if data.version else None,
            status="online",
            last_seen_at=datetime.now(timezone.utc),
        )
        session.add(agent)
        await session.flush()  # Generates agent.id

        # 3. Create concurrent initial Data Sources if provided
        if data.data_sources:
            for ds_input in data.data_sources:
                ds_obj = DataSource(
                    agent_id=agent.id,
                    name=ds_input.name.strip(),
                    type=ds_input.type.lower().strip(),
                    role=ds_input.role.lower().strip(),
                    identifier=ds_input.identifier.strip(),
                )
                session.add(ds_obj)

        await session.commit()

        # 4. Return agent re-queried with data_sources relationship loaded
        return await AgentService.get_agent_by_id(session, agent.id)  # type: ignore[return-value]

    @staticmethod
    async def get_agent_by_id(
        session: AsyncSession, agent_id: uuid.UUID
    ) -> Optional[Agent]:
        """Fetch agent by primary key UUID with data_sources relationship eagerly loaded."""
        stmt = (
            select(Agent)
            .where(Agent.id == agent_id)
            .options(selectinload(Agent.data_sources))
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_agent_by_identifier(
        session: AsyncSession, agent_identifier: str
    ) -> Optional[Agent]:
        """Fetch agent by unique agent_identifier."""
        stmt = (
            select(Agent)
            .where(Agent.agent_identifier == agent_identifier.strip())
            .options(selectinload(Agent.data_sources))
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_agents_by_user(
        session: AsyncSession, user_id: uuid.UUID
    ) -> List[Agent]:
        """Fetch all agents owned by a specific user."""
        stmt = (
            select(Agent)
            .where(Agent.user_id == user_id)
            .options(selectinload(Agent.data_sources))
            .order_by(Agent.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_agent(
        session: AsyncSession, agent: Agent, data: AgentUpdate
    ) -> Agent:
        """Update agent attributes."""
        changed = False
        if data.name is not None and data.name.strip() != agent.name:
            agent.name = data.name.strip()
            changed = True
        if data.status is not None and data.status.strip() != agent.status:
            agent.status = data.status.strip()
            changed = True
        if data.version is not None and data.version.strip() != agent.version:
            agent.version = data.version.strip()
            changed = True

        if not changed:
            return agent

        await session.commit()
        return await AgentService.get_agent_by_id(session, agent.id)  # type: ignore[return-value]

    @staticmethod
    async def process_agent_heartbeat(
        session: AsyncSession, agent: Agent, heartbeat: AgentHeartbeat
    ) -> Agent:
        """Process periodic heartbeat ping from agent."""
        agent.status = heartbeat.status.strip()
        agent.last_seen_at = datetime.now(timezone.utc)
        if heartbeat.version:
            agent.version = heartbeat.version.strip()

        await session.commit()
        await session.refresh(agent)
        return agent

    @staticmethod
    async def delete_agent(session: AsyncSession, agent: Agent) -> None:
        """Delete an agent (cascade deletes linked data sources)."""
        await session.delete(agent)
        await session.commit()
