"""
Output Chunk: Wan 2.2 T2V-A14B Video Generation (Diffusers)

Generates video from text using Wan 2.2 T2V-A14B (MoE, 27B total, 14B active)
via the GPU service. Uses official HuggingFace Diffusers WanPipeline.

Input (from Stage 2/3 or direct):
    - prompt (TEXT_1): Text description of the video to generate

Output:
    - MP4 video bytes
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_video_wan22_diffusers",
    "media_type": "video",
    "output_format": "mp4",
    "estimated_duration_seconds": "120-240",
    "quality_rating": 5,
    "requires_gpu": True,
    "gpu_vram_mb": 14000,
}

DEFAULTS = {
    "negative_prompt": "blurry, distorted, low quality, static, watermark",
    "width": 1280,
    "height": 720,
    "num_frames": 81,
    "steps": 40,
    "cfg_scale": 4.0,
    "guidance_scale_2": 3.0,
    "fps": 16,
    "seed": None,
}


async def execute(
    prompt: str = None,
    TEXT_1: str = None,
    model_id: str = "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
    negative_prompt: str = None,
    width: int = None,
    height: int = None,
    num_frames: int = None,
    steps: int = None,
    cfg_scale: float = None,
    guidance_scale_2: float = None,
    fps: int = None,
    seed: int = None,
    **kwargs
) -> bytes:
    """
    Execute Wan 2.2 T2V-A14B video generation.

    The output config provides resolution defaults and model_id.
    GPU service handles WanPipeline loading with VAE float32 separation
    and optional FP8 quantization for the dual MoE transformers.

    Returns:
        MP4 video bytes

    Raises:
        Exception: If generation fails or backend unavailable
    """
    from my_app.services.diffusers_client import get_diffusers_backend
    import random

    # Map pipeline convention
    if prompt is None and TEXT_1 is not None:
        prompt = TEXT_1

    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for video generation")

    # Apply defaults
    negative_prompt = negative_prompt if negative_prompt is not None else DEFAULTS["negative_prompt"]
    width = width if width is not None else DEFAULTS["width"]
    height = height if height is not None else DEFAULTS["height"]
    num_frames = num_frames if num_frames is not None else DEFAULTS["num_frames"]
    steps = steps if steps is not None else DEFAULTS["steps"]
    cfg_scale = cfg_scale if cfg_scale is not None else DEFAULTS["cfg_scale"]
    guidance_scale_2 = guidance_scale_2 if guidance_scale_2 is not None else DEFAULTS["guidance_scale_2"]
    fps = fps if fps is not None else DEFAULTS["fps"]

    if seed is None or seed == "random":
        seed = random.randint(0, 2**32 - 1)

    logger.info(f"[CHUNK:wan22-t2v] Executing: model={model_id}, {width}x{height}, {num_frames} frames, {steps} steps")
    logger.info(f"[CHUNK:wan22-t2v] Prompt: {prompt[:100]}...")

    backend = get_diffusers_backend()

    ok, why = await backend.availability()
    if not ok:
        raise Exception(f"Diffusers backend not available: {why}")

    video_bytes = await backend.generate_video(
        prompt=prompt,
        model_id=model_id,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_frames=num_frames,
        steps=steps,
        cfg_scale=cfg_scale,
        fps=fps,
        seed=seed,
        guidance_scale_2=guidance_scale_2,
    )

    if video_bytes is None:
        raise Exception("Video generation failed")

    logger.info(f"[CHUNK:wan22-t2v] Generated {len(video_bytes)} bytes (seed={seed})")
    return video_bytes
