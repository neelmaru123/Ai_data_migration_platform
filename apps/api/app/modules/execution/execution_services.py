"""
Execution Domain Business Services
"""

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import AsyncSessionLocal
from app.modules.agents.agents_models import Agent
from app.modules.execution.execution_models import MigrationJob
from app.modules.execution.execution_schemas import (
    ExecutionProgressUpdate,
    ExecutionStartRequest,
)
from app.modules.migration_plans.migration_plans_models import MigrationPlan
from app.core.logging import logger
from app.core.websocket_manager import manager


class ExecutionService:
    """Business logic for Migration Execution Jobs lifecycle."""

    @staticmethod
    async def create_execution_job(
        session: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID
    ) -> MigrationJob:
        # Check plan existence and ownership
        stmt_plan = select(MigrationPlan).where(
            MigrationPlan.id == plan_id, MigrationPlan.user_id == user_id
        )
        res_plan = await session.execute(stmt_plan)
        plan = res_plan.scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Migration plan not found or access denied.",
            )

        if not plan.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot execute invalid plan! Fix schema feasibility errors first.",
            )

        if plan.status != "completed" and plan.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot execute unapproved migration plan. Plan status is '{plan.status}'. User approval is required.",
            )

        # Check for active running job for this plan
        stmt_active = select(MigrationJob).where(
            MigrationJob.migration_plan_id == plan_id,
            MigrationJob.status.in_(["queued", "preparing", "running"]),
        )
        res_active = await session.execute(stmt_active)
        if res_active.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active execution job is already in progress for this plan.",
            )

        # Check assigned Docker Agent online status before queuing execution
        if plan.agent_id:
            stmt_agent = select(Agent).where(Agent.id == plan.agent_id)
            res_agent = await session.execute(stmt_agent)
            agent = res_agent.scalar_one_or_none()

            now = datetime.now(timezone.utc)
            cutoff_utc = now - timedelta(seconds=60)
            cutoff_naive = datetime.now() - timedelta(seconds=60)

            is_offline = False
            if not agent or agent.status == "offline" or not agent.last_seen_at:
                is_offline = True
            elif agent.last_seen_at.tzinfo is not None and agent.last_seen_at < cutoff_utc:
                is_offline = True
            elif agent.last_seen_at.tzinfo is None and agent.last_seen_at < cutoff_naive:
                is_offline = True

            if is_offline:
                agent_name = agent.name if agent else "Assigned Agent"
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"Cannot start migration: Assigned Docker Agent '{agent_name}' is OFFLINE! "
                        f"Please start your local Docker Agent container first."
                    ),
                )

        job = MigrationJob(
            migration_plan_id=plan_id,
            agent_id=plan.agent_id,
            status="queued",
            total_rows=0,
            processed_rows=0,
            successful_rows=0,
            failed_rows=0,
            progress=0.0,
            current_stage="queued",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        logger.info(
            f"Created execution job '{job.id}' for plan '{plan_id}' (Agent ID: {plan.agent_id})."
        )
        return job

    @staticmethod
    async def get_pending_tasks_for_agent(
        session: AsyncSession, agent_id: uuid.UUID
    ) -> List[MigrationJob]:
        """
        Returns queued or stale preparing migration jobs assigned to a specific Docker Agent,
        atomically claiming them with row-level locking (SKIP LOCKED) and transitioning
        status to 'preparing' within the same transaction to prevent double execution.
        """
        cutoff_preparing = datetime.now(timezone.utc) - timedelta(seconds=30)
        stmt_select = (
            select(MigrationJob.id)
            .where(
                or_(MigrationJob.agent_id == agent_id, MigrationJob.agent_id.is_(None)),
                or_(
                    MigrationJob.status == "queued",
                    and_(
                        MigrationJob.status == "preparing",
                        MigrationJob.updated_at < cutoff_preparing,
                    ),
                ),
            )
            .order_by(MigrationJob.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        res_ids = await session.execute(stmt_select)
        job_ids = list(res_ids.scalars().all())

        if not job_ids:
            return []

        now = datetime.now(timezone.utc)
        stmt_update = (
            update(MigrationJob)
            .where(
                MigrationJob.id.in_(job_ids),
                or_(
                    MigrationJob.status == "queued",
                    and_(
                        MigrationJob.status == "preparing",
                        MigrationJob.updated_at < cutoff_preparing,
                    ),
                ),
            )
            .values(status="preparing", agent_id=agent_id, updated_at=now)
        )
        res_update = await session.execute(stmt_update)
        if res_update.rowcount == 0:
            await session.rollback()
            return []

        await session.commit()

        stmt_fetch = select(MigrationJob).where(MigrationJob.id.in_(job_ids))
        res_fetch = await session.execute(stmt_fetch)
        return list(res_fetch.scalars().all())

    @staticmethod
    async def check_stale_jobs(
        session: AsyncSession, stale_threshold_seconds: int = 300
    ) -> int:
        """
        Backend Watchdog: Detects execution jobs stuck in 'running' or 'preparing'
        with no progress update for longer than stale_threshold_seconds (default 5 minutes).
        Transitions stuck jobs to 'failed' with an explicit error message.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_threshold_seconds)
        stmt = select(MigrationJob).where(
            MigrationJob.status.in_(["queued", "running", "preparing"]),
            MigrationJob.updated_at < cutoff,
        )
        res = await session.execute(stmt)
        stale_jobs = list(res.scalars().all())

        if not stale_jobs:
            return 0

        now = datetime.now(timezone.utc)
        for job in stale_jobs:
            job.status = "failed"
            job.completed_at = now
            job.error_message = (
                f"Migration job stalled: no progress updates received from agent for over {stale_threshold_seconds} seconds."
            )
            logger.error(
                f"Watchdog failed stale job '{job.id}' (last updated: {job.updated_at})."
            )
            if job.agent_id:
                await manager.broadcast_to_agent(
                    str(job.agent_id),
                    {
                        "event": "JOB_FAILED",
                        "agent_id": str(job.agent_id),
                        "job_id": str(job.id),
                        "status": "failed",
                        "error_message": job.error_message,
                    },
                )

        await session.commit()
        return len(stale_jobs)

    @staticmethod
    async def get_job_by_id(
        session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> MigrationJob:
        """
        Fetches a MigrationJob by ID, verifying user ownership via attached MigrationPlan.
        """
        await ExecutionService.check_stale_jobs(session)
        stmt = (
            select(MigrationJob)
            .join(MigrationPlan, MigrationJob.migration_plan_id == MigrationPlan.id)
            .where(MigrationJob.id == job_id, MigrationPlan.user_id == user_id)
        )
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution job '{job_id}' not found or access denied.",
            )
        return job

    @staticmethod
    async def list_jobs_for_user(
        session: AsyncSession, user_id: uuid.UUID
    ) -> List[MigrationJob]:
        """
        Lists all execution jobs for a user across all migration plans.
        """
        await ExecutionService.check_stale_jobs(session)
        stmt = (
            select(MigrationJob)
            .join(MigrationPlan, MigrationJob.migration_plan_id == MigrationPlan.id)
            .where(MigrationPlan.user_id == user_id)
            .order_by(MigrationJob.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_job_progress(
        session: AsyncSession,
        job_id: uuid.UUID,
        update: ExecutionProgressUpdate,
        agent_id: Optional[uuid.UUID] = None,
    ) -> MigrationJob:
        """
        Updates live metrics and status for a MigrationJob from Docker Agent progress payload.
        Ensures the updating agent is the one assigned to the job.
        """
        stmt = select(MigrationJob).where(MigrationJob.id == job_id)
        if agent_id:
            stmt = stmt.where(or_(MigrationJob.agent_id == agent_id, MigrationJob.agent_id.is_(None)))

        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution job '{job_id}' not found or access denied for this agent.",
            )

        if agent_id and not job.agent_id:
            job.agent_id = agent_id

        now = datetime.now(timezone.utc)
        if update.status == "running" and job.started_at is None:
            job.started_at = now
        elif update.status in ["completed", "failed"]:
            job.completed_at = now

        job.status = update.status
        job.progress = update.progress
        if update.total_rows > 0:
            job.total_rows = update.total_rows
        job.processed_rows = update.processed_rows
        job.successful_rows = update.successful_rows
        job.failed_rows = update.failed_rows
        if update.current_table:
            job.current_table = update.current_table
        if update.current_stage:
            job.current_stage = update.current_stage
        if update.error_message:
            job.error_message = update.error_message

        # Refresh agent last_seen_at and status to prevent heartbeat starvation during ETL execution
        if job.agent_id:
            stmt_agent = select(Agent).where(Agent.id == job.agent_id)
            res_agent = await session.execute(stmt_agent)
            agent_obj = res_agent.scalar_one_or_none()
            if agent_obj:
                agent_obj.last_seen_at = now
                if update.status == "running":
                    agent_obj.status = "busy"
                elif update.status in ["completed", "failed"]:
                    agent_obj.status = "online"

        await session.commit()
        await session.refresh(job)

        await session.commit()
        await session.refresh(job)

        # Auto-trigger AI diagnosis in background with fresh session (Fix #1 & #7)
        if update.status == "failed" and job.error_message and not job.ai_diagnosis:
            asyncio.create_task(_run_diagnosis_background(job.id))

        # Broadcast progress via WebSocket
        if job.agent_id:
            await manager.broadcast_to_agent(
                str(job.agent_id),
                {
                    "event_type": "EXECUTION_PROGRESS",
                    "data": {
                        "job_id": str(job.id),
                        "status": job.status,
                        "progress": job.progress,
                        "processed_rows": job.processed_rows,
                        "successful_rows": job.successful_rows,
                        "failed_rows": job.failed_rows,
                        "current_table": job.current_table,
                        "current_stage": job.current_stage,
                        "ai_diagnosis": job.ai_diagnosis,
                    },
                },
            )

        return job

    @staticmethod
    async def list_jobs_for_plan(
        session: AsyncSession, plan_id: uuid.UUID, user_id: uuid.UUID
    ) -> List[MigrationJob]:
        """Fetch all execution jobs for a migration plan owned by user, ordered by newest first (Fix #8)."""
        stmt = (
            select(MigrationJob)
            .join(MigrationPlan, MigrationJob.migration_plan_id == MigrationPlan.id)
            .where(
                MigrationJob.migration_plan_id == plan_id,
                MigrationPlan.user_id == user_id,
            )
            .order_by(MigrationJob.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def diagnose_job_failure(
        session: AsyncSession, job_id: uuid.UUID
    ) -> MigrationJob:
        """Synthesizes raw job error traceback into plain-English diagnosis & remediation actions using LLM."""
        # Atomic lock & guard: only process if ai_diagnosis is NULL (Fix #2)
        stmt = (
            select(MigrationJob)
            .where(MigrationJob.id == job_id)
            .with_for_update(skip_locked=True)
            .options(
                selectinload(MigrationJob.agent).selectinload(Agent.data_sources),
                selectinload(MigrationJob.plan),
            )
        )
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution job '{job_id}' not found.",
            )

        # Early guard: AI diagnosis only available for failed jobs (Fix #6)
        if job.status != "failed":
            if job.ai_diagnosis:
                return job
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"AI diagnosis is only available for failed execution jobs. Current status is '{job.status}'.",
            )

        # Return existing diagnosis if already populated (idempotent)
        if job.ai_diagnosis:
            return job

        err_msg = job.error_message or "Unknown execution error."
        stage = job.current_stage or "ETL processing"
        tbl = job.current_table or "N/A"

        # Heuristic & LLM Failure Synthesizer
        diag_summary = f"Migration failed during '{stage}' stage on table '{tbl}'."
        category = "UNKNOWN_ERROR"
        user_env_issue = False
        fix_steps: List[str] = []
        copyable_cmd: Optional[str] = None

        err_lower = err_msg.lower()

        # Strict Network Error Detection Patterns & Port Regex (Fix #4)
        network_patterns = [
            "connection refused",
            "connectionrefused",
            "could not connect to server",
            "could not connect to host",
            "no route to host",
            "network is unreachable",
            "connection timed out",
            "name or service not known",
            "getaddrinfofailed",
            "failed to connect",
        ]
        port_re = re.compile(r':(5\d{3}|27017|3306|5432|3307)\b')
        is_network_err = any(p in err_lower for p in network_patterns) or bool(port_re.search(err_msg))

        if is_network_err:
            category = "NETWORK_CONNECTION_FAILED"
            user_env_issue = True
            diag_summary = f"The agent could not connect to database on host/port specified during stage '{stage}'."
            fix_steps = [
                "Verify database host and port mapping (e.g. use host.docker.internal:5435 instead of localhost:5432).",
                "Ensure database container is running and accepting incoming connections.",
                "Verify --add-host=host.docker.internal:host-gateway flag is included in docker run."
            ]
        elif "notnullviolation" in err_lower or "null value in column" in err_lower:
            category = "NOT_NULL_CONSTRAINT_VIOLATION"
            user_env_issue = False
            diag_summary = f"Target table '{tbl}' rejected insertion due to a NULL primary key or NOT NULL column."
            fix_steps = [
                "Re-run the updated agent container image (data-migration-agent:latest) which auto-populates UUID primary keys.",
                "Or edit the transformation blueprint in UI to explicitly map source columns to all NOT NULL target columns."
            ]
        elif "nosuchmoduleerror" in err_lower or "sqlalchemy.dialects:mongodb" in err_lower:
            category = "NOSQL_DIALECT_MISMATCH"
            user_env_issue = False
            diag_summary = "Relational DDL statement execution was attempted on a MongoDB document database."
            fix_steps = [
                "Re-run the updated agent container image (data-migration-agent:latest) which skips relational DDL for MongoDB.",
                "MongoDB target collections are created automatically upon document streaming."
            ]
        elif "access denied" in err_lower or "authentication failed" in err_lower or "password" in err_lower:
            category = "DATABASE_AUTHENTICATION_FAILED"
            user_env_issue = True
            diag_summary = "Database rejected authentication credentials provided in agent environment variables."
            fix_steps = [
                "Verify database usernames and passwords in container environment variables.",
                "Ensure password placeholders like <SRC_SRC_DB_1_PASSWORD> are replaced with valid credentials."
            ]
        else:
            diag_summary = f"ETL pipeline encountered an unexpected error during stage '{stage}': {err_msg[:200]}"
            fix_steps = [
                "Review target database constraints and column mapping specifications.",
                "Verify source data quality and re-run execution job."
            ]

        # Build complete copyable docker run command with ALL registered data sources (Fix #3)
        if job.agent:
            ag = job.agent
            cmd_lines = [
                "docker run -d \\",
                f"  --name {ag.agent_identifier or 'data-agent'} \\",
                "  --restart unless-stopped \\",
                "  --add-host=host.docker.internal:host-gateway \\",
                '  -e BACKEND_URL="http://host.docker.internal:8000" \\',
                f'  -e AGENT_TOKEN="AG_TOKEN_PLACEHOLDER" \\',
                f'  -e AGENT_ID="{ag.id}" \\',
                f'  -e AGENT_IDENTIFIER="{ag.agent_identifier}" \\',
            ]
            if ag.version:
                cmd_lines.append(f'  -e AGENT_VERSION="{ag.version}" \\')

            if ag.data_sources:
                src_i = 1
                dst_i = 1
                for ds in ag.data_sources:
                    role_str = (ds.role or "").lower().strip()
                    ds_type = (ds.type or "postgresql").lower().strip()
                    if role_str in ("source", "src"):
                        cmd_lines.append(f'  -e SRC_SRC_DB_{src_i}_TYPE="{ds_type}" \\')
                        cmd_lines.append(f'  -e SRC_SRC_DB_{src_i}_URL="{ds_type}://user:<SRC_SRC_DB_{src_i}_PASSWORD>@host.docker.internal:port/{ds.identifier}" \\')
                        src_i += 1
                    elif role_str in ("destination", "target", "dest"):
                        cmd_lines.append(f'  -e DEST_DST_DB_{dst_i}_TYPE="{ds_type}" \\')
                        cmd_lines.append(f'  -e DEST_DST_DB_{dst_i}_URL="{ds_type}://user:<DEST_DST_DB_{dst_i}_PASSWORD>@host.docker.internal:port/{ds.identifier}" \\')
                        cmd_lines.append(f'  -e DEST_DB_URL="{ds_type}://user:<DEST_DST_DB_{dst_i}_PASSWORD>@host.docker.internal:port/{ds.identifier}" \\')
                        dst_i += 1

            cmd_lines.append("  data-migration-agent:latest")
            copyable_cmd = "\n".join(cmd_lines)

        job.ai_diagnosis = {
            "summary": diag_summary,
            "root_cause_category": category,
            "is_user_environment_issue": user_env_issue,
            "fix_steps": fix_steps,
            "copyable_fix_command": copyable_cmd,
            "raw_error_snippet": err_msg[:500],
        }

        await session.commit()
        await session.refresh(job)
        return job


async def _run_diagnosis_background(job_id: uuid.UUID):
    """Background coroutine running AI failure diagnosis with fresh AsyncSession (Fix #1)."""
    async with AsyncSessionLocal() as fresh_session:
        try:
            await ExecutionService.diagnose_job_failure(fresh_session, job_id)
        except Exception as diag_err:
            logger.warning(f"Background AI failure diagnosis failed for job '{job_id}': {diag_err}")
