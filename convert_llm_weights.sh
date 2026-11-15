#!/bin/bash
# AI4ArtsEd - weights of the local language models in ComfyUI's own format
#
# ComfyUI implements some of the local language models itself (Qwen 3.5 and
# 3.8, comfy/text_encoders/qwen35.py). For those, the table
# devserver/config/local_llm_weights.json names, under "comfy_weights", one
# file under <ComfyUI>/models/text_encoders/ per format. This script writes
# the files from the folders download_llm_models.sh installed under
# <ComfyUI>/models/llm/. With its file a model answers on ComfyUI's own
# implementation; without it, through transformers.
#
# Usage:
#   ./convert_llm_weights.sh                  every installed model of the table
#                                             that has "comfy_weights" and whose
#                                             default file is not written yet
#   ./convert_llm_weights.sh qwen3.8:27b      the alias named, the table's default
#   ./convert_llm_weights.sh qwen3.8:27b nvfp4   the alias named, the format named
#
# Run it after download_llm_models.sh. The 8- and 4-bit formats are computed
# on the card, under a lease of the DevServer's gate: the DevServer has to
# run (default http://127.0.0.1:17802, or AI4ARTSED_DEVSERVER). A 27B model
# takes about a minute and a half on the card and about 30 GB of disk (mxfp8).
# Idempotent: a file that is there is left alone. ComfyUI lists a new file at
# its next validation; no restart.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMFYUI="${COMFYUI_PATH:-${SCRIPT_DIR}/dlbackend/ComfyUI}"
PYTHON="${COMFYUI_PYTHON:-${COMFYUI}/venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
    echo "No Python of ComfyUI at $PYTHON (set COMFYUI_PATH or COMFYUI_PYTHON)." >&2
    exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/devserver/scripts/convert_llm_for_comfyui.py" --comfyui "$COMFYUI" "$@"
