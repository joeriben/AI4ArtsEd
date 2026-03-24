"""
Text Routes — DevServer proxy to GPU service's Latent Text Lab

Session 176: Proxies REST + SSE endpoints for dekonstruktive LLM operations.
Session 177: Added rep-engineering, compare, bias-probe endpoints.
Frontend calls /api/text/* → DevServer → GPU service (port 17803).

Endpoints:
- GET  /api/text/models - List loaded models
- GET  /api/text/presets - List available model presets
- POST /api/text/load - Load model
- POST /api/text/unload - Unload model
- POST /api/text/embedding - Get prompt embedding
- POST /api/text/interpolate - Interpolate between prompts
- POST /api/text/attention - Get attention maps
- POST /api/text/rep-engineering - Representation Engineering (Zou 2023)
- POST /api/text/compare - Comparative Model Archaeology
- POST /api/text/bias-probe - Bias Archaeology
- POST /api/text/generate - Generate with token surgery
- POST /api/text/generate/stream - SSE streaming generation
- POST /api/text/variations - Generate seed variations
- POST /api/text/layers - Compare layer outputs
"""

import logging
import asyncio
import json

from flask import Blueprint, request, jsonify, Response, stream_with_context

logger = logging.getLogger(__name__)

text_bp = Blueprint('text', __name__, url_prefix='/api/text')


def _run_async(coro):
    """Run async coroutine in sync Flask context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_client():
    """Get TextClient singleton (lazy import)."""
    from my_app.services.text_client import get_text_client
    return get_text_client()


# =============================================================================
# Model Management
# =============================================================================

@text_bp.route('/models', methods=['GET'])
def list_models():
    """List currently loaded models."""
    client = _get_client()
    models = _run_async(client.get_loaded_models())
    return jsonify({"models": models})


@text_bp.route('/presets', methods=['GET'])
def list_presets():
    """List available model presets with VRAM info."""
    scenario = request.args.get("scenario", "qwen")
    client = _get_client()
    data = _run_async(client.get_presets(scenario=scenario))
    return jsonify(data)


@text_bp.route('/load', methods=['POST'])
def load_model():
    """Load an LLM model."""
    data = request.get_json() or {}
    model_id = data.get("model_id")
    quantization = data.get("quantization")

    if not model_id:
        return jsonify({"error": "model_id required"}), 400

    client = _get_client()
    result = _run_async(client.load_model(model_id, quantization))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/unload', methods=['POST'])
def unload_model():
    """Unload a specific model."""
    data = request.get_json() or {}
    model_id = data.get("model_id")

    if not model_id:
        return jsonify({"error": "model_id required"}), 400

    client = _get_client()
    result = _run_async(client.unload_model(model_id))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


# =============================================================================
# Dekonstruktive Operations
# =============================================================================

@text_bp.route('/embedding', methods=['POST'])
def get_embedding():
    """Get embedding representation of a prompt."""
    data = request.get_json() or {}
    text = data.get("text")
    model_id = data.get("model_id")
    layer = data.get("layer", -1)

    if not text or not model_id:
        return jsonify({"error": "text and model_id required"}), 400

    client = _get_client()
    result = _run_async(client.get_prompt_embedding(text, model_id, layer))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/interpolate', methods=['POST'])
def interpolate_prompts():
    """Analyze embedding space between two prompts."""
    data = request.get_json() or {}
    prompt_a = data.get("prompt_a")
    prompt_b = data.get("prompt_b")
    model_id = data.get("model_id")
    steps = data.get("steps", 5)
    layer = data.get("layer", -1)

    if not prompt_a or not prompt_b or not model_id:
        return jsonify({"error": "prompt_a, prompt_b, and model_id required"}), 400

    client = _get_client()
    result = _run_async(client.interpolate_prompts(prompt_a, prompt_b, model_id, steps, layer))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/attention', methods=['POST'])
def get_attention():
    """Get attention patterns for visualization."""
    data = request.get_json() or {}
    text = data.get("text")
    model_id = data.get("model_id")
    layer = data.get("layer")
    head = data.get("head")

    if not text or not model_id:
        return jsonify({"error": "text and model_id required"}), 400

    client = _get_client()
    result = _run_async(client.get_attention_map(text, model_id, layer, head))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@text_bp.route('/rep-engineering', methods=['POST'])
def rep_engineering():
    """Representation Engineering: concept directions via contrast pairs."""
    data = request.get_json() or {}
    contrast_pairs = data.get("contrast_pairs")
    model_id = data.get("model_id")

    if not contrast_pairs or not model_id:
        return jsonify({"error": "contrast_pairs and model_id required"}), 400

    client = _get_client()
    result = _run_async(client.rep_engineering(
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
    """Compare two models' internal representations."""
    data = request.get_json() or {}
    text = data.get("text")
    model_id_a = data.get("model_id_a")
    model_id_b = data.get("model_id_b")

    if not text or not model_id_a or not model_id_b:
        return jsonify({"error": "text, model_id_a, and model_id_b required"}), 400

    client = _get_client()
    result = _run_async(client.compare_models(
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
    """Systematic bias probing through controlled token manipulation."""
    data = request.get_json() or {}
    prompt = data.get("prompt")
    model_id = data.get("model_id")

    if not prompt or not model_id:
        return jsonify({"error": "prompt and model_id required"}), 400

    client = _get_client()
    result = _run_async(client.bias_probe(
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


@text_bp.route('/generate', methods=['POST'])
def generate_with_surgery():
    """Generate text with token-level logit manipulation."""
    data = request.get_json() or {}
    prompt = data.get("prompt")
    model_id = data.get("model_id")

    if not prompt or not model_id:
        return jsonify({"error": "prompt and model_id required"}), 400

    client = _get_client()
    result = _run_async(client.generate_with_token_surgery(
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
    """SSE streaming generation — proxy raw bytes from GPU service."""
    data = request.get_json() or {}
    prompt = data.get("prompt")
    model_id = data.get("model_id")

    if not prompt or not model_id:
        return jsonify({"error": "prompt and model_id required"}), 400

    import requests as http_requests
    from config import GPU_SERVICE_URL

    gpu_url = f"{GPU_SERVICE_URL.rstrip('/')}/api/text/generate/stream"

    def proxy_stream():
        try:
            with http_requests.post(gpu_url, json=data, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        yield line.decode('utf-8') + '\n\n'
        except http_requests.ConnectionError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'GPU service unreachable'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream_with_context(proxy_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@text_bp.route('/variations', methods=['POST'])
def generate_variations():
    """Generate deterministic variations with different seeds."""
    data = request.get_json() or {}
    prompt = data.get("prompt")
    model_id = data.get("model_id")

    if not prompt or not model_id:
        return jsonify({"error": "prompt and model_id required"}), 400

    client = _get_client()
    result = _run_async(client.generate_variations(
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


@text_bp.route('/layers', methods=['POST'])
def compare_layers():
    """Analyze how representations change through layers."""
    data = request.get_json() or {}
    text = data.get("text")
    model_id = data.get("model_id")

    if not text or not model_id:
        return jsonify({"error": "text and model_id required"}), 400

    client = _get_client()
    result = _run_async(client.compare_layer_outputs(text, model_id))

    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


# =============================================================================
# LLM Interpretation of Experiment Results
# =============================================================================

INTERPRETATION_SYSTEM_PROMPTS = {
    "repeng": (
        "Du erklärst Jugendlichen (13-17) das Ergebnis eines Representation-Engineering-Experiments. "
        "Fokus auf den MECHANISMUS, nicht auf den Inhalt der generierten Texte. "
        "WICHTIG: Beachte den α-Wert (alpha) genau! "
        "α < 0 = Richtung wird INVERTIERT (Wahrheitstendenz umgekehrt → Modell sollte falsch antworten). "
        "α > 0 = Richtung wird VERSTÄRKT (Wahrheitstendenz verstärkt → Modell sollte noch sicherer korrekt antworten). "
        "α = 0 wäre keine Manipulation (kommt nicht vor). "
        "Bei α > 0: Wenn sich wenig ändert, ist das ERWARTET — das Modell war schon korrekt, mehr Wahrheit ändert wenig. "
        "Bei α < 0: Wenn sich etwas ändert, zeigt das dass Wissen und Wahrheitstendenz GETRENNT kodiert sind. "
        "Bei identischen Outputs: Richtung war zu schwach oder kodiert nicht das Zielkonzept. "
        "3-5 Sätze, sachlich, kein Fachjargon. Antworte in der Sprache der Eingabe."
    ),
    "bias": (
        "Du erklärst Jugendlichen (13-17) das Ergebnis eines Bias-Experiments. "
        "Vergleiche Baseline mit den Manipulationsgruppen: "
        "Was ändert sich, wenn bestimmte Tokens unterdrückt oder verstärkt werden? "
        "Wenn sich nichts ändert: Erkläre warum (z.B. Modell nutzt geschlechtsneutrale Defaults). "
        "Wenn sich etwas ändert: Welche Voreinstellungen des Modells werden sichtbar? "
        "3-5 Sätze, sachlich, kein Fachjargon. Antworte in der Sprache der Eingabe."
    ),
    "compare": (
        "Du erklärst Jugendlichen (13-17) den Vergleich zweier KI-Modelle. "
        "Fokus: Wo liefern die Modelle ähnliche Ergebnisse, wo unterscheiden sie sich? "
        "Was sagt das über die unterschiedliche 'Weltsicht' der Modelle? "
        "Beachte Modellgröße, Trainingsunterschiede und die CKA-Ähnlichkeit. "
        "3-5 Sätze, sachlich, kein Fachjargon. Antworte in der Sprache der Eingabe."
    ),
}


def _build_interpretation_prompt(results: dict, experiment_type: str) -> str:
    """Format experiment results into a structured prompt for the LLM."""
    parts = []

    if experiment_type == "bias":
        parts.append(f"Experiment: Bias-Archäologie ({results.get('bias_type', 'unknown')})")
        parts.append(f"Prompt: \"{results.get('prompt', '')}\"")
        parts.append(f"Modell: {results.get('model_id', 'unknown')}")

        baseline = results.get("baseline", [])
        if baseline:
            parts.append("\nBaseline (keine Manipulation):")
            for s in baseline:
                parts.append(f"  Seed {s.get('seed')}: {s.get('text', '')}")

        for group in results.get("groups", []):
            name = group.get("group_name", "")
            mode = group.get("mode", "")
            tokens = ", ".join(group.get("tokens", []))
            parts.append(f"\nGruppe '{name}' ({mode}), Tokens: [{tokens}]:")
            for s in group.get("samples", []):
                parts.append(f"  Seed {s.get('seed')}: {s.get('text', '')}")

        parts.append("\nVergleiche Baseline mit den Gruppen. Was zeigt das über die Voreinstellungen des Modells?")

    elif experiment_type == "repeng":
        alpha = results.get('alpha', 0)
        if alpha < 0:
            mode_desc = "invertiert (Wahrheitstendenz umgekehrt)"
        elif alpha > 0:
            mode_desc = "verstärkt (Wahrheitstendenz verstärkt)"
        else:
            mode_desc = "neutral"
        parts.append(f"Experiment: Representation Engineering — Wahrheitsrichtung {mode_desc}")
        parts.append(f"Kontrastpaare: {results.get('num_pairs', '?')} Paare (wahr vs. falsch)")
        parts.append(f"Erklärte Varianz: {results.get('explained_variance', 0):.1%}")
        parts.append(f"Manipulationsstärke: α = {alpha} ({'Invertierung' if alpha < 0 else 'Verstärkung'})")
        parts.append(f"\nBaseline (α = 0, keine Manipulation):\n  {results.get('baseline_text', '')}")
        parts.append(f"\nManipuliert (α = {alpha}):\n  {results.get('manipulated_text', '')}")

        if results.get('baseline_text') == results.get('manipulated_text'):
            parts.append("\nDie Texte sind IDENTISCH. Die Manipulation hatte keinen Effekt. Erkläre warum das passieren kann.")
        elif alpha < 0:
            parts.append("\nDie Texte sind UNTERSCHIEDLICH. Die Richtung wurde INVERTIERT (α < 0). "
                         "Erkläre den Mechanismus: Warum antwortet das Modell jetzt falsch, obwohl es die Antwort 'kennt'? "
                         "Nicht den Inhalt analysieren, sondern erklären dass Wissen und Wahrheitstendenz getrennt kodiert sind.")
        else:
            parts.append(f"\nDie Texte sind UNTERSCHIEDLICH. Die Richtung wurde VERSTÄRKT (α = {alpha}). "
                         "Erkläre was sich geändert hat. Bei α > 0 ist wenig Änderung ERWARTET — "
                         "wenn das Modell schon korrekt antwortet, bringt mehr Wahrheitstendenz wenig Neues.")

    elif experiment_type == "compare":
        parts.append("Experiment: Vergleichende Modell-Archäologie")
        ma = results.get("model_a", {})
        mb = results.get("model_b", {})
        parts.append(f"Modell A ({ma.get('model_id', '?')}): {ma.get('generated_text', '')}")
        parts.append(f"Modell B ({mb.get('model_id', '?')}): {mb.get('generated_text', '')}")
        parts.append("\nWorin unterscheiden sich die Antworten? Was sagt das über die Modelle?")

    return "\n".join(parts)


@text_bp.route('/interpret', methods=['POST'])
def interpret_results():
    """LLM interpretation of experiment results (bias, repeng, compare)."""
    data = request.get_json() or {}
    results = data.get("results")
    experiment_type = data.get("experiment_type")

    if not results or not experiment_type:
        return jsonify({"error": "results and experiment_type required"}), 400

    prompt = _build_interpretation_prompt(results, experiment_type)

    from my_app.routes.chat_routes import call_chat_helper
    try:
        system_prompt = INTERPRETATION_SYSTEM_PROMPTS.get(experiment_type, INTERPRETATION_SYSTEM_PROMPTS["bias"])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        response = call_chat_helper(messages, temperature=0.5, max_tokens=400)
        return jsonify({"interpretation": response["content"]})
    except Exception as e:
        logger.warning(f"[TEXT] Interpretation failed: {e}")
        return jsonify({"error": str(e)}), 500
