#!/usr/bin/env bash
#
# Write the public subset of this repository into another checkout as one commit.
#
#   scripts/public_export/export.sh <target-checkout> [<ref>]
#
# <target-checkout> is a git working tree (the public repository); <ref> is the
# commit to export, default HEAD. The target's tracked files are replaced by the
# public files of <ref> (scripts/public_export/exclude.txt decides which), the
# i18n work-order file is cut to its pending section, and the result is
# committed in the target. Nothing is pushed.
set -euo pipefail

TARGET="${1:?usage: export.sh <target-checkout> [<ref>]}"
REF="${2:-HEAD}"
REPO="$(git rev-parse --show-toplevel)"
PY="$(command -v python3)"

git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null
if [ -n "$(git -C "$TARGET" status --porcelain)" ]; then
    echo "export: the target checkout has uncommitted changes" >&2
    exit 1
fi

SHA="$(git -C "$REPO" rev-parse --short "$REF")"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/public-export.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

git -C "$REPO" archive --format=tar "$REF" | tar -x -C "$TMP"
"$PY" "$REPO/scripts/public_export/public_files.py" --prune "$TMP"
if [ -f "$TMP/public/ai4artsed-frontend/src/i18n/WORK_ORDERS.md" ]; then
    "$PY" "$REPO/scripts/public_export/public_files.py" --trim-work-orders \
        "$TMP/public/ai4artsed-frontend/src/i18n/WORK_ORDERS.md"
fi

# The checks that guard the public surface run on the exported tree itself.
(cd "$TMP" && "$PY" devserver/tests/test_public_surface_clean.py --tree "$TMP")

(cd "$TARGET" && git ls-files -z | xargs -0 rm -f \
    && find . -mindepth 1 -type d -empty -not -path './.git' -not -path './.git/*' -delete)
cp -a "$TMP"/. "$TARGET"/
(cd "$TARGET" && git add -A && git commit -q -m "Export of ${SHA}")
echo "export: committed the public files of ${SHA} in ${TARGET}"
