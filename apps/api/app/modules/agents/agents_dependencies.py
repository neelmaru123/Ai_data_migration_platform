"""
Security & Permission Middleware Dependencies for Agents Domain
"""

import hashlib
import uuid
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.modules.agents.agents_models import Agent


def hash_agent_token(raw_token: str) -> str:
    """Computes SHA-256 hex digest of a raw agent token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


async def get_current_agent(
    x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """
    FastAPI Security Dependency that authenticates an Agent via API Token.
    Checks `X-Agent-Token` header first, then fallback to `Authorization: Bearer <token>`.
    Verifies token hash against `agents.api_token_hash`.
    """
    token = x_agent_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent API token missing. Provide 'X-Agent-Token' header.",
        )

    token_hash = hash_agent_token(token)
    stmt = (
        select(Agent)
        .where(Agent.api_token_hash == token_hash)
        .options(selectinload(Agent.data_sources))
    )
    res = await db.execute(stmt)
    agent = res.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked Agent API token.",
        )

    return agent
