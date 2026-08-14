"""
Pydantic Request & Response Schemas for Sources Domain (Data Sources Identity)
"""

import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

VALID_SOURCE_TYPES = Literal["postgresql", "mysql", "mongodb", "csv", "excel", "parquet"]
VALID_SOURCE_ROLES = Literal["source", "target", "both"]


class DataSourceCreate(BaseModel):
    """Request payload to register a data source identity for an agent."""
    agent_id: uuid.UUID = Field(..., description="ID of the assigned local Docker Agent")
    name: str = Field(..., min_length=1, max_length=255, examples=["Production Database"])
    type: VALID_SOURCE_TYPES = Field(..., examples=["postgresql"])
    role: VALID_SOURCE_ROLES = Field(default="source", examples=["source"])
    identifier: str = Field(..., min_length=1, max_length=255, examples=["prod_pg_db"])


class DataSourceUpdate(BaseModel):
    """Request payload to update a data source identity."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, examples=["Production Database Main"])
    role: Optional[VALID_SOURCE_ROLES] = Field(None, examples=["target"])
    identifier: Optional[str] = Field(None, min_length=1, max_length=255, examples=["prod_pg_db_v2"])


class DataSourceResponse(BaseModel):
    """Response payload representing a registered data source identity."""
    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    type: str
    role: str
    identifier: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
