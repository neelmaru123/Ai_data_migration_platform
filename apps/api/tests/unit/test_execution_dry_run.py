"""
Unit tests for Dry Run Migration Execution Mode.
Verifies:
1. Backend: is_dry_run flag on MigrationJob model, create_execution_job, ExecutionJobResponse, and AgentTaskItemResponse.
2. Backend: update_job_progress handles "dry_run_completed" status lifecycle.
3. Agent Engine: ExecutionOrchestrator.run_job in dry-run mode:
   - Skips pre-migration and post-migration DDL
   - Transforms data but bypasses TargetWriterFactory.bulk_load
   - Preserves checkpoints (does not clear them)
   - Reports terminal status "dry_run_completed" with would-be row counts
4. Agent Engine: ExecutionOrchestrator.run_job in normal mode (regression check):
   - Executes DDL, writes to target, clears checkpoints, reports "completed"
"""

import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import polars as pl
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
from app.modules.sources.sources_models import DataSource
from app.modules.metadata.metadata_models import MetadataSnapshot, MetadataSchema, MetadataTable
from app.modules.execution.execution_models import MigrationJob
from app.modules.execution.execution_schemas import ExecutionJobResponse, AgentTaskItemResponse
from app.modules.execution.execution_services import ExecutionService
from app.modules.agents.agents_services import AgentService
from app.modules.migration_plans.migration_plans_models import MigrationPlan
from app.modules.users.users_models import User

from execution_engine import CheckpointManager, ExecutionOrchestrator, DDLExecutor, TargetWriterFactory


@pytest.mark.asyncio
async def test_create_execution_job_dry_run_flag():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    async with async_session() as session:
        user = User(id=user_id, email="dryrun@example.com", password_hash="pw", name="Dry Run User")
        agent = Agent(
            id=agent_id,
            user_id=user_id,
            name="Test Agent",
            agent_identifier="agent_dry_run",
            api_token_hash="tok",
            status="online",
            last_seen_at=datetime.now(timezone.utc),
        )
        plan = MigrationPlan(
            id=plan_id,
            user_id=user_id,
            agent_id=agent_id,
            status="approved",
            is_valid=True,
            plan_data={"table_mappings": []},
            target_config={"database_type": "postgresql"},
        )
        session.add_all([user, agent, plan])
        await session.commit()

    async with async_session() as session:
        # Create a dry run job
        job_dry = await ExecutionService.create_execution_job(
            session, user_id=user_id, plan_id=plan_id, is_dry_run=True
        )
        assert job_dry.is_dry_run is True
        assert job_dry.status == "queued"

        # Verify ExecutionJobResponse schema
        dto = ExecutionJobResponse.model_validate(job_dry)
        assert dto.is_dry_run is True

    # Use a second plan for non-dry run job because a plan cannot have two concurrent active jobs
    plan2_id = uuid.uuid4()
    async with async_session() as session:
        plan2 = MigrationPlan(
            id=plan2_id,
            user_id=user_id,
            agent_id=agent_id,
            status="approved",
            is_valid=True,
            plan_data={"table_mappings": []},
            target_config={"database_type": "postgresql"},
        )
        session.add(plan2)
        await session.commit()

        # Create a standard non-dry run job
        job_normal = await ExecutionService.create_execution_job(
            session, user_id=user_id, plan_id=plan2_id, is_dry_run=False
        )
        assert job_normal.is_dry_run is False

        # Agent task polling returns is_dry_run
        tasks = await ExecutionService.get_pending_tasks_for_agent(session, agent_id=agent_id)
        assert len(tasks) >= 2
        dry_job = next(t for t in tasks if t.id == job_dry.id)
        assert dry_job.is_dry_run is True
        dry_task_dto = AgentTaskItemResponse(
            job_id=dry_job.id,
            migration_plan_id=dry_job.migration_plan_id,
            status=dry_job.status,
            is_dry_run=dry_job.is_dry_run,
            created_at=dry_job.created_at,
        )
        assert dry_task_dto.is_dry_run is True

        normal_job = next(t for t in tasks if t.id == job_normal.id)
        assert normal_job.is_dry_run is False
        normal_task_dto = AgentTaskItemResponse(
            job_id=normal_job.id,
            migration_plan_id=normal_job.migration_plan_id,
            status=normal_job.status,
            is_dry_run=normal_job.is_dry_run,
            created_at=normal_job.created_at,
        )
        assert normal_task_dto.is_dry_run is False


@pytest.mark.asyncio
async def test_update_job_progress_dry_run_completed():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    async with async_session() as session:
        user = User(id=user_id, email="progress@example.com", password_hash="pw", name="User")
        agent = Agent(
            id=agent_id,
            user_id=user_id,
            name="Agent",
            agent_identifier="agent_prog",
            api_token_hash="tok",
            status="online",
            last_seen_at=datetime.now(timezone.utc),
        )
        plan = MigrationPlan(
            id=plan_id,
            user_id=user_id,
            agent_id=agent_id,
            status="approved",
            is_valid=True,
            plan_data={"table_mappings": []},
            target_config={"database_type": "postgresql"},
        )
        session.add_all([user, agent, plan])
        await session.commit()

    async with async_session() as session:
        job = await ExecutionService.create_execution_job(
            session, user_id=user_id, plan_id=plan_id, is_dry_run=True
        )
        job_id = job.id

    from app.modules.execution.execution_schemas import ExecutionProgressUpdate
    async with async_session() as session:
        update_dto = ExecutionProgressUpdate(
            status="dry_run_completed",
            progress=100.0,
            total_rows=500,
            processed_rows=500,
            successful_rows=500,
            failed_rows=0,
            current_table="customers",
        )
        # Simulate agent reporting terminal status "dry_run_completed"
        updated = await ExecutionService.update_job_progress(
            session,
            job_id=job_id,
            update=update_dto,
        )
        assert updated.status == "dry_run_completed"
        assert updated.processed_rows == 500
        assert updated.successful_rows == 500
        assert updated.completed_at is not None


def test_orchestrator_dry_run_skips_ddl_and_target_writes():
    """
    Verifies that when ExecutionOrchestrator runs with is_dry_run=True:
    1. Pre and Post DDL execution is skipped.
    2. Data extraction and transformation still occur.
    3. TargetWriterFactory.bulk_load is NOT invoked.
    4. CheckpointManager.clear_job_checkpoints is NOT invoked.
    5. Terminal status reported is 'dry_run_completed'.
    """
    job_id = "job-sim-001"
    target_table = "users_sim"

    plan_ast = {
        "plan_data": {
            "pre_migration_ddl": ["CREATE TABLE users_sim (id INT, name TEXT);"],
            "post_migration_ddl": ["CREATE INDEX idx_users_sim ON users_sim (name);"],
            "table_mappings": [
                {
                    "target_table_name": target_table,
                    "source_tables": [{"identifier": "src_db", "table_name": "users_src"}],
                    "column_mappings": [
                        {"target_column_name": "id", "transformation_type": "direct_copy", "source_columns": [{"column_name": "id"}]},
                        {"target_column_name": "name", "transformation_type": "direct_copy", "source_columns": [{"column_name": "name"}]},
                    ],
                }
            ],
        }
    }

    source_db_urls = {"src_db": "postgresql://localhost/src"}
    target_db_url = "postgresql://localhost/target"

    def mock_read_source_chunk(db_url, engine_type, table_or_file_name, offset=0, chunk_size=50000, pk_col=None, last_pk_val=None):
        if offset == 0:
            df = pl.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})
            return df, False, None
        return pl.DataFrame(), False, None

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.dict(os.environ, {"CHECKPOINT_DIR": tmp_dir}):
            with patch("execution_engine.DDLExecutor.execute_ddl_list") as mock_ddl, \
                 patch("execution_engine.ProgressReporter.report") as mock_report, \
                 patch("execution_engine.SourceConnectorFactory.read_source_chunk", side_effect=mock_read_source_chunk), \
                 patch("execution_engine.TargetWriterFactory.bulk_load") as mock_bulk_load, \
                 patch("execution_engine.CheckpointManager.clear_job_checkpoints") as mock_clear_checkpoints:

                ExecutionOrchestrator.run_job(
                    backend_url="http://localhost:8000",
                    agent_token="token",
                    job_id=job_id,
                    plan_ast=plan_ast,
                    source_db_urls=source_db_urls,
                    target_db_url=target_db_url,
                    is_dry_run=True,
                )

                # 1. DDL was NOT executed
                assert not mock_ddl.called, "DDLExecutor must not be called during dry run"

                # 2. Target writer was NOT called
                assert not mock_bulk_load.called, "TargetWriterFactory.bulk_load must not be called during dry run"

                # 3. Checkpoints were NOT cleared
                assert not mock_clear_checkpoints.called, "Checkpoints must be preserved during dry run"

                # 4. Terminal status reported was dry_run_completed
                terminal_call = mock_report.call_args_list[-1]
                call_args = terminal_call[0]
                status_arg = call_args[3]
                processed_arg = call_args[5]
                successful_arg = call_args[6]
                failed_arg = call_args[7]
                assert status_arg == "dry_run_completed"
                assert processed_arg == 3
                assert successful_arg == 3
                assert failed_arg == 0


def test_orchestrator_normal_run_executes_ddl_and_target_writes():
    """
    Regression check: Verifies that when ExecutionOrchestrator runs with is_dry_run=False:
    1. Pre and Post DDL execution is invoked.
    2. TargetWriterFactory.bulk_load is invoked.
    3. CheckpointManager.clear_job_checkpoints is invoked.
    4. Terminal status reported is 'completed'.
    """
    job_id = "job-real-001"
    target_table = "users_real"

    plan_ast = {
        "plan_data": {
            "pre_migration_ddl": ["CREATE TABLE users_real (id INT, name TEXT);"],
            "post_migration_ddl": ["CREATE INDEX idx_users_real ON users_real (name);"],
            "table_mappings": [
                {
                    "target_table_name": target_table,
                    "source_tables": [{"identifier": "src_db", "table_name": "users_src"}],
                    "column_mappings": [
                        {"target_column_name": "id", "transformation_type": "direct_copy", "source_columns": [{"column_name": "id"}]},
                        {"target_column_name": "name", "transformation_type": "direct_copy", "source_columns": [{"column_name": "name"}]},
                    ],
                }
            ],
        }
    }

    source_db_urls = {"src_db": "postgresql://localhost/src"}
    target_db_url = "postgresql://localhost/target"

    def mock_read_source_chunk(db_url, engine_type, table_or_file_name, offset=0, chunk_size=50000, pk_col=None, last_pk_val=None):
        if offset == 0:
            df = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
            return df, False, None
        return pl.DataFrame(), False, None

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.dict(os.environ, {"CHECKPOINT_DIR": tmp_dir}):
            with patch("execution_engine.DDLExecutor.execute_ddl_list") as mock_ddl, \
                 patch("execution_engine.ProgressReporter.report") as mock_report, \
                 patch("execution_engine.SourceConnectorFactory.read_source_chunk", side_effect=mock_read_source_chunk), \
                 patch("execution_engine.TargetWriterFactory.bulk_load", return_value=(2, 0, 0)) as mock_bulk_load, \
                 patch("execution_engine.CheckpointManager.clear_job_checkpoints") as mock_clear_checkpoints:

                ExecutionOrchestrator.run_job(
                    backend_url="http://localhost:8000",
                    agent_token="token",
                    job_id=job_id,
                    plan_ast=plan_ast,
                    source_db_urls=source_db_urls,
                    target_db_url=target_db_url,
                    is_dry_run=False,
                )

                # 1. DDL was executed
                assert mock_ddl.call_count == 2  # pre and post DDL

                # 2. Target writer was called
                assert mock_bulk_load.called

                # 3. Checkpoints were cleared
                assert mock_clear_checkpoints.called

                # 4. Terminal status reported was completed
                terminal_call = mock_report.call_args_list[-1]
                call_args = terminal_call[0]
                status_arg = call_args[3]
                processed_arg = call_args[5]
                successful_arg = call_args[6]
                assert status_arg == "completed"
                assert processed_arg == 2
                assert successful_arg == 2

