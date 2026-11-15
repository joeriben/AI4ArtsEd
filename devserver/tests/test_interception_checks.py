"""/pipeline/interception: the intake, the text Stage 2 wrote at the result, and
the check before the model.

The intake reads every text the request brings, as it was sent, before any of
it reaches a model; the edited context reaches one right after it, to be
translated. The text Stage 2 writes leaves as the answer's `final_output` and
the terms the model looked up leave in its `metadata`; each is checked at the
result before it does. The interception an adaption was written from stays on
the server and is not read. A text the request brings itself, a Stage 2 result
handed back in or an input Stage 2 hands on as it came, passed the intake and
is not read again at the result.

Before a media model, the check reads what the model receives: the translation
at kids, with the text it was translated from, and the text as written above
kids. For SD3.5 the caption goes as written and T5 reads the interception. Code
goes to no model on this way and is checked as code at the result.

At kids and youth every picture the run stored is checked at the result, and a
picture that was not stored does not leave, nor does its raw output. Nor does a
3D model that could not be stored, with the preview its chunk sent beside it.
"""
import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         CHECKPOINT_RESULT, REASON_CONTENT,
                                         REASON_IMAGE_CONTENT, REASON_PERSONAL_DATA,
                                         REASON_SYMBOL, REASON_UNAVAILABLE, Verdict)

INTERCEPTION = "/api/schema/pipeline/interception"
DEVICE = "test-interception-checks"
PERSPECTIVE = "bauhaus"          # a perspective whose plan writes a text
PROMPT = "Ein Haus steht in einer Landschaft."
CONTEXT = "Beschreibe es so, wie es eine Architektin täte."
DESCRIPTION = "A house standing alone in a wide landscape."
WRITTEN = "A Bauhaus house in a landscape, primary colours, flat roof."
LOOKED_UP = [{"term": "Bauhaus", "why": "the school the perspective names",
              "title": "Bauhaus", "url": "https://de.wikipedia.org/wiki/Bauhaus"}]
REFUSED = "refuse-this-text"
REFUSED_BEFORE_THE_MODEL = "refuse-before-the-model"
OUTPUT = "sd35_large"
CAPTION = "a flat-roofed house, primary colours"
SKETCH = "function setup() { createCanvas(400, 400); }"
PICTURE = base64.b64encode(b"the picture the model made").decode()
MESH = base64.b64encode(b"the mesh the model made").decode()
MODEL_3D = "hunyuan3d_text_to_3d"


class _Recorder:
    """Takes every call a run makes on its record; keeps its errors and the
    entities it saves. With `store_fails` an output is not stored, and with
    `store_raises` storing it raises, as a full disk does."""

    def __init__(self, store_fails=False, store_raises=False):
        self.metadata = {"entities": [], "models_used": {}}
        self.errors = []
        self.store_fails = store_fails
        self.store_raises = store_raises

    def save_error(self, **kw):
        self.errors.append(kw)

    def save_entity(self, entity_type, content=None, metadata=None, **kw):
        if self.store_raises and entity_type.startswith("output_"):
            raise OSError("No space left on device")
        if self.store_fails and entity_type.startswith("output_"):
            return None
        sequence = len(self.metadata["entities"]) + 1
        filename = f"{sequence:02d}_{entity_type}"
        self.metadata["entities"].append({"type": entity_type, "sequence": sequence,
                                          "filename": filename})
        return filename

    def output_entities(self, kind):
        return [e for e in self.metadata["entities"] if e["type"] == f"output_{kind}"]

    def __getattr__(self, name):
        return lambda *a, **kw: None


@pytest.fixture
def run(monkeypatch):
    """/pipeline/interception, with the three checks, Stage 2, both
    translations and the media model replaced; no medium is made unless an
    output config is asked for. The checks record what they read; the intake
    and the check at the result refuse a text that carries REFUSED, the check
    before the model one that carries REFUSED_BEFORE_THE_MODEL. The media model
    records what it receives and answers `state["made"]`, by default nothing;
    the check of a picture records what it reads and refuses with
    `state["refuse_picture"]`."""
    R.init_schema_engine()
    seen = {"intake": [], "result": [], "stage2": [], "translated": [], "recorders": [],
            "for_model": [], "before_model": [], "model": [], "pictures": []}
    state = {"translation_fails": False, "made": None, "store_fails": False,
             "store_raises": False,
             "refuse_picture": False}
    stage2 = {"interception": DESCRIPTION, "adaption": WRITTEN, "looked_up": LOOKED_UP}

    def intake(fields, *, level):
        seen["intake"].append(dict(fields))
        for name, text in fields.items():
            if REFUSED in str(text or ""):
                return Verdict(False, CHECKPOINT_INTAKE, level, name, REASON_PERSONAL_DATA,
                               "refused at the intake")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def result(text, *, level, field="text"):
        seen["result"].append((field, text))
        if REFUSED in text:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT,
                           "refused at the result")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    async def execute_stage2(**kwargs):
        seen["stage2"].append(kwargs["input_text"])
        return SimpleNamespace(success=True, interception_result=stage2["interception"],
                               optimized_prompt=stage2["adaption"],
                               final_output=stage2["adaption"], error=None, steps=[],
                               execution_time=0,
                               metadata={"wikipedia_terms": list(stage2["looked_up"])})

    def translate_context(text, language, tag, on_translated=None):
        seen["translated"].append(text)
        return text

    def recorder(**kw):
        made = _Recorder(store_fails=state["store_fails"],
                         store_raises=state["store_raises"])
        seen["recorders"].append(made)
        return made

    async def translate_for_model(text, pipeline_executor, *, device_id=None,
                                  translation_instruction=None):
        seen["for_model"].append(text)
        return None if state["translation_fails"] else f"[en] {text}"

    def before_model(texts, *, level, originals=(), images=(), translation_instruction=None):
        seen["before_model"].append({"texts": dict(texts), "originals": dict(originals),
                                     "images": dict(images), "level": level})
        for name, text in texts.items():
            if REFUSED_BEFORE_THE_MODEL in str(text or ""):
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_SYMBOL,
                               "refused before the model")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    async def media_model(config_name=None, input_text=None, context_override=None, **kw):
        placeholders = getattr(context_override, "custom_placeholders", None) or {}
        seen["model"].append((config_name, input_text, placeholders.get("prompt_3")))
        return state["made"] or SimpleNamespace(
            success=False, error="stub: no model in this test", final_output=None,
            metadata={}, steps=[], execution_time=0)

    def pictures_of_run(recorder, safety_level, expect_image=False):
        return [(e["sequence"], f"picture-{e['sequence']}")
                for e in recorder.output_entities("image")], None

    def check_picture(path, *, level, recorder, entity):
        seen["pictures"].append((path, level, entity))
        if state["refuse_picture"]:
            return Verdict(False, CHECKPOINT_RESULT, level, "image", REASON_IMAGE_CONTENT,
                           "refused picture")
        return Verdict(True, CHECKPOINT_RESULT, level, "image")

    monkeypatch.setattr(R, "check_intake_texts", intake)
    monkeypatch.setattr(R, "check_result_text", result)
    monkeypatch.setattr(R, "execute_stage2_with_optimization", execute_stage2)
    monkeypatch.setattr(R, "_translate_context", translate_context)
    monkeypatch.setattr(R, "lookup_output_config", lambda media_type: None)
    monkeypatch.setattr(R, "get_recorder", recorder)
    monkeypatch.setattr(R, "_translate_for_model", translate_for_model)
    monkeypatch.setattr(R, "check_before_model", before_model)
    monkeypatch.setattr(R.pipeline_executor, "execute_pipeline", media_model)
    monkeypatch.setattr(R, "_pictures_of_run", pictures_of_run)
    monkeypatch.setattr(R, "check_result_image", check_picture)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp, url_prefix="/api/schema")
    client = app.test_client()

    def post(schema=PERSPECTIVE, level="kids", **fields):
        monkeypatch.setattr(R, "resolve_safety_level", lambda: level)
        body = {"schema": schema, "input_text": PROMPT, "device_id": DEVICE,
                "user_language": "de", **fields}
        return client.post(INTERCEPTION, json=body)

    post.seen = seen
    post.stage2 = stage2
    post.state = state
    yield post
    R._active_generations.pop(DEVICE, None)


def _errors(run):
    [recorder] = run.seen["recorders"]
    return [error["details"]["check"] for error in recorder.errors]


# ── The intake ──────────────────────────────────────────────────────────────

def test_the_intake_reads_every_text_the_request_brings(run):
    response = run(context_prompt=CONTEXT, context_language="de",
                   interception_result=DESCRIPTION, optimization_result=WRITTEN,
                   user_input=f"{PROMPT} (as typed)")
    assert response.status_code == 200, response.get_data(as_text=True)
    assert run.seen["intake"] == [{
        "input_text": PROMPT, "context_prompt": CONTEXT,
        "interception_result": DESCRIPTION, "optimization_result": WRITTEN,
        "user_input": f"{PROMPT} (as typed)"}]


@pytest.mark.parametrize("field", ["input_text", "context_prompt", "interception_result",
                                   "optimization_result", "user_input"])
def test_a_text_the_intake_refuses_reaches_no_model(run, field):
    fields = {"context_prompt": CONTEXT, "context_language": "de",
              field: f"{PROMPT} {REFUSED}"}
    response = run(**fields)
    body = response.get_json()
    assert response.status_code == 403 and body["status"] == "blocked"
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert body["safety_block"]["field"] == field
    assert run.seen["translated"] == [] and run.seen["stage2"] == []
    assert run.seen["result"] == []
    assert _errors(run) == ["intake"]


def test_the_edited_context_is_translated_after_the_intake(run):
    response = run(context_prompt=CONTEXT, context_language="de")
    assert response.status_code == 200, response.get_data(as_text=True)
    assert run.seen["intake"][0]["context_prompt"] == CONTEXT
    assert run.seen["translated"] == [CONTEXT]


def test_a_system_pipeline_passes_the_intake_as_well(run):
    response = run(schema="pre_output/translation_en")
    assert response.status_code == 200, response.get_data(as_text=True)
    assert [fields["input_text"] for fields in run.seen["intake"]] == [PROMPT]


# ── The text Stage 2 wrote, at the result ───────────────────────────────────

def test_the_text_stage2_wrote_is_read_at_the_result(run):
    response = run()
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["final_output"] == WRITTEN
    assert run.seen["result"] == [
        ("optimized_prompt", WRITTEN),
        ("wikipedia_terms", "Bauhaus: the school the perspective names")]


def test_the_interception_an_adaption_was_written_from_is_not_read(run):
    run()
    assert DESCRIPTION not in [text for _field, text in run.seen["result"]]


def test_without_an_adaption_the_interception_is_read(run):
    run.stage2["adaption"] = DESCRIPTION
    run.stage2["looked_up"] = []
    response = run()
    assert response.status_code == 200, response.get_data(as_text=True)
    assert run.seen["result"] == [("optimized_prompt", DESCRIPTION)]


@pytest.mark.parametrize("where", ["adaption", "looked_up"])
def test_a_text_refused_at_the_result_does_not_leave(run, where):
    if where == "adaption":
        run.stage2["adaption"] = f"{WRITTEN} {REFUSED}"
    else:
        run.stage2["looked_up"] = [{"term": "Bauhaus", "why": REFUSED}]
    response = run()
    body = response.get_json()
    assert response.status_code == 403 and body["status"] == "blocked"
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert REFUSED not in response.get_data(as_text=True)
    assert _errors(run) == ["result"]


def test_a_handed_in_result_is_not_read_again(run):
    response = run(interception_result=DESCRIPTION)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["final_output"] == DESCRIPTION
    assert run.seen["intake"][0]["interception_result"] == DESCRIPTION
    assert run.seen["stage2"] == [] and run.seen["result"] == []


def test_an_input_stage2_hands_on_as_it_came_is_not_read_again(run):
    response = run(schema="latent_lab")
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["final_output"] == PROMPT
    assert run.seen["stage2"] == [] and run.seen["result"] == []


# ── What a media model receives, before it ──────────────────────────────────

def test_at_kids_the_model_receives_the_translation_and_the_check_reads_both(run):
    response = run(output_config=OUTPUT)
    assert response.status_code == 502, response.get_data(as_text=True)
    assert run.seen["for_model"] == [WRITTEN]
    assert run.seen["before_model"] == [{
        "texts": {"prompt": f"[en] {WRITTEN}"}, "originals": {"prompt": WRITTEN},
        "images": {}, "level": "kids"}]
    assert run.seen["model"] == [(OUTPUT, f"[en] {WRITTEN}", None)]


@pytest.mark.parametrize("level", ["youth", "adult", "research"])
def test_above_kids_the_model_receives_the_text_as_written(run, level):
    response = run(level=level, output_config=OUTPUT)
    assert response.status_code == 502, response.get_data(as_text=True)
    assert run.seen["for_model"] == []
    assert run.seen["before_model"] == [{
        "texts": {"prompt": WRITTEN}, "originals": {}, "images": {}, "level": level}]
    assert run.seen["model"] == [(OUTPUT, WRITTEN, None)]


@pytest.mark.parametrize("level, translated", [("kids", True), ("youth", False)])
def test_for_sd35_the_caption_goes_as_written_and_t5_reads_the_interception(
        run, level, translated):
    run.stage2["adaption"] = json.dumps({"clip": CAPTION, "t5": "the adaption's long form"})
    response = run(level=level, output_config=OUTPUT)
    assert response.status_code == 502, response.get_data(as_text=True)
    long_form = f"[en] {DESCRIPTION}" if translated else DESCRIPTION
    assert run.seen["before_model"] == [{
        "texts": {"prompt": CAPTION, "prompt_3": long_form},
        "originals": {"prompt_3": DESCRIPTION} if translated else {},
        "images": {}, "level": level}]
    assert run.seen["model"] == [(OUTPUT, CAPTION, long_form)]


def test_the_pictures_the_model_receives_go_to_the_check(run):
    run(level="youth", output_config=OUTPUT, input_image="an-upload.png",
        input_image2="another-upload.png")
    assert run.seen["before_model"][0]["images"] == {
        "input_image": "an-upload.png", "input_image2": "another-upload.png"}


def test_a_text_refused_before_the_model_reaches_no_model(run):
    run.stage2["adaption"] = f"{WRITTEN} {REFUSED_BEFORE_THE_MODEL}"
    response = run(level="youth", output_config=OUTPUT)
    body = response.get_json()
    assert response.status_code == 403 and body["status"] == "blocked"
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_BEFORE_MODEL
    assert body["safety_block"]["field"] == "prompt"
    assert run.seen["model"] == []
    assert _errors(run) == ["before_model"]


def test_at_kids_a_run_without_its_translation_stops(run):
    run.state["translation_fails"] = True
    response = run(output_config=OUTPUT)
    body = response.get_json()
    assert response.status_code == 403 and body["status"] == "blocked"
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_BEFORE_MODEL
    assert body["safety_block"]["reason_key"] == REASON_UNAVAILABLE
    assert run.seen["before_model"] == [] and run.seen["model"] == []
    assert _errors(run) == ["before_model"]


@pytest.mark.parametrize("level, recorded", [("kids", True), ("adult", True),
                                             ("research", False)])
def test_the_record_names_the_models_the_check_ran_on(run, level, recorded):
    run(level=level, output_config=OUTPUT)
    [recorder] = run.seen["recorders"]
    models = recorder.metadata["models_used"]
    assert ("stage3_translation" in models) is recorded
    assert ("stage3_safety" in models) is recorded


def test_code_reaches_no_model_and_is_not_checked_before_it(run):
    run.stage2["adaption"] = SKETCH
    response = run(output_config="p5js_code")
    assert response.status_code == 502, response.get_data(as_text=True)
    assert run.seen["for_model"] == [] and run.seen["before_model"] == []
    assert run.seen["model"] == [("p5js_code", SKETCH, None)]


# ── The pictures, at the result ─────────────────────────────────────────────

def _made():
    """What a diffusers model answers: the picture as base64 in its metadata."""
    return SimpleNamespace(success=True, final_output="diffusers_generated", error=None,
                           steps=[], execution_time=0, metadata={"image_data": PICTURE})


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_every_picture_the_run_stored_is_checked_at_the_result(run, level):
    run.state["made"] = _made()
    response = run(level=level, output_config=OUTPUT)
    assert response.status_code == 200, response.get_data(as_text=True)
    [recorder] = run.seen["recorders"]
    [picture] = recorder.output_entities("image")
    assert run.seen["pictures"] == [
        (f"picture-{picture['sequence']}", level, picture["sequence"])]


def test_a_refused_picture_withholds_the_run(run):
    run.state["made"] = _made()
    run.state["refuse_picture"] = True
    response = run(level="youth", output_config=OUTPUT)
    body = response.get_json()
    assert response.status_code == 403 and body["status"] == "blocked"
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert body["safety_block"]["reason_key"] == REASON_IMAGE_CONTENT
    assert PICTURE not in response.get_data(as_text=True)


@pytest.mark.parametrize("level", ["adult", "research"])
def test_above_youth_no_picture_is_checked(run, level):
    run.state["made"] = _made()
    response = run(level=level, output_config=OUTPUT)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert run.seen["pictures"] == []


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_a_picture_that_was_not_stored_does_not_leave(run, level):
    run.state["made"] = _made()
    run.state["store_fails"] = True
    response = run(level=level, output_config=OUTPUT)
    body = response.get_json()
    assert response.status_code == 403 and body["status"] == "blocked"
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert body["safety_block"]["reason_key"] == REASON_UNAVAILABLE
    assert PICTURE not in response.get_data(as_text=True)
    assert "diffusers_generated" not in response.get_data(as_text=True)
    assert _errors(run) == ["result"]


def test_above_youth_a_picture_that_was_not_stored_goes_as_before(run):
    run.state["made"] = _made()
    run.state["store_fails"] = True
    response = run(level="adult", output_config=OUTPUT)
    assert response.status_code == 200, response.get_data(as_text=True)
    media = response.get_json()["media_output"]
    assert media["media_stored"] is False
    assert media["output"] == "diffusers_generated"
    assert media["metadata"]["image_data"] == PICTURE


def _modelled():
    """What the 3D chunk answers: the mesh and its Blender preview as base64."""
    return SimpleNamespace(success=True, final_output="hunyuan3d_generated", error=None,
                           steps=[], execution_time=0,
                           metadata={"chunk_type": "python", "media_type": "3d",
                                     "mesh_data": MESH, "mesh_format": "glb",
                                     "image_data": PICTURE})


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_a_3d_model_that_could_not_be_stored_does_not_leave(run, level):
    """Neither the mesh nor its preview, which no check has read."""
    run.state["made"] = _modelled()
    run.state["store_raises"] = True
    response = run(level=level, output_config=MODEL_3D)
    body = response.get_json()
    assert response.status_code == 403 and body["status"] == "blocked"
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert body["safety_block"]["reason_key"] == REASON_UNAVAILABLE
    text = response.get_data(as_text=True)
    assert MESH not in text and PICTURE not in text
    assert _errors(run) == ["result"]


def test_above_youth_a_3d_model_that_could_not_be_stored_goes_as_before(run):
    run.state["made"] = _modelled()
    run.state["store_raises"] = True
    response = run(level="adult", output_config=MODEL_3D)
    assert response.status_code == 200, response.get_data(as_text=True)
    media = response.get_json()["media_output"]
    assert media["media_stored"] is False
    assert media["metadata"]["mesh_data"] == MESH


# ── A saved perspective ─────────────────────────────────────────────────────

KEPT = "Sieh es so, wie es eine Architektin täte."
KEPT_TASK = "Schreibe kurz."


@pytest.fixture
def kept(run, monkeypatch):
    """The schema names a perspective somebody kept (custom:7), over the
    structure of PERSPECTIVE, as course_prompt_resolver builds one."""
    import dataclasses
    config = dataclasses.replace(R.pipeline_executor.config_loader.get_config(PERSPECTIVE),
                                 name="custom:7", context=KEPT)
    config.task_instruction = KEPT_TASK
    monkeypatch.setattr(R, "_resolve_interception_config", lambda name: config)
    return config


def test_the_intake_reads_the_text_of_a_saved_perspective(run, kept):
    response = run(schema="custom:7")
    assert response.status_code == 200, response.get_json()
    [fields] = run.seen["intake"]
    assert (fields["context_text"], fields["task_instruction"]) == (KEPT, KEPT_TASK)


def test_an_edited_context_takes_the_place_of_the_saved_one(run, kept):
    run(schema="custom:7", context_prompt=CONTEXT)
    [fields] = run.seen["intake"]
    assert "context_text" not in fields
    assert (fields["context_prompt"], fields["task_instruction"]) == (CONTEXT, KEPT_TASK)


def test_a_refused_saved_perspective_reaches_no_model(run, kept):
    kept.context = f"{KEPT} {REFUSED}"
    response = run(schema="custom:7")
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["field"] == "context_text"
    assert run.seen["stage2"] == []
