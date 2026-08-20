"""
Agents Domain Services (Business logic & Atomic operations boundary)
"""

from datetime import datetime, timedelta, timezone
import secrets
from typing import List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
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
from app.modules.execution.execution_models import MigrationJob
from app.modules.sources.sources_models import DataSource
from app.modules.sources.sources_schemas import DataSourceResponse


class AgentService:
    """Business operations service for Agent domain entity and concurrent Data Source creation."""

    @staticmethod
    async def create_agent(
        session: AsyncSession, user_id: uuid.UUID, data: AgentCreate
    ) -> AgentDetailResponse:
        """
        Create a new Docker Agent for the given user.
        Uniqueness of agent_identifier is enforced per user.
        Generates a secure API token, stores its SHA-256 hash, and sets initial status to 'offline'.
        Concurrently creates initial Data Source identities (source and destination DBs)
        in the same atomic transaction if provided.
        Generates copy-paste ready Docker run commands with credential placeholders and returns them.
        """
        # 1. Check for per-user identifier uniqueness
        stmt_check = select(Agent).where(
            Agent.user_id == user_id,
            Agent.agent_identifier == data.agent_identifier.strip(),
        )
        res_check = await session.execute(stmt_check)
        if res_check.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You already have an agent with identifier '{data.agent_identifier}'.",
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

        return AgentDetailResponse.model_validate(response_dict)

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
        """
        Update agent user-facing attributes (name, version).
        Agent status is strictly managed via authenticated heartbeats and background watchdog.
        """
        changed = False
        if data.name is not None and data.name.strip() != agent.name:
            agent.name = data.name.strip()
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
        Updates agent status, version, last_seen_at, and data sources health diagnostics.
        Emits AGENT_CONNECTED on transition to online, AGENT_DISCONNECTED on offline, or AGENT_HEARTBEAT on recurring pings.
        """
        now = datetime.now(timezone.utc)

        # Rate-limiting throttle guard: only throttle identical status pings arriving < 0.1s after the previous one
        if agent.last_seen_at and heartbeat.status == agent.status and not heartbeat.data_sources:
            last_seen = agent.last_seen_at if agent.last_seen_at.tzinfo else agent.last_seen_at.replace(tzinfo=timezone.utc)
            if (now - last_seen).total_seconds() < 0.1:
                return agent

        previous_status = agent.status
        agent.status = heartbeat.status.strip()
        agent.last_seen_at = now
        if heartbeat.version:
            agent.version = heartbeat.version.strip()

        # Update attached Data Sources health diagnostics if provided in heartbeat
        data_sources_summary = []
        if heartbeat.data_sources and agent.data_sources:
            # Build comprehensive source map to match both raw and prefixed identifiers
            source_map = {}
            for ds in agent.data_sources:
                ident_lower = ds.identifier.lower().strip()
                source_map[ident_lower] = ds
                if ident_lower.startswith("src_"):
                    source_map[ident_lower[4:]] = ds
                elif ident_lower.startswith("dest_"):
                    source_map[ident_lower[5:]] = ds
                else:
                    source_map[f"src_{ident_lower}"] = ds
                    source_map[f"dest_{ident_lower}"] = ds

            updated_data_sources = set()
            for report in heartbeat.data_sources:
                rep_id = report.identifier.lower().strip()
                if rep_id in source_map:
                    ds = source_map[rep_id]
                    if ds.id in updated_data_sources:
                        continue
                    updated_data_sources.add(ds.id)

                    if report.is_healthy:
                        ds.status = "healthy"
                        ds.last_error = None
                    else:
                        ds.status = report.error_type if report.error_type else "unreachable"
                        ds.last_error = report.error_message
                    ds.last_checked_at = now
                    data_sources_summary.append({
                        "id": str(ds.id),
                        "identifier": ds.identifier,
                        "name": ds.name,
                        "role": ds.role,
                        "status": ds.status,
                        "last_error": ds.last_error,
                        "last_checked_at": ds.last_checked_at.isoformat(),
                    })
                else:
                    logger.warning(
                        f"Unmatched health report identifier '{report.identifier}' for agent '{agent.id}'"
                    )

        await session.commit()
        await session.refresh(agent)

        if heartbeat.status == "offline":
            event_name = "AGENT_DISCONNECTED"
        elif previous_status != "online" and agent.status == "online":
            event_name = "AGENT_CONNECTED"
        elif previous_status != agent.status:
            event_name = "AGENT_STATUS_CHANGED"
        else:
            event_name = "AGENT_HEARTBEAT"

        # Broadcast real-time signal to Web App subscribers
        await manager.broadcast_to_agent(
            str(agent.id),
            {
                "event": event_name,
                "agent_id": str(agent.id),
                "status": agent.status,
                "version": agent.version,
                "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
                "data_sources": data_sources_summary if data_sources_summary else [
                    {
                        "id": str(ds.id),
                        "identifier": ds.identifier,
                        "name": ds.name,
                        "role": ds.role,
                        "status": ds.status,
                        "last_error": ds.last_error,
                        "last_checked_at": ds.last_checked_at.isoformat() if ds.last_checked_at else None,
                    }
                    for ds in (agent.data_sources or [])
                ],
            },
        )

        return agent

    @staticmethod
    async def check_stale_agents_and_jobs(
        session: AsyncSession, stale_threshold_seconds: int = 60
    ) -> dict[str, int]:
        """
        Watchdog task: Checks for agents that have not reported a heartbeat within the stale threshold.
        Marks them as 'offline', triggers WebSocket disconnections, and fails any orphaned migration jobs.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=stale_threshold_seconds)

        # 1. Find all active agents that exceeded the timeout threshold
        stmt_stale = (
            select(Agent)
            .where(
                Agent.status.in_(["online", "busy", "degraded"]),
                or_(
                    Agent.last_seen_at < cutoff_time,
                    Agent.last_seen_at.is_(None),
                ),
            )
            .options(selectinload(Agent.data_sources))
        )
        res_stale = await session.execute(stmt_stale)
        stale_agents = list(res_stale.scalars().all())

        stale_agent_count = len(stale_agents)
        failed_jobs_count = 0

        for agent in stale_agents:
            # Check if there is an active job updated recently AND agent was seen recently (keeps agent alive during progress reports)
            stmt_active_job = select(MigrationJob).where(
                MigrationJob.agent_id == agent.id,
                MigrationJob.status.in_(["running", "preparing"]),
                MigrationJob.updated_at >= cutoff_time,
            )
            res_active_job = await session.execute(stmt_active_job)
            active_job = res_active_job.scalar_one_or_none()
            if active_job and agent.last_seen_at and agent.last_seen_at >= cutoff_time:
                continue

            agent.status = "offline"
            logger.warning(
                f"Agent '{agent.name}' ({agent.id}) timed out (last seen: {agent.last_seen_at}). Marked offline."
            )

            # Broadcast real-time signal to Web App subscribers
            await manager.broadcast_to_agent(
                str(agent.id),
                {
                    "event": "AGENT_DISCONNECTED",
                    "agent_id": str(agent.id),
                    "status": "offline",
                    "reason": "heartbeat_timeout",
                    "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
                },
            )

            # 2. Check for active/running migration jobs linked to this dead agent
            stmt_jobs = select(MigrationJob).where(
                MigrationJob.agent_id == agent.id,
                MigrationJob.status.in_(["running", "preparing"]),
            )
            res_jobs = await session.execute(stmt_jobs)
            running_jobs = list(res_jobs.scalars().all())

            for job in running_jobs:
                job.status = "failed"
                job.error_message = "Agent disconnected or timed out during migration execution."
                job.completed_at = datetime.now(timezone.utc)
                failed_jobs_count += 1
                logger.error(
                    f"MigrationJob '{job.id}' failed due to agent '{agent.id}' timeout."
                )

                # Broadcast job failure event
                await manager.broadcast_to_agent(
                    str(agent.id),
                    {
                        "event": "JOB_FAILED",
                        "agent_id": str(agent.id),
                        "job_id": str(job.id),
                        "status": "failed",
                        "error_message": job.error_message,
                    },
                )

        if stale_agent_count > 0 or failed_jobs_count > 0:
            await session.commit()

        return {
            "stale_agents_marked_offline": stale_agent_count,
            "failed_jobs_recovered": failed_jobs_count,
        }

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
            environment_variables=cmd_payload["environment_variables"],
        )
