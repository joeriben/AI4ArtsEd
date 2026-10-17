"""
Knowledge-library ingest JOB service (Tier O, Settings curation).

A tiny in-process job runner for operator document ingest (BIBLIOTHEK.md §9),
rewired for the Verdichtungs-Umbau (2026-07-04). Each job runs THREE steps:

  1. Docling -> RAW Markdown, via knowledge_ingest.py in the Docling venv
     (KNOWLEDGE_INGEST_PYTHON). PDF -> convert; already-Markdown -> passthrough
     (no torch). The raw MD is a gitignored re-processing intermediate under
     resources/knowledge_originals/operator/<doc_id>.raw.md.
  2. Verdichtung, IN-PROCESS: knowledge_processing.process_document() reads the
     raw MD + the operator metadata and writes the COMPACT library file
     (front-matter + ## PROFIL + ## WISSEN + ## GLOSSAR) to the Tier-O dir as a
     draft. This step uses the platform's own provider routing (call_chat_helper,
     role KNOWLEDGE_PROCESSING_MODEL) — no second server, no Docling.
  3. Reindex, via build_knowledge_index.py (KNOWLEDGE_INDEX_PYTHON), so the new
     draft is immediately curatable.

It follows the two in-house idioms that fit best:
  * a keyed status registry + circular log buffer, like training_service.py
    (keyed by job_id so the Settings tab can show a small job list), and
  * subprocess.Popen + a daemon thread streaming stdout into the status dict
    for the two subprocess steps (Docling, reindex).

Jobs run one at a time through a single FIFO worker thread: the Verdichtung
issues LLM calls and Docling is heavy, so serialising is the safe default. The
registry is in-memory only (does NOT survive a devserver restart); the produced
Markdown + index on disk are the durable artefacts.

Failure classification (CLAUDE.md rule 12): a missing Docling/ingest interpreter
is a DEPLOYMENT failure and is reported as one clear log line pointing at the
install docs — the server never crashes on it.

The GPU slot (CLAUDE.md rule 15, UCD-141): step 1 holds the plant-wide lease
"docling" for as long as the Docling process runs. Docling's OCR and layout
models select cuda:0 wherever they find a card — seen in the UCD-132 E2E of
2026-09-27 — so a conversion meets the same card every generation queues for.
The conflict behaviour is the gate's own, not a second policy of this service:
an ingest that starts while a generation runs WAITS in the gate's queue until
the generation ends, and a generation that starts while a conversion runs waits
the same way for the conversion. Only the gate's own refusals end the job
instead of queueing it — a full queue, a wait past its budget, or a long hold
(a LoRA training keeps the card for hours and turns everything else away at
once): the job then goes to `error` carrying the gate's sentence, and nothing
was converted. A Markdown passthrough takes no lease: knowledge_ingest.py
imports the converter lazily, so that path never reaches the card.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import subprocess
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LOG_MAX = 1000  # circular log-buffer cap per job (training_service parity)

# job_id -> status dict. Guarded by _JOBS_LOCK. Log lines live in a bounded
# deque; get_job() copies to a plain list (never hands out the live buffer).
_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()

# FIFO of job_ids waiting for the single worker thread.
_QUEUE: "Queue[str]" = Queue()
_WORKER_STARTED = False
_WORKER_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_worker() -> None:
    """Start the single consumer thread on first use (lazy, idempotent)."""
    global _WORKER_STARTED
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return
        t = threading.Thread(target=_worker_loop, name="knowledge-ingest", daemon=True)
        t.start()
        _WORKER_STARTED = True


def _append_log(job_id: str, line: str) -> None:
    line = (line or "").rstrip("\n")
    if not line:
        return
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            job["_log"].append(line)


def _set(job_id: str, **fields: Any) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            job.update(fields)


def _is_cancelled(job_id: str) -> bool:
    """True if a cancel was requested for this job (the worker polls this at
    phase boundaries and hands a bound version to the Verdichtung Map loop)."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        ev = job.get("_cancel") if job else None
    return bool(ev and ev.is_set())


def _set_proc(job_id: str, proc: Optional["subprocess.Popen"]) -> None:
    """Publish (or clear) the running subprocess handle so request_cancel can
    terminate() it. Guarded by _JOBS_LOCK."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            job["_proc"] = proc


def request_cancel(job_id: str) -> Dict[str, Any]:
    """Ask a job to stop. Returns {"ok": bool, "state": <new/current state>,
    "error": <msg on ok=False>} — the route maps ok=False to 409.

      * queued  -> flip to `cancelled` immediately. The worker skips a job that
        is already cancelled when it pops it from the FIFO (we cannot cheaply
        remove an arbitrary id from a Queue, so we tombstone instead).
      * running -> set the cancel Event (the worker checks it at every phase
        boundary and between Verdichtung Map calls) AND terminate() any live
        Docling/reindex subprocess so a long external step stops promptly.
      * done | error | cancelled -> nothing to cancel (ok=False).
    """
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return {"ok": False, "state": None, "error": f"No such job '{job_id}'"}
        state = job["state"]
        if state == "queued":
            # Tombstone: mark cancelled now; the worker drops it when dequeued.
            job["_cancel"].set()
            job["state"] = "cancelled"
            job["message"] = "cancelled (was queued)"
            job["finished_at"] = _now()
            job["_log"].append("cancelled while queued (removed from queue)")
            return {"ok": True, "state": "cancelled"}
        if state == "running":
            job["_cancel"].set()
            job["_log"].append("cancel requested — stopping at the next step boundary")
            proc = job.get("_proc")
            # terminate the in-flight subprocess (if the running step is Docling
            # or reindex); the Verdichtung step has no subprocess and is caught
            # by the Event poll in its Map loop instead.
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    job["_log"].append("terminated the running subprocess")
                except Exception as e:  # noqa: BLE001
                    job["_log"].append(f"could not terminate subprocess: {e}")
            return {"ok": True, "state": "running"}
        # done | error | cancelled — terminal, nothing to do.
        return {"ok": False, "state": state,
                "error": f"job is already '{state}' — nothing to cancel"}


def enqueue_ingest(
    *,
    doc_id: str,
    title: str,
    lizenz: str,
    source_pdf: Optional[Path] = None,
    source_md: Optional[Path] = None,
    autor: str = "",
    year: Optional[int] = None,
    lang: str = "",
    url: str = "",
    sparten: str = "",
    themen: str = "",
    bereich: str = "",
    hinweis: str = "",
    tier: str = "o",
    status: str = "draft",
    reprocess: bool = False,
    cleanup_paths: Optional[List[Path]] = None,
    raw_hash: str = "",
) -> str:
    """Register a Tier-O ingest job and return its job_id. Exactly one of
    source_pdf / source_md must be given. The job runs asynchronously through
    the FIFO worker (Docling -> Verdichtung -> reindex); poll get_job(job_id)
    for progress.

    `lang` defaults to "" (empty): the Verdichtung detects the document's
    source language itself (identify_bibliographic) and never assumes German.
    `status` defaults to "draft" (a fresh upload always starts as a draft); the
    reprocess route passes the item's CURRENT status so a re-analysis of an
    already-published document does not silently unpublish it. NOTE: `status`
    is NOT a reliable signal for "is this a reprocess?" -- a reprocess of a
    still-`draft` document also passes status="draft", identical to a fresh
    upload's default.

    `reprocess` defaults to False (a fresh upload). Only reprocess_item()
    passes reprocess=True. This is the ONLY thing _finish_cancelled uses to
    decide whether <doc_id>.md and raw_out (this doc_id's _raw_md_path()) are
    THIS run's own throwaway partial artefacts (fresh upload -- safe to remove
    on cancel) or the operator's pre-existing draft and stored source
    (reprocess -- must survive a cancel untouched). See _finish_cancelled's
    docstring for the full reasoning."""
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "state": "queued",           # queued | running | done | error | cancelled
            "doc_id": doc_id,
            "title": title,
            "returncode": None,
            "message": "queued",
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "_log": deque(maxlen=_LOG_MAX),
            # Cancellation plumbing (BIBLIOTHEK.md §9 curation): an Event the
            # worker polls at phase boundaries + inside the Verdichtung Map loop,
            # and a live Popen handle for the running subprocess step (Docling /
            # reindex) so a cancel can terminate() it. Both are internal (never
            # in the public view). _proc is guarded by _JOBS_LOCK.
            "_cancel": threading.Event(),
            "_proc": None,
            # spec below is consumed by the worker, then dropped from the view.
            "_spec": {
                "source_pdf": str(source_pdf) if source_pdf else None,
                "source_md": str(source_md) if source_md else None,
                "doc_id": doc_id,
                "title": title,
                "lizenz": lizenz,
                "autor": autor,
                "year": year,
                "lang": lang,
                "url": url,
                "sparten": sparten,
                "themen": themen,
                "bereich": bereich,
                "hinweis": hinweis,
                "tier": tier,
                "status": status,
                "reprocess": reprocess,
                "cleanup_paths": [str(p) for p in (cleanup_paths or [])],
                # Stage A (UCD-131): raw-bytes SHA-256 of the uploaded source,
                # recorded into the hash index at job end (final doc_id after
                # the Author-Year-Title rename + the extracted-MD hash).
                "raw_hash": raw_hash or "",
            },
        }
    _ensure_worker()
    _QUEUE.put(job_id)
    return job_id


def get_job(job_id: str, log_tail: int = 40) -> Optional[Dict[str, Any]]:
    """A JSON-safe snapshot of one job (log_tail last lines), or None."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        return _public_view(job, log_tail)


def list_jobs(log_tail: int = 0) -> List[Dict[str, Any]]:
    """All jobs, newest first (for the Settings tab's job list)."""
    with _JOBS_LOCK:
        jobs = [_public_view(j, log_tail) for j in _JOBS.values()]
    jobs.sort(key=lambda j: j["created_at"], reverse=True)
    return jobs


def _public_view(job: Dict[str, Any], log_tail: int) -> Dict[str, Any]:
    log = list(job["_log"])
    if log_tail and log_tail > 0:
        log = log[-log_tail:]
    return {
        "job_id": job["job_id"],
        "state": job["state"],
        "doc_id": job["doc_id"],
        "title": job["title"],
        "returncode": job["returncode"],
        "message": job["message"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "log_tail": log,
    }


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _worker_loop() -> None:
    while True:
        job_id = _QUEUE.get()
        try:
            _run_job(job_id)
        except Exception as e:  # noqa: BLE001 - never let the worker die
            logger.exception("[KNOWLEDGE-JOB] worker crash on %s", job_id)
            _append_log(job_id, f"CRITICAL: worker error: {e}")
            _set(job_id, state="error", message=str(e), finished_at=_now())
        finally:
            _QUEUE.task_done()


def _run_job(job_id: str) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        spec = dict(job["_spec"]) if job else None
    if spec is None:
        return

    # A job cancelled while still queued was tombstoned to `cancelled` by
    # request_cancel; skip it entirely (we could not pull it from the FIFO).
    if _is_cancelled(job_id):
        _append_log(job_id, "skipped: cancelled before it started")
        _cleanup(spec)
        return

    _set(job_id, state="running", message="docling", started_at=_now())

    # --- step 1: Docling -> raw Markdown (subprocess, Docling venv) -----------
    raw_out = _raw_md_path(spec["doc_id"])
    from my_app.services.gpu_lease_client import GpuBusyError
    try:
        rc = _run_docling(job_id, spec, raw_out)
    except GpuBusyError as e:
        # The gate refused the slot instead of queueing for it: the card is on a
        # long hold, the queue is full, or the wait ran out. Nothing was
        # converted; the job ends like any other step-1 failure (the stored
        # original stays for a second attempt, staged temporaries go), and the
        # operator reads the gate's own sentence.
        _append_log(job_id, f"GPU slot not free: {e}")
        _set(job_id, state="error", message=f"gpu busy: {e}", finished_at=_now())
        _cleanup(spec)
        return
    if _is_cancelled(job_id):
        return _finish_cancelled(job_id, spec, raw_out)
    if rc != 0:
        _set(job_id, state="error", message=f"docling failed (code {rc})",
             returncode=rc, finished_at=_now())
        _cleanup(spec)
        return
    if not raw_out.exists():
        _append_log(job_id, f"raw Markdown was not produced at {raw_out}")
        _set(job_id, state="error", message="raw markdown missing", finished_at=_now())
        _cleanup(spec)
        return

    # --- step 2: Verdichtung -> compact library file (IN-PROCESS) -------------
    _set(job_id, message="verdichtung")
    _append_log(job_id, "docling OK; running Verdichtung in-process…")
    try:
        out_path = _run_verdichtung(job_id, spec, raw_out)
    except Exception as e:  # noqa: BLE001
        logger.exception("[KNOWLEDGE-JOB] Verdichtung failed on %s", job_id)
        _append_log(job_id, f"Verdichtung error: {e}")
        _set(job_id, state="error", message=f"verdichtung failed: {e}", finished_at=_now())
        _cleanup(spec)
        return
    # _run_verdichtung returns None in two distinct cases that must NOT be
    # conflated: (a) an operator abort caught inside the Map loop
    # (ProcessingCancelled) -- a real cancellation, handled by _finish_cancelled
    # (which also removes THIS run's partial draft, if any); (b) a FATAL sanity-
    # check failure (result.fatal non-empty) -- _run_verdichtung has already
    # logged the reasons and set state="error", and wrote NOTHING, so there is
    # no partial draft to clean up and any PREVIOUS good draft on disk must be
    # left exactly as it is. Only case (a) sets the cancel Event, so
    # _is_cancelled(job_id) tells them apart.
    if out_path is None:
        if _is_cancelled(job_id):
            return _finish_cancelled(job_id, spec, raw_out)
        _cleanup(spec)
        return
    # A cancel that arrived after the Verdichtung finished but before reindex.
    if _is_cancelled(job_id):
        return _finish_cancelled(job_id, spec, raw_out)
    _append_log(job_id, f"Verdichtung OK -> {out_path}")

    # --- step 2b: legible Author-Year-Title doc_id (fresh upload) --------------
    try:
        out_path, raw_out = _apply_composed_doc_id(job_id, spec, out_path, raw_out)
    except Exception as e:  # noqa: BLE001 - never fatal; keep the provisional id
        _append_log(job_id, f"doc_id composition skipped: {e}")

    # --- step 3: reindex (subprocess, devserver venv) -------------------------
    _set(job_id, message="reindex")
    _append_log(job_id, "rebuilding index…")
    idx_rc = _run_reindex(job_id)
    if _is_cancelled(job_id):
        return _finish_cancelled(job_id, spec, raw_out)
    _cleanup(spec)
    if idx_rc != 0:
        _set(job_id, state="error", message=f"reindex failed (code {idx_rc})",
             finished_at=_now())
        return
    _record_hash_index_entry(job_id, spec, raw_out)
    _set(job_id, state="done", message="done", returncode=0, finished_at=_now())


def _record_hash_index_entry(job_id: str, spec: Dict[str, Any], raw_out: Path) -> None:
    """Stage A (UCD-131): on a SUCCESSFUL ingest, write the document's hash
    index entry with the FINAL doc_id (the Author-Year-Title rename in step 2b
    may have changed it since the upload route recorded its provisional
    first-guess entry) and the raw-MD hash (same content in another file
    garb or after a new Docling build counts as known). Only fresh uploads
    carry a raw_hash; a reprocess passes none (re-analysing an EXISTING
    document is the operator's explicit way around the index by design).
    Failures are logged, never raised — the ingest itself has already
    succeeded."""
    raw_hash = str(spec.get("raw_hash") or "")
    if not raw_hash:
        return
    md_h = ""
    try:
        if raw_out.exists():
            from my_app.services import upload_gate

            md_h = upload_gate.md_hash(raw_out.read_text(encoding="utf-8"))
    except OSError as e:  # noqa: BLE001 — index entry is best-effort
        logger.warning("[KNOWLEDGE-JOB] raw MD unreadable for hash index: %s", e)
    try:
        from my_app.services import upload_gate

        upload_gate.record_hash_index(str(spec["doc_id"]), raw_hash, md_h or None)
    except Exception as e:  # noqa: BLE001
        logger.warning("[KNOWLEDGE-JOB] hash index record failed for %s: %s",
                       spec.get("doc_id"), e)


def _finish_cancelled(job_id: str, spec: Dict[str, Any], raw_out: Path) -> None:
    """Land a cancelled job in the `cancelled` state, removing ONLY what is
    safe to remove for the KIND of run being aborted. A fresh upload and a
    reprocess do NOT mean the same thing by "<doc_id>.md" or by raw_out, and
    conflating them was a data-destroying bug: this function used to remove
    both, unconditionally, on every cancel.

      * FRESH UPLOAD (spec["reprocess"] is False -- upload_document()'s only
        mode): <doc_id>.md under KNOWLEDGE_TIER_O_DIR, if it exists at all, is
        at most a partial draft THIS run just started writing -- a half-baked
        file that must not linger as if it were a real, curatable document.
        raw_out (resources/knowledge_originals/operator/<doc_id>.raw.md) is a
        re-processing intermediate THIS run just produced. Both are removed.
        The original upload (resources/knowledge_originals/operator/
        <doc_id>.pdf) is DELIBERATELY kept: cancelling ingest must not lose
        the operator's source, so re-uploading or a future restart of
        processing stays possible.

      * REPROCESS (spec["reprocess"] is True -- set only by reprocess_item()):
        <doc_id>.md is the PREVIOUS, GOOD analysis -- it pre-dates this run
        and is exactly what the operator keeps using if this run is aborted.
        raw_out is, here, NOT an intermediate: reprocess_item() resolves it as
        the STORED SOURCE for the document whenever a .raw.md survived the
        original ingest, and passes that SAME path as source_md -- Docling
        then runs as a passthrough with input==output. For documents ingested
        from an already-Markdown original, raw_out is the ONLY stored copy of
        the source: there is no <doc_id>.pdf fallback. Removing either file
        here would destroy operator data with no way back, so on a reprocess
        we remove NEITHER -- only the temp inputs the route staged
        (cleanup_paths; normally empty for a reprocess, since its source is
        always an already-stored path, never a temp upload).

    Either way: terminate/clear any live subprocess handle, log plainly what
    happened, and flip the job to `cancelled`.
    """
    if spec.get("reprocess"):
        _cleanup(spec)
        _append_log(
            job_id,
            "cancelled: existing draft and stored source left untouched (reprocess)",
        )
        _set_proc(job_id, None)
        _set(job_id, state="cancelled", message="cancelled", finished_at=_now())
        return

    from config import KNOWLEDGE_TIER_O_DIR
    doc_id = spec["doc_id"]
    removed: List[str] = []

    draft = Path(KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md"
    try:
        if draft.exists():
            draft.unlink()
            removed.append(draft.name)
    except OSError as e:
        _append_log(job_id, f"could not remove partial draft {draft}: {e}")

    try:
        if raw_out and raw_out.exists():
            raw_out.unlink()
            removed.append(raw_out.name)
    except OSError as e:
        _append_log(job_id, f"could not remove raw intermediate {raw_out}: {e}")

    _cleanup(spec)
    if removed:
        _append_log(job_id, "cleaned up unfinished artefacts: " + ", ".join(removed))
    _append_log(job_id, "original upload kept for re-processing")
    _set_proc(job_id, None)
    _set(job_id, state="cancelled", message="cancelled", finished_at=_now())


def _raw_md_path(doc_id: str) -> Path:
    """Where the raw Docling MD is written for a Tier-O upload (gitignored)."""
    from config import KNOWLEDGE_ORIGINALS_DIR
    d = Path(KNOWLEDGE_ORIGINALS_DIR) / "operator"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{doc_id}.raw.md"


def _run_docling(job_id: str, spec: Dict[str, Any], raw_out: Path) -> int:
    """Convert the source in the Docling venv, under the GPU gate.

    A PDF conversion holds the plant-wide slot for as long as its process runs
    (kind "docling"): Docling's OCR and layout models take cuda:0 whenever a
    card is there. How much memory that is has not been measured, so nothing is
    declared — serialising is what is known to be needed, and a figure nobody
    measured would be worse than none (blender_service.py takes the slot on the
    same reasoning). Raises GpuBusyError when the gate refuses rather than
    queues; _run_job turns that into a job the operator can read.
    """
    from config import KNOWLEDGE_INGEST_PYTHON, KNOWLEDGE_INGEST_SCRIPT
    from my_app.services.gpu_lease_client import gpu_lease_sync
    interp = Path(KNOWLEDGE_INGEST_PYTHON)
    if not interp.exists():
        # DEPLOYMENT failure class (CLAUDE.md rule 12): the ingest venv is not
        # installed. One clear line, point at the install docs, do not crash.
        _append_log(
            job_id,
            f"Docling-venv fehlt: interpreter not found at {interp}. "
            "Deployment: create it per docs/installation "
            "(python3 -m venv ~/ai/venvs/knowledge && pip install -r "
            "devserver/scripts/requirements_knowledge.txt). "
            "Override the path with KNOWLEDGE_INGEST_PYTHON.",
        )
        return 127
    cmd = [str(interp), str(KNOWLEDGE_INGEST_SCRIPT),
           "--doc-id", spec["doc_id"], "--raw-out", str(raw_out)]
    converts_pdf = False
    if spec.get("source_md"):
        cmd += ["--md", spec["source_md"]]
    elif spec.get("source_pdf"):
        cmd += [spec["source_pdf"]]
        converts_pdf = True
    else:
        _append_log(job_id, "no source PDF/MD in job spec")
        return 2
    _append_log(job_id, "$ " + " ".join(cmd))
    if converts_pdf:
        _append_log(job_id, "waiting for the GPU slot (a generation in flight "
                            "finishes first)…")
    slot = (gpu_lease_sync(kind="docling", model_id="docling", required_mb=0,
                           label=f"Docling: {spec['doc_id']}")
            if converts_pdf else contextlib.nullcontext())
    with slot:
        if _is_cancelled(job_id):
            # The cancel arrived while this job stood in the gate's queue, where
            # there was no process to terminate. Do not start one now; the caller
            # reads the Event and lands in `cancelled`.
            _append_log(job_id, "cancelled while waiting for the GPU slot")
            return 1
        return _stream_subprocess(job_id, cmd)


def _run_verdichtung(job_id: str, spec: Dict[str, Any], raw_out: Path) -> Optional[Path]:
    """In-process Verdichtung: raw MD + operator metadata -> compact draft file
    in the Tier-O dir. Returns the written path, or None in TWO distinct cases
    the caller (_run_job) must not conflate: (a) the operator aborted inside the
    Map loop (ProcessingCancelled, caught here so the caller does not depend on
    the exception class identity — which matters under a test reload of
    knowledge_processing; in production kp is never reloaded), or (b) the
    Verdichtung's own sanity check found a FATAL condition (result.fatal
    non-empty, e.g. an all-404 provider outage) — in that case this function has
    already logged the reasons and set the job to state="error", and crucially
    wrote NOTHING, so the caller must not run _finish_cancelled (which would
    delete a partial draft that does not exist here, and would mislabel the
    error as a cancellation). Only case (a) sets the job's cancel Event, so
    _is_cancelled(job_id) tells the two apart."""
    from config import KNOWLEDGE_TIER_O_DIR
    from my_app.services import knowledge_processing as kp

    raw_md = raw_out.read_text(encoding="utf-8")
    tier = (spec.get("tier") or "o").strip().lower()
    front_matter = {
        "id": spec["doc_id"],
        "titel": spec.get("title") or "",
        "autor": spec.get("autor") or ("UNESCO" if tier == "f" else ""),
        "jahr": spec.get("year") or "",
        # Detected below via identify_bibliographic if left blank -- NEVER a
        # hardcoded "de" (Defect 1c: German is data, not a platform assumption).
        "sprache": spec.get("lang") or "",
        "tier": tier.upper(),
        "sparten": [s.strip() for s in (spec.get("sparten") or "").split(",") if s.strip()],
        "themen": [t.strip() for t in (spec.get("themen") or "").split(",") if t.strip()],
        "lizenz": spec.get("lizenz") or "",
        "url": spec.get("url") or "",
        # Fresh upload starts as a draft (BIBLIOTHEK.md §9); a reprocess carries
        # the item's CURRENT status forward via spec["status"] so re-analysing a
        # published document does not silently unpublish it.
        "status": spec.get("status") or "draft",
    }
    # bereich (operator area id) + hinweis (operator per-document note) are single
    # scalar strings; only add them when set so the front-matter of an area-less
    # upload stays exactly as before.
    if (spec.get("bereich") or "").strip():
        front_matter["bereich"] = spec["bereich"].strip()
    if (spec.get("hinweis") or "").strip():
        front_matter["hinweis"] = spec["hinweis"].strip()

    # --- Bibliographic identification (2026-07-05): fill titel/autor/jahr/quelle
    # the OPERATOR left blank from the document's real bibliography (title page +
    # the imprint note), so the compact file's `titel:` is the work's title and
    # not a stray first heading (an author byline, a journal masthead, or a
    # chapter heading of a book excerpt). This is the ORCHESTRATION layer: it
    # seeds front_matter BEFORE the (deliberately LLM-metadata-free) Verdichtung
    # engine runs. The operator's own input always wins — only blank fields are
    # filled. Best-effort: any failure leaves front_matter untouched and the
    # engine's deterministic paratext fallback still fills the title.
    # sprache is included here (unlike the other fields) even though the
    # operator never fills it in via a form: it must be RE-DETECTED on every
    # run (including reprocess) rather than trusted from spec, so a stale/wrong
    # value never survives untouched (Defect 1c).
    need_biblio = any(
        not str(front_matter.get(k, "")).strip()
        for k in ("titel", "autor", "jahr", "sprache")
    )
    if need_biblio:
        try:
            rec = kp.identify_bibliographic(
                raw_md, hinweis=str(front_matter.get("hinweis", "") or ""),
                doc_id=str(spec.get("doc_id", "") or ""))
            verdikt = []
            if not str(front_matter.get("titel", "")).strip() and rec.composed_titel:
                front_matter["titel"] = rec.composed_titel
                verdikt.append(f"titel={rec.composed_titel!r}")
            if not str(front_matter.get("autor", "")).strip() and rec.autoren_str:
                front_matter["autor"] = rec.autoren_str
                verdikt.append(f"autor={rec.autoren_str!r}")
            if not str(front_matter.get("jahr", "")).strip() and rec.jahr:
                front_matter["jahr"] = rec.jahr
                verdikt.append(f"jahr={rec.jahr}")
            if not str(front_matter.get("quelle", "")).strip() and rec.quelle:
                front_matter["quelle"] = rec.quelle
                verdikt.append(f"quelle={rec.quelle!r}")
            if not str(front_matter.get("sprache", "")).strip() and rec.sprache:
                front_matter["sprache"] = rec.sprache
                verdikt.append(f"sprache={rec.sprache!r}")
            _append_log(
                job_id,
                "bibliografische Identifikation (conf=%s): %s"
                % (rec.confidence, ", ".join(verdikt) or "keine Felder ergänzt"),
            )
        except Exception as e:  # noqa: BLE001 - identity is best-effort, never fatal
            _append_log(job_id, f"bibliografische Identifikation übersprungen: {e}")

    def _progress(msg: str) -> None:
        _append_log(job_id, msg)

    # Poll this job's cancel Event between Map calls so an operator abort during
    # the (potentially many-call) Verdichtung takes effect within one unit. The
    # abort surfaces as kp.ProcessingCancelled, caught here and reported to the
    # caller as a None return (no partial draft is written in that case).
    try:
        result = kp.process_document(
            raw_md, front_matter, progress=_progress,
            cancel_check=lambda: _is_cancelled(job_id),
        )
    except kp.ProcessingCancelled as c:
        _append_log(job_id, f"Verdichtung {c}")
        return None
    for w in result.warnings:
        _append_log(job_id, f"WARN: {w}")

    if result.fatal:
        # Sanity check failed (e.g. an all-404 provider outage produced a stub
        # with no PROFIL/WISSEN). Abort BEFORE writing/reindexing: the previous
        # draft on disk (which may be `published`) must survive untouched --
        # a failed run must never destroy a good analysis (CLAUDE.md rule 12;
        # this is the exact failure that once overwrote jorissen-2022-digitale-
        # sympoiesis-und-kulturelle-resilienz-alte with a 558-char stub).
        for reason in result.fatal:
            _append_log(job_id, f"FATAL: {reason}")
        _set(job_id, state="error",
             message=f"Verdichtung failed sanity check: {result.fatal[0]}",
             finished_at=_now())
        return None

    out_dir = Path(KNOWLEDGE_TIER_O_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec['doc_id']}.md"
    out_path.write_text(result.markdown, encoding="utf-8")
    _append_log(
        job_id,
        f"compact file: {result.compact_chars} chars ({result.ratio:.1%} of raw), "
        f"{result.n_emitted_sections} Abschnitte, {result.n_missing_sections} FEHLEND, "
        f"{result.n_glossary} Glossar",
    )
    return out_path


def _front_scalar(md_text: str, key: str) -> str:
    """First `key: value` scalar from a compact-file front-matter block (outer
    matching quotes stripped). '' when the key is absent."""
    m = re.search(r"(?m)^" + re.escape(key) + r":\s*(.*)$", md_text)
    if not m:
        return ""
    v = m.group(1).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v.strip()


def _apply_composed_doc_id(job_id: str, spec: Dict[str, Any],
                           out_path: Path, raw_out: Path):
    """Rename a FRESH upload's provisional doc_id to a legible Author-Year-Title
    id once Verdichtung has written the draft and
    identify_bibliographic has resolved titel/autor/jahr into it. Moves the draft
    .md, rewrites its `id:` front-matter, and renames the stored originals
    (<id>.pdf, <id>.raw.md) so a later re-verdichtung still finds the source.
    Returns the (possibly new) (draft, raw.md) paths. Reprocess is EXEMPT -- an
    already-published id is never renamed. Best-effort: any snag leaves the
    provisional id in place (never fatal)."""
    if spec.get("reprocess"):
        return out_path, raw_out
    from my_app.services import knowledge_processing as kp
    from config import KNOWLEDGE_TIER_O_DIR, KNOWLEDGE_ORIGINALS_DIR
    old_id = str(spec["doc_id"])
    text = out_path.read_text(encoding="utf-8")
    new_id = kp.compose_doc_id(
        _front_scalar(text, "titel"),
        _front_scalar(text, "autor"),
        _front_scalar(text, "jahr"),
    )
    if not new_id or new_id == old_id:
        return out_path, raw_out
    out_dir = Path(KNOWLEDGE_TIER_O_DIR)
    final, n = new_id, 2
    while (out_dir / (final + ".md")).exists():   # never overwrite another doc
        final, n = "%s-%d" % (new_id, n), n + 1
    text2, k = re.subn(r"(?m)^id:\s*" + re.escape(old_id) + r"\s*$",
                       "id: " + final, text, count=1)
    if k != 1:
        _append_log(job_id, "doc_id rename skipped: id-line for %r not unique" % old_id)
        return out_path, raw_out
    new_md = out_dir / (final + ".md")
    new_md.write_text(text2, encoding="utf-8")
    out_path.unlink()
    ops = Path(KNOWLEDGE_ORIGINALS_DIR) / "operator"
    new_raw = raw_out
    for src, dst in ((raw_out, ops / (final + ".raw.md")),
                     (ops / (old_id + ".pdf"), ops / (final + ".pdf"))):
        if src.exists():
            src.rename(dst)
            if src == raw_out:
                new_raw = dst
    spec["doc_id"] = final
    _set(job_id, doc_id=final)
    _append_log(job_id, "doc_id: %s -> %s (Author-Year-Title)" % (old_id, final))
    return new_md, new_raw


def _run_reindex(job_id: str) -> int:
    from config import (
        KNOWLEDGE_INDEX_PYTHON,
        KNOWLEDGE_INDEX_SCRIPT,
        KNOWLEDGE_INDEX_DB,
        KNOWLEDGE_LIBRARY_DIR,
        KNOWLEDGE_TIER_O_DIR,
        KNOWLEDGE_GLOSSARY_OVERRIDES,
    )
    interp = Path(KNOWLEDGE_INDEX_PYTHON)
    if not interp.exists():
        _append_log(
            job_id,
            f"index interpreter not found at {interp} (deployment). "
            "Set KNOWLEDGE_INDEX_PYTHON to the devserver venv python.",
        )
        return 1
    # Pass configured paths explicitly (production defaults coincide with these).
    cmd = [
        str(interp), str(KNOWLEDGE_INDEX_SCRIPT),
        "--db", str(KNOWLEDGE_INDEX_DB),
        "--library", str(KNOWLEDGE_LIBRARY_DIR),
        "--tier-o", str(KNOWLEDGE_TIER_O_DIR),
        "--glossary-overrides", str(KNOWLEDGE_GLOSSARY_OVERRIDES),
    ]
    _append_log(job_id, "$ " + " ".join(cmd))
    return _stream_subprocess(job_id, cmd)


def _stream_subprocess(job_id: str, cmd: List[str]) -> int:
    """Run cmd, streaming merged stdout/stderr into the job log. Returns the
    process return code (or a non-zero sentinel if it could not be launched).

    The Popen handle is published on the job dict for the duration of the run so
    request_cancel can terminate() it; it is cleared again before returning. A
    terminated process returns a non-zero code, which the caller sees — but when
    a cancel was requested the worker checks _is_cancelled() right after and
    lands in `cancelled`, so the non-zero code is not mistaken for an error."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )
    except Exception as e:  # noqa: BLE001
        _append_log(job_id, f"could not launch: {e}")
        return 127
    _set_proc(job_id, proc)
    try:
        if proc.stdout is not None:
            for line in iter(proc.stdout.readline, ""):
                _append_log(job_id, line)
            proc.stdout.close()
        return proc.wait()
    finally:
        _set_proc(job_id, None)


def _cleanup(spec: Dict[str, Any]) -> None:
    """Remove any temp inputs the route staged (e.g. an uploaded .md copied into
    a tmp dir). The stored PDF original and the raw.md intermediate under
    resources/ are NOT cleanup paths (kept for re-processing)."""
    for p in spec.get("cleanup_paths", []):
        try:
            path = Path(p)
            if path.exists():
                path.unlink()
        except OSError:
            pass
