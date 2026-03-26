"""
Output Chunk: Composable Diffusion (Diffusers)

Per-concept noise prediction blending during denoising.
Each concept gets its own transformer pass; noise predictions are
weighted and summed before the scheduler step.

Based on Liu et al. (2022) "Compositional Visual Generation with
Composable Diffusion Models".

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
    **kwargs
) -> dict:
    """Returns dict with composable diffusion result."""
    from my_app.services.diffusers_backend import get_diffusers_backend

    # Concepts can come as JSON string from the pipeline
    if concepts and isinstance(concepts, str):
        concepts = json.loads(concepts)

    if not concepts or len(concepts) < 2:
        raise ValueError("Need at least 2 concepts for composable diffusion")

    steps = steps if steps is not None else DEFAULTS["steps"]
    cfg = cfg if cfg is not None else DEFAULTS["cfg"]
    negative_prompt = negative_prompt or DEFAULTS["negative_prompt"]
    normalize_weights = normalize_weights if normalize_weights is not None else DEFAULTS["normalize_weights"]

    backend = get_diffusers_backend()
    result = await backend.generate_image_composable(
        concepts=concepts,
        negative_prompt=negative_prompt,
        steps=steps,
        cfg_scale=cfg,
        seed=seed if seed is not None else -1,
        normalize_weights=normalize_weights,
    )

    if result is None:
        raise Exception("Composable diffusion generation failed")

    return {
        'content_marker': 'diffusers_composable_generated',
        'image_base64': result['image_base64'],
        'seed': result['seed'],
        'concept_count': result['concept_count'],
        'weights_used': result['weights_used'],
        'timing_s': result['timing_s'],
    }
