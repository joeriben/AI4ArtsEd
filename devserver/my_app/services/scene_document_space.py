"""Sitzungsbezogener Dokumentraum für die Zusammenfassungen im Flow.

A PDF a group brings into the flow is NOT a Tier-O operator document — no
draft/publish, no library. It is summarised the way the library condenses a
document (scene_ingest_service), and the summary hangs on the session (the
canvas session id, used as the journal id) and VERFÄLLT MIT DER SITZUNG.
Storage layout (all gitignored under devserver exports, same idiom as the
knowledge uploads):

    exports/scene_documents/<journal_id>/<doc_id>/summary.json     # Profil, Abschnitte, Glossar
    exports/scene_documents/<journal_id>/<doc_id>/document.json    # Metadaten + provenance

A document stored before 2026-09-28 carries capsules.json/segments.json
instead (image-prompt capsules, removed that day). It has no summary.json,
counts as absent here, and a new run of the same file replaces it.

NEVER stored here: PDF raw bytes, full-text MD (both live only in the FIFO
worker's job-scoped workdir and are deleted at job end). Deleting
the journal (resona delete route) drops its document space with it — the
space dies with the session.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import EXPORTS_DIR

SCENE_DOCUMENTS_DIR = EXPORTS_DIR / "scene_documents"

_ID_RE = re.compile(r"[^a-z0-9-]+")
_LOCK = threading.Lock()


def _safe_id(raw: str) -> Optional[str]:
    """Sanitise a journal/doc id to the kebab class used across the intake
    paths. Returns None for unusable ids (never a path with weird bytes)."""
    s = (raw or "").strip().lower()
    s = _ID_RE.sub("-", s).strip("-")
    if not s or len(s) > 120:
        return None
    return s


def _journal_dir(journal_id: str) -> Optional[Path]:
    j = _safe_id(journal_id)
    if j is None:
        return None
    return SCENE_DOCUMENTS_DIR / j


def _doc_dir(journal_id: str, doc_id: str) -> Optional[Path]:
    jd = _journal_dir(journal_id)
    d = _safe_id(doc_id)
    if jd is None or d is None:
        return None
    return jd / d


def store_document(journal_id: str, doc_id: str, *,
                   summary: Dict[str, Any],
                   meta: Dict[str, Any]) -> Optional[Path]:
    """Persist one summarised document into the session space: the summary
    (profile, sections, glossary) and the metadata/provenance JSON. The files
    of the capsule format a document of the same id may still carry go.
    Returns the document dir or None on an unusable id (never raises on id
    problems — the caller turns None into an error)."""
    d = _doc_dir(journal_id, doc_id)
    if d is None:
        return None
    with _LOCK:
        d.mkdir(parents=True, exist_ok=True)
        for stale in ("capsules.json", "segments.json"):
            try:
                (d / stale).unlink()
            except FileNotFoundError:
                pass
        (d / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (d / "document.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def get_document(journal_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """One document's stored view: meta + the summary the card shows. Parts
    the safety check withheld were never stored; `n_withheld` counts them.
    None for a document the space does not hold, and for one stored in the
    capsule format before 2026-09-28 (no summary.json)."""
    d = _doc_dir(journal_id, doc_id)
    if d is None or not (d / "document.json").exists() \
            or not (d / "summary.json").exists():
        return None
    meta = json.loads((d / "document.json").read_text(encoding="utf-8"))
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    return {
        "doc_id": doc_id,
        "meta": meta,
        "summary": summary,
        "n_withheld": int(meta.get("n_withheld", 0)),
    }


def list_documents(journal_id: str) -> List[Dict[str, Any]]:
    """All summarised documents of one session (meta + counts only, no
    summary bodies — the surface lists, and reads single documents)."""
    jd = _journal_dir(journal_id)
    if jd is None or not jd.exists():
        return []
    out: List[Dict[str, Any]] = []
    for d in sorted(jd.iterdir()):
        meta_p = d / "document.json"
        summary_p = d / "summary.json"
        if not meta_p.exists() or not summary_p.exists():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        try:
            n_sections = len(json.loads(summary_p.read_text(encoding="utf-8")).get("sections", []))
        except (OSError, json.JSONDecodeError, AttributeError):
            n_sections = 0
        out.append({
            "doc_id": d.name,
            "title": meta.get("title", ""),
            "n_sections": n_sections,
            "n_withheld": int(meta.get("n_withheld", 0)),
            "analyzed_at": meta.get("analyzed_at", ""),
        })
    return out


def delete_journal_space(journal_id: str) -> int:
    """Drop a whole session's document space (journal delete hook — the space
    verfällt mit der Sitzung). Returns the number of removed document dirs."""
    jd = _journal_dir(journal_id)
    if jd is None or not jd.exists():
        return 0
    import shutil

    n = len([p for p in jd.iterdir() if p.is_dir()])
    shutil.rmtree(jd, ignore_errors=True)
    return n


def delete_document(journal_id: str, doc_id: str) -> bool:
    """Remove ONE document's space entry (fresh upload of the same file becomes
    analysable again). Returns True when something was removed."""
    d = _doc_dir(journal_id, doc_id)
    if d is None or not d.exists():
        return False
    import shutil

    shutil.rmtree(d, ignore_errors=True)
    return True


