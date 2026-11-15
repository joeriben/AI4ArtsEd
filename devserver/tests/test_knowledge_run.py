"""
The library runner (scripts/knowledge_run.py), without Docling and without a
model: selection from the transfer table (PDF and DOCX), the licence from an
earlier analysis or the index, the library location per tier, resume per
document, and the call and token ceilings.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from my_app.services import knowledge_processing as kp
from my_app.services.knowledge_extract import from_markdown

_SPEC = importlib.util.spec_from_file_location(
    "knowledge_run", Path(__file__).resolve().parents[1] / "scripts" / "knowledge_run.py")
run = importlib.util.module_from_spec(_SPEC)
sys.modules["knowledge_run"] = run          # the dataclasses look the module up
_SPEC.loader.exec_module(run)

_MD = """## Ablauf

Die Einheit umfasst 6–8 Doppelstunden zu je 90 Minuten im Kunstraum der Schule.

## Auswertung

Die Gruppe bespricht die Bilder und hält fest, was das Bildmodell verändert hat.
"""

_EMPTY_REVIEW = {"omissions": [], "distortions": [], "additions": []}

_HEADER = ["status", "tier", "bereich", "unterordner", "doc_id", "jahr", "titel", "ziel"]


def _llm(system, user, max_tokens=None):
    if "REFUTE" in system:
        return json.dumps(_EMPTY_REVIEW)
    if system.startswith("You classify"):
        return json.dumps({"type": "practice_report", "language": "de", "reason": "x"})
    if "PROFILE" in system:
        return "Praxisbericht."
    return ("## Ablauf\n\nDie Einheit dauert mehrere Doppelstunden.\n\n"
            "## Auswertung\n\nDie Gruppe bespricht, was das Bildmodell geändert hat.")


def _corpus(tmp_path, ids=("doc-a", "doc-b", "doc-c")):
    src = tmp_path / "src"
    rows = []
    for i, doc_id in enumerate(ids):
        sub = "operator/kunst"
        ext = ".docx" if doc_id.endswith("x") else ".pdf"
        (src / sub).mkdir(parents=True, exist_ok=True)
        (src / sub / f"{doc_id}{ext}").write_bytes(b"%PDF")
        rows.append(["ok", "O", "kunst", sub, doc_id, "2024", f"Titel {i}",
                     f"{sub}/{doc_id}{ext}"])
    (src / run.TABLE_NAME).write_text(
        "\n".join("\t".join(r) for r in [_HEADER] + rows) + "\n", encoding="utf-8")
    work = tmp_path / "work"
    for doc_id in ids:
        w = work / "operator/kunst"
        w.mkdir(parents=True, exist_ok=True)
        (w / f"{doc_id}.raw.md").write_text(_MD, encoding="utf-8")
        (w / f"{doc_id}.blocks.json").write_text("{}", encoding="utf-8")
        source = next((src / "operator/kunst").glob(f"{doc_id}.*"))
        (w / f"{doc_id}.source.json").write_text(
            json.dumps({"source": str(source), "sha256": run.file_sha256(source)}),
            encoding="utf-8")
    return src, work


def test_an_extraction_of_another_source_file_is_made_anew(tmp_path, monkeypatch):
    src, work = _corpus(tmp_path, ids=("doc-a",))
    doc = run.Doc("doc-a", src / "operator/kunst/doc-a.pdf", "operator/kunst")
    docling = []

    def fake_docling(cmd, env=None):
        docling.append(env["CUDA_VISIBLE_DEVICES"])
        (work / "operator/kunst/doc-a.blocks.json").write_text("{}", encoding="utf-8")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(run.subprocess, "run", fake_docling)
    monkeypatch.setattr(run.config, "KNOWLEDGE_INGEST_PYTHON", str(tmp_path))
    run.extract(doc, work, False, lambda m: None)
    assert docling == []                                   # same file: reused
    doc.source.write_bytes(b"%PDF other")                  # replaced under the same doc_id
    run.extract(doc, work, False, lambda m: None)
    assert docling == [""]                                 # extracted anew, on the CPU
    record = json.loads((work / "operator/kunst/doc-a.source.json").read_text())
    assert record["sha256"] == run.file_sha256(doc.source)
    (work / "operator/kunst/doc-a.source.json").unlink()   # no record: anew as well
    run.extract(doc, work, False, lambda m: None)
    assert len(docling) == 2


def test_a_kept_description_counts_only_for_the_image_it_was_made_from(tmp_path):
    from my_app.services.knowledge_extract import Block, Extraction
    figs = tmp_path / "d.figures"
    figs.mkdir()
    (figs / "fig-001-p1.png").write_bytes(b"one")
    (figs / "fig-002-p1.png").write_bytes(b"two")
    ext = Extraction(blocks=[Block("figure", page=1, seq=0, image="fig-001-p1.png"),
                             Block("figure", page=1, seq=1, image="fig-002-p1.png")],
                     pages=1, source="docling", figures_dir=figs)
    blocks_json = tmp_path / "d.blocks.json"
    record = {
        "lang": "de",
        "descriptions": {"fig-001-p1.png": "Eins.", "fig-002-p1.png": "Zwei."},
        "image_sha256": {"fig-001-p1.png": run.file_sha256(figs / "fig-001-p1.png"),
                         "fig-002-p1.png": run.file_sha256(figs / "fig-002-p1.png")}}
    run.figures_cache(blocks_json, "d").write_text(json.dumps(record))
    assert run.cached_descriptions(blocks_json, ext, "d") == {}      # no prompt digests: old call
    record["prompt_sha256"] = run._prompt_digests(ext, "de")
    run.figures_cache(blocks_json, "d").write_text(json.dumps(record))
    assert run.cached_descriptions(blocks_json, ext, "d") == {0: "Eins.", 1: "Zwei."}
    (figs / "fig-002-p1.png").write_bytes(b"another figure")
    assert run.cached_descriptions(blocks_json, ext, "d") == {0: "Eins."}
    ext.blocks[0].caption = "Abb. 1: Skizze"                         # another call for figure 1
    assert run.cached_descriptions(blocks_json, ext, "d") == {}


def test_a_kept_description_in_another_language_than_the_record_is_not_kept(tmp_path):
    from my_app.services.knowledge_extract import Block, Extraction
    figs = tmp_path / "d.figures"
    figs.mkdir()
    (figs / "fig-001-p1.png").write_bytes(b"one")
    (figs / "fig-002-p1.png").write_bytes(b"two")
    ext = Extraction(blocks=[Block("figure", page=1, seq=0, image="fig-001-p1.png"),
                             Block("figure", page=1, seq=1, image="fig-002-p1.png")],
                     pages=1, source="docling", figures_dir=figs)
    blocks_json = tmp_path / "d.blocks.json"
    record = {
        "lang": "de",
        "descriptions": {
            "fig-001-p1.png": "Ein Kind steht vor der Wand und malt mit einem Pinsel.",
            "fig-002-p1.png": "A child stands in front of the wall and paints with a brush."},
        "image_sha256": {n: run.file_sha256(figs / n) for n in ("fig-001-p1.png",
                                                                "fig-002-p1.png")},
        "prompt_sha256": run._prompt_digests(ext, "de")}
    run.figures_cache(blocks_json, "d").write_text(json.dumps(record))
    assert list(run.cached_descriptions(blocks_json, ext, "d")) == [0]


@pytest.fixture
def fake(monkeypatch):
    """No Docling, no pdftotext, no model: the extraction comes from _MD and
    every call goes to _llm, counted."""
    calls = []

    def llm_fn(model=None, **_kw):
        def fn(system, user, max_tokens=None):
            calls.append(system[:40])
            return _llm(system, user, max_tokens)
        fn.models_used = ["fake-model"]
        return fn

    monkeypatch.setattr(run, "extract_with_integrity",
                        lambda blocks, source, page_range=None: from_markdown(_MD))
    monkeypatch.setattr(kp, "default_llm_fn", llm_fn)
    import my_app
    monkeypatch.setattr(my_app, "reload_user_settings", lambda *_a: None)
    return calls


def _args(src, work, out, *extra):
    return ["--source-root", str(src), "--work-root", str(work), "--out", str(out),
            "--prior-library", str(out / "no-prior"), "--prior-index", str(out / "none.sqlite"),
            "--ledger", str(out / "ledger.jsonl"), *extra]


def test_selection_reads_tier_bereich_and_a_docx_source(tmp_path):
    src, _ = _corpus(tmp_path, ids=("doc-a", "doc-x"))
    a = run.build_parser().parse_args(["--source-root", str(src)])
    a.tsv = src / run.TABLE_NAME
    docs = {d.doc_id: d for d in run.select_docs(a)}
    assert docs["doc-x"].source.suffix == ".docx" and docs["doc-x"].source.is_file()
    assert docs["doc-a"].tier == "O" and docs["doc-a"].bereich == "kunst"
    assert docs["doc-a"].subdir == "operator/kunst"


def test_library_target_per_tier(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_DIR", tmp_path / "lib")
    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tmp_path / "o")
    d = run.Doc("x", tmp_path / "x.pdf", "")
    assert run.library_target(run.Doc(**{**d.__dict__, "tier": "F"})) == tmp_path / "lib/unesco/x.md"
    assert run.library_target(run.Doc(**{**d.__dict__, "tier": "R"})) == tmp_path / "lib/research/x.md"
    assert run.library_target(run.Doc(**{**d.__dict__, "tier": "O"})) == tmp_path / "o/x.md"


def test_a_draft_does_not_replace_a_published_library_file(monkeypatch, tmp_path):
    import argparse
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tmp_path / "o")
    d = run.Doc("x", tmp_path / "x.pdf", "", tier="O")
    a = argparse.Namespace(write_library=True, out=tmp_path / "run")
    lib, held = tmp_path / "o/x.md", tmp_path / "run/condensed/x.md"
    assert run.output_path(d, a, "draft") == lib               # no library file yet
    lib.parent.mkdir(parents=True)
    lib.write_text("---\nid: x\nstatus: published\n---\n# X\n", encoding="utf-8")
    assert run.output_path(d, a, "draft") == held
    assert run.output_path(d, a, "published") == lib
    lib.write_text("---\nid: x\nstatus: draft\n---\n# X\n", encoding="utf-8")
    assert run.output_path(d, a, "draft") == lib
    assert run.output_path(d, argparse.Namespace(write_library=False, out=tmp_path / "run"),
                           "published") == held


def test_licence_from_prior_file_else_from_the_index(tmp_path):
    db = tmp_path / "idx.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE docs (doc_id TEXT, lizenz TEXT)")
    con.execute("INSERT INTO docs VALUES ('doc-a', 'CC BY 4.0')")
    con.commit()
    con.close()
    doc = run.Doc("doc-a", tmp_path / "a.pdf", "", tier="O")
    spec, origin = run.make_spec(doc, None, db)
    assert spec["lizenz"] == "CC BY 4.0" and origin == "knowledge index"
    spec, origin = run.make_spec(doc, {"lizenz": "Alle Rechte vorbehalten", "_path": "p.md"}, db)
    assert spec["lizenz"] == "Alle Rechte vorbehalten" and origin == "library file p.md"
    assert run.make_spec(run.Doc("doc-z", tmp_path, ""), None, db)[1] == "none"


def test_fixed_doc_types_carry_the_normative_texts():
    assert set(run.FIXED_DOC_TYPES.values()) == {"normative_text"}
    assert "normative_text" in kp.DOC_TYPES


def test_a_run_writes_to_out_not_to_the_library_and_resumes(fake, tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tmp_path / "library-o")
    src, work = _corpus(tmp_path)
    out = tmp_path / "out"
    assert run.main(_args(src, work, out)) == 0
    for d in ("doc-a", "doc-b", "doc-c"):
        assert (out / "condensed" / f"{d}.md").is_file()
        side = json.loads((out / "condensed" / f"{d}.checks.json").read_text(encoding="utf-8"))
        assert side["review"]["passed"] is True
        assert run.read_state(out, d)["state"] == "done"
        assert (out / "logs" / f"{d}.log").read_text(encoding="utf-8").count("written") == 1
    assert not (tmp_path / "library-o").exists()          # no --write-library
    n = len(fake)
    assert run.main(_args(src, work, out)) == 0             # all done: skipped
    assert len(fake) == n
    run.write_state(out, "doc-b", state="stopped", reason="x")
    assert run.main(_args(src, work, out)) == 0             # only doc-b again
    assert len(fake) == n + n // 3
    assert run.main(_args(src, work, out, "--force", "--doc-id", "doc-a")) == 0
    assert len(fake) == n + 2 * (n // 3)


def test_write_library_puts_the_file_where_its_tier_lives(fake, tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tmp_path / "library-o")
    src, work = _corpus(tmp_path, ids=("doc-a",))
    out = tmp_path / "out"
    assert run.main(_args(src, work, out, "--write-library")) == 0
    assert (tmp_path / "library-o" / "doc-a.md").is_file()
    assert (tmp_path / "library-o" / "doc-a.checks.json").is_file()
    assert not (out / "condensed").exists()


def test_the_call_ceiling_stops_before_the_call_and_writes_nothing(fake, tmp_path):
    src, work = _corpus(tmp_path)
    out = tmp_path / "out"
    assert run.main(_args(src, work, out)) == 0
    per_doc = len(fake) // 3
    out2 = tmp_path / "out2"
    fake.clear()
    rc = run.main(_args(src, work, out2, "--max-calls", str(per_doc + 2)))
    assert rc == 2
    assert len(fake) == per_doc + 2                         # never past the ceiling
    assert run.read_state(out2, "doc-a")["state"] == "done"
    assert run.read_state(out2, "doc-b")["state"] == "stopped"
    assert "call ceiling" in run.read_state(out2, "doc-b")["reason"]
    assert not (out2 / "condensed" / "doc-b.md").exists()
    assert run.read_state(out2, "doc-c") == {}              # not started
    fake.clear()
    assert run.main(_args(src, work, out2)) == 0            # resume: b and c
    assert len(fake) == 2 * per_doc
    assert run.read_state(out2, "doc-c")["state"] == "done"


def test_the_token_ceiling_reads_the_usage_ledger(fake, tmp_path, monkeypatch):
    src, work = _corpus(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    ledger = out / "ledger.jsonl"
    ledger.write_text(json.dumps({"model": "fake-model", "input_tokens": 10**6,
                                  "output_tokens": 0}) + "\n")
    inner = kp.default_llm_fn

    def logging_llm_fn(model=None, **kw):
        fn = inner(model, **kw)

        def logged(system, user, max_tokens=None):
            with ledger.open("a") as fh:
                fh.write(json.dumps({"model": "fake-model", "input_tokens": 400,
                                     "output_tokens": 100}) + "\n")
                fh.write(json.dumps({"model": "other-model", "input_tokens": 10**6,
                                     "output_tokens": 0}) + "\n")   # another run's call
            return fn(system, user, max_tokens)
        logged.models_used = fn.models_used
        return logged

    monkeypatch.setattr(kp, "default_llm_fn", logging_llm_fn)
    rc = run.main(_args(src, work, out, "--max-tokens", "2000"))
    assert rc == 2                                          # earlier records do not count
    assert len(fake) == 4                                   # 4 x 500 tokens, then stop
    state = run.read_state(out, "doc-a")
    assert state["state"] == "stopped" and "token ceiling" in state["reason"]


def test_usage_per_document_comes_from_the_ledger(fake, tmp_path, monkeypatch):
    src, work = _corpus(tmp_path, ids=("doc-a",))
    out = tmp_path / "out"
    out.mkdir()
    ledger = out / "ledger.jsonl"
    inner = kp.default_llm_fn

    def logging_llm_fn(model=None, **kw):
        fn = inner(model, **kw)

        def logged(system, user, max_tokens=None):
            with ledger.open("a") as fh:
                fh.write(json.dumps({"model": "fake-model", "input_tokens": 7,
                                     "output_tokens": 3}) + "\n")
            return fn(system, user, max_tokens)
        logged.models_used = fn.models_used
        return logged

    monkeypatch.setattr(kp, "default_llm_fn", logging_llm_fn)
    assert run.main(_args(src, work, out)) == 0
    usage = run.read_state(out, "doc-a")["usage"]
    assert usage == {"calls": len(fake), "input_tokens": 7 * len(fake),
                     "output_tokens": 3 * len(fake)}


def test_the_dry_run_plans_without_a_call_and_skips_a_planned_document(fake, tmp_path):
    src, work = _corpus(tmp_path)
    out = tmp_path / "out"
    assert run.main(_args(src, work, out, "--dry-run")) == 0
    assert fake == []
    plan = json.loads((out / "plan" / "doc-a.plan.json").read_text(encoding="utf-8"))
    assert plan["plan"]["totals"]["review_calls"] == len(plan["plan"]["units"]) == 1
    totals = json.loads((out / "plan" / "totals.json").read_text(encoding="utf-8"))
    assert totals["documents"] == 3 and totals["units"] == 3 and totals["review_calls"] == 3
    (out / "plan" / "doc-b.plan.json").write_text(
        json.dumps(dict(plan, doc_id="doc-b", marker=1)), encoding="utf-8")
    assert run.main(_args(src, work, out, "--dry-run")) == 0
    assert json.loads((out / "plan" / "doc-b.plan.json").read_text(encoding="utf-8"))["marker"] == 1


def _figure_corpus(tmp_path, monkeypatch):
    """doc-a with two numbered figures and a description kept beside its
    extraction by an earlier model."""
    from PIL import Image
    from my_app.services.knowledge_extract import Block, Extraction
    src, work = _corpus(tmp_path, ids=("doc-a",))
    wdir = work / "operator/kunst"
    figs = wdir / "doc-a.figures"
    figs.mkdir()
    for name, box in (("fig-001-p1.png", (0, 0, 100, 300)), ("fig-002-p2.png", (0, 0, 300, 100))):
        im = Image.new("RGB", (300, 300), (200, 200, 200))
        im.paste((10, 10, 10), box)
        im.save(figs / name)
    blocks = [Block("paragraph", text="Abb. 1 zeigt eine Skizze.", page=1, seq=0),
              Block("figure", page=1, seq=1, figure_no="1", caption="Abb. 1: Skizze",
                    image="fig-001-p1.png"),
              Block("figure", page=2, seq=2, figure_no="2", caption="Abb. 2: Foto",
                    image="fig-002-p2.png")]
    monkeypatch.setattr(run, "extract_with_integrity", lambda b, s, r=None: Extraction(
        blocks=[Block(**vars(x)) for x in blocks], pages=2, source="docling",
        figures_dir=figs))
    kept = run.figures_cache(wdir / "doc-a.blocks.json", "doc-a")
    kept.write_text(json.dumps({"model": "local/qwen3-vl:4b", "lang": "de",
                                "descriptions": {"fig-001-p1.png": "Ein Wort: SLUT."}}),
                    encoding="utf-8")
    seen = []

    def describe(extraction, lang, model=None, timings=None):
        seen.append((lang, model, [f.image for f in extraction.figures_to_describe()]))
        return {f.seq: f"Neu {f.seq}." for f in extraction.figures_to_describe()}
    monkeypatch.setattr(kp, "describe_figures", describe)
    import my_app
    monkeypatch.setattr(my_app, "reload_user_settings", lambda *_a: None)
    return src, work, kept, seen


def test_figures_only_compares_image_models_without_touching_the_kept_descriptions(
        tmp_path, monkeypatch):
    src, work, kept, seen = _figure_corpus(tmp_path, monkeypatch)
    before = kept.read_bytes()
    out = tmp_path / "compare"
    assert run.main(_args(src, work, out, "--doc-id", "doc-a", "--figures-only",
                          "--image-model", "mammouth/big-vlm")) == 0
    # The language comes from the kept record; the model is the one asked for.
    assert seen == [("de", "mammouth/big-vlm", ["fig-001-p1.png", "fig-002-p2.png"])]
    assert kept.read_bytes() == before
    record = json.loads((out / "figures" / "doc-a.figures.json").read_text(encoding="utf-8"))
    assert record["model"] == "mammouth/big-vlm"
    assert record["leased_at"] is None  # an online model takes no lease of the card
    assert record["descriptions"] == {"fig-001-p1.png": "Neu 1.", "fig-002-p2.png": "Neu 2."}
    page = (out / "figures" / "doc-a.compare.md").read_text(encoding="utf-8")
    assert "Ein Wort: SLUT." in page and "Neu 1." in page
    assert "Caption: Abb. 1: Skizze" in page and "Passage: Abb. 1 zeigt eine Skizze." in page
    assert not (out / "condensed").exists()


def test_figures_only_with_describe_figures_keeps_them_beside_the_extraction(
        tmp_path, monkeypatch):
    src, work, kept, seen = _figure_corpus(tmp_path, monkeypatch)
    out = tmp_path / "run"
    assert run.main(_args(src, work, out, "--doc-id", "doc-a", "--figures-only",
                          "--describe-figures", "--image-model", "mammouth/big-vlm",
                          "--lang", "en")) == 0
    assert seen[0][0] == "en"
    record = json.loads(kept.read_text(encoding="utf-8"))
    assert record["model"] == "mammouth/big-vlm" and record["descriptions"]["fig-002-p2.png"] == "Neu 2."
    assert not (out / "figures").exists()


def test_an_excerpt_carries_its_pages_into_the_spec_and_the_source_record(tmp_path):
    """EXCERPT_PAGES gives the PDF pages of a chapter; a prior library file's
    `pdf_seiten` comes first. The source record keeps the SHA-256 of the
    whole file and names the range."""
    did = "wagner-2021-von-der-entmachtung-des-westlichen-blicks-eine-prognose-zum-ende-der-documenta-als-ausstellungsform-seiten-9-10"
    assert run.EXCERPT_PAGES[did] == (9, 10)
    doc = run._row_doc({"doc_id": did, "ziel": "operator/x/w.pdf"}, tmp_path)
    assert doc.pdf_range == (9, 10)
    assert run.make_spec(doc, None)[0]["pdf_seiten"] == "9-10"
    assert run.make_spec(doc, {"pdf_seiten": "9-9", "_path": "p.md"})[0]["pdf_seiten"] == "9-9"
    assert run.make_spec(run.Doc("doc-a", tmp_path / "a.pdf", ""), None)[0]["pdf_seiten"] == ""
    blocks = tmp_path / f"{did}.blocks.json"
    run.source_record_path(blocks, did).write_text(json.dumps({"sha256": "abc"}), encoding="utf-8")
    rec = run.source_record(blocks, did, (9, 10))
    assert rec == {"sha256": "abc", "pdf_seiten": "9-10"}
    assert json.loads(run.source_record_path(blocks, did).read_text())["pdf_seiten"] == "9-10"
    assert "pdf_seiten" not in run.source_record(blocks, did, None)


def test_the_ledger_counts_the_records_of_the_run_s_models_only(tmp_path):
    """Another model's calls at the same time are not this run's (issue #138)."""
    ledger = run.UsageLedger(tmp_path / "ledger.jsonl")
    mark = ledger.mark()
    ledger.path.write_text("\n".join(json.dumps(r) for r in [
        {"model": "glm-5.3", "input_tokens": 100, "output_tokens": 50000},
        {"model": "claude-sonnet-5.5", "input_tokens": 10, "output_tokens": 20},
        {"model": "glm-5.3", "input_tokens": 1, "output_tokens": 2}]) + "\n")
    assert run.UsageLedger.tokens(ledger.since(mark, ["openrouter/anthropic/claude-sonnet-5.5"])) \
        == {"calls": 1, "input_tokens": 10, "output_tokens": 20}
    assert run.UsageLedger.tokens(ledger.since(mark, ["openrouter/z-ai/glm-5.3"]))["calls"] == 2
    assert run.UsageLedger.tokens(ledger.since(mark))["calls"] == 3


def test_the_ledger_names_the_prompt_cache_where_the_records_carry_it(tmp_path):
    ledger = run.UsageLedger(tmp_path / "ledger.jsonl")
    mark = ledger.mark()
    ledger.path.write_text("\n".join(json.dumps(r) for r in [
        {"model": "claude-opus-5.5", "input_tokens": 30000, "output_tokens": 9000,
         "cache_write_tokens": 29000},
        {"model": "claude-opus-5.5", "input_tokens": 31000, "output_tokens": 800,
         "cache_read_tokens": 29000},
        {"model": "claude-opus-5.5", "input_tokens": 500, "output_tokens": 300}]) + "\n")
    usage = run.UsageLedger.tokens(ledger.since(mark))
    assert usage == {"calls": 3, "input_tokens": 61500, "output_tokens": 10100,
                     "cache_read_tokens": 29000, "cache_write_tokens": 29000}
    assert run.UsageLedger.cache_text(usage) == \
        " (of them 29000 read from the prompt cache, 29000 written to it)"
    assert run.UsageLedger.cache_text({"calls": 1, "input_tokens": 1, "output_tokens": 1}) == ""


def test_the_counting_wrapper_passes_the_document_on_and_counts_it():
    seen = []

    def fn(system, user, max_tokens=None, document=None, cache_ttl=""):
        seen.append((system, user, document, cache_ttl))
        return "ok"
    fn.takes_document = True

    llm = run.CountingLlm(fn=fn)
    assert llm.takes_document is True
    assert llm("S", "U", None, document="DOC", cache_ttl="1h") == "ok"
    assert seen == [("S", "U", "DOC", "1h")]
    assert llm.input_chars == len("S") + len("U") + len("DOC")
    assert run.CountingLlm(fn=_llm).takes_document is False


def test_review_only_reviews_the_condensation_under_out_without_changing_it(fake, tmp_path):
    src, work = _corpus(tmp_path, ids=("doc-a",))
    out = tmp_path / "out"
    assert run.main(_args(src, work, out)) == 0
    md = out / "condensed" / "doc-a.md"
    written = md.read_text(encoding="utf-8")
    n = len(fake)
    extra = ("--review-only", "--model", "openrouter/anthropic/claude-opus-5.5",
             "--reasoning-effort", "high")
    assert run.main(_args(src, work, out, *extra)) == 0
    assert md.read_text(encoding="utf-8") == written
    review_calls = fake[n:]
    assert review_calls == ["You review the summary of a document, or"]  # one unit, one call
    record = json.loads((out / "review" / "claude-opus-5.5-high" / "doc-a.json")
                        .read_text(encoding="utf-8"))
    assert record["condensed_by"] == "fake-model" and record["reasoning_effort"] == "high"
    assert record["verdict"]["passed"] is True and record["llm_calls"] == len(review_calls)
    assert run.main(_args(src, work, out, *extra)) == 0     # reviewed before: skipped
    assert len(fake) == n + len(review_calls)
