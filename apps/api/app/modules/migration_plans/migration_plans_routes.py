"""
Migration Plans Domain — FastAPI REST API Routes
"""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.modules.agents.agents_dependencies import hash_agent_token
from app.modules.agents.agents_models import Agent
from app.modules.migration_plans.migration_plans_schemas import (
    PlanDetailResponse,
    PlanGenerationRequest,
    PlanResponse,
)
from app.modules.migration_plans.migration_plans_services import MigrationPlanService
from app.modules.users.users_dependencies import get_current_active_user, get_current_user
from app.modules.users.users_models import User

router = APIRouter(prefix="/plans", tags=["Migration Plans & AI Generation"])


async def _get_agent_for_user(
    agent_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> Agent:
    """Fetch and verify agent ownership."""
    from sqlalchemy import select
    from app.modules.sources.sources_models import DataSource

    stmt = (
        select(Agent)
        .where(Agent.id == agent_id, Agent.user_id == current_user.id)
        .options(selectinload(Agent.data_sources))
    )
    res = await session.execute(stmt)
    agent = res.scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found or does not belong to your account.",
        )
    return agent


@router.post("/generate", response_model=PlanDetailResponse, status_code=status.HTTP_201_CREATED)
async def generate_migration_plan(
    payload: PlanGenerationRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Generate an AI Migration Plan for all source databases connected to the specified Agent.

    The LLM receives ONLY structural schema metadata (tables, columns, data types, FK relationships).
    No passwords, row data, or sensitive information is transmitted.

    Returns a complete `TransformationPlanAST` JSON with:
    - Per-table transformation strategy (direct_copy, merge, split_target)
    - Per-column mappings with transformation_type and UI badge type
    - Pre/post migration DDL statements
    - AI narrative explanation and warnings
    """
    agent = await _get_agent_for_user(payload.agent_id, current_user, session)
    plan = await MigrationPlanService.create_plan_for_agent(
        session=session, agent=agent, target_config=payload.target_config
    )
    return PlanDetailResponse(
        id=plan.id,
        agent_id=plan.agent_id,
        status=plan.status,
        ai_model=plan.ai_model,
        confidence_score=plan.confidence_score,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        plan_data=plan.plan_data,
        target_config=plan.target_config,
        prompt_version=plan.prompt_version,
    )


@router.get("", response_model=List[PlanResponse])
async def list_migration_plans(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """List all migration plans for the authenticated user."""
    plans = await MigrationPlanService.list_plans_for_user(
        session=session, user_id=current_user.id
    )
    return [
        PlanResponse(
            id=p.id,
            agent_id=p.agent_id,
            status=p.status,
            ai_model=p.ai_model,
            confidence_score=p.confidence_score,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in plans
    ]


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_migration_plan(
    plan_id: uuid.UUID,
    request: Request,
    x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token"),
    session: AsyncSession = Depends(get_db),
):
    """
    Fetch the complete migration plan including full TransformationPlanAST JSON for UI rendering.
    Supports user session or Agent authentication via X-Agent-Token header.
    """
    plan = await MigrationPlanService.get_plan_by_id(session, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Migration plan '{plan_id}' not found.",
        )

    # 1. Agent Token Auth
    if x_agent_token:
        token_hash = hash_agent_token(x_agent_token)
        from sqlalchemy import select
        res_agent = await session.execute(select(Agent).where(Agent.api_token_hash == token_hash))
        agent = res_agent.scalar_one_or_none()
        if agent and plan.agent_id == agent.id:
            return PlanDetailResponse(
                id=plan.id,
                agent_id=plan.agent_id,
                status=plan.status,
                ai_model=plan.ai_model,
                confidence_score=plan.confidence_score,
                created_at=plan.created_at,
                updated_at=plan.updated_at,
                plan_data=plan.plan_data,
                target_config=plan.target_config,
                prompt_version=plan.prompt_version,
            )

    # 2. User Auth Fallback
    try:
        current_user = await get_current_user(request=request, bearer_token=None, db=session)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide valid user session or X-Agent-Token.",
        )

    if not current_user or plan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this migration plan.",
        )

    return PlanDetailResponse(
        id=plan.id,
        agent_id=plan.agent_id,
        status=plan.status,
        ai_model=plan.ai_model,
        confidence_score=plan.confidence_score,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        plan_data=plan.plan_data,
        target_config=plan.target_config,
        prompt_version=plan.prompt_version,
    )


@router.put("/{plan_id}", response_model=PlanDetailResponse)
async def update_migration_plan(
    plan_id: uuid.UUID,
    plan_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Save user-edited plan data.
    The UI allows manual adjustment of column mappings — this endpoint persists those edits.
    Plan status is updated to 'edited'.
    """
    plan = await MigrationPlanService.get_plan_by_id(session, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Migration plan '{plan_id}' not found.",
        )
    if plan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit this migration plan.",
        )
    updated = await MigrationPlanService.update_plan_data(session, plan, plan_data)
    return PlanDetailResponse(
        id=updated.id,
        agent_id=updated.agent_id,
        status=updated.status,
        ai_model=updated.ai_model,
        confidence_score=updated.confidence_score,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        plan_data=updated.plan_data,
        target_config=updated.target_config,
        prompt_version=updated.prompt_version,
    )
