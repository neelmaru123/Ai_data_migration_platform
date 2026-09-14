"""
Resumable checkpointing module for agent execution engine.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("docker-agent-execution")

CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "/tmp")


class CheckpointManager:
    """Manages resumable checkpointing per table and per source to prevent restarting from zero on agent crash."""

    @staticmethod
    def get_checkpoint_path(
        job_id: str,
        table_name: str,
        source_identifier: Optional[str] = None,
        source_table: Optional[str] = None,
    ) -> str:
        tmp_dir = os.getenv("CHECKPOINT_DIR", "/tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        if source_identifier or source_table:
            src_id = (source_identifier or "default").replace("/", "_").replace("\\", "_")
            src_tbl = (source_table or "default").replace("/", "_").replace("\\", "_")
            return os.path.join(tmp_dir, f"checkpoint_{job_id}_{table_name}_{src_id}_{src_tbl}.json")
        return os.path.join(tmp_dir, f"checkpoint_{job_id}_{table_name}.json")

    @classmethod
    def get_last_offset(
        cls,
        job_id: str,
        table_name: str,
        source_identifier: Optional[str] = None,
        source_table: Optional[str] = None,
    ) -> int:
        path = cls.get_checkpoint_path(job_id, table_name, source_identifier, source_table)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_offset", 0)
            except Exception as exc:
                logger.warning(f"Could not read checkpoint file '{path}': {exc}")
                return 0

        # Backward compatibility for legacy checkpoint naming without source suffix
        legacy_path = os.path.join(os.getenv("CHECKPOINT_DIR", "/tmp"), f"checkpoint_{job_id}_{table_name}.json")
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_offset", 0)
            except Exception as exc:
                logger.warning(f"Could not read legacy checkpoint file '{legacy_path}': {exc}")
                return 0

        return 0

    @classmethod
    def save_checkpoint(
        cls,
        job_id: str,
        table_name: str,
        offset: int,
        rows_processed: int,
        source_identifier: Optional[str] = None,
        source_table: Optional[str] = None,
    ):
        path = cls.get_checkpoint_path(job_id, table_name, source_identifier, source_table)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "job_id": job_id,
                    "table_name": table_name,
                    "source_identifier": source_identifier,
                    "source_table": source_table,
                    "last_offset": offset,
                    "rows_processed": rows_processed,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as exc:
            logger.warning(f"Could not write checkpoint for table '{table_name}' source '{source_identifier}.{source_table}': {exc}")

    @classmethod
    def clear_job_checkpoints(cls, job_id: str):
        """Removes all checkpoint JSON files for a completed job."""
        tmp_dir = os.getenv("CHECKPOINT_DIR", "/tmp")
        if not os.path.exists(tmp_dir):
            return
        prefix = f"checkpoint_{job_id}_"
        try:
            for fname in os.listdir(tmp_dir):
                if fname.startswith(prefix) and fname.endswith(".json"):
                    fpath = os.path.join(tmp_dir, fname)
                    try:
                        os.remove(fpath)
                        logger.info(f"Cleaned up checkpoint file: {fname}")
                    except Exception as err:
                        logger.warning(f"Could not remove checkpoint file '{fpath}': {err}")
        except Exception as exc:
            logger.warning(f"Error scanning checkpoint directory '{tmp_dir}': {exc}")

    @classmethod
    def clear_table_checkpoints(cls, job_id: str, table_name: str):
        """
        Removes all per-source checkpoint files for a single target table.
        Used when a multi-source staging file was found missing/stale on resume
        (e.g. after a crash mid-merge), so every source for that table re-stages
        from offset 0 instead of skipping rows that no longer exist in a fresh
        staging database.
        """
        tmp_dir = os.getenv("CHECKPOINT_DIR", "/tmp")
        if not os.path.exists(tmp_dir):
            return
        prefix = f"checkpoint_{job_id}_{table_name}_"
        try:
            for fname in os.listdir(tmp_dir):
                if fname.startswith(prefix) and fname.endswith(".json"):
                    fpath = os.path.join(tmp_dir, fname)
                    try:
                        os.remove(fpath)
                        logger.info(f"Reset stale checkpoint file for re-staging: {fname}")
                    except Exception as err:
                        logger.warning(f"Could not remove checkpoint file '{fpath}': {err}")
        except Exception as exc:
            logger.warning(f"Error scanning checkpoint directory '{tmp_dir}': {exc}")
