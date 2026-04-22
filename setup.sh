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
echo "  1. Create Python virtual environment"
echo "  2. Install Python dependencies"
echo "  3. Create exports directories"
echo "  4. Build frontend production bundle"
echo ""
echo "Installation directory: $SCRIPT_DIR"
echo ""

# Check Python version
echo -e "${BLUE}[Checking]${NC} Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[✗]${NC} Python 3 not found. Please install Python 3.11+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2 | cut -d '.' -f 1-2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d '.' -f 1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d '.' -f 2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo -e "${RED}[✗]${NC} Python $PYTHON_VERSION found. Python 3.11+ required."
    exit 1
fi

echo -e "${GREEN}[✓]${NC} Python $PYTHON_VERSION found"

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
        python3 -m venv venv
        echo -e "${GREEN}[✓]${NC} Virtual environment recreated"
    else
        echo -e "${BLUE}[→]${NC} Keeping existing venv"
    fi
else
    python3 -m venv venv
    echo -e "${GREEN}[✓]${NC} Virtual environment created"
fi

# Activate venv and install dependencies
echo -e "${BLUE}[Installing]${NC} Python dependencies..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip > /dev/null 2>&1

# Install dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    python scripts/validate_transformers_runtime.py
    echo -e "${GREEN}[✓]${NC} Python dependencies installed"
else
    echo -e "${RED}[✗]${NC} requirements.txt not found!"
    exit 1
fi

deactivate

# Step 2: Create exports directories
echo ""
echo -e "${BLUE}[2/4]${NC} Creating exports directories..."

mkdir -p exports/{json,html,pdf,docx,xml,pipeline_runs}
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
echo "  1. ${BLUE}Install ComfyUI custom nodes${NC} (if SwarmUI is installed):"
echo "     ${BLUE}./install_comfyui_nodes.sh${NC}"
echo "     Or set path: ${BLUE}SWARMUI_PATH=/path/to/SwarmUI ./install_comfyui_nodes.sh${NC}"
echo ""
echo "  2. Edit ${BLUE}devserver/config.py${NC}"
echo "     - Update SWARMUI_BASE_PATH and COMFYUI_BASE_PATH"
echo "     - Set UI_MODE and DEFAULT_SAFETY_LEVEL"
echo "     - Adjust PORT if needed (default: 17801)"
echo ""
echo "  3. Create ${BLUE}devserver/api_keys.json${NC}"
echo "     - Add OpenRouter API key (required)"
echo "     - Add OpenAI API key (optional)"
echo ""
echo "  4. See ${BLUE}docs/installation/CONFIGURATION_GUIDE.md${NC} for details"
echo ""
echo -e "${GREEN}[✓]${NC} Setup complete!"
echo ""
echo "To start the server:"
echo "  ${BLUE}cd devserver${NC}"
echo "  ${BLUE}source ../venv/bin/activate${NC}"
echo "  ${BLUE}python3 server.py${NC}"
echo ""
