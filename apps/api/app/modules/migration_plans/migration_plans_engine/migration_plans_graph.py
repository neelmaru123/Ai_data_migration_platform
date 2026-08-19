"""
LangGraph Stateful Agent Architecture Engine

Implements the 9-node StateGraph for AI migration plan generation, deterministic feasibility checking,
auto-correction loops, human-in-the-loop (HITL) approval, and plan persistence.
"""

import logging
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.modules.migration_plans.migration_plans_engine.migration_plans_llm import (
    MetadataContextSerializer,
    llm_plan_generator,
)
from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
    MigrationPlanValidator,
    PlanValidationResult,
)

logger = logging.getLogger(__name__)


class MigrationPlanState(TypedDict):
    """Central LangGraph State Schema passed across all graph nodes."""
    agent_id: str
    user_id: str
    target_db_type: str
    custom_instructions: Optional[str]
    context_yaml: str
    snapshots: List[Any]
    alias_map: Dict[str, str]
    current_ast: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    user_feedback: Optional[str]
    manual_edits: Optional[Dict[str, Any]]
    attempt_count: int
    is_approved: bool
    feasibility_explanation: Optional[str]
    persisted_plan_id: Optional[str]


# ============================================================================
# Node Functions
# ============================================================================

def serialize_context_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 1: Serializes metadata snapshots into Zero-Raw-Data YAML context."""
    logger.info(f"[LangGraph Node 1] Serializing context for agent '{state.get('agent_id')}'...")
    context_yaml = MetadataContextSerializer.serialize(
        snapshots=state.get("snapshots", []),
        source_aliases=state.get("alias_map", {}),
        target_db_type=state.get("target_db_type", "postgresql"),
        custom_instructions=state.get("custom_instructions"),
    )
    return {"context_yaml": context_yaml}


def generate_plan_ast_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 2: Generates initial or refined TransformationPlanAST using Gemini."""
    logger.info(f"[LangGraph Node 2] Generating AST (user_feedback={bool(state.get('user_feedback'))})...")
    context_yaml = state["context_yaml"]
    target_db_type = state.get("target_db_type", "postgresql")
    user_feedback = state.get("user_feedback")
    current_ast = state.get("current_ast")

    if user_feedback and current_ast:
        ast_obj = llm_plan_generator.refine(
            context_str=context_yaml,
            current_ast_dict=current_ast,
            user_feedback=user_feedback,
        )
    else:
        ast_obj = llm_plan_generator.generate(
            context_str=context_yaml,
            target_db_type=target_db_type,
        )

    ast_dict = ast_obj.model_dump(mode="json")
    return {"current_ast": ast_dict, "user_feedback": None}


def validate_feasibility_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 3: Deterministic feasibility validation against database schemas."""
    logger.info("[LangGraph Node 3] Validating AST feasibility...")
    ast_dict = state.get("current_ast") or {}
    snapshots = state.get("snapshots") or []
    alias_map = state.get("alias_map") or {}

    val_res: PlanValidationResult = MigrationPlanValidator.validate(
        plan_ast_data=ast_dict,
        snapshots=snapshots,
        alias_map=alias_map,
    )
    val_dict = val_res.model_dump(mode="json")
    logger.info(f"[LangGraph Node 3] Validation result: is_valid={val_res.is_valid}, errors={len(val_res.errors)}")
    return {"validation_result": val_dict}


def auto_correct_ast_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 4: Auto-correction loop feeding validation errors back to Gemini."""
    attempt_count = state.get("attempt_count", 0) + 1
    val_res = state.get("validation_result") or {}
    errors = val_res.get("errors", [])
    logger.info(f"[LangGraph Node 4] Auto-correct attempt {attempt_count}/3 for errors: {errors}")

    context_yaml = state["context_yaml"]
    current_ast = state.get("current_ast") or {}

    try:
        ast_obj = llm_plan_generator.refine(
            context_str=context_yaml,
            current_ast_dict=current_ast,
            validation_errors=errors,
        )
        ast_dict = ast_obj.model_dump(mode="json")
        return {"current_ast": ast_dict, "attempt_count": attempt_count}
    except Exception as exc:
        logger.error(f"[LangGraph Node 4] Auto-correction LLM call failed on attempt {attempt_count}: {exc}")
        return {"attempt_count": attempt_count}


def human_approval_interrupt_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 5: Human-in-the-Loop pause point using LangGraph interrupt()."""
    logger.info("[LangGraph Node 5] Reached Human Review State. Interrupting execution for UI interaction...")
    human_input = interrupt({
        "status": "awaiting_approval",
        "current_ast": state.get("current_ast"),
        "validation_result": state.get("validation_result"),
    })

    if isinstance(human_input, dict):
        return {
            "is_approved": human_input.get("is_approved", False),
            "user_feedback": human_input.get("user_feedback"),
            "manual_edits": human_input.get("manual_edits"),
        }
    return {}


def process_user_feedback_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 6: Processes prompt feedback and clears manual edits before re-generating AST."""
    logger.info(f"[LangGraph Node 6] Processing user feedback: '{state.get('user_feedback')}'")
    return {"manual_edits": None}


def process_manual_edits_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 7: Applies direct structural UI edits to current_ast and resets attempt_count."""
    logger.info("[LangGraph Node 7] Applying manual UI edits to AST blueprint...")
    manual_edits = state.get("manual_edits") or {}
    current_ast = state.get("current_ast") or {}

    # Merge top-level or table-level edits into AST
    updated_ast = {**current_ast, **manual_edits}
    return {"current_ast": updated_ast, "manual_edits": None, "attempt_count": 0}


def explanation_generator_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 8: Builds feasibility failure report when auto-correction retries are exhausted."""
    val_res = state.get("validation_result") or {}
    errors = val_res.get("errors", [])
    explanation = (
        f"Migration impossible after 3 auto-correction attempts. Blocking errors: "
        + "; ".join(errors)
    )
    logger.warning(f"[LangGraph Node 8] Feasibility failure: {explanation}")
    return {"feasibility_explanation": explanation}


def finalize_and_persist_node(state: MigrationPlanState) -> Dict[str, Any]:
    """Node 9: Finalizes verified MigrationPlan signal node."""
    logger.info("[LangGraph Node 9] Finalizing and persisting verified MigrationPlan...")
    return {
        "is_approved": True,
        "persisted_plan_id": state.get("persisted_plan_id"),
    }


# ============================================================================
# Conditional Edge Router Functions
# ============================================================================

def check_validation_router(state: MigrationPlanState) -> str:
    """Router 1: Determines next node based on validation result and attempt count."""
    val_res = state.get("validation_result") or {}
    is_valid = val_res.get("is_valid", False)
    attempt_count = state.get("attempt_count", 0)

    if is_valid:
        return "human_approval_interrupt_node"
    if attempt_count < 3:
        return "auto_correct_ast_node"
    return "explanation_generator_node"


def human_feedback_router(state: MigrationPlanState) -> str:
    """Router 2: Determines next node based on human UI action."""
    if state.get("is_approved"):
        return "finalize_and_persist_node"
    if state.get("user_feedback"):
        return "process_user_feedback_node"
    if state.get("manual_edits"):
        return "process_manual_edits_node"
    logger.warning("[Router 2] No user action received; staying in human approval interrupt state.")
    return "human_approval_interrupt_node"


# ============================================================================
# LangGraph Workflow Construction
# ============================================================================

def build_migration_plan_graph():
    """Constructs and compiles the 9-node LangGraph StateGraph."""
    workflow = StateGraph(MigrationPlanState)

    # 1. Add all 9 Nodes
    workflow.add_node("serialize_context_node", serialize_context_node)
    workflow.add_node("generate_plan_ast_node", generate_plan_ast_node)
    workflow.add_node("validate_feasibility_node", validate_feasibility_node)
    workflow.add_node("auto_correct_ast_node", auto_correct_ast_node)
    workflow.add_node("human_approval_interrupt_node", human_approval_interrupt_node)
    workflow.add_node("process_user_feedback_node", process_user_feedback_node)
    workflow.add_node("process_manual_edits_node", process_manual_edits_node)
    workflow.add_node("explanation_generator_node", explanation_generator_node)
    workflow.add_node("finalize_and_persist_node", finalize_and_persist_node)

    # 2. Set Entry Point
    workflow.set_entry_point("serialize_context_node")

    # 3. Add Edges
    workflow.add_edge("serialize_context_node", "generate_plan_ast_node")
    workflow.add_edge("generate_plan_ast_node", "validate_feasibility_node")

    # 4. Add Conditional Edge Router 1 (Validation Check)
    workflow.add_conditional_edges(
        "validate_feasibility_node",
        check_validation_router,
        {
            "human_approval_interrupt_node": "human_approval_interrupt_node",
            "auto_correct_ast_node": "auto_correct_ast_node",
            "explanation_generator_node": "explanation_generator_node",
        },
    )

    workflow.add_edge("auto_correct_ast_node", "validate_feasibility_node")
    workflow.add_edge("explanation_generator_node", END)

    # 5. Add Conditional Edge Router 2 (Human Feedback Router)
    workflow.add_conditional_edges(
        "human_approval_interrupt_node",
        human_feedback_router,
        {
            "finalize_and_persist_node": "finalize_and_persist_node",
            "process_user_feedback_node": "process_user_feedback_node",
            "process_manual_edits_node": "process_manual_edits_node",
        },
    )

    workflow.add_edge("process_user_feedback_node", "generate_plan_ast_node")
    workflow.add_edge("process_manual_edits_node", "validate_feasibility_node")
    workflow.add_edge("finalize_and_persist_node", END)

    return workflow.compile()


# Singleton compiled graph instance
migration_plan_graph = build_migration_plan_graph()
