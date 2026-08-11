"""
Pydantic Request & Response Schemas for Sources Domain
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.modules.sources.sources_connectors import (
    ConnectionHealthResult,
    DatabaseMetadata,
)
from app.modules.sources.sources_loaders import FileSchemaMetadata


class ConnectionConfig(BaseModel):
    """Generic payload for database connection parameters."""
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None
    ssl_mode: Optional[str] = None


class ConnectionCreate(BaseModel):
    """Request payload to register a new DB or File Source."""
    name: str = Field(..., examples=["Legacy Production Postgres"])
    type: str = Field(..., examples=["postgresql"])  # postgresql, mysql, mongodb, csv, excel
    role: str = Field(default="source", examples=["source"])  # source, target
    config: ConnectionConfig


class ConnectionResponse(BaseModel):
    """Response payload representing a registered connection."""
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: str
    role: str
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    status: str
    last_tested_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestConnectionRequest(BaseModel):
    """Request payload to test connection health prior to saving."""
    type: str = Field(..., examples=["postgresql"])
    config: ConnectionConfig
