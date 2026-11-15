"""What a Latent Lab recording brings from the browser is checked where it comes in.

An instrument records its run from the browser: its parameters and results, its
own word about each output and part, and its pictures, as base64 or as the
address of a picture this storage already holds
(latent_lab_recorder_routes.save_recording). A reading instrument sets the
plate a run is shown by the same way (set_run_output). Until 2026-10-31 none of
it was checked, and no picture of a lab run carried a verdict, so at kids and
youth none of them went out.

Run: python3 -m pytest devserver/tests/test_latent_lab_recording_intake.py -q
"""
import base64
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask
from PIL import Image

import config
from my_app.routes import latent_lab_recorder_routes as routes
from my_app.services import latent_lab_recorder as lab
from my_app.services import safety_gate as gate
from my_app.services.pipeline_recorder import entity_cleared_for_delivery
from my_app.utils import vlm_safety
from schemas.engine import stage_orchestrator

DEVICE = "tablet-07_2026-10-31"


class FakeImageCheck:
    """Stands in for the vision model's picture question."""

    def __init__(self):
        self.calls = []
        self.safe = True
        self.operational = False

    def __call__(self, path, level):
        self.calls.append((str(path), level))
        if self.safe:
            return True, "", ""
        if self.operational:
            return False, vlm_safety.VLM_OPERATIONAL_BLOCK_MESSAGE, ""
        return False, vlm_safety.VLM_CONTENT_BLOCK_MESSAGE, ""


@pytest.fixture(autouse=True)
def fresh_memory():
    gate._RELEASED.clear()
    yield
    gate._RELEASED.clear()


@pytest.fixture(autouse=True)
def names(monkeypatch):
    """The name recogniser: available, and finding nothing."""
    monkeypatch.setattr(stage_orchestrator, "fast_dsgvo_check", lambda text: (False, [], True))


@pytest.fixture
def images(monkeypatch):
    fake = FakeImageCheck()
    monkeypatch.setattr(vlm_safety, "vlm_safety_check", fake)
    return fake


@pytest.fixture
def requester():
    """The level of whoever sends the request; a test sets it."""
    return {"level": "kids"}


@pytest.fixture
def storage(tmp_path, monkeypatch, requester):
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(routes, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(routes, "resolve_safety_level", lambda: requester["level"])
    return tmp_path


@pytest.fixture
def client(storage):
    app = Flask(__name__)
    app.register_blueprint(routes.latent_lab_recorder_bp)
    return app.test_client()


@pytest.fixture
def sitting(storage):
    opened = []

    def open_one(tool):
        recorder = lab.create_lab_recorder(latent_lab_tool=tool, device_id=DEVICE)
        opened.append(recorder.session_id)
        return recorder.session_id

    yield open_one
    for session_id in opened:
        lab.cleanup_lab_recorder(session_id)


@pytest.fixture
def names_refused(monkeypatch):
    """The intake check, replaced: it refuses a text that names someone."""

    def check_intake(material, *, level, kind, field):
        if kind == "text" and "Max Muster" in material:
            return gate.Verdict(False, gate.CHECKPOINT_INTAKE, level, field,
                                gate.REASON_PERSONAL_DATA, "DSGVO: Max Muster")
        return gate.Verdict(True, gate.CHECKPOINT_INTAKE, level, field)

    monkeypatch.setattr(routes, "check_intake", check_intake)


def png_b64(colour=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), colour).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def picture(b64=None, **meta):
    out = {"type": "image", "format": "png", "dataBase64": b64 or png_b64()}
    if meta:
        out["meta"] = meta
    return out


def save(client, session_id, **body):
    return client.post("/api/latent-lab/record/save", json={"session_id": session_id, **body})


def written(storage, run_id):
    folder = next(storage.glob(f"*/*/{run_id}"))
    return folder, json.loads((folder / "metadata.json").read_text(encoding="utf-8"))


def the_picture(metadata):
    [entity] = [e for e in metadata["entities"] if e["type"] == "output_image"]
    return entity


def no_run_written(storage):
    return list(storage.glob("*/*/run_*")) == []


# ── A recording ─────────────────────────────────────────────────────────────

def test_a_picture_that_passes_carries_its_verdict(client, storage, images, sitting):
    answer = save(client, sitting("composable_diffusion"),
                  parameters={"prompt": "a lighthouse"}, outputs=[picture()])
    assert answer.status_code == 200
    _folder, metadata = written(storage, answer.get_json()["run_id"])
    assert metadata["safety_level"] == "kids"
    entity = the_picture(metadata)
    assert (entity["metadata"]["safety"]["safe"], entity["metadata"]["safety"]["level"]) == \
        (True, "kids")
    assert entity_cleared_for_delivery(entity, metadata, "kids") == (True, "")
    assert [level for _path, level in images.calls] == ["kids"]


def test_the_picture_asked_about_is_the_one_kept(client, storage, monkeypatch, sitting):
    """Decoded as the recorder decodes it. A picture whose base64 is shorter than
    a path was once read as a path, found nowhere, and refused as a fault."""
    seen = []

    def look(path, level):
        seen.append(Path(path).read_bytes())
        return True, "", ""

    monkeypatch.setattr(vlm_safety, "vlm_safety_check", look)
    b64 = png_b64((1, 2, 3))
    assert len(b64) < 1024
    assert save(client, sitting("composable_diffusion"), outputs=[picture(b64)]).status_code == 200
    assert seen == [base64.b64decode(b64)]


@pytest.mark.parametrize("operational,reason_key", [
    (False, "image_content"),
    (True, "unavailable"),
])
def test_a_picture_that_does_not_pass_refuses_the_recording(client, storage, images, sitting,
                                                            operational, reason_key):
    images.safe = False
    images.operational = operational
    answer = save(client, sitting("composable_diffusion"), outputs=[picture()])
    assert answer.status_code == 403
    block = answer.get_json()["safety_block"]
    assert (block["checkpoint"], block["reason_key"], block["field"]) == \
        ("intake", reason_key, "outputs[0]")
    assert no_run_written(storage)


@pytest.mark.parametrize("body, field", [
    ({"parameters": {"prompt": "für Max Muster"}}, "parameters[prompt]"),
    ({"parameters": {"concepts": [{"text": "Max Muster"}]}}, "parameters[concepts][0][text]"),
    ({"results": {"caption": "Max Muster am Strand"}}, "results[caption]"),
    ({"outputs": [picture(words="Max Muster")]}, "outputs[0][meta][words]"),
    ({"steps": [{"format": "png", "dataBase64": png_b64(), "meta": {"label": "Max Muster"}}]},
     "steps[0][meta][label]"),
])
def test_a_name_in_the_words_refuses_the_recording(client, storage, sitting, names_refused,
                                                   body, field):
    answer = save(client, sitting("composable_diffusion"), **body)
    assert answer.status_code == 403
    block = answer.get_json()["safety_block"]
    assert (block["reason_key"], block["field"]) == ("personal_data", field)
    assert no_run_written(storage)


@pytest.mark.parametrize("level", ["adult", "research"])
def test_where_no_picture_is_checked_none_is_asked_and_none_carries_a_verdict(
        client, storage, images, requester, sitting, level):
    requester["level"] = level
    # A verdict sent along by the browser is not the instrument's word, and is
    # not written either.
    forged = {"safe": True, "level": "kids", "checked_at": "2026-10-31T00:00:00"}
    answer = save(client, sitting("composable_diffusion"),
                  outputs=[picture(safety=forged, view="mean")])
    assert answer.status_code == 200
    assert images.calls == []
    _folder, metadata = written(storage, answer.get_json()["run_id"])
    assert metadata["safety_level"] == level
    entity = the_picture(metadata)
    assert "safety" not in entity["metadata"]
    assert entity["metadata"]["view"] == "mean"
    assert entity_cleared_for_delivery(entity, metadata, "kids") == (False, "unchecked")


def test_a_verdict_sent_along_is_never_the_one_on_the_picture(client, storage, images, sitting):
    forged = {"safe": True, "level": "kids", "checked_at": "forged"}
    answer = save(client, sitting("composable_diffusion"), outputs=[picture(safety=forged)])
    _folder, metadata = written(storage, answer.get_json()["run_id"])
    assert the_picture(metadata)["metadata"]["safety"]["checked_at"] != "forged"


def test_a_picture_read_through_its_address_carries_a_pass_at_the_level(client, storage, images,
                                                                        sitting):
    first = save(client, sitting("mean_images"), outputs=[picture()]).get_json()["run_id"]
    images.calls.clear()
    answer = save(client, sitting("mean_images"),
                  outputs=[{"type": "image", "format": "png", "ref": f"/api/media/image/{first}/0"}])
    assert answer.status_code == 200
    assert images.calls == []
    _folder, metadata = written(storage, answer.get_json()["run_id"])
    assert the_picture(metadata)["metadata"]["safety"]["level"] == "kids"


def test_the_parts_go_out_with_the_finished_picture(client, storage, images, sitting):
    """The Denoising Archaeology's step pictures, where the browser records them,
    are not asked about one by one: they go out with the verdict on the finished
    picture, and only with it."""
    answer = save(client, sitting("denoising_archaeology"), outputs=[picture()],
                  steps=[{"format": "png", "dataBase64": png_b64((i, i, i))} for i in range(3)])
    assert answer.status_code == 200
    assert len(images.calls) == 1
    _folder, metadata = written(storage, answer.get_json()["run_id"])
    steps = [e for e in metadata["entities"] if e["type"] == "latent_lab_step"]
    assert len(steps) == 3
    for step in steps:
        assert entity_cleared_for_delivery(step, metadata, "kids") == (True, "")


# ── A plate ─────────────────────────────────────────────────────────────────

def plate_run(client, sitting):
    answer = save(client, sitting("attention_cartography"), outputs=[picture(plate="reading")])
    assert answer.status_code == 200
    return answer.get_json()["run_id"]


def set_plate(client, run_id, **body):
    return client.post(f"/api/latent-lab/run/{run_id}/output/0",
                       json={"device_id": DEVICE, "dataBase64": png_b64((5, 90, 200)), **body})


def test_a_plate_that_passes_carries_its_own_verdict(client, storage, images, sitting):
    run_id = plate_run(client, sitting)
    answer = set_plate(client, run_id, reading={"words": "lighthouse"})
    assert answer.status_code == 200
    assert len(images.calls) == 2
    _folder, metadata = written(storage, run_id)
    entity = the_picture(metadata)
    assert entity["metadata"]["safety"]["level"] == "kids"
    assert entity["metadata"]["reading"] == {"words": "lighthouse"}
    assert entity_cleared_for_delivery(entity, metadata, "kids") == (True, "")


@pytest.mark.parametrize("operational", [False, True])
def test_a_plate_that_does_not_pass_is_not_set(client, storage, images, sitting, operational):
    run_id = plate_run(client, sitting)
    folder, metadata = written(storage, run_id)
    path = folder / "final" / the_picture(metadata)["filename"]
    before = path.read_bytes()
    images.safe = False
    images.operational = operational
    answer = set_plate(client, run_id)
    assert answer.status_code == 403
    assert answer.get_json()["safety_block"]["field"] == "dataBase64"
    assert path.read_bytes() == before
    _folder, metadata = written(storage, run_id)
    assert the_picture(metadata)["metadata"]["safety"]["safe"] is True


def test_a_plate_set_unchecked_loses_the_verdict_of_the_one_it_replaced(client, storage, images,
                                                                       requester, sitting):
    run_id = plate_run(client, sitting)
    requester["level"] = "adult"
    answer = set_plate(client, run_id)
    assert answer.status_code == 200
    _folder, metadata = written(storage, run_id)
    entity = the_picture(metadata)
    assert "safety" not in entity["metadata"]
    assert entity_cleared_for_delivery(entity, metadata, "kids") == (False, "unchecked")


def test_a_name_in_a_plate_s_reading_is_not_set(client, storage, images, sitting, names_refused):
    run_id = plate_run(client, sitting)
    answer = set_plate(client, run_id, reading={"words": ["Haus", "Max Muster"]})
    assert answer.status_code == 403
    assert answer.get_json()["safety_block"]["field"] == "reading[words][1]"
    _folder, metadata = written(storage, run_id)
    assert "reading" not in the_picture(metadata)["metadata"]
