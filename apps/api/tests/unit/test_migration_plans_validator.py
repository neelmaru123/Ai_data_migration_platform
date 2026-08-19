"""
Unit tests for MigrationPlanValidator
"""

import pytest
import app.main  # noqa: F401
from app.modules.metadata.metadata_models import (
    MetadataColumn,
    MetadataSchema,
    MetadataSnapshot,
    MetadataTable,
)
from app.modules.migration_plans.migration_plans_engine.migration_plans_validator import (
    MigrationPlanValidator,
)


@pytest.fixture
def dummy_snapshots():
    """Builds dummy MetadataSnapshot with table 'users' containing columns 'id', 'email', 'name'."""
    col_id = MetadataColumn(column_name="id", data_type="integer", is_primary_key=True, ordinal_position=1)
    col_email = MetadataColumn(column_name="email", data_type="varchar(255)", is_unique=True, ordinal_position=2)
    col_name = MetadataColumn(column_name="name", data_type="varchar(255)", ordinal_position=3)

    tbl_users = MetadataTable(table_name="users", table_type="BASE TABLE", columns=[col_id, col_email, col_name])
    schema_public = MetadataSchema(schema_name="public", tables=[tbl_users])

    snapshot = MetadataSnapshot(
        id="00000000-0000-0000-0000-000000000001",
        data_source_id="00000000-0000-0000-0000-000000000002",
        database_name="db_1",
        total_tables=1,
        total_columns=3,
        schemas=[schema_public],
    )
    return [snapshot]


def test_validator_valid_plan(dummy_snapshots):
    """Test 1: Valid AST blueprint returns is_valid=True with 0 errors."""
    valid_ast = {
        "target_database_type": "postgresql",
        "ai_explanation": "Valid test blueprint",
        "confidence_score": 0.95,
        "warnings": [],
        "table_mappings": [
            {
                "target_table_name": "target_users",
                "transformation_type": "direct_copy",
                "ai_reasoning": "1:1 table copy",
                "confidence_score": 0.95,
                "source_tables": [
                    {
                        "identifier": "source_db_1",
                        "schema_name": "public",
                        "table_name": "users",
                        "join_type": "primary",
                    }
                ],
                "column_mappings": [
                    {
                        "target_column_name": "id",
                        "target_data_type": "integer",
                        "transformation_type": "direct_copy",
                        "ui_badge_type": "direct_copy",
                        "explanation": "Copy id",
                        "source_columns": [
                            {
                                "identifier": "source_db_1",
                                "schema_name": "public",
                                "table_name": "users",
                                "column_name": "id",
                            }
                        ],
                    },
                    {
                        "target_column_name": "email",
                        "target_data_type": "varchar(255)",
                        "transformation_type": "direct_copy",
                        "ui_badge_type": "direct_copy",
                        "explanation": "Copy email",
                        "source_columns": [
                            {
                                "identifier": "source_db_1",
                                "schema_name": "public",
                                "table_name": "users",
                                "column_name": "email",
                            }
                        ],
                    },
                ],
            }
        ],
    }

    alias_map = {"00000000-0000-0000-0000-000000000002": "source_db_1"}
    res = MigrationPlanValidator.validate(valid_ast, dummy_snapshots, alias_map)

    assert res.is_valid is True
    assert len(errors := res.errors) == 0


def test_validator_missing_column(dummy_snapshots):
    """Test 2: Invalid AST with non-existent source column returns is_valid=False."""
    invalid_ast = {
        "target_database_type": "postgresql",
        "ai_explanation": "Invalid test blueprint",
        "confidence_score": 0.95,
        "warnings": [],
        "table_mappings": [
            {
                "target_table_name": "target_users",
                "transformation_type": "direct_copy",
                "ai_reasoning": "1:1 table copy",
                "confidence_score": 0.95,
                "source_tables": [
                    {
                        "identifier": "source_db_1",
                        "schema_name": "public",
                        "table_name": "users",
                        "join_type": "primary",
                    }
                ],
                "column_mappings": [
                    {
                        "target_column_name": "non_existent",
                        "target_data_type": "varchar(255)",
                        "transformation_type": "direct_copy",
                        "ui_badge_type": "direct_copy",
                        "explanation": "Copy missing col",
                        "source_columns": [
                            {
                                "identifier": "source_db_1",
                                "schema_name": "public",
                                "table_name": "users",
                                "column_name": "non_existent_column_123",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    alias_map = {"00000000-0000-0000-0000-000000000002": "source_db_1"}
    res = MigrationPlanValidator.validate(invalid_ast, dummy_snapshots, alias_map)

    assert res.is_valid is False
    assert len(res.errors) > 0
    assert "non_existent_column_123" in res.errors[0]
