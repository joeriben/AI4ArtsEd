"""The wait a provider names, and what happened while nobody read it.

Every service in `_OPENAI_STYLE_PROVIDERS` and `_ANTHROPIC_STYLE_PROVIDERS`
sends `Retry-After` on 429 and 503. Until 2026-09-09 the header appeared
nowhere on this platform: the reader doubled from one second, gave up about
four seconds after the first 429 whatever number the provider had named, and
left as `API Error: 429`. `is_retriable_llm_error` classes that as
availability, so the chain fell through to a DIFFERENT model -- the provenance
harm this module's own comment gives as the reason for having no read timeout.

RFC 9110 allows two forms and providers use both.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from my_app.services.openai_style_stream import (
    _RETRY_AFTER_CEILING, _retry_after_seconds,
)


class _Response:
    def __init__(self, **headers):
        self.headers = headers


# --------------------------------------------------------------------------
# Reading the header
# --------------------------------------------------------------------------

def test_a_count_of_seconds_is_read():
    assert _retry_after_seconds(_Response(**{"Retry-After": "30"})) == 30.0


def test_a_fractional_count_is_read():
    assert _retry_after_seconds(_Response(**{"Retry-After": "1.5"})) == 1.5


def test_surrounding_space_does_not_matter():
    assert _retry_after_seconds(_Response(**{"Retry-After": "  12 "})) == 12.0


def test_an_http_date_is_read_as_the_distance_to_it():
    when = datetime.now(timezone.utc) + timedelta(seconds=45)
    stamp = when.strftime("%a, %d %b %Y %H:%M:%S GMT")
    named = _retry_after_seconds(_Response(**{"Retry-After": stamp}))
    assert named is not None
    assert 40 <= named <= 50


def test_a_date_in_the_past_is_no_wait_at_all():
    when = datetime.now(timezone.utc) - timedelta(hours=1)
    stamp = when.strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert _retry_after_seconds(_Response(**{"Retry-After": stamp})) == 0.0


def test_no_header_means_the_provider_named_nothing():
    assert _retry_after_seconds(_Response()) is None


def test_an_unreadable_header_is_not_taken_for_a_number():
    """`None` falls back to the doubling; a wrong number would be worse."""
    assert _retry_after_seconds(_Response(**{"Retry-After": "soon"})) is None
    assert _retry_after_seconds(_Response(**{"Retry-After": ""})) is None


def test_a_negative_count_does_not_become_a_negative_sleep():
    assert _retry_after_seconds(_Response(**{"Retry-After": "-5"})) == 0.0


# --------------------------------------------------------------------------
# The ceiling is ours
# --------------------------------------------------------------------------

def test_the_ceiling_covers_an_ordinary_rate_limit_window():
    """60s is the commonest value there is; it must be waited out, not skipped."""
    assert _RETRY_AFTER_CEILING >= 60


def test_the_ceiling_is_not_an_hour():
    """A room in silence is worse than an answer that says what happened."""
    assert _RETRY_AFTER_CEILING <= 300


def test_the_loop_prefers_the_named_wait_over_the_doubling():
    import inspect

    from my_app.services import openai_style_stream as S
    src = inspect.getsource(S)
    assert "named = _retry_after_seconds(response)" in src
    assert "wait = named if named is not None else" in src, \
        "the doubling must be the fallback, not the rule"
