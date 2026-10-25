"""
Output Chunk: Piper Speech Synthesis

Speaks a given text. This is a Python-based chunk - the code IS the chunk.

What makes this chunk different from every other output chunk:
its input is CONTENT, not a prompt. An image chunk receives a prompt that
describes what to make; this chunk receives the sentence that is to be
spoken, verbatim. Nothing here may rewrite, optimize or translate it.
The matching config therefore runs with skip_stage2. On kids/youth, Stage 3
still translates to English before Stage 4, so a text routed through an audio
output config is spoken in English there.

Like Supertonic and eSpeak NG, and unlike VoxCPM2, this model cannot continue
past the text it was handed: VITS with a duration predictor produces exactly
the phonemes it was given and stops.

Input (from Stage 4, or direct):
    - text (TEXT_1): the utterance, spoken as given
    - language / context_language: platform language code
    - voice (optional): which installed model speaks, by file stem — any of
      them, whatever its language (what the file's phonemiser then does with
      the sentence stands in the backend's module docstring).
      Several languages carry more than one — three Spanish voices from
      Spain, Mexico and Argentina, two English, two German, two Ukrainian
    - emotion (optional): one of the model's named speakers. The name is
      historical and no installed voice names a feeling: fourteen of the
      fifteen have a single speaker and ignore the parameter, and the German
      corpus voice names its 236 speakers by number
    - length_scale / noise_w (optional): Piper's own scales, `--length-scale`
      (phoneme length, the tempo) and `--noise-w-scale` (phoneme width noise);
      its third, `--noise-scale` (generator noise), stays at the file's value

Output:
    - dict with audio_data (base64 WAV), what spoke it, and the register
      (f0_hz) measured off the audio being returned

Piper is in the voices comparison as the system whose voice is a recording
and nothing else: every voice is one file trained on one recorded dataset,
the file is chosen, and nothing about it can be asked for — no category for
gender, no control for feeling. It stands as the second machine (the third of
five columns). See my_app/services/piper_backend.py, and
docs/SPRACHSYNTHESE_PIPER_KONFIGURATION.md for the catalogue it comes from.

There is NO English fallback here, and none is needed: Piper has a voice for
every platform language — Hebrew, which Supertonic lacks, and Bulgarian and
Ukrainian, which VoxCPM2 answers in English. If a language is nonetheless
unanswerable, a download is missing, and saying so is the point: answering a
download gap with English would hide it behind a limit that does not exist.
"""

import base64
import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_speech_piper",
    "media_type": "audio",
    "output_format": "wav",
    "estimated_duration_seconds": "0-1",
    "requires_gpu": False,
    "gpu_vram_mb": 0,
    # What is installed. Every platform language has at least one voice —
    # download_piper.sh fetches them all — which makes this, with eSpeak NG,
    # one of the two synthesisers here that never need the English fallback.
    # The authority is still the model directory: the backend reads it, and
    # /api/speech/status reports what it found, not this literal.
    "supported_languages": ["ar", "bg", "de", "en", "es", "fr", "he", "ko",
                            "tr", "uk"],
    # Never handed an English rendering: a language outside the ten is refused
    # with the cause, and so is a platform language without an installed voice
    # when no voice is named (speech_routes._spoken_language reads this); no
    # cloud call is spent on a sentence this chunk would not speak.
    "english_fallback": False,
    "verbatim_input": True,
}

DEFAULTS = {
    "voice": None,         # None -> PIPER_DEFAULT_VOICE, or the language's first
    "emotion": None,       # None -> the model's own default speaker
    "length_scale": None,  # None -> the value in the model's sidecar JSON
    "noise_w": None,
}

# Every safety level, as with the other three speech chunks: synthesis adds no
# content of its own. It speaks a text that already exists and has already
# passed whatever check its origin runs, so a level that may READ a sentence
# may hear it.
#
# On kids/youth Stage 3 translates to English before Stage 4, so a text routed
# through an audio OUTPUT CONFIG is spoken in English there. That restriction
# sits in piper_standard.json, not here.
#
# The fail-closed guard below stays as it is: an absent or unknown level blocks.
ALLOWED_SAFETY_LEVELS = ("kids", "youth", "open", "adult", "research")


async def execute(
    text: str = None,
    TEXT_1: str = None,       # Pipeline convention: first text input
    language: str = None,
    context_language: str = None,
    safety_level: str = None,
    voice: str = None,
    emotion: str = None,
    length_scale=None,
    noise_w=None,
    **kwargs                  # Ignore extra parameters from pipeline
) -> dict:
    """
    Execute Piper speech synthesis.

    Returns:
        dict with base64 WAV, the voice that spoke, and the measured register.

    Raises:
        PermissionError: safety level not enabled for this chunk.
        ValueError: an unknown voice or a speaker the model does not have.
        RuntimeError: nothing installed for that language, or Piper missing.
    """
    from my_app.services.piper_backend import (
        get_piper_backend,
        UnvoicedLanguageError,
    )
    from config import PIPER_ENABLED

    # Fail closed: an absent or unexpected safety level blocks synthesis.
    level = (safety_level or "").strip().lower()
    if level not in ALLOWED_SAFETY_LEVELS:
        logger.error(
            f"[CHUNK:piper] Refused: safety_level='{safety_level or 'missing'}' "
            f"not in {ALLOWED_SAFETY_LEVELS}"
        )
        raise PermissionError(
            f"Speech synthesis is not enabled for safety level "
            f"'{safety_level or 'unknown'}'"
        )

    if not PIPER_ENABLED:
        logger.error("[CHUNK:piper] Backend disabled in config")
        raise RuntimeError("Piper backend is disabled (PIPER_ENABLED=false)")

    # Map pipeline convention to semantic name
    if text is None and TEXT_1 is not None:
        text = TEXT_1

    if not text or not text.strip():
        raise ValueError("No text provided for speech synthesis")

    lang = (language or context_language or "en").strip().lower()

    voice = voice if voice is not None else DEFAULTS["voice"]
    emotion = emotion if emotion is not None else DEFAULTS["emotion"]
    length_scale = length_scale if length_scale is not None else DEFAULTS["length_scale"]
    noise_w = noise_w if noise_w is not None else DEFAULTS["noise_w"]

    backend = get_piper_backend()

    if not await backend.is_available():
        logger.error("[CHUNK:piper] Backend not available")
        raise RuntimeError(
            "Piper not available. Check PIPER_BIN and the model directory; "
            "download_piper.sh installs both."
        )

    # Stated before synthesis, so a missing download never arrives disguised as
    # a broken synthesiser. No English fallback — see the module docstring.
    # The language is one of the ten whatever is named: it is what the route
    # reports back as spoken (`X-Speech-Language`), and nothing outside the
    # ten has a meaning here.
    if lang not in CHUNK_META["supported_languages"]:
        installed = ", ".join(backend.languages()) or "none"
        logger.warning(f"[CHUNK:piper] '{lang}' is not a platform language")
        raise RuntimeError(
            f"'{lang}' is not one of this platform's ten languages. Piper "
            f"voices are installed for: {installed}."
        )
    # A named voice speaks any of the ten and needs no voice for the text's;
    # the check is for the default, which is looked up by that language.
    if not voice:
        try:
            backend.resolve_language(lang)
        except UnvoicedLanguageError:
            installed = ", ".join(backend.languages()) or "none"
            logger.warning(f"[CHUNK:piper] No voice installed for '{lang}'")
            # A platform language: Piper's catalogue has a voice for every one
            # of the ten, so what is missing is the download.
            raise RuntimeError(
                f"No Piper voice is installed for '{lang}'. Installed: "
                f"{installed}. download_piper.sh fetches the missing voice."
            )

    logger.info(f"[CHUNK:piper] {len(text)} chars | language={lang} | level={level}")

    wav, spoke, f0_hz = await backend.synthesize(
        text=text,
        language=lang,
        voice=voice,
        emotion=emotion,
        length_scale=length_scale,
        noise_w=noise_w,
    )

    return {
        "content_marker": "piper_generated",
        "chunk_name": "output_speech_piper",
        "media_type": "audio",
        "backend": "piper",
        "voice": spoke,
        "f0_hz": round(f0_hz, 1),
        "audio_data": base64.b64encode(wav).decode("utf-8"),
        "audio_format": "wav",
        "size_bytes": len(wav),
    }
