"""
LLM Watchdog — Self-healing for llama-server failures.

When the circuit breaker trips (llama-server unreachable), the watchdog
attempts to restart via systemctl. Requires passwordless sudo
for the llama-server service.

Setup (one-time, as root):
    echo "USERNAME ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart llama-server, \\
    /usr/bin/systemctl start llama-server, /usr/bin/systemctl stop llama-server" \\
    | sudo tee /etc/sudoers.d/ai4artsed-llama-server
"""

import logging
import subprocess
import time
import threading

import requests

logger = logging.getLogger(__name__)

# Restart cooldown: max 1 restart attempt per 5 minutes
_RESTART_COOLDOWN_SECONDS = 300
_RESTART_TIMEOUT_SECONDS = 15
_HEALTH_CHECK_INTERVAL = 2.0
_HEALTH_CHECK_MAX_WAIT = 30.0

_last_restart_attempt = 0.0
_restart_lock = threading.Lock()

# Systemd service name for llama-server
_SERVICE_NAME = "llama-server"


def _llm_healthy(base_url: str) -> bool:
    """Quick health check — can llama-server respond?"""
    try:
        resp = requests.get(f"{base_url}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _can_restart() -> bool:
    """Check if enough time has passed since the last restart attempt."""
    return (time.time() - _last_restart_attempt) >= _RESTART_COOLDOWN_SECONDS


def attempt_restart() -> bool:
    """
    Attempt to restart llama-server via systemctl.

    Returns True if llama-server is healthy after the restart attempt.
    Returns False if restart failed or is on cooldown.

    Thread-safe: only one restart attempt at a time.
    """
    global _last_restart_attempt

    if not _restart_lock.acquire(blocking=False):
        logger.info("[LLM-WATCHDOG] Restart already in progress, skipping")
        return False

    try:
        if not _can_restart():
            remaining = _RESTART_COOLDOWN_SECONDS - (time.time() - _last_restart_attempt)
            logger.info(f"[LLM-WATCHDOG] Restart on cooldown ({remaining:.0f}s remaining)")
            return False

        _last_restart_attempt = time.time()
        logger.warning(f"[LLM-WATCHDOG] Attempting {_SERVICE_NAME} restart via systemctl...")

        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", _SERVICE_NAME],
                capture_output=True,
                text=True,
                timeout=_RESTART_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            logger.warning("[LLM-WATCHDOG] systemctl not found — not a systemd system")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"[LLM-WATCHDOG] systemctl restart timed out after "
                         f"{_RESTART_TIMEOUT_SECONDS}s")
            return False

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "password" in stderr.lower() or "sudo" in stderr.lower():
                logger.warning(
                    f"[LLM-WATCHDOG] sudo requires password — passwordless rule not configured. "
                    f"Setup: echo 'USERNAME ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart {_SERVICE_NAME}' "
                    f"| sudo tee /etc/sudoers.d/ai4artsed-llama-server"
                )
            else:
                logger.error(f"[LLM-WATCHDOG] systemctl restart failed: {stderr}")
            return False

        logger.info("[LLM-WATCHDOG] systemctl restart succeeded, waiting for health...")

        from config import LLAMA_SERVER_URL
        base_url = LLAMA_SERVER_URL.rstrip('/')

        start = time.time()
        while (time.time() - start) < _HEALTH_CHECK_MAX_WAIT:
            if _llm_healthy(base_url):
                duration = time.time() - start
                logger.info(f"[LLM-WATCHDOG] llama-server healthy after {duration:.1f}s")
                return True
            time.sleep(_HEALTH_CHECK_INTERVAL)

        logger.error(f"[LLM-WATCHDOG] llama-server not healthy after {_HEALTH_CHECK_MAX_WAIT}s")
        return False

    finally:
        _restart_lock.release()
