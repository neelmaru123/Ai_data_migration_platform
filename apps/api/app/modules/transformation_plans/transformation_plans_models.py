"""
Transformation Plans Domain Database Models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, String, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

JSON_TYPE = JSONB().with_variant(JSON, "sqlite")

if TYPE_CHECKING:
    from app.modules.users.users_models import User
    from app.modules.sources.sources_models import Connection
    from app.modules.execution.execution_models import MigrationJob


class MigrationPlan(Base):
    __tablename__ = "migration_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    source_connection_ids: Mapped[Any] = mapped_column(JSON_TYPE, nullable=False)
    source_snapshot_ids: Mapped[Any] = mapped_column(JSON_TYPE, nullable=False)
    plan: Mapped[Any] = mapped_column(JSON_TYPE, nullable=False)
    ai_model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="migration_plans")
    target_connection: Mapped[Optional["Connection"]] = relationship(
        "Connection", back_populates="target_migration_plans"
    )
    jobs: Mapped[List["MigrationJob"]] = relationship(
        "MigrationJob", back_populates="plan", cascade="all, delete-orphan"
    )
