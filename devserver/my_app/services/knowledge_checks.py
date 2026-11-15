"""Checks on a condensed knowledge document, run in code after every condensation.

Two kinds, kept apart and never argued for each other:

* COPYRIGHT -- one quantity only: the share of the output that runs word for
  word with the source (runs of at least KNOWLEDGE_VERBATIM_MIN_WORDS words),
  against a ceiling KNOWLEDGE_VERBATIM_MAX_SHARE. Marked short quotations
  count toward the share like any other verbatim run.
* QUALITY -- what code can tell about a summary without reading it: every
  unit has its summary, every list keeps its items, every figure stands with
  its description, every `###` section names its pages and every page
  reference exists, the extraction has no unrepaired gaps. Numbers and source
  headings missing from the summary are listed and counted, not gated
  (2026-11-13), and so are list items (2026-11-15, issue #140): whether what
  is missing matters is the review's judgement (knowledge_review).

A failed check keeps the document a draft (knowledge_processing.process_document
writes the label into the front matter key `checks` and the full report into
the `<doc_id>.checks.json` sidecar).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from my_app.services.knowledge_extract import Block, IntegrityReport, skeleton

COPYRIGHT = "copyright"
QUALITY = "quality"


@dataclass
class SectionPair:
    """One unit of the source and the section the condensation wrote for it."""
    index: int
    heading: str
    source_blocks: List[Block]
    output: str                       # the section as written: `### ` line + body
    page_from: int = 0
    page_to: int = 0
    missing: bool = False
    figure_idents: List[str] = field(default_factory=list)


@dataclass
class CheckResult:
    name: str
    kind: str                         # COPYRIGHT or QUALITY
    passed: bool
    summary: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    value: Optional[float] = None
    limit: Optional[float] = None


@dataclass
class CheckReport:
    results: List[CheckResult]

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed(self) -> List[CheckResult]:
        return [r for r in self.results if not r.passed]

    def label(self, cap: int = 400) -> str:
        """The front-matter value: `passed`, or `failed: <check> (<summary>); …`."""
        if self.passed:
            return "passed"
        text = "failed: " + "; ".join(f"{r.name} ({r.summary})" for r in self.failed)
        return text if len(text) <= cap else text[: cap - 1] + "…"

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "label": self.label(cap=10_000),
                "results": [asdict(r) for r in self.results]}


def write_sidecar(path: Path, report: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> None:
    """Write `<doc_id>.checks.json` beside the library file: the report
    (CheckReport.to_dict()) plus whatever the caller adds (doc type, units,
    the integrity report). The retention step reads `passed` from it."""
    data = dict(report)
    if extra:
        data.update(extra)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def sidecar_path(library_file: Path) -> Path:
    """`<doc_id>.md` -> `<doc_id>.checks.json` in the same folder."""
    p = Path(library_file)
    return p.with_name(p.stem + ".checks.json")


def read_sidecar(path: Path) -> Optional[Dict[str, Any]]:
    """The sidecar's content, or None when there is none or it is unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def record_review(path: Path, passed: bool, reviewer: str, note: str = "",
                  at: str = "") -> Dict[str, Any]:
    """Record the adversarial review of a condensation in its sidecar (key
    `review`). A new condensation writes a new sidecar without one, so a
    review always belongs to the file it was made on. Raises FileNotFoundError
    when the document has no sidecar (it has not been through the checks)."""
    from datetime import datetime, timezone
    data = read_sidecar(path)
    if data is None:
        raise FileNotFoundError(f"no checks sidecar at {path}")
    data["review"] = {
        "passed": bool(passed), "reviewer": reviewer, "note": note,
        "at": at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data["review"]


# --------------------------------------------------------------------------
# Copyright: verbatim share
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _source_grams(source_text: str, n: int) -> set:
    src = _tokens(source_text)
    return {tuple(src[i:i + n]) for i in range(len(src) - n + 1)}


def _runs_of(flags: List[bool]) -> List[tuple]:
    """The runs of set flags as (length, start, end)."""
    runs: List[tuple] = []
    start = None
    for i, c in enumerate(flags + [False]):
        if c and start is None:
            start = i
        elif not c and start is not None:
            runs.append((i - start, start, i))
            start = None
    return runs


def _verbatim_runs(grams: set, out: List[str], n: int) -> tuple:
    """(covered flags, runs as (length, start, end)) of the output tokens that
    stand in an n-gram of the source."""
    covered = [False] * len(out)
    for i in range(len(out) - n + 1):
        if tuple(out[i:i + n]) in grams:
            for j in range(i, i + n):
                covered[j] = True
    return covered, _runs_of(covered)


def source_list_text(blocks: Sequence[Block]) -> str:
    """The text of the source's lists, the lists of two or more items as the
    list check takes them (_source_lists), one item per line. A run of the
    output that stands in this text is left out of the verbatim share
    (Projektleitung, 13.11.2026: „Listen raus aus der Zählung“)."""
    return "\n\n".join("\n".join(b.text for b in run) for run in _source_lists(blocks))


def _list_flags(list_text: str, out: List[str], n: int) -> List[bool]:
    """The output tokens that stand in a run of at least n words of the
    source's lists."""
    grams = _source_grams(list_text, n) if list_text else set()
    return _verbatim_runs(grams, out, n)[0] if grams else [False] * len(out)


def check_verbatim_share(source_text: str, output_text: str, min_words: int,
                         max_share: float, excluded: Sequence[str] = (),
                         list_text: str = "") -> CheckResult:
    """Share of output words that stand in a run of at least `min_words` words
    occurring in the same order in the source. Reported with the longest run
    and the five longest runs. `excluded` names the parts the caller left
    out of `output_text`, each as the summary is to name it (the source's
    bibliography, kept verbatim as reference data; the figure
    descriptions); the summary says so. `list_text` is the text of the
    source's lists (source_list_text): output words in a run of it count
    neither as verbatim nor among the words, and the summary gives their
    number."""
    out = _tokens(_HTML_COMMENT_RE.sub("", output_text))
    n = max(1, int(min_words))
    grams = _source_grams(source_text, n)
    note = f"; not counted: {', '.join(excluded)}" if excluded else ""
    if not out or not grams:
        return CheckResult("verbatim_share", COPYRIGHT, True, "share 0.0%" + note, [],
                           0.0, max_share)
    covered, _runs = _verbatim_runs(grams, out, n)
    in_lists = _list_flags(list_text, out, n)
    counted = [c and not li for c, li in zip(covered, in_lists)]
    n_listed = sum(in_lists)
    words = len(out) - n_listed
    share = sum(counted) / words if words else 0.0
    runs = sorted(_runs_of(counted), reverse=True)
    findings = [{"words": length, "text": " ".join(out[s:e])[:300]}
                for length, s, e in runs[:5]]
    longest = runs[0][0] if runs else 0
    passed = share <= max_share
    if n_listed:
        note = f"; not counted: {n_listed} words from the source's lists" + note
    summary = (f"share {share:.1%} of {words} words, ceiling {max_share:.0%}, "
               f"longest run {longest} words" + note)
    return CheckResult("verbatim_share", COPYRIGHT, passed, summary, findings,
                       round(share, 4), max_share)


_QUOTED_RE = re.compile(r"„[^“”\n]*[“”]|“[^”\n]*”|\"[^\"\n]*\"|«[^»\n]*»|»[^«\n]*«")


def unmarked_verbatim(source_text: str, output_text: str, min_words: int,
                      quoted: bool = False, list_text: str = "") -> List[str]:
    """The runs of at least `min_words` words of the output that stand as they
    stand in the source although they are not a heading line, longest first;
    runs inside quotation marks are left out unless `quoted` is set, and so
    are the words that stand in the source's lists (`list_text`, as
    check_verbatim_share leaves them out). Not a check: the input of a
    revision request. The check is `check_verbatim_share`, which counts
    quoted words as well -- a revision that has to bring the share down names
    them (`quoted=True`)."""
    n = max(1, int(min_words))
    grams = _source_grams(source_text, n)
    if not grams:
        return []
    found: List[tuple] = []
    for line in _HTML_COMMENT_RE.sub("", output_text).splitlines():
        if line.lstrip().startswith("#"):
            continue
        for segment in ([line] if quoted else _QUOTED_RE.split(line)):
            seg_tokens = _TOKEN_RE.findall(segment)
            low = [t.lower() for t in seg_tokens]
            covered, _runs = _verbatim_runs(grams, low, n)
            in_lists = _list_flags(list_text, low, n)
            counted = [c and not li for c, li in zip(covered, in_lists)]
            found += [(length, " ".join(seg_tokens[s:e])) for length, s, e in _runs_of(counted)]
    found.sort(key=lambda r: -r[0])
    return [text for _length, text in found]


# --------------------------------------------------------------------------
# Quality: lists
# --------------------------------------------------------------------------

_OUT_ITEM_RE = re.compile(r"^(?:([-*+•])|(\d+)[.)])\s+\S")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}")


def _source_lists(blocks: Sequence[Block]) -> List[List[Block]]:
    """The lists of a unit with two or more items. Items of one list_id form
    one list even where pictures or paragraphs stand between them: the
    extraction gives a numbered list Docling had split one list_id again
    (knowledge_extract.reunite_numbered_lists). A list item without a
    list_id belongs to the run of items it stands in."""
    lists: Dict[str, List[Block]] = {}
    order: List[str] = []
    prev: Optional[Block] = None
    anonymous = 0
    for b in blocks:
        if b.kind == "list_item":
            if b.list_id:
                key = b.list_id
            elif prev is not None and prev.kind == "list_item" and not prev.list_id:
                key = f"#run/{anonymous}"
            else:
                anonymous += 1
                key = f"#run/{anonymous}"
            if key not in lists:
                lists[key] = []
                order.append(key)
            lists[key].append(b)
        prev = b
    return [lists[k] for k in order if len(lists[k]) >= 2]


# Words that carry no content of a list item, for the item comparison: the
# frequent function words of the source languages, four letters or longer
# (shorter words are not compared at all).
_ITEM_STOPWORDS = frozenset("""
    aber alle allem allen aller alles also auch beim dann dass dein deine dem
    den denn der des dessen diese diesem diesen dieser dieses doch dort durch
    eine einem einen einer eines einige euch eure fuer haben hier ihre ihrem
    ihren ihrer indem jede jedem jeden jeder jedes kann kein keine koennen mehr
    mich mein meine nach nicht noch oder ohne sehr sein seine sich sind sowie
    ueber unter viel vom waehrend wann warum was weil welche wenn werden wird
    wieder wurde wurden zum zur zwischen
    about after also among been before being between both could does each from
    have here into more most much only other over should some such than that
    their them then there these they this those through under very what when
    where which while will with would your
    avec dans elle elles leur leurs mais nous pour sans sont sous tout tous
    vous cette celle ceux comme entre
    como esta este para pero por sobre todo todos una unos unas
""".split())

# Numbers written as words count as the number (KlappKLAUS: "die vier Felder"
# against "die 4 Felder").
_NUMBER_WORDS = {
    "zwei": "2", "drei": "3", "vier": "4", "fuenf": "5", "sechs": "6",
    "sieben": "7", "acht": "8", "neun": "9", "zehn": "10", "elf": "11",
    "zwoelf": "12", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12",
}
_ITEM_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
# Word stems are compared on their first letters: German compounds and
# inflection ("Binden" / "binden", "Ausdrucke" / "Ausdrucken") meet there.
_ITEM_STEM = 5


def _fold(word: str) -> str:
    w = unicodedata.normalize("NFKD", word.lower())
    w = (w.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
         .replace("ß", "ss"))
    return "".join(ch for ch in w if not unicodedata.combining(ch))


def item_terms(text: str) -> set:
    """The content terms of a list item: numbers (written as words or as
    digits) and the stems of words of four letters or more that are not
    function words."""
    terms = set()
    for raw in _ITEM_WORD_RE.findall(text or ""):
        w = _fold(raw)
        if w.isdigit():
            terms.add(str(int(w)))
        elif w in _NUMBER_WORDS:
            terms.add(_NUMBER_WORDS[w])
        elif len(w) >= 4 and w not in _ITEM_STOPWORDS:
            terms.add(w[:_ITEM_STEM])
    return terms


def _items_match(source_item: str, output_item: str) -> bool:
    """An output item answers a source item when they share a content term,
    or when the source item has none to compare ("Ja.", "1)")."""
    src = item_terms(source_item)
    return not src or bool(src & item_terms(output_item))


def _unmatched_items(run: Sequence[Block], items: Sequence[str]) -> List[int]:
    """The positions (0-based) of the source items that the output item in
    the same position does not answer."""
    return [k for k, (b, o) in enumerate(zip(run, items)) if not _items_match(b.text, o)]


def output_list_items(text: str) -> List[List[str]]:
    """The top-level Markdown lists in `text`, each as the texts of its items.
    A list goes on across blank lines when the next line is again a top-level
    item of the same kind (bullet or number); indented lines belong to the
    item above."""
    lines = text.splitlines()
    lists: List[List[str]] = []
    cur_kind: Optional[str] = None
    items: List[str] = []

    def _close() -> None:
        nonlocal cur_kind, items
        if cur_kind is not None:
            lists.append(items)
        cur_kind, items = None, []

    i = 0
    while i < len(lines):
        line = lines[i]
        m = _OUT_ITEM_RE.match(line)
        if m:
            kind = "bullet" if m.group(1) else "number"
            if cur_kind != kind:
                _close()
                cur_kind = kind
            items.append(line[m.end() - 1:].strip())
        elif not line.strip():
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = _OUT_ITEM_RE.match(lines[j]) if j < len(lines) else None
            if cur_kind is not None and not (nxt and ("bullet" if nxt.group(1) else "number") == cur_kind):
                _close()
        elif line.startswith((" ", "\t")) and cur_kind is not None:
            items[-1] += " " + line.strip()  # continuation or nested item
        elif cur_kind is not None:
            _close()
        i += 1
    _close()
    return lists


def output_lists(text: str) -> List[int]:
    """Item counts of the top-level Markdown lists in `text`."""
    return [len(items) for items in output_list_items(text)]


def _table_cells(table_md: str) -> List[str]:
    cells: List[str] = []
    for row in table_md.splitlines():
        if not row.strip().startswith("|") or _TABLE_SEP_RE.match(row.replace("|", "", 1)):
            continue
        cells += [c.strip() for c in row.strip().strip("|").split("|")]
    return [c for c in cells if c]


def check_lists(pairs: Sequence[SectionPair], compare_items: bool = True) -> CheckResult:
    """Every source list of two or more items reappears in its section as a
    top-level list with the same item count, and item by item: the output
    item in each position shares a content term with the source item in that
    position (item_terms: a number, or a word stem that is not a function
    word). Of the output lists of the right length, the one that answers the
    most items stands for the source list, so a list of the same length
    elsewhere in the section cannot stand in for one the answer broke up.
    `compare_items=False` (a condensation written in another language than
    the source) compares the count alone. A table of short cells (four words
    or fewer on average) is a list in grid form: every cell reappears.

    A count, not a gate (2026-11-15, issue #140): the check measures the
    form, and a list given as running text or a corrected typo in a cell
    counts as incomplete although the content is there. Whether an item that
    matters is missing is the review's question (knowledge_review, omissions)."""
    findings: List[Dict[str, Any]] = []
    n_lists = 0
    for p in pairs:
        out = output_list_items(p.output)
        counts = [len(items) for items in out]
        runs = _source_lists(p.source_blocks)
        n_lists += len(runs)
        # (unmatched items, run, output list) for every list of the right
        # length; the closest pairs are taken first.
        options = []
        for r, run in enumerate(runs):
            for i, items in enumerate(out):
                if len(items) == len(run):
                    bad = _unmatched_items(run, items) if compare_items else []
                    options.append((len(bad), r, i, bad))
        options.sort(key=lambda o: (o[0], o[1], o[2]))
        used: set = set()
        taken: Dict[int, tuple] = {}
        for n_bad, r, i, bad in options:
            if r in taken or i in used:
                continue
            taken[r] = (i, bad)
            used.add(i)
        for r, run in enumerate(runs):
            if r not in taken:
                findings.append({"section": p.heading, "page": run[0].page,
                                 "expected_items": len(run),
                                 "first_item": run[0].text[:80],
                                 "output_lists": counts})
                continue
            i, bad = taken[r]
            if bad:
                findings.append({"section": p.heading, "page": run[0].page,
                                 "expected_items": len(run),
                                 "first_item": run[0].text[:80],
                                 "output_lists": counts,
                                 "unanswered_items": [
                                     {"item": k + 1, "source": run[k].text[:80],
                                      "output": out[i][k][:80]} for k in bad]})
        out_sk = skeleton(p.output)
        for b in p.source_blocks:
            if b.kind != "table":
                continue
            cells = _table_cells(b.markdown or b.text)
            if not cells:
                continue
            words = sum(len(c.split()) for c in cells) / len(cells)
            if words > 4:
                continue
            n_lists += 1
            lost = [c for c in cells if len(skeleton(c)) >= 2 and skeleton(c) not in out_sk]
            if lost:
                findings.append({"section": p.heading, "page": b.page, "table_cells": len(cells),
                                 "missing_cells": lost[:20]})
    summary = (f"{len(findings)} of {n_lists} lists/tables incomplete (listed, not gated)"
               if findings else f"{n_lists} lists/tables complete")
    return CheckResult("lists", QUALITY, True, summary, findings)


# --------------------------------------------------------------------------
# Quality: numbers
# --------------------------------------------------------------------------

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\bdoi:\s*\S+|\b10\.\d{4,}/\S+", re.IGNORECASE)
_FIG_REF_RE = re.compile(
    r"\b(?:Abb(?:ildung)?|Fig(?:ure)?|Grafik|Bild|Tab(?:elle)?|Table)\.?\s*\d+\s*[a-z]?"
    r"(?:\s*[–-]\s*\d*\s*[a-z]?\b)?", re.IGNORECASE)
_PAGE_REF_RE = re.compile(r"\b(?:S\.|pp?\.|Seiten?)\s*\d+(?:\s*[–-]\s*\d+)?(?:\s*f{1,2}\.)?")
_CITATION_RE = re.compile(
    r"\((?=[^()]*\b(?:1[5-9]\d\d|20\d\d)[a-z]?\b)(?=[^()]*(?:\b[A-ZÄÖÜ][a-zäöüß]+|vgl|ebd|et al))[^()]*\)")
_NUMBER_KINDS = frozenset({"paragraph", "list_item", "heading", "table", "code", "formula"})


def _norm_number(n: str) -> str:
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", n):
        return n.replace(".", "").replace(",", "").lstrip("0") or "0"
    n = n.replace(",", ".")
    if "." not in n:
        return n.lstrip("0") or "0"
    return n


def numbers_in(text: str) -> set:
    return {_norm_number(m) for m in _NUM_RE.findall(text)}


def source_numbers(blocks: Sequence[Block]) -> Dict[str, int]:
    """The numbers a unit's source states, with the page of first occurrence.
    Not counted: figure and page references, citation parentheses with a
    year, URLs and DOIs, footnotes and figure captions."""
    found: Dict[str, int] = {}
    for b in blocks:
        if b.kind not in _NUMBER_KINDS:
            continue
        text = b.markdown or b.text if b.kind == "table" else b.text
        for rx in (_URL_RE, _CITATION_RE, _FIG_REF_RE, _PAGE_REF_RE):
            text = rx.sub(" ", text)
        for n in numbers_in(text):
            found.setdefault(n, b.page)
    return found


def check_numbers(pairs: Sequence[SectionPair]) -> CheckResult:
    """A count, not a gate (2026-11-13): the numbers of a unit's source that
    do not appear in its summary. A summary keeps the numbers that matter,
    not every number; whether one that matters is missing is the review's
    question (knowledge_review, omissions)."""
    findings: List[Dict[str, Any]] = []
    total = 0
    for p in pairs:
        src = source_numbers(p.source_blocks)
        total += len(src)
        have = numbers_in(p.output)
        lost = sorted((n for n in src if n not in have), key=lambda n: (src[n], n))
        for n in lost:
            findings.append({"section": p.heading, "page": src[n], "number": n})
    summary = (f"{len(findings)} of {total} numbers of the source not in the summary "
               "(listed, not gated)" if findings else f"{total} numbers present")
    return CheckResult("numbers", QUALITY, True, summary, findings, float(len(findings)))


# --------------------------------------------------------------------------
# Quality: headings and units
# --------------------------------------------------------------------------

_INNER_HEADING_RE = re.compile(r"^#{3,4}\s+(.*\S)\s*$", re.MULTILINE)


def check_headings(pairs: Sequence[SectionPair]) -> CheckResult:
    """Every unit has its summary; that is the gate. The headings of the
    source that do not stand in the summary as a heading line are listed and
    do not fail the check (2026-11-13): the summary follows the document's
    structure in its own sections, not heading by heading."""
    findings: List[Dict[str, Any]] = []
    missing = 0
    total = 0
    for p in pairs:
        if p.missing:
            missing += 1
            findings.append({"section": p.heading, "page": p.page_from, "missing_section": True})
            continue
        lines_sk = skeleton(" ".join(_INNER_HEADING_RE.findall(p.output)))
        for b in p.source_blocks:
            if b.kind != "heading":
                continue
            total += 1
            if skeleton(b.text) not in lines_sk:
                findings.append({"section": p.heading, "page": b.page, "heading": b.text})
    parts = []
    if missing:
        parts.append(f"{missing} of {len(pairs)} units without a summary")
    if len(findings) > missing:
        parts.append(f"{len(findings) - missing} of {total} source headings not a "
                     "heading line (listed, not gated)")
    summary = "; ".join(parts) if parts else f"{len(pairs)} units, {total} headings present"
    return CheckResult("headings", QUALITY, not missing, summary, findings)


# --------------------------------------------------------------------------
# Quality: figures
# --------------------------------------------------------------------------

def check_figures(pairs: Sequence[SectionPair],
                  wrong_language: Sequence[Dict[str, Any]] = ()) -> CheckResult:
    """Every figure of a unit stands in that unit's section, and its
    description is in the language of the source (`wrong_language`: the
    figures whose description is not, from
    knowledge_processing.screen_figure_text; such a description is not kept,
    knowledge_run.cached_descriptions)."""
    findings: List[Dict[str, Any]] = []
    total = 0
    for p in pairs:
        for ident in p.figure_idents:
            total += 1
            if ident not in p.output:
                findings.append({"section": p.heading, "figure": ident})
    missing = len(findings)
    findings += [dict(w) for w in wrong_language]
    parts = []
    if missing:
        parts.append(f"{missing} of {total} figures missing")
    if wrong_language:
        parts.append(f"{len(wrong_language)} figure descriptions not in the language "
                     f"of the source")
    summary = "; ".join(parts) if parts else f"{total} figures present"
    return CheckResult("figures", QUALITY, not findings, summary, findings)


def check_figure_descriptions(pending: Sequence[Dict[str, Any]], total: int) -> CheckResult:
    """Every figure carries a description by the image model."""
    summary = (f"{len(pending)} of {total} figure descriptions pending" if pending
               else f"{total} figures described")
    return CheckResult("figure_descriptions", QUALITY, not pending, summary, list(pending))


def check_figure_text(unconfirmed: Sequence[Dict[str, Any]]) -> CheckResult:
    """A count, not a gate: the quoted texts in figure descriptions that
    occur nowhere in the page's text layer, the figure's caption or the
    passage referring to it -- read by the image model alone, marked as
    unconfirmed in the output (knowledge_processing.screen_figure_text). The
    image itself is not checked; the check passes."""
    n = sum(len(u.get("quotes") or []) for u in unconfirmed)
    summary = (f"{n} quoted texts in {len(unconfirmed)} figure descriptions not "
               f"confirmed by the text of the source" if n
               else "every quoted text in the figure descriptions confirmed by the source")
    return CheckResult("figure_text", QUALITY, True, summary,
                       [dict(u) for u in unconfirmed], value=float(n))


# Function words by language, for telling the language of a short text such as
# a figure description. Words that two of these languages share ("la", "de",
# "en", "es", "in", "que") are left out.
_LANGUAGE_WORDS: Dict[str, frozenset] = {
    "de": frozenset("der die das und ist nicht mit sich auf für ein eine einem einen "
                    "dem den des zu im auch wird werden sind von als bei aus wie".split()),
    "en": frozenset("the and of to is that it for with as are this be on by an was "
                    "which from or at has have".split()),
    "fr": frozenset("le les et des est une du qui dans pour pas sur au aux avec sont "
                    "ce cette il elle ou".split()),
    "es": frozenset("el los las y del una por con para se al lo como su sus está".split()),
}


def text_language(text: str) -> str:
    """The language of a text by its function words (de, en, fr, es), or ""
    when no language has at least three of them and twice as many as the
    next one."""
    words = [w.lower() for w in _TOKEN_RE.findall(unicodedata.normalize("NFC", text or ""))]
    hits = sorted(((sum(1 for w in words if w in vocab), lang)
                   for lang, vocab in _LANGUAGE_WORDS.items()), reverse=True)
    (best, lang), (second, _) = hits[0], hits[1]
    return lang if best >= 3 and best >= 2 * second else ""


# Quoted text in a description: the quotation marks of _QUOTED_RE, the German
# single marks, and straight single marks that stand outside a word (not an
# apostrophe).
_DESCRIPTION_QUOTE_RE = re.compile(
    _QUOTED_RE.pattern + r"|‚[^‘’\n]*[‘’]|(?<!\w)'[^'\n]+'(?!\w)")
_ELLIPSIS_RE = re.compile(r"\[?…\]?|\[?\.\.\.\]?")
# A quote whose skeleton is this long also counts as found when the witness
# carries it across a line break or a hyphenation (pdftotext).
_QUOTE_SKELETON_MIN = 12


def quoted_texts(description: str) -> List[str]:
    """The quoted texts of a description, each with its quotation marks."""
    return [m.group(0) for m in _DESCRIPTION_QUOTE_RE.finditer(description or "")
            if any(ch.isalnum() for ch in m.group(0))]


def _in_order(needle: List[str], hay: List[str]) -> bool:
    n = len(needle)
    return any(hay[i:i + n] == needle for i in range(len(hay) - n + 1))


def quote_confirmed(quote: str, witness: str) -> bool:
    """Whether the text of a quote (without its marks) stands in the witness:
    its words in the same order, parts separated by an ellipsis each on their
    own. A quote in capitals (lettering) is compared with its case, anything
    else without; a long quote also counts when its skeleton is in the
    witness's skeleton."""
    inner = quote[1:-1].strip()
    parts = [p.strip() for p in _ELLIPSIS_RE.split(inner) if p.strip()]
    wit = unicodedata.normalize("NFKC", witness or "")
    wit_tokens = _TOKEN_RE.findall(wit)
    wit_lower = [t.lower() for t in wit_tokens]
    wit_skel = skeleton(wit)
    for part in parts:
        part = unicodedata.normalize("NFKC", part)
        tokens = _TOKEN_RE.findall(part)
        if not tokens:
            continue
        letters = [ch for ch in part if ch.isalpha()]
        if len(letters) >= 2 and all(ch.isupper() for ch in letters):
            found = _in_order(tokens, wit_tokens)
        else:
            skel = skeleton(part)
            found = (_in_order([t.lower() for t in tokens], wit_lower)
                     or (len(skel) >= _QUOTE_SKELETON_MIN and skel in wit_skel))
        if not found:
            return False
    return True


def unconfirmed_quotes(description: str, witness: str) -> List[str]:
    """The quoted texts of a description that the witness (the page's text
    layer, the caption, the passage referring to the figure) does not carry."""
    return [q for q in quoted_texts(description) if not quote_confirmed(q, witness)]


# --------------------------------------------------------------------------
# Quality: page references
# --------------------------------------------------------------------------

_OUT_PAGE_REF_RE = re.compile(r"\((?:S\.|pp?\.)\s*(\d+)(?:\s*[–-]\s*(\d+))?\)")
_SECTION_LINE_RE = re.compile(r"^###\s+(.*)$", re.MULTILINE)


def check_page_refs(pairs: Sequence[SectionPair], first: int, last: int,
                    kind: str = "pdf") -> CheckResult:
    """Every page reference lies within the document's pages ``first``..``last``
    and within its unit's pages; with page numbers known, every ``###``
    heading carries its pages. ``kind`` says which numbering the references
    use (``printed-labels``, ``printed-folio``, ``pdf``; see
    knowledge_extract.detect_page_numbering). A source without pages (DOCX,
    markdown, ``last`` 0) carries no page reference."""
    findings: List[Dict[str, Any]] = []
    total = 0
    pages = last
    for p in pairs:
        if p.missing:
            continue
        for m in _OUT_PAGE_REF_RE.finditer(p.output):
            total += 1
            a = int(m.group(1))
            b = int(m.group(2) or a)
            if pages <= 0:
                findings.append({"section": p.heading, "ref": m.group(0),
                                 "problem": "source has no page numbers"})
            elif not (first <= a <= b <= last):
                findings.append({"section": p.heading, "ref": m.group(0),
                                 "problem": f"outside the document ({first}–{last})"})
            elif p.page_from and not (p.page_from <= a and b <= p.page_to):
                findings.append({"section": p.heading, "ref": m.group(0),
                                 "problem": f"outside the section ({p.page_from}–{p.page_to})"})
        if pages > 0 and p.page_from:
            heads = list(_SECTION_LINE_RE.finditer(p.output))
            if not heads:
                findings.append({"section": p.heading, "problem": "no section heading"})
            for head in heads:
                if not _OUT_PAGE_REF_RE.search(head.group(1)):
                    findings.append({"section": p.heading, "heading": head.group(1).strip(),
                                     "problem": "section heading without pages"})
    numbering = f"{kind} pages {first}–{last}" if last > 0 else "no pages"
    summary = (f"{len(findings)} of {total} page references wrong or absent ({numbering})"
               if findings else f"{total} page references valid ({numbering})")
    return CheckResult("page_refs", QUALITY, not findings, summary, findings)


# --------------------------------------------------------------------------
# Quality: extraction
# --------------------------------------------------------------------------

def check_extraction(integrity: IntegrityReport, source: str) -> CheckResult:
    """The extraction was checked against the PDF's text layer and every gap
    found was repaired. A markdown source has no text layer to check against."""
    if source == "markdown":
        return CheckResult("extraction", QUALITY, True, "markdown source, no text layer")
    if not integrity.checked:
        return CheckResult("extraction", QUALITY, False,
                           f"not cross-checked: {integrity.reason or 'unknown'}")
    lost = integrity.unrepaired
    findings = [{"page": g.page, "words": g.words, "text": g.text[:200]} for g in lost]
    summary = (f"{len(lost)} of {len(integrity.gaps)} gaps unrepaired" if lost
               else f"{integrity.pages_checked} pages checked, {len(integrity.gaps)} gaps repaired")
    return CheckResult("extraction", QUALITY, not lost, summary, findings)


def check_reading_order(integrity: IntegrityReport, source: str) -> CheckResult:
    """No sentence of the body text is broken by the order Docling read a
    page in. Text that stands elsewhere on its page than in the reading of
    the PDF's text layer that agrees best with Docling (layout or flow order)
    is put back where it can be (knowledge_extract.check_reading_order);
    what is left fails the check only where Docling cuts a sentence
    (OrderFinding.breaks_text). The rest is listed and does not fail: an
    order that differs while every sentence runs on, and anything in the
    bibliography or the apparatus (notes, contents), whose order is judged
    there. A markdown or DOCX source has no page layout to compare with."""
    if source == "markdown":
        return CheckResult("reading_order", QUALITY, True, "markdown source, no page layout")
    if not integrity.order_pages_checked:
        return CheckResult("reading_order", QUALITY, True,
                           "no page layout to compare with" if integrity.checked
                           else f"not checked: {integrity.reason or 'unknown'}")
    left = integrity.order_unrepaired
    breaking = integrity.order_breaking
    findings = [{"page": o.page, "words": o.words, "text": o.text[:200],
                 "blocks": o.refs, "problem": o.note, "fails": o.breaks_text,
                 "breaks": o.breaks, "section": o.section} for o in left]
    repaired = len(integrity.order) - len(left)
    if breaking:
        summary = (f"{len(breaking)} passages out of order break a sentence "
                   f"({len(left)} of {len(integrity.order)} not repairable)")
    elif left:
        summary = (f"{len(left)} of {len(integrity.order)} passages out of order not "
                   f"repairable, none breaks a sentence of the body text")
    else:
        summary = (f"{integrity.order_pages_checked} pages checked, "
                   f"{repaired} passages put back in order")
    return CheckResult("reading_order", QUALITY, not breaking, summary, findings)


# --------------------------------------------------------------------------

def run_checks(pairs: Sequence[SectionPair], *, source_text: str, output_text: str,
               page_first: int, page_last: int, page_kind: str,
               integrity: IntegrityReport, source: str,
               pending_figures: Sequence[Dict[str, Any]], n_figures: int,
               min_words: int, max_share: float,
               output_excluded: Sequence[str] = (),
               compare_items: bool = True,
               wrong_language: Sequence[Dict[str, Any]] = (),
               unconfirmed_figure_text: Sequence[Dict[str, Any]] = ()) -> CheckReport:
    """`compare_items`: the list check compares the items, not only their
    count (false when the condensation is not in the language of the
    source). `wrong_language` and `unconfirmed_figure_text` come from
    knowledge_processing.screen_figure_text. The verbatim share leaves out
    the source's lists, taken unit by unit from `pairs`."""
    list_text = "\n\n".join(t for t in (source_list_text(p.source_blocks) for p in pairs) if t)
    return CheckReport([
        check_verbatim_share(source_text, output_text, min_words, max_share, output_excluded,
                             list_text),
        check_lists(pairs, compare_items),
        check_numbers(pairs),
        check_headings(pairs),
        check_figures(pairs, wrong_language),
        check_figure_descriptions(pending_figures, n_figures),
        check_figure_text(unconfirmed_figure_text),
        check_page_refs(pairs, page_first, page_last, page_kind),
        check_extraction(integrity, source),
        check_reading_order(integrity, source),
    ])
