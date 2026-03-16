#!/bin/bash
# Start GPU Service in foreground (visible terminal output)
# Shared Diffusers + HeartMuLa inference on port 17803
# Both dev (17802) and prod (17801) backends call this via HTTP REST

# Keep window open on error
trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR

GPU_PORT=17803

# Get directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RECORD_SERVICE_NAME="GPU Service"
source "$SCRIPT_DIR/_record.sh"

echo "=== AI4ArtsEd GPU Service ==="
echo ""

# Check if port is in use and terminate any process using it
echo "Checking port ${GPU_PORT}..."
if lsof -ti:${GPU_PORT} > /dev/null 2>&1; then
    echo "Port ${GPU_PORT} is in use. Terminating existing process..."
    lsof -ti:${GPU_PORT} -sTCP:LISTEN | xargs -r kill -9
    sleep 2
    echo "✅ Process terminated."
fi

# Move to gpu_service directory
cd "$SCRIPT_DIR/gpu_service"

echo ""
echo "Starting GPU Service on http://127.0.0.1:${GPU_PORT}"
echo "Working directory: $SCRIPT_DIR/gpu_service"
echo "Press Ctrl+C to stop"
echo ""

# Remove error trap - allow normal server exit without "Script failed" message
trap - ERR

# Reduce CUDA memory fragmentation on large GPUs (recommended since PyTorch 2.1+)
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

# Use venv Python directly (shared with Flask backends)
"$SCRIPT_DIR/venv/bin/python" server.py
