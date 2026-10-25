"""
Tests for media reference resolution (my_app/utils/media_ref.py).

Written after a Canvas apparatus failed on 2026-07-23: an image_evaluation node
fed by a generation node received the media URL
/api/media/image/<run_id>/<index>, and the vision helper — having no URL branch
— fell through to "assume it is already base64". The URL was decoded into a few
dozen bytes of garbage and shipped to the VLM as an image. It had never worked
since the node was introduced, and nothing tested it: the graph validator
asserts generation -> image_evaluation -> comparison is a legal apparatus, but
no test ever resolved an image.

The rule these tests hold: a reference either resolves, or it raises. Nothing
is ever reinterpreted as something else.

Run: python3 -m pytest devserver/tests/test_media_ref.py -q
"""
import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image

import config
from my_app.utils.media_ref import (
    MediaRefError,
    encode_image_b64,
    find_media_entities,
    is_media_entity,
    load_image_b64,
    resolve_media_ref,
)

RUN = "run_probe_canvas__gen_normal"


def _png(path, size=(16, 16), color=(10, 120, 200)):
    Image.new("RGB", size, color).save(path, format="PNG")


class _FakeRecorder:
    def __init__(self, final_folder, entities):
        self.final_folder = final_folder
        self.metadata = {"entities": entities}


@pytest.fixture()
def run_folder(tmp_path, monkeypatch):
    final = tmp_path / "final"
    final.mkdir()
    _png(final / "02_output_image.png")
    _png(final / "05_output_image.png", color=(200, 30, 30))
    entities = [
        {"type": "output_image", "filename": "02_output_image.png", "sequence": 2},
        {"type": "output_text", "filename": "03_translation.txt", "sequence": 3},
        {"type": "output_image", "filename": "05_output_image.png", "sequence": 5},
    ]
    import my_app.services.pipeline_recorder as pr
    monkeypatch.setattr(
        pr, "load_recorder",
        lambda run_id, base_path=None: _FakeRecorder(final, entities) if run_id == RUN else None,
    )
    return final


# ---------------------------------------------------------------------------
# The reference shapes the platform actually passes around
# ---------------------------------------------------------------------------

def test_media_url_resolves_to_the_indexed_file(run_folder):
    assert resolve_media_ref(f"/api/media/image/{RUN}/0") == run_folder / "02_output_image.png"
    assert resolve_media_ref(f"/api/media/image/{RUN}/1") == run_folder / "05_output_image.png"


def test_media_url_without_index_takes_the_latest(run_folder):
    assert resolve_media_ref(f"/api/media/image/{RUN}") == run_folder / "05_output_image.png"


def test_explicit_index_overrides_the_url(run_folder):
    assert resolve_media_ref(f"/api/media/image/{RUN}/1", index=0) == run_folder / "02_output_image.png"


def test_bare_run_id_resolves(run_folder):
    assert resolve_media_ref(RUN) == run_folder / "05_output_image.png"


def test_existing_path_is_taken_as_is(run_folder):
    path = run_folder / "02_output_image.png"
    assert resolve_media_ref(str(path)) == path
    assert resolve_media_ref(path) == path


def test_upload_id_and_upload_url_resolve(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads_tmp"
    uploads.mkdir()
    _png(uploads / "abc-123.webp")
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", uploads)
    assert resolve_media_ref("abc-123") == uploads / "abc-123.webp"
    assert resolve_media_ref("/api/media/uploads/abc-123") == uploads / "abc-123.webp"


# ---------------------------------------------------------------------------
# The regression: an unresolvable reference raises, it does not become "bytes"
# ---------------------------------------------------------------------------

def test_media_url_of_an_unknown_run_raises(run_folder):
    with pytest.raises(MediaRefError):
        resolve_media_ref("/api/media/image/run_that_does_not_exist/0")


def test_media_url_is_never_read_as_base64(run_folder):
    """The 2026-07-23 failure verbatim: the URL must not survive as image data."""
    with pytest.raises(MediaRefError):
        load_image_b64("/api/media/image/run_that_does_not_exist/0")


def test_index_out_of_range_raises(run_folder):
    with pytest.raises(MediaRefError):
        resolve_media_ref(f"/api/media/image/{RUN}/7")


def test_missing_file_on_disk_raises(run_folder):
    (run_folder / "05_output_image.png").unlink()
    with pytest.raises(MediaRefError):
        resolve_media_ref(f"/api/media/image/{RUN}/1")


def test_nonsense_and_empty_references_raise(run_folder):
    for bad in ("", "   ", None, "not-a-reference-at-all", "/api/media/image/"):
        with pytest.raises(MediaRefError):
            resolve_media_ref(bad)


def test_run_without_images_raises_naming_the_run(tmp_path, monkeypatch):
    final = tmp_path / "final"
    final.mkdir()
    import my_app.services.pipeline_recorder as pr
    monkeypatch.setattr(
        pr, "load_recorder",
        lambda run_id, base_path=None: _FakeRecorder(final, [{"type": "output_text", "filename": "a.txt"}]),
    )
    with pytest.raises(MediaRefError) as excinfo:
        resolve_media_ref("run_text_only")
    assert "run_text_only" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Entity selection — one rule, the one the media route serves by
# ---------------------------------------------------------------------------

def test_entities_are_ordered_by_sequence():
    entities = [
        {"type": "output_image", "filename": "b.png", "sequence": 5},
        {"type": "output_image", "filename": "a.png", "sequence": 2},
    ]
    assert [e["filename"] for e in find_media_entities(entities)] == ["a.png", "b.png"]


def test_legacy_bare_type_is_the_fallback_not_a_mixture():
    entities = [
        {"type": "image", "filename": "legacy.png", "sequence": 1},
        {"type": "output_image", "filename": "current.png", "sequence": 2},
    ]
    assert [e["filename"] for e in find_media_entities(entities)] == ["current.png"]
    assert [e["filename"] for e in find_media_entities([entities[0]])] == ["legacy.png"]


def test_kind_selects_the_medium():
    entities = [
        {"type": "output_image", "filename": "i.png", "sequence": 1},
        {"type": "output_audio", "filename": "a.wav", "sequence": 2},
    ]
    assert [e["filename"] for e in find_media_entities(entities, "audio")] == ["a.wav"]


def test_a_kept_latent_is_no_medium_anybody_is_handed():
    """
    A run may keep its final latent so a SET of runs can be averaged before the
    decoder. It is recorded as `output_latent` and it is numpy: there is no
    media route for it, nothing can show it, and the disclosure card would read
    an unmarked file and say the run's picture was unmarked. The listings that
    walk `output_*` generically ask this before they offer anything.
    """
    assert is_media_entity("output_image")
    assert is_media_entity("output_audio")
    assert not is_media_entity("output_latent")
    # And nothing that is no output at all.
    assert not is_media_entity("input")
    assert not is_media_entity("interception")
    assert not is_media_entity(None)


def test_the_kept_latent_is_still_addressable_by_its_own_kind():
    """
    Out of the generic listings, not out of the record: the overlay reads the
    latent of a run through the platform's one selection rule, by name.
    """
    entities = [
        {"type": "output_image", "filename": "i.png", "sequence": 1},
        {"type": "output_latent", "filename": "l.npy", "sequence": 2},
    ]
    assert [e["filename"] for e in find_media_entities(entities, "latent")] == ["l.npy"]
    assert [e["filename"] for e in find_media_entities(entities)] == ["i.png"]


# ---------------------------------------------------------------------------
# Normalisation — the envelope the VLM runner survives
# ---------------------------------------------------------------------------

def _decoded(b64):
    return Image.open(io.BytesIO(base64.b64decode(b64)))


def test_oversized_image_is_brought_into_the_envelope(tmp_path):
    path = tmp_path / "big.png"
    _png(path, size=(2000, 1200))
    img = _decoded(encode_image_b64(path))
    assert max(img.size) <= 768
    assert img.format == "JPEG"


def test_undersized_image_is_upscaled(tmp_path):
    path = tmp_path / "tiny.png"
    _png(path, size=(10, 10))
    assert min(_decoded(encode_image_b64(path)).size) >= 64


def test_transparency_is_flattened_not_dropped(tmp_path):
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (128, 128), (0, 200, 0, 128)).save(path, format="PNG")
    assert _decoded(encode_image_b64(path)).mode == "RGB"


def test_unreadable_file_raises_instead_of_passing_bytes_on(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"not-really-a-png")
    with pytest.raises(MediaRefError):
        encode_image_b64(path)


# ---------------------------------------------------------------------------
# The listings that walk a run's outputs, held against a kept latent
#
# A run of the two SD 3.5 rows may keep its final latent so a SET can be
# averaged before the decoder (Mean Images). It is recorded as `output_latent`,
# it is numpy, and there is no media route for it. Every listing that walked
# `output_*` would have offered it as something to look at, count or download —
# at an address that answers nothing. These are the four, each through its own
# route.
# ---------------------------------------------------------------------------

LATENT_RUN = "run_that_kept_its_latent"


def _client(blueprint):
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = "test-only"
    app.register_blueprint(blueprint)
    return app.test_client()


@pytest.fixture()
def one_image_one_latent(tmp_path):
    """A run holding exactly one picture and the latent it was decoded from."""
    import numpy as np

    final = tmp_path / LATENT_RUN / "final"
    final.mkdir(parents=True)
    _png(final / "02_output_image.png")
    np.save(final / "03_output_latent.npy", np.zeros((4, 8, 8), dtype=np.float16))
    entities = [
        {"type": "output_image", "filename": "02_output_image.png", "sequence": 2,
         "metadata": {"format": "png"}},
        {"type": "output_latent", "filename": "03_output_latent.npy", "sequence": 3,
         "metadata": {"format": "npy", "latent": {"model_id": "m",
                                                  "pipeline_class": "P"}}},
    ]
    return final, entities


def _recorder_for(monkeypatch, module, final, entities):
    recorder = _FakeRecorder(final, entities)
    recorder.metadata["run_id"] = LATENT_RUN
    recorder.metadata["config_name"] = "sd35_large"
    monkeypatch.setattr(
        module, "load_recorder",
        lambda run_id, base_path=None: recorder if run_id == LATENT_RUN else None)
    return recorder


def test_the_disclosure_fallback_reads_the_picture_and_not_the_latent(
    monkeypatch, one_image_one_latent
):
    """
    Without an index the card asks for the LAST output of the run. With the
    latent in that list it would open a .npy, find no marking in it, and report
    the run's picture as unmarked under the EU AI Act.
    """
    import my_app.routes.media_routes as media_routes

    final, entities = one_image_one_latent
    _recorder_for(monkeypatch, media_routes, final, entities)

    body = _client(media_routes.media_bp).get(
        f"/api/media/disclosure/{LATENT_RUN}").get_json()
    assert body["media_type"] == "image"
    assert body["filename"] == "02_output_image.png"


def test_the_media_listing_of_a_run_names_one_medium(monkeypatch, one_image_one_latent):
    import my_app.routes.media_routes as media_routes

    final, entities = one_image_one_latent
    _recorder_for(monkeypatch, media_routes, final, entities)

    body = _client(media_routes.media_bp).get(
        f"/api/media/info/{LATENT_RUN}").get_json()
    assert [o["type"] for o in body["outputs"]] == ["image"]


def test_restoring_a_favourite_hands_out_no_address_for_a_latent(
    monkeypatch, one_image_one_latent
):
    """
    `/api/media/latent/<run>/0` has no route. A restore that listed it gave the
    surface something to place and nothing to place there.
    """
    import my_app.routes.favorites_routes as favorites_routes

    final, entities = one_image_one_latent
    _recorder_for(monkeypatch, favorites_routes, final, entities)

    body = _client(favorites_routes.favorites_bp).get(
        f"/api/favorites/{LATENT_RUN}/restore").get_json()
    outputs = body["media_outputs"]
    assert [o["type"] for o in outputs] == ["image"]
    assert all("/api/media/latent/" not in o["url"] for o in outputs)


def test_the_research_table_counts_one_medium_for_a_run_that_kept_a_latent(
    monkeypatch, tmp_path, one_image_one_latent
):
    """The table's column says how many media a run produced. A latent is none."""
    import json as _json

    import my_app.routes.settings_routes as settings_routes

    final, entities = one_image_one_latent
    folder = final.parent
    (folder / "metadata.json").write_text(_json.dumps({
        "run_id": LATENT_RUN,
        "timestamp": "2026-09-04T10:00:00",
        "config_name": "sd35_large",
        "safety_level": "open",
        "device_id": "dev",
        "entities": entities,
    }), encoding="utf-8")

    info = settings_routes.MetadataInfo(
        metadata_path=folder / "metadata.json", run_id=LATENT_RUN,
        run_folder=folder, relative_path=LATENT_RUN)
    monkeypatch.setattr(settings_routes, "get_cached_metadata_files",
                        lambda base_path: [info])

    body = _client(settings_routes.settings_bp).get(
        "/api/settings/sessions").get_json()
    session = next(s for s in body["sessions"] if s["run_id"] == LATENT_RUN)
    assert session["entity_count"] == 2
    assert session["media_count"] == 1
