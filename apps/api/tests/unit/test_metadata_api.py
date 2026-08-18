"""
Unit Tests for Metadata Domain API Endpoints & Ingestion Service
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app
from app.modules.agents.agents_models import Agent
from app.modules.sources.sources_models import DataSource
from app.modules.metadata.metadata_models import (
    MetadataColumn,
    MetadataConstraint,
    MetadataRelationship,
    MetadataSchema,
    MetadataSnapshot,
    MetadataTable,
)


@pytest.mark.asyncio
async def test_metadata_sync_and_retrieval_lifecycle():
    """
    Test full Metadata Domain API lifecycle:
    1. Register user and create Agent with 2 Data Sources (source & target)
    2. POST /api/v1/metadata/sync (Agent authenticated via X-Agent-Token) -> Ingest Snapshot v1
    3. GET /api/v1/metadata/sources/{source_id}/snapshots -> Verify snapshot listed
    4. GET /api/v1/metadata/sources/{source_id}/snapshots/latest -> Verify full schema detail tree
    5. GET /api/v1/metadata/snapshots/{snapshot_id} -> Verify specific snapshot retrieval
    6. POST /api/v1/metadata/sync again -> Verify version auto-increment to v2
    7. Ownership check: Unauthenticated or non-owner user cannot access snapshot -> 403 Forbidden
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
        # 1. Register User & Create Agent with attached Data Sources
        user_payload = {
            "email": "metadata_owner@example.com",
            "password": "Password123!",
            "name": "Metadata Owner",
        }
        res_u = await client.post("/api/v1/auth/register", json=user_payload)
        assert res_u.status_code == 201

        agent_payload = {
            "name": "Metadata Profiler Agent",
            "agent_identifier": "meta_agent_01",
            "version": "1.0.0",
            "data_sources": [
                {
                    "name": "E-Commerce PostgreSQL DB",
                    "type": "postgresql",
                    "role": "source",
                    "identifier": "pg_shop",
                },
                {
                    "name": "Analytics MySQL Target",
                    "type": "mysql",
                    "role": "target",
                    "identifier": "mysql_dw",
                },
            ],
        }
        res_agent = await client.post("/api/v1/agents", json=agent_payload)
        assert res_agent.status_code == 201
        agent_data = res_agent.json()
        agent_id = agent_data["id"]
        api_token = agent_data["api_token"]
        source_id = agent_data["data_sources"][0]["id"]

        # 2. POST /api/v1/metadata/sync — Ingest Metadata Snapshot v1
        sync_payload = {
            "identifier": "pg_shop",
            "database_name": "shop_db",
            "database_version": "PostgreSQL 16.1",
            "total_tables": 2,
            "total_columns": 5,
            "total_rows": 150,
            "schemas": [
                {
                    "schema_name": "public",
                    "tables": [
                        {
                            "schema_name": "public",
                            "table_name": "users",
                            "table_type": "table",
                            "row_count": 100,
                            "size_bytes": 8192,
                            "columns": [
                                {
                                    "column_name": "id",
                                    "ordinal_position": 1,
                                    "data_type": "uuid",
                                    "native_data_type": "uuid",
                                    "nullable": False,
                                    "is_primary_key": True,
                                    "is_unique": True,
                                },
                                {
                                    "column_name": "email",
                                    "ordinal_position": 2,
                                    "data_type": "varchar",
                                    "native_data_type": "varchar(255)",
                                    "nullable": False,
                                    "is_primary_key": False,
                                    "is_unique": True,
                                },
                            ],
                            "constraints": [
                                {
                                    "constraint_name": "pk_users",
                                    "constraint_type": "primary_key",
                                }
                            ],
                        },
                        {
                            "schema_name": "public",
                            "table_name": "orders",
                            "table_type": "table",
                            "row_count": 50,
                            "size_bytes": 4096,
                            "columns": [
                                {
                                    "column_name": "id",
                                    "ordinal_position": 1,
                                    "data_type": "uuid",
                                    "native_data_type": "uuid",
                                    "nullable": False,
                                    "is_primary_key": True,
                                },
                                {
                                    "column_name": "user_id",
                                    "ordinal_position": 2,
                                    "data_type": "uuid",
                                    "native_data_type": "uuid",
                                    "nullable": False,
                                },
                                {
                                    "column_name": "total_amount",
                                    "ordinal_position": 3,
                                    "data_type": "numeric",
                                    "native_data_type": "numeric(10,2)",
                                    "nullable": False,
                                },
                            ],
                            "constraints": [],
                        },
                    ],
                }
            ],
            "relationships": [
                {
                    "source_schema": "public",
                    "source_table": "orders",
                    "source_column": "user_id",
                    "target_schema": "public",
                    "target_table": "users",
                    "target_column": "id",
                    "relationship_type": "foreign_key",
                    "confidence": 1.0,
                }
            ],
        }

        # Transmit sync request using X-Agent-Token
        res_sync = await client.post(
            "/api/v1/metadata/sync",
            json=sync_payload,
            headers={"X-Agent-Token": api_token},
        )
        assert res_sync.status_code == 201, res_sync.text
        snap_v1 = res_sync.json()
        assert snap_v1["version"] == 1
        assert snap_v1["database_name"] == "shop_db"
        assert snap_v1["total_tables"] == 2
        assert snap_v1["total_columns"] == 5
        assert len(snap_v1["schemas"]) == 1
        assert snap_v1["schemas"][0]["schema_name"] == "public"
        assert len(snap_v1["schemas"][0]["tables"]) == 2
        assert len(snap_v1["relationships"]) == 1

        snapshot_id = snap_v1["id"]

        # 3. GET /api/v1/metadata/sources/{source_id}/snapshots (List)
        res_snaps = await client.get(f"/api/v1/metadata/sources/{source_id}/snapshots")
        assert res_snaps.status_code == 200
        snaps_list = res_snaps.json()
        assert len(snaps_list) == 1
        assert snaps_list[0]["version"] == 1

        # 4. GET /api/v1/metadata/sources/{source_id}/snapshots/latest
        res_latest = await client.get(f"/api/v1/metadata/sources/{source_id}/snapshots/latest")
        assert res_latest.status_code == 200
        latest_data = res_latest.json()
        assert latest_data["id"] == snapshot_id
        assert latest_data["version"] == 1
        assert len(latest_data["schemas"][0]["tables"]) == 2

        # 5. GET /api/v1/metadata/snapshots/{snapshot_id} (Detail)
        res_detail = await client.get(f"/api/v1/metadata/snapshots/{snapshot_id}")
        assert res_detail.status_code == 200
        assert res_detail.json()["id"] == snapshot_id

        # 6. POST /api/v1/metadata/sync again -> Version should auto-increment to 2
        res_sync_v2 = await client.post(
            "/api/v1/metadata/sync",
            json=sync_payload,
            headers={"X-Agent-Token": api_token},
        )
        assert res_sync_v2.status_code == 201
        snap_v2 = res_sync_v2.json()
        assert snap_v2["version"] == 2

        # 7. Ownership Security Test: Register second user and attempt accessing first user's metadata -> 403 Forbidden
        user2_payload = {
            "email": "unauthorized_user@example.com",
            "password": "Password123!",
            "name": "Other User",
        }
        await client.post("/api/v1/auth/register", json=user2_payload)

        res_unauth_latest = await client.get(f"/api/v1/metadata/sources/{source_id}/snapshots/latest")
        assert res_unauth_latest.status_code == 403

        res_unauth_detail = await client.get(f"/api/v1/metadata/snapshots/{snapshot_id}")
        assert res_unauth_detail.status_code == 403

    app.dependency_overrides.clear()
