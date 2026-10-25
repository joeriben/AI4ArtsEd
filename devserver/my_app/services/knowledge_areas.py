"""
Knowledge Areas (Wissensbereiche) — operator-facing sparten of the knowledge
library (Settings curation, MoJo-Diskursräume analogue).

An "area" (Bereich) is a lightweight, operator-defined bucket that groups the
Tier-O documents an operator uploaded together with an optional free-text
`kommentar` — a note for the agent explaining WHY these texts were uploaded /
why this area exists. The area id tags each document's front-matter (`bereich:`)
and travels into the FTS index as a facet, so the curation UI can filter by area
and Resona's lookup can surface the operator's note as neutral data-context.

Storage: one flat JSON under the shared knowledge/exports root
(exports/json/knowledge_areas.json), guarded by a module lock with an atomic
write — the same idiom as resona_memory / canvas_workflow_store. Shape:

    {"areas": [{"id": "<sanitized>", "name": str, "kommentar": str,
                "created": "<iso-8601>"}]}

This module owns ONLY the area records (CRUD). Document counts per area and the
deletion-safety check ("an area with documents cannot be deleted") are computed
by the routes from the FTS index, because the index is the single source of
truth for which documents currently carry which `bereich`.

The UNESCO pseudo-area (id "unesco", fixed=True) is NOT stored here — it is a
view-only sentinel the routes add to the GET /areas response (it maps to the
Tier-F corpus, which is committed and never operator-editable).
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

import config

logger = logging.getLogger(__name__)

# my_app/services/knowledge_areas.py -> parents[2] == devserver/  (same STORAGE
# root idiom as resona_memory / knowledge_library).
STORE_PATH = config.DEVSERVER_JSON_DIR / "knowledge_areas.json"

# The fixed UNESCO pseudo-area id. Reserved: it can never be created, edited,
# deleted, or used as an upload target (the routes enforce that).
UNESCO_ID = "unesco"

MAX_NAME_CHARS = 120
MAX_KOMMENTAR_CHARS = 2000

# id sanitiser: the same lowercase-alnum-and-hyphen character class the ingest
# kebab-slug and the doc_id sanitiser use, so an area id is a safe filename /
# front-matter / facet token. Collisions get a -2, -3, … suffix.
_ID_SAFE = re.compile(r"[^a-z0-9]+")

# One lock guards the single store file — area mutations are rare (a handful per
# curation session), so one lock is simpler than anything finer-grained.
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_id(name: str) -> str:
    """Turn an area name into a safe id token (lowercase alnum + hyphens)."""
    s = _ID_SAFE.sub("-", (name or "").lower()).strip("-")
    return s or "bereich"


# ---------------------------------------------------------------------------
# Load / save (atomic, locked)
# ---------------------------------------------------------------------------

def _load() -> List[Dict]:
    if not STORE_PATH.exists():
        return []
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("[KNOWLEDGE-AREAS] could not read %s: %s", STORE_PATH, e)
        return []
    areas = data.get("areas") if isinstance(data, dict) else None
    return areas if isinstance(areas, list) else []


def _save(areas: List[Dict]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(STORE_PATH.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"areas": areas}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(STORE_PATH))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Public CRUD
# ---------------------------------------------------------------------------

def list_areas() -> List[Dict]:
    """All stored operator areas (excludes the UNESCO pseudo-area), oldest
    first (creation order)."""
    with _LOCK:
        return [dict(a) for a in _load()]


def get_area(area_id: str) -> Optional[Dict]:
    """One stored operator area by id, or None. Never returns the UNESCO
    sentinel (it is not a stored record)."""
    aid = (area_id or "").strip()
    if not aid:
        return None
    with _LOCK:
        for a in _load():
            if a.get("id") == aid:
                return dict(a)
    return None


def create_area(name: str, kommentar: str = "") -> Dict:
    """Create an area from a display name. The id is sanitised from the name and
    made collision-free (-2, -3, …). Raises ValueError on an empty name or on a
    name that resolves to the reserved UNESCO id."""
    name = (name or "").strip()[:MAX_NAME_CHARS]
    if not name:
        raise ValueError("Bereichsname darf nicht leer sein.")
    kommentar = (kommentar or "").strip()[:MAX_KOMMENTAR_CHARS]
    base = sanitize_id(name)
    if base == UNESCO_ID:
        raise ValueError(f"Der Bezeichner '{UNESCO_ID}' ist reserviert.")
    with _LOCK:
        areas = _load()
        taken = {a.get("id") for a in areas} | {UNESCO_ID}
        candidate = base
        n = 1
        while candidate in taken:
            n += 1
            candidate = f"{base}-{n}"
        record = {"id": candidate, "name": name, "kommentar": kommentar,
                  "created": _now()}
        areas.append(record)
        _save(areas)
    return dict(record)


def update_area(area_id: str, *, name: Optional[str] = None,
                kommentar: Optional[str] = None) -> Optional[Dict]:
    """Update an area's name and/or kommentar IN PLACE (the id is stable, so the
    documents tagged with it keep their `bereich`). Passing name=None /
    kommentar=None leaves that field unchanged; passing an empty kommentar
    string clears it. Returns the updated record, or None if no such area. Raises
    ValueError on the reserved UNESCO id or an empty new name."""
    aid = (area_id or "").strip()
    if aid == UNESCO_ID:
        raise ValueError("Der UNESCO-Bereich ist fest und kann nicht bearbeitet werden.")
    with _LOCK:
        areas = _load()
        for a in areas:
            if a.get("id") == aid:
                if name is not None:
                    new_name = name.strip()[:MAX_NAME_CHARS]
                    if not new_name:
                        raise ValueError("Bereichsname darf nicht leer sein.")
                    a["name"] = new_name
                if kommentar is not None:
                    a["kommentar"] = kommentar.strip()[:MAX_KOMMENTAR_CHARS]
                _save(areas)
                return dict(a)
    return None


def delete_area(area_id: str) -> bool:
    """Delete an area record. Returns True if it existed and was removed, False
    if there was no such area. Raises ValueError on the reserved UNESCO id.

    NOTE: this does NOT check for attached documents — the routes do that
    (against the index) BEFORE calling here, because the index is the source of
    truth for `bereich` membership."""
    aid = (area_id or "").strip()
    if aid == UNESCO_ID:
        raise ValueError("Der UNESCO-Bereich ist fest und kann nicht gelöscht werden.")
    with _LOCK:
        areas = _load()
        remaining = [a for a in areas if a.get("id") != aid]
        if len(remaining) == len(areas):
            return False
        _save(remaining)
    return True


def area_exists(area_id: str) -> bool:
    """True if area_id is a real, usable upload target: a stored operator area.
    The reserved UNESCO id is NOT a usable target and returns False here."""
    aid = (area_id or "").strip()
    if not aid or aid == UNESCO_ID:
        return False
    return get_area(aid) is not None
