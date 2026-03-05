#!/bin/bash
# Stop all AI4ArtsEd services

# Keep window open on error
trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR

echo "=== Stopping All AI4ArtsEd Services ==="
echo ""

# Stop backend processes (both dev and prod ports)
echo "[1/3] Stopping backend processes..."
if lsof -ti:17802 > /dev/null 2>&1; then
    lsof -ti:17802 | xargs -r kill -9
    echo "   ✅ Backend dev (17802) stopped"
else
    echo "   ⚪ Backend dev (17802) not running"
fi

if lsof -ti:17801 > /dev/null 2>&1; then
    lsof -ti:17801 | xargs -r kill -9
    echo "   ✅ Backend prod (17801) stopped"
else
    echo "   ⚪ Backend prod (17801) not running"
fi


if lsof -ti:17803 > /dev/null 2>&1; then
    lsof -ti:17803 | xargs -r kill -9
    echo "   ✅ GPU Service (17803) stopped"
else
    echo "   ⚪ GPU Service (17803) not running"
fi


if lsof -ti:17804 > /dev/null 2>&1; then
    lsof -ti:17804 | xargs -r kill -9
    echo "   ✅ ComfyUI (17804) stopped"
else
    echo "   ⚪ ComfyUI (17804) not running"
fi

# Stop frontend process
echo "[2/3] Stopping frontend process..."
if lsof -ti:5173 > /dev/null 2>&1; then
    lsof -ti:5173 | xargs -r kill -9
    echo "   ✅ Frontend (5173) stopped"
else
    echo "   ⚪ Frontend (5173) not running"
fi

# Stop cloudflared tunnel
echo "[3/3] Stopping cloudflared tunnel..."
if pgrep -f "cloudflared.*tunnel run" > /dev/null; then
    pkill -f "cloudflared.*tunnel run"
    echo "   ✅ Cloudflared tunnel stopped"
else
    echo "   ⚪ Cloudflared tunnel not running"
fi

echo ""
echo "✅ All AI4ArtsEd services stopped"
