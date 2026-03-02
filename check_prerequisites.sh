#!/bin/bash
# AI4ArtsEd DevServer - Prerequisites Checker
# Verifies system requirements before installation

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Symbols
CHECK="✓"
CROSS="✗"
WARNING="⚠"

echo -e "${BLUE}=== AI4ArtsEd DevServer - Prerequisites Check ===${NC}"
echo ""

FAILED=0
WARNINGS=0

# Function to check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to format size
format_size() {
    numfmt --to=iec-i --suffix=B "$1" 2>/dev/null || echo "$1"
}

# 1. Check Disk Space
echo -e "${BLUE}[1/10]${NC} Checking disk space..."
REQUIRED_SPACE=$((350 * 1024 * 1024)) # 350GB in KB
AVAILABLE_SPACE=$(df /opt 2>/dev/null | tail -1 | awk '{print $4}' || df / | tail -1 | awk '{print $4}')

if [ "$AVAILABLE_SPACE" -gt "$REQUIRED_SPACE" ]; then
    echo -e "${GREEN}${CHECK}${NC} Disk space: $(format_size $((AVAILABLE_SPACE * 1024))) available (need 350GB)"
else
    echo -e "${RED}${CROSS}${NC} Disk space: Only $(format_size $((AVAILABLE_SPACE * 1024))) available (need 350GB)"
    FAILED=$((FAILED + 1))
fi

# 2. Check RAM
echo -e "${BLUE}[2/10]${NC} Checking RAM..."
TOTAL_RAM=$(free -g | awk '/^Mem:/ {print $2}')
if [ "$TOTAL_RAM" -ge 16 ]; then
    echo -e "${GREEN}${CHECK}${NC} RAM: ${TOTAL_RAM}GB (recommended 16GB+)"
else
    echo -e "${YELLOW}${WARNING}${NC} RAM: ${TOTAL_RAM}GB (recommended 16GB+, might struggle)"
    WARNINGS=$((WARNINGS + 1))
fi

# 3. Check GPU
echo -e "${BLUE}[3/10]${NC} Checking GPU..."
if command_exists nvidia-smi; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        echo -e "${GREEN}${CHECK}${NC} GPU: $GPU_INFO"

        # Check VRAM
        VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ "$VRAM_MB" -lt 16000 ]; then
            echo -e "${YELLOW}${WARNING}${NC} VRAM: ${VRAM_MB}MB (recommended 16GB+ for video generation)"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo -e "${RED}${CROSS}${NC} GPU: nvidia-smi failed to detect GPU"
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${RED}${CROSS}${NC} GPU: nvidia-smi not found (NVIDIA drivers not installed)"
    FAILED=$((FAILED + 1))
fi

# 4. Check CUDA Version
echo -e "${BLUE}[4/10]${NC} Checking CUDA version..."
if command_exists nvidia-smi; then
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}' | cut -d. -f1)
    if [ -n "$CUDA_VERSION" ] && [ "$CUDA_VERSION" -ge 12 ]; then
        echo -e "${GREEN}${CHECK}${NC} CUDA: Version $(nvidia-smi | grep "CUDA Version" | awk '{print $9}')"
    else
        echo -e "${RED}${CROSS}${NC} CUDA: Version $CUDA_VERSION (need 12.0+)"
        FAILED=$((FAILED + 1))
    fi
fi

# 5. Check Python
echo -e "${BLUE}[5/10]${NC} Checking Python..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        echo -e "${GREEN}${CHECK}${NC} Python: $PYTHON_VERSION (need 3.11+)"
    else
        echo -e "${RED}${CROSS}${NC} Python: $PYTHON_VERSION (need 3.11+)"
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${RED}${CROSS}${NC} Python: python3 not found"
    FAILED=$((FAILED + 1))
fi

# 6. Check SpaCy NER Models
echo -e "${BLUE}[6/10]${NC} Checking SpaCy NER models..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    SPACY_MISSING=()
    for MODEL in de_core_news_lg xx_ent_wiki_sm; do
        if ! "$VENV_PYTHON" -c "import spacy; spacy.util.is_package('$MODEL') or exit(1)" 2>/dev/null; then
            SPACY_MISSING+=("$MODEL")
        fi
    done
    if [ ${#SPACY_MISSING[@]} -eq 0 ]; then
        echo -e "${GREEN}${CHECK}${NC} SpaCy: Both NER models installed"
    else
        echo -e "${RED}${CROSS}${NC} SpaCy: Missing models: ${SPACY_MISSING[*]}"
        echo -e "        Install: venv/bin/python -m spacy download ${SPACY_MISSING[*]}"
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${YELLOW}${WARNING}${NC} SpaCy: venv not found, cannot check (run setup first)"
    WARNINGS=$((WARNINGS + 1))
fi

# 7. Check Node.js
echo -e "${BLUE}[7/10]${NC} Checking Node.js..."
if command_exists node; then
    NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d. -f1)
    if [ "$NODE_VERSION" -ge 20 ]; then
        echo -e "${GREEN}${CHECK}${NC} Node.js: v$(node --version | cut -d'v' -f2) (need v20+)"
    else
        echo -e "${RED}${CROSS}${NC} Node.js: v$(node --version | cut -d'v' -f2) (need v20+)"
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${RED}${CROSS}${NC} Node.js: node not found"
    FAILED=$((FAILED + 1))
fi

# 8. Check Ports
echo -e "${BLUE}[8/10]${NC} Checking required ports..."
PORTS=(7801 7821 11434 17801)
PORTS_OK=true

for PORT in "${PORTS[@]}"; do
    if command_exists lsof; then
        if sudo lsof -i :$PORT >/dev/null 2>&1; then
            echo -e "${YELLOW}${WARNING}${NC} Port $PORT is already in use"
            WARNINGS=$((WARNINGS + 1))
            PORTS_OK=false
        fi
    else
        if ss -tuln 2>/dev/null | grep -q ":$PORT "; then
            echo -e "${YELLOW}${WARNING}${NC} Port $PORT is already in use"
            WARNINGS=$((WARNINGS + 1))
            PORTS_OK=false
        fi
    fi
done

if $PORTS_OK; then
    echo -e "${GREEN}${CHECK}${NC} Ports: 7801, 7821, 11434, 17801 are available"
fi

# 9. Check Internet Connectivity
echo -e "${BLUE}[9/10]${NC} Checking internet connectivity..."
if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    echo -e "${GREEN}${CHECK}${NC} Internet: Connected"
else
    echo -e "${RED}${CROSS}${NC} Internet: Not connected (required for downloads)"
    FAILED=$((FAILED + 1))
fi

# 10. Check System Packages
echo -e "${BLUE}[10/10]${NC} Checking required system packages..."
MISSING_PACKAGES=()

# Essential packages
PACKAGES=("git" "curl" "wget" "gcc" "make")

for PKG in "${PACKAGES[@]}"; do
    if ! command_exists "$PKG"; then
        MISSING_PACKAGES+=("$PKG")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo -e "${GREEN}${CHECK}${NC} System packages: All essential packages installed"
else
    echo -e "${YELLOW}${WARNING}${NC} System packages: Missing: ${MISSING_PACKAGES[*]}"
    WARNINGS=$((WARNINGS + 1))
fi

# Summary
echo ""
echo "========================================"
echo -e "${BLUE}Summary:${NC}"
echo "========================================"

if [ $FAILED -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}${CHECK} All checks passed!${NC}"
    echo ""
    echo "Your system meets all requirements for AI4ArtsEd installation."
    echo ""
    echo "Next steps:"
    echo "  1. Get API keys: https://openrouter.ai/keys"
    echo "  2. Follow: docs/installation/QUICKSTART.md"
    echo ""
    exit 0
elif [ $FAILED -eq 0 ]; then
    echo -e "${YELLOW}${WARNING} Passed with $WARNINGS warning(s)${NC}"
    echo ""
    echo "Your system meets minimum requirements, but some issues need attention."
    echo "Installation should work, but performance might be affected."
    echo ""
    exit 0
else
    echo -e "${RED}${CROSS} Failed: $FAILED critical check(s) failed${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}${WARNING} Also $WARNINGS warning(s)${NC}"
    fi
    echo ""
    echo "Your system does NOT meet requirements. Please fix the issues above."
    echo ""
    echo "See: docs/installation/SYSTEM_REQUIREMENTS.md"
    echo ""
    exit 1
fi
