"""
Unit & API Integration Tests for Agent Domain Module
Verifies Agent registration with concurrent Data Sources, listing, detail, heartbeat,
per-user uniqueness, status validation, degraded diagnostics, and watchdog stale recovery.
"""

from datetime import datetime, timedelta, timezone
import uuid
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app
from app.modules.agents.agents_models import Agent
from app.modules.agents.agents_services import AgentService
from app.modules.execution.execution_models import MigrationJob
from app.modules.migration_plans.migration_plans_models import MigrationPlan


@pytest.mark.asyncio
async def test_agent_api_lifecycle_and_concurrent_data_sources():
    """
    Test full Agent API lifecycle:
    1. Register user and authenticate via cookies
    2. POST /api/v1/agents with concurrent source and target data_sources
    3. GET /api/v1/agents -> verify list returns attached data sources with role
    4. GET /api/v1/agents/{id} -> verify agent detail
    5. POST /api/v1/agents/heartbeat -> verify heartbeat timestamp & degraded status
    6. PUT /api/v1/agents/{id} -> verify agent detail update (name, version)
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
                    "identifier": "pg_primary",
                },
                {
                    "name": "Destination MySQL Warehouse",
                    "type": "mysql",
                    "role": "target",
                    "identifier": "mysql_warehouse",
                },
            ],
        }
        res_agent = await client.post("/api/v1/agents", json=agent_create_payload)
        assert res_agent.status_code == 201, res_agent.text
        data_agent = res_agent.json()
        assert data_agent["name"] == "Production Edge Agent"
        assert data_agent["status"] == "offline"
        assert data_agent["api_token"] is not None
        assert data_agent["api_token"].startswith("ag_live_")
        assert len(data_agent["data_sources"]) == 2
        assert data_agent["data_sources"][0]["type"] == "postgresql"
        assert data_agent["data_sources"][0]["role"] == "source"
        assert data_agent["data_sources"][1]["type"] == "mysql"
        assert data_agent["data_sources"][1]["role"] == "target"

        agent_id = data_agent["id"]
        api_token = data_agent["api_token"]

        # Verify generated Docker run commands & .env template returned in creation response
        assert "docker_command" in data_agent
        assert "docker_command_powershell" in data_agent
        assert "docker_command_oneline" in data_agent
        assert "env_template" in data_agent
        assert api_token in data_agent["docker_command"]
        assert "SRC_PG_PRIMARY_URL=" in data_agent["docker_command"]
        assert "DEST_MYSQL_WAREHOUSE_URL=" in data_agent["docker_command"]

        # 3. GET /api/v1/agents (List)
        res_list = await client.get("/api/v1/agents")
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1
        assert res_list.json()[0]["id"] == agent_id

        # 4. GET /api/v1/agents/{agent_id} (Detail)
        res_detail = await client.get(f"/api/v1/agents/{agent_id}")
        assert res_detail.status_code == 200
        assert res_detail.json()["agent_identifier"] == "edge_prod_001"

        # 4b. GET /api/v1/agents/{agent_id}/docker-command
        res_cmd = await client.get(f"/api/v1/agents/{agent_id}/docker-command")
        assert res_cmd.status_code == 200
        cmd_data = res_cmd.json()
        assert cmd_data["agent_id"] == agent_id
        assert "docker_command" in cmd_data
        assert "docker_command_powershell" in cmd_data
        assert "docker_command_oneline" in cmd_data
        assert "env_template" in cmd_data
        assert "SRC_PG_PRIMARY_URL" in cmd_data["environment_variables"]
        assert "DEST_MYSQL_WAREHOUSE_URL" in cmd_data["environment_variables"]

        # 5a. Unauthenticated Heartbeat attempt -> 401 Unauthorized
        res_unauth_hb = await client.post(
            "/api/v1/agents/heartbeat",
            json={"status": "online", "version": "1.0.1"},
        )
        assert res_unauth_hb.status_code == 401

        # 5b. Heartbeat with invalid token -> 401 Unauthorized
        res_bad_token_hb = await client.post(
            "/api/v1/agents/heartbeat",
            json={"status": "online", "version": "1.0.1"},
            headers={"X-Agent-Token": "invalid_token_123"},
        )
        assert res_bad_token_hb.status_code == 401

        # 5c. Heartbeat with invalid status value -> 422 Unprocessable Entity (EC-5 validation)
        res_invalid_status_hb = await client.post(
            "/api/v1/agents/heartbeat",
            json={"status": "UNKNOWN_INVALID_STATUS", "version": "1.0.1"},
            headers={"X-Agent-Token": api_token},
        )
        assert res_invalid_status_hb.status_code == 422

        # 5d. Direct Authenticated Heartbeat Ping via X-Agent-Token header -> 200 OK & Status becomes online
        res_hb_direct = await client.post(
            "/api/v1/agents/heartbeat",
            json={"status": "online", "version": "1.0.1"},
            headers={"X-Agent-Token": api_token},
        )
        assert res_hb_direct.status_code == 200
        assert res_hb_direct.json()["status"] == "online"
        assert res_hb_direct.json()["version"] == "1.0.1"

        # 5e. Heartbeat with failing database connection diagnostics -> updates DataSource status and error
        failing_hb_payload = {
            "status": "degraded",
            "version": "1.0.1",
            "data_sources": [
                {
                    "identifier": "pg_primary",
                    "is_healthy": False,
                    "error_type": "ConnectionRefused",
                    "error_message": "Connection refused on host.docker.internal:5432. Ensure database is running.",
                    "latency_ms": 0.0,
                },
                {
                    "identifier": "src_mysql_warehouse",  # Fuzzy matching test (EC-3)
                    "is_healthy": False,
                    "error_type": "UnfilledPlaceholder",
                    "error_message": "Unfilled credential placeholder found in password.",
                    "latency_ms": 0.0,
                },
            ],
        }
        res_failing_hb = await client.post(
            "/api/v1/agents/heartbeat",
            json=failing_hb_payload,
            headers={"X-Agent-Token": api_token},
        )
        assert res_failing_hb.status_code == 200
        assert res_failing_hb.json()["status"] == "degraded"

        # Verify data sources in agent detail reflect the failure state
        res_detail_failing = await client.get(f"/api/v1/agents/{agent_id}")
        assert res_detail_failing.status_code == 200
        ds_list = {ds["identifier"]: ds for ds in res_detail_failing.json()["data_sources"]}
        assert ds_list["pg_primary"]["status"] == "ConnectionRefused"
        assert "Connection refused" in ds_list["pg_primary"]["last_error"]
        assert ds_list["pg_primary"]["last_checked_at"] is not None
        assert ds_list["mysql_warehouse"]["status"] == "UnfilledPlaceholder"
        assert "Unfilled credential" in ds_list["mysql_warehouse"]["last_error"]

        # 5f. Self-healing / recovery: Heartbeat with restored healthy database connections -> updates status to healthy
        recovered_hb_payload = {
            "status": "online",
            "version": "1.0.1",
            "data_sources": [
                {
                    "identifier": "pg_primary",
                    "is_healthy": True,
                    "latency_ms": 4.2,
                    "database_name": "prod_db",
                },
                {
                    "identifier": "mysql_warehouse",
                    "is_healthy": True,
                    "latency_ms": 8.1,
                    "database_name": "warehouse_db",
                },
            ],
        }
        res_recovered_hb = await client.post(
            "/api/v1/agents/heartbeat",
            json=recovered_hb_payload,
            headers={"X-Agent-Token": api_token},
        )
        assert res_recovered_hb.status_code == 200

        # Verify data sources in agent detail reflect the recovered healthy state
        res_detail_healthy = await client.get(f"/api/v1/agents/{agent_id}")
        assert res_detail_healthy.status_code == 200
        ds_healthy_list = {ds["identifier"]: ds for ds in res_detail_healthy.json()["data_sources"]}
        assert ds_healthy_list["pg_primary"]["status"] == "healthy"
        assert ds_healthy_list["pg_primary"]["last_error"] is None
        assert ds_healthy_list["mysql_warehouse"]["status"] == "healthy"
        assert ds_healthy_list["mysql_warehouse"]["last_error"] is None

        # 5g. Graceful offline heartbeat (EC-2)
        res_offline_hb = await client.post(
            "/api/v1/agents/heartbeat",
            json={"status": "offline", "version": "1.0.1"},
            headers={"X-Agent-Token": api_token},
        )
        assert res_offline_hb.status_code == 200
        assert res_offline_hb.json()["status"] == "offline"

        # 6. PUT /api/v1/agents/{agent_id} (EC-7: updates name and version)
        res_put = await client.put(
            f"/api/v1/agents/{agent_id}",
            json={"name": "Updated Production Edge Agent", "version": "1.0.2"},
        )
        assert res_put.status_code == 200
        assert res_put.json()["name"] == "Updated Production Edge Agent"
        assert res_put.json()["version"] == "1.0.2"

        # 7. Ownership check & Per-user uniqueness (EC-6): Register User 2
        user2_payload = {
            "email": "other_user@example.com",
            "password": "Password123!",
            "name": "Other User",
        }
        await client.post("/api/v1/auth/register", json=user2_payload)

        # User 2 can create an agent with the SAME agent_identifier as User 1 (EC-6 per-user uniqueness)
        res_u2_agent = await client.post(
            "/api/v1/agents",
            json={"name": "User2 Agent", "agent_identifier": "edge_prod_001"},
        )
        assert res_u2_agent.status_code == 201
        assert res_u2_agent.json()["agent_identifier"] == "edge_prod_001"

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


@pytest.mark.asyncio
async def test_stale_agent_and_orphaned_job_watchdog():
    """
    Test Watchdog Recovery (EC-1 & EC-8):
    1. Create an agent that was online in the past (last_seen_at > 60s ago).
    2. Attach a running MigrationJob to this agent.
    3. Execute AgentService.check_stale_agents_and_jobs.
    4. Assert agent is transitioned to 'offline'.
    5. Assert orphaned MigrationJob is transitioned to 'failed' with timeout reason.
    """
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # Create user
        from app.modules.users.users_models import User
        user = User(
            email="watchdog_test@example.com",
            password_hash="hashed_pwd",
            name="Watchdog Test User",
        )
        session.add(user)
        await session.flush()

        # Create agent that hasn't sent heartbeat in 120 seconds
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        stale_agent = Agent(
            user_id=user.id,
            name="Stale Watchdog Agent",
            agent_identifier="stale_agent_001",
            api_token_hash="fake_hash_123",
            status="online",
            last_seen_at=stale_time,
        )
        session.add(stale_agent)
        await session.flush()

        # Create a migration plan and running job for this stale agent
        plan = MigrationPlan(
            user_id=user.id,
            agent_id=stale_agent.id,
            status="approved",
            plan_data={"source_type": "postgresql", "target_type": "mysql"},
        )
        session.add(plan)
        await session.flush()

        running_job = MigrationJob(
            migration_plan_id=plan.id,
            agent_id=stale_agent.id,
            status="running",
            progress=45.0,
            started_at=datetime.now(timezone.utc),
        )
        session.add(running_job)
        await session.commit()

        # Run the watchdog check
        stats = await AgentService.check_stale_agents_and_jobs(session, stale_threshold_seconds=60)
        assert stats["stale_agents_marked_offline"] == 1
        assert stats["failed_jobs_recovered"] == 1

        # Verify in DB
        stmt_agent = select(Agent).where(Agent.id == stale_agent.id)
        res_a = await session.execute(stmt_agent)
        updated_agent = res_a.scalar_one()
        assert updated_agent.status == "offline"

        stmt_job = select(MigrationJob).where(MigrationJob.id == running_job.id)
        res_j = await session.execute(stmt_job)
        updated_job = res_j.scalar_one()
        assert updated_job.status == "failed"
        assert "timed out" in updated_job.error_message
        assert updated_job.completed_at is not None

    await test_engine.dispose()
