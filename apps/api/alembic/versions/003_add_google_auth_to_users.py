"""add_google_auth_to_users

Revision ID: 003_add_google_auth
Revises: 002_add_agents
Create Date: 2026-08-12
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_add_google_auth"
down_revision: Union[str, None] = "002_add_agents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add google_id column to users table
    op.add_column("users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_users_google_id"), "users", ["google_id"], unique=True)

    # 2. Make password_hash nullable for OAuth users
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # 1. Revert password_hash to NOT NULL
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)

    # 2. Drop google_id index and column
    op.drop_index(op.f("ix_users_google_id"), table_name="users")
    op.drop_column("users", "google_id")
