"""
MySQL / MariaDB Database Connector Implementation
"""

import time
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.sources.sources_connectors.sources_connectors_base import (
    BaseConnector,
    ColumnMetadata,
    ConnectionHealthResult,
    DatabaseMetadata,
    TableMetadata,
)
from app.modules.sources.sources_connectors.sources_connectors_factory import ConnectorFactory


@ConnectorFactory.register("mysql")
@ConnectorFactory.register("mariadb")
class MySQLConnector(BaseConnector):
    """MySQL Database Connector powered by SQLAlchemy aiomysql."""

    def _build_connection_string(self) -> str:
        """Construct MySQL aiomysql connection URI."""
        if "connection_string" in self.config and self.config["connection_string"]:
            return self.config["connection_string"]

        user = self.config.get("username", "root")
        password = self.config.get("password", "")
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 3306)
        database = self.config.get("database_name", "mysql")

        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"

    def _get_engine(self):
        """
        Create a SQLAlchemy async engine for this connector config.
        Note: Engines are created per-call because connectors are stateless by design.
        For high-throughput scenarios, consider caching this at the service layer.
        pool_pre_ping=True ensures stale connections are discarded automatically.
        """
        return create_async_engine(
            self._build_connection_string(),
            echo=False,
            pool_pre_ping=True,
        )

    async def test_connection(self) -> ConnectionHealthResult:
        start_time = time.perf_counter()
        engine = self._get_engine()

        try:
            async with engine.connect() as conn:
                res = await conn.execute(text("SELECT VERSION();"))
                version_str = res.scalar() or "MySQL"
                latency = (time.perf_counter() - start_time) * 1000

                return ConnectionHealthResult(
                    is_healthy=True,
                    latency_ms=round(latency, 2),
                    server_version=str(version_str),
                    database_name=self.config.get("database_name"),
                )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ConnectionHealthResult(
                is_healthy=False,
                latency_ms=round(latency, 2),
                error_message=str(e),
            )
        finally:
            await engine.dispose()

    async def introspect_schema(self) -> DatabaseMetadata:
        engine = self._get_engine()
        db_name = self.config.get("database_name", "mysql")

        try:
            async with engine.connect() as conn:
                ver_res = await conn.execute(text("SELECT VERSION();"))
                server_ver = ver_res.scalar() or "MySQL"

                # Enumerate visible schemas / databases (not just the connected db)
                schema_query = text("""
                    SELECT SCHEMA_NAME
                    FROM information_schema.SCHEMATA
                    WHERE SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                    ORDER BY SCHEMA_NAME;
                """)
                schema_res = await conn.execute(schema_query)
                schemas = [row[0] for row in schema_res.fetchall()]

                table_query = text("""
                    SELECT TABLE_NAME, TABLE_TYPE, TABLE_ROWS
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = :db_name
                    ORDER BY TABLE_NAME;
                """)
                table_res = await conn.execute(table_query, {"db_name": db_name})
                table_rows = table_res.fetchall()

                column_query = text("""
                    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE,
                           CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, ORDINAL_POSITION
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = :db_name
                    ORDER BY TABLE_NAME, ORDINAL_POSITION;
                """)
                column_res = await conn.execute(column_query, {"db_name": db_name})
                col_rows = column_res.fetchall()

                cols_by_table: Dict[str, List[ColumnMetadata]] = {}
                total_columns = 0
                for c in col_rows:
                    t_name = c[0]
                    if t_name not in cols_by_table:
                        cols_by_table[t_name] = []

                    cols_by_table[t_name].append(
                        ColumnMetadata(
                            name=c[1],
                            data_type=c[2],
                            native_type=c[3],
                            nullable=(c[4].upper() == "YES"),
                            max_length=c[5],
                            numeric_precision=c[6],
                            numeric_scale=c[7],
                        )
                    )
                    total_columns += 1

                tables: List[TableMetadata] = []
                for t in table_rows:
                    t_name, t_type, row_est = t[0], t[1], t[2]
                    col_list = cols_by_table.get(t_name, [])

                    # Note: TABLE_ROWS is an InnoDB planner estimate (may be off by ±50%).
                    # It matches the "estimated_rows" semantic of our metadata model.
                    estimated_rows = int(row_est) if row_est is not None else 0

                    tables.append(
                        TableMetadata(
                            schema_name=db_name,
                            table_name=t_name,
                            table_type="table" if "BASE" in t_type.upper() else "view",
                            estimated_rows=estimated_rows,
                            columns=col_list,
                        )
                    )

                return DatabaseMetadata(
                    database_name=db_name,
                    server_version=str(server_ver),
                    schemas=schemas,
                    tables=tables,
                    total_tables=len(tables),
                    total_columns=total_columns,
                )
        finally:
            await engine.dispose()

    async def get_table_sample(
        self, table_name: str, schema_name: str = "public", limit: int = 10
    ) -> List[Dict[str, Any]]:
        engine = self._get_engine()

        try:
            async with engine.connect() as conn:
                stmt = text(f"SELECT * FROM `{table_name}` LIMIT :limit")
                res = await conn.execute(stmt, {"limit": limit})
                keys = res.keys()
                rows = res.fetchall()
                return [dict(zip(keys, row)) for row in rows]
        finally:
            await engine.dispose()

    async def stream_table_data(
        self, table_name: str, schema_name: str = "public", chunk_size: int = 10000
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        engine = self._get_engine()

        try:
            async with engine.connect() as conn:
                result_stream = await conn.stream(text(f"SELECT * FROM `{table_name}`"))
                keys = result_stream.keys()

                batch: List[Dict[str, Any]] = []
                async for row in result_stream:
                    batch.append(dict(zip(keys, row)))
                    if len(batch) >= chunk_size:
                        yield batch
                        batch = []

                if batch:
                    yield batch
        finally:
            await engine.dispose()
