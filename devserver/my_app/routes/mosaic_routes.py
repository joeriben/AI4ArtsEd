"""
Mosaic Routes — DevServer proxy to GPU service for Arcimboldo Mosaic

Thin JSON proxy: Frontend calls /api/diffusers/mosaic/* -> DevServer -> GPU service (17803).
"""

import logging
import requests as http_requests
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

mosaic_bp = Blueprint('mosaic', __name__, url_prefix='/api/diffusers/mosaic')


def _proxy_post(path: str):
    """Forward POST JSON to GPU service."""
    from config import GPU_SERVICE_URL, GPU_SERVICE_TIMEOUT
    url = f"{GPU_SERVICE_URL.rstrip('/')}{path}"
    data = request.get_json() or {}

    try:
        resp = http_requests.post(url, json=data, timeout=GPU_SERVICE_TIMEOUT)
        return jsonify(resp.json()), resp.status_code
    except http_requests.ConnectionError:
        return jsonify({"success": False, "error": "GPU service unreachable"}), 503
    except http_requests.Timeout:
        return jsonify({"success": False, "error": "GPU service timeout"}), 504
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@mosaic_bp.route('/segment', methods=['POST'])
def segment():
    return _proxy_post('/api/diffusers/mosaic/segment')


@mosaic_bp.route('/generate-tiles', methods=['POST'])
def generate_tiles():
    return _proxy_post('/api/diffusers/mosaic/generate-tiles')


@mosaic_bp.route('/compose', methods=['POST'])
def compose():
    return _proxy_post('/api/diffusers/mosaic/compose')
