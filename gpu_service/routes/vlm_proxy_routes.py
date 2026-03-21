"""
VLM Chat Proxy Routes

Proxies vision model requests to Ollama via the VRAM-coordinated backend.
Called by DevServer instead of Ollama directly.
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

vlm_proxy_bp = Blueprint('vlm_proxy', __name__)


@vlm_proxy_bp.route('/api/vlm/chat', methods=['POST'])
def vlm_chat():
    """
    VRAM-coordinated VLM chat proxy.

    Request: {
        "model": "qwen3-vl:2b",
        "messages": [{"role": "user", "content": "Describe this image..."}],
        "images": ["base64..."],           // optional
        "temperature": 0.7,                // optional
        "max_new_tokens": 2000,            // optional
        "enable_thinking": false           // optional
    }
    Response: {
        "status": "success",
        "content": "...",
        "thinking": "..." | null,
        "model": "qwen3-vl:2b"
    }
    """
    from services.vlm_proxy_backend import get_vlm_proxy_backend
    import config

    if not config.VLM_PROXY_ENABLED:
        return jsonify({'status': 'error', 'error': 'VLM proxy disabled'}), 503

    try:
        data = request.get_json()
        model = data.get('model')
        messages = data.get('messages')

        if not model or not messages:
            return jsonify({'status': 'error', 'error': 'model and messages required'}), 400

        backend = get_vlm_proxy_backend()
        result = backend.chat(
            model=model,
            messages=messages,
            images=data.get('images'),
            temperature=data.get('temperature', 0.7),
            max_new_tokens=data.get('max_new_tokens', 2000),
            enable_thinking=data.get('enable_thinking', False),
        )

        if result is None:
            return jsonify({'status': 'error', 'error': 'VLM returned no response', 'model': model}), 500

        return jsonify({
            'status': 'success',
            'content': result.get('content', ''),
            'thinking': result.get('thinking'),
            'model': model,
        })

    except Exception as e:
        logger.error(f"[VLM-PROXY-ROUTE] Error: {e}", exc_info=True)
        return jsonify({'status': 'error', 'error': str(e)}), 500
