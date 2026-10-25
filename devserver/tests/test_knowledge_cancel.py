"""
Tests for ingest-job cancellation (Settings/curation, BIBLIOTHEK.md §9).

Feature: an operator can abort an ingest job — one that is still queued (dropped
from the FIFO) or one that is running (asked to stop at the next step boundary,
with any in-flight Docling/reindex subprocess terminated). What a cancelled
run removes depends on WHICH KIND of job it is: a fresh upload's cancel
removes its own unfinished artefacts (the partial compact draft + the raw.md
intermediate) but keeps the original upload; a reprocess's cancel removes
NEITHER, because its draft and raw.md pre-date the run -- they are the
operator's existing, good analysis and (for documents with no PDF fallback)
the only stored copy of the source. Conflating the two was a data-destroying
bug.

Three route-level cases + one load-bearing unit test + one FIFO-worker
robustness test + one reprocess-vs-fresh-upload pair (this data-destroying
cancel bug's fix):
  * queued job -> POST /jobs/<id>/cancel flips it to `cancelled` and it never
    runs (verified by holding the single worker busy with a gate).
  * running job -> the Verdichtung Map loop honours the per-job cancel_check at
    a unit boundary (stub LLM trips the cancel on its first Map call); the job
    lands in `cancelled` and its partial draft + raw.md are gone.
  * cancel on a finished (done) job -> 409.
  * knowledge_processing.process_document raises ProcessingCancelled BETWEEN Map
    calls when cancel_check turns true (pure unit test, no Flask, no worker).
  * a FATAL sanity-check abort (CLAUDE.md rule 12) on one document must not
    wedge the shared FIFO worker: the next queued document still has to run.
  * a cancelled FRESH upload still removes its own partial draft + raw.md
    (made explicit, unchanged) -- but a cancelled REPROCESS removes NEITHER,
    proven with byte-identical before/after content on both files.

The Verdichtung LLM is stubbed throughout (no provider call). The --md
passthrough ingest needs no Docling (interpreter = current python).

Run: python3 -m pytest devserver/tests/test_knowledge_cancel.py -q
"""

import importlib
import io
import sys
import threading
import time
from pathlib import Path

# devserver/tests/... -> parents[1] == devserver/ (same convention as the other
# knowledge/resona tests).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


# A raw (Docling-style) input Markdown for the --md passthrough path, long enough
# for a couple of content sections (so the Map loop has >1 unit to step through).
_MINI_MD = """# Mini Operator Doc

## Einleitung

Ein kurzes Betreiberdokument ueber dekoloniale Kunstpaedagogik und kulturelle Resilienz. Es baut auf vorhandenen Diskursen auf und richtet sich an die mediale und performative Praxis. Das Dokument entstand aus einer Reihe von Werkstattgespraechen mit Kulturschaffenden, die seit mehreren Jahren an Schulen und in ausserschulischen Bildungsformaten arbeiten und dabei immer wieder auf koloniale Kontinuitaeten in Lehrplaenen und Materialien stossen.

## Abschnitt Eins

Etwas mehr Fliesstext, damit der Struktur-Chunker mindestens einen inhaltstragenden Abschnitt erzeugt. Konkrete Massnahme: drei Schritte, Mindestalter 12, Evaluation alle 6 Monate. Beispiel: ein Projekt mit 30 Teilnehmenden im Jahr 2025. Die drei Schritte umfassen erstens eine Bestandsaufnahme der verwendeten Materialien, zweitens eine Schulung des Lehrpersonals zu kolonialen Bildsprachen und drittens eine externe Begutachtung durch eine Fachstelle vor der Veroeffentlichung.

## Abschnitt Zwei

Noch ein inhaltstragender Abschnitt mit weiteren konkreten Angaben: Budget von 5000 Euro, Laufzeit ueber zwoelf Monate, drei Standorte in der Region und eine Kohorte von 25 Lernenden pro Durchgang. Die Finanzierung erfolgt ueber eine Mischung aus kommunalen Mitteln und einer externen Foerderung, die zunaechst auf drei Jahre befristet ist und danach evaluiert werden soll.
"""


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Flask test client with all knowledge storage redirected into tmp_path and
    the ingest interpreter = current python (the --md path needs no Docling).
    The Verdichtung LLM is stubbed PER TEST (each test sets kp.default_llm_fn to
    a stub with the behaviour it needs), so the fixture leaves it unset."""
    import config

    tier_o = tmp_path / "knowledge_library"
    originals = tmp_path / "resources" / "knowledge_originals"
    lib = tmp_path / "library"
    (lib / "unesco").mkdir(parents=True)
    db = tmp_path / "knowledge_index.sqlite"
    overrides = tmp_path / "json" / "knowledge_glossary_overrides.json"

    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tier_o, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_ORIGINALS_DIR", originals, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_DIR", lib, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", db, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_GLOSSARY_OVERRIDES", overrides, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INGEST_PYTHON", sys.executable, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_PYTHON", sys.executable, raising=False)

    # Fresh processing module so a per-test default_llm_fn stub never leaks.
    import my_app.services.knowledge_processing as kp
    importlib.reload(kp)
    # The service module owns the single FIFO worker thread + queue; do NOT
    # reload it (a reload would orphan the running worker and its Queue). Instead
    # drain any job left running/queued by a previous test (the shared worker is
    # single-threaded, so a still-busy worker would otherwise pick up THIS test's
    # job late — and a previous test's LLM stub could fire against it), then clear
    # the in-memory registry so a test only sees its own jobs.
    import my_app.services.knowledge_ingest_service as jobs
    _deadline = time.time() + 30
    while time.time() < _deadline:
        with jobs._JOBS_LOCK:
            busy = any(j["state"] in ("queued", "running") for j in jobs._JOBS.values())
        if not busy:
            break
        time.sleep(0.05)
    with jobs._JOBS_LOCK:
        jobs._JOBS.clear()

    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    kl._QUERY_TRANSLATION_CACHE.clear()

    from my_app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()
    yield client, kp, jobs, kl, config

    # Teardown: drain any job THIS test left queued/running to a terminal
    # state BEFORE returning control to pytest's fixture-teardown chain.
    # `monkeypatch` (this fixture's own dependency) reverts KNOWLEDGE_TIER_O_DIR
    # / KNOWLEDGE_ORIGINALS_DIR / KNOWLEDGE_LIBRARY_DIR / KNOWLEDGE_INDEX_DB /
    # KNOWLEDGE_GLOSSARY_OVERRIDES / KNOWLEDGE_INGEST_PYTHON /
    # KNOWLEDGE_INDEX_PYTHON back to their PRODUCTION values as ITS OWN
    # teardown, which fires immediately after this generator resumes (pytest
    # tears fixtures down in reverse dependency order, so this code runs
    # BEFORE monkeypatch's revert). The single FIFO worker thread is a
    # module-level singleton that outlives every individual test BY DESIGN
    # (see the drain-then-clear above -- it is never reloaded), and
    # knowledge_ingest_service.py resolves every one of those config values
    # fresh, via a plain `from config import ...` INSIDE _run_docling /
    # _run_verdichtung / _run_reindex, at the moment each step actually runs
    # -- not once at job start. A job this test released (e.g. from behind a
    # gate, in a `finally` block) but never itself waited out can therefore
    # still be mid-flight on that thread when monkeypatch reverts -- and its
    # very next config lookup silently returns the REAL production paths
    # instead of this test's tmp_path: a stray draft written into the real
    # Tier-O library, and/or a real reindex invoked against the real,
    # live-served knowledge_index.sqlite. Confirmed with an isolated
    # reproduction (fake prod dirs, no real data at risk): both the draft
    # write and the reindex subprocess call picked up the reverted paths the
    # moment they lagged behind a revert, and confirmed live via instrumented
    # runs of this very file (both at this commit and at the pre-Verdichtungs-
    # Umbau baseline -- same fixture, same latent race): a leftover job
    # intermittently lands in state=error with "reindex failed" or with the
    # production (unstubbed) LLM path having been invoked instead of the
    # test's stub. Waiting here, before yield's caller tears monkeypatch
    # down, closes that window.
    _deadline = time.time() + 30
    while time.time() < _deadline:
        with jobs._JOBS_LOCK:
            busy = any(j["state"] in ("queued", "running") for j in jobs._JOBS.values())
        if not busy:
            break
        time.sleep(0.05)


def _upload(client, filename="mini.md", title="Mini Operator Doc", content=_MINI_MD):
    data = {
        "title": title,
        "lizenz": "CC BY 4.0",
        "autor": "Tester",
        "year": "2026",
        "lang": "de",
        "document": (io.BytesIO(content.encode("utf-8")), filename),
    }
    return client.post("/api/knowledge/upload", data=data,
                       content_type="multipart/form-data")


def _wait_state(client, job_id, states, timeout=30):
    """Poll GET /jobs/<id> until state is in `states` (a set), or timeout."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/knowledge/jobs/{job_id}").get_json()
        if last and last["state"] in states:
            return last
        time.sleep(0.1)
    return last


# ---------------------------------------------------------------------------
# 1) queued -> cancel drops it from the FIFO; it never runs
# ---------------------------------------------------------------------------

def test_cancel_queued_job_removes_from_queue(app_client):
    client, kp, jobs, _, _ = app_client

    # A gate the FIRST job's LLM blocks on, so the single worker stays busy and
    # the SECOND job sits in `queued` for as long as we need.
    gate = threading.Event()

    def _blocking_llm(temperature: float = 0.2):
        def _fn(system, user, max_tokens):
            gate.wait(timeout=20)  # hold the worker on job #1
            if "PROFIL" in system:
                return "Profil."
            import json as _json
            return _json.dumps({"section_title": "A", "digest": "x",
                                "terms": []}, ensure_ascii=False)
        return _fn

    kp.default_llm_fn = _blocking_llm

    try:
        first = _upload(client, filename="first.md", title="First").get_json()
        # Wait until job #1 is actually running (worker occupied).
        _wait_state(client, first["job_id"], {"running"})

        second = _upload(client, filename="second.md", title="Second").get_json()
        # Job #2 is still queued (worker is busy on #1).
        snap = client.get(f"/api/knowledge/jobs/{second['job_id']}").get_json()
        assert snap["state"] == "queued", snap

        # Cancel the queued job -> cancelled immediately, tombstoned in the FIFO.
        r = client.post(f"/api/knowledge/jobs/{second['job_id']}/cancel")
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["success"] is True and body["state"] == "cancelled"
    finally:
        # Always release job #1 so the shared worker never stays blocked (which
        # would hang the next test's drain barrier).
        gate.set()

    # The worker dequeues the tombstoned #2 and skips it.
    end = _wait_state(client, second["job_id"], {"cancelled"})
    assert end["state"] == "cancelled", end
    # It never produced a draft (it was cancelled before running).
    import config
    assert not (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{second['doc_id']}.md").exists()
    # And it never transitioned through running/done (message names the cause).
    assert "queue" in (end["message"] or "").lower() or any(
        "queued" in ln.lower() for ln in end.get("log_tail", []))


# ---------------------------------------------------------------------------
# 2) running -> abort at a Verdichtung unit boundary; artefacts cleaned up
# ---------------------------------------------------------------------------

def test_cancel_running_job_aborts_at_unit_boundary_and_cleans_up(app_client):
    client, kp, jobs, _, config = app_client

    # The stub trips THIS job's cancel on its first Map call, so process_document
    # raises ProcessingCancelled at the boundary after unit 1. We learn the
    # job_id from the upload response and set the cancel via the service.
    state = {"job_id": None, "map_calls": 0}

    def _cancelling_llm(temperature: float = 0.2):
        def _fn(system, user, max_tokens):
            if "PROFIL" in system:
                return "Profil."
            state["map_calls"] += 1
            # On the first Map call, request cancel for this job so the loop's
            # post-unit cancel_check fires before the next unit. Guard on the job
            # actually being `running` (a Map call only happens during running;
            # this also makes the intent explicit).
            if state["map_calls"] == 1 and state["job_id"]:
                snap = jobs.get_job(state["job_id"])
                if snap and snap["state"] == "running":
                    jobs.request_cancel(state["job_id"])
            import json as _json
            return _json.dumps({"section_title": "A", "digest": "x",
                                "terms": []}, ensure_ascii=False)
        return _fn

    kp.default_llm_fn = _cancelling_llm

    body = _upload(client).get_json()
    state["job_id"] = body["job_id"]
    doc_id = body["doc_id"]

    end = _wait_state(client, body["job_id"], {"cancelled", "done", "error"})
    assert end is not None and end["state"] == "cancelled", end

    # The Map loop ran at least once but did NOT process every unit (aborted).
    assert state["map_calls"] >= 1

    # Artefact cleanup: the partial compact draft and the raw.md intermediate of
    # THIS run are gone; the log records the cleanup + that the original is kept.
    draft = Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md"
    raw = Path(config.KNOWLEDGE_ORIGINALS_DIR) / "operator" / f"{doc_id}.raw.md"
    assert not draft.exists(), "partial draft must be removed on cancel"
    assert not raw.exists(), "raw intermediate must be removed on cancel"
    log = " ".join(end.get("log_tail", []))
    assert "original upload kept" in log.lower()

    # The cancelled doc is not in the Tier-O inventory (never reindexed in).
    items = client.get("/api/knowledge/items").get_json()["items"]
    assert all(i["doc_id"] != doc_id for i in items)


# ---------------------------------------------------------------------------
# 3) cancel on a finished (done) job -> 409
# ---------------------------------------------------------------------------

def test_cancel_done_job_conflicts(app_client):
    client, kp, jobs, _, _ = app_client

    def _stub_llm(temperature: float = 0.2):
        def _fn(system, user, max_tokens):
            if "PROFIL" in system:
                return "Profil ueber Resilienz."
            import json as _json
            return _json.dumps({
                "section_title": "Massnahmen",
                "digest": "- drei Schritte\n- Mindestalter 12",
                "terms": [],
            }, ensure_ascii=False)
        return _fn

    kp.default_llm_fn = _stub_llm

    body = _upload(client).get_json()
    end = _wait_state(client, body["job_id"], {"done", "error"}, timeout=60)
    assert end is not None and end["state"] == "done", end

    r = client.post(f"/api/knowledge/jobs/{body['job_id']}/cancel")
    assert r.status_code == 409, r.get_json()
    assert "done" in (r.get_json().get("error", "") + r.get_json().get("state", "")).lower()


def test_cancel_unknown_job_404(app_client):
    client, *_ = app_client
    r = client.post("/api/knowledge/jobs/does-not-exist/cancel")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 4) load-bearing unit test: process_document honours cancel_check BETWEEN units
# ---------------------------------------------------------------------------

def test_process_document_raises_between_map_calls():
    """The cancel poll sits at the unit boundary: with >1 unit and a cancel_check
    that turns true after the first Map call, process_document raises
    ProcessingCancelled and does NOT map every unit. No Flask, no worker."""
    import my_app.services.knowledge_processing as kp
    importlib.reload(kp)

    calls = {"map": 0}
    flip = {"cancel": False}

    def _llm(system, user, max_tokens):
        if "PROFIL" in system:
            return "Profil."
        calls["map"] += 1
        # After the first unit is condensed, ask to cancel.
        if calls["map"] == 1:
            flip["cancel"] = True
        import json as _json
        return _json.dumps({"section_title": "A", "digest": "x",
                            "terms": []}, ensure_ascii=False)

    fm = {"id": "unit-cancel-doc", "titel": "T", "tier": "O",
          "sparten": [], "themen": [], "status": "draft"}

    with pytest.raises(kp.ProcessingCancelled) as ei:
        kp.process_document(
            _MINI_MD, fm, llm=_llm,
            cancel_check=lambda: flip["cancel"],
            mode="standard",
        )
    # Aborted after the first unit — not every unit was mapped.
    assert ei.value.units_done == 1
    assert calls["map"] == 1


def test_process_document_cancel_before_first_unit():
    """A cancel already true before the Map loop -> raise with units_done=0 and
    zero Map calls."""
    import my_app.services.knowledge_processing as kp
    importlib.reload(kp)

    calls = {"map": 0}

    def _llm(system, user, max_tokens):
        if "PROFIL" in system:
            return "Profil."
        calls["map"] += 1
        import json as _json
        return _json.dumps({"section_title": "A", "digest": "x",
                            "terms": []}, ensure_ascii=False)

    fm = {"id": "pre-cancel-doc", "titel": "T", "tier": "O",
          "sparten": [], "themen": [], "status": "draft"}

    with pytest.raises(kp.ProcessingCancelled) as ei:
        kp.process_document(_MINI_MD, fm, llm=_llm,
                            cancel_check=lambda: True, mode="standard")
    assert ei.value.units_done == 0
    assert calls["map"] == 0


# ---------------------------------------------------------------------------
# 5) a FATAL sanity-check abort must not wedge the shared FIFO worker: the
#    NEXT queued document still has to run (BIBLIOTHEK.md §9 + CLAUDE.md rule
#    12 -- the owner's next bulk re-analysis is ~30 documents through this
#    SAME single worker; one bad document must not starve the rest).
# ---------------------------------------------------------------------------

_POISON_MD = """# Poison Doc

## Ausfallabschnitt Eins

PROVIDERAUSFALL simuliert einen vollstaendigen Ausfall des Sprachmodell-Anbieters fuer dieses eine Dokument, damit die Sanity-Pruefung im Verdichtungsschritt zuverlaessig als FATAL erkannt wird. Der Text ist absichtlich lang genug gehalten, damit der Struktur-Chunker eine reguläre inhaltstragende Einheit erzeugt, obwohl die gestellte Antwort fuer diese Einheit vollstaendig unbrauchbar bleibt und daher als fehlend gilt.

## Ausfallabschnitt Zwei

Auch dieser zweite Abschnitt traegt PROVIDERAUSFALL im Fliesstext, damit mehrere Einheiten entstehen und die Verdichtung trotzdem komplett fehlschlaegt, weil jede Map-Antwort ungueltiges JSON liefert und als fehlend gezaehlt wird.
"""


def test_fatal_middle_job_does_not_wedge_the_fifo_worker(app_client):
    """Three jobs, back-to-back, through the ONE shared FIFO worker: a good
    document, a document whose every Verdichtung call returns unparsable
    content (simulating the all-404 provider outage CLAUDE.md rule 12 guards
    against), and a second good document. The middle job must abort as a
    FATAL sanity-check failure (state=error) -- never `cancelled` (its cancel
    Event is never set) -- and, critically, the worker must not get stuck on
    it: the THIRD job has to reach `done` regardless. This is the exact shape
    of the owner's next bulk re-analysis (many documents through the same
    single worker) -- one bad document must not starve the rest of the batch.
    """
    client, kp, jobs, _, _ = app_client

    def _mixed_llm(temperature: float = 0.2):
        def _fn(system, user, max_tokens):
            if "PROFIL" in system:
                return "Profil."
            if "PROVIDERAUSFALL" in user:
                # Unparsable on both the first attempt AND the one repair
                # retry _map_unit gives it -> the unit is recorded MISSING.
                return "not a json object at all"
            import json as _json
            return _json.dumps({
                "section_title": "Massnahmen",
                "digest": "- drei Schritte\n- Mindestalter 12",
                "terms": [],
            }, ensure_ascii=False)
        return _fn

    kp.default_llm_fn = _mixed_llm

    # Enqueue all three before waiting on any of them: the single FIFO worker
    # (BIBLIOTHEK.md §9) processes them strictly in order, so job B is
    # guaranteed to run to completion (successfully or not) before job C is
    # even dequeued.
    a = _upload(client, filename="a.md", title="Doc A").get_json()
    b = _upload(client, filename="b.md", title="Doc B (poison)",
                content=_POISON_MD).get_json()
    c = _upload(client, filename="c.md", title="Doc C").get_json()

    end_a = _wait_state(client, a["job_id"], {"done", "error", "cancelled"}, timeout=60)
    assert end_a is not None and end_a["state"] == "done", end_a

    end_b = _wait_state(client, b["job_id"], {"done", "error", "cancelled"}, timeout=60)
    assert end_b is not None and end_b["state"] == "error", end_b
    assert "sanity check" in (end_b["message"] or "").lower(), end_b

    # The load-bearing assertion: the worker was NOT wedged by B's fatal
    # abort, so C still runs to completion right behind it.
    end_c = _wait_state(client, c["job_id"], {"done", "error", "cancelled"}, timeout=60)
    assert end_c is not None and end_c["state"] == "done", end_c

    # B's fatal abort must not have destroyed (or created) anything: it never
    # wrote a draft -- the whole point of the sanity band (CLAUDE.md rule 12).
    import config
    assert not (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{b['doc_id']}.md").exists()


# ---------------------------------------------------------------------------
# 6) reprocess vs. fresh upload: _finish_cancelled must not conflate the two
#    (the data-destroying bug this file's cancel tests exist to catch: BEFORE
#    the fix, a cancelled REPROCESS removed <doc_id>.md and raw.md exactly as
#    a cancelled fresh upload does -- destroying the operator's existing,
#    good analysis and, for documents with no <doc_id>.pdf fallback, the ONLY
#    stored copy of the source).
# ---------------------------------------------------------------------------

def test_cancel_fresh_upload_removes_partial_draft_but_keeps_original(app_client):
    """The pre-existing (unchanged) fresh-upload cancel behaviour, pinned down
    explicitly and by contrast with the reprocess test right below: a FRESH
    upload's partial draft + raw.md intermediate are removed on cancel
    (enqueue_ingest's new `reprocess` parameter defaults to False -- exactly
    the branch upload_document() has always taken), while a permanent
    original at <doc_id>.pdf is never touched by _finish_cancelled in EITHER
    branch. A real PDF+Docling round trip is out of reach for this file by
    design (see the module docstring), so the permanent-original guarantee is
    checked with a stand-in file at the exact path _finish_cancelled must
    never reach for."""
    client, kp, jobs, _, config = app_client

    state = {"job_id": None, "map_calls": 0}

    def _cancelling_llm(temperature: float = 0.2):
        def _fn(system, user, max_tokens):
            if "PROFIL" in system:
                return "Profil."
            state["map_calls"] += 1
            if state["map_calls"] == 1 and state["job_id"]:
                snap = jobs.get_job(state["job_id"])
                if snap and snap["state"] == "running":
                    jobs.request_cancel(state["job_id"])
            import json as _json
            return _json.dumps({"section_title": "A", "digest": "x",
                                "terms": []}, ensure_ascii=False)
        return _fn

    kp.default_llm_fn = _cancelling_llm

    body = _upload(client, filename="explicit-fresh.md", title="Explicit Fresh").get_json()
    state["job_id"] = body["job_id"]
    doc_id = body["doc_id"]

    originals_dir = Path(config.KNOWLEDGE_ORIGINALS_DIR) / "operator"
    originals_dir.mkdir(parents=True, exist_ok=True)
    pdf_stand_in = originals_dir / f"{doc_id}.pdf"
    pdf_stand_in.write_bytes(b"%PDF-1.4 stand-in original bytes\n")
    pdf_bytes_before = pdf_stand_in.read_bytes()

    end = _wait_state(client, body["job_id"], {"cancelled", "done", "error"})
    assert end is not None and end["state"] == "cancelled", end
    assert state["map_calls"] >= 1

    draft = Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md"
    raw = Path(config.KNOWLEDGE_ORIGINALS_DIR) / "operator" / f"{doc_id}.raw.md"
    assert not draft.exists(), "a fresh upload's partial draft must be removed on cancel"
    assert not raw.exists(), "a fresh upload's raw.md intermediate must be removed on cancel"

    assert pdf_stand_in.exists(), "a permanent original must never be touched by cancellation"
    assert pdf_stand_in.read_bytes() == pdf_bytes_before

    log = " ".join(end.get("log_tail", []))
    assert "original upload kept" in log.lower()


def test_cancel_reprocess_keeps_existing_draft_and_source(app_client):
    """A reprocess's <doc_id>.md and raw.md PRE-DATE this run: they are the
    operator's existing, good analysis and (for MD-native documents with no
    PDF fallback) the only stored copy of the source. Cancelling a reprocess
    must remove NEITHER -- the fix for the data-destroying bug this test is
    named for."""
    client, kp, jobs, _, config = app_client

    # Step 1: a normal, successful FIRST ingest, so doc_id has a real draft +
    # raw.md on disk and is a proper Tier-O item reprocess_item() can look up.
    def _clean_llm(temperature: float = 0.2):
        def _fn(system, user, max_tokens):
            if "PROFIL" in system:
                return "Profil ueber Resilienz."
            import json as _json
            return _json.dumps({
                "section_title": "Massnahmen",
                "digest": "- drei Schritte\n- Mindestalter 12",
                "terms": [],
            }, ensure_ascii=False)
        return _fn

    kp.default_llm_fn = _clean_llm
    first = _upload(client, filename="existing.md", title="Existing Good Doc").get_json()
    done = _wait_state(client, first["job_id"], {"done", "error"}, timeout=60)
    assert done is not None and done["state"] == "done", done
    # The FINAL id (the ingest renames a fresh upload to the Author-Year-Title
    # id); the reprocess below must find the draft here.
    doc_id = done["doc_id"]

    draft = Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md"
    raw = Path(config.KNOWLEDGE_ORIGINALS_DIR) / "operator" / f"{doc_id}.raw.md"
    assert draft.exists() and raw.exists()
    draft_bytes_before = draft.read_bytes()
    raw_bytes_before = raw.read_bytes()

    # Step 2: reprocess the SAME doc_id, cancel it at a Verdichtung unit
    # boundary (same trip-on-first-Map-call technique as the test above).
    state = {"job_id": None, "map_calls": 0}

    def _cancelling_llm(temperature: float = 0.2):
        def _fn(system, user, max_tokens):
            if "PROFIL" in system:
                return "Profil."
            state["map_calls"] += 1
            if state["map_calls"] == 1 and state["job_id"]:
                snap = jobs.get_job(state["job_id"])
                if snap and snap["state"] == "running":
                    jobs.request_cancel(state["job_id"])
            import json as _json
            return _json.dumps({"section_title": "B", "digest": "y",
                                "terms": []}, ensure_ascii=False)
        return _fn

    kp.default_llm_fn = _cancelling_llm
    r = client.post(f"/api/knowledge/items/{doc_id}/reprocess")
    assert r.status_code == 200, r.get_json()
    reprocess_job_id = r.get_json()["job_id"]
    state["job_id"] = reprocess_job_id

    end = _wait_state(client, reprocess_job_id, {"cancelled", "done", "error"})
    assert end is not None and end["state"] == "cancelled", end
    assert state["map_calls"] >= 1

    # The existing, good analysis and the stored source must be untouched --
    # byte for byte, not merely "a file happens to exist again".
    assert draft.exists(), "the existing draft must survive a cancelled reprocess"
    assert draft.read_bytes() == draft_bytes_before
    assert raw.exists(), "the stored source (raw.md) must survive a cancelled reprocess"
    assert raw.read_bytes() == raw_bytes_before

    log = " ".join(end.get("log_tail", []))
    assert "reprocess" in log.lower()

