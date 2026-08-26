"""
Unit Tests for Alembic Migration Chain
Verifies all migrations form a continuous, non-branching chain from 001 to 005.
"""

import os
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest


def test_alembic_migration_chain_is_linear_and_valid():
    """Verify that Alembic migrations form a single continuous linear chain with no split heads."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    api_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    ini_path = os.path.join(api_root, "alembic.ini")

    config = Config(ini_path)
    config.set_main_option("script_location", os.path.join(api_root, "alembic"))
    script = ScriptDirectory.from_config(config)

    # 1. Verify single head
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 migration head, found {heads}"
    assert heads[0] == "007_ai_diagnosis_migration_jobs"

    # 2. Verify complete linear chain from head to base
    revisions = list(script.walk_revisions(base="base", head="heads"))
    rev_ids = [r.revision for r in revisions]

    expected_order = [
        "007_ai_diagnosis_migration_jobs",
        "006_feasibility_and_langgraph",
        "005_agent_tokens_and_diagnostics",
        "004_agent_centric_arch",
        "003_add_google_auth_to_users",
        "002_add_agents",
        "001_initial_schema",
    ]
    assert rev_ids == expected_order, f"Migration chain mismatch: {rev_ids} vs {expected_order}"

    # 3. Verify down_revision pointers are exact
    rev_map = {r.revision: r.down_revision for r in revisions}
    assert rev_map["007_ai_diagnosis_migration_jobs"] == "006_feasibility_and_langgraph"
    assert rev_map["006_feasibility_and_langgraph"] == "005_agent_tokens_and_diagnostics"
    assert rev_map["005_agent_tokens_and_diagnostics"] == "004_agent_centric_arch"
    assert rev_map["004_agent_centric_arch"] == "003_add_google_auth_to_users"
    assert rev_map["003_add_google_auth_to_users"] == "002_add_agents"
    assert rev_map["002_add_agents"] == "001_initial_schema"
    assert rev_map["001_initial_schema"] is None
