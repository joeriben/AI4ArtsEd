#!/usr/bin/env python3
"""List, and on request remove, the stored full texts of library documents.

Runs in the devserver venv. By default it only lists: for every library file
with something stored in the roots, what is stored, the licence class, the
state of the checks and of the adversarial review, and whether it would be
removed. Nothing is removed without --apply.

A full text is removed when the licence field names no Creative Commons
licence, the checks passed and an adversarial review is recorded as passed
(my_app/services/knowledge_retention.py). CC texts keep their full text.

USAGE
    venv/bin/python devserver/scripts/knowledge_retention.py            # list
    ... --json                                                          # list as JSON
    ... --record-review <doc_id> --reviewer NAME [--review-failed] [--note TEXT]
    ... --apply                                                         # remove

Roots (each a parameter, defaults from config.py):
    --source-root    source PDFs        (KNOWLEDGE_SOURCE_ROOT)
    --work-root      extraction output  (KNOWLEDGE_WORK_ROOT)
    --originals-dir  operator uploads   (KNOWLEDGE_ORIGINALS_DIR)
    --library-dir    library files, repeatable (KNOWLEDGE_TIER_O_DIR and
                     KNOWLEDGE_LIBRARY_DIR)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

DEVSERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVSERVER))

import config  # noqa: E402
from my_app.services import knowledge_checks  # noqa: E402
from my_app.services import knowledge_retention as kr  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source-root", type=Path, default=Path(config.KNOWLEDGE_SOURCE_ROOT))
    p.add_argument("--work-root", type=Path, default=Path(config.KNOWLEDGE_WORK_ROOT))
    p.add_argument("--originals-dir", type=Path, default=Path(config.KNOWLEDGE_ORIGINALS_DIR))
    p.add_argument("--library-dir", type=Path, action="append",
                   help="library folder (repeatable; default: Tier-O and Tier-F folders)")
    p.add_argument("--json", action="store_true", help="print the plan as JSON")
    p.add_argument("--apply", action="store_true",
                   help="REMOVE what the plan marks 'remove' (default: list only)")
    p.add_argument("--record-review", metavar="DOC_ID",
                   help="record an adversarial review for this document and exit")
    p.add_argument("--reviewer", default="")
    p.add_argument("--review-failed", action="store_true")
    p.add_argument("--note", default="")
    return p


def _library_dirs(a: argparse.Namespace) -> List[Path]:
    return a.library_dir or [Path(config.KNOWLEDGE_TIER_O_DIR), Path(config.KNOWLEDGE_LIBRARY_DIR)]


def _record_review(a: argparse.Namespace) -> int:
    if not a.reviewer.strip():
        print("--record-review needs --reviewer")
        return 2
    for lib in _library_dirs(a):
        for md in Path(lib).rglob(a.record_review + ".md"):
            side = knowledge_checks.sidecar_path(md)
            try:
                review = knowledge_checks.record_review(
                    side, passed=not a.review_failed, reviewer=a.reviewer.strip(), note=a.note)
            except FileNotFoundError as e:
                print(str(e))
                return 1
            print(f"review recorded in {side}: {review}")
            return 0
    print(f"no library file {a.record_review}.md in {[str(d) for d in _library_dirs(a)]}")
    return 1


def main(argv: Optional[list] = None) -> int:
    a = build_parser().parse_args(argv)
    if a.record_review:
        return _record_review(a)
    plan = kr.plan_retention(_library_dirs(a), source_root=a.source_root,
                             work_root=a.work_root, originals_dir=a.originals_dir)
    if a.json:
        print(json.dumps([i.to_dict() for i in plan], ensure_ascii=False, indent=1))
    else:
        for i in plan:
            print(f"[{i.action.upper():6}] {i.doc_id}  ({i.reason})")
            for p in i.paths:
                print(f"           {p}")
        n = sum(1 for i in plan if i.action == "remove")
        print(f"{n} of {len(plan)} documents marked for removal"
              + ("" if a.apply else " (list only; nothing removed without --apply)"))
    if not a.apply:
        return 0
    for line in kr.apply_plan(plan, [a.source_root, a.work_root, a.originals_dir]):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
