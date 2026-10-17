"""
Output Chunk: Supertonic Speech Synthesis

Speaks a given text. This is a Python-based chunk - the code IS the chunk.

What makes this chunk different from every other output chunk:
its input is CONTENT, not a prompt. An image chunk receives a prompt that
describes what to make; this chunk receives the sentence that is to be
spoken, verbatim. Nothing here may rewrite, optimize or translate it.
The matching configs therefore run with skip_stage2. On kids/youth, Stage 3
still translates to English before Stage 4, so a text routed through an
audio output config is spoken in English there.

The model cannot do otherwise, which is why it was chosen: Supertonic 3 is
non-autoregressive — flow matching plus a speech autoencoder — so it has no
way to continue past the text it was handed. Its predecessor here did, and
did: a fragment cut at a comma cost 16.3 s and came back with a continuation
nobody had written.

Input (from Stage 4, or direct):
    - text (TEXT_1): the utterance, spoken as given
    - language / context_language: platform language code (nine of ten)
    - text_en (optional): English rendering, used only when the requested
      language has no voice in this model (Hebrew)
    - voice (optional): one of the named mixes, see config.SUPERTONIC_VOICES.
      Left out, the backend draws one per sentence — never the one the previous
      sentence used. Naming it is the "this voice fits this sentence" case.
    - seed (optional): "random" (default), -1, or an integer. The variation
      between runs is wanted, so a seed is drawn rather than fixed — but it IS
      drawn, logged and returned, so an utterance can be heard again.
    - mix / steps / speed (optional): examination parameters. `mix` is a
      weighting over the ten presets (M1-M5, F1-F5) and puts the call into
      examination mode — the weighting is spoken once, exactly as given, with
      no register correction, and it never becomes a voice of this platform.
      `steps` and `speed` are the machine's own settings for this one call.
      All three are absent on every path that speaks an agent's words.

Output:
    - dict with audio_data (base64 WAV), the seed that produced it, and the
      register (f0_hz) measured off the audio being returned

See DEVELOPMENT_DECISIONS.md, 2026-08-08, for the voice policy and the search.
"""

import base64
import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_speech_supertonic",
    "media_type": "audio",
    "output_format": "wav",
    "estimated_duration_seconds": "1-5",
    # Runs on the CPU. The GPU stays free for image and video.
    "requires_gpu": False,
    "gpu_vram_mb": 0,
    "supported_languages": ["ar", "bg", "de", "en", "es", "fr", "ko", "tr", "uk"],
    "verbatim_input": True,
}

DEFAULTS = {
    "voice": None,      # None -> SUPERTONIC_DEFAULT_VOICE
    "seed": "random",   # drawn per utterance, then reported back
}

# Every safety level. The restriction to adult/research was lifted:
# synthesis adds no content of its own. It speaks a text that
# already exists and has already passed whatever check its origin runs, so a
# level that may READ a sentence may hear it.
#
# What the old note described is a Stage-3 matter, not a level matter: on
# kids/youth Stage 3 translates to English before Stage 4, so a text routed
# through an audio OUTPUT CONFIG is spoken in English there. The platform's own
# voice (/api/speech) does not pass Stage 3 and never did.
#
# The fail-closed guard below stays as it is: an absent or unknown level blocks.
ALLOWED_SAFETY_LEVELS = ("kids", "youth", "open", "adult", "research")


async def execute(
    text: str = None,
    TEXT_1: str = None,       # Pipeline convention: first text input
    text_en: str = None,      # optional English rendering for unvoiced languages
    language: str = None,
    context_language: str = None,
    safety_level: str = None,
    voice: str = None,
    seed: str = None,         # "random" | -1 | integer
    seed_override: int = None,
    mix: dict = None,         # examination: weighting over presets, see below
    steps: int = None,        # flow steps for this call only
    speed: float = None,      # speaking rate for this call only
    **kwargs                  # Ignore extra parameters from pipeline
) -> dict:
    """
    Execute Supertonic speech synthesis.

    Returns:
        dict with the WAV as base64 in audio_data, and the seed used.

    Raises:
        PermissionError: safety level not enabled for this chunk.
        RuntimeError: language has no voice and no English rendering was
                      supplied, or the backend is unavailable.
    """
    from my_app.services.supertonic_backend import (
        get_supertonic_backend,
        parse_mix,
        UnvoicedLanguageError,
        VoiceMixError,
    )
    from config import SUPERTONIC_ENABLED

    # Fail closed: an absent or unexpected safety level blocks synthesis.
    level = (safety_level or "").strip().lower()
    if level not in ALLOWED_SAFETY_LEVELS:
        logger.warning(
            f"[CHUNK:supertonic] Refused: safety_level='{safety_level or 'missing'}' "
            f"not in {ALLOWED_SAFETY_LEVELS}"
        )
        raise PermissionError(
            f"Speech synthesis is not enabled for safety level "
            f"'{safety_level or 'unknown'}'"
        )

    if not SUPERTONIC_ENABLED:
        logger.error("[CHUNK:supertonic] Backend disabled in config")
        raise RuntimeError("Supertonic backend is disabled (SUPERTONIC_ENABLED=false)")

    # Map pipeline convention to semantic name
    if text is None and TEXT_1 is not None:
        text = TEXT_1

    if not text or not text.strip():
        raise ValueError("No text provided for speech synthesis")

    lang = (language or context_language or "en").strip().lower()
    voice = voice if voice is not None else DEFAULTS["voice"]

    # Seed handling, same convention as the image and audio chunks.
    actual_seed = seed_override if seed_override is not None else seed
    if actual_seed is None:
        actual_seed = DEFAULTS["seed"]

    # Examination parameters. Absent — the normal case, and every caller that
    # speaks an agent's words — this chunk behaves exactly as before.
    parsed_mix = None
    if mix:
        try:
            parsed_mix = parse_mix(mix)
        except VoiceMixError as e:
            logger.warning(f"[CHUNK:supertonic] Refused mix: {e}")
            raise ValueError(f"Unusable voice mix: {e}")

    if steps is not None:
        try:
            steps = max(1, min(64, int(steps)))
        except (TypeError, ValueError):
            logger.warning(f"[CHUNK:supertonic] Unreadable steps={steps!r}, using default")
            steps = None

    if speed is not None:
        try:
            speed = max(0.5, min(2.0, float(speed)))
        except (TypeError, ValueError):
            logger.warning(f"[CHUNK:supertonic] Unreadable speed={speed!r}, using default")
            speed = None

    backend = get_supertonic_backend()

    # Whether a language has a voice is a static property of the model, not of
    # the installation. Decide it before touching the backend, so "no voice for
    # Hebrew" never arrives disguised as "model not installed".
    #
    # The decision of 2026-08-06 stands: English fallback, never a foreign voice
    # on the original text, and never Russian in place of Ukrainian. The fallback
    # needs an English rendering of the SAME utterance — the caller supplies it,
    # this chunk does not translate.
    try:
        backend.resolve_language(lang)
    except UnvoicedLanguageError:
        if not (text_en and text_en.strip()):
            logger.warning(
                f"[CHUNK:supertonic] No voice for '{lang}' and no English rendering supplied"
            )
            raise RuntimeError(
                f"Supertonic has no voice for '{lang}'. Supply text_en with an English "
                f"rendering of the same utterance, or leave it unspoken."
            )
        logger.info(f"[CHUNK:supertonic] No voice for '{lang}' — speaking English rendering")
        text, lang = text_en, "en"

    if not await backend.is_available():
        logger.error("[CHUNK:supertonic] Backend not available")
        raise RuntimeError(
            "Supertonic not available. Check the supertonic installation and model files."
        )

    logger.info(
        f"[CHUNK:supertonic] {len(text)} chars | language={lang} | level={level} "
        f"| seed={actual_seed}")

    wav, used_seed, used_voice, f0_hz = await backend.synthesize(
        text=text, language=lang, voice=voice, seed=actual_seed,
        mix=parsed_mix, steps=steps, speed=speed)

    logger.info(
        f"[CHUNK:supertonic] {len(wav)} bytes (voice={used_voice}, "
        f"seed={used_seed}, {f0_hz:.0f} Hz)")

    # Structured dict — _execute_python_chunk merges it into the metadata, which
    # is how the seed reaches the caller. The keys mirror what the raw-bytes
    # path would have produced, so nothing downstream has to know the difference.
    return {
        "content_marker": "supertonic_generated",
        "chunk_name": "output_speech_supertonic",
        "media_type": "audio",
        "backend": "supertonic",
        "seed": used_seed,
        "voice": used_voice,
        # The register this run actually landed on, measured off the audio that
        # is being returned. Reported so a study can show where a mixture went
        # instead of asserting it — see the backend's `_explored_style()`.
        "f0_hz": round(f0_hz, 1),
        "audio_data": base64.b64encode(wav).decode("utf-8"),
        "audio_format": "wav",
        "size_bytes": len(wav),
    }
