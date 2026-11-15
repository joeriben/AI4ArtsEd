"""The three places where the platform checks what passes through it.

Every check sits at one of three places: the intake of the user's material,
the step before a media model, and the result before it leaves the server.
Six functions carry them:

  check_intake         every new piece of the user's material, once: names of
                       living private individuals and addresses with a house
                       number; at kids and youth an uploaded picture as well
  check_before_model   everything a media model receives, after the last step
                       a language model takes: the §86a lists of every
                       language over the original and its English version,
                       then the classifier with the level's question
  check_result_image   a picture, before it leaves the server (kids, youth)
  check_result_video   a video as a whole, before it leaves the server (kids,
                       youth), asked of the video reader: the classifier
                       takes no video
  check_result_text    a text a language model wrote, before it is shown
  check_result_code    code a language model wrote, before it runs in a browser

Rules that hold for all six:

  * The level is a required argument and has no default. The route resolves it
    once, on the request thread, and hands it in; nothing here asks the
    resolver, which answers the strictest level on any other thread. A value
    that is not a level is checked as the strictest one.
  * research checks nothing and calls no model. The file check of an upload
    is not in this module and stays on every level.
  * A question that gets no answer is a block. It is reported as a technical
    fault (REASON_UNAVAILABLE), never as a rating of what somebody made.
  * Each returns a Verdict: passed or not, the checkpoint, the field, a key for
    the message and the reason. The route builds the block message from it.

A verdict that passed answers for the level it was reached at and for every
looser one, in the order the resolver ranks them (kids, youth, adult,
research). A pass at youth does not answer for kids.

"Once" means that a pass is remembered per material and level, a text by its
hash, for as long as the process runs. A chat sends its history with every
turn, and what the server wrote and released at the result comes back in it
unchanged; neither is new material. Nothing that failed is remembered, and a
fault never is.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple

from my_app.services.pipeline_recorder import (
    DERIVED_IMAGE_KINDS,
    IMAGE_CHECKED_LEVELS,
    SAFETY_VERDICT_KEY,
)
from my_app.services.safety_level_resolver import SAFETY_LEVELS_STRICTEST_FIRST, STRICTEST
from my_app.utils.circuit_breaker import safety_breaker

logger = logging.getLogger(__name__)


# ── Checkpoints and message keys ────────────────────────────────────────────
#
# These travel to the browser in the block message ("safety_block") and the
# interface picks its sentence by them. `refusal` is reported by the routes,
# where a language model declined to write (is_safety_refusal); no function
# here returns it.

CHECKPOINT_INTAKE = "intake"
CHECKPOINT_BEFORE_MODEL = "before_model"
CHECKPOINT_RESULT = "result"
CHECKPOINT_REFUSAL = "refusal"

REASON_PERSONAL_DATA = "personal_data"
REASON_CONTENT = "content"
# A picture whose content was refused. The interface tells the user something
# else for a picture than for a text, and by the checkpoint whether the
# platform made the picture (result) or was given it (any other).
REASON_IMAGE_CONTENT = "image_content"
# A video the check at the result refused. A video is only ever one the
# platform made; the interface does not call it a picture.
REASON_VIDEO_CONTENT = "video_content"
REASON_SYMBOL = "symbol"
REASON_CODE = "code"
REASON_IMAGE_UNCHECKED = "image_unchecked"
# A run whose texts were checked at a looser level than the one asking: no
# verdict answers for that level (the favourites' restore).
REASON_UNCHECKED = "unchecked"
REASON_UNAVAILABLE = "unavailable"
REASON_REFUSAL = "refusal"

# The level that checks nothing at all.
UNCHECKED_LEVELS = ("research",)

# Code is looked at for what it does in the browser only below this level. The
# pattern list ran on every level except adult and research before this module
# existed (stage_orchestrator.execute_stage3_safety_code).
_CODE_PATTERN_LIMIT = "adult"

# What the sandbox must keep a sketch from: reaching out of the frame, the
# network, browser storage, injected markup, text run as code. The list the
# code check carried until 2026-10-30, unchanged.
CODE_PATTERNS = (
    'eval(',
    'Function(',
    'document.cookie',
    'localStorage.',
    'sessionStorage.',
    'fetch(',
    'XMLHttpRequest',
    'import(',
    'require(',
    '<script',
    '</script',
    'innerHTML',
    'outerHTML',
    'document.write',
    'setTimeout(',
    'setInterval(',
)


# ── The verdict ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Verdict:
    """What one check decided, and enough to say so.

    `level` is the level the check ran at, after normalisation; a pass answers
    for it and for every looser level. `field` names the material where the
    caller named it ("prompt", "context_prompt", "negative_prompt" …), so that
    a series can drop the one row whose text was refused. `reason` is the
    sentence the platform has shown for this kind of block until now; the
    interface prefers its own sentence for `reason_key`.
    """

    passed: bool
    checkpoint: str
    level: str
    field: str = ""
    reason_key: str = ""
    reason: str = ""

    @property
    def operational(self) -> bool:
        """True where no check could be carried out: a fault, not a rating."""
        return self.reason_key == REASON_UNAVAILABLE

    def block(self) -> dict:
        """The block message's own key (`safety_block`) for this verdict."""
        return safety_block(self.checkpoint, self.reason_key, self.reason, self.field)


def _passed(checkpoint: str, level: str, field: str = "") -> Verdict:
    return Verdict(True, checkpoint, level, field)


def _blocked(checkpoint: str, level: str, field: str, reason_key: str,
             reason: str) -> Verdict:
    return Verdict(False, checkpoint, level, field, reason_key, reason)


def _unavailable(checkpoint: str, level: str, field: str, why: str) -> Verdict:
    logger.error("[SAFETY-GATE] %s/%s (%s): no verdict (%s) - withheld; a fault, "
                 "not a rating", checkpoint, field or "-", level, why)
    return _blocked(checkpoint, level, field, REASON_UNAVAILABLE, _unavailable_message())


# ── The block message ───────────────────────────────────────────────────────

def safety_block(checkpoint: str, reason_key: str, reason: str = "",
                 field: str = "") -> dict:
    """The block message's own key, `safety_block`, as every route sends it.

    `checkpoint` says where the material stopped, `field` which material (the
    request field, where it is known), `reason_key` what kind of block it is,
    and `reason` the sentence the platform has shown for it until now. The
    interface picks its own sentence by `reason_key`.
    """
    return {"checkpoint": checkpoint, "field": field or "",
            "reason_key": reason_key or "", "reason": reason or ""}


def delivery_block(word: str, field: str = "image") -> dict:
    """A recorded picture, video, sketch or 3D model the delivery rule refused,
    as a block message.

    `word` is the rule's own (entity_cleared_for_delivery): "unchecked" where no
    verdict stands for it, "blocked" where one refused it. With `field` "code"
    the message is about code and with "video" about a video, which the
    interface must not call a picture. A 3D model goes by the verdict on its
    preview, which is a picture, and takes the picture's message.
    """
    if field == "code":
        key = {"unchecked": REASON_UNCHECKED, "blocked": REASON_CODE}.get(word, "")
    elif field == "video":
        key = {"unchecked": REASON_UNCHECKED, "blocked": REASON_VIDEO_CONTENT}.get(word, "")
    else:
        key = {"unchecked": REASON_IMAGE_UNCHECKED,
               "blocked": REASON_IMAGE_CONTENT}.get(word, "")
    return safety_block(CHECKPOINT_RESULT, key, word, field)


# ── Messages ────────────────────────────────────────────────────────────────
#
# The sentences below are the ones the checks before this module showed for
# these blocks (Stage 1, Stage 3, the image check). They are read from where
# they stand, or written as they stood, so that a page loaded before the
# interface read `reason_key` still reads them as it did.

def _unavailable_message() -> str:
    from schemas.engine.stage_orchestrator import SAFETY_CHECK_UNAVAILABLE_MESSAGE
    return SAFETY_CHECK_UNAVAILABLE_MESSAGE


def _content_message() -> str:
    from schemas.engine.stage_orchestrator import build_safety_message
    return build_safety_message([])


# No check before this module looked at a video. The sentence for a refused
# one is written as the image check's stands (vlm_safety.VLM_CONTENT_BLOCK_
# MESSAGE), for a page that reads `reason` rather than `reason_key`.
VIDEO_CONTENT_BLOCK_MESSAGE = (
    "⚠️ Dein Video wurde nicht freigegeben\n\n"
    "Die Videoprüfung hat Inhalte erkannt, die hier nicht geeignet sind. "
    "Versuche es mit einer anderen Idee."
)


_DSGVO_WHY = (
    "WARUM DIESE REGEL?\n"
    "Der Schutz persönlicher Daten (DSGVO) verbietet die Verarbeitung von Namen, "
    "Adressen und Kontaktdaten ohne Einwilligung.\n"
    "Bitte verwende Phantasienamen oder beschreibe Personen ohne echte Namen."
)


def _personal_data_message(candidates: Sequence[str]) -> str:
    if candidates:
        return (
            "⚠️ Dein Prompt wurde blockiert\n\n"
            "GRUND: DSGVO - Persönliche Daten erkannt\n\n"
            "Folgende persönliche Daten wurden in deinem Prompt gefunden:\n"
            f"{', '.join(candidates[:5])}\n\n" + _DSGVO_WHY
        )
    return (
        "⚠️ Dein Prompt wurde blockiert\n\n"
        "GRUND: DSGVO - Persönliche Daten erkannt\n\n"
        "Dein Prompt enthält möglicherweise persönliche Daten.\n\n" + _DSGVO_WHY
    )


def _symbol_message(terms: Sequence[str]) -> str:
    return (
        "⚠️ Dein Prompt wurde blockiert\n\n"
        "GRUND: §86a StGB\n\n"
        "Dein Prompt enthält Begriffe, die nach deutschem Recht verboten sind: "
        f"{', '.join(terms[:3])}\n\n"
        "WARUM DIESE REGEL?\n"
        "Diese Symbole werden benutzt, um Gewalt und Hass zu verbreiten.\n"
        "Wir schützen dich und andere vor gefährlichen Inhalten."
    )


# ── Levels ──────────────────────────────────────────────────────────────────

_RANK = {name: i for i, name in enumerate(SAFETY_LEVELS_STRICTEST_FIRST)}


def normalise_level(level) -> str:
    """The level as the resolver names it; any other value is the strictest.

    None counts as such a value. The functions here require the argument, and a
    caller that has nothing to pass gets the children's questions, the same
    direction the resolver falls in when it cannot resolve.
    """
    if isinstance(level, str):
        name = level.strip().lower()
        if name in _RANK:
            return name
    logger.warning("[SAFETY-GATE] %r is not a safety level - checking at %s", level, STRICTEST)
    return STRICTEST


def _rank(level) -> Optional[int]:
    if not isinstance(level, str):
        return None
    return _RANK.get(level.strip().lower())


def counts_for(verdict_level, level) -> bool:
    """Whether a pass reached at `verdict_level` answers for `level`.

    A pass answers for its own level and every looser one. A verdict level that
    is not a level answers for nothing.
    """
    have = _rank(verdict_level)
    if have is None:
        return False
    return have <= _RANK[normalise_level(level)]


def run_opens_at(run_level, level) -> bool:
    """Whether what a run recorded may be handed to whoever asks at `level`.

    At kids and youth only the material of a run made at the same level or a
    stricter one: its texts were checked with the text question of its own
    level, and a looser run's were not. A run that names no level answers for
    none. Above youth every run may be opened. The favourites' restore asks
    this (favorites_routes._restorable), and so do the chat's page context of a
    run and the chat's tools that open runs, favourites and kept strategies,
    since the chat's answer is not checked (2026-11-08). The list of a
    journal's runs in Together's prompt does not ask it (#147).
    """
    from my_app.services.pipeline_recorder import IMAGE_CHECKED_LEVELS
    if normalise_level(level) not in IMAGE_CHECKED_LEVELS:
        return True
    return counts_for(run_level, level)


def looser_level(*levels) -> Optional[str]:
    """The least strict of the given levels, or None when any of them is not a
    level. Material written at several levels answers for what the least
    strict of them answers for, and material of an unknown level for none."""
    ranks = [_rank(level) for level in levels]
    if not ranks or any(rank is None for rank in ranks):
        return None
    return SAFETY_LEVELS_STRICTEST_FIRST[max(ranks)]


# ── What has passed ─────────────────────────────────────────────────────────

class _Released:
    """Material that passed, by hash, with the strictest level it passed at.

    Bounded: the oldest entries go first. A forgotten entry costs one more
    check, never a pass.
    """

    def __init__(self, limit: int = 20000):
        self._items: "OrderedDict[tuple, str]" = OrderedDict()
        self._limit = limit
        self._lock = threading.Lock()

    def knows(self, key: tuple, level: str) -> bool:
        with self._lock:
            stored = self._items.get(key)
            if stored is None or not counts_for(stored, level):
                return False
            self._items.move_to_end(key)
            return True

    def remember(self, key: tuple, level: str) -> None:
        with self._lock:
            stored = self._items.get(key)
            if stored is None or _RANK[level] < _RANK[stored]:
                self._items[key] = level
            self._items.move_to_end(key)
            while len(self._items) > self._limit:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_RELEASED = _Released()


def _text_key(kind: str, text: str) -> tuple:
    return (kind, hashlib.sha256(text.encode("utf-8")).hexdigest())


def remember_chat_reply(text: str, *, level: str) -> None:
    """Record a reply a chat wrote at this level, so that it is no new material
    when it comes back in that chat's history.

    The chats do not check their replies (2026-11-08), so the record has a key
    of its own: it answers for a line of a chat's history and for nothing else.
    A text under the key "result" passed the lists and the level's questions;
    a chat reply passed neither, and must not count as if it had."""
    if text and text.strip():
        _RELEASED.remember(_text_key("chat_reply", text), normalise_level(level))


# ── The classifier ──────────────────────────────────────────────────────────

def _ask(policy, document: str, images: Optional[List[str]] = None) -> Optional[bool]:
    """True where the classifier says yes to `policy`, None where it said nothing."""
    from my_app.services import safety_classifier
    try:
        return safety_classifier.is_unsafe(policy, document, images=images)
    except Exception as e:  # noqa: BLE001 - no verdict is the answer to every failure
        logger.error("[SAFETY-GATE] the classifier raised %r - no verdict", e)
        return None


def _level_policy(level: str, medium: str):
    """The classifier's question for this level and medium, or None.

    None where the classifier carries no question for the pair. The check then
    cannot run, and the caller withholds. `policy_for_level` is not used here
    because it answers every gap with another question: an unknown medium gets
    the picture question, a level without questions the children's one.
    """
    from my_app.services import safety_classifier
    instruct = safety_classifier.LEVEL_INSTRUCTS.get(level)
    query = (safety_classifier.LEVEL_QUERIES.get(level) or {}).get(medium)
    if not instruct or not query:
        return None
    return instruct, query


def _level_policies(level: str, medium: str):
    """The classifier's questions for this level and medium as (level, policy)
    pairs, strictest first -- the level's own, then every less strict checked
    level's -- or None.

    None where the classifier carries no question for this level and medium
    itself (`_level_policy`); the check then cannot run, and the caller
    withholds. The chain is `safety_classifier.policies_for_level`: a level
    refuses what any less strict level refuses, by construction and not by the
    wording of its instruct.
    """
    from my_app.services import safety_classifier
    if _level_policy(level, medium) is None:
        return None
    return safety_classifier.policies_for_level(level, medium)


def _symbol_policies(level: str, medium: str):
    """The symbol questions for this level and medium as (level, policy) pairs,
    strictest first: the pair without the exception at kids and youth, then
    adult's with the exception for a historical, scientific or artistic
    context; adult's alone at adult. A text has its own pairs."""
    from my_app.services import safety_classifier
    return safety_classifier.symbol_policies_for(level, medium)


def _ask_chain(policies, document: str, images: Optional[List[str]] = None):
    """The chain of questions about one document: (answer, level).

    True at the first question that says yes, with the level whose question it
    was; None at the first that gives no answer, with that level; (False, None)
    when every question said no. The questions go strictest first, so the
    journal names the level whose question refused.
    """
    for name, policy in policies:
        answer = _ask(policy, document, images=images)
        if answer is None:
            return None, name
        if answer:
            return True, name
    return False, None


def _code_policy():
    """The question whether a sketch uses the constructs the pattern list found
    in a way that is dangerous in its sandbox, or None where the classifier
    carries none. A flagged sketch cannot be judged then, and it is withheld."""
    from my_app.services import safety_classifier
    return getattr(safety_classifier, "CODE_POLICY", None)


def _symbol_terms(texts: Iterable[str]) -> List[str]:
    """The §86a terms of every language that occur in any of `texts`.

    Raises where the list cannot be loaded; the callers turn that into a block.
    """
    from schemas.engine.stage_orchestrator import fast_filter_86a_all_languages
    found: List[str] = []
    for text in texts:
        _hit, terms = fast_filter_86a_all_languages(text)
        for term in terms:
            if term not in found:
                found.append(term)
    return found


def _versions(*texts: Optional[str]) -> List[str]:
    """The distinct, non-empty versions of one text, in order."""
    out: List[str] = []
    for text in texts:
        if text and text.strip() and text.strip() not in (t.strip() for t in out):
            out.append(text)
    return out


def _judge(versions: Sequence[str], *, level: str, medium: str, checkpoint: str,
           field: str) -> Verdict:
    """The lists, then the level's questions on every version, then, after a
    list hit, the symbol questions. A list hit alone decides nothing: the lists
    know neither the context of a word nor the symbols they lack. The questions
    of a level are its own and those of every less strict checked level
    (`_level_policies`), so that kids refuses what youth refuses."""
    try:
        terms = _symbol_terms(versions)
    except Exception as e:  # noqa: BLE001
        return _unavailable(checkpoint, level, field, f"§86a list unavailable: {e}")

    policies = _level_policies(level, medium)
    if policies is None:
        return _unavailable(checkpoint, level, field,
                            f"the classifier has no {medium} question for {level}")

    for text in versions:
        answer, asked = _ask_chain(policies, text)
        if answer is None:
            return _unavailable(checkpoint, level, field, "the classifier did not answer")
        if answer:
            logger.warning("[SAFETY-GATE] %s/%s (%s): refused by the %s question of %s",
                           checkpoint, field or "-", level, medium, asked)
            return _blocked(checkpoint, level, field, REASON_CONTENT, _content_message())

    if terms:
        return _ask_symbols(versions, terms, level=level, medium=medium,
                            checkpoint=checkpoint, field=field)
    return _passed(checkpoint, level, field)


def _ask_symbols(versions: Sequence[str], terms: Sequence[str], *, level: str, medium: str,
                 checkpoint: str, field: str) -> Verdict:
    """After a list hit, the symbol questions on every version."""
    logger.info("[SAFETY-GATE] %s/%s (%s): §86a list hit %s - asking the symbol question",
                checkpoint, field or "-", level, list(terms)[:3])
    for text in versions:
        answer, asked = _ask_chain(_symbol_policies(level, medium), text)
        if answer is None:
            return _unavailable(checkpoint, level, field, "the classifier did not answer")
        if answer:
            logger.warning("[SAFETY-GATE] %s/%s (%s): refused by the symbol question of %s",
                           checkpoint, field or "-", level, asked)
            return _blocked(checkpoint, level, field, REASON_SYMBOL, _symbol_message(terms))
    return _passed(checkpoint, level, field)


def _judge_lists(versions: Sequence[str], *, level: str, medium: str, checkpoint: str,
                 field: str) -> Verdict:
    """The lists, and after a hit the symbol questions. The level's questions
    are not asked: what a chat takes in (`_intake_chat`)."""
    try:
        terms = _symbol_terms(versions)
    except Exception as e:  # noqa: BLE001
        return _unavailable(checkpoint, level, field, f"§86a list unavailable: {e}")
    if terms:
        return _ask_symbols(versions, terms, level=level, medium=medium,
                            checkpoint=checkpoint, field=field)
    return _passed(checkpoint, level, field)


# ── Translation for the check ───────────────────────────────────────────────
#
# Where a media model receives the text as written, the check translates it
# itself, so that the lists and the classifier read an English version beside
# the original. Fail-closed, as Stage 3 was: no translation, no check.

_TRANSLATIONS: "OrderedDict[tuple, str]" = OrderedDict()
_TRANSLATIONS_LIMIT = 512
_TRANSLATIONS_LOCK = threading.Lock()


def _run(coro):
    """Run a coroutine to its end from synchronous code, inside an event loop
    or outside one."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _translate_for_check(text: str, instruction: Optional[str] = None) -> Optional[str]:
    """The English version the check reads beside `text`, or None.

    Through the platform's own translation config, in the context every
    translation into English runs in (stage_orchestrator.translation_context).
    Remembered by the text and the wording it was made under, so that a run
    that checks the same text twice translates it once; the key is the text
    itself, so no device reads another one's translation.
    """
    key = (hashlib.sha256(text.encode("utf-8")).hexdigest(), (instruction or "").strip())
    with _TRANSLATIONS_LOCK:
        if key in _TRANSLATIONS:
            _TRANSLATIONS.move_to_end(key)
            return _TRANSLATIONS[key]
    try:
        import my_app.routes.schema_pipeline_routes as spr
        from schemas.engine.stage_orchestrator import translation_context
        if spr.pipeline_executor is None:
            spr.init_schema_engine()
        result = _run(spr.pipeline_executor.execute_pipeline(
            'pre_output/translation_en', text,
            context_override=translation_context(text, instruction),
        ))
    except Exception as e:  # noqa: BLE001
        logger.error("[SAFETY-GATE] translation for the check failed: %r", e)
        return None
    english = (getattr(result, "final_output", None) or "").strip()
    if not getattr(result, "success", False) or not english:
        logger.error("[SAFETY-GATE] translation for the check came back empty")
        return None
    with _TRANSLATIONS_LOCK:
        _TRANSLATIONS[key] = english
        while len(_TRANSLATIONS) > _TRANSLATIONS_LIMIT:
            _TRANSLATIONS.popitem(last=False)
    return english


# ── Addresses ───────────────────────────────────────────────────────────────
#
# A street with a house number. A hit decides nothing: the classifier's name
# question decides after it, as it does after a name the recogniser flags.
# German compounds and separate street words ("Hauptstraße 12", "Berliner
# Straße 5a", "Am Mühlweg 3"), and the English order ("221B Baker Street").
# House numbers have one to three digits, so that a year after a word ending in
# one of these suffixes is no address.

_STREET_SUFFIX_DE = (
    r"(?:stra(?:ß|ss)e|str\.|weg|gasse|allee|platz|ring|damm|ufer|chaussee|"
    r"steig|stieg|pfad|zeile|graben|wall|kai|promenade)"
)
_ADDRESS_DE = re.compile(
    r"(?<![\w-])[\w.-]*?" + _STREET_SUFFIX_DE + r"\s+\d{1,3}\s?[a-z]?(?![\w])",
    re.IGNORECASE,
)
_ADDRESS_EN = re.compile(
    r"(?<![\w])\d{1,4}[A-Za-z]?\s+(?:[A-Z][\w'-]*\s+){1,3}"
    r"(?i:street|st\.?|road|rd\.?|avenue|ave\.?|lane|ln\.?|drive|dr\.?|"
    r"boulevard|blvd\.?|way|place|pl\.?|square|sq\.?|court|ct\.?)(?![\w])"
)


def find_addresses(text: str) -> List[str]:
    """Every stretch of `text` that looks like a street with a house number."""
    found: List[str] = []
    for pattern in (_ADDRESS_DE, _ADDRESS_EN):
        for match in pattern.finditer(text or ""):
            hit = match.group(0).strip()
            if hit and hit not in found:
                found.append(hit)
    return found


# ── Images ──────────────────────────────────────────────────────────────────

_UPLOAD_EXTS = ("png", "jpg", "jpeg", "webp")
_UPLOAD_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_UPLOAD_VERDICT_LOCK = threading.Lock()


def _uploads_dir() -> Path:
    import config
    return Path(config.UPLOADS_TMP_DIR)


def _runs_dir() -> Path:
    import config
    return Path(config.JSON_STORAGE_DIR)


def upload_verdict_path(upload_id: str) -> Optional[Path]:
    """Where the verdicts of one upload are kept, or None for a malformed id."""
    if not isinstance(upload_id, str) or not _UPLOAD_ID_RE.fullmatch(upload_id):
        return None
    return _uploads_dir() / f"{upload_id}.verdict.json"


def record_upload_verdict(upload_id: str, verdict: Verdict) -> bool:
    """Keep a verdict beside the upload it judges, one entry per level.

    Returns False where nothing could be written; the upload then has no
    verdict, and a strict level will not take it.
    """
    path = upload_verdict_path(upload_id)
    if path is None:
        logger.error("[SAFETY-GATE] %r is no upload id - verdict not kept", upload_id)
        return False
    entry = {"passed": bool(verdict.passed), "checked_at": datetime.now().isoformat()}
    with _UPLOAD_VERDICT_LOCK:
        levels = _read_upload_verdicts(path)
        levels[verdict.level] = entry
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"levels": levels}, handle)
            os.replace(tmp, path)
        except OSError as e:
            logger.error("[SAFETY-GATE] verdict for upload %s not kept: %s", upload_id, e)
            return False
    return True


def _read_upload_verdicts(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    levels = data.get("levels") if isinstance(data, dict) else None
    return dict(levels) if isinstance(levels, dict) else {}


def upload_cleared_for(upload_id: str, level: str) -> bool:
    """Whether a kept verdict of this upload answers for `level`."""
    path = upload_verdict_path(upload_id)
    if path is None:
        return False
    for verdict_level, entry in _read_upload_verdicts(path).items():
        if isinstance(entry, dict) and entry.get("passed") is True and counts_for(verdict_level, level):
            return True
    return False


def entity_cleared_for(entity: dict, run_metadata: dict, level: str) -> bool:
    """Whether a recorded picture carries a pass that answers for `level`.

    The verdict's own level counts; a verdict written before verdicts carried
    one counts at the level of its run. A picture made of the run's pictures
    (a strip, a before/after pair) answers as the least cleared of them.
    """
    etype = str(entity.get("type") or "")
    kind = etype[len("output_"):] if etype.startswith("output_") else etype
    if kind in DERIVED_IMAGE_KINDS:
        sources = [e for e in run_metadata.get("entities", []) if e.get("type") == "output_image"]
        return bool(sources) and all(entity_cleared_for(e, run_metadata, level) for e in sources)
    verdict = (entity.get("metadata") or {}).get(SAFETY_VERDICT_KEY)
    if not isinstance(verdict, dict) or verdict.get("safe") is not True:
        return False
    return counts_for(verdict.get("level") or run_metadata.get("safety_level"), level)


def _load_run(run_id: str):
    from my_app.services.pipeline_recorder import load_recorder
    try:
        return load_recorder(run_id, base_path=_runs_dir())
    except Exception as e:  # noqa: BLE001
        logger.debug("[SAFETY-GATE] run %s could not be loaded: %s", run_id, e)
        return None


def _run_image_cleared(run_id: str, index: Optional[int], level: str) -> bool:
    from my_app.utils.media_ref import find_media_entities
    recorder = _load_run(run_id)
    if recorder is None:
        return False
    entities = find_media_entities(recorder.metadata.get("entities", []), "image")
    if not entities:
        return False
    i = -1 if index is None else int(index)
    if i < 0:
        i += len(entities)
    if not 0 <= i < len(entities):
        return False
    return entity_cleared_for(entities[i], recorder.metadata, level)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _path_cleared(path: Path, level: str) -> bool:
    """A file path has a verdict only in two places: the upload directory and
    the final folder of a recorded run. Anywhere else it has none."""
    try:
        path = path.resolve()
        uploads = _uploads_dir().resolve()
        runs = _runs_dir().resolve()
    except OSError:
        return False
    if path.parent == uploads:
        stem, _dot, ext = path.name.rpartition(".")
        return ext.lower() in _UPLOAD_EXTS and upload_cleared_for(stem, level)
    if _within(path, runs) and path.parent.name == "final":
        recorder = _load_run(path.parent.parent.name)
        if recorder is None:
            return False
        try:
            if Path(recorder.final_folder).resolve() != path.parent:
                return False
        except OSError:
            return False
        for entity in recorder.metadata.get("entities", []):
            if entity.get("filename") == path.name:
                return entity_cleared_for(entity, recorder.metadata, level)
    return False


def _decode_image_data(material) -> Optional[bytes]:
    """Raw image bytes from bytes, a data URL or a base64 string; None otherwise."""
    if isinstance(material, (bytes, bytearray)):
        return bytes(material)
    if not isinstance(material, str):
        return None
    from my_app.utils.media_ref import strip_data_url
    try:
        return base64.b64decode(strip_data_url(material.strip()), validate=False)
    except (binascii.Error, ValueError):
        return None


def _is_inline_image(ref) -> bool:
    """Whether `ref` carries the picture itself rather than naming one.

    Bytes and data URLs do. A string longer than any path the resolver reads
    as a reference is base64 (utils/media_ref.py, _MAX_PATHLIKE_LEN).
    """
    from my_app.utils.media_ref import _MAX_PATHLIKE_LEN
    if isinstance(ref, (bytes, bytearray)):
        return True
    if isinstance(ref, str):
        stripped = ref.strip()
        return stripped.startswith("data:") or len(stripped) > _MAX_PATHLIKE_LEN
    return False


def image_reference_cleared(ref, level: str) -> bool:
    """Whether the picture `ref` names carries a pass that answers for `level`.

    The references a picture reaches a model by, each read the way
    utils/media_ref.resolve_media_ref reads it:

      1. a file path: the upload's verdict under the upload directory, the
         recorded entity's verdict in a run's final folder, none elsewhere
      2. an upload id
      3. /api/media/uploads/<id>
      4. /api/media/image/<run>/<index>, and a bare run id
      5. the picture itself (base64) is not a reference: check_intake judges it

    Nothing here resolves a reference that the resolver would refuse, and
    nothing here passes a reference it cannot place.
    """
    from my_app.utils.media_ref import _MAX_PATHLIKE_LEN, _MEDIA_URL_RE, _UPLOAD_URL_RE

    level = normalise_level(level)
    if isinstance(ref, Path):
        return ref.exists() and _path_cleared(ref, level)
    if not isinstance(ref, str) or not ref.strip():
        return False
    ref = ref.strip()

    if len(ref) <= _MAX_PATHLIKE_LEN and not ref.startswith("/api/"):
        try:
            candidate = Path(ref)
            if candidate.exists():
                return _path_cleared(candidate, level)
        except (OSError, ValueError):
            pass

    match = _MEDIA_URL_RE.match(ref)
    if match:
        if match.group("kind") != "image":
            return False
        index = match.group("index")
        return _run_image_cleared(match.group("run_id"),
                                  int(index) if index is not None else None, level)

    match = _UPLOAD_URL_RE.match(ref)
    if match:
        return upload_cleared_for(match.group("upload_id"), level)

    if "/" not in ref and "\\" not in ref and len(ref) <= _MAX_PATHLIKE_LEN:
        if any((_uploads_dir() / f"{ref}.{ext}").exists() for ext in _UPLOAD_EXTS):
            return upload_cleared_for(ref, level)
        return _run_image_cleared(ref, None, level)

    return False


def carried_intake_verdict(raw, source, *, level, field: str) -> Optional[Verdict]:
    """The pass a recorded picture carries over to its own bytes, uploaded again.

    A surface that takes a recorded picture as material fetches it and uploads
    it again, naming the address it fetched (useMaterialIntake.
    uploadImageFromUrl); the flow does this with every picture of its own runs.
    Where `source` is the address of a recorded picture
    (/api/media/image/<run>[/<index>]), that picture carries a pass answering
    for `level`, and `raw` is that picture byte for byte, the pass carries over
    and nothing is asked again. None otherwise, and the upload is asked like any
    other: the address is the sender's word, the bytes are not.
    """
    level = normalise_level(level)
    if level not in IMAGE_CHECKED_LEVELS or not isinstance(source, str):
        return None
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        return None
    from my_app.utils.media_ref import _MEDIA_URL_RE, MediaRefError, resolve_media_ref

    address = source.strip().split("#", 1)[0].split("?", 1)[0]
    match = _MEDIA_URL_RE.match(address)
    if not match or match.group("kind") != "image" or not image_reference_cleared(address, level):
        return None
    try:
        recorded = resolve_media_ref(address, kind="image", level=level).read_bytes()
    except (MediaRefError, OSError) as e:
        logger.info("[SAFETY-GATE] %s could not be read back: %s", address, e)
        return None
    if recorded != bytes(raw):
        return None
    logger.info("[SAFETY-GATE] intake/%s (%s): the pass of %s carries over", field or "-", level, address)
    return _passed(CHECKPOINT_INTAKE, level, field)


class _ImageFile:
    """A picture as a file on disk, written to a temporary one where it came as data.

    `path` is None where there is no picture to look at; `fault` then says why,
    where writing it down failed.
    """

    def __init__(self, material):
        self.path: Optional[Path] = None
        self.fault = ""
        self._temporary = False
        if isinstance(material, Path) or (isinstance(material, str) and not _is_inline_image(material)):
            candidate = Path(material)
            try:
                if candidate.is_file():
                    self.path = candidate
            except (OSError, ValueError):
                pass
            return
        data = _decode_image_data(material)
        if not data:
            return
        name = None
        try:
            fd, name = tempfile.mkstemp(prefix="safety_gate_", suffix=".img")
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
        except OSError as e:
            # The check reads a file. A picture the disk cannot take was never
            # looked at: it is withheld as a fault, and no half of it stays.
            self.fault = f"the picture could not be written for the check: {e}"
            if name is not None:
                try:
                    os.unlink(name)
                except OSError:
                    pass
            return
        self.path = Path(name)
        self._temporary = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self._temporary and self.path is not None:
            try:
                self.path.unlink()
            except OSError:
                pass
        return False


def _ask_image(path: Path, level: str, checkpoint: str, field: str) -> Verdict:
    """The level's picture question about one file, through the image check."""
    from my_app.utils.vlm_safety import VLM_OPERATIONAL_BLOCK_MESSAGE, vlm_safety_check
    try:
        safe, reason, _description = vlm_safety_check(path, level)
    except Exception as e:  # noqa: BLE001
        return _unavailable(checkpoint, level, field, f"the image check raised {e!r}")
    if safe:
        return _passed(checkpoint, level, field)
    if reason == VLM_OPERATIONAL_BLOCK_MESSAGE:
        logger.error("[SAFETY-GATE] %s/%s (%s): the image check gave no verdict",
                     checkpoint, field or "-", level)
        return _blocked(checkpoint, level, field, REASON_UNAVAILABLE, reason)
    logger.warning("[SAFETY-GATE] %s/%s (%s): picture refused", checkpoint, field or "-", level)
    return _blocked(checkpoint, level, field, REASON_IMAGE_CONTENT, reason)


def _ask_video(path: Path, level: str, checkpoint: str, field: str) -> Verdict:
    """The level's video questions about one file, asked of the video reader.

    The questions are the classifier's, in the classifier's form
    (safety_classifier.video_question), and each score is read against the
    classifier's threshold. The questions are the level's own and those of
    every less strict level with a video question (kids asks kids' and
    youth's), each a pass of the reader over the video; the first yes refuses.
    No answer is a block, as everywhere here.
    """
    from my_app.services import safety_classifier
    from my_app.services.media_analysis_client import get_media_analysis_client, last_reason
    try:
        if not path.is_file():
            return _unavailable(checkpoint, level, field, f"no video at {path.name}")
        chain = safety_classifier.policies_for_level(level, medium="video")
        if not chain:
            return _unavailable(checkpoint, level, field,
                                f"the classifier has no video question for {level}")
        client = get_media_analysis_client()
        for asked, policy in chain:
            system_prompt, prompt = safety_classifier.video_question(policy)
            value = client.score_video(str(path), system_prompt, prompt)
            if value is None:
                return _unavailable(checkpoint, level, field,
                                    f"the video check gave no verdict ({last_reason() or 'no reason given'})")
            if value >= safety_classifier.UNSAFE_THRESHOLD:
                logger.warning("[SAFETY-GATE] %s/%s (%s): video refused by the question of %s (score %.4f)",
                               checkpoint, field or "-", level, asked, value)
                return _blocked(checkpoint, level, field, REASON_VIDEO_CONTENT,
                                VIDEO_CONTENT_BLOCK_MESSAGE)
            logger.info("[SAFETY-GATE] %s/%s (%s): video passed the question of %s (score %.4f)",
                        checkpoint, field or "-", level, asked, value)
    except Exception as e:  # noqa: BLE001
        return _unavailable(checkpoint, level, field, f"the video check raised {e!r}")
    return _passed(checkpoint, level, field)


# ── 1. The intake ───────────────────────────────────────────────────────────

def check_intake(material, *, level, kind: str, field: str) -> Verdict:
    """Check one new piece of the user's material, once.

    kind "text"      names of living private individuals and addresses with a
                     house number: the name recogniser and the address pattern
                     look, and after a hit the classifier's name question
                     decides. Without the recogniser the question is always
                     asked.
    kind "image"     a file path, raw bytes, a data URL or base64. At kids and
                     youth the level's picture question; at the other levels
                     nothing. Where the picture is an upload, the route keeps
                     the verdict beside it (record_upload_verdict).
    kind "document"  the text of a document, one string per section. Every
                     list (§86a in every language, §86 organisations, further
                     categories); after a hit the level's text question about
                     that section. Then names and addresses, section by
                     section. The file check of the upload is the route's.
    kind "chat"      what a chat turn takes in: names and addresses as for
                     "text", then the §86a lists of every language and, after
                     a hit, the symbol question. The level's text question is
                     not asked: what the chat says is its model's, under the
                     level named in its prompt, and nothing of what the model
                     writes is checked (since 2026-11-08).
    """
    level = normalise_level(level)
    if level in UNCHECKED_LEVELS:
        return _passed(CHECKPOINT_INTAKE, level, field)
    if kind == "text":
        return _intake_text(material, level, field)
    if kind == "image":
        return _intake_image(material, level, field)
    if kind == "document":
        return _intake_document(material, level, field)
    if kind == "chat":
        return _intake_chat(material, level, field)
    raise ValueError(f"check_intake: unknown kind of material {kind!r}")


def check_intake_texts(fields: Mapping[str, Optional[str]], *, level,
                       kind: str = "text") -> Verdict:
    """check_intake for several text fields: the first block, or a pass."""
    level = normalise_level(level)
    for name, text in fields.items():
        verdict = check_intake(text, level=level, kind=kind, field=name)
        if not verdict.passed:
            return verdict
    return _passed(CHECKPOINT_INTAKE, level)


def _intake_text(text, level: str, field: str) -> Verdict:
    if text is None or not str(text).strip():
        return _passed(CHECKPOINT_INTAKE, level, field)
    text = str(text)
    key = _text_key("intake", text)
    if _RELEASED.knows(key, level) or _RELEASED.knows(_text_key("result", text), level):
        return _passed(CHECKPOINT_INTAKE, level, field)

    try:
        from schemas.engine.stage_orchestrator import fast_dsgvo_check, llm_personal_data_check
        _has_names, names, recogniser = fast_dsgvo_check(text)
    except Exception as e:  # noqa: BLE001
        return _unavailable(CHECKPOINT_INTAKE, level, field, f"name recognition failed: {e!r}")

    candidates = list(names) if recogniser else []
    candidates += find_addresses(text)
    if recogniser and not candidates:
        _RELEASED.remember(key, level)
        return _passed(CHECKPOINT_INTAKE, level, field)

    # The breaker decides nothing: it writes to the log when the name question
    # keeps failing, and when it answers again.
    try:
        answer = llm_personal_data_check(text, candidates or None)
    except Exception as e:  # noqa: BLE001
        safety_breaker.record_failure()
        return _unavailable(CHECKPOINT_INTAKE, level, field, f"the name question raised {e!r}")
    if answer is None:
        safety_breaker.record_failure()
        return _unavailable(CHECKPOINT_INTAKE, level, field, "the name question got no answer")
    safety_breaker.record_success()
    if answer:
        logger.warning("[SAFETY-GATE] intake/%s (%s): personal data", field or "-", level)
        return _blocked(CHECKPOINT_INTAKE, level, field, REASON_PERSONAL_DATA,
                        _personal_data_message(candidates))
    _RELEASED.remember(key, level)
    return _passed(CHECKPOINT_INTAKE, level, field)


def _intake_chat(text, level: str, field: str) -> Verdict:
    if text is None or not str(text).strip():
        return _passed(CHECKPOINT_INTAKE, level, field)
    text = str(text)
    key = _text_key("chat", text)
    if _RELEASED.knows(key, level) or _RELEASED.knows(_text_key("result", text), level):
        return _passed(CHECKPOINT_INTAKE, level, field)
    # A reply of the chat comes back in the next turn's history. It is the
    # model's own text, which the chats do not check, and no new material
    # there; in any other field it is (remember_chat_reply).
    if field == "history" and _RELEASED.knows(_text_key("chat_reply", text), level):
        return _passed(CHECKPOINT_INTAKE, level, field)
    verdict = _intake_text(text, level, field)
    if not verdict.passed:
        return verdict
    verdict = _judge_lists([text], level=level, medium="text", checkpoint=CHECKPOINT_INTAKE,
                           field=field)
    if verdict.passed:
        _RELEASED.remember(key, level)
    return verdict


def _intake_image(material, level: str, field: str) -> Verdict:
    if level not in IMAGE_CHECKED_LEVELS:
        return _passed(CHECKPOINT_INTAKE, level, field)
    with _ImageFile(material) as image:
        if image.path is None:
            return _unavailable(CHECKPOINT_INTAKE, level, field,
                                image.fault or "no picture could be read")
        try:
            key = ("image", hashlib.sha256(image.path.read_bytes()).hexdigest())
        except OSError as e:
            return _unavailable(CHECKPOINT_INTAKE, level, field, f"the picture could not be read: {e}")
        if _RELEASED.knows(key, level):
            return _passed(CHECKPOINT_INTAKE, level, field)
        verdict = _ask_image(image.path, level, CHECKPOINT_INTAKE, field)
    if verdict.passed:
        _RELEASED.remember(key, level)
    return verdict


def _document_list_hit(section: str) -> Optional[bool]:
    """Whether any list knows a term of the section; None where a list cannot be read."""
    try:
        if _symbol_terms([section]):
            return True
        from my_app.services.upload_gate import scan_own_lists
        return scan_own_lists(section) is not None
    except Exception as e:  # noqa: BLE001
        logger.error("[SAFETY-GATE] a document list could not be read: %r", e)
        return None


def _intake_document(sections, level: str, field: str) -> Verdict:
    if isinstance(sections, str):
        sections = [sections]
    sections = [s for s in (sections or []) if isinstance(s, str) and s.strip()]
    for i, section in enumerate(sections):
        name = f"{field}[{i}]" if len(sections) > 1 else field
        hit = _document_list_hit(section)
        if hit is None:
            return _unavailable(CHECKPOINT_INTAKE, level, name, "a document list could not be read")
        if hit:
            # The section is asked the level's text question, about what it
            # says as a whole; at kids, youth and adult that question carries
            # the rule on symbols for a text.
            policies = _level_policies(level, "text")
            if policies is None:
                return _unavailable(CHECKPOINT_INTAKE, level, name,
                                    f"the classifier has no text question for {level}")
            answer, asked = _ask_chain(policies, section)
            if answer is None:
                return _unavailable(CHECKPOINT_INTAKE, level, name, "the classifier did not answer")
            if answer:
                logger.warning("[SAFETY-GATE] intake/%s (%s): document section refused by the "
                               "text question of %s", name, level, asked)
                return _blocked(CHECKPOINT_INTAKE, level, name, REASON_CONTENT, _content_message())
        verdict = _intake_text(section, level, name)
        if not verdict.passed:
            return verdict
    return _passed(CHECKPOINT_INTAKE, level, field)


# ── 2. Before the model ─────────────────────────────────────────────────────

def _named(values, prefix: str) -> List[Tuple[str, object]]:
    """(field, value) pairs from a mapping, a single value or a sequence."""
    if values is None:
        return []
    if isinstance(values, Mapping):
        return list(values.items())
    if isinstance(values, (str, bytes, bytearray, Path)):
        return [(prefix, values)]
    values = list(values)
    if len(values) == 1:
        return [(prefix, values[0])]
    return [(f"{prefix}_{i}", v) for i, v in enumerate(values)]


def check_before_model(texts, *, level, originals=(), images=(),
                       translation_instruction: Optional[str] = None) -> Verdict:
    """Check everything a media model is about to receive.

    `texts` are the texts the model receives, after the last step a language
    model takes; no language model may run between this check and the model.
    A mapping names their fields ({"prompt": …, "negative_prompt": …}). None
    and an empty text are no text. Anything else that is not a string is
    withheld: the model would receive what the check cannot read.
    `originals` are the same texts before translation, under the same names,
    where the model receives a translation; the translation is then the
    English version the check reads. Where the model receives a text as
    written, the check translates it itself, and a translation that fails is
    a block.

    The §86a lists of every language run over both versions, the classifier
    asks the level's prompt question about both, and after a list hit the
    symbol question. A list hit alone decides nothing.

    `images` are the pictures the model receives, as references or data. At
    kids and youth each needs a pass that answers for the level, found through
    its reference; a picture that comes as data is new material and judged
    here. Pictures are not checked at the other levels.
    """
    level = normalise_level(level)
    checkpoint = CHECKPOINT_BEFORE_MODEL
    if level in UNCHECKED_LEVELS:
        return _passed(checkpoint, level)

    if level in IMAGE_CHECKED_LEVELS:
        for field, ref in _named(images, "image"):
            if _is_inline_image(ref):
                verdict = _intake_image(ref, level, field)
                if not verdict.passed:
                    return Verdict(False, checkpoint, level, field, verdict.reason_key, verdict.reason)
            elif not image_reference_cleared(ref, level):
                logger.warning("[SAFETY-GATE] before_model/%s (%s): picture without a verdict "
                               "for this level - withheld", field, level)
                return _blocked(checkpoint, level, field, REASON_IMAGE_UNCHECKED, "")

    original_of = {name: value for name, value in _named(originals, "text")}
    for field, text in _named(texts, "text"):
        if text is None or (isinstance(text, str) and not text.strip()):
            continue
        if not isinstance(text, str):
            return _unavailable(checkpoint, level, field,
                                f"a {type(text).__name__} where a text belongs")
        original = original_of.get(field)
        if isinstance(original, str) and original.strip() and original.strip() != text.strip():
            versions = _versions(original, text)
        else:
            english = _translate_for_check(text, translation_instruction)
            if english is None:
                return _unavailable(checkpoint, level, field, "translation for the check failed")
            versions = _versions(text, english)
        verdict = _judge(versions, level=level, medium="prompt", checkpoint=checkpoint, field=field)
        if not verdict.passed:
            return verdict
    return _passed(checkpoint, level)


# ── 3. At the result ────────────────────────────────────────────────────────

def check_result_image(path, *, level, recorder=None, entity=None,
                       field: str = "image") -> Verdict:
    """Ask the level's picture question about a picture before it leaves.

    At kids and youth only; at adult a picture is not checked. `path` is a
    file, or the picture's bytes where it stands only in a response body. With
    `recorder` and `entity` (the entity's sequence number) the verdict is
    written onto the entity, with its level, which is what delivery reads.
    """
    level = normalise_level(level)
    if level not in IMAGE_CHECKED_LEVELS:
        return _passed(CHECKPOINT_RESULT, level, field)
    with _ImageFile(path) as image:
        if image.path is None:
            verdict = _unavailable(CHECKPOINT_RESULT, level, field,
                                   image.fault or "no picture could be read")
        else:
            verdict = _ask_image(image.path, level, CHECKPOINT_RESULT, field)
    _record(recorder, entity, verdict)
    return verdict


def check_result_video(path, *, level, recorder=None, entity=None,
                       field: str = "video") -> Verdict:
    """Ask the level's video question about a video before it leaves.

    At kids and youth only, as a picture; at adult a video is not checked.
    The video is asked about as a whole, frames and motion, by the video
    reader, because the classifier takes no video; its sound is not heard
    here. `path` is the video's file. With `recorder` and `entity` (the
    entity's sequence number) the verdict is written onto the entity, with
    its level, which is what delivery reads.
    """
    level = normalise_level(level)
    if level not in IMAGE_CHECKED_LEVELS:
        return _passed(CHECKPOINT_RESULT, level, field)
    verdict = _ask_video(Path(path), level, CHECKPOINT_RESULT, field)
    _record(recorder, entity, verdict)
    return verdict


def preview_for(preview, *, level):
    """A picture shown while it is being made, as it may go out at `level`.

    At kids and youth a picture goes out only with a verdict, and one still
    being made has none: it goes out with the verdict on the finished picture,
    and by the time that verdict is there, the finished picture is what is
    shown. So at those levels a preview does not go out at all, and the surface
    shows the progress without a picture. At adult and research no picture is
    checked. Without a level it is held back, as at the strictest.
    """
    return None if normalise_level(level) in IMAGE_CHECKED_LEVELS else preview


def check_result_text(text, *, level, field: str = "text") -> Verdict:
    """Check a text a language model wrote, before it is shown or kept.

    The §86a lists of every language, the level's text question, and after a
    list hit the symbol question. The text is not changed: it passes as it is
    or it is withheld. A text that passed is remembered, so that it is no new
    material when it comes back in a chat's history.
    """
    level = normalise_level(level)
    if level in UNCHECKED_LEVELS or not isinstance(text, str) or not text.strip():
        return _passed(CHECKPOINT_RESULT, level, field)
    key = _text_key("result", text)
    if _RELEASED.knows(key, level):
        return _passed(CHECKPOINT_RESULT, level, field)
    verdict = _judge([text], level=level, medium="text", checkpoint=CHECKPOINT_RESULT, field=field)
    if verdict.passed:
        _RELEASED.remember(key, level)
    return verdict


def code_patterns_in(code: str) -> List[str]:
    """The constructs of CODE_PATTERNS that occur in `code`, case aside."""
    lowered = (code or "").lower()
    return [p for p in CODE_PATTERNS if p.lower() in lowered]


def check_result_code(code, *, level, recorder=None, entity=None,
                      field: str = "code") -> Verdict:
    """Check code a language model wrote, before it runs in a browser.

    The level's text check over the code as text, because the strings of a
    sketch can appear on the surface. Below adult, the pattern list as well:
    after a hit the classifier is asked whether the sketch uses what the list
    found in a way that is dangerous in its sandbox. With `recorder` and
    `entity` the verdict is written onto the entity, with its level, which is
    what delivery reads.
    """
    level = normalise_level(level)
    if level in UNCHECKED_LEVELS:
        return _passed(CHECKPOINT_RESULT, level, field)
    verdict = check_result_text(code, level=level, field=field)
    if verdict.passed and _RANK[level] < _RANK[_CODE_PATTERN_LIMIT]:
        patterns = code_patterns_in(code)
        if patterns:
            policy = _code_policy()
            if policy is None:
                verdict = _unavailable(CHECKPOINT_RESULT, level, field,
                                       f"patterns {patterns} and no code question")
            else:
                # The question names what the list found; the document is the
                # sketch as it would run.
                instruct, query = policy
                answer = _ask((instruct, query.replace("{patterns}", ", ".join(patterns))),
                              code)
                if answer is None:
                    verdict = _unavailable(CHECKPOINT_RESULT, level, field,
                                           "the code question got no answer")
                elif answer:
                    logger.warning("[SAFETY-GATE] result/%s (%s): code refused for %s",
                                   field, level, patterns)
                    verdict = _blocked(CHECKPOINT_RESULT, level, field, REASON_CODE,
                                       _content_message())
    _record(recorder, entity, verdict)
    return verdict


def _record(recorder, entity, verdict: Verdict) -> None:
    """Write the verdict onto a recorded entity, with its level.

    A check that could not be carried out writes nothing. The entity stays
    without a verdict, which delivery withholds all the same, and a later check
    can still clear it; written down, the fault would stand on the entity for
    good as a rating of what somebody made.
    """
    if recorder is None or entity is None or verdict.operational:
        return
    try:
        recorder.mark_entity_safety(entity, verdict.passed, reason=verdict.reason,
                                    level=verdict.level)
    except Exception as e:  # noqa: BLE001 - an unmarked entity is not delivered
        logger.error("[SAFETY-GATE] the verdict for entity %s could not be written: %r",
                     entity, e)
