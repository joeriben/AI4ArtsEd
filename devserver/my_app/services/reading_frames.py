"""The frames an image can be read in -- one text per frame and language.

The texts live in ``schemas/reading_frames/<frame>.<lang>.md``, next to the
chunks, because they are prompt content: what a frame asks of a picture is
edited there, and never in the server's configuration file.

A frame is written per language, like every other text a participant reads:
``kritisch.ko.md`` is the Korean frame. Until a language has its file, the
English one stands in and carries one appended line naming the language the
reading is to be written in -- that line is the stand-in, and it disappears as
soon as the file exists.

Before 2026-08-29 the four frames stood in config.py, and each body carried
"Schreibe auf Deutsch" / "Write in English" inside itself. That nailed the
reading to two languages: of the platform's ten interface languages, eight got
an English reading on one surface, and the canvas got a German one on all ten.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FRAMES_DIR = Path(__file__).resolve().parents[2] / "schemas" / "reading_frames"

# The name each language is called by in the appended rule. A code that is
# missing here travels as itself -- a model told to write in "sw" does better
# than a model told nothing.
LANGUAGE_NAMES = {
    'ar': 'Arabic', 'bg': 'Bulgarian', 'de': 'German', 'en': 'English',
    'es': 'Spanish', 'fr': 'French', 'he': 'Hebrew', 'tr': 'Turkish',
    'uk': 'Ukrainian', 'ko': 'Korean', 'hsb': 'Upper Sorbian',
    'dsb': 'Lower Sorbian', 'fry': 'Frisian', 'yo': 'Yoruba',
    'sw': 'Swahili', 'qu': 'Quechua', 'cy': 'Welsh', 'hi': 'Hindi',
    'ja': 'Japanese', 'zh': 'Chinese',
}

_cache: dict[str, str] = {}


def _read(frame: str, body_lang: str) -> Optional[str]:
    key = "%s.%s" % (frame, body_lang)
    if key in _cache:
        return _cache[key]
    path = FRAMES_DIR / (key + ".md")
    try:
        text = path.read_text(encoding="utf-8").rstrip()
    except OSError:
        return None
    _cache[key] = text
    return text


def frame_ids() -> list[str]:
    """Every frame that has a text on disk, in alphabetical order."""
    try:
        return sorted({p.name.split(".")[0] for p in FRAMES_DIR.glob("*.en.md")})
    except OSError:
        logger.exception("[READING-FRAMES] %s cannot be listed", FRAMES_DIR)
        return []


def has(frame: str) -> bool:
    """Whether this name is a frame. An unknown name is a plain reading."""
    return bool(frame) and _read(frame, "en") is not None


def resolve_lang(raw: Optional[str]) -> str:
    """The language a reading is asked for. 'system' means the instance's own."""
    from config import DEFAULT_LANGUAGE

    code = str(raw or "").strip().lower()
    if not code or code == "system":
        code = str(DEFAULT_LANGUAGE or "en").strip().lower()
    return code or "en"


def prompt(frame: str, lang: Optional[str] = None) -> Optional[str]:
    """The full text for this frame in ``lang``.

    A frame that has this language is served in it and needs no instruction
    about which language to answer in -- the questions are already in it. A
    frame that lacks it is served in English with one line appended that names
    the language, so the reading arrives in the participant's language while
    the translation is still missing. ``None`` says the frame has no text at
    all, which is the caller's cue to read the picture plainly instead of
    inventing a prompt.
    """
    code = resolve_lang(lang)
    body = _read(frame, code)
    if body is not None:
        return body + "\n"
    body = _read(frame, "en")
    if body is None:
        return None
    return body + "\n- Write the reading in %s.\n" % LANGUAGE_NAMES.get(code, code)
