"""
FastAPI Router Endpoints for Agents Domain
"""

import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_jwt_token
from app.core.websocket_manager import manager
from app.modules.agents.agents_dependencies import get_current_agent
from app.modules.agents.agents_models import Agent
from app.modules.agents.agents_schemas import (
    AgentCreate,
    AgentDetailResponse,
    AgentDockerCommandResponse,
    AgentHeartbeat,
    AgentResponse,
    AgentUpdate,
)
from app.modules.agents.agents_services import AgentService
from app.modules.sources.sources_dependencies import get_verified_agent
from app.modules.users.users_dependencies import get_current_active_user
from app.modules.users.users_models import User
from app.modules.users.users_services import UserService

router = APIRouter(prefix="/agents", tags=["Agents Management"])


@router.post("", response_model=AgentDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Register a new Docker Agent for the current user.
    Generates a secure API Token and initial 'offline' status.
    Optionally registers initial source and destination database identities concurrently
    in the same atomic database transaction.
    Returns ready-to-run Docker commands with token and database credential placeholders.
    """
    return await AgentService.create_agent(
        session=session, user_id=current_user.id, data=payload
    )


@router.get("", response_model=List[AgentDetailResponse])
async def list_agents(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """List all Docker Agents registered by the authenticated user."""
    return await AgentService.list_agents_by_user(
        session=session, user_id=current_user.id
    )


@router.get("/{agent_id}/docker-command", response_model=AgentDockerCommandResponse)
async def get_agent_docker_command(
    agent: Agent = Depends(get_verified_agent),
):
    """
    Generate and retrieve ready-to-run Docker commands (Bash, PowerShell, Single-line)
    and .env configuration template for an existing Docker Agent.
    Verifies agent ownership.
    """
    return AgentService.get_agent_docker_command(agent=agent)


@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(
    agent: Agent = Depends(get_verified_agent),
):
    """
    Fetch Docker Agent details by UUID along with all attached Data Sources.
    Verifies agent ownership.
    """
    return agent




@router.put("/{agent_id}", response_model=AgentDetailResponse)
async def update_agent(
    payload: AgentUpdate,
    agent: Agent = Depends(get_verified_agent),
    session: AsyncSession = Depends(get_db),
):
    """
    Update Docker Agent details (name, version).
    Verifies agent ownership.
    """
    return await AgentService.update_agent(
        session=session, agent=agent, data=payload
    )


@router.post("/heartbeat", response_model=AgentResponse)
async def agent_heartbeat_direct(
    payload: AgentHeartbeat,
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
):
    """
    Direct authenticated agent heartbeat ping endpoint.
    Verifies agent identity via 'X-Agent-Token' header and updates status/version/last_seen_at.
    Broadcasts real-time signal to Web App subscribers over WebSocket.
    """
    return await AgentService.process_agent_heartbeat(
        session=session, agent=current_agent, heartbeat=payload
    )


@router.websocket("/ws/{agent_id}")
async def agent_websocket_endpoint(
    websocket: WebSocket,
    agent_id: uuid.UUID,
    token: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """
    Authenticated WebSocket endpoint for Web Applications to listen for real-time status changes
    and connection events for a specific agent.
    Requires user access JWT token passed as query parameter `?token=<jwt>`.
    Verifies agent ownership.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token missing")
        return

    try:
        payload = decode_jwt_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")
        if not user_id_str or token_type != "access":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid access token")
            return
        user_id = uuid.UUID(user_id_str)
    except (PyJWTError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired access token")
        return

    user = await UserService.get_user_by_id(session, user_id)
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User account invalid or inactive")
        return

    agent = await AgentService.get_agent_by_id(session, agent_id)
    if not agent or agent.user_id != user.id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden agent access")
        return

    await manager.connect(str(agent_id), websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data:
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    if data.strip().lower() == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(str(agent_id), websocket)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent: Agent = Depends(get_verified_agent),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete Docker Agent.
    Cascade-deletes all linked Data Sources identity records.
    Verifies agent ownership.
    """
    await AgentService.delete_agent(session=session, agent=agent)
