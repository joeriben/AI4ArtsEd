"""Translations that never have to be paid for twice.

The bias questions are a fixed corpus. The same question, asked for in the same
language, has exactly one translation, and asking a model for it a second time
buys a result that is already known. So what comes back is kept.

WHAT IS KEPT IS A WHOLE QUESTION, never its pieces on their own. The obvious
saving would be to key each piece separately - BBQ repeats itself heavily, the
same "Cannot be determined" and the same group names run through thousands of
situations, and a store keyed by piece would translate each of those once for
the whole benchmark. It would also be wrong. German makes an answer agree with
how its situation named the person, so "The 78-year-old" is "Die 78-jaehrige
Person" under one situation and "Der 78-Jaehrige" under another. A piece
translated in the first situation and served in the second reads as a mismatch
inside one question - and gendered variation across templates is exactly what
BBQ varies on purpose, so the mismatch would land on the axis the instrument is
measuring. The five pieces therefore go down together, come back together, and
are kept together under one key.

WHAT MAY BE KEPT is decided by what this server itself handed out, not by what
a caller claims. The endpoint feeding this store takes no credentials and is
reachable from outside, so a scope name in a request body is only a word. But
the questions do not come from the request either: they come from
/api/text/bbq-sample, which this server answers, and which calls admit() on
every string it serves. A piece nobody was ever given is not kept - so the
store holds benchmark text or nothing, whoever is posting.

This is not about anything a person writes. Nothing a person writes goes near
here: the store sits in the list branch of the translate endpoint, whose only
caller is Bias Archaeology; the pages carrying what people type use the
singular branch, which has no store at all.

The file lives under devserver/data, which .gitignore holds shut
(devserver/data/*.sqlite3*, the whole family - SQLite's companion files are
named after the journal mode it actually got); see the global rule on user data
and repositories.
"""

import hashlib
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence

import config

logger = logging.getLogger(__name__)

DATA_DIR = config.DEVSERVER_DATA_DIR
CACHE_FILE = DATA_DIR / "translation_cache.sqlite3"

# Public, fixed material only: "bbq" is the corpus behind Bias Archaeology,
# "winobias" the one behind Bias Archaeology 2. Nothing a person writes
# belongs in this set.
ALLOWED_SCOPES = frozenset({"bbq", "winobias"})

# Bumping this invalidates every row without touching a file. It belongs in the
# key because a stored translation is only as good as what produced it: change
# the interpreter prompt or the helper model, and what is on disk is an answer
# to a question no longer being asked. Without this the only way to clear a bad
# translation would be deleting the store.
CACHE_VERSION = "1"

# A question, not a document. BBQ's five pieces together run about 280
# characters, 420 at the ninetieth percentile. These bounds are what keeps the
# store from being usable as a place to park text.
MAX_ITEMS = 16
MAX_CHARS = 2000

# A ceiling on the file itself. The whole benchmark, every question in every
# language this platform speaks, comes to roughly half a gigabyte - and that is
# the case where every question has been read in every language, which will not
# happen. This endpoint takes no credentials, so the ceiling is what turns
# "grows until someone stops posting" into a bounded thing. One stat call.
MAX_BYTES = 2 * 1024 * 1024 * 1024

# One writer at a time, and one reader of the admitted set at a time. SQLite
# would serialise the file anyway; the lock keeps the schema statement from
# racing itself on the first two requests. No model call ever happens while it
# is held, and it is never acquired twice on one path.
_lock = threading.Lock()

# What this server has handed out, per scope, as piece hashes. A translation is
# only kept for material that went through here first, which is what makes the
# store's contents independent of who is posting to the endpoint. The set is
# lost on restart: a question served before the restart can still be READ back,
# it just cannot be written until it has been served again - which is what any
# page does before it asks for a translation.
_admitted: Dict[str, set] = {}

# Far above the 33,212 distinct pieces the whole benchmark holds, and admit()
# only ever sees what this server served, so this is a backstop, not a budget.
MAX_ADMITTED = 200_000


def _piece(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()[:16]


def admit(scope: str, pieces: Iterable[str]) -> None:
    """Note strings this server has served, so their translation may be kept."""
    if scope not in ALLOWED_SCOPES:
        return
    try:
        with _lock:
            known = _admitted.setdefault(scope, set())
            if len(known) > MAX_ADMITTED:
                known.clear()
                logger.info(f"[TRANSLATION-CACHE] admitted set for {scope} reset")
            for text in pieces:
                if isinstance(text, str) and text.strip():
                    known.add(_piece(text))
    except Exception as exc:
        logger.warning(f"[TRANSLATION-CACHE] could not admit: {exc}")


def _all_admitted(scope: str, texts: Sequence[str]) -> bool:
    with _lock:
        known = _admitted.get(scope) or set()
        return all(_piece(t) in known for t in texts)


# The table carries its schema generation in its name: CREATE TABLE IF NOT
# EXISTS does not alter an existing table, so a changed layout under the same
# name would leave every query failing quietly against the old one.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries_v1 (
    scope  TEXT NOT NULL,
    lang   TEXT NOT NULL,
    key    TEXT NOT NULL,
    src    TEXT NOT NULL,
    dst    TEXT NOT NULL,
    ts     TEXT NOT NULL,
    PRIMARY KEY (scope, lang, key)
)
"""


def _acceptable(texts: Sequence[str]) -> bool:
    """Whether this is the shape of thing this store exists for."""
    if not texts or len(texts) > MAX_ITEMS:
        return False
    total = 0
    for piece in texts:
        if not isinstance(piece, str) or not piece.strip():
            return False
        total += len(piece)
    return total <= MAX_CHARS


def _key(texts: Sequence[str]) -> str:
    # The unit separator cannot occur in the corpus, so no two different lists
    # can join into the same string.
    joined = CACHE_VERSION + "\x1f" + "\x1f".join(texts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_FILE, timeout=5.0)
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def lookup(scope: str, lang: str, texts: Sequence[str]) -> Optional[List[str]]:
    """The whole set of pieces as it was translated, or None.

    All or nothing on purpose: a half-answered question would be pieces from two
    different calls standing next to each other, which is the thing this store
    is keyed to avoid.

    A store that cannot be read costs a model call, never a translation. Every
    error here comes back as "nothing known".
    """
    if scope not in ALLOWED_SCOPES or not _acceptable(texts):
        return None
    conn = None
    try:
        with _lock:
            conn = _connect()
            row = conn.execute(
                "SELECT dst FROM entries_v1 WHERE scope=? AND lang=? AND key=?",
                (scope, lang, _key(texts)),
            ).fetchone()
        if not row or not row[0]:
            return None
        kept = json.loads(row[0])
        if isinstance(kept, list) and len(kept) == len(texts) \
                and all(isinstance(p, str) and p for p in kept):
            return kept
    except Exception as exc:
        logger.warning(f"[TRANSLATION-CACHE] could not read: {exc}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return None


def store(scope: str, lang: str, texts: Sequence[str], translated: Sequence[str]) -> None:
    """Keep a finished question, so it is only ever asked for once.

    Kept only if every piece was served by this server first; see admit().

    A set in which some piece came back unchanged is not kept. To the caller, a
    line the helper never returned and a line that needed no translation look
    exactly alike - both arrive as the original. Writing the first of those into
    a permanent store would freeze one missed line forever, so a set carrying
    any of them is let go and costs one more call next time.
    """
    if scope not in ALLOWED_SCOPES or not _acceptable(texts):
        return
    if len(translated) != len(texts):
        return
    if not _all_admitted(scope, texts):
        # Not material this server handed out. Whoever sent it, it is not kept.
        return
    try:
        if CACHE_FILE.exists() and CACHE_FILE.stat().st_size > MAX_BYTES:
            logger.warning("[TRANSLATION-CACHE] at its ceiling; keeping nothing further")
            return
    except Exception:
        pass
    for src, dst in zip(texts, translated):
        if not isinstance(dst, str) or not dst.strip() or dst == src:
            return
    conn = None
    try:
        with _lock:
            conn = _connect()
            conn.execute(
                "INSERT OR REPLACE INTO entries_v1 (scope, lang, key, src, dst, ts) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    scope, lang, _key(texts),
                    json.dumps(list(texts), ensure_ascii=False),
                    json.dumps(list(translated), ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning(f"[TRANSLATION-CACHE] could not write: {exc}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
