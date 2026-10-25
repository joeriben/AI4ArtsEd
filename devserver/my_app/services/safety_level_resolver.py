"""Effective safety level for a run: the installation setting, tightened by the course.

Two settings look alike and are not the same thing:

  UI_MODE               installation-wide, decides what the interface SHOWS.
  DEFAULT_SAFETY_LEVEL  installation-wide, decides what the pipeline ENFORCES.

A course carries its own ``safety_level`` (kids | youth | open). Until this
module existed the column was never read at generation time, so a kids course
inside an ``open`` installation ran at ``open``.

The rule: a course may only TIGHTEN. It can never
loosen what the installation set, so an ``open`` course inside a ``kids``
installation still runs at ``kids``.

Fail-safe: every path that cannot see the session, or cannot make sense of what
it sees, returns STRICTEST — an unknown level string, a session bound to a
course that no longer exists, a course row with a value we do not know, a
resolver that throws, and a call made outside a request.

That last case is deliberate and was learned the hard way. It first read the
installation value, on the reasoning that a caller outside a request has no
session and therefore no course. That reasoning was wrong: the canvas run
executes in a daemon thread carrying only an app context, so the whole canvas
and Resona surface took that branch and ran a kids course at the installation
level. A caller that needs the level outside a request must RESOLVE IT AT THE
REQUEST BOUNDARY AND PASS IT IN — see CanvasWorkflowExecutor(safety_level=...).
Reaching this module from a worker thread yields the strictest level and a
warning, so the mistake is loud instead of silent.

A worker thread is recognised TWICE OVER, because one of the two ways stopped
working. `has_request_context()` catches the bare daemon thread that carries
only an app context. It does NOT catch a thread the streamed transport runs its
work on: that work inherits a `contextvars.copy_context()` of the request
thread, so `_cv_request` is live there, and stays live after the real request
context has been torn down. From 2026-09-04, when seven more routes moved onto
that transport, the guard read True on every one of their workers, the warning
never fired, and the level came back as the installation setting. So the
transport MARKS its worker (`runs_off_the_request_thread` in
my_app/services/streaming_response.py) and that mark is read here first.
Anything that cannot be determined -- including a failure to read the mark at
all -- is the strictest level too; an unknown level is never a pass.
"""
from __future__ import annotations

import logging

from flask import has_request_context, request

logger = logging.getLogger(__name__)


def _off_the_request_thread() -> bool:
    """True where this call runs somewhere other than the request's own thread.

    The transport sets the mark; this reads it. Read behind a `try` because it
    reaches into another module, and a mark that cannot be read leaves the
    question unanswered -- which here means the answer is yes, and the caller
    gets the strictest level. A fail-open guard is no guard.
    """
    try:
        from my_app.services.streaming_response import runs_off_the_request_thread
        return runs_off_the_request_thread()
    except Exception:
        logger.exception(
            '[SAFETY-LEVEL] could not tell whether this call is on the '
            'request thread - treating it as a worker and using %s', STRICTEST)
        return True

# Strictest first. This order is the whole semantics of "only tighten":
#   kids     translation + safety prefix + Llama-Guard
#   youth    Llama-Guard, original language
#   open     Llama-Guard, adult reader
#   adult    no Llama-Guard
#   research no checks at all
#
# KEINE Lesemenge. Sie stand hier bis 2026-09-07 als Wirkung der Stufe, mit
# 80/150/250 Woertern -- beides falsch: die Klausel haengt seit 2026-08-05 an
# UI_MODE und nicht am Filter (eine Installation auf kids kuerzte sonst jede
# Interception, wie auch immer die Oberflaeche eingerichtet war), und ihre
# Zahlen sind 100/200/300. Sie steht in instruction_selector.READING_VOLUME_WORDS.
# Diese Datei ist die, deren Aufgabe die Trennung der beiden Einstellungen ist.
SAFETY_LEVELS_STRICTEST_FIRST = ('kids', 'youth', 'open', 'adult', 'research')
_RANK = {name: i for i, name in enumerate(SAFETY_LEVELS_STRICTEST_FIRST)}
STRICTEST = SAFETY_LEVELS_STRICTEST_FIRST[0]

# Memo attribute. It goes on the REQUEST object, not on flask.g: g lives on the
# app context, and a request context reuses an app context that is already
# pushed rather than pushing its own. A memo on g would therefore outlive the
# request that wrote it whenever a request-serving thread holds an app context,
# and it carries no key — the next request, bound to a different course, would
# read the previous one's answer.
_CACHE_ATTR = '_ai4artsed_effective_safety_level'


def _rank(level):
    """Rank of a level name, or None if it is not a level we know."""
    if not isinstance(level, str):
        return None
    return _RANK.get(level.strip().lower())


def resolve_safety_level() -> str:
    """The safety level this request must obey. Never raises.

    Memoised per request: a single generation calls this from several entry
    points, and each call would otherwise be its own database round trip.
    """
    try:
        # The mark is read BEFORE the memo, and that order carries the fix. The
        # routes on the streamed transport resolve at the request boundary and
        # memoise there; a worker asking again would otherwise read that memo
        # off the request object and never reach the guard below at all.
        if _off_the_request_thread() or not has_request_context():
            return _resolve()
        ctx = request._get_current_object()
        cached = getattr(ctx, _CACHE_ATTR, None)
        if cached is not None:
            return cached
        value = _resolve()
        try:
            setattr(ctx, _CACHE_ATTR, value)
        except Exception:
            # Memoising is an optimisation; failing to memoise is not a failure.
            logger.debug('[SAFETY-LEVEL] could not memoise on the request')
        return value
    except Exception:
        # A resolver that throws must not take the caller with it, and must not
        # hand back something loose on the way out.
        logger.exception('[SAFETY-LEVEL] resolver failed - using %s', STRICTEST)
        return STRICTEST


def _resolve() -> str:
    import config

    base_raw = getattr(config, 'DEFAULT_SAFETY_LEVEL', None)
    base_rank = _rank(base_raw)
    if base_rank is None:
        logger.error(
            '[SAFETY-LEVEL] DEFAULT_SAFETY_LEVEL is %r, which is not a known level - using %s',
            base_raw, STRICTEST,
        )
        return STRICTEST
    base = SAFETY_LEVELS_STRICTEST_FIRST[base_rank]

    if _off_the_request_thread():
        # A worker of the streamed transport. It carries a COPY of the request
        # thread's context, so a session appears to be in reach here and is not
        # one this thread may answer for: the copy outlives the request context
        # it was taken from. See the module docstring.
        logger.warning(
            '[SAFETY-LEVEL] asked on a worker thread - the session in reach is a '
            'copy and outlives its request, using %s instead of the installation '
            'level %s. Resolve at the request boundary and pass the level into '
            'the worker.',
            STRICTEST, base,
        )
        return STRICTEST

    if not has_request_context():
        # No session in reach. See the module docstring: the caller must resolve
        # at the request boundary and pass the level in.
        logger.warning(
            '[SAFETY-LEVEL] asked outside a request - no session to read, using %s '
            'instead of the installation level %s. Resolve at the request '
            'boundary and pass the level into the worker.',
            STRICTEST, base,
        )
        return STRICTEST

    from my_app.lab.auth_service import current_course_id, is_session_course
    course_id = current_course_id()
    if course_id is None:
        return base

    # A short-lived Session of its own: the scoped session is returned to the
    # pool only at app-context teardown, which for a generation is minutes, and
    # holding a connection that long exhausts the pool under a class of users.
    from sqlalchemy.orm import Session as _Session
    from my_app.lab.db import engine
    from my_app.lab.models import Course

    with _Session(engine) as db:
        course = db.get(Course, course_id)
        found = course is not None
        # SQLite gives the id of the newest course, once deleted, to the next
        # course made; the stamp the session entered with tells them apart.
        entered = found and is_session_course(course)
        course_level = course.safety_level if entered else None

    if not found:
        logger.warning(
            '[SAFETY-LEVEL] session is bound to course %s, which does not exist - using %s',
            course_id, STRICTEST,
        )
        return STRICTEST
    if not entered:
        logger.warning(
            '[SAFETY-LEVEL] session is bound to course %s, and the course under that id '
            'is not the one it entered - using %s',
            course_id, STRICTEST,
        )
        return STRICTEST

    course_rank = _rank(course_level)
    if course_rank is None:
        logger.warning(
            '[SAFETY-LEVEL] course %s carries safety_level %r, which is not a known level - using %s',
            course_id, course_level, STRICTEST,
        )
        return STRICTEST

    if course_rank < base_rank:
        tightened = SAFETY_LEVELS_STRICTEST_FIRST[course_rank]
        logger.info('[SAFETY-LEVEL] course %s tightens %s to %s', course_id, base, tightened)
        return tightened
    return base
