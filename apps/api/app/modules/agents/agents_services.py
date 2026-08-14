"""
Agents Domain Services (Business logic & Atomic operations boundary)
"""

import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.websocket_manager import manager
from app.modules.agents.agents_command_generator import AgentCommandGenerator
from app.modules.agents.agents_dependencies import hash_agent_token
from app.modules.agents.agents_models import Agent
from app.modules.agents.agents_schemas import (
    AgentCreate,
    AgentDetailResponse,
    AgentDockerCommandResponse,
    AgentHeartbeat,
    AgentResponse,
    AgentUpdate,
)
from app.modules.sources.sources_models import DataSource
from app.modules.sources.sources_schemas import DataSourceResponse


class AgentService:
    """Business operations service for Agent domain entity and concurrent Data Source creation."""

    @staticmethod
    async def create_agent(
        session: AsyncSession, user_id: uuid.UUID, data: AgentCreate
    ) -> AgentDetailResponse:
        """
        Create a new Docker Agent.
        Generates a secure API token, stores its SHA-256 hash, and sets initial status to 'offline'.
        Concurrently creates initial Data Source identities (source and destination DBs)
        in the same atomic transaction if provided.
        Generates copy-paste ready Docker run commands with credential placeholders and returns them.
        """
        # 1. Check for identifier uniqueness
        stmt_check = select(Agent).where(Agent.agent_identifier == data.agent_identifier.strip())
        res_check = await session.execute(stmt_check)
        if res_check.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An agent with identifier '{data.agent_identifier}' already exists.",
            )

        # 2. Generate secure agent API token & SHA-256 hash
        raw_token = f"ag_live_{secrets.token_urlsafe(32)}"
        token_hash = hash_agent_token(raw_token)

        # 3. Instantiate Agent (initial status is offline until agent container boots and sends heartbeat)
        agent = Agent(
            user_id=user_id,
            name=data.name.strip(),
            agent_identifier=data.agent_identifier.strip(),
            api_token_hash=token_hash,
            version=data.version.strip() if data.version else None,
            status="offline",
            last_seen_at=None,
        )
        session.add(agent)
        await session.flush()  # Generates agent.id

        # 4. Create concurrent initial Data Sources if provided
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

        # 5. Fetch newly created agent entity with data_sources eagerly loaded
        fetched_agent = await AgentService.get_agent_by_id(session, agent.id)
        if fetched_agent is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve newly created agent entity.",
            )

        # 6. Generate Docker commands configured with token and DB credential placeholders
        cmd_payload = AgentCommandGenerator.generate_command_payload(
            agent=fetched_agent,
            data_sources=fetched_agent.data_sources,
            raw_token=raw_token,
        )

        # 7. Construct AgentDetailResponse with all dynamic docker commands & raw api_token included
        base_dict = AgentResponse.model_validate(fetched_agent).model_dump()
        response_dict = {
            **base_dict,
            "data_sources": [
                DataSourceResponse.model_validate(ds) for ds in (fetched_agent.data_sources or [])
            ],
            "api_token": raw_token,
            "docker_command": cmd_payload["docker_command"],
            "docker_command_powershell": cmd_payload["docker_command_powershell"],
            "docker_command_oneline": cmd_payload["docker_command_oneline"],
            "env_template": cmd_payload["env_template"],
        }

        return AgentDetailResponse(**response_dict)

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
        """
        Process periodic heartbeat ping from authenticated agent.
        Updates status, last_seen_at timestamp, and broadcasts real-time status signal over WebSocket.
        Emits AGENT_CONNECTED on offline->online transition, or AGENT_HEARTBEAT on recurring pings.
        """
        previous_status = agent.status
        agent.status = heartbeat.status.strip()
        agent.last_seen_at = datetime.now(timezone.utc)
        if heartbeat.version:
            agent.version = heartbeat.version.strip()

        await session.commit()
        await session.refresh(agent)

        event_name = (
            "AGENT_CONNECTED"
            if previous_status != "online" and agent.status == "online"
            else "AGENT_HEARTBEAT"
        )

        # Broadcast real-time signal to Web App subscribers
        await manager.broadcast_to_agent(
            str(agent.id),
            {
                "event": event_name,
                "agent_id": str(agent.id),
                "status": agent.status,
                "version": agent.version,
                "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
            },
        )

        return agent

    @staticmethod
    async def delete_agent(session: AsyncSession, agent: Agent) -> None:
        """Delete an agent (cascade deletes linked data sources)."""
        await session.delete(agent)
        await session.commit()

    @staticmethod
    def get_agent_docker_command(agent: Agent) -> AgentDockerCommandResponse:
        """
        Generate Docker run commands and .env configuration template for an existing agent.
        Uses placeholder token since raw token is not stored in plaintext.
        """
        cmd_payload = AgentCommandGenerator.generate_command_payload(
            agent=agent,
            data_sources=agent.data_sources,
        )
        return AgentDockerCommandResponse(
            agent_id=agent.id,
            agent_identifier=agent.agent_identifier,
            docker_command=cmd_payload["docker_command"],
            docker_command_powershell=cmd_payload["docker_command_powershell"],
            docker_command_oneline=cmd_payload["docker_command_oneline"],
            env_template=cmd_payload["env_template"],
        )
