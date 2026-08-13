"""
Agents Domain Routes (API endpoints boundary)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/health")
async def agents_health():
    return {"status": "agents module active"}
