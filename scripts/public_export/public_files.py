#!/usr/bin/env python3
"""Which tracked files belong to the public repository.

The public repository is this repository minus the paths in
scripts/public_export/exclude.txt. This module is the one place that reads
that list: scripts/public_export/export.sh uses it to build the public tree,
and devserver/tests/test_public_surface_clean.py uses it to decide which
files it checks.

Usage:
    public_files.py              list the public files (git ls-files minus the list)
    public_files.py --excluded   list the tracked files the list removes
    public_files.py --prune DIR  delete the excluded paths under DIR, a copy of
                                 the repository tree
    public_files.py --trim-work-orders FILE
                                 cut src/i18n/WORK_ORDERS.md after the
                                 "## Completed" heading: completed orders are
                                 history, pending ones ship

Patterns: one per line, relative to the repository root, `#` starts a comment.
A trailing slash names a directory and everything under it. `*` matches
within one path segment, `**` across segments. A pattern without a wildcard
names one path exactly.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
EXCLUDE_FILE = REPO / "scripts/public_export/exclude.txt"
WORK_ORDERS = "public/ai4artsed-frontend/src/i18n/WORK_ORDERS.md"


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    directory = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
        else:
            out.append(re.escape(ch))
        i += 1
    body = "".join(out)
    return re.compile(f"^{body}(/.*)?$" if directory else f"^{body}$")


def load_patterns(path: pathlib.Path = EXCLUDE_FILE) -> list[re.Pattern[str]]:
    patterns = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(_pattern_regex(line))
    return patterns


_PATTERNS: list[re.Pattern[str]] | None = None


def is_public(rel_path: str) -> bool:
    """True when the repository-relative path is part of the public repository."""
    global _PATTERNS
    if _PATTERNS is None:
        _PATTERNS = load_patterns()
    return not any(p.match(rel_path) for p in _PATTERNS)


def tracked_files(repo: pathlib.Path = REPO) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"],
                         check=True, capture_output=True).stdout
    return [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]


def public_files(repo: pathlib.Path = REPO) -> list[str]:
    return [p for p in tracked_files(repo) if is_public(p)]


def excluded_files(repo: pathlib.Path = REPO) -> list[str]:
    return [p for p in tracked_files(repo) if not is_public(p)]


def prune(tree: pathlib.Path) -> int:
    """Delete every excluded path under `tree`, a copy of the repository tree."""
    removed = 0
    for rel in sorted((str(p.relative_to(tree)) for p in tree.rglob("*") if p.is_file()),
                      reverse=True):
        if not is_public(rel):
            (tree / rel).unlink()
            removed += 1
    for directory in sorted((p for p in tree.rglob("*") if p.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    return removed


def trim_work_orders(path: pathlib.Path) -> None:
    """Keep the header and the pending orders; completed orders are history."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\n") == "## Completed":
            path.write_text("".join(lines[: index + 1]) + "\n", encoding="utf-8")
            return


def main(argv: list[str]) -> int:
    if argv[1:2] == ["--excluded"]:
        print("\n".join(excluded_files()))
    elif argv[1:2] == ["--prune"]:
        print(f"removed {prune(pathlib.Path(argv[2]))} files")
    elif argv[1:2] == ["--trim-work-orders"]:
        trim_work_orders(pathlib.Path(argv[2]))
    else:
        print("\n".join(public_files()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
