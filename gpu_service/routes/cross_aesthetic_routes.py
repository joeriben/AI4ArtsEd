"""
GPU Service Crossmodal Lab Routes

REST endpoints for Crossmodal Lab v2:
- /synth: Latent Audio Synth (T5 embedding manipulation)
- /image_guided_audio: ImageBind gradient guidance (Phase 3)
- /mmaudio: MMAudio image/text-to-audio (Phase 2, separate blueprint)
"""

import asyncio
import base64
import logging
import time
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

cross_aesthetic_bp = Blueprint('cross_aesthetic', __name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@cross_aesthetic_bp.route('/api/cross_aesthetic/available', methods=['GET'])
def available():
    """Check if crossmodal lab backends are available."""
    try:
        from config import CROSS_AESTHETIC_ENABLED, STABLE_AUDIO_ENABLED
        from config import IMAGEBIND_ENABLED, MMAUDIO_ENABLED

        return jsonify({
            "available": CROSS_AESTHETIC_ENABLED,
            "backends": {
                "synth": STABLE_AUDIO_ENABLED,
                "imagebind_guidance": IMAGEBIND_ENABLED,
                "mmaudio": MMAUDIO_ENABLED,
            },
        })
    except Exception as e:
        return jsonify({"available": False, "error": str(e)})


@cross_aesthetic_bp.route('/api/cross_aesthetic/synth', methods=['POST'])
def synth():
    """Latent Audio Synth: manipulate T5 embeddings and generate audio.

    Request JSON:
        prompt_a: str (required) - Base text prompt
        prompt_b: str (optional) - Second prompt for interpolation
        alpha: float (default 0.5) - Interpolation factor (-2.0 to 3.0)
        magnitude: float (default 1.0) - Global embedding scale (0.1-5.0)
        noise_sigma: float (default 0.0) - Noise injection strength (0-1.0)
        dimension_offsets: dict (optional) - {dim_idx: offset_value}
        duration_seconds: float (default 1.0) - Audio duration (0.5-5.0)
        steps: int (default 20) - Inference steps
        cfg_scale: float (default 3.5) - CFG scale
        seed: int (default -1) - Random seed

    Returns: { success, audio_base64, embedding_stats, generation_time_ms, seed }
    """
    data = request.get_json()
    if not data or 'prompt_a' not in data:
        return jsonify({"success": False, "error": "prompt_a required"}), 400

    from services.cross_aesthetic_backend import get_cross_aesthetic_backend
    backend = get_cross_aesthetic_backend()

    result = _run_async(backend.synth(
        prompt_a=data['prompt_a'],
        prompt_b=data.get('prompt_b'),
        alpha=float(data.get('alpha', 0.5)),
        magnitude=float(data.get('magnitude', 1.0)),
        noise_sigma=float(data.get('noise_sigma', 0.0)),
        dimension_offsets=data.get('dimension_offsets'),
        duration_seconds=float(data.get('duration_seconds', 1.0)),
        steps=int(data.get('steps', 20)),
        cfg_scale=float(data.get('cfg_scale', 3.5)),
        seed=int(data.get('seed', -1)),
    ))

    if result is None:
        return jsonify({"success": False, "error": "Synth generation failed"}), 500

    return jsonify({
        "success": True,
        "audio_base64": base64.b64encode(result["audio_bytes"]).decode('utf-8'),
        "embedding_stats": result["embedding_stats"],
        "generation_time_ms": result["generation_time_ms"],
        "seed": result["seed"],
    })


@cross_aesthetic_bp.route('/api/cross_aesthetic/semantic_axes', methods=['GET'])
def semantic_axes():
    """Return available semantic axis metadata for frontend dropdown population."""
    from services.cross_aesthetic_backend import get_cross_aesthetic_backend
    backend = get_cross_aesthetic_backend()
    return jsonify({"success": True, "axes": backend.get_available_axes()})


@cross_aesthetic_bp.route('/api/cross_aesthetic/multi_axis_synth', methods=['POST'])
def multi_axis_synth():
    """Multi-axis semantic synth: combine multiple semantic axes into audio.

    Request JSON:
        axes: dict (required) - {axis_name: 0.0-1.0}
        dimension_offsets: dict (optional) - {dim_idx: offset_value}
        duration_seconds: float (default 1.0)
        steps: int (default 20)
        cfg_scale: float (default 3.5)
        seed: int (default -1)

    Returns: { success, audio_base64, embedding_stats, axis_contributions, generation_time_ms, seed }
    """
    data = request.get_json()
    if not data or 'axes' not in data:
        return jsonify({"success": False, "error": "axes dict required"}), 400

    from services.cross_aesthetic_backend import get_cross_aesthetic_backend
    backend = get_cross_aesthetic_backend()

    result = _run_async(backend.multi_axis_synth(
        axes=data['axes'],
        dimension_offsets=data.get('dimension_offsets'),
        duration_seconds=float(data.get('duration_seconds', 1.0)),
        steps=int(data.get('steps', 20)),
        cfg_scale=float(data.get('cfg_scale', 3.5)),
        seed=int(data.get('seed', -1)),
    ))

    if result is None:
        return jsonify({"success": False, "error": "Multi-axis synth failed"}), 500

    return jsonify({
        "success": True,
        "audio_base64": base64.b64encode(result["audio_bytes"]).decode('utf-8'),
        "embedding_stats": result["embedding_stats"],
        "axis_contributions": result["axis_contributions"],
        "generation_time_ms": result["generation_time_ms"],
        "seed": result["seed"],
    })


@cross_aesthetic_bp.route('/api/cross_aesthetic/image_guided_audio', methods=['POST'])
def image_guided_audio():
    """ImageBind gradient guidance: image-guided audio generation.

    Request JSON:
        image_base64: str (required) - Base64-encoded image
        prompt: str (optional) - Text basis conditioning
        lambda_guidance: float (default 0.1) - Guidance strength
        warmup_steps: int (default 10) - Gradient guidance steps
        total_steps: int (default 50) - Total inference steps
        duration_seconds: float (default 10.0)
        cfg_scale: float (default 7.0)
        seed: int (default -1)

    Returns: { success, audio_base64, cosine_similarity, seed }
    """
    data = request.get_json()
    if not data or 'image_base64' not in data:
        return jsonify({"success": False, "error": "image_base64 required"}), 400

    try:
        image_bytes = base64.b64decode(data['image_base64'])
    except Exception:
        return jsonify({"success": False, "error": "Invalid base64 image data"}), 400

    from services.stable_audio_backend import get_stable_audio_backend
    stable_audio = get_stable_audio_backend()

    result = _run_async(stable_audio.generate_audio_with_guidance(
        image_bytes=image_bytes,
        prompt=data.get('prompt', ''),
        lambda_guidance=float(data.get('lambda_guidance', 0.1)),
        warmup_steps=int(data.get('warmup_steps', 10)),
        total_steps=int(data.get('total_steps', 50)),
        duration_seconds=float(data.get('duration_seconds', 10.0)),
        cfg_scale=float(data.get('cfg_scale', 7.0)),
        seed=int(data.get('seed', -1)),
    ))

    if result is None:
        return jsonify({"success": False, "error": "Guided generation failed"}), 500

    return jsonify({
        "success": True,
        "audio_base64": base64.b64encode(result["audio_bytes"]).decode('utf-8'),
        "cosine_similarity": result.get("cosine_similarity"),
        "generation_time_ms": result.get("generation_time_ms"),
        "seed": result["seed"],
    })
