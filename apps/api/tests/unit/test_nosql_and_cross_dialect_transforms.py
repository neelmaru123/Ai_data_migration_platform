"""
Unit Test Suite for NoSQL to SQL and Cross-Dialect Transformations
Verifies:
1. json_flatten: Extracting nested document fields (address.city -> address_city)
2. json_stringify: Serializing dict/list objects to JSON strings
3. array_to_csv: Converting list columns to CSV strings ("tag1,tag2")
4. array_to_json: Converting list columns to JSON array strings ('["tag1", "tag2"]')
5. nosql_field_promote: Promoting MongoDB document keys to dedicated SQL columns
"""

import sys
import os
import pytest
import polars as pl

# Ensure agent module is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../agent")))
from execution_engine import ASTTransformer


def test_nosql_json_flatten_and_promote():
    """Test extracting nested document keys and promoting NoSQL fields."""
    raw_docs = [
        {
            "_id": "64f1a2b3c4d5e6f7a8b9c0d1",
            "email": "alice@company.com",
            "profile": {"bio": "Engineer", "location": {"city": "New York", "country": "USA"}},
            "tags": ["python", "sql", "ai"],
        },
        {
            "_id": "64f1a2b3c4d5e6f7a8b9c0d2",
            "email": "bob@company.com",
            "profile": {"bio": "Designer", "location": {"city": "San Francisco", "country": "USA"}},
            "tags": ["design", "ui"],
        },
    ]
    df_raw = pl.DataFrame(raw_docs)

    mappings = [
        {"target_column_name": "user_id", "transformation_type": "type_cast", "target_data_type": "uuid", "source_columns": [{"column_name": "_id"}]},
        {"target_column_name": "user_email", "transformation_type": "nosql_field_promote", "source_columns": [{"column_name": "email"}]},
        {"target_column_name": "city", "transformation_type": "json_flatten", "source_columns": [{"column_name": "profile.location.city"}]},
        {"target_column_name": "tags_csv", "transformation_type": "array_to_csv", "source_columns": [{"column_name": "tags"}]},
        {"target_column_name": "tags_json", "transformation_type": "array_to_json", "source_columns": [{"column_name": "tags"}]},
        {"target_column_name": "raw_profile_json", "transformation_type": "json_stringify", "source_columns": [{"column_name": "profile"}]},
    ]

    df_trans, errors = ASTTransformer.transform_chunk(df_raw, mappings)
    assert errors == 0
    assert len(df_trans) == 2
    assert "user_id" in df_trans.columns
    assert "user_email" in df_trans.columns
    assert "city" in df_trans.columns
    assert "tags_csv" in df_trans.columns
    assert "tags_json" in df_trans.columns
    assert "raw_profile_json" in df_trans.columns

    # Assert row 1 values
    row1 = df_trans.to_dicts()[0]
    assert row1["user_email"] == "alice@company.com"
    assert row1["city"] == "New York"
    assert row1["tags_csv"] == "python,sql,ai"
    assert "python" in row1["tags_json"]
    assert "Engineer" in row1["raw_profile_json"]


def test_cross_dialect_array_and_json_conversions():
    """Test Postgres array and JSONB cross-dialect conversions for MySQL/SQLite targets."""
    pg_rows = [
        {"id": 1, "categories": ["tech", "cloud"], "metadata_b_json": {"version": 1, "tier": "gold"}},
        {"id": 2, "categories": ["finance"], "metadata_b_json": {"version": 2, "tier": "silver"}},
    ]
    df_pg = pl.DataFrame(pg_rows)

    mappings = [
        {"target_column_name": "id", "transformation_type": "direct_copy", "source_columns": [{"column_name": "id"}]},
        {"target_column_name": "category_csv", "transformation_type": "array_to_csv", "source_columns": [{"column_name": "categories"}]},
        {"target_column_name": "category_json", "transformation_type": "array_to_json", "source_columns": [{"column_name": "categories"}]},
        {"target_column_name": "meta_str", "transformation_type": "json_stringify", "source_columns": [{"column_name": "metadata_b_json"}]},
    ]

    df_trans, errors = ASTTransformer.transform_chunk(df_pg, mappings)
    assert errors == 0
    assert df_trans.to_dicts()[0]["category_csv"] == "tech,cloud"
    assert "tech" in df_trans.to_dicts()[0]["category_json"]
    assert "gold" in df_trans.to_dicts()[0]["meta_str"]
