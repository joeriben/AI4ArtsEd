"""
VLM Safety Check — Image safety via local VLM.

Extracted from schema_pipeline_routes.py to be reusable for both
post-generation checks and input image upload checks.

Uses LLMClient (GPU Service primary, Ollama fallback).
"""

import base64
import io
import logging
from pathlib import Path

from PIL import Image

import config

# Max dimension for VLM input — safety classification doesn't need full resolution
VLM_MAX_SIZE = 768

logger = logging.getLogger(__name__)

VLM_PROMPTS = {
    'kids': (
        '/no_think\n'
        'Is the image free of violence, nudity, unsettling, scaring, '
        'potentially traumatizing, or other content unsafe or unhealthy '
        'for children age 6-12 years? Answer ONLY "safe" or "unsafe".'
    ),
    'youth': (
        '/no_think\n'
        'Is the image free of violence, nudity, unsettling, scaring, '
        'potentially traumatizing, or other content unsafe or unhealthy '
        'for teenagers age 14-18 years? Answer ONLY "safe" or "unsafe".'
    ),
}


def vlm_safety_check(image_path: str | Path, safety_level: str) -> tuple[bool, str, str]:
    """
    Check image safety via qwen3-vl. Returns (is_safe, reason, description). Fail-open.

    Args:
        image_path: Path to the image file on disk.
        safety_level: 'kids' or 'youth' (only these trigger VLM check).

    Returns:
        (is_safe, reason, description) — description is the VLM's image analysis.
        (True, '', '') on safe or error (fail-open).
    """
    try:
        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning("[VLM-SAFETY] Image file not found — skipping check")
            return (True, '', '')

        prompt_text = VLM_PROMPTS.get(safety_level)
        if not prompt_text:
            return (True, '', '')

        # Downscale for VLM — safety classification doesn't need full resolution
        img = Image.open(image_path)
        original_size = img.size
        if max(img.size) > VLM_MAX_SIZE:
            img.thumbnail((VLM_MAX_SIZE, VLM_MAX_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=80)
        image_bytes = buf.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        logger.info(f"[VLM-SAFETY] Checking image ({original_size} -> {img.size}, {len(image_bytes)} bytes) with {config.VLM_SAFETY_MODEL} for safety_level={safety_level}")

        from my_app.services.llm_backend import get_llm_backend
        result = get_llm_backend().chat(
            model=config.VLM_SAFETY_MODEL,
            messages=[{'role': 'user', 'content': prompt_text}],
            images=[image_b64],
            temperature=0.0,
            max_new_tokens=50,
        )

        if result is None:
            logger.warning("[VLM-SAFETY] LLM returned None (fail-open)")
            return (True, '', '')

        # With /no_think, verdict is in 'content' directly.
        # Fallback: check 'thinking' too in case model ignores /no_think.
        content = result.get('content', '').lower().strip()
        thinking = (result.get('thinking') or '').lower().strip()
        combined = f"{content} {thinking}"
        logger.info(f"[VLM-SAFETY] Model response: content={content!r}, thinking={thinking[:200]!r}")

        description = content or thinking

        if 'unsafe' in combined:
            return (False, f"VLM safety check ({config.VLM_SAFETY_MODEL}): image flagged as unsafe for {safety_level}", description)
        if 'safe' in combined:
            return (True, '', description)
        # No clear verdict — fail-open but log warning
        logger.warning(f"[VLM-SAFETY] No clear safe/unsafe verdict in response — fail-open")
        return (True, '', description)

    except Exception as e:
        # Fail-open: VLM failure should never block
        logger.warning(f"[VLM-SAFETY] Error during check (fail-open): {e}")
        return (True, '', '')
