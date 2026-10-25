"""
Wikimedia Commons routes — the found-images row under the model grid.

Two endpoints:

  POST /api/commons/lookup        prompt -> search term + up to three files
  GET  /api/commons/image/<ref>   one thumbnail, served from OUR origin

The second one is not a convenience. Embedding upload.wikimedia.org in the page
would make every participant's browser connect to Wikimedia on page load; here
the DevServer fetches and re-serves, so nothing leaves the origin. The reference is a
packed URL that is validated against a host allowlist before anything is
fetched — the route is not an open proxy.

Serving from our origin also means the answer is ours. The service returns only
raster types (never image/svg+xml, which is a scriptable document), and this
route adds a CSP that keeps the response from doing anything at all if a type
ever slips through.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from flask import Blueprint, Response, jsonify, request

from my_app.services import commons_service
from my_app.services.streaming_response import answered_either_way, object_body

logger = logging.getLogger(__name__)

commons_bp = Blueprint("commons", __name__, url_prefix="/api/commons")


@commons_bp.route("/lookup", methods=["POST"])
def lookup():
    """Reduce the prompt to a search term and look Commons up.

    Answers 200 in all four outcomes — ``ok``, ``no_motif``, ``nothing_found``
    and ``error``. The first three are results and the frontend renders each
    differently; ``error`` says the archive or the model could not be reached and
    is deliberately NOT folded into the other two, so an outage is never shown as
    a finding about the participant's prompt.

    Commons is not age-filtered, so the effective safety level of this session
    goes down with the request: at kids and youth every picture is checked before
    it is shown.

    With "enable_streaming" the answer travels as this platform's SSE stream
    instead of as one JSON body, and of everything on this server this is the
    route that needed it most. At those two levels the lookup works through up
    to ``MAX_CHECK_CANDIDATES`` pictures and each of them costs two model calls,
    on top of the one that turns the prompt into a search term: up to nineteen
    model calls inside a single POST that says nothing, each queueing for the
    plant-wide GPU slot. The edge in front of this server ends a request whose
    origin has been silent for about 100 seconds, so the row was regularly
    looked up, checked, and thrown away.
    """
    # A body that is not a JSON OBJECT is a caller's mistake and is named as
    # one. `"hello"` reached `.get()` below and came back as Flask's own HTML
    # 500 page: a fault of this server, where a caller's mistake stands.
    data, refusal = object_body(silent=True, envelope={"success": False})
    if refusal:
        payload, http_status = refusal
        return jsonify(payload), http_status

    # Resolved HERE, at the request boundary, and handed in. The resolver only
    # sees the course from inside a request and returns the STRICTEST level to
    # anyone who calls it from a worker thread — that is deliberate, and the way
    # to honour it is to pass the level down, not to look it up further in
    # (services/safety_level_resolver.py, module docstring). Under the stream
    # the lookup RUNS on such a worker, so a resolve that had stayed below this
    # line would hand every room `kids` — which is not the level its course
    # asked for, and the row would be checked against the wrong one silently.
    from my_app.services.safety_level_resolver import resolve_safety_level
    try:
        safety_level = resolve_safety_level()
    except Exception as exc:  # noqa: BLE001 - guarded the way the sibling is
        # The resolver documents that it never raises. Unguarded, an exception
        # here left the view entirely and Flask put its own HTML page on the
        # wire: no status a caller can act on, no field it can read, and nothing
        # naming what failed. It stands IN FRONT of the two refusals inside the
        # run, so `prompt required` and `prompt too long` arrived as that page
        # too, in place of 400 and 413.
        #
        # What every body gets instead is this 500, with the cause in it. The
        # two refusals stay behind it and that is right: whether the pictures in
        # this row are looked at at all hangs on the level, and a level that
        # cannot be read is an error rather than a pass.
        # mean_images_routes.py guards the identical call the same way.
        logger.error(f"[COMMONS] Safety level could not be resolved: {exc}",
                     exc_info=True)
        return jsonify({
            "success": False,
            "error": "The pictures of this row could not be checked: the "
                     f"safety level could not be resolved ({exc})",
        }), 500

    # The run DECLARES `client_gone`, so `streamed_answer` hands it the event —
    # and of the routes on this transport this is the one that may take it. What
    # it makes is a row for ONE page: nothing is saved, so a row whose reader has
    # gone is pure loss on a card other people are waiting for. A generation
    # saves its image and therefore declines the signal; the same decision, read
    # off what the work leaves behind.
    #
    # What is kept here is the CANDIDATE LIST alone (commons_service._search_cache,
    # keyed on the search term, beside _term_cache for the term itself). The
    # per-picture checks are cached nowhere, so a reader who left after two
    # frames still paid for every one of MAX_CHECK_CANDIDATES candidates — two
    # model calls and one download of up to MAX_IMAGE_BYTES each, every model
    # call queueing for the plant-wide GPU slot.
    #
    # Narrow on purpose: whether a run should end when its reader leaves is an
    # open question on this platform, and stopping here answers nothing about
    # work that saves what it makes.
    return answered_either_way(data, _run_lookup, data, safety_level,
                               label='COMMONS-LOOKUP')


def _run_lookup(data: dict, safety_level: str,
                client_gone: Optional[threading.Event] = None):
    """The lookup, and the ``(payload, http_status)`` it answers with.

    Split out of the route so that one lookup can be answered either way — the
    refusals below included, so that a caller which asked for the stream is
    answered on the stream whatever the answer is. Left at the boundary they
    would arrive as one plain JSON body where the frames were asked for, which
    services/directRun.ts reads as a half-finished deploy and says so on the
    console.

    It must not reach for ``request``: everything it needs stands in ``data``,
    and the safety level is resolved at the request boundary and passed in —
    resolved here it would be the strictest level for everyone, which is a
    different judgement from the one the visitor's course asked for.

    ``client_gone`` is the leaving signal, set when the stream ends and ``None``
    on the plain path, where there is no stream to end. It is looked at between
    candidates, never inside one check — see the route above for why this row
    may stop where a generation may not.
    """
    raw = data.get("prompt")
    # A `prompt` that is not text is a caller's mistake and is named as one,
    # exactly as a body that is no JSON object is named above. `str(raw)` is the
    # platform's other coercion (media_routes._run_analyze_image) and it is the
    # wrong one HERE: this route is unauthenticated and every unique prompt
    # costs a model call, so `str([1, 2])` would send a Python repr nobody wrote
    # to a model and key the archive cache on it. Unnamed, `123` reached
    # `.strip()`: Flask's HTML 500 on the plain path, and on the stream a 200
    # carrying "'int' object has no attribute 'strip'" with a traceback in the
    # log — a Python fault of this server put there by any caller at all.
    if raw is not None and not isinstance(raw, str):
        return {"success": False, "error": "prompt must be a string"}, 400
    prompt = (raw or "").strip()
    if not prompt:
        return {"success": False, "error": "prompt required"}, 400
    if len(prompt) > commons_service.MAX_PROMPT_CHARS:
        return {"success": False, "error": "prompt too long"}, 413

    limit = data.get("limit", commons_service.MAX_IMAGES)
    try:
        limit = max(1, min(int(limit), commons_service.MAX_IMAGES))
    except (TypeError, ValueError, OverflowError):
        # OverflowError belongs here for the same reason the two beside it do:
        # Python's JSON reader accepts `Infinity` and `NaN`, and `int(inf)`
        # raises neither of the others — so `{"limit": Infinity}` came back as
        # "cannot convert float infinity to integer" where the default stands.
        limit = commons_service.MAX_IMAGES

    try:
        result = commons_service.lookup_for_prompt(prompt, limit=limit,
                                                   safety_level=safety_level,
                                                   client_gone=client_gone)
    except Exception as exc:  # noqa: BLE001 - the row degrades, the page does not
        logger.error(f"[COMMONS] Lookup failed: {exc}", exc_info=True)
        return {"success": True, "state": "error", "term": None, "images": []}, 200

    result["success"] = True
    return result, 200


@commons_bp.route("/image/<path:ref>", methods=["GET"])
def image(ref: str):
    """Serve one Commons thumbnail from our own origin.

    ``ref`` is the packed URL from the lookup answer. Anything that does not
    decode to an https URL on an allowed Wikimedia host is refused before a
    request is made.
    """
    url = commons_service.decode_image_ref(ref)
    if not url:
        return jsonify({"success": False, "error": "invalid image reference"}), 400

    fetched = commons_service.fetch_image_bytes(url)
    if not fetched:
        return jsonify({"success": False, "error": "image unavailable"}), 502

    payload, content_type = fetched
    response = Response(payload, mimetype=content_type)
    # Belt and braces around the type allowlist in the service: even if some
    # scriptable type ever reached here, this response may load nothing and run
    # nothing. `sandbox` alone (no allow-* token) also denies same-origin.
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    # A Commons thumbnail URL carries the file revision, so what is behind it
    # never changes. X-Immutable-Asset is the app's own marker for exactly that
    # (my_app/__init__.py, add_cache_headers) and keeps the development no-store
    # rule from re-fetching three pictures on every render.
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["X-Immutable-Asset"] = "1"
    return response
