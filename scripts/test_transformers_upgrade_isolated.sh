#!/usr/bin/env bash
set -euo pipefail

# Isolated upgrade test for Hugging Face Transformers.
#
# Purpose:
# - keep the main AI4ArtsEd venv untouched
# - start from a faithful copy of the currently working main venv
# - upgrade only transformers-related packages in that copy
# - run import-level smoke checks against the productively used classes
#
# Usage:
#   bash scripts/test_transformers_upgrade_isolated.sh
#   TEST_VENV=.venv-transformers-upgrade TEST_TRANSFORMERS_SPEC='git+https://github.com/huggingface/transformers.git' \
#     bash scripts/test_transformers_upgrade_isolated.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_VENV="${TEST_VENV:-$ROOT_DIR/.venv-transformers-upgrade}"
SOURCE_VENV="${SOURCE_VENV:-$ROOT_DIR/venv}"
TEST_TRANSFORMERS_SPEC="${TEST_TRANSFORMERS_SPEC:-transformers==4.57.6}"

echo "=== AI4ArtsEd isolated Transformers upgrade test ==="
echo "Root: $ROOT_DIR"
echo "Test venv: $TEST_VENV"
echo "Source venv: $SOURCE_VENV"
echo "Target transformers spec: $TEST_TRANSFORMERS_SPEC"
echo

if [[ ! -x "$SOURCE_VENV/bin/python" ]]; then
  echo "ERROR: source venv not found or missing python: $SOURCE_VENV"
  exit 1
fi

rm -rf "$TEST_VENV"
cp -a "$SOURCE_VENV" "$TEST_VENV"

source "$TEST_VENV/bin/activate"

python -m pip install --upgrade pip

echo
echo "[1/3] Baseline copied from working main venv"
python - <<'PY'
import torch, transformers
print(f'baseline torch={torch.__version__}')
print(f'baseline transformers={transformers.__version__}')
PY

echo
echo "[2/3] Overriding transformers-related packages in isolated venv..."
if [[ "$TEST_TRANSFORMERS_SPEC" == git+* ]]; then
  python -m pip install --upgrade "$TEST_TRANSFORMERS_SPEC"
else
  python -m pip install --upgrade "$TEST_TRANSFORMERS_SPEC"
fi

echo
echo "[3/3] Running smoke checks..."
cd "$ROOT_DIR"
python "$ROOT_DIR/devserver/testfiles/test_transformers_upgrade_smoke.py"

echo
echo "Done. Main venv was not modified."
