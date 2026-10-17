"""
Text Routes — the doors of the Latent Text Lab

Proxies REST + SSE endpoints for dekonstruktive LLM operations, including
the rep-engineering and bias-probe endpoints.
Stage 5 of the move to ComfyUI: the coreference contrast, BBQ, Representation
Engineering and the model row are answered from services/text_probes and
services/text_presets (one prompt of a node of the platform's package on
ComfyUI; the table config/text_presets.json), the tokenizer doors from
ComfyUI's HTTP routes. The routes no surface named (models, load, unload,
embedding, interpolate, attention, contrast-control, generate, variations,
layers) were struck in stage 8.

Endpoints:
- GET  /api/text/presets - List available model presets
- POST /api/text/tokenize - Cut a text into tokens (no GPU, no model)
- GET  /api/text/tokenizers - Which tokenizers this machine has
- POST /api/text/encoder-rows - Which piece stands in which row at CLIP and T5 (no GPU, no model)
- POST /api/text/rep-engineering - Representation Engineering (Zou 2023)
- POST /api/text/bias-probe - Bias Archaeology
- POST /api/text/bbq-probe - BBQ: does the model name someone where the text does not say?
- GET  /api/text/bbq-overview - what is in the benchmark, without running a model
- GET  /api/text/bbq-sample - a fresh draw of questions for one run
- POST /api/text/bbq-record - keep one finished model series
- GET  /api/text/bbq-stats - the platform's own history of the bias score
- GET  /api/text/bias-corpus - the pairs one run walks, without running a model
"""

import logging
from my_app.services.own_loop import run_blocking
import json
from pathlib import Path

from flask import Blueprint, request, jsonify

from my_app.services.streaming_response import answered_either_way

logger = logging.getLogger(__name__)

text_bp = Blueprint('text', __name__, url_prefix='/api/text')


def _get_client():
    """Get TextClient singleton (lazy import)."""
    from my_app.services.text_client import get_text_client
    return get_text_client()


# The tokenizers the comparison instrument offers: id, label, role. A table
# under devserver/config/, not code — a model id is data. Read on every call;
# it is a few hundred bytes, and an edit to the table is live at once.
_TOKENIZER_CATALOGUE = Path(__file__).resolve().parent.parent.parent / "config" / "tokenizer_catalogue.json"


def _tokenizer_catalogue() -> list:
    """The rows of the table. Raises OSError, ValueError or KeyError with the
    cause when the file is missing, no JSON, or holds no `tokenizers`."""
    with open(_TOKENIZER_CATALOGUE, encoding="utf-8") as f:
        return json.load(f)["tokenizers"]


def _catalogue_or_refusal():
    """(rows, None) or (None, the 500 to answer with)."""
    try:
        return _tokenizer_catalogue(), None
    except (OSError, ValueError, KeyError) as e:
        logger.error(f"[TEXT-ROUTES] the tokenizer table could not be read: {e}")
        return None, (jsonify({"error": f"the tokenizer table {_TOKENIZER_CATALOGUE.name} "
                                        f"could not be read: {e}"}), 500)


# =============================================================================
# Model Management
# =============================================================================


@text_bp.route('/presets', methods=['GET'])
def list_presets():
    """One row of the Text Lab's models: the installed members, the missing
    ones, and whether each fits the card."""
    from my_app.services import text_presets
    from my_app.services.gpu_card import CardUnreadable
    scenario = request.args.get("scenario", "qwen")
    try:
        return jsonify(text_presets.listing(scenario))
    except KeyError as e:
        return jsonify({"error": str(e.args[0]) if e.args else str(e)}), 400
    except CardUnreadable as e:
        # No card size, no fit: the row is refused with the cause, as a run
        # would be.
        return jsonify({"error": f"the card could not be read, so no fit can be said: {e}"}), 503
    except (OSError, ValueError) as e:
        logger.error(f"[TEXT-ROUTES] the model rows could not be read: {e}")
        return jsonify({"error": f"the table {text_presets.TABLE_FILE.name} could not be read: {e}"}), 500



# =============================================================================
# Dekonstruktive Operations
# =============================================================================


@text_bp.route('/tokenize', methods=['POST'])
def tokenize_text():
    """Cut a text into tokens. Reads a vocabulary file, holds no model.

    The cut is made on ComfyUI (the node package answers it on ComfyUI's HTTP
    server, off the queue); which tokenizers may be asked is this table's
    business, and the label and role of the one asked go into the answer here.
    """
    data = request.get_json() or {}
    text = data.get("text")
    model_id = data.get("model_id")

    if not text or not model_id:
        return jsonify({"error": "text and model_id required"}), 400
    catalogue, refusal = _catalogue_or_refusal()
    if refusal is not None:
        return refusal
    entry = next((e for e in catalogue if e["id"] == model_id), None)
    if entry is None:
        return jsonify({"error": f"Unknown tokenizer: {model_id}"}), 400

    client = _get_client()
    result = run_blocking(client.tokenize(text, model_id))

    if "error" in result:
        return jsonify(result), result.get("http_status", 500)
    result.update(label=entry["label"], role=entry["role"])
    return jsonify(result)


@text_bp.route('/tokenizers', methods=['GET'])
def list_tokenizers():
    """Which tokenizers are available, with vocabulary size and window.

    The rows are the table's; whether each one is on the machine, and its
    window and matrix, is asked of ComfyUI in one call.
    """
    catalogue, refusal = _catalogue_or_refusal()
    if refusal is not None:
        return refusal
    client = _get_client()
    facts = run_blocking(client.tokenizer_facts([e["id"] for e in catalogue]))

    if "error" in facts:
        return jsonify(facts), facts.get("http_status", 500)
    rows = []
    for entry in catalogue:
        row = dict(entry)
        row.update(facts.get(entry["id"]) or {"available": False})
        rows.append(row)
    return jsonify({"tokenizers": rows})


@text_bp.route('/encoder-rows', methods=['POST'])
def encoder_rows():
    """The rows of SD 3.5's conditioning table one text fills: the pieces CLIP
    and T5 cut it into, row by row, as the Surrealizer's graph lays them
    (comfyui_nodes/ai4artsed_comfyui/_tokenizers.py::encoder_rows). The T5
    block's length is the one the graphs set, so the rows are the run's.
    Reads two vocabulary files on ComfyUI, off its queue; no model.
    """
    data = request.get_json() or {}
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "text required"}), 400

    from schemas.engine.comfyui_chunk_support import T5_LENGTH
    client = _get_client()
    result = run_blocking(client.encoder_rows(text, T5_LENGTH))

    if "error" in result:
        return jsonify(result), result.get("http_status", 500)
    return jsonify(result)


@text_bp.route('/rep-engineering', methods=['POST'])
def rep_engineering():
    """Representation Engineering: concept directions via contrast pairs."""
    data = request.get_json() or {}
    contrast_pairs = data.get("contrast_pairs")
    model_id = data.get("model_id")

    if not contrast_pairs or not model_id:
        return jsonify({"error": "contrast_pairs and model_id required"}), 400

    # With "enable_streaming" the answer travels as the platform's SSE stream
    # instead of as one JSON body. It is the same work; only its way back is
    # different. What the stream adds is the heartbeat, and the heartbeat is
    # what carries the name of the model at work to the bar while a probe that
    # reads every layer of a 9B model keeps the card busy for minutes.
    #
    # The work names no `client_gone` parameter, and that is a decision rather
    # than an omission: one upstream call stands behind it and leaving would not
    # end it, only lose the answer to a probe already run.
    return answered_either_way(data, _run_rep_engineering, data,
                               label='TEXT-REP-ENGINEERING')


def _run_rep_engineering(data):
    """The concept directions, and the ``(payload, http_status)`` they answer with.

    Split from the route so that one call can be answered either way. It must
    not reach for ``request``: the body is read at the request boundary and
    passed in, and a streamed answer runs this on a thread of its own.
    """
    from my_app.services import text_probes
    result = text_probes.rep_engineering(
        contrast_pairs=data.get("contrast_pairs"),
        model_id=data.get("model_id"),
        target_layer=data.get("target_layer"),
        test_text=data.get("test_text"),
        alpha=data.get("alpha", 1.0),
        alphas=data.get("alphas"),
        max_new_tokens=data.get("max_new_tokens"),
        temperature=data.get("temperature", 0.7),
        seed=data.get("seed", -1),
    )

    if "error" in result:
        return result, result.get("http_status", 500)
    return result, 200



@text_bp.route('/bias-probe', methods=['POST'])
def bias_probe():
    """Who a pronoun refers to, in two sentences one word apart."""
    data = request.get_json() or {}
    model_id = data.get("model_id")
    if not model_id:
        return jsonify({"error": "model_id required"}), 400

    # Answered either way; see `/rep-engineering` above for what the stream is
    # for. A probe runs one item after another and takes as long as the list.
    return answered_either_way(data, _run_bias_probe, data,
                               label='TEXT-BIAS-PROBE')


def _run_bias_probe(data):
    """The reference readings, and the ``(payload, http_status)`` they answer with."""
    from my_app.services import text_probes
    result = text_probes.bias_probe(
        model_id=data.get("model_id"),
        item_ids=data.get("item_ids"),
    )

    if "error" in result:
        return result, result.get("http_status", 500)
    return result, 200


def _bbq_level() -> str:
    """The safety level this installation runs at, resolved HERE.

    Never taken from the request. What a course at the kids level is offered -
    which categories, and which situations inside them - is decided by the
    level, and a client that could name its own level could hand a group of
    children material its course does not allow. The screen itself lives in
    services/bbq_corpus.py (KIDS_CATEGORIES, KIDS_EXCLUDE); the list in the
    Vue file only decides what a dropdown shows.
    """
    from my_app.services.safety_level_resolver import resolve_safety_level
    return resolve_safety_level()


@text_bp.route('/bbq-probe', methods=['POST'])
def bbq_probe():
    """BBQ: does the model name someone where the text does not say?"""
    data = request.get_json() or {}
    model_id = data.get("model_id")
    if not model_id:
        return jsonify({"error": "model_id required"}), 400

    # The level is resolved HERE and handed down. A streamed answer runs the
    # work on a thread of its own, where there is no request to resolve it from
    # — and a level that failed to resolve would be the one thing on this route
    # that must never be got wrong (see `_bbq_level`).
    level = _bbq_level()
    return answered_either_way(data, _run_bbq_probe, data, level,
                               label='TEXT-BBQ-PROBE')


def _run_bbq_probe(data, level):
    """The BBQ readings, and the ``(payload, http_status)`` they answer with."""
    from my_app.services import text_probes
    result = text_probes.bbq_probe(
        model_id=data.get("model_id"),
        item_ids=data.get("item_ids"),
        category=data.get("category", "Gender_identity"),
        situations=int(data.get("situations", 30)),
        level=level,
    )

    if "error" in result:
        return result, result.get("http_status", 500)
    return result, 200


@text_bp.route('/bbq-overview', methods=['GET'])
def bbq_overview():
    """What is in the benchmark, without running a model."""
    from my_app.services import text_probes
    return jsonify(text_probes.bbq_overview(_bbq_level()))


@text_bp.route('/bbq-sample', methods=['GET'])
def bbq_sample():
    """A fresh draw of questions for one run."""
    from my_app.services import text_probes
    seed = request.args.get('seed')
    result = text_probes.bbq_sample(
        request.args.get('category', 'Gender_identity'),
        int(request.args.get('situations', 30)),
        int(seed) if seed not in (None, '') else None,
        _bbq_level(),
    )
    if "error" in result:
        # 403 where the level is not offered the category, 503 where the
        # benchmark was never fetched (download_bbq.sh).
        return jsonify(result), result.get("http_status", 500)
    # These strings are now allowed to have their translation kept. What the
    # translate endpoint may store is decided by what this server served, not
    # by what a request claims; see services/translation_cache.py.
    try:
        from my_app.services import translation_cache
        translation_cache.admit("bbq", (
            piece
            for item in (result.get("items") or [])
            for piece in [item.get("context"), item.get("question"), *(item.get("answers") or [])]
            if isinstance(piece, str)
        ))
    except Exception as exc:
        logger.warning(f"[BBQ-SAMPLE] could not admit for translation: {exc}")
    return jsonify(result)


@text_bp.route('/bbq-record', methods=['POST'])
def bbq_record():
    """Keep what one model series measured, so later runs have a reference."""
    data = request.get_json() or {}
    if not data.get("model_id"):
        return jsonify({"error": "model_id required"}), 400

    from my_app.services import bbq_runs
    bbq_runs.record(data)
    return jsonify(bbq_runs.summary(
        data.get("category") or None,
        data.get("instrument") or None,
    ))


@text_bp.route('/bbq-stats', methods=['GET'])
def bbq_stats():
    """The platform's own history of the bias score. No model is run for this."""
    from my_app.services import bbq_runs
    category = request.args.get('category') or None
    return jsonify(bbq_runs.summary(category, request.args.get('instrument') or None))


@text_bp.route('/bias-corpus', methods=['GET'])
def bias_corpus():
    """The pairs one run walks, without running a model.

    The level is resolved HERE, never taken from the request: the vetted sixty
    are what the kids level runs, and only above it is there a draw from the
    whole checked pool. A client that asked for its own level could otherwise
    hand a group material its course does not allow.
    """
    from my_app.services.safety_level_resolver import resolve_safety_level
    level = resolve_safety_level()
    try:
        pairs = int(request.args.get('pairs', 60))
    except (TypeError, ValueError):
        pairs = 60
    seed = request.args.get('seed')
    try:
        seed = int(seed) if seed is not None else None
    except (TypeError, ValueError):
        seed = None

    from my_app.services import text_probes
    result = text_probes.bias_corpus(level=level, pairs=pairs, seed=seed)
    if "error" in result:
        # A missing dataset is a deployment matter, not a failure of the run:
        # the answer names the script that fetches it, with a 503.
        return jsonify(result), result.get("http_status", 500)
    # As with the questions: what may have its translation kept is what this
    # server served. See services/translation_cache.py.
    try:
        from my_app.services import translation_cache
        translation_cache.admit("winobias", (
            piece
            for pair in (result.get("pairs") or [])
            for piece in [
                (pair.get("matching") or {}).get("sentence"),
                (pair.get("other") or {}).get("sentence"),
            ]
            if isinstance(piece, str)
        ))
    except Exception as exc:
        logger.warning(f"[BIAS-CORPUS] could not admit for translation: {exc}")
    return jsonify(result)



# =============================================================================
# LLM Interpretation of Experiment Results
# =============================================================================


