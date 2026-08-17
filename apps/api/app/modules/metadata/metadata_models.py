"""
Profiler Domain Database Models (Metadata Management)
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

JSON_TYPE = JSONB().with_variant(JSON, "sqlite")

if TYPE_CHECKING:
    from app.modules.sources.sources_models import DataSource
    from app.modules.migration_plans.migration_plans_models import MigrationPlan


class MetadataSnapshot(Base):
    __tablename__ = "metadata_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    database_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_tables: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_columns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_rows: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
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
    data_source: Mapped["DataSource"] = relationship("DataSource", back_populates="snapshots")
    schemas: Mapped[List["MetadataSchema"]] = relationship(
        "MetadataSchema", back_populates="snapshot", cascade="all, delete-orphan"
    )
    relationships: Mapped[List["MetadataRelationship"]] = relationship(
        "MetadataRelationship", back_populates="snapshot", cascade="all, delete-orphan"
    )
    migration_plans: Mapped[List["MigrationPlan"]] = relationship(
        "MigrationPlan", secondary="migration_plan_snapshots", back_populates="snapshots"
    )


class MetadataSchema(Base):
    __tablename__ = "metadata_schemas"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "schema_name", name="uq_metadata_schemas_snapshot_schema"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_snapshots.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    snapshot: Mapped["MetadataSnapshot"] = relationship("MetadataSnapshot", back_populates="schemas")
    tables: Mapped[List["MetadataTable"]] = relationship(
        "MetadataTable", back_populates="schema", cascade="all, delete-orphan"
    )


class MetadataTable(Base):
    __tablename__ = "metadata_tables"
    __table_args__ = (
        UniqueConstraint("schema_id", "table_name", name="uq_metadata_tables_schema_table"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_schemas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_type: Mapped[str] = mapped_column(String(50), default="table", nullable=False)
    row_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    schema: Mapped["MetadataSchema"] = relationship("MetadataSchema", back_populates="tables")
    columns: Mapped[List["MetadataColumn"]] = relationship(
        "MetadataColumn", back_populates="table", cascade="all, delete-orphan"
    )
    constraints: Mapped[List["MetadataConstraint"]] = relationship(
        "MetadataConstraint", back_populates="table", cascade="all, delete-orphan"
    )


class MetadataColumn(Base):
    __tablename__ = "metadata_columns"
    __table_args__ = (
        UniqueConstraint("table_id", "column_name", name="uq_metadata_columns_table_column"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_tables.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    native_data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    max_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    numeric_precision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    numeric_scale: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    null_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    distinct_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    statistics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    sample_values: Mapped[Optional[List[Any]]] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    table: Mapped["MetadataTable"] = relationship("MetadataTable", back_populates="columns")


class MetadataConstraint(Base):
    __tablename__ = "metadata_constraints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_tables.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    constraint_name: Mapped[str] = mapped_column(String(255), nullable=False)
    constraint_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # primary_key, foreign_key, unique, check, not_null
    definition: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    table: Mapped["MetadataTable"] = relationship("MetadataTable", back_populates="constraints")


class MetadataRelationship(Base):
    __tablename__ = "metadata_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_snapshots.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_tables.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_column_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_columns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_tables.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_column_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_columns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # foreign_key, inferred, reference
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    snapshot: Mapped["MetadataSnapshot"] = relationship("MetadataSnapshot", back_populates="relationships")
    source_table: Mapped["MetadataTable"] = relationship(
        "MetadataTable", foreign_keys=[source_table_id]
    )
    source_column: Mapped["MetadataColumn"] = relationship(
        "MetadataColumn", foreign_keys=[source_column_id]
    )
    target_table: Mapped["MetadataTable"] = relationship(
        "MetadataTable", foreign_keys=[target_table_id]
    )
    target_column: Mapped["MetadataColumn"] = relationship(
        "MetadataColumn", foreign_keys=[target_column_id]
    )
