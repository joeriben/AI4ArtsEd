"""
Output Chunk: Attention Cartography (ComfyUI)

ComfyUI counterpart of output_image_attention_cartography_diffusers.py. Same output
contract, same content_marker -- the route dispatch and the surface are unchanged.
What differs is where the attention is read: AI4ArtsEdAttentionCapture patches the
model inside ComfyUI, the readout rides along with the sampler, and
AI4ArtsEdAttentionMaps writes maps and tokens to a file the ws client fetches with
the picture. The GPU service computes nothing of it.

What is read is the twin's reading (gpu_service/services/attention_processors_sd3.py):
on the chosen joint blocks at the chosen steps, softmax(QK^T / sqrt(d)) by hand, the
weight of every image position on every text position, averaged over negative and
positive and over the heads, cut to the columns that carry a word, quantized to
ten-thousandths. The picture is made with ComfyUI's own attention beside it.

Input: prompt (TEXT_1), capture_layers, capture_every_n_steps
Output: dict with base64 image + attention_data (tokens, maps, spatial info)
"""

import json
import logging
import random

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_attention_cartography_comfyui",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "30-50",
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
    "capture_layers": [3, 9, 17],
    "capture_every_n_steps": 1,
    "sampler_name": "euler",
    "scheduler": "normal",
}

SAVE_NODE_ID = "40"
CAPTURE_NODE_ID = "30"
MAPS_NODE_ID = "31"

# What the maps file has to carry; the surface reads every one of these.
RECORD_KEYS = (
    "tokens", "word_groups", "tokens_t5", "word_groups_t5", "clip_token_count",
    "attention_maps", "spatial_resolution", "image_resolution", "capture_layers",
    "capture_steps",
)


def _layers_text(capture_layers):
    """The node takes its block indices as "3,9,17"; the surface sends a list."""
    if isinstance(capture_layers, str):
        parts = [p.strip() for p in capture_layers.split(",") if p.strip()]
    else:
        parts = [str(p).strip() for p in capture_layers]
    for part in parts:
        if not part.isdigit():
            raise ValueError(f"capture_layers {capture_layers!r}: {part!r} is no block index")
    if not parts:
        raise ValueError("capture_layers names no block")
    return ",".join(parts)


def _build_workflow(prompt, negative_prompt, checkpoint, layers_text, every_n,
                    width, height, steps, cfg, seed, sampler_name, scheduler):
    """The graph one run submits: the platform's SD 3.5 graph with the capture
    on the model and the maps written after the sampler."""
    from schemas.engine.comfyui_chunk_support import (
        CLIP_NODE, checkpoint_loader, negative_encode, t5_length, text_encode,
        triple_clip_loader,
    )
    return {
        "5": checkpoint_loader(checkpoint),
        "7": triple_clip_loader(),
        CLIP_NODE: t5_length(),
        "1": text_encode(prompt, title="Positive"),
        "6": negative_encode(negative_prompt),
        CAPTURE_NODE_ID: {
            "inputs": {
                "model": ["5", 0], "clip": [CLIP_NODE, 0], "text": prompt,
                "capture_layers": layers_text, "steps": steps,
                "capture_every_n_steps": every_n,
            },
            "class_type": "AI4ArtsEdAttentionCapture",
            "_meta": {"title": "Read the attention"},
        },
        "3": {
            "inputs": {"width": width, "height": height, "batch_size": 1},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "Empty latent"},
        },
        "20": {
            "inputs": {
                "model": [CAPTURE_NODE_ID, 0], "positive": ["1", 0], "negative": ["6", 0],
                "latent_image": ["3", 0], "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": sampler_name, "scheduler": scheduler, "denoise": 1,
            },
            "class_type": "KSampler",
            "_meta": {"title": "Sample"},
        },
        MAPS_NODE_ID: {
            "inputs": {"readout": [CAPTURE_NODE_ID, 1], "samples": ["20", 0],
                       "filename_prefix": "ai4artsed_attention"},
            "class_type": "AI4ArtsEdAttentionMaps",
            "_meta": {"title": "Write the maps"},
        },
        "22": {
            "inputs": {"samples": [MAPS_NODE_ID, 0], "vae": ["5", 2]},
            "class_type": "VAEDecode",
            "_meta": {"title": "Decode"},
        },
        SAVE_NODE_ID: {
            "inputs": {"filename_prefix": "ComfyUI", "images": ["22", 0]},
            "class_type": "SaveImage",
            "_meta": {"title": "Save"},
        },
    }


def attention_record(result):
    """The maps file of the run, parsed and checked for the keys the surface reads."""
    files = [f for f in result.media_files
             if f.media_type == "attention" and f.node_id == MAPS_NODE_ID and f.data]
    if not files:
        raise RuntimeError(
            "Attention Cartography (ComfyUI): the run announced no maps file "
            f"(prompt {result.prompt_id})"
        )
    try:
        record = json.loads(files[0].data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"Attention Cartography (ComfyUI): the maps file {files[0].filename} "
            f"is no JSON: {exc}"
        ) from exc
    missing = [key for key in RECORD_KEYS if key not in record]
    if missing:
        raise RuntimeError(
            f"Attention Cartography (ComfyUI): the maps file lacks {', '.join(missing)}"
        )
    if not record["tokens"] or not record["attention_maps"]:
        raise RuntimeError(
            f"Attention Cartography (ComfyUI): the maps file {files[0].filename} "
            f"carries {len(record['tokens'])} tokens and maps of "
            f"{len(record['attention_maps'])} steps"
        )
    return record


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
    capture_layers: list = None,
    capture_every_n_steps: int = None,
    **kwargs
) -> dict:
    """Returns dict with base64 image + attention data -- uses the extended Python chunk dict-return path."""
    from my_app.services.latent_lab_capabilities import get_latent_lab_capabilities
    from my_app.services.latent_lab_model import get_latent_lab_model_id
    from schemas.engine.comfyui_chunk_support import (
        final_image,
        resolve_checkpoint,
    )

    caps = await get_latent_lab_capabilities()
    if not caps.get("attention_cartography"):
        threshold = caps.get("threshold_gb", 40)
        vram = caps.get("total_vram_gb")
        vram_str = f"{vram:.0f} GB" if vram else "unbekannt"
        raise RuntimeError(
            f"Attention Cartography ist auf dieser GPU nicht verfügbar "
            f"(erkannt: {vram_str}, benötigt: ≥{threshold:.0f} GB). "
            f"Override: AI4ARTSED_FORCE_HEAVY_LATENT_LAB=true"
        )

    prompt = prompt or TEXT_1 or kwargs.get('PREVIOUS_OUTPUT', '')
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for Attention Cartography")

    steps = int(steps if steps is not None else (STEPS if STEPS is not None else DEFAULTS["steps"]))
    cfg_scale = float(cfg if cfg is not None else (CFG if CFG is not None else DEFAULTS["cfg"]))
    neg = negative_prompt if negative_prompt is not None else (
        NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"])
    w = int(width if width is not None else (WIDTH if WIDTH is not None else DEFAULTS["width"]))
    h = int(height if height is not None else (HEIGHT if HEIGHT is not None else DEFAULTS["height"]))
    layers_text = _layers_text(capture_layers or DEFAULTS["capture_layers"])
    every_n = int(capture_every_n_steps if capture_every_n_steps is not None
                  else DEFAULTS["capture_every_n_steps"])
    if w % 16 or h % 16:
        # The model pads a latent of odd size to its patch, and the maps then
        # lie on a grid the picture has not got; the twin's pipeline refused
        # the same sizes before sampling.
        raise ValueError(
            f"Attention Cartography: width and height have to be multiples of 16, "
            f"got {w}x{h}"
        )
    if steps < 1 or every_n < 1:
        raise ValueError(f"steps ({steps}) and capture_every_n_steps ({every_n}) must be at least 1")

    if seed is None or seed == 'random' or int(seed) < 0:
        # The UI sends -1 for "random seed"; ComfyUI's INT widget rejects negatives.
        seed = random.randint(0, 2 ** 32 - 1)
    else:
        seed = int(seed)

    model_id = await get_latent_lab_model_id()
    checkpoint, client = await resolve_checkpoint(model_id, "ATTENTION-COMFY")

    workflow = _build_workflow(
        prompt=prompt, negative_prompt=neg, checkpoint=checkpoint,
        layers_text=layers_text, every_n=every_n, width=w, height=h, steps=steps,
        cfg=cfg_scale, seed=seed, sampler_name=DEFAULTS["sampler_name"],
        scheduler=DEFAULTS["scheduler"],
    )

    logger.info(
        "[ATTENTION-COMFY] layers=%s, every_n=%s, steps=%s, size=%sx%s, seed=%s, model=%s",
        layers_text, every_n, steps, w, h, seed, model_id,
    )

    result = await client.submit_and_track(workflow, timeout=None)

    image = final_image(result, SAVE_NODE_ID)
    if image is None:
        raise Exception("Attention Cartography (ComfyUI): no image returned")
    record = attention_record(result)

    logger.info(
        "[ATTENTION-COMFY] %d timesteps captured, tokens=%d, spatial=%s",
        len(record["attention_maps"]), len(record["tokens"]), record["spatial_resolution"],
    )

    return {
        'content_marker': 'diffusers_attention_generated',
        'image_data': image,
        'media_type': 'image',
        'backend': 'comfyui',
        'model_id': model_id,
        'seed': seed,
        'attention_data': {key: record[key] for key in RECORD_KEYS},
        'parameters': {
            'width': w,
            'height': h,
            'steps': steps,
            'cfg_scale': cfg_scale,
        }
    }
