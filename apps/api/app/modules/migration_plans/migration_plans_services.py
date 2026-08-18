"""
Migration Plans Domain — Business Logic Service
Handles plan creation, retrieval, and lifecycle management.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.websocket_manager import manager
from app.modules.agents.agents_models import Agent
from app.modules.metadata.metadata_models import MetadataSnapshot, MetadataSchema, MetadataTable
from app.modules.migration_plans.migration_plans_engine.migration_plans_llm import (
    PROMPT_VERSION,
    MetadataContextSerializer,
    llm_plan_generator,
)
from app.modules.migration_plans.migration_plans_models import MigrationPlan, MigrationPlanSnapshot
from app.modules.migration_plans.migration_plans_schemas import (
    PlanDetailResponse,
    PlanResponse,
    TargetDatabaseConfig,
    TransformationPlanAST,
)
from app.modules.sources.sources_models import DataSource

logger = logging.getLogger(__name__)


class MigrationPlanService:
    """Orchestrates AI plan generation, persistence, and queries for the Migration Plans domain."""

    @staticmethod
    async def _fetch_latest_snapshots_for_agent(
        session: AsyncSession, agent: Agent
    ) -> tuple[List[MetadataSnapshot], Dict[str, str]]:
        """
        Fetches the latest MetadataSnapshot for every source DataSource attached to the Agent.
        Returns (snapshots_list, alias_map) where alias_map maps data_source_id → logical alias.
        """
        data_sources = agent.data_sources or []
        if not data_sources:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agent has no attached data sources. Add source databases before generating a plan.",
            )

        snapshots: List[MetadataSnapshot] = []
        alias_map: Dict[str, str] = {}

        source_count = 0
        for ds in data_sources:
            # Build logical alias: src_db_1, src_db_2, etc.
            source_count += 1
            alias = ds.identifier if ds.identifier else f"source_db_{source_count}"
            alias_map[str(ds.id)] = alias

            # Fetch latest snapshot for this DataSource
            stmt = (
                select(MetadataSnapshot)
                .where(MetadataSnapshot.data_source_id == ds.id)
                .order_by(MetadataSnapshot.version.desc())
                .limit(1)
                .options(
                    selectinload(MetadataSnapshot.schemas)
                    .selectinload(MetadataSchema.tables)
                    .selectinload(MetadataTable.columns),
                    selectinload(MetadataSnapshot.schemas)
                    .selectinload(MetadataSchema.tables)
                    .selectinload(MetadataTable.constraints),
                    selectinload(MetadataSnapshot.relationships),
                )
            )
            res = await session.execute(stmt)
            snap = res.scalar_one_or_none()

            if snap:
                snapshots.append(snap)
            else:
                logger.warning(
                    f"DataSource '{ds.identifier}' (ID: {ds.id}) has no metadata snapshot. "
                    f"Ensure the Docker Agent has run introspection for this source."
                )

        if not snapshots:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "No metadata snapshots found for any of this agent's data sources. "
                    "Run the Docker Agent first to collect metadata before generating a plan."
                ),
            )

        return snapshots, alias_map

    @staticmethod
    async def create_plan_for_agent(
        session: AsyncSession,
        agent: Agent,
        target_config: TargetDatabaseConfig,
    ) -> MigrationPlan:
        """
        Full plan generation lifecycle:
        1. Fetch latest MetadataSnapshots for all Agent DataSources.
        2. Serialize metadata to sanitized context string (Zero Raw Data).
        3. Call LLM engine to generate TransformationPlanAST.
        4. Persist MigrationPlan + MigrationPlanSnapshot join rows.
        5. Broadcast PLAN_GENERATED WebSocket event.
        """
        # Step 1: Fetch snapshots
        snapshots, alias_map = await MigrationPlanService._fetch_latest_snapshots_for_agent(
            session, agent
        )

        target_db_type = target_config.database_type
        custom_instructions = target_config.custom_instructions

        # Step 2: Serialize metadata → sanitized context
        context_str = MetadataContextSerializer.serialize(
            snapshots=snapshots,
            source_aliases=alias_map,
            target_db_type=target_db_type,
            custom_instructions=custom_instructions,
        )

        # Step 3: Call LLM — may raise RuntimeError on total failure
        plan_status = "completed"
        plan_ast: Optional[TransformationPlanAST] = None
        try:
            plan_ast = llm_plan_generator.generate(
                context_str=context_str,
                target_db_type=target_db_type,
            )
        except RuntimeError as exc:
            logger.error(f"LLM plan generation failed: {exc}")
            plan_status = "draft_failed"

        # Step 4: Persist MigrationPlan
        plan_data: Dict[str, Any] = (
            plan_ast.model_dump(mode="json") if plan_ast else {"error": "LLM generation failed"}
        )

        migration_plan = MigrationPlan(
            user_id=agent.user_id,
            agent_id=agent.id,
            status=plan_status,
            plan_data=plan_data,
            target_config=target_config.model_dump(mode="json"),
            ai_model=f"{settings_llm_provider()}:{settings_llm_model()}",
            prompt_version=PROMPT_VERSION,
            confidence_score=plan_ast.confidence_score if plan_ast else 0.0,
        )
        session.add(migration_plan)
        await session.flush()

        # Step 5: Persist MigrationPlanSnapshot join rows (link plan ↔ all source snapshots)
        for snap in snapshots:
            join_row = MigrationPlanSnapshot(
                migration_plan_id=migration_plan.id,
                metadata_snapshot_id=snap.id,
            )
            session.add(join_row)

        await session.commit()

        # Step 6: Broadcast WebSocket event
        if plan_status == "completed" and plan_ast:
            await manager.broadcast_to_agent(
                agent_id=str(agent.id),
                message={
                    "event_type": "PLAN_GENERATED",
                    "data": {
                        "plan_id": str(migration_plan.id),
                        "agent_id": str(agent.id),
                        "status": plan_status,
                        "confidence_score": migration_plan.confidence_score,
                        "total_tables": len(plan_ast.table_mappings),
                        "warnings_count": len(plan_ast.warnings),
                    },
                },
            )

        logger.info(
            f"Migration plan {migration_plan.id} [{plan_status}] generated for agent '{agent.id}' "
            f"(Tables: {len(plan_ast.table_mappings) if plan_ast else 0}, "
            f"Confidence: {migration_plan.confidence_score:.2f})."
        )

        return migration_plan

    @staticmethod
    async def get_plan_by_id(
        session: AsyncSession, plan_id: uuid.UUID
    ) -> Optional[MigrationPlan]:
        """Fetch MigrationPlan by primary key UUID."""
        res = await session.get(MigrationPlan, plan_id)
        return res

    @staticmethod
    async def list_plans_for_user(
        session: AsyncSession, user_id: uuid.UUID
    ) -> List[MigrationPlan]:
        """List all MigrationPlans owned by a user, ordered by newest first."""
        stmt = (
            select(MigrationPlan)
            .where(MigrationPlan.user_id == user_id)
            .order_by(MigrationPlan.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_plan_data(
        session: AsyncSession,
        plan: MigrationPlan,
        plan_data: Dict[str, Any],
    ) -> MigrationPlan:
        """Save user-edited plan data (UI allows manual adjustment of column mappings)."""
        plan.plan_data = plan_data
        plan.status = "edited"
        await session.commit()
        return plan


def settings_llm_provider() -> str:
    from app.core.config import settings
    return settings.LLM_PROVIDER


def settings_llm_model() -> str:
    from app.core.config import settings
    return settings.LLM_MODEL
