"""
Output Chunk: eSpeak NG Speech Synthesis

Speaks a given text. This is a Python-based chunk - the code IS the chunk.

What makes this chunk different from every other output chunk:
its input is CONTENT, not a prompt. An image chunk receives a prompt that
describes what to make; this chunk receives the sentence that is to be
spoken, verbatim. Nothing here may rewrite, optimize or translate it.
The matching config therefore runs with skip_stage2. On kids/youth, Stage 3
still translates to English before Stage 4, so a text routed through an audio
output config is spoken in English there.

Like Supertonic, and unlike VoxCPM2, this cannot continue past the text it was
handed - and here for the plainest reason on the platform: there is no model to
continue with. Rules turn the letters into phonemes and the phonemes are played
as resonances. Nothing was trained, nobody was recorded.

Input (from Stage 4, or direct):
    - text (TEXT_1): the utterance, spoken as given
    - language / context_language: platform language code
    - variant (optional): one of twelve settings of the same formant
      machinery, `f1`-`f5` and `m1`-`m7`. Empty means the language's plain
      voice
    - speed (optional): words per minute, eSpeak NG's own default is 175
    - pitch (optional): 0-99, its own default is 50

Output:
    - dict with audio_data (base64 WAV), what spoke it, and the register
      (f0_hz) measured off the audio being returned

eSpeak NG is in the voices comparison as the computer voice from before AI: the
method computers spoke with for decades, still installed on every Linux, a few
megabytes for over a hundred languages. It is the first of the three columns
because of what can be asked of it - a number for the speed, a number for the
pitch, a variant - and because none of those numbers is a feeling. See
my_app/services/espeak_backend.py.

There is NO English fallback here and none is needed: eSpeak NG has a voice for
every platform language, Hebrew and Bulgarian included, and it has them without
anybody having been recorded for it.
"""

import base64
import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_speech_espeak",
    "media_type": "audio",
    "output_format": "wav",
    "estimated_duration_seconds": "0-1",
    "requires_gpu": False,
    "gpu_vram_mb": 0,
    # All ten, and not because ten were downloaded: eSpeak NG carries over a
    # hundred languages in a few megabytes, and the platform's ten are in it.
    "supported_languages": ["ar", "bg", "de", "en", "es", "fr", "he", "ko",
                            "tr", "uk"],
    "verbatim_input": True,
}

DEFAULTS = {
    "variant": None,  # None -> the language's plain voice
    "speed": None,    # None -> eSpeak NG's own default (175 wpm)
    "pitch": None,    # None -> eSpeak NG's own default (50)
}

# Every safety level, as with the other two speech chunks: synthesis adds no
# content of its own. It speaks a text that already exists and has already
# passed whatever check its origin runs, so a level that may READ a sentence
# may hear it.
#
# On kids/youth Stage 3 translates to English before Stage 4, so a text routed
# through an audio OUTPUT CONFIG is spoken in English there. That restriction
# sits in espeak_standard.json, not here.
#
# The fail-closed guard below stays as it is: an absent or unknown level blocks.
ALLOWED_SAFETY_LEVELS = ("kids", "youth", "open", "adult", "research")


async def execute(
    text: str = None,
    TEXT_1: str = None,       # Pipeline convention: first text input
    language: str = None,
    context_language: str = None,
    safety_level: str = None,
    variant: str = None,
    speed=None,
    pitch=None,
    **kwargs                  # Ignore extra parameters from pipeline
) -> dict:
    """
    Execute eSpeak NG speech synthesis.

    Returns:
        dict with base64 WAV, the voice that spoke, and the measured register.

    Raises:
        PermissionError: safety level not enabled for this chunk.
        ValueError: an unknown variant.
        RuntimeError: eSpeak NG missing, or no voice for that language.
    """
    from my_app.services.espeak_backend import (
        get_espeak_backend,
        UnvoicedLanguageError,
    )
    from config import ESPEAK_ENABLED

    # Fail closed: an absent or unexpected safety level blocks synthesis.
    level = (safety_level or "").strip().lower()
    if level not in ALLOWED_SAFETY_LEVELS:
        logger.error(
            f"[CHUNK:espeak] Refused: safety_level='{safety_level or 'missing'}' "
            f"not in {ALLOWED_SAFETY_LEVELS}"
        )
        raise PermissionError(
            f"Speech synthesis is not enabled for safety level "
            f"'{safety_level or 'unknown'}'"
        )

    if not ESPEAK_ENABLED:
        logger.error("[CHUNK:espeak] Backend disabled in config")
        raise RuntimeError("eSpeak NG backend is disabled (ESPEAK_ENABLED=false)")

    # Map pipeline convention to semantic name
    if text is None and TEXT_1 is not None:
        text = TEXT_1

    if not text or not text.strip():
        raise ValueError("No text provided for speech synthesis")

    lang = (language or context_language or "en").strip().lower()

    variant = variant if variant is not None else DEFAULTS["variant"]
    speed = speed if speed is not None else DEFAULTS["speed"]
    pitch = pitch if pitch is not None else DEFAULTS["pitch"]

    backend = get_espeak_backend()

    if not await backend.is_available():
        logger.error("[CHUNK:espeak] Backend not available")
        raise RuntimeError(
            "eSpeak NG not available. It is a system package: "
            "`dnf install espeak-ng` / `apt install espeak-ng`."
        )

    try:
        backend.resolve_language(lang)
    except UnvoicedLanguageError:
        raise RuntimeError(
            f"eSpeak NG has no voice for '{lang}'. Platform languages: "
            f"{', '.join(backend.languages())}."
        )

    logger.info(f"[CHUNK:espeak] {len(text)} chars | language={lang} | level={level}")

    wav, spoke, f0_hz = await backend.synthesize(
        text=text,
        language=lang,
        variant=variant,
        speed=speed,
        pitch=pitch,
    )

    return {
        "content_marker": "espeak_generated",
        "chunk_name": "output_speech_espeak",
        "media_type": "audio",
        "backend": "espeak",
        "voice": spoke,
        "f0_hz": round(f0_hz, 1),
        "audio_data": base64.b64encode(wav).decode("utf-8"),
        "audio_format": "wav",
        "size_bytes": len(wav),
    }
