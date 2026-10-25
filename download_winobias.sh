#!/bin/bash
# AI4ArtsEd DevServer - WinoBias downloader (Coreference Test)
#
# Fetches WinoBias: Zhao, Wang, Yatskar, Ordonez and Chang, "Gender Bias in
# Coreference Resolution: Evaluation and Debiasing Methods", NAACL 2018, 15-20.
# Released under the MIT licence at https://github.com/uclanlp/corefBias and read
# here through the mirror the datasets library keeps (uclanlp/wino_bias).
#
# 1,584 sentence pairs in two groups. Only the group whose grammar fixes the
# referent is used - 792 pairs, of which 777 pass the instrument's own check.
#
# The dataset is downloadable material and does not belong in the repository. It
# lands in the datasets cache (HF_HOME, by default ~/.cache/huggingface); the
# loader reads it from there and says "run download_winobias.sh" when it cannot.
#
# The sixty hand-vetted pairs the kids level runs on are NOT from here: they ship
# with the repository in devserver/config/winobias_curated.json and need no
# download at all.
#
# Idempotent: re-running is a no-op once the cache holds it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${SCRIPT_DIR}/venv/bin/python"
[ -x "${PY}" ] || PY="python3"

echo "Fetching WinoBias (uclanlp/wino_bias, configurations type2_pro and type2_anti)"

"${PY}" - <<'PYEOF'
from datasets import load_dataset

total = 0
for cfg in ("type2_pro", "type2_anti"):
    ds = load_dataset("uclanlp/wino_bias", cfg)
    for split in ds:
        total += len(ds[split])
        print(f"  {cfg:<12} {split:<12} {len(ds[split])} sentences")
print(f"  {'':<12} {'':<12} {total} in total")
PYEOF

echo
"${PY}" - <<'PYEOF'
import sys
from pathlib import Path
root = Path(__file__).resolve().parent if "__file__" in dir() else Path.cwd()
sys.path.insert(0, str(Path.cwd() / "devserver"))
try:
    from my_app.services import winobias_corpus as wb
    print(f"Checked and drawable: {len(wb.pool())} pairs")
    print(f"Vetted for the kids level, from the repository: {len(wb.kids_pool())} pairs")
except Exception as exc:
    print(f"Loader reports: {exc}")
PYEOF

echo
echo "Done. The instrument reads it through devserver/my_app/services/winobias_corpus.py."
