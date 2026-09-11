"""
Migration Plans Domain — Business Logic Service
Handles plan creation, retrieval, and lifecycle management.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.websocket_manager import manager
from app.modules.agents.agents_models import Agent
from app.modules.metadata.metadata_models import MetadataSnapshot, MetadataSchema, MetadataTable
from app.modules.migration_plans.migration_plans_engine.migration_plans_llm import (
    PROMPT_VERSION,
    MetadataContextSerializer,
    llm_plan_generator,
)
from app.modules.migration_plans.migration_plans_models import (
    MigrationPlan,
    MigrationPlanSnapshot,
    MigrationPlanVersion,
)
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
            if ds.role == "target":
                continue
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
        Full plan generation lifecycle using LangGraph StateGraph:
        1. Fetch latest MetadataSnapshots for all Agent DataSources.
        2. Execute LangGraph workflow (Nodes 1 -> 2 -> 3 -> Router -> Node 5 interrupt).
        3. Run feasibility validator.
        4. Persist MigrationPlan entity with validation status.
        """
        from app.modules.migration_plans.migration_plans_engine.migration_plans_graph import (
            migration_plan_graph,
        )
        from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
            MigrationPlanValidator,
        )

        snapshots, alias_map = await MigrationPlanService._fetch_latest_snapshots_for_agent(
            session, agent
        )

        target_db_type = target_config.database_type
        # Auto-detect target database type from agent's target data source if default or unset
        target_ds = next(
            (ds for ds in (agent.data_sources or []) if ds.role in ("target", "both") and ds.type),
            None,
        )
        if target_ds and (not target_db_type or target_db_type.lower() == "postgresql"):
            target_db_type = target_ds.type.lower()
            target_config.database_type = target_db_type

        custom_instructions = target_config.custom_instructions

        initial_state = {
            "agent_id": str(agent.id),
            "user_id": str(agent.user_id),
            "target_db_type": target_db_type,
            "custom_instructions": custom_instructions,
            "context_yaml": "",
            "snapshots": snapshots,
            "alias_map": alias_map,
            "current_ast": None,
            "validation_result": None,
            "user_feedback": None,
            "manual_edits": None,
            "attempt_count": 0,
            "is_approved": False,
            "feasibility_explanation": None,
            "persisted_plan_id": None,
        }

        # Run LangGraph graph
        plan_status = "draft"
        plan_ast_dict = None
        val_res_dict = None

        try:
            res_state = await migration_plan_graph.ainvoke(initial_state)
            plan_ast_dict = res_state.get("current_ast")
            val_res_dict = res_state.get("validation_result")
            if res_state.get("feasibility_explanation"):
                plan_status = "invalid"
            else:
                plan_status = "draft"
        except Exception as exc:
            logger.error(f"LangGraph execution exception: {exc}")
            # Direct LLM fallback if graph interrupted
            context_str = MetadataContextSerializer.serialize(
                snapshots=snapshots,
                source_aliases=alias_map,
                target_db_type=target_db_type,
                custom_instructions=custom_instructions,
            )
            try:
                ast_obj = llm_plan_generator.generate(context_str, target_db_type)
                plan_ast_dict = ast_obj.model_dump(mode="json")
                val_res = MigrationPlanValidator.validate(plan_ast_dict, snapshots, alias_map)
                val_res_dict = val_res.model_dump(mode="json")
                plan_status = "draft"
            except Exception as inner_exc:
                logger.error(f"Fallback generation also failed: {inner_exc}")
                plan_status = "draft_failed"

        if not val_res_dict and plan_ast_dict:
            val_res = MigrationPlanValidator.validate(plan_ast_dict, snapshots, alias_map)
            val_res_dict = val_res.model_dump(mode="json")

        is_valid = val_res_dict.get("is_valid", False) if val_res_dict else False

        migration_plan = MigrationPlan(
            user_id=agent.user_id,
            agent_id=agent.id,
            status=plan_status,
            plan_data=plan_ast_dict or {"error": "Generation failed"},
            target_config=target_config.model_dump(mode="json"),
            ai_model=f"{settings_llm_provider()}:{settings_llm_model()}",
            prompt_version=PROMPT_VERSION,
            confidence_score=plan_ast_dict.get("confidence_score", 0.9) if plan_ast_dict else 0.0,
            is_valid=is_valid,
            validation_errors=val_res_dict,
        )
        session.add(migration_plan)
        await session.flush()

        for snap in snapshots:
            join_row = MigrationPlanSnapshot(
                migration_plan_id=migration_plan.id,
                metadata_snapshot_id=snap.id,
            )
            session.add(join_row)

        # Create Version 1 snapshot
        initial_version = MigrationPlanVersion(
            migration_plan_id=migration_plan.id,
            version_number=1,
            edit_type="initial_ai_generation",
            user_feedback=target_config.custom_instructions if target_config else None,
            plan_data=plan_ast_dict or {"error": "Generation failed"},
            is_valid=is_valid,
            confidence_score=plan_ast_dict.get("confidence_score", 0.9) if plan_ast_dict else 0.0,
            validation_errors=val_res_dict,
        )
        session.add(initial_version)

        await session.commit()
        return migration_plan

    @staticmethod
    async def get_plan_by_id(
        session: AsyncSession, plan_id: uuid.UUID
    ) -> Optional[MigrationPlan]:
        """Fetch MigrationPlan by primary key UUID with agent and data_sources eagerly loaded."""
        stmt = (
            select(MigrationPlan)
            .where(MigrationPlan.id == plan_id)
            .options(
                selectinload(MigrationPlan.agent).selectinload(Agent.data_sources)
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

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
    async def _check_active_execution_lock(session: AsyncSession, plan_id: uuid.UUID):
        """Verifies that no active execution job is running for the given migration plan."""
        from app.modules.execution.execution_models import MigrationJob
        stmt = select(MigrationJob).where(
            MigrationJob.migration_plan_id == plan_id,
            MigrationJob.status.in_(["queued", "preparing", "running"]),
        )
        res = await session.execute(stmt)
        active_job = res.scalar_one_or_none()
        if active_job:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot edit migration plan while execution job '{active_job.id}' is active (status: '{active_job.status}').",
            )

    @staticmethod
    async def update_plan_data(
        session: AsyncSession,
        plan: MigrationPlan,
        plan_data: Dict[str, Any],
    ) -> MigrationPlan:
        """Save user-edited plan data and run feasibility validation."""
        from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
            MigrationPlanValidator,
        )

        await MigrationPlanService._check_active_execution_lock(session, plan.id)

        plan.plan_data = plan_data
        if plan.agent:
            snapshots, alias_map = await MigrationPlanService._fetch_latest_snapshots_for_agent(
                session, plan.agent
            )
            val_res = MigrationPlanValidator.validate(plan_data, snapshots, alias_map)
            val_dict = val_res.model_dump(mode="json")
            plan.is_valid = val_res.is_valid
            plan.validation_errors = val_dict
            plan.status = "edited" if val_res.is_valid else "invalid_edits"
        else:
            plan.status = "edited"

        # Compute next version number and persist version snapshot
        stmt_ver = select(func.coalesce(func.max(MigrationPlanVersion.version_number), 0)).where(
            MigrationPlanVersion.migration_plan_id == plan.id
        )
        max_ver = (await session.execute(stmt_ver)).scalar_one()
        next_ver = max_ver + 1

        version_snapshot = MigrationPlanVersion(
            migration_plan_id=plan.id,
            version_number=next_ver,
            edit_type="manual_ast_edit",
            plan_data=plan_data,
            is_valid=plan.is_valid,
            confidence_score=plan_data.get("confidence_score", 1.0) if isinstance(plan_data, dict) else 1.0,
            validation_errors=plan.validation_errors,
        )
        session.add(version_snapshot)

        await session.commit()
        return plan

    @staticmethod
    async def refine_plan(
        session: AsyncSession,
        plan: MigrationPlan,
        user_feedback: str,
    ) -> MigrationPlan:
        """Refines a plan using natural language user feedback via LLM + Validator."""
        from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
            MigrationPlanValidator,
        )

        await MigrationPlanService._check_active_execution_lock(session, plan.id)

        # Acquire row lock to serialize concurrent refinement updates (EC-24)
        stmt_lock = select(MigrationPlan).where(MigrationPlan.id == plan.id).with_for_update()
        res_lock = await session.execute(stmt_lock)
        locked_plan = res_lock.scalar_one_or_none()
        if locked_plan:
            plan = locked_plan

        if not plan.agent:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Migration plan has no attached agent.",
            )

        snapshots, alias_map = await MigrationPlanService._fetch_latest_snapshots_for_agent(
            session, plan.agent
        )

        target_db_type = (
            plan.target_config.get("database_type", "postgresql")
            if plan.target_config
            else "postgresql"
        )
        custom_instructions = (
            plan.target_config.get("custom_instructions", "")
            if plan.target_config
            else ""
        )

        context_str = MetadataContextSerializer.serialize(
            snapshots=snapshots,
            source_aliases=alias_map,
            target_db_type=target_db_type,
            custom_instructions=custom_instructions,
        )

        llm_timeout = float(getattr(settings, "LLM_TIMEOUT_SECONDS", 180.0))
        try:
            refined_ast_obj = await asyncio.wait_for(
                asyncio.to_thread(
                    llm_plan_generator.refine,
                    context_str=context_str,
                    current_ast_dict=plan.plan_data,
                    user_feedback=user_feedback,
                ),
                timeout=llm_timeout,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"LLM plan refinement timed out after {int(llm_timeout)} seconds. Please try again.",
            )

        refined_ast_dict = refined_ast_obj.model_dump(mode="json")
        val_res = MigrationPlanValidator.validate(refined_ast_dict, snapshots, alias_map)
        val_dict = val_res.model_dump(mode="json")

        plan.plan_data = refined_ast_dict
        plan.is_valid = val_res.is_valid
        plan.validation_errors = val_dict
        plan.status = "edited" if val_res.is_valid else "invalid_edits"

        # Compute next version number and insert version snapshot
        stmt_ver = select(func.coalesce(func.max(MigrationPlanVersion.version_number), 0)).where(
            MigrationPlanVersion.migration_plan_id == plan.id
        )
        max_ver = (await session.execute(stmt_ver)).scalar_one()
        next_ver = max_ver + 1

        version_snapshot = MigrationPlanVersion(
            migration_plan_id=plan.id,
            version_number=next_ver,
            edit_type="llm_refinement",
            user_feedback=user_feedback,
            plan_data=refined_ast_dict,
            is_valid=val_res.is_valid,
            confidence_score=refined_ast_dict.get("confidence_score", 0.9) if isinstance(refined_ast_dict, dict) else 0.9,
            validation_errors=val_dict,
        )
        session.add(version_snapshot)

        await session.commit()
        return plan

    @staticmethod
    async def list_plan_versions(
        session: AsyncSession,
        plan_id: uuid.UUID,
    ) -> List[MigrationPlanVersion]:
        """Fetch all versions of a migration plan, ordered from newest to oldest."""
        stmt = (
            select(MigrationPlanVersion)
            .where(MigrationPlanVersion.migration_plan_id == plan_id)
            .order_by(MigrationPlanVersion.version_number.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_plan_version(
        session: AsyncSession,
        plan_id: uuid.UUID,
        version_number: int,
    ) -> Optional[MigrationPlanVersion]:
        """Fetch a specific version of a migration plan by plan ID and version number."""
        stmt = select(MigrationPlanVersion).where(
            MigrationPlanVersion.migration_plan_id == plan_id,
            MigrationPlanVersion.version_number == version_number,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def restore_plan_version(
        session: AsyncSession,
        plan: MigrationPlan,
        version_number: int,
    ) -> MigrationPlan:
        """Restores a migration plan to a historical AST version."""
        from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
            MigrationPlanValidator,
        )

        await MigrationPlanService._check_active_execution_lock(session, plan.id)

        target_version = await MigrationPlanService.get_plan_version(
            session, plan.id, version_number
        )
        if not target_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} not found for migration plan '{plan.id}'.",
            )

        # Update live plan with historical AST data
        plan.plan_data = target_version.plan_data

        if plan.agent:
            snapshots, alias_map = await MigrationPlanService._fetch_latest_snapshots_for_agent(
                session, plan.agent
            )
            val_res = MigrationPlanValidator.validate(target_version.plan_data, snapshots, alias_map)
            val_dict = val_res.model_dump(mode="json")
            plan.is_valid = val_res.is_valid
            plan.validation_errors = val_dict
            plan.status = "edited" if val_res.is_valid else "invalid_edits"
        else:
            plan.status = "edited"

        # Compute next version number for recording the restoration event
        stmt_ver = select(func.coalesce(func.max(MigrationPlanVersion.version_number), 0)).where(
            MigrationPlanVersion.migration_plan_id == plan.id
        )
        max_ver = (await session.execute(stmt_ver)).scalar_one()
        next_ver = max_ver + 1

        restored_snapshot = MigrationPlanVersion(
            migration_plan_id=plan.id,
            version_number=next_ver,
            edit_type="version_restored",
            user_feedback=f"Restored from version {version_number}",
            plan_data=target_version.plan_data,
            is_valid=plan.is_valid,
            confidence_score=target_version.confidence_score,
            validation_errors=plan.validation_errors,
        )
        session.add(restored_snapshot)

        await session.commit()
        return plan

    @staticmethod
    async def validate_plan_by_id(
        session: AsyncSession,
        plan: MigrationPlan,
    ) -> Dict[str, Any]:
        """Runs instant feasibility check on a plan."""
        from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
            MigrationPlanValidator,
        )

        if not plan.agent:
            return {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "explanation": "No agent attached for snapshot validation.",
            }

        snapshots, alias_map = await MigrationPlanService._fetch_latest_snapshots_for_agent(
            session, plan.agent
        )
        val_res = MigrationPlanValidator.validate(plan.plan_data, snapshots, alias_map)
        return val_res.model_dump(mode="json")

    @staticmethod
    async def approve_plan(
        session: AsyncSession,
        plan: MigrationPlan,
    ) -> MigrationPlan:
        """Approves a plan for execution."""
        from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
            MigrationPlanValidator,
        )

        if plan.agent:
            snapshots, alias_map = await MigrationPlanService._fetch_latest_snapshots_for_agent(
                session, plan.agent
            )
            val_res = MigrationPlanValidator.validate(plan.plan_data, snapshots, alias_map)
            if not val_res.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cannot approve invalid plan: {val_res.explanation}",
                )

        plan.status = "approved"
        await session.commit()

        if plan.agent_id:
            await manager.broadcast_to_agent(
                agent_id=str(plan.agent_id),
                message={
                    "event_type": "PLAN_GENERATED",
                    "data": {
                        "plan_id": str(plan.id),
                        "agent_id": str(plan.agent_id),
                        "status": "approved",
                    },
                },
            )

        return plan


def settings_llm_provider() -> str:
    from app.core.config import settings
    return settings.LLM_PROVIDER


def settings_llm_model() -> str:
    from app.core.config import settings
    return settings.LLM_MODEL
