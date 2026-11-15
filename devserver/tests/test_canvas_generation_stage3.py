#!/usr/bin/env python3
"""Every Canvas generation asks the check before the model, at every level.

The flow checks each text before a media model receives it. The Canvas calls
Stage 4 alone, and until 2026-10-02 no text on it was checked on that way,
whichever node wrote it: an input wired straight to a video model went through
unread. From then until 2026-10-31 the generation node asked the flow's
Stage 3, which let adult pass unasked. Now it asks check_before_model at every
level, on every text the model receives: the prompt, the second text, and what
the workflow's language-model steps wrote, which run first. The model receives
each text as the board wired it, so the check is handed no originals and
translates for itself.

A refusal stops the node, says so in the run's errors with the block
message `safety_block`, and the board shows it in the platform's safety
window; the picture check after generation reports the same way.

The check, the steps and Stage 4 are stubbed; what is under test is who is
asked with what, and what goes on.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.schema_pipeline_routes as spr
from my_app.services import canvas_executor, safety_gate
from my_app.services.canvas_executor import CanvasWorkflowExecutor
from my_app.services.chunk_llm_steps import LlmStepError
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, REASON_SYMBOL,
                                         REASON_UNAVAILABLE, Verdict)
from my_app.services.safety_level_resolver import SAFETY_LEVELS_STRICTEST_FIRST

REAL_CHECK = safety_gate.check_before_model


class _Recorder:
    def save_entity(self, **kw):
        pass

    def save_image_from_url(self, **kw):
        pass


class _Engine:
    async def process_request(self, req):  # no model is asked in these graphs
        raise AssertionError("no language model belongs in this test")


@pytest.fixture
def stages(monkeypatch):
    """The check refuses a text with 'forbidden' in it and has no verdict on one
    with 'unreadable'; the steps answer what `seen["steps"]` holds, or raise
    it; Stage 4 records what it was given. `order` keeps who was reached when."""
    seen = {"checks": [], "steps_run": [], "steps": {}, "stage4": [], "stage4_result": None,
            "order": []}

    def check(texts, *, level, originals=(), images=(), translation_instruction=None):
        seen["order"].append("check")
        seen["checks"].append({"texts": dict(texts), "level": level,
                               "originals": originals, "images": images})
        for name, text in texts.items():
            if "forbidden" in str(text or ""):
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_SYMBOL,
                               "Content blocked")
            if "unreadable" in str(text or ""):
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_UNAVAILABLE,
                               "no verdict")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    def steps(chunk, prompt):
        seen["order"].append("steps")
        seen["steps_run"].append((chunk, prompt))
        if isinstance(seen["steps"], Exception):
            raise seen["steps"]
        return dict(seen["steps"])

    async def stage4(**kw):
        seen["order"].append("stage4")
        seen["stage4"].append(kw)
        return seen["stage4_result"] or {
            "success": True, "media_output": {"url": "/api/media/image/x/0", "seed": 7},
            "model_meta": None,
        }

    monkeypatch.setattr(canvas_executor, "check_before_model", check)
    monkeypatch.setattr(canvas_executor, "run_llm_steps", steps)
    monkeypatch.setattr(canvas_executor, "_output_chunk",
                        lambda config_id: f"chunk_of_{config_id}")
    monkeypatch.setattr(spr, "execute_stage4_generation_only", stage4)
    return seen


def _run(level, prompt="a red circle", second=None):
    nodes = [
        {"id": "in", "type": "input", "promptText": prompt},
        {"id": "gen", "type": "generation", "configId": "sd35_large"},
        {"id": "col", "type": "collector"},
    ]
    conns = [{"sourceId": "in", "targetId": "gen", "label": "input-1"},
             {"sourceId": "gen", "targetId": "col"}]
    if second is not None:
        nodes.append({"id": "in2", "type": "input", "promptText": second})
        conns.append({"sourceId": "in2", "targetId": "gen", "label": "input-2"})
    ex = CanvasWorkflowExecutor(nodes, conns, _Recorder(), "run_test", _Engine(),
                                safety_level=level, lang="fr", device_id="dev_1")
    list(ex.execute_with_events())
    return ex


def _read(texts):
    """The texts a check read, without the fields the board left empty."""
    return {name: text for name, text in texts.items() if text}


@pytest.mark.parametrize("level", SAFETY_LEVELS_STRICTEST_FIRST)
def test_every_level_asks_and_gets_what_the_board_wired(stages, level):
    """adult has its own question now; at research the check itself lets
    everything pass."""
    ex = _run(level)
    [check] = stages["checks"]
    assert check["level"] == level
    assert _read(check["texts"]) == {"prompt": "a red circle"}
    assert stages["stage4"][0]["prompt"] == "a red circle"
    assert ex.get_result()["success"] is True


def test_the_check_translates_for_itself(stages):
    """The model receives the text as the board wired it, so no translation
    stands in for it as an original."""
    _run("kids")
    [check] = stages["checks"]
    assert check["originals"] == () and check["images"] == ()


@pytest.mark.parametrize("level", ["kids", "youth", "adult"])
def test_a_refused_text_reaches_no_model(stages, level):
    ex = _run(level, prompt="something forbidden")
    assert stages["stage4"] == []
    res = ex.results["gen"]
    assert res["error"] == "Content blocked"
    assert res["safety_block"] == {"checkpoint": "before_model", "field": "prompt",
                                   "reason_key": "symbol", "reason": "Content blocked"}
    errors = ex.get_result()["errors"]
    assert errors[0]["node_id"] == "gen"
    assert errors[0]["safety_block"] == res["safety_block"]
    assert ex.collector_items == []


def test_the_second_text_is_checked(stages):
    ex = _run("youth", second="something forbidden")
    [check] = stages["checks"]
    assert _read(check["texts"]) == {"prompt": "a red circle",
                                     "secondary_text": "something forbidden"}
    assert stages["stage4"] == []
    assert ex.results["gen"]["safety_block"]["field"] == "secondary_text"


def test_a_text_in_two_fields_is_read_once(stages):
    _run("kids", second=" a red circle ")
    [check] = stages["checks"]
    assert _read(check["texts"]) == {"prompt": "a red circle"}
    assert stages["stage4"][0]["secondary_text"] == " a red circle "


def test_a_check_without_a_verdict_is_said_to_be_one(stages):
    ex = _run("kids", prompt="unreadable")
    assert stages["stage4"] == []
    assert ex.results["gen"]["safety_block"]["reason_key"] == "unavailable"
    assert ex.get_result()["errors"][0]["safety_block"]["reason_key"] == "unavailable"


# ── The workflow's language-model steps ─────────────────────────────────────

def test_the_steps_run_before_the_check_and_it_reads_what_they_wrote(stages):
    stages["steps"] = {"t5_prompt": "A circle, red.", "clip_prompt": "red, circle",
                       "proposed_alpha": 0.5}
    ex = _run("adult")
    assert stages["order"] == ["steps", "check", "stage4"]
    assert stages["steps_run"] == [("chunk_of_sd35_large", "a red circle")]
    [check] = stages["checks"]
    assert _read(check["texts"]) == {"prompt": "a red circle", "t5_prompt": "A circle, red.",
                                     "clip_prompt": "red, circle"}
    assert stages["stage4"][0]["step_results"] == stages["steps"]
    assert ex.get_result()["success"] is True


def test_a_text_a_step_wrote_and_the_check_refuses_reaches_no_model(stages):
    stages["steps"] = {"t5_prompt": "something forbidden", "clip_prompt": "red, circle"}
    ex = _run("kids")
    assert stages["stage4"] == []
    assert ex.results["gen"]["safety_block"]["field"] == "t5_prompt"


def test_a_step_that_fails_ends_the_node(stages):
    stages["steps"] = LlmStepError("the step that writes t5_prompt failed: gone")
    ex = _run("kids")
    assert stages["checks"] == [] and stages["stage4"] == []
    assert "language-model step" in ex.results["gen"]["error"]
    assert "safety_block" not in ex.results["gen"]


def test_research_passes_the_real_check(stages, monkeypatch):
    """The real function, not the stub: at research it passes before it reads
    anything."""
    monkeypatch.setattr(canvas_executor, "check_before_model", REAL_CHECK)
    ex = _run("research", prompt="something forbidden")
    assert stages["stage4"][0]["prompt"] == "something forbidden"
    assert ex.get_result()["success"] is True


def test_the_picture_check_after_generation_is_reported(stages):
    refused = {"checkpoint": "result", "field": "image", "reason_key": "image_content",
               "reason": "weapon"}
    stages["stage4_result"] = {
        "success": False, "error": "safety_blocked: weapon", "safety_block": refused,
        "vlm_reason": "weapon", "vlm_description": "a knife",
    }
    ex = _run("kids")
    assert ex.results["gen"]["safety_block"] == refused
    assert ex.results["gen"]["vlm_description"] == "a knife"
    assert ex.get_result()["errors"][0]["safety_block"] == refused
    assert ex.get_result()["errors"][0]["vlm_description"] == "a knife"
