#!/bin/bash
# Stop all AI4ArtsEd services
#
# Backend, GPU service and ComfyUI now run as systemd services with
# Restart=always. A plain `kill -9` on their port just gets them
# auto-restarted by systemd a few seconds later. For those three we stop
# via systemctl; everything else (frontend dev server, app cloudflared
# tunnel) is not systemd-managed here and keeps the old port-kill / pkill
# logic. The SSH-access tunnel (cloudflared-ssh-fedora.service) is never
# touched by this script.

# Keep window open on error
trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR

echo "=== Stopping All AI4ArtsEd Services ==="
echo ""

stop_unit_or_port() {
    local unit="$1"
    local port="$2"
    local label="$3"

    if command -v systemctl > /dev/null 2>&1 && systemctl list-unit-files "$unit" > /dev/null 2>&1 && systemctl is-enabled "$unit" > /dev/null 2>&1; then
        if systemctl is-active --quiet "$unit"; then
            if sudo systemctl stop "$unit"; then
                echo "   ✅ $label ($unit) stopped via systemctl"
            else
                echo "   ❌ $label ($unit) stop FAILED (check sudo password / permissions)"
            fi
        else
            echo "   ⚪ $label ($unit) not running"
        fi
        return
    fi

    # Fallback: not a managed systemd unit here (e.g. local/Mac dev) — kill by port
    if lsof -ti:"$port" > /dev/null 2>&1; then
        lsof -ti:"$port" | xargs -r kill -9
        echo "   ✅ $label ($port) stopped"
    else
        echo "   ⚪ $label ($port) not running"
    fi
}

echo "[1/3] Stopping backend/GPU/ComfyUI..."
stop_unit_or_port ai4artsed-backend.service 17802 "Backend dev"

if lsof -ti:17801 > /dev/null 2>&1; then
    lsof -ti:17801 | xargs -r kill -9
    echo "   ✅ Backend prod (17801) stopped"
else
    echo "   ⚪ Backend prod (17801) not running"
fi

stop_unit_or_port ai4artsed-gpu.service 17803 "GPU Service"
stop_unit_or_port ai4artsed-comfyui.service 17804 "ComfyUI"

# Stop frontend process (no systemd unit — dev-only Vite server)
echo "[2/3] Stopping frontend process..."
if lsof -ti:5173 > /dev/null 2>&1; then
    lsof -ti:5173 | xargs -r kill -9
    echo "   ✅ Frontend (5173) stopped"
else
    echo "   ⚪ Frontend (5173) not running"
fi

# Stop cloudflared tunnel (app tunnel only — never touch the SSH access tunnel,
# which runs as cloudflared-ssh-fedora.service with ssh-fedora-config.yml)
echo "[3/3] Stopping cloudflared tunnel..."
app_tunnel_pids=$(pgrep -f "cloudflared.*tunnel run" | while read -r pid; do
    if ! ps -p "$pid" -o args= | grep -q "ssh-fedora-config.yml"; then
        echo "$pid"
    fi
done)
if [ -n "$app_tunnel_pids" ]; then
    echo "$app_tunnel_pids" | xargs -r kill -9
    echo "   ✅ Cloudflared app tunnel stopped"
else
    echo "   ⚪ Cloudflared app tunnel not running"
fi

echo ""
echo "✅ Done"
echo ""
echo "To start again: sudo systemctl start ai4artsed-gpu.service; sudo systemctl start ai4artsed-comfyui.service; sudo systemctl restart ai4artsed-backend.service"
