#!/bin/bash
# AI4ArtsEd DevServer - Setup Script
# Creates venv, exports directory, builds frontend, prepares for configuration

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

echo -e "${BLUE}=== AI4ArtsEd DevServer - Setup ===${NC}"
echo ""
echo "This script will:"
echo "  1. Create Python virtual environment (python3.13)"
echo "  2. Install Python dependencies, in the order requirements.txt names"
echo "  3. Create exports directories"
echo "  4. Build frontend production bundle"
echo ""
echo "Installation directory: $SCRIPT_DIR"
echo ""

# Check Python version: 3.13, the one the pinned torch wheels are built for
# (requirements.txt, check_prerequisites.sh).
echo -e "${BLUE}[Checking]${NC} Python version..."
if ! command -v python3.13 &> /dev/null; then
    echo -e "${RED}[✗]${NC} python3.13 not found. The platform needs Python 3.13 (see check_prerequisites.sh)."
    exit 1
fi
echo -e "${GREEN}[✓]${NC} $(python3.13 --version) found"

# Check Node.js version
echo -e "${BLUE}[Checking]${NC} Node.js version..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}[✗]${NC} Node.js not found. Please install Node.js 20+ first."
    exit 1
fi

NODE_VERSION=$(node --version | cut -d 'v' -f 2 | cut -d '.' -f 1)
if [ "$NODE_VERSION" -lt 20 ]; then
    echo -e "${RED}[✗]${NC} Node.js v$NODE_VERSION found. Node.js v20+ required."
    exit 1
fi

echo -e "${GREEN}[✓]${NC} Node.js $(node --version) found"

# Step 1: Create Python virtual environment
echo ""
echo -e "${BLUE}[1/4]${NC} Creating Python virtual environment..."

if [ -d "venv" ]; then
    echo -e "${YELLOW}[⚠]${NC} Virtual environment already exists"
    read -p "Recreate it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3.13 -m venv venv
        echo -e "${GREEN}[✓]${NC} Virtual environment recreated"
    else
        echo -e "${BLUE}[→]${NC} Keeping existing venv"
    fi
else
    python3.13 -m venv venv
    echo -e "${GREEN}[✓]${NC} Virtual environment created"
fi

# Activate venv and install dependencies
echo -e "${BLUE}[Installing]${NC} Python dependencies..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip > /dev/null 2>&1

# Install dependencies, in the order requirements.txt names: the PyTorch
# stack first (its pinned wheels), then requirements.txt, then the git
# packages. Until 2026-10-10 this installed requirements.txt alone (S-048).
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}[✗]${NC} requirements.txt not found!"
    exit 1
fi
pip install -r deployment/requirements-torch.txt
pip install -r requirements.txt
pip install -r deployment/requirements-git.txt
python scripts/validate_transformers_runtime.py
echo -e "${GREEN}[✓]${NC} Python dependencies installed"

# SpaCy NER models for the Stage-1 DSGVO check (pinned wheels).
# The devserver refuses to start when they are missing (devserver/my_app/__init__.py).
echo -e "${BLUE}[Installing]${NC} SpaCy NER models (DSGVO check)..."
pip install -r deployment/requirements-spacy.txt
echo -e "${GREEN}[✓]${NC} SpaCy NER models installed"

deactivate

# Step 2: Create exports directories
echo ""
echo -e "${BLUE}[2/4]${NC} Creating exports directories..."

mkdir -p exports/json
echo -e "${GREEN}[✓]${NC} Exports directories created"

# Step 3: Build frontend
echo ""
echo -e "${BLUE}[3/4]${NC} Building frontend production bundle..."

if [ ! -d "public/ai4artsed-frontend" ]; then
    echo -e "${RED}[✗]${NC} Frontend directory not found!"
    exit 1
fi

cd public/ai4artsed-frontend

# Install npm dependencies
echo -e "${BLUE}[Installing]${NC} npm dependencies (this may take a few minutes)..."
npm install

# Build production bundle
echo -e "${BLUE}[Building]${NC} frontend bundle..."
npm run build

if [ -f "dist/index.html" ]; then
    echo -e "${GREEN}[✓]${NC} Frontend built successfully"
else
    echo -e "${RED}[✗]${NC} Frontend build failed!"
    exit 1
fi

cd "$SCRIPT_DIR"

# Step 4: Configuration reminder
echo ""
echo -e "${BLUE}[4/4]${NC} Configuration needed:"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "  1. ${BLUE}Install ComfyUI and the platform's nodes${NC} (ComfyUI under dlbackend/ComfyUI):"
echo "     ${BLUE}./install_comfyui_nodes.sh${NC}  (or COMFYUI_PATH=/path/to/ComfyUI ./install_comfyui_nodes.sh)"
echo "     then the models: ${BLUE}./download_models.sh${NC}"
echo ""
echo "  2. Settings: ${BLUE}devserver/user_settings.json${NC} (copy user_settings.json.example),"
echo "     or the Settings page once the server runs (UI mode, safety level, models)."
echo "     PORT: 17802 by default (devserver/config.py); 5_start_backend_prod.sh exports 17801."
echo ""
echo "  3. Provider keys: one key file per provider under devserver/, named in"
echo "     ${BLUE}devserver/config/llm_providers.json${NC} (key_file), or the env_var it names."
echo ""
echo "  4. See ${BLUE}docs/installation/INSTALLATION.md${NC} for the whole path"
echo ""
echo -e "${GREEN}[✓]${NC} Setup complete!"
echo ""
echo "To start the server:"
echo "  ${BLUE}cd devserver${NC}"
echo "  ${BLUE}source ../venv/bin/activate${NC}"
echo "  ${BLUE}python3 server.py${NC}"
echo ""
