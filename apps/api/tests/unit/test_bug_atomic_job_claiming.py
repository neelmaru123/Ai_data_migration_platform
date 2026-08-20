"""
Unit test for Fix 5: Atomic job claiming to prevent double-execution.
Verifies that get_pending_tasks_for_agent atomically claims queued jobs and prevents concurrent duplicate execution.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[3].parent
API_DIR = REPO_ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.core.db import Base
import app.modules.users.users_models
import app.modules.agents.agents_models
import app.modules.sources.sources_models
import app.modules.metadata.metadata_models
import app.modules.migration_plans.migration_plans_models
import app.modules.execution.execution_models
from app.modules.agents.agents_models import Agent
from app.modules.execution.execution_models import MigrationJob
from app.modules.execution.execution_services import ExecutionService
from app.modules.migration_plans.migration_plans_models import MigrationPlan
from app.modules.users.users_models import User


@pytest.mark.asyncio
async def test_atomic_job_claiming_single_agent():
    """
    Verifies single-agent task polling flow: one queued job is claimed and transitioned to 'preparing'.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async with async_session() as session:
        user = User(id=user_id, email="user@example.com", password_hash="pw", name="User Test")
        agent = Agent(id=agent_id, user_id=user_id, name="Test Agent", agent_identifier="agent_1", api_token_hash="hash")
        plan = MigrationPlan(id=plan_id, user_id=user_id, agent_id=agent_id, plan_data={}, status="completed", is_valid=True)
        job = MigrationJob(id=job_id, migration_plan_id=plan_id, agent_id=agent_id, status="queued", progress=0.0)

        session.add_all([user, agent, plan, job])
        await session.commit()

    # Query pending tasks
    async with async_session() as session:
        tasks = await ExecutionService.get_pending_tasks_for_agent(session, agent_id)
        assert len(tasks) == 1
        assert tasks[0].id == job_id
        assert tasks[0].status == "preparing"

    # Subsequent query should find no queued tasks
    async with async_session() as session:
        tasks_again = await ExecutionService.get_pending_tasks_for_agent(session, agent_id)
        assert len(tasks_again) == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_atomic_job_claiming_concurrent_polls(tmp_path):
    """
    Verifies that two concurrent calls to get_pending_tasks_for_agent against 1 queued job
    result in only 1 caller receiving the job.
    """
    db_file = tmp_path / "test_atomic.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async with async_session() as session:
        user = User(id=user_id, email="concurrent@example.com", password_hash="pw", name="User Concurrent")
        agent = Agent(id=agent_id, user_id=user_id, name="Concurrent Agent", agent_identifier="agent_2", api_token_hash="hash2")
        plan = MigrationPlan(id=plan_id, user_id=user_id, agent_id=agent_id, plan_data={}, status="completed", is_valid=True)
        job = MigrationJob(id=job_id, migration_plan_id=plan_id, agent_id=agent_id, status="queued", progress=0.0)

        session.add_all([user, agent, plan, job])
        await session.commit()

    async def poll_task():
        async with async_session() as session:
            return await ExecutionService.get_pending_tasks_for_agent(session, agent_id)

    # Execute two concurrent polls
    res1, res2 = await asyncio.gather(poll_task(), poll_task())

    # Exactly one result list should contain the job, and the other should be empty
    jobs_claimed = len(res1) + len(res2)
    assert jobs_claimed == 1

    await engine.dispose()
