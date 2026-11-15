#!/usr/bin/env python3
"""The Canvas's intake, and its check at the result.

A board passes the intake on the server before any of it runs or is kept
(canvas_executor.board_intake): its name and description and every text on its
nodes go through check_intake, and at kids and youth a picture on it needs a
verdict that answers for the level. The run stream and the batch refuse a board
before a run of it exists; the batch reads each of its prompts before that
prompt's run; keeping a refused board answers 403 and stores nothing.

Every node that shows what a language model wrote asks the check at the result
before the text is kept, shown or handed on (CanvasWorkflowExecutor._withheld).
A withheld text goes nowhere, and the node stops its branch with the block.

The gate functions, the language models and the run's machinery are stubbed;
nothing here asks a model.
"""
import json
import sys
import types
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.schema_pipeline_routes as spr
from my_app.routes import canvas_routes
from my_app.services import canvas_executor
from my_app.services import canvas_run_service as crs
from my_app.services.canvas_executor import CanvasWorkflowExecutor, board_intake, intake_refusal
from my_app.services.safety_gate import (CHECKPOINT_INTAKE, CHECKPOINT_RESULT, REASON_CONTENT,
                                         REASON_IMAGE_UNCHECKED, REASON_PERSONAL_DATA, Verdict)

AT_THE_INTAKE = "refuse-at-the-intake"
AT_THE_RESULT = "refuse-at-the-result"

BOARD = {
    "name": "Perspektive gegen Rohtext",
    "description": "zwei Wege",
    "nodes": [
        {"id": "in1", "type": "input", "promptText": "Ein Haus am Meer"},
        {"id": "ic1", "type": "interception", "contextPrompt": "Sieh es als Ort."},
        {"id": "tr1", "type": "translation", "translationPrompt": "Übersetze.",
         "translationLanguage": "en"},
        {"id": "ev1", "type": "evaluation", "evaluationPrompt": "Ist es klar?"},
        {"id": "cmp1", "type": "comparison_evaluator", "comparisonCriteria": "Klarheit"},
        {"id": "rp1", "type": "random_prompt", "randomPromptSystemPrompt": "Schreib frei."},
        {"id": "ie1", "type": "image_evaluation", "imageEvaluationPrompt": "Was ist zu sehen?"},
        {"id": "out1", "type": "display", "title": "Ergebnis"},
    ],
    "connections": [],
}

PICTURE = {"id": "img1", "type": "image_input",
           "imageData": {"image_id": "u1", "image_path": "/uploads/u1.png"}}


@pytest.fixture
def intake(monkeypatch):
    """check_intake keeps what it read and refuses a text with AT_THE_INTAKE in
    it; a picture has a verdict where `cleared` holds its path."""
    seen = {"read": {}, "cleared": set(), "pictures": []}

    def check(material, *, level, kind, field):
        seen["read"][field] = material
        if AT_THE_INTAKE in str(material or ""):
            return Verdict(False, CHECKPOINT_INTAKE, level, field, REASON_PERSONAL_DATA,
                           "refused at the intake")
        return Verdict(True, CHECKPOINT_INTAKE, level, field)

    def cleared(ref, level):
        seen["pictures"].append((ref, level))
        return ref in seen["cleared"]

    monkeypatch.setattr(canvas_executor, "check_intake", check)
    monkeypatch.setattr(canvas_routes, "check_intake", check)
    monkeypatch.setattr(canvas_executor, "image_reference_cleared", cleared)
    return seen


def _read(seen):
    """What the intake read, without the fields the board left empty."""
    return {field: text for field, text in seen["read"].items() if text}


# ── The board ───────────────────────────────────────────────────────────────

def test_the_intake_reads_every_text_of_the_board(intake):
    verdict, node = board_intake(BOARD["nodes"], level="kids", workflow=BOARD)
    assert verdict.passed and node is None
    assert _read(intake) == {
        "workflow[name]": "Perspektive gegen Rohtext",
        "workflow[description]": "zwei Wege",
        "nodes[in1].promptText": "Ein Haus am Meer",
        "nodes[ic1].contextPrompt": "Sieh es als Ort.",
        "nodes[tr1].translationPrompt": "Übersetze.",
        "nodes[tr1].translationLanguage": "en",
        "nodes[ev1].evaluationPrompt": "Ist es klar?",
        "nodes[cmp1].comparisonCriteria": "Klarheit",
        "nodes[rp1].randomPromptSystemPrompt": "Schreib frei.",
        "nodes[ie1].imageEvaluationPrompt": "Was ist zu sehen?",
        "nodes[out1].title": "Ergebnis",
    }


def test_a_refused_text_on_a_node_names_the_node(intake):
    nodes = [dict(n) for n in BOARD["nodes"]]
    nodes[1]["contextPrompt"] = f"Sieh es als Ort. {AT_THE_INTAKE}"
    verdict, node = board_intake(nodes, level="youth", workflow=BOARD)
    assert not verdict.passed and verdict.field == "nodes[ic1].contextPrompt"
    assert node["id"] == "ic1"
    event = intake_refusal(verdict, node)
    assert event["message"] == "refused at the intake"
    assert event["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert event["errors"] == [{"node_id": "ic1", "node_type": "interception",
                                "error": "refused at the intake",
                                "safety_block": event["safety_block"]}]
    assert event["results"]["ic1"]["safety_block"] == event["safety_block"]


def test_a_refused_name_of_the_board_names_no_node(intake):
    verdict, node = board_intake(BOARD["nodes"], level="adult",
                                 workflow={**BOARD, "name": AT_THE_INTAKE})
    assert not verdict.passed and verdict.field == "workflow[name]" and node is None
    event = intake_refusal(verdict, node)
    assert event["errors"][0]["node_id"] is None and event["results"] == {}


def test_a_batch_of_prompts_leaves_the_input_texts_to_its_prompts(intake):
    board_intake(BOARD["nodes"], level="kids", workflow=BOARD, with_inputs=False)
    assert "nodes[in1].promptText" not in intake["read"]
    assert intake["read"]["nodes[ic1].contextPrompt"] == "Sieh es als Ort."


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_a_picture_without_a_verdict_is_refused_at_kids_and_youth(intake, level):
    verdict, node = board_intake([PICTURE], level=level)
    assert not verdict.passed and node["id"] == "img1"
    assert verdict.reason_key == REASON_IMAGE_UNCHECKED
    assert verdict.field == "nodes[img1].imageData"
    assert intake["pictures"] == [("/uploads/u1.png", level)]


def test_a_picture_with_its_verdict_passes(intake):
    intake["cleared"].add("/uploads/u1.png")
    verdict, _node = board_intake([PICTURE], level="kids")
    assert verdict.passed


@pytest.mark.parametrize("level", ["adult", "research"])
def test_above_youth_no_picture_is_asked_about(intake, level):
    verdict, _node = board_intake([PICTURE], level=level)
    assert verdict.passed and intake["pictures"] == []


# ── The run stream ──────────────────────────────────────────────────────────

@pytest.fixture
def app(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(canvas_routes.canvas_bp)
    monkeypatch.setattr(canvas_routes, "resolve_safety_level", lambda: "kids")
    return app


def _events(body):
    """(name, payload) of every event on the wire, in order."""
    out = []
    for raw in body.split("\n\n"):
        name = data = None
        for line in raw.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if name:
            out.append((name, data))
    return out


@pytest.fixture
def runs(monkeypatch):
    """start_run records what it was handed; the run's events are one `complete`."""
    started = []

    def start_run(**kw):
        started.append(kw)
        return "run_stand_in"

    def iter_events(run_id, after=-1, timeout=300.0, client_gone=None):
        yield {"_i": 0, "type": "complete", "data": {"run_id": run_id}}

    monkeypatch.setattr(crs, "start_run", start_run)
    monkeypatch.setattr(crs, "iter_events", iter_events)
    return started


def test_a_refused_board_gets_one_error_and_no_run(app, intake, runs):
    nodes = [{"id": "in1", "type": "input", "promptText": AT_THE_INTAKE}]
    body = app.test_client().post("/api/canvas/execute-stream",
                                  json={"nodes": nodes, "connections": []}).get_data(as_text=True)
    [(name, data)] = _events(body)
    assert name == "error"
    assert data["safety_block"]["field"] == "nodes[in1].promptText"
    assert data["errors"][0]["node_id"] == "in1"
    assert runs == [], "a run was started for a refused board"


def test_a_board_that_passes_starts_its_run(app, intake, runs):
    nodes = [{"id": "in1", "type": "input", "promptText": "Ein Haus"}]
    body = app.test_client().post("/api/canvas/execute-stream",
                                  json={"nodes": nodes, "connections": [],
                                        "workflow": {"name": "Haus"}}).get_data(as_text=True)
    assert [name for name, _ in _events(body)] == ["run_started", "started", "complete"]
    [run] = runs
    assert run["safety_level"] == "kids" and run["name"] == "Haus"
    assert intake["read"]["workflow[name]"] == "Haus"
    assert intake["read"]["nodes[in1].promptText"] == "Ein Haus"


# ── The batch ───────────────────────────────────────────────────────────────

@pytest.fixture
def batch(app, intake, monkeypatch):
    """The batch, with its executor and recorders stood in for. `runs` keeps
    the prompt each run was given, `recorders` the runs that made a record, and
    `result` is what every run's executor answers."""
    seen = {"runs": [], "recorders": [], "result": {"success": True}}

    class Recorder:
        device_id = "dev"
        run_folder = Path("/nonexistent")

        def mark_complete(self):
            pass

    class Executor:
        def __init__(self, **kw):
            seen["runs"].append(kw.get("prompt_override"))

        def execute_with_events(self):
            return iter(())

        def get_result(self):
            return seen["result"]

    def recorder(run_id, **kw):
        seen["recorders"].append(run_id)
        return Recorder()

    engine = types.ModuleType("schemas.engine.prompt_interception_engine")
    engine.PromptInterceptionEngine = lambda: object()
    engine.PromptInterceptionRequest = object
    monkeypatch.setitem(sys.modules, "schemas.engine.prompt_interception_engine", engine)
    monkeypatch.setattr(canvas_routes, "get_canvas_recorder", recorder)
    monkeypatch.setattr(canvas_routes, "cleanup_canvas_recorder", lambda run_id: None)
    monkeypatch.setattr(canvas_routes, "CanvasWorkflowExecutor", Executor)

    def post(**body):
        return _events(app.test_client().post("/api/canvas/execute-batch", json=body)
                       .get_data(as_text=True))

    post.seen = seen
    return post


def test_a_refused_board_runs_no_batch(batch):
    board = {"nodes": [{"id": "ic1", "type": "interception", "contextPrompt": AT_THE_INTAKE}],
             "connections": []}
    events = batch(workflow=board, count=2)
    assert [name for name, _ in events] == ["error"]
    assert events[0][1]["safety_block"]["field"] == "nodes[ic1].contextPrompt"
    assert batch.seen["recorders"] == [] and batch.seen["runs"] == []


def test_a_refused_prompt_ends_its_run_and_the_batch_goes_on(batch):
    """The board's own input text is no material in prompt mode: the prompts
    replace it."""
    board = {"nodes": [{"id": "in1", "type": "input", "promptText": AT_THE_INTAKE}],
             "connections": []}
    events = batch(workflow=board,
                   prompts=["Ein Wald", f"Ein Fluss {AT_THE_INTAKE}", "Ein See"])
    assert [name for name, _ in events] == [
        "batch_started", "run_start", "run_complete", "run_start", "run_error",
        "run_start", "run_complete", "batch_complete"]
    [refused] = [data for name, data in events if name == "run_error"]
    assert refused["run_index"] == 1
    assert refused["safety_block"]["field"] == "prompts[1]"
    assert batch.seen["runs"] == ["Ein Wald", "Ein See"]
    assert len(batch.seen["recorders"]) == 2


def test_a_node_the_checks_refused_carries_its_block_into_run_error(batch):
    block = {"checkpoint": "result", "field": "interception", "reason_key": "content",
             "reason": "withheld"}
    batch.seen["result"] = {"success": False, "error": "ic1 (interception): withheld",
                            "errors": [{"node_id": "ic1", "error": "withheld",
                                        "safety_block": block}]}
    events = batch(workflow={"nodes": [{"id": "in1", "type": "input"}], "connections": []},
                   count=1)
    [refused] = [data for name, data in events if name == "run_error"]
    assert refused["safety_block"] == block


# ── Keeping a board ─────────────────────────────────────────────────────────

def test_keeping_a_refused_board_stores_nothing(app, intake, monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    board = {"name": AT_THE_INTAKE, "nodes": [], "connections": []}
    r = app.test_client().post("/api/canvas/keep", json={"workflow": board})
    assert r.status_code == 403
    body = r.get_json()
    assert body["status"] == "blocked"
    assert body["safety_block"]["field"] == "workflow[name]"
    assert list(tmp_path.iterdir()) == []


# ── What a language model wrote ─────────────────────────────────────────────

KINDS = ["random_prompt", "interception", "translation", "model_adaption", "evaluation",
         "comparison_evaluator", "image_evaluation"]


class _Response:
    success = True
    error = None
    model_used = "stub-model"
    output_float = None

    def __init__(self, text):
        self.output_str = text


class _Engine:
    def __init__(self, answer):
        self.answer = answer

    async def process_request(self, req):
        return _Response(self.answer)


class _Recorder:
    def __init__(self):
        self.saved = []

    def save_entity(self, **kw):
        self.saved.append(kw)


def _graph(kind):
    """A board on which a node `n` of `kind` writes, with a display after it."""
    if kind == "random_prompt":
        nodes = [{"id": "n", "type": "random_prompt", "randomPromptModel": "local/stub"}]
        connections = []
    elif kind == "image_evaluation":
        nodes = [dict(PICTURE, id="src"),
                 {"id": "n", "type": "image_evaluation", "visionModel": "local/stub-vision"}]
        connections = [{"sourceId": "src", "targetId": "n"}]
    elif kind == "comparison_evaluator":
        nodes = [{"id": "a", "type": "input", "promptText": "Ein Haus"},
                 {"id": "b", "type": "input", "promptText": "Ein Baum"},
                 {"id": "n", "type": "comparison_evaluator", "comparisonLlmModel": "local/stub"}]
        connections = [{"sourceId": "a", "targetId": "n", "label": "input-1"},
                       {"sourceId": "b", "targetId": "n", "label": "input-2"}]
    else:
        node = {"id": "n", "type": kind, "llmModel": "local/stub"}
        if kind == "interception":
            node["contextPrompt"] = "Sieh es als Ort."
        if kind == "model_adaption":
            node["modelAdaptionPreset"] = "video"
        nodes = [{"id": "src", "type": "input", "promptText": "Ein Haus am Meer"}, node]
        connections = [{"sourceId": "src", "targetId": "n"}]
    nodes.append({"id": "out", "type": "display"})
    connections.append({"sourceId": "n", "targetId": "out"})
    return nodes, connections


@pytest.fixture
def results(monkeypatch):
    """The check at the result keeps what it read and withholds a text with
    AT_THE_RESULT in it."""
    seen = []

    def check(text, *, level, field="text"):
        seen.append((text, level, field))
        if AT_THE_RESULT in str(text or ""):
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT, "withheld")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(canvas_executor, "check_result_text", check)
    return seen


@pytest.fixture
def writing(monkeypatch):
    """Runs a board at kids on which a node of a kind writes `text`."""
    from my_app.utils import image_analysis
    monkeypatch.setattr(spr, "load_output_config_defaults", lambda: {"video": "a_video_config"})
    monkeypatch.setattr(spr, "_load_optimization_instruction",
                        lambda config_id: "VIDEO RULES" if config_id == "a_video_config" else None)
    monkeypatch.setattr(spr, "_load_optimization_model", lambda config_id: None)

    def run(kind, text):
        def read_the_picture(image_ref, **kw):
            return text

        monkeypatch.setattr(image_analysis, "analyze_image", read_the_picture)
        answer = f"COMMENTARY: {text}\nSCORE: 7" if kind == "evaluation" else text
        nodes, connections = _graph(kind)
        recorder = _Recorder()
        ex = CanvasWorkflowExecutor(nodes, connections, recorder, "run_test", _Engine(answer),
                                    safety_level="kids")
        list(ex.execute_with_events())
        return ex, recorder

    return run


@pytest.mark.parametrize("kind", KINDS)
def test_what_a_model_wrote_is_checked_before_it_is_shown(results, writing, kind):
    ex, _recorder = writing(kind, "Ein Haus steht am Meer.")
    assert results == [("Ein Haus steht am Meer.", "kids", kind)]
    assert ex.results["n"].get("error") is None
    assert "out" in ex.results, "a text that passed did not go on"


@pytest.mark.parametrize("kind", KINDS)
def test_a_withheld_text_is_neither_kept_nor_handed_on(results, writing, kind):
    ex, recorder = writing(kind, f"Ein Haus. {AT_THE_RESULT}")
    res = ex.results["n"]
    assert res["error"] == "withheld"
    assert res["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert res["safety_block"]["field"] == kind
    assert AT_THE_RESULT not in json.dumps(res)
    assert [kept for kept in recorder.saved if kept.get("node_id") == "n"] == []
    assert "out" not in ex.results, "a withheld text went on"
    [error] = ex.get_result()["errors"]
    assert error["node_id"] == "n" and error["safety_block"] == res["safety_block"]


def test_a_refusal_of_the_perspective_is_said_as_a_block(results, writing):
    from schemas.engine.instruction_selector import SAFETY_REFUSAL_SENTENCE
    ex, _recorder = writing("interception",
                            SAFETY_REFUSAL_SENTENCE + " Bitte formuliere es anders.")
    res = ex.results["n"]
    assert res["output"] == ""
    assert res["safety_block"]["checkpoint"] == "refusal"
    assert res["safety_block"]["reason_key"] == "refusal"
    assert results == [], "a refusal is no text to show"
    assert "out" not in ex.results
