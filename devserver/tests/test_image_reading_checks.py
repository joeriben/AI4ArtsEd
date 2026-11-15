"""The image readings run over the intake and the check at the result.

/compare/analyze-image takes an instruction the visitor can edit. It passes
the intake before any model reads the picture, and a refusal there ends the
request. The reading is checked at the result before it leaves: as one text
where it is answered as JSON, one paragraph at a time where it is streamed, so
that only what passed reaches the page. A refused paragraph ends the stream
with the block message, after the paragraphs that passed.

/api/image/analyze takes an optional prompt of the caller's own, which passes
the intake; without one the frame's own text is read and nothing is asked. The
analysis is checked at the result.

The gate's own functions stand in here; what they decide is tested in
test_safety_gate.py. No model is called.
"""
import json
import threading
from types import SimpleNamespace

import pytest
from flask import Flask
from PIL import Image

import config
from my_app.routes import schema_pipeline_routes as R
from my_app.services import llm_backend as LB
from my_app.services.safety_gate import (
    CHECKPOINT_INTAKE,
    CHECKPOINT_RESULT,
    REASON_CONTENT,
    REASON_PERSONAL_DATA,
    Verdict,
)
from my_app.utils import image_analysis as IA

COMPARE = "/api/schema/compare/analyze-image"
ANALYZE = "/api/image/analyze"
INSTRUCTION = "Describe the picture."
FIRST = "A house stands at the edge of a field.\n\n"
SECOND = "The light comes from the left."
READING = FIRST + SECOND


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp)
    app.register_blueprint(R.schema_compat_bp)
    return app.test_client()


class Checks:
    """The intake and the check at the result, standing in: they record what
    they were asked and refuse what they are told to -- a field at the intake,
    a field or one text at the result."""

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
        if self.refuse_result in (field, text):
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT,
                           "not for this level")
        return Verdict(True, CHECKPOINT_RESULT, level, field)


@pytest.fixture
def checks(monkeypatch):
    stand_in = Checks()
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "youth")
    monkeypatch.setattr(R, "check_intake_texts", stand_in.check_intake_texts)
    monkeypatch.setattr(R, "check_result_text", stand_in.check_result_text)
    return stand_in


@pytest.fixture
def reader(monkeypatch, tmp_path):
    """An uploaded picture, a table that offers one model, and a vision model
    that writes READING: whole, or as `reader.pieces` when streamed.
    `reader.asked` records the instructions it was given."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    picture = uploads / "a.png"
    Image.new("RGB", (96, 96), (200, 180, 160)).save(picture)
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", uploads)
    monkeypatch.setattr(R, "_image_reader_backends", lambda: {"stand-in": "llm"})

    stand_in = SimpleNamespace(path=str(picture), pieces=[FIRST, SECOND], asked=[],
                               closed=False)

    class Stream:
        def __iter__(self):
            for piece in stand_in.pieces:
                yield ("token", piece)
            yield ("done", "stop")

        def close(self):
            stand_in.closed = True

    class Backend:
        def chat(self, *, model, messages, images, temperature, **kw):
            stand_in.asked.append(messages[0]["content"])
            return {"content": READING}

        def chat_stream(self, *, model, messages, images, temperature, **kw):
            stand_in.asked.append(messages[0]["content"])
            return Stream()

    monkeypatch.setattr(LB, "get_llm_backend", lambda: Backend())
    return stand_in


@pytest.fixture
def analysis(monkeypatch):
    """A run's picture read by a stand-in, which records the prompt and the
    level it was asked with."""
    stand_in = SimpleNamespace(text="The picture shows a house.", asked=[])

    def analyze_image_from_run(run_id, prompt=None, analysis_type="bildwissenschaftlich",
                               *, level):
        stand_in.asked.append((prompt, level))
        return stand_in.text

    monkeypatch.setattr(IA, "analyze_image_from_run", analyze_image_from_run)
    return stand_in


def _compare(client, reader, **extra):
    return client.post(COMPARE, json={"image_path": reader.path, "model": "stand-in",
                                      "prompt": INSTRUCTION, **extra})


def _frames(response):
    return [json.loads(line[len("data: "):])
            for line in response.get_data(as_text=True).split("\n")
            if line.startswith("data: ")]


# ── /compare/analyze-image ──────────────────────────────────────────────────

def test_the_instruction_passes_the_intake(client, checks, reader):
    response = _compare(client, reader)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == [({"prompt": INSTRUCTION}, "youth")]
    assert reader.asked == [INSTRUCTION]


@pytest.mark.parametrize("stream", [False, True], ids=["whole", "streamed"])
def test_a_refused_instruction_reaches_no_model(client, checks, reader, stream):
    checks.refuse_intake = "prompt"
    response = _compare(client, reader, stream=stream)
    assert response.status_code == 403
    assert response.mimetype == "application/json"
    assert response.get_json()["safety_block"] == {
        "checkpoint": "intake", "field": "prompt",
        "reason_key": "personal_data", "reason": "a name"}
    assert reader.asked == [] and checks.result == []


def test_a_reading_answered_whole_is_checked_before_it_leaves(client, checks, reader):
    response = _compare(client, reader)
    assert response.get_json()["description"] == READING
    assert checks.result == [("description", READING, "youth")]


def test_a_refused_reading_is_withheld(client, checks, reader):
    checks.refuse_result = "description"
    response = _compare(client, reader)
    assert response.status_code == 403
    body = response.get_json()
    assert body["safety_block"]["checkpoint"] == "result"
    assert "description" not in body
    assert READING not in response.get_data(as_text=True)


def test_a_streamed_reading_leaves_a_paragraph_at_a_time_after_its_check(client, checks,
                                                                         reader):
    frames = _frames(_compare(client, reader, stream=True))
    assert [f["type"] for f in frames] == ["token", "token", "done"]
    assert [f["text"] for f in frames[:2]] == [FIRST, SECOND]
    assert checks.result == [("description", FIRST, "youth"), ("description", SECOND, "youth")]
    assert frames[-1]["char_count"] == len(READING)


def test_a_paragraph_leaves_only_once_it_is_complete(client, checks, reader):
    reader.pieces = ["A house ", "stands at the edge", " of a field.\n\nThe light ",
                     "comes from the left."]
    frames = _frames(_compare(client, reader, stream=True))
    assert [f["text"] for f in frames if f["type"] == "token"] == [FIRST, SECOND]


def test_a_refused_paragraph_ends_the_reading_with_the_block_message(client, checks, reader):
    checks.refuse_result = SECOND
    frames = _frames(_compare(client, reader, stream=True))
    assert [f["type"] for f in frames] == ["token", "blocked"]
    assert frames[0]["text"] == FIRST
    assert frames[1]["safety_block"]["checkpoint"] == "result"
    assert SECOND not in json.dumps(frames)
    assert reader.closed


def test_the_streamed_reading_is_checked_at_the_level_of_the_session(client, checks, reader,
                                                                     monkeypatch):
    """The reading goes on on a worker of the stream transport, where the
    resolver answers the strictest level: the level is read on the request
    thread."""
    request_thread = threading.current_thread()
    monkeypatch.setattr(R, "resolve_safety_level",
                        lambda: "youth" if threading.current_thread() is request_thread
                        else "kids")
    _frames(_compare(client, reader, stream=True))
    assert checks.intake == [({"prompt": INSTRUCTION}, "youth")]
    assert {level for _field, _text, level in checks.result} == {"youth"}


# ── /api/image/analyze ──────────────────────────────────────────────────────

def test_a_prompt_of_the_callers_own_passes_the_intake(client, checks, analysis):
    response = client.post(ANALYZE, json={"run_id": "run_x", "prompt": INSTRUCTION})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == [({"prompt": INSTRUCTION}, "youth")]
    assert analysis.asked == [(INSTRUCTION, "youth")]


def test_without_a_prompt_the_frame_is_read_and_nothing_is_asked(client, checks, analysis):
    response = client.post(ANALYZE, json={"run_id": "run_x"})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == []
    assert analysis.asked == [(None, "youth")]


def test_a_refused_prompt_reaches_no_model(client, checks, analysis):
    checks.refuse_intake = "prompt"
    response = client.post(ANALYZE, json={"run_id": "run_x", "prompt": INSTRUCTION})
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["field"] == "prompt"
    assert analysis.asked == [] and checks.result == []


def test_the_analysis_is_checked_before_it_leaves(client, checks, analysis):
    response = client.post(ANALYZE, json={"run_id": "run_x"})
    assert response.get_json()["analysis"] == analysis.text
    assert checks.result == [("analysis", analysis.text, "youth")]


def test_a_refused_analysis_is_withheld(client, checks, analysis):
    checks.refuse_result = "analysis"
    response = client.post(ANALYZE, json={"run_id": "run_x"})
    assert response.status_code == 403
    body = response.get_json()
    assert body["safety_block"]["checkpoint"] == "result"
    assert "analysis" not in body


# ── the level ───────────────────────────────────────────────────────────────

def test_a_level_that_cannot_be_resolved_runs_nothing(client, checks, reader, analysis,
                                                      monkeypatch):
    def boom():
        raise RuntimeError("the course lookup is down")

    monkeypatch.setattr(R, "resolve_safety_level", boom)
    for route, body in ((COMPARE, {"image_path": reader.path, "model": "stand-in",
                                   "prompt": INSTRUCTION, "stream": True}),
                        (ANALYZE, {"run_id": "run_x"})):
        response = client.post(route, json=body)
        assert response.status_code == 500
        assert response.mimetype == "application/json"
        assert "the course lookup is down" in response.get_json()["error"]
    assert checks.intake == [] and reader.asked == [] and analysis.asked == []
