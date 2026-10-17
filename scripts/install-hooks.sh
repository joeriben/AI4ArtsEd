#!/usr/bin/env bash
#
# Point this clone's git at the versioned hooks in scripts/git-hooks.
#
# The hooks are versioned so that every clone runs the same gates. Copying them into
# .git/hooks was the old instruction and it drifted: for four months the file in the
# repository and the file git actually ran held different gates, and a fresh clone
# installed neither. core.hooksPath cannot drift, because there is only one file.
#
# Run once per clone, from anywhere inside the working tree:
#   scripts/install-hooks.sh
set -euo pipefail

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "install-hooks: not inside a git repository" >&2
    exit 1
fi

REPO="$(git rev-parse --show-toplevel)"
HOOKS="scripts/git-hooks"

if [ ! -d "$REPO/$HOOKS" ]; then
    echo "install-hooks: $HOOKS is missing from $REPO" >&2
    exit 1
fi

chmod +x "$REPO/$HOOKS"/* 2>/dev/null || true
git config core.hooksPath "$HOOKS"

echo "install-hooks: core.hooksPath = $(git config core.hooksPath)"
echo "install-hooks: git will now run the gates in $REPO/$HOOKS"
echo ""
echo "A hook copied into .git/hooks earlier is now dead: core.hooksPath replaces that"
echo "directory rather than adding to it. Nothing was deleted."
