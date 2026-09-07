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
from sqlalchemy import and_
from app.modules.sources.sources_models import DataSource
from app.modules.sources.sources_schemas import DataSourceResponse

# ---------------------------------------------------------------------------
# Option C — Adaptive Idle Heartbeat thresholds
# ---------------------------------------------------------------------------
_IDLE_MODE_THRESHOLD_SECONDS = 300   # 5 minutes: switch to 5-min standby heartbeat
# ---------------------------------------------------------------------------


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

        # 1b. Check for target DB uniqueness across user agents
        if data.data_sources:
            dest_identifiers = [
                ds.identifier.strip().lower()
                for ds in data.data_sources
                if ds.role and ds.role.lower().strip() in ("destination", "target", "dest")
            ]
            if dest_identifiers:
                stmt_existing_dest = (
                    select(DataSource, Agent)
                    .join(Agent, DataSource.agent_id == Agent.id)
                    .where(
                        Agent.user_id == user_id,
                        DataSource.role.in_(["destination", "target", "dest"]),
                        DataSource.identifier.in_(dest_identifiers),
                    )
                )
                res_dest = await session.execute(stmt_existing_dest)
                existing_match = res_dest.first()
                if existing_match:
                    existing_ds, existing_agent = existing_match
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Target database '{existing_ds.name}' (identifier: '{existing_ds.identifier}') "
                            f"is already registered and in use by Agent '{existing_agent.name}'. "
                            f"To prevent data corruption, please specify a unique target database for this new agent."
                        ),
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
    ) -> AgentResponse:
        """
        Process periodic heartbeat ping from authenticated agent.
        Updates agent status, version, last_seen_at, and data sources health diagnostics.
        Emits AGENT_CONNECTED on transition to online, AGENT_DISCONNECTED on offline, or AGENT_HEARTBEAT on recurring pings.
        Returns AgentResponse with optional action directive (ENTER_IDLE_MODE, RESUME_ACTIVE_MODE, SHUTDOWN).
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

        # Update fatal stopping error if reported
        if heartbeat.error_message or heartbeat.status == "error":
            agent.last_error = heartbeat.error_message
            agent.error_category = heartbeat.error_category or "FATAL_ERROR"
            agent.last_error_at = now
            agent.status = "error"
        elif heartbeat.status == "online":
            # Agent recovered and is healthy online — clear active fatal stopping error
            agent.last_error = None
            agent.error_category = None

        # Update attached Data Sources health diagnostics if provided in heartbeat
        data_sources_summary = []
        if heartbeat.data_sources and agent.data_sources:
            # Build comprehensive source map to match both raw and prefixed identifiers
            source_map = {}
            for ds in agent.data_sources:
                ident_lower = ds.identifier.lower().strip()
                source_map[ident_lower] = ds

                clean_id = ident_lower
                if clean_id.startswith("src_"):
                    clean_id = clean_id[4:]
                elif clean_id.startswith("dest_"):
                    clean_id = clean_id[5:]
                elif clean_id.startswith("dst_"):
                    clean_id = clean_id[4:]

                source_map[clean_id] = ds
                source_map[f"src_{clean_id}"] = ds
                source_map[f"dest_{clean_id}"] = ds
                source_map[f"dst_{clean_id}"] = ds

            # Fallback for single source or single destination data sources
            sources_by_role = {"source": [], "destination": []}
            for ds in agent.data_sources:
                role = (ds.role or "").lower()
                if "src" in role or "source" in role:
                    sources_by_role["source"].append(ds)
                elif "dest" in role or "dst" in role or "target" in role:
                    sources_by_role["destination"].append(ds)

            if len(sources_by_role["destination"]) == 1:
                single_dest = sources_by_role["destination"][0]
                for generic_key in ("db", "dest", "dest_db", "dst", "dst_db", "target"):
                    if generic_key not in source_map:
                        source_map[generic_key] = single_dest

            if len(sources_by_role["source"]) == 1:
                single_src = sources_by_role["source"][0]
                for generic_key in ("source", "source_db", "src", "src_db"):
                    if generic_key not in source_map:
                        source_map[generic_key] = single_src

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
                    logger.debug(
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

        # ---------------------------------------------------------------
        # Option A + C: Determine backend control directive
        # Priority order:
        #   1. Active job → RESUME_ACTIVE_MODE (fast heartbeat)
        #   2. Most recent job completed successfully → SHUTDOWN (container exits)
        #   3. Idle 5+ min with no successful job → ENTER_IDLE_MODE (standby)
        # ---------------------------------------------------------------
        action: Optional[str] = None
        action_reason: Optional[str] = None

        if agent.idle_since is not None and heartbeat.status != "offline":
            # Priority 1: Check for any currently active/queued job
            stmt_active = select(MigrationJob).where(
                MigrationJob.agent_id == agent.id,
                MigrationJob.status.in_(["queued", "preparing", "running"]),
            )
            res_active = await session.execute(stmt_active)
            active_job = res_active.scalar_one_or_none()

            if active_job:
                # Job is running — clear idle marker, restore fast heartbeat
                agent.idle_since = None
                await session.commit()
                action = "RESUME_ACTIVE_MODE"
                action_reason = (
                    f"Active migration job '{active_job.id}' detected. "
                    "Restoring 20-second heartbeat frequency."
                )
                logger.info(
                    f"Agent '{agent.name}' ({agent.id}): active job detected — issuing RESUME_ACTIVE_MODE."
                )
            else:
                # Priority 2: Check if the most recent job completed successfully
                # If so, the migration is done — shut down the container (Option A auto-trigger).
                stmt_latest_job = (
                    select(MigrationJob)
                    .where(MigrationJob.agent_id == agent.id)
                    .order_by(MigrationJob.completed_at.desc().nullslast())
                    .limit(1)
                )
                res_latest = await session.execute(stmt_latest_job)
                latest_job = res_latest.scalar_one_or_none()

                if latest_job and latest_job.status == "completed":
                    # Check if the job completed recently (within 120s).
                    # If completed long ago, the container was restarted by the user to perform new tasks.
                    is_recent_completion = False
                    if latest_job.completed_at:
                        comp_time = (
                            latest_job.completed_at
                            if latest_job.completed_at.tzinfo
                            else latest_job.completed_at.replace(tzinfo=timezone.utc)
                        )
                        if (now - comp_time).total_seconds() <= 120:
                            is_recent_completion = True

                    if is_recent_completion:
                        # Option A: Migration finished recently — issue SHUTDOWN directive
                        action = "SHUTDOWN"
                        action_reason = (
                            f"Migration job '{latest_job.id}' completed successfully. "
                            "Initiating graceful container shutdown."
                        )
                        logger.info(
                            f"Agent '{agent.name}' ({agent.id}): job '{latest_job.id}' completed recently — "
                            "issuing SHUTDOWN directive."
                        )
                    else:
                        # Job completed in a prior run; agent was restarted by user for new work.
                        # Apply Option C standby rules instead of auto-shutdown.
                        idle_since_aware = (
                            agent.idle_since
                            if agent.idle_since.tzinfo
                            else agent.idle_since.replace(tzinfo=timezone.utc)
                        )
                        idle_seconds = (now - idle_since_aware).total_seconds()
                        if idle_seconds >= 300:
                            action = "ENTER_IDLE_MODE"
                            action_reason = f"Agent idle for {int(idle_seconds)}s — entering low-power standby mode."
                        else:
                            action = "RESUME_ACTIVE_MODE"
                else:
                    # Priority 3: No completed job (never ran, or last job failed / was queued)
                    # Apply Option C: slow down heartbeat after 5-min idle grace window.
                    idle_since_aware = (
                        agent.idle_since
                        if agent.idle_since.tzinfo
                        else agent.idle_since.replace(tzinfo=timezone.utc)
                    )
                    idle_seconds = (now - idle_since_aware).total_seconds()

                    if idle_seconds >= _IDLE_MODE_THRESHOLD_SECONDS:
                        # Option C: 5+ minutes idle — slow heartbeat, container stays alive
                        action = "ENTER_IDLE_MODE"
                        action_reason = (
                            f"No active migration tasks for {int(idle_seconds // 60)} minutes. "
                            "Switching to 5-minute standby heartbeat. Container remains active and ready."
                        ) 
                        logger.info(
                            f"Agent '{agent.name}' ({agent.id}): idle for {int(idle_seconds // 60)}m "
                            "— issuing ENTER_IDLE_MODE."
                        )
                    # else: within 5-min grace window, no directive issued yet

        # Broadcast real-time signal to Web App subscribers
        await manager.broadcast_to_agent(
            str(agent.id),
            {
                "event": event_name,
                "agent_id": str(agent.id),
                "status": agent.status,
                "version": agent.version,
                "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
                "last_error": agent.last_error,
                "error_category": agent.error_category,
                "last_error_at": agent.last_error_at.isoformat() if agent.last_error_at else None,
                "action": action,
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

        # Build and return AgentResponse with embedded control directive
        return AgentResponse(
            id=agent.id,
            user_id=agent.user_id,
            name=agent.name,
            agent_identifier=agent.agent_identifier,
            status=agent.status,
            version=agent.version,
            api_token=None,  # Never expose raw token in responses
            last_seen_at=agent.last_seen_at,
            last_error=agent.last_error,
            error_category=agent.error_category,
            last_error_at=agent.last_error_at,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            action=action,
            action_reason=action_reason,
        )

    @staticmethod
    async def record_fatal_error(
        session: AsyncSession,
        agent_id: uuid.UUID,
        error_message: str,
        error_category: str = "FATAL_ERROR",
    ) -> AgentResponse:
        """
        Records an emergency fatal error reported by an agent (e.g. startup crash, token failure)
        and broadcasts real-time alert to UI subscribers.
        """
        stmt = select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.data_sources))
        res = await session.execute(stmt)
        agent = res.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        now = datetime.now(timezone.utc)
        agent.status = "error"
        agent.last_error = error_message
        agent.error_category = error_category
        agent.last_error_at = now
        await session.commit()
        await session.refresh(agent)

        await manager.broadcast_to_agent(
            str(agent.id),
            {
                "event": "AGENT_STATUS_CHANGED",
                "agent_id": str(agent.id),
                "status": "error",
                "last_error": agent.last_error,
                "error_category": agent.error_category,
                "last_error_at": agent.last_error_at.isoformat(),
            },
        )

        return AgentResponse(
            id=agent.id,
            user_id=agent.user_id,
            name=agent.name,
            agent_identifier=agent.agent_identifier,
            status=agent.status,
            version=agent.version,
            api_token=None,
            last_seen_at=agent.last_seen_at,
            last_error=agent.last_error,
            error_category=agent.error_category,
            last_error_at=agent.last_error_at,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            action=None,
            action_reason=None,
        )

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
            # Keep agent online if job is actively reporting progress AND agent was seen recently
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
            agent.error_category = "DISCONNECTED_UNEXPECTEDLY"
            agent.last_error = (
                f"Agent stopped reporting heartbeats for over {stale_threshold_seconds}s. "
                "The Docker container may have exited, crashed, or lost network connectivity."
            )
            agent.last_error_at = datetime.now(timezone.utc)
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
                    "last_error": agent.last_error,
                    "error_category": agent.error_category,
                    "last_error_at": agent.last_error_at.isoformat(),
                    "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
                },
            )

            # 2. Check for active/running/queued migration jobs linked to this dead agent
            stmt_jobs = select(MigrationJob).where(
                MigrationJob.agent_id == agent.id,
                MigrationJob.status.in_(["queued", "running", "preparing"]),
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

        from app.modules.execution.execution_services import ExecutionService
        stale_job_failures = await ExecutionService.check_stale_jobs(session, stale_threshold_seconds=300)

        if stale_agent_count > 0 or failed_jobs_count > 0:
            await session.commit()

        return {
            "stale_agents_marked_offline": stale_agent_count,
            "failed_jobs_recovered": failed_jobs_count + stale_job_failures,
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
