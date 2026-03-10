"""
Ollama LLM Client — Direct HTTP wrapper for Ollama inference.

All LLM inference (safety verification, prompt interception, chat)
goes directly to Ollama. GPU Service handles media inference only.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMClient:
    """Ollama client for LLM inference."""

    def __init__(self):
        from config import OLLAMA_API_BASE_URL
        self.ollama_url = OLLAMA_API_BASE_URL.rstrip('/')
        logger.info(f"[LLM-CLIENT] Initialized: ollama={self.ollama_url}")

    def _ollama_chat(self, model: str, messages: list, images: Optional[list] = None,
                     temperature: float = 0.7, max_new_tokens: int = 500,
                     keep_alive: str = "10m",
                     repetition_penalty: Optional[float] = None,
                     enable_thinking: bool = True,
                     timeout: int = 120) -> Optional[Dict[str, Any]]:
        """Ollama chat endpoint."""
        import requests

        # Strip local/ prefix for Ollama
        ollama_model = model.replace("local/", "") if model.startswith("local/") else model

        # Inject images into first user message if provided
        ollama_messages = []
        for msg in messages:
            m = dict(msg)
            if images and m.get("role") == "user" and not any("images" in prev for prev in ollama_messages):
                m["images"] = images
            ollama_messages.append(m)

        options = {"temperature": temperature, "num_predict": max_new_tokens}
        if repetition_penalty is not None:
            options["repeat_penalty"] = repetition_penalty

        payload = {
            "model": ollama_model,
            "messages": ollama_messages,
            "stream": False,
            "keep_alive": keep_alive,
            "options": options,
        }
        # Ollama Qwen3 thinking suppression
        if not enable_thinking:
            payload["think"] = False
            logger.debug(f"[LLM-CLIENT] Thinking disabled for {ollama_model}, payload has think={payload.get('think')}")

        try:
            resp = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=timeout)
            resp.raise_for_status()
            msg = resp.json().get("message", {})
            return {
                "content": msg.get("content", "").strip(),
                "thinking": msg.get("thinking", "").strip() or None,
            }
        except Exception as e:
            logger.error(f"[LLM-CLIENT] Ollama chat failed ({ollama_model}): {e}")
            return None

    def _ollama_generate(self, model: str, prompt: str,
                         temperature: float = 0.7, max_new_tokens: int = 500,
                         keep_alive: str = "10m",
                         repetition_penalty: Optional[float] = None,
                         enable_thinking: bool = True,
                         timeout: int = 120) -> Optional[Dict[str, Any]]:
        """Ollama generate endpoint."""
        import requests

        ollama_model = model.replace("local/", "") if model.startswith("local/") else model

        options = {"temperature": temperature, "num_predict": max_new_tokens}
        if repetition_penalty is not None:
            options["repeat_penalty"] = repetition_penalty

        payload = {
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "options": options,
        }
        if not enable_thinking:
            payload["think"] = False

        try:
            resp = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
            return {
                "response": resp.json().get("response", "").strip(),
                "thinking": None,
            }
        except Exception as e:
            logger.error(f"[LLM-CLIENT] Ollama generate failed ({ollama_model}): {e}")
            return None

    # =========================================================================
    # Public API
    # =========================================================================

    def chat(self, model: str, messages: list, images: Optional[list] = None,
             temperature: float = 0.7, max_new_tokens: int = 500,
             keep_alive: str = "10m",
             repetition_penalty: Optional[float] = None,
             enable_thinking: bool = True,
             timeout: int = 120) -> Optional[Dict[str, Any]]:
        """Messages-based chat via Ollama.

        Returns {"content": str, "thinking": str|None} or None on failure.
        """
        return self._ollama_chat(model, messages, images, temperature, max_new_tokens,
                                 keep_alive, repetition_penalty, enable_thinking, timeout)

    def generate(self, model: str, prompt: str,
                 temperature: float = 0.7, max_new_tokens: int = 500,
                 keep_alive: str = "10m",
                 repetition_penalty: Optional[float] = None,
                 enable_thinking: bool = True,
                 timeout: int = 120) -> Optional[Dict[str, Any]]:
        """Raw prompt generation via Ollama.

        Returns {"response": str, "thinking": str|None} or None on failure.
        """
        return self._ollama_generate(model, prompt, temperature, max_new_tokens,
                                     keep_alive, repetition_penalty, enable_thinking, timeout)
