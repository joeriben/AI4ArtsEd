#!/usr/bin/env python3
"""
Fail-closed runtime guard for the supported Transformers version.

AI4ArtsEd currently allows exactly one validated Transformers release in the
main venv: 4.57.6. The previously tested 4.57.0 release is yanked on PyPI and
must never be accepted. The 5.x line is also blocked for now because isolated
tests exposed a Wan/offline-cache regression.
"""

from __future__ import annotations

import sys


SUPPORTED_VERSION = "4.57.6"
BLOCKED_VERSIONS = {
    "4.57.0": "PyPI yanked release; rejected for deployment.",
}


def main() -> int:
    try:
        import transformers
    except Exception as exc:
        print(f"ERROR: failed to import transformers: {exc}", file=sys.stderr)
        return 1

    version = transformers.__version__

    if version in BLOCKED_VERSIONS:
        print(
            "ERROR: unsupported transformers version "
            f"{version}: {BLOCKED_VERSIONS[version]}",
            file=sys.stderr,
        )
        return 1

    if version != SUPPORTED_VERSION:
        print(
            "ERROR: unsupported transformers version "
            f"{version}; expected exactly {SUPPORTED_VERSION}.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: transformers runtime pinned to validated version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
