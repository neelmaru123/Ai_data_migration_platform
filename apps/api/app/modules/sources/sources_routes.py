"""
FastAPI Router Endpoints for Sources Domain (Data Sources Identity)
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.users.users_dependencies import get_current_active_user
from app.modules.users.users_models import User
from app.modules.agents.agents_models import Agent
from app.modules.sources.sources_models import DataSource
from app.modules.sources.sources_schemas import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
)
from app.modules.sources.sources_services import SourceService
from app.modules.sources.sources_dependencies import (
    get_verified_agent,
    get_verified_data_source,
)

router = APIRouter(prefix="/    ", tags=["Data Sources Identity"])


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    payload: DataSourceCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Register a new Data Source identity assigned to a local Docker Agent.
    Verifies that the target agent exists and belongs to the current user.
    """
    await get_verified_agent(agent_id=payload.agent_id, current_user=current_user, db=session)
    return await SourceService.create_data_source(session=session, data=payload)


@router.get("/agent/{agent_id}", response_model=List[DataSourceResponse])
async def list_data_sources_by_agent(
    agent_id: uuid.UUID,
    agent: Agent = Depends(get_verified_agent),
    session: AsyncSession = Depends(get_db),
):
    """
    List all registered Data Source identities linked to a Docker Agent.
    Verifies agent ownership before returning data sources.
    """
    return await SourceService.get_data_sources_by_agent(
        session=session, agent_id=agent.id
    )


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_data_source(
    source: DataSource = Depends(get_verified_data_source),
):
    """
    Fetch Data Source identity by UUID.
    Verifies that the data source belongs to an agent owned by the current user.
    """
    return source


@router.put("/{source_id}", response_model=DataSourceResponse)
async def update_data_source(
    payload: DataSourceUpdate,
    source: DataSource = Depends(get_verified_data_source),
    session: AsyncSession = Depends(get_db),
):
    """
    Update Data Source identity attributes.
    Verifies that the data source belongs to an agent owned by the current user.
    """
    return await SourceService.update_data_source(
        session=session, source=source, data=payload
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    source: DataSource = Depends(get_verified_data_source),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete Data Source identity.
    Verifies that the data source belongs to an agent owned by the current user.
    """
    await SourceService.delete_data_source(session=session, source=source)
