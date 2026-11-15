"""The code of a sketch goes through the check at the result.

A p5.js or Tone.js sketch is code a language model wrote, and it runs in the
browser of whoever is shown it. The check at the result reads that code before
it leaves the server, on each way that makes it: the output step, which the
one-body answer and the Canvas reach; the stream, which runs the check while
its own loop keeps the connection alive; and /pipeline/interception. Its
verdict lands on the sketch's entity, and delivery reads it as it reads a
picture's: at kids and youth only with a pass that answers for whoever asks,
and a sketch refused at adult is not handed out at adult either.

Where the test is about who asks the check with what, the check is a stand-in.
Where the verdict's way onto the entity is under test, the real check runs and
only the classifier's answer is a stand-in. No model, no GPU.

Run: cd devserver && python3 -m pytest tests/test_code_check_at_result.py -q
"""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

import config
from my_app.routes import media_routes as M
from my_app.routes import pipeline_routes as P
from my_app.routes import schema_pipeline_routes as R
from my_app.services import pipeline_recorder as pr
from my_app.services import safety_gate as gate
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         CHECKPOINT_RESULT, REASON_CODE, REASON_UNCHECKED,
                                         Verdict)

SKETCH = "function setup() { createCanvas(400, 400); circle(200, 200, 80); }"
REFUSED = "refuse-this-sketch"
PROMPT = "Ein Kreis, der langsam wächst."
DEVICE = "test-code-check"
GENERATION = "/api/schema/pipeline/generation"
INTERCEPTION = "/api/schema/pipeline/interception"
BLOCK = {"checkpoint": CHECKPOINT_RESULT, "field": "code", "reason_key": REASON_CODE}


class _Check:
    """The check at the result as a stand-in: it records what it read and
    refuses a sketch that carries its mark."""

    def __init__(self):
        self.read = []

    def __call__(self, code, *, level, recorder=None, entity=None, field="code"):
        self.read.append({"code": code, "level": level, "entity": entity})
        if REFUSED in code:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CODE,
                           "refused at the result")
        return Verdict(True, CHECKPOINT_RESULT, level, field)


class _Recorder:
    """Takes every call a run makes on its record; keeps its entities and errors."""

    def __init__(self):
        self.metadata = {"entities": [], "models_used": {}}
        self.errors = []

    def save_entity(self, entity_type, content=None, metadata=None, **kw):
        sequence = len(self.metadata["entities"]) + 1
        self.metadata["entities"].append(
            {"sequence": sequence, "type": entity_type, "metadata": dict(metadata or {})})
        return f"{sequence:02d}_{entity_type}"

    def save_error(self, **kw):
        self.errors.append(kw)

    def output_entities(self, *a, **kw):
        return []

    def __getattr__(self, name):
        return lambda *a, **kw: None


def _sequence(recorder, kind):
    [entity] = [e for e in recorder.metadata["entities"] if e["type"] == kind]
    return entity["sequence"]


def _block_of(answer):
    return {key: answer["safety_block"][key] for key in BLOCK}


def _events(text):
    """The named frames of a stream, in order, as (event, data)."""
    out = []
    for block in text.split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if name:
            out.append((name, data))
    return out


def _named(events, name):
    return [data for event, data in events if event == name]


def _schema_client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp, url_prefix="/api/schema")
    return app.test_client()


# ---------------------------------------------------------------------------
# The output step: the one-body answer and the Canvas
# ---------------------------------------------------------------------------

@pytest.fixture
def step(tmp_path, monkeypatch):
    """The output step on a run record of its own, with a code model that
    writes back the prompt it was given."""
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(pr, "_active_recorders", {})
    check = _Check()

    async def execute_pipeline(**kw):
        return SimpleNamespace(success=True, final_output=kw["input_text"], metadata={},
                               error=None, execution_time=0)

    monkeypatch.setattr(R, "pipeline_executor", SimpleNamespace(
        execute_pipeline=execute_pipeline,
        config_loader=SimpleNamespace(get_config=lambda name: None)))
    monkeypatch.setattr(R, "check_result_code", check)

    def run(code, level="kids", output_config="p5js_code", **kw):
        run_id = f"run_{output_config}_{level}"
        result = asyncio.run(R.execute_stage4_generation_only(
            prompt=code, output_config=output_config, safety_level=level, run_id=run_id,
            seed=1, **kw))
        return result, pr._active_recorders[run_id]

    run.check = check
    run.monkeypatch = monkeypatch
    return run


@pytest.mark.parametrize("output_config, kind", [("p5js_code", "p5"), ("tonejs_code", "tonejs")])
def test_the_output_step_checks_the_sketch_it_recorded(step, output_config, kind):
    result, recorder = step(SKETCH, output_config=output_config)
    assert step.check.read == [
        {"code": SKETCH, "level": "kids", "entity": _sequence(recorder, kind)}]
    assert result["success"] is True
    assert result["media_output"]["code"] == SKETCH


def test_a_refused_sketch_does_not_leave_the_output_step(step):
    result, recorder = step(f"{SKETCH} // {REFUSED}")
    assert result["success"] is False
    assert _block_of(result) == BLOCK
    assert REFUSED not in json.dumps(result)
    [error] = [e for e in recorder.metadata["entities"] if e["type"] == "error"]
    assert error["metadata"]["error_type"] == "safety_blocked"


def test_a_caller_that_runs_the_check_itself_is_not_asked_twice(step):
    result, _recorder = step(SKETCH, check_at_result=False)
    assert step.check.read == []
    assert result["success"] is True


def test_the_verdict_lands_on_the_sketch_where_delivery_reads_it(step):
    """The real check; only the classifier's answer to the text question is a
    stand-in. The sketch names nothing from the pattern list, so no other
    question is asked."""
    def text_passes(text, *, level, field="text"):
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    assert gate.code_patterns_in(SKETCH) == []
    step.monkeypatch.setattr(gate, "check_result_text", text_passes)
    step.monkeypatch.setattr(R, "check_result_code", gate.check_result_code)
    result, recorder = step(SKETCH, level="kids")
    [sketch] = [e for e in recorder.metadata["entities"] if e["type"] == "p5"]
    assert result["success"] is True
    verdict = sketch["metadata"][pr.SAFETY_VERDICT_KEY]
    assert (verdict["safe"], verdict["level"]) == (True, "kids")


# ---------------------------------------------------------------------------
# The stream
# ---------------------------------------------------------------------------

@pytest.fixture
def stream(monkeypatch):
    """/pipeline/generation on the stream, for a sketch. The intake and the
    check before the model pass; the output step records the sketch and hands
    it back without checking it, as it does for the stream."""
    R.init_schema_engine()
    check = _Check()
    recorders = []
    written = {}
    asked_stage4 = []

    async def translate(text, pipeline_executor, **kw):
        return text

    async def stage4(**kw):
        asked_stage4.append(kw.get("check_at_result"))
        kw["recorder"].save_entity("p5", written["code"])
        run_id = kw["run_id"]
        return {"success": True, "run_id": run_id,
                "media_output": {"media_type": "code", "url": f"/api/media/p5/{run_id}",
                                 "code": written["code"], "run_id": run_id, "seed": 1}}

    def recorder(**kw):
        made = _Recorder()
        recorders.append(made)
        return made

    def passes(checkpoint):
        return lambda *a, level, **kw: Verdict(True, checkpoint, level)

    monkeypatch.setattr(R, "check_intake_texts", passes(CHECKPOINT_INTAKE))
    monkeypatch.setattr(R, "check_before_model", passes(CHECKPOINT_BEFORE_MODEL))
    monkeypatch.setattr(R, "_translate_for_model", translate)
    monkeypatch.setattr(R, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(R, "get_recorder", recorder)
    monkeypatch.setattr(R, "check_result_code", check)
    client = _schema_client()

    def run(code, level="kids"):
        written["code"] = code
        monkeypatch.setattr(R, "resolve_safety_level", lambda: level)
        response = client.get(GENERATION, query_string={
            "prompt": PROMPT, "output_config": "p5js_code", "device_id": DEVICE,
            "enable_streaming": "true"})
        # A stream runs as it is read: read it whole before anything is asserted.
        text = response.get_data(as_text=True)
        return _events(text), text, recorders[-1]

    run.check = check
    run.asked_stage4 = asked_stage4
    yield run
    R._active_generations.pop(DEVICE, None)


def test_the_stream_checks_the_sketch_once_and_sends_it_on_a_pass(stream):
    events, _text, recorder = stream(SKETCH)
    assert stream.asked_stage4 == [False]
    assert stream.check.read == [
        {"code": SKETCH, "level": "kids", "entity": _sequence(recorder, "p5")}]
    [complete] = _named(events, "complete")
    assert complete["media_output"]["code"] == SKETCH
    assert _named(events, "blocked") == []


def test_the_stream_does_not_send_a_refused_sketch(stream):
    events, text, recorder = stream(f"{SKETCH} // {REFUSED}")
    assert _named(events, "complete") == []
    [blocked] = _named(events, "blocked")
    assert _block_of(blocked) == BLOCK
    assert REFUSED not in text
    assert [e["details"]["check"] for e in recorder.errors] == ["result"]


# ---------------------------------------------------------------------------
# /pipeline/interception
# ---------------------------------------------------------------------------

@pytest.fixture
def interception(monkeypatch):
    """/pipeline/interception for a sketch, under a perspective whose plan
    writes no text. The intake and the output config, which hands the sketch
    on, are replaced."""
    R.init_schema_engine()
    check = _Check()
    recorders = []
    written = {}

    async def execute_pipeline(config_name=None, **kw):
        return SimpleNamespace(success=True, final_output=written["code"], metadata={},
                               steps=[], execution_time=0, error=None)

    def recorder(**kw):
        made = _Recorder()
        recorders.append(made)
        return made

    monkeypatch.setattr(R, "check_intake_texts",
                        lambda fields, *, level: Verdict(True, CHECKPOINT_INTAKE, level))
    monkeypatch.setattr(R.pipeline_executor, "execute_pipeline", execute_pipeline)
    monkeypatch.setattr(R, "get_recorder", recorder)
    monkeypatch.setattr(R, "check_result_code", check)
    client = _schema_client()

    def run(code, level="kids"):
        written["code"] = code
        monkeypatch.setattr(R, "resolve_safety_level", lambda: level)
        response = client.post(INTERCEPTION, json={
            "schema": "latent_lab", "input_text": PROMPT, "output_config": "p5js_code",
            "device_id": DEVICE, "user_language": "de"})
        return response, recorders[-1]

    run.check = check
    yield run
    R._active_generations.pop(DEVICE, None)


def test_the_interception_route_checks_the_sketch_it_recorded(interception):
    response, recorder = interception(SKETCH)
    assert interception.check.read == [
        {"code": SKETCH, "level": "kids", "entity": _sequence(recorder, "p5")}]
    assert response.status_code == 200
    assert SKETCH in response.get_data(as_text=True)


def test_the_interception_route_does_not_hand_out_a_refused_sketch(interception):
    response, recorder = interception(f"{SKETCH} // {REFUSED}")
    body = response.get_json()
    assert response.status_code == 403 and body["status"] == "blocked"
    assert _block_of(body) == BLOCK
    assert REFUSED not in response.get_data(as_text=True)
    assert [e["details"]["check"] for e in recorder.errors] == ["result"]


# ---------------------------------------------------------------------------
# Delivery: /api/media/p5, /tonejs, /sonicpi, and the run's own entity routes
# ---------------------------------------------------------------------------

@pytest.fixture
def media(tmp_path, monkeypatch):
    """The media routes over a run storage of their own. `put` lays down a run
    made at `made_at` with one piece of code, carrying `safety` as its verdict
    (None: none)."""
    monkeypatch.setattr(M, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(P, "PIPELINE_BASE_PATH", tmp_path)
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(pr, "_active_recorders", {})
    app = Flask(__name__)
    app.register_blueprint(M.media_bp)
    app.register_blueprint(P.pipeline_bp)
    client = app.test_client()

    def put(run_id, kind, made_at, safety=None):
        folder = tmp_path / "2026-10-31" / "a-device" / run_id
        (folder / "final").mkdir(parents=True)
        filename = f"01_{kind}.txt"
        (folder / "final" / filename).write_text(SKETCH)
        entity = {"sequence": 1, "type": kind, "filename": filename,
                  "metadata": {"format": "txt"}}
        if safety is not None:
            entity["metadata"][pr.SAFETY_VERDICT_KEY] = safety
        (folder / "metadata.json").write_text(json.dumps(
            {"run_id": run_id, "config_name": "p5js_code", "safety_level": made_at,
             "entities": [entity]}))

    def get(kind, run_id, level):
        monkeypatch.setattr(M, "resolve_safety_level", lambda: level)
        return client.get(f"/api/media/{kind}/{run_id}")

    def get_path(path, level):
        monkeypatch.setattr(P, "resolve_safety_level", lambda: level)
        return client.get(path)

    return SimpleNamespace(put=put, get=get, get_path=get_path)


@pytest.mark.parametrize("kind", ["p5", "tonejs", "sonicpi"])
def test_code_with_a_pass_that_answers_for_the_asker_is_delivered(media, kind):
    media.put("run_passed", kind, "kids", {"safe": True, "reason": "", "level": "kids"})
    response = media.get(kind, "run_passed", "youth")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == SKETCH


@pytest.mark.parametrize("kind", ["p5", "tonejs", "sonicpi"])
def test_code_without_a_verdict_is_withheld_from_kids(media, kind):
    media.put("run_unchecked", kind, "kids")
    response = media.get(kind, "run_unchecked", "kids")
    assert response.status_code == 403
    block = response.get_json()["safety_block"]
    assert (block["field"], block["reason_key"]) == ("code", REASON_UNCHECKED)
    assert SKETCH not in response.get_data(as_text=True)


@pytest.mark.parametrize("asker, status", [("adult", 403), ("kids", 403), ("research", 200)])
def test_a_sketch_refused_at_adult_is_withheld_there_and_below(media, asker, status):
    media.put("run_refused", "tonejs", "adult", {"safe": False, "reason": "x", "level": "adult"})
    response = media.get("tonejs", "run_refused", asker)
    assert response.status_code == status
    if status == 403:
        assert _block_of(response.get_json()) == BLOCK


@pytest.mark.parametrize("path", ["/api/pipeline/run_entity/entity/p5",
                                  "/api/pipeline/run_entity/file/01_p5.txt"])
def test_the_run_routes_refuse_a_sketch_as_code(media, path):
    """The run's own routes reach the same file through the recorder's door,
    and say what they refused."""
    media.put("run_entity", "p5", "kids")
    response = media.get_path(path, "kids")
    assert response.status_code == 403
    block = response.get_json()["safety_block"]
    assert (block["field"], block["reason_key"]) == ("code", REASON_UNCHECKED)
    assert SKETCH not in response.get_data(as_text=True)
