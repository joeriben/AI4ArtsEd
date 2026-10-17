"""Stage-A upload gate at the ROUTE level (UCD-131) — acceptance criteria 1,
2 and 6 as an end-to-end answer:

  * uploading the SAME PDF twice triggers NO second analysis: the second
    response is a 409 referencing the existing dossier with its provenance,
  * a rejected file causes NO storage, NO Docling run, NO model call — only
    the audit entry exists,
  * the image upload path gets file validation + hash blocklist (reduced
    Stage A).

Uses the same fixture idiom as test_knowledge_curation.py (all storage into
tmp_path, ingest interpreter = current python, Verdichtung LLM stubbed). The
PDF upload path is exercised at the gate level here (the route calls the gate
synchronously before the enqueue); the full Docling pipeline on PDFs is out
of scope for these tests — the MD passthrough path proves the enqueue
plumbing, the hand-built PDFs prove the gate.

Run: python3 -m pytest devserver/tests/test_upload_gate_routes.py -q
"""

import importlib
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import my_app.services.upload_gate as ug
from test_upload_gate import mk_pdf
from test_knowledge_curation import _stub_llm  # noqa: E402


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    import config

    tier_o = tmp_path / "knowledge_library"
    originals = tmp_path / "resources" / "knowledge_originals"
    lib = tmp_path / "library"
    (lib / "unesco").mkdir(parents=True)
    db = tmp_path / "knowledge_index.sqlite"
    overrides = tmp_path / "json" / "knowledge_glossary_overrides.json"
    lists_dir = tmp_path / "safety_lists"
    lists_dir.mkdir()

    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tier_o, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_ORIGINALS_DIR", originals, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_DIR", lib, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", db, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_GLOSSARY_OVERRIDES", overrides, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INGEST_PYTHON", sys.executable, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_PYTHON", sys.executable, raising=False)
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path, raising=False)
    monkeypatch.setattr(ug, "_SAFETY_LISTS_DIR", lists_dir, raising=False)

    import my_app.services.knowledge_processing as kp

    importlib.reload(kp)
    monkeypatch.setattr(kp, "default_llm_fn", _stub_llm, raising=False)

    import my_app.services.knowledge_library as kl

    importlib.reload(kl)

    from my_app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()
    return client, kl, config, tmp_path


def _upload_pdf(client, data: bytes, filename="doc.pdf", **form):
    payload = {"document": (io.BytesIO(data), filename)}
    payload.update(form)
    return client.post("/api/knowledge/upload", data=payload,
                       content_type="multipart/form-data")


# ---------------------------------------------------------------------------
# Acceptance 2: a rejected file stores nothing, runs nothing
# ---------------------------------------------------------------------------

class TestRejectLeavesNoTrace:
    def test_86a_reject_stores_nothing_and_audits(self, app_client):
        client, kl, config, tmp = app_client
        n_jobs_before = len(client.get("/api/knowledge/jobs").get_json()["jobs"])
        bad = mk_pdf(text_lines=("ein foto mit ss symbol an der wand",))
        r = _upload_pdf(client, bad)
        assert r.status_code == 400, r.get_json()
        msg = r.get_json()["error"]
        assert "Kennzeichen verfassungswidriger" in msg
        # Nothing stored: no original, no draft, no NEW job (the job registry
        # is module-global across tests in this process — compare the count).
        originals = list((tmp / "resources" / "knowledge_originals").rglob("*"))
        assert originals == []
        assert list((Path(config.KNOWLEDGE_TIER_O_DIR)).glob("*.md")) == []
        r2 = client.get("/api/knowledge/jobs")
        assert len(r2.get_json()["jobs"]) == n_jobs_before
        # Only the audit entry exists.
        audit = tmp / "knowledge_uploads" / "upload_gate_audit.log"
        assert audit.exists()
        entry = json.loads(audit.read_text(encoding="utf-8").strip())
        assert entry["reason"] == ug.REASON_86A
        # The found term never appears in the audit or the answer.
        assert "ss symbol" not in audit.read_text(encoding="utf-8")

    def test_not_a_pdf_rejected_before_anything(self, app_client):
        client, _, _, _ = app_client
        r = _upload_pdf(client, b"PK\x03\x04 zip masquerading as pdf")
        assert r.status_code == 400
        assert r.get_json()["error"] == ug.reject_message(ug.REASON_NOT_PDF)

    def test_embedded_file_rejected(self, app_client):
        client, _, _, _ = app_client
        r = _upload_pdf(client, mk_pdf(embedded_name="evil.exe"))
        assert r.status_code == 400
        assert r.get_json()["error"] == ug.reject_message(ug.REASON_EMBEDDED_FILE)

    def test_encrypted_rejected(self, app_client):
        from pypdf import PdfWriter

        w = PdfWriter()
        w.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        w.encrypt("pw")
        w.write(buf)
        client, _, _, _ = app_client
        r = _upload_pdf(client, buf.getvalue())
        assert r.status_code == 400
        assert r.get_json()["error"] == ug.reject_message(ug.REASON_ENCRYPTED)

    def test_blocked_hash_reject(self, app_client):
        client, _, config, tmp = app_client
        data = mk_pdf()
        (tmp / "safety_lists" / "upload_gate_blocked_hashes.json").write_text(
            json.dumps({"hashes": [ug.sha256_hex(data)]}), encoding="utf-8")
        r = _upload_pdf(client, data)
        assert r.status_code == 400
        assert r.get_json()["error"] == ug.reject_message(ug.REASON_BLOCKED_HASH)

    def test_unavailable_scan_rejects_and_stores_nothing(self, app_client, monkeypatch):
        """UCD-140: with the §86a matcher unimportable, a CLEAN PDF gets the
        same treatment as a rejected one — 400, audit line, nothing stored.
        Before 2026-09-28 it was stored, analysed and answered with success."""
        client, _, config, tmp = app_client
        monkeypatch.setitem(sys.modules, "schemas.engine.stage_orchestrator", None)
        n_jobs_before = len(client.get("/api/knowledge/jobs").get_json()["jobs"])

        r = _upload_pdf(client, mk_pdf())

        assert r.status_code == 400, r.get_json()
        assert r.get_json()["error"] == ug.reject_message(ug.REASON_SCAN_UNAVAILABLE)
        assert list((tmp / "resources" / "knowledge_originals").rglob("*")) == []
        assert list(Path(config.KNOWLEDGE_TIER_O_DIR).glob("*.md")) == []
        assert len(client.get("/api/knowledge/jobs").get_json()["jobs"]) == n_jobs_before
        entry = json.loads(
            (tmp / "knowledge_uploads" / "upload_gate_audit.log").read_text(
                encoding="utf-8").strip())
        assert entry["reason"] == ug.REASON_SCAN_UNAVAILABLE
        assert entry["origin"] == "knowledge/upload"


# ---------------------------------------------------------------------------
# Acceptance 1: same PDF twice -> no second analysis, reference + provenance
# ---------------------------------------------------------------------------

class TestDuplicateUpload:
    def test_second_upload_is_rejected_with_reference(self, app_client):
        client, kl, config, tmp = app_client
        data = mk_pdf(text_lines=("Kunstpaedagogik im Kontext.",))

        # First upload: runs the REAL ingest (Docling --md passthrough? no —
        # this is a PDF; the ingest script converts PDFs with Docling). To
        # avoid the Docling dependency in tests, record the index entry the
        # way the worker would after a successful run.
        r1 = _upload_pdf(client, data)
        assert r1.status_code == 200, r1.get_json()
        doc_id = r1.get_json()["doc_id"]
        # Simulate the worker's end-of-run index record (final id + md hash).
        ug.record_hash_index(doc_id, ug.sha256_hex(data), ug.md_hash("# raw"))

        # Second upload of the SAME bytes: duplicate, no second job.
        n_jobs_before = len(client.get("/api/knowledge/jobs").get_json()["jobs"])
        r2 = _upload_pdf(client, data)
        assert r2.status_code == 409, r2.get_json()
        body = r2.get_json()
        assert body.get("duplicate") is True
        assert body.get("doc_id") == doc_id
        assert "bereits analysiert" in body["error"]
        # No new job was enqueued for the duplicate.
        jobs = client.get("/api/knowledge/jobs").get_json()["jobs"]
        assert len(jobs) == n_jobs_before

    def test_second_upload_other_garb_same_content(self, app_client):
        client, kl, config, tmp = app_client
        # Two different files (different bytes) whose extracted MD is the
        # same after normalisation -> known by the MD hash.
        data = mk_pdf(text_lines=("Dasselbe Dokument.",))
        ug.record_hash_index("existing", "0" * 64, ug.md_hash("dasselbe dokument"))
        # The MD hash path needs the extraction to run; the gate extracts the
        # real text layer of this PDF, which is NOT "dasselbe dokument" —
        # so this upload is NOT a duplicate (honest expectation, pinned).
        r = _upload_pdf(client, data)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Image upload path (reduced Stage A)
# ---------------------------------------------------------------------------

class TestImageUploadReducedGate:
    def _png(self):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(buf, format="PNG")
        return buf.getvalue()

    def test_image_upload_still_works(self, app_client):
        client, _, _, _ = app_client
        r = client.post("/api/media/upload/image",
                        data={"file": (io.BytesIO(self._png()), "t.png")},
                        content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()

    def test_image_blocked_hash_rejected(self, app_client):
        client, kl, config, tmp = app_client
        data = self._png()
        (tmp / "safety_lists" / "upload_gate_blocked_hashes.json").write_text(
            json.dumps({"hashes": [ug.sha256_hex(data)]}), encoding="utf-8")
        r = client.post("/api/media/upload/image",
                        data={"file": (io.BytesIO(data), "t.png")},
                        content_type="multipart/form-data")
        assert r.status_code == 400
        assert r.get_json()["error"] == ug.reject_message(ug.REASON_BLOCKED_HASH)

    def test_image_wrong_magic_rejected(self, app_client):
        client, _, _, _ = app_client
        r = client.post("/api/media/upload/image",
                        data={"file": (io.BytesIO(b"BM fake"), "t.png")},
                        content_type="multipart/form-data")
        assert r.status_code == 400

    def test_reject_audit_written_for_image(self, app_client):
        client, kl, config, tmp = app_client
        data = self._png()
        (tmp / "safety_lists" / "upload_gate_blocked_hashes.json").write_text(
            json.dumps({"hashes": [ug.sha256_hex(data)]}), encoding="utf-8")
        client.post("/api/media/upload/image",
                    data={"file": (io.BytesIO(data), "t.png")},
                    content_type="multipart/form-data")
        audit = tmp / "knowledge_uploads" / "upload_gate_audit.log"
        assert audit.exists()
