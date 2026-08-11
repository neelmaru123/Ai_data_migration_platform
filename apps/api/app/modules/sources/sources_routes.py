"""
FastAPI Router Endpoints for Sources Domain
"""

import os
import tempfile
import uuid
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.sources.sources_connectors import (
    ConnectionHealthResult,
    DatabaseMetadata,
)
from app.modules.sources.sources_loaders import FileSchemaMetadata
from app.modules.sources.sources_schemas import (
    ConnectionCreate,
    ConnectionResponse,
    TestConnectionRequest,
)
from app.modules.sources.sources_services import SourceService

router = APIRouter(prefix="/sources", tags=["Sources & Connectors"])

# Mock User ID for development phase until auth middleware is wired
MOCK_USER_ID = uuid.UUID("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11")


@router.post("/test", response_model=ConnectionHealthResult)
async def test_source_connection(payload: TestConnectionRequest):
    """Test connection health & latency for PostgreSQL, MySQL, or MongoDB."""
    config_dict = payload.config.model_dump(exclude_none=True)
    try:
        return await SourceService.test_connection_config(
            type_name=payload.type, config_dict=config_dict
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection test error: {str(e)}",
        )


@router.post("/introspect", response_model=DatabaseMetadata)
async def introspect_source_schema(payload: TestConnectionRequest):
    """Perform live schema introspection for database sources."""
    config_dict = payload.config.model_dump(exclude_none=True)
    try:
        return await SourceService.introspect_connection_schema(
            type_name=payload.type, config_dict=config_dict
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schema introspection error: {str(e)}",
        )


@router.post("/upload-file", response_model=FileSchemaMetadata)
async def upload_and_introspect_file(file: UploadFile = File(...)):
    """Upload a CSV or Excel file and inspect headers, column types, and sample rows."""
    filename = file.filename or "uploaded_data.csv"
    ext = filename.split(".")[-1].lower()

    if ext not in ["csv", "xlsx", "xls"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a CSV (.csv) or Excel (.xlsx, .xls) file.",
        )

    # Save to temp location for inspection
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        schema_meta = await SourceService.inspect_uploaded_file(
            file_type=ext, file_path=tmp_path
        )
        schema_meta.filename = filename
        return schema_meta
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_source_connection(
    payload: ConnectionCreate, session: AsyncSession = Depends(get_db)
):
    """Save a new database connection or file source."""
    return await SourceService.create_connection(
        session=session, user_id=MOCK_USER_ID, data=payload
    )


@router.get("", response_model=List[ConnectionResponse])
async def list_source_connections(session: AsyncSession = Depends(get_db)):
    """List all registered database and file connections."""
    return await SourceService.get_all_connections(
        session=session, user_id=MOCK_USER_ID
    )
