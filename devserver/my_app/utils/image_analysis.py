"""
Universal Image Analysis Helper
Reusable function for analyzing images with vision models

Uses LLMClient (GPU Service).
"""

import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def analyze_image(
    image_path: str,
    prompt: Optional[str] = None,
    analysis_type: str = 'bildwissenschaftlich',
    model: Optional[str] = None
) -> str:
    """
    Analyze image using vision model via LLMClient.

    Args:
        image_path: Path to image file OR base64-encoded image string
        prompt: Analysis prompt. If None, uses default from config.py
                based on analysis_type + DEFAULT_LANGUAGE.
                Fallback: "Analyze this image thoroughly."
        analysis_type: Analysis framework to use:
            - 'bildungstheoretisch': Jörissen/Marotzki (Bildungspotenziale)
            - 'bildwissenschaftlich': Panofsky (art-historical, default)
            - 'ethisch': Ethical analysis
            - 'kritisch': Decolonial & critical media studies
        model: Vision model to use. If None, uses IMAGE_ANALYSIS_MODEL from config.
               Accepts 'local/model:tag' format, strips 'local/' prefix.

    Returns:
        Analysis text from vision model

    Raises:
        FileNotFoundError: If image_path is file path and doesn't exist
        Exception: If inference fails
    """
    from config import (
        IMAGE_ANALYSIS_MODEL,
        DEFAULT_LANGUAGE,
        IMAGE_ANALYSIS_PROMPTS
    )

    # Session 152: Use provided model or fallback to config default
    # Strip 'local/' prefix if present (Canvas uses 'local/model:tag' format)
    if model:
        vision_model = model.replace('local/', '') if model.startswith('local/') else model
    else:
        vision_model = IMAGE_ANALYSIS_MODEL

    # Step 1: Load image as base64
    if ',' in image_path and image_path.startswith('data:image'):
        # Already base64 with data URL prefix
        image_data = image_path.split(',', 1)[-1]
    elif Path(image_path).exists():
        # File path - load and encode
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
    else:
        # Assume it's already base64 string
        image_data = image_path

    # Step 2: Get prompt with fallback cascade
    if prompt is None:
        try:
            # Try to get from config based on analysis_type + language
            prompt = IMAGE_ANALYSIS_PROMPTS[analysis_type][DEFAULT_LANGUAGE]
        except (KeyError, ImportError, AttributeError):
            # Fallback if prompts not in config or invalid analysis_type
            prompt = "Analyze this image thoroughly."
            logger.warning(f"Analysis prompt not found for {analysis_type}/{DEFAULT_LANGUAGE}, using fallback")

    # Step 3: Call via LLMClient (GPU Service)
    logger.info(f"[IMAGE-ANALYSIS] Analyzing image with {vision_model}")

    try:
        from my_app.services.llm_backend import get_llm_backend
        result = get_llm_backend().chat(
            model=vision_model,
            messages=[{'role': 'user', 'content': prompt}],
            images=[image_data],
            temperature=0.7,
            max_new_tokens=2000,
            enable_thinking=False,
        )

        if result is None:
            raise Exception("LLM returned None")

        analysis_text = result.get("content", "").strip()

        # qwen3-vl quirk: sometimes writes to thinking field instead of content
        if not analysis_text:
            analysis_text = (result.get("thinking") or "").strip()

        if not analysis_text:
            raise Exception("Empty response from LLM")

        logger.info(f"[IMAGE-ANALYSIS] Analysis complete ({len(analysis_text)} chars)")
        return analysis_text

    except Exception as e:
        logger.error(f"[IMAGE-ANALYSIS] Failed: {e}")
        raise


def analyze_image_from_run(
    run_id: str,
    prompt: Optional[str] = None,
    analysis_type: str = 'bildwissenschaftlich'
) -> str:
    """
    Convenience function: Analyze image from LivePipelineRecorder run_id

    Args:
        run_id: Run ID from LivePipelineRecorder
        prompt: Analysis prompt (optional, uses default if None)
        analysis_type: Analysis framework (bildungstheoretisch/bildwissenschaftlich/ethisch/kritisch)

    Returns:
        Analysis text

    Raises:
        FileNotFoundError: If run_id not found or no image in run
    """
    from my_app.services.pipeline_recorder import load_recorder
    from config import JSON_STORAGE_DIR

    # Load recorder
    recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
    if not recorder:
        raise FileNotFoundError(f"Run ID not found: {run_id}")

    # Find image entity
    entities = recorder.metadata.get('entities', [])
    image_entity = next(
        (e for e in entities if 'image' in e.get('type', '') and e.get('filename', '').endswith(('.png', '.jpg', '.jpeg', '.webp'))),
        None
    )

    if not image_entity:
        raise FileNotFoundError(f"No image found in run {run_id}")

    # Session 130: Files are in final/ subfolder
    image_path = recorder.final_folder / image_entity['filename']

    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    logger.info(f"[IMAGE-ANALYSIS] Loading image from run {run_id}: {image_path}")

    # Analyze
    return analyze_image(str(image_path), prompt, analysis_type)
