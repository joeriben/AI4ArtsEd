#!/bin/bash
# AI4ArtsEd - Systemd Services Installation
# Makes GPU service, backend, and cloudflared start automatically on boot
#
# REQUIRES: sudo privileges
# RUN ONCE: After initial setup on production/remote servers
#
# Usage: sudo ./install_systemd_services.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[✗]${NC} This script must be run with sudo"
    echo "    Usage: sudo ./install_systemd_services.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
if [ "$ACTUAL_USER" = "root" ]; then
    echo -e "${RED}[✗]${NC} Cannot determine actual user. Don't run as root directly."
    echo "    Usage: sudo ./install_systemd_services.sh"
    exit 1
fi

# Get script directory (should be repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVSERVER_DIR="$SCRIPT_DIR/devserver"
GPU_SERVICE_DIR="$SCRIPT_DIR/gpu_service"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
AI_TOOLS_BASE="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}=== AI4ArtsEd - Systemd Services Setup ===${NC}"
echo ""
echo "This will configure automatic startup on boot for:"
echo "  - Cloudflared tunnel (if config exists)"
echo "  - AI4ArtsEd GPU service"
echo "  - AI4ArtsEd backend"
echo ""
echo "Installation directory: $SCRIPT_DIR"
echo "Running as user: $ACTUAL_USER"
echo ""

# Verify required services exist
if [ ! -f "$DEVSERVER_DIR/server.py" ]; then
    echo -e "${RED}[✗]${NC} server.py not found in $DEVSERVER_DIR"
    exit 1
fi

if [ ! -f "$GPU_SERVICE_DIR/server.py" ]; then
    echo -e "${RED}[✗]${NC} server.py not found in $GPU_SERVICE_DIR"
    exit 1
fi

if [ ! -x "$VENV_PYTHON" ]; then
    echo -e "${RED}[✗]${NC} Python executable not found at $VENV_PYTHON"
    exit 1
fi

# Detect port from environment or default
BACKEND_PORT="${PORT:-17801}"
echo -e "${BLUE}[Info]${NC} Backend will run on port $BACKEND_PORT"
echo ""

# ============================================
# Step 1: Cloudflared Service
# ============================================
echo -e "${BLUE}[1/4]${NC} Checking Cloudflared..."

CLOUDFLARED_CONFIG="/etc/cloudflared/config.yml"

if [ -f "$CLOUDFLARED_CONFIG" ]; then
    echo -e "${GREEN}[✓]${NC} Cloudflared config found: $CLOUDFLARED_CONFIG"

    # Check if service file exists
    if [ -f "/etc/systemd/system/cloudflared.service" ]; then
        echo -e "${BLUE}[→]${NC} Cloudflared service already exists"
    else
        echo -e "${BLUE}[Creating]${NC} Cloudflared systemd service..."

        cat > /etc/systemd/system/cloudflared.service << EOF
[Unit]
Description=Cloudflared Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
ExecStart=/usr/local/bin/cloudflared --config $CLOUDFLARED_CONFIG tunnel run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
        echo -e "${GREEN}[✓]${NC} Cloudflared service created"
    fi

    # Enable cloudflared
    systemctl daemon-reload
    systemctl enable cloudflared
    echo -e "${GREEN}[✓]${NC} Cloudflared enabled for boot"

    CLOUDFLARED_ENABLED=true
else
    echo -e "${YELLOW}[⚠]${NC} No cloudflared config at $CLOUDFLARED_CONFIG"
    echo "    Skipping cloudflared setup. Configure manually if needed."
    CLOUDFLARED_ENABLED=false
fi

# ============================================
# Step 2: GPU Service
# ============================================
echo ""
echo -e "${BLUE}[2/4]${NC} Creating AI4ArtsEd GPU service..."

cat > /etc/systemd/system/ai4artsed-gpu.service << EOF
[Unit]
Description=AI4ArtsEd GPU Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$GPU_SERVICE_DIR
Environment=GPU_SERVICE_PORT=17803
Environment=PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
Environment=AI_TOOLS_BASE=$AI_TOOLS_BASE
Environment=HOME=/home/$ACTUAL_USER
Environment=PATH=$SCRIPT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$VENV_PYTHON $GPU_SERVICE_DIR/server.py
Restart=on-failure
RestartSec=15
TimeoutStartSec=300
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}[✓]${NC} GPU service created"

systemctl daemon-reload
systemctl enable ai4artsed-gpu
echo -e "${GREEN}[✓]${NC} GPU service enabled for boot"

# ============================================
# Step 3: Backend Service
# ============================================
echo ""
echo -e "${BLUE}[3/4]${NC} Creating AI4ArtsEd backend service..."

# Determine dependencies
if [ "$CLOUDFLARED_ENABLED" = true ]; then
    AFTER_DEPS="After=network-online.target ai4artsed-gpu.service cloudflared.service"
    WANTS_DEPS="Wants=network-online.target ai4artsed-gpu.service cloudflared.service"
else
    AFTER_DEPS="After=network-online.target ai4artsed-gpu.service"
    WANTS_DEPS="Wants=network-online.target ai4artsed-gpu.service"
fi

cat > /etc/systemd/system/ai4artsed-backend.service << EOF
[Unit]
Description=AI4ArtsEd Backend Server
$AFTER_DEPS
$WANTS_DEPS

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$DEVSERVER_DIR
Environment=PORT=$BACKEND_PORT
Environment=DISABLE_API_CACHE=false
Environment=AI_TOOLS_BASE=$AI_TOOLS_BASE
Environment=HOME=/home/$ACTUAL_USER
Environment=PATH=$SCRIPT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$VENV_PYTHON $DEVSERVER_DIR/server.py
Restart=always
RestartSec=5

# Give time for cleanup on stop
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}[✓]${NC} Backend service created"

# Enable backend
systemctl daemon-reload
systemctl enable ai4artsed-backend
echo -e "${GREEN}[✓]${NC} Backend enabled for boot"

# ============================================
# Step 4: Summary
# ============================================
echo ""
echo -e "${BLUE}[4/4]${NC} Installation complete!"
echo ""
echo -e "${GREEN}=== Summary ===${NC}"
echo ""

if [ "$CLOUDFLARED_ENABLED" = true ]; then
    echo "  Cloudflared:  enabled (starts on boot)"
    echo "                sudo systemctl start cloudflared"
    echo "                sudo systemctl status cloudflared"
else
    echo "  Cloudflared:  not configured"
fi

echo ""
echo "  GPU Service:  enabled (starts on boot, port 17803)"
echo "                sudo systemctl start ai4artsed-gpu"
echo "                sudo systemctl status ai4artsed-gpu"
echo ""
echo "  Backend:      enabled (starts on boot, port $BACKEND_PORT)"
echo "                sudo systemctl start ai4artsed-backend"
echo "                sudo systemctl status ai4artsed-backend"
echo ""
echo -e "${YELLOW}Commands:${NC}"
echo "  Start now:    sudo systemctl start ai4artsed-backend"
echo "  Stop:         sudo systemctl stop ai4artsed-backend"
echo "  Logs:         sudo journalctl -u ai4artsed-backend -f"
echo "  Disable:      sudo systemctl disable ai4artsed-backend"
echo ""
echo -e "${GREEN}[✓]${NC} Server will now start automatically after reboot!"
echo ""
