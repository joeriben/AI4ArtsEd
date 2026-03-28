"""
Service for high-level LLM interactions via GPU Service.

Translation, safety checks, image analysis — all routed through
GPU Service's /api/llm/* endpoints (llama-cpp-python in-process).
"""
import json
import logging
import requests
from typing import Dict, Optional, Any

from config import (
    GPU_SERVICE_URL,
    LLM_TIMEOUT,
    STAGE3_MODEL,
    SAFETY_MODEL,
    IMAGE_ANALYSIS_MODEL,
    ANALYSIS_SYSTEM_PROMPT,
    PROMPT_CACHE,
    TRANSLATION_PROMPT,
    NO_TRANSLATE,
)

logger = logging.getLogger(__name__)


class LLMService:
    """Service class for high-level LLM interactions via GPU Service."""

    def __init__(self):
        self.base_url = GPU_SERVICE_URL.rstrip('/')
        self.timeout = LLM_TIMEOUT
        logger.info(f"Initialized LLM service via GPU Service at {self.base_url}")

    def _chat(self, model: str, messages: list, images: list = None,
              temperature: float = 0.7, max_tokens: int = 512) -> Optional[Dict[str, Any]]:
        """Call GPU Service /api/llm/chat."""
        payload = {
            "model": model.replace("local/", "") if model.startswith("local/") else model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if images:
            payload["images"] = images

        try:
            response = requests.post(
                f"{self.base_url}/api/llm/chat",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM chat request failed: {e}")
            return None

    def _complete(self, model: str, prompt: str, system: str = "",
                  temperature: float = 0.7, max_tokens: int = 512) -> Optional[str]:
        """Generate text via GPU Service chat endpoint and return content string."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        result = self._chat(model, messages, temperature=temperature, max_tokens=max_tokens)
        if result:
            return result.get("content", "").strip()
        return None

    def _complete_with_image(self, model: str, prompt: str, image_b64: str,
                             system: str = "", temperature: float = 0.7,
                             max_tokens: int = 512) -> Optional[str]:
        """Generate text with image input via GPU Service VLM."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Pass images separately — GPU Service LLM backend handles injection
        images = [image_b64]

        result = self._chat(model, messages, images=images, temperature=temperature, max_tokens=max_tokens)
        if result:
            return result.get("content", "").strip()
        return None

    def translate_text(self, text: str) -> Optional[str]:
        """
        Translate text to English.

        Args:
            text: Text to translate

        Returns:
            Translated text or None if translation fails
        """
        prompt = TRANSLATION_PROMPT.format(text=text)
        return self._complete(STAGE3_MODEL, prompt)

    def check_safety(self, text: str) -> Dict[str, Any]:
        """
        Check if text is safe using safety model.

        Args:
            text: Text to check

        Returns:
            Dictionary with 'is_safe' boolean and optional 'reason' if unsafe
        """
        prompt = f"Is the following text safe? Please classify it. The text is:\n\n{text}"
        result = self._complete(SAFETY_MODEL, prompt)

        if not result:
            return {"is_safe": True, "note": "Safety check service failed, bypassing check."}

        if result.lower().strip().startswith("safe"):
            return {"is_safe": True}
        else:
            codes = [p.strip() for p in result.strip().split('\n')]
            return {
                "is_safe": False,
                "reason": f"Sorry, your prompt has been rejected due to potential issues: {', '.join(sorted(list(set(codes))))}"
            }

    def analyze_image(self, image_data: str) -> Optional[str]:
        """
        Analyze an image using vision model.

        Args:
            image_data: Base64 encoded image data

        Returns:
            Analysis text or None if analysis fails
        """
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',', 1)[-1]

        logger.info(f"Sending image to model: {IMAGE_ANALYSIS_MODEL}")
        result = self._complete_with_image(
            IMAGE_ANALYSIS_MODEL, "Analyze the image.", image_data,
            system=ANALYSIS_SYSTEM_PROMPT
        )
        if result:
            logger.info("Image analysis successful.")
        return result

    def validate_and_translate_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Validate and translate a prompt with caching.

        Args:
            prompt: Original prompt text

        Returns:
            Dictionary with 'success', 'translated_prompt', and optional 'error'
        """
        cache_key = prompt.strip().lower()

        # Check cache first
        if cache_key in PROMPT_CACHE:
            return {
                "success": True,
                "translated_prompt": PROMPT_CACHE[cache_key]["translated"],
                "cached": True
            }

        is_image_analysis = prompt.strip().startswith("Material and medial properties:")

        if NO_TRANSLATE:
            translated_prompt = prompt
            logger.info("Translation disabled by NO_TRANSLATE flag, using original prompt")
        elif is_image_analysis:
            translated_prompt = prompt
            logger.info("Skipping translation for image analysis prompt")
        else:
            translated_prompt = self.translate_text(prompt)
            if not translated_prompt:
                return {"success": False, "error": "Übersetzungs-Service fehlgeschlagen."}

        safety_result = self.check_safety(translated_prompt)
        if not safety_result["is_safe"]:
            return {"success": False, "error": safety_result.get("reason", "Prompt rejected for safety reasons.")}

        PROMPT_CACHE[cache_key] = {
            "translated": translated_prompt,
            "is_safe": True
        }
        logger.info(f"Cached new prompt: {cache_key[:50]}...")

        return {
            "success": True,
            "translated_prompt": translated_prompt,
            "cached": False
        }

    # ===== STREAMING METHODS =====

    def translate_text_stream(self, text: str):
        """
        Translate text to English, yielding the complete result as a single chunk.

        Note: GPU Service LLM backend does not support streaming yet.
        For small safety/translation models, response time is <1s anyway.
        """
        prompt = TRANSLATION_PROMPT.format(text=text)
        logger.info(f"Starting translation for text: {text[:50]}...")
        result = self._complete(STAGE3_MODEL, prompt)
        if result:
            yield result


# Singleton instance
llm_service = LLMService()

# Backward-compatible alias
ollama_service = llm_service
