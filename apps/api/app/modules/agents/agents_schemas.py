"""
Agents Domain Schemas (Pydantic boundaries)
"""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.modules.sources.sources_schemas import (
    DataSourceResponse,
    VALID_SOURCE_ROLES,
    VALID_SOURCE_TYPES,
)

VALID_AGENT_STATUS = Literal["online", "offline", "busy", "degraded", "error"]


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
    """Request payload to update agent details (name, version). Status is managed strictly by agent heartbeats & backend watchdog."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    version: Optional[str] = Field(None, max_length=50, examples=["1.0.1"])


class DataSourceHealthReport(BaseModel):
    """Health and connectivity report for an individual Data Source on the Agent."""
    identifier: str = Field(..., description="Logical identifier of the data source on the agent")
    is_healthy: bool = Field(..., description="Whether database connection and credential check succeeded")
    error_type: Optional[str] = Field(None, description="Classified error type (e.g. ConnectionRefused, AuthenticationFailed)")
    error_message: Optional[str] = Field(None, description="Sanitized diagnostic error message")
    latency_ms: float = Field(default=0.0, description="Ping/query latency in milliseconds")
    server_version: Optional[str] = Field(None, description="Database server version if connection succeeded")
    database_name: Optional[str] = Field(None, description="Database or collection name")


class AgentHeartbeat(BaseModel):
    """Request payload for agent periodic heartbeat status ping, fatal stopping errors, and data source diagnostics."""
    status: VALID_AGENT_STATUS = "online"
    version: Optional[str] = Field(None, max_length=50, examples=["1.0.1"])
    data_sources: Optional[List[DataSourceHealthReport]] = Field(
        default=None,
        description="Optional list of health diagnostics for attached data sources",
    )
    error_message: Optional[str] = Field(
        None,
        description="Diagnostic explanation if the agent encountered a fatal error causing it to stop or degrade.",
    )
    error_category: Optional[str] = Field(
        None,
        description="Category tag for the stopping error (e.g. CONFIG_ERROR, AUTH_ERROR, RUNTIME_CRASH).",
    )


class AgentFatalErrorRequest(BaseModel):
    """Emergency fatal error reporting payload when an agent is stopping."""
    error_message: str = Field(..., description="Description of the fatal stopping error")
    error_category: str = Field(default="FATAL_ERROR", description="Category tag for the stopping error")


VALID_AGENT_ACTION = Literal["SHUTDOWN", "ENTER_IDLE_MODE", "RESUME_ACTIVE_MODE"]


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
    last_error: Optional[str] = None
    error_category: Optional[str] = None
    last_error_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Control directive fields — backend uses these to command the agent
    # (e.g. slow heartbeat, resume fast mode, or shut down container)
    action: Optional[str] = Field(
        default=None,
        description="Optional backend control directive: 'SHUTDOWN', 'ENTER_IDLE_MODE', or 'RESUME_ACTIVE_MODE'",
    )
    action_reason: Optional[str] = Field(
        default=None,
        description="Human-readable explanation for the issued action directive.",
    )

    model_config = ConfigDict(from_attributes=True)


class AgentDetailResponse(AgentResponse):
    """Detailed response representation of an Agent with all linked data sources and ready-to-run Docker commands."""
    data_sources: List[DataSourceResponse] = []
    docker_command: Optional[str] = Field(
        None,
        description="Ready-to-run multi-line Bash / Linux / macOS Docker command with credential placeholders.",
    )
    docker_command_powershell: Optional[str] = Field(
        None,
        description="Ready-to-run Windows PowerShell Docker command with backtick line continuations.",
    )
    docker_command_oneline: Optional[str] = Field(
        None,
        description="Single-line Docker run command for easy copy-paste.",
    )
    env_template: Optional[str] = Field(
        None,
        description="Formatted .env file template containing all agent and database environment variables.",
    )

    model_config = ConfigDict(from_attributes=True)


class AgentDockerCommandResponse(BaseModel):
    """Response payload specifically containing Docker commands and environment template for an Agent."""
    agent_id: UUID
    agent_identifier: str
    docker_command: str
    docker_command_powershell: str
    docker_command_oneline: str
    env_template: str
    environment_variables: dict[str, str] = Field(default_factory=dict)

