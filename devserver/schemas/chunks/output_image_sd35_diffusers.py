"""
Output Chunk: SD3.5 Large via Diffusers

Standard image generation using Stable Diffusion 3.5 Large with triple text encoding.
Supports triple-prompt (CLIP-L/G optimization), LoRA, and full parameter control.
This is a Python-based chunk - the code IS the chunk.

Input: prompt (TEXT_1), optional prompt_2/prompt_3 for per-encoder control
Output: dict with base64 image data + generation metadata
"""

import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_sd35_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "15-30",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
    "fallback_chunk": "output_image_sd35_large",
}

MODEL_ID = "stabilityai/stable-diffusion-3.5-large"
PIPELINE_CLASS = "StableDiffusion3Pipeline"

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "blurry, bad quality, watermark, text, distorted",
    "seed": None,
    "width": 1024,
    "height": 1024,
}


async def execute(
    prompt: str = None,
    TEXT_1: str = None,
    negative_prompt: str = None,
    NEGATIVE_PROMPT: str = None,
    steps: int = None,
    STEPS: int = None,
    cfg: float = None,
    CFG: float = None,
    seed: int = None,
    width: int = None,
    WIDTH: int = None,
    height: int = None,
    HEIGHT: int = None,
    prompt_2: str = None,
    prompt_3: str = None,
    loras: list = None,
    **kwargs
) -> dict:
    """Returns dict with base64 image — uses extended Python chunk dict-return path."""
    from my_app.services.diffusers_backend import get_diffusers_backend
    import base64
    import random

    prompt = prompt or TEXT_1 or kwargs.get('PREVIOUS_OUTPUT', '')
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for SD3.5 generation")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))

    if seed is None or seed == 'random' or seed == -1:
        seed = random.randint(0, 2**32 - 1)
    else:
        seed = int(seed)

    backend = get_diffusers_backend()
    if not await backend.is_available():
        raise RuntimeError("Diffusers backend not available")

    # Forward per-encoder prompts for SD3.5 triple-prompt (CLIP-L/G optimization)
    extra_kwargs = {}
    if prompt_2:
        extra_kwargs['prompt_2'] = prompt_2
    if prompt_3:
        extra_kwargs['prompt_3'] = prompt_3
    if extra_kwargs:
        logger.info(f"[SD35] Triple-prompt: forwarding {list(extra_kwargs.keys())}")

    if loras:
        logger.info(f"[SD35] Applying {len(loras)} LoRA(s): {[l['name'] for l in loras]}")

    logger.info(f"[SD35] Generating: steps={steps}, size={w}x{h}, cfg={cfg_scale}")
    image_bytes = await backend.generate_image(
        prompt=prompt,
        model_id=MODEL_ID,
        negative_prompt=neg,
        width=w,
        height=h,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=seed,
        pipeline_class=PIPELINE_CLASS,
        loras=loras if loras else None,
        **extra_kwargs,
    )

    if not image_bytes:
        raise RuntimeError("SD3.5 generation returned empty result")

    return {
        'content_marker': 'diffusers_generated',
        'image_data': base64.b64encode(image_bytes).decode('utf-8'),
        'media_type': 'image',
        'backend': 'diffusers',
        'model_id': MODEL_ID,
        'seed': seed,
        'parameters': {
            'width': w,
            'height': h,
            'steps': steps,
            'cfg_scale': cfg_scale,
        }
    }
