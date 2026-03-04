"""
Output Chunk: Stable Audio Open (Diffusers)

Generates audio from text prompts using Stable Audio Open 1.0.
Direct extraction of _process_stable_audio_chunk() from backend_router.py.

Input (from pipeline parameters):
    - TEXT_1: Text prompt (from Stage 2/3 output)
    - SECONDS: Duration in seconds (from output config, default 47.6)
    - STEPS: Inference steps (from output config, default 50)
    - CFG: Guidance scale (from output config, default 4.98)
    - NEGATIVE_PROMPT: What to avoid (from output config)
    - seed: Seed for reproducibility

Output:
    - dict with audio_data (base64), matching BackendResponse metadata format

Fallback:
    - If generation fails, router reads CHUNK_META['fallback_chunk']
      and re-enters _process_output_chunk('output_audio_stableaudio') → ComfyUI
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Chunk metadata
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

# Defaults matching the JSON input_mappings
DEFAULTS = {
    "negative_prompt": "",
    "duration_seconds": 30.0,
    "steps": 100,
    "cfg_scale": 7.0,
    "seed": "random",
    "output_format": "mp3"
}


async def execute(
    # Pipeline parameter names (from output config: stableaudio_open.json)
    TEXT_1: str = None,       # Prompt text from Stage 2/3
    TEXT_2: str = None,       # Unused, but pipeline may send it
    NEGATIVE_PROMPT: str = None,
    SECONDS: float = None,    # Duration
    STEPS: int = None,
    CFG: float = None,
    seed: str = None,
    seed_override: int = None,
    OUTPUT_CHUNK: str = None,  # Ignored (router metadata)
    _chunk_name: str = None,   # Ignored (router metadata)
    SAMPLER: str = None,       # ComfyUI param, not used by Diffusers
    SCHEDULER: str = None,     # ComfyUI param, not used by Diffusers
    # Also accept PREVIOUS_OUTPUT in case prompt comes that way
    PREVIOUS_OUTPUT: str = None,
    **kwargs
) -> dict:
    """
    Execute Stable Audio generation via the existing backend service.

    Direct port of backend_router._process_stable_audio_chunk() logic.
    Returns a dict (not bytes) so we control the metadata format.

    Raises:
        Exception: If backend disabled, unavailable, or generation fails.
    """
    from my_app.services.stable_audio_backend import get_stable_audio_backend
    from my_app.services.backend_registry import get_backend_registry
    import random
    import base64

    # --- Check backend availability ---
    registry = get_backend_registry()
    if not registry.is_enabled("stable_audio"):
        raise Exception("Stable Audio backend disabled in registry")

    backend = get_stable_audio_backend()

    if not await backend.is_available():
        raise Exception("Stable Audio backend not available (missing packages or GPU)")

    # --- Map pipeline parameters to backend API ---
    audio_prompt = TEXT_1 or PREVIOUS_OUTPUT or ""

    if not audio_prompt:
        raise ValueError("No prompt provided for audio generation")

    negative_prompt = NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"]
    duration_seconds = float(SECONDS) if SECONDS is not None else DEFAULTS["duration_seconds"]
    steps = int(STEPS) if STEPS is not None else DEFAULTS["steps"]
    cfg_scale = float(CFG) if CFG is not None else DEFAULTS["cfg_scale"]
    output_format = DEFAULTS["output_format"]

    # Seed handling
    actual_seed = seed_override if seed_override is not None else seed
    if actual_seed is None or actual_seed == "random" or actual_seed == -1:
        actual_seed = random.randint(0, 2**32 - 1)
        logger.info(f"[CHUNK:stable_audio] Generated random seed: {actual_seed}")
    else:
        actual_seed = int(actual_seed)

    # --- Generate ---
    logger.info(f"[CHUNK:stable_audio] Generating: prompt='{audio_prompt[:100]}...', duration={duration_seconds}s")
    logger.info(f"[CHUNK:stable_audio] Parameters: steps={steps}, cfg={cfg_scale}, seed={actual_seed}")

    audio_bytes = await backend.generate_audio(
        prompt=audio_prompt,
        negative_prompt=negative_prompt,
        duration_seconds=duration_seconds,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=actual_seed,
        output_format=output_format
    )

    if not audio_bytes:
        raise Exception("Stable Audio generation returned empty result")

    logger.info(f"[CHUNK:stable_audio] Generated {len(audio_bytes)} bytes (seed={actual_seed})")

    # Return dict — _execute_python_chunk wraps it in BackendResponse
    return {
        "content_marker": "stable_audio_generated",
        "chunk_name": "output_audio_stableaudio_diffusers",
        "media_type": "audio",
        "backend": "stable_audio",
        "seed": actual_seed,
        "audio_data": base64.b64encode(audio_bytes).decode('utf-8'),
        "audio_format": output_format,
        "parameters": {
            "prompt": audio_prompt[:200],
            "duration_seconds": duration_seconds,
            "steps": steps,
            "cfg_scale": cfg_scale
        }
    }
