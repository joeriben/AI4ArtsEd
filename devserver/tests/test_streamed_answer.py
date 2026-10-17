#!/usr/bin/env python3
"""The transport that carries one answer over a connection that keeps breathing
(my_app/services/streaming_response.py), and the one route where asking for it
was ambiguous.

Written on 2026-09-04, after the change that moved every cloud call onto a
streamed transport left two holes on this side of the platform.

The first is what the terminal frame SAYS when a run ends badly. The worker
recorded only an `Exception`, so anything else that could end it — a
cancellation, a MemoryError, an interpreter being torn down — left the holder
empty; the loop then raised `KeyError: 'result'` and the frame carried the whole
message "'result'", the name of a dictionary key. It failed closed. What was
missing was the reason, and a failure nobody can read is a failure nobody can
fix.

The second is /pipeline/interception. "enable_streaming" names an older
Stage-1-and-2 event protocol there, and the shared transport is asked for with
"enable_answer_streaming" — while that same word names the shared transport on
every other route of this server, and services/directRun.ts sends exactly it. No
caller had walked into that yet; the next one would have received a different
pipeline, with a run_id of its own and no terminal frame, and waited for a frame
nobody writes.

Nothing here reaches a model or a GPU. Run:
  python3 -m pytest devserver/tests/test_streamed_answer.py -q
"""
import contextvars
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from flask import jsonify

from my_app.routes import schema_pipeline_routes as R
from my_app.services import streaming_response as SR
from my_app.services.streaming_response import (
    _complete_event,
    _json_body,
    events_with_heartbeat,
    streamed_answer,
)


def frames_of(run, **kw):
    """Drive the transport to its end and return the frames it wrote."""
    return list(streamed_answer(run, label="TEST", **kw))


def nothing_may_buffer_this(response) -> None:
    """The two headers, on every streamed answer this file drives.

    nginx buffers a proxied response by default, and a buffered stream is an
    origin that has sent nothing -- the 524 this whole change exists to prevent,
    reinstated at the last hop. Nothing asserted them until 2026-09-05: they
    could be stripped from every route and the transport tests stayed green.
    """
    assert response.mimetype == "text/event-stream", response.mimetype
    assert response.headers.get("Cache-Control") == "no-cache", dict(response.headers)
    assert response.headers.get("X-Accel-Buffering") == "no", dict(response.headers)


def terminal_body(frames):
    """The body of the `complete` frame, which is what the client reads."""
    for frame in frames:
        if frame.startswith("event: complete"):
            return json.loads(frame.split("data: ", 1)[1])
    raise AssertionError(f"no terminal frame in {frames!r}")


# ---------------------------------------------------------------------------
# 1. What the terminal frame says when the work ends badly
# ---------------------------------------------------------------------------

class TestTheFrameSaysWhatEndedTheRun:
    def test_the_answer_and_its_status_travel_when_the_work_succeeds(self):
        """The control. Without it every assertion below could be satisfied by a
        transport that failed on everything."""
        body = terminal_body(frames_of(lambda: ({"status": "success"}, 200)))
        assert body == {"http_status": 200, "body": {"status": "success"}}

    def test_an_ordinary_failure_still_arrives_with_what_it_said(self):
        def run():
            raise RuntimeError("the GPU service did not answer")

        body = terminal_body(frames_of(run))
        assert body["http_status"] == 500
        assert body["body"]["error"] == "the GPU service did not answer"

    @pytest.mark.parametrize("ending", [KeyboardInterrupt, SystemExit])
    def test_a_worker_that_ends_on_a_base_exception_names_what_ended_it(self, ending):
        """None of these is an Exception, and each of them used to leave the
        holder empty. The frame then carried "'result'" — a KeyError's message,
        which names a key in this module rather than anything that happened."""
        def run():
            raise ending()

        body = terminal_body(frames_of(run))
        assert body["http_status"] == 500
        message = body["body"]["error"]
        assert ending.__name__ in message
        assert message != "'result'"

    def test_an_exception_with_nothing_to_say_is_named_by_its_type(self):
        """A MemoryError reaches its route AS ITSELF, because what an ending is
        is part of what it says. What it has no words for is the rest:
        str(MemoryError()) is the empty string, and an empty message is the one
        thing this frame exists to prevent. So the type stands in for them."""
        def run():
            raise MemoryError()

        body = terminal_body(frames_of(run))
        assert body["http_status"] == 500
        assert "MemoryError" in body["body"]["error"]

    def test_a_base_exception_that_carries_words_carries_them_into_the_frame(self):
        def run():
            raise KeyboardInterrupt("the run was cancelled from outside")

        assert "the run was cancelled from outside" in terminal_body(frames_of(run))["body"]["error"]

    def test_a_run_that_ends_badly_still_ends_closed(self):
        """The property that must not move: a failure is a 500 carrying
        status=error, never a body a caller could read as an answer."""
        def run():
            raise KeyboardInterrupt()

        body = terminal_body(frames_of(run))
        assert body["body"]["status"] == "error"

    def test_the_leaving_signal_is_set_even_when_the_worker_ends_on_one_of_these(self):
        """Work holding the plant-wide GPU slot reads that event to stop early.
        A transport that stopped setting it on this path would leave the slot
        held by a run nobody is waiting for."""
        seen = {}

        def run(client_gone):
            seen["event"] = client_gone
            raise KeyboardInterrupt()

        frames_of(run)
        assert seen["event"].is_set()


# ---------------------------------------------------------------------------
# 2. Which stream /pipeline/interception was asked for
# ---------------------------------------------------------------------------

INTERCEPTION = "/api/schema/pipeline/interception"


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp)
    return app.test_client()


@pytest.fixture(autouse=True)
def a_run_that_answers(monkeypatch):
    """Both pipelines replaced by something that says which one ran.

    The older protocol writes its own frames; the shared transport hands back
    the `(payload, http_status)` a plain POST would have returned. Nothing about
    either pipeline is under test here — only which of the two a request
    reaches.
    """
    def older_protocol(data):
        yield "event: complete\ndata: " + json.dumps(
            {"status": "success", "run_id": "the-older-protocol"}) + "\n\n"

    monkeypatch.setattr(R, "execute_pipeline_streaming", older_protocol)
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(R, "_run_interception_pipeline",
                        lambda data, safety_level: (
                            {"status": "success", "run_id": "the-shared-transport"}, 200))


class TestTheTwoStreamsAreAskedForByDifferentNames:
    def test_a_post_that_asks_with_the_older_word_alone_is_refused(self, client):
        """The walk-in this closes. services/directRun.ts speaks the shared
        transport and says `enable_streaming`, because that is what the word
        means on every other route here. Served the older protocol, such a
        caller gets a different pipeline with a run_id of its own and waits for
        a terminal frame nobody writes."""
        response = client.post(INTERCEPTION, json={
            "schema": "dada", "input_text": "ein Haus", "enable_streaming": True,
        })
        assert response.status_code == 400
        answer = response.get_json()
        assert answer["cause"] == "ambiguous_streaming_flag"
        # The refusal names both flags, because the caller has to choose one.
        assert "enable_streaming" in answer["error"]
        assert "enable_answer_streaming" in answer["error"]

    def test_a_post_that_names_the_shared_transport_is_served_it(self, client):
        """Both words together, which is what directRun.ts now sends: the newer
        one decides, so a client that says which transport it means gets it."""
        response = client.post(INTERCEPTION, json={
            "schema": "dada", "input_text": "ein Haus",
            "enable_streaming": True, "enable_answer_streaming": True,
        })
        assert response.status_code == 200
        assert response.mimetype == "text/event-stream"
        nothing_may_buffer_this(response)
        assert "the-shared-transport" in response.get_data(as_text=True)

    def test_the_shared_transport_alone_is_served_as_it_always_was(self, client):
        response = client.post(INTERCEPTION, json={
            "schema": "dada", "input_text": "ein Haus", "enable_answer_streaming": True,
        })
        assert response.status_code == 200
        nothing_may_buffer_this(response)
        assert "the-shared-transport" in response.get_data(as_text=True)

    def test_the_older_protocol_says_do_not_buffer_too(self, client):
        """The one stream here that is not this transport at all. It writes its
        own frames, and it takes the Response from the same place -- so a stream
        nginx would buffer cannot come back from either of them."""
        response = client.get(
            INTERCEPTION + "?schema=dada&input_text=ein+Haus&enable_streaming=true")
        nothing_may_buffer_this(response)

    def test_a_get_still_reaches_the_older_protocol(self, client):
        """Untouched, and this is why the refusal above is confined to POST: the
        older protocol's only client is an EventSource in views/x2x_flow.vue,
        and an EventSource can ask nothing but a GET."""
        response = client.get(
            INTERCEPTION + "?schema=dada&input_text=ein+Haus&enable_streaming=true")
        assert response.status_code == 200
        assert response.mimetype == "text/event-stream"
        assert "the-older-protocol" in response.get_data(as_text=True)

    def test_a_post_without_a_streaming_flag_still_answers_with_one_json_body(self, client):
        response = client.post(INTERCEPTION, json={
            "schema": "dada", "input_text": "ein Haus",
        })
        assert response.status_code == 200
        assert response.mimetype == "application/json"
        assert response.get_json()["run_id"] == "the-shared-transport"


# ---------------------------------------------------------------------------
# 2b. Every route folded onto the shared gate answers on the same wire
# ---------------------------------------------------------------------------

MEAN_IMAGES = "/api/latent-lab/mean-images"

FOLDED_SITES = [
    # (module, run to stand in for, route, body, the word that asks)
    pytest.param('schema', '_run_stage2', "/api/schema/pipeline/stage2",
                 {"schema": "dada", "input_text": "ein Haus"},
                 "enable_streaming", id="stage2"),
    pytest.param('schema', '_run_optimize_prompt', "/api/schema/pipeline/optimize",
                 {"prompt": "ein Haus"}, "enable_streaming", id="optimize"),
    pytest.param('schema', '_run_safety_check_quick', "/api/schema/pipeline/safety/quick",
                 {"text": "ein Haus"}, "enable_streaming", id="safety_quick"),
    pytest.param('schema', '_run_translate', "/api/schema/pipeline/translate",
                 {"text": "ein Haus"}, "enable_streaming", id="translate"),
    pytest.param('schema', '_run_direct_workflow', "/api/schema/pipeline/direct",
                 {"prompt": "ein Haus"}, "enable_streaming", id="direct"),
    pytest.param('schema', '_run_interception_pipeline', INTERCEPTION,
                 {"schema": "dada", "input_text": "ein Haus"},
                 "enable_answer_streaming", id="interception"),
    pytest.param('mean_images', '_run_variants', MEAN_IMAGES + "/variants",
                 {"prompt": "ein Haus"}, "enable_streaming", id="mean_images_variants"),
    pytest.param('mean_images', '_run_overlay', MEAN_IMAGES + "/overlay",
                 {"run_ids": ["a", "b"]}, "enable_streaming", id="mean_images_overlay"),
    pytest.param('commons', '_run_lookup', "/api/commons/lookup",
                 {"prompt": "ein Haus"}, "enable_streaming", id="commons_lookup"),
]


@pytest.fixture()
def every_site(monkeypatch):
    """Both blueprints, with every folded run replaced by something that answers.

    What is under test is the WIRE each route answers on, not what any of them
    computes -- so each run is a stand-in and nothing here reaches a model.
    """
    from my_app.routes import commons_routes as C
    from my_app.routes import mean_images_routes as MI

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp)
    app.register_blueprint(MI.mean_images_bp)
    app.register_blueprint(C.commons_bp)
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(MI, "resolve_safety_level", lambda: "kids", raising=False)
    # Nothing to replace on the Commons route: it imports the resolver inside
    # the view, so what runs there is the real one -- which, on the request
    # thread and with no course pinned, is the installation setting and raises
    # nothing.
    return app, {"schema": R, "mean_images": MI, "commons": C}


@pytest.mark.parametrize("module,run,path,body,flag", FOLDED_SITES)
def test_every_folded_site_answers_on_the_same_wire(every_site, monkeypatch,
                                                    module, run, path, body, flag):
    """Fourteen sites wrote this Response out by hand, headers included, until
    they were folded onto one helper on 2026-09-05. Each one is asked here for
    both of its answers: the stream nginx must not buffer, and the one JSON body
    a caller that asked for no stream still gets."""
    app, modules = every_site
    target = modules[module]
    monkeypatch.setattr(target, run,
                        lambda *a, **kw: ({"status": "success"}, 200))
    client = app.test_client()

    streamed = client.post(path, json={**body, flag: True})
    nothing_may_buffer_this(streamed)
    assert "event: complete" in streamed.get_data(as_text=True)

    plain = client.post(path, json=dict(body))
    assert plain.mimetype == "application/json"
    assert plain.status_code == 200


# ---------------------------------------------------------------------------
# 3. A route whose safety level cannot be resolved
# ---------------------------------------------------------------------------

STAGE2 = "/api/schema/pipeline/stage2"


class TestARouteThatCannotResolveItsSafetyLevelSaysSo:
    """Both routes ask for the level at the request boundary, because a worker
    thread cannot see the session. Asked there and left unguarded, a resolver
    that raises leaves the route entirely, Flask puts its own HTML error page on
    the wire, and the cause is gone: no status a caller can act on, no field it
    can read, nothing in the answer naming what failed. /pipeline/safety/quick
    and the Mean Images overlay were guarded when they were moved; these two
    were not.
    """

    @pytest.fixture()
    def resolver_is_down(self, monkeypatch):
        def boom():
            raise RuntimeError("the course lookup is down")
        # After the autouse fixture above, so this is the one that stands.
        monkeypatch.setattr(R, "resolve_safety_level", boom)

    def test_stage2_answers_json_naming_the_cause(self, client, resolver_is_down):
        response = client.post(STAGE2, json={"schema": "dada", "input_text": "ein Haus"})
        assert response.status_code == 500
        assert response.mimetype == "application/json"
        answer = response.get_json()
        assert answer["success"] is False
        assert "safety level" in answer["error"]
        # The real cause travels, not a house error: a message that only says
        # something failed cannot be acted on.
        assert "the course lookup is down" in answer["error"]

    def test_interception_answers_json_naming_the_cause(self, client, resolver_is_down):
        response = client.post(INTERCEPTION, json={"schema": "dada", "input_text": "ein Haus"})
        assert response.status_code == 500
        assert response.mimetype == "application/json"
        answer = response.get_json()
        assert answer["status"] == "error"
        assert answer["cause"] == "safety_level_unresolved"
        assert "the course lookup is down" in answer["error"]

    def test_nothing_ran(self, client, resolver_is_down, monkeypatch):
        """SAFETY. An unresolved level is an unknown level, and a run under an
        unknown level would put Stage 1 and the kids/youth gate against nothing.
        The request ends before the pipeline is entered."""
        ran = []
        monkeypatch.setattr(R, "_run_stage2",
                            lambda data, safety_level: ran.append(1) or ({}, 200))
        monkeypatch.setattr(R, "_run_interception_pipeline",
                            lambda data, safety_level: ran.append(1) or ({}, 200))
        client.post(STAGE2, json={"schema": "dada", "input_text": "ein Haus"})
        client.post(INTERCEPTION, json={"schema": "dada", "input_text": "ein Haus"})
        assert ran == []


# ---------------------------------------------------------------------------
# 4. The two transports write the same answer the same way
# ---------------------------------------------------------------------------

class TestTheTerminalFrameIsWrittenLikeAJsonBody:
    """One route answers one question two ways: `jsonify(payload)` without the
    streaming flag, the same payload inside the terminal frame with it. Written
    with a bare `json.dumps` those were the same fields in a different order —
    Flask's provider sorts keys, `json.dumps` keeps insertion order — so a
    recording of one transport could not be held against the other."""

    PAYLOAD = {"status": "success", "run_id": "abc", "images": ["x"], "blocked": False}

    def test_the_frame_carries_the_body_byte_for_byte(self):
        app = Flask(__name__)
        with app.test_request_context("/"):
            blocking = jsonify(self.PAYLOAD).get_data(as_text=True).strip()
            frame = _complete_event(self.PAYLOAD, 200)
        streamed = frame.split("data: ", 1)[1].strip()
        assert blocking in streamed
        assert json.loads(streamed) == {"http_status": 200, "body": self.PAYLOAD}

    def test_the_two_spellings_of_the_writer_agree(self):
        """`_json_body` asks the app's own provider when there is an app, and
        writes DefaultJSONProvider's settings out when there is none — a unit
        test, or a stream built outside a request. Held equal here, so that is
        one policy written twice rather than two policies."""
        without_an_app = _json_body(self.PAYLOAD)
        app = Flask(__name__)
        with app.test_request_context("/"):
            with_an_app = _json_body(self.PAYLOAD)
        assert without_an_app == with_an_app

    def test_a_nested_payload_is_sorted_all_the_way_down(self):
        nested = {"b": 1, "a": {"d": 2, "c": [{"f": 3, "e": 4}]}}
        app = Flask(__name__)
        with app.test_request_context("/"):
            assert _json_body(nested) == jsonify(nested).get_data(as_text=True).strip()


# ---------------------------------------------------------------------------
# 5. One loop, two shapes
# ---------------------------------------------------------------------------

class TestOneLoopUnderBothShapes:
    """`streamed_answer` carries work that RETURNS a result;
    `events_with_heartbeat` carries work that YIELDS events as it goes. They ran
    as two files with two copies of one loop until 2026-09-04 — the same thread
    under a copied context, the same frame before the first wait, the same
    cadence, the same run carrying on when the reader leaves.

    What they genuinely do not share is what an ENDING means, and that is the
    last test here.
    """

    def test_both_shapes_are_the_same_loop(self, monkeypatch):
        seen = []
        real = SR._pumped

        def spy(source, **kw):
            seen.append(kw["label"])
            return real(source, **kw)

        monkeypatch.setattr(SR, "_pumped", spy)
        list(streamed_answer(lambda: ({"ok": True}, 200), label="ANSWER"))
        list(events_with_heartbeat(iter([1]), label="EVENTS",
                                   frame=lambda x: f"data: {x}\n\n"))
        assert seen == ["ANSWER", "EVENTS"]

    def test_both_write_a_frame_before_the_work_has_said_anything(self):
        """A byte from the start, not from the work's first sign of life."""
        def slow_answer():
            time.sleep(0.4)
            return {"ok": True}, 200

        def slow_events():
            time.sleep(0.4)
            yield 1

        for frames in (streamed_answer(slow_answer, label="TEST", interval=0.05),
                       events_with_heartbeat(slow_events(), label="TEST",
                                             frame=lambda x: "data: x\n\n",
                                             interval=0.05)):
            started = time.time()
            first = next(frames)
            assert time.time() - started < 0.2
            assert first == ": heartbeat\n\n"
            list(frames)

    def test_neither_lets_a_silence_grow_past_the_cadence(self):
        """The edge cuts at about a hundred seconds of silence and nothing here
        may approach it. Both shapes keep the same distance from it."""
        def slow_answer():
            time.sleep(0.6)
            return {"ok": True}, 200

        def slow_events():
            time.sleep(0.6)
            yield 1

        for frames in (streamed_answer(slow_answer, label="TEST", interval=0.1),
                       events_with_heartbeat(slow_events(), label="TEST",
                                             frame=lambda x: "data: x\n\n",
                                             interval=0.1)):
            gaps = []
            last = time.time()
            for _ in frames:
                now = time.time()
                gaps.append(now - last)
                last = now
            assert max(gaps) < 0.3, gaps
            assert len(gaps) >= 5

    def test_both_carry_the_caller_context_onto_the_worker(self):
        """Under Flask this is what puts the request and the app context on the
        worker thread. Without it, storage and everything else the work reaches
        for through Flask is simply gone, and gone silently."""
        marker = contextvars.ContextVar("marker")
        marker.set("from the caller")
        seen = {}

        def answer_work():
            seen["answer"] = marker.get()
            return {"ok": True}, 200

        def event_work():
            seen["events"] = marker.get()
            yield 1

        list(streamed_answer(answer_work, label="TEST", interval=0.05))
        list(events_with_heartbeat(event_work(), label="TEST",
                                   frame=lambda x: "data: x\n\n", interval=0.05))
        assert seen == {"answer": "from the caller", "events": "from the caller"}

    def test_the_work_runs_on_when_the_reader_leaves(self):
        """A closed tab ends the streaming and nothing else: the run finishes
        and saves what it made. Both shapes."""
        finished = threading.Event()

        def answer_work():
            time.sleep(0.2)
            finished.set()
            return {"ok": True}, 200

        frames = streamed_answer(answer_work, label="TEST", interval=0.05)
        next(frames)
        frames.close()
        assert finished.wait(3.0)

        finished.clear()

        def event_work():
            time.sleep(0.2)
            finished.set()
            yield 1

        frames = events_with_heartbeat(event_work(), label="TEST",
                                       frame=lambda x: "data: x\n\n", interval=0.05)
        next(frames)
        frames.close()
        assert finished.wait(3.0)

    def test_an_ending_is_the_one_thing_the_two_shapes_answer_differently(self):
        """The answer shape has a terminal frame to put a failure into and an
        HTTP status to put beside it. The event shape has neither, and a route
        above it that has already written events of its own — so it RAISES,
        after everything that went out before the failure, and that route turns
        it into an event in the order it belongs.
        """
        def failing_answer():
            raise RuntimeError("the work fell over")

        body = terminal_body(frames_of(failing_answer))
        assert body["http_status"] == 500
        assert "the work fell over" in body["body"]["error"]

        def failing_events():
            yield 1
            raise RuntimeError("the work fell over")

        got = []
        with pytest.raises(RuntimeError, match="the work fell over"):
            for frame in events_with_heartbeat(failing_events(), label="TEST",
                                               frame=lambda x: f"data: {x}\n\n",
                                               interval=0.05):
                got.append(frame)
        # Everything the work produced before the failure went out first.
        assert "data: 1\n\n" in got


def test_the_event_shape_no_longer_stands_in_a_file_of_its_own():
    """Rule 13. Two implementations of one behaviour is a bug, and this
    transport was two files: services/streaming_events.py held the event shape
    with its own copy of the thread, the context, the cadence and the leaving.
    """
    with pytest.raises(ModuleNotFoundError):
        import my_app.services.streaming_events  # noqa: F401
