"""add_migration_plan_versions

Revision ID: 008_migration_plan_versions
Revises: 007_ai_diagnosis_migration_jobs
Create Date: 2026-08-26
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "008_migration_plan_versions"
down_revision: Union[str, None] = "007_ai_diagnosis_migration_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "migration_plan_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "migration_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migration_plans.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("edit_type", sa.String(50), nullable=False),
        sa.Column("user_feedback", sa.Text(), nullable=True),
        sa.Column("plan_data", json_type, nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("validation_errors", json_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("migration_plan_id", "version_number", name="uq_plan_version"),
    )
    op.create_index(
        "idx_mpv_plan_id_version",
        "migration_plan_versions",
        ["migration_plan_id", sa.text("version_number DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_mpv_plan_id_version", table_name="migration_plan_versions")
    op.drop_table("migration_plan_versions")
