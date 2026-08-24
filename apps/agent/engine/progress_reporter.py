"""
HTTP backend progress reporter module for agent execution engine.
"""

import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger("docker-agent-execution")


class ProgressReporter:
    """Sends HTTP progress reports to Control Plane POST /api/v1/executions/{id}/progress."""

    @staticmethod
    def report(
        backend_url: str,
        agent_token: str,
        job_id: str,
        status: str,
        progress: float,
        processed_rows: int,
        successful_rows: int,
        failed_rows: int,
        skipped_rows: int = 0,
        total_rows: int = 0,
        current_table: Optional[str] = None,
        current_stage: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        url = f"{backend_url.rstrip('/')}/api/v1/executions/{job_id}/progress"
        payload = json.dumps({
            "status": status,
            "progress": progress,
            "processed_rows": processed_rows,
            "successful_rows": successful_rows,
            "failed_rows": failed_rows,
            "skipped_rows": skipped_rows,
            "total_rows": total_rows,
            "current_table": current_table,
            "current_stage": current_stage,
            "error_message": error_message,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Token": agent_token,
            },
            method="POST",
        )
        if not backend_url or "testserver" in backend_url:
            return

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status not in (200, 201):
                    logger.warning(f"Progress report update returned HTTP status {resp.status} for job '{job_id}'.")
        except urllib.error.HTTPError as http_err:
            logger.error(f"Progress report failed for job '{job_id}' with HTTP status {http_err.code}: {http_err.reason}")
        except Exception as exc:
            logger.warning(f"Could not transmit progress report for job '{job_id}': {exc}")
