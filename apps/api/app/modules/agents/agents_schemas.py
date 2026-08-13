"""
Agents Domain Schemas (Pydantic boundaries)
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.modules.sources.sources_schemas import (
    DataSourceResponse,
    VALID_SOURCE_ROLES,
    VALID_SOURCE_TYPES,
)


class InitialDataSourceCreate(BaseModel):
    """Schema for registering a source or target database identity during Agent creation."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Primary PostgreSQL DB"])
    type: VALID_SOURCE_TYPES = Field(..., examples=["postgresql"])
    role: VALID_SOURCE_ROLES = Field(default="source", examples=["source"])
    identifier: str = Field(..., min_length=1, max_length=255, examples=["prod_pg_db"])


class AgentCreate(BaseModel):
    """Request payload to register a new Docker Agent."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Local Production Agent"])
    agent_identifier: str = Field(..., min_length=1, max_length=255, examples=["agent_prod_001"])
    version: Optional[str] = Field(None, max_length=50, examples=["1.0.0"])
    data_sources: Optional[List[InitialDataSourceCreate]] = Field(
        default=None,
        description="Optional list of source and destination database identities to attach concurrently during agent creation.",
    )


class AgentUpdate(BaseModel):
    """Request payload to update agent details."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, max_length=50, examples=["online", "offline", "busy"])
    version: Optional[str] = Field(None, max_length=50, examples=["1.0.1"])


class AgentHeartbeat(BaseModel):
    """Request payload for agent periodic heartbeat status ping."""
    status: str = Field(default="online", max_length=50, examples=["online", "busy"])
    version: Optional[str] = Field(None, max_length=50, examples=["1.0.1"])


class AgentResponse(BaseModel):
    """Basic response representation of an Agent."""
    id: UUID
    user_id: UUID
    name: str
    agent_identifier: str
    status: str
    version: Optional[str] = None
    api_token: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentDetailResponse(AgentResponse):
    """Detailed response representation of an Agent with all linked data sources."""
    data_sources: List[DataSourceResponse] = []

    model_config = ConfigDict(from_attributes=True)
