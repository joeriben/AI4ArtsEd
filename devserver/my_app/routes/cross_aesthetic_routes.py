"""
Cross-Aesthetic Routes — the Crossmodal Lab's doors, answered by ComfyUI

Crossmodal Lab v2: the DevServer's doors for the crossmodal instruments.
Each generation is one prompt of a node of the platform's package
(comfyui_nodes/ai4artsed_comfyui/: ai4artsed_audio_synth,
ai4artsed_image_guided_audio, ai4artsed_mmaudio), queued at ComfyUI and
tracked the way a picture is (services/llm_client.run_node_files). The axis
vocabulary of the synth -- which semantic axes there are, their poles, the
neutral prompt, the frame the poles are encoded under, the PCA labels -- is
the table config/audio_synth_axes.json; the node is handed the poles to
encode, already framed, and knows none of it by itself. Which checkpoints
run is the tier (services/stable_audio_tier) and the table
config/local_media_weights.json; what is installed is what the package
reports (services/media_stations).

Until stage 6 of the move to ComfyUI these routes
forwarded to the GPU service's routes of the same paths. The JSON shapes are
the ones the surfaces read then, unchanged.

Endpoints, below the blueprint's prefix /api/cross_aesthetic:
- GET  available          - which instruments can run, and what each runs
- GET  semantic_axes      - the axis vocabulary of the synth
- POST synth              - Latent Audio Synth
- POST image_guided_audio - ImageBind gradient guidance
- POST mmaudio            - MMAudio image/text to audio
"""

import base64
import functools
import json
import logging
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify

from my_app.services.streaming_response import (answered_either_way,
                                                note_dispatch,
                                                object_body,
                                                without_transport_flags)

logger = logging.getLogger(__name__)

cross_aesthetic_bp = Blueprint('cross_aesthetic', __name__, url_prefix='/api/cross_aesthetic')

AXES_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "audio_synth_axes.json"

SYNTH_NODE = "ai4artsed_audio_synth"
GUIDED_NODE = "ai4artsed_image_guided_audio"
MMAUDIO_NODE = "ai4artsed_mmaudio"

# The refusal shape this page reads: views/latent_lab/crossmodal_lab.vue
# branches on `success` before it looks at `error`.
_proxy_body = functools.partial(object_body, envelope={"success": False})


# ---------------------------------------------------------------------------
# The axis vocabulary, off the table.

@lru_cache(maxsize=1)
def _axes_table() -> dict:
    with open(AXES_FILE) as f:
        return json.load(f)


def _framed(text: str) -> str:
    """A pole or the neutral prompt as the synth encodes it: under the
    production frame of the table."""
    return f"{_axes_table().get('production_frame', '')}{text}"


def _axis_rows() -> List[Dict[str, Any]]:
    """The axes as the page's dropdown lists them: the semantic axes of the
    table, then the ear-validated PCA labels, each keyed by its PC index."""
    table = _axes_table()
    rows = [
        {"name": name, "pole_a": axis["pole_a"], "pole_b": axis["pole_b"],
         "level": axis["level"], "d": axis["d"], "type": "semantic"}
        for name, axis in table["semantic_axes"].items()
    ]
    for label in table["pca_labels"]:
        rows.append({"name": f"pc{label['pc']}", "pole_a": label["pole_a"],
                     "pole_b": label["pole_b"], "level": "pca", "d": None, "type": "pca"})
    return rows


def _axes_for_node(axes: Any) -> List[Dict[str, Any]]:
    """The page's {axis name: t} as the node takes it: one entry per axis,
    a semantic axis with its two poles framed, a PCA axis by name alone
    (the node reads the component off the PCA file). An axis the table
    does not know is refused by name, the way the station refused it."""
    if not isinstance(axes, dict):
        raise ValueError("axes has to be an object of {axis name: t}")
    table = _axes_table()
    semantic = table["semantic_axes"]
    pca = {f"pc{label['pc']}" for label in table["pca_labels"]}
    out = []
    for name, t in axes.items():
        name = str(name)
        try:
            t = float(t)
        except (TypeError, ValueError):
            raise ValueError(f"axis {name}: t has to be a number, got {t!r}") from None
        if name in pca:
            out.append({"name": name, "t": t})
            continue
        axis = semantic.get(name)
        if axis is None:
            raise ValueError(f"Unknown axis: {name}")
        out.append({"name": name, "t": t,
                    "pole_a": _framed(axis["pole_a"]), "pole_b": _framed(axis["pole_b"])})
    return out


# ---------------------------------------------------------------------------
# What runs, and whether it can.

def _first_installed(station: str, stations: Optional[dict]) -> Tuple[Optional[str], Optional[str]]:
    """(alias, folder) of the first whole checkpoint of a station in table
    order, or (None, None)."""
    from my_app.services import local_media_weights, media_stations
    if not media_stations.available(station, stations):
        return None, None
    folders = media_stations.installed(station, stations)
    for alias in local_media_weights.aliases_of_station(station):
        folder = local_media_weights.dir_name(alias)
        if folder in folders:
            return alias, folder
    return None, None


def _synth_model(stations: Optional[dict]) -> Tuple[Optional[str], Optional[str]]:
    """(alias, folder) of the Stable Audio checkpoint this card runs for the
    synth and the guidance, when it is whole; (None, None) otherwise. The
    tier reads the card once; a card that cannot be read leaves the synth
    unavailable rather than handed a model never chosen for it."""
    from my_app.services import media_stations, stable_audio_tier
    try:
        alias = stable_audio_tier.alias("music")
        folder = stable_audio_tier.dir_name("music")
    except Exception as e:
        logger.warning(f"[CROSS-AESTHETIC] the stable audio model went unnamed ({e})")
        return None, None
    if not media_stations.has_folder("stable_audio", folder, stations):
        return None, None
    return alias, folder



# ---------------------------------------------------------------------------
# One prompt of a node, and what it wrote.

def _float(data: dict, key: str, default: float) -> float:
    """A number of the body, by name: a body that carries something else
    under the key is refused with the key in the sentence."""
    value = data.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} has to be a number, got {value!r}") from None


def _int(data: dict, key: str, default: int) -> int:
    value = data.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} has to be a whole number, got {value!r}") from None


def _seed(data: dict) -> int:
    """The page's seed, or one drawn here for -1, the way the station drew it."""
    seed = _int(data, 'seed', -1)
    return seed if seed >= 0 else random.randint(0, 2**32 - 1)


def _run_node(class_type: str, inputs: dict, model_alias: Optional[str]):
    """The node's ui outputs and the files it announced. Says which model
    the run is at for the bar that names it (note_dispatch), and that it is
    at none once the run has ended, whichever way."""
    from my_app.services.llm_client import LLMClient
    note_dispatch(model_alias, local=True)
    try:
        return LLMClient.run_node_files(class_type, inputs)
    finally:
        note_dispatch(None, local=True)


def _failed(label: str, e: BaseException) -> Tuple[dict, int]:
    """The answer to a run that did not end in a sound: the node's own
    sentence, under the status that says which side failed
    (llm_client.node_failure_status)."""
    from my_app.services.gpu_lease_client import GpuBusyError
    from my_app.services.llm_client import node_failure_status
    logger.error(f"[CROSS-AESTHETIC] {label} failed: {e!r}")
    payload = {"success": False, "error": str(e) or type(e).__name__}
    if isinstance(e, GpuBusyError):
        payload["busy"] = True
    return payload, node_failure_status(e)


def _sound_base64(files) -> Optional[str]:
    sound = next((f for f in files if f.media_type == "audio"), None)
    return base64.b64encode(sound.data).decode('ascii') if sound else None


def _watermarked(payload: dict) -> dict:
    """AI-Origin Disclosure (EU AI Act Art. 50): the sound goes straight from
    this route to the page and is downloaded from there. No recorder sees it
    on the way."""
    try:
        from my_app.services.watermark_service import watermark_result_metadata
        watermark_result_metadata(payload, {'seed': payload.get('seed')})
    except Exception as e:
        logger.warning(f"[CROSS-AESTHETIC] watermark not applied ({e})")
    return payload


def _image_base64_of(data: dict) -> Tuple[Optional[str], Optional[Tuple[dict, int]]]:
    """The picture as base64, from the body's image_base64 or its image_path.

    Only files this server itself wrote through /api/media/upload/image are
    readable. The path arrives in the request body and is read straight off
    this machine's disk, so without the containment any caller could name any
    file the server user can read -- a key, a database, a run of somebody
    else's -- and have its bytes handed on. media_routes._run_analyze_image
    and the Stage-4 image lookback in schema_pipeline_routes carry exactly
    this check. Every path that reaches here is an upload: MediaInputBox
    re-uploads even a picture taken off the platform's own boards before it
    hands the path on.
    """
    image_path = data.get('image_path')
    if not image_path:
        return data.get('image_base64') or None, None
    from config import UPLOADS_TMP_DIR
    resolved = None
    try:
        resolved = Path(str(image_path)).resolve()
        uploaded = (UPLOADS_TMP_DIR.resolve() in resolved.parents and resolved.is_file())
    except Exception as e:
        # A path that cannot even be resolved is not an uploaded picture.
        logger.warning(f"[CROSS-AESTHETIC] could not resolve {image_path}: {e}")
        uploaded = False
    if not uploaded:
        logger.warning(f"[CROSS-AESTHETIC] refused image outside the uploads: {image_path}")
        return None, ({"success": False, "error": "image_path must point to an uploaded image"}, 400)
    try:
        return base64.b64encode(resolved.read_bytes()).decode('ascii'), None
    except Exception as e:
        logger.warning(f"Failed to read image {image_path}: {e}")
        return None, ({"success": False, "error": f"Image read failed: {e}"}, 400)


def _synth_post(data: dict, mode: str):
    """The synth (mode "synth" or "multi_axis"), and the ``(payload,
    http_status)`` it answers with. It must not reach for ``request``: the
    body is read at the request boundary and passed in, and a streamed
    answer runs this on a thread of its own."""
    from my_app.services import local_media_weights, stable_audio_tier
    data = without_transport_flags(data)
    if mode == "synth" and not data.get('prompt_a'):
        return {"success": False, "error": "prompt_a required"}, 400
    if mode == "multi_axis" and not isinstance(data.get('axes'), dict):
        return {"success": False, "error": "axes dict required"}, 400
    try:
        axes = _axes_for_node(data.get('axes') or {})
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400
    table = _axes_table()
    try:
        alias = stable_audio_tier.alias("music")
        folder = local_media_weights.dir_name(alias)
    except Exception as e:
        return {"success": False, "error": f"no Stable Audio model for this card: {e}"}, 503
    try:
        inputs = {
            "model_name": folder,
            "mode": mode,
            "prompt_a": str(data.get('prompt_a') or ""),
            "seed": _seed(data),
            "prompt_b": str(data.get('prompt_b') or ""),
            "alpha": _float(data, 'alpha', 0.5),
            "magnitude": _float(data, 'magnitude', 1.0),
            "noise_sigma": _float(data, 'noise_sigma', 0.0),
            "dimension_offsets": json.dumps(data.get('dimension_offsets') or {}),
            "axes": json.dumps(axes),
            "neutral_prompt": _framed(table["neutral_prompt"]),
            "pca_axes_file": table["pca_file"],
            "base_prompt": str(data.get('base_prompt') or ""),
            "duration_seconds": _float(data, 'duration_seconds', 1.0),
            "steps": _int(data, 'steps', 8),
            "cfg_scale": _float(data, 'cfg_scale', 1.0),
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400
    try:
        out, files = _run_node(SYNTH_NODE, inputs, alias)
    except Exception as e:
        return _failed("synth", e)
    sound = _sound_base64(files)
    if sound is None:
        return {"success": False, "error": "the run ended without a sound"}, 500
    contributions = json.loads(out.get("axis_contributions") or "[]")
    payload = {
        "success": True,
        "audio_base64": sound,
        "embedding_stats": json.loads(out.get("embedding_stats") or "{}"),
        "generation_time_ms": out.get("generation_time_ms"),
        "seed": out.get("seed"),
    }
    # As the station answered: the synth names contributions only where an
    # axis moved something; the multi-axis synth always names them.
    if mode == "multi_axis" or contributions:
        payload["axis_contributions"] = contributions
    return _watermarked(payload), 200


def _guided_post(data: dict):
    """ImageBind gradient guidance, and the ``(payload, http_status)``."""
    from my_app.services import media_stations
    data = without_transport_flags(data)
    image_b64, refusal = _image_base64_of(data)
    if refusal is not None:
        return refusal
    if not image_b64:
        return {"success": False, "error": "image_base64 required"}, 400
    stations = media_stations.read()
    sa_alias, sa_folder = _synth_model(stations)
    ib_alias, ib_folder = _first_installed("imagebind", stations)
    if not sa_folder or not ib_folder:
        return {"success": False, "error": "Stable Audio or ImageBind is not installed on ComfyUI"}, 503
    try:
        inputs = {
            "model_name": sa_folder,
            "imagebind_name": ib_folder,
            "prompt": str(data.get('prompt') or ""),
            "lambda_guidance": _float(data, 'lambda_guidance', 5.0),
            "warmup_steps": _int(data, 'warmup_steps', 8),
            "total_steps": _int(data, 'total_steps', 8),
            "duration_seconds": _float(data, 'duration_seconds', 10.0),
            "cfg_scale": _float(data, 'cfg_scale', 1.0),
            "seed": _seed(data),
            "image_base64": image_b64,
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400
    try:
        out, files = _run_node(GUIDED_NODE, inputs, ib_alias)
    except Exception as e:
        return _failed("guided generation", e)
    sound = _sound_base64(files)
    if sound is None:
        return {"success": False, "error": "the run ended without a sound"}, 500
    return _watermarked({
        "success": True,
        "audio_base64": sound,
        "cosine_similarity": out.get("cosine_similarity"),
        "guidance_steps_skipped": out.get("guidance_steps_skipped"),
        "generation_time_ms": out.get("generation_time_ms"),
        "seed": out.get("seed"),
    }), 200


def _mmaudio_post(data: dict):
    """MMAudio from an image and/or a text, and the ``(payload, http_status)``."""
    from my_app.services import media_stations
    data = without_transport_flags(data)
    image_b64, refusal = _image_base64_of(data)
    if refusal is not None:
        return refusal
    prompt = str(data.get('prompt') or "")
    if not image_b64 and not prompt:
        return {"success": False, "error": "image_base64 or prompt required"}, 400
    mm_alias, mm_folder = _first_installed("mmaudio", media_stations.read())
    if not mm_folder:
        return {"success": False, "error": "MMAudio is not installed on ComfyUI"}, 503
    try:
        inputs = {
            "model_name": mm_folder,
            "prompt": prompt,
            # The station clamped the length to its ceiling; the node does too.
            "duration_seconds": min(_float(data, 'duration_seconds', 8.0), 8.0),
            "seed": _seed(data),
            "image_base64": image_b64 or "",
            "negative_prompt": str(data.get('negative_prompt') or ""),
            "cfg_strength": _float(data, 'cfg_strength', 4.5),
            "num_steps": _int(data, 'num_steps', 25),
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400
    try:
        out, files = _run_node(MMAUDIO_NODE, inputs, mm_alias)
    except Exception as e:
        return _failed("MMAudio", e)
    sound = _sound_base64(files)
    if sound is None:
        return {"success": False, "error": "the run ended without a sound"}, 500
    return _watermarked({
        "success": True,
        "audio_base64": sound,
        "seed": out.get("seed"),
        "generation_time_ms": out.get("generation_time_ms"),
    }), 200


def _streamed_post(run, label: str, *args):
    """A generation, answered as a stream where the caller asked for it.

    With "enable_streaming" the answer travels as the platform's SSE stream
    instead of as one JSON body. It is the same generation; only its way back is
    different. Every one of these makes sound on the shared card and stands in
    the plant-wide queue first, and ten seconds of MMAudio is minutes of
    silence on the wire. The edge in front of this server ends a request
    whose origin has sent nothing for about 100 seconds and hands the browser a
    524, so sound that had already been made reached nobody.

    The work names no `client_gone` parameter, and that is a decision rather
    than an omission: one run of a node stands behind it, the node has the
    card by the time this waits at all, and leaving the call would not end the
    generation -- only lose the answer to sound already made. Work that could
    give something back by stopping asks for the signal by declaring the
    parameter; see `streamed_answer`.
    """
    data, refusal = _proxy_body()
    if refusal is not None:
        return jsonify(refusal[0]), refusal[1]
    return answered_either_way(data, run, data, *args, label=label)



@cross_aesthetic_bp.route('/semantic_axes', methods=['GET'])
def semantic_axes():
    try:
        return jsonify({"success": True, "axes": _axis_rows()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



@cross_aesthetic_bp.route('/synth', methods=['POST'])
def synth():
    return _streamed_post(_synth_post, 'CROSS-AESTHETIC-SYNTH', "synth")


@cross_aesthetic_bp.route('/image_guided_audio', methods=['POST'])
def image_guided_audio():
    return _streamed_post(_guided_post, 'CROSS-AESTHETIC-IMAGE-GUIDED-AUDIO')


@cross_aesthetic_bp.route('/mmaudio', methods=['POST'])
def mmaudio():
    return _streamed_post(_mmaudio_post, 'CROSS-AESTHETIC-MMAUDIO')
