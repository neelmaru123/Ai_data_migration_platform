"""
Security & Permission Middleware Dependencies for Sources Domain
"""

import uuid
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.users.users_dependencies import get_current_active_user
from app.modules.users.users_models import User
from app.modules.agents.agents_models import Agent
from app.modules.agents.agents_services import AgentService
from app.modules.sources.sources_models import DataSource
from app.modules.sources.sources_services import SourceService


async def get_verified_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """
    Middleware dependency that fetches an agent by ID and asserts
    it belongs to the authenticated user.
    """
    agent = await AgentService.get_agent_by_id(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found.",
        )
    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage data sources for this agent.",
        )
    return agent


async def get_verified_data_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DataSource:
    """
    Middleware dependency that fetches a DataSource by ID and asserts
    its owning Agent belongs to the authenticated user.
    """
    source = await SourceService.get_data_source_by_id(db, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data Source with ID '{source_id}' not found.",
        )
    agent = await AgentService.get_agent_by_id(db, source.agent_id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access or modify this data source.",
        )
    return source
