#!/usr/bin/env python3
"""The routes that answer ONE result, now that the shared transport carries them.

Seven of them on 2026-09-04, and the Wikimedia Commons lookup
(/api/commons/lookup) on 2026-09-05 -- the longest silent POST on this platform,
which is why it is here at all: at the kids and youth levels it works through up
to MAX_CHECK_CANDIDATES pictures, each costing two model calls by the service's
own reckoning, on top of the call that turns the prompt into a search term.

Written on 2026-09-04, alongside the change that put `streamed_answer`
(my_app/services/streaming_response.py) under the three media readings
(/api/media/analyze/image, /av, /compare), the Fusion Workbench cell
(/api/fusion_workbench/generate) and the three Crossmodal Lab generations
(/api/cross_aesthetic/synth, /mmaudio, /image_guided_audio).

test_sse_transport_sites.py is the precedent and this file takes its reading
helpers from it rather than making a third copy of them: that file pins the
same claims for the routes that answer a STREAM of events, this one for the
routes that answer a single body. What the two shapes have in common is the one
loop underneath, and the assertions about it are therefore also one.

Two claims, and the first is the reason any of this was built.

  * THE CONNECTION KEEPS BREATHING. The tunnel in front of this server ends a
    proxied request whose origin has been silent for about a hundred seconds and
    hands the browser a 524. Behind every route below stands work that is
    regularly silent for longer than that -- a vision model that has to be
    loaded, a card that has to be waited for, a generation that takes as long as
    it takes -- so a stretch in which the work says nothing must be a stretch in
    which frames still go out. That is asserted by HOLDING the work and counting
    what arrives, never by sleeping long enough to hope for it. Asserting the
    mere PRESENCE of one comment frame would not do it: a transport that emits
    its single pre-wait beat and then never breathes again passes that, and it
    is exactly the failure this change exists to end.

  * ONLY THE TRANSPORT CHANGED. Each route answers the same body and the same
    HTTP status it always did, and that is stated as an EQUALITY between the two
    ways back: the same request against the same stand-in, once as a plain POST
    and once as a stream, has to come out the same. Read against a literal
    written into this file instead, the claim would only be that the streamed
    answer is what a test author expected -- which is a different and much
    weaker thing.

And one property this change introduced: the two words that ask for the stream
stop at the proxy boundary. `postStreamedRun` writes both of them into every
body it sends, and on this platform "enable_streaming" already names two
different protocols depending on which route reads it.

Nothing here reaches a model, a GPU or ComfyUI: every backend is a stand-in.

Run:  python3 -m pytest devserver/tests/test_sse_transport_answer_sites.py -q
"""
import ast
import functools
import inspect
import json
import re
import sys
import threading
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

import config
from my_app.routes import (commons_routes, cross_aesthetic_routes,
                           fusion_workbench_routes, media_routes)
from my_app.services import commons_service
from my_app.services.streaming_response import (answered_either_way,
                                                sse_response, streamed_answer)
# The reading of the wire is the sibling file's, once. `frames_of` calls a frame
# a comment because it begins with ':', `no_comment_carries_a_payload` says the
# other half, and `kept_breathing` holds both halves of the first claim above.
from test_sse_transport_sites import (kept_breathing,
                                      no_comment_carries_a_payload,
                                      read_while_held)


# ---------------------------------------------------------------------------
# reading the wire, and holding the work
# ---------------------------------------------------------------------------

def answer(body: str):
    """The terminal frame, as the ``(payload, http_status)`` a plain POST would
    have returned. Reproducing that pair exactly is the whole contract of this
    transport, and services/directRun.ts reads precisely these two fields."""
    for raw in body.split("\n\n"):
        if not raw.startswith("event: complete"):
            continue
        frame = json.loads(raw.split("data: ", 1)[1])
        return frame["body"], frame["http_status"]
    raise AssertionError(f"no terminal frame on this wire: {body[:400]!r}")


class Held:
    """A backend that says nothing until the reader has heard the transport.

    Every breathing test below runs its route against one of these, so the
    silence the assertions are about is DRIVEN and not raced: the work cannot
    finish before `read_while_held` has counted its beats and opened the gate.
    `seen` keeps what the route asked it for, which is where the last section
    of this file reads what actually travelled on.
    """

    def __init__(self, result):
        self.gate = threading.Event()
        self.result = result
        self.seen = []

    def __call__(self, *args, **kwargs):
        self.seen.append((args, kwargs))
        assert self.gate.wait(30.0), "the gate was never opened"
        return self.result

    def opened(self):
        """The same stand-in with nothing held back, for the parity tests."""
        self.gate.set()
        return self


class Ran:
    """What the local station hands back since it is ComfyUI (llm_client
    `_track`): the run, as much of it as the client reads -- the node's ui
    output under its node id in `outputs_metadata`."""

    def __init__(self, content):
        from my_app.services.llm_client import NODE_ID
        self.prompt_id = "stand-in-prompt"
        self.outputs_metadata = {NODE_ID: {"content": [content], "thinking": [""],
                                           "finish_reason": ["stop"],
                                           "prompt_tokens": [1], "completion_tokens": [1]}}


# `Answered`, what `requests.post` handed back, stood here while a route of
# this file still posted for itself: the comparison until stage 3 of the move
# to ComfyUI (2026-09-07), the AV reading and the crossmodal generations until
# stage 6 (2026-09-14). Every one of them is one run of a node at ComfyUI now
# (`Made`, below), and no route on this transport posts to a station.


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(media_routes.media_bp)
    app.register_blueprint(fusion_workbench_routes.fusion_workbench_bp)
    app.register_blueprint(cross_aesthetic_routes.cross_aesthetic_bp)
    app.register_blueprint(commons_routes.commons_bp)
    return app


def nothing_may_buffer_this(response) -> None:
    """The two headers, asserted on every streamed answer this file drives.

    Not decoration, and the reason they are checked at all: nginx buffers a
    proxied response by default, and a buffered stream is an origin that has
    sent nothing -- which is the 524 this whole change exists to prevent,
    reinstated at the last hop before the browser. Stripped from all seven
    routes, the twenty-five tests written on 2026-09-04 stayed green.
    """
    assert response.mimetype == "text/event-stream", response.mimetype
    assert response.headers.get("Cache-Control") == "no-cache", \
        dict(response.headers)
    assert response.headers.get("X-Accel-Buffering") == "no", \
        dict(response.headers)


def both_ways(app, path, body):
    """The same request over both transports: ``(plain, streamed)``, each as the
    ``(payload, http_status)`` pair the caller ends up with."""
    client = app.test_client()
    plain = client.post(path, json=body)
    streamed = client.post(path, json={**body, "enable_streaming": True})
    nothing_may_buffer_this(streamed)
    assert plain.mimetype == "application/json", plain.mimetype
    return (plain.get_json(), plain.status_code), answer(streamed.get_data(as_text=True))


def breathed(response, held):
    """Read a held stream to its end and pin the first claim on what arrived."""
    nothing_may_buffer_this(response)
    arrivals, body, beats = read_while_held(response.response, held.gate)
    kept_breathing(arrivals, beats)
    no_comment_carries_a_payload(body)
    return answer(body)


def read_and_leave(stream, held, frames=2, watchdog_after=12.0):
    """Read a held stream for a few frames and then ABANDON it, as a closed tab
    does. Returns what had arrived; the work behind it is still running."""
    arrivals, body = [], ""
    watchdog = threading.Timer(watchdog_after, held.gate.set)
    watchdog.daemon = True
    watchdog.start()
    try:
        for chunk in stream:
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
            if not text:
                continue
            arrivals.append(text)
            body += text
            if len(arrivals) >= frames:
                break
    finally:
        watchdog.cancel()
        stream.close()
    return arrivals, body


# ---------------------------------------------------------------------------
# 1. The image reading — /api/media/analyze/image
# ---------------------------------------------------------------------------

IMAGE_READING = "a house at the edge of a field"


@pytest.fixture()
def uploaded_image(tmp_path, monkeypatch):
    """A file inside the uploads directory, which is the only place this route
    will read from."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    path = uploads / "stand_in.png"
    # A real bitmap: since 2026-09-09 the plain reading sends the picture
    # through the vision envelope (media_ref.encode_image_b64) instead of the
    # file's raw bytes, so an undecodable stand-in is answered with 500 here
    # rather than reaching the transport these tests are about.
    from PIL import Image
    Image.new("RGB", (120, 90), (10, 20, 30)).save(path)
    monkeypatch.setattr(media_routes, "UPLOADS_TMP_DIR", uploads)
    return path


def hold_the_vision_model(monkeypatch, reading=IMAGE_READING):
    from my_app.services.llm_service import llm_service
    held = Held(reading)
    monkeypatch.setattr(llm_service, "analyze_image", held)
    return held


def test_the_image_reading_keeps_breathing_while_the_model_is_silent(
        app, uploaded_image, monkeypatch):
    """A vision model has to be loaded before it can look at anything, and it
    waits its turn for the card like every other piece of work here. Nothing at
    all went out while it did."""
    held = hold_the_vision_model(monkeypatch)
    with app.test_request_context('/api/media/analyze/image',
                                  json={"image_path": str(uploaded_image),
                                        "enable_streaming": True}):
        response = media_routes.analyze_image_file()

    payload, http_status = breathed(response, held)
    assert http_status == 200
    assert payload["analysis"] == IMAGE_READING


@pytest.mark.parametrize("body", [
    pytest.param({}, id="a body with no picture in it"),
    pytest.param({"image_path": "/etc/passwd"}, id="a path outside the uploads"),
])
def test_the_image_reading_refuses_the_same_either_way(app, uploaded_image, body):
    """A refusal is an answer, and it travels with its status. Nothing is held
    here: none of these reach a model at all."""
    plain, streamed = both_ways(app, '/api/media/analyze/image', body)
    assert plain == streamed
    assert plain[1] == 400


def test_the_image_reading_answers_the_same_either_way(app, uploaded_image,
                                                       monkeypatch):
    hold_the_vision_model(monkeypatch).opened()
    plain, streamed = both_ways(app, '/api/media/analyze/image',
                                {"image_path": str(uploaded_image)})
    assert plain == streamed
    assert plain == ({"success": True, "analysis": IMAGE_READING}, 200)


def test_a_reading_that_did_not_come_back_is_the_same_failure_either_way(
        app, uploaded_image, monkeypatch):
    """The 502 the surface reads as "the model said nothing" — usePictureTemplate
    branches on exactly this status, so it has to survive the trip."""
    hold_the_vision_model(monkeypatch, reading="").opened()
    plain, streamed = both_ways(app, '/api/media/analyze/image',
                                {"image_path": str(uploaded_image)})
    assert plain == streamed
    assert plain == ({"error": "Image analysis failed"}, 502)


# ---------------------------------------------------------------------------
# 2. The audio and video reading — /api/media/analyze/av
# ---------------------------------------------------------------------------

AV_READING = "a low hum, and a door somewhere behind it"


class Recorder:
    """A run, as much of one as this route reads."""

    def __init__(self, folder, entities):
        self.metadata = {"entities": entities}
        self.final_folder = folder


@pytest.fixture()
def recorded_audio(tmp_path, monkeypatch):
    folder = tmp_path / "run_stand_in"
    folder.mkdir()
    (folder / "output_audio.wav").write_bytes(b"never decoded here")
    monkeypatch.setattr(
        media_routes, "load_recorder",
        lambda run_id, base_path=None: Recorder(
            folder, [{"type": "output_audio", "filename": "output_audio.wav"}]))
    return folder


class Made:
    """What a media station hands back since it is ComfyUI (llm_client
    `_track`): the run, as much of it as the station clients read -- the
    node's ui output under its node id, and the files the node announced."""

    def __init__(self, ui, files=()):
        from my_app.services.llm_client import NODE_ID
        self.prompt_id = "stand-in-prompt"
        self.outputs_metadata = {NODE_ID: {k: [v] for k, v in ui.items()}}
        self.media_files = list(files)


class Broke:
    """A run that ended in the node's own error, as the tracking raises it."""

    def __init__(self, sentence):
        self.sentence = sentence
        self.seen = []

    def __call__(self, *args, **kwargs):
        self.seen.append((args, kwargs))
        raise RuntimeError(self.sentence)


def hold_the_local_station(monkeypatch, held):
    """Every local reading is one run at ComfyUI, on the client's own thread;
    `held` stands in for that run."""
    from my_app.services.llm_client import LLMClient
    monkeypatch.setattr(LLMClient, "_track", held)
    return held


def hold_the_reading(monkeypatch, held):
    """A reading is one run of the reading node at ComfyUI: the file goes into
    ComfyUI's input directory first (llm_client.upload_input), the run follows
    on the client's own thread. `held` stands in for the run; the upload is
    answered here, without a ComfyUI, with the name the client chose."""
    from my_app.services import llm_client
    monkeypatch.setattr(llm_client, "upload_input", lambda data, name: name)
    return hold_the_local_station(monkeypatch, held)


def the_inputs_of(held):
    """The node inputs the route handed to the run: what travelled on."""
    from my_app.services.llm_client import NODE_ID
    args, kwargs = held.seen[0]
    workflow = args[0] if args else kwargs["workflow"]
    return workflow[NODE_ID]["inputs"]


def test_the_av_reading_keeps_breathing_while_the_station_is_silent(
        app, recorded_audio, monkeypatch):
    """The listening is one run of the reading node at ComfyUI, whose first
    call loads the model and whose clips are as long as they are."""
    held = hold_the_reading(monkeypatch, Held(Made({"analysis": AV_READING})))

    with app.test_request_context('/api/media/analyze/av',
                                  json={"run_id": "run_stand_in", "kind": "audio",
                                        "enable_streaming": True}):
        response = media_routes.analyze_av_file()

    payload, http_status = breathed(response, held)
    assert http_status == 200
    assert payload["analysis"] == AV_READING


def test_the_av_reading_answers_the_same_either_way(app, recorded_audio, monkeypatch):
    hold_the_reading(monkeypatch, Held(Made({"analysis": AV_READING})).opened())
    plain, streamed = both_ways(app, '/api/media/analyze/av',
                                {"run_id": "run_stand_in", "kind": "audio"})
    assert plain == streamed
    assert plain == ({"success": True, "analysis": AV_READING}, 200)


def test_a_run_that_broke_is_the_same_500_with_its_own_sentence_either_way(
        app, recorded_audio, monkeypatch):
    """The run's own sentence goes through. A reading that broke at ComfyUI
    answers 500 with the node's error in it (media_analysis_client.last_reason),
    and the stream must not flatten that into anything else. Until stage 6 of
    the move to ComfyUI this held the GPU service's 503 for a taken card; the
    card is ComfyUI's queue now, and a run waits in it instead of being
    refused."""
    hold_the_reading(monkeypatch, Broke("ComfyUI execution error in the reading: no such reader"))
    plain, streamed = both_ways(app, '/api/media/analyze/av',
                                {"run_id": "run_stand_in", "kind": "audio"})
    assert plain == streamed
    assert plain == ({"error": "ComfyUI execution error in the reading: no such reader"}, 500)


# ---------------------------------------------------------------------------
# 3. The comparison — /api/media/analyze/compare
# ---------------------------------------------------------------------------

COMPARISON = "both hold still, and only one of them lets the light in"

TWO_READINGS = {"parts": [{"label": "Work A", "text": "a house"},
                          {"label": "Work B", "text": "a field"}]}


@pytest.fixture()
def analysis_model(monkeypatch):
    """The route asks config for the model it reads with; the name here is a
    stand-in, and no request built from it leaves this process. The local
    station is ComfyUI (llm_client): the stand-in is made a known, installed
    local model there, and the run itself is what each test holds."""
    from my_app.services import local_llm_weights
    monkeypatch.setattr(config, "IMAGE_ANALYSIS_MODEL", "local/stand-in-reader")
    monkeypatch.setattr(local_llm_weights, "dir_name", lambda model_id: "stand-in-reader")
    monkeypatch.setattr(local_llm_weights, "is_installed", lambda model_id: True)


def test_the_comparison_keeps_breathing_while_the_model_writes(
        app, analysis_model, monkeypatch):
    """One call with two whole readings in the prompt, and the model writes for
    as long as it writes."""
    held = hold_the_local_station(monkeypatch, Held(Ran(COMPARISON)))

    with app.test_request_context('/api/media/analyze/compare',
                                  json={**TWO_READINGS, "enable_streaming": True}):
        response = media_routes.analyze_media_compare()

    payload, http_status = breathed(response, held)
    assert http_status == 200
    assert payload["comparison"] == COMPARISON


def test_the_comparison_answers_the_same_either_way(app, analysis_model, monkeypatch):
    hold_the_local_station(monkeypatch, Held(Ran(COMPARISON)).opened())
    plain, streamed = both_ways(app, '/api/media/analyze/compare', TWO_READINGS)
    assert plain == streamed
    assert plain == ({"success": True, "comparison": COMPARISON}, 200)


def test_the_comparison_refuses_the_same_either_way(app, analysis_model):
    """One reading is no comparison, and this refusal never reaches a model."""
    plain, streamed = both_ways(app, '/api/media/analyze/compare',
                                {"parts": [{"label": "Work A", "text": "a house"}]})
    assert plain == streamed
    assert plain == ({"error": "exactly two parts with text are required"}, 400)


# ---------------------------------------------------------------------------
# 4. The Fusion Workbench cell — /api/fusion_workbench/generate
# ---------------------------------------------------------------------------

CELL = {"prompt": "a house", "alpha_factor": 20.0, "seed": 42}


def hold_the_workbench_run(monkeypatch, held):
    """The cell's one run at ComfyUI (latent_lab_context_graphs.run_graph),
    held: `held` is asked with the graph the route built and answers the
    picture, base64. The checkpoint is named without a card. Until stage 4 of
    the move to ComfyUI this was a POST of the route's own, held the way the
    Crossmodal Lab's still are."""
    from my_app.services import latent_lab_context_graphs as graphs

    async def checkpoint_of(model_id, tag):
        return "OfficialStableDiffusion/sd3.5_large.safetensors", model_id or "stand-in/model"

    async def run_graph(graph, workload, tag):
        return held(graph, workload=workload, tag=tag)

    monkeypatch.setattr(graphs, "checkpoint_of", checkpoint_of)
    monkeypatch.setattr(graphs, "run_graph", run_graph)
    return held


def test_the_workbench_cell_keeps_breathing_while_the_card_is_busy(app, monkeypatch):
    """A sweep sends these one after another, and each one stands in the
    plant-wide GPU queue before it renders. The 524 used to end the whole sweep
    on a cell the card had already made."""
    held = hold_the_workbench_run(monkeypatch, Held("QUJD"))

    with app.test_request_context('/api/fusion_workbench/generate',
                                  json={**CELL, "enable_streaming": True}):
        response = fusion_workbench_routes.generate()

    payload, http_status = breathed(response, held)
    assert http_status == 200
    assert payload["image_base64"] == "QUJD" and payload["seed"] == 42


def test_the_workbench_cell_answers_the_same_either_way(app, monkeypatch):
    hold_the_workbench_run(monkeypatch, Held("QUJD").opened())
    plain, streamed = both_ways(app, '/api/fusion_workbench/generate', CELL)
    assert plain == streamed
    assert plain[1] == 200


def test_a_busy_card_stays_a_503_on_the_workbench_cell(app, monkeypatch):
    """views/latent_lab/fusion_workbench.vue reads `error` off the rejection and
    puts it through the platform's classifier, so both have to arrive."""
    from my_app.services.gpu_lease_client import GpuBusyError

    def refuse(*args, **kwargs):
        raise GpuBusyError("queue full")

    hold_the_workbench_run(monkeypatch, refuse)
    plain, streamed = both_ways(app, '/api/fusion_workbench/generate', CELL)
    assert plain == streamed
    assert plain == ({"success": False, "error": "the card is busy: queue full"}, 503)


def test_the_transport_flags_do_not_reach_the_workbench_graph(app, monkeypatch):
    """The workbench's station is ComfyUI, asked with a graph. The words that
    ask for the stream stand nowhere in it, whether they were true or false,
    and what the caller sent is in it: the prompt at the encoder, alpha at the
    fusion, the seed at the sampler."""
    held = hold_the_workbench_run(monkeypatch, Held("QUJD").opened())
    for flags in ({"enable_streaming": True, "enable_answer_streaming": True},
                  {"enable_streaming": False, "enable_answer_streaming": False}):
        answer = app.test_client().post('/api/fusion_workbench/generate',
                                        json={**CELL, **flags})
        answer.get_data()
    assert len(held.seen) == 2
    for args, _kwargs in held.seen:
        graph = args[0]
        wire = json.dumps(graph)
        assert "enable_streaming" not in wire and "enable_answer_streaming" not in wire
        assert graph["10"]["inputs"]["text"] == "a house"
        assert graph["17"]["inputs"]["alpha"] == 20.0
        assert graph["20"]["inputs"]["seed"] == 42


# ---------------------------------------------------------------------------
# 5. The Crossmodal Lab generations — /api/cross_aesthetic/*
# ---------------------------------------------------------------------------

# What a station's node writes beside the sound it announces: the synth's
# statistics and contributions as JSON text, the guidance's similarity, and
# the seed and the clock every one of them reports.
SOUND_UI = {"seed": 42, "generation_time_ms": 1234, "sample_rate": 44100,
            "duration_seconds": 1.0, "embedding_stats": "{}",
            "axis_contributions": "[]", "cosine_similarity": 0.5}

CROSSMODAL = [
    pytest.param('/api/cross_aesthetic/synth',
                 {"prompt_a": "sound", "duration_seconds": 1.0}, id="synth"),
    pytest.param('/api/cross_aesthetic/mmaudio',
                 {"prompt": "rain on a roof", "duration_seconds": 10.0}, id="mmaudio"),
    # The guidance is guided by a picture and refuses without one (400, as
    # the station did); the surface always sends one.
    pytest.param('/api/cross_aesthetic/image_guided_audio',
                 {"prompt": "rain on a roof", "lambda_guidance": 5.0,
                  "image_base64": "QUJD"},
                 id="image_guided_audio"),
]

# The two of them whose node takes a picture. Until stage 6 of the move to
# ComfyUI the proxy read `image_path` for every route it forwarded; the synth
# has no picture, and its route reads none.
WITH_A_PICTURE = [p for p in CROSSMODAL if p.id != "synth"]


def a_sound(data=b"ABC"):
    """The file a station's node announces under "audio"."""
    from my_app.services.comfyui_ws_client import MediaFile
    return MediaFile(data=data, filename="stand_in.wav", media_type="audio")


def hold_the_stations(monkeypatch):
    """Every station whole, as the package would report it off the stations
    endpoint, and the tier's reading of the card stood in with the table's
    own medium alias; nothing here names a model."""
    from my_app.services import local_media_weights as weights
    from my_app.services import media_stations, stable_audio_tier
    medium = weights.stable_audio_policy()["medium"]
    stations = {station: {"library": True, "error": "",
                          "installed": [weights.dir_name(a) for a in weights.aliases_of_station(station)]}
                for station in weights.stations()}
    monkeypatch.setattr(media_stations, "read", lambda: stations)
    monkeypatch.setattr(stable_audio_tier, "alias", lambda kind="music": medium)
    monkeypatch.setattr(stable_audio_tier, "dir_name", lambda kind="music": weights.dir_name(medium))


def hold_the_station_run(monkeypatch, held):
    """A crossmodal generation is one run of a node at ComfyUI, with the
    stations read first; `held` stands in for the run."""
    hold_the_stations(monkeypatch)
    return hold_the_local_station(monkeypatch, held)


@pytest.mark.parametrize("path,body", CROSSMODAL)
def test_a_crossmodal_generation_keeps_breathing_while_the_card_is_busy(
        app, monkeypatch, path, body):
    """Each of these makes sound on the shared card and stands in ComfyUI's
    queue before it does; ten seconds of MMAudio is minutes of silence."""
    held = hold_the_station_run(monkeypatch, Held(Made(SOUND_UI, [a_sound()])))

    with app.test_request_context(path, json={**body, "enable_streaming": True}):
        response = app.view_functions[
            f"cross_aesthetic.{path.rsplit('/', 1)[1]}"]()

    payload, http_status = breathed(response, held)
    assert http_status == 200
    assert payload["audio_base64"] == "QUJD"


@pytest.mark.parametrize("path,body", CROSSMODAL)
def test_a_crossmodal_generation_answers_the_same_either_way(app, monkeypatch,
                                                             path, body):
    hold_the_station_run(monkeypatch, Held(Made(SOUND_UI, [a_sound()])).opened())
    plain, streamed = both_ways(app, path, body)
    assert plain == streamed
    assert plain[1] == 200


@pytest.mark.parametrize("path,body", WITH_A_PICTURE)
def test_a_picture_that_cannot_be_read_is_the_same_400_either_way(app, monkeypatch,
                                                                  path, body):
    """The route reads the picture off this server's disk before it hands
    anything to the node, and a path it cannot read is a refusal of its own."""
    hold_the_station_run(monkeypatch, Held(Made(SOUND_UI, [a_sound()])).opened())
    plain, streamed = both_ways(app, path,
                                {**body, "image_path": "/nowhere/at/all.png"})
    assert plain == streamed
    assert plain[1] == 400
    assert plain[0]["success"] is False


# ---------------------------------------------------------------------------
# 6. The words that ask for the stream stop at the proxy boundary
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,body", [
    pytest.param('/api/cross_aesthetic/synth', {"prompt_a": "sound"}, id="cross_aesthetic"),
])
def test_the_transport_flags_do_not_travel_on_to_the_station(app, monkeypatch,
                                                             path, body):
    """`postStreamedRun` writes both names of the stream into every body it
    sends. They say how the answer is to come back from THIS server, and the
    node behind the route is asked for one generation either way -- while on
    this platform "enable_streaming" already names two different protocols
    depending on which route reads it. Everything the caller actually sent still
    goes on, unchanged, as the node's inputs."""
    held = hold_the_station_run(monkeypatch, Held(Made(SOUND_UI, [a_sound()])).opened())

    # The answer is READ and not only asked for: a streamed route hands back a
    # generator, and the work behind it runs on a thread of its own. Asserting
    # on what that thread forwarded without draining the stream first was a
    # race, and it passed only for as long as the forwarding happened to be the
    # first thing the thread did.
    answer = app.test_client().post(path, json={**body, "enable_streaming": True,
                                                "enable_answer_streaming": True})
    answer.get_data()

    forwarded = the_inputs_of(held)
    assert "enable_streaming" not in forwarded
    assert "enable_answer_streaming" not in forwarded
    for key, value in body.items():
        assert forwarded[key] == value


@pytest.mark.parametrize("path,body", CROSSMODAL)
def test_the_node_is_handed_the_same_inputs_whichever_way_the_answer_is_asked_for(
        app, monkeypatch, path, body):
    """The two tests around this one can only say that the flags are not
    among the node's inputs, which no route could manage, since the inputs
    are built from named keys. What they cannot say is that the plain and the
    streamed way build the same inputs: the same run, asked for twice. The
    seed is fixed, since -1 draws one."""
    held = hold_the_station_run(monkeypatch, Held(Made(SOUND_UI, [a_sound()])).opened())
    client = app.test_client()
    client.post(path, json={**body, "seed": 7}).get_data()
    client.post(path, json={**body, "seed": 7, "enable_streaming": True,
                            "enable_answer_streaming": True}).get_data()
    assert len(held.seen) == 2
    inputs = [the_inputs_of_call(call) for call in held.seen]
    assert inputs[0] == inputs[1]
    assert inputs[0]["seed"] == 7


def the_inputs_of_call(call):
    from my_app.services.llm_client import NODE_ID
    args, kwargs = call
    workflow = args[0] if args else kwargs["workflow"]
    return workflow[NODE_ID]["inputs"]


@pytest.mark.parametrize("path,body", [
    pytest.param('/api/cross_aesthetic/synth', {"prompt_a": "sound"}, id="cross_aesthetic"),
])
def test_the_transport_flags_stop_here_on_the_plain_path_too(app, monkeypatch,
                                                             path, body):
    """The half the test above cannot reach. It posts with the streaming flags
    set and therefore only ever exercises the streamed branch, so the stripping
    on the plain branch was never driven at all -- and both branches forward
    the same body, which is exactly the kind of shared code a test that runs
    one path twice cannot tell apart.

    Both words are sent, and both say NO. That is the one body left that
    reaches the plain branch with something still to strip: since 2026-09-05
    EITHER word opens the stream when it is true (`asks_for_the_stream`), so a
    body that asks for no stream is one whose words are false or absent -- and
    a word that is present and false is still a word this proxy must not pass
    on. Until that day this test asked with "enable_answer_streaming" alone,
    which reached the plain branch only because the transport read the other
    word: it was driving the very trap that change closed."""
    held = hold_the_station_run(monkeypatch, Held(Made(SOUND_UI, [a_sound()])).opened())

    response = app.test_client().post(
        path, json={**body, "enable_streaming": False,
                    "enable_answer_streaming": False})
    assert response.mimetype == "application/json"

    forwarded = the_inputs_of(held)
    assert "enable_streaming" not in forwarded
    assert "enable_answer_streaming" not in forwarded
    for key, value in body.items():
        assert forwarded[key] == value


# ---------------------------------------------------------------------------
# 7. A body that is not an object
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    pytest.param("hello", id="a string"),
    pytest.param([1, 2], id="a list"),
])
@pytest.mark.parametrize("path", [
    '/api/media/analyze/image',
    '/api/media/analyze/av',
    '/api/media/analyze/compare',
    '/api/fusion_workbench/generate',
    '/api/fusion_workbench/expand_t5',
    '/api/cross_aesthetic/synth',
    '/api/cross_aesthetic/mmaudio',
    '/api/cross_aesthetic/image_guided_audio',
    '/api/commons/lookup',
])
def test_a_body_that_is_not_an_object_is_a_400_and_says_so(app, path, body):
    """A caller's mistake, named as one.

    Moving the body-reading to the request boundary put the dict operations
    outside the runs' own `try`, so `"hello"` reached `.items()` or `.get()` and
    Flask answered an HTML 500 page: a fault of this server where a caller's
    mistake stands, with no field a caller can read and no cause in it."""
    response = app.test_client().post(path, json=body)
    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert "object" in response.get_json()["error"]


# ---------------------------------------------------------------------------
# 8. The picture the Crossmodal Lab is handed
# ---------------------------------------------------------------------------

@pytest.fixture()
def uploads(tmp_path, monkeypatch):
    """The one directory these routes may read a picture from."""
    folder = tmp_path / "uploads_tmp"
    folder.mkdir()
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", folder)
    return folder


@pytest.mark.parametrize("path,body", WITH_A_PICTURE)
def test_a_picture_outside_the_uploads_is_refused(app, monkeypatch, uploads,
                                                  tmp_path, path, body):
    """An arbitrary file read, closed.

    The route reads `image_path` straight off this server's disk and hands
    what it finds to the node as base64. With no containment, any caller could
    name any file the server user can read. media_routes and the Stage-4 image
    lookback have carried this check for months; the proxy this route replaced
    had none until 2026-09-05.

    Nothing may be handed on either: a refusal that still ran the node would
    have handed the file on before answering."""
    elsewhere = tmp_path / "not_an_upload.png"
    elsewhere.write_bytes(b"never forwarded")
    held = hold_the_station_run(monkeypatch, Held(Made(SOUND_UI, [a_sound()])).opened())

    plain, streamed = both_ways(app, path,
                                {**body, "image_path": str(elsewhere)})
    assert plain == streamed
    assert plain[1] == 400
    assert plain[0]["success"] is False
    assert held.seen == [], "the file was handed on before the refusal"


@pytest.mark.parametrize("path,body", WITH_A_PICTURE)
def test_a_picture_inside_the_uploads_still_travels(app, monkeypatch, uploads,
                                                    path, body):
    """The other half, without which the check above could be passing by
    refusing everything. An upload is what every one of these routes is actually
    handed: MediaInputBox re-uploads even a picture taken off this platform's own
    boards before it hands the path on."""
    picture = uploads / "stand_in.png"
    # Four bytes, so that the base64 that travels ("QUJDRA==") is the file's
    # and not the "QUJD" a body may carry under image_base64 already.
    picture.write_bytes(b"ABCD")
    held = hold_the_station_run(monkeypatch, Held(Made(SOUND_UI, [a_sound()])).opened())

    response = app.test_client().post(path, json={**body,
                                                  "image_path": str(picture)})
    assert response.status_code == 200
    forwarded = the_inputs_of(held)
    assert forwarded["image_base64"] == "QUJDRA==", "the path's file travels, not the body's picture"
    assert "image_path" not in forwarded


# ---------------------------------------------------------------------------
# 9. The station that accepts and then says nothing
# ---------------------------------------------------------------------------

def test_the_readings_ride_the_comfyui_transport_and_name_no_cap_of_their_own(
        app, recorded_audio, monkeypatch):
    """Both halves of one rule, and the second is as binding as the first.

    While the readings were POSTs of the routes' own to the GPU service this
    held their two timeouts: CONNECT capped, so that a station that is DOWN is
    caught (measured against a socket that accepts and never answers: 9 frames
    in 16 s, no terminal frame, both server threads parked for as long as
    anyone cared to wait), and READ None, which is platform policy: the first
    call loads the model, long clips take as long as they take, and a read cap
    would cut a reading that is being made. The comparison left this test at
    stage 3 of the move to ComfyUI and the AV reading at stage 6: each is one
    run of a node at ComfyUI (llm_client), which connects with the ComfyUI
    client's own timeouts and waits for the answer without a ceiling. What is
    left to hold here is that the reading is handed to that transport and that
    the route names no cap of its own on the way.
    """
    from my_app.services.llm_client import NODE_ID, LLMClient
    held = hold_the_reading(monkeypatch, Held(Made({"analysis": "x"})).opened())

    app.test_client().post('/api/media/analyze/av',
                           json={"run_id": "run_stand_in", "kind": "audio"})

    args, kwargs = held.seen[0]
    workflow = args[0] if args else kwargs["workflow"]
    assert workflow[NODE_ID]["class_type"] == "ai4artsed_media_reading"
    # The tracking the run rides (LLMClient._tracked, stood in for above)
    # waits for the answer without a ceiling: what it hands submit_and_track
    # is timeout=None, and the run takes no cap from the route (run_node
    # carries none in its signature).
    tracked = inspect.getsource(LLMClient._tracked)
    assert "submit_and_track(" in tracked and "timeout=None" in tracked, tracked
    assert "timeout" not in inspect.signature(LLMClient.run_node).parameters


# ---------------------------------------------------------------------------
# 10. The reader that leaves
# ---------------------------------------------------------------------------

def test_a_reader_that_leaves_does_not_stop_the_reading(app, analysis_model,
                                                        monkeypatch):
    """The claim the reading tests could not make, because they all read to the
    end.

    A closed tab ends the STREAM and nothing else. None of the seven readings
    and proxies declares `client_gone`, and that is a decision: what stands
    behind each of them is one call to a model that already has the card, so
    leaving would end nothing and only lose the answer to work already done.
    Asserted by leaving and then watching the work finish anyway.

    The Commons lookup in section 12 is the one route here that decides the
    other way, and for the reason this one does not: it holds the card for a
    whole chain of checks and saves nothing at the end of them.
    """
    finished = threading.Event()

    class Slow(Held):
        def __call__(self, *args, **kwargs):
            result = super().__call__(*args, **kwargs)
            finished.set()
            return result

    held = hold_the_local_station(monkeypatch, Slow(Ran(COMPARISON)))

    with app.test_request_context('/api/media/analyze/compare',
                                  json={**TWO_READINGS, "enable_streaming": True}):
        response = media_routes.analyze_media_compare()
        nothing_may_buffer_this(response)
        arrivals, body = read_and_leave(response.response, held)

    assert arrivals, "nothing reached the reader before it left"
    assert "event: complete" not in body, "the reader left before the answer"

    # The model answers AFTER the reader has gone, which is the whole point: the
    # gate stands for the upstream, never for the reader.
    held.gate.set()
    assert finished.wait(20.0), "the reading stopped when its reader left"


# ---------------------------------------------------------------------------
# 11. The leaving signal is reachable from a call site at all
# ---------------------------------------------------------------------------

def test_work_handed_over_with_its_arguments_is_told_when_the_reader_leaves():
    """The opt-in, driven the way the routes now hand their work over.

    `streamed_answer` decides whether the work wants the signal by reading
    `client_gone` off its signature. Every one of the seven sites wrapped its
    work in `lambda: run(data)`, whose parameter list is empty -- so the answer
    was False at all of them, it was False for any lambda, and it would have
    stayed False on the day `run` grew the parameter. The opt-in was
    structurally unreachable and failed silently.
    """
    entered = threading.Event()
    noticed = threading.Event()

    def run(data, client_gone):
        entered.set()
        while not client_gone.is_set():
            threading.Event().wait(0.01)
        noticed.set()
        return {"seen": data}, 200

    frames = streamed_answer(run, {"a": 1}, label="TEST", interval=0.05)
    assert next(frames) == ": heartbeat\n\n"
    assert entered.wait(3.0)
    assert not noticed.is_set()
    frames.close()
    assert noticed.wait(3.0), "the work was never told its reader had gone"


def test_the_same_reaches_work_bound_with_functools_partial():
    """The other spelling, for arguments a positional list cannot carry.
    `inspect.signature` resolves a partial down to the parameters still open, so
    the declaration survives the binding."""
    told = {}

    def run(data, *, client_gone):
        told["signal"] = client_gone
        return {"seen": data}, 200

    list(streamed_answer(functools.partial(run, {"a": 1}), label="TEST",
                         interval=0.05))
    assert isinstance(told["signal"], threading.Event)


def test_a_lambda_that_buries_the_declaration_is_refused_by_name():
    """Detected, not silently ignored -- and at CALL time, because by the first
    frame the route has already handed Flask a 200 and the client would read a
    torn body in place of a fault."""
    def run(data, client_gone):
        return {"seen": data}, 200

    with pytest.raises(TypeError) as raised:
        streamed_answer(lambda: run({"a": 1}), label="TEST")
    assert "run" in str(raised.value)
    assert "client_gone" in str(raised.value)


def test_a_lambda_that_buries_nothing_is_left_alone():
    """The other half. A lambda that IS the work hides no declaration, and
    refusing every lambda would be a rule about spelling rather than about the
    signal."""
    assert list(streamed_answer(lambda: ({"ok": True}, 200), label="TEST"))


ROUTES_ON_THIS_TRANSPORT = sorted(
    (Path(__file__).resolve().parents[1] / 'my_app' / 'routes').glob('*.py'))


ON_THIS_TRANSPORT = ('streamed_answer', 'answered_either_way',
                     'events_with_heartbeat')


def _the_work_handed_over(call):
    """The argument that IS the work, at any of the three entry points.

    All three take it first and positionally. Read out of the tree rather than
    out of a window of text, because these calls are written over four and five
    lines and because the OTHER arguments are allowed to be lambdas: `frame=`
    and `heartbeat=` are frame writers, they hide no declaration, and a rule
    that flagged them would be a rule about spelling.
    """
    name = getattr(call.func, 'id', None) or getattr(call.func, 'attr', None)
    if name not in ON_THIS_TRANSPORT:
        return None
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg in ('run', 'events'):
            return kw.value
    return None


def _lambdas_handed_to_this_transport(source, where):
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        work = _the_work_handed_over(node)
        if isinstance(work, ast.Lambda):
            offenders.append(f'{where}:{node.lineno}: {ast.unparse(node)[:90]}')
    return offenders


def test_no_route_hands_this_transport_a_lambda():
    """The static half of the same rule, and the reason it is static: what
    `_a_declaration_this_lambda_hides` can see is the names a lambda's own code
    object holds, so a call reached through an attribute or built at run time
    passes it. Here no route may write the shape at all.

    All THREE entry points, since 2026-09-05. The regex read only the two
    answer-shaped ones, so five sites that handed their work to
    `events_with_heartbeat` stood outside it -- and the event shape is where
    the opt-in was actually lost.

    Deliberately not a hand-written file list -- a list of the files an author
    happened to edit can only confirm that author."""
    offenders = []
    for path in ROUTES_ON_THIS_TRANSPORT:
        offenders += _lambdas_handed_to_this_transport(
            path.read_text(encoding='utf-8'), path.name)
    assert not offenders, (
        'hand the work over with its arguments instead:\n' + '\n'.join(offenders))


def test_the_guard_knows_every_way_into_this_transport():
    """`ON_THIS_TRANSPORT` is the transport's own list of entry points.

    What stood here until 2026-09-05 ran `_lambdas_handed_to_this_transport`
    over two hand-written sample strings and asserted what that helper made of
    them. Nothing in this codebase could make it fail: not a route that
    regressed, and not a FOURTH way into the transport appearing beside the
    three named above — which is precisely how the third one came to stand
    outside the guard, with five sites behind it.

    An entry point is a public function of the transport that takes the work:
    a parameter called `run` or `events`. Every one of them has to be named in
    the tuple above, or the guard walks straight past the sites that use it.
    """
    import inspect
    from my_app.services import streaming_response

    entry_points = {
        name
        for name, fn in inspect.getmembers(streaming_response, inspect.isfunction)
        if not name.startswith('_')
        and fn.__module__ == streaming_response.__name__
        and {'run', 'events'} & set(inspect.signature(fn).parameters)
    }
    assert entry_points == set(ON_THIS_TRANSPORT), (
        'the guard reads ' + repr(sorted(ON_THIS_TRANSPORT))
        + ' and the transport offers ' + repr(sorted(entry_points))
        + ' — widen ON_THIS_TRANSPORT, or the sites using the new one are unguarded')

    # And the shape itself, so the failure above is readable: the work is
    # caught, the frame writer beside it is left alone.
    assert len(_lambdas_handed_to_this_transport(
        'events_with_heartbeat(lambda: run(data), label="X", frame=lambda s: s)',
        'sample')) == 1


# ---------------------------------------------------------------------------
# 12. The found-pictures row — /api/commons/lookup
# ---------------------------------------------------------------------------

FOUND_ROW = {"state": "ok", "term": "house",
             "images": [{"title": "A house at dusk.jpg"}]}


def hold_the_lookup(monkeypatch, result=None):
    """The whole lookup held at once: the search term, the archive and every
    picture check behind it."""
    held = Held(dict(result if result is not None else FOUND_ROW))
    monkeypatch.setattr(commons_service, "lookup_for_prompt", held)
    return held


def test_the_commons_lookup_keeps_breathing_while_the_row_is_checked(app, monkeypatch):
    """The worst case on this platform, and the reason this route was moved.

    At the kids and youth levels the lookup works through up to
    MAX_CHECK_CANDIDATES pictures and each of them costs two model calls by the
    service's own reckoning, on top of the call that turns the prompt into a
    search term: up to nineteen model calls inside one POST, each of them
    queueing for the plant-wide GPU slot, and the POST said nothing for the
    whole of it.
    """
    held = hold_the_lookup(monkeypatch)
    with app.test_request_context('/api/commons/lookup',
                                  json={"prompt": "ein haus am feldrand",
                                        "enable_streaming": True}):
        response = commons_routes.lookup()

    payload, http_status = breathed(response, held)
    assert http_status == 200
    assert payload["success"] is True
    assert payload["state"] == "ok"
    assert payload["images"] == FOUND_ROW["images"]


def test_the_commons_lookup_answers_the_same_either_way(app, monkeypatch):
    hold_the_lookup(monkeypatch).opened()
    plain, streamed = both_ways(app, '/api/commons/lookup', {"prompt": "a house"})
    assert plain == streamed
    assert plain == ({**FOUND_ROW, "success": True}, 200)


@pytest.mark.parametrize("body,http_status,message", [
    pytest.param({}, 400, "prompt required", id="no prompt at all"),
    pytest.param({"prompt": "   "}, 400, "prompt required", id="a prompt of spaces"),
    pytest.param({"prompt": "x" * (commons_service.MAX_PROMPT_CHARS + 1)},
                 413, "prompt too long", id="longer than the model reads"),
])
def test_the_commons_lookup_refuses_the_same_either_way(app, monkeypatch, body,
                                                        http_status, message):
    """A refusal is an answer, and it travels on the transport it was asked on.

    That is why these stand inside the run rather than at the boundary: handed
    one plain JSON body where it asked for frames, services/directRun.ts reads a
    half-finished deploy and writes a console line about it — for a refusal that
    is nothing of the kind.

    Nothing is held: none of these reach the archive or a model at all, and the
    last assertion is what says so.
    """
    held = hold_the_lookup(monkeypatch).opened()
    plain, streamed = both_ways(app, '/api/commons/lookup', body)
    assert plain == streamed
    assert plain == ({"success": False, "error": message}, http_status)
    assert held.seen == [], "a refused prompt was looked up anyway"


def test_a_lookup_that_could_not_be_made_is_the_same_row_either_way(app, monkeypatch):
    """An outage is never shown as a finding about the participant's prompt: the
    row says `error`, and views/compare/model_comparison.vue renders that
    differently from the three states that ARE about the prompt. The 200 is this
    route's own contract in all four outcomes, and both ways back keep it."""
    def unreachable(*args, **kwargs):
        raise RuntimeError("commons is not answering")

    monkeypatch.setattr(commons_service, "lookup_for_prompt", unreachable)
    plain, streamed = both_ways(app, '/api/commons/lookup', {"prompt": "a house"})
    assert plain == streamed
    assert plain == ({"success": True, "state": "error", "term": None,
                      "images": []}, 200)


def test_the_commons_lookup_takes_its_safety_level_where_the_session_is(
        app, monkeypatch):
    """The level every picture here is checked against, resolved on the thread
    that serves the request and handed into the work.

    Under this transport the work runs on a worker carrying a COPY of the
    request thread's context. `safety_level_resolver` marks that worker and
    answers it with the STRICTEST level plus a warning — correct, and it means a
    resolve left inside the run would check every room's pictures at `kids`
    while the room worked at another level, silently. Driven with the
    installation at `open` and no course pinned, over the STREAM, which is the
    only way back that has such a worker at all.
    """
    monkeypatch.setattr(config, "DEFAULT_SAFETY_LEVEL", "open")
    held = hold_the_lookup(monkeypatch).opened()

    streamed = app.test_client().post('/api/commons/lookup',
                                      json={"prompt": "a house",
                                            "enable_streaming": True})
    nothing_may_buffer_this(streamed)
    assert answer(streamed.get_data(as_text=True))[1] == 200

    assert held.seen[0][1]["safety_level"] == "open", \
        "the level was resolved on the worker, which owes the strictest one"


@pytest.mark.parametrize("value", [123, 1.5, True, [1, 2], {"a": 1}],
                         ids=["a number", "a float", "a boolean", "a list",
                              "an object"])
def test_a_prompt_that_is_not_text_is_named_and_never_looked_up(app, monkeypatch,
                                                                value):
    """A caller's mistake, named as one, on both ways back.

    Unnamed it reached `.strip()`: Flask's HTML 500 on the plain path, and on
    the stream a 200 whose terminal frame carried "'int' object has no attribute
    'strip'" with a traceback in the log. The route is unauthenticated, so any
    caller at all could put a Python type error into a response body.

    `str(value)` is this platform's other coercion (media_routes
    ._run_analyze_image) and it is the wrong one here: every unique prompt costs
    a model call, so `str([1, 2])` would send a Python repr nobody wrote to a
    model and key the archive cache on it. The last assertion is what says
    nothing was asked.
    """
    held = hold_the_lookup(monkeypatch).opened()
    plain, streamed = both_ways(app, '/api/commons/lookup', {"prompt": value})
    assert plain == streamed
    assert plain == ({"success": False, "error": "prompt must be a string"}, 400)
    assert held.seen == [], "a prompt that is not text was looked up anyway"


def test_a_limit_that_is_no_number_falls_back_instead_of_raising(app, monkeypatch):
    """The route's other input, read the same way.

    Python's JSON reader accepts `Infinity` and `NaN`, and `int(inf)` raises
    OverflowError, which is neither of the two the fallback caught -- so
    `{"limit": Infinity}` came back as "cannot convert float infinity to
    integer" in place of the default.
    """
    held = hold_the_lookup(monkeypatch).opened()
    client = app.test_client()
    for body in ('{"prompt": "a house", "limit": Infinity}',
                 '{"prompt": "a house", "limit": NaN}',
                 '{"prompt": "a house", "limit": "three"}',
                 '{"prompt": "a house", "limit": [3]}'):
        response = client.post('/api/commons/lookup', data=body,
                               content_type='application/json')
        assert response.status_code == 200, body
        assert response.get_json()["state"] == "ok", body
    for _args, kwargs in held.seen:
        assert kwargs["limit"] == commons_service.MAX_IMAGES


class TestTheRowStopsWhereItsReaderLeft:
    """The one route on this transport that TAKES the leaving signal.

    Every other route here declines it, and rightly: a generation saves its
    image, so a reader that goes away still leaves something behind. This one
    saves nothing. What it makes is a row for one page, and the archive's
    candidate list is the only thing kept for the next reader (the service's
    `_search_cache`, keyed on the search term). The per-picture checks are
    cached nowhere, so before the signal was declared a reader who left after
    two frames still paid for every one of MAX_CHECK_CANDIDATES candidates --
    two model calls and one download of up to MAX_IMAGE_BYTES each, every model
    call queueing for the plant-wide GPU slot, on a card other people are
    waiting for.
    """

    TERM = "house field"  # two words, so the widening below cannot follow

    @pytest.fixture()
    def a_shelf_of_candidates(self, monkeypatch):
        """The archive already asked, and its files waiting to be looked at.

        Primed into the service's own cache rather than mocked around it, so
        what runs is the real `_take` -- which is where the signal is read.
        """
        commons_service._search_cache.clear()
        commons_service._term_cache.clear()
        commons_service._search_cache.set(self.TERM, [
            asdict(commons_service.CommonsImage(
                title=f"A house {n}.jpg",
                thumb_proxy=f"/api/commons/image/ref{n}",
                width=800, height=600, author="somebody",
                licence="CC BY-SA 4.0",
                file_page="https://commons.wikimedia.org/wiki/File:House.jpg",
                categories=["Houses"]))
            for n in range(commons_service.MAX_CHECK_CANDIDATES)])
        monkeypatch.setattr(commons_service, "derive_search_term",
                            lambda prompt: (self.TERM, commons_service.TERM_OK))
        # The level at which pictures are looked at at all. No course is pinned
        # here, so the installation setting is what the resolver answers with.
        monkeypatch.setattr(config, "DEFAULT_SAFETY_LEVEL", "kids")
        # Nothing may reach Wikimedia if a widening ever does follow.
        monkeypatch.setattr(commons_service, "_api_get", lambda params: None)
        yield
        commons_service._search_cache.clear()
        commons_service._term_cache.clear()

    class OnePictureAtATime(Held):
        """One candidate check: a download of up to MAX_IMAGE_BYTES and two
        model calls, by the service's own reckoning. The first one waits, which
        is what gives the reader time to leave."""

        def __call__(self, image, safety_level):
            self.seen.append(image.title)
            if len(self.seen) == 1:
                assert self.gate.wait(30.0), "the gate was never opened"
            return False  # so the loop would work through the whole list

    def a_row_being_checked(self, monkeypatch):
        checks = self.OnePictureAtATime(None)
        monkeypatch.setattr(commons_service, "_passes_image_check", checks)
        return checks

    def watched(self, monkeypatch):
        """The real lookup, with a word when it is over."""
        real = commons_service.lookup_for_prompt
        finished = threading.Event()

        def run(*args, **kwargs):
            try:
                return real(*args, **kwargs)
            finally:
                finished.set()

        monkeypatch.setattr(commons_service, "lookup_for_prompt", run)
        return finished

    def test_the_checks_stop_when_the_reader_goes(self, app, monkeypatch,
                                                  a_shelf_of_candidates):
        checks = self.a_row_being_checked(monkeypatch)
        finished = self.watched(monkeypatch)

        with app.test_request_context('/api/commons/lookup',
                                      json={"prompt": "ein haus am feldrand",
                                            "enable_streaming": True}):
            response = commons_routes.lookup()
            nothing_may_buffer_this(response)
            arrivals, body = read_and_leave(response.response, checks)

        assert arrivals, "nothing reached the reader before it left"
        assert "event: complete" not in body, "the reader left before the answer"

        # Only now: the first check was still holding the card when the tab
        # closed, and it is not interrupted in the middle of it.
        checks.gate.set()
        assert finished.wait(20.0), "the lookup never ended"
        assert len(checks.seen) == 1, (
            f"{len(checks.seen)} of {commons_service.MAX_CHECK_CANDIDATES} "
            "candidates were checked for a page that had gone")

    def test_a_reader_that_stays_gets_the_whole_row(self, app, monkeypatch,
                                                    a_shelf_of_candidates):
        """The other half of the claim: nothing stops on its own.

        Without this the test above would pass just as well against a lookup
        that had simply stopped checking pictures.
        """
        checks = self.a_row_being_checked(monkeypatch)
        checks.gate.set()

        client = app.test_client()
        response = client.post('/api/commons/lookup',
                               json={"prompt": "ein haus am feldrand",
                                     "enable_streaming": True})
        nothing_may_buffer_this(response)
        payload, http_status = answer(response.get_data(as_text=True))

        assert http_status == 200
        assert payload["state"] == "nothing_found"
        assert len(checks.seen) == commons_service.MAX_CHECK_CANDIDATES


class TestALookupThatCannotResolveItsSafetyLevelSaysSo:
    """Commons is not age-filtered, so whether a picture in this row is looked
    at at all hangs on the level. Resolved at the request boundary and left
    unguarded, a resolver that raised took the whole view with it: Flask's own
    HTML page, no status a caller can act on, no field it can read -- and
    because the resolve stands in front of the run, the two refusals inside it
    answered 500 as well instead of 400 and 413. /pipeline/safety/quick and the
    Mean Images overlay were guarded when they moved; this one was not.
    """

    @pytest.fixture()
    def resolver_is_down(self, monkeypatch):
        import my_app.services.safety_level_resolver as resolver

        def boom():
            raise RuntimeError("the course lookup is down")

        monkeypatch.setattr(resolver, "resolve_safety_level", boom)

    @pytest.mark.parametrize("body", [
        pytest.param({}, id="a body that would have been refused"),
        pytest.param({"prompt": "a house"}, id="a body that would have run"),
    ])
    def test_it_answers_json_naming_the_cause(self, app, resolver_is_down, body):
        response = app.test_client().post('/api/commons/lookup', json=body)
        assert response.status_code == 500
        assert response.mimetype == "application/json"
        answered = response.get_json()
        assert answered["success"] is False
        # The real cause travels: a message that only says something failed
        # cannot be acted on.
        assert "the course lookup is down" in answered["error"]

    def test_nothing_was_looked_up(self, app, monkeypatch, resolver_is_down):
        """SAFETY. An unresolved level is an unknown level, and a row checked
        against an unknown level is a row nobody checked."""
        held = hold_the_lookup(monkeypatch).opened()
        app.test_client().post('/api/commons/lookup', json={"prompt": "a house"})
        assert held.seen == []


def test_the_response_every_streamed_route_hands_back_says_do_not_buffer():
    """One place for the wire, so a route cannot answer with headers of its own.
    Fourteen sites wrote this Response out by hand until 2026-09-05."""
    app_for_context = Flask(__name__)
    with app_for_context.test_request_context('/'):
        response = sse_response(iter([": heartbeat\n\n"]))
    nothing_may_buffer_this(response)


def test_the_gate_answers_one_json_body_where_no_stream_was_asked_for():
    """The other branch of the same helper, so that folding fourteen sites into
    it cannot have quietly turned the plain answer into a stream."""
    app_for_context = Flask(__name__)

    def run(data):
        return {"seen": data}, 201

    with app_for_context.test_request_context('/'):
        response, http_status = answered_either_way(
            {"nothing": "asked"}, run, {"a": 1}, label="TEST")
        assert http_status == 201
        assert response.mimetype == "application/json"
        assert response.get_json() == {"seen": {"a": 1}}
