"""
Output Chunk: Surrealizer via Diffusers

Token-level CLIP-L/T5 extrapolation with selectable fusion strategy.
Sweet spot: alpha=15-35. Three strategies: dual_alpha (default), normalized, legacy.
This is a Python-based chunk - the code IS the chunk.

Input: prompt (TEXT_1), alpha_factor, fusion_strategy, optional t5_prompt
Output: dict with base64 image data + generation metadata
"""

import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_surrealizer_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "20-40",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
    "fallback_chunk": None,
}

MODEL_ID = "stabilityai/stable-diffusion-3.5-large"

DEFAULTS = {
    "steps": 25,
    "cfg": 5.5,
    "negative_prompt": "watermark",
    "seed": None,
    "width": 1024,
    "height": 1024,
    "alpha_factor": None,
    "fusion_strategy": "dual_alpha",
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
    alpha_factor: float = None,
    fusion_strategy: str = None,
    t5_prompt: str = None,
    loras: list = None,
    **kwargs
) -> dict:
    """Returns dict with base64 image — uses extended Python chunk dict-return path."""
    from my_app.services.diffusers_backend import get_diffusers_backend
    import base64
    import random

    prompt = prompt or TEXT_1 or kwargs.get('PREVIOUS_OUTPUT', '')
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for Surrealizer generation")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))
    fusion_strategy = fusion_strategy or DEFAULTS["fusion_strategy"]

    # Auto-generate alpha when not provided (e.g. Canvas random node)
    if alpha_factor is None:
        alpha_factor = random.randint(20, 30)
        logger.info(f"[SURREALIZER] Auto-generated alpha_factor: {alpha_factor}")
    alpha_factor = float(alpha_factor)

    if seed is None or seed == 'random' or seed == -1:
        seed = random.randint(0, 2**32 - 1)
    else:
        seed = int(seed)

    backend = get_diffusers_backend()
    if not await backend.is_available():
        raise RuntimeError("Diffusers backend not available")

    logger.info(f"[SURREALIZER] Generating: alpha={alpha_factor}, strategy={fusion_strategy}, steps={steps}, size={w}x{h}")
    image_bytes = await backend.generate_image_with_fusion(
        prompt=prompt,
        t5_prompt=t5_prompt,
        alpha_factor=alpha_factor,
        model_id=MODEL_ID,
        negative_prompt=neg,
        width=w,
        height=h,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=seed,
        loras=loras if loras else None,
        fusion_strategy=fusion_strategy,
    )

    if not image_bytes:
        raise RuntimeError("Surrealizer generation returned empty result")

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
            'alpha_factor': alpha_factor,
            'fusion_strategy': fusion_strategy,
        }
    }
