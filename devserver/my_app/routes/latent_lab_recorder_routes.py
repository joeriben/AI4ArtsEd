"""
Flask routes for Latent Lab recording + capability discovery.

Recording endpoints:
  POST /api/latent-lab/record/start  — open a sitting (one per instrument tab)
  POST /api/latent-lab/record/save   — write ONE run, return its run_id
  POST /api/latent-lab/record/end    — close the sitting

Reading endpoints:
  GET  /api/latent-lab/run/<run_id>            — the run as an instrument object
  GET  /api/latent-lab/run/<run_id>/part/<i>   — one part of that run
  GET  /api/latent-lab/session/<id>/runs       — every run of one sitting

Setting the plate a run is shown by:
  POST /api/latent-lab/run/<run_id>/output/<i> — for an instrument whose picture
                                                 is a READING of its run

Capability endpoint:
  GET  /api/latent-lab/capabilities  — which VRAM-heavy tools are usable here

A sitting is not an address. What the platform stores, favourites and restores
is a RUN, and `record/save` returns the id of the one it just wrote — that is
what a surface puts on its run card.
"""

import asyncio
import logging
import re
from flask import Blueprint, jsonify, request, send_file

from config import JSON_STORAGE_DIR
from my_app.services.latent_lab_recorder import (
    MAX_PLATE_BASE64,
    build_instrument_object,
    create_lab_recorder,
    cleanup_lab_recorder,
    get_lab_recorder,
    list_session_runs,
    replace_output_image,
    resolve_part_path,
)
from my_app.services.latent_lab_capabilities import get_latent_lab_capabilities
from my_app.services.latent_lab_model import get_latent_lab_model_id

logger = logging.getLogger(__name__)

# An id that reaches the filesystem is checked before it gets there: the device
# folder is named by what the browser sends.
_PLAIN_ID = re.compile(r'[A-Za-z0-9._:-]{1,128}')

latent_lab_recorder_bp = Blueprint('latent_lab_recorder', __name__)


@latent_lab_recorder_bp.route('/api/latent-lab/capabilities', methods=['GET'])
def latent_lab_capabilities():
    """Return which VRAM-heavy Latent-Lab tools are available on this GPU.

    Response JSON shape:
      {
        "attention_cartography": bool,
        "feature_probing": bool,
        "total_vram_gb": float | null,
        "threshold_gb": float,
        "forced": bool,
        "latent_lab_model": str
      }

    `latent_lab_model` is the backbone the raster instruments resolve to on this
    card (services/latent_lab_model.py). It is answered here because it is the
    same reading — the card's VRAM — and because the bar names it before a run
    has happened: under 50 GB these instruments run SD 3.5 Medium while their
    output configs are written for Large, and until now no surface said so.
    """
    async def _caps_with_model() -> dict:
        # Together, not one after the other. Both ask the GPU service the same
        # question and both memoize separately, so a warm capabilities memo does
        # not spare the second read — and each carries a ten-second timeout. In
        # series a hung GPU service held this page load for twenty.
        caps, model = await asyncio.gather(
            get_latent_lab_capabilities(),
            get_latent_lab_model_id(),
        )
        # A copy: the resolver memoizes and hands back the same dict every time.
        return {**caps, 'latent_lab_model': model}

    try:
        caps = asyncio.run(_caps_with_model())
        return jsonify(caps)
    except Exception as e:
        logger.error(f"[LAB_CAPS] Failed to resolve capabilities: {e}")
        return jsonify({"error": str(e)}), 500


@latent_lab_recorder_bp.route('/api/latent-lab/record/start', methods=['POST'])
def start_recording():
    """
    Open a Latent Lab sitting.

    Request JSON:
        latent_lab_tool: str  — tool identifier (e.g. "denoising_archaeology")
        device_id: str?       — browser device ID
    Response JSON:
        session_id: str
    """
    data = request.get_json(silent=True) or {}
    tool = data.get('latent_lab_tool')
    if not tool:
        return jsonify({"error": "latent_lab_tool is required"}), 400

    device_id = data.get('device_id')
    recorder = create_lab_recorder(latent_lab_tool=tool, device_id=device_id)

    logger.info(f"[LAB_RECORD] Opened session {recorder.session_id} for {tool}")
    # `run_id` is the same handle under the name this endpoint used before a
    # sitting and a run became two things. A browser tab that was open across a
    # deploy still reads that key, and without it that tab would go on running
    # and record NOTHING, silently, for the rest of its life.
    return jsonify({"session_id": recorder.session_id, "run_id": recorder.session_id})


@latent_lab_recorder_bp.route('/api/latent-lab/record/save', methods=['POST'])
def save_recording():
    """
    Write one generation as a run of its own.

    Request JSON:
        session_id: str
        parameters: dict      — generation parameters
        results: dict?        — result metadata (seed, timing)
        outputs: [{type, format, dataBase64 | ref, meta?}]?  — final media.
                  `ref` is a media address (/api/media/<kind>/<run_id>/<index>)
                  for bytes this storage already holds; it is read from there
                  instead of being uploaded again.
        steps: [{format, dataBase64, meta?}]?          — the ordered parts
    Response JSON:
        run_id: str           — what the surface puts on its run card
        entity_count: int
    """
    data = request.get_json(silent=True) or {}
    # `run_id`: what an older bundle calls the sitting. See start_recording.
    session_id = data.get('session_id') or data.get('run_id')
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    recorder = get_lab_recorder(session_id)
    if not recorder:
        return jsonify({"error": f"No open session: {session_id}"}), 404

    written = recorder.record(
        parameters=data.get('parameters', {}),
        results=data.get('results'),
        outputs=data.get('outputs'),
        steps=data.get('steps'),
    )

    return jsonify({
        "status": "saved",
        "run_id": written["run_id"],
        "entity_count": written["entity_count"],
    })


@latent_lab_recorder_bp.route('/api/latent-lab/record/end', methods=['POST'])
def end_recording():
    """
    Close a sitting.

    Request JSON:
        session_id: str
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id') or data.get('run_id')
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    recorder = get_lab_recorder(session_id)
    if not recorder:
        # Already closed or never opened — not an error
        return jsonify({"status": "already_ended"})

    recorder.complete()
    cleanup_lab_recorder(session_id)

    logger.info(f"[LAB_RECORD] Closed session {session_id}")
    return jsonify({"status": "completed"})


@latent_lab_recorder_bp.route('/api/latent-lab/session/<session_id>/runs', methods=['GET'])
def get_session_runs(session_id: str):
    """
    The runs of one sitting, in the order they were made.

    What it is for: a surface keeps its runs in the browser, so a reload emptied
    it while every run lay complete on disk. With this the surface can ask for
    its own sitting back.

    Query:
        device_id: str  — REQUIRED; the sitting is read out of this device's own
            folders. Without it the scan covered every device that used the
            machine that day, and one shared run id would have opened the whole
            sitting behind it — including runs nobody shared. The browser sends
            it on every call.
    Response JSON:
        session_id: str
        runs: [instrument object]  — the same shape a single run comes back in
    """
    if not _PLAIN_ID.fullmatch(session_id):
        return jsonify({"error": "invalid session_id"}), 400

    device_id = request.args.get('device_id') or ''
    if not _PLAIN_ID.fullmatch(device_id):
        return jsonify({"error": "device_id is required"}), 400

    try:
        runs = list_session_runs(session_id, device_id=device_id, base_path=JSON_STORAGE_DIR)
    except Exception as e:
        # The wording goes to the log, where the paths belong. What comes back
        # names the kind of failure without handing out the shape of the disk.
        logger.error(f"[LAB_RECORD] Failed to list session {session_id}: {e}", exc_info=True)
        return jsonify({
            "error": "session runs could not be read",
            "reason": type(e).__name__,
        }), 500

    return jsonify({"session_id": session_id, "runs": runs})


@latent_lab_recorder_bp.route('/api/latent-lab/run/<run_id>', methods=['GET'])
def get_run(run_id: str):
    """One run as an instrument object: tool, parameters, results, parts, outputs.

    404 for anything that is not a Latent Lab run — a pipeline run has its own
    shape and its own routes, and answering with a half-filled object here would
    hand a surface something it cannot take back.
    """
    obj = build_instrument_object(run_id)
    if not obj:
        return jsonify({"error": f"No latent lab run: {run_id}"}), 404
    return jsonify(obj)


@latent_lab_recorder_bp.route('/api/latent-lab/run/<run_id>/part/<int:index>', methods=['GET'])
def get_run_part(run_id: str, index: int):
    """One part of a run — a denoising step, an axis cell, a probe frame."""
    path = resolve_part_path(run_id, index)
    if not path:
        return jsonify({"error": f"No part {index} in run {run_id}"}), 404

    mimetypes = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.json': 'application/json',
        '.txt': 'text/plain',
        '.wav': 'audio/wav',
    }
    response = send_file(
        path,
        mimetype=mimetypes.get(path.suffix.lower(), 'application/octet-stream'),
        as_attachment=False,
    )
    # No download name from here: the surface that offers a part for download
    # names the file (the Denoising Archaeology's step frames carry their step
    # and seed in the name), and a Content-Disposition, which send_file sets
    # from the file's own name, would win over that name in the browser.
    response.headers.pop('Content-Disposition', None)
    # A part is written once and set again never (only an OUTPUT can be
    # replaced, see set_run_output), so the browser may keep it. The Denoising
    # Archaeology moves along the step frames of a run (25 by default), and
    # since 2026-09-22 a fresh run's frames come from here as well. The marker
    # exempts the answer from the app-wide no-store policy (my_app/__init__.py),
    # as the miniatures are.
    response.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
    response.headers['X-Immutable-Asset'] = '1'
    return response


#: What each refusal from replace_output_image means to a client. A single
#: status for all of them would tell a surface that a deleted run and a payload
#: its own build produced wrongly are the same thing.
_PLATE_STATUS = {
    "no_picture": 400,      # nothing sent, or what was sent is no base64 picture
    "no_reading": 400,
    "too_large": 413,
    "no_run": 404,
    "not_a_lab_run": 400,   # the id names something that lays no plates at all
    "no_such_output": 404,
    "not_a_reading": 409,   # the picture there is the model's own, not a plate
    "other_device": 403,
    "write_failed": 500,
    "record_write_failed": 500,   # the picture was set and put back again
}


@latent_lab_recorder_bp.route('/api/latent-lab/run/<run_id>/output/<int:index>', methods=['POST'])
def set_run_output(run_id: str, index: int):
    """Set the picture a run is SHOWN by, where that picture is a READING.

    Attention Cartography puts a map over its render, and which map that is
    depends on the words, the depth and the step the surface stands at. What
    belongs in the strip and in the favourites is the map as it was read, so the
    surface writes it here — when the run is made, and again when the run is
    kept. The render itself stays in the run as a further output and is refused
    here; so is every run that is not this device's own Latent Lab run.

    Request JSON:
        dataBase64: str  — the picture, base64, in the format the output has
        device_id: str   — the device that made the run; REQUIRED
        reading: dict?   — what the plate says: words, encoders, depth, step,
                           strength, ground. Written onto the picture's own
                           entry, because a map with no record of its reading
                           cannot be interpreted later.
    Response JSON:
        version: int     — the file's modification time in MICROSECONDS. A
                           picture is answered as immutable, so a URL has to
                           change when the bytes do; this is what it carries.
        Every refusal is a refusal: the surface has to say the reading was not
        kept rather than keep the run under a picture that shows another one.
    """
    if not _PLAIN_ID.fullmatch(run_id):
        return jsonify({"error": "invalid run_id"}), 400

    # What the body may weigh is decided BEFORE it is read. The size gate in the
    # service sees the payload only after the whole request has been parsed into
    # memory, which is one thread per request on a threaded server.
    declared = request.content_length
    if declared is not None and declared > MAX_PLATE_BASE64 + 4096:
        return jsonify({"error": "the plate was not set", "reason": "too_large"}), 413

    data = request.get_json(silent=True) or {}
    device_id = data.get('device_id') or ''
    if not isinstance(device_id, str) or not _PLAIN_ID.fullmatch(device_id):
        return jsonify({"error": "device_id is required", "reason": "no_device"}), 400

    reading = data.get('reading')
    if reading is not None and not isinstance(reading, dict):
        return jsonify({"error": "reading must be an object", "reason": "no_reading"}), 400

    result = replace_output_image(
        run_id,
        index,
        data.get('dataBase64'),
        device_id=device_id,
        reading=reading,
        base_path=JSON_STORAGE_DIR,
    )
    if not result.get("ok"):
        reason = str(result.get("reason") or "write_failed")
        # The wording of what went wrong travels with the status; the paths stay
        # in the log, where they belong.
        logger.info(f"[LAB_RECORD] Plate of {run_id}/{index} not set: {reason}")
        return jsonify({
            "error": "the plate was not set",
            "reason": reason,
            "run_id": run_id,
            "index": index,
        }), _PLATE_STATUS.get(reason, 500)

    return jsonify({"version": result.get("version")})
