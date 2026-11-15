#!/usr/bin/env python3
"""What the Fusion Workbench checks before a cell is made, and before the cell
and the T5 expansion leave the server.

A cell (/api/fusion_workbench/generate) passes the intake with every text its
request carries and the check before the model with what its graph hands the
model, at the level its view resolved; only then does the graph run. The
picture passes the check of the result as it leaves, marked. A refusal
answers 403 with the block message, and nothing after it runs. The T5
expander's prompt passes the intake, and what the expander wrote the check of
the result. The four research instruments answer at the research level only,
and hand their run that level.

The gate functions, the graph's run at ComfyUI, the watermark and the expander
are stubbed; nothing here asks a model.
"""
import json
import sys
import threading
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.routes import fusion_workbench_routes as fwr
from my_app.services import latent_lab_context_graphs as graphs
from my_app.services import t5_expansion
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         CHECKPOINT_RESULT, REASON_CONTENT,
                                         REASON_IMAGE_CONTENT, REASON_PERSONAL_DATA, Verdict)

GENERATE = '/api/fusion_workbench/generate'
EXPAND = '/api/fusion_workbench/expand_t5'

AT_THE_INTAKE = "refuse-at-the-intake"
BEFORE_THE_MODEL = "refuse-before-the-model"
AT_THE_RESULT = "refuse-at-the-result"

CELL = {"prompt": "a house", "t5_prompt": "a house by the sea", "negative_prompt": "fog",
        "seed": 4}


class Reached(list):
    """What was reached, in order. `made` is the picture the graph's run
    answers, `wrote` what the expander writes."""
    made = "QUJD"
    wrote = "a house of pale stone by a grey sea"


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(fwr.fusion_workbench_bp)
    return app


@pytest.fixture
def ran(monkeypatch):
    """The checks, the graph's run, the watermark and the expander recorded
    where they are reached, in that order. A text with AT_THE_INTAKE or
    BEFORE_THE_MODEL in it is refused there, a picture or an expansion with
    AT_THE_RESULT in it at the result. The view resolves "youth"."""
    reached = Reached()
    monkeypatch.setattr(fwr, "resolve_safety_level", lambda: "youth")

    async def checkpoint_of(model_id, tag):
        return "OfficialStableDiffusion/sd3.5_large.safetensors", "stand-in/model"

    async def run_graph(graph, workload, tag):
        reached.append(("graph", workload))
        return reached.made

    def watermark(payload, meta, extra_keys=()):
        payload["image_base64"] = f"marked {payload['image_base64']}"

    def expand(prompt):
        reached.append(("expander", prompt))
        return reached.wrote

    def intake_texts(fields, *, level):
        reached.append(("intake", dict(fields), level))
        for name, text in fields.items():
            if AT_THE_INTAKE in str(text or ""):
                return Verdict(False, CHECKPOINT_INTAKE, level, name, REASON_PERSONAL_DATA,
                               "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def before_model(texts, *, level, originals=(), images=(), translation_instruction=None):
        reached.append(("before_model", dict(texts), level))
        for name, text in texts.items():
            if BEFORE_THE_MODEL in str(text or ""):
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_CONTENT,
                               "content")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    def result_image(picture, *, level, recorder=None, entity=None, field="image"):
        reached.append(("result_image", picture, level, field))
        if AT_THE_RESULT in picture:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_IMAGE_CONTENT,
                           "a picture")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    def result_text(text, *, level, field="text"):
        reached.append(("result_text", text, level, field))
        if AT_THE_RESULT in text:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT, "a text")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(graphs, "checkpoint_of", checkpoint_of)
    monkeypatch.setattr(graphs, "run_graph", run_graph)
    monkeypatch.setattr("my_app.services.watermark_service.watermark_result_metadata", watermark)
    monkeypatch.setattr(t5_expansion, "expand_t5", expand)
    monkeypatch.setattr(fwr, "check_intake_texts", intake_texts)
    monkeypatch.setattr(fwr, "check_before_model", before_model)
    monkeypatch.setattr(fwr, "check_result_image", result_image)
    monkeypatch.setattr(fwr, "check_result_text", result_text)
    return reached


def terminal_frame(wire: str) -> dict:
    """The streamed answer's terminal frame: the plain answer and its status."""
    for raw in wire.split("\n\n"):
        if raw.startswith("event: complete"):
            return json.loads(raw.split("data: ", 1)[1])
    raise AssertionError(f"no terminal frame on this wire: {wire[:300]!r}")


def _written(fields):
    """The texts of an intake call that carry anything."""
    return {name: text for name, text in fields.items() if text is not None}


# ── A cell ──────────────────────────────────────────────────────────────────

def test_a_cell_is_checked_before_its_graph_runs_and_as_it_leaves(app, ran):
    response = app.test_client().post(GENERATE, json=CELL)
    assert response.status_code == 200
    assert response.get_json()["image_base64"] == "marked QUJD"
    assert [r[0] for r in ran] == ["intake", "before_model", "graph", "result_image"]
    texts = {"prompt": "a house", "t5_prompt": "a house by the sea", "negative_prompt": "fog"}
    assert _written(ran[0][1]) == texts and ran[0][2] == "youth"
    assert ran[1] == ("before_model", texts, "youth")
    assert ran[3] == ("result_image", "marked QUJD", "youth", "image_base64")


def test_a_cell_without_its_own_t5_text_is_checked_as_its_prompt(app, ran):
    """The T5 encoder then receives the prompt, which the check reads once."""
    response = app.test_client().post(GENERATE, json={"prompt": "a house", "seed": 4})
    assert response.status_code == 200
    before = next(r for r in ran if r[0] == "before_model")
    assert before[1] == {"prompt": "a house", "t5_prompt": None, "negative_prompt": None}


def test_a_text_refused_at_the_intake_runs_nothing(app, ran):
    response = app.test_client().post(GENERATE, json={**CELL, "prompt": f"a {AT_THE_INTAKE}"})
    assert response.status_code == 403
    answer = response.get_json()
    assert answer["success"] is False and "image_base64" not in answer
    assert answer["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert answer["safety_block"]["field"] == "prompt"
    assert [r[0] for r in ran] == ["intake"]


def test_a_text_refused_before_the_model_runs_nothing(app, ran):
    response = app.test_client().post(
        GENERATE, json={**CELL, "t5_prompt": f"a {BEFORE_THE_MODEL}"})
    assert response.status_code == 403
    answer = response.get_json()
    assert answer["safety_block"]["checkpoint"] == CHECKPOINT_BEFORE_MODEL
    assert answer["safety_block"]["field"] == "t5_prompt"
    assert [r[0] for r in ran] == ["intake", "before_model"]


def test_a_picture_refused_at_the_result_does_not_leave(app, ran):
    ran.made = f"QUJD {AT_THE_RESULT}"
    response = app.test_client().post(GENERATE, json=CELL)
    assert response.status_code == 403
    answer = response.get_json()
    assert "image_base64" not in answer
    assert answer["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert answer["safety_block"]["field"] == "image_base64"
    assert [r[0] for r in ran] == ["intake", "before_model", "graph", "result_image"]


@pytest.mark.parametrize("texts,made", [
    pytest.param({"prompt": f"a {AT_THE_INTAKE}"}, "QUJD", id="at the intake"),
    pytest.param({"negative_prompt": f"a {BEFORE_THE_MODEL}"}, "QUJD", id="before the model"),
    pytest.param({}, f"QUJD {AT_THE_RESULT}", id="at the result"),
])
def test_a_refusal_is_the_same_either_way(app, ran, texts, made):
    """A streamed answer carries the plain one in its terminal frame; a refusal
    is no exception."""
    ran.made = made
    body = {**CELL, **texts}
    client = app.test_client()
    plain = client.post(GENERATE, json=body)
    streamed = client.post(GENERATE, json={**body, "enable_streaming": True})
    frame = terminal_frame(streamed.get_data(as_text=True))
    assert (frame["body"], frame["http_status"]) == (plain.get_json(), 403)


def test_the_level_is_resolved_in_the_view_and_travels_with_the_cell(app, ran, monkeypatch):
    """A streamed answer runs the cell on a thread of its own, where the
    resolver answers the strictest level whatever the course is. The view
    resolves it on the request thread and hands it on."""
    resolved_on = []

    def level():
        resolved_on.append(threading.get_ident())
        return "adult"

    monkeypatch.setattr(fwr, "resolve_safety_level", level)
    response = app.test_client().post(GENERATE, json={**CELL, "enable_streaming": True})
    assert terminal_frame(response.get_data(as_text=True))["http_status"] == 200
    assert resolved_on == [threading.get_ident()]
    assert [r[2] for r in ran if r[0] != "graph"] == ["adult"] * 3


# ── The research instruments ────────────────────────────────────────────────

def test_the_decomposition_hands_its_run_the_research_level_and_names_its_texts(
        app, ran, monkeypatch):
    monkeypatch.setattr(fwr, "resolve_safety_level", lambda: "research")
    body = {"source_prompt": "a house", "clip_l_prompt": "a lantern",
            "cells": [{"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a moth"}]}
    response = app.test_client().post('/api/fusion_workbench/decomposition', json=body)
    assert response.status_code == 200
    texts = {"source_prompt": "a house", "clip_l_prompt": "a lantern",
             "cells[0].prompt": "a moth"}
    assert _written(ran[0][1]) == texts and ran[0][2] == "research"
    assert _written(ran[1][1]) == texts and ran[1][2] == "research"


@pytest.mark.parametrize("kind", ["decomposition", "position_probe", "delayed_kickin",
                                  "delayed_kickin_cumulative"])
def test_a_research_instrument_refuses_every_other_level_before_it_reads_the_body(
        app, ran, kind):
    response = app.test_client().post(f'/api/fusion_workbench/{kind}', json=[1])
    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error": f"{kind} runs at the research level only; this installation runs at 'youth'"}
    assert ran == []


# ── The T5 expansion ────────────────────────────────────────────────────────

def test_the_expansion_is_checked_at_the_intake_and_at_the_result(app, ran):
    response = app.test_client().post(EXPAND, json={"prompt": " a house "})
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "t5_expansion": Reached.wrote}
    assert ran == [("intake", {"prompt": "a house"}, "youth"), ("expander", "a house"),
                   ("result_text", Reached.wrote, "youth", "t5_expansion")]


def test_a_prompt_refused_at_the_intake_never_reaches_the_expander(app, ran):
    response = app.test_client().post(EXPAND, json={"prompt": f"a {AT_THE_INTAKE}"})
    assert response.status_code == 403
    answer = response.get_json()
    assert answer["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert [r[0] for r in ran] == ["intake"]


def test_a_refused_expansion_is_not_shown(app, ran):
    ran.wrote = f"a house {AT_THE_RESULT}"
    response = app.test_client().post(EXPAND, json={"prompt": "a house"})
    assert response.status_code == 403
    answer = response.get_json()
    assert "t5_expansion" not in answer
    assert answer["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert answer["safety_block"]["field"] == "t5_expansion"
