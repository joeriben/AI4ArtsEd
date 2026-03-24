"""
Text Routes - REST + SSE endpoints for Latent Text Lab

Session 175: Dekonstruktive LLM operations via HTTP REST.

Endpoints:
- POST /api/text/load - Load model
- POST /api/text/unload - Unload model
- POST /api/text/embedding - Get prompt embedding
- POST /api/text/interpolate - Interpolate between prompts
- POST /api/text/attention - Get attention maps
- POST /api/text/generate - Generate with token surgery
- POST /api/text/generate/stream - SSE streaming generation
- POST /api/text/variations - Generate seed variations
- POST /api/text/layers - Compare layer outputs
- GET /api/text/models - List loaded models
- GET /api/text/presets - List available model presets
"""

import logging
import json
from flask import Blueprint, request, jsonify, Response, stream_with_context
import asyncio

logger = logging.getLogger(__name__)

text_bp = Blueprint('text', __name__, url_prefix='/api/text')


def run_async(coro):
    """Run async coroutine in sync Flask context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Model Management
# =============================================================================

@text_bp.route('/load', methods=['POST'])
def load_model():
    """
    Load an LLM model.

    Request:
        {
            "model_id": "Qwen/Qwen2.5-3B-Instruct",
            "quantization": "bf16"  // optional: bf16, fp16, int8, int4, nf4
        }

    Response:
        {"success": true, "model_id": "...", "quantization": "...", "vram_mb": 1234}
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    model_id = data.get("model_id")
    quantization = data.get("quantization")

    if not model_id:
        return jsonify({"error": "model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    success = run_async(backend.load_model(model_id, quantization))

    if success:
        models = backend.get_loaded_models()
        model_info = next((m for m in models if m["model_id"] == model_id), {})
        return jsonify({
            "success": True,
            "model_id": model_id,
            "quantization": model_info.get("quantization", "unknown"),
            "vram_mb": model_info.get("vram_mb", 0),
        })
    else:
        return jsonify({"error": f"Failed to load {model_id}"}), 500


@text_bp.route('/unload', methods=['POST'])
def unload_model():
    """
    Unload a specific model.

    Request:
        {"model_id": "Qwen/Qwen2.5-3B-Instruct"}
    """
    data = request.get_json() or {}
    model_id = data.get("model_id")

    if not model_id:
        return jsonify({"error": "model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    success = run_async(backend.unload_model(model_id))

    if success:
        return jsonify({"success": True, "model_id": model_id})
    else:
        return jsonify({"error": f"Model {model_id} not loaded"}), 404


@text_bp.route('/models', methods=['GET'])
def list_models():
    """
    List currently loaded models.

    Response:
        {
            "models": [
                {"model_id": "...", "vram_mb": 1234, "quantization": "bf16", "in_use": false}
            ]
        }
    """
    from services.text_backend import get_text_backend
    backend = get_text_backend()

    return jsonify({"models": backend.get_loaded_models()})


@text_bp.route('/presets', methods=['GET'])
def list_presets():
    """
    List available model presets with VRAM fit status.

    Query params:
        scenario: "qwen" (default) or "mixed"

    Response:
        {
            "presets": {
                "tiny": {
                    "id": "...", "vram_gb": 4.0, "description": "...",
                    "fits_bf16": true, "fits_int8": true, "fits_int4": true,
                    "suggested_quant": "bf16"
                },
                ...
            },
            "scenario": "qwen",
            "available_scenarios": ["qwen", "mixed"],
            "free_vram_gb": 22.3,
            "total_vram_gb": 24.0
        }
    """
    from config import TEXT_PRESET_SCENARIOS
    from services.text_backend import estimate_model_vram
    from services.vram_coordinator import get_vram_coordinator

    scenario = request.args.get("scenario", "qwen")
    if scenario not in TEXT_PRESET_SCENARIOS:
        scenario = "qwen"

    presets = TEXT_PRESET_SCENARIOS[scenario]

    coordinator = get_vram_coordinator()
    free_vram_gb = coordinator.get_free_vram_mb() / 1024
    total_vram_gb = coordinator.get_total_vram_mb() / 1024

    enriched = {}
    for key, preset in presets.items():
        p = dict(preset)
        p["fits_bf16"] = estimate_model_vram(preset["id"], "bf16") * 1.1 < free_vram_gb
        p["fits_int8"] = estimate_model_vram(preset["id"], "int8") * 1.1 < free_vram_gb
        p["fits_int4"] = estimate_model_vram(preset["id"], "int4") * 1.1 < free_vram_gb
        p["suggested_quant"] = (
            "bf16" if p["fits_bf16"] else
            "int8" if p["fits_int8"] else
            "int4" if p["fits_int4"] else
            None
        )
        enriched[key] = p

    return jsonify({
        "presets": enriched,
        "scenario": scenario,
        "available_scenarios": list(TEXT_PRESET_SCENARIOS.keys()),
        "free_vram_gb": round(free_vram_gb, 1),
        "total_vram_gb": round(total_vram_gb, 1),
    })


# =============================================================================
# Dekonstruktive Operations
# =============================================================================

@text_bp.route('/embedding', methods=['POST'])
def get_embedding():
    """
    Get embedding representation of a prompt.

    Request:
        {
            "text": "Hello world",
            "model_id": "Qwen/Qwen2.5-3B-Instruct",
            "layer": -1  // optional, default: last layer
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    text = data.get("text")
    model_id = data.get("model_id")
    layer = data.get("layer", -1)

    if not text or not model_id:
        return jsonify({"error": "text and model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.get_prompt_embedding(text, model_id, layer))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/interpolate', methods=['POST'])
def interpolate_prompts():
    """
    Analyze embedding space between two prompts.

    Request:
        {
            "prompt_a": "The cat sat on the mat",
            "prompt_b": "The dog ran in the park",
            "model_id": "...",
            "steps": 5,
            "layer": -1
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    prompt_a = data.get("prompt_a")
    prompt_b = data.get("prompt_b")
    model_id = data.get("model_id")
    steps = data.get("steps", 5)
    layer = data.get("layer", -1)

    if not prompt_a or not prompt_b or not model_id:
        return jsonify({"error": "prompt_a, prompt_b, and model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.interpolate_prompts(prompt_a, prompt_b, model_id, steps, layer))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/attention', methods=['POST'])
def get_attention():
    """
    Get attention patterns for visualization.

    Request:
        {
            "text": "The quick brown fox",
            "model_id": "...",
            "layer": null,  // optional: specific layer
            "head": null    // optional: specific head
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    text = data.get("text")
    model_id = data.get("model_id")
    layer = data.get("layer")
    head = data.get("head")

    if not text or not model_id:
        return jsonify({"error": "text and model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.get_attention_map(text, model_id, layer, head))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/generate', methods=['POST'])
def generate_with_surgery():
    """
    Generate text with token-level logit manipulation.

    Request:
        {
            "prompt": "Write a poem about nature",
            "model_id": "...",
            "boost_tokens": ["dark", "shadow"],
            "suppress_tokens": ["light", "sun"],
            "boost_factor": 2.0,
            "max_new_tokens": 50,
            "temperature": 0.7,
            "seed": -1
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    prompt = data.get("prompt")
    model_id = data.get("model_id")

    if not prompt or not model_id:
        return jsonify({"error": "prompt and model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.generate_with_token_surgery(
        prompt=prompt,
        model_id=model_id,
        boost_tokens=data.get("boost_tokens"),
        suppress_tokens=data.get("suppress_tokens"),
        boost_factor=data.get("boost_factor", 2.0),
        max_new_tokens=data.get("max_new_tokens", 50),
        temperature=data.get("temperature", 0.7),
        seed=data.get("seed", -1),
    ))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/generate/stream', methods=['POST'])
def generate_streaming():
    """
    Generate text with real-time SSE streaming.

    Request:
        {
            "prompt": "Once upon a time",
            "model_id": "...",
            "max_new_tokens": 100,
            "temperature": 0.7,
            "seed": -1
        }

    Response: text/event-stream with events:
        data: {"type": "token", "token": "...", "token_id": 123}
        data: {"type": "done", "full_text": "..."}
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    prompt = data.get("prompt")
    model_id = data.get("model_id")

    if not prompt or not model_id:
        return jsonify({"error": "prompt and model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    def generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            async def stream():
                async for chunk in backend.generate_streaming(
                    prompt=prompt,
                    model_id=model_id,
                    max_new_tokens=data.get("max_new_tokens", 100),
                    temperature=data.get("temperature", 0.7),
                    seed=data.get("seed", -1),
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"

            gen = stream()
            while True:
                try:
                    chunk = loop.run_until_complete(gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@text_bp.route('/variations', methods=['POST'])
def generate_variations():
    """
    Generate deterministic variations with different seeds.

    Request:
        {
            "prompt": "The meaning of life is",
            "model_id": "...",
            "num_variations": 5,
            "base_seed": 42,
            "temperature": 0.8,
            "max_new_tokens": 50
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    prompt = data.get("prompt")
    model_id = data.get("model_id")

    if not prompt or not model_id:
        return jsonify({"error": "prompt and model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.generate_variations(
        prompt=prompt,
        model_id=model_id,
        num_variations=data.get("num_variations", 5),
        temperature=data.get("temperature", 0.8),
        base_seed=data.get("base_seed", 42),
        max_new_tokens=data.get("max_new_tokens", 50),
    ))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/rep-engineering', methods=['POST'])
def rep_engineering():
    """
    Representation Engineering: find concept directions and manipulate generation.

    Request:
        {
            "contrast_pairs": [
                {"positive": "Paris is the capital of France", "negative": "Paris is the capital of Germany"},
                ...
            ],
            "model_id": "...",
            "target_layer": -1,
            "test_text": "Berlin is the capital of...",
            "alpha": 1.0,
            "max_new_tokens": 50,
            "temperature": 0.7,
            "seed": -1
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    contrast_pairs = data.get("contrast_pairs")
    model_id = data.get("model_id")

    if not contrast_pairs or not model_id:
        return jsonify({"error": "contrast_pairs and model_id required"}), 400

    if not isinstance(contrast_pairs, list) or len(contrast_pairs) < 1:
        return jsonify({"error": "contrast_pairs must be a non-empty list"}), 400

    for pair in contrast_pairs:
        if not isinstance(pair, dict) or "positive" not in pair or "negative" not in pair:
            return jsonify({"error": "Each pair must have 'positive' and 'negative' keys"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.rep_engineering(
        contrast_pairs=contrast_pairs,
        model_id=model_id,
        target_layer=data.get("target_layer", -1),
        test_text=data.get("test_text"),
        alpha=data.get("alpha", 1.0),
        max_new_tokens=data.get("max_new_tokens", 50),
        temperature=data.get("temperature", 0.7),
        seed=data.get("seed", -1),
    ))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/compare', methods=['POST'])
def compare_models():
    """
    Compare two models' internal representations.

    Request:
        {
            "text": "The quick brown fox",
            "model_id_a": "...",
            "model_id_b": "...",
            "max_new_tokens": 50,
            "temperature": 0.7,
            "seed": 42
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    text = data.get("text")
    model_id_a = data.get("model_id_a")
    model_id_b = data.get("model_id_b")

    if not text or not model_id_a or not model_id_b:
        return jsonify({"error": "text, model_id_a, and model_id_b required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.compare_models(
        text=text,
        model_id_a=model_id_a,
        model_id_b=model_id_b,
        max_new_tokens=data.get("max_new_tokens", 50),
        temperature=data.get("temperature", 0.7),
        seed=data.get("seed", 42),
    ))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/bias-probe', methods=['POST'])
def bias_probe():
    """
    Systematic bias probing through controlled token manipulation.

    Request:
        {
            "prompt": "The doctor said",
            "model_id": "...",
            "bias_type": "gender",
            "custom_boost": null,
            "custom_suppress": null,
            "num_samples": 3,
            "max_new_tokens": 50,
            "temperature": 0.7,
            "seed": 42
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    prompt = data.get("prompt")
    model_id = data.get("model_id")

    if not prompt or not model_id:
        return jsonify({"error": "prompt and model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.bias_probe(
        prompt=prompt,
        model_id=model_id,
        bias_type=data.get("bias_type", "gender"),
        custom_boost=data.get("custom_boost"),
        custom_suppress=data.get("custom_suppress"),
        num_samples=data.get("num_samples", 3),
        max_new_tokens=data.get("max_new_tokens", 50),
        temperature=data.get("temperature", 0.7),
        seed=data.get("seed", 42),
    ))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/layers', methods=['POST'])
def compare_layers():
    """
    Analyze how representations change through layers.

    Request:
        {
            "text": "Understanding emerges gradually",
            "model_id": "..."
        }
    """
    from config import TEXT_ENABLED
    if not TEXT_ENABLED:
        return jsonify({"error": "Text backend disabled"}), 503

    data = request.get_json() or {}
    text = data.get("text")
    model_id = data.get("model_id")

    if not text or not model_id:
        return jsonify({"error": "text and model_id required"}), 400

    from services.text_backend import get_text_backend
    backend = get_text_backend()

    result = run_async(backend.compare_layer_outputs(text, model_id))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)
