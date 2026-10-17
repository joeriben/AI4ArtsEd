"""
Flask routes for Resona's Werkstatt-Journal API (Phase R1/J1).

Journal lifecycle (ensure/read/new/delete) + J2 media provenance. Delete
("new dialog") removes the journal's .jsonl+.meta.json AND clears the
Memory-Digest of the devices that wrote it; media run folders stay
(PLAN_DATENHALTUNG §5 / E5); export + retention-sweep + journal-code remain J4/R6.
Orchestrator and pipeline executor are untouched; this blueprint is pure
Resona-domain bookkeeping on top of my_app.services.resona_journal.
"""

import logging

from flask import Blueprint, jsonify, request

from my_app.services import resona_journal, resona_memory, resona_question_filter

logger = logging.getLogger(__name__)

resona_bp = Blueprint('resona', __name__, url_prefix='/api/resona')


@resona_bp.route('/journal/ensure', methods=['POST'])
def journal_ensure():
    """
    Ensure a journal exists for this device_id, creating it if needed.

    POST /api/resona/journal/ensure
    Body: {"device_id": "..."}

    Response: {"journal_id", "created", "event_count", "read_only"}
    """
    try:
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id')
        if not device_id or not isinstance(device_id, str):
            return jsonify({"error": "device_id is required"}), 400

        meta = resona_journal.ensure(device_id)
        if meta is None:
            return jsonify({"error": "invalid device_id"}), 400

        return jsonify({
            "journal_id": meta["journal_id"],
            "created": meta["created"],
            "event_count": meta["event_count"],
            "read_only": meta["read_only"],
        })
    except Exception as e:
        logger.error(f"[RESONA-ROUTES] journal_ensure error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@resona_bp.route('/journal/<journal_id>', methods=['GET'])
def journal_get(journal_id: str):
    """
    Get paginated events for a journal (restore + teacher view).

    GET /api/resona/journal/<journal_id>?offset=&limit=

    Response: {"events": [...], "meta": {...}}
    404 if the journal does not exist (journal_id is sanitized server-side
    before lookup — an unsanitizable/foreign id is treated as not found).
    """
    try:
        offset = request.args.get('offset', default=0, type=int) or 0
        limit = request.args.get('limit', default=resona_journal.READ_LIMIT_DEFAULT, type=int)
        if limit is None:
            limit = resona_journal.READ_LIMIT_DEFAULT

        result = resona_journal.read_events(journal_id, offset=offset, limit=limit)
        if result is None:
            return jsonify({"error": "journal not found"}), 404

        return jsonify(result)
    except Exception as e:
        logger.error(f"[RESONA-ROUTES] journal_get error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@resona_bp.route('/journal/<journal_id>/media', methods=['POST'])
def journal_media_result(journal_id: str):
    """
    Report a finished/failed generation back into the journal (J2).

    POST /api/resona/journal/<journal_id>/media
    Body: {"intent_id", "status", "run_id"?, "media_type"?, "media_url"?,
           "seed"?, "device_id"?}

    status: completed | blocked | error | cancelled. For blocked results only
    this generic status is recorded — never safety term details (kids journal,
    PLAN_DATENHALTUNG E8).
    """
    try:
        data = request.get_json(silent=True) or {}
        intent_id = data.get('intent_id')
        status = data.get('status')
        if not intent_id or not isinstance(intent_id, str):
            return jsonify({"error": "intent_id is required"}), 400
        if not isinstance(status, str) or status.strip().lower() not in resona_journal.VALID_MEDIA_RESULT_STATUS:
            return jsonify({"error": "status must be one of: " + ", ".join(resona_journal.VALID_MEDIA_RESULT_STATUS)}), 400
        if not resona_journal.journal_exists(journal_id):
            return jsonify({"error": "journal not found"}), 404

        seq = resona_journal.append_event(
            journal_id,
            "media_result",
            {
                "intent_id": intent_id,
                "run_id": data.get('run_id'),
                "status": status,
                "media_type": data.get('media_type'),
                "media_url": data.get('media_url'),
                "seed": data.get('seed'),
            },
            device_id=data.get('device_id'),
        )
        if seq is None:
            return jsonify({"error": "event rejected (journal read-only or payload invalid)"}), 409
        return jsonify({"seq": seq})
    except Exception as e:
        logger.error(f"[RESONA-ROUTES] journal_media_result error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500



@resona_bp.route('/journal/new', methods=['POST'])
def journal_new():
    """
    Mint a FRESH empty journal for this device ("Neues Gespraech"), keeping any
    existing journal on disk. POST /api/resona/journal/new  Body: {"device_id"}
    Response: {"journal_id", "created", "event_count", "read_only"}
    """
    try:
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id')
        if not device_id or not isinstance(device_id, str):
            return jsonify({"error": "device_id is required"}), 400
        meta = resona_journal.new_journal(device_id)
        if meta is None:
            return jsonify({"error": "invalid device_id"}), 400
        return jsonify({
            "journal_id": meta["journal_id"],
            "created": meta["created"],
            "event_count": meta["event_count"],
            "read_only": meta["read_only"],
        })
    except Exception as e:
        logger.error(f"[RESONA-ROUTES] journal_new error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@resona_bp.route('/journal/<journal_id>', methods=['DELETE'])
def journal_delete(journal_id: str):
    """
    "New dialog": delete this journal's .jsonl + .meta.json AND drop the
    Memory-Digest records made in it, so Resona starts with an empty head
    instead of re-reading her old working notes into every following turn
    (chat_routes._build_resona_memory_digest).

    DELETE /api/resona/journal/<journal_id>
    404 if the journal is unknown. Media run folders are NOT touched
    (PLAN_DATENHALTUNG §5 / E5 — kept favorites reference run_ids).

    Order matters: the memory goes first, the journal only if that succeeded.
    Both halves are irreversible, and of the two, a journal deleted while its
    memory quietly stayed is the failure this endpoint exists to prevent — the
    group would be told the dialog was dropped and then meet it again in
    Resona's next sentence, with no journal left to explain where it came from.
    """
    try:
        if not resona_journal.journal_exists(journal_id):
            return jsonify({"error": "journal not found"}), 404

        # Every device that wrote here may hold records of this journal (a
        # journal carried across days collects one device_id per day).
        owner = resona_journal.owning_device(journal_id)
        devices = list(resona_journal.device_ids(journal_id))
        if owner and owner not in devices:
            devices.append(owner)

        # Records from before records carried a journal at all are claimable
        # only when nothing else could claim them: the journal's OWN device
        # (derived from the id, never from the client-fed meta list) and no
        # sibling conversation on that device. Checked while this journal's
        # meta still exists.
        unstamped_owner = owner if (owner and not resona_journal.has_other_generations(journal_id)) else None

        forgotten = 0
        for device_id in devices:
            forgotten += resona_memory.forget_journal(
                device_id, journal_id, include_unstamped=(device_id == unstamped_owner)
            )

        # The count of sentences cut from the last reply belongs to that reply.
        try:
            for device_id in devices:
                resona_question_filter.clear_notice(device_id)
        except Exception:
            logger.warning("[RESONA-ROUTES] clearing the cut-sentence notice failed", exc_info=True)

        # UCD-132: the journal's session document space (scene capsules of
        # documents the group brought in) verfällt MIT der Sitzung — drop it
        # with the journal, best-effort (a missing space is not an error).
        try:
            from my_app.services import scene_document_space as _space
            _space.delete_journal_space(journal_id)
        except Exception:
            logger.warning("[RESONA-ROUTES] scene document space cleanup failed", exc_info=True)

        removed = resona_journal.delete(journal_id)
        if not removed:
            # The journal was there a moment ago and its memory is already
            # gone, so this is a failed unlink, not an unknown id. Saying 404
            # here would tell the group nothing happened while their notes went.
            logger.error(f"[RESONA-ROUTES] memory purged but journal files survived: {journal_id}")
            return jsonify({"error": "journal files could not be removed"}), 500
        return jsonify({
            "deleted": True,
            "journal_id": journal_id,
            "memories_forgotten": forgotten,
        })
    except Exception as e:
        logger.error(f"[RESONA-ROUTES] journal_delete error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500
