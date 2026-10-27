#!/bin/bash
# AI4ArtsEd DevServer - Model Download Script
# Downloads the core ComfyUI checkpoints needed by AI4ArtsEd from HuggingFace,
# including the COMPLETE video generation stack (LTX-Video + Wan 2.2 14B t2v/i2v).
# Idempotent: safe to re-run, skips existing files.
#
# Architecture note: AI4ArtsEd uses a single-directory layout. ComfyUI lives at
#   <repo>/dlbackend/ComfyUI/
# and its model files live under
#   <repo>/dlbackend/ComfyUI/models/
# This script downloads into that tree by default.
#
# Override the target by exporting COMFYUI_PATH before running, e.g. for a
# stand-alone ComfyUI install outside the repo:
#   COMFYUI_PATH=/some/other/ComfyUI ./download_models.sh
#
# NOTE: BOTH SD3.5 repos (stabilityai/stable-diffusion-3.5-large and
# stabilityai/stable-diffusion-3.5-medium) are GATED on HuggingFace — accept
# their license once in a browser, then make a token available (e.g.
# `huggingface-cli login`, or export HF_TOKEN). The SDXL, Wan 2.2, LTX-Video
# and flux_text_encoders sources used here are ungated.

set -e

# Resolve repo root from this script's location, then default ComfyUI path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
COMFYUI_PATH="${COMFYUI_PATH:-${SCRIPT_DIR}/dlbackend/ComfyUI}"

echo -e "${BLUE}=== AI4ArtsEd Model Downloader ===${NC}"
echo ""
echo "ComfyUI path:   $COMFYUI_PATH"
echo "Total download: ~124 GB (SD3.5/SDXL/CLIP/LTX core ~60 GB + Wan 2.2 14B video stack ~64 GB)"
echo "Estimated time: 2.5-3.5 hours (100 Mbps)"
echo ""

# Verify ComfyUI exists (the install_systemd_services.sh step assumes this layout)
if [ ! -d "$COMFYUI_PATH" ]; then
    echo -e "${YELLOW}Warning:${NC} ComfyUI directory not found at $COMFYUI_PATH"
    echo "Creating it now. If you intended a different path, set COMFYUI_PATH and re-run."
    mkdir -p "$COMFYUI_PATH"
fi

# Prefer aria2c for parallel chunks
DOWNLOADER="wget"
if command -v aria2c >/dev/null 2>&1; then
    echo -e "${GREEN}Using aria2c for faster downloads${NC}"
    DOWNLOADER="aria2c"
fi

CHECKPOINTS_DIR="${COMFYUI_PATH}/models/checkpoints"
SD35_DIR="${CHECKPOINTS_DIR}/OfficialStableDiffusion"
CLIP_DIR="${COMFYUI_PATH}/models/clip"
DIFFUSION_DIR="${COMFYUI_PATH}/models/diffusion_models"
VAE_DIR="${COMFYUI_PATH}/models/vae"
LORA_DIR="${COMFYUI_PATH}/models/loras"

# Comfy-Org repackaged Wan 2.2 repo — the canonical ComfyUI-ready source for the
# Wan 2.2 14B video stack (UNETs, LoRAs, the umt5 text encoder, and the Wan 2.1 VAE).
WAN_REPO="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files"

# Create target directories
echo -e "${BLUE}[1/5]${NC} Creating directories..."
mkdir -p "$SD35_DIR" "$CLIP_DIR" "$DIFFUSION_DIR" "$VAE_DIR" "$LORA_DIR"
echo -e "${GREEN}✓${NC} Directories ready"
echo ""

# Download the three checkpoints the image configs and the Latent Lab
# instruments load by name.
#
# SD3.5 Large is the default for the image configs and the model every Latent
# Lab instrument runs, on every card: Large has to fit in 32 GB. Medium is not
# fetched any more; devserver/my_app/services/latent_lab_model.py used to
# answer Medium on cards under 50 GB. SDXL exists for
# Denoising Archaeology:
#   - SDXL   : the second backbone (U-Net instead of MMDiT), the thing the
#              instrument is for — the same prompt denoised by two architectures
#   - Turbo  : the distilled sibling of Large, four steps instead of twenty-five,
#              offered on the main path as sd35_large_turbo
#
# The SDXL file is the 0.9-VAE variant, which is the one ComfyUI ships against;
# it is stored under the name the workflows load (output_image_sdxl.json and
# the archaeology chunk both say sdxl_base.safetensors).
echo -e "${BLUE}[2/5]${NC} Downloading SD3.5 Large + Turbo and SDXL base (~39GB)..."
download_file \
    "https://huggingface.co/stabilityai/stable-diffusion-3.5-large/resolve/main/sd3.5_large.safetensors" \
    "${SD35_DIR}/sd3.5_large.safetensors"
download_file \
    "https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo/resolve/main/sd3.5_large_turbo.safetensors" \
    "${SD35_DIR}/sd3.5_large_turbo.safetensors"
download_file \
    "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0_0.9vae.safetensors" \
    "${SD35_DIR}/sdxl_base.safetensors"
echo ""

# Download CLIP / text encoders used by SD3.5 and the LTX-Video pipeline
echo -e "${BLUE}[3/5]${NC} Downloading CLIP / T5 encoders (~16GB)..."
download_file \
    "https://huggingface.co/stabilityai/stable-diffusion-3.5-large/resolve/main/clip_g.safetensors" \
    "${CLIP_DIR}/clip_g.safetensors"
# Two encoder-only T5-XXL files, the same 220 tensors in two precisions.
# t5xxl_fp16 carries SD3.5: the Diffusers path this platform ran until the move
# to ComfyUI loaded text_encoder_3 in float16, and the SD3.5 graphs
# (TripleCLIPLoader -> clip_name3) name this file, so ComfyUI conditions on the
# same weights. Ungated repo, no token needed.
download_file \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors" \
    "${CLIP_DIR}/t5xxl_fp16.safetensors"
# t5xxl_enconly is the F8_E4M3 half of that pair. It stays for LTX-Video, whose
# chunk (output_video_ltx.json -> CLIPLoader) loads it by this name.
download_file \
    "https://huggingface.co/stabilityai/stable-diffusion-3.5-large/resolve/main/t5xxl_enconly.safetensors" \
    "${CLIP_DIR}/t5xxl_enconly.safetensors"
# clip_l completes SD3.5's THREE text encoders (CLIP-L + CLIP-G + T5-XXL). SD3.5 is
# designed for all three; the Diffusers path uses all three, and the ComfyUI SD3.5
# img2img fallback (output_image_sd35_img2img.json -> TripleCLIPLoader) requires it.
# Pulled from the ungated flux_text_encoders repo (byte-standard CLIP-L, no token needed).
download_file \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
    "${CLIP_DIR}/clip_l.safetensors"
echo ""

# Download LTX-Video
echo -e "${BLUE}[4/5]${NC} Downloading LTX-Video (~15GB)..."
download_file \
    "https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltxv-13b-0.9.7-distilled-fp8.safetensors" \
    "${CHECKPOINTS_DIR}/ltxv-13b-0.9.7-distilled-fp8.safetensors"
echo ""

# Download the Wan 2.2 14B video stack (text-to-video + image-to-video).
# Filenames are canonical — they MUST match the loader names hardcoded in
# devserver/schemas/chunks/output_video_wan22_{t2v_fast,i2v}.json. The single
# shared text encoder (umt5) and VAE are downloaded once; the t2v and i2v
# configs both reference them.
#
# IMPORTANT: the Wan 2.2 14B configs use wan_2.1_vae.safetensors (the Wan 2.1
# VAE, reused by the 14B family). This is a DIFFERENT file from
# wan2.2_vae.safetensors (the 5B-TI2V VAE) — they are NOT interchangeable.
echo -e "${BLUE}[5/5]${NC} Downloading Wan 2.2 14B video stack (~64GB)..."

# Shared text encoder + VAE (used by both the t2v and i2v configs)
download_file \
    "${WAN_REPO}/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
    "${CLIP_DIR}/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
download_file \
    "${WAN_REPO}/vae/wan_2.1_vae.safetensors" \
    "${VAE_DIR}/wan_2.1_vae.safetensors"

# Wan 2.2 text-to-video 14B — UNET pair (high/low noise)
download_file \
    "${WAN_REPO}/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors" \
    "${DIFFUSION_DIR}/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"
download_file \
    "${WAN_REPO}/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors" \
    "${DIFFUSION_DIR}/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"

# Wan 2.2 image-to-video 14B — UNET pair (high/low noise)
download_file \
    "${WAN_REPO}/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" \
    "${DIFFUSION_DIR}/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
download_file \
    "${WAN_REPO}/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" \
    "${DIFFUSION_DIR}/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"

# LightX2V 4-step LoRAs — t2v pair (note the v1.1 in the filename) and i2v pair (v1)
download_file \
    "${WAN_REPO}/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors" \
    "${LORA_DIR}/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors"
download_file \
    "${WAN_REPO}/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors" \
    "${LORA_DIR}/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors"
download_file \
    "${WAN_REPO}/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" \
    "${LORA_DIR}/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
download_file \
    "${WAN_REPO}/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors" \
    "${LORA_DIR}/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"
echo ""

# Verification
echo "==================================="
echo -e "${BLUE}Verification:${NC}"
echo "==================================="

MODELS_OK=true

check_model "${SD35_DIR}/sd3.5_large.safetensors"                                  "SD3.5 Large"
check_model "${SD35_DIR}/sd3.5_large_turbo.safetensors"                            "SD3.5 Large Turbo"
check_model "${SD35_DIR}/sdxl_base.safetensors"                                    "SDXL base (Denoising Archaeology U-Net backbone)"
check_model "${CLIP_DIR}/clip_l.safetensors"                                       "CLIP-L (SD3.5 triple-encoder)"
check_model "${CLIP_DIR}/clip_g.safetensors"                                       "CLIP-G"
check_model "${CLIP_DIR}/t5xxl_fp16.safetensors"                                   "T5-XXL enc-only, fp16 (SD3.5)"
check_model "${CLIP_DIR}/t5xxl_enconly.safetensors"                                "T5-XXL enc-only, fp8 (LTX-Video)"
check_model "${CHECKPOINTS_DIR}/ltxv-13b-0.9.7-distilled-fp8.safetensors"          "LTX-Video checkpoint"
check_model "${CLIP_DIR}/umt5_xxl_fp8_e4m3fn_scaled.safetensors"                   "umt5-XXL (Wan 2.2)"
check_model "${VAE_DIR}/wan_2.1_vae.safetensors"                                   "Wan 2.1 VAE (Wan 2.2 14B)"
check_model "${DIFFUSION_DIR}/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"    "Wan 2.2 t2v UNET (high noise)"
check_model "${DIFFUSION_DIR}/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"     "Wan 2.2 t2v UNET (low noise)"
check_model "${DIFFUSION_DIR}/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"    "Wan 2.2 i2v UNET (high noise)"
check_model "${DIFFUSION_DIR}/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"     "Wan 2.2 i2v UNET (low noise)"
check_model "${LORA_DIR}/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors" "Wan 2.2 t2v LoRA (high noise)"
check_model "${LORA_DIR}/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors"  "Wan 2.2 t2v LoRA (low noise)"
check_model "${LORA_DIR}/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"   "Wan 2.2 i2v LoRA (high noise)"
check_model "${LORA_DIR}/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"    "Wan 2.2 i2v LoRA (low noise)"

echo ""

if $MODELS_OK; then
    echo -e "${GREEN}=== Download Complete! ===${NC}"
    echo ""
    echo "Total size on disk:"
    du -sh "${COMFYUI_PATH}/models"
    echo ""
    echo "This script covers the SD3.5 (Large + Medium) / SDXL / CLIP / LTX core"
    echo "plus the COMPLETE"
    echo "Wan 2.2 14B video stack (text-to-video + image-to-video). All three"
    echo "video output configs (ltx_video, wan22_t2v_video_fast, wan22_i2v_video)"
    echo "now have every model file they need."
    echo ""
    echo "Next: ./download_qwen.sh  (~51 GB — Qwen Image Edit + 2511 multi, required"
    echo "                            for qwen_img2img and qwen_2511_multi configs)"
    echo "      ./download_flux2.sh  (~70 GB — Flux 2 dev + Mistral text encoder)"
    echo "      ./download_flux3.sh  (~20 GB — FLUX 3 Image Klein + Qwen3-VL-4B text encoder;"
    echo "                            gated, needs ComfyUI >= 0.41.0)"
    echo "      ./download_llm_models.sh    (the local language models, models/llm/)"
    echo "      ./download_media_models.sh  (~105 GB — Stable Audio 3, ImageBind, MMAudio,"
    echo "                                   HeartMuLa, Hunyuan3D 2, the media readers,"
    echo "                                   models/<station>/)"
    echo "For the rest of the model inventory (Wan 2.2 TI2V-5B, NER models)"
    echo "see docs/installation/MODELS_REQUIRED.md."
    echo ""
else
    echo -e "${RED}=== Download Failed ===${NC}"
    echo ""
    echo "Some models failed to download. Please check errors above."
    echo "You can re-run this script to resume downloads."
    exit 1
fi
