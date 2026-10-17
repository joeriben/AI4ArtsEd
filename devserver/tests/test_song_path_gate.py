"""The Flow's song: what reaches HeartMuLa is what was checked, and the song
goes the way every run of the Flow that generates goes.

views/x2x_flow.vue (runMusic) runs the perspective over the lyrics and hands
the song to finishRun, which opens the generation stream (GET
/pipeline/generation) with output_config 'heartmula_standard', the lyrics as
prompt and the style tags as secondary_text. output_music_heartmula reads the
prompt as TEXT_1 and the second text as TEXT_2, both as they were written.

From 2026-07-10 (af517455) to 2026-10-06 the song went to
/pipeline/interception with schema 'heartmula' and the two texts as
custom_placeholders, beside the stream every run of the page that generates
uses: the box showed no queue place for it, a device holding another run as
"GPU busy", and the check station the checks of the last picture. What that
route was taught for the song on 2026-10-01 holds on the stream: the lyrics
the interception handed on and the style tags pass Stage 1, Stage 3 reads
the lyrics and then both together as the chunk receives them, and nothing
translates them on the way. The interception route refuses
custom_placeholders now; its stop and device mechanics stay tested below with
a media run of another perspective.

Everything is mocked: no model, no GPU, no record on disk.

Run: cd devserver && python3 -m pytest tests/test_song_path_gate.py -q
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R

LYRICS = "Ein Haus steht in einer Landschaft."
STYLE = "folk, acoustic guitar, calm"
REFUSED_AT_1 = "refuse-at-stage-1"
REFUSED_AT_3 = "refuse-at-stage-3"
DEVICE = "test-song"
SONG = "heartmula_standard"
GENERATION = "/api/schema/pipeline/generation"
LEVELS = ("kids", "youth", "open", "adult", "research")
# Read before any fixture replaces it.
REAL_STAGE4 = R.execute_stage4_generation_only


class _Recorder:
    """Takes every call a run makes on its record and keeps nothing."""
    metadata = {"entities": [], "models_used": {}}

    def output_entities(self, *a, **kw):
        return []

    def __getattr__(self, name):
        return lambda *a, **kw: None


def _client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp, url_prefix="/api/schema")
    return app.test_client()


def _events(response):
    """The named frames of a stream, in order, as (event, data)."""
    out = []
    for block in response.get_data(as_text=True).split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if name:
            out.append((name, data))
    return out


def _blocked(response):
    return [data for name, data in _events(response) if name == "blocked"]


def _parameters_at_the_router(monkeypatch):
    """The parameters every chunk request carries when it reaches the backend.

    The real executor, ChunkBuilder and injection loop run; only the router is
    replaced, so nothing is generated and nothing is written.
    """
    from schemas.engine import backend_router as BR

    seen = []

    async def capture(self, request):
        seen.append(dict(request.parameters))
        return BR.BackendResponse(success=False, content="", error="captured")

    monkeypatch.setattr(BR.BackendRouter, "process_request", capture)
    return seen


# ---------------------------------------------------------------------------
# The song on the generation stream
# ---------------------------------------------------------------------------

@pytest.fixture
def song(monkeypatch):
    """The Flow's song on the generation stream, at a chosen level.

    Stage 1 and Stage 3 are stand-ins that record what they read. Stage 3
    answers a text it was not asked to take as given with a translation of it,
    so a translated prompt shows where it arrives. Stage 4 is a stand-in that
    records what it was handed, unless a test puts the real one back.
    """
    R.init_schema_engine()
    seen = {"stage1": [], "stage3": [], "stage4": []}

    async def stage1(text, safety_level, pipeline_executor, user_language='de'):
        seen["stage1"].append(text)
        if REFUSED_AT_1 in text:
            return (False, text, "refused at stage 1", ["stub"])
        return (True, text, None, ["stub"])

    async def stage3(prompt, safety_level, media_type, pipeline_executor, **kw):
        seen["stage3"].append((prompt, kw))
        if REFUSED_AT_3 in prompt:
            return {"safe": False, "method": "stub", "abort_reason": "refused at stage 3"}
        unchecked = safety_level in ("research", "adult") and not kw.get("force_translation")
        as_written = kw.get("as_given") or unchecked
        return {"safe": True, "method": "stub",
                "positive_prompt": prompt if as_written else f"EN: {prompt}"}

    async def stage4(**kw):
        seen["stage4"].append(kw)
        return {"success": False, "error": "stub: no model in this test",
                "run_id": kw.get("run_id")}

    monkeypatch.setattr(R, "execute_stage1_safety_unified", stage1)
    monkeypatch.setattr(R, "execute_stage3_safety", stage3)
    monkeypatch.setattr(R, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    client = _client()

    def ask(level, lyrics=LYRICS, style=STYLE, output_config=SONG):
        """What finishRun in x2x_flow.vue asks for, the forced translation included."""
        monkeypatch.setattr(R, "resolve_safety_level", lambda: level)
        query = {"prompt": lyrics, "output_config": output_config, "device_id": DEVICE,
                 "enable_streaming": "true", "force_translation": "true"}
        if style is not None:
            query["secondary_text"] = style
        response = client.get(GENERATION, query_string=query)
        # A stream runs as it is read: read it whole before anything is asserted.
        response.get_data()
        return response, seen

    ask.client = client
    ask.monkeypatch = monkeypatch
    yield ask
    R._active_generations.pop(DEVICE, None)


@pytest.mark.parametrize("level", LEVELS)
def test_the_song_reaches_stage_4_as_written(song, level):
    _response, seen = song(level)
    assert [(kw["prompt"], kw["secondary_text"], kw["output_config"])
            for kw in seen["stage4"]] == [(LYRICS, STYLE, SONG)]


@pytest.mark.parametrize("level", ["research", "adult"])
def test_no_translation_reaches_the_song_where_the_level_checks_nothing(song, monkeypatch, level):
    """At research and adult Stage 3 checks nothing, and a forced translation
    still translates (execute_stage3_safety, the real one here). The Flow
    forces it for every run; the song's lyrics reach Stage 4 as written."""
    from schemas.engine import stage_orchestrator as O

    async def translate(*a, **kw):
        return SimpleNamespace(success=True, final_output="TRANSLATED")

    monkeypatch.setattr(R, "execute_stage3_safety", O.execute_stage3_safety)
    monkeypatch.setattr(R.pipeline_executor, "execute_pipeline", translate)
    _response, seen = song(level)
    assert [kw["prompt"] for kw in seen["stage4"]] == [LYRICS]


@pytest.mark.parametrize("level", ["kids", "research"])
def test_the_chunk_sings_the_lyrics_and_reads_the_style(song, monkeypatch, level):
    """Through the real Stage 4, the executor and ChunkBuilder: the router
    receives the lyrics as TEXT_1 and the style tags as TEXT_2."""
    monkeypatch.setattr(R, "execute_stage4_generation_only", REAL_STAGE4)
    at_router = _parameters_at_the_router(monkeypatch)
    response, _seen = song(level)
    assert [(p.get("TEXT_1"), p.get("TEXT_2")) for p in at_router] == [(LYRICS, STYLE)], (
        [data for name, data in _events(response) if name == "error"])


@pytest.mark.parametrize("level", ["kids", "youth", "adult"])
def test_stage_1_reads_the_lyrics_and_the_style(song, level):
    _response, seen = song(level)
    assert seen["stage1"] == [LYRICS, STYLE]


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_refused_lyrics_stop_the_song_at_stage_1(song, level):
    response, seen = song(level, lyrics=f"{REFUSED_AT_1} words")
    blocked = _blocked(response)
    assert [(b["stage"], b["reason"]) for b in blocked] == [(1, "refused at stage 1")]
    assert seen["stage3"] == [] and seen["stage4"] == []


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_a_refused_style_stops_the_song_at_stage_1(song, level):
    response, seen = song(level, style=f"{REFUSED_AT_1}, drums")
    blocked = _blocked(response)
    assert [(b["stage"], b["reason"]) for b in blocked] == [(1, "refused at stage 1")]
    assert seen["stage3"] == [] and seen["stage4"] == []


@pytest.mark.parametrize("level", ["kids", "youth", "open"])
def test_stage_3_reads_both_texts_as_the_chunk_receives_them(song, level):
    """The lyrics first, whose translation is kept for the device as an image
    run keeps its prompt's; then both together, joined as
    /pipeline/interception joined them until 2026-10-06, and that
    translation is kept for nobody."""
    _response, seen = song(level)
    assert [(text, kw.get("as_given"), kw.get("device_id"))
            for text, kw in seen["stage3"]] == [
        (LYRICS, True, DEVICE), (f"{LYRICS} | {STYLE}", True, None)]


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_a_refused_style_stops_the_song_at_stage_3(song, level):
    response, seen = song(level, style=f"{REFUSED_AT_3}, drums")
    assert [(b["stage"], b["reason"]) for b in _blocked(response)] == [(3, "refused at stage 3")]
    assert seen["stage4"] == []


def test_refused_lyrics_stop_the_song_at_stage_3(song):
    response, seen = song("kids", lyrics=f"{REFUSED_AT_3} words")
    assert [b["stage"] for b in _blocked(response)] == [3]
    assert [text for text, _kw in seen["stage3"]] == [f"{REFUSED_AT_3} words"]
    assert seen["stage4"] == []


def test_an_empty_style_leaves_the_lyrics_to_the_chunk_as_its_tags(song):
    """HeartMuLa picked by hand with one text: the Flow sends the style empty,
    and the chunk sings no lyrics then but reads the text as its tags."""
    _response, seen = song("kids", style="")
    assert seen["stage1"] == [LYRICS]
    assert [text for text, _kw in seen["stage3"]] == [LYRICS]
    assert [kw["secondary_text"] for kw in seen["stage4"]] == [""]


def test_a_song_that_did_not_come_is_an_error(song):
    response, _seen = song("research")
    events = _events(response)
    assert "complete" not in [name for name, _data in events]
    errors = [data for name, data in events if name == "error"]
    assert errors and "stub: no model in this test" in errors[0]["message"]
    assert DEVICE not in R._active_generations


def test_a_run_without_a_second_text_goes_as_before(song):
    """Persona and Resona send their song as one prompt, "lyrics || tags", and
    no second text: neither the Stage 1 nor the as-given check of this path
    runs, and the forced translation stands."""
    _response, seen = song("kids", style=None)
    assert seen["stage1"] == []
    assert [(kw.get("as_given"), kw.get("force_translation"))
            for _text, kw in seen["stage3"]] == [(None, True)]
    assert [kw["secondary_text"] for kw in seen["stage4"]] == [None]


def test_a_second_text_for_a_config_that_reads_one_is_refused(song):
    response, seen = song("kids", output_config="sd35_large")
    assert response.status_code == 400
    assert "'sd35_large' is no config that reads two texts" in response.get_json()["error"]
    assert seen == {"stage1": [], "stage3": [], "stage4": []}
    assert DEVICE not in R._active_generations


def test_a_second_text_without_a_config_is_refused(song):
    song.monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    response = song.client.get(GENERATION, query_string={
        "prompt": LYRICS, "secondary_text": STYLE, "device_id": DEVICE,
        "enable_streaming": "true"})
    assert response.status_code == 400
    assert "names none" in response.get_json()["error"]


def test_a_second_text_off_the_stream_is_refused(song):
    song.monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    response = song.client.post(GENERATION, json={
        "prompt": LYRICS, "output_config": SONG, "secondary_text": STYLE,
        "device_id": DEVICE})
    assert response.status_code == 400
    assert "stream" in response.get_json()["error"]


@pytest.mark.parametrize("value", [["folk"], 3, {"style": "folk"}])
def test_a_second_text_that_is_no_string_is_refused(song, value):
    song.monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    response = song.client.post(GENERATION, json={
        "prompt": LYRICS, "output_config": SONG, "secondary_text": value,
        "device_id": DEVICE, "enable_streaming": True})
    assert response.status_code == 400
    assert "string" in response.get_json()["error"]


def test_the_config_that_sings_declares_two_texts():
    """The stream serves a second text only to a config that declares it reads two."""
    R.init_schema_engine()
    assert R._reads_two_texts(SONG) is True
    assert R._reads_two_texts("sd35_large") is False
    assert R._reads_two_texts(None) is False


# ---------------------------------------------------------------------------
# /pipeline/interception: no placeholders, and a media run's stop and device
# ---------------------------------------------------------------------------

VEHICLE = "latent_lab"    # an interception config whose plan writes no text
OUTPUT = "sd35_large"


@pytest.fixture
def run(monkeypatch):
    """A media request to /pipeline/interception at a chosen level, with every
    check and the generator replaced."""
    R.init_schema_engine()
    seen = {"stage1": [], "stage3": [], "pipelines": [],
            "at_stage3": None, "at_stage4": None}

    async def stage1(text, safety_level, pipeline_executor, user_language='de'):
        seen["stage1"].append(text)
        return (True, text, None, ["stub"])

    async def stage3(prompt, safety_level, media_type, pipeline_executor, **kw):
        seen["stage3"].append(prompt)
        if seen["at_stage3"]:
            seen["at_stage3"]()
        return {"safe": True, "method": "stub", "positive_prompt": prompt}

    async def execute_pipeline(config_name=None, **kw):
        seen["pipelines"].append(config_name)
        if seen["at_stage4"]:
            seen["at_stage4"]()
        return SimpleNamespace(success=False, error="stub: no model in this test",
                               final_output=None, metadata={}, steps=[],
                               execution_time=0)

    monkeypatch.setattr(R, "execute_stage1_safety_unified", stage1)
    monkeypatch.setattr(R, "execute_stage3_safety", stage3)
    monkeypatch.setattr(R.pipeline_executor, "execute_pipeline", execute_pipeline)
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    client = _client()

    def post(level, schema=VEHICLE, **extra):
        monkeypatch.setattr(R, "resolve_safety_level", lambda: level)
        body = {"schema": schema, "input_text": LYRICS, "output_config": OUTPUT,
                "device_id": DEVICE, "user_language": "de", **extra}
        response = client.post("/api/schema/pipeline/interception", json=body)
        return response, seen

    post.seen = seen
    post.client = client
    yield post
    R._active_generations.pop(DEVICE, None)


@pytest.mark.parametrize("value", [{"TEXT_1": LYRICS, "TEXT_2": STYLE}, {}, [], "", 0, False])
def test_the_interception_route_takes_no_placeholders(run, value):
    """A placeholder writes a chunk parameter. The song took the two texts in
    here until 2026-10-06; nothing sends them now, and the field is refused
    by name rather than dropped unread."""
    response, seen = run("kids", custom_placeholders=value)
    assert response.status_code == 400
    assert "secondary_text" in response.get_json()["error"]
    assert seen["pipelines"] == [] and seen["stage1"] == []


def test_a_media_run_that_did_not_come_is_not_a_success(run):
    response, seen = run("research")
    body = response.get_json()
    assert seen["pipelines"] == [OUTPUT]
    assert response.status_code == 502
    assert body["status"] == "error"
    assert "stub: no model in this test" in body["error"]


@pytest.mark.parametrize("level", ["kids", "research"])
def test_an_output_config_posted_as_schema_is_refused(run, level):
    """Stage 2 ran its plan as the interception, with nothing checked after Stage 1."""
    response, seen = run(level, schema="sd35_large")
    assert response.status_code == 400
    assert "makes media" in response.get_json()["error"]
    assert seen["pipelines"] == [] and seen["stage1"] == []


def _cancel(run):
    """The Flow's stop: the cancel route, asked for this device."""
    answer = run.client.post("/api/schema/pipeline/generation-cancel", json={"device_id": DEVICE})
    return answer.get_json()


def test_a_media_run_holds_the_device_and_carries_its_run_id(run):
    """What the cancel route and the gate go by, present while the medium is made."""
    from my_app.services import generation_abort
    held = {}

    def look():
        entry = dict(R._active_generations.get(DEVICE) or {})
        held.update(entry=entry, run=generation_abort.CURRENT_RUN_ID.get(),
                    config=generation_abort.CURRENT_OUTPUT_CONFIG.get())

    run.seen["at_stage4"] = look
    response, _seen = run("research")
    body = response.get_json()
    assert held["entry"]["phase"] == "generating"
    assert held["entry"]["run_id"] == body["run_id"] == held["run"]
    assert held["config"] == OUTPUT
    assert DEVICE not in R._active_generations


def test_a_stop_while_the_medium_is_made_is_answered_as_a_stop(run):
    asked = []
    run.seen["at_stage4"] = lambda: asked.append(_cancel(run))
    response, _seen = run("research")
    assert asked == [{"cancelled": True}]
    assert response.status_code == 200
    assert response.get_json()["status"] == "cancelled"
    assert DEVICE not in R._active_generations


@pytest.mark.parametrize("level", ["kids", "research"])
def test_a_stop_during_the_checks_makes_nothing(run, level):
    asked = []
    run.seen["at_stage3"] = lambda: asked.append(_cancel(run))
    response, seen = run(level)
    assert asked and asked[0] == {"cancelled": True}
    assert seen["pipelines"] == []
    assert response.get_json()["status"] == "cancelled"
    assert DEVICE not in R._active_generations


def test_a_device_that_is_generating_is_told_so_and_keeps_its_run(run):
    import time
    other = {"run_id": "run_other", "ts": time.time(), "output_config": "sd35_large",
             "phase": "generating"}
    R._active_generations[DEVICE] = dict(other)
    response, seen = run("research")
    body = response.get_json()
    assert response.status_code == 429
    assert body["code"] == "device_busy"
    assert seen["pipelines"] == []
    assert R._active_generations[DEVICE] == other


def test_a_stop_on_a_media_run_is_not_read_as_the_next_press_of_the_device(run):
    """The cancel flag is set by device. Set for this run, which reads its
    run's mark, it was read by the device's next picture as its own stop."""
    flagged = {}

    def stop_and_look():
        _cancel(run)
        this_run = R._active_generations[DEVICE]["run_id"]
        flagged.update(this_run=R._is_cancelled(DEVICE, this_run),
                       picture=R._is_cancelled(DEVICE, "run_the_next_picture"))

    run.seen["at_stage4"] = stop_and_look
    run("research")
    assert flagged == {"this_run": True, "picture": False}
    assert not R._is_cancelled(DEVICE)


@pytest.mark.parametrize("level", ["kids", "research"])
def test_a_stop_while_the_request_is_read_makes_nothing(run, monkeypatch, level):
    asked = []
    resolve = R._resolve_interception_config

    def resolve_after_a_stop(schema_name):
        asked.append(_cancel(run))
        return resolve(schema_name)

    monkeypatch.setattr(R, "_resolve_interception_config", resolve_after_a_stop)
    response, seen = run(level)
    assert asked == [{"cancelled": True}]
    assert seen["pipelines"] == []
    assert response.get_json()["status"] == "cancelled"
    assert DEVICE not in R._active_generations


def test_a_media_run_waiting_long_for_the_card_stays_announced(run, monkeypatch):
    """The stale sweep takes an entry after half an hour, and the GPU gate lets
    a run wait longer. The route has no stream to refresh its entry with."""
    import threading
    import time
    monkeypatch.setattr(R, "_KEEP_ANNOUNCED_EVERY_S", 0.02)
    stamps = []

    def wait_for_the_card():
        stamps.append(R._active_generations[DEVICE]["ts"])
        time.sleep(0.2)
        stamps.append(R._active_generations[DEVICE]["ts"])

    run.seen["at_stage4"] = wait_for_the_card
    run("research")
    assert stamps[1] > stamps[0]
    time.sleep(0.1)
    assert not [t for t in threading.enumerate() if t.name.startswith("keep-announced-")]


# ---------------------------------------------------------------------------
# Plans that make media, and the kids/youth override
# ---------------------------------------------------------------------------

def test_a_named_model_on_an_output_config_is_refused_with_a_cause(monkeypatch):
    """The media-plan refusal stands behind the model gate on /pipeline/stage2,
    whose every refusal carries a cause."""
    R.init_schema_engine()
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    app = Flask(__name__)
    with app.test_request_context():
        body, status = R._run_stage2({"schema": "sd35_large", "input_text": LYRICS,
                                      "interception_model": "local/some-model",
                                      "device_id": DEVICE}, "kids")
    assert status >= 400
    assert body.get("cause"), body


def test_the_override_still_stands_where_the_plan_writes_an_interception(monkeypatch):
    """A skipping pipeline whose plan does hold an interception keeps the kids/youth override."""
    R.init_schema_engine()
    pipeline = SimpleNamespace(skip_stage2=True, pipeline_type="passthrough")
    monkeypatch.setattr(R.pipeline_executor.config_loader, "get_pipeline", lambda name: pipeline)
    config = SimpleNamespace(pipeline_name="some_pipeline", chunks=["manipulate"])
    assert R._skips_stage2(config, "kids") is False
    assert R._skips_stage2(config, "youth") is False
    assert R._skips_stage2(config, "research") is True


def test_an_unknown_chunk_keeps_the_override(monkeypatch):
    R.init_schema_engine()
    pipeline = SimpleNamespace(skip_stage2=True, pipeline_type="passthrough")
    monkeypatch.setattr(R.pipeline_executor.config_loader, "get_pipeline", lambda name: pipeline)
    config = SimpleNamespace(pipeline_name="some_pipeline", chunks=["no_such_chunk_here"])
    assert R._skips_stage2(config, "kids") is False


def test_shipped_configs_without_a_text_step_skip_at_every_level():
    """The real files: latent_lab and surrealizer run no text model in Stage 2."""
    R.init_schema_engine()
    loader = R.pipeline_executor.config_loader
    skipping = []
    for name in loader.list_configs():
        config = loader.get_config(name)
        if (config.meta or {}).get("stage") != "interception":
            continue
        pipeline = loader.get_pipeline(config.pipeline_name)
        if pipeline and pipeline.skip_stage2:
            skipping.append(name)
            for level in ("kids", "youth", "adult", "research"):
                assert R._skips_stage2(config, level) is True, (name, level)
    assert VEHICLE in skipping


def test_the_plan_reader_tells_media_from_text():
    R.init_schema_engine()
    loader = R.pipeline_executor.config_loader
    assert R._plan_makes_media(loader.get_config(SONG)) is True
    assert R._plan_makes_media(loader.get_config("sd35_large")) is True
    assert R._plan_makes_media(loader.get_config("latent_lab")) is False
    assert R._plan_makes_media(loader.get_config("user_defined")) is False
    assert R._plan_runs_no_text_model(loader.get_config("user_defined")) is False


def test_a_precheck_at_kids_on_a_skipped_plan_runs_the_classifier(monkeypatch):
    """/pipeline/stage2 with skip_optimization reached its classifier gate for
    these plans through the kids/youth override; it runs it itself now."""
    R.init_schema_engine()
    asked = []

    async def stage1(text, safety_level, pipeline_executor, user_language='de'):
        return (True, text, None, ["stub"])

    async def classifier(input_text, safety_level):
        asked.append((input_text, safety_level))
        return SimpleNamespace(success=True, final_output=input_text, error=None,
                               steps=[], metadata={}, execution_time=0)

    monkeypatch.setattr(R, "execute_stage1_safety_unified", stage1)
    monkeypatch.setattr(R, "execute_stage2_classifier", classifier)
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    app = Flask(__name__)
    with app.test_request_context():
        R._run_stage2({"schema": "latent_lab", "input_text": LYRICS,
                       "skip_optimization": True, "device_id": DEVICE}, "kids")
    assert asked == [(LYRICS, "kids")]


# ---------------------------------------------------------------------------
# Stage 3 as given
# ---------------------------------------------------------------------------

def _stage3_reading(monkeypatch, refuse=None):
    """execute_stage3_safety with the translation and the classifier replaced:
    the translation answers TRANSLATED, the classifier records what it reads
    and refuses the text named by `refuse`."""
    import asyncio
    from schemas.engine import stage_orchestrator as O
    read = []

    def classify(text, policy):
        read.append(text)
        unsafe = text == refuse
        return {"safe": not unsafe, "uncoded_unsafe": unsafe, "verdict": True,
                "model_used": "stub", "execution_time": 0, "llm_output": ""}

    class Executor:
        async def execute_pipeline(self, *a, **kw):
            return SimpleNamespace(success=True, final_output="TRANSLATED")

    monkeypatch.setattr(O, "_llm_safety_check_generation", classify)

    def run(level, as_given):
        return asyncio.run(O.execute_stage3_safety(LYRICS, level, "music", Executor(),
                                                   as_given=as_given)), read
    return run


def test_as_given_at_kids_reads_the_translation_and_the_text(monkeypatch):
    result, read = _stage3_reading(monkeypatch)("kids", True)
    assert read == ["TRANSLATED", LYRICS]
    assert result["safe"] and result["positive_prompt"] == LYRICS


def test_as_given_at_kids_refuses_a_text_its_translation_passed(monkeypatch):
    result, read = _stage3_reading(monkeypatch, refuse=LYRICS)("kids", True)
    assert read == ["TRANSLATED", LYRICS]
    assert result["safe"] is False


def test_as_given_at_youth_reads_the_text(monkeypatch):
    result, read = _stage3_reading(monkeypatch)("youth", True)
    assert read == [LYRICS]
    assert result["positive_prompt"] == LYRICS


def test_without_as_given_kids_reads_the_translation_alone(monkeypatch):
    result, read = _stage3_reading(monkeypatch)("kids", False)
    assert read == ["TRANSLATED"]
    assert result["positive_prompt"] == "TRANSLATED"


# ---------------------------------------------------------------------------
# How long a song runs
# ---------------------------------------------------------------------------

def _configs_that_sing():
    """Every output config whose run reaches output_music_heartmula.

    Read from the files, not listed by hand: until 2026-10-10 two configs
    named after ACE-Step reached this chunk through the music_generation
    pipeline without a length of their own (retired with S-010).
    """
    schemas = Path(__file__).resolve().parents[1] / "schemas"
    found = []
    for path in sorted((schemas / "configs" / "output").glob("*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        pipeline = schemas / "pipelines" / f"{config.get('pipeline', '')}.json"
        if not pipeline.exists():
            continue
        chunks = json.loads(pipeline.read_text(encoding="utf-8")).get("chunks", [])
        named = (config.get("parameters") or {}).get("OUTPUT_CHUNK")
        chunks = [named if c == "{{OUTPUT_CHUNK}}" else c for c in chunks]
        if "output_music_heartmula" in chunks:
            found.append(path.stem)
    return found


def test_the_configs_that_sing_are_found():
    assert SONG in _configs_that_sing()


@pytest.mark.parametrize("config_name", _configs_that_sing())
def test_a_song_from_a_prompt_runs_at_most_a_minute(monkeypatch, config_name):
    """A song from a prompt runs at most 60 s, for pragmatic and fair-culture
    reasons.

    heartlib generates one frame plus up to max_audio_length_ms // 80 frames of
    80 ms and stops earlier when the model ends the song, so this number is
    the longest HeartMuLa song a prompt can get. The Flow sends the two texts
    and no length (the stream reads none from it); the length comes from the
    config, or from the chunk's own default where a config names none.
    """
    import asyncio
    from schemas.engine.pipeline_executor import PipelineContext, executor

    seen = _parameters_at_the_router(monkeypatch)
    context = PipelineContext(input_text=LYRICS, user_input=STYLE)
    context.custom_placeholders = {"TEXT_1": LYRICS, "TEXT_2": STYLE}
    asyncio.run(executor.execute_pipeline(
        config_name=config_name, input_text=LYRICS, user_input=STYLE,
        context_override=context,
    ))
    assert len(seen) == 1
    length = seen[0].get("max_audio_length_ms")
    if length is None:
        from schemas.chunks.output_music_heartmula import DEFAULTS
        length = DEFAULTS["max_audio_length_ms"]
    assert 0 < length <= 60_000


def test_the_recording_page_passes_its_own_length_over_it(monkeypatch):
    """Re-enactment (formerly Silly Parrot / Cover Band) hands HeartMuLa the
    recording's length.

    parrot_service._sing hands the recording's length to the chunk as a custom
    placeholder, which ChunkBuilder merges over the config's 60 s; the page's
    frame is 10 to 240 s (SONG_MIN_MS..SONG_MAX_MS, 4d07ece3, bbd41622).
    """
    from my_app.services import parrot_service as P

    seen = _parameters_at_the_router(monkeypatch)
    assert P._sing({"lyrics": LYRICS, "tags": STYLE}, 137_000, P.SONG_CONFIG) is None
    assert [p.get("max_audio_length_ms") for p in seen] == [137_000]
