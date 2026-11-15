"""Zusammenfassungen im Flow — HTTP-Routen (from UCD-132).

/api/scene/* — the BACKEND surface of UCD-132 (no "+"-Integration; that is
UCD-133's own scope). The upload route runs the file check (UCD-131) and
takes the document's name in at the platform's intake, synchronously, BEFORE
storage/enqueue — rejected files cost nothing. Then it stages the PDF into a
job temp dir and enqueues the summary job (scene_ingest_service: the intake of
the document's text, the library's condensation, then the check at the
result), with the safety level resolved here.

Session scoping: the caller supplies the journal id (the session idiom of the
flow surface), and no route hands out the id of another session. Deleting a
journal drops its space (scene_document_space.delete_journal_space, wired into
the resona journal delete route).

Duplicate protection: before enqueue the route looks for a stored summary of
the same file in ANY session (scene_ingest_service.take_summary, which says why
and under which conditions), checks it at this session's level and copies it
into this session. The answer is a 409 with the doc_id + provenance, and no
second analysis runs. The session id carries the date, so a search in the
session alone ended at midnight UTC.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from flask import Blueprint, jsonify, request

from my_app.services import scene_document_space as space
from my_app.services import scene_ingest_service as jobs
from my_app.services import upload_gate
from my_app.services.safety_gate import check_intake, safety_block
from my_app.services.safety_level_resolver import resolve_safety_level

logger = logging.getLogger(__name__)

scene_bp = Blueprint("scene", __name__, url_prefix="/api/scene")

_ALLOWED_EXTENSIONS = {"pdf"}
# 100 MB — BIBLIOTHEK.md §9 parity (same limit the knowledge upload route
# enforces; the constant lives there, not in config).
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXTENSIONS


def _job_view(job: dict) -> dict:
    """A job as a caller sees it. The log stays on the server: it names the
    document's headings, those of parts the check withheld included. So does
    the session, because a job is read by its id alone."""
    return {k: v for k, v in job.items() if k not in ("log_tail", "journal_id")}


@scene_bp.route("/upload", methods=["POST"])
def upload_document():
    """Multipart PDF upload into the document summary. Requires `journal_id`
    (the session) and the file part `document`. The file check first, the
    intake of the document's name second, the duplicate check third, all
    BEFORE any storage, enqueue or stored summary taken over. A refused name
    answers 403 with the block message. What the document says is taken in by
    the job once the converter has read it."""
    try:
        # Resolved HERE, at the request boundary: the worker thread has no
        # session and would get the strictest level.
        level = resolve_safety_level()
        journal_id = (request.form.get("journal_id") or "").strip()
        if not journal_id:
            return jsonify({"error": "journal_id fehlt (Sitzungsbezug)."}), 400

        if "document" not in request.files:
            return jsonify({"error": "No file part 'document' in request"}), 400
        file = request.files["document"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not _allowed_file(file.filename):
            return jsonify({
                "error": f"Invalid file type. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            }), 400

        file.stream.seek(0, 2)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_UPLOAD_BYTES:
            return jsonify({
                "error": f"File too large ({size} bytes). Max {MAX_UPLOAD_BYTES} bytes (100 MB)."
            }), 400
        if size == 0:
            return jsonify({"error": "Uploaded file is empty."}), 400

        # --- The file check (UCD-131), at every level: deterministic, BEFORE
        # storage. What the document says is not read here: the job takes its
        # text in at the intake once the converter has read it, scanned pages
        # included. ---------------------------------------------------------
        raw_bytes = file.stream.read()
        file.stream.seek(0)
        reason, raw_hash = upload_gate.gate_pdf_file(raw_bytes)

        if reason is not None and not upload_gate.is_duplicate(reason):
            upload_gate.audit_rejection(raw_hash, reason, "scene/upload")
            return jsonify({"error": upload_gate.reject_message(reason)}), 400

        # The summary is written in the language of the surface it came from;
        # a code the form does not carry falls back to the library default.
        from my_app.services.knowledge_processing import DEFAULT_ANALYSIS_LANG

        lang = (request.form.get("lang") or "").strip().lower()
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z]{4})?", lang):
            lang = DEFAULT_ANALYSIS_LANG

        # --- The document's name: it stands on the card and in the job list,
        # and a stored summary is taken over under it, so it passes the intake
        # before anything is looked up. A refusal names the kind of block,
        # never what was found. ---------------------------------------------
        title = (request.form.get("title") or "").strip() or Path(file.filename).stem
        verdict = check_intake(title, level=level, kind="text", field="title")
        if not verdict.passed:
            logger.warning("[SZENE] upload refused at the intake (%s: %s)",
                           verdict.field, verdict.reason_key)
            return jsonify({
                "error": "safety_blocked",
                "safety_block": safety_block(verdict.checkpoint, verdict.reason_key,
                                             field=verdict.field),
            }), 403

        # --- Already summarised, in this session or another --------------------
        # Note: gate_pdf_file's duplicate hit is against the TIER-O hash
        # index (a library document); the summary lookup is the document space.
        # Both mean the same thing for the flow: no second analysis.
        try:
            existing = jobs.take_summary(journal_id, raw_hash, title=title, lang=lang,
                                         safety_level=level)
        except RuntimeError as e:
            # No answer from the check. What this session already holds at this
            # level stands as it is. Otherwise the job asks again when its turn
            # comes, and ends as the technical fault this is.
            logger.warning("[SZENE] check gave no answer for a stored summary: %s", e)
            existing = space.get_document(journal_id, space.doc_id_for(raw_hash))
            if existing is not None and not space.checked_for(existing["meta"], level):
                existing = None
        if existing is None and upload_gate.is_duplicate(reason):
            # Known Tier-O document — not in this session's space, but still
            # no second analysis: the caller is told the document is already
            # analysed on the platform (dossier reference, no scene job).
            return jsonify({
                "success": False,
                "duplicate": True,
                "doc_id": "",
                "error": (
                    "Dieses Dokument wurde bereits analysiert"
                    " — bestehendes Dossier in der Wissensbibliothek."
                    " In der Sitzung kann es keinen zweiten Analyse-Lauf geben."
                ),
            }), 409
        if existing is not None:
            meta = existing.get("meta", {})
            doc_id = meta.get("doc_id", "")
            provenance = ""
            if meta.get("analyzed_at"):
                provenance = (
                    f" Analysiert am {meta['analyzed_at']}"
                    f" mit {meta.get('analysis_model') or 'unbekanntem Modell'}."
                )
            return jsonify({
                "success": False,
                "duplicate": True,
                "doc_id": doc_id,
                "error": (
                    "Dieses Dokument wurde bereits analysiert"
                    + (f" — bestehende Zusammenfassung: '{doc_id}'." if doc_id else ".")
                    + provenance
                ),
            }), 409

        # --- The same document is still being summarised in this session: the
        # space only holds finished documents, so a second upload during the
        # minutes of the first would otherwise start a second run.
        running = jobs.find_active_job(journal_id, raw_hash)
        if running is not None:
            return jsonify({
                "success": False,
                "duplicate": True,
                "doc_id": running["doc_id"],
                "job_id": running["job_id"],
                "error": "Dieses Dokument wird in dieser Sitzung gerade zusammengefasst.",
            }), 409

        # --- Admitted: stage into a JOB temp dir (§6 — the only place the raw
        # PDF ever exists outside the caller's hands; the worker deletes it) --
        tmp_dir = jobs.new_staging_dir()
        staged_pdf = tmp_dir / "document.pdf"
        doc_id = space.doc_id_for(raw_hash)
        try:
            file.save(str(staged_pdf))
            job_id = jobs.enqueue_scene_ingest(
                journal_id=journal_id,
                title=title,
                staged_pdf=staged_pdf,
                raw_hash=raw_hash,
                doc_id=doc_id,
                lang=lang,
                safety_level=level,
            )
        except jobs.DuplicateJobError as dup:
            # Lost the race against an identical upload: its raw PDF goes now.
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return jsonify({
                "success": False,
                "duplicate": True,
                "doc_id": dup.doc_id,
                "job_id": dup.job_id,
                "error": "Dieses Dokument wird in dieser Sitzung gerade zusammengefasst.",
            }), 409
        except Exception:
            # No job took the file over, so nothing else would delete it.
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
        logger.info("[SZENE] queued scene job %s for %s (journal %s)",
                    job_id, doc_id, journal_id)
        return jsonify({"success": True, "job_id": job_id, "doc_id": doc_id}), 200
    except Exception as e:  # noqa: BLE001
        logger.error("[SZENE] upload failed: %s", e)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@scene_bp.route("/jobs", methods=["GET"])
def list_jobs():
    """The jobs of one session."""
    journal_id = (request.args.get("journal_id") or "").strip()
    if not journal_id:
        return jsonify({"error": "journal_id fehlt."}), 400
    return jsonify({"jobs": [_job_view(j) for j in jobs.list_jobs()
                             if j["journal_id"] == journal_id]})


@scene_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    job = jobs.get_job(job_id)
    if job is None:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(_job_view(job))


@scene_bp.route("/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    return jsonify(jobs.request_cancel(job_id))


@scene_bp.route("/documents", methods=["GET"])
def list_documents():
    """All analysed documents of one session (counts only — the surface
    lists; single documents carry the summary)."""
    journal_id = (request.args.get("journal_id") or "").strip()
    if not journal_id:
        return jsonify({"error": "journal_id fehlt."}), 400
    return jsonify({"documents": space.list_documents(journal_id)})


@scene_bp.route("/documents/<doc_id>", methods=["GET"])
def get_document(doc_id):
    """One document with its summary (profile, sections, glossary) and
    provenance. A document checked at a looser level than the session's stands
    back until the file comes in again and goes through this level's check."""
    from my_app.services.safety_level_resolver import resolve_safety_level

    journal_id = (request.args.get("journal_id") or "").strip()
    if not journal_id:
        return jsonify({"error": "journal_id fehlt."}), 400
    doc = space.get_document(journal_id, doc_id)
    if doc is None or not space.checked_for(doc["meta"], resolve_safety_level()):
        return jsonify({"error": "unknown document"}), 404
    return jsonify(doc)


@scene_bp.route("/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    """Remove ONE document's space entry. A fresh upload of the same file is
    summarised again unless another session holds a summary of it."""
    journal_id = (request.args.get("journal_id") or "").strip()
    if not journal_id:
        return jsonify({"error": "journal_id fehlt."}), 400
    jd = space._journal_dir(journal_id)
    d = space._doc_dir(journal_id, doc_id)
    if d is None or jd is None or not d.exists():
        return jsonify({"error": "unknown document"}), 404
    import shutil

    shutil.rmtree(d, ignore_errors=True)
    return jsonify({"success": True})
