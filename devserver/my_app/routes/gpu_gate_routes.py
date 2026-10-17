"""
The gate on HTTP: the lease for a holder that is not this process, and the
gate's reading for whoever wants to look at the card.

Every holder inside this process leases the gate by a call
(services/gpu_lease_client.py); these routes exist for the ones outside it —
the GPU service, which leases here for every hold of its own until stage 8
takes it down; a research script; an operator's curl — and for the readings
the settings page and the workshop companion show.

  POST /api/gate/lease/acquire     {kind, model_id, required_mb, label, workload, timeout_s} -> {token} | 503
  POST /api/gate/lease/heartbeat   {token} -> {ok}
  POST /api/gate/lease/release     {token, failed} -> {ok}
  GET  /api/gate/status            -> the gate's state
  GET  /api/gate/plan              -> the queue in the order it will run, with expected waits
  GET  /api/gate/stats             -> measured slot times and footprints
  GET  /api/gate/prefetch-advice   -> which model could be warmed beside the running one
  POST /api/gate/prefetch-claim    {model_id} -> {claimed}
  POST /api/gate/prefetch-done     {model_id} -> {ok}
  GET  /api/gate/vram              -> the card: memory, processes, ComfyUI's resident models

Until stage 7 of the move to ComfyUI these stood on the GPU service under
/api/gpu/... and /api/health/vram; the gate moved into this process with
them (services/gpu_gate.py).

The old host listened on 127.0.0.1 only; this one is reachable through the
tunnel. The routes that take, keep or give back the slot therefore pass the
settings guard: a request from this machine goes through as before, a
request through the tunnel needs the settings session, and a request from
another machine on the network is refused by its address. The readings stay
open — they name the leases and carry no token.
"""

import logging

from flask import Blueprint, jsonify, request

from my_app.routes.settings_routes import require_settings_auth
from my_app.services.gpu_gate import GpuBusy, get_gpu_gate

logger = logging.getLogger(__name__)

gpu_gate_bp = Blueprint("gpu_gate", __name__, url_prefix="/api/gate")


def _busy(e: GpuBusy):
    """The refusal, with its token: which of the four refusals it was travels
    beside the sentence, so a surface chooses what to say from the state and
    never from prose matching."""
    return jsonify({
        "error": str(e), "code": "gpu_busy", "detail": str(e),
        "busy_reason": e.reason, "holder_kind": e.holder_kind, "waiting": e.waiting,
        "free_mb": e.free_mb, "required_mb": e.required_mb,
    }), 503


@gpu_gate_bp.route("/lease/acquire", methods=["POST"])
@require_settings_auth
def acquire_lease():
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "the body must be a JSON object"}), 400
    kind = str(data.get("kind") or "comfyui")
    model_id = str(data.get("model_id") or "comfyui")
    try:
        required_mb = float(data.get("required_mb") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "required_mb must be a number"}), 400
    label = str(data.get("label") or "")
    # The output config, where the caller knows one — see Lease.stats_key.
    workload = str(data.get("workload") or "")
    # The process behind the lease, so its line on the settings page reads
    # "in use" while it holds — see Lease.holder.
    holder = str(data.get("holder") or "")
    # A caller that would rather hear "busy" than queue for the full budget.
    raw_timeout = data.get("timeout_s")
    try:
        timeout_s = float(raw_timeout) if raw_timeout is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "timeout_s must be a number"}), 400
    try:
        token = get_gpu_gate().acquire(kind, model_id, required_mb, label=label,
                                       workload=workload, timeout_s=timeout_s,
                                       holder=holder)
        return jsonify({"token": token}), 200
    except GpuBusy as e:
        logger.warning("[GATE] Lease denied (busy): %s", e)
        return _busy(e)
    except Exception as e:
        logger.error("[GATE] acquire error: %s", e)
        return jsonify({"error": f"the lease could not be taken: {e}"}), 500


@gpu_gate_bp.route("/lease/heartbeat", methods=["POST"])
@require_settings_auth
def heartbeat_lease():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token") if isinstance(data, dict) else None
    ok = bool(token) and get_gpu_gate().heartbeat(str(token))
    return jsonify({"ok": ok}), (200 if ok else 404)


@gpu_gate_bp.route("/lease/release", methods=["POST"])
@require_settings_auth
def release_lease():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token") if isinstance(data, dict) else None
    # The owner says whether the run completed. An abort in the queue or a
    # broken render must not enter the duration statistics as a valid hold.
    failed = bool(data.get("failed")) if isinstance(data, dict) else False
    gate = get_gpu_gate()
    ok = bool(token) and gate.release(str(token), failed=failed)
    # The holder's own coordinator asked ComfyUI to free everything during
    # the hold (the GPU service's, until stage 8): what this gate believed
    # resident went with it.
    if ok and isinstance(data, dict) and data.get("cleared_comfyui"):
        gate.forget_resident("the holder asked ComfyUI to free everything during its hold")
    return jsonify({"ok": ok}), 200


@gpu_gate_bp.route("/status", methods=["GET"])
def gate_status():
    return jsonify(get_gpu_gate().get_status()), 200


@gpu_gate_bp.route("/plan", methods=["GET"])
def gate_plan():
    """The queue in the order it will actually run, with expected waits.

    Covers what has reached the gate. Runs still in translation, Prompt
    Interception or the safety check are not here — the pipeline routes see
    those and fold them in.
    """
    return jsonify(get_gpu_gate().plan()), 200


@gpu_gate_bp.route("/stats", methods=["GET"])
def gate_stats():
    """What has actually been paid so far: slot time and VRAM.

    Slot time is keyed by output config where one was named and by model
    otherwise (`keyed_by` on each entry says which); VRAM is always keyed by
    model. Both keys are in the entry, so a reader is never left guessing what
    a number is about.
    """
    from my_app.services.gpu_model_stats import SPREAD_LIMIT, TRUSTED_SAMPLES, get_model_stats
    return jsonify({
        "models": get_model_stats().snapshot(),
        "trusted_samples": TRUSTED_SAMPLES,
        "spread_limit": SPREAD_LIMIT,
    }), 200


@gpu_gate_bp.route("/prefetch-advice", methods=["GET"])
def gate_prefetch_advice():
    """Which model could be warmed right now beside the running one, if any."""
    return jsonify(get_gpu_gate().prefetch_advice()), 200


@gpu_gate_bp.route("/prefetch-claim", methods=["POST"])
@require_settings_auth
def gate_prefetch_claim():
    data = request.get_json(force=True, silent=True) or {}
    model_id = str(data.get("model_id") or "") if isinstance(data, dict) else ""
    if not model_id:
        return jsonify({"claimed": False, "error": "model_id required"}), 400
    return jsonify({"claimed": get_gpu_gate().prefetch_claim(model_id)}), 200


@gpu_gate_bp.route("/prefetch-done", methods=["POST"])
@require_settings_auth
def gate_prefetch_done():
    data = request.get_json(force=True, silent=True) or {}
    model_id = str(data.get("model_id") or "") if isinstance(data, dict) else ""
    get_gpu_gate().prefetch_done(model_id)
    return jsonify({"ok": True}), 200


@gpu_gate_bp.route("/vram", methods=["GET"])
def gate_vram():
    """The card: memory and processes from the driver, the resident models
    from ComfyUI, the gate's state beside them."""
    try:
        return jsonify(get_gpu_gate().vram_status()), 200
    except Exception as e:
        logger.error("[GATE] vram status error: %s", e)
        return jsonify({"error": f"the card could not be read: {e}"}), 500
