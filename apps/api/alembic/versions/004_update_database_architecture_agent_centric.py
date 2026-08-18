"""update_database_architecture_agent_centric

Revision ID: 004_agent_centric_arch
Revises: 003_add_google_auth
Create Date: 2026-08-13
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_agent_centric_arch"
down_revision: Union[str, None] = "003_add_google_auth_to_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # 1. Create data_sources table with role column and unique constraint on (agent_id, identifier)
    op.create_table(
        "data_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="source"),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "identifier", name="uq_data_sources_agent_identifier"),
    )
    op.create_index(op.f("ix_data_sources_agent_id"), "data_sources", ["agent_id"], unique=False)

    # 2. Update metadata_snapshots: add data_source_id (NOT NULL), created_at, updated_at; remove connection_id
    op.add_column("metadata_snapshots", sa.Column("data_source_id", sa.UUID(), nullable=False))
    op.add_column("metadata_snapshots", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column("metadata_snapshots", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index(op.f("ix_metadata_snapshots_data_source_id"), "metadata_snapshots", ["data_source_id"], unique=False)
    op.create_foreign_key(
        "fk_metadata_snapshots_data_source_id",
        "metadata_snapshots",
        "data_sources",
        ["data_source_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop connection_id FK and column
    op.drop_constraint("metadata_snapshots_connection_id_fkey", "metadata_snapshots", type_="foreignkey", if_exists=True)
    op.drop_index("ix_metadata_snapshots_connection_id", table_name="metadata_snapshots", if_exists=True)
    op.drop_column("metadata_snapshots", "connection_id")

    # 3. Update migration_plans: add agent_id (nullable, SET NULL), plan_data (NOT NULL), target_config; remove obsolete connection fields
    op.add_column("migration_plans", sa.Column("agent_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_migration_plans_agent_id"), "migration_plans", ["agent_id"], unique=False)
    op.create_foreign_key(
        "fk_migration_plans_agent_id",
        "migration_plans",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("migration_plans", sa.Column("plan_data", json_type, nullable=False))
    op.add_column("migration_plans", sa.Column("target_config", json_type, nullable=True))

    op.alter_column("migration_plans", "ai_model", existing_type=sa.String(length=100), nullable=True)
    op.alter_column("migration_plans", "prompt_version", existing_type=sa.String(length=50), nullable=True)

    # Drop connection-related columns from migration_plans
    op.drop_constraint("migration_plans_target_connection_id_fkey", "migration_plans", type_="foreignkey", if_exists=True)
    op.drop_index("ix_migration_plans_target_connection_id", table_name="migration_plans", if_exists=True)
    op.drop_column("migration_plans", "target_connection_id")
    op.drop_column("migration_plans", "source_connection_ids")
    op.drop_column("migration_plans", "source_snapshot_ids")
    op.drop_column("migration_plans", "plan")

    # 4. Create migration_plan_snapshots join table with reverse index
    op.create_table(
        "migration_plan_snapshots",
        sa.Column("migration_plan_id", sa.UUID(), nullable=False),
        sa.Column("metadata_snapshot_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["metadata_snapshot_id"], ["metadata_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["migration_plan_id"], ["migration_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("migration_plan_id", "metadata_snapshot_id"),
    )
    op.create_index(
        op.f("ix_migration_plan_snapshots_snapshot_id"),
        "migration_plan_snapshots",
        ["metadata_snapshot_id"],
        unique=False,
    )

    # 5. Drop obsolete connections table
    op.drop_index("ix_connections_agent_id", table_name="connections", if_exists=True)
    op.drop_index("ix_connections_user_id", table_name="connections", if_exists=True)
    op.drop_table("connections")


def downgrade() -> None:
    # 1. Re-create connections table
    op.create_table(
        "connections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("database_name", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("credentials_encrypted", sa.String(), nullable=True),
        sa.Column("config", json_type, nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_connections_user_id", "connections", ["user_id"], unique=False)
    op.create_index("ix_connections_agent_id", "connections", ["agent_id"], unique=False)

    # 2. Drop migration_plan_snapshots
    op.drop_index(op.f("ix_migration_plan_snapshots_snapshot_id"), table_name="migration_plan_snapshots")
    op.drop_table("migration_plan_snapshots")

    # 3. Revert migration_plans
    op.add_column("migration_plans", sa.Column("plan", json_type, nullable=True))
    op.add_column("migration_plans", sa.Column("source_snapshot_ids", json_type, nullable=True))
    op.add_column("migration_plans", sa.Column("source_connection_ids", json_type, nullable=True))
    op.add_column("migration_plans", sa.Column("target_connection_id", sa.UUID(), nullable=True))
    op.create_index("ix_migration_plans_target_connection_id", "migration_plans", ["target_connection_id"], unique=False)
    op.create_foreign_key(
        "migration_plans_target_connection_id_fkey",
        "migration_plans",
        "connections",
        ["target_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("migration_plans", "target_config")
    op.drop_column("migration_plans", "plan_data")
    op.drop_constraint("fk_migration_plans_agent_id", "migration_plans", type_="foreignkey")
    op.drop_index("ix_migration_plans_agent_id", table_name="migration_plans")
    op.drop_column("migration_plans", "agent_id")

    # 4. Revert metadata_snapshots
    op.add_column("metadata_snapshots", sa.Column("connection_id", sa.UUID(), nullable=True))
    op.create_index("ix_metadata_snapshots_connection_id", "metadata_snapshots", ["connection_id"], unique=False)
    op.create_foreign_key(
        "metadata_snapshots_connection_id_fkey",
        "metadata_snapshots",
        "connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("fk_metadata_snapshots_data_source_id", "metadata_snapshots", type_="foreignkey")
    op.drop_index("ix_metadata_snapshots_data_source_id", table_name="metadata_snapshots")
    op.drop_column("metadata_snapshots", "updated_at")
    op.drop_column("metadata_snapshots", "created_at")
    op.drop_column("metadata_snapshots", "data_source_id")

    # 5. Drop data_sources
    op.drop_index("ix_data_sources_agent_id", table_name="data_sources")
    op.drop_constraint("uq_data_sources_agent_identifier", "data_sources", type_="unique")
    op.drop_table("data_sources")
