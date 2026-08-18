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
