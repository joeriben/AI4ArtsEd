"""
LLM Routes — Local LLM inference endpoints.

Local LLM inference for safety checks, DSGVO verification, VLM safety.
"""

import logging
from flask import Blueprint, request, jsonify


logger = logging.getLogger(__name__)

llm_bp = Blueprint('llm', __name__, url_prefix='/api/llm')

# Long enough to carry a child's last lines. The DevServer prints what comes
# back (LLMClient._body_reason), and "500 inference failed" is a sentence that
# sends whoever reads the log looking in the wrong place; the exit code and the
# five lines before it name the cause outright.
_ERROR_CHARS = 1200


def _llm_error(e):
    """One HTTP answer per failure class, with the real cause in the body.

    503 for a load that never happened — the request was not begun, and the same
    request works once there is room. 503 as well when the child itself answered
    503 (it is still loading). 500 for a child that died mid-answer or refused
    the request, with the child's own message.
    """
    from services.llm_child_backend import ChildDied, ChildRequestError

    if isinstance(e, ChildRequestError):
        logger.error(f"[LLM] {e}")
        return jsonify({"error": str(e)[:_ERROR_CHARS]}), e.route_status
    if isinstance(e, ChildDied):
        logger.error(f"[LLM] {e}")
        return jsonify({"error": str(e)[:_ERROR_CHARS]}), 500
    # ModelLoadRefused: nothing was inferred, the model never reached the card,
    # and the message already says what stood in the way.
    logger.error(f"[LLM] {e}")
    return jsonify({"error": str(e)[:_ERROR_CHARS]}), 503


def _engine():
    """(backend, None), or (None, the JSON refusal that says why there is none).

    Building the engine can fail before a single request is served: an
    LLM_ENGINE nobody knows, a state directory the supervisor refuses. Raised
    out of a route that does not catch it, that reaches the DevServer as Flask's
    own 500 with an HTML page — and the log then says "500 Server Error" for a
    fault whose message names the variable and the value. 503, because nothing
    was attempted and the same request works once the configuration is right.
    """
    from services.llm_child_backend import get_llm_backend

    try:
        return get_llm_backend(), None
    except Exception as e:  # noqa: BLE001
        logger.error(f"[LLM] The engine could not be built: {e}")
        return None, (jsonify({"error": str(e)[:_ERROR_CHARS]}), 503)


def _llm_failures():
    """The exception classes the routes below answer for, as a tuple."""
    from services.llm_child_backend import (ChildDied, ChildRequestError,
                                            ModelLoadRefused)
    return (ModelLoadRefused, ChildDied, ChildRequestError)



@llm_bp.route('/classify', methods=['POST'])
def llm_classify():
    """
    Safety classification: one yes/no question about one document.

    Request:
        {
            "model": "shieldstral:3b",
            "instruct": "...",        // the policy and how strictly to read it
            "query": "...",           // one yes/no question
            "document": "...",        // the text under examination
            "images": ["base64..."]   // optional, one picture or several
        }

    Response:
        {"score": 0.87}   the probability of "yes"

    The caller decides what the score means: for a question asked as "is this
    unsafe", high is a block. A request that produced no answer is an error
    with a status, never a score -- the check that cannot answer must not be
    able to look like a check that answered "no".
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    model = data.get("model", "")
    instruct = data.get("instruct", "")
    query = data.get("query", "")
    document = data.get("document", "")
    if not model or not instruct or not query:
        return jsonify({"error": "model, instruct and query required"}), 400
    if not document and not data.get("images"):
        return jsonify({"error": "document or images required"}), 400

    backend, refusal = _engine()
    if refusal is not None:
        return refusal
    classify = getattr(backend, "classify", None)
    if classify is None:
        return jsonify({"error": "this engine cannot classify; "
                                 "LLM_ENGINE=child is the one that can"}), 501
    try:
        score = classify(model=model, instruct=instruct, query=query,
                         document=document, images=data.get("images"))
    except _llm_failures() as e:
        return _llm_error(e)

    if score is None:
        return jsonify({"error": f"{model} gave no verdict"}), 500

    return jsonify({"score": score})



@llm_bp.route('/models', methods=['GET'])
def llm_models():
    """List available and loaded LLM models.

    A loaded entry additionally carries pid, port and state: with one process
    per model, an operator looking at a wedged reading needs to know which
    process it is before they can do anything about it.
    """
    backend, refusal = _engine()
    if refusal is not None:
        return refusal
    return jsonify({
        "available": backend.get_available_models(),
        "loaded": backend.get_loaded_models(),
    })


@llm_bp.route('/unload', methods=['POST'])
def llm_unload():
    """Unload a specific LLM model to free VRAM.

    Request:
        {"model": "...", "force": false}

    force is the operator's escape hatch for a child whose refcount never came
    back — a wedged reading, a consumer that vanished. It skips the busy check
    and nothing else, and the requests still in flight on that child fail. Only
    the child engine can honour it; in-process, freeing a model under a running
    generation takes the service down, so there it is refused and said so.
    """
    data = request.get_json()
    if not data or not data.get("model"):
        return jsonify({"error": "model required"}), 400

    backend, refusal = _engine()
    if refusal is not None:
        return refusal
    force = bool(data.get("force"))
    success = backend.unload(data["model"], force=force)
    # A refusal has to be visible: callers read the HTTP status, not the body
    # (devserver settings_routes does exactly that), and a model reported as
    # unloaded while it still sits on the card is how the card fills up.
    return (jsonify({"success": success, "model": data["model"], "force": force}),
            (200 if success else 409))


@llm_bp.route('/health', methods=['GET'])
def llm_health():
    """Health check for the LLM engine.

    "backend" now names the engine that actually answers — "llama-server" for
    the supervised children, "llama-cpp-python" when LLM_ENGINE selects the
    in-process one — and the child engine adds the binary and its build string,
    because a wrong or missing llama.cpp build is the one deployment fault that
    makes every model on this service unavailable at once.
    """
    backend, refusal = _engine()
    if refusal is not None:
        return refusal
    payload = {"status": "ok" if backend.is_available() else "unavailable"}
    try:
        payload.update(backend.get_engine_info())
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[LLM] Could not describe the engine: {e}")
        payload.setdefault("backend", "unknown")
    return jsonify(payload)
