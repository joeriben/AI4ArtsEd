"""
GPU Service Configuration

Shared GPU inference service for media generation (Diffusers, HeartMuLa, StableAudio).
Runs as a standalone Flask/Waitress process on port 17803.
Both dev (17802) and prod (17801) backends call this via HTTP REST.
LLM inference is handled directly by Ollama via LLMClient — NOT by GPU Service.
"""

import os
from pathlib import Path

# --- Server ---
HOST = "127.0.0.1"  # Localhost only — NEVER expose to network
PORT = int(os.environ.get("GPU_SERVICE_PORT", "17803"))
THREADS = 4  # GPU is the bottleneck, not I/O

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

# Model presets with VRAM estimates (bf16)
# Used for auto-quantization decisions
TEXT_MODEL_PRESETS = {
    "tiny": {
        "id": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
        "vram_gb": 4.0,
        "description": "SmolLM2 1.7B - Fast iteration"
    },
    "small": {
        "id": "Qwen/Qwen2.5-3B-Instruct",
        "vram_gb": 7.0,
        "description": "Qwen 2.5 3B - Different tokenizer"
    },
    "nemo": {
        "id": "mistralai/Mistral-Nemo-Instruct-2407",
        "vram_gb": 24.0,
        "description": "Mistral Nemo 12B - Sliding window attention"
    },
    "large": {
        "id": "Qwen/Qwen2.5-14B-Instruct",
        "vram_gb": 30.0,
        "description": "Qwen 2.5 14B - Best quality"
    },
}

# Quantization VRAM multipliers
TEXT_QUANT_MULTIPLIERS = {
    "bf16": 1.0,
    "fp16": 1.0,
    "int8": 0.5,
    "int4": 0.25,
    "nf4": 0.25,  # bitsandbytes NormalFloat4
}

