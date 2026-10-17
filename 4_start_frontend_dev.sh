#!/bin/bash
# Start Vite dev server for frontend development

# Keep window open on error
trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR

VITE_PORT=5173
BACKEND_DEV_PORT=17802

# Get directory where this script lives (repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Safety check: Only run from 'develop' directory
if [[ ! "$SCRIPT_DIR" =~ "develop" ]]; then
    echo "❌ ERROR: This development script can only be run from a directory containing 'develop' in its path."
    echo "   Current directory: $SCRIPT_DIR"
    echo "   Expected: Path must contain 'develop' (e.g., ~/ai/ai4artsed_development)"
    exit 1
fi

# Frontend is in public/ai4artsed-frontend relative to repo root
FRONTEND_DIR="$SCRIPT_DIR/public/ai4artsed-frontend"

echo "=== AI4ArtsEd Frontend (Development) ==="
echo ""

# Check if Vite port is in use and terminate any process using it
echo "Checking port ${VITE_PORT}..."
if lsof -ti:${VITE_PORT} > /dev/null 2>&1; then
    echo "Port ${VITE_PORT} is in use. Terminating existing process..."
    lsof -ti:${VITE_PORT} | xargs -r kill -9
    sleep 2
    echo "✅ Process terminated."
fi

# Move to frontend directory
cd "$FRONTEND_DIR"

echo ""
echo "Building frontend (fresh build)..."
npm run build

if [ $? -ne 0 ]; then
    echo "❌ Build failed! Check errors above."
    exit 1
fi

echo ""
echo "✅ Build completed successfully"
echo ""
echo "Starting Vite dev server on http://localhost:${VITE_PORT}"
echo "Backend API proxy: http://localhost:${BACKEND_DEV_PORT} (dev backend)"
echo "Working directory: $FRONTEND_DIR"
echo "Press Ctrl+C to stop"
echo ""

# Remove error trap - allow normal server exit without "Script failed" message
trap - ERR

npm run dev
