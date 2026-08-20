"""
Execution Domain Business Services
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Business operations service for MigrationJob execution and progress tracking."""

    @staticmethod
    async def create_execution_job(
        session: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID
    ) -> MigrationJob:
        """
        Creates a new MigrationJob for an approved MigrationPlan.
        Validates plan ownership and assigns target agent.
        """
        stmt = select(MigrationPlan).where(
            MigrationPlan.id == plan_id, MigrationPlan.user_id == user_id
        )
        res = await session.execute(stmt)
        plan = res.scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration plan '{plan_id}' not found or access denied.",
            )

        if plan.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot execute unapproved migration plan. Plan status is '{plan.status}'. User approval is required.",
            )

        if plan.is_valid is False:
            err_msg = (
                plan.validation_errors.get("explanation")
                if plan.validation_errors and isinstance(plan.validation_errors, dict)
                else "Plan validation failed."
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot execute invalid migration plan: {err_msg}",
            )

        job = MigrationJob(
            id=uuid.uuid4(),
            migration_plan_id=plan.id,
            agent_id=plan.agent_id,
            status="queued",
            progress=0.0,
            total_rows=0,
            processed_rows=0,
            successful_rows=0,
            failed_rows=0,
            current_stage="queued",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        # Broadcast start event via WebSocket
        if plan.agent_id:
            await manager.broadcast_to_agent(
                str(plan.agent_id),
                {
                    "event_type": "EXECUTION_QUEUED",
                    "data": {
                        "job_id": str(job.id),
                        "plan_id": str(plan.id),
                        "status": "queued",
                    },
                },
            )

        return job

    @staticmethod
    async def get_pending_tasks_for_agent(
        session: AsyncSession, agent_id: uuid.UUID
    ) -> List[MigrationJob]:
        """
        Returns queued migration jobs assigned to a specific Docker Agent,
        atomically claiming them with row-level locking (SKIP LOCKED) and transitioning
        status to 'preparing' within the same transaction to prevent double execution.
        """
        stmt_select = (
            select(MigrationJob.id)
            .where(
                MigrationJob.agent_id == agent_id,
                MigrationJob.status == "queued",
            )
            .order_by(MigrationJob.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        res_ids = await session.execute(stmt_select)
        job_ids = list(res_ids.scalars().all())

        if not job_ids:
            return []

        stmt_update = (
            update(MigrationJob)
            .where(
                MigrationJob.id.in_(job_ids),
                MigrationJob.status == "queued",
            )
            .values(status="preparing")
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
            MigrationJob.status.in_(["running", "preparing"]),
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
            stmt = stmt.where(MigrationJob.agent_id == agent_id)

        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution job '{job_id}' not found or access denied for this agent.",
            )

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
                    },
                },
            )

        return job
