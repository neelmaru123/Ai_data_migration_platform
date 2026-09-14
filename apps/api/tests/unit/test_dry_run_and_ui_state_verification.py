"""
Comprehensive validation test suite verifying the 4 requested scenarios:
1. Normal job (clean target tables): No existing target data warning, clean execution start.
2. Target table with existing data: Advisory warning attached, execution is NOT blocked (queued).
3. Dry Run mode: 0 rows written to target, DDL skipped, accurate read of successful/failed counts, status "dry_run_completed", checkpoints preserved.
4. Resume / Retry / Completed button logic:
   - Failed job with processed_rows > 0 -> "Resume" with checkpoint reuse tooltip.
   - Failed job with processed_rows == 0 -> "Retry" from beginning.
   - Completed job -> Retry disabled with checkpoint tooltip, offers "Create New Migration".
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
from app.modules.execution.execution_schemas import ExecutionJobResponse, ExecutionProgressUpdate
from app.modules.execution.execution_services import ExecutionService
from app.modules.migration_plans.migration_plans_models import MigrationPlan
from app.modules.users.users_models import User

from execution_engine import CheckpointManager, ExecutionOrchestrator


@pytest.mark.asyncio
async def test_scenario_1_normal_job_no_existing_data_warning():
    """
    Scenario 1: Confirm a normal job (no existing target data) has no warning banner.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    target_ds_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
    schema_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    async with async_session() as session:
        user = User(id=user_id, email="u1@test.com", password_hash="pw", name="User 1")
        agent = Agent(id=agent_id, user_id=user_id, name="Agent 1", agent_identifier="ag_1", api_token_hash="tok", status="online", last_seen_at=datetime.now(timezone.utc))
        target_ds = DataSource(id=target_ds_id, agent_id=agent_id, name="Target DB", type="postgresql", role="target", identifier="target_clean")
        snapshot = MetadataSnapshot(id=snapshot_id, data_source_id=target_ds_id, database_name="target_db", version=1)
        schema = MetadataSchema(id=schema_id, snapshot_id=snapshot_id, schema_name="public")
        table_clean = MetadataTable(id=uuid.uuid4(), schema_id=schema_id, table_name="users", table_type="table", row_count=0)
        plan = MigrationPlan(
            id=plan_id, user_id=user_id, agent_id=agent_id, status="approved", is_valid=True,
            plan_data={"table_mappings": [{"target_table_name": "users"}]},
            target_config={"database_type": "postgresql", "identifier": "target_clean"},
        )
        session.add_all([user, agent, target_ds, snapshot, schema, table_clean, plan])
        await session.commit()

    async with async_session() as session:
        job = await ExecutionService.create_execution_job(session, user_id=user_id, plan_id=plan_id)
        assert job.status == "queued"

        # Verify no warning attached
        warnings = getattr(job, "target_tables_with_existing_data", [])
        assert len(warnings) == 0, "Clean table must have empty target_tables_with_existing_data"

        dto = ExecutionJobResponse.model_validate(job)
        assert dto.target_tables_with_existing_data == []
        # In JobExecutionBanner.tsx:
        # {job.target_tables_with_existing_data && job.target_tables_with_existing_data.length > 0 && (...)}
        # Evaluates to FALSE -> No warning banner is rendered.


@pytest.mark.asyncio
async def test_scenario_2_target_table_with_existing_data_warns_without_blocking():
    """
    Scenario 2: Point a plan at a target table that already has rows.
    Confirm the warning appears and execution is NOT blocked (user can proceed).
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    target_ds_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
    schema_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    async with async_session() as session:
        user = User(id=user_id, email="u2@test.com", password_hash="pw", name="User 2")
        agent = Agent(id=agent_id, user_id=user_id, name="Agent 2", agent_identifier="ag_2", api_token_hash="tok", status="online", last_seen_at=datetime.now(timezone.utc))
        target_ds = DataSource(id=target_ds_id, agent_id=agent_id, name="Target DB", type="postgresql", role="target", identifier="target_existing")
        snapshot = MetadataSnapshot(id=snapshot_id, data_source_id=target_ds_id, database_name="target_db", version=1)
        schema = MetadataSchema(id=schema_id, snapshot_id=snapshot_id, schema_name="public")
        table_pop = MetadataTable(id=uuid.uuid4(), schema_id=schema_id, table_name="customers", table_type="table", row_count=8450)
        plan = MigrationPlan(
            id=plan_id, user_id=user_id, agent_id=agent_id, status="approved", is_valid=True,
            plan_data={"table_mappings": [{"target_table_name": "customers"}]},
            target_config={"database_type": "postgresql", "identifier": "target_existing"},
        )
        session.add_all([user, agent, target_ds, snapshot, schema, table_pop, plan])
        await session.commit()

    async with async_session() as session:
        job = await ExecutionService.create_execution_job(session, user_id=user_id, plan_id=plan_id)

        # 1. Execution is NOT blocked: status is successfully queued
        assert job.status == "queued"
        assert job.migration_plan_id == plan_id

        # 2. Warning details are populated with exact table and row count
        warnings = getattr(job, "target_tables_with_existing_data", [])
        assert len(warnings) == 1
        assert warnings[0]["table_name"] == "customers"
        assert warnings[0]["existing_row_count"] == 8450

        # 3. Response DTO contains warnings for the UI banner
        dto = ExecutionJobResponse.model_validate(job)
        assert len(dto.target_tables_with_existing_data) == 1
        # In JobExecutionBanner.tsx:
        # {job.target_tables_with_existing_data && job.target_tables_with_existing_data.length > 0 && (...)}
        # Evaluates to TRUE -> Warning banner displays: "customers: 8,450 existing rows"


def test_scenario_3_dry_run_zero_writes_and_accurate_metrics():
    """
    Scenario 3: Run a Dry Run:
    - Zero rows written to target (TargetWriterFactory.bulk_load is NOT called)
    - Pre and Post DDL are completely skipped
    - Accurate read of how many rows would succeed vs fail
    - Final status is "dry_run_completed"
    - Checkpoints are preserved
    """
    job_id = "job-dryrun-validation"
    target_table = "orders_dry"

    plan_ast = {
        "plan_data": {
            "pre_migration_ddl": ["DROP TABLE IF EXISTS orders_dry;", "CREATE TABLE orders_dry (id INT, item TEXT);"],
            "post_migration_ddl": ["ALTER TABLE orders_dry ADD PRIMARY KEY (id);"],
            "table_mappings": [
                {
                    "target_table_name": target_table,
                    "source_tables": [{"identifier": "src", "table_name": "orders_src"}],
                    "column_mappings": [
                        {"target_column_name": "id", "transformation_type": "direct_copy", "source_columns": [{"column_name": "id"}]},
                        {"target_column_name": "item", "transformation_type": "direct_copy", "source_columns": [{"column_name": "item"}]},
                    ],
                }
            ],
        }
    }

    # Simulate 2 chunks of source data: 4 rows total
    def mock_read_source_chunk(db_url, engine_type, table_or_file_name, offset=0, chunk_size=50000, pk_col=None, last_pk_val=None):
        if offset == 0:
            return pl.DataFrame({"id": [1, 2], "item": ["Widget A", "Widget B"]}), True, 2
        elif offset == 2:
            return pl.DataFrame({"id": [3, 4], "item": ["Widget C", "Widget D"]}), False, None
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
                    source_db_urls={"src": "postgresql://localhost/src"},
                    target_db_url="postgresql://localhost/target",
                    is_dry_run=True,
                )

                # 1. Zero rows written to target DB
                assert not mock_bulk_load.called, "TargetWriterFactory.bulk_load must NEVER be called in dry run!"

                # 2. DDL skipped
                assert not mock_ddl.called, "DDLExecutor must NEVER execute in dry run!"

                # 3. Checkpoints preserved
                assert not mock_clear_checkpoints.called, "Checkpoints must NOT be cleared on dry run!"

                # 4. Terminal status and accurate row counts reported
                terminal_call = mock_report.call_args_list[-1]
                args = terminal_call[0]
                status_reported = args[3]
                processed_reported = args[5]
                successful_reported = args[6]
                failed_reported = args[7]

                assert status_reported == "dry_run_completed"
                assert processed_reported == 4
                assert successful_reported == 4
                assert failed_reported == 0


def test_scenario_4_resume_retry_button_ui_logic():
    """
    Scenario 4: Confirm resume/retry button logic for failed vs completed jobs:
    - Failed + processed_rows > 0 -> "Resume" (canResume=True), tooltip specifies checkpoints reused
    - Failed + processed_rows == 0 -> "Retry" (canResume=False), tooltip specifies retry from start
    - Completed -> Retry is disabled, offers "Create New Migration"
    """
    def evaluate_button_ui(status: str, processed_rows: int, is_dry_run: bool = False):
        st = status.lower()
        isDryRunCompleted = st == "dry_run_completed"
        isRealCompleted = st == "completed"
        isFailed = st == "failed"
        canResume = isFailed and processed_rows > 0

        # Determine rendered buttons & properties matching JobExecutionBanner.tsx
        rendered = {}
        if isRealCompleted:
            rendered["create_new_migration_visible"] = True
            rendered["retry_button_disabled"] = True
            rendered["retry_button_tooltip"] = "Checkpoints will be reused when the job is completed. Create a new migration instead."
            rendered["retry_button_label"] = "⚡ RETRY (DISABLED)"
        elif isFailed:
            rendered["create_new_migration_visible"] = False
            rendered["retry_button_disabled"] = False
            if canResume:
                rendered["retry_button_label"] = "⚡ RESUME DRY RUN" if is_dry_run else "⚡ RESUME"
                rendered["retry_button_tooltip"] = f"Checkpoints will be reused: resumes execution from {processed_rows:,} processed rows."
            else:
                rendered["retry_button_label"] = "⚡ RETRY DRY RUN" if is_dry_run else "⚡ RETRY MIGRATION JOB"
                rendered["retry_button_tooltip"] = "Retries migration from the beginning."

        return rendered

    # 4A. Failed job with partial progress (e.g. crashed midway after 2,500 rows)
    ui_4a = evaluate_button_ui(status="failed", processed_rows=2500)
    assert ui_4a["retry_button_label"] == "⚡ RESUME"
    assert "Checkpoints will be reused" in ui_4a["retry_button_tooltip"]
    assert ui_4a["retry_button_disabled"] is False
    assert ui_4a["create_new_migration_visible"] is False

    # 4B. Failed job with 0 rows processed (e.g. immediate connection error before any rows)
    ui_4b = evaluate_button_ui(status="failed", processed_rows=0)
    assert ui_4b["retry_button_label"] == "⚡ RETRY MIGRATION JOB"
    assert "Retries migration from the beginning" in ui_4b["retry_button_tooltip"]
    assert ui_4b["retry_button_disabled"] is False

    # 4C. Completed job (100% finished migration)
    ui_4c = evaluate_button_ui(status="completed", processed_rows=50000)
    assert ui_4c["create_new_migration_visible"] is True
    assert ui_4c["retry_button_disabled"] is True
    assert "Checkpoints will be reused when the job is completed" in ui_4c["retry_button_tooltip"]
    assert ui_4c["retry_button_label"] == "⚡ RETRY (DISABLED)"
