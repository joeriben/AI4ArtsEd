"""A favorite belongs to whoever kept it: the account the session was signed
in with, or, kept without an account, the device that added it.

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

Since 2026-11-14 a favorite kept under an account belongs to the account,
as a kept perspective does (TestAccount): a place keeps its favorites under
every code it is given, a leader on every machine. The device id holds only
where no account is signed in, a sign-in that has ended included; the
listing names neither. The real sign-in of a place is tested in
test_lab_courses.py (section H).

Run: python3 -m pytest devserver/tests/test_favorites_ownership.py -q
"""

import json
import os
import re
import sys
import threading
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
# A device that kept nothing.
BARE = "tablet-30_2026-08-29"


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
def client(storage, monkeypatch):
    # What a note says is not what this file tests: the intake check passes it
    # here (test_favorites_note_intake.py tests the check).
    import my_app.routes.favorites_routes as favorites_routes
    from my_app.services import safety_gate as gate

    monkeypatch.setattr(favorites_routes, "check_intake",
                        lambda material, *, level, kind, field:
                        gate.Verdict(True, gate.CHECKPOINT_INTAKE, level, field))
    # No sign-in unless a test makes one (`sign_in`).
    monkeypatch.setattr(favorites_routes, "current_user", lambda: None)
    monkeypatch.setattr(favorites_routes, "place_session_unverified", lambda: False)
    monkeypatch.setattr(favorites_routes, "account_stamp", lambda account: account.made)
    # What drop_owned took out stays in memory for the process; each test
    # starts without.
    import my_app.services.favorites_store as favorites_store
    monkeypatch.setattr(favorites_store, "_DROPPED", set())
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

    def test_no_surface_reads_a_device_id_off_a_favorite(self):
        """Since 2026-11-14 the listing carries no device id: a favorite
        belongs to an account or a device, and the server says whether whoever
        asks may change it (`may_change`). A surface that reads a missing
        device id as 'nobody's' offers every favorite for removal."""
        src_dir = STORE_TS.parents[1]
        users = [p for p in src_dir.rglob("*")
                 if p.suffix in (".vue", ".ts") and "__tests__" not in p.parts
                 and "useFavoritesStore" in p.read_text(encoding="utf-8")]
        assert len(users) > 10, "the search for the store's users found too few"
        for path in users:
            assert not re.search(r"\.device_id\b", path.read_text(encoding="utf-8")), path

    def test_a_star_reads_whether_the_favorite_is_its_own(self):
        """Every star reads the store's `isFavorited`; in the "All" view the
        list holds other accounts' favorites, whose stars must stay dark."""
        src = STORE_TS.read_text(encoding="utf-8")
        i = src.index("const isFavorited = ")
        body = src[i:src.index("\n  }\n", i)]
        assert "may_change === true" in body


class _Account:
    """An account as `_asker` reads it: its id, and the moment it was made."""

    def __init__(self, account_id, made):
        self.id = account_id
        self.made = made


ACCOUNT = _Account(7, "2026-11-01T09:00:00+00:00")
OTHER = _Account(8, "2026-11-01T09:05:00+00:00")
# The id of ACCOUNT, given by SQLite to an account made after ACCOUNT was deleted.
LATER = _Account(7, "2026-11-14T10:00:00+00:00")


@pytest.fixture()
def sign_in(monkeypatch):
    """Who the session is: an account, none, or a place session that could
    not be checked."""
    import my_app.routes.favorites_routes as favorites_routes

    def _as(account=None, *, unchecked=False):
        monkeypatch.setattr(favorites_routes, "current_user", lambda: account)
        monkeypatch.setattr(favorites_routes, "place_session_unverified", lambda: unchecked)
    return _as


class _Run:
    """A run as the listing and the adding read it, with nothing in it."""
    metadata = {}


@pytest.fixture()
def runs(monkeypatch):
    """Every run exists and keeps its piece; what a run holds is not what this
    file tests."""
    import my_app.routes.favorites_routes as favorites_routes

    monkeypatch.setattr(favorites_routes, "resolve_safety_level", lambda: "open")
    monkeypatch.setattr(favorites_routes, "load_recorder", lambda run_id, base_path=None: _Run())
    monkeypatch.setattr(favorites_routes, "_keeps_media", lambda recorder, media_type: True)
    monkeypatch.setattr(favorites_routes, "_listable", lambda fav, recorder, level: True)
    monkeypatch.setattr(favorites_routes, "_picture_fields", lambda run_id, recorder, level: {})


def _entry(storage, run_id):
    doc = json.loads((storage / "favorites.json").read_text(encoding="utf-8"))
    return next(f for f in doc["favorites"] if f["run_id"] == run_id)


def _keep(client, device_id=MEIN):
    r = client.post("/api/favorites",
                    json={"run_id": "run_new", "media_type": "audio", "device_id": device_id})
    assert r.status_code == 201
    return r.get_json()["favorite"]


def _listed(client, device_id, view_mode="per_user"):
    r = client.get(f"/api/favorites?device_id={device_id}&view_mode={view_mode}")
    assert r.status_code == 200
    return {f["run_id"]: f for f in r.get_json()["favorites"]}


class TestAccount:
    """Since 2026-11-14 a favorite belongs to the account it was kept under."""

    def test_kept_under_the_account_and_not_the_device(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        answer = _keep(client)
        assert answer["may_change"] is True
        assert "owner_id" not in answer and "owner_stamp" not in answer
        kept = _entry(storage, "run_new")
        assert kept["owner_id"] == ACCOUNT.id
        assert kept["owner_stamp"] == ACCOUNT.made
        assert kept["device_id"] is None

    def test_the_account_finds_it_on_another_device(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        _keep(client, MEIN)
        assert list(_listed(client, BARE)) == ["run_new"]

    def test_the_device_without_the_account_does_not_find_it(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        _keep(client, MEIN)
        sign_in(None)
        assert list(_listed(client, MEIN)) == ["run_mine"]

    def test_the_account_removes_it_from_another_device(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        _keep(client, MEIN)
        r = client.delete(f"/api/favorites/run_new?device_id={FREMD}")
        assert r.status_code == 200
        assert "run_new" not in _ids(storage)

    def test_another_account_is_refused(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        _keep(client)
        sign_in(OTHER)
        assert client.delete(f"/api/favorites/run_new?device_id={MEIN}").status_code == 403
        r = client.patch("/api/favorites/run_new", json={"user_note": "fremd", "device_id": MEIN})
        assert r.status_code == 403
        assert "run_new" in _ids(storage)
        assert _note(storage, "run_new") == ""

    def test_an_account_made_later_under_the_same_id_is_refused(self, client, storage, sign_in, runs):
        """SQLite gives the id of a deleted account to the next one made."""
        sign_in(ACCOUNT)
        _keep(client)
        sign_in(LATER)
        assert "run_new" not in _listed(client, MEIN)
        assert client.delete(f"/api/favorites/run_new?device_id={MEIN}").status_code == 403
        assert "run_new" in _ids(storage)

    def test_the_same_device_without_the_account_is_refused(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        _keep(client, MEIN)
        sign_in(None)
        assert client.delete(f"/api/favorites/run_new?device_id={MEIN}").status_code == 403
        assert "run_new" in _ids(storage)

    def test_an_account_reaches_what_its_device_kept_that_day(self, client, storage, sign_in, runs):
        """A place whose sign-in had ended starred on the device, or a leader
        starred before signing in: signed in on that device the same day, it
        is theirs there, and on no other device."""
        sign_in(ACCOUNT)
        assert "run_mine" in _listed(client, MEIN)
        assert "run_mine" not in _listed(client, BARE)
        r = client.post("/api/favorites",
                        json={"run_id": "run_mine", "media_type": "image", "device_id": MEIN})
        assert r.status_code == 409
        assert r.get_json()["error"] == "Favorite already exists"
        assert client.delete(f"/api/favorites/run_mine?device_id={BARE}").status_code == 403
        assert client.delete(f"/api/favorites/run_mine?device_id={MEIN}").status_code == 200

    def test_a_run_kept_by_another_is_refused_with_its_reason(self, client, storage, sign_in, runs):
        """A run is kept once; the page that asks learns why its star stays dark."""
        sign_in(ACCOUNT)
        r = client.post("/api/favorites",
                        json={"run_id": "run_theirs", "media_type": "image", "device_id": MEIN})
        assert r.status_code == 409
        assert r.get_json()["error"] == "This run is kept by another account or device"
        assert _entry(storage, "run_theirs")["device_id"] == FREMD

    def test_an_account_may_still_remove_an_entry_without_owner(self, client, storage, sign_in):
        sign_in(ACCOUNT)
        assert client.delete(f"/api/favorites/run_orphan?device_id={MEIN}").status_code == 200

    def test_the_same_device_without_the_account_cannot_rename_it(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        _keep(client, MEIN)
        sign_in(None)
        r = client.patch("/api/favorites/run_new", json={"user_note": "x", "device_id": MEIN})
        assert r.status_code == 403
        assert _note(storage, "run_new") == ""

    def test_an_account_made_later_cannot_rename_it(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        _keep(client)
        sign_in(LATER)
        r = client.patch("/api/favorites/run_new", json={"user_note": "x", "device_id": MEIN})
        assert r.status_code == 403
        assert _note(storage, "run_new") == ""

    def test_a_request_cannot_name_the_owner_itself(self, client, storage, sign_in, runs):
        """Whose a favorite is comes from the session, never from the body."""
        sign_in(None)
        r = client.post("/api/favorites", json={
            "run_id": "run_new", "media_type": "audio", "device_id": MEIN,
            "owner_id": ACCOUNT.id, "owner_stamp": ACCOUNT.made})
        assert r.status_code == 201
        kept = _entry(storage, "run_new")
        assert kept["owner_id"] is None and kept["owner_stamp"] is None
        assert kept["device_id"] == MEIN
        sign_in(ACCOUNT)
        assert "run_new" not in _listed(client, FREMD)

    def test_an_unchecked_sign_in_is_answered_503(self, client, storage, sign_in, runs):
        before = (storage / "favorites.json").read_text(encoding="utf-8")
        sign_in(None, unchecked=True)
        assert client.get(f"/api/favorites?device_id={MEIN}").status_code == 503
        r = client.post("/api/favorites",
                        json={"run_id": "run_new", "media_type": "audio", "device_id": MEIN})
        assert r.status_code == 503
        assert client.delete(f"/api/favorites/run_mine?device_id={MEIN}").status_code == 503
        r = client.patch("/api/favorites/run_mine", json={"user_note": "x", "device_id": MEIN})
        assert r.status_code == 503
        assert client.get(f"/api/favorites/run_mine/keeper?device_id={MEIN}").status_code == 503
        assert (storage / "favorites.json").read_text(encoding="utf-8") == before

    def test_every_write_reads_and_writes_under_one_hold(self, client, storage, sign_in, runs, monkeypatch):
        """A star and the deletion of a course at once each wrote back what
        they had read, and the later one undid the earlier."""
        import my_app.routes.favorites_routes as favorites_routes
        events = _record_the_hold(monkeypatch)
        monkeypatch.setattr(favorites_routes, "load_favorites_strict",
                            _noted(events, "read", favorites_routes.load_favorites_strict))
        monkeypatch.setattr(favorites_routes, "save_favorites",
                            _noted(events, "write", favorites_routes.save_favorites))
        _keep(client)
        assert client.patch("/api/favorites/run_new",
                            json={"user_note": "x", "device_id": MEIN}).status_code == 200
        assert client.delete(f"/api/favorites/run_new?device_id={MEIN}").status_code == 200
        assert events == ["hold", "read", "write", "let go"] * 3

    def test_a_store_that_cannot_be_read_is_not_written_over(self, client, storage, sign_in, runs):
        """Read leniently, an unreadable store became the empty default, and a
        star saved a store holding that star alone."""
        (storage / "favorites.json").write_text('{"favorites": [{"run_id": "run_a"', encoding="utf-8")
        before = (storage / "favorites.json").read_text(encoding="utf-8")
        r = client.post("/api/favorites",
                        json={"run_id": "run_new", "media_type": "audio", "device_id": MEIN})
        assert r.status_code == 500
        assert client.delete(f"/api/favorites/run_a?device_id={MEIN}").status_code == 500
        assert client.patch("/api/favorites/run_a",
                            json={"user_note": "x", "device_id": MEIN}).status_code == 500
        assert (storage / "favorites.json").read_text(encoding="utf-8") == before

    def test_a_star_under_an_account_that_has_gone_is_kept_by_the_device(self, client, storage, sign_in, runs):
        """It set out before its account was deleted and reaches the store
        after drop_owned took the account's favourites out."""
        from my_app.services.favorites_store import drop_owned
        assert drop_owned([(ACCOUNT.id, ACCOUNT.made)]) == 0
        sign_in(ACCOUNT)
        r = client.post("/api/favorites",
                        json={"run_id": "run_new", "media_type": "audio", "device_id": MEIN})
        assert r.status_code == 201
        kept = _entry(storage, "run_new")
        assert (kept["owner_id"], kept["owner_stamp"], kept["device_id"]) == (None, None, MEIN)

    def test_a_star_under_an_account_that_has_gone_without_a_device_is_refused(self, client, storage, sign_in, runs):
        from my_app.services.favorites_store import drop_owned
        assert drop_owned([(ACCOUNT.id, ACCOUNT.made)]) == 0
        before = (storage / "favorites.json").read_text(encoding="utf-8")
        sign_in(ACCOUNT)
        r = client.post("/api/favorites", json={"run_id": "run_new", "media_type": "audio"})
        assert r.status_code == 401
        assert (storage / "favorites.json").read_text(encoding="utf-8") == before

    def test_an_entry_without_owner_is_kept_anew_by_whoever_stars_it(self, client, storage, sign_in, runs):
        """It predates owners, and anybody may take it back. A star takes it
        back and keeps the run under whoever stars it; nothing of the old entry
        stays, the note included."""
        sign_in(ACCOUNT)
        r = client.post("/api/favorites",
                        json={"run_id": "run_orphan", "media_type": "image", "device_id": MEIN})
        assert r.status_code == 201
        assert r.get_json()["favorite"]["may_change"] is True
        kept = _entry(storage, "run_orphan")
        assert (kept["owner_id"], kept["owner_stamp"], kept["device_id"]) == (ACCOUNT.id, ACCOUNT.made, None)
        assert kept["user_note"] == ""
        assert _ids(storage).count("run_orphan") == 1
        assert "run_orphan" in _listed(client, BARE)

    def test_a_star_from_neither_an_account_nor_a_device_is_refused(self, client, storage, runs):
        before = (storage / "favorites.json").read_text(encoding="utf-8")
        r = client.post("/api/favorites", json={"run_id": "run_new", "media_type": "audio"})
        assert r.status_code == 400
        assert (storage / "favorites.json").read_text(encoding="utf-8") == before

    def test_an_empty_store_takes_a_star(self, client, storage, sign_in, runs):
        """An empty file holds no favourites to protect."""
        for empty in ("", "  \n", "{}"):
            (storage / "favorites.json").write_text(empty, encoding="utf-8")
            _keep(client)
            assert _ids(storage) == ["run_new"]

    def test_who_keeps_a_run_is_not_told_from_a_store_that_cannot_be_read(self, client, storage):
        (storage / "favorites.json").write_text('{"favorites": [{"run_id": "run_a"', encoding="utf-8")
        assert client.get(f"/api/favorites/run_a/keeper?device_id={MEIN}").status_code == 500

    def test_who_keeps_a_run(self, client, storage, sign_in, runs):
        """A surface that writes into a run before keeping it asks first; the
        "Mine" view cannot say that somebody else keeps it."""
        def keeper(run_id, device_id=MEIN):
            r = client.get(f"/api/favorites/{run_id}/keeper?device_id={device_id}")
            assert r.status_code == 200
            return r.get_json()
        assert keeper("run_nobody") == {"kept": False, "may_change": False}
        assert keeper("run_mine") == {"kept": True, "may_change": True}
        assert keeper("run_theirs") == {"kept": True, "may_change": False}
        sign_in(ACCOUNT)
        _keep(client, MEIN)
        sign_in(OTHER)
        assert keeper("run_new", BARE) == {"kept": True, "may_change": False}
        assert "run_new" not in _listed(client, BARE)

    def test_the_listing_says_whose_without_naming_the_account(self, client, storage, sign_in, runs):
        sign_in(ACCOUNT)
        _keep(client)
        sign_in(None)
        shared = _listed(client, MEIN, "global")
        assert {k: v["may_change"] for k, v in shared.items()} == {
            "run_new": False, "run_mine": True, "run_theirs": False, "run_orphan": True}
        for entry in shared.values():
            assert "owner_id" not in entry and "owner_stamp" not in entry
            # A device id in the listing was all another page needed to take
            # that device's favorites away.
            assert "device_id" not in entry


class TestStore:
    """favorites_store: the write that replaces the store, and drop_owned,
    which runs after the accounts are deleted and raises nothing."""

    def test_a_save_leaves_no_file_beside_the_store(self, storage):
        from my_app.services.favorites_store import load_favorites, save_favorites
        assert save_favorites(load_favorites())
        assert sorted(p.name for p in storage.iterdir()) == ["favorites.json"]

    def test_a_save_that_fails_leaves_the_store_as_it_was(self, storage):
        from my_app.services.favorites_store import save_favorites
        before = (storage / "favorites.json").read_text(encoding="utf-8")
        assert save_favorites({"favorites": [object()]}) is False
        assert (storage / "favorites.json").read_text(encoding="utf-8") == before
        assert sorted(p.name for p in storage.iterdir()) == ["favorites.json"]

    def test_a_save_keeps_the_mode_of_the_store(self, storage):
        from my_app.services.favorites_store import load_favorites, save_favorites
        (storage / "favorites.json").chmod(0o640)
        assert save_favorites(load_favorites())
        assert (storage / "favorites.json").stat().st_mode & 0o777 == 0o640

    def test_a_store_that_is_a_link_is_written_where_it_points(self, storage):
        from my_app.services.favorites_store import load_favorites, save_favorites
        elsewhere = storage / "elsewhere"
        elsewhere.mkdir()
        (storage / "favorites.json").rename(elsewhere / "favorites.json")
        (storage / "favorites.json").symlink_to(elsewhere / "favorites.json")
        data = load_favorites()
        data["favorites"] = data["favorites"][:1]
        assert save_favorites(data)
        assert (storage / "favorites.json").is_symlink()
        doc = json.loads((elsewhere / "favorites.json").read_text(encoding="utf-8"))
        assert [f["run_id"] for f in doc["favorites"]] == ["run_mine"]

    def test_a_store_that_cannot_be_read_is_reported(self, storage):
        from my_app.services.favorites_store import drop_owned
        (storage / "favorites.json").write_text('{"favorites": [{"run_id": "run_a"', encoding="utf-8")
        assert drop_owned([(7, "x")]) == -1

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file of any mode")
    def test_a_store_without_read_permission_is_reported(self, storage):
        from my_app.services.favorites_store import drop_owned
        (storage / "favorites.json").chmod(0)
        try:
            assert drop_owned([(7, "x")]) == -1
        finally:
            (storage / "favorites.json").chmod(0o644)

    def test_drop_owned_reads_and_writes_under_one_hold(self, storage, monkeypatch):
        import my_app.services.favorites_store as favorites_store
        (storage / "favorites.json").write_text(json.dumps({
            "version": "1.0", "mode": "global",
            "favorites": [{"run_id": "run_a", "owner_id": 7, "owner_stamp": "x"}],
        }), encoding="utf-8")
        events = _record_the_hold(monkeypatch)
        monkeypatch.setattr(favorites_store, "load_favorites_strict",
                            _noted(events, "read", favorites_store.load_favorites_strict))
        monkeypatch.setattr(favorites_store, "save_favorites",
                            _noted(events, "write", favorites_store.save_favorites))
        assert favorites_store.drop_owned([(7, "x")]) == 1
        assert events == ["hold", "read", "write", "let go"]

    def test_a_store_that_is_no_store_is_reported(self, storage):
        from my_app.services.favorites_store import drop_owned
        (storage / "favorites.json").write_text("[]", encoding="utf-8")
        assert drop_owned([(7, "x")]) == -1
        assert (storage / "favorites.json").read_text(encoding="utf-8") == "[]"

    def test_an_entry_that_is_no_entry_stays(self, storage):
        from my_app.services.favorites_store import drop_owned
        (storage / "favorites.json").write_text(json.dumps({
            "version": "1.0", "mode": "global",
            "favorites": ["stray", {"run_id": "run_a", "owner_id": 7, "owner_stamp": "x"}],
        }), encoding="utf-8")
        assert drop_owned([(7, "x")]) == 1
        doc = json.loads((storage / "favorites.json").read_text(encoding="utf-8"))
        assert doc["favorites"] == ["stray"]

    def test_nothing_to_remove_writes_nothing(self, storage):
        from my_app.services.favorites_store import drop_owned
        path = storage / "favorites.json"
        before = (path.read_text(encoding="utf-8"), path.stat().st_mtime_ns)
        assert drop_owned([(7, "x")]) == 0
        assert (path.read_text(encoding="utf-8"), path.stat().st_mtime_ns) == before

    def test_a_failed_write_is_reported(self, storage, monkeypatch):
        import my_app.services.favorites_store as favorites_store
        (storage / "favorites.json").write_text(json.dumps({
            "version": "1.0", "mode": "global",
            "favorites": [{"run_id": "run_a", "owner_id": 7, "owner_stamp": "x"}],
        }), encoding="utf-8")
        monkeypatch.setattr(favorites_store, "save_favorites", lambda data, storage_dir=None: False)
        assert favorites_store.drop_owned([(7, "x")]) == -1


def _record_the_hold(monkeypatch):
    """Put a lock in place of the store's that notes when it is taken and let
    go (favorites_store.editing reads the lock at call time)."""
    import my_app.services.favorites_store as favorites_store

    events = []

    class _Recording:
        def __init__(self):
            self.lock = threading.RLock()

        def __enter__(self):
            self.lock.acquire()
            events.append("hold")

        def __exit__(self, *exc):
            events.append("let go")
            self.lock.release()

    monkeypatch.setattr(favorites_store, "_EDITING", _Recording())
    return events


def _noted(events, name, real):
    def call(*args, **kwargs):
        events.append(name)
        return real(*args, **kwargs)
    return call
