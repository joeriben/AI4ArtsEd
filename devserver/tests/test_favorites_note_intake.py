"""A favourite's note is the user's own material, checked where it comes in.

The note is kept beside the favourite, and the chat hands it to its model
(`lookup_shared_favorites`). Until this check it reached both unread. The
interface sends no note today; any client can.

Run: python3 -m pytest devserver/tests/test_favorites_note_intake.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

import config
from my_app.routes import favorites_routes
from my_app.services import safety_gate as gate

MEIN = "tablet-07_2026-10-31"


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(favorites_routes, "JSON_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(favorites_routes, "resolve_safety_level", lambda: "kids")
    (tmp_path / "favorites.json").write_text(json.dumps({
        "version": "1.0", "mode": "global",
        "favorites": [{"run_id": "run_mine", "device_id": MEIN, "media_type": "image",
                       "user_id": "anonymous", "user_note": "alt",
                       "added_at": "2026-10-31T10:00:00"}],
    }), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def client(storage):
    app = Flask(__name__)
    app.register_blueprint(favorites_routes.favorites_bp)
    return app.test_client()


@pytest.fixture()
def checked(monkeypatch):
    """The intake check, replaced: it refuses a note that names someone."""
    seen = []

    def check_intake(material, *, level, kind, field):
        seen.append((material, level, kind, field))
        if "Max Muster" in material:
            return gate.Verdict(False, gate.CHECKPOINT_INTAKE, level, field,
                                gate.REASON_PERSONAL_DATA, "DSGVO: Max Muster")
        return gate.Verdict(True, gate.CHECKPOINT_INTAKE, level, field)

    monkeypatch.setattr(favorites_routes, "check_intake", check_intake)
    return seen


def _notes(storage):
    data = json.loads((storage / "favorites.json").read_text(encoding="utf-8"))
    return {f["run_id"]: f.get("user_note") for f in data["favorites"]}


def test_a_note_that_names_someone_is_not_kept(client, storage, checked):
    answer = client.patch("/api/favorites/run_mine",
                          json={"user_note": "für Max Muster", "device_id": MEIN})
    assert answer.status_code == 403
    block = answer.get_json()["safety_block"]
    assert (block["checkpoint"], block["reason_key"], block["field"]) == \
        ("intake", "personal_data", "user_note")
    assert _notes(storage)["run_mine"] == "alt"
    assert checked == [("für Max Muster", "kids", "text", "user_note")]


def test_a_note_that_passes_is_kept(client, storage, checked):
    answer = client.patch("/api/favorites/run_mine",
                          json={"user_note": "ein Haus am Meer", "device_id": MEIN})
    assert answer.status_code == 200
    assert _notes(storage)["run_mine"] == "ein Haus am Meer"


def test_no_note_asks_nothing(client, storage, checked):
    for body in ({"device_id": MEIN}, {"user_note": "", "device_id": MEIN},
                 {"user_note": "   ", "device_id": MEIN}):
        assert client.patch("/api/favorites/run_mine", json=body).status_code == 200
    assert checked == []


def test_a_favourite_whose_note_names_someone_is_not_added(client, storage, checked,
                                                           monkeypatch):
    monkeypatch.setattr(favorites_routes, "load_recorder",
                        lambda run_id, base_path=None: object())
    monkeypatch.setattr(favorites_routes, "_keeps_media", lambda recorder, media_type: True)
    answer = client.post("/api/favorites", json={
        "run_id": "run_new", "media_type": "audio", "device_id": MEIN,
        "user_note": "von Max Muster"})
    assert answer.status_code == 403
    assert answer.get_json()["safety_block"]["reason_key"] == "personal_data"
    assert "run_new" not in _notes(storage)


def test_a_note_the_check_could_not_read_is_not_kept(client, storage, monkeypatch):
    monkeypatch.setattr(favorites_routes, "check_intake",
                        lambda material, *, level, kind, field: gate.Verdict(
                            False, gate.CHECKPOINT_INTAKE, level, field,
                            gate.REASON_UNAVAILABLE, "no answer"))
    answer = client.patch("/api/favorites/run_mine",
                          json={"user_note": "ein Haus am Meer", "device_id": MEIN})
    assert answer.status_code == 403
    assert answer.get_json()["safety_block"]["reason_key"] == "unavailable"
    assert _notes(storage)["run_mine"] == "alt"


def _levels(storage):
    data = json.loads((storage / "favorites.json").read_text(encoding="utf-8"))
    return {f["run_id"]: f.get("note_level") for f in data["favorites"]}


def test_a_changed_note_keeps_the_level_it_was_written_at(client, storage, checked):
    """The chat hands a note on only where that level opens (lookup_shared_favorites)."""
    assert client.patch("/api/favorites/run_mine",
                        json={"user_note": "ein Haus am Meer", "device_id": MEIN}).status_code == 200
    assert _levels(storage)["run_mine"] == "kids"


def test_a_patch_without_a_note_leaves_its_level(client, storage, checked):
    assert client.patch("/api/favorites/run_mine", json={"device_id": MEIN}).status_code == 200
    assert _levels(storage)["run_mine"] is None


def test_a_new_favourite_keeps_the_level_of_its_note(client, storage, checked, monkeypatch):
    monkeypatch.setattr(favorites_routes, "load_recorder",
                        lambda run_id, base_path=None: object())
    monkeypatch.setattr(favorites_routes, "_keeps_media", lambda recorder, media_type: True)
    answer = client.post("/api/favorites", json={
        "run_id": "run_new", "media_type": "audio", "device_id": MEIN,
        "user_note": "ein Lied"})
    assert answer.status_code in (200, 201)
    assert _levels(storage)["run_new"] == "kids"
