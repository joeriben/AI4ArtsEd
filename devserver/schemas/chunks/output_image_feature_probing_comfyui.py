"""
Output Chunk: Feature Probing (ComfyUI)

ComfyUI counterpart of output_image_feature_probing_diffusers.py. Same output
contract, same content_marker — the route dispatch and the surface are unchanged.
What differs is where the measurement happens: the AI4ArtsEdSD3 node family reads
the three text encoders apart inside ComfyUI, so the model is loaded under
ComfyUI's memory management.

The instrument runs in two passes over one prompt pair, and the second pass is a
second call: with no dimensions named it measures and generates prompt A, with
dimensions named it carries those from B into A at the same seed. What separates
the two pictures is then the selection and nothing else.

The first pass measures on every encoder at once: four more probe nodes read
the same two encodes and feed nothing, and the page switches between their
lists when the encoder changes, with no run. Until 2026-09-28 a change of
encoder on the page started a whole new picture of prompt A only to measure.

Measurement and writing share one window: the positions the two prompts fill.
Text encoders pad — CLIP to 77, T5 to at least 77 — and the encoder's answer to
that padding differs between two prompts for reasons that say nothing about how
the prompts differ.

Input: prompt (A), prompt_b (B), probing_encoder, transfer_dims
Output: dict with base64 image and the per-dimension measurement
"""

import logging
import random

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_feature_probing_comfyui",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "25-45",
    "requires_gpu": True,
    "gpu_vram_mb": 12000,
}

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "",
    "seed": None,
    "width": 1024,
    "height": 1024,
    "probing_encoder": "all",
    "sampler_name": "euler",
    "scheduler": "normal",
}

SAVE_NODE_ID = "40"
PROBE_NODE_ID = "12"
# The first pass's measurement on each encoder, beside the one that feeds the
# sampler. The probe is an output node, so ComfyUI runs these although nothing
# reads their result.
MEASURE_NODE_IDS = {"clip_l": "51", "clip_g": "52", "t5": "53", "all": "54"}


def _build_workflow(prompt_a, prompt_b, negative_prompt, checkpoint, encoder,
                    transfer_dims, transfer, width, height, steps, cfg, seed,
                    sampler_name, scheduler, measure_all=False):
    """The graph one run submits: two encodes, one measurement, one branch, and
    with `measure_all` a measurement on every encoder beside it."""
    from schemas.engine.comfyui_chunk_support import (
        CLIP_NODE, checkpoint_loader, negative_encode, sd3_assemble, sd3_encode,
        t5_length, triple_clip_loader,
    )

    workflow = {
        "5": checkpoint_loader(checkpoint),
        "7": triple_clip_loader(),
        CLIP_NODE: t5_length(),
        "10": sd3_encode(prompt_a, title="Encode A"),
        "11": sd3_encode(prompt_b, title="Encode B"),
        PROBE_NODE_ID: {
            "inputs": {
                "a": ["10", 0], "b": ["11", 0],
                "encoder": encoder,
                "transfer_dims": transfer_dims,
                "transfer": transfer,
            },
            "class_type": "AI4ArtsEdSD3Probe",
            "_meta": {"title": "Where A and B differ"},
        },
        "13": sd3_assemble([PROBE_NODE_ID, 0], "Assemble"),
        "6": negative_encode(negative_prompt),
        "3": {
            "inputs": {"width": width, "height": height, "batch_size": 1},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "Empty latent"},
        },
        "20": {
            "inputs": {
                "model": ["5", 0], "positive": ["13", 0], "negative": ["6", 0],
                "latent_image": ["3", 0], "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": sampler_name, "scheduler": scheduler, "denoise": 1,
            },
            "class_type": "KSampler",
            "_meta": {"title": "Sample"},
        },
        "22": {
            "inputs": {"samples": ["20", 0], "vae": ["5", 2]},
            "class_type": "VAEDecode",
            "_meta": {"title": "Decode"},
        },
        SAVE_NODE_ID: {
            "inputs": {"filename_prefix": "ComfyUI", "images": ["22", 0]},
            "class_type": "SaveImage",
            "_meta": {"title": "Save"},
        },
    }
    if measure_all:
        for name, node_id in MEASURE_NODE_IDS.items():
            workflow[node_id] = {
                "inputs": {
                    "a": ["10", 0], "b": ["11", 0],
                    "encoder": name,
                    "transfer_dims": "",
                    "transfer": False,
                },
                "class_type": "AI4ArtsEdSD3Probe",
                "_meta": {"title": f"Where A and B differ on {name}"},
            }
    return workflow


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
    """Returns dict (not bytes) — uses the extended Python chunk dict-return path."""
    from my_app.services.latent_lab_model import get_latent_lab_model_id
    from schemas.engine.comfyui_chunk_support import (
        announced,
        final_image,
        resolve_checkpoint,
    )

    # No VRAM gate here. The one the Diffusers chunk carries names its own
    # reason: T5-XXL activation memory at max_sequence_length=512 across several
    # passes, on top of a resident pipeline (latent_lab_capabilities.py). Since
    # 09.09.2026 this path runs T5 at 512 too, so half of that reason holds here
    # as well; what is left of the difference is ComfyUI's partial loading, which
    # keeps on the card only what a pass needs. The config asks for 12 GB where
    # the Diffusers config asked for 30, and nobody has run this path on a card
    # that small.

    prompt = prompt or TEXT_1 or kwargs.get('PREVIOUS_OUTPUT', '')
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for Dimension Explorer")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (
        NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))
    encoder = probing_encoder or DEFAULTS["probing_encoder"]

    if seed is None or seed == 'random' or int(seed) < 0:
        # The UI sends -1 for "random seed"; ComfyUI's INT widget rejects negatives.
        seed = random.randint(0, 2 ** 32 - 1)
    else:
        seed = int(seed)

    # ComfyUI has no list widget, so the selection travels as text. Which pass
    # this is travels separately: a second pass that names no dimension is a run
    # that moved nothing and says so, and only a caller that named no list at all
    # asked for the first pass.
    transfer = transfer_dims is not None
    named = ",".join(str(int(d)) for d in (transfer_dims or []))

    model_id = await get_latent_lab_model_id()
    checkpoint, client = await resolve_checkpoint(model_id, "PROBING-COMFY")

    workflow = _build_workflow(
        prompt_a=prompt, prompt_b=prompt_b or "", negative_prompt=neg,
        checkpoint=checkpoint, encoder=encoder, transfer_dims=named,
        transfer=transfer, measure_all=not transfer,
        width=w, height=h, steps=steps, cfg=cfg_scale, seed=seed,
        sampler_name=DEFAULTS["sampler_name"], scheduler=DEFAULTS["scheduler"],
    )

    logger.info(
        "[PROBING-COMFY] encoder=%s, transfer=%s, steps=%s, size=%sx%s, seed=%s, "
        "model=%s", encoder, len(transfer_dims or []), steps, w, h, seed, model_id,
    )

    result = await client.submit_and_track(workflow, timeout=900)

    image = final_image(result, SAVE_NODE_ID)
    if image is None:
        raise Exception("Dimension Explorer (ComfyUI): no image returned")

    measured = announced(result, PROBE_NODE_ID, "ai4artsed_probe")
    if measured is None:
        raise Exception(
            "Dimension Explorer (ComfyUI): the probe node announced no measurement. "
            "An image without it is not this instrument."
        )
    if not transfer:
        by_encoder = {}
        for name, node_id in MEASURE_NODE_IDS.items():
            said = announced(result, node_id, "ai4artsed_probe")
            if said is None:
                raise Exception(
                    f"Dimension Explorer (ComfyUI): the measurement on {name} was "
                    f"not announced."
                )
            by_encoder[name] = {key: said[key] for key in
                                ("top_dims", "top_values", "embed_dim", "nonzero_dims")}
        measured["by_encoder"] = by_encoder

    return {
        # Same marker as the Diffusers chunk on purpose: the route dispatches on
        # it and the frontend contract stays identical.
        'content_marker': 'diffusers_probing_generated',
        'image_data': image,
        'media_type': 'image',
        'backend': 'comfyui',
        'model_id': model_id,
        'seed': seed,
        'probing_data': measured,
        'parameters': {
            'width': w,
            'height': h,
            'steps': steps,
            'cfg_scale': cfg_scale,
        },
    }
