"""
GPU Service Configuration

Shared GPU inference service for media generation (Diffusers, HeartMuLa, StableAudio)
and local LLM/VLM inference (llama-cpp-python).
Runs as a standalone Flask/Waitress process on port 17803.
Both dev (17802) and prod (17801) backends call this via HTTP REST.
"""

import os
from pathlib import Path

# --- Server ---
HOST = "127.0.0.1"  # Localhost only — NEVER expose to network
PORT = int(os.environ.get("GPU_SERVICE_PORT", "17803"))
THREADS = 16  # Enough headroom for concurrent HTTP requests while GPU serializes inference

# --- AI Tools Base ---
_AI_TOOLS_BASE = Path(os.environ.get("AI_TOOLS_BASE", str(Path.home() / "ai")))

# --- Diffusers ---
DIFFUSERS_ENABLED = os.environ.get("DIFFUSERS_ENABLED", "true").lower() == "true"
_diffusers_cache_env = os.environ.get("DIFFUSERS_CACHE_DIR", "")
DIFFUSERS_CACHE_DIR = Path(_diffusers_cache_env) if _diffusers_cache_env else None
DIFFUSERS_USE_TENSORRT = os.environ.get("DIFFUSERS_USE_TENSORRT", "false").lower() == "true"
DIFFUSERS_TORCH_DTYPE = os.environ.get("DIFFUSERS_TORCH_DTYPE", "float16")
DIFFUSERS_DEVICE = os.environ.get("DIFFUSERS_DEVICE", "cuda")
DIFFUSERS_ENABLE_ATTENTION_SLICING = os.environ.get("DIFFUSERS_ENABLE_ATTENTION_SLICING", "true").lower() == "true"
DIFFUSERS_ENABLE_VAE_TILING = os.environ.get("DIFFUSERS_ENABLE_VAE_TILING", "false").lower() == "true"
DIFFUSERS_VRAM_RESERVE_MB = int(os.environ.get("DIFFUSERS_VRAM_RESERVE_MB", "3072"))
DIFFUSERS_TENSORRT_MODELS = {
    "sd35_large": "stabilityai/stable-diffusion-3.5-large-tensorrt",
    "sd35_medium": "stabilityai/stable-diffusion-3.5-medium-tensorrt",
}
_SERVER_BASE = Path(os.environ.get("SERVER_BASE", str(_AI_TOOLS_BASE / "ai4artsed_webserver")))
LORA_DIR = Path(os.environ.get("LORA_DIR", str(_SERVER_BASE / "dlbackend" / "ComfyUI" / "models" / "loras")))
DIFFUSERS_FLUX2_QUANTIZE = os.environ.get("DIFFUSERS_FLUX2_QUANTIZE", "fp8")  # bf16 or fp8
DIFFUSERS_WAN22_QUANTIZE = os.environ.get("DIFFUSERS_WAN22_QUANTIZE", "bf16")  # bf16 or fp8

# Peak VRAM (MB) during inference — measured Session 268 (2026-03-18) on RTX PRO 6000
# Blackwell 96GB via nvidia-smi peak monitoring. CPU-offloaded models report ~0 via
# torch.cuda.memory_allocated(), so these static values are used by the coordinator.
MODEL_PEAK_VRAM_MB = {
    "sd35_large_fp16": 30_000,    # measured: 30253 MiB
    "sd35_large_bf16": 30_000,
    "flux2_bf16": 55_000,         # measured via ComfyUI: 54712 MiB peak
    "flux2_fp8": 33_000,          # measured via Diffusers FP8: 32055 MiB (gen failed, min peak)
    "wan22_t2v_bf16": 39_000,     # measured via ComfyUI: 39290 MiB peak
    "wan22_t2v_fp8": 20_000,
    "wan22_t2v_moe_bf16": 39_000, # measured via ComfyUI (A14B MoE): 39290 MiB peak
    "wan22_t2v_moe_fp8": 22_000,
    "wan22_i2v_bf16": 39_000,     # estimated same arch as T2V
    "wan22_i2v_fp8": 20_000,
    "wan22_i2v_moe_bf16": 39_000,
    "wan22_i2v_moe_fp8": 24_000,
}

# --- HeartMuLa ---
HEARTMULA_ENABLED = os.environ.get("HEARTMULA_ENABLED", "true").lower() == "true"
HEARTMULA_MODEL_PATH = os.environ.get(
    "HEARTMULA_MODEL_PATH",
    str(_AI_TOOLS_BASE / "heartlib" / "ckpt")
)
HEARTMULA_VERSION = os.environ.get("HEARTMULA_VERSION", "3B")
HEARTMULA_LAZY_LOAD = os.environ.get("HEARTMULA_LAZY_LOAD", "true").lower() == "true"
HEARTMULA_DEVICE = os.environ.get("HEARTMULA_DEVICE", "cuda")

# --- Stable Audio ---
STABLE_AUDIO_ENABLED = os.environ.get("STABLE_AUDIO_ENABLED", "true").lower() == "true"
STABLE_AUDIO_MODEL_ID = os.environ.get("STABLE_AUDIO_MODEL_ID", "stabilityai/stable-audio-open-1.0")
STABLE_AUDIO_DEVICE = os.environ.get("STABLE_AUDIO_DEVICE", "cuda")
STABLE_AUDIO_DTYPE = os.environ.get("STABLE_AUDIO_DTYPE", "float16")
STABLE_AUDIO_LAZY_LOAD = os.environ.get("STABLE_AUDIO_LAZY_LOAD", "true").lower() == "true"
STABLE_AUDIO_MAX_DURATION = 47.55  # seconds (model maximum)
STABLE_AUDIO_SAMPLE_RATE = 44100

# --- Crossmodal Lab ---
CROSS_AESTHETIC_ENABLED = os.environ.get("CROSS_AESTHETIC_ENABLED", "true").lower() == "true"
CLIP_VISION_MODEL_ID = os.environ.get("CLIP_VISION_MODEL_ID", "openai/clip-vit-large-patch14")

# ImageBind (gradient guidance)
IMAGEBIND_ENABLED = os.environ.get("IMAGEBIND_ENABLED", "true").lower() == "true"
IMAGEBIND_MODEL_ID = os.environ.get("IMAGEBIND_MODEL_ID", "facebook/imagebind-huge")

# MMAudio (CVPR 2025 Video-to-Audio)
MMAUDIO_ENABLED = os.environ.get("MMAUDIO_ENABLED", "true").lower() == "true"
MMAUDIO_MODEL = os.environ.get("MMAUDIO_MODEL", "large_44k_v2")
MMAUDIO_REPO = os.environ.get("MMAUDIO_REPO", str(_AI_TOOLS_BASE / "MMAudio"))

# --- Text/LLM (Latent Text Lab) ---
TEXT_ENABLED = os.environ.get("TEXT_ENABLED", "true").lower() == "true"
TEXT_DEVICE = os.environ.get("TEXT_DEVICE", "cuda")
TEXT_DEFAULT_DTYPE = os.environ.get("TEXT_DEFAULT_DTYPE", "bfloat16")
TEXT_VRAM_RESERVE_MB = int(os.environ.get("TEXT_VRAM_RESERVE_MB", "2048"))

# Model preset scenarios for Bias Archaeology
# "qwen": Same family, different sizes → isolates size effects
# "mixed": Different families, similar sizes → isolates tokenizer/training effects
TEXT_PRESET_SCENARIOS = {
    "qwen": {
        "tiny": {
            "id": "Qwen/Qwen3-1.7B",
            "vram_gb": 4.0,
            "description": "Qwen3 1.7B - Fast iteration"
        },
        "small": {
            "id": "Qwen/Qwen3-4B",
            "vram_gb": 8.0,
            "description": "Qwen3 4B - Good balance"
        },
        "medium": {
            "id": "Qwen/Qwen3-8B",
            "vram_gb": 16.0,
            "description": "Qwen3 8B - Strong mid-range"
        },
        "large": {
            "id": "Qwen/Qwen3-14B",
            "vram_gb": 28.0,
            "description": "Qwen3 14B - Best quality"
        },
    },
    "mixed": {
        "qwen": {
            "id": "Qwen/Qwen3-4B",
            "vram_gb": 8.0,
            "description": "Qwen3 4B - Qwen tokenizer"
        },
        "phi": {
            "id": "microsoft/Phi-3.5-mini-instruct",
            "vram_gb": 8.0,
            "description": "Phi 3.5 Mini 3.8B - Microsoft tokenizer"
        },
        "llama": {
            "id": "meta-llama/Llama-3.2-3B-Instruct",
            "vram_gb": 7.0,
            "description": "Llama 3.2 3B - Meta tokenizer"
        },
        "gemma": {
            "id": "google/gemma-2-2b-it",
            "vram_gb": 6.0,
            "description": "Gemma 2 2B - Google tokenizer"
        },
    },
}

# Default preset (backward compat)
TEXT_MODEL_PRESETS = TEXT_PRESET_SCENARIOS["qwen"]

# Quantization VRAM multipliers
TEXT_QUANT_MULTIPLIERS = {
    "bf16": 1.0,
    "fp16": 1.0,
    "int8": 0.5,
    "int4": 0.25,
    "nf4": 0.25,  # bitsandbytes NormalFloat4
}

# --- VRAM Watchdog ---
VRAM_USE_NVML = os.environ.get("VRAM_USE_NVML", "true").lower() == "true"
VRAM_FOREIGN_OVERHEAD_MB = int(os.environ.get("VRAM_FOREIGN_OVERHEAD_MB", "2048"))  # CUDA context + driver overhead
VRAM_BLACKLISTED_PORTS = [7801, 7821, 8188]  # SwarmUI ports — NEVER tolerated
COMFYUI_PORT = int(os.environ.get("COMFYUI_PORT", "17804"))  # Expected ComfyUI

# --- Hunyuan3D-2 ---
HUNYUAN3D_ENABLED = os.environ.get("HUNYUAN3D_ENABLED", "true").lower() == "true"
HUNYUAN3D_MODEL_ID = os.environ.get("HUNYUAN3D_MODEL_ID", "tencent/Hunyuan3D-2")
HUNYUAN3D_DEVICE = os.environ.get("HUNYUAN3D_DEVICE", "cuda")
HUNYUAN3D_DTYPE = os.environ.get("HUNYUAN3D_DTYPE", "float16")

