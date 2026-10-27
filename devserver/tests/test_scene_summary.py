"""The flow's document summary — the job service and the session space.

A PDF brought in through the flow's plus is condensed by the library's own
procedure (knowledge_processing.process_document) and then checked part by
part before anything is stored. Covered here, with no network and no Docling:

  * the parts of a library condensation the card shows (profile, sections
    without their review anchors, glossary),
  * the safety check: a failing part is withheld and counted, a check with no
    answer ends the job without storing anything,
  * the job end to end: the library's condensation runs with the surface's
    language, the raw files are gone afterwards, the summary is in the space,
  * the session space: store, read, list, drop; a document of the capsule
    format stored before 2026-09-28 counts as absent.

Run: python3 -m pytest devserver/tests/test_scene_summary.py -q
"""

import importlib
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import my_app.services.upload_gate as ug
from test_upload_gate import mk_pdf


_RAW = """# Bildung und Kultur

## Einleitung

Bildung und Kultur gehören zusammen. Ein Beispiel: das Atelier im Keller der Gemeindeschule in Feldbach, seit 2023.

## Kapitel 1: Das Atelier

Im Atelier malen Zwölfjährige an großen Leinwänden. Jeden Dienstag treffen sich 14 Jugendliche im Kellerraum.

## Kapitel 2: Die Ausstellung

Zum Jahresende hängen die Jugendlichen ihre Bilder im Flur der Schule auf.
"""


def _markdown():
    """A condensation in the library's own file format."""
    from my_app.services import knowledge_processing as kp

    digests = [
        kp.SectionDigest(abschnitt_de="Das Atelier", verdichtung="- 14 Jugendliche\n- jeden Dienstag",
                         begriffe=[{"term": "Atelier", "definition": "Werkraum"}],
                         source_heading="Kapitel 1: Das Atelier", missing=False),
        kp.SectionDigest(abschnitt_de="Die Ausstellung", verdichtung="Bilder im Flur der Schule.",
                         begriffe=[], source_heading="Kapitel 2: Die Ausstellung", missing=False),
    ]
    return kp.assemble_markdown({"id": "doc-x", "titel": "Bildung und Kultur"},
                                "Ein Schulatelier in Feldbach.", digests)


@pytest.fixture()
def scene_env(tmp_path, monkeypatch):
    """All storage into tmp_path: the scene documents space and the curated
    lists; the space module reloaded (module-level test idiom)."""
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


@pytest.fixture()
def check(monkeypatch):
    """The platform's safety check, stubbed: the texts it was asked about are
    recorded, and a text containing an entry of `unsafe` fails."""
    from my_app.services.llm_service import llm_service

    asked = []
    unsafe = []
    state = {"unavailable": False}

    def _check(text, safety_level=None):
        asked.append((text, safety_level))
        if state["unavailable"]:
            return {"is_safe": False, "reason": "Technische Störung", "unavailable": True}
        if any(u in text for u in unsafe):
            return {"is_safe": False, "reason": "rejected"}
        return {"is_safe": True}

    monkeypatch.setattr(llm_service, "check_safety", _check)
    return asked, unsafe, state


class TestSummaryParts:
    def test_profile_sections_glossary(self):
        from my_app.services.scene_ingest_service import summary_from_markdown

        s = summary_from_markdown(_markdown())
        assert s["profile"] == "Ein Schulatelier in Feldbach."
        assert [x["heading"] for x in s["sections"]] == ["Das Atelier", "Die Ausstellung"]
        assert s["sections"][0]["body"] == "- 14 Jugendliche\n- jeden Dienstag"
        # The review anchor back to the original heading is curation plumbing.
        assert all("quelle" not in x["body"] for x in s["sections"])
        assert s["glossary"] == [{"term": "Atelier", "definition": "Werkraum"}]


class TestSafetyCheck:
    def test_every_part_is_asked_with_the_level(self, check):
        from my_app.services.scene_ingest_service import _check_summary, summary_from_markdown

        asked, unsafe, state = check
        out, withheld = _check_summary(summary_from_markdown(_markdown()), "kids")
        assert withheld == 0
        assert out["profile"] and len(out["sections"]) == 2 and out["glossary"]
        # profile + two sections + glossary, each on its own, all at "kids"
        assert len(asked) == 4
        assert {lvl for _, lvl in asked} == {"kids"}

    def test_a_failing_section_is_withheld_and_counted(self, check):
        from my_app.services.scene_ingest_service import _check_summary, summary_from_markdown

        asked, unsafe, state = check
        unsafe.append("Flur")
        out, withheld = _check_summary(summary_from_markdown(_markdown()), "kids")
        assert withheld == 1
        assert [x["heading"] for x in out["sections"]] == ["Das Atelier"]
        assert "Flur" not in str(out)

    def test_a_failing_profile_is_withheld(self, check):
        from my_app.services.scene_ingest_service import _check_summary, summary_from_markdown

        asked, unsafe, state = check
        unsafe.append("Schulatelier")
        out, withheld = _check_summary(summary_from_markdown(_markdown()), "youth")
        assert out["profile"] == ""
        assert withheld == 1

    def test_no_answer_raises_never_passes(self, check):
        from my_app.services.scene_ingest_service import _check_summary, summary_from_markdown

        asked, unsafe, state = check
        state["unavailable"] = True
        with pytest.raises(RuntimeError):
            _check_summary(summary_from_markdown(_markdown()), "kids")

    def test_curated_list_hit_is_withheld_without_asking(self, check, monkeypatch):
        from my_app.services import scene_ingest_service as sjs

        asked, unsafe, state = check
        monkeypatch.setattr(ug, "scan_text_layer",
                            lambda text: "86a" if "feldbach" in text else None)
        out, withheld = sjs._check_summary(sjs.summary_from_markdown(_markdown()), "open")
        assert out["profile"] == ""
        assert withheld == 1
        assert all("Feldbach" not in t for t, _ in asked)


def _run_job_to_end(jobs, job_id, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs.get_job(job_id)
        if job["state"] in ("done", "error", "cancelled"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {jobs.get_job(job_id)}")


def _staged(tmp, name):
    staged_dir = tmp / "scene_jobs" / name
    staged_dir.mkdir(parents=True)
    staged_pdf = staged_dir / "document.pdf"
    staged_pdf.write_bytes(mk_pdf())
    return staged_dir, staged_pdf


class TestJob:
    def test_library_condensation_checked_and_stored(self, scene_env, check, monkeypatch):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs
        from my_app.services import knowledge_processing as kp

        staged_dir, staged_pdf = _staged(tmp, "j1")

        def _fake_docling(job_id, pdf_path, raw_out):
            raw_out.write_text(_RAW, encoding="utf-8")
            return 0

        calls = {}

        def _fake_process(raw_md, front_matter, **kw):
            calls.update(kw, raw_md=raw_md, front_matter=front_matter)
            kw["on_progress"](0, 2)
            kw["on_progress"](2, 2)
            return kp.ProcessingResult(
                doc_id=front_matter["id"], markdown=_markdown(), raw_chars=len(raw_md),
                compact_chars=10, ratio=0.1, n_content_sections=2, n_emitted_sections=2,
                n_missing_sections=0, n_glossary=1, warnings=[], fatal=[],
                analyzed_at="2026-09-28T10:00:00+00:00", analysis_lang=kw["target_lang"],
                analysis_model="stub/model")

        monkeypatch.setattr(sjs, "_run_docling", _fake_docling, raising=False)
        monkeypatch.setattr(kp, "process_document", _fake_process)

        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-1", title="Testdokument", staged_pdf=staged_pdf,
            raw_hash="a" * 64, doc_id="doc-aaaaaaaaaaaa", lang="de", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "done", job
        assert job["progress"] == {"units_done": 2, "units_total": 2}
        # The library's condensation, in the surface's language, several at once.
        assert calls["target_lang"] == "de"
        assert calls["map_workers"] == sjs.SUMMARY_MAP_WORKERS
        assert calls["front_matter"] == {"id": "doc-aaaaaaaaaaaa", "titel": "Testdokument"}
        # The raw files are gone.
        assert not staged_pdf.exists()
        assert not (staged_dir / "raw.md").exists()
        doc = space.get_document("journal-1", "doc-aaaaaaaaaaaa")
        assert doc is not None
        assert doc["summary"]["profile"] == "Ein Schulatelier in Feldbach."
        assert len(doc["summary"]["sections"]) == 2
        assert doc["n_withheld"] == 0
        assert doc["meta"]["analysis_lang"] == "de"
        assert doc["meta"]["analysis_model"] == "stub/model"
        assert doc["meta"]["safety_level"] == "kids"

    def test_check_without_answer_stores_nothing(self, scene_env, check, monkeypatch):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs
        from my_app.services import knowledge_processing as kp

        asked, unsafe, state = check
        state["unavailable"] = True
        staged_dir, staged_pdf = _staged(tmp, "j3")

        def _fake_docling(job_id, pdf_path, raw_out):
            raw_out.write_text(_RAW, encoding="utf-8")
            return 0

        monkeypatch.setattr(sjs, "_run_docling", _fake_docling, raising=False)
        monkeypatch.setattr(kp, "process_document", lambda raw_md, fm, **kw: kp.ProcessingResult(
            doc_id=fm["id"], markdown=_markdown(), raw_chars=1, compact_chars=1, ratio=1.0,
            n_content_sections=2, n_emitted_sections=2, n_missing_sections=0, n_glossary=1,
            warnings=[], fatal=[]))

        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-3", title="T", staged_pdf=staged_pdf,
            raw_hash="c" * 64, doc_id="doc-cccccccccccc", lang="en", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "error"
        assert job["message"] == "check-unavailable"
        assert not staged_pdf.exists()
        assert space.get_document("journal-3", "doc-cccccccccccc") is None

    def test_error_path_also_cleans_workdir(self, scene_env, monkeypatch):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        staged_dir, staged_pdf = _staged(tmp, "j2")
        monkeypatch.setattr(sjs, "_run_docling", lambda *a: 1, raising=False)
        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-2", title="T", staged_pdf=staged_pdf,
            raw_hash="b" * 64, doc_id="doc-bbbbbbbbbbbb", lang="en", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "error"
        assert not staged_pdf.exists()


_SUMMARY = {"profile": "P", "sections": [{"heading": "H", "body": "B"}], "glossary": []}


class TestDocumentSpace:
    def test_store_get_list_delete(self, scene_env):
        tmp, space = scene_env
        meta = {"doc_hash": "c" * 64, "title": "D", "analyzed_at": "t",
                "analysis_model": "m", "analysis_lang": "de", "n_withheld": 2}
        d = space.store_document("j", "doc-1", summary=_SUMMARY, meta=meta)
        assert d is not None and d.exists()
        doc = space.get_document("j", "doc-1")
        assert doc["summary"] == _SUMMARY
        assert doc["n_withheld"] == 2
        listed = space.list_documents("j")
        assert listed[0]["doc_id"] == "doc-1"
        assert listed[0]["n_sections"] == 1
        assert space.delete_document("j", "doc-1") is True
        assert space.get_document("j", "doc-1") is None

    def test_capsule_format_counts_as_absent_and_is_replaced(self, scene_env):
        tmp, space = scene_env
        d = tmp / "scene_documents" / "j" / "doc-old"
        d.mkdir(parents=True)
        (d / "document.json").write_text('{"doc_hash": "e"}', encoding="utf-8")
        (d / "capsules.json").write_text("[]", encoding="utf-8")
        (d / "segments.json").write_text("[]", encoding="utf-8")
        assert space.get_document("j", "doc-old") is None
        assert space.list_documents("j") == []
        space.store_document("j", "doc-old", summary=_SUMMARY, meta={"doc_hash": "e"})
        assert not (d / "capsules.json").exists()
        assert not (d / "segments.json").exists()
        assert space.get_document("j", "doc-old")["summary"] == _SUMMARY

    def test_journal_delete_drops_space(self, scene_env):
        tmp, space = scene_env
        space.store_document("jj", "doc-2", summary=_SUMMARY, meta={"doc_hash": "d"})
        assert space.delete_journal_space("jj") == 1
        assert space.list_documents("jj") == []

    def test_unsafe_ids_rejected(self, scene_env):
        tmp, space = scene_env
        # empty id -> None; path separators never survive _safe_id (the id
        # class is [a-z0-9-], traversal collapses into a plain name — the
        # STORED path can never leave the space root)
        assert space.store_document("", "x", summary=_SUMMARY, meta={}) is None
        d = space.store_document("j", "../../etc", summary=_SUMMARY, meta={})
        assert d is not None
        assert d.parent == tmp / "scene_documents" / "j"
        assert ".." not in str(d)
