"""
GPU Service MMAudio Routes

REST endpoints for MMAudio (CVPR 2025) image/text-to-audio generation.
"""

from routes._async import run_async
import base64
import logging
from flask import Blueprint, request, jsonify

from services.gpu_admission import gated

logger = logging.getLogger(__name__)

mmaudio_bp = Blueprint('mmaudio', __name__)



@mmaudio_bp.route('/api/cross_aesthetic/mmaudio', methods=['POST'])
@gated("mmaudio")
def generate():
    """MMAudio: generate audio from image and/or text.

    Request JSON:
        image_base64: str (optional) - Base64-encoded image
        prompt: str (optional) - Text prompt
        negative_prompt: str (default "") - Negative text
        duration_seconds: float (default 8.0, max 8.0)
        cfg_strength: float (default 4.5)
        num_steps: int (default 25)
        seed: int (default -1)

    At least one of image_base64 or prompt must be provided.

    Returns: { success, audio_base64, seed, generation_time_ms }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Request body required"}), 400

    has_image = 'image_base64' in data and data['image_base64']
    has_prompt = 'prompt' in data and data['prompt']

    if not has_image and not has_prompt:
        return jsonify({"success": False, "error": "image_base64 or prompt required"}), 400

    from services.mmaudio_backend import get_mmaudio_backend
    backend = get_mmaudio_backend()

    seed = int(data.get('seed', -1))
    duration = min(float(data.get('duration_seconds', 8.0)), 8.0)
    cfg = float(data.get('cfg_strength', 4.5))
    steps = int(data.get('num_steps', 25))
    negative = data.get('negative_prompt', '')
    prompt = data.get('prompt', '')

    if has_image:
        try:
            image_bytes = base64.b64decode(data['image_base64'])
        except Exception:
            return jsonify({"success": False, "error": "Invalid base64 image data"}), 400

        result = run_async(backend.generate_from_image(
            image_bytes=image_bytes,
            prompt=prompt,
            negative_prompt=negative,
            duration_seconds=duration,
            cfg_strength=cfg,
            num_steps=steps,
            seed=seed,
        ))
    else:
        result = run_async(backend.generate_from_text(
            prompt=prompt,
            negative_prompt=negative,
            duration_seconds=duration,
            cfg_strength=cfg,
            num_steps=steps,
            seed=seed,
        ))

    if result is None:
        return jsonify({"success": False, "error": "MMAudio generation failed"}), 500

    return jsonify({
        "success": True,
        "audio_base64": base64.b64encode(result["audio_bytes"]).decode('utf-8'),
        "seed": result["seed"],
        "generation_time_ms": result["generation_time_ms"],
    })
