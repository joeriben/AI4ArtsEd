"""
VLM Safety Check — Two-model image safety architecture.

Step 1: VLM (qwen3-vl:2b) describes the image — no classification, no deliberation.
Step 2: Text model (qwen3:1.7b) judges the description — SAFE/UNSAFE verdict.

Separation of concerns eliminates both failure modes:
- Deliberation loops (VLM debates edge cases) — gone, VLM only describes.
- Truncation (verdict cut off at token limit) — gone, verdict model gets 200 tokens.

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

# Step 1: VLM describes image (no classification, no SAFE/UNSAFE question)
VLM_DESCRIBE_SYSTEM = (
    'You are an image description assistant. '
    'Describe exactly what you see. Do not reason or speculate. '
    'Do not guess titles or artists. Be factual and specific.'
)
VLM_DESCRIBE_PROMPT = (
    'Describe this image in detail. '
    'Where potentially sensitive content is visible, describe it specifically rather than vaguely.'
)

# Step 2: Text model judges description (per safety level)
# Single calibration line prevents over-classification without weakening detection
VLM_VERDICT_PROMPTS = {
    'kids': (
        'You are a safety classifier for a children\'s educational app (ages 6-12).\n\n'
        'An image has been described as follows:\n\n'
        '"{description}"\n\n'
        'UNSAFE means the image CLEARLY DEPICTS one of these:\n'
        '- Graphic violence, gore, blood, injury\n'
        '- Nudity or sexual content\n'
        '- Hate symbols (swastikas, KKK imagery, etc.)\n'
        '- Self-harm depictions\n'
        '- Terrorism or hate crime scenes\n'
        '- Horror imagery: monsters, zombies, ghosts, skulls, demons, '
        'or imagery designed to frighten\n\n'
        'IMPORTANT: Dark lighting, shadows, or moody atmosphere alone '
        'are NOT harmful. Only flag content from the list above.\n\n'
        'Answer SAFE or UNSAFE.'
    ),
    'youth': (
        'You are a safety classifier for a youth educational app (ages 12-16).\n\n'
        'An image has been described as follows:\n\n'
        '"{description}"\n\n'
        'UNSAFE means the image CLEARLY DEPICTS one of these:\n'
        '- Graphic violence, gore, blood, injury\n'
        '- Nudity or sexual content\n'
        '- Hate symbols (swastikas, KKK imagery, etc.)\n'
        '- Self-harm depictions\n'
        '- Terrorism or hate crime scenes\n\n'
        'IMPORTANT: Dark lighting, shadows, or moody atmosphere alone '
        'are NOT harmful. Only flag content from the list above.\n\n'
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
    Check image safety via two-model architecture. Returns (is_safe, reason, description).

    Step 1: VLM (qwen3-vl) describes the image — no classification question.
    Step 2: Text model (qwen3:1.7b) judges the description — SAFE/UNSAFE verdict.

    Fail-closed: if safety cannot be confirmed, the image is blocked.
    Only an explicit SAFE verdict lets an image through.

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
            return (False, "VLM safety check: image file not found, blocked for safety", '')

        verdict_prompt_template = VLM_VERDICT_PROMPTS.get(safety_level)
        if not verdict_prompt_template:
            return (True, '', '')

        # --- Step 1: VLM describes the image ---
        img = Image.open(image_path)
        original_size = img.size
        if max(img.size) > VLM_MAX_SIZE:
            img.thumbnail((VLM_MAX_SIZE, VLM_MAX_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=80)
        image_bytes = buf.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        logger.info(
            f"[VLM-SAFETY] Step 1: Describing image ({original_size} -> {img.size}, "
            f"{len(image_bytes)} bytes) with {config.VLM_SAFETY_MODEL}"
        )

        from my_app.services.llm_backend import get_llm_backend
        llm = get_llm_backend()

        describe_result = llm.chat(
            model=config.VLM_SAFETY_MODEL,
            messages=[
                {'role': 'system', 'content': VLM_DESCRIBE_SYSTEM},
                {'role': 'user', 'content': VLM_DESCRIBE_PROMPT},
            ],
            images=[image_b64],
            temperature=0.0,
            max_new_tokens=1500,
            enable_thinking=False,
        )

        if describe_result is None:
            logger.error("[VLM-SAFETY] Step 1: VLM returned None — BLOCKING (cannot verify safety)")
            return (False, f"VLM safety check ({config.VLM_SAFETY_MODEL}): model unreachable, blocked for safety", '')

        content = describe_result.get('content', '').strip()
        thinking = (describe_result.get('thinking') or '').strip()
        description = thinking or content

        logger.info(f"[VLM-SAFETY] Step 1: Description ({len(description)} chars): {description[:200]!r}")

        if not description:
            logger.error("[VLM-SAFETY] Step 1: Empty description — BLOCKING (fail-closed)")
            return (False, f"VLM safety check ({config.VLM_SAFETY_MODEL}): empty description, blocked for safety", '')

        # --- Step 2: Text model judges the description ---
        verdict_prompt = verdict_prompt_template.format(description=description)

        logger.info(
            f"[VLM-SAFETY] Step 2: Judging description with {config.VLM_VERDICT_MODEL} "
            f"for safety_level={safety_level}"
        )

        verdict_result = llm.chat(
            model=config.VLM_VERDICT_MODEL,
            messages=[{'role': 'user', 'content': verdict_prompt}],
            temperature=0.0,
            max_new_tokens=200,
            enable_thinking=False,
        )

        if verdict_result is None:
            logger.error("[VLM-SAFETY] Step 2: Verdict model returned None — BLOCKING (cannot verify safety)")
            return (False, f"VLM safety check ({config.VLM_VERDICT_MODEL}): verdict model unreachable, blocked for safety", description)

        verdict_content = verdict_result.get('content', '').strip()
        verdict_thinking = (verdict_result.get('thinking') or '').strip()
        verdict_text = verdict_content or verdict_thinking

        logger.info(f"[VLM-SAFETY] Step 2: Verdict response: {verdict_text!r}")

        verdict = _extract_verdict(verdict_content) or _extract_verdict(verdict_thinking)

        if verdict == 'unsafe':
            return (False, f"VLM safety check ({config.VLM_VERDICT_MODEL}): image flagged as unsafe for {safety_level}", description)
        if verdict == 'safe':
            return (True, '', description)

        # Model responded but no verdict — FAIL-CLOSED
        logger.error(
            "[VLM-SAFETY] Step 2: No SAFE/UNSAFE verdict — BLOCKING (fail-closed). "
            f"verdict_content={verdict_content!r}, verdict_thinking={verdict_thinking[:200]!r}"
        )
        return (False, f"VLM safety check ({config.VLM_VERDICT_MODEL}): no clear verdict, blocked for safety", description)

    except Exception as e:
        logger.error(f"[VLM-SAFETY] Error during check — BLOCKING (cannot verify safety): {e}")
        return (False, "VLM safety check: error during check, blocked for safety", '')
