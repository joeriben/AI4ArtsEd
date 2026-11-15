"""/pipeline/optimize runs over the intake and the check at the result.

The text to adapt passes the intake before any model reads it, and a refusal
there ends the request. What a model wrote here is checked at the result
before the answer leaves: the adaption, and where the text behind a caption had
to be shortened to the window, the shortened text. A sketch is checked as code.
The visitor's own text, handed back unchanged, is not checked there again; it
passed the intake. A refusal at the result withholds the answer as a whole.

The gate's own functions stand in here; what they decide is tested in
test_safety_gate.py. No model is called.
"""
import threading

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services.safety_gate import (
    CHECKPOINT_INTAKE,
    CHECKPOINT_RESULT,
    REASON_CODE,
    REASON_CONTENT,
    REASON_PERSONAL_DATA,
    Verdict,
)

ROUTE = "/api/schema/pipeline/optimize"
TEXT = "Ein Haus steht in einer Landschaft."
ADAPTED = "a house standing in a landscape, wide shot"
BODY = {"input_text": TEXT, "output_config": "sd35_large"}


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp)
    return app.test_client()


class Checks:
    """The intake and the two checks at the result, standing in: they record
    what they were asked and refuse the field they are told to."""

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
        self.result.append(("text", field, text, level))
        if field == self.refuse_result:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT,
                           "not for this level")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    def check_result_code(self, code, *, level, recorder=None, entity=None, field="code"):
        self.result.append(("code", field, code, level))
        if field == self.refuse_result:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CODE,
                           "not in this sandbox")
        return Verdict(True, CHECKPOINT_RESULT, level, field)


@pytest.fixture
def checks(monkeypatch):
    stand_in = Checks()
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "youth")
    monkeypatch.setattr(R, "check_intake_texts", stand_in.check_intake_texts)
    monkeypatch.setattr(R, "check_result_text", stand_in.check_result_text)
    monkeypatch.setattr(R, "check_result_code", stand_in.check_result_code)
    return stand_in


@pytest.fixture
def adaption(monkeypatch):
    """The adaption replaced: every config has an instruction, and the model
    writes what `adaption.writes` holds. `adaption.asked` records the texts it
    was asked to adapt."""
    async def fake(input_text, optimization_instruction, model_override=None):
        fake.asked.append(input_text)
        return fake.writes

    fake.writes = ADAPTED
    fake.asked = []
    monkeypatch.setattr(R, "_load_optimization_instruction", lambda cfg: "adapt it")
    monkeypatch.setattr(R, "_load_optimization_model", lambda cfg: None)
    monkeypatch.setattr(R, "_load_estimated_duration", lambda cfg: "30")
    monkeypatch.setattr(R, "execute_optimization", fake)
    return fake


def _results(checks):
    return [(kind, field, text) for kind, field, text, _level in checks.result]


# ── the intake ──────────────────────────────────────────────────────────────

def test_the_intake_takes_the_text_to_adapt(client, checks, adaption):
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == [({"input_text": TEXT}, "youth")]
    assert adaption.asked == [TEXT]


def test_a_refused_text_reaches_no_model(client, checks, adaption):
    checks.refuse_intake = "input_text"
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 403
    body = response.get_json()
    assert body["success"] is False
    assert body["safety_block"] == {"checkpoint": "intake", "field": "input_text",
                                    "reason_key": "personal_data", "reason": "a name"}
    assert adaption.asked == [] and checks.result == []


def test_a_text_without_an_adaption_is_handed_back_after_the_intake(client, checks,
                                                                     adaption, monkeypatch):
    monkeypatch.setattr(R, "_load_optimization_instruction", lambda cfg: None)
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["optimized_prompt"] == TEXT
    assert checks.intake == [({"input_text": TEXT}, "youth")]
    assert adaption.asked == [] and checks.result == []


# ── the result ──────────────────────────────────────────────────────────────

def test_what_the_adaption_wrote_is_checked_before_it_leaves(client, checks, adaption):
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["optimized_prompt"] == ADAPTED
    assert checks.result == [("text", "optimized_prompt", ADAPTED, "youth")]


def test_a_refused_adaption_is_withheld(client, checks, adaption):
    checks.refuse_result = "optimized_prompt"
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 403
    body = response.get_json()
    assert body["success"] is False
    assert body["safety_block"] == {"checkpoint": "result", "field": "optimized_prompt",
                                    "reason_key": "content", "reason": "not for this level"}
    assert ADAPTED not in response.get_data(as_text=True)


def test_an_adaption_that_hands_the_text_back_is_not_read_again(client, checks, adaption):
    adaption.writes = f"  {TEXT}\n"
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.result == []


def test_a_text_shortened_to_the_window_is_checked_as_well(client, checks, adaption,
                                                            monkeypatch):
    """The caption leaves inside the adaption; the text T5 reads behind it
    leaves on its own, and where a model shortened it, it is that model's
    text."""
    adaption.writes = '{"clip": "a house", "t5": "a house standing in a landscape"}'
    monkeypatch.setattr(R, "_fit_encoder_window",
                        lambda clip, text, cfg: ("a house, shortened", True, 77))
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["condensed_text"] == "a house, shortened"
    assert _results(checks) == [("text", "optimized_prompt", adaption.writes),
                                ("text", "interception_result", "a house, shortened")]

    checks.refuse_result = "interception_result"
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["field"] == "interception_result"
    assert "a house, shortened" not in response.get_data(as_text=True)


def test_the_visitors_own_text_behind_a_caption_is_not_read_again(client, checks,
                                                                   adaption, monkeypatch):
    adaption.writes = '{"clip": "a house", "t5": "a house standing in a landscape"}'
    monkeypatch.setattr(R, "_fit_encoder_window", lambda clip, text, cfg: (text, False, 40))
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["interception_result"] == TEXT
    assert _results(checks) == [("text", "optimized_prompt", adaption.writes)]


@pytest.mark.parametrize("config", ["p5js_code", "tonejs_code"])
def test_a_sketch_is_checked_as_code(client, checks, adaption, config):
    adaption.writes = "function setup() { createCanvas(800, 600) }"
    response = client.post(ROUTE, json={"input_text": TEXT, "output_config": config})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert _results(checks) == [("code", "optimized_prompt", adaption.writes)]

    checks.refuse_result = "optimized_prompt"
    response = client.post(ROUTE, json={"input_text": TEXT, "output_config": config})
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["reason_key"] == "code"
    assert "createCanvas" not in response.get_data(as_text=True)


# ── the level ───────────────────────────────────────────────────────────────

def test_the_streamed_answer_is_checked_at_the_level_of_the_session(client, checks,
                                                                     adaption, monkeypatch):
    """The run goes on on a worker of the stream transport, where the resolver
    answers the strictest level: the level is read on the request thread."""
    request_thread = threading.current_thread()
    monkeypatch.setattr(R, "resolve_safety_level",
                        lambda: "youth" if threading.current_thread() is request_thread
                        else "kids")
    response = client.post(ROUTE, json={**BODY, "enable_streaming": True})
    assert "event: complete" in response.get_data(as_text=True)
    assert checks.intake == [({"input_text": TEXT}, "youth")]
    assert checks.result == [("text", "optimized_prompt", ADAPTED, "youth")]


def test_a_level_that_cannot_be_resolved_runs_nothing(client, checks, adaption,
                                                       monkeypatch):
    def boom():
        raise RuntimeError("the course lookup is down")

    monkeypatch.setattr(R, "resolve_safety_level", boom)
    response = client.post(ROUTE, json=BODY)
    assert response.status_code == 500
    assert response.mimetype == "application/json"
    assert "the course lookup is down" in response.get_json()["error"]
    assert checks.intake == [] and adaption.asked == []
