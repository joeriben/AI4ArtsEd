"""Sitzungsbezogener Dokumentraum für die Szenen-Kapsel-Pipeline (UCD-132).

UCD-124 plan §4: a PDF a group brings into the flow is NOT a Tier-O operator
document — no draft/publish, no library. The document space hangs on the
session (resona journal id, the idiom of the resona routes; a kursbezogener
Raum is a later Ausbaustufe, plan §9.4) and VERFÄLLT MIT DER SITZUNG. Storage
layout (all gitignored under devserver exports, same idiom as the knowledge
uploads):

    exports/scene_documents/<journal_id>/<doc_id>/capsules.json    # Kapseln
    exports/scene_documents/<journal_id>/<doc_id>/segments.json     # Segment-Verdichtungen
    exports/scene_documents/<journal_id>/<doc_id>/document.json    # Metadaten + provenance

NEVER stored here: PDF raw bytes, full-text MD (plan §6 — both live only in
the FIFO worker's job-scoped workdir and are deleted at job end). Deleting
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
                   capsules: List[Dict[str, Any]],
                   segments: List[Dict[str, Any]],
                   meta: Dict[str, Any]) -> Optional[Path]:
    """Persist one analysed document into the session space. Writes capsules,
    segments and the metadata/provenance JSON. Returns the document dir or
    None on an unusable id (never raises on id problems — the caller turns
    None into a 400)."""
    d = _doc_dir(journal_id, doc_id)
    if d is None:
        return None
    with _LOCK:
        d.mkdir(parents=True, exist_ok=True)
        (d / "capsules.json").write_text(
            json.dumps(capsules, ensure_ascii=False, indent=2), encoding="utf-8")
        (d / "segments.json").write_text(
            json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
        (d / "document.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def get_document(journal_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """One document's stored view: meta + capsule count + capsule/segment
    lists (the agent question base). The stored segment entries carry ONLY
    the kept (pass) digests; flagged segments were never stored (count-only,
    plan §3.5)."""
    d = _doc_dir(journal_id, doc_id)
    if d is None or not (d / "document.json").exists():
        return None
    meta = json.loads((d / "document.json").read_text(encoding="utf-8"))
    capsules = json.loads((d / "capsules.json").read_text(encoding="utf-8"))
    segments = json.loads((d / "segments.json").read_text(encoding="utf-8"))
    return {
        "doc_id": doc_id,
        "meta": meta,
        "capsules": capsules,
        "n_capsules": len(capsules),
        "n_flagged_segments": int(meta.get("n_flagged_segments", 0)),
        "n_discarded_capsules": int(meta.get("n_discarded_capsules", 0)),
        "segments": segments,
    }


def list_documents(journal_id: str) -> List[Dict[str, Any]]:
    """All documents of one session (meta + counts only, no capsule bodies —
    the surface lists; the agent fetches single documents)."""
    jd = _journal_dir(journal_id)
    if jd is None or not jd.exists():
        return []
    out: List[Dict[str, Any]] = []
    for d in sorted(jd.iterdir()):
        meta_p = d / "document.json"
        if not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        caps_p = d / "capsules.json"
        n_caps = 0
        if caps_p.exists():
            try:
                n_caps = len(json.loads(caps_p.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                n_caps = 0
        out.append({
            "doc_id": d.name,
            "title": meta.get("title", ""),
            "n_capsules": n_caps,
            "n_flagged_segments": int(meta.get("n_flagged_segments", 0)),
            "n_discarded_capsules": int(meta.get("n_discarded_capsules", 0)),
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


