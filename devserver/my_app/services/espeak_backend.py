"""
eSpeak NG backend — the computer voice from before AI.

The first column of the voices comparison, and the only synthesiser here that
was never trained on anything. There is no model file, no dataset, nobody
recorded: a set of hand-written rules turns the letters of a language into
phonemes, and every phoneme is played as a handful of resonances — formant
synthesis, the method computers spoke with for decades before neural
synthesis existed. Its own README says what that costs and what it buys:
"The speech is clear, and can be used at high speeds, but is not as natural or
smooth as larger synthesizers which are based on human speech recordings."

**Where it comes from.** Written as `speak` for Acorn/RISC OS from 1995 by
Jonathan Duddington, rewritten as eSpeak in 2007, forked to eSpeak NG in late
2015 (README, "History"). It also carries Klatt formant synthesis as a set of
variants, which is the line the method itself descends from — Dennis Klatt's
synthesiser, described 1980 and 1990.

**Nothing is downloaded and nothing is trained.** It is a system package
(`espeak-ng`, GPL-3.0), a few megabytes for over a hundred languages, and it
runs on the CPU. Whoever installs the platform has it already: Piper embedded
it too, as its phonemiser.

**All ten platform languages, and no provenance question to answer.** The other
two backends have to say whose recordings they were built from — Supertonic and
VoxCPM2 both decline to. Here the question does not arise: no one's voice went
into it. What can be criticised instead is that every language's rules were
written by somebody, that the quality of those rules differs from language to
language, and that a rule-written pronunciation is a decision about how a
language ought to sound.

**What can be asked of it.** A variant — twelve of them are offered, `f1`-`f5`
and `m1`-`m7`, each a different setting of the same formant machinery — plus
speed and pitch as plain numbers. That is the point of its place in the row:
the oldest procedure is the one with dials on it, and none of the dials is a
feeling.

This is not the platform's voice and must never become it. A caller reaches it
only by naming it (`system: "espeak"`).
"""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class UnvoicedLanguageError(RuntimeError):
    """This eSpeak NG installation has no voice for that language.

    Raised instead of substituting a neighbouring language, exactly as in the
    other backends.
    """

    def __init__(self, language: str):
        super().__init__(f"No eSpeak NG voice for language '{language}'")
        self.language = language


# Platform language code -> the eSpeak NG voice name that speaks it.
#
# Written out rather than probed, because two of them are a choice and not a
# lookup: `en` is `en-us` and `es` is European Spanish, where eSpeak NG also
# offers en-gb, es-419 and es-mx. Naming the choice here keeps it visible
# instead of leaving it to whatever the voice list happens to return first.
LANGUAGE_VOICES = {
    "ar": "ar",
    "bg": "bg",
    "de": "de",
    "en": "en-us",
    "es": "es",
    "fr": "fr-fr",
    "he": "he",
    "ko": "ko",
    "tr": "tr",
    "uk": "uk",
}

# The variants offered, in the order they are shown. eSpeak NG ships about a
# hundred of them; these twelve are the systematic set — the same machinery at
# twelve settings, five named female and seven named male, which is the same
# leading distinction the Supertonic column carries and can be read against it.
#
# The named ones (`Alex`, `grandma`, `Storm`, `robosoft`) and the `klatt` set
# are deliberately not in this list: they are characters and a second synthesis
# method, and either would turn a comparison of procedures into a costume box.
OFFERED_VARIANTS = ("f1", "f2", "f3", "f4", "f5",
                    "m1", "m2", "m3", "m4", "m5", "m6", "m7")


class EspeakBackend:
    """Speaks through the `espeak-ng` binary. No model, no state, no warm-up."""

    def __init__(self):
        from config import (
            ESPEAK_BIN,
            ESPEAK_DATA_DIR,
            ESPEAK_LOUDNESS_LUFS,
        )
        self.binary = Path(ESPEAK_BIN)
        self.data_dir = Path(ESPEAK_DATA_DIR)
        self.loudness_lufs = float(ESPEAK_LOUDNESS_LUFS)
        self._version: Optional[str] = None

    # ------------------------------------------------------------- what it is

    def version(self) -> str:
        """The version string the binary reports, read once."""
        if self._version is not None:
            return self._version
        self._version = ""
        try:
            out = subprocess.run([str(self.binary), "--version"],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            first = (out.stdout or b"").decode("utf-8", "ignore").strip()
            # "eSpeak NG text-to-speech: 1.51.1  Data at: /usr/share/..."
            if ":" in first:
                self._version = first.split(":", 1)[1].split()[0]
        except Exception as e:
            logger.warning(f"[ESPEAK] Could not read version: {e}")
        return self._version

    def variants(self) -> List[str]:
        """The offered variants that this installation actually has."""
        folder = self.data_dir / "voices" / "!v"
        if not folder.is_dir():
            logger.warning(f"[ESPEAK] No variant directory at {folder}")
            return []
        present = {p.name for p in folder.iterdir() if p.is_file()}
        return [v for v in OFFERED_VARIANTS if v in present]

    def languages(self) -> List[str]:
        """The platform languages this can speak. All ten, unless the package
        was built without their data."""
        return sorted(LANGUAGE_VOICES)

    def describe(self) -> Dict[str, object]:
        """What the status route hands the interface."""
        return {
            "version": self.version(),
            "sample_rate": 22050,
            "variants": self.variants(),
        }

    def resolve_language(self, language: Optional[str]) -> str:
        """The eSpeak NG voice name for a platform language, or refuse."""
        code = (language or "").strip().lower()
        if code in LANGUAGE_VOICES:
            return code
        raise UnvoicedLanguageError(code)

    def resolve_variant(self, variant: Optional[str]) -> str:
        """The variant that will speak, or "" for the language's plain voice."""
        name = (variant or "").strip()
        if not name:
            return ""
        if name not in self.variants():
            raise ValueError(
                f"Unknown eSpeak NG variant '{name}'. "
                f"Offered: {', '.join(self.variants())}")
        return name

    async def is_available(self) -> bool:
        """True when this could actually speak, not when it is configured."""
        if not self.binary.is_file():
            logger.error(f"[ESPEAK] Binary not found: {self.binary}")
            return False
        return True

    # -------------------------------------------------------------- synthesis

    async def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        variant: Optional[str] = None,
        speed: Optional[int] = None,
        pitch: Optional[int] = None,
        **kwargs,
    ) -> Tuple[bytes, str, float]:
        """Speak `text` verbatim.

        Returns (WAV bytes, what spoke it, measured f0 in Hz). The f0 is read
        off the audio being handed back, by the same procedure the other two
        synthesisers are measured with — and here it is worth saying twice that
        it is a measurement of resonances nobody's larynx produced.
        """
        from my_app.services.speech_audio import read_wav, to_wav
        from my_app.services.voice_register import median_f0

        if not self.binary.is_file():
            raise RuntimeError(
                f"eSpeak NG is not installed at {self.binary}. It is a system "
                f"package: `dnf install espeak-ng` / `apt install espeak-ng`.")

        code = self.resolve_language(language)
        chosen = self.resolve_variant(variant)
        voice = LANGUAGE_VOICES[code] + (f"+{chosen}" if chosen else "")

        command = [str(self.binary), "-v", voice, "--stdin"]
        if speed is not None:
            command += ["-s", str(int(speed))]
        if pitch is not None:
            command += ["-p", str(int(pitch))]

        with tempfile.TemporaryDirectory(prefix="espeak-") as workdir:
            out = Path(workdir) / "speech.wav"
            command += ["-w", str(out)]

            def _run():
                # No timeout: this is a synthesis call, and a cap here would
                # cut an utterance off mid-sentence rather than let it finish.
                return subprocess.run(
                    command, input=text.encode("utf-8"),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            logger.info(f"[ESPEAK] {len(text)} chars | {voice} | {code}")
            process = await asyncio.to_thread(_run)

            if process.returncode != 0:
                detail = (process.stderr or b"").decode("utf-8", "ignore").strip()
                logger.error(f"[ESPEAK] Failed ({process.returncode}): {detail[-400:]}")
                raise RuntimeError("eSpeak NG synthesis failed")
            if not out.is_file():
                raise RuntimeError("eSpeak NG wrote no audio")
            raw = out.read_bytes()

        samples, sample_rate = read_wav(raw)
        wav = to_wav(samples, sample_rate, self.loudness_lufs)
        f0_hz = median_f0(samples, sample_rate)

        logger.info(f"[ESPEAK] {len(wav)} bytes ({voice}, {f0_hz:.0f} Hz)")
        return wav, voice, f0_hz


_backend: Optional[EspeakBackend] = None


def get_espeak_backend() -> EspeakBackend:
    global _backend
    if _backend is None:
        _backend = EspeakBackend()
    return _backend
