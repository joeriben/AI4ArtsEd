"""
What every ComfyUI chunk of the Latent Lab needs, in one place.

The Denoising Archaeology chunk was the first of its kind and carried these
three privately. Stufe 4 of the ComfyUI move builds six more chunks of exactly
that shape, and three copies of a checkpoint map is the parallel structure
Regel 13 forbids — so they live here from the second chunk on.

This module sits in schemas/engine and not beside the chunks: the chunk
directory is scanned for chunks, and a helper there would be read as one.
Since 2026-10-10 the archaeology chunk reads its helpers from here too, and
the five chunks that resolve the model the same way share resolve_checkpoint.
"""

import base64
import logging

logger = logging.getLogger(__name__)


def checkpoint_for(model_id, large_id, unet_id):
    """Map a resolver model id onto a ComfyUI checkpoint filename.

    Keyed by the resolver's own constants rather than literal model ids, so a
    chunk stays clean under devserver/tests/test_latent_lab_model_policy.py and
    cannot drift away from latent_lab_model.py.

    Both files are fetched by download_models.sh. The Medium entry went on
    2026-10-10, with the resolver's Medium answer (docs/DEVELOPMENT_DECISIONS.md
    2026-09-18): nothing could reach it.
    """
    return {
        large_id: "OfficialStableDiffusion/sd3.5_large.safetensors",
        unet_id: "OfficialStableDiffusion/sdxl_base.safetensors",
    }.get(model_id)


async def checkpoint_available(base_url, checkpoint, tag="COMFY-CHUNK"):
    """Whether ComfyUI can actually load this file. None when it cannot be told.

    ComfyUI rejects a workflow naming a checkpoint it does not have with a 400 at
    /prompt. Asking first costs one GET and lets the operator read what is
    missing and what fetches it.
    """
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/object_info/CheckpointLoaderSimple") as response:
                if response.status != 200:
                    return None
                info = await response.json()
        known = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        return checkpoint in known
    except Exception as e:
        logger.warning(
            "[%s] Could not read ComfyUI's checkpoint list (%s: %s)",
            tag, type(e).__name__, e,
        )
        return None


async def resolve_checkpoint(model_id, tag="COMFY-CHUNK"):
    """The checkpoint file for the resolver's model, and a client to a ComfyUI
    that has it: (checkpoint, client).

    The model id stays with the chunk, which takes it from
    get_latent_lab_model_id() where the policy test looks for the call
    (devserver/tests/test_latent_lab_model_policy.py). What follows that call
    stood in five chunks word for word until 2026-10-10: the map onto a file,
    ComfyUI started, the file asked for before a graph names it.
    """
    from my_app.services.comfyui_manager import get_comfyui_manager
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    from my_app.services.latent_lab_model import LATENT_LAB_LARGE, get_latent_lab_unet

    unet_id, _pipeline_class = get_latent_lab_unet()
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
    if await checkpoint_available(client.base_url, checkpoint, tag) is False:
        raise Exception(
            f"ComfyUI has no checkpoint {checkpoint!r} (model {model_id!r}). "
            f"./download_models.sh fetches it."
        )
    return checkpoint, client


async def node_accepts(base_url, class_type, widget, tag="COMFY-CHUNK"):
    """Whether the RUNNING ComfyUI declares this input on this node class.
    None when it cannot be told.

    ComfyUI reads a custom node file once, at process start, and an input the
    running class does not declare is dropped from a submitted graph without an
    error (execution.py, get_input_data: an unknown key has no input category
    and never reaches the node). A ComfyUI older than a node file therefore runs
    the node's default while the chunk's record names what was asked for. Asking
    costs one GET.
    """
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/object_info/{class_type}") as response:
                if response.status != 200:
                    return None
                info = await response.json()
        declared = info[class_type]["input"]
        return (widget in declared.get("required", {})
                or widget in declared.get("optional", {}))
    except Exception as e:
        logger.warning(
            "[%s] Could not read ComfyUI's inputs for %s (%s: %s)",
            tag, class_type, type(e).__name__, e,
        )
        return None


def final_image(result, node_id):
    """The picture the named SaveImage node wrote, base64, or None."""
    for media in result.media_files:
        if media.node_id == node_id and media.media_type == "image":
            return base64.b64encode(media.data).decode("utf-8")
    return None


# SD 3.5's three text encoders are separate files from the checkpoint. The same
# three filenames stand in schemas/chunks/output_image_sd35_large.json and in
# every ComfyUI chunk of the Latent Lab; download_models.sh fetches all three.
#
# T5 in fp16: the Diffusers path loaded stable-diffusion-3.5-large's
# text_encoder_3 in float16, so every SD 3.5 picture this platform made before
# the move to ComfyUI was conditioned by fp16 weights. The file ComfyUI carried
# for SD 3.5 until now, t5xxl_enconly.safetensors, holds the same 220 encoder
# tensors in F8_E4M3. LTX-Video goes on loading that fp8 file by its name
# (schemas/chunks/output_video_ltx.json), so both files stay on disk.
# The weights match byte for byte; the arithmetic still differs. ComfyUI sets
# the text encoders' compute dtype to float32 (comfy/sd.py, its own comment:
# "Match torch.float32 hardcode upcast in TE implemention"), while the Diffusers
# path ran float16 with the 24 DenseReluDense.wo projections held at float32 by
# transformers.
SD35_TEXT_ENCODERS = (
    "clip_l.safetensors",
    "clip_g.safetensors",
    "t5xxl_fp16.safetensors",
)


def checkpoint_loader(checkpoint, title="Load checkpoint (model + VAE)"):
    """The graph node that loads the checkpoint: transformer and VAE in one file.

    Pass title=None for a graph that carries no titles.
    """
    node = {"inputs": {"ckpt_name": checkpoint}, "class_type": "CheckpointLoaderSimple"}
    if title:
        node["_meta"] = {"title": title}
    return node


def triple_clip_loader(title="TripleCLIPLoader (CLIP-L + CLIP-G + T5-XXL)"):
    """The graph node that loads SD 3.5's three text encoders.

    Three chunks built this node privately, which is the parallel structure
    Regel 13 forbids. Pass title=None for a graph that carries no titles.
    """
    node = {
        "inputs": {
            "clip_name1": SD35_TEXT_ENCODERS[0],
            "clip_name2": SD35_TEXT_ENCODERS[1],
            "clip_name3": SD35_TEXT_ENCODERS[2],
        },
        "class_type": "TripleCLIPLoader",
    }
    if title:
        node["_meta"] = {"title": title}
    return node


# How many positions SD 3.5's T5 stream carries on this platform. Every call
# into the Diffusers backend sets max_sequence_length=512, so a prompt has
# always been conditioned on 77 CLIP + 512 T5 positions. ComfyUI's
# T5XXLTokenizer starts at min_length=77 and grows only with the prompt, which
# puts a short prompt on 154 positions instead of 589: the same prompt, another
# picture. T5_LENGTH holds the platform's number for the ComfyUI side.
T5_LENGTH = 512

# Where a graph puts the tokenizer options, and where its text encoders read
# their CLIP. The loader keeps the id it always had, "7".
CLIP_NODE = "9"


def t5_length(clip_node="7", title="T5 length"):
    """The graph node that puts the T5 stream on the platform's length.

    Every SD 3.5 text encoder in a ComfyUI graph takes its CLIP from here rather
    than straight from the loader, so the option reaches all three encoders at
    once. Pass title=None for a graph that carries no titles.
    """
    node = {
        "inputs": {
            "clip": [clip_node, 0],
            "min_padding": 0,
            "min_length": T5_LENGTH,
        },
        "class_type": "T5TokenizerOptions",
    }
    if title:
        node["_meta"] = {"title": title}
    return node


def text_encode(text, clip_node=CLIP_NODE, title="Text"):
    """SD 3.5's conditioning of one text: all three encoders, the CLIP window
    (`AI4ArtsEdSD3TextEncode`), T5 at the length `clip_node` gives it.

    `empty_padding: "empty_prompt"` sends an empty text through the encoders
    too, which is what the Diffusers twins do with an empty negative: they hand
    `negative_prompt or None` to a pipeline that encodes the empty string. The
    other setting, "none", leaves the token lists empty and lets `SD3ClipModel`
    put zeros in their place, and at cfg 4.5 that is another picture.

    Pass title=None for a graph that carries no titles.
    """
    node = {
        "inputs": {
            "clip_l": text,
            "clip_g": text,
            "t5xxl": text,
            "empty_padding": "empty_prompt",
            "clip": [clip_node, 0],
        },
        "class_type": "AI4ArtsEdSD3TextEncode",
    }
    if title:
        node["_meta"] = {"title": title}
    return node


def negative_encode(negative_prompt, clip_node=CLIP_NODE, title="Negative"):
    """SD 3.5's negative conditioning, the way every graph on this platform builds it
    but the two that fuse their negative (the Surrealizer's chunk and the Fusion
    Workbench's scheduled fusion in my_app/services/latent_lab_context_graphs.py):
    a fused negative needs the parts before the assembly, and this returns a
    CONDITIONING, so those build sd3_encode -> sd3_fusion -> sd3_assemble.
    """
    return text_encode(negative_prompt, clip_node=clip_node, title=title)


def sd3_encode(text, clip_node=CLIP_NODE, title="Encode", empty_padding=None):
    """AI4ArtsEdSD3Encode: one text read by the three encoders, as PARTS. With
    `empty_padding` None the node's own default stands; the Surrealizer and the
    Workbench name "empty_prompt", an empty text then encoding as the empty
    string on every encoder."""
    inputs = {"clip": [clip_node, 0], "text": text}
    if empty_padding is not None:
        inputs["empty_padding"] = empty_padding
    return {"inputs": inputs, "class_type": "AI4ArtsEdSD3Encode", "_meta": {"title": title}}


def sd3_fusion(clip_side, t5_side, alpha, strategy, title="Fuse CLIP and T5"):
    """AI4ArtsEdSD3Fusion of two PARTS at alpha under a strategy; the sides are
    node links ([node_id, 0]), the same link twice for one prompt."""
    return {
        "inputs": {"clip_side": clip_side, "t5_side": t5_side,
                   "alpha": float(alpha), "strategy": strategy},
        "class_type": "AI4ArtsEdSD3Fusion",
        "_meta": {"title": title},
    }


def sd3_three_factors(parts, a, b, c, t5_rows="full", pooled="clip", title="Three factors"):
    """AI4ArtsEdSD3ThreeFactors on PARTS (a node link): a on the CLIP block, b
    for T5's rows 0..76 mixed into it cell by cell, c on the T5 block; the T5
    block complete under the CLIP rows ("full", 589 rows) or as the tail
    ("tail", rows 77.., 512 rows); the pooled vector CLIP's own ("clip") or
    zeros ("zero")."""
    return {
        "inputs": {"parts": parts, "a": float(a), "b": float(b), "c": float(c),
                   "t5_rows": t5_rows, "pooled": pooled},
        "class_type": "AI4ArtsEdSD3ThreeFactors",
        "_meta": {"title": title},
    }


def sd3_assemble(parts, title="Assemble"):
    """AI4ArtsEdSD3Assemble: PARTS (a node link) to a CONDITIONING."""
    return {"inputs": {"parts": parts}, "class_type": "AI4ArtsEdSD3Assemble",
            "_meta": {"title": title}}


def announced(result, node_id, key, field=None):
    """What one of our own nodes announced, from the run's raw outputs.

    A node output alone never leaves ComfyUI. A node that announces its number
    puts it into the run's history, and `GenerationResult.outputs_metadata`
    carries it here. None where the announcement is absent: naming a number
    nobody measured is worse than saying the measure is missing.

    `field` picks one number out of the announcement; without it the whole
    announcement comes back.
    """
    said = (result.outputs_metadata or {}).get(node_id) or {}
    for entry in said.get(key, []):
        if not isinstance(entry, dict):
            continue
        if field is None:
            return entry
        value = entry.get(field)
        if isinstance(value, (int, float)):
            return float(value)
    return None
