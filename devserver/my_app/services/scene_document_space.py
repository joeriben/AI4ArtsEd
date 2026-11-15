"""Sitzungsbezogener Dokumentraum für die Zusammenfassungen im Flow.

A PDF a group brings into the flow is NOT a Tier-O operator document — no
draft/publish, no library. It is summarised the way the library condenses a
document (scene_ingest_service), and the summary hangs on the session (the
canvas session id, used as the journal id). The session id carries the date,
so a session ends at midnight UTC; the summary stays stored, and
`scene_ingest_service.take_summary` finds it again for the same file.
Storage layout (all gitignored under devserver exports, same idiom as the
knowledge uploads):

    exports/scene_documents/<journal_id>/<doc_id>/summary.json     # Profil, Abschnitte, Glossar
    exports/scene_documents/<journal_id>/<doc_id>/document.json    # Metadaten + provenance

A document stored before 2026-09-28 carries capsules.json/segments.json
instead (image-prompt capsules, removed that day). It has no summary.json,
counts as absent here, and a new run of the same file replaces it.

NEVER stored here: PDF raw bytes, full-text MD (both live only in the FIFO
worker's job-scoped workdir and are deleted at job end, or at the next backend
start for a job a restart ended). Deleting a journal (resona delete route)
drops its document space with it. A device's first journal carries the device
id, which is that day's flow session id, so Resona's "New dialog" reaches the
space of that flow session too.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import EXPORTS_DIR
from my_app.services.safety_level_resolver import SAFETY_LEVELS_STRICTEST_FIRST

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


def doc_id_for(raw_hash: str) -> str:
    """The id a document has in every session: it comes from the file's bytes."""
    return f"doc-{raw_hash[:12]}"


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


def _read_stored(d: Path) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """A document's metadata and summary, read as one: `store_document` writes
    the two under the same lock, so a reader never pairs the metadata of one
    version with the summary of another. None where either file is missing or
    unreadable."""
    with _LOCK:
        try:
            meta = json.loads((d / "document.json").read_text(encoding="utf-8"))
            summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return meta, summary


def get_document(journal_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """One document's stored view: meta + the summary the card shows. Parts
    the safety check withheld were never stored; `n_withheld` counts them.
    None for a document the space does not hold, and for one stored in the
    capsule format before 2026-09-28 (no summary.json)."""
    d = _doc_dir(journal_id, doc_id)
    stored = None if d is None else _read_stored(d)
    if stored is None:
        return None
    meta, summary = stored
    return {
        "doc_id": doc_id,
        "meta": meta,
        "summary": summary,
        "n_withheld": int(meta.get("n_withheld", 0)),
    }


def find_summary(raw_hash: str, *, lang: str,
                 safety_level: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Metadata and summary of a stored summary of exactly this file in `lang`,
    from any session, or None when there is none a session at `safety_level`
    can start from.

    The search runs over all sessions because the session id carries the date:
    searching one session found nothing the next day, and one browser had the
    same PDF summarised on 30.10., 01.11., 05.11. and 06.11. It answers only to
    someone who hands in the file.

    A record without a level we know does not count. Neither does one from a
    stricter level that withheld parts: this session may see what that copy
    lost, and a new run gives it that. Among the others the one from the loosest
    level is taken, because it withheld the least. What of it may be shown here
    is the check's to say (`scene_ingest_service.take_summary`).
    """
    best: Optional[Tuple[Dict[str, Any], Dict[str, Any]]] = None
    best_rank = -1
    session_rank = SAFETY_LEVELS_STRICTEST_FIRST.index(safety_level)
    for meta_p in SCENE_DOCUMENTS_DIR.glob(f"*/{doc_id_for(raw_hash)}/document.json"):
        stored = _read_stored(meta_p.parent)
        if stored is None:
            continue
        meta = stored[0]
        level = meta.get("safety_level")
        if (meta.get("doc_hash") != raw_hash or meta.get("analysis_lang") != lang
                or level not in SAFETY_LEVELS_STRICTEST_FIRST):
            continue
        rank = SAFETY_LEVELS_STRICTEST_FIRST.index(level)
        if rank < session_rank and int(meta.get("n_withheld", 0)) > 0:
            continue
        if rank > best_rank:
            best, best_rank = stored, rank
    return best


def checked_for(meta: Dict[str, Any], safety_level: str) -> bool:
    """Whether a stored document was checked at `safety_level` or a stricter
    one: a summary checked at a looser level was never asked this level's
    question."""
    level = meta.get("safety_level")
    if level not in SAFETY_LEVELS_STRICTEST_FIRST \
            or safety_level not in SAFETY_LEVELS_STRICTEST_FIRST:
        return False
    return (SAFETY_LEVELS_STRICTEST_FIRST.index(level)
            <= SAFETY_LEVELS_STRICTEST_FIRST.index(safety_level))


def stricter_level(a: str, b: str) -> str:
    """The stricter of two known levels."""
    return min(a, b, key=SAFETY_LEVELS_STRICTEST_FIRST.index)


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
    """Drop a whole session's document space (journal delete hook). A session
    that handed in the same file keeps its own copy. Returns the number of
    removed document dirs."""
    jd = _journal_dir(journal_id)
    if jd is None or not jd.exists():
        return 0
    import shutil

    n = len([p for p in jd.iterdir() if p.is_dir()])
    shutil.rmtree(jd, ignore_errors=True)
    return n


def delete_document(journal_id: str, doc_id: str) -> bool:
    """Remove ONE document's space entry. A fresh upload of the same file is
    summarised again unless another session holds a summary of it. Returns True
    when something was removed."""
    d = _doc_dir(journal_id, doc_id)
    if d is None or not d.exists():
        return False
    import shutil

    shutil.rmtree(d, ignore_errors=True)
    return True


