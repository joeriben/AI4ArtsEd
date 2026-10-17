"""
Output Chunk: Composable Diffusion (Diffusers)

Per-concept score composition during denoising.
Each concept gets its own transformer pass; the composed prediction is
eps_u + sum_i v_i * (eps_i - eps_u), so a negative weight subtracts a
concept (the paper's NOT operator) instead of blending it in.

Based on Liu et al. (2022) "Compositional Visual Generation with
Composable Diffusion Models".

This station composes in score space and refuses `combine_at="conditioning"`,
the place the ComfyUI twin also offers (output_image_composable_diffusion_comfyui.py).

Input: concepts (list of {prompt, weight} dicts)
Output: dict with image_base64, seed, concept_count, timing_s
"""

import logging
import json

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_composable_diffusion_diffusers",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "60-120",
    "requires_gpu": True,
    "gpu_vram_mb": 30000,
}

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "",
    "seed": None,
    "normalize_weights": True,
}


async def execute(
    prompt: str = None,
    TEXT_1: str = None,
    concepts: str = None,
    negative_prompt: str = None,
    steps: int = None,
    cfg: float = None,
    seed: int = None,
    normalize_weights: bool = None,
    combine_at: str = None,
    **kwargs
) -> dict:
    """Returns dict with composable diffusion result."""
    from my_app.services.diffusers_client import get_diffusers_backend
    from my_app.services.latent_lab_model import get_latent_lab_model_id

    # Concepts can come as JSON string from the pipeline
    if concepts and isinstance(concepts, str):
        concepts = json.loads(concepts)

    if not concepts or len(concepts) < 2:
        raise ValueError("Need at least 2 concepts for composable diffusion")

    if combine_at is not None and combine_at != "score":
        raise ValueError(
            f"combine_at is {combine_at!r}. This station runs every concept "
            f"through the transformer at every step and adds the predictions, "
            f"which is the place 'score'; the place 'conditioning' runs in "
            f"ComfyUI (config composable_diffusion)."
        )

    steps = steps if steps is not None else DEFAULTS["steps"]
    cfg = cfg if cfg is not None else DEFAULTS["cfg"]
    negative_prompt = negative_prompt or DEFAULTS["negative_prompt"]
    normalize_weights = normalize_weights if normalize_weights is not None else DEFAULTS["normalize_weights"]

    backend = get_diffusers_backend()
    model_id = await get_latent_lab_model_id()
    result = await backend.generate_image_composable(
        concepts=concepts,
        negative_prompt=negative_prompt,
        steps=steps,
        cfg_scale=cfg,
        seed=seed if seed is not None else -1,
        normalize_weights=normalize_weights,
        model_id=model_id,
    )

    if result is None:
        raise Exception("Composable diffusion generation failed")

    return {
        'content_marker': 'diffusers_composable_generated',
        'image_data': result['image_base64'],
        'media_type': 'image',
        'backend': 'diffusers',
        'model_id': model_id,
        'seed': result['seed'],
        'composable_data': {
            'concept_count': result['concept_count'],
            'weights_used': result['weights_used'],
            'guidance_used': result.get('guidance_used'),
            'composition_mode': result.get('composition_mode'),
            'negated_count': result.get('negated_count'),
            'timing_s': result['timing_s'],
        },
    }
