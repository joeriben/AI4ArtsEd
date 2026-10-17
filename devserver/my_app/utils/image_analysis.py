"""
Universal Image Analysis Helper
Reusable function for analyzing images with vision models

Uses LLMClient (GPU Service).
Reference resolution lives in my_app/utils/media_ref.py — this module never
guesses what a string is.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def analyze_image(
    image_ref: str,
    prompt: Optional[str] = None,
    analysis_type: str = 'bildwissenschaftlich',
    model: Optional[str] = None,
    index: Optional[int] = None,
    lang: Optional[str] = None,
) -> str:
    """
    Analyze image using vision model via LLMClient.

    Args:
        image_ref: Any reference media_ref.resolve_media_ref accepts — a file
                path, /api/media/image/<run_id>[/<index>], /api/media/uploads/<id>,
                a bare run_id or upload id — or a data:image/...;base64 URL.
        prompt: Analysis prompt. If None, the frame's own text is read from
                schemas/reading_frames, written to answer in `lang`.
                Fallback: "Analyze this image thoroughly."
        analysis_type: Analysis framework to use:
            - 'bildungstheoretisch': Jörissen/Marotzki (Bildungspotenziale)
            - 'bildwissenschaftlich': Panofsky (art-historical, default)
            - 'ethisch': Ethical analysis
            - 'kritisch': Critical reading (media-critical)
        model: Vision model to use. If None, uses IMAGE_ANALYSIS_MODEL from config.
               Accepts 'local/model:tag' format, strips 'local/' prefix.
        index: Explicit image index for multi-output runs; overrides the index
               carried in a media URL.
        lang: Language the reading is written in. Only read when `prompt` is
              None, since a prompt handed in already says what it wants.
              None means the instance language.

    Returns:
        Analysis text from vision model

    Raises:
        MediaRefError (a FileNotFoundError): the reference does not resolve to
            an image on disk
        Exception: If inference fails
    """
    from config import IMAGE_ANALYSIS_MODEL
    from my_app.utils.media_ref import load_image_b64, strip_data_url

    # Use provided model or fallback to config default
    # Strip 'local/' prefix if present (Canvas uses 'local/model:tag' format)
    if model:
        vision_model = model.replace('local/', '') if model.startswith('local/') else model
    else:
        vision_model = IMAGE_ANALYSIS_MODEL

    # Step 1: Resolve the reference to image bytes. The branch this replaced
    # assumed that any string it could not place was already base64 — so a
    # media URL was decoded into a few dozen bytes of garbage and shipped to
    # the VLM as an image. That is why a Canvas image_evaluation reading a
    # generated image never worked: generation outputs carry a URL, not a path.
    if isinstance(image_ref, str) and image_ref.startswith('data:image'):
        image_data = strip_data_url(image_ref)
    else:
        image_data = load_image_b64(image_ref, index=index)

    # Step 2: Get prompt with fallback cascade
    if prompt is None:
        from my_app.services.reading_frames import prompt as frame_prompt
        prompt = frame_prompt(analysis_type, lang)
        if prompt is None:
            # An unknown frame reads the picture plainly rather than not at all.
            prompt = "Analyze this image thoroughly."
            logger.warning("[IMAGE-ANALYSIS] no text for frame %r, reading plainly", analysis_type)

    # Step 3: Call via LLMClient (GPU Service)
    logger.info(f"[IMAGE-ANALYSIS] Analyzing image with {vision_model}")

    try:
        from my_app.services.llm_backend import get_llm_backend
        result = get_llm_backend().chat(
            model=vision_model,
            messages=[{'role': 'user', 'content': prompt}],
            images=[image_data],
            temperature=0.7,
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
        MediaRefError (a FileNotFoundError): run not found, or no image in it
    """
    from my_app.utils.media_ref import resolve_media_ref

    image_path = resolve_media_ref(run_id, kind='image')
    logger.info(f"[IMAGE-ANALYSIS] Loading image from run {run_id}: {image_path}")
    return analyze_image(str(image_path), prompt, analysis_type)
