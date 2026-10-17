"""A favorite belongs to the device that added it.

Until 2026-08-29 neither DELETE nor PATCH on /api/favorites/<run_id> looked
at the owner. Both matched on `run_id` alone, so any device could remove or
rename any other device's favorite. Only surfaces were guarded, and only
some: resona.vue carried a note saying the store's toggle "would DELETE such
a record", and worked around it locally. In `global` view mode the footer
strip deliberately shows everyone's favorites — in a workshop with twenty
tablets on one server that was a button that took something away from
someone else.

Two halves are tested here, because the hole had two halves:

1. The backend must REFUSE a foreign change (TestDelete, TestPatch).
2. The frontend must SEND the device id (TestDieOberflaecheSchickt). That is
   a source read, on purpose: `removeFavorite` had long taken a `deviceId`
   parameter, documented as "for ownership validation",
   and dropped it at the axios call. A backend test cannot see that.

Run: python3 -m pytest devserver/tests/test_favorites_ownership.py -q
"""

import json
import sys
from pathlib import Path

# devserver/tests/... -> parents[1] == devserver/ (same as test_favorites_store)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

import config
from my_app.routes.favorites_routes import favorites_bp

from file_modules import REPO

STORE_TS = REPO / "public" / "ai4artsed-frontend" / "src" / "stores" / "favorites.ts"

MEIN = "tablet-07_2026-08-29"
FREMD = "tablet-12_2026-08-29"


def _fav(run_id, device_id, note=""):
    return {
        "run_id": run_id,
        "device_id": device_id,
        "added_at": "2026-08-29T10:00:00",
        "thumbnail_url": f"/api/media/image/{run_id}/0",
        "media_type": "image",
        "user_id": "anonymous",
        "user_note": note,
        "source_view": "x2x_flow",
    }


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    """Point favorites_store at a temp dir (config is read at CALL time)."""
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    (tmp_path / "favorites.json").write_text(json.dumps({
        "version": "1.0",
        "mode": "global",
        "favorites": [
            _fav("run_mine", MEIN, "meins"),
            _fav("run_theirs", FREMD, "fremd"),
            _fav("run_orphan", None, "herrenlos"),
        ],
    }), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def client(storage):
    app = Flask(__name__)
    app.register_blueprint(favorites_bp)
    return app.test_client()


def _ids(storage):
    doc = json.loads((storage / "favorites.json").read_text(encoding="utf-8"))
    return [f["run_id"] for f in doc["favorites"]]


def _note(storage, run_id):
    doc = json.loads((storage / "favorites.json").read_text(encoding="utf-8"))
    return next(f["user_note"] for f in doc["favorites"] if f["run_id"] == run_id)


class TestDelete:
    def test_eigenes_geht(self, client, storage):
        r = client.delete(f"/api/favorites/run_mine?device_id={MEIN}")
        assert r.status_code == 200
        assert "run_mine" not in _ids(storage)

    def test_fremdes_wird_abgelehnt(self, client, storage):
        """The case that ran through until 2026-08-29."""
        r = client.delete(f"/api/favorites/run_theirs?device_id={MEIN}")
        assert r.status_code == 403
        assert "run_theirs" in _ids(storage)

    def test_ohne_device_id_wird_abgelehnt(self, client, storage):
        """No device id means: not the owner. An old client cannot delete."""
        r = client.delete("/api/favorites/run_mine")
        assert r.status_code == 403
        assert "run_mine" in _ids(storage)

    def test_herrenloses_darf_jeder(self, client, storage):
        """An entry from before per-user favorites stays removable, or it
        would stand in the strip forever with no way to take it out."""
        r = client.delete(f"/api/favorites/run_orphan?device_id={MEIN}")
        assert r.status_code == 200
        assert "run_orphan" not in _ids(storage)

    def test_unbekanntes_bleibt_404(self, client):
        """Not found comes before not yours."""
        r = client.delete(f"/api/favorites/run_gibtsnicht?device_id={MEIN}")
        assert r.status_code == 404


class TestPatch:
    def test_eigenes_geht(self, client, storage):
        r = client.patch("/api/favorites/run_mine",
                         json={"user_note": "neu", "device_id": MEIN})
        assert r.status_code == 200
        assert _note(storage, "run_mine") == "neu"

    def test_fremdes_wird_abgelehnt(self, client, storage):
        r = client.patch("/api/favorites/run_theirs",
                         json={"user_note": "uebermalt", "device_id": MEIN})
        assert r.status_code == 403
        assert _note(storage, "run_theirs") == "fremd"

    def test_device_id_auch_als_query(self, client, storage):
        """DELETE and PATCH can be called the same way."""
        r = client.patch(f"/api/favorites/run_mine?device_id={MEIN}",
                         json={"user_note": "per query"})
        assert r.status_code == 200
        assert _note(storage, "run_mine") == "per query"


class TestDieOberflaecheSchickt:
    """The other half: a backend check is worthless if the client sends
    nothing. This is what actually failed for months."""

    def test_delete_traegt_die_device_id(self):
        src = STORE_TS.read_text(encoding="utf-8")
        i = src.index("axios.delete<RemoveFavoriteResponse>")
        zeile = src[i:src.index("\n", i)]
        assert "device_id" in zeile or "${query}" in zeile, (
            "removeFavorite() takes a deviceId and drops it again at the "
            "axios call. Then the backend cannot tell whose favorite it is, "
            "and every device may delete every other device's.")
