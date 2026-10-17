"""Szenen-Kapsel-Pipeline — HTTP-Routen (UCD-132).

/api/scene/* — the BACKEND surface of UCD-132 (no "+"-Integration; that is
UCD-133's own scope). The upload route runs the Stage-A gate (UCD-131,
synchronously, BEFORE storage/enqueue — rejected files cost nothing), then
stages the PDF into a job temp dir and enqueues the scene pipeline job.

Session scoping: the caller supplies the resona journal id (the session
idiom of the flow surface). The document space verfällt mit der Sitzung;
deleting a journal drops its space (scene_document_space.delete_journal_space
— wired into the resona journal delete route).

Duplicate protection (§5 layer 1, session-scoped): before enqueue the
route consults the session space's hash map; a re-upload of an already
analysed document gets a 409 with the existing doc_id + provenance — no
second analysis (acceptance 5).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from my_app.services import scene_document_space as space
from my_app.services import scene_ingest_service as jobs
from my_app.services import upload_gate

logger = logging.getLogger(__name__)

scene_bp = Blueprint("scene", __name__, url_prefix="/api/scene")

_ALLOWED_EXTENSIONS = {"pdf"}
# 100 MB — BIBLIOTHEK.md §9 parity (same limit the knowledge upload route
# enforces; the constant lives there, not in config).
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXTENSIONS


def _find_doc_by_hash(journal_id: str, raw_hash: str) -> dict | None:
    """Session-scoped hash lookup: the FIRST document of this session whose
    doc_hash matches (acceptance 5 — same document re-uploaded within the
    session refers back to the existing analysis)."""
    for doc in space.list_documents(journal_id):
        full = space.get_document(journal_id, doc["doc_id"])
        if full and full["meta"].get("doc_hash") == raw_hash:
            return full
    return None


@scene_bp.route("/upload", methods=["POST"])
def upload_document():
    """Multipart PDF upload into the scene pipeline. Requires `journal_id`
    (the session) and the file part `document`. Stage-A gate first, duplicate
    check second — both BEFORE any storage or enqueue."""
    try:
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

        # --- Stage-A admission gate (UCD-131): deterministic, BEFORE storage --
        raw_bytes = file.stream.read()
        file.stream.seek(0)
        reason, raw_hash = upload_gate.gate_pdf_upload(raw_bytes)

        if reason is not None and not upload_gate.is_duplicate(reason):
            upload_gate.audit_rejection(raw_hash, reason, "scene/upload")
            return jsonify({"error": upload_gate.reject_message(reason)}), 400

        # --- Duplicate within the session (§5 layer 1 / acceptance 5) ----------
        # Note: gate_pdf_upload's duplicate hit is against the TIER-O hash
        # index (a library document); the SESSION check is the space lookup.
        # Both mean the same thing for the flow: no second analysis.
        existing = _find_doc_by_hash(journal_id, raw_hash)
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
                "n_capsules": existing.get("n_capsules", 0),
                "error": (
                    "Dieses Dokument wurde in dieser Sitzung bereits analysiert"
                    + (f" — bestehende Kapseln: '{doc_id}'." if doc_id else ".")
                    + provenance
                ),
            }), 409

        # --- Admitted: stage into a JOB temp dir (§6 — the only place the raw
        # PDF ever exists outside the caller's hands; the worker deletes it) --
        tmp_dir = Path(tempfile.mkdtemp(prefix="scene_pdf_"))
        staged_pdf = tmp_dir / "document.pdf"
        file.save(str(staged_pdf))

        title = (request.form.get("title") or "").strip() or Path(file.filename).stem
        doc_id = f"doc-{raw_hash[:12]}"
        job_id = jobs.enqueue_scene_ingest(
            journal_id=journal_id,
            title=title,
            staged_pdf=staged_pdf,
            raw_hash=raw_hash,
            doc_id=doc_id,
        )
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
    return jsonify({"jobs": jobs.list_jobs()})


@scene_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    job = jobs.get_job(job_id)
    if job is None:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(job)


@scene_bp.route("/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    return jsonify(jobs.request_cancel(job_id))


@scene_bp.route("/documents", methods=["GET"])
def list_documents():
    """All analysed documents of one session (counts only — the surface
    lists; single documents carry the capsules)."""
    journal_id = (request.args.get("journal_id") or "").strip()
    if not journal_id:
        return jsonify({"error": "journal_id fehlt."}), 400
    return jsonify({"documents": space.list_documents(journal_id)})


@scene_bp.route("/documents/<doc_id>", methods=["GET"])
def get_document(doc_id):
    """One document with its capsules + segment digests (the agent question
    base) and provenance."""
    journal_id = (request.args.get("journal_id") or "").strip()
    if not journal_id:
        return jsonify({"error": "journal_id fehlt."}), 400
    doc = space.get_document(journal_id, doc_id)
    if doc is None:
        return jsonify({"error": "unknown document"}), 404
    return jsonify(doc)


@scene_bp.route("/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    """Remove ONE document's space entry (incl. its hash protection — a
    fresh upload of the same file becomes analysable again)."""
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
