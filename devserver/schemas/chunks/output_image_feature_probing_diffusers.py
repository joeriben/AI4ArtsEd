"""
Output Chunk: Feature Probing via Diffusers

Analyzes embedding differences between two prompts and generates images
with selective dimension transfer. Returns image + per-dimension difference data.
This is a Python-based chunk - the code IS the chunk.

Input: prompt (TEXT_1), prompt_b, probing_encoder, optional transfer_dims
Output: dict with base64 image + probing_data (embedding analysis)
"""

import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_feature_probing_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "25-45",
    "requires_gpu": True,
    "gpu_vram_mb": 12000,
    "fallback_chunk": None,
}

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "",
    "seed": None,
    "width": 1024,
    "height": 1024,
    "probing_encoder": "all",
}


async def execute(
    prompt: str = None,
    TEXT_1: str = None,
    prompt_b: str = "",
    probing_encoder: str = None,
    transfer_dims: list = None,
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
    **kwargs
) -> dict:
    """Returns dict with base64 image + probing data — uses extended Python chunk dict-return path."""
    from my_app.services.diffusers_client import get_diffusers_backend
    from my_app.services.latent_lab_model import get_latent_lab_model_id
    from my_app.services.latent_lab_capabilities import get_latent_lab_capabilities
    import random

    caps = await get_latent_lab_capabilities()
    if not caps.get("feature_probing"):
        threshold = caps.get("threshold_gb", 40)
        vram = caps.get("total_vram_gb")
        vram_str = f"{vram:.0f} GB" if vram else "unbekannt"
        raise RuntimeError(
            f"Dimension Explorer ist auf dieser GPU nicht verfügbar "
            f"(erkannt: {vram_str}, benötigt: ≥{threshold:.0f} GB). "
            f"Override: AI4ARTSED_FORCE_HEAVY_LATENT_LAB=true"
        )

    prompt = prompt or TEXT_1 or kwargs.get('PREVIOUS_OUTPUT', '')
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for Dimension Explorer")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))
    probing_encoder = probing_encoder or DEFAULTS["probing_encoder"]

    if seed is None or seed == 'random' or seed == -1:
        seed = random.randint(0, 2**32 - 1)
    else:
        seed = int(seed)

    backend = get_diffusers_backend()
    ok, why = await backend.availability()
    if not ok:
        raise RuntimeError(f"Diffusers backend not available: {why}")

    model_id = await get_latent_lab_model_id()

    logger.info(f"[PROBING] Generating: encoder={probing_encoder}, transfer={'yes' if transfer_dims else 'no'}, steps={steps}, size={w}x{h}, model={model_id}")
    probing_result = await backend.generate_image_with_probing(
        prompt_a=prompt,
        prompt_b=prompt_b,
        encoder=probing_encoder,
        transfer_dims=transfer_dims,
        negative_prompt=neg,
        width=w,
        height=h,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=seed,
        model_id=model_id,
    )

    if not probing_result or (isinstance(probing_result, dict) and 'error' in probing_result):
        error_detail = probing_result.get('error', 'unknown') if isinstance(probing_result, dict) else 'empty result'
        raise RuntimeError(f"Dimension Explorer generation failed: {error_detail}")

    return {
        'content_marker': 'diffusers_probing_generated',
        'image_data': probing_result['image_base64'],
        'media_type': 'image',
        'backend': 'diffusers',
        'model_id': model_id,
        'seed': probing_result['seed'],
        'probing_data': probing_result['probing_data'],
        'parameters': {
            'width': w,
            'height': h,
            'steps': steps,
            'cfg_scale': cfg_scale,
        }
    }
