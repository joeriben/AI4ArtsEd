#!/bin/bash
# AI4ArtsEd DevServer - Qwen Image Edit Component Downloader
#
# Downloads the ComfyUI-ready Qwen Image Edit components needed by the
# `qwen_img2img` output config (Vue card "Qwen" in image_transformation.vue).
# Without these files the GPU-service availability check reports
# `qwen_img2img: false` and the frontend HIDES the model card (strict mode).
#
# Files for qwen_img2img (see schemas/chunks/output_image_qwen_img2img.json):
#   diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors   (UNETLoader)
#   clip/qwen_2.5_vl_7b_fp8_scaled.safetensors                (CLIPLoader)
#   vae/qwen_image_vae.safetensors                            (VAELoader)
#   loras/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors (Lightning 4-step)
#
# Optional (export QWEN_WITH_2511=true) — adds the `qwen_2511_multi` config's
# extra files (the FP8-mixed 2511 diffusion model + its Lightning LoRA). The
# CLIP encoder and VAE are SHARED with qwen_img2img, so only two extra files.
#   diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors
#   loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
#
# All source repos (Comfy-Org/*, lightx2v/*) are UNGATED — no HF token needed.
# Idempotent: safe to re-run, skips existing files.
#
# Architecture: AI4ArtsEd uses a single-directory layout. ComfyUI lives at
#   <repo>/dlbackend/ComfyUI/
# Override the target by exporting COMFYUI_PATH before running.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
COMFYUI_PATH="${COMFYUI_PATH:-${SCRIPT_DIR}/dlbackend/ComfyUI}"
QWEN_WITH_2511="${QWEN_WITH_2511:-true}"

echo -e "${BLUE}=== AI4ArtsEd Qwen Image Edit Downloader ===${NC}"
echo ""
echo "ComfyUI path:   $COMFYUI_PATH"
if [ "$QWEN_WITH_2511" = "true" ]; then
    echo "Scope:          qwen_img2img + qwen_2511_multi"
    echo "Total download: ~51 GB (edit 20.4 + 2511 20.5 + clip 9.4 + vae 0.3 + 2 LoRAs)"
else
    echo "Scope:          qwen_img2img only (export QWEN_WITH_2511=false skipped the 2511 multi config)"
    echo "Total download: ~30 GB (edit 20.4 + clip 9.4 + vae 0.3 + LoRA)"
fi
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

DM_DIR="${COMFYUI_PATH}/models/diffusion_models"
CLIP_DIR="${COMFYUI_PATH}/models/clip"
VAE_DIR="${COMFYUI_PATH}/models/vae"
LORA_DIR="${COMFYUI_PATH}/models/loras"

echo -e "${BLUE}[1/4]${NC} Creating directories..."
mkdir -p "$DM_DIR" "$CLIP_DIR" "$VAE_DIR" "$LORA_DIR"
echo -e "${GREEN}✓${NC} Directories ready"
echo ""

# Source repos (all ungated, ComfyUI-ready split_files):
#   https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI  (diffusion models)
#   https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI       (shared encoder + VAE)
#   https://huggingface.co/lightx2v/Qwen-Image-Lightning      (Edit Lightning LoRA)
#   https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning (2511 LoRA)
EDIT_BASE="https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files"
SHARED_BASE="https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files"
LORA_BASE="https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main"
LORA_2511_BASE="https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main"

# Diffusion model (FP8 e4m3fn, ComfyUI-ready, ~20.4 GB)
echo -e "${BLUE}[2/4]${NC} Downloading Qwen Image Edit diffusion model (FP8, ~20.4 GB)..."
download_file \
    "${EDIT_BASE}/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors" \
    "${DM_DIR}/qwen_image_edit_fp8_e4m3fn.safetensors"
echo ""

# Shared text encoder (Qwen 2.5 VL 7B, FP8 scaled, ~9.4 GB) + VAE (~254 MB)
echo -e "${BLUE}[3/4]${NC} Downloading shared text encoder (~9.4 GB) + VAE (~254 MB)..."
download_file \
    "${SHARED_BASE}/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
    "${CLIP_DIR}/qwen_2.5_vl_7b_fp8_scaled.safetensors"
download_file \
    "${SHARED_BASE}/vae/qwen_image_vae.safetensors" \
    "${VAE_DIR}/qwen_image_vae.safetensors"
echo ""

# Lightning 4-step LoRA
echo -e "${BLUE}[4/4]${NC} Downloading Qwen Image Edit Lightning 4-step LoRA..."
download_file \
    "${LORA_BASE}/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors" \
    "${LORA_DIR}/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors"
echo ""

# Optional: qwen_2511_multi extras (shares the encoder + VAE downloaded above)
if [ "$QWEN_WITH_2511" = "true" ]; then
    echo -e "${BLUE}[+]${NC} Downloading qwen_2511_multi extras (2511 model ~20.5 GB + LoRA)..."
    download_file \
        "${EDIT_BASE}/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors" \
        "${DM_DIR}/qwen_image_edit_2511_fp8mixed.safetensors"
    download_file \
        "${LORA_2511_BASE}/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors" \
        "${LORA_DIR}/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"
    echo ""
fi

echo "==================================="
echo -e "${BLUE}Verification:${NC}"
echo "==================================="

MODELS_OK=true

check_model "${DM_DIR}/qwen_image_edit_fp8_e4m3fn.safetensors"                  "Qwen Image Edit FP8 (diffusion)"
check_model "${CLIP_DIR}/qwen_2.5_vl_7b_fp8_scaled.safetensors"                 "Qwen 2.5 VL 7B FP8 (text encoder)"
check_model "${VAE_DIR}/qwen_image_vae.safetensors"                            "Qwen Image VAE"
check_model "${LORA_DIR}/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors" "Qwen Edit Lightning 4-step LoRA"
if [ "$QWEN_WITH_2511" = "true" ]; then
    check_model "${DM_DIR}/qwen_image_edit_2511_fp8mixed.safetensors"                   "Qwen Image Edit 2511 FP8mixed"
    check_model "${LORA_DIR}/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors" "Qwen Edit 2511 Lightning LoRA"
fi

echo ""
if [ "$MODELS_OK" = true ]; then
    echo -e "${GREEN}All Qwen components present.${NC}"
    echo "The GPU-service availability cache has a 5-minute TTL — the qwen_img2img"
    echo "card appears in the frontend within ~5 min, or restart ai4artsed-backend"
    echo "to refresh immediately. ComfyUI must be able to see the new files"
    echo "(it scans models/ on its next /object_info query)."
else
    echo -e "${RED}Some components are missing — re-run this script.${NC}"
    exit 1
fi
