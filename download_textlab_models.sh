#!/bin/bash
# AI4ArtsEd - Latent Text Lab Model Downloader
#
# The models the two bias instruments COMPARE. They are HuggingFace transformers
# repositories and land in the HF cache (~/.cache/huggingface by default, HF_HOME
# to move it); each whole snapshot is then LINKED into <ComfyUI>/models/llm/
# under the repository's name with its slash written as two dashes, which is
# where ComfyUI's loader reads it since stage 5 of the move to ComfyUI
# (comfyui_nodes/ai4artsed_comfyui/_local_llm.py). Nothing is copied.
#
# The list is NOT written out here. It is read from
# devserver/config/text_presets.json, which is where the surfaces get it from
# as well: a model identifier is data, and a second copy in a shell script
# would drift from the first the day someone changes a lineup.
#
#   qwen     ~56 GB   one family across its sizes (Qwen3 1.7B / 4B / 8B / 14B)
#   mixed    ~93 GB   the small models of four makers plus five 7-12B models
#   history  ~60 GB   one family at one size over five generations (2023-2025)
#
# Roughly 210 GB for all three, less where they overlap (Qwen3 4B and 8B stand
# in two scenarios each and are fetched once).
#
# Pick scenarios with SCENARIOS, e.g. for the small lineup alone:
#   SCENARIOS=mixed ./download_textlab_models.sh
#
# Idempotent: an existing, complete snapshot is left alone, an interrupted one
# resumes. Where the catalogue pins a `revision`, that exact state is fetched
# and not the repository's current main.
#
# Only what transformers reads is fetched. Several of these repos also carry
# the maker's own checkpoint beside it - Llama 3.2 3B ships `original/`
# with a 6.4 GB .pth of the same weights - and that is a second copy nothing
# here can load.
#
# THREE STREAMS AT A TIME, no more (FETCH_WORKERS, default 3): one repo after
# another, at most three parallel streams, or the download never finishes.
# The repos run one after another anyway; what was wide open was the
# inside of a single repo - and the xet transport underneath opens its own
# fan-out on top of that, which is how 171 connections came to share ~19
# Mbit/s with nothing finishing. Both levels are bounded to the same number.
#
# An attempt ends when the bytes stop coming, not when a clock runs out. A
# stalled transfer is not hypothetical: on 2026-08-23 the run sat TWELVE HOURS
# on one file that was already complete on disk, threads parked in a futex with
# a dozen idle connections open. A fixed wall clock (45 min, until 2026-09-13)
# was the wrong answer to that: in the night of 2026-09-13 every one of eight
# repositories stalled a few minutes in and then sat out the rest of its 45
# minutes - OLMo 2, 1.3 GB short, received nothing in three quarters of an
# hour, and six hours went by that way. So the watchdog reads what the
# transfer has actually written (occupied blocks under the repo's blobs/) and
# kills the attempt after STALL_TIMEOUT seconds without growth; the next round
# takes the repo up again, and a partial file survives, so it resumes where it
# stopped. FETCH_TIMEOUT stays as an absolute ceiling, 0 for none.
#
# TWO REPOS NEED SOMETHING BEYOND THIS SCRIPT:
#
#   meta-llama/Llama-3.2-3B-Instruct is GATED — accept its licence once in a
#   browser, then make a token available (`hf auth login`, or export HF_TOKEN).
#   Without it this one repo fails and the rest still download.
#
#   Qwen/Qwen-7B (08/2023, the first member of the time series) ships its own
#   loading code. It is the one entry in the catalogue that carries
#   `trust_remote_code`, and it carries a pinned `revision` with it — see the
#   note in devserver/config/text_presets.json. ComfyUI's loader executes no
#   repository code, so this script leaves the member out and says so; the
#   surfaces name it as missing with the same reason. It is fetched once the
#   loader allows it for this one entry.
#
# Without this download the surfaces offer the members that ARE installed and
# name the rest as missing (/api/text/presets); nothing is fetched on first use.

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VENV:-${SCRIPT_DIR}/venv}"
SCENARIOS="${SCENARIOS:-qwen,mixed,history}"
FETCH_TIMEOUT="${FETCH_TIMEOUT:-0}"
STALL_TIMEOUT="${STALL_TIMEOUT:-300}"
FETCH_WORKERS="${FETCH_WORKERS:-3}"
# Plain HTTPS, the xet transport off. Three nights in a row (13., 14. and
# 15.09.2026) every repository that had a part-file from an earlier xet run
# received NOT ONE BYTE in five minutes and was cut, while repositories without
# such a part completed in the same nights. xet writes its parts with holes
# and does not take them up again on this line; the classic path writes what
# it downloaded and resumes from there. download_commoncanvas.sh went the same
# way on 2026-09-03 for the same reason. Three workers are then three
# connections.
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
# A cut attempt leaves what it fetched on disk, so the way through a big
# repository is more attempts, not longer ones. What must NOT happen is what
# happened in the night of 2026-08-25: OLMo 2 was given three quarters of an
# hour three times over, came within a whisker each time, was marked failed and
# never touched again - while five hours of the window went by. Repositories
# are therefore gone over in rounds, and a round that fetches no byte at all
# ends the run.
ATTEMPTS="${ATTEMPTS:-1}"
ROUNDS="${ROUNDS:-24}"
HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}"

# Actually occupied blocks, not apparent size: the xet transport writes its
# part-files with holes, and apparent size would report progress where none was.
cache_bytes() { du -sB1 "$HF_CACHE/hub" 2>/dev/null | cut -f1 || echo 0; }
repo_bytes() { [ -d "$1" ] && du -sB1 "$1" 2>/dev/null | cut -f1 || echo 0; }

echo -e "${BLUE}=== AI4ArtsEd Latent Text Lab Model Downloader ===${NC}"
echo "Scenarios: $SCENARIOS  |  gleichzeitig: $FETCH_WORKERS"

SELECTED="$(cd "$SCRIPT_DIR/devserver" && "$VENV/bin/python" - "$SCRIPT_DIR" "$SCENARIOS" <<'PY'
import sys, os, json
from my_app.services import text_presets
with open(os.path.join(sys.argv[1], "devserver", "config", "text_presets.json"), encoding="utf-8") as f:
    rows = json.load(f)["scenarios"]

wanted = [s.strip() for s in sys.argv[2].split(",") if s.strip()]
unknown = [s for s in wanted if s not in rows]
if unknown:
    sys.exit("unknown scenario(s): %s - known: %s"
             % (", ".join(unknown), ", ".join(rows)))

seen, held, whole = [], [], []
for scenario in wanted:
    for preset in rows[scenario].values():
        if preset.get("trust_remote_code"):
            # ComfyUI's loader executes no code from a repository, so this
            # member runs nowhere yet and is left out here, by name.
            if preset["id"] not in held:
                held.append(preset["id"])
            continue
        if text_presets.is_installed(preset["id"]):
            # Whole under models/llm already, whichever installer put it
            # there: nothing to fetch and nothing to link.
            if preset["id"] not in whole:
                whole.append(preset["id"])
            continue
        line = "%s\t%s" % (preset["id"], preset.get("revision") or "")
        if line not in seen:
            seen.append(line)
for model_id in held:
    print("%s needs code from its repository (trust_remote_code), which the "
          "loader does not execute; left out" % model_id, file=sys.stderr)
for model_id in whole:
    print("%s is whole under models/llm already; nothing to fetch" % model_id, file=sys.stderr)
print("\n".join(seen))
PY
)" || exit 1
MODELS=()
[ -n "$SELECTED" ] && mapfile -t MODELS <<< "$SELECTED"

if [ ${#MODELS[@]} -eq 0 ]; then
    echo -e "${GREEN}Nothing to fetch: every member of ${SCENARIOS} is whole under models/llm.${NC}"
    exit 0
fi

echo "Repositories: ${#MODELS[@]}"

PENDING=("${MODELS[@]}")
UNLINKED=()
ROUND=0
while [ ${#PENDING[@]} -gt 0 ] && [ "$ROUND" -lt "$ROUNDS" ]; do
ROUND=$((ROUND + 1))
BYTES_BEFORE="$(cache_bytes)"
[ "$ROUND" -gt 1 ] && echo -e "\n${BLUE}--- Durchgang $ROUND, offen: ${#PENDING[@]} ---${NC}"
FAILED=()
for ENTRY in "${PENDING[@]}"; do
    MODEL_ID="${ENTRY%%$'\t'*}"
    REVISION="${ENTRY#*$'\t'}"
    echo ""
    if [ -n "$REVISION" ]; then
        echo -e "${YELLOW}Fetching ${MODEL_ID} @ ${REVISION} ...${NC}"
    else
        echo -e "${YELLOW}Fetching ${MODEL_ID} ...${NC}"
    fi
    ok=false
    for attempt in $(seq 1 "$ATTEMPTS"); do
        [ "$attempt" -gt 1 ] && echo -e "${YELLOW}  Versuch ${attempt}/${ATTEMPTS} ...${NC}"
        "$VENV/bin/python" - "$MODEL_ID" "$REVISION" "$FETCH_WORKERS" <<'PY' &
import fnmatch
import os
import sys
from huggingface_hub import HfApi, snapshot_download

model_id, revision = sys.argv[1], (sys.argv[2] or None)
workers = max(1, int(sys.argv[3]))

# The maker's own checkpoint beside the transformers one, and the formats of
# other frameworks. A second copy of the same weights that nothing here can read.
IGNORE = ["original/*", "*.pth", "*.h5", "*.msgpack", "*.onnx", "*.onnx_data"]

api = HfApi()
info = api.model_info(model_id, revision=revision, files_metadata=True)
names = [s.rfilename for s in info.siblings]

# Mistral ships its single-file checkpoint NEXT TO the sharded transformers one:
# 45.6 GB where 22.8 GB are read. Only drop it where the shards are there to be
# read instead - a repo that carries the single file alone needs it.
if any(fnmatch.fnmatch(n, "model-*-of-*.safetensors") for n in names):
    IGNORE += [n for n in names if fnmatch.fnmatch(n, "consolidated*.safetensors")]

# A part-file that xet wrote is full of holes, and the plain path would resume
# it from its apparent size - past the holes - and call the file finished. So
# with xet off, a part that occupies fewer blocks than its size is taken away
# before the download starts; it was never going to be completed by this path.
if os.environ.get("HF_HUB_DISABLE_XET", "") not in ("", "0"):
    blobs = os.path.join(
        os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")),
        "hub", "models--" + model_id.replace("/", "--"), "blobs")
    for name in (os.listdir(blobs) if os.path.isdir(blobs) else []):
        if not name.endswith(".incomplete"):
            continue
        st = os.stat(os.path.join(blobs, name))
        if st.st_blocks * 512 < st.st_size:
            os.remove(os.path.join(blobs, name))
            print("removed a part with holes (xet):", name[:16], file=sys.stderr)

path = snapshot_download(
    model_id, revision=revision, ignore_patterns=IGNORE, max_workers=workers
)

# A returned path is NOT a downloaded model. snapshot_download hands back the
# local snapshot when it cannot reach the hub, and a repo that had only its
# tokenizer fetched earlier then looks finished: on the night of 2026-08-24 five
# repos were reported complete with 11 MB on disk. So the weights are counted
# against what the repository says they are.
missing, short = [], []
for sib in info.siblings:
    name = sib.rfilename
    if any(fnmatch.fnmatch(name, pat) for pat in IGNORE):
        continue
    if not name.endswith((".safetensors", ".bin", ".gguf", ".model")):
        continue
    local = os.path.join(path, name)
    if not os.path.exists(local):
        missing.append(name)
    elif sib.size and os.path.getsize(local) < sib.size:
        short.append(name)

if missing or short:
    print("INCOMPLETE %s: %d missing, %d short" % (model_id, len(missing), len(short)),
          file=sys.stderr)
    for name in (missing + short)[:5]:
        print("   ", name, file=sys.stderr)
    sys.exit(1)

print("weights at", path)
PY
        fetch_pid=$!
        blobs="$HF_CACHE/hub/models--${MODEL_ID//\//--}/blobs"
        last_bytes=$(repo_bytes "$blobs"); last_growth=$SECONDS; started=$SECONDS
        why=""
        while kill -0 "$fetch_pid" 2>/dev/null; do
            sleep 15
            now_bytes=$(repo_bytes "$blobs")
            if [ "$now_bytes" -gt "$last_bytes" ]; then
                last_bytes=$now_bytes; last_growth=$SECONDS
            elif [ $((SECONDS - last_growth)) -ge "$STALL_TIMEOUT" ]; then
                why="seit ${STALL_TIMEOUT}s kein Byte"; break
            fi
            if [ "$FETCH_TIMEOUT" -gt 0 ] && [ $((SECONDS - started)) -ge "$FETCH_TIMEOUT" ]; then
                why="Zeitgrenze ${FETCH_TIMEOUT}s"; break
            fi
        done
        if [ -n "$why" ]; then
            kill -KILL "$fetch_pid" 2>/dev/null
            wait "$fetch_pid" 2>/dev/null || true
            echo -e "${YELLOW}  abgebrochen ($why) — was da ist, bleibt liegen${NC}"
            continue
        fi
        if wait "$fetch_pid"; then
            ok=true
            break
        fi
        echo -e "${YELLOW}  abgebrochen (Fehler) — was da ist, bleibt liegen${NC}"
    done

    if $ok; then
        echo -e "${GREEN}✓ ${MODEL_ID}${NC}"
        # Linked where ComfyUI's loader reads it: the snapshot folder itself
        # under <ComfyUI>/models/llm/, so nothing is copied. A folder that is
        # already there and points elsewhere is left alone and said.
        (cd "$SCRIPT_DIR/devserver" && "$VENV/bin/python" - "$MODEL_ID" "$REVISION" <<'PY'
import os, sys
from huggingface_hub import try_to_load_from_cache
from my_app.services import local_llm_weights, text_presets

model_id, revision = sys.argv[1], (sys.argv[2] or None)
hit = try_to_load_from_cache(model_id, "config.json", revision=revision)
if not isinstance(hit, str):
    sys.exit("%s: no config.json in the cache to link" % model_id)
snapshot = os.path.dirname(hit)
root = local_llm_weights.models_root()
root.mkdir(parents=True, exist_ok=True)
link = root / text_presets.folder_of(model_id)
if link.is_symlink() or link.exists():
    if os.path.realpath(link) == os.path.realpath(snapshot):
        print("linked already: %s" % link)
        sys.exit(0)
    sys.exit("%s exists and points elsewhere; left alone" % link)
os.symlink(snapshot, link)
print("linked %s -> %s" % (link, snapshot))
PY
        ) || { echo -e "${YELLOW}  not linked (see above)${NC}"; UNLINKED+=("$MODEL_ID"); }
    else
        echo -e "${RED}✗ ${MODEL_ID}${NC}"
        FAILED+=("$ENTRY")
    fi
done

PENDING=("${FAILED[@]}")
if [ ${#PENDING[@]} -gt 0 ]; then
    GAINED=$(( $(cache_bytes) - BYTES_BEFORE ))
    if [ "$GAINED" -le 0 ]; then
        echo -e "${RED}Durchgang $ROUND hat kein Byte geholt — Abbruch.${NC}"
        break
    fi
    echo "Durchgang $ROUND: $(numfmt --to=iec "$GAINED" 2>/dev/null || echo "$GAINED B") dazu."
fi
done

echo ""
if [ ${#PENDING[@]} -eq 0 ]; then
    echo -e "${GREEN}All ${#MODELS[@]} repositories are present.${NC}"
else
    echo -e "${RED}${#PENDING[@]} of ${#MODELS[@]} failed:${NC}"
    printf '  %s\n' "${PENDING[@]%%$'\t'*}"
    echo "A gated repo needs its licence accepted and a token (see the header)."
fi
if [ ${#UNLINKED[@]} -gt 0 ]; then
    echo -e "${YELLOW}${#UNLINKED[@]} present and NOT linked under models/llm/ (a folder of that name points elsewhere, see above):${NC}"
    printf '  %s\n' "${UNLINKED[@]}"
fi

echo ""
echo "ComfyUI lists a linked folder at its next validation; nothing to restart."
