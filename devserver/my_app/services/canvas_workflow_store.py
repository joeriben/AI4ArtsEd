"""
Canvas Workflow Store — durable persistence for Resona's STRATEGY REPERTOIRE.

Formerly a flat one-file-per-graph store; now a versioned strategy repertoire.
One JSON file per STRATEGY under exports/json/canvas_workflows/, id stable across
versions, mirroring the storage idiom of resona_memory.py (module-level LOCK, id
sanitization, exports/json root, indent=2 + ensure_ascii=False).

A strategy is a proven apparatus the group returns to: an expressive title,
a line on what it is for, an application type, and a list of versions. Each
version carries an EXPANDED, executor-ready graph (the route/tool validates and
expands via canvas_graph_authoring.validate_and_expand before saving), a memo
(why built / what changed and why), and version-bound feedback (observations
from the room, pinned to the version that ran).

File shape (<id>.json):
  {
    "id": "cw_<uuid8>",
    "title": str,                  # expressive, Resona's own handle
    "description": str,            # what it is / when to reach for it
    "application_type": str,       # free string <=40, e.g. "vergleich"
    "author": str,                 # "resona"
    "created_at": ISO,             # first version's date
    "updated_at": ISO,             # bumped on revise/feedback
    "versions": [
      {"version": 1,
       "workflow": {"nodes": [...], "connections": [...]},
       "created_at": ISO,
       "memo": str|null,           # v1: why built (optional); v>=2: required
       "feedback": [ {"ts": ISO, "note": str}, ... ]},
      ...
    ]
  }

Legacy (yesterday's flat) files with a top-level "workflow" and no "versions"
are wrapped on load (migrate-on-load); the migrated shape is persisted back on
the next write, never eagerly.

Pure storage, no Flask.
"""

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

logger = logging.getLogger(__name__)

# devserver/my_app/services/canvas_workflow_store.py -> parents[2] == devserver/
STORAGE_DIR = config.DEVSERVER_JSON_DIR / "canvas_workflows"

# One lock guards all strategy files — saves are infrequent (a few per session).
_LOCK = threading.Lock()

MAX_TITLE_CHARS = 120
MAX_DESCRIPTION_CHARS = 2000
MAX_APPLICATION_TYPE_CHARS = 40
MAX_MEMO_CHARS = 2000
MAX_NOTE_CHARS = 2000
MAX_VERSIONS = 50
MAX_FEEDBACK_PER_VERSION = 50

# A minted id: cw_ + 8 lowercase hex chars. Also the ONLY shape the getters
# accept, so a path-traversal id can never reach the filesystem.
_ID_RE = re.compile(r"^cw_[a-f0-9]{8}$")

_ID_SANITIZE = re.compile(r"[^A-Za-z0-9_-]")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mint_id() -> str:
    return f"cw_{uuid.uuid4().hex[:8]}"


def _safe_path(strategy_id: str) -> Optional[Path]:
    """
    Turn a strategy_id into a storage path, ONLY if it matches the minted shape
    ^cw_[a-f0-9]{8}$. Anything else (traversal, separators, wrong prefix) -> None.
    """
    if not isinstance(strategy_id, str):
        return None
    # Defense in depth: sanitize, then require the exact minted shape.
    cleaned = _ID_SANITIZE.sub("_", strategy_id)[:200]
    if not _ID_RE.match(cleaned):
        return None
    return STORAGE_DIR / f"{cleaned}.json"


def _clean_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the minimal graph shape and normalize to {nodes, connections}."""
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise ValueError("workflow must be an object with a 'nodes' list.")
    connections = workflow.get("connections", [])
    if not isinstance(connections, list):
        connections = []
    return {"nodes": workflow["nodes"], "connections": connections}


def _migrate_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrap a legacy flat record (top-level 'workflow', no 'versions') into the
    versioned strategy shape. In-memory only; callers persist on next write.
    """
    if not isinstance(rec, dict):
        return rec
    if isinstance(rec.get("versions"), list):
        return rec  # already new shape
    if "workflow" not in rec:
        return rec  # neither shape — leave as-is, let callers cope
    created = rec.get("created_at") or _now_iso()
    try:
        workflow = _clean_workflow(rec.get("workflow") or {})
    except ValueError:
        workflow = {"nodes": [], "connections": []}
    return {
        "id": rec.get("id"),
        "title": rec.get("name") or rec.get("title") or "",
        "description": rec.get("description", "") or "",
        "application_type": rec.get("application_type", "") or "",
        "author": rec.get("author", "resona") or "resona",
        "created_at": created,
        "updated_at": rec.get("updated_at") or created,
        "versions": [
            {
                "version": 1,
                "workflow": workflow,
                "created_at": created,
                "memo": None,
                "feedback": [],
            }
        ],
    }


def _load(path: Path) -> Optional[Dict[str, Any]]:
    """Read one strategy file, migrating a legacy flat shape on the way out."""
    try:
        with path.open("r", encoding="utf-8") as f:
            rec = json.load(f)
    except Exception:
        logger.warning(f"[CANVAS-WF-STORE] Failed reading {path.name}", exc_info=True)
        return None
    return _migrate_record(rec)


def _write(path: Path, record: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)



def save_strategy(
    title: str,
    workflow: Dict[str, Any],
    description: str = "",
    application_type: str = "",
    author: str = "resona",
    memo: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Persist a strategy, minting id 'cw_<uuid8>' and creating version 1.

    Validation: title non-empty <=120; description <=2000; application_type <=40;
    memo <=2000 (optional for v1). workflow must carry a 'nodes' list.

    Returns the stored record. Raises ValueError on invalid input.
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("strategy title must be a non-empty string.")
    title = title.strip()
    if len(title) > MAX_TITLE_CHARS:
        raise ValueError(f"strategy title must be at most {MAX_TITLE_CHARS} characters.")

    graph = _clean_workflow(workflow)

    if not isinstance(description, str):
        description = ""
    description = description.strip()
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise ValueError(f"description must be at most {MAX_DESCRIPTION_CHARS} characters.")

    if not isinstance(application_type, str):
        application_type = ""
    application_type = application_type.strip()
    if len(application_type) > MAX_APPLICATION_TYPE_CHARS:
        raise ValueError(
            f"application_type must be at most {MAX_APPLICATION_TYPE_CHARS} characters."
        )

    if memo is not None:
        if not isinstance(memo, str):
            memo = str(memo)
        memo = memo.strip() or None
        if memo is not None and len(memo) > MAX_MEMO_CHARS:
            raise ValueError(f"memo must be at most {MAX_MEMO_CHARS} characters.")

    if not isinstance(author, str) or not author.strip():
        author = "resona"

    now = _now_iso()
    record = {
        "id": _mint_id(),
        "title": title,
        "description": description,
        "application_type": application_type,
        "author": author.strip(),
        "created_at": now,
        "updated_at": now,
        "versions": [
            {
                "version": 1,
                "workflow": graph,
                "created_at": now,
                "memo": memo,
                "feedback": [],
            }
        ],
    }

    with _LOCK:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        path = STORAGE_DIR / f"{record['id']}.json"
        # Extremely unlikely uuid8 collision — remint rather than clobber.
        while path.exists():
            record["id"] = _mint_id()
            path = STORAGE_DIR / f"{record['id']}.json"
        _write(path, record)

    logger.info(f"[CANVAS-WF-STORE] Saved strategy {record['id']} ('{title}') v1")
    return record


def _summary(record: Dict[str, Any]) -> Dict[str, Any]:
    versions = record.get("versions") or []
    latest = versions[-1] if versions else {}
    return {
        "id": record.get("id"),
        "title": record.get("title", ""),
        "description": record.get("description", ""),
        "application_type": record.get("application_type", ""),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at") or record.get("created_at"),
        "version_count": len(versions),
        "latest_memo": latest.get("memo"),
    }


def list_strategies(
    query: Optional[str] = None,
    application_type: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Summaries of stored strategies, newest-updated first.

    query — case-insensitive substring matched against title + description.
    application_type — exact match (case-insensitive) when given.
    limit — max returned (clamped to [1, 200]).
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(limit, 200))

    q = (query or "").strip().lower()
    at = (application_type or "").strip().lower()

    records: List[Dict[str, Any]] = []
    with _LOCK:
        if not STORAGE_DIR.exists():
            return []
        for path in STORAGE_DIR.glob("cw_*.json"):
            rec = _load(path)
            if rec is None:
                continue
            if q:
                haystack = f"{rec.get('title', '')} {rec.get('description', '')}".lower()
                if q not in haystack:
                    continue
            if at:
                if (rec.get("application_type", "") or "").strip().lower() != at:
                    continue
            records.append(rec)

    records.sort(
        key=lambda r: (r.get("updated_at") or r.get("created_at") or ""),
        reverse=True,
    )
    return [_summary(r) for r in records[:limit]]


def get_strategy(
    strategy_id: str, version: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Return the full stored record for a strategy_id, or None if the id is invalid
    or no such strategy exists. The id must match ^cw_[a-f0-9]{8}$.

    If `version` is given and exists, the record additionally carries a
    convenience key "selected_version" with that version dict; otherwise
    "selected_version" is the latest version.
    """
    path = _safe_path(strategy_id)
    if path is None:
        return None
    with _LOCK:
        if not path.exists():
            return None
        record = _load(path)
    if record is None:
        return None

    versions = record.get("versions") or []
    selected = None
    if version is not None:
        for v in versions:
            if v.get("version") == version:
                selected = v
                break
    if selected is None:
        selected = versions[-1] if versions else None
    record["selected_version"] = selected
    return record


def add_version(
    strategy_id: str, workflow: Dict[str, Any], memo: str
) -> Dict[str, Any]:
    """
    Append version N+1 to an existing strategy and bump updated_at.

    memo is REQUIRED (non-empty, <=2000) — what changed and why. workflow must
    carry a 'nodes' list. Caps at MAX_VERSIONS versions.

    Returns the updated record. Raises ValueError on invalid input / missing
    strategy / cap overflow.
    """
    if not isinstance(memo, str) or not memo.strip():
        raise ValueError("memo is required when revising — say what changed and why.")
    memo = memo.strip()
    if len(memo) > MAX_MEMO_CHARS:
        raise ValueError(f"memo must be at most {MAX_MEMO_CHARS} characters.")

    graph = _clean_workflow(workflow)

    path = _safe_path(strategy_id)
    if path is None:
        raise ValueError(f"no strategy with id '{strategy_id}'.")

    with _LOCK:
        if not path.exists():
            raise ValueError(f"no strategy with id '{strategy_id}'.")
        record = _load(path)
        if record is None:
            raise ValueError(f"strategy '{strategy_id}' could not be read.")
        versions = record.get("versions") or []
        if len(versions) >= MAX_VERSIONS:
            raise ValueError(
                f"strategy '{strategy_id}' has reached the cap of {MAX_VERSIONS} versions."
            )
        next_version = (versions[-1].get("version", len(versions)) if versions else 0) + 1
        now = _now_iso()
        versions.append(
            {
                "version": next_version,
                "workflow": graph,
                "created_at": now,
                "memo": memo,
                "feedback": [],
            }
        )
        record["versions"] = versions
        record["updated_at"] = now
        _write(path, record)

    logger.info(
        f"[CANVAS-WF-STORE] Revised strategy {strategy_id} to v{next_version}"
    )
    return record


def add_feedback(
    strategy_id: str, note: str, version: Optional[int] = None
) -> Dict[str, Any]:
    """
    Append a feedback entry {ts, note} to the given version (default latest) and
    bump updated_at.

    note is REQUIRED (non-empty, <=2000). Caps at MAX_FEEDBACK_PER_VERSION per
    version.

    Returns the updated record. Raises ValueError on invalid input / missing
    strategy / missing version / cap overflow.
    """
    if not isinstance(note, str) or not note.strip():
        raise ValueError("feedback note must be a non-empty string.")
    note = note.strip()
    if len(note) > MAX_NOTE_CHARS:
        raise ValueError(f"feedback note must be at most {MAX_NOTE_CHARS} characters.")

    path = _safe_path(strategy_id)
    if path is None:
        raise ValueError(f"no strategy with id '{strategy_id}'.")

    with _LOCK:
        if not path.exists():
            raise ValueError(f"no strategy with id '{strategy_id}'.")
        record = _load(path)
        if record is None:
            raise ValueError(f"strategy '{strategy_id}' could not be read.")
        versions = record.get("versions") or []
        if not versions:
            raise ValueError(f"strategy '{strategy_id}' has no versions to annotate.")

        target = None
        if version is not None:
            for v in versions:
                if v.get("version") == version:
                    target = v
                    break
            if target is None:
                raise ValueError(
                    f"strategy '{strategy_id}' has no version {version}."
                )
        else:
            target = versions[-1]

        feedback = target.get("feedback")
        if not isinstance(feedback, list):
            feedback = []
        if len(feedback) >= MAX_FEEDBACK_PER_VERSION:
            raise ValueError(
                f"version {target.get('version')} has reached the cap of "
                f"{MAX_FEEDBACK_PER_VERSION} feedback entries."
            )
        now = _now_iso()
        feedback.append({"ts": now, "note": note})
        target["feedback"] = feedback
        record["updated_at"] = now
        _write(path, record)

    logger.info(
        f"[CANVAS-WF-STORE] Feedback on strategy {strategy_id} "
        f"v{target.get('version')}"
    )
    return record


# ---------------------------------------------------------------------------
# Thin backward-compatible aliases.
#
# canvas_routes.py has been updated to the new names, but resona_memory-style
# callers and older imports may still reach for these. They operate on the new
# versioned records: save_workflow == save_strategy(title=name); list_workflows
# and get_workflow return records unchanged (additive keys are harmless).
# ---------------------------------------------------------------------------

def save_workflow(
    name: str,
    workflow: Dict[str, Any],
    description: str = "",
    author: str = "resona",
) -> Dict[str, Any]:
    return save_strategy(
        title=name, workflow=workflow, description=description, author=author
    )


def list_workflows(query: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    return list_strategies(query=query, limit=limit)


def get_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
    return get_strategy(workflow_id)
