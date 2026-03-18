"""
GPU Service Stable Audio Routes

REST endpoints for Stable Audio Open generation.
"""

import asyncio
import base64
import io
import logging
from flask import Blueprint, request, jsonify

import numpy as np
import torch

logger = logging.getLogger(__name__)

stable_audio_bp = Blueprint('stable_audio', __name__)


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_backend():
    from services.stable_audio_backend import get_stable_audio_backend
    return get_stable_audio_backend()


@stable_audio_bp.route('/api/stable_audio/available', methods=['GET'])
def available():
    """Check if Stable Audio backend is available."""
    try:
        from config import STABLE_AUDIO_ENABLED
        if not STABLE_AUDIO_ENABLED:
            return jsonify({"available": False, "reason": "disabled"})
        backend = _get_backend()
        is_available = _run_async(backend.is_available())
        return jsonify({"available": is_available})
    except Exception as e:
        return jsonify({"available": False, "reason": str(e)})


@stable_audio_bp.route('/api/stable_audio/load', methods=['POST'])
def load():
    """Preload Stable Audio pipeline into GPU memory without generating."""
    try:
        backend = _get_backend()
        result = _run_async(backend._load_pipeline())
        return jsonify({"success": result})
    except Exception as e:
        logger.error(f"[STABLE-AUDIO] Preload failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stable_audio_bp.route('/api/stable_audio/unload', methods=['POST'])
def unload():
    """Unload Stable Audio pipeline from GPU."""
    backend = _get_backend()
    result = _run_async(backend.unload_pipeline())
    return jsonify({"success": result})


@stable_audio_bp.route('/api/stable_audio/generate', methods=['POST'])
def generate():
    """Generate audio from text prompt.

    Request JSON:
        prompt: str (required)
        duration_seconds: float (default 10.0, max 47.55)
        negative_prompt: str (default "")
        steps: int (default 100)
        cfg_scale: float (default 7.0)
        seed: int (default -1 = random)
        output_format: str ("wav" or "mp3", default "wav")

    Returns: { success, audio_base64, seed, duration_seconds, sample_rate }
    """
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"success": False, "error": "prompt required"}), 400

    seed = int(data.get('seed', -1))

    backend = _get_backend()
    audio_bytes = _run_async(backend.generate_audio(
        prompt=data['prompt'],
        duration_seconds=float(data.get('duration_seconds', 10.0)),
        negative_prompt=data.get('negative_prompt', ''),
        steps=int(data.get('steps', 100)),
        cfg_scale=float(data.get('cfg_scale', 7.0)),
        seed=seed,
        output_format=data.get('output_format', 'wav'),
    ))

    if audio_bytes is None:
        return jsonify({"success": False, "error": "Audio generation failed"}), 500

    return jsonify({
        "success": True,
        "audio_base64": base64.b64encode(audio_bytes).decode('utf-8'),
        "seed": seed,
        "duration_seconds": float(data.get('duration_seconds', 10.0)),
        "sample_rate": backend.sample_rate,
    })


@stable_audio_bp.route('/api/stable_audio/generate_from_embeddings', methods=['POST'])
def generate_from_embeddings():
    """Generate audio from pre-computed T5 embeddings.

    For research use: SAE feature sonification, cross-aesthetic generation.

    Request JSON:
        embeddings_b64: str (base64-encoded numpy array, shape [1, seq, 768], float32)
        attention_mask_b64: str (base64-encoded numpy array, shape [1, seq], float32)
        duration_seconds: float (default 2.0)
        steps: int (default 100)
        cfg_scale: float (default 7.0)
        seed: int (default -1 = random)

    Returns: { success, audio_base64, seed, duration_seconds, sample_rate }
    """
    data = request.get_json()
    if not data or 'embeddings_b64' not in data:
        return jsonify({"success": False, "error": "embeddings_b64 required"}), 400

    # Decode numpy arrays from base64
    emb_bytes = base64.b64decode(data['embeddings_b64'])
    prompt_embeds = torch.from_numpy(
        np.load(io.BytesIO(emb_bytes), allow_pickle=False)
    )

    attention_mask = None
    if 'attention_mask_b64' in data:
        mask_bytes = base64.b64decode(data['attention_mask_b64'])
        attention_mask = torch.from_numpy(
            np.load(io.BytesIO(mask_bytes), allow_pickle=False)
        )

    duration = float(data.get('duration_seconds', 2.0))
    seed = int(data.get('seed', -1))

    backend = _get_backend()
    audio_bytes = _run_async(backend.generate_from_embeddings(
        prompt_embeds=prompt_embeds,
        attention_mask=attention_mask,
        seconds_start=0.0,
        seconds_end=duration,
        steps=int(data.get('steps', 100)),
        cfg_scale=float(data.get('cfg_scale', 7.0)),
        seed=seed,
    ))

    if audio_bytes is None:
        return jsonify({"success": False, "error": "Embedding generation failed"}), 500

    return jsonify({
        "success": True,
        "audio_base64": base64.b64encode(audio_bytes).decode('utf-8'),
        "seed": seed,
        "duration_seconds": duration,
        "sample_rate": backend.sample_rate,
    })
