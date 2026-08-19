"""add_feasibility_and_langgraph_to_plans

Revision ID: 006_feasibility_and_langgraph
Revises: 005_agent_tokens_and_diagnostics
Create Date: 2026-08-19
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_feasibility_and_langgraph"
down_revision: Union[str, None] = "005_agent_tokens_and_diagnostics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # Add is_valid, validation_errors, and langgraph_thread_id to migration_plans table
    op.add_column(
        "migration_plans",
        sa.Column(
            "is_valid",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("true"),
        ),
    )
    # Remove server_default so future inserts are managed by model default
    op.alter_column("migration_plans", "is_valid", server_default=None)

    op.add_column(
        "migration_plans",
        sa.Column("validation_errors", json_type, nullable=True),
    )

    op.add_column(
        "migration_plans",
        sa.Column("langgraph_thread_id", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("migration_plans", "langgraph_thread_id")
    op.drop_column("migration_plans", "validation_errors")
    op.drop_column("migration_plans", "is_valid")
