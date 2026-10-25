#!/bin/bash
# AI4ArtsEd DevServer - VoxCPM2 Setup
#
# Installs VoxCPM2, the synthesiser that is asked for a voice in words.
#
# Nothing here is committed to this repository. VoxCPM2, like Piper and like
# every model on this platform, is a downloaded technology: the code lives in
# its own virtual environment, the weights live outside the working tree, and
# both are fetched by this script.
#
# WHY ITS OWN ENVIRONMENT, AND NOT THE PLATFORM'S
#
# Not a preference. `voxcpm` declares `datasets>=3,<4` and `gradio>=6,<7`; the
# platform runs datasets 4.5.0 and gradio 5.50.0. Installing it into the shared
# environment would downgrade the one and upgrade the other under everything
# else that uses them. Qwen3-TTS was lost to exactly that kind of move — a
# transformers upgrade elsewhere in the environment — on 2026-08-12, and it is
# the reason this synthesiser is here at all.
#
# It is therefore reached the way Piper is reached: out of process. Unlike
# Piper it is a 2 B model on the GPU, so it is not started per utterance —
# `voxcpm_service/server.py` holds it and answers on VOXCPM_PORT.
#
# WHAT IT IS
#
# Tokenizer-free diffusion autoregressive TTS, 2 B parameters, 48 kHz, 30
# languages — eight of the platform's ten (Arabic, German, English, Spanish,
# French, Hebrew, Korean, Turkish; no Bulgarian, no Ukrainian). Apache-2.0,
# openbmb/VoxCPM2.
#
# The voice is asked for in words, inside the text itself:
#     "(A young woman, gentle and sweet voice)Hello, welcome to VoxCPM2!"
# The description and the utterance are one string, so the model has to decide
# what to speak and what to obey. That is the property this platform compares
# it for; it is not a reason to trust the outcome.
#
# Origin of the recorded voices behind the model: not disclosed by the
# publisher, consent of the recorded speakers unknown.
#
# Idempotent: safe to re-run.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

VOXCPM_HOME="${VOXCPM_HOME:-$HOME/ai/voxcpm}"
VENV="$VOXCPM_HOME/venv"
MODEL_ID="${VOXCPM_MODEL_ID:-openbmb/VoxCPM2}"

echo "=== VoxCPM2 setup ==="
echo "Home:  $VOXCPM_HOME"
echo "Model: $MODEL_ID"
echo ""

mkdir -p "$VOXCPM_HOME"

# --- the environment ------------------------------------------------------

if [ ! -x "$VENV/bin/python" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV"
else
    echo "Virtual environment present."
fi

# No --system-site-packages on purpose: seeing the platform's datasets and
# gradio is the one thing this environment exists to prevent.
"$VENV/bin/python" -m pip install --upgrade --quiet pip wheel

if "$VENV/bin/python" -c "import voxcpm" 2>/dev/null; then
    echo "voxcpm present."
else
    echo -e "${YELLOW}Installing voxcpm (this pulls its own torch, several GB)...${NC}"
    "$VENV/bin/python" -m pip install voxcpm
fi

# --- the weights ----------------------------------------------------------

echo ""
echo -e "${YELLOW}Fetching $MODEL_ID ...${NC}"
"$VENV/bin/python" - "$MODEL_ID" <<'PY'
import sys
from huggingface_hub import snapshot_download
path = snapshot_download(sys.argv[1])
print("weights at", path)
PY

# --- proof that it speaks -------------------------------------------------

echo ""
echo -e "${YELLOW}Speaking one sentence to prove the install...${NC}"
"$VENV/bin/python" - "$MODEL_ID" "$VOXCPM_HOME/install_check.wav" <<'PY'
import sys
import soundfile as sf
from voxcpm import VoxCPM

model = VoxCPM.from_pretrained(sys.argv[1], load_denoiser=False)
wav = model.generate(text="(A calm voice)This install works.")
sf.write(sys.argv[2], wav, model.tts_model.sample_rate)
print("wrote", sys.argv[2], len(wav) / model.tts_model.sample_rate, "s")
PY

echo ""
echo -e "${GREEN}Done.${NC} VoxCPM2 lives in $VOXCPM_HOME"
echo "Start the worker with: ./2_start_voxcpm.sh"
