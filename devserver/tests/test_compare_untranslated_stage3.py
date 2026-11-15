"""Compare without translation: the check before the model reads what the model receives.

The language comparison (views/compare/language_comparison.vue) opens the
generation stream (GET /pipeline/generation) with skip_stage3_translation, so
that each image model receives the prompt in the language it was written in.
Until 2026-10-31 Stage 3 translated for its §86a list and, at kids, the
classifier read only that translation while the route then put the original
back in its place: the model received a text no classifier had read. The flag
comes from the client, so the same held for any request that sent it.

Since 2026-11-01 the check before the model (safety_gate.check_before_model)
reads every text as the model receives it and translates for itself where it
needs a translation; adult is checked as well, and at research the check
itself passes. What is tested here is that the flag changes what the model
receives and nothing of what is read: the text that is read is the text that
generates, at every level.

The route and the stream are the real ones. The intake, the check before the
model and Stage 4 are stand-ins that record what they are handed; nothing is
translated for the model, because the flag says so. No model, no GPU, no
record on disk.

Run: cd devserver && python3 -m pytest tests/test_compare_untranslated_stage3.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         REASON_CONTENT, Verdict)

REFUSED = "REFUSED"
PROMPT = "Ein Haus steht in einer Landschaft."
DEVICE = "test-compare_cmp0"
GENERATION = "/api/schema/pipeline/generation"
CHECKED = ("kids", "youth", "adult")


class _Recorder:
    """Takes every call a run makes on its record; keeps its errors."""

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


def _blocked_at(events):
    """The checkpoints of the `blocked` frames of a stream, in order."""
    return [data["safety_block"]["checkpoint"] for event, data in events if event == "blocked"]


@pytest.fixture
def compare(monkeypatch):
    """A request as the language comparison sends it, at a chosen level."""
    R.init_schema_engine()
    seen = {"translated": [], "before_model": [], "stage4": []}

    def intake(fields, *, level):
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def before_model(texts, *, level, originals=(), images=(), translation_instruction=None):
        seen["before_model"].append({"texts": dict(texts), "originals": dict(originals),
                                     "level": level})
        for name, text in texts.items():
            if isinstance(text, str) and REFUSED in text:
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_CONTENT,
                               "refused before the model")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    async def translate(text, *a, **kw):
        seen["translated"].append(text)
        return f"EN: {text}"

    async def stage4(**kw):
        seen["stage4"].append(kw)
        return {"success": False, "error": "stub: no model in this test",
                "run_id": kw.get("run_id")}

    monkeypatch.setattr(R, "check_intake_texts", intake)
    monkeypatch.setattr(R, "check_before_model", before_model)
    monkeypatch.setattr(R, "_translate_for_model", translate)
    monkeypatch.setattr(R, "_translate_encoder_text", translate)
    monkeypatch.setattr(R, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(R, "get_recorder", lambda **kw: _Recorder())
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp, url_prefix="/api/schema")
    client = app.test_client()

    def ask(level, prompt=PROMPT, output_config="sd35_large", **extra):
        monkeypatch.setattr(R, "resolve_safety_level", lambda: level)
        query = {"prompt": prompt, "output_config": output_config, "device_id": DEVICE,
                 "enable_streaming": "true", "skip_stage3_translation": "true",
                 "source_view": "compare", **extra}
        response = client.get(GENERATION, query_string=query)
        # A stream runs as it is read: read it whole before anything is asserted.
        response.get_data()
        return _events(response), seen

    yield ask
    R._active_generations.pop(DEVICE, None)


@pytest.mark.parametrize("level", CHECKED + ("research",))
def test_the_check_reads_the_text_the_model_receives(compare, level):
    _events, seen = compare(level)
    assert seen["translated"] == []
    assert [(c["texts"], c["originals"]) for c in seen["before_model"]] == [({"prompt": PROMPT}, {})]
    assert [kw["prompt"] for kw in seen["stage4"]] == [PROMPT]


@pytest.mark.parametrize("level", CHECKED)
def test_a_refused_text_reaches_no_model(compare, level):
    events, seen = compare(level, prompt=f"{PROMPT} {REFUSED}")
    assert _blocked_at(events) == ["before_model"]
    assert seen["stage4"] == []


@pytest.mark.parametrize("level", CHECKED + ("research",))
def test_both_encoder_texts_reach_the_encoders_as_they_were_read(compare, level):
    """An SD3.5 adaptation sent with the flag: caption and long form reach
    their encoders untranslated, each read as its encoder receives it."""
    caption, long_form = "Ein Haus", "Ein Haus steht in einer Landschaft."
    _events, seen = compare(level, prompt=json.dumps({"clip": caption, "t5": long_form}))
    assert seen["translated"] == []
    assert [(c["texts"], c["originals"]) for c in seen["before_model"]] == [
        ({"prompt": caption, "prompt_3": long_form}, {})]
    assert [(kw["prompt"], kw["prompt_3"]) for kw in seen["stage4"]] == [(caption, long_form)]


@pytest.mark.parametrize("level", CHECKED)
def test_a_refused_encoder_text_stops_the_run(compare, level):
    caption, long_form = "Ein Haus", f"Ein Haus steht in einer Landschaft {REFUSED}."
    events, seen = compare(level, prompt=json.dumps({"clip": caption, "t5": long_form}))
    assert _blocked_at(events) == ["before_model"]
    assert seen["stage4"] == []
