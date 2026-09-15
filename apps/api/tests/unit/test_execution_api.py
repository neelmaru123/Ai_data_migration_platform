"""
Unit tests for Execution Domain REST API endpoints
"""

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_execution_api_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test polling tasks endpoint with agent token header (unregistered token returns 401/404)
        agent_headers = {"X-Agent-Token": "test_agent_raw_token"}
        resp_tasks = await client.get("/api/v1/agents/tasks", headers=agent_headers)
        assert resp_tasks.status_code in [401, 404]

        # 2. Test execution listing endpoint without auth (returns 401)
        resp_list = await client.get("/api/v1/executions")
        assert resp_list.status_code == 401


def test_truncate_target_schema_and_task_serialization():
    from app.modules.execution.execution_schemas import (
        ExecutionStartRequest,
        AgentTaskItemResponse,
        ExecutionJobResponse,
    )
    import uuid
    from datetime import datetime, timezone

    # Test ExecutionStartRequest defaults to False, accepts True
    req_default = ExecutionStartRequest()
    assert req_default.truncate_target is False

    req_custom = ExecutionStartRequest(truncate_target=True)
    assert req_custom.truncate_target is True

    # Test AgentTaskItemResponse serializes truncate_target
    task_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    task = AgentTaskItemResponse(
        job_id=task_id,
        migration_plan_id=plan_id,
        status="queued",
        is_dry_run=False,
        truncate_target=True,
        created_at=datetime.now(timezone.utc),
    )
    task_dict = task.model_dump(mode="json")
    assert task_dict["truncate_target"] is True

    # Test ExecutionJobResponse serializes truncate_target
    job_resp = ExecutionJobResponse(
        id=task_id,
        migration_plan_id=plan_id,
        status="queued",
        is_dry_run=False,
        truncate_target=True,
        progress=0.0,
        total_rows=0,
        processed_rows=0,
        successful_rows=0,
        failed_rows=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    job_dict = job_resp.model_dump(mode="json")
    assert job_dict["truncate_target"] is True
