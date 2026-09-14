"""
Unit & API Integration Test for Agent Token Regeneration Endpoint.
Verifies:
1. Initial agent creation returns api_token (token_1).
2. token_1 authenticates successfully on agent-authenticated endpoints.
3. POST /api/v1/agents/{agent_id}/regenerate-token returns a new api_token (token_2 != token_1).
4. Newly generated docker commands embed token_2.
5. Old token_1 is immediately rejected with HTTP 401 Unauthorized.
6. New token_2 authenticates successfully on agent-authenticated endpoints (simulating redeployed container).
7. Unauthorized user cannot regenerate another user's agent token (HTTP 403 Forbidden).
"""

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app


@pytest.mark.asyncio
async def test_agent_token_regeneration_lifecycle():
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
        # 1. Register User 1
        user1_payload = {
            "email": "token_owner@example.com",
            "password": "Password123!",
            "name": "Token Owner",
        }
        res_u1 = await client.post("/api/v1/auth/register", json=user1_payload)
        assert res_u1.status_code == 201, res_u1.text

        # 2. Create Agent
        agent_payload = {
            "name": "Token Rotation Test Agent",
            "agent_identifier": "rotate_agent_001",
            "version": "1.0.0",
            "data_sources": [
                {
                    "name": "App PostgreSQL",
                    "type": "postgresql",
                    "role": "source",
                    "identifier": "src_pg_1",
                },
                {
                    "name": "Analytics Warehouse",
                    "type": "postgresql",
                    "role": "target",
                    "identifier": "dst_pg_1",
                },
            ],
        }
        res_create = await client.post("/api/v1/agents", json=agent_payload)
        assert res_create.status_code == 201, res_create.text
        data_create = res_create.json()

        agent_id = data_create["id"]
        token_1 = data_create["api_token"]
        assert token_1 is not None
        assert token_1.startswith("ag_live_")

        # 3. Confirm token_1 works for container heartbeat authentication
        hb_payload = {
            "status": "online",
            "version": "1.0.0",
            "active_jobs": 0,
        }
        res_hb1 = await client.post(
            "/api/v1/agents/heartbeat",
            json=hb_payload,
            headers={"X-Agent-Token": token_1},
        )
        assert res_hb1.status_code == 200, res_hb1.text
        assert res_hb1.json()["status"] == "online"

        # 4. Call POST /api/v1/agents/{agent_id}/regenerate-token
        res_regen = await client.post(f"/api/v1/agents/{agent_id}/regenerate-token")
        assert res_regen.status_code == 200, res_regen.text
        data_regen = res_regen.json()

        token_2 = data_regen.get("api_token")
        assert token_2 is not None, "Regenerated response must contain api_token"
        assert token_2.startswith("ag_live_"), "Regenerated token must match format"
        assert token_2 != token_1, "Regenerated token must be different from original token"

        # Check that commands are updated with token_2
        assert token_2 in data_regen["docker_command"], "docker_command must contain token_2"
        assert token_2 in data_regen["docker_command_powershell"], "powershell command must contain token_2"
        assert token_2 in data_regen["docker_command_oneline"], "oneline command must contain token_2"
        assert token_2 in data_regen["env_template"], "env_template must contain token_2"
        assert token_1 not in data_regen["docker_command"], "docker_command must NOT contain old token_1"

        # 5. Confirm old token_1 now gets rejected (HTTP 401)
        res_hb_old = await client.post(
            "/api/v1/agents/heartbeat",
            json=hb_payload,
            headers={"X-Agent-Token": token_1},
        )
        assert res_hb_old.status_code == 401, f"Expected 401, got {res_hb_old.status_code}"
        assert "Invalid or revoked Agent API token" in res_hb_old.json().get("detail", "")

        # 6. Confirm redeployed container using new token_2 authenticates successfully (HTTP 200)
        res_hb_new = await client.post(
            "/api/v1/agents/heartbeat",
            json={
                "status": "online",
                "version": "1.0.0",
                "active_jobs": 0,
            },
            headers={"X-Agent-Token": token_2},
        )
        assert res_hb_new.status_code == 200, f"Expected 200, got {res_hb_new.status_code}"
        assert res_hb_new.json()["status"] == "online"

        # 7. Confirm authorization guard: User 2 cannot regenerate User 1's agent token
        user2_payload = {
            "email": "intruder@example.com",
            "password": "Password123!",
            "name": "Intruder",
        }
        res_u2 = await client.post("/api/v1/auth/register", json=user2_payload)
        assert res_u2.status_code == 201

        res_regen_forbidden = await client.post(f"/api/v1/agents/{agent_id}/regenerate-token")
        assert res_regen_forbidden.status_code == 403, f"Expected 403, got {res_regen_forbidden.status_code}"

    app.dependency_overrides.clear()
