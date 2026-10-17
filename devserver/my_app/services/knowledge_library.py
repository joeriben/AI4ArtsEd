"""
Knowledge Library (Runtime) — Tier-F retrieval over the FTS5 index.

Read-only service on top of exports/knowledge_index.sqlite (built offline by
scripts/build_knowledge_index.py). stdlib-only (sqlite3 + FTS5): the running
devserver gains NO new dependency. Two operations back Resona's two knowledge
tools (BIBLIOTHEK.md §6):

    search(query, sparte, thema, tier, limit) -> a compact MENU:
        doc cards (id / title / year / one-line thesis) + glossary hits +
        top chunk snippets. BM25 over the three FTS tables (cards, chunks,
        glossary), fused by Reciprocal Rank Fusion (k=60); facet filter via
        JOIN. Cross-lingual: one English query variant is generated via the
        GPU LLM (cached in-process); both queries search, RRF fuses. If the
        LLM is unavailable the translation is skipped silently (degrade,
        never break). Whole reply budgeted to ~500–800 tokens.

    read(doc_id, section, chunk_ids, max_chars) -> the passages you actually
        need plus citation metadata (title, year, lizenz, url).

Only status='published' documents are visible. The DB is opened read-only
(mode=ro URI); a missing index yields a clear, actionable error string
(Deployment class — "run build_knowledge_index.py").
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import config

# One serialiser for a front-matter scalar: the index's parser reads the
# value back verbatim only if it is quoted the way the renderer quotes it.
from my_app.services.knowledge_processing import _yaml_scalar as _admin_yaml_scalar

logger = logging.getLogger(__name__)


def index_db_path() -> Path:
    """config.KNOWLEDGE_INDEX_DB, read at call time: the file the ingest writes,
    the one a test redirects. Until 2026-10-10 this module derived the path from
    its own __file__, so a redirected config left it reading the real index
    (finding S-077 of the code review of 2026-10-10)."""
    return Path(config.KNOWLEDGE_INDEX_DB)


RRF_K = 60          # Reciprocal Rank Fusion constant (BIBLIOTHEK.md §5)
PER_TABLE_LIMIT = 20  # candidates pulled from each FTS table before fusion
SNIPPET_CHARS = 200   # per-chunk snippet cap in the search menu
READ_DEFAULT_MAX_CHARS = 6000

_INDEX_MISSING_MSG = (
    "The knowledge index is not built yet — no results are available. "
    "Run: python3 devserver/scripts/build_knowledge_index.py "
    "(after download_knowledge.sh + knowledge_ingest.py have produced the "
    "library Markdown). This is a deployment step, not a platform error."
)

# In-process cache of query -> English variant (bounded; see _translate_query).
_QUERY_TRANSLATION_CACHE: Dict[str, str] = {}
_QUERY_CACHE_MAX = 512


# ---------------------------------------------------------------------------
# DB access (read-only)
# ---------------------------------------------------------------------------

def _connect() -> Optional[sqlite3.Connection]:
    """Open the index read-only. Returns None if the file does not exist."""
    db_path = index_db_path()
    if not db_path.exists():
        return None
    uri = f"file:{db_path.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def _fts_match_query(raw: str) -> str:
    """Turn free text into a safe FTS5 MATCH string: keep word tokens, OR them,
    drop punctuation that FTS5 would treat as syntax. Empty -> a token that
    matches nothing rather than a syntax error."""
    tokens = re.findall(r"\w+", raw, flags=re.UNICODE)
    tokens = [t for t in tokens if len(t) > 1]
    if not tokens:
        return '"__no_such_token__"'
    # quote each token (phrase of one word) and OR them for recall
    return " OR ".join(f'"{t}"' for t in tokens)


# ---------------------------------------------------------------------------
# Cross-lingual query variant (optional, degrades silently)
# ---------------------------------------------------------------------------

def _translate_query(query: str) -> Optional[str]:
    """One short GPU-LLM call: an English variant of the query for cross-lingual
    recall. Cached in-process. Returns None (skip) on any failure or if the
    query already looks English/degenerate."""
    q = query.strip()
    if not q:
        return None
    if q in _QUERY_TRANSLATION_CACHE:
        return _QUERY_TRANSLATION_CACHE[q] or None

    variant: Optional[str] = None
    try:
        # Lazy import — keeps this module import-safe in offline/test contexts.
        from my_app.services.llm_service import llm_service
        from my_app.services.knowledge_processing import _strip_think
        from config import KNOWLEDGE_QUERY_TRANSLATION_MODEL
        # llm_service speaks ONLY to the local GPU endpoint — the model must be
        # a local (Ollama) name; the qwen3 line needs /no_think + think-strip.
        model = (KNOWLEDGE_QUERY_TRANSLATION_MODEL or "").strip()
        if model:
            reply = llm_service._complete(  # small, fast, no streaming
                model,
                prompt=f"/no_think Translate this search query to English. Reply with ONLY the "
                       f"translation, no quotes, no explanation:\n{q}",
                temperature=0.0,
            )
            reply = _strip_think(reply)
            if reply:
                cand = reply.strip().strip('"').splitlines()[0].strip()
                # ignore no-ops (same as input) and over-long hallucinations
                if cand and cand.lower() != q.lower() and len(cand) <= 200:
                    variant = cand
    except Exception as e:  # noqa: BLE001 - never break search on translation
        logger.debug("query translation skipped: %s", e)

    if len(_QUERY_TRANSLATION_CACHE) < _QUERY_CACHE_MAX:
        _QUERY_TRANSLATION_CACHE[q] = variant or ""
    return variant


# Public alias: the cross-lingual query variant is a shared retrieval utility.
# website_search.search() reuses it so curated-site search gets the same
# cross-lingual recall the library already has. Kept as an alias (not a rename)
# so the existing private call sites and tests stay untouched.
translate_query = _translate_query


# ---------------------------------------------------------------------------
# Ranked retrieval per table + RRF fusion
# ---------------------------------------------------------------------------

def _facet_clause(sparte: Optional[str], thema: Optional[str], tier: Optional[str]
                  ) -> Tuple[str, list]:
    """Facet filter applied against the docs row (joined in). sparten/themen are
    JSON arrays -> substring match on the JSON text (cheap, index is small)."""
    clauses = ["d.status = 'published'"]
    params: list = []
    if tier:
        clauses.append("d.tier = ?")
        params.append(tier)
    if sparte:
        clauses.append("d.sparten_json LIKE ?")
        params.append(f'%"{sparte}"%')
    if thema:
        clauses.append("d.themen_json LIKE ?")
        params.append(f'%"{thema}"%')
    return " AND ".join(clauses), params


def _facet_doc_ids(con, facet_sql: str, facet_params: list) -> set:
    """The set of published doc_ids passing the current facet filter (used to
    gate glossary hits when a facet is active)."""
    rows = con.execute(
        f"SELECT d.doc_id FROM docs d WHERE {facet_sql}", facet_params
    ).fetchall()
    return {r["doc_id"] for r in rows}


def _search_docs(con, match: str, facet_sql: str, facet_params: list) -> List[str]:
    """Ranked doc_ids from the card FTS."""
    sql = (
        "SELECT d.doc_id FROM docs_fts f "
        "JOIN docs d ON d.rowid = f.rowid "
        f"WHERE docs_fts MATCH ? AND {facet_sql} "
        "ORDER BY bm25(docs_fts) LIMIT ?"
    )
    rows = con.execute(sql, [match, *facet_params, PER_TABLE_LIMIT]).fetchall()
    return [r["doc_id"] for r in rows]


def _search_chunks(con, match: str, facet_sql: str, facet_params: list) -> List[sqlite3.Row]:
    """Ranked chunk rows (with their doc facets) from the chunk FTS."""
    sql = (
        "SELECT c.chunk_id, c.doc_id, c.section_path, c.heading, c.context_txt, "
        "       substr(c.body_md,1,400) AS snippet "
        "FROM chunks_fts f "
        "JOIN chunks c ON c.chunk_id = f.rowid "
        "JOIN docs d ON d.doc_id = c.doc_id "
        f"WHERE chunks_fts MATCH ? AND {facet_sql} "
        "ORDER BY bm25(chunks_fts) LIMIT ?"
    )
    return con.execute(sql, [match, *facet_params, PER_TABLE_LIMIT]).fetchall()


def _search_glossary(con, match: str) -> List[sqlite3.Row]:
    """Ranked glossary rows (glossary has no facets of its own)."""
    sql = (
        "SELECT g.term, g.definition, g.doc_refs_json "
        "FROM glossary_fts f JOIN glossary g ON g.rowid = f.rowid "
        "WHERE glossary_fts MATCH ? ORDER BY bm25(glossary_fts) LIMIT ?"
    )
    return con.execute(sql, [match, PER_TABLE_LIMIT]).fetchall()


def _rrf(rank_lists: List[List[str]]) -> Dict[str, float]:
    """Reciprocal Rank Fusion over several ordered id-lists -> {id: score}."""
    scores: Dict[str, float] = {}
    for lst in rank_lists:
        for rank, key in enumerate(lst):
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


# ---------------------------------------------------------------------------
# Public: search
# ---------------------------------------------------------------------------

def search(query: str, sparte: Optional[str] = None, thema: Optional[str] = None,
           tier: Optional[str] = None, limit: int = 8) -> str:
    con = _connect()
    if con is None:
        return _INDEX_MISSING_MSG
    try:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 8
        limit = max(1, min(limit, 15))

        q = (query or "").strip()
        if not q:
            return "Please give a search query (a topic, term, or question)."

        # Retrieval facet is TIER-ONLY: thema/sparte are non-exclusionary (soft
        # boost below), so a facet can never HIDE a query-relevant doc. Root
        # cause of F1b dismissal: the Tier-O corpus is untagged, and a hard thema
        # filter returned a UNESCO-only menu, so the model disclaimed the topic.
        facet_sql, facet_params = _facet_clause(None, None, tier)

        # Query variants: original + optional English variant.
        variants = [q]
        en = _translate_query(q)
        if en:
            variants.append(en)

        # Per-variant ranked lists, fused per table with RRF.
        doc_lists: List[List[str]] = []
        chunk_lists: List[List[str]] = []
        gloss_lists: List[List[str]] = []
        chunk_by_id: Dict[str, sqlite3.Row] = {}
        gloss_by_term: Dict[str, sqlite3.Row] = {}

        for v in variants:
            match = _fts_match_query(v)
            doc_lists.append(_search_docs(con, match, facet_sql, facet_params))
            crows = _search_chunks(con, match, facet_sql, facet_params)
            chunk_lists.append([str(r["chunk_id"]) for r in crows])
            for r in crows:
                chunk_by_id[str(r["chunk_id"])] = r
            grows = _search_glossary(con, match)
            gloss_lists.append([r["term"] for r in grows])
            for r in grows:
                gloss_by_term.setdefault(r["term"], r)

        doc_scores = _rrf(doc_lists)
        chunk_scores = _rrf(chunk_lists)
        gloss_scores = _rrf(gloss_lists)

        # Promote docs of top chunks into the doc menu too (a strong chunk hit
        # means its document is relevant even if the card didn't match).
        for cid, sc in chunk_scores.items():
            row = chunk_by_id.get(cid)
            if row:
                doc_scores[row["doc_id"]] = doc_scores.get(row["doc_id"], 0.0) + sc * 0.5

        # Soft-facet boost: a thema/sparte facet is a PREFERENCE, not a filter.
        # Bump candidate docs whose actual themen/sparten carry the requested
        # value (same JSON-substring test _facet_clause uses) by one first-rank
        # RRF-unit per matched dimension - re-ranks intent up without evicting
        # query-relevant docs that lack the tag (esp. the untagged Tier-O corpus).
        if (thema or sparte) and doc_scores:
            _soft_boost = 1.0 / (RRF_K + 1)
            _ids = list(doc_scores.keys())
            _ph = ",".join("?" * len(_ids))
            for fr in con.execute(
                "SELECT doc_id, themen_json, sparten_json FROM docs "
                f"WHERE doc_id IN ({_ph})", _ids,
            ).fetchall():
                _bump = 0.0
                if thema and (f'"{thema}"' in (fr["themen_json"] or "")):
                    _bump += _soft_boost
                if sparte and (f'"{sparte}"' in (fr["sparten_json"] or "")):
                    _bump += _soft_boost
                if _bump:
                    doc_scores[fr["doc_id"]] = doc_scores.get(fr["doc_id"], 0.0) + _bump

        if not doc_scores and not chunk_scores and not gloss_scores:
            return (
                f"No knowledge-library hits for '{q}'"
                + (f" (filtered sparte={sparte}, thema={thema}, tier={tier})" if (sparte or thema or tier) else "")
                + ". Try broader terms, or drop a facet filter."
            )

        # ---- render the compact menu ----
        out: List[str] = []

        has_bereich = _docs_has_column(con, "bereich")
        bereich_col = ", bereich" if has_bereich else ""
        shown_bereiche: List[str] = []  # distinct operator areas among the hits, in order

        top_docs = sorted(doc_scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        if top_docs:
            out.append("DOCUMENTS (use read_knowledge(doc_id) to open a passage):")
            for doc_id, _ in top_docs:
                meta = con.execute(
                    "SELECT title, year, card_md" + bereich_col +
                    " FROM docs WHERE doc_id = ? AND status='published'",
                    [doc_id],
                ).fetchone()
                if not meta:
                    continue
                thesis = _one_line_thesis(meta["card_md"])
                year = f", {meta['year']}" if meta["year"] else ""
                line = f"- {doc_id} — {meta['title']}{year}"
                if thesis:
                    line += f" — {thesis}"
                out.append(line)
                if has_bereich:
                    b = (meta["bereich"] or "").strip()
                    if b and b not in shown_bereiche:
                        shown_bereiche.append(b)

        # Operator area context (BIBLIOTHEK.md §9, "Hinweis für Agent"): for each
        # operator area represented in the results that carries a kommentar, add
        # ONE neutral context line naming the area + the operator's note. This is
        # DATA context (why these texts were collected), not an instruction — it
        # sits below the menu and mirrors read()'s per-document hinweis header.
        for line in _bereich_context_lines(shown_bereiche):
            out.append(line)

        # When a facet is active, restrict glossary hits to terms that reference
        # at least one doc passing that facet (so the filter governs the whole
        # menu, not just the DOCUMENTS block). Without a facet, the glossary
        # spans the corpus (§1: "ein Glossar über beide Schichten").
        # Glossary gating is tier-only too (a soft thema/sparte facet must not
        # hide glossary terms), consistent with the tier-only retrieval facet.
        allowed_docs = _facet_doc_ids(con, facet_sql, facet_params) if tier else None

        # Glossary refs must never expose a DRAFT doc_id (published-only surface,
        # BIBLIOTHEK.md §6). The glossary table aggregates terms across the whole
        # corpus incl. drafts, so filter each term's refs to published docs here;
        # a term that lives ONLY in drafts is dropped entirely.
        published_docs = {r["doc_id"] for r in con.execute(
            "SELECT doc_id FROM docs WHERE status='published'"
        ).fetchall()}

        top_gloss = sorted(gloss_scores.items(), key=lambda kv: kv[1], reverse=True)[:5]
        gloss_lines: List[str] = []
        for term, _ in top_gloss:
            row = gloss_by_term.get(term)
            if not row:
                continue
            refs = [d for d in _refs_doc_ids(row["doc_refs_json"]) if d in published_docs]
            if not refs and _refs_doc_ids(row["doc_refs_json"]):
                continue  # term only lives in unpublished (draft) docs
            if allowed_docs is not None and refs and not (set(refs) & allowed_docs):
                continue  # term only lives in facet-excluded docs
            definition = (row["definition"] or "").strip()
            ref_txt = f" [in {', '.join(refs)}]" if refs else ""
            gloss_lines.append(f"- {term}: {_clip(definition, 160)}{ref_txt}")
        if gloss_lines:
            out.append("")
            out.append("GLOSSARY:")
            out.extend(gloss_lines)

        top_chunks = sorted(chunk_scores.items(), key=lambda kv: kv[1], reverse=True)[:5]
        if top_chunks:
            out.append("")
            out.append("PASSAGES (snippets):")
            for cid, _ in top_chunks:
                row = chunk_by_id.get(cid)
                if not row:
                    continue
                where = row["section_path"] or row["heading"] or ""
                out.append(
                    f"- {row['doc_id']} § {where}: \"{_clip(row['snippet'], SNIPPET_CHARS)}\""
                )

        return "\n".join(out).strip()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Public: read
# ---------------------------------------------------------------------------

def read(doc_id: str, section: Optional[str] = None,
         chunk_ids: Optional[List] = None, max_chars: int = READ_DEFAULT_MAX_CHARS) -> str:
    con = _connect()
    if con is None:
        return _INDEX_MISSING_MSG
    try:
        doc_id = (doc_id or "").strip()
        if not doc_id:
            return "Please give a doc_id (from lookup_knowledge)."
        try:
            max_chars = int(max_chars)
        except (TypeError, ValueError):
            max_chars = READ_DEFAULT_MAX_CHARS
        max_chars = max(500, min(max_chars, 12000))

        hinweis_col = ", hinweis" if _docs_has_column(con, "hinweis") else ""
        meta = con.execute(
            "SELECT doc_id,title,authors,year,lang,lizenz,url,status" + hinweis_col +
            " FROM docs WHERE doc_id = ?",
            [doc_id],
        ).fetchone()
        if not meta:
            available = [r["doc_id"] for r in con.execute(
                "SELECT doc_id FROM docs WHERE status='published' ORDER BY doc_id"
            ).fetchall()]
            return (f"No document '{doc_id}'. Available: "
                    + (", ".join(available) if available else "(none indexed)"))
        if meta["status"] != "published":
            return f"Document '{doc_id}' is not published (draft) — not available."

        # Select chunks: explicit ids > section filter > document head.
        rows: List[sqlite3.Row] = []
        if chunk_ids:
            ids = []
            for c in chunk_ids:
                try:
                    ids.append(int(c))
                except (TypeError, ValueError):
                    continue
            if ids:
                placeholders = ",".join("?" for _ in ids)
                rows = con.execute(
                    f"SELECT chunk_id,section_path,heading,context_txt,body_md "
                    f"FROM chunks WHERE doc_id = ? AND chunk_id IN ({placeholders}) "
                    f"ORDER BY chunk_id", [doc_id, *ids],
                ).fetchall()
        elif section:
            rows = con.execute(
                "SELECT chunk_id,section_path,heading,context_txt,body_md "
                "FROM chunks WHERE doc_id = ? AND "
                "(section_path LIKE ? OR heading LIKE ?) ORDER BY chunk_id",
                [doc_id, f"%{section}%", f"%{section}%"],
            ).fetchall()
        if not rows:
            rows = con.execute(
                "SELECT chunk_id,section_path,heading,context_txt,body_md "
                "FROM chunks WHERE doc_id = ? ORDER BY chunk_id", [doc_id],
            ).fetchall()

        # Source metadata header: title, year, url — enough to hand someone
        # the book across the table. The license is curation plumbing (it
        # lives in the items/settings layer), NOT speech material — keeping
        # it out of this text is what keeps it out of Resona's answers.
        # The operator's per-document hinweis (why this was uploaded) is added
        # as ONE neutral line when present — data context, not an instruction.
        doc_hinweis = (meta["hinweis"].strip() if ("hinweis" in meta.keys() and meta["hinweis"]) else "")
        header = [
            f"{meta['title']} — {meta['authors'] or 'UNESCO'}"
            + (f" ({meta['year']})" if meta["year"] else ""),
            *([f"{meta['url']}"] if meta["url"] else []),
            *([f"[Betreiber-Hinweis: {doc_hinweis}]"] if doc_hinweis else []),
            "",
        ]

        body_parts: List[str] = []
        used = 0
        for r in rows:
            where = r["section_path"] or r["heading"] or ""
            block = (f"[§ {where} — chunk {r['chunk_id']}]\n" if where else "") + (r["body_md"] or "")
            if used + len(block) > max_chars and body_parts:
                body_parts.append(f"… (truncated at {max_chars} chars; narrow with section= or chunk_ids=)")
                break
            body_parts.append(block)
            used += len(block)

        if not body_parts:
            return "\n".join(header) + "(this document has no indexed passages)"
        return "\n".join(header) + "\n\n".join(body_parts)
    finally:
        con.close()


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def doc_tier(doc_id: str) -> Optional[str]:
    """Which tier a published document sits in, or None if it is not indexed.

    A caller with partial access needs this: search can be pinned to one tier,
    but read() takes a doc_id and would open any document there is.
    """
    con = _connect()
    if not con:
        return None
    try:
        row = con.execute(
            "SELECT tier FROM docs WHERE doc_id = ? AND status = 'published'",
            (doc_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def doc_card(doc_id: str) -> Optional[Dict]:
    """Title, authors, year, licence and link of a published document.

    read() prints these into its passage for a model to cite from. A card on the
    workshop board needs the same facts as fields, and parsing them back out of
    a formatted passage would make the card break the next time that format is
    touched.
    """
    con = _connect()
    if not con:
        return None
    try:
        row = con.execute(
            "SELECT doc_id, title, authors, year, lizenz, url FROM docs "
            "WHERE doc_id = ? AND status = 'published'",
            (doc_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def _clip(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _one_line_thesis(card_md: str) -> str:
    """One-line thesis for the search menu, from the PROFIL text (docs.card_md).
    The PROFIL is already the positioning digest, so the first substantive line
    is the thesis. Tolerates an older ### POSITION card by preferring that line
    when present."""
    if not card_md:
        return ""
    body = card_md
    m = re.search(r"###\s*POSITION\s*\n(.+?)(?:\n###|\Z)", card_md, re.DOTALL)
    if m:
        body = m.group(1)
    for line in body.splitlines():
        line = line.strip().lstrip("-").strip()
        if line and not line.startswith("#") and line != "_(zu ergänzen)_":
            return _clip(line, 160)
    return ""


def _refs_doc_ids(doc_refs_json: Optional[str]) -> List[str]:
    if not doc_refs_json:
        return []
    try:
        refs = json.loads(doc_refs_json)
    except (json.JSONDecodeError, TypeError):
        return []
    out = []
    for r in refs:
        if isinstance(r, dict) and r.get("doc_id"):
            out.append(r["doc_id"])
    return out[:4]


def _bereich_context_lines(bereich_ids: List[str]) -> List[str]:
    """One neutral context line per operator area (that has a kommentar) among the
    given area ids, in order. Shape:

        [Bereich "<name>" — Betreiber-Hinweis: <kommentar>]

    This is the "Hinweis für Agent" surface (BIBLIOTHEK.md §9): DATA context that
    tells Resona why an operator collected these texts. Areas without a kommentar
    contribute nothing (no bare area names — the note is the point). Reads the
    areas store lazily so this module stays import-safe; any failure degrades to
    no lines (never breaks search)."""
    if not bereich_ids:
        return []
    try:
        from my_app.services import knowledge_areas as _ka
    except Exception:  # noqa: BLE001
        return []
    lines: List[str] = []
    for bid in bereich_ids:
        try:
            area = _ka.get_area(bid)
        except Exception:  # noqa: BLE001
            area = None
        if not area:
            continue
        kommentar = (area.get("kommentar") or "").strip()
        if not kommentar:
            continue
        name = (area.get("name") or bid).strip()
        lines.append(f'[Bereich "{name}" — Betreiber-Hinweis: {kommentar}]')
    return lines


# ===========================================================================
# OPERATOR CURATION (Settings, BIBLIOTHEK.md §9) — NOT the Resona retrieval path
# ===========================================================================
# The functions above (search / read) are Resona's published-only retrieval
# surface and must stay untouched. Everything below is the Tier-O *curation*
# surface used exclusively by the authenticated Settings routes: it sees drafts,
# reads the Markdown source directly (so card edits show before a reindex), and
# never leaks into a tool the model can call. All of it is confined to Tier O
# (exports/knowledge_library/); Tier-F files (committed library/) are read-only
# from here — the routes enforce that with a 403.

# Front-matter / section parsing for the curation views. Kept local (a small
# mirror of build_knowledge_index._parse_front_matter) so this runtime module
# has no import dependency on the offline scripts package.
_ADMIN_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_ADMIN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_ADMIN_GLOSS_LINE_RE = re.compile(
    r"^-\s+\*\*(.+?)\*\*\s+—\s+(.*?)(?:\s+_\(→\s*(.*?)\s*\)_)?\s*$"
)


def _admin_unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return s[1:-1]
    return s


def _admin_parse_front_matter(md: str) -> Dict:
    m = _ADMIN_FM_RE.match(md)
    if not m:
        return {}
    fm: Dict = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if not line or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            fm[key] = [_admin_unquote(p.strip()) for p in inner.split(",")] if inner else []
        else:
            fm[key] = _admin_unquote(raw)
    return fm


def _admin_top_sections(md: str) -> Dict[str, str]:
    """Split the body (after front-matter) into its top-level ## sections
    (PROFIL / WISSEN / GLOSSAR), returning {SECTION_NAME: body_text}. WISSEN's
    own ### subsection headings are level-3 and stay inside WISSEN."""
    m = _ADMIN_FM_RE.match(md)
    rest = md[m.end():] if m else md
    sections: Dict[str, str] = {}
    cur_name: Optional[str] = None
    cur_lines: List[str] = []

    def _flush():
        if cur_name is not None:
            sections[cur_name] = "\n".join(cur_lines).strip()

    for line in rest.splitlines():
        hm = _ADMIN_HEADING_RE.match(line)
        if hm and len(hm.group(1)) == 2:  # a top-level ## heading
            _flush()
            cur_name = hm.group(2).strip().upper()
            cur_lines = []
        elif cur_name is not None:
            cur_lines.append(line)
    _flush()
    return sections


def _admin_parse_glossary(gloss_md: str) -> List[Dict]:
    out: List[Dict] = []
    for line in (gloss_md or "").splitlines():
        gm = _ADMIN_GLOSS_LINE_RE.match(line.strip())
        if gm:
            out.append({
                "term": gm.group(1).strip(),
                "definition": (gm.group(2) or "").strip(),
                "anchor": (gm.group(3) or "").strip(),
            })
    return out



def _docs_has_column(con, column: str) -> bool:
    """True if the docs table carries `column`. Guards against an index built by
    an older schema (pre-bereich/hinweis) so the curation views + the bereich
    facet degrade gracefully until the next reindex."""
    try:
        cols = {r["name"] for r in con.execute("PRAGMA table_info(docs)").fetchall()}
    except sqlite3.Error:
        return False
    return column in cols


def list_operator_items(bereich: Optional[str] = None) -> List[Dict]:
    """Curation list of ALL Tier-O items (drafts INCLUDED), from the index.

    Settings-Kuration only (BIBLIOTHEK.md §9). Returns doc_id, titel, jahr,
    lizenz, status, sparten, themen, bereich, hinweis and chunk count per item.
    A freshly uploaded item appears here once its ingest job has reindexed.
    Optionally filtered to one operator area (`bereich`). Returns an empty list
    when the index does not exist yet.
    """
    con = _connect()
    if con is None:
        return []
    try:
        has_bereich = _docs_has_column(con, "bereich")
        has_hinweis = _docs_has_column(con, "hinweis")
        # Analysis provenance columns (additive, 2026-07-10): guarded the same
        # way as bereich/hinweis so a not-yet-reindexed old-schema DB degrades
        # gracefully instead of a "no such column" crash.
        has_analyzed_at = _docs_has_column(con, "analyzed_at")
        has_analysis_lang = _docs_has_column(con, "analysis_lang")
        has_analysis_model = _docs_has_column(con, "analysis_model")
        extra_cols = ""
        if has_bereich:
            extra_cols += ", d.bereich"
        if has_hinweis:
            extra_cols += ", d.hinweis"
        if has_analyzed_at:
            extra_cols += ", d.analyzed_at"
        if has_analysis_lang:
            extra_cols += ", d.analysis_lang"
        if has_analysis_model:
            extra_cols += ", d.analysis_model"
        where = "d.tier = 'O'"
        params: list = []
        if bereich and has_bereich:
            where += " AND d.bereich = ?"
            params.append(bereich)
        rows = con.execute(
            "SELECT d.doc_id, d.title, d.year, d.lizenz, d.status, d.lang, "
            "       d.sparten_json, d.themen_json, d.authors" + extra_cols + ", "
            "       (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id) AS chunks "
            f"FROM docs d WHERE {where} ORDER BY d.doc_id",
            params,
        ).fetchall()
        out: List[Dict] = []
        for r in rows:
            keys = r.keys()
            out.append({
                "doc_id": r["doc_id"],
                "titel": r["title"],
                "jahr": r["year"],
                "lizenz": r["lizenz"],
                "status": r["status"],
                "sprache": r["lang"],
                "autor": r["authors"],
                "sparten": _json_list(r["sparten_json"]),
                "themen": _json_list(r["themen_json"]),
                "bereich": r["bereich"] if "bereich" in keys else "",
                "hinweis": r["hinweis"] if "hinweis" in keys else "",
                "analyzed_at": r["analyzed_at"] if "analyzed_at" in keys else "",
                "analysis_lang": r["analysis_lang"] if "analysis_lang" in keys else "",
                "analysis_model": r["analysis_model"] if "analysis_model" in keys else "",
                "chunks": r["chunks"],
                "readonly": False,  # Tier-O items are curated (mutable)
            })
        return out
    finally:
        con.close()


def _json_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return [str(x) for x in v] if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def operator_md_path(doc_id: str) -> Optional[Path]:
    """The Tier-O Markdown path for a doc_id, or None if the id is unsafe.

    Sanitised against path traversal (the doc_id was server-derived at upload,
    but curation routes take it from the URL, so treat it as untrusted)."""
    from config import KNOWLEDGE_TIER_O_DIR
    safe = re.sub(r"[^A-Za-z0-9_-]", "", (doc_id or "").strip())
    if not safe:
        return None
    return Path(KNOWLEDGE_TIER_O_DIR) / f"{safe}.md"


def _item_view_from_md(md: str, stem: str, *, readonly: bool) -> Dict:
    """Parse one compact library Markdown (PROFIL/WISSEN/GLOSSAR + front-matter)
    into the curation/detail view dict. Shared by the Tier-O curation view and
    the Tier-F Settings-transparency view — the ONLY difference between them is
    `readonly` (Tier F is never editable) and where the file came from. The
    PROFIL is exposed as `card` (the editable digest for Tier O; read-only text
    for Tier F), WISSEN as read-only context, GLOSSAR as parsed entries."""
    fm = _admin_parse_front_matter(md)
    sections = _admin_top_sections(md)
    return {
        "doc_id": fm.get("id") or stem,
        "titel": fm.get("titel", ""),
        "autor": fm.get("autor", ""),
        "jahr": fm.get("jahr", ""),
        "quelle": fm.get("quelle", "") if isinstance(fm.get("quelle"), str) else "",
        "sprache": fm.get("sprache", ""),
        "tier": fm.get("tier", ""),
        "lizenz": fm.get("lizenz", ""),
        "url": fm.get("url", ""),
        "status": fm.get("status", "draft"),
        "sparten": fm.get("sparten", []) if isinstance(fm.get("sparten"), list) else [],
        "themen": fm.get("themen", []) if isinstance(fm.get("themen"), list) else [],
        "bereich": fm.get("bereich", "") if isinstance(fm.get("bereich"), str) else "",
        "hinweis": fm.get("hinweis", "") if isinstance(fm.get("hinweis"), str) else "",
        # Analysis provenance (additive, 2026-07-10): absent ("") on any
        # document produced before this feature -- never guessed/backfilled.
        # The frontend renders that as a muted "never analysed with
        # provenance" marker. analysis_lang is the TARGET language the
        # analysis was WRITTEN in; `sprache` above is the document's own
        # detected SOURCE language -- the two must never be conflated (see
        # knowledge_processing.DEFAULT_ANALYSIS_LANG).
        "analyzed_at": fm.get("analyzed_at", "") if isinstance(fm.get("analyzed_at"), str) else "",
        "analysis_lang": fm.get("analysis_lang", "") if isinstance(fm.get("analysis_lang"), str) else "",
        "analysis_model": fm.get("analysis_model", "") if isinstance(fm.get("analysis_model"), str) else "",
        "card": sections.get("PROFIL", ""),
        "wissen": sections.get("WISSEN", ""),
        "glossary": _admin_parse_glossary(sections.get("GLOSSAR", "")),
        "readonly": bool(readonly),
    }


def get_operator_item(doc_id: str) -> Optional[Dict]:
    """Full curation view of ONE Tier-O item, read from the Markdown source
    (drafts included). Returns metadata + the PROFIL text (as `card`, the
    editable positioning digest) + the WISSEN text (read-only context) + parsed
    glossary terms, or None if no such Tier-O file exists. Reads the MD, not the
    index, so edits are visible before a reindex (BIBLIOTHEK.md §9)."""
    path = operator_md_path(doc_id)
    if not path or not path.exists():
        return None
    try:
        md = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("[KNOWLEDGE] could not read Tier-O item %s: %s", path, e)
        return None
    return _item_view_from_md(md, path.stem, readonly=False)


# --- Tier-F read-only views (Settings transparency only) --------------------
# The committed UNESCO corpus (library/**) is shown READ-ONLY in the Settings
# "Knowledge Library" tab so the operator can see WHICH texts the platform ships
# with and what each says — no curation actions attach to it (no publish, no
# delete, no move, no card edit). There is deliberately NO mutation counterpart
# to these: the Tier-O mutation helpers below take Tier-O paths only, so a Tier-F
# doc_id is simply "not there" for them (the routes already return 404/403). None
# of this touches the Resona retrieval path (search/read stay published-only).


def fixed_md_path(doc_id: str) -> Optional[Path]:
    """The committed Tier-F Markdown path for a doc_id, or None if not found.

    Tier F lives in a tree (library/<sparte>/<doc_id>.md), so this scans the
    library dir for a matching file. The doc_id is sanitised against path
    traversal (same character class as operator_md_path) and the resolved file
    is verified to sit UNDER the library dir before it is returned — this is a
    read-only lookup, but the input arrives from a URL, so treat it as untrusted.
    Returns None (not a raise) for an unknown/unsafe id: the caller renders 404.
    """
    from config import KNOWLEDGE_LIBRARY_DIR
    safe = re.sub(r"[^A-Za-z0-9_-]", "", (doc_id or "").strip())
    if not safe:
        return None
    lib = Path(KNOWLEDGE_LIBRARY_DIR)
    if not lib.exists():
        return None
    lib_res = lib.resolve()
    for p in lib.rglob(f"{safe}.md"):
        # Defence in depth: never return a file resolving outside the library.
        if lib_res in p.resolve().parents:
            return p
    return None


def list_fixed_items(bereich: Optional[str] = None) -> List[Dict]:
    """Read-only list of ALL Tier-F (committed UNESCO) items, from the index.

    Settings-transparency only (BIBLIOTHEK.md §9): so the operator can SEE the
    fixed corpus that ships with the platform. Same shape as list_operator_items
    (doc_id, titel, jahr, lizenz, status, sprache, autor, sparten, themen,
    bereich, hinweis, chunks) but every item carries `readonly: True` — there are
    no curation actions for these. `bereich` is accepted for call-site symmetry
    with list_operator_items but ignored (Tier-F docs carry no operator area).
    Returns an empty list when the index does not exist yet."""
    con = _connect()
    if con is None:
        return []
    try:
        has_hinweis = _docs_has_column(con, "hinweis")
        # Analysis provenance columns (additive, 2026-07-10) -- see the same
        # guard in list_operator_items.
        has_analyzed_at = _docs_has_column(con, "analyzed_at")
        has_analysis_lang = _docs_has_column(con, "analysis_lang")
        has_analysis_model = _docs_has_column(con, "analysis_model")
        extra_cols = ", d.hinweis" if has_hinweis else ""
        if has_analyzed_at:
            extra_cols += ", d.analyzed_at"
        if has_analysis_lang:
            extra_cols += ", d.analysis_lang"
        if has_analysis_model:
            extra_cols += ", d.analysis_model"
        rows = con.execute(
            "SELECT d.doc_id, d.title, d.year, d.lizenz, d.status, d.lang, "
            "       d.sparten_json, d.themen_json, d.authors" + extra_cols + ", "
            "       (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id) AS chunks "
            "FROM docs d WHERE d.tier = 'F' ORDER BY d.doc_id",
        ).fetchall()
        out: List[Dict] = []
        for r in rows:
            keys = r.keys()
            out.append({
                "doc_id": r["doc_id"],
                "titel": r["title"],
                "jahr": r["year"],
                "lizenz": r["lizenz"],
                "status": r["status"],
                "sprache": r["lang"],
                "autor": r["authors"],
                "sparten": _json_list(r["sparten_json"]),
                "themen": _json_list(r["themen_json"]),
                "bereich": "",
                "hinweis": r["hinweis"] if "hinweis" in keys else "",
                "analyzed_at": r["analyzed_at"] if "analyzed_at" in keys else "",
                "analysis_lang": r["analysis_lang"] if "analysis_lang" in keys else "",
                "analysis_model": r["analysis_model"] if "analysis_model" in keys else "",
                "chunks": r["chunks"],
                "readonly": True,  # committed Tier-F: view-only, never curated
            })
        return out
    finally:
        con.close()


def get_fixed_item(doc_id: str) -> Optional[Dict]:
    """Full READ-ONLY view of ONE Tier-F item, read from the committed Markdown
    (library/**). Same detail shape as get_operator_item — PROFIL as `card`,
    WISSEN, parsed GLOSSAR — plus `readonly: True`. Returns None if no such
    Tier-F file exists. Settings transparency only; not a curation surface, so
    there is no set_fixed_* counterpart (Tier F is immutable from the API)."""
    path = fixed_md_path(doc_id)
    if not path or not path.exists():
        return None
    try:
        md = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("[KNOWLEDGE] could not read Tier-F item %s: %s", path, e)
        return None
    return _item_view_from_md(md, path.stem, readonly=True)


# --- Tier-O mutations (rewrite the Markdown source, curation only) ----------
# These edit the operator Markdown in place. They NEVER touch Tier-F (the routes
# reject Tier-F before calling here, but these also refuse a path outside the
# Tier-O directory as defence in depth). A reindex is the caller's job.

_ADMIN_STATUS_RE = re.compile(r"^(status:\s*).*$", re.MULTILINE)
# A whole `bereich: …` front-matter line (with its trailing newline) so it can be
# replaced in place OR removed entirely when the doc is moved to "no area".
_ADMIN_BEREICH_LINE_RE = re.compile(r"^bereich:\s*.*\n?", re.MULTILINE)

# Front-matter ordering for inserted meta fields: an absent `quelle:` must land in
# the SAME slot render_front_matter uses (right after jahr) so a repaired file
# matches a freshly-produced one. The anchors are the keys quelle sits between.
_META_INSERT_AFTER = {
    "titel": ("id",),          # titel goes right after id (already always present)
    "autor": ("titel", "id"),  # autor after titel
    "jahr": ("autor", "titel", "id"),
    "quelle": ("jahr", "autor", "titel", "id"),
}



def _set_fm_scalar(fm_block: str, key: str, value) -> str:
    """Return `fm_block` (the '---\\n…\\n---\\n' slice) with front-matter scalar
    `key` set to `value`. Replaces the line in place if present, else inserts it
    after the first present anchor in _META_INSERT_AFTER[key] (falling back to
    just before the closing '---'). Only the FM slice is passed in, so a stray
    `key:` in body text is never touched. Value is quoted via _admin_yaml_scalar."""
    line_re = re.compile(rf"^{re.escape(key)}:\s*.*$", re.MULTILINE)
    new_line = f"{key}: {_admin_yaml_scalar(value)}"
    if line_re.search(fm_block):
        return line_re.sub(new_line, fm_block, count=1)
    # Insert after the first present anchor key; else before the closing '---'.
    for anchor in _META_INSERT_AFTER.get(key, ()):  # ordered preference
        anchor_re = re.compile(rf"^{re.escape(anchor)}:\s*.*$", re.MULTILINE)
        am = anchor_re.search(fm_block)
        if am:
            return fm_block[:am.end()] + f"\n{new_line}" + fm_block[am.end():]
    fm_end = fm_block.rfind("\n---")
    return fm_block[:fm_end] + f"\n{new_line}" + fm_block[fm_end:]


def _assert_tier_o(path: Path) -> None:
    from config import KNOWLEDGE_TIER_O_DIR
    tier_o = Path(KNOWLEDGE_TIER_O_DIR).resolve()
    if tier_o not in path.resolve().parents:
        raise PermissionError(f"Refusing to modify a non-Tier-O file: {path}")


def set_operator_status(doc_id: str, status: str) -> bool:
    """Rewrite the front-matter `status:` of a Tier-O item (draft|published).
    Returns True on success, False if the item does not exist. Raises
    PermissionError if the resolved path is not under the Tier-O directory."""
    if status not in ("draft", "published"):
        raise ValueError("status must be 'draft' or 'published'")
    path = operator_md_path(doc_id)
    if not path or not path.exists():
        return False
    _assert_tier_o(path)
    md = path.read_text(encoding="utf-8")
    if _ADMIN_STATUS_RE.search(md):
        md = _ADMIN_STATUS_RE.sub(f"status: {status}", md, count=1)
    else:
        # No status line in front-matter — insert one before the closing '---'.
        m = _ADMIN_FM_RE.match(md)
        if not m:
            raise ValueError("Tier-O file has no front-matter block")
        fm_end = md.rfind("\n---", 0, m.end())
        md = md[:fm_end] + f"\nstatus: {status}" + md[fm_end:]
    _atomic_write_text(path, md)
    return True


def set_operator_bereich(doc_id: str, bereich: Optional[str]) -> bool:
    """Move a Tier-O item to another operator area by rewriting its front-matter
    `bereich:`. Mirrors set_operator_status's front-matter-rewrite idiom (same
    Tier-O guard); the caller validates the target area exists and rejects the
    fixed UNESCO pseudo-area BEFORE calling here, and reindexes AFTER.

      * bereich = "<area-id>"  -> set/replace the `bereich:` line.
      * bereich = None (or "") -> remove the `bereich:` line entirely (the doc
        then carries no area — the operator inventory's "ohne Bereich" state).

    Only the front-matter block is touched (the edit is confined to the FM slice,
    so a stray `bereich:` in body text is never rewritten). Returns True on
    success, False if the item does not exist. Raises PermissionError if the
    resolved path is not under the Tier-O directory."""
    path = operator_md_path(doc_id)
    if not path or not path.exists():
        return False
    _assert_tier_o(path)
    md = path.read_text(encoding="utf-8")

    m = _ADMIN_FM_RE.match(md)
    if not m:
        raise ValueError("Tier-O file has no front-matter block")
    fm_block = md[: m.end()]          # "---\n…\n---\n"
    rest = md[m.end():]

    target = (bereich or "").strip()
    has_line = _ADMIN_BEREICH_LINE_RE.search(fm_block)
    if target:
        new_line = f"bereich: {target}\n"
        if has_line:
            fm_block = _ADMIN_BEREICH_LINE_RE.sub(new_line, fm_block, count=1)
        else:
            # Insert before the closing '---' (same anchor as set_operator_status).
            fm_end = fm_block.rfind("\n---")
            fm_block = fm_block[:fm_end] + f"\nbereich: {target}" + fm_block[fm_end:]
    else:
        # Move to "no area": drop the line if present; a no-op otherwise.
        if has_line:
            fm_block = _ADMIN_BEREICH_LINE_RE.sub("", fm_block, count=1)

    _atomic_write_text(path, fm_block + rest)
    return True


# Meta fields the curation route may edit (bibliographic id redaction, 2026-07-05).
# titel/autor are strings; jahr is an int-or-empty; quelle is a string-or-empty.
_META_FIELDS = ("titel", "autor", "jahr", "quelle")


def set_operator_meta(doc_id: str, **fields) -> bool:
    """Rewrite the bibliographic front-matter of a Tier-O item: any of
    titel/autor/jahr/quelle passed in `fields` (others left untouched). Mirrors
    set_operator_bereich's FM-slice-confined rewrite idiom (same Tier-O guard);
    the route validates the payload and reindexes AFTER. This is the operator's
    correction surface for a mis-identified title/author (the filename-as-title
    problem): the identifier is best-effort, the operator has the last word.

    Semantics per field (only keys present in `fields` are considered):
      * titel: always kept as a scalar; an empty value is refused for titel (a
        document must keep A title) — the caller enforces that, this just writes.
      * autor / quelle: set to the given string; an empty string CLEARS the field
        (writes `autor: ""` / removes handled by writing the empty scalar).
      * jahr: an int (or a digit string) is written as-is; empty clears it.

    Returns True on success, False if the item does not exist. Raises
    PermissionError if the resolved path is not under the Tier-O directory."""
    path = operator_md_path(doc_id)
    if not path or not path.exists():
        return False
    _assert_tier_o(path)
    md = path.read_text(encoding="utf-8")

    m = _ADMIN_FM_RE.match(md)
    if not m:
        raise ValueError("Tier-O file has no front-matter block")
    fm_block = md[: m.end()]
    rest = md[m.end():]

    for key in _META_FIELDS:
        if key not in fields:
            continue
        val = fields[key]
        if key == "jahr":
            # Normalise a year to an int scalar; blank/None clears to "".
            if val is None or str(val).strip() == "":
                val = ""
            else:
                mm = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(val))
                val = int(mm.group(1)) if mm else str(val).strip()
        else:
            val = "" if val is None else str(val).strip()
        fm_block = _set_fm_scalar(fm_block, key, val)

    _atomic_write_text(path, fm_block + rest)
    return True


def set_operator_card(doc_id: str, card_body: str) -> bool:
    """Replace the ## PROFIL section body of a Tier-O item (the editable
    positioning digest), leaving every other byte untouched. `card_body` is the
    text UNDER the `## PROFIL` heading (the heading itself is managed here).
    Returns False if the item does not exist."""
    path = operator_md_path(doc_id)
    if not path or not path.exists():
        return False
    _assert_tier_o(path)
    md = path.read_text(encoding="utf-8")
    md = _replace_top_section(md, "PROFIL", (card_body or "").strip())
    _atomic_write_text(path, md)
    return True


def delete_operator_item(doc_id: str) -> Dict:
    """Delete a Tier-O item's Markdown and its original upload (PDF), if any.
    Returns {'md_deleted': bool, 'original_deleted': bool}. Raises
    PermissionError if the resolved MD path is not under the Tier-O directory."""
    path = operator_md_path(doc_id)
    result = {"md_deleted": False, "original_deleted": False}
    if path and path.exists():
        _assert_tier_o(path)
        path.unlink()
        result["md_deleted"] = True
    # Remove the stored original PDF too (operator originals live under
    # resources/knowledge_originals/operator/<doc_id>.pdf).
    orig = _operator_original_path(doc_id)
    if orig and orig.exists():
        try:
            orig.unlink()
            result["original_deleted"] = True
        except OSError as e:
            logger.warning("[KNOWLEDGE] could not delete original %s: %s", orig, e)
    return result


def _operator_original_path(doc_id: str) -> Optional[Path]:
    from config import KNOWLEDGE_ORIGINALS_DIR
    safe = re.sub(r"[^A-Za-z0-9_-]", "", (doc_id or "").strip())
    if not safe:
        return None
    return Path(KNOWLEDGE_ORIGINALS_DIR) / "operator" / f"{safe}.pdf"


def _replace_top_section(md: str, section: str, new_body: str) -> str:
    """Replace the body of a `## <section>` block (heading kept), preserving the
    rest. If the section is absent, insert it right after the H1 title (or after
    the front-matter when there is no H1). Mirrors the assemble_markdown order
    enough for PROFIL (which sits first, before WISSEN/GLOSSAR)."""
    heading = f"## {section}"
    new_block = f"{heading}\n\n{new_body}".rstrip()

    # Find the section heading at line start.
    sec_re = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
    sm = sec_re.search(md)
    if sm:
        # End = next top-level '## ' heading after this one, or EOF.
        nxt = re.compile(r"^##\s+\S", re.MULTILINE).search(md, sm.end())
        end = nxt.start() if nxt else len(md)
        return md[:sm.start()] + new_block + "\n\n" + md[end:]

    # Not present — insert after the H1 title if any, else after front-matter.
    h1 = re.compile(r"^#\s+.*$", re.MULTILINE).search(md)
    if h1:
        insert_at = h1.end()
    else:
        m = _ADMIN_FM_RE.match(md)
        insert_at = m.end() if m else 0
    return md[:insert_at] + "\n\n" + new_block + "\n\n" + md[insert_at:].lstrip("\n")


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text atomically (tmp file in the same dir + os.replace)."""
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
# ---------------------------------------------------------------------------
# Scope summary (Resona's GIVEN LIBRARY note)
# ---------------------------------------------------------------------------

_SCOPE_CACHE: Tuple[float, str] = (0.0, "")


def scope_summary() -> str:
    """One-paragraph factual map of the published holdings: total, Sparten
    with counts, Themen vocabulary, tiers. Purely descriptive — the rule that
    interprets it (the library's silence vs. own knowledge) lives in the Resona
    core prompt. Returns '' when the index is missing or empty. Cached
    against the index file's mtime (curation rebuilds the index).
    """
    global _SCOPE_CACHE
    try:
        mtime = index_db_path().stat().st_mtime
    except OSError:
        return ""
    if _SCOPE_CACHE[0] == mtime and _SCOPE_CACHE[1]:
        return _SCOPE_CACHE[1]
    con = _connect()
    if con is None:
        return ""
    try:
        rows = con.execute(
            "SELECT tier, sparten_json, themen_json FROM docs"
            " WHERE status='published'"
        ).fetchall()
    finally:
        con.close()
    if not rows:
        _SCOPE_CACHE = (mtime, "")
        return ""

    from collections import Counter
    sparten: Counter = Counter()
    tiers: Counter = Counter()
    themen = set()
    for r in rows:
        for field, sink in (("sparten_json", sparten), ("themen_json", None)):
            try:
                values = json.loads(r[field] or "[]")
            except (ValueError, TypeError):
                values = []
            for v in values:
                if sink is None:
                    themen.add(str(v))
                else:
                    sink[str(v)] += 1
        tiers[str(r["tier"] or "unspecified")] += 1

    parts = [f"GIVEN LIBRARY: {len(rows)} published titles in this platform's library."]
    if sparten:
        parts.append(
            "Sparten: "
            + ", ".join(f"{name} ({n})" for name, n in sparten.most_common())
            + "."
        )
    if themen:
        listed = sorted(themen)
        shown, extra = listed[:24], len(listed) - 24
        tail = f" — and {extra} more." if extra > 0 else "."
        parts.append("Themen: " + ", ".join(shown) + tail)
    tier_gloss = {
        "F": "UNESCO foundation, fixed",
        "O": "this installation's own holdings",
        "R": "research literature - the studies the platform's instruments rest on",
    }
    parts.append(
        "Tiers: "
        + ", ".join(
            f"{name} = {tier_gloss[name]} ({n})" if name in tier_gloss else f"{name} ({n})"
            for name, n in tiers.most_common()
        )
        + "."
    )
    parts.append(
        "These names are the valid sparte/thema filters for lookup_knowledge."
    )
    text = " ".join(parts)
    _SCOPE_CACHE = (mtime, text)
    return text
