"""
Knowledge processing (Verdichtung): a document's blocks -> ONE condensed
knowledge file, in the running devserver process.

The library never holds a non-CC source verbatim; it holds a condensation an
expert can work from WITHOUT the original (BIBLIOTHEK.md §3, rebuilt
2026-11-12 after "Monster im Dialog" lost a four-item list, four teaching
steps, the time frame, the prompt wording, seven cases and every figure).

The input is an Extraction (knowledge_extract.py): ordered blocks with their
PDF page and kind, cross-checked against the PDF's text layer. A markdown
source (an upload that already is markdown, a scene text) enters through
knowledge_extract.from_markdown and carries no page numbers.

    ┌─ pipeline ──────────────────────────────────────────────────────────┐
    │ 1 clean_blocks     deterministic: running heads, bare page numbers,  │
    │                    ToC and acronym blocks, skipped back matter       │
    │                    (references, ToC, imprint)                        │
    │ 2 library_units    deterministic: the whole document is ONE unit;    │
    │                    only a document above _DOC_UNIT_MAX_CHARS is cut, │
    │                    at its headings (build_units), into parts of      │
    │                    about equal size.                                 │
    │ 3 document type    ONE call: practice report, scholarly article,     │
    │                    framework/report, normative text, tool/handout,   │
    │                    book chapter + the source language.               │
    │ 4 summary          ONE call per unit, i.e. per document (role        │
    │                    KNOWLEDGE_PROCESSING_MODEL): a summary in         │
    │                    Markdown, in the source language, own words,      │
    │                    `##` headings after the document's structure with │
    │                    their pages, a TERMS section. The verbatim share  │
    │                    is measured in code; above the ceiling ONE        │
    │                    revision call names the copied passages.          │
    │ 5 reduce           ONE call: the PROFIL                              │
    │ 6 assemble         front matter + ## PROFIL + ## WISSEN (the         │
    │                    summary's sections as `###`, their subsections as │
    │                    `####`, then the figures as a list with pages) +  │
    │                    ## GLOSSAR                                        │
    │ 7 checks + gate    knowledge_checks.py: copyright (verbatim share)   │
    │                    and quality (lists, headings, figures, page       │
    │                    references, extraction) kept apart; a failed      │
    │                    check sets status draft and names itself in the   │
    │                    front matter key `checks`                         │
    └──────────────────────────────────────────────────────────────────────┘

Figures are described by the image model (describe_figures, figure_model:
KNOWLEDGE_IMAGE_MODEL, else the condensing model where it reads images, else
IMAGE_ANALYSIS_MODEL) in a separate step; until a
description exists the figure line says it is pending and the check
`figure_descriptions` fails, so the document stays draft. A small labelled
figure (knowledge_extract.screen_figures) is set with its caption only and
needs no description.

The front matter keeps its schema (id, titel, autor, jahr, quelle, sprache,
tier, sparten, themen, bereich, hinweis, lizenz, url, status, analyzed_at,
analysis_lang, analysis_model) and adds `checks` and `doc_type`; the body
form (PROFIL / WISSEN / GLOSSAR, `###` per section) is the one
build_knowledge_index.py reads.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path

from my_app.services import knowledge_checks, knowledge_review
from my_app.services.knowledge_extract import (
    _BIBLIOGRAPHY_HINTS, _SKIP_HEADING_HINTS, Block, Extraction, _heading_matches,
    skeleton)

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
    "es": "SPANISH",
    "ar": "ARABIC",
    "bg": "BULGARIAN",
    "he": "HEBREW",
    "zh-hant": "TRADITIONAL CHINESE (TAIWAN)",
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


# Default unit sizes of build_units (characters of rendered source text), the
# packing the scene capsule path reads. They decide where a unit is cut, never
# how long its text may be.
#   _UNIT_MIN_CHARS     a unit shorter than this takes the next section in
#   _UNIT_TARGET_CHARS  consecutive sections share a unit up to this size
#   _UNIT_MAX_CHARS     a single section above this is cut into windows
#   _UNIT_WINDOW_CHARS  the size of such a window
_UNIT_MIN_CHARS = 2500
_UNIT_TARGET_CHARS = 8000
_UNIT_MAX_CHARS = 12000
_UNIT_WINDOW_CHARS = 8000

# The library summarizes a document in ONE call (library_units, BIBLIOTHEK.md
# §3, rebuilt 2026-11-13): a document up to this size is one unit; a longer
# one is cut into parts of about equal size, each its own summary call.
_DOC_UNIT_MAX_CHARS = 120_000

# Text the document-type call sees: title, outline and the opening.
_TYPE_SAMPLE_CHARS = 6000
# Summary text handed to the PROFIL call.
_REDUCE_SAMPLE_CAP = 60000
# Glossary: at most this many terms per unit, this many per document.
_TERMS_PER_UNIT = 15
_GLOSSARY_DOC_CAP = 40

def _est_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ===========================================================================
# 1) Docling-artifact filtering helpers
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


# The headings of scaffolding (_SKIP_HEADING_HINTS: skipped entirely, never a
# content section, never paratext) and of the source's bibliography
# (_BIBLIOGRAPHY_HINTS: not condensed, but kept verbatim as the file's
# LITERATUR section by bibliography(), since the library is a citation
# apparatus, 2026-11-13) live in knowledge_extract, whose reading-order check
# judges these sections separately.
_BACK_MATTER_HINTS = _SKIP_HEADING_HINTS + _BIBLIOGRAPHY_HINTS
LITERATUR_SECTION = "LITERATUR"

# Front-matter `seitenzahlen` per Extraction.page_kind.
SEITENZAHLEN = {"printed-labels": "gedruckt", "printed-folio": "gedruckt",
                "pdf": "pdf", "none": "keine"}
# Annexes and appendices are content (case studies, instruments, word lists)
# and are condensed like any other section (2026-11-12).


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


def _find_repeated_lines(md: str, min_repeats: int = 4, min_len: int = 8) -> set:
    """Lines that recur many times across the document are running page
    headers/footers (e.g. the document title stamped on every page). Return the
    set of such lines so clean_blocks can drop them. Short lines and heading
    lines are never treated as repeats."""
    counts: Dict[str, int] = {}
    for line in md.splitlines():
        s = line.strip()
        if len(s) < min_len or _HEADING_RE.match(line):
            continue
        counts[s] = counts.get(s, 0) + 1
    return {s for s, n in counts.items() if n >= min_repeats}


# ===========================================================================
# 3+4) LLM calls (provider-routed)
# ===========================================================================

# A caller-supplied LLM function: (system, user, max_tokens) -> content str or
# None. max_tokens is Optional[int]; None means NO CAP (platform rule: hard
# max_tokens caps are forbidden -- _summarize_unit, _reduce_profile and
# detect_document_type all pass None).
LlmFn = Callable[[str, str, Optional[int]], Optional[str]]


# The models Mistral's chat completions give a flat reasoning_effort, by model
# name on the provider `mistral`, each with the levels it takes
# (docs.mistral.ai/studio/conversations/reasoning, read 2026-11-14: Mistral
# Large 4 takes low, medium and high, and that ladder holds for Large 4 alone).
MISTRAL_REASONING_EFFORTS: Dict[str, Tuple[str, ...]] = {
    "mistral-large-4-0": ("low", "medium", "high"),
}


def reasoning_payload(effort: Optional[str], model: Optional[str] = None) -> Optional[dict]:
    """The request fields for the reasoning effort of the condensing model,
    per provider, for the chat helper's provider_payload (default_llm_fn).
    Empty or None: nothing.

    OpenRouter's unified request field {"reasoning": {"effort": ...}} is the
    one this setting was measured with (issue #138), and OpenRouter
    translates it for the model behind it. Mistral is sent a flat
    reasoning_effort, only when `model` is pinned and named in
    MISTRAL_REASONING_EFFORTS: the chat helper hands provider_payload to
    every candidate on a provider, so a field keyed `mistral` without a
    pinned model would reach every Mistral model of a fallback chain, those
    that take no such field included. A level the model does not take is
    refused here rather than by the provider in the middle of a run. The
    other providers are named nowhere: OpenAI's chat completions and IONOS
    know a flat reasoning_effort, Anthropic's messages API a thinking block,
    Mammouth's endpoint neither documented here; bedrock and local/ are not
    reached through call_chat. A candidate there is sent no reasoning field
    and reasons as its provider's default has it."""
    effort = (effort or "").strip()
    if not effort:
        return None
    payload: Dict[str, dict] = {"openrouter": {"reasoning": {"effort": effort}}}
    provider, _, name = (model or "").strip().partition("/")
    levels = MISTRAL_REASONING_EFFORTS.get(name) if provider == "mistral" else None
    if levels is not None:
        if effort not in levels:
            raise ValueError(f"{model} takes the reasoning effort {', '.join(levels)}, "
                             f"not {effort!r}")
        payload["mistral"] = {"reasoning_effort": effort}
    return payload


def default_llm_fn(temperature: float = 0.2, model: Optional[str] = None,
                   reasoning_effort: Optional[str] = None) -> LlmFn:
    """The production LLM path: call_chat_helper with role
    KNOWLEDGE_PROCESSING_MODEL so the model->provider fallback chain applies.
    Imported lazily to keep this module import-safe in offline/test contexts.

    `model` pins one model (call_chat_helper's model_override: a single
    attempt, no fallback), for a run that has to be made with exactly that
    model, such as a pilot.

    The returned callable also exposes `.models_used` (List[str]): the distinct
    models that have ACTUALLY served a call so far, in first-seen order --
    call_chat_helper's own `model_used` (the post-fallback candidate that
    really answered), never the configured KNOWLEDGE_PROCESSING_MODEL slot. A
    silent model->provider fallback mid-run (see call_chat_helper's two-stage
    chain) can diverge from the configured slot with no other visible sign.
    process_document reads this attribute back after its type/summary/Reduce
    calls to stamp `analysis_model` in the front-matter (see process_document).

    `reasoning_effort` overrides config.KNOWLEDGE_REASONING_EFFORT for this
    callable; "" sends no reasoning field (reasoning_payload).

    `document` (2026-11-14): the source text several calls of one document
    share (unit_document: the summary, its retry and its revision, the review
    and its repair). It goes FIRST, as the opening text block of a single user
    message with the cache marker on it, and the instructions (`system`, then
    `user`) follow in a second block; no system message is sent, so the
    request prefix up to the marker is the same bytes in every call that
    shares the document, and the provider reads it from its prompt cache
    instead of processing it again. The marker lives `cache_ttl` ("1h"; empty
    = the provider's default of 5 minutes) from the last call that read it.
    OpenRouter is given a session id, a hash of the document, so the calls of
    one document go to the same upstream provider and find its cache there.
    A connection without prompt caching gets the two blocks joined into one
    string (llm_providers.without_cache_markers). The callable says it takes
    a document by `.takes_document`; knowledge_review.ask reads that.

    A model that reasoned and answered nothing returns None, as a failed call
    does: the chat helper hands such reasoning over as the content, the
    chat surface's rule (chat_routes.reasoning_only), and the library would
    take it for a summary or a review (issue #154). The caller's own path for
    a missing answer follows: the summary asks once more, the review sends
    its repair request."""
    import hashlib

    from my_app.routes.chat_routes import call_chat_helper, reasoning_only
    from my_app.services.llm_providers import CACHE_MARKER
    import config

    if reasoning_effort is None:
        reasoning_effort = getattr(config, "KNOWLEDGE_REASONING_EFFORT", "")
    provider_payload = reasoning_payload(reasoning_effort, model)
    models_used: List[str] = []

    def _fn(system: str, user: str, max_tokens: Optional[int] = None,
            document: Optional[str] = None, cache_ttl: str = "") -> Optional[str]:
        payload = provider_payload
        if document:
            marker = {"type": "ephemeral", **({"ttl": cache_ttl} if cache_ttl else {})}
            messages = [{"role": "user", "content": [
                {"type": "text", "text": document, CACHE_MARKER: marker},
                {"type": "text", "text": "\n\n".join(p for p in (system, user) if p)},
            ]}]
            session = "kb-" + hashlib.sha256(document.encode("utf-8")).hexdigest()[:32]
            payload = {k: dict(v) for k, v in (provider_payload or {}).items()}
            payload.setdefault("openrouter", {})["session_id"] = session
        else:
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": user}]
        try:
            result = call_chat_helper(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                role="KNOWLEDGE_PROCESSING_MODEL",
                model_override=model,
                provider_payload=payload,
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
            if reasoning_only(result):
                logger.warning("[KNOWLEDGE-PROC] %s answered with its reasoning only "
                               "(%d chars), taken as no answer", served,
                               len(result.get("thinking") or ""))
                return None
            return result.get("content")
        return result

    _fn.models_used = models_used  # type: ignore[attr-defined]
    _fn.takes_document = True  # type: ignore[attr-defined]
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



# ===========================================================================
# 2) Cleaning and units
# ===========================================================================

# Words the output uses for a page, a figure, an unnumbered image, a part of a
# long section, and a figure still waiting for its description -- in the
# language the condensation is written in. An unlisted language takes English.
# `unconfirmed` marks a quoted text in a figure description that the text of
# the source does not carry (screen_figure_text); it is set in the language of
# the source, the language of the description.
_LABELS: Dict[str, Dict[str, str]] = {
    "de": {"page": "S.", "figure": "Abb.", "image": "Bild", "part": "Teil",
           "pending": "Bildbeschreibung ausstehend", "note": "Anmerkung",
           "figures": "Abbildungen",
           "unconfirmed": "Schrift im Bild, vom Bildmodell gelesen, nicht bestätigt"},
    "en": {"page": "p.", "figure": "Fig.", "image": "Image", "part": "part",
           "pending": "image description pending", "note": "Note",
           "figures": "Figures",
           "unconfirmed": "Lettering in the image, read by the image model, not confirmed"},
    "fr": {"page": "p.", "figure": "fig.", "image": "Image", "part": "partie",
           "pending": "description de l'image en attente", "note": "Note",
           "figures": "Figures",
           "unconfirmed": "Texte dans l'image, lu par le modèle d'image, non confirmé"},
    "es": {"page": "p.", "figure": "fig.", "image": "Imagen", "part": "parte",
           "pending": "descripción de la imagen pendiente", "note": "Nota",
           "figures": "Figuras",
           "unconfirmed": "Texto en la imagen, leído por el modelo de imagen, no confirmado"},
}


def _labels(lang: Optional[str]) -> Dict[str, str]:
    return _LABELS.get((lang or "").strip().lower()[:2], _LABELS["en"])


def _page_span(page_from: int, page_to: int, lang: Optional[str]) -> str:
    """'(S. 4)' / '(S. 4–5)' / '(p. 4–5)'; '' when the pages are unknown."""
    if not page_from:
        return ""
    lab = _labels(lang)["page"]
    if page_to and page_to != page_from:
        return f"({lab} {page_from}–{page_to})"
    return f"({lab} {page_from})"


_BARE_PAGE_NO_RE = re.compile(r"[-–—\s]*\d{1,4}[-–—\s]*")


def clean_blocks(ext: Extraction, title: str = "") -> Tuple[List[Block], List[str]]:
    """The content blocks of an extraction with the scaffolding removed.

    Dropped: paragraphs that repeat across the document (running heads Docling
    did not mark as furniture), bare page numbers, table-of-contents and
    acronym blocks, and every section under a heading that names back matter
    or scaffolding (_SKIP_HEADING_HINTS: contents, imprint, …) or the
    bibliography (_BIBLIOGRAPHY_HINTS, kept verbatim by bibliography()) up
    to the next heading of the same or a higher level. A first heading that
    is the document's own title is dropped too: the file's `# titel` carries
    it. Remaining text has its PDF space runs squeezed.

    Returns (blocks, skipped), where `skipped` names what was dropped as a
    section, for the log and the report.
    """
    import dataclasses

    source = ext.content_blocks()
    repeated = _find_repeated_lines(
        "\n".join(b.text for b in source if b.kind == "paragraph"))
    title_sk = skeleton(title) if title else ""
    out: List[Block] = []
    skipped: List[str] = []
    skip_level: Optional[int] = None
    seen_content = False
    for orig in source:
        b = dataclasses.replace(orig)
        b.text = _squeeze_pdf_spaces(_HTML_COMMENT_RE.sub("", b.text or "")).strip()
        if b.kind == "title":
            b.kind, b.level = "heading", 1
        if b.kind == "heading":
            level = b.level or 1
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and _heading_matches(b.text, _BACK_MATTER_HINTS):
                skip_level = level
                skipped.append(f"{b.text} (p. {b.page})" if b.page else b.text)
                continue
            if not seen_content and title_sk:
                sk = skeleton(b.text)
                if len(sk) >= 6 and (title_sk.startswith(sk) or sk.startswith(title_sk)):
                    continue
        if skip_level is not None:
            continue
        if b.kind == "paragraph":
            if not b.text or b.text in repeated or _BARE_PAGE_NO_RE.fullmatch(b.text):
                continue
            if _is_toc_block(orig.text) or _is_acronym_block(orig.text):
                continue
        if b.kind != "heading":
            seen_content = True
        out.append(b)
    return out, skipped


@dataclass
class BibliographySection:
    """A bibliography of the source, its entries verbatim."""
    heading: str
    page_from: int
    page_to: int
    entries: List[str]


def bibliography(ext: Extraction) -> List[BibliographySection]:
    """The source's bibliography sections (_BIBLIOGRAPHY_HINTS) with every
    paragraph and list item under them up to the next heading of the same
    or a higher level, one entry per block, the text as Docling read it
    with its PDF space runs squeezed. clean_blocks leaves these sections out
    of the condensation; assemble_markdown writes them as LITERATUR."""
    out: List[BibliographySection] = []
    cur: Optional[BibliographySection] = None
    level: Optional[int] = None
    for b in ext.content_blocks():
        kind = "heading" if b.kind == "title" else b.kind
        text = _squeeze_pdf_spaces(_HTML_COMMENT_RE.sub("", b.text or "")).strip()
        if kind == "heading":
            lv = b.level or 1
            if level is not None and lv <= level:
                cur, level = None, None
            if level is None and _heading_matches(text, _BIBLIOGRAPHY_HINTS):
                cur = BibliographySection(text, b.page, b.page, [])
                out.append(cur)
                level = lv
            continue
        if cur is None or kind not in ("paragraph", "list_item") or not text:
            continue
        cur.entries.append(text)
        if b.page:
            cur.page_from = cur.page_from or b.page
            cur.page_to = max(cur.page_to, b.page)
    return [s for s in out if s.entries]


@dataclass
class Unit:
    """One condensation unit: a run of blocks the summary call reads at once.

    `blocks` starts with the unit's own heading block when it has one (`head`);
    further headings inside are its inner headings. A long section cut into
    windows yields several units with the same heading and `part`/`parts`.
    The text before the document's first heading has no heading of its own;
    its unit carries the document title as `derived_heading`, which names it
    in the source anchor (`source_span`) and nowhere the model reads.
    """
    heading: str
    blocks: List[Block]
    part: int = 1
    parts: int = 1
    index: int = 0
    derived_heading: str = ""

    @property
    def head(self) -> Optional[Block]:
        if self.blocks and self.blocks[0].kind == "heading" and self.part == 1:
            return self.blocks[0]
        return None

    @property
    def inner_headings(self) -> List[Block]:
        head = self.head
        return [b for b in self.blocks if b.kind == "heading" and b is not head]

    @property
    def page_from(self) -> int:
        pages = [b.page for b in self.blocks if b.page]
        return min(pages) if pages else 0

    @property
    def page_to(self) -> int:
        pages = [b.page for b in self.blocks if b.page]
        return max(pages) if pages else 0

    @property
    def chars(self) -> int:
        return sum(_block_chars(b) for b in self.blocks)

    @property
    def body(self) -> str:
        """The unit's text without page markers or figure markers (the scene
        path reads this)."""
        return render_blocks([b for b in self.blocks if b is not self.head],
                             lang=None, page_markers=False, figure_markers=False)

    @property
    def source_span(self) -> str:
        label = self.heading or self.derived_heading or "—"
        if self.parts > 1:
            label += f" [{self.part}/{self.parts}]"
        if self.page_from:
            label += f" (p. {self.page_from}–{self.page_to})" if self.page_to != self.page_from \
                else f" (p. {self.page_from})"
        return label


def _block_chars(b: Block) -> int:
    return len(_render_block(b, None, figure_markers=True)) + 2


def _can_cut_before(blocks: List[Block], i: int) -> bool:
    """A window never separates two items of one list, and a figure stays with
    the text before it."""
    if i <= 0:
        return False
    b, prev = blocks[i], blocks[i - 1]
    if b.kind == "figure":
        return False
    if b.kind == "list_item" and prev.kind == "list_item" and b.list_id == prev.list_id:
        return False
    return True


def _windows(blocks: List[Block], target: int) -> List[List[Block]]:
    """Cut a run of blocks into windows of about `target` characters at block
    boundaries. From 60 % of the target on, a heading or a page change is
    taken as the cut; past the target, any boundary that keeps lists and
    figures whole. A last window under a quarter of the target joins the one
    before it."""
    out: List[List[Block]] = []
    cur: List[Block] = []
    size = 0
    for i, b in enumerate(blocks):
        bc = _block_chars(b)
        if cur and _can_cut_before(blocks, i):
            natural = (b.kind == "heading"
                       or (b.page and cur[-1].page and b.page != cur[-1].page))
            if size + bc > target or (size >= 0.6 * target and natural):
                out.append(cur)
                cur, size = [], 0
        cur.append(b)
        size += bc
    if cur:
        if out and size < 0.25 * target:
            out[-1].extend(cur)
        else:
            out.append(cur)
    return out


def _cut_level(blocks: List[Block]) -> Optional[int]:
    """The heading level that opens a new unit: the smallest level at or above
    which at least two headings stand (a lone `# Title` over `##` chapters does
    not make the whole document one unit)."""
    levels = sorted(b.level or 1 for b in blocks if b.kind == "heading")
    if not levels:
        return None
    for lvl in sorted(set(levels)):
        if sum(1 for x in levels if x <= lvl) >= 2:
            return lvl
    return levels[0]


def build_units(blocks: List[Block], title: str = "", *,
                min_chars: int = _UNIT_MIN_CHARS, target_chars: int = _UNIT_TARGET_CHARS,
                max_chars: int = _UNIT_MAX_CHARS,
                window_chars: int = _UNIT_WINDOW_CHARS) -> List[Unit]:
    """The headings carry the units.

    The document is split at every heading into sections (text before the
    first heading is a section of its own, named by `title` as its derived
    heading: a document without page numbers is referenced by section, and
    "—" names nothing). Consecutive sections share a unit
    while the unit is under `min_chars`, or while the next section is a
    sub-section (below the cut level) and the unit stays within
    `target_chars`; the later headings stay in the unit as inner headings.
    A unit above `max_chars` -- a long chapter, or a document without
    headings -- is cut into windows of `window_chars` at block boundaries,
    preferring page changes. Every block lands in exactly one unit, in order.
    The defaults are the scene capsule's packing; the library calls this
    through library_units.
    """
    if not blocks:
        return []
    cut = _cut_level(blocks)

    sections: List[List[Block]] = []
    for b in blocks:
        if b.kind == "heading" or not sections:
            sections.append([b])
        else:
            sections[-1].append(b)

    packed: List[List[Block]] = []
    size = 0
    for sec in sections:
        sc = sum(_block_chars(b) for b in sec)
        opens = sec[0].kind == "heading"
        top = opens and cut is not None and (sec[0].level or 1) <= cut
        if packed and opens:
            if size + sc > target_chars or (top and size >= min_chars):
                packed.append([])
                size = 0
        if not packed:
            packed.append([])
        packed[-1].extend(sec)
        size += sc

    units: List[Unit] = []
    for group in packed:
        heading = group[0].text if group[0].kind == "heading" else ""
        derived = "" if heading else title.strip()
        total = sum(_block_chars(b) for b in group)
        if total <= max_chars:
            units.append(Unit(heading=heading, blocks=group, derived_heading=derived))
            continue
        wins = _windows(group, window_chars)
        for k, win in enumerate(wins, 1):
            units.append(Unit(heading=heading, blocks=win, part=k, parts=len(wins),
                              derived_heading=derived))
    for i, u in enumerate(units):
        u.index = i
    return units


def library_units(blocks: List[Block], title: str = "") -> List[Unit]:
    """The units of a library summary: the whole document is one unit, so the
    model reads the document as a whole. Only a document above
    _DOC_UNIT_MAX_CHARS is cut, into as many parts as its size needs, each
    of about equal size, at headings where it can (build_units)."""
    if not blocks:
        return []
    total = sum(_block_chars(b) for b in blocks)
    n = -(-total // _DOC_UNIT_MAX_CHARS)
    if n <= 1:
        target = _DOC_UNIT_MAX_CHARS
    else:
        target = min(_DOC_UNIT_MAX_CHARS, int(total / n * 1.15))
    return build_units(blocks, title, min_chars=target, target_chars=target,
                       max_chars=_DOC_UNIT_MAX_CHARS if n <= 1 else target,
                       window_chars=target)


# ---------------------------------------------------------------------------
# Rendering a unit's text for a model call
# ---------------------------------------------------------------------------

_FIG_LABEL_PREFIX_RE = re.compile(
    r"^\s*(?:Abb(?:ildung)?|Fig(?:ure)?|Grafik|Bild|Image|Tab(?:elle)?|Table)\.?\s*"
    r"\d+\s*[a-z]?(?:\s*[–-]\s*[a-z]\b)?\s*[:.)]?\s*", re.IGNORECASE)


def _figure_ident(b: Block, lang: Optional[str]) -> str:
    lab = _labels(lang)
    if b.figure_no:
        return f"{lab['figure']} {b.figure_no}"
    return f"{lab['image']} {b.seq}"


def _figure_caption(b: Block) -> str:
    return _FIG_LABEL_PREFIX_RE.sub("", b.caption or "", count=1).strip()


def _render_block(b: Block, lang: Optional[str], figure_markers: bool = True) -> str:
    if b.kind == "heading":
        return f"#### {b.text}"
    if b.kind == "list_item":
        marker = b.marker.strip() if (b.enumerated and b.marker.strip()) else "-"
        return f"{marker} {b.text}"
    if b.kind == "table":
        table = b.markdown or b.text
        return f"{b.caption}\n{table}" if b.caption else table
    if b.kind == "figure":
        caption = _figure_caption(b)
        ident = _figure_ident(b, lang)
        if figure_markers:
            return f"[[FIG:{b.seq}]] {ident}: {caption}".rstrip(": ")
        return f"{ident}: {caption}".rstrip(": ")
    if b.kind == "footnote":
        return f"[{_labels(lang)['note']}] {b.text}"
    return b.text


def render_blocks(blocks: List[Block], lang: Optional[str], page_markers: bool = True,
                  figure_markers: bool = True) -> str:
    """Blocks as the text a model call reads: `#### ` headings, list items
    one per line, tables as Markdown, `[[FIG:n]]` figure markers, and a page
    marker `[S. n]` wherever the page changes. A list that runs over a page
    break stays one list: the marker then stands inside the item that opens
    the new page (`- [S. 4] …`)."""
    lab = _labels(lang)["page"]
    parts: List[str] = []
    last_page = None
    prev: Optional[Block] = None
    for b in blocks:
        chunk = _render_block(b, lang, figure_markers=figure_markers)
        same_list = (prev is not None and prev.kind == "list_item"
                     and b.kind == "list_item" and prev.list_id == b.list_id)
        if page_markers and b.page and b.page != last_page:
            marker = f"[{lab} {b.page}]"
            last_page = b.page
            if same_list:
                head, _, rest = chunk.partition(" ")
                chunk = f"{head} {marker} {rest}"
            else:
                parts.append(("\n\n" if parts else "") + marker)
                prev = None
        sep = "\n" if same_list else "\n\n"
        parts.append((sep if parts else "") + chunk)
        prev = b
    return "".join(parts).strip()


# ===========================================================================
# 3) Document type
# ===========================================================================

# Each type: (name shown to the model, what the type is). The summary call
# names the type in one sentence; what is kept is the same for every type
# (_summary_system, 2026-11-13: the per-type duties of the Map prompt went
# with it).
DOC_TYPES: Dict[str, Tuple[str, str]] = {
    "practice_report": (
        "practice report",
        "a report on teaching or educational practice: a lesson, a project, a "
        "workshop, a course, told by the people who did it"),
    "scholarly_article": (
        "scholarly article",
        "an academic article, essay or paper that argues a thesis or reports "
        "research"),
    "framework_report": (
        "framework or report",
        "a policy framework, agenda, strategy, guideline or institutional "
        "report"),
    "normative_text": (
        "normative text",
        "a legal or normative instrument: convention, law, regulation, "
        "declaration, statute, curriculum"),
    "tool_handout": (
        "tool or handout",
        "a tool for use in practice: method card, worksheet, word list, game, "
        "checklist, handout, instructions"),
    "book_chapter": (
        "book chapter",
        "a chapter or section of a book"),
}


def _type_system() -> str:
    lines = [
        "You classify one document for the knowledge library of an "
        "arts-education platform. Answer ONLY with a JSON object "
        "{\"type\": \"<type>\", \"language\": \"<ISO 639-1 code of the "
        "language the document is written in>\", \"reason\": \"<one short "
        "sentence>\"}. The types:",
    ]
    for key, (_name, what) in DOC_TYPES.items():
        lines.append(f"- {key}: {what}")
    return "\n".join(lines)


def _type_user(title: str, units: List[Unit]) -> str:
    headings = [b.text for u in units for b in u.blocks if b.kind == "heading"]
    outline = "\n".join(f"- {h}" for h in headings[:60]) or "- (no headings)"
    opening = ""
    for u in units:
        opening += render_blocks(u.blocks, None, page_markers=False,
                                 figure_markers=False) + "\n\n"
        if len(opening) >= _TYPE_SAMPLE_CHARS:
            break
    return (f"Title: \"{title}\"\n\nOutline:\n{outline}\n\n"
            f"Opening:\n{opening[:_TYPE_SAMPLE_CHARS].strip()}")


def detect_document_type(title: str, units: List[Unit], llm: "LlmFn") -> Tuple[str, str, str]:
    """ONE call: (type key, ISO language code, reason). ('', '', reason) when
    the answer is unusable; the summary call then names no type."""
    obj = _extract_json_object(llm(_type_system(), _type_user(title, units), None))
    if not isinstance(obj, dict):
        return "", "", "type call gave no JSON"
    key = str(obj.get("type", "")).strip()
    lang = str(obj.get("language", "")).strip().lower()
    if key not in DOC_TYPES:
        return "", lang, f"unknown type {key!r}"
    return key, lang, str(obj.get("reason", "")).strip()


# ===========================================================================
# 4) Summary: one call per unit; a document up to _DOC_UNIT_MAX_CHARS is one
#    unit (library_units)
# ===========================================================================

# The heading the summary call puts over its term list (_summary_system), and
# the words a model may put there instead, in the languages the library writes.
_TERMS_HEADING = "TERMS"
_TERMS_HEADING_WORDS = frozenset({
    "terms", "begriffe", "glossar", "glossary", "termes", "glossaire",
    "términos", "terminos", "glosario"})
# A revision request names at most this many copied passages.
_REVISION_PASSAGES_CAP = 200


def _summary_system(target_lang: str, doc_type: str, has_pages: bool) -> str:
    """The summary request (BIBLIOTHEK.md §3.5, 2026-11-13): what the readers
    need kept, in plain terms, and the form of the answer. The verbatim share
    is not a rule of the request; it is measured in code afterwards
    (_summarize_unit)."""
    lang_name = _lang_display(target_lang)
    lab = _labels(target_lang)["page"]
    parts = [
        "Summarize the document given as SOURCE for the knowledge library of an "
        "arts-education platform. Its readers are teachers, educators and "
        "researchers who work from the summary and cite the document."]
    if doc_type in DOC_TYPES:
        name, what = DOC_TYPES[doc_type]
        parts.append(f"The document is a {name}: {what}.")
    parts.append(
        "Keep: the purpose or thesis and the course of the argument; the "
        "concepts the document introduces, with their meaning; the cases, "
        "examples and works it discusses, with names; instructions, steps and "
        "enumerations completely, item by item; numbers as given.")
    parts.append(
        f"Write in {lang_name}, in your own words. Quote only where the wording "
        "itself matters, briefly and in quotation marks.")
    if has_pages:
        parts.append(
            f"The SOURCE carries page markers such as [{lab} 4]. Give the pages "
            "for each part of your summary: every ## heading ends with the "
            f"pages it covers, as ({lab} 4) or ({lab} 4–6).")
    else:
        parts.append("The source has no page numbers: write no page references.")
    parts.append(
        "Answer in Markdown, with ## headings that follow the document's own "
        "structure. Start with the first ## heading; write no title line.")
    parts.append(
        f"End with a section headed exactly \"## {_TERMS_HEADING}\": the terms "
        f"the document itself coins or defines, at most {_TERMS_PER_UNIT}, one "
        "per line as \"- **term**: its meaning in this document\". Leave the "
        "section out when the document coins none.")
    return "\n\n".join(parts)


def unit_document(unit: Unit, units: List[Unit], title: str, lang: str,
                  author: str = "", has_pages: bool = True) -> str:
    """The source of one unit as every call about it is given it, the summary
    with its retry and revision and the review with its repair: the title
    line, which part of a cut document it is, and the text with page markers
    between SOURCE delimiters. The same bytes for all of them, since they are
    sent first under the cache marker (default_llm_fn) and the provider reads
    a prefix from its cache only where it is identical. Ends in a blank line,
    so the instructions that follow stand apart where a connection without
    prompt caching joins the two blocks."""
    head = (f"Document: \"{title}\"" if title else "Document") \
        + (f", by {author}" if author else "")
    if len(units) > 1:
        head += f"\n\nPart {unit.index + 1} of {len(units)}: {unit.source_span}"
    text = render_blocks(unit.blocks, lang, page_markers=has_pages, figure_markers=False)
    return f"{head}\n\n=== SOURCE ===\n{text}\n=== END OF SOURCE ===\n\n"


def _summary_task(units: List[Unit]) -> str:
    """What the summary call says after the instructions: for a part of a cut
    document, that it summarizes this part only."""
    return "Summarize this part only." if len(units) > 1 else ""


def _then(task: str, more: str) -> str:
    """`more` after `task`, a blank line between them where both are there."""
    return "\n\n".join(p for p in (task, more) if p)


@dataclass
class SectionDigest:
    abschnitt_de: str            # a heading set over the text; "" when the text opens with its own
    verdichtung: str             # the unit's summary: `###` sections, `####` below them
    begriffe: List[Dict[str, str]]
    source_heading: str          # review anchor: source heading and pages
    missing: bool = False
    unit_index: int = -1
    notes: List[str] = field(default_factory=list)


def _digest_text(d: SectionDigest) -> str:
    """A digest as it stands in WISSEN."""
    if d.abschnitt_de:
        return f"### {d.abschnitt_de}\n\n{d.verdichtung}".rstrip()
    return d.verdichtung.strip()


_MD_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_PAGE_REF = r"(?:S\.|pp?\.)\s*\d+(?:\s*[–-]\s*\d+)?"
_TRAILING_PAGE_REF_RE = re.compile(r"\s*[(\[]" + _PAGE_REF + r"[)\]]\s*$")
_BRACKET_PAGE_REF_RE = re.compile(r"\[(" + _PAGE_REF + r")\]")
_PAGE_NUMBERS_RE = re.compile(r"(?:S\.|pp?\.)\s*(\d+)(?:\s*[–-]\s*(\d+))?")
_CODE_FENCE_RE = re.compile(r"^```[\w-]*[ \t]*\n(.*?)\n?```\s*$", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+(.*\S)\s*$")
_TERM_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$")


def _heading_lines(lines: List[str]) -> List[Tuple[int, int, str]]:
    """(line index, level, text) of the Markdown headings."""
    out: List[Tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        m = _MD_HEADING_LINE_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2)))
    return out


def _trailing_pages(text: str) -> List[int]:
    """The page numbers of a heading's trailing page reference."""
    m = _TRAILING_PAGE_REF_RE.search(text)
    if not m:
        return []
    n = _PAGE_NUMBERS_RE.search(m.group(0))
    return [int(n.group(1)), int(n.group(2) or n.group(1))] if n else []


def _parse_terms(lines: List[str]) -> List[Dict[str, str]]:
    """The entries of a TERMS section: `- **term**: meaning`, also with the
    colon inside the bold, a dash instead of the colon, or no bold."""
    out: List[Dict[str, str]] = []
    for line in lines:
        m = _LIST_ITEM_RE.match(line)
        if not m:
            continue
        item = m.group(1)
        b = _TERM_BOLD_RE.match(item)
        if b:
            term = b.group(1).strip().rstrip(":").strip()
            meaning = re.sub(r"^(?::|[—–-])\s*", "", b.group(2).strip()).strip()
        else:
            parts = re.split(r"\s*:\s+|\s+[—–]\s+", item, maxsplit=1)
            if len(parts) != 2:
                continue
            term, meaning = parts[0].strip(), parts[1].strip()
        if term and meaning:
            out.append({"term": term, "definition": meaning})
    return out[:_TERMS_PER_UNIT]


def _split_terms(lines: List[str]) -> Tuple[List[str], List[Dict[str, str]]]:
    """The TERMS section out of a summary: the heading asked for, or, as the
    last section of its level, one of the words for it in the library's
    languages. (the lines without it, its entries)."""
    heads = _heading_lines(lines)
    for k in range(len(heads) - 1, -1, -1):
        i, level, text = heads[k]
        key = _TRAILING_PAGE_REF_RE.sub("", text).strip().strip("*_:").strip().lower()
        later = [h for h in heads[k + 1:] if h[1] <= level]
        if key == _TERMS_HEADING.lower() or (key in _TERMS_HEADING_WORDS and not later):
            end = later[0][0] if later else len(lines)
            return lines[:i] + lines[end:], _parse_terms(lines[i + 1:end])
    return lines, []


def figure_line(fig: Block, lang: Optional[str], description: str = "") -> str:
    """A figure at its place: number, page, caption, description -- or the
    note that the description is pending, naming the exported image file. A
    figure that gets no description (Block.describe) stands with its caption."""
    ident = _figure_ident(fig, lang)
    span = _page_span(fig.page, fig.page, lang)
    head = f"*{ident}{' ' + span if span else ''}:*"
    caption = _figure_caption(fig)
    text = head + (f" {caption}" if caption else "")
    if description.strip():
        return f"{text} — {description.strip()}"
    if not fig.describe:
        return text
    pending = _labels(lang)["pending"]
    return f"{text} _({pending}: {fig.image or '—'})_"


def _section_heading(unit: Unit, title: str, lang: str, whole: bool = True) -> str:
    """The heading set over a summary that opens without one of its own: the
    document title over a document summarized whole, the source heading over
    one part of a cut document; with the pages."""
    if whole:
        heading = title or unit.heading or unit.derived_heading or "—"
    else:
        heading = unit.heading or unit.derived_heading or title or "—"
        if unit.parts > 1:
            heading += f" ({_labels(lang)['part']} {unit.part}/{unit.parts})"
    span = _page_span(unit.page_from, unit.page_to, lang)
    return f"{heading} {span}" if span else heading


def _is_title_line(lines: List[str], heads: List[Tuple[int, int, str]],
                   has_pages: bool) -> bool:
    """Whether the first heading of a summary is a title line over the whole
    (asked not to be written, written anyway): it opens the answer, carries
    no pages where the others do, and is the only heading of its level, or
    stands without sections of its own beside sections that carry pages."""
    if len(heads) < 2 or any(line.strip() for line in lines[:heads[0][0]]):
        return False
    _i, level, text = heads[0]
    if level != min(h[1] for h in heads):
        return False
    if has_pages and _TRAILING_PAGE_REF_RE.search(text):
        return False
    same = [h for h in heads[1:] if h[1] == level]
    if not same:
        return True
    own = [h for h in heads[1:] if h[0] < same[0][0]]
    return has_pages and not own and any(_TRAILING_PAGE_REF_RE.search(h[2]) for h in same)


def _finish_body(answer: str, unit: Unit, title: str, lang: str,
                 descriptions: Dict[int, str], has_pages: bool,
                 whole: bool) -> Tuple[str, List[Dict[str, str]], List[str]]:
    """The summary as it stands in WISSEN, and its terms. Deterministic: the
    TERMS section is taken out; a title line goes; the top heading level
    becomes `###` (one index chunk each), every deeper one `####`; a page
    reference in square brackets takes round ones; a `###` without pages
    takes the span of its `####` sections; a summary that opens without a
    heading gets the document's (`_section_heading`); the unit's figures
    follow as a list under their own `###`."""
    notes: List[str] = []
    text = answer.strip()
    fence = _CODE_FENCE_RE.match(text)
    if fence:
        text = fence.group(1).strip()
    lines, terms = _split_terms(text.splitlines())
    heads = _heading_lines(lines)
    if _is_title_line(lines, heads, has_pages):
        notes.append(f"title line removed: {heads[0][2]}")
        del lines[heads[0][0]]
        heads = _heading_lines(lines)
    if heads:
        top = min(h[1] for h in heads)
        for i, level, htext in heads:
            lines[i] = f"{'###' if level == top else '####'} {htext}"
    text = _BRACKET_PAGE_REF_RE.sub(r"(\1)", "\n".join(lines))

    if has_pages:
        lines = text.splitlines()
        heads = _heading_lines(lines)
        for k, (i, level, htext) in enumerate(heads):
            if level != 3 or _TRAILING_PAGE_REF_RE.search(htext):
                continue
            pages: List[int] = []
            for _j, lv, ct in heads[k + 1:]:
                if lv <= 3:
                    break
                pages += _trailing_pages(ct)
            if pages:
                span = _page_span(min(pages), max(pages), lang)
                lines[i] = f"### {htext} {span}"
                notes.append(f"pages {span} set from the sections below: {htext}")
        text = "\n".join(lines)

    text = text.strip()
    if not text.startswith("### "):
        text = f"### {_section_heading(unit, title, lang, whole)}\n\n{text}"

    figs = [b for b in unit.blocks if b.kind == "figure"]
    if figs:
        pages = [f.page for f in figs if f.page]
        span = _page_span(min(pages), max(pages), lang) if pages else ""
        head = f"### {_labels(lang)['figures']}" + (f" {span}" if span else "")
        text += "\n\n" + head + "\n\n" + "\n\n".join(
            figure_line(f, lang, descriptions.get(f.seq, "")) for f in figs)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, terms, notes


def _revision_user(task: str, answer: str, share: float, ceiling: float,
                   min_words: int, copied: List[str]) -> str:
    """The summary request once more (the same document goes before it,
    _summarize_unit), with the first answer, its verbatim share against the
    ceiling, and the passages that stand word for word in the document --
    quoted ones included, since the share counts them too."""
    shown = copied[:_REVISION_PASSAGES_CAP]
    passages = "\n".join(f"- {p}" for p in shown)
    if len(copied) > len(shown):
        passages += f"\n- … ({len(copied) - len(shown)} more)"
    return _then(task, (
        f"---\nYour summary:\n\n{answer}\n\n---\n"
        f"{share:.0%} of your summary repeats the document word for word "
        f"(runs of {min_words} words or more); the library takes at most "
        f"{ceiling:.0%}. These passages of your summary stand word for word in "
        f"the document:\n{passages}\n\n"
        "Rewrite them in your own words and with your own sentence structure. "
        "Keep a quotation only where the wording itself matters (a prompt, a "
        "task put to learners, a term the document coins), and keep it short. "
        "Names and titles of works may stay as written. Change nothing else: "
        "every heading with its pages, every list item, name, number and page "
        "reference stays. Answer with the complete summary in the same "
        f"Markdown, including the ## {_TERMS_HEADING} section."))


def _summarize_unit(unit: Unit, units: List[Unit], llm: LlmFn, *, title: str,
                    target_lang: str, doc_type: str, has_pages: bool, author: str = "",
                    descriptions: Optional[Dict[int, str]] = None,
                    cache_ttl: str = "") -> SectionDigest:
    """One summary call for one unit, with ONE retry on an empty answer; on a
    second empty answer the unit is recorded MISSING (the run goes on; the
    heading check then fails and the document stays draft). The verbatim
    share of the answer is measured as the gate measures it; above the
    ceiling ONE revision call names the passages, and the revision is kept
    when its share is lower. Every call sends the unit's document first
    (unit_document, knowledge_review.ask) with the cache marker of lifetime
    `cache_ttl`; the review of the unit sends the same document."""
    from config import KNOWLEDGE_VERBATIM_MAX_SHARE, KNOWLEDGE_VERBATIM_MIN_WORDS
    whole = len(units) == 1
    system = _summary_system(target_lang, doc_type, has_pages)
    document = unit_document(unit, units, title, target_lang, author, has_pages)
    task = _summary_task(units)

    def ask(user: str) -> str:
        return (_strip_think(knowledge_review.ask(llm, system, user, document, cache_ttl))
                or "").strip()

    answer = ask(task)
    if not answer:
        answer = ask(_then(task, "---\nYour last answer was empty. Answer NOW with "
                                 "the summary in Markdown."))
    if not answer:
        logger.warning("[KNOWLEDGE-PROC] unit MISSING (empty answer x2): %s", unit.source_span)
        return SectionDigest(abschnitt_de=_section_heading(unit, title, target_lang, whole),
                             verdichtung="", begriffe=[], source_heading=unit.source_span,
                             missing=True, unit_index=unit.index)

    notes: List[str] = []
    source = render_blocks(unit.blocks, None, page_markers=False, figure_markers=False)
    lists = knowledge_checks.source_list_text(unit.blocks)
    share = knowledge_checks.check_verbatim_share(
        source, answer, KNOWLEDGE_VERBATIM_MIN_WORDS, KNOWLEDGE_VERBATIM_MAX_SHARE,
        list_text=lists).value or 0.0
    if share > KNOWLEDGE_VERBATIM_MAX_SHARE:
        copied = knowledge_checks.unmarked_verbatim(
            source, answer, KNOWLEDGE_VERBATIM_MIN_WORDS, quoted=True, list_text=lists)
        revised = ask(_revision_user(
            task, answer, share, KNOWLEDGE_VERBATIM_MAX_SHARE,
            KNOWLEDGE_VERBATIM_MIN_WORDS, copied))
        revised_share = knowledge_checks.check_verbatim_share(
            source, revised, KNOWLEDGE_VERBATIM_MIN_WORDS,
            KNOWLEDGE_VERBATIM_MAX_SHARE, list_text=lists).value if revised else None
        if revised and revised_share is not None and revised_share < share:
            notes.append(f"verbatim share {share:.1%}, revised to {revised_share:.1%}")
            answer = revised
        else:
            notes.append(f"verbatim share {share:.1%}, revision kept nothing lower"
                         + (f" ({revised_share:.1%})" if revised_share is not None else
                            " (empty answer)"))

    body, terms, finish_notes = _finish_body(answer, unit, title, target_lang,
                                             descriptions or {}, has_pages, whole)
    return SectionDigest(abschnitt_de="", verdichtung=body, begriffe=terms,
                         source_heading=unit.source_span, unit_index=unit.index,
                         notes=notes + finish_notes)


# ===========================================================================
# 5) Reduce: the PROFIL
# ===========================================================================

def _reduce_system(target_lang: str = DEFAULT_ANALYSIS_LANG, doc_type: str = "") -> str:
    lang_name = _lang_display(target_lang)
    kind = f" (a {DOC_TYPES[doc_type][0]})" if doc_type in DOC_TYPES else ""
    return (
        f"Write in {lang_name}. Keep the document's own terms in their "
        "wording, and quote nothing else: the summary already carries the "
        f"quotations. You write the PROFILE of a document{kind} for the knowledge "
        "library of an arts-education platform, from its summary. "
        "Factual register; no evaluation, no blurb, no promotional language. "
        "About 6 to 12 lines. State, as far as the document makes it explicit: "
        "who wrote it (as the author line names them; where no author line is "
        "given, leave authorship out), for whom and in what context; its "
        "subject and its own "
        "claim or position; what it contains, part by part; the works and "
        "authors it builds on or sets itself against; for which disciplines and "
        "situations of arts education it is usable. State only what the "
        "summary says; nothing about the condition of the text, its "
        "completeness or its figures. Running prose or \"- \" points, no "
        "heading.")


def _reduce_profile(title: str, digests: List[SectionDigest], llm: LlmFn,
                    target_lang: str, doc_type: str = "", author: str = "") -> str:
    """One Reduce call: the summary -> the PROFIL text."""
    sample = "\n\n".join(_digest_text(d) for d in digests if not d.missing)
    user = ((f"Title: \"{title}\".\n" if title else "")
            + (f"Author(s): {author}.\n" if author else "")
            + "\nSummary:\n\n" + sample[:_REDUCE_SAMPLE_CAP])
    reply = _strip_think(llm(_reduce_system(target_lang, doc_type), user, None))
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
    # and are likewise only emitted when present. `checks` (the gate's verdict,
    # next to status) and `doc_type` (the document type of the condensation)
    # date from 2026-11-12.
    # `seitenzahlen` (2026-11-13) says which numbering the page references of
    # the file use: gedruckt (the page number printed in the source), pdf (the
    # page's position in the file) or keine (DOCX, markdown: none).
    # `review` (2026-11-13), next to checks: the adversarial review's verdict
    # (knowledge_review), `passed` or the material findings.
    # `status_reason` (2026-11-13), right after status: why a draft is a
    # draft (STATUS_REASONS); absent on a published file.
    # `pdf_seiten` (2026-11-13), after hinweis: the PDF pages of a document
    # that is part of its file (a chapter of a volume); absent otherwise.
    order =["id", "titel", "autor", "jahr", "quelle", "sprache", "tier",
             "sparten", "themen", "bereich", "hinweis", "pdf_seiten", "lizenz", "url", "status",
             "status_reason", "checks", "review", "analyzed_at", "analysis_lang", "analysis_model", "doc_type",
             "seitenzahlen"]
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
    the summary prompt already limits per-unit terms)."""
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
                      glossary_cap: int = _GLOSSARY_DOC_CAP,
                      literatur: Optional[List[BibliographySection]] = None,
                      lang: Optional[str] = None) -> str:
    """Assemble the compact knowledge file:
        --- front-matter ---
        # Titel
        ## PROFIL
        ## WISSEN             per unit: its `###` sections (`####` below), the
                              figures under their own `###`, then the anchor
                              <!-- quelle: <source heading> (p. n–m) -->
        ## LITERATUR          (the source's bibliography, entries verbatim,
                               + <!-- quelle: <heading> (S. n–m) --> anchor)
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
        out.append(_digest_text(d))
        out.append("")
        # Review anchor back to the source unit (stripped from the index); it
        # closes the unit's text, so digests_from_markdown reads units back by it.
        out.append(f"<!-- quelle: {d.source_heading} -->")
        out.append("")

    if literatur:
        out.append(f"## {LITERATUR_SECTION}")
        out.append("")
        for sec in literatur:
            span = _page_span(sec.page_from, sec.page_to, lang)
            out.append(f"<!-- quelle: {sec.heading}{' ' + span if span else ''} -->")
            out.append("")
            out.extend(f"- {e}" for e in sec.entries)
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




# ===========================================================================
# 8) Checks, gate and orchestration
# ===========================================================================

# Why a library file is a draft (front matter `status_reason`, several joined
# by ", "). A published file carries none; a draft never stands without one.
STATUS_REASON_CHECKS = "checks"        # a check of knowledge_checks failed
STATUS_REASON_REVIEW = "review"        # the adversarial review found errors
STATUS_REASON_NO_REVIEW = "no_review"  # the run was made without a review
STATUS_REASON_RELEASE = "release"      # a fresh upload awaiting the operator's release
STATUS_REASON_OPERATOR = "operator"    # the operator set the file to draft
STATUS_REASONS = (STATUS_REASON_CHECKS, STATUS_REASON_REVIEW, STATUS_REASON_NO_REVIEW,
                  STATUS_REASON_RELEASE, STATUS_REASON_OPERATOR)


def gate_status(checks_passed: bool, review_passed: Optional[bool],
                hold: str) -> Tuple[str, str]:
    """(status, status_reason) of a condensation. A file whose checks and
    review pass is published, unless the caller holds it: a fresh upload
    stays a draft until the operator releases it (BIBLIOTHEK.md §3.3 and §9,
    hold STATUS_REASON_RELEASE), a file the operator had set to draft stays
    one on reprocess (STATUS_REASON_OPERATOR); reprocess_hold says which.
    `review_passed` is None for a run made without a review."""
    if hold and hold not in STATUS_REASONS:
        raise ValueError(f"unknown hold {hold!r}")
    reasons = []
    if not checks_passed:
        reasons.append(STATUS_REASON_CHECKS)
    if review_passed is None:
        reasons.append(STATUS_REASON_NO_REVIEW)
    elif not review_passed:
        reasons.append(STATUS_REASON_REVIEW)
    if hold:
        # A hold is recorded beside a failed check too, so a later run whose
        # checks pass still knows the file waits for the operator.
        reasons.append(hold)
    return ("draft" if reasons else "published"), ", ".join(reasons)


def reprocess_hold(status: str, status_reason: str) -> str:
    """The hold of a reprocess: the operator's draft stays one, every other
    prior state is decided by the gate anew (a passing file is published)."""
    reasons = [r.strip() for r in (status_reason or "").split(",")]
    if status == "draft" and STATUS_REASON_OPERATOR in reasons:
        return STATUS_REASON_OPERATOR
    if status == "draft" and STATUS_REASON_RELEASE in reasons:
        # Not yet released by the operator: a reprocess does not release it.
        return STATUS_REASON_RELEASE
    return ""


@dataclass
class ProcessingResult:
    doc_id: str
    markdown: str
    source_chars: int            # rendered source text of all units
    compact_chars: int
    n_units: int
    n_emitted_sections: int
    n_missing_sections: int
    n_glossary: int
    warnings: List[str] = field(default_factory=list)
    fatal: List[str] = field(default_factory=list)
    # Analysis provenance (2026-07-10): when, in which language, by which
    # model(s) actually serving the calls (llm.models_used, never the
    # configured slot). Already in `markdown`'s front matter.
    analyzed_at: str = ""
    analysis_lang: str = ""
    analysis_model: str = ""
    doc_type: str = ""
    # Gate (2026-11-12): `status` as written into the front matter (draft
    # whenever a check failed), `checks` its front-matter label, and the
    # full report for the `<doc_id>.checks.json` sidecar.
    status: str = ""
    status_reason: str = ""      # gate_status: why a draft is a draft
    checks: str = ""
    check_report: Dict[str, Any] = field(default_factory=dict)
    units: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    # Adversarial review (knowledge_review): the sidecar's `review` entry,
    # empty when the run was made without one.
    review: Dict[str, Any] = field(default_factory=dict)

    @property
    def checks_passed(self) -> bool:
        return bool(self.check_report.get("passed"))

    @property
    def review_passed(self) -> bool:
        return bool(self.review.get("passed"))


def _validate(markdown: str, digests: List[SectionDigest],
              profil: str) -> Tuple[List[str], List[str]]:
    """FATAL means the run produced no usable document: the caller writes
    nothing and does not reindex (a provider outage must never overwrite a
    good prior analysis). Returns (fatal, warnings). Completeness and
    copyright are the checks' business (knowledge_checks), not this one's."""
    fatal: List[str] = []
    warnings: List[str] = []
    if "## PROFIL" not in markdown:
        fatal.append("missing ## PROFIL section")
    if "## WISSEN" not in markdown:
        fatal.append("missing ## WISSEN section")
    if not [d for d in digests if not d.missing and d.verdichtung.strip()]:
        fatal.append("no WISSEN subsections emitted (all units MISSING/empty)")
    profil_body = profil.strip()
    if not profil_body or profil_body == _NO_PROFIL_PLACEHOLDER:
        fatal.append("PROFIL is empty or the placeholder (no usable profile was produced)")
    if _has_mojibake(markdown):
        warnings.append("possible mojibake / encoding damage in output")
    return fatal, warnings


def _unit_summary(u: Unit) -> Dict[str, Any]:
    return {"index": u.index, "heading": u.heading, "derived_heading": u.derived_heading,
            "part": u.part, "parts": u.parts,
            "page_from": u.page_from, "page_to": u.page_to, "chars": u.chars,
            "blocks": len(u.blocks), "inner_headings": len(u.inner_headings),
            "figures": sum(1 for b in u.blocks if b.kind == "figure")}


def _source_text(units: List[Unit]) -> str:
    return "\n\n".join(render_blocks(u.blocks, None, page_markers=False,
                                     figure_markers=False) for u in units)


def _body_of(markdown: str) -> str:
    """The markdown without its front matter."""
    if markdown.startswith("---\n"):
        end = markdown.find("\n---", 4)
        if end >= 0:
            return markdown[end + 4:]
    return markdown


def _without_section(markdown: str, name: str) -> str:
    """The markdown without its `## <name>` section."""
    return re.sub(rf"(?ms)^## {re.escape(name)}\s*$.*?(?=^## |\Z)", "", markdown)


def _without_figure_lists(markdown: str, lang: str) -> str:
    """The markdown without the figure lists _finish_body appends to a
    unit, each under `### <figures label> (<pages>)` up to the next heading
    of level three or higher."""
    label = re.escape(_labels(lang)["figures"])
    return re.sub(rf"(?ms)^### {label}(?: \([^)\n]*\))?\s*$.*?(?=^#{{1,3}} |\Z)", "", markdown)


# What the verbatim share leaves out of the condensation, as its summary
# names it. The share is measured on the text: the source's bibliography
# stands in LITERATUR verbatim as reference data, and the figure
# descriptions do not count (Projektleitung, 13.11.2026: „20% Text.
# Bildbeschreibungen zählen nicht dazu.“).
VERBATIM_EXCLUDED_LITERATUR = f"{LITERATUR_SECTION} (reference data, entries verbatim)"
VERBATIM_EXCLUDED_FIGURES = "figure descriptions"


@dataclass
class FigureScreen:
    """What the code can say about the figure descriptions without the image:
    `marked` are the descriptions as they go into the output, a quoted text
    that the source does not carry marked as read by the image model alone;
    `unconfirmed` lists those quotes per figure (check figure_text);
    `wrong_language` the figures whose description is not in the language
    of the source (check figures)."""
    marked: Dict[int, str] = field(default_factory=dict)
    unconfirmed: List[Dict[str, Any]] = field(default_factory=list)
    wrong_language: List[Dict[str, Any]] = field(default_factory=list)


def figure_witness(extraction: Extraction, fig: Block, reference: str) -> str:
    """The text of the source a figure description can be checked against:
    the text layer of the figure's PDF page (for a source without one, the
    extracted text of its page), the caption, and the passage referring to
    the figure."""
    page_text = extraction.text_layer.get(fig.pdf_page, "") if fig.pdf_page else ""
    if not page_text:
        page_text = "\n".join(b.text for b in extraction.blocks
                               if b.page == fig.page and b.text)
    return "\n".join(t for t in (page_text, fig.caption or "", reference) if t)


def screen_figure_text(extraction: Extraction, descriptions: Dict[int, str],
                       lang: str, source_lang: str) -> FigureScreen:
    """The code's part of checking figure descriptions (the review never
    sees the image): a quoted text in a description that stands nowhere in
    the page's text layer, caption or referring passage is marked in the
    output as read by the image model alone, in the language of the source;
    a description whose language is not the source's is listed for the check
    `figures`. `lang` names the figures as the output does."""
    refs = figure_references(extraction.blocks)
    src = (source_lang or "").strip().lower()[:2]
    label = _labels(src or lang)["unconfirmed"]
    screen = FigureScreen()
    for fig in extraction.figures():
        text = (descriptions.get(fig.seq) or "").strip()
        if not text:
            continue
        ident = _figure_ident(fig, lang)
        quotes = knowledge_checks.unconfirmed_quotes(
            text, figure_witness(extraction, fig, refs.get(fig.seq, "")))
        if quotes:
            screen.unconfirmed.append({"figure": ident, "page": fig.page,
                                       "image": fig.image, "quotes": quotes})
            text = f"{text} _({label}: {', '.join(quotes)})_"
        screen.marked[fig.seq] = text
        said = knowledge_checks.text_language(descriptions[fig.seq])
        if src and said and said != src:
            screen.wrong_language.append({"figure": ident, "page": fig.page,
                                          "image": fig.image, "description_language": said,
                                          "source_language": src})
    for seq, text in descriptions.items():
        screen.marked.setdefault(seq, text)
    return screen


def _run_checks(units: List[Unit], digests: List[SectionDigest], markdown: str,
                extraction: Extraction, lang: str,
                descriptions: Dict[int, str],
                source_lang: str = "",
                screen: Optional[FigureScreen] = None) -> knowledge_checks.CheckReport:
    """`source_lang`: the language of the source; where it is known and the
    condensation is in another one, the list check compares counts only.
    `screen`: the figure screening of process_document (screen_figure_text)."""
    from config import KNOWLEDGE_VERBATIM_MAX_SHARE, KNOWLEDGE_VERBATIM_MIN_WORDS

    by_unit = {d.unit_index: d for d in digests}
    pairs: List[knowledge_checks.SectionPair] = []
    pending: List[Dict[str, Any]] = []
    n_figures = 0
    for u in units:
        d = by_unit.get(u.index)
        figs = [b for b in u.blocks if b.kind == "figure"]
        n_figures += sum(1 for f in figs if f.describe)
        for f in figs:
            if f.describe and not descriptions.get(f.seq, "").strip():
                pending.append({"figure": _figure_ident(f, lang), "page": f.page,
                                "image": f.image})
        missing = d is None or d.missing or not d.verdichtung.strip()
        output = "" if missing else _digest_text(d)
        pairs.append(knowledge_checks.SectionPair(
            index=u.index, heading=u.source_span, source_blocks=u.blocks, output=output,
            page_from=u.page_from, page_to=u.page_to, missing=missing,
            figure_idents=[_figure_ident(f, lang) for f in figs]))
    # The LITERATUR section holds the source's bibliography verbatim: reference
    # data, left out of the verbatim share, and so are the figure lists (the
    # check's summary says so).
    body = _body_of(markdown)
    text = _without_figure_lists(_without_section(body, LITERATUR_SECTION), lang)
    has_lit = bool(re.search(rf"(?m)^## {LITERATUR_SECTION}\s*$", markdown))
    has_figs = text != _without_section(body, LITERATUR_SECTION)
    return knowledge_checks.run_checks(
        pairs, source_text=_source_text(units),
        output_text=text,
        page_first=extraction.page_first, page_last=extraction.page_last,
        page_kind=extraction.page_kind, integrity=extraction.integrity,
        source=extraction.source, pending_figures=pending, n_figures=n_figures,
        min_words=KNOWLEDGE_VERBATIM_MIN_WORDS, max_share=KNOWLEDGE_VERBATIM_MAX_SHARE,
        output_excluded=([VERBATIM_EXCLUDED_LITERATUR] if has_lit else [])
        + ([VERBATIM_EXCLUDED_FIGURES] if has_figs else []),
        compare_items=not source_lang or source_lang.lower()[:2] == lang.lower()[:2],
        wrong_language=screen.wrong_language if screen else [],
        unconfirmed_figure_text=screen.unconfirmed if screen else [])


def _unit_layer(unit: Unit, layer_pages: Dict[int, str], lang: str) -> str:
    """The text layer of the unit's PDF pages that are in `layer_pages`
    (Extraction.order_layer), each under the page as the output cites it."""
    printed: Dict[int, int] = {}
    for b in unit.blocks:
        if b.pdf_page and b.pdf_page in layer_pages:
            printed.setdefault(b.pdf_page, b.page)
    return "\n\n".join(f"[{_labels(lang)['page']} {printed[p] or p}]\n{layer_pages[p].strip()}"
                       for p in sorted(printed))


def review_sections(units: List[Unit], digests: List[SectionDigest], lang: str,
                    has_pages: bool,
                    descriptions: Dict[int, str],
                    layer_pages: Optional[Dict[int, str]] = None,
                    *, title: str = "", author: str = "",
                    ) -> List[knowledge_review.ReviewSection]:
    """The sections the adversarial review reads: per unit with a summary,
    the unit's document as the summary call was given it (unit_document,
    with the same `title` and `author`, so the review reads it from the
    cache the summary call wrote) and the summary as written into the file.
    The image descriptions of the unit's figures go along, marked as the image
    model's text, each with the passage that refers to its figure where that
    passage stands outside the unit, so the reviewer can check the
    description against what the source says the figure shows. `layer_pages`
    (PDF page: text layer, Extraction.order_layer) gives a unit on such a page
    the text layer as a second reading for the order check."""
    by_unit = {d.unit_index: d for d in digests}
    references = figure_references([b for u in units for b in u.blocks])
    out: List[knowledge_review.ReviewSection] = []
    for u in units:
        d = by_unit.get(u.index)
        if d is None or d.missing or not d.verdichtung.strip():
            continue
        figs = [b for b in u.blocks if b.kind == "figure"]
        out.append(knowledge_review.ReviewSection(
            index=u.index, heading=u.source_span,
            document=unit_document(u, units, title, lang, author, has_pages),
            output=_digest_text(d),
            page_from=u.page_from, page_to=u.page_to,
            image_descriptions=[
                _review_description(f, lang, descriptions[f.seq], references.get(f.seq, ""), u)
                for f in figs if descriptions.get(f.seq, "").strip()],
            layer=_unit_layer(u, layer_pages or {}, lang)))
    return out


def _review_description(fig: Block, lang: str, description: str, reference: str,
                        unit: Unit) -> str:
    line = f"{_figure_ident(fig, lang)}: {description}"
    in_unit = any(b.text and reference.strip("…") in b.text for b in unit.blocks)
    if reference and not in_unit:
        line += f"\n  (source text referring to this figure, outside this section: \"{reference}\")"
    return line


_QUELLE_ANCHOR_RE = re.compile(r"^<!-- quelle: (.*) -->$")


def digests_from_markdown(markdown: str, units: List[Unit]) -> List[SectionDigest]:
    """The WISSEN text of a written condensation as digests, the inverse of
    assemble_markdown: a unit's summary is the text up to its
    `<!-- quelle: <span> -->` anchor, opening with a `### ` heading, and the
    anchor names its unit by Unit.source_span. Units with the same span are
    taken in document order, as assemble_markdown wrote them. An anchor that
    names no unit raises ValueError: the file was written from another
    extraction or under another title, and a review against the wrong source
    unit says nothing. The glossary terms are not read back (the review does
    not see them)."""
    lines = markdown.splitlines()
    try:
        start = lines.index("## WISSEN") + 1
    except ValueError:
        return []
    ends = {f"## {LITERATUR_SECTION}", "## GLOSSAR"}
    end = next((i for i in range(start, len(lines)) if lines[i] in ends), len(lines))
    by_span: Dict[str, List[Unit]] = {}
    for u in units:
        by_span.setdefault(u.source_span, []).append(u)
    digests: List[SectionDigest] = []
    chunk: List[str] = []
    for line in lines[start:end]:
        m = _QUELLE_ANCHOR_RE.match(line)
        if not m:
            chunk.append(line)
            continue
        span = m.group(1)
        if not by_span.get(span):
            raise ValueError(f"anchor names no unit of the extraction: {span!r}")
        unit = by_span[span].pop(0)
        text = "\n".join(chunk).strip()
        chunk = []
        if not text.startswith("### "):
            raise ValueError(f"summary without a ### heading before the anchor {span!r}")
        digests.append(SectionDigest(abschnitt_de="", verdichtung=text,
                                     begriffe=[], source_heading=span, unit_index=unit.index))
    return digests


def review_condensation(extraction: Extraction, markdown: str, review_llm: LlmFn, *,
                        title: str, lang: str, source_lang: str,
                        author: str = "",
                        figure_descriptions: Optional[Dict[int, str]] = None,
                        workers: int = 1,
                        progress: Optional[Callable[[str], None]] = None,
                        ) -> knowledge_review.ReviewVerdict:
    """The adversarial review of a condensation already written, through
    `review_llm`, so that one reviewer can judge the files of several
    condensing models: the units are built again from the extraction under
    the title the file carries, the sections are read from the file
    (digests_from_markdown), the figure descriptions are screened as in
    process_document, and the review runs as there. `lang` is the language
    the file is written in (analysis_lang), `source_lang` the source's
    (sprache), `author` the file's `autor`, which the summary call's document
    named. The file is not changed; the caller keeps the verdict. The calls
    of a review alone find no summary's cache entry (its lifetime is minutes),
    so the marker keeps the provider's default lifetime: one write, read by
    a repair where one is needed."""
    blocks, _ = clean_blocks(extraction, title)
    units = library_units(blocks, title)
    digests = digests_from_markdown(markdown, units)
    descriptions = screen_figure_text(extraction, dict(figure_descriptions or {}),
                                      lang, source_lang).marked
    has_pages = extraction.page_last > 0
    return knowledge_review.review_document(
        review_sections(units, digests, lang, has_pages, descriptions,
                        extraction.order_layer(), title=title, author=author),
        review_llm, has_pages=has_pages, workers=workers, progress=progress)


def _summarize_units_side_by_side(units: List[Unit], llm: LlmFn, *, workers: int,
                                  cancelled: Callable[[], bool],
                                  log: Callable[[str], None],
                                  report: Callable[[int], None],
                                  **summary_kwargs: Any) -> List[SectionDigest]:
    """The summary step with `workers` calls in flight at once (a document cut
    into several units); the digests come back in the document's order. The
    cancel check is read whenever calls return: calls not yet started are
    dropped, the ones in flight finish on their threads and are discarded."""
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    results: List[Optional[SectionDigest]] = [None] * len(units)
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="kp-sum")
    try:
        index = {pool.submit(_summarize_unit, unit, units, llm, **summary_kwargs): i
                 for i, unit in enumerate(units)}
        log(f"verdichte {len(units)} Einheiten, {workers} zugleich")
        pending = set(index)
        done_n = 0
        while pending:
            finished, pending = wait(pending, return_when=FIRST_COMPLETED)
            for fut in finished:
                i = index[fut]
                results[i] = fut.result()
                done_n += 1
                log(f"verdichtet {done_n}/{len(units)}: {units[i].source_span}")
                report(done_n)
            if cancelled():
                raise ProcessingCancelled(units_done=done_n)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return [r for r in results if r is not None]


def _fallback_title(extraction: Extraction) -> str:
    """The first heading of the extraction that is not scaffolding."""
    for b in extraction.content_blocks():
        if b.kind in ("title", "heading") and b.text.strip() \
                and not _heading_matches(b.text, _BACK_MATTER_HINTS):
            return _squeeze_pdf_spaces(b.text).strip()
    return ""


def process_document(
    extraction: Extraction,
    front_matter: Dict[str, Any],
    llm: Optional[LlmFn] = None,
    progress: Optional[Callable[[str], None]] = None,
    target_lang: Optional[str] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
    map_workers: int = 1,
    figure_descriptions: Optional[Dict[int, str]] = None,
    doc_type: Optional[str] = None,
    review: bool = True,
    review_llm: Optional[LlmFn] = None,
    hold: str = STATUS_REASON_RELEASE,
) -> ProcessingResult:
    """Condense ONE extraction into a knowledge file.

    front_matter carries the schema fields (id, titel, …), built by the
    caller; the bibliographic identification (identify_bibliographic) runs
    in the caller before this. A missing titel is filled from the first
    heading. `llm` defaults to the production path; tests inject a stub.

    Language: `target_lang` when given (the scene path writes in the
    instance language); otherwise the source language as the type call
    reports it, then front_matter['sprache'], then DEFAULT_ANALYSIS_LANG.

    `doc_type` (a DOC_TYPES key) skips the type call; the language then
    comes from target_lang or front_matter['sprache'].

    `figure_descriptions` maps a figure's `seq` to its description by the
    image model (describe_figures). A figure without one is written with the
    note that its description is pending, and the check
    `figure_descriptions` fails.

    Units (library_units): the whole document is one unit and one summary
    call; only a document longer than _DOC_UNIT_MAX_CHARS is cut, at its
    headings, into parts of about equal length.

    `cancel_check` is polled before the type call, before the summary step
    and at every unit boundary; a true answer raises ProcessingCancelled.
    `on_progress(done, total)` is called once the units are known and after
    every summary call. `map_workers` > 1 runs that many summary calls, and
    later review calls, at once.

    Gate: the checks (knowledge_checks) run on the assembled file. The
    front-matter key `checks` carries `passed` or the failed checks. The
    gate (gate_status) sets `status` and `status_reason`, whatever status
    the caller's front matter carried: published when checks and review
    pass and the caller does not `hold` the file (default: a fresh upload,
    STATUS_REASON_RELEASE; a reprocess passes ""), else draft with every
    reason.

    Review (`review=True`, knowledge_review): after the checks, one call per
    unit, through `review_llm` (default: `llm`), with the instruction to
    refute the summary against its source unit. The
    front-matter key `review` carries `passed` or the material findings; a
    failed review makes the file a draft as well. The verdict goes into
    `ProcessingResult.review`, which write_library_file puts into the sidecar
    for the retention step. `review=False` leaves both out (the document then
    has no recorded review, is a draft with reason `no_review`, and the
    retention step keeps its source).
    """
    llm = llm or default_llm_fn()
    descriptions = dict(figure_descriptions or {})
    fm = dict(front_matter)
    doc_id = str(fm.get("id", "document"))

    def _log(msg: str) -> None:
        logger.info("[KNOWLEDGE-PROC] %s", msg)
        if progress:
            try:
                progress(msg)
            except Exception:  # noqa: BLE001 - never let logging break the run
                pass

    def _cancelled() -> bool:
        if cancel_check is None:
            return False
        try:
            return bool(cancel_check())
        except Exception:  # noqa: BLE001 - a broken checker must not abort a run
            return False

    if not str(fm.get("titel", "")).strip():
        fallback = _fallback_title(extraction)
        if fallback:
            fm["titel"] = fallback
    title = str(fm.get("titel", "")).strip()

    blocks, skipped = clean_blocks(extraction, title)
    literatur = bibliography(extraction)
    units = library_units(blocks, title)
    source_chars = sum(u.chars for u in units)
    fm["seitenzahlen"] = SEITENZAHLEN[extraction.page_kind]
    _log(f"Einheiten: {len(units)} aus {len(blocks)} Blöcken, {extraction.pages} Seiten "
         f"({extraction.page_kind} {extraction.page_first}–{extraction.page_last}), "
         f"{source_chars} Zeichen" + (f"; übersprungen: {', '.join(skipped)}" if skipped else ""))
    if not units:
        return ProcessingResult(
            doc_id=doc_id, markdown="", source_chars=0, compact_chars=0, n_units=0,
            n_emitted_sections=0, n_missing_sections=0, n_glossary=0,
            fatal=["no content blocks after cleaning"], skipped=skipped)

    if _cancelled():
        raise ProcessingCancelled(units_done=0)

    # 3) Document type, once.
    type_key = doc_type if doc_type in DOC_TYPES else ""
    detected_lang = ""
    if not type_key:
        type_key, detected_lang, reason = detect_document_type(title, units, llm)
        _log(f"Dokumenttyp: {type_key or '—'} ({reason}); Sprache: {detected_lang or '—'}")
    lang = (target_lang or detected_lang or str(fm.get("sprache", "") or "").strip()
            or DEFAULT_ANALYSIS_LANG).lower()
    if detected_lang and not str(fm.get("sprache", "") or "").strip():
        fm["sprache"] = detected_lang
    source_lang = str(fm.get("sprache", "") or detected_lang or "").strip().lower()
    screen = screen_figure_text(extraction, descriptions, lang, source_lang)
    descriptions = screen.marked

    def _report(done: int) -> None:
        if on_progress is None:
            return
        try:
            on_progress(done, len(units))
        except Exception:  # noqa: BLE001 - a display must never break a run
            pass

    if _cancelled():
        raise ProcessingCancelled(units_done=0)

    # 4) Summary, one call per unit.
    # The lifetime of the cache marker on each unit's document
    # (default_llm_fn): the unit's review reads what its summary call wrote.
    # Where every unit's summary starts at once, the review starts about two
    # minutes after it (two one-unit runs with 12291 and 10097 output tokens,
    # api_usage.jsonl, 2026-11-13 23:20 and 23:24), inside the provider's
    # default of 5 minutes, and a write costs 1.25 times the
    # input price against 2 times for the hour. Where units wait for a
    # worker, the first unit's review waits for every summary, and the
    # marker asks for the hour.
    cache_ttl = "" if len(units) <= max(1, map_workers) else "1h"
    summary_kwargs = dict(title=title, author=str(fm.get("autor", "") or "").strip(),
                          target_lang=lang, doc_type=type_key,
                          has_pages=extraction.page_last > 0, descriptions=descriptions,
                          cache_ttl=cache_ttl)
    _report(0)
    digests: List[SectionDigest] = []
    if map_workers > 1 and len(units) > 1:
        digests = _summarize_units_side_by_side(units, llm, workers=map_workers,
                                                cancelled=_cancelled, log=_log,
                                                report=_report, **summary_kwargs)
    else:
        for i, unit in enumerate(units, 1):
            _log(f"verdichte Einheit {i}/{len(units)}: {unit.source_span}")
            digests.append(_summarize_unit(unit, units, llm, **summary_kwargs))
            _report(i)
            if _cancelled():
                raise ProcessingCancelled(units_done=i)

    # 5) Reduce: the PROFIL.
    _log("erzeuge PROFIL (Reduce)")
    profil = _reduce_profile(title, digests, llm, lang, type_key, summary_kwargs["author"])

    # Provenance.
    analyzed_at = datetime.now(timezone.utc).isoformat()
    analysis_model = ", ".join(dict.fromkeys(getattr(llm, "models_used", None) or []))
    fm["analyzed_at"] = analyzed_at
    fm["analysis_lang"] = lang
    fm["analysis_model"] = analysis_model
    if type_key:
        fm["doc_type"] = type_key

    # 6) Assemble, 7) checks and gate, then assemble with the gate's verdict.
    markdown = assemble_markdown(fm, profil, digests, literatur=literatur, lang=lang)
    report = _run_checks(units, digests, markdown, extraction, lang, descriptions,
                         source_lang=source_lang, screen=screen)
    fm["checks"] = report.label()
    for r in report.failed:
        _log(f"Prüfung nicht bestanden: {r.name} ({r.kind}): {r.summary}")

    # 8) Adversarial review, one call per unit.
    review_dict: Dict[str, Any] = {}
    if review:
        if _cancelled():
            raise ProcessingCancelled(units_done=len(units))
        verdict = knowledge_review.review_document(
            review_sections(units, digests, lang, extraction.page_last > 0, descriptions,
                            extraction.order_layer(), title=title,
                            author=summary_kwargs["author"]),
            review_llm or llm, has_pages=extraction.page_last > 0,
            workers=map_workers, cache_ttl=cache_ttl, progress=progress)
        review_dict = verdict.to_dict()
        fm["review"] = verdict.label()
    fm["status"], reasons = gate_status(report.passed, verdict.passed if review else None, hold)
    if reasons:
        fm["status_reason"] = reasons
        _log(f"Status draft: {reasons}")
    else:
        fm.pop("status_reason", None)
    markdown = assemble_markdown(fm, profil, digests, literatur=literatur, lang=lang)

    fatal, warnings = _validate(markdown, digests, profil)
    for d in digests:
        warnings.extend(f"{d.source_heading}: {n}" for n in d.notes)
    for f in fatal:
        logger.error("[KNOWLEDGE-PROC] %s: FATAL: %s", doc_id, f)
    for w in warnings:
        logger.warning("[KNOWLEDGE-PROC] %s: %s", doc_id, w)

    emitted = [d for d in digests if not d.missing and d.verdichtung.strip()]
    result = ProcessingResult(
        doc_id=doc_id, markdown=markdown, source_chars=source_chars,
        compact_chars=len(markdown), n_units=len(units),
        n_emitted_sections=len(emitted),
        n_missing_sections=sum(1 for d in digests if d.missing),
        n_glossary=len(_dedup_glossary(digests)), warnings=warnings, fatal=fatal,
        analyzed_at=analyzed_at, analysis_lang=lang, analysis_model=analysis_model,
        doc_type=type_key, status=fm["status"], status_reason=fm.get("status_reason", ""),
        checks=fm["checks"],
        check_report=report.to_dict(), units=[_unit_summary(u) for u in units],
        skipped=skipped, review=review_dict)
    _log(f"fertig: {result.compact_chars} Zeichen, {result.n_emitted_sections} Abschnitte, "
         f"{result.n_missing_sections} FEHLEND, Prüfungen: {result.checks}"
         + (f", Gegenprüfung: {fm['review']}" if review else "")
         + (f", FATAL: {'; '.join(result.fatal)}" if result.fatal else ""))
    return result


def write_library_file(result: ProcessingResult, out_md: Path,
                       extraction: Extraction,
                       extra: Optional[Dict[str, Any]] = None) -> Path:
    """Write the condensation and its `<doc_id>.checks.json` sidecar: the
    check report, the document's provenance, the integrity report and, when
    the run made one, the adversarial review under `review` (the entry the
    retention step reads). Every writer of a library file goes through here,
    so a new file never keeps the review of an older one."""
    out_md = Path(out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(result.markdown, encoding="utf-8")
    data: Dict[str, Any] = {"doc_id": result.doc_id, "doc_type": result.doc_type,
                            "analyzed_at": result.analyzed_at, "units": result.units,
                            "skipped": result.skipped,
                            "integrity": extraction.integrity.to_dict()}
    if result.review:
        data["review"] = result.review
    data.update(extra or {})
    knowledge_checks.write_sidecar(knowledge_checks.sidecar_path(out_md),
                                   result.check_report, extra=data)
    return out_md


def plan_document(extraction: Extraction, front_matter: Dict[str, Any],
                  lang: Optional[str] = None) -> Dict[str, Any]:
    """What process_document and describe_figures would do, without a model
    call: units, the type call, one summary call per unit and the Reduce call
    with their input sizes, the ceiling of the revision calls, and one
    image-model call per figure. The summary system prompt depends on the
    document type the type call returns, so its size is given as the range
    over all types; the user text is exact. The Reduce input depends on the
    summaries and is given as its ceiling."""
    title = str(front_matter.get("titel", "") or "").strip() or _fallback_title(extraction)
    lang = (lang or str(front_matter.get("sprache", "") or "").strip()
            or DEFAULT_ANALYSIS_LANG).lower()
    blocks, skipped = clean_blocks(extraction, title)
    units = library_units(blocks, title)
    has_pages = extraction.page_last > 0
    author = str(front_matter.get("autor", "") or "").strip()

    type_call = {"system_chars": len(_type_system()),
                 "user_chars": len(_type_user(title, units)) if units else 0}
    sys_sizes = [len(_summary_system(lang, t, has_pages)) for t in list(DOC_TYPES) + [""]]
    summary_calls = []
    for u in units:
        summary_calls.append({
            "unit": u.index,
            "user_chars": len(unit_document(u, units, title, lang, author, has_pages))
                          + len(_summary_task(units)),
            "system_chars_min": min(sys_sizes),
            "system_chars_max": max(sys_sizes)})
    reduce_call = {"system_chars": max(len(_reduce_system(lang, t)) for t in DOC_TYPES),
                   "user_chars_max": len(title) + len(author) + 60 + _REDUCE_SAMPLE_CAP}

    image_calls = []
    references = figure_references(extraction.blocks)
    for f in [b for u in units for b in u.blocks if b.kind == "figure" and b.describe]:
        path = (extraction.figures_dir / f.image) if (extraction.figures_dir and f.image) else None
        image_calls.append({"figure": _figure_ident(f, lang), "page": f.page,
                            "image": f.image,
                            "bytes": path.stat().st_size if path and path.is_file() else None,
                            "prompt_chars": len(_figure_prompt(f, lang, references.get(f.seq, "")))})

    # The review: one call per unit with a summary, its input the unit's
    # document (the one the summary call was sent), the instructions, the
    # text layer of its pages with an unrepaired order finding, and the
    # summary. The summary is not known before the summary call; its ceiling
    # here is the length of the unit's source text.
    review_calls = []
    layer_pages = extraction.order_layer()
    for u in units:
        src = render_blocks(u.blocks, lang, page_markers=has_pages, figure_markers=False)
        document = unit_document(u, units, title, lang, author, has_pages)
        layer = _unit_layer(u, layer_pages, lang)
        review_calls.append({"unit": u.index, "layer_chars": len(layer),
                             "input_chars_max": knowledge_review.plan_section_chars(
                                 len(document), has_pages, len(layer)) + len(src)})

    llm_input = (type_call["system_chars"] + type_call["user_chars"]
                 + sum(c["user_chars"] + c["system_chars_max"] for c in summary_calls)
                 + reduce_call["system_chars"] + reduce_call["user_chars_max"])
    review_input = sum(c["input_chars_max"] for c in review_calls)
    return {
        "title": title, "lang_assumed": lang, "pages": extraction.pages,
        "page_numbering": extraction.page_numbering(),
        "blocks_after_cleaning": len(blocks), "skipped": skipped,
        "bibliography_entries": sum(len(b.entries) for b in bibliography(extraction)),
        "units": [_unit_summary(u) for u in units],
        "type_call": type_call, "summary_calls": summary_calls, "reduce_call": reduce_call,
        "image_calls": image_calls, "review_calls": review_calls,
        "totals": {
            "llm_calls": (1 + len(summary_calls) + 1) if units else 0,
            "review_calls": len(review_calls),
            # A review answer that is not the JSON object asked for is sent
            # back once (knowledge_review.review_section).
            "review_repair_calls_max": len(review_calls),
            "review_input_chars_max": review_input,
            # A summary whose verbatim share is above the ceiling is sent back
            # once (_summarize_unit): at most one more call per unit, its
            # input the summary input plus the first answer.
            "revision_calls_max": len(summary_calls),
            "llm_input_chars_max": llm_input if units else 0,
            "image_calls": len(image_calls),
            "image_bytes": sum(c["bytes"] or 0 for c in image_calls),
            "image_prompt_chars": sum(c["prompt_chars"] for c in image_calls),
        },
    }


# ===========================================================================
# 9) Figures: one image-model call per figure
# ===========================================================================

# The passage that refers to a figure goes into its description call at most
# this long, cut around the reference.
FIGURE_REFERENCE_MAX_CHARS = 800


def _figure_number_re(figure_no: str) -> Optional["re.Pattern"]:
    m = re.match(r"\s*(\d+)", figure_no or "")
    if not m:
        return None
    return re.compile(
        r"(?:^|[\s(\[])(?:Abb(?:ildung)?|Fig(?:ure|s)?|Figs?\.|Grafik|Bild|Image)\.?\s*"
        + m.group(1) + r"(?!\d)", re.IGNORECASE)


def figure_references(blocks: List[Block]) -> Dict[int, str]:
    """{figure seq: the paragraph that refers to it}, for the numbered
    figures: of the paragraphs that name the figure's label and number, the
    one nearest to the figure in the reading order (a book numbers its
    figures anew in every chapter). A long paragraph is cut to
    FIGURE_REFERENCE_MAX_CHARS around the reference. An unnumbered figure
    has no reference."""
    paras = [(i, b) for i, b in enumerate(blocks)
             if b.kind in ("paragraph", "list_item", "footnote") and b.text]
    out: Dict[int, str] = {}
    for fi, fig in enumerate(blocks):
        if fig.kind != "figure" or not fig.figure_no:
            continue
        rx = _figure_number_re(fig.figure_no)
        if rx is None:
            continue
        best: Optional[Tuple[int, str, int]] = None
        for i, b in paras:
            m = rx.search(b.text)
            if m and (best is None or abs(i - fi) < best[0]):
                best = (abs(i - fi), b.text, m.start())
        if best is None:
            continue
        _, text, at = best
        if len(text) > FIGURE_REFERENCE_MAX_CHARS:
            half = FIGURE_REFERENCE_MAX_CHARS // 2
            lo = max(0, min(at - half, len(text) - FIGURE_REFERENCE_MAX_CHARS))
            text = (("…" if lo else "") + text[lo:lo + FIGURE_REFERENCE_MAX_CHARS].strip()
                    + ("…" if lo + FIGURE_REFERENCE_MAX_CHARS < len(text) else ""))
        out[fig.seq] = text
    return out


def _figure_prompt(fig: Block, lang: Optional[str], reference: str = "") -> str:
    """The description call of one figure. The image model describes what
    the picture shows; the caption and the passage that refers to the figure
    go along to say which figure it is, not as a source for the description."""
    caption = (fig.caption or "").strip()
    language = _lang_display(lang or DEFAULT_ANALYSIS_LANG)
    parts = [
        f"Describe this picture from a document. Write in {language}, the "
        "language of the document, two to five sentences.",
        "Describe only what is visible in the picture: what kind of picture it is "
        "(photograph, drawing, screenshot, diagram, chart, table, …) and what it "
        "shows. Add nothing the picture does not show: no speech bubbles, labels, "
        "people or objects that are not there.",
        "Text in the picture: quote a word or a line, as written, only where every "
        "letter of it is legible. Where text is there but not legible, say that it "
        "is not legible; do not complete or guess it.",
        "No interpretation, no evaluation, no statement about what the picture means.",
    ]
    if caption or reference:
        parts.append("For orientation only, what the document says about this "
                     "figure. It tells which figure this is; it is not a source for "
                     "your description, which must be visible in the picture itself.")
        if caption:
            parts.append(f"Caption: \"{caption}\"")
        if reference:
            parts.append(f"Passage referring to the figure: \"{reference}\"")
    return "\n\n".join(parts)


def figure_model(condensing: Optional[str] = None) -> Tuple[str, str]:
    """The image model for the figure descriptions, and where it comes from:
    KNOWLEDGE_IMAGE_MODEL when set; else the condensing model (`condensing`,
    else KNOWLEDGE_PROCESSING_MODEL) when Settings measured it reading an
    image (vision_support.is_vision_capable); else IMAGE_ANALYSIS_MODEL.
    Read at call time.

    The figures of the library are pictures from publications, not personal
    data, and may be described online, by the condensing model where it
    reads images (docs/DEVELOPMENT_DECISIONS.md). A condensing model that reads
    none (GLM 5.3) leaves the figures to KNOWLEDGE_IMAGE_MODEL, which an
    operator sets by hand, or to the local IMAGE_ANALYSIS_MODEL."""
    import config
    from my_app.utils.vision_support import is_vision_capable

    explicit = (getattr(config, "KNOWLEDGE_IMAGE_MODEL", "") or "").strip()
    if explicit:
        return explicit, "KNOWLEDGE_IMAGE_MODEL"
    condensing = (condensing or getattr(config, "KNOWLEDGE_PROCESSING_MODEL", "") or "").strip()
    if condensing and is_vision_capable(condensing):
        return condensing, "the condensing model, measured reading images"
    return (getattr(config, "IMAGE_ANALYSIS_MODEL", "") or "").strip(), "IMAGE_ANALYSIS_MODEL"


def _describe_figure_online(model: str, prompt: str, image_b64: str) -> str:
    """One figure described by a model outside this machine: the platform's
    chat helper, pinned to `model` (one attempt, no fallback chain), with
    the picture itself (may_leave_server: a figure of a publication, not
    personal data). No temperature is named, so a chat-completions provider is
    sent the helper's 0.7, the temperature of the local path
    (analyze_image), and the messages dialect is sent none."""
    from my_app.routes.chat_routes import call_chat_helper

    result = call_chat_helper(messages=[{"role": "user", "content": prompt}],
                              model_override=model, image_b64=image_b64,
                              may_leave_server=True)
    return ((result or {}).get("content") or "").strip()


def describe_figures(extraction: Extraction, lang: Optional[str],
                     model: Optional[str] = None,
                     timings: Optional[List[Dict[str, Any]]] = None) -> Dict[int, str]:
    """One image-model call per figure to describe (Extraction.
    figures_to_describe; the model is `model`, else figure_model). A local
    model is asked through the platform's image-analysis path
    (utils/image_analysis.analyze_image), a model outside this machine
    through the chat helper with the picture (_describe_figure_online). The
    call carries the figure's
    caption and the passage that refers to it (figure_references). Returns
    {figure seq: description}; a figure whose file is missing or whose call
    fails is left out and stays pending. `timings`, when given, receives one entry per call: the figure's
    file, seconds, and whether it was described.

    A model outside this machine that Settings has not measured reading an
    image is refused before the first call: the chat helper would hand such
    a model a description by the local image model in place of the picture,
    and the library would keep a description of a description.

    The lease (rule 15): a local image model is one prompt of ComfyUI's node,
    and comfyui_ws_client takes the gate's lease around every prompt it
    queues, load and forward in one admission. Inside the DevServer that is
    the platform's gate, and no lease is taken here: the gate has one slot,
    and a lease held around the loop would wait on itself at the first
    call. A process outside the DevServer takes the DevServer's lease over
    HTTP around this call (gpu_lease_remote.gpu_lease_remote,
    scripts/knowledge_run.py).

    The picture goes through the shared envelope of the vision channel
    (media_ref.encode_image_b64: RGB, 64 to 768 px, JPEG): Docling exports
    figures at twice their printed size, and an oversized bitmap is what
    has taken the runner down before."""
    from my_app.services.model_capabilities import is_local
    from my_app.utils.image_analysis import analyze_image
    from my_app.utils.media_ref import encode_image_b64
    from my_app.utils.vision_support import is_vision_capable

    model = model or figure_model()[0] or None
    online = bool(model) and not is_local(model)
    if online and not is_vision_capable(model):
        raise ValueError(f"{model} is not recorded as reading images (Settings, model "
                         f"capabilities): measure it there, or name another image model")
    references = figure_references(extraction.blocks)
    out: Dict[int, str] = {}
    for fig in extraction.figures_to_describe():
        if not (extraction.figures_dir and fig.image):
            continue
        path = extraction.figures_dir / fig.image
        if not path.is_file():
            logger.warning("[KNOWLEDGE-PROC] figure file missing: %s", path)
            continue
        started = time.monotonic()
        text = ""
        try:
            prompt = _figure_prompt(fig, lang, references.get(fig.seq, ""))
            if online:
                text = _describe_figure_online(model, prompt, encode_image_b64(path))
            else:
                data_url = "data:image/jpeg;base64," + encode_image_b64(path)
                text = analyze_image(data_url, prompt=prompt, model=model, lang=lang, level=None)
        except Exception as e:  # noqa: BLE001 - one figure must not end the run
            logger.warning("[KNOWLEDGE-PROC] figure %s not described: %s", fig.image, e)
        if timings is not None:
            timings.append({"image": fig.image, "seconds": round(time.monotonic() - started, 2),
                            "described": bool((text or "").strip())})
        if (text or "").strip():
            out[fig.seq] = text.strip()
    return out
