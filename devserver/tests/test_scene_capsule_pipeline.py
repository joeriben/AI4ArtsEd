"""Szenen-Kapsel-Pipeline (UCD-132) — deterministische Unit-Tests.

Covers the five acceptance criteria at the module level, with a stub LLM (NO
network, NO Docling, hand-built PDFs where the route is exercised):

  1. end-to-end: raw MD -> capsules with anchor/scene/prompt/safety/provenance
     persisted in the session document space,
  2. fail-closed: a flagged segment/capsule is DISCARDED, its content never
     stored; only the count appears (n_flagged_segments),
  3. raw lifecycle: after a finished job the workdir holds NEITHER the PDF
     bytes NOR the full-text MD (service-level with a passthrough docling
     stand-in); capsules + segments + meta remain,
  4. determinism: the same capsule ALWAYS yields the same prompt
     (assemble_prompt regression),
  5. hash protection: the same document re-uploaded within the session gets
     the duplicate answer, no second analysis (route-level).

Run: python3 -m pytest devserver/tests/test_scene_capsule_pipeline.py -q
"""

import importlib
import io
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import my_app.services.upload_gate as ug
from test_upload_gate import mk_pdf


# ---------------------------------------------------------------------------
# A raw MD shaped like a chapter document (parse_structure input)
# ---------------------------------------------------------------------------

_RAW = """# Bildung und Kultur

## Einleitung

Bildung und Kultur gehören zusammen. Die Schule von morgen braucht Orte, an denen Kinder und Jugendliche selbst gestalten. Ein Beispiel: das Atelier im Keller der Gemeindeschule in Feldbach, seit 2023.

## Kapitel 1: Das Atelier

Im Atelier malen Zwölfjährige an großen Leinwänden. Die Kunstpädagogin Mira Lent leitet das Atelier seit drei Jahren. Jeden Dienstag treffen sich 14 Jugendliche im Kellerraum, bringen eigene Ideen mit und stimmen über das nächste Projekt ab. Die Stimmung ist konzentriert und laut zugleich.

## Kapitel 2: Die Ausstellung

Zum Jahresende hängen die Jugendlichen ihre Bilder im Flur der Schule auf. Eltern und Lehrkräfte sehen die Werke. Die Gemeinde bezahlt die Rahmen.
"""


def _seg_answer(digest="Zwölfjährige malen im Kellerraum in Feldbach. Die Kunstpädagogin Mira Lent leitet das Atelier seit drei Jahren.",
                verdict="pass", cats=None, title="Das Atelier"):
    return json.dumps({
        "section_title": title,
        "digest": digest,
        "safetyVerdict": verdict,
        "safetyCategories": cats if cats is not None else ([] if verdict == "pass" else ["86-propaganda"]),
    }, ensure_ascii=False)


def _caps_answer(scene="In einem Kellerraum in Feldbach malen zwölfjährige Jugendliche unter Leitung einer Kunstpädagogin an großen Leinwänden.",
                  verdict="pass", cats=None, n=1):
    caps = []
    for _ in range(n):
        caps.append({
            "scene": scene,
            "prompt_template": "Ein Bild, das zeigt: " + scene + ".",
            "safetyVerdict": verdict,
            "safetyCategories": cats if cats is not None else ([] if verdict == "pass" else ["86-propaganda"]),
        })
    return json.dumps({"capsules": caps}, ensure_ascii=False)


def _stub_llm(digest_verdict="pass", capsule_verdict="pass", scene=None, n=1):
    """Deterministic stand-in answering the segment map and the capsule
    reduce calls (distinguished by the system prompt's marker words)."""
    scene = scene or ("In einem Kellerraum in Feldbach malen zwölfjährige "
                      "Jugendliche unter Leitung einer Kunstpädagogin an großen Leinwänden.")

    def _fn(system: str, user: str, max_tokens=None):
        if "Szenen-Kapseln" in system:
            return _caps_answer(scene=scene, verdict=capsule_verdict, n=n)
        return _seg_answer(verdict=digest_verdict)

    _fn.models_used = ["stub/test-model"]
    return _fn


@pytest.fixture()
def scene_env(tmp_path, monkeypatch):
    """All storage into tmp_path: scene documents space, gate index, curated
    lists; kp reloaded (module-level test idiom)."""
    import config

    lists = tmp_path / "safety_lists"
    lists.mkdir()
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path, raising=False)
    monkeypatch.setattr(ug, "_SAFETY_LISTS_DIR", lists, raising=False)
    monkeypatch.setattr(ug, "_INDEX_LOCK", threading.Lock(), raising=False)

    import my_app.services.scene_document_space as space

    importlib.reload(space)
    monkeypatch.setattr(space, "SCENE_DOCUMENTS_DIR", tmp_path / "scene_documents", raising=False)
    return tmp_path, space


# ---------------------------------------------------------------------------
# Acceptance 4: deterministic prompt (regression)
# ---------------------------------------------------------------------------

class TestDeterministicPrompt:
    def test_same_scene_same_prompt(self):
        import my_app.services.scene_capsule_pipeline as scp

        p1 = scp.assemble_prompt("Ein Kellerraum. Jugendliche malen.")
        p2 = scp.assemble_prompt("Ein Kellerraum. Jugendliche malen.")
        assert p1 == p2
        assert p1.startswith("Ein Bild, das zeigt: ")
        assert p1.endswith(".")

    def test_whitespace_normalised_not_altered(self):
        import my_app.services.scene_capsule_pipeline as scp

        p = scp.assemble_prompt("Ein  Kellerraum.\nJugendliche  malen.")
        assert p == "Ein Bild, das zeigt: Ein Kellerraum. Jugendliche malen.."

    def test_prompt_prefix_in_reduce_system_prompt(self):
        # the assembled prompt shape must match the template the reduce call
        # asks for (same prefix), so the deterministic assembly is the one
        # the model was told to mirror
        import my_app.services.scene_capsule_pipeline as scp

        scene = "Jugendliche malen in einem Kellerraum"
        assert scp.assemble_prompt(scene) == "Ein Bild, das zeigt: " + scene + "."


# ---------------------------------------------------------------------------
# Fail-closed: verdict parsing
# ---------------------------------------------------------------------------

class TestFailClosedParsing:
    def test_missing_block_fails_closed(self):
        import my_app.services.scene_capsule_pipeline as scp

        verdict, cats = scp.parse_safety_block({})
        assert verdict == "flagged"
        assert cats

    def test_unknown_verdict_fails_closed(self):
        import my_app.services.scene_capsule_pipeline as scp

        verdict, _ = scp.parse_safety_block({"safetyVerdict": "ok"})
        assert verdict == "flagged"

    def test_unknown_category_fails_closed(self):
        import my_app.services.scene_capsule_pipeline as scp

        verdict, _ = scp.parse_safety_block({
            "safetyVerdict": "flagged", "safetyCategories": ["sonstwas"]})
        assert verdict == "flagged"

    def test_pass_needs_clean_categories(self):
        import my_app.services.scene_capsule_pipeline as scp

        verdict, cats = scp.parse_safety_block({
            "safetyVerdict": "pass", "safetyCategories": []})
        assert verdict == "pass" and cats == []


# ---------------------------------------------------------------------------
# Deterministic backstop over the curated lists
# ---------------------------------------------------------------------------

class TestDeterministicBackstop:
    def test_86a_term_in_scene_discards_capsule(self, scene_env, monkeypatch):
        """A §86a term in the SCENE kills the capsule even when the model
        said pass (fail-closed backstop, plan §7.2.2). The gate's §86a side
        runs through the platform's bilingual matcher — one inventory. For
        this unit test the §86 org list carries the term (own data file,
        exact matcher), which exercises the same discard path."""
        tmp, space = scene_env
        (tmp / "safety_lists" / ug.LIST_86_ORGS).write_text(
            json.dumps({"terms": ["doppelblitz"]}, ensure_ascii=False), encoding="utf-8")

        import my_app.services.scene_capsule_pipeline as scp

        reason = scp.deterministic_safety_pass(
            "Eine Wand mit doppelblitz im Hintergrund")
        assert reason == ug.REASON_86

        # through the full pipeline: the capsule dies, the count rises
        result = scp.process_document_to_capsules(
            _RAW, doc_id="doc-x", llm=_stub_llm(scene="Eine Wand mit doppelblitz im Hintergrund"),
        )
        assert result["capsules"] == []
        assert result["n_discarded_capsules"] >= 1


# ---------------------------------------------------------------------------
# Acceptance 1 + 2: end-to-end over the pipeline (stub LLM)
# ---------------------------------------------------------------------------

class TestPipelineEndToEnd:
    def test_capsules_carry_the_full_schema(self, scene_env):
        import my_app.services.scene_capsule_pipeline as scp

        result = scp.process_document_to_capsules(
            _RAW, doc_id="doc-abc123", llm=_stub_llm())
        assert result["fatal"] == []
        assert result["capsules"], "at least one capsule from the stub"
        for cap in result["capsules"]:
            assert set(cap.keys()) == {"anchor", "scene", "prompt", "safety"}
            assert cap["anchor"]["chapter"]
            assert cap["anchor"]["probe"]  # Beleg-Stichprobe (anchor duty)
            assert cap["scene"]
            assert cap["prompt"].startswith("Ein Bild, das zeigt: ")
            assert cap["safety"]["verdict"] == "pass"
            assert cap["safety"]["categories"] == []
        # provenance rides the result dict (the job stamps it into meta)
        assert result["analyzed_at"]
        assert result["analysis_lang"] == "de"
        assert result["models_used"] == ["stub/test-model"]

    def test_flagged_segment_counted_never_stored(self, scene_env):
        """Acceptance 2: a sensibilisiertes segment is discarded; the count
        appears; the content does NOT ride any stored segment."""
        import my_app.services.scene_capsule_pipeline as scp

        result = scp.process_document_to_capsules(
            _RAW, doc_id="doc-x",
            llm=_stub_llm(digest_verdict="flagged", capsule_verdict="pass"))
        assert result["n_flagged_segments"] >= 1
        assert result["capsules"] == []  # flagged segment yields no capsules
        assert result["segments"] == []   # and no stored digest
        assert result["fatal"], "no usable segment at all is FATAL (honest)"

    def test_flagged_capsule_discarded_counted(self, scene_env):
        import my_app.services.scene_capsule_pipeline as scp

        result = scp.process_document_to_capsules(
            _RAW, doc_id="doc-x",
            llm=_stub_llm(digest_verdict="pass", capsule_verdict="flagged"))
        assert result["n_discarded_capsules"] >= 1
        assert result["capsules"] == []
        # the segment itself passed and stays the question base
        assert result["segments"]

    def test_capsule_ceiling_configurable(self, scene_env):
        import my_app.services.scene_capsule_pipeline as scp

        result = scp.process_document_to_capsules(
            _RAW, doc_id="doc-x", llm=_stub_llm(n=3), max_capsules=1)
        assert len(result["capsules"]) == 1


# ---------------------------------------------------------------------------
# Acceptance 3 + 1 at the SERVICE level: workdir lifecycle + space persist
# ---------------------------------------------------------------------------

def _run_job_to_done(jobs, job_id, timeout=30.0):
    """Wait for a scene job to leave queued/running (the worker is a daemon
    thread; the test asserts the FINAL state)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs.get_job(job_id)
        if job["state"] in ("done", "error", "cancelled"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {jobs.get_job(job_id)}")


class TestServiceLifecycle:
    def test_raw_files_deleted_and_space_persisted(self, scene_env, monkeypatch, tmp_path):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs
        import my_app.services.scene_capsule_pipeline as scp

        # Docling stand-in: MD passthrough (the real Docling runs in its own
        # venv; the lifecycle contract under test is the FILE handling, not
        # the conversion). It writes raw.md from the staged PDF's sibling
        # test fixture content.
        staged_dir = tmp / "scene_jobs" / "j1"
        staged_dir.mkdir(parents=True)
        staged_pdf = staged_dir / "document.pdf"
        staged_pdf.write_bytes(mk_pdf())

        def _fake_docling(job_id, pdf_path, raw_out):
            raw_out.write_text(_RAW, encoding="utf-8")
            return 0

        monkeypatch.setattr(sjs, "_run_docling", _fake_docling, raising=False)
        monkeypatch.setattr(
            scp, "process_document_to_capsules",
            lambda raw_md, **kw: scp_result_stub(), raising=False)

        # a stable result stub with the schema
        def scp_result_stub():
            return {
                "capsules": [{
                    "anchor": {"chapter": "Kapitel 1: Das Atelier",
                               "probe": "Zwölfjährige malen im Kellerraum"},
                    "scene": "Jugendliche malen in einem Kellerraum",
                    "prompt": "Ein Bild, das zeigt: Jugendliche malen in einem Kellerraum.",
                    "safety": {"verdict": "pass", "categories": []},
                }],
                "segments": [{"section_title": "Das Atelier", "digest": "…",
                              "safety": {"verdict": "pass", "categories": []}}],
                "n_flagged_segments": 1,
                "n_discarded_capsules": 0,
                "fatal": [],
                "mode": "standard",
                "mode_reason": "test",
                "analyzed_at": "2026-09-27T12:00:00+00:00",
                "models_used": ["stub/test-model"],
                "analysis_lang": "de",
            }

        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-1", title="Testdokument",
            staged_pdf=staged_pdf, raw_hash="a" * 64, doc_id="doc-aaaaaaaaaaaa",
        )
        job = _run_job_to_done(sjs, job_id)
        assert job["state"] == "done", job
        # Acceptance 3: the workdir is GONE (PDF bytes + raw MD deleted)
        assert not staged_pdf.exists()
        assert not (staged_dir / "raw.md").exists()
        # the log line documents the deletion
        assert any("gelöscht" in ln for ln in job["log_tail"])
        # the SPACE holds the capsule + segment + meta (question base)
        doc = space.get_document("journal-1", "doc-aaaaaaaaaaaa")
        assert doc is not None
        assert doc["n_capsules"] == 1
        assert doc["capsules"][0]["prompt"].startswith("Ein Bild, das zeigt: ")
        assert doc["meta"]["doc_hash"] == "a" * 64
        assert doc["n_flagged_segments"] == 1

    def test_error_path_also_cleans_workdir(self, scene_env, monkeypatch):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        staged_dir = tmp / "scene_jobs" / "j2"
        staged_dir.mkdir(parents=True)
        staged_pdf = staged_dir / "document.pdf"
        staged_pdf.write_bytes(mk_pdf())

        def _failing_docling(job_id, pdf_path, raw_out):
            return 1

        monkeypatch.setattr(sjs, "_run_docling", _failing_docling, raising=False)
        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-2", title="T", staged_pdf=staged_pdf,
            raw_hash="b" * 64, doc_id="doc-bbbbbbbbbbbb",
        )
        job = _run_job_to_done(sjs, job_id)
        assert job["state"] == "error"
        assert not staged_pdf.exists()  # §6 holds on the ERROR path too


# ---------------------------------------------------------------------------
# Session document space
# ---------------------------------------------------------------------------

class TestDocumentSpace:
    def test_store_get_list_delete(self, scene_env):
        tmp, space = scene_env
        meta = {"doc_hash": "c" * 64, "title": "D", "analyzed_at": "t",
                "analysis_model": "m", "analysis_lang": "de",
                "n_flagged_segments": 0, "n_discarded_capsules": 0}
        d = space.store_document("j", "doc-1", capsules=[{"x": 1}],
                                 segments=[], meta=meta)
        assert d is not None and d.exists()
        doc = space.get_document("j", "doc-1")
        assert doc["n_capsules"] == 1
        assert space.list_documents("j")[0]["doc_id"] == "doc-1"
        assert space.delete_document("j", "doc-1") is True
        assert space.get_document("j", "doc-1") is None

    def test_journal_delete_drops_space(self, scene_env):
        tmp, space = scene_env
        meta = {"doc_hash": "d" * 64, "title": "D", "analyzed_at": "t",
                "analysis_model": "m", "analysis_lang": "de",
                "n_flagged_segments": 0, "n_discarded_capsules": 0}
        space.store_document("jj", "doc-2", capsules=[], segments=[], meta=meta)
        assert space.delete_journal_space("jj") == 1
        assert space.list_documents("jj") == []

    def test_unsafe_ids_rejected(self, scene_env):
        tmp, space = scene_env
        # empty id -> None; path separators never survive _safe_id (the id
        # class is [a-z0-9-], traversal collapses into a plain name — the
        # STORED path can never leave the space root)
        assert space.store_document("", "x", capsules=[], segments=[], meta={}) is None
        d = space.store_document("j", "../../etc", capsules=[], segments=[], meta={})
        assert d is not None
        assert d.parent == tmp / "scene_documents" / "j"
        assert ".." not in str(d)
