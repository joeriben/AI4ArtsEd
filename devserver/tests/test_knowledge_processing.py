"""
Tests for the knowledge condensation service (my_app.services.knowledge_processing).

Exercise the DETERMINISTIC parts (cleaning, units, prompts, assembly,
validation) against a synthetic extraction (knowledge_extract.from_markdown,
no Docling, no network), with a stub LLM injected for the type, Map and
Reduce calls. The checks themselves are tested in test_knowledge_neubau.py.

Run: python3 -m pytest devserver/tests/test_knowledge_processing.py -q
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import knowledge_processing as kp
from my_app.services.knowledge_extract import from_markdown


# A raw (Docling-style) Markdown: a ToC, an acronym table, an image marker, a
# running head that Docling left as separate paragraphs, and a list.
_RAW = """# Guidance Note on Something

<!-- image -->

## Table of Contents

Introduction .......... 3
Chapter 1 .......... 5
Conclusion .......... 9

## Abbreviations

AI   Artificial Intelligence
ICH   Intangible Cultural Heritage
GDPR   General Data Protection Regulation

## Foreword

This guidance sets out a human-centred approach. It builds on the 2021
Recommendation on the Ethics of AI. The minimum age for independent use is 13.

The Guidance Note running header

## Chapter 1: Access thresholds

Governments should enact the following measures:
- set a minimum age of 13 for account creation
- require parental consent below age 16
- audit systems every 12 months

The Guidance Note running header

Concrete example: a school in Kenya piloted this in 2022 with 650 students.

The Guidance Note running header

## Conclusion

The Guidance Note running header

The way forward requires coordinated action across ministries.
"""

_TYPE_ANSWER = json.dumps({"type": "framework_report", "language": "en",
                           "reason": "a guidance note"})


def _is_type_call(system: str) -> bool:
    return system.startswith("You classify")


_SUMMARY = ("## Zugangsschwellen\n\n- Mindestalter 13\n- elterliche Zustimmung unter 16\n"
            "- Audit alle 12 Monate\n\nBeispiel: Kenia 2022, 650 Lernende.\n\n"
            "## TERMS\n\n- **Intangible Cultural Heritage**: immaterielles Kulturerbe")


def _stub(system, user, max_tokens):
    if _is_type_call(system):
        return _TYPE_ANSWER
    if "PROFILE" in system:
        return ("Menschzentrierter Ansatz, baut auf der Empfehlung zur KI-Ethik "
                "2021 auf. Anwendbar in medialer Kunstpaedagogik.")
    return _SUMMARY


def _cut(monkeypatch, ceiling=8000):
    """Lower the unit ceiling so that _standard_raw (about 29,000 characters)
    is summarized in parts; a document of library size is one unit."""
    monkeypatch.setattr(kp, "_DOC_UNIT_MAX_CHARS", ceiling)


def _fm(**over):
    fm = {"id": "test-guidance-2023", "titel": "", "autor": "UNESCO", "jahr": 2023,
          "sprache": "en", "tier": "F", "sparten": ["medial"], "themen": ["ai_ethics"],
          "lizenz": "CC BY-SA 3.0 IGO", "url": "https://x", "status": "draft"}
    fm.update(over)
    return fm


def _standard_raw() -> str:
    """A heading-rich, long document: eight chapters of distinct lines; one
    unit, or several parts under a lowered ceiling (_cut)."""
    parts = ["# A Long Framework Document", ""]
    for i in range(1, 9):
        parts.append(f"## Chapter {i}: Area {i}")
        parts.append("")
        for j in range(60):
            parts.append(f"Measure {i}.{j}: governments should enact this specific action.")
            parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Cleaning (deterministic)
# ---------------------------------------------------------------------------

def test_clean_blocks_drops_scaffolding_and_names_what_it_skipped():
    blocks, skipped = kp.clean_blocks(from_markdown(_RAW), "Guidance Note on Something")
    joined = "\n".join(b.text for b in blocks)
    assert "........" not in joined
    assert "Artificial Intelligence" not in joined     # acronym table dropped
    assert "<!-- image -->" not in joined
    assert "running header" not in joined              # repeated paragraph dropped
    headings = [b.text for b in blocks if b.kind == "heading"]
    assert "Guidance Note on Something" not in headings  # the title is the file's `# titel`
    assert "Foreword" in headings and "Conclusion" in headings
    assert skipped == ["Table of Contents", "Abbreviations"]
    # The list survives as three items of one list.
    items = [b for b in blocks if b.kind == "list_item"]
    assert len(items) == 3 and len({b.list_id for b in items}) == 1


def test_repeated_line_detection_flags_running_header():
    repeated = kp._find_repeated_lines(_RAW)
    assert "The Guidance Note running header" in repeated


def test_acronym_and_toc_block_detectors():
    assert kp._is_acronym_block("AI   Artificial Intelligence\nICH   Intangible Cultural Heritage\nGDPR   General Data Protection Regulation")
    assert kp._is_toc_block("Introduction .......... 3\nChapter 1 .......... 5\nConclusion .......... 9")
    assert not kp._is_acronym_block("This is an ordinary paragraph of prose about AI in schools.")


# ---------------------------------------------------------------------------
# Assembly + full pipeline (stub LLM)
# ---------------------------------------------------------------------------

def test_process_document_shape():
    res = kp.process_document(from_markdown(_RAW), _fm(), llm=_stub)
    md = res.markdown

    # The compact form: PROFIL/WISSEN/GLOSSAR, never the old full-text markers.
    assert "## PROFIL" in md
    assert "## WISSEN" in md
    assert "## GLOSSAR" in md
    assert "## DOCUMENT" not in md
    assert "## CARD" not in md
    # Title filled from the first heading; the type call's answer is recorded.
    assert "titel: Guidance Note on Something" in md
    assert res.doc_type == "framework_report"
    assert "doc_type: framework_report" in md
    # The summary is in WISSEN, with its review anchor; the whole document is one unit.
    assert res.n_units == 1
    assert "### Zugangsschwellen" in md and "TERMS" not in md
    assert "Mindestalter 13" in md
    assert "<!-- quelle:" in md
    assert "Intangible Cultural Heritage" in md
    assert res.n_glossary >= 1
    assert res.n_emitted_sections >= 1
    assert res.n_missing_sections == 0
    # The gate verdict is in the front matter, whatever it is.
    assert re.search(r"^checks: ", md, re.MULTILINE)
    assert res.check_report and "results" in res.check_report


def test_type_call_runs_once_and_doc_type_skips_it():
    seen = {"type": 0}

    def _spy(system, user, max_tokens):
        if _is_type_call(system):
            seen["type"] += 1
        return _stub(system, user, max_tokens)

    kp.process_document(from_markdown(_standard_raw()), _fm(), llm=_spy)
    assert seen["type"] == 1
    kp.process_document(from_markdown(_standard_raw()), _fm(), llm=_spy,
                        doc_type="practice_report")
    assert seen["type"] == 1


def test_unusable_type_answer_runs_with_the_common_rules_only():
    def _bad_type(system, user, max_tokens):
        if _is_type_call(system):
            return json.dumps({"type": "poem", "language": "en"})
        assert "Reproduce completely" not in system or "PROFILE" in system
        return _stub(system, user, max_tokens)

    res = kp.process_document(from_markdown(_RAW), _fm(), llm=_bad_type)
    assert res.doc_type == ""
    assert res.n_emitted_sections >= 1


def test_summary_side_by_side_gives_the_same_file_and_reports_progress(monkeypatch):
    """map_workers > 1 overlaps the waiting for the parts of a cut document
    and nothing else: the same digests in the document's order, the same
    file, and one progress report per unit after the first."""
    def _strip_time(md):
        return re.sub(r"^analyzed_at:.*$", "", md, flags=re.MULTILINE)

    _cut(monkeypatch)
    one = kp.process_document(from_markdown(_standard_raw()), _fm(), llm=_stub)
    reports = []
    many = kp.process_document(from_markdown(_standard_raw()), _fm(), llm=_stub,
                               map_workers=4,
                               on_progress=lambda d, t: reports.append((d, t)))
    assert _strip_time(many.markdown) == _strip_time(one.markdown)
    total = one.n_units
    assert total > 1
    assert reports == [(i, total) for i in range(total + 1)]


class _DocSpy:
    """An LLM function that takes the document apart, as default_llm_fn does,
    and records what each call sent with it."""
    takes_document = True

    def __init__(self):
        self.sent = []          # (document, cache_ttl, system)

    def __call__(self, system, user, max_tokens=None, document=None, cache_ttl=""):
        if document:
            self.sent.append((document, cache_ttl, system))
        return _stub(system, (document or "") + user, max_tokens)


def test_summary_and_review_of_a_unit_send_the_same_document():
    """The prompt cache holds only a prefix that is the same bytes: the
    review of a unit has to send exactly the document its summary sent."""
    spy = _DocSpy()
    res = kp.process_document(from_markdown(_standard_raw()), _fm(), llm=spy)
    assert res.n_units == 1
    documents = {d for d, _, _ in spy.sent}
    assert len(documents) == 1
    systems = [s for _, _, s in spy.sent]
    assert any("REFUTE" in s for s in systems)
    assert any("REFUTE" not in s for s in systems)


def test_the_cache_lifetime_follows_the_waiting_for_a_worker(monkeypatch):
    """Every unit at once: the provider's default of 5 minutes. Units that
    wait for a worker: the hour, since the first unit's review waits for
    every summary."""
    one = _DocSpy()
    kp.process_document(from_markdown(_standard_raw()), _fm(), llm=one)
    assert {ttl for _, ttl, _ in one.sent} == {""}

    _cut(monkeypatch)
    queued = _DocSpy()
    res = kp.process_document(from_markdown(_standard_raw()), _fm(), llm=queued, map_workers=2)
    assert res.n_units > 2
    assert {ttl for _, ttl, _ in queued.sent} == {"1h"}
    assert len({d for d, _, _ in queued.sent}) == res.n_units

    at_once = _DocSpy()
    kp.process_document(from_markdown(_standard_raw()), _fm(), llm=at_once,
                        map_workers=res.n_units)
    assert {ttl for _, ttl, _ in at_once.sent} == {""}


def test_summary_side_by_side_honours_cancel(monkeypatch):
    _cut(monkeypatch)
    calls = []

    def _cancel():
        return len(calls) >= 2

    def _counting(system, user, max_tokens):
        calls.append(1)
        return _stub(system, user, max_tokens)

    with pytest.raises(kp.ProcessingCancelled):
        kp.process_document(from_markdown(_standard_raw()), _fm(), llm=_counting,
                            map_workers=2, cancel_check=_cancel)


# ---------------------------------------------------------------------------
# Prompts: guards against silent drift
# ---------------------------------------------------------------------------

def test_summary_system_names_type_language_page_form_and_terms():
    sysp = kp._summary_system("de", "practice_report", has_pages=True)
    name, what = kp.DOC_TYPES["practice_report"]
    assert f"The document is a {name}: {what}." in sysp
    assert "Write in GERMAN, in your own words" in sysp
    assert "(S. 4)" in sysp and "[S. 4]" in sysp     # page form in the summary's language
    assert "instructions, steps and enumerations completely" in sysp
    assert f'"## {kp._TERMS_HEADING}"' in sysp
    assert "write no title line" in sysp


def test_summary_system_without_pages_forbids_page_references():
    sysp = kp._summary_system("en", "", has_pages=False)
    assert "write no page references" in sysp
    assert "The document is a" not in sysp           # no type, no type sentence


def test_every_doc_type_has_a_name_and_a_description():
    assert set(kp.DOC_TYPES) == {"practice_report", "scholarly_article", "framework_report",
                                 "normative_text", "tool_handout", "book_chapter"}
    for key in kp.DOC_TYPES:
        name, what = kp.DOC_TYPES[key]
        assert name and what
        assert f"- {key}:" in kp._type_system()


def test_unit_document_carries_the_whole_document_with_page_markers():
    md = "# T\n\n## A\n\nText A.\n\n## B\n\nText B.\n"
    ex = from_markdown(md)
    for b in ex.blocks:
        b.page = 3 if "B" in b.text else 2
    units = kp.library_units(kp.clean_blocks(ex, "T")[0], "T")
    assert len(units) == 1
    doc = kp.unit_document(units[0], units, "T", "en")
    assert doc.startswith('Document: "T"')
    assert "Text A." in doc and "Text B." in doc
    assert "[p. 2]" in doc and "[p. 3]" in doc
    assert "Part 1 of" not in doc
    # The document ends in a blank line, so the instructions joined after it
    # by a connection without prompt caching stand apart.
    assert doc.endswith("=== END OF SOURCE ===\n\n")
    assert kp._summary_task(units) == ""


# ---------------------------------------------------------------------------
# Summary answers: the form in WISSEN, missing units, fatal
# ---------------------------------------------------------------------------

def _figure_unit():
    from my_app.services.knowledge_extract import Block
    blocks = [Block("heading", "A", page=4, level=2),
              Block("paragraph", "Text A.", page=4),
              Block("heading", "Inner", page=5, level=3),
              Block("paragraph", "More.", page=5),
              Block("figure", page=5, seq=1, figure_no="3", caption="Abb. 3: Monster",
                    image="doc.figures/fig-001.png"),
              Block("figure", page=5, seq=2, figure_no="4", caption="Abb. 4: Vulkan",
                    image="doc.figures/fig-002.png")]
    return kp.build_units(blocks)[0]


def test_finish_body_takes_out_title_line_and_terms_and_sets_heading_levels():
    answer = ("# Monster im Dialog\n\n## Ablauf (S. 4)\n\nText.\n\n### Inner [S. 5]\n\n"
              "More.\n\n## TERMS\n\n- **Sparringspartner**: das Bildmodell als Gegenüber")
    body, terms, notes = kp._finish_body(answer, _figure_unit(), "Monster", "de", {},
                                         True, True)
    assert body.startswith("### Ablauf (S. 4)\n\nText.\n\n#### Inner (S. 5)")
    assert "Monster im Dialog" not in body and "TERMS" not in body
    assert not re.search(r"^#{1,2} ", body, re.MULTILINE)
    assert any("title line removed: Monster im Dialog" in n for n in notes)
    assert terms == [{"term": "Sparringspartner", "definition": "das Bildmodell als Gegenüber"}]


def test_finish_body_keeps_a_first_section_with_sections_of_its_own():
    """A first heading without pages that carries sections of its own is a
    section, not a title line; it takes the pages of the sections below."""
    answer = ("## Ablauf\n\n### Erster Teil (S. 4)\n\nA.\n\n### Zweiter Teil (S. 5)\n\nB.\n\n"
              "## Schluss (S. 5)\n\nC.")
    body, _terms, notes = kp._finish_body(answer, _figure_unit(), "Monster", "de", {},
                                          True, True)
    assert body.startswith("### Ablauf (S. 4–5)\n\n#### Erster Teil (S. 4)")
    assert "### Schluss (S. 5)" in body
    assert not any("title line" in n for n in notes)


def test_finish_body_heads_a_bare_summary_and_lists_the_figures_at_the_end():
    body, _terms, _notes = kp._finish_body("Nur Text.", _figure_unit(), "Monster", "de",
                                           {1: "Ein gezeichnetes Monster mit drei Augen."},
                                           True, True)
    assert body.startswith("### Monster (S. 4–5)\n\nNur Text.\n\n### Abbildungen (S. 5)")
    # Figure 1 with number, page, caption and description; figure 2 without a
    # description names the exported image file.
    assert "*Abb. 3 (S. 5):* Monster — Ein gezeichnetes Monster mit drei Augen." in body
    assert body.endswith("_(Bildbeschreibung ausstehend: doc.figures/fig-002.png)_")


def test_glossary_doc_cap():
    """The per-document glossary is curated, not a vocabulary notebook."""
    digests = [
        kp.SectionDigest(abschnitt_de=f"A{i}", verdichtung="x",
                         begriffe=[{"term": f"T{i}-{j}", "definition": "d"} for j in range(5)],
                         source_heading=f"A{i}")
        for i in range(20)
    ]
    gloss = kp._dedup_glossary(digests)
    assert len(gloss) <= kp._GLOSSARY_DOC_CAP


def test_summary_missing_on_empty_answer_does_not_abort(monkeypatch):
    """A part whose model answers empty twice is recorded MISSING; the run
    completes, the other parts still emit, the heading check fails and the
    document stays draft."""
    _cut(monkeypatch)
    calls = []

    def _bad(system, user, max_tokens):
        if _is_type_call(system):
            return _TYPE_ANSWER
        if "PROFILE" in system:
            return "A profile of this document."
        if "Part 1 of" in user:
            calls.append(user)
            return ""
        return "## OK\n\n- a measure"

    res = kp.process_document(from_markdown(_standard_raw()), _fm(status="published"), llm=_bad)
    assert len(calls) == 2 and "Your last answer was empty" in calls[1]
    assert res.n_missing_sections == 1
    assert res.n_emitted_sections >= 1
    assert "## WISSEN" in res.markdown
    assert res.fatal == []
    assert res.status == "draft"
    failed = [r["name"] for r in res.check_report["results"] if not r["passed"]]
    assert "headings" in failed


def test_summary_all_empty_marks_document_fatal():
    """When EVERY unit comes back empty (a provider outage), the document is
    FATAL: the caller writes nothing (CLAUDE.md rule 12)."""
    def _all_bad(system, user, max_tokens):
        if _is_type_call(system):
            return _TYPE_ANSWER
        return ""

    res = kp.process_document(from_markdown(_standard_raw()), _fm(), llm=_all_bad)
    assert res.n_emitted_sections == 0
    assert any("no WISSEN subsections emitted" in f for f in res.fatal)
    assert any("PROFIL is empty or the placeholder" in f for f in res.fatal)


def test_short_document_is_not_flagged_for_its_length():
    """There is no ratio band: a short source whose condensation is longer
    than itself is neither a warning nor fatal."""
    short_raw = (
        "# Kurzanleitung: Klapp-Klaus\n\n## Spielablauf\n\n"
        "Zwei bis vier Personen ab 8 Jahren. Reihum spielt jede Person eine Karte; "
        "die hoechste Zahl gewinnt den Stich.\n")

    def _long(system, user, max_tokens):
        if _is_type_call(system):
            return json.dumps({"type": "tool_handout", "language": "de", "reason": "x"})
        if "PROFILE" in system:
            return "Kurzes Regelwerk fuer ein Kartenspiel ab 8 Jahren."
        return json.dumps({"title": "Spielablauf", "body": (
            "Fuer zwei bis vier Personen ab 8 Jahren; reihum wird eine Karte ausgespielt, "
            "die hoechste Zahl gewinnt den Stich, danach werden die Stiche gezaehlt."),
            "terms": []}, ensure_ascii=False)

    res = kp.process_document(from_markdown(short_raw), _fm(sprache="de"), llm=_long)
    assert res.compact_chars > res.source_chars
    assert res.fatal == []
    assert not any("ratio" in w for w in res.warnings)


def test_json_extraction_handles_fences_and_prose():
    obj = kp._extract_json_object("Sure, here you go:\n```json\n{\"a\": 1}\n```\nDone.")
    assert obj == {"a": 1}
    assert kp._extract_json_object("<think>reasoning only, no answer") is None


def test_mojibake_sniff():
    assert kp._has_mojibake("kaputt: Ã©cole")
    assert kp._has_mojibake("replacement � here")
    assert not kp._has_mojibake("saubere Zeichen: Kunstpädagogik, œuvre, 13")


def test_condensation_language_follows_the_source():
    """No target language given: the type call's language is the language of
    the condensation (page label, prompts), not DEFAULT_ANALYSIS_LANG."""
    seen = {"german": False}

    def _de(system, user, max_tokens):
        if _is_type_call(system):
            return json.dumps({"type": "practice_report", "language": "de", "reason": "x"})
        if "Write in GERMAN" in system:
            seen["german"] = True
        return _stub(system, user, max_tokens)

    res = kp.process_document(from_markdown(_RAW), _fm(sprache=""), llm=_de)
    assert seen["german"]
    assert res.analysis_lang == "de"
    assert "sprache: de" in res.markdown


def test_title_filled_from_first_heading_not_scaffolding():
    raw = "## Table of Contents\n\nA .......... 3\n\n## Der eigentliche Titel\n\nText.\n"
    res = kp.process_document(from_markdown(raw), _fm(titel=""), llm=_stub)
    assert "titel: Der eigentliche Titel" in res.markdown


# ---------------------------------------------------------------------------
# Glossary dedupe: acronym-in-parens normalisation
# ---------------------------------------------------------------------------

def test_glossary_dedupes_acronym_in_parens():
    """'Critical Diversity Literacy (CDL)' ≡ 'Critical Diversity Literacy' — one
    entry, the LONGER definition wins, and the acronym-bearing label is kept
    (the Mörsch run emitted both forms)."""
    digests = [
        kp.SectionDigest(
            abschnitt_de="A", verdichtung="x", source_heading="A",
            begriffe=[{"term": "Critical Diversity Literacy",
                       "definition": "kurz"}]),
        kp.SectionDigest(
            abschnitt_de="B", verdichtung="y", source_heading="B",
            begriffe=[{"term": "Critical Diversity Literacy (CDL)",
                       "definition": "eine deutlich längere, informationsreichere Definition"}]),
    ]
    gloss = kp._dedup_glossary(digests)
    cdl = [g for g in gloss if "Critical Diversity Literacy" in g["term"]]
    assert len(cdl) == 1, f"expected one CDL entry, got {[g['term'] for g in cdl]}"
    # Acronym-bearing label kept, longer definition won.
    assert cdl[0]["term"] == "Critical Diversity Literacy (CDL)"
    assert "informationsreichere" in cdl[0]["definition"]


def test_glossary_key_normalisation():
    assert kp._glossary_key("Critical Diversity Literacy (CDL)") == "critical diversity literacy"
    assert kp._glossary_key("Critical Diversity Literacy") == "critical diversity literacy"
    # A real parenthetical that is not an acronym (too long) is NOT stripped.
    assert kp._glossary_key("Kanon (im Sinne der Auswahl)") != "kanon"


# ---------------------------------------------------------------------------
# Bibliographic identification (identify_bibliographic) — title != byline !=
# chapter-heading != journal-head; excerpt -> overarching title + teil; nothing
# invented (unbestimmbar -> null + confidence low). The pass runs at the
# ORCHESTRATION layer (_run_verdichtung / repair script), NOT inside
# process_document — so process_document's own metadata stays LLM-call-free.
# ---------------------------------------------------------------------------

# A raw Docling-style title page: a MANGLED byline first, then the real title,
# then a subtitle, then body. This is exactly the art105413 shape.
_BIBLIO_RAW = """## Ernst wAgnEr

## Education for Sustainable Development

The Problem of a Universal Assumption Within UNESCO's Frameworks

This chapter questions global concepts like 'arts education' or 'education for
sustainable development' (ESD) that are considered universal. It reflects the
author's experiences over 17 years in international projects.

## References

- Belting, H. (1999). Hybrid Art?
"""

_BIBLIO_HINWEIS = ("International Journal for Research in Cultural, Aesthetic, and "
                   "Arts Education Volume 1 (2023), No. 1, 90–95 "
                   "https://doi.org/10.31244/IJRCAAE.2023.01.017 Waxmann 2023")


def test_identify_bibliographic_distinguishes_title_from_byline():
    """The identifier must return the WORK title, the byline in autoren (with the
    casing fixed), the year + journal from the imprint — never the byline as the
    title. The stub asserts the imprint line reached the prompt."""
    seen = {"hinweis": False}

    def _biblio(system, user, max_tokens):
        assert "bibliographic cataloguer" in system
        if "IJRCAAE" in user:
            seen["hinweis"] = True
        return json.dumps({
            "titel": "Education for Sustainable Development",
            "untertitel": "The Problem of a Universal Assumption Within UNESCO's Frameworks",
            "autoren": ["Ernst Wagner"],
            "jahr": 2023,
            "quelle": "International Journal for Research in Cultural, Aesthetic, and Arts Education (IJRCAAE)",
            "teil": None,
            "confidence": "high",
        }, ensure_ascii=False)

    rec = kp.identify_bibliographic(_BIBLIO_RAW, hinweis=_BIBLIO_HINWEIS, llm=_biblio)
    assert seen["hinweis"], "the operator imprint (hinweis) must reach the prompt"
    assert rec.titel == "Education for Sustainable Development"
    assert rec.autoren == ["Ernst Wagner"]           # casing normalised, byline -> author
    assert "wAgnEr" not in rec.composed_titel          # the byline is NOT the title
    assert rec.jahr == 2023
    assert rec.confidence == "high"
    # composed title carries the subtitle after ". "
    assert rec.composed_titel == (
        "Education for Sustainable Development. "
        "The Problem of a Universal Assumption Within UNESCO's Frameworks"
    )


def test_identify_bibliographic_excerpt_uses_overarching_title_and_teil():
    """A book excerpt: titel is the BOOK's title, the chapter goes into `teil`,
    and composed_titel joins them with ' — '."""
    def _biblio(system, user, max_tokens):
        return json.dumps({
            "titel": "Kunstlabore: Für mehr Kunst in Schulen!",
            "untertitel": None,
            "autoren": ["J. Heisig", "I. Scharf", "H. Schönfeld"],
            "jahr": None,
            "quelle": "transcript Verlag",
            "teil": "Künstlerische Strategien (S. 3–48)",
            "confidence": "high",
        }, ensure_ascii=False)

    rec = kp.identify_bibliographic("## Künstlerische Strategien\n\nText …",
                                    hinweis="auszug aus: Heisig, J. …", llm=_biblio)
    assert rec.titel == "Kunstlabore: Für mehr Kunst in Schulen!"
    assert rec.teil == "Künstlerische Strategien (S. 3–48)"
    assert rec.composed_titel.endswith(" — Künstlerische Strategien (S. 3–48)")
    assert rec.autoren_str == "J. Heisig, I. Scharf, H. Schönfeld"


def test_identify_bibliographic_invents_nothing_on_bad_json():
    """On a hard JSON miss (twice) the record is empty + confidence low — the
    caller then keeps its own fallbacks. Never raises."""
    rec = kp.identify_bibliographic("## Something\n\nBody.", hinweis="",
                                    llm=lambda s, u, m: "not json at all")
    assert rec.titel is None
    assert rec.composed_titel == ""
    assert rec.autoren == []
    assert rec.jahr is None
    assert rec.confidence == "low"


def test_identify_bibliographic_year_parsed_from_noise():
    """A year embedded in a noisy string is extracted; a non-year is dropped."""
    def _biblio(system, user, max_tokens):
        return json.dumps({"titel": "T", "autoren": [], "jahr": "erschienen 2021",
                           "quelle": None, "teil": None, "confidence": "low"})
    rec = kp.identify_bibliographic("## T\n\nx", llm=_biblio)
    assert rec.jahr == 2021

    def _biblio2(system, user, max_tokens):
        return json.dumps({"titel": "T", "autoren": [], "jahr": "n.d.",
                           "quelle": None, "teil": None, "confidence": "low"})
    rec2 = kp.identify_bibliographic("## T\n\nx", llm=_biblio2)
    assert rec2.jahr is None


def test_identify_bibliographic_year_fallback_from_doc_id_slug():
    """Title page yields no year -> the doc_id slug's year fills it; a year IN
    the document always wins over the slug; a non-year number (issue/page) is
    not mistaken for a year."""
    def _no_year(system, user, max_tokens):
        return json.dumps({"titel": "T", "autoren": ["Wu"], "jahr": None,
                           "quelle": None, "teil": None, "confidence": "low"})
    rec = kp.identify_bibliographic("## T\n\nx", doc_id="wu-et-al-2023-stable", llm=_no_year)
    assert rec.jahr == 2023

    def _has_year(system, user, max_tokens):
        return json.dumps({"titel": "T", "autoren": ["Wu"], "jahr": 2019,
                           "quelle": None, "teil": None, "confidence": "low"})
    rec2 = kp.identify_bibliographic("## T\n\nx", doc_id="wu-et-al-2023-stable", llm=_has_year)
    assert rec2.jahr == 2019

    rec3 = kp.identify_bibliographic("## T\n\nx", doc_id="issue-149-p60-67", llm=_no_year)
    assert rec3.jahr is None


def test_identify_bibliographic_passes_max_tokens_none():
    """Platform rule: hard max_tokens caps are forbidden. identify_bibliographic
    must not cap either the main call or the repair retry (both must reach the
    LLM helper as max_tokens=None)."""
    seen_max_tokens = []

    def _biblio(system, user, max_tokens):
        seen_max_tokens.append(max_tokens)
        return "not json at all"  # forces both the main call and the repair retry

    kp.identify_bibliographic("## Something\n\nBody.", hinweis="", llm=_biblio)
    assert len(seen_max_tokens) == 2, "expected the main call + one repair retry"
    assert all(mt is None for mt in seen_max_tokens)


def test_identify_bibliographic_head_tail_window_labels_imprint_region():
    """_content_head_tail keeps real lines (drops blanks + image markers) and, for
    a long document, appends a distinct tail block for the imprint region."""
    long_raw = "# Title\n\n<!-- image -->\n\n" + "\n".join(
        f"Content line {i}." for i in range(200)) + "\n\nIMPRESSUM: Verlag 2020\n"
    window = kp._content_head_tail(long_raw)
    assert "<!-- image -->" not in window
    assert "Title" in window
    assert "PAGE END / IMPRINT" in window
    assert "IMPRESSUM: Verlag 2020" in window


def test_biblio_system_prompt_encodes_the_distinctions():
    """A guard against silent prompt drift: the identifier prompt must name the
    title-vs-byline-vs-chapter-vs-journal distinctions and the excerpt rule."""
    sysp = kp._BIBLIO_SYSTEM
    assert "WORK TITLE" in sysp
    assert "BYLINE" in sysp
    assert "CHAPTER" in sysp
    assert "JOURNAL" in sysp or "MASTHEAD" in sysp
    assert "INVENT NOTHING" in sysp
    assert "teil" in sysp  # the excerpt field is described


def test_quelle_rendered_in_front_matter_when_present():
    """render_front_matter emits `quelle:` (after jahr) only when present, and
    JSON-quotes a citation string (it contains ':' and ','). An absent quelle
    leaves the front-matter as before."""
    fm = {"id": "x", "titel": "T", "autor": "A", "jahr": 2023,
          "quelle": "IJRCAAE, Vol. 1: 90–95", "sprache": "de", "tier": "O",
          "sparten": [], "themen": [], "lizenz": "x", "url": "", "status": "draft"}
    out = kp.render_front_matter(fm)
    assert 'quelle: "IJRCAAE, Vol. 1: 90–95"' in out
    # order: quelle sits between jahr and sprache
    assert out.index("jahr:") < out.index("quelle:") < out.index("sprache:")
    # absent quelle -> no line
    fm2 = dict(fm)
    del fm2["quelle"]
    assert "quelle:" not in kp.render_front_matter(fm2)


def test_process_document_does_not_call_biblio_itself():
    """The engine must NOT fire a bibliographic call: a stub that ONLY answers
    Map/Reduce (and would error on a biblio prompt) still completes, and the
    title comes from paratext — proof the biblio pass is not wired into the
    engine (it lives in _run_verdichtung / the repair script)."""
    calls = {"biblio": 0}

    def _strict(system, user, max_tokens):
        if "bibliographic cataloguer" in system:
            calls["biblio"] += 1
            raise AssertionError("process_document must not call identify_bibliographic")
        return _stub(system, user, max_tokens)

    res = kp.process_document(from_markdown(_RAW), _fm(titel=""), llm=_strict)
    assert calls["biblio"] == 0
    assert "titel: Guidance Note on Something" in res.markdown  # first-heading fallback


# ---------------------------------------------------------------------------
# Analysis provenance (analyzed_at / analysis_lang / analysis_model) -- the
# owner otherwise cannot tell WHEN a document was analysed, in WHAT language,
# or by WHICH model(s) actually served the run. The configured
# KNOWLEDGE_PROCESSING_MODEL slot can silently diverge from the latter via
# call_chat_helper's model->provider fallback (see default_llm_fn) -- this is
# exactly how a hybrid document once happened invisibly (six of eleven Map
# calls fell back from mammouth/qwen3.7-plus to gemini mid-run).
# ---------------------------------------------------------------------------

def test_process_document_writes_analysis_provenance_keys():
    """A successful Verdichtung stamps all three provenance keys into the
    front-matter, and mirrors them on the returned ProcessingResult.
    analysis_model reflects the model(s) that ACTUALLY served the run
    (llm.models_used, mirroring default_llm_fn's tracking of call_chat_helper's
    `model_used`) -- simulated here exactly as the qwen -> gemini fallback
    incident happened: two distinct models served this one document's calls,
    comma-joined in the output. analysis_lang (the target_lang the analysis
    was WRITTEN in) must never be conflated with `sprache` (the document's own
    detected SOURCE language, here deliberately set to a DIFFERENT value)."""
    def _spy(system, user, max_tokens):
        return _stub(system, user, max_tokens)
    _spy.models_used = ["mammouth/qwen3.7-plus", "openrouter/google/gemini-3-flash-preview"]

    res = kp.process_document(from_markdown(_RAW), _fm(sprache="de"), llm=_spy,
                              target_lang="en")

    assert "analyzed_at:" in res.markdown
    assert "sprache: de" in res.markdown
    assert "analysis_lang: en" in res.markdown  # the target language, not "de"
    expected_model_line = "analysis_model: " + kp._yaml_scalar(
        "mammouth/qwen3.7-plus, openrouter/google/gemini-3-flash-preview")
    assert expected_model_line in res.markdown

    # analyzed_at is a real, timezone-aware UTC timestamp -- not a placeholder.
    m = re.search(r'analyzed_at: "(.+?)"', res.markdown)
    assert m, "analyzed_at line not found (or not quoted) in the assembled markdown"
    parsed = datetime.fromisoformat(m.group(1))
    assert parsed.tzinfo is not None

    # Mirrored on the result object too, not only baked into the markdown.
    assert res.analyzed_at == m.group(1)
    assert res.analysis_lang == "en"
    assert res.analysis_model == "mammouth/qwen3.7-plus, openrouter/google/gemini-3-flash-preview"


def test_process_document_provenance_degrades_without_models_used():
    """A caller-supplied llm with no `.models_used` (every pre-existing test
    stub in this file, and any future caller that just passes a bare function)
    must never crash -- analysis_model degrades to the empty string, never a
    guess. analyzed_at/analysis_lang are still stamped (they never depend on
    models_used)."""
    res = kp.process_document(from_markdown(_RAW), _fm(), llm=_stub)
    assert "analyzed_at:" in res.markdown
    assert "analysis_lang: en" in res.markdown
    assert "analysis_model: " + kp._yaml_scalar("") in res.markdown
    assert res.analysis_model == ""


def test_render_front_matter_without_provenance_keys_still_parses():
    """A document lacking the provenance keys (any file produced before this
    feature) must still render exactly as before -- render_front_matter's
    allowlist only emits a key when the caller's dict actually carries it, so
    an old-style call site (no analyzed_at/analysis_lang/analysis_model in fm)
    is completely unaffected: no stray keys, no crash, no guessed values."""
    fm = {"id": "x", "titel": "T", "autor": "A", "jahr": 2023,
          "sprache": "de", "tier": "O", "sparten": [], "themen": [],
          "lizenz": "x", "url": "", "status": "draft"}
    out = kp.render_front_matter(fm)
    assert "analyzed_at:" not in out
    assert "analysis_lang:" not in out
    assert "analysis_model:" not in out



def test_compose_doc_id_author_year_title():
    from my_app.services.knowledge_processing import compose_doc_id
    assert compose_doc_id("Becoming Planetary", "Jennifer Gabrys", 2018) == \
        "gabrys-2018-becoming-planetary"
    assert compose_doc_id(
        "An Invitation for Black and Indigenous Artists to Dream",
        "Kite, Alisha B. Wormsley", "2020").startswith("kite-and-wormsley-2020-")
    assert compose_doc_id(
        "(Re-)Searching Peace Education",
        "Benjamin Jörissen, Gloria Zapata Restrepo, Tanja Klepacki", 2026) == \
        "jorissen-et-al-2026-re-searching-peace-education"
    assert compose_doc_id(
        "Über die Kunst, den Wandel zu gestalten",
        "Karola Braun-Wanke, Anke Ebel", 2020) == \
        "braun-wanke-and-ebel-2020-uber-die-kunst-den-wandel-zu-gestalten"


def test_compose_doc_id_title_only_and_excerpt():
    from my_app.services.knowledge_processing import compose_doc_id
    # missing year -> title-only (the author is dropped as well)
    r = compose_doc_id("Generative AI and the Politics of Perception",
                       "Benjamin Jörissen, Vanessa Baumann", "")
    assert "jorissen" not in r and r.startswith("generative-ai")
    # missing author -> title-only
    assert compose_doc_id("Der Raum", "", 2019) == "der-raum"
    # excerpt: the section after the em-dash is the slug
    assert compose_doc_id(
        "Kunstlabore: Für mehr Kunst — Künstlerische Strategien",
        "", "") == "kunstlerische-strategien"
    # no title at all -> '' (caller keeps provisional id)
    assert compose_doc_id("", "Gabrys", 2018) == ""
