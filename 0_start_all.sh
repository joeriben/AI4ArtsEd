#!/bin/bash
# Start all AI4ArtsEd services (backend, GPU service, ComfyUI).
#
# These run as systemd services (Restart=always) — this script is a thin
# wrapper around systemctl so you don't need to remember unit names.
# It does NOT touch the frontend dev server or the cloudflared app tunnel,
# neither of which is systemd-managed here; start those manually if needed.

trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR

echo "=== Starting All AI4ArtsEd Services ==="
echo ""

start_unit() {
    local unit="$1"
    local label="$2"

    if systemctl is-active --quiet "$unit"; then
        echo "   ⚪ $label already running — restarting"
        sudo systemctl restart "$unit"
    else
        sudo systemctl start "$unit"
    fi

    if systemctl is-active --quiet "$unit"; then
        echo "   ✅ $label ($unit) running"
    else
        echo "   ❌ $label ($unit) FAILED to start — check: journalctl -u $unit -n 50"
    fi
}

echo "[1/3] GPU Service..."
start_unit ai4artsed-gpu.service "GPU Service"

echo "[2/3] ComfyUI..."
start_unit ai4artsed-comfyui.service "ComfyUI"

echo "[3/3] Backend..."
start_unit ai4artsed-backend.service "Backend"

echo ""
echo "✅ Done — check status any time with: systemctl status ai4artsed-gpu ai4artsed-comfyui ai4artsed-backend"
