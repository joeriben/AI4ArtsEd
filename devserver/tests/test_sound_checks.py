#!/usr/bin/env python3
"""What the three sound instruments of the Crossmodal Lab check before a sound
is made.

Latent Audio Synth, ImageBind guidance and MMAudio take texts the user wrote,
and the two last a picture. Each generation passes the intake with the texts
and then the check before the model with what the node receives, at the level
its view resolved, and only then runs the node (cross_aesthetic_routes). A
refusal answers 403 with the block message and runs nothing. A picture reaches
the check by its upload's path, or as data where the body carries it. The
sound itself is not checked.

The gate functions, the stations and the node's run are stubbed; nothing here
asks a model.
"""
import json
import sys
import threading
import types
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from my_app.routes import cross_aesthetic_routes as car
from my_app.services import local_media_weights, media_stations, stable_audio_tier
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         REASON_CONTENT, REASON_PERSONAL_DATA, Verdict)

AT_THE_INTAKE = "refuse-at-the-intake"
BEFORE_THE_MODEL = "refuse-before-the-model"

# Each route, a body it runs with, and the text field a refusal is put into.
ROUTES = [
    pytest.param('/api/cross_aesthetic/synth', {"prompt_a": "a bell"}, "prompt_a",
                 id="synth"),
    pytest.param('/api/cross_aesthetic/image_guided_audio',
                 {"prompt": "rain on a roof", "image_base64": "QUJD"}, "prompt",
                 id="image_guided_audio"),
    pytest.param('/api/cross_aesthetic/mmaudio',
                 {"prompt": "rain on a roof", "negative_prompt": "music"}, "negative_prompt",
                 id="mmaudio"),
]

# The two whose node takes a picture.
PICTURED = [
    pytest.param('/api/cross_aesthetic/image_guided_audio', {"prompt": "rain on a roof"},
                 id="image_guided_audio"),
    pytest.param('/api/cross_aesthetic/mmaudio', {"prompt": "rain on a roof"}, id="mmaudio"),
]


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(car.cross_aesthetic_bp)
    return app


@pytest.fixture
def ran(monkeypatch):
    """Every station whole, the checks and the node's run recorded where they
    are reached, in that order; a text with AT_THE_INTAKE or BEFORE_THE_MODEL
    in it is refused there. The view resolves "youth"."""
    calls = []
    monkeypatch.setattr(car, "resolve_safety_level", lambda: "youth")
    monkeypatch.setattr(stable_audio_tier, "alias", lambda kind="music": "stand-in-audio")
    monkeypatch.setattr(local_media_weights, "dir_name", lambda alias: f"{alias}-folder")
    monkeypatch.setattr(media_stations, "read", lambda: {})
    monkeypatch.setattr(car, "_synth_model", lambda stations: ("stand-in-audio", "sa-folder"))
    monkeypatch.setattr(car, "_first_installed",
                        lambda station, stations: (station, f"{station}-folder"))

    def run_node(class_type, inputs, model_alias):
        calls.append(("node", class_type))
        sound = types.SimpleNamespace(media_type="audio", data=b"ABC")
        return {"seed": 7, "generation_time_ms": 1}, [sound]

    def intake_texts(fields, *, level):
        calls.append(("intake", dict(fields), level))
        for name, text in fields.items():
            if AT_THE_INTAKE in str(text or ""):
                return Verdict(False, CHECKPOINT_INTAKE, level, name, REASON_PERSONAL_DATA,
                               "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def before_model(texts, *, level, originals=(), images=(), translation_instruction=None):
        calls.append(("before_model", dict(texts), level, dict(images)))
        for name, text in texts.items():
            if BEFORE_THE_MODEL in str(text or ""):
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_CONTENT,
                               "content")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    monkeypatch.setattr(car, "_run_node", run_node)
    monkeypatch.setattr(car, "check_intake_texts", intake_texts)
    monkeypatch.setattr(car, "check_before_model", before_model)
    return calls


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    """The one directory these routes read a picture from."""
    folder = tmp_path / "uploads_tmp"
    folder.mkdir()
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", folder)
    return folder


def terminal_frame(wire: str) -> dict:
    """The streamed answer's terminal frame: the plain answer and its status."""
    for raw in wire.split("\n\n"):
        if raw.startswith("event: complete"):
            return json.loads(raw.split("data: ", 1)[1])
    raise AssertionError(f"no terminal frame on this wire: {wire[:300]!r}")


def _refused(body, field, marker):
    return {**body, field: f"{body[field]} {marker}"}


# ── The texts ───────────────────────────────────────────────────────────────

def test_the_synth_checks_what_the_user_wrote_before_the_node_runs(app, ran):
    texts = {"prompt_a": "a bell", "prompt_b": "a drum", "base_prompt": "a room"}
    response = app.test_client().post('/api/cross_aesthetic/synth', json=texts)
    assert response.status_code == 200
    assert ran == [("intake", texts, "youth"), ("before_model", texts, "youth", {}),
                   ("node", car.SYNTH_NODE)]


def test_the_poles_and_the_neutral_prompt_are_not_asked(app, ran):
    """The node is handed each moved axis's poles and the neutral prompt,
    framed, off config/audio_synth_axes.json. They are the platform's words;
    the checks read what the user wrote."""
    axis = next(iter(car._axes_table()["semantic_axes"]))
    response = app.test_client().post('/api/cross_aesthetic/synth',
                                      json={"prompt_a": "a bell", "axes": {axis: 0.5}})
    assert response.status_code == 200
    asked = {"prompt_a": "a bell", "prompt_b": "", "base_prompt": ""}
    assert [c for c in ran if c[0] == "before_model"] == [("before_model", asked, "youth", {})]


def test_mmaudio_checks_the_negative_prompt_too(app, ran):
    texts = {"prompt": "rain on a roof", "negative_prompt": "music"}
    response = app.test_client().post('/api/cross_aesthetic/mmaudio', json=texts)
    assert response.status_code == 200
    assert ran == [("intake", texts, "youth"), ("before_model", texts, "youth", {}),
                   ("node", car.MMAUDIO_NODE)]


@pytest.mark.parametrize("path,body,field", ROUTES)
def test_a_text_refused_at_the_intake_makes_no_sound(app, ran, path, body, field):
    response = app.test_client().post(path, json=_refused(body, field, AT_THE_INTAKE))
    assert response.status_code == 403
    answer = response.get_json()
    assert answer["success"] is False
    assert answer["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert answer["safety_block"]["field"] == field
    assert [c[0] for c in ran] == ["intake"]


@pytest.mark.parametrize("path,body,field", ROUTES)
def test_a_text_refused_before_the_model_makes_no_sound(app, ran, path, body, field):
    response = app.test_client().post(path, json=_refused(body, field, BEFORE_THE_MODEL))
    assert response.status_code == 403
    answer = response.get_json()
    assert answer["success"] is False
    assert answer["safety_block"]["checkpoint"] == CHECKPOINT_BEFORE_MODEL
    assert answer["safety_block"]["field"] == field
    assert [c[0] for c in ran] == ["intake", "before_model"]


@pytest.mark.parametrize("path,body,field", ROUTES)
def test_a_refusal_is_the_same_either_way(app, ran, path, body, field):
    """A streamed answer carries the plain one in its terminal frame; a refusal
    is no exception."""
    refused = _refused(body, field, BEFORE_THE_MODEL)
    client = app.test_client()
    plain = client.post(path, json=refused)
    streamed = client.post(path, json={**refused, "enable_streaming": True})
    frame = terminal_frame(streamed.get_data(as_text=True))
    assert (frame["body"], frame["http_status"]) == (plain.get_json(), 403)


def test_the_level_is_resolved_in_the_view_and_travels_with_the_work(app, ran, monkeypatch):
    """A streamed answer runs the work on a thread of its own, where the
    resolver answers the strictest level whatever the course is. The view
    resolves it on the request thread and hands it on."""
    resolved_on = []

    def level():
        resolved_on.append(threading.get_ident())
        return "adult"

    monkeypatch.setattr(car, "resolve_safety_level", level)
    response = app.test_client().post('/api/cross_aesthetic/synth',
                                      json={"prompt_a": "a bell", "enable_streaming": True})
    assert terminal_frame(response.get_data(as_text=True))["http_status"] == 200
    assert resolved_on == [threading.get_ident()]
    assert [c[2] for c in ran if c[0] in ("intake", "before_model")] == ["adult", "adult"]


# ── The picture ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,body", PICTURED)
def test_an_upload_reaches_the_check_by_its_path(app, ran, uploads, path, body):
    """The pages hand on an upload's path. The check before the model reads the
    verdict the upload keeps beside it; the picture is not judged again."""
    picture = uploads / "u1.png"
    picture.write_bytes(b"ABCD")
    response = app.test_client().post(path, json={**body, "image_path": str(picture)})
    assert response.status_code == 200
    before = next(c for c in ran if c[0] == "before_model")
    assert before[3] == {"image_path": str(picture)}


@pytest.mark.parametrize("path,body", PICTURED)
def test_a_picture_sent_as_data_is_handed_to_the_check_as_data(app, ran, path, body):
    """A picture the body carries is new material: the check judges it
    itself."""
    response = app.test_client().post(path, json={**body, "image_base64": "QUJD"})
    assert response.status_code == 200
    before = next(c for c in ran if c[0] == "before_model")
    assert before[3] == {"image_base64": "QUJD"}


def test_mmaudio_without_a_picture_hands_the_check_none(app, ran):
    response = app.test_client().post('/api/cross_aesthetic/mmaudio', json={"prompt": "rain"})
    assert response.status_code == 200
    before = next(c for c in ran if c[0] == "before_model")
    assert before[3] == {}
