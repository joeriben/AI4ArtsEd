#!/usr/bin/env python3
"""
Knowledge-library ingest (Tier F/O, offline) — PDF -> blocks, figures, raw Markdown.

This script runs Docling in its own venv (Docling and torch are never a
devserver dependency) and writes the extraction the processing stage reads.
It does not write the library file: that is
`my_app/services/knowledge_processing.py`, which runs in the devserver where
the LLM provider routing lives.

    ┌─ what this writes, all beside --raw-out ────────────────────────────┐
    │ <doc_id>.blocks.json  ordered blocks with PDF page number and kind  │
    │                       (heading+level, paragraph, list item, table,  │
    │                       figure with caption and image file, ...)      │
    │ <doc_id>.figures/     every figure as PNG (named in blocks.json)    │
    │ <doc_id>.raw.md       Docling's Markdown export (hashing, scenes)   │
    └──────────────────────────────────────────────────────────────────────┘

`my_app/services/knowledge_extract.py` reads blocks.json, checks it page by
page against `pdftotext -layout`, and repairs what Docling lost. The default
location is the work root outside the repository (config.KNOWLEDGE_WORK_ROOT,
<root>/<subdir>/); the upload service passes --raw-out under
resources/knowledge_originals/operator/. All three are intermediates that
scripts/knowledge_retention.py lists and removes for non-CC documents.

────────────────────────────────────────────────────────────────────────────
VENV (one-time, on the GPU host):

    python3 -m venv ~/ai/venvs/knowledge
    ~/ai/venvs/knowledge/bin/pip install -r \
        devserver/scripts/requirements_knowledge.txt

USAGE:

    # PDF -> blocks, figures and raw Markdown in the work root:
    ~/ai/venvs/knowledge/bin/python devserver/scripts/knowledge_ingest.py \
        ~/ai4artsed_knowledge_db/unesco/<doc_id>.pdf --doc-id <doc_id>

    # explicit output path (blocks.json and figures/ go beside it):
    ...same... --raw-out /path/to/<doc_id>.raw.md

    # pass an already-Markdown source through unchanged (no Docling/torch):
    ...  --md some_input.md --raw-out /path/to/out.raw.md
────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="[knowledge-ingest] %(levelname)s %(message)s")
logger = logging.getLogger("knowledge_ingest")

# devserver/scripts/knowledge_ingest.py -> parents[1] == devserver/
DEVSERVER_DIR = Path(__file__).resolve().parents[1]
# The work root is config.py's (stdlib-only, so the knowledge venv can read
# it): outside the repository, config.KNOWLEDGE_WORK_ROOT.
sys.path.insert(0, str(DEVSERVER_DIR))
from config import KNOWLEDGE_WORK_ROOT  # noqa: E402


# ---------------------------------------------------------------------------
# Slug / id
# ---------------------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def kebab_slug(text: str) -> str:
    s = _SLUG_STRIP.sub("-", (text or "").lower()).strip("-")
    return s or "document"


# ---------------------------------------------------------------------------
# Docling conversion
# ---------------------------------------------------------------------------

_FIGURE_NO_RE = re.compile(
    r"\b(?:Abb(?:ildung)?|Fig(?:ure)?|Grafik|Bild|Tab(?:elle)?)\.?\s*(\d+[a-z]?)",
    re.IGNORECASE)


def _convert(pdf_path: Path):
    """Run Docling on a PDF (figure export switched on) or a DOCX (Docling's
    own Word reader: no pages, embedded images as figures). Returns the
    DoclingDocument. Docling is imported lazily so the --md passthrough path
    (and tests) never require torch."""
    try:
        from docling.datamodel.base_models import InputFormat  # type: ignore
        from docling.datamodel.pipeline_options import PdfPipelineOptions  # type: ignore
        from docling.document_converter import DocumentConverter, PdfFormatOption  # type: ignore
    except ImportError as e:  # pragma: no cover - env-dependent
        raise SystemExit(
            "Docling is not installed in this environment. Create the ingest venv:\n"
            "  python3 -m venv ~/ai/venvs/knowledge\n"
            "  ~/ai/venvs/knowledge/bin/pip install -r "
            "devserver/scripts/requirements_knowledge.txt\n"
            f"(import error: {e})"
        )
    opts = PdfPipelineOptions()
    opts.generate_picture_images = True
    opts.images_scale = 2.0
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    logger.info("Converting %s with Docling (this can take a while)…", pdf_path.name)
    return converter.convert(str(pdf_path)).document


# The source formats Docling reads here; extract_with_integrity checks a DOCX
# against its own paragraphs (knowledge_extract.docx_text), a PDF against
# its text layer.
SOURCE_SUFFIXES = (".pdf", ".docx")


def _page_of(item) -> Optional[int]:
    prov = getattr(item, "prov", None) or []
    return int(prov[0].page_no) if prov else None


def _text_of(item, doc) -> str:
    from docling_core.types.doc import TableItem  # type: ignore
    if isinstance(item, TableItem):
        return item.export_to_markdown(doc)
    return (getattr(item, "text", "") or "").strip()


# A DOCX heading set by hand: a paragraph wholly in bold, short, not ending
# like a sentence. Its level follows the numbering ("2.1 …" is level 2).
_BOLD_HEADING_MAX_WORDS = 20
_HEADING_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")
_NO_SPACE_BEFORE_RE = re.compile(r"^[.,;:!?)\]»“”’]")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _manual_heading_level(item, text: str) -> int:
    """The level of a paragraph a DOCX author made a heading by setting it in
    bold (Docling's Word reader reports the run formatting, its PDF reader
    does not), or 0 when it is not one."""
    fmt = getattr(item, "formatting", None)
    if fmt is None or not getattr(fmt, "bold", False):
        return 0
    if not text or "\n" in text.strip() or len(text.split()) > _BOLD_HEADING_MAX_WORDS:
        return 0
    if text.rstrip()[-1:] in ".;,":
        return 0
    m = _HEADING_NUMBER_RE.match(text)
    return len(m.group(1).split(".")) if m else 1


def _author_lines_out_of_headings(blocks: list, bold_rule: set) -> None:
    """A heading that holds an e-mail address is an author's affiliation,
    and a heading the bold rule made that stands right before such a line
    is the author's name: both become paragraphs. In "Generative AI and the
    Politics of Perception" (DOCX) the names "Benjamin Jörissen" and
    "Vanessa Baumann" are bold paragraphs and the first affiliation carries
    Word's Heading 2 style; without this they head sections of their own."""
    body = [b for b in blocks if b.get("kind") not in ("furniture", "figure_text")]
    for k, b in enumerate(body):
        if b.get("kind") != "heading":
            continue
        nxt = body[k + 1].get("text", "") if k + 1 < len(body) else ""
        if _EMAIL_RE.search(b.get("text", "")) or (id(b) in bold_rule and _EMAIL_RE.search(nxt)):
            b["kind"] = "paragraph"
            b.pop("level", None)


def _join_inline(parts: list) -> str:
    """The pieces of one paragraph that Docling's Word reader splits at every
    change of run formatting, joined back: a space between pieces, none
    before closing punctuation or after an opening bracket."""
    out = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if out and not _NO_SPACE_BEFORE_RE.match(part) and out[-1:] not in "([„“‘«":
            out += " "
        out += part
    return out


def document_to_blocks(doc, figures_dir: Optional[Path]) -> dict:
    """Walk a DoclingDocument in reading order and return the block export
    that knowledge_extract.py reads: every body item with its PDF page number
    and kind, figures with caption and an exported image file, and -- for the
    cross-check against pdftotext only -- the furniture (running heads, page
    footers) and the text Docling found INSIDE a picture.

    Block kinds: title, heading (with level), paragraph, list_item (with the
    id of its list and its marker), table (Markdown), figure (caption, image,
    figure_no), caption, footnote, code, formula, furniture, figure_text.

    DOCX: the pieces of an inline group (one Word paragraph, split by Docling
    at every change of run formatting) become one paragraph; a paragraph set
    wholly in bold (_manual_heading_level) becomes a heading, unless it is an
    author line (_author_lines_out_of_headings).
    """
    from docling_core.types.doc import (  # type: ignore
        ContentLayer, DocItemLabel, GroupLabel, ListItem, PictureItem, SectionHeaderItem,
    )

    blocks: list = []
    bold_rule: set = set()     # id() of the headings _manual_heading_level made
    inline: dict = {}          # inline group ref -> (block, parts)
    caption_refs: set = set()
    fig_count = 0
    if figures_dir is not None:
        figures_dir.mkdir(parents=True, exist_ok=True)

    layers = {ContentLayer.BODY, ContentLayer.FURNITURE}
    for item, _lvl in doc.iterate_items(with_groups=False, traverse_pictures=True,
                                        included_content_layers=layers):
        label = getattr(item, "label", None)
        page = _page_of(item)
        ref = item.self_ref
        in_picture = None
        parent = item.parent.resolve(doc) if getattr(item, "parent", None) else None
        while parent is not None:
            if isinstance(parent, PictureItem):
                in_picture = parent.self_ref
                break
            parent = parent.parent.resolve(doc) if getattr(parent, "parent", None) else None

        block = {"page": page, "ref": ref}
        group = item.parent.resolve(doc) if getattr(item, "parent", None) else None
        if (in_picture is None and group is not None
                and getattr(group, "label", None) == GroupLabel.INLINE
                and getattr(item, "content_layer", ContentLayer.BODY) == ContentLayer.BODY
                and label not in (DocItemLabel.CAPTION,)
                and not isinstance(item, (PictureItem, ListItem, SectionHeaderItem))
                and label != DocItemLabel.TABLE):
            gref = group.self_ref
            if gref not in inline:
                block.update(kind="paragraph", ref=gref, text="")
                inline[gref] = (block, [])
                blocks.append(block)
            held, parts = inline[gref]
            parts.append(_text_of(item, doc))
            held["text"] = _join_inline(parts)
            if held.get("page") is None:
                held["page"] = page
            continue
        if getattr(item, "content_layer", ContentLayer.BODY) != ContentLayer.BODY:
            block.update(kind="furniture", text=_text_of(item, doc))
        elif in_picture is not None and not isinstance(item, PictureItem):
            if ref in caption_refs:
                continue
            block.update(kind="figure_text", text=_text_of(item, doc), figure_ref=in_picture)
        elif isinstance(item, PictureItem):
            fig_count += 1
            caption = item.caption_text(doc).strip()
            for c in item.captions:
                caption_refs.add(c.cref)
            m = _FIGURE_NO_RE.search(caption)
            image_name = ""
            if figures_dir is not None:
                img = item.get_image(doc)
                if img is not None:
                    image_name = f"fig-{fig_count:03d}-p{page or 0}.png"
                    img.save(figures_dir / image_name)
            block.update(kind="figure", text="", caption=caption,
                         figure_no=m.group(1) if m else "", image=image_name,
                         seq=fig_count)
        elif ref in caption_refs:
            continue  # already carried by its figure/table
        elif isinstance(item, SectionHeaderItem):
            block.update(kind="heading", level=int(item.level or 1), text=_text_of(item, doc))
        elif label == DocItemLabel.TITLE:
            block.update(kind="title", level=0, text=_text_of(item, doc))
        elif isinstance(item, ListItem):
            block.update(kind="list_item", text=_text_of(item, doc),
                         list_id=item.parent.cref if item.parent else "",
                         enumerated=bool(getattr(item, "enumerated", False)),
                         marker=str(getattr(item, "marker", "") or ""))
        elif label == DocItemLabel.TABLE:
            caption = item.caption_text(doc).strip()
            for c in item.captions:
                caption_refs.add(c.cref)
            block.update(kind="table", text=_text_of(item, doc), caption=caption)
        elif label == DocItemLabel.CAPTION:
            block.update(kind="caption", text=_text_of(item, doc))
        elif label == DocItemLabel.FOOTNOTE:
            block.update(kind="footnote", text=_text_of(item, doc))
        elif label in (DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER):
            block.update(kind="furniture", text=_text_of(item, doc))
        elif label == DocItemLabel.CODE:
            block.update(kind="code", text=_text_of(item, doc))
        elif label == DocItemLabel.FORMULA:
            block.update(kind="formula", text=_text_of(item, doc))
        else:
            text = _text_of(item, doc)
            level = _manual_heading_level(item, text)
            if level:
                block.update(kind="heading", level=level, text=text)
                bold_rule.add(id(block))
            else:
                block.update(kind="paragraph", text=text)
        if block.get("kind") != "figure" and not block.get("text"):
            continue
        blocks.append(block)
    blocks = [b for b in blocks if b.get("kind") == "figure" or b.get("text")]
    _author_lines_out_of_headings(blocks, bold_rule)

    return {
        "source": "docling",
        "pages": len(doc.pages),       # 0 for a DOCX: no page in the item provenance
        "figures_dir": figures_dir.name if figures_dir is not None else "",
        "blocks": blocks,
    }


def pdf_to_markdown(pdf_path: Path) -> str:
    """Convert a PDF to structured Markdown using Docling (kept for callers
    that only want the raw Markdown)."""
    return _convert(pdf_path).export_to_markdown()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _default_raw_out(doc_id: str, subdir: str) -> Path:
    """Default raw-MD path: <KNOWLEDGE_WORK_ROOT>/<subdir>/<doc_id>.raw.md
    (the tier folder mirrors the source root's layout)."""
    return Path(KNOWLEDGE_WORK_ROOT) / subdir / f"{doc_id}.raw.md"


def to_raw_markdown(args: argparse.Namespace) -> Path:
    # Source: PDF (Docling) or an already-Markdown file (--md, passthrough).
    if args.md:
        md_path = Path(args.md).resolve()
        if not md_path.exists():
            raise SystemExit(f"Markdown not found: {md_path}")
        raw_md = md_path.read_text(encoding="utf-8")
        source = md_path
    else:
        if not args.pdf:
            raise SystemExit("Provide a PDF or DOCX path or --md <markdown file>.")
        pdf_path = Path(args.pdf).resolve()
        if not pdf_path.exists():
            raise SystemExit(f"Source not found: {pdf_path}")
        if pdf_path.suffix.lower() not in SOURCE_SUFFIXES:
            raise SystemExit(f"Not a PDF or DOCX: {pdf_path}")
        source = pdf_path

    doc_id = kebab_slug(args.doc_id) if args.doc_id else kebab_slug(source.stem)

    if args.raw_out:
        out_path = Path(args.raw_out).resolve()
    else:
        out_path = _default_raw_out(doc_id, args.subdir or "unesco")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.md:
        # PDF or DOCX: the block export (pages, kinds, figures) is what the
        # Verdichtung reads; the raw Markdown stays beside it for the intake
        # check of the scene path and for hashing.
        doc = _convert(source)
        raw_md = doc.export_to_markdown()
        # blocks.json names its figures folder relative to itself, so both
        # always sit beside the raw Markdown.
        blocks_out = out_path.with_name(doc_id + ".blocks.json")
        figures_dir = out_path.with_name(doc_id + ".figures")
        export = document_to_blocks(doc, figures_dir)
        blocks_out.write_text(json.dumps(export, ensure_ascii=False, indent=1),
                              encoding="utf-8")
        logger.info("Wrote %d blocks to %s, figures to %s",
                    len(export["blocks"]), blocks_out, figures_dir)

    out_path.write_text(raw_md, encoding="utf-8")
    logger.info("Wrote raw Markdown %s (%d chars)", out_path, len(raw_md))
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert a source PDF into blocks, figures and raw Docling "
                    "Markdown (the processing stage downstream writes the "
                    "library file).")
    p.add_argument("pdf", nargs="?", help="Path to the source PDF or DOCX (omit with --md)")
    p.add_argument("--md", metavar="MD_PATH",
                   help="Pass an already-Markdown source through unchanged, WITHOUT "
                        "Docling/torch (for Tier-O uploads that are already Markdown).")
    p.add_argument("--doc-id", help="Document id (else derived kebab-slug from the "
                                    "source filename); names the raw-MD output.")
    p.add_argument("--raw-out", metavar="PATH",
                   help="Explicit output path for the raw Markdown; "
                        "<doc_id>.blocks.json and <doc_id>.figures/ go beside it "
                        "(default: <KNOWLEDGE_WORK_ROOT>/<subdir>/<doc_id>.raw.md).")
    p.add_argument("--subdir", default="unesco",
                   help="Tier folder under KNOWLEDGE_WORK_ROOT for the default "
                        "raw-out path (default: unesco).")
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.pdf and not args.md:
        raise SystemExit("A PDF or DOCX path or --md MD_PATH is required.")
    out = to_raw_markdown(args)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
