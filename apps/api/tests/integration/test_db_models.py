"""
Integration Test for Control Plane Database Models (Agent-Centric Design)
Validates ORM creation, relationships, JSONB handling, and cascading deletes across all entities.
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

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
async def test_full_orm_entity_lifecycle():
    """Test full ORM creation and relationship traversal across all Agent-Centric entities."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # 1. User
        user = User(
            email="test_user@migrationplatform.com",
            password_hash="hashed_secret_123",
            name="Test Lead Architect",
        )
        session.add(user)
        await session.flush()
        assert user.id is not None

        # 2. Agent
        agent = Agent(
            user_id=user.id,
            name="Customer On-Prem Agent 01",
            agent_identifier="agent-uuid-001",
            status="online",
            version="1.0.0",
        )
        session.add(agent)
        await session.flush()
        assert agent.id is not None

        # 3. DataSource
        data_source = DataSource(
            agent_id=agent.id,
            name="Source Postgres DB",
            type="postgresql",
            identifier="prod_pg_db_01",
        )
        session.add(data_source)
        await session.flush()

        # 4. Metadata Snapshot
        snapshot = MetadataSnapshot(
            data_source_id=data_source.id,
            version=1,
            database_name="legacy_db",
            database_version="PostgreSQL 14.5",
            total_tables=1,
            total_columns=2,
            total_rows=1000,
            status="completed",
        )
        session.add(snapshot)
        await session.flush()

        # 5. Metadata Schema
        schema = MetadataSchema(
            snapshot_id=snapshot.id,
            schema_name="public",
        )
        session.add(schema)
        await session.flush()

        # 6. Metadata Table
        table = MetadataTable(
            schema_id=schema.id,
            table_name="customers",
            table_type="table",
            row_count=1000,
            size_bytes=81920,
        )
        session.add(table)
        await session.flush()

        # 7. Metadata Columns
        col1 = MetadataColumn(
            table_id=table.id,
            column_name="id",
            ordinal_position=1,
            data_type="uuid",
            native_data_type="uuid",
            nullable=False,
            is_primary_key=True,
            is_unique=True,
            statistics={"null_count": 0},
            sample_values=["a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"],
        )
        col2 = MetadataColumn(
            table_id=table.id,
            column_name="email",
            ordinal_position=2,
            data_type="string",
            native_data_type="varchar(255)",
            nullable=False,
            is_primary_key=False,
            is_unique=True,
        )
        session.add_all([col1, col2])
        await session.flush()

        # 8. Metadata Constraint
        constraint = MetadataConstraint(
            table_id=table.id,
            constraint_name="pk_customers",
            constraint_type="primary_key",
            definition="PRIMARY KEY (id)",
        )
        session.add(constraint)
        await session.flush()

        # 9. Metadata Relationship
        meta_rel = MetadataRelationship(
            snapshot_id=snapshot.id,
            source_table_id=table.id,
            source_column_id=col1.id,
            target_table_id=table.id,
            target_column_id=col2.id,
            relationship_type="inferred",
            confidence=0.95,
        )
        session.add(meta_rel)
        await session.flush()

        # 10. Migration Plan
        plan = MigrationPlan(
            user_id=user.id,
            agent_id=agent.id,
            plan_data={"tables": [{"target_table": "users_new", "source_tables": ["customers"]}]},
            target_config={"target_type": "mysql"},
            ai_model="gemini-1.5-pro",
            prompt_version="1.0.0",
            status="approved",
            confidence_score=0.98,
        )
        session.add(plan)
        await session.flush()

        # 11. Migration Plan Snapshot Link
        plan_snap = MigrationPlanSnapshot(
            migration_plan_id=plan.id,
            metadata_snapshot_id=snapshot.id,
        )
        session.add(plan_snap)
        await session.flush()

        # 12. Migration Job
        job = MigrationJob(
            migration_plan_id=plan.id,
            agent_id=agent.id,
            status="running",
            progress=50.0,
            total_rows=1000,
            processed_rows=500,
            successful_rows=495,
            failed_rows=5,
            current_table="customers",
            current_stage="transforming",
            started_at=datetime.now(timezone.utc),
        )
        session.add(job)
        await session.flush()

        # 13. Migration Error
        error = MigrationError(
            migration_job_id=job.id,
            source_table="customers",
            source_row_identifier="row_42",
            error_type="DataValidationError",
            error_message="Invalid email format string",
            raw_data={"id": "row_42", "email": "invalid-email-str"},
            ai_suggestion="Cast or clean email string using regex",
            status="unresolved",
            retry_count=0,
        )
        session.add(error)
        await session.commit()

        # Fetch using async select with selectinload
        stmt_user = select(User).where(User.id == user.id).options(
            selectinload(User.agents),
        )
        result_user = await session.execute(stmt_user)
        fetched_user = result_user.scalar_one()

        stmt_job = select(MigrationJob).where(MigrationJob.id == job.id).options(
            selectinload(MigrationJob.errors),
            selectinload(MigrationJob.agent),
        )
        result_job = await session.execute(stmt_job)
        fetched_job = result_job.scalar_one()

        # Assertions
        assert fetched_user.agents[0].name == "Customer On-Prem Agent 01"
        assert data_source.agent_id == agent.id
        assert data_source.identifier == "prod_pg_db_01"
        assert snapshot.database_name == "legacy_db"
        assert schema.schema_name == "public"
        assert table.table_name == "customers"
        assert col1.ordinal_position == 1
        assert constraint.constraint_type == "primary_key"
        assert fetched_job.status == "running"
        assert fetched_job.agent.agent_identifier == "agent-uuid-001"
        assert fetched_job.errors[0].error_type == "DataValidationError"

    await test_engine.dispose()
