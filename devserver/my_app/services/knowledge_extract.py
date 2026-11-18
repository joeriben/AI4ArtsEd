"""Extraction with integrity: a PDF as ordered blocks, checked against its text layer.

The library's condensation reads a document block by block. Each block carries
the PDF page it stands on and its kind (heading with level, paragraph, list
item, table, figure with caption and exported image file). The blocks come from
Docling (``scripts/knowledge_ingest.py`` writes them as ``<doc_id>.blocks.json``
beside the raw text, the figure images into ``<doc_id>.figures/``).

Docling loses text. In "Monster im Dialog" a whole page of body text (p. 10)
never reaches its output, and a sentence on p. 11 survives only as text inside
a picture. So every page is checked against the PDF's own text layer
(``pdftotext -layout``): a run of words the text layer has and Docling does not
is a gap. A gap is reported with its page and repaired by inserting the passage
as a paragraph at the position of its neighbours, flagged ``repaired``.

Pictures that carry no content (icons, logos repeated on every page, rules
and bands) are removed before anything describes them (screen_figures).

This module needs no Docling: it runs in the DevServer process, in the pilot
runner, and in tests, none of which may import Docling. Beside the standard
library it uses Pillow, only in screen_figures, to read the exported
pictures' pixels.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# Kinds that carry the document's content, in the order Docling read them.
CONTENT_KINDS = frozenset({
    "title", "heading", "paragraph", "list_item", "table", "figure",
    "footnote", "code", "formula",
})

# A caption that opens with a figure label is a caption. Anything else Docling
# hung under a picture is body text that ran beside it.
_FIGURE_LABEL_RE = re.compile(
    r"^\s*(?:Abb(?:ildung)?|Fig(?:ure|\.)?|Grafik|Bild|Tab(?:elle)?|Table|Image)"
    r"\.?\s*\d", re.IGNORECASE)

# A gap is at least this many words and this many skeleton characters; shorter
# runs are page numbers, stray labels, hyphen fragments.
GAP_MIN_WORDS = 3
GAP_MIN_CHARS = 15
# A page on which Docling's text covers less than this share of the text
# layer is taken from the text layer whole.
PAGE_REPLACE_BELOW = 0.5
# A gap whose words (three letters or more) stand in Docling's remaining
# blocks of its page and the neighbouring pages to this share is a duplicate:
# Docling has the text, in another order (columns, table cells, the labels of
# a picture, a running head). It is not inserted.
GAP_DUPLICATE_SHARE = 0.8
# A gap of which fewer than this share of the tokens are words is debris of a
# formula, a plot axis or a number grid. It is not inserted.
GAP_WORD_SHARE = 0.5
# A gap with this many mathematical signs or Greek letters per token is a
# formula set in the text layer (Docling marks the formula itself).
GAP_FORMULA_SHARE = 0.1
# A coverage window is at least this many words and skeleton characters.
_WINDOW_WORDS = 4
_WINDOW_CHARS = 12


@dataclass
class Block:
    kind: str
    text: str = ""
    page: int = 0
    level: int = 0
    list_id: str = ""
    enumerated: bool = False
    marker: str = ""
    caption: str = ""
    figure_no: str = ""
    image: str = ""
    seq: int = 0
    markdown: str = ""
    ref: str = ""
    figure_ref: str = ""
    repaired: bool = False
    # A figure too small to hold anything legible (screen_figures): it keeps
    # its caption and gets no image description.
    describe: bool = True
    # The PDF page (1 = first page of the file) once number_pages has given
    # `page` the printed page; 0 for a source without pages.
    pdf_page: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        if known.get("page") is None:
            known["page"] = 0       # a DOCX item carries no page
        return cls(**known)


@dataclass
class Gap:
    page: int
    text: str
    words: int
    kind: str = "missing"     # "missing" / "reordered"
    repaired: bool = False
    anchor: str = ""          # "after <ref>" / "before <ref>" / "end"


@dataclass
class OrderFinding:
    """A run of text that Docling put elsewhere on its page than the text layer."""
    page: int
    text: str
    words: int
    refs: list[str] = field(default_factory=list)   # the Docling blocks involved
    repaired: bool = False
    note: str = ""            # how it was repaired, or why it could not be
    # Junctions between Docling's body blocks around an unrepaired finding
    # where a sentence is broken (_junction_breaks); empty when the order
    # differs from the layer but every sentence runs on as the layer has it.
    breaks: list[str] = field(default_factory=list)
    # ORDER_SECTION_BIBLIOGRAPHY or ORDER_SECTION_APPARATUS when the finding
    # stands under such a heading, else "".
    section: str = ""

    @property
    def breaks_text(self) -> bool:
        """A finding that changes what the text says: a broken sentence in
        the body text, outside the bibliography and the apparatus."""
        return bool(self.breaks) and not self.section


@dataclass
class IntegrityReport:
    """All page numbers in this report are PDF pages (1 = first page of the
    file), whatever numbering the library file uses for its references."""
    checked: bool = False
    reason: str = ""          # why the check did not run, if it did not
    pages_checked: int = 0
    gaps: list[Gap] = field(default_factory=list)
    # Uncovered runs of the text layer that are not lost text: "duplicate"
    # (Docling's remaining blocks hold the words) or "debris" (formula, axis,
    # number grid). Not inserted, and not gaps.
    gaps_dismissed: list[dict] = field(default_factory=list)
    captions_reclassified: list[dict] = field(default_factory=list)
    # Captions Docling had given to the picture after their own
    # (reassign_shifted_captions): page, caption (its label), from (the ref of
    # the picture that carried it), to (the ref of the picture above it).
    captions_reassigned: list[dict] = field(default_factory=list)
    # Numbered headings Docling had cut into a list (restore_numbered_headings):
    # page, ref, text, rule ("number-only heading" / "list item between
    # headings").
    headings_restored: list[dict] = field(default_factory=list)
    # Numbered lists Docling had split around pictures or paragraphs
    # (reunite_numbered_lists): page, list (the list_id the fragment joins),
    # fragment (its own list_id, or the ref of the paragraph), markers,
    # rule ("fragment continues numbering" / "paragraph continues numbering").
    lists_reunited: list[dict] = field(default_factory=list)
    # Pictures removed as not carrying content (screen_figures): page, image,
    # w, h (pixels), reason (small / repeated / strip), figure (the labelled
    # figure on the page of a small one, if any).
    figures_screened: list[dict] = field(default_factory=list)
    superseded: list[dict] = field(default_factory=list)
    replaced_pages: list[int] = field(default_factory=list)
    noise_dropped: int = 0
    hyphens_restored: list[dict] = field(default_factory=list)
    order: list[OrderFinding] = field(default_factory=list)
    order_pages_checked: int = 0
    page_order_moved: list[dict] = field(default_factory=list)

    @property
    def unrepaired(self) -> list[Gap]:
        return [g for g in self.gaps if not g.repaired]

    @property
    def order_unrepaired(self) -> list[OrderFinding]:
        return [o for o in self.order if not o.repaired]

    @property
    def order_breaking(self) -> list[OrderFinding]:
        return [o for o in self.order_unrepaired if o.breaks_text]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["unrepaired"] = len(self.unrepaired)
        d["order_unrepaired"] = len(self.order_unrepaired)
        d["order_breaking"] = len(self.order_breaking)
        d["pages_are"] = "pdf"
        return d


# How the pages of a library file are numbered (Extraction.page_kind).
PAGES_PRINTED_LABELS = "printed-labels"   # the PDF's own page labels (/PageLabels)
PAGES_PRINTED_FOLIO = "printed-folio"     # the page number printed on the page
PAGES_PDF = "pdf"                         # position in the file, 1 = first page
PAGES_NONE = "none"                       # no pages (DOCX, markdown): sections


@dataclass
class Extraction:
    blocks: list[Block]
    pages: int = 0                       # PDF pages in the file; 0 = no pages
    source: str = "docling"
    figures_dir: Optional[Path] = None
    integrity: IntegrityReport = field(default_factory=IntegrityReport)
    # The numbering Block.page carries after number_pages(): until then the
    # PDF page. page_first..page_last is the range a reference may name.
    page_kind: str = PAGES_PDF
    page_first: int = 0
    page_last: int = 0
    page_detail: dict = field(default_factory=dict)
    # A document that is part of the file (a chapter of a volume): its PDF
    # pages, first and last (restrict_to_pages). `pages` then counts the
    # pages of the range and `file_pages` those of the file.
    pdf_range: Optional[tuple[int, int]] = None
    file_pages: int = 0
    # The PDF or DOCX the blocks were checked against (extract_with_integrity).
    source_file: Optional[Path] = None
    # The text layer of the PDF (pdftotext, reading order), per PDF page of
    # the document: the second reading of a page that the review and the
    # figure descriptions are held against. Not part of to_dict.
    text_layer: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.pages <= 0:
            self.page_kind = PAGES_NONE
        elif not self.page_last:
            self.page_first, self.page_last = 1, self.pages

    def content_blocks(self) -> list[Block]:
        return [b for b in self.blocks if b.kind in CONTENT_KINDS]

    def figures(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "figure"]

    def figures_to_describe(self) -> list[Block]:
        """The figures that get an image description: all but the small
        labelled ones screen_figures keeps with their caption only."""
        return [b for b in self.figures() if b.describe]

    def order_layer(self) -> dict:
        """{PDF page: text layer} of the pages that carry an unrepaired
        reading-order finding in the body text (outside the bibliography and
        the apparatus): the pages the review reads a second time."""
        pages = {o.page for o in self.integrity.order_unrepaired if not o.section}
        return {p: self.text_layer[p] for p in sorted(pages) if self.text_layer.get(p)}

    def page_numbering(self) -> dict:
        excerpt = ({"pdf_seiten": format_page_range(self.pdf_range),
                    "file_pages": self.file_pages} if self.pdf_range else {})
        return {"kind": self.page_kind, "first": self.page_first,
                "last": self.page_last, **excerpt, **self.page_detail}

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "pages": self.pages,
            "page_numbering": self.page_numbering(),
            "figures_dir": self.figures_dir.name if self.figures_dir else "",
            "blocks": [asdict(b) for b in self.blocks],
            "integrity": self.integrity.to_dict(),
        }


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_blocks(path: Path) -> Extraction:
    """Read ``<doc_id>.blocks.json`` as written by ``knowledge_ingest.py``."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    fig_name = data.get("figures_dir") or ""
    return Extraction(
        blocks=[Block.from_dict(b) for b in data.get("blocks", [])],
        pages=int(data.get("pages") or 0),
        source=data.get("source") or "docling",
        figures_dir=(path.parent / fig_name) if fig_name else None,
    )


# --------------------------------------------------------------------------
# A document that is part of the file
# --------------------------------------------------------------------------

_PAGE_RANGE_RE = re.compile(r"^\s*(\d{1,5})\s*(?:[-–]\s*(\d{1,5}))?\s*$")


def parse_page_range(text) -> Optional[tuple[int, int]]:
    """``"111-137"`` (or ``"111–137"``, or ``"9"``) as (first, last) PDF page;
    None for an empty value. The front-matter field `pdf_seiten` and the
    runner's EXCERPT_PAGES carry it. Raises ValueError on anything else."""
    if text is None or (isinstance(text, str) and not text.strip()):
        return None
    if isinstance(text, (tuple, list)) and len(text) == 2:
        first, last = int(text[0]), int(text[1])
    else:
        m = _PAGE_RANGE_RE.match(str(text))
        if not m:
            raise ValueError(f"page range {text!r}: expected 'first-last'")
        first = int(m.group(1))
        last = int(m.group(2) or m.group(1))
    if first < 1 or last < first:
        raise ValueError(f"page range {text!r}: first page 1 or later, last not before first")
    return first, last


def format_page_range(rng: Optional[tuple[int, int]]) -> str:
    return f"{rng[0]}-{rng[1]}" if rng else ""


def restrict_to_pages(ext: Extraction, rng: tuple[int, int]) -> None:
    """Keep the blocks of PDF pages rng[0]..rng[1]: the document is a chapter
    or section of the file (a volume, a brochure, a galley). A block without
    a page goes with the block before it. `pages` becomes the number of pages
    in the range, `file_pages` keeps the file's; the PDF page numbers of the
    blocks stay those of the file, and number_pages gives them the printed
    pages of the volume. Raises ValueError for a range outside the file."""
    first, last = rng
    if ext.pages <= 0:
        raise ValueError("a page range needs a paged source (PDF)")
    if last > ext.pages:
        raise ValueError(f"page range {first}-{last} outside the file ({ext.pages} pages)")
    kept: list[Block] = []
    inside = False
    for b in ext.blocks:
        if b.page:
            inside = first <= b.page <= last
        if inside:
            kept.append(b)
    ext.blocks = kept
    ext.file_pages = ext.pages
    ext.pages = last - first + 1
    ext.pdf_range = (first, last)
    ext.page_first, ext.page_last = first, last


def _range_only(layout_pages: list[str], rng: Optional[tuple[int, int]]) -> list[str]:
    """The text layer with the pages outside the range left empty: the
    checks compare the range alone, and a page keeps its PDF number."""
    if not rng:
        return layout_pages
    return [t if rng[0] <= p <= rng[1] else "" for p, t in enumerate(layout_pages, 1)]


_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_MD_LIST_RE = re.compile(r"^\s*(?:([-*•·])|(\d+)[.)])\s+(.*\S)\s*$")
_MD_IMAGE_RE = re.compile(r"^\s*<!--\s*image\s*-->\s*$")


def from_markdown(md: str) -> Extraction:
    """Blocks from markdown: a ``--md`` source, a legacy raw text, a scene text.

    Markdown carries no page numbers; every block stands on page 0 and the
    extraction reports ``pages == 0``, which the condensation reads as "no
    page references possible".
    """
    blocks: list[Block] = []
    para: list[str] = []
    table: list[str] = []
    list_no = 0
    in_list = False

    def flush_para():
        if para:
            blocks.append(Block(kind="paragraph", text=" ".join(s.strip() for s in para)))
            para.clear()

    def flush_table():
        if table:
            blocks.append(Block(kind="table", markdown="\n".join(table)))
            table.clear()

    for line in md.splitlines():
        if line.lstrip().startswith("|"):
            flush_para()
            table.append(line.rstrip())
            in_list = False
            continue
        flush_table()
        if not line.strip():
            flush_para()
            in_list = False
            continue
        if _MD_IMAGE_RE.match(line):
            flush_para()
            continue
        m = _MD_HEADING_RE.match(line)
        if m:
            flush_para()
            in_list = False
            blocks.append(Block(kind="heading", text=m.group(2), level=len(m.group(1))))
            continue
        m = _MD_LIST_RE.match(line)
        if m:
            flush_para()
            if not in_list:
                list_no += 1
                in_list = True
            blocks.append(Block(
                kind="list_item", text=m.group(3), list_id=f"md/{list_no}",
                enumerated=m.group(2) is not None,
                marker=m.group(1) or f"{m.group(2)}."))
            continue
        if in_list and blocks and blocks[-1].kind == "list_item" and line.startswith((" ", "\t")):
            blocks[-1].text += " " + line.strip()
            continue
        in_list = False
        para.append(line)
    flush_para()
    flush_table()
    return Extraction(blocks=blocks, pages=0, source="markdown")


# --------------------------------------------------------------------------
# Normalisation of Docling's output
# --------------------------------------------------------------------------

def normalise(ext: Extraction) -> None:
    """Captions that are body text become paragraphs; textless blocks go.

    Docling assigns the text running beside a picture to that picture as its
    caption ("entscheidet sich Karlotta in ihrer finalen Umsetzung …", p. 8).
    Such a caption is moved out as a paragraph directly before the figure, and
    the figure keeps no number it did not carry in a real caption.
    """
    out: list[Block] = []
    for b in ext.blocks:
        if b.kind == "figure" and b.caption and not _FIGURE_LABEL_RE.match(b.caption):
            out.append(Block(kind="paragraph", text=b.caption, page=b.page,
                             ref=f"{b.ref}/caption"))
            ext.integrity.captions_reclassified.append(
                {"page": b.page, "figure": b.ref, "text": b.caption[:120]})
            b.caption = ""
            b.figure_no = ""
        if b.kind in ("paragraph", "list_item", "heading") and not any(
                ch.isalnum() for ch in b.text):
            ext.integrity.noise_dropped += 1
            continue
        out.append(b)
    ext.blocks = out
    reassign_shifted_captions(ext)
    restore_numbered_headings(ext)
    reunite_numbered_lists(ext)


# A figure caption's label and number: "Figure 11.", "Abb. 3:".
_FIGURE_NUMBER_RE = re.compile(
    r"^\s*(Abb(?:ildung)?|Fig(?:ure|\.)?|Grafik|Bild|Image)\.?\s*(\d+)\b", re.IGNORECASE)


def _caption_number(text: str) -> Optional[tuple[str, int]]:
    m = _FIGURE_NUMBER_RE.match(text or "")
    return (m.group(1)[:3].lower(), int(m.group(2))) if m else None


def reassign_shifted_captions(ext: Extraction) -> None:
    """A caption Docling gave to the picture after its own goes back up.

    Where a caption stands below its picture and a second picture follows on
    the page, Docling can attach the caption to the second picture and leave
    the second picture's own caption as a free caption block (Esser et al.
    2024, p. 22: "Figure 11. The mode (left) and logit-normal (right)
    distributions" on the image grid, "Figure 12. Qualitative effects of
    scaling" free beneath it, the distribution charts above without one).
    Bound to an unbroken numbering on one page: a picture with caption N,
    the picture before it without caption or number, and the next caption
    block after it numbered N + 1 under the same label, before any further
    picture. The caption N then goes to the picture before, and the free
    caption N + 1 becomes the caption of the picture that carried N. Each
    move is recorded in ``integrity.captions_reassigned``.
    """
    blocks = ext.blocks
    drop: set[int] = set()
    for i, b in enumerate(blocks):
        if b.kind != "figure" or not b.caption:
            continue
        num = _caption_number(b.caption)
        if num is None:
            continue
        prev = None
        for j in range(i - 1, -1, -1):
            if blocks[j].page != b.page or blocks[j].kind == "caption":
                break
            if blocks[j].kind == "figure":
                prev = j
                break
        if prev is None or blocks[prev].caption or blocks[prev].figure_no:
            continue
        free = None
        for k in range(i + 1, len(blocks)):
            if blocks[k].page != b.page or blocks[k].kind == "figure":
                break
            if blocks[k].kind == "caption":
                if k not in drop and _caption_number(blocks[k].text) == (num[0], num[1] + 1):
                    free = k
                break
        if free is None:
            continue
        above = blocks[prev]
        above.caption, above.figure_no = b.caption, b.figure_no or str(num[1])
        b.caption, b.figure_no = blocks[free].text, str(num[1] + 1)
        drop.add(free)
        ext.integrity.captions_reassigned.append(
            {"page": b.page, "caption": f"{num[0]} {num[1]}", "from": b.ref, "to": above.ref})
    if drop:
        ext.blocks = [b for i, b in enumerate(blocks) if i not in drop]


# A heading or list item that carries its own number: "2. Gut geplant ist halb
# gewonnen", "1.".
_NUMBERED_RE = re.compile(r"^(\d{1,3})[.)](?:\s+|$)")


def _heading_number(b: Block) -> Optional[int]:
    if b.kind != "heading":
        return None
    m = _NUMBERED_RE.match(b.text.strip())
    return int(m.group(1)) if m else None


def _marker_number(b: Block) -> Optional[int]:
    m = re.match(r"^(\d{1,3})[.)]?$", (b.marker or "").strip())
    return int(m.group(1)) if b.enumerated and m else None


def restore_numbered_headings(ext: Extraction) -> None:
    """Numbered headings that Docling cut into a list become headings again.

    Two cases, both bound to an unbroken numbering of the headings around
    them (KlappKLAUS, p. 1: "1." / "Der Zufall macht's" / "2. Gut geplant …" /
    a list ending in "3. Reflexion schadet nie" / "4. Mehr kann mehr"):

    - a heading that is only a number ("1.") followed by a list of one item:
      the item is the heading's text;
    - an enumerated list item numbered N, the only enumerated item of its
      list, whose nearest heading before it is numbered N-1 and whose nearest
      heading after it is numbered N+1: it is heading N, at their level.
    """
    blocks = ext.blocks
    group_size: dict[str, int] = {}
    group_enum: dict[str, int] = {}
    for b in blocks:
        if b.kind == "list_item" and b.list_id:
            group_size[b.list_id] = group_size.get(b.list_id, 0) + 1
            if b.enumerated:
                group_enum[b.list_id] = group_enum.get(b.list_id, 0) + 1

    def neighbour_heading(i: int, step: int) -> Optional[Block]:
        j = i + step
        while 0 <= j < len(blocks):
            if blocks[j].kind == "heading":
                return blocks[j]
            j += step
        return None

    def continues(i: int, n: int) -> bool:
        before, after = neighbour_heading(i, -1), neighbour_heading(i, 1)
        return ((before is not None and _heading_number(before) == n - 1)
                or (after is not None and _heading_number(after) == n + 1))

    out: list[Block] = []
    skip: set[int] = set()
    for i, b in enumerate(blocks):
        if i in skip:
            continue
        n = _heading_number(b)
        if n is not None and _NUMBERED_RE.match(b.text.strip()).end() == len(b.text.strip()):
            j = i + 1
            while j < len(blocks) and blocks[j].kind == "furniture":
                j += 1
            nxt = blocks[j] if j < len(blocks) else None
            if (nxt is not None and nxt.kind == "list_item" and nxt.list_id
                    and group_size.get(nxt.list_id) == 1 and continues(i, n)):
                b.text = f"{b.text.strip()} {nxt.text.strip()}"
                skip.add(j)
                ext.integrity.headings_restored.append(
                    {"page": b.page, "ref": b.ref, "text": b.text[:120],
                     "rule": "number-only heading"})
        out.append(b)
    blocks = out

    for i, b in enumerate(blocks):
        n = _marker_number(b) if b.kind == "list_item" else None
        if n is None or group_enum.get(b.list_id) != 1:
            continue
        before, after = neighbour_heading(i, -1), neighbour_heading(i, 1)
        if (before is None or after is None or _heading_number(before) != n - 1
                or _heading_number(after) != n + 1 or (before.level or 1) != (after.level or 1)):
            continue
        b.kind = "heading"
        b.level = before.level
        b.text = f"{b.marker.strip()} {b.text.strip()}"
        b.list_id, b.enumerated, b.marker = "", False, ""
        ext.integrity.headings_restored.append(
            {"page": b.page, "ref": b.ref, "text": b.text[:120],
             "rule": "list item between headings"})
    ext.blocks = blocks


def _unbroken_numbers(items: list[Block]) -> Optional[list[int]]:
    """The numbers of a list's items when every item is enumerated and they
    run on without a gap (3, 4, 5); else None."""
    nums = [_marker_number(b) for b in items]
    if not nums or any(n is None for n in nums):
        return None
    if any(b != a + 1 for a, b in zip(nums, nums[1:])):
        return None
    return nums


def reunite_numbered_lists(ext: Extraction) -> None:
    """Fragments of one numbered list that Docling split around a picture or
    a paragraph become one list again (KlappKLAUS, p. 2: item 1 alone, items
    2-4 as a second list after the pictures, item 5 as the caption of a
    picture that normalise made a paragraph).

    Bound to an unbroken numbering, like restore_numbered_headings: a
    fragment joins the list before it when every item of both is enumerated,
    each numbered one higher than the item before, and its first number is
    the last number of that list plus one; a paragraph that opens with the
    next number ("5. Ausprobieren und erweitern!") becomes that list's next
    item. Pictures, figure texts and paragraphs may stand between them; a
    heading, a list that is not numbered this way, or more than one page
    between the two ends the list. Each join is recorded in
    integrity.lists_reunited.
    """
    blocks = ext.blocks
    members: dict[str, list[Block]] = {}
    for b in blocks:
        if b.kind == "list_item" and b.list_id:
            members.setdefault(b.list_id, []).append(b)
    numbers = {lid: _unbroken_numbers(items) for lid, items in members.items()}
    first_of = {id(items[0]): lid for lid, items in members.items()}

    open_id: Optional[str] = None      # the list a continuation joins
    open_last = 0                      # its last number
    open_page = 0                      # the page of its last item
    for b in blocks:
        if b.kind == "heading":
            open_id = None
            continue
        if b.kind == "list_item" and b.list_id:
            if b.list_id == open_id:
                open_page = b.page or open_page
                continue
            lid = first_of.get(id(b))
            nums = numbers.get(b.list_id)
            if lid is None or nums is None:
                # not the first item of its list, or not numbered unbroken
                open_id = None
                continue
            near = not (b.page and open_page) or b.page - open_page <= 1
            if open_id is not None and nums[0] == open_last + 1 and near:
                for item in members[lid]:
                    item.list_id = open_id
                ext.integrity.lists_reunited.append(
                    {"page": b.page, "list": open_id, "fragment": lid,
                     "markers": f"{nums[0]}-{nums[-1]}",
                     "rule": "fragment continues numbering"})
            else:
                open_id = lid
            open_last = nums[-1]
            open_page = members[lid][-1].page or b.page
            continue
        if b.kind == "paragraph" and open_id is not None:
            text = b.text.strip()
            m = _NUMBERED_RE.match(text)
            near = not (b.page and open_page) or b.page - open_page <= 1
            if m and int(m.group(1)) == open_last + 1 and text[m.end():].strip() and near:
                b.kind = "list_item"
                b.list_id = open_id
                b.enumerated = True
                b.marker = text[:m.end()].strip()
                b.text = text[m.end():].strip()
                open_last += 1
                open_page = b.page or open_page
                ext.integrity.lists_reunited.append(
                    {"page": b.page, "list": open_id, "fragment": b.ref,
                     "markers": str(open_last), "rule": "paragraph continues numbering"})


# --------------------------------------------------------------------------
# Figure screening: which pictures carry content
# --------------------------------------------------------------------------

# Docling exports pictures at twice their printed size (images_scale 2.0), so
# 100 px are 50 pt, 1.8 cm on the page: link icons (~52 x 43 px), bullets,
# the tiles of a grid of small pictures.
FIGURE_SMALL_PX = 100
# Two pictures are the same picture (a logo, a running ornament) when their
# files are identical or their 256-bit difference hashes differ in at most
# this many bits and their sizes by at most FIGURE_SAME_SIZE.
FIGURE_SAME_HASH_BITS = 16
FIGURE_SAME_SIZE = 0.1
FIGURE_REPEAT_PAGES = 2
# A paragraph that refers to a figure by label and number.
_FIGURE_REFERENCE_RE = re.compile(
    r"(?:^|[\s(\[])(?:Abb(?:ildung)?|Fig(?:ure|s)?|Figs?\.|Grafik|Bild|Image)\.?\s*\d",
    re.IGNORECASE)


def _picture_facts(path: Path) -> Optional[dict]:
    """Size, file hash and 256-bit difference hash of an exported picture.
    Pillow is imported here, not at module level: the extraction itself is
    standard library only, the screening needs the pixels."""
    import hashlib
    try:
        from PIL import Image
        data = path.read_bytes()
        with Image.open(path) as im:
            w, h = im.size
            g = im.convert("L").resize((17, 16))
            px = list(g.getdata())
    except Exception:  # noqa: BLE001 - an unreadable file is not screened
        return None
    bits = 0
    for y in range(16):
        for x in range(16):
            bits = bits << 1 | (px[y * 17 + x] < px[y * 17 + x + 1])
    return {"w": w, "h": h, "sha": hashlib.sha256(data).hexdigest(), "dh": bits}


def _same_picture(a: dict, b: dict) -> bool:
    if a["sha"] == b["sha"]:
        return True
    return (bin(a["dh"] ^ b["dh"]).count("1") <= FIGURE_SAME_HASH_BITS
            and abs(a["w"] - b["w"]) <= FIGURE_SAME_SIZE * max(a["w"], 1)
            and abs(a["h"] - b["h"]) <= FIGURE_SAME_SIZE * max(a["h"], 1))


def screen_figures(ext: Extraction) -> list[dict]:
    """Remove the pictures that carry no content, and mark the small labelled
    ones as not to be described.

    A figure is labelled when it keeps a caption after normalise() (one that
    opens with a figure label) or a figure number. A labelled figure stays
    in every case; under FIGURE_SMALL_PX on its longer side it is rendered
    with its caption only (``describe = False``): nothing in it can be read.
    An unlabelled picture is removed when
      - its longer side is under FIGURE_SMALL_PX ("small": icons, bullets,
        tiles of a picture grid; the labelled figure on its page, if any,
        is named in the record),
      - the same picture stands on FIGURE_REPEAT_PAGES pages or more of the
        document ("repeated": logos, ornaments),
      - its shorter side is under FIGURE_SMALL_PX, no labelled figure stands
        on its page and no paragraph of its page refers to a figure by
        number ("strip": rules, bars, decorative bands).
    Every other picture is described, the unlabelled pictures beside a
    numbered figure (its parts a, b, c) included. Each removal is recorded
    in ``integrity.figures_screened``. A picture whose file cannot be read
    is left as it is.
    """
    figures = ext.figures()
    if not figures or ext.figures_dir is None:
        return []
    facts: dict[int, dict] = {}
    for i, b in enumerate(figures):
        if b.image:
            f = _picture_facts(ext.figures_dir / b.image)
            if f is not None:
                facts[i] = f
    labelled = {i for i, b in enumerate(figures) if b.caption or b.figure_no}
    labelled_on: dict[int, str] = {}
    for i in labelled:
        labelled_on.setdefault(figures[i].page, figures[i].ref)
    referring_pages = {b.page for b in ext.blocks
                       if b.kind in ("paragraph", "list_item", "footnote")
                       and _FIGURE_REFERENCE_RE.search(b.text)}
    paged = ext.pages > 0
    drop: dict[int, dict] = {}
    for i, f in facts.items():
        b = figures[i]
        short, long_ = min(f["w"], f["h"]), max(f["w"], f["h"])
        if i in labelled:
            if long_ < FIGURE_SMALL_PX:
                b.describe = False
            continue
        reason = ""
        if long_ < FIGURE_SMALL_PX:
            reason = "small"
        else:
            same = [j for j, g in facts.items() if j == i or _same_picture(f, g)]
            spread = len({figures[j].page for j in same}) if paged else len(same)
            if spread >= FIGURE_REPEAT_PAGES:
                reason = "repeated"
            elif (short < FIGURE_SMALL_PX and b.page not in labelled_on
                  and b.page not in referring_pages):
                reason = "strip"
        if reason:
            rec = {"page": b.page, "image": b.image, "w": f["w"], "h": f["h"],
                   "reason": reason}
            if reason == "small" and b.page in labelled_on:
                rec["figure"] = labelled_on[b.page]
            drop[id(b)] = rec
    if drop:
        ext.blocks = [b for b in ext.blocks if id(b) not in drop]
        ext.integrity.figures_screened.extend(drop.values())
    return list(drop.values())


# --------------------------------------------------------------------------
# The text layer
# --------------------------------------------------------------------------

def pdftotext_pages(pdf: Path) -> list[str]:
    """The PDF's text layer, one string per page, in ``-layout`` mode."""
    exe = shutil.which("pdftotext") or "/usr/bin/pdftotext"
    proc = subprocess.run(
        [exe, "-layout", "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True, check=True, timeout=300,
    )
    pages = proc.stdout.decode("utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def pdftotext_flow_pages(pdf: Path) -> list[str]:
    """The PDF's text layer, one string per page, in pdftotext's own reading
    order (no ``-layout``): it follows the text flows it finds, three columns
    or a column beside a figure included, where the layout mode gives lines."""
    exe = shutil.which("pdftotext") or "/usr/bin/pdftotext"
    proc = subprocess.run(
        [exe, "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True, check=True, timeout=300,
    )
    pages = proc.stdout.decode("utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def reading_lines(page_text: str) -> list[str]:
    """The lines of a layout page in reading order.

    ``-layout`` puts two columns side by side on one line. A column gutter is
    an x range that is blank on nearly every line; justified text has wide
    gaps too, but never at the same x on every line. The page is split there
    only when both sides carry a substantial number of lines, so a caption set
    beside an image does not turn into a column.
    """
    lines = [l.rstrip() for l in page_text.split("\n")]
    content = [l for l in lines if l.strip()]
    if len(content) < 10:
        return [l.strip() for l in content]
    width = max(len(l) for l in content)
    occ = [0] * width
    for l in content:
        for x, ch in enumerate(l):
            if not ch.isspace():
                occ[x] += 1
    tolerance = max(1, int(0.03 * len(content)))
    lo, hi = int(width * 0.25), int(width * 0.75)
    best: Optional[tuple[int, int]] = None
    x = lo
    while x < hi:
        if occ[x] <= tolerance:
            start = x
            while x < hi and occ[x] <= tolerance:
                x += 1
            if x - start >= 2 and (best is None or x - start > best[1] - best[0]):
                best = (start, x)
        x += 1
    if best is None:
        return [l.strip() for l in content]
    gutter = (best[0] + best[1]) // 2
    left: list[str] = []
    right: list[str] = []
    for l in content:
        if len(l) > gutter and not l[gutter].isspace():
            left.append(l.strip())        # a line across the gutter stays whole
            continue
        if l[:gutter].strip():
            left.append(l[:gutter].strip())
        if l[gutter:].strip():
            right.append(l[gutter:].strip())
    need = max(5, int(0.25 * len(content)))
    if len(left) < need or len(right) < need:
        return [l.strip() for l in content]
    return left + right


_LIGATURE_RE = re.compile(r"ff[il]|f[fil]")


def skeleton(text: str) -> str:
    """Letters and digits only, lower case, ligature letters removed.

    ``pdftotext`` drops ligature glyphs ("Re exionsbogen" for
    "Reflexionsbogen"); removing fi/fl/ff on both sides makes the two
    spellings meet. Spacing, hyphenation and punctuation vanish entirely.
    Diacritics vanish too: a PDF can set an accent as a glyph of its own
    ("Herv´ e J´ egou" for "Hervé Jégou"), and both spellings then meet.
    """
    s = unicodedata.normalize("NFKC", text).lower()
    s = _LIGATURE_RE.sub("", s)
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if ch.isalnum() and not unicodedata.combining(ch))


# --------------------------------------------------------------------------
# Cross-check and repair
# --------------------------------------------------------------------------

def _block_text(b: Block) -> str:
    if b.kind == "figure":
        return b.caption
    if b.kind == "table":
        return b.markdown or b.text
    return b.text


@dataclass
class _Word:
    text: str
    sk: str
    line: int
    cell: int


def _page_words(page_text: str, columns: bool = True) -> list[_Word]:
    """The words of a layout page in reading order, with line and cell.

    A cell is a run of text separated from the next by three or more spaces;
    a passage whose every line has the same number of cells is a table.
    ``columns=False`` takes the lines as they stand (a DOCX text, which has
    no layout to split into columns).
    """
    out: list[_Word] = []
    lines = (reading_lines(page_text) if columns
             else [l.strip() for l in page_text.split("\n") if l.strip()])
    for ln, line in enumerate(lines):
        for cn, cell in enumerate(re.split(r"\s{3,}", line.strip())):
            for w in cell.split():
                out.append(_Word(w, skeleton(w), ln, cn))
    return out


def _windows(sks: list[str]):
    """Coverage windows: (start, end, skeleton) of four words / twelve chars."""
    n = len(sks)
    for i in range(n):
        if not sks[i]:
            continue
        acc = ""
        j = i
        count = 0
        while j < n and (count < _WINDOW_WORDS or len(acc) < _WINDOW_CHARS):
            acc += sks[j]
            if sks[j]:
                count += 1
            j += 1
        if len(acc) < _WINDOW_CHARS:
            return
        yield i, j, acc


def _covered(sks: list[str], hay: str, offsets: Optional[list[tuple[int, int]]] = None
             ) -> tuple[list[bool], list[int]]:
    """Which words occur, in this order, in ``hay``; and in which block.

    A window of at least four words (and twelve skeleton characters) starting
    at each word is searched in ``hay``; a hit covers every word in it, and
    the block whose text the hit starts in becomes the anchor of those words.
    """
    n = len(sks)
    covered = [False] * n
    anchor = [-1] * n
    for i, j, acc in _windows(sks):
        pos = hay.find(acc)
        if pos < 0:
            continue
        blk = -1
        for start, idx in offsets or ():
            if start > pos:
                break
            blk = idx
        for k in range(i, j):
            if not covered[k]:
                covered[k] = True
                anchor[k] = blk
    # Words without a skeleton (punctuation) take their neighbours' state.
    for i in range(1, n - 1):
        if not sks[i] and covered[i - 1] and covered[i + 1]:
            covered[i] = True
            anchor[i] = anchor[i - 1]
    return covered, anchor


def _join_words(words: list[str], vocab: dict[str, str]) -> str:
    """Words as text: syllable hyphenation undone, dropped ligatures restored.

    A word whose skeleton Docling knows elsewhere in the document is written
    in Docling's spelling, so "Re exionsbogen" comes back as
    "Reflexionsbogen". Where the text layer split a word at the dropped
    ligature, the pair is joined when the joined skeleton is known.
    """
    out: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if w.endswith("-") and i + 1 < len(words) and words[i + 1][:1].isalpha():
            # "Hell-" "Dunkel" is a compound and keeps its hyphen; "Positio-"
            # "nierung" is a syllable break and loses it.
            w = (w[:-1] if words[i + 1][:1].islower() else w) + words[i + 1]
            i += 1
        elif i + 1 < len(words):
            pair = skeleton(w + words[i + 1])
            if (skeleton(w) and skeleton(words[i + 1]) and pair in vocab
                    and skeleton(w) not in vocab):
                lead = re.match(r"^\W*", w).group(0)
                trail = re.search(r"\W*$", words[i + 1]).group(0)
                w = lead + vocab[pair] + trail
                i += 1
        core = re.sub(r"^\W+|\W+$", "", w)
        if core:
            known = vocab.get(skeleton(core))
            if known and known != core:
                w = w.replace(core, known, 1)
        out.append(w)
        i += 1
    return " ".join(out)


def _gap_text(run: list[_Word], vocab: dict[str, str]) -> tuple[str, bool]:
    """The text of a gap, and whether it is a table.

    A run spanning two or more lines that all have the same number (two or
    more) of cells is a table: its rows stay rows, its cells are separated by
    " | ". Anything else is prose and is joined into one paragraph.
    """
    lines: dict[int, dict[int, list[str]]] = {}
    for w in run:
        lines.setdefault(w.line, {}).setdefault(w.cell, []).append(w.text)
    cell_counts = {len(cells) for cells in lines.values()}
    if len(lines) >= 2 and len(cell_counts) == 1 and min(cell_counts) >= 2:
        rows = ["| " + " | ".join(_join_words(ws, vocab) for _c, ws in sorted(cells.items()))
                + " |" for _l, cells in sorted(lines.items())]
        return "\n".join(rows), True
    return _join_words([w.text for w in run], vocab), False


def _vocabulary(blocks: list[Block]) -> tuple[dict[str, str], set[str]]:
    """Docling's spelling of every word longer than three letters (by
    skeleton), and the skeletons of all words, figure text left out."""
    vocab: dict[str, str] = {}
    bag: set[str] = set()
    for b in blocks:
        if b.kind == "figure_text":
            continue
        for w in _block_text(b).split():
            core = re.sub(r"^\W+|\W+$", "", w)
            bag.add(skeleton(core))
            if b.kind != "furniture" and len(core) > 3:
                vocab.setdefault(skeleton(core), core)
    return vocab, bag


def cross_check(ext: Extraction, layout_pages: list[str], paged: bool = True) -> IntegrityReport:
    """Compare every page with the text layer; insert what Docling lost.

    Returns the report (also kept on ``ext.integrity``). Each gap is reported
    with its page and with its kind: ``missing`` when most of its words occur
    nowhere in Docling's text, ``reordered`` when Docling has the words but
    not in the order of the page (a word list read column by column across
    pages). Either way the passage goes in with ``repaired=True``: as a
    table when its lines are rows of equally many cells (word cards), else
    as a paragraph. It goes after the block that holds the last covered word
    before the gap on the same page, else before the block of the next
    covered word on that page; a gap with no covered word on its own page
    goes after the previous covered word and the blocks that follow it on
    earlier pages, so that it never stands before a figure of an earlier
    page; else before the next covered word anywhere.

    A page on which Docling covers less than half of the text layer (a page
    of word cards read across the page, a sentence split around a picture)
    is taken from the text layer whole, as one passage, and reported in
    ``replaced_pages``.

    A Docling block that only repeats repaired text is removed and reported
    as superseded: on a replaced page, every block whose words the repaired
    passages contain; elsewhere, a block whose words the repaired passages
    contain and that does not follow the order of the text layer.

    Two kinds of uncovered run are not lost text and are not inserted; they
    are reported in ``gaps_dismissed``. "debris": less than half of its
    characters stand in words (plot ticks, a number grid read line by line,
    a lettering set along a curve), or one token in ten is a mathematical
    sign or a Greek letter (a formula). "duplicate": its words stand in the Docling blocks that remain on
    its page and the neighbouring pages (a column or table read across, the
    labels of a picture, a running head, a reference split at a line break).
    Neither test applies on a replaced page; table rows are only tested for
    formulas.
    """
    rep = ext.integrity
    if not layout_pages or not any(p.strip() for p in layout_pages):
        rep.checked = False
        rep.reason = "no text layer"
        return rep
    blocks = ext.blocks
    vocab, bag = _vocabulary(blocks)
    page_hay: dict[int, list[tuple[str, int]]] = {}
    for idx, b in enumerate(blocks):
        if b.kind == "figure_text":
            continue                    # text inside a picture is not body text
        t = _block_text(b)
        if not t:
            continue
        page_hay.setdefault(b.page, []).append((skeleton(t), idx))

    pages: list[tuple[int, list[_Word], list[bool], list[int]]] = []
    for pno, text in enumerate(layout_pages, start=1):
        words = _page_words(text, columns=paged)
        if not words:
            continue
        hay = ""
        offsets: list[tuple[int, int]] = []
        for p in (pno - 1, pno, pno + 1):
            for s, idx in page_hay.get(p, []):
                offsets.append((len(hay), idx))
                hay += s
        covered, anchor = _covered([w.sk for w in words], hay, offsets)
        pages.append((pno, words, covered, anchor))
    rep.checked = True
    rep.pages_checked = len(pages)

    # Covered words with an anchor, in reading order across the document.
    flat: list[int] = []
    for _p, _w, covered, anchor in pages:
        flat.extend(a for c, a in zip(covered, anchor) if c and a >= 0)
    for pno, words, covered, _a in pages:
        total = sum(len(w.sk) for w in words)
        hit = sum(len(w.sk) for w, c in zip(words, covered) if c)
        if total >= GAP_MIN_CHARS and hit < PAGE_REPLACE_BELOW * total:
            rep.replaced_pages.append(pno)

    cands: list[tuple[Gap, list[str], int, bool, Block, bool]] = []
    replaced = set(rep.replaced_pages)
    done = 0                                        # anchored words on earlier pages
    for pno, words, covered, anchor in pages:
        n = len(words)

        def anchored_before(k: int) -> int:
            return done + sum(1 for c, a in zip(covered[:k], anchor[:k]) if c and a >= 0)

        gapmask = [False] * n if pno in rep.replaced_pages else covered
        i = 0
        while i < n:
            if gapmask[i]:
                i += 1
                continue
            j = i
            while j < n and not gapmask[j]:
                j += 1
            run = words[i:j]
            sks = [w.sk for w in run if w.sk]
            if len(sks) >= GAP_MIN_WORDS and len("".join(sks)) >= GAP_MIN_CHARS:
                text, table = _gap_text(run, vocab)
                known = sum(1 for s in sks if s in bag)
                bpage = pno if paged else 0
                gap = Gap(page=bpage, text=text, words=len(run),
                          kind="reordered" if known >= 0.5 * len(sks) else "missing")
                prev_same = next((anchor[k] for k in range(i - 1, -1, -1)
                                  if covered[k] and anchor[k] >= 0
                                  and blocks[anchor[k]].page == bpage), -1)
                next_same = next((anchor[k] for k in range(j, n)
                                  if covered[k] and anchor[k] >= 0
                                  and blocks[anchor[k]].page == bpage), -1)
                cut_prev, cut_next = anchored_before(i), anchored_before(j)
                prev_any = flat[cut_prev - 1] if cut_prev > 0 else -1
                next_any = flat[cut_next] if cut_next < len(flat) else -1
                if prev_same >= 0:
                    target, after = prev_same, True
                elif next_same >= 0:
                    target, after = next_same, False
                elif prev_any >= 0:
                    # Past the blocks of earlier pages that follow the anchor
                    # (figures Docling placed after the last text of a page).
                    target, after = prev_any, True
                    while (target + 1 < len(blocks)
                           and 0 < blocks[target + 1].page < bpage):
                        target += 1
                elif next_any >= 0:
                    target, after = next_any, False
                else:
                    target, after = len(blocks), False
                gap.anchor = ("end" if target >= len(blocks) else
                              f"{'after' if after else 'before'} {blocks[target].ref or target}")
                blk = (Block(kind="table", markdown=text, page=bpage, repaired=True)
                       if table else Block(kind="paragraph", text=text, page=bpage,
                                           repaired=True))
                debris = pno not in replaced and (
                    (not table and _word_share(run) < GAP_WORD_SHARE)
                    or _formula_share(text) >= GAP_FORMULA_SHARE)
                cands.append((gap, sks, target, after, blk, debris))
            i = j
        done += sum(1 for c, a in zip(covered, anchor) if c and a >= 0)

    # Text-layer skeleton per page, in reading order, for the superseded test.
    layer = {pno: "".join(w.sk for w in words) for pno, words, _c, _a in pages}
    # A gap whose words Docling keeps in the blocks that remain is a
    # duplicate. Dismissing one leaves more blocks in place, which can make
    # another gap a duplicate; repeated until nothing changes.
    kept = [k for k in range(len(cands)) if not cands[k][5]]
    while True:
        repaired_bag = {s for k in kept for s in cands[k][1]}
        gone = {idx for idx, b in enumerate(blocks)
                if _superseded(b, layer, repaired_bag, b.page in replaced)}
        page_words: dict[int, set[str]] = {}
        page_text: dict[int, str] = {}
        for idx, b in enumerate(blocks):
            if idx not in gone:
                t = _block_text(b)
                page_words.setdefault(b.page, set()).update(skeleton(w) for w in t.split())
                page_text[b.page] = page_text.get(b.page, "") + "|" + skeleton(t)
        dup = [k for k in kept if cands[k][0].page not in replaced
               and _duplicate(cands[k][1], cands[k][0].page, page_words, page_text)]
        if not dup:
            break
        kept = [k for k in kept if k not in dup]
    for k in range(len(cands)):
        if k not in kept:
            dup = _duplicate(cands[k][1], cands[k][0].page, page_words, page_text)
            rep.gaps_dismissed.append(_dismissed(cands[k][0],
                                                 "duplicate" if dup else "debris"))

    if not kept:
        return rep
    before: dict[int, list[Block]] = {}
    after_: dict[int, list[Block]] = {}
    for k in kept:
        gap, _sks, target, after, blk, _debris = cands[k]
        gap.repaired = True
        blk.ref = f"#/repaired/{len(rep.gaps)}"
        rep.gaps.append(gap)
        (after_ if after else before).setdefault(target, []).append(blk)

    merged: list[Block] = []
    for idx, b in enumerate(blocks):
        merged.extend(before.get(idx, []))
        if idx in gone:
            rep.superseded.append({"page": b.page, "ref": b.ref, "text": b.text[:120]})
        else:
            merged.append(b)
        merged.extend(after_.get(idx, []))
    merged.extend(before.get(len(blocks), []))
    ext.blocks = merged
    return rep


_WORD_TOKEN_RE = re.compile(r"(?=(?:[^\W\d_][-'’*]?){3})[^\W\d_]+(?:[-'’*][^\W\d_]+)*")


def _word_share(run: list[_Word]) -> float:
    """Share of the characters of a run that stand in words: three letters or
    more, joined by hyphens or apostrophes, punctuation around them stripped.
    Formula symbols, numbers, single letters, axis ticks and the syllables of
    a lettering set along a curve are not words; the short words of prose
    weigh little."""
    toks = [re.sub(r"^\W+|\W+$", "", w.text) for w in run
            if not w.text.startswith("\\")]           # a TeX command is no word
    total = sum(len(re.sub(r"^\W+|\W+$", "", w.text)) for w in run)
    return sum(len(t) for t in toks if _WORD_TOKEN_RE.fullmatch(t)) / max(1, total)


def _formula_share(text: str) -> float:
    """Mathematical signs (Unicode class Sm, the bars of a table row left out)
    and Greek letters per token."""
    toks = [t for t in text.split() if t != "|"]
    signs = sum(1 for ch in text if ch != "|" and (
        unicodedata.category(ch) == "Sm" or "GREEK" in unicodedata.name(ch, "")))
    return signs / max(1, len(toks))


def _duplicate(sks: list[str], page: int, page_words: dict[int, set[str]],
               page_text: dict[int, str]) -> bool:
    """The gap's text stands in the remaining blocks of its page or a
    neighbouring page: as one piece (a run that begins inside a word Docling
    joined at a line break), or word by word to GAP_DUPLICATE_SHARE (words of
    three letters or more; numbers are left out, since Docling drops page and
    paragraph numbers)."""
    near = (page - 1, page, page + 1)
    if any("".join(sks) in page_text.get(p, "") for p in near):
        return True
    words = [s for s in sks if len(s) > 2 and not s.isdigit()] or sks
    have = set().union(*(page_words.get(p, set()) for p in near))
    return sum(1 for s in words if s in have) >= GAP_DUPLICATE_SHARE * len(words)


def _dismissed(gap: Gap, reason: str) -> dict:
    return {"page": gap.page, "words": gap.words, "reason": reason, "text": gap.text[:200]}


def _superseded(b: Block, layer: dict[int, str], repaired_bag: set[str],
                on_replaced_page: bool) -> bool:
    if b.kind not in ("paragraph", "list_item") or b.repaired or not repaired_bag:
        return False
    sks = [skeleton(w) for w in b.text.split()]
    sks = [s for s in sks if s]
    if not sks or sum(1 for s in sks if s in repaired_bag) < 0.9 * len(sks):
        return False
    if on_replaced_page:
        return True
    if len(sks) < _WINDOW_WORDS:
        return False
    # Pages separated, so that no window is found across a page boundary.
    hay = "|".join(layer.get(p, "") for p in (b.page - 1, b.page, b.page + 1))
    covered, _ = _covered(sks, hay)
    return sum(covered) < 0.5 * len(sks)


_LINE_END_HYPHEN_RE = re.compile(r"(\w+)-$")
_CAPITAL_START_RE = re.compile(r"^([A-ZÄÖÜ]\w*)")


def restore_compound_hyphens(ext: Extraction, layout_pages: list[str]) -> list[dict]:
    """Put back the hyphen of a compound that Docling joined at a line break.

    Docling undoes every line-end hyphen. Where the word goes on with a
    capital letter ("Hell-" / "Dunkel-Kontraste", p. 9 of "Monster im
    Dialog"), the hyphen belongs to the word, and "HellDunkel" is wrong. The
    text layer shows each such break; a joined spelling that the text layer
    never shows as one word is replaced by the hyphenated one in the blocks
    of that page. Reported in ``hyphens_restored``.
    """
    rep = ext.integrity
    layer_words: set[str] = set()
    breaks: dict[int, set[tuple[str, str]]] = {}
    for page_no, page in enumerate(layout_pages, 1):
        lines = reading_lines(page)
        layer_words.update(re.findall(r"\w+", page))
        for a, b in zip(lines, lines[1:]):
            m, n = _LINE_END_HYPHEN_RE.search(a), _CAPITAL_START_RE.match(b)
            if m and n:
                breaks.setdefault(page_no, set()).add((m.group(1), n.group(1)))
    for b in ext.blocks:
        for left, right in breaks.get(b.page, ()):
            joined = left + right
            if joined in layer_words:
                continue
            pattern = re.compile(r"\b" + re.escape(joined) + r"\b")
            for attr in ("text", "caption"):
                value = getattr(b, attr)
                if value and pattern.search(value):
                    setattr(b, attr, pattern.sub(f"{left}-{right}", value))
                    rep.hyphens_restored.append(
                        {"page": b.page, "ref": b.ref, "word": f"{left}-{right}"})
    return rep.hyphens_restored


# --------------------------------------------------------------------------
# Reading order within a page
# --------------------------------------------------------------------------

# The kinds whose order on the page is compared with the text layer. Figures
# and tables are left out: the text layer sets a caption or a table cell
# wherever the layout puts it, which says nothing about the reading order.
_ORDER_KINDS = frozenset({"title", "heading", "paragraph", "list_item"})
ORDER_MIN_WORDS = 3
# A group of blocks is replaced by the text layer only when the layer passage
# is this close in length to the group's text.
_ORDER_LENGTH_TOLERANCE = 0.15
# Blocks between the paragraphs of a repaired group that are kept as they
# are, after the repaired paragraph: figures and what belongs to them.
_ORDER_KEPT = ("figure", "figure_text", "furniture")


def _longest_rising(seq: list[int]) -> set[int]:
    """Indices of one longest non-decreasing subsequence of ``seq``."""
    import bisect
    tails: list[int] = []
    tails_at: list[int] = []
    prev = [-1] * len(seq)
    for i, x in enumerate(seq):
        k = bisect.bisect_right(tails, x)
        if k == len(tails):
            tails.append(x)
            tails_at.append(i)
        else:
            tails[k] = x
            tails_at[k] = i
        prev[i] = tails_at[k - 1] if k > 0 else -1
    out: set[int] = set()
    i = tails_at[-1] if tails_at else -1
    while i >= 0:
        out.add(i)
        i = prev[i]
    return out


@dataclass
class _PageOrder:
    words: list[_Word]
    word_block: list[int]          # index into ext.blocks, -1 = not found
    runs: list[tuple[int, int]]    # displaced word runs [a, b)
    inorder: list[bool]


def _page_order(ext: Extraction, pno: int, page_text: str,
                columns: bool = True) -> Optional[_PageOrder]:
    idxs = [i for i, b in enumerate(ext.blocks)
            if b.page == pno and b.kind in _ORDER_KINDS and b.text]
    if not idxs:
        return None
    hay = ""
    offsets: list[tuple[int, int]] = []
    for i in idxs:
        offsets.append((len(hay), i))
        hay += skeleton(ext.blocks[i].text)
    # Docling files a paragraph that runs over a page break under the page it
    # starts on, so the layer of this page can hold words of a block of the
    # page before; a window is unique only if the neighbouring pages' text
    # does not hold it either.
    near = "|".join(skeleton(b.text) for b in ext.blocks
                    if b.kind in _ORDER_KINDS and b.text and abs(b.page - pno) <= 1)
    words = _page_words(page_text, columns)
    sks = [w.sk for w in words]
    layer = "".join(sks)
    hits: list[tuple[int, int, int, int]] = []       # (start, end, pos, block)
    last = 0
    for i, j, acc in _windows(sks):
        # A window that occurs twice on the page, in the layer or in Docling's
        # text, says nothing about the order: a running head repeating the
        # title ("Sensing a Planet in Crisis" over p. 2 of Gabrys 2019, and in
        # its paragraph), a phrase the author uses twice on one page (p. 3,
        # "formations of citizenship and political engagement"), a phrase of
        # the page before's paragraph continued here (p. 3, "of media and
        # environment."). Located at the other occurrence it reads as
        # displaced text.
        if layer.count(acc) > 1 or near.count(acc) > 1:
            continue
        pos = hay.find(acc, last)
        if pos < 0:
            pos = hay.find(acc)
        if pos < 0:
            continue
        last = max(last, pos)
        blk = -1
        for start, idx in offsets:
            if start > pos:
                break
            blk = idx
        hits.append((i, j, pos, blk))
    n = len(words)
    keep = _longest_rising([h[2] for h in hits])
    inorder = [False] * n
    displaced = [False] * n
    word_block = [-1] * n
    for k, (i, j, _pos, blk) in enumerate(hits):
        if word_block[i] < 0:
            word_block[i] = blk
        for w in range(i, j):
            if k in keep:
                inorder[w] = True
            else:
                displaced[w] = True
    for k, (i, j, _pos, blk) in enumerate(hits):
        for w in range(i, j):
            if word_block[w] < 0:
                word_block[w] = blk
    runs: list[tuple[int, int]] = []
    w = 0
    while w < n:
        if not (displaced[w] and not inorder[w]):
            w += 1
            continue
        a = w
        while w < n and displaced[w] and not inorder[w]:
            w += 1
        if sum(1 for x in words[a:w] if x.sk) >= ORDER_MIN_WORDS:
            runs.append((a, w))
    return _PageOrder(words, word_block, runs, inorder)


def _repair_order_run(ext: Extraction, pno: int, po: _PageOrder, run: tuple[int, int],
                      vocab: dict[str, str], seq: int) -> tuple[bool, str, list[str]]:
    """Replace the blocks a displaced run belongs to by the text layer's
    passage, when that can be done without guessing: the blocks form one
    contiguous group on this page of paragraphs (figures between them are
    kept, after the passage), the layer passage holds the words of exactly
    these blocks, and its length matches theirs. Returns (repaired, note,
    refs)."""
    a, b = run
    involved = {po.word_block[w] for w in range(a, b) if po.word_block[w] >= 0}
    before = next((po.word_block[w] for w in range(a - 1, -1, -1)
                   if po.inorder[w] and po.word_block[w] >= 0), -1)
    after = next((po.word_block[w] for w in range(b, len(po.words))
                  if po.inorder[w] and po.word_block[w] >= 0), -1)
    involved |= {x for x in (before, after) if x >= 0}
    if not involved:
        return False, "the run's words belong to no block", []
    lo, hi = min(involved), max(involved)
    group = ext.blocks[lo:hi + 1]
    refs = [ext.blocks[i].ref for i in sorted(involved)]
    odd = sorted({g.kind for g in group if g.kind not in ("paragraph",) + _ORDER_KEPT}
                 | ({"other page"} if any(g.page != pno for g in group) else set()))
    if odd:
        return False, f"blocks of kind {', '.join(odd)} are involved", refs
    texts = {i for i in range(lo, hi + 1) if ext.blocks[i].kind == "paragraph"}
    span = [w for w, blk in enumerate(po.word_block) if blk in texts]
    if not span:
        return False, "no layer passage", refs
    first, last = min(span), max(span)
    foreign = [w for w in range(first, last + 1)
               if po.word_block[w] >= 0 and po.word_block[w] not in texts]
    if foreign:
        return False, "the layer passage interleaves other blocks", refs
    passage = po.words[first:last + 1]
    layer_len = sum(len(w.sk) for w in passage)
    group_len = sum(len(skeleton(ext.blocks[i].text)) for i in texts)
    if not group_len or abs(layer_len - group_len) > _ORDER_LENGTH_TOLERANCE * group_len:
        return False, (f"layer passage ({layer_len} letters) and blocks ({group_len}) "
                       "differ in length"), refs
    merged = Block(kind="paragraph", text=_join_words([w.text for w in passage], vocab),
                   page=pno, repaired=True, ref=f"#/reordered/{seq}")
    figures = [g for g in group if g.kind in _ORDER_KEPT]
    ext.blocks[lo:hi + 1] = [merged] + figures
    return True, f"{len(texts)} blocks replaced by the text layer's passage", refs


def _displaced_words(po: _PageOrder) -> int:
    return sum(b - a for a, b in po.runs)


def _page_order_best(ext: Extraction, pno: int, layout_text: str,
                     flow_text: Optional[str]) -> tuple[Optional[_PageOrder], str, bool]:
    """The page's order against the reading of the text layer that agrees
    best with Docling: the layout mode split at its column gutter, or
    pdftotext's flow order. Returns (order, text, columns) so a repaired page
    is compared again against the same reading."""
    po = _page_order(ext, pno, layout_text)
    if po is None or not po.runs or flow_text is None:
        return po, layout_text, True
    pf = _page_order(ext, pno, flow_text, columns=False)
    if pf is not None and _displaced_words(pf) < _displaced_words(po):
        return pf, flow_text, False
    return po, layout_text, True


# Headings that are pure front/back-matter scaffolding (knowledge_processing
# skips their sections entirely: never a content section, never paratext).
_SKIP_HEADING_HINTS = (
    "table of contents", "contents", "inhalt", "inhaltsverzeichnis",
    "list of abbreviations", "abbreviations", "acronyms", "abkürzungen",
    "abkuerzungen", "glossary of terms",
    "list of boxes", "list of figures", "list of tables", "list of acronyms",
    "abbildungsverzeichnis", "tabellenverzeichnis",
    "acknowledgements", "acknowledgments", "danksagung", "impressum",
    "imprint", "colophon", "copyright", "credits",
    "index", "endnotes", "notes",
)
# The source's bibliography (knowledge_processing keeps it verbatim as the
# file's LITERATUR section, 2026-11-13).
_BIBLIOGRAPHY_HINTS = (
    "bibliography", "references", "literaturverzeichnis", "literatur",
    "quellenverzeichnis", "quellen", "sources", "works cited",
)


def _norm_heading(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower())


_HEADING_NUMBERING_RE = re.compile(r"^(?:[\dIVXLC]+[.)]?\s*)+")
_HEADING_TAIL_RE = re.compile(r"[\s.:]+$")


def _heading_matches(heading: str, hints: tuple[str, ...]) -> bool:
    """The heading, without its numbering and closing punctuation, IS one of
    the hints, or starts with one followed by a separator ("Literatur: …",
    "References (selection)"). A heading that merely contains a hint word
    ("Inhaltliche Grundlagen", "Notes on practice") does not match: the
    substring match of the old procedure dropped such content sections."""
    hn = _HEADING_TAIL_RE.sub("", _HEADING_NUMBERING_RE.sub("", _norm_heading(heading)))
    for hint in hints:
        if hn == hint:
            return True
        if hn.startswith(hint) and re.match(r"\s*[:(–—-]", hn[len(hint):]):
            return True
    return False


ORDER_SECTION_BIBLIOGRAPHY = "bibliography"
ORDER_SECTION_APPARATUS = "apparatus"


def _order_sections(blocks: list[Block]) -> list[str]:
    """Per block, the back-matter section it stands in: under a heading named
    by _BIBLIOGRAPHY_HINTS or _SKIP_HEADING_HINTS up to the next heading of
    the same or a higher level, as knowledge_processing.clean_blocks and
    bibliography() delimit these sections; "" for the body."""
    out: list[str] = []
    cur, level = "", None
    for b in blocks:
        if b.kind in ("heading", "title"):
            lv = b.level or 1
            if level is not None and lv <= level:
                cur, level = "", None
            if level is None:
                if _heading_matches(b.text or "", _BIBLIOGRAPHY_HINTS):
                    cur, level = ORDER_SECTION_BIBLIOGRAPHY, lv
                elif _heading_matches(b.text or "", _SKIP_HEADING_HINTS):
                    cur, level = ORDER_SECTION_APPARATUS, lv
        out.append(cur)
    return out


# Junctions: where two body blocks that Docling reads one after the other
# meet, the sentence either runs on as some reading of the text layer has it,
# or it breaks. Of 64 unrepaired findings across 30 documents read against
# the page images (2026-11-13), 15 changed what the text says (a sentence
# cut by a heading or by another paragraph, a fragment set after the next
# heading), 24 were real but harmless (two list items or two notes swapped
# with their markers kept, a caption beside its paragraph, a bibliography
# entry) and 25 came from a layer reading that interleaves two columns or
# reads a grid row by row. Only the first kind fails the check.
_JUNCTION_KINDS = frozenset({"title", "heading", "paragraph", "list_item"})
_JUNCTION_TEXT = frozenset({"paragraph", "list_item"})
_JUNCTION_WORDS = 3
_SENTENCE_END_RE = re.compile(r"[.!?:;\"”“»«'’)\]]\s*$")
# Note markers after a closing sign ("… 2019).12", "… werden.*").
_NOTE_MARK_RE = re.compile(r"(?<=[.!?:;\"”’)\]])[\d*†‡,\s]+$")


def _sentence_ends(text: str) -> bool:
    return bool(_SENTENCE_END_RE.search(_NOTE_MARK_RE.sub("", text.strip())))


def _sentence_open(text: str) -> bool:
    """The block stops on a comma, a hyphen, an opening bracket, or a
    lowercase word: the sentence goes on elsewhere."""
    w = _NOTE_MARK_RE.sub("", text.strip()).split()
    if not w:
        return False
    x = w[-1]
    return x[-1:] in ",-–(" or (x[:1].islower() and x.isalpha())


def _skeleton_words(text: str) -> list[str]:
    """The skeletons of the words of ``text`` that carry two letters or
    more. Single letters, numbers and symbols are what formulas, note
    markers and figure lettering are made of; one reading of the layer sets
    them between two blocks and Docling does not have them there (formula
    (5) between "we let" and "from which we obtain", p. 4 of Arora and
    Zhang 2017)."""
    return [s for s in (skeleton(x) for x in text.split())
            if sum(ch.isalpha() for ch in s) >= 2]


def _junction_block(b: Block) -> bool:
    """A block whose start and end say something about a sentence: body
    text, not a label of fewer than five words without a closing sign (an
    axis title, a box caption Docling read as a paragraph), not formula or
    plot debris."""
    t = (b.text or "").strip()
    if b.kind not in _JUNCTION_KINDS or not t:
        return False
    if b.kind in _JUNCTION_TEXT:
        if len(t.split()) < 5 and not _SENTENCE_END_RE.search(t) and not t[:1].islower():
            return False
        if _word_share([_Word(x, "", 0, 0) for x in t.split()]) < GAP_WORD_SHARE:
            return False
    return True


def _layer_readings(ext: Extraction, pno: int, layout_text: str,
                    flow_text: Optional[str]) -> list[str]:
    """The page's text layer in its three readings (layout split at the
    gutter, layout line by line, flow), each as a space-joined skeleton
    restricted to words Docling has on this page or the next one to either
    side, so running heads, page numbers and figure lettering do not stand
    between the end of one block and the start of the next."""
    body = {s for b in ext.blocks if b.kind in _ORDER_KINDS and b.text
            and abs((b.page or 0) - pno) <= 1 for s in _skeleton_words(b.text)}
    out = []
    for text, columns in ((layout_text, True), (layout_text, False), (flow_text, False)):
        if text is None:
            continue
        out.append(" " + " ".join(w.sk for w in _page_words(text, columns)
                                  if w.sk and w.sk in body) + " ")
    return out


def _runs_on(a: str, b: str, readings: list[str]) -> bool:
    """The last words of ``a`` and the first of ``b`` stand together in a
    reading of the layer."""
    ta, hb = _skeleton_words(a)[-_JUNCTION_WORDS:], _skeleton_words(b)[:_JUNCTION_WORDS]
    if len(ta) < 2 or len(hb) < 2:
        return False
    pat = " " + " ".join(ta + hb) + " "
    return any(pat in r for r in readings)


_NEIGHBOUR_WORDS = 12
_HOLDING_WORDS = 5


def _neighbours(words: list[str], readings: list[str], after: bool) -> list[list[str]]:
    """The words that follow (or precede) ``words`` in each reading where
    they occur exactly once, up to _NEIGHBOUR_WORDS of them."""
    pat = " " + " ".join(words) + " "
    out = []
    for r in readings:
        if r.count(pat) != 1:
            continue
        i = r.index(pat)
        near = (r[i + len(pat):].split()[:_NEIGHBOUR_WORDS] if after
                else r[:i].split()[-_NEIGHBOUR_WORDS:])
        if len(near) >= 4:
            out.append(near)
    return out


def _block_holding(ext: Extraction, pno: int, words: list[str],
                   from_end: bool = False) -> Optional[int]:
    """The one body block on the page whose text holds these skeleton words:
    the shortest run of them, from _HOLDING_WORDS words on and taken from
    the side next to the junction (the end when ``from_end``), that exactly
    one block holds. A common phrase stands in several blocks and the words
    after it decide ("human rights and fundamental freedoms", p. 18 of the
    UNESCO Recommendation on the Ethics of AI); once no block holds the run,
    it has crossed into the next block and there is no answer."""
    texts = [(i, " " + " ".join(_skeleton_words(b.text)) + " ")
             for i, b in enumerate(ext.blocks)
             if b.page == pno and b.kind in _ORDER_KINDS and b.text]
    for k in range(min(_HOLDING_WORDS, len(words)), len(words) + 1):
        pat = " " + " ".join(words[-k:] if from_end else words[:k]) + " "
        hit = [i for i, t in texts if pat in t]
        if len(hit) == 1:
            return hit[0]
        if not hit:
            return None
    return None


def _junction_breaks(ext: Extraction, pno: int, lo: int, hi: int,
                     readings: list[str]) -> list[str]:
    """Junctions between consecutive body blocks of the page, within the
    block range [lo, hi] of a finding, where Docling breaks a sentence:

    - a block stops mid-sentence and a heading follows, while the layer
      continues the sentence in a third block ("including" / "POLICY AREA
      5", p. 30 of the UNESCO Recommendation);
    - a block stops mid-sentence and the next one does not continue it in
      any reading, while the layer continues it in a third block;
    - a block starts lowercase and does not continue the one before it in
      any reading, while the layer has it continue a third block;
    - a block starts lowercase and the layer sets it inside the block
      before it, not after that block's end: Docling took it out of the
      middle of a sentence ("derives a model in which" / "three
      interrelated core elements of resilience", p. 5 of Jörissen and
      Klepacki 2026).
    """
    body = [(i, b) for i, b in enumerate(ext.blocks) if b.page == pno and _junction_block(b)]
    out: list[str] = []
    for (ia, a), (ib, b) in zip(body, body[1:]):
        if ib < lo or ia > hi:
            continue
        ta, tb = a.text.strip(), b.text.strip()
        mid = a.kind in _JUNCTION_TEXT and not _sentence_ends(ta) and _sentence_open(ta)
        first = tb.split()[0]
        # A lowercase word, not a symbol of a notation list ("η A predictor
        # function", "v A column vector", p. 21 of Belrose 2023).
        low = (b.kind in _JUNCTION_TEXT and len(first) >= 2 and first.isalpha()
               and first.islower())
        if not (mid or low):
            continue
        if not (mid and b.kind in ("heading", "title")) and _runs_on(ta, tb, readings):
            continue
        what = f"{ta[-40:]!r} | {tb[:40]!r}"
        if mid:
            nxt = (_block_holding(ext, pno, w) for w in
                   _neighbours(_skeleton_words(ta)[-_JUNCTION_WORDS:], readings, after=True))
            if any(x is not None and x not in (ia, ib) for x in nxt):
                out.append(f"sentence cut: {what}")
                continue
        if low and b.kind not in ("heading", "title"):
            tail = _skeleton_words(ta)[-_JUNCTION_WORDS:]
            prv = [(w, _block_holding(ext, pno, w, from_end=True)) for w in
                   _neighbours(_skeleton_words(tb)[:_JUNCTION_WORDS], readings, after=False)]
            if any(x is not None and x not in (ia, ib) for _w, x in prv):
                out.append(f"sentence start detached: {what}")
            elif any(x == ia and w[-len(tail):] != tail for w, x in prv):
                out.append(f"sentence start cut out of the block before: {what}")
    return out


def _cut_out(ext: Extraction, pno: int, text: str, readings: list[str]) -> Optional[str]:
    """The displaced passage stands, in a reading of the layer, between two
    words that one Docling block has side by side: Docling took it out of
    the middle of that block's sentence and set it elsewhere."""
    sk = _skeleton_words(text)
    if len(sk) < _JUNCTION_WORDS:
        return None
    pre = _neighbours(sk[:_JUNCTION_WORDS], readings, after=False)
    post = _neighbours(sk[-_JUNCTION_WORDS:], readings, after=True)
    joins = {" " + " ".join(p[-_JUNCTION_WORDS:] + q[:_JUNCTION_WORDS]) + " "
             for p in pre for q in post}
    for b in ext.blocks:
        if b.page != pno or not _junction_block(b):
            continue
        bsk = " " + " ".join(_skeleton_words(b.text)) + " "
        if any(j in bsk for j in joins):
            return f"passage cut out of {b.text.strip()[:40]!r}"
    return None


def check_reading_order(ext: Extraction, layout_pages: list[str],
                        flow_pages: Optional[list[str]] = None) -> list[OrderFinding]:
    """Compare the order of Docling's text on each page with the text layer.

    The text layer has two readings: the layout mode split at a two-column
    gutter, and pdftotext's flow order. Neither is right on every page: the
    layout mode reads a three-column bibliography line by line across the
    columns (p. 11 of Park 2024, "White Default"), the flow mode does not
    know which of two columns comes first when one stands beside a figure.
    A page is compared with the reading that agrees best with Docling, so a
    passage counts as displaced only when no reading of the layer supports
    Docling's order (Park 2024: 100 findings against the layout reading, 16
    against the better of the two).

    For every page that was not replaced whole, the four-word windows of the
    text layer are located in Docling's text of that page (headings,
    paragraphs, list items, in Docling's order). Where the located positions
    fall back, the words that leave the longest rising sequence are text
    Docling put elsewhere ("einem Vulkan mit rotem Mond – noch / auch die Sonne
    sein könnte" read before "ohne dunklen Himmel, sodass das Rote", p. 9 of
    "Monster im Dialog"). Each such run of three words or more is a finding.
    A finding is repaired when the blocks involved are paragraphs of one
    page, contiguous apart from figures: they are replaced by the text
    layer's passage in the layer's order, the figures follow it. Any other
    finding stays unrepaired -- a grid of numbered steps read row by row by
    Docling and column by column by the text layer is such a case, since
    neither order can be taken as the page's. An unrepaired finding carries
    the junctions where Docling breaks a sentence (_junction_breaks) and the
    back-matter section it stands in (_order_sections); only a finding with
    a broken sentence in the body text fails the check
    (OrderFinding.breaks_text).
    """
    rep = ext.integrity
    replaced = set(rep.replaced_pages)
    vocab, _bag = _vocabulary(ext.blocks)
    seq = 0
    for pno, layout_text in enumerate(layout_pages, start=1):
        if pno in replaced:
            continue
        flow_text = (flow_pages[pno - 1] if flow_pages is not None
                     and pno <= len(flow_pages) else None)
        po, text, columns = _page_order_best(ext, pno, layout_text, flow_text)
        if po is None:
            continue
        rep.order_pages_checked += 1
        for _attempt in range(50):
            if not po.runs:
                break
            for run in po.runs:
                ok, note, refs = _repair_order_run(ext, pno, po, run, vocab, seq)
                if ok:
                    rep.order.append(OrderFinding(
                        page=pno, text=_join_words([w.text for w in po.words[run[0]:run[1]]], vocab),
                        words=run[1] - run[0], refs=refs, repaired=True, note=note))
                    seq += 1
                    break
            else:
                for run in po.runs:
                    _ok, note, refs = _repair_order_run(ext, pno, po, run, vocab, seq)
                    rep.order.append(OrderFinding(
                        page=pno, text=_join_words([w.text for w in po.words[run[0]:run[1]]], vocab),
                        words=run[1] - run[0], refs=refs, repaired=False, note=note))
                break
            po = _page_order(ext, pno, text, columns)
            if po is None:
                break
    left = [o for o in rep.order if not o.repaired]
    if left:
        sections = _order_sections(ext.blocks)
        at = {b.ref: i for i, b in enumerate(ext.blocks) if b.ref}
        readings: dict[int, list[str]] = {}
        for o in left:
            idx = [at[r] for r in o.refs if r in at]
            if not idx:
                continue
            o.section = sections[min(idx)]
            if o.page not in readings:
                flow_text = (flow_pages[o.page - 1] if flow_pages is not None
                             and o.page <= len(flow_pages) else None)
                readings[o.page] = _layer_readings(ext, o.page, layout_pages[o.page - 1], flow_text)
            o.breaks = _junction_breaks(ext, o.page, min(idx), max(idx), readings[o.page])
            cut = _cut_out(ext, o.page, o.text, readings[o.page])
            if cut:
                o.breaks.append(cut)
    return rep.order


def restore_page_order(ext: Extraction) -> list[dict]:
    """Put every block on its page in page order, keeping the order within
    a page: a block that stands after a block of a later page is moved back
    (stable sort by page; a block without a page goes with the block before
    it). Reported in ``page_order_moved``."""
    keyed: list[tuple[int, int, Block]] = []
    page = 0
    for i, b in enumerate(ext.blocks):
        if b.page:
            page = b.page
        keyed.append((page, i, b))
    highest = 0
    for page, _i, b in keyed:
        if page < highest:
            ext.integrity.page_order_moved.append(
                {"page": b.page, "ref": b.ref, "kind": b.kind, "after_page": highest})
        highest = max(highest, page)
    if ext.integrity.page_order_moved:
        ext.blocks = [b for _p, _i, b in sorted(keyed, key=lambda t: (t[0], t[1]))]
    return ext.integrity.page_order_moved


# --------------------------------------------------------------------------
# Page numbering
# --------------------------------------------------------------------------

_FOLIO_RE = re.compile(r"^\d{1,4}$")
# A folio offset counts when this share of the pages with text carries it.
FOLIO_MIN_SHARE = 0.5


def _pdf_page_labels(pdf: Path) -> Optional[list[str]]:
    """The PDF's /PageLabels, one label per page, or None when the file has
    none (pypdf answers '1'..'n' then) or pypdf is not installed."""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return None
    try:
        reader = PdfReader(str(pdf))
        if "/PageLabels" not in reader.trailer["/Root"]:
            return None
        return [str(x) for x in reader.page_labels]
    except Exception:  # noqa: BLE001 - a damaged label tree means no labels
        return None


def _folio_offsets(page_text: str, pdf_page: int) -> set[int]:
    """Offsets (printed - PDF page) that a bare number at the start or the
    end of one of the first or last three lines of the page would give. A
    rule set against the number counts with it ("|9", "24|" in the galley of
    Jörissen & Marotzki 2009)."""
    lines = [l.split() for l in page_text.split("\n") if l.strip()]
    out: set[int] = set()
    for toks in lines[:3] + lines[-3:]:
        for tok in (toks[0].strip("|"), toks[-1].strip("|")):
            if _FOLIO_RE.match(tok) and int(tok) > 0:
                out.add(int(tok) - pdf_page)
    return out


def detect_page_numbering(layout_pages: list[str], pdf: Optional[Path]
                          ) -> tuple[str, dict[int, int], dict]:
    """How the pages of the source are numbered in print.

    1. The PDF's page labels (/PageLabels), where at least half of them are
       arabic numbers; a page with another label (roman front matter, "Cover")
       has no printed number.
    2. Else the folio: a bare number of up to four digits at the start or end
       of one of the first or last three lines of a page. The difference to
       the PDF page that most pages share is taken when at least half of the
       pages with text (and at least two) carry it ("Von der Entmachtung des
       westlichen Blicks": PDF pages 1-2 are printed 72-73).
    3. Else the PDF page.

    Returns (kind, map PDF page -> printed page with 0 for "no printed
    number", detail for the sidecar).
    """
    n = len(layout_pages)
    identity = {p: p for p in range(1, n + 1)}
    labels = _pdf_page_labels(pdf) if pdf is not None else None
    if labels and len(labels) == n:
        arabic = {p: int(l) for p, l in enumerate(labels, 1) if _FOLIO_RE.match(l) and int(l) > 0}
        if len(arabic) >= FOLIO_MIN_SHARE * n:
            mapping = {p: arabic.get(p, 0) for p in range(1, n + 1)}
            return PAGES_PRINTED_LABELS, mapping, {"source": "/PageLabels"}
    with_text = [p for p, t in enumerate(layout_pages, 1) if t.strip()]
    votes: dict[int, int] = {}
    for p in with_text:
        for off in _folio_offsets(layout_pages[p - 1], p):
            votes[off] = votes.get(off, 0) + 1
    if votes:
        off, count = max(votes.items(), key=lambda kv: (kv[1], -abs(kv[0])))
        if count >= max(2, FOLIO_MIN_SHARE * len(with_text)):
            mapping = {p: (p + off if p + off > 0 else 0) for p in range(1, n + 1)}
            return PAGES_PRINTED_FOLIO, mapping, {"offset": off, "pages_with_folio": count}
    return PAGES_PDF, identity, {}


def number_pages(ext: Extraction, layout_pages: list[str], pdf: Optional[Path]) -> str:
    """Give every block its printed page (detect_page_numbering) and set the
    extraction's page kind and range. Runs last: the integrity report and
    the figure file names keep the PDF page. For a document that is part of
    the file (ext.pdf_range), `layout_pages` holds the text of its pages only
    (the others empty), so the folio is the one its own pages carry (an
    issue of four contributions, each with the pages of its journal); the
    page labels are the file's. Its range is that of its own pages, printed
    as in the volume."""
    kind, mapping, detail = detect_page_numbering(layout_pages, pdf)
    if ext.pdf_range:
        first, last = ext.pdf_range
        mapping = {p: v for p, v in mapping.items() if first <= p <= last}
    for b in ext.blocks:
        if b.page:
            b.pdf_page = b.page
            b.page = mapping.get(b.page, b.page)
    printed = [v for v in mapping.values() if v > 0]
    ext.page_kind = kind
    ext.page_first = min(printed) if printed else 0
    ext.page_last = max(printed) if printed else 0
    unnumbered = sorted(p for p, v in mapping.items() if v == 0)
    ext.page_detail = dict(detail, **({"unnumbered_pdf_pages": unnumbered} if unnumbered else {}))
    return kind


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path) -> str:
    """The paragraphs of a DOCX body (table cells included), one per line:
    the text Docling's DOCX reading is checked against, and the text the
    upload gate scans. `path` is a file path or a binary file object."""
    import xml.etree.ElementTree as ET
    import zipfile
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    lines: list[str] = []
    for p in root.iter(_W_NS + "p"):
        parts: list[str] = []
        for node in p.iter():
            if node.tag == _W_NS + "t":
                parts.append(node.text or "")
            elif node.tag in (_W_NS + "tab", _W_NS + "br"):
                parts.append(" ")
        text = "".join(parts).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def extract_with_integrity(blocks_json: Path, source: Optional[Path],
                           page_range: Optional[tuple[int, int]] = None) -> Extraction:
    """Load Docling's blocks, normalise them, and check them against the source.

    A PDF: cross-check against the text layer, compound hyphens, reading order
    within each page, page order, printed page numbers. A DOCX: cross-check
    against the document's own paragraphs; it has no pages, and the library
    file refers to its sections.

    `page_range` (first, last PDF page) makes the document the part of the
    file on those pages (restrict_to_pages): the checks read the text layer
    of the range only, and the page references are printed pages of the
    volume. A DOCX takes no range (ValueError).
    """
    ext = load_blocks(blocks_json)
    if page_range:
        if source is not None and Path(source).suffix.lower() == ".docx":
            raise ValueError("a page range needs a paged source (PDF), not a DOCX")
        restrict_to_pages(ext, page_range)
    if source is not None and Path(source).exists():
        ext.source_file = Path(source)
    normalise(ext)
    screen_figures(ext)
    if source is not None and Path(source).suffix.lower() == ".docx" and Path(source).exists():
        ext.pages = 0
        ext.page_kind = PAGES_NONE
        ext.page_first = ext.page_last = 0
        for b in ext.blocks:
            b.page = 0
        cross_check(ext, [docx_text(Path(source))], paged=False)
        return ext
    if source is not None and Path(source).exists():
        pages = _range_only(pdftotext_pages(Path(source)), ext.pdf_range)
        cross_check(ext, pages)
        restore_compound_hyphens(ext, pages)
        flow = _range_only(pdftotext_flow_pages(Path(source)), ext.pdf_range)
        ext.text_layer = {p: t for p, t in enumerate(flow, 1) if t.strip()}
        check_reading_order(ext, pages, flow)
        restore_page_order(ext)
        number_pages(ext, pages, Path(source))
    else:
        ext.integrity.reason = "no PDF to check against"
    return ext
