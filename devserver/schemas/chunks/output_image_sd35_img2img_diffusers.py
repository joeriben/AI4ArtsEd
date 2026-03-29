"""
Output Chunk: SD3.5 Large Image-to-Image via Diffusers

Image-to-image generation using Stable Diffusion 3.5 Large with from_pipe().
The input image is VAE-encoded and partially denoised according to strength.
Zero extra VRAM — reuses the existing t2i pipeline components.

Input:
    - image_base64: Base64-encoded PNG/JPEG image (direct API calls)
    - input_image: File path to image on disk (pipeline executor in i2X pages)
    - prompt (TEXT_1): Text description to guide the transformation
    - strength: Denoising strength 0-1 (0 = no change, 1 = full generation)

Output: dict with base64 image data + generation metadata
"""

import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_sd35_img2img_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "15-30",
    "requires_gpu": True,
    "gpu_vram_mb": 57000,
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
    "strength": 0.65,
}


async def execute(
    image_base64: str = None,
    input_image: str = None,
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
    strength: float = None,
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
        raise ValueError("No prompt provided for SD3.5 img2img generation")

    # Resolve image from base64 or file path
    if image_base64:
        image_b64 = image_base64
    elif input_image:
        with open(input_image, 'rb') as f:
            image_b64 = base64.b64encode(f.read()).decode('utf-8')
        logger.info(f"[SD35-I2I] Loaded image from path: {input_image}")
    else:
        raise ValueError("No image provided (need image_base64 or input_image)")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))
    strength_val = float(strength if strength is not None else DEFAULTS["strength"])

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
        logger.info(f"[SD35-I2I] Triple-prompt: forwarding {list(extra_kwargs.keys())}")

    if loras:
        logger.info(f"[SD35-I2I] Applying {len(loras)} LoRA(s): {[l['name'] for l in loras]}")

    logger.info(f"[SD35-I2I] Generating: steps={steps}, size={w}x{h}, cfg={cfg_scale}, strength={strength_val}")
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
        image_base64=image_b64,
        strength=strength_val,
        loras=loras if loras else None,
        **extra_kwargs,
    )

    if not image_bytes:
        raise RuntimeError("SD3.5 img2img generation returned empty result")

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
            'strength': strength_val,
        }
    }
