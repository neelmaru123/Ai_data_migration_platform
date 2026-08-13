"""
Agents Domain Schemas (Pydantic boundaries)
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class AgentBase(BaseModel):
    name: str
    agent_identifier: str


class AgentResponse(AgentBase):
    id: UUID
    user_id: UUID
    status: str
    version: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
