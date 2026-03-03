"""
Output Chunk: Stable Audio Open (Diffusers)

Generates audio from text prompts using Stable Audio Open 1.0 via HuggingFace Diffusers.
This is a Python-based chunk - the code IS the chunk.

Input (from Stage 2/3):
    - prompt (PREVIOUS_OUTPUT): Text description of audio to generate

Output:
    - MP3 audio bytes

Fallback:
    - If generation fails, router auto-falls back to 'output_audio_stableaudio' (ComfyUI)

Usage:
    result = await execute(prompt="Gentle piano melody with soft reverb")
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Chunk metadata (replaces JSON meta section)
CHUNK_META = {
    "name": "output_audio_stableaudio_diffusers",
    "media_type": "audio",
    "output_format": "mp3",
    "backend": "stable_audio",
    "backend_type": "stable_audio",
    "model_id": "stabilityai/stable-audio-open-1.0",
    "fallback_chunk": "output_audio_stableaudio",
    "estimated_duration_seconds": "8-12",
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
    "optimization_instruction": "Transform the input into a clear audio generation prompt; describe the sonic content (instruments, sounds, textures), the acoustic environment (reverb, space, atmosphere), the rhythm and tempo (if applicable), the mood and energy level, and any specific sonic characteristics (pitch, timbre, dynamics); keep it concise and focused on auditory elements; example: 'Gentle piano melody with soft reverb, slow tempo, melancholic mood, warm analog sound, minimal background ambience.'"
}

# Default parameters (replaces JSON input_mappings defaults)
DEFAULTS = {
    "duration_seconds": 30.0,
    "negative_prompt": "",
    "steps": 100,
    "cfg_scale": 7.0,
    "seed": None,  # None = random
    "output_format": "mp3"
}


async def execute(
    prompt: str = None,
    PREVIOUS_OUTPUT: str = None,  # Pipeline convention: previous stage output
    negative_prompt: str = None,
    duration_seconds: float = None,
    steps: int = None,
    cfg_scale: float = None,
    seed: int = None,
    output_format: str = None,
    **kwargs  # Ignore extra parameters from pipeline
) -> bytes:
    """
    Execute Stable Audio generation.

    Args:
        prompt: Text description of audio to generate
        PREVIOUS_OUTPUT: Pipeline convention (mapped to prompt)
        negative_prompt: What to avoid in the generation
        duration_seconds: Duration of audio in seconds (max 47s)
        steps: Number of inference steps (more = higher quality, slower)
        cfg_scale: Classifier Free Guidance scale
        seed: Seed for reproducibility (None = random)
        output_format: Output format: 'mp3' or 'wav'

    Returns:
        Audio bytes (MP3/WAV, ready for storage/response)

    Raises:
        Exception: If generation fails or backend unavailable
    """
    from my_app.services.stable_audio_backend import get_stable_audio_backend
    from my_app.services.backend_registry import get_backend_registry
    import random as random_module

    # Map pipeline convention (PREVIOUS_OUTPUT) to semantic name
    if prompt is None and PREVIOUS_OUTPUT is not None:
        prompt = PREVIOUS_OUTPUT

    # Apply defaults
    negative_prompt = negative_prompt if negative_prompt is not None else DEFAULTS["negative_prompt"]
    duration_seconds = float(duration_seconds) if duration_seconds is not None else DEFAULTS["duration_seconds"]
    steps = int(steps) if steps is not None else DEFAULTS["steps"]
    cfg_scale = float(cfg_scale) if cfg_scale is not None else DEFAULTS["cfg_scale"]
    output_format = output_format if output_format is not None else DEFAULTS["output_format"]

    # Handle seed
    if seed is None or seed == "random" or seed == -1:
        seed = random_module.randint(0, 2**32 - 1)
        logger.info(f"[CHUNK:stable_audio] Generated random seed: {seed}")
    else:
        seed = int(seed)

    # Validate prompt
    if not prompt or not prompt.strip():
        logger.error("[CHUNK:stable_audio] No prompt provided")
        raise ValueError("No prompt provided for audio generation")

    logger.info(f"[CHUNK:stable_audio] Executing: prompt='{prompt[:100]}...', duration={duration_seconds}s, steps={steps}")

    # Check if Stable Audio backend is enabled via registry
    registry = get_backend_registry()
    if not registry.is_enabled("stable_audio"):
        logger.error("[CHUNK:stable_audio] Backend disabled in config")
        raise Exception("Stable Audio backend is disabled in registry")

    # Get backend
    backend = get_stable_audio_backend()

    # Check availability
    if not await backend.is_available():
        logger.error("[CHUNK:stable_audio] Backend not available")
        raise Exception("Stable Audio not available. Check diffusers installation and GPU.")

    # Generate audio
    audio_bytes = await backend.generate_audio(
        prompt=prompt,
        negative_prompt=negative_prompt,
        duration_seconds=duration_seconds,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=seed,
        output_format=output_format
    )

    if audio_bytes is None:
        logger.error("[CHUNK:stable_audio] Generation returned None")
        raise Exception("Audio generation failed (returned None)")

    logger.info(f"[CHUNK:stable_audio] Generated {len(audio_bytes)} bytes (seed={seed}, format={output_format})")

    # Return raw bytes - backend_router will wrap them properly
    return audio_bytes
