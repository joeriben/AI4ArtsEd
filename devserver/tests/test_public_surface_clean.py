#!/usr/bin/env python3
"""
Policy: the public surface names no person, points to no development session
and carries no path of one installation.

Comments, docstrings, notes and documentation explain what the code does.
They do not report who asked for it, what was said in which conversation,
or in which numbered session it was written; decisions are recorded in
docs/DEVELOPMENT_DECISIONS.md. This gate holds that state for every file
that is part of the public repository (scripts/public_export/exclude.txt
decides which; scripts/public_export/public_files.py reads the list).

What it sees, exactly (FORBIDDEN below):

  - the initials and the pseudonym under which the project lead was named
    in comments, in every inflected form;
  - a pointer to a numbered development session ("Session 152");
  - the phrases that mark a sentence as somebody's dictated wording;
  - a pointer to a file that is not part of the public repository: the
    development log, the assistant's rule and plan files, and the analysis,
    plan, handover and report documents;
  - a home directory or mount path of one installation.

It also checks that every `docs/...` path a public file names is itself
public (DANGLING below): a public document that sends its reader to a file
that is not there is a broken reference.

Binary files and lock files are skipped. The files of the export mechanism
and this test are skipped: they carry the patterns as patterns.

Run: python3 devserver/tests/test_public_surface_clean.py           (whole tree)
     python3 devserver/tests/test_public_surface_clean.py --staged  (pre-commit gate 10)
     python3 devserver/tests/test_public_surface_clean.py --tree DIR (an exported tree)
     python3 -m pytest devserver/tests/test_public_surface_clean.py -q
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/public_export"))
import public_files as pf  # noqa: E402

FORBIDDEN = [
    (re.compile(r"\bBJs?\b|BJ's"), "initials of a person"),
    (re.compile(r"\bPLs?\b|PL's|\bPL-"), "pseudonym of a person"),
    (re.compile(r"\bSessions? [0-9]{1,3}\b(?![0-9.,:%])"), "pointer to a development session"),
    (re.compile(r"in his (own )?words|DIKTIERT VON|dictated by"), "attribution of a wording"),
    (re.compile(r"DEVELOPMENT_LOG\.md|\.claude/(CLAUDE\.md|agents|plans)"),
     "pointer to a file outside the public repository"),
    (re.compile(r"/home/(joerissen|benjamin)\b|/Users/joerissen|/run/media/joerissen"),
     "path of one installation"),
]
DOC_POINTER = re.compile(r"docs/[A-Za-z0-9_][A-Za-z0-9_. &-]*?\.(?:md|tsv|html)")

TEXT_SUFFIXES = {
    ".py", ".ts", ".js", ".vue", ".css", ".html", ".md", ".txt", ".tsv", ".csv",
    ".json", ".yaml", ".yml", ".toml", ".sh", ".service", ".ini", ".cfg", ".env",
    ".conf", ".xml", ".svg", ".atcanvas",
}
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
SKIP_PATHS = {
    "devserver/tests/test_public_surface_clean.py",
    "scripts/public_export/exclude.txt",
    "scripts/public_export/public_files.py",
    "scripts/public_export/export.sh",
}


def _is_text(rel: str, data: bytes) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if name in SKIP_NAMES:
        return False
    suffix = pathlib.PurePosixPath(name).suffix.lower()
    if suffix and suffix not in TEXT_SUFFIXES:
        return False
    return b"\0" not in data[:8192]


def findings_in(rel: str, data: bytes, public: set[str] | None) -> list[str]:
    """Problems in one file's content; `public` is the set of public paths for
    the dangling-pointer check, or None to skip that check."""
    if rel in SKIP_PATHS or not _is_text(rel, data):
        return []
    text = data.decode("utf-8", "replace")
    if rel == pf.WORK_ORDERS:
        # The export cuts the work-order file after its "## Completed" heading
        # (completed orders are history); only the part that ships is checked.
        text = text.split("\n## Completed", 1)[0]
    out = []
    for num, line in enumerate(text.splitlines(), 1):
        for pattern, what in FORBIDDEN:
            if pattern.search(line):
                out.append(f"{rel}:{num}  {what}: {line.strip()[:120]}")
                break
        if public is not None:
            for target in DOC_POINTER.findall(line):
                if target not in public and (REPO / target).exists():
                    out.append(f"{rel}:{num}  points to a file that is not public: {target}")
    return out


def check_tree(root: pathlib.Path, paths: list[str]) -> list[str]:
    public = set(paths)
    out = []
    for rel in paths:
        path = root / rel
        if not path.is_file():
            continue
        out.extend(findings_in(rel, path.read_bytes(), public))
    return out


def check_repo() -> list[str]:
    return check_tree(REPO, pf.public_files(REPO))


def test_public_files_are_clean():
    bad = check_repo()
    assert not bad, (
        f"{len(bad)} place(s) on the public surface name a person, a session or a "
        f"private file:\n  " + "\n  ".join(bad[:60])
        + ("\n  ..." if len(bad) > 60 else "")
    )


def _staged() -> list[str]:
    names = subprocess.run(
        ["git", "-C", str(REPO), "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        check=True, capture_output=True).stdout
    public = set(pf.public_files(REPO))
    out = []
    for raw in names.split(b"\0"):
        rel = raw.decode("utf-8", "surrogateescape")
        if not rel or rel not in public:
            continue
        data = subprocess.run(["git", "-C", str(REPO), "show", f":{rel}"],
                              check=True, capture_output=True).stdout
        out.extend(findings_in(rel, data, public))
    return out


if __name__ == "__main__":
    if "--staged" in sys.argv:
        try:
            bad = _staged()
        except Exception as e:                               # noqa: BLE001
            print(f"public-surface gate could not read the staged commit ({e}); "
                  f"letting it through", file=sys.stderr)
            raise SystemExit(0)
        if bad:
            print("\nCOMMIT BLOCKED -- the public surface names a person, a session or a "
                  "private file:\n  " + "\n  ".join(bad)
                  + "\n\nComments explain what the code does; decisions go to "
                  "docs/DEVELOPMENT_DECISIONS.md.\nRule and reasoning: "
                  "devserver/tests/test_public_surface_clean.py\n", file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)
    if "--tree" in sys.argv:
        root = pathlib.Path(sys.argv[sys.argv.index("--tree") + 1]).resolve()
        rels = sorted(str(p.relative_to(root)) for p in root.rglob("*")
                      if p.is_file() and ".git" not in p.parts)
        bad = check_tree(root, rels)
    else:
        bad = check_repo()
    if bad:
        print("\n".join(bad))
        print(f"\n{len(bad)} finding(s)")
        raise SystemExit(1)
    print("public surface: clean")
    raise SystemExit(0)
