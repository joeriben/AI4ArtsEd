"""
Vision support utilities for /api/chat hybrid image handling.

Three functions:
- prepare_image_b64: Resolve image source (run_id or file path) to base64
- is_vision_capable: Determine if a model supports multimodal input
- describe_image_for_fallback: Generate text description via IMAGE_ANALYSIS_MODEL
"""

import base64
import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

# Match vlm_safety.py constants
IMAGE_MAX_SIZE = 768
IMAGE_MIN_SIZE = 64


def prepare_image_b64(image_source: Optional[str] = None, run_id: Optional[str] = None) -> Optional[str]:
    """
    Resolve an image source to a base64-encoded JPEG string.

    Args:
        image_source: File path or base64 string
        run_id: Run ID from LivePipelineRecorder (used if image_source is None)

    Returns:
        Base64-encoded JPEG string, or None on failure
    """
    image_path = None

    # Resolve run_id to file path
    if run_id and not image_source:
        try:
            from my_app.services.pipeline_recorder import load_recorder
            from config import JSON_STORAGE_DIR
            recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
            if not recorder:
                logger.warning(f"[VISION] Run ID not found: {run_id}")
                return None

            entities = recorder.metadata.get('entities', [])
            image_entity = next(
                (e for e in entities if 'image' in e.get('type', '') and e.get('filename', '').endswith(('.png', '.jpg', '.jpeg', '.webp'))),
                None
            )
            if not image_entity:
                logger.warning(f"[VISION] No image entity in run {run_id}")
                return None

            image_path = str(recorder.final_folder / image_entity['filename'])
        except Exception as e:
            logger.error(f"[VISION] Failed to resolve run_id {run_id}: {e}")
            return None
    elif image_source:
        # Check if it's already base64
        if not Path(image_source).exists() and '/' not in image_source:
            return image_source
        image_path = image_source

    if not image_path or not Path(image_path).exists():
        logger.warning(f"[VISION] Image not found: {image_path}")
        return None

    try:
        img = Image.open(image_path)
        if min(img.size) < IMAGE_MIN_SIZE:
            scale = IMAGE_MIN_SIZE / min(img.size)
            new_size = (max(IMAGE_MIN_SIZE, int(img.width * scale)),
                        max(IMAGE_MIN_SIZE, int(img.height * scale)))
            img = img.resize(new_size, Image.LANCZOS)
        if max(img.size) > IMAGE_MAX_SIZE:
            img.thumbnail((IMAGE_MAX_SIZE, IMAGE_MAX_SIZE), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=80)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"[VISION] Failed to encode image {image_path}: {e}")
        return None


def is_vision_capable(model_string: str) -> bool:
    """
    Determine if a model supports multimodal (image) input.

    Cloud providers are assumed vision-capable (all modern models support it).
    Local models are checked by name heuristics.
    """
    if not model_string:
        return False

    model_lower = model_string.lower()

    # Cloud providers — all modern models support vision
    cloud_prefixes = ('mammouth/', 'anthropic/', 'openai/', 'openrouter/', 'mistral/', 'bedrock/')
    if any(model_lower.startswith(p) for p in cloud_prefixes):
        return True

    # IONOS — conservative, no vision support assumed
    if model_lower.startswith('ionos/'):
        return False

    # Local models — check name heuristics
    if model_lower.startswith('local/'):
        model_name = model_lower[len('local/'):]
    else:
        model_name = model_lower

    vision_indicators = ('vl', 'vision', 'llava', 'pixtral')
    return any(ind in model_name for ind in vision_indicators)


def describe_image_for_fallback(image_b64: str) -> str:
    """
    Generate a text description of an image using IMAGE_ANALYSIS_MODEL.
    Used as fallback when the chat model is not vision-capable.

    Returns:
        Description text, or a placeholder on failure
    """
    try:
        from config import IMAGE_ANALYSIS_MODEL
        from my_app.services.llm_backend import get_llm_backend

        model = IMAGE_ANALYSIS_MODEL
        if model.startswith('local/'):
            model = model[len('local/'):]

        prompt = (
            "Describe this image in 2-3 sentences. "
            "What is shown? What are the colors, mood, composition? "
            "Be concrete. No preamble."
        )

        result = get_llm_backend().chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            images=[image_b64],
            temperature=0.7,
            max_new_tokens=500,
            enable_thinking=False,
        )

        if result and result.get('content'):
            return result['content'].strip()

        # qwen3-vl quirk: may write to thinking field
        if result and result.get('thinking'):
            return result['thinking'].strip()

        return "[Image provided but could not be analyzed]"
    except Exception as e:
        logger.error(f"[VISION] Fallback description failed: {e}")
        return "[Image provided but could not be analyzed]"
