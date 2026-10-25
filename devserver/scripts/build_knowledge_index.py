#!/usr/bin/env python3
"""
Build the knowledge-library search index (Stufe 1, FTS5/BM25).

Deterministic, idempotent rebuild (DROP + CREATE) from the committed Markdown
under devserver/my_app/knowledge/library/** (and, when present, the Tier-O
exports under exports/knowledge_library/**) into

    exports/knowledge_index.sqlite   (gitignored, rebuildable)

Schema (BIBLIOTHEK.md §5 + build brief):
    docs(doc_id PK, title, authors, year, lang, tier, sparten_json, themen_json,
         lizenz, url, status, owner_key, card_md, source_path, bereich, hinweis,
         analyzed_at, analysis_lang, analysis_model)
    chunks(chunk_id PK, doc_id, section_path, heading, context_txt, body_md,
           tokens_est)
    glossary(term, definition, doc_refs_json, curated)
plus FTS5 external-content virtual tables over cards (card_md), chunks
(heading + context + body), and glossary (term + definition). curated glossary
overrides from exports/json/knowledge_glossary_overrides.json are merged last.

This script is stdlib-only (sqlite3 + FTS5, both in the system SQLite). It reads
the COMPACT Markdown format the Verdichtung (knowledge_processing.py) writes:
    --- front-matter ---
    # Title
    ## PROFIL   (the positioning digest — indexed as the "card")
    ## WISSEN   (### <Abschnitt de> subsections = the condensed knowledge units;
                 each ends in a <!-- quelle: … --> review anchor, stripped here)
    ## GLOSSAR  (- **term** — definition)
Full source text is NEVER present in the library, so it is never indexed and
never reaches the model (BIBLIOTHEK.md §3 core rule).

USAGE:
    python3 devserver/scripts/build_knowledge_index.py
    python3 devserver/scripts/build_knowledge_index.py --db /tmp/other.sqlite \
        --library /path/to/library --owner-scan  # (Tier-O later)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="[knowledge-index] %(levelname)s %(message)s")
logger = logging.getLogger("build_knowledge_index")

# devserver/scripts/build_knowledge_index.py -> parents[1] == devserver/
DEVSERVER_DIR = Path(__file__).resolve().parents[1]
# The defaults are config.py's (stdlib-only, like this script).
sys.path.insert(0, str(DEVSERVER_DIR))
from config import (  # noqa: E402
    KNOWLEDGE_GLOSSARY_OVERRIDES, KNOWLEDGE_INDEX_DB, KNOWLEDGE_LIBRARY_DIR,
    KNOWLEDGE_TIER_O_DIR,
)

DEFAULT_LIBRARY = KNOWLEDGE_LIBRARY_DIR
DEFAULT_TIER_O = KNOWLEDGE_TIER_O_DIR
DEFAULT_DB = KNOWLEDGE_INDEX_DB
GLOSSARY_OVERRIDES = KNOWLEDGE_GLOSSARY_OVERRIDES

_CHARS_PER_TOKEN = 4


def _est_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# Markdown parsing (mirror of knowledge_processing.assemble_markdown)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
# HTML comments (e.g. the WISSEN "<!-- quelle: … -->" review anchors) are review
# aids only and must not enter the indexed text.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# Glossary line: "- **term** — definition" (the compact form has no anchor; the
# optional "_(→ anchor)_" tail is still tolerated for older files).
_GLOSS_LINE_RE = re.compile(r"^-\s+\*\*(.+?)\*\*\s+—\s+(.*?)(?:\s+_\(→\s*(.*?)\s*\)_)?\s*$")


def _parse_front_matter(md: str) -> Tuple[Dict[str, Any], str]:
    """Parse the simple YAML subset knowledge_ingest.py emits (scalars, JSON-quoted
    scalars, and `key: [a, b]` lists). Returns (front_matter, rest_of_markdown)."""
    m = _FM_RE.match(md)
    if not m:
        return {}, md
    block = m.group(1)
    fm: Dict[str, Any] = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            items: List[str] = []
            if inner:
                for part in _split_list(inner):
                    items.append(_unquote(part.strip()))
            fm[key] = items
        else:
            fm[key] = _unquote(raw)
    return fm, md[m.end():]


def _split_list(inner: str) -> List[str]:
    """Split a `a, "b, c", d` list honoring JSON-quoted items."""
    out, buf, in_str, esc = [], [], False, False
    for ch in inner:
        if esc:
            buf.append(ch); esc = False; continue
        if ch == "\\" and in_str:
            buf.append(ch); esc = True; continue
        if ch == '"':
            in_str = not in_str; buf.append(ch); continue
        if ch == "," and not in_str:
            out.append("".join(buf)); buf = []; continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s[1:-1]
    return s


# The three level-2 markers the compact Verdichtung form emits. Only these start
# a new top section — a WISSEN body legitimately carries its own ### subsection
# headings, which are handled by _parse_wissen_chunks, NOT as top boundaries.
_TOP_SECTION_KEYS = {"PROFIL", "WISSEN", "GLOSSAR"}


def _split_top_sections(md: str) -> Dict[str, str]:
    """Split the post-front-matter markdown into the known top sections keyed by
    UPPERCASED heading (PROFIL / WISSEN / GLOSSAR). A `## X` heading is a
    boundary ONLY when X is one of those keys; every other heading (the # Title
    and the WISSEN ### subsection headings) stays inside the current section."""
    sections: Dict[str, str] = {}
    cur_key: Optional[str] = None
    cur: List[str] = []
    for line in md.splitlines():
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) == 2 and m.group(2).strip().upper() in _TOP_SECTION_KEYS:
            if cur_key is not None:
                sections[cur_key] = "\n".join(cur).strip()
            cur_key = m.group(2).strip().upper()
            cur = []
        elif cur_key is not None:
            cur.append(line)
    if cur_key is not None:
        sections[cur_key] = "\n".join(cur).strip()
    return sections


def _strip_html_comments(text: str) -> str:
    """Remove HTML comments (the WISSEN quelle-anchors) from indexed text."""
    return _HTML_COMMENT_RE.sub("", text)


def _parse_glossary(gloss_md: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for line in gloss_md.splitlines():
        m = _GLOSS_LINE_RE.match(line.strip())
        if m:
            out.append({
                "term": m.group(1).strip(),
                "definition": (m.group(2) or "").strip(),
                "anchor": (m.group(3) or "").strip(),
            })
    return out


def _parse_wissen_chunks(wissen_md: str) -> List[Dict[str, Any]]:
    """One chunk per `### <Abschnitt>` subsection of the ## WISSEN section. The
    subsection heading is the chunk heading + section_path; the body is the
    condensed text with its <!-- quelle: … --> anchor (and any other HTML
    comment) stripped. No context_txt in the compact form (kept empty for the
    unchanged schema/FTS shape). Any text before the first ### (there normally is
    none) becomes a 'WISSEN' preamble chunk so nothing is silently dropped."""
    chunks: List[Dict[str, Any]] = []
    heading = "WISSEN"
    buf: List[str] = []

    def _flush():
        body = _strip_html_comments("\n".join(buf)).strip()
        if body:
            chunks.append({
                "section_path": heading,
                "heading": heading,
                "context_txt": "",
                "body_md": body,
                "tokens_est": _est_tokens(body),
            })
        buf.clear()

    for line in wissen_md.splitlines():
        hm = _HEADING_RE.match(line)
        if hm and len(hm.group(1)) == 3:  # a ### subsection = a new chunk
            _flush()
            heading = hm.group(2).strip()
        else:
            buf.append(line)
    _flush()
    return chunks
    return chunks


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def load_document(md_path: Path, owner_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    md = md_path.read_text(encoding="utf-8")
    fm, rest = _parse_front_matter(md)
    doc_id = fm.get("id") or md_path.stem
    if not fm.get("lizenz"):
        # Policy: a document without a license is not indexed (ingest already
        # refuses to write one, but a hand-edited file could slip through).
        logger.warning("SKIP %s: no 'lizenz' in front-matter (policy).", md_path.name)
        return None

    sections = _split_top_sections(rest)
    # PROFIL is indexed as the "card" (kept in the docs.card_md column for the
    # unchanged search-menu shape). WISSEN subsections become the chunks.
    card_md = _strip_html_comments(sections.get("PROFIL", "")).strip()
    glossary = _parse_glossary(sections.get("GLOSSAR", ""))
    chunks = _parse_wissen_chunks(sections.get("WISSEN", ""))

    return {
        "doc_id": doc_id,
        "title": fm.get("titel", doc_id),
        "authors": fm.get("autor", ""),
        "year": fm.get("jahr", ""),
        "lang": fm.get("sprache", ""),
        "tier": fm.get("tier", ""),
        "sparten": fm.get("sparten", []) if isinstance(fm.get("sparten"), list) else [],
        "themen": fm.get("themen", []) if isinstance(fm.get("themen"), list) else [],
        "lizenz": fm.get("lizenz", ""),
        "url": fm.get("url", ""),
        "status": fm.get("status", "published"),
        "owner_key": owner_key,
        # bereich = operator area id (a facet, like sparten/themen); hinweis =
        # the operator's per-document note ("why this was uploaded"). Both are
        # metadata carried in the docs row for the curation UI and (bereich) the
        # facet filter — they are DELIBERATELY not added to any FTS table (a note
        # must never surface as a search hit).
        "bereich": fm.get("bereich", ""),
        "hinweis": fm.get("hinweis", ""),
        # Analysis provenance (additive, 2026-07-10): absent ("") on any
        # document produced before this feature -- never guessed/backfilled.
        # analysis_lang is the TARGET language the analysis was WRITTEN in;
        # `lang` above (front-matter `sprache`) is the document's own detected
        # SOURCE language -- the two are never the same field.
        "analyzed_at": fm.get("analyzed_at", ""),
        "analysis_lang": fm.get("analysis_lang", ""),
        "analysis_model": fm.get("analysis_model", ""),
        "card_md": card_md,
        "source_path": str(md_path),
        "glossary": glossary,
        "chunks": chunks,
    }


def scan_library(library_dir: Path, tier_o_dir: Optional[Path]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    if library_dir.exists():
        for md_path in sorted(library_dir.rglob("*.md")):
            if md_path.name.upper() in ("ATTRIBUTION.MD",):
                continue
            if md_path.name.endswith(".raw.md"):
                continue  # raw Docling intermediate, never the library form
            d = load_document(md_path)
            if d:
                docs.append(d)
    else:
        logger.warning("Library dir not found: %s", library_dir)
    # Tier O (exports/knowledge_library/) — present only on operator installs.
    if tier_o_dir and tier_o_dir.exists():
        for md_path in sorted(tier_o_dir.rglob("*.md")):
            if md_path.name.endswith(".raw.md"):
                continue
            d = load_document(md_path)
            if d:
                docs.append(d)
    return docs


# ---------------------------------------------------------------------------
# SQLite schema + population
# ---------------------------------------------------------------------------

SCHEMA = """
DROP TABLE IF EXISTS docs;
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS glossary;
DROP TABLE IF EXISTS docs_fts;
DROP TABLE IF EXISTS chunks_fts;
DROP TABLE IF EXISTS glossary_fts;

CREATE TABLE docs (
    doc_id       TEXT PRIMARY KEY,
    title        TEXT,
    authors      TEXT,
    year         TEXT,
    lang         TEXT,
    tier         TEXT,
    sparten_json TEXT,
    themen_json  TEXT,
    lizenz       TEXT,
    url          TEXT,
    status       TEXT,
    owner_key    TEXT,
    card_md      TEXT,
    source_path  TEXT,
    bereich      TEXT,
    hinweis      TEXT,
    analyzed_at    TEXT,
    analysis_lang  TEXT,
    analysis_model TEXT
);

CREATE TABLE chunks (
    chunk_id     INTEGER PRIMARY KEY,
    doc_id       TEXT NOT NULL,
    section_path TEXT,
    heading      TEXT,
    context_txt  TEXT,
    body_md      TEXT,
    tokens_est   INTEGER
);
CREATE INDEX idx_chunks_doc ON chunks(doc_id);

CREATE TABLE glossary (
    term          TEXT,
    definition    TEXT,
    doc_refs_json TEXT,
    curated       INTEGER DEFAULT 0
);
CREATE INDEX idx_glossary_term ON glossary(term);

-- FTS5 external-content tables (content= links back to the base row by rowid).
CREATE VIRTUAL TABLE docs_fts USING fts5(
    card_md, title,
    content='docs', content_rowid='rowid', tokenize='porter unicode61'
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    heading, context_txt, body_md,
    content='chunks', content_rowid='chunk_id', tokenize='porter unicode61'
);
CREATE VIRTUAL TABLE glossary_fts USING fts5(
    term, definition,
    content='glossary', content_rowid='rowid', tokenize='porter unicode61'
);
"""


def _iter_glossary_overrides(raw: Any):
    """Yield (term, spec_dict) pairs from a glossary-overrides JSON, accepting
    both the canonical dict-keyed shape and the legacy list shape (see build()).
    Malformed entries are skipped silently (the caller degrades, never crashes)."""
    if isinstance(raw, dict) and "terms" in raw and isinstance(raw["terms"], list):
        # legacy: {"terms": [ {"term": ..., "definition": ..., ...}, ... ]}
        for ov in raw["terms"]:
            if isinstance(ov, dict) and str(ov.get("term", "")).strip():
                yield ov["term"], ov
    elif isinstance(raw, dict):
        # canonical: { "<term>": {"definition": ..., "hidden": bool}, ... }
        for term, spec in raw.items():
            if isinstance(spec, dict):
                yield term, spec
            elif isinstance(spec, str):
                # shorthand: { "<term>": "definition" }
                yield term, {"definition": spec}


def build(db_path: Path, docs: List[Dict[str, Any]]) -> Dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()  # full rebuild — deterministic, no stale rows

    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(SCHEMA)

        # docs
        for d in docs:
            con.execute(
                "INSERT INTO docs (doc_id,title,authors,year,lang,tier,sparten_json,"
                "themen_json,lizenz,url,status,owner_key,card_md,source_path,bereich,hinweis,"
                "analyzed_at,analysis_lang,analysis_model) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    d["doc_id"], d["title"], d["authors"], str(d["year"]), d["lang"],
                    d["tier"], json.dumps(d["sparten"], ensure_ascii=False),
                    json.dumps(d["themen"], ensure_ascii=False), d["lizenz"], d["url"],
                    d["status"], d["owner_key"], d["card_md"], d["source_path"],
                    d.get("bereich", ""), d.get("hinweis", ""),
                    d.get("analyzed_at", ""), d.get("analysis_lang", ""),
                    d.get("analysis_model", ""),
                ),
            )

        # chunks (chunk_id is a stable running integer; order = doc order then
        # in-doc order, so a rebuild from identical inputs yields identical ids)
        chunk_id = 0
        chunk_rows: List[Tuple] = []
        for d in docs:
            for ch in d["chunks"]:
                chunk_id += 1
                chunk_rows.append((
                    chunk_id, d["doc_id"], ch["section_path"], ch["heading"],
                    ch["context_txt"], ch["body_md"], ch["tokens_est"],
                ))
        con.executemany(
            "INSERT INTO chunks (chunk_id,doc_id,section_path,heading,context_txt,"
            "body_md,tokens_est) VALUES (?,?,?,?,?,?,?)", chunk_rows,
        )

        # glossary — aggregate identical terms across docs (case-insensitive),
        # collecting doc refs; definition from the first occurrence.
        agg: Dict[str, Dict[str, Any]] = {}
        for d in docs:
            for g in d["glossary"]:
                key = g["term"].strip().lower()
                if not key:
                    continue
                entry = agg.setdefault(key, {"term": g["term"].strip(),
                                             "definition": g.get("definition", ""),
                                             "refs": []})
                if not entry["definition"] and g.get("definition"):
                    entry["definition"] = g["definition"]
                ref = {"doc_id": d["doc_id"], "anchor": g.get("anchor", "")}
                if ref not in entry["refs"]:
                    entry["refs"].append(ref)

        # curated overrides (operator redaction, BIBLIOTHEK.md §8) merged LAST,
        # marked curated=1. Two accepted shapes:
        #   (canonical) { "<term>": {"definition": "...", "hidden": false}, ... }
        #   (legacy)    { "terms": [ {"term": "...", "definition": "...",
        #                             "doc_refs": [...], "hidden": false}, ... ] }
        # hidden:true REMOVES the term from the index entirely (operator veto),
        # even when documents contributed it. A curated definition replaces the
        # aggregated one; refs default to whatever the docs contributed unless
        # the override provides doc_refs.
        curated_terms = set()
        if GLOSSARY_OVERRIDES.exists():
            try:
                raw = json.loads(GLOSSARY_OVERRIDES.read_text(encoding="utf-8"))
                for term, spec in _iter_glossary_overrides(raw):
                    term = str(term).strip()
                    if not term:
                        continue
                    key = term.lower()
                    if bool(spec.get("hidden", False)):
                        agg.pop(key, None)          # operator veto: drop the term
                        curated_terms.discard(key)
                        continue
                    curated_terms.add(key)
                    prev = agg.get(key, {})
                    definition = str(spec.get("definition", "")).strip()
                    agg[key] = {
                        "term": term,
                        "definition": definition or prev.get("definition", ""),
                        "refs": spec.get("doc_refs", prev.get("refs", [])),
                    }
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not read glossary overrides: %s", e)

        gloss_rows = [
            (e["term"], e["definition"], json.dumps(e["refs"], ensure_ascii=False),
             1 if key in curated_terms else 0)
            for key, e in sorted(agg.items())
        ]
        con.executemany(
            "INSERT INTO glossary (term,definition,doc_refs_json,curated) "
            "VALUES (?,?,?,?)", gloss_rows,
        )

        # Populate FTS from base tables (external-content: insert rowid+cols).
        con.execute(
            "INSERT INTO docs_fts(rowid, card_md, title) "
            "SELECT rowid, card_md, title FROM docs"
        )
        con.execute(
            "INSERT INTO chunks_fts(rowid, heading, context_txt, body_md) "
            "SELECT chunk_id, heading, context_txt, body_md FROM chunks"
        )
        con.execute(
            "INSERT INTO glossary_fts(rowid, term, definition) "
            "SELECT rowid, term, definition FROM glossary"
        )

        con.commit()
        counts = {
            "docs": len(docs),
            "chunks": chunk_id,
            "glossary": len(gloss_rows),
        }
        return counts
    finally:
        con.close()


def main(argv: Optional[List[str]] = None) -> int:
    global GLOSSARY_OVERRIDES
    p = argparse.ArgumentParser(description="Build the knowledge-library FTS index.")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Output SQLite path")
    p.add_argument("--library", default=str(DEFAULT_LIBRARY), help="Tier-F library dir")
    p.add_argument("--tier-o", default=str(DEFAULT_TIER_O),
                   help="Tier-O exports dir (indexed if present)")
    p.add_argument("--glossary-overrides", default=None,
                   help="Operator glossary-overrides JSON (default: exports/json/"
                        "knowledge_glossary_overrides.json). Overrides merged last.")
    args = p.parse_args(argv)

    if args.glossary_overrides:
        GLOSSARY_OVERRIDES = Path(args.glossary_overrides)

    docs = scan_library(Path(args.library), Path(args.tier_o))
    if not docs:
        logger.warning("No documents found — building an empty index.")
    counts = build(Path(args.db), docs)
    logger.info("Index built at %s: %d docs, %d chunks, %d glossary terms.",
                args.db, counts["docs"], counts["chunks"], counts["glossary"])
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
