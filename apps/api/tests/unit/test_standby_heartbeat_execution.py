import pytest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base
from app.modules.agents.agents_models import Agent
from app.modules.agents.agents_services import AgentService
from app.modules.execution.execution_models import MigrationJob
from app.modules.execution.execution_services import ExecutionService
from app.modules.migration_plans.migration_plans_models import MigrationPlan
from app.modules.users.users_models import User


@pytest.mark.asyncio
async def test_standby_agent_not_falsely_marked_offline_by_watchdog():
    """
    Verifies that an agent in 5-minute standby mode (idle_since >= 300s)
    is NOT marked offline by the watchdog when seen within the 360s standby threshold.
    """
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(
            email="standby_test@example.com",
            password_hash="fake_pwd",
            name="Standby Test User",
        )
        session.add(user)
        await session.flush()

        now = datetime.now(timezone.utc)
        # Agent was idle for 10 minutes, and sent its last heartbeat 180s ago (well within 360s standby)
        standby_agent = Agent(
            user_id=user.id,
            name="Standby Migration Agent",
            agent_identifier="standby_agent_001",
            api_token_hash="token_hash_standby_1",
            status="online",
            last_seen_at=now - timedelta(seconds=180),
            idle_since=now - timedelta(seconds=600),
        )
        session.add(standby_agent)
        await session.commit()

        # Run watchdog with 60s active threshold and 360s standby threshold
        stats = await AgentService.check_stale_agents_and_jobs(
            session, stale_threshold_seconds=60, standby_threshold_seconds=360
        )
        assert stats["stale_agents_marked_offline"] == 0

        # Verify agent is STILL online!
        stmt = select(Agent).where(Agent.id == standby_agent.id)
        res = await session.execute(stmt)
        ag = res.scalar_one()
        assert ag.status == "online"
        assert ag.last_error is None


@pytest.mark.asyncio
async def test_create_execution_job_succeeds_with_standby_agent():
    """
    Verifies that create_execution_job allows execution for an agent in standby mode
    whose last heartbeat was 180s ago, without raising HTTP 503.
    """
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(
            email="standby_exec_test@example.com",
            password_hash="fake_pwd",
            name="Standby Exec User",
        )
        session.add(user)
        await session.flush()

        now = datetime.now(timezone.utc)
        # Agent was idle for 15 minutes, last seen 200s ago
        standby_agent = Agent(
            user_id=user.id,
            name="Standby Exec Agent",
            agent_identifier="standby_agent_002",
            api_token_hash="token_hash_standby_2",
            status="online",
            last_seen_at=now - timedelta(seconds=200),
            idle_since=now - timedelta(seconds=900),
        )
        session.add(standby_agent)
        await session.flush()

        plan = MigrationPlan(
            user_id=user.id,
            agent_id=standby_agent.id,
            status="approved",
            is_valid=True,
            plan_data={"source_type": "postgresql", "target_type": "postgresql"},
        )
        session.add(plan)
        await session.commit()

        # create_execution_job should succeed without raising HTTP 503
        job = await ExecutionService.create_execution_job(
            session=session,
            user_id=user.id,
            plan_id=plan.id,
            is_dry_run=False,
        )
        assert job is not None
        assert job.status == "queued"

        # Verify agent idle_since was reset
        res = await session.execute(select(Agent).where(Agent.id == standby_agent.id))
        updated_agent = res.scalar_one()
        assert updated_agent.idle_since is None
        assert updated_agent.status == "online"
