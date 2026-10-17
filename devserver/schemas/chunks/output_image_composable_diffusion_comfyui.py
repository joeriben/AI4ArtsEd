"""
Output Chunk: Composable Diffusion (ComfyUI)

ComfyUI counterpart of output_image_composable_diffusion_diffusers.py. Same output
contract, same content_marker — the route dispatch in schema_pipeline_routes.py and the
surface are unchanged. What differs is where the sampling happens: the
AI4ArtsEdComposableDiffusion custom node runs inside ComfyUI, so the model is loaded
under ComfyUI's memory management instead of diffusers' enable_model_cpu_offload().

The graph is built rather than stored, because the number of concepts is a property of
the run: the surface allows two to five, and each one becomes its own text encode and
its own link in the concept chain. A stored workflow with five slots would run five
transformer passes per step for a two-concept run.

`combine_at` carries the place the concepts are combined, which the node reads:
"score", one prediction per concept at every denoising step, or "conditioning", the
concepts' conditionings interpolated into one before the run. The Diffusers twin runs
the score place alone and refuses the other one.

Input: concepts (list of {prompt, weight}), negative_prompt, steps, cfg, seed, combine_at
Output: dict with image_data + composable_data, as the Diffusers twin returns it
"""

import json
import logging
import random

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_composable_diffusion_comfyui",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "60-120",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
}

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "",
    "seed": None,
    "normalize_weights": True,
    "combine_at": "score",
    "width": 1024,
    "height": 1024,
    "sampler_name": "euler",
    "scheduler": "normal",
}

COMBINE_PLACES = ("score", "conditioning")

# What a ComfyUI whose node class predates the input `combine_at` does with a
# graph that carries it: the input is dropped and the node samples in this place.
PLACE_WITHOUT_THE_INPUT = "score"

SAMPLER_NODE_ID = "8"
SAVE_IMAGE_NODE_ID = "4"


def _build_workflow(concepts, negative_prompt, checkpoint, width, height,
                    steps, cfg, seed, normalize_weights, combine_at,
                    sampler_name, scheduler):
    """The graph one run submits: one encode and one chain link per concept."""
    from schemas.engine.comfyui_chunk_support import (
        CLIP_NODE, checkpoint_loader, negative_encode, t5_length, text_encode,
        triple_clip_loader,
    )

    workflow = {
        "5": checkpoint_loader(checkpoint),
        "7": triple_clip_loader(),
        CLIP_NODE: t5_length(),
        "6": negative_encode(negative_prompt, title="CLIP Text Encode SD3 (Negative)"),
        "3": {
            "inputs": {"width": width, "height": height, "batch_size": 1},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "Empty Latent Image"},
        },
    }

    # Each concept reaches all three encoders with its own text, the same way the
    # main SD3.5 path does: the interception prompt goes to CLIP-L, CLIP-G and
    # T5-XXL unchanged (paper Fig. 2a), no per-encoder keyword splitting.
    previous_chain = None
    for index, concept in enumerate(concepts):
        text = str(concept.get("prompt") or "")
        weight = float(concept.get("weight", 1.0))
        encode_id = str(100 + index)
        chain_id = str(200 + index)
        workflow[encode_id] = text_encode(text, title=f"Concept {index + 1}")
        chain_inputs = {"conditioning": [encode_id, 0], "weight": weight}
        if previous_chain is not None:
            chain_inputs["concepts"] = [previous_chain, 0]
        workflow[chain_id] = {
            "inputs": chain_inputs,
            "class_type": "AI4ArtsEdConcept",
            "_meta": {"title": f"Concept {index + 1} @ {weight}"},
        }
        previous_chain = chain_id

    workflow[SAMPLER_NODE_ID] = {
        "inputs": {
            "model": ["5", 0],
            "concepts": [previous_chain, 0],
            "negative": ["6", 0],
            "latent_image": ["3", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "normalize_weights": bool(normalize_weights),
            "combine_at": combine_at,
        },
        "class_type": "AI4ArtsEdComposableDiffusion",
        "_meta": {"title": "Composable Diffusion"},
    }
    workflow["2"] = {
        "inputs": {"samples": [SAMPLER_NODE_ID, 0], "vae": ["5", 2]},
        "class_type": "VAEDecode",
        "_meta": {"title": "VAE Decode"},
    }
    workflow[SAVE_IMAGE_NODE_ID] = {
        "inputs": {"filename_prefix": "ComfyUI", "images": ["2", 0]},
        "class_type": "SaveImage",
        "_meta": {"title": "Save Image"},
    }
    return workflow


def _composition(concepts, cfg, normalize_weights, combine_at):
    """The weights as the node will read them, for the record the surface shows.

    In the score place the arithmetic is the Diffusers twin's, unchanged
    (gpu_service/services/diffusers_backend.py, generate_image_composable): a
    negative weight turns normalization off, because a signed mixture has no
    meaning, and every weight is a share of the guidance.

    In the conditioning place the node interpolates between the concepts
    instead of adding them, so only the ratio of the weights acts: there is
    nothing to normalize and no guidance per concept.
    """
    raw = [float(c.get("weight", 1.0)) for c in concepts]
    if combine_at == "conditioning":
        return raw, [], "interpolated"
    if normalize_weights and any(w < 0 for w in raw):
        normalize_weights = False
    if normalize_weights:
        total = sum(raw)
        weights = [w / total for w in raw] if total > 0 else list(raw)
        mode = "mixture"
    else:
        weights = list(raw)
        mode = "temperature"
    return weights, [cfg * w for w in weights], mode


async def execute(
    prompt: str = None,
    TEXT_1: str = None,
    concepts=None,
    negative_prompt: str = None,
    steps: int = None,
    cfg: float = None,
    seed: int = None,
    width: int = None,
    height: int = None,
    normalize_weights: bool = None,
    combine_at: str = None,
    **kwargs
) -> dict:
    """Returns dict (not bytes) — uses the extended Python chunk dict-return path."""
    from my_app.services.latent_lab_model import get_latent_lab_model_id
    from schemas.engine.comfyui_chunk_support import (
        final_image,
        node_accepts,
        resolve_checkpoint,
    )

    if concepts and isinstance(concepts, str):
        concepts = json.loads(concepts)
    if not concepts or len(concepts) < 2:
        raise ValueError("Need at least 2 concepts for composable diffusion")

    steps = steps if steps is not None else DEFAULTS["steps"]
    cfg = cfg if cfg is not None else DEFAULTS["cfg"]
    negative_prompt = negative_prompt or DEFAULTS["negative_prompt"]
    width = width or DEFAULTS["width"]
    height = height or DEFAULTS["height"]
    if normalize_weights is None:
        normalize_weights = DEFAULTS["normalize_weights"]
    if combine_at is None:
        combine_at = DEFAULTS["combine_at"]
    if combine_at not in COMBINE_PLACES:
        raise ValueError(
            f"combine_at is {combine_at!r}; the places the concepts can be "
            f"combined are {' and '.join(COMBINE_PLACES)}."
        )
    if seed is None or seed < 0:
        # The UI sends -1 for "random seed"; ComfyUI's INT widget rejects negatives.
        seed = random.randint(0, 2 ** 32 - 1)

    model_id = await get_latent_lab_model_id()
    checkpoint, client = await resolve_checkpoint(model_id, "COMPOSABLE-COMFY")

    # ComfyUI drops a submitted input its running node class does not declare,
    # without an error, so a ComfyUI started before the node file gained
    # `combine_at` would sample in PLACE_WITHOUT_THE_INPUT while the record
    # below names the place that was asked for.
    if combine_at != PLACE_WITHOUT_THE_INPUT and await node_accepts(
            client.base_url, "AI4ArtsEdComposableDiffusion", "combine_at",
            "COMPOSABLE-COMFY") is False:
        raise Exception(
            f"The running ComfyUI holds AI4ArtsEdComposableDiffusion without "
            f"the input combine_at, so it would combine the concepts in the place "
            f"{PLACE_WITHOUT_THE_INPUT!r} while the record said {combine_at!r}. "
            f"Restart ai4artsed-comfyui.service: ComfyUI reads a node file at "
            f"process start."
        )

    weights, guidance, mode = _composition(concepts, cfg, normalize_weights, combine_at)

    workflow = _build_workflow(
        concepts=concepts, negative_prompt=negative_prompt, checkpoint=checkpoint,
        width=width, height=height, steps=steps, cfg=cfg, seed=seed,
        normalize_weights=normalize_weights, combine_at=combine_at,
        sampler_name=DEFAULTS["sampler_name"], scheduler=DEFAULTS["scheduler"],
    )

    logger.info(
        "[COMPOSABLE-COMFY] %d concepts, combine_at=%s, mode=%s, weights=%s, "
        "guidance=%s, negated=%d, steps=%s, size=%sx%s, seed=%s, cfg=%s",
        len(concepts), combine_at, mode, [f"{w:.2f}" for w in weights],
        [f"{v:.2f}" for v in guidance], sum(1 for w in weights if w < 0),
        steps, width, height, seed, cfg,
    )

    result = await client.submit_and_track(workflow, timeout=900)

    image_base64 = final_image(result, SAVE_IMAGE_NODE_ID)
    if image_base64 is None:
        raise Exception("Composable diffusion (ComfyUI): no image returned")

    return {
        # Same marker as the Diffusers chunk on purpose: the route dispatches on
        # it and the frontend contract stays identical.
        'content_marker': 'diffusers_composable_generated',
        'image_data': image_base64,
        'media_type': 'image',
        'backend': 'comfyui',
        'model_id': model_id,
        'seed': seed,
        'composable_data': {
            'concept_count': len(concepts),
            'weights_used': weights,
            'guidance_used': guidance,
            'composition_mode': mode,
            'combine_at': combine_at,
            'negated_count': sum(1 for w in weights if w < 0),
            'timing_s': result.execution_time,
        },
    }
