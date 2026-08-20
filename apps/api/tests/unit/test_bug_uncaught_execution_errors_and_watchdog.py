"""
Unit test for Fix 6: Uncaught execution errors & backend watchdog.
Verifies that:
1. ExecutionOrchestrator.run_job reports failed progress update with error_message on unhandled exception.
2. ExecutionService.check_stale_jobs identifies jobs stuck in 'running'/'preparing' > 5 min and marks them failed.
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[3].parent
API_DIR = REPO_ROOT / "apps" / "api"
AGENT_DIR = REPO_ROOT / "apps" / "agent"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

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
from execution_engine import ExecutionOrchestrator, ProgressReporter, DDLExecutor


def test_agent_run_job_uncaught_exception_reports_failure():
    """
    Verifies that when ExecutionOrchestrator.run_job encounters an unhandled exception,
    it calls ProgressReporter.report with status='failed' and a non-empty error_message.
    """
    backend_url = "http://localhost:8000"
    agent_token = "ag_live_token123"
    job_id = str(uuid.uuid4())
    plan_ast = {
        "plan_data": {
            "pre_migration_ddl": [],
            "post_migration_ddl": [],
            "table_mappings": [
                {
                    "target_table_name": "users",
                    "source_tables": [{"identifier": "src1", "table_name": "users"}],
                    "column_mappings": [],
                }
            ],
        }
    }

    reports_sent = []

    def mock_report(url, token, j_id, status, progress, proc, succ, fail, skip=0, current_table=None, current_stage=None, error_message=None, **kwargs):
        reports_sent.append({
            "status": status,
            "error_message": error_message,
        })

    def mock_ddl_raise(*args, **kwargs):
        raise ValueError("Simulated DDL connection failure")

    with patch.object(ProgressReporter, "report", side_effect=mock_report), \
         patch.object(DDLExecutor, "execute_ddl_list", side_effect=mock_ddl_raise):
        
        with pytest.raises(ValueError, match="Simulated DDL connection failure"):
            ExecutionOrchestrator.run_job(
                backend_url=backend_url,
                agent_token=agent_token,
                job_id=job_id,
                plan_ast=plan_ast,
                source_db_urls={"src1": "postgresql://localhost:5432/db"},
                target_db_url="postgresql://localhost:5432/db",
            )

    assert len(reports_sent) >= 1
    failed_reports = [r for r in reports_sent if r["status"] == "failed"]
    assert len(failed_reports) == 1
    assert "Simulated DDL connection failure" in failed_reports[0]["error_message"]


@pytest.mark.asyncio
async def test_backend_watchdog_fails_stale_running_jobs(tmp_path):
    """
    Verifies that ExecutionService.check_stale_jobs identifies jobs stuck in 'running'
    with updated_at > 5 minutes ago and transitions them to 'failed'.
    """
    db_file = tmp_path / "test_watchdog.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    job_id = uuid.uuid4()

    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    async with async_session() as session:
        user = User(id=user_id, email="watchdog@example.com", password_hash="pw", name="User Watchdog")
        agent = Agent(id=agent_id, user_id=user_id, name="Watchdog Agent", agent_identifier="agent_w", api_token_hash="hashw")
        plan = MigrationPlan(id=plan_id, user_id=user_id, agent_id=agent_id, plan_data={}, status="completed", is_valid=True)
        job = MigrationJob(
            id=job_id,
            migration_plan_id=plan_id,
            agent_id=agent_id,
            status="running",
            progress=45.0,
            updated_at=stale_time,
        )

        session.add_all([user, agent, plan, job])
        await session.commit()

    async with async_session() as session:
        stale_count = await ExecutionService.check_stale_jobs(session, stale_threshold_seconds=300)
        assert stale_count == 1

    async with async_session() as session:
        updated_job = await session.get(MigrationJob, job_id)
        assert updated_job is not None
        assert updated_job.status == "failed"
        assert "stalled" in updated_job.error_message.lower()

    await engine.dispose()
