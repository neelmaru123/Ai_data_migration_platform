"""
Unit test for Fix 1: Multi-source merge checkpoint key isolation
Verifies that CheckpointManager and ExecutionOrchestrator isolate checkpoints per (job_id, target_table, source_identifier, source_table)
and correctly support backward compatibility with legacy checkpoint files.
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch
import polars as pl
import pytest

from pathlib import Path

# Locate repo root (test file is in apps/api/tests/unit/ -> 4 directories up is repo root)
REPO_ROOT = Path(__file__).resolve().parents[3].parent
AGENT_DIR = REPO_ROOT / "apps" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from execution_engine import CheckpointManager, ExecutionOrchestrator


def test_checkpoint_path_and_key_isolation():
    job_id = "job-test-123"
    target_table = "users_merged"
    src1_ident = "source_db_1"
    src1_table = "users_pg"
    src2_ident = "source_db_2"
    src2_table = "users_mysql"

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.dict(os.environ, {"CHECKPOINT_DIR": tmp_dir}):
            path1 = CheckpointManager.get_checkpoint_path(job_id, target_table, src1_ident, src1_table)
            path2 = CheckpointManager.get_checkpoint_path(job_id, target_table, src2_ident, src2_table)

            assert path1 != path2
            assert f"checkpoint_{job_id}_{target_table}_{src1_ident}_{src1_table}.json" in path1
            assert f"checkpoint_{job_id}_{target_table}_{src2_ident}_{src2_table}.json" in path2

            # Save checkpoint for source 1 (offset 100)
            CheckpointManager.save_checkpoint(job_id, target_table, offset=100, rows_processed=100, source_identifier=src1_ident, source_table=src1_table)

            # Assert source 1 offset is 100, while source 2 offset remains 0
            assert CheckpointManager.get_last_offset(job_id, target_table, src1_ident, src1_table) == 100
            assert CheckpointManager.get_last_offset(job_id, target_table, src2_ident, src2_table) == 0


def test_legacy_checkpoint_fallback():
    job_id = "job-legacy-999"
    target_table = "legacy_table"

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.dict(os.environ, {"CHECKPOINT_DIR": tmp_dir}):
            # Create a legacy checkpoint file (no source suffix)
            legacy_file = os.path.join(tmp_dir, f"checkpoint_{job_id}_{target_table}.json")
            with open(legacy_file, "w", encoding="utf-8") as f:
                json.dump({"job_id": job_id, "table_name": target_table, "last_offset": 450, "rows_processed": 450}, f)

            # Fetching offset with a specific source when per-source file doesn't exist should fall back to legacy offset
            offset = CheckpointManager.get_last_offset(job_id, target_table, "src_1", "tbl_1")
            assert offset == 450


def test_bug_multisource_checkpoint_key_isolation_execution():
    """
    Simulates ExecutionOrchestrator running 2 mocked sources into 1 target merge table.
    Verifies that source 1 ending at offset 50 does NOT force source 2 to start at offset 50.
    """
    job_id = "job-merge-crash-resume"
    target_table = "customers_unified"

    plan_ast = {
        "plan_data": {
            "pre_migration_ddl": [],
            "post_migration_ddl": [],
            "table_mappings": [
                {
                    "target_table_name": target_table,
                    "source_tables": [
                        {"identifier": "src_pg", "table_name": "users_pg"},
                        {"identifier": "src_mysql", "table_name": "users_mysql"},
                    ],
                    "column_mappings": [
                        {"target_column_name": "id", "transformation_type": "direct_copy", "source_columns": [{"column_name": "id"}]},
                        {"target_column_name": "name", "transformation_type": "direct_copy", "source_columns": [{"column_name": "name"}]},
                    ],
                    "conflict_resolution": {"deduplication_key": "id", "deduplication_strategy": "first_wins"},
                }
            ],
        }
    }

    source_db_urls = {"src_pg": "postgresql://localhost/pg", "src_mysql": "mysql://localhost/mysql"}
    target_db_url = "postgresql://localhost/target"

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.dict(os.environ, {"CHECKPOINT_DIR": tmp_dir}):
            # Pre-populate checkpoint for src_pg at offset 20 (it previously completed chunk 1 of 20 rows)
            CheckpointManager.save_checkpoint(job_id, target_table, offset=20, rows_processed=20, source_identifier="src_pg", source_table="users_pg")

            def mock_read_source_chunk(db_url, engine_type, table_or_file_name, offset=0, chunk_size=50000, pk_col=None, last_pk_val=None):
                if "users_pg" in table_or_file_name:
                    if offset == 20:
                        df = pl.DataFrame({"id": [21, 22], "name": ["Alice21", "Alice22"]})
                        return df, False, None
                    return pl.DataFrame(), False, None
                elif "users_mysql" in table_or_file_name:
                    if offset == 0:
                        # Should start at 0 even though src_pg was at offset 20!
                        df = pl.DataFrame({"id": [101, 102], "name": ["Bob101", "Bob102"]})
                        return df, False, None
                    return pl.DataFrame(), False, None
                return pl.DataFrame(), False, None

            with patch("execution_engine.DDLExecutor.execute_ddl_list"), \
                 patch("execution_engine.ProgressReporter.report"), \
                 patch("execution_engine.SourceConnectorFactory.read_source_chunk", side_effect=mock_read_source_chunk), \
                 patch("execution_engine.TargetWriterFactory.bulk_load", return_value=(4, 0, 0)) as mock_bulk_load:

                ExecutionOrchestrator.run_job(
                    backend_url="http://localhost:8000",
                    agent_token="token",
                    job_id=job_id,
                    plan_ast=plan_ast,
                    source_db_urls=source_db_urls,
                    target_db_url=target_db_url,
                )

                # Verify bulk_load was called and processed rows
                assert mock_bulk_load.called
                loaded_df = mock_bulk_load.call_args[0][3]
                assert len(loaded_df) == 4
                ids = loaded_df["id"].to_list()
                assert set(ids) == {21, 22, 101, 102}

                # Verify distinct checkpoint files were saved for both sources
                path_pg = CheckpointManager.get_checkpoint_path(job_id, target_table, "src_pg", "users_pg")
                path_mysql = CheckpointManager.get_checkpoint_path(job_id, target_table, "src_mysql", "users_mysql")

                assert os.path.exists(path_pg)
                assert os.path.exists(path_mysql)
                assert CheckpointManager.get_last_offset(job_id, target_table, "src_pg", "users_pg") == 22
                assert CheckpointManager.get_last_offset(job_id, target_table, "src_mysql", "users_mysql") == 2
