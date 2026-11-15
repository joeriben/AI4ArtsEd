#!/usr/bin/env python3
"""
The Canvas node "Model Adaption" runs (2026-09-27).

Until then the executor had no branch for it: a chain input -> Model Adaption
-> display ended at the node, and the run reported complete with nothing in
the display. The node now runs the flow's adaption step (/pipeline/optimize):
the adaption instruction of the target's output config, carried out by the
model that config names for its adaption, else by the Stage 2 interception
model. A target whose config carries no instruction passes the text on
unchanged.

The engine and the two loaders of the routes module are stubbed; what is
under test is the executor's routing and what it sends.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.schema_pipeline_routes as spr
from my_app.services.canvas_executor import CanvasWorkflowExecutor


@pytest.fixture(autouse=True)
def _results_pass(monkeypatch):
    """The check at the result lets every text pass; test_canvas_checks.py
    tests it."""
    from my_app.services import canvas_executor
    from my_app.services.safety_gate import CHECKPOINT_RESULT, Verdict

    def passes(text, *, level, field="text"):
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(canvas_executor, "check_result_text", passes)


class _Recorder:
    def __init__(self):
        self.saved = []

    def save_entity(self, **kw):
        self.saved.append(kw)


class _Response:
    def __init__(self, text):
        self.success = True
        self.output_str = text
        self.error = None
        self.model_used = "stub-model"


class _Engine:
    def __init__(self):
        self.requests = []

    async def process_request(self, req):
        self.requests.append(req)
        return _Response(f"ADAPTED[{req.input_prompt}]")


@pytest.fixture
def stubs(monkeypatch):
    video = (spr.load_output_config_defaults() or {}).get("video")
    assert video, "the medium defaults name no video config"
    instructions = {video: "VIDEO RULES"}
    monkeypatch.setattr(spr, "_load_optimization_instruction", lambda c: instructions.get(c))
    monkeypatch.setattr(spr, "_load_optimization_model", lambda c: None)
    return video


def _run(preset):
    nodes = [
        {"id": "in", "type": "input", "promptText": "a red circle"},
        {"id": "ad", "type": "model_adaption", "modelAdaptionPreset": preset},
        {"id": "out", "type": "display"},
    ]
    connections = [{"sourceId": "in", "targetId": "ad"}, {"sourceId": "ad", "targetId": "out"}]
    engine = _Engine()
    ex = CanvasWorkflowExecutor(nodes, connections, _Recorder(), "run_test", engine)
    list(ex.execute_with_events())
    return ex, engine


def test_video_runs_the_video_instruction(stubs):
    ex, engine = _run("video")
    assert ex.execution_trace == ["in", "ad", "out"]
    assert len(engine.requests) == 1
    assert engine.requests[0].style_prompt == "VIDEO RULES"
    assert engine.requests[0].input_prompt == "a red circle"
    res = ex.results["ad"]
    assert res["output"] == "ADAPTED[a red circle]"
    assert res["config_id"] == stubs and res["adapted"] is True and res["error"] is None
    assert ex.get_result()["success"] is True


def test_the_model_is_the_flows(stubs, monkeypatch):
    import config
    ex, engine = _run("video")
    assert engine.requests[0].model == config.STAGE2_INTERCEPTION_MODEL
    monkeypatch.setattr(spr, "_load_optimization_model", lambda c: "named-by-config")
    ex, engine = _run("video")
    assert engine.requests[0].model == "named-by-config"


@pytest.mark.parametrize("preset", ["sd35", "flux", "none"])
def test_no_instruction_passes_the_text_on(stubs, preset):
    ex, engine = _run(preset)
    assert ex.execution_trace == ["in", "ad", "out"]
    assert engine.requests == []
    assert ex.results["ad"]["output"] == "a red circle"
    assert ex.results["ad"]["adapted"] is False


def test_a_looped_answer_goes_on_in_its_once_form(stubs):
    """No error for a model that began to repeat itself: the text goes on with
    what repeated in it standing in it once, as at the translation node
    (docs/DEVELOPMENT_DECISIONS.md, 2026-10-31). The engine side is in
    test_interception_local_branch.py."""
    _, engine = _run("video")
    assert engine.requests[0].loop_once is True
