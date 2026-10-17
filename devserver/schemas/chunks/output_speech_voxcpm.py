"""
Output Chunk: VoxCPM2 Speech Synthesis

Speaks a given text. This is a Python-based chunk - the code IS the chunk.

What makes this chunk different from every other output chunk:
its input is CONTENT, not a prompt. An image chunk receives a prompt that
describes what to make; this chunk receives the sentence that is to be
spoken, verbatim. Nothing here may rewrite, optimize or translate it.
The matching config therefore runs with skip_stage2.

**How this one is asked for a voice, and why that is worth having here.**
Supertonic is given a mixture over ten fixed presets and has no parameter for
feeling. Qwen3-TTS was given an English sentence about the delivery, alongside
the utterance. VoxCPM2 is given a description of the speaker INSIDE the
utterance — "(A young woman, gentle and sweet voice)Guten Tag." — one string in
which the model itself decides which part is an instruction and which part is
what to say. Three synthesisers, three procedures for asking a machine for a
feeling; that is what the voices comparison is for.

The description is composed into the text by the worker, never here and never
by a caller. Left empty, nothing is asked and the model reads the prosody off
the sentence — which is a finding in itself, not a fallback.

**This does not break the verbatim contract.** What is spoken is the text as
given. The description is the model's control channel and is not part of the
utterance; measured on 2026-08-12, it is not read aloud (the same sentence came
back 1.6-1.8 s long with and without a description, and at 150.9 / 202.5 /
119.7 / 233.0 Hz for four different ones). A sentence that itself begins with
"(" is refused rather than silently taken as an instruction.

**Autoregressive.** Like Qwen3-TTS and unlike Supertonic and Piper, this model
can continue past the text it was handed. Its own `retry_badcase` guard is left
on, and the length of what comes back is not assumed to be the length of what
was asked for.

Input (from Stage 4, or direct):
    - text (TEXT_1): the utterance, spoken as given
    - language / context_language: platform language code. The model takes no
      language parameter — it is used here only to notice the two languages it
      has no voice for
    - text_en (optional): English rendering, used only when the requested
      language has no voice in this model (bg, uk). The caller supplies it;
      this chunk never translates
    - voice_description (optional): the speaker in words. Empty means nothing
      is asked
    - cfg_value / inference_timesteps (optional): the two settings the model
      card documents. Defaults are the card's own values

Output:
    - dict with audio_data (base64 WAV), what was asked for, and the register
      (f0_hz) measured off the audio being returned

Voice cloning is NOT reachable from here. VoxCPM2 can clone a voice from a few
seconds of recording; no parameter in this chunk, the backend or the worker
leads to it. See my_app/services/voxcpm_backend.py.

The model runs in its own environment as a separate process — voxcpm pins
datasets<4 and gradio>=6 against the platform's versions, and moving those
under everything else is how Qwen3-TTS was lost. download_voxcpm.sh builds it,
voxcpm_service/server.py is the worker.
"""

import base64
import logging

logger = logging.getLogger(__name__)

CHUNK_META = {
    "name": "output_speech_voxcpm",
    "media_type": "audio",
    "output_format": "wav",
    "estimated_duration_seconds": "1-5",
    # The model is on the GPU, but in another process — this chunk holds
    # nothing. Stated as it is: the VRAM is occupied while the worker lives.
    "requires_gpu": True,
    "gpu_vram_mb": 8000,
    # Eight of the platform's ten, from the model card's list of 30. Bulgarian
    # and Ukrainian have no voice; the route answers those with an English
    # rendering of the same sentence. The authority is the backend, which this
    # literal must not contradict — see the test in devserver/tests.
    "supported_languages": ["ar", "de", "en", "es", "fr", "he", "ko", "tr"],
    "verbatim_input": True,
}

DEFAULTS = {
    "voice_description": None,   # None -> nothing is asked
    "cfg_value": None,           # None -> VOXCPM_CFG_VALUE
    "inference_timesteps": None,  # None -> VOXCPM_INFERENCE_TIMESTEPS
}

# Every safety level, as with the other speech chunks. Synthesis adds no
# content of its own: it speaks a text that already exists and has already
# passed whatever check its origin runs, so a level that may READ a sentence
# may hear it. What restricts this one to adult/research is its OUTPUT CONFIG,
# on the same grounds as Qwen3-TTS: an autoregressive model can continue past
# the sentence it was handed, and nothing checks what it added.
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
    voice_description: str = None,
    cfg_value=None,
    inference_timesteps=None,
    **kwargs                  # Ignore extra parameters from pipeline
) -> dict:
    """
    Execute VoxCPM2 speech synthesis.

    Returns:
        dict with base64 WAV, what was asked for, and the measured register.

    Raises:
        PermissionError: safety level not enabled for this chunk.
        ValueError: no text, or a sentence the delimiter would swallow.
        RuntimeError: no voice for that language, or the worker is not there.
    """
    from my_app.services.voxcpm_backend import (
        get_voxcpm_backend,
        UnvoicedLanguageError,
    )
    from config import VOXCPM_ENABLED

    # Fail closed: an absent or unexpected safety level blocks synthesis.
    level = (safety_level or "").strip().lower()
    if level not in ALLOWED_SAFETY_LEVELS:
        logger.warning(
            f"[CHUNK:voxcpm] Refused: safety_level='{safety_level or 'missing'}' "
            f"not in {ALLOWED_SAFETY_LEVELS}"
        )
        raise PermissionError(
            f"Speech synthesis is not enabled for safety level "
            f"'{safety_level or 'unknown'}'"
        )

    if not VOXCPM_ENABLED:
        logger.error("[CHUNK:voxcpm] Backend disabled in config")
        raise RuntimeError("VoxCPM2 backend is disabled (VOXCPM_ENABLED=false)")

    # Map pipeline convention to semantic name
    if text is None and TEXT_1 is not None:
        text = TEXT_1

    if not text or not text.strip():
        raise ValueError("No text provided for speech synthesis")

    lang = (language or context_language or "en").strip().lower()

    voice_description = (voice_description if voice_description is not None
                         else DEFAULTS["voice_description"])
    cfg_value = cfg_value if cfg_value is not None else DEFAULTS["cfg_value"]
    inference_timesteps = (inference_timesteps if inference_timesteps is not None
                           else DEFAULTS["inference_timesteps"])

    backend = get_voxcpm_backend()

    # The decision of 2026-08-06: English fallback, never a foreign voice on
    # the original text. The fallback needs an English rendering of the SAME
    # utterance — the caller supplies it, this chunk does not translate. Said
    # before synthesis, so a language gap never arrives disguised as a broken
    # synthesiser.
    try:
        backend.resolve_language(lang)
    except UnvoicedLanguageError:
        if not (text_en and text_en.strip()):
            spoken = ", ".join(backend.languages())
            logger.warning(
                f"[CHUNK:voxcpm] No voice for '{lang}' and no English rendering supplied")
            raise RuntimeError(
                f"VoxCPM2 has no voice for '{lang}'. It speaks: {spoken}. Supply "
                f"text_en with an English rendering of the same utterance, or "
                f"leave it unspoken. This is a limit of the model, not a "
                f"missing download."
            )
        logger.info(f"[CHUNK:voxcpm] No voice for '{lang}' — speaking English rendering")
        text, lang = text_en, "en"

    # Starts the worker if it is not there — about 25 seconds the first time.
    if not await backend.is_available():
        logger.error("[CHUNK:voxcpm] Worker not available")
        raise RuntimeError(
            "VoxCPM2 is not available. Its worker runs in its own environment; "
            "download_voxcpm.sh installs it and 2_start_voxcpm.sh starts it."
        )

    logger.info(f"[CHUNK:voxcpm] {len(text)} chars | language={lang} | level={level}")

    wav, asked, f0_hz = await backend.synthesize(
        text=text,
        language=lang,
        voice_description=voice_description,
        cfg_value=cfg_value,
        inference_timesteps=inference_timesteps,
    )

    return {
        "content_marker": "voxcpm_generated",
        "chunk_name": "output_speech_voxcpm",
        "media_type": "audio",
        "backend": "voxcpm",
        # What was asked for, not who spoke: there is no speaker to name. The
        # header this ends up in is read as "what was requested" everywhere
        # else too, and a described voice is exactly that.
        "voice": asked,
        "f0_hz": round(f0_hz, 1),
        "audio_data": base64.b64encode(wav).decode("utf-8"),
        "audio_format": "wav",
        "size_bytes": len(wav),
    }
