"""
Piper backend — one file per voice, trained on one recorded dataset.

The second machine of the voices comparison, in the third of its five
columns, beside eSpeak NG. A Piper voice has no control over emotion
or register, and no way to be asked for one. The speaker heard is the
recorded one; pitch and rhythm are sampled anew at every run, which is what
VITS was built for ("a text input can be spoken in multiple ways with
different pitches and rhythms", Kim, Kong and Son 2021, abstract). A caller
can set Piper's phoneme length (`--length-scale`, the tempo) and phoneme
width noise (`--noise-w-scale`); the comparison column sets neither.

What it offers instead is a choice of voice file, and every installed voice
is in it: a studio professional and a volunteer reader, said
apart where the dataset says who was recorded rather than sorted apart before
anyone hears them. Every file is trained on one dataset, and most of the
installed files were fine-tuned from an English base voice (each MODEL_CARD
says which: nine of the fifteen here, from lessac, ryan or LibriTTS-R). Two
datasets are refused, both the same hobbyist reader: `thorsten_emotional`,
eight labelled feelings performed by one reader, replayed by speaker id,
is refused because acted emotions from one reading say nothing about
what a synthesiser can do, and this column would read them as Piper's;
`thorsten` itself is refused because the column offers professional voices
only. See EXCLUDED_DATASETS.

**Provenance is disclosed, which Supertonic and VoxCPM2 do not do.** Both
decline to say whose voices they were built from, and neither says whether
those people agreed. Every Piper voice names its dataset and the terms it was
released under — see docs/SPRACHSYNTHESE_PIPER_KONFIGURATION.md, §2, and
docs/installation/MODELS_REQUIRED.md, compiled from the models' own MODEL_CARD
files. What is additionally known about who did the reading stands in the
interface's copy (`compare.voice.piper.recordings.<dataset>` in en.ts, one
entry per dataset that documents it), keyed by the dataset the sidecar names;
nothing about a voice is restated in this service.

**Where it comes from.** Written by Michael Hansen for the Rhasspy project,
begun 2022, over VITS (Kim, Kong and Son, 2021): "Voices are trained with VITS
and exported to the onnxruntime", and the aim in the makers' own words was "a
fast, local neural text to speech system that sounds great and is optimized for
the Raspberry Pi 4" (rhasspy/piper README, 2023). Development has since moved
to OHF-Voice/piper1-gpl, whose README says "A fast and local neural
text-to-speech engine that embeds espeak-ng for phonemization"; that is the
package installed here (piper-tts 1.6.0).

**It runs as a separate process in its own environment.** Piper is a
downloaded technology like every model here: none of it lives in this
repository, `download_piper.sh` fetches it, and its own environment keeps its
onnxruntime and espeak-ng data from colliding with the platform's. It runs on
the CPU, 0.03–0.22 s per sentence (measured 2026-09-17), and never touches the
card — declared as such in devserver/tests/test_gpu_admission_coverage.py.

**Every platform language.** Supertonic has nine of ten and no Hebrew; VoxCPM2
has eight and answers Bulgarian and Ukrainian in English; eSpeak NG has all
ten from rules. Piper has all ten from recordings, so it never needs the
English fallback — and where the catalogue offers several regional voices,
several are installed: Spanish from Spain, Mexico and Argentina, English from
the US and Britain, two of the three Ukrainian voices. One voice per language
would have let this platform decide, silently and once, that Spanish is Spain.
Where there is only one, that is worth hearing too: Arabic here is one voice
from Jordan. A caller that names no voice gets the configured default where
its language matches, otherwise the first installed file of the language in
name order (Spanish: Argentina); `/api/speech/status` reports that choice per
language under `default_voices`, and the comparison column names its voice
wherever the lit language has a file.

**Any installed voice can be named for any sentence**, so that foreign voices
can be explored as well. What then happens is the file's phonemiser's business, measured
on 2026-09-18 with `PiperVoice.phonemize` of the installed piper-tts 1.6.0:
fourteen files phonemise with eSpeak NG set to the file's language
(`espeak.voice` in the sidecar). eSpeak NG applies that language's rules to
the words it reads in it — under `en_US-lessac-high`, whose sidecar names
`en-us`, „Der Lappen" comes out dˈɛɹ lˈæpən, and under `en_GB-cori-high`,
which names `en`, dˈeə lˈapən — and switches language for other words, above
all by script (under the Arabic, Bulgarian, Korean and Ukrainian files a
Latin-script sentence goes to English; under the French file „Eisschrank"
does), or spells a word in a script it has no rules for letter by letter with
the script's name in front (under the German file, Cyrillic: „kyrillisch ge,
kyrillisch a …"). Piper strips the switch marks and
the file speaks the phonemes its id map has; the rest is dropped
(`phoneme_ids.py`). The fifteenth, `he_IL-saspeech-medium`, has
`phoneme_type: "hebrew"` and phonemises with Piper's own Hebrew phonemiser,
which keeps Hebrew letters only: a sentence without them phonemises to spaces
and the model voices those, so `synthesize` refuses such a text with the cause
rather than return audio with none of the sentence in it. The comparison
column chooses in the three steps of Piper's own sample page
(rhasspy.github.io/piper-samples, four selects: Language, Voice, Quality,
Speaker) and of Home Assistant's Wyoming integration (the voices of a
language, each named "name (quality)"; the speaker as an option —
`wyoming_piper/__main__.py`, `homeassistant/components/wyoming/tts.py`): the
voice is selectable the way these Piper integrations make it. The language
first, the interface's preselected, then the voices of that language, then, in
the corpus file, one of its 236 speakers (`emotion`), one per call. What the
lit file does with a sentence of another language is heard, or refused with
the cause. No per-file line under the choice says this in advance; such a
stack of lines makes the panel too long.

**What is documented about a corpus speaker lies beside the model, never in
this repository.** The German corpus file names its speakers by their
Multilingual LibriSpeech number and its sidecar says nothing else about them.
The corpus does: its `metainfo.txt` (in the dataset's repository, one row per
chapter) records each speaker's gender and the minutes recorded, from 0.2 to
36,041.8 minutes across the 236. `download_piper.sh` fetches that file to
`<stem>.metainfo.txt` beside the model; `PiperVoiceModel` sums the minutes
per speaker and `describe()` reports both under `speaker_info`, so the
comparison column can name them in its speaker list. Without the file — or
with one that is unreadable, wrongly encoded, or covers only some of the
speakers, which is what a half-finished download leaves — the list carries
the numbers alone, as the model names them: this file documents the voices
and can never take them down. The corpus's terms
forbid identifying the speakers ("You agree to not attempt to determine the
identity of speakers in this dataset", its dataset card), so the number is
shown and nothing is resolved from it.

This is not the platform's voice and must never become it. A caller reaches it
only by naming it (`system: "piper"`).
"""

import asyncio
import json
import logging
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# The Hebrew LETTERS: the twenty-two consonants with their final forms
# (U+05D0–U+05EA) and the presentation forms (U+FB1D–U+FB4F). The block
# U+0590–U+05FF also holds vowel points, cantillation marks and punctuation,
# and none of those phonemises on its own, so the guard below asks for
# letters. A letter of any script, for the share the guard compares.
HEBREW_LETTER = re.compile(r"[\u05D0-\u05EA\uFB1D-\uFB4F]")
ANY_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


class UnvoicedLanguageError(RuntimeError):
    """This installation has no Piper voice for that language.

    Raised instead of substituting a neighbouring language, exactly as in the
    other backends. What is missing is a download, not a capability — see
    the module docstring.
    """

    def __init__(self, language: str):
        super().__init__(f"No Piper voice installed for language '{language}'")
        self.language = language


# Datasets that are never offered, even if someone puts the file in the model
# directory. Both are the same hobbyist reader. `thorsten_emotional` — eight
# labelled feelings performed by one reader, replayed by speaker id — is
# refused: one dataset's acted emotions say nothing about
# what a synthesiser can do, and a column that compares synthesisers would
# read them as Piper's. `thorsten` is refused because the column offers
# professional voices only.
#
# What a dataset documents about who was recorded is not restated here: it
# stands in the interface's copy, keyed by the `dataset` the sidecar names
# (`compare.voice.piper.recordings.<dataset>`, en.ts), where it is translated.
EXCLUDED_DATASETS = {"thorsten", "thorsten_emotional"}


class PiperVoiceModel:
    """One installed .onnx and what its sidecar JSON says about it.

    Everything here is read from the file that will actually speak. Nothing
    about a Piper voice is written out in this repository — the speaker map in
    particular, because a restated map would let an interface offer a speaker
    the model does not have.
    """

    def __init__(self, path: Path, meta: dict):
        self.path = path
        self.key = path.name[:-len(".onnx")] if path.name.endswith(".onnx") else path.name
        # `or {}` and not a default: a sidecar that carries the key with a
        # null would otherwise raise here, and `voices()` would take every
        # installed voice down with it.
        audio = meta.get("audio") or {}
        language = meta.get("language") or {}
        self.sample_rate = int(audio.get("sample_rate", 22050))
        # The quality level as the sidecar names it under `audio.quality`.
        # Piper's sample page names four levels ("Voices are trained at one
        # of 4 'quality' levels", rhasspy.github.io/piper-samples, read
        # 2026-09-19); the fifteen files installed here carry three of them,
        # low, medium and high.
        self.quality = str(audio.get("quality", "") or "")
        self.language = str(
            language.get("family")
            or str(language.get("code", ""))[:2]
            or ""
        ).lower()
        # The region the catalogue folds into its language code ("DE", "GB",
        # "US", "MX" ...) and this platform's language codes do not carry.
        self.region = str(language.get("region", "") or "").upper()
        self.dataset = str(meta.get("dataset", "") or "")
        # 0.2.0 to 1.5.0 across the installed voices, so it describes the file
        # and never Piper as such.
        self.piper_version = str(meta.get("piper_version", "") or "")
        # "espeak" for fourteen of the installed files (absent in the sidecar
        # of the oldest, which Piper treats as espeak); "hebrew" for the
        # Hebrew file, which has its own phonemiser. The module docstring
        # says what each of the two does with a foreign sentence.
        self.phoneme_type = str(meta.get("phoneme_type") or "espeak").lower()
        self.num_speakers = int(meta.get("num_speakers", 1) or 1)
        # name -> id. Empty for a single-speaker voice, which is fourteen of
        # the fifteen installed; the German corpus voice names 236.
        raw = meta.get("speaker_id_map") or {}
        self.speakers: Dict[str, int] = {
            str(name): int(index) for name, index in raw.items()
        } if self.num_speakers > 1 else {}
        inference = meta.get("inference", {}) or {}
        self.length_scale = float(inference.get("length_scale", 1.0))
        self.noise_scale = float(inference.get("noise_scale", 0.667))
        self.noise_w = float(inference.get("noise_w", 0.8))
        # What the corpus documents about the speakers, read from the
        # corpus's own metainfo beside the model (module docstring,
        # download_piper.sh); {} for a single-speaker voice or without the file.
        self.speaker_info: Dict[str, dict] = self._read_speaker_info()

    def _read_speaker_info(self) -> Dict[str, dict]:
        """Gender and recorded minutes per speaker, from `<stem>.metainfo.txt`.

        The file is the corpus's own: pipe-separated, one row per chapter, a
        header row, the columns SPEAKER | GENDER | PARTITION | MINUTES |
        BOOK ID | TITLE | CHAPTER. Minutes are summed per speaker.

        Exactly two results, and never a third: every speaker of this model
        with both values, or nothing. A file that covers only some of them is
        a half-finished download, not a corpus, and a partial map would put
        plausible wrong amounts under the speakers it did reach; it is
        refused as a whole and logged with the count. The same for a missing
        file, an unreadable one, a wrongly encoded one and a non-finite
        number: the speakers then stand by their number alone, as the model
        names them, and no error reaches the caller — this file documents the
        voices and must never be able to take them down.
        """
        if not self.speakers:
            return {}
        info_path = self.path.with_name(f"{self.key}.metainfo.txt")
        if not info_path.is_file():
            logger.info(f"[PIPER] {self.key}: no {info_path.name} beside the "
                        f"model; its speakers stand by number alone")
            return {}
        gender: Dict[str, str] = {}
        minutes: Dict[str, float] = {}
        try:
            with open(info_path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    cells = [c.strip() for c in line.split("|")]
                    if len(cells) < 4 or cells[0] not in self.speakers:
                        continue
                    try:
                        value = float(cells[3])
                    except ValueError:
                        continue
                    if not math.isfinite(value):
                        logger.warning(
                            f"[PIPER] {info_path.name}: speaker {cells[0]} has "
                            f"'{cells[3]}' minutes; the file is not used")
                        return {}
                    minutes[cells[0]] = minutes.get(cells[0], 0.0) + value
                    if not gender.get(cells[0]):
                        gender[cells[0]] = cells[1]
        except OSError as exc:
            logger.warning(f"[PIPER] {info_path.name} unreadable: {exc}")
            return {}
        if len(minutes) != len(self.speakers):
            logger.warning(
                f"[PIPER] {info_path.name} documents {len(minutes)} of this "
                f"model's {len(self.speakers)} speakers; the file is not used. "
                f"Delete it and run download_piper.sh again.")
            return {}
        return {
            name: {"gender": gender.get(name, ""), "minutes": round(total, 1)}
            for name, total in minutes.items()
        }

    def resolve_speaker(self, name: Optional[str]) -> Optional[Tuple[str, int]]:
        """The (name, id) that will speak, or None for a single-speaker voice.

        Two things this must never do, and Piper does both if left alone:

        An unknown name is refused rather than falling back to speaker 0. A
        silent fallback would answer a request for one speaker with another,
        and on a 236-speaker corpus nothing in the audio would show it.

        A *missing* name is resolved here rather than left to the CLI, which
        also takes speaker 0. Something always speaks, and whichever it is has
        to be named back to the caller. "neutral" is chosen where a model has
        a speaker by that name — the one name that does not claim a state.
        """
        if not self.speakers:
            return None

        key = (name or "").strip()
        if key:
            if key not in self.speakers:
                raise ValueError(
                    f"Voice '{self.key}' has no speaker '{key}'. "
                    f"Known: {', '.join(sorted(self.speakers))}")
            return key, self.speakers[key]

        if "neutral" in self.speakers:
            return "neutral", self.speakers["neutral"]
        return min(self.speakers.items(), key=lambda kv: kv[1])

    def describe(self) -> dict:
        return {
            "key": self.key,
            "language": self.language,
            # The dataset, as the sidecar names it. The interface looks up what
            # is documented about the recording under this key; a dataset with
            # no entry there is "not documented", never a verdict.
            "dataset": self.dataset,
            "region": self.region,
            "quality": self.quality,
            "sample_rate": self.sample_rate,
            "piper_version": self.piper_version,
            "phoneme_type": self.phoneme_type,
            # Sorted by id, not alphabetically: the order is the dataset's.
            "speakers": [n for n, _ in sorted(self.speakers.items(),
                                              key=lambda kv: kv[1])],
            # What the corpus documents per speaker (gender as it records it,
            # recorded minutes), keyed by the speaker's name; {} without the
            # corpus's metainfo beside the model.
            "speaker_info": self.speaker_info,
            "length_scale": self.length_scale,
            "noise_w": self.noise_w,
        }


class PiperBackend:
    """Speaks by running the `piper` binary of its own environment.

    Holds no model in this process — see the module docstring for why. What it
    does hold is the description of every installed voice, read once from the
    sidecar JSONs, so that `/api/speech/status` can answer without a synthesis.
    """

    def __init__(self):
        from config import (
            PIPER_BIN, PIPER_DEFAULT_VOICE, PIPER_LOUDNESS_LUFS, PIPER_MODEL_DIR,
        )

        self.binary = Path(PIPER_BIN).expanduser()
        self.model_dir = Path(PIPER_MODEL_DIR).expanduser()
        self.loudness_lufs = float(PIPER_LOUDNESS_LUFS)
        self.default_voice = PIPER_DEFAULT_VOICE
        self._voices: Optional[Dict[str, PiperVoiceModel]] = None

    # ----------------------------------------------------------------- voices

    def voices(self) -> Dict[str, PiperVoiceModel]:
        """Every installed voice, keyed by file stem. Scanned once."""
        if self._voices is not None:
            return self._voices

        found: Dict[str, PiperVoiceModel] = {}
        if self.model_dir.is_dir():
            for onnx in sorted(self.model_dir.glob("*.onnx")):
                sidecar = onnx.with_suffix(onnx.suffix + ".json")
                if not sidecar.is_file():
                    logger.warning(f"[PIPER] {onnx.name} has no sidecar JSON — skipped")
                    continue
                try:
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning(f"[PIPER] {sidecar.name} unreadable: {e}")
                    continue
                voice = PiperVoiceModel(onnx, meta)
                if voice.dataset in EXCLUDED_DATASETS:
                    logger.info(f"[PIPER] {onnx.name} skipped: dataset excluded")
                    continue
                found[voice.key] = voice
        else:
            logger.warning(f"[PIPER] Model directory not found: {self.model_dir}")

        self._voices = found
        logger.info(f"[PIPER] {len(found)} voice(s): {sorted(found)}")
        return found

    def languages(self) -> List[str]:
        """The languages this installation can actually speak, sorted."""
        return sorted({v.language for v in self.voices().values() if v.language})

    def resolve_language(self, language: Optional[str]) -> str:
        """The language code a voice exists for here, or refuse.

        A separate step, so that "nothing installed for Turkish" can never
        arrive disguised as "the synthesiser is broken".
        """
        code = (language or "").strip().lower()
        if code in self.languages():
            return code
        raise UnvoicedLanguageError(code)

    def resolve_voice(self, voice: Optional[str], language: str) -> PiperVoiceModel:
        """The model that will speak: a named voice, whatever its language;
        otherwise the configured default where its language matches, and
        failing that the first installed file of that language in name order
        (what `default_voices()` reports)."""
        installed = self.voices()

        name = (voice or "").strip()
        if name:
            if name not in installed:
                raise ValueError(
                    f"Unknown Piper voice '{name}'. "
                    f"Installed: {', '.join(sorted(installed))}")
            # A named voice of another language than the text's is spoken,
            # not refused, so that foreign voices can be explored. The file phonemises with its own
            # language's rules, so an English voice on a German sentence is
            # German read by English pronunciation rules. The response names
            # the file that spoke.
            if installed[name].language != language:
                logger.info(
                    f"[PIPER] {name} ({installed[name].language}) reads a "
                    f"'{language}' text: foreign voice by request")
            return installed[name]

        if self.default_voice in installed and \
                installed[self.default_voice].language == language:
            return installed[self.default_voice]

        for key in sorted(installed):
            if installed[key].language == language:
                return installed[key]
        raise UnvoicedLanguageError(language)

    def default_voices(self) -> Dict[str, str]:
        """Which file speaks per installed language when a caller names none:
        the rule of `resolve_voice`, written out so that the choice is never
        silent."""
        return {code: self.resolve_voice(None, code).key for code in self.languages()}

    async def is_available(self) -> bool:
        """True when this could actually speak, not when it is configured."""
        if not self.binary.is_file():
            logger.error(f"[PIPER] Binary not found: {self.binary}")
            return False
        if not self.voices():
            logger.error(f"[PIPER] No voices installed in {self.model_dir}")
            return False
        return True

    # -------------------------------------------------------------- synthesis

    async def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        voice: Optional[str] = None,
        emotion: Optional[str] = None,
        length_scale: Optional[float] = None,
        noise_w: Optional[float] = None,
        **kwargs,
    ) -> Tuple[bytes, str, float]:
        """Speak `text` verbatim.

        Returns (WAV bytes, what spoke it, measured f0 in Hz). The f0 is read
        off the audio being handed back, by the same procedure the other three
        synthesisers are measured with — the number is a measurement, never
        anything that was asked for.

        `emotion` is the historical name of the speaker parameter: one of the
        model's named speakers. No installed voice names a feeling — fourteen
        have a single speaker and ignore it, and the German corpus voice names
        its 236 speakers by number.
        """
        from my_app.services.speech_audio import read_wav, to_wav
        from my_app.services.voice_register import median_f0

        if not self.binary.is_file():
            raise RuntimeError(
                f"Piper is not installed at {self.binary}. "
                f"Run download_piper.sh, or set PIPER_BIN.")

        # A named voice speaks any language. Only the default is looked up
        # by the text's language, which then has to have an installed voice.
        code = (language or "").strip().lower()
        if not (voice or "").strip():
            code = self.resolve_language(language)
        model = self.resolve_voice(voice, code)
        speaker = model.resolve_speaker(emotion)

        # The Hebrew file phonemises Hebrew letters only (module docstring),
        # and drops everything else. A text whose letters are mostly not
        # Hebrew would come back as the few Hebrew ones between voiced
        # spaces, which is audio with almost none of the sentence in it. The
        # refusal names what it counted. Said, not drawn.
        if model.phoneme_type == "hebrew":
            hebrew = len(HEBREW_LETTER.findall(text))
            letters = len(ANY_LETTER.findall(text))
            if hebrew * 2 < letters or hebrew == 0:
                raise ValueError(
                    f"Piper voice '{model.key}' phonemises Hebrew letters only "
                    f"(phoneme_type 'hebrew') and drops the rest; of {letters} "
                    f"letters in this text {hebrew} are Hebrew.")

        command = [
            str(self.binary),
            "-m", str(model.path),
            # Piper normalises every sentence to its own peak by default, which
            # makes the loudness jump between them. Off here; the loudness is
            # set once over the whole utterance below, as for every other
            # synthesiser (speech_audio.to_wav).
            "--no-normalize",
        ]
        if speaker is not None:
            command += ["-s", str(speaker[1])]
        if length_scale is not None:
            command += ["--length-scale", str(float(length_scale))]
        if noise_w is not None:
            command += ["--noise-w-scale", str(float(noise_w))]

        with tempfile.TemporaryDirectory(prefix="piper-") as workdir:
            out = Path(workdir) / "speech.wav"
            command += ["-f", str(out)]

            def _run():
                # No timeout: this is a model call, and a cap here would cut an
                # utterance off mid-sentence rather than let it finish.
                return subprocess.run(
                    command, input=text.encode("utf-8"),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            logger.info(
                f"[PIPER] {len(text)} chars | {model.key} | "
                f"{speaker[0] if speaker else 'single speaker'} | {code}")
            process = await asyncio.to_thread(_run)

            if process.returncode != 0:
                detail = (process.stderr or b"").decode("utf-8", "ignore").strip()
                logger.error(f"[PIPER] Failed ({process.returncode}): {detail[-400:]}")
                # The cause travels to the column: the binary's own last
                # lines, never a house sentence.
                raise RuntimeError(
                    f"Piper exited with status {process.returncode}: "
                    f"{detail[-400:] or 'no message on stderr'}")
            if not out.is_file():
                raise RuntimeError("Piper wrote no audio")
            raw = out.read_bytes()

        samples, sample_rate = read_wav(raw)
        wav = to_wav(samples, sample_rate, self.loudness_lufs)
        f0_hz = median_f0(samples, sample_rate)

        # What spoke, written the way it will be shown. The model file and the
        # speaker, both read back from the model — never the speaker alone,
        # which would read as a state somebody was in rather than a speaker id
        # in a file. A multi-speaker voice always names one, including when the
        # caller named none: something spoke, and which it was is not optional.
        spoke = f"{model.key} / {speaker[0]}" if speaker else model.key

        logger.info(f"[PIPER] {len(wav)} bytes ({spoke}, {f0_hz:.0f} Hz)")
        return wav, spoke, f0_hz


_backend: Optional[PiperBackend] = None


def get_piper_backend() -> PiperBackend:
    global _backend
    if _backend is None:
        _backend = PiperBackend()
    return _backend
