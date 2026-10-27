#!/bin/bash
# Start Flask backend in foreground (visible terminal output)
# PRODUCTION backend on port 17801 (for cloudflared tunnel)

# Keep window open on error
trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR

BACKEND_PORT=17801

# Get directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Record the terminal output into a protocol file where the installation has _record.sh
RECORD_SERVICE_NAME="backend"
if [ -f "$SCRIPT_DIR/_record.sh" ]; then
    source "$SCRIPT_DIR/_record.sh"
fi

# Safety check: the development branch is not served on the production port
if [ "$(git -C "$SCRIPT_DIR" symbolic-ref --short -q HEAD 2>/dev/null)" = "develop" ]; then
    echo "❌ ERROR: This production script does not run on the branch 'develop'."
    echo "   Current directory: $SCRIPT_DIR"
    echo "   Expected: a checkout of 'main', the production branch"
    exit 1
fi

echo "=== AI4ArtsEd Backend (Production) ==="
echo ""

# Check if port is in use and terminate any process using it
echo "Checking port ${BACKEND_PORT}..."
if lsof -ti:${BACKEND_PORT} > /dev/null 2>&1; then
    echo "Port ${BACKEND_PORT} is in use. Terminating existing process..."
    lsof -ti:${BACKEND_PORT} -sTCP:LISTEN | xargs -r kill -9
    sleep 2
    echo "✅ Process terminated."
fi

# Move to devserver directory
cd "$SCRIPT_DIR/devserver"

# Load AWS credentials if available
if [ -f "$SCRIPT_DIR/devserver/setup_aws_env.sh" ]; then
    echo "Loading AWS credentials..."
    source "$SCRIPT_DIR/devserver/setup_aws_env.sh"
fi

# Clean Python cache
echo "Cleaning Python cache..."
rm -rf my_app/__pycache__ my_app/*/__pycache__ schemas/__pycache__ schemas/*/__pycache__

echo ""
echo "Starting Flask backend (PRODUCTION) on http://0.0.0.0:${BACKEND_PORT}"
echo "Working directory: $SCRIPT_DIR/devserver"
echo "Press Ctrl+C to stop"
echo ""

# Override PORT via environment variable
export PORT=17801

# Enable browser caching for production (configs/models cached for 5min)
export DISABLE_API_CACHE=false

# Remove error trap - allow normal server exit without "Script failed" message
trap - ERR

# Use venv Python directly (more reliable than sourcing activate). `exec` for
# the same reason as in 2_start_gpu_service.sh: one process, and the signal
# reaches it rather than a shell that would swallow it.
exec "$SCRIPT_DIR/venv/bin/python" server.py
