"""
LLM Routes — Local LLM inference endpoints.

Local LLM inference for safety checks, DSGVO verification, VLM safety.
"""

import json
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context

logger = logging.getLogger(__name__)

llm_bp = Blueprint('llm', __name__, url_prefix='/api/llm')


@llm_bp.route('/chat', methods=['POST'])
def llm_chat():
    """
    Chat completion endpoint.

    Request:
        {
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "..."}],
            "images": ["base64..."],  // optional, for VLM
            "temperature": 0.7,
            "max_tokens": 500,
            "repetition_penalty": 1.1  // optional
        }

    Response:
        {"content": "...", "thinking": null, "tool_calls": null}
    """
    from services.llm_backend import get_llm_backend

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    model = data.get("model", "")
    messages = data.get("messages", [])
    if not model or not messages:
        return jsonify({"error": "model and messages required"}), 400

    backend = get_llm_backend()
    result = backend.chat(
        model=model,
        messages=messages,
        images=data.get("images"),
        temperature=data.get("temperature", 0.7),
        max_tokens=data.get("max_tokens", 500),
        repetition_penalty=data.get("repetition_penalty"),
    )

    if result is None:
        return jsonify({"error": f"LLM inference failed for {model}"}), 500

    return jsonify(result)


@llm_bp.route('/generate', methods=['POST'])
def llm_generate():
    """
    Text completion endpoint.

    Request:
        {
            "model": "llama-guard3:1b",
            "prompt": "...",
            "temperature": 0.7,
            "max_tokens": 500
        }

    Response:
        {"response": "...", "thinking": null}
    """
    from services.llm_backend import get_llm_backend

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    model = data.get("model", "")
    prompt = data.get("prompt", "")
    if not model or not prompt:
        return jsonify({"error": "model and prompt required"}), 400

    backend = get_llm_backend()
    result = backend.generate(
        model=model,
        prompt=prompt,
        temperature=data.get("temperature", 0.7),
        max_tokens=data.get("max_tokens", 500),
        repetition_penalty=data.get("repetition_penalty"),
    )

    if result is None:
        return jsonify({"error": f"LLM inference failed for {model}"}), 500

    return jsonify(result)


@llm_bp.route('/models', methods=['GET'])
def llm_models():
    """List available and loaded LLM models."""
    from services.llm_backend import get_llm_backend

    backend = get_llm_backend()
    return jsonify({
        "available": backend.get_available_models(),
        "loaded": backend.get_loaded_models(),
    })


@llm_bp.route('/chat-models', methods=['GET'])
def llm_chat_models():
    """List chat-capable LLM models for Compare Hub."""
    from services.llm_backend import get_llm_backend

    backend = get_llm_backend()
    return jsonify({
        "models": backend.get_chat_models(),
    })


@llm_bp.route('/vlm-models', methods=['GET'])
def llm_vlm_models():
    """List VLM-capable LLM models for Compare Hub (Image Understanding)."""
    from services.llm_backend import get_llm_backend

    backend = get_llm_backend()
    return jsonify({
        "models": backend.get_vlm_models(),
    })


@llm_bp.route('/install-precheck', methods=['POST'])
def llm_install_precheck():
    """Check whether a model can be installed right now (no side effects)."""
    from services.install_service import get_install_service

    data = request.get_json() or {}
    alias = data.get("alias", "").strip()
    if not alias:
        return jsonify({"ok": False, "reason": "alias required"}), 400

    svc = get_install_service()
    result = svc.precheck(alias)
    result["busy"] = svc.is_busy()
    result["active_alias"] = svc.active_alias()
    return jsonify(result)


@llm_bp.route('/install', methods=['POST'])
def llm_install():
    """
    Install a MODEL_CONFIGS entry from HuggingFace. SSE stream.

    Request:
        {"alias": "qwen3:4b"}

    Response: text/event-stream with events:
        data: {"type": "start",    "alias": "...", "file": "...", "total_mb": 4082}
        data: {"type": "progress", "alias": "...", "done_mb": 512, "total_mb": 4082, "speed_mb_s": 28.3}
        data: {"type": "done",     "alias": "...", "elapsed_s": 147}
        data: {"type": "error",    "alias": "...", "message": "..."}
    """
    from services.install_service import get_install_service

    data = request.get_json() or {}
    alias = data.get("alias", "").strip()
    if not alias:
        return jsonify({"error": "alias required"}), 400

    svc = get_install_service()

    def generate():
        for event in svc.install(alias):
            yield f"data: {json.dumps(event)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


@llm_bp.route('/unload', methods=['POST'])
def llm_unload():
    """Unload a specific LLM model to free VRAM."""
    from services.llm_backend import get_llm_backend

    data = request.get_json()
    if not data or not data.get("model"):
        return jsonify({"error": "model required"}), 400

    backend = get_llm_backend()
    success = backend.evict_model(data["model"])
    return jsonify({"success": success, "model": data["model"]})


@llm_bp.route('/health', methods=['GET'])
def llm_health():
    """Health check for LLM backend."""
    from services.llm_backend import get_llm_backend

    backend = get_llm_backend()
    return jsonify({
        "status": "ok" if backend.is_available() else "unavailable",
        "backend": "llama-cpp-python",
    })
