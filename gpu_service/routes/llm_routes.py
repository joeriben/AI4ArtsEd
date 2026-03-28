"""
LLM Routes — Local LLM inference endpoints.

Replaces Ollama for safety checks, DSGVO verification, VLM safety.
"""

import logging
from flask import Blueprint, request, jsonify

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


@llm_bp.route('/health', methods=['GET'])
def llm_health():
    """Health check for LLM backend."""
    from services.llm_backend import get_llm_backend

    backend = get_llm_backend()
    return jsonify({
        "status": "ok" if backend.is_available() else "unavailable",
        "backend": "llama-cpp-python",
    })
