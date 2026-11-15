#!/usr/bin/env python3
"""The knowledge library's runner: the processing stage on source files from
the command line, for one document, a selection, or the whole corpus.

Runs in the devserver venv. For each selected document:

  1. Extraction: Docling in the knowledge venv (scripts/knowledge_ingest.py),
     on the CPU (CUDA_VISIBLE_DEVICES=""), writing `<doc_id>.raw.md`,
     `<doc_id>.blocks.json` and `<doc_id>.figures/` into the work root, in the
     same sub-folder as the source under the source root, with
     `<doc_id>.source.json` naming the source by SHA-256. PDF and DOCX. An
     extraction that is already there is reused when that record matches the
     source and --re-extract is not given.
  2. Integrity: the cross-check against `pdftotext -layout`, or the DOCX's own
     paragraph text (knowledge_extract.extract_with_integrity).
  3. --dry-run: units, the planned LLM calls (bibliographic, type, summary, Reduce,
     review) and image-model calls with their input sizes
     (knowledge_processing.plan_document), written to
     `<out>/plan/<doc_id>.plan.json`. No model call.
     Without --dry-run: the condensation with its checks and adversarial review
     (knowledge_processing.process_document, KNOWLEDGE_PROCESSING_MODEL),
     written with its sidecar (write_library_file) to `<out>/condensed/` --
     or, with --write-library, to the library location of its tier: F to
     KNOWLEDGE_LIBRARY_DIR/unesco, R to KNOWLEDGE_LIBRARY_DIR/research, O to
     KNOWLEDGE_TIER_O_DIR. Nothing is reindexed; the index is rebuilt by
     scripts/build_knowledge_index.py or the library's reindex.
  4. Figure descriptions (--describe-figures): --image-model, else
     KNOWLEDGE_IMAGE_MODEL, else IMAGE_ANALYSIS_MODEL, through the platform's
     image analysis (utils.image_analysis.analyze_image), one call per figure
     the screening keeps (knowledge_extract.screen_figures). A local model
     holds the DevServer gate's lease over HTTP (--gate, gpu_lease_remote.
     gpu_lease_remote) for the whole document; an unreachable gate or a
     refused lease stops the run. The descriptions are kept in
     `<doc_id>.figures.json` beside the extraction, with the lease times, the
     seconds of each call, the SHA-256 of each image and of each prompt; a
     later run takes a description from there only for the image file it was
     made from and the prompt it was made with.
     --figures-only --describe-figures: the same, without the condensation.
     --figures-only alone is the comparison of image models: the
     descriptions go to `<out>/figures/<doc_id>.figures.json` and, side by
     side with the descriptions kept beside the extraction, to
     `<out>/figures/<doc_id>.compare.md`; nothing beside the extraction and
     nothing of an earlier run is written.
     From the worktree, COMFYUI_PATH has to name the main checkout's ComfyUI,
     where the weights are.
  5. --review-only: the adversarial review of the condensation already under
     `<out>/condensed/` by the model of this run (--model,
     --reasoning-effort), so that one reviewer judges the files of several
     condensing models alike (knowledge_processing.review_condensation). The
     condensation stays as it is; the verdict, the condensing model, the
     verdict the file carries and the usage go to
     `<out>/review/<reviewer>/<doc_id>.json`, which a later run skips unless
     --force is given.

Documents come from the transfer table `ZUORDNUNG_ZOTERO.tsv` under the source
root (columns tier, bereich, unterordner, doc_id, jahr, titel, ziel, ...),
selected by --doc-id / --tier / --bereich / --max-pages, or the whole table; or
one explicit file with --source PATH --doc-id ID (tier and bereich still come
from the table when the doc_id is in it). Metadata of an earlier analysis
(titel, autor, lizenz, sparten, themen, hinweis, url) is carried forward
from a library file `<doc_id>.md` in one of the --prior-library folders, as
a reprocess does; the licence, where no such file has one, from the
knowledge index (--prior-index, opened read-only). The status is the gate's
(knowledge_processing.gate_status): a document with a prior file is
reprocessed (held only as the operator's draft or an unreleased upload), one
without is a fresh upload held for the operator's release.

Resumable: every document leaves `<out>/state/<doc_id>.json` (done, failed,
stopped) and its log in `<out>/logs/<doc_id>.log`; a document that is done is
skipped on the next run unless --force is given. A dry run skips a document
whose plan is there.

Ceiling: --max-calls and --max-tokens stop the run before the call that would
pass them (counted over the whole run: LLM calls through this runner, and the
input plus output tokens the platform's usage ledger, data/api_usage.jsonl,
records for them). The document in progress is not written and stays
`stopped`; the next run starts it again.

USAGE
    venv/bin/python devserver/scripts/knowledge_run.py --dry-run
    venv/bin/python devserver/scripts/knowledge_run.py --dry-run --max-pages 199
    venv/bin/python devserver/scripts/knowledge_run.py --doc-id <id> --max-calls 200
    venv/bin/python devserver/scripts/knowledge_run.py --tier O --write-library --max-tokens 5000000
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DEVSERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVSERVER))

import config  # noqa: E402
from my_app.services import knowledge_checks  # noqa: E402
from my_app.services import knowledge_library as kl  # noqa: E402
from my_app.services import knowledge_processing as kp  # noqa: E402
from my_app.services import knowledge_review  # noqa: E402
from my_app.services.knowledge_extract import (  # noqa: E402
    extract_with_integrity, format_page_range, parse_page_range)
from my_app.services.knowledge_ingest_service import (  # noqa: E402
    build_front_matter, needs_bibliographic_call)

TABLE_NAME = "ZUORDNUNG_ZOTERO.tsv"
HOLDER = "knowledge_run"

# Document types set here instead of asked of the model
# (process_document(doc_type=...)): the three normative instruments of Tier F.
# Taken over from scripts/reprocess_library.py, which this runner replaces.
FIXED_DOC_TYPES = {
    "unesco-basic-texts-of-the-2003-convention-for-the-safeguarding-of-the-intangible-cultural-heritage-2024-edition-2003": "normative_text",
    "unesco-uebereinkommen-ueber-den-schutz-und-die-foerderung-der-vielfalt-kultureller-ausdrucksformen-2005-deutsche-uebersetzung-2005": "normative_text",
    "unesco-recommendation-on-the-ethics-of-artificial-intelligence-2021": "normative_text",
}

# Documents that are a chapter or section of the file they come in (a whole
# volume, brochure or galley): their PDF pages, first and last. Only these
# pages are extracted for the condensation, checked and cited; the page
# references are the printed pages of the volume (knowledge_extract.
# restrict_to_pages). Each range is the page range of the excerpt the library
# held before (resources/knowledge_originals/operator/<doc_id>.pdf), found by
# matching every page of that excerpt with a page of the volume (2026-11-13).
# Carried into the front matter as `pdf_seiten`; a prior library file's
# `pdf_seiten` takes precedence (make_spec).
EXCERPT_PAGES = {
    # "5 Gemeine Durchschnittsbilder", the chapter; printed 109-135 (the
    # 111-137 of the doc_id are PDF pages).
    "steyerl-2025-medium-hot-bilder-in-zeiten-der-hitze-seiten-111-137": (111, 137),
    # Wagner's contribution in an issue of four; printed 72-73.
    "wagner-2021-von-der-entmachtung-des-westlichen-blicks-eine-prognose-zum-ende-der-documenta-als-ausstellungsform-seiten-9-10": (9, 10),
    # "Analyse und Empfehlungen gelebter Bildungsarbeit" (Gute Praxis im
    # Porträt); printed 72-151, PDF 72 an empty divider page.
    "braun-wanke-and-ebel-2020-uber-die-kunst-den-wandel-zu-gestalten": (72, 151),
    # Printed 95-140: "Künstlerische Strategien" (95-114) with "Gestaltung des
    # Arbeitsprozesses", "Inhalte und Themen" and "Präsentation und
    # Abschluss" up to the next Qualitätsbereich.
    "kunstlabore-kunstlerische-strategien": (96, 141),
    # "Die Beziehung", printed 141-158.
    "kunstlabore-qualitatsbereich-beziehung": (142, 159),
    # "Der Raum" (printed 159-179) with "Schlusswort" and the link list,
    # printed 180-189.
    "kunstlabore-qualitatsbereich-raum": (160, 190),
    # Chapter 2, printed 9-40.
    "jorissen-and-marotzki-2009-strukturale-bildungstheorie-und-strukturale-medienbildung": (5, 36),
    # Chapter 4 from its start to the first page of 4.2, printed 95-111.
    "jorissen-and-marotzki-2009-visuelle-artikulationsformen": (91, 107),
}


@dataclass
class Doc:
    doc_id: str
    source: Path           # the source file, PDF or DOCX
    subdir: str            # sub-folder under the source root (and the work root)
    tier: str = ""
    bereich: str = ""
    titel: str = ""
    jahr: str = ""
    # PDF pages of a document that is part of the file (EXCERPT_PAGES).
    pdf_range: Optional[Tuple[int, int]] = None


class CeilingReached(Exception):
    """The run's call or token ceiling would be passed by the next call."""


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

def read_table(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _row_doc(row: Dict[str, str], source_root: Path) -> Doc:
    doc_id = row["doc_id"].strip()
    ziel = (row.get("ziel") or "").strip()
    subdir = (row.get("unterordner") or "").strip()
    if ziel:
        source = source_root / ziel
        subdir = subdir or str(Path(ziel).parent)
    else:
        source = source_root / subdir / f"{doc_id}.pdf"
    return Doc(doc_id=doc_id, source=source, subdir=subdir,
               tier=(row.get("tier") or "").strip().upper(),
               bereich=(row.get("bereich") or "").strip(),
               titel=(row.get("titel") or "").strip(), jahr=(row.get("jahr") or "").strip(),
               pdf_range=EXCERPT_PAGES.get(doc_id))


def page_count(path: Path) -> int:
    """Pages of a PDF (pdfinfo); 0 for a DOCX or an unreadable file."""
    if path.suffix.lower() != ".pdf":
        return 0
    try:
        out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True,
                             timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return 0
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 0


def select_docs(a: argparse.Namespace) -> List[Doc]:
    rows = read_table(a.tsv)
    if a.source:
        if not a.doc_id or len(a.doc_id) != 1:
            raise SystemExit("--source needs exactly one --doc-id")
        match = [r for r in rows if r.get("doc_id", "").strip() == a.doc_id[0]]
        doc = _row_doc(match[0], a.source_root) if match else Doc(a.doc_id[0], a.source, "")
        doc.source = a.source
        if not doc.subdir:
            doc.subdir = "operator" if (a.tier or "O").upper() == "O" else (a.tier or "").lower()
        doc.tier = doc.tier or (a.tier or "O").upper()
        doc.bereich = doc.bereich or (a.bereich or "")
        return [doc]
    if not rows:
        raise SystemExit(f"no table at {a.tsv}")
    docs = []
    for r in rows:
        if a.doc_id and r.get("doc_id", "").strip() not in a.doc_id:
            continue
        if a.tier and (r.get("tier") or "").strip().upper() != a.tier.upper():
            continue
        if a.bereich and (r.get("bereich") or "").strip() != a.bereich:
            continue
        doc = _row_doc(r, a.source_root)
        pages = (doc.pdf_range[1] - doc.pdf_range[0] + 1 if doc.pdf_range
                 else page_count(doc.source))
        if a.max_pages and pages > a.max_pages:
            continue
        docs.append(doc)
    return docs


# --------------------------------------------------------------------------
# Metadata from earlier analyses
# --------------------------------------------------------------------------

def prior_item(doc_id: str, dirs: List[Path]) -> Optional[Dict[str, Any]]:
    for d in dirs:
        for md in Path(d).rglob(f"{doc_id}.md"):
            item = kl.read_item_file(md)
            if item:
                item["_path"] = str(md)
                return item
    return None


def index_licence(doc_id: str, index_db: Optional[Path]) -> str:
    """The licence the knowledge index holds for a document, read-only."""
    if not index_db or not Path(index_db).is_file():
        return ""
    con = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT lizenz FROM docs WHERE doc_id = ?", (doc_id,)).fetchone()
    except sqlite3.Error:
        row = None
    finally:
        con.close()
    return (row[0] or "") if row else ""


def make_spec(doc: Doc, prior: Optional[Dict[str, Any]],
              index_db: Optional[Path] = None) -> Tuple[Dict[str, Any], str]:
    """The job spec the ingest service would build: a prior analysis' metadata
    first (sprache excepted, it is detected anew), the table's second; the
    licence from the prior file, else from the index. Returns the spec and
    where its licence came from."""
    p = prior or {}
    lizenz, origin = p.get("lizenz") or "", ""
    if lizenz:
        origin = f"library file {p.get('_path', '')}"
    else:
        lizenz = index_licence(doc.doc_id, index_db)
        origin = "knowledge index" if lizenz else "none"
    spec = {
        "doc_id": doc.doc_id,
        "tier": (p.get("tier") or doc.tier or "O").lower(),
        "title": p.get("titel") or doc.titel,
        "autor": p.get("autor") or "",
        "year": p.get("jahr") or doc.jahr,
        "lang": "",
        "sparten": ", ".join(p.get("sparten") or []),
        "themen": ", ".join(p.get("themen") or []),
        "lizenz": lizenz,
        "url": p.get("url") or "",
        "bereich": p.get("bereich") or doc.bereich,
        "hinweis": p.get("hinweis") or "",
        "pdf_seiten": p.get("pdf_seiten") or format_page_range(doc.pdf_range),
        # A document with a prior file is reprocessed, one without is a fresh
        # upload held for the operator's release (knowledge_processing.gate_status).
        "hold": (kp.reprocess_hold(p.get("status") or "", p.get("status_reason") or "")
                 if prior else kp.STATUS_REASON_RELEASE),
    }
    return spec, origin


def library_target(doc: Doc) -> Path:
    """Where the condensation of a document lives in the library."""
    tier = (doc.tier or "O").upper()
    if tier == "F":
        return Path(config.KNOWLEDGE_LIBRARY_DIR) / "unesco" / f"{doc.doc_id}.md"
    if tier == "R":
        return Path(config.KNOWLEDGE_LIBRARY_DIR) / "research" / f"{doc.doc_id}.md"
    return Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc.doc_id}.md"


# --------------------------------------------------------------------------
# Calls, usage and the ceiling
# --------------------------------------------------------------------------

class UsageLedger:
    """The platform's usage ledger (usage_tracker.USAGE_FILE): the records
    appended since a mark, so a run reads the tokens of its own calls. The
    ledger is shared by every caller on the machine; `since(mark, models)`
    keeps the records of the run's models only, so a run of another model at
    the same time does not count into this one (measured 13.11.2026, issue
    #138: Sonnet and Hydrogen counted GLM's calls). A concurrent run of the
    SAME model still counts in: the ledger carries no run of its own."""

    def __init__(self, path: Optional[Path] = None) -> None:
        if path is None:
            from my_app.services.usage_tracker import USAGE_FILE
            path = USAGE_FILE
        self.path = Path(path)

    def mark(self) -> int:
        return self.path.stat().st_size if self.path.is_file() else 0

    def since(self, mark: int, models: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """The records after `mark`; with `models` (as the run names them,
        "openrouter/z-ai/glm-5.3"), those of these models only. The ledger
        keeps the last segment of the name ("glm-5.3")."""
        if not self.path.is_file():
            return []
        with self.path.open("rb") as fh:
            fh.seek(mark)
            lines = fh.read().decode("utf-8", errors="replace").splitlines()
        wanted = {m.rsplit("/", 1)[-1] for m in models or [] if m}
        out = []
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if wanted and str(rec.get("model") or "").rsplit("/", 1)[-1] not in wanted:
                continue
            out.append(rec)
        return out

    @staticmethod
    def tokens(records: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calls and tokens of the records. input_tokens is the whole prompt;
        of it, the tokens read from and written to the provider's prompt
        cache stand under their own keys where there are any, as the usage
        tracker records them."""
        out = {"calls": len(records),
               "input_tokens": sum(int(r.get("input_tokens") or 0) for r in records),
               "output_tokens": sum(int(r.get("output_tokens") or 0) for r in records)}
        for key in ("cache_read_tokens", "cache_write_tokens"):
            n = sum(int(r.get(key) or 0) for r in records)
            if n:
                out[key] = n
        return out

    @staticmethod
    def cache_text(usage: Dict[str, int]) -> str:
        """The cache share of a usage dict for a log line; empty without one."""
        read, write = usage.get("cache_read_tokens", 0), usage.get("cache_write_tokens", 0)
        return (f" (of them {read} read from the prompt cache, {write} written to it)"
                if read or write else "")


class Budget:
    """The run's ceiling: LLM calls and tokens (input plus output) over the
    whole run. 0 means no ceiling."""

    def __init__(self, max_calls: int = 0, max_tokens: int = 0,
                 ledger: Optional[UsageLedger] = None) -> None:
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self.ledger = ledger
        self.calls = 0
        self._mark = ledger.mark() if (ledger and max_tokens) else 0

    def tokens_used(self, models: Optional[List[str]] = None) -> int:
        if not self.ledger:
            return 0
        t = UsageLedger.tokens(self.ledger.since(self._mark, models))
        return t["input_tokens"] + t["output_tokens"]

    def take(self, models: Optional[List[str]] = None) -> None:
        """Count one call, or raise at the ceiling; `models` are the run's
        models, whose ledger records alone count against the token ceiling."""
        if self.max_calls and self.calls >= self.max_calls:
            raise CeilingReached(f"call ceiling reached: {self.calls} of {self.max_calls} calls")
        if self.max_tokens:
            used = self.tokens_used(models)
            if used >= self.max_tokens:
                raise CeilingReached(f"token ceiling reached: {used} of {self.max_tokens} tokens")
        self.calls += 1


class CountingLlm:
    """The production LLM path (or `fn`), counting calls and input characters
    and asking the budget before every call."""

    def __init__(self, model: Optional[str] = None, budget: Optional[Budget] = None,
                 fn: Optional[Callable[..., Optional[str]]] = None,
                 reasoning_effort: Optional[str] = None) -> None:
        self._fn = fn or kp.default_llm_fn(model=model, reasoning_effort=reasoning_effort)
        self.model = model
        self.budget = budget or Budget()
        self.calls = 0
        self.input_chars = 0

    @property
    def models_used(self) -> List[str]:
        return list(getattr(self._fn, "models_used", None) or [])

    @property
    def ledger_models(self) -> List[str]:
        """The models whose ledger records are this run's: those that served
        a call, before the first call the pinned one."""
        return self.models_used or [m for m in [self.model] if m]

    @property
    def takes_document(self) -> bool:
        """Whether the wrapped function takes the cached document apart
        (knowledge_review.ask); passed on as it is."""
        return bool(getattr(self._fn, "takes_document", False))

    def __call__(self, system: str, user: str, max_tokens: Optional[int] = None,
                 **kw: Any) -> Optional[str]:
        self.budget.take(self.ledger_models)
        self.calls += 1
        self.input_chars += len(system) + len(user) + len(kw.get("document") or "")
        return self._fn(system, user, max_tokens, **kw)


# --------------------------------------------------------------------------
# State and log per document
# --------------------------------------------------------------------------

def state_path(out: Path, doc_id: str) -> Path:
    return out / "state" / f"{doc_id}.json"


def read_state(out: Path, doc_id: str) -> Dict[str, Any]:
    try:
        return json.loads(state_path(out, doc_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(out: Path, doc_id: str, **data: Any) -> None:
    p = state_path(out, doc_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    data["at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


class DocLog:
    """Prints a line and appends it to `<out>/logs/<doc_id>.log`."""

    def __init__(self, out: Path, doc_id: str) -> None:
        self.path = out / "logs" / f"{doc_id}.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, msg: str) -> None:
        print(msg, flush=True)
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {msg}\n")


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------

def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_record_path(blocks_json: Path, doc_id: str) -> Path:
    """`<doc_id>.source.json` beside the extraction: the file it was made
    from, by size and SHA-256."""
    return blocks_json.with_name(f"{doc_id}.source.json")


def source_record(blocks_json: Path, doc_id: str,
                  page_range: Optional[Tuple[int, int]]) -> Dict[str, Any]:
    """The provenance of the condensation: the file (path, size, SHA-256 of
    the whole file) and, for a document that is part of it, its PDF pages as
    `pdf_seiten`. Docling converts the whole file; the range is applied after
    (knowledge_extract.restrict_to_pages), so one extraction serves every
    range of the file. The record beside the extraction is brought to the
    range of this run."""
    path = source_record_path(blocks_json, doc_id)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    pdf_seiten = format_page_range(page_range)
    if record.get("pdf_seiten", "") != pdf_seiten:
        if pdf_seiten:
            record["pdf_seiten"] = pdf_seiten
        else:
            record.pop("pdf_seiten", None)
        path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return record


def extract(doc: Doc, work_root: Path, re_extract: bool, log: Callable[[str], None]) -> Path:
    """Docling on the CPU; returns the blocks.json path. An extraction is
    reused only when its source record names a file with the same SHA-256 as
    the source now: a source replaced under the same doc_id is extracted
    anew, and an extraction without a record is too."""
    work = work_root / doc.subdir
    raw = work / f"{doc.doc_id}.raw.md"
    blocks = work / f"{doc.doc_id}.blocks.json"
    record = source_record_path(blocks, doc.doc_id)
    digest = file_sha256(doc.source)
    if raw.is_file() and blocks.is_file() and not re_extract:
        try:
            made_from = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            made_from = {}
        if made_from.get("sha256") == digest:
            log(f"  extraction reused: {blocks}")
            return blocks
        log("  extraction there, but " + (
            f"made from another file ({made_from.get('source')}, {made_from.get('bytes')} bytes)"
            if made_from else "without a source record") + ": extracted anew")
    interp = Path(config.KNOWLEDGE_INGEST_PYTHON)
    if not interp.exists():
        raise SystemExit(f"Docling venv missing: {interp} (KNOWLEDGE_INGEST_PYTHON)")
    work.mkdir(parents=True, exist_ok=True)
    cmd = [str(interp), str(config.KNOWLEDGE_INGEST_SCRIPT), "--doc-id", doc.doc_id,
           "--raw-out", str(raw), str(doc.source)]
    log("  $ " + " ".join(cmd))
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="")
    started = datetime.now()
    rc = subprocess.run(cmd, env=env).returncode
    log(f"  Docling: exit {rc}, {(datetime.now() - started).total_seconds():.0f} s")
    if rc != 0 or not blocks.is_file():
        raise RuntimeError(f"Docling failed for {doc.doc_id} (exit {rc})")
    record.write_text(json.dumps({"source": str(doc.source), "bytes": doc.source.stat().st_size,
                                  "sha256": digest,
                                  "extracted_at": datetime.now().astimezone().isoformat(
                                      timespec="seconds")}, indent=1), encoding="utf-8")
    return blocks


def _block_counts(extraction) -> Dict[str, int]:
    return dict(collections.Counter(b.kind for b in extraction.blocks))


def run_doc(doc: Doc, a: argparse.Namespace, budget: Budget) -> Dict[str, Any]:
    log = DocLog(a.out, doc.doc_id)
    log(f"== {doc.doc_id}  ({doc.source})")
    if not doc.source.is_file():
        log("  source file missing")
        write_state(a.out, doc.doc_id, state="failed", reason=f"source missing: {doc.source}")
        return {"doc_id": doc.doc_id, "error": f"source missing: {doc.source}"}
    blocks_json = extract(doc, a.work_root, a.re_extract, log)
    raw_md = blocks_json.with_name(f"{doc.doc_id}.raw.md").read_text(encoding="utf-8")
    prior = prior_item(doc.doc_id, a.prior_library)
    spec, licence_origin = make_spec(doc, prior, a.prior_index)
    page_range = parse_page_range(spec["pdf_seiten"])
    extraction = extract_with_integrity(blocks_json, doc.source, page_range)
    integ = extraction.integrity
    source = source_record(blocks_json, doc.doc_id, page_range)
    summary: Dict[str, Any] = {
        "doc_id": doc.doc_id, "source": str(doc.source), "tier": doc.tier,
        "source_sha256": source.get("sha256", ""), "pdf_seiten": spec["pdf_seiten"],
        "bereich": doc.bereich, "pages": extraction.pages,
        "page_numbering": extraction.page_numbering(),
        "lizenz": spec["lizenz"], "lizenz_from": licence_origin,
        "blocks_by_kind": _block_counts(extraction),
        "figures_exported": len(extraction.figures()) + len(integ.figures_screened),
        "figures_screened": len(integ.figures_screened),
        "figures_to_describe": len(extraction.figures_to_describe()),
        "figures_dir": str(extraction.figures_dir or ""),
        "integrity": integ.to_dict(),
    }
    log(f"  pages {extraction.pages} ({extraction.page_numbering()}); "
        f"blocks {summary['blocks_by_kind']}; licence {spec['lizenz']!r} from {licence_origin}")
    log(f"  integrity: checked={integ.checked} gaps={len(integ.gaps)} "
        f"unrepaired={len(integ.unrepaired)} replaced_pages={integ.replaced_pages}")
    for g in integ.gaps:
        log(f"    p.{g.page} {g.kind} {g.words}w {'repaired' if g.repaired else 'UNREPAIRED'}"
            f" {g.anchor}: {g.text[:140]!r}")
    doc_type = a.doc_type or FIXED_DOC_TYPES.get(doc.doc_id)

    if a.review_only:
        return review_doc(doc, a, budget, extraction, blocks_json, log, summary)

    if a.dry_run:
        fm = build_front_matter(spec, raw_md, identify=False)
        plan = kp.plan_document(extraction, fm, lang=a.lang)
        biblio = needs_bibliographic_call(fm)
        plan["bibliographic_call"] = biblio
        plan["doc_type_fixed"] = doc_type or ""
        t = plan["totals"]
        t["llm_calls"] += int(biblio) - (1 if (doc_type and plan["units"]) else 0)
        summary["plan"] = plan
        p = a.out / "plan" / f"{doc.doc_id}.plan.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"  units {len(plan['units'])}: " + "; ".join(
            f"{u['heading'] or '—'} (p.{u['page_from']}-{u['page_to']}, {u['chars']} ch"
            + (f", part {u['part']}/{u['parts']}" if u['parts'] > 1 else "") + ")"
            for u in plan["units"]))
        if plan["skipped"]:
            log(f"  skipped: {plan['skipped']}")
        log(f"  planned: {t['llm_calls']} LLM calls (bibliographic {int(biblio)}) "
            f"+ up to {t['revision_calls_max']} revision calls, input <= "
            f"{t['llm_input_chars_max']} chars; {t['review_calls']} review calls, input <= "
            f"{t['review_input_chars_max']} chars; {t['image_calls']} image calls, "
            f"{t['image_bytes']} bytes, prompts {t['image_prompt_chars']} chars")
        return summary

    llm = CountingLlm(a.model, budget, reasoning_effort=a.reasoning_effort)
    if a.figures_only:
        lang = figures_lang(doc, a, blocks_json)
        if not lang:
            raise SystemExit(f"--figures-only needs --lang, or {output_path(doc, a)} with "
                             f"its sprache, or a kept {figures_cache(blocks_json, doc.doc_id).name} "
                             f"with its lang")
        summary["figures"] = figures_step(doc, extraction, blocks_json, lang, a, log,
                                          keep=a.describe_figures)
        return summary

    ledger = UsageLedger(a.ledger)
    mark = ledger.mark()
    write_state(a.out, doc.doc_id, state="started")
    try:
        fm = build_front_matter(spec, raw_md, lambda m: log("  " + m), llm=llm)
        descriptions: Dict[int, str] = {}
        if extraction.figures_to_describe():
            if a.describe_figures:
                summary["figures"] = figures_step(doc, extraction, blocks_json,
                                                  fm.get("sprache") or "", a, log)
            descriptions = cached_descriptions(blocks_json, extraction, doc.doc_id)
            log(f"  figure descriptions: {len(descriptions)} of "
                f"{len(extraction.figures_to_describe())}")
        result = kp.process_document(extraction, fm, llm=llm, progress=lambda m: log("  " + m),
                                     figure_descriptions=descriptions, doc_type=doc_type,
                                     target_lang=a.lang, map_workers=a.workers,
                                     hold=spec["hold"])
    except CeilingReached as e:
        log(f"  STOPPED: {e}; nothing written for this document")
        write_state(a.out, doc.doc_id, state="stopped", reason=str(e))
        raise
    usage = UsageLedger.tokens(ledger.since(mark, llm.ledger_models))
    summary.update({"llm_calls": llm.calls, "llm_input_chars": llm.input_chars,
                    "usage": usage, "models": llm.models_used,
                    "status": result.status, "status_reason": result.status_reason,
                    "checks": result.checks, "review": result.review.get("label", ""),
                    "fatal": result.fatal, "warnings": result.warnings,
                    "doc_type": result.doc_type, "units": result.units})
    if result.fatal:
        log(f"  FATAL: {result.fatal}; nothing written")
        write_state(a.out, doc.doc_id, state="failed", reason="; ".join(result.fatal),
                    usage=usage)
        return summary
    out_md = kp.write_library_file(result, output_path(doc, a, result.status), extraction,
                                   extra={"source": source})
    findings = knowledge_review.findings_text(result.review)
    if findings:
        log("  review findings:\n" + "\n".join("    " + line for line in findings.splitlines()))
    log(f"  written {out_md}; status {result.status}"
        + (f" ({result.status_reason})" if result.status_reason else "")
        + f"; checks {result.checks}; "
        f"review {summary['review']}; {llm.calls} LLM calls, {llm.input_chars} input chars; "
        f"ledger: {usage['calls']} calls, {usage['input_tokens']} input tokens"
        f"{UsageLedger.cache_text(usage)}, {usage['output_tokens']} output tokens")
    write_state(a.out, doc.doc_id, state="done", target=str(out_md), status=result.status,
                status_reason=result.status_reason, checks=result.checks, review=summary["review"], usage=usage,
                llm_calls=llm.calls, llm_input_chars=llm.input_chars)
    return summary


def output_path(doc: Doc, a: argparse.Namespace, status: str = "") -> Path:
    """Where a condensation is written. With --write-library its library
    location, except a draft whose library file is published: the published
    file stays, and the draft goes to <out>/condensed (2026-11-15), so a run
    never takes a document out of what the agent reads."""
    run_path = a.out / "condensed" / f"{doc.doc_id}.md"
    if not a.write_library:
        return run_path
    target = library_target(doc)
    if status == "draft" and target.is_file():
        current = kl.read_item_file(target) or {}
        if current.get("status") == "published":
            return run_path
    return target


def reviewer_slug(model: Optional[str], effort: Optional[str]) -> str:
    """The folder of one reviewer's verdicts: the model's last name segment
    and the reasoning effort, "claude-opus-5.5-high"; "default" for the
    platform's model chain."""
    name = (model or "default").rsplit("/", 1)[-1]
    return f"{name}-{effort}" if effort else name


def review_path(doc_id: str, a: argparse.Namespace) -> Path:
    return a.out / "review" / reviewer_slug(a.model, a.reasoning_effort) / f"{doc_id}.json"


def review_doc(doc: Doc, a: argparse.Namespace, budget: Budget, extraction,
               blocks_json: Path, log: Callable[[str], None],
               summary: Dict[str, Any]) -> Dict[str, Any]:
    """--review-only: the adversarial review of the condensation under --out,
    by the model of this run (--model, --reasoning-effort), so that one
    reviewer judges the files of several condensing models alike
    (kp.review_condensation). The condensation is not changed; the verdict,
    the condensing model and the usage go to review_path."""
    md_path = output_path(doc, a)
    item = kl.read_item_file(md_path) if md_path.is_file() else None
    if not item:
        log(f"  no condensation at {md_path}: nothing to review")
        return {"doc_id": doc.doc_id, "error": f"no condensation: {md_path}"}
    descriptions = (cached_descriptions(blocks_json, extraction, doc.doc_id)
                    if extraction.figures_to_describe() else {})
    llm = CountingLlm(a.model, budget, reasoning_effort=a.reasoning_effort)
    ledger = UsageLedger(a.ledger)
    mark = ledger.mark()
    started = datetime.now()
    verdict = kp.review_condensation(
        extraction, md_path.read_text(encoding="utf-8"), llm,
        title=str(item.get("titel") or "").strip(),
        lang=(item.get("analysis_lang") or item.get("sprache")
              or kp.DEFAULT_ANALYSIS_LANG).lower(),
        source_lang=str(item.get("sprache") or "").strip().lower(),
        author=str(item.get("autor") or "").strip(),
        figure_descriptions=descriptions, workers=a.workers,
        progress=lambda m: log("  " + m))
    usage = UsageLedger.tokens(ledger.since(mark, llm.ledger_models))
    record = {"doc_id": doc.doc_id, "condensation": str(md_path),
              "condensed_by": item.get("analysis_model", ""),
              "review_in_file": item.get("review", ""),
              "reasoning_effort": a.reasoning_effort or config.KNOWLEDGE_REASONING_EFFORT,
              "seconds": round((datetime.now() - started).total_seconds()),
              "llm_calls": llm.calls, "usage": usage, "verdict": verdict.to_dict()}
    out = review_path(doc.doc_id, a)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    findings = knowledge_review.findings_text(record["verdict"])
    if findings:
        log("  review findings:\n" + "\n".join("    " + line for line in findings.splitlines()))
    log(f"  review of {md_path.name} (condensed by {record['condensed_by']}): "
        f"{verdict.label()}; in the file: {record['review_in_file']}; written {out}; "
        f"{llm.calls} calls, {usage['input_tokens']} input tokens"
        f"{UsageLedger.cache_text(usage)}, {usage['output_tokens']} output tokens")
    summary.update({"review": verdict.label(), "usage": usage, "llm_calls": llm.calls})
    return summary


# --------------------------------------------------------------------------
# Figures: the image model, once per figure, kept beside the extraction
# --------------------------------------------------------------------------

def figures_cache(blocks_json: Path, doc_id: str) -> Path:
    """`<doc_id>.figures.json` beside the extraction: the descriptions by
    figure file, the model, the language and the time each call took. A
    later run reads them from here and puts nothing on the card."""
    return blocks_json.with_name(f"{doc_id}.figures.json")


def _image_digests(extraction) -> Dict[str, str]:
    """SHA-256 of every exported figure file, by its file name."""
    out = {}
    for f in extraction.figures():
        p = (extraction.figures_dir / f.image) if (extraction.figures_dir and f.image) else None
        if p and p.is_file():
            out[f.image] = file_sha256(p)
    return out


def _prompt_digests(extraction, lang: str) -> Dict[str, str]:
    """SHA-256 of the description call of every figure to describe, by its
    file name: the prompt with the figure's caption and the passage that
    refers to it (knowledge_processing._figure_prompt)."""
    refs = kp.figure_references(extraction.blocks)
    return {f.image: hashlib.sha256(kp._figure_prompt(f, lang, refs.get(f.seq, ""))
                                    .encode("utf-8")).hexdigest()
            for f in extraction.figures_to_describe() if f.image}


def cached_descriptions(blocks_json: Path, extraction, doc_id: str) -> Dict[int, str]:
    """The kept descriptions of the figures as they are now: a description
    counts only for the image file it was made from (same SHA-256) and for
    the call it was made with (same prompt SHA-256, in the language of the
    record), so a figure that changed with a new extraction, and every
    figure after a change of the description prompt, goes back to pending.
    A record without prompt digests predates them and counts for nothing.
    A description that is not in the language of the record (the source's)
    is not kept either: the check `figures` fails it, and the next run
    describes the figure again."""
    path = figures_cache(blocks_json, doc_id)
    if not path.is_file():
        return {}
    record = json.loads(path.read_text(encoding="utf-8"))
    by_image = record.get("descriptions") or {}
    made_from = record.get("image_sha256") or {}
    asked = record.get("prompt_sha256") or {}
    now = _image_digests(extraction)
    lang = (record.get("lang") or "").strip().lower()[:2]
    prompts = _prompt_digests(extraction, record.get("lang") or "")

    def _in_language(text: str) -> bool:
        said = knowledge_checks.text_language(text)
        return not lang or not said or said == lang

    return {f.seq: by_image[f.image] for f in extraction.figures_to_describe()
            if f.image and (by_image.get(f.image) or "").strip()
            and made_from.get(f.image) and made_from.get(f.image) == now.get(f.image)
            and asked.get(f.image) and asked.get(f.image) == prompts.get(f.image)
            and _in_language(by_image[f.image])}


def figures_lang(doc: Doc, a: argparse.Namespace, blocks_json: Path) -> str:
    """The language the figures are described in, the source's: --lang, else
    the sprache of the condensation under --out, else the lang of the
    descriptions kept beside the extraction. No LLM call."""
    if a.lang:
        return a.lang
    prior_out = prior_item(doc.doc_id, [output_path(doc, a).parent])
    if (prior_out or {}).get("sprache"):
        return prior_out["sprache"]
    kept = figures_cache(blocks_json, doc.doc_id)
    if kept.is_file():
        return json.loads(kept.read_text(encoding="utf-8")).get("lang") or ""
    return ""


def _quoted(text: str) -> str:
    return "> " + (text or "—").replace("\n", "\n> ")


def compare_figures(doc: Doc, extraction, kept: Dict[str, Any], new: Dict[str, Any]) -> str:
    """The comparison page: per figure to describe, the picture, its caption,
    the passage that refers to it, the description kept beside the extraction
    (with its model) and the new one (with its model); then the figures the
    screening removed or set with their caption only that carry a kept
    description."""
    refs = kp.figure_references(extraction.blocks)
    kept_d = kept.get("descriptions") or {}
    new_d = new.get("descriptions") or {}
    lines = [f"# {doc.doc_id}: figure descriptions",
             "", f"- kept: {kept.get('model') or '—'} ({kept.get('lang') or '—'})",
             f"- new: {new.get('model')} ({new.get('lang')})", ""]
    for f in extraction.figures_to_describe():
        path = (extraction.figures_dir / f.image) if (extraction.figures_dir and f.image) else None
        lines += [f"## {kp._figure_ident(f, new.get('lang'))}, p. {f.page}: {f.image}", ""]
        if path:
            lines += [f"![{f.image}]({path})", ""]
        if f.caption:
            lines += [f"Caption: {f.caption}", ""]
        if refs.get(f.seq):
            lines += [f"Passage: {refs[f.seq]}", ""]
        lines += [f"**kept ({kept.get('model') or '—'})**", "", _quoted(kept_d.get(f.image, "")), "",
                  f"**new ({new.get('model')})**", "", _quoted(new_d.get(f.image, "")), ""]
    described = {f.image for f in extraction.figures_to_describe()}
    left = [img for img in kept_d if img not in described]
    if left:
        lines += ["## Kept descriptions of figures that get no description now", ""]
        screened = {r["image"]: r for r in extraction.integrity.figures_screened}
        for img in left:
            r = screened.get(img)
            why = (f"removed ({r['reason']}, {r['w']}x{r['h']} px)" if r
                   else "caption only (small labelled figure)")
            lines += [f"- {img}: {why}", "", _quoted(kept_d[img]), ""]
    return "\n".join(lines)


def figures_step(doc: Doc, extraction, blocks_json: Path, lang: str,
                 a: argparse.Namespace, log: Callable[[str], None] = print,
                 keep: bool = True) -> Dict[str, Any]:
    """Describe the figures through the platform's image-analysis path. A
    local image model runs on the card: this process is not the DevServer,
    so the DevServer's gate is leased over HTTP for the whole document (rule
    15, gpu_lease_remote.gpu_lease_remote); a gate that does not answer ends
    the run before anything is loaded.

    `keep`: the record goes beside the extraction, where the condensation
    reads it. Otherwise (the comparison of image models) it goes to
    `<out>/figures/<doc_id>.figures.json`, with `<doc_id>.compare.md` beside
    it, and the record beside the extraction is only read."""
    from my_app.services.gpu_lease_remote import gpu_lease_remote
    from my_app.services.model_capabilities import is_local

    model, source = (a.image_model, "--image-model") if a.image_model else kp.figure_model(a.model)
    if not model:
        raise SystemExit("no image model: --image-model, KNOWLEDGE_IMAGE_MODEL and "
                         "IMAGE_ANALYSIS_MODEL are empty, and the condensing model is not "
                         "recorded as reading images")
    log(f"  figures: image model {model} ({source})")
    timings: List[Dict[str, Any]] = []
    started = datetime.now().astimezone()
    if is_local(model):
        alias = model.split("/", 1)[1] if model.startswith("local/") else model
        with gpu_lease_remote(a.gate, "comfyui", alias, 0,
                              label=f"knowledge figures: {doc.doc_id}", holder=HOLDER):
            leased_at = datetime.now().astimezone()
            descriptions = kp.describe_figures(extraction, lang, model=model, timings=timings)
    else:
        # An online model is not on this machine's card: no lease is taken.
        leased_at = None
        descriptions = kp.describe_figures(extraction, lang, model=model, timings=timings)
    ended = datetime.now().astimezone()
    by_seq = {f.seq: f.image for f in extraction.figures()}
    record = {
        "doc_id": doc.doc_id, "model": model, "lang": lang,
        "requested_at": started.isoformat(timespec="seconds"),
        "leased_at": leased_at.isoformat(timespec="seconds") if leased_at else None,
        "ended_at": ended.isoformat(timespec="seconds"),
        "call_seconds": round(sum(t["seconds"] for t in timings), 2),
        "timings": timings,
        "descriptions": {by_seq[seq]: text for seq, text in descriptions.items()},
        "image_sha256": _image_digests(extraction),
        "prompt_sha256": _prompt_digests(extraction, lang),
    }
    kept_path = figures_cache(blocks_json, doc.doc_id)
    if keep:
        target = kept_path
    else:
        target = a.out / "figures" / f"{doc.doc_id}.figures.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        kept = json.loads(kept_path.read_text(encoding="utf-8")) if kept_path.is_file() else {}
        target.with_name(f"{doc.doc_id}.compare.md").write_text(
            compare_figures(doc, extraction, kept, record), encoding="utf-8")
    target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    span = (f"lease {record['leased_at']}" if leased_at
            else f"online, no lease, {record['requested_at']}")
    log(f"  figures: {len(descriptions)} of {len(extraction.figures_to_describe())} described "
        f"with {model} ({lang}) into {target}; {span} to "
        f"{record['ended_at']}, {record['call_seconds']} s in calls")
    return {k: record[k] for k in ("model", "lang", "requested_at", "leased_at",
                                    "ended_at", "call_seconds")}


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def plan_totals(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The totals of a dry run over the documents planned."""
    planned = [s for s in summaries if "plan" in s]
    keys = ("llm_calls", "revision_calls_max", "llm_input_chars_max", "review_calls",
            "review_repair_calls_max", "review_input_chars_max", "image_calls", "image_bytes")
    totals: Dict[str, Any] = {k: sum(s["plan"]["totals"][k] for s in planned) for k in keys}
    totals.update({
        "documents": len(planned),
        "pages": sum(s["pages"] for s in planned),
        "units": sum(len(s["plan"]["units"]) for s in planned),
        "figures": sum(s["figures_exported"] for s in planned),
        "integrity_gaps": sum(len(s["integrity"].get("gaps") or []) for s in planned),
        "integrity_unrepaired": sum(len(s["integrity"].get("unrepaired") or []) for s in planned),
    })
    return totals


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true",
                   help="extraction, integrity, units and the call plan; no model call")
    p.add_argument("--source-root", type=Path, default=Path(config.KNOWLEDGE_SOURCE_ROOT))
    p.add_argument("--tsv", type=Path, help=f"transfer table (default <source-root>/{TABLE_NAME})")
    p.add_argument("--doc-id", action="append", help="repeatable")
    p.add_argument("--tier")
    p.add_argument("--bereich")
    p.add_argument("--max-pages", type=int, default=0,
                   help="only documents with at most this many PDF pages (DOCX: 0 pages)")
    p.add_argument("--source", type=Path, help="one explicit source file, PDF or DOCX (with one --doc-id)")
    p.add_argument("--work-root", type=Path, default=Path(config.KNOWLEDGE_WORK_ROOT))
    p.add_argument("--re-extract", action="store_true", help="run Docling even if an extraction exists")
    p.add_argument("--out", type=Path,
                   help="run folder: plan/, state/, logs/, condensed/ (default <work-root>/run)")
    p.add_argument("--write-library", action="store_true",
                   help="write the condensations into the library location of their tier "
                        "instead of <out>/condensed")
    p.add_argument("--force", action="store_true",
                   help="process documents that are already done (or planned, in a dry run)")
    p.add_argument("--max-calls", type=int, default=0,
                   help="stop before the LLM call that would pass this many calls in the run")
    p.add_argument("--max-tokens", type=int, default=0,
                   help="stop before the next LLM call once the run's calls have used this many "
                        "input plus output tokens (from the usage ledger)")
    p.add_argument("--ledger", type=Path, help="usage ledger (default: the platform's api_usage.jsonl)")
    p.add_argument("--doc-type", help="document type for every selected document instead of the "
                                      "type call (a key of knowledge_processing.DOC_TYPES)")
    p.add_argument("--lang", help="write the condensation in this language instead of the "
                                  "source's")
    p.add_argument("--workers", type=int, default=1, help="summary and review calls at once")
    p.add_argument("--describe-figures", action="store_true",
                   help="describe the figures the screening keeps with the image model "
                        "(--image-model; a local model loads the GPU card, under a lease of the "
                        "DevServer's gate) and keep them in <doc_id>.figures.json beside the "
                        "extraction. Without it a run takes the descriptions kept there, and "
                        "figures without one stay pending")
    p.add_argument("--figures-only", action="store_true",
                   help="describe the figures and stop, no LLM call. Alone: write the "
                        "descriptions to <out>/figures/ beside the kept ones (<doc_id>.compare.md) "
                        "and touch nothing else; with --describe-figures: keep them beside the "
                        "extraction. Language: --lang, else the sprache of the condensation under "
                        "--out, else the lang of the kept descriptions")
    p.add_argument("--review-only", action="store_true",
                   help="review the condensation under <out>/condensed/ with --model and "
                        "--reasoning-effort, unchanged; the verdict goes to "
                        "<out>/review/<reviewer>/<doc_id>.json")
    p.add_argument("--image-model", help="default KNOWLEDGE_IMAGE_MODEL, else the condensing model "
                                         "(--model, else KNOWLEDGE_PROCESSING_MODEL) where Settings "
                                         "measured it reading images, else IMAGE_ANALYSIS_MODEL "
                                         "(knowledge_processing.figure_model)")
    p.add_argument("--gate", default=os.environ.get("AI4ARTSED_DEVSERVER_URL") or "http://127.0.0.1:17802",
                   help="the DevServer whose gate leases the card")
    p.add_argument("--settings", type=Path,
                   help="user_settings.json to run with (default: the devserver's own)")
    p.add_argument("--model", help="pin this model for every call, without the fallback chain "
                                   "(default: the role KNOWLEDGE_PROCESSING_MODEL with its chain)")
    p.add_argument("--reasoning-effort",
                   help="reasoning effort of the condensing model for this run, sent to an "
                        "OpenRouter candidate as {\"reasoning\": {\"effort\": ...}} and to a "
                        "pinned Mistral model that takes it as reasoning_effort "
                        "(knowledge_processing.reasoning_payload); \"\" sends nothing (default "
                        "KNOWLEDGE_REASONING_EFFORT)")
    p.add_argument("--prior-library", type=Path, action="append",
                   help="folder with earlier analyses to carry metadata from (repeatable; "
                        "default: the Tier-O and the Tier-F/R folders)")
    p.add_argument("--prior-index", type=Path,
                   help="knowledge index to read a licence from, read-only "
                        "(default KNOWLEDGE_INDEX_DB)")
    return p


def main(argv: Optional[list] = None) -> int:
    a = build_parser().parse_args(argv)
    from my_app import reload_user_settings
    reload_user_settings(a.settings)
    a.tsv = a.tsv or a.source_root / TABLE_NAME
    a.out = a.out or a.work_root / "run"
    a.prior_library = a.prior_library or [Path(config.KNOWLEDGE_TIER_O_DIR),
                                          Path(config.KNOWLEDGE_LIBRARY_DIR)]
    a.prior_index = a.prior_index or Path(config.KNOWLEDGE_INDEX_DB)
    docs = select_docs(a)
    if not docs:
        print("no document selected")
        return 1
    budget = Budget(a.max_calls, a.max_tokens, UsageLedger(a.ledger) if a.max_tokens else None)
    summaries: List[Dict[str, Any]] = []
    stopped = ""
    for d in docs:
        if not a.force:
            if a.review_only:
                if review_path(d.doc_id, a).is_file():
                    print(f"== {d.doc_id}: reviewed before by "
                          f"{reviewer_slug(a.model, a.reasoning_effort)}, skipped")
                    continue
            elif a.dry_run and (a.out / "plan" / f"{d.doc_id}.plan.json").is_file():
                summaries.append(json.loads((a.out / "plan" / f"{d.doc_id}.plan.json")
                                            .read_text(encoding="utf-8")))
                print(f"== {d.doc_id}: planned before, skipped")
                continue
            if not a.dry_run and not a.figures_only and not a.review_only \
                    and read_state(a.out, d.doc_id).get("state") == "done":
                print(f"== {d.doc_id}: done before, skipped")
                continue
        try:
            summaries.append(run_doc(d, a, budget))
        except CeilingReached as e:
            stopped = str(e)
            break
        except RuntimeError as e:      # Docling failed: this document only
            print(f"  ERROR: {e}")
            write_state(a.out, d.doc_id, state="failed", reason=str(e))
            summaries.append({"doc_id": d.doc_id, "error": str(e)})
    if a.dry_run:
        totals = plan_totals(summaries)
        (a.out / "plan").mkdir(parents=True, exist_ok=True)
        (a.out / "plan" / "totals.json").write_text(json.dumps(totals, indent=1), encoding="utf-8")
        print("totals: " + json.dumps(totals))
    else:
        print(f"LLM calls in this run: {budget.calls}")
    if stopped:
        print(f"run stopped: {stopped}")
        return 2
    return 1 if any("error" in s for s in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(main())
