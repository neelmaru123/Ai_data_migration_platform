"""
FastAPI Router Endpoints for Agents Domain
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.users.users_dependencies import get_current_active_user
from app.modules.users.users_models import User
from app.modules.agents.agents_models import Agent
from app.modules.agents.agents_schemas import (
    AgentCreate,
    AgentDetailResponse,
    AgentHeartbeat,
    AgentResponse,
    AgentUpdate,
)
from app.modules.agents.agents_services import AgentService
from app.modules.sources.sources_dependencies import get_verified_agent

router = APIRouter(prefix="/agents", tags=["Agents Management"])


@router.post("", response_model=AgentDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Register a new Docker Agent for the current user.
    Optionally registers initial source and destination database identities concurrently
    in the same atomic database transaction.
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
    Update Docker Agent details (name, status, version).
    Verifies agent ownership.
    """
    return await AgentService.update_agent(
        session=session, agent=agent, data=payload
    )


@router.post("/{agent_id}/heartbeat", response_model=AgentResponse)
async def agent_heartbeat(
    agent_id: uuid.UUID,
    payload: AgentHeartbeat,
    session: AsyncSession = Depends(get_db),
):
    """
    Periodic agent heartbeat ping endpoint.
    Updates agent status, version, and last_seen_at timestamp.
    """
    agent = await AgentService.get_agent_by_id(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found.",
        )
    return await AgentService.process_agent_heartbeat(
        session=session, agent=agent, heartbeat=payload
    )


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
