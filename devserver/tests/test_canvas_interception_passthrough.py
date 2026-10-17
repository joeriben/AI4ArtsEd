#!/usr/bin/env python3
"""A Canvas interception node with no perspective hands its input on verbatim.

It is the flow's empty zone: "Du bestimmst" with nothing filled in, where the
user's wording goes to the media model as written (config_loader
.wants_passthrough). Until 2026-10-02 the node
asked its language model anyway, with the task instruction and no perspective,
and what reached the image model was that model's rewrite. The basic forms the
Canvas offers under "New" (schemas/canvas_presets) start with such a node.

The age check is not this step's: it runs where the text meets the media
model (test_canvas_generation_stage3.py). A node that names a perspective but
carries none of its words is not the empty zone -- its text did not arrive --
and stops instead of passing the prompt on under the perspective's name.

The engine is stubbed; what is under test is who is asked, and what goes on.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.services.canvas_executor import CanvasWorkflowExecutor


class _Recorder:
    def __init__(self):
        self.entities = []

    def save_entity(self, **kw):
        self.entities.append(kw)


class _Response:
    success = True
    error = None
    model_used = "stub-model"

    def __init__(self, text):
        self.output_str = text


class _Engine:
    def __init__(self):
        self.requests = []

    async def process_request(self, req):
        self.requests.append(req)
        return _Response(f"REWRITTEN[{req.input_prompt}]")


def _run(safety_level="adult", **interception):
    nodes = [
        {"id": "in", "type": "input", "promptText": "a red circle"},
        {"id": "ic", "type": "interception", "llmModel": "local/stub", **interception},
        {"id": "out", "type": "display"},
    ]
    connections = [{"sourceId": "in", "targetId": "ic"}, {"sourceId": "ic", "targetId": "out"}]
    engine, recorder = _Engine(), _Recorder()
    ex = CanvasWorkflowExecutor(nodes, connections, recorder, "run_test", engine,
                                safety_level=safety_level)
    list(ex.execute_with_events())
    return ex, engine, recorder


@pytest.mark.parametrize("level", ["kids", "youth", "adult", "research"])
def test_no_perspective_is_passthrough_at_every_level(level):
    ex, engine, recorder = _run(safety_level=level)
    assert engine.requests == []
    res = ex.results["ic"]
    assert res["output"] == "a red circle"
    assert res["passthrough"] is True and res["error"] is None
    assert ex.execution_trace == ["in", "ic", "out"]
    assert ex.get_result()["success"] is True


def test_the_passthrough_is_recorded():
    _, _, recorder = _run()
    step = [e for e in recorder.entities if e["node_id"] == "ic"]
    assert step and step[0]["content"] == "a red circle"
    assert step[0]["metadata"]["passthrough"] is True


def test_blank_context_is_passthrough():
    ex, engine, _ = _run(contextPrompt="  \n ", interceptionPreset="user_defined")
    assert engine.requests == []
    assert ex.results["ic"]["output"] == "a red circle"


def test_a_perspective_without_its_words_stops():
    ex, engine, _ = _run(interceptionPreset="bauhaus", contextPrompt="")
    assert engine.requests == []
    assert ex.results["ic"]["output"] == ""
    assert "bauhaus" in ex.results["ic"]["error"]
    assert "out" not in ex.execution_trace


def test_a_written_perspective_runs():
    ex, engine, _ = _run(contextPrompt="Sieh es als Ort.")
    assert len(engine.requests) == 1
    assert engine.requests[0].style_prompt == "Sieh es als Ort."
    assert ex.results["ic"]["output"] == "REWRITTEN[a red circle]"
    assert "passthrough" not in ex.results["ic"]


def test_a_configured_lens_runs():
    ex, engine, _ = _run(configId="bauhaus")
    assert len(engine.requests) == 1
    assert engine.requests[0].style_prompt.strip()
    assert ex.results["ic"]["config_id"] == "bauhaus"


def test_a_perspective_keeps_its_safety_prefix():
    ex, engine, _ = _run(safety_level="kids", contextPrompt="Sieh es als Ort.")
    assert "SAFETY (ages 8-13)" in engine.requests[0].task_instruction
