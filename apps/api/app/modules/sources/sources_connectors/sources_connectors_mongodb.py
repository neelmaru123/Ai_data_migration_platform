"""
MongoDB Document Database Connector Implementation
"""

import time
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List
from motor.motor_asyncio import AsyncIOMotorClient

from app.modules.sources.sources_connectors.sources_connectors_base import (
    BaseConnector,
    ColumnMetadata,
    ConnectionHealthResult,
    DatabaseMetadata,
    TableMetadata,
)
from app.modules.sources.sources_connectors.sources_connectors_factory import ConnectorFactory


@ConnectorFactory.register("mongodb")
@ConnectorFactory.register("mongo")
class MongoDBConnector(BaseConnector):
    """MongoDB Database Connector powered by motor async driver."""

    def _build_connection_string(self) -> str:
        """Construct MongoDB URI."""
        if "connection_string" in self.config and self.config["connection_string"]:
            return self.config["connection_string"]

        user = self.config.get("username", "")
        password = self.config.get("password", "")
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 27017)
        database = self.config.get("database_name", "admin")

        if user and password:
            return f"mongodb://{user}:{password}@{host}:{port}/{database}"
        return f"mongodb://{host}:{port}/{database}"

    async def test_connection(self) -> ConnectionHealthResult:
        start_time = time.perf_counter()
        uri = self._build_connection_string()
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)

        try:
            # server_info() both proves connectivity AND returns version — one round-trip (fix #8)
            server_info = await client.server_info()
            version_str = server_info.get("version", "MongoDB")
            latency = (time.perf_counter() - start_time) * 1000

            return ConnectionHealthResult(
                is_healthy=True,
                latency_ms=round(latency, 2),
                server_version=f"MongoDB {version_str}",
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
            client.close()

    async def introspect_schema(self) -> DatabaseMetadata:
        uri = self._build_connection_string()
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        db_name = self.config.get("database_name", "test")

        try:
            db = client[db_name]
            collection_names = await db.list_collection_names()
            server_info = await client.server_info()
            version_str = server_info.get("version", "MongoDB")

            tables: List[TableMetadata] = []
            total_columns = 0

            for coll_name in collection_names:
                collection = db[coll_name]
                doc_count = await collection.estimated_document_count()

                # Sample up to 10 documents and merge all field names to handle
                # schema drift in schemaless collections (fix #7: single doc was insufficient).
                pipeline = [{"$sample": {"size": 10}}]
                sample_docs = await collection.aggregate(pipeline).to_list(length=10)

                merged_fields: Dict[str, str] = {}
                for doc in sample_docs:
                    for field_name, value in doc.items():
                        if field_name not in merged_fields:
                            merged_fields[field_name] = type(value).__name__

                columns: List[ColumnMetadata] = [
                    ColumnMetadata(
                        name=field_name,
                        data_type=b_type,
                        native_type=b_type,
                        is_primary_key=(field_name == "_id"),
                    )
                    for field_name, b_type in merged_fields.items()
                ]
                total_columns += len(columns)

                tables.append(
                    TableMetadata(
                        schema_name=db_name,
                        table_name=coll_name,
                        table_type="collection",
                        estimated_rows=doc_count,
                        columns=columns,
                    )
                )

            return DatabaseMetadata(
                database_name=db_name,
                server_version=f"MongoDB {version_str}",
                schemas=[db_name],
                tables=tables,
                total_tables=len(tables),
                total_columns=total_columns,
            )
        finally:
            client.close()

    async def get_table_sample(
        self, table_name: str, schema_name: str = "public", limit: int = 10
    ) -> List[Dict[str, Any]]:
        uri = self._build_connection_string()
        client = AsyncIOMotorClient(uri)
        db_name = self.config.get("database_name", "test")

        try:
            collection = client[db_name][table_name]
            cursor = collection.find().limit(limit)
            docs = await cursor.to_list(length=limit)

            for doc in docs:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
            return docs
        finally:
            client.close()

    async def stream_table_data(
        self, table_name: str, schema_name: str = "public", chunk_size: int = 10000
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        uri = self._build_connection_string()
        client = AsyncIOMotorClient(uri)
        db_name = self.config.get("database_name", "test")

        try:
            collection = client[db_name][table_name]
            cursor = collection.find(batch_size=chunk_size)

            batch: List[Dict[str, Any]] = []
            async for doc in cursor:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                batch.append(doc)

                if len(batch) >= chunk_size:
                    yield batch
                    batch = []

            if batch:
                yield batch
        finally:
            client.close()
