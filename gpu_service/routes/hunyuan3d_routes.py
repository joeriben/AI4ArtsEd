"""
Hunyuan3D-2 Routes — Text-to-3D Mesh Generation API

Endpoints:
- GET  /api/hunyuan3d/available  — Health check
- POST /api/hunyuan3d/generate   — Generate 3D mesh from text
- POST /api/hunyuan3d/unload     — Free VRAM
"""

from flask import Blueprint, request, jsonify
import asyncio
import base64
import logging

logger = logging.getLogger(__name__)

hunyuan3d_bp = Blueprint('hunyuan3d', __name__)


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_backend():
    from services.hunyuan3d_backend import get_hunyuan3d_backend
    return get_hunyuan3d_backend()


@hunyuan3d_bp.route('/api/hunyuan3d/available', methods=['GET'])
def available():
    """Check if Hunyuan3D-2 backend is available."""
    try:
        from config import HUNYUAN3D_ENABLED
        if not HUNYUAN3D_ENABLED:
            return jsonify({"available": False, "reason": "disabled in config"})

        backend = _get_backend()
        is_available = _run_async(backend.is_available())
        return jsonify({"available": is_available})
    except Exception as e:
        logger.error(f"[HUNYUAN3D-ROUTE] Availability check failed: {e}")
        return jsonify({"available": False, "reason": str(e)})


@hunyuan3d_bp.route('/api/hunyuan3d/generate', methods=['POST'])
def generate():
    """
    Generate a 3D mesh from a text prompt.

    Request JSON:
        {
            "image_base64": "<base64 PNG/JPEG data>",
            "seed": 42,
            "num_inference_steps": 50,
            "guidance_scale": 7.5,
            "octree_resolution": 256
        }

    Response JSON:
        {
            "success": true,
            "mesh_base64": "<base64 GLB data>",
            "seed": 42
        }
    """
    data = request.get_json()
    if not data or 'image_base64' not in data:
        return jsonify({"success": False, "error": "image_base64 required"}), 400

    try:
        backend = _get_backend()
        glb_bytes, actual_seed = _run_async(backend.generate_mesh(
            image_base64=data['image_base64'],
            seed=data.get('seed', -1),
            num_inference_steps=data.get('num_inference_steps', 50),
            guidance_scale=data.get('guidance_scale', 7.5),
            octree_resolution=data.get('octree_resolution', 256),
        ))

        if glb_bytes is None:
            return jsonify({"success": False, "error": "Mesh generation failed"}), 500

        return jsonify({
            "success": True,
            "mesh_base64": base64.b64encode(glb_bytes).decode('utf-8'),
            "size_bytes": len(glb_bytes),
            "seed": actual_seed,
        })

    except Exception as e:
        logger.error(f"[HUNYUAN3D-ROUTE] Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@hunyuan3d_bp.route('/api/hunyuan3d/unload', methods=['POST'])
def unload():
    """Unload Hunyuan3D-2 models to free VRAM."""
    try:
        backend = _get_backend()
        success = _run_async(backend.unload_pipeline())
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"[HUNYUAN3D-ROUTE] Unload failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
