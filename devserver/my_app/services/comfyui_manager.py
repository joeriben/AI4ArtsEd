"""
ComfyUI Manager — Process lifecycle management

Architecture:
    - Health check via GET /system_stats on ComfyUI port
    - Auto-start via 2_start_comfyui.sh startup script
    - Singleton with double-check locking
"""

import asyncio
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ComfyUIManager:
    """Manages ComfyUI lifecycle: startup, health checks, auto-recovery.

    Design Pattern: Singleton with lazy initialization.
    Thread Safety: asyncio.Lock for concurrent startup attempts.
    """

    def __init__(self):
        try:
            from config import (
                COMFYUI_PORT,
                COMFYUI_AUTO_START,
                COMFYUI_STARTUP_TIMEOUT,
                COMFYUI_HEALTH_CHECK_INTERVAL,
                BASE_DIR,
            )
            self.comfyui_port = int(COMFYUI_PORT)
            self._auto_start_enabled = COMFYUI_AUTO_START
            self._startup_timeout = COMFYUI_STARTUP_TIMEOUT
            self._health_check_interval = COMFYUI_HEALTH_CHECK_INTERVAL
            self._base_dir = BASE_DIR

        except ImportError as e:
            logger.error(f"[COMFYUI-MANAGER] Failed to import config: {e}")
            self.comfyui_port = 17804
            self._auto_start_enabled = True
            self._startup_timeout = 120
            self._health_check_interval = 2.0
            self._base_dir = Path(__file__).parent.parent.parent.parent

        # Concurrency control
        self._startup_lock = asyncio.Lock()
        self._is_starting = False

        logger.info(
            f"[COMFYUI-MANAGER] Initialized (port={self.comfyui_port}, "
            f"auto_start={self._auto_start_enabled})"
        )

    async def ensure_comfyui_available(self) -> bool:
        """Ensure ComfyUI is running, start if needed.

        Main entry point for all services needing ComfyUI.

        Returns:
            True if ComfyUI is available, False otherwise.
        """
        # Quick health check (no lock)
        if await self.is_healthy():
            return True

        if not self._auto_start_enabled:
            logger.warning("[COMFYUI-MANAGER] Auto-start disabled, ComfyUI not available")
            return False

        # Acquire lock (prevent multiple threads starting)
        async with self._startup_lock:
            # Double-check after lock
            if await self.is_healthy():
                logger.info("[COMFYUI-MANAGER] Another thread started ComfyUI")
                return True

            logger.warning("[COMFYUI-MANAGER] ComfyUI not available, starting...")
            return await self._start_comfyui()

    async def is_healthy(self) -> bool:
        """Check if ComfyUI is responsive via GET /system_stats."""
        try:
            from my_app.services.comfyui_ws_client import get_comfyui_ws_client
            client = get_comfyui_ws_client()
            return await client.health_check()
        except Exception as e:
            logger.debug(f"[COMFYUI-MANAGER] Health check failed: {e}")
            return False

    async def _start_comfyui(self) -> bool:
        """Execute startup script and wait for ready state."""
        try:
            self._is_starting = True

            script_path = self._get_startup_script_path()
            if not script_path.exists():
                logger.error(f"[COMFYUI-MANAGER] Startup script not found: {script_path}")
                logger.error("[COMFYUI-MANAGER] Please start ComfyUI manually")
                return False

            logger.info(f"[COMFYUI-MANAGER] Starting ComfyUI via: {script_path}")

            process = subprocess.Popen(
                [str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=script_path.parent,
                start_new_session=True,
            )

            logger.info(f"[COMFYUI-MANAGER] ComfyUI process started (PID: {process.pid})")

            return await self._wait_for_ready()

        except Exception as e:
            logger.error(f"[COMFYUI-MANAGER] Startup failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._is_starting = False

    async def _wait_for_ready(self) -> bool:
        """Poll health endpoint until ready or timeout."""
        start_time = time.time()
        logger.info(
            f"[COMFYUI-MANAGER] Waiting for ComfyUI (timeout: {self._startup_timeout}s)..."
        )

        while True:
            elapsed = time.time() - start_time

            if elapsed > self._startup_timeout:
                logger.error(f"[COMFYUI-MANAGER] Startup timeout after {self._startup_timeout}s")
                return False

            if await self.is_healthy():
                logger.info(f"[COMFYUI-MANAGER] ComfyUI ready! (took {elapsed:.1f}s)")
                return True

            logger.debug(f"[COMFYUI-MANAGER] Still waiting... ({elapsed:.1f}s elapsed)")
            await asyncio.sleep(self._health_check_interval)

    def _get_startup_script_path(self) -> Path:
        """Resolve path to 2_start_comfyui.sh."""
        return self._base_dir / "2_start_comfyui.sh"

    def is_starting(self) -> bool:
        """Check if ComfyUI is currently in startup process."""
        return self._is_starting


# Singleton
_comfyui_manager: Optional[ComfyUIManager] = None


def get_comfyui_manager() -> ComfyUIManager:
    """Get singleton ComfyUI Manager instance."""
    global _comfyui_manager
    if _comfyui_manager is None:
        _comfyui_manager = ComfyUIManager()
    return _comfyui_manager
