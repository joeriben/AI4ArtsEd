"""/pipeline/stage2 runs over the intake and the check at the result.

The intake takes both texts the visitor sent, under the names they came under,
before any model reads them, and a refusal there ends the request. Every text a
model wrote in Stage 2 is checked at the result before the answer leaves: the
interception, the adaption, and the terms the model looked up. The visitor's
own text is not checked there again; it passed the intake. A refusal at the
result withholds the answer as a block at stage 2.

The pre-check (skip_optimization) takes both texts in at the intake and hands
the visitor's text back as it came in. No model writes there, so nothing is
checked at the result. Until 2026-11-01 it ran Stage 1 and a classifier gate.

The gate's own functions stand in here; what they decide is tested in
test_safety_gate.py. No model is called.
"""
import json
import types

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services.safety_gate import (
    CHECKPOINT_INTAKE,
    CHECKPOINT_RESULT,
    REASON_CONTENT,
    REASON_PERSONAL_DATA,
    Verdict,
)
from schemas.engine.instruction_selector import SAFETY_REFUSAL_SENTENCE

SCHEMA = "bauhaus"
TEXT = "Ein Haus steht in einer Landschaft."
CONTEXT = "Erzähle es als Gedicht."
ROUTE = "/api/schema/pipeline/stage2"


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp)
    return app.test_client()


class Checks:
    """The intake and the check at the result, standing in: they record what
    they were asked and refuse the field they are told to."""

    def __init__(self):
        self.intake = []
        self.result = []
        self.refuse_intake = None
        self.refuse_result = None

    def check_intake_texts(self, fields, *, level):
        self.intake.append((dict(fields), level))
        if self.refuse_intake in fields:
            return Verdict(False, CHECKPOINT_INTAKE, level, self.refuse_intake,
                           REASON_PERSONAL_DATA, "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def check_result_text(self, text, *, level, field="text"):
        self.result.append((field, text, level))
        if field == self.refuse_result:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT,
                           "not for this level")
        return Verdict(True, CHECKPOINT_RESULT, level, field)


@pytest.fixture
def checks(monkeypatch):
    stand_in = Checks()
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    monkeypatch.setattr(R, "check_intake_texts", stand_in.check_intake_texts)
    monkeypatch.setattr(R, "check_result_text", stand_in.check_result_text)
    return stand_in


def _stage2_writes(monkeypatch, **fields):
    """Stage 2 replaced by an answer with these fields; returns the calls."""
    ran = []

    async def fake(**kwargs):
        ran.append(kwargs)
        answer = dict(success=True, error=None, steps=[], execution_time=0, metadata={})
        answer.update(fields)
        return types.SimpleNamespace(**answer)

    monkeypatch.setattr(R, "execute_stage2_with_optimization", fake)
    return ran


# ── the intake ──────────────────────────────────────────────────────────────

def test_the_intake_takes_both_texts_by_their_names(client, checks, monkeypatch):
    _stage2_writes(monkeypatch, final_output="ein Haus aus Glas")
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT,
                                        "context_prompt": CONTEXT})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == [({"input_text": TEXT, "context_prompt": CONTEXT}, "kids")]


def test_a_refused_text_ends_the_request_before_stage_2(client, checks, monkeypatch):
    ran = _stage2_writes(monkeypatch, final_output="ein Haus aus Glas")
    checks.refuse_intake = "input_text"
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT})
    assert response.status_code == 403
    body = response.get_json()
    assert body["safety_block"] == {"checkpoint": "intake", "field": "input_text",
                                    "reason_key": "personal_data", "reason": "a name"}
    # The old fields went once no reader was left.
    assert "blocked_at_stage" not in body and "blocked_on" not in body
    assert ran == []
    assert checks.result == []


def test_a_refused_context_names_the_context(client, checks, monkeypatch):
    """A series drops the one row whose perspective was refused, by this field."""
    _stage2_writes(monkeypatch, final_output="ein Haus aus Glas")
    checks.refuse_intake = "context_prompt"
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT,
                                        "context_prompt": CONTEXT})
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["field"] == "context_prompt"


# ── the result ──────────────────────────────────────────────────────────────

def test_every_text_a_model_wrote_is_checked(client, checks, monkeypatch):
    _stage2_writes(monkeypatch,
                   interception_result="ein Haus aus Glas",
                   optimized_prompt="a glass house, photographed at dusk",
                   final_output="a glass house, photographed at dusk",
                   metadata={"wikipedia_terms": [
                       {"term": "Glasarchitektur", "lang": "de", "found": True},
                       {"term": "Bauhaus", "lang": "de", "found": False}]})
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT,
                                        "output_config": "sd35_large"})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.result == [
        ("interception", "ein Haus aus Glas", "kids"),
        ("optimized_prompt", "a glass house, photographed at dusk", "kids"),
        ("wikipedia_terms", "Glasarchitektur\nBauhaus", "kids"),
    ]


def test_the_visitors_own_text_is_not_checked_again(client, checks, monkeypatch):
    """A perspective that owes the visitor their wording hands it on."""
    _stage2_writes(monkeypatch, interception_result=TEXT, optimized_prompt=TEXT,
                   final_output=TEXT, metadata={"passthrough": True})
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.result == []


def test_a_refused_text_withholds_the_answer(client, checks, monkeypatch):
    _stage2_writes(monkeypatch, interception_result="ein Haus aus Glas",
                   optimized_prompt="ein Haus aus Glas", final_output="ein Haus aus Glas")
    checks.refuse_result = "interception"
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT})
    assert response.status_code == 403
    body = response.get_json()
    assert body["status"] == "blocked"
    assert body["safety_block"] == {"checkpoint": "result", "field": "interception",
                                    "reason_key": "content", "reason": "not for this level"}
    assert "ein Haus aus Glas" not in response.get_data(as_text=True)


def test_refused_lookups_withhold_the_answer_too(client, checks, monkeypatch):
    _stage2_writes(monkeypatch, final_output="ein Haus aus Glas",
                   metadata={"wikipedia_terms": [{"term": "Glasarchitektur", "lang": "de",
                                                  "found": True}]})
    checks.refuse_result = "wikipedia_terms"
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT})
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["field"] == "wikipedia_terms"
    assert "Glasarchitektur" not in response.get_data(as_text=True)


def test_the_models_refusal_is_reported_as_its_refusal(client, checks, monkeypatch):
    refusal = SAFETY_REFUSAL_SENTENCE + " Bitte formuliere es anders."
    _stage2_writes(monkeypatch, final_output=refusal)
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT})
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["checkpoint"] == "refusal"
    assert checks.result == []


def test_a_structured_answer_is_read_as_the_json_it_leaves_as():
    answer = types.SimpleNamespace(final_output={"title": "Haus"}, metadata={})
    assert R._stage2_written_texts(answer, TEXT) == [
        ("stage2_result", json.dumps({"title": "Haus"}, ensure_ascii=False))]


# ── the pre-check ───────────────────────────────────────────────────────────

def test_the_pre_check_takes_the_texts_in_and_hands_the_text_back(client, checks, monkeypatch):
    ran = _stage2_writes(monkeypatch, final_output="x")
    response = client.post(ROUTE, json={"schema": SCHEMA, "input_text": TEXT,
                                        "skip_optimization": True})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == [({"input_text": TEXT, "context_prompt": None}, "kids")]
    assert ran == []
    assert checks.result == []
    assert response.get_json()["stage2_result"] == TEXT


# ── a saved perspective ─────────────────────────────────────────────────────

KEPT = "Sieh es von der Seite."
KEPT_TASK = "Schreibe kurz."


def _a_saved_perspective(monkeypatch):
    """The schema names a perspective somebody kept (custom:7), over this
    preset's structure, as course_prompt_resolver builds one."""
    import dataclasses
    R.init_schema_engine()
    kept = dataclasses.replace(R.pipeline_executor.config_loader.get_config(SCHEMA),
                               name="custom:7", context=KEPT)
    kept.task_instruction = KEPT_TASK
    monkeypatch.setattr(R, "_resolve_interception_config", lambda name: kept)


def test_the_text_of_a_saved_perspective_goes_through_the_intake(client, checks, monkeypatch):
    _a_saved_perspective(monkeypatch)
    _stage2_writes(monkeypatch, final_output="ein Haus aus Glas")
    response = client.post(ROUTE, json={"schema": "custom:7", "input_text": TEXT})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == [({"input_text": TEXT, "context_prompt": None, "context_text": KEPT,
                               "task_instruction": KEPT_TASK}, "kids")]


def test_an_edited_context_takes_the_place_of_the_saved_one(client, checks, monkeypatch):
    _a_saved_perspective(monkeypatch)
    _stage2_writes(monkeypatch, final_output="ein Haus aus Glas")
    client.post(ROUTE, json={"schema": "custom:7", "input_text": TEXT, "context_prompt": CONTEXT})
    assert checks.intake == [({"input_text": TEXT, "context_prompt": CONTEXT,
                               "task_instruction": KEPT_TASK}, "kids")]


def test_a_refused_saved_perspective_reaches_no_model(client, checks, monkeypatch):
    """A series drops the one row whose saved perspective was refused, by this
    field."""
    _a_saved_perspective(monkeypatch)
    ran = _stage2_writes(monkeypatch, final_output="ein Haus aus Glas")
    checks.refuse_intake = "context_text"
    response = client.post(ROUTE, json={"schema": "custom:7", "input_text": TEXT})
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["field"] == "context_text"
    assert ran == []
