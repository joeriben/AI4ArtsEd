"""
Output Chunk: Wan 2.2 I2V-A14B Image-to-Video Generation (Diffusers)

Generates video from an input image using Wan 2.2 I2V-A14B (MoE, 27B total, 14B active)
via the GPU service. Uses WanImageToVideoPipeline from HuggingFace Diffusers.

Input:
    - image_base64: Base64-encoded PNG/JPEG image to animate
    - input_image: File path to image on disk (from pipeline executor in i2X pages)
    - prompt (TEXT_1): Optional text description to guide the animation

Output:
    - MP4 video bytes
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_video_wan22_i2v_diffusers",
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
    image_base64: str = None,
    input_image: str = None,
    prompt: str = None,
    TEXT_1: str = None,
    model_id: str = "Wan-AI/Wan2.2-I2V-A14B-Diffusers",
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
    Execute Wan 2.2 I2V-A14B image-to-video generation.

    Accepts image via either:
    - image_base64: Base64-encoded image (direct API calls)
    - input_image: File path on disk (pipeline executor in i2X pages)

    An optional text prompt can guide the animation direction.

    Returns:
        MP4 video bytes

    Raises:
        Exception: If generation fails, backend unavailable, or no image provided
    """
    from my_app.services.diffusers_backend import get_diffusers_backend
    import base64
    import random

    # Map pipeline convention
    if prompt is None and TEXT_1 is not None:
        prompt = TEXT_1

    # Resolve image from base64 or file path
    if image_base64:
        image_bytes = base64.b64decode(image_base64)
    elif input_image:
        with open(input_image, 'rb') as f:
            image_bytes = f.read()
        logger.info(f"[CHUNK:wan22-i2v] Loaded image from path: {input_image}")
    else:
        raise ValueError("No image provided (need image_base64 or input_image)")

    # Apply defaults
    prompt = prompt or ""
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

    logger.info(f"[CHUNK:wan22-i2v] Executing: model={model_id}, {width}x{height}, {num_frames} frames, {steps} steps")
    if prompt:
        logger.info(f"[CHUNK:wan22-i2v] Prompt: {prompt[:100]}...")

    backend = get_diffusers_backend()

    if not await backend.is_available():
        raise Exception("Diffusers backend not available")

    video_bytes = await backend.generate_video_from_image(
        image_bytes=image_bytes,
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
        raise Exception("I2V video generation failed")

    logger.info(f"[CHUNK:wan22-i2v] Generated {len(video_bytes)} bytes (seed={seed})")
    return video_bytes
