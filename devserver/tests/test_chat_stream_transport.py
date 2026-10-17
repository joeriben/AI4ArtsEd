#!/usr/bin/env python3
"""What /api/chat/stream and the chat helper's fallback chain must keep doing.

Two failures this file holds shut, both measured on 2026-09-04:

  * The stream had no heartbeat. Its first byte WAS the model's first token, and
    the two moved one for one — a provider that stayed silent for 130 s produced
    a first byte at 130.01 s and would have gone on. The tunnel in front of this
    server ends a proxied request whose origin has been silent for about a
    hundred seconds and hands the browser an HTTP 524, and seven surfaces read
    this endpoint precisely to escape that.

  * The blocking chat helper asked again after a provider broke off mid-answer,
    because `requests.exceptions.ChunkedEncodingError` carries the word
    "connection" in its text and the availability list matched it. One question
    cost 3 requests and 1200 generated tokens.

Nothing here reaches a provider: the only transport is a stand-in, and its
address points at a port nothing listens on.

Run:  python3 -m pytest devserver/tests/test_chat_stream_transport.py -q
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import requests
import urllib3
from flask import Flask

from my_app.routes import chat_routes
from my_app.services import openai_style_stream as oss
from my_app.services.streaming_response import events_with_heartbeat

# Not real model ids. The platform holds no knowledge about any particular
# model, so a test that named one would pin the very thing that was removed.
STAND_INS = ["mistral/stand-in-one", "ionos/stand-in-two", "mammouth/stand-in-three"]

DONE = {"type": "done", "reply": "fertig", "thinking": None, "context_used": False,
        "run_id": None, "generated_media": [], "generated_graphs": [],
        "generated_compositions": [], "evidence_violations": []}


def frames_of(body: str) -> list:
    """The frames on the wire, in order, as (kind, payload).

    kind is 'comment' for a line the SSE spec calls a comment — which every
    reader on this platform drops — and 'event' for a `data:` frame.
    """
    out = []
    for raw in body.split("\n\n"):
        if not raw.strip():
            continue
        if raw.startswith("data:"):
            out.append(("event", json.loads(raw[len("data:"):].strip())))
        else:
            out.append(("comment", raw))
    return out


def drain(response, deadline=30.0):
    """Read a streamed Flask response, keeping the arrival time of every write."""
    arrivals = []
    started = time.time()
    body = ""
    for chunk in response.response:
        if not chunk:
            continue
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        arrivals.append((time.time() - started, text))
        body += text
        assert time.time() - started < deadline, "the stream did not end"
    return arrivals, body


def sse(ev) -> str:
    return "data: " + json.dumps(ev) + "\n\n"


@pytest.fixture()
def app():
    a = Flask(__name__)
    a.register_blueprint(chat_routes.chat_bp)
    return a


# ---------------------------------------------------------------------------
# 1. The stream breathes
# ---------------------------------------------------------------------------

def test_the_first_frame_goes_out_before_the_work_has_said_anything():
    """A byte from the start, not from the model's first token."""
    def silent():
        time.sleep(0.4)
        yield DONE

    started = time.time()
    frames = events_with_heartbeat(silent(), label="TEST", frame=sse, interval=0.05)
    first = next(frames)
    assert time.time() - started < 0.2
    assert first == ": heartbeat\n\n"
    list(frames)


def test_a_silent_stretch_never_grows_past_the_cadence():
    """The gap between two writes stays at the cadence, however long the work
    takes to say its first word. That is the whole point: the edge cuts at about
    a hundred seconds of silence and nothing here may approach it."""
    def silent():
        time.sleep(0.6)
        yield {"type": "token", "text": "at last"}

    gaps = []
    last = time.time()
    for _ in events_with_heartbeat(silent(), label="TEST", frame=sse, interval=0.1):
        now = time.time()
        gaps.append(now - last)
        last = now
    assert max(gaps) < 0.3, gaps
    assert len(gaps) >= 5


def test_the_heartbeat_carries_no_payload_and_so_reaches_no_consumer():
    """An SSE comment is not an event.

    Every surface on this endpoint reads it through `parseFrame` in
    lib/sseStream.ts, which drops a frame carrying no `data:` payload — see
    "passes over the heartbeat comment" in lib/__tests__/sseStream.spec.ts. What
    is asserted HERE is the other half of that contract: that what this server
    writes between the events really is such a frame.
    """
    def silent():
        time.sleep(0.3)
        yield DONE

    body = "".join(events_with_heartbeat(silent(), label="TEST", frame=sse, interval=0.05))
    read = frames_of(body)
    assert [k for k, _ in read].count("comment") >= 3
    for kind, payload in read:
        if kind == "comment":
            assert payload.startswith(":")
            assert "data:" not in payload
    assert [p for k, p in read if k == "event"] == [DONE]


def test_the_chat_stream_writes_while_the_turn_is_silent(app, monkeypatch):
    """The route itself, at its own cadence, against a turn that says nothing
    for longer than that cadence."""
    def silent_turn(data):
        time.sleep(2.5)
        yield {"type": "token", "text": "hi"}
        yield DONE

    monkeypatch.setattr(chat_routes, "_chat_events", silent_turn)
    with app.test_request_context("/api/chat/stream", json={"message": "x"}):
        arrivals, body = drain(chat_routes.chat_stream())

    assert arrivals[0][0] < 0.5, "the first byte waited for the turn"
    gaps = [arrivals[i][0] - arrivals[i - 1][0] for i in range(1, len(arrivals))]
    assert max(gaps) < 2.5, gaps
    assert [p["type"] for k, p in frames_of(body) if k == "event"] == ["token", "done"]


# ---------------------------------------------------------------------------
# 2. …and changes nothing else
# ---------------------------------------------------------------------------

def test_all_five_event_types_arrive_unchanged_and_in_order(app, monkeypatch):
    """token, discard, withdraw, done, error — payload for payload."""
    events = [
        {"type": "token", "text": "ein Satz mit Ümlaut"},
        {"type": "discard"},
        {"type": "withdraw", "text": "der gestrichene Entwurf"},
        {**DONE, "context_used": True, "run_id": "r1",
         "generated_media": [{"intent_id": "i1"}]},
        {"type": "error", "error": "Internal server error", "details": "why", "status": 500},
    ]
    monkeypatch.setattr(chat_routes, "_chat_events", lambda data: iter(events))

    with app.test_request_context("/api/chat/stream", json={"message": "x"}):
        _, body = drain(chat_routes.chat_stream())

    assert [p for k, p in frames_of(body) if k == "event"] == events
    # Not escaped away: the working language of this platform is German.
    assert "Ümlaut" in body


def test_a_turn_that_raises_still_ends_as_an_error_event_after_what_it_wrote(app, monkeypatch):
    """The failure travels inside the stream, because the status line has long
    gone — and everything the turn produced before it goes out first."""
    def turn(data):
        yield {"type": "token", "text": "half a sentence"}
        raise RuntimeError("the turn fell over")

    monkeypatch.setattr(chat_routes, "_chat_events", turn)
    with app.test_request_context("/api/chat/stream", json={"message": "x"}):
        _, body = drain(chat_routes.chat_stream())

    payloads = [p for k, p in frames_of(body) if k == "event"]
    assert payloads[0] == {"type": "token", "text": "half a sentence"}
    assert payloads[-1]["type"] == "error"
    assert "the turn fell over" in payloads[-1]["details"]


def test_the_blocking_endpoint_still_drains_the_same_turn(app, monkeypatch):
    """POST /api/chat is unchanged: it eats the same generator and answers with
    the closing payload, minus the marker only the stream needs."""
    monkeypatch.setattr(chat_routes, "_chat_events",
                        lambda data: iter([{"type": "token", "text": "f"}, DONE]))
    with app.test_request_context("/api/chat", json={"message": "x"}):
        response = chat_routes.chat()

    assert json.loads(response.get_data(as_text=True)) == \
        {k: v for k, v in DONE.items() if k != "type"}


def test_the_turn_still_stands_in_the_request_that_started_it(app, monkeypatch):
    """The turn runs on a thread of its own now, and the request it belongs to
    travels with it.

    `events_with_heartbeat` hands the worker a `contextvars.copy_context()` of
    the request's own context, which is how `streamed_answer` carries a route
    with one result onto its thread. Without it, anything the turn reaches for
    through Flask — and the storage it opens through the app context — would
    simply be gone, and it would be gone silently.
    """
    from flask import request as flask_request

    def turn(data):
        yield {"type": "token", "text": flask_request.path}
        yield {**DONE, "reply": flask_request.json["message"]}

    monkeypatch.setattr(chat_routes, "_chat_events", turn)
    with app.test_request_context("/api/chat/stream", json={"message": "from the request"}):
        _, body = drain(chat_routes.chat_stream())

    payloads = [p for k, p in frames_of(body) if k == "event"]
    assert payloads[0] == {"type": "token", "text": "/api/chat/stream"}
    assert payloads[-1]["reply"] == "from the request"


# ---------------------------------------------------------------------------
# 3. One question, one bill
# ---------------------------------------------------------------------------

def broken_stream_error():
    """What requests raises when a response body stops arriving mid-answer."""
    return requests.exceptions.ChunkedEncodingError(
        urllib3.exceptions.ProtocolError(
            "Connection broken: IncompleteRead(0 bytes read)"))


def test_a_broken_stream_is_not_an_availability_failure():
    assert chat_routes.is_retriable_llm_error(broken_stream_error()) is False


def test_everything_that_fails_before_the_answer_still_falls_through():
    """The availability list is untouched, and the new line is drawn by TYPE: a
    host that cannot be reached raises a SIBLING of the broken-stream error, not
    a subclass of it, so it keeps falling through.

    The message used here is the name-lookup failure. A host that refuses the
    connection is the case just below, which had its own reason to be wrong."""
    assert chat_routes.is_retriable_llm_error(
        requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='a-provider', port=443): Max retries exceeded "
            "(Caused by NewConnectionError('Failed to establish a new connection: "
            "[Errno -2] Name or service not known'))")) is True
    for status in (429, 500, 502, 503, 504, 524):
        assert chat_routes.is_retriable_llm_error(Exception(f"API Error: {status}\n")) is True
    assert chat_routes.is_retriable_llm_error(
        Exception("a provider returned empty response for model x")) is True
    # And a refusal is still never retried, whatever else changed.
    assert chat_routes.is_retriable_llm_error(Exception("content policy violation")) is False


class _BrokenAfterTokens:
    """200, four hundred deltas, then the connection dies mid-answer."""

    status_code = 200
    headers = {"Content-Type": "text/event-stream; charset=utf-8"}
    text = ""
    encoding = None

    def __init__(self, stats):
        self._stats = stats

    def iter_lines(self, decode_unicode=False):
        for i in range(400):
            self._stats["tokens"] += 1
            yield "data: " + json.dumps({"choices": [{"delta": {"content": f"w{i} "}}]})
            yield ""
        raise broken_stream_error()

    def close(self):
        pass


class _RefusedBeforeAnswering:
    """A 500 without a byte of an answer: a real availability failure, and one
    the shared reader does not itself ask again on, so the count below is the
    fallback chain's own."""

    status_code = 500
    headers = {"Content-Type": "application/json"}
    text = '{"error": "internal server error"}'
    encoding = None

    def __init__(self, stats):
        pass

    def iter_lines(self, decode_unicode=False):
        return iter(())

    def close(self):
        pass


@pytest.fixture()
def stand_in_transport(monkeypatch):
    """The whole cloud transport replaced by one counted stand-in.

    The fake address points at a port nothing listens on, so a call that somehow
    escaped the stand-in would fail locally rather than reach a provider.
    """
    stats = {"requests": 0, "tokens": 0}

    for provider in ("mistral", "ionos", "mammouth"):
        monkeypatch.setitem(
            oss._OPENAI_STYLE_PROVIDERS, provider,
            lambda: ("http://127.0.0.1:1/v1/chat/completions", "stand-in-key"))
    # The platform's ledger is the platform's, not this file's.
    monkeypatch.setattr(oss, "get_usage_tracker",
                        lambda: type("NoLedger", (), {"log": staticmethod(lambda **k: None)})())
    monkeypatch.setattr(chat_routes, "build_model_candidate_chain",
                        lambda key, primary: list(STAND_INS))

    def install(response_class):
        def fake_post(url, **kwargs):
            stats["requests"] += 1
            return response_class(stats)
        monkeypatch.setattr(oss.requests, "post", fake_post)
        return stats

    return install


def test_one_question_costs_one_request_when_the_stream_breaks(stand_in_transport):
    """Measured before the fix: 3 requests and 1200 generated tokens for one
    question, because the chain asked two more providers the same thing after
    the first had already written 400 of them."""
    stats = stand_in_transport(_BrokenAfterTokens)

    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        chat_routes.call_chat_helper([{"role": "user", "content": "one question"}],
                                     role="CHAT_HELPER_MODEL")

    assert stats["requests"] == 1
    assert stats["tokens"] == 400


def test_a_refusal_before_the_first_byte_still_walks_the_whole_chain(stand_in_transport):
    """The chain still exists for what it exists for."""
    stats = stand_in_transport(_RefusedBeforeAnswering)

    with pytest.raises(Exception) as excinfo:
        chat_routes.call_chat_helper([{"role": "user", "content": "one question"}],
                                     role="CHAT_HELPER_MODEL")

    assert "500" in str(excinfo.value)
    assert stats["requests"] == len(STAND_INS)
    assert stats["tokens"] == 0


def test_the_streaming_twin_still_stops_after_its_first_piece(stand_in_transport):
    """Unchanged, and named here because it is the same line: a candidate that
    breaks AFTER a room has read part of its answer ends the turn."""
    stats = stand_in_transport(_BrokenAfterTokens)

    pieces = []
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        for kind, payload in chat_routes.call_chat_helper_stream(
                [{"role": "user", "content": "one question"}], role="CHAT_HELPER_MODEL"):
            if kind == "token":
                pieces.append(payload)

    assert stats["requests"] == 1
    assert len(pieces) == 400


def test_a_host_that_is_down_is_not_a_moderation_refusal():
    """The classifier read the fragment "refus" out of "[Errno 111] Connection
    refused" and filed a dead endpoint as a content refusal, so the chain
    stopped at it and no further candidate was ever tried — for a failure in
    which nothing was refused, because the request never arrived.

    Both spellings are held: the TYPE, which is what a live call raises, and the
    PHRASE, which is what is left once something upstream has re-raised the same
    failure as plain text.
    """
    refused = ("HTTPSConnectionPool(host='a-provider', port=443): Max retries "
               "exceeded with url: /v1/chat/completions (Caused by "
               "NewConnectionError('Failed to establish a new connection: "
               "[Errno 111] Connection refused'))")
    assert chat_routes.is_retriable_llm_error(
        requests.exceptions.ConnectionError(refused)) is True
    assert chat_routes.is_retriable_llm_error(Exception(refused)) is True
    # The other three failures that arrive as this type, and are the same kind.
    assert chat_routes.is_retriable_llm_error(
        requests.exceptions.ConnectTimeout("timed out while connecting")) is True
    assert chat_routes.is_retriable_llm_error(
        requests.exceptions.SSLError("certificate verify failed")) is True
    assert chat_routes.is_retriable_llm_error(
        requests.exceptions.ProxyError("cannot connect to proxy")) is True


def test_a_refusal_is_still_never_retried():
    """SAFETY. The whole point of the content list is that a prompt a model
    refused must not be handed to a laxer one, and nothing above may widen a
    hole in it. "refus" still catches a refusal that says so in its own words.
    """
    for message in ("the model refused to answer",
                    "refusal: this request violates the content policy",
                    "blocked by moderation",
                    "content_filter triggered",
                    "the output was flagged"):
        assert chat_routes.is_retriable_llm_error(Exception(message)) is False


def test_a_stream_that_broke_while_it_was_read_still_stops():
    """The line drawn by the change this file was written for. It survives the
    one above because requests.ConnectionError is a SIBLING of
    ChunkedEncodingError and not its parent — asserted here rather than assumed,
    because the whole classification hangs on it.
    """
    assert not issubclass(requests.exceptions.ChunkedEncodingError,
                          requests.exceptions.ConnectionError)
    assert chat_routes.is_retriable_llm_error(broken_stream_error()) is False
