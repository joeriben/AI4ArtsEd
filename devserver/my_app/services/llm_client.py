"""
LLM Client — HTTP wrapper for GPU Service LLM endpoints.

All local LLM inference (safety verification, DSGVO, VLM safety)
goes to the GPU Service's /api/llm/* endpoints.
Cloud LLM calls (Stage 1-3 interception) go through backend_router.
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for local LLM inference via GPU Service."""

    def __init__(self):
        from config import GPU_SERVICE_URL
        self.base_url = GPU_SERVICE_URL.rstrip('/')
        logger.info(f"[LLM-CLIENT] Initialized: gpu_service={self.base_url}")

    def _prepare_model_name(self, model: str) -> str:
        """Strip local/ prefix if present."""
        return model.replace("local/", "") if model.startswith("local/") else model

    def _chat(self, model: str, messages: list, images: Optional[List[str]] = None,
              temperature: float = 0.7, max_new_tokens: int = 500,
              repetition_penalty: Optional[float] = None,
              timeout: int = 120) -> Optional[Dict[str, Any]]:
        """Chat via GPU Service /api/llm/chat."""
        import requests

        model_name = self._prepare_model_name(model)

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_new_tokens,
        }
        if images:
            payload["images"] = images
        if repetition_penalty is not None:
            payload["repetition_penalty"] = repetition_penalty

        try:
            from my_app.services.gpu_service_manager import get_gpu_service_manager
            if not get_gpu_service_manager().ensure_gpu_service_available():
                logger.error(f"[LLM-CLIENT] GPU service unavailable at {self.base_url}")
                return None
            resp = requests.post(f"{self.base_url}/api/llm/chat", json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[LLM-CLIENT] Chat failed ({model_name}): {e}")
            return None

    def _generate(self, model: str, prompt: str,
                  temperature: float = 0.7, max_new_tokens: int = 500,
                  repetition_penalty: Optional[float] = None,
                  timeout: int = 120) -> Optional[Dict[str, Any]]:
        """Generate via GPU Service /api/llm/generate."""
        import requests

        model_name = self._prepare_model_name(model)

        payload = {
            "model": model_name,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_new_tokens,
        }
        if repetition_penalty is not None:
            payload["repetition_penalty"] = repetition_penalty

        try:
            from my_app.services.gpu_service_manager import get_gpu_service_manager
            if not get_gpu_service_manager().ensure_gpu_service_available():
                logger.error(f"[LLM-CLIENT] GPU service unavailable at {self.base_url}")
                return None
            resp = requests.post(f"{self.base_url}/api/llm/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[LLM-CLIENT] Generate failed ({model_name}): {e}")
            return None

    # =========================================================================
    # Public API (unchanged signatures for all callers)
    # =========================================================================

    def chat(self, model: str, messages: list, images: Optional[list] = None,
             temperature: float = 0.7, max_new_tokens: int = 500,
             keep_alive: str = "10m",
             repetition_penalty: Optional[float] = None,
             enable_thinking: bool = True,
             timeout: int = 120,
             tools: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """Messages-based chat.

        Returns {"content": str, "thinking": str|None, "tool_calls": list|None} or None on failure.

        Note: keep_alive, enable_thinking, tools are accepted for backward compatibility
        but ignored (llama-cpp-python does not support these legacy features).
        """
        return self._chat(model, messages, images, temperature, max_new_tokens,
                          repetition_penalty, timeout)

    def generate(self, model: str, prompt: str,
                 temperature: float = 0.7, max_new_tokens: int = 500,
                 keep_alive: str = "10m",
                 repetition_penalty: Optional[float] = None,
                 enable_thinking: bool = True,
                 timeout: int = 120) -> Optional[Dict[str, Any]]:
        """Raw prompt generation.

        Returns {"response": str, "thinking": str|None} or None on failure.

        Note: keep_alive and enable_thinking are accepted for backward compatibility
        but ignored.
        """
        return self._generate(model, prompt, temperature, max_new_tokens,
                              repetition_penalty, timeout)
