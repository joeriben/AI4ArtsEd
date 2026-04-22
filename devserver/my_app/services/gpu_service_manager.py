"""
GPU Service Manager — ensures GPU service (port 17803) is running.

Analog zu ComfyUIManager, aber SYNC, weil LLMClient (Haupt-Caller) sync ist.
Auto-startet 2_start_gpu_service.sh via subprocess.Popen, wenn /api/health fehlschlägt.
Kein sudo, kein systemd-Zwang — Fremdrechner-deploybar.
"""

import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class GPUServiceManager:
    def __init__(self):
        try:
            from config import (
                GPU_SERVICE_URL,
                GPU_SERVICE_AUTO_START,
                GPU_SERVICE_STARTUP_TIMEOUT,
                GPU_SERVICE_HEALTH_CHECK_INTERVAL,
                BASE_DIR,
            )
            self._base_url = GPU_SERVICE_URL.rstrip('/')
            self._auto_start_enabled = GPU_SERVICE_AUTO_START
            self._startup_timeout = GPU_SERVICE_STARTUP_TIMEOUT
            self._health_check_interval = GPU_SERVICE_HEALTH_CHECK_INTERVAL
            self._base_dir = Path(BASE_DIR)
        except ImportError as e:
            logger.error(f"[GPU-MANAGER] Config import failed: {e}")
            self._base_url = "http://localhost:17803"
            self._auto_start_enabled = True
            self._startup_timeout = 180
            self._health_check_interval = 2.0
            self._base_dir = Path(__file__).parent.parent.parent.parent

        self._startup_lock = threading.Lock()
        self._is_starting = False

    def is_healthy(self) -> bool:
        """GET /api/health — breit (VRAM-Coordinator deckt alle Backends ab)."""
        try:
            resp = requests.get(f"{self._base_url}/api/health", timeout=3)
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"[GPU-MANAGER] Health check failed: {e}")
            return False

    def is_starting(self) -> bool:
        return self._is_starting

    def ensure_gpu_service_available(self) -> bool:
        """Main entry. Double-check locking — other threads may be mid-start."""
        if self.is_healthy():
            return True

        if not self._auto_start_enabled:
            logger.warning("[GPU-MANAGER] Auto-start disabled, GPU service unavailable")
            return False

        with self._startup_lock:
            if self.is_healthy():
                logger.info("[GPU-MANAGER] Another thread started GPU service")
                return True

            logger.warning("[GPU-MANAGER] GPU service down, starting...")
            return self._start_gpu_service()

    def _start_gpu_service(self) -> bool:
        script_path = self._base_dir / "2_start_gpu_service.sh"
        if not script_path.exists():
            logger.error(f"[GPU-MANAGER] Startup script not found: {script_path}")
            return False

        self._is_starting = True
        try:
            logger.info(f"[GPU-MANAGER] Spawning: {script_path}")
            process = subprocess.Popen(
                [str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=script_path.parent,
                start_new_session=True,
            )
            logger.info(f"[GPU-MANAGER] Started PID={process.pid}, waiting for ready...")
            return self._wait_for_ready()
        except Exception as e:
            logger.error(f"[GPU-MANAGER] Start failed: {e}")
            return False
        finally:
            self._is_starting = False

    def _wait_for_ready(self) -> bool:
        start = time.time()
        logger.info(f"[GPU-MANAGER] Waiting for GPU service (timeout: {self._startup_timeout}s)...")
        while True:
            elapsed = time.time() - start
            if elapsed > self._startup_timeout:
                logger.error(f"[GPU-MANAGER] Startup timeout after {self._startup_timeout}s")
                return False
            if self.is_healthy():
                logger.info(f"[GPU-MANAGER] GPU service ready (took {elapsed:.1f}s)")
                return True
            logger.debug(f"[GPU-MANAGER] Still waiting... ({elapsed:.1f}s elapsed)")
            time.sleep(self._health_check_interval)


_gpu_service_manager: Optional[GPUServiceManager] = None


def get_gpu_service_manager() -> GPUServiceManager:
    """Singleton accessor."""
    global _gpu_service_manager
    if _gpu_service_manager is None:
        _gpu_service_manager = GPUServiceManager()
    return _gpu_service_manager
