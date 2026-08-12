"""
Sources Domain Database Models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

JSON_TYPE = JSONB().with_variant(JSON, "sqlite")

if TYPE_CHECKING:
    from app.modules.users.users_models import User
    from app.modules.profiler.profiler_models import MetadataSnapshot
    from app.modules.transformation_plans.transformation_plans_models import MigrationPlan
    from app.modules.agents.agents_models import Agent


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # postgresql, mysql, mongodb, csv, excel, parquet
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # source, target
    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    database_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    credentials_encrypted: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    user: Mapped["User"] = relationship("User", back_populates="connections")
    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="connections")
    snapshots: Mapped[List["MetadataSnapshot"]] = relationship(
        "MetadataSnapshot", back_populates="connection", cascade="all, delete-orphan"
    )
    target_migration_plans: Mapped[List["MigrationPlan"]] = relationship(
        "MigrationPlan", back_populates="target_connection"
    )
