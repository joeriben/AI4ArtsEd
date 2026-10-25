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

# 1. Check Disk Space (on the partition that holds the repo / $HOME)
echo -e "${BLUE}[1/11]${NC} Checking disk space..."
SCRIPT_DIR_FOR_DF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_SPACE=$((700 * 1024 * 1024)) # ~700 GB in KB — full model inventory ≈ 616 GB plus headroom
AVAILABLE_SPACE=$(df "$SCRIPT_DIR_FOR_DF" 2>/dev/null | tail -1 | awk '{print $4}' || df "$HOME" | tail -1 | awk '{print $4}')

if [ "$AVAILABLE_SPACE" -gt "$REQUIRED_SPACE" ]; then
    echo -e "${GREEN}${CHECK}${NC} Disk space: $(format_size $((AVAILABLE_SPACE * 1024))) available (need ~700GB for full model set)"
else
    echo -e "${RED}${CROSS}${NC} Disk space: Only $(format_size $((AVAILABLE_SPACE * 1024))) available (need ~700GB for full model set)"
    FAILED=$((FAILED + 1))
fi

# 2. Check RAM
echo -e "${BLUE}[2/11]${NC} Checking RAM..."
TOTAL_RAM=$(free -g | awk '/^Mem:/ {print $2}')
if [ "$TOTAL_RAM" -ge 16 ]; then
    echo -e "${GREEN}${CHECK}${NC} RAM: ${TOTAL_RAM}GB (recommended 16GB+)"
else
    echo -e "${YELLOW}${WARNING}${NC} RAM: ${TOTAL_RAM}GB (recommended 16GB+, might struggle)"
    WARNINGS=$((WARNINGS + 1))
fi

# 3. Check GPU
echo -e "${BLUE}[3/11]${NC} Checking GPU..."
if command_exists nvidia-smi; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        echo -e "${GREEN}${CHECK}${NC} GPU: $GPU_INFO"

        # Architecture. The platform is built and run on Blackwell (sm_120):
        # llama-server is compiled with -DCMAKE_CUDA_ARCHITECTURES=120 and does
        # not run anywhere else, and the VRAM figures the GPU service budgets
        # with were measured on these cards.
        COMPUTE_CAP=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1 | tr -d ' ')
        if [ "$COMPUTE_CAP" = "12.0" ]; then
            echo -e "${GREEN}${CHECK}${NC} GPU architecture: Blackwell (compute capability $COMPUTE_CAP)"
        elif [ -n "$COMPUTE_CAP" ]; then
            echo -e "${RED}${CROSS}${NC} GPU architecture: compute capability $COMPUTE_CAP — the platform requires 12.0 (Blackwell: RTX PRO 6000 Blackwell, RTX 5090)"
            FAILED=$((FAILED + 1))
        else
            echo -e "${YELLOW}${WARNING}${NC} GPU architecture: this driver does not report compute_cap; 12.0 (Blackwell) is required"
            WARNINGS=$((WARNINGS + 1))
        fi

        # VRAM. A floor, not a recommendation: the smaller of the two supported
        # cards is the RTX 5090 with 32 GB, and every VRAM figure the GPU service
        # budgets and evicts with was measured against that card. Below it the
        # platform does not run.
        VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ -z "$VRAM_MB" ]; then
            echo -e "${YELLOW}${WARNING}${NC} VRAM: this driver does not report memory.total; 32 GB is required"
            WARNINGS=$((WARNINGS + 1))
        elif [ "$VRAM_MB" -lt 32000 ]; then
            echo -e "${RED}${CROSS}${NC} VRAM: ${VRAM_MB}MB — the platform requires a 32 GB card (RTX 5090 or larger)"
            FAILED=$((FAILED + 1))
        else
            echo -e "${GREEN}${CHECK}${NC} VRAM: ${VRAM_MB}MB"
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
echo -e "${BLUE}[4/11]${NC} Checking CUDA version..."
if command_exists nvidia-smi; then
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}' | cut -d. -f1)
    # 13.0 is the platform's line, not a preference: the PyTorch stack is the
    # cu130 nightly (deployment/requirements-torch.txt) and llama.cpp is built
    # against the CUDA 13 toolkit. A 12.x driver runtime cannot load either.
    if [ -n "$CUDA_VERSION" ] && [ "$CUDA_VERSION" -ge 13 ]; then
        echo -e "${GREEN}${CHECK}${NC} CUDA: Version $(nvidia-smi | grep "CUDA Version" | awk '{print $9}')"
    else
        echo -e "${RED}${CROSS}${NC} CUDA: Version $CUDA_VERSION (need 13.0+ — the cu130 torch stack and the llama.cpp build)"
        FAILED=$((FAILED + 1))
    fi
fi

# 5. Check Python (current platform requires 3.13 to match the cu130 nightly wheels)
echo -e "${BLUE}[5/11]${NC} Checking Python..."
if command_exists python3.13; then
    PYTHON_VERSION=$(python3.13 --version | awk '{print $2}')
    echo -e "${GREEN}${CHECK}${NC} Python: $PYTHON_VERSION (need 3.13)"
elif command_exists python3; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -eq 13 ]; then
        echo -e "${GREEN}${CHECK}${NC} Python: $PYTHON_VERSION (need 3.13)"
    else
        echo -e "${RED}${CROSS}${NC} Python: $PYTHON_VERSION (need 3.13 — install python3.13)"
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${RED}${CROSS}${NC} Python: python3 not found"
    FAILED=$((FAILED + 1))
fi

# 6. Check SpaCy NER Models
echo -e "${BLUE}[6/11]${NC} Checking SpaCy NER models..."
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
        echo -e "        Install: venv/bin/pip install -r deployment/requirements-spacy.txt"
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${YELLOW}${WARNING}${NC} SpaCy: venv not found, cannot check (run setup first)"
    WARNINGS=$((WARNINGS + 1))
fi

# 7. Check llama-server binary (LLM/VLM engine: supervised llama.cpp children)
echo -e "${BLUE}[7/11]${NC} Checking llama-server binary..."
# Same resolution as gpu_service/config.py: LLAMA_SERVER_BIN, else
# <AI_TOOLS_BASE>/llama.cpp/build/bin/llama-server, with AI_TOOLS_BASE defaulting to
# the repo root (nested-tools layout, same convention as dlbackend/ComfyUI).
AI_TOOLS_BASE_RESOLVED="${AI_TOOLS_BASE:-$SCRIPT_DIR}"
LLAMA_SERVER_PATH="${LLAMA_SERVER_BIN:-$AI_TOOLS_BASE_RESOLVED/llama.cpp/build/bin/llama-server}"

if [ -x "$LLAMA_SERVER_PATH" ]; then
    LLAMA_SERVER_VERSION=$("$LLAMA_SERVER_PATH" --version 2>&1 | grep -m1 "version:" || true)
    if [ -n "$LLAMA_SERVER_VERSION" ]; then
        echo -e "${GREEN}${CHECK}${NC} llama-server: ${LLAMA_SERVER_VERSION}"
        echo -e "        Path: $LLAMA_SERVER_PATH"
        echo -e "        Pinned commit: see docs/installation/SOFTWARE_VERSIONS.md"
    else
        echo -e "${RED}${CROSS}${NC} llama-server: $LLAMA_SERVER_PATH ran but printed no version line"
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${RED}${CROSS}${NC} llama-server: not found or not executable"
    echo -e "        Expected: $LLAMA_SERVER_PATH"
    echo -e "        Build it: Phase 3.4 of docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md"
    echo -e "        Elsewhere: set LLAMA_SERVER_BIN (or AI_TOOLS_BASE) for every entry point"
    FAILED=$((FAILED + 1))
fi

# 8. Check Node.js
echo -e "${BLUE}[8/11]${NC} Checking Node.js..."
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

# 9. Check Ports. LLM/VLM inference runs as llama-server children on loopback
#    ports 17810-17849 (GPU service port + 7, 40 ports); a busy one is skipped by
#    the supervisor, so only the fixed service ports are checked here.
echo -e "${BLUE}[9/11]${NC} Checking required ports..."
# 17801 = DevServer (prod) | 17802 = DevServer (dev) | 17803 = GPU Service | 17804 = ComfyUI
PORTS=(17801 17803 17804)
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
    echo -e "${GREEN}${CHECK}${NC} Ports: 17801 (backend), 17803 (gpu service), 17804 (comfyui) are available"
fi

# 10. Check Internet Connectivity
echo -e "${BLUE}[10/11]${NC} Checking internet connectivity..."
if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    echo -e "${GREEN}${CHECK}${NC} Internet: Connected"
else
    echo -e "${RED}${CROSS}${NC} Internet: Not connected (required for downloads)"
    FAILED=$((FAILED + 1))
fi

# 11. Check System Packages
echo -e "${BLUE}[11/11]${NC} Checking required system packages..."
MISSING_PACKAGES=()

# Essential packages
PACKAGES=("git" "curl" "wget" "gcc" "make" "cmake")

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
    echo "  1. Follow: docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md"
    echo "  2. API keys (optional, per provider): see Phase 7 of the install guide"
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
