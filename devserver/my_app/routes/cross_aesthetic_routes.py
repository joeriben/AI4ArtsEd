"""
Cross-Aesthetic Routes — DevServer proxy to GPU service

Crossmodal Lab v2: Thin JSON proxy for crossmodal generation experiments.
Frontend calls /api/cross_aesthetic/* -> DevServer -> GPU service (port 17803).

Endpoints:
- GET  /api/cross_aesthetic/available          - Health check + backend status
- POST /api/cross_aesthetic/synth              - Latent Audio Synth
- POST /api/cross_aesthetic/image_guided_audio - ImageBind gradient guidance
- POST /api/cross_aesthetic/mmaudio            - MMAudio image/text to audio
"""

import base64
import logging
from pathlib import Path

import requests as http_requests
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

cross_aesthetic_bp = Blueprint('cross_aesthetic', __name__, url_prefix='/api/cross_aesthetic')


def _proxy_get(path: str):
    """Forward GET to GPU service, return JSON."""
    from config import GPU_SERVICE_URL
    url = f"{GPU_SERVICE_URL.rstrip('/')}{path}"
    try:
        resp = http_requests.get(url, timeout=10)
        return jsonify(resp.json()), resp.status_code
    except http_requests.ConnectionError:
        return jsonify({"available": False, "error": "GPU service unreachable"}), 503
    except Exception as e:
        return jsonify({"available": False, "error": str(e)}), 500


def _proxy_post(path: str):
    """Forward POST JSON to GPU service. Convert image_path to image_base64 if present."""
    from config import GPU_SERVICE_URL, GPU_SERVICE_TIMEOUT
    url = f"{GPU_SERVICE_URL.rstrip('/')}{path}"
    data = request.get_json() or {}

    # Convert server-side image_path to base64 for GPU service
    image_path = data.pop('image_path', None)
    if image_path:
        try:
            img_bytes = Path(image_path).read_bytes()
            data['image_base64'] = base64.b64encode(img_bytes).decode('ascii')
        except Exception as e:
            logger.warning(f"Failed to read image {image_path}: {e}")
            return jsonify({"success": False, "error": f"Image read failed: {e}"}), 400

    try:
        resp = http_requests.post(url, json=data, timeout=GPU_SERVICE_TIMEOUT)
        return jsonify(resp.json()), resp.status_code
    except http_requests.ConnectionError:
        return jsonify({"success": False, "error": "GPU service unreachable"}), 503
    except http_requests.Timeout:
        return jsonify({"success": False, "error": "GPU service timeout"}), 504
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@cross_aesthetic_bp.route('/available', methods=['GET'])
def available():
    return _proxy_get('/api/cross_aesthetic/available')


@cross_aesthetic_bp.route('/semantic_axes', methods=['GET'])
def semantic_axes():
    return _proxy_get('/api/cross_aesthetic/semantic_axes')


@cross_aesthetic_bp.route('/multi_axis_synth', methods=['POST'])
def multi_axis_synth():
    return _proxy_post('/api/cross_aesthetic/multi_axis_synth')


@cross_aesthetic_bp.route('/synth', methods=['POST'])
def synth():
    return _proxy_post('/api/cross_aesthetic/synth')


@cross_aesthetic_bp.route('/image_guided_audio', methods=['POST'])
def image_guided_audio():
    return _proxy_post('/api/cross_aesthetic/image_guided_audio')


@cross_aesthetic_bp.route('/mmaudio', methods=['POST'])
def mmaudio():
    return _proxy_post('/api/cross_aesthetic/mmaudio')
