"""
VRAM Monitor — consolidated view of GPU memory usage across backends.

DevServer orchestrates GPU Service (LLM + media generation).
This module provides a unified view of VRAM usage for both, enabling
future VRAM budget management (Phase 4B).
"""

import logging
from typing import Dict, Any, List, Optional

import requests

logger = logging.getLogger(__name__)


class VRAMMonitor:
    """Monitors VRAM usage across the GPU Service (diffusers, heartmula, in-process LLM)."""

    def __init__(self):
        from config import GPU_SERVICE_URL
        self.gpu_url = GPU_SERVICE_URL.rstrip('/')
        self.llm_url = self.gpu_url + '/api/llm'

    def get_llm_models(self) -> List[Dict[str, Any]]:
        """GET /api/llm/models → list of loaded LLM models."""
        try:
            resp = requests.get(f"{self.llm_url}/models", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for name in data.get("loaded", []):
                models.append({
                    "name": name,
                    "vram_mb": 0,
                    "size_mb": 0,
                    "status": "loaded",
                })
            return models
        except Exception as e:
            logger.debug(f"[VRAM-MONITOR] LLM /models failed: {e}")
            return []

    def get_gpu_service_status(self) -> Dict[str, Any]:
        """GET /api/health → GPU service health and loaded models."""
        try:
            resp = requests.get(f"{self.gpu_url}/api/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"[VRAM-MONITOR] GPU service /api/health failed: {e}")
            return {"reachable": False, "error": str(e)}

    def get_combined_status(self) -> Dict[str, Any]:
        """Consolidated VRAM view across both backends."""
        llm_models = self.get_llm_models()
        gpu_status = self.get_gpu_service_status()

        return {
            "llm_server": {
                "reachable": len(llm_models) > 0 or self._llm_reachable(),
                "models": llm_models,
            },
            "gpu_service": {
                "reachable": gpu_status.get("status") in ("ok", "healthy"),
                "raw": gpu_status,
            },
        }

    def _llm_reachable(self) -> bool:
        """Quick reachability check for the GPU Service LLM endpoint."""
        try:
            resp = requests.get(f"{self.llm_url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


# Module-level singleton
_monitor: Optional[VRAMMonitor] = None


def get_vram_monitor() -> VRAMMonitor:
    """Get VRAMMonitor singleton."""
    global _monitor
    if _monitor is None:
        _monitor = VRAMMonitor()
    return _monitor
