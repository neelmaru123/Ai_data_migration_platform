"""
Pydantic Validation Schemas for Metadata Ingestion and Response DTOs
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Ingestion Payload Schemas (Agent -> Backend Control Plane)
# ============================================================================

class ColumnIngestionPayload(BaseModel):
    """Column metadata definition received during agent introspection sync."""
    column_name: str = Field(..., min_length=1, max_length=255)
    ordinal_position: int = Field(default=1, ge=1)
    data_type: str = Field(..., min_length=1, max_length=100)
    native_data_type: Optional[str] = Field(None, max_length=100)
    nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    default_value: Optional[str] = None
    max_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    null_count: int = Field(default=0, ge=0)
    distinct_count: int = Field(default=0, ge=0)
    statistics: Optional[Dict[str, Any]] = None
    sample_values: Optional[List[Any]] = None


class ConstraintIngestionPayload(BaseModel):
    """Table constraint definition (primary_key, foreign_key, unique, check)."""
    constraint_name: str = Field(..., min_length=1, max_length=255)
    constraint_type: str = Field(..., min_length=1, max_length=50)  # primary_key, foreign_key, unique, check
    definition: Optional[str] = None


class TableIngestionPayload(BaseModel):
    """Table metadata definition containing columns and constraints."""
    schema_name: str = Field(default="public", max_length=255)
    table_name: str = Field(..., min_length=1, max_length=255)
    table_type: str = Field(default="table", max_length=50)  # table, view, materialized_view
    row_count: int = Field(default=0, ge=0)
    size_bytes: int = Field(default=0, ge=0)
    columns: List[ColumnIngestionPayload] = Field(default_factory=list)
    constraints: List[ConstraintIngestionPayload] = Field(default_factory=list)


class SchemaIngestionPayload(BaseModel):
    """Schema grouping container."""
    schema_name: str = Field(..., min_length=1, max_length=255)
    tables: List[TableIngestionPayload] = Field(default_factory=list)


class RelationshipIngestionPayload(BaseModel):
    """Foreign key or inferred cross-table relationship link."""
    source_schema: str = Field(default="public", max_length=255)
    source_table: str = Field(..., min_length=1, max_length=255)
    source_column: str = Field(..., min_length=1, max_length=255)
    target_schema: str = Field(default="public", max_length=255)
    target_table: str = Field(..., min_length=1, max_length=255)
    target_column: str = Field(..., min_length=1, max_length=255)
    relationship_type: str = Field(default="foreign_key", max_length=50)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MetadataSnapshotSyncPayload(BaseModel):
    """
    Complete payload transmitted by Docker Agent during metadata sync.
    Can identify target data source by `data_source_id` UUID or string `identifier`.
    """
    data_source_id: Optional[uuid.UUID] = None
    identifier: Optional[str] = None
    database_name: str = Field(..., min_length=1, max_length=255)
    database_version: Optional[str] = Field(None, max_length=255)
    total_tables: int = Field(default=0, ge=0)
    total_columns: int = Field(default=0, ge=0)
    total_rows: int = Field(default=0, ge=0)
    schemas: List[SchemaIngestionPayload] = Field(default_factory=list)
    tables: List[TableIngestionPayload] = Field(default_factory=list)  # Direct flat list fallback
    relationships: List[RelationshipIngestionPayload] = Field(default_factory=list)


# ============================================================================
# Response DTO Schemas (Control Plane -> Client / UI / AI Engine)
# ============================================================================

class ColumnResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    column_name: str
    ordinal_position: int
    data_type: str
    native_data_type: str
    nullable: bool
    is_primary_key: bool
    is_unique: bool
    default_value: Optional[str] = None
    max_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    null_count: int = 0
    distinct_count: int = 0
    statistics: Optional[Dict[str, Any]] = None
    sample_values: Optional[List[Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConstraintResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    constraint_name: str
    constraint_type: str
    definition: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TableResponse(BaseModel):
    id: uuid.UUID
    schema_id: uuid.UUID
    table_name: str
    table_type: str
    row_count: int
    size_bytes: int
    columns: List[ColumnResponse] = []
    constraints: List[ConstraintResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SchemaResponse(BaseModel):
    id: uuid.UUID
    snapshot_id: uuid.UUID
    schema_name: str
    tables: List[TableResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RelationshipResponse(BaseModel):
    id: uuid.UUID
    snapshot_id: uuid.UUID
    source_table_id: uuid.UUID
    source_column_id: uuid.UUID
    target_table_id: uuid.UUID
    target_column_id: uuid.UUID
    relationship_type: str
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetadataSnapshotResponse(BaseModel):
    id: uuid.UUID
    data_source_id: uuid.UUID
    version: int
    database_name: str
    database_version: Optional[str] = None
    total_tables: int
    total_columns: int
    total_rows: int
    status: str
    collected_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetadataSnapshotDetailResponse(MetadataSnapshotResponse):
    """Full hierarchical metadata snapshot detail containing all schemas, tables, columns, and relationships."""
    schemas: List[SchemaResponse] = []
    relationships: List[RelationshipResponse] = []
