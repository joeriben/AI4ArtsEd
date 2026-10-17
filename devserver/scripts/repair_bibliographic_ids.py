#!/usr/bin/env python3
"""
Repair the bibliographic front-matter of existing Tier-O knowledge files.

The problem (2026-07-05): the compact library files under
exports/knowledge_library/ frequently carry a WRONG `titel:` — not the work's
title but whatever surface line Docling put first: an author byline
("Ernst wAgnEr"), a journal/series masthead ("IJRCAAE"), or a chapter/section
heading of a book excerpt ("Künstlerische Strategien"). `autor:` is almost
always empty. Since the texts are being read anyway, the operator asked for the
`titel` fields to carry the REAL titles so the inventory is controllable.

This script re-derives the bibliography for each Tier-O document by running the
SAME identifier the live ingest uses (knowledge_processing.identify_bibliographic)
over the document's RAW Docling Markdown (resources/knowledge_originals/operator/
<doc_id>.raw.md) plus its operator imprint note (the `hinweis:` front-matter,
the richest bibliographic signal). It then updates ONLY the front-matter fields
titel / autor / jahr / quelle via the Tier-O curation rewrite
(knowledge_library.set_operator_meta). The PROFIL / WISSEN / GLOSSAR body is left
BYTE-FOR-BYTE untouched — this is a metadata repair, not a re-Verdichtung.

Do-no-harm heuristic (avoid clobbering an already-good title): if the EXISTING
title is plausible (non-empty, not ≈ the doc_id/filename, not on the known-bad
list) AND the identifier reports confidence "low", the document is SKIPPED (kept
as-is). A high-confidence identification always applies; a blank/known-bad title
is always replaced when the identifier found one.

Batch discipline (hard rule): run the PILOT first (--doc art105413), verify the
result against the raw title page yourself, and only then run the corpus.

USAGE:
    # pilot one document, no writes:
    python3 devserver/scripts/repair_bibliographic_ids.py --doc art105413 --dry-run
    # pilot one document, write it:
    python3 devserver/scripts/repair_bibliographic_ids.py --doc art105413
    # dry-run over the whole Tier-O corpus (plan table, no writes, no reindex):
    python3 devserver/scripts/repair_bibliographic_ids.py --dry-run
    # real run over the corpus + ONE reindex at the end:
    python3 devserver/scripts/repair_bibliographic_ids.py

Runs in the devserver venv (it uses the platform's own provider routing for the
LLM, role KNOWLEDGE_PROCESSING_MODEL). It hits real providers — mind the
Ein-Dokument-Gate.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# devserver/scripts/repair_bibliographic_ids.py -> parents[1] == devserver/;
# put devserver/ on sys.path so `import config` and `from my_app…` resolve, the
# same way the offline scripts and the in-process ingest do.
_DEVSERVER_DIR = Path(__file__).resolve().parents[1]
if str(_DEVSERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_DEVSERVER_DIR))

logging.basicConfig(level=logging.INFO,
                    format="[repair-biblio] %(levelname)s %(message)s")
logger = logging.getLogger("repair_bibliographic_ids")


# ---------------------------------------------------------------------------
# Known-bad title inventory (the fault cases erhoben 2026-07-05). A title on this
# list is treated as definitely wrong, so it is replaced whenever the identifier
# found ANY title (even at low confidence). Matched case-insensitively on the
# stripped title. Titles NOT on this list are protected by the plausibility +
# confidence heuristic instead.
# ---------------------------------------------------------------------------
_KNOWN_BAD_TITLES = {
    "ernst wagner",                       # art105413 — author byline
    "ijrcaae",                            # aug100500 — journal masthead
    "künstlerische strategien",           # oa…-3-48 — chapter heading
    "gute praxis im porträt analyse und empfehlungen gelebter bildungsarbeit",  # holz — chapter head
    "5 gemeine durchschnittsbilder",      # steyerl — chapter heading
    "fünfter qualitätsbereich der raum",  # oa…-67-97 — chapter heading
    # a whole question as a title (oa…-49-66) — matched by the '?' heuristic too
    "welche rolle spielt der faktor beziehung und durch welche aspekte wird diese beziehung beeinflusst?",
}


def _norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip()).lower()


def _looks_like_doc_id(title: str, doc_id: str) -> bool:
    """True if the title is essentially the doc_id/filename slug (kebab or
    space-joined), i.e. the title fell back to the filename at upload."""
    def _slug(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (s or "").lower())
    ts, ds = _slug(title), _slug(doc_id)
    if not ts:
        return True
    # doc_id slug often carries a trailing -2 dedupe suffix and a year; a title
    # that is a prefix of the id slug (or vice versa) is filename-derived.
    return ts == ds or ts in ds or ds in ts


def _title_is_plausible(title: str, doc_id: str) -> bool:
    """A heuristic 'this existing title looks like a real work title'. Used only
    to DECIDE whether a low-confidence identification may overwrite it. Plausible
    = non-empty, not the doc_id/filename, not a known-bad title, not a bare
    question (a '?'-ending single sentence is a chapter subhead, not a title)."""
    t = (title or "").strip()
    if not t:
        return False
    if _norm_title(t) in _KNOWN_BAD_TITLES:
        return False
    if _looks_like_doc_id(t, doc_id):
        return False
    if t.endswith("?"):
        return False
    return True


# ---------------------------------------------------------------------------
# Plan for one document
# ---------------------------------------------------------------------------

class RepairPlan:
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.old: Dict[str, str] = {}
        self.new: Dict[str, str] = {}
        self.changes: Dict[str, object] = {}   # only the fields that would change
        self.action = "pending"                # updated | skipped | no-raw | no-id | error
        self.reason = ""
        self.confidence = ""


def _raw_md_path(doc_id: str) -> Path:
    from config import KNOWLEDGE_ORIGINALS_DIR
    return Path(KNOWLEDGE_ORIGINALS_DIR) / "operator" / f"{doc_id}.raw.md"


def _plan_document(doc_id: str) -> RepairPlan:
    """Build the repair plan for ONE Tier-O document (no writes). Reads the
    current front-matter (for the old values + the hinweis signal), locates the
    raw.md, runs identify_bibliographic, applies the do-no-harm heuristic, and
    records exactly which of titel/autor/jahr/quelle would change."""
    from my_app.services import knowledge_library as kl
    from my_app.services import knowledge_processing as kp

    plan = RepairPlan(doc_id)
    item = kl.get_operator_item(doc_id)
    if item is None:
        plan.action = "error"
        plan.reason = "not a Tier-O item (no export md)"
        return plan
    plan.old = {
        "titel": str(item.get("titel", "") or ""),
        "autor": str(item.get("autor", "") or ""),
        "jahr": str(item.get("jahr", "") or ""),
        "quelle": str(item.get("quelle", "") or ""),
    }
    hinweis = str(item.get("hinweis", "") or "")

    raw_path = _raw_md_path(doc_id)
    if not raw_path.exists():
        plan.action = "no-raw"
        plan.reason = f"raw markdown not found at {raw_path}"
        return plan
    try:
        raw_md = raw_path.read_text(encoding="utf-8")
    except OSError as e:
        plan.action = "error"
        plan.reason = f"could not read raw markdown: {e}"
        return plan

    rec = kp.identify_bibliographic(raw_md, hinweis=hinweis, doc_id=doc_id)
    plan.confidence = rec.confidence

    identified_title = rec.composed_titel
    existing_plausible = _title_is_plausible(plan.old["titel"], doc_id)

    # --- titel: replace when the identifier found a title AND either the existing
    # title is NOT plausible (blank / filename / known-bad / bare question) OR the
    # identifier is confident. A plausible existing title + low confidence -> keep.
    if identified_title:
        if not existing_plausible or rec.confidence == "high":
            if identified_title.strip() != plan.old["titel"].strip():
                plan.changes["titel"] = identified_title
        # else: plausible existing title + low confidence -> leave titel as-is.

    # --- autor: fill only when currently blank and the identifier found authors
    # (never overwrite an operator-provided author).
    if not plan.old["autor"].strip() and rec.autoren_str:
        plan.changes["autor"] = rec.autoren_str

    # --- jahr: fill only when currently blank and a year was identified.
    if not plan.old["jahr"].strip() and rec.jahr:
        plan.changes["jahr"] = rec.jahr

    # --- quelle: fill only when currently blank and a source was identified.
    if not plan.old["quelle"].strip() and rec.quelle:
        plan.changes["quelle"] = rec.quelle

    if not plan.changes:
        plan.action = "skipped"
        if not identified_title and not (rec.autoren_str or rec.jahr or rec.quelle):
            plan.reason = "identifier found nothing usable"
        elif existing_plausible and rec.confidence == "low":
            plan.reason = "kept existing (plausible title, low confidence)"
        else:
            plan.reason = "no field would change"
    else:
        plan.action = "would-update"
        plan.reason = f"changes: {', '.join(sorted(plan.changes))}"
    return plan


def _apply(plan: RepairPlan) -> bool:
    """Write the planned front-matter changes for ONE document via the Tier-O
    curation rewrite (body untouched). Returns True on a write."""
    from my_app.services import knowledge_library as kl
    if not plan.changes:
        return False
    ok = kl.set_operator_meta(plan.doc_id, **plan.changes)
    plan.action = "updated" if ok else "error"
    if not ok:
        plan.reason = "set_operator_meta returned False (item vanished?)"
    return ok


# ---------------------------------------------------------------------------
# Corpus discovery + reporting
# ---------------------------------------------------------------------------

def _tier_o_doc_ids() -> List[str]:
    """All Tier-O export doc_ids (the .md stems under exports/knowledge_library/),
    sorted. This is the curation surface; drafts included."""
    from config import KNOWLEDGE_TIER_O_DIR
    d = Path(KNOWLEDGE_TIER_O_DIR)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.md"))


def _fmt_change(old: str, new: object) -> str:
    o = (old or "").strip() or "∅"
    return f"{o!r} -> {str(new)!r}"


def _print_report(plans: List[RepairPlan], *, dry_run: bool) -> None:
    updated = [p for p in plans if p.action in ("updated", "would-update")]
    skipped = [p for p in plans if p.action == "skipped"]
    no_raw = [p for p in plans if p.action == "no-raw"]
    errors = [p for p in plans if p.action in ("error", "no-id")]

    verb = "WOULD CHANGE" if dry_run else "CHANGED"
    print("\n" + "=" * 78)
    print(f"BIBLIOGRAPHIC REPAIR REPORT  ({'DRY-RUN' if dry_run else 'APPLIED'})")
    print("=" * 78)
    print(f"documents examined : {len(plans)}")
    print(f"{verb:<19}: {len(updated)}")
    print(f"skipped (kept)     : {len(skipped)}")
    print(f"raw.md missing     : {len(no_raw)}")
    print(f"errors             : {len(errors)}")

    if updated:
        print("\n--- " + verb + " ---")
        for p in updated:
            print(f"\n[{p.doc_id}]  (confidence={p.confidence})")
            for field in ("titel", "autor", "jahr", "quelle"):
                if field in p.changes:
                    print(f"    {field:<7}: {_fmt_change(p.old.get(field, ''), p.changes[field])}")

    if skipped:
        print("\n--- SKIPPED (kept existing) ---")
        for p in skipped:
            print(f"  [{p.doc_id}]  titel={p.old.get('titel','')!r}  "
                  f"(conf={p.confidence}) — {p.reason}")

    if no_raw:
        print("\n--- raw.md MISSING (cannot identify) ---")
        for p in no_raw:
            print(f"  [{p.doc_id}] — {p.reason}")

    if errors:
        print("\n--- ERRORS ---")
        for p in errors:
            print(f"  [{p.doc_id}] — {p.reason}")
    print()


def _reindex() -> int:
    """Rebuild the FTS index (build_knowledge_index.py, stdlib-only) so the
    repaired titles show in the inventory + search. Returns the return code."""
    import subprocess
    import os
    from config import (KNOWLEDGE_INDEX_PYTHON, KNOWLEDGE_INDEX_SCRIPT,
                        KNOWLEDGE_INDEX_DB, KNOWLEDGE_LIBRARY_DIR,
                        KNOWLEDGE_TIER_O_DIR, KNOWLEDGE_GLOSSARY_OVERRIDES)
    interp = Path(KNOWLEDGE_INDEX_PYTHON)
    if not interp.exists():
        logger.warning("index interpreter not found at %s — skipping reindex "
                       "(run build_knowledge_index.py manually).", interp)
        return 1
    cmd = [str(interp), str(KNOWLEDGE_INDEX_SCRIPT),
           "--db", str(KNOWLEDGE_INDEX_DB),
           "--library", str(KNOWLEDGE_LIBRARY_DIR),
           "--tier-o", str(KNOWLEDGE_TIER_O_DIR),
           "--glossary-overrides", str(KNOWLEDGE_GLOSSARY_OVERRIDES)]
    logger.info("reindex: %s", " ".join(cmd))
    proc = subprocess.run(cmd, env=os.environ.copy())
    return proc.returncode


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _bootstrap_settings() -> str:
    """Load user_settings.json into config (as create_app does at startup) so the
    KNOWLEDGE_PROCESSING_MODEL role resolves to the SAME model the live ingest
    uses (STAGE2_INTERCEPTION → … → CHAT_HELPER fallback). Returns the resolved
    model string for the log (empty if none could be resolved). Never raises."""
    try:
        from my_app import reload_user_settings
        reload_user_settings()
    except SystemExit:
        # reload_user_settings sys.exit(1)s when user_settings.json is missing;
        # surface that as a clear message rather than a bare traceback.
        logger.error("user_settings.json missing — the LLM model cannot be "
                     "resolved. Run from the configured devserver checkout.")
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning("could not load user settings (%s) — model may be unset.", e)
    import config
    try:
        return config.resolve_knowledge_processing_model()
    except Exception:  # noqa: BLE001
        return str(getattr(config, "KNOWLEDGE_PROCESSING_MODEL", "") or "")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Repair Tier-O bibliographic front-matter.")
    ap.add_argument("--doc", help="repair only this doc_id (the pilot gate)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show planned changes; write nothing, no reindex")
    ap.add_argument("--no-reindex", action="store_true",
                    help="apply changes but skip the final reindex")
    args = ap.parse_args(argv)

    model = _bootstrap_settings()
    logger.info("LLM (KNOWLEDGE_PROCESSING_MODEL) resolves to: %s", model or "(unset!)")

    if args.doc:
        doc_ids = [args.doc]
    else:
        doc_ids = _tier_o_doc_ids()
    if not doc_ids:
        logger.error("no Tier-O documents found (exports/knowledge_library/ empty?)")
        return 1

    logger.info("%s %d document(s)%s", "planning" if args.dry_run else "repairing",
                len(doc_ids), " [DRY-RUN]" if args.dry_run else "")

    plans: List[RepairPlan] = []
    for doc_id in doc_ids:
        logger.info("… %s", doc_id)
        try:
            plan = _plan_document(doc_id)
        except Exception as e:  # noqa: BLE001 - one bad doc must not sink the run
            logger.exception("planning failed for %s", doc_id)
            plan = RepairPlan(doc_id)
            plan.action = "error"
            plan.reason = f"exception: {e}"
        if not args.dry_run and plan.action == "would-update":
            try:
                _apply(plan)
            except Exception as e:  # noqa: BLE001
                logger.exception("apply failed for %s", doc_id)
                plan.action = "error"
                plan.reason = f"apply exception: {e}"
        plans.append(plan)

    _print_report(plans, dry_run=args.dry_run)

    wrote = any(p.action == "updated" for p in plans)
    if args.dry_run:
        logger.info("dry-run: nothing written, no reindex.")
    elif not wrote:
        logger.info("no documents changed — skipping reindex.")
    elif args.no_reindex:
        logger.info("--no-reindex: skipped the index rebuild (do it manually).")
    else:
        rc = _reindex()
        if rc != 0:
            logger.error("reindex failed (rc=%s).", rc)
            return rc

    errors = [p for p in plans if p.action in ("error", "no-id")]
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
