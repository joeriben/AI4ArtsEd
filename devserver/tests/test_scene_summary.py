"""The flow's document summary — the job service and the session space.

A PDF brought in through the flow's plus is taken in at the intake once the
converter has read it, condensed by the library's own procedure
(knowledge_processing.process_document) and then checked part by part at the
result before anything is stored. Covered here, with no network, no Docling
and no model (the platform's checks stand in):

  * the sections the intake takes the document's text in by,
  * the parts of a library condensation the card shows (profile, sections
    without their review anchors, glossary),
  * the check at the result: a failing part is withheld and counted, a check
    with no answer ends the job without storing anything,
  * the job end to end: the intake before the condensation, a refused
    document not condensed and not stored, the library's condensation with
    the surface's language, the raw files gone afterwards, the summary in
    the space,
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
    """The check at the result, standing in: the texts it was asked about are
    recorded with the level and the field, and a text containing an entry of
    `unsafe` fails; with state["unavailable"] it gives no answer."""
    import my_app.services.scene_ingest_service as sjs
    from my_app.services import safety_gate as gate

    asked = []
    unsafe = []
    state = {"unavailable": False}

    def _check(text, *, level, field="text"):
        asked.append((text, level, field))
        if state["unavailable"]:
            return gate.Verdict(False, gate.CHECKPOINT_RESULT, level, field,
                                gate.REASON_UNAVAILABLE, "no answer")
        if any(u in text for u in unsafe):
            return gate.Verdict(False, gate.CHECKPOINT_RESULT, level, field,
                                gate.REASON_CONTENT, "rejected")
        return gate.Verdict(True, gate.CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(sjs, "check_result_text", _check)
    return asked, unsafe, state


@pytest.fixture()
def intake(monkeypatch):
    """The intake, standing in: it records what it was asked, and refuses with
    answer["reason_key"] where one is set. Its refusal carries a sentence
    that names what it found, as the intake's own does."""
    import my_app.services.scene_ingest_service as sjs
    from my_app.services import safety_gate as gate

    asked = []
    answer = {"reason_key": ""}

    def _intake(material, *, level, kind, field):
        asked.append((material, level, kind, field))
        if answer["reason_key"]:
            return gate.Verdict(False, gate.CHECKPOINT_INTAKE, level, f"{field}[1]",
                                answer["reason_key"], "gefunden: Max Mustermann")
        return gate.Verdict(True, gate.CHECKPOINT_INTAKE, level, field)

    monkeypatch.setattr(sjs, "check_intake", _intake)
    return asked, answer


class TestDocumentSections:
    def test_a_section_runs_from_heading_to_heading(self):
        from my_app.services.scene_ingest_service import document_sections

        sections = document_sections(_RAW)
        assert [s.splitlines()[0] for s in sections] == [
            "# Bildung und Kultur", "## Einleitung",
            "## Kapitel 1: Das Atelier", "## Kapitel 2: Die Ausstellung"]
        assert " ".join(sections).split() == _RAW.split()

    def test_text_before_the_first_heading_is_a_section(self):
        from my_app.services.scene_ingest_service import document_sections

        assert document_sections("Titelblatt\n\n# Eins\nText") == [
            "Titelblatt", "# Eins\nText"]

    def test_a_long_section_is_cut_between_paragraphs_and_loses_nothing(self):
        from my_app.services import scene_ingest_service as sjs

        text = "\n\n".join(f"Absatz {i} " + "wort " * 300 for i in range(40))
        sections = sjs.document_sections(text)
        assert len(sections) > 1
        assert all(len(s) <= sjs._INTAKE_SECTION_CHARS for s in sections)
        assert all(s.startswith("Absatz ") for s in sections)
        assert " ".join(sections).split() == text.split()

    def test_a_paragraph_without_breaks_is_cut_at_the_limit(self):
        from my_app.services import scene_ingest_service as sjs

        text = "x" * (2 * sjs._INTAKE_SECTION_CHARS + 5)
        sections = sjs.document_sections(text)
        assert [len(s) for s in sections] == [
            sjs._INTAKE_SECTION_CHARS, sjs._INTAKE_SECTION_CHARS, 5]
        assert "".join(sections) == text

    def test_an_empty_document_has_no_section(self):
        from my_app.services.scene_ingest_service import document_sections

        assert document_sections("") == []
        assert document_sections("\n  \n") == []


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
    def test_every_part_is_asked_with_the_level_under_its_name(self, check):
        from my_app.services.scene_ingest_service import _check_summary, summary_from_markdown

        asked, unsafe, state = check
        out, withheld = _check_summary(summary_from_markdown(_markdown()), "kids")
        assert withheld == 0
        assert out["profile"] and len(out["sections"]) == 2 and out["glossary"]
        # profile + two sections + glossary, each on its own, all at "kids"
        assert [field for _, _, field in asked] == [
            "profile", "sections[0]", "sections[1]", "glossary"]
        assert {lvl for _, lvl, _ in asked} == {"kids"}
        assert asked[1][0] == "Das Atelier\n\n- 14 Jugendliche\n- jeden Dienstag"

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

    def test_a_failing_glossary_is_withheld(self, check):
        from my_app.services.scene_ingest_service import _check_summary, summary_from_markdown

        asked, unsafe, state = check
        unsafe.append("Werkraum")
        out, withheld = _check_summary(summary_from_markdown(_markdown()), "adult")
        assert out["glossary"] == []
        assert withheld == 1
        assert asked[-1][1:] == ("adult", "glossary")

    def test_no_answer_raises_never_passes(self, check):
        from my_app.services.scene_ingest_service import _check_summary, summary_from_markdown

        asked, unsafe, state = check
        state["unavailable"] = True
        with pytest.raises(RuntimeError):
            _check_summary(summary_from_markdown(_markdown()), "kids")


def _run_job_to_end(jobs, job_id, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs.get_job(job_id)
        if job["state"] in ("done", "error", "cancelled", "blocked"):
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
    def test_library_condensation_checked_and_stored(self, scene_env, check, intake,
                                                     monkeypatch):
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
                doc_id=front_matter["id"], markdown=_markdown(), source_chars=1,
                compact_chars=10, n_units=2, n_emitted_sections=2,
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
        assert job["safety_block"] is None
        assert job["progress"] == {"units_done": 2, "units_total": 2}
        # The intake took the text in, section by section, at the job's level.
        assert intake[0] == [(sjs.document_sections(_RAW), "kids", "document", "document")]
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
        # Every part went through the check, at the level the route resolved.
        asked = check[0]
        assert {level for _, level, _field in asked} == {"kids"}
        assert len(asked) == 4  # profile, two sections, glossary

    def test_job_behind_the_same_document_reads_nothing_again(self, scene_env, check, monkeypatch):
        """Two sessions queue the same file: the second job takes the first's
        summary when its turn comes, and neither reader runs."""
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        raw_hash = "b" * 64
        doc_id = space.doc_id_for(raw_hash)
        space.store_document(
            "journal-first", doc_id,
            summary={"profile": "P", "sections": [], "glossary": []},
            meta={"doc_id": doc_id, "doc_hash": raw_hash, "title": "T",
                  "analysis_lang": "de", "safety_level": "kids", "n_withheld": 0})
        staged_dir, staged_pdf = _staged(tmp, "j-second")

        def _no_docling(*a, **kw):
            raise AssertionError("the file was read a second time")

        monkeypatch.setattr(sjs, "_run_docling", _no_docling, raising=False)
        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-second", title="T", staged_pdf=staged_pdf,
            raw_hash=raw_hash, doc_id=doc_id, lang="de", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "done", job
        assert not staged_pdf.exists()
        assert space.get_document("journal-second", doc_id)["summary"]["profile"] == "P"

    def test_a_job_that_crashes_leaves_no_raw_file(self, scene_env, check, monkeypatch):
        """§6: the raw PDF goes at any outcome, a crash of the job included."""
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        def _crash(*a, **kw):
            raise OSError("disk full")

        monkeypatch.setattr(sjs, "take_summary", _crash)
        staged_dir, staged_pdf = _staged(tmp, "j-crash")
        job_id = sjs.enqueue_scene_ingest(
            journal_id="j", title="T", staged_pdf=staged_pdf, raw_hash="c" * 64,
            doc_id="doc-cccccccccccc", lang="de", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "error"
        assert not staged_dir.exists()

    def test_check_without_answer_on_a_stored_summary_ends_the_job(self, scene_env, check):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        raw_hash = "d" * 64
        doc_id = space.doc_id_for(raw_hash)
        space.store_document(
            "journal-first", doc_id,
            summary={"profile": "P", "sections": [], "glossary": []},
            meta={"doc_id": doc_id, "doc_hash": raw_hash, "title": "T",
                  "analysis_lang": "de", "safety_level": "research", "n_withheld": 0})
        check[2]["unavailable"] = True
        staged_dir, staged_pdf = _staged(tmp, "j-nocheck")
        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-second", title="T", staged_pdf=staged_pdf,
            raw_hash=raw_hash, doc_id=doc_id, lang="de", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "error"
        assert job["message"] == "check-unavailable"
        assert not staged_pdf.exists()

    def test_the_intake_comes_before_the_condensation(self, scene_env, check, intake,
                                                      monkeypatch):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs
        from my_app.services import knowledge_processing as kp

        staged_dir, staged_pdf = _staged(tmp, "j4")
        order = []

        def _fake_docling(job_id, pdf_path, raw_out):
            raw_out.write_text(_RAW, encoding="utf-8")
            return 0

        real_intake = sjs.check_intake

        def _intake(material, **kw):
            order.append("intake")
            return real_intake(material, **kw)

        def _fake_process(raw_md, front_matter, **kw):
            order.append("condensation")
            return kp.ProcessingResult(
                doc_id=front_matter["id"], markdown=_markdown(), source_chars=1,
                compact_chars=1, n_units=2, n_emitted_sections=2,
                n_missing_sections=0, n_glossary=1, warnings=[], fatal=[])

        monkeypatch.setattr(sjs, "_run_docling", _fake_docling, raising=False)
        monkeypatch.setattr(sjs, "check_intake", _intake)
        monkeypatch.setattr(kp, "process_document", _fake_process)

        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-4", title="T", staged_pdf=staged_pdf,
            raw_hash="d" * 64, doc_id="doc-dddddddddddd", lang="de", safety_level="youth",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "done", job
        assert order == ["intake", "condensation"]
        assert intake[0][0][1] == "youth"

    @pytest.mark.parametrize("reason_key", ["personal_data", "content"])
    def test_a_refused_document_is_neither_condensed_nor_stored(
            self, scene_env, check, intake, monkeypatch, reason_key):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs
        from my_app.services import knowledge_processing as kp

        intake[1]["reason_key"] = reason_key
        staged_dir, staged_pdf = _staged(tmp, f"j5-{reason_key}")
        condensed = []

        def _fake_docling(job_id, pdf_path, raw_out):
            raw_out.write_text(_RAW, encoding="utf-8")
            return 0

        monkeypatch.setattr(sjs, "_run_docling", _fake_docling, raising=False)
        monkeypatch.setattr(kp, "process_document",
                            lambda *a, **kw: condensed.append(1))

        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-5", title="T", staged_pdf=staged_pdf,
            raw_hash="e" * 64, doc_id="doc-eeeeeeeeeeee", lang="de", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "blocked", job
        assert job["message"] == "blocked"
        # The kind of refusal and the section; what was found stays out of the
        # job, whose list is open to every caller.
        assert job["safety_block"] == {"checkpoint": "intake", "field": "document[1]",
                                       "reason_key": reason_key, "reason": ""}
        assert "Mustermann" not in str(sjs.list_jobs(log_tail=40))
        assert condensed == []
        assert check[0] == []
        assert not staged_pdf.exists()
        assert not (staged_dir / "raw.md").exists()
        assert space.get_document("journal-5", "doc-eeeeeeeeeeee") is None

    def test_an_intake_without_answer_is_a_fault(self, scene_env, check, intake, monkeypatch):
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs
        from my_app.services import knowledge_processing as kp
        from my_app.services import safety_gate as gate

        intake[1]["reason_key"] = gate.REASON_UNAVAILABLE
        staged_dir, staged_pdf = _staged(tmp, "j6")
        condensed = []

        def _fake_docling(job_id, pdf_path, raw_out):
            raw_out.write_text(_RAW, encoding="utf-8")
            return 0

        monkeypatch.setattr(sjs, "_run_docling", _fake_docling, raising=False)
        monkeypatch.setattr(kp, "process_document",
                            lambda *a, **kw: condensed.append(1))

        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-6", title="T", staged_pdf=staged_pdf,
            raw_hash="f" * 64, doc_id="doc-ffffffffffff", lang="de", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "error"
        assert job["message"] == "check-unavailable"
        assert job["safety_block"] is None
        assert condensed == []
        assert not staged_pdf.exists()
        assert space.get_document("journal-6", "doc-ffffffffffff") is None

    def test_check_without_answer_stores_nothing(self, scene_env, check, intake, monkeypatch):
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
            doc_id=fm["id"], markdown=_markdown(), source_chars=1, compact_chars=1,
            n_units=2, n_emitted_sections=2, n_missing_sections=0, n_glossary=1,
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

        def _half_read(job_id, pdf_path, raw_out):
            raw_out.write_text(_RAW, encoding="utf-8")
            return 1

        monkeypatch.setattr(sjs, "_run_docling", _half_read, raising=False)
        job_id = sjs.enqueue_scene_ingest(
            journal_id="journal-2", title="T", staged_pdf=staged_pdf,
            raw_hash="b" * 64, doc_id="doc-bbbbbbbbbbbb", lang="en", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert job["state"] == "error"
        assert not staged_dir.exists()

    def test_a_job_runs_while_it_looks_for_a_stored_summary(self, scene_env, check, monkeypatch):
        """A cancel during that look is a cancel of a running job: its flag is
        read later, and the state it answered with stays true."""
        tmp, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        seen = {}

        def _look(journal_id, raw_hash, **kw):
            seen["state"] = sjs._JOBS[job_id]["state"]
            return {"meta": {}}

        monkeypatch.setattr(sjs, "take_summary", _look)
        staged_dir, staged_pdf = _staged(tmp, "j-look")
        job_id = sjs.enqueue_scene_ingest(
            journal_id="j", title="T", staged_pdf=staged_pdf, raw_hash="e" * 64,
            doc_id="doc-eeeeeeeeeeee", lang="de", safety_level="kids",
        )
        job = _run_job_to_end(sjs, job_id)
        assert seen["state"] == "running"
        assert job["state"] == "done"
        assert job["started_at"] is not None


class TestStaging:
    @pytest.fixture()
    def root(self, tmp_path, monkeypatch):
        import my_app.services.scene_ingest_service as sjs

        monkeypatch.setattr(sjs, "_staging_root", lambda: tmp_path / "staging")
        return tmp_path / "staging"

    def test_a_workdir_stands_under_this_backend_s_root(self, root):
        import my_app.services.scene_ingest_service as sjs

        d = sjs.new_staging_dir()
        assert d.parent == root
        assert oct(root.stat().st_mode & 0o777) == oct(0o700)

    def test_the_root_carries_the_port_of_this_backend(self, monkeypatch):
        import my_app.services.scene_ingest_service as sjs

        monkeypatch.setenv("PORT", "17812")
        assert sjs._staging_root().name == "scene_pdf_17812"

    def test_a_start_clears_what_jobs_of_the_last_run_staged(self, root):
        import my_app.services.scene_ingest_service as sjs

        d = sjs.new_staging_dir()
        (d / "document.pdf").write_bytes(b"%PDF")
        (d / "raw.md").write_text("Volltext", encoding="utf-8")
        assert sjs.sweep_staging() == 1
        assert list(root.iterdir()) == []

    def test_a_first_start_finds_nothing_to_clear(self, root):
        import my_app.services.scene_ingest_service as sjs

        assert sjs.sweep_staging() == 0


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

    def _store(self, space, journal, raw_hash, lang="de", level="youth", **extra):
        doc_id = space.doc_id_for(raw_hash)
        space.store_document(
            journal, doc_id,
            summary={"profile": journal, "sections": [], "glossary": []},
            meta={"doc_id": doc_id, "doc_hash": raw_hash, "title": "T",
                  "analysis_lang": lang, "safety_level": level, **extra})
        return doc_id

    def test_summary_is_found_only_for_exactly_this_file(self, scene_env):
        _, space = scene_env
        self._store(space, "j1", "a" * 64)
        same_prefix = "a" * 12 + "b" * 52
        assert space.find_summary("a" * 64, lang="de", safety_level="youth") is not None
        assert space.find_summary(same_prefix, lang="de", safety_level="youth") is None

    def test_summary_needs_the_language(self, scene_env):
        _, space = scene_env
        self._store(space, "j1", "a" * 64)
        assert space.find_summary("a" * 64, lang="en", safety_level="youth") is None

    def test_the_loosest_level_is_taken(self, scene_env):
        _, space = scene_env
        self._store(space, "strict", "a" * 64, level="kids")
        self._store(space, "looser", "a" * 64, level="youth")
        self._store(space, "loose", "a" * 64, level="research")
        meta, summary = space.find_summary("a" * 64, lang="de", safety_level="kids")
        assert summary["profile"] == "loose"

    def test_a_copy_cut_at_a_stricter_level_serves_no_looser_session(self, scene_env):
        _, space = scene_env
        self._store(space, "strict", "a" * 64, level="kids", n_withheld=3)
        assert space.find_summary("a" * 64, lang="de", safety_level="research") is None
        assert space.find_summary("a" * 64, lang="de", safety_level="kids") is not None

    def test_a_whole_copy_from_a_stricter_level_serves_a_looser_session(self, scene_env):
        _, space = scene_env
        self._store(space, "strict", "a" * 64, level="kids", n_withheld=0)
        assert space.find_summary("a" * 64, lang="de", safety_level="research") is not None

    def test_a_cut_copy_of_a_looser_level_serves_a_stricter_session(self, scene_env):
        _, space = scene_env
        self._store(space, "loose", "a" * 64, level="research", n_withheld=2)
        assert space.find_summary("a" * 64, lang="de", safety_level="kids") is not None

    def test_a_record_without_a_known_level_does_not_count(self, scene_env):
        _, space = scene_env
        self._store(space, "j1", "a" * 64, level="unknown")
        assert space.find_summary("a" * 64, lang="de", safety_level="youth") is None

    @pytest.mark.parametrize("broken", [b"{", b"\xff\xfe"])
    def test_an_unreadable_record_does_not_count(self, scene_env, broken):
        _, space = scene_env
        doc_id = self._store(space, "j1", "a" * 64)
        (space._doc_dir("j1", doc_id) / "document.json").write_bytes(broken)
        assert space.find_summary("a" * 64, lang="de", safety_level="youth") is None
        assert space.get_document("j1", doc_id) is None

    def test_a_level_covers_itself_and_what_is_looser(self, scene_env):
        _, space = scene_env
        assert space.checked_for({"safety_level": "youth"}, "youth")
        assert space.checked_for({"safety_level": "youth"}, "adult")
        assert not space.checked_for({"safety_level": "youth"}, "kids")
        assert not space.checked_for({"safety_level": "unknown"}, "research")
        assert not space.checked_for({}, "research")

    def test_taking_a_summary_leaves_the_session_it_came_from(self, scene_env, check):
        _, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        doc_id = self._store(space, "first", "a" * 64, job_id="j", journal_id="first")
        doc = sjs.take_summary("second", "a" * 64, title="Mein Name", lang="de",
                               safety_level="youth")
        assert doc["meta"]["journal_id"] == "second"
        assert doc["meta"]["title"] == "Mein Name"
        assert "job_id" not in doc["meta"]
        first = space.get_document("first", doc_id)["meta"]
        assert first["job_id"] == "j"
        assert first["title"] == "T"

    def test_a_taken_summary_goes_through_the_check_of_this_session(self, scene_env, check):
        _, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        asked, unsafe, _state = check
        self._store(space, "loose", "a" * 64, level="research", n_withheld=2)
        unsafe.append("loose")
        doc = sjs.take_summary("strict", "a" * 64, title="T", lang="de", safety_level="kids")
        assert asked == [("loose", "kids", "profile")]
        assert doc["summary"]["profile"] == ""
        assert doc["n_withheld"] == 3
        assert doc["meta"]["safety_level"] == "kids"

    def test_a_taken_summary_keeps_the_stricter_level_it_was_checked_at(self, scene_env, check):
        _, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        self._store(space, "strict", "a" * 64, level="kids")
        doc = sjs.take_summary("loose", "a" * 64, title="T", lang="de", safety_level="research")
        assert doc["meta"]["safety_level"] == "kids"

    def test_a_check_without_answer_stores_nothing_in_this_session(self, scene_env, check):
        _, space = scene_env
        import my_app.services.scene_ingest_service as sjs

        doc_id = self._store(space, "first", "a" * 64)
        check[2]["unavailable"] = True
        with pytest.raises(RuntimeError):
            sjs.take_summary("second", "a" * 64, title="T", lang="de", safety_level="kids")
        assert space.get_document("second", doc_id) is None

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
