"""
Tests for what the knowledge library takes from a source beyond its running
text: printed page numbers (A1), the reading order within a page (A2), word
cards and grids as tables (A3), the bibliography (A4) and DOCX input (A5).

No Docling, no PDF reader, no model: the text layer is given as strings, the
Docling result as blocks.

Run: python3 -m pytest devserver/tests/test_knowledge_sources.py -q
"""

import importlib.util
import json
import sqlite3
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.services import knowledge_checks as kc
from my_app.services import knowledge_extract as kx
from my_app.services import knowledge_processing as kp
from my_app.services.knowledge_extract import Block, Extraction

DEVSERVER = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"_{name}_under_test",
                                                  DEVSERVER / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _para(text: str, page: int, ref: str = "") -> Block:
    return Block("paragraph", text=text, page=page, ref=ref)


# ---------------------------------------------------------------------------
# A1 printed page numbers
# ---------------------------------------------------------------------------

def test_folio_gives_the_printed_page(monkeypatch):
    monkeypatch.setattr(kx, "_pdf_page_labels", lambda pdf: None)
    layer = ["Kopfzeile des Aufsatzes\nErster Absatz mit Text.\n72",
             "73\nZweiter Absatz mit Text.\nLiteratur"]
    kind, mapping, detail = kx.detect_page_numbering(layer, Path("x.pdf"))
    assert kind == kx.PAGES_PRINTED_FOLIO
    assert mapping == {1: 72, 2: 73}
    assert detail == {"offset": 71, "pages_with_folio": 2}


def test_page_labels_come_first_and_roman_pages_have_no_number(monkeypatch):
    monkeypatch.setattr(kx, "_pdf_page_labels", lambda pdf: ["i", "ii", "1", "2", "3"])
    layer = ["a", "b", "c 9", "d", "e"]
    kind, mapping, _ = kx.detect_page_numbering(layer, Path("x.pdf"))
    assert kind == kx.PAGES_PRINTED_LABELS
    assert mapping == {1: 0, 2: 0, 3: 1, 4: 2, 5: 3}


def test_without_labels_or_folio_the_pdf_page_counts(monkeypatch):
    monkeypatch.setattr(kx, "_pdf_page_labels", lambda pdf: None)
    layer = ["Text ohne Zahl.", "Noch mehr Text.", "Und noch einer."]
    kind, mapping, detail = kx.detect_page_numbering(layer, None)
    assert kind == kx.PAGES_PDF and mapping == {1: 1, 2: 2, 3: 3} and detail == {}


def test_number_pages_relabels_blocks_and_records_unnumbered_pages(monkeypatch):
    monkeypatch.setattr(kx, "_pdf_page_labels", lambda pdf: ["Cover", "1", "2"])
    ext = Extraction(blocks=[_para("Titelei", 1), _para("Eins", 2), _para("Zwei", 3)],
                     pages=3, source="docling")
    assert kx.number_pages(ext, ["Cover", "eins", "zwei"], Path("x.pdf")) == kx.PAGES_PRINTED_LABELS
    assert [b.page for b in ext.blocks] == [0, 1, 2]
    assert (ext.page_first, ext.page_last) == (1, 2)
    assert ext.page_detail["unnumbered_pdf_pages"] == [1]
    assert kp.SEITENZAHLEN[ext.page_kind] == "gedruckt"


def test_page_refs_are_checked_against_the_printed_range():
    pair = kc.SectionPair(index=0, heading="A", source_blocks=[], output="### A (S. 72–73)\n\nText (S. 73).",
                          page_from=72, page_to=73)
    ok = kc.check_page_refs([pair], 72, 73, kx.PAGES_PRINTED_FOLIO)
    assert ok.passed and "printed-folio pages 72–73" in ok.summary
    early = kc.SectionPair(index=0, heading="A", source_blocks=[], output="### A (S. 72–73)\n\nText (S. 2).",
                           page_from=72, page_to=73)
    assert not kc.check_page_refs([early], 72, 73, kx.PAGES_PRINTED_FOLIO).passed


# ---------------------------------------------------------------------------
# A2 reading order
# ---------------------------------------------------------------------------

_A = "Anfangs zeichnete Kemal einen grossen Vulkan"
_B = "mit rotem Mond ohne dunklen Himmel"
_C = "danach entwarf die Maschine eine eigene Variante davon"


def test_text_placed_out_of_order_is_repaired_from_the_text_layer():
    # Docling: A + C in one paragraph, B in the next; the page reads A B C.
    ext = Extraction(blocks=[_para(f"{_A} {_C}", 9, "#/texts/73"), _para(_B, 9, "#/texts/74"),
                             Block("figure", page=9, ref="#/pictures/5", image="fig-005-p9.png")],
                     pages=9, source="docling")
    layer = [""] * 8 + [f"{_A} {_B} {_C}"]
    findings = kx.check_reading_order(ext, layer)
    assert len(findings) == 1 and findings[0].repaired
    assert findings[0].page == 9 and findings[0].refs == ["#/texts/73", "#/texts/74"]
    assert [b.kind for b in ext.blocks] == ["paragraph", "figure"]
    assert ext.blocks[0].text == f"{_A} {_B} {_C}"
    assert ext.blocks[0].ref == "#/reordered/0"
    rep = kc.check_reading_order(ext.integrity, "docling")
    assert rep.passed


def test_an_order_finding_on_a_list_stays_unrepaired_and_fails_the_check():
    ext = Extraction(blocks=[_para(f"{_A} {_C}", 2, "#/texts/18"),
                             Block("list_item", text=_B, page=2, ref="#/texts/30")],
                     pages=2, source="docling")
    findings = kx.check_reading_order(ext, ["", f"{_A} {_B} {_C}"])
    assert len(findings) == 1 and not findings[0].repaired
    assert "list_item" in findings[0].note
    assert [b.ref for b in ext.blocks] == ["#/texts/18", "#/texts/30"]       # untouched
    res = kc.check_reading_order(ext.integrity, "docling")
    assert not res.passed and res.findings[0]["page"] == 2
    assert res.findings[0]["fails"] and "cut out" in res.findings[0]["breaks"][0]


def test_list_items_in_another_order_with_every_sentence_whole_do_not_fail_the_check():
    first = "Erstens zeichnete Kemal einen grossen Vulkan mit rotem Mond."
    second = "Zweitens entwarf die Maschine eine eigene Variante davon."
    ext = Extraction(blocks=[Block("list_item", text=second, page=1, ref="#/texts/1"),
                             Block("list_item", text=first, page=1, ref="#/texts/2")],
                     pages=1, source="docling")
    findings = kx.check_reading_order(ext, [f"{first} {second}"])
    assert len(findings) == 1 and not findings[0].repaired and not findings[0].breaks
    res = kc.check_reading_order(ext.integrity, "docling")
    assert res.passed and "none breaks a sentence" in res.summary
    assert res.findings and not res.findings[0]["fails"]


def test_a_sentence_cut_by_a_heading_fails_the_check():
    # UNESCO Recommendation p. 30: "… including" / "POLICY AREA 5" / item 84 /
    # "the continuation of item 81".
    a = "Member States should support research and innovation, including"
    rest = "studies on the effects of the systems on learners and teachers."
    other = "Member States should assess the direct and indirect impact on the environment."
    ext = Extraction(blocks=[_para(a, 1, "#/texts/1"),
                             Block("heading", text="Policy area five environment", page=1,
                                   ref="#/texts/2", level=2),
                             Block("list_item", text=other, page=1, ref="#/texts/3"),
                             Block("list_item", text=rest, page=1, ref="#/texts/4")],
                     pages=1, source="docling")
    kx.check_reading_order(ext, [f"{a} {rest} Policy area five environment {other}"])
    left = ext.integrity.order_unrepaired
    assert left and any(o.breaks_text for o in left)
    assert not kc.check_reading_order(ext.integrity, "docling").passed


def test_an_order_finding_in_the_bibliography_does_not_fail_the_check():
    ext = Extraction(blocks=[Block("heading", text="References", page=2, ref="#/texts/9", level=1),
                             _para(f"{_A} {_C}", 2, "#/texts/18"),
                             Block("list_item", text=_B, page=2, ref="#/texts/30")],
                     pages=2, source="docling")
    kx.check_reading_order(ext, ["", f"References {_A} {_B} {_C}"])
    left = ext.integrity.order_unrepaired
    assert left and all(o.section == kx.ORDER_SECTION_BIBLIOGRAPHY for o in left)
    res = kc.check_reading_order(ext.integrity, "docling")
    assert res.passed and res.findings[0]["section"] == "bibliography"


def test_a_phrase_that_occurs_twice_on_the_page_is_no_order_finding():
    # Gabrys 2019, p. 2–3: a running head repeating a phrase of the body, and
    # a phrase the author uses twice on one page. Docling's order is right.
    head = "Sensing a Planet in Crisis"
    p1 = (f"Citizens build networks of devices and these sensors are {head.lower()} "
          "that formations of citizenship and political engagement follow")
    p2 = ("The rewiring of environments is multi-layered and formations of citizenship "
          "and political engagement are operationalized through these devices")
    ext = Extraction(blocks=[Block("furniture", text=head, page=2, ref="#/texts/9"),
                             _para(p1, 2, "#/texts/123"), _para(p2, 2, "#/texts/131")],
                     pages=2, source="docling")
    findings = kx.check_reading_order(ext, ["", f"{head}\n{p1}\n{p2}"])
    assert findings == []
    assert [b.ref for b in ext.blocks] == ["#/texts/9", "#/texts/123", "#/texts/131"]


def test_a_page_the_flow_reading_supports_is_no_order_finding():
    # Park 2024, p. 11: a bibliography in three columns. The layout mode
    # reads it line by line across the columns; pdftotext's flow order reads
    # each column down, as Docling does.
    cols = [
        ["Gebru, T. (2020). Race and gender.", "In M. D. Dubber, F. Pasquale,",
         "and S. Das (Eds.), The Oxford handbook", "of ethics of AI (pp. 252-269)."],
        ["Heikkila, M. (2022, December 12).", "The viral AI avatar app Lensa",
         "undressed me without my consent.", "MIT Technology Review online."],
        ["Manovich, L. (2017). Automating", "aesthetics: Artificial intelligence",
         "and image culture. Flash Art", "International magazine issue."],
    ]
    blocks = [Block("list_item", text=" ".join(c), page=11, ref=f"#/texts/{136 + k}")
              for k, c in enumerate(cols)]
    layout = "\n".join("    ".join(f"{c[r]:<40}" for c in cols).rstrip() for r in range(4))
    flow = "\n".join(" ".join(c) for c in cols)

    ext = Extraction(blocks=list(blocks), pages=11, source="docling")
    assert kx.check_reading_order(ext, [""] * 10 + [layout]) != []

    ext = Extraction(blocks=list(blocks), pages=11, source="docling")
    assert kx.check_reading_order(ext, [""] * 10 + [layout], [""] * 10 + [flow]) == []


def test_a_passage_no_reading_supports_stays_a_finding():
    ext = Extraction(blocks=[_para(f"{_A} {_C}", 9, "#/texts/73"), _para(_B, 9, "#/texts/74")],
                     pages=9, source="docling")
    layer = [""] * 8 + [f"{_A} {_B} {_C}"]
    findings = kx.check_reading_order(ext, layer, list(layer))
    assert len(findings) == 1 and findings[0].repaired
    assert ext.blocks[0].text == f"{_A} {_B} {_C}"


def test_a_sentence_start_cut_out_of_the_middle_of_the_block_before_fails_the_check():
    # Jörissen and Klepacki 2026, p. 5: the layer has "three interrelated
    # core elements …" inside the sentence "derives a model in which …";
    # Docling ends that sentence and sets the cut-out words after it.
    a = ("Klepacki derives a model in which several processes of adaptation "
         "can be distinguished in practice.")
    cut = "three interrelated core elements of resilience stand out and shape it."
    whole = ("Klepacki derives a model in which three interrelated core elements of "
             "resilience stand out and shape it several processes of adaptation "
             "can be distinguished in practice.")
    ext = Extraction(blocks=[_para(a, 5, "#/texts/21"),
                             Block("list_item", text=cut, page=5, ref="#/texts/22")],
                     pages=5, source="docling")
    kx.check_reading_order(ext, [""] * 4 + [whole])
    breaks = [b for o in ext.integrity.order_unrepaired for b in o.breaks]
    assert any(b.startswith("sentence start cut out of the block before") for b in breaks)
    assert not kc.check_reading_order(ext.integrity, "docling").passed


def test_a_phrase_in_two_blocks_does_not_hide_where_a_cut_sentence_goes_on():
    # UNESCO Recommendation on the Ethics of AI, p. 18: "in compliance with"
    # goes on in a block after a heading and a list item, and "human rights
    # and fundamental freedoms" stands in that list item too.
    a = "Member States should act in proportionality and in compliance with"
    rest = "human rights and fundamental freedoms. In all cases the measures stay lawful."
    item = "Respect for human rights and fundamental freedoms and human dignity matters."
    ext = Extraction(blocks=[_para(a, 18, "#/texts/98"),
                             Block("heading", text="Values of the recommendation", page=18,
                                   ref="#/texts/99", level=2),
                             Block("list_item", text=item, page=18, ref="#/texts/100"),
                             _para(rest, 18, "#/texts/103")],
                     pages=18, source="docling")
    kx.check_reading_order(ext, [""] * 17 + [f"{a} {rest} Values of the recommendation {item}"])
    breaks = [b for o in ext.integrity.order_unrepaired for b in o.breaks]
    assert any(b.startswith("sentence cut") for b in breaks)
    assert not kc.check_reading_order(ext.integrity, "docling").passed


def test_blocks_of_a_later_page_move_back_behind_their_page():
    ext = Extraction(blocks=[_para("eins", 1), _para("drei", 3), _para("zwei", 2)],
                     pages=3, source="docling")
    moved = kx.restore_page_order(ext)
    assert [b.text for b in ext.blocks] == ["eins", "zwei", "drei"]
    assert moved == [{"page": 2, "ref": "", "kind": "paragraph", "after_page": 3}]


# ---------------------------------------------------------------------------
# A3 word cards and grids
# ---------------------------------------------------------------------------

def test_word_cards_lost_by_docling_come_back_as_a_table_and_every_card_is_checked():
    cards = ("Heran-gehensweise    Technik     Material\n"
             "Klebeband           Schere      Pappe\n"
             "Zeitung             Faden       Kleister")
    intro = ("Die Karten werden ausgeschnitten, gemischt und verdeckt auf den Tisch gelegt; "
             "jede Gruppe zieht aus jeder Spalte eine Karte und beginnt mit dem, was sie zeigt.")
    ext = Extraction(blocks=[_para(intro, 1)], pages=1, source="docling")
    kx.cross_check(ext, [intro + "\n" + cards])
    assert ext.integrity.replaced_pages == []
    tables = [b for b in ext.blocks if b.kind == "table"]
    assert len(tables) == 1 and tables[0].repaired
    assert "Kleister" in tables[0].markdown
    full = kc.SectionPair(index=0, heading="Karten", source_blocks=tables,
                          output="### Karten (S. 1)\n\n- Heran-gehensweise, Technik, Material\n"
                                 "- Klebeband, Schere, Pappe\n- Zeitung, Faden, Kleister")
    assert not kc.check_lists([full]).findings
    short = kc.SectionPair(index=0, heading="Karten", source_blocks=tables,
                           output="### Karten (S. 1)\n\n- Klebeband, Schere, Pappe")
    lost = kc.check_lists([short])
    assert lost.findings and lost.passed            # listed, not gated (#140)
    assert "Kleister" in json.dumps(lost.findings, ensure_ascii=False)


# ---------------------------------------------------------------------------
# A4 bibliography
# ---------------------------------------------------------------------------

def _with_bibliography() -> Extraction:
    return Extraction(blocks=[
        Block("heading", text="Einleitung", level=1, page=72),
        _para("Ein Absatz über den westlichen Blick.", 72),
        Block("heading", text="Literatur", level=1, page=73),
        Block("list_item", text="Bhabha, H. (1994): The Location of Culture. London.", page=73),
        Block("list_item", text="Hall, S. (1997): Representation. London.", page=73),
    ], pages=2, source="docling")


def test_the_bibliography_is_kept_verbatim_and_left_out_of_the_condensation():
    ext = _with_bibliography()
    secs = kp.bibliography(ext)
    assert len(secs) == 1 and secs[0].heading == "Literatur"
    assert secs[0].entries == ["Bhabha, H. (1994): The Location of Culture. London.",
                               "Hall, S. (1997): Representation. London."]
    assert (secs[0].page_from, secs[0].page_to) == (73, 73)
    kept, skipped = kp.clean_blocks(ext)
    assert skipped == ["Literatur (p. 73)"]
    assert all("Bhabha" not in b.text for b in kept)
    md = kp.assemble_markdown({"doc_id": "x", "titel": "X"}, "Profil.", [], literatur=secs, lang="de")
    lit = md.split("## LITERATUR", 1)[1]
    assert "<!-- quelle: Literatur (S. 73) -->" in lit
    assert "- Bhabha, H. (1994): The Location of Culture. London." in lit


def test_verbatim_share_does_not_count_the_bibliography_and_says_so():
    entry = "Bhabha, H. (1994): The Location of Culture. London: Routledge Press, Second Edition."
    res = kc.check_verbatim_share(entry + " eigener Text dazu", "eigene Worte ohne Zitat",
                                  min_words=7, max_share=0.1,
                                  excluded=["LITERATUR (reference data, entries verbatim)"])
    assert res.passed
    assert "not counted: LITERATUR (reference data, entries verbatim)" in res.summary


def test_the_index_holds_the_bibliography_as_its_own_chunk(tmp_path):
    bki = _load_script("build_knowledge_index")
    md = tmp_path / "x.md"
    md.write_text(
        "---\ndoc_id: x\ntitel: X\ntier: o\nsprache: de\nlizenz: CC BY 4.0\nseitenzahlen: gedruckt\n---\n\n"
        "## PROFIL\n\nProfil.\n\n## WISSEN\n\n### Einleitung (S. 72)\n\nText.\n\n"
        "## LITERATUR\n\n<!-- quelle: Literatur (S. 73) -->\n\n"
        "- Hall, S. (1997): Representation. London.\n", encoding="utf-8")
    doc = bki.load_document(md)
    assert doc["seitenzahlen"] == "gedruckt"
    lit = [c for c in doc["chunks"] if c["section_path"] == "LITERATUR"]
    assert len(lit) == 1 and "Hall, S. (1997)" in lit[0]["body_md"]
    db = tmp_path / "idx.sqlite"
    bki.build(db, [doc])
    con = sqlite3.connect(db)
    assert con.execute("SELECT seitenzahlen FROM docs WHERE doc_id='x'").fetchone() == ("gedruckt",)
    con.close()


# ---------------------------------------------------------------------------
# A5 DOCX
# ---------------------------------------------------------------------------

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx(path: Path, paragraphs) -> Path:
    body = "".join("<w:p>" + "".join(f"<w:r><w:t xml:space=\"preserve\">{r}</w:t></w:r>" for r in runs)
                   + "</w:p>" for runs in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml",
                   f"<?xml version=\"1.0\"?><w:document xmlns:w=\"{_W}\"><w:body>{body}</w:body></w:document>")
    return path


def test_docx_text_joins_the_runs_of_a_paragraph(tmp_path):
    p = _docx(tmp_path / "a.docx", [["1. Approaching ", "generative AI"], ["Body text, ", "et al", ". 2023."]])
    assert kx.docx_text(p) == "1. Approaching generative AI\nBody text, et al. 2023."


def test_a_docx_is_checked_without_pages_and_referenced_by_section(tmp_path):
    src = _docx(tmp_path / "a.docx", [["Approaching generative AI"],
                                      ["Generative models shape what is seen in culture and arts education."],
                                      ["A paragraph Docling lost entirely somewhere in the middle of it."]])
    blocks = tmp_path / "a.blocks.json"
    blocks.write_text(json.dumps({"source": "docling", "pages": 1, "blocks": [
        {"kind": "heading", "level": 1, "text": "Approaching generative AI", "page": 1},
        {"kind": "paragraph", "text": "Generative models shape what is seen in culture and arts education.",
         "page": 1}]}), encoding="utf-8")
    ext = kx.extract_with_integrity(blocks, src)
    assert ext.pages == 0 and ext.page_kind == kx.PAGES_NONE and ext.page_last == 0
    assert ext.integrity.checked and len(ext.integrity.gaps) == 1
    assert ext.integrity.gaps[0].page == 0
    assert "lost entirely" in ext.blocks[-1].text
    res = kc.check_page_refs([kc.SectionPair(index=0, heading="A", source_blocks=[],
                                             output="### Approaching generative AI\n\nText.")],
                             0, 0, kx.PAGES_NONE)
    assert res.passed


def test_docling_word_pieces_join_into_one_paragraph_and_bold_lines_become_headings():
    ki = _load_script("knowledge_ingest")
    assert ki._join_inline(["Bahroun, Z", "et al", ". 2023. Transforming", "(", "education", ")"]) \
        == "Bahroun, Z et al. 2023. Transforming (education)"
    bold = SimpleNamespace(formatting=SimpleNamespace(bold=True))
    plain = SimpleNamespace(formatting=SimpleNamespace(bold=False))
    assert ki._manual_heading_level(bold, "2.1 Radical hope: AI in the spirit of decolonial empowerment") == 2
    assert ki._manual_heading_level(bold, "1. Approaching generative AI") == 1
    assert ki._manual_heading_level(bold, "Abstract") == 1
    assert ki._manual_heading_level(bold, "A bold sentence that ends like one.") == 0
    assert ki._manual_heading_level(plain, "2.2 Radical critique") == 0
    assert ki._manual_heading_level(SimpleNamespace(), "2.2 Radical critique") == 0


def test_author_names_and_affiliations_do_not_become_headings():
    # "Generative AI and the Politics of Perception" (DOCX): bold author
    # names, the first affiliation in Word's Heading 2 style.
    ki = _load_script("knowledge_ingest")
    name1 = {"kind": "heading", "level": 1, "text": "Benjamin Jörissen"}
    aff1 = {"kind": "heading", "level": 2,
            "text": "Friedrich-Alexander-Universität Erlangen-Nürnberg, Germany.\n"
                    "benjamin.joerissen@fau.de"}
    name2 = {"kind": "heading", "level": 1, "text": "Vanessa Baumann"}
    aff2 = {"kind": "paragraph", "text": "Friedrich-Alexander-Universität Erlangen-Nürnberg, "
                                         "Germany. coauthor@example.org"}
    abstract = {"kind": "heading", "level": 1, "text": "Abstract"}
    body = {"kind": "paragraph", "text": "Write to the editors at office@example.org."}
    contact = {"kind": "heading", "level": 1, "text": "Contact"}
    blocks = [name1, aff1, name2, aff2, abstract, {"kind": "paragraph", "text": "Text."},
              contact, body]
    ki._author_lines_out_of_headings(blocks, {id(name1), id(name2), id(abstract)})
    assert [b["kind"] for b in blocks[:5]] == ["paragraph"] * 4 + ["heading"]
    assert "level" not in name1 and "level" not in aff1
    assert contact["kind"] == "heading"     # a Word heading, not the bold rule


# ---------------------------------------------------------------------------
# A document that is part of its file (a chapter of a volume)
# ---------------------------------------------------------------------------

def test_page_range_parses_and_refuses_what_is_no_range():
    assert kx.parse_page_range("111-137") == (111, 137)
    assert kx.parse_page_range("111–137") == (111, 137)
    assert kx.parse_page_range(" 9 ") == (9, 9)
    assert kx.parse_page_range("") is None and kx.parse_page_range(None) is None
    for bad in ("0-3", "12-9", "S. 9", "9-10-11"):
        try:
            kx.parse_page_range(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert kx.format_page_range((9, 10)) == "9-10"


def test_a_chapter_keeps_its_pages_and_takes_the_folio_of_its_own_pages(tmp_path, monkeypatch):
    """Four pages of an issue; the chapter is PDF pages 3-4, printed 72-73,
    while the other contribution carries the folios of another journal: the
    blocks outside the range are gone, the text layer outside it is not read,
    and the printed pages are those of the chapter."""
    monkeypatch.setattr(kx, "_pdf_page_labels", lambda pdf: None)
    layer = ["Anderer Beitrag eins.\n12", "Anderer Beitrag zwei.\n13",
             "Erster Absatz des Kapitels mit Text.\n72",
             "Zweiter Absatz des Kapitels mit Text.\n73"]
    monkeypatch.setattr(kx, "pdftotext_pages", lambda pdf: list(layer))
    monkeypatch.setattr(kx, "pdftotext_flow_pages", lambda pdf: list(layer))
    src = tmp_path / "heft.pdf"
    src.write_bytes(b"%PDF")
    blocks = tmp_path / "heft.blocks.json"
    blocks.write_text(json.dumps({"source": "docling", "pages": 4, "blocks": [
        {"kind": "paragraph", "text": "Anderer Beitrag eins.", "page": 1},
        {"kind": "paragraph", "text": "Anderer Beitrag zwei.", "page": 2},
        {"kind": "paragraph", "text": "Erster Absatz des Kapitels mit Text.", "page": 3},
        {"kind": "paragraph", "text": "Zweiter Absatz des Kapitels mit Text.", "page": 4}]}),
        encoding="utf-8")
    ext = kx.extract_with_integrity(blocks, src, (3, 4))
    assert [b.text for b in ext.blocks] == ["Erster Absatz des Kapitels mit Text.",
                                            "Zweiter Absatz des Kapitels mit Text."]
    assert [b.page for b in ext.blocks] == [72, 73]
    assert (ext.pages, ext.file_pages, ext.pdf_range) == (2, 4, (3, 4))
    assert (ext.page_kind, ext.page_first, ext.page_last) == (kx.PAGES_PRINTED_FOLIO, 72, 73)
    assert ext.page_numbering()["pdf_seiten"] == "3-4"
    assert not ext.integrity.gaps                       # pages 1-2 of the layer unread
    try:
        kx.extract_with_integrity(blocks, src, (3, 5))
    except ValueError as e:
        assert "outside the file" in str(e)
    else:
        raise AssertionError("a range past the last page is refused")


def test_a_folio_with_a_rule_counts():
    assert 4 in kx._folio_offsets("|9\nStrukturale Bildungstheorie\nText.", 5)
    assert kx._folio_offsets("24| Strukturale Bildungstheorie\nText.", 20) == {4}
