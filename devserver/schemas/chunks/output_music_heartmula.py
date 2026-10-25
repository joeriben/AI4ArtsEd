"""
Output Chunk: HeartMuLa Music Generation

Generates music from lyrics and style tags using HeartMuLa (heartlib).
This is a Python-based chunk - the code IS the chunk.

Input (from Stage 2/3 or direct):
    - lyrics (TEXT_1): Song lyrics with [Verse], [Chorus], [Bridge] markers
    - tags (TEXT_2): Comma-separated style tags (genre, mood, instruments)

Output:
    - MP3 audio bytes

Usage:
    result = await execute(lyrics="[Verse] Hello...", tags="pop, upbeat")
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Chunk metadata (replaces JSON meta section)
CHUNK_META = {
    "name": "output_music_heartmula",
    "media_type": "music",
    "output_format": "mp3",
    "estimated_duration_seconds": "30-240",
    "quality_rating": 4,
    "requires_gpu": True,
    "gpu_vram_mb": 16000,
    "supported_languages": ["en", "zh", "ja", "ko", "es"]
}

# Default parameters (replaces JSON input_mappings defaults)
#
# topk 70 / cfg_scale 3.0 are the values this platform ran on from 2026-02-05 to
# 2026-06-22, with audible tag adherence. 0fde2e15 lowered them to heartlib's own
# README defaults (50 / 1.5) on the grounds that 3.0 "over-guided the flow-matching
# generation". That reasoning does not describe this model: cfg_scale is applied to
# the autoregressive LM's logits, uncond + (cond - uncond) * cfg_scale, where the
# uncond branch is the same prompt with every text embedding replaced by a learned
# null embedding (modeling_heartmula.py). It is the knob that decides how much the
# style tags count at all; the flow-matching part is HeartCodec's decoder, which
# never sees it. Halving it halved tag adherence in listening.
#
# max_audio_length_ms was measured in 4d07ece3 as NOT a ceiling: heartlib generates
# max_audio_length_ms // 80 frames and the early-EOS break did not fire, so an
# 11.9 s recording with a 60000 ms budget produced 60.080 s of audio. The break
# does fire: on 2026-10-01 two Flow songs at 240000 ended after 10 s and 33.2 s.
# The number is the longest the song can be, one frame plus number // 80 frames
# of 80 ms. Callers pass it explicitly. Where one does not, 60000 applies: a
# HeartMuLa song from a prompt is at most 60 s. Two configs named after
# ACE-Step reached this chunk through the music_generation pipeline without a
# length and ran at 240 s until then; they were retired on 2026-10-10 (finding S-010 of the code review of 2026-10-10).
# Re-enactment (formerly Silly Parrot / Cover Band) passes the recording's
# length (parrot_service._sing).
DEFAULTS = {
    "temperature": 1.0,
    "topk": 70,
    "cfg_scale": 3.0,
    "max_audio_length_ms": 60000,
    "seed": None  # None = random
}


async def execute(
    lyrics: str = None,
    tags: str = "",
    TEXT_1: str = None,  # Pipeline convention: first text input
    TEXT_2: str = None,  # Pipeline convention: second text input
    temperature: float = None,
    topk: int = None,
    cfg_scale: float = None,
    max_audio_length_ms: int = None,
    seed: int = None,
    **kwargs  # Ignore extra parameters from pipeline
) -> bytes:
    """
    Execute HeartMuLa music generation.

    Args:
        lyrics: Song lyrics with structure markers [Verse], [Chorus], [Bridge]
        tags: Comma-separated style tags (genre, mood, instruments, tempo)
        temperature: Creativity (0.1-2.0)
        topk: Token sampling parameter
        cfg_scale: Classifier-free guidance scale
        max_audio_length_ms: Maximum audio length in milliseconds
        seed: Seed for reproducibility (None = random)

    Returns:
        MP3 audio bytes (ready for storage/response)

    Raises:
        Exception: If generation fails or backend unavailable
    """
    from my_app.services.heartmula_backend import get_heartmula_backend
    from config import HEARTMULA_ENABLED
    import random

    # Map pipeline convention (TEXT_1, TEXT_2) to semantic names
    if lyrics is None and TEXT_1 is not None:
        lyrics = TEXT_1
    if not tags and TEXT_2 is not None:
        tags = TEXT_2

    # The streaming path duplicates a single prompt into BOTH TEXT_1 and TEXT_2
    # (Persona / dual_text pipeline with one prompt). Detect that (tags == lyrics)
    # and undo it, so the single-input handling below splits "lyrics || tags".
    if tags and tags == lyrics:
        tags = ""

    # Single-input mode (Persona, API): split "lyrics || tags" into parts
    # If TEXT_2 was not provided, check if lyrics contains the separator
    if not tags and lyrics and ' || ' in lyrics:
        parts = lyrics.split(' || ', 1)
        lyrics = parts[0].strip()
        tags = parts[1].strip()
        logger.info(f"[CHUNK:heartmula] Split single input: lyrics={len(lyrics)} chars, tags='{tags}'")
    elif not tags and lyrics:
        # No separator found: treat entire input as tags (instrumental, no lyrics)
        tags = lyrics
        lyrics = ""
        logger.info(f"[CHUNK:heartmula] No separator found, instrumental mode: tags='{tags}'")

    # Apply defaults
    temperature = temperature if temperature is not None else DEFAULTS["temperature"]
    topk = topk if topk is not None else DEFAULTS["topk"]
    cfg_scale = cfg_scale if cfg_scale is not None else DEFAULTS["cfg_scale"]
    max_audio_length_ms = max_audio_length_ms if max_audio_length_ms is not None else DEFAULTS["max_audio_length_ms"]

    # Handle seed
    if seed is None or seed == "random":
        seed = random.randint(0, 2**32 - 1)

    logger.info(f"[CHUNK:heartmula] Executing with lyrics={len(lyrics) if lyrics else 0} chars")
    logger.info(f"[CHUNK:heartmula] Tags (full): '{tags}'")
    logger.info(f"[CHUNK:heartmula] Parameters: temp={temperature}, topk={topk}, cfg={cfg_scale}, max_ms={max_audio_length_ms}, seed={seed}")

    # Check if HeartMuLa is enabled
    if not HEARTMULA_ENABLED:
        logger.error("[CHUNK:heartmula] Backend disabled in config")
        raise Exception("HeartMuLa backend is disabled (HEARTMULA_ENABLED=false)")

    # Get backend
    backend = get_heartmula_backend()

    # Check availability
    if not await backend.is_available():
        from my_app.services import media_stations
        why = media_stations.why_unavailable('heartmula')
        logger.error(f"[CHUNK:heartmula] not available: {why}")
        raise Exception(f"HeartMuLa is not available on ComfyUI: {why}")

    # Validate input: either lyrics or tags must be present
    if (not lyrics or not lyrics.strip()) and (not tags or not tags.strip()):
        logger.error("[CHUNK:heartmula] No lyrics and no tags provided")
        raise ValueError("No input provided for music generation (need lyrics, tags, or both)")

    # Validate lyrics length (HeartMuLa has token limits)
    MAX_LYRICS_CHARS = 2000  # Conservative limit
    if len(lyrics) > MAX_LYRICS_CHARS:
        logger.warning(f"[CHUNK:heartmula] Lyrics too long ({len(lyrics)} chars), truncating to {MAX_LYRICS_CHARS}")
        lyrics = lyrics[:MAX_LYRICS_CHARS]

    # Normalize tag format. HeartMuLa's own README asks for exactly one thing
    # here: "Our different tags are comma-separated without spaces", shown as
    # piano,happy,wedding,synthesizer,romantic (heartlib/README.md, and
    # heartlib/assets/tags.txt is "piano,happy"). That is the space AFTER the
    # comma.
    #
    # It never asks for the spaces INSIDE a tag to be replaced by underscores,
    # and the tag guidance the README points at spells them with their space
    # ("acoustic guitar").
    #
    # Gluing them changed what the model reads. Against its own tokenizer
    # (heartlib/ckpt/tokenizer.json): "hand drums" is [hand][ drums] but
    # "hand_drums" is [hand][_dr][ums]; "clean studio recording" is
    # [clean][ studio][ recording] against [clean][_st][udio][_rec][ording]. Not
    # every tag suffers — "folk_song" and "hip_hop" stay two pieces, and
    # single-word tags are identical either way.
    #
    # Measured before this was changed (2026-08-09, same lyrics, three seeds,
    # CLAP against the same label list; issue #37): the six
    # requested labels scored 0.152 underscored, 0.193 spaced, and 0.165 for a
    # control that asked for something else entirely. Spaced is the only variant
    # that beats the control, and the margin is small and unsteady across seeds.
    # The underscores date from ceb764fb (5 February) and so predate the time
    # this page was heard working: they are not a broken route and they are not
    # the regression.
    if tags:
        tag_list = [' '.join(tag.split()) for tag in tags.split(',')]
        tags = ','.join(t for t in tag_list if t)
        logger.info(f"[CHUNK:heartmula] Tags normalized: '{tags}'")

    # Validate tags (keep simple like HeartMuLa examples: "piano,happy")
    MAX_TAGS_CHARS = 200  # HeartMuLa expects simple tags
    if tags and len(tags) > MAX_TAGS_CHARS:
        logger.warning(f"[CHUNK:heartmula] Tags too long ({len(tags)} chars), truncating to {MAX_TAGS_CHARS}")
        tags = tags[:MAX_TAGS_CHARS]
        # Ensure we don't cut mid-tag
        if ',' in tags:
            tags = ','.join(tags.split(',')[:-1])  # Remove partial last tag

    # Generate music
    audio_bytes = await backend.generate_music(
        lyrics=lyrics,
        tags=tags,
        temperature=temperature,
        topk=topk,
        cfg_scale=cfg_scale,
        max_audio_length_ms=max_audio_length_ms,
        seed=seed,
        output_format="mp3"
    )

    if audio_bytes is None:
        logger.error("[CHUNK:heartmula] Generation returned None")
        raise Exception("Music generation failed")

    logger.info(f"[CHUNK:heartmula] Generated {len(audio_bytes)} bytes (seed={seed})")

    # Return raw bytes - backend_router will wrap them properly
    return audio_bytes
