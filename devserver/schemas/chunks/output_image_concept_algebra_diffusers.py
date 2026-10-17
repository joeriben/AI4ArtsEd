"""
Output Chunk: Concept Algebra (Diffusers)

Vector arithmetic on text encoder embeddings: A - scale_sub*B + scale_add*C
Inspired by Mikolov's word2vec analogies, applied to SD3.5 text encoders.
This is a Python-based chunk - the code IS the chunk.

Input: prompt (A), prompt_b (B), prompt_c (C)
Output: dict with reference image (A) + result image (A-B+C) + algebra metadata
"""

import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_concept_algebra_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "40-80",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
}

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "",
    "seed": None,
    "algebra_encoder": "all",
    "scale_sub": 1.0,
    "scale_add": 1.0,
}


async def execute(
    prompt: str = None,
    TEXT_1: str = None,
    prompt_b: str = "",
    prompt_c: str = "",
    algebra_encoder: str = None,
    scale_sub: float = None,
    scale_add: float = None,
    negative_prompt: str = None,
    steps: int = None,
    cfg: float = None,
    seed: int = None,
    **kwargs
) -> dict:
    """Returns dict (not bytes) - uses extended Python chunk dict-return path."""
    from my_app.services.diffusers_client import get_diffusers_backend
    from my_app.services.latent_lab_model import get_latent_lab_model_id

    prompt = prompt or TEXT_1
    steps = steps if steps is not None else DEFAULTS["steps"]
    cfg = cfg if cfg is not None else DEFAULTS["cfg"]
    negative_prompt = negative_prompt or DEFAULTS["negative_prompt"]
    algebra_encoder = algebra_encoder or DEFAULTS["algebra_encoder"]
    scale_sub = scale_sub if scale_sub is not None else DEFAULTS["scale_sub"]
    scale_add = scale_add if scale_add is not None else DEFAULTS["scale_add"]

    if not prompt or not prompt.strip():
        raise ValueError("No prompt A provided for concept algebra")

    backend = get_diffusers_backend()
    model_id = await get_latent_lab_model_id()
    result = await backend.generate_image_with_algebra(
        prompt_a=prompt,
        prompt_b=prompt_b,
        prompt_c=prompt_c,
        encoder=algebra_encoder,
        scale_sub=float(scale_sub),
        scale_add=float(scale_add),
        negative_prompt=negative_prompt,
        steps=steps,
        cfg_scale=cfg,
        seed=seed if seed is not None else -1,
        model_id=model_id,
    )

    if result is None:
        raise Exception("Concept algebra generation failed")

    return {
        'content_marker': 'diffusers_algebra_generated',
        # WHICH backbone ran. The resolver answers Medium or Large by the size of
        # the card, and without this the answer names the output config instead —
        # "Concept Algebra (SD 3.5)", which is the instrument's name and not a
        # model, and which drops exactly that distinction.
        'model_id': model_id,
        'reference_image': result['reference_image'],
        'result_image': result['result_image'],
        'algebra_data': result['algebra_data'],
        'seed': result['seed'],
    }
