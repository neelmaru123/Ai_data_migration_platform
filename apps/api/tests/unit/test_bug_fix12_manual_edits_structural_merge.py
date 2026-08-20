"""
Unit test for Fix 12: process_manual_edits_node structural merge.
Verifies that partial manual edits payloads touching 1 table do not wipe out unedited tables or columns.
"""

import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3].parent
API_DIR = REPO_ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.modules.migration_plans.migration_plans_engine.migration_plans_graph import process_manual_edits_node


def test_process_manual_edits_preserves_unedited_tables_and_columns():
    """
    Submits a manual_edits payload modifying 1 column in table_1,
    and asserts table_2 and all other columns in table_1 remain intact.
    """
    initial_ast = {
        "target_database_type": "postgresql",
        "table_mappings": [
            {
                "target_table_name": "table_1",
                "transformation_type": "direct_copy",
                "column_mappings": [
                    {"target_column_name": "id", "transformation_type": "type_cast"},
                    {"target_column_name": "email", "transformation_type": "direct_copy"},
                ],
            },
            {
                "target_table_name": "table_2",
                "transformation_type": "direct_copy",
                "column_mappings": [
                    {"target_column_name": "order_id", "transformation_type": "direct_copy"},
                ],
            },
        ],
    }

    # Partial manual edits touching ONLY email column in table_1
    partial_manual_edits = {
        "table_mappings": [
            {
                "target_table_name": "table_1",
                "column_mappings": [
                    {"target_column_name": "email", "explanation": "Updated via UI"},
                ],
            }
        ]
    }

    state = {
        "current_ast": initial_ast,
        "manual_edits": partial_manual_edits,
    }

    res = process_manual_edits_node(state)
    updated_ast = res["current_ast"]

    # 1. Assert table_2 is still present and unchanged
    table_names = [t["target_table_name"] for t in updated_ast["table_mappings"]]
    assert "table_1" in table_names
    assert "table_2" in table_names

    # 2. Assert table_1 still contains both 'id' and 'email' columns
    tbl1 = next(t for t in updated_ast["table_mappings"] if t["target_table_name"] == "table_1")
    col_names = [c["target_column_name"] for c in tbl1["column_mappings"]]
    assert "id" in col_names
    assert "email" in col_names

    # 3. Assert explanation for email was updated
    email_col = next(c for c in tbl1["column_mappings"] if c["target_column_name"] == "email")
    assert email_col["explanation"] == "Updated via UI"
    assert email_col["transformation_type"] == "direct_copy"
