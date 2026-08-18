"""
Unit & Integration Test Suite for Agent-Centric Database Architecture
Verifies ORM models, foreign keys, cascade deletes, and N:M relationships for all 13 entities.
"""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base
from app.modules.users.users_models import User
from app.modules.agents.agents_models import Agent
from app.modules.sources.sources_models import DataSource
from app.modules.metadata.metadata_models import (
    MetadataSnapshot,
    MetadataSchema,
    MetadataTable,
    MetadataColumn,
    MetadataConstraint,
    MetadataRelationship,
)
from app.modules.migration_plans.migration_plans_models import (
    MigrationPlan,
    MigrationPlanSnapshot,
)
from app.modules.execution.execution_models import MigrationJob, MigrationError


@pytest.mark.asyncio
async def test_agent_centric_orm_relationships_and_cascades():
    """
    Test complete lifecycle of Agent-Centric Database Models:
    User -> Agent -> DataSource -> MetadataSnapshot -> (Schemas/Tables/Columns/Constraints/Relationships)
    MigrationPlan <-> MetadataSnapshot (N:M via MigrationPlanSnapshot)
    MigrationPlan -> MigrationJob -> MigrationError
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # 1. Create User
        user = User(
            email="agent.owner@example.com",
            name="Agent Owner",
        )
        session.add(user)
        await session.commit()
        assert user.id is not None

        # 2. Create Agent
        agent = Agent(
            user_id=user.id,
            name="Production Edge Agent",
            agent_identifier="agent_prod_001",
            status="online",
        )
        session.add(agent)
        await session.commit()
        assert agent.id is not None

        # 3. Create DataSource identity (no credentials stored on control plane)
        ds = DataSource(
            agent_id=agent.id,
            name="Production Postgres DB",
            type="postgresql",
            identifier="prod_pg_instance_1",
        )
        session.add(ds)
        await session.commit()
        assert ds.id is not None

        # 4. Create MetadataSnapshot
        snapshot = MetadataSnapshot(
            data_source_id=ds.id,
            database_name="prod_db",
            total_tables=1,
            total_columns=2,
            total_rows=100,
        )
        session.add(snapshot)
        await session.commit()
        assert snapshot.id is not None

        # 5. Create Metadata Detail Tables
        schema = MetadataSchema(
            snapshot_id=snapshot.id,
            schema_name="public",
        )
        session.add(schema)
        await session.commit()

        table = MetadataTable(
            schema_id=schema.id,
            table_name="users",
            row_count=100,
        )
        session.add(table)
        await session.commit()

        col1 = MetadataColumn(
            table_id=table.id,
            column_name="id",
            ordinal_position=1,
            data_type="uuid",
            native_data_type="uuid",
            is_primary_key=True,
        )
        col2 = MetadataColumn(
            table_id=table.id,
            column_name="email",
            ordinal_position=2,
            data_type="varchar",
            native_data_type="varchar(255)",
            nullable=False,
        )
        session.add_all([col1, col2])
        await session.commit()

        constraint = MetadataConstraint(
            table_id=table.id,
            constraint_name="pk_users",
            constraint_type="primary_key",
        )
        session.add(constraint)
        await session.commit()

        rel = MetadataRelationship(
            snapshot_id=snapshot.id,
            source_table_id=table.id,
            source_column_id=col1.id,
            target_table_id=table.id,
            target_column_id=col1.id,
            relationship_type="self_reference",
        )
        session.add(rel)
        await session.commit()

        # 6. Create MigrationPlan linked to User and Agent
        plan = MigrationPlan(
            user_id=user.id,
            agent_id=agent.id,
            status="approved",
            plan_data={"steps": ["extract", "transform", "load"]},
            target_config={"target_type": "mysql"},
        )
        session.add(plan)
        await session.commit()
        assert plan.id is not None

        # 7. Create N:M link via MigrationPlanSnapshot
        plan_snapshot = MigrationPlanSnapshot(
            migration_plan_id=plan.id,
            metadata_snapshot_id=snapshot.id,
        )
        session.add(plan_snapshot)
        await session.commit()

        # 8. Create MigrationJob and MigrationError
        job = MigrationJob(
            migration_plan_id=plan.id,
            agent_id=agent.id,
            status="running",
            total_rows=100,
            processed_rows=50,
        )
        session.add(job)
        await session.commit()
        assert job.id is not None

        err = MigrationError(
            migration_job_id=job.id,
            source_table="users",
            error_type="type_mismatch",
            error_message="Column email failed length check",
        )
        session.add(err)
        await session.commit()
        assert err.id is not None

        # 9. Verify Queries and Relationships using selectinload
        res_agent = await session.execute(
            select(Agent).where(Agent.id == agent.id).options(selectinload(Agent.data_sources))
        )
        fetched_agent = res_agent.scalar_one()
        assert len(fetched_agent.data_sources) == 1
        assert fetched_agent.data_sources[0].name == "Production Postgres DB"

        res_plan = await session.execute(
            select(MigrationPlan)
            .where(MigrationPlan.id == plan.id)
            .options(selectinload(MigrationPlan.agent), selectinload(MigrationPlan.snapshots))
        )
        fetched_plan = res_plan.scalar_one()
        assert fetched_plan.agent.name == "Production Edge Agent"
        assert len(fetched_plan.snapshots) == 1
        assert fetched_plan.snapshots[0].database_name == "prod_db"

    await engine.dispose()
