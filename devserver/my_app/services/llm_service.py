"""
Service for high-level LLM interactions.

Translation, safety checks, image analysis: all through the platform's LLM
backend (services/llm_backend), which runs the local models in ComfyUI since
stage 3 of the move.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

from config import (
    STAGE3_MODEL,
    IMAGE_ANALYSIS_MODEL,
    ANALYSIS_SYSTEM_PROMPT,
    PROMPT_CACHE,
    TRANSLATION_PROMPT,
    NO_TRANSLATE,
)

logger = logging.getLogger(__name__)


class LLMService:
    """Service class for high-level LLM interactions through the LLM backend.

    No output cap by default (see llm_client): max_tokens is left at None and
    the model runs to its own context ceiling. The default used to be 512,
    which silently truncated every caller that did not override it.
    """

    def __init__(self):
        logger.info("Initialized LLM service (services/llm_backend)")

    def _chat(self, model: str, messages: list, images: list = None,
              temperature: float = 0.7, max_tokens: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Call the LLM backend's chat through the shared client.

        One implementation of this transport instead of a second one beside
        it. LLMClient resolves the model over the table of local models, logs
        a failure with the run's own sentence and answers it with None, which
        is what this method has always returned.

        The absent cap stays absent: this method passes max_new_tokens=None,
        and LLMClient sets no cap at all (see its `chat`).
        """
        from my_app.services.llm_backend import get_llm_backend
        return get_llm_backend().chat(
            model=model,
            messages=messages,
            images=images,
            temperature=temperature,
            max_new_tokens=max_tokens,
        )

    def _complete(self, model: str, prompt: str, system: str = "",
                  temperature: float = 0.7, max_tokens: Optional[int] = None) -> Optional[str]:
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
                             max_tokens: Optional[int] = None) -> Optional[str]:
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

    def check_safety(self, text: str, safety_level: str = None) -> Dict[str, Any]:
        """
        Ask the safety classifier the question of the running level.

        Args:
            text: Text to check
            safety_level: the level the run is under. Absent, the child's
                question is asked, because a level nobody passed is a level
                nobody set.

        Returns:
            Dictionary with 'is_safe' boolean and optional 'reason' if unsafe
        """
        # The platform's own sentence for a check that could not be carried out.
        # It is German, it is already translated at the surface, and it opens
        # with "Technische Störung", which is what tells a fault apart from a
        # content rating downstream. Nothing new is worded here.
        from schemas.engine.stage_orchestrator import SAFETY_CHECK_UNAVAILABLE_MESSAGE
        from my_app.services import safety_classifier

        if (safety_level or '').strip().lower() in ('adult', 'research'):
            return {"is_safe": True}

        # Until 2026-09 this asked a chat-trained guard "Is the following text
        # safe?" in free text and read the answer out of its prose. Two things
        # were wrong with that beyond the reading: the question was the same at
        # every level, although this route resolves one, and a no-answer
        # returned {"is_safe": True} until 2026-09-04 — the first of the
        # patterns that have broken this chain since 2025. Both are gone: the
        # level is the question, and no answer blocks.
        verdict = safety_classifier.is_unsafe(
            safety_classifier.policy_for_level(safety_level), text)

        if verdict is None:
            logger.error("[SAFETY] no verdict — blocking (fail-closed)")
            return {"is_safe": False, "reason": SAFETY_CHECK_UNAVAILABLE_MESSAGE,
                    "unavailable": True}
        if verdict:
            return {
                "is_safe": False,
                "reason": "Sorry, your prompt has been rejected due to potential issues."
            }
        return {"is_safe": True}

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

    def describe_image_neutral(self, image_b64: str) -> Optional[str]:
        """Full, neutral visual account of an image (Resona's view_favorite).

        Same VLM as analyze_image, but a plain descriptive brief instead of the
        image-generation analysis prompt.
        """
        if ',' in image_b64:
            image_b64 = image_b64.split(',', 1)[-1]
        prompt = (
            "Describe fully and concretely what is visible in this image: subjects, "
            "composition, colors, style/technique, and any readable text. "
            "No speculation about intent, no quality judgement."
        )
        return self._complete_with_image(self.view_vlm_model(), prompt, image_b64, max_tokens=None)

    def ask_about_image(self, image_b64: str, question: str) -> Optional[str]:
        """Answer ONE question about an image, on the platform's vision channel.

        The same channel and the same model as describe_image_neutral; what
        differs is that the question comes from the model that is answering the
        person, not from this file. A model that cannot see asks for what it
        needs and asks again -- a fixed description decides in advance what
        there was to notice, and leaves nothing to come back for.

        The brief is the caller's (utils/vision_support._LOOK_BRIEF), so the
        local channel and a provider's delegate are asked in the same words.
        """
        if ',' in image_b64:
            image_b64 = image_b64.split(',', 1)[-1]
        return self._complete_with_image(self.view_vlm_model(), question,
                                         image_b64, temperature=0.2, max_tokens=None)

    def view_vlm_model(self) -> str:
        """The VLM the look runs on: qwen3-vl:4b, or RESONA_VIEW_VLM_MODEL.

        Pulled out of describe_image_neutral and describe_image_brief, which
        each carried this block verbatim and now share it with ask_about_image.
        Three copies of one setting is three chances to read a different one.
        Public because the installer asks it too (local_llm_install._role_models):
        no role on the settings page names this model.
        """
        # A model of its own rather than IMAGE_ANALYSIS_MODEL. On the primary
        # category of 120 images, qwen3-vl:4b agreed with qwen3-vl:32b in 93.3 %
        # (kappa 0.896; series G1-G2, 2026-07-02; the data are in
        # joeriben/ai4artsed_research since 2026-09-06). The 32b failed on the
        # GPU service's chat route on 2026-07-03 (HTTP 500), which the look no
        # longer takes: _chat goes through LLMClient to ComfyUI.
        # Override via RESONA_VIEW_VLM_MODEL in user_settings.json, read here
        # rather than from config because the installer runs in a process that
        # never loads the settings; a "local/" prefix is accepted
        # (local_llm_weights.resolve_alias).
        model = "qwen3-vl:4b"
        try:
            import json as _json
            settings_file = Path(__file__).parent.parent.parent / "user_settings.json"
            if settings_file.exists():
                value = _json.loads(settings_file.read_text(encoding="utf-8")).get("RESONA_VIEW_VLM_MODEL")
                if isinstance(value, str) and value.strip():
                    model = value.strip()
        except Exception:
            logger.warning("the look's VLM setting is unreadable", exc_info=True)
        return model

    def describe_image_brief(self, image_b64: str) -> Optional[str]:
        """A short (1-2 sentence) neutral caption of an image — Resona's
        automatic glance at material placed on her board. Same VLM channel as
        describe_image_neutral, but a brief prompt. Deliberately does NOT ask
        for readable text: a caption is written into the SYSTEM prompt, so
        faithfully transcribing text embedded in an untrusted dropped image
        would be an injection vector. The full account (with any text) stays
        behind the deliberate view_upload / view_favorite look."""
        if ',' in image_b64:
            image_b64 = image_b64.split(',', 1)[-1]
        prompt = (
            "In one or two sentences, say plainly what this image shows — its "
            "main subject, and its medium or evident style. No interpretation, "
            "no judgement, and do not transcribe any text in the image."
        )
        return self._complete_with_image(self.view_vlm_model(), prompt, image_b64, max_tokens=None)

    def validate_and_translate_prompt(self, prompt: str, safety_level: str = None) -> Dict[str, Any]:
        """
        Validate and translate a prompt with caching.

        Args:
            prompt: Original prompt text
            safety_level: the level the run is under, which decides both the
                question the check asks and what the cache may answer.

        Returns:
            Dictionary with 'success', 'translated_prompt', and optional 'error'
        """
        # The level belongs in the key. A cache hit returns without checking,
        # and the key was the prompt alone, so a prompt cleared in research
        # answered the next run under kids as already safe.
        cache_key = ((safety_level or '').strip().lower(), prompt.strip().lower())

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

        safety_result = self.check_safety(translated_prompt, safety_level)
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


# Singleton instance
llm_service = LLMService()
