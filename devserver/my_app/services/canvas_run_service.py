"""
Canvas Run Service — background-job wrapper around CanvasWorkflowExecutor.

Why this exists (the failure class it fixes):
    Canvas graph runs used to live INSIDE the request generator of
    /api/canvas/execute-stream. When the backend process died mid-run (a
    restart), the SSE stream tore, the client fell into FAILED, and the
    in-flight run was orphaned — even though the recorder had already written
    every finished node's output to disk. The stream WAS the run: kill the
    stream, lose the run.

    This service pulls the run OUT of the request. Each run becomes a daemon
    worker thread registered by run_id. Every executor event is:
      1. appended to an in-memory ring buffer (fast tail for live readers), and
      2. appended to events.jsonl in the recorder run folder (one JSON line per
         event, with a running index) — so the event history is restart-fest
         READABLE, and
    the coarse job state (running/complete/error/interrupted + last event index)
    is written to status.json in the same folder via an ATOMIC write.

    The SSE route becomes a TAIL over this: a reader can attach at any event
    index (?after=<n> / Last-Event-ID), replay what it missed from the buffer
    (or from events.jsonl if the job left memory), then follow live. Reconnect
    is therefore lossless within a live process.

    The executor itself (canvas_executor.CanvasWorkflowExecutor) is UNCHANGED —
    this is only the execution shell around it.

Scope note (Auftrag D1): a torn run is recovered as PARTIAL (finished nodes are
    on disk, reachable via /api/media/image/<run_id>). This service does NOT
    auto-resume the remaining nodes after a restart — that is documented
    follow-up work (workflow.json + partial entities + events.jsonl make it
    possible). See mark_orphans_interrupted().

Registry is in-memory only (does NOT survive a devserver restart); the persisted
    artifacts (events.jsonl, status.json, metadata.json, final/) do.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from my_app.services.canvas_executor import CanvasWorkflowExecutor
from my_app.services.canvas_recorder import get_canvas_recorder, cleanup_canvas_recorder
from my_app.services.pipeline_recorder import generate_run_id

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

EVENTS_FILENAME = "events.jsonl"
STATUS_FILENAME = "status.json"

# Terminal job states. Once a job reaches one of these, no more live events come.
TERMINAL_STATES = {"complete", "error", "interrupted"}

# Cap the in-memory event buffer per run so a pathological graph can't grow it
# without bound. events.jsonl on disk stays complete regardless; a reader that
# needs events older than the buffer window reads them back from the file.
MAX_BUFFER_EVENTS = 5000

# ── registry ─────────────────────────────────────────────────────────────────

# run_id -> job dict. Guarded by _JOBS_LOCK.
#   state:        running | complete | error | interrupted
#   events:       List[dict]  (ring buffer; each event has "_i": running index)
#   n_events:     int         (total events ever produced == next index)
#   cond:         threading.Condition  (bound to _JOBS_LOCK; notified per event)
#   run_folder:   str
#   error:        Optional[str]
#   started_at / finished_at: iso strings
_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
_JOBS_COND = threading.Condition(_JOBS_LOCK)


def _now() -> str:
    return datetime.now().isoformat()


# ── status.json (atomic) ─────────────────────────────────────────────────────

def _status_path(run_folder: Path) -> Path:
    return Path(run_folder) / STATUS_FILENAME


def _write_status_file(run_folder: Path, state: str, n_events: int,
                       error: Optional[str] = None,
                       started_at: Optional[str] = None,
                       finished_at: Optional[str] = None) -> None:
    """Atomically write status.json (write temp + os.replace). Best effort:
    a status write must never take down a run."""
    try:
        payload = {
            "state": state,
            "n_events": n_events,
            "error": error,
            "started_at": started_at,
            "finished_at": finished_at,
            "updated_at": _now(),
        }
        p = _status_path(run_folder)
        tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)
    except Exception as e:  # pragma: no cover - disk edge
        logger.warning("[CANVAS-RUN] status write failed for %s: %s", run_folder, e)


def _read_status_file(run_folder: Path) -> Optional[Dict[str, Any]]:
    try:
        p = _status_path(run_folder)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # pragma: no cover - disk edge
        logger.warning("[CANVAS-RUN] status read failed for %s: %s", run_folder, e)
        return None


# ── events.jsonl (append) ────────────────────────────────────────────────────

def _events_path(run_folder: Path) -> Path:
    return Path(run_folder) / EVENTS_FILENAME


def _append_event_file(run_folder: Path, record: Dict[str, Any]) -> None:
    """Append one event record as a single JSON line. Best effort."""
    try:
        with _events_path(run_folder).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # pragma: no cover - disk edge
        logger.warning("[CANVAS-RUN] event append failed for %s: %s", run_folder, e)


def _read_events_file(run_folder: Path, after: int = -1) -> List[Dict[str, Any]]:
    """Read persisted events with running index > after. Tolerant of partial
    last lines (a torn write). Returns [] if the file is absent."""
    out: List[Dict[str, Any]] = []
    p = _events_path(run_folder)
    if not p.exists():
        return out
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    # Torn final line from an unflushed append — stop here.
                    break
                if rec.get("_i", -1) > after:
                    out.append(rec)
    except Exception as e:  # pragma: no cover - disk edge
        logger.warning("[CANVAS-RUN] events read failed for %s: %s", run_folder, e)
    return out


# ── event publishing ─────────────────────────────────────────────────────────

def _publish(run_id: str, event_type: str, data: Dict[str, Any],
             state: Optional[str] = None, error: Optional[str] = None) -> None:
    """Assign a running index, append to the in-memory buffer AND events.jsonl,
    then notify readers. Called only from the worker thread.

    If `state` is given, the job state transition happens in the SAME critical
    section as the buffer append — so for a terminal event (complete/error) there
    is no window where state is terminal but the event isn't yet buffered. This
    is what lets a reader break on the terminal state without ever missing the
    terminal event, and guarantees status.json (written here) is consistent the
    moment the event becomes visible."""
    # Reserve the running index under the lock, but do NOT publish to the buffer
    # yet if this is a terminal event: we first flush the line to events.jsonl,
    # so that the instant any reader/poller can observe the terminal STATE (set
    # atomically with the buffer append below), events.jsonl already contains it.
    with _JOBS_COND:
        job = _JOBS.get(run_id)
        if job is None:
            return
        idx = job["n_events"]
        run_folder = Path(job["run_folder"])
    record = {"_i": idx, "type": event_type, "data": data}
    terminal = state in TERMINAL_STATES if state is not None else False

    if terminal:
        # Flush BOTH files to their terminal values BEFORE the event/state become
        # observable in memory. Then any reader that has seen `complete`/`error`
        # (or a poller that sees the terminal state) finds events.jsonl AND
        # status.json already consistent — no post-visibility write window.
        _append_event_file(run_folder, record)
        with _JOBS_COND:
            job = _JOBS.get(run_id)
            finished_at = _now() if (job and not job.get("finished_at")) else \
                (job.get("finished_at") if job else _now())
            started_at = job.get("started_at") if job else None
        _write_status_file(run_folder, state, idx + 1, error=error,
                           started_at=started_at, finished_at=finished_at)

    with _JOBS_COND:
        job = _JOBS.get(run_id)
        if job is None:
            return
        job["events"].append(record)
        job["n_events"] = idx + 1
        if len(job["events"]) > MAX_BUFFER_EVENTS:
            del job["events"][: len(job["events"]) - MAX_BUFFER_EVENTS]
        write_status = False
        if state is not None:
            job["state"] = state
            if error is not None:
                job["error"] = error
            if state in TERMINAL_STATES:
                if not job.get("finished_at"):
                    job["finished_at"] = finished_at
            else:
                write_status = True
                status_args = (state, job["n_events"], job.get("error"),
                               job.get("started_at"), job.get("finished_at"))
        _JOBS_COND.notify_all()

    if not terminal:
        # High-frequency path: append outside the lock (must not serialize readers).
        _append_event_file(run_folder, record)
        if write_status:
            _write_status_file(run_folder, status_args[0], status_args[1],
                               error=status_args[2], started_at=status_args[3],
                               finished_at=status_args[4])


def _set_state(run_id: str, state: str, error: Optional[str] = None) -> None:
    """Transition job state (no event), persist status.json atomically, wake
    readers. Used for non-terminal transitions like 'running'."""
    with _JOBS_COND:
        job = _JOBS.get(run_id)
        if job is None:
            return
        job["state"] = state
        if error is not None:
            job["error"] = error
        if state in TERMINAL_STATES and not job.get("finished_at"):
            job["finished_at"] = _now()
        n_events = job["n_events"]
        run_folder = Path(job["run_folder"])
        started_at = job.get("started_at")
        finished_at = job.get("finished_at")
        _JOBS_COND.notify_all()
    _write_status_file(run_folder, state, n_events, error=error,
                       started_at=started_at, finished_at=finished_at)


# ── worker ───────────────────────────────────────────────────────────────────

def _worker(run_id: str, nodes: list, connections: list,
            device_id: Optional[str], app: Any, safety_level: str,
            lang: Optional[str] = None) -> None:
    """Drive the (unchanged) executor, publishing every event. Runs in a daemon
    thread. Emits a synthetic 'complete' or 'error' terminal event so readers —
    live or reconnecting — always see an explicit end."""
    ctx = app.app_context() if app is not None else None
    if ctx is not None:
        ctx.push()
    try:
        from schemas.engine.prompt_interception_engine import PromptInterceptionEngine
        engine = PromptInterceptionEngine()

        with _JOBS_COND:
            job = _JOBS.get(run_id)
            recorder = job["recorder"] if job else None
        if recorder is None:
            return

        executor = CanvasWorkflowExecutor(
            nodes=nodes,
            connections=connections,
            recorder=recorder,
            run_id=run_id,
            engine=engine,
            device_id=recorder.device_id,
            safety_level=safety_level,
            lang=lang,
        )

        _set_state(run_id, "running")
        for event_type, event_data in executor.execute_with_events():
            _publish(run_id, event_type, event_data)

        result = executor.get_result()
        if not result.get("success"):
            err = result.get("error", "Unknown error")
            # A failed run leaves a record too, and it is the SAME record the
            # 'complete' event carries: node results, trace, collected items.
            # Publishing only a message made the run illegible afterwards --
            # view_run found no results and told Resona it 'may still be
            # rendering', and images that had already rendered stayed invisible.
            # Terminal event + state atomically (status.json consistent on sight).
            _publish(run_id, "error", {
                "message": err,
                "errors": result.get("errors", []),
                "results": result.get("results", {}),
                "collectorOutput": result.get("collector_items", []),
                "cardMeta": result.get("card_meta", {}),
                "executionOrder": result.get("execution_trace", []),
                "exportPath": str(recorder.run_folder),
                "run_id": run_id,
            }, state="error", error=err)
            cleanup_canvas_recorder(run_id)
            return

        recorder.mark_complete()
        export_path = str(recorder.run_folder)
        _publish(run_id, "complete", {
            "results": result["results"],
            "collectorOutput": result["collector_items"],
            # Prompt, model sheet, time and sub-run per generation node. Its own
            # key so it is in the record even when the graph has no collector.
            "cardMeta": result.get("card_meta", {}),
            "executionOrder": result["execution_trace"],
            "exportPath": export_path,
            "run_id": run_id,
        }, state="complete")
        cleanup_canvas_recorder(run_id)
        logger.info("[CANVAS-RUN] %s complete. Trace: %s",
                    run_id, " -> ".join(result["execution_trace"]))

    except Exception as e:  # executor blew up unexpectedly
        logger.error("[CANVAS-RUN] %s fatal: %s", run_id, e)
        import traceback
        traceback.print_exc()
        _publish(run_id, "error", {"message": str(e)}, state="error", error=str(e))
        try:
            cleanup_canvas_recorder(run_id)
        except Exception:
            pass
    finally:
        if ctx is not None:
            ctx.pop()


# ── public API ───────────────────────────────────────────────────────────────

def start_run(nodes: list, connections: list,
              device_id: Optional[str] = None, app: Any = None,
              safety_level: Optional[str] = None,
              lang: Optional[str] = None,
              name: str = '') -> str:
    """Create the recorder + register the job + spawn its worker thread.
    Returns the run_id immediately (before any node executes).

    name is the workflow's name, recorded in workflow.json beside the graph:
    a kept output of the run opens its board again from there, and the board
    keeps the name its files are called by.

    safety_level MUST be resolved by the caller, inside the request: the worker
    runs in a daemon thread with only an app context, where the session — and
    with it the course binding — is out of reach. Omitting it runs the graph at
    the strictest level rather than at the installation default."""
    from my_app.services.safety_level_resolver import STRICTEST
    safety_level = safety_level or STRICTEST
    run_id = generate_run_id(suffix="canvas")
    recorder = get_canvas_recorder(
        run_id=run_id,
        workflow={"name": name or '', "nodes": nodes, "connections": connections},
        device_id=device_id,
    )
    started_at = _now()
    with _JOBS_COND:
        _JOBS[run_id] = {
            "state": "starting",
            "events": [],          # ring buffer of {"_i", "type", "data"}
            "n_events": 0,
            "recorder": recorder,
            "run_folder": str(recorder.run_folder),
            "error": None,
            "started_at": started_at,
            "finished_at": None,
        }
    _write_status_file(recorder.run_folder, "running", 0, started_at=started_at)

    t = threading.Thread(
        target=_worker,
        args=(run_id, nodes, connections, device_id, app, safety_level, lang),
        name=f"canvas-run-{run_id}",
        daemon=True,
    )
    t.start()
    logger.info("[CANVAS-RUN] started %s in %s", run_id, recorder.run_folder)
    return run_id


def iter_events(run_id: str, after: int = -1, timeout: float = 300.0,
                client_gone: Optional[threading.Event] = None):
    """Yield event records for a run starting AFTER running-index `after`.

    Live job (in registry): replay buffered events > after (or read them back
        from events.jsonl if they predate the buffer window), then block on the
        condition for new events until a terminal event is delivered.
    Absent job (left memory / another process / post-restart): read whatever
        events.jsonl holds and stop — the caller then falls back to the status
        endpoint (which surfaces `interrupted`).

    Each yielded item is {"_i": int, "type": str, "data": dict}.

    `client_gone` ends the TAIL and nothing else. The SSE transport that carries
    these records sets it when the browser goes away (services/
    streaming_response.py); the RUN is a background job by design and keeps
    going, so a reader that comes back gets every event of it from events.jsonl.
    Without the signal an abandoned tail sat here for the full `timeout`, waking
    once a second to take _JOBS_LOCK — which the status endpoint and the run
    worker both need. Optional and defaulted, so every existing caller reads as
    it always did.
    """
    deadline = time.monotonic() + timeout
    last = after

    # If the job isn't live, serve purely from disk (best-effort replay).
    with _JOBS_LOCK:
        live = run_id in _JOBS
    if not live:
        for rec in _read_events_file(_run_folder_from_disk(run_id) or Path("."), after=last):
            yield rec
        return

    # Cover the gap between `after` and the buffer's oldest index using the file.
    with _JOBS_LOCK:
        job = _JOBS.get(run_id)
        buf_lo = job["events"][0]["_i"] if job and job["events"] else job["n_events"] if job else 0
    if last + 1 < buf_lo:
        for rec in _read_events_file(Path(job["run_folder"]), after=last):
            if rec["_i"] < buf_lo:
                yield rec
                last = rec["_i"]

    # We end on the first terminal-TYPE event we actually yield (complete/error),
    # not merely on job["state"] flipping terminal. This decouples the stream end
    # from the status-file write ordering: the worker writes status.json to its
    # terminal value BEFORE publishing the terminal event, so a reader that has
    # seen `complete`/`error` can trust that status.json is already consistent.
    saw_terminal = False
    while not saw_terminal:
        if client_gone is not None and client_gone.is_set():
            logger.info("[CANVAS-RUN] %s: tail ended, its reader is gone", run_id)
            return
        drained: List[Dict[str, Any]] = []
        with _JOBS_COND:
            job = _JOBS.get(run_id)
            if job is None:
                break
            for rec in job["events"]:
                if rec["_i"] > last:
                    drained.append(rec)
            terminal_state = job["state"] in TERMINAL_STATES
            if not drained:
                if terminal_state:
                    # Terminal with nothing new buffered → no terminal event is
                    # coming (e.g. reader joined post-terminal). Stop.
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                _JOBS_COND.wait(timeout=min(remaining, 1.0))
        for rec in drained:
            if rec["_i"] > last:
                last = rec["_i"]
                yield rec
                if rec["type"] in ("complete", "error"):
                    saw_terminal = True
                    break


def get_status(run_id: str) -> Dict[str, Any]:
    """Cheap status snapshot for polling. Prefers the live registry; falls back
    to status.json on disk; else 'unknown'."""
    with _JOBS_LOCK:
        job = _JOBS.get(run_id)
        if job is not None:
            return {
                "run_id": run_id,
                "state": job["state"],
                "n_events": job["n_events"],
                "error": job.get("error"),
                "started_at": job.get("started_at"),
                "finished_at": job.get("finished_at"),
            }
    run_folder = _run_folder_from_disk(run_id)
    if run_folder is not None:
        st = _read_status_file(run_folder)
        if st is not None:
            st["run_id"] = run_id
            return st
    return {"run_id": run_id, "state": "unknown", "n_events": 0, "error": None}


# ── disk lookup (restart / cross-process) ────────────────────────────────────

def _run_folder_from_disk(run_id: str, base_path: Optional[Path] = None) -> Optional[Path]:
    """Locate a run folder on disk by run_id, mirroring load_recorder's search
    (YYYY-MM-DD/device_id/run_id). run_id is assumed already sanitized by the
    route. Returns None if not found."""
    if base_path is None:
        from config import JSON_STORAGE_DIR
        base_path = JSON_STORAGE_DIR
    base_path = Path(base_path)
    if not base_path.exists():
        return None
    # Newest date folders first.
    for date_folder in sorted(base_path.glob("20??-??-??"), reverse=True):
        if not date_folder.is_dir():
            continue
        # New format: date/device_id/run_id/
        for device_folder in date_folder.iterdir():
            if device_folder.is_dir():
                cand = device_folder / run_id
                if (cand / "metadata.json").exists() or (cand / STATUS_FILENAME).exists():
                    return cand
        # Legacy: date/run_id/
        legacy = date_folder / run_id
        if (legacy / "metadata.json").exists() or (legacy / STATUS_FILENAME).exists():
            return legacy
    return None


# ── startup hook (restart detection) ─────────────────────────────────────────

def mark_orphans_interrupted(base_path: Optional[Path] = None) -> int:
    """On backend start, any run folder whose status.json still says 'running'
    is an orphan from a process that died mid-run. Rewrite it to 'interrupted'
    (atomic) so a client that reconnects/polls afterward gets 'interrupted' +
    its partial results (served via /api/media/image/<run_id>).

    No auto-resume of the remaining nodes here — that is documented follow-up
    work. Returns the number of runs re-marked.
    """
    if base_path is None:
        from config import JSON_STORAGE_DIR
        base_path = JSON_STORAGE_DIR
    base_path = Path(base_path)
    if not base_path.exists():
        return 0
    n = 0
    try:
        # Covers both nesting depths (date/device/run and legacy date/run).
        for status_file in base_path.glob("**/status.json"):
            if _maybe_reinterrupt(status_file):
                n += 1
    except Exception as e:  # pragma: no cover - disk edge
        logger.warning("[CANVAS-RUN] orphan scan failed: %s", e)
    if n:
        logger.info("[CANVAS-RUN] marked %d orphaned running -> interrupted", n)
    return n


def _maybe_reinterrupt(status_file: Path) -> bool:
    try:
        st = json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return False
    if st.get("state") != "running":
        return False
    run_folder = status_file.parent
    _write_status_file(
        run_folder, "interrupted", st.get("n_events", 0),
        error="Backend restarted while this run was in progress.",
        started_at=st.get("started_at"), finished_at=_now(),
    )
    logger.info("[CANVAS-RUN] orphan re-marked interrupted: %s", run_folder.name)
    return True


# ── test / introspection helpers ─────────────────────────────────────────────

def _reset_registry_for_tests() -> None:
    """Clear the in-memory registry (unit-test isolation only)."""
    with _JOBS_LOCK:
        _JOBS.clear()
