"""
Knowledge Library — Settings/Curation routes (Phase 2).

The operator-facing curation layer for Tier-O documents (operator uploads). All
routes require Settings auth (@require_settings_auth) and never touch the
Resona retrieval path: the running server's search/read stay published-only and
untouched. This blueprint only

  * accepts a PDF/MD upload, derives a collision-free doc_id, stores the
    original, and enqueues an ingest job (POST /upload),
  * re-runs the SAME ingest pipeline on an already-ingested doc_id's stored
    source, WITHOUT re-upload, preserving its metadata (POST
    /items/<doc_id>/reprocess),
  * exposes the ingest job registry (GET /jobs, /jobs/<id>),
  * lists / shows Tier-O items INCLUDING drafts (GET /items, /items/<id>),
  * toggles draft<->published, edits the card, deletes an item (mutations are
    Tier-O only; Tier-F -> 403),
  * edits the glossary overrides (GET/PUT /glossary-overrides), and
  * triggers a manual reindex (POST /reindex).

Upload idiom mirrors media_routes.py (secure_filename, extension whitelist,
error/success JSON shape). Job idiom: knowledge_ingest_service (FIFO worker,
Docling -> in-process Verdichtung -> reindex). Since the Formular-
Entbürokratisierung (2026-07-04) only the FILE is required — license defaults to
internal-use-only and the title is extracted from the document.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from flask import Blueprint, Response, jsonify, request
from werkzeug.utils import secure_filename

import config
from my_app.routes.settings_routes import require_settings_auth
from my_app.services import knowledge_library as kl
from my_app.services import knowledge_ingest_service as jobs
from my_app.services import knowledge_areas as areas
from my_app.services import upload_gate

logger = logging.getLogger(__name__)

knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/knowledge")

ALLOWED_EXTENSIONS = {"pdf", "md"}
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB upload cap

# doc_id sanitiser (same character class as the ingest kebab-slug / the service
# path sanitiser): lowercase alphanumerics and hyphens.
_ID_SAFE = re.compile(r"[^a-z0-9]+")


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _kebab(text: str) -> str:
    s = _ID_SAFE.sub("-", (text or "").lower()).strip("-")
    return s or "document"


def _derive_doc_id(title: str, year: Optional[str], fallback: str = "") -> str:
    """Derive a Tier-O doc_id from title (+year), then make it collision-free
    against BOTH the Tier-F library and the Tier-O exports (suffix -2, -3, …).
    WITHOUT the 'unesco-' prefix. When the title is empty (now optional), fall
    back to the uploaded filename stem so the id is still meaningful; the real
    title is extracted from the document paratext during Verdichtung."""
    base = _kebab(title) if (title or "").strip() else _kebab(fallback)
    if year and str(year).strip():
        base = f"{base}-{str(year).strip()}"
    candidate = base
    n = 1
    while _doc_id_taken(candidate):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def _doc_id_taken(doc_id: str) -> bool:
    tier_o = Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md"
    if tier_o.exists():
        return True
    # Tier-F library is a tree (library/unesco/…): scan for any <doc_id>.md.
    lib = Path(config.KNOWLEDGE_LIBRARY_DIR)
    if lib.exists():
        for p in lib.rglob(f"{doc_id}.md"):
            return True
    return False


# ---------------------------------------------------------------------------
# Upload + ingest
# ---------------------------------------------------------------------------

# Default license when the operator leaves the field blank (Formular-
# Entbürokratisierung, 2026-07-04): the safest conservative assumption for an
# internal upload of unknown provenance.
_DEFAULT_LICENSE = "Alle Rechte vorbehalten — nur interne Nutzung"


@knowledge_bp.route("/upload", methods=["POST"])
@require_settings_auth
def upload_document():
    """Multipart upload of a Tier-O document (PDF or MD). Stores the original and
    enqueues an ingest job (Docling -> Verdichtung -> reindex).

    Formular-Entbürokratisierung (2026-07-04): only the FILE is truly required.
    title/year/lang are optional — the Verdichtung extracts the title from the
    document paratext (fallback: filename) and detects the source language
    itself (identify_bibliographic); analysis defaults to English and is never
    a hardcoded German assumption (Defect 1c). lizenz is optional and defaults
    to an internal-use-only license.
    """
    try:
        if "document" not in request.files:
            return jsonify({"error": "No file part 'document' in request"}), 400
        file = request.files["document"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not _allowed_file(file.filename):
            return jsonify({
                "error": f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            }), 400

        # All metadata optional now — only the file is required.
        title = (request.form.get("title") or "").strip()
        lizenz = (request.form.get("lizenz") or "").strip() or _DEFAULT_LICENSE
        autor = (request.form.get("autor") or "").strip()
        year = (request.form.get("year") or "").strip()
        lang = (request.form.get("lang") or "").strip()  # blank -> source language auto-detected (Verdichtung analysis defaults to English otherwise)
        url = (request.form.get("url") or "").strip()
        sparten = (request.form.get("sparten") or "").strip()
        themen = (request.form.get("themen") or "").strip()
        # Operator area (bereich) + per-document note (hinweis). The UI always
        # sets bereich; the fixed UNESCO pseudo-area is a view-only sentinel and
        # can NEVER be an upload target. An unknown (non-existent) bereich is
        # rejected too, so a document can't be tagged with a dangling area id.
        bereich = (request.form.get("bereich") or "").strip()
        hinweis = (request.form.get("hinweis") or "").strip()
        if bereich:
            if bereich == areas.UNESCO_ID:
                return jsonify({
                    "error": "Der UNESCO-Bereich ist fest und nimmt keine Uploads auf."
                }), 400
            if not areas.area_exists(bereich):
                return jsonify({"error": f"Unbekannter Bereich '{bereich}'."}), 400

        # Enforce the size limit by reading into memory-bounded stream check.
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_UPLOAD_BYTES:
            return jsonify({
                "error": f"File too large ({size} bytes). Max {MAX_UPLOAD_BYTES} bytes (100 MB)."
            }), 400
        if size == 0:
            return jsonify({"error": "Uploaded file is empty."}), 400

        # --- Stage-A admission gate (UCD-131): deterministic, BEFORE storage ---
        # The upload is read into memory once (the 100 MB cap was enforced
        # above); every check is pure Python / pypdf — zero model cost. A
        # reject means: nothing stored, no Docling run, no enqueue. Only the
        # audit line is written (docHash, rule category, timestamp — never
        # content, never a found term).
        raw_bytes = file.stream.read()
        file.stream.seek(0)
        raw_hash = upload_gate.sha256_hex(raw_bytes)

        safe_name = secure_filename(file.filename)
        ext = safe_name.rsplit(".", 1)[1].lower()

        if ext == "pdf":
            reason = upload_gate.gate_pdf_upload(raw_bytes)[0]
            if upload_gate.is_duplicate(reason):
                # Known document: no new job, no second analysis (cost defect,
                # UCD-124 §5 layer 1). The answer points at the existing
                # dossier with its provenance. Explicit re-analysis stays the
                # operator's way: reprocess_item on the existing doc_id
                # (working basis while the UCD-124 decision is open).
                entry = upload_gate.lookup_hash_index(raw_hash) or {}
                existing_doc_id = str(entry.get("doc_id", ""))
                item = kl.get_operator_item(existing_doc_id) if existing_doc_id else None
                provenance = ""
                if item and item.get("analyzed_at"):
                    provenance = (
                        f" Analysiert am {item['analyzed_at']}"
                        f" mit {item.get('analysis_model') or 'unbekanntem Modell'}"
                        f" (Analysesprache {item.get('analysis_lang') or 'unbekannt'})."
                    )
                return jsonify({
                    "success": False,
                    "duplicate": True,
                    "doc_id": existing_doc_id,
                    "error": (
                        "Dieses Dokument wurde bereits analysiert"
                        + (f" — bestehendes Dossier: '{existing_doc_id}'." if existing_doc_id else ".")
                        + provenance
                        + " Eine Neu-Analyse ist über die Neu-Analyse-Funktion des bestehenden Dossiers möglich."
                    ),
                }), 409
            if reason is not None:
                upload_gate.audit_rejection(raw_hash, reason, "knowledge/upload")
                return jsonify({"error": upload_gate.reject_message(reason)}), 400
        else:
            # MD upload: hash blocklist only (validation: it is text; the
            # curated §86/§86a scan runs in the pipeline stage B on the
            # analysis side — an MD has no binary attack surface).
            if raw_hash in upload_gate.load_blocked_hashes():
                upload_gate.audit_rejection(raw_hash, upload_gate.REASON_BLOCKED_HASH, "knowledge/upload")
                return jsonify({"error": upload_gate.reject_message(upload_gate.REASON_BLOCKED_HASH)}), 400

        filename_stem = safe_name.rsplit(".", 1)[0]
        doc_id = _derive_doc_id(title, year, fallback=filename_stem)

        source_pdf: Optional[Path] = None
        source_md: Optional[Path] = None
        cleanup_paths = []

        if ext == "pdf":
            # Store the original under resources/knowledge_originals/operator/.
            originals_dir = Path(config.KNOWLEDGE_ORIGINALS_DIR) / "operator"
            originals_dir.mkdir(parents=True, exist_ok=True)
            source_pdf = originals_dir / f"{doc_id}.pdf"
            file.save(str(source_pdf))
        else:  # md — no original store; stage into a tmp dir as ingest input.
            tmp_dir = Path(tempfile.mkdtemp(prefix="knowledge_md_"))
            source_md = tmp_dir / f"{doc_id}.md"
            file.save(str(source_md))
            cleanup_paths = [source_md, tmp_dir]

        year_int = None
        if year:
            try:
                year_int = int(year)
            except ValueError:
                year_int = None

        job_id = jobs.enqueue_ingest(
            doc_id=doc_id,
            title=title,
            lizenz=lizenz,
            source_pdf=source_pdf,
            source_md=source_md,
            autor=autor,
            year=year_int,
            lang=lang,
            url=url,
            sparten=sparten,
            themen=themen,
            bereich=bereich,
            hinweis=hinweis,
            cleanup_paths=cleanup_paths,
            raw_hash=raw_hash,
        )
        logger.info("[KNOWLEDGE] queued ingest job %s for doc_id=%s (%s)", job_id, doc_id, ext)
        return jsonify({"success": True, "job_id": job_id, "doc_id": doc_id}), 200
    except Exception as e:  # noqa: BLE001
        logger.error("[KNOWLEDGE] upload failed: %s", e)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@knowledge_bp.route("/jobs", methods=["GET"])
@require_settings_auth
def list_ingest_jobs():
    return jsonify({"jobs": jobs.list_jobs(log_tail=0)}), 200


@knowledge_bp.route("/jobs/<job_id>", methods=["GET"])
@require_settings_auth
def get_ingest_job(job_id):
    job = jobs.get_job(job_id, log_tail=40)
    if job is None:
        return jsonify({"error": f"No such job '{job_id}'"}), 404
    return jsonify(job), 200


@knowledge_bp.route("/jobs/<job_id>/cancel", methods=["POST"])
@require_settings_auth
def cancel_ingest_job(job_id):
    """Cancel an ingest job. A `queued` job is dropped from the queue; a
    `running` job is asked to stop at the next step boundary (and its in-flight
    Docling/reindex subprocess is terminated). A job that is already
    done/error/cancelled -> 409 (nothing to cancel). Unknown id -> 404. The
    unfinished draft + raw intermediate of a cancelled run are cleaned up by the
    worker; the original upload is kept for re-processing."""
    result = jobs.request_cancel(job_id)
    if result.get("ok"):
        job = jobs.get_job(job_id, log_tail=40)
        return jsonify({"success": True, "job_id": job_id,
                        "state": result["state"], "job": job}), 200
    if result.get("state") is None:  # no such job
        return jsonify({"error": result.get("error", f"No such job '{job_id}'")}), 404
    # terminal state -> conflict
    return jsonify({"error": result.get("error", "job cannot be cancelled"),
                    "state": result["state"]}), 409


# ---------------------------------------------------------------------------
# Items (Tier-O curation, drafts included)
# ---------------------------------------------------------------------------

@knowledge_bp.route("/items", methods=["GET"])
@require_settings_auth
def list_items():
    # Optional ?bereich=<area-id> filter (the area panel lists only its docs).
    # The fixed UNESCO pseudo-area is not a real `bereich` tag on any doc: it
    # stands for the committed Tier-F corpus, so ?bereich=unesco returns that
    # read-only list (every item carries readonly:true) instead of Tier-O docs.
    # This is Settings-transparency only — the Resona retrieval path is untouched.
    bereich = (request.args.get("bereich") or "").strip() or None
    if bereich == areas.UNESCO_ID:
        return jsonify({"items": kl.list_fixed_items()}), 200
    return jsonify({"items": kl.list_operator_items(bereich=bereich)}), 200


@knowledge_bp.route("/items/<doc_id>", methods=["GET"])
@require_settings_auth
def get_item(doc_id):
    # Tier-O curation view first; fall back to the read-only Tier-F view so a
    # committed UNESCO doc_id opens its profile too (readonly:true in the body).
    # This GET is read-only either way — the mutation routes below stay Tier-O
    # only (a Tier-F doc_id is "not found" there → 404/403, guards unchanged).
    item = kl.get_operator_item(doc_id) or kl.get_fixed_item(doc_id)
    if item is None:
        return jsonify({"error": f"No knowledge item '{doc_id}'"}), 404
    return jsonify(item), 200


# ---------------------------------------------------------------------------
# Wissensbereiche (operator areas) — MoJo-Diskursräume analogue
# ---------------------------------------------------------------------------
# CRUD over the operator-defined areas (knowledge_areas service), enriched with
# a live document count per area read from the FTS index. The fixed UNESCO
# pseudo-area is appended to the listing (view-only: the Tier-F corpus).

def _bereich_counts() -> dict:
    """{area_id: {"total": n, "published": m}} over ALL Tier-O docs in the index
    (drafts included — this is the curation view; "published" counts the subset
    with status='published' so the chips can show published/total). Empty when
    the index is missing or predates the bereich column."""
    import sqlite3
    db = Path(config.KNOWLEDGE_INDEX_DB)
    if not db.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    except sqlite3.Error:
        return {}
    try:
        cols = {r["name"] for r in con.execute("PRAGMA table_info(docs)").fetchall()}
        if "bereich" not in cols:
            return {}
        rows = con.execute(
            "SELECT bereich, COUNT(*) AS total, "
            "       SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) AS published "
            "FROM docs "
            "WHERE tier = 'O' AND bereich IS NOT NULL AND bereich <> '' "
            "GROUP BY bereich"
        ).fetchall()
        return {r["bereich"]: {"total": int(r["total"]),
                               "published": int(r["published"] or 0)}
                for r in rows}
    finally:
        con.close()


def _count_fields(counts: dict, area_id: str) -> dict:
    """The three count fields of an /areas response entry, from _bereich_counts.
    `count` stays the TOTAL (drafts included) for backwards compatibility — the
    delete-safety check and any older consumer read it; `count_published` /
    `count_total` back the chips' published/total display."""
    c = counts.get(area_id) or {"total": 0, "published": 0}
    return {"count": c["total"], "count_published": c["published"],
            "count_total": c["total"]}


def _unesco_counts() -> dict:
    """{"total": n, "published": m} over the Tier-F corpus (the UNESCO
    pseudo-area). Committed Tier-F docs ship published, so this is normally
    n/n — but count from the index rather than assuming."""
    import sqlite3
    db = Path(config.KNOWLEDGE_INDEX_DB)
    if not db.exists():
        return {"total": 0, "published": 0}
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {"total": 0, "published": 0}
    try:
        row = con.execute(
            "SELECT COUNT(*), "
            "       SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) "
            "FROM docs WHERE tier = 'F'"
        ).fetchone()
        if not row:
            return {"total": 0, "published": 0}
        return {"total": int(row[0]), "published": int(row[1] or 0)}
    except sqlite3.Error:
        return {"total": 0, "published": 0}
    finally:
        con.close()


def _unesco_pseudo_area() -> dict:
    c = _unesco_counts()
    return {
        "id": areas.UNESCO_ID,
        "fixed": True,
        "name": "UNESCO — Werteausrichtung",
        "kommentar": "",
        "count": c["total"],
        "count_published": c["published"],
        "count_total": c["total"],
    }


@knowledge_bp.route("/areas", methods=["GET"])
@require_settings_auth
def list_areas():
    counts = _bereich_counts()
    out = []
    for a in areas.list_areas():
        out.append({**a, "fixed": False, **_count_fields(counts, a["id"])})
    out.append(_unesco_pseudo_area())
    return jsonify({"areas": out}), 200


def _export_item_line(it: dict) -> str:
    """One Markdown bullet for an export item: **Titel** — Autor (Jahr), with a
    bracketed status suffix for anything not published (drafts, so an operator
    scanning the export can tell what is not yet live)."""
    titel = it.get("titel") or it.get("doc_id") or "(ohne Titel)"
    autor = it.get("autor") or ""
    jahr = it.get("jahr") or ""
    meta = " ".join(x for x in (autor, f"({jahr})" if jahr else "") if x)
    status = it.get("status") or ""
    suffix = f" [{status}]" if status and status != "published" else ""
    line = f"- **{titel}**"
    if meta:
        line += f" — {meta}"
    line += suffix
    return line


@knowledge_bp.route("/export.md", methods=["GET"])
@require_settings_auth
def export_markdown():
    """Flat Markdown export of the whole Knowledge Library, grouped by area:
    operator areas (Bereiche, creation order) with their `kommentar`, an
    "(kein Bereich)" bucket for un-tagged Tier-O items, and the fixed UNESCO
    pseudo-area last. Each item is one line (Titel — Autor (Jahr)), sorted by
    title within its area. Read-only, Settings-transparency only — flattens the
    same data GET /areas + GET /items already expose, into one downloadable
    file so an operator can see the whole library (author/title/area) at a
    glance."""
    lines = ["# Knowledge Library", ""]

    all_operator_items = kl.list_operator_items()
    for a in areas.list_areas():
        items = sorted(
            (it for it in all_operator_items if it.get("bereich") == a["id"]),
            key=lambda it: (it.get("titel") or "").lower(),
        )
        lines.append(f"## {a['name']}")
        if a.get("kommentar"):
            lines.append(f"_{a['kommentar']}_")
        lines.append("")
        if not items:
            lines.append("_(keine Dokumente)_")
        else:
            lines.extend(_export_item_line(it) for it in items)
        lines.append("")

    unassigned = sorted(
        (it for it in all_operator_items if not it.get("bereich")),
        key=lambda it: (it.get("titel") or "").lower(),
    )
    if unassigned:
        lines.append("## (kein Bereich)")
        lines.append("")
        lines.extend(_export_item_line(it) for it in unassigned)
        lines.append("")

    fixed_items = sorted(kl.list_fixed_items(), key=lambda it: (it.get("titel") or "").lower())
    lines.append("## UNESCO — Werteausrichtung")
    lines.append("")
    if not fixed_items:
        lines.append("_(keine Dokumente)_")
    else:
        lines.extend(_export_item_line(it) for it in fixed_items)
    lines.append("")

    md = "\n".join(lines) + "\n"
    return Response(
        md,
        mimetype="text/markdown",
        headers={"Content-Disposition": "attachment; filename=knowledge_library.md"},
    )



@knowledge_bp.route("/areas", methods=["POST"])
@require_settings_auth
def create_area():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    kommentar = str(data.get("kommentar", "") or "").strip()
    if not name:
        return jsonify({"error": "'name' darf nicht leer sein."}), 400
    try:
        area = areas.create_area(name, kommentar)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"success": True,
                    "area": {**area, "fixed": False, "count": 0,
                             "count_published": 0, "count_total": 0}}), 200


@knowledge_bp.route("/areas/<area_id>", methods=["PUT"])
@require_settings_auth
def update_area(area_id):
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    kommentar = data.get("kommentar")
    try:
        area = areas.update_area(
            area_id,
            name=None if name is None else str(name),
            kommentar=None if kommentar is None else str(kommentar),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if area is None:
        return jsonify({"error": f"Unbekannter Bereich '{area_id}'."}), 404
    counts = _bereich_counts()
    return jsonify({"success": True,
                    "area": {**area, "fixed": False,
                             **_count_fields(counts, area_id)}}), 200


@knowledge_bp.route("/areas/<area_id>", methods=["DELETE"])
@require_settings_auth
def delete_area(area_id):
    # An area with documents cannot be deleted (the operator must first move or
    # remove its documents). The index is the source of truth for membership.
    # TOTAL count on purpose: drafts block deletion just like published docs.
    count = _count_fields(_bereich_counts(), area_id)["count_total"]
    if count > 0:
        return jsonify({
            "error": f"Bereich enthält noch {count} Dokument(e) — erst leeren.",
            "count": count,
        }), 400
    try:
        ok = areas.delete_area(area_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not ok:
        return jsonify({"error": f"Unbekannter Bereich '{area_id}'."}), 404
    return jsonify({"success": True, "area_id": area_id}), 200


@knowledge_bp.route("/items/<doc_id>/status", methods=["POST"])
@require_settings_auth
def set_item_status(doc_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip()
    if status not in ("draft", "published"):
        return jsonify({"error": "status must be 'draft' or 'published'"}), 400
    try:
        ok = kl.set_operator_status(doc_id, status)
    except PermissionError:
        return jsonify({"error": "Tier-F documents cannot be modified here."}), 403
    if not ok:
        return jsonify({"error": f"No Tier-O item '{doc_id}'"}), 404
    rc, log = _reindex_sync()
    return jsonify({"success": True, "doc_id": doc_id, "status": status,
                    "reindex_rc": rc, "reindex_log": log}), 200


@knowledge_bp.route("/items/<doc_id>/bereich", methods=["POST"])
@require_settings_auth
def set_item_bereich(doc_id):
    """Move a Tier-O document to another operator area (or to no area).

    Body: {"bereich": "<area-id>"} to move into an area, or {"bereich": null}
    (or "") to remove the area. The target must be an existing operator area;
    the fixed UNESCO pseudo-area is rejected (400), as is an unknown area (400).
    Tier-F documents are not addressable here (404/403). Reindexes on success so
    items?bereich + the /areas counts follow immediately. Response carries the
    old and new area for the UI."""
    data = request.get_json(silent=True) or {}
    if "bereich" not in data:
        return jsonify({"error": "Body must include 'bereich' (an area id or null)."}), 400
    raw = data.get("bereich")
    target = "" if raw is None else str(raw).strip()

    # Validate the target: null/"" clears the area; otherwise it must be a real
    # operator area and never the fixed UNESCO pseudo-area (mirrors upload).
    if target:
        if target == areas.UNESCO_ID:
            return jsonify({
                "error": "Der UNESCO-Bereich ist fest und nimmt keine Dokumente auf."
            }), 400
        if not areas.area_exists(target):
            return jsonify({"error": f"Unbekannter Bereich '{target}'."}), 400

    # Capture the current area for the response before rewriting.
    current = kl.get_operator_item(doc_id)
    if current is None:
        return jsonify({"error": f"No Tier-O item '{doc_id}'"}), 404
    old_bereich = (current.get("bereich") or "") or None

    try:
        ok = kl.set_operator_bereich(doc_id, target or None)
    except PermissionError:
        return jsonify({"error": "Tier-F documents cannot be modified here."}), 403
    if not ok:
        return jsonify({"error": f"No Tier-O item '{doc_id}'"}), 404
    rc, log = _reindex_sync()
    return jsonify({"success": True, "doc_id": doc_id,
                    "old_bereich": old_bereich, "bereich": target or None,
                    "reindex_rc": rc, "reindex_log": log}), 200


@knowledge_bp.route("/items/<doc_id>/card", methods=["PUT"])
@require_settings_auth
def put_item_card(doc_id):
    data = request.get_json(silent=True) or {}
    card = data.get("card")
    if card is None:
        return jsonify({"error": "Body must include 'card'."}), 400
    try:
        ok = kl.set_operator_card(doc_id, str(card))
    except PermissionError:
        return jsonify({"error": "Tier-F documents cannot be modified here."}), 403
    if not ok:
        return jsonify({"error": f"No Tier-O item '{doc_id}'"}), 404
    rc, log = _reindex_sync()
    return jsonify({"success": True, "doc_id": doc_id,
                    "reindex_rc": rc, "reindex_log": log}), 200


@knowledge_bp.route("/items/<doc_id>/meta", methods=["PUT"])
@require_settings_auth
def put_item_meta(doc_id):
    """Edit the bibliographic front-matter of a Tier-O item: titel, autor, jahr,
    quelle. This is the operator's correction surface for a mis-identified title
    (the filename/byline/chapter-heading-as-title problem, 2026-07-05): the
    ingest identifier is best-effort; the operator has the last word.

    Body: any subset of {"titel", "autor", "jahr", "quelle"}. Only the keys
    present are changed; the rest of the front-matter (and the whole body) is left
    byte-for-byte untouched. `titel`, when given, must not be blank (a document
    keeps a title). `autor`/`quelle` may be "" to clear them. `jahr` may be a year
    int, a year string, or "" to clear it; a non-year string is rejected. Tier-F
    documents are not addressable here (404/403). Reindexes on success so the
    inventory + search follow immediately."""
    data = request.get_json(silent=True) or {}
    fields = {k: data[k] for k in ("titel", "autor", "jahr", "quelle") if k in data}
    if not fields:
        return jsonify({
            "error": "Body must include at least one of titel, autor, jahr, quelle."
        }), 400
    if "titel" in fields and not str(fields["titel"] or "").strip():
        return jsonify({"error": "titel darf nicht leer sein."}), 400
    if "jahr" in fields:
        raw = fields["jahr"]
        if raw is not None and str(raw).strip() != "":
            if not re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(raw)):
                return jsonify({"error": "jahr muss eine Jahreszahl sein (oder leer)."}), 400
    try:
        ok = kl.set_operator_meta(doc_id, **fields)
    except PermissionError:
        return jsonify({"error": "Tier-F documents cannot be modified here."}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not ok:
        return jsonify({"error": f"No Tier-O item '{doc_id}'"}), 404
    rc, log = _reindex_sync()
    # Echo the resulting values so the UI can reflect the normalised state.
    item = kl.get_operator_item(doc_id) or {}
    return jsonify({"success": True, "doc_id": doc_id,
                    "titel": item.get("titel", ""), "autor": item.get("autor", ""),
                    "jahr": item.get("jahr", ""), "quelle": item.get("quelle", ""),
                    "reindex_rc": rc, "reindex_log": log}), 200


@knowledge_bp.route("/items/<doc_id>", methods=["DELETE"])
@require_settings_auth
def delete_item(doc_id):
    try:
        result = kl.delete_operator_item(doc_id)
    except PermissionError:
        return jsonify({"error": "Tier-F documents cannot be modified here."}), 403
    if not result["md_deleted"]:
        return jsonify({"error": f"No Tier-O item '{doc_id}'"}), 404
    # Stage A (UCD-131): the deleted dossier's hash-index entries must go too,
    # or the same file could never be uploaded again ("already analysed").
    upload_gate.remove_hash_index(doc_id)
    rc, log = _reindex_sync()
    return jsonify({"success": True, "doc_id": doc_id, **result,
                    "reindex_rc": rc, "reindex_log": log}), 200


# ---------------------------------------------------------------------------
# Reprocess (re-run Verdichtung on an already-ingested doc, no re-upload)
# ---------------------------------------------------------------------------

@knowledge_bp.route("/items/<doc_id>/reprocess", methods=["POST"])
@require_settings_auth
def reprocess_item(doc_id):
    """Re-run the SAME ingest pipeline (Docling passthrough for a stored
    .raw.md -> Verdichtung with the CURRENTLY configured
    KNOWLEDGE_PROCESSING_MODEL -> reindex) on an ALREADY-ingested Tier-O
    document, without re-uploading the source (2026-07-09: ~30 operator docs
    need re-Verdichtung now that the model is pinned).

    The existing front-matter (titel, autor, jahr, bereich, lizenz, url,
    sparten, themen, hinweis) is read from the current Tier-O item via the
    same helper the GET /items/<doc_id> route uses, and carried through
    unchanged so nothing is lost on re-run. `sprache` is the ONE exception:
    it is deliberately NOT carried over but re-detected fresh on every
    reprocess (Defect 1c) -- all 30 existing items currently say "de"
    unconditionally, which is exactly the hardcoded assumption being fixed;
    carrying it forward would make that lie permanent.

    Source resolution prefers the raw Docling Markdown intermediate the
    original ingest wrote (resources/knowledge_originals/operator/
    <doc_id>.raw.md) — Docling then becomes a no-op passthrough and only
    Verdichtung + reindex actually run. Falls back to the stored PDF
    (<doc_id>.pdf, re-runs Docling too) if no .raw.md survived. Neither
    present -> 404 naming the doc_id (nothing to re-analyze from).

    NOTE: a re-analyze carries the item's CURRENT `status` and `bereich`
    forward (a reprocess of a `published` document stays `published`; a
    reprocess of a `draft` stays `draft`) -- unlike a fresh upload, which
    always starts at `draft`. Before this fix, every reprocess unconditionally
    reset `status` to `draft`, which would have silently unpublished 25 of the
    30 documents in the library on the owner's planned bulk re-analysis.

    NOTE: cancelling a reprocess must not destroy the existing draft or the
    stored source either. enqueue_ingest(reprocess=True) tells
    _finish_cancelled to leave both <doc_id>.md and raw_out untouched on a
    cancel (see its docstring for the full reasoning). Before THIS fix, every
    cancelled reprocess removed both exactly as a cancelled fresh upload does,
    on the mistaken assumption that both were this run's own throwaway
    partial artefacts -- for the two Tier-O documents with no <doc_id>.pdf
    fallback, that made a single Cancel click during a reprocess unrecoverable
    data loss.

    Tier-F is not addressable here: get_operator_item returns None for a
    Tier-F doc_id, so this is a 404 like the sibling Tier-O-only mutation
    routes above (status/bereich/card/meta/delete).
    """
    item = kl.get_operator_item(doc_id)
    if item is None:
        return jsonify({"error": f"No Tier-O item '{doc_id}'"}), 404

    originals_dir = Path(config.KNOWLEDGE_ORIGINALS_DIR) / "operator"
    raw_md_path = originals_dir / f"{doc_id}.raw.md"
    pdf_path = originals_dir / f"{doc_id}.pdf"
    if raw_md_path.exists():
        src_md, src_pdf = raw_md_path, None
    elif pdf_path.exists():
        src_md, src_pdf = None, pdf_path
    else:
        return jsonify({
            "error": (f"No stored source for '{doc_id}' — neither "
                      f"{raw_md_path.name} nor {pdf_path.name} found under "
                      f"{originals_dir}; cannot re-analyze."),
        }), 404

    # --- Stage A on the stored source (UCD-131): deterministic re-check of an
    # EXISTING document's stored PDF — embedded files / launch actions could
    # have slipped in before this gate existed; the curated text-layer lists
    # apply equally. The hash INDEX is deliberately NOT consulted here:
    # re-analysing an existing document is the operator's explicit way around
    # it (working basis while the UCD-124 decision is open). A blocked-hash
    # entry still rejects.
    if src_pdf is not None:
        try:
            stored = src_pdf.read_bytes()
        except OSError as e:
            return jsonify({"error": f"Stored source unreadable: {e}"}), 500
        reason, stored_hash = upload_gate.gate_stored_pdf(stored)
        if reason is not None:
            upload_gate.audit_rejection(stored_hash, reason, "knowledge/reprocess")
            return jsonify({"error": upload_gate.reject_message(reason)}), 400

    sparten = ", ".join(item.get("sparten") or [])
    themen = ", ".join(item.get("themen") or [])
    year_raw = str(item.get("jahr", "") or "").strip()
    try:
        year_val = int(year_raw) if year_raw else None
    except ValueError:
        year_val = None

    job_id = jobs.enqueue_ingest(
        doc_id=doc_id,
        title=item.get("titel", "") or "",
        lizenz=item.get("lizenz", "") or "",
        source_pdf=src_pdf,
        source_md=src_md,
        autor=item.get("autor", "") or "",
        year=year_val,
        lang="",  # sprache is re-detected fresh on every reprocess (Defect 1c) -- never carry the stale value forward
        url=item.get("url", "") or "",
        sparten=sparten,
        themen=themen,
        bereich=item.get("bereich", "") or "",
        hinweis=item.get("hinweis", "") or "",
        status=item.get("status", "") or "draft",
        # This run's <doc_id>.md and raw.md PRE-DATE it (the existing analysis
        # + the stored source, resolved above) -- a cancel must remove
        # NEITHER. Only this route ever sets reprocess=True; upload_document()
        # leaves it at the enqueue_ingest default (False). See
        # _finish_cancelled's docstring for the full reasoning.
        reprocess=True,
    )
    logger.info("[KNOWLEDGE] queued reprocess job %s for doc_id=%s (source=%s)",
                job_id, doc_id, "raw.md" if src_md else "pdf")
    return jsonify({"success": True, "job_id": job_id, "doc_id": doc_id}), 200


# ---------------------------------------------------------------------------
# Glossary overrides (operator redaction)
# ---------------------------------------------------------------------------

@knowledge_bp.route("/glossary-overrides", methods=["GET"])
@require_settings_auth
def get_glossary_overrides():
    path = Path(config.KNOWLEDGE_GLOSSARY_OVERRIDES)
    if not path.exists():
        return jsonify({"overrides": {}}), 200
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return jsonify({"error": f"Could not read overrides: {e}"}), 500
    return jsonify({"overrides": data}), 200


@knowledge_bp.route("/glossary-overrides", methods=["PUT"])
@require_settings_auth
def put_glossary_overrides():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Body must be a JSON object of overrides."}), 400
    # Accept either the whole {overrides: {...}} envelope or the bare mapping.
    overrides = data.get("overrides", data)
    if not isinstance(overrides, dict):
        return jsonify({"error": "'overrides' must be an object."}), 400
    path = Path(config.KNOWLEDGE_GLOSSARY_OVERRIDES)
    try:
        _atomic_write_json(path, overrides)
    except OSError as e:
        return jsonify({"error": f"Could not write overrides: {e}"}), 500
    rc, log = _reindex_sync()
    return jsonify({"success": True, "count": len(overrides),
                    "reindex_rc": rc, "reindex_log": log}), 200


# ---------------------------------------------------------------------------
# Reindex
# ---------------------------------------------------------------------------

@knowledge_bp.route("/reindex", methods=["POST"])
@require_settings_auth
def reindex():
    rc, log = _reindex_sync()
    status = 200 if rc == 0 else 500
    return jsonify({"success": rc == 0, "returncode": rc, "log": log}), status


def _reindex_sync():
    """Rebuild the FTS index synchronously (build_knowledge_index.py is fast and
    stdlib-only). Returns (returncode, log_tail). A missing interpreter is a
    deployment failure reported as one line, not a crash."""
    interp = Path(config.KNOWLEDGE_INDEX_PYTHON)
    script = Path(config.KNOWLEDGE_INDEX_SCRIPT)
    if not interp.exists():
        msg = (f"index interpreter not found at {interp} (deployment). "
               "Set KNOWLEDGE_INDEX_PYTHON to the devserver venv python.")
        logger.warning("[KNOWLEDGE] %s", msg)
        return 1, [msg]
    # Pass the configured paths explicitly so the reindex honours any config
    # override (the script's own defaults coincide with these in production).
    cmd = [
        str(interp), str(script),
        "--db", str(config.KNOWLEDGE_INDEX_DB),
        "--library", str(config.KNOWLEDGE_LIBRARY_DIR),
        "--tier-o", str(config.KNOWLEDGE_TIER_O_DIR),
        "--glossary-overrides", str(config.KNOWLEDGE_GLOSSARY_OVERRIDES),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=600,
            env=os.environ.copy(),
        )
    except Exception as e:  # noqa: BLE001
        logger.error("[KNOWLEDGE] reindex launch failed: %s", e)
        return 1, [f"reindex launch failed: {e}"]
    out = (proc.stdout or "") + (proc.stderr or "")
    log = [ln for ln in out.splitlines() if ln.strip()][-20:]
    return proc.returncode, log


def _atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
