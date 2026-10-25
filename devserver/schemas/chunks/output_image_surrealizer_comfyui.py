"""
Output Chunk: Surrealizer (ComfyUI)

ComfyUI counterpart of output_image_surrealizer_diffusers.py. Same output contract,
same content_marker -- the route dispatch and the surfaces are unchanged. What differs
is where the fusion happens: AI4ArtsEdSD3Fusion of the AI4ArtsEdSD3 node family adds
T5's reading to the CLIP block inside ComfyUI, so the model is loaded under ComfyUI's
memory management and the GPU service computes nothing.

The arithmetic is the twin's: on the first 77 positions w_clip * CLIP + w_t5 * T5, T5's
remainder as the tail, the weights by strategy (centered_fade, legacy, dual_alpha,
normalized, original), nothing clamped. The negative prompt is fused the same way at
the same alpha, an empty negative as the encoding of the empty string. T5 stands at
the platform's length, 512 positions or the text's own past that, except under
`original`, which runs T5 at the length of its own text on each side and CLIP-L
alone, as the 2025 workflow did. Alpha runs from -75 to 75, the range the surfaces
reach; ComfyUI refuses a graph carrying a value outside it before anything runs.

Since 2026-09-15 the Encoder Fusion surface sends three factors instead of an alpha
and a strategy: `factor_a` on
the CLIP block, `factor_b` for T5's rows 0..76 mixed into it cell by cell, `factor_c`
on the T5 block, `t5_rows` for the layout of that block, "full" (rows 0..511 under
the CLIP rows, 589 in all, the layout SD 3.5 runs on its own) or "tail" (rows 77.., the
layout of 2025), and, since 2026-09-17, `pooled` for the pooled vector, "clip" (as the
two CLIP encoders compute it) or "zero" (zeros in its place). AI4ArtsEdSD3ThreeFactors
of the same node family carries them; the negative goes the same way under the same
factors, layout and pooled vector. The three come together or not at
all, and never alongside an alpha or a strategy. `alpha_factor` and `fusion_strategy`
stay for the Canvas and for stored runs.

The research options the twin reads after '#' in the strategy name (path=sphere,
t5len, pooled, neg, pos0, fuse_only, hook, cfg_interval, cap, capdir, rng, band) stay
on the twin; the twin's `pooled=zero` option is its own switch, read only there, and
this chunk's parameter `pooled` is the surface's: a name carrying one is refused with the option named, so that no run is
attributed to a mechanism that did not run.

Input: prompt (TEXT_1), alpha_factor + fusion_strategy or factor_a/b/c + t5_rows + pooled,
optional clip_prompt/t5_prompt
Output: dict with base64 image data + generation metadata
"""

import logging
import math
import random

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_surrealizer_comfyui",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "20-40",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
}

DEFAULTS = {
    "steps": 25,
    "cfg": 5.5,
    "negative_prompt": "",
    "seed": None,
    "width": 1024,
    "height": 1024,
    "alpha_factor": None,
    "fusion_strategy": "dual_alpha",
    "t5_rows": "full",
    "pooled": "clip",
    "sampler_name": "euler",
    "scheduler": "normal",
}

# The fusions the Surrealizer offers, by name. The node file carries one more
# (comfyui_nodes/ai4artsed_sd3_conditioning.py::FUSIONS): `slerp`, which the
# Fusion Workbench puts on its strategy axis and the Surrealizer does not (the
# sphere is off this instrument); a test holds the lists together.
FUSIONS = ("centered_fade", "legacy", "dual_alpha", "normalized", "original")

SAVE_NODE_ID = "40"
FUSION_NODE_ID = "12"


def _fusion_named(fusion_strategy):
    """The bare name of the fusion, or the reason the name cannot run here."""
    base, *options = str(fusion_strategy or "").split("#")
    if options:
        raise ValueError(
            f"fusion_strategy {fusion_strategy!r}: the options after '#' "
            f"({', '.join(options)}) run on the Diffusers twin alone "
            f"(output config surrealization_diffusers)"
        )
    if base not in FUSIONS:
        raise ValueError(f"fusion_strategy {base!r} is none of {', '.join(FUSIONS)}")
    return base


# The two layouts of the T5 block under the CLIP block (the node's T5_ROWS).
T5_ROWS = ("full", "tail")
# The pooled vector: CLIP's own, or zeros in its place (the node's POOLED).
POOLED = ("clip", "zero")


def _factors_named(factor_a, factor_b, factor_c, t5_rows, pooled=None):
    """The three factors as floats, the layout and the pooled vector by name,
    or the reason they cannot run: all three together, each a number, the
    layout one of T5_ROWS (left out: full), the pooled vector one of POOLED
    (left out: clip)."""
    given = {"factor_a": factor_a, "factor_b": factor_b, "factor_c": factor_c}
    missing = [name for name, value in given.items() if value is None]
    if missing:
        raise ValueError(f"the three factors run together; {', '.join(missing)} not given")
    named = []
    for name, value in given.items():
        # float() takes True and "nan" as well; neither is a factor.
        try:
            number = float(value) if not isinstance(value, bool) else math.nan
        except (TypeError, ValueError):
            number = math.nan
        if not math.isfinite(number):
            raise ValueError(f"{name}={value!r} is not a number")
        named.append(number)
    rows = t5_rows or DEFAULTS["t5_rows"]
    if rows not in T5_ROWS:
        raise ValueError(f"t5_rows {rows!r}: one of {', '.join(T5_ROWS)}")
    pool = pooled or DEFAULTS["pooled"]
    if pool not in POOLED:
        raise ValueError(f"pooled {pool!r}: one of {', '.join(POOLED)}")
    return (named[0], named[1], named[2], rows, pool)


def _build_workflow(clip_prompt, t5_prompt, negative_prompt, checkpoint, strategy,
                    alpha, width, height, steps, cfg, seed, sampler_name, scheduler,
                    factors=None):
    """The graph one run submits: the encodes, a fusion each for the positive and
    the negative, one sampler branch. With `factors` (a, b, c, t5_rows, pooled)
    the two fusion nodes are AI4ArtsEdSD3ThreeFactors instead, and `strategy`
    and `alpha` are not read."""
    from schemas.engine.comfyui_chunk_support import (
        CLIP_NODE, checkpoint_loader, sd3_assemble, sd3_encode, sd3_fusion,
        sd3_three_factors, t5_length, triple_clip_loader,
    )

    # T5 at the platform's length, except under `original`, where T5 runs at the
    # length of its own text: the encoders then read the loader directly.
    clip_from = "7" if strategy == "original" else CLIP_NODE
    if factors is not None:
        a, b, c, rows, pool = factors
        fuse_positive = sd3_three_factors(["10", 0], a, b, c, rows, pool, "Three factors")
        fuse_negative = sd3_three_factors(["14", 0], a, b, c, rows, pool,
                                          "Three factors on the negative")
    else:
        fuse_positive = sd3_fusion(["10", 0], ["10", 0], alpha, strategy, "Fuse CLIP and T5")
        fuse_negative = sd3_fusion(["14", 0], ["14", 0], alpha, strategy,
                                   "Fuse the negative the same way")
    graph = {
        "5": checkpoint_loader(checkpoint),
        "7": triple_clip_loader(),
        "10": sd3_encode(clip_prompt, clip_node=clip_from, title="Encode the CLIP side",
                         empty_padding="empty_prompt"),
        FUSION_NODE_ID: fuse_positive,
        "13": sd3_assemble([FUSION_NODE_ID, 0], "Positive"),
        "14": sd3_encode(negative_prompt, clip_node=clip_from, title="Encode the negative",
                         empty_padding="empty_prompt"),
        "15": fuse_negative,
        "16": sd3_assemble(["15", 0], "Negative"),
        "3": {
            "inputs": {"width": width, "height": height, "batch_size": 1},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "Empty latent"},
        },
        "20": {
            "inputs": {
                "model": ["5", 0], "positive": ["13", 0], "negative": ["16", 0],
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
    if strategy != "original":
        graph[CLIP_NODE] = t5_length()
    if t5_prompt != clip_prompt:
        # The adapted prompts: T5 reads its own text. With one prompt the same
        # encode feeds both sides, and the encoders run once.
        graph["11"] = sd3_encode(t5_prompt, clip_node=clip_from, title="Encode the T5 side",
                                 empty_padding="empty_prompt")
        graph[FUSION_NODE_ID]["inputs"]["t5_side"] = ["11", 0]
    return graph


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
    alpha_factor: float = None,
    fusion_strategy: str = None,
    t5_prompt: str = None,
    clip_prompt: str = None,
    loras: list = None,
    factor_a: float = None,
    factor_b: float = None,
    factor_c: float = None,
    t5_rows: str = None,
    pooled: str = None,
    **kwargs
) -> dict:
    """Returns dict with base64 image -- uses the extended Python chunk dict-return path."""
    from my_app.services.latent_lab_model import get_latent_lab_model_id
    from schemas.engine.comfyui_chunk_support import (
        final_image,
        resolve_checkpoint,
    )

    prompt = prompt or TEXT_1 or kwargs.get('PREVIOUS_OUTPUT', '')
    # The adapted prompts hand each encoder its own text: the orchestrator writes
    # them (my_app/services/surrealizer_original.py) and passes both down.
    # `prompt` is the CLIP side, `t5_prompt` the T5 side.
    if clip_prompt and clip_prompt.strip():
        prompt = clip_prompt
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for Surrealizer generation")
    if loras:
        # The Diffusers twin applied adapters; this graph carries none, and a
        # run that dropped them would show a picture the adapter never touched.
        raise ValueError(
            "The Surrealizer's ComfyUI graph carries no LoRA; adapters run on the "
            "sd35_large config (views/latent_lab/lora_reach.vue)"
        )

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (
        NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))
    # The three factors, where the run names any of them. They read one prompt
    # and take the place of alpha and strategy: a run naming both would be a
    # run attributed to two mechanisms.
    factors = None
    if any(v is not None for v in (factor_a, factor_b, factor_c, t5_rows, pooled)):
        factors = _factors_named(factor_a, factor_b, factor_c, t5_rows, pooled)
        if alpha_factor is not None or fusion_strategy is not None:
            raise ValueError(
                "the three factors and alpha_factor/fusion_strategy do not run "
                "together; send one of the two"
            )
        if (t5_prompt or "").strip() or (clip_prompt or "").strip():
            raise ValueError("the three factors read one prompt for all three encoders")
        strategy = None
    else:
        strategy = _fusion_named(fusion_strategy or DEFAULTS["fusion_strategy"])

    # The original fusion is defined by its TWO texts. One prompt for both
    # encoders would still produce an image, attributed to a mechanism that did
    # not run; the twin stops here as well.
    if strategy == "original" and not (t5_prompt or "").strip():
        raise ValueError(
            "original fusion needs its own T5 text; "
            "one prompt for both encoders is a different mechanism"
        )
    t5_text = t5_prompt if t5_prompt else prompt

    # Auto-generate alpha when not provided (e.g. Canvas random node)
    if factors is None:
        if alpha_factor is None:
            alpha_factor = random.randint(20, 30)
            logger.info(f"[SURREALIZER-COMFY] Auto-generated alpha_factor: {alpha_factor}")
        alpha_factor = float(alpha_factor)

    if seed is None or seed == 'random' or int(seed) < 0:
        # The UI sends -1 for "random seed"; ComfyUI's INT widget rejects negatives.
        seed = random.randint(0, 2 ** 32 - 1)
    else:
        seed = int(seed)

    model_id = await get_latent_lab_model_id()
    checkpoint, client = await resolve_checkpoint(model_id, "SURREALIZER-COMFY")

    workflow = _build_workflow(
        clip_prompt=prompt, t5_prompt=t5_text, negative_prompt=neg,
        checkpoint=checkpoint, strategy=strategy, alpha=alpha_factor,
        width=w, height=h, steps=steps, cfg=cfg_scale, seed=seed,
        sampler_name=DEFAULTS["sampler_name"], scheduler=DEFAULTS["scheduler"],
        factors=factors,
    )

    if factors is not None:
        logger.info(
            "[SURREALIZER-COMFY] a=%s, b=%s, c=%s, t5_rows=%s, pooled=%s, steps=%s, size=%sx%s, "
            "seed=%s, model=%s", *factors, steps, w, h, seed, model_id,
        )
    else:
        logger.info(
            "[SURREALIZER-COMFY] strategy=%s, alpha=%s, steps=%s, size=%sx%s, seed=%s, "
            "model=%s, per_encoder_prompts=%s",
            strategy, alpha_factor, steps, w, h, seed, model_id, bool(t5_prompt),
        )

    result = await client.submit_and_track(workflow, timeout=None)

    image = final_image(result, SAVE_NODE_ID)
    if image is None:
        raise Exception("Surrealizer (ComfyUI): no image returned")

    return {
        'content_marker': 'diffusers_generated',
        'image_data': image,
        'media_type': 'image',
        'backend': 'comfyui',
        'model_id': model_id,
        'seed': seed,
        'parameters': {
            'width': w,
            'height': h,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'alpha_factor': alpha_factor,
            'fusion_strategy': 'three_factor' if factors is not None else strategy,
            'clip_prompt': prompt,
            't5_prompt': t5_prompt,
            **({'factor_a': factors[0], 'factor_b': factors[1], 'factor_c': factors[2],
                't5_rows': factors[3], 'pooled': factors[4]} if factors is not None else {}),
        }
    }
