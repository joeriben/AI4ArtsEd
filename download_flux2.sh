#!/bin/bash
# AI4ArtsEd DevServer - Flux 2 Component Downloader
#
# Downloads the ComfyUI-ready Flux 2 components (text encoders, diffusion model,
# VAE) from the canonical Comfy-Org/flux2-dev HuggingFace repository.
#
# This script does NOT download:
#   - flux2-dev.safetensors (BF16 full checkpoint, 61 GB):
#       lives in black-forest-labs/FLUX.2-dev — pull the full Diffusers repo
#       via huggingface-cli or rely on Diffusers' lazy cache.
#   - mistral_3_small_flux2.safetensors (FP16 16-bit text encoder, 12 GB):
#       not published in Comfy-Org/flux2-dev. The fp8 and bf16 variants below
#       cover all production paths; FP16 is only needed for niche workflows.
#   - flux2_berthe_morisot.safetensors (workshop-specific LoRA):
#       no canonical public source.
#
# Idempotent: safe to re-run, skips existing files.
#
# Architecture: AI4ArtsEd uses a single-directory layout. ComfyUI lives at
#   <repo>/dlbackend/ComfyUI/
# Override the target by exporting COMFYUI_PATH before running.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
COMFYUI_PATH="${COMFYUI_PATH:-${SCRIPT_DIR}/dlbackend/ComfyUI}"

echo -e "${BLUE}=== AI4ArtsEd Flux 2 Component Downloader ===${NC}"
echo ""
echo "ComfyUI path:   $COMFYUI_PATH"
echo "Total download: ~70 GB (fp8 ~17 GB + bf16 ~34 GB + diffusion ~35 GB + vae ~0.3 GB)"
echo "Estimated time: 30-90 minutes (100 Mbps)"
echo ""

if [ ! -d "$COMFYUI_PATH" ]; then
    echo -e "${YELLOW}Warning:${NC} ComfyUI directory not found at $COMFYUI_PATH"
    echo "Creating it now. If you intended a different path, set COMFYUI_PATH and re-run."
    mkdir -p "$COMFYUI_PATH"
fi

DOWNLOADER="wget"
if command -v aria2c >/dev/null 2>&1; then
    echo -e "${GREEN}Using aria2c for faster downloads${NC}"
    DOWNLOADER="aria2c"
fi

CLIP_DIR="${COMFYUI_PATH}/models/clip"
DM_DIR="${COMFYUI_PATH}/models/checkpoints/Flux1"
VAE_DIR="${COMFYUI_PATH}/models/vae/Flux"

echo -e "${BLUE}[1/4]${NC} Creating directories..."
mkdir -p "$CLIP_DIR" "$DM_DIR" "$VAE_DIR"
echo -e "${GREEN}✓${NC} Directories ready"
echo ""

# Source repo: https://huggingface.co/Comfy-Org/flux2-dev
HF_BASE="https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files"

# Text encoders — pick one for your VRAM:
#   fp8  (~17 GB) — RTX 4090 / 24 GB class, recommended for 4090
#   bf16 (~34 GB) — Blackwell / 48 GB+, full precision
echo -e "${BLUE}[2/4]${NC} Downloading Mistral 3 Small text encoders (FP8 + BF16)..."
download_file \
    "${HF_BASE}/text_encoders/mistral_3_small_flux2_fp8.safetensors" \
    "${CLIP_DIR}/mistral_3_small_flux2_fp8.safetensors"
download_file \
    "${HF_BASE}/text_encoders/mistral_3_small_flux2_bf16.safetensors" \
    "${CLIP_DIR}/mistral_3_small_flux2_bf16.safetensors"
echo ""

# Diffusion model (FP8 mixed, ComfyUI-ready)
echo -e "${BLUE}[3/4]${NC} Downloading Flux 2 diffusion model (FP8 mixed, ~35 GB)..."
download_file \
    "${HF_BASE}/diffusion_models/flux2_dev_fp8mixed.safetensors" \
    "${DM_DIR}/flux2_dev_fp8mixed.safetensors"
echo ""

# VAE
echo -e "${BLUE}[4/4]${NC} Downloading Flux 2 VAE (~321 MB)..."
download_file \
    "${HF_BASE}/vae/flux2-vae.safetensors" \
    "${VAE_DIR}/flux2-vae.safetensors"
echo ""

echo "==================================="
echo -e "${BLUE}Verification:${NC}"
echo "==================================="

MODELS_OK=true

check_model "${CLIP_DIR}/mistral_3_small_flux2_fp8.safetensors"   "Mistral 3 Small FP8"
check_model "${CLIP_DIR}/mistral_3_small_flux2_bf16.safetensors"  "Mistral 3 Small BF16"
check_model "${DM_DIR}/flux2_dev_fp8mixed.safetensors"            "Flux 2 Diffusion FP8mixed"
check_model "${VAE_DIR}/flux2-vae.safetensors"                    "Flux 2 VAE"

echo ""

if $MODELS_OK; then
    echo -e "${GREEN}=== Download Complete! ===${NC}"
    echo ""
    echo "Total Flux 2 size on disk:"
    du -sh "${CLIP_DIR}/mistral_3_small_flux2_"*.safetensors "${DM_DIR}/flux2_dev_fp8mixed.safetensors" "${VAE_DIR}/flux2-vae.safetensors" 2>/dev/null | tail -4
    echo ""
    echo "Optional extras (NOT downloaded by this script):"
    echo "  - BF16 full checkpoint (61 GB):  see black-forest-labs/FLUX.2-dev"
    echo "  - FP16 text encoder (12 GB):     not on canonical HF; convert manually if needed"
    echo "  - flux2_berthe_morisot LoRA:     workshop-specific, procure separately"
    echo ""
    echo "See docs/installation/MODELS_REQUIRED.md for the full model inventory."
else
    echo -e "${RED}=== Download Failed ===${NC}"
    echo ""
    echo "Some Flux 2 files failed to download. Please check errors above."
    echo "You can re-run this script to resume downloads."
    exit 1
fi
