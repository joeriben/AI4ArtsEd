"""
The decode of a kept latent, in ComfyUI.

Mean Images averages the latents of a set and decodes the average once
(my_app/routes/mean_images_routes.py). The pictures of a set are made by
ComfyUI since stage 2 of the move, and their mean is decoded the same way:
the latent goes up as a file, the way a picture for img2img does, ComfyUI's
checkpoint loader brings the model that made the set, the platform's own node
reads the file back into that model's latent space (AI4ArtsEdLoadKeptLatent,
comfyui_nodes/ai4artsed_keep_latent.py), and ComfyUI's VAE decodes it. The ws
client holds one lease for the run, as it does for every workflow it submits,
and the decode is filed under a workload of its own (DECODE_WORKLOAD), as the
GPU service filed it: the gate's duration bucket for a generation on this
checkpoint must not learn from a decode of a few seconds.

WHICH checkpoint: the record names the model by repository and pipeline class
(`latent_meta`, written from the chunk's `latent_decoder`). The chunk that
declares that model is the chunk whose workflow loads it, so its checkpoint
loader names the file: read off the chunk, never written here. A model no
chunk of this installation declares is an error carrying the model's name;
there is no second way to decode.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CHUNKS = Path(__file__).resolve().parents[2] / "schemas" / "chunks"

# The platform's reader node, as ComfyUI registers it.
LOAD_NODE = "AI4ArtsEdLoadKeptLatent"

# The workload the decode's lease carries. The same name the GPU service's
# decode ran under (gpu_service/services/diffusers_backend.py, `vae-decode`).
DECODE_WORKLOAD = "vae-decode"


class LatentDecodeError(RuntimeError):
    """A decode that did not end in a picture, with the reason."""


def _checkpoint_loader_of(workflow: Any) -> Optional[str]:
    """The file the workflow's checkpoint loader names, or None.

    The decode needs that loader in particular: its third output is the VAE.
    """
    if not isinstance(workflow, dict):
        return None
    for node_id in sorted(workflow, key=str):
        node = workflow[node_id]
        if isinstance(node, dict) and node.get("class_type") == "CheckpointLoaderSimple":
            name = (node.get("inputs") or {}).get("ckpt_name")
            if isinstance(name, str) and name:
                return name
    return None


def checkpoint_for(model_id: str, pipeline_class: str) -> str:
    """The checkpoint ComfyUI loads for the model a kept latent names."""
    found = {}
    for path in sorted(CHUNKS.glob("*.json")):
        try:
            chunk = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        decoder = chunk.get("latent_decoder") if isinstance(chunk, dict) else None
        if not isinstance(decoder, dict):
            continue
        if decoder.get("model_id") != model_id or decoder.get("pipeline_class") != pipeline_class:
            continue
        name = _checkpoint_loader_of(chunk.get("workflow"))
        if name:
            found[path.name] = name
    names = sorted(set(found.values()))
    if not names:
        raise LatentDecodeError(
            f"no chunk of this installation declares {model_id} ({pipeline_class}) "
            f"as the model of a kept latent, so nothing here can decode it")
    if len(names) > 1:
        raise LatentDecodeError(
            f"the chunks that declare {model_id} ({pipeline_class}) load different "
            f"checkpoints: " + ", ".join(f"{c} -> {n}" for c, n in sorted(found.items())))
    return names[0]


def decode_workflow(ckpt_name: str, latent_file: str) -> Dict[str, Any]:
    """The four nodes of a decode: the loader, the platform's reader, ComfyUI's
    VAE decode, and the picture."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt_name}},
        "2": {"class_type": LOAD_NODE,
              "inputs": {"model": ["1", 0], "latent_file": latent_file}},
        "3": {"class_type": "VAEDecode",
              "inputs": {"samples": ["2", 0], "vae": ["1", 2]}},
        "4": {"class_type": "SaveImage",
              "inputs": {"images": ["3", 0], "filename_prefix": "ai4artsed_mean"}},
    }


def _why_no_picture(result: Any) -> str:
    """What the run's record says about a decode that handed back no picture."""
    said = result.outputs_metadata or {}
    if not said:
        return ("ComfyUI's history holds no outputs for it: the run vanished, or "
                "the history could not be read")
    if any(isinstance(node, dict) and node.get("images") for node in said.values()):
        return "the picture ComfyUI announced could not be downloaded"
    return "ComfyUI announced no picture"


async def decode_in_comfyui(meta: Dict[str, Any], latent_npy: bytes) -> bytes:
    """One latent through the decoder of the model that made it. PNG bytes, or raises.

    Never None: a whole set of pictures was generated before this call, so
    every exit that is not a picture is a `LatentDecodeError` with its reason.
    A card that is taken travels as `GpuBusyError` out of the lease, as it did.

    The file goes up under the lease, right before the workflow does: a file
    that waited in ComfyUI's input directory through a wait for the card is
    gone after a restart, which empties that directory (2_start_comfyui.sh).
    Its name is new for every decode, so two decodes in flight never write the
    same file, and so that ComfyUI, which keys its cache on a node's inputs,
    never answers a second mean with a first mean's picture. (The node hashes
    the file as well, `IS_CHANGED`, the way ComfyUI's own loaders do.)
    """
    from my_app.services.comfyui_manager import get_comfyui_manager
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
    from my_app.services.gpu_lease_client import GpuBusyError

    ckpt = checkpoint_for(str(meta.get("model_id") or ""), str(meta.get("pipeline_class") or ""))
    if not await get_comfyui_manager().ensure_comfyui_available():
        raise LatentDecodeError("ComfyUI is not available")
    client = get_comfyui_ws_client()
    name = f"ai4artsed_mean_{uuid.uuid4().hex}.npy"

    async def hand_over():
        stored = await client.upload_file(latent_npy, name)
        if stored != name:
            raise LatentDecodeError(
                f"ComfyUI stored the latent as {stored!r}, and the workflow names {name!r}")

    token = CURRENT_OUTPUT_CONFIG.set(DECODE_WORKLOAD)
    try:
        result = await client.submit_and_track(
            decode_workflow(ckpt, name), timeout=None, before_submit=hand_over)
    except (GpuBusyError, LatentDecodeError):
        raise
    except Exception as exc:
        raise LatentDecodeError(f"ComfyUI did not decode the latent: {exc}") from exc
    finally:
        CURRENT_OUTPUT_CONFIG.reset(token)
    pictures = [f for f in result.media_files if f.media_type == "image" and f.data]
    if not pictures:
        raise LatentDecodeError(
            f"ComfyUI answered without a picture: {_why_no_picture(result)} "
            f"(prompt {result.prompt_id})")
    logger.info(f"[LATENT-DECODE] the mean was decoded in ComfyUI under {ckpt}")
    return pictures[0].data
