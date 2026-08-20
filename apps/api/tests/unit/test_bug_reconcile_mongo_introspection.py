"""
Unit test for Fix 10: Reconcile the two divergent Mongo introspection implementations.
Verifies that both AgentMetadataEngine._introspect_mongodb and MongoDBConnector.introspect_schema
produce matching sets of flattened field paths for nested Mongo documents.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3].parent
API_DIR = REPO_ROOT / "apps" / "api"
AGENT_DIR = REPO_ROOT / "apps" / "agent"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from metadata_engine import AgentMetadataEngine
from app.modules.sources.sources_connectors.sources_connectors_mongodb import MongoDBConnector


@pytest.mark.asyncio
async def test_reconciled_mongo_introspection_produces_identical_flattened_field_paths():
    """
    Verifies that both agent-side and server-side Mongo connectors discover identical depth-3 flattened paths.
    """
    mock_docs = [
        {
            "_id": "1001",
            "name": "Acme Corp",
            "address": {
                "street": "123 Main St",
                "city": "Metropolis",
                "zip": "10001",
            },
            "orders": [{"item": "Widget A", "qty": 5}],
        }
    ]

    expected_paths = {"_id", "name", "address", "address.street", "address.city", "address.zip", "orders", "orders.item", "orders.qty"}

    # 1. Test Agent-side AgentMetadataEngine._introspect_mongodb
    mock_coll = MagicMock()
    mock_coll.estimated_document_count.return_value = 1
    mock_coll.find.return_value.limit.return_value = mock_docs

    mock_db = MagicMock()
    mock_db.list_collection_names.return_value = ["customers"]
    mock_db.__getitem__.return_value = mock_coll

    class MockPyMongoClient:
        def __init__(self, *args, **kwargs):
            pass

        def __getitem__(self, item):
            return mock_db

        def close(self):
            pass

    with patch("pymongo.MongoClient", MockPyMongoClient):
        agent_res = AgentMetadataEngine._introspect_mongodb("src_mongo", "mongodb://localhost:27017/test_db")
        assert agent_res is not None
        agent_cols = {c["column_name"] for c in agent_res["tables"][0]["columns"]}
        assert agent_cols == expected_paths

    # 2. Test API-side MongoDBConnector.introspect_schema
    connector = MongoDBConnector({"database_name": "test_db", "host": "localhost", "port": 27017})

    class MockMotorCursor:
        async def to_list(self, length=100):
            return mock_docs

    class MockMotorCollection:
        def aggregate(self, pipeline):
            return MockMotorCursor()

        async def estimated_document_count(self):
            return 1

    class MockMotorDB:
        async def list_collection_names(self):
            return ["customers"]

        def __getitem__(self, item):
            return MockMotorCollection()

    class MockMotorClient:
        def __init__(self, *args, **kwargs):
            pass

        def __getitem__(self, item):
            return MockMotorDB()

        async def server_info(self):
            return {"version": "7.0.0"}

        def close(self):
            pass

    with patch("app.modules.sources.sources_connectors.sources_connectors_mongodb.AsyncIOMotorClient", MockMotorClient):
        api_res = await connector.introspect_schema()
        assert api_res is not None
        api_cols = {c.name for c in api_res.tables[0].columns}
        assert api_cols == expected_paths
