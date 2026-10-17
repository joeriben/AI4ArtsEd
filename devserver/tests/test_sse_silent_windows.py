#!/usr/bin/env python3
"""The stretches of my_app/routes/schema_pipeline_routes.py that said nothing.

Written on 2026-09-05. Opening a stream is not the protection; SPEAKING while
the work runs is. The tunnel in front of this server ends a proxied request
whose origin has been silent for about a hundred seconds and hands the browser
a 524, and it makes no difference to that tunnel whether the silent request was
a plain POST or a stream that opened and then went quiet.

Five such stretches stood in this file, found by MEASURING the wall-clock gap
between two writes of the real generators with every model and pipeline call
stubbed to take a known time, not by reading:

  * /pipeline/interception (GET), between `connected` and `stage_start`: the
    Stage-1 gate, which takes a slot in the plant-wide LLM queue and then calls
    a model.
  * /pipeline/interception (GET), between `stage_start` and `chunk`: the
    interception itself. The loop there wrote only when the model had looked
    something up in Wikipedia, so an ORDINARY run -- the common case, on the
    platform's main working surface, every single time -- sent nothing at all
    from the moment the interception started until it finished.
  * /pipeline/optimize (GET), between `stage_start` and `chunk`: one adaptation
    by a model that is regularly a cloud model behind a tunnel.
  * /compare/analyze-image (POST, stream), before the first piece and between
    two pieces: a vision model to load, a GPU slot to stand in.
  * /pipeline/generate/stream (GET, diffusers), between `stage4_start` and the
    first beat of the progress loop: the station reads the encoders.

Two claims, the sibling files' own, and the reading of the wire is theirs too.

  * THE CONNECTION KEEPS BREATHING. Asserted by HOLDING the work and counting
    what arrives, never by sleeping long enough to hope for it. And the mere
    PRESENCE of a comment frame would not do it: the transport's single
    pre-wait beat passes that, and a stream that beats once and then goes quiet
    is exactly what each of these five was. `test_..._breathes_once_and_then_
    goes_quiet_...` below holds every cadence test against precisely that
    stream and requires it to fail there.

  * THE FRAMES DO NOT MOVE. Every event each generator wrote before it
    breathed, it still writes, unchanged and in the same order; what fills the
    gaps is an SSE comment, which carries no payload and so reaches no consumer
    as an event.

Nothing here reaches a model, a GPU or ComfyUI: every backend is a stand-in.

Run:  python3 -m pytest devserver/tests/test_sse_silent_windows.py -q
"""
import functools
import inspect
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.routes import schema_pipeline_routes as spr
from my_app.services import streaming_response as transport
# The reading of the wire is the sibling file's, once -- `frames_of` calls a
# frame a comment because it begins with ':', `no_comment_carries_a_payload`
# says the other half, and `kept_breathing` holds both halves of the first
# claim above.
from test_sse_transport_sites import (event_names, event_payloads,
                                      kept_breathing,
                                      no_comment_carries_a_payload,
                                      read_while_held)


# ---------------------------------------------------------------------------
# stand-ins
# ---------------------------------------------------------------------------

@dataclass
class StubConfig:
    """A resolved config, as much of one as these generators touch. A dataclass
    because the interception path copies it with `dataclasses.replace`."""
    name: str = "stand_in"
    context: str = ""
    meta: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)


class StubRunResult:
    success = True
    final_output = "the interception result"
    error = None
    metadata: dict = {}


class StubRecorder:
    metadata: dict = {"entities": []}
    # A record that does not say what level it was made under is judged by the
    # strictest one, whatever the request asks for — so a stand-in has to say.
    # These runs are made at the level `resolve_safety_level` is stubbed to.
    safety_level: str = "open"

    def pictures_awaiting_a_verdict(self):
        """Nothing: this stand-in records no entity at all."""
        return []

    def _save_metadata(self):
        pass

    def save_to_prompting_process(self, *a, **kw):
        pass

    def save_error(self, *a, **kw):
        pass

    def save_entity(self, *a, **kw):
        pass

    def get_entity_path(self, *a, **kw):
        return None


class Opened(threading.Event):
    """A gate that was never shut: for the tests about the FRAMES, where the
    work must simply run."""

    def __init__(self):
        super().__init__()
        self.set()


def held_on(gate, result):
    """A stand-in that says nothing until the reader has heard the transport.

    Every cadence test below runs against one of these, so the silence the
    assertions are about is DRIVEN and not raced: the work cannot finish before
    `read_while_held` has counted its beats and opened the gate.
    """
    def stands_still(*args, **kwargs):
        assert gate.wait(30.0), "the gate was never opened"
        return result() if callable(result) else result
    return stands_still


def breathes_once_and_stops(events, *, label, frame, **_writers):
    """The transport as it is when it breathes once and then goes quiet.

    One comment frame, and then the work ON THIS THREAD -- which is exactly the
    shape each window below had before it was wrapped. A cadence test that
    cannot tell this from the real transport asserts nothing, so every one of
    them is run against it and required to fail.
    """
    yield transport.heartbeat_comment(0.0, 1)
    made = events
    # Set however this stand-in ends, exactly as `_pumped` sets it: work that
    # takes the signal can wait on it, and a stand-in that never set it would
    # leave that waiting standing for the rest of the session -- an artefact of
    # the stand-in, in a file whose whole subject is what happens when a reader
    # leaves.
    client_gone = threading.Event()
    if inspect.isfunction(events) or isinstance(events, functools.partial):
        made = (events(client_gone=client_gone)
                if 'client_gone' in inspect.signature(events).parameters
                else events())
    try:
        for item in made:
            yield frame(item)
    finally:
        client_gone.set()


# ---------------------------------------------------------------------------
# the two interception generators — GET /pipeline/interception, /pipeline/optimize
# ---------------------------------------------------------------------------

def _wire_interception(monkeypatch, pipeline_gate):
    """Every backend the interception stream reaches for, replaced."""
    from schemas.engine import config_loader as cl

    class StubExecutor:
        async def execute_pipeline(self, *a, **kw):
            return held_on(pipeline_gate, StubRunResult)()

    monkeypatch.setattr(spr, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(spr, "pipeline_executor", StubExecutor())
    monkeypatch.setattr(spr, "get_recorder", lambda **kw: StubRecorder())
    monkeypatch.setattr(spr, "_resolve_interception_config",
                        lambda name: StubConfig(name=name))
    monkeypatch.setattr(cl, "resolve_context_language", lambda *a, **kw: "")
    monkeypatch.setattr(cl, "wants_passthrough", lambda *a, **kw: False)


def _interception_data():
    return {"schema": "stand_in", "input_text": "ein satz am feldrand",
            "device_id": "stand-in-device", "user_language": "de"}


STAGE1_PASSED = (True, None, ["stand_in"], None, {})


def window_the_stage_1_gate(monkeypatch):
    """Between `connected` and `stage_start`: one slot in the plant-wide LLM
    queue, then a model."""
    gate = threading.Event()
    _wire_interception(monkeypatch, Opened())
    monkeypatch.setattr(spr, "_stage1_check_texts", held_on(gate, STAGE1_PASSED))
    return spr.execute_pipeline_streaming(_interception_data()), gate, 2


def window_the_interception(monkeypatch):
    """Between `stage_start` and `chunk`: the interception. The loop here wrote
    only on a Wikipedia lookup, so an ordinary run wrote nothing at all."""
    gate = threading.Event()
    _wire_interception(monkeypatch, gate)
    monkeypatch.setattr(spr, "_stage1_check_texts",
                        held_on(Opened(), STAGE1_PASSED))
    # Three, because the open Stage-1 gate above contributes the transport's
    # single pre-wait beat: at least two of the beats counted have to come from
    # the window under test.
    return spr.execute_pipeline_streaming(_interception_data()), gate, 3



# ---------------------------------------------------------------------------
# the reading — POST /compare/analyze-image with "stream"
# ---------------------------------------------------------------------------

def _wire_the_reading(monkeypatch, before_first, between_two):
    """A vision model that writes two pieces, each behind a gate of its own."""
    from my_app.services import llm_backend as lb

    class StubStream:
        def __init__(self):
            self.closed = False

        def __iter__(self):
            assert before_first.wait(30.0), "the gate was never opened"
            yield ("token", "a house")
            assert between_two.wait(30.0), "the gate was never opened"
            yield ("token", " at the edge of a field")
            yield ("done", "stop")

        def close(self):
            self.closed = True

    stream = StubStream()
    monkeypatch.setattr(lb, "get_llm_backend",
                        lambda: type("B", (), {"chat_stream": lambda self, **kw: stream})())
    return stream


def window_before_the_first_piece(monkeypatch):
    """A vision model to load and a GPU slot to stand in, before it writes."""
    gate = threading.Event()
    _wire_the_reading(monkeypatch, gate, Opened())
    return spr._stream_image_reading("alias", "a model", "read this", "b64"), gate, 2


def window_between_two_pieces(monkeypatch):
    """A model that has written and then stops for as long as it stops."""
    gate = threading.Event()
    _wire_the_reading(monkeypatch, Opened(), gate)
    # Three: the first piece has already gone out past the transport's pre-wait
    # beat, so two of the counted beats still have to come from this window.
    return spr._stream_image_reading("alias", "a model", "read this", "b64"), gate, 3


# ---------------------------------------------------------------------------
# the generation stream — GET /pipeline/generate/stream, diffusers
# ---------------------------------------------------------------------------

ENCODING_INFO = {"tokens": ["a", "house"], "token_count": 2}


def _wire_the_generation(monkeypatch, encode_gate, model_id="stand-in/model"):
    from my_app.services import model_meta as mm

    class StubLoader:
        def get_config(self, name):
            # `model_id` is where the encoding reading takes the model from
            # since 2026-09-05: the config's own meta, else the MODEL_ID of the
            # chunk that will run. It used to be read off the run's provenance
            # sheet with a literal behind it, and sd35_large declares no
            # model_id at all, so that literal was what every run on this
            # platform's main image config actually sent.
            meta = {"backend_type": "diffusers"}
            if model_id is not None:
                meta["model_id"] = model_id
            return StubConfig(name=name, meta=meta)

    class StubExecutor:
        config_loader = StubLoader()

    class StubEncodeAnswer:
        status_code = 200

        def json(self):
            return dict(ENCODING_INFO)

    class StubRequests:
        def post(self, *a, **kw):
            return held_on(encode_gate, StubEncodeAnswer())(*a, **kw)

        def get(self, *a, **kw):
            raise RuntimeError("the progress endpoint is not part of this test")

    async def checked(*a, **kw):
        return {"safe": True, "positive_prompt": "ein satz", "method": "stand_in"}

    async def generated(**kw):
        return {"success": True, "run_id": kw.get("run_id"), "loras": [],
                "media_output": {"media_type": "image", "url": "stand-in"}}

    monkeypatch.setattr(spr, "resolve_safety_level", lambda: "open")
    monkeypatch.setattr(spr, "pipeline_executor", StubExecutor())
    monkeypatch.setattr(spr, "get_recorder", lambda **kw: StubRecorder())
    monkeypatch.setattr(spr, "execute_stage3_safety", checked)
    monkeypatch.setattr(spr, "execute_stage4_generation_only", generated)
    monkeypatch.setattr(spr, "_announce_generation", lambda *a, **kw: None)
    monkeypatch.setattr(spr, "_release_generation", lambda *a, **kw: None)
    monkeypatch.setattr(spr, "_touch_generation", lambda *a, **kw: None)
    monkeypatch.setattr(spr, "_is_cancelled", lambda device_id, run_id=None: False)
    monkeypatch.setattr(spr, "_try_acquire_generation", lambda *a, **kw: (True, 0))
    monkeypatch.setattr(spr, "_queue_update", lambda *a, **kw: None)
    monkeypatch.setattr(spr, "set_progress_callback", lambda cb: None)
    monkeypatch.setattr(spr, "requests", StubRequests())
    monkeypatch.setattr(mm, "build_model_meta", lambda *a, **kw: {"model_id": "stand-in"})


def _generation_data():
    return {"prompt": "ein satz", "output_config": "stand_in_config",
            "device_id": "stand-in-device", "user_language": "de"}


def window_reading_the_encoders(monkeypatch):
    """Between `stage4_start` and the first beat of the progress loop: the
    station encodes the prompt before it can answer."""
    gate = threading.Event()
    _wire_the_generation(monkeypatch, gate)
    # Three: Stage 3 above is already wrapped and open, and contributes the
    # transport's single pre-wait beat.
    return spr.execute_generation_streaming(_generation_data()), gate, 3


# ---------------------------------------------------------------------------
# 1. every window keeps breathing
# ---------------------------------------------------------------------------

WINDOWS = {
    "the Stage-1 gate of the interception stream": window_the_stage_1_gate,
    "the interception itself": window_the_interception,
    "the reading before its first piece": window_before_the_first_piece,
    "the reading between two pieces": window_between_two_pieces,
    "the encoders being read before stage 4": window_reading_the_encoders,
}


@pytest.mark.parametrize("name", list(WINDOWS))
def test_the_stream_keeps_breathing_while(name, monkeypatch):
    """The work is HELD until the reader has heard the transport breathe, and
    what is asserted is what actually arrived."""
    stream, gate, beats = WINDOWS[name](monkeypatch)
    arrivals, body, held_beats = read_while_held(stream, gate, beats=beats)

    kept_breathing(arrivals, held_beats, beats=beats)
    no_comment_carries_a_payload(body)


@pytest.mark.parametrize("name", list(WINDOWS))
def test_a_stream_that_breathes_once_and_then_goes_quiet_fails_that(
        name, monkeypatch):
    """The other half, and the reason the test above is written the way it is.

    With the transport replaced by one that writes a single comment and then
    runs the work in silence -- which is what each of these windows was -- the
    assertion above has to fail. A test that passes here would be pinning
    nothing.
    """
    monkeypatch.setattr(spr, "events_with_heartbeat", breathes_once_and_stops)
    stream, gate, beats = WINDOWS[name](monkeypatch)
    # The beats never come here, so it is the watchdog that lets the work go.
    # Five seconds rather than the helper's twelve: that is already longer than
    # the widest silence `kept_breathing` tolerates, and the six windows below
    # would otherwise cost this suite a minute and a half of waiting.
    arrivals, body, held_beats = read_while_held(stream, gate, beats=beats,
                                                 watchdog_after=5.0)

    with pytest.raises(AssertionError):
        kept_breathing(arrivals, held_beats, beats=beats)


# ---------------------------------------------------------------------------
# 2. the frames do not move
# ---------------------------------------------------------------------------

def frames_of_an_open_run(monkeypatch, window):
    """The same generator with every gate open, read to its end."""
    stream, gate, _beats = window(monkeypatch)
    gate.set()
    return "".join(chunk for chunk in stream)


def test_the_interception_stream_writes_the_frames_it_always_wrote(monkeypatch):
    body = frames_of_an_open_run(monkeypatch, window_the_interception)

    assert event_names(body) == ["connected", "stage_start", "chunk", "complete"]
    chunk = [p for p in event_payloads(body) if p.get("stage") == 2
             and "text_chunk" in p]
    assert chunk and chunk[0]["accumulated"] == StubRunResult.final_output
    no_comment_carries_a_payload(body)



def test_the_reading_writes_the_pieces_it_always_wrote(monkeypatch):
    body = frames_of_an_open_run(monkeypatch, window_before_the_first_piece)

    payloads = event_payloads(body)
    assert [p["type"] for p in payloads] == ["token", "token", "done"]
    assert "".join(p["text"] for p in payloads if p["type"] == "token") == \
        "a house at the edge of a field"
    assert payloads[-1]["finish_reason"] == "stop"
    # Counted as it left this server, which is what the page holds its own
    # count against.
    assert payloads[-1]["char_count"] == len("a house at the edge of a field")
    no_comment_carries_a_payload(body)


def test_the_generation_stream_still_says_what_the_encoders_read(monkeypatch):
    """The one event whose emission moved: it is written from the generator as
    before, after the reading it reports, with the payload it always had."""
    body = frames_of_an_open_run(monkeypatch, window_reading_the_encoders)

    assert event_names(body) == ["connected", "stage3_start", "stage3_complete",
                                 "stage4_start", "encoding_info", "complete"]
    encoding = [p for p in event_payloads(body) if "token_count" in p]
    assert encoding == [ENCODING_INFO]
    no_comment_carries_a_payload(body)


def test_a_station_that_says_nothing_about_the_encoders_leaves_the_run_alone(
        monkeypatch):
    """Best-effort, exactly as before: the event is simply absent, and the
    generation goes on."""
    class Refused:
        status_code = 503

        def json(self):
            return {}

    _wire_the_generation(monkeypatch, Opened())
    monkeypatch.setattr(spr.requests, "post", lambda *a, **kw: Refused())
    body = "".join(spr.execute_generation_streaming(_generation_data()))

    assert event_names(body) == ["connected", "stage3_start", "stage3_complete",
                                 "stage4_start", "complete"]


def test_a_refusal_by_stage_1_still_ends_the_stream_where_it_always_did(
        monkeypatch):
    """The path the wrapping had to leave alone. What the gate decided is now
    read back out of the worker's result, and a refusal has to reach the same
    `blocked` event, with the same fields, and stop the run there."""
    _wire_interception(monkeypatch, Opened())
    monkeypatch.setattr(
        spr, "_stage1_check_texts",
        lambda *a, **kw: (False, "Kids-Filter: nicht erlaubt", ["fast_filter"],
                          "input_text", {}))

    body = "".join(spr.execute_pipeline_streaming(_interception_data()))

    assert event_names(body) == ["connected", "blocked"]
    blocked = event_payloads(body)[-1]
    assert blocked["stage"] == "safety"
    assert blocked["reason"] == "Kids-Filter: nicht erlaubt"
    assert blocked["checks_passed"] == ["fast_filter"]


def test_an_interception_that_raised_still_arrives_as_the_error_event(
        monkeypatch):
    """The pipeline runs on an executor of its own and the notices around it
    now run under the transport, so the failure travels a longer way. It still
    ends as this generator's own `error` event and not as a torn stream."""
    class Broken:
        async def execute_pipeline(self, *a, **kw):
            raise RuntimeError("the station was not there")

    _wire_interception(monkeypatch, Opened())
    monkeypatch.setattr(spr, "pipeline_executor", Broken())
    monkeypatch.setattr(spr, "_stage1_check_texts",
                        held_on(Opened(), STAGE1_PASSED))

    body = "".join(spr.execute_pipeline_streaming(_interception_data()))

    assert event_names(body) == ["connected", "stage_start", "error"]
    assert "the station was not there" in event_payloads(body)[-1]["message"]


# ---------------------------------------------------------------------------
# 3. the reading is told when its reader leaves
# ---------------------------------------------------------------------------

def test_a_reading_whose_page_went_away_stops_and_releases_the_model(monkeypatch):
    """Before the wrapping this arrived as a `GeneratorExit` at the reading's
    own yield; on a thread it never does, so the source reads the leaving
    signal instead. Closing the stream is what ends the generation on the GPU
    service and releases the model."""
    from my_app.services import llm_backend as lb

    state = {"closed": False, "pieces": 0}
    let_go = threading.Event()

    class StubStream:
        def __iter__(self):
            while True:
                assert let_go.wait(30.0), "the reading was never let go"
                state["pieces"] += 1
                yield ("token", "another piece ")

        def close(self):
            state["closed"] = True

    monkeypatch.setattr(lb, "get_llm_backend",
                        lambda: type("B", (), {"chat_stream": lambda self, **kw: StubStream()})())

    stream = spr._stream_image_reading("alias", "a model", "read this", "b64")
    next(stream)                      # the first breath
    stream.close()                    # the page goes away
    let_go.set()                      # and only now does the model write again

    deadline = time.time() + 5.0
    while time.time() < deadline and not state["closed"]:
        time.sleep(0.02)
    assert state["closed"], "the reading went on with nobody at the other end"
