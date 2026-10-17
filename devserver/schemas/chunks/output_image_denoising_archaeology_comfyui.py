"""
Output Chunk: Denoising Archaeology (ComfyUI)

ComfyUI counterpart of output_image_denoising_archaeology_diffusers.py.

Same output contract, same content_marker — the frontend and the route dispatch in
schema_pipeline_routes.py are unchanged. What differs is where the sampling happens:
the AI4ArtsEdDenoisingArchaeology custom node runs inside ComfyUI, so the model is
loaded under ComfyUI's memory management (partial loading / weight streaming) instead
of diffusers' enable_model_cpu_offload().

Why this chunk exists: on 24 GB (4090) and 32 GB (5090) cards the Diffusers path forced
SD3.5-Medium via a < 50 GB threshold in latent_lab_model.py. This chunk was the probe
for whether SD3.5-Large runs there under ComfyUI; since 2026-09-18 the resolver answers
Large on every card, and the override AI4ARTSED_LATENT_LAB_MODEL is gone
(docs/DEVELOPMENT_DECISIONS.md).

It takes the same three per-run choices as the Diffusers chunk, so a run can be put
side by side with its Diffusers twin: `backbone` (which net denoises), `scheduler`
(which rule walks the path) and `shift` (how the steps are spread along a straight
flow-matching path). The vocabularies differ between the two backends and the
translation is SCHEDULER_TO_COMFY below.

Input: prompt (TEXT_1)
Output: dict with final image + per-step JPEG frames
"""

import base64
import logging
import random

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_image_denoising_archaeology_comfyui",
    "media_type": "image",
    "output_format": "png",
    "estimated_duration_seconds": "35-55",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
}

DEFAULTS = {
    "steps": 25,
    "cfg": 4.5,
    "negative_prompt": "blurry, bad quality, watermark, text, distorted",
    "seed": 123456789,
    "capture_every_n": 1,
    "width": 1024,
    "height": 1024,
    # ComfyUI's own defaults on its two sampling axes. A run that names no
    # scheduler, or one SCHEDULER_TO_COMFY does not know, walks on these.
    "sampler_name": "euler",
    "scheduler": "normal",
}

ARCHAEOLOGY_NODE_ID = "8"
SAVE_IMAGE_NODE_ID = "4"
MODEL_SAMPLING_NODE_ID = "9"

# Diffusers scheduler class name -> ComfyUI (sampler_name, scheduler).
#
# The two backends cut the same decision differently. Diffusers names ONE class
# that carries both the update rule and the sigma schedule; ComfyUI names the
# update rule in `sampler_name` and the sigma schedule in `scheduler`. Every
# entry here is therefore a pair, and the second element is the sigma schedule.
#
# Why "normal" throughout: on the diffusers side these classes are always built
# with from_config(current.config) — see _install_run_scheduler in
# gpu_service/services/diffusers_backend.py — so they inherit the pipeline's own
# scheduler config, in which use_karras_sigmas is false. No such run walks a
# Karras schedule, and mapping any of them onto ComfyUI's "karras" would change
# the very thing the two paths are compared on. ComfyUI's "normal" reads the
# sigmas off the model itself, which is the counterpart of that default.
#
# The keys are the fourteen names this instrument's surface used to send, read
# off the picker that stood there until 2026-08-31 (commit 3e13d74b^). The
# service still takes the parameter, so a probe or a replay script can name one.
#
# Two entries are near, not exact, and say so:
#   DPMSolverSinglestepScheduler — diffusers' DPM++ 2S is deterministic;
#       ComfyUI ships the ancestral 2S only, which puts noise back each step.
#   PNDMScheduler — ComfyUI ships iPNDM (improved PNDM), not PNDM.
SCHEDULER_TO_COMFY = {
    "EulerDiscreteScheduler":          ("euler", "normal"),
    "EulerAncestralDiscreteScheduler": ("euler_ancestral", "normal"),
    "HeunDiscreteScheduler":           ("heun", "normal"),
    "LMSDiscreteScheduler":            ("lms", "normal"),
    "KDPM2DiscreteScheduler":          ("dpm_2", "normal"),
    "KDPM2AncestralDiscreteScheduler": ("dpm_2_ancestral", "normal"),
    "DPMSolverMultistepScheduler":     ("dpmpp_2m", "normal"),
    "DPMSolverSinglestepScheduler":    ("dpmpp_2s_ancestral", "normal"),  # near, not exact
    "DPMSolverSDEScheduler":           ("dpmpp_sde", "normal"),
    "DEISMultistepScheduler":          ("deis", "normal"),
    "UniPCMultistepScheduler":         ("uni_pc", "normal"),
    "DDIMScheduler":                   ("ddim", "normal"),
    "DDPMScheduler":                   ("ddpm", "normal"),
    "PNDMScheduler":                   ("ipndm", "normal"),  # near, not exact
}


def _sampling_for(scheduler_name):
    """(sampler_name, scheduler) for the rule one run asked for.

    A name this map does not carry costs the run nothing: it is logged and the
    ComfyUI defaults stand. That is the same promise _install_run_scheduler
    makes on the diffusers side — a surface sending a word this backend does not
    know must not lose a generation over it.
    """
    if not scheduler_name:
        return DEFAULTS["sampler_name"], DEFAULTS["scheduler"]

    pair = SCHEDULER_TO_COMFY.get(str(scheduler_name).strip())
    if pair is None:
        logger.warning(
            "[ARCHAEOLOGY-COMFY] No ComfyUI sampler mapped for scheduler %r, "
            "running %s / %s",
            scheduler_name, DEFAULTS["sampler_name"], DEFAULTS["scheduler"],
        )
        return DEFAULTS["sampler_name"], DEFAULTS["scheduler"]
    return pair


def _read_shift(raw):
    """The shift one run asked for, or None to leave the model its own."""
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "[ARCHAEOLOGY-COMFY] Unreadable shift %r, running the model default", raw
        )
        return None


def _build_workflow(backbone, prompt, negative_prompt, checkpoint, width, height,
                    steps, cfg, seed, capture_every_n, sampler_name, scheduler,
                    shift=None):
    """The graph one run submits, with the archaeology node where a KSampler stands.

    The two backbones need different text encoding, and the graph says so:
      - sd35: the triple-encoder head of output_image_sd35_large.json
        (TripleCLIPLoader + AI4ArtsEdSD3TextEncode), because SD3.5's three encoders
        live outside the checkpoint.
      - sdxl: the head of output_image_sdxl.json (CLIPTextEncode twice on the
        checkpoint's own CLIP), because SDXL carries its two encoders inside it.

    `shift` spreads the steps along a straight flow-matching path, so it belongs
    to SD3.5 alone. In ComfyUI it is a node — ModelSamplingSD3, between the
    checkpoint and the sampler — rather than a field, so on SDXL it is left out
    of the graph instead of being passed as a no-op.
    """
    from schemas.engine.comfyui_chunk_support import (
        checkpoint_loader, negative_encode, t5_length, text_encode, triple_clip_loader,
    )
    workflow = {
        "5": checkpoint_loader(checkpoint, title=None),
        "3": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
    }

    # Which node hands the MODEL to the sampler. ModelSamplingSD3 steps into
    # that place when a run sets shift.
    model_source = ["5", 0]

    if backbone == "sdxl":
        workflow["1"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["5", 1]},
        }
        workflow["6"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["5", 1]},
        }
    else:
        workflow["7"] = triple_clip_loader(title=None)
        # The T5 stream on the platform's length, and the empty negative through
        # all three encoders: both the way every other SD 3.5 graph here sets
        # them, from schemas/engine/comfyui_chunk_support.py. This graph names
        # the node "10" because "9" is its ModelSamplingSD3.
        workflow["10"] = t5_length("7", title=None)
        workflow["1"] = text_encode(prompt, clip_node="10", title=None)
        workflow["6"] = negative_encode(negative_prompt, clip_node="10", title=None)
        if shift is not None:
            workflow[MODEL_SAMPLING_NODE_ID] = {
                "class_type": "ModelSamplingSD3",
                "inputs": {"model": ["5", 0], "shift": shift},
            }
            model_source = [MODEL_SAMPLING_NODE_ID, 0]

    workflow[ARCHAEOLOGY_NODE_ID] = {
        "class_type": "AI4ArtsEdDenoisingArchaeology",
        "inputs": {
            "model": model_source,
            "positive": ["1", 0],
            "negative": ["6", 0],
            "latent_image": ["3", 0],
            "vae": ["5", 2],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": 1.0,
            "capture_every_n": capture_every_n,
            "frame_max_size": 0,
            "frame_quality": 95,
            "filename_prefix": "archaeology_step",
        },
    }
    workflow["2"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": [ARCHAEOLOGY_NODE_ID, 0], "vae": ["5", 2]},
    }
    workflow[SAVE_IMAGE_NODE_ID] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "archaeology_final", "images": ["2", 0]},
    }
    return workflow


def _collect_step_images(result):
    """Map the node's frame list onto the downloaded bytes.

    The custom node reports {step, sigma, filename, subfolder} in its ui payload;
    the ws client downloads every announced file. Joining on filename keeps the
    step order authoritative rather than relying on dict iteration order.
    """
    node_output = (result.outputs_metadata or {}).get(ARCHAEOLOGY_NODE_ID, {})
    entries = node_output.get("archaeology") or []
    frames = entries[0].get("frames", []) if entries else []

    by_name = {f.filename: f.data for f in result.media_files}
    step_images = []
    for frame in frames:
        data = by_name.get(frame["filename"])
        if data is None:
            logger.warning("[ARCHAEOLOGY-COMFY] frame not downloaded: %s", frame["filename"])
            continue
        step_images.append({
            "step": frame["step"],
            # The Diffusers path reports the scheduler timestep here; ComfyUI's
            # callback exposes the sigma instead. Same role, different scale.
            "timestep": frame.get("sigma", 0.0),
            "image_base64": base64.b64encode(data).decode("utf-8"),
        })
    return step_images, entries[0] if entries else {}


async def execute(
    prompt: str = None,
    TEXT_1: str = None,
    negative_prompt: str = None,
    steps: int = None,
    cfg: float = None,
    seed: int = None,
    width: int = None,
    height: int = None,
    **kwargs
) -> dict:
    """Returns dict (not bytes) — uses the extended Python chunk dict-return path."""
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    from my_app.services.comfyui_manager import get_comfyui_manager
    from my_app.services.latent_lab_model import get_latent_lab_model_id
    from my_app.services.latent_lab_model import (
        LATENT_LAB_LARGE,
        get_latent_lab_unet,
    )
    from schemas.engine.comfyui_chunk_support import (
        checkpoint_available,
        checkpoint_for,
        final_image,
    )

    prompt = prompt or TEXT_1
    if not prompt or not prompt.strip():
        raise ValueError("No prompt provided for denoising archaeology")

    steps = steps if steps is not None else DEFAULTS["steps"]
    cfg = cfg if cfg is not None else DEFAULTS["cfg"]
    seed = seed if seed is not None else DEFAULTS["seed"]
    if seed < 0:
        # The UI sends -1 for "random seed"; ComfyUI's INT widget rejects negatives.
        seed = random.randint(0, 2 ** 32 - 1)
    width = width or DEFAULTS["width"]
    height = height or DEFAULTS["height"]
    negative_prompt = negative_prompt or DEFAULTS["negative_prompt"]

    # Which net does the denoising. It comes from the output config, so the model
    # card of the run says the same thing that ran -- see
    # configs/output/denoising_archaeology_sdxl_comfyui.json.
    backbone = str(kwargs.get("backbone") or "sd35").strip().lower()
    unet_id, _unet_pipeline_class = get_latent_lab_unet()
    if backbone == "sdxl":
        model_id = unet_id
    else:
        if backbone != "sd35":
            logger.warning(
                "[ARCHAEOLOGY-COMFY] Unknown backbone %r, running SD3.5", backbone
            )
            backbone = "sd35"
        model_id = await get_latent_lab_model_id()

    # Which rule walks the path, and how the steps sit on it. Both come from the
    # request, because both are choices WITHIN a run -- unlike the backbone,
    # which is the config's.
    sampler_name, comfy_scheduler = _sampling_for(kwargs.get("scheduler"))
    shift = _read_shift(kwargs.get("shift"))
    if shift is not None and backbone != "sd35":
        # A U-Net walks a curved path; there is no straight one to spread steps
        # along, and ComfyUI has no node that would do it.
        logger.warning(
            "[ARCHAEOLOGY-COMFY] shift %s has no meaning on backbone %s, ignoring",
            shift, backbone,
        )
        shift = None

    checkpoint = checkpoint_for(model_id, LATENT_LAB_LARGE, unet_id)
    if checkpoint is None:
        raise Exception(
            f"No ComfyUI checkpoint mapped for {model_id!r}. Extend "
            f"schemas/engine/comfyui_chunk_support.py::checkpoint_for and make sure "
            f"download_models.sh fetches the file."
        )

    if not await get_comfyui_manager().ensure_comfyui_available():
        raise Exception("ComfyUI is not available")

    client = get_comfyui_ws_client()
    if await checkpoint_available(client.base_url, checkpoint, "ARCHAEOLOGY-COMFY") is False:
        raise Exception(
            f"ComfyUI has no checkpoint {checkpoint!r} for backbone {backbone!r} "
            f"(model {model_id!r}). ./download_models.sh fetches it."
        )

    workflow = _build_workflow(
        backbone=backbone, prompt=prompt, negative_prompt=negative_prompt,
        checkpoint=checkpoint, width=width, height=height, steps=steps, cfg=cfg,
        seed=seed, capture_every_n=DEFAULTS["capture_every_n"],
        sampler_name=sampler_name, scheduler=comfy_scheduler, shift=shift,
    )

    logger.info(
        "[ARCHAEOLOGY-COMFY] backbone=%s ckpt=%s sampler=%s/%s shift=%s "
        "steps=%s seed=%s prompt=%r",
        backbone, checkpoint, sampler_name, comfy_scheduler, shift,
        steps, seed, prompt[:80],
    )

    result = await client.submit_and_track(workflow, timeout=600)

    step_images, meta = _collect_step_images(result)
    image_base64 = final_image(result, SAVE_IMAGE_NODE_ID)
    if image_base64 is None:
        raise Exception("Denoising archaeology (ComfyUI): no final image returned")

    logger.info(
        "[ARCHAEOLOGY-COMFY] Done: %s step frames, %.1fs",
        len(step_images), result.execution_time,
    )

    return {
        # Same marker as the Diffusers chunk on purpose: schema_pipeline_routes.py
        # dispatches on it and the frontend contract stays identical.
        'content_marker': 'diffusers_archaeology_generated',
        # WHICH backbone ran, as the Diffusers twin reports it: the surface that
        # names the model reads this and otherwise falls back to the output
        # config's own name, which names the instrument and not a model.
        'model_id': model_id,
        'image_data': image_base64,
        'archaeology_data': {
            'step_images': step_images,
            'total_steps': meta.get('total_steps', steps),
            'seed': meta.get('seed', seed),
            # What ran, in ComfyUI's own words. The Diffusers twin reports a
            # diffusers class name here; both name the rule that walked the path.
            # ComfyUI's samplers are all first order in the frame count -- one
            # callback per step -- so the order the surface reads stays 1 and the
            # frame count matches the step count, unlike a second-order diffusers
            # scheduler.
            'scheduler': f"{sampler_name}/{comfy_scheduler}",
            'scheduler_order': 1,
            # Which net ran, by the word the surface chooses it with. The
            # server-side record (services/denoising_archaeology_record.py)
            # writes it into the run so a restore chooses the same net.
            'backbone': backbone,
        },
        'seed': meta.get('seed', seed),
    }
