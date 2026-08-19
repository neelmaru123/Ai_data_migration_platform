import os
import sys
import uuid
import polars as pl
import pytest
from httpx import ASGITransport, AsyncClient

# Add apps/agent to sys.path
agent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent"))
if agent_path not in sys.path:
    sys.path.insert(0, agent_path)

from execution_engine import ASTTransformer
from app.main import app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.db import Base, get_db
from app.modules.agents.agents_models import Agent
from app.modules.execution.execution_models import MigrationJob
from app.modules.migration_plans.migration_plans_models import MigrationPlan
from app.modules.users.users_models import User


@pytest.mark.asyncio
async def test_multi_agent_job_isolation():
    """
    Verifies that Agent 1 cannot poll or update Agent 2's migration jobs.
    """
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Register User
            test_email = f"agent_iso_{uuid.uuid4().hex[:6]}@example.com"
            res_user = await client.post("/api/v1/auth/register", json={
                "email": test_email,
                "password": "Password123!",
                "name": "Multi Agent Tester",
            })
            assert res_user.status_code == 201

            # 2. Register Agent 1 and Agent 2
            res_a1 = await client.post("/api/v1/agents", json={
                "name": "Docker Agent One",
                "agent_identifier": "agent_alpha",
                "data_sources": [{"name": "DB 1", "type": "postgresql", "role": "source", "identifier": "src_1"}],
            })
            assert res_a1.status_code == 201
            agent_1_data = res_a1.json()
            agent_1_id = agent_1_data["id"]
            agent_1_token = agent_1_data["api_token"]

            res_a2 = await client.post("/api/v1/agents", json={
                "name": "Docker Agent Two",
                "agent_identifier": "agent_beta",
                "data_sources": [{"name": "DB 2", "type": "mysql", "role": "source", "identifier": "src_2"}],
            })
            assert res_a2.status_code == 201
            agent_2_data = res_a2.json()
            agent_2_id = agent_2_data["id"]
            agent_2_token = agent_2_data["api_token"]

            # 3. Create MigrationPlan & ExecutionJob assigned strictly to Agent 1
            async with TestSession() as session:
                user = (await session.execute(__import__("sqlalchemy").select(User).where(User.email == test_email))).scalar_one()
                
                plan_1 = MigrationPlan(
                    user_id=user.id,
                    agent_id=uuid.UUID(agent_1_id),
                    status="completed",
                    plan_data={"table_mappings": []},
                    is_valid=True,
                )
                session.add(plan_1)
                await session.flush()

                job_1 = MigrationJob(
                    migration_plan_id=plan_1.id,
                    agent_id=uuid.UUID(agent_1_id),
                    status="queued",
                    total_rows=1000,
                )
                session.add(job_1)
                await session.commit()
                job_1_id = str(job_1.id)

            # 4. Agent 1 polls tasks -> Should find Job 1
            res_poll_1 = await client.get("/api/v1/agents/tasks", headers={"X-Agent-Token": agent_1_token})
            assert res_poll_1.status_code == 200
            tasks_1 = res_poll_1.json()
            assert len(tasks_1) == 1
            assert tasks_1[0]["job_id"] == job_1_id

            # 5. Agent 2 polls tasks -> Should find ZERO tasks (Isolation guaranteed!)
            res_poll_2 = await client.get("/api/v1/agents/tasks", headers={"X-Agent-Token": agent_2_token})
            assert res_poll_2.status_code == 200
            tasks_2 = res_poll_2.json()
            assert len(tasks_2) == 0

            # 6. Agent 2 tries to update Agent 1's Job 1 -> Should be REJECTED with 404 (Access Denied)
            res_illegal_update = await client.post(
                f"/api/v1/executions/{job_1_id}/progress",
                json={
                    "status": "running",
                    "progress": 50.0,
                    "processed_rows": 500,
                    "total_rows": 1000,
                },
                headers={"X-Agent-Token": agent_2_token},
            )
            assert res_illegal_update.status_code == 404
            assert "access denied" in res_illegal_update.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_ast_transformer_multi_column_merge_and_expression():
    """
    Verifies that ASTTransformer correctly:
    1. Combines 2 source columns into 1 (e.g. first_name + last_name -> full_name).
    2. Calculates derived columns from 2+ columns (e.g. price - discount -> net_price).
    """
    # Sample Source DataFrame extracted by agent
    raw_df = pl.DataFrame({
        "first_name": ["Alice", "Bob", "Charlie"],
        "last_name": ["Smith", "Jones", "Brown"],
        "price": [100.0, 250.0, 50.0],
        "discount": [10.0, 25.0, 5.0],
        "tax_rate": [0.10, 0.10, 0.08],
    })

    # AST Column Mappings generated by LLM / user
    column_mappings = [
        # 1. Combining 2 columns with merge_concat
        {
            "target_column_name": "full_name",
            "transformation_type": "merge_concat",
            "source_columns": [{"column_name": "first_name"}, {"column_name": "last_name"}],
            "target_data_type": "varchar(255)",
        },
        # 2. Calculating 3rd column from other 2 columns: net_price = price - discount
        {
            "target_column_name": "net_price",
            "transformation_type": "expression",
            "expression_template": "price - discount",
            "source_columns": [{"column_name": "price"}, {"column_name": "discount"}],
            "target_data_type": "numeric(10,2)",
        },
        # 3. Calculating complex formula: total_with_tax = (price - discount) * (1 + tax_rate)
        {
            "target_column_name": "total_with_tax",
            "transformation_type": "expression",
            "expression_template": "(price - discount) * (1 + tax_rate)",
            "source_columns": [{"column_name": "price"}, {"column_name": "discount"}, {"column_name": "tax_rate"}],
            "target_data_type": "numeric(10,2)",
        },
    ]

    transformed_df, errors = ASTTransformer.transform_chunk(raw_df, column_mappings)

    assert errors == 0
    assert "full_name" in transformed_df.columns
    assert "net_price" in transformed_df.columns
    assert "total_with_tax" in transformed_df.columns

    # Verify column combining
    assert transformed_df["full_name"].to_list() == ["Alice Smith", "Bob Jones", "Charlie Brown"]

    # Verify expression calculations from other columns
    assert transformed_df["net_price"].to_list() == pytest.approx([90.0, 225.0, 45.0])
    assert transformed_df["total_with_tax"].to_list() == pytest.approx([99.0, 247.5, 48.6])
