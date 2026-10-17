"""Every apparatus Resona authors, written to disk the moment she authors it.

Every supposedly built run is exported, in a Canvas-importable format, so
that a run which fails to appear can be traced to the UI or to the backend.

So this writes at the ONE place where the authoring is a fact — the tool handler,
before anything downstream can lose it — and it separates the three cases the
board cannot tell apart:

  * a file under canvas_graph_runs/ = a graph was AUTHORED and accepted. It is a
    CanvasWorkflow, laid out and enveloped, and canvasStore.loadWorkflow opens
    it — the function the Canvas's own Import Workflow dialog calls, once the
    file has been fetched off this host.
  * a file under canvas_graph_runs/rejected/ = the model reached for the tool and
    was refused — by the validator, or for a missing title. The reason is in the
    file. Not a CanvasWorkflow, and deliberately not importable: there is no
    workflow to import.
  * no file at all = the model never called the tool, or the write itself failed
    (which says so in the log, as [CANVAS-EXPORT]).

What a file does NOT say is that the run succeeded. It is written when the
apparatus is authored and never touched again; whether the run then rendered
anything is the run record's and the journal's business, and `resona.intent_id`
is the key both of them use.

Storage idiom follows canvas_workflow_store.py (module-level LOCK, exports/json
root, indent=2 + ensure_ascii=False). Nothing here raises: a turn must never fail
because a trace could not be written.
"""

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import config

from my_app.services.canvas_graph_authoring import to_canvas_workflow

logger = logging.getLogger(__name__)

# devserver/my_app/services/canvas_graph_export.py -> parents[2] == devserver/
# `exports/` is ignored by git (.gitignore:71), which is where a trace of what a
# room built belongs.
EXPORT_DIR = config.DEVSERVER_JSON_DIR / "canvas_graph_runs"
REJECTED_DIR = EXPORT_DIR / "rejected"

_LOCK = threading.Lock()

def _slug(title: str) -> str:
    """A filename from a title, in whatever script the room writes.

    `str.isalnum()` rather than an ASCII class: stripping to [a-z0-9] turned
    every Cyrillic, Korean, Greek and Chinese title into the same word, and this
    platform ships uk and ko. Two apparatus in one round would then have written
    one file. The uniqueness token below carries the guarantee either way; this
    only keeps the name readable.
    """
    out = []
    dashed = True
    for ch in (title or ""):
        if ch.isalnum():
            out.append(ch.lower())
            dashed = False
        elif not dashed:
            out.append("-")
            dashed = True
    return ("".join(out).strip("-")[:48] or "apparatus")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _filename(title: str, token: Optional[str] = None) -> str:
    """Stamp, title and a token that cannot repeat.

    The stamp resolves to the whole second and one assistant round runs its tool
    calls in a tight loop, so two apparatus authored in the same second is an
    ordinary path, not a contrived one. Without the token the second file
    overwrote the first, silently, and the count on disk undercounted what the
    room built — in the rejected directory, where the file's whole content is
    the reason, the first reason simply vanished.
    """
    return f"{_stamp()}_{_slug(title)}_{token or uuid.uuid4().hex[:8]}.json"


def _write(directory: Path, filename: str, body: Dict[str, Any]) -> Optional[Path]:
    try:
        with _LOCK:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / filename
            path.write_text(json.dumps(body, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        return path
    except Exception as e:
        logger.warning(f"[CANVAS-EXPORT] could not write {filename}: {e}")
        return None


def record_accepted(title: str, payload: Dict[str, Any],
                    motivation: Optional[str] = None,
                    summary: Optional[str] = None,
                    intent_id: Optional[str] = None,
                    device_id: Optional[str] = None) -> Optional[Path]:
    """Write the accepted graph as a CanvasWorkflow. Returns the path, or None."""
    try:
        described = " — ".join(p for p in (summary, motivation) if p)
        workflow = to_canvas_workflow(
            payload,
            name=title or "Apparatus",
            description=described,
            workflow_id=intent_id or f"cg_{uuid.uuid4().hex[:8]}",
        )
        # Provenance rides INSIDE the workflow, under a key of its own: the
        # Canvas reads the fields it knows and carries the rest along, so the
        # file stays one importable object rather than a wrapper around one.
        workflow["resona"] = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "intent_id": intent_id,
            "device_id": device_id,
            "motivation": motivation,
            "summary": summary,
        }
    except Exception as e:
        logger.warning(f"[CANVAS-EXPORT] could not lay out '{title}': {e}")
        return None
    path = _write(EXPORT_DIR, _filename(title, intent_id), workflow)
    if path:
        logger.info(f"[CANVAS-EXPORT] apparatus '{title}' written to {path}")
    return path


def record_rejected(title: str, graph: Any, error: str,
                    device_id: Optional[str] = None) -> Optional[Path]:
    """Write a refused graph, with the reason. Not a CanvasWorkflow."""
    body = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "title": title or None,
        "device_id": device_id,
        "error": error,
        "authored_graph": graph,
    }
    path = _write(REJECTED_DIR, _filename(title), body)
    if path:
        logger.info(f"[CANVAS-EXPORT] refused apparatus '{title}' written to {path}: {error}")
    return path
