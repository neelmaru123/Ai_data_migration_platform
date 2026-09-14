"""add_idle_since_to_agents

Revision ID: 5efc466974d2
Revises: '008_migration_plan_versions'
Create Date: 2026-09-07 15:21:12.031295

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5efc466974d2'
down_revision: Union[str, None] = '008_migration_plan_versions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add idle_since column to agents table.
    # Tracks when the agent last became idle (no active/queued jobs).
    # Used by the backend to determine when to issue ENTER_IDLE_MODE (Option C)
    # or SHUTDOWN (Option A) directives in heartbeat responses.
    op.add_column(
        'agents',
        sa.Column(
            'idle_since',
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp when agent last became idle (no active jobs). "
                "Set on job complete/fail, cleared on new job queued. "
                "Used to determine ENTER_IDLE_MODE / SHUTDOWN directives."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column('agents', 'idle_since')
