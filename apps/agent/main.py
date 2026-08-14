import json
import logging
import os
import sys
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


def main():
    logger.info("Initializing Docker Agent process...")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    agent_token = os.getenv("AGENT_TOKEN", "")
    version = os.getenv("AGENT_VERSION", "1.0.0")

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
