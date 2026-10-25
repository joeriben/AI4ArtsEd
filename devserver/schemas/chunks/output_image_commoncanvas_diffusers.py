"""
Output Chunk: CommonCanvas XL C via Diffusers

The same weights the ComfyUI route runs, loaded through the GPU service instead.
The ComfyUI route reads a single-file checkpoint; this one reads the repository
in diffusers format, which is what the Latent Lab instruments need to reach a
U-Net at all. Both exist so that the provenance question can be asked twice:
once as a picture beside the other models pictures, and once from inside an
instrument.

This is a Python-based chunk - the code IS the chunk.

Input: prompt (TEXT_1)
Output: dict with base64 image data + generation metadata
"""

import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_commoncanvas_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "15-40",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
    # None on purpose, unlike the other diffusers chunks. This config exists so
    # that a run can say which loader made the picture; a silent switch to the
    # ComfyUI route would leave the provenance sheet naming a loader that did
    # not run. A failure here has to be a failure.
    "fallback_chunk": None,
    #
    # Where a run carries LoRAs it goes to the ComfyUI route instead, before
    # this chunk sees it -- the same reason as SD3.5: a LoRA trained on this
    # platform carries Kohya key names, the diffusers loader looks for
    # diffusers names, finds none, and generates as if no adapter had been
    # asked for. No error anywhere, and the image is the one without it.
    "lora_chunk": "output_image_commoncanvas_xl_c",
}

MODEL_ID = "common-canvas/CommonCanvas-XL-C"
PIPELINE_CLASS = "StableDiffusionXLPipeline"

# What the generating call gives this models text encoders to read. Both are
# CLIP and both read 77 tokens; there is no T5 behind them to carry the rest,
# so everything past the window is dropped without a word. Half of SD3.5s
# number, and the reason a long intercepted text reaches this model as a stump.
PROMPT_WINDOW_TOKENS = 77
PROMPT_WINDOW_TOKENIZER = "clip_l"

# Held against the ComfyUI route on purpose: same steps, same cfg, same negative
# prompt, so that a difference between the two images is the loader and the
# sampler and not the numbers. The schedulers still differ -- ComfyUI runs
# euler_ancestral, the diffusers pipeline its own Euler default -- so the two
# are comparable in output, not reproducible seed for seed.
DEFAULTS = {
    "steps": 30,
    "cfg": 7.0,
    "negative_prompt": "ugly, blurry, deformed, watermark, text, low quality",
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
    loras: list = None,
    **kwargs
) -> dict:
    """Returns dict with base64 image - uses extended Python chunk dict-return path."""
    from my_app.services.diffusers_client import get_diffusers_backend
    import base64
    import random

    prompt = prompt or TEXT_1 or kwargs.get("PREVIOUS_OUTPUT", "")
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for CommonCanvas generation")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))

    if seed is None or seed == "random" or seed == -1:
        seed = random.randint(0, 2**32 - 1)
    else:
        seed = int(seed)

    backend = get_diffusers_backend()
    ok, why = await backend.availability()
    if not ok:
        raise RuntimeError(f"Diffusers backend not available: {why}")

    if loras:
        logger.info("[COMMONCANVAS] Applying %d LoRA(s): %s", len(loras), [l.get("name") for l in loras])

    logger.info(f"[COMMONCANVAS] Generating: steps={steps}, size={w}x{h}, cfg={cfg_scale}")
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
    )

    if not image_bytes:
        raise RuntimeError("CommonCanvas generation returned empty result")

    return {
        "content_marker": "diffusers_generated",
        "image_data": base64.b64encode(image_bytes).decode("utf-8"),
        "media_type": "image",
        "backend": "diffusers",
        "model_id": MODEL_ID,
        "seed": seed,
        "parameters": {
            "width": w,
            "height": h,
            "steps": steps,
            "cfg_scale": cfg_scale,
        },
    }
