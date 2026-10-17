"""Szenen-Kapsel-Pipeline — FIFO-Job-Service (UCD-132).

The pipeline's own single-FIFO job runner, mirroring
knowledge_ingest_service.py's tested idiom (keyed status registry + circular
log buffer + one worker thread), with the PDF lifecycle of plan §6:

  1. Stage-A gate (UCD-131) runs in the UPLOAD ROUTE, before any enqueue —
     rejected files are never stored, never queued.
  2. Docling -> raw MD, into a JOB-SCOPED workdir (a temp dir owned by this
     job, NOT the durable originals dir — the flow document space keeps no
     source files, plan §6).
  3. Segment-Map with Stufe-B fields + capsule-Reduce with the fail-closed
     capsule gate (scene_capsule_pipeline.process_document_to_capsules,
     in-process, provider-routed like the library Verdichtung).
  4. Persist into the SESSION document space (scene_document_space):
     capsules.json, segments.json, document.json (provenance incl. docHash).
  5. Lifecycle: at job end — success, error, cancel, ANY outcome — the raw
     PDF bytes AND the extracted full-text MD are DELETED (acceptance 3).
     What remains: capsules + segment digests + hash-index entry + audit.

Hash-index protection (§5 layer 1): the route consults the session space's
own hash map before enqueue; a re-upload of the SAME document within the
session gets a 409-style duplicate answer with the existing doc_id and
provenance — no second analysis, no second cost (acceptance 5).

The GPU slot (CLAUDE.md rule 15, UCD-141): step 2 holds the plant-wide lease
"docling" for as long as the Docling process runs — the same venv, and the same
finding, as knowledge_ingest_service: Docling's OCR and layout models select
cuda:0 wherever they find a card (UCD-132 E2E, 2026-09-27). The conflict
behaviour is the gate's own: a capsule job that starts while a generation runs
WAITS in the gate's queue until the generation ends, and a generation that
starts while a conversion runs waits the same way for the conversion. Only the
gate's own refusals end the job instead of queueing it — a full queue, a wait
past its budget, a long hold such as a LoRA training — and the §6 lifecycle
holds on that path too: the raw PDF is deleted before the job goes to `error`.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional

from my_app.services import scene_document_space as space

logger = logging.getLogger(__name__)

_LOG_MAX = 1000

_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
_QUEUE: "Queue[str]" = Queue()
_WORKER_STARTED = False
_WORKER_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_worker() -> None:
    global _WORKER_STARTED
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return
        t = threading.Thread(target=_worker_loop, name="scene-ingest", daemon=True)
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
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return bool(job and job["_cancel"].is_set())


def request_cancel(job_id: str) -> Dict[str, Any]:
    """Best-effort cancel: tombstones a queued job, signals a running one (the
    pipeline polls at unit boundaries; a live Docling Popen is terminated)."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return {"success": False, "error": "unknown job"}
        if job["state"] in ("done", "error", "cancelled"):
            return {"success": True, "state": job["state"], "note": "already finished"}
        job["_cancel"].set()
        if job["state"] == "queued":
            job["state"] = "cancelled"
            job["message"] = "cancelled"
            job["finished_at"] = _now()
        proc = job.get("_proc")
        state = job["state"]
    if state == "cancelled":
        _cleanup_queued(job_id)
        return {"success": True, "state": "cancelled"}
    if proc is not None:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass
    return {"success": True, "state": state, "note": "cancel requested"}


def _cleanup_queued(job_id: str) -> None:
    """A queued-then-cancelled job never ran: drop its staged temp upload (the
    only artefact a cancelled-before-start job can have)."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id) or {}
    staged = (job.get("_spec") or {}).get("staged_pdf")
    if staged:
        try:
            Path(staged).unlink()
        except OSError:
            pass


def enqueue_scene_ingest(
    *,
    journal_id: str,
    title: str,
    staged_pdf: Path,
    raw_hash: str,
    doc_id: str,
    max_capsules: int = 30,
) -> str:
    """Register a scene-pipeline job and return its job_id. The route has
    ALREADY run the Stage-A gate and staged the PDF into a job temp dir; the
    worker moves it into its own job-scoped workdir and deletes ALL raw
    artefacts at job end (§6)."""
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "state": "queued",
            "doc_id": doc_id,
            "title": title,
            "journal_id": journal_id,
            "returncode": None,
            "message": "queued",
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "_log": deque(maxlen=_LOG_MAX),
            "_cancel": threading.Event(),
            "_proc": None,
            "_spec": {
                "journal_id": journal_id,
                "doc_id": doc_id,
                "title": title,
                "staged_pdf": str(staged_pdf),
                "raw_hash": raw_hash,
                "max_capsules": max_capsules,
            },
        }
    _ensure_worker()
    _QUEUE.put(job_id)
    return job_id


def get_job(job_id: str, log_tail: int = 40) -> Optional[Dict[str, Any]]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        return _public_view(job, log_tail)


def list_jobs(log_tail: int = 0) -> List[Dict[str, Any]]:
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
        "journal_id": job["journal_id"],
        "returncode": job["returncode"],
        "message": job["message"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "log_tail": log,
    }


def _worker_loop() -> None:
    while True:
        job_id = _QUEUE.get()
        try:
            _run_job(job_id)
        except Exception as e:  # noqa: BLE001 - never let the worker die
            logger.exception("[SZENE-JOB] worker crash on %s", job_id)
            _append_log(job_id, f"CRITICAL: worker error: {e}")
            _set(job_id, state="error", message=str(e), finished_at=_now())
        finally:
            _QUEUE.task_done()


def _set_proc(job_id: str, proc: Optional["subprocess.Popen"]) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            job["_proc"] = proc


def _stream_subprocess(job_id: str, cmd: List[str]) -> int:
    """Popen + daemon thread streaming stdout into the job log (the ingest
    service's tested idiom)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    _set_proc(job_id, proc)

    def _pump() -> None:
        try:
            for line in proc.stdout or []:
                _append_log(job_id, line)
        except Exception:  # noqa: BLE001
            pass
        finally:
            _set_proc(job_id, None)

    threading.Thread(target=_pump, daemon=True).start()
    rc = proc.wait()
    _set_proc(job_id, None)
    return rc


def _run_docling(job_id: str, pdf_path: Path, raw_out: Path) -> int:
    """Convert the staged PDF in the Docling venv, under the GPU gate.

    The conversion holds the plant-wide slot for as long as its process runs
    (kind "docling"): Docling's OCR and layout models take cuda:0 whenever a
    card is there. How much memory that is has not been measured, so nothing is
    declared — serialising is what is known to be needed, and a figure nobody
    measured would be worse than none (blender_service.py takes the slot on the
    same reasoning). Raises GpuBusyError when the gate refuses rather than
    queues; _run_job turns that into a job the operator can read, and deletes
    the raw PDF on the way out.
    """
    from config import KNOWLEDGE_INGEST_PYTHON, KNOWLEDGE_INGEST_SCRIPT
    from my_app.services.gpu_lease_client import gpu_lease_sync

    interp = Path(KNOWLEDGE_INGEST_PYTHON)
    if not interp.exists():
        # DEPLOYMENT failure class (CLAUDE.md rule 12): one clear line, no crash.
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
           "--doc-id", "scene-" + job_id, "--raw-out", str(raw_out), str(pdf_path)]
    _append_log(job_id, "$ " + " ".join(cmd))
    _append_log(job_id, "waiting for the GPU slot (a generation in flight "
                        "finishes first)…")
    with gpu_lease_sync(kind="docling", model_id="docling", required_mb=0,
                        label="Docling: scene-" + job_id):
        if _is_cancelled(job_id):
            # The cancel arrived while this job stood in the gate's queue, where
            # there was no process to terminate. Do not start one now; the caller
            # reads the Event and lands in `cancelled`.
            _append_log(job_id, "cancelled while waiting for the GPU slot")
            return 1
        return _stream_subprocess(job_id, cmd)


def _delete_raw(workdir: Path) -> List[str]:
    """§6 lifecycle: remove EVERY raw artefact of the job workdir (PDF bytes,
    full-text MD). Returns the removed names for the audit log line. The
    workdir itself is removed too — nothing raw survives the job."""
    import shutil

    removed = []
    for p in sorted(workdir.glob("*")) if workdir.exists() else []:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                p.unlink()
            except OSError:
                pass
        removed.append(p.name)
    if workdir.exists():
        try:
            workdir.rmdir()
        except OSError:
            pass
    return removed


def _run_job(job_id: str) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        spec = dict(job["_spec"]) if job else None
    if spec is None:
        return

    if _is_cancelled(job_id):
        _append_log(job_id, "skipped: cancelled before it started")
        staged = Path(spec["staged_pdf"])
        if staged.exists():
            try:
                staged.unlink()
            except OSError:
                pass
        return

    # Job-scoped workdir (§6: the raw files exist ONLY here, never in the
    # document space; deleted in EVERY exit path).
    workdir = Path(spec["staged_pdf"]).parent
    pdf_path = Path(spec["staged_pdf"])
    raw_out = workdir / "raw.md"

    _set(job_id, state="running", message="docling", started_at=_now())

    # --- step 1: Docling -> raw MD (subprocess, Docling venv) ---------------
    from my_app.services.gpu_lease_client import GpuBusyError
    try:
        rc = _run_docling(job_id, pdf_path, raw_out)
    except GpuBusyError as e:
        # The gate refused the slot instead of queueing for it: the card is on a
        # long hold, the queue is full, or the wait ran out. Nothing was
        # converted — and the §6 lifecycle does not care why a job ends, so the
        # raw PDF goes before the job does.
        removed = _delete_raw(workdir)
        _append_log(job_id, f"GPU slot not free: {e}")
        _append_log(job_id, f"nicht gestartet; Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
        _set(job_id, state="error", message=f"gpu busy: {e}", finished_at=_now())
        return
    if _is_cancelled(job_id):
        removed = _delete_raw(workdir)
        _append_log(job_id, f"abgebrochen; Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
        _set(job_id, state="cancelled", message="cancelled", finished_at=_now())
        return
    if rc != 0 or not raw_out.exists():
        removed = _delete_raw(workdir)
        _set(job_id, state="error",
             message=f"docling failed (code {rc})", returncode=rc, finished_at=_now())
        _append_log(job_id, f"docling failed; Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
        return
    _append_log(job_id, "docling OK; running Szenen-Pipeline in-process…")

    # --- step 2+3: segment map (Stufe B) + capsule reduce (gate) ------------
    _set(job_id, message="szenen-pipeline")
    from my_app.services import scene_capsule_pipeline as scp

    cancel_check: Callable[[], bool] = lambda: _is_cancelled(job_id)
    try:
        raw_md = raw_out.read_text(encoding="utf-8")
        result = scp.process_document_to_capsules(
            raw_md,
            doc_id=spec["doc_id"],
            progress=lambda m: _append_log(job_id, m),
            cancel_check=cancel_check,
            max_capsules=int(spec.get("max_capsules", 30)),
        )
    except Exception as e:  # noqa: BLE001
        # ProcessingCancelled (operator abort) lands here too — the raw files
        # die either way (§6: the job ends with a bereinigtes Arbeitsverzeichnis).
        from my_app.services import knowledge_processing as kp

        cancelled = isinstance(e, kp.ProcessingCancelled)
        removed = _delete_raw(workdir)
        _append_log(job_id, f"Arbeitsverzeichnis bereinigt ({len(removed)} Dateien: PDF-Rohbytes + Volltext-MD)")
        if cancelled:
            _set(job_id, state="cancelled", message="cancelled", finished_at=_now())
        else:
            logger.exception("[SZENE-JOB] pipeline failed on %s", job_id)
            _append_log(job_id, f"pipeline error: {e}")
            _set(job_id, state="error", message=f"pipeline failed: {e}", finished_at=_now())
        return

    if result["fatal"]:
        for reason in result["fatal"]:
            _append_log(job_id, f"FATAL: {reason}")
        removed = _delete_raw(workdir)
        _set(job_id, state="error",
             message=f"pipeline failed sanity check: {result['fatal'][0]}",
             finished_at=_now())
        return

    # --- step 4: persist into the SESSION document space --------------------
    from my_app.services import upload_gate

    md_h = upload_gate.md_hash(raw_md)

    # --- step 5: §6 lifecycle — PDF-Rohbytes + Volltext-MD löschen -----------
    removed = _delete_raw(workdir)
    _append_log(
        job_id,
        f"Rohdaten gelöscht ({', '.join(removed) if removed else 'nichts'}): "
        "PDF-Rohbytes und Volltext-MD; Kapseln + Segment-Verdichtungen bleiben.",
    )

    meta = {
        "doc_id": spec["doc_id"],
        "title": spec["title"],
        "journal_id": spec["journal_id"],
        "doc_hash": spec["raw_hash"],
        "md_hash": md_h,
        "analyzed_at": result.get("analyzed_at") or _now(),
        "analysis_model": ", ".join(dict.fromkeys(result.get("models_used", []))),
        "analysis_lang": result.get("analysis_lang", "de"),
        "n_flagged_segments": result["n_flagged_segments"],
        "n_discarded_capsules": result["n_discarded_capsules"],
        "mode": result.get("mode", "standard"),
        "job_id": job_id,
    }
    d = space.store_document(
        spec["journal_id"], spec["doc_id"],
        capsules=result["capsules"], segments=result["segments"], meta=meta,
    )
    if d is None:
        _set(job_id, state="error", message="document space id unusable",
             finished_at=_now())
        return
    _append_log(
        job_id,
        f"fertig: {len(result['capsules'])} Kapseln, "
        f"{len(result['segments'])} Segment-Verdichtungen, "
        f"{result['n_flagged_segments']} Abschnitte ausgeschlossen (Schutzgründe), "
        f"{result['n_discarded_capsules']} Kapseln verworfen (Kapsel-Gate)",
    )
    _set(job_id, state="done", message="done", returncode=0, finished_at=_now())
