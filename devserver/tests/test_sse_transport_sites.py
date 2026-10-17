#!/usr/bin/env python3
"""The five streamed routes, now that the shared transport carries them.

Written on 2026-09-04, alongside the change that put `events_with_heartbeat`
(my_app/services/streaming_response.py) under the canvas run stream, its
reconnect twin, the canvas batch, the text proxy and the Stage-3 wait of
/pipeline/generate/stream. test_chat_stream_transport.py is the precedent: it
pins the same claims for the chat application of this transport, and
`frames_of` below is its helper widened to the second SSE dialect these routes
speak.

Three claims, and the first is the reason any of this was built.

  * THE CONNECTION KEEPS BREATHING. The tunnel in front of this server ends a
    proxied request whose origin has been silent for about a hundred seconds
    and hands the browser a 524. So on every route below, a stretch in which
    the work says nothing is a stretch in which frames still go out — and that
    is asserted here by HOLDING the work and counting what arrives, not by
    sleeping long enough to hope for it. Asserting the mere PRESENCE of one
    comment frame would not do it: a transport that emits its single pre-wait
    beat and then never breathes again passes that, and it is exactly the
    failure this change exists to end.

  * THE FRAMES DO NOT MOVE. Every event each route wrote before it breathed, it
    still writes, unchanged and in the same order; what fills the gaps is an SSE
    comment, which carries no payload and so reaches no consumer as an event.
    `frames_of` calls a frame a comment BECAUSE it begins with ':', so a
    `kinds ==` assertion says only that — `no_comment_carries_a_payload` below
    is what says the other half.

  * THE READER'S LEAVING STILL ARRIVES. Before the wrapping, a closed browser
    tab raised `GeneratorExit` at the route generator's own `yield`, and for the
    canvas batch and the text proxy that was the ONLY cancellation they had. The
    work now runs on a thread, where that never happens: the batch ran its
    remaining generations onto the shared card for nobody, each taking a GPU
    lease, and the proxy held the GPU service's text slot and model lock to the
    last token of an answer no one would read. A source that asks for the
    leaving signal is told; one that does not ask runs exactly as it did.

Nothing here reaches a model, a GPU or ComfyUI: every backend is a stand-in.

Run:  python3 -m pytest devserver/tests/test_sse_transport_sites.py -q
"""
import json
import sys
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import requests
from flask import Flask

from my_app.routes import canvas_routes, schema_pipeline_routes
from my_app.services import canvas_run_service as crs
from my_app.services import streaming_response as transport
from my_app.services.streaming_response import (UnwritableEvent,
                                                events_with_heartbeat,
                                                streamed_answer)

# The cadence every route below runs at: `events_with_heartbeat`'s own default,
# which is what those routes take. Stated once so the assertions read as what
# they are — a bound on silence — and so that forcing the transport slower makes
# every one of them fail rather than one.
CADENCE = 2.0


# ---------------------------------------------------------------------------
# reading the wire
# ---------------------------------------------------------------------------

def frames_of(body: str) -> list:
    """The frames on the wire, in order, as (kind, payload).

    kind is 'comment' for a line the SSE spec calls a comment — which every
    reader on this platform drops — and 'event' for a frame carrying a `data:`
    field. The payload stays RAW text, because these routes speak two dialects
    of it — `event: <name>` above the data line, and a bare `data:` — and part
    of what is under test is that each keeps writing its own.
    """
    out = []
    for raw in body.split("\n\n"):
        if not raw.strip():
            continue
        if raw.lstrip().startswith(":"):
            out.append(("comment", raw))
        else:
            out.append(("event", raw))
    return out


def event_names(body: str) -> list:
    """The `event:` names in order, for the routes that write them."""
    names = []
    for kind, raw in frames_of(body):
        if kind != "event":
            continue
        for line in raw.split("\n"):
            if line.startswith("event: "):
                names.append(line[len("event: "):])
    return names


def event_payloads(body: str) -> list:
    payloads = []
    for kind, raw in frames_of(body):
        if kind != "event":
            continue
        for line in raw.split("\n"):
            if line.startswith("data: "):
                payloads.append(json.loads(line[len("data: "):]))
    return payloads


def no_comment_carries_a_payload(body: str) -> None:
    """The half of the contract `frames_of` cannot check.

    `frames_of` calls a frame a comment BECAUSE it starts with ':', which makes
    every `kinds ==` assertion in this file circular on its own: it says the
    frame began with a colon and nothing more. What has to hold is that such a
    frame carries no field at all — `parseFrame` in lib/sseStream.ts drops a
    frame with no `data:` payload, and that is the whole reason a heartbeat
    reaches no consumer as an event.
    """
    comments = [raw for kind, raw in frames_of(body) if kind == "comment"]
    assert comments, "nothing on this wire was a comment"
    for raw in comments:
        for line in raw.split("\n"):
            assert not line.startswith("data:"), raw
            assert not line.startswith("event:"), raw
            assert not line.startswith("id:"), raw


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


def read_while_held(stream, gate, beats=2, watchdog_after=12.0):
    """Read a stream whose work is HELD, and let the work go on only once the
    transport has breathed `beats` times.

    DRIVEN, not raced. Every stand-in that uses this stays silent until this
    reader opens its gate, so "the connection kept breathing across a silence
    longer than the cadence" is settled by what actually arrived, and never by
    a sleep chosen long enough to hope for it. The watchdog opens the gate if
    the beats never come, so a transport that does NOT breathe fails at the
    assertion below instead of hanging here.

    Returns (arrivals, body, beats_while_held).
    """
    arrivals, body, held_beats = [], "", 0
    started = time.time()
    watchdog = threading.Timer(watchdog_after, gate.set)
    watchdog.daemon = True
    watchdog.start()
    try:
        for chunk in stream:
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
            if not text:
                continue
            arrivals.append((time.time() - started, text))
            body += text
            if not gate.is_set():
                held_beats += sum(1 for kind, _ in frames_of(text)
                                  if kind == "comment")
                if held_beats >= beats:
                    gate.set()
            assert time.time() - started < watchdog_after + 30, \
                "the stream did not end"
    finally:
        watchdog.cancel()
    return arrivals, body, held_beats


def widest_gap(arrivals) -> float:
    """The longest stretch with nothing on the wire. This is the number the
    tunnel in front of this server actually measures."""
    return max([arrivals[i][0] - arrivals[i - 1][0]
                for i in range(1, len(arrivals))] or [0.0])


def kept_breathing(arrivals, held_beats, beats=2):
    """Both halves of the first claim, in one place.

    The count says frames kept coming while the work said nothing; the gap says
    none of those silences grew. Either alone can be passed by a transport that
    breathes once and stops.
    """
    assert held_beats >= beats, \
        "the stream stopped breathing while its work said nothing"
    assert widest_gap(arrivals) < CADENCE * 1.5, \
        [round(a, 3) for a, _ in arrivals]


def wait_for(predicate, timeout=10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


# ---------------------------------------------------------------------------
# 1. The transport offers the leaving signal, and offers exactly one
# ---------------------------------------------------------------------------

def test_a_source_handed_over_as_a_function_is_told_when_the_reader_leaves():
    """The property the wrapping had removed, restored at its source.

    A source handed over as the FUNCTION — rather than as a generator already
    made — declares `client_gone` and is given the event, which is set the
    moment the frames are abandoned. That is the closed tab, arriving where the
    work can act on it.
    """
    entered = threading.Event()
    noticed = threading.Event()

    def work(client_gone):
        entered.set()
        while not client_gone.is_set():
            time.sleep(0.01)
        noticed.set()
        yield "data: never read\n\n"

    frames = events_with_heartbeat(work, label="TEST", frame=lambda s: s,
                                   interval=0.05)
    assert next(frames) == ": heartbeat\n\n"
    assert entered.wait(3.0)
    assert not noticed.is_set()
    frames.close()
    assert noticed.wait(3.0), "the source was never told its reader had gone"


def test_the_answer_shape_is_told_at_the_same_moment():
    """The other shape, on the same property. Drained to the end, ANY
    implementation ends with something set; what tells the two apart is a
    stream dropped while the work is still running."""
    entered = threading.Event()
    noticed = threading.Event()

    def work(client_gone):
        entered.set()
        while not client_gone.is_set():
            time.sleep(0.01)
        noticed.set()
        return {"ok": True}, 200

    frames = streamed_answer(work, label="TEST", interval=0.05)
    assert next(frames) == ": heartbeat\n\n"
    assert entered.wait(3.0)
    assert not noticed.is_set()
    frames.close()
    assert noticed.wait(3.0), "the work was never told its reader had gone"


def test_a_source_that_asks_for_nothing_runs_exactly_as_it_did():
    """The other half: most callers hand over a generator already made, ask for
    nothing, and must be untouched by any of this."""
    finished = threading.Event()

    def work():
        yield "data: one\n\n"
        time.sleep(0.15)
        finished.set()
        yield "data: two\n\n"

    body = "".join(events_with_heartbeat(work(), label="TEST",
                                         frame=lambda s: s, interval=0.05))
    assert finished.is_set()
    assert [p for _, p in frames_of(body) if _ == "event"] == \
        ["data: one", "data: two"]


def test_both_shapes_hand_on_the_signal_their_loop_made(monkeypatch):
    """One event, made in `_pumped`, handed on by both shapes — not one
    mechanism per transport, which is how two answers to "has the reader gone?"
    start drifting apart.

    COMPARED, and not merely observed twice. Watching an event come back set
    from each shape settles nothing: drained to the end, an implementation that
    made one of its own per shape would look exactly the same. Here the loop is
    replaced by a stand-in that keeps the source each shape handed it, and that
    source is then called with an event of OUR making. What the work receives
    is that event, so neither shape can be holding one of its own.
    """
    captured = {}

    def stand_in(source, *, label, interval, heartbeat):
        captured["source"] = source
        return
        yield        # pragma: no cover - makes this a generator function

    monkeypatch.setattr(transport, "_pumped", stand_in)

    seen = {}

    def answer(client_gone):
        seen["answer"] = client_gone
        return {"ok": True}, 200

    def events(client_gone):
        seen["events"] = client_gone
        yield "data: x\n\n"

    ours = threading.Event()

    list(transport.streamed_answer(answer, label="TEST"))
    list(captured["source"](client_gone=ours))

    list(transport.events_with_heartbeat(events, label="TEST",
                                         frame=lambda s: s))
    list(captured["source"](client_gone=ours))

    assert seen["answer"] is ours, "the answer shape made a signal of its own"
    assert seen["events"] is ours, "the event shape made a signal of its own"


def test_a_source_that_only_holds_a_result_puts_no_byte_on_the_wire():
    """The shape /pipeline/generate/stream gives Stage 3: nothing to write, a
    holder to fill, and a `yield ''` whose only job is to make the function a
    generator. Without that yield `_pumped` would be handed a value where it
    expects an iterable — and the whole of Stage 3 would already have run, in
    silence, on the request thread, which is the failure the wrapping exists to
    end.
    """
    holder = {}

    def stage3():
        time.sleep(0.2)
        holder["result"] = "safe"
        yield ''

    body = "".join(events_with_heartbeat(stage3(), label="TEST",
                                         frame=lambda s: s, interval=0.05))
    assert holder["result"] == "safe"
    assert [k for k, _ in frames_of(body)] == ["comment"] * len(frames_of(body))
    assert "data:" not in body


def test_a_source_that_is_both_callable_and_iterable_is_read_and_not_called():
    """Which of the two spellings a source is, decided by something that cannot
    misfire.

    `callable()` cannot tell them apart: an object that is BOTH — a Mock above
    all, and every stand-in built on one — answers yes, is therefore CALLED,
    and its `__iter__` never runs. The stream is then silently empty, which is
    the worst of the three possible answers.
    """
    class Both:
        called = False

        def __call__(self):
            type(self).called = True
            return iter(())

        def __iter__(self):
            return iter(["data: one\n\n", "data: two\n\n"])

    body = "".join(events_with_heartbeat(Both(), label="TEST",
                                         frame=lambda s: s, interval=0.05))
    assert Both.called is False, "the source was called instead of being read"
    assert [p for k, p in frames_of(body) if k == "event"] == \
        ["data: one", "data: two"]


def test_an_event_that_cannot_be_written_is_not_a_departure(monkeypatch):
    """A `frame` that raises is a fault of the STREAM, not a reader leaving.

    The canvas run stream and its reconnect twin write their frames with
    `json.dumps` over a record, which is a thing that can fail on its own.
    Reported as a departure, that failure set the leaving signal and ended a
    tail whose client was still there and still reading. It must be visible —
    an event that never reached the wire is a real fault — and it must not be
    told to the source as a leaving.

    The pumped loop is held here for the length of the test, so that what is
    asserted is what the transport DID and not when the collector got round to
    the leftovers.
    """
    kept = []
    real_pumped = transport._pumped

    def keeping(source, **kw):
        loop = real_pumped(source, **kw)
        kept.append(loop)
        return loop

    monkeypatch.setattr(transport, "_pumped", keeping)

    signal = {}

    def work(client_gone):
        signal["given"] = client_gone
        yield {"a record": object()}          # nothing json.dumps can write

    frames = events_with_heartbeat(
        work, label="TEST",
        frame=lambda rec: "data: " + json.dumps(rec) + "\n\n",
        interval=0.05)

    failure, got = None, []
    try:
        for chunk in frames:
            got.append(chunk)
    except UnwritableEvent as e:
        failure = e

    assert failure is not None, "the unwritable event was swallowed"
    assert "could not write an event" in str(failure)
    assert isinstance(failure.__cause__, TypeError)
    assert not signal["given"].is_set(), \
        "a frame that could not be written reached the source as a departure"
    # And a real departure still is one.
    kept[0].close()
    assert signal["given"].is_set()


# ---------------------------------------------------------------------------
# 2. Endings, and what each one may still be when it arrives
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ending", [SystemExit, KeyboardInterrupt])
def test_an_ending_that_is_no_exception_arrives_where_a_route_can_catch_it(ending):
    """Every route above this transport is written with `except Exception`.
    Re-raised raw, a BaseException sails straight past it and tears the stream
    with no terminal frame in it at all — the answer shape has normalised that
    since it was written; the event shape had not."""
    def work():
        yield "data: one\n\n"
        raise ending()

    got = []
    with pytest.raises(Exception) as excinfo:
        for chunk in events_with_heartbeat(work(), label="TEST",
                                           frame=lambda s: s, interval=0.05):
            got.append(chunk)
    assert type(excinfo.value) is not ending
    assert ending.__name__ in str(excinfo.value)
    # And everything written before the failure went out first, in order.
    assert "data: one\n\n" in got


@pytest.mark.parametrize("ending", [MemoryError, requests.Timeout])
def test_an_exception_reaches_its_route_as_itself(ending):
    """What an ending IS, is part of what it says.

    `str(MemoryError())` is the empty string, and a `requests.Timeout` can be
    raised with nothing to say. Weighed by its MESSAGE rather than by its type,
    such an ending was rewrapped as a bare `Exception` on the way up — so a
    route that answers one kind of failure differently from the rest, by
    catching it by name, would silently stop seeing it and write the wrong line
    for the one case it was written for.
    """
    def work():
        yield "data: one\n\n"
        raise ending()

    with pytest.raises(ending) as excinfo:
        list(events_with_heartbeat(work(), label="TEST", frame=lambda s: s,
                                   interval=0.05))
    assert type(excinfo.value) is ending
    assert str(excinfo.value) == ""


def test_a_worker_thread_that_cannot_start_is_said_and_not_swallowed(monkeypatch):
    """Under load `thread.start()` raises inside the generator, before the first
    heartbeat. Three routes hand their generator straight to Flask, which has
    already sent the 200 — so raised out, this leaves an empty torn body and no
    word about why."""
    def refuse(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", refuse)

    got = []
    with pytest.raises(Exception) as excinfo:
        for chunk in events_with_heartbeat(iter(["data: x\n\n"]), label="TEST",
                                           frame=lambda s: s, interval=0.05):
            got.append(chunk)
    assert "can't start new thread" in str(excinfo.value)
    assert got == []


def test_the_answer_shape_puts_the_same_failure_in_its_terminal_frame(monkeypatch):
    def refuse(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", refuse)

    frames = list(streamed_answer(lambda: ({"ok": True}, 200), label="TEST"))
    terminal = [f for f in frames if f.startswith("event: complete")]
    assert terminal, frames
    body = json.loads(terminal[0].split("data: ", 1)[1])
    assert body["http_status"] == 500
    assert "can't start new thread" in body["body"]["error"]


# ---------------------------------------------------------------------------
# 3. The canvas run stream and its reconnect twin
# ---------------------------------------------------------------------------

RECORDS = [
    {"_i": 0, "type": "progress",
     "data": {"node_id": "n1", "node_type": "input", "message": "los"}},
    {"_i": 1, "type": "node_complete", "data": {"node_id": "n1"}},
    {"_i": 2, "type": "complete",
     "data": {"results": {}, "run_id": "run_stand_in_canvas"}},
]


@pytest.fixture()
def canvas_app(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(canvas_routes.canvas_bp)
    monkeypatch.setattr(canvas_routes, "resolve_safety_level", lambda: "kids")
    return app


def test_the_canvas_run_stream_writes_the_frames_it_always_wrote(canvas_app, monkeypatch):
    monkeypatch.setattr(crs, "start_run", lambda **kw: "run_stand_in_canvas")

    def tail(run_id, after=-1, timeout=300.0, client_gone=None):
        for rec in RECORDS:
            yield rec

    monkeypatch.setattr(crs, "iter_events", tail)

    client = canvas_app.test_client()
    body = client.post("/api/canvas/execute-stream",
                       json={"nodes": [{"id": "n1"}], "connections": []}
                       ).get_data(as_text=True)

    assert event_names(body) == ["run_started", "started",
                                 "progress", "node_complete", "complete"]
    # The two route frames first, then the transport's first breath, then the
    # run's own events — the order a reader has always seen, plus a comment.
    kinds = [k for k, _ in frames_of(body)]
    assert kinds == ["event", "event", "comment", "event", "event", "event"]
    no_comment_carries_a_payload(body)
    # The id: line that makes a reconnect lossless is still on every record.
    assert "id: 2\nevent: complete\n" in body


def test_the_canvas_run_stream_keeps_breathing_while_the_tail_is_silent(canvas_app, monkeypatch):
    """A node waiting at the admission gate for the card writes nothing to the
    run's events, for as long as GPU_ADMISSION_ACQUIRE_TIMEOUT_S lets it wait.
    The tail is HELD here for exactly as long as it takes to hear the transport
    breathe twice, so what is asserted is the cadence and not a sleep."""
    monkeypatch.setattr(crs, "start_run", lambda **kw: "run_stand_in_canvas")
    gate = threading.Event()

    def tail(run_id, after=-1, timeout=300.0, client_gone=None):
        assert gate.wait(30.0)
        for rec in RECORDS:
            yield rec

    monkeypatch.setattr(crs, "iter_events", tail)

    with canvas_app.test_request_context(
            "/api/canvas/execute-stream",
            json={"nodes": [{"id": "n1"}], "connections": []}):
        response = canvas_routes.execute_workflow_stream()
    arrivals, body, held = read_while_held(response.response, gate)

    kept_breathing(arrivals, held)
    assert event_names(body) == ["run_started", "started",
                                 "progress", "node_complete", "complete"]
    no_comment_carries_a_payload(body)


def test_the_canvas_reconnect_writes_the_frames_it_always_wrote(canvas_app, monkeypatch):
    def tail(run_id, after=-1, timeout=300.0, client_gone=None):
        assert after == 1, "the resume point did not reach the tail"
        for rec in RECORDS[2:]:
            yield rec

    monkeypatch.setattr(crs, "iter_events", tail)

    client = canvas_app.test_client()
    body = client.get("/api/canvas/execute-stream/run_stand_in_canvas?after=1"
                      ).get_data(as_text=True)

    assert event_names(body) == ["run_started", "complete"]
    assert [k for k, _ in frames_of(body)] == ["event", "comment", "event"]
    no_comment_carries_a_payload(body)


def test_the_canvas_reconnect_keeps_breathing_while_the_tail_is_silent(canvas_app, monkeypatch):
    """This is the path a client reaches after it has already lost one stream,
    so it is the one place where a second silent gap must not cost it the run."""
    gate = threading.Event()

    def tail(run_id, after=-1, timeout=300.0, client_gone=None):
        assert gate.wait(30.0)
        for rec in RECORDS[2:]:
            yield rec

    monkeypatch.setattr(crs, "iter_events", tail)

    with canvas_app.test_request_context(
            "/api/canvas/execute-stream/run_stand_in_canvas?after=1"):
        response = canvas_routes.reconnect_workflow_stream("run_stand_in_canvas")
    arrivals, body, held = read_while_held(response.response, gate)

    kept_breathing(arrivals, held)
    assert event_names(body) == ["run_started", "complete"]
    no_comment_carries_a_payload(body)


def test_the_canvas_tail_is_told_when_its_reader_leaves(canvas_app, monkeypatch):
    entered, noticed = threading.Event(), threading.Event()
    monkeypatch.setattr(crs, "start_run", lambda **kw: "run_stand_in_canvas")

    def tail(run_id, after=-1, timeout=300.0, client_gone=None):
        entered.set()
        while not client_gone.is_set():
            time.sleep(0.01)
        noticed.set()
        yield RECORDS[0]

    monkeypatch.setattr(crs, "iter_events", tail)

    with canvas_app.test_request_context(
            "/api/canvas/execute-stream",
            json={"nodes": [{"id": "n1"}], "connections": []}):
        response = canvas_routes.execute_workflow_stream()
    stream = response.response
    next(stream)                      # run_started
    next(stream)                      # started
    next(stream)                      # the transport's first breath
    assert entered.wait(3.0)
    stream.close()                    # the closed tab
    assert noticed.wait(3.0), "the tail sat on after its reader had gone"


def test_the_run_tail_ends_on_the_signal_and_the_run_itself_does_not(tmp_path):
    """canvas_run_service.iter_events itself. An abandoned tail used to sit here
    for the full 300 s, waking once a second to take _JOBS_LOCK — which the
    status endpoint and the run worker both need. The RUN is a background job by
    design: the reader leaving must not touch it."""
    crs._reset_registry_for_tests()
    folder = tmp_path / "run_stand_in_canvas"
    folder.mkdir()
    with crs._JOBS_COND:
        crs._JOBS["run_stand_in_canvas"] = {
            "state": "running", "events": [], "n_events": 0, "recorder": None,
            "run_folder": str(folder), "error": None,
            "started_at": "2026-09-04T00:00:00", "finished_at": None,
        }
    try:
        gone = threading.Event()
        ended = threading.Event()

        def read():
            for _ in crs.iter_events("run_stand_in_canvas", after=-1,
                                     timeout=300.0, client_gone=gone):
                pass
            ended.set()

        threading.Thread(target=read, daemon=True).start()
        time.sleep(0.3)
        assert not ended.is_set(), "the tail ended before anything told it to"
        gone.set()
        assert ended.wait(3.0), "the tail outlived its reader"
        # The job is exactly as it was: nobody cancelled the run.
        assert crs.get_status("run_stand_in_canvas")["state"] == "running"
    finally:
        crs._reset_registry_for_tests()


def test_a_tail_without_the_signal_waits_out_its_timeout_as_before(tmp_path):
    """The parameter is additive. Every caller that passes none — the two route
    tests above aside, the whole of test_canvas_run_service.py — reads as it
    always did, and ends on the timeout it was given."""
    crs._reset_registry_for_tests()
    folder = tmp_path / "run_stand_in_canvas"
    folder.mkdir()
    with crs._JOBS_COND:
        crs._JOBS["run_stand_in_canvas"] = {
            "state": "running", "events": [], "n_events": 0, "recorder": None,
            "run_folder": str(folder), "error": None,
            "started_at": "2026-09-04T00:00:00", "finished_at": None,
        }
    try:
        ended = threading.Event()

        def read():
            for _ in crs.iter_events("run_stand_in_canvas", after=-1, timeout=0.6):
                pass
            ended.set()

        threading.Thread(target=read, daemon=True).start()
        time.sleep(0.2)
        assert not ended.is_set()
        assert ended.wait(4.0)
    finally:
        crs._reset_registry_for_tests()


# ---------------------------------------------------------------------------
# 4. The canvas batch
# ---------------------------------------------------------------------------

class _FakeRecorder:
    def __init__(self, run_folder):
        self.run_folder = run_folder
        self.device_id = "stand-in-device"

    def mark_complete(self):
        pass


class _FakeExecutor:
    """Yields a scripted event stream and reports success. One instance per run,
    counted, because 'the remaining runs never start' is counted here."""
    script = [("progress", {"node_id": "n1"}), ("node_complete", {"node_id": "n1"})]
    delay = 0.0
    made = []

    def __init__(self, **kwargs):
        type(self).made.append(kwargs.get("run_id"))

    def execute_with_events(self):
        for event in type(self).script:
            if type(self).delay:
                time.sleep(type(self).delay)
            yield event[0], dict(event[1])

    def get_result(self):
        return {"success": True, "results": {}, "collector_items": [],
                "execution_trace": ["n1"]}


@pytest.fixture()
def batch_wired(canvas_app, tmp_path, monkeypatch):
    _FakeExecutor.made = []
    _FakeExecutor.delay = 0.0
    _FakeExecutor.script = [("progress", {"node_id": "n1"}),
                            ("node_complete", {"node_id": "n1"})]
    canvas_routes.BATCH_ABORT_FLAGS.clear()
    monkeypatch.setattr(canvas_routes, "CanvasWorkflowExecutor", _FakeExecutor)
    monkeypatch.setattr(
        canvas_routes, "get_canvas_recorder",
        lambda run_id, **kw: _FakeRecorder(tmp_path / run_id))
    monkeypatch.setattr(canvas_routes, "cleanup_canvas_recorder", lambda run_id: None)
    # execute_batch imports the engine inside the view; stub the module it
    # reaches for, as test_canvas_run_service.py does for the same reason.
    fake = types.ModuleType("schemas.engine.prompt_interception_engine")
    fake.PromptInterceptionEngine = lambda: object()
    fake.PromptInterceptionRequest = object
    monkeypatch.setitem(sys.modules, "schemas.engine.prompt_interception_engine", fake)
    yield canvas_app
    canvas_routes.BATCH_ABORT_FLAGS.clear()


def _batch_request(app, count=2):
    return app.test_request_context("/api/canvas/execute-batch", json={
        "workflow": {"nodes": [{"id": "n1"}], "connections": []},
        "count": count})


def test_the_batch_writes_the_frames_it_always_wrote(batch_wired):
    client = batch_wired.test_client()
    body = client.post("/api/canvas/execute-batch", json={
        "workflow": {"nodes": [{"id": "n1"}], "connections": []},
        "count": 2,
    }).get_data(as_text=True)

    assert event_names(body) == [
        "batch_started",
        "run_start", "progress", "node_complete", "run_complete",
        "run_start", "progress", "node_complete", "run_complete",
        "batch_complete",
    ]
    # The whole batch is under the transport, so its first breath comes before
    # the first event — and it is a comment, which reaches no consumer.
    assert frames_of(body)[0][0] == "comment"
    no_comment_carries_a_payload(body)
    # run_index still rides on every event of a run.
    assert [p["run_index"] for p in event_payloads(body) if "run_index" in p] == \
        [0, 0, 0, 0, 1, 1, 1, 1]
    assert len(_FakeExecutor.made) == 2


def test_the_batch_keeps_breathing_while_a_run_says_nothing(batch_wired, tmp_path,
                                                            monkeypatch):
    """A batch waits at the admission gate once per run, and says nothing for
    the whole of it. The recorder is HELD here, which is where that wait sits."""
    gate = threading.Event()

    def held_recorder(run_id, **kw):
        assert gate.wait(30.0)
        return _FakeRecorder(tmp_path / run_id)

    monkeypatch.setattr(canvas_routes, "get_canvas_recorder", held_recorder)

    with _batch_request(batch_wired, count=1):
        response = canvas_routes.execute_batch()
    arrivals, body, held = read_while_held(response.response, gate)

    kept_breathing(arrivals, held)
    assert event_names(body)[-1] == "batch_complete"
    no_comment_carries_a_payload(body)


def test_a_batch_stops_when_its_reader_leaves_and_leaves_nothing_behind(batch_wired,
                                                                        monkeypatch):
    """What a closed tab used to do, and stopped doing when this stream was
    wrapped: every remaining run went on to take a GPU lease and render onto the
    shared card for nobody. BATCH_ABORT_FLAGS cannot stand in for it — nothing
    sets the flag on a disconnect, and the batch id lived only in the tab that
    closed.

    And an abandoned batch has to leave the platform as it found it. The early
    return used to keep neither promise the abort path a few lines below keeps:
    its flag stayed in BATCH_ABORT_FLAGS under a batch id nothing would ever
    ask about again, and the in-flight run stayed in the recorder registry —
    both for the life of the process.
    """
    cleaned = []
    monkeypatch.setattr(canvas_routes, "cleanup_canvas_recorder",
                        lambda run_id: cleaned.append(run_id))
    _FakeExecutor.delay = 0.02
    _FakeExecutor.script = [("progress", {"node_id": f"n{i}"}) for i in range(40)]

    with _batch_request(batch_wired, count=4):
        response = canvas_routes.execute_batch()
    stream = response.response

    seen = []
    while len([f for f in seen if "event: progress" in f]) < 2:
        seen.append(next(stream))
    assert len(_FakeExecutor.made) == 1
    stream.close()

    # Not a window guessed to be long enough: the batch's OWN bookkeeping says
    # when it is done with itself. A batch that stops and a batch that runs all
    # four runs both end by deleting the flag, so this wait ends either way —
    # and what it ends WITH is the count below.
    assert wait_for(lambda: not canvas_routes.BATCH_ABORT_FLAGS), \
        "the abandoned batch left its abort flag standing for the life of the process"
    assert len(_FakeExecutor.made) == 1, \
        "the batch went on generating for a reader that had gone"
    assert cleaned == [_FakeExecutor.made[0]], \
        "the abandoned run stayed in the recorder registry"


def test_a_batch_reads_the_signal_at_the_run_boundary(batch_wired, tmp_path,
                                                      monkeypatch):
    """Read only inside the loop over `execute_with_events()`, the signal is
    reached only once a run has something to SAY.

    A run whose executor yields nothing at all — 'No source nodes found' is
    exactly that — therefore never reached it, and every remaining run of a
    malformed batch executed for a reader that had gone. A departure noticed
    between two runs had, by the time it was seen, already made the next run's
    recorder and its two directories.
    """
    _FakeExecutor.script = []          # a malformed run: no events at all
    gate = threading.Event()
    asked = []

    def held_recorder(run_id, **kw):
        asked.append(run_id)
        assert gate.wait(30.0)
        return _FakeRecorder(tmp_path / run_id)

    monkeypatch.setattr(canvas_routes, "get_canvas_recorder", held_recorder)

    with _batch_request(batch_wired, count=4):
        response = canvas_routes.execute_batch()
    stream = response.response

    seen = []
    while not any("event: run_start" in f for f in seen):
        seen.append(next(stream))
    assert wait_for(lambda: len(asked) == 1, 5.0)
    stream.close()                     # the reader goes while run 0 is held
    gate.set()                         # and run 0 is then let through

    assert wait_for(lambda: not canvas_routes.BATCH_ABORT_FLAGS), \
        "the abandoned batch never reached its own cleanup"
    assert len(asked) == 1, \
        "the batch built the remaining runs' recorders for a reader that had gone"


def test_the_same_batch_left_alone_still_makes_every_run(batch_wired):
    """The other half of the two tests above: a batch whose reader stays is
    untouched by either check. All four runs, in order, and nothing of the
    batch left behind afterwards."""
    _FakeExecutor.delay = 0.02
    _FakeExecutor.script = [("progress", {"node_id": f"n{i}"}) for i in range(8)]

    body = batch_wired.test_client().post("/api/canvas/execute-batch", json={
        "workflow": {"nodes": [{"id": "n1"}], "connections": []},
        "count": 4,
    }).get_data(as_text=True)

    assert len(_FakeExecutor.made) == 4
    assert event_names(body)[-1] == "batch_complete"
    assert not canvas_routes.BATCH_ABORT_FLAGS


# ---------------------------------------------------------------------------
# 5. The text proxy
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 6. Stage 3 of /pipeline/generate/stream
# ---------------------------------------------------------------------------

@pytest.fixture()
def stage3_wired(monkeypatch):
    """Stage 3 with every backend it reaches for replaced, and the run stopped
    the moment Stage 3 is done — the cancel check right after `stage3_complete`
    is the nearest exit, so nothing of Stage 4 runs."""
    spr = schema_pipeline_routes
    monkeypatch.setattr(spr, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(spr, "pipeline_executor", object())
    monkeypatch.setattr(spr, "_announce_generation", lambda *a, **kw: None)
    monkeypatch.setattr(spr, "_is_cancelled", lambda device_id, run_id=None: True)
    return spr


def _stage3_data():
    return {"prompt": "ein Satz", "output_config": "stand_in_config",
            "device_id": "stand-in-device", "user_language": "de"}


def test_stage3_writes_the_frames_it_always_wrote(stage3_wired, monkeypatch):
    async def checked(*a, **kw):
        return {"safe": True, "positive_prompt": "ein Satz", "method": "stand_in"}

    monkeypatch.setattr(stage3_wired, "execute_stage3_safety", checked)
    body = "".join(stage3_wired.execute_generation_streaming(_stage3_data()))

    assert event_names(body) == ["connected", "stage3_start", "stage3_complete",
                                 "cancelled"]
    complete = [p for p in event_payloads(body) if p.get("safe") is True]
    assert complete and complete[0]["checks_passed"] == ["stand_in"]
    no_comment_carries_a_payload(body)


def test_stage3_keeps_breathing_while_the_check_runs(stage3_wired, monkeypatch):
    """Between `stage3_start` and `stage3_complete` stand a translation and a
    guard model, on a card that may be busy — and nothing at all went out while
    they ran. The check is HELD here until the reader has heard the transport
    breathe twice."""
    gate = threading.Event()

    async def waiting(*a, **kw):
        assert gate.wait(30.0)
        return {"safe": True, "positive_prompt": "ein Satz", "method": "stand_in"}

    monkeypatch.setattr(stage3_wired, "execute_stage3_safety", waiting)
    stream = stage3_wired.execute_generation_streaming(_stage3_data())
    arrivals, body, held_beats = read_while_held(stream, gate)

    kept_breathing(arrivals, held_beats)
    assert event_names(body) == ["connected", "stage3_start", "stage3_complete",
                                 "cancelled"]
    no_comment_carries_a_payload(body)
