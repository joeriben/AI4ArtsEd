"""
VRAM Monitor — consolidated view of GPU memory usage across backends.

DevServer orchestrates both Ollama (LLM) and GPU Service (media generation).
This module provides a unified view of VRAM usage for both, enabling
future VRAM budget management (Phase 4B).
"""

import logging
from typing import Dict, Any, List, Optional

import requests

logger = logging.getLogger(__name__)


class VRAMMonitor:
    """Monitors VRAM usage across llama-server and GPU Service."""

    def __init__(self):
        from config import LLAMA_SERVER_URL, GPU_SERVICE_URL
        self.llm_url = LLAMA_SERVER_URL.rstrip('/')
        self.gpu_url = GPU_SERVICE_URL.rstrip('/')

    def get_llm_models(self) -> List[Dict[str, Any]]:
        """GET /models → list of loaded llama-server models."""
        try:
            resp = requests.get(f"{self.llm_url}/models", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data if isinstance(data, list) else data.get("data", []):
                models.append({
                    "name": m.get("id", m.get("name", "unknown")),
                    "vram_mb": 0,  # llama-server doesn't report per-model VRAM
                    "size_mb": 0,
                    "status": m.get("status", "unknown"),
                })
            return models
        except Exception as e:
            logger.debug(f"[VRAM-MONITOR] llama-server /models failed: {e}")
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
        """Quick reachability check for llama-server."""
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
