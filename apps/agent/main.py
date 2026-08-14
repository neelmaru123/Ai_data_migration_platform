import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import os
import re
import signal
import socket
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("docker-agent")


def _mask_url(url_val: str) -> str:
    """Masks password in connection URLs for safe logging, highlighting unfilled placeholders."""
    if "<" in url_val and ">" in url_val:
        return f"{url_val} [WARNING: Unfilled credential placeholder detected]"
    return re.sub(r":([^:@]+)@", r":***@", url_val)


def extract_identifier_from_env_key(env_key: str) -> str:
    """
    Extracts the clean data source identifier from environment variable name.
    e.g. 'SRC_PG_PRIMARY_URL' -> 'pg_primary'
    e.g. 'DEST_MYSQL_WAREHOUSE_URL' -> 'mysql_warehouse'
    e.g. 'SOURCE_DB_URL' -> 'source_db'
    """
    k = env_key.upper()
    if k.endswith("_URL"):
        k = k[:-4]
    elif k.endswith("_URI"):
        k = k[:-4]

    if k.startswith("SRC_"):
        k = k[4:]
    elif k.startswith("DEST_"):
        k = k[5:]
    return k.lower()


def test_database_connection(identifier: str, url_val: str) -> Dict[str, Any]:
    """
    Tests network reachability, socket connection, and credential completeness for a database URL.
    Returns structured diagnostic health result with actionable troubleshooting advice.
    """
    if not url_val or not url_val.strip():
        return {
            "identifier": identifier,
            "is_healthy": False,
            "error_type": "MissingConfiguration",
            "error_message": f"Connection URL for '{identifier}' is empty.",
            "latency_ms": 0.0,
        }

    # 1. Detect unfilled placeholders (e.g. <password>, <username>, <database_name>)
    if "<" in url_val and ">" in url_val:
        return {
            "identifier": identifier,
            "is_healthy": False,
            "error_type": "UnfilledPlaceholder",
            "error_message": (
                f"Unfilled credential placeholder detected in database URL for '{identifier}'. "
                "Please replace placeholders (e.g. <password>, <username>) with your actual database credentials."
            ),
            "latency_ms": 0.0,
        }

    # 2. Parse URL components
    try:
        parsed = urllib.parse.urlparse(url_val)
        scheme = parsed.scheme.lower() if parsed.scheme else "unknown"
        hostname = parsed.hostname or "localhost"
        db_name = parsed.path.lstrip("/") if parsed.path else None

        default_ports = {
            "postgresql": 5432,
            "postgres": 5432,
            "mysql": 3306,
            "mariadb": 3306,
            "mongodb": 27017,
            "mongodb+srv": 27017,
        }
        port = parsed.port or default_ports.get(scheme, 5432)
    except Exception as parse_err:
        return {
            "identifier": identifier,
            "is_healthy": False,
            "error_type": "InvalidUrlFormat",
            "error_message": f"Could not parse database URL: {parse_err}",
            "latency_ms": 0.0,
        }

    # 3. Test TCP socket reachability with timeout
    t0 = time.perf_counter()
    try:
        sock = socket.create_connection((hostname, port), timeout=3.5)
        sock.close()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "identifier": identifier,
            "is_healthy": True,
            "error_type": None,
            "error_message": None,
            "latency_ms": latency_ms,
            "database_name": db_name,
        }
    except (socket.timeout, TimeoutError):
        return {
            "identifier": identifier,
            "is_healthy": False,
            "error_type": "TimeoutError",
            "error_message": f"Connection timed out reaching database host '{hostname}:{port}'.",
            "latency_ms": 0.0,
        }
    except ConnectionRefusedError:
        msg = f"Connection refused on {hostname}:{port}. Ensure your database server is running."
        if hostname in ("localhost", "127.0.0.1"):
            msg += (
                " Note: Inside a Docker container, 'localhost' refers to the container itself. "
                "Use 'host.docker.internal' instead to connect to a database on your host machine."
            )
        return {
            "identifier": identifier,
            "is_healthy": False,
            "error_type": "ConnectionRefused",
            "error_message": msg,
            "latency_ms": 0.0,
        }
    except socket.gaierror as dns_err:
        return {
            "identifier": identifier,
            "is_healthy": False,
            "error_type": "DnsResolutionFailed",
            "error_message": f"Could not resolve host '{hostname}': {dns_err}.",
            "latency_ms": 0.0,
        }
    except Exception as exc:
        return {
            "identifier": identifier,
            "is_healthy": False,
            "error_type": "NetworkError",
            "error_message": f"Could not connect to {hostname}:{port}: {exc}",
            "latency_ms": 0.0,
        }


def collect_data_sources_health() -> List[Dict[str, Any]]:
    """
    Scans environment for all configured database connection URLs and tests their health concurrently.
    Uses ThreadPoolExecutor to bound total execution time to ≤ 3.5s regardless of database count.
    Returns list of DataSourceHealthReport dicts.
    """
    items_to_test: List[tuple[str, str]] = []
    seen_identifiers = set()

    for k, v in os.environ.items():
        if (k.startswith("SRC_") or k.startswith("DEST_") or k in ("SOURCE_DB_URL", "DEST_DB_URL")) and (
            "URL" in k or "URI" in k
        ):
            raw_id = extract_identifier_from_env_key(k)
            if raw_id in seen_identifiers:
                continue
            seen_identifiers.add(raw_id)
            items_to_test.append((raw_id, v))

    if not items_to_test:
        return []

    reports: List[Dict[str, Any]] = []
    # Run socket health checks concurrently
    max_workers = min(len(items_to_test), 10)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_id = {
            executor.submit(test_database_connection, ident, url): ident
            for ident, url in items_to_test
        }
        for future in as_completed(future_to_id):
            try:
                report = future.result()
                reports.append(report)
            except Exception as exc:
                ident = future_to_id[future]
                reports.append({
                    "identifier": ident,
                    "is_healthy": False,
                    "error_type": "HealthCheckFailed",
                    "error_message": f"Unexpected health check error: {exc}",
                    "latency_ms": 0.0,
                })

    return reports


def send_heartbeat(
    backend_url: str,
    agent_token: str,
    version: str,
    override_status: Optional[str] = None,
) -> bool:
    """
    Sends periodic heartbeat ping and data source diagnostics to backend API.
    Computes status ('online', 'degraded', or 'offline') based on health checks or override.
    """
    url = f"{backend_url.rstrip('/')}/api/v1/agents/heartbeat"
    headers = {
        "Content-Type": "application/json",
        "X-Agent-Token": agent_token,
    }

    if override_status == "offline":
        ds_reports = None
        computed_status = "offline"
    else:
        # Collect latest connection diagnostics for all configured local databases concurrently
        ds_reports = collect_data_sources_health()
        if override_status:
            computed_status = override_status
        elif ds_reports:
            # If any configured DB is failing, mark agent status as 'degraded'
            all_healthy = all(r.get("is_healthy", False) for r in ds_reports)
            computed_status = "online" if all_healthy else "degraded"
        else:
            computed_status = "online"

    payload_data: Dict[str, Any] = {
        "status": computed_status,
        "version": version,
        "data_sources": ds_reports if ds_reports else None,
    }
    payload = json.dumps(payload_data).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                if computed_status == "offline":
                    logger.info(f"Offline status synced with backend (Agent ID: {body.get('id')}).")
                    return True

                healthy_count = sum(1 for r in (ds_reports or []) if r.get("is_healthy"))
                failing_count = len(ds_reports or []) - healthy_count
                logger.info(
                    f"Heartbeat synced [{computed_status.upper()}] (Agent ID: {body.get('id')}). "
                    f"Databases: {healthy_count} healthy, {failing_count} failing."
                )
                for r in (ds_reports or []):
                    if not r.get("is_healthy"):
                        logger.warning(f"  [!] DataSource '{r.get('identifier')}' unreachable: {r.get('error_message')}")
                return True
    except urllib.error.HTTPError as err:
        logger.error(f"Agent heartbeat failed with HTTP status {err.code}: {err.reason}")
    except Exception as exc:
        logger.error(f"Could not connect to backend at {url}: {exc}")

    return False


def log_configured_databases():
    """Scans and logs all configured source and destination database environments."""
    src_configs = {}
    dest_configs = {}

    for k, v in os.environ.items():
        if k.startswith("SRC_") or k == "SOURCE_DB_URL":
            src_configs[k] = _mask_url(v) if "URL" in k or "PASSWORD" in k else v
        elif k.startswith("DEST_") or k == "DEST_DB_URL":
            dest_configs[k] = _mask_url(v) if "URL" in k or "PASSWORD" in k else v

    if src_configs:
        logger.info("Configured Source Databases detected:")
        for k, v in src_configs.items():
            logger.info(f"  - {k}: {v}")
    else:
        logger.warning("No Source Database environment variables detected.")

    if dest_configs:
        logger.info("Configured Destination Databases detected:")
        for k, v in dest_configs.items():
            logger.info(f"  - {k}: {v}")
    else:
        logger.warning("No Destination Database environment variables detected.")


def graceful_shutdown(backend_url: str, agent_token: str, version: str):
    """Notifies the backend that the agent process is stopping."""
    logger.info("Sending offline notification to backend before shutdown...")
    try:
        send_heartbeat(backend_url, agent_token, version, override_status="offline")
    except Exception as exc:
        logger.warning(f"Could not send final offline heartbeat: {exc}")


def main():
    logger.info("Initializing Docker Agent process...")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    agent_token = os.getenv("AGENT_TOKEN", "")
    version = os.getenv("AGENT_VERSION", "1.0.0")
    run_once = os.getenv("AGENT_RUN_ONCE", "false").lower() == "true"
    interval = int(os.getenv("HEARTBEAT_INTERVAL", "20"))

    log_configured_databases()

    if not agent_token:
        logger.warning("AGENT_TOKEN environment variable not set. Agent running in unauthenticated mode.")
        return

    # Register graceful shutdown handlers
    is_shutting_down = False

    def signal_handler(signum, frame):
        nonlocal is_shutting_down
        if is_shutting_down:
            return
        is_shutting_down = True
        logger.info(f"Received termination signal ({signum}). Initiating graceful shutdown...")
        graceful_shutdown(backend_url, agent_token, version)
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except (ValueError, AttributeError):
        # Some signals may not be available on all OS/thread setups
        pass

    # Initial startup connection handshake with retry loop
    max_retries = 5
    backoff_seconds = 3
    connected = False

    for attempt in range(1, max_retries + 1):
        logger.info(f"Executing startup connection handshake with backend (attempt {attempt}/{max_retries})...")
        if send_heartbeat(backend_url, agent_token, version):
            connected = True
            break
        if attempt < max_retries:
            logger.warning(f"Handshake failed. Retrying in {backoff_seconds} seconds...")
            time.sleep(backoff_seconds)

    if not connected:
        logger.error(f"Agent startup handshake failed after {max_retries} attempts. Check backend logs and AGENT_TOKEN.")
        return

    logger.info("Agent process is online and securely connected to backend.")

    if run_once:
        logger.info("AGENT_RUN_ONCE is enabled. Exiting startup routine.")
        return

    # Continuous background heartbeat loop for automatic self-healing recovery
    logger.info(f"Starting continuous background health check loop (interval: {interval}s)...")
    try:
        while True:
            time.sleep(interval)
            success = send_heartbeat(backend_url, agent_token, version)
            if not success:
                logger.warning("Heartbeat failed in loop. Will retry sooner in 5 seconds...")
                time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Docker Agent process stopping on user signal.")
        graceful_shutdown(backend_url, agent_token, version)


if __name__ == "__main__":
    main()
