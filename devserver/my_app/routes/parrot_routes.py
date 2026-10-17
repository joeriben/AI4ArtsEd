"""
Silly Parrot routes — /api/parrot/*

    POST /api/parrot/recording        multipart wav  -> {recording_id}
    GET  /api/parrot/stream/<id>      SSE, one event per station
    GET  /api/parrot/sung/<id>        the generated audio, inline
    POST /api/parrot/discard/<id>     drop everything for this recording

The recording is never a work: it is staged outside the export store, read
by the stations, and the input file is deleted the moment the chain ends.
Nothing here creates a run, a media-store entry, a favourite or an export,
and /sung deliberately serves inline with no attachment disposition — the
piece is to be heard once, not collected. See services/parrot_service.py.
"""

import json
import logging
import os

from flask import Blueprint, Response, jsonify, request, send_file

logger = logging.getLogger(__name__)

parrot_bp = Blueprint('parrot', __name__, url_prefix='/api/parrot')

# A backstop against something that is not a recording, not a length rule — the
# length rule is MAX_RECORDING_SECONDS and it is checked below. The page pins
# its wav to 48 kHz, where four minutes is 23 MB; this leaves room for a client
# whose AudioContext would not take a rate and fell back to the device's, which
# on a 96 kHz interface makes the same four minutes 46 MB. Refusing THAT as
# "too long" would be a lie the recorder could not act on.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
DURATION_SLACK_SECONDS = 3


@parrot_bp.route('/recording', methods=['POST'])
def upload_recording():
    """Take a wav recorded in the browser. Returns an id, stores no work."""
    from my_app.services.parrot_service import (
        MAX_RECORDING_SECONDS, new_recording_dir, discard,
    )

    # Asked before the body is touched. request.files materialises the upload,
    # and with no duration cap in front of it there is nothing else between an
    # arbitrary POST and this machine's disk. Content-Length can be absent or
    # lie, so the measurement after the save stays as the backstop.
    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return jsonify({"success": False, "code": "too_long",
                        "error": "recording too large"}), 413

    if 'file' not in request.files:
        return jsonify({"success": False, "error": "no file in request"}), 400
    upload = request.files['file']
    if not upload.filename:
        return jsonify({"success": False, "error": "no file selected"}), 400

    recording_id, directory = new_recording_dir()
    path = os.path.join(directory, "recording.wav")
    upload.save(path)

    size = os.path.getsize(path)
    if size > MAX_UPLOAD_BYTES:
        discard(recording_id)
        return jsonify({"success": False, "code": "too_long",
                        "error": "recording too large"}), 413

    # Check the audio itself rather than trusting the client's timer.
    try:
        import soundfile as sf
        info = sf.info(path)
    except Exception as e:
        discard(recording_id)
        return jsonify({"success": False, "error": f"not a readable wav: {e}"}), 400

    # The client stops at the cap; this is for a client that did not.
    if info.duration > MAX_RECORDING_SECONDS + DURATION_SLACK_SECONDS:
        discard(recording_id)
        return jsonify({
            "success": False,
            "code": "too_long",
            "error": f"recording longer than {MAX_RECORDING_SECONDS}s",
        }), 400

    logger.info(f"[PARROT] staged {recording_id}: {info.duration:.1f}s, "
                f"{info.samplerate} Hz, {info.channels}ch, {size} bytes")
    return jsonify({
        "success": True,
        "recording_id": recording_id,
        "duration_seconds": round(info.duration, 2),
        "sample_rate": info.samplerate,
    })


@parrot_bp.route('/stream/<recording_id>', methods=['GET'])
def stream_chain(recording_id: str):
    """Run the four stations, one server-sent event each."""
    from my_app.services.parrot_service import recording_dir, run_chain

    directory = recording_dir(recording_id)
    if not directory or not os.path.isfile(os.path.join(directory, "recording.wav")):
        def missing():
            yield f"data: {json.dumps({'station': 'input', 'status': 'failed', 'error': 'recording not found'})}\n\n"
        return Response(missing(), mimetype='text/event-stream')

    language = request.args.get('language') or None
    # Which language the page is being read in. NOT `language` above — that one
    # forces the transcriber's decision; this one only asks for its output in a
    # readable form. See parrot_service.run_chain.
    reading = request.args.get('reading') or None
    # A hand-picked config for station 5. Validated in parrot_service against
    # the four it offers; anything else is not an error but simply not a pick,
    # and the chain routes itself. See resolve_singer.
    singer = request.args.get('config') or None
    recording_path = os.path.join(directory, "recording.wav")

    def generate():
        try:
            for event in run_chain(recording_path, language=language,
                                   reading=reading, singer=singer):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[PARROT] chain failed for {recording_id}: {e}", exc_info=True)
            yield f"data: {json.dumps({'station': 'chain', 'status': 'failed', 'error': str(e)})}\n\n"
        finally:
            # The input is gone the moment the stations are done with it,
            # whether the chain finished or not.
            try:
                os.remove(recording_path)
            except OSError:
                pass
            yield f"data: {json.dumps({'station': 'chain', 'status': 'complete'})}\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


@parrot_bp.route('/sung/<recording_id>', methods=['GET'])
def sung(recording_id: str):
    """Serve the generated audio inline. No attachment, no filename to save."""
    from my_app.services.parrot_service import recording_dir

    directory = recording_dir(recording_id)
    if not directory:
        return jsonify({"success": False, "error": "not found"}), 404
    # The extension is the station's, because the format is the chunk's: the
    # music models hand back mp3 and the speech chunk wav. Serving wav bytes as
    # audio/mpeg makes them silent in the browser.
    types = {"mp3": "audio/mpeg", "wav": "audio/wav",
             "flac": "audio/flac", "ogg": "audio/ogg"}
    path = None
    for ext, mime in types.items():
        candidate = os.path.join(directory, "sung." + ext)
        if os.path.isfile(candidate):
            path, mimetype = candidate, mime
            break
    if path is None:
        return jsonify({"success": False, "error": "nothing sung yet"}), 404

    response = send_file(path, mimetype=mimetype, as_attachment=False,
                         conditional=True)
    response.headers['Cache-Control'] = 'no-store'
    return response


@parrot_bp.route('/discard/<recording_id>', methods=['POST'])
def discard_recording(recording_id: str):
    """Drop the recording and anything made from it."""
    from my_app.services.parrot_service import discard
    discard(recording_id)
    return jsonify({"success": True})
