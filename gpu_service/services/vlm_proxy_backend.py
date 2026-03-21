"""
VLM Chat Proxy Backend

Proxies Ollama VLM requests through the GPU service's VRAM coordinator.
Ensures vision model loads are coordinated with all other GPU backends
(Diffusers, HeartMuLa, etc.) to prevent VRAM conflicts.

Key behaviors:
- Before calling Ollama, requests VRAM from coordinator (triggers eviction if needed)
- Tracks which VLM is currently loaded (Ollama keeps one model hot)
- Unloads previous VLM via keep_alive=0 before loading a different one
- Reports loaded model to coordinator via VRAMBackend protocol
"""

import json
import logging
import time
import urllib.request
from typing import Any, Dict, List, Optional

import config
from services.vram_coordinator import EvictionPriority, get_vram_coordinator

logger = logging.getLogger(__name__)


class VLMProxyBackend:
    """VRAM-coordinated proxy for Ollama vision model requests."""

    def __init__(self):
        self._current_model: Optional[str] = None
        self._current_vram_mb: float = 0
        self._last_used: float = 0
        self._in_use: int = 0

        # Register with VRAM coordinator
        coordinator = get_vram_coordinator()
        coordinator.register_backend(self)
        logger.info("[VLM-PROXY] Backend registered with VRAM coordinator")

    def get_backend_id(self) -> str:
        return "vlm_proxy"

    def get_registered_models(self) -> List[Dict[str, Any]]:
        if not self._current_model:
            return []
        return [{
            "model_id": self._current_model,
            "vram_mb": self._current_vram_mb,
            "priority": EvictionPriority.NORMAL,
            "last_used": self._last_used,
            "in_use": self._in_use,
        }]

    def evict_model(self, model_id: str) -> bool:
        """Evict a VLM by telling Ollama to unload it."""
        if model_id != self._current_model:
            return False
        success = self._ollama_unload(model_id)
        if success:
            logger.info(f"[VLM-PROXY] Evicted {model_id}, freed ~{self._current_vram_mb}MB")
            self._current_model = None
            self._current_vram_mb = 0
        return success

    def chat(
        self,
        model: str,
        messages: list,
        images: Optional[list] = None,
        temperature: float = 0.7,
        max_new_tokens: int = 2000,
        enable_thinking: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        VRAM-coordinated VLM chat.

        1. If switching models: unload previous, request VRAM, load new
        2. Call Ollama /api/chat
        3. Track model state for coordinator
        """
        required_vram = config.VLM_VRAM_ESTIMATES.get(model, config.VLM_DEFAULT_VRAM_MB)

        # Model switch needed?
        if model != self._current_model:
            # Unload current model first
            if self._current_model:
                self._ollama_unload(self._current_model)
                logger.info(f"[VLM-PROXY] Unloaded {self._current_model}")
                self._current_model = None
                self._current_vram_mb = 0

            # Request VRAM from coordinator (may evict other backends)
            coordinator = get_vram_coordinator()
            if not coordinator.request_vram("vlm_proxy", required_vram, EvictionPriority.NORMAL):
                logger.warning(f"[VLM-PROXY] Could not secure {required_vram}MB for {model}, proceeding anyway")

        # Mark in-use
        self._in_use += 1
        self._last_used = time.time()

        try:
            result = self._ollama_chat(model, messages, images, temperature, max_new_tokens, enable_thinking)

            # Track loaded model
            self._current_model = model
            self._current_vram_mb = required_vram

            return result
        finally:
            self._in_use -= 1

    def _ollama_chat(
        self,
        model: str,
        messages: list,
        images: Optional[list],
        temperature: float,
        max_new_tokens: int,
        enable_thinking: bool,
    ) -> Optional[Dict[str, Any]]:
        """Direct Ollama /api/chat call."""
        import requests

        # Inject images into first user message
        ollama_messages = []
        for msg in messages:
            m = dict(msg)
            if images and m.get("role") == "user" and not any("images" in prev for prev in ollama_messages):
                m["images"] = images
            ollama_messages.append(m)

        options = {"temperature": temperature, "num_predict": max_new_tokens}
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "keep_alive": "10m",
            "options": options,
        }
        if not enable_thinking:
            payload["think"] = False

        try:
            resp = requests.post(
                f"{config.OLLAMA_API_URL}/api/chat",
                json=payload,
                timeout=config.VLM_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            msg = resp.json().get("message", {})
            return {
                "content": msg.get("content", "").strip(),
                "thinking": msg.get("thinking", "").strip() or None,
            }
        except Exception as e:
            logger.error(f"[VLM-PROXY] Ollama chat failed ({model}): {e}")
            return None

    def _ollama_unload(self, model: str) -> bool:
        """Tell Ollama to unload a model via keep_alive=0."""
        try:
            payload = json.dumps({
                "model": model,
                "keep_alive": 0,
            }).encode()
            req = urllib.request.Request(
                f"{config.OLLAMA_API_URL}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            return True
        except Exception as e:
            logger.warning(f"[VLM-PROXY] Failed to unload {model}: {e}")
            return False


# --- Singleton ---
_backend: Optional[VLMProxyBackend] = None


def get_vlm_proxy_backend() -> VLMProxyBackend:
    global _backend
    if _backend is None:
        _backend = VLMProxyBackend()
    return _backend
