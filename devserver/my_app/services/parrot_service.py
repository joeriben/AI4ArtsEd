"""
Silly Parrot — the re-enactment chain.

A recording made on a microphone is handed to three machines in turn, and
what the last one produces is played back against what the middle one wrote
down. The subject of the page is the distance between those two.

    recording  ->  ranked against a list we chose      (MuQ-MuLan)
               ->  turned into words                    (HeartTranscriptor)
               ->  written up as tags and lyrics        (an LLM)
               ->  sung        (the sound config it resolved to)

Beside the transcription, and beside it only, the words it produced are offered a
second time in the language the platform is set to, because a
group that cannot read the alphabet the transcriber decided on can see THAT
something was misheard and never WHAT. It is an aid next to the words, never
in place of them, and nothing downstream receives it: the song is written from
the transcription, in the language the transcriber chose. See _read_in.

Two properties are load-bearing and must not be "fixed" later:

- No station is corrected or gated. If the recording contains no words, the
  transcription still returns a confident sentence and the chain still runs.
  That is the demonstration, not a failure — a group can point a microphone
  at an empty room and get a song about a line nobody said.
- The recording is not a work. It is written to a temp directory, read by
  the stations, and deleted. It is never registered as a run, never enters
  the media store, never appears in favourites or exports.

There is deliberately no Stage 2 interception here. Elsewhere on the
platform the LLM performs a pedagogical transformation; here it is the
station that invents, and it has to be seen doing exactly that. The reading
aid uses the same model, and for the same reason must not transform: it
renders, it does not interpret, and the page names the machine that wrote it
exactly as it names every other one.
"""

import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# The song is as long as the recording.
#
# max_audio_length_ms reads like a ceiling and is not one. heartlib computes
# max_audio_frames = max_audio_length_ms // 80 and generates that many frames;
# the early-EOS break exists but did not fire on the run this was measured on —
# an 11.9 s recording with a 60000 ms budget produced 60.080 s of mp3, which is
# 751 frames of 80 ms exactly. So the number IS the song's length, and the
# recording's length can simply be handed to it.
#
# The frame exists because the number is taken that literally: two seconds of
# coughing would otherwise be two seconds of music. 240 s was the ceiling
# HeartMuLa's own output config carried. That config now carries 60 s, for
# a song from a prompt; this page passes its own length over it in _sing,
# and its frame stays at 240 s.
SONG_MIN_MS = 10_000
SONG_MAX_MS = 240_000

# Recordings are capped at 240 s. The recording stops where the song does,
# DERIVED from it rather than written out again, so that two independent
# constants cannot drift into meaning different things.
MAX_RECORDING_SECONDS = SONG_MAX_MS // 1000


def _song_length_ms(seconds: float) -> int:
    """The recording's length, held inside the range HeartMuLa is run at."""
    return max(SONG_MIN_MS, min(SONG_MAX_MS, int(round(seconds * 1000))))


def _recording_seconds(path: str) -> float:
    """How long the recording is, read from the file rather than from a timer.

    0.0 when the header cannot be read, and also when the file is a readable wav
    with no frames in it. The caller cannot tell those two apart and does not
    have to: both land on SONG_MIN_MS, and neither can reach the music station
    anyway, because the ranking station refuses audio with nothing in it.
    """
    try:
        import soundfile as sf
        return float(sf.info(path).duration)
    except Exception as e:
        logger.warning(f"[PARROT] Could not read the recording's length: {e}")
        return 0.0

# The music station is not wired to a client. It runs one of the platform's
# output configs, which names the chunk and carries the parameters — so a change
# there reaches this page too. See _sing().
#
# WHICH one is decided by what was HEARD — the ranking of station 1 and the
# words of station 2 — by this routing table: two yes/no answers, four
# outcomes, and a hand-pick that beats all four:
#
#     music + text  → HeartMuLa      a song: words to sing and a style to sing them in
#     music, no text → SA3 Music     music, but nothing to sing
#     text, no music → VoxCPM2       a voice: the words spoken back
#     neither        → SA3 SFX       a sound
#
# The list is this page's, not the flow's: the flow offers Stable Audio 3 and
# HeartMuLa here
# and has no speech at all, and a chain that ends in a spoken voice is a reading
# of the recording this page can show and the flow cannot.
SOUND_CONFIGS = (
    ("heartmula_standard", "HeartMuLa"),
    ("stableaudio_music", "SA3 Music"),
    ("stableaudio_sfx", "SA3 SFX"),
    ("voxcpm_standard", "VoxCPM2"),
)
SONG_CONFIG = "heartmula_standard"
MUSIC_CONFIG = "stableaudio_music"
SFX_CONFIG = "stableaudio_sfx"
SPEECH_CONFIG = "voxcpm_standard"
SA3_CONFIGS = (MUSIC_CONFIG, SFX_CONFIG)
SINGER_NAMES = dict(SOUND_CONFIGS)

# Recordings live outside the working tree and outside the export store, so
# that nothing here can become committable or end up in a gallery.
_STAGING_ROOT = os.path.join(tempfile.gettempdir(), "ai4artsed_parrot")
_STAGING_TTL_SECONDS = 3600


def staging_root() -> str:
    os.makedirs(_STAGING_ROOT, exist_ok=True)
    return _STAGING_ROOT


def sweep_staging() -> None:
    """Drop anything older than the TTL. Cheap, runs on every upload."""
    root = staging_root()
    cutoff = time.time() - _STAGING_TTL_SECONDS
    for name in os.listdir(root):
        path = os.path.join(root, name)
        try:
            if os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
        except OSError:
            pass


def new_recording_dir() -> tuple:
    """Returns (recording_id, directory)."""
    sweep_staging()
    recording_id = uuid.uuid4().hex
    directory = os.path.join(staging_root(), recording_id)
    os.makedirs(directory, exist_ok=True)
    return recording_id, directory


def recording_dir(recording_id: str) -> Optional[str]:
    """Resolve an id to its directory, refusing anything that is not a plain id."""
    if not re.fullmatch(r"[0-9a-f]{32}", recording_id or ""):
        return None
    directory = os.path.join(staging_root(), recording_id)
    return directory if os.path.isdir(directory) else None


def discard(recording_id: str) -> None:
    directory = recording_dir(recording_id)
    if directory:
        shutil.rmtree(directory, ignore_errors=True)


# ---------------------------------------------------------------------------
# The station that invents
# ---------------------------------------------------------------------------

# The two machines at the sorting station, as (alias, name shown on the page).
#
# The first is the one that answers: chosen from a published comparison against
# human listeners rather than from what was installed, and checked here.
#
# The second is the one that used to answer alone. It stays because its way of
# failing is the thing this page is about: handed synthetic laughing and crying
# it produced "throat singing" and "gamelan", and that label then travelled
# through the written song into a music model that does not know the tradition
# and sang pop over it. A page that demonstrates machine confabulation must not
# quietly delete the confabulation it had.
RANKER_PRIMARY = ("clap-music-speech", "CLAP-Music&Speech")
RANKER_SECOND = ("muq-mulan", "MuQ-MuLan")

# The other two, named the same way. Until 2026-08-09 the transcriber and the
# singer were the only machines on this page that stayed anonymous, which was
# survivable while the page only showed what they PRODUCED and became wrong when
# the middle box started reporting the run itself.
#
# The transcriber is the alias `hearttranscriptor` — HeartMuLa/
# HeartTranscriptor-oss, a Whisper fine-tune, see media_analysis_backend's
# module note. The singer is whichever sound config station 5 resolved to, so
# its name is not a constant here: it rides on that station's own events, and
# the running event already carries it because the resolution happens before
# the station starts. See SOUND_CONFIGS and resolve_singer().
TRANSCRIBER_NAME = "HeartTranscriptor"


# The platform's own languages, keyed by locale, valued by the English name the
# transcriber answers with (media_analysis_backend._detect_language returns a
# name, not a code).
READING_LANGUAGES = {
    "en": "English", "de": "German", "es": "Spanish", "fr": "French",
    "tr": "Turkish", "ko": "Korean", "uk": "Ukrainian", "ar": "Arabic",
    "he": "Hebrew", "bg": "Bulgarian",
}

# The transcriber answers with a lowercase English NAME. A caller who forced
# `language` on it gets the CODE back instead (media_analysis_backend:
# `detected = language or self._detect_language(...)`). Both reduce to a locale.
_DETECTED_LOCALES = {name.lower(): code for code, name in READING_LANGUAGES.items()}

READING_PROMPT = """Translate the following into {target}.

It comes from a speech recogniser and may be nonsense, may be fragments, may be
words nobody said. Translate what is there, literally. Do not correct it, do not
complete it, do not comment on it, do not explain it. Carry over unchanged
anything that cannot be translated.

Answer with the translation and nothing else.

TEXT:
{text}"""


WRITER_PROMPT = """You are writing the input for a music generation model, from machine readings of a recording.

None of the readings is reliable, and you must not treat them as if they were:
- The labels are a ranking inside a fixed list somebody chose in advance. The recording's actual instrument may not be in the list at all.
- Two different machines ranked that same list, and they disagree. Neither of them is the correct one.
- The transcription may contain words that were never sung. On a recording with no words in it, that transcriber still produces fluent sentences.

Work from them anyway. Do not hedge, do not comment on the quality of the input, do not explain yourself. Write the song.

RANKED LABELS from the first machine ({model_first}), best match first, inside a fixed list:
{labels}

RANKED LABELS from the second machine ({model_second}), same recording, same list:
{labels_second}

TRANSCRIPTION:
{transcription}

Write the lyrics in the language the transcription came back in, including when that is plainly not the language anyone was speaking. Do not translate it. Keep the words it gives you where you can; invent only where you must. The style words stay English.

The song will be {seconds} seconds long. That is a budget the music model spends frame by frame, and it stops when the budget is gone, mid-word if it has to. Write only what can be sung in that time, and never more than 24 lines.

Answer with a single JSON object and nothing else:
{{"tags": "<comma-separated style words for the music model>",
  "lyrics": "<lyrics using [Verse] / [Chorus] section markers, sized to the length above>"}}"""


def _writer_model() -> str:
    """Same precedence the rest of the platform uses for a strong text model."""
    import config
    for name in ("STAGE2_INTERCEPTION_MODEL", "STAGE1_TEXT_MODEL",
                 "STAGE3_MODEL", "CHAT_HELPER_MODEL"):
        value = (getattr(config, name, "") or "").strip()
        if value:
            return value
    return ""


def _parse_writer_output(raw: str) -> Optional[Dict[str, str]]:
    """Pull the JSON object out of whatever the model wrapped it in."""
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    tags = str(data.get("tags", "")).strip()
    lyrics = str(data.get("lyrics", "")).strip()
    if not lyrics:
        return None
    # A writer that answers with the same string twice looks, to the music
    # chunk, exactly like a caller that duplicated one prompt into both of its
    # fields — it would move the lyrics into the tag slot and sing an
    # instrumental, and the words the group is reading would not be the words
    # in the song. Read an equal pair as "no tags" and let the fallback below
    # do the rest.
    if tags == lyrics:
        tags = ""
    # `styled` is the constellation the flow looks for: words to be sung AND a
    # description of how they should sound. A non-empty tag field is not that —
    # the writer prompt demands one, so reading it as the assertion would make
    # the assertion unconditional and the default below unreachable. The test is
    # the flow's, thresholds included; see _asserts_song.
    return {
        "tags": tags or "song",
        "lyrics": lyrics,
        "styled": _asserts_song(lyrics, tags),
    }


# The flow's reading of a lyrics-plus-style pair, ported from
# composables/useTextRoles.ts — same markers, same word list, same thresholds.
# It lives twice because the two sides decide at different moments: the board
# scores two undeclared texts before a run, this scores the writer's two
# declared fields during one. Change both or they disagree about the same song.
_SECTION_RE = re.compile(
    r"\[(verse|chorus|bridge|intro|outro|hook|refrain|strophe|pre-chorus)\b[^\]]*\]",
    re.IGNORECASE)

_STYLE_WORDS = {
    # genre
    "pop", "rock", "jazz", "classical", "electronic", "hip-hop", "hiphop", "rap", "r&b",
    "soul", "funk", "blues", "country", "folk", "metal", "punk", "indie", "reggae",
    "latin", "salsa", "tango", "samba", "bossa nova", "flamenco", "gospel", "afrobeat",
    "highlife", "cumbia", "fado", "qawwali", "k-pop", "bollywood", "house", "techno",
    "trance", "dubstep", "drum and bass", "synthwave", "lo-fi", "lofi", "trap", "ambient",
    "dance", "chanson", "schlager", "volksmusik", "orchestral", "cinematic", "chiptune",
    # mood
    "dark", "happy", "sad", "melancholic", "melancholy", "dreamy", "aggressive", "calm",
    "energetic", "uplifting", "haunting", "nostalgic", "epic", "playful", "somber", "warm",
    "traurig", "fröhlich", "düster", "ruhig", "melancholisch", "verträumt",
    # instrument
    "piano", "guitar", "acoustic guitar", "electric guitar", "violin", "cello", "strings",
    "drums", "bass", "synth", "synthesizer", "saxophone", "trumpet", "flute", "harp",
    "organ", "choir", "vocals", "female vocals", "male vocals", "a cappella", "accordion",
    "sitar", "klavier", "gitarre", "geige", "schlagzeug", "streicher", "chor",
    # tempo / production
    "slow", "fast", "mid-tempo", "midtempo", "upbeat", "downtempo", "bpm", "instrumental",
    "minimal", "reverb", "distorted", "acoustic", "live", "langsam", "schnell",
}


def _non_empty_lines(text: str) -> int:
    return len([line for line in text.split("\n") if line.strip()])


def _lyrics_score(text: str) -> int:
    score = 4 if _SECTION_RE.search(text) else 0
    lines = _non_empty_lines(text)
    if lines >= 3:
        score += 1
    if lines >= 6:
        score += 1
    if len(text) > 120:
        score += 1
    return score


def _style_score(text: str) -> int:
    parts = [p.strip().lower() for p in text.split(",")]
    parts = [p for p in parts if p]
    score = 0
    if len(parts) >= 2:
        score += 2
    if len(text) <= 140:
        score += 1
    if not re.search(r"[.!?]", text):
        score += 1
    hits = len([p for p in parts if p in _STYLE_WORDS])
    if hits >= 1:
        score += 2
    if hits >= 2:
        score += 1
    if _SECTION_RE.search(text):
        score -= 4
    if _non_empty_lines(text) > 2:
        score -= 2
    return score


# What the ranking heard, as the two yes/no answers the table above turns on.
#
# Both are comparisons INSIDE the ranking and never against a fixed number.
# Neither ranker has an abstain: both embed an arbitrary English string and score
# cosine similarity against the recording, so every label gets a number and the
# best one always wins something. MUSIC_TAG_VOCABULARY says this of MuQ-MuLan in
# gpu_service/services/media_analysis_backend.py; for CLAP it is what the probes
# show — it scored "silence" .25 on a loud pop song. An absolute score therefore
# says nothing; only "this label beat that one" does.
#
# The music side is named by exclusion, so a label added to the vocabulary
# counts as music unless it is listed here — which is what the vocabulary is
# mostly made of. Mood and recording-quality labels are on neither side: "sad
# and slow" and "a rough recording made in a room" are true of speech and of a
# slammed door as well.
_SPEAKING_LABEL = "a voice speaking, not singing"
_SINGING_LABELS = ("a single voice singing alone",
                   "several voices singing together")
_VOICE_LABELS = (_SPEAKING_LABEL,) + _SINGING_LABELS
_NO_VOICE_LABEL = "no voice at all"
_NOT_MUSIC_LABELS = ("noise, not music", "silence")
_NEITHER_SIDE = {
    "humming without words",          # a voice, but no words — and not music
    "a clean studio recording",
    "a rough recording made in a room",
    "happy and upbeat", "sad and slow", "calm and quiet", "loud and aggressive",
}
# The music side is named by exclusion, so a label added to the vocabulary counts
# as music unless it is listed here — which is what the vocabulary is mostly made
# of. SINGING IS MUSIC and therefore stays out of this set: a recording of a
# choir has no instrument in it, so if the singing labels counted against music,
# every unaccompanied voice would be read as speech and spoken back by a TTS. On
# a page whose own instruction is „Sing, summ oder halte dein Handy hoch" that
# would take the commonest case off the board.
_NOT_MUSIC_SIDE = ({_SPEAKING_LABEL, _NO_VOICE_LABEL}
                   | set(_NOT_MUSIC_LABELS) | _NEITHER_SIDE)


def _what_was_heard(ranking: Optional[List[Dict[str, Any]]],
                    transcription: str) -> Optional[tuple]:
    """(music?, text?) — the two answers the routing table turns on, or None
    when this ranking cannot answer at all.

    WHICH ranking is handed in: the second one, MuQ-MuLan. It is the
    music-tagging model of the two, and on the probes it was the only one whose
    top answer was right every time. CLAP is what the page SHOWS first, and that
    stays — the page is about what these machines make of a recording, and the
    one that is wrong in public is not the one that should route. CLAP is not a
    fallback here: measured on clean German speech it scored „a voice speaking,
    not singing" at −0.118 while putting „jazz" at .277, so routing on it does
    not degrade the answer, it inverts it. When MuQ says nothing this returns
    None and the caller falls back to a declared default instead of guessing.

    The numbers, the probe files and the full rankings are in
    `devserver/testfiles/probe_parrot_routing.py`, which reruns them, and in
    „ARCHITECTURE PART 38 - Cover-Band.md".

    Three comparisons, in this order:

    1. Top-1 is „noise, not music" or „silence" → no music. On the noise probe
       that is the only thing that catches it: MuQ still had a music label at
       ~.46 there. It settles the MUSIC question only — a recording made in a
       room can be ranked „silence" at the top and still have words in it.
    2. Otherwise, if „a voice speaking, not singing" beats the best music label,
       this is a speaking voice → no music. Only the SPEAKING label may do this.
       The singing labels are on the music side, see _NOT_MUSIC_SIDE.
    3. Otherwise music is present when the best music label beats the best of
       „noise, not music" / „silence".

    Text needs the transcriber AND the ranking, and WHICH voice label the
    ranking is asked for depends on the answer above, because the question is
    not the same one:

    * in music, „are there words" means „is somebody singing" — asked of the two
      singing labels. Asking the speaking label there is what let an instrumental
      pass as a song: its score sits in this model's cross-category leakage, and
      it does not have to be high, only higher than „no voice at all".
    * without music it means „is somebody talking" — asked of the speaking label.

    The transcriber alone will not do, and that is the whole subject of this
    page: handed brown noise it wrote „uh...", handed synthetic chords
    „××××，x，x，x，". Requiring the ranking to agree is the one place where the
    confabulation is caught rather than shown.

    Every comparison is between labels that stand for opposed answers. Across
    unrelated labels these numbers do not compare: on the sung probe CLAP gave
    „silence" .25 while every voice label sat near .11.

    The narrowest of them is the voice-against-„no voice at all" one: MuQ scored
    „no voice at all" .499 on a recording that is nothing but a voice, .073 below
    its own top label. It is recorded as such in issue #37.
    """
    scores = {e["label"]: e["score"] for e in (ranking or [])
              if isinstance(e, dict) and "label" in e and "score" in e}
    if not scores:
        return None

    def best(labels):
        found = [scores[label] for label in labels if label in scores]
        return max(found) if found else None

    speaking = scores.get(_SPEAKING_LABEL)
    singing = best(_SINGING_LABELS)
    no_voice = best((_NO_VOICE_LABEL,))
    music = best([label for label in scores if label not in _NOT_MUSIC_SIDE])
    not_music = best(_NOT_MUSIC_LABELS)

    def over_none(voice):
        return voice is not None and (no_voice is None or voice > no_voice)

    if max(scores, key=lambda label: scores[label]) in _NOT_MUSIC_LABELS:
        has_music = False
    elif speaking is not None and music is not None and speaking > music:
        has_music = False
    else:
        has_music = music is not None and (not_music is None or music > not_music)

    wrote = bool((transcription or "").strip())
    if has_music:
        return True, wrote and over_none(singing)
    return False, wrote and over_none(speaking)


def _asserts_song(lyrics: str, tags: str) -> bool:
    """The flow's two bars: words that behave like a song, tags that behave like
    a description of one. Anything less is not the pair, and station 5 falls back
    to the sound medium's default the way the flow's board does."""
    if not lyrics or not tags:
        return False
    return _lyrics_score(lyrics) >= 3 and _style_score(tags) >= 5


def resolve_singer(ranking: Optional[List[Dict[str, Any]]],
                   transcription: str,
                   picked: Optional[str] = None) -> str:
    """Which output config station 5 runs (the routing table in the module header).

    A hand-pick holds and beats everything, and an unknown one is not an error:
    it is simply not a pick (x2x_flow.vue, manualModel). Otherwise the decision
    is made from what was HEARD — the ranking of station 1 and the words of
    station 2 — and not from what the writing station wrote. Scoring the writer
    decided nothing about WHICH MACHINE: it is asked for a song every time and
    produces one every time. (Its `styled` flag still picks which of its two
    texts prompts Stable Audio, further down in _sing. That is a different
    question and it stays.)

    When the ranking cannot answer, this returns the song config: that is what
    ran here for months before the table existed, and it is a declared default
    rather than a guess made from the other machine.
    """
    if picked in SINGER_NAMES:
        return picked
    heard = _what_was_heard(ranking, transcription)
    if heard is None:
        logger.warning("[PARROT] no usable ranking for the routing; "
                       f"falling back to {SONG_CONFIG}")
        return SONG_CONFIG
    has_music, has_text = heard
    if has_music:
        return SONG_CONFIG if has_text else MUSIC_CONFIG
    return SPEECH_CONFIG if has_text else SFX_CONFIG


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------

def run_chain(recording_path: str, language: Optional[str] = None,
              reading: Optional[str] = None,
              singer: Optional[str] = None) -> Iterator[Dict[str, Any]]:
    """Yield one event per station, in order. Never raises; failures are events."""
    from my_app.services.media_analysis_client import get_media_analysis_client

    analysis = get_media_analysis_client()
    # One number: what the music model is given, and what the writing station is told the
    # song will be. They can never drift apart.
    song_ms = _song_length_ms(_recording_seconds(recording_path))

    # --- ranked against a list we chose ------------------------------------
    # The name rides on the RUNNING event too, not only on the answer. The
    # middle box says which machine is working; until 2026-08-09 it could only
    # name the ones that had already stopped, so the longest station of the four
    # spent its whole run anonymous.
    yield {"station": "ranked", "status": "running",
           "model": f"{RANKER_PRIMARY[1]} \u00b7 {RANKER_SECOND[1]}"}
    started = time.time()
    tags = analysis.tag(recording_path, model=RANKER_PRIMARY[0])
    if tags is None:
        from my_app.services.media_analysis_client import last_reason
        yield {"station": "ranked", "status": "failed",
               "error": last_reason() or "the ranking station did not answer"}
        return
    # The second machine is not a station of its own: if it stays silent the
    # chain carries on with one reading instead of two. Where its call failed,
    # the page says which machine it was and why.
    second = analysis.tag(recording_path, model=RANKER_SECOND[0])
    second_failed = None
    if second is None:
        from my_app.services.media_analysis_client import last_reason
        second_failed = {"model": RANKER_SECOND[1],
                         "error": last_reason() or "the ranking station did not answer"}
    yield {
        "station": "ranked", "status": "done",
        "ranking": tags,
        "model": RANKER_PRIMARY[1],
        "second": ({"model": RANKER_SECOND[1], "ranking": second} if second else None),
        "second_failed": second_failed,
        "ms": int((time.time() - started) * 1000),
    }

    # --- turned into words --------------------------------------------------
    yield {"station": "words", "status": "running", "model": TRANSCRIBER_NAME}
    started = time.time()
    heard = analysis.transcribe(recording_path, language=language)
    if heard is None:
        from my_app.services.media_analysis_client import last_reason
        yield {"station": "words", "status": "failed",
               "error": last_reason() or "the transcription station did not answer"}
        return
    transcription = heard["text"]
    detected = heard["language"]
    yield {
        "station": "words", "status": "done",
        "text": transcription,
        # Nothing on the page asks for a language, so this is the model's own
        # decision and belongs next to the words it produced from it.
        "language": detected,
        "model": TRANSCRIBER_NAME,
        # An empty answer and an invented answer look the same from here. The
        # page has to say so; the backend must not pretend to know which.
        "empty": transcription.strip() == "",
        "ms": int((time.time() - started) * 1000),
    }

    # --- the same words, readable -------------------------------------------
    # After the event above and never before it. The model call below has no read
    # timeout, correctly so (config.LLM_TIMEOUT = (10, None)); a provider that
    # accepts the connection and never answers would otherwise hold back the one
    # output this page exists to show — and with it stations 4 and 5, the route's
    # `finally`, and the deletion of the recording.
    #
    # `reading` is the language selected for the platform. It is deliberately NOT
    # the `language` parameter above: that one is handed to the transcriber and
    # forces its decision, which would delete the subject of this page. This one
    # never reaches the transcriber.
    target = _reading_target(detected, reading)
    if target and transcription.strip():
        readable = _read_in(transcription, target)
        if readable:
            # Its own station name: it is not a second reading of the recording,
            # it is the same words again. Nothing downstream sees it — the song
            # is written from the transcription, in the language it came back in.
            # The model is named because every other station on this page names
            # its own, and this one is a different vendor from all of them.
            yield {"station": "reading", "status": "done",
                   "text": readable, "model": _writer_model()}

    # --- written up ---------------------------------------------------------
    yield {"station": "written", "status": "running", "model": _writer_model()}
    started = time.time()
    written = _write_song(tags, second, transcription, song_ms // 1000)
    if written is None:
        yield {"station": "written", "status": "failed",
               "error": "the writing station did not answer"}
        return
    yield {
        "station": "written", "status": "done",
        "tags": written["tags"],
        "lyrics": written["lyrics"],
        "model": _writer_model(),
        "ms": int((time.time() - started) * 1000),
    }

    # --- sung ---------------------------------------------------------------
    # Resolved before the station starts, so the running event can name the
    # machine that is working — the same thing the sorting station does.
    config_id = resolve_singer(second, transcription, singer)
    singer_name = SINGER_NAMES[config_id]
    # The id, not only the name: the page lights the machine that runs, and
    # matching it back from a display label would break the day one is renamed.
    yield {"station": "sung", "status": "running",
           "model": singer_name, "config": config_id}
    started = time.time()
    # `.get(named, named)` and not a bare get: a caller who forced `language`
    # gets a CODE back from the transcriber, not a name, and dropping it here
    # would hand the speech chunk nothing and let it default to English.
    _heard = (detected or "").strip().lower()
    sung_result = _sing(written, song_ms, config_id,
                        lang=_DETECTED_LOCALES.get(_heard, _heard) or None)
    if sung_result is None:
        yield {"station": "sung", "status": "failed",
               "error": "the last machine did not answer"}
        return
    audio, fmt = sung_result
    # AI-Origin Disclosure (EU AI Act Art. 50). This file is written past every
    # recorder and served straight out of /api/parrot/sung — the marking has to
    # happen here or nowhere. (The recording it answers is a person singing and
    # is deliberately left alone.)
    try:
        from my_app.services.watermark_service import watermark_media_bytes
        audio = watermark_media_bytes(audio, "output_audio", {"model": singer_name})
    except Exception as e:
        logger.warning(f"[PARROT] watermark not applied ({e})")
    output_path = os.path.join(os.path.dirname(recording_path), "sung." + fmt)
    with open(output_path, "wb") as handle:
        handle.write(audio)
    yield {
        "station": "sung", "status": "done",
        "model": singer_name,
        "config": config_id,
        "bytes": len(audio),
        "ms": int((time.time() - started) * 1000),
    }


def _write_song(ranking: List[Dict[str, Any]],
                second: Optional[List[Dict[str, Any]]],
                transcription: str,
                seconds: int) -> Optional[Dict[str, str]]:
    """Run the writer prompt on whichever model the platform is configured for.

    Goes through PromptInterceptionEngine, which is the platform's model
    router — it is what dispatches a model string to the local GGUF backend
    or to one of the providers (mammouth/, openrouter/, anthropic/ ...), with
    the fallback chain behind it. `prebuilt_prompt` hands it the prompt as-is,
    so nothing pedagogical is layered on: this station is meant to confabulate
    plainly, and routing is the only thing being reused.
    """
    import asyncio
    from schemas.engine.prompt_interception_engine import (
        engine as model_router, PromptInterceptionRequest,
    )

    model = _writer_model()
    if not model:
        logger.error("[PARROT] No text model configured")
        return None

    # The writer sees the same head of each ranking the page shows, so that what
    # it worked from and what the group reads are the same thing.
    def head(entries: List[Dict[str, Any]], n: int) -> str:
        # `run_chain` verspricht "never raises", und diese Zeile konnte es
        # brechen: ein unvollstaendiger Ranking-Eintrag warf einen KeyError aus
        # der ganzen Kette. Erst die n oberen nehmen, dann die unvollstaendigen
        # weglassen -- nicht umgekehrt, sonst rueckt ein tieferer Eintrag in
        # die Spitzengruppe nach, den dort niemand gemessen hat.
        oben = entries[:n]
        ganz = [e for e in oben if e.get('label') is not None
                and isinstance(e.get('score'), (int, float))]
        return ", ".join(f"{e['label']} ({e['score']:+.2f})" for e in ganz)

    prompt = WRITER_PROMPT.format(
        model_first=RANKER_PRIMARY[1],
        labels=head(ranking, 8),
        model_second=RANKER_SECOND[1],
        labels_second=head(second, 5) if second else "(this machine did not answer)",
        transcription=transcription.strip() or "(the transcriber returned nothing)",
        seconds=seconds,
    )

    request = PromptInterceptionRequest(
        input_prompt="",
        prebuilt_prompt=prompt,
        model=model,
        parameters={
            "temperature": 0.8,
            # No max_tokens: the model stops at EOS, not at a number we picked.
        },
    )

    try:
        response = asyncio.run(model_router.process_request(request))
    except Exception as e:
        logger.error(f"[PARROT] Writing station failed: {e}")
        return None

    if not response or not response.success:
        logger.error(f"[PARROT] Writing station: {getattr(response, 'error', 'no response')}")
        return None
    return _parse_writer_output(response.output_str)


def _reading_target(detected: Optional[str], reading: Optional[str]) -> Optional[str]:
    """The language to render the transcription in, or nothing at all.

    Nothing when the page's language is not one of ours, when the transcriber
    named NO language, or when the two are the same language.

    The middle case is the one worth spelling out: a failed detection is a
    documented outcome, not an exotic one, and it says nothing about which
    language the words are in. Translating then would put a second paragraph
    under the first with no way to tell whether it differs — and the line that
    names the transcriber's decision is hidden in exactly that case, because
    there is no decision to name.
    """
    code = (reading or "").strip().lower()
    target = READING_LANGUAGES.get(code)
    if not target:
        return None
    named = (detected or "").strip().lower()
    if not named:
        return None
    return None if _DETECTED_LOCALES.get(named, named) == code else target


def _read_in(text: str, target: str) -> Optional[str]:
    """The transcription in the language the page is being read in.

    Not a correction and not a second opinion: what the
    transcriber decided stays on the page above this, and the song is
    still written in the language it decided on. This exists because a group
    whose page is German and whose recording came back as Finnish could see THAT
    something was misheard and never WHAT — and what it misheard is the subject.

    Never raises: a failed translation costs a paragraph, the station stands.
    """
    import asyncio
    from schemas.engine.prompt_interception_engine import (
        engine as model_router, PromptInterceptionRequest,
    )

    model = _writer_model()
    if not model:
        return None

    request = PromptInterceptionRequest(
        input_prompt="",
        prebuilt_prompt=READING_PROMPT.format(target=target, text=text.strip()),
        model=model,
        parameters={
            "temperature": 0.2,
            # No max_tokens: the model stops at EOS, not at a number we picked.
        },
    )

    try:
        response = asyncio.run(model_router.process_request(request))
    except Exception as e:
        logger.error(f"[PARROT] Reading translation failed: {e}")
        return None

    if not response or not response.success:
        logger.error(
            f"[PARROT] Reading translation: {getattr(response, 'error', 'no response')}"
        )
        return None
    return (response.output_str or "").strip() or None


def _sing(written: Dict[str, Any], song_ms: int, config_id: str,
          lang: Optional[str] = None) -> Optional[tuple]:
    """Sing the written song through the platform's own output path.

    This does not call HeartMuLaClient. It runs the output config the way every
    other page runs one: execute_pipeline resolves the config station 5 chose,
    lets
    ChunkBuilder assemble the chunk request, and hands the audio back in the
    result metadata. Calling the client directly, as this did until 2026-08-05,
    was a second road to the same model, and it quietly skipped everything the
    chunk does — tag normalisation, the HEARTMULA_ENABLED gate, is_available(),
    the lyrics and tag length caps, seed handling. It also meant a change to
    heartmula_standard.json reached every page except this one.

    Both properties of the page survive the detour, and neither survives by
    accident:

    Nothing is kept. The executor generates and returns; it holds no recorder,
    no media store, no favourites. On every other page the persistence sits in
    the route handler wrapped around execute_pipeline, and this page has no such
    handler — run_chain writes the bytes into the staging directory and the
    sweeper takes them away again.

    No station is gated, and that holds for all three configs rather than for
    heartmula_standard's pipeline flag. skip_stage2 is read in
    schema_pipeline_routes — the orchestrator this path deliberately does not go
    through — and the engine below it runs the chunks a config names. All three
    name a single output chunk and set requires_interception_prompt false, so no
    safety check, no interception and no translation sits between the written
    words and the sung ones. Nothing here refuses a song or judges what was
    said.

    The chunk does reshape what it is handed, and that is worth naming rather
    than glossing: it strips the space after each comma (the one thing the
    model's README asks for), caps the lyrics at 2000 characters and the tags at
    200, and picks a random seed. Until 2026-08-12 it also glued multi-word tags
    with underscores, which the model's README never asks for and which changed
    what its tokenizer reads; see the chunk's own note for what was measured and
    what was not.
    None of that stops the chain. One of its branches would have done worse
    than reshape — handed a tag string equal to the lyrics, it reads that as a
    caller who duplicated one prompt into both fields, moves the lyrics into
    the tag slot and sings an instrumental. _parse_writer_output closes that
    off upstream; see the comment there.
    """
    import asyncio
    import base64

    # The engine's own singleton, not the one in the route module: a service
    # has no business importing routes, and this one initialises itself on
    # first use.
    from schemas.engine.pipeline_executor import PipelineContext, executor

    # TEXT_1/TEXT_2 is the pipeline's convention for a dual-text chunk. Custom
    # placeholders beat the config, which is how the one value this page insists
    # on gets in: the length of the recording it heard, rather than the config's
    # 60 s for a song from a prompt. It is worth knowing that this override
    # survives only because
    # ChunkBuilder merges custom placeholders over the config's parameters — the
    # executor's own injection loop would have skipped it, since
    # max_audio_length_ms is not one of its GENERATION_OVERRIDE_PARAMS.
    lyrics = written["lyrics"]
    tags = written["tags"]

    if config_id == SONG_CONFIG:
        context = PipelineContext(input_text=lyrics, user_input=tags)
        context.custom_placeholders = {
            "TEXT_1": lyrics,
            "TEXT_2": tags,
            "max_audio_length_ms": song_ms,
        }
        first, second = lyrics, tags
    elif config_id == SPEECH_CONFIG:
        # VoxCPM2 speaks its input verbatim — the config says so itself, and
        # that is the whole reason it can stand here: the words the page is
        # showing are the words that come back, with nothing added and nothing
        # rewritten. It has no length parameter; the text is the length.
        #
        # It stands where Qwen3-TTS stood until 2026-08-12, for the same
        # property and in the same place.
        context = PipelineContext(input_text=lyrics, user_input=lyrics)
        # TEXT_1 by name: the chunk reads it as the utterance (its own docstring),
        # and a config that resolves the text from somewhere else would otherwise
        # speak whatever that somewhere else held.
        #
        # text_en is the chunk's own escape for the five languages the model has
        # no voice for (tr, uk, he, ar, bg) — all five are platform languages, so
        # without it a recording heard as any of them dead-ends here. The
        # platform decided on 2026-08-06 that the fallback is English and never a
        # foreign voice; the chunk uses this only when it has no voice, so it
        # costs one call and changes nothing in the other cases.
        placeholders = {"TEXT_1": lyrics}
        english = _read_in(lyrics, "English") if lang not in (None, "en") else None
        if english:
            placeholders["text_en"] = english
        context.custom_placeholders = placeholders
        first = second = lyrics
    else:
        # Both Stable Audio targets, SA3 Music and SA3 SFX, are the same call:
        # the model takes one text and a length and draws no line between music
        # and a sound effect. The line is drawn one station earlier, by what was
        # heard. FROM THIS PAGE the two configs differ in the name alone — the
        # prompt does not branch on the id and SECONDS is overwritten below with
        # the recording's own length, so their differing defaults never reach the
        # model here. They do differ everywhere else the configs are offered.
        #
        # The text is the style description wherever the writer produced one — a
        # sound is what the tags describe, not what the lyrics say — and the
        # length is the recording's, clamped to what the model can render.
        # Until 2026-10-01 Stable Audio's chunk named a fallback chunk, a legacy
        # ComfyUI workflow whose SaveAudioMP3 wrote past the staging dir, and
        # this check was where that was stopped. The chunk names none since;
        # the check stays as the refusal when Stable Audio is not available.
        try:
            from my_app.services.stable_audio_client import get_stable_audio_client
            if config_id not in SA3_CONFIGS:
                logger.error(f"[PARROT] unknown sound config {config_id!r}")
                return None
            if not asyncio.run(get_stable_audio_client().is_available()):
                logger.error("[PARROT] Stable Audio is not available; refusing")
                return None
        except Exception as e:
            logger.error(f"[PARROT] Stable Audio availability check failed: {e}")
            return None

        prompt = tags if written.get("styled") else lyrics
        context = PipelineContext(input_text=prompt, user_input=prompt)
        song_seconds = round(song_ms / 1000.0, 1)
        context.custom_placeholders = {
            # The chunk reads a trailing "DURATION: n" line and lets it decide the
            # length — that is how the flow's adaption sets one. Ending this page's
            # own text with the recording's length means a stray line inside the
            # lyrics or the tags cannot decide it instead: the LAST such line is
            # the one read, and this one is last. It is stripped again before the
            # model sees it, so nothing renders the word.
            "TEXT_1": f"{prompt.rstrip()}\nDURATION: {song_seconds}",
            # The recording's own length, inside this page's frame and
            # nothing else: this page sizes the length of its audio to the recording, up to 240 s. The frame is SONG_MIN_MS..SONG_MAX_MS, 10 to 240 s, and it
            # has already been applied — song_ms comes from _song_length_ms.
            #
            # A second ceiling stood here, 47.6 s, which is Stable Audio 1.0's;
            # it stayed behind when the platform moved to SA3 and cut every
            # recording over three quarters of a minute down to it. What is left
            # is the platform's own STABLE_AUDIO_MAX_DURATION (240 s)
            # intersected at load with what the loaded model FILE can
            # render — 380 s for SA3 medium, but exactly 120 s for the small
            # music/sfx models, which are what a card under 50 GB loads. On such a
            # card this page's four-minute promise stops at two minutes; the
            # backend now says so in its log instead of shortening in silence.
            "SECONDS": song_seconds,
        }
        first = second = prompt

    try:
        result = asyncio.run(executor.execute_pipeline(
            config_name=config_id,
            input_text=first,
            user_input=second,
            context_override=context,
            # Only the speech chunk reads it, and it must: without a language it
            # defaults to English and speaks whatever the transcriber invented in
            # an English voice. The transcriber's own decision is the honest one
            # to hand over — including when the model has no voice for it, where
            # the chunk refuses and the station reports that it did not answer.
            context_language=lang if config_id == SPEECH_CONFIG else None,
        ))
    except Exception as e:
        logger.error(f"[PARROT] Music generation failed: {e}")
        return None

    if not result or not result.success:
        logger.error(f"[PARROT] Music generation: {getattr(result, 'error', 'no result')}")
        return None

    audio_b64 = (result.metadata or {}).get("audio_data")
    if not audio_b64:
        logger.error("[PARROT] Music generation returned no audio_data")
        return None
    # The format is the chunk's to state, not this page's to assume: the music
    # models return mp3 and the speech chunk returns wav, and bytes served under
    # the wrong type do not play. Every other route on the platform reads this
    # field; until 2026-08-10 this one wrote sung.mp3 whatever it was handed.
    fmt = str((result.metadata or {}).get("audio_format") or "mp3").lower().lstrip(".")
    try:
        return base64.b64decode(audio_b64), fmt
    except Exception as e:
        # run_chain promises never to raise. An undecodable payload is a failed
        # station, not an exception escaping the chain.
        logger.error(f"[PARROT] Music generation returned undecodable audio: {e}")
        return None
