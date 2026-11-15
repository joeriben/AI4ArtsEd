"""The direct route (/api/schema/pipeline/direct) checks its pictures at the
result, at kids and youth.

Every picture the run stored goes to the check at the result, the Blender
preview of a 3D run included, each with its verdict on its entity. The
algebra's reference picture stands in the answer alone and is stored nowhere,
so it is checked as it stands there. One refused picture withholds the run:
the answer carries none of its pictures, the Denoising Archaeology writes no
record of it, and the run's record holds the block. At adult and research no
picture is checked.

The two checks before the model pass, and the store, the pipeline, the
archaeology's record and the check of a picture are replaced; nothing here asks
a model.
"""
import base64
from types import SimpleNamespace

import pytest

from my_app.routes import schema_pipeline_routes as R
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         CHECKPOINT_RESULT, REASON_IMAGE_CONTENT, Verdict)

PICTURE = base64.b64encode(b"the picture the model made").decode()
REFERENCE = base64.b64encode(b"the reference picture of the algebra").decode()
FRAME = base64.b64encode(b"a step of the denoising").decode()
MESH = base64.b64encode(b"a mesh").decode()


class _Recorder:
    """Takes every call a run makes on its record; keeps its errors and the
    entities it saves."""

    run_id = "run_direct_pictures"

    def __init__(self):
        self.metadata = {"entities": [], "current_state": {}}
        self.errors = []

    def save_error(self, **kw):
        self.errors.append(kw)

    def save_entity(self, entity_type, content=None, metadata=None, **kw):
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
def run(monkeypatch, tmp_path):
    """The direct route, answering what `state["made"]` says the model made.
    The check of a picture keeps what it reads and refuses the stored pictures
    with "stored" in `state["refuse"]`, the reference picture with
    "reference"."""
    import config
    from my_app.services import denoising_archaeology_record
    seen = {"recorders": [], "pictures": [], "records": []}
    state = {"made": None, "refuse": set()}

    def recorder(**kw):
        made = _Recorder()
        seen["recorders"].append(made)
        return made

    async def execute_pipeline(**kwargs):
        return state["made"]

    def pictures_of_run(recorder, safety_level, expect_image=False):
        return [(e["sequence"], f"picture-{e['sequence']}")
                for e in recorder.output_entities("image")], None

    def check_picture(path, *, level, recorder=None, entity=None, field="image"):
        seen["pictures"].append((path, level, entity, field))
        if ("reference" if path == REFERENCE else "stored") in state["refuse"]:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_IMAGE_CONTENT,
                           "refused picture")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    def record_archaeology_run(raw_record, **kw):
        seen["records"].append(raw_record)
        return {"id": "the written run"}, None

    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(R, "check_intake_texts",
                        lambda fields, *, level: Verdict(True, CHECKPOINT_INTAKE, level))
    monkeypatch.setattr(R, "check_before_model",
                        lambda texts, *, level, **kw: Verdict(True, CHECKPOINT_BEFORE_MODEL,
                                                              level))
    monkeypatch.setattr(R, "get_recorder", recorder)
    monkeypatch.setattr(R, "pipeline_executor",
                        SimpleNamespace(execute_pipeline=execute_pipeline,
                                        config_loader=SimpleNamespace(
                                            get_config=lambda name: None)))
    monkeypatch.setattr(R, "_pictures_of_run", pictures_of_run)
    monkeypatch.setattr(R, "check_result_image", check_picture)
    monkeypatch.setattr(denoising_archaeology_record, "record_archaeology_run",
                        record_archaeology_run)

    def go(level="kids", **fields):
        data = {"prompt": "a house", "output_config": "sd35_large", "seed": 1, **fields}
        return R._run_direct_workflow(data, level)

    go.seen = seen
    go.state = state
    return go


def _made(output, **metadata):
    """What a model answers: a sentinel, and its pictures as base64 in the
    metadata."""
    return SimpleNamespace(success=True, final_output=output, error=None, metadata=metadata)


def _algebra():
    return _made("diffusers_algebra_generated", result_image=PICTURE,
                 reference_image=REFERENCE, algebra_data={"encoder": "all"})


def _archaeology():
    return _made("diffusers_archaeology_generated", image_data=PICTURE,
                 archaeology_data={"frames": [FRAME]})


# ── The stored pictures ─────────────────────────────────────────────────────

@pytest.mark.parametrize("level", ["kids", "youth"])
def test_every_picture_the_run_stored_is_checked_on_its_entity(run, level):
    run.state["made"] = _made("diffusers_generated", image_data=PICTURE)
    payload, status = run(level=level)
    assert status == 200, payload
    [recorder] = run.seen["recorders"]
    [picture] = recorder.output_entities("image")
    assert run.seen["pictures"] == [
        (f"picture-{picture['sequence']}", level, picture["sequence"], "image")]


def test_a_refused_picture_withholds_the_run(run):
    run.state["made"] = _made("diffusers_attention_generated", image_data=PICTURE,
                              attention_data={"tokens": ["a", "house"]})
    run.state["refuse"] = {"stored"}
    payload, status = run(level="youth")
    assert status == 403 and payload["status"] == "blocked"
    assert payload["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert payload["safety_block"]["reason_key"] == REASON_IMAGE_CONTENT
    assert PICTURE not in repr(payload)
    assert "attention_data" not in payload
    [recorder] = run.seen["recorders"]
    assert [error["error_type"] for error in recorder.errors] == ["safety_blocked"]


@pytest.mark.parametrize("level", ["adult", "research"])
def test_above_youth_no_picture_is_checked(run, level):
    run.state["made"] = _algebra()
    payload, status = run(level=level)
    assert status == 200, payload
    assert run.seen["pictures"] == []
    assert payload["algebra_data"]["reference_image"] == REFERENCE


def test_the_preview_of_a_3d_run_is_checked(run):
    run.state["made"] = _made("hunyuan3d_generated", mesh_data=MESH, image_data=PICTURE,
                              media_type="3d")
    payload, status = run(level="kids")
    assert status == 200, payload
    [recorder] = run.seen["recorders"]
    [preview] = recorder.output_entities("image")
    assert [entity for _path, _level, entity, _field in run.seen["pictures"]] == [
        preview["sequence"]]


# ── The reference picture of the algebra ────────────────────────────────────

@pytest.mark.parametrize("level", ["kids", "youth"])
def test_the_reference_picture_is_checked_as_it_stands_in_the_answer(run, level):
    run.state["made"] = _algebra()
    payload, status = run(level=level)
    assert status == 200, payload
    assert (REFERENCE, level, None, "reference_image") in run.seen["pictures"]
    assert len(run.seen["pictures"]) == 2, "the result picture and the reference"
    assert payload["algebra_data"]["reference_image"] == REFERENCE


def test_a_refused_reference_picture_withholds_the_run(run):
    run.state["made"] = _algebra()
    run.state["refuse"] = {"reference"}
    payload, status = run(level="kids")
    assert status == 403 and payload["status"] == "blocked"
    assert payload["safety_block"]["field"] == "reference_image"
    assert REFERENCE not in repr(payload) and PICTURE not in repr(payload)


# ── The steps of the Denoising Archaeology ──────────────────────────────────

def test_the_steps_go_out_with_the_checked_picture(run):
    run.state["made"] = _archaeology()
    payload, status = run(level="kids", record={"sitting": "one"})
    assert status == 200, payload
    assert len(run.seen["pictures"]) == 1, "the steps count as checked with the picture"
    assert run.seen["records"] == [{"sitting": "one"}]
    assert payload["archaeology_data"]["frames"] == [FRAME]


def test_a_refused_picture_writes_no_record_and_no_step_leaves(run):
    run.state["made"] = _archaeology()
    run.state["refuse"] = {"stored"}
    payload, status = run(level="kids", record={"sitting": "one"})
    assert status == 403, payload
    assert run.seen["records"] == []
    assert FRAME not in repr(payload) and PICTURE not in repr(payload)
