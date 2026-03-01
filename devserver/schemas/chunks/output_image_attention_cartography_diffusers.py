"""
Output Chunk: Attention Cartography via Diffusers

Generates image with cross-attention map extraction. Returns image + per-token
attention heatmaps at selected layers and timesteps. Custom attention processor
replaces JointAttnProcessor2_0 on selected transformer blocks.
This is a Python-based chunk - the code IS the chunk.

Input: prompt (TEXT_1)
Output: dict with base64 image + attention_data (tokens, maps, spatial info)
"""

import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_attention_cartography_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "30-50",
    "requires_gpu": True,
    "gpu_vram_mb": 12000,
    "fallback_chunk": None,
}

MODEL_ID = "stabilityai/stable-diffusion-3.5-large"

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "",
    "seed": None,
    "width": 1024,
    "height": 1024,
    "capture_layers": [3, 9, 17],
    "capture_every_n_steps": 1,
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
    capture_layers: list = None,
    capture_every_n_steps: int = None,
    **kwargs
) -> dict:
    """Returns dict with base64 image + attention data — uses extended Python chunk dict-return path."""
    from my_app.services.diffusers_backend import get_diffusers_backend
    import random

    prompt = prompt or TEXT_1 or kwargs.get('PREVIOUS_OUTPUT', '')
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for Attention Cartography")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))
    capture_layers = capture_layers or DEFAULTS["capture_layers"]
    capture_every_n = int(capture_every_n_steps if capture_every_n_steps is not None else DEFAULTS["capture_every_n_steps"])

    if seed is None or seed == 'random' or seed == -1:
        seed = random.randint(0, 2**32 - 1)
    else:
        seed = int(seed)

    backend = get_diffusers_backend()
    if not await backend.is_available():
        raise RuntimeError("Diffusers backend not available")

    logger.info(f"[ATTENTION] Generating: layers={capture_layers}, every_n={capture_every_n}, steps={steps}, size={w}x{h}")
    attention_result = await backend.generate_image_with_attention(
        prompt=prompt,
        model_id=MODEL_ID,
        negative_prompt=neg,
        width=w,
        height=h,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=seed,
        capture_layers=capture_layers,
        capture_every_n_steps=capture_every_n,
    )

    if not attention_result:
        raise RuntimeError("Attention Cartography generation returned empty result")

    return {
        'content_marker': 'diffusers_attention_generated',
        'image_data': attention_result['image_base64'],
        'media_type': 'image',
        'backend': 'diffusers',
        'model_id': MODEL_ID,
        'seed': attention_result['seed'],
        'attention_data': {
            'tokens': attention_result['tokens'],
            'word_groups': attention_result.get('word_groups', []),
            'tokens_t5': attention_result.get('tokens_t5', []),
            'word_groups_t5': attention_result.get('word_groups_t5', []),
            'clip_token_count': attention_result.get('clip_token_count', 0),
            'attention_maps': attention_result['attention_maps'],
            'spatial_resolution': attention_result['spatial_resolution'],
            'image_resolution': attention_result['image_resolution'],
            'capture_layers': attention_result['capture_layers'],
            'capture_steps': attention_result['capture_steps'],
        },
        'parameters': {
            'width': w,
            'height': h,
            'steps': steps,
            'cfg_scale': cfg_scale,
        }
    }
