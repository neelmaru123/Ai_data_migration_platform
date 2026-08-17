"""
Business Logic & Persistence Operations Service for Metadata Domain
"""

from datetime import datetime, timezone
import logging
import uuid
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.websocket_manager import manager
from app.modules.agents.agents_models import Agent
from app.modules.sources.sources_models import DataSource
from app.modules.metadata.metadata_models import (
    MetadataColumn,
    MetadataConstraint,
    MetadataRelationship,
    MetadataSchema,
    MetadataSnapshot,
    MetadataTable,
)
from app.modules.metadata.metadata_schemas import (
    MetadataSnapshotSyncPayload,
    TableIngestionPayload,
)

logger = logging.getLogger(__name__)


class MetadataService:
    """Service handling metadata introspection ingestion, persistence, and querying."""

    @staticmethod
    async def ingest_agent_metadata_snapshot(
        session: AsyncSession, agent: Agent, payload: MetadataSnapshotSyncPayload
    ) -> MetadataSnapshot:
        """
        Ingests a structural database metadata snapshot from an authenticated Docker Agent.
        Matches target DataSource, computes version, bulk-persists MetadataSnapshot hierarchy,
        and broadcasts a real-time 'METADATA_PROFILED' WebSocket event.
        """
        now = datetime.now(timezone.utc)

        # 1. Resolve target DataSource entity
        data_source: Optional[DataSource] = None
        data_sources_list = agent.data_sources or []

        if payload.data_source_id:
            data_source = next((ds for ds in data_sources_list if ds.id == payload.data_source_id), None)

        if not data_source and payload.identifier:
            req_id = payload.identifier.lower().strip()
            # Build identifier lookup map
            source_map: Dict[str, DataSource] = {}
            for ds in data_sources_list:
                clean_id = ds.identifier.lower().strip()
                source_map[clean_id] = ds
                if clean_id.startswith("src_"):
                    source_map[clean_id[4:]] = ds
                elif clean_id.startswith("dest_"):
                    source_map[clean_id[5:]] = ds
                else:
                    source_map[f"src_{clean_id}"] = ds
                    source_map[f"dest_{clean_id}"] = ds

            data_source = source_map.get(req_id)

        # Fallback to single data source if only 1 attached
        if not data_source and len(data_sources_list) == 1:
            data_source = data_sources_list[0]

        if not data_source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not match data source identifier '{payload.identifier or payload.data_source_id}' for agent '{agent.id}'.",
            )

        # 2. Determine next snapshot version number
        stmt_ver = (
            select(MetadataSnapshot.version)
            .where(MetadataSnapshot.data_source_id == data_source.id)
            .order_by(MetadataSnapshot.version.desc())
            .limit(1)
        )
        res_ver = await session.execute(stmt_ver)
        latest_ver = res_ver.scalar_one_or_none()
        next_version = (latest_ver + 1) if latest_ver else 1

        # 3. Create MetadataSnapshot header
        snapshot = MetadataSnapshot(
            data_source_id=data_source.id,
            version=next_version,
            database_name=payload.database_name.strip(),
            database_version=payload.database_version.strip() if payload.database_version else None,
            total_tables=payload.total_tables,
            total_columns=payload.total_columns,
            total_rows=payload.total_rows,
            status="completed",
            collected_at=now,
        )
        session.add(snapshot)
        await session.flush()  # Generates snapshot.id

        # 4. Process Schemas and Tables
        # Combine explicit schemas and flat tables into structured schema groups
        schema_table_map: Dict[str, List[TableIngestionPayload]] = {}

        for sch_payload in payload.schemas:
            s_name = sch_payload.schema_name.strip()
            if s_name not in schema_table_map:
                schema_table_map[s_name] = []
            schema_table_map[s_name].extend(sch_payload.tables)

        for tbl_payload in payload.tables:
            s_name = tbl_payload.schema_name.strip() if tbl_payload.schema_name else "public"
            if s_name not in schema_table_map:
                schema_table_map[s_name] = []
            # Prevent duplicate table insertion if already included under schemas
            if not any(t.table_name == tbl_payload.table_name for t in schema_table_map[s_name]):
                schema_table_map[s_name].append(tbl_payload)

        if not schema_table_map:
            schema_table_map["public"] = []

        # Global lookup map for mapping relationships: (schema_name, table_name, column_name) -> (table_id, column_id)
        col_lookup: Dict[Tuple[str, str, str], Tuple[uuid.UUID, uuid.UUID]] = {}
        table_lookup: Dict[Tuple[str, str], uuid.UUID] = {}

        total_cols_count = 0
        total_tables_count = 0

        for schema_name, tables_list in schema_table_map.items():
            db_schema = MetadataSchema(
                snapshot_id=snapshot.id,
                schema_name=schema_name,
            )
            session.add(db_schema)
            await session.flush()

            for tbl_dto in tables_list:
                total_tables_count += 1
                db_table = MetadataTable(
                    schema_id=db_schema.id,
                    table_name=tbl_dto.table_name.strip(),
                    table_type=tbl_dto.table_type.strip().lower(),
                    row_count=tbl_dto.row_count,
                    size_bytes=tbl_dto.size_bytes,
                )
                session.add(db_table)
                await session.flush()
                table_lookup[(schema_name.lower(), tbl_dto.table_name.lower())] = db_table.id

                # Add Columns
                for col_dto in tbl_dto.columns:
                    total_cols_count += 1
                    db_col = MetadataColumn(
                        table_id=db_table.id,
                        column_name=col_dto.column_name.strip(),
                        ordinal_position=col_dto.ordinal_position,
                        data_type=col_dto.data_type.strip(),
                        native_data_type=col_dto.native_data_type.strip() if col_dto.native_data_type else col_dto.data_type.strip(),
                        nullable=col_dto.nullable,
                        is_primary_key=col_dto.is_primary_key,
                        is_unique=col_dto.is_unique,
                        default_value=col_dto.default_value,
                        max_length=col_dto.max_length,
                        numeric_precision=col_dto.numeric_precision,
                        numeric_scale=col_dto.numeric_scale,
                        null_count=col_dto.null_count,
                        distinct_count=col_dto.distinct_count,
                        statistics=col_dto.statistics,
                        sample_values=col_dto.sample_values,
                    )
                    session.add(db_col)
                    await session.flush()
                    col_lookup[(schema_name.lower(), tbl_dto.table_name.lower(), col_dto.column_name.lower())] = (db_table.id, db_col.id)

                # Add Constraints
                for cst_dto in tbl_dto.constraints:
                    db_cst = MetadataConstraint(
                        table_id=db_table.id,
                        constraint_name=cst_dto.constraint_name.strip(),
                        constraint_type=cst_dto.constraint_type.strip().lower(),
                        definition=cst_dto.definition,
                    )
                    session.add(db_cst)

        # 5. Process Relationships
        for rel_dto in payload.relationships:
            src_key = (rel_dto.source_schema.lower(), rel_dto.source_table.lower(), rel_dto.source_column.lower())
            tgt_key = (rel_dto.target_schema.lower(), rel_dto.target_table.lower(), rel_dto.target_column.lower())

            if src_key in col_lookup and tgt_key in col_lookup:
                src_tbl_id, src_col_id = col_lookup[src_key]
                tgt_tbl_id, tgt_col_id = col_lookup[tgt_key]

                db_rel = MetadataRelationship(
                    snapshot_id=snapshot.id,
                    source_table_id=src_tbl_id,
                    source_column_id=src_col_id,
                    target_table_id=tgt_tbl_id,
                    target_column_id=tgt_col_id,
                    relationship_type=rel_dto.relationship_type.strip().lower(),
                    confidence=rel_dto.confidence,
                )
                session.add(db_rel)

        # Update totals if payload provided defaults
        if total_tables_count > 0:
            snapshot.total_tables = total_tables_count
        if total_cols_count > 0:
            snapshot.total_columns = total_cols_count

        # 6. Update DataSource status to 'profiled'
        data_source.status = "profiled"
        data_source.last_checked_at = now
        data_source.last_error = None

        await session.commit()

        # 7. Broadcast real-time WebSocket event to active dashboard clients
        await manager.broadcast_to_agent(
            agent_id=str(agent.id),
            message={
                "event_type": "METADATA_PROFILED",
                "data": {
                    "snapshot_id": str(snapshot.id),
                    "data_source_id": str(data_source.id),
                    "identifier": data_source.identifier,
                    "version": snapshot.version,
                    "total_tables": snapshot.total_tables,
                    "total_columns": snapshot.total_columns,
                    "collected_at": snapshot.collected_at.isoformat(),
                },
            },
        )

        logger.info(
            f"Metadata snapshot v{snapshot.version} successfully ingested for data source '{data_source.identifier}' "
            f"(Snapshot ID: {snapshot.id}, Tables: {snapshot.total_tables}, Columns: {snapshot.total_columns})."
        )

        return await MetadataService.get_snapshot_by_id(session, snapshot.id)  # type: ignore[return-value]

    @staticmethod
    async def get_snapshot_by_id(
        session: AsyncSession, snapshot_id: uuid.UUID
    ) -> Optional[MetadataSnapshot]:
        """Fetch complete hierarchical MetadataSnapshot by ID."""
        stmt = (
            select(MetadataSnapshot)
            .where(MetadataSnapshot.id == snapshot_id)
            .options(
                selectinload(MetadataSnapshot.schemas)
                .selectinload(MetadataSchema.tables)
                .selectinload(MetadataTable.columns),
                selectinload(MetadataSnapshot.schemas)
                .selectinload(MetadataSchema.tables)
                .selectinload(MetadataTable.constraints),
                selectinload(MetadataSnapshot.relationships),
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_latest_snapshot_for_source(
        session: AsyncSession, data_source_id: uuid.UUID
    ) -> Optional[MetadataSnapshot]:
        """Fetch latest MetadataSnapshot for a given DataSource ID."""
        stmt = (
            select(MetadataSnapshot)
            .where(MetadataSnapshot.data_source_id == data_source_id)
            .order_by(MetadataSnapshot.version.desc())
            .limit(1)
            .options(
                selectinload(MetadataSnapshot.schemas)
                .selectinload(MetadataSchema.tables)
                .selectinload(MetadataTable.columns),
                selectinload(MetadataSnapshot.schemas)
                .selectinload(MetadataSchema.tables)
                .selectinload(MetadataTable.constraints),
                selectinload(MetadataSnapshot.relationships),
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_snapshots_for_source(
        session: AsyncSession, data_source_id: uuid.UUID
    ) -> List[MetadataSnapshot]:
        """List all versioned snapshots for a given DataSource ID."""
        stmt = (
            select(MetadataSnapshot)
            .where(MetadataSnapshot.data_source_id == data_source_id)
            .order_by(MetadataSnapshot.version.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
