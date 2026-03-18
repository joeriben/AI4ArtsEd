"""
VLM Safety Check — Image safety via local VLM.

Extracted from schema_pipeline_routes.py to be reusable for both
post-generation checks and input image upload checks.

Uses LLMClient (GPU Service primary, Ollama fallback).
Fail-closed: blocks if safety cannot be confirmed.
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
        'Does this image contain violence, gore, nudity, hate symbols, self-harm, '
        'racism, hate crime settings, terrorism, sexism, '
        'or content that is scary, unsettling, or traumatizing for young children? '
        'Answer SAFE or UNSAFE.'
    ),
    'youth': (
        'Does this image contain violence, gore, nudity, hate symbols, self-harm, '
        'racism, hate crime settings, terrorism, or sexism? '
        'Answer SAFE or UNSAFE.'
    ),
}


def _extract_verdict(text: str) -> str | None:
    """Extract SAFE/UNSAFE verdict from text.

    Priority: first word, last word, then last occurrence of 'unsafe'/'safe'
    in text (to catch thinking conclusions like '...so this is unsafe').
    'unsafe' is checked before 'safe' to avoid substring false matches.
    """
    if not text or not text.strip():
        return None
    words = text.strip().split()
    # Check first and last word (cleanest signal)
    for word in (words[0], words[-1]):
        cleaned = word.lower().rstrip('.,!:;')
        if cleaned in ('safe', 'unsafe'):
            return cleaned
    # Fallback: scan for last standalone 'unsafe' or 'safe' in text.
    # Check unsafe first — 'unsafe' contains 'safe' as substring.
    lower = text.lower()
    for target in ('unsafe', 'safe'):
        pos = lower.rfind(target)
        if pos != -1:
            # Verify it's a standalone word (not part of e.g. "unsafely")
            before_ok = pos == 0 or not lower[pos - 1].isalpha()
            after_end = pos + len(target)
            after_ok = after_end >= len(lower) or not lower[after_end].isalpha()
            if before_ok and after_ok:
                return target
    return None


def vlm_describe_image(image_path: str | Path) -> str:
    """
    Describe image content using VLM. Same model and call pattern as vlm_safety_check.
    Returns description string, or empty string on failure.
    """
    try:
        image_path = Path(image_path)
        if not image_path.exists():
            return ''

        img = Image.open(image_path)
        if max(img.size) > VLM_MAX_SIZE:
            img.thumbnail((VLM_MAX_SIZE, VLM_MAX_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=80)
        image_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        from my_app.services.llm_backend import get_llm_backend
        result = get_llm_backend().chat(
            model=config.VLM_SAFETY_MODEL,
            messages=[{'role': 'user', 'content': 'Describe this image in 2-3 sentences. Focus on subject, composition, colors, and style.'}],
            images=[image_b64],
            temperature=0.0,
            enable_thinking=False,
        )
        if result is None:
            return ''
        content = result.get('content', '').strip()
        thinking = (result.get('thinking') or '').strip()
        return thinking or content
    except Exception as e:
        logger.error(f"[VLM-DESCRIBE] Failed: {e}")
        return ''


def vlm_safety_check(image_path: str | Path, safety_level: str) -> tuple[bool, str, str]:
    """
    Check image safety via qwen3-vl. Returns (is_safe, reason, description).

    Fail-closed: if safety cannot be confirmed, the image is blocked.
    Only an explicit SAFE verdict from the VLM lets an image through.

    Args:
        image_path: Path to the image file on disk.
        safety_level: 'kids' or 'youth' (only these trigger VLM check).

    Returns:
        (is_safe, reason, description) — description is the VLM's image analysis.
        (False, reason, '') on any failure to confirm safety.
    """
    try:
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error("[VLM-SAFETY] Image file not found — BLOCKING (cannot verify safety)")
            return (False, f"VLM safety check: image file not found, blocked for safety", '')

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
            enable_thinking=False,  # Disable thinking — model loops endlessly otherwise
        )

        if result is None:
            logger.error("[VLM-SAFETY] LLM returned None — BLOCKING (cannot verify safety)")
            return (False, f"VLM safety check ({config.VLM_SAFETY_MODEL}): model unreachable, blocked for safety", '')

        content = result.get('content', '').strip()
        thinking = (result.get('thinking') or '').strip()
        logger.info(f"[VLM-SAFETY] Model response: content={content!r}, thinking={thinking[:200]!r}")

        # Use thinking as description (contains the analysis); fall back to content
        # if no thinking. Pure verdict words ('SAFE'/'UNSAFE') aren't useful descriptions.
        description = thinking or content

        verdict = _extract_verdict(content) or _extract_verdict(thinking)

        if verdict == 'unsafe':
            return (False, f"VLM safety check ({config.VLM_SAFETY_MODEL}): image flagged as unsafe for {safety_level}", description)
        if verdict == 'safe':
            return (True, '', description)

        # Model responded but no verdict — FAIL-CLOSED
        logger.error(
            "[VLM-SAFETY] Model responded but no SAFE/UNSAFE verdict — BLOCKING (fail-closed). "
            f"content={content!r}, thinking={thinking[:200]!r}"
        )
        return (False, f"VLM safety check ({config.VLM_SAFETY_MODEL}): no clear verdict, blocked for safety", description)

    except Exception as e:
        logger.error(f"[VLM-SAFETY] Error during check — BLOCKING (cannot verify safety): {e}")
        return (False, f"VLM safety check: error during check, blocked for safety", '')
