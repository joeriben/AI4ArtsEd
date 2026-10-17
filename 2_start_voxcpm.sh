#!/bin/bash
# Start the VoxCPM2 worker (port 17805)
#
# VoxCPM2 runs in its own virtual environment, not the platform's — see
# voxcpm_service/server.py for why, and download_voxcpm.sh for how that
# environment is built. The DevServer starts this script by itself when a
# caller asks for the voxcpm system and nothing is listening; run it by hand to
# have the model resident before the first request, or to watch its log.
#
# Before its weights go on the card the worker asks the DevServer's gate for
# the card's turn (POST /api/gate/lease/acquire), found through
# AI4ARTSED_DEVSERVER_URL or PORT (17802 by default; a production backend
# answers on 17801, so export PORT=17801 for a hand start there). Until the
# gate answers, /health says "gate": "waiting" and nothing is loaded.

# Keep window open on error
trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR

VOXCPM_PORT="${VOXCPM_PORT:-17805}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RECORD_SERVICE_NAME="VoxCPM2"
source "$SCRIPT_DIR/_record.sh"

VOXCPM_HOME="${VOXCPM_HOME:-$HOME/ai/voxcpm}"
VENV_PYTHON="$VOXCPM_HOME/venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "❌ ERROR: VoxCPM2 environment not found at $VOXCPM_HOME"
    echo ""
    echo "Run ./download_voxcpm.sh — it creates the environment and fetches"
    echo "the weights. Neither is part of this repository."
    exit 1
fi

echo "Checking port ${VOXCPM_PORT}..."
if lsof -ti:${VOXCPM_PORT} > /dev/null 2>&1; then
    echo "Port ${VOXCPM_PORT} is in use. Terminating existing process..."
    lsof -ti:${VOXCPM_PORT} | xargs -r kill -9
    sleep 2
    echo "✅ Process terminated."
fi

echo "=== Starting VoxCPM2 worker ==="
echo "Environment: $VOXCPM_HOME"
echo "Port:        $VOXCPM_PORT"
echo "Gate:        ${AI4ARTSED_DEVSERVER_URL:-http://127.0.0.1:${PORT:-17802}} (the DevServer the worker asks for the card's turn)"
echo ""
echo "The model needs about 25 seconds to load. Until it is up, /health"
echo "answers with loaded=false rather than refusing the connection."
echo ""

# Remove error trap - allow normal server exit without "Script failed" message
trap - ERR

cd "$SCRIPT_DIR"
PYTHONUNBUFFERED=1 VOXCPM_PORT="$VOXCPM_PORT" \
    "$VENV_PYTHON" "$SCRIPT_DIR/voxcpm_service/server.py"
