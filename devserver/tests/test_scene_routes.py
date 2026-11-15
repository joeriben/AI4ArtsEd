"""The flow's document summary at the ROUTE level (from UCD-132) — the
duplicate answer and the admission surface:

  * a PDF upload with journal_id enqueues a summary job (after the file
    check and the intake of the document's name), with the surface's
    language and the safety level resolved at the request,
  * a file the file check refuses never enqueues, never stages — audit only,
  * a name the intake refuses answers 403 with the block message, which
    never repeats what was found, and never enqueues,
  * a list hit in the text layer no longer stops the upload: the job takes
    the document's text in at the intake,
  * the SAME document re-uploaded gets the 409 duplicate answer with provenance
    and NO second job, in the same session and in a later one, as long as a
    stored summary has the surface's language; it goes through the check of the
    session's level first,
  * the routes hand out neither another session's jobs nor a job's log, and a
    document checked at a looser level than the session's stands back,
  * missing journal_id is a 400.

All storage goes into tmp_path; the pipeline LLM is never reached on these
paths — duplicate/reject answer before the enqueue, and the job itself runs
against stubs in the unit test. The intake and the check at the result stand
in for the platform's: no model is asked. The blueprint runs in a bare app: the
platform's app factory needs the installation's settings file, which a test
does not have.

Run: python3 -m pytest devserver/tests/test_scene_routes.py -q
"""

import io
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import my_app.services.upload_gate as ug
from test_upload_gate import mk_pdf


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    import config

    lists = tmp_path / "safety_lists"
    lists.mkdir()
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path, raising=False)
    monkeypatch.setattr(ug, "_SAFETY_LISTS_DIR", lists, raising=False)

    import my_app.services.scene_document_space as space
    space.SCENE_DOCUMENTS_DIR = tmp_path / "scene_documents"

    import my_app.services.scene_ingest_service as sjs

    # Never let a real job run in the route tests: the enqueue is recorded,
    # the worker stays idle (a sentinel proves the route DID enqueue).
    enqueued = []

    def _fake_enqueue(**kwargs):
        enqueued.append(kwargs)
        # The route staged the PDF for a worker that never comes.
        shutil.rmtree(kwargs["staged_pdf"].parent, ignore_errors=True)
        return "testjob"

    monkeypatch.setattr(sjs, "enqueue_scene_ingest", _fake_enqueue, raising=False)
    monkeypatch.setattr(sjs, "_staging_root", lambda: tmp_path / "staging")

    import my_app.routes.scene_routes as routes
    from my_app.services import safety_gate as gate
    routes.jobs.enqueue_scene_ingest = _fake_enqueue

    # The check at the result, standing in: a stored summary taken over goes
    # through it at the session's level, and a part with VERBOTEN fails.
    def _result(text, *, level, field="text"):
        if "VERBOTEN" in text:
            return gate.Verdict(False, gate.CHECKPOINT_RESULT, level, field,
                                gate.REASON_CONTENT, "rejected")
        return gate.Verdict(True, gate.CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(sjs, "check_result_text", _result)

    # The intake, standing in: it records what it was asked and refuses with
    # intake["refuse"] where one is set, with a sentence naming what it found.
    intake = {"asked": [], "refuse": ""}

    def _intake(material, *, level, kind, field):
        intake["asked"].append((material, level, kind, field))
        if intake["refuse"]:
            return gate.Verdict(False, gate.CHECKPOINT_INTAKE, level, field,
                                intake["refuse"], "gefunden: Max Mustermann")
        return gate.Verdict(True, gate.CHECKPOINT_INTAKE, level, field)

    monkeypatch.setattr(routes, "check_intake", _intake)
    monkeypatch.setattr(routes, "resolve_safety_level", lambda: "youth")

    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(routes.scene_bp)
    app.config.update(TESTING=True)
    client = app.test_client()
    return client, enqueued, tmp_path, intake


def _upload(client, data: bytes, journal_id="j-1", filename="doc.pdf", lang="en"):
    return client.post(
        "/api/scene/upload",
        data={"document": (io.BytesIO(data), filename), "journal_id": journal_id,
              "lang": lang},
        content_type="multipart/form-data",
    )


def _stored(journal_id, pdf, *, lang="en", level="kids", body="B", n_withheld=0):
    """A finished summary of `pdf` in the given session's space."""
    import my_app.services.scene_document_space as space

    raw_hash = ug.sha256_hex(pdf)
    doc_id = f"doc-{raw_hash[:12]}"
    space.store_document(
        journal_id, doc_id,
        summary={"profile": "P", "sections": [{"heading": "H", "body": body}],
                 "glossary": []},
        meta={"doc_id": doc_id, "doc_hash": raw_hash, "title": "T",
              "journal_id": journal_id, "job_id": "firstjob",
              "analyzed_at": "2026-09-27T12:00:00+00:00",
              "analysis_model": "stub/model", "analysis_lang": lang,
              "safety_level": level, "n_withheld": n_withheld},
    )
    return doc_id


class TestSceneUploadRoute:
    def test_admitted_pdf_enqueues_job(self, app_client):
        client, enqueued, tmp, intake = app_client
        r = _upload(client, mk_pdf())
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["success"] is True
        assert body["doc_id"].startswith("doc-")
        assert len(enqueued) == 1
        assert enqueued[0]["journal_id"] == "j-1"
        assert enqueued[0]["lang"] == "en"
        # The level the view resolved reaches the job.
        assert enqueued[0]["safety_level"] == "youth"
        # The document's name, at that level; its text is the job's.
        assert intake["asked"] == [("doc", "youth", "text", "title")]

    def test_a_form_without_language_gets_the_library_default(self, app_client):
        client, enqueued, tmp, _intake = app_client
        from my_app.services.knowledge_processing import DEFAULT_ANALYSIS_LANG

        r = client.post(
            "/api/scene/upload",
            data={"document": (io.BytesIO(mk_pdf()), "doc.pdf"), "journal_id": "j"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200, r.get_json()
        assert enqueued[0]["lang"] == DEFAULT_ANALYSIS_LANG

    def test_a_failed_save_leaves_no_raw_file(self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        from werkzeug.datastructures import FileStorage

        def _no_disk(self, dst, *a, **kw):
            with open(dst, "wb") as f:
                f.write(b"half a file")
            raise OSError("disk full")

        monkeypatch.setattr(FileStorage, "save", _no_disk)
        assert _upload(client, mk_pdf()).status_code == 500
        assert list((tmp / "staging").iterdir()) == []

    def test_a_failed_enqueue_leaves_no_raw_file(self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.routes.scene_routes as routes

        def _no_queue(**kwargs):
            raise OSError("no thread")

        monkeypatch.setattr(routes.jobs, "enqueue_scene_ingest", _no_queue)
        assert _upload(client, mk_pdf()).status_code == 500
        assert list((tmp / "staging").iterdir()) == []

    def test_the_surface_language_reaches_the_job(self, app_client):
        client, enqueued, tmp, intake = app_client
        r = client.post(
            "/api/scene/upload",
            data={"document": (io.BytesIO(mk_pdf()), "doc.pdf"), "journal_id": "j",
                  "lang": "de"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200, r.get_json()
        assert enqueued[0]["lang"] == "de"

    def test_a_file_the_file_check_refuses_never_enqueues(self, app_client):
        client, enqueued, tmp, intake = app_client
        r = _upload(client, mk_pdf(embedded_name="setup.exe"))
        assert r.status_code == 400, r.get_json()
        assert "eingebettete Dateien" in r.get_json()["error"]
        assert enqueued == []  # no job, no staging, nothing
        assert intake["asked"] == []

    def test_a_list_hit_no_longer_stops_the_upload(self, app_client):
        client, enqueued, tmp, intake = app_client
        # A §86a term in the text layer: the job's intake reads the text.
        r = _upload(client, mk_pdf(text_lines=("ein foto mit ss symbol an der wand",)))
        assert r.status_code == 200, r.get_json()
        assert len(enqueued) == 1

    @pytest.mark.parametrize("reason_key", ["personal_data", "unavailable"])
    def test_a_refused_name_never_enqueues(self, app_client, reason_key):
        client, enqueued, tmp, intake = app_client
        intake["refuse"] = reason_key
        r = _upload(client, mk_pdf(), filename="Brief an Max Mustermann.pdf")
        assert r.status_code == 403, r.get_json()
        body = r.get_json()
        assert body["safety_block"] == {"checkpoint": "intake", "field": "title",
                                        "reason_key": reason_key, "reason": ""}
        assert "gefunden" not in r.get_data(as_text=True)
        assert enqueued == []

    def test_missing_journal_id_is_400(self, app_client):
        client, enqueued, tmp, intake = app_client
        r = client.post(
            "/api/scene/upload",
            data={"document": (io.BytesIO(mk_pdf()), "doc.pdf")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert enqueued == []

    def test_non_pdf_extension_is_400(self, app_client):
        client, enqueued, tmp, intake = app_client
        r = client.post(
            "/api/scene/upload",
            data={"document": (io.BytesIO(b"hello"), "doc.txt"), "journal_id": "j"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert enqueued == []


class TestDuplicateWithinSession:
    def test_second_upload_same_hash_gets_409_no_second_job(self, app_client):
        """Acceptance 5: same document again within the session -> duplicate
        answer with provenance, NO second enqueue."""
        client, enqueued, tmp, intake = app_client
        pdf = mk_pdf()
        r1 = _upload(client, pdf, journal_id="j-dup")
        assert r1.status_code == 200
        # simulate the first analysis having PERSISTED into the session space
        # (the route checks the space, not the job registry)
        doc_id = _stored("j-dup", pdf)
        r2 = _upload(client, pdf, journal_id="j-dup")
        assert r2.status_code == 409, r2.get_json()
        body = r2.get_json()
        assert body["duplicate"] is True
        assert body["doc_id"] == doc_id
        assert "bereits analysiert" in body["error"]
        assert "2026-09-27T12:00:00+00:00" in body["error"]
        assert "stub/model" in body["error"]
        # NO second analysis
        assert len(enqueued) == 1


class TestDuplicateAcrossSessions:
    """The session id carries the date, so the next day is another session."""

    def test_a_later_session_gets_the_summary_and_no_job(self, app_client):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.scene_document_space as space

        pdf = mk_pdf()
        doc_id = _stored("browser_2026-11-05", pdf)
        r = _upload(client, pdf, journal_id="browser_2026-11-06")
        assert r.status_code == 409, r.get_json()
        assert r.get_json()["doc_id"] == doc_id
        assert enqueued == []
        doc = space.get_document("browser_2026-11-06", doc_id)
        assert doc["summary"]["profile"] == "P"
        assert doc["meta"]["analyzed_at"] == "2026-09-27T12:00:00+00:00"
        assert doc["meta"]["journal_id"] == "browser_2026-11-06"
        assert "job_id" not in doc["meta"]

    def test_another_language_is_summarised_again(self, app_client):
        client, enqueued, tmp, _intake = app_client
        pdf = mk_pdf()
        _stored("browser_2026-11-05", pdf, lang="en")
        r = _upload(client, pdf, journal_id="browser_2026-11-06", lang="de")
        assert r.status_code == 200, r.get_json()
        assert enqueued[0]["lang"] == "de"

    def test_a_stricter_session_gets_what_passes_its_own_check(
            self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.safety_level_resolver as resolver
        import my_app.services.scene_document_space as space

        monkeypatch.setattr(resolver, "resolve_safety_level", lambda: "youth")
        pdf = mk_pdf()
        doc_id = _stored("browser_2026-11-05", pdf, level="research", body="VERBOTEN")
        r = _upload(client, pdf, journal_id="browser_2026-11-06")
        assert r.status_code == 409, r.get_json()
        assert enqueued == []
        doc = space.get_document("browser_2026-11-06", doc_id)
        assert doc["summary"]["sections"] == []
        assert doc["n_withheld"] == 1
        assert doc["meta"]["safety_level"] == "youth"

    def test_the_card_carries_the_name_this_upload_brought(self, app_client):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.scene_document_space as space

        pdf = mk_pdf()
        doc_id = _stored("browser_2026-11-05", pdf)
        _upload(client, pdf, journal_id="browser_2026-11-06", filename="meins.pdf")
        assert space.get_document("browser_2026-11-06", doc_id)["meta"]["title"] == "meins"

    def test_a_check_without_answer_leaves_it_to_the_job(self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.scene_ingest_service as sjs
        from my_app.services import safety_gate as gate

        monkeypatch.setattr(sjs, "check_result_text",
                            lambda text, *, level, field="text": gate.Verdict(
                                False, gate.CHECKPOINT_RESULT, level, field,
                                gate.REASON_UNAVAILABLE, "no answer"))
        pdf = mk_pdf()
        _stored("browser_2026-11-05", pdf)
        r = _upload(client, pdf, journal_id="browser_2026-11-06")
        assert r.status_code == 200, r.get_json()
        assert len(enqueued) == 1

    def test_a_check_without_answer_leaves_the_session_its_own_document(
            self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.safety_level_resolver as resolver
        import my_app.services.scene_ingest_service as sjs
        from my_app.services import safety_gate as gate

        monkeypatch.setattr(resolver, "resolve_safety_level", lambda: "kids")
        monkeypatch.setattr(sjs, "check_result_text",
                            lambda text, *, level, field="text": gate.Verdict(
                                False, gate.CHECKPOINT_RESULT, level, field,
                                gate.REASON_UNAVAILABLE, "no answer"))
        pdf = mk_pdf()
        doc_id = _stored("browser_2026-11-06", pdf, level="kids")
        r = _upload(client, pdf, journal_id="browser_2026-11-06")
        assert r.status_code == 409, r.get_json()
        assert r.get_json()["doc_id"] == doc_id
        assert enqueued == []

    def test_a_check_without_answer_gives_no_copy_of_a_looser_level(
            self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.safety_level_resolver as resolver
        import my_app.services.scene_ingest_service as sjs
        from my_app.services import safety_gate as gate

        monkeypatch.setattr(resolver, "resolve_safety_level", lambda: "kids")
        monkeypatch.setattr(sjs, "check_result_text",
                            lambda text, *, level, field="text": gate.Verdict(
                                False, gate.CHECKPOINT_RESULT, level, field,
                                gate.REASON_UNAVAILABLE, "no answer"))
        pdf = mk_pdf()
        _stored("browser_2026-11-06", pdf, level="research")
        r = _upload(client, pdf, journal_id="browser_2026-11-06")
        assert r.status_code == 200, r.get_json()
        assert len(enqueued) == 1

    def test_a_copy_a_stricter_session_cut_is_summarised_again(
            self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.safety_level_resolver as resolver

        monkeypatch.setattr(resolver, "resolve_safety_level", lambda: "research")
        pdf = mk_pdf()
        _stored("browser_2026-11-05", pdf, level="kids", n_withheld=3)
        r = _upload(client, pdf, journal_id="browser_2026-11-06")
        assert r.status_code == 200, r.get_json()
        assert len(enqueued) == 1

    def test_a_summary_from_a_stricter_level_serves_a_looser_one(
            self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.safety_level_resolver as resolver

        monkeypatch.setattr(resolver, "resolve_safety_level", lambda: "research")
        pdf = mk_pdf()
        _stored("browser_2026-11-05", pdf, level="kids")
        r = _upload(client, pdf, journal_id="browser_2026-11-06")
        assert r.status_code == 409, r.get_json()
        assert enqueued == []


class TestWhatTheRoutesHandOut:
    def test_the_job_list_is_the_session_s_own_and_carries_no_log(
            self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.routes.scene_routes as routes

        job = {"job_id": "a", "journal_id": "mine", "log_tail": ["### Überschrift"]}
        other = {"job_id": "b", "journal_id": "theirs", "log_tail": []}
        monkeypatch.setattr(routes.jobs, "list_jobs", lambda: [job, other])
        assert client.get("/api/scene/jobs").status_code == 400
        assert client.get("/api/scene/jobs?journal_id=mine").get_json() == {
            "jobs": [{"job_id": "a"}]}

    def test_one_job_carries_neither_log_nor_session(self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.routes.scene_routes as routes

        monkeypatch.setattr(routes.jobs, "get_job",
                            lambda job_id: {"job_id": job_id, "journal_id": "theirs",
                                            "log_tail": ["### Überschrift"]})
        assert client.get("/api/scene/jobs/x").get_json() == {"job_id": "x"}

    def test_a_document_of_a_looser_level_stands_back(self, app_client, monkeypatch):
        client, enqueued, tmp, _intake = app_client
        import my_app.services.safety_level_resolver as resolver

        doc_id = _stored("j-1", mk_pdf(), level="research")
        monkeypatch.setattr(resolver, "resolve_safety_level", lambda: "research")
        assert client.get(f"/api/scene/documents/{doc_id}?journal_id=j-1").status_code == 200
        monkeypatch.setattr(resolver, "resolve_safety_level", lambda: "kids")
        assert client.get(f"/api/scene/documents/{doc_id}?journal_id=j-1").status_code == 404
