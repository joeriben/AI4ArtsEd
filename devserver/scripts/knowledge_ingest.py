#!/usr/bin/env python3
"""
Knowledge-library ingest (Tier F/O, offline) — PDF -> RAW Markdown (Docling).

Since the Verdichtungs-Umbau (BIBLIOTHEK.md §3, 2026-07-04) this script does ONE
thing: convert a source PDF into a *raw* Docling Markdown. It no longer produces
the committed knowledge file — that is the job of the in-process
`my_app/services/knowledge_processing.py` (Verdichtung), which runs in the
devserver where the LLM provider routing lives.

    ┌─ what this writes ──────────────────────────────────────────────────┐
    │ resources/knowledge_originals/<subdir>/<doc_id>.raw.md              │
    │   the raw Docling conversion, NOT committed (gitignored), a          │
    │   re-processing intermediate — never the library form.              │
    └──────────────────────────────────────────────────────────────────────┘

The compact library file (front-matter + ## PROFIL + ## WISSEN + ## GLOSSAR)
is produced downstream by knowledge_processing.process_document(). This split
keeps Docling (+torch) OUT of the devserver runtime — it lives in a separate
venv and is only invoked here.

────────────────────────────────────────────────────────────────────────────
VENV (one-time, on the GPU host):

    python3 -m venv ~/ai/venvs/knowledge
    ~/ai/venvs/knowledge/bin/pip install -r \
        devserver/scripts/requirements_knowledge.txt

USAGE:

    # PDF -> raw Markdown next to the PDF (default raw-out path derived from --doc-id):
    ~/ai/venvs/knowledge/bin/python devserver/scripts/knowledge_ingest.py \
        resources/knowledge_originals/unesco/unesco-seoul-agenda-arts-education-2010.pdf \
        --doc-id unesco-seoul-agenda-...-2010

    # explicit output path:
    ...same... --raw-out /path/to/out.raw.md

    # pass an already-Markdown source through unchanged (no Docling/torch):
    ...  --md some_input.md --raw-out /path/to/out.raw.md

The downstream Verdichtung reads the raw Markdown + the operator metadata and
writes the compact library file itself.
────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="[knowledge-ingest] %(levelname)s %(message)s")
logger = logging.getLogger("knowledge_ingest")

# devserver/scripts/knowledge_ingest.py -> parents[1] == devserver/
DEVSERVER_DIR = Path(__file__).resolve().parents[1]
# The originals directory is config.py's (stdlib-only, so the knowledge venv
# can read it): resources/knowledge_originals/ at the repo root.
sys.path.insert(0, str(DEVSERVER_DIR))
from config import KNOWLEDGE_ORIGINALS_DIR as ORIGINALS_DIR  # noqa: E402


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

def pdf_to_markdown(pdf_path: Path) -> str:
    """Convert a PDF to structured Markdown using Docling.

    Docling is imported lazily so the --md passthrough path (and tests) never
    require torch.
    """
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except ImportError as e:  # pragma: no cover - env-dependent
        raise SystemExit(
            "Docling is not installed in this environment. Create the ingest venv:\n"
            "  python3 -m venv ~/ai/venvs/knowledge\n"
            "  ~/ai/venvs/knowledge/bin/pip install -r "
            "devserver/scripts/requirements_knowledge.txt\n"
            f"(import error: {e})"
        )
    logger.info("Converting %s with Docling (this can take a while)…", pdf_path.name)
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    return result.document.export_to_markdown()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _default_raw_out(doc_id: str, subdir: str) -> Path:
    """Default raw-MD path: resources/knowledge_originals/<subdir>/<doc_id>.raw.md
    (mirrors where the source PDF lives)."""
    return ORIGINALS_DIR / subdir / f"{doc_id}.raw.md"


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
            raise SystemExit("Provide a PDF path or --md <markdown file>.")
        pdf_path = Path(args.pdf).resolve()
        if not pdf_path.exists():
            raise SystemExit(f"PDF not found: {pdf_path}")
        raw_md = pdf_to_markdown(pdf_path)
        source = pdf_path

    doc_id = kebab_slug(args.doc_id) if args.doc_id else kebab_slug(source.stem)

    if args.raw_out:
        out_path = Path(args.raw_out).resolve()
    else:
        out_path = _default_raw_out(doc_id, args.subdir or "unesco")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(raw_md, encoding="utf-8")
    logger.info("Wrote raw Markdown %s (%d chars)", out_path, len(raw_md))
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert a source PDF into raw Docling Markdown "
                    "(the Verdichtung downstream produces the library file).")
    p.add_argument("pdf", nargs="?", help="Path to the source PDF (omit with --md)")
    p.add_argument("--md", metavar="MD_PATH",
                   help="Pass an already-Markdown source through unchanged, WITHOUT "
                        "Docling/torch (for Tier-O uploads that are already Markdown).")
    p.add_argument("--doc-id", help="Document id (else derived kebab-slug from the "
                                    "source filename); names the raw-MD output.")
    p.add_argument("--raw-out", metavar="PATH",
                   help="Explicit output path for the raw Markdown (default: "
                        "resources/knowledge_originals/<subdir>/<doc_id>.raw.md).")
    p.add_argument("--subdir", default="unesco",
                   help="Sub-folder under resources/knowledge_originals/ for the "
                        "default raw-out path (default: unesco).")
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.pdf and not args.md:
        raise SystemExit("A PDF path or --md MD_PATH is required.")
    out = to_raw_markdown(args)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
