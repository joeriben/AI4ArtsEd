"""Document summaries in the flow — FIFO job service.

A PDF the flow's plus brings in is summarised the way the knowledge library
condenses a document: Docling turns it into raw Markdown, and
knowledge_processing.process_document condenses that into a profile, the
condensed sections and a glossary. The library procedure runs unchanged,
with two differences: the parts of a document too long for one call are
summarized at once (map_workers), and the
summary is written in the language of the surface it was brought in from.
Until 2026-09-28 this job turned a document into image-prompt "scene
capsules" (UCD-132); that was never commissioned, and it was removed.

The runner mirrors knowledge_ingest_service.py's tested idiom (keyed status
registry + circular log buffer + one worker thread):

  1. The file check (UCD-131) and the intake of the document's name run in
     the UPLOAD ROUTE, before any enqueue — rejected files are never stored,
     never queued.
  2. Docling -> raw MD, into a JOB-SCOPED workdir (a temp dir owned by this
     job; the flow's document space keeps no source files).
  3. The intake (safety_gate.check_intake, kind "document"): the text Docling
     read, scanned pages included, section by section, at the level the
     route resolved, before any of it reaches the condensation's model. A
     refused document ends the job as `blocked`, with the block message; an
     intake that gives no answer ends it as a technical fault. Either way
     nothing is stored.
  4. The library's condensation (process_document), in-process,
     provider-routed like the library run (role KNOWLEDGE_PROCESSING_MODEL).
  5. The check at the result over what the card shows: the profile, each
     condensed section and the glossary are checked one by one
     (safety_gate.check_result_text). A part that fails is withheld and
     only counted. A check that gives no answer ends the job as a technical
     fault, never as a verdict, and nothing is stored.
  6. Lifecycle: at job end — success, error, cancel, ANY outcome — the raw
     PDF bytes AND the extracted full-text MD are DELETED. A backend restart
     ends the jobs without that step, because they live in memory; the next
     start clears what they staged (`sweep_staging`).
  7. Persist into the SESSION document space (scene_document_space):
     summary.json + document.json (provenance incl. docHash).

Duplicate protection: the route looks for a stored summary of the same file in
every session before enqueue (`take_summary`, which checks it again at the
level of the session) and answers with the existing doc_id. A job asks the same
question when its turn comes, because a job queued behind the same document
could not get that answer yet.

The GPU slot (CLAUDE.md rule 15, UCD-141): step 2 holds the plant-wide lease
"docling" for as long as the Docling process runs — the same venv, and the same
finding, as knowledge_ingest_service: Docling's OCR and layout models select
cuda:0 wherever they find a card (UCD-132 E2E, 2026-09-27). The conflict
behaviour is the gate's own: a summary job that starts while a generation runs
WAITS in the gate's queue until the generation ends, and a generation that
starts while a conversion runs waits the same way for the conversion. Only the
gate's own refusals end the job instead of queueing it — a full queue, a wait
past its budget, a long hold such as a LoRA training — and the §6 lifecycle
holds on that path too: the raw PDF is deleted before the job goes to `error`.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Tuple

from my_app.services import scene_document_space as space
from my_app.services.safety_gate import check_intake, check_result_text, safety_block

logger = logging.getLogger(__name__)

_LOG_MAX = 1000

# How many summary calls of the condensation run at once. A document up to
# knowledge_processing._DOC_UNIT_MAX_CHARS is one call; the parts of a longer
# one the library runs one after another. Under the per-section procedure
# (until 2026-11-13) a document of 35 sections took eleven minutes that way
# on 2026-09-28, with a group waiting at the board. The calls go to the
# provider of KNOWLEDGE_PROCESSING_MODEL, whose fallback chain answers when
# one provider refuses.
SUMMARY_MAP_WORKERS = 6

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
        if job["state"] in ("done", "error", "cancelled", "blocked"):
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


class DuplicateJobError(Exception):
    """The same document of the same session is already queued or running."""

    def __init__(self, job_id: str, doc_id: str):
        super().__init__(f"job {job_id} already summarises {doc_id}")
        self.job_id = job_id
        self.doc_id = doc_id


def _active_job_for(journal_id: str, raw_hash: str) -> Optional[Dict[str, Any]]:
    """The queued or running job of this session for this document hash, if
    any. The caller holds _JOBS_LOCK."""
    for job in _JOBS.values():
        spec = job.get("_spec") or {}
        if (job["state"] in ("queued", "running")
                and spec.get("journal_id") == journal_id
                and spec.get("raw_hash") == raw_hash):
            return job
    return None


def find_active_job(journal_id: str, raw_hash: str) -> Optional[Dict[str, Any]]:
    """Public view of the job summarising this document in this session right
    now (queued or running), or None. The session space only knows finished
    documents; this covers the minutes before that."""
    with _JOBS_LOCK:
        job = _active_job_for(journal_id, raw_hash)
        return _public_view(job, 0) if job else None


def enqueue_scene_ingest(
    *,
    journal_id: str,
    title: str,
    staged_pdf: Path,
    raw_hash: str,
    doc_id: str,
    lang: str,
    safety_level: str,
) -> str:
    """Register a summary job and return its job_id. The route has ALREADY
    run the Stage-A gate and staged the PDF into a job temp dir; the worker
    deletes ALL raw artefacts at job end. `lang` is the language the summary
    is written in (the surface's), `safety_level` the level the route
    resolved at the request boundary: the worker thread has no session to
    resolve it from (safety_level_resolver)."""
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        # Checked and registered under one lock: two uploads of one document
        # arriving together cannot both pass.
        active = _active_job_for(journal_id, raw_hash)
        if active is not None:
            raise DuplicateJobError(active["job_id"], active["doc_id"])
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
            # Sections condensed / total, once the condensation knows its
            # units (on_progress); None while the job waits or converts.
            "progress": None,
            "_log": deque(maxlen=_LOG_MAX),
            "_cancel": threading.Event(),
            "_proc": None,
            "_spec": {
                "journal_id": journal_id,
                "doc_id": doc_id,
                "title": title,
                "staged_pdf": str(staged_pdf),
                "raw_hash": raw_hash,
                "lang": lang,
                "safety_level": safety_level,
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
        "progress": job.get("progress"),
        # Where the intake refused the document: the kind of refusal and the
        # section, never what was found, for the list is open to every caller.
        "safety_block": job.get("safety_block"),
        "log_tail": log,
    }


def _drop_raw_of(job_id: str) -> None:
    """The §6 lifecycle for a job that crashed: no path of `_run_job` got to
    delete its raw files."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        staged = job["_spec"]["staged_pdf"] if job else None
    if staged:
        _delete_raw(Path(staged).parent)


def _worker_loop() -> None:
    while True:
        job_id = _QUEUE.get()
        try:
            _run_job(job_id)
        except Exception as e:  # noqa: BLE001 - never let the worker die
            logger.exception("[SZENE-JOB] worker crash on %s", job_id)
            _append_log(job_id, f"CRITICAL: worker error: {e}")
            _drop_raw_of(job_id)
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
        _set(job_id, message="docling")
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


def _staging_root() -> Path:
    """Where this backend stages raw files. One directory per port, because
    several backends share a machine and `sweep_staging` may clear only its
    own."""
    from config import PORT

    return Path(tempfile.gettempdir()) / f"scene_pdf_{os.getenv('PORT', PORT)}"


def new_staging_dir() -> Path:
    """A workdir for one job, readable by this user alone."""
    root = _staging_root()
    root.mkdir(mode=0o700, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=root))


def sweep_staging() -> int:
    """Delete what an earlier run of this backend staged and return how many
    workdirs went. Called once at server start, when no job exists: jobs live
    in memory, so a restart ends them, and no `_delete_raw` comes for their
    files."""
    root = _staging_root()
    if not root.is_dir():
        return 0
    stale = [p for p in root.iterdir() if p.is_dir()]
    for p in stale:
        shutil.rmtree(p, ignore_errors=True)
    if stale:
        logger.info("[SZENE-JOB] cleared %d workdirs of an earlier run", len(stale))
    return len(stale)


def summary_from_markdown(md: str) -> Dict[str, Any]:
    """The parts of a library condensation the document card shows: the
    profile, the condensed sections, the glossary. Read with the library's
    own section readers (knowledge_library), the file format being theirs."""
    from my_app.services import knowledge_library as kl

    top = kl._admin_top_sections(md)
    return {
        "profile": top.get("PROFIL", "").strip(),
        "sections": _wissen_sections(top.get("WISSEN", "")),
        "glossary": [
            {"term": g["term"], "definition": g["definition"]}
            for g in kl._admin_parse_glossary(top.get("GLOSSAR", ""))
        ],
    }


_WISSEN_HEADING_RE = re.compile(r"^###\s+(.*\S)\s*$")
_QUELLE_RE = re.compile(r"<!--\s*quelle:.*?-->", re.DOTALL)


def _wissen_sections(wissen: str) -> List[Dict[str, str]]:
    """The ### subsections of WISSEN as heading + body. The review anchors
    (<!-- quelle: … -->) are curation plumbing and stay out, as in the
    library's own read-only view (KnowledgeLibraryTab.vue parseWissenSections)."""
    out: List[Dict[str, str]] = []
    heading: Optional[str] = None
    body: List[str] = []

    def _flush() -> None:
        text = _QUELLE_RE.sub("", "\n".join(body)).strip()
        if heading or text:
            out.append({"heading": (heading or "").strip(), "body": text})

    for line in (wissen or "").splitlines():
        m = _WISSEN_HEADING_RE.match(line)
        if m:
            _flush()
            heading, body = m.group(1), []
        else:
            body.append(line)
    _flush()
    return out


# The longest piece of a document the intake asks about at once: about what
# the condensation hands its model per call (knowledge_processing,
# _PACK_TARGET_CHARS). A section without headings, as a scanned page often
# is, is cut between its paragraphs.
_INTAKE_SECTION_CHARS = 9000
_HEADING_LINE_RE = re.compile(r"^#{1,6}\s")


def document_sections(md: str) -> List[str]:
    """The document's text as the intake takes it in: one string per section,
    from one Markdown heading to the next, none longer than
    _INTAKE_SECTION_CHARS. Every word of the text is in one of them: the
    condensation reads all of it."""
    groups: List[List[str]] = [[]]
    for line in (md or "").splitlines():
        if _HEADING_LINE_RE.match(line) and groups[-1]:
            groups.append([])
        groups[-1].append(line)
    sections: List[str] = []
    for lines in groups:
        sections += _pieces("\n".join(lines).strip(), _INTAKE_SECTION_CHARS)
    return sections


def _pieces(text: str, limit: int) -> List[str]:
    """`text` in pieces of at most `limit` characters: cut at the last
    paragraph break before the limit, else at the last space, else at the
    limit itself."""
    pieces: List[str] = []
    while len(text) > limit:
        cut = text.rfind("\n\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        pieces.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        pieces.append(text)
    return pieces


def _check_summary(summary: Dict[str, Any],
                   safety_level: str) -> Tuple[Dict[str, Any], int]:
    """The check at the result over every part the card shows, each part on
    its own: the profile, each condensed section (heading and text), the
    glossary (safety_gate.check_result_text, at the level the route
    resolved). A part that fails is withheld and counted, never shown. A
    check that gives no answer raises: a technical fault is never a verdict,
    and the caller ends the job without storing anything.
    """
    def passes(text: str, field: str) -> bool:
        verdict = check_result_text(text, level=safety_level, field=field)
        if verdict.operational:
            raise RuntimeError("the check at the result gave no answer")
        return verdict.passed

    withheld = 0
    profile = summary["profile"]
    if profile and not passes(profile, "profile"):
        profile = ""
        withheld += 1
    sections: List[Dict[str, str]] = []
    for i, s in enumerate(summary["sections"]):
        if passes(f"{s['heading']}\n\n{s['body']}", f"sections[{i}]"):
            sections.append(s)
        else:
            withheld += 1
    glossary = summary["glossary"]
    if glossary and not passes(
            "\n".join(f"{g['term']}: {g['definition']}" for g in glossary), "glossary"):
        glossary = []
        withheld += 1
    return {"profile": profile, "sections": sections, "glossary": glossary}, withheld


def take_summary(journal_id: str, raw_hash: str, *, title: str, lang: str,
                 safety_level: str) -> Optional[Dict[str, Any]]:
    """This file's stored summary as a document of this session, or None when
    there is none in `lang` (scene_document_space.find_summary).

    Reuse spares the text recognition and the condensation, and nothing else:
    every part goes through the check again, at the level of this session and
    against today's lists. So a stricter session can use a summary from a looser
    one, and a list tightened since counts. What the check withholds now joins
    the count of what was withheld before. A check that gives no answer raises,
    as in the job. Which stored copies a session may start from at all is
    `find_summary`'s to say.

    The title is the one this upload brought, because the first uploader's file
    name is theirs and the check never reads it. The session the summary came
    from is not recorded.
    """
    found = space.find_summary(raw_hash, lang=lang, safety_level=safety_level)
    if found is None:
        return None
    meta, summary = found
    checked, n_withheld = _check_summary(summary, safety_level)
    meta.pop("job_id", None)
    meta.update(
        title=title,
        journal_id=journal_id,
        safety_level=space.stricter_level(meta["safety_level"], safety_level),
        n_withheld=int(meta.get("n_withheld", 0)) + n_withheld,
    )
    doc_id = space.doc_id_for(raw_hash)
    if space.store_document(journal_id, doc_id, summary=checked, meta=meta) is None:
        return None
    return space.get_document(journal_id, doc_id)


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

    # "gpu-wait" until the gate admits the conversion (_run_docling), then
    # "docling". The card's status line reads neither and says text recognition
    # for both. Running from here on: a cancel reaches the job through its flag.
    _set(job_id, state="running", message="gpu-wait", started_at=_now())

    # Queued behind the same document of another session, this job finds the
    # finished summary here: at its upload there was none yet.
    try:
        known = take_summary(spec["journal_id"], spec["raw_hash"], title=spec["title"],
                             lang=spec["lang"], safety_level=spec["safety_level"])
    except RuntimeError as e:
        # No answer from the check is a technical fault, never a verdict (step 5).
        removed = _delete_raw(workdir)
        logger.error("[SZENE-JOB] safety check gave no answer on %s: %s", job_id, e)
        _append_log(job_id, f"safety check gave no answer: {e}; "
                            f"Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
        _set(job_id, state="error", message="check-unavailable", finished_at=_now())
        return
    if known is not None:
        removed = _delete_raw(workdir)
        _append_log(job_id, f"already summarised; Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
        _set(job_id, state="done", message="done", returncode=0, finished_at=_now())
        return

    # --- step 2: Docling -> raw MD (subprocess, Docling venv) ---------------
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
    _append_log(job_id, "docling OK; taking the text in at the intake…")

    # --- step 3: the intake: what the document says, as the converter read
    # it, before any of it reaches the condensation's model ----------------
    _set(job_id, message="intake")
    try:
        raw_md = raw_out.read_text(encoding="utf-8")
        verdict = check_intake(document_sections(raw_md), level=spec["safety_level"],
                               kind="document", field="document")
    except Exception as e:  # noqa: BLE001
        # A check that raised checked nothing: a technical fault, never a verdict.
        removed = _delete_raw(workdir)
        logger.error("[SZENE-JOB] intake failed on %s: %s", job_id, e)
        _append_log(job_id, f"intake failed; Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
        _set(job_id, state="error", message="check-unavailable", finished_at=_now())
        return
    if not verdict.passed:
        removed = _delete_raw(workdir)
        if verdict.operational:
            _append_log(job_id, f"intake gave no answer; "
                                f"Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
            _set(job_id, state="error", message="check-unavailable", finished_at=_now())
        else:
            _append_log(job_id, f"intake refused the document ({verdict.reason_key}); "
                                f"Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
            _set(job_id, state="blocked", message="blocked", finished_at=_now(),
                 safety_block=safety_block(verdict.checkpoint, verdict.reason_key,
                                           field=verdict.field))
        return
    if _is_cancelled(job_id):
        removed = _delete_raw(workdir)
        _append_log(job_id, f"abgebrochen; Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
        _set(job_id, state="cancelled", message="cancelled", finished_at=_now())
        return
    _append_log(job_id, "intake passed; running the library condensation in-process…")

    # --- step 4: the library's condensation (knowledge_processing) ---------
    _set(job_id, message="summary")
    from my_app.services import knowledge_processing as kp
    from my_app.services.knowledge_extract import from_markdown

    cancel_check: Callable[[], bool] = lambda: _is_cancelled(job_id)
    try:
        # The card reads the Markdown text: no image description runs on this
        # path and the workdir dies with the job, so the figures of the block
        # export would stand on the card as pending notes naming files.
        result = kp.process_document(
            from_markdown(raw_md),
            {"id": spec["doc_id"], "titel": spec["title"]},
            progress=lambda m: _append_log(job_id, m),
            target_lang=spec["lang"],
            cancel_check=cancel_check,
            on_progress=lambda done, total: _set(
                job_id, progress={"units_done": done, "units_total": total}),
            map_workers=SUMMARY_MAP_WORKERS,
        )
    except Exception as e:  # noqa: BLE001
        # ProcessingCancelled (operator abort) lands here too — the raw files
        # die either way: the job ends with a cleaned workdir.
        cancelled = isinstance(e, kp.ProcessingCancelled)
        removed = _delete_raw(workdir)
        _append_log(job_id, f"Arbeitsverzeichnis bereinigt ({len(removed)} Dateien: PDF-Rohbytes + Volltext-MD)")
        if cancelled:
            _set(job_id, state="cancelled", message="cancelled", finished_at=_now())
        else:
            logger.exception("[SZENE-JOB] summary failed on %s", job_id)
            _append_log(job_id, f"summary error: {e}")
            _set(job_id, state="error", message=f"summary failed: {e}", finished_at=_now())
        return

    if result.fatal:
        for reason in result.fatal:
            _append_log(job_id, f"FATAL: {reason}")
        removed = _delete_raw(workdir)
        _set(job_id, state="error",
             message=f"summary failed sanity check: {result.fatal[0]}",
             finished_at=_now())
        return

    # --- step 5: the check at the result over what the card shows ---------
    try:
        summary = summary_from_markdown(result.markdown)
    except Exception as e:  # noqa: BLE001
        removed = _delete_raw(workdir)
        logger.exception("[SZENE-JOB] summary unreadable on %s", job_id)
        _set(job_id, state="error", message=f"summary unreadable: {e}", finished_at=_now())
        return
    _set(job_id, message="check")
    try:
        summary, n_withheld = _check_summary(summary, spec["safety_level"])
    except Exception as e:  # noqa: BLE001
        # No answer from the check is a technical fault, never a verdict
        # (safety_classifier): nothing is stored, and the card says so.
        removed = _delete_raw(workdir)
        logger.error("[SZENE-JOB] safety check gave no answer on %s: %s", job_id, e)
        _append_log(job_id, f"safety check gave no answer: {e}; "
                            f"Arbeitsverzeichnis bereinigt ({len(removed)} Dateien)")
        _set(job_id, state="error", message="check-unavailable", finished_at=_now())
        return

    from my_app.services import upload_gate

    md_h = upload_gate.md_hash(raw_md)

    # --- step 6: lifecycle — PDF-Rohbytes + Volltext-MD löschen ------------
    removed = _delete_raw(workdir)
    _append_log(
        job_id,
        f"Rohdaten gelöscht ({', '.join(removed) if removed else 'nichts'}): "
        "PDF-Rohbytes und Volltext-MD; die Zusammenfassung bleibt.",
    )

    # --- step 7: persist into the SESSION document space -------------------
    meta = {
        "doc_id": spec["doc_id"],
        "title": spec["title"],
        "journal_id": spec["journal_id"],
        "doc_hash": spec["raw_hash"],
        "md_hash": md_h,
        "analyzed_at": result.analyzed_at or _now(),
        "analysis_model": result.analysis_model,
        "analysis_lang": result.analysis_lang,
        "safety_level": spec["safety_level"],
        "n_withheld": n_withheld,
        "job_id": job_id,
    }
    d = space.store_document(spec["journal_id"], spec["doc_id"],
                             summary=summary, meta=meta)
    if d is None:
        _set(job_id, state="error", message="document space id unusable",
             finished_at=_now())
        return
    _append_log(
        job_id,
        f"fertig: Profil {'da' if summary['profile'] else 'zurückgehalten'}, "
        f"{len(summary['sections'])} Abschnitte, "
        f"{len(summary['glossary'])} Glossar-Begriffe, "
        f"{n_withheld} Teile von der Prüfung zurückgehalten",
    )
    _set(job_id, state="done", message="done", returncode=0, finished_at=_now())
