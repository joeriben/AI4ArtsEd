"""An uploaded picture is checked where it comes in, and carries its verdict.

media_routes.upload_image runs the picture as it is kept through the intake
check (safety_gate.check_intake) and keeps the verdict beside it at kids and
youth. A picture that does not pass is not kept. Everything after the upload
reads that verdict and asks nothing again: the upload's own address, the
resolver every model input goes through (utils/media_ref.resolve_media_ref),
and the quick check the interface calls after an upload.

A recorded picture that the interface fetches and uploads again under its own
address carries the pass it has, where the bytes are that picture.

Run: python3 -m pytest devserver/tests/test_upload_intake.py -q
"""
import io
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask
from PIL import Image

import config
from my_app.routes import media_routes
from my_app.services import safety_gate as gate
from my_app.utils import vlm_safety
from my_app.utils.media_ref import MediaRefError, resolve_media_ref


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
    uploads = tmp_path / "uploads_tmp"
    runs = tmp_path / "json"
    uploads.mkdir()
    runs.mkdir()
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", uploads)
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", runs)
    monkeypatch.setattr(media_routes, "UPLOADS_TMP_DIR", uploads)
    monkeypatch.setattr(media_routes, "JSON_STORAGE_DIR", runs)
    monkeypatch.setattr(media_routes, "resolve_safety_level", lambda: requester["level"])
    # The file gate (magic bytes, hash list) is not what this file tests.
    monkeypatch.setattr(media_routes.upload_gate, "gate_image_upload",
                        lambda raw: (None, "test-hash"))
    return uploads, runs


@pytest.fixture
def client(storage):
    app = Flask(__name__)
    app.register_blueprint(media_routes.media_bp)
    return app.test_client()


def png_bytes(colour=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", (80, 80), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def upload(client, raw, *, source=None):
    form = {"file": (io.BytesIO(raw), "picture.png")}
    if source is not None:
        form["source"] = source
    return client.post("/api/media/upload/image", data=form,
                       content_type="multipart/form-data")


def write_run(runs, *, level, verdict_level, picture):
    """A recorded run with one picture and its verdict, as the recorder keeps it."""
    run_id = f"run_upload_{uuid.uuid4().hex[:10]}"
    folder = runs / "2026-10-31" / "dev_test" / run_id
    (folder / "final").mkdir(parents=True)
    filename = "01_output_image.png"
    (folder / "final" / filename).write_bytes(picture)
    entity = {"type": "output_image", "sequence": 1, "filename": filename, "metadata": {}}
    if verdict_level is not None:
        entity["metadata"]["safety"] = {"safe": True, "reason": "", "description": "",
                                        "checked_at": "2026-10-31T10:00:00",
                                        "level": verdict_level}
    (folder / "metadata.json").write_text(json.dumps({
        "run_id": run_id, "config_name": "test", "safety_level": level,
        "safety_verdicts": True, "entities": [entity],
    }))
    return run_id


def kept(uploads):
    return sorted(p.name for p in uploads.iterdir())


# ── The check where the picture comes in ────────────────────────────────────

def test_a_picture_that_passes_is_kept_with_its_verdict(client, storage, images):
    uploads, _runs = storage
    answer = upload(client, png_bytes())
    assert answer.status_code == 200
    image_id = answer.get_json()["image_id"]
    path = uploads / f"{image_id}.png"
    assert path.exists()
    # The picture as it is kept is the one asked, at the level of the request.
    assert images.calls == [(str(path), "kids")]
    assert gate.upload_cleared_for(image_id, "kids")


@pytest.mark.parametrize("operational,reason_key", [
    (False, "image_content"),
    (True, "unavailable"),
])
def test_a_picture_that_does_not_pass_is_not_kept(client, storage, images,
                                                  operational, reason_key):
    uploads, _runs = storage
    images.safe = False
    images.operational = operational
    answer = upload(client, png_bytes())
    assert answer.status_code == 403
    body = answer.get_json()
    assert body["error"] == "safety_blocked"
    block = body["safety_block"]
    assert (block["checkpoint"], block["reason_key"], block["field"]) == \
        ("intake", reason_key, "file")
    assert kept(uploads) == []


def test_a_verdict_that_cannot_be_kept_keeps_no_picture(client, storage, images,
                                                        monkeypatch):
    uploads, _runs = storage
    monkeypatch.setattr(media_routes, "record_upload_verdict", lambda image_id, verdict: False)
    answer = upload(client, png_bytes())
    assert answer.status_code == 500
    assert kept(uploads) == []


@pytest.mark.parametrize("level", ["adult", "research"])
def test_where_no_picture_is_checked_nothing_is_asked_or_kept_beside_it(
        client, storage, images, requester, level):
    uploads, _runs = storage
    requester["level"] = level
    answer = upload(client, png_bytes())
    assert answer.status_code == 200
    assert images.calls == []
    assert kept(uploads) == [f"{answer.get_json()['image_id']}.png"]


# ── A recorded picture, uploaded again ──────────────────────────────────────

@pytest.mark.parametrize("suffix", ["/0", "", "/0?t=1730370000"])
def test_a_recorded_picture_uploaded_again_carries_its_pass(client, storage, images,
                                                           suffix):
    _uploads, runs = storage
    run_id = write_run(runs, level="kids", verdict_level="kids", picture=png_bytes())
    answer = upload(client, png_bytes(), source=f"/api/media/image/{run_id}{suffix}")
    assert answer.status_code == 200
    assert images.calls == []
    assert gate.upload_cleared_for(answer.get_json()["image_id"], "kids")


def test_other_bytes_under_a_recorded_address_are_asked(client, storage, images):
    _uploads, runs = storage
    run_id = write_run(runs, level="kids", verdict_level="kids", picture=png_bytes())
    answer = upload(client, png_bytes((10, 10, 10)), source=f"/api/media/image/{run_id}/0")
    assert answer.status_code == 200
    assert len(images.calls) == 1


def test_a_pass_at_youth_does_not_carry_at_kids(client, storage, images):
    _uploads, runs = storage
    run_id = write_run(runs, level="youth", verdict_level="youth", picture=png_bytes())
    answer = upload(client, png_bytes(), source=f"/api/media/image/{run_id}/0")
    assert answer.status_code == 200
    assert [level for _path, level in images.calls] == ["kids"]


@pytest.mark.parametrize("source", [
    "/api/media/uploads/{upload}",
    "/api/media/video/{run}/0",
    "{run}",
])
def test_only_a_recorded_picture_s_address_carries(client, storage, images, source):
    """An upload's own address, another kind of medium and a bare run id carry
    nothing over: the upload is asked like any other."""
    uploads, runs = storage
    run_id = write_run(runs, level="kids", verdict_level="kids", picture=png_bytes())
    first = upload(client, png_bytes()).get_json()["image_id"]
    images.calls.clear()
    gate._RELEASED.clear()
    answer = upload(client, png_bytes(),
                    source=source.format(upload=first, run=run_id))
    assert answer.status_code == 200
    assert len(images.calls) == 1


# ── Everything after the upload reads the verdict ───────────────────────────

def _unjudged_upload(uploads):
    """An upload kept without a verdict, as every upload was before 2026-10-31."""
    upload_id = str(uuid.uuid4())
    (uploads / f"{upload_id}.png").write_bytes(png_bytes())
    return upload_id


def test_an_upload_goes_out_at_kids_only_with_its_verdict(client, storage, images,
                                                          requester):
    uploads, _runs = storage
    judged = upload(client, png_bytes()).get_json()["image_id"]
    unjudged = _unjudged_upload(uploads)

    assert client.get(f"/api/media/uploads/{judged}").status_code == 200
    refused = client.get(f"/api/media/uploads/{unjudged}")
    assert refused.status_code == 403
    block = refused.get_json()["safety_block"]
    assert (block["checkpoint"], block["reason_key"]) == ("result", "image_unchecked")

    requester["level"] = "adult"
    assert client.get(f"/api/media/uploads/{unjudged}").status_code == 200


def test_a_pass_at_youth_does_not_hand_an_upload_to_kids(client, storage, images,
                                                         requester):
    requester["level"] = "youth"
    image_id = upload(client, png_bytes()).get_json()["image_id"]
    assert client.get(f"/api/media/uploads/{image_id}").status_code == 200
    requester["level"] = "kids"
    assert client.get(f"/api/media/uploads/{image_id}").status_code == 403


def test_the_resolver_hands_on_an_upload_at_kids_only_with_its_verdict(client, storage,
                                                                       images):
    uploads, _runs = storage
    judged = upload(client, png_bytes()).get_json()["image_id"]
    unjudged = _unjudged_upload(uploads)

    for upload_id in (judged, unjudged):
        path = uploads / f"{upload_id}.png"
        refs = (str(path), path, upload_id, f"/api/media/uploads/{upload_id}")
        for ref in refs:
            if upload_id == judged:
                assert resolve_media_ref(ref, level="kids") == path
            else:
                with pytest.raises(MediaRefError):
                    resolve_media_ref(ref, level="kids")
            assert resolve_media_ref(ref, level="adult") == path


# ── The quick check reads the verdict and asks nothing ──────────────────────

def _quick(image_path, level):
    from my_app.routes.schema_pipeline_routes import _run_safety_check_quick
    return _run_safety_check_quick({"image_path": image_path}, level)


def test_the_quick_check_reads_the_verdict_of_every_reference(client, storage, images):
    uploads, runs = storage
    answer = upload(client, png_bytes()).get_json()
    image_id = answer["image_id"]
    run_id = write_run(runs, level="kids", verdict_level="kids", picture=png_bytes())
    images.calls.clear()

    for ref in (answer["image_path"], image_id, f"/api/media/uploads/{image_id}",
                f"/api/media/image/{run_id}/0", run_id):
        body, status = _quick(ref, "kids")
        assert (status, body["safe"]) == (200, True), ref
    assert images.calls == []


def test_the_quick_check_refuses_what_carries_no_verdict(client, storage, images,
                                                         tmp_path):
    uploads, runs = storage
    unjudged = _unjudged_upload(uploads)
    youth_run = write_run(runs, level="youth", verdict_level="youth", picture=png_bytes())
    elsewhere = tmp_path / "elsewhere.png"
    elsewhere.write_bytes(png_bytes())
    import base64
    inline = "data:image/png;base64," + base64.b64encode(png_bytes()).decode()

    for ref in (unjudged, str(elsewhere), inline, f"/api/media/image/{youth_run}/0"):
        body, status = _quick(ref, "kids")
        assert (status, body["safe"]) == (200, False), ref[:60]
        block = body["safety_block"]
        assert (block["checkpoint"], block["reason_key"]) == ("intake", "image_unchecked")
    assert images.calls == []


def test_the_quick_check_asks_nothing_where_no_picture_is_checked(storage, images):
    uploads, _runs = storage
    unjudged = _unjudged_upload(uploads)
    for level in ("adult", "research"):
        body, status = _quick(unjudged, level)
        assert (status, body["safe"]) == (200, True)
    assert images.calls == []
