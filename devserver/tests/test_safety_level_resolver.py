"""
The effective safety level: installation setting, tightened by the active course.

Two rules are under test, and they are the whole contract:

  ONLY TIGHTEN  a course may lower the level, never raise it. An 'open' course
                inside a 'kids' installation still runs at 'kids'.
  FAIL-SAFE     every uncertain path lands on the STRICTEST level, not on the
                looser installation value. Unknown level strings, a session
                bound to a course that no longer exists, a resolver that throws
                — all of them return 'kids'.

Background: until 2026-08-07 the course column was never read at generation
time (my_app/routes/schema_pipeline_routes.py assigned config.DEFAULT_SAFETY_LEVEL
directly at eleven places), so a kids course inside an 'open' installation ran
at 'open'. The policy guard at the bottom keeps that from coming back.

Run: python3 -m pytest devserver/tests/test_safety_level_resolver.py -q
"""

import logging
import os
import re
import sys
import tempfile
import threading
from pathlib import Path

# devserver/tests/... -> parents[1] == devserver/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# A throwaway DB, bound before my_app.lab.db is imported anywhere.
os.environ['AI4ARTSED_DB_PATH'] = str(Path(tempfile.mkdtemp()) / 'lab_test.db')

import pytest
from flask import Flask

import config
from my_app.lab.db import Base, engine, SessionLocal
from my_app.lab.models import Course
from my_app.lab.place_codes import course_stamp
from my_app.services.safety_level_resolver import (
    STRICTEST,
    SAFETY_LEVELS_STRICTEST_FIRST,
    resolve_safety_level,
)

from file_modules import DEVSERVER


@pytest.fixture(scope='module')
def app():
    Base.metadata.create_all(engine)
    a = Flask(__name__)
    a.secret_key = 'test-only'
    return a


def _course(level, name='c'):
    """Insert a course carrying  and return its id. Bypasses the API on
    purpose: the point is what the resolver does with whatever is in the row,
    including values the API would reject."""
    db = SessionLocal()
    c = Course(name=name, safety_level=level)
    db.add(c)
    db.commit()
    cid = c.id
    return cid


_ENTERED = object()


def _resolve(app, base, course_id=None, stamp=_ENTERED):
    """The level of a request whose session is bound to `course_id`. `stamp`
    is what the session remembers of that course: by default what login_place
    writes (place_codes.course_stamp), None for nothing at all."""
    original = config.DEFAULT_SAFETY_LEVEL
    config.DEFAULT_SAFETY_LEVEL = base
    try:
        with app.test_request_context('/'):
            if course_id is not None:
                from flask import session
                session['course_id'] = course_id
                if stamp is _ENTERED:
                    course = SessionLocal().get(Course, course_id)
                    if course is not None:
                        session['course_stamp'] = course_stamp(course)
                elif stamp is not None:
                    session['course_stamp'] = stamp
            return resolve_safety_level()
    finally:
        config.DEFAULT_SAFETY_LEVEL = original


# --------------------------------------------------------------- only tighten
def test_no_course_uses_the_installation_setting(app):
    assert _resolve(app, 'open') == 'open'


def test_course_tightens(app):
    cid = _course('kids', 'tighten')
    assert _resolve(app, 'open', cid) == 'kids'


def test_course_may_not_loosen(app):
    cid = _course('open', 'loosen')
    assert _resolve(app, 'kids', cid) == 'kids'


def test_equal_levels_stay(app):
    cid = _course('youth', 'equal')
    assert _resolve(app, 'youth', cid) == 'youth'


def test_research_installation_is_tightened_by_a_course(app):
    """The most consequential case: 'research' skips every safety check. A kids
    course inside such an installation must not inherit that."""
    cid = _course('kids', 'research_host')
    assert _resolve(app, 'research', cid) == 'kids'


def test_every_pair_only_tightens(app):
    """Exhaustive over the level vocabulary: the result is never looser than
    either input, and never stricter than the stricter of the two."""
    rank = {n: i for i, n in enumerate(SAFETY_LEVELS_STRICTEST_FIRST)}
    for i, base in enumerate(SAFETY_LEVELS_STRICTEST_FIRST):
        for course_level in ('kids', 'youth', 'open'):
            cid = _course(course_level, f'pair{i}{course_level}')
            got = _resolve(app, base, cid)
            assert rank[got] == min(rank[base], rank[course_level]), (base, course_level, got)


# ----------------------------------------------------------------- fail-safe
def test_unknown_installation_level_is_strictest(app):
    assert _resolve(app, 'wide-open') == STRICTEST


def test_empty_installation_level_is_strictest(app):
    assert _resolve(app, '') == STRICTEST


def test_none_installation_level_is_strictest(app):
    assert _resolve(app, None) == STRICTEST


def test_session_bound_to_a_missing_course_is_strictest(app):
    assert _resolve(app, 'open', 999999) == STRICTEST


def test_a_course_made_under_the_id_of_the_session_course_is_strictest(app):
    """SQLite gives the id of the newest course, once deleted, to the next
    course made. The session remembers the moment the course it entered was
    made, and this course was made at another."""
    cid = _course('open', 'reused')
    assert _resolve(app, 'open', cid, stamp='2026-01-01T00:00:00+00:00') == STRICTEST


def test_a_session_course_without_a_stamp_is_strictest(app):
    """A participant session from before the places remembers no course."""
    cid = _course('open', 'unstamped')
    assert _resolve(app, 'open', cid, stamp=None) == STRICTEST


def test_course_with_an_unknown_level_is_strictest(app):
    cid = _course('erwachsene', 'badlevel')
    assert _resolve(app, 'open', cid) == STRICTEST


def test_a_throwing_resolver_is_strictest(app, monkeypatch):
    import my_app.services.safety_level_resolver as mod
    monkeypatch.setattr(mod, '_resolve', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    with app.test_request_context('/'):
        assert mod.resolve_safety_level() == STRICTEST


def test_outside_a_request_is_strictest():
    """Learned the hard way. This branch first returned the installation value,
    on the reasoning that a caller with no session has no course. But the canvas
    run executes in a daemon thread carrying only an app context, so the whole
    canvas and Resona surface took this branch and ran a kids course at the
    installation level (measured: 'research', i.e. no checks at all). A caller
    that needs the level outside a request must resolve it at the request
    boundary and pass it in."""
    original = config.DEFAULT_SAFETY_LEVEL
    config.DEFAULT_SAFETY_LEVEL = 'research'
    try:
        assert resolve_safety_level() == STRICTEST
    finally:
        config.DEFAULT_SAFETY_LEVEL = original


def test_the_level_is_resolved_once_per_request(app, monkeypatch):
    """A single generation asks from several entry points; each ask would
    otherwise be its own database round trip."""
    import my_app.services.safety_level_resolver as mod
    calls = []
    monkeypatch.setattr(mod, '_resolve', lambda: (calls.append(1), 'youth')[1])
    with app.test_request_context('/'):
        assert [mod.resolve_safety_level() for _ in range(5)] == ['youth'] * 5
    assert len(calls) == 1
    with app.test_request_context('/'):
        mod.resolve_safety_level()
    assert len(calls) == 2, 'the memo must not survive into the next request'


# --------------------------------------------- threads that are not the request

def test_a_bare_worker_thread_with_only_an_app_context_is_strictest(app):
    """The canvas run's shape: a daemon thread carrying an app context and no
    request. It has always been caught by `has_request_context()`, and it has to
    stay caught -- the mark the streamed transport sets is an ADDITION to this
    guard, never a replacement for it."""
    original = config.DEFAULT_SAFETY_LEVEL
    config.DEFAULT_SAFETY_LEVEL = 'open'
    answered = {}
    try:
        def run():
            with app.app_context():
                answered['level'] = resolve_safety_level()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(10.0)
    finally:
        config.DEFAULT_SAFETY_LEVEL = original

    assert answered['level'] == STRICTEST


def test_the_streamed_transports_worker_is_strictest(app, caplog):
    """The guard the shared transport disarmed, driven through the REAL loop.

    `streamed_answer` runs its work on a thread under a
    `contextvars.copy_context()` of the request thread, and that copy carries a
    live `_cv_request`. So from 2026-09-04 `has_request_context()` answered True
    on every one of those workers: the fail-safe branch was never entered, no
    warning was written, and the level came back as the installation setting --
    measured with DEFAULT_SAFETY_LEVEL='open' and no course pinned, `open` where
    the module's own text promised `kids`.

    Driven through `streamed_answer` and not through a thread built here on
    purpose: a hand-built thread is a claim about what the transport does, and
    this is the transport.

    The boundary resolve is part of the shape, not decoration. Every route on
    this transport resolves at the boundary and the resolver memoises there, so
    a worker asking again reads that memo off the request object -- and a guard
    that stands after the memo would never be reached at all.
    """
    from my_app.services.streaming_response import streamed_answer

    original = config.DEFAULT_SAFETY_LEVEL
    config.DEFAULT_SAFETY_LEVEL = 'open'
    answered = {}
    try:
        def work():
            answered['worker'] = resolve_safety_level()
            return {'ok': True}, 200

        with caplog.at_level(logging.WARNING,
                             logger='my_app.services.safety_level_resolver'):
            with app.test_request_context('/'):
                answered['boundary'] = resolve_safety_level()
                list(streamed_answer(work, label='SAFETY-LEVEL-TEST',
                                     interval=0.05))
    finally:
        config.DEFAULT_SAFETY_LEVEL = original

    assert answered['boundary'] == 'open', 'the request thread reads the session'
    assert answered['worker'] == STRICTEST, (
        'the worker read the installation level where it owes the strictest one')
    assert any('worker thread' in r.getMessage() for r in caplog.records), \
        'the mistake has to be loud: no warning was written'


def test_a_mark_that_cannot_be_read_is_strictest(app, monkeypatch):
    """The guard reaches into another module to ask which thread it is on. A
    question that cannot be answered is not a pass: it is the strictest level,
    like every other uncertainty here."""
    import my_app.services.streaming_response as transport

    def unreadable():
        raise RuntimeError('the mark could not be read')

    monkeypatch.setattr(transport, 'runs_off_the_request_thread', unreadable)
    assert _resolve(app, 'open') == STRICTEST


# ------------------------------------------------- the canvas worker thread
def _executor(**kw):
    from my_app.services.canvas_executor import CanvasWorkflowExecutor
    return CanvasWorkflowExecutor(
        nodes=[], connections=[], recorder=None, run_id='r', engine=None, **kw
    )


def test_canvas_executor_defaults_to_strictest():
    """An executor nobody told the level runs at the strictest one."""
    assert _executor().safety_level == STRICTEST


def test_canvas_executor_uses_the_level_it_was_handed():
    assert _executor(safety_level='youth').safety_level == 'youth'


def test_worker_thread_modules_never_resolve_the_level_themselves():
    """The canvas run executes in a daemon thread with only an app context
    (canvas_run_service._worker). Resolving there cannot see the session, so the
    level must be resolved at the request boundary and handed in."""
    for rel in ('my_app/services/canvas_executor.py',
                'my_app/services/canvas_run_service.py'):
        text = (DEVSERVER / rel).read_text(encoding='utf-8')
        assert 'resolve_safety_level()' not in text, (
            f'{rel} resolves the level in a worker thread; hand it in instead'
        )


def test_level_names_are_case_and_space_tolerant(app):
    cid = _course('  KIDS  ', 'sloppy')
    assert _resolve(app, 'open', cid) == 'kids'


# --------------------------------------------------------------- policy guard
# Files that may read the raw installation setting, with the reason.
RAW_SETTING_ALLOWED = {
    # The admin surface shows and writes the setting itself.
    'my_app/routes/settings_routes.py',
    # The resolver IS the reader.
    'my_app/services/safety_level_resolver.py',
}


def test_no_route_or_service_reads_the_raw_setting():
    """Regression guard, deliberately NOT a hand-written file list — a list of
    the files the author happened to edit can only confirm the author.

    Reading config.DEFAULT_SAFETY_LEVEL outside the allowlist is the bug this
    module fixed: it ignores the course the session is bound to."""
    pattern = re.compile(r'\bDEFAULT_SAFETY_LEVEL\b')
    offenders = []
    for folder in ('my_app/routes', 'my_app/services'):
        for path in sorted((DEVSERVER / folder).glob('*.py')):
            rel = f'{folder}/{path.name}'
            if rel in RAW_SETTING_ALLOWED:
                continue
            for i, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                code = line.split('#', 1)[0]
                if pattern.search(code):
                    offenders.append(f'{rel}:{i}: {line.strip()}')
    assert not offenders, 'use resolve_safety_level() instead:\n' + '\n'.join(offenders)
