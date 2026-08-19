"""
Unit tests for Phase 5 Code Audit Bug Fixes.
"""

import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.modules.migration_plans.migration_plans_engine.migration_plans_graph import (
    auto_correct_ast_node,
    finalize_and_persist_node,
    human_feedback_router,
)
from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
    MigrationPlanValidator,
)
from app.modules.migration_plans.migration_plans_routes import _to_plan_detail_response
from app.modules.execution.execution_services import ExecutionService
from app.modules.migration_plans.migration_plans_models import MigrationPlan


def test_bug2_human_feedback_router_fallback():
    """Bug #2: human_feedback_router should not fall through to finalize_and_persist_node."""
    state = {
        "is_approved": False,
        "user_feedback": None,
        "manual_edits": None,
    }
    next_node = human_feedback_router(state)
    assert next_node == "human_approval_interrupt_node"


def test_bug1_finalize_and_persist_node_response():
    """Bug #1: finalize_and_persist_node should preserve persisted_plan_id."""
    state = {"persisted_plan_id": "test-uuid-123"}
    res = finalize_and_persist_node(state)
    assert res["is_approved"] is True
    assert res["persisted_plan_id"] == "test-uuid-123"


def test_bug3_validator_stage_d_fk_check():
    """Bug #3: Validator Stage D should flag non-existent FK target tables in post-migration DDL."""
    ast_dict = {
        "target_database_type": "postgresql",
        "ai_explanation": "Test FK validation",
        "confidence_score": 0.9,
        "warnings": [],
        "table_mappings": [
            {
                "target_table_name": "users",
                "transformation_type": "direct_copy",
                "ai_reasoning": "Direct copy users",
                "confidence_score": 1.0,
                "source_tables": [{"identifier": "src_1", "table_name": "users"}],
                "column_mappings": [
                    {
                        "target_column_name": "id",
                        "transformation_type": "direct_copy",
                        "ui_badge_type": "direct_copy",
                        "source_columns": [{"identifier": "src_1", "table_name": "users", "column_name": "id"}],
                        "explanation": "Map id",
                    }
                ],
            }
        ],
        "pre_migration_ddl": [],
        "post_migration_ddl": [
            "ALTER TABLE users ADD CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES non_existent_orgs(id)"
        ],
    }

    mock_snapshot = MagicMock()
    mock_snapshot.id = uuid.uuid4()
    mock_snapshot.data_source_id = uuid.uuid4()
    mock_schema = MagicMock()
    mock_table = MagicMock()
    mock_table.table_name = "users"
    mock_col = MagicMock()
    mock_col.column_name = "id"
    mock_col.data_type = "integer"
    mock_table.columns = [mock_col]
    mock_schema.tables = [mock_table]
    mock_snapshot.schemas = [mock_schema]

    res = MigrationPlanValidator.validate(ast_dict, [mock_snapshot], alias_map={str(mock_snapshot.data_source_id): "src_1"})
    assert res.is_valid is False
    assert any("non_existent_orgs" in err for err in res.errors)


@pytest.mark.asyncio
async def test_bug5_execution_guard_status_check():
    """Bug #5: ExecutionService should block jobs if plan.status != 'completed'."""
    from unittest.mock import AsyncMock
    session = AsyncMock()
    plan = MigrationPlan(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="draft",  # Unapproved status
        is_valid=True,
    )
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = plan
    session.execute.return_value = mock_exec

    with pytest.raises(HTTPException) as exc_info:
        await ExecutionService.create_execution_job(session, plan.user_id, plan.id)

    assert exc_info.value.status_code == 422
    assert "Cannot execute unapproved migration plan" in exc_info.value.detail


def test_bug4_plan_detail_response_warnings():
    """Bug #4: _to_plan_detail_response should populate validation_warnings."""
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.agent_id = uuid.uuid4()
    plan.status = "draft"
    plan.ai_model = "gemini"
    plan.confidence_score = 0.9
    plan.is_valid = True
    plan.validation_errors = {"warnings": ["Casting varchar to int"], "errors": []}
    plan.created_at = "2026-08-18"
    plan.updated_at = "2026-08-18"
    plan.plan_data = {}
    plan.target_config = {}
    plan.prompt_version = "v1.0.0"

    resp = _to_plan_detail_response(plan)
    assert resp.validation_warnings == ["Casting varchar to int"]


def test_bug6_auto_correct_ast_node_exception_handling():
    """Bug #6: auto_correct_ast_node should catch LLM exceptions without crashing."""
    state = {
        "attempt_count": 1,
        "context_yaml": "test context",
        "current_ast": {"test": 1},
        "validation_result": {"errors": ["error 1"]},
    }
    with patch("app.modules.migration_plans.migration_plans_engine.migration_plans_graph.llm_plan_generator.refine", side_effect=Exception("LLM Timeout")):
        res = auto_correct_ast_node(state)
        assert res["attempt_count"] == 2
        assert "current_ast" not in res
