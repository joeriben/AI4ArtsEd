"""Deterministic delivery filter for Resona: the choose-one closing question
never reaches the group.

Operator decision 2026-07-31, after three prompt-level attempts at three
different causes each softened the move and none stopped it: Resona may write
whatever she writes, but a sentence that is a question AND either asks for a
volition ("möchtet ihr", "soll ich", "willst du" and their equivalents) or
holds a disjunction ("oder") is cut before delivery. Handing the group a set of
categories to pick from pre-empts a determination that is theirs alone; the
prompt says so, the model kept finding exceptions, so the guarantee moves out
of the prompt and into the code.

What she is told: the NEXT turn carries a plain count of what did not reach the
group. The removed sentence itself is never repeated back — repeating it would
hand her the draft again and invite the same move.

Both conditions must hold. A question that neither asks for a decision nor
offers alternatives ("Was passiert, wenn das Modell den Begriff behält?") goes
through untouched — the target is the pick-one move, not curiosity.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Question marks across the ten interface languages (ar/he carry their own).
_QUESTION_MARKS = "?？؟"

# Asking the group to will something. Lower-cased substring match, so stems
# cover their inflections (German "soll" covers sollst/sollt/sollen/sollten;
# Turkish "ister" covers ister misiniz/isterseniz).
_VOLITION = [
    # de
    "möcht", "willst", "wollt", "wollen", "soll", "wünsch", "hättet ihr lust",
    "lieber",
    # en
    "would you like", "do you want", "want me to", "shall ", "should i",
    "should we", "do you prefer", "which would you", "let me know if you",
    # fr
    "voulez", "veux-tu", "souhait", "aimeriez", "préfér", "dois-je",
    "devons-nous", "faut-il",
    # es
    "quieres", "queréis", "quieren", "desea", "prefier", "debo ", "debemos",
    # tr
    "ister", "mi̇siniz", "misiniz", "misin",
    # ko
    "하시겠", "원하", "할까요", "좋을까요", "드릴까요", "하시려", "선택",
    # uk
    "хочете", "хочеш", "бажаєте", "волієте", "чи варто", "оберіть", "обрати",
    # bg
    "искате", "искаш", "желаете", "предпочитате", "изберете",
    # ar
    "تريد", "ترغب", "تفضل", "هل",
    # he
    "רוצה", "רוצים", "מעדיף", "האם", "תבחר",
]

# Holding alternatives against each other. Word-bounded, because these are
# short and would otherwise match inside ordinary words.
_DISJUNCTION_WORDS = [
    "oder",              # de
    "or",                # en
    "ou",                # fr
    "o", "u",            # es
    "veya", "yoksa",     # tr
    "ya da",             # tr (two words)
    "아니면", "또는", "혹은",   # ko
    "чи", "або",         # uk
    "или",               # bg
    "أو", "أم",          # ar
    "או",                # he
]
_DISJUNCTION_RE = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(w) for w in _DISJUNCTION_WORDS) + r")(?!\w)",
    re.IGNORECASE,
)

# A sentence: everything up to and including its terminator (plus trailing
# closing quotes/brackets), or the trailing fragment of a line. Applied per
# line, so paragraphs, bullets and blank lines survive untouched.
#
# A terminator ends a sentence only where whitespace or the end of the line
# follows it. A dot inside a version, a file name or a domain ends nothing
# (`SD 3.5`, `bild.png`, `FLUX.2`), and neither does a `?"` before a comma. It
# is the rule of the voice's cutter (`splitForSpeech` in useSpeech.ts), so that
# what is delivered is cut where the stream was cut: since 2026-09-18 the
# voice speaks the stream's sentences, and a delivered text cut elsewhere sent
# it back to the first one.
_SENTENCE_RE = re.compile(
    r".*?[.!?…" + _QUESTION_MARKS + r"]+[)\"'»”\]]*(?=\s|$)"
    r"|.+$"
)

# Abbreviation dots are not sentence ends. Without this, "z. B." splits the
# sentence into fragments and a fragment that holds the question mark no longer
# holds the marker — the sentence goes out whole. Masked before splitting,
# restored after, so what is delivered is byte-identical to what was written.
_DOT = "\x00"
_ABBREV = (
    "ca|bzw|ggf|evtl|bspw|vgl|usw|etc|sog|bes|inkl|exkl|max|min|Nr|Abb|Bd|Hrsg"
    "|Jh|Dr|Prof|St|No|vs|Fig|Vol|ed|eds|al|approx|resp|Mio|Mrd|Tsd|engl|dt"
)
_ABBREV_RE = re.compile(
    r"(?<!\w)(?:" + _ABBREV + r")\.|(?<!\w)[A-Za-zÄÖÜäöüßÀ-ÿ]\.",
)


def _mask_abbreviations(line: str) -> str:
    return _ABBREV_RE.sub(lambda m: m.group(0)[:-1] + _DOT, line)



def is_offered_choice(sentence: str) -> bool:
    """True when this sentence is a question that also asks the group to will
    something or holds alternatives against each other."""
    if not any(mark in sentence for mark in _QUESTION_MARKS):
        return False
    low = sentence.lower()
    if any(marker in low for marker in _VOLITION):
        return True
    return bool(_DISJUNCTION_RE.search(sentence))


def filter_reply(text: str) -> Tuple[str, int]:
    """Returns (what is delivered, how many sentences were removed).

    Structure is preserved: filtering happens inside each line, so paragraphs,
    lists and blank lines come through as written. A line that loses all of its
    sentences disappears, and the paragraph breaks around it are collapsed so
    no hole is left where the question was.
    """
    if not text:
        return text, 0

    removed = 0
    out_lines = []
    for line in text.split("\n"):
        if not line.strip():
            out_lines.append(line)
            continue
        # The masking keeps every length, so a span found on the masked line
        # is the same span on the written one: what is delivered is sliced
        # out of the line as written, byte for byte.
        spans = [
            (m.start(), m.end())
            for m in _SENTENCE_RE.finditer(_mask_abbreviations(line))
        ]
        if not spans:
            out_lines.append(line)
            continue
        kept = []
        removed_here = 0
        for start, end in spans:
            if is_offered_choice(line[start:end]):
                removed_here += 1
            else:
                kept.append(line[start:end])
        removed += removed_here
        if removed_here == 0:
            out_lines.append(line)
        elif kept:
            out_lines.append("".join(kept).strip())
        else:
            continue  # the whole line was the question

    delivered = "\n".join(out_lines)
    delivered = re.sub(r"\n{3,}", "\n\n", delivered).strip()

    if removed and not delivered:
        logger.error(
            "[RESONA-FILTER] the entire reply was offered choices — "
            "nothing left to deliver"
        )
    return delivered, removed


# ---------------------------------------------------------------------------
# What she is told next turn — a count, never the sentence.
# ---------------------------------------------------------------------------
_PENDING: Dict[str, int] = {}
_PENDING_LOCK = threading.Lock()
_PENDING_MAX = 512  # process-global under threaded WSGI; bounded, best-effort


def note_removed(device_id: str | None, count: int) -> None:
    if not device_id or count <= 0:
        return
    with _PENDING_LOCK:
        if len(_PENDING) >= _PENDING_MAX and device_id not in _PENDING:
            _PENDING.clear()
        _PENDING[device_id] = _PENDING.get(device_id, 0) + count


def clear_notice(device_id: str | None) -> None:
    """
    Drop a pending cut-sentence notice without reading it. Called when the
    dialog it refers to is dropped ("new dialog", resona_routes.journal_delete)
    — otherwise the first turn of the next conversation opens by accounting for
    a sentence in a reply that no longer exists.
    """
    if not device_id:
        return
    with _PENDING_LOCK:
        _PENDING.pop(device_id, None)


def take_notice(device_id: str | None) -> str:
    """Consumes the pending count and renders the note for the system prompt.
    Empty when nothing was cut. Consuming means it is said once."""
    if not device_id:
        return ""
    with _PENDING_LOCK:
        count = _PENDING.pop(device_id, 0)
    if not count:
        return ""
    n = "One sentence" if count == 1 else f"{count} sentences"
    return (
        f"GIVEN LAST TURN: {n} of the previous reply did not reach the group. "
        "They ended in a question mark and asked the group to want something or "
        "to take one of the alternatives just laid out. Sentences of that shape "
        "are removed before delivery, every time, and they are not repeated "
        "here — the determination they would have pre-empted belongs to the "
        "people at the table. The group saw everything else."
    )
