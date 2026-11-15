"""Retention of the library's source texts (raw text, blocks, figures, PDF).

A condensation is made from the full text of its source. For a document whose
licence is a Creative Commons licence (UNESCO's CC BY-SA IGO titles, CC BY
papers) the full text may stay. For every other document the full text is
temporary: once the condensation has passed the checks (knowledge_checks,
`passed` in `<doc_id>.checks.json`) and an adversarial review has been
recorded as passed (`review.passed` in the same sidecar, written by
knowledge_checks.record_review), its PDF and its extraction intermediates are
removed.

The licence class comes from the licence field (`lizenz`) of the library
file's front matter and nothing else. An empty field is not a CC licence.

`plan_retention` only looks; `apply_plan` removes, and only what the plan
marked `remove`, and only inside the roots it was given. The script
scripts/knowledge_retention.py lists by default and removes only with
`--apply`.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from my_app.services import knowledge_checks

# What belongs to a document in a root, by file name.
_INTERMEDIATE_SUFFIXES = (".raw.md", ".blocks.json", ".figures")
_SOURCE_SUFFIXES = (".pdf",)

_CC_RE = re.compile(r"\bCC(?:0|[\s-]+(?:BY|ZERO)\b|\s*$)|creative\s+commons", re.IGNORECASE)
_FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def licence_class(lizenz: str) -> str:
    """'cc' for a Creative Commons licence, else 'restricted'."""
    return "cc" if _CC_RE.search(lizenz or "") else "restricted"


def _front_scalar(md: str, key: str) -> str:
    m = _FRONT_RE.match(md)
    if not m:
        return ""
    k = re.search(r"(?m)^" + re.escape(key) + r":\s*(.*)$", m.group(1))
    if not k:
        return ""
    v = k.group(1).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v.strip()


@dataclass
class RetentionItem:
    doc_id: str
    library_file: Optional[Path]
    lizenz: str
    licence_class: str
    checks_passed: bool
    review_passed: bool
    action: str                     # "remove" | "keep"
    reason: str
    paths: List[Path] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "library_file": str(self.library_file) if self.library_file else "",
            "lizenz": self.lizenz, "licence_class": self.licence_class,
            "checks_passed": self.checks_passed, "review_passed": self.review_passed,
            "action": self.action, "reason": self.reason,
            "paths": [str(p) for p in self.paths],
        }


def _doc_id_of(name: str, suffixes: Sequence[str]) -> Optional[str]:
    for s in suffixes:
        if name.endswith(s) and len(name) > len(s):
            return name[: -len(s)]
    return None


def _index_root(root: Optional[Path], suffixes: Sequence[str]) -> Dict[str, List[Path]]:
    """doc_id -> the files/folders under `root` that carry it, by name."""
    out: Dict[str, List[Path]] = {}
    if root is None or not Path(root).is_dir():
        return out
    for p in sorted(Path(root).rglob("*")):
        doc_id = _doc_id_of(p.name, suffixes)
        if doc_id is None:
            continue
        if any(parent.name.endswith(".figures") for parent in p.parents):
            continue            # a figure inside a figures folder
        out.setdefault(doc_id, []).append(p)
    return out


def plan_retention(library_dirs: Iterable[Path], *, source_root: Optional[Path],
                   work_root: Optional[Path], originals_dir: Optional[Path]
                   ) -> List[RetentionItem]:
    """One item per library file that has something stored in the roots, and
    one per orphaned intermediate in the work root (kept: no library file
    decides about it)."""
    sources = _index_root(source_root, _SOURCE_SUFFIXES)
    work = _index_root(work_root, _INTERMEDIATE_SUFFIXES)
    originals = _index_root(originals_dir, _INTERMEDIATE_SUFFIXES + _SOURCE_SUFFIXES)

    items: List[RetentionItem] = []
    seen: set = set()
    for lib in library_dirs:
        if not Path(lib).is_dir():
            continue
        for md in sorted(Path(lib).rglob("*.md")):
            if md.name.endswith(".raw.md"):
                continue
            text = md.read_text(encoding="utf-8", errors="replace")
            doc_id = _front_scalar(text, "id") or md.stem
            if doc_id in seen:
                continue
            paths = sources.get(doc_id, []) + work.get(doc_id, []) + originals.get(doc_id, [])
            if not paths:
                continue
            seen.add(doc_id)
            lizenz = _front_scalar(text, "lizenz")
            cls = licence_class(lizenz)
            side = knowledge_checks.read_sidecar(knowledge_checks.sidecar_path(md)) or {}
            checks_ok = bool(side.get("passed"))
            review_ok = bool((side.get("review") or {}).get("passed"))
            if cls == "cc":
                action, reason = "keep", f"CC licence ({lizenz}): the full text may stay"
            elif not side:
                action, reason = "keep", "no checks sidecar: not condensed by the current stage"
            elif not checks_ok:
                action, reason = "keep", "checks not passed"
            elif not review_ok:
                action, reason = "keep", "no passed adversarial review recorded"
            else:
                action = "remove"
                reason = (f"licence {lizenz!r} is not CC; checks and review passed"
                          if lizenz else "no licence given; checks and review passed")
            items.append(RetentionItem(doc_id, md, lizenz, cls, checks_ok, review_ok,
                                       action, reason, paths))

    for doc_id, paths in sorted(work.items()):
        if doc_id not in seen:
            items.append(RetentionItem(doc_id, None, "", "", False, False, "keep",
                                       "no library file for these intermediates", paths))
    return items


def apply_plan(items: Iterable[RetentionItem], roots: Iterable[Optional[Path]]) -> List[str]:
    """Remove the paths of every item marked `remove`. A path outside the given
    roots is refused, never removed. Returns one log line per path."""
    allowed = [Path(r).resolve() for r in roots if r is not None]
    log: List[str] = []
    for item in items:
        if item.action != "remove":
            continue
        for p in item.paths:
            rp = Path(p).resolve()
            if not any(rp.is_relative_to(a) for a in allowed):
                log.append(f"REFUSED (outside the roots): {p}")
                continue
            try:
                if rp.is_dir():
                    shutil.rmtree(rp)
                elif rp.exists():
                    rp.unlink()
                log.append(f"removed: {p}")
            except OSError as e:
                log.append(f"FAILED: {p}: {e}")
    return log
