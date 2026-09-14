"""
Unit test for preflight target table existing data check.
Verifies that create_execution_job checks the agent's target DataSource
metadata snapshot for existing table row counts without blocking execution,
and attaches target_tables_with_existing_data to the response.
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
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
from app.modules.sources.sources_models import DataSource
from app.modules.metadata.metadata_models import MetadataSnapshot, MetadataSchema, MetadataTable
from app.modules.execution.execution_models import MigrationJob
from app.modules.execution.execution_schemas import ExecutionJobResponse
from app.modules.execution.execution_services import ExecutionService
from app.modules.migration_plans.migration_plans_models import MigrationPlan
from app.modules.users.users_models import User


@pytest.mark.asyncio
async def test_create_execution_job_warns_on_existing_target_data():
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
        user = User(id=user_id, email="dev@example.com", password_hash="pw", name="Developer")
        agent = Agent(
            id=agent_id,
            user_id=user_id,
            name="Primary Agent",
            agent_identifier="agent_01",
            api_token_hash="tok",
            status="online",
            last_seen_at=datetime.now(timezone.utc),
        )
        target_ds = DataSource(
            id=target_ds_id,
            agent_id=agent_id,
            name="Target PostgreSQL",
            type="postgresql",
            role="target",
            identifier="target_dwh",
        )
        snapshot = MetadataSnapshot(
            id=snapshot_id,
            data_source_id=target_ds_id,
            database_name="target_db",
            version=1,
            total_tables=2,
            total_columns=10,
        )
        schema = MetadataSchema(
            id=schema_id,
            snapshot_id=snapshot_id,
            schema_name="public",
        )
        table_users = MetadataTable(
            id=uuid.uuid4(),
            schema_id=schema_id,
            table_name="users",
            table_type="table",
            row_count=150,  # non-zero existing row count!
        )
        table_orders = MetadataTable(
            id=uuid.uuid4(),
            schema_id=schema_id,
            table_name="orders",
            table_type="table",
            row_count=0,  # empty table
        )
        plan = MigrationPlan(
            id=plan_id,
            user_id=user_id,
            agent_id=agent_id,
            status="approved",
            is_valid=True,
            plan_data={
                "table_mappings": [
                    {"target_table_name": "users"},
                    {"target_table_name": "orders"},
                ]
            },
            target_config={"database_type": "postgresql", "identifier": "target_dwh"},
        )

        session.add_all([user, agent, target_ds, snapshot, schema, table_users, table_orders, plan])
        await session.commit()

    async with async_session() as session:
        job = await ExecutionService.create_execution_job(session, user_id=user_id, plan_id=plan_id)

        # 1. Execution is NOT blocked
        assert job.status == "queued"
        assert job.migration_plan_id == plan_id

        # 2. Existing data warnings attached
        warnings = getattr(job, "target_tables_with_existing_data", None)
        assert warnings is not None
        assert len(warnings) == 1
        assert warnings[0] == {"table_name": "users", "existing_row_count": 150}

        # 3. Serialized cleanly into ExecutionJobResponse
        response_dto = ExecutionJobResponse.model_validate(job)
        assert len(response_dto.target_tables_with_existing_data) == 1
        assert response_dto.target_tables_with_existing_data[0] == {
            "table_name": "users",
            "existing_row_count": 150,
        }


@pytest.mark.asyncio
async def test_create_execution_job_empty_when_target_tables_clean():
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
        user = User(id=user_id, email="clean@example.com", password_hash="pw", name="Clean")
        agent = Agent(
            id=agent_id,
            user_id=user_id,
            name="Primary Agent",
            agent_identifier="agent_clean",
            api_token_hash="tok",
            status="online",
            last_seen_at=datetime.now(timezone.utc),
        )
        target_ds = DataSource(
            id=target_ds_id,
            agent_id=agent_id,
            name="Target DB",
            type="postgresql",
            role="target",
            identifier="target_clean",
        )
        snapshot = MetadataSnapshot(
            id=snapshot_id,
            data_source_id=target_ds_id,
            database_name="target_db",
            version=1,
            total_tables=1,
            total_columns=5,
        )
        schema = MetadataSchema(
            id=schema_id,
            snapshot_id=snapshot_id,
            schema_name="public",
        )
        table_customers = MetadataTable(
            id=uuid.uuid4(),
            schema_id=schema_id,
            table_name="customers",
            table_type="table",
            row_count=0,  # 0 rows!
        )
        plan = MigrationPlan(
            id=plan_id,
            user_id=user_id,
            agent_id=agent_id,
            status="approved",
            is_valid=True,
            plan_data={
                "table_mappings": [
                    {"target_table_name": "customers"},
                ]
            },
            target_config={"database_type": "postgresql", "identifier": "target_clean"},
        )

        session.add_all([user, agent, target_ds, snapshot, schema, table_customers, plan])
        await session.commit()

    async with async_session() as session:
        job = await ExecutionService.create_execution_job(session, user_id=user_id, plan_id=plan_id)

        assert job.status == "queued"
        warnings = getattr(job, "target_tables_with_existing_data", None)
        assert warnings == []

        response_dto = ExecutionJobResponse.model_validate(job)
        assert response_dto.target_tables_with_existing_data == []
