"""
Unit test for Fix 9: Residual/unmapped field capture at execution time.
Verifies that fields missing from AST column mappings are captured into extra_attributes JSON column without data loss.
"""

import json
import sys
from pathlib import Path
import polars as pl
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3].parent
API_DIR = REPO_ROOT / "apps" / "api"
AGENT_DIR = REPO_ROOT / "apps" / "agent"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from execution_engine import ASTTransformer


def test_residual_field_capture_for_unmapped_document_fields():
    """
    Verifies that transform_chunk captures unmapped fields (field_c, nested_doc)
    into an extra_attributes JSON column while preserving mapped fields (field_a, field_b).
    """
    input_df = pl.DataFrame({
        "field_a": ["Alice"],
        "field_b": ["user@example.com"],
        "unforeseen_field_c": [12345],
        "nested_doc": [{"k1": "v1", "k2": 99}],
    })

    column_mappings = [
        {
            "target_column_name": "name",
            "transformation_type": "direct_copy",
            "source_columns": [{"identifier": "mongo1", "column_name": "field_a"}],
        },
        {
            "target_column_name": "email",
            "transformation_type": "direct_copy",
            "source_columns": [{"identifier": "mongo1", "column_name": "field_b"}],
        },
    ]

    transformed_df, errors = ASTTransformer.transform_chunk(input_df, column_mappings)
    assert errors == 0
    assert "name" in transformed_df.columns
    assert "email" in transformed_df.columns
    assert "extra_attributes" in transformed_df.columns

    extra_val_str = transformed_df["extra_attributes"][0]
    extra_json = json.loads(extra_val_str)

    assert extra_json.get("unforeseen_field_c") == 12345
    assert extra_json.get("nested_doc") == {"k1": "v1", "k2": 99}
