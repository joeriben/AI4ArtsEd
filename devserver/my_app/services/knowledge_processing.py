"""
Knowledge processing (Verdichtung) — raw Docling Markdown -> ONE compact
knowledge file, in the running devserver process.

This is the VERDICHTUNGS-Umbau (BIBLIOTHEK.md §3, revised 2026-07-04): the
library never holds a source document verbatim. Full text is far too much
signal for the model, but a cartoon summary the model already knows at that
resolution is useless too. So every document is *processed* — condensed into a
form pitched at the MIDDLE resolution: below the model's general training
knowledge (keep the concrete numbers, thresholds, age limits, the full
enumerated measures/strategies/steps, the named concepts and the document's own
in-vivo terms, the concrete examples), above a generic abstract (drop the
platitudes any language model would already produce, the marketing/appraisal
register, and the meta-sentences about the document).

SARAH principle: what is DETERMINISTICALLY computable is done first (structure
tree, paratext harvest, Docling-artifact detection); the LLM is aimed narrowly
(one Map call per content-bearing section, one Reduce call for the PROFIL); the
document's own terms are kept in-vivo. No Docling here — the raw Markdown is the
input; this runs in the devserver process. The LLM goes through the platform's
own provider routing (call_chat_helper, role KNOWLEDGE_PROCESSING_MODEL, with
the model->provider fallback chain).

    ┌─ pipeline ──────────────────────────────────────────────────────────┐
    │ 1 parse_structure   deterministic: heading tree + Docling-artifact   │
    │                     filtering (ToC point-leaders, page headers,       │
    │                     acronym lists, image markers)                     │
    │ 2 harvest_paratext  deterministic: title/subtitle/foreword/summary    │
    │ 3 pack + map (LLM)  sections are PACKED into CHAPTER units (~9K chars)│
    │                     and each unit gets ONE call with a HARD word      │
    │                     budget (total ≈ 15% standard / 10% normtext of    │
    │                     the content-bearing raw words) -> {section_title, │
    │                     digest, terms[]} (schema JSON, 1 retry). JSON keys│
    │                     are English (wire contract); analysis LANGUAGE is │
    │                     a target_lang param, default English, not German  │
    │ 4 reduce (LLM)      paratext + unit digests -> PROFIL (~8-12 lines)   │
    │ 5 assemble          deterministic: front-matter + ## PROFIL +         │
    │                     ## WISSEN (### per unit) + ## GLOSSAR (max 40)    │
    │ 6 validate          PROFIL/WISSEN present + emitted; ratio < floor -> │
    │                     FATAL (stub signature); ratio > ceiling / mojibake│
    │                     -> WARN only, file still written                  │
    └──────────────────────────────────────────────────────────────────────┘

Lesson wired in from the first corpus run (2026-07-04): condensing at
SUB-SECTION granularity with per-section percentages aggregates to 50-70%
retention — a German rendition, not a Verdichtung. The unit of condensation is
therefore the CHAPTER, under a document-level word budget named concretely in
every prompt; Mittellage means SELECTING, not paraphrasing. "Vollständig als
Liste" applies to genuine measure/recommendation catalogues only. When budget
and specificity collide, the specifics are sacrosanct and general prose falls.
Legal instruments (mode="normtext") are condensed reference-style (definitions
in-vivo, core state obligations, list/procedure mechanics, community role,
directives essence) — never article-by-article.

The produced file's front-matter schema is UNCHANGED (id, titel, autor, jahr,
sprache, tier, sparten, themen, lizenz, url, status) plus three ADDITIVE
analysis-provenance keys stamped on every successful run (analyzed_at,
analysis_lang, analysis_model -- see process_document); only the BODY form is
new (PROFIL / WISSEN / GLOSSAR instead of CARD / GLOSSARY / DOCUMENT-full-text).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default analysis language: the LLM writes the PROFIL/WISSEN/GLOSSAR content in
# this language unless a caller passes a different `target_lang` explicitly.
# English by platform policy (CLAUDE.md i18n rule: German is data/content, never
# a hardcoded platform assumption) -- analysing an English-language paper into
# German was exactly that bug. The document's own original language is an
# acceptable fallback a caller may choose to pass; it is never assumed here.
DEFAULT_ANALYSIS_LANG = "en"

# Display name for the "Zielsprache" (target-language) slot inside the prompts
# below, keyed by ISO 639-1 code -- the same codes used by the front-matter
# `sprache:` field and the platform's i18n language set (CLAUDE.md: de/en/tr/
# ko/uk/fr). An unlisted code falls back to itself upper-cased: never breaks a
# run, just a plainer label the model still understands fine.
_LANG_DISPLAY_NAMES: Dict[str, str] = {
    "en": "ENGLISH",
    "de": "GERMAN",
    "fr": "FRENCH",
    "tr": "TURKISH",
    "ko": "KOREAN",
    "uk": "UKRAINIAN",
}


def _lang_display(target_lang: str) -> str:
    code = (target_lang or DEFAULT_ANALYSIS_LANG).strip().lower()
    return _LANG_DISPLAY_NAMES.get(code, code.upper())


class ProcessingCancelled(Exception):
    """Raised by process_document when a caller-supplied cancel_check() turns
    true at a unit boundary. The ingest job worker catches it to distinguish an
    operator-requested abort from a genuine failure (BIBLIOTHEK.md §9 curation).
    Carries how many units were already condensed, for the log line."""

    def __init__(self, units_done: int = 0):
        self.units_done = units_done
        super().__init__(f"processing cancelled after {units_done} unit(s)")


# Token estimate (chars/4) — sizing only, no tokenizer needed. Mirrors the
# offline scripts so the two agree on "how big is this".
_CHARS_PER_TOKEN = 4

# A content section shorter than this (chars) is not worth carrying as content —
# it is folded into the paratext sample for the Reduce step instead.
_MIN_SECTION_CHARS = 220
# Paratext-hint sections (foreword/intro/conclusion) are substantive even when
# short; condense them as content down to this lower bar.
_PARATEXT_CONTENT_MIN_CHARS = 120

# Chapter-level Verdichtung units: content sections are PACKED into units of
# roughly this many chars (subsections ride inside their chapter as context).
# Lesson from the first corpus run: verdichten at sub-section granularity
# aggregates to 50-70% retention — the unit must be the CHAPTER, not the
# bullet group.
_PACK_TARGET_CHARS = 9000
# A new top-level chapter starts a new unit once the current unit has this much.
_PACK_MIN_BREAK_CHARS = 3000
# Body cap handed to one Map call (safety bound; units are packed below this).
_MAP_SECTION_CAP = 12000

_REDUCE_SAMPLE_CAP = 8000        # paratext + digests handed to the Reduce call

# Hard document word budget (the core lever against paraphrase-instead-of-
# selection): the compact WISSEN text targets this fraction of the content-
# bearing raw words, distributed over the units proportional to size, and named
# in each Map prompt as a concrete word count.
_BUDGET_RATIO = {
    "standard": 0.15,   # guidance/frameworks: ~12-18% of content-bearing raw
    "normtext": 0.10,   # legal instrument (convention): ~8-12%, reference-style
    # Argumentative Fachaufsatz: a dense short essay carries far more relative
    # substance per word than a report — the argument IS the content, so a
    # tighter cut would shave the reasoning. Target BAND 15-30% (BIBLIOTHEK.md
    # §3.5). The budget RATIO here sits at the band floor because the model
    # reliably overshoots a per-unit word budget (~2x); calibrated on the Mörsch
    # pilot so the OUTPUT lands inside 15-30% rather than the instruction.
    "essay": 0.15,      # short argumentative essay: budget floor -> output ~15-30%
}
_MIN_UNIT_BUDGET_WORDS = 60      # floor so tiny units still carry their specifics

# --- Text-type detection (deterministic, BIBLIOTHEK.md §3.5) ----------------
# An argumentative Fachaufsatz has almost no structural scaffolding: the whole
# argument runs as continuous prose under one or two headings (the Mörsch essay
# has 3 content-bearing headings and ~60 lines). Heading-based sectioning then
# produces 2 amorphous WISSEN blocks and the argument is flattened. When a
# document is heading-sparse OR short (and is not a legal instrument), it is
# processed in `essay` mode instead: the LLM segments the argument, not the
# heading tree. Thresholds are constants so the log can name them.
_ESSAY_MAX_CONTENT_HEADINGS = 4   # fewer content-bearing headings than this -> essay-eligible
_ESSAY_MAX_RAW_LINES = 800        # OR shorter than this many raw lines -> essay-eligible

# Essays are segmented by the LLM into this many argument sections (a whole
# short essay fits one context window, so the segmenter sees the full text).
_ESSAY_MIN_SEGMENTS = 5
_ESSAY_MAX_SEGMENTS = 10

# Glossary curation: at most this many terms survive per document (order of
# first appearance). The Map prompt additionally limits per-unit terms. Essays
# are short and get a tighter cap: a curated concept index, not a 40-term
# vocabulary list bolted onto a 20 KB text.
_GLOSSARY_DOC_CAP = 40
_ESSAY_GLOSSARY_DOC_CAP = 10

# Compression ratio (compact / raw) has TWO bounds with different jobs and
# different consequences. Making both FATAL was a design error: a floor
# breach and a ceiling breach are not the same kind of failure.
#
# FLOOR = a SAFETY bound; stays FATAL. It is the stub signature -- the
# provider-outage incident this guard exists for produced a 558-char
# placeholder at ratio 1.3%, and that is what a ratio this low actually
# means: the substance vanished. (The structural checks above -- missing
# PROFIL/WISSEN, zero emitted WISSEN subsections, the PROFIL placeholder --
# already catch a stub on their own; the floor is corroborating evidence,
# never the sole detector.)
#
# CEILING = a QUALITY signal, ADVISORY only (warn, still write) -- never
# fatal. An analysis carries irreducible FIXED overhead (YAML front-matter,
# three ## headings, per-section ### headings, <!-- quelle: --> anchors, a
# glossary) of roughly 1.5-2.5 kB regardless of source length. For a short
# source that overhead alone can exceed the ceiling (e.g.
# klapp-klaus-spielanleitung-printable at 121%): the ratio then measures
# overhead, not condensation, so the ceiling is structurally unreachable-
# under for such a document and must never be able to block a write. A
# breach can at most mean the model paraphrased instead of selecting
# (Mittellage violation), never that the document is unusable -- the lever
# against paraphrase is budget_words (_BUDGET_RATIO/_map_unit above), not
# this guard. Making the ceiling FATAL blocked real documents forever and,
# since a blocked run can also never be RE-analysed, permanently froze
# their old (possibly worse) output in place -- itself a form of data loss.
#
# Essays keep a higher share of their (small) raw substance, so both bounds
# are wider.
_RATIO_FLOOR = 0.05
_RATIO_CEILING = 0.25
_ESSAY_RATIO_FLOOR = 0.10
_ESSAY_RATIO_CEILING = 0.45


def _est_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ===========================================================================
# 1) Deterministic structure parsing + Docling-artifact filtering
# ===========================================================================

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# A leftover ingest context marker, in case a .raw.md ever carries one.
_CONTEXT_LINE_RE = re.compile(r"^\s*<!--\s*context:.*?-->\s*$", re.MULTILINE)

# Table-of-contents leader lines: "Introduction .......... 7" or "1.2 Aims 12"
# (dot leaders, or a heading-ish line ending in a bare page number). Docling
# emits these from the printed ToC and they carry no content.
_TOC_DOTLEADER_RE = re.compile(r"\.{4,}\s*\d{1,4}\s*$")
_TOC_TRAILING_PAGE_RE = re.compile(r"^\s*[\dIVXLC]*[\.\)]?\s+.{2,80}?\s+\d{1,4}\s*$")

# A markdown table row that is really a ToC (cells + a trailing page number),
# e.g. "| Introduction | ... | 7 |". Docling frequently tabularises the ToC.
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")

# Acronym / abbreviation list lines, e.g. "ICH   Intangible Cultural Heritage"
# or "AI — Artificial Intelligence". Only treated as an artifact when a run of
# them clusters (see _is_acronym_block).
_ACRONYM_LINE_RE = re.compile(r"^\s*([A-Z]{2,6})\s*[—:–-]?\s+[A-Z].{2,}$")

# Image / figure placeholder markers Docling injects.
_IMAGE_MARKER_RE = re.compile(r"^\s*<!--\s*image\s*-->\s*$", re.IGNORECASE)


@dataclass
class Section:
    """One heading-delimited section of the raw document."""
    level: int
    heading: str
    path: str                    # "Chapter > Section"
    body: str                    # cleaned body text (artifacts stripped)

    @property
    def chars(self) -> int:
        return len(self.body)


@dataclass
class Paratext:
    title: str = ""
    subtitle: str = ""
    # (label, text) pairs for foreword / summary / abstract / preamble / closing
    blocks: List[Tuple[str, str]] = field(default_factory=list)

    def as_sample(self, cap: int) -> str:
        parts: List[str] = []
        if self.title:
            parts.append(f"TITEL: {self.title}")
        if self.subtitle:
            parts.append(f"UNTERTITEL: {self.subtitle}")
        for label, text in self.blocks:
            parts.append(f"[{label}]\n{text}")
        sample = "\n\n".join(parts)
        return sample[:cap]


# Headings whose content is paratext (position/self-claim of the document),
# matched case-insensitively as a substring of the heading.
_PARATEXT_HEADING_HINTS = (
    "foreword", "preface", "vorwort", "geleitwort", "avant-propos",
    "summary", "executive summary", "zusammenfassung", "abstract",
    "introduction", "einleitung", "einführung", "einfuehrung", "préambule",
    "preamble", "präambel", "praeambel",
    "conclusion", "schluss", "schlussbemerkung", "fazit", "ausblick",
    "the way forward", "moving forward",
)

# Headings that are pure front/back-matter scaffolding — skipped entirely (never
# a content section, never paratext).
_SKIP_HEADING_HINTS = (
    "table of contents", "contents", "inhalt", "inhaltsverzeichnis",
    "list of abbreviations", "abbreviations", "acronyms", "abkürzungen",
    "abkuerzungen", "glossary of terms",
    "list of boxes", "list of figures", "list of tables", "list of acronyms",
    "abbildungsverzeichnis", "tabellenverzeichnis",
    "acknowledgements", "acknowledgments", "danksagung", "impressum",
    "imprint", "colophon", "copyright", "credits", "bibliography",
    "references", "literaturverzeichnis", "annex", "appendix", "anhang",
    "index", "endnotes", "notes",
)


def _norm_heading(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower())


def _first_raw_heading(raw_md: str) -> str:
    """The document's FIRST heading in raw order that is not front-matter
    scaffolding (skip-matter). Used as a title fallback: unlike the parsed
    sections, this survives even when the title heading has an empty body (a
    title line immediately followed by a byline heading). Returns '' if none."""
    raw_md = _CONTEXT_LINE_RE.sub("", raw_md)
    for line in raw_md.splitlines():
        m = _HEADING_RE.match(line)
        if not m:
            continue
        heading = m.group(2).strip()
        if _heading_matches(heading, _SKIP_HEADING_HINTS):
            continue
        return heading
    return ""


def _heading_matches(heading: str, hints: Tuple[str, ...]) -> bool:
    hn = _norm_heading(heading)
    return any(hint in hn for hint in hints)


def _squeeze_pdf_spaces(text: str) -> str:
    """Docling text extracted from justified PDF columns often carries runs of
    spaces between words (and inside words, letter-spacing). Collapse runs of
    2+ spaces to one, per line, without touching newlines/paragraph breaks."""
    out_lines = []
    for line in text.splitlines():
        out_lines.append(re.sub(r"[ \t]{2,}", " ", line).rstrip())
    return "\n".join(out_lines)


def _is_acronym_block(paragraph: str) -> bool:
    """A paragraph is an acronym/abbreviation table when most of its non-empty
    lines look like '<ACRONYM> <Expansion>'. Requires at least 3 such lines so
    an ordinary sentence starting with an initialism is not misclassified."""
    lines = [ln for ln in paragraph.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    hits = sum(1 for ln in lines if _ACRONYM_LINE_RE.match(ln))
    return hits >= max(3, int(0.6 * len(lines)))


def _is_toc_block(paragraph: str) -> bool:
    """A paragraph is a table-of-contents fragment when most of its lines are
    dot-leader lines, tabularised ToC rows, or heading-then-page-number lines."""
    lines = [ln for ln in paragraph.splitlines() if ln.strip()]
    if not lines:
        return False
    hits = 0
    for ln in lines:
        if (_TOC_DOTLEADER_RE.search(ln)
                or (_TABLE_ROW_RE.match(ln) and re.search(r"\d{1,4}\s*\|\s*$", ln))
                or _TOC_TRAILING_PAGE_RE.match(ln)):
            hits += 1
    return hits >= max(2, int(0.6 * len(lines)))


def _clean_body(raw_body: str, repeated_lines: set) -> str:
    """Strip Docling artifacts from a section body:
      - image markers and HTML comments
      - running page headers/footers (lines that repeat across the document)
      - ToC fragments and acronym-table paragraphs
    then squeeze PDF space runs. Paragraph structure is preserved."""
    body = _IMAGE_MARKER_RE.sub("", raw_body)
    body = _HTML_COMMENT_RE.sub("", body)

    # Drop lines that repeat verbatim across the doc (running headers/footers)
    # and bare page-number lines.
    kept_lines: List[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and stripped in repeated_lines:
            continue
        if re.fullmatch(r"[-–—\s]*\d{1,4}[-–—\s]*", stripped):
            continue  # a bare page number (optionally dash-wrapped)
        kept_lines.append(line)
    body = "\n".join(kept_lines)

    # Drop whole paragraphs that are ToC or acronym tables.
    paragraphs = re.split(r"\n\s*\n", body)
    kept_paras = [p for p in paragraphs
                  if p.strip() and not _is_toc_block(p) and not _is_acronym_block(p)]
    body = "\n\n".join(kept_paras)

    return _squeeze_pdf_spaces(body).strip()


def _find_repeated_lines(md: str, min_repeats: int = 4, min_len: int = 8) -> set:
    """Lines that recur many times across the document are running page
    headers/footers (e.g. the document title stamped on every page). Return the
    set of such lines so _clean_body can drop them. Short lines and heading
    lines are never treated as repeats."""
    counts: Dict[str, int] = {}
    for line in md.splitlines():
        s = line.strip()
        if len(s) < min_len or _HEADING_RE.match(line):
            continue
        counts[s] = counts.get(s, 0) + 1
    return {s for s, n in counts.items() if n >= min_repeats}


def parse_structure(raw_md: str) -> Tuple[Paratext, List[Section], List[Section]]:
    """Deterministically parse a raw Docling Markdown into
        (paratext, content_sections, all_sections_for_ratio).

    content_sections are the substantive, content-bearing sections (skip-matter
    and paratext excluded, and anything too small to warrant its own Map call
    folded away). all_sections is every non-skip section kept for the raw-size /
    compression accounting.
    """
    raw_md = _CONTEXT_LINE_RE.sub("", raw_md)
    repeated = _find_repeated_lines(raw_md)

    # Split at ATX headings into (level, heading, path, raw_body).
    lines = raw_md.splitlines()
    stack: List[str] = []
    entries: List[Dict[str, Any]] = []
    cur = {"level": 0, "heading": "", "path": "", "body_lines": []}

    def _flush():
        body = "\n".join(cur["body_lines"])
        entries.append({"level": cur["level"], "heading": cur["heading"],
                        "path": cur["path"], "raw_body": body})

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            _flush()
            level = len(m.group(1))
            heading = m.group(2).strip()
            stack = stack[: max(0, level - 1)]
            stack.append(heading)
            cur = {"level": level, "heading": heading,
                   "path": " > ".join(stack), "body_lines": []}
        else:
            cur["body_lines"].append(line)
    _flush()

    paratext = Paratext()
    content: List[Section] = []
    all_kept: List[Section] = []

    # The leading entry (level 0, no heading) is the pre-title preamble; its body
    # plus the first H1 give us title/subtitle.
    for e in entries:
        heading = e["heading"]
        if heading and _heading_matches(heading, _SKIP_HEADING_HINTS):
            continue  # front/back-matter scaffolding: drop entirely

        cleaned = _clean_body(e["raw_body"], repeated)

        # Title / subtitle: first H1 becomes the title; a short H2 right under it
        # (before any real content) becomes the subtitle.
        if not paratext.title and e["level"] == 1 and heading:
            paratext.title = heading
            if cleaned and len(cleaned) < 200 and "\n" not in cleaned.strip():
                paratext.subtitle = cleaned.strip()
                cleaned = ""

        if not cleaned:
            continue

        sec = Section(level=e["level"], heading=heading or "(Präambel)",
                      path=e["path"] or (heading or "(Präambel)"), body=cleaned)
        all_kept.append(sec)

        if heading and _heading_matches(heading, _PARATEXT_HEADING_HINTS):
            paratext.blocks.append((heading, cleaned[:_MAP_SECTION_CAP]))
            # Introductions/conclusions are ALSO substantive and often carry the
            # self-claim plus framing numbers — condense them as content sections
            # even when short (a lower bar than an ordinary body section, so a
            # tight foreword's concrete facts reach WISSEN, not only the PROFIL).
            if len(cleaned) >= _PARATEXT_CONTENT_MIN_CHARS:
                content.append(sec)
            continue

        if not heading and len(cleaned) >= _MIN_SECTION_CHARS:
            # Pre-heading preamble with real body -> paratext AND content.
            paratext.blocks.append(("Präambel", cleaned[:_MAP_SECTION_CAP]))
            content.append(sec)
            continue

        if len(cleaned) >= _MIN_SECTION_CHARS:
            content.append(sec)
        else:
            # Too small for its own Map call; still counts for the ratio and is
            # worth showing the Reduce step as context.
            paratext.blocks.append((heading or "(klein)", cleaned))

    return paratext, content, all_kept


# ===========================================================================
# 2b) Text-type detection: standard / normtext / essay  (deterministic)
# ===========================================================================

def _count_content_headings(all_kept: List[Section]) -> int:
    """How many content-bearing headings survived structure parsing (skip-matter
    and paratext scaffolding already removed by parse_structure). The pre-title
    preamble section carries the synthetic '(Präambel)' heading and does not
    count as a real heading. This is the structural-sparseness signal."""
    n = 0
    for s in all_kept:
        h = (s.heading or "").strip()
        if not h or h == "(Präambel)":
            continue
        n += 1
    return n


def detect_mode(raw_md: str, all_kept: List[Section],
                explicit: Optional[str] = None) -> Tuple[str, str]:
    """Decide the processing mode for a document, returning (mode, reason).

    An explicit mode (given by the caller, e.g. 'normtext' for a known legal
    instrument) is honoured verbatim — detection only runs for mode 'auto' or an
    unset/unknown mode. A legal instrument is NEVER downgraded to essay.

    The essay signal (BIBLIOTHEK.md §3.5) is deterministic: a document with
    FEWER than _ESSAY_MAX_CONTENT_HEADINGS content-bearing headings OR shorter
    than _ESSAY_MAX_RAW_LINES raw lines is an argumentative Fachaufsatz whose
    argument runs as continuous prose — heading-based sectioning would flatten
    it into 1-2 amorphous WISSEN blocks. Everything else stays 'standard'.
    """
    if explicit in ("standard", "normtext", "essay"):
        return explicit, f"explicit mode '{explicit}'"

    n_headings = _count_content_headings(all_kept)
    n_lines = len(raw_md.splitlines())
    heading_sparse = n_headings < _ESSAY_MAX_CONTENT_HEADINGS
    short_doc = n_lines < _ESSAY_MAX_RAW_LINES

    if heading_sparse or short_doc:
        why = []
        if heading_sparse:
            why.append(f"{n_headings} inhaltstragende Headings < {_ESSAY_MAX_CONTENT_HEADINGS}")
        if short_doc:
            why.append(f"{n_lines} Rohzeilen < {_ESSAY_MAX_RAW_LINES}")
        return "essay", f"essay ({', '.join(why)})"

    return "standard", f"standard ({n_headings} Headings, {n_lines} Zeilen)"


# ===========================================================================
# 3+4) LLM Map / Reduce  (schema-forced JSON, provider-routed)
# ===========================================================================

# A caller-supplied LLM function: (system, user, max_tokens) -> content str or
# None. max_tokens is Optional[int]; None means NO CAP (platform rule: hard
# max_tokens caps are forbidden -- see _map_unit/_reduce_profile/_segment_essay,
# which all pass None now).
LlmFn = Callable[[str, str, Optional[int]], Optional[str]]


def default_llm_fn(temperature: float = 0.2) -> LlmFn:
    """The production LLM path: call_chat_helper with role
    KNOWLEDGE_PROCESSING_MODEL so the model->provider fallback chain applies.
    Imported lazily to keep this module import-safe in offline/test contexts.

    The returned callable also exposes `.models_used` (List[str]): the distinct
    models that have ACTUALLY served a call so far, in first-seen order --
    call_chat_helper's own `model_used` (the post-fallback candidate that
    really answered), never the configured KNOWLEDGE_PROCESSING_MODEL slot. A
    silent model->provider fallback mid-run (see call_chat_helper's two-stage
    chain) can diverge from the configured slot with no other visible sign.
    process_document reads this attribute back after its Map/Reduce/segmenter
    calls to stamp `analysis_model` in the front-matter (see process_document)."""
    from my_app.routes.chat_routes import call_chat_helper

    models_used: List[str] = []

    def _fn(system: str, user: str, max_tokens: Optional[int] = None) -> Optional[str]:
        try:
            result = call_chat_helper(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=temperature,
                max_tokens=max_tokens,
                role="KNOWLEDGE_PROCESSING_MODEL",
            )
        except Exception as e:  # noqa: BLE001 - degrade to a caller-visible None
            logger.warning("[KNOWLEDGE-PROC] LLM call failed: %s", e)
            return None
        if isinstance(result, dict):
            # Additive, never guessed: call_chat_helper already reports the
            # candidate that actually served the request (post-fallback).
            served = result.get("model_used")
            if served and served not in models_used:
                models_used.append(served)
            return result.get("content")
        return result

    _fn.models_used = models_used  # type: ignore[attr-defined]
    return _fn


# Reasoning models may wrap the answer in <think>…</think>; strip it (an unclosed
# block means the budget was eaten before the answer — treat as unusable).
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>", re.IGNORECASE)


def _strip_think(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = _THINK_BLOCK_RE.sub("", text).strip()
    if _THINK_OPEN_RE.search(cleaned):
        return None
    return cleaned or None


def _extract_json_object(text: Optional[str]) -> Optional[dict]:
    """Best-effort extraction of ONE JSON object from an LLM reply (handles
    ```json fences and leading prose). Returns the dict or None."""
    import json
    text = _strip_think(text)
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    raw = (fenced.group(1) if fenced else text).strip()
    oi, oj = raw.find("{"), raw.rfind("}")
    if 0 <= oi < oj:
        try:
            return json.loads(raw[oi: oj + 1])
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# Chapter-level packing: content sections -> Verdichtungs-Einheiten
# ---------------------------------------------------------------------------

@dataclass
class Unit:
    """One chapter-level Verdichtungs-Einheit: consecutive content sections
    packed together; subsection headings ride inside the body as context."""
    heading: str                 # the leading chapter heading of the unit
    body: str                    # concatenated section bodies with sub-headings
    source_span: str             # "first heading … last heading" review anchor

    @property
    def chars(self) -> int:
        return len(self.body)


def _top_ancestor(path: str) -> str:
    return (path or "").split(" > ")[0].strip()


def _pack_units(sections: List[Section]) -> List[Unit]:
    """Greedy chapter packing: walk the content sections in order and pack them
    into units of ~_PACK_TARGET_CHARS. A change of top-level chapter starts a
    new unit once the current one carries at least _PACK_MIN_BREAK_CHARS, so
    units align with chapters where chapters are big enough to stand alone and
    merge small front/back chapters instead of spawning micro-units."""
    units: List[Unit] = []
    buf: List[Section] = []
    buf_chars = 0

    def _emit():
        nonlocal buf, buf_chars
        if not buf:
            return
        parts: List[str] = []
        for s in buf:
            parts.append(f"### {s.heading}\n{s.body}")
        first, last = buf[0].heading, buf[-1].heading
        span = first if first == last else f"{first} … {last}"
        units.append(Unit(heading=_top_ancestor(buf[0].path) or buf[0].heading,
                          body="\n\n".join(parts), source_span=span))
        buf, buf_chars = [], 0

    prev_anchor: Optional[str] = None
    for s in sections:
        anchor = _top_ancestor(s.path)
        chapter_changed = prev_anchor is not None and anchor != prev_anchor
        if buf and (
            buf_chars + s.chars > _PACK_TARGET_CHARS
            or (chapter_changed and buf_chars >= _PACK_MIN_BREAK_CHARS)
        ):
            _emit()
        buf.append(s)
        buf_chars += s.chars
        prev_anchor = anchor
    _emit()
    return units


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


# The Mittellage rule — the single most important instruction of the whole
# rebuild. Kept as a named constant so the map prompt and any future reuse share
# one wording (and a test can assert its presence). Mittellage means SELECTING,
# not paraphrasing: what carries specificity survives, general prose falls.
def _mittellage_rule(lang_name: str) -> str:
    return (
        "Preserve the resolution BELOW the model's general training "
        "knowledge — that means SELECTING, not paraphrasing. ONLY carriers "
        "of specificity survive: concrete numbers, thresholds and age "
        "limits; GENUINE measure/recommendation catalogues given in full as "
        "a list (only these — not just any enumeration); named concepts and "
        "the document's own terms (in-vivo, kept in their original wording, "
        "with a brief gloss in " + lang_name + "); concrete examples and "
        "named cases with name/year. EVERYTHING ELSE IS DROPPED: platitudes "
        "any language model would produce anyway (e.g. \"AI offers "
        "opportunities and risks\"); derivations and justificatory prose; "
        "evaluative and promotional language; meta-sentences about the "
        "document. Keep to the stated word budget. If the budget and "
        "specificity collide, the specifics are sacred and the general "
        "prose is what gives way."
    )


def _map_system(target_lang: str = DEFAULT_ANALYSIS_LANG) -> str:
    lang_name = _lang_display(target_lang)
    return (
        f"Write your entire response in {lang_name}. Preserve the "
        "document's own technical terms and key concepts verbatim, in "
        "their original wording. You are condensing one chapter of a "
        "scholarly text for an arts-education knowledge library. Register: "
        "sober and factual, for professional arts educators. "
        + _mittellage_rule(lang_name) +
        "\n\nTERMS: at most 3 per chapter, only genuinely load-bearing, "
        "document-specific terms (not a vocabulary list, no general terms "
        "such as \"UNESCO\" or \"AI\").\n\n"
        "Respond ONLY as a JSON object with exactly these keys:\n"
        "{\"section_title\": <the chapter's title, short>, "
        "\"digest\": <the condensed version; Markdown allowed, lists as "
        "\"- \" lines>, "
        "\"terms\": [{\"term\": <the document's own term, in the original>, "
        "\"definition\": <one sentence of explanation, in " + lang_name + ">}]}. "
        "terms may be empty. No text outside the JSON object."
    )

# Extra system block for legal instruments (conventions etc.): reference-style
# condensation, never article-by-article paraphrase.
_NORMTEXT_BLOCK = (
    "\n\nSPECIAL CASE NORMTEXT: this text is a legal instrument (a "
    "convention/agreement with articles and implementation provisions). Do "
    "NOT paraphrase it article by article. Condense exclusively onto: (a) "
    "core concepts and definitions in the document's own wording (in-vivo, "
    "e.g. the definitional articles), (b) the core obligations of the "
    "states parties, (c) the mechanics of the lists/procedures/bodies, (d) "
    "the role of communities/custodians, (e) the essence of the "
    "implementation provisions. Procedural and final provisions "
    "(ratification, entry into force, languages, depositary) are dropped "
    "or dispatched in one sentence. The result is a REFERENCE digest, not "
    "continuous prose."
)


# ---------------------------------------------------------------------------
# ESSAY MODE — argument-preserving condensation of a Fachaufsatz
# ---------------------------------------------------------------------------
# The preservation rules for an argumentative essay REPLACE the Mittellage
# policy rules (which are tuned for measure/recommendation catalogues). Here the
# argument itself is the substance: what the text claims, what it sets itself
# against, how it justifies each step. A budget-driven "select the specifics"
# cut would sever exactly the connective reasoning that makes an essay an essay.
def _essay_preserve_rule(lang_name: str) -> str:
    return (
        "This is an ARGUMENTATIVE scholarly essay, not a report and not a "
        "catalogue. The LINE OF ARGUMENT itself is the substance. "
        "Preserve:\n"
        "(a) the LINE OF ARGUMENT — what the text claims, what it sets "
        "itself AGAINST, and HOW it argues (thesis -> demarcation -> step); "
        "the logical movement must remain traceable in the condensed text, "
        "not just the results;\n"
        "(b) central DISTINCTIONS and conceptual work (document-specific "
        "terms in-vivo, in the original, with a brief gloss in "
        + lang_name + ");\n"
        "(c) the author's SELF-POSITIONING and reflexivity wherever it "
        "carries the argument (e.g. \"I have ... struck through\", "
        "acknowledged difficulties, her own standpoint);\n"
        "(d) concrete EXAMPLES and case material WITH their function in "
        "the argument (not the example alone, but what it serves);\n"
        "(e) COMPLETE criteria/indicator/feature lists — if the text "
        "presents a list of indicators, criteria or dimensions, reproduce "
        "it IN FULL and in the original's order; drop NO item.\n"
        "What remains FORBIDDEN: platitudes any language model would "
        "produce anyway; meta-sentences about the document (\"The text "
        "addresses...\", \"The author argues that...\" as mere paraphrase); "
        "blurb and evaluative language. Write the condensed SUBJECT "
        "MATTER, not a description of the text."
    )


def _essay_map_system(target_lang: str = DEFAULT_ANALYSIS_LANG) -> str:
    lang_name = _lang_display(target_lang)
    return (
        f"Write your entire response in {lang_name}. Preserve the "
        "document's own technical terms and key concepts verbatim, in "
        "their original wording. You are condensing ONE argument section "
        "of an arts-education scholarly essay for a knowledge library. "
        "Register: sober and factual, for professional arts educators. "
        + _essay_preserve_rule(lang_name) +
        "\n\nWORD BUDGET (binding): the stated word budget is a HARD "
        "ceiling, not a guideline — do not exceed it. Condensing means "
        "SELECTING: render the argument step in a few dense sentences, NO "
        "decorative prose, NO repetition, NO paraphrase in full "
        "paragraphs. Only for a criteria/indicator list that must be "
        "reproduced IN FULL (rule e) may the budget be exceeded for the "
        "list items — the surrounding running text is then all the more "
        "sparing.\n\n"
        "TERMS: at most 3 per section, only genuinely load-bearing, "
        "document-specific terms (not a vocabulary list, no general "
        "terms).\n\n"
        "Respond ONLY as a JSON object with exactly these keys:\n"
        "{\"section_title\": <working title of the section, short>, "
        "\"digest\": <the condensed version; Markdown allowed, lists as "
        "\"- \" lines>, "
        "\"terms\": [{\"term\": <the document's own term, in the original>, "
        "\"definition\": <one sentence of explanation, in " + lang_name + ">}]}. "
        "terms may be empty. No text outside the JSON object."
    )

# The essay segmenter's job: read the WHOLE essay (short enough for one window)
# and return an ordered outline of 5-10 ARGUMENT sections — each a
# target-language working title (Defect 1a -- never hardcoded German) plus the
# line range it spans in the numbered text. The line ranges let the
# deterministic code slice the raw text back into units; the titles become the
# WISSEN ### headings and the review anchors.
def _essay_segment_system(target_lang: str = DEFAULT_ANALYSIS_LANG) -> str:
    lang_name = _lang_display(target_lang)
    return (
        f"Write the section titles in {lang_name}. You are segmenting an "
        "argumentative scholarly essay into its ARGUMENT SECTIONS. The "
        "text below is marked with line numbers ([12] etc.). Break the "
        "LINE OF THOUGHT (not the layout) into "
        f"{_ESSAY_MIN_SEGMENTS} to {_ESSAY_MAX_SEGMENTS} consecutive, "
        "gapless sections that together cover the entire content-bearing "
        "text (notes/footnotes and the bibliography may be omitted or "
        "combined into ONE section if they carry an argument of their "
        "own). Each section bundles one coherent argument step (e.g. "
        "problem framing, conceptual clarification, thesis, demarcation, "
        "criteria framework, application, self-critique/outlook).\n\n"
        "Respond ONLY as a JSON object:\n"
        "{\"sections\": [{\"title\": <short working title of the argument "
        "step, in " + lang_name + ">, \"von\": <first line number>, \"bis\": "
        "<last line number>}]}. "
        "The sections must be in text order and must not overlap. No text "
        "outside the JSON object."
    )


@dataclass
class EssaySegment:
    """One LLM-identified argument section: target-language working title (see
    target_lang / DEFAULT_ANALYSIS_LANG, Defect 1a) + the raw text it spans
    (sliced deterministically from the numbered essay)."""
    titel: str
    body: str
    von: int
    bis: int

    @property
    def chars(self) -> int:
        return len(self.body)


def _number_lines(text: str) -> str:
    """Prefix every line with its 1-based number in [n] form, for the segmenter
    to reference. Mirrors the slicing in _slice_lines (1-based, inclusive)."""
    return "\n".join(f"[{i}] {ln}" for i, ln in enumerate(text.splitlines(), 1))


def _slice_lines(text: str, von: int, bis: int) -> str:
    """Inclusive 1-based line slice [von, bis], clamped to the text bounds."""
    lines = text.splitlines()
    n = len(lines)
    a = max(1, min(von, n))
    b = max(a, min(bis, n))
    return "\n".join(lines[a - 1:b])


def _segment_essay(raw_md: str, llm: LlmFn,
                   target_lang: str = DEFAULT_ANALYSIS_LANG) -> Optional[List[EssaySegment]]:
    """One LLM pre-call: hand the WHOLE numbered essay to the segmenter and parse
    its outline into ordered EssaySegments (title + sliced body). Returns None on
    a hard miss (no valid JSON, no usable segments) so the caller can fall back
    to heading-based packing. Line ranges are honoured verbatim; overlaps are
    tolerated (the slices simply overlap), gaps are tolerated (some raw lines go
    to no segment — acceptable for an essay whose paratext is thin). `target_lang`
    (default DEFAULT_ANALYSIS_LANG) is the language the segment titles are
    written in -- never hardcoded German."""
    numbered = _number_lines(raw_md)
    # The whole essay must fit one window; guard with a generous cap anyway.
    body = numbered[:60000]
    user = (
        "Segment the following essay into its argument sections "
        "(line numbers in square brackets):\n\n" + body
    )
    system = _essay_segment_system(target_lang)
    # No max_tokens cap (platform rule: hard caps forbidden).
    obj = _extract_json_object(llm(system, user, None))
    if obj is None:
        repair = user + (
            "\n\n---\nYour last answer was not valid JSON. Respond NOW "
            "ONLY with {\"sections\":[{\"title\":…,\"von\":…,\"bis\":…}]}."
        )
        obj = _extract_json_object(llm(system, repair, None))
    if obj is None:
        return None

    raw_segs = obj.get("sections")
    if not isinstance(raw_segs, list) or not raw_segs:
        return None

    segments: List[EssaySegment] = []
    for it in raw_segs[:_ESSAY_MAX_SEGMENTS]:
        if not isinstance(it, dict):
            continue
        titel = str(it.get("title", "") or "").strip()
        try:
            von = int(it.get("von"))
            bis = int(it.get("bis"))
        except (TypeError, ValueError):
            continue
        sliced = _slice_lines(raw_md, von, bis).strip()
        if not titel or len(sliced) < _MIN_SECTION_CHARS:
            continue
        segments.append(EssaySegment(titel=titel, body=sliced, von=von, bis=bis))

    return segments or None


def _units_from_segments(segments: List[EssaySegment]) -> List[Unit]:
    """Wrap the argument segments as Units so the existing Map machinery runs
    unchanged. In essay mode the review anchor (source_span) is the LLM working
    title of the segment — NOT a raw heading like 'Von Carmen Mörsch' (the whole
    reason the old output produced two anchor-collided blocks)."""
    return [
        Unit(heading=s.titel, body=s.body, source_span=s.titel)
        for s in segments
    ]


@dataclass
class SectionDigest:
    abschnitt_de: str
    verdichtung: str
    begriffe: List[Dict[str, str]]
    source_heading: str
    missing: bool = False


def _map_unit(unit: Unit, budget_words: int, llm: LlmFn,
              mode: str = "standard",
              target_lang: str = DEFAULT_ANALYSIS_LANG) -> SectionDigest:
    """One Map call per unit (chapter unit in standard/normtext, argument segment
    in essay mode), with ONE repair retry on a JSON miss. On a second miss the
    unit is recorded MISSING (the run does not abort). The concrete word budget
    is the enforcement lever; in essay mode the argument-preservation prompt
    replaces the Mittellage catalogue rules. `target_lang` (default
    DEFAULT_ANALYSIS_LANG) is the language the digest itself is written in --
    never hardcoded German; in-vivo terms stay in the document's own wording
    regardless."""
    if mode == "essay":
        system = _essay_map_system(target_lang)
    else:
        system = _map_system(target_lang) + (_NORMTEXT_BLOCK if mode == "normtext" else "")
    body = unit.body[:_MAP_SECTION_CAP]
    user = (
        f"Chapter: \"{unit.heading}\".\n"
        f"WORD BUDGET for the condensation: at most ~{budget_words} words.\n\n"
        f"{body}"
    )
    # No max_tokens cap (platform rule: hard caps forbidden -- a reasoning model
    # spends reasoning tokens out of that budget, which truncated the PROFIL
    # mid-word at cap=400; see default_llm_fn/call_chat_helper). The WORD budget
    # above is the actual enforcement lever, not a token ceiling.
    obj = _extract_json_object(llm(system, user, None))
    if obj is None:
        # One repair attempt with an explicit reminder.
        repair = user + (
            "\n\n---\nYour last answer was not valid JSON. Respond NOW "
            "ONLY with the JSON object {\"section_title\":…, \"digest\":…, "
            "\"terms\":[…]}, with no other text. Keep to the word budget."
        )
        obj = _extract_json_object(llm(system, repair, None))

    if obj is None:
        logger.warning("[KNOWLEDGE-PROC] unit MISSING (bad JSON x2): %s", unit.heading)
        return SectionDigest(
            abschnitt_de=unit.heading, verdichtung="", begriffe=[],
            source_heading=unit.source_span, missing=True,
        )

    verdichtung = str(obj.get("digest", "")).strip()
    abschnitt_de = str(obj.get("section_title", "") or unit.heading).strip()
    begriffe: List[Dict[str, str]] = []
    raw_terms = obj.get("terms", [])
    if isinstance(raw_terms, list):
        for it in raw_terms[:3]:  # prompt says <=3; enforce in code too
            if isinstance(it, dict) and str(it.get("term", "")).strip():
                begriffe.append({
                    "term": str(it["term"]).strip(),
                    "definition": str(it.get("definition", "")).strip(),
                })
    missing = not verdichtung
    if missing:
        logger.warning("[KNOWLEDGE-PROC] unit produced empty verdichtung: %s", unit.heading)
    return SectionDigest(
        abschnitt_de=abschnitt_de or unit.heading,
        verdichtung=verdichtung, begriffe=begriffe,
        source_heading=unit.source_span, missing=missing,
    )


def _reduce_system(target_lang: str = DEFAULT_ANALYSIS_LANG) -> str:
    lang_name = _lang_display(target_lang)
    return (
        f"Write your entire response in {lang_name}. Preserve the "
        "document's own technical terms and key concepts verbatim, in "
        "their original wording. You are writing a concise PROFILE of a "
        "scholarly text for an arts-education knowledge library. Factual "
        "register, NO value judgment, NO blurb, NO promotional or "
        "evaluative language. About 8 to 12 lines. Include, TO THE EXTENT "
        "THE TEXT MAKES IT EXPLICIT:\n"
        "- the document's own claim/position (what the text is about);\n"
        "- reference works and its stance toward them (builds on / "
        "extends / contrasts) — only where the text names this itself;\n"
        "- applicability for an arts-education platform (disciplines, "
        "typical situations).\n"
        "Respond as running prose (short paragraphs or \"- \" bullet "
        "points), with no heading."
    )


# Essay PROFIL: shorter (a short essay does not warrant a 12-line profile that
# rivals the WISSEN in size) and pointed at the ARGUMENT, not a topic blurb.
def _reduce_system_essay(target_lang: str = DEFAULT_ANALYSIS_LANG) -> str:
    lang_name = _lang_display(target_lang)
    return (
        f"Write your entire response in {lang_name}. Preserve the "
        "document's own technical terms and key concepts verbatim, in "
        "their original wording. You are writing a concise PROFILE of an "
        "argumentative scholarly essay for an arts-education knowledge "
        "library. Factual register, NO value judgment, NO blurb. AT MOST "
        "5 to 7 lines, ONE paragraph. State briefly: the text's central "
        "THESIS and what it sets itself AGAINST; reference authors/"
        "concepts only where they carry the argument; applicability for "
        "arts education in one sentence. No section-by-section paraphrase, "
        "no listing of every topic — this POSITIONS the text, it does not "
        "summarize it (that is the job of the WISSEN section). Respond as "
        "running prose with no heading."
    )


def _reduce_profile(paratext: Paratext, digests: List[SectionDigest], llm: LlmFn,
                    mode: str = "standard",
                    target_lang: str = DEFAULT_ANALYSIS_LANG) -> str:
    """One Reduce call: paratext + the section digests -> the PROFIL text. In
    essay mode a shorter, argument-pointed profile (so it does not rival the
    WISSEN in size for a short text). `target_lang` defaults to
    DEFAULT_ANALYSIS_LANG (English) -- never a hardcoded assumption."""
    digest_sample = "\n\n".join(
        f"### {d.abschnitt_de}\n{d.verdichtung}" for d in digests if not d.missing
    )
    combined = (paratext.as_sample(_REDUCE_SAMPLE_CAP // 2)
                + "\n\n=== CONDENSED SECTIONS ===\n\n"
                + digest_sample)[:_REDUCE_SAMPLE_CAP]
    user = (
        (f"Title: \"{paratext.title}\".\n\n" if paratext.title else "")
        + "Material (paratext + condensed sections):\n\n" + combined
    )
    system = _reduce_system_essay(target_lang) if mode == "essay" else _reduce_system(target_lang)
    # No max_tokens cap (platform rule; see _map_unit) -- the 400/700-token caps
    # here were the ones that visibly truncated the PROFIL mid-word.
    reply = _strip_think(llm(system, user, None))
    return (reply or "").strip()


# ===========================================================================
# 4b) Bibliographic identification  (schema-forced JSON, provider-routed)
# ===========================================================================
# The filename-as-title problem (2026-07-05): the compact file's `titel:` was
# frequently NOT the work's title but whatever surface line Docling put first —
# an author byline ("Ernst wAgnEr"), a journal/series masthead ("IJRCAAE"), or a
# chapter/section heading of a book excerpt ("Künstlerische Strategien"). A tiny
# extra LLM call reads the document's TITLE PAGE region (and, when present, the
# operator's imprint note) and returns a STRUCTURED bibliographic record, so the
# title/author/year can be set from the real bibliography rather than a stray
# heading. It NEVER invents: unbestimmbar -> null + confidence "low", and the
# caller's own metadata always wins (see process_document).

# How much of the raw text the identifier sees: the title page and front are at
# the top; the imprint/colophon/references head is at the bottom. Sending only
# these two windows keeps the call cheap and pointed at the paratext.
_BIBLIO_HEAD_LINES = 100   # first N content-bearing lines (title page + front)
_BIBLIO_TAIL_LINES = 30    # last N lines (imprint / colophon / references head)

_BIBLIO_SYSTEM = (
    "You are a bibliographic cataloguer. From the beginning (title page) "
    "and the end (imprint/colophon) of a scholarly text, determine the "
    "BIBLIOGRAPHIC record of the work. Target language of the field "
    "values: the title's own original language (do not translate).\n\n"
    "DISTINGUISH strictly — do NOT confuse these with the work's title:\n"
    "- WORK TITLE: the title of the essay/chapter/book itself.\n"
    "- CHAPTER/SECTION HEADING: a heading INSIDE the work (e.g. "
    "\"Künstlerische Strategien\", \"Der Raum\", a question used as an "
    "interstitial heading) — this is NOT the work title.\n"
    "- JOURNAL/SERIES MASTHEAD: the name of the journal or series (e.g. "
    "\"IJRCAAE\", \"International Journal for …\") — this is the SOURCE, "
    "not the title.\n"
    "- BYLINE: the name(s) of the author(s) (e.g. \"Ernst Wagner\", \"Von "
    "Carmen Mörsch\") — this belongs in autoren, NOT in titel.\n"
    "- RUNNING HEAD/COLUMN TITLE: a header/footer repeated on every page — "
    "ignore it.\n\n"
    "EXCERPTS (a chapter of a BOOK): if the text is an excerpt from a "
    "larger BOOK/edited volume (the imprint/note names the book, the text "
    "is only one chapter), then titel is the book's OVERARCHING WORK TITLE "
    "and the CHAPTER NAME goes into the field teil (e.g. titel "
    "\"Kunstlabore: Für mehr Kunst in Schulen!\", teil \"Künstlerische "
    "Strategien\"). teil is EXCLUSIVELY for the chapter/section name of a "
    "book excerpt.\n"
    "IMPORTANT — teil is NOT for journals: for a JOURNAL ARTICLE, teil is "
    "null. Volume/issue/year/page numbers (e.g. \"Vol. 1, No. 1, 90–95\") "
    "are NOT a teil and do not belong in titel — they are part of quelle "
    "(the citation), not of the title.\n\n"
    "Normalise CAPITALISATION: render names and titles in correct casing "
    "(no \"wAgnEr\", no ALL-CAPS RUN, no Docling mis-casing).\n\n"
    "AUTHORS — only what is stated: take the names exactly as they appear "
    "in the text/imprint. DO NOT INVENT first names. If only \"Heisig, "
    "J.\" or \"J. Heisig\" appears, give \"J. Heisig\" (initial), NOT a "
    "made-up full first name. Complete a name only when the full first "
    "name appears VERBATIM in the text.\n\n"
    "LANGUAGE: additionally determine the language the WORK ITSELF is "
    "written in (independent of the language of this instruction), as an "
    "ISO 639-1 code (e.g. \"de\", \"en\", \"fr\", \"tr\", \"ko\", \"uk\"). "
    "If you are unsure, sprache is null — do NOT guess \"de\" as a "
    "default.\n\n"
    "INVENT NOTHING. Whatever you cannot determine with confidence from "
    "the text/imprint is null. If you are unsure about the TITLE, set "
    "confidence \"low\".\n\n"
    "Respond ONLY as a JSON object with exactly these keys:\n"
    "{\"titel\": <work title as a string>, "
    "\"untertitel\": <subtitle or null>, "
    "\"autoren\": [<names as strings, correctly cased>], "
    "\"jahr\": <year of publication as an integer, or null>, "
    "\"quelle\": <journal/book/publisher incl. volume/issue/pages, or "
    "null>, "
    "\"teil\": <ONLY for book excerpts, the chapter name; null for "
    "journals>, "
    "\"sprache\": <ISO 639-1 code of the work's language, e.g. \"de\"/"
    "\"en\", or null>, "
    "\"confidence\": <\"high\" or \"low\">}. "
    "No text outside the JSON object."
)


@dataclass
class BiblioRecord:
    """Structured bibliographic identification of a document (from its title page
    + imprint). Empty/uncertain fields are None; `confidence` is the model's own
    verdict on the TITLE (used by the repair heuristic to avoid clobbering an
    already-good title with a low-confidence guess)."""
    titel: Optional[str] = None
    untertitel: Optional[str] = None
    autoren: List[str] = field(default_factory=list)
    jahr: Optional[int] = None
    quelle: Optional[str] = None
    teil: Optional[str] = None
    sprache: Optional[str] = None
    confidence: str = "low"

    @property
    def composed_titel(self) -> str:
        """The display title: <titel>[. <untertitel>][ — <teil>]. Empty string if
        there is no titel (nothing identified)."""
        base = (self.titel or "").strip()
        if not base:
            return ""
        sub = (self.untertitel or "").strip()
        if sub:
            base = f"{base}. {sub}"
        teil = (self.teil or "").strip()
        if teil:
            base = f"{base} — {teil}"
        return base

    @property
    def autoren_str(self) -> str:
        """Authors joined for the single-scalar `autor:` front-matter field."""
        names = [a.strip() for a in self.autoren if a and a.strip()]
        return ", ".join(names)


# --- Author-Year-Title doc_id composition ------------------------------------
# A fresh operator upload must receive a legible `<author>-<year>-<title>` doc_id
# by default at evaluation instead of a provisional upload slug
# (art105413, aug100500, oa9783839449851-...). DETERMINISTIC (no LLM): it slugs
# the fields identify_bibliographic already resolved. When the author OR the year
# is missing it falls back to a title-only slug.
# Diacritics fold to ASCII to match the existing corpus ids; the title is capped
# at a word boundary with dangling stopwords dropped. knowledge_ingest_service
# applies the result as the .md filename, the `id:` front-matter, and the
# <id>.{pdf,raw.md} original names.
_ID_STOP = {
    "a", "an", "the", "of", "and", "or", "for", "to", "in", "on", "with", "as",
    "at", "by", "der", "die", "das", "und", "von", "zu", "im", "eine", "ein",
    "als", "auf", "mit", "fur",
}


def _id_slug(text: str, cap: int = 60) -> str:
    """Lowercase ASCII slug: fold diacritics, non-alnum -> '-', collapse, cap at
    a word boundary, drop trailing stopwords so no id ends in '-the'/'-und'."""
    if not text:
        return ""
    text = text.replace("ß", "ss")  # eszett -> ss (NFKD leaves it intact)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(text) > cap:
        text = text[:cap].rsplit("-", 1)[0]
    parts = [p for p in text.split("-") if p]
    while parts and parts[-1] in _ID_STOP:
        parts.pop()
    return "-".join(parts)


def _id_surname(name: str) -> str:
    """Slug of the last whitespace token of a personal name
    ('Karola Braun-Wanke' -> 'braun-wanke', 'Kite' -> 'kite')."""
    name = (name or "").strip()
    return _id_slug(name.split()[-1]) if name else ""


def compose_doc_id(titel: str, autor: str, jahr: Any) -> str:
    """Deterministic Author-Year-Title doc_id from resolved bibliographic fields:
    <first-surname>[-and-<second>|-et-al]-<year>-<title-slug> when BOTH a first
    author AND a 4-digit year are present, else a title-only slug.
    `autor` is the comma-joined 'Firstname Lastname' list identify_bibliographic
    emits. Returns '' when there is no title to slug (caller keeps the
    provisional id)."""
    titel = (titel or "").strip()
    # A book excerpt's display title is '<book> — <section>'; the section
    # after the last ' — ' is the concise, distinguishing part.
    sep = " — "
    title_src = titel.rsplit(sep, 1)[-1] if sep in titel else titel
    title_slug = _id_slug(title_src)
    if not title_slug:
        return ""
    ym = re.search(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)", str(jahr or "").strip())
    authors = [a.strip() for a in (autor or "").split(",") if a.strip()]
    if authors and ym:
        first = _id_surname(authors[0])
        if first:
            if len(authors) == 1:
                prefix = first
            elif len(authors) == 2:
                prefix = first + "-and-" + _id_surname(authors[1])
            else:
                prefix = first + "-et-al"
            return prefix + "-" + ym.group(1) + "-" + title_slug
    return title_slug


def _content_head_tail(raw_md: str) -> str:
    """The title-page window handed to the identifier: the first
    _BIBLIO_HEAD_LINES content-bearing lines (blank lines and Docling image/
    comment markers dropped so the budget is spent on real text) plus, when the
    document is long enough to have a distinct tail, the last _BIBLIO_TAIL_LINES
    raw lines (imprint / colophon / references head). Headings are kept — the
    title itself is usually a heading."""
    raw_md = _CONTEXT_LINE_RE.sub("", raw_md)
    kept: List[str] = []
    for line in raw_md.splitlines():
        s = line.strip()
        if not s:
            continue
        if _IMAGE_MARKER_RE.match(line) or _HTML_COMMENT_RE.fullmatch(s):
            continue
        kept.append(line)
    head = kept[:_BIBLIO_HEAD_LINES]
    tail_lines = raw_md.splitlines()
    tail = [ln for ln in tail_lines[-_BIBLIO_TAIL_LINES:] if ln.strip()]
    # Only append a tail block if it is genuinely a different region than the head
    # (short documents: head already covers everything).
    parts = ["\n".join(head)]
    if len(kept) > _BIBLIO_HEAD_LINES and tail:
        parts.append("=== PAGE END / IMPRINT ===\n" + "\n".join(tail))
    return "\n\n".join(parts)


def identify_bibliographic(raw_md: str, hinweis: str = "", doc_id: str = "",
                           llm: Optional[LlmFn] = None) -> BiblioRecord:
    """One small LLM call: read the document's title-page region (+ the operator's
    imprint note, if any) and return a structured BiblioRecord. The `hinweis` is
    the operator's per-document imprint/citation line captured at upload — it is
    the single richest bibliographic signal and is handed to the model verbatim
    as the imprint. Never invents (unbestimmbar -> None + confidence "low"). On
    any LLM/JSON failure returns an empty BiblioRecord (confidence "low") so the
    caller degrades to its existing fallbacks — this never raises."""
    llm = llm or default_llm_fn()
    window = _content_head_tail(raw_md)
    hinweis = (hinweis or "").strip()
    user_parts: List[str] = []
    if hinweis:
        user_parts.append(
            "IMPRINT/SOURCE NOTE (captured by the operator — the most "
            "reliable bibliographic signal; use it preferentially for "
            "source, year and authors):\n" + hinweis
        )
    slug = (doc_id or "").strip()
    if slug:
        user_parts.append("FILENAME SLUG (a weak hint: it often carries the first-author surname and the publication year; the title page and imprint above always win, and it is lowercased/undiacritised, so never copy author names from it verbatim): " + slug)
    user_parts.append("TITLE PAGE / TEXT START:\n" + window)
    user = "\n\n".join(user_parts)

    # No max_tokens cap (platform rule: hard caps forbidden).
    obj = _extract_json_object(llm(_BIBLIO_SYSTEM, user, None))
    if obj is None:
        repair = user + (
            "\n\n---\nYour last answer was not valid JSON. Respond NOW "
            "ONLY with the JSON object {\"titel\":…, \"untertitel\":…, "
            "\"autoren\":[…], \"jahr\":…, \"quelle\":…, \"teil\":…, "
            "\"sprache\":…, \"confidence\":…}."
        )
        obj = _extract_json_object(llm(_BIBLIO_SYSTEM, repair, None))
    if obj is None:
        logger.warning("[KNOWLEDGE-PROC] bibliographic id: no JSON (x2)")
        return BiblioRecord()

    def _s(v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    autoren_raw = obj.get("autoren", [])
    autoren: List[str] = []
    if isinstance(autoren_raw, list):
        for a in autoren_raw:
            name = _s(a)
            if name:
                autoren.append(name)
    elif _s(autoren_raw):
        autoren.append(_s(autoren_raw))  # tolerate a single-string answer

    jahr: Optional[int] = None
    jahr_raw = obj.get("jahr")
    if jahr_raw is not None:
        m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(jahr_raw))
        if m:
            jahr = int(m.group(1))
    # doc_id slug fallback: the title-page window often lacks the year for a
    # journal article or book excerpt; the slug reliably carries it. Fill from
    # the slug ONLY when the text gave none, and only an isolated 4-digit year.
    if jahr is None and doc_id:
        _ms = re.search(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)", doc_id)
        if _ms:
            jahr = int(_ms.group(1))

    # Detected source language (ISO 639-1). Never guessed: an implausible or
    # missing value stays None so the front-matter `sprache:` is left empty
    # rather than defaulting to "de" (Defect 1c -- German is data, not a
    # hardcoded assumption).
    sprache = _s(obj.get("sprache"))
    if sprache:
        sprache = sprache.strip().lower()
        if not re.fullmatch(r"[a-z]{2}", sprache):
            sprache = None

    confidence = str(obj.get("confidence", "low")).strip().lower()
    if confidence not in ("high", "low"):
        confidence = "low"

    rec = BiblioRecord(
        titel=_s(obj.get("titel")),
        untertitel=_s(obj.get("untertitel")),
        autoren=autoren,
        jahr=jahr,
        quelle=_s(obj.get("quelle")),
        teil=_s(obj.get("teil")),
        sprache=sprache,
        confidence=confidence,
    )
    logger.info(
        "[KNOWLEDGE-PROC] bibliographic id: titel=%r autoren=%r jahr=%s "
        "sprache=%s quelle=%r teil=%r conf=%s",
        rec.composed_titel, rec.autoren_str, rec.jahr, rec.sprache, rec.quelle,
        rec.teil, rec.confidence,
    )
    return rec


# ===========================================================================
# 5) Deterministic assembly of the compact Markdown
# ===========================================================================

import json as _json


def _yaml_scalar(v: Any) -> str:
    s = str(v)
    if s == "" or re.search(r'[:#\[\]{}",]', s) or s != s.strip():
        return _json.dumps(s, ensure_ascii=False)
    return s


def _yaml_list(items: List[Any]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(_yaml_scalar(i) for i in items) + "]"


def render_front_matter(fm: Dict[str, Any]) -> str:
    # bereich (operator area id) + hinweis (operator per-document note) sit with
    # the other facets/metadata; both are optional and only emitted when the
    # caller put them in fm (the loop skips absent keys), so Tier-F files are
    # unchanged. `quelle` (journal/book/publisher, from the bibliographic id pass)
    # is likewise optional — it sits right after jahr, next to the other source
    # metadata, and is only emitted when present. analyzed_at/analysis_lang/
    # analysis_model (analysis PROVENANCE: when / in what language / by which
    # model(s) process_document actually ran -- distinct from `sprache`, the
    # document's own detected SOURCE language) are additive too, appended last,
    # and are likewise only emitted when present.
    order = ["id", "titel", "autor", "jahr", "quelle", "sprache", "tier",
             "sparten", "themen", "bereich", "hinweis", "lizenz", "url", "status",
             "analyzed_at", "analysis_lang", "analysis_model"]
    lines = ["---"]
    for key in order:
        if key not in fm:
            continue
        val = fm[key]
        if isinstance(val, list):
            lines.append(f"{key}: {_yaml_list(val)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(val)}")
    lines.append("---")
    return "\n".join(lines)


# Acronym-in-parenthesis suffix, e.g. "Critical Diversity Literacy (CDL)". The
# parenthetical initialism is a duplicate of the spelled-out term, not a new
# term — so "Critical Diversity Literacy (CDL)" and "Critical Diversity Literacy"
# collapse to ONE glossary entry (the Mörsch run emitted both).
_ACRONYM_PAREN_RE = re.compile(r"\s*\([A-Za-zÄÖÜäöüß]{2,8}\)\s*$")


def _glossary_key(term: str) -> str:
    """Normalise a term to its dedupe key: strip a trailing acronym-in-parens and
    lowercase. 'Critical Diversity Literacy (CDL)' -> 'critical diversity
    literacy' -> equal to the spelled-out form's key. Whitespace collapsed."""
    stripped = _ACRONYM_PAREN_RE.sub("", (term or "").strip())
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _dedup_glossary(digests: List[SectionDigest],
                    cap: int = _GLOSSARY_DOC_CAP) -> List[Dict[str, str]]:
    """Aggregate begriffe across units, deduped case-insensitively AND with
    acronym-in-parens normalisation ('X (ABC)' ≡ 'X'). Deterministic order =
    first appearance. On a collision the LONGER definition wins (more
    information), and the displayed term prefers the variant that CARRIES the
    acronym (the spelled-out-with-initialism form is the more useful label).
    Capped at `cap` per document (curated glossary, not a vocabulary notebook —
    the Map prompt already limits per-unit terms)."""
    seen: Dict[str, Dict[str, str]] = {}
    order: List[str] = []
    for d in digests:
        for b in d.begriffe:
            term = b["term"].strip()
            key = _glossary_key(term)
            if not key:
                continue
            definition = b.get("definition", "").strip()
            if key not in seen:
                seen[key] = {"term": term, "definition": definition}
                order.append(key)
                continue
            cur = seen[key]
            # Longer definition wins (the shorter is usually the impoverished one).
            if len(definition) > len(cur["definition"]):
                cur["definition"] = definition
            # Prefer the term variant that carries the acronym in parens as the
            # display label (more identifying), regardless of which came first.
            has_acr = bool(_ACRONYM_PAREN_RE.search(term))
            cur_has_acr = bool(_ACRONYM_PAREN_RE.search(cur["term"]))
            if has_acr and not cur_has_acr:
                cur["term"] = term
    return [seen[k] for k in order[:cap]]


# The PROFIL fallback when the Reduce call produced nothing usable (e.g. an
# LLM/provider outage). Named so _validate can recognise it as a FATAL
# condition -- an empty/placeholder PROFIL is not a usable document (CLAUDE.md
# rule 12 lesson: a 404 outage once wrote this stub over a good analysis and it
# got indexed).
_NO_PROFIL_PLACEHOLDER = "_(kein Profil erzeugt)_"


def assemble_markdown(fm: Dict[str, Any], profil: str,
                      digests: List[SectionDigest],
                      glossary_cap: int = _GLOSSARY_DOC_CAP) -> str:
    """Assemble the compact knowledge file:
        --- front-matter ---
        # Titel
        ## PROFIL
        ## WISSEN
          ### <Abschnitt de>   (+ <!-- quelle: <Original-Heading> --> anchor)
        ## GLOSSAR
    """
    out: List[str] = [render_front_matter(fm), ""]
    out.append(f"# {fm.get('titel', fm.get('id', 'Dokument'))}")
    out.append("")

    out.append("## PROFIL")
    out.append("")
    out.append(profil.strip() or _NO_PROFIL_PLACEHOLDER)
    out.append("")

    out.append("## WISSEN")
    out.append("")
    for d in digests:
        if d.missing or not d.verdichtung.strip():
            continue
        out.append(f"### {d.abschnitt_de}")
        out.append("")
        out.append(d.verdichtung.strip())
        out.append("")
        # Review anchor back to the original heading (stripped from the index).
        out.append(f"<!-- quelle: {d.source_heading} -->")
        out.append("")

    glossary = _dedup_glossary(digests, cap=glossary_cap)
    if glossary:
        out.append("## GLOSSAR")
        out.append("")
        for g in glossary:
            definition = g["definition"] or ""
            out.append(f"- **{g['term']}** — {definition}")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# ===========================================================================
# 6) Validation
# ===========================================================================

def _has_mojibake(text: str) -> bool:
    """Cheap mojibake sniff: the classic UTF-8-decoded-as-Latin1 sequences, the
    replacement char, or C1 control bytes leaking through."""
    if "�" in text:
        return True
    if re.search(r"Ã[\x80-\xbf]|â€", text):
        return True
    for ch in text:
        if unicodedata.category(ch) == "Cc" and ch not in "\n\t\r":
            return True
    return False


@dataclass
class ProcessingResult:
    doc_id: str
    markdown: str
    raw_chars: int
    compact_chars: int
    ratio: float
    n_content_sections: int
    n_emitted_sections: int
    n_missing_sections: int
    n_glossary: int
    warnings: List[str] = field(default_factory=list)
    fatal: List[str] = field(default_factory=list)
    # Analysis provenance (additive, 2026-07-10) -- WHEN this run happened,
    # WHAT target language it wrote in, and WHICH model(s) actually served it
    # (never the configured KNOWLEDGE_PROCESSING_MODEL slot, which a silent
    # provider fallback can diverge from invisibly; see default_llm_fn). Empty
    # when unavailable (e.g. a test's stub llm reports no served model) --
    # never guessed. Already baked into `markdown`'s front-matter by the time
    # this is returned; mirrored here so a caller can inspect/log them without
    # re-parsing the file.
    analyzed_at: str = ""
    analysis_lang: str = ""
    analysis_model: str = ""


def _validate(doc_id: str, markdown: str, raw_chars: int,
              digests: List[SectionDigest], mode: str = "standard",
              profil: str = "") -> Tuple[List[str], List[str]]:
    """Split validation: FATAL conditions mean the run produced no usable
    document at all -- process_document/_run_verdichtung must abort the write
    and the reindex (a provider outage that returns nothing usable must never
    overwrite a good prior analysis, CLAUDE.md rule 12). Everything else is
    ADVISORY: logged, the file is still written -- including a too-HIGH
    compression ratio, which is a quality signal, not a safety one (see
    _RATIO_CEILING below). Returns (fatal, warnings)."""
    fatal: List[str] = []
    warnings: List[str] = []

    if "## PROFIL" not in markdown:
        fatal.append("missing ## PROFIL section")
    if "## WISSEN" not in markdown:
        fatal.append("missing ## WISSEN section")
    emitted = [d for d in digests if not d.missing and d.verdichtung.strip()]
    if not emitted:
        fatal.append("no WISSEN subsections emitted (all sections MISSING/empty)")

    profil_body = profil.strip()
    if not profil_body or profil_body == _NO_PROFIL_PLACEHOLDER:
        fatal.append("PROFIL is empty or the placeholder (no usable profile was produced)")

    # Essays keep a higher share of their (small) raw substance — both bounds
    # are wider. FLOOR is a safety bound (stub signature) and stays FATAL;
    # CEILING is a quality signal (paraphrase-not-selection) and is ADVISORY
    # only -- see the comment above _RATIO_FLOOR/_RATIO_CEILING for why a
    # ceiling breach must never abort a write.
    lo, hi = ((_ESSAY_RATIO_FLOOR, _ESSAY_RATIO_CEILING) if mode == "essay"
              else (_RATIO_FLOOR, _RATIO_CEILING))
    compact_chars = len(markdown)
    ratio = compact_chars / raw_chars if raw_chars else 0.0
    if raw_chars and ratio < lo:
        fatal.append(
            f"compression ratio {ratio:.1%} below the floor {lo:.0%} "
            f"(compact={compact_chars}, raw={raw_chars}, mode={mode}) -- "
            "the stub signature: substance vanished"
        )
    elif raw_chars and ratio > hi:
        warnings.append(
            f"compression ratio {ratio:.1%} above the ceiling {hi:.0%} "
            f"(compact={compact_chars}, raw={raw_chars}, mode={mode}) -- "
            "likely paraphrase rather than selection (see budget_words), "
            "not fatal: fixed overhead alone exceeds the ceiling for short "
            "sources"
        )
    if _has_mojibake(markdown):
        warnings.append("possible mojibake / encoding damage in output")
    return fatal, warnings


# ===========================================================================
# Orchestration
# ===========================================================================

def process_document(
    raw_md: str,
    front_matter: Dict[str, Any],
    llm: Optional[LlmFn] = None,
    progress: Optional[Callable[[str], None]] = None,
    mode: str = "auto",
    target_lang: str = DEFAULT_ANALYSIS_LANG,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> ProcessingResult:
    """Process ONE raw Docling Markdown into a compact knowledge file.

    front_matter must carry the schema fields (id, titel, …) — the caller (the
    ingest CLI / the Settings job) builds it; missing 'titel' may be filled from
    parsed paratext here (deterministic fallback). The smart bibliographic
    identification (title/author/year/quelle from the title page + the operator
    imprint note) is done by the CALLER via identify_bibliographic BEFORE this
    engine runs — see _run_verdichtung — so a supplied titel is used as-is and
    this stays LLM-call-free for its own metadata. `llm` defaults to the
    production provider-routed path; tests inject a stub. `progress(msg)` receives
    one line per unit so the Phase-2 job can surface log_tail.

    `cancel_check`, when given, is polled (a) once before the Map loop starts and
    (b) between each per-unit Map call. If it returns true, process_document
    raises ProcessingCancelled instead of finishing — the enclosing ingest job
    turns that into a `cancelled` state and cleans up the partial draft. The poll
    sits at the unit boundary (the coarsest place where an in-flight LLM call has
    just returned), so an abort takes effect within one Map call, never mid-call.
    Default None keeps every existing caller (CLI, tests) unchanged.

    mode:
      * "auto" (default): detect_mode() picks standard vs essay from structure
        (heading-sparse OR short -> essay; else standard). A legal instrument is
        never auto-detected — pass "normtext" explicitly for those.
      * "standard": guidance/frameworks, budget ~15% of content-bearing raw
        words, heading-based chapter packing.
      * "normtext": legal instruments, budget ~10%, reference-style (no
        article-by-article paraphrase).
      * "essay": argumentative Fachaufsatz, WISSEN targets band 15-30% (budget
        ratio at the band floor since the model overshoots per-unit budgets),
        LLM segments the ARGUMENT (not the heading tree), argument-preservation
        prompt, tighter PROFIL + glossary cap. If the LLM segmenter fails, falls
        back to heading-based packing while keeping the essay budget + prompt
        (degrade, never break).

    target_lang: language the LLM writes the digest/PROFIL in (ISO 639-1 code
        or display name), default DEFAULT_ANALYSIS_LANG ("en" -- English,
        never a hardcoded German assumption; the original language is an
        acceptable fallback but must be passed explicitly). In-vivo terms/key
        concepts are kept in their original wording regardless of target_lang.

    Analysis provenance (additive front-matter, 2026-07-10): every successful
    run stamps `analyzed_at` (UTC ISO-8601), `analysis_lang` (== target_lang,
    distinct from front_matter['sprache']) and `analysis_model` (the actually-
    served model(s), read off llm.models_used -- see default_llm_fn) into the
    assembled markdown's front-matter and mirrors them on ProcessingResult. A
    FATAL run's markdown (with these keys already baked in) is simply never
    written by the caller, so a failed run never overwrites good provenance.
    """
    llm = llm or default_llm_fn()
    doc_id = str(front_matter.get("id", "document"))

    def _log(msg: str) -> None:
        logger.info("[KNOWLEDGE-PROC] %s", msg)
        if progress:
            try:
                progress(msg)
            except Exception:  # noqa: BLE001 - never let logging break the run
                pass

    paratext, content_sections, all_kept = parse_structure(raw_md)
    raw_chars = sum(s.chars for s in all_kept) or len(raw_md)

    # Text-type detection (deterministic). 'auto' -> standard|essay; an explicit
    # mode is honoured. detect_mode logs the decision with its numeric reason.
    mode, mode_reason = detect_mode(raw_md, all_kept, explicit=mode)
    if mode not in _BUDGET_RATIO:
        mode = "standard"
    _log(f"Modus: {mode_reason}")

    # Fill the title from paratext if the caller left it blank. Docling often
    # emits an essay's title as an H2 (not H1), so paratext.title (H1-only) stays
    # empty — fall back to the document's FIRST heading in the raw Markdown (any
    # level), which is the title even when it has no body of its own (a title
    # line immediately followed by the byline heading would otherwise be dropped
    # as an empty section, leaving only the byline "Von …").
    #
    # This is the DETERMINISTIC, cheap fallback. The SMART bibliographic
    # identification (identify_bibliographic — a small LLM call that reads the
    # title page + the operator's imprint note) is deliberately NOT here: it is an
    # orchestration/metadata concern and lives one layer up, in the ingest
    # service's _run_verdichtung (and in the repair script), where it seeds
    # front_matter['titel'/'autor'/'jahr'/'quelle'] BEFORE calling this engine.
    # By the time a mis-titled upload reaches here, titel is already correct and
    # this block is a no-op; keeping the engine LLM-call-free preserves its cost,
    # latency and testability (the unit-test stubs never see a biblio call).
    if not str(front_matter.get("titel", "")).strip():
        title = paratext.title or _first_raw_heading(raw_md)
        if title:
            front_matter = dict(front_matter)
            front_matter["titel"] = title

    # --- Unit construction: essay = LLM argument segmentation; else = chapter
    # packing (the first corpus run showed per-subsection condensation aggregates
    # to 50-70% retention — a German rendition, not a Verdichtung). Essays have
    # no chapter tree to pack, so the LLM segments the argument instead.
    seg_note = ""
    if mode == "essay":
        _log("Essay-Segmentierung (LLM liest den Volltext)…")
        segments = _segment_essay(raw_md, llm, target_lang=target_lang)
        if segments:
            units = _units_from_segments(segments)
            # Essay budget is the fraction of the WHOLE content-bearing raw words
            # (the argument runs continuously, so all content sections count).
            content_words = _count_words(raw_md)
            seg_note = f", {len(segments)} Argument-Abschnitte (LLM)"
        else:
            # Segmenter failed — degrade to heading packing, keep essay budget.
            _log("Essay-Segmentierung fehlgeschlagen -> Fallback Heading-Packing")
            units = _pack_units(content_sections)
            content_words = sum(_count_words(s.body) for s in content_sections)
            seg_note = ", Segmentierung fiel aus (Heading-Fallback)"
    else:
        units = _pack_units(content_sections)
        content_words = sum(_count_words(s.body) for s in content_sections)

    total_budget = max(_MIN_UNIT_BUDGET_WORDS,
                       int(content_words * _BUDGET_RATIO[mode]))
    total_unit_chars = sum(u.chars for u in units) or 1

    unit_word = "Argument-Abschnitte" if mode == "essay" else "Kapitel-Einheiten"
    _log(f"structure: {len(content_sections)} sections -> {len(units)} {unit_word}"
         f"{seg_note}, {len(paratext.blocks)} paratext blocks, raw≈{raw_chars} "
         f"chars, Budget {total_budget} Wörter (mode={mode})")

    # Per-unit budget floor. Essays are cut into MANY small argument segments, so
    # the standard 60-word floor would blow the whole document budget (8 units x
    # 60 = 480 words regardless of the target). Essay units get a lower floor so
    # the total budget actually binds; the argument-preservation prompt (not the
    # floor) protects the reasoning.
    unit_floor = 30 if mode == "essay" else _MIN_UNIT_BUDGET_WORDS

    # Budget distribution: essay = EQUAL per argument step (each step deserves
    # comparable space; the char-heavy footnote/reference segment must NOT hog
    # the budget just because it is long). standard/normtext = proportional to
    # chapter size.
    n_units = len(units) or 1

    def _cancelled() -> bool:
        if cancel_check is None:
            return False
        try:
            return bool(cancel_check())
        except Exception:  # noqa: BLE001 - a broken checker must not abort a run
            return False

    # A cancel requested before any Map work: nothing was written, bail early.
    if _cancelled():
        raise ProcessingCancelled(units_done=0)

    # 3) Map — one call per unit, each with its share of the budget. The cancel
    # check sits at the unit boundary: an operator abort takes effect after the
    # current unit's LLM call returns, never mid-call (the coarsest safe point).
    digests: List[SectionDigest] = []
    for i, unit in enumerate(units, 1):
        if mode == "essay":
            unit_budget = max(unit_floor, int(total_budget / n_units))
        else:
            unit_budget = max(unit_floor,
                              int(total_budget * unit.chars / total_unit_chars))
        _log(f"verdichte Einheit {i}/{len(units)} (~{unit_budget} W): {unit.heading}")
        digests.append(_map_unit(unit, unit_budget, llm, mode=mode, target_lang=target_lang))
        if _cancelled():
            raise ProcessingCancelled(units_done=i)

    # 4) Reduce — one call for the PROFIL.
    _log("erzeuge PROFIL (Reduce)")
    profil = _reduce_profile(paratext, digests, llm, mode=mode, target_lang=target_lang)

    # Essays get a tighter glossary cap (short text -> curated concept index).
    glossary_cap = _ESSAY_GLOSSARY_DOC_CAP if mode == "essay" else _GLOSSARY_DOC_CAP

    # --- Analysis provenance (additive front-matter, 2026-07-10) --------------
    # WHEN this run happened; WHAT target language it wrote in (target_lang --
    # never front_matter['sprache'], the document's own detected SOURCE
    # language; see DEFAULT_ANALYSIS_LANG); WHICH model(s) actually served the
    # Map/Reduce/segmenter calls above (read back off llm.models_used -- see
    # default_llm_fn -- not the configured KNOWLEDGE_PROCESSING_MODEL slot,
    # which a silent provider fallback can diverge from invisibly). A bare/
    # custom `llm` callable (e.g. a test stub) simply has no `.models_used`,
    # so this degrades to "" -- never a crash, never a guess. Comma-joined
    # when more than one model served this run.
    analyzed_at = datetime.now(timezone.utc).isoformat()
    models_used = list(dict.fromkeys(getattr(llm, "models_used", None) or []))
    analysis_model = ", ".join(models_used)

    front_matter = dict(front_matter)
    front_matter["analyzed_at"] = analyzed_at
    front_matter["analysis_lang"] = target_lang
    front_matter["analysis_model"] = analysis_model

    # 5) Assemble.
    markdown = assemble_markdown(front_matter, profil, digests,
                                 glossary_cap=glossary_cap)

    # 6) Validate -- split into FATAL (the run failed; caller must not write or
    # reindex) and advisory warnings (logged, the file is still written).
    fatal, warnings = _validate(doc_id, markdown, raw_chars, digests, mode=mode,
                                profil=profil)
    for f in fatal:
        logger.error("[KNOWLEDGE-PROC] %s: FATAL: %s", doc_id, f)
    for w in warnings:
        logger.warning("[KNOWLEDGE-PROC] %s: %s", doc_id, w)

    emitted = [d for d in digests if not d.missing and d.verdichtung.strip()]
    missing = [d for d in digests if d.missing]
    glossary = _dedup_glossary(digests, cap=glossary_cap)

    result = ProcessingResult(
        doc_id=doc_id,
        markdown=markdown,
        raw_chars=raw_chars,
        compact_chars=len(markdown),
        ratio=(len(markdown) / raw_chars if raw_chars else 0.0),
        n_content_sections=len(units),
        n_emitted_sections=len(emitted),
        n_missing_sections=len(missing),
        n_glossary=len(glossary),
        warnings=warnings,
        fatal=fatal,
        analyzed_at=analyzed_at,
        analysis_lang=target_lang,
        analysis_model=analysis_model,
    )
    _log(f"fertig: {result.compact_chars} chars ({result.ratio:.1%} von roh), "
         f"{result.n_emitted_sections} Einheiten, {result.n_missing_sections} FEHLEND, "
         f"{result.n_glossary} Glossar-Begriffe"
         + (f", FATAL: {'; '.join(result.fatal)}" if result.fatal else ""))
    return result
