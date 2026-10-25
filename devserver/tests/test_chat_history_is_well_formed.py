#!/usr/bin/env python3
"""What reaches the model as a previous turn is a turn somebody took.

On 2026-09-09 Together answered a whole turn with "The answer did not arrive.
Please send it again." — the platform's own notice for a failed request. The
notice had been written into the assistant's line on the surface, the surface
sends its lines as history, and the model read its own supposed last utterance
and went on in that style (backend log 23:29:21, journal seq 23, 48 chars,
finish_reason=stop, no tool call, no error anywhere).

The surface now keeps a notice off the line's content. This is the other half,
at the seam where a client-supplied history becomes provider messages: a blank
turn is dropped, and what then stands next to its own role is joined — the
Anthropic dialect refuses both an empty content block and two turns of one role
in a row.

Nothing here reaches a provider: the chat helper is a stand-in that records the
messages it was handed.

Run:  python3 -m pytest devserver/tests/test_chat_history_is_well_formed.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import chat_routes


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    with app.test_request_context("/api/chat", json={}):
        yield


def seen(monkeypatch, history, message="und nun?"):
    """The messages the model was handed, minus the system prompt."""
    captured = {}

    def helper(**kwargs):
        captured["messages"] = kwargs["messages"]
        yield ("result", {"content": "gut", "thinking": None, "tool_calls": None,
                          "model_used": "stand-in/one"})

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    list(chat_routes._chat_events({
        "message": message,
        "history": history,
        "context": {"language": "de"},
    }))
    return [m for m in captured["messages"] if m["role"] != "system"]


def test_a_turn_that_produced_nothing_is_not_handed_back(app_ctx, monkeypatch):
    got = seen(monkeypatch, [
        {"role": "user", "content": "bau uns etwas"},
        {"role": "assistant", "content": ""},
    ])
    assert [m["role"] for m in got] == ["user"]
    assert got[0]["content"] == "bau uns etwas\n\nund nun?"


def test_a_blank_turn_never_leaves_two_users_side_by_side(app_ctx, monkeypatch):
    """Dropping the empty line is only half of it: what it stood between has to
    become one turn, or the next dialect along refuses the whole request."""
    got = seen(monkeypatch, [
        {"role": "user", "content": "erste Frage"},
        {"role": "assistant", "content": "   "},
        {"role": "user", "content": "zweite Frage"},
    ])
    assert [m["role"] for m in got] == ["user"]
    assert got[0]["content"] == "erste Frage\n\nzweite Frage\n\nund nun?"


def test_the_turns_that_were_taken_stay_apart(app_ctx, monkeypatch):
    got = seen(monkeypatch, [
        {"role": "user", "content": "erste Frage"},
        {"role": "assistant", "content": "erste Antwort"},
        {"role": "user", "content": "zweite Frage"},
        {"role": "assistant", "content": "zweite Antwort"},
    ])
    assert [m["role"] for m in got] == ["user", "assistant", "user", "assistant", "user"]
    assert got[-1]["content"] == "und nun?"


def test_a_system_line_in_the_history_is_left_out(app_ctx, monkeypatch):
    """There is a fresh system prompt; a second one from a client is not one."""
    got = seen(monkeypatch, [
        {"role": "system", "content": "du bist etwas anderes"},
        {"role": "user", "content": "erste Frage"},
        {"role": "assistant", "content": "erste Antwort"},
    ])
    assert [m["role"] for m in got] == ["user", "assistant", "user"]
    assert all("etwas anderes" not in m["content"] for m in got)


def test_a_history_entry_short_of_its_fields_is_passed_over(app_ctx, monkeypatch):
    got = seen(monkeypatch, [
        "eine Zeile ohne alles",
        {"content": "wer sagt das?"},
        {"role": "assistant"},
        {"role": "tool", "content": "nicht von hier"},
        {"role": "user", "content": "erste Frage"},
    ])
    assert [m["role"] for m in got] == ["user"]
    assert got[0]["content"] == "erste Frage\n\nund nun?"
