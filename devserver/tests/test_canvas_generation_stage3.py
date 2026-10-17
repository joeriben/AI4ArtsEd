#!/usr/bin/env python3
"""Every Canvas generation asks the flow's Stage 3, at every level.

The flow checks each text before a media model receives it
(execute_generation_stage4: Stage 3, then Stage 4). The Canvas calls Stage 4
alone, and until 2026-10-02 no text on it was checked on that way, whichever
node wrote it: an input wired straight to a video model went through unread.
Now the generation node asks the same Stage 3, at every level as the flow does
(Stage 3 itself lets adult and research pass), and only for its verdict -- what
the model receives is what the board wired to it, so every text is checked as
given.

A refusal stops the node, says so in the run's errors (`blocked`), and the
board shows it in the platform's safety window; the picture check after
generation reports the same way.

Stage 3 and Stage 4 are stubbed; what is under test is who is asked with
what, and what goes on.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.schema_pipeline_routes as spr
import schemas.engine.stage_orchestrator as so
from my_app.services.canvas_executor import CanvasWorkflowExecutor
from my_app.services.safety_level_resolver import SAFETY_LEVELS_STRICTEST_FIRST

REAL_STAGE3 = so.execute_stage3_safety


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
    """Stage 3 refuses any text with 'forbidden' in it; Stage 4 records its prompt."""
    seen = {"stage3": [], "stage4": [], "stage4_result": None}

    async def stage3(prompt, safety_level, media_type, pipeline_executor, **kw):
        seen["stage3"].append((prompt, safety_level, kw.get("as_given", False), kw.get("user_language")))
        seen.setdefault("devices", []).append(kw.get("device_id"))
        if safety_level in ("adult", "research"):
            return {"safe": True, "method": "disabled", "positive_prompt": prompt}
        if "forbidden" in prompt:
            return {"safe": False, "method": "llm_safety_check",
                    "abort_reason": "Content blocked by safety filter", "found_terms": []}
        return {"safe": True, "method": "llm_safety_check", "positive_prompt": f"EN[{prompt}]"}

    async def stage4(**kw):
        seen["stage4"].append(kw)
        return seen["stage4_result"] or {
            "success": True, "media_output": {"url": "/api/media/image/x/0", "seed": 7},
            "model_meta": None,
        }

    monkeypatch.setattr(so, "execute_stage3_safety", stage3)
    monkeypatch.setattr(spr, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(spr, "pipeline_executor", object())
    return seen


def _run(level, prompt="a red circle", second=None, lang="fr"):
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
                                safety_level=level, lang=lang, device_id="dev_1")
    list(ex.execute_with_events())
    return ex


@pytest.mark.parametrize("level", SAFETY_LEVELS_STRICTEST_FIRST)
def test_every_level_asks_and_gets_what_the_board_wired(stages, level):
    """The level is Stage 3's to judge, as in the flow -- `open` included."""
    ex = _run(level)
    assert stages["stage3"] == [("a red circle", level, True, "fr")]
    assert stages["stage4"][0]["prompt"] == "a red circle"
    assert ex.get_result()["success"] is True


@pytest.mark.parametrize("level", ["open", "youth", "kids"])
def test_a_refusal_at_any_checked_level_reaches_no_model(stages, level):
    _run(level, prompt="something forbidden")
    assert stages["stage4"] == []


@pytest.mark.parametrize("level", ["adult", "research"])
def test_adult_and_research_pass_the_real_stage3_unchecked(stages, monkeypatch, level):
    """The real function, not the stub: these levels leave it before it reads anything."""
    monkeypatch.setattr(so, "execute_stage3_safety", REAL_STAGE3)
    ex = _run(level, prompt="something forbidden")
    assert stages["stage4"][0]["prompt"] == "something forbidden"
    assert ex.get_result()["success"] is True


def test_a_refused_text_reaches_no_model(stages):
    ex = _run("kids", prompt="something forbidden")
    assert stages["stage4"] == []
    res = ex.results["gen"]
    assert res["error"] == "Content blocked by safety filter"
    assert res["blocked"]["stage"] == 3 and res["blocked"]["operational"] is False
    errors = ex.get_result()["errors"]
    assert errors[0]["node_id"] == "gen" and errors[0]["blocked"]["stage"] == 3
    assert ex.collector_items == []


def test_the_second_text_is_checked_as_given(stages):
    ex = _run("youth", second="something forbidden")
    assert [(s[0], s[2]) for s in stages["stage3"]] == [("a red circle", True), ("something forbidden", True)]
    # The prompt's translation is the device's to reuse; the second text's is not.
    assert stages["devices"] == ["dev_1", None]
    assert stages["stage4"] == []
    assert ex.results["gen"]["blocked"]["stage"] == 3


def test_a_check_that_cannot_run_stops_only_its_node(stages, monkeypatch):
    async def broken(prompt, safety_level, media_type, pipeline_executor, **kw):
        raise RuntimeError("the translator is gone")

    monkeypatch.setattr(so, "execute_stage3_safety", broken)
    ex = _run("kids")
    assert stages["stage4"] == []
    blocked = ex.results["gen"]["blocked"]
    assert blocked["operational"] is True and "could not run" in blocked["reason"]
    assert ex.get_result()["errors"][0]["blocked"]["operational"] is True


def test_a_check_without_a_verdict_is_said_to_be_one(stages, monkeypatch):
    async def no_verdict(prompt, safety_level, media_type, pipeline_executor, **kw):
        return {"safe": False, "method": "llm_check_failed", "abort_reason": "unavailable"}

    monkeypatch.setattr(so, "execute_stage3_safety", no_verdict)
    ex = _run("kids")
    assert ex.results["gen"]["blocked"]["operational"] is True


def test_the_picture_check_after_generation_is_reported(stages):
    stages["stage4_result"] = {
        "success": False, "error": "safety_blocked: weapon", "blocked": True,
        "stage": "vlm_safety", "vlm_reason": "weapon", "vlm_description": "a knife",
    }
    ex = _run("kids")
    blocked = ex.results["gen"]["blocked"]
    assert blocked["stage"] == "vlm_safety" and blocked["vlm_description"] == "a knife"
    assert ex.get_result()["errors"][0]["blocked"]["stage"] == "vlm_safety"
