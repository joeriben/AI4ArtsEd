"""
Output Chunk: Stable Audio 3 (GPU Service)

Generates audio from text prompts using Stable Audio 3 medium via the GPU service
(stable-audio-tools, t5gemma conditioner), routed through the stable_audio HTTP client.
NOTE: the filename still says "diffusers" for backward compatibility with the
OUTPUT_CHUNK wiring in stableaudio_open.json; the engine is stable-audio-tools, not diffusers.

Input (from pipeline parameters):
    - TEXT_1: Text prompt (from Stage 2/3 output)
    - SECONDS: Duration in seconds (from output config)
    - STEPS: Inference steps (from output config, default 8 — SA3 is few-step rectified flow)
    - CFG: Guidance scale (from output config, default 1.0 — guidance is distilled into the model)
    - NEGATIVE_PROMPT: What to avoid (largely inert at CFG≈1.0)
    - seed: Seed for reproducibility

Output:
    - dict with audio_data (base64), matching BackendResponse metadata format

Fallback:
    - None. A failure reaches the caller with its own cause.
"""

import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Chunk metadata
CHUNK_META = {
    "name": "output_audio_stableaudio_diffusers",
    "media_type": "audio",
    "output_format": "mp3",
    "backend": "stable_audio",
    "backend_type": "stable_audio",
    "model_id": "stabilityai/stable-audio-3-medium",
    "fallback_chunk": None,
    "estimated_duration_seconds": "8-12",
    "quality_rating": 3,
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
    "optimization_instruction": (
        "Transform the input into a clear audio generation prompt; describe the sonic "
        "content (instruments, sounds, textures), the acoustic environment (reverb, "
        "space, atmosphere), the rhythm and tempo (if applicable), the mood and energy "
        "level, and any specific sonic characteristics (pitch, timbre, dynamics); keep "
        "it concise and focused on auditory elements.\n"
        "\n"
        "Then decide HOW LONG this sound has to be to be itself, and write that as the "
        "last line, alone, in the form DURATION: <whole seconds>. A single event — a "
        "door, a bell, a footstep — is over in a few seconds; an atmosphere or a room "
        "tone needs long enough to stop sounding like a loop; a piece of music needs "
        "long enough to have a shape. Anything between 10 and 240 seconds. Decide it "
        "from what is being made, not from a default.\n"
        "\n"
        "Example:\n"
        "Gentle piano melody with soft reverb, slow tempo, melancholic mood, warm "
        "analog sound, minimal background ambience.\n"
        "DURATION: 60"
    )
}

# What the adaption is allowed to ask for. The floor is the shortest thing worth
# rendering; the ceiling is the platform's own (gpu_service/config.py,
# STABLE_AUDIO_MAX_DURATION), and the GPU service clamps to it silently anyway —
# refusing here means a wrong number is visible in the log instead of vanishing.
DURATION_MIN_SECONDS = 10.0
DURATION_MAX_SECONDS = 240.0

# The adaption writes its length as the last line (see optimization_instruction).
# Tolerant on purpose: an LLM will produce "DURATION: 45", "duration: 45s",
# "**DURATION:** 45 seconds", "length 45". What it may NOT do is hide it mid-text
# — the line has to be at the END, or this is not a length, it is prose about
# one, and the prompt would be better off keeping it.
_DURATION_LINE = re.compile(
    r"^[\s*_#>~-]*(?:duration|dauer|l\u00e4nge|laenge|length|dur\u00e9e|duraci\u00f3n)\s*[:=]?[\s*_~]*"
    r"([0-9]+(?:[.,][0-9]+)?)\s*(?:s|sec|secs|second|seconds|sek|sekunden?|segundos?|secondes?)?[\s*_.]*$",
    re.IGNORECASE,
)

# What a model closes a block with and what carries nothing: a fence, a rule, a
# stray quote. Walked past on the way in — a decoration must not cost the length,
# and must not leave the directive standing in the prompt either.
_CLOSING_NOISE = re.compile(r"^[\s*_\-=#`~.'\"]*$")


def _read_seconds(raw: str):
    """The number out of a matched line, or None."""
    # "1,200" and "1.200" are a thousands separator, not a decimal point — three
    # digits behind it. Read as 1.2 they would turn the LONGEST length a model
    # can ask for into the SHORTEST the platform will render.
    if re.fullmatch(r"[0-9]{1,3}[.,][0-9]{3}", raw):
        raw = raw.replace(".", "").replace(",", "")
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def _take_duration(prompt: str):
    """Split an adaption's trailing DURATION line off its prompt.

    Returns (prompt without the line, seconds or None). The line is REMOVED
    either way it is read: it is an instruction to this chunk, not something the
    audio model should try to render. Several such lines are all removed and the
    LAST one written decides — anything else would leave a directive in the text.
    """
    lines = (prompt or "").rstrip().split("\n")
    end = len(lines)
    seconds = None
    cut = None
    while end > 0:
        line = lines[end - 1]
        if not line.strip() or _CLOSING_NOISE.match(line):
            end -= 1
            continue
        match = _DURATION_LINE.match(line)
        if not match:
            break
        if seconds is None:
            seconds = _read_seconds(match.group(1))
        end -= 1
        cut = end
    # Nothing found: the prompt is handed back untouched, decoration included.
    if cut is None or seconds is None:
        return prompt, None
    text = "\n".join(lines[:cut]).rstrip()
    clamped = max(DURATION_MIN_SECONDS, min(DURATION_MAX_SECONDS, seconds))
    if clamped != seconds:
        logger.warning(f"[CHUNK:stable_audio] adaption asked for {seconds}s, "
                       f"outside {DURATION_MIN_SECONDS}-{DURATION_MAX_SECONDS}s; "
                       f"using {clamped}s")
    # A prompt that was NOTHING BUT the line would leave the model with no text
    # at all, and an empty prompt raises below. Keep the length, keep the prompt.
    return (text or prompt), clamped


# Defaults matching the JSON input_mappings.
# SA3 medium baseline: adversarial-distilled few-step rectified flow → 8 steps, cfg 1.0,
# pingpong sampler (set in the GPU-service backend). cfg≈1.0 makes negative_prompt inert.
# (SA1 used steps≈50-100, cfg≈5-7.) See gpu_service/services/stable_audio_backend.py.
DEFAULTS = {
    "negative_prompt": "",
    "duration_seconds": 30.0,
    "steps": 8,
    "cfg_scale": 1.0,
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
    # The client of the platform's node on ComfyUI (SA3 via stable-audio-tools
    # in ComfyUI's venv; until stage 6 of the move to ComfyUI it called the GPU
    # service over HTTP).
    from my_app.services.stable_audio_client import get_stable_audio_client
    from my_app.services.backend_registry import get_backend_registry
    import random
    import base64

    # --- Check backend availability ---
    registry = get_backend_registry()
    if not registry.is_enabled("stable_audio"):
        raise Exception("Stable Audio backend disabled in registry")

    backend = get_stable_audio_client()

    if not await backend.is_available():
        from my_app.services import media_stations
        raise Exception(f"Stable Audio is not available on ComfyUI: {media_stations.why_unavailable('stable_audio')}")

    # --- Map pipeline parameters to backend API ---
    audio_prompt = TEXT_1 or PREVIOUS_OUTPUT or ""

    if not audio_prompt:
        raise ValueError("No prompt provided for audio generation")

    # The adaption decides the length of what it just described: the flow's
    # x2audio step produces a length statement of its own. Before this,
    # every sound from the flow was exactly as long as the config's default said,
    # whether it was a door closing or a piece of music.
    #
    # Callers that already know the length are untouched, because they hand over
    # a prompt with no such line: the re-enactment chain puts the recording's own
    # length in SECONDS and writes no DURATION anywhere.
    audio_prompt, asked_seconds = _take_duration(audio_prompt)

    negative_prompt = NEGATIVE_PROMPT if NEGATIVE_PROMPT is not None else DEFAULTS["negative_prompt"]
    duration_seconds = float(SECONDS) if SECONDS is not None else DEFAULTS["duration_seconds"]
    if asked_seconds is not None:
        logger.info(f"[CHUNK:stable_audio] prompt asked for {asked_seconds}s "
                    f"(config said {duration_seconds}s)")
        duration_seconds = asked_seconds
    else:
        # Said out loud, because otherwise a run where the adaption picked the
        # config's length and a run where it wrote no line at all leave exactly
        # the same trace, and the hit rate of the mechanism is unmeasurable in
        # production.
        logger.info(f"[CHUNK:stable_audio] no length in the prompt; "
                    f"using {duration_seconds}s")
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
