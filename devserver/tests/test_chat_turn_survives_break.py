#!/usr/bin/env python3
"""An apparatus outlives the sentence written about it.

Measured on 2026-09-07 in the backend journal: `run_canvas_graph` returned at
20:54:25 with a validated, expanded graph in hand, and at 20:54:33 the reply
stream was reset after 48 pieces. The turn raised, the closing `done` event
never went out, and the apparatus — finished work, already paid for — was
discarded with the half-written sentence. The room saw nothing.

Two decisions used to be one. Refusing a second model after pieces have gone out
is right for the TEXT: a fresh candidate would write a second answer underneath
half of a first one that a room has already read. It is wrong for what the
turn's TOOLS produced, which no second attempt improves.

Nothing here reaches a provider or a GPU: the chat helper is a stand-in, and
run_canvas_graph is decision-only — it validates and hands back a payload.

Run:  python3 -m pytest devserver/tests/test_chat_turn_survives_break.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import requests
from flask import Flask

from my_app.routes import chat_routes
from my_app.services.canvas_graph_authoring import RESONA_CANVAS_CONFIGS

CFG = sorted(RESONA_CANVAS_CONFIGS)[0]

GRAPH = {
    "nodes": [
        {"id": "i", "type": "input", "promptText": "ein Haus"},
        {"id": "g", "type": "generation", "configId": CFG},
    ],
    "connections": [{"sourceId": "i", "targetId": "g"}],
}

GRAPH_CALL = [{
    "id": "call_1",
    "type": "function",
    "function": {
        "name": "run_canvas_graph",
        "arguments": json.dumps({
            "title": "Perspektive gegen Rohtext",
            "motivation": "zwei Wege auf dasselbe Motiv",
            "graph": GRAPH,
        }),
    },
}]

RESONA_DATA = {
    "message": "bau uns einen kleinen Apparat",
    "context": {"resona_mode": True, "language": "de", "device_id": "test-device"},
}


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    with app.test_request_context("/api/chat", json={}):
        yield


def rounds(*plans):
    """A stand-in chat helper that plays the given rounds in order.

    Each plan is (tokens, result_or_exception): the tokens go out as pieces, and
    then either a result closes the round or the exception is raised mid-round —
    the shape of a provider whose connection is reset while it is writing.
    """
    state = {"i": 0}

    def helper(**kwargs):
        plan = plans[min(state["i"], len(plans) - 1)]
        state["i"] += 1
        toks, end = plan
        for t in toks:
            yield ("token", t)
        if isinstance(end, BaseException):
            raise end
        yield ("result", end)

    return helper


def answer(content, tool_calls=None):
    return {"content": content, "thinking": None, "tool_calls": tool_calls,
            "model_used": "stand-in/one"}


BROKEN = requests.exceptions.ChunkedEncodingError(
    "Connection broken: ConnectionResetError(104, 'Connection reset by peer')")


def events(monkeypatch, helper, data=None):
    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    return list(chat_routes._chat_events(dict(data or RESONA_DATA)))


def test_apparatus_travels_before_the_closing_sentence(app_ctx, monkeypatch):
    """The graph event goes out on the tool round, ahead of `done`."""
    evs = events(monkeypatch, rounds(
        ([], answer("", GRAPH_CALL)),
        (["Ich ", "habe ", "gebaut."], answer("Ich habe gebaut.")),
    ))
    kinds = [e["type"] for e in evs]
    assert "graph" in kinds, kinds
    assert kinds.index("graph") < kinds.index("done"), kinds

    built = [e["graph"] for e in evs if e["type"] == "graph"]
    assert len(built) == 1
    assert built[0]["title"] == "Perspektive gegen Rohtext"
    assert built[0]["workflow"]["nodes"], "the payload must be executor-ready"

    # It stays in the closing payload as well: the blocking mouth of this
    # endpoint reads nothing else, and a surface may have opened late.
    done = evs[-1]
    assert done["type"] == "done"
    assert [g["intent_id"] for g in done["generated_graphs"]] == [built[0]["intent_id"]]


def test_a_reset_closing_sentence_keeps_the_apparatus(app_ctx, monkeypatch):
    """The turn ends with `done`, holding the apparatus and the half sentence."""
    evs = events(monkeypatch, rounds(
        ([], answer("", GRAPH_CALL)),
        (["Ich habe zwei ", "Wege nebeneinand"], BROKEN),
    ))
    kinds = [e["type"] for e in evs]
    assert "error" not in kinds, kinds
    assert kinds[-1] == "done", kinds

    done = evs[-1]
    assert len(done["generated_graphs"]) == 1
    assert done["reply"] == "Ich habe zwei Wege nebeneinand"
    assert "Connection reset by peer" in (done["broke_off"] or "")


def test_a_round_that_wrote_nothing_still_fails_loudly(app_ctx, monkeypatch):
    """Only a round cut MID-ANSWER is swallowed. A round that wrote no piece is
    a failure with nothing standing in a room, and it keeps being raised."""
    evs = events(monkeypatch, rounds(([], BROKEN)))
    assert evs[-1]["type"] == "error"
    assert "Connection reset by peer" in evs[-1]["details"]


def test_a_later_failure_is_not_relabelled_by_earlier_success(app_ctx, monkeypatch):
    """A turn that built something keeps failing loudly when a LATER round fails.

    The guard reads this round's pieces, never the turn's built results. Reading
    the latter would swallow every failure after the first successful tool call —
    a content refusal among them, which reaches this handler unretriable and with
    candidates still left — and ship an empty reply the journal then refuses.
    """
    refused = Exception("content policy: the request was blocked")
    evs = events(monkeypatch, rounds(
        ([], answer("", GRAPH_CALL)),
        ([], refused),
    ))
    err = evs[-1]
    assert err["type"] == "error"
    assert "content policy" in err["details"]

    # And the apparatus built in the first round travels with the failure: it is
    # finished work, and losing it means having it built a second time.
    assert [g["title"] for g in err["generated_graphs"]] == ["Perspektive gegen Rohtext"]
    # It had already gone out on its own event, before anything failed.
    assert [e["type"] for e in evs].count("graph") == 1


def test_a_break_with_no_message_is_still_a_break(app_ctx, monkeypatch):
    """`broke_off` is a flag, and an exception whose str() is empty is still one.

    Read as a truthy value, an empty reason re-enters the normal path: the half
    sentence ships as the finished answer, and on Resona the evidence duty sends
    the cut draft back for a correction — a second answer written underneath half
    of a first one, which is the one thing the chain refuses to do.
    """
    evs = events(monkeypatch, rounds((["Ich habe zwei "], Exception())))
    done = evs[-1]
    assert done["type"] == "done"
    # The delivery filters run on the partial text as on any other reply.
    assert done["reply"].startswith("Ich habe zwei")
    assert done["broke_off"] == "Exception"


def test_a_whole_turn_says_it_did_not_break_off(app_ctx, monkeypatch):
    """broke_off travels on every turn, empty when the sentence was finished."""
    evs = events(monkeypatch, rounds((["fertig"], answer("fertig"))))
    assert evs[-1]["type"] == "done"
    assert evs[-1]["broke_off"] is None


def test_a_failure_with_nothing_built_carries_empty_hands(app_ctx, monkeypatch):
    """The three fields are always on the error event, empty when nothing was built."""
    def helper(**kwargs):
        raise RuntimeError("something else went wrong")
    evs = events(monkeypatch, helper)
    err = evs[-1]
    assert err["type"] == "error"
    assert err["generated_graphs"] == []
    assert err["generated_media"] == []
    assert err["generated_compositions"] == []
