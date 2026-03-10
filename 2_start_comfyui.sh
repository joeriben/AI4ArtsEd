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

# ComfyUI location (standalone installation)
COMFYUI_DIR="$SCRIPT_DIR/dlbackend/ComfyUI"

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
# Models are in standard ComfyUI paths (models/checkpoints, models/clip, etc.)
# No --extra-model-paths-config needed
# Pipe through awk to prepend ISO timestamps (ComfyUI logs have none by default)
PYTHONUNBUFFERED=1 python main.py \
    --listen 127.0.0.1 \
    --port "$COMFYUI_PORT" \
    --preview-method auto \
    2>&1 | awk '{ print strftime("%Y-%m-%dT%H:%M:%S"), $0; fflush() }'
