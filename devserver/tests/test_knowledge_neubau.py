"""
Tests for the rebuilt processing stage of the knowledge library:
units (knowledge_processing.build_units), the checks (knowledge_checks), the
gate in process_document, the extraction cross-check
(knowledge_extract.cross_check), the dry-run plan (plan_document) and the
retention step (knowledge_retention, scripts/knowledge_retention.py).

No Docling, no network, no model: extractions are built from blocks, the LLM
is a stub.

Run: python3 -m pytest devserver/tests/test_knowledge_neubau.py -q
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.services import knowledge_checks as kc
from my_app.services import knowledge_processing as kp
from my_app.services import knowledge_retention as kr
from my_app.services.knowledge_extract import (Block, Extraction, cross_check, from_markdown,
                                               restore_compound_hyphens)


def _para(text: str, page: int, seq: int = 0) -> Block:
    return Block("paragraph", text=text, page=page, seq=seq)


def _filler(tag: str, chars: int) -> str:
    """A paragraph of about `chars` characters, distinct per tag."""
    words = []
    i = 0
    while len(" ".join(words)) < chars:
        words.append(f"{tag}w{i}")
        i += 1
    return " ".join(words) + "."


def _flatten(units):
    return [b for u in units for b in u.blocks]


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

def test_units_heading_rich_one_unit_per_section():
    blocks = []
    for i in range(6):
        blocks.append(Block("heading", text=f"Kapitel {i}", level=2, page=i + 1))
        blocks.append(_para(_filler(f"k{i}a", 1500), i + 1))
        blocks.append(_para(_filler(f"k{i}b", 1500), i + 1))
    units = kp.build_units(blocks)
    assert [u.heading for u in units] == [f"Kapitel {i}" for i in range(6)]
    assert all(u.parts == 1 for u in units)
    assert _flatten(units) == blocks                      # every block once, in order


def test_units_short_sections_pack_and_keep_their_headings_inside():
    blocks = []
    for i in range(4):
        blocks.append(Block("heading", text=f"Schritt {i + 1}", level=2, page=1))
        blocks.append(_para(_filler(f"s{i}", 300), 1))
    units = kp.build_units(blocks)
    assert len(units) == 1
    assert [b.text for b in units[0].inner_headings] == ["Schritt 2", "Schritt 3", "Schritt 4"]


def test_units_heading_less_cut_in_page_windows_and_lists_stay_whole():
    blocks = []
    for page in range(1, 11):
        for j in range(3):
            blocks.append(_para(_filler(f"p{page}x{j}", 1000), page))
        if page == 5:
            for k in range(6):
                blocks.append(Block("list_item", text=f"Punkt {k} " + _filler(f"l{k}", 200),
                                    page=page, list_id="L5"))
    units = kp.build_units(blocks)
    assert len(units) > 1
    assert all(u.heading == "" for u in units)
    assert _flatten(units) == blocks
    assert all(u.chars <= kp._UNIT_MAX_CHARS for u in units)
    # Every cut lies at a page change.
    for prev, nxt in zip(units, units[1:]):
        assert prev.blocks[-1].page != nxt.blocks[0].page
    # The six items of the list stand in one unit.
    holders = {u.index for u in units for b in u.blocks if b.list_id == "L5"}
    assert len(holders) == 1


def test_a_unit_without_a_heading_takes_the_title_as_derived_heading():
    blocks = [_para(_filler("vorspann", 1500), 1), _para(_filler("vorspann2", 1500), 1),
              Block("heading", text="Kapitel 1", level=2, page=2),
              _para(_filler("k1", 1500), 2), _para(_filler("k1b", 1500), 2)]
    units = kp.build_units(blocks, "Ein Aufsatz")
    assert [(u.heading, u.derived_heading) for u in units] == [
        ("", "Ein Aufsatz"), ("Kapitel 1", "")]
    assert units[0].source_span == "Ein Aufsatz (p. 1)"
    # Without a title nothing is derived, and the anchor stays the dash.
    assert kp.build_units(blocks)[0].source_span == "— (p. 1)"


def test_units_book_chapter_by_chapter_long_chapter_in_windows():
    blocks = []
    page = 1
    for c in range(1, 5):
        blocks.append(Block("heading", text=f"Kapitel {c}", level=1, page=page))
        for s in range(2):
            blocks.append(Block("heading", text=f"{c}.{s + 1} Abschnitt", level=2, page=page))
            blocks.append(_para(_filler(f"c{c}s{s}", 2800), page))
            page += 1
    # A long chapter without sub-headings: 40 pages of text.
    blocks.append(Block("heading", text="Kapitel 5", level=1, page=page))
    for _ in range(40):
        blocks.append(_para(_filler(f"lang{page}", 900), page))
        page += 1
    units = kp.build_units(blocks)
    plain = [u for u in units if u.parts == 1]
    assert [u.heading for u in plain] == [f"Kapitel {c}" for c in range(1, 5)]
    for u in plain:                                       # sub-sections stay inside
        assert len(u.inner_headings) == 2
    long_parts = [u for u in units if u.heading == "Kapitel 5"]
    assert len(long_parts) > 1
    assert [u.part for u in long_parts] == list(range(1, len(long_parts) + 1))
    assert all(u.parts == len(long_parts) for u in long_parts)
    assert _flatten(units) == blocks
    # No unit mixes two chapters.
    for u in units:
        assert len({b.text for b in u.blocks if b.kind == "heading" and b.level == 1}) <= 1


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _pair(source_blocks, output, page_from=0, page_to=0, missing=False):
    return kc.SectionPair(index=0, heading="Abschnitt", source_blocks=source_blocks,
                          output=output, page_from=page_from, page_to=page_to,
                          missing=missing)


_FOUR = [Block("list_item", text=t, page=3, list_id="L1")
         for t in ("Farbe", "Form", "Hell-Dunkel", "Komposition")]


def test_lists_complete_is_clean_and_fused_or_short_list_is_listed():
    ok = kc.check_lists([_pair(_FOUR, "### A\n\n- Farbe\n- Form\n- Hell-Dunkel\n- Komposition")])
    assert not ok.findings and ok.kind == kc.QUALITY
    short = kc.check_lists([_pair(_FOUR, "### A\n\n- Farbe\n- Form\n- Komposition")])
    assert short.findings and short.passed          # listed, not gated (#140)
    assert short.findings[0]["expected_items"] == 4 and short.findings[0]["page"] == 3
    fused = kc.check_lists([_pair(_FOUR, "### A\n\nFarbe, Form, Hell-Dunkel und Komposition.")])
    assert fused.passed and fused.findings[0]["output_lists"] == []


def test_lists_a_broken_list_is_not_covered_by_a_same_length_list_elsewhere():
    questions = [Block("list_item", text=t, page=3 if i == 0 else 4, list_id="Q")
                 for i, t in enumerate(("Wie wirkt die Stimmung?", "Was übernehme ich?",
                                        "Wo bringe ich Neues ein?", "Wie wirkt es stärker?"))]
    source = questions + _FOUR
    broken = ("### A\n\n- „Wie wirkt die Stimmung?“\n\nFortsetzung (S. 4):\n\n"
              "- „Was übernehme ich?“\n- „Wo bringe ich Neues ein?“\n- „Wie wirkt es stärker?“\n\n"
              "Bereiche:\n\n- Farbe\n- Form\n- Hell-Dunkel\n- Komposition")
    res = kc.check_lists([_pair(source, broken)])
    assert res.findings and res.passed
    assert [f["first_item"] for f in res.findings] == ["Wie wirkt die Stimmung?"]
    whole = broken.replace("\n\nFortsetzung (S. 4):\n\n", "\n")
    assert not kc.check_lists([_pair(source, whole)]).findings


def test_render_keeps_a_list_whole_across_a_page_break():
    blocks = [_para("Fragen:", 3)] + [Block("list_item", text=t, page=p, list_id="Q")
                                     for t, p in (("eins", 3), ("zwei", 4), ("drei", 4))]
    assert kp.render_blocks(blocks, "de") == "[S. 3]\n\nFragen:\n\n- eins\n- [S. 4] zwei\n- drei"


def test_lists_numbered_list_across_blank_lines_counts_as_one():
    assert kc.output_lists("1. a\n\n2. b\n\n3. c\n\n4. d") == [4]
    assert kc.output_lists("- a\n- b\n\nText\n\n- c") == [2, 1]


def test_numbers_missing_from_the_summary_are_listed_and_references_do_not_count():
    # 2026-11-13: a summary leaves numbers out by its nature; the check lists
    # them for the review and gates nothing.
    src = [_para("Die Einheit umfasst 6–8 × 90 Minuten (Müller 2019), siehe Abb. 3 auf S. 12.", 4)]
    ok = kc.check_numbers([_pair(src, "### A\n\nUmfang: 6–8 Doppelstunden à 90 Minuten.")])
    assert ok.passed and ok.findings == []
    lost = kc.check_numbers([_pair(src, "### A\n\nUmfang: mehrere Doppelstunden.")])
    assert lost.passed
    assert sorted(f["number"] for f in lost.findings) == ["6", "8", "90"]
    assert all(f["page"] == 4 for f in lost.findings)


def test_page_refs_inside_document_and_section():
    good = "### Ablauf (S. 4–5)\n\nDetail (S. 5)."
    assert kc.check_page_refs([_pair([], good, 4, 5)], 1, 13).passed
    beyond = kc.check_page_refs([_pair([], "### Ablauf (S. 4–5)\n\nDetail (S. 14).", 4, 5)], 1, 13)
    assert not beyond.passed and "outside the document" in beyond.findings[0]["problem"]
    other = kc.check_page_refs([_pair([], "### Ablauf (S. 4–5)\n\nDetail (S. 9).", 4, 5)], 1, 13)
    assert not other.passed and "outside the section" in other.findings[0]["problem"]
    bare = kc.check_page_refs([_pair([], "### Ablauf\n\nDetail.", 4, 5)], 1, 13)
    assert not bare.passed and bare.findings[0]["problem"] == "section heading without pages"
    nopages = kc.check_page_refs([_pair([], "### Ablauf\n\nDetail (p. 2).")], 0, 0, "none")
    assert not nopages.passed and "no page numbers" in nopages.findings[0]["problem"]
    assert kc.check_page_refs([_pair([], "### Ablauf\n\nDetail.")], 0, 0, "none").passed


def test_page_refs_leave_the_figure_list_out():
    # An image of a table of contents: its description gives the pages the
    # image shows, not pages of the section (OECD 2025, image 6).
    out = ("### Ablauf (p. 1–42)\n\nDetail (p. 4).\n\n### Figures (p. 4)\n\n"
           '*Image 6 (p. 4):* — A table of contents: "The AILit Framework" (p. 17-43).')
    pair = _pair([], out, 1, 42)
    pair.figure_idents = ["Image 6"]
    res = kc.check_page_refs([pair], 1, 62)
    assert res.passed, res.findings
    # The same line under an ident the unit does not carry is summary text.
    pair.figure_idents = ["Image 60"]
    assert not kc.check_page_refs([pair], 1, 62).passed


def test_verbatim_share_is_a_copyright_quantity_with_a_ceiling():
    source = " ".join(f"quelle{i}" for i in range(200))
    own = " ".join(f"eigen{i}" for i in range(80))
    copied = " ".join(f"quelle{i}" for i in range(50, 70))           # a run of 20 words
    over = kc.check_verbatim_share(source, copied + " " + own, min_words=7, max_share=0.10)
    assert over.kind == kc.COPYRIGHT and not over.passed
    assert over.value == 0.2 and over.findings[0]["words"] == 20
    clean = kc.check_verbatim_share(source, own, min_words=7, max_share=0.10)
    assert clean.passed and clean.value == 0.0
    # A short marked quotation counts toward the share, it just stays below N.
    quote = '"' + " ".join(f"quelle{i}" for i in range(5)) + '" ' + own
    assert kc.check_verbatim_share(source, quote, min_words=7, max_share=0.10).value == 0.0
    assert kc.check_verbatim_share(source, quote, min_words=5, max_share=0.10).value > 0


def test_verbatim_share_leaves_the_source_lists_out():
    items = [Block("list_item", text=" ".join(f"punkt{k}{i}" for i in range(9)), list_id="L1")
             for k in range(3)]
    lone = [Block("list_item", text=" ".join(f"einzeln{i}" for i in range(9)), list_id="L2")]
    lists = kc.source_list_text(items + lone)
    assert "punkt0" in lists and "einzeln" not in lists      # a list has two or more items
    prose = " ".join(f"quelle{i}" for i in range(100))
    source = prose + "\n" + "\n".join(b.text for b in items)
    own = " ".join(f"eigen{i}" for i in range(60))
    copied = " ".join(f"quelle{i}" for i in range(10, 25))    # 15 words of prose
    listed = "\n".join(f"- {b.text}" for b in items)          # 27 words of the list
    res = kc.check_verbatim_share(source, f"{own} {copied}\n{listed}", min_words=7,
                                  max_share=0.20, list_text=lists)
    assert res.value == 0.2 and res.passed                    # 15 of 75, the list out of both
    assert "27 words from the source's lists" in res.summary
    assert all("punkt" not in f["text"] for f in res.findings)
    counted = kc.check_verbatim_share(source, f"{own} {copied}\n{listed}", min_words=7,
                                      max_share=0.20)
    assert counted.value == round(42 / 102, 4) and not counted.passed
    assert kc.unmarked_verbatim(source, f"{copied}\n{listed}", 7, list_text=lists) == [copied]


def test_unmarked_verbatim_leaves_quotations_and_headings_out():
    source = " ".join(f"quelle{i}" for i in range(100))
    run = " ".join(f"quelle{i}" for i in range(10, 20))
    text = (f"#### {run}\n\nEigen eins „{run}“ eigen zwei.\n\n"
            f"Eigen drei {run} eigen vier.")
    assert kc.unmarked_verbatim(source, text, 7) == [run]
    assert kc.unmarked_verbatim(source, "Eigen eins zwei drei vier fünf sechs sieben.", 7) == []


def _summary_fixture():
    blocks = [Block("heading", text="Schritt 1", level=1, page=2),
              _para("Die Kinder zeichnen zuerst frei aus sich heraus ein Monster in das Skizzenbuch.", 2)]
    units = kp.library_units(blocks, "T")
    calls = []

    def answer(body):
        return f"## Schritt 1\n\n{body}"
    return units, calls, answer


def test_summary_above_the_ceiling_sends_copied_passages_back_once_and_takes_the_revision():
    units, calls, answer = _summary_fixture()
    replies = [answer("Die Kinder zeichnen zuerst frei aus sich heraus ein Monster."),
               answer("Zu Beginn entwerfen die Kinder ohne Vorgabe ein Monster.")]

    def llm(system, user, max_tokens=None):
        calls.append(user)
        return replies[len(calls) - 1]
    d = kp._summarize_unit(units[0], units, llm, title="T", target_lang="de",
                           doc_type="practice_report", has_pages=True)
    assert len(calls) == 2
    assert "die kinder zeichnen zuerst frei aus sich heraus".replace(" ", "") in \
        calls[1].lower().replace(" ", "")
    assert "Zu Beginn entwerfen" in d.verdichtung
    assert "zeichnen zuerst frei" not in d.verdichtung
    assert any("revised to" in n for n in d.notes)


def test_summary_below_the_ceiling_makes_one_call():
    units, calls, answer = _summary_fixture()

    def llm(system, user, max_tokens=None):
        calls.append(user)
        return answer("Zu Beginn entwerfen die Kinder ohne Vorgabe ein Monster.")
    d = kp._summarize_unit(units[0], units, llm, title="T", target_lang="de",
                           doc_type="practice_report", has_pages=True)
    assert len(calls) == 1
    assert d.notes == []


def test_profile_call_receives_the_author_line():
    digests = [kp.SectionDigest(abschnitt_de="Spiel (S. 1)", verdichtung="Ein Spiel.",
                                begriffe=[], source_heading="Spiel")]
    seen = []

    def llm(system, user, max_tokens=None):
        seen.append(user)
        return "- Profil."
    kp._reduce_profile("T", digests, llm, "de", "tool_handout", author="J. Heisig, I. Scharf")
    kp._reduce_profile("T", digests, llm, "de", "tool_handout")
    assert "Author(s): J. Heisig, I. Scharf." in seen[0]
    assert "Author(s)" not in seen[1]


def test_run_checks_keeps_copyright_and_quality_apart():
    ext = Extraction(blocks=[], pages=0, source="markdown")
    report = kc.run_checks([_pair([], "### A\n\nText.")], source_text="a b c",
                           output_text="### A\n\nText.", page_first=0, page_last=0,
                           page_kind="none", integrity=ext.integrity,
                           source="markdown", pending_figures=[], n_figures=0,
                           min_words=7, max_share=0.1)
    kinds = {r.name: r.kind for r in report.results}
    assert [n for n, k in kinds.items() if k == kc.COPYRIGHT] == ["verbatim_share"]
    assert set(kinds) == {"verbatim_share", "lists", "numbers", "headings", "figures",
                          "figure_descriptions", "figure_text", "page_refs", "extraction",
                          "reading_order"}


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

_GATE_MD = """## Ablauf

Die Einheit umfasst 6–8 Doppelstunden zu je 90 Minuten im Kunstraum der Schule.

- Beobachten der Vorlage
- Zeichnen des eigenen Monsters
- Generieren mit dem Bildmodell
- Besprechen in der Gruppe
"""


def _gate_stub(body):
    def llm(system, user, max_tokens=None):
        if "REFUTE" in system:   # the adversarial review: nothing to refute
            return json.dumps({"omissions": [], "distortions": [], "additions": []})
        if system.startswith("You classify"):
            return json.dumps({"type": "practice_report", "language": "de", "reason": "x"})
        if "PROFILE" in system:
            return "Praxisbericht zu einer Unterrichtseinheit."
        return f"## Ablauf\n\n{body}"
    return llm


_FULL_BODY = ("Umfang: 6–8 Doppelstunden à 90 Minuten.\n\n"
              "- Vorlage ansehen\n- eigenes Monster zeichnen\n- Bildmodell nutzen\n- Gruppengespräch")


def test_gate_passed_checks_and_review_publish_a_reprocess():
    # The Monster case of 2026-11-13: a prior draft whose checks and review
    # pass is published; the caller's status no longer decides.
    fm = {"id": "gate-doc", "titel": "Monster-Test", "sprache": "de", "status": "draft"}
    res = kp.process_document(from_markdown(_GATE_MD), fm, llm=_gate_stub(_FULL_BODY), hold="")
    assert res.check_report["passed"], res.check_report["label"]
    assert res.status == "published" and res.checks == "passed" and res.status_reason == ""
    assert "checks: passed" in res.markdown and "status_reason" not in res.markdown


def test_gate_holds_a_fresh_upload_for_the_operator_and_says_so():
    fm = {"id": "gate-doc", "titel": "Monster-Test", "sprache": "de"}
    res = kp.process_document(from_markdown(_GATE_MD), fm, llm=_gate_stub(_FULL_BODY))
    assert res.check_report["passed"]
    assert res.status == "draft" and res.status_reason == "release"
    assert "status: draft\nstatus_reason: release\n" in res.markdown


def test_gate_without_review_is_a_draft_with_that_reason():
    fm = {"id": "gate-doc", "titel": "Monster-Test", "sprache": "de"}
    res = kp.process_document(from_markdown(_GATE_MD), fm, llm=_gate_stub(_FULL_BODY),
                              hold="", review=False)
    assert res.status == "draft" and res.status_reason == "no_review"


def test_gate_status_names_every_reason_of_a_draft():
    assert kp.gate_status(True, True, "") == ("published", "")
    assert kp.gate_status(False, True, "") == ("draft", "checks")
    assert kp.gate_status(True, False, "") == ("draft", "review")
    assert kp.gate_status(False, None, "operator") == ("draft", "checks, no_review, operator")
    assert kp.gate_status(True, True, "release") == ("draft", "release")
    with pytest.raises(ValueError):
        kp.gate_status(True, True, "later")


def test_reprocess_hold_keeps_only_the_operators_draft_and_an_unreleased_upload():
    assert kp.reprocess_hold("draft", "") == ""                      # Monster: no reason recorded
    assert kp.reprocess_hold("draft", "checks, review") == ""
    assert kp.reprocess_hold("published", "") == ""
    assert kp.reprocess_hold("draft", "checks, operator") == "operator"
    assert kp.reprocess_hold("draft", "release") == "release"


def test_gate_lists_and_numbers_are_listed_and_gate_nothing():
    """#140 (2026-11-15): a list given as running text is listed by the lists
    check and holds nothing; the review judges whether an item is missing."""
    fm = {"id": "gate-doc", "titel": "Monster-Test", "sprache": "de", "status": "published"}
    lossy = "Mehrere Doppelstunden; die Schritte reichen vom Ansehen bis zum Gespräch."
    res = kp.process_document(from_markdown(_GATE_MD), fm, llm=_gate_stub(lossy), hold="")
    lists = next(r for r in res.check_report["results"] if r["name"] == "lists")
    assert lists["passed"] and lists["findings"] and "not gated" in lists["summary"]
    assert not [r["name"] for r in res.check_report["results"] if not r["passed"]]
    assert res.checks == "passed" and "checks" not in (res.status_reason or "")
    # The numbers the summary left out are listed, and gate nothing.
    numbers = next(r for r in res.check_report["results"] if r["name"] == "numbers")
    assert numbers["passed"] and sorted(f["number"] for f in numbers["findings"]) == ["6", "8", "90"]


def test_gate_pending_figure_description_forces_draft():
    blocks = [Block("heading", text="Ablauf", level=2, page=1, seq=0),
              _para("Die Gruppe zeichnet Monster.", 1, seq=1),
              Block("figure", page=1, seq=2, figure_no="1", caption="Monster",
                    image="fig-001.png")]
    ext = Extraction(blocks=blocks, pages=1, source="docling")
    ext.integrity.checked = True
    ext.integrity.pages_checked = 1
    fm = {"id": "fig-doc", "titel": "Monster-Test", "sprache": "de", "status": "published"}
    res = kp.process_document(ext, fm, llm=_gate_stub("Die Gruppe zeichnet."),
                              doc_type="practice_report")
    failed = {r["name"] for r in res.check_report["results"] if not r["passed"]}
    assert "figure_descriptions" in failed and res.status == "draft"
    described = kp.process_document(ext, fm, llm=_gate_stub("Die Gruppe zeichnet."),
                                    doc_type="practice_report",
                                    figure_descriptions={2: "Ein Monster mit drei Augen."})
    failed = {r["name"] for r in described.check_report["results"] if not r["passed"]}
    assert "figure_descriptions" not in failed
    assert "Ein Monster mit drei Augen." in described.markdown


# ---------------------------------------------------------------------------
# Extraction cross-check
# ---------------------------------------------------------------------------

def test_cross_check_inserts_the_lost_passage_at_its_place():
    first = "Am Anfang beobachtet die Klasse das Bild des Monsters im Atelier sehr genau."
    lost = "Danach bespricht die Lehrerin Jana mit der Gruppe die Farbgebung der Figuren."
    last = "Zum Schluss stellt jede Gruppe ihr Ergebnis im Plenum der ganzen Klasse vor."
    blocks = [_para(first, 1, 0), _para(last, 1, 1)]
    ext = Extraction(blocks=blocks, pages=1, source="docling")
    rep = cross_check(ext, ["\n".join([first, lost, last])])
    assert rep.checked and rep.pages_checked == 1
    assert len(rep.gaps) == 1 and rep.gaps[0].repaired and rep.gaps[0].page == 1
    texts = [b.text for b in ext.blocks]
    assert len(texts) == 3 and "Jana" in texts[1]
    assert ext.blocks[1].repaired and not ext.blocks[0].repaired
    assert not rep.unrepaired


def test_cross_check_dismisses_duplicates_and_formula_debris():
    # Running head with page number (gabrys-2019 p.17), a Docling heading the
    # layer reads in another order, a display formula (belrose p.17).
    body = "Die Messstationen zeichnen die Luft an vielen Orten der Stadt über Monate auf."
    more = "Die Daten gehen an eine offene Plattform, die alle Bewohner einsehen können."
    head = Block("furniture", text="JENNIFER GABRYS", page=1)
    blocks = [_para(body, 1, 1), _para(more, 1, 2), head]
    ext = Extraction(blocks=blocks, pages=1, source="docling")
    layer = "\n".join(["190   Jennifer Gabrys", body,
                       "m X d X (PX)i = Aij (WX)j + Bij Xj , j=1 j=m+1", more])
    rep = cross_check(ext, [layer])
    assert rep.gaps == []
    reasons = sorted(x["reason"] for x in rep.gaps_dismissed)
    assert reasons == ["debris", "duplicate"]
    assert [b.text for b in ext.blocks] == [body, more, "JENNIFER GABRYS"]
    assert kc.check_extraction(rep, "docling").passed


def test_cross_check_a_fragment_inside_a_joined_word_is_a_duplicate():
    # colombo p.2: the layer's line starts inside "generat-ing".
    para = "Generative systems are now generating visual content."
    other = "Museums and the press take them up in large numbers every single day."
    ext = Extraction(blocks=[_para(para, 1, 0), _para(other, 1, 1)], pages=1, source="docling")
    layer = "\n".join([other, "ing visual content.", "Generative systems are now generat-"])
    rep = cross_check(ext, [layer])
    assert rep.gaps == [] and [x["reason"] for x in rep.gaps_dismissed] == ["duplicate"]


def test_compound_hyphen_joined_at_a_line_break_is_restored():
    head = Block("heading", text="Raumangebote und Atmosphäre durch HellDunkel-Kontraste",
                 level=2, page=1)
    para = Block("paragraph", text="Die Positionierung bleibt.", page=1)
    ext = Extraction(blocks=[head, para], pages=1, source="docling")
    layer = "Raumangebote und Atmosphäre durch Hell-\nDunkel-Kontraste\nDie Positio-\nnierung bleibt."
    restored = restore_compound_hyphens(ext, [layer])
    assert head.text == "Raumangebote und Atmosphäre durch Hell-Dunkel-Kontraste"
    assert para.text == "Die Positionierung bleibt."
    assert restored == [{"page": 1, "ref": "", "word": "Hell-Dunkel"}]


def test_extraction_check_fails_without_a_text_layer():
    ext = Extraction(blocks=[_para("Text ohne Textschicht.", 1)], pages=1, source="docling")
    rep = cross_check(ext, [""])
    assert not rep.checked and rep.reason == "no text layer"
    assert not kc.check_extraction(rep, "docling").passed
    assert kc.check_extraction(rep, "markdown").passed


# ---------------------------------------------------------------------------
# Figure screening and the description call
# ---------------------------------------------------------------------------

def _picture(path, size, seed, tweak=False):
    """A blocky random picture of `size`; the same seed gives the same
    picture, `tweak` changes one pixel (another file, the same picture)."""
    import random
    from PIL import Image
    rnd = random.Random(seed)
    small = Image.new("L", (8, 8))
    small.putdata([rnd.randrange(256) for _ in range(64)])
    im = small.resize(size, Image.NEAREST).convert("RGB")
    if tweak:
        im.putpixel((0, 0), (1, 2, 3))
    im.save(path)


def _screening_extraction(tmp_path):
    figs = tmp_path / "doc.figures"
    figs.mkdir()
    spec = [  # image, size, seed, page, caption, figure_no
        ("fig-001-p1.png", (400, 300), 1, 1, "Abb. 1: Diagramm", "1"),
        ("fig-002-p1.png", (300, 250), 2, 1, "", ""),       # part of figure 1
        ("fig-003-p1.png", (52, 43), 3, 1, "", ""),         # link icon
        ("fig-004-p2.png", (150, 120), 4, 2, "", ""),       # logo ...
        ("fig-005-p3.png", (150, 120), 4, 3, "", ""),       # ... again, another file
        ("fig-006-p2.png", (600, 20), 6, 2, "", ""),        # rule
        ("fig-007-p3.png", (400, 40), 7, 3, "", ""),        # image row, referred to
        ("fig-008-p3.png", (60, 60), 8, 3, "Abb. 2: Symbol", "2"),
        ("fig-009-p3.png", (500, 400), 9, 3, "", ""),
    ]
    blocks = [_para("Abbildung 1 zeigt den Ablauf der Einheit im Kunstraum.", 1, 0)]
    for i, (name, size, seed, page, caption, no) in enumerate(spec, 1):
        _picture(figs / name, size, seed, tweak=(name == "fig-005-p3.png"))
        blocks.append(Block("figure", page=page, seq=i, image=name, caption=caption,
                            figure_no=no, ref=f"#/pictures/{i}"))
    blocks.append(_para("Die Reihe in Abb. 4 zeigt vier Entwürfe.", 3, 20))
    return Extraction(blocks=blocks, pages=3, source="docling", figures_dir=figs)


def test_screening_removes_icons_logos_and_rules_and_keeps_the_parts_of_a_figure(tmp_path):
    from my_app.services.knowledge_extract import screen_figures
    ext = _screening_extraction(tmp_path)
    removed = screen_figures(ext)
    by_image = {r["image"]: r for r in removed}
    assert {k: v["reason"] for k, v in by_image.items()} == {
        "fig-003-p1.png": "small", "fig-004-p2.png": "repeated",
        "fig-005-p3.png": "repeated", "fig-006-p2.png": "strip"}
    # The icon stood beside figure 1: the record names it.
    assert by_image["fig-003-p1.png"]["figure"] == "#/pictures/1"
    assert (by_image["fig-003-p1.png"]["w"], by_image["fig-003-p1.png"]["h"]) == (52, 43)
    assert ext.integrity.figures_screened == removed
    kept = [b.image for b in ext.figures()]
    assert kept == ["fig-001-p1.png", "fig-002-p1.png", "fig-007-p3.png",
                    "fig-008-p3.png", "fig-009-p3.png"]
    # The small labelled figure stays, with its caption only.
    assert [b.image for b in ext.figures_to_describe()] == [
        "fig-001-p1.png", "fig-002-p1.png", "fig-007-p3.png", "fig-009-p3.png"]


def test_a_small_labelled_figure_is_set_with_its_caption_and_is_not_pending(tmp_path):
    from my_app.services.knowledge_extract import screen_figures
    ext = _screening_extraction(tmp_path)
    screen_figures(ext)
    small = next(b for b in ext.figures() if b.image == "fig-008-p3.png")
    assert kp.figure_line(small, "de") == "*Abb. 2 (S. 3):* Symbol"
    plan = kp.plan_document(ext, {"id": "doc", "titel": "Plan", "sprache": "de"})
    assert plan["totals"]["image_calls"] == 4
    assert "fig-008-p3.png" not in {c["image"] for c in plan["image_calls"]}


def test_screening_reads_the_extraction_after_normalise(tmp_path):
    """extract_with_integrity screens right after normalise: a caption that is
    body text no longer labels its picture."""
    import json as _json
    from my_app.services.knowledge_extract import extract_with_integrity
    ext = _screening_extraction(tmp_path)
    blocks_json = tmp_path / "doc.blocks.json"
    d = ext.to_dict()
    d["figures_dir"] = "doc.figures"
    blocks_json.write_text(_json.dumps(d), encoding="utf-8")
    out = extract_with_integrity(blocks_json, None)
    assert len(out.integrity.figures_screened) == 4
    assert out.to_dict()["integrity"]["figures_screened"][0]["reason"] == "small"


def test_the_description_call_carries_caption_and_referring_passage(tmp_path):
    from my_app.services.knowledge_extract import screen_figures
    ext = _screening_extraction(tmp_path)
    screen_figures(ext)
    refs = kp.figure_references(ext.blocks)
    fig1 = next(b for b in ext.figures() if b.figure_no == "1")
    assert refs == {fig1.seq: "Abbildung 1 zeigt den Ablauf der Einheit im Kunstraum."}
    prompt = kp._figure_prompt(fig1, "de", refs[fig1.seq])
    assert "Write in GERMAN, the language of the document" in prompt
    assert "only what is visible" in prompt
    assert "not legible" in prompt
    assert 'Caption: "Abb. 1: Diagramm"' in prompt
    assert "Abbildung 1 zeigt den Ablauf" in prompt
    # An unnumbered picture has no reference; its call carries no context.
    bare = next(b for b in ext.figures() if b.image == "fig-009-p3.png")
    assert bare.seq not in refs
    assert "Caption:" not in kp._figure_prompt(bare, "de")


def test_the_nearest_passage_is_the_reference_and_a_long_one_is_cut():
    long_text = "Vorlauf " * 200 + "wie Abb. 2 zeigt, " + "Nachlauf " * 200
    blocks = [_para("Abb. 2 im ersten Kapitel.", 1, 0),
              Block("heading", text="Kapitel 2", level=2, page=5, seq=1),
              _para(long_text, 5, 2),
              Block("figure", page=5, seq=3, figure_no="2", caption="Abb. 2: Karte",
                    image="f.png"),
              _para("Abb. 12 ist eine andere.", 5, 4)]
    ref = kp.figure_references(blocks)[3]
    assert "wie Abb. 2 zeigt" in ref
    assert len(ref) <= kp.FIGURE_REFERENCE_MAX_CHARS + 2
    assert ref.startswith("…") and ref.endswith("…")


@pytest.fixture()
def reads_images(monkeypatch):
    """The models Settings measured reading an image, as a set the test fills."""
    from my_app.utils import vision_support
    seeing = set()
    monkeypatch.setattr(vision_support, "is_vision_capable", lambda m: m in seeing)
    return seeing


def test_the_library_image_model_is_the_setting_then_the_seeing_condenser_then_image_analysis(
        monkeypatch, reads_images):
    import config
    monkeypatch.setattr(config, "IMAGE_ANALYSIS_MODEL", "local/qwen3-vl:4b", raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_IMAGE_MODEL", "", raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_PROCESSING_MODEL", "mistral/zai-glm-5-3", raising=False)
    assert config._SETTINGS_DEFAULTS["KNOWLEDGE_IMAGE_MODEL"] == ""
    # A condensing model that reads no images leaves the figures to IMAGE_ANALYSIS_MODEL.
    assert kp.figure_model() == ("local/qwen3-vl:4b", "IMAGE_ANALYSIS_MODEL")
    # One that does describes them itself, the slot's or the pinned one.
    reads_images.update({"mistral/mistral-large-4-0", "openrouter/anthropic/claude-opus-5.5"})
    assert kp.figure_model("mistral/mistral-large-4-0")[0] == "mistral/mistral-large-4-0"
    monkeypatch.setattr(config, "KNOWLEDGE_PROCESSING_MODEL",
                        "openrouter/anthropic/claude-opus-5.5", raising=False)
    assert kp.figure_model()[0] == "openrouter/anthropic/claude-opus-5.5"
    # The hand-set image model goes before both.
    monkeypatch.setattr(config, "KNOWLEDGE_IMAGE_MODEL", "local/qwen3-vl:32b", raising=False)
    assert kp.figure_model("mistral/mistral-large-4-0") == ("local/qwen3-vl:32b",
                                                            "KNOWLEDGE_IMAGE_MODEL")


def _one_figure_extraction(tmp_path):
    from PIL import Image
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir()
    Image.new("RGB", (200, 120), (200, 30, 30)).save(figures_dir / "fig-001-p1.png")
    blocks = [_para("Abb. 1 zeigt den Aufbau.", 1, 0),
              Block("figure", page=1, seq=1, figure_no="1", caption="Abb. 1: Aufbau",
                    image="fig-001-p1.png")]
    return Extraction(blocks=blocks, pages=1, source="docling", figures_dir=figures_dir)


def test_an_online_image_model_is_handed_the_picture_itself(tmp_path, monkeypatch, reads_images):
    from my_app.routes import chat_routes
    from my_app.utils import image_analysis
    asked = []

    def helper(messages, **kw):
        asked.append(kw)
        return {"content": " Ein rotes Rechteck. ", "thinking": None, "tool_calls": None}

    monkeypatch.setattr(chat_routes, "call_chat_helper", helper)
    monkeypatch.setattr(image_analysis, "analyze_image",
                        lambda *a, **k: pytest.fail("the local path was taken"))
    reads_images.add("mistral/mistral-large-4-0")
    ext = _one_figure_extraction(tmp_path)
    out = kp.describe_figures(ext, "de", model="mistral/mistral-large-4-0")
    assert out == {1: "Ein rotes Rechteck."}
    (kw,) = asked
    assert kw["model_override"] == "mistral/mistral-large-4-0"
    assert kw["may_leave_server"] is True
    assert kw["image_b64"] and not kw["image_b64"].startswith("data:")
    assert "temperature" not in kw


def test_an_online_image_model_not_measured_reading_images_is_refused(tmp_path, monkeypatch,
                                                                     reads_images):
    from my_app.routes import chat_routes
    monkeypatch.setattr(chat_routes, "call_chat_helper",
                        lambda *a, **k: pytest.fail("a call was made"))
    ext = _one_figure_extraction(tmp_path)
    with pytest.raises(ValueError, match="not recorded as reading images"):
        kp.describe_figures(ext, "de", model="mistral/zai-glm-5-3")


# ---------------------------------------------------------------------------
# Reasoning effort of the condensing model (issue #138)
# ---------------------------------------------------------------------------

@pytest.fixture()
def sent_payloads(monkeypatch):
    """The request body each provider would receive, with no request made:
    the reader's payload is caught where it would be sent."""
    from my_app.services import openai_style_stream as oss
    sent = []

    def fake_sse(provider, api_url, headers, payload, grammar, model, stage):
        sent.append((provider, payload))
        yield ("result", {"content": "ok", "thinking": None, "tool_calls": None,
                          "finish_reason": "stop"})

    for name in ("openrouter", "mammouth", "mistral", "ionos"):
        monkeypatch.setitem(oss._OPENAI_STYLE_PROVIDERS, name,
                            lambda: ("http://127.0.0.1:1/v1/chat/completions", "stand-in-key"))
    monkeypatch.setattr(oss, "_stream_sse", fake_sse)
    return sent


def test_the_reasoning_effort_defaults_to_high_and_names_openrouter_only():
    import config
    assert config._SETTINGS_DEFAULTS["KNOWLEDGE_REASONING_EFFORT"] == "high"
    assert kp.reasoning_payload("high") == {"openrouter": {"reasoning": {"effort": "high"}}}
    assert kp.reasoning_payload("") is None
    assert kp.reasoning_payload("  ") is None
    assert kp.reasoning_payload(None) is None


def test_the_condensing_call_carries_the_reasoning_field_when_set(sent_payloads, monkeypatch):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_REASONING_EFFORT", "high", raising=False)
    fn = kp.default_llm_fn(model="openrouter/z-ai/glm-5.3")
    assert fn("system", "user") == "ok"
    provider, payload = sent_payloads[-1]
    assert provider == "openrouter"
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["model"] == "z-ai/glm-5.3"

    kp.default_llm_fn(model="openrouter/z-ai/glm-5.3", reasoning_effort="medium")("s", "u")
    assert sent_payloads[-1][1]["reasoning"] == {"effort": "medium"}


def test_an_empty_reasoning_effort_sends_no_field(sent_payloads, monkeypatch):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_REASONING_EFFORT", "", raising=False)
    kp.default_llm_fn(model="openrouter/z-ai/glm-5.3")("system", "user")
    assert "reasoning" not in sent_payloads[-1][1]

    monkeypatch.setattr(config, "KNOWLEDGE_REASONING_EFFORT", "high", raising=False)
    kp.default_llm_fn(model="openrouter/z-ai/glm-5.3", reasoning_effort="")("system", "user")
    assert "reasoning" not in sent_payloads[-1][1]


@pytest.mark.parametrize("model", ["mammouth/glm-5.3", "mistral/mistral-large-latest",
                                   "ionos/some-model"])
def test_a_candidate_on_another_provider_is_sent_no_reasoning_field(sent_payloads, monkeypatch,
                                                                    model):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_REASONING_EFFORT", "high", raising=False)
    kp.default_llm_fn(model=model)("system", "user")
    provider, payload = sent_payloads[-1]
    assert provider == model.split("/")[0]
    assert "reasoning" not in payload


def test_a_pinned_mistral_large_4_is_sent_its_flat_reasoning_effort(sent_payloads, monkeypatch):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_REASONING_EFFORT", "high", raising=False)
    kp.default_llm_fn(model="mistral/mistral-large-4-0")("system", "user")
    provider, payload = sent_payloads[-1]
    assert provider == "mistral"
    assert payload["reasoning_effort"] == "high"
    assert "reasoning" not in payload
    # Another Mistral model, and Large 4 on OpenRouter, are not sent the flat field.
    kp.default_llm_fn(model="mistral/zai-glm-5-3")("system", "user")
    assert "reasoning_effort" not in sent_payloads[-1][1]
    kp.default_llm_fn(model="openrouter/mistralai/mistral-large-4-0")("system", "user")
    assert sent_payloads[-1][1]["reasoning"] == {"effort": "high"}
    assert "reasoning_effort" not in sent_payloads[-1][1]


def test_a_level_mistral_large_4_does_not_take_is_refused_before_any_call(sent_payloads):
    with pytest.raises(ValueError, match="low, medium, high"):
        kp.default_llm_fn(model="mistral/mistral-large-4-0", reasoning_effort="xhigh")
    assert sent_payloads == []
    # Without a pinned model nothing is keyed to Mistral at all.
    assert "mistral" not in kp.reasoning_payload("high")


def test_other_callers_of_the_chat_helper_send_no_reasoning_field(sent_payloads):
    from my_app.routes import chat_routes
    chat_routes.call_chat_helper([{"role": "user", "content": "hallo"}],
                                 model_override="openrouter/z-ai/glm-5.3")
    assert "reasoning" not in sent_payloads[-1][1]


# ---------------------------------------------------------------------------
# The document as the cached opening block (2026-11-14)
# ---------------------------------------------------------------------------

def _session(document):
    import hashlib
    return "kb-" + hashlib.sha256(document.encode("utf-8")).hexdigest()[:32]


def test_a_call_with_a_document_sends_it_first_with_the_cache_marker(sent_payloads,
                                                                      monkeypatch):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_REASONING_EFFORT", "high", raising=False)
    fn = kp.default_llm_fn(model="openrouter/z-ai/glm-5.3")
    assert fn.takes_document is True
    assert fn("SYS", "TASK", None, document="DOC\n\n", cache_ttl="1h") == "ok"
    provider, payload = sent_payloads[-1]
    assert provider == "openrouter"
    assert payload["messages"] == [{"role": "user", "content": [
        {"type": "text", "text": "DOC\n\n", "cache_control": {"type": "ephemeral", "ttl": "1h"}},
        {"type": "text", "text": "SYS\n\nTASK"},
    ]}]
    assert payload["session_id"] == _session("DOC\n\n")
    assert payload["reasoning"] == {"effort": "high"}


def test_a_reply_of_reasoning_only_is_no_answer_for_the_library(monkeypatch):
    """Issue #154: the chat helper hands a reasoning-only reply over as the
    content; the library takes it as no answer, and an answer beside its
    reasoning stays the answer."""
    from my_app.services import openai_style_stream as oss
    replies = [{"content": "", "thinking": "Ich überlege noch.", "tool_calls": None,
                "finish_reason": "stop"},
               {"content": "Die Zusammenfassung.", "thinking": "Ich überlege.",
                "tool_calls": None, "finish_reason": "stop"}]

    def fake_sse(provider, api_url, headers, payload, grammar, model, stage):
        yield ("result", replies.pop(0))

    monkeypatch.setitem(oss._OPENAI_STYLE_PROVIDERS, "openrouter",
                        lambda: ("http://127.0.0.1:1/v1/chat/completions", "stand-in-key"))
    monkeypatch.setattr(oss, "_stream_sse", fake_sse)
    fn = kp.default_llm_fn(model="openrouter/z-ai/glm-5.3")
    assert fn("SYS", "TASK", None, document="DOC") is None
    assert fn("SYS", "TASK", None, document="DOC") == "Die Zusammenfassung."
    assert fn.models_used == ["openrouter/z-ai/glm-5.3"]


def test_the_session_is_the_document_s_and_the_default_lifetime_names_no_ttl(sent_payloads):
    fn = kp.default_llm_fn(model="openrouter/z-ai/glm-5.3")
    fn("A", "1", document="DOC")
    fn("B", "2", document="DOC")
    fn("A", "1", document="OTHER")
    first, second, third = (p for _, p in sent_payloads[-3:])
    assert first["session_id"] == second["session_id"] == _session("DOC")
    assert third["session_id"] == _session("OTHER") != first["session_id"]
    assert first["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert first["messages"][0]["content"][0] == second["messages"][0]["content"][0]


def test_a_call_without_a_document_keeps_the_system_message_and_no_session(sent_payloads,
                                                                           monkeypatch):
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_REASONING_EFFORT", "high", raising=False)
    fn = kp.default_llm_fn(model="openrouter/z-ai/glm-5.3")
    fn("S", "U", document="DOC")
    fn("S", "U")
    payload = sent_payloads[-1][1]
    assert payload["messages"] == [{"role": "system", "content": "S"},
                                   {"role": "user", "content": "U"}]
    assert "session_id" not in payload
    assert payload["reasoning"] == {"effort": "high"}


def test_a_connection_without_prompt_caching_gets_the_document_as_text(sent_payloads):
    kp.default_llm_fn(model="mammouth/glm-5.3")("SYS", "TASK", document="DOC\n\n")
    provider, payload = sent_payloads[-1]
    assert provider == "mammouth"
    assert payload["messages"] == [{"role": "user", "content": "DOC\n\nSYS\n\nTASK"}]
    assert "session_id" not in payload


# ---------------------------------------------------------------------------
# Dry run (no model call)
# ---------------------------------------------------------------------------

def test_plan_document_counts_calls_without_a_model(tmp_path, monkeypatch):
    figs = tmp_path / "doc.figures"
    figs.mkdir()
    (figs / "fig-001.png").write_bytes(b"\x89PNG" + b"0" * 96)
    blocks = []
    for i in range(3):
        blocks.append(Block("heading", text=f"Teil {i}", level=2, page=i + 1, seq=len(blocks)))
        blocks.append(_para(_filler(f"t{i}", 3000), i + 1, len(blocks)))
    blocks.append(Block("figure", page=3, seq=len(blocks), figure_no="1", caption="Skizze",
                        image="fig-001.png"))
    ext = Extraction(blocks=blocks, pages=3, source="docling", figures_dir=figs)
    fm = {"id": "doc", "titel": "Plan", "sprache": "de"}
    plan = kp.plan_document(ext, fm)
    assert len(plan["units"]) == 1                     # the whole document is one call
    assert plan["totals"]["llm_calls"] == 1 + 1 + 1    # type, summary, Reduce
    assert plan["totals"]["revision_calls_max"] == 1
    assert plan["totals"]["image_calls"] == 1 and plan["totals"]["image_bytes"] == 100
    assert plan["image_calls"][0]["page"] == 3
    assert plan["totals"]["llm_input_chars_max"] > 9000
    # Only a document above the ceiling is cut, here into its three sections.
    monkeypatch.setattr(kp, "_DOC_UNIT_MAX_CHARS", 4000)
    cut = kp.plan_document(ext, fm)
    assert len(cut["units"]) == 3
    assert cut["totals"]["llm_calls"] == 1 + 3 + 1
    assert cut["totals"]["revision_calls_max"] == 3


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

def _lib_file(lib: Path, doc_id: str, lizenz: str, sidecar=None):
    md = lib / f"{doc_id}.md"
    md.write_text(f"---\nid: {doc_id}\ntitel: T\nlizenz: \"{lizenz}\"\nstatus: published\n---\n\n# T\n",
                  encoding="utf-8")
    if sidecar is not None:
        kc.write_sidecar(kc.sidecar_path(md), sidecar)
    return md


def _store(src: Path, work: Path, doc_id: str):
    (src / f"{doc_id}.pdf").write_bytes(b"%PDF")
    (work / f"{doc_id}.raw.md").write_text("raw", encoding="utf-8")
    (work / f"{doc_id}.blocks.json").write_text("{}", encoding="utf-8")
    (work / f"{doc_id}.figures").mkdir()
    (work / f"{doc_id}.figures" / "fig-001.png").write_bytes(b"png")


def _retention_env(tmp_path):
    lib, src, work = tmp_path / "lib", tmp_path / "src" / "operator" / "kunst", tmp_path / "work"
    for d in (lib, src, work):
        d.mkdir(parents=True)
    ok = {"passed": True, "review": {"passed": True, "reviewer": "r"}}
    _lib_file(lib, "cc-doc", "CC BY-SA 3.0 IGO", ok)
    _lib_file(lib, "nosidecar-doc", "Alle Rechte vorbehalten")
    _lib_file(lib, "failed-doc", "Alle Rechte vorbehalten", {"passed": False})
    _lib_file(lib, "noreview-doc", "Alle Rechte vorbehalten", {"passed": True})
    _lib_file(lib, "ok-doc", "Alle Rechte vorbehalten", ok)
    for d in ("cc-doc", "nosidecar-doc", "failed-doc", "noreview-doc", "ok-doc"):
        _store(src, work, d)
    (work / "orphan.raw.md").write_text("raw", encoding="utf-8")
    return lib, tmp_path / "src", work


def test_licence_class_from_the_licence_field():
    assert kr.licence_class("CC BY 4.0") == "cc"
    assert kr.licence_class("CC BY-SA 3.0 IGO") == "cc"
    assert kr.licence_class("Creative Commons Namensnennung") == "cc"
    assert kr.licence_class("Alle Rechte vorbehalten") == "restricted"
    assert kr.licence_class("") == "restricted"


def test_retention_plan_removes_only_checked_and_reviewed_non_cc(tmp_path):
    lib, src, work = _retention_env(tmp_path)
    plan = {i.doc_id: i for i in kr.plan_retention([lib], source_root=src, work_root=work,
                                                   originals_dir=None)}
    assert {d: i.action for d, i in plan.items()} == {
        "cc-doc": "keep", "nosidecar-doc": "keep", "failed-doc": "keep",
        "noreview-doc": "keep", "ok-doc": "remove", "orphan": "keep"}
    names = sorted(p.name for p in plan["ok-doc"].paths)
    assert names == ["ok-doc.blocks.json", "ok-doc.figures", "ok-doc.pdf", "ok-doc.raw.md"]
    # The plan only looks.
    assert (src / "operator" / "kunst" / "ok-doc.pdf").exists()


def test_retention_apply_removes_inside_the_roots_and_refuses_outside(tmp_path):
    lib, src, work = _retention_env(tmp_path)
    plan = kr.plan_retention([lib], source_root=src, work_root=work, originals_dir=None)
    outside = tmp_path / "elsewhere.pdf"
    outside.write_bytes(b"%PDF")
    plan.append(kr.RetentionItem("x", None, "", "restricted", True, True, "remove", "test",
                                 [outside]))
    log = kr.apply_plan(plan, [src, work])
    assert any(line.startswith("REFUSED") and "elsewhere.pdf" in line for line in log)
    assert outside.exists()
    assert not (src / "operator" / "kunst" / "ok-doc.pdf").exists()
    assert not (work / "ok-doc.figures").exists()
    assert not (work / "ok-doc.raw.md").exists()
    for kept in ("cc-doc", "nosidecar-doc", "failed-doc", "noreview-doc"):
        assert (src / "operator" / "kunst" / f"{kept}.pdf").exists()
        assert (work / f"{kept}.raw.md").exists()
    assert (lib / "ok-doc.md").exists()                    # the condensation stays


def _retention_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "knowledge_retention.py"
    spec = importlib.util.spec_from_file_location("knowledge_retention_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_retention_script_lists_by_default_and_removes_nothing(tmp_path, capsys):
    lib, src, work = _retention_env(tmp_path)
    script = _retention_script()
    args = ["--library-dir", str(lib), "--source-root", str(src), "--work-root", str(work),
            "--originals-dir", str(tmp_path / "none")]
    assert script.main(args) == 0
    out = capsys.readouterr().out
    assert "[REMOVE] ok-doc" in out and "list only" in out
    assert (src / "operator" / "kunst" / "ok-doc.pdf").exists()
    assert (work / "ok-doc.figures" / "fig-001.png").exists()
    assert script.main(args + ["--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert {i["doc_id"] for i in listed if i["action"] == "remove"} == {"ok-doc"}


def test_retention_script_records_a_review(tmp_path, capsys):
    lib, src, work = _retention_env(tmp_path)
    script = _retention_script()
    rc = script.main(["--library-dir", str(lib), "--record-review", "noreview-doc",
                      "--reviewer", "adversarial-agent"])
    assert rc == 0
    side = kc.read_sidecar(kc.sidecar_path(lib / "noreview-doc.md"))
    assert side["review"]["passed"] is True and side["review"]["reviewer"] == "adversarial-agent"
    plan = {i.doc_id: i.action for i in kr.plan_retention(
        [lib], source_root=src, work_root=work, originals_dir=None)}
    assert plan["noreview-doc"] == "remove"


def _klappklaus_p1() -> Extraction:
    """KlappKLAUS, p. 1, as Docling gave it: heading 1 is a bare number with
    a one-item list, heading 3 is the enumerated last item of a bullet list."""
    return Extraction(blocks=[
        Block("heading", text="Es gibt verschiedene Spielvarianten:", page=1, level=1),
        Block("heading", text="1.", page=1, level=1, ref="#/texts/3"),
        Block("list_item", text="Der Zufall macht's", page=1, list_id="g0"),
        _para("Klappen Sie wahllos jeweils einen Begriff um.", 1),
        Block("heading", text="2. Gut geplant ist halb gewonnen", page=1, level=1),
        Block("list_item", text="Stellen Sie Kartensets zusammen.", page=1, list_id="g1"),
        Block("list_item", text="Tipps zur Auswahl.", page=1, list_id="g1"),
        Block("list_item", text="Reflexion schadet nie", page=1, list_id="g1",
              enumerated=True, marker="3.", ref="#/texts/9"),
        _para("Blicken Sie auf vergangene Projekte zurück.", 1),
        Block("heading", text="4. Mehr kann mehr", page=1, level=1),
        _para("Überlegen Sie sich weitere Kategorien.", 1),
    ], pages=1)


def test_numbered_headings_cut_into_lists_become_headings_again():
    from my_app.services.knowledge_extract import normalise
    ext = _klappklaus_p1()
    normalise(ext)
    headings = [b.text for b in ext.blocks if b.kind == "heading"]
    assert headings == ["Es gibt verschiedene Spielvarianten:", "1. Der Zufall macht's",
                        "2. Gut geplant ist halb gewonnen", "3. Reflexion schadet nie",
                        "4. Mehr kann mehr"]
    items = [b for b in ext.blocks if b.kind == "list_item"]
    assert [b.text for b in items] == ["Stellen Sie Kartensets zusammen.", "Tipps zur Auswahl."]
    assert [h["rule"] for h in ext.integrity.headings_restored] == [
        "number-only heading", "list item between headings"]
    # The bullet list is two items again, and a two-item output list covers it.
    pairs = [kc.SectionPair(index=0, heading="KlappKLAUS", source_blocks=ext.blocks,
                            output="- Kartensets zusammenstellen\n- Tipps zur Auswahl\n",
                            page_from=1, page_to=1, missing=False, figure_idents=[])]
    assert not kc.check_lists(pairs).findings


def test_a_numbered_list_between_numbered_headings_stays_a_list():
    """Items 2 and 3 of a numbered list between headings 2 and 4 are a list:
    item 3 is not the only enumerated item of its list."""
    from my_app.services.knowledge_extract import normalise
    ext = Extraction(blocks=[
        Block("heading", text="2. Vorbereitung", page=1, level=1),
        Block("list_item", text="Papier", page=1, list_id="g", enumerated=True, marker="1."),
        Block("list_item", text="Schere", page=1, list_id="g", enumerated=True, marker="2."),
        Block("list_item", text="Kleber", page=1, list_id="g", enumerated=True, marker="3."),
        Block("heading", text="4. Durchführung", page=1, level=1),
        Block("heading", text="5.", page=1, level=1),
        Block("list_item", text="Erste Zeile", page=1, list_id="h"),
        Block("list_item", text="Zweite Zeile", page=1, list_id="h"),
    ], pages=1)
    normalise(ext)
    assert [b.kind for b in ext.blocks].count("list_item") == 5
    assert ext.integrity.headings_restored == []


# ---------------------------------------------------------------------------
# Numbered lists split by Docling (reunite_numbered_lists)
# ---------------------------------------------------------------------------

def _item(text, page, lid, marker):
    return Block("list_item", text=text, page=page, list_id=lid, enumerated=True,
                 marker=marker)


def _klappklaus_p2() -> Extraction:
    """KlappKLAUS, p. 2, as Docling gave it: item 1 alone, the pictures,
    items 2-4 as a second list, item 5 as a paragraph after a picture."""
    return Extraction(blocks=[
        Block("heading", text="So geht's", page=2, level=2),
        _item("Karten ausschneiden", 2, "g2", "1."),
        Block("figure", page=2, seq=1, image="a.png"),
        _para("Abb. 1: Die Karten", 2),
        _item("Karten falten", 2, "g3", "2."),
        _item("Karten mischen", 2, "g3", "3."),
        _item("Karten aufdecken", 2, "g3", "4."),
        Block("figure", page=2, seq=2, image="b.png"),
        Block("paragraph", text="5. Ausprobieren und erweitern!", page=2, ref="#/texts/40"),
    ], pages=2)


def test_a_numbered_list_split_around_pictures_is_one_list_again():
    from my_app.services.knowledge_extract import normalise
    ext = _klappklaus_p2()
    normalise(ext)
    items = [b for b in ext.blocks if b.kind == "list_item"]
    assert [b.text for b in items] == ["Karten ausschneiden", "Karten falten", "Karten mischen",
                                      "Karten aufdecken", "Ausprobieren und erweitern!"]
    assert {b.list_id for b in items} == {"g2"}
    assert [(r["fragment"], r["markers"], r["rule"]) for r in ext.integrity.lists_reunited] == [
        ("g3", "2-4", "fragment continues numbering"),
        ("#/texts/40", "5", "paragraph continues numbering")]
    # The check takes the five items as one list and compares them item by item.
    pairs = [_pair([b for b in ext.blocks if b.kind == "list_item"],
                   "### A\n\n1. Ausschneiden der Karten\n2. Falten\n3. Mischen\n"
                   "4. Aufdecken\n5. Ausprobieren")]
    assert not kc.check_lists(pairs).findings


def _esser_p22(free_caption: str = "Figure 12. Qualitative effects of scaling.") -> Extraction:
    """Esser et al. 2024, p. 22, as Docling gave it: the distribution charts
    without a caption, the caption of Figure 11 on the image grid below
    them, and the grid's own caption as a free caption block."""
    return Extraction(blocks=[
        Block("figure", page=22, seq=26, image="fig-026-p22.png", ref="#/pictures/25"),
        Block("figure_text", text="0.5", page=22, figure_ref="#/pictures/25"),
        Block("paragraph", text="t", page=22),
        Block("figure", page=22, seq=27, image="fig-027-p22.png", ref="#/pictures/26",
              caption="Figure 11. The mode (left) and logit-normal (right) distributions.",
              figure_no="11"),
        Block("figure_text", text="'A bowl of soup'", page=22, figure_ref="#/pictures/26"),
        Block("caption", text=free_caption, page=22, ref="#/texts/884"),
    ], pages=22)


def test_a_caption_given_to_the_next_picture_goes_back_to_its_own():
    from my_app.services.knowledge_extract import normalise
    ext = _esser_p22()
    normalise(ext)
    figs = [b for b in ext.blocks if b.kind == "figure"]
    assert [(b.image, b.figure_no, b.caption[:9]) for b in figs] == [
        ("fig-026-p22.png", "11", "Figure 11"), ("fig-027-p22.png", "12", "Figure 12")]
    assert not [b for b in ext.blocks if b.kind == "caption"]
    assert ext.integrity.captions_reassigned == [
        {"page": 22, "caption": "fig 11", "from": "#/pictures/26", "to": "#/pictures/25"}]


def test_a_caption_stays_where_the_numbering_does_not_continue():
    """The free caption below is a table's, or carries another number: the
    picture keeps its caption."""
    from my_app.services.knowledge_extract import normalise
    for free in ("Table 4. Results.", "Figure 14. Something else."):
        ext = _esser_p22(free)
        normalise(ext)
        figs = [b for b in ext.blocks if b.kind == "figure"]
        assert [b.figure_no for b in figs] == ["", "11"]
        assert ext.integrity.captions_reassigned == []


def test_lists_are_not_joined_across_a_heading_or_a_broken_numbering():
    from my_app.services.knowledge_extract import normalise
    ext = Extraction(blocks=[
        _item("eins", 1, "a", "1."), _item("zwei", 1, "a", "2."),
        Block("heading", text="Weiter", page=1, level=2),
        _item("drei", 1, "b", "3."), _item("vier", 1, "b", "4."),
        _para("Text", 1),
        _item("sechs", 1, "c", "6."), _item("sieben", 1, "c", "7."),     # 5 is missing
        _item("acht", 1, "d", "8."),
        Block("list_item", text="Unterpunkt ohne Nummer", page=1, list_id="d"),
        _item("neun", 1, "d", "9."),
        _item("zehn", 1, "e", "10."),
        _item("elf", 4, "f", "11."),                                     # three pages on
    ], pages=4)
    normalise(ext)
    assert ext.integrity.lists_reunited == []
    assert [b.list_id for b in ext.blocks if b.kind == "list_item"][-2:] == ["e", "f"]


def test_a_list_item_without_a_list_id_forms_its_run_and_a_list_id_crosses_pictures():
    blocks = [Block("list_item", text="x", page=1), Block("list_item", text="y", page=1),
              _para("Zwischentext", 1),
              _item("eins", 1, "L", "1."), Block("figure", page=1, seq=3),
              _item("zwei", 1, "L", "2.")]
    assert [[b.text for b in run] for run in kc._source_lists(blocks)] == [["x", "y"],
                                                                         ["eins", "zwei"]]


def test_lists_compare_the_items_not_only_their_count():
    src = [Block("list_item", text=t, page=2, list_id="L")
           for t in ("Die vier Felder ausschneiden", "Begriffe notieren", "Karten mischen")]
    ok = "### A\n\n- Die 4 Felder ausschneiden\n- Notieren der Begriffe\n- Mischen"
    assert not kc.check_lists([_pair(src, ok)]).findings
    wrong = "### A\n\n- Die 4 Felder ausschneiden\n- Bilder malen\n- Mischen"
    res = kc.check_lists([_pair(src, wrong)])
    assert res.findings and res.passed
    assert res.findings[0]["unanswered_items"] == [
        {"item": 2, "source": "Begriffe notieren", "output": "Bilder malen"}]
    # A condensation in another language than the source compares the count.
    assert not kc.check_lists([_pair(src, wrong)], compare_items=False).findings


# ---------------------------------------------------------------------------
# Figure descriptions the review cannot check
# ---------------------------------------------------------------------------

def test_text_language_by_function_words():
    assert kc.text_language("Ein Kind steht vor der Wand und malt mit einem Pinsel.") == "de"
    assert kc.text_language("A child stands in front of the wall and paints with a brush.") == "en"
    assert kc.text_language("Wand, Pinsel") == ""


def test_a_quote_counts_as_confirmed_only_where_the_source_carries_it():
    witness = "Abb. 3: Das Wort BLUT steht auf der Wand.\nTo all the kids who are read-\ning this!"
    assert kc.quote_confirmed("„BLUT“", witness)
    assert not kc.quote_confirmed("„SLUT“", witness)
    assert not kc.quote_confirmed("„GUT“", "Das ging gut.")           # lettering keeps its case
    assert kc.quote_confirmed("„das wort blut“", witness)
    assert kc.quote_confirmed("“To all the kids who are reading this!”", witness)  # skeleton
    assert kc.quote_confirmed("„Das Wort […] steht“", witness)                       # ellipsis
    assert kc.unconfirmed_quotes("Ein Schild „SLUT“ und ‚BLUT‘, it's here.", witness) == ["„SLUT“"]


def _figure_screen_extraction() -> Extraction:
    ext = Extraction(blocks=[
        _para("Die Kinder malen.", 1),
        Block("figure", page=1, seq=1, image="fig-001-p1.png", figure_no="1",
              caption="Abb. 1: Wand mit dem Wort BLUT"),
        Block("figure", page=1, seq=2, image="fig-002-p1.png", figure_no="2"),
    ], pages=1, source="docling")
    for b in ext.blocks:
        b.pdf_page = 1
    ext.text_layer = {1: "Die Kinder malen.\nAbb. 1: Wand mit dem Wort BLUT"}
    return ext


def test_screen_marks_unconfirmed_lettering_and_lists_a_description_in_another_language():
    ext = _figure_screen_extraction()
    desc = {1: "Auf der Wand steht „BLUT“ und darunter „GUT“ in roter Farbe.",
            2: "A child stands in front of the wall and paints with a brush."}
    screen = kp.screen_figure_text(ext, desc, "de", "de")
    assert screen.marked[1] == (desc[1] + " _(Schrift im Bild, vom Bildmodell gelesen, "
                                          "nicht bestätigt: „GUT“)_")
    assert screen.marked[2] == desc[2]
    assert screen.unconfirmed == [{"figure": "Abb. 1", "page": 1, "image": "fig-001-p1.png",
                                   "quotes": ["„GUT“"]}]
    assert [(w["figure"], w["description_language"], w["source_language"])
            for w in screen.wrong_language] == [("Abb. 2", "en", "de")]
    text = kc.check_figure_text(screen.unconfirmed)
    assert text.passed and text.value == 1.0
    assert text.summary.startswith("1 quoted texts in 1 figure descriptions not confirmed")
    figures = kc.check_figures([], screen.wrong_language)
    assert not figures.passed
    assert figures.summary == "1 figure descriptions not in the language of the source"


def test_review_reads_the_text_layer_of_its_pages_with_order_findings():
    from my_app.services.knowledge_extract import OrderFinding
    blocks = [Block("heading", text="Ablauf", level=2, page=3, seq=0),
              Block("paragraph", text="Erst A, dann B.", page=3, seq=1)]
    for b in blocks:
        b.pdf_page = 5
    ext = Extraction(blocks=blocks, pages=5, source="docling")
    ext.text_layer = {5: "Ablauf\nErst A, dann B.", 6: "Anderes"}
    assert ext.order_layer() == {}
    ext.integrity.order = [OrderFinding(page=5, text="dann B", words=2),
                           OrderFinding(page=6, text="x", words=1, repaired=True)]
    assert ext.order_layer() == {5: "Ablauf\nErst A, dann B."}
    units = kp.build_units(blocks)
    assert kp._unit_layer(units[0], ext.order_layer(), "de") == "[S. 3]\nAblauf\nErst A, dann B."


def test_the_verbatim_share_leaves_out_the_figure_lists_and_only_them():
    md = ("## WISSEN\n\n### Teil eins\n\nEigener Text.\n\n"
          "### Abbildungen (S. 2–3)\n\n*Bild 1 (S. 2):* Beschreibung eins.\n\n"
          "*Bild 2 (S. 3):* Beschreibung zwei.\n\n"
          "### Teil zwei\n\nWeiterer Text.\n\n#### Unterteil\n\nNoch Text.\n\n"
          "### Abbildungen (S. 9)\n\n*Bild 3 (S. 9):* Beschreibung drei.\n\n"
          "## GLOSSAR\n\nBegriff.\n")
    out = kp._without_figure_lists(md, "de")
    assert "Beschreibung" not in out and "### Abbildungen" not in out
    for kept in ("Eigener Text.", "### Teil zwei", "Weiterer Text.", "#### Unterteil",
                 "Noch Text.", "## GLOSSAR", "Begriff."):
        assert kept in out
    en = "### Figures (p. 4)\n\n*Figure 1 (p. 4):* A chart.\n\n### Next\n\nText.\n"
    assert kp._without_figure_lists(en, "en") == "### Next\n\nText.\n"
    # a heading that only begins with the label is not a figure list
    assert kp._without_figure_lists("### Abbildungen im Text\n\nX.\n", "de") \
        == "### Abbildungen im Text\n\nX.\n"


def test_the_verbatim_summary_names_every_part_left_out():
    res = kc.check_verbatim_share("ein Satz der Quelle mit genug Wörtern für einen Lauf",
                                  "eigene Worte ohne Zitat", min_words=7, max_share=0.2,
                                  excluded=[kp.VERBATIM_EXCLUDED_LITERATUR,
                                            kp.VERBATIM_EXCLUDED_FIGURES])
    assert ("not counted: LITERATUR (reference data, entries verbatim), figure descriptions"
            in res.summary)
