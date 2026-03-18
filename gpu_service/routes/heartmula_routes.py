"""
GPU Service HeartMuLa Routes

REST endpoints for HeartMuLa music generation.
"""

import asyncio
import base64
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

heartmula_bp = Blueprint('heartmula', __name__)


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_backend():
    from services.heartmula_backend import get_heartmula_backend
    return get_heartmula_backend()


@heartmula_bp.route('/api/heartmula/available', methods=['GET'])
def available():
    """Check if HeartMuLa backend is available."""
    try:
        from config import HEARTMULA_ENABLED
        if not HEARTMULA_ENABLED:
            return jsonify({"available": False, "reason": "disabled"})
        backend = _get_backend()
        is_available = _run_async(backend.is_available())
        return jsonify({"available": is_available})
    except Exception as e:
        return jsonify({"available": False, "reason": str(e)})


@heartmula_bp.route('/api/heartmula/load', methods=['POST'])
def load():
    """Preload HeartMuLa pipeline into GPU memory without generating."""
    try:
        backend = _get_backend()
        result = _run_async(backend._load_pipeline())
        return jsonify({"success": result})
    except Exception as e:
        logger.error(f"[HEARTMULA] Preload failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@heartmula_bp.route('/api/heartmula/unload', methods=['POST'])
def unload():
    """Unload HeartMuLa pipeline from GPU."""
    backend = _get_backend()
    result = _run_async(backend.unload_pipeline())
    return jsonify({"success": result})


@heartmula_bp.route('/api/heartmula/generate', methods=['POST'])
def generate():
    """Generate music from lyrics and tags.

    Returns: { success, audio_base64 }
    """
    data = request.get_json()
    if not data or 'lyrics' not in data:
        return jsonify({"success": False, "error": "lyrics required"}), 400

    backend = _get_backend()
    audio_bytes = _run_async(backend.generate_music(
        lyrics=data['lyrics'],
        tags=data.get('tags', ''),
        temperature=float(data.get('temperature', 1.0)),
        topk=int(data.get('topk', 70)),
        cfg_scale=float(data.get('cfg_scale', 3.0)),
        max_audio_length_ms=int(data.get('max_audio_length_ms', 240000)),
        seed=int(data.get('seed')) if data.get('seed') is not None else None,
        output_format=data.get('output_format', 'mp3'),
    ))

    if audio_bytes is None:
        return jsonify({"success": False, "error": "Music generation failed"}), 500

    return jsonify({
        "success": True,
        "audio_base64": base64.b64encode(audio_bytes).decode('utf-8'),
    })
