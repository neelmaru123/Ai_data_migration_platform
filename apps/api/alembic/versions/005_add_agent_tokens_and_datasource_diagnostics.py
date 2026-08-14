"""add_agent_tokens_and_datasource_diagnostics

Revision ID: 005_agent_tokens_and_diagnostics
Revises: 004_agent_centric_arch
Create Date: 2026-08-14
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "005_agent_tokens_and_diagnostics"
down_revision: Union[str, None] = "004_agent_centric_arch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update agents table
    # Add api_token_hash column (nullable first, backfill default if needed, then NOT NULL)
    op.add_column(
        "agents",
        sa.Column(
            "api_token_hash",
            sa.String(length=255),
            nullable=False,
            server_default=sa.text("md5(random()::text)"),
        ),
    )
    # Remove server_default so future inserts are handled by model/application
    op.alter_column("agents", "api_token_hash", server_default=None)

    op.create_index(
        op.f("ix_agents_api_token_hash"),
        "agents",
        ["api_token_hash"],
        unique=True,
    )

    # Change agent_identifier from global unique index to per-user unique constraint
    op.drop_index("ix_agents_agent_identifier", table_name="agents", if_exists=True)
    op.create_index(
        op.f("ix_agents_agent_identifier"),
        "agents",
        ["agent_identifier"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_agents_user_identifier",
        "agents",
        ["user_id", "agent_identifier"],
    )

    # 2. Update data_sources table
    # Add status, last_error, and last_checked_at columns
    op.add_column(
        "data_sources",
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="untested",
        ),
    )
    # Remove server default from status so application manages default
    op.alter_column("data_sources", "status", server_default=None)

    op.add_column(
        "data_sources",
        sa.Column("last_error", sa.String(), nullable=True),
    )
    op.add_column(
        "data_sources",
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # 1. Revert data_sources table changes
    op.drop_column("data_sources", "last_checked_at")
    op.drop_column("data_sources", "last_error")
    op.drop_column("data_sources", "status")

    # 2. Revert agents table changes
    op.drop_constraint("uq_agents_user_identifier", "agents", type_="unique")
    op.drop_index(op.f("ix_agents_agent_identifier"), table_name="agents")
    op.create_index(
        "ix_agents_agent_identifier",
        "agents",
        ["agent_identifier"],
        unique=True,
    )
    op.drop_index(op.f("ix_agents_api_token_hash"), table_name="agents")
    op.drop_column("agents", "api_token_hash")
