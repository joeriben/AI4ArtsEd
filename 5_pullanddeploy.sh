#!/bin/bash
# Production deploy: pull main, build frontend, restart systemd services.
#
# This box is production-only. Development happens on Fedora (RTX 6000 Blackwell).
# See README_PRODUCTION.md.

# Ensure script runs in a terminal window
if [ ! -t 0 ]; then
    gnome-terminal -- bash -c "$0; exec bash" || xterm -e "$0; exec bash" || konsole -e "$0; exec bash"
    exit 0
fi

trap 'echo ""; echo "❌ ERROR: Command failed! (exit code: $?)"; echo ""; read -n 1 -s -r -p "Press any key to close..."; exit 1' ERR
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== AI4ArtsEd Production Deployment ==="
echo "Repo: $SCRIPT_DIR"
echo ""

# ── 1. Pull main (fast-forward only) ──
echo "📥 Step 1/4: Pulling main (ff-only)..."
git checkout main
git pull --ff-only origin main
echo "✅ HEAD now at: $(git log -1 --oneline)"
echo ""

# ── 2. Build frontend ──
echo "🔨 Step 2/4: Building frontend..."
cd "$SCRIPT_DIR/public/ai4artsed-frontend"
npm ci
npm run build
cd "$SCRIPT_DIR"
echo "✅ Frontend built ($(du -sh public/ai4artsed-frontend/dist | cut -f1))"
echo ""

# ── 3. Restart systemd services ──
echo "🔄 Step 3/4: Restarting services..."
echo "    Requires sudo password."
sudo systemctl restart ai4artsed-gpu ai4artsed-backend
# ComfyUI too, where it runs as a unit of its own (setup_lab6000_supervision.sh
# writes one; install_systemd_services.sh does not, and there the backend
# starts ComfyUI itself, so its restart takes ComfyUI along). The platform's
# own nodes are symlinked into custom_nodes and read at ComfyUI's start, so a
# pull that changes comfyui_nodes/ left a unit-run ComfyUI on the old code
# until 2026-10-10 (S-047). Without the unit the restart used to fail the
# deploy under the ERR trap (second review of 2026-10-10).
if systemctl list-unit-files ai4artsed-comfyui.service 2>/dev/null | grep -q '^ai4artsed-comfyui'; then
    sudo systemctl restart ai4artsed-comfyui
fi
echo "✅ Restart issued."
echo ""

# ── 4. Healthcheck ──
echo "🩺 Step 4/4: Healthcheck (up to 60s)..."
GPU_OK=0
BACKEND_OK=0
COMFY_OK=0
for i in $(seq 1 30); do
    if [ "$GPU_OK" = "0" ] && curl -fsS --max-time 2 http://127.0.0.1:17803/api/health > /dev/null 2>&1; then
        echo "    gpu_service ✓ (after ${i}×2s)"
        GPU_OK=1
    fi
    if [ "$BACKEND_OK" = "0" ] && curl -fsS --max-time 2 http://127.0.0.1:17801 > /dev/null 2>&1; then
        echo "    backend ✓ (after ${i}×2s)"
        BACKEND_OK=1
    fi
    if [ "$COMFY_OK" = "0" ] && curl -fsS --max-time 2 http://127.0.0.1:17804/system_stats > /dev/null 2>&1; then
        echo "    comfyui ✓ (after ${i}×2s)"
        COMFY_OK=1
    fi
    [ "$GPU_OK" = "1" ] && [ "$BACKEND_OK" = "1" ] && [ "$COMFY_OK" = "1" ] && break
    sleep 2
done

if [ "$GPU_OK" = "0" ] || [ "$BACKEND_OK" = "0" ] || [ "$COMFY_OK" = "0" ]; then
    echo ""
    echo "❌ Service(s) did not come up within 60s:"
    [ "$GPU_OK" = "0" ] && echo "   - gpu_service (17803) DOWN"
    [ "$BACKEND_OK" = "0" ] && echo "   - backend (17801) DOWN"
    [ "$COMFY_OK" = "0" ] && echo "   - comfyui (17804) DOWN"
    echo ""
    echo "Inspect with:  journalctl -u ai4artsed-gpu -u ai4artsed-backend -u ai4artsed-comfyui -n 80 --no-pager"
    exit 1
fi

echo ""
echo "✅ Deployment complete. lab.ai4artsed.org should serve the new build."
echo ""
read -n 1 -s -r -p "Press any key to close this window..."
echo ""
exec bash
