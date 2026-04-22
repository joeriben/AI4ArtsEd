#!/bin/bash
# AI4ArtsEd DevServer - Update Script
# Pulls latest code, updates dependencies, rebuilds frontend, restarts services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory (repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}=== AI4ArtsEd DevServer - Update ===${NC}"
echo ""
echo "This script will:"
echo "  1. Pull latest code from git"
echo "  2. Update Python dependencies"
echo "  3. Rebuild frontend"
echo "  4. Restart services (if using systemd)"
echo ""

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "${YELLOW}[⚠]${NC} You have uncommitted changes:"
    git status --short
    echo ""
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}[✗]${NC} Update cancelled"
        exit 1
    fi
fi

# Step 1: Git pull
echo ""
echo -e "${BLUE}[1/4]${NC} Pulling latest code..."

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo -e "${BLUE}[→]${NC} Current branch: $CURRENT_BRANCH"

if git pull origin "$CURRENT_BRANCH"; then
    echo -e "${GREEN}[✓]${NC} Code updated"
else
    echo -e "${RED}[✗]${NC} Git pull failed"
    exit 1
fi

# Step 2: Update Python dependencies
echo ""
echo -e "${BLUE}[2/4]${NC} Updating Python dependencies..."

if [ ! -d "venv" ]; then
    echo -e "${RED}[✗]${NC} Virtual environment not found. Run setup.sh first."
    exit 1
fi

source venv/bin/activate

# Upgrade pip
pip install --upgrade pip > /dev/null 2>&1

# Update dependencies
if pip install -r requirements.txt; then
    python scripts/validate_transformers_runtime.py
    echo -e "${GREEN}[✓]${NC} Python dependencies updated"
else
    echo -e "${RED}[✗]${NC} Failed to update Python dependencies"
    deactivate
    exit 1
fi

deactivate

# Step 3: Rebuild frontend
echo ""
echo -e "${BLUE}[3/4]${NC} Rebuilding frontend..."

cd public/ai4artsed-frontend

# Update npm dependencies
echo -e "${BLUE}[Installing]${NC} npm dependencies..."
npm install

# Rebuild
echo -e "${BLUE}[Building]${NC} frontend bundle..."
if npm run build; then
    echo -e "${GREEN}[✓]${NC} Frontend rebuilt"
else
    echo -e "${RED}[✗]${NC} Frontend build failed"
    exit 1
fi

cd "$SCRIPT_DIR"

# Step 4: Restart services
echo ""
echo -e "${BLUE}[4/4]${NC} Restarting services..."

# Check if systemd services exist
BACKEND_SERVICE="ai4artsed-backend.service"
SWARMUI_SERVICE="ai4artsed-swarmui.service"

SERVICES_RESTARTED=false

# Restart backend service
if systemctl list-unit-files | grep -q "^$BACKEND_SERVICE"; then
    echo -e "${BLUE}[Restarting]${NC} $BACKEND_SERVICE..."
    if sudo systemctl restart "$BACKEND_SERVICE"; then
        echo -e "${GREEN}[✓]${NC} Backend restarted"
        SERVICES_RESTARTED=true
    else
        echo -e "${RED}[✗]${NC} Failed to restart backend"
    fi
else
    echo -e "${YELLOW}[⚠]${NC} systemd service '$BACKEND_SERVICE' not found"
fi

# Optionally restart SwarmUI (usually not needed for code updates)
if systemctl list-unit-files | grep -q "^$SWARMUI_SERVICE"; then
    read -p "Restart SwarmUI? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}[Restarting]${NC} $SWARMUI_SERVICE..."
        if sudo systemctl restart "$SWARMUI_SERVICE"; then
            echo -e "${GREEN}[✓]${NC} SwarmUI restarted"
            SERVICES_RESTARTED=true
        else
            echo -e "${RED}[✗]${NC} Failed to restart SwarmUI"
        fi
    fi
fi

if [ "$SERVICES_RESTARTED" = false ]; then
    echo -e "${YELLOW}[ℹ]${NC} No systemd services found or restarted"
    echo ""
    echo "To manually restart:"
    echo "  ${BLUE}cd devserver${NC}"
    echo "  ${BLUE}source ../venv/bin/activate${NC}"
    echo "  ${BLUE}python3 server.py${NC}"
fi

# Summary
echo ""
echo -e "${GREEN}[✓]${NC} Update complete!"
echo ""

# Show version info
if command -v git &> /dev/null; then
    COMMIT=$(git rev-parse --short HEAD)
    COMMIT_DATE=$(git log -1 --format=%cd --date=short)
    echo "Current version:"
    echo "  Commit: ${BLUE}$COMMIT${NC}"
    echo "  Date: ${BLUE}$COMMIT_DATE${NC}"
    echo ""
fi

# Check service status
if [ "$SERVICES_RESTARTED" = true ]; then
    echo "Service status:"
    if systemctl list-unit-files | grep -q "^$BACKEND_SERVICE"; then
        STATUS=$(systemctl is-active "$BACKEND_SERVICE")
        if [ "$STATUS" = "active" ]; then
            echo -e "  Backend: ${GREEN}$STATUS${NC}"
        else
            echo -e "  Backend: ${RED}$STATUS${NC}"
        fi
    fi

    if systemctl list-unit-files | grep -q "^$SWARMUI_SERVICE"; then
        STATUS=$(systemctl is-active "$SWARMUI_SERVICE")
        if [ "$STATUS" = "active" ]; then
            echo -e "  SwarmUI: ${GREEN}$STATUS${NC}"
        else
            echo -e "  SwarmUI: ${RED}$STATUS${NC}"
        fi
    fi
    echo ""
fi

echo "View logs:"
echo "  ${BLUE}sudo journalctl -u ai4artsed-backend -f${NC}"
echo ""
