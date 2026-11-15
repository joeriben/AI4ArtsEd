"""
Adversarial review of a summary (knowledge library, step after the checks).

The checks in knowledge_checks count what can be counted: list items, figures,
page references, the verbatim share. What they cannot see is whether the
summary says what the source says and keeps what matters. For that a second
set of model calls reads, per unit (the whole document, or one part of a
document too long for one call), the source and the summary written for it,
with the instruction to REFUTE the summary: to list what essential it leaves
out (the thesis, the concepts the document introduces, the cases and works it
discusses, instructions and enumerations), what it distorts, and what it adds
that the source does not say. Which page a statement is assigned to is not
reviewed (2026-11-13, issue #139).

Every finding carries a severity. `material`: a reader who works only from the
summary would act, teach or cite wrongly, or would miss something they need;
`minor`: everything else the reviewer reports. The review passes when no unit
has a material finding and every unit has been answered. A unit the reviewer
does not answer with a usable JSON object (after one repair request) counts as
not reviewed, and the review fails.

The verdict is written into the front matter (`review: passed` or
`review: failed: …`) and, in full, into the `<doc_id>.checks.json` sidecar
under `review`, where the retention step (knowledge_retention) reads
`review.passed`. A failed review holds the document in draft
(knowledge_processing.process_document).

The reviewer uses the same LLM path as the summary (role
KNOWLEDGE_PROCESSING_MODEL) unless the caller passes another function. Each
review call sends the unit's source first, as the same bytes the summary
call sent (knowledge_processing.unit_document), so a provider with prompt
caching reads it from the cache the summary call wrote (ask,
knowledge_processing.default_llm_fn; 2026-11-14). The
image descriptions in a unit are the image model's text, written from the
picture alone; they are checked against what the source itself says a figure
shows (its caption, the text that refers to it), and a contradiction is a
distortion.

A unit whose pages carry an unrepaired reading-order finding of the
extraction (knowledge_extract.check_reading_order) goes to the reviewer with
the text layer of those pages beside the source (`ReviewSection.layer`,
pdftotext): a second reading of the same pages. Where the order of the
extraction changes what a sentence or a list says, the reviewer reports an
`order` finding. It is material, and the review fails, when it quotes the
summary, i.e. the summary carries the changed meaning; without a summary
quote it is minor (2026-11-15, issue #140, finding_severity). A difference
in order alone is no finding.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

LlmFn = Callable[[str, str, Optional[int]], Optional[str]]

MATERIAL = "material"
MINOR = "minor"
FINDING_KINDS = ("omissions", "distortions", "additions", "order")
# Kinds whose severity follows from the finding, not from the reviewer: an
# order finding is material when it quotes the summary (finding_severity).
_ALWAYS_MATERIAL = ("order",)
_QUOTE_MAX_CHARS = 400


@dataclass
class ReviewSection:
    """One unit to review: the source unit as the summary call read it, and
    the summary written for it."""
    index: int
    heading: str                   # source heading and pages (Unit.source_span)
    # The unit's source as the summary call was given it, byte for byte
    # (knowledge_processing.unit_document): title line, part line, the
    # rendered text with page markers. Sent first, under the cache marker,
    # so the review reads from the provider's cache what the summary wrote
    # to it (ask).
    document: str
    output: str                    # the unit's summary as WISSEN carries it
    page_from: int = 0
    page_to: int = 0
    image_descriptions: List[str] = field(default_factory=list)
    # The text layer (pdftotext) of the section's pages that carry an
    # unrepaired reading-order finding, with page markers; empty otherwise.
    layer: str = ""


@dataclass
class SectionReview:
    index: int
    section: str
    answered: bool
    omissions: List[Dict[str, Any]] = field(default_factory=list)
    distortions: List[Dict[str, Any]] = field(default_factory=list)
    additions: List[Dict[str, Any]] = field(default_factory=list)
    order: List[Dict[str, Any]] = field(default_factory=list)

    def findings(self) -> List[Dict[str, Any]]:
        return [dict(f, kind=k) for k in FINDING_KINDS for f in getattr(self, k)]

    @property
    def material(self) -> int:
        return sum(1 for f in self.findings() if f.get("severity") == MATERIAL)


@dataclass
class ReviewVerdict:
    reviewer: str
    sections: List[SectionReview]
    at: str = ""

    @property
    def unanswered(self) -> List[str]:
        return [s.section for s in self.sections if not s.answered]

    @property
    def passed(self) -> bool:
        return bool(self.sections) and not self.unanswered \
            and all(s.material == 0 for s in self.sections)

    def counts(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for k in FINDING_KINDS:
            items = [f for s in self.sections for f in getattr(s, k)]
            out[k] = {MATERIAL: sum(1 for f in items if f.get("severity") == MATERIAL),
                      MINOR: sum(1 for f in items if f.get("severity") != MATERIAL)}
        return out

    def note(self) -> str:
        if not self.sections:
            return "no section to review"
        c = self.counts()
        parts = [f"{k}: {v[MATERIAL]} material, {v[MINOR]} minor" for k, v in c.items()]
        if self.unanswered:
            parts.append(f"not reviewed: {len(self.unanswered)} section(s) without a usable answer")
        return "; ".join(parts)

    def label(self, cap: int = 400) -> str:
        """The front-matter value: `passed`, or `failed: <counts>`."""
        if self.passed:
            return "passed"
        c = self.counts()
        material = {k: v[MATERIAL] for k, v in c.items() if v[MATERIAL]}
        text = "failed: " + ", ".join(f"{n} material {k}" for k, n in material.items())
        if self.unanswered:
            text += ("; " if material else "") + f"{len(self.unanswered)} section(s) not reviewed"
        if not self.sections:
            text = "failed: no section to review"
        return text if len(text) <= cap else text[: cap - 1] + "…"

    def to_dict(self) -> Dict[str, Any]:
        """The sidecar's `review` entry. `passed`, `reviewer`, `note` and `at`
        have the shape knowledge_checks.record_review writes, so the retention
        step reads both alike."""
        return {"passed": self.passed, "reviewer": self.reviewer, "kind": "model",
                "note": self.note(), "at": self.at, "label": self.label(cap=10_000),
                "counts": self.counts(),
                "sections": [asdict(s) for s in self.sections]}


def _system(has_pages: bool, has_layer: bool = False) -> str:
    rules = [
        "You review the summary of a document, or of one part of a long document, "
        "for the knowledge library of an arts-education platform. Teachers, "
        "educators and researchers work from the summary and cite the document. "
        "Your task is to REFUTE the summary: compare it with the source and find "
        "where it fails the source.",
        "Report three kinds of finding:\n"
        "- omissions: something essential of the source that the summary leaves "
        "out: the purpose or thesis, a step of the argument that what follows "
        "depends on, a concept the document introduces or defines, a case, example "
        "or work it discusses, an instruction, a step or an item of an enumeration, "
        "a number that matters for what the source says.\n"
        "- distortions: statements of the summary that say something other than "
        "the source (changed meaning, wrong attribution of a view to a person or to "
        "the authors, wrong number, a hedged claim made firm or a firm one hedged, a "
        "causal or evaluative shift).\n"
        "- additions: statements of the summary that are not in the source "
        "(interpretation, evaluation, background knowledge, generalisation the source "
        "does not make).",
        "Do not report: detail left out whose substance the summary carries; "
        "wording and style; the order of statements; the wording of a heading; "
        "which page a statement of the summary is assigned to.",
        "Figure lines: in the summary, the text after the dash in a figure line is "
        "a description an image model wrote from the picture alone. Check it "
        "against what the source says the figure shows, in its caption and in the "
        "text that refers to it: where the description contradicts the source "
        "(another object, other words or numbers in the picture, another kind of "
        "picture), report a distortion that quotes the description as \"summary\" "
        "and the caption or passage as \"source\". Where the source says nothing "
        "about what the figure shows, do not report the description.",
        "Severity: \"material\" when a reader working only from the summary would "
        "act, teach or cite wrongly, or would miss something they need; \"minor\" "
        "otherwise.",
    ]
    if has_pages:
        rules.append("The source carries page markers such as \"[S. 5]\" or \"[p. 5]\": "
                     "what follows a marker stands on that page.")
    if has_layer:
        rules.append(
            "TEXT LAYER: the text layer of some pages of the source, as the PDF "
            "itself holds it, is given as a second reading of the same pages. The "
            "SOURCE is the extraction, which can have put a passage in another place "
            "on its page than the text layer has it. Report as \"order\" every place "
            "where the order of the extraction changes what a sentence or a list says "
            "(a sentence that runs on into another passage, a list item that stands "
            "under another item or another heading, a passage moved into a sentence "
            "it does not belong to), quoting the extraction as \"source\" and the text "
            "layer as \"layer\", and the summary as \"summary\" where it carries the "
            "changed meaning. A difference in order alone, which changes "
            "nothing a sentence or list says, is no finding. An order finding that "
            "quotes the summary is always material.")
    rules += [
        "Each finding quotes the passage concerned, at most 40 words, in its own "
        "language, and gives the source page where the source has one.",
        "Answer ONLY with a JSON object:\n"
        "{\"omissions\": [{\"source\": \"<quote>\", \"page\": <n or null>, "
        "\"severity\": \"material|minor\"}],\n"
        " \"distortions\": [{\"summary\": \"<quote>\", \"source\": \"<quote>\", "
        "\"page\": <n or null>, \"severity\": \"material|minor\"}],\n"
        " \"additions\": [{\"summary\": \"<quote>\", \"severity\": \"material|minor\"}]"
        + (",\n \"order\": [{\"source\": \"<quote>\", \"layer\": \"<quote>\", "
           "\"summary\": \"<quote or empty>\", \"page\": <n or null>, "
           "\"severity\": \"material\"}]" if has_layer else "")
        + "}\n"
        "Use empty lists where there is nothing to report.",
    ]
    return "\n\n".join(rules)


def ask(llm: LlmFn, system: str, user: str, document: str = "",
        cache_ttl: str = "") -> Optional[str]:
    """One call that puts `document` before the instructions. An LLM function
    that says it takes a document (`takes_document`, as
    knowledge_processing.default_llm_fn does) is given it apart, to send it
    as the cached opening block; any other gets it in front of `user`, so
    every function sees the same text in the same order."""
    if document and getattr(llm, "takes_document", False):
        return llm(system, user, None, document=document, cache_ttl=cache_ttl)
    return llm(system, document + user, None)


def _user(section: ReviewSection) -> str:
    """What follows the document: the image descriptions, the text layer
    where there is one, and the summary under review."""
    parts: List[str] = []
    if section.image_descriptions:
        parts += ["=== IMAGE DESCRIPTIONS (image model; checked against the source) ===",
                  "\n".join(section.image_descriptions)]
    if section.layer:
        parts += ["=== TEXT LAYER (second reading of the same pages; for the order check) ===",
                  section.layer]
    parts += ["=== SUMMARY ===", section.output]
    return "\n\n".join(parts)


def _quote(v: Any) -> str:
    s = str(v or "").strip()
    return s if len(s) <= _QUOTE_MAX_CHARS else s[: _QUOTE_MAX_CHARS - 1] + "…"


def _page(v: Any) -> Optional[int]:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def finding_severity(kind: str, severity: str, finding: Dict[str, Any]) -> str:
    """The severity a finding counts with. An `order` finding is material
    when it quotes the summary, i.e. the summary carries the meaning the
    extraction's order changed; without a summary quote it concerns the
    extraction alone, and the summary that gives the source right is not
    held for it (2026-11-15, issue #140). Every other finding keeps the
    reviewer's severity."""
    if kind in _ALWAYS_MATERIAL:
        return MATERIAL if str(finding.get("summary") or "").strip() else MINOR
    return MATERIAL if severity == MATERIAL else MINOR


def _clean(kind: str, items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for it in items:
        if not isinstance(it, dict):
            continue
        sev = str(it.get("severity", "")).strip().lower()
        f: Dict[str, Any] = {}
        for key in ("source", "summary", "layer"):
            if key in it:
                f[key] = _quote(it[key])
        f["severity"] = finding_severity(kind, sev, f)
        if "page" in it:
            f["page"] = _page(it["page"])
        if any(f.get(k) for k in ("source", "summary")):
            out.append(f)
    return out


def _parse(obj: Any) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    if not isinstance(obj, dict) or not any(k in obj for k in FINDING_KINDS):
        return None
    return {k: _clean(k, obj.get(k)) for k in FINDING_KINDS}


def review_section(section: ReviewSection, llm: LlmFn, *, has_pages: bool,
                   cache_ttl: str = "") -> SectionReview:
    """One review call for one section, with ONE repair request on a JSON miss.
    Both send the section's document first (ask), the one the summary call
    was sent, so both read it from the provider's cache."""
    from my_app.services.knowledge_processing import _extract_json_object
    system = _system(has_pages, bool(section.layer))
    user = _user(section)
    parsed = _parse(_extract_json_object(
        ask(llm, system, user, section.document, cache_ttl)))
    if parsed is None:
        repair = user + ("\n\n---\nYour last answer was not the JSON object asked for. "
                         "Answer NOW only with {\"omissions\": […], \"distortions\": […], "
                         "\"additions\": […]"
                         + (", \"order\": […]" if section.layer else "") + "}.")
        parsed = _parse(_extract_json_object(
            ask(llm, system, repair, section.document, cache_ttl)))
    if parsed is None:
        logger.warning("[KNOWLEDGE-REVIEW] no usable answer for %s", section.heading)
        return SectionReview(index=section.index, section=section.heading, answered=False)
    return SectionReview(index=section.index, section=section.heading, answered=True, **parsed)


def review_document(sections: Sequence[ReviewSection], llm: LlmFn, *,
                    has_pages: bool, workers: int = 1, cache_ttl: str = "",
                    progress: Optional[Callable[[str], None]] = None) -> ReviewVerdict:
    """Review every section (in `workers` calls at once) and return the
    verdict. The reviewer named is the model(s) that served the calls
    (`llm.models_used`, as for the condensation), else `model`. `cache_ttl`
    is the lifetime of the cache marker on each section's document (ask)."""
    def log(msg: str) -> None:
        logger.info("[KNOWLEDGE-REVIEW] %s", msg)
        if progress:
            try:
                progress(msg)
            except Exception:  # noqa: BLE001 - logging never breaks a run
                pass

    results: List[SectionReview] = []
    if workers > 1 and len(sections) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="kp-review") as pool:
            futures = [pool.submit(review_section, s, llm, has_pages=has_pages,
                                   cache_ttl=cache_ttl)
                       for s in sections]
            for i, fut in enumerate(futures, 1):
                results.append(fut.result())
                log(f"geprüft {i}/{len(sections)}: {sections[i - 1].heading}")
    else:
        for i, s in enumerate(sections, 1):
            log(f"Gegenprüfung {i}/{len(sections)}: {s.heading}")
            results.append(review_section(s, llm, has_pages=has_pages, cache_ttl=cache_ttl))
    models = list(dict.fromkeys(getattr(llm, "models_used", None) or []))
    verdict = ReviewVerdict(reviewer="model: " + (", ".join(models) or "unknown"),
                            sections=results,
                            at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    log(f"Gegenprüfung: {verdict.label()} ({verdict.note()})")
    return verdict


def plan_section_chars(document_chars: int, has_pages: bool,
                       layer_chars: int = 0) -> int:
    """Input characters of one review call before the condensation is known:
    the section's document (knowledge_processing.unit_document), the
    instructions, the frame and the text layer of the pages with an order
    finding. The condensation adds its own length on top (see
    knowledge_processing.plan_document)."""
    frame = _user(ReviewSection(0, "", "", "", layer="x" * layer_chars))
    return len(_system(has_pages, bool(layer_chars))) + 2 + len(frame) + document_chars


def findings_text(verdict: Dict[str, Any]) -> str:
    """The sidecar's review entry as plain lines, one per finding, for logs
    and reports."""
    lines: List[str] = []
    for s in verdict.get("sections") or []:
        head = s.get("section") or "(no heading)"
        if not s.get("answered"):
            lines.append(f"[{head}] NOT REVIEWED (no usable answer)")
            continue
        for k in FINDING_KINDS:
            for f in s.get(k) or []:
                rest = {x: f[x] for x in f if x != "severity"}
                lines.append(f"[{head}] {k} ({f.get('severity')}): "
                             + json.dumps(rest, ensure_ascii=False))
    return "\n".join(lines)
