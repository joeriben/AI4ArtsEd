"""
Output Chunk: Denoising Archaeology (Diffusers)

Generates image with step-by-step denoising visualization.
Captures VAE-decoded intermediates at every sampling step.
This is a Python-based chunk - the code IS the chunk.

Input: prompt (TEXT_1)
Output: dict with final image + per-step JPEG thumbnails
"""

import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_denoising_archaeology_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "35-55",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
}

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "",
    "seed": None,
    "capture_every_n": 1,
}


async def execute(
    prompt: str = None,
    TEXT_1: str = None,
    negative_prompt: str = None,
    steps: int = None,
    cfg: float = None,
    seed: int = None,
    **kwargs
) -> dict:
    """Returns dict (not bytes) - uses extended Python chunk dict-return path."""
    from my_app.services.diffusers_client import get_diffusers_backend
    from my_app.services.latent_lab_model import get_latent_lab_model_id
    from my_app.services.latent_lab_model import (
        get_latent_lab_unet,
        get_mmdit_pipeline_class,
    )

    prompt = prompt or TEXT_1
    steps = steps if steps is not None else DEFAULTS["steps"]
    cfg = cfg if cfg is not None else DEFAULTS["cfg"]
    negative_prompt = negative_prompt or DEFAULTS["negative_prompt"]

    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for denoising archaeology")

    backend = get_diffusers_backend()

    # Which net does the denoising. It comes from the output config, so the
    # model card of the run says the same thing that ran -- see
    # configs/output/denoising_archaeology_sdxl_diffusers.json.
    backbone = str(kwargs.get('backbone') or 'sd35').strip().lower()
    if backbone == 'sdxl':
        model_id, pipeline_class = get_latent_lab_unet()
    else:
        if backbone != 'sd35':
            logger.warning(
                "[ARCHAEOLOGY] Unknown backbone %r, running SD3.5", backbone
            )
            backbone = 'sd35'
        model_id = await get_latent_lab_model_id()
        pipeline_class = get_mmdit_pipeline_class()
    # Which rule walks the path, and how the steps sit on it. Both come from the
    # request, because both are choices WITHIN a run -- unlike the backbone, which
    # is the config's. The GPU service checks the name against the loaded
    # pipeline's own compatibility list and keeps its own scheduler if it does not
    # know the word, so a stale value cannot cost a run.
    scheduler = kwargs.get('scheduler') or None
    shift = kwargs.get('shift')
    try:
        shift = float(shift) if shift is not None and shift != '' else None
    except (TypeError, ValueError):
        logger.warning("[ARCHAEOLOGY] Unreadable shift %r, running the model default", shift)
        shift = None

    logger.info(
        "[ARCHAEOLOGY] backbone=%s model=%s scheduler=%s shift=%s",
        backbone, model_id, scheduler, shift,
    )

    result = await backend.generate_image_with_archaeology(
        prompt=prompt,
        negative_prompt=negative_prompt,
        steps=steps,
        cfg_scale=cfg,
        seed=seed if seed is not None else -1,
        capture_every_n=DEFAULTS["capture_every_n"],
        model_id=model_id,
        pipeline_class=pipeline_class,
        scheduler=scheduler,
        shift=shift,
    )

    if result is None:
        raise Exception("Denoising archaeology generation failed")

    return {
        'content_marker': 'diffusers_archaeology_generated',
        # WHICH backbone ran — this instrument has two, an MMDiT and a U-Net, and
        # the MMDiT is Medium or Large by the size of the card. Without this the
        # answer names the output config instead, which names neither.
        'model_id': model_id,
        'image_data': result['image_base64'],
        'archaeology_data': {
            'step_images': result['step_images'],
            'total_steps': result['total_steps'],
            'seed': result['seed'],
            # What ran, read off the pipeline. A second-order scheduler asks the
            # net twice per step, so there are more frames than steps and the
            # surface cannot name one without knowing which.
            'scheduler': result.get('scheduler'),
            'scheduler_order': result.get('scheduler_order', 1),
            # Which net ran, by the word the surface chooses it with, as the
            # ComfyUI twin reports it: the server-side record
            # (services/denoising_archaeology_record.py) writes it into the run.
            'backbone': backbone,
        },
        'seed': result['seed'],
    }
