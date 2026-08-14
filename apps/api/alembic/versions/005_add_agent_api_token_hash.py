"""add_agent_api_token_hash

Revision ID: 005_agent_api_token_hash
Revises: 004_agent_centric_arch
Create Date: 2026-08-14
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_agent_api_token_hash"
down_revision: Union[str, None] = "004_agent_centric_arch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add api_token_hash column to agents table if it does not exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("agents")]

    if "api_token_hash" not in columns:
        op.add_column(
            "agents",
            sa.Column("api_token_hash", sa.String(length=255), nullable=True),
        )
        op.create_index(
            op.f("ix_agents_api_token_hash"),
            "agents",
            ["api_token_hash"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_agents_api_token_hash"), table_name="agents")
    op.drop_column("agents", "api_token_hash")
