"""The text window of a generating model, and what happens to a text that exceeds it.

An encoder reads a fixed number of tokens and drops what comes after without
saying so. Where the platform knows that number, a run asks here before it
starts: a text that fits goes as it stands, and a text that does not is
shortened — and a shortening is put in front of the person whose text it is,
because it takes words away.

The count comes from ComfyUI, measured with the tokenizer its graph cuts the
prompt with (the node package answers it on ComfyUI's HTTP server, off the
queue). The translation probe exists because the platform translates before it
generates and English costs roughly half the tokens of German: a text too long
in its own language often fits once translated, and shortening it first would
take words for nothing.
"""

import logging
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)

# The encoders a config may declare its window for (`prompt_window_tokenizer`).
ENCODERS = ('clip_l', 'clip_g', 't5')

# The shortening keeps the text and takes out what the text says twice. It is
# not a rewrite: what stays, stays in the words it was written in.
CONDENSE_INSTRUCTION = (
    "Shorten the Input to at most {words} words.\n"
    "Keep its wording, its images and its figures: what stays, stays as it is written.\n"
    "Take out repetition, restatement, and clauses that add nothing the text has not already said.\n"
    "Keep the order in which things are said, and keep the position the text is written from.\n"
    "Reply in the language of the Input.\n"
    "Output ONLY the shortened text."
)

# What is left of the window once the shortening has run. A model that answers a
# word count approximately still has to land inside the window.
_MARGIN = 0.85


def count_tokens(text: str, role: str) -> Optional[int]:
    """What ``text`` costs at the encoder ``role``, or None when unknown."""
    text = (text or '').strip()
    if not text or role not in ENCODERS:
        return None
    try:
        import requests
        from config import COMFYUI_URL

        response = requests.post(
            f"{COMFYUI_URL}/ai4artsed/text/token-count",
            json={'text': text, 'encoder': role},
            # A read timeout belongs here and nowhere near a model call: this
            # reads a vocabulary file and answers in milliseconds, off
            # ComfyUI's queue. Without one, a stalled server holds the run.
            timeout=(5, 15),
        )
        if response.status_code != 200:
            logger.warning(f"[WINDOW] Token count refused ({response.status_code}): {response.text[:200]}")
            return None
        return int(response.json().get('count'))
    except Exception as e:
        logger.warning(f"[WINDOW] Token count unavailable: {e}")
        return None


def fit_to_window(
    text: str,
    limit: int,
    role: str,
    condense: Callable[[str, str], str],
    translate: Optional[Callable[[str], str]] = None,
) -> Tuple[str, bool, Optional[int]]:
    """Return ``(text, shortened, tokens)`` for one encoder window.

    ``tokens`` is what the returned text costs once it was shortened, so the
    surface can say the figure instead of the fact.

    ``condense`` and ``translate`` are handed in so this module stays clear of
    the orchestrator: both are calls the routes already own.
    """
    text = (text or '').strip()
    if not text or not limit or role not in ENCODERS:
        return text, False, None

    count = count_tokens(text, role)
    if count is None:
        # Unknown is left alone: the encoder cuts its tail as it always did,
        # and no words are taken on a guess.
        return text, False, None
    if count <= limit:
        return text, False, count

    effective = count
    if translate is not None:
        probe = (translate(text) or '').strip()
        probe_count = count_tokens(probe, role) if probe else None
        if probe_count is not None:
            if probe_count <= limit:
                logger.info(f"[WINDOW] {count} tokens, {probe_count} translated — fits, left as it stands")
                return text, False, count
            effective = probe_count

    words = len(text.split())
    target = max(20, int(words * (limit / float(effective)) * _MARGIN))
    shortened = (condense(CONDENSE_INSTRUCTION.format(words=target), text) or '').strip()
    if not shortened or shortened == text:
        logger.warning(f"[WINDOW] Shortening returned nothing usable; text goes as it stands ({count} tokens)")
        return text, False, count

    after = count_tokens(shortened, role)
    logger.info(
        f"[WINDOW] {effective} tokens over a window of {limit}: "
        f"{words}w shortened to {len(shortened.split())}w (asked for {target}w, {after} tokens)"
    )
    return shortened, True, after
