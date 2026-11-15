"""The checks of /pipeline/generation: the intake and the check before the model.

Until 2026-10-31 the generation ran Stage 3 before its model, and Stage 1 only
for a song's two texts. Now every text the request brings passes the intake as
it was sent, and what the model receives passes the check before the model:
the translation the model receives beside the text it was made from, every
other text the model receives (the negative prompt among them), and every
picture. Which text the model receives is decided as Stage 3 decided it.

The two checks, the translation for the model and Stage 4 are stand-ins: what
is under test is who is asked with what, and what goes on. No model, no GPU,
no record on disk.

Run: cd devserver && python3 -m pytest tests/test_generation_checks.py -q
"""
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         REASON_CONTENT, REASON_PERSONAL_DATA, Verdict)

DEVICE = "test-generation-checks"
GENERATION = "/api/schema/pipeline/generation"
PICTURE = "sd35_large"
PROMPT = "Ein Haus steht in einer Landschaft."
REFUSED_AT_INTAKE = "refuse-at-the-intake"
REFUSED_BEFORE_MODEL = "refuse-before-the-model"
UNTRANSLATABLE = "cannot-be-translated"
CHECKED = ("kids", "youth", "adult")


class _Recorder:
    """Takes every call a run makes on its record; keeps its errors and models."""

    def __init__(self):
        self.metadata = {"entities": [], "models_used": {}}
        self.errors = []

    def save_error(self, **kw):
        self.errors.append(kw)

    def output_entities(self, *a, **kw):
        return []

    def __getattr__(self, name):
        return lambda *a, **kw: None


def _events(response):
    """The named frames of a stream, in order, as (event, data)."""
    out = []
    for block in response.get_data(as_text=True).split("\n\n"):
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


@pytest.fixture
def generation(monkeypatch):
    """/pipeline/generation at a chosen level, on the stream or off it.

    The intake and the check before the model record what they read and refuse
    a text that carries their mark. The translation for the model answers
    "EN: <text>", or nothing for a text that cannot be translated. Stage 4
    records what it was handed and makes nothing.
    """
    R.init_schema_engine()
    seen = {"intake": [], "before_model": [], "translated": [], "stage4": [], "recorders": []}

    def intake(fields, *, level):
        seen["intake"].append(dict(fields))
        for name, text in fields.items():
            if isinstance(text, str) and REFUSED_AT_INTAKE in text:
                return Verdict(False, CHECKPOINT_INTAKE, level, name, REASON_PERSONAL_DATA,
                               "refused at the intake")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def before_model(texts, *, level, originals=(), images=(), translation_instruction=None):
        seen["before_model"].append({"texts": dict(texts), "originals": dict(originals),
                                     "images": dict(images), "level": level})
        for name, text in texts.items():
            if isinstance(text, str) and REFUSED_BEFORE_MODEL in text:
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_CONTENT,
                               "refused before the model")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    async def translate(text, pipeline_executor, **kw):
        seen["translated"].append(text)
        return None if UNTRANSLATABLE in text else f"EN: {text}"

    async def translate_half(text, label, pipeline_executor, **kw):
        seen["translated"].append(text)
        return f"EN: {text}"

    async def stage4(**kw):
        seen["stage4"].append(kw)
        return {"success": False, "error": "stub: no model in this test",
                "run_id": kw.get("run_id")}

    def recorder(**kw):
        made = _Recorder()
        seen["recorders"].append(made)
        return made

    monkeypatch.setattr(R, "check_intake_texts", intake)
    monkeypatch.setattr(R, "check_before_model", before_model)
    monkeypatch.setattr(R, "_translate_for_model", translate)
    monkeypatch.setattr(R, "_translate_encoder_text", translate_half)
    monkeypatch.setattr(R, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(R, "get_recorder", recorder)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp, url_prefix="/api/schema")
    client = app.test_client()

    def stream(level, **query):
        """The stream, as the Flow opens it: the translation is forced unless
        the query says otherwise."""
        monkeypatch.setattr(R, "resolve_safety_level", lambda: level)
        query = {"prompt": PROMPT, "output_config": PICTURE, "device_id": DEVICE,
                 "enable_streaming": "true", **query}
        response = client.get(GENERATION, query_string=query)
        # A stream runs as it is read: read it whole before anything is asserted.
        response.get_data()
        return _events(response), seen

    def post(level, **body):
        """The one-body answer, which reads no translation flag."""
        monkeypatch.setattr(R, "resolve_safety_level", lambda: level)
        body = {"prompt": PROMPT, "output_config": PICTURE, "device_id": DEVICE, **body}
        return client.post(GENERATION, json=body), seen

    stream.post = post
    stream.monkeypatch = monkeypatch
    yield stream
    R._active_generations.pop(DEVICE, None)


# ---------------------------------------------------------------------------
# The intake
# ---------------------------------------------------------------------------

def test_every_text_the_stream_takes_passes_the_intake(generation):
    _events, seen = generation(
        "kids", negative_prompt="blurry", input_text="meine Worte",
        context_prompt="ein Kontext", interception_result="das Ergebnis",
        comparison_original_prompt="das Original")
    assert seen["intake"] == [{
        "prompt": PROMPT, "negative_prompt": "blurry", "secondary_text": None,
        "input_text": "meine Worte", "context_prompt": "ein Kontext",
        "interception_result": "das Ergebnis", "comparison_original_prompt": "das Original"}]


def test_the_intake_reads_an_sd35_prompt_as_it_was_sent(generation):
    sent = json.dumps({"clip": "Ein Haus", "t5": "Ein Haus in einer weiten Landschaft"})
    _events, seen = generation("kids", prompt=sent)
    assert [fields["prompt"] for fields in seen["intake"]] == [sent]


def test_a_refusal_at_the_intake_stops_the_stream_before_anything_is_translated(generation):
    events, seen = generation("kids", input_text=f"{REFUSED_AT_INTAKE} words")
    blocked = _named(events, "blocked")
    assert [(b["reason"], b["safety_block"]["checkpoint"],
             b["safety_block"]["field"]) for b in blocked] == [
        ("refused at the intake", "intake", "input_text")]
    assert "stage3_complete" not in [name for name, _data in events]
    assert seen["translated"] == [] and seen["before_model"] == [] and seen["stage4"] == []
    assert [(e["stage"], e["details"]["check"]) for e in seen["recorders"][0].errors] == [
        (1, "intake")]


def test_off_the_stream_every_text_it_takes_passes_the_intake(generation):
    _response, seen = generation.post(
        "kids", input_text="meine Worte", context_prompt="ein Kontext",
        interception_result="das Ergebnis")
    assert seen["intake"] == [{
        "prompt": PROMPT, "input_text": "meine Worte", "context_prompt": "ein Kontext",
        "interception_result": "das Ergebnis"}]


def test_off_the_stream_a_refusal_at_the_intake_is_a_403(generation):
    response, seen = generation.post("kids", prompt=f"{REFUSED_AT_INTAKE} words")
    body = response.get_json()
    assert response.status_code == 403
    assert (body["status"], body["safety_block"]["checkpoint"]) == ("blocked", "intake")
    assert seen["before_model"] == [] and seen["stage4"] == []
    assert DEVICE not in R._active_generations


# ---------------------------------------------------------------------------
# What the model receives, and what the check reads
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", CHECKED + ("research",))
def test_where_the_model_receives_a_translation_the_check_reads_both(generation, level):
    _events, seen = generation(level)
    assert seen["translated"] == [PROMPT]
    assert [(c["texts"], c["originals"]) for c in seen["before_model"]] == [
        ({"prompt": f"EN: {PROMPT}"}, {"prompt": PROMPT})]
    assert [kw["prompt"] for kw in seen["stage4"]] == [f"EN: {PROMPT}"]


@pytest.mark.parametrize("level, translated", [
    ("kids", True), ("youth", False), ("adult", False), ("research", False)])
def test_without_the_forced_translation_kids_alone_receives_one(generation, level, translated):
    _events, seen = generation(level, force_translation="false")
    model_receives = f"EN: {PROMPT}" if translated else PROMPT
    assert seen["translated"] == ([PROMPT] if translated else [])
    assert [(c["texts"], c["originals"]) for c in seen["before_model"]] == [
        ({"prompt": model_receives}, {"prompt": PROMPT} if translated else {})]
    assert [kw["prompt"] for kw in seen["stage4"]] == [model_receives]


def test_comparison_mode_hands_the_model_the_text_as_written(generation):
    """The model's answer to the language the prompt was written in is what a
    comparison explores; the check translates for itself."""
    _events, seen = generation("kids", skip_stage3_translation="true")
    assert seen["translated"] == []
    assert [(c["texts"], c["originals"]) for c in seen["before_model"]] == [
        ({"prompt": PROMPT}, {})]
    assert [kw["prompt"] for kw in seen["stage4"]] == [PROMPT]


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_a_failed_translation_stops_the_run_where_the_model_was_to_receive_it(generation, level):
    events, seen = generation(level, prompt=f"{UNTRANSLATABLE} words")
    blocked = _named(events, "blocked")
    assert [(b["safety_block"]["checkpoint"], b["safety_block"]["reason_key"])
            for b in blocked] == [("before_model", "unavailable")]
    assert seen["before_model"] == [] and seen["stage4"] == []


@pytest.mark.parametrize("level", ["adult", "research"])
def test_at_adult_and_research_a_failed_translation_leaves_the_text_as_written(generation, level):
    text = f"{UNTRANSLATABLE} words"
    _events, seen = generation(level, prompt=text)
    assert [(c["texts"], c["originals"]) for c in seen["before_model"]] == [
        ({"prompt": text}, {})]
    assert [kw["prompt"] for kw in seen["stage4"]] == [text]


def test_the_negative_prompt_is_checked_as_the_model_receives_it(generation):
    _events, seen = generation("kids", negative_prompt="blurry")
    assert [c["texts"].get("negative_prompt") for c in seen["before_model"]] == ["blurry"]
    assert [kw["negative_prompt"] for kw in seen["stage4"]] == ["blurry"]


def test_without_a_negative_prompt_there_is_none_to_check(generation):
    _events, seen = generation("kids")
    assert ["negative_prompt" in c["texts"] for c in seen["before_model"]] == [False]


def test_the_pictures_the_model_receives_go_to_the_check(generation):
    _events, seen = generation("kids", input_image="/uploads/a.png",
                               input_image2="/uploads/b.png")
    assert [c["images"] for c in seen["before_model"]] == [
        {"input_image": "/uploads/a.png", "input_image2": "/uploads/b.png"}]


def test_each_sd35_half_is_checked_as_its_encoder_receives_it(generation):
    caption, long_form = "Ein Haus", "Ein Haus in einer weiten Landschaft"
    _events, seen = generation("kids", prompt=json.dumps({"clip": caption, "t5": long_form}))
    assert [(c["texts"], c["originals"]) for c in seen["before_model"]] == [(
        {"prompt": f"EN: {caption}", "prompt_3": f"EN: {long_form}"},
        {"prompt": caption, "prompt_3": long_form})]
    assert [(kw["prompt"], kw["prompt_3"]) for kw in seen["stage4"]] == [
        (f"EN: {caption}", f"EN: {long_form}")]


def test_a_refusal_before_the_model_stops_the_run_and_is_recorded(generation):
    events, seen = generation("kids", negative_prompt=f"{REFUSED_BEFORE_MODEL}, drums")
    blocked = _named(events, "blocked")
    assert [(b["reason"], b["safety_block"]["checkpoint"],
             b["safety_block"]["field"]) for b in blocked] == [
        ("refused before the model", "before_model", "negative_prompt")]
    assert seen["stage4"] == []
    assert [(e["stage"], e["details"]["check"], e["details"]["field"])
            for e in seen["recorders"][0].errors] == [(3, "before_model", "negative_prompt")]


@pytest.mark.parametrize("level, checks", [
    ("kids", ["translation", "llm_safety_check"]), ("research", ["translation"])])
def test_the_checks_that_passed_are_named(generation, level, checks):
    events, _seen = generation(level)
    assert [(c["was_translated"], c["checks_passed"])
            for c in _named(events, "stage3_complete")] == [(True, checks)]


def test_the_models_the_checks_ran_on_are_recorded(generation):
    from config import STAGE3_MODEL
    from my_app.services.safety_classifier import model_name
    _events, seen = generation("kids")
    assert seen["recorders"][-1].metadata["models_used"] == {
        "stage3_translation": STAGE3_MODEL, "stage3_safety": model_name()}


def test_where_nothing_is_translated_or_checked_no_model_is_recorded(generation):
    _events, seen = generation("research", force_translation="false")
    assert seen["recorders"][-1].metadata["models_used"] == {}


# ---------------------------------------------------------------------------
# A reader who left
# ---------------------------------------------------------------------------

def _leaving(generation, when):
    """The transport, as it hands the checks the leaving signal; `when` says
    whether the reader has gone before the checks or after the intake."""
    left = threading.Event()
    if when == "before":
        left.set()

    def transport(source, **kw):
        yield from source(client_gone=left)

    generation.monkeypatch.setattr(R, "events_with_heartbeat", transport)
    return left


def test_a_reader_who_left_before_the_checks_has_nothing_checked(generation):
    _leaving(generation, "before")
    events, seen = generation("kids")
    assert [name for name, _data in events] == ["connected", "stage3_start"]
    assert seen["intake"] == [] and seen["before_model"] == [] and seen["stage4"] == []


def test_a_reader_who_left_during_the_intake_has_nothing_translated(generation):
    left = _leaving(generation, "after")
    intake = R.check_intake_texts

    def intake_then_gone(fields, *, level):
        verdict = intake(fields, level=level)
        left.set()
        return verdict

    generation.monkeypatch.setattr(R, "check_intake_texts", intake_then_gone)
    events, seen = generation("kids")
    assert [name for name, _data in events] == ["connected", "stage3_start"]
    assert seen["translated"] == [] and seen["before_model"] == [] and seen["stage4"] == []


# ---------------------------------------------------------------------------
# Off the stream
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level, translated", [
    ("kids", True), ("youth", False), ("adult", False), ("research", False)])
def test_off_the_stream_kids_alone_receives_a_translation(generation, level, translated):
    _response, seen = generation.post(level)
    model_receives = f"EN: {PROMPT}" if translated else PROMPT
    assert [(c["texts"], c["originals"]) for c in seen["before_model"]] == [
        ({"prompt": model_receives}, {"prompt": PROMPT} if translated else {})]
    assert [kw["prompt"] for kw in seen["stage4"]] == [model_receives]


def test_off_the_stream_a_refusal_before_the_model_is_a_403(generation):
    response, seen = generation.post("kids", prompt=f"{REFUSED_BEFORE_MODEL} words")
    body = response.get_json()
    assert response.status_code == 403
    assert body["safety_block"]["checkpoint"] == "before_model"
    assert seen["stage4"] == []


def test_off_the_stream_a_failed_translation_at_kids_stops_the_run(generation):
    response, seen = generation.post("kids", prompt=f"{UNTRANSLATABLE} words")
    body = response.get_json()
    assert response.status_code == 403
    assert body["safety_block"]["reason_key"] == "unavailable"
    assert seen["before_model"] == [] and seen["stage4"] == []


def test_off_the_stream_the_pictures_go_to_the_check(generation):
    _response, seen = generation.post("kids", input_image="/uploads/a.png")
    assert [c["images"] for c in seen["before_model"]] == [{"input_image": "/uploads/a.png"}]


# ---------------------------------------------------------------------------
# The picture check after generation
# ---------------------------------------------------------------------------

def test_a_picture_check_that_ended_without_a_verdict_is_said_as_one(generation):
    """The transport ended without the picture check's verdict and without a
    failure. No verdict is not a pass: the run stops, and the block says that
    a check could not be carried out, never that the picture was rated."""
    from my_app.utils.vlm_safety import VLM_OPERATIONAL_BLOCK_MESSAGE

    async def made(**kw):
        return {"success": True, "media_output": {"media_type": "image"},
                "run_id": kw.get("run_id")}

    transport = R.events_with_heartbeat

    def without_the_picture_check(source, **kw):
        if getattr(source, "__name__", "") == "_vlm_work":
            return
        yield from transport(source, **kw)

    generation.monkeypatch.setattr(R, "execute_stage4_generation_only", made)
    generation.monkeypatch.setattr(R, "events_with_heartbeat", without_the_picture_check)
    events, _seen = generation("kids")
    assert [b["safety_block"] for b in _named(events, "blocked")] == [
        {"checkpoint": "result", "field": "image", "reason_key": "unavailable",
         "reason": VLM_OPERATIONAL_BLOCK_MESSAGE}]
