#!/usr/bin/env python3
"""What the three media readings check, and where.

/api/media/analyze/image reads an uploaded picture. The picture came in
through the upload, which judged it: the reading model gets it only where the
check before the model finds a pass for the level of whoever asks now, and for
a reference that check asks no model. The reading is checked at the result as
it leaves.

/api/media/analyze/av reads a run's sound or video, and its reading is checked
at the result as it leaves. A video is read only where delivery would hand it
to whoever asks, by the verdict the check at the result wrote on it: the
reading says what the video shows.

/api/media/analyze/compare reads two readings side by side. Both readings and
their labels pass the intake, because they come from the request and go into
the model's prompt; the comparison is checked at the result as it leaves.

A refusal answers 403 with the block message, the same on both ways back, and
nothing after it runs. The views resolve the level once and hand it on.

The gate's own functions stand in here; what they decide is tested in
test_safety_gate.py. No model is called.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from my_app.routes import media_routes
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         CHECKPOINT_RESULT, REASON_CONTENT,
                                         REASON_IMAGE_UNCHECKED, REASON_PERSONAL_DATA,
                                         REASON_UNCHECKED, REASON_VIDEO_CONTENT,
                                         Verdict)

IMAGE = "/api/media/analyze/image"
AV = "/api/media/analyze/av"
COMPARE = "/api/media/analyze/compare"

REFUSE = "REFUSE"
READING = "a house at the edge of a field"
AV_READING = "a low hum, and a door somewhere behind it"
COMPARISON = "both hold still, and only one of them lets the light in"
PARTS = [{"label": "Image 1", "text": READING}, {"label": "Audio 1", "text": AV_READING}]
AV_BODY = {"run_id": "run_stand_in", "kind": "audio"}
VIDEO_BODY = {"run_id": "run_stand_in", "kind": "video"}

WAYS_BACK = pytest.mark.parametrize("stream", [False, True], ids=["whole", "streamed"])


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(media_routes.media_bp)
    return app


def post(app, path, body, stream=False):
    """The answer as ``(payload, http_status)``, over either way back."""
    client = app.test_client()
    if not stream:
        response = client.post(path, json=body)
        return response.get_json(), response.status_code
    response = client.post(path, json={**body, "enable_streaming": True})
    for raw in response.get_data(as_text=True).split("\n\n"):
        if raw.startswith("event: complete"):
            frame = json.loads(raw.split("data: ", 1)[1])
            return frame["body"], frame["http_status"]
    raise AssertionError("no terminal frame on this wire")


class Reached(list):
    """What was reached, in order. A text with REFUSE in it is refused where it
    is checked; a picture whose reference is in `unchecked` has no pass."""

    def __init__(self):
        super().__init__()
        self.unchecked = set()

    def models(self):
        return [entry for entry in self if entry[0] == "model"]


@pytest.fixture
def reached(monkeypatch):
    """The gate and the translation, standing in. The views resolve "youth"."""
    calls = Reached()
    monkeypatch.setattr(media_routes, "resolve_safety_level", lambda: "youth")

    def intake(material, *, level, kind, field):
        calls.append(("intake", material, level, kind, field))
        if REFUSE in str(material):
            return Verdict(False, CHECKPOINT_INTAKE, level, field, REASON_PERSONAL_DATA,
                           "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level, field)

    def before_model(texts, *, level, originals=(), images=(), translation_instruction=None):
        calls.append(("before_model", dict(texts), level, dict(images)))
        for field, ref in dict(images).items():
            if ref in calls.unchecked:
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, field,
                               REASON_IMAGE_UNCHECKED, "")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    def result_text(text, *, level, field="text"):
        calls.append(("result", text, level, field))
        if REFUSE in text:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT,
                           "not for this level")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    def translate(text, lang):
        calls.append(("translate", text, lang))
        return f"[{lang}] {text.strip()}"

    monkeypatch.setattr(media_routes, "check_intake", intake)
    monkeypatch.setattr(media_routes, "check_before_model", before_model)
    monkeypatch.setattr(media_routes, "check_result_text", result_text)
    monkeypatch.setattr(media_routes, "_translate_analysis", translate)
    return calls


# ── The picture ─────────────────────────────────────────────────────────────

@pytest.fixture
def upload(tmp_path, monkeypatch):
    """A picture in the uploads directory, the one place the reading takes one
    from, by the path the check is handed."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    path = uploads / "stand_in.png"
    Image.new("RGB", (120, 90), (10, 20, 30)).save(path)
    monkeypatch.setattr(media_routes, "UPLOADS_TMP_DIR", uploads)
    return str(path.resolve())


@pytest.fixture
def reader(monkeypatch, reached):
    """The reading model. It answers `reader.reading` with the blank space a
    model leaves around its answer."""
    from my_app.services.llm_service import llm_service
    model = SimpleNamespace(reading=READING)

    def analyze_image(image_b64):
        reached.append(("model", "reading"))
        return f"\n{model.reading}\n"

    monkeypatch.setattr(llm_service, "analyze_image", analyze_image)
    return model


def test_the_picture_reaches_the_model_with_the_pass_of_its_upload(app, reached, upload,
                                                                   reader):
    body, status = post(app, IMAGE, {"image_path": upload})
    assert status == 200
    assert reached[:2] == [("before_model", {}, "youth", {"image": upload}),
                           ("model", "reading")]


@WAYS_BACK
def test_a_picture_without_a_pass_reaches_no_model(app, reached, upload, reader, stream):
    reached.unchecked.add(upload)
    body, status = post(app, IMAGE, {"image_path": upload}, stream)
    assert status == 403
    assert body == {"error": "safety_blocked",
                    "safety_block": {"checkpoint": CHECKPOINT_BEFORE_MODEL, "field": "image",
                                     "reason_key": REASON_IMAGE_UNCHECKED, "reason": ""}}
    assert reached.models() == []


def test_the_reading_leaves_as_it_was_checked(app, reached, upload, reader):
    """Trimmed: the comparison takes the reading back in, and the intake knows
    a released text only in the words it was released in."""
    body, status = post(app, IMAGE, {"image_path": upload})
    assert (body, status) == ({"success": True, "analysis": READING}, 200)
    assert reached[-1] == ("result", READING, "youth", "analysis")


def test_a_translated_reading_is_checked_in_the_words_that_leave(app, reached, upload,
                                                                 reader):
    body, status = post(app, IMAGE, {"image_path": upload, "lang": "de"})
    assert (body, status) == ({"success": True, "analysis": f"[de] {READING}"}, 200)
    assert reached[-1] == ("result", f"[de] {READING}", "youth", "analysis")


def test_a_framed_reading_is_checked_as_it_leaves(app, reached, upload, monkeypatch):
    from my_app.utils import image_analysis

    def framed(image_ref, prompt=None, analysis_type=None, lang=None, level=None):
        reached.append(("model", "framed", analysis_type, level))
        return f"{READING}, read through a frame\n"

    monkeypatch.setattr(image_analysis, "analyze_image", framed)
    body, status = post(app, IMAGE, {"image_path": upload, "frame": "descriptive"})
    assert status == 200
    assert reached == [("before_model", {}, "youth", {"image": upload}),
                       ("model", "framed", "descriptive", "youth"),
                       ("result", f"{READING}, read through a frame", "youth", "analysis")]


@WAYS_BACK
def test_a_refused_reading_is_withheld(app, reached, upload, reader, stream):
    reader.reading = f"{READING} {REFUSE}"
    body, status = post(app, IMAGE, {"image_path": upload}, stream)
    assert status == 403
    assert body == {"error": "safety_blocked",
                    "safety_block": {"checkpoint": CHECKPOINT_RESULT, "field": "analysis",
                                     "reason_key": REASON_CONTENT,
                                     "reason": "not for this level"}}


# ── Sound and video ─────────────────────────────────────────────────────────

class Recorder:
    """A run, as much of one as this route reads."""

    def __init__(self, folder, entities):
        self.metadata = {"entities": entities}
        self.final_folder = folder


@pytest.fixture
def listener(tmp_path, monkeypatch, reached):
    """A run with a sound, and the reader that listens to it. It answers
    `listener.reading` with a model's blank space after it."""
    folder = tmp_path / "run_stand_in"
    folder.mkdir()
    (folder / "output_audio.wav").write_bytes(b"never decoded here")
    monkeypatch.setattr(media_routes, "load_recorder",
                        lambda run_id, base_path=None: Recorder(
                            folder, [{"type": "output_audio", "filename": "output_audio.wav"}]))
    from my_app.services import media_analysis_client
    model = SimpleNamespace(reading=AV_READING)

    class Client:
        def describe(self, path):
            reached.append(("model", "listening"))
            return f"{model.reading} "

    monkeypatch.setattr(media_analysis_client, "get_media_analysis_client", Client)
    return model


def test_the_av_reading_leaves_as_it_was_checked(app, reached, listener):
    body, status = post(app, AV, AV_BODY)
    assert (body, status) == ({"success": True, "analysis": AV_READING}, 200)
    assert reached == [("model", "listening"), ("result", AV_READING, "youth", "analysis")]


@WAYS_BACK
def test_a_refused_av_reading_is_withheld(app, reached, listener, stream):
    listener.reading = f"{AV_READING} {REFUSE}"
    body, status = post(app, AV, AV_BODY, stream)
    assert status == 403
    assert "analysis" not in body
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_RESULT


@pytest.fixture
def watcher(tmp_path, monkeypatch, reached):
    """A run with a video, and the reader that watches it. The video carries
    `watcher.verdict`, or none while that is None."""
    folder = tmp_path / "run_stand_in"
    folder.mkdir()
    (folder / "output_video.mp4").write_bytes(b"never decoded here")
    model = SimpleNamespace(reading=AV_READING, verdict=None)

    def load(run_id, base_path=None):
        metadata = {} if model.verdict is None else {"safety": dict(model.verdict)}
        return Recorder(folder, [{"type": "output_video", "filename": "output_video.mp4",
                                  "metadata": metadata}])

    monkeypatch.setattr(media_routes, "load_recorder", load)
    from my_app.services import media_analysis_client

    class Client:
        def describe_video(self, path):
            reached.append(("model", "watching"))
            return f"{model.reading} "

    monkeypatch.setattr(media_analysis_client, "get_media_analysis_client", Client)
    return model


@WAYS_BACK
def test_a_video_without_a_pass_is_not_read(app, reached, watcher, stream):
    body, status = post(app, AV, VIDEO_BODY, stream)
    assert status == 403
    assert body["safety_block"] == {"checkpoint": CHECKPOINT_RESULT, "field": "video",
                                    "reason_key": REASON_UNCHECKED, "reason": "unchecked"}
    assert reached.models() == []


def test_a_refused_video_is_not_read(app, reached, watcher):
    watcher.verdict = {"safe": False, "reason": "", "level": "youth"}
    body, status = post(app, AV, VIDEO_BODY)
    assert status == 403
    assert body["safety_block"]["reason_key"] == REASON_VIDEO_CONTENT
    assert reached.models() == []


def test_a_pass_for_a_stricter_level_is_a_pass(app, reached, watcher):
    watcher.verdict = {"safe": True, "reason": "", "level": "kids"}
    body, status = post(app, AV, VIDEO_BODY)
    assert (body, status) == ({"success": True, "analysis": AV_READING}, 200)
    assert reached == [("model", "watching"), ("result", AV_READING, "youth", "analysis")]


def test_a_pass_for_a_looser_level_is_none(app, reached, watcher):
    watcher.verdict = {"safe": True, "reason": "", "level": "adult"}
    body, status = post(app, AV, VIDEO_BODY)
    assert status == 403
    assert reached.models() == []


# ── The comparison ──────────────────────────────────────────────────────────

@pytest.fixture
def comparer(monkeypatch, reached):
    """The analysis model the comparison is written by. It writes
    `comparer.written`."""
    from my_app.services import llm_backend
    monkeypatch.setattr(config, "IMAGE_ANALYSIS_MODEL", "local/stand-in-reader")
    writer = SimpleNamespace(written=COMPARISON)

    class Backend:
        def chat(self, **kwargs):
            reached.append(("model", "comparison"))
            return {"content": writer.written}

    monkeypatch.setattr(llm_backend, "get_llm_backend", Backend)
    return writer


def test_both_readings_and_their_labels_pass_the_intake_before_the_model(app, reached,
                                                                         comparer):
    body, status = post(app, COMPARE, {"parts": PARTS})
    assert status == 200
    assert reached[:5] == [
        ("intake", READING, "youth", "text", "parts[0]"),
        ("intake", "Image 1", "youth", "text", "parts[0].label"),
        ("intake", AV_READING, "youth", "text", "parts[1]"),
        ("intake", "Audio 1", "youth", "text", "parts[1].label"),
        ("model", "comparison"),
    ]


@WAYS_BACK
@pytest.mark.parametrize("key,field", [("text", "parts[1]"), ("label", "parts[1].label")])
def test_a_refused_part_reaches_no_model(app, reached, comparer, key, field, stream):
    parts = [dict(PARTS[0]), dict(PARTS[1])]
    parts[1][key] = f"{parts[1][key]} {REFUSE}"
    body, status = post(app, COMPARE, {"parts": parts}, stream)
    assert status == 403
    assert body["safety_block"] == {"checkpoint": CHECKPOINT_INTAKE, "field": field,
                                    "reason_key": REASON_PERSONAL_DATA, "reason": "a name"}
    assert reached.models() == []


def test_the_comparison_is_checked_in_the_words_that_leave(app, reached, comparer):
    body, status = post(app, COMPARE, {"parts": PARTS, "lang": "de"})
    assert (body, status) == ({"success": True, "comparison": f"[de] {COMPARISON}"}, 200)
    assert reached[-1] == ("result", f"[de] {COMPARISON}", "youth", "comparison")


@WAYS_BACK
def test_a_refused_comparison_is_withheld(app, reached, comparer, stream):
    comparer.written = f"{COMPARISON} {REFUSE}"
    body, status = post(app, COMPARE, {"parts": PARTS}, stream)
    assert status == 403
    assert "comparison" not in body
    assert body["safety_block"]["field"] == "comparison"
