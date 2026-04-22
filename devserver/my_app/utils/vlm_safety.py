"""
VLM Safety Check — Hybrid single-model + two-model adjudication architecture.

Primary: VLM sees the image and classifies directly. SAFE is trusted (fast path).
Adjudication: UNSAFE or no-verdict from the 2B primary triggers the two-model
          path: VLM description (neutral, no verdict coercion) → STAGE3_MODEL
          verdict on the description. This prevents the 2B from false-blocking
          harmless images the primary prompt overextends on.

Fail-closed: blocks if safety cannot be confirmed at any stage.
"""

import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests
from PIL import Image
from my_app.services.usage_tracker import get_usage_tracker, extract_usage

import config

# Max dimension for VLM input — safety classification doesn't need full resolution
VLM_MAX_SIZE = 768
# Min dimension — qwen3-vl panics on images < 32px (SmartResize factor=32).
# A panic kills the runner process, causing ALL subsequent VLM requests to 500
# until the backend is restarted. Discovered 2026-03-22 in production.
VLM_MIN_SIZE = 64

logger = logging.getLogger(__name__)

# --- Primary path: VLM sees + judges (same categories as before) ---
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

# --- Fallback path: VLM describes, text model judges ---
VLM_DESCRIBE_PROMPTS = {
    'kids': (
        'Examine this image for the following: violence, gore, nudity, hate symbols, '
        'self-harm, racism, hate crime settings, terrorism, sexism, '
        'or content that is scary, unsettling, or traumatizing for young children. '
        'Describe what you see.'
    ),
    'youth': (
        'Examine this image for the following: violence, gore, nudity, hate symbols, '
        'self-harm, racism, hate crime settings, terrorism, or sexism. '
        'Describe what you see.'
    ),
}

VLM_VERDICT_PROMPTS = {
    'kids': (
        'You are a safety classifier for a children\'s educational app (ages 6-12).\n\n'
        'A safety-focused analysis of an image produced the following:\n\n'
        '"{description}"\n\n'
        'Based on this analysis, does the image contain harmful content?\n\n'
        'UNSAFE means the analysis found: graphic violence, gore, nudity, '
        'hate symbols, self-harm, terrorism, or horror imagery '
        '(monsters, zombies, ghosts, skulls, demons).\n\n'
        'IMPORTANT: Dark lighting, shadows, or moody atmosphere alone '
        'are NOT harmful. Only flag content from the list above.\n\n'
        'Answer SAFE or UNSAFE.'
    ),
    'youth': (
        'You are a safety classifier for a youth educational app (ages 12-16).\n\n'
        'A safety-focused analysis of an image produced the following:\n\n'
        '"{description}"\n\n'
        'Based on this analysis, does the image contain harmful content?\n\n'
        'UNSAFE means the analysis found: graphic violence, gore, nudity, '
        'hate symbols, self-harm, or terrorism.\n\n'
        'IMPORTANT: Dark lighting, shadows, or moody atmosphere alone '
        'are NOT harmful. Only flag content from the list above.\n\n'
        'Answer SAFE or UNSAFE.'
    ),
}

# Cloud provider configs for verdict model routing
_CLOUD_PROVIDERS = {
    'mammouth': {
        'url': 'https://api.mammouth.ai/v1/chat/completions',
        'key_file': 'mammouth.key',
        'env_var': 'MAMMOUTH_API_KEY',
    },
    'mistral': {
        'url': 'https://api.mistral.ai/v1/chat/completions',
        'key_file': 'mistral.key',
        'env_var': 'MISTRAL_API_KEY',
    },
    'openrouter': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key_file': 'openrouter.key',
        'env_var': 'OPENROUTER_API_KEY',
    },
    'ionos': {
        'url': 'https://llm.2.2-rc.2.2.ionoscloud.com/v1/chat/completions',
        'key_file': 'ionos.key',
        'env_var': 'IONOS_API_KEY',
    },
}


def _get_api_key(provider: str) -> Optional[str]:
    """Load API key from env var or .key file in devserver/."""
    prov = _CLOUD_PROVIDERS.get(provider)
    if not prov:
        return None
    # 1. Environment variable
    key = os.environ.get(prov['env_var'], '')
    if key:
        return key
    # 2. Key file (devserver/{provider}.key)
    key_file = Path(__file__).parent.parent.parent / prov['key_file']
    if key_file.exists():
        for line in key_file.read_text().strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('//'):
                return line
    return None


def _call_verdict_model(prompt: str) -> Optional[str]:
    """Call STAGE3_MODEL for verdict classification. Routes by model prefix.

    Returns response content string, or None on failure.
    """
    model = config.STAGE3_MODEL

    # Determine provider from prefix
    provider = None
    api_model = model
    for prefix in _CLOUD_PROVIDERS:
        if model.startswith(f'{prefix}/'):
            provider = prefix
            api_model = model[len(prefix) + 1:]
            break

    if not provider and model.startswith('local/'):
        api_model = model[6:]

    if provider:
        # Cloud API call (OpenAI-compatible)
        api_key = _get_api_key(provider)
        if not api_key:
            logger.error(f"[VLM-SAFETY] No API key for provider {provider}")
            return None

        prov_config = _CLOUD_PROVIDERS[provider]
        try:
            response = requests.post(
                prov_config['url'],
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': api_model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0,
                    'max_tokens': 200,
                },
                timeout=(10, 30),
            )
            if response.status_code != 200:
                logger.error(f"[VLM-SAFETY] {provider} API error: {response.status_code} {response.text[:200]}")
                return None
            result = response.json()

            inp, out = extract_usage(result, provider)
            if inp or out:
                get_usage_tracker().log(model=model, provider=provider,
                                        stage="stage3", input_tokens=inp, output_tokens=out)

            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"[VLM-SAFETY] {provider} API call failed: {e}")
            return None
    else:
        # Local model via GPU Service LLM backend
        from my_app.services.llm_backend import get_llm_backend
        result = get_llm_backend().chat(
            model=api_model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.0,
            max_new_tokens=200,
            enable_thinking=False,
        )
        if result is None:
            return None
        return result.get('content', '').strip()


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
    Describe image content using VLM. Used by compare page.
    Returns description string, or empty string on failure.
    """
    try:
        image_path = Path(image_path)
        if not image_path.exists():
            return ''

        img = Image.open(image_path)
        if min(img.size) < VLM_MIN_SIZE:
            scale = VLM_MIN_SIZE / min(img.size)
            new_size = (max(VLM_MIN_SIZE, int(img.width * scale)), max(VLM_MIN_SIZE, int(img.height * scale)))
            img = img.resize(new_size, Image.LANCZOS)
            logger.warning(f"[VLM-DESCRIBE] Upscaled undersized image {image_path.name}: {img.size}")
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
    Check image safety via hybrid architecture. Returns (is_safe, reason, description).

    Primary: VLM sees the image and classifies directly. Only SAFE is trusted as
             a final verdict — the 2B primary is known to over-block harmless
             images on the kids prompt.
    Adjudication: Primary UNSAFE or no-verdict escalates to the two-model path:
             VLM describes neutrally → STAGE3_MODEL classifies the description.
    Final: Fail-closed if adjudication cannot confirm safety.

    Args:
        image_path: Path to the image file on disk.
        safety_level: 'kids' or 'youth' (only these trigger VLM check).

    Returns:
        (is_safe, reason, description) — description is the VLM's image analysis.
        (False, reason, '') on any failure to confirm safety.
    """
    verdict_model = config.STAGE3_MODEL

    try:
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error("[VLM-SAFETY] Image file not found — BLOCKING (cannot verify safety)")
            return (False, "VLM safety check: image file not found, blocked for safety", '')

        prompt_text = VLM_PROMPTS.get(safety_level)
        if not prompt_text:
            return (True, '', '')

        # --- Prepare image ---
        img = Image.open(image_path)
        original_size = img.size
        if min(img.size) < VLM_MIN_SIZE:
            scale = VLM_MIN_SIZE / min(img.size)
            new_size = (max(VLM_MIN_SIZE, int(img.width * scale)), max(VLM_MIN_SIZE, int(img.height * scale)))
            img = img.resize(new_size, Image.LANCZOS)
            logger.warning(f"[VLM-SAFETY] Upscaled undersized image {original_size} -> {img.size} (min {VLM_MIN_SIZE}px)")
        if max(img.size) > VLM_MAX_SIZE:
            img.thumbnail((VLM_MAX_SIZE, VLM_MAX_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=80)
        image_bytes = buf.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        from my_app.services.llm_backend import get_llm_backend
        llm = get_llm_backend()

        # =================================================================
        # PRIMARY PATH: VLM sees image + classifies directly
        # =================================================================
        logger.info(
            f"[VLM-SAFETY] Primary: VLM direct check ({original_size} -> {img.size}, "
            f"{len(image_bytes)} bytes) with {config.VLM_SAFETY_MODEL} for {safety_level}"
        )

        result = llm.chat(
            model=config.VLM_SAFETY_MODEL,
            messages=[{'role': 'user', 'content': prompt_text}],
            images=[image_b64],
            temperature=0.0,
            max_new_tokens=1500,
            enable_thinking=False,
        )

        if result is not None:
            content = result.get('content', '').strip()
            thinking = (result.get('thinking') or '').strip()
            description = thinking or content

            logger.info(f"[VLM-SAFETY] Primary response: content={content!r}, thinking={thinking[:200]!r}")

            verdict = _extract_verdict(content) or _extract_verdict(thinking)

            if verdict == 'safe':
                return (True, '', description)

            # Primary UNSAFE is NOT a final verdict — the 2B over-blocks. Escalate
            # to the two-model adjudication path (VLM describe → STAGE3_MODEL judge).
            if verdict == 'unsafe':
                logger.warning(
                    "[VLM-SAFETY] Primary flagged unsafe — escalating to two-model adjudication. "
                    f"content={content[:100]!r}, thinking={thinking[:100]!r}"
                )
            else:
                logger.warning(
                    "[VLM-SAFETY] Primary: no SAFE/UNSAFE verdict — trying two-model fallback. "
                    f"content={content[:100]!r}, thinking={thinking[:100]!r}"
                )
        else:
            description = ''
            logger.warning("[VLM-SAFETY] Primary: VLM returned None — trying two-model fallback")

        # =================================================================
        # FALLBACK PATH: VLM describes → STAGE3_MODEL judges
        # =================================================================
        describe_prompt = VLM_DESCRIBE_PROMPTS.get(safety_level)
        verdict_prompt_template = VLM_VERDICT_PROMPTS.get(safety_level)

        if not describe_prompt or not verdict_prompt_template:
            # Should not happen (safety_level already validated), but fail-closed
            return (False, f"VLM safety check: no fallback prompt for {safety_level}, blocked for safety", description)

        # Step 1: VLM describes the image (safety-focused, no verdict coercion)
        logger.info(f"[VLM-SAFETY] Fallback Step 1: Describing image with {config.VLM_SAFETY_MODEL}")

        describe_result = llm.chat(
            model=config.VLM_SAFETY_MODEL,
            messages=[{'role': 'user', 'content': describe_prompt}],
            images=[image_b64],
            temperature=0.0,
            max_new_tokens=1500,
            enable_thinking=False,
        )

        if describe_result is None:
            logger.error("[VLM-SAFETY] Fallback Step 1: VLM returned None — BLOCKING")
            return (False, f"VLM safety check ({config.VLM_SAFETY_MODEL}): model unreachable, blocked for safety", '')

        fb_content = describe_result.get('content', '').strip()
        fb_thinking = (describe_result.get('thinking') or '').strip()
        fb_description = fb_thinking or fb_content

        logger.info(f"[VLM-SAFETY] Fallback Step 1: Description ({len(fb_description)} chars): {fb_description[:200]!r}")

        if not fb_description:
            logger.error("[VLM-SAFETY] Fallback Step 1: Empty description — BLOCKING")
            return (False, f"VLM safety check ({config.VLM_SAFETY_MODEL}): empty description, blocked for safety", '')

        # Use fallback description as the returned description (more informative than primary's non-verdict)
        description = fb_description

        # Step 2: STAGE3_MODEL classifies the description
        verdict_prompt = verdict_prompt_template.format(description=fb_description)

        logger.info(f"[VLM-SAFETY] Fallback Step 2: Judging with {verdict_model} for {safety_level}")

        verdict_content = _call_verdict_model(verdict_prompt)

        if verdict_content is None:
            logger.error("[VLM-SAFETY] Fallback Step 2: Verdict model returned None — BLOCKING")
            return (False, f"VLM safety check ({verdict_model}): verdict model unreachable, blocked for safety", description)

        logger.info(f"[VLM-SAFETY] Fallback Step 2: Verdict response: {verdict_content!r}")

        verdict = _extract_verdict(verdict_content)

        if verdict == 'unsafe':
            return (False, f"VLM safety check ({verdict_model}): image flagged as unsafe for {safety_level}", description)
        if verdict == 'safe':
            return (True, '', description)

        # Neither path produced a verdict — FAIL-CLOSED
        logger.error(
            "[VLM-SAFETY] Both paths failed to produce verdict — BLOCKING (fail-closed). "
            f"verdict_content={verdict_content[:200]!r}"
        )
        return (False, f"VLM safety check: no verdict from either path, blocked for safety", description)

    except Exception as e:
        logger.error(f"[VLM-SAFETY] Error during check — BLOCKING (cannot verify safety): {e}")
        return (False, "VLM safety check: error during check, blocked for safety", '')
