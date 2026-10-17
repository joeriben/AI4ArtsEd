"""
Supertonic backend — the platform's speaking voice.

Supertonic 3 is a reader, not a generator: flow matching plus a speech
autoencoder, non-autoregressive. It speaks the text it is given and cannot
continue past it. That is the whole reason it is here; see
DEVELOPMENT_DECISIONS.md, 2026-08-08.

Two things in this file are policy rather than plumbing.

**The voice is mixed, never picked.** Supertonic ships ten preset voices, five
named male and five named female, and no third category. Choosing one would set
a person for the platform — a speaker with a gender, an age, a role. The voice
of this platform is not a person. Every voice below is therefore a linear
combination of presets, and the combination is the statement.

**Several voices per utterance, one per sentence.** Not one voice that varies —
several distinct ones, and the utterance moves between them. The five weightings
in `config.SUPERTONIC_VOICES` are fixed; they are used as they
are and are not to be re-derived.

The platform speaks sentence by sentence, each piece its own call, so choosing
per call IS choosing per sentence. `resolve_voice()` does it in two ways, in
this order:

1. **By fit.** A caller that knows which voice belongs to this sentence names
   it, and that name is honoured. Nothing in this file decides what fits — that
   is the caller's knowledge, not the synthesiser's.
2. **By chance, where there is no fit.** With no name, one is drawn — never the
   one the sentence before it used, so consecutive sentences always differ.

Naming a seed switches the draw to a purely seed-derived one, so a named seed
reproduces the whole utterance including which voice spoke it.

**The female share never drops below 60 percent.** Measured 2026-08-08, six runs
per weighting: an equal-parts mixture over two male presets does not land in the
middle, it lands on the male voice (95–106 Hz, with a 190 Hz female preset in the
mixture). At 50:50 the mixture also becomes unsteady — it sits between two
attractors and the sampling noise decides per run where it falls. From 60 percent
upward it holds its place. `_validated()` enforces this at import time: a
weighting that breaks the rule stops the module from loading rather than quietly
speaking male.

**The variation between runs is wanted, and it is seeded.** A voice that is
never quite the same is a voice that claims no subject, so the variation stays.
Seeding does not take it away: the noise comes from `np.random.randn` in
supertonic/core.py, and a seed set immediately before the call fixes that one
utterance byte for byte. We therefore draw a fresh seed per utterance instead of
fixing one — the variation is unchanged, and it becomes reproducible. Every
synthesis logs its seed and hands it back to the caller; passing it in again
returns the same utterance. Leaving the seed out would give exactly the same
variation and throw away the ability to ever return to a voice one liked.

The variation still has to stay inside the rule, and the weighting alone does not
keep it there. Measured 2026-08-08 over twenty runs per voice: the default of the
day fell below the male line in nine of them, and mixtures containing M2 threw
single runs at 97 Hz. `_f0_median()` therefore measures every synthesis and
`synthesize()` draws a new seed and tries again when it lands too low. A seed
alone does not fix that — it fixes which sample is drawn, not where a *new*
sentence ends up, and every sentence is new. A seed named by the caller is
honoured exactly: one attempt, no correction, because whoever names a seed wants
that utterance and not a better one.
"""

import asyncio
import io
import logging
import threading
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Synthesis is serialised. Not for correctness — ONNX Runtime sessions take
# concurrent calls — but because each call already spreads over
# SUPERTONIC_THREADS cores. Two calls at once would oversubscribe the machine,
# and oversubscription is precisely what costs the most here: letting the
# default grab all 24 cores made the first sentence three times slower
# (1.42 s instead of 0.44 s).
_synth_lock = threading.Lock()


# Seeds are drawn from here and not from the global numpy state, because that
# global state is what synthesis itself consumes and what `_seeded()` overwrites
# for the duration of a call.
_seed_source = np.random.default_rng()

# Which of the five spoke the sentence before this one. Module state, so that
# "a different voice than the last" survives across calls — the platform makes
# one call per sentence.
_last_voice: Optional[str] = None

# np.random.seed() takes 0 .. 2**32-1.
SEED_MAX = 2 ** 32 - 1


def _seeded(seed: int, fn):
    """Run `fn` with numpy's global RNG seeded, then put the state back.

    Supertonic draws its flow-matching noise from `np.random.randn`, which reads
    the *global* numpy state — seeding it is the only way in. Restoring the
    state afterwards keeps a speech call from quietly making unrelated code in
    this process deterministic as a side effect.
    """
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        return fn()
    finally:
        np.random.set_state(state)


def _locked(fn):
    """Run `fn` while holding the synthesis lock."""
    with _synth_lock:
        return fn()


# The 31 languages Supertonic 3 speaks. Hebrew is NOT among them — of the ten
# platform languages it is the one without a voice here.
SUPERTONIC_LANGUAGES = frozenset((
    "en", "ko", "ja", "ar", "bg", "cs", "da", "de", "el", "es", "et", "fi",
    "fr", "hi", "hr", "hu", "id", "it", "lt", "lv", "nl", "pl", "pt", "ro",
    "ru", "sk", "sl", "sv", "tr", "uk", "vi",
))

# The platform's ten (src/i18n/index.ts), split by whether this model has them.
PLATFORM_LANGUAGES = ("ar", "bg", "de", "en", "es", "fr", "he", "ko", "tr", "uk")
UNVOICED_PLATFORM_LANGUAGES = tuple(
    c for c in PLATFORM_LANGUAGES if c not in SUPERTONIC_LANGUAGES)

MIN_FEMALE_SHARE = 0.60


class UnvoicedLanguageError(RuntimeError):
    """This model has no voice for that language.

    Raised deliberately instead of substituting a neighbouring language. In
    particular Russian is never offered in place of Ukrainian.
    """

    def __init__(self, language: str):
        super().__init__(f"Supertonic has no voice for language '{language}'")
        self.language = language


class VoiceMixError(ValueError):
    """A weighting that must not be spoken."""


# The ten presets this model ships, five labelled male and five female.
PRESETS = tuple(f"{s}{i}" for s in "FM" for i in range(1, 6))


def parse_mix(raw) -> Dict[str, float]:
    """Read a weighting sent by a caller who is exploring the preset space.

    Structurally the same check as `_validated()` — known presets, no negative
    weight, sums to one — with two differences, both deliberate:

    * The female floor is not applied. See `_explored_style()` for why.
    * The weighting is never named and never stored as a voice. It describes
      one point that was listened to, and it dies with the request.

    Weights are normalised rather than refused when they miss one by a hair:
    a field sends coordinates, and a coordinate is not a typo.
    """
    if not isinstance(raw, dict) or not raw:
        raise VoiceMixError("mix must be a non-empty object of preset -> weight")

    weights: Dict[str, float] = {}
    for preset, weight in raw.items():
        name = str(preset).strip().upper()
        if name not in PRESETS:
            raise VoiceMixError(
                f"Unknown preset '{preset}'. Known: {', '.join(PRESETS)}")
        try:
            value = float(weight)
        except (TypeError, ValueError):
            raise VoiceMixError(f"Weight for '{name}' is not a number")
        if value < 0:
            raise VoiceMixError(f"Negative weight for '{name}'")
        if value > 0:
            weights[name] = value

    total = sum(weights.values())
    if total <= 0:
        raise VoiceMixError("All weights are zero — nothing to mix")

    return {n: w / total for n, w in weights.items()}


def describe_mix(weights: Dict[str, float]) -> str:
    """A weighting written out, e.g. 'F3 60 / M4 40'.

    Used wherever a voice name would otherwise stand. An explored point has no
    name — writing the weighting there keeps it from ever reading as one of the
    five, in a log line as much as in the interface.
    """
    parts = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))
    return " / ".join(f"{n} {w * 100:.0f}" for n, w in parts)


def _validated(name: str, weights: Dict[str, float]) -> Dict[str, float]:
    """Refuse a weighting that breaks the rule, at import time.

    Three ways to get it wrong, all of them silent if unchecked: weights that
    do not sum to one (the style vector is then scaled, which changes the
    voice), an unknown preset name, and too little female share.
    """
    if not weights:
        raise VoiceMixError(f"Voice '{name}': empty weighting")

    for preset in weights:
        if len(preset) != 2 or preset[0] not in "MF" or preset[1] not in "12345":
            raise VoiceMixError(f"Voice '{name}': unknown preset '{preset}'")

    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise VoiceMixError(f"Voice '{name}': weights sum to {total:.4f}, not 1")

    if any(w < 0 for w in weights.values()):
        raise VoiceMixError(f"Voice '{name}': negative weight")

    female = sum(w for p, w in weights.items() if p.startswith("F"))
    if female < MIN_FEMALE_SHARE - 1e-9:
        raise VoiceMixError(
            f"Voice '{name}': female share {female:.2f} is below the "
            f"{MIN_FEMALE_SHARE:.2f} floor. Measured 2026-08-08: below it the "
            f"mixture collapses into the male range and becomes unsteady "
            f"between runs. See DEVELOPMENT_DECISIONS.md, 2026-08-08.")

    return dict(weights)



# The two characters this model's own front end refuses, and what they become.
#
# `„` and `‚` are the German OPENING quotes, and they are not in the model's
# inventory: a sentence containing one comes back as "Found 1 unsupported
# character(s)" and nothing is spoken at all. Their closing partners `“ ” ‘ ’`
# pass, as do dashes, ellipses and umlauts — checked one by one on 2026-08-14,
# after the platform's own voice fell silent on a Help text set in proper
# German typography.
#
# Replacing them is not a workaround for a bug of ours: the vocabulary of a
# downloaded model is not ours to extend, and preparing text for a synthesiser
# is what a text front end is. Nothing else is touched — this is not a
# normaliser, and it must not become one. Two characters, named, with the
# reason written next to them.
_SPEAKABLE = {
    "\u201e": '"',   # „ opening double, German
    "\u201a": "'",   # ‚ opening single, German
}


def _speakable(text: str) -> str:
    """The utterance with the two characters this model cannot take."""
    for bad, good in _SPEAKABLE.items():
        text = text.replace(bad, good)
    return text


class SupertonicBackend:
    """Loads Supertonic once, mixes the voice, speaks.

    Runs on the CPU on purpose — the GPU stays free for image and video. At
    four threads the first sentence is ready in 0.44 s, which is faster than
    the model this replaces managed on an idle RTX PRO 6000.
    """

    def __init__(self):
        from config import (
            SUPERTONIC_DEFAULT_VOICE, SUPERTONIC_F0_REDRAWS, SUPERTONIC_FLOW_STEPS,
            SUPERTONIC_LOUDNESS_LUFS, SUPERTONIC_MIN_F0_HZ, SUPERTONIC_MODEL,
            SUPERTONIC_SPEED, SUPERTONIC_THREADS, SUPERTONIC_VOICES,
        )

        self.model_name = SUPERTONIC_MODEL
        self.threads = SUPERTONIC_THREADS
        self.flow_steps = SUPERTONIC_FLOW_STEPS
        self.speed = SUPERTONIC_SPEED
        self.loudness_lufs = SUPERTONIC_LOUDNESS_LUFS
        self.min_f0_hz = SUPERTONIC_MIN_F0_HZ
        self.min_f0_redraws = SUPERTONIC_F0_REDRAWS

        # Validated here, so a bad weighting fails on startup and not in front
        # of a room full of people.
        self.voices: Dict[str, Dict[str, float]] = {
            name: _validated(name, weights)
            for name, weights in SUPERTONIC_VOICES.items()
        }
        if SUPERTONIC_DEFAULT_VOICE not in self.voices:
            raise VoiceMixError(
                f"SUPERTONIC_DEFAULT_VOICE '{SUPERTONIC_DEFAULT_VOICE}' is not "
                f"one of {sorted(self.voices)}")
        self.default_voice = SUPERTONIC_DEFAULT_VOICE

        self._tts = None
        self._presets: Dict[str, object] = {}
        self._mixed: Dict[str, object] = {}
        # Styles for weightings under examination. A separate store, so that
        # nothing explored can ever be mistaken for one of the five.
        self._explored: Dict[str, object] = {}
        self._load_lock = asyncio.Lock()
        self._load_error: Optional[str] = None

    # ---------------------------------------------------------------- loading


    async def is_available(self) -> bool:
        """True when the model can actually speak, not when it is configured."""
        try:
            await self._get_tts()
            return True
        except Exception as e:
            logger.error(f"[SUPERTONIC] Not available: {e}")
            return False

    async def _get_tts(self):
        if self._tts is not None:
            return self._tts

        async with self._load_lock:
            if self._tts is not None:
                return self._tts

            def _load():
                from supertonic import TTS
                return TTS(model=self.model_name, auto_download=True,
                           intra_op_num_threads=self.threads)

            logger.info(
                f"[SUPERTONIC] Loading {self.model_name} "
                f"({self.threads} threads, CPU)")
            self._tts = await asyncio.to_thread(_locked, _load)
            logger.info(f"[SUPERTONIC] Loaded. Voices: {sorted(self.voices)}")
            return self._tts

    # ----------------------------------------------------------------- voices

    def _preset(self, tts, name: str):
        if name not in self._presets:
            self._presets[name] = tts.get_voice_style(voice_name=name)
        return self._presets[name]

    def _build_style(self, tts, weights: Dict[str, float]):
        """A style tensor pair from a weighting over presets.

        Both tensors carry the voice — `ttl` (1, 50, 256) the sound formation,
        `dp` (1, 8, 16) the durations — so both are mixed with the same
        weights. Mixing only one produces a voice that sounds like A but is
        paced like B.
        """
        from supertonic.core import Style

        ttl = sum(w * self._preset(tts, n).ttl for n, w in weights.items())
        dp = sum(w * self._preset(tts, n).dp for n, w in weights.items())
        return Style(style_ttl_onnx=np.asarray(ttl, dtype=np.float32),
                     style_dp_onnx=np.asarray(dp, dtype=np.float32))

    def _style(self, tts, voice: str):
        """The mixed style for one of the five platform voices, built once."""
        if voice in self._mixed:
            return self._mixed[voice]

        style = self._build_style(tts, self.voices[voice])
        self._mixed[voice] = style
        return style

    def _explored_style(self, tts, weights: Dict[str, float]):
        """The style for a weighting that is being LOOKED AT, not spoken with.

        Kept apart from `_style` on purpose, and the separation is the point:

        `self.voices` is how this platform speaks. It is validated at import
        time by `_validated()`, the female share never falls below
        MIN_FEMALE_SHARE, and those five weightings are fixed. Nothing here
        may reach that dictionary or add to it — an explored weighting is
        material under examination, never a voice the platform acquires.

        The floor is deliberately NOT applied here, and that is not a hole in
        it. The floor exists so the platform never speaks as a man by accident.
        A study that may only look at the female side of the register cannot
        show what the register does — and what it does (equal parts over two
        male presets landing on the male voice, not in the middle) is exactly
        the finding of 2026-08-08 that the floor was built from. Refusing to
        let anyone hear that would leave the rule standing as an assertion.

        Cached by weighting, so re-visiting a point on a field costs nothing.
        """
        key = "|".join(f"{n}:{weights[n]:.4f}" for n in sorted(weights))
        cached = self._explored.get(key)
        if cached is None:
            cached = self._build_style(tts, weights)
            self._explored[key] = cached
        return cached

    def resolve_voice(self, voice: Optional[str], seed: Optional[int] = None) -> str:
        """Which of the five speaks this sentence. Never a silent miss.

        A named voice is the fit case and wins. Otherwise one is drawn — see
        the module docstring. `_last_voice` is module state on purpose:
        synthesis is serialised anyway, and "not the one before" needs to know
        what the one before was.
        """
        global _last_voice

        name = (voice or "").strip()
        if name and name in self.voices:
            _last_voice = name
            return name
        if name:
            logger.warning(f"[SUPERTONIC] Unknown voice '{name}', drawing one")

        palette = sorted(self.voices)
        if seed is not None:
            # A named seed has to reproduce the voice too, so no history here.
            drawn = palette[int(np.random.default_rng(seed).integers(len(palette)))]
        else:
            choices = [v for v in palette if v != _last_voice] or palette
            drawn = choices[int(_seed_source.integers(len(choices)))]
        _last_voice = drawn
        return drawn

    def resolve_seed(self, seed) -> Optional[int]:
        """A caller's seed, or None meaning "draw a fresh one".

        Follows the platform convention used by the image and audio chunks:
        `None`, `"random"` and `-1` all mean draw. An unreadable value draws
        too, rather than failing the utterance over it.
        """
        if seed is None or seed == -1:
            return None
        if isinstance(seed, str):
            text = seed.strip().lower()
            if not text or text == "random":
                return None
            try:
                seed = int(text)
            except ValueError:
                logger.warning(
                    f"[SUPERTONIC] Unreadable seed '{seed}', drawing one instead")
                return None
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            logger.warning(
                f"[SUPERTONIC] Unreadable seed '{seed}', drawing one instead")
            return None
        if seed < 0:
            return None
        return seed % (SEED_MAX + 1)

    def resolve_language(self, language: Optional[str]) -> str:
        """The language code this model will speak, or refuse.

        Kept as a separate step so that "no voice for Hebrew" can never arrive
        disguised as "the model is not installed".
        """
        code = (language or "").strip().lower()
        if code in SUPERTONIC_LANGUAGES:
            return code
        raise UnvoicedLanguageError(code)

    # ------------------------------------------------------------- synthesis

    def _to_wav(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """One loudness for the whole utterance, then WAV.

        The procedure moved to `services/speech_audio.py` unchanged, so that
        the other synthesisers finish their audio the same way. Three systems
        heard next to each other in one player must not differ by their
        normalisation, or the comparison is between normalisations.
        """
        from my_app.services.speech_audio import to_wav

        return to_wav(audio, sample_rate, self.loudness_lufs)

    def _f0_median(self, x: np.ndarray, sample_rate: int) -> float:
        """Median fundamental frequency over the voiced parts, in Hz.

        The procedure moved to `services/voice_register.py` unchanged, so that
        the second synthesiser is measured by the same one and the two readings
        can be held against each other. What it does and what it returns is
        described there; the register rule below is unaffected.
        """
        from my_app.services.voice_register import median_f0

        return median_f0(x, sample_rate)

    async def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        voice: Optional[str] = None,
        seed=None,
        mix: Optional[Dict[str, float]] = None,
        steps: Optional[int] = None,
        speed: Optional[float] = None,
        **kwargs,
    ) -> Tuple[bytes, int, str, float]:
        """Speak `text` verbatim.

        Returns (WAV bytes, seed, the voice that spoke, measured f0 in Hz).
        The f0 is what `_f0_median()` read off the audio that is being handed
        back — the same measurement the register rule is built on. It is
        reported rather than kept internal because a study of the preset space
        has to be able to show where a mixture actually landed.

        `seed` may be None, "random" or -1 to draw one — which is the normal
        case, and the drawn value comes back so the utterance can be repeated.

        `mix` puts the call into examination mode: a weighting over presets is
        spoken ONCE, exactly as given, with no register correction and without
        touching `self.voices`. `voice` is ignored when `mix` is present.
        `steps` and `speed` likewise override the configured values for this
        one call — they are the machine's own parameters, and hearing them
        change is the point of a study. None of the three affects any other
        call.

        Raises UnvoicedLanguageError when this model has no voice for the
        language — the caller decides what to do about it, this backend does
        not substitute one.
        """
        if not text or not text.strip():
            raise ValueError("No text to speak")

        text = _speakable(text)
        lang = self.resolve_language(language)
        requested_seed = self.resolve_seed(seed)
        tts = await self._get_tts()

        if mix:
            # Examination: the weighting IS the statement, so it is spoken as
            # given. No redraw — a corrected run would hide the very thing a
            # study of the register is looking for.
            name = describe_mix(mix)
            style = self._explored_style(tts, mix)
            corrects_register = False
        else:
            name = self.resolve_voice(voice, requested_seed)
            style = self._style(tts, name)
            corrects_register = True

        total_steps = self.flow_steps if steps is None else max(1, int(steps))
        rate = self.speed if speed is None else float(speed)

        requested = requested_seed

        def _generate(used: int) -> Tuple[np.ndarray, int]:
            def _call():
                audio, _ = tts.synthesize(
                    text=text,
                    lang=lang,
                    voice_style=style,
                    total_steps=total_steps,
                    speed=rate,
                )
                return audio, int(getattr(tts, "sample_rate", 44100))
            return _seeded(used, _call)

        # Draw until the register holds, then keep the highest attempt. Keeping
        # the highest rather than the last matters: the draws are independent,
        # so the last one can be worse than the one before it. A seed named by
        # the caller gets exactly one attempt — see the module docstring.
        attempts = (1 if requested is not None or not corrects_register
                    else 1 + max(0, self.min_f0_redraws))
        best_audio = None
        best_rate = 44100
        best_f0 = -1.0
        best_seed = 0
        tried = 0

        for _ in range(attempts):
            used = (requested if requested is not None
                    else int(_seed_source.integers(0, SEED_MAX)))
            audio, sample_rate = await asyncio.to_thread(
                _locked, lambda u=used: _generate(u))
            tried += 1
            f0 = self._f0_median(
                np.asarray(audio, dtype=np.float32).squeeze(), sample_rate)
            if f0 > best_f0:
                best_audio, best_rate, best_f0, best_seed = (
                    audio, sample_rate, f0, used)
            # 0.0 means nothing voiced was found — no verdict, not a low one.
            if f0 <= 0.0 or requested is not None or f0 >= self.min_f0_hz:
                break
            logger.info(
                f"[SUPERTONIC] Seed {used} landed at {f0:.0f} Hz, below the "
                f"{self.min_f0_hz:.0f} Hz floor — drawing again")

        if corrects_register and best_f0 > 0.0 and best_f0 < self.min_f0_hz:
            # Said out loud rather than swallowed: this run speaks lower than
            # the voice is meant to, and that is the thing the policy exists to
            # prevent. Speaking is still better than silence.
            logger.warning(
                f"[SUPERTONIC] Voice '{name}' stayed at {best_f0:.0f} Hz after "
                f"{tried} attempt(s), below the {self.min_f0_hz:.0f} Hz floor "
                f"(seed {best_seed})")

        wav = self._to_wav(best_audio, best_rate)
        logger.info(
            f"[SUPERTONIC] {len(text)} chars | {lang} "
            f"| {'mix' if mix else 'voice'}={name} | steps={total_steps} "
            f"| seed={best_seed} | {best_f0:.0f} Hz | {tried} draw(s) "
            f"| {len(wav)} B")
        return wav, best_seed, name, best_f0

    async def unload(self) -> bool:
        """Drop the session. Used by the model-management surface."""
        if self._tts is None:
            return False
        async with self._load_lock:
            self._tts = None
            self._presets.clear()
            self._mixed.clear()
            self._explored.clear()
        logger.info("[SUPERTONIC] Unloaded")
        return True


_backend: Optional[SupertonicBackend] = None


def get_supertonic_backend() -> SupertonicBackend:
    global _backend
    if _backend is None:
        _backend = SupertonicBackend()
    return _backend


