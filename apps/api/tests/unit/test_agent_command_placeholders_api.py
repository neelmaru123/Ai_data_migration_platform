"""
Unit & API Integration Tests for Generic Parameterized DB URL Placeholders in Agent Commands.
Tests calling:
- POST /api/v1/agents (Agent creation endpoint returning docker_command and env_vars)
- GET /api/v1/agents/{agent_id}/docker-command (Command generator retrieval endpoint)
Verifies:
- <SRC_..._HOST>, <SRC_..._PORT>, <SRC_..._USER>, <SRC_..._PASSWORD>, <SRC_..._NAME>
are present across PostgreSQL, MySQL, and MongoDB engine types.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app


@pytest.mark.asyncio
async def test_agent_api_docker_command_contains_all_placeholders():
    """
    Test calling POST /api/v1/agents and GET /api/v1/agents/{id}/docker-command
    with PostgreSQL, MySQL, and MongoDB data sources and verify that all
    generic placeholders (HOST, PORT, USER, PASSWORD, NAME) are present.
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
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # 1. Register User & establish session
        register_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "agent_placeholder_tester@example.com",
                "password": "SecurePassword123!",
                "name": "Placeholder Tester",
            },
        )
        assert register_res.status_code == 201, register_res.text

        # 2. Call POST /api/v1/agents with postgresql, mysql, mongodb sources & postgresql target
        agent_create_payload = {
            "name": "Omni-Engine Test Agent",
            "agent_identifier": "omni_test_agent_01",
            "version": "1.0.0",
            "data_sources": [
                {
                    "name": "Postgres Source DB",
                    "type": "postgresql",
                    "role": "source",
                    "identifier": "pg_source",
                },
                {
                    "name": "MySQL Source DB",
                    "type": "mysql",
                    "role": "source",
                    "identifier": "mysql_source",
                },
                {
                    "name": "MongoDB Source DB",
                    "type": "mongodb",
                    "role": "source",
                    "identifier": "mongo_source",
                },
                {
                    "name": "Consolidated Target DB",
                    "type": "postgresql",
                    "role": "target",
                    "identifier": "target_dwh",
                },
            ],
        }

        create_res = await client.post("/api/v1/agents", json=agent_create_payload)
        assert create_res.status_code == 201, create_res.text
        created_data = create_res.json()
        agent_id = created_data["id"]

        # 3. Validate docker_command returned directly from POST /api/v1/agents
        assert "docker_command" in created_data
        bash_cmd = created_data["docker_command"]
        ps_cmd = created_data["docker_command_powershell"]
        oneline_cmd = created_data["docker_command_oneline"]
        env_tpl = created_data["env_template"]

        # Confirm PostgreSQL placeholders
        for cmd_text in (bash_cmd, ps_cmd, oneline_cmd, env_tpl):
            assert "<SRC_PG_SOURCE_HOST>" in cmd_text
            assert "<SRC_PG_SOURCE_PORT>" in cmd_text
            assert "<SRC_PG_SOURCE_USER>" in cmd_text
            assert "<SRC_PG_SOURCE_PASSWORD>" in cmd_text
            assert "<SRC_PG_SOURCE_NAME>" in cmd_text

        # Confirm MySQL placeholders
        for cmd_text in (bash_cmd, ps_cmd, oneline_cmd, env_tpl):
            assert "<SRC_MYSQL_SOURCE_HOST>" in cmd_text
            assert "<SRC_MYSQL_SOURCE_PORT>" in cmd_text
            assert "<SRC_MYSQL_SOURCE_USER>" in cmd_text
            assert "<SRC_MYSQL_SOURCE_PASSWORD>" in cmd_text
            assert "<SRC_MYSQL_SOURCE_NAME>" in cmd_text

        # Confirm MongoDB placeholders
        for cmd_text in (bash_cmd, ps_cmd, oneline_cmd, env_tpl):
            assert "<SRC_MONGO_SOURCE_HOST>" in cmd_text
            assert "<SRC_MONGO_SOURCE_PORT>" in cmd_text
            assert "<SRC_MONGO_SOURCE_USER>" in cmd_text
            assert "<SRC_MONGO_SOURCE_PASSWORD>" in cmd_text
            assert "<SRC_MONGO_SOURCE_NAME>" in cmd_text

        # Confirm Destination PostgreSQL placeholders
        for cmd_text in (bash_cmd, ps_cmd, oneline_cmd, env_tpl):
            assert "<DEST_TARGET_DWH_HOST>" in cmd_text
            assert "<DEST_TARGET_DWH_PORT>" in cmd_text
            assert "<DEST_TARGET_DWH_USER>" in cmd_text
            assert "<DEST_TARGET_DWH_PASSWORD>" in cmd_text
            assert "<DEST_TARGET_DWH_NAME>" in cmd_text

        # 4. Call GET /api/v1/agents/{agent_id}/docker-command
        cmd_res = await client.get(f"/api/v1/agents/{agent_id}/docker-command")
        assert cmd_res.status_code == 200, cmd_res.text
        cmd_data = cmd_res.json()

        # Validate environment_variables dictionary
        env_vars = cmd_data["environment_variables"]
        assert env_vars["SRC_PG_SOURCE_TYPE"] == "postgresql"
        assert env_vars["SRC_PG_SOURCE_URL"] == "postgresql://<SRC_PG_SOURCE_USER>:<SRC_PG_SOURCE_PASSWORD>@<SRC_PG_SOURCE_HOST>:<SRC_PG_SOURCE_PORT>/<SRC_PG_SOURCE_NAME>"

        assert env_vars["SRC_MYSQL_SOURCE_TYPE"] == "mysql"
        assert env_vars["SRC_MYSQL_SOURCE_URL"] == "mysql+pymysql://<SRC_MYSQL_SOURCE_USER>:<SRC_MYSQL_SOURCE_PASSWORD>@<SRC_MYSQL_SOURCE_HOST>:<SRC_MYSQL_SOURCE_PORT>/<SRC_MYSQL_SOURCE_NAME>"

        assert env_vars["SRC_MONGO_SOURCE_TYPE"] == "mongodb"
        assert env_vars["SRC_MONGO_SOURCE_URL"] == "mongodb://<SRC_MONGO_SOURCE_USER>:<SRC_MONGO_SOURCE_PASSWORD>@<SRC_MONGO_SOURCE_HOST>:<SRC_MONGO_SOURCE_PORT>/<SRC_MONGO_SOURCE_NAME>?authSource=admin"

        assert env_vars["DEST_TARGET_DWH_TYPE"] == "postgresql"
        assert env_vars["DEST_TARGET_DWH_URL"] == "postgresql://<DEST_TARGET_DWH_USER>:<DEST_TARGET_DWH_PASSWORD>@<DEST_TARGET_DWH_HOST>:<DEST_TARGET_DWH_PORT>/<DEST_TARGET_DWH_NAME>"

    app.dependency_overrides.clear()
