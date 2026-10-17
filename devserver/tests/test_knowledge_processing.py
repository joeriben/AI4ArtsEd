"""
Tests for the knowledge Verdichtung service (my_app.services.knowledge_processing).

Exercise the DETERMINISTIC parts against a synthetic raw Docling Markdown (no
network) and the assembly/validation, with a stub LLM injected for the Map/Reduce
steps. The point of these tests is the SARAH promise: structure and artifact
filtering are computed deterministically, so they can be asserted exactly.

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

## Chapter 1: Access thresholds

Governments should enact the following measures:
- set a minimum age of 13 for account creation
- require parental consent below age 16
- audit systems every 12 months

Concrete example: a school in Kenya piloted this in 2022 with 650 students.

The Guidance Note running header
The Guidance Note running header
The Guidance Note running header
The Guidance Note running header
The Guidance Note running header

## Conclusion

The way forward requires coordinated action across ministries.
"""


def _stub(system, user, max_tokens):
    if "PROFIL" in system:
        return ("Menschzentrierter Ansatz, baut auf der Empfehlung zur KI-Ethik "
                "2021 auf. Anwendbar in medialer Kunstpaedagogik.")
    head = "Zugangsschwellen" if "Access" in user else "Abschnitt"
    return json.dumps({
        "section_title": head,
        "digest": "- Mindestalter 13\n- elterliche Zustimmung unter 16\n- Audit alle 12 Monate\nBeispiel: Kenia 2022, 650 Lernende.",
        "terms": [{"term": "Intangible Cultural Heritage", "definition": "immaterielles Kulturerbe"}],
    }, ensure_ascii=False)


def _fm(**over):
    fm = {"id": "test-guidance-2023", "titel": "", "autor": "UNESCO", "jahr": 2023,
          "sprache": "en", "tier": "F", "sparten": ["medial"], "themen": ["ai_ethics"],
          "lizenz": "CC BY-SA 3.0 IGO", "url": "https://x", "status": "draft"}
    fm.update(over)
    return fm


# ---------------------------------------------------------------------------
# Deterministic structure parsing + artifact filtering
# ---------------------------------------------------------------------------

def test_parse_structure_filters_artifacts_and_harvests_paratext():
    paratext, content, all_kept = kp.parse_structure(_RAW)
    joined = "\n".join(s.body for s in all_kept)

    # Title harvested from the H1.
    assert paratext.title == "Guidance Note on Something"
    # ToC dot-leaders, the acronym table, the image marker and the running header
    # are all gone from every kept section body.
    assert "........" not in joined
    assert "Artificial Intelligence" not in joined  # acronym table dropped
    assert "GDPR" not in joined
    assert "<!-- image -->" not in joined
    assert "running header" not in joined
    # Foreword + Chapter 1 + Conclusion are content sections; ToC/Abbreviations
    # (skip-matter) are not.
    headings = {s.heading for s in content}
    assert any("Access" in h or "Chapter 1" in h for h in headings)
    assert not any("Contents" in h or "Abbreviations" in h for h in headings)


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

def test_process_document_shape_and_mittellage():
    # mode pinned: _RAW is heading-sparse+short and would auto-detect as essay;
    # this test exercises STANDARD-mode mechanics (chapter packing + budget).
    res = kp.process_document(_RAW, _fm(), llm=_stub, mode="standard")
    md = res.markdown

    # The compact form: PROFIL/WISSEN/GLOSSAR, never the old full-text markers.
    assert "## PROFIL" in md
    assert "## WISSEN" in md
    assert "## GLOSSAR" in md
    assert "## DOCUMENT" not in md
    assert "## CARD" not in md

    # Title filled from paratext; front-matter schema unchanged.
    assert "titel: Guidance Note on Something" in md

    # Mittellage: a concrete number + enumerated measures survive into WISSEN.
    assert "Mindestalter 13" in md
    assert "Audit alle 12 Monate" in md

    # Review anchor present in the file (stripped only at index time).
    assert "<!-- quelle:" in md

    # Glossary term deduplicated + present.
    assert "Intangible Cultural Heritage" in md
    assert res.n_glossary >= 1
    assert res.n_emitted_sections >= 1
    assert res.n_missing_sections == 0


def test_mittellage_rule_constant_is_in_map_prompt():
    """The Mittellage rule is the core instruction; it must reach the Map prompt
    verbatim (a guard against silent prompt drift). Selection-not-paraphrase and
    the budget-vs-specifics tiebreak are part of the rule."""
    rule = kp._mittellage_rule("ENGLISH")
    assert "BELOW the model's general training knowledge" in rule
    assert "SELECTING" in rule
    assert "specifics are sacred" in rule
    assert rule in kp._map_system("en")


def test_map_system_target_lang_parameter_reaches_prompt():
    """The target_lang parameter must actually reach the Map system prompt --
    the exact defect this rebuild fixes: telling the model its target language
    in the WRONG language. _map_system("de") must be steered towards GERMAN;
    the default (no arg / "en") towards ENGLISH."""
    assert "GERMAN" in kp._map_system("de")
    assert "ENGLISH" in kp._map_system()
    assert "ENGLISH" in kp._map_system("en")


def test_word_budget_named_in_map_prompt():
    """Every Map call must carry a concrete word budget (the enforcement lever
    against paraphrase-instead-of-selection)."""
    seen = {"budget": False}

    def _spy(system, user, max_tokens):
        if "PROFIL" in system:
            return "Ein Profil."
        if "WORD BUDGET" in user and "words" in user:
            seen["budget"] = True
        return json.dumps({"section_title": "OK", "digest": "- x", "terms": []})

    kp.process_document(_RAW, _fm(), llm=_spy, mode="standard")
    assert seen["budget"]


def test_normtext_mode_adds_block_and_tighter_budget():
    """mode='normtext' must add the legal-instrument block to the system prompt
    (reference-style, no article-by-article paraphrase)."""
    seen = {"norm": False}

    def _spy(system, user, max_tokens):
        if "PROFIL" in system:
            return "Ein Profil."
        if "SPECIAL CASE NORMTEXT" in system:
            seen["norm"] = True
        return json.dumps({"section_title": "OK", "digest": "- x", "terms": []})

    kp.process_document(_RAW, _fm(), llm=_spy, mode="normtext")
    assert seen["norm"]
    assert kp._BUDGET_RATIO["normtext"] < kp._BUDGET_RATIO["standard"]


def test_pack_units_merges_small_sections():
    """Chapter packing: many small sections collapse into few units (the unit of
    condensation is the chapter, not the bullet group)."""
    _, content, _ = kp.parse_structure(_RAW)
    units = kp._pack_units(content)
    assert 1 <= len(units) <= len(content)


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


def test_map_missing_on_bad_json_does_not_abort():
    """A unit whose LLM never returns valid JSON is recorded MISSING; the run
    completes and other units still emit. Uses the heading-rich
    _standard_raw() document (naturally packs into several units, no
    monkeypatching needed) so raw_chars is large enough that fixed
    front-matter/heading overhead does not itself distort the
    compression-ratio band -- a tiny document cannot carry this assertion,
    since its assembled skeleton alone would already exceed the band
    regardless of digest content."""
    digest = (
        "- governments should enact a minimum threshold and an explicit age "
        "limit for this measure, reviewed annually by the responsible "
        "ministry\n"
        "- compliance is audited on a fixed schedule and the results are "
        "published to the public and to oversight bodies\n"
        "- concrete example: a comparable programme piloted this in 2022 "
        "across several regions with specific uptake numbers reported back"
    )

    def _bad(system, user, max_tokens):
        if "PROFIL" in system:
            return ("A profile that states the position, the reference "
                     "frameworks, and the applicability of this document "
                     "for arts education.")
        # Chapter 1's unit: junk both times (main call + repair retry).
        if "Chapter 1:" in user:
            return "not json at all"
        return json.dumps({"section_title": "OK", "digest": digest, "terms": []})

    res = kp.process_document(_standard_raw(), _fm(), llm=_bad, mode="standard")
    assert res.n_missing_sections >= 1
    assert res.n_emitted_sections >= 1  # the other units still made it
    # A MISSING unit contributes no WISSEN subsection.
    assert "## WISSEN" in res.markdown
    # One bad unit among several must NOT abort/fatal the document -- only a
    # total wipeout should (see test_map_all_bad_json_marks_document_fatal).
    assert res.fatal == []


def test_map_all_bad_json_marks_document_fatal():
    """The mirror case: when EVERY unit fails to parse (e.g. a provider outage
    returning junk for the whole run), the document is marked FATAL. This is
    the guard that stops an outage from silently overwriting a good prior
    analysis (CLAUDE.md rule 12). process_document itself never raises -- the
    caller is the one that must refuse to write/reindex on a non-empty
    result.fatal."""
    def _all_bad(system, user, max_tokens):
        if "PROFIL" in system:
            return "A profile."
        return "not json at all"

    res = kp.process_document(_standard_raw(), _fm(), llm=_all_bad, mode="standard")
    assert res.n_emitted_sections == 0
    assert any("no WISSEN subsections emitted" in f for f in res.fatal)


# ---------------------------------------------------------------------------
# Compression ratio: FLOOR is a safety bound (FATAL), CEILING is a quality
# signal (ADVISORY only) -- see the comment above _RATIO_FLOOR/_RATIO_CEILING
# in knowledge_processing.py. These two tests are the mirror pair the bound
# split exists to prove: a too-HIGH ratio must never block the write, a
# genuine stub must always be rejected, floor included.
# ---------------------------------------------------------------------------

def test_ratio_above_ceiling_is_warning_not_fatal():
    """A too-HIGH compression ratio is a QUALITY signal (the model paraphrased
    instead of selecting), never a safety one -- it must NOT abort the write.
    Fixed assembly overhead (front-matter, headings, quelle-anchors) dominates
    the ratio for a short source -- this fixture is the real shape of
    klapp-klaus-spielanleitung-printable (a few kB raw -> > 100% ratio), so
    the ceiling is structurally unreachable-under for such a document and
    must stay advisory-only."""
    short_raw = (
        "# Kurzanleitung: Klapp-Klaus\n\n"
        "## Spielablauf\n\n"
        "Diese Spielanleitung beschreibt den Ablauf eines einfachen "
        "Kartenspiels fuer zwei bis vier Personen ab acht Jahren. Zum Aufbau "
        "werden alle Karten gemischt und gleichmaessig ausgeteilt. Reihum "
        "spielt jede Person eine Karte aus der Hand aus; wer die hoechste "
        "Zahl zeigt, gewinnt den Stich und legt ihn verdeckt beiseite. Nach "
        "dem letzten Stich zaehlt jede Person ihre gewonnenen Karten; die "
        "Person mit den meisten Stichen gewinnt die Runde. Zum Abbau werden "
        "alle Karten wieder eingesammelt und im Kaestchen verstaut.\n"
    )

    def _stub_ceiling(system, user, max_tokens):
        if "PROFIL" in system:
            return ("Kurzes Regelwerk fuer ein Kartenspiel; Zielgruppe Kinder "
                     "ab acht Jahren; anwendbar im Kunstunterricht als "
                     "spielerischer Einstieg in Regelverstaendnis.")
        return json.dumps({
            "section_title": "Spielablauf",
            "digest": ("Aufbau: Karten mischen und austeilen. Ablauf: reihum "
                       "eine Karte ausspielen, hoechste gewinnt den Stich. "
                       "Abbau: Karten einsammeln und verstauen."),
            "terms": [],
        }, ensure_ascii=False)

    res = kp.process_document(short_raw, _fm(), llm=_stub_ceiling, mode="standard")
    assert res.ratio > kp._RATIO_CEILING
    # Not fatal: a paraphrase-vs-selection quality issue must never block the write.
    assert res.fatal == []
    # Advisory only, naming the ratio so the operator sees it in the job log.
    assert len(res.warnings) == 1
    assert "compression ratio" in res.warnings[0]
    assert "ceiling" in res.warnings[0]
    # The document is still complete and would be written.
    assert "## PROFIL" in res.markdown
    assert "## WISSEN" in res.markdown
    assert res.n_emitted_sections == 1
    assert res.n_missing_sections == 0


def test_stub_output_stays_fatal_with_all_reasons():
    """The mirror case: a genuine provider-outage stub (no usable PROFIL,
    every unit MISSING, compression ratio far BELOW the floor) must still be
    rejected with every one of its reasons. This is the exact shape of the
    incident this whole guard exists for (a 558-char stub at ratio 1.3% once
    overwrote a good analysis, CLAUDE.md rule 12) -- the floor stays FATAL,
    corroborating the (also fatal) structural checks."""
    long_raw = (
        "# Stub Source\n\n## Chapter\n\n"
        + "Substantive prose about arts education policy and practice. " * 700
    )

    def _stub_outage(system, user, max_tokens):
        if "PROFIL" in system:
            return ""  # the Reduce call returns nothing usable
        return "not a valid json response at all"  # every Map call fails twice -> MISSING

    res = kp.process_document(long_raw, _fm(), llm=_stub_outage, mode="standard")
    assert res.ratio < kp._RATIO_FLOOR
    assert res.n_emitted_sections == 0
    assert res.fatal
    assert any("no WISSEN subsections emitted" in f for f in res.fatal)
    assert any("PROFIL is empty or the placeholder" in f for f in res.fatal)
    assert any("below the floor" in f for f in res.fatal)
    assert res.warnings == []


def test_json_extraction_handles_fences_and_prose():
    obj = kp._extract_json_object("Sure, here you go:\n```json\n{\"a\": 1}\n```\nDone.")
    assert obj == {"a": 1}
    assert kp._extract_json_object("<think>reasoning only, no answer") is None


def test_mojibake_sniff():
    assert kp._has_mojibake("kaputt: Ã©cole")
    assert kp._has_mojibake("replacement � here")
    assert not kp._has_mojibake("saubere Zeichen: Kunstpädagogik, œuvre, 13")


# ---------------------------------------------------------------------------
# Text-type detection: standard / normtext / essay (deterministic)
# ---------------------------------------------------------------------------

# A dense argumentative essay: continuous prose under one heading, few headings,
# short. This is the shape that produced 2 amorphous WISSEN blocks before.
_ESSAY_RAW = """## Skizze zu einer diskriminierungskritischen Bildung

## Von A. Autorin

Zunächst behaupte ich, dass bloße Erweiterung der Inhalte nicht genügt. Denn
wer nur die Lektürelisten ergänzt, lässt die Strukturen unangetastet, gegen die
sich dieser Text gerade wendet. Ich setze mich also ab gegen die additive
Lösung und begründe das mit der Kolonialität der Institutionen selbst.

Daraus folgt meine zentrale Unterscheidung zwischen Diskriminierungskritik und
Dekolonisierung: die erste arbeitet an Kategorien im Hier, die zweite an der
epistemischen Ordnung. Ich habe den Titel durchgestrichen, weil das Ziel kaum
erreichbar ist und doch den Horizont bildet — eine Selbstpositionierung, die den
Widerspruch aushält.

Als Kriterienrahmen dienen die folgenden Indikatoren: Differenz als sozial
hergestellt verstehen; Intersektionalität erkennen; Privilegiertheit
reflektieren; eine Sprache für Herrschaft haben; hegemoniale Adressierung
dekodieren; Kontinuitäten begreifen; und den Willen zur Veränderung entwickeln.

Ein Beispiel trägt das Argument: in gemischten Gruppen droht die
Instrumentalisierung der Betroffenen als Lehrende. Daran zeigt sich, dass das
Curriculum die Kritik zuerst auf sich selbst anwenden muss und nie
abgeschlossen ist.
"""


def _standard_raw() -> str:
    """A heading-rich AND long document (>= 4 content headings, >= 800 lines):
    the standard/report shape that must NOT be treated as an essay. Body lines
    are DISTINCT (a repeated identical line would be stripped as a running
    header, emptying the section)."""
    parts = ["# A Long Framework Document", ""]
    for i in range(1, 9):
        parts.append(f"## Chapter {i}: Area {i}")
        parts.append("")
        for j in range(120):
            parts.append(f"Measure {i}.{j}: governments should enact this specific action.")
        parts.append("")
    return "\n".join(parts)


def test_detect_mode_essay_on_heading_sparse_short():
    """A dense short essay (few headings, short) -> essay mode, with a numeric
    reason naming the trigger."""
    _, _, all_kept = kp.parse_structure(_ESSAY_RAW)
    mode, reason = kp.detect_mode(_ESSAY_RAW, all_kept, explicit="auto")
    assert mode == "essay"
    assert "essay" in reason.lower()
    # The reason states the concrete count that fired the rule.
    assert "Heading" in reason or "Zeilen" in reason


def test_detect_mode_standard_on_heading_rich_long():
    """A heading-rich, long document -> standard (NOT essay): both essay signals
    must be false."""
    raw = _standard_raw()
    assert len(raw.splitlines()) >= kp._ESSAY_MAX_RAW_LINES
    _, _, all_kept = kp.parse_structure(raw)
    assert kp._count_content_headings(all_kept) >= kp._ESSAY_MAX_CONTENT_HEADINGS
    mode, reason = kp.detect_mode(raw, all_kept, explicit="auto")
    assert mode == "standard"


def test_detect_mode_honours_explicit_normtext():
    """An explicit mode is never overridden by detection (a legal instrument is
    not downgraded to essay just because it is heading-sparse)."""
    _, _, all_kept = kp.parse_structure(_ESSAY_RAW)
    mode, _ = kp.detect_mode(_ESSAY_RAW, all_kept, explicit="normtext")
    assert mode == "normtext"


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
# Essay mode: LLM segmentation drives the units + argument-preservation prompt
# ---------------------------------------------------------------------------

def _essay_stub(system, user, max_tokens):
    """Stub for the essay path: the segmenter returns an outline of argument
    sections; each Map call returns a digest; the Reduce returns a PROFIL."""
    if "ARGUMENT SECTIONS" in system:
        # Segmenter — argument sections spanning the essay by line range (the
        # four argument paragraphs of _ESSAY_RAW: problem, distinction+self-
        # positioning, criteria, application/self-application).
        return json.dumps({"sections": [
            {"title": "Problemaufriss: additive Lösung genügt nicht", "von": 5, "bis": 8},
            {"title": "Zentrale Unterscheidung + Selbstpositionierung", "von": 10, "bis": 14},
            {"title": "Kriterienrahmen: Indikatoren", "von": 16, "bis": 19},
            {"title": "Anwendung + Selbstanwendung", "von": 21, "bis": 24},
        ]}, ensure_ascii=False)
    if "PROFIL" in system:
        return "Setzt sich gegen bloße Inhaltserweiterung ab; Kriterienrahmen; Selbstanwendung."
    # A Map call — echo a short digest, carry one in-vivo term.
    return json.dumps({
        "section_title": "Argument",
        "digest": "- These: additive Lösung genügt nicht\n- Abgrenzung zur epistemischen Ordnung",
        "terms": [{"term": "Diskriminierungskritik", "definition": "Kritik an Kategorien der Ungleichheit"}],
    }, ensure_ascii=False)


def test_essay_mode_uses_llm_segmentation_and_preserve_prompt():
    """In essay mode the ARGUMENT-preservation prompt reaches the Map call and
    the units come from the LLM segmenter (multiple argument sections, each
    anchored to its LLM working title — not a raw heading)."""
    seen = {"preserve": False, "segmenter": False}

    def _spy(system, user, max_tokens):
        if "ARGUMENT SECTIONS" in system:
            seen["segmenter"] = True
        if "ARGUMENTATIVE scholarly essay" in system:
            seen["preserve"] = True
        return _essay_stub(system, user, max_tokens)

    res = kp.process_document(_ESSAY_RAW, _fm(id="essay-test"), llm=_spy, mode="essay")
    assert seen["segmenter"], "the essay segmenter pre-call must run"
    assert seen["preserve"], "the argument-preservation prompt must reach the Map call"
    # More than the 2 amorphous blocks the heading parser would have produced.
    assert res.n_emitted_sections >= 4
    # Review anchor is the LLM working title, never the byline heading.
    assert "<!-- quelle: Kriterienrahmen: Indikatoren -->" in res.markdown
    assert "Von A. Autorin" not in res.markdown.split("## WISSEN")[1]


def test_essay_segmenter_slices_by_line_range():
    """_segment_essay honours the LLM line ranges verbatim (1-based inclusive)."""
    def _seg(system, user, max_tokens):
        return json.dumps({"sections": [
            {"title": "Erste Hälfte", "von": 5, "bis": 8},
            {"title": "Zweite Hälfte", "von": 10, "bis": 14},
        ]}, ensure_ascii=False)

    segs = kp._segment_essay(_ESSAY_RAW, _seg)
    assert segs is not None and len(segs) == 2
    assert segs[0].titel == "Erste Hälfte"
    # The sliced body is the actual line-5..8 content of the essay.
    assert "additive" in segs[0].body or "Erweiterung" in segs[0].body


def test_first_raw_heading_prefers_title_over_byline():
    """_first_raw_heading returns the DOCUMENT title even when it has an empty
    body followed by a byline heading (the Mörsch shape: '## Title' then
    '## Von X'). This drives the essay title fallback."""
    raw = "## Decolonizing Arts Education. Skizze\n\n## Von A. Autorin\n\nDer Text …\n"
    assert kp._first_raw_heading(raw) == "Decolonizing Arts Education. Skizze"
    # Skip-matter (a ToC heading) is passed over.
    raw2 = "## Table of Contents\n\n## Der eigentliche Titel\n\nText …\n"
    assert kp._first_raw_heading(raw2) == "Der eigentliche Titel"


def test_essay_title_filled_from_first_raw_heading():
    """When titel is blank and the title is an H2 with no body (Docling essay
    shape), process_document fills it from the first raw heading, not the byline
    and not empty."""
    raw = ("## Der Aufsatztitel\n\n## Von A. Autorin\n\n"
           + _ESSAY_RAW.split("## Von A. Autorin", 1)[1])

    def _seg(system, user, max_tokens):
        if "ARGUMENT SECTIONS" in system:
            return json.dumps({"sections": [
                {"title": "Abschnitt eins", "von": 5, "bis": 9},
            ]}, ensure_ascii=False)
        if "PROFIL" in system:
            return "Ein Profil."
        return json.dumps({"section_title": "OK", "digest": "- x", "terms": []}, ensure_ascii=False)

    res = kp.process_document(raw, _fm(id="essay-title", titel=""), llm=_seg, mode="essay")
    assert "titel: Der Aufsatztitel" in res.markdown
    assert "titel: Von A. Autorin" not in res.markdown


def test_essay_mode_falls_back_to_packing_when_segmenter_fails():
    """If the segmenter never returns valid JSON, essay mode degrades to
    heading-based packing (keeping the essay budget) — it must NOT abort."""
    def _bad_seg(system, user, max_tokens):
        if "ARGUMENT SECTIONS" in system:
            return "not json"
        if "PROFIL" in system:
            return "Ein Profil."
        return json.dumps({"section_title": "OK", "digest": "- ein Punkt", "terms": []}, ensure_ascii=False)

    res = kp.process_document(_ESSAY_RAW, _fm(id="essay-fb"), llm=_bad_seg, mode="essay")
    assert "## WISSEN" in res.markdown
    assert res.n_emitted_sections >= 1


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
        if "PROFIL" in system:
            return "Ein Profil."
        return json.dumps({"section_title": "OK", "digest": "- x", "terms": []})

    res = kp.process_document(_RAW, _fm(titel=""), llm=_strict, mode="standard")
    assert calls["biblio"] == 0
    assert "titel: Guidance Note on Something" in res.markdown  # paratext fallback


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
        if "PROFIL" in system:
            return "Ein Profil."
        return json.dumps({"section_title": "OK", "digest": "- x", "terms": []})
    _spy.models_used = ["mammouth/qwen3.7-plus", "openrouter/google/gemini-3-flash-preview"]

    res = kp.process_document(_RAW, _fm(sprache="de"), llm=_spy, mode="standard")

    assert "analyzed_at:" in res.markdown
    assert "sprache: de" in res.markdown
    assert "analysis_lang: en" in res.markdown  # DEFAULT_ANALYSIS_LANG, not "de"
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
    res = kp.process_document(_RAW, _fm(), llm=_stub, mode="standard")
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
