"""Szenen-Kapsel-Pipeline at the ROUTE level (UCD-132) — acceptance 5 and the
admission surface:

  * a PDF upload with journal_id enqueues a scene job (after the Stage-A gate),
  * a REJECTED file (Stage-A hit) never enqueues, never stages — audit only,
  * the SAME document re-uploaded within the session gets the 409 duplicate
    answer with provenance and NO second job (acceptance 5),
  * missing journal_id is a 400.

Same fixture idiom as test_upload_gate_routes.py (all storage into tmp_path;
the pipeline LLM is never reached on these paths — duplicate/reject answer
before the enqueue, and the job itself runs against stubs in the unit test).

Run: python3 -m pytest devserver/tests/test_scene_routes.py -q
"""

import io
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
        return "testjob"

    monkeypatch.setattr(sjs, "enqueue_scene_ingest", _fake_enqueue, raising=False)

    import my_app.routes.scene_routes as routes
    routes.jobs.enqueue_scene_ingest = _fake_enqueue

    from my_app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()
    return client, enqueued, tmp_path


def _upload(client, data: bytes, journal_id="j-1", filename="doc.pdf"):
    return client.post(
        "/api/scene/upload",
        data={"document": (io.BytesIO(data), filename), "journal_id": journal_id},
        content_type="multipart/form-data",
    )


class TestSceneUploadRoute:
    def test_admitted_pdf_enqueues_job(self, app_client):
        client, enqueued, tmp = app_client
        r = _upload(client, mk_pdf())
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["success"] is True
        assert body["doc_id"].startswith("doc-")
        assert len(enqueued) == 1
        assert enqueued[0]["journal_id"] == "j-1"

    def test_rejected_pdf_never_enqueues(self, app_client):
        client, enqueued, tmp = app_client
        # §86a hit in the text layer (platform bilingual matcher, tested list)
        bad = mk_pdf(text_lines=("ein foto mit ss symbol an der wand",))
        r = _upload(client, bad)
        assert r.status_code == 400, r.get_json()
        assert "Kennzeichen verfassungswidriger" in r.get_json()["error"]
        assert enqueued == []  # no job, no staging, nothing

    def test_missing_journal_id_is_400(self, app_client):
        client, enqueued, tmp = app_client
        r = client.post(
            "/api/scene/upload",
            data={"document": (io.BytesIO(mk_pdf()), "doc.pdf")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert enqueued == []

    def test_non_pdf_extension_is_400(self, app_client):
        client, enqueued, tmp = app_client
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
        client, enqueued, tmp = app_client
        pdf = mk_pdf()
        r1 = _upload(client, pdf, journal_id="j-dup")
        assert r1.status_code == 200
        # simulate the first analysis having PERSISTED into the session space
        # (the route checks the space, not the job registry)
        import my_app.services.scene_document_space as space

        raw_hash = ug.sha256_hex(pdf)
        space.store_document(
            "j-dup", f"doc-{raw_hash[:12]}",
            capsules=[{"scene": "x", "prompt": "y",
                      "safety": {"verdict": "pass", "categories": []},
                      "anchor": {"chapter": "k", "probe": "p"}}],
            segments=[],
            meta={"doc_id": f"doc-{raw_hash[:12]}", "doc_hash": raw_hash,
                  "title": "T", "analyzed_at": "2026-09-27T12:00:00+00:00",
                  "analysis_model": "stub/model", "analysis_lang": "de",
                  "n_flagged_segments": 0, "n_discarded_capsules": 0},
        )
        r2 = _upload(client, pdf, journal_id="j-dup")
        assert r2.status_code == 409, r2.get_json()
        body = r2.get_json()
        assert body["duplicate"] is True
        assert body["n_capsules"] == 1
        assert "bereits analysiert" in body["error"]
        # NO second analysis
        assert len(enqueued) == 1
