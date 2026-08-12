"""Initial Control Plane Database Schema Migration

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-11 13:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. connections
    op.create_table(
        "connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("database_name", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("credentials_encrypted", sa.String(), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_connections_user_id", "connections", ["user_id"])

    # 3. metadata_snapshots
    op.create_table(
        "metadata_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("database_name", sa.String(length=255), nullable=False),
        sa.Column("database_version", sa.String(length=255), nullable=True),
        sa.Column("total_tables", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_columns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rows", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="completed"),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_metadata_snapshots_connection_id", "metadata_snapshots", ["connection_id"])

    # 4. metadata_schemas
    op.create_table(
        "metadata_schemas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("snapshot_id", "schema_name", name="uq_metadata_schemas_snapshot_schema"),
    )
    op.create_index("ix_metadata_schemas_snapshot_id", "metadata_schemas", ["snapshot_id"])

    # 5. metadata_tables
    op.create_table(
        "metadata_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("schema_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_schemas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_name", sa.String(length=255), nullable=False),
        sa.Column("table_type", sa.String(length=50), nullable=False, server_default="table"),
        sa.Column("row_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("schema_id", "table_name", name="uq_metadata_tables_schema_table"),
    )
    op.create_index("ix_metadata_tables_schema_id", "metadata_tables", ["schema_id"])

    # 6. metadata_columns
    op.create_table(
        "metadata_columns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_name", sa.String(length=255), nullable=False),
        sa.Column("ordinal_position", sa.Integer(), nullable=False),
        sa.Column("data_type", sa.String(length=100), nullable=False),
        sa.Column("native_data_type", sa.String(length=100), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_primary_key", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_unique", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("default_value", sa.String(), nullable=True),
        sa.Column("max_length", sa.Integer(), nullable=True),
        sa.Column("numeric_precision", sa.Integer(), nullable=True),
        sa.Column("numeric_scale", sa.Integer(), nullable=True),
        sa.Column("null_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("distinct_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("statistics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sample_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("table_id", "column_name", name="uq_metadata_columns_table_column"),
    )
    op.create_index("ix_metadata_columns_table_id", "metadata_columns", ["table_id"])

    # 7. metadata_constraints
    op.create_table(
        "metadata_constraints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("constraint_name", sa.String(length=255), nullable=False),
        sa.Column("constraint_type", sa.String(length=50), nullable=False),
        sa.Column("definition", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_metadata_constraints_table_id", "metadata_constraints", ["table_id"])

    # 8. metadata_relationships
    op.create_table(
        "metadata_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_column_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_columns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_column_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metadata_columns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_metadata_relationships_snapshot_id", "metadata_relationships", ["snapshot_id"])
    op.create_index("ix_metadata_relationships_source_table_id", "metadata_relationships", ["source_table_id"])
    op.create_index("ix_metadata_relationships_target_table_id", "metadata_relationships", ["target_table_id"])

    # 9. migration_plans
    op.create_table(
        "migration_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_connection_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_snapshot_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ai_model", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_migration_plans_user_id", "migration_plans", ["user_id"])
    op.create_index("ix_migration_plans_target_connection_id", "migration_plans", ["target_connection_id"])

    # 10. migration_jobs
    op.create_table(
        "migration_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("migration_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("migration_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_rows", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("successful_rows", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("current_table", sa.String(length=255), nullable=True),
        sa.Column("current_stage", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_migration_jobs_migration_plan_id", "migration_jobs", ["migration_plan_id"])
    op.create_index("ix_migration_jobs_status", "migration_jobs", ["status"])

    # 11. migration_errors
    op.create_table(
        "migration_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("migration_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("migration_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_table", sa.String(length=255), nullable=False),
        sa.Column("source_row_identifier", sa.String(length=255), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.String(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ai_suggestion", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="unresolved"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_migration_errors_migration_job_id", "migration_errors", ["migration_job_id"])


def downgrade() -> None:
    op.drop_table("migration_errors")
    op.drop_table("migration_jobs")
    op.drop_table("migration_plans")
    op.drop_table("metadata_relationships")
    op.drop_table("metadata_constraints")
    op.drop_table("metadata_columns")
    op.drop_table("metadata_tables")
    op.drop_table("metadata_schemas")
    op.drop_table("metadata_snapshots")
    op.drop_table("connections")
    op.drop_table("users")
