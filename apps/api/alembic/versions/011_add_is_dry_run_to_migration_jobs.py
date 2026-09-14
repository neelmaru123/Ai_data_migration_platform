"""add_is_dry_run_to_migration_jobs

Revision ID: b8e9f1a2345d
Revises: a7d8e9f1234c
Create Date: 2026-09-09 11:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8e9f1a2345d'
down_revision: Union[str, None] = 'a7d8e9f1234c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'migration_jobs',
        sa.Column(
            'is_dry_run',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment="Whether this job is a dry run simulation (no DDL or target writes).",
        ),
    )


def downgrade() -> None:
    op.drop_column('migration_jobs', 'is_dry_run')
