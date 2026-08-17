"""
Migration Plans Domain — Pydantic Schemas & AST Contract

Defines the complete TransformationPlanAST Pydantic model hierarchy that:
- Serves as the strict JSON contract the LLM must generate.
- Is used with LangChain's `with_structured_output()` for schema-enforced output.
- Powers the Next.js UI visualization layer (ui_badge_type, explanation per column).
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Column-Level Transformation Types
# ============================================================================

COLUMN_TRANSFORMATION_TYPES = Literal[
    "direct_copy",       # 1:1 column copy, no transformation
    "merge_concat",      # Combine 2+ source columns into 1 target column
    "type_cast",         # Data type conversion (VARCHAR → UUID, INT → BIGINT)
    "split",             # Decompose 1 source column into 2+ target columns
    "expression",        # Derive value using SQL expression
    "lookup_join",       # Resolve FK → referenced table descriptive column
    "default_constant",  # Fill with hardcoded constant value
    "drop_column",       # Source column has no target equivalent — dropped
    "new_column_added",  # New target column with no source equivalent
]

TABLE_TRANSFORMATION_TYPES = Literal[
    "direct_copy",    # Table copied unchanged from exactly 1 source database
    "merge",          # 2+ source tables combined (union/join) into 1 target table
    "split_target",   # 1 source table decomposed into 2+ target tables
]


# ============================================================================
# Source References
# ============================================================================

class SourceColumnRef(BaseModel):
    """Reference to a specific source column in a source database."""
    identifier: str = Field(..., description="Logical database alias (e.g. 'source_db_1')")
    schema_name: str = Field(default="public", description="Schema name in source database")
    table_name: str = Field(..., description="Source table name")
    column_name: str = Field(..., description="Source column name")


class SourceTableRef(BaseModel):
    """Reference to a source table participating in a table-level mapping."""
    identifier: str = Field(..., description="Logical database alias (e.g. 'source_db_1')")
    schema_name: str = Field(default="public", description="Schema name in source database")
    table_name: str = Field(..., description="Source table name")
    join_type: Literal["primary", "union_merge", "left_join", "right_join"] = Field(
        default="primary",
        description="How this source table participates in the target table construction",
    )


# ============================================================================
# Conflict Resolution
# ============================================================================

class ConflictResolutionSpec(BaseModel):
    """Strategy for handling PK conflicts and duplicate rows when merging sources."""
    primary_key_strategy: Literal[
        "uuid_v4_rekey",         # Replace integer PKs with new UUIDs
        "prefix_id",             # Prefix existing IDs with source alias (src1_101)
        "autoincrement_offset",  # Offset auto-increment ranges per source
        "keep_original",         # Keep existing PKs as-is (only if globally unique)
    ] = Field(default="uuid_v4_rekey")
    deduplication_key: Optional[str] = Field(
        None, description="Business key used for deduplication (e.g. 'email')"
    )
    deduplication_strategy: Optional[Literal[
        "first_wins",           # Keep first occurrence
        "last_updated_wins",    # Keep most recently updated row
        "merge_all",            # Keep all rows (no deduplication)
    ]] = Field(default="first_wins")


# ============================================================================
# Column Mapping Specification
# ============================================================================

class ColumnMappingSpec(BaseModel):
    """
    Defines how a target column is produced from one or more source columns.
    This is the primary unit the UI uses to render transformation visualization cards.
    """
    target_column_name: Optional[str] = Field(
        None, description="Target column name. Null only for drop_column type."
    )
    target_data_type: Optional[str] = Field(
        None, description="Target column SQL data type (e.g. 'uuid', 'varchar(255)', 'numeric(10,2)')"
    )
    nullable: Optional[bool] = Field(None, description="Whether target column allows NULL values")
    is_primary_key: bool = Field(default=False)
    transformation_type: COLUMN_TRANSFORMATION_TYPES = Field(
        ..., description="Type of transformation applied to produce this target column"
    )
    ui_badge_type: COLUMN_TRANSFORMATION_TYPES = Field(
        ..., description="Badge type for UI rendering — must match transformation_type"
    )
    source_columns: List[SourceColumnRef] = Field(
        default_factory=list,
        description="Source columns feeding this target column. Empty for new_column_added and default_constant.",
    )
    expression_template: Optional[str] = Field(
        None, description="SQL expression template for expression, merge_concat, and split types"
    )
    constant_value: Optional[str] = Field(
        None, description="The constant value for default_constant type (e.g. 'org_01')"
    )
    explanation: str = Field(
        ..., description="Plain-English explanation for the non-technical user shown in the UI"
    )


# ============================================================================
# Table Mapping Specification
# ============================================================================

class TableMappingSpec(BaseModel):
    """
    Defines how a target table is constructed from one or more source tables.
    Contains all column mappings and conflict resolution strategies.
    """
    target_table_name: str = Field(..., description="Name of the target table")
    transformation_type: TABLE_TRANSFORMATION_TYPES = Field(
        ..., description="Table-level transformation type"
    )
    ai_reasoning: str = Field(
        ..., description="LLM explanation of why this table mapping was chosen"
    )
    confidence_score: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="LLM confidence in this table mapping (0.0 – 1.0)"
    )
    conflict_resolution: Optional[ConflictResolutionSpec] = Field(
        None, description="Required when transformation_type is 'merge'"
    )
    source_tables: List[SourceTableRef] = Field(
        ..., description="One or more source tables contributing to this target table"
    )
    column_mappings: List[ColumnMappingSpec] = Field(
        ..., description="All target columns with their transformation specs"
    )


# ============================================================================
# Top-Level Transformation Plan AST (LLM Output Contract)
# ============================================================================

class TransformationPlanAST(BaseModel):
    """
    The complete, structured AI-generated migration plan.
    This is the exact JSON structure the LLM must produce via with_structured_output().
    """
    target_database_type: str = Field(
        ..., description="Target database dialect (e.g. 'postgresql', 'mysql', 'sqlite')"
    )
    ai_explanation: str = Field(
        ..., description="Markdown narrative explaining the overall multi-source merge strategy shown to user"
    )
    confidence_score: float = Field(
        default=0.9, ge=0.0, le=1.0,
        description="Overall LLM confidence in the generated plan"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of data quality risks, manual cleanup suggestions, or ambiguous mappings"
    )
    table_mappings: List[TableMappingSpec] = Field(
        ..., description="All target tables with their full transformation specifications"
    )
    pre_migration_ddl: List[str] = Field(
        default_factory=list,
        description="SQL DDL statements to execute BEFORE migration (CREATE TABLE, CREATE EXTENSION, etc.)"
    )
    post_migration_ddl: List[str] = Field(
        default_factory=list,
        description="SQL DDL statements to execute AFTER migration (CREATE INDEX, ADD CONSTRAINT, etc.)"
    )


# ============================================================================
# REST API Request / Response DTOs
# ============================================================================

class TargetDatabaseConfig(BaseModel):
    """Configuration of the target database the user wants to migrate into."""
    database_type: str = Field(default="postgresql", description="Target DB dialect")
    identifier: Optional[str] = Field(
        None, description="Target DataSource identifier if already registered in the system"
    )
    custom_instructions: Optional[str] = Field(
        None, description="Optional user instructions to guide the LLM (e.g. 'Prefer UUID primary keys')"
    )


class PlanGenerationRequest(BaseModel):
    """Request body for POST /api/v1/plans/generate."""
    agent_id: uuid.UUID = Field(..., description="Agent ID whose source DataSources will be profiled")
    target_config: TargetDatabaseConfig = Field(
        ..., description="Target database configuration"
    )


class PlanResponse(BaseModel):
    """Summary response for list endpoints."""
    id: uuid.UUID
    agent_id: Optional[uuid.UUID]
    status: str
    ai_model: Optional[str]
    confidence_score: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanDetailResponse(PlanResponse):
    """Full response including plan AST data for UI rendering."""
    plan_data: Dict[str, Any]
    target_config: Optional[Dict[str, Any]]
    prompt_version: Optional[str]

    model_config = ConfigDict(from_attributes=True)
