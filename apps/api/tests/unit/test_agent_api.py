"""
Unit & API Integration Tests for Agent Domain Module
Verifies Agent registration with concurrent Data Sources, listing, detail, heartbeat, and ownership checks.
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app


@pytest.mark.asyncio
async def test_agent_api_lifecycle_and_concurrent_data_sources():
    """
    Test full Agent API lifecycle:
    1. Register user and authenticate via cookies
    2. POST /api/v1/agents with concurrent source and target data_sources
    3. GET /api/v1/agents -> verify list returns attached data sources with role
    4. GET /api/v1/agents/{id} -> verify agent detail
    5. POST /api/v1/agents/{id}/heartbeat -> verify heartbeat timestamp update
    6. PUT /api/v1/agents/{id} -> verify agent detail update
    7. Ownership security check: register second user and attempt accessing first user's agent -> 403 Forbidden
    8. DELETE /api/v1/agents/{id} -> verify deletion
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
        # 1. Register User 1
        user1_payload = {
            "email": "agent_owner@example.com",
            "password": "Password123!",
            "name": "Agent Owner",
        }
        res_u1 = await client.post("/api/v1/auth/register", json=user1_payload)
        assert res_u1.status_code == 201

        # 2. POST /api/v1/agents with concurrent source and target data sources
        agent_create_payload = {
            "name": "Production Edge Agent",
            "agent_identifier": "edge_prod_001",
            "version": "1.0.0",
            "data_sources": [
                {
                    "name": "Primary PostgreSQL Source",
                    "type": "postgresql",
                    "role": "source",
                    "identifier": "src_pg_instance_01",
                },
                {
                    "name": "Destination MySQL Warehouse",
                    "type": "mysql",
                    "role": "target",
                    "identifier": "dest_mysql_instance_01",
                },
            ],
        }
        res_agent = await client.post("/api/v1/agents", json=agent_create_payload)
        assert res_agent.status_code == 201, res_agent.text
        data_agent = res_agent.json()
        assert data_agent["name"] == "Production Edge Agent"
        assert len(data_agent["data_sources"]) == 2
        assert data_agent["data_sources"][0]["type"] == "postgresql"
        assert data_agent["data_sources"][0]["role"] == "source"
        assert data_agent["data_sources"][1]["type"] == "mysql"
        assert data_agent["data_sources"][1]["role"] == "target"

        agent_id = data_agent["id"]

        # 3. GET /api/v1/agents (List)
        res_list = await client.get("/api/v1/agents")
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1
        assert res_list.json()[0]["id"] == agent_id

        # 4. GET /api/v1/agents/{agent_id} (Detail)
        res_detail = await client.get(f"/api/v1/agents/{agent_id}")
        assert res_detail.status_code == 200
        assert res_detail.json()["agent_identifier"] == "edge_prod_001"

        # 5. POST /api/v1/agents/{agent_id}/heartbeat
        res_hb = await client.post(
            f"/api/v1/agents/{agent_id}/heartbeat",
            json={"status": "online", "version": "1.0.1"},
        )
        assert res_hb.status_code == 200
        assert res_hb.json()["version"] == "1.0.1"

        # 6. PUT /api/v1/agents/{agent_id}
        res_put = await client.put(
            f"/api/v1/agents/{agent_id}",
            json={"name": "Updated Production Edge Agent"},
        )
        assert res_put.status_code == 200
        assert res_put.json()["name"] == "Updated Production Edge Agent"

        # 7. Ownership check: Register User 2 and attempt access to User 1's Agent
        user2_payload = {
            "email": "other_user@example.com",
            "password": "Password123!",
            "name": "Other User",
        }
        await client.post("/api/v1/auth/register", json=user2_payload)

        # Try GET User 1's Agent as User 2 -> 403 Forbidden
        res_unauth_get = await client.get(f"/api/v1/agents/{agent_id}")
        assert res_unauth_get.status_code == 403

        # 8. Re-authenticate as User 1 and DELETE Agent
        await client.post(
            "/api/v1/auth/login",
            json={"email": "agent_owner@example.com", "password": "Password123!"},
        )
        res_del = await client.delete(f"/api/v1/agents/{agent_id}")
        assert res_del.status_code == 204

        # Verify agent no longer exists
        res_get_del = await client.get(f"/api/v1/agents/{agent_id}")
        assert res_get_del.status_code == 404

    app.dependency_overrides.clear()
    await test_engine.dispose()
