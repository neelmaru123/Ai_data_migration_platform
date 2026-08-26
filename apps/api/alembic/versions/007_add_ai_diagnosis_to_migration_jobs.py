"""add_ai_diagnosis_to_migration_jobs

Revision ID: 007_ai_diagnosis_migration_jobs
Revises: 006_feasibility_and_langgraph
Create Date: 2026-08-25
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007_ai_diagnosis_migration_jobs"
down_revision: Union[str, None] = "006_feasibility_and_langgraph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "migration_jobs",
        sa.Column("ai_diagnosis", json_type, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("migration_jobs", "ai_diagnosis")
