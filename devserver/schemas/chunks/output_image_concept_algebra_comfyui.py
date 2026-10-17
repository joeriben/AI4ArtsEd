"""
Output Chunk: Concept Algebra (ComfyUI)

ComfyUI counterpart of output_image_concept_algebra_diffusers.py. Same output
contract, same content_marker — the route dispatch and the surface are unchanged.
What differs is where the arithmetic happens: the AI4ArtsEdSD3 node family runs it
inside ComfyUI, so the model is loaded under ComfyUI's memory management.

The arithmetic is the twin's, unchanged: A - scale_sub*B + scale_add*C on the chosen
encoder, on the token stream and on the pooled vector where that encoder has one, with
nothing clamped and nothing renormalized. The encoders that were not chosen stay as
prompt A encoded them.

The graph carries TWO sampler branches on ONE seed, because the instrument shows a
pair: the reference is prompt A alone, the result is the arithmetic, and the two are
only comparable when the noise is the same.

Input: prompt (A), prompt_b (B), prompt_c (C), algebra_encoder, scale_sub, scale_add
Output: dict with reference image, result image and the algebra record
"""

import logging
import random

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_concept_algebra_comfyui",
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
    "width": 1024,
    "height": 1024,
    "sampler_name": "euler",
    "scheduler": "normal",
}

SAVE_REFERENCE_NODE_ID = "40"
SAVE_RESULT_NODE_ID = "41"
ALGEBRA_NODE_ID = "13"


def _build_workflow(prompt_a, prompt_b, prompt_c, negative_prompt, checkpoint,
                    encoder, scale_sub, scale_add, width, height, steps, cfg, seed,
                    sampler_name, scheduler):
    """The graph one run submits: three encodes, one arithmetic, two branches."""
    from schemas.engine.comfyui_chunk_support import (
        CLIP_NODE, checkpoint_loader, negative_encode, sd3_assemble, sd3_encode,
        t5_length, triple_clip_loader,
    )

    return {
        "5": checkpoint_loader(checkpoint),
        "7": triple_clip_loader(),
        CLIP_NODE: t5_length(),
        "10": sd3_encode(prompt_a, title="Encode A"),
        "11": sd3_encode(prompt_b, title="Encode B"),
        "12": sd3_encode(prompt_c, title="Encode C"),
        "13": {
            "inputs": {
                "a": ["10", 0], "b": ["11", 0], "c": ["12", 0],
                "encoder": encoder,
                "scale_sub": scale_sub,
                "scale_add": scale_add,
            },
            "class_type": "AI4ArtsEdSD3Algebra",
            "_meta": {"title": "A - sub*B + add*C"},
        },
        "14": sd3_assemble(["10", 0], "Assemble A"),
        "15": sd3_assemble(["13", 0], "Assemble the result"),
        "6": negative_encode(negative_prompt),
        "3": {
            "inputs": {"width": width, "height": height, "batch_size": 1},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "Empty latent"},
        },
        "20": {
            "inputs": {
                "model": ["5", 0], "positive": ["14", 0], "negative": ["6", 0],
                "latent_image": ["3", 0], "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": sampler_name, "scheduler": scheduler, "denoise": 1,
            },
            "class_type": "KSampler",
            "_meta": {"title": "Reference (A alone)"},
        },
        "21": {
            "inputs": {
                "model": ["5", 0], "positive": ["15", 0], "negative": ["6", 0],
                "latent_image": ["3", 0], "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": sampler_name, "scheduler": scheduler, "denoise": 1,
            },
            "class_type": "KSampler",
            "_meta": {"title": "Result (the arithmetic)"},
        },
        "22": {
            "inputs": {"samples": ["20", 0], "vae": ["5", 2]},
            "class_type": "VAEDecode",
            "_meta": {"title": "Decode the reference"},
        },
        "23": {
            "inputs": {"samples": ["21", 0], "vae": ["5", 2]},
            "class_type": "VAEDecode",
            "_meta": {"title": "Decode the result"},
        },
        SAVE_REFERENCE_NODE_ID: {
            "inputs": {"filename_prefix": "ComfyUI", "images": ["22", 0]},
            "class_type": "SaveImage",
            "_meta": {"title": "Save the reference"},
        },
        SAVE_RESULT_NODE_ID: {
            "inputs": {"filename_prefix": "ComfyUI", "images": ["23", 0]},
            "class_type": "SaveImage",
            "_meta": {"title": "Save the result"},
        },
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
    """Returns dict (not bytes) — uses the extended Python chunk dict-return path."""
    from my_app.services.latent_lab_model import get_latent_lab_model_id
    from schemas.engine.comfyui_chunk_support import (
        announced,
        final_image,
        resolve_checkpoint,
    )

    prompt = prompt or TEXT_1 or kwargs.get('PREVIOUS_OUTPUT', '')
    if not prompt or not prompt.strip():
        raise ValueError("No prompt A provided for concept algebra")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (
        NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))
    encoder = algebra_encoder or DEFAULTS["algebra_encoder"]
    scale_sub = float(scale_sub if scale_sub is not None else DEFAULTS["scale_sub"])
    scale_add = float(scale_add if scale_add is not None else DEFAULTS["scale_add"])

    if seed is None or seed == 'random' or int(seed) < 0:
        # The UI sends -1 for "random seed"; ComfyUI's INT widget rejects negatives.
        seed = random.randint(0, 2 ** 32 - 1)
    else:
        seed = int(seed)

    model_id = await get_latent_lab_model_id()
    checkpoint, client = await resolve_checkpoint(model_id, "ALGEBRA-COMFY")

    workflow = _build_workflow(
        prompt_a=prompt, prompt_b=prompt_b or "", prompt_c=prompt_c or "",
        negative_prompt=neg, checkpoint=checkpoint, encoder=encoder,
        scale_sub=scale_sub, scale_add=scale_add, width=w, height=h,
        steps=steps, cfg=cfg, seed=seed,
        sampler_name=DEFAULTS["sampler_name"], scheduler=DEFAULTS["scheduler"],
    )

    logger.info(
        "[ALGEBRA-COMFY] encoder=%s, sub=%s, add=%s, steps=%s, size=%sx%s, seed=%s, "
        "model=%s", encoder, scale_sub, scale_add, steps, w, h, seed, model_id,
    )

    result = await client.submit_and_track(workflow, timeout=900)

    reference = final_image(result, SAVE_REFERENCE_NODE_ID)
    outcome = final_image(result, SAVE_RESULT_NODE_ID)
    if outcome is None:
        raise Exception("Concept algebra (ComfyUI): no result image returned")
    if reference is None:
        raise Exception("Concept algebra (ComfyUI): no reference image returned")

    return {
        # Same marker as the Diffusers chunk on purpose: the route dispatches on
        # it and the frontend contract stays identical.
        'content_marker': 'diffusers_algebra_generated',
        'model_id': model_id,
        'reference_image': reference,
        'result_image': outcome,
        'algebra_data': {
            'encoder': encoder,
            'operation': 'A - scale_sub*B + scale_add*C',
            'scale_sub': scale_sub,
            'scale_add': scale_add,
            'l2_distance': announced(result, ALGEBRA_NODE_ID,
                                     'ai4artsed_algebra', 'l2_from_a'),
            'backend': 'comfyui',
            'timing_s': result.execution_time,
        },
        'seed': seed,
    }
