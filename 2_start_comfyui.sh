#!/bin/bash
# Start ComfyUI directly (standalone installation)
#
# ComfyUI runs on port 17804 and is accessed directly by the DevServer
# via WebSocket (progress tracking) and HTTP (media download).
# Models are in dlbackend/ComfyUI/models/ (ComfyUI standard paths).

# Keep window open on error
trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR

COMFYUI_PORT=17804

# Get directory where this script lives (repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RECORD_SERVICE_NAME="ComfyUI"
source "$SCRIPT_DIR/_record.sh"

# ComfyUI location (standalone installation, overridable via env)
COMFYUI_DIR="${COMFYUI_DIR:-$SCRIPT_DIR/dlbackend/ComfyUI}"

# Check if port is in use and terminate any process using it
echo "Checking port ${COMFYUI_PORT}..."
if lsof -ti:${COMFYUI_PORT} > /dev/null 2>&1; then
    echo "Port ${COMFYUI_PORT} is in use. Terminating existing process..."
    lsof -ti:${COMFYUI_PORT} | xargs -r kill -9
    sleep 2
    echo "✅ Process terminated."
fi

echo "=== Starting ComfyUI (Standalone) ==="
echo ""

# Check if ComfyUI directory exists
if [ ! -d "$COMFYUI_DIR" ]; then
    echo "❌ ERROR: ComfyUI not found at: $COMFYUI_DIR"
    echo ""
    echo "Expected location: dlbackend/ComfyUI/"
    echo "Run: cd dlbackend && git clone https://github.com/comfyanonymous/ComfyUI.git"
    exit 1
fi

cd "$COMFYUI_DIR"
echo "Working directory: $COMFYUI_DIR"

# Verify main.py exists (newer ComfyUI versions may have different entry points)
if [ ! -f "main.py" ]; then
    echo "❌ ERROR: main.py not found in $COMFYUI_DIR"
    echo ""
    echo "Directory contents: $(ls -1 | head -10)"
    echo "If ComfyUI is installed elsewhere, set COMFYUI_DIR env variable."
    exit 1
fi

# === Startup Cleanup (ported from old SwarmUI script) ===
# DevServer exports to /exports, so ComfyUI output/input are redundant between sessions
echo "========================================"
echo "Cleaning up redundant files from previous sessions..."
echo "========================================"

# ComfyUI output directory (generated images — DevServer already exports its own copies)
if [ -d "./output" ] && [ "$(ls -A ./output 2>/dev/null)" ]; then
    count=$(find ./output -type f 2>/dev/null | wc -l)
    echo "ComfyUI output/: $count files -> Deleted"
    rm -rf ./output/*
else
    echo "ComfyUI output/: empty"
fi

# ComfyUI input directory (uploaded i2i images from previous sessions)
if [ -d "./input" ] && [ "$(ls -A ./input 2>/dev/null)" ]; then
    count=$(find ./input -type f 2>/dev/null | wc -l)
    echo "ComfyUI input/: $count files -> Deleted"
    rm -rf ./input/*
else
    echo "ComfyUI input/: empty"
fi

# DevServer uploads_tmp (temporary upload staging area)
UPLOADS_TMP="$SCRIPT_DIR/exports/uploads_tmp"
if [ -d "$UPLOADS_TMP" ] && [ "$(ls -A "$UPLOADS_TMP" 2>/dev/null)" ]; then
    count=$(find "$UPLOADS_TMP" -type f 2>/dev/null | wc -l)
    echo "exports/uploads_tmp/: $count files -> Deleted"
    rm -rf "$UPLOADS_TMP"/*
else
    echo "exports/uploads_tmp/: empty"
fi

echo "========================================"
echo ""

# Activate ComfyUI's own venv
VENV_DIR="$COMFYUI_DIR/venv"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    echo "Activated venv: $VENV_DIR"
else
    echo "⚠️ No venv found at $VENV_DIR, using system Python"
fi

echo "Starting ComfyUI on port $COMFYUI_PORT..."
echo "Press Ctrl+C to stop"
echo ""

# Remove error trap - allow normal server exit without "Script failed" message
trap - ERR

# Start ComfyUI directly
# --listen 127.0.0.1: only local access (DevServer connects locally)
# --port 17804: AI4ArtsEd embedded ComfyUI port
# --cache-ram 8: keep node results across prompts until 8 GB of RAM are
#   left. ComfyUI's default cache holds the results of the LAST prompt only;
#   since stage 3 of the move to ComfyUI every safety check and image reading
#   is a one-node prompt between the image runs, and with the default cache
#   each of them threw the image workflow's loaded checkpoint away, to be
#   read from disk again for the next picture.
# --max-upload-size 2048: ComfyUI's default is 100 MB; since stage 6 of the
#   move the media readers (audio description, lyrics, video) and MMAudio take
#   a recording or a video handed over through /upload/image, and a video of
#   a few minutes is more than 100 MB.
# Models are in standard ComfyUI paths (models/checkpoints, models/clip, etc.)
# No --extra-model-paths-config needed
# HF_HUB_USER_AGENT_ORIGIN: a checkpoint the maker ships in FP8 (Qwen 3.8
#   27B, Ministral 3) runs through a Triton kernel that transformers 5.17
#   fetches once from the Hub (kernels-community/finegrained-fp8, publisher
#   verified by the Hub, no trust_remote_code). main.py switches Hub telemetry
#   off, and with it the kernels package hands huggingface_hub an empty user
#   agent, which leaves the header ending in "; " -- httpx refuses the header,
#   and the publisher check fails as "could not verify publisher trust status"
#   (kernels 0.16.2 and 0.17.1 with huggingface_hub 1.32.0, 2026-09-17). The
#   origin tag is the last element of that header and closes it.
# Pipe through awk to prepend ISO timestamps (ComfyUI logs have none by default)
HF_HUB_USER_AGENT_ORIGIN=comfyui PYTHONUNBUFFERED=1 python main.py \
    --listen 127.0.0.1 \
    --port "$COMFYUI_PORT" \
    --preview-method auto \
    --cache-ram 8 \
    --max-upload-size 2048 \
    2>&1 | awk '{ print strftime("%Y-%m-%dT%H:%M:%S"), $0; fflush() }'
