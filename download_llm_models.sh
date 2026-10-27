#!/bin/bash
# AI4ArtsEd - Local Language Model Downloader
#
# The local language and image-reading models (the local half of the comparison
# surfaces, the image readers), as safetensors snapshots from Hugging Face into
# <ComfyUI>/models/llm/<repository>/, where ComfyUI runs them (stage 3 of
# The local language and image-reading models (the local half of the comparison
# surfaces, the image readers), as safetensors snapshots from Hugging Face into
# <ComfyUI>/models/llm/<repository>/, where ComfyUI runs them (stage 3 of
# the move to ComfyUI). Which alias is which repository is ONE
# table, devserver/config/local_llm_weights.json; the Download entry of the model
# lists of System Prompts and Image Understanding (POST /api/chat/install) installs
# from the same table.
# The safety classifier is not among them: the GPU service runs it from its own
# store (docs/installation/MODELS_REQUIRED.md).
#
# Usage:
#   ./download_llm_models.sh                  every local model a model role of the
#                                             settings names (user_settings.json),
#                                             except SAFETY_MODEL's, and the model
#                                             the look at images runs on
#   ./download_llm_models.sh qwen3:1.7b ...   the aliases named
#
# Idempotent: an installed model is left alone; an interrupted download
# resumes. A gated repository (the table says which) needs HF_TOKEN in the
# environment, from a Hugging Face account that accepted the model's licence.
# ComfyUI lists a new folder at its next validation; no restart.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VENV:-${SCRIPT_DIR}/venv}"

cd "$SCRIPT_DIR/devserver"
exec "$VENV/bin/python" -m my_app.services.local_llm_install "$@"
