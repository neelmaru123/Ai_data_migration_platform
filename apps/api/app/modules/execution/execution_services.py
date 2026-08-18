"""
Execution Domain Business Services
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.agents_models import Agent
from app.modules.execution.execution_models import MigrationJob
from app.modules.execution.execution_schemas import (
    ExecutionProgressUpdate,
    ExecutionStartRequest,
)
from app.modules.migration_plans.migration_plans_models import MigrationPlan
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
        Returns queued or preparing migration jobs assigned to a specific Docker Agent.
        """
        stmt = (
            select(MigrationJob)
            .where(
                MigrationJob.agent_id == agent_id,
                MigrationJob.status.in_(["queued", "preparing"]),
            )
            .order_by(MigrationJob.created_at.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_job_by_id(
        session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> MigrationJob:
        """
        Fetches a MigrationJob by ID, verifying user ownership via attached MigrationPlan.
        """
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
        session: AsyncSession, job_id: uuid.UUID, update: ExecutionProgressUpdate
    ) -> MigrationJob:
        """
        Updates live metrics and status for a MigrationJob from Docker Agent progress payload.
        """
        stmt = select(MigrationJob).where(MigrationJob.id == job_id)
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution job '{job_id}' not found.",
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
