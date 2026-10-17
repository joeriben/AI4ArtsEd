#!/bin/bash
# =============================================================================
# AI4ArtsEd — lab6000 Stack Supervision (systemd)
# =============================================================================
# Brings the WHOLE serving stack under systemd supervision so lab6000.ai4artsed.org
# can never silently 502 again. Each service gets Restart=always + start-on-boot.
#
#   ai4artsed-gpu        -> GPU service        (port 17803)
#   ai4artsed-comfyui    -> ComfyUI            (port 17804)
#   ai4artsed-backend    -> DevServer backend  (port 17802)  <- this is what the
#                                                               cloudflared tunnel
#                                                               (lab6000) points at
#
# Also REMOVES the stale old production unit (ai4artsed-production, port 17801,
# on an external production mount) that the tunnel no longer uses.
#
# Design notes:
#  - Each unit just wraps the existing, battle-tested start scripts (no logic
#    duplication). RECORD=0 disables the terminal-protocol tee; journald captures
#    everything instead (view live: journalctl -fu ai4artsed-backend).
#  - The backend unit sets COMFYUI_AUTO_START=false so the backend does NOT also
#    try to launch ComfyUI -> systemd is the single owner of ComfyUI. This env is
#    LOCAL to this unit only; the committed config keeps auto-start=true so
#    ComfyUI-only workshop deployments are unaffected (deployment independence).
#  - Backend depends on (After/Wants) gpu + comfyui so they come up first.
#
# REQUIRES sudo. Idempotent — safe to re-run.
# =============================================================================
set -euo pipefail

# The repository is the directory this script lives in; the service user is the
# account that invoked sudo. Both can be overridden from the environment.
REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
USER_NAME="${USER_NAME:-${SUDO_USER:-$USER}}"
VENV="$REPO/venv"
PATHENV="$VENV/bin:/usr/local/bin:/usr/bin:/bin"
SYSD="/etc/systemd/system"

if [ "$EUID" -ne 0 ]; then
    echo "[✗] Must run with sudo:  sudo bash $0"
    exit 1
fi

echo "=== AI4ArtsEd lab6000 supervision setup ==="
echo "Repo: $REPO"
echo ""

# ----------------------------------------------------------------------------
# 1) GPU service (17803)
# ----------------------------------------------------------------------------
cat > "$SYSD/ai4artsed-gpu.service" <<EOF
[Unit]
Description=AI4ArtsEd GPU Service (port 17803)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$REPO
Environment=HOME=/home/$USER_NAME
Environment=RECORD=0
Environment=PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
ExecStart=/usr/bin/bash $REPO/2_start_gpu_service.sh
Restart=always
RestartSec=15
TimeoutStartSec=300
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "[✓] wrote ai4artsed-gpu.service"

# ----------------------------------------------------------------------------
# 2) ComfyUI (17804)
# ----------------------------------------------------------------------------
cat > "$SYSD/ai4artsed-comfyui.service" <<EOF
[Unit]
Description=AI4ArtsEd ComfyUI (port 17804)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$REPO
Environment=HOME=/home/$USER_NAME
Environment=RECORD=0
ExecStart=/usr/bin/bash $REPO/2_start_comfyui.sh
Restart=always
RestartSec=15
TimeoutStartSec=300
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "[✓] wrote ai4artsed-comfyui.service"

# ----------------------------------------------------------------------------
# 3) Backend (17802 — serves lab6000)
# ----------------------------------------------------------------------------
cat > "$SYSD/ai4artsed-backend.service" <<EOF
[Unit]
Description=AI4ArtsEd Backend (port 17802 — serves lab6000.ai4artsed.org)
After=network-online.target ai4artsed-gpu.service ai4artsed-comfyui.service
Wants=network-online.target ai4artsed-gpu.service ai4artsed-comfyui.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$REPO/devserver
Environment=HOME=/home/$USER_NAME
Environment=RECORD=0
Environment=COMFYUI_AUTO_START=false
Environment=DISABLE_API_CACHE=false
Environment=PATH=$PATHENV
ExecStart=/usr/bin/bash $REPO/3_start_backend_dev.sh
Restart=always
RestartSec=5
TimeoutStopSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "[✓] wrote ai4artsed-backend.service"

# ----------------------------------------------------------------------------
# 4) Remove the stale OLD production unit (17801, external mount) — unused
# ----------------------------------------------------------------------------
OLD="ai4artsed-production.service"
if [ -f "$SYSD/$OLD" ]; then
    echo ""
    echo "Removing stale old production unit ($OLD, port 17801)..."
    systemctl stop "$OLD" 2>/dev/null || true
    systemctl disable "$OLD" 2>/dev/null || true
    cp "$SYSD/$OLD" "$REPO/${OLD}.removed.bak"   # reversible backup in repo dir
    rm -f "$SYSD/$OLD"
    echo "[✓] $OLD stopped, disabled, removed (backup: $REPO/${OLD}.removed.bak)"
fi
# Defensive: free port 17801 if anything is still listening there
if command -v lsof >/dev/null && lsof -ti:17801 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Killing leftover listener on 17801..."
    lsof -ti:17801 -sTCP:LISTEN | xargs -r kill
fi

# ----------------------------------------------------------------------------
# 5) Reload, enable on boot, (re)start now
# ----------------------------------------------------------------------------
echo ""
echo "Reloading systemd, enabling + starting services..."
systemctl daemon-reload
systemctl enable ai4artsed-gpu.service ai4artsed-comfyui.service ai4artsed-backend.service
# Start GPU + ComfyUI first, then backend (handover from the manual backend on 17802
# is automatic: 3_start_backend_dev.sh frees the port before launching).
systemctl restart ai4artsed-gpu.service
systemctl restart ai4artsed-comfyui.service
systemctl restart ai4artsed-backend.service

echo ""
echo "=== Status ==="
systemctl --no-pager --lines=0 status ai4artsed-gpu ai4artsed-comfyui ai4artsed-backend \
    | grep -E "●|Active:|Loaded:" || true

echo ""
echo "Backend will be reachable on http://127.0.0.1:17802 within a few seconds."
echo "ComfyUI needs ~30-60s to report healthy (heavy import)."
echo ""
echo "Live logs:   journalctl -fu ai4artsed-backend"
echo "             journalctl -fu ai4artsed-comfyui"
echo "             journalctl -fu ai4artsed-gpu"
echo "Stop/Start:  sudo systemctl stop|start ai4artsed-backend"
echo ""
echo "[✓] Done. lab6000 backend is now supervised (Restart=always + boot-start)."
