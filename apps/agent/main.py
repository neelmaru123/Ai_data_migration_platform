import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docker-agent")


def send_startup_handshake(backend_url: str, agent_token: str, version: str) -> bool:
    """
    Sends initial startup handshake / heartbeat ping to backend API
    using X-Agent-Token authentication header.
    Signals web application that agent container is live and online.
    """
    url = f"{backend_url.rstrip('/')}/api/v1/agents/heartbeat"
    headers = {
        "Content-Type": "application/json",
        "X-Agent-Token": agent_token,
    }
    payload = json.dumps({"status": "online", "version": version}).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                logger.info(f"Agent startup handshake successful! Agent ID: {body.get('id')}, Status: {body.get('status')}")
                return True
    except urllib.error.HTTPError as err:
        logger.error(f"Agent startup handshake failed with HTTP status {err.code}: {err.reason}")
    except Exception as exc:
        logger.error(f"Could not connect to backend at {url}: {exc}")

    return False


def _mask_url(url_val: str) -> str:
    """Masks password in connection URLs for safe logging, highlighting unfilled placeholders."""
    if "<" in url_val and ">" in url_val:
        return f"{url_val} [WARNING: Unfilled credential placeholder detected]"
    return re.sub(r":([^:@]+)@", r":***@", url_val)


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


def main():
    logger.info("Initializing Docker Agent process...")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    agent_token = os.getenv("AGENT_TOKEN", "")
    version = os.getenv("AGENT_VERSION", "1.0.0")

    log_configured_databases()

    if not agent_token:
        logger.warning("AGENT_TOKEN environment variable not set. Agent running in unauthenticated mode.")
    else:
        max_retries = 5
        backoff_seconds = 3
        success = False

        for attempt in range(1, max_retries + 1):
            logger.info(f"Executing startup connection handshake with backend (attempt {attempt}/{max_retries})...")
            if send_startup_handshake(backend_url, agent_token, version):
                success = True
                break
            if attempt < max_retries:
                logger.warning(f"Handshake failed. Retrying in {backoff_seconds} seconds...")
                time.sleep(backoff_seconds)

        if success:
            logger.info("Agent process is online and securely connected to backend.")
        else:
            logger.error(f"Agent startup handshake failed after {max_retries} attempts. Check backend logs and AGENT_TOKEN.")


if __name__ == "__main__":
    main()
