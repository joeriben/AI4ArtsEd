#!/bin/bash
# AI4ArtsEd - Media Analysis Model Downloader (the GPU service's readers)
#
# Since stage 6 of the move to ComfyUI (2026-09-14) the
# platform reads media on ComfyUI: ./download_media_models.sh media_reading
# installs the audio describer, the lyrics transcriber and the music taggers
# under dlbackend/ComfyUI/models/media_reading/, ./download_llm_models.sh the
# image and video reader under models/llm/. This script fills the Hugging Face
# cache the GPU service reads until stage 8.
#
# The models the GPU service reads media WITH, as opposed to the ones it
# generates media with. They are HuggingFace transformers repositories and land
# in the HF cache (~/.cache/huggingface by default, HF_HOME to move it), not in
# the ComfyUI tree:
#
#   Qwen/Qwen3-VL-8B-Instruct   ~17 GB  images (Compare Hub) and video
#   Qwen/Qwen3.8-27B-FP8        ~28 GB  the image reader of the 96 and 48 GB
#                                       profiles, in place of qwen3-vl:32b
#   mispeech/midashenglm-7b     ~31 GB  audio
#
# Both are ungated -- no HF token needed. Idempotent: an existing, complete
# snapshot is left alone; an interrupted one resumes.
#
# Without this download the reading of audio and video (the node package's
# media reading on ComfyUI, asked through devserver/my_app/services/
# media_analysis_client.py) answers with an error. Still images are NOT read
# here: the same Qwen3-VL 8B runs as a
# GGUF on the llama-cpp station, several times faster, and the Compare Hub's
# image understanding page fetches it through the model install button there.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VENV:-${SCRIPT_DIR}/venv}"
WITH_AUDIO="${WITH_AUDIO:-true}"

echo -e "${BLUE}=== AI4ArtsEd Media Analysis Model Downloader ===${NC}"

MODELS=("Qwen/Qwen3-VL-8B-Instruct" "Qwen/Qwen3.8-27B-FP8")
if [ "$WITH_AUDIO" = "true" ]; then
    MODELS+=("mispeech/midashenglm-7b")
else
    echo -e "${YELLOW}WITH_AUDIO=false — skipping the audio model.${NC}"
fi

for MODEL_ID in "${MODELS[@]}"; do
    echo ""
    echo -e "${YELLOW}Fetching ${MODEL_ID} ...${NC}"
    "$VENV/bin/python" - "$MODEL_ID" <<'PY'
import sys
from huggingface_hub import snapshot_download
path = snapshot_download(sys.argv[1])
print("weights at", path)
PY
    echo -e "${GREEN}✓ ${MODEL_ID}${NC}"
done

echo ""
echo -e "${GREEN}Done. Restart the GPU service so it sees them:${NC}"
echo "  sudo systemctl restart ai4artsed-gpu.service"
