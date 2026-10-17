#!/usr/bin/env python3
"""Build the research-literature section of the knowledge library (Tier R).

The section holds condensations of the research the platform's own instruments
rest on - the reference lists of
docs/analysis/embedding_subtraction/{KLAERUNG_eingriffsorte…, LITERATUR_prior_und_bias…}.
Originals are never committed: PDFs live under resources/knowledge_originals/
research/ (gitignored), the raw Docling Markdown beside them, and only the
compact PROFIL/WISSEN/GLOSSAR form lands in the library. That is the library's
standing rule (BIBLIOTHEK.md §3), not an extra precaution for this section.

Three phases, each resumable - re-running skips whatever is already there,
and a reindex afterwards whenever the library changed:

  1. fetch    arXiv PDF or a direct pdf_url -> resources/knowledge_originals/research/
              (entries carrying local_pdf are operator copies and are never fetched)
  2. raw      PDF -> <doc_id>.raw.md via knowledge_ingest.py (Docling, needs the
              knowledge venv - this phase re-executes itself there)
  3. condense raw Markdown -> library/research/<doc_id>.md via the platform's own
              Verdichtung (my_app/services/knowledge_processing.py)

Title/authors/year come from the document itself via the platform's own
identify_bibliographic (which returns nothing rather than inventing); entries
with a "meta" block carry hand-verified data for publisher PDFs whose title page
does not survive extraction.

USAGE
    ../venv/bin/python devserver/scripts/ingest_research_literature.py --all
    ... --phase fetch|raw|condense       # one phase only
    ... --only 2303.07345 --force        # single entry, redo it
    ... --list                           # what is done, what is pending
The index is rebuilt automatically whenever this run changed the library, or
whenever the index is older than the texts in it - so a condensation is
findable the moment it exists, and the two cannot drift apart unnoticed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
DEVSERVER = REPO / "devserver"
sys.path.insert(0, str(DEVSERVER))
from config import (  # noqa: E402
    KNOWLEDGE_INDEX_SCRIPT, KNOWLEDGE_INGEST_PYTHON, KNOWLEDGE_INGEST_SCRIPT,
    KNOWLEDGE_LIBRARY_DIR, KNOWLEDGE_ORIGINALS_DIR,
)

MANIFEST = DEVSERVER / "scripts" / "research_literature_manifest.json"
ORIGINALS = KNOWLEDGE_ORIGINALS_DIR / "research"
LIBRARY = KNOWLEDGE_LIBRARY_DIR / "research"
# The documented ingest venv, or KNOWLEDGE_INGEST_PYTHON from the environment.
KNOWLEDGE_PY = Path(KNOWLEDGE_INGEST_PYTHON)
INGEST = KNOWLEDGE_INGEST_SCRIPT
UA = "ai4artsed-knowledge-ingest/1.0 (+https://ai4artsed.org; research library)"


def log(msg: str) -> None:
    print(msg, flush=True)


def library_state() -> Dict[str, int]:
    """What lies in the section right now, by name and modification time."""
    if not LIBRARY.exists():
        return {}
    return {p.name: p.stat().st_mtime_ns for p in LIBRARY.glob("*.md")}


def index_is_behind() -> bool:
    """True when the index is missing or older than the newest text in here.

    The library and the index are two things, and only this tells them apart.
    """
    from my_app.services.knowledge_library import index_db_path
    db_path = index_db_path()
    if not db_path.exists():
        return True
    state = library_state()
    return bool(state) and max(state.values()) > db_path.stat().st_mtime_ns


def rebuild_index() -> int:
    """Rebuild the FTS index, so what was just written is findable.

    The library on disk and the index are two things: until this runs, a new
    condensation exists and no search reaches it. Every other path into the
    library reindexes as its own last step - the upload job's step 3, and each
    operator route that writes. This is that step for the path that does not go
    through the devserver. build_knowledge_index.py is stdlib-only, so whichever
    interpreter is running this script can run it.
    """
    script = KNOWLEDGE_INDEX_SCRIPT
    log("")
    log("reindex: " + script.name)
    proc = subprocess.run([sys.executable, str(script)],
                          capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in [ln for ln in out.splitlines() if ln.strip()][-8:]:
        log("  " + line)
    if proc.returncode != 0:
        log(f"  reindex FAILED (code {proc.returncode}) - the library changed "
            f"but no search can see it yet. Run {script} by hand.")
    return proc.returncode


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def resolve(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Every entry carries its own doc_id and url; bibliographic fields are read
    from the document itself at condense time (identify_bibliographic), never
    from an external index and never typed from memory."""
    e = dict(entry)
    if not e.get("doc_id"):
        raise ValueError(f"manifest entry without doc_id: {e}")
    if not e.get("url") and e.get("arxiv"):
        e["url"] = f"https://arxiv.org/abs/{e['arxiv']}"
    return e


def load_manifest() -> List[Dict[str, Any]]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return data["entries"]


# --------------------------------------------------------------------------
# Phases
# --------------------------------------------------------------------------

def pdf_path(e: Dict[str, Any]) -> Path:
    if e.get("local_pdf"):
        return ORIGINALS / e["local_pdf"]
    return ORIGINALS / f"{e['doc_id']}.pdf"


def raw_path(e: Dict[str, Any]) -> Path:
    return ORIGINALS / f"{e['doc_id']}.raw.md"


def out_path(e: Dict[str, Any]) -> Path:
    return LIBRARY / f"{e['doc_id']}.md"


def phase_fetch(e: Dict[str, Any], force: bool) -> bool:
    target = pdf_path(e)
    if e.get("local_pdf"):
        if not target.exists():
            log(f"  MISSING operator copy: {target}")
            return False
        return True
    if target.exists() and not force:
        return True
    url = e.get("pdf_url") or f"https://arxiv.org/pdf/{e['arxiv']}"
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    if not data.startswith(b"%PDF"):
        log(f"  NOT A PDF from {url} ({len(data)} bytes)")
        return False
    target.write_bytes(data)
    log(f"  fetched {len(data)//1024} KB -> {target.name}")
    return True


def phase_raw(e: Dict[str, Any], force: bool) -> bool:
    raw = raw_path(e)
    if raw.exists() and not force:
        return True
    pdf = pdf_path(e)
    if not pdf.exists():
        log(f"  no PDF for {e['doc_id']}")
        return False
    if not KNOWLEDGE_PY.exists():
        log(f"  knowledge venv missing: {KNOWLEDGE_PY}")
        return False
    cmd = [
        str(KNOWLEDGE_PY), str(INGEST), str(pdf),
        "--doc-id", e["doc_id"], "--raw-out", str(raw),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5400)
    if res.returncode != 0 or not raw.exists():
        log(f"  DOCLING FAILED: {res.stderr.strip().splitlines()[-3:]}")
        return False
    log(f"  raw {raw.stat().st_size // 1024} KB")
    return True


def phase_condense(e: Dict[str, Any], force: bool) -> bool:
    out = out_path(e)
    if out.exists() and not force:
        return True
    raw = raw_path(e)
    if not raw.exists():
        log(f"  no raw Markdown for {e['doc_id']}")
        return False

    os.chdir(DEVSERVER)
    from my_app.services import knowledge_processing as kp

    raw_md = raw.read_text(encoding="utf-8")
    llm = kp.default_llm_fn()
    meta = dict(e.get("meta") or {})

    # Bibliography from the document itself - the platform's own identifier,
    # which returns None rather than inventing. A hand-verified "meta" block in
    # the manifest (publisher PDFs without a machine-readable title page) wins.
    if not meta.get("titel") or not meta.get("autor"):
        rec = kp.identify_bibliographic(raw_md, doc_id=e["doc_id"], llm=llm)
        meta.setdefault("titel", rec.composed_titel or "")
        meta.setdefault("autor", rec.autoren_str or "")
        meta.setdefault("jahr", rec.jahr or 0)
        log(f"     biblio: {meta.get('titel','')[:70]!r} / {meta.get('autor','')[:60]!r}"
            f" / {meta.get('jahr')} (confidence={rec.confidence})")

    front_matter = {
        "id": e["doc_id"],
        "titel": meta.get("titel", ""),
        "autor": meta.get("autor", ""),
        "jahr": meta.get("jahr", 0),
        "sprache": e.get("sprache", "en"),
        "tier": e.get("tier", "R"),
        "sparten": e.get("sparten", ["uebergreifend"]),
        "themen": e.get("themen", ["ai"]),
        "lizenz": e.get("lizenz", ""),
        "url": meta.get("url") or e.get("url", ""),
        "status": "published",
    }
    res = kp.process_document(
        raw_md, front_matter,
        llm=llm, mode=e.get("mode", "essay"), target_lang="en",
        progress=lambda m: log("     " + m),
    )
    if res.fatal:
        log("  FATAL (nothing written): " + "; ".join(res.fatal))
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(res.markdown, encoding="utf-8")
    log(f"  -> {out.name}  ratio={res.ratio:.3f}  {res.n_emitted_sections}/{res.n_content_sections} sections"
        f"  glossar={res.n_glossary}  model={res.analysis_model}")
    for w in res.warnings:
        log("  WARN: " + w)
    return True


PHASES = {"fetch": phase_fetch, "raw": phase_raw, "condense": phase_condense}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=list(PHASES), action="append",
                    help="run only this phase (repeatable); default: all three")
    ap.add_argument("--all", action="store_true", help="run every manifest entry")
    ap.add_argument("--only", action="append", default=[],
                    help="restrict to an arXiv id or doc_id (repeatable)")
    ap.add_argument("--force", action="store_true", help="redo work that is already present")
    ap.add_argument("--list", action="store_true", help="show state per entry and exit")
    a = ap.parse_args(argv)

    entries = [resolve(e) for e in load_manifest()]
    if a.only:
        wanted = set(a.only)
        entries = [e for e in entries if e.get("arxiv") in wanted or e["doc_id"] in wanted]
        if not entries:
            log("nothing in the manifest matches --only")
            return 1

    if a.list:
        done = 0
        for e in entries:
            marks = "".join(
                m if p.exists() else "-"
                for m, p in (("P", pdf_path(e)), ("R", raw_path(e)), ("C", out_path(e)))
            )
            done += out_path(e).exists()
            log(f"  [{marks}] {e['doc_id']}")
        log(f"{done}/{len(entries)} condensed  (P=pdf R=raw C=condensed)")
        return 0

    if not (a.all or a.only):
        ap.error("pass --all, --only <id>, or --list")

    phases = a.phase or ["fetch", "raw", "condense"]
    before = library_state()
    failed: List[str] = []
    for i, e in enumerate(entries, 1):
        if out_path(e).exists() and not a.force and phases == ["fetch", "raw", "condense"]:
            log(f"[{i}/{len(entries)}] {e['doc_id']} - already condensed, skipping")
            continue
        log(f"[{i}/{len(entries)}] {e['doc_id']}")
        for name in phases:
            if not PHASES[name](e, a.force):
                failed.append(f"{e['doc_id']} ({name})")
                break
    log("")
    log(f"done. {len(entries) - len(failed)}/{len(entries)} through the requested phases.")
    for f in failed:
        log("  FAILED: " + f)

    # A failed entry does not hold back the ones that got through: whatever
    # reached the library is indexed, and the failures are reported either way.
    index_rc = 0
    if library_state() != before or index_is_behind():
        index_rc = rebuild_index()
    else:
        log("library unchanged and the index is current - nothing to rebuild.")
    return 1 if (failed or index_rc) else 0


if __name__ == "__main__":
    sys.exit(main())
