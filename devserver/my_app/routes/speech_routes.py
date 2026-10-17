"""
Speech routes — /api/speech/*

    GET  /api/speech/status     what can be spoken here, and in which languages
    POST /api/speech            speak a text, returns wav

This endpoint exists because speaking is not generating. Everywhere else in
the platform a text is a prompt: something a model reads in order to make
something else. Here the text IS the utterance. It is spoken verbatim, and
nothing on the way may rewrite, optimize or translate it.

Two consequences run through the whole file:

  * The safety level is read from the server's own configuration, never from
    the request. A caller cannot ask to be treated as an adult.
    This holds for the examination parameters below without exception: `mix`
    changes which weighting is heard, never who is allowed to hear it.
  * For a platform language a synthesiser has no voice for, the utterance is
    translated to English and the English is spoken. Never a foreign voice on
    the original text by the server's choice, and never Russian as a stand-in
    for Ukrainian. A caller may NAME a foreign voice (Piper, since 2026-09-18:
    the comparison column offers every installed file, and the response names
    the file that spoke).

See DEVELOPMENT_DECISIONS.md, 2026-08-06 for the language policy and
2026-08-08 for the model and the voice policy.
"""

import asyncio
import importlib.util
import logging
from pathlib import Path

from typing import Optional, Tuple

from flask import Blueprint, Response, jsonify, request
from my_app.services.safety_level_resolver import resolve_safety_level

logger = logging.getLogger(__name__)

speech_bp = Blueprint('speech', __name__, url_prefix='/api/speech')

# The output config that carries OUTPUT_CHUNK: output_speech_supertonic.
SPEECH_CONFIG = 'supertonic_standard'

# The synthesisers reachable from here, by the name a caller uses.
#
# Supertonic is the platform's voice and the default: everything that speaks an
# agent's words arrives without naming a system and gets it. The other three are
# here because they are asked for a voice differently, and the difference is
# what a study of persuasive speech has to hear. eSpeak NG cannot be asked for
# a feeling at all — it has no model to ask: rules turn letters into phonemes
# and the phonemes are played as resonances. It speaks every platform language,
# Hebrew included, without anybody having been recorded for it.
#
# Piper is the fourth system, beside eSpeak NG rather than in its place: the
# local speech of Home Assistant, begun in 2022 over VITS (2021), with eSpeak
# NG as the method it descends from. It is not a historical reference. One
# recorded dataset trained into one file per voice, a choice of recording and
# nothing to ask of it, and an installed voice for every platform language.
# VoxCPM2 is asked in words, and the words travel inside the utterance, so the
# model itself decides which part of the string is an instruction.
#
# Qwen3-TTS stood in this list. A transformers upgrade elsewhere in the
# platform's environment broke it, and it was removed; VoxCPM2 took its
# place, in its own environment for that reason.
#
# None of the three is ever the platform's voice; a caller has to ask by name.
SPEECH_SYSTEMS = {
    'supertonic': 'supertonic_standard',
    'voxcpm': 'voxcpm_standard',
    'espeak': 'espeak_standard',
    'piper': 'piper_standard',
}
DEFAULT_SPEECH_SYSTEM = 'supertonic'

# Faster than realtime on the CPU, but synthesis is serialised, so one long
# request would make everyone else wait. This is not a cap on what a model may
# produce — it is a guard against a single request holding the queue. Over the
# limit the request is refused with the number, never silently cut short: half a
# sentence spoken as if it were the whole one is worse than no sound at all.
MAX_SPEECH_CHARS = 4000

def _chunk():
    """The chunk module, for the facts that live there.

    Which safety levels may speak and which languages have a voice are
    properties of the chunk, and the chunk is also the enforcing gate. Loaded
    by the availability service, so this route and the agents' GIVEN VOICE note
    read the same one.
    """
    from my_app.services.speech_availability import speech_chunk
    return speech_chunk()


_extra_chunks = {}


def _extra_chunk(name: str):
    """A speech chunk that is not the platform's, loaded from its own file.

    Loaded here rather than through `speech_availability`, and that is on
    purpose: that service answers "does this platform speak", and the platform
    speaks with Supertonic. A second or third synthesiser one can ask for must
    not be able to change that answer.
    """
    module = _extra_chunks.get(name)
    if module is None:
        path = (Path(__file__).resolve().parents[2]
                / "schemas" / "chunks" / f"{name}.py")
        spec = importlib.util.spec_from_file_location(f"_speech_facts_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _extra_chunks[name] = module
    return module


def _system_chunk(system: str):
    """The chunk that will run for this system — the gate, whichever it is."""
    if system == 'espeak':
        return _extra_chunk('output_speech_espeak')
    if system == 'piper':
        return _extra_chunk('output_speech_piper')
    if system == 'voxcpm':
        return _extra_chunk('output_speech_voxcpm')
    return _chunk()


def _server_safety_level() -> str:
    """The level this run obeys: server policy, tightened by the active course.

    Deliberately not a request parameter.
    """
    return resolve_safety_level()


def _header_safe(value) -> str:
    """A header value that cannot break the response.

    HTTP headers are encoded latin-1, and what goes into X-Speech-Voice is not
    ours: with VoxCPM2 it carries the voice description a person typed. A
    single em dash or curly quote in there took the whole response down with a
    UnicodeEncodeError while the audio itself was already finished (2026-08-09,
    when the same header carried Qwen3-TTS's delivery instruction).
    Unencodable characters are dropped rather than escaped — this header is a
    label, and a readable approximation beats a failed request.
    """
    text = str(value or '')
    return text.encode('latin-1', 'ignore').decode('latin-1')[:400]


# The executor wraps whatever a chunk raised in two layers of its own before it
# arrives here. What the chunk said is written to be read by a person — "eSpeak
# NG has no voice for 'xx'" tells someone what to do,
# "speech synthesis failed" tells them nothing — so the wrapping comes off and
# the sentence underneath is handed through.
_ERROR_WRAPPERS = (
    'Python chunk execution failed: ',
    'Backend error: ',
)


def _chunk_reason(error) -> str:
    """The chunk's own sentence, or a plain fallback if there is none."""
    text = str(error or '').strip()
    for wrapper in _ERROR_WRAPPERS:
        _, marker, tail = text.rpartition(wrapper)
        if marker:
            text = tail.strip()
    return text or "Speech synthesis failed."


class SpeechRefused(Exception):
    """Synthesis did not happen, with a reason fit to show a person."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.message = message
        self.status = status


async def _translate_to_english(text: str) -> str:
    """Render `text` in English for a language that has no voice."""
    from schemas.engine.pipeline_executor import executor
    from schemas.engine.stage_orchestrator import translation_context

    result = await executor.execute_pipeline(
        'pre_output/translation_en', text, context_override=translation_context(text))
    english = (getattr(result, 'final_output', '') or '').strip()
    if not result.success or not english:
        raise SpeechRefused(
            "This language has no voice, and the English rendering could not "
            "be produced.", 503)
    return english


def _spoken_language(system: str, language: str) -> str:
    """The language this synthesiser will actually speak in.

    A system with no voice for the language asked for does not say so - it is
    handed an English rendering of the sentence and speaks that instead. Which
    language comes back is therefore a finding, not a detail, and it is decided
    here so that the substitution and the header reporting it can never drift
    apart.

    A chunk that declares `english_fallback: False` never reads `text_en`: it
    refuses a language it has no voice for, with the cause. Handing it an
    English rendering would spend a cloud call on a sentence it will not
    speak.
    """
    meta = _system_chunk(system).CHUNK_META
    if not meta.get("english_fallback", True):
        return language
    return language if language in meta["supported_languages"] else "en"


async def _speak(text: str, language: str, voice: str, safety_level: str,
                 seed=None, mix=None, steps=None, speed=None,
                 system: str = DEFAULT_SPEECH_SYSTEM,
                 voice_description=None, variant=None, pitch=None,
                 cfg_value=None,
                 inference_timesteps=None,
                 emotion=None, length_scale=None,
                 noise_w=None) -> Tuple[bytes, Optional[int],
                                        Optional[str],
                                        Optional[float]]:
    from schemas.engine.pipeline_executor import PipelineContext, executor

    # Custom placeholders reach the chunk only where the config leaves the key
    # open — which is why the output config carries no "voice" parameter.
    placeholders = {
        "TEXT_1": text,
        "text": text,
        "language": language,
    }
    if voice:
        placeholders["voice"] = voice
    if seed is not None:
        placeholders["seed"] = seed
    # Examination parameters, only ever set by a caller that is studying the
    # preset space. Absent, this is the ordinary speaking path, unchanged.
    if mix:
        placeholders["mix"] = mix
    if steps is not None:
        placeholders["steps"] = steps
    if speed is not None:
        placeholders["speed"] = speed
    # VoxCPM2: the speaker described in words. It is composed into the
    # utterance by the worker, not here — the model receives one string and
    # decides for itself which part is an instruction and which part is what to
    # say. Empty means nothing is asked.
    if voice_description:
        placeholders["voice_description"] = voice_description
    # VoxCPM2: the two settings its model card documents. Absent, the
    # configured defaults apply — the card's own values.
    if cfg_value is not None:
        placeholders["cfg_value"] = cfg_value
    if inference_timesteps is not None:
        placeholders["inference_timesteps"] = inference_timesteps
    # eSpeak NG: one of twelve settings of the same formant machinery, and two
    # numbers. None of them is a feeling, which is the point of its column.
    if variant:
        placeholders["variant"] = variant
    if pitch is not None:
        placeholders["pitch"] = pitch
    # Piper: one of the model file's named speakers, and its two scales
    # (`--length-scale`, `--noise-w-scale`). No installed voice names a
    # feeling — fourteen have a single speaker, and the German corpus voice
    # names its 236 by number. Passed as given; a name the corpus voice does
    # not have is refused by the backend rather than answered with speaker 0,
    # and a single-speaker voice ignores the parameter (its chunk says so).
    if emotion:
        placeholders["emotion"] = emotion
    if length_scale is not None:
        placeholders["length_scale"] = length_scale
    if noise_w is not None:
        placeholders["noise_w"] = noise_w

    if _spoken_language(system, language) != language:
        placeholders["text_en"] = await _translate_to_english(text)

    context = PipelineContext(input_text=text, user_input=text)
    context.custom_placeholders = placeholders

    result = await executor.execute_pipeline(
        config_name=SPEECH_SYSTEMS.get(system, SPEECH_CONFIG),
        input_text=text,
        safety_level=safety_level,
        context_override=context,
        context_language=language,
    )

    if not result or not result.success:
        reason = getattr(result, 'error', None) or 'no result'
        logger.error(f"[SPEECH] Synthesis failed: {reason}")
        raise SpeechRefused(_chunk_reason(reason), 503)

    import base64
    metadata = result.metadata or {}
    audio_b64 = metadata.get('audio_data')
    if not audio_b64:
        logger.error("[SPEECH] Pipeline returned no audio_data")
        raise SpeechRefused("Speech synthesis produced no audio.", 503)
    try:
        return (base64.b64decode(audio_b64), metadata.get('seed'),
                metadata.get('voice'), metadata.get('f0_hz'))
    except Exception as e:
        logger.error(f"[SPEECH] Undecodable audio payload: {e}")
        raise SpeechRefused("Speech synthesis produced unreadable audio.", 503)


@speech_bp.route('/status', methods=['GET'])
def status():
    """What the frontend needs to know before it offers a voice at all.

    A voice that is not available should be absent from the interface, not a
    button that fails when pressed.
    """
    from my_app.services.supertonic_backend import (
        MIN_FEMALE_SHARE, PRESETS, UNVOICED_PLATFORM_LANGUAGES)
    from my_app.services.speech_availability import speech_availability
    from config import (
        SUPERTONIC_DEFAULT_VOICE, SUPERTONIC_FLOW_STEPS, SUPERTONIC_SPEED,
        SUPERTONIC_VOICES)

    chunk = _chunk()
    state = speech_availability(probe=True)

    return jsonify({
        'available': state['available'],
        'reason': state['reason'],
        # Spoken in their own language.
        'voiced_languages': list(chunk.CHUNK_META['supported_languages']),
        # Spoken in English, or left unspoken — the caller's choice.
        'unvoiced_languages': list(UNVOICED_PLATFORM_LANGUAGES),
        'fallback_language': 'en',
        'voices': sorted(SUPERTONIC_VOICES),
        'default_voice': SUPERTONIC_DEFAULT_VOICE,
        'max_chars': MAX_SPEECH_CHARS,
        # What a study of the preset space needs to state facts instead of
        # claims: the ten presets the model ships, the five weightings this
        # platform actually speaks with, and the rule those five obey. Read
        # from the running configuration, never restated in an interface.
        'presets': list(PRESETS),
        'platform_mixes': {n: dict(w) for n, w in SUPERTONIC_VOICES.items()},
        'min_female_share': MIN_FEMALE_SHARE,
        'default_steps': SUPERTONIC_FLOW_STEPS,
        'default_speed': SUPERTONIC_SPEED,
        # The other three synthesisers, and what each can be asked for.
        # Everything above describes the platform's own voice and is
        # unaffected by them.
        'systems': _systems_status(),
    }), 200


def _systems_status() -> dict:
    """What each reachable synthesiser is and what it takes.

    Read from the modules that will actually run — speaker list, languages and
    allowed levels come from the backend and the chunk, never from a list
    written out here that could drift from them.
    """
    from config import SUPERTONIC_ENABLED

    supertonic_chunk = _chunk()
    out = {
        'supertonic': {
            'enabled': bool(SUPERTONIC_ENABLED),
            'languages': list(supertonic_chunk.CHUNK_META['supported_languages']),
            'allowed_safety_levels': list(supertonic_chunk.ALLOWED_SAFETY_LEVELS),
            'autoregressive': False,
            'is_platform_voice': True,
            # Asked in a language it has no voice for, it speaks an English
            # translation rather than refusing. Stated, so an interface does
            # not have to assume it.
            'english_fallback': True,
        },
    }

    try:
        from config import VOXCPM_ENABLED
        from my_app.services.voxcpm_backend import get_voxcpm_backend

        voxcpm_chunk = _extra_chunk('output_speech_voxcpm')
        out['voxcpm'] = {
            'enabled': bool(VOXCPM_ENABLED),
            'languages': get_voxcpm_backend().languages(),
            'allowed_safety_levels': list(voxcpm_chunk.ALLOWED_SAFETY_LEVELS),
            # Stated, not hidden: this model can continue past the text it was
            # handed, exactly as Qwen3-TTS could.
            'autoregressive': True,
            'is_platform_voice': False,
            # Bulgarian and Ukrainian have no voice here and come back as an
            # English rendering, not as a refusal.
            'english_fallback': True,
        }
    except Exception as e:
        logger.warning(f"[SPEECH] VoxCPM2 status unavailable: {e}")

    try:
        from config import ESPEAK_ENABLED
        from my_app.services.espeak_backend import get_espeak_backend

        backend = get_espeak_backend()
        espeak_chunk = _extra_chunk('output_speech_espeak')
        out['espeak'] = {
            'enabled': bool(ESPEAK_ENABLED),
            'languages': backend.languages(),
            'allowed_safety_levels': list(espeak_chunk.ALLOWED_SAFETY_LEVELS),
            'autoregressive': False,
            'is_platform_voice': False,
            # What the binary itself reports, and the twelve settings that are
            # offered of it. There is no model to describe.
            'engine': backend.describe(),
            # No English stand-in and none needed: it has every platform
            # language, without anybody having been recorded for it.
            'english_fallback': False,
        }
    except Exception as e:
        logger.warning(f"[SPEECH] eSpeak NG status unavailable: {e}")

    try:
        from config import PIPER_ENABLED
        from my_app.services.piper_backend import get_piper_backend

        backend = get_piper_backend()
        piper_chunk = _extra_chunk('output_speech_piper')
        out['piper'] = {
            'enabled': bool(PIPER_ENABLED),
            # What is installed, read off the files that would speak — not the
            # catalogue, which has all ten. A language missing here is a
            # download, and saying so is the difference between a gap and a
            # limit.
            'languages': backend.languages(),
            'allowed_safety_levels': list(piper_chunk.ALLOWED_SAFETY_LEVELS),
            'autoregressive': False,
            'is_platform_voice': False,
            # Every installed voice with what its own file says about it and,
            # where the dataset documents it, who was recorded; the speaker
            # list is empty for all but the German corpus voice, whose 236
            # names are corpus speaker numbers.
            'voices': [v.describe() for v in backend.voices().values()],
            'default_voice': backend.default_voice,
            # Which file speaks per language when a caller names none: the
            # configured default where its language matches, otherwise the
            # first installed file in name order. Written out, never silent.
            'default_voices': backend.default_voices(),
            # No English stand-in: every platform language has an installed
            # voice, and a language that has none is a missing download, which
            # is refused with that reason rather than answered in English.
            'english_fallback': False,
        }
    except Exception as e:
        logger.warning(f"[SPEECH] Piper status unavailable: {e}")

    return out


@speech_bp.route('', methods=['POST'])
@speech_bp.route('/', methods=['POST'])
def speak():
    """Speak a text. Returns audio/wav, played inline and stored nowhere.

    Body: {"text": "...", "language": "de", "voice": "even"}

    The audio is not a work: it creates no run, no media-store entry, no
    favourite and no export. It is heard and it is gone.
    """
    data = request.get_json(silent=True) or {}

    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'success': False, 'error': 'no text'}), 400
    if len(text) > MAX_SPEECH_CHARS:
        return jsonify({
            'success': False,
            'error': 'text too long to speak',
            'length': len(text),
            'max_chars': MAX_SPEECH_CHARS,
        }), 413

    language = (data.get('language') or 'en').strip().lower()
    voice = (data.get('voice') or '').strip()
    # Optional. Left out, the backend draws one and reports it back in
    # X-Speech-Seed, so an utterance can be asked for again.
    seed = data.get('seed')

    # Examination parameters — a caller studying the preset space rather than
    # having something said. `mix` names a weighting over the ten presets
    # instead of one of the five platform voices; it is spoken once, exactly as
    # given, and never becomes a voice of this platform. The text is still
    # spoken verbatim, and the safety level is still the server's.
    mix = data.get('mix')
    steps = data.get('steps')
    speed = data.get('speed')

    # Which synthesiser. Left out — every path that speaks an agent's words —
    # this is the platform's own voice and nothing changes.
    system = (data.get('system') or DEFAULT_SPEECH_SYSTEM).strip().lower()
    if system not in SPEECH_SYSTEMS:
        return jsonify({
            'success': False,
            'error': f"unknown speech system '{system}'",
            'known': sorted(SPEECH_SYSTEMS),
        }), 400

    # VoxCPM2 only. The description is composed into the utterance itself, and
    # the model decides what to obey and what to speak.
    voice_description = (data.get('voice_description') or '').strip()

    # eSpeak NG only. An unknown variant is a 400, not a substitution. Its
    # speed comes through the `speed` key the Supertonic column already uses -
    # the unit differs (words per minute against a factor), the request key
    # does not.
    variant = (data.get('variant') or '').strip()
    pitch = data.get('pitch')

    # VoxCPM2 only, and the two settings its model card documents.
    cfg_value = data.get('cfg_value')
    inference_timesteps = data.get('inference_timesteps')

    # Piper only. `emotion` is the historical name of its speaker parameter,
    # one of the model file's named speakers; an unknown one is refused, not
    # substituted. The two scales are Piper's own (`--length-scale`,
    # `--noise-w-scale`); absent, the file's values apply.
    emotion = (data.get('emotion') or '').strip()
    length_scale = data.get('length_scale')
    noise_w = data.get('noise_w')

    chunk = _system_chunk(system)
    level = _server_safety_level()
    if level not in chunk.ALLOWED_SAFETY_LEVELS:
        # The chunk refuses this too. Answering here keeps it a clean 403
        # rather than a pipeline error, and says why.
        logger.info(f"[SPEECH] Refused: server safety level '{level or 'unset'}'")
        return jsonify({
            'success': False,
            'error': 'speech is not enabled at this safety level',
            'reason': 'safety_level',
        }), 403

    try:
        audio, seed_used, voice_used, f0_used = asyncio.run(
            _speak(text, language, voice, level, seed, mix, steps, speed,
                   system, voice_description,
                   variant, pitch,
                   cfg_value, inference_timesteps,
                   emotion, length_scale, noise_w))
    except SpeechRefused as e:
        return jsonify({'success': False, 'error': e.message}), e.status
    except ValueError as e:
        # An unusable mix is the caller's mistake, not a synthesis failure —
        # say which, so a field can show what it sent wrong.
        logger.info(f"[SPEECH] Refused: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"[SPEECH] Unexpected failure: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'speech synthesis failed'}), 503

    # AI-Origin Disclosure (EU AI Act Art. 50). This sound is stored nowhere,
    # so there is no recorder to mark it: it is marked on the way out or not
    # at all — and a browser saves what it is handed.
    try:
        from my_app.services.watermark_service import watermark_media_bytes
        from my_app.services.watermark_service import DIGITAL_SOURCE_TYPE_ALGORITHMIC
        audio = watermark_media_bytes(audio, 'output_audio', {
            'model': system,
            'seed': seed_used,
            # eSpeak NG synthesises from rules: nothing was trained, nobody was
            # recorded (see output_speech_espeak.py). IPTC keeps a value for
            # exactly that, and calling it "trained" would be untrue.
            'digital_source_type': (
                DIGITAL_SOURCE_TYPE_ALGORITHMIC if system == 'espeak' else None
            ),
        })
    except Exception as e:
        logger.warning(f"[SPEECH] watermark not applied ({e})")

    return Response(
        audio,
        mimetype='audio/wav',
        headers={
            'Content-Disposition': 'inline; filename="speech.wav"',
            'Content-Length': str(len(audio)),
            'Cache-Control': 'no-store',
            # Hand the seed back: the variation between runs is wanted, and
            # this is what makes a run repeatable rather than merely gone.
            'X-Speech-Seed': str(seed_used) if seed_used is not None else '',
            # Which of the five spoke this sentence. Drawn per sentence unless
            # the caller named one. For an examined mix this is the weighting
            # written out, never a name — an explored point has none.
            'X-Speech-Voice': _header_safe(voice_used),
            # The register this run landed on, measured off the audio being
            # returned. A study needs the measurement, not the intention.
            'X-Speech-F0': str(f0_used) if f0_used is not None else '',
            # What was spoken, which is not always what was asked for: a
            # synthesiser without a voice for this language got an English
            # translation of the sentence instead. Reported, so an interface
            # can say it happened rather than let it pass as the same
            # sentence in another accent.
            'X-Speech-Language': _spoken_language(system, language),
            'Access-Control-Expose-Headers':
                'X-Speech-Seed, X-Speech-Voice, X-Speech-F0, X-Speech-Language',
        },
    )
