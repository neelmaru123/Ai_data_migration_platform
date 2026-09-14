"""add_error_fields_to_agents

Revision ID: a7d8e9f1234c
Revises: 5efc466974d2
Create Date: 2026-09-07 17:37:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7d8e9f1234c'
down_revision: Union[str, None] = '5efc466974d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'agents',
        sa.Column(
            'last_error',
            sa.Text(),
            nullable=True,
            comment="Human-readable description of the fatal error that stopped or degraded the agent.",
        ),
    )
    op.add_column(
        'agents',
        sa.Column(
            'error_category',
            sa.String(100),
            nullable=True,
            comment="Category tag for the fatal error (e.g. CONFIG_ERROR, AUTH_ERROR, RUNTIME_CRASH, DISCONNECTED_UNEXPECTEDLY).",
        ),
    )
    op.add_column(
        'agents',
        sa.Column(
            'last_error_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when the fatal stopping error occurred or was recorded.",
        ),
    )


def downgrade() -> None:
    op.drop_column('agents', 'last_error_at')
    op.drop_column('agents', 'error_category')
    op.drop_column('agents', 'last_error')
