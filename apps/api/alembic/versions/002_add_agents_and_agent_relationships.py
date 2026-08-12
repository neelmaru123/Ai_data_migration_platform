"""Add agents table and agent relationships to connections and migration_jobs

Revision ID: 002_add_agents
Revises: 001_initial_schema
Create Date: 2026-08-12 14:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_add_agents"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create agents table
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("agent_identifier", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="offline"),
        sa.Column("version", sa.String(length=50), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agents_user_id", "agents", ["user_id"])
    op.create_index("ix_agents_agent_identifier", "agents", ["agent_identifier"], unique=True)

    # 2. Add agent_id FK to connections
    op.add_column(
        "connections",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_connections_agent_id", "connections", ["agent_id"])

    # 3. Add agent_id FK to migration_jobs
    op.add_column(
        "migration_jobs",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_migration_jobs_agent_id", "migration_jobs", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_migration_jobs_agent_id", table_name="migration_jobs")
    op.drop_column("migration_jobs", "agent_id")

    op.drop_index("ix_connections_agent_id", table_name="connections")
    op.drop_column("connections", "agent_id")

    op.drop_index("ix_agents_agent_identifier", table_name="agents")
    op.drop_index("ix_agents_user_id", table_name="agents")
    op.drop_table("agents")
