#!/bin/bash
# AI4ArtsEd DevServer - CommonCanvas XL C Downloader
#
# CommonCanvas XL C is on the platform twice, and the two routes read the
# weights from two different places:
#
#   commoncanvas_xl_c            ComfyUI, single-file checkpoint under
#                                <repo>/dlbackend/ComfyUI/models/checkpoints/
#   commoncanvas_xl_c_diffusers  GPU service, the repository in diffusers
#                                format out of the HuggingFace cache
#
# Neither is optional for the config that names it: a diffusers config whose
# repository is missing does not fail fast -- it fetches at load time, inside
# the card's admission slot, and holds the whole platform for the download.
#
# Idempotent: safe to re-run, skips what is already there.
#
# Architecture: AI4ArtsEd uses a single-directory layout. ComfyUI lives at
#   <repo>/dlbackend/ComfyUI/
# Override the target by exporting COMFYUI_PATH before running.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMFYUI_PATH="${COMFYUI_PATH:-${SCRIPT_DIR}/dlbackend/ComfyUI}"
CKPT_DIR="${COMFYUI_PATH}/models/checkpoints"
REPO="common-canvas/CommonCanvas-XL-C"

echo -e "${BLUE}=== AI4ArtsEd CommonCanvas XL C Downloader ===${NC}"
echo ""
echo "ComfyUI path:   $COMFYUI_PATH"
echo "Total download: ~21 GB (checkpoint ~6.9 GB + diffusers repository ~14 GB)"
echo "Estimated time: 15-40 minutes (100 Mbps)"
echo ""

# --- 1. ComfyUI route: the single-file checkpoint ---------------------------

mkdir -p "$CKPT_DIR"
TARGET="${CKPT_DIR}/commoncanvas_xl_c.safetensors"

if [ -f "$TARGET" ]; then
    echo -e "${GREEN}✓${NC} Already exists, skipping: commoncanvas_xl_c.safetensors"
else
    URL="https://huggingface.co/${REPO}/resolve/main/commoncanvas_xl_c.safetensors"
    echo -e "${BLUE}→${NC} commoncanvas_xl_c.safetensors (~6.9 GB)"
    if command -v aria2c >/dev/null 2>&1; then
        aria2c -x 8 -s 8 -c --dir "$CKPT_DIR" \
               --out "commoncanvas_xl_c.safetensors.part" "$URL"
        mv "${TARGET}.part" "$TARGET"
    else
        wget -c -O "${TARGET}.part" "$URL"
        mv "${TARGET}.part" "$TARGET"
    fi
    echo -e "${GREEN}✓${NC} commoncanvas_xl_c.safetensors"
fi

# --- 2. Diffusers route: the repository into the HuggingFace cache ----------
#
# Only the files the pipeline actually loads. The repository also carries ONNX,
# OpenVINO and Flax copies of the same weights, and an fp16 variant of each
# component that the GPU service does not ask for -- it loads the default
# files and casts. Pulling everything would be roughly three times this.

# xet off, deliberately. On 2026-09-03 the xet transfer for this repository
# died mid-file and left three of the four weight files at their full size
# with zero bytes in them. huggingface_hub then read the size, called them
# finished, and the load failed on a safetensors header of nothing. The
# classic HTTP path writes what it downloaded and resumes from there, which
# is the property that matters more here than throughput.
export HF_HUB_DISABLE_XET=1

PY="python3"
if [ -x "${SCRIPT_DIR}/venv/bin/python" ]; then
    PY="${SCRIPT_DIR}/venv/bin/python"
fi

echo ""
echo -e "${BLUE}→${NC} ${REPO} in diffusers format (~14 GB)"

"$PY" - "$REPO" <<'PYEOF'
import sys

try:
    from huggingface_hub import snapshot_download
except ImportError:
    sys.exit(
        "huggingface_hub is not installed for this interpreter.\n"
        "Install it, or run this script from the repository so that venv/bin/python is used."
    )

repo = sys.argv[1]
patterns = [
    "model_index.json",
    "scheduler/*.json",
    "tokenizer/*",
    "tokenizer_2/*",
    "text_encoder/config.json",
    "text_encoder/model.safetensors",
    "text_encoder_2/config.json",
    "text_encoder_2/model.safetensors",
    "unet/config.json",
    "unet/diffusion_pytorch_model.safetensors",
    "vae/config.json",
    "vae/diffusion_pytorch_model.safetensors",
]
path = snapshot_download(repo_id=repo, allow_patterns=patterns, max_workers=4)
print(path)
PYEOF

echo -e "${GREEN}✓${NC} ${REPO}"
echo ""
echo -e "${GREEN}Done.${NC} Both CommonCanvas routes have their weights."
echo "The DevServer reports the diffusers config as available once the cache is complete;"
echo "ComfyUI picks the checkpoint up on its next model-list refresh."
