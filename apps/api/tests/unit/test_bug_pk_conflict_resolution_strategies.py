"""
Unit test for Fix 7: Implement missing PK conflict-resolution strategies.
Verifies keep_original, autoincrement_offset, prefix_id, uuid_v4_rekey, and validator warning.
"""

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
from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import MigrationPlanValidator
from app.modules.migration_plans.migration_plans_schemas import TransformationPlanAST, TableMappingSpec, ColumnMappingSpec, ConflictResolutionSpec, SourceTableRef, SourceColumnRef


def test_pk_strategy_keep_original():
    df = pl.DataFrame({"user_id": [101, 102]})
    column_mappings = [
        {
            "target_column_name": "id",
            "transformation_type": "type_cast",
            "is_primary_key": True,
            "primary_key_strategy": "keep_original",
            "target_data_type": "integer",
            "source_columns": [{"identifier": "src1", "column_name": "user_id"}],
        }
    ]
    transformed_df, errors = ASTTransformer.transform_chunk(df, column_mappings)
    assert errors == 0
    assert transformed_df["id"].to_list() == [101, 102]


def test_pk_strategy_autoincrement_offset():
    # Source 1 (source_index = 0 -> offset 0)
    df1 = pl.DataFrame({"id": [1, 2]})
    cm1 = [
        {
            "target_column_name": "id",
            "transformation_type": "type_cast",
            "is_primary_key": True,
            "primary_key_strategy": "autoincrement_offset",
            "target_data_type": "integer",
            "source_index": 0,
            "source_columns": [{"identifier": "source_db_1", "column_name": "id"}],
        }
    ]
    res1, _ = ASTTransformer.transform_chunk(df1, cm1)
    assert res1["id"].to_list() == [1, 2]

    # Source 2 (source_index = 1 -> offset 1,000,000,000)
    df2 = pl.DataFrame({"id": [1, 2]})
    cm2 = [
        {
            "target_column_name": "id",
            "transformation_type": "type_cast",
            "is_primary_key": True,
            "primary_key_strategy": "autoincrement_offset",
            "target_data_type": "integer",
            "source_index": 1,
            "source_columns": [{"identifier": "source_db_2", "column_name": "id"}],
        }
    ]
    res2, _ = ASTTransformer.transform_chunk(df2, cm2)
    assert res2["id"].to_list() == [1000000001, 1000000002]


def test_pk_strategy_prefix_id():
    df = pl.DataFrame({"id": [501, 502]})
    cm = [
        {
            "target_column_name": "id",
            "transformation_type": "type_cast",
            "is_primary_key": True,
            "primary_key_strategy": "prefix_id",
            "target_data_type": "varchar",
            "source_columns": [{"identifier": "source_db_1", "column_name": "id"}],
        }
    ]
    res, _ = ASTTransformer.transform_chunk(df, cm)
    assert res["id"].to_list() == ["source_db_1_501", "source_db_1_502"]


def test_pk_strategy_uuid_v4_rekey():
    df = pl.DataFrame({"id": [1, 2]})
    cm = [
        {
            "target_column_name": "id",
            "transformation_type": "type_cast",
            "is_primary_key": True,
            "primary_key_strategy": "uuid_v4_rekey",
            "target_data_type": "uuid",
            "source_columns": [{"identifier": "src1", "column_name": "id"}],
        }
    ]
    res, _ = ASTTransformer.transform_chunk(df, cm)
    uuids = res["id"].to_list()
    assert len(uuids) == 2
    assert len(uuids[0]) == 36
    assert uuids[0] != uuids[1]


def test_validator_warning_for_rekeyed_pk_with_multisource_merge():
    ast = TransformationPlanAST(
        target_database_type="postgresql",
        ai_explanation="Test plan explanation",
        table_mappings=[
            TableMappingSpec(
                target_table_name="users",
                transformation_type="merge",
                ai_reasoning="Merging users",
                confidence_score=0.9,
                conflict_resolution=ConflictResolutionSpec(
                    primary_key_strategy="uuid_v4_rekey",
                    deduplication_key="email",
                ),
                source_tables=[
                    SourceTableRef(identifier="src1", table_name="users"),
                    SourceTableRef(identifier="src2", table_name="customers"),
                ],
                column_mappings=[
                    ColumnMappingSpec(
                        target_column_name="id",
                        target_data_type="uuid",
                        is_primary_key=True,
                        transformation_type="type_cast",
                        ui_badge_type="type_cast",
                        explanation="PK type cast",
                        source_columns=[SourceColumnRef(identifier="src1", table_name="users", column_name="id")],
                    ),
                    ColumnMappingSpec(
                        target_column_name="email",
                        target_data_type="varchar",
                        transformation_type="direct_copy",
                        ui_badge_type="direct_copy",
                        explanation="Direct copy email",
                        source_columns=[SourceColumnRef(identifier="src1", table_name="users", column_name="email")],
                    ),
                ],
            )
        ],
    )

    result = MigrationPlanValidator.validate(ast, [])
    assert any("primary key strategy 'uuid_v4_rekey'" in w for w in result.warnings)
