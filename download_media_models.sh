#!/bin/bash
# AI4ArtsEd - Media Station Model Downloader
#
# The weights of the media stations -- Stable Audio 3, ImageBind, MMAudio,
# HeartMuLa, Hunyuan3D 2 and the media readers (the audio describer, the lyrics
# transcriber, the music taggers) -- into <ComfyUI>/models/<station>/<folder>/,
# where the platform's node package runs them (stage 6 of
# the move to ComfyUI). Which alias is which repository, which
# folder it lands in and which files make the folder whole is ONE table,
# devserver/config/local_media_weights.json; the ComfyUI nodes and the backend
# status of the settings page read the same table.
#
# Usage:
#   ./download_media_models.sh                      every model of the table
#   ./download_media_models.sh heartmula-3b ...     the aliases named
#   ./download_media_models.sh media_reading ...    every model of a station
#                                                   (stable_audio, imagebind, mmaudio,
#                                                   heartmula, hunyuan3d, media_reading)
#
# Idempotent: an installed model is left alone; an interrupted download is
# taken up again (finished files stay, the file in flight is fetched again).
# The Stable Audio 3 repositories are gated: HF_TOKEN in the
# environment, from a Hugging Face account that accepted the model's licence.
# What a station's library loads by name (the table's 'cached') goes into the
# Hugging Face cache, ~/.cache/huggingface by default, HF_HOME to move it.
# ComfyUI lists a new folder at its next validation; no restart.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VENV:-${SCRIPT_DIR}/venv}"

cd "$SCRIPT_DIR/devserver"
exec "$VENV/bin/python" -m my_app.services.local_media_install "$@"
