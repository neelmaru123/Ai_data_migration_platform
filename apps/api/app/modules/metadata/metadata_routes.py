"""
FastAPI Router Endpoints for Metadata Domain
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.agents.agents_dependencies import get_current_agent
from app.modules.agents.agents_models import Agent
from app.modules.metadata.metadata_schemas import (
    MetadataSnapshotDetailResponse,
    MetadataSnapshotResponse,
    MetadataSnapshotSyncPayload,
)
from app.modules.metadata.metadata_services import MetadataService
from app.modules.sources.sources_dependencies import get_verified_data_source
from app.modules.sources.sources_models import DataSource
from app.modules.users.users_dependencies import get_current_active_user
from app.modules.users.users_models import User

router = APIRouter(prefix="/metadata", tags=["Metadata Introspection & Management"])


@router.post("/sync", response_model=MetadataSnapshotDetailResponse, status_code=status.HTTP_201_CREATED)
async def sync_agent_metadata(
    payload: MetadataSnapshotSyncPayload,
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
):
    """
    Authenticated Docker Agent metadata synchronization endpoint.
    Accepts full structural schema introspection payload from agent, matches target DataSource,
    persists versioned snapshot hierarchy in PostgreSQL control plane, and pushes real-time WebSocket event.
    """
    return await MetadataService.ingest_agent_metadata_snapshot(
        session=session, agent=current_agent, payload=payload
    )


@router.get("/sources/{source_id}/snapshots", response_model=List[MetadataSnapshotResponse])
async def list_source_snapshots(
    source: DataSource = Depends(get_verified_data_source),
    session: AsyncSession = Depends(get_db),
):
    """
    List all versioned metadata snapshots for a specified DataSource.
    Verifies user ownership.
    """
    return await MetadataService.list_snapshots_for_source(
        session=session, data_source_id=source.id
    )


@router.get("/sources/{source_id}/snapshots/latest", response_model=MetadataSnapshotDetailResponse)
async def get_latest_source_snapshot(
    source: DataSource = Depends(get_verified_data_source),
    session: AsyncSession = Depends(get_db),
):
    """
    Fetch the latest hierarchical metadata snapshot (schemas, tables, columns, constraints, relationships)
    for a specified DataSource.
    Verifies user ownership.
    """
    snapshot = await MetadataService.get_latest_snapshot_for_source(
        session=session, data_source_id=source.id
    )
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metadata snapshots found for data source '{source.id}'. Ensure agent is running.",
        )
    return snapshot


@router.get("/snapshots/{snapshot_id}", response_model=MetadataSnapshotDetailResponse)
async def get_snapshot_detail(
    snapshot_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Fetch a specific versioned metadata snapshot by primary UUID.
    Verifies user ownership.
    """
    snapshot = await MetadataService.get_snapshot_by_id(session, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata snapshot with ID '{snapshot_id}' not found.",
        )

    # Verify ownership via linked DataSource -> Agent -> user_id
    source = await session.get(DataSource, snapshot.data_source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated data source for snapshot not found.",
        )

    agent = await session.get(Agent, source.agent_id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this metadata snapshot.",
        )

    return snapshot
