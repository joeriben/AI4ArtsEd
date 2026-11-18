"""
Tests for the Lab User/Course system — P1 (admin educators, courses) and the
places: a course admits devices through its places, each a number and a code,
while its access window is open.

Covers:
- Admin educator management is admin-gated (create/list/patch/reset/delete);
  a non-admin educator is 403 on every admin route. The account of a place is
  managed in its course: the admin routes neither rename, retype, reset nor
  delete it, and no other account takes the participant role. A participant
  account that leads no course takes no field either and may only be
  deleted; one that leads a course the admin repairs. An account the admin
  deletes leaves standing the accounts it made and the versions it wrote.
- Course CRUD + ownership gates: a foreign educator gets 403 on GET/PATCH/DELETE
  and on the places and the access window of a course they do not lead.
- Places: numbered in their course, the numbering continuing after the highest
  number; each code is in the response that makes it and nowhere else; the
  account of a place carries no email, no username and no display name.
- Entering with a code binds the session to the course and the place; case,
  spaces, hyphens and what a paste carries along are ignored; an unknown code
  is 401, a missing one 400, a closed course 403; two devices may share a
  code. The whole copied list of codes enters no place. A failed login logs
  neither the identifier nor the code.
- Malformed input is 400, never 500: a count that is no whole number, a code
  that is no string, a body that is no object, a moment without an offset or
  beyond the year 9999. An id beyond SQLite's INTEGER, in a path or a body,
  names no row: 404, and 400 for a body.
- Replacing every code of a course at once: the old codes and their
  sessions end, nothing is deleted (the places keep their numbers, accounts,
  perspectives with versions and palette entries, drafts, works and LoRA
  adapters, the leader keeps theirs, and a device entering with a new code
  reaches the same place), the places of
  other courses keep their codes, and a code drawn meanwhile is 409 with the
  old codes still entering.
- A place session ends at its next request once its code is replaced, the
  window is closed or has run out, the course is archived or deleted, the
  place is removed, or the account is deactivated or has changed its role,
  and a participant session that holds no place (the course key before) ends
  too. An ended session keeps the course's safety level until a sign-out, and
  a deleted course means the strictest; a settings-admin flag goes at the
  place login. A request whose check fails has no account and leaves the
  session for the next one, and /api/auth/me says `unverified` for it and
  for no ended session. A session passes to no account SQLite makes later
  under the id it signed in with. A place without a code gets its first
  one.
- A place reads its course without the list of places and manages nothing,
  whatever rows its account kept, and it is a member of its own course alone.
- deletion-impact counts places + works.

The whole Lab DB is redirected to a throwaway file via AI4ARTSED_DB_PATH, set
BEFORE importing the lab modules (db.py binds its engine at import time). Each
test starts from an empty schema.

Run: python3 -m pytest devserver/tests/test_lab_courses.py -q
"""
import os
import sys
import datetime as _dt
import logging
import tempfile
from pathlib import Path

# devserver/tests/test_lab_courses.py -> parents[1] == devserver/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Redirect the lab DB to a throwaway file BEFORE importing the lab package.
_TMP_DB = Path(tempfile.mkdtemp(prefix="lab_courses_test_")) / "lab_test.db"
os.environ["AI4ARTSED_DB_PATH"] = str(_TMP_DB)

import pytest
from flask import Flask

from my_app.lab.db import Base, engine, SessionLocal
from my_app.lab import models as M
from my_app.lab.auth_service import hash_password
from my_app.lab.terms import TERMS_VERSION
from my_app.lab import place_codes as PC
from my_app.routes.auth_routes import auth_bp
from my_app.routes.admin_users_routes import admin_users_bp
from my_app.routes.courses_routes import courses_bp
from my_app.utils.url_ids import install_row_id_converter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_schema():
    SessionLocal.remove()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    SessionLocal.remove()


@pytest.fixture(autouse=True)
def favorites_store_of_its_own(tmp_path, monkeypatch):
    """Deleting a course or an account removes its favorites
    (favorites_store.drop_owned), and the store must be a throwaway one here,
    never the installation's (config is read at call time)."""
    import config
    import my_app.services.favorites_store as favorites_store
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    # What drop_owned took out stays in memory for the process; ids and stamps
    # repeat between tests.
    monkeypatch.setattr(favorites_store, "_DROPPED", set())
    return tmp_path


@pytest.fixture
def app():
    a = Flask(__name__)
    a.secret_key = "test-secret"
    install_row_id_converter(a)
    a.register_blueprint(auth_bp)
    a.register_blueprint(admin_users_bp)
    a.register_blueprint(courses_bp)
    yield a
    SessionLocal.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def level(app, monkeypatch):
    """The safety level a request of a client runs under, in an installation
    set to `adult` (services/safety_level_resolver.py)."""
    import config
    from flask import jsonify
    from my_app.services.safety_level_resolver import resolve_safety_level
    app.add_url_rule("/_level", "level", lambda: jsonify(level=resolve_safety_level()))
    monkeypatch.setattr(config, "DEFAULT_SAFETY_LEVEL", "adult")
    return lambda c: c.get("/_level").get_json()["level"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_user(role, email=None, username=None, password="secret12", active=True, display=""):
    db = SessionLocal()
    u = M.User(
        email=email, username=username, role=role,
        display_name=display, password_hash=hash_password(password), is_active=active,
    )
    db.add(u)
    db.commit()
    return u.id


def _login(client, identifier, password="secret12"):
    # An account with a password signs in with its agreement to the
    # conditions of use (lab/terms.py, 2026-11-15).
    return client.post("/api/auth/login", json={"identifier": identifier, "password": password,
                                                "accept_terms": TERMS_VERSION, "language": "en"})


def _make_admin():
    return _make_user(M.Role.admin, username="admin")


def _make_educator(email="edu@example.org", username=None):
    return _make_user(M.Role.educator, email=email, username=username, display="Edu")


def _create_course(client, title="Course A", safety="youth"):
    return client.post("/api/courses", json={"title": title, "safety_level": safety})


def _setup_course(client, safety="youth"):
    """An educator signed in on `client`, with one course they own. Returns its id."""
    _make_educator()
    _login(client, "edu@example.org")
    return _create_course(client, safety=safety).get_json()["course"]["id"]


def _open(client, cid, hours=24):
    until = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=hours)
    return client.put(f"/api/courses/{cid}/access", json={"until": until.isoformat()})


def _add_places(client, cid, count=1):
    return client.post(f"/api/courses/{cid}/places", json={"count": count})


def _codes(client, cid, count=1):
    resp = _add_places(client, cid, count)
    assert resp.status_code == 201
    return [p["code"] for p in resp.get_json()["places"]]


def _enter(client, code):
    return client.post("/api/auth/participant-login", json={"code": code})


def _me(client):
    return client.get("/api/auth/me").get_json()


# ---------------------------------------------------------------------------
# A) Admin educator management — admin-gated
# ---------------------------------------------------------------------------
def test_admin_create_educator_returns_temp_password_once(client):
    _make_admin()
    _login(client, "admin")
    resp = client.post("/api/admin/users",
                       json={"email": "new@edu.org", "display_name": "New Edu"})
    assert resp.status_code == 201
    body = resp.get_json()["user"]
    assert body["role"] == "educator"
    assert body["email"] == "new@edu.org"
    assert body["temp_password"]                 # shown once
    assert "password_hash" not in body


def test_admin_create_duplicate_email_409(client):
    _make_admin()
    _login(client, "admin")
    client.post("/api/admin/users", json={"email": "dup@edu.org", "display_name": "A"})
    resp = client.post("/api/admin/users", json={"email": "dup@edu.org", "display_name": "B"})
    assert resp.status_code == 409


def test_admin_routes_require_admin(client):
    """An educator (non-admin) is 403 on every admin/users route; anon is 401."""
    _make_educator(email="edu@edu.org")
    # anonymous
    assert client.get("/api/admin/users").status_code == 401
    # educator
    _login(client, "edu@edu.org")
    assert client.get("/api/admin/users").status_code == 403
    assert client.post("/api/admin/users",
                       json={"email": "x@edu.org", "display_name": "X"}).status_code == 403


def test_admin_deactivate_and_reactivate(client):
    admin_id = _make_admin()
    _login(client, "admin")
    eid = client.post("/api/admin/users",
                      json={"email": "t@edu.org", "display_name": "T"}).get_json()["user"]["id"]
    off = client.patch(f"/api/admin/users/{eid}", json={"is_active": False})
    assert off.status_code == 200 and off.get_json()["user"]["is_active"] is False
    on = client.patch(f"/api/admin/users/{eid}", json={"is_active": True})
    assert on.get_json()["user"]["is_active"] is True


def test_admin_password_reset_returns_new_temp_password(client):
    _make_admin()
    _login(client, "admin")
    eid = client.post("/api/admin/users",
                      json={"email": "r@edu.org", "display_name": "R"}).get_json()["user"]["id"]
    resp = client.patch(f"/api/admin/users/{eid}", json={"reset_password": True})
    assert resp.status_code == 200
    new_pw = resp.get_json()["user"].get("temp_password")
    assert new_pw
    # The new password actually works for login.
    assert _login(client, "r@edu.org", new_pw).status_code == 200


def test_admin_cannot_deactivate_self(client):
    _make_admin()
    _login(client, "admin")
    me = client.get("/api/auth/me").get_json()["user"]
    resp = client.patch(f"/api/admin/users/{me['id']}", json={"is_active": False})
    assert resp.status_code == 400


def test_admin_leaves_a_place_to_its_course(client):
    """The account of a place keeps its role, carries no name and has no
    password; it goes with its course, and no other account takes its role."""
    _make_admin()
    cid = _setup_course(client)
    _codes(client, cid)
    db = SessionLocal()
    edu = db.query(M.User).filter(M.User.role == M.Role.educator).one().id
    place = db.query(M.CourseMembership).filter(M.CourseMembership.course_id == cid).one().user_id
    client.post("/api/auth/logout")
    _login(client, "admin")

    url = f"/api/admin/users/{place}"
    for body in ({"role": "educator"}, {"display_name": "Anna"}, {"reset_password": True},
                 {"is_active": False}, {"locale": "Anna, 4b"}):
        assert client.patch(url, json=body).status_code == 400
    assert client.delete(url).status_code == 400
    assert client.patch(f"/api/admin/users/{edu}", json={"role": "participant"}).status_code == 400

    SessionLocal.remove()
    db = SessionLocal()
    account = db.get(M.User, place)
    assert account.role == M.Role.participant and account.display_name == ""
    assert account.is_active and account.locale != "Anna, 4b"
    assert db.get(M.User, edu).role == M.Role.educator


def test_admin_deletes_an_educator_who_made_places(client):
    """The places stay with their course, and their accounts lose the
    pointer to the account that made them."""
    _make_admin()
    cid = _setup_course(client)
    _codes(client, cid, 2)
    db = SessionLocal()
    edu = db.query(M.User).filter(M.User.role == M.Role.educator).one().id
    client.post("/api/auth/logout")
    _login(client, "admin")
    assert client.delete(f"/api/admin/users/{edu}").status_code == 200

    SessionLocal.remove()
    db = SessionLocal()
    places = db.query(M.CourseMembership).filter(M.CourseMembership.course_id == cid).all()
    assert len(places) == 2
    assert all(db.get(M.User, p.user_id).created_by is None for p in places)


def test_admin_repairs_and_removes_a_demoted_educator(client):
    """An account with the participant role that leads a course holds no
    place (lab/db.py `_PLACE_ACCOUNT`): the admin gives it its role back or
    removes it."""
    _make_admin()
    cid = _setup_course(client)
    db = SessionLocal()
    demoted = [_make_user(M.Role.participant, email=f"{n}@example.org", display=n)
               for n in ("anna", "ben")]
    for uid in demoted:
        db.add(M.CourseEducator(course_id=cid, user_id=uid, role_in_course=M.CourseRole.co_leader))
    db.commit()
    client.post("/api/auth/logout")
    _login(client, "admin")
    first, second = (f"/api/admin/users/{uid}" for uid in demoted)
    assert client.patch(first, json={"role": "educator"}).status_code == 200
    assert client.delete(second).status_code == 200

    SessionLocal.remove()
    db = SessionLocal()
    assert db.get(M.User, demoted[0]).role == M.Role.educator
    assert db.get(M.User, demoted[1]) is None


def test_admin_names_no_participant_account_that_leads_no_course(client):
    """The migration stripped such an account of its names (lab/db.py
    `_PLACE_ACCOUNT`); no field of it takes one again, nor a role."""
    _make_admin()
    uid = _make_user(M.Role.participant)
    _login(client, "admin")
    url = f"/api/admin/users/{uid}"
    for body in ({"display_name": "Anna Beispiel, 4b"}, {"reset_password": True},
                 {"role": "admin"}, {"locale": "fr"}, {"is_active": False}):
        assert client.patch(url, json=body).status_code == 400, body
    SessionLocal.remove()
    u = SessionLocal().get(M.User, uid)
    assert (u.role, u.display_name, u.locale, u.is_active) == (M.Role.participant, "", "de", True)


def test_admin_deletes_an_admin_who_wrote_a_version_of_another_perspective(client):
    """An admin writes a version with every edit of somebody else's
    perspective (interception_prompts_routes); the version stays and loses
    its author."""
    _make_admin()
    other = _make_user(M.Role.admin, username="admin2")
    edu = _make_educator()
    db = SessionLocal()
    prompt = M.InterceptionPrompt(owner_id=edu, name="E", context_text="x")
    db.add(prompt)
    db.flush()
    version = M.PromptVersion(prompt_id=prompt.id, version_no=1, name="E",
                              context_text="x", created_by=other)
    db.add(version)
    db.commit()
    vid = version.id
    _login(client, "admin")
    assert client.delete(f"/api/admin/users/{other}").status_code == 200
    SessionLocal.remove()
    kept = SessionLocal().get(M.PromptVersion, vid)
    assert kept is not None and kept.created_by is None


def test_admin_removes_a_participant_account_that_holds_no_place(client):
    """An account with the participant role and no course: the migration
    strips its name and numbers nothing (lab/db.py `_migrate_places`)."""
    _make_admin()
    uid = _make_user(M.Role.participant)
    _login(client, "admin")
    assert client.delete(f"/api/admin/users/{uid}").status_code == 200
    SessionLocal.remove()
    assert SessionLocal().get(M.User, uid) is None


# ---------------------------------------------------------------------------
# B) Course CRUD + ownership gates
# ---------------------------------------------------------------------------
def test_create_course_makes_caller_owner(client):
    _make_educator()
    _login(client, "edu@example.org")
    resp = _create_course(client, title="My Course", safety="kids")
    assert resp.status_code == 201
    c = resp.get_json()["course"]
    assert c["name"] == "My Course"
    assert c["safety_level"] == "kids"
    assert "join_code" not in c
    assert c["place_count"] == 0
    assert c["access_until"] is None and c["access_open"] is False
    # Owner sees it in the list.
    mine = client.get("/api/courses").get_json()["courses"]
    assert any(x["id"] == c["id"] for x in mine)


def test_create_course_invalid_safety_400(client):
    _make_educator()
    _login(client, "edu@example.org")
    resp = _create_course(client, safety="grownups")
    assert resp.status_code == 400


def test_create_course_requires_educator(client, app):
    """A place may not create a course."""
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert _create_course(device).status_code == 403


def test_foreign_educator_cannot_access_course(client):
    # Owner creates a course.
    _make_educator(email="owner@edu.org")
    _login(client, "owner@edu.org")
    cid = _create_course(client).get_json()["course"]["id"]
    _add_places(client, cid)
    client.post("/api/auth/logout")

    # A different educator must not read/patch/delete it, nor touch its places
    # or its access window.
    _make_educator(email="stranger@edu.org")
    _login(client, "stranger@edu.org")
    assert client.get(f"/api/courses/{cid}").status_code == 403
    assert client.patch(f"/api/courses/{cid}", json={"title": "hijack"}).status_code == 403
    assert _add_places(client, cid).status_code == 403
    assert client.post(f"/api/courses/{cid}/places/1/code").status_code == 403
    assert client.post(f"/api/courses/{cid}/places/codes").status_code == 403
    assert _open(client, cid).status_code == 403
    assert client.delete(f"/api/courses/{cid}/access").status_code == 403
    assert client.get(f"/api/courses/{cid}/deletion-impact").status_code == 403
    assert client.delete(f"/api/courses/{cid}", json={"confirm": True}).status_code == 403
    # And it does not appear in their course list.
    assert client.get("/api/courses").get_json()["courses"] == []


def test_owner_can_patch_course(client):
    _make_educator()
    _login(client, "edu@example.org")
    cid = _create_course(client).get_json()["course"]["id"]
    resp = client.patch(f"/api/courses/{cid}", json={"safety_level": "installation", "title": "Renamed"})
    assert resp.status_code == 200
    c = resp.get_json()["course"]
    assert c["safety_level"] == "installation" and c["name"] == "Renamed"


def test_open_is_no_level_a_course_can_take(client):
    """The level open is gone (2026-11-01): neither a new course nor a changed
    one is given it."""
    _make_educator()
    _login(client, "edu@example.org")
    assert _create_course(client, safety="open").status_code == 400
    cid = _create_course(client).get_json()["course"]["id"]
    assert client.patch(f"/api/courses/{cid}", json={"safety_level": "open"}).status_code == 400


# ---------------------------------------------------------------------------
# C) Places
# ---------------------------------------------------------------------------
def test_places_are_numbered_and_their_codes_shown_once(client):
    cid = _setup_course(client)
    made = _add_places(client, cid, 3)
    assert made.status_code == 201
    places = made.get_json()["places"]
    assert [p["number"] for p in places] == [1, 2, 3]
    codes = [p["code"] for p in places]
    assert len(set(codes)) == 3
    for code in codes:
        assert len(code) == PC.CODE_LENGTH == 5
        assert set(code) <= set(PC._ALPHABET)
    assert made.get_json()["course"]["place_count"] == 3

    # The leader's view of the course lists the places, and no code.
    listed = client.get(f"/api/courses/{cid}")
    course = listed.get_json()["course"]
    assert [p["number"] for p in course["places"]] == [1, 2, 3]
    assert all(p["has_code"] and "code" not in p for p in course["places"])
    assert all(p["code_issued_at"].endswith("+00:00") for p in course["places"])
    raw = listed.get_data(as_text=True)
    assert not any(f'"{code}"' in raw for code in codes)

    # More places continue the numbering.
    more = _add_places(client, cid, 2).get_json()["places"]
    assert [p["number"] for p in more] == [4, 5]


def test_a_place_carries_no_name(client):
    cid = _setup_course(client)
    codes = _codes(client, cid, 2)
    db = SessionLocal()
    rows = db.query(M.CourseMembership).filter(M.CourseMembership.course_id == cid).all()
    assert len(rows) == 2
    for m in rows:
        assert m.user.role == M.Role.participant
        assert m.user.email is None and m.user.username is None
        assert m.user.display_name == ""
        # Only the hash of the code is kept.
        assert m.code_hash == PC.hash_code(codes[m.place_number - 1])
        assert m.code_hash not in codes


def test_place_count_is_bounded(client):
    cid = _setup_course(client)
    url = f"/api/courses/{cid}/places"
    for body in ({}, {"count": 0}, {"count": 101}, {"count": "x"},
                 {"count": True}, {"count": 2.9}, {"count": "1_0"}, {"count": " 3 "}, [1]):
        assert client.post(url, json=body).status_code == 400
    too_large = client.post(url, data='{"count": 1e400}', content_type="application/json")
    assert too_large.status_code == 400
    assert _add_places(client, cid, 100).status_code == 201


# ---------------------------------------------------------------------------
# D) Entering with a code
# ---------------------------------------------------------------------------
def test_code_login_binds_course_and_place(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    codes = _codes(client, cid, 2)
    device = app.test_client()
    resp = _enter(device, codes[1])
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user"]["role"] == "participant"
    assert body["course"]["id"] == cid
    assert body["place"] == 2
    # Session carries course_id (the exclusivity axis) and the place.
    me = _me(device)
    assert me["user"]["role"] == "participant"
    assert me["course_id"] == cid and me["place"] == 2


def test_code_login_ignores_case_spaces_and_hyphens(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    typed = f" {code[:2].lower()} -{code[2:].lower()} "
    assert _enter(app.test_client(), typed).status_code == 200


def test_code_login_ignores_what_a_paste_carries(client, app):
    """Full-width letters, a soft hyphen, a zero-width space, an en dash."""
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    wide = "".join(chr(ord(c) + 0xFEE0) for c in code)
    for typed in (wide, f"{code[:2]}­{code[2:]}", f"{code[:3]}​{code[3:]}",
                  f"{code[:2]}–{code[2:]}"):
        assert _enter(app.test_client(), typed).status_code == 200, repr(typed)


def test_code_login_takes_the_code_from_a_copied_line(client, app):
    """A line of the "Copy" text in two languages, and the marks a message
    carries around a code: a full stop, quotes, brackets, a minus sign, a
    line break."""
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    for typed in (f"Place 3: {code}", f"Platz 3: {code}", f"{code}.", f"\u201e{code}\u201c",
                  f"({code})", f"{code[:3]}\u2212{code[3:]}", f"{code}\r\n"):
        assert _enter(app.test_client(), typed).status_code == 200, repr(typed)


def test_a_pasted_list_of_codes_enters_no_place(client, app):
    """The whole "Copy" text, one line per place, and a line with two colons:
    either would enter the place its last code names."""
    cid = _setup_course(client)
    _open(client, cid)
    codes = _codes(client, cid, 3)
    listed = "\n".join(f"Place {i}: {c}" for i, c in enumerate(codes, 1))
    for typed in (listed, f"Place 1: {codes[0]}, Place 2: {codes[1]}", f"{codes[0]}\n{codes[1]}"):
        assert _enter(app.test_client(), typed).status_code == 401, repr(typed)
    r = _enter(app.test_client(), f"\n Place 2: {codes[1]} \n")
    assert r.status_code == 200 and r.get_json()["place"] == 2


def test_code_login_rejects_unknown_and_missing_codes(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, "").status_code == 400
    assert device.post("/api/auth/participant-login", json={}).status_code == 400
    wrong = next(c for c in ("AAAAA", "CCCCC") if c != code)
    resp = _enter(device, wrong)
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid_code"
    assert _enter(device, code + "A").status_code == 401
    assert _me(device)["user"] is None
    # A code that is no string, and a body that is no object.
    for body in ({"code": 12345}, {"code": True}, {"code": ["A"]}, [1], "abc", 5):
        assert device.post("/api/auth/participant-login", json=body).status_code == 400


def test_closed_course_turns_a_right_code_away(client, app):
    cid = _setup_course(client)
    code = _codes(client, cid)[0]  # the window was never opened
    device = app.test_client()
    resp = _enter(device, code)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "access_closed"
    assert _open(client, cid).status_code == 200
    assert _enter(device, code).status_code == 200


def test_two_devices_share_a_code(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    a, b = app.test_client(), app.test_client()
    assert _enter(a, code).status_code == 200
    assert _enter(b, code).status_code == 200
    assert _me(a)["place"] == _me(b)["place"] == 1


def test_password_login_refuses_a_participant_account(client):
    """A place enters with its code alone. An account with the participant
    role and a password would otherwise get a session bound to no course."""
    _make_user(M.Role.participant, username="kid1")
    assert _login(client, "kid1").status_code == 401
    assert _me(client)["user"] is None


def test_a_failed_login_names_nobody(client, caplog):
    """The field of the password login also receives a code typed into the
    wrong tab, and a password typed into the wrong field."""
    _make_educator()
    with caplog.at_level(logging.INFO):
        assert _login(client, "edu@example.org", "K7M3Q").status_code == 401
        assert _login(client, "Q7M3K", "secret12").status_code == 401
        assert _enter(client, "M3Q7K").status_code == 401
    assert "failed login" in caplog.text
    for typed in ("edu@example.org", "K7M3Q", "Q7M3K", "M3Q7K"):
        assert typed not in caplog.text


# ---------------------------------------------------------------------------
# E) When a place session ends
# ---------------------------------------------------------------------------
def test_replaced_code_ends_the_old_session_and_keeps_the_place(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    old = _codes(client, cid)[0]
    device = app.test_client()
    entered = _enter(device, old).get_json()

    resp = client.post(f"/api/courses/{cid}/places/1/code")
    assert resp.status_code == 201
    place = resp.get_json()["place"]
    new = place["code"]
    assert place["number"] == 1 and new != old

    assert _me(device)["user"] is None            # the old session ended
    assert _enter(device, old).status_code == 401
    again = _enter(device, new).get_json()
    assert again["user"]["id"] == entered["user"]["id"]   # the same place


def test_replacing_the_code_of_an_unknown_place_is_404(client):
    cid = _setup_course(client)
    assert client.post(f"/api/courses/{cid}/places/1/code").status_code == 404
    assert client.post(f"/api/courses/{cid}/places/{2**63}/code").status_code == 404


def test_a_place_without_a_code_gets_one_and_enters(client, app):
    """A roster entry the migration turned into a place has a number and no
    code (lab/db.py `_migrate_places`)."""
    cid = _setup_course(client)
    _open(client, cid)
    db = SessionLocal()
    account = M.User(role=M.Role.participant, password_hash="!")
    db.add(account)
    db.flush()
    db.add(M.CourseMembership(course_id=cid, user_id=account.id, place_number=1))
    db.commit()
    listed = client.get(f"/api/courses/{cid}").get_json()["course"]["places"]
    assert listed == [{"number": 1, "has_code": False, "code_issued_at": None}]

    code = client.post(f"/api/courses/{cid}/places/1/code").get_json()["place"]["code"]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert _me(device)["place"] == 1


def test_a_code_taken_meanwhile_is_409(client, monkeypatch):
    """Two requests that draw the same code in the same moment: the unique
    index on the hash turns the second away."""
    from sqlalchemy.exc import IntegrityError
    from my_app.routes import courses_routes as CR
    cid = _setup_course(client)
    _codes(client, cid)

    def taken(_db, _place):
        raise IntegrityError("UPDATE course_memberships", {}, Exception("UNIQUE constraint failed"))
    monkeypatch.setattr(CR, "issue_code", taken)
    assert client.post(f"/api/courses/{cid}/places/1/code").status_code == 409
    assert client.get(f"/api/courses/{cid}").get_json()["course"]["places"][0]["has_code"]


def _perspective(owner_id, name="kept"):
    db = SessionLocal()
    p = M.InterceptionPrompt(owner_id=owner_id, name=name, context_text="x")
    db.add(p)
    db.commit()
    return p.id


def _place_account(cid, number):
    return SessionLocal().query(M.CourseMembership).filter_by(
        course_id=cid, place_number=number).one().user_id


def test_replacing_all_codes_ends_every_session_and_keeps_what_the_places_saved(client, app):
    """Every place gets a new code at once and the sessions of the old codes
    end. Replacing the codes deletes nothing (2026-11-14): a place keeps its
    number, its account and what its account saved, and a device that enters
    with the new code reaches the same place; the leader's own perspectives
    and the window stay."""
    cid = _setup_course(client)
    _open(client, cid)
    old = _codes(client, cid, 3)
    device = app.test_client()
    entered = _enter(device, old[0]).get_json()
    seats = [_place_account(cid, n) for n in (1, 2, 3)]
    kept = _perspective(seats[0])
    plain = _perspective(seats[2], "no version, no palette entry")
    db = SessionLocal()
    db.add(M.PromptVersion(prompt_id=kept, version_no=1, name="kept", context_text="x"))
    db.add(M.CoursePaletteItem(course_id=cid, source_type=M.PaletteSourceType.custom,
                               prompt_id=kept))
    db.add(M.PromptDraft(owner_id=seats[1], course_id=cid, text="a draft of place 2"))
    db.add(M.Work(owner_id=seats[1], course_id=cid, run_id="a run of place 2"))
    db.add(M.LoraAdapter(file="place-2.safetensors", name="place 2", owner_id=seats[1],
                         course_id=cid))
    leader = db.query(M.User).filter_by(email="edu@example.org").one().id
    db.commit()
    own = _perspective(leader, "the leader's")

    resp = client.post(f"/api/courses/{cid}/places/codes")
    assert resp.status_code == 201
    issued = resp.get_json()["places"]
    assert [p["number"] for p in issued] == [1, 2, 3]
    assert not {p["code"] for p in issued} & set(old)

    assert _me(device)["user"] is None              # the old session ended
    for code in old:
        assert _enter(app.test_client(), code).status_code == 401
    SessionLocal.remove()
    db = SessionLocal()
    assert db.get(M.InterceptionPrompt, kept).owner_id == seats[0]
    assert db.get(M.InterceptionPrompt, plain).owner_id == seats[2]
    assert db.get(M.InterceptionPrompt, own) is not None
    assert db.query(M.PromptVersion).filter_by(prompt_id=kept).count() == 1
    assert db.query(M.CoursePaletteItem).filter_by(course_id=cid).count() == 1
    assert db.query(M.PromptDraft).filter_by(owner_id=seats[1], course_id=cid).count() == 1
    assert db.query(M.Work).filter_by(owner_id=seats[1], course_id=cid).count() == 1
    assert db.query(M.LoraAdapter).filter_by(owner_id=seats[1], course_id=cid).count() == 1
    assert [_place_account(cid, n) for n in (1, 2, 3)] == seats
    again = _enter(device, issued[0]["code"]).get_json()
    assert again["user"]["id"] == entered["user"]["id"]  # the same place
    course = client.get(f"/api/courses/{cid}").get_json()["course"]
    assert course["access_open"] and len(course["places"]) == 3


def test_replacing_all_codes_leaves_other_courses_alone(client, app):
    cid = _setup_course(client)
    other = _create_course(client, title="Course B").get_json()["course"]["id"]
    _open(client, cid)
    _open(client, other)
    _codes(client, cid)
    theirs = _codes(client, other)[0]

    assert client.post(f"/api/courses/{cid}/places/codes").status_code == 201
    assert _enter(app.test_client(), theirs).status_code == 200


def test_replacing_all_codes_of_a_course_without_places_issues_none(client):
    cid = _setup_course(client)
    resp = client.post(f"/api/courses/{cid}/places/codes")
    assert resp.status_code == 201
    assert resp.get_json()["places"] == []


def test_all_codes_taken_meanwhile_is_409_and_the_old_codes_still_enter(client, app, monkeypatch):
    """Place 1 has its new code when place 2 meets a code another request took
    in the same moment: nothing of it stands, and the old codes still enter."""
    from sqlalchemy.exc import IntegrityError
    from my_app.routes import courses_routes as CR
    cid = _setup_course(client)
    _open(client, cid)
    old = _codes(client, cid, 2)
    issue = CR.issue_code

    def taken(db, place):
        if place.place_number == 1:
            return issue(db, place)
        raise IntegrityError("UPDATE course_memberships", {}, Exception("UNIQUE constraint failed"))
    monkeypatch.setattr(CR, "issue_code", taken)
    assert client.post(f"/api/courses/{cid}/places/codes").status_code == 409
    SessionLocal.remove()
    for code in old:
        assert _enter(app.test_client(), code).status_code == 200


def test_closing_access_ends_sessions_and_reopening_admits_the_same_codes(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200

    closed = client.delete(f"/api/courses/{cid}/access")
    assert closed.status_code == 200
    assert closed.get_json()["course"]["access_open"] is False
    assert _me(device)["user"] is None
    assert _enter(device, code).status_code == 403

    _open(client, cid)
    assert _enter(device, code).status_code == 200


def test_window_running_out_ends_sessions(client, app, monkeypatch):
    cid = _setup_course(client)
    _open(client, cid, hours=1)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200

    # Fast-forward the place module's clock past the window.
    later = PC._utcnow() + _dt.timedelta(hours=2)
    monkeypatch.setattr(PC, "_utcnow", lambda: later)
    assert _me(device)["user"] is None
    resp = _enter(device, code)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "access_closed"


def test_archiving_ends_sessions(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert client.patch(f"/api/courses/{cid}", json={"archived": True}).status_code == 200
    assert _me(device)["user"] is None
    assert _enter(device, code).status_code == 403


def test_a_participant_session_without_a_place_ends(client, app):
    """A session of the course key before the places holds no place."""
    cid = _setup_course(client)
    _open(client, cid)
    _codes(client, cid)
    uid = SessionLocal().query(M.CourseMembership).filter(
        M.CourseMembership.course_id == cid).first().user_id
    device = app.test_client()
    with device.session_transaction() as s:
        s["user_id"], s["role"], s["course_id"] = uid, "participant", cid
    assert _me(device)["user"] is None
    assert device.get(f"/api/courses/{cid}").status_code == 401


def test_a_session_passes_to_no_account_made_under_its_id(client, app):
    """SQLite gives the id of the newest account, once it is deleted, to the
    next account made. The browser still signed in as the deleted educator
    reaches neither the new account nor, once that is an admin, the admin
    routes; the new account signs in as itself."""
    _make_admin()
    _login(client, "admin")
    first = client.post("/api/admin/users", json={
        "email": "first@example.org", "temp_password": "firstpw123"}).get_json()["user"]["id"]
    old = app.test_client()
    assert _login(old, "first@example.org", "firstpw123").status_code == 200
    assert client.delete(f"/api/admin/users/{first}").status_code == 200
    second = client.post("/api/admin/users", json={
        "email": "second@example.org", "temp_password": "secondpw123"}).get_json()["user"]["id"]
    assert second == first
    assert client.patch(f"/api/admin/users/{second}", json={"role": "admin"}).status_code == 200
    assert _me(old)["user"] is None
    assert old.get("/api/admin/users").status_code in (401, 403)
    new = app.test_client()
    assert _login(new, "second@example.org", "secondpw123").status_code == 200
    assert new.get("/api/admin/users").status_code == 200


def test_a_session_signed_in_before_the_account_stamp_keeps_its_account(client):
    _make_educator()
    _login(client, "edu@example.org")
    with client.session_transaction() as s:
        del s["user_stamp"]
    assert _me(client)["user"]["identifier"] == "edu@example.org"
    with client.session_transaction() as s:
        assert "user_stamp" in s
    assert _me(client)["user"]["identifier"] == "edu@example.org"


def test_a_session_that_holds_a_place_account_without_its_place_ends(client, app):
    """A role claim from before a demotion, or an id given to a new account:
    the session holds the account of a place without having entered it."""
    cid = _setup_course(client)
    _open(client, cid)
    _codes(client, cid)
    uid = SessionLocal().query(M.CourseMembership).filter(
        M.CourseMembership.course_id == cid).first().user_id
    device = app.test_client()
    with device.session_transaction() as s:
        s["user_id"], s["role"] = uid, "educator"
    assert _me(device)["user"] is None
    assert device.get(f"/api/courses/{cid}").status_code == 401


def test_a_removed_place_and_a_deactivated_account_end_the_session(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    first, second = _codes(client, cid, 2)
    a, b = app.test_client(), app.test_client()
    _enter(a, first)
    uid = _enter(b, second).get_json()["user"]["id"]
    db = SessionLocal()
    db.query(M.CourseMembership).filter(
        M.CourseMembership.course_id == cid, M.CourseMembership.place_number == 1
    ).one().status = M.MembershipStatus.removed
    db.get(M.User, uid).is_active = False
    db.commit()
    assert _me(a)["user"] is None
    assert _me(b)["user"] is None


def test_deleting_the_course_ends_the_session_under_the_strictest_level(client, app, level):
    """The session keeps a course that no longer exists, and a course the
    resolver cannot find means the strictest level."""
    cid = _setup_course(client, safety="youth")
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert level(device) == "youth"
    assert client.delete(f"/api/courses/{cid}", json={"confirm": True}).status_code == 200
    assert _me(device)["user"] is None
    assert level(device) == "kids"


def test_a_course_made_under_a_deleted_course_id_is_not_the_session_course(client, app, level):
    """SQLite gives the id of the newest course, once deleted, to the next
    course made. The ended session of a device of the deleted course stays
    under the strictest level."""
    cid = _setup_course(client, safety="kids")
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert client.delete(f"/api/courses/{cid}", json={"confirm": True}).status_code == 200
    assert _me(device)["user"] is None
    made = _create_course(client, title="Course B", safety="installation").get_json()["course"]
    assert made["id"] == cid
    assert level(device) == "kids"


def test_a_role_change_ends_the_session(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    uid = _enter(device, code).get_json()["user"]["id"]
    db = SessionLocal()
    db.get(M.User, uid).role = M.Role.educator
    db.commit()
    assert _me(device)["user"] is None
    assert _create_course(device).status_code == 401


def test_an_ended_session_keeps_the_course_level(client, app, level):
    """The device of a place stays under its course's safety level once the
    place session has ended, and falls to the installation's at a sign-out."""
    cid = _setup_course(client, safety="kids")
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert level(device) == "kids"

    assert client.delete(f"/api/courses/{cid}/access").status_code == 200
    assert _me(device)["user"] is None
    assert level(device) == "kids"

    device.post("/api/auth/logout")
    assert level(device) == "adult"


def test_an_end_inside_a_streamed_response_reaches_the_cookie(client, app):
    """A streamed response writes its cookie before its body. The check runs
    before the view, so a session that ends in a stream stays ended once the
    course is open again."""
    from flask import Response, stream_with_context
    from my_app.lab.auth_service import current_user

    def stream():
        def body():
            yield str(getattr(current_user(), "id", None))
        return Response(stream_with_context(body()))
    app.add_url_rule("/api/_stream", "stream", stream)

    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert client.delete(f"/api/courses/{cid}/access").status_code == 200
    assert device.get("/api/_stream").get_data(as_text=True) == "None"
    assert _open(client, cid).status_code == 200
    assert _me(device)["user"] is None


def test_a_place_login_drops_the_settings_flag(client, app):
    """A browser signed in to the settings enters a place: once the place
    session ends, it reaches no admin account. The settings password alone
    signs nobody in since 2026-11-15 (lab/sign_in_gate.py, `signed_in_user`);
    the flag still goes with the place login."""
    _make_admin()
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    with device.session_transaction() as s:
        s["settings_authenticated"] = True
    assert _me(device)["user"] is None
    assert _enter(device, code).status_code == 200
    with device.session_transaction() as s:
        assert "settings_authenticated" not in s
    client.delete(f"/api/courses/{cid}/access")
    assert _me(device)["user"] is None


def test_a_session_that_cannot_be_checked_has_no_account(client, app, level, monkeypatch):
    """Where the database refuses the check, the request has no account and
    runs under the course's level, and the session stays for the next
    request to check."""
    from my_app.lab import auth_service as AS
    cid = _setup_course(client, safety="kids")
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200

    def refused():
        raise RuntimeError("database is locked")
    real = AS._place_admits_session
    monkeypatch.setattr(AS, "_place_admits_session", refused)
    assert _me(device)["user"] is None
    assert device.get(f"/api/courses/{cid}").status_code == 401
    assert level(device) == "kids"

    monkeypatch.setattr(AS, "_place_admits_session", real)
    me = _me(device)
    assert me["user"]["role"] == "participant" and me["place"] == 1


def test_me_tells_an_unchecked_session_from_an_ended_one(client, app, monkeypatch):
    """A device asking whether its sign-in holds reads `unverified` where the
    database refused the check, and a plain signed-out answer once the code
    is replaced, the account is gone, or there was no session."""
    from my_app.lab import auth_service as AS
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert "unverified" not in _me(device)

    def refused():
        raise RuntimeError("database is locked")
    real = AS._place_admits_session
    monkeypatch.setattr(AS, "_place_admits_session", refused)
    me = _me(device)
    assert me["user"] is None and me["unverified"] is True

    monkeypatch.setattr(AS, "_place_admits_session", real)
    assert _me(device)["place"] == 1
    assert client.post(f"/api/courses/{cid}/places/1/code").status_code == 201
    me = _me(device)
    assert me["user"] is None and "unverified" not in me

    gone = app.test_client()
    with gone.session_transaction() as s:
        s["user_id"], s["role"] = 9999, "educator"
    me = _me(gone)
    assert me["user"] is None and "unverified" not in me
    assert "unverified" not in _me(app.test_client())


def test_educator_login_drops_the_place_binding(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert _login(device, "edu@example.org").status_code == 200
    me = _me(device)
    assert me["user"]["role"] == "educator"
    assert me["course_id"] is None and me["place"] is None


def test_educator_login_does_not_set_course_id(client):
    """An educator login must NOT auto-pin course_id (Entscheid 1)."""
    _make_educator()
    _login(client, "edu@example.org")
    me = _me(client)
    assert me["user"]["role"] == "educator"
    assert me["course_id"] is None and me["place"] is None


# ---------------------------------------------------------------------------
# F) What a place reads, and what it cannot do
# ---------------------------------------------------------------------------
def test_a_place_reads_its_course_without_the_places(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid, 2)[0]
    device = app.test_client()
    _enter(device, code)
    course = device.get(f"/api/courses/{cid}").get_json()["course"]
    assert course["id"] == cid and "places" not in course
    assert [c["id"] for c in device.get("/api/courses").get_json()["courses"]] == [cid]


def test_a_place_manages_nothing(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    _enter(device, code)
    assert _add_places(device, cid).status_code == 403
    assert device.post(f"/api/courses/{cid}/places/1/code").status_code == 403
    assert device.post(f"/api/courses/{cid}/places/codes").status_code == 403
    assert _open(device, cid).status_code == 403
    assert device.delete(f"/api/courses/{cid}/access").status_code == 403
    assert device.patch(f"/api/courses/{cid}", json={"title": "x"}).status_code == 403


def test_a_place_leads_no_course(client, app):
    """A row its account kept from before it was a place leads nothing."""
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    uid = _enter(device, code).get_json()["user"]["id"]
    db = SessionLocal()
    db.add(M.CourseEducator(course_id=cid, user_id=uid, role_in_course=M.CourseRole.owner))
    db.commit()
    assert _add_places(device, cid).status_code == 403
    assert device.post(f"/api/courses/{cid}/places/1/code").status_code == 403
    assert device.post(f"/api/courses/{cid}/places/codes").status_code == 403
    assert _open(device, cid).status_code == 403
    assert device.patch(f"/api/courses/{cid}", json={"title": "x"}).status_code == 403
    assert device.get(f"/api/courses/{cid}/deletion-impact").status_code == 403
    assert "places" not in device.get(f"/api/courses/{cid}").get_json()["course"]


def test_a_place_is_a_member_of_its_own_course_alone(client, app):
    cid = _setup_course(client)
    other = _create_course(client, title="Course B").get_json()["course"]["id"]
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    uid = _enter(device, code).get_json()["user"]["id"]
    db = SessionLocal()
    db.add(M.CourseMembership(course_id=other, user_id=uid))
    db.commit()
    assert device.get(f"/api/courses/{other}").status_code == 403
    assert device.get(f"/api/courses/{other}/palette").status_code == 403
    assert device.get(f"/api/courses/{cid}").status_code == 200
    assert [c["id"] for c in device.get("/api/courses").get_json()["courses"]] == [cid]


def test_a_membership_without_a_place_grants_nothing(client, app):
    """An educator who joined another's course with its join code, before
    the places, reads nothing of it and lists nothing."""
    cid = _setup_course(client)
    other = _make_educator(email="other@example.org")
    db = SessionLocal()
    db.add(M.CourseMembership(course_id=cid, user_id=other))
    db.commit()
    stranger = app.test_client()
    _login(stranger, "other@example.org")
    assert stranger.get(f"/api/courses/{cid}").status_code == 403
    assert stranger.get(f"/api/courses/{cid}/palette").status_code == 403
    assert stranger.get("/api/courses").get_json()["courses"] == []


def test_a_course_id_beyond_any_row_is_404(client):
    """For a leader and for the admin, on the routes of the places."""
    _make_admin()
    _setup_course(client)
    big = 2**63
    calls = (("post", f"/api/courses/{big}/places"), ("post", f"/api/courses/{big}/places/1/code"),
             ("post", f"/api/courses/{big}/places/codes"),
             ("put", f"/api/courses/{big}/access"), ("delete", f"/api/courses/{big}/access"),
             ("get", f"/api/courses/{big}"), ("delete", f"/api/courses/{big}"))
    for who in ("edu@example.org", "admin"):
        client.post("/api/auth/logout")
        _login(client, who)
        for method, path in calls:
            assert getattr(client, method)(path, json={}).status_code == 404, (who, method, path)


def test_an_id_beyond_sqlite_integer_names_no_row_on_any_path(client):
    """my_app/utils/url_ids.py: beyond 2**63 - 1 a path answers 404, and the
    user_id of a co-leader names no account."""
    _make_admin()
    cid = _setup_course(client)
    big = 2**63
    assert client.delete(f"/api/courses/{cid}/educators/{big}").status_code == 404
    assert client.patch(f"/api/courses/{cid}/palette/{big}", json={"enabled": False}).status_code == 404
    assert client.delete(f"/api/courses/{cid}/palette/{big}").status_code == 404
    assert client.post(f"/api/courses/{cid}/places/{big}/code").status_code == 404
    for uid in (big, "1", True, 0):
        assert client.post(f"/api/courses/{cid}/educators", json={"user_id": uid}).status_code == 400, uid
    client.post("/api/auth/logout")
    _login(client, "admin")
    assert client.patch(f"/api/admin/users/{big}", json={"locale": "de"}).status_code == 404
    assert client.delete(f"/api/admin/users/{big}").status_code == 404


def test_the_app_bounds_its_integers_before_the_first_blueprint():
    """create_app() installs the converter before any rule takes one."""
    source = (Path(__file__).resolve().parents[1] / "my_app" / "__init__.py").read_text()
    installed = source.index("install_row_id_converter(app)")
    assert installed < source.index("app.register_blueprint(")


def test_open_access_wants_a_moment_ahead(client):
    cid = _setup_course(client)
    url = f"/api/courses/{cid}/access"
    assert client.put(url, json={}).status_code == 400
    assert client.put(url, json={"until": "tomorrow"}).status_code == 400
    past = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=1)
    assert client.put(url, json={"until": past.isoformat()}).status_code == 400
    # A moment without an offset names a different moment in every zone.
    naive = (_dt.datetime.now() + _dt.timedelta(hours=3)).isoformat()
    assert client.put(url, json={"until": naive}).status_code == 400
    assert client.put(url, json={"until": "2031-01-01"}).status_code == 400
    assert client.put(url, json={"until": "9999-12-31T23:30:00-01:00"}).status_code == 400
    assert client.put(url, json=[1]).status_code == 400

    # A moment in another zone is kept as the same moment, in UTC.
    ahead = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=2))) + _dt.timedelta(hours=3)
    resp = client.put(url, json={"until": ahead.isoformat()})
    assert resp.status_code == 200
    course = resp.get_json()["course"]
    assert course["access_open"] is True
    stored = _dt.datetime.fromisoformat(course["access_until"])
    assert stored.utcoffset() == _dt.timedelta(0) and stored == ahead


def test_the_roster_and_the_course_key_are_gone(client):
    cid = _setup_course(client)
    assert client.post(f"/api/courses/{cid}/members", json={"username": "x"}).status_code == 404
    assert client.post(f"/api/courses/{cid}/access-key", json={}).status_code == 404
    assert client.post("/api/courses/join", json={"join_code": "ABCDEF"}).status_code == 404


# ---------------------------------------------------------------------------
# deletion-impact
# ---------------------------------------------------------------------------
def test_deletion_impact_counts_places_and_works(client):
    cid = _setup_course(client)
    _codes(client, cid, 3)

    # Add two Work rows tied to this course (directly via the model).
    db = SessionLocal()
    owner_id = db.query(M.User).filter(M.User.role == M.Role.educator).first().id
    for i in range(2):
        db.add(M.Work(owner_id=owner_id, course_id=cid, run_id=f"run{i}", config_name="cfg"))
    db.commit()

    impact = client.get(f"/api/courses/{cid}/deletion-impact").get_json()["impact"]
    assert impact["places"] == 3
    assert impact["course_works"] == 2

    # A removed membership keeps its number (lab/db.py) and is no place: the
    # preview counts the same places the course card does.
    removed = db.query(M.CourseMembership).filter(
        M.CourseMembership.course_id == cid,
        M.CourseMembership.place_number.isnot(None)).first()
    removed.status = M.MembershipStatus.removed
    db.commit()
    impact = client.get(f"/api/courses/{cid}/deletion-impact").get_json()["impact"]
    assert impact["places"] == 2


def test_delete_course_without_confirm_returns_409_with_impact(client):
    cid = _setup_course(client)
    _codes(client, cid)
    resp = client.delete(f"/api/courses/{cid}", json={})
    assert resp.status_code == 409
    assert resp.get_json()["impact"]["places"] == 1


def test_delete_course_confirmed_removes_its_places(client):
    cid = _setup_course(client)
    _codes(client, cid, 2)
    resp = client.delete(f"/api/courses/{cid}", json={"confirm": True})
    assert resp.status_code == 200
    assert resp.get_json()["deleted"]["participant_accounts_removed"] == 2
    # The accounts of the places are gone (they were in no other course).
    db = SessionLocal()
    assert db.query(M.User).filter(M.User.role == M.Role.participant).count() == 0


# ---------------------------------------------------------------------------
# G) The course a leader works in (2026-11-14): chosen in the sign-in field
#    of the header, or none, the account's own use ("Eigene Nutzung")
# ---------------------------------------------------------------------------
def _choose(client, cid):
    return client.post("/api/auth/active-course", json={"course_id": cid})


def test_a_leader_works_in_own_use_until_choosing(client, level):
    _setup_course(client, safety="kids")
    me = _me(client)
    assert me["course_id"] is None and me["course"] is None
    assert level(client) == "adult"


def test_a_chosen_course_holds_its_own_level(client, level):
    # A course entered without its stamp would run at the strictest level,
    # kids; youth shows that the course chosen is the course entered.
    cid = _setup_course(client, safety="youth")
    resp = _choose(client, cid)
    assert resp.status_code == 200
    assert resp.get_json()["course"] == {"id": cid, "name": "Course A"}
    assert _me(client)["course"] == {"id": cid, "name": "Course A"}
    assert level(client) == "youth"


def test_a_leader_returns_to_own_use(client, level):
    cid = _setup_course(client, safety="youth")
    _choose(client, cid)
    resp = _choose(client, None)
    assert resp.status_code == 200
    assert resp.get_json()["course_id"] is None
    assert resp.get_json()["course"] is None
    assert level(client) == "adult"


def test_a_leader_cannot_choose_a_course_led_by_another(client):
    cid = _setup_course(client)
    _make_educator(email="other@example.org")
    _login(client, "other@example.org")
    assert _choose(client, cid).status_code == 403
    assert _me(client)["course_id"] is None


def test_an_admin_chooses_any_course(client, app):
    cid = _setup_course(client)
    _make_admin()
    admin = app.test_client()
    _login(admin, "admin")
    assert _choose(admin, cid).status_code == 200
    assert _me(admin)["course_id"] == cid


def test_the_choice_takes_a_course_id_or_null(client):
    cid = _setup_course(client)
    assert client.post("/api/auth/active-course", json={}).status_code == 400
    assert client.post("/api/auth/active-course", data="x",
                       content_type="text/plain").status_code == 400
    for bad in (True, "1", 1.5, [cid]):
        assert _choose(client, bad).status_code == 400, bad
    for impossible in (0, -1, 2**63, 2**80):
        assert _choose(client, impossible).status_code == 404, impossible
    # An id the leader leads no course under is refused whether or not a
    # course has it: the answer tells nobody which ids exist.
    assert _choose(client, cid + 1).status_code == 403
    assert _me(client)["course_id"] is None


def test_an_admin_learns_that_no_course_has_an_id(client, app):
    cid = _setup_course(client)
    _make_admin()
    admin = app.test_client()
    _login(admin, "admin")
    assert _choose(admin, cid + 1).status_code == 404


def test_a_database_that_refuses_ends_no_request(client, app, monkeypatch):
    # The check of a chosen course runs before every request of the API; where
    # the database refuses it, the request is served and the choice stays.
    from my_app.lab import auth_service
    app.add_url_rule("/api/_ping", "ping", lambda: "ok")
    cid = _setup_course(client)
    assert _choose(client, cid).status_code == 200

    def refuse(*args, **kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(auth_service, "current_user", refuse)
    assert client.get("/api/_ping").status_code == 200
    monkeypatch.undo()
    assert _me(client)["course_id"] == cid


def test_choosing_needs_a_sign_in(client):
    assert _choose(client, None).status_code == 401


def test_a_place_cannot_choose(client, app):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert _choose(device, None).status_code == 403
    assert _choose(device, cid).status_code == 403
    assert _me(device)["course"] == {"id": cid, "name": "Course A"}


def test_the_choice_ends_when_the_account_no_longer_leads(client, app):
    cid = _setup_course(client)
    co = _make_educator(email="co@example.org")
    assert client.post(f"/api/courses/{cid}/educators", json={"user_id": co}).status_code == 201
    co_client = app.test_client()
    _login(co_client, "co@example.org")
    assert _choose(co_client, cid).status_code == 200
    assert client.delete(f"/api/courses/{cid}/educators/{co}").status_code == 200
    me = _me(co_client)
    assert me["course_id"] is None and me["course"] is None


def test_the_choice_ends_with_its_course(client, app, level):
    cid = _setup_course(client, safety="youth")
    _make_admin()
    admin = app.test_client()
    _login(admin, "admin")
    assert _choose(admin, cid).status_code == 200
    # SQLite gives the id of a deleted course to the next course made
    # (`courses.id` has no AUTOINCREMENT); the admin, who passes every
    # course, would find itself in the new one without the stamp.
    db = SessionLocal()
    made = db.get(M.Course, cid).created_at
    db.delete(db.get(M.Course, cid))
    db.commit()
    again = M.Course(name="Course B", safety_level="kids",
                     created_at=made + _dt.timedelta(minutes=1))
    db.add(again)
    db.commit()
    assert again.id == cid
    me = _me(admin)
    assert me["course_id"] is None and me["course"] is None
    assert level(admin) == "adult"


# ---------------------------------------------------------------------------
# H) Favorites follow the account of a place (2026-11-14): kept under every
#    code the place is given, kept on the device while its sign-in has ended,
#    and gone with the account
# ---------------------------------------------------------------------------
class _Run:
    """A run as the favorites routes read it, with nothing in it."""
    metadata = {}


@pytest.fixture
def favorites(app, monkeypatch, favorites_store_of_its_own):
    """The favorites routes on this app. Every run exists and keeps its piece;
    what a run holds is not what this section tests."""
    import my_app.routes.favorites_routes as FR
    monkeypatch.setattr(FR, "load_recorder", lambda run_id, base_path=None: _Run())
    monkeypatch.setattr(FR, "_keeps_media", lambda recorder, media_type: True)
    monkeypatch.setattr(FR, "_listable", lambda fav, recorder, level: True)
    app.register_blueprint(FR.favorites_bp)
    return favorites_store_of_its_own


TABLET = "tablet-07_2026-11-14"


def _star(client, run_id, device_id=TABLET):
    return client.post("/api/favorites",
                       json={"run_id": run_id, "media_type": "audio", "device_id": device_id})


def _mine(client, device_id=TABLET):
    r = client.get(f"/api/favorites?device_id={device_id}&view_mode=per_user")
    assert r.status_code == 200
    return [f["run_id"] for f in r.get_json()["favorites"]]


def _stored(store):
    import json as _json
    return {f["run_id"]: f for f in
            _json.loads((store / "favorites.json").read_text(encoding="utf-8"))["favorites"]}


def test_a_place_finds_its_favorites_under_its_new_code(client, app, favorites):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert _star(device, "run_place").status_code == 201
    assert _stored(favorites)["run_place"]["owner_id"] == _place_account(cid, 1)

    new = client.post(f"/api/courses/{cid}/places/codes").get_json()["places"][0]["code"]
    # The sign-in has ended: the device asks as a device, and the place's
    # favorite is not its own.
    assert _mine(device) == []
    assert _enter(device, new).status_code == 200
    assert _mine(device, "another-tablet_2026-11-21") == ["run_place"]


def test_a_device_whose_sign_in_has_ended_keeps_on_the_device(client, app, favorites):
    """While the course is closed the device keeps as a device without an
    account. Once the access is open again the place enters with its code and
    reaches from that device, the same day, what it kept in between."""
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert client.delete(f"/api/courses/{cid}/access").status_code == 200
    assert _star(device, "run_after").status_code == 201
    kept = _stored(favorites)["run_after"]
    assert kept["owner_id"] is None and kept["device_id"] == TABLET
    assert _mine(device) == ["run_after"]

    assert _open(client, cid).status_code == 200
    assert _enter(device, code).status_code == 200
    assert _me(device)["user"]["role"] == "participant"
    assert _mine(device) == ["run_after"]
    assert _mine(device, "another-tablet_2026-11-21") == []
    again = _star(device, "run_after")
    assert again.status_code == 409 and again.get_json()["error"] == "Favorite already exists"
    assert device.delete(f"/api/favorites/run_after?device_id={TABLET}").status_code == 200


def test_a_leader_keeps_what_the_browser_starred_before_signing_in(app, favorites):
    _make_educator()
    browser = app.test_client()
    assert _star(browser, "run_before").status_code == 201
    assert _login(browser, "edu@example.org").status_code == 200
    assert _mine(browser) == ["run_before"]
    assert _mine(browser, "another-browser_2026-11-14") == []
    assert browser.delete(f"/api/favorites/run_before?device_id={TABLET}").status_code == 200


def test_an_unchecked_place_session_changes_no_favorite(client, app, favorites, monkeypatch):
    """Where the database refuses the check of a place session, the
    favourites answer 503 and the store stays as it was."""
    from my_app.lab import auth_service as AS
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert _star(device, "run_place").status_code == 201
    before = (favorites / "favorites.json").read_text(encoding="utf-8")

    def refused():
        raise RuntimeError("database is locked")
    monkeypatch.setattr(AS, "_place_admits_session", refused)
    assert device.get(f"/api/favorites?device_id={TABLET}&view_mode=per_user").status_code == 503
    assert _star(device, "run_other").status_code == 503
    assert device.delete(f"/api/favorites/run_place?device_id={TABLET}").status_code == 503
    assert device.patch("/api/favorites/run_place",
                        json={"user_note": "x", "device_id": TABLET}).status_code == 503
    assert (favorites / "favorites.json").read_text(encoding="utf-8") == before


def test_the_settings_sign_in_keeps_under_the_admin_account(app, favorites):
    """Signed out, the browser keeps as a device again: the settings sign-in
    outlived the sign-out, and the browser kept as the admin."""
    admin = _make_admin()
    browser = app.test_client()
    with browser.session_transaction() as s:
        s["settings_authenticated"] = True
    assert _star(browser, "run_settings").status_code == 201
    kept = _stored(favorites)["run_settings"]
    assert kept["owner_id"] == admin and kept["device_id"] is None

    assert browser.post("/api/auth/logout").status_code == 200
    assert _me(browser)["user"] is None
    assert _mine(browser) == []
    assert _star(browser, "run_signed_out").status_code == 201
    kept = _stored(favorites)["run_signed_out"]
    assert kept["owner_id"] is None and kept["device_id"] == TABLET


def test_a_star_asked_while_its_course_is_deleted_is_kept_by_the_device(client, app, favorites, monkeypatch):
    """A place stars while its course is being deleted. The deletion takes
    the places' favourites before the star is written; the star is not kept
    under the account that went, and the device keeps it."""
    import threading
    import my_app.routes.favorites_routes as FR
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200

    deleted = []

    def deleted_meanwhile(run_id, base_path=None):
        # Once, while the star is out; the listing after it reads the run too.
        if deleted:
            return _Run()
        deleted.append(run_id)
        # The deletion is a request of its own, on a thread of its own as the
        # server runs it: on this thread it would share the star's `g`.
        answers = []
        worker = threading.Thread(target=lambda: answers.append(
            client.delete(f"/api/courses/{cid}", json={"confirm": True}).status_code))
        worker.start()
        worker.join()
        assert answers == [200]
        return _Run()
    monkeypatch.setattr(FR, "load_recorder", deleted_meanwhile)
    assert _star(device, "run_late").status_code == 201
    late = _stored(favorites)["run_late"]
    assert (late["owner_id"], late["owner_stamp"], late["device_id"]) == (None, None, TABLET)
    assert _mine(device) == ["run_late"]


def test_deleting_a_course_deletes_the_favorites_of_its_places(client, app, favorites):
    cid = _setup_course(client)
    _open(client, cid)
    code = _codes(client, cid)[0]
    device = app.test_client()
    assert _enter(device, code).status_code == 200
    assert _star(device, "run_place").status_code == 201
    assert _star(client, "run_leader").status_code == 201
    assert _star(app.test_client(), "run_device", "browser-3_2026-11-14").status_code == 201

    assert client.delete(f"/api/courses/{cid}", json={"confirm": True}).status_code == 200
    assert set(_stored(favorites)) == {"run_leader", "run_device"}


def test_deleting_an_account_deletes_its_favorites(client, app, favorites):
    _make_educator()
    _login(client, "edu@example.org")
    assert _star(client, "run_edu").status_code == 201
    _make_admin()
    admin = app.test_client()
    _login(admin, "admin")
    assert _star(admin, "run_admin").status_code == 201
    edu = SessionLocal().query(M.User).filter_by(email="edu@example.org").one().id
    assert admin.delete(f"/api/admin/users/{edu}").status_code == 200
    assert set(_stored(favorites)) == {"run_admin"}


def test_a_deletion_holds_the_favorites_from_its_commit_until_they_are_out(client, app, favorites, monkeypatch):
    """No star is written between the commit that deletes an account and the
    removal of its favourites: written there, it was kept under the account
    and taken out with it, and the device that sent it kept nothing."""
    import my_app.routes.courses_routes as CR
    import my_app.routes.admin_users_routes as AR
    import my_app.services.favorites_store as FS
    from sqlalchemy.orm import Session
    seen = []
    real_commit = Session.commit

    def commit(self):
        seen.append(("commit", FS._EDITING._is_owned()))
        return real_commit(self)

    def recorded(real):
        def drop(owners):
            seen.append(("drop", FS._EDITING._is_owned()))
            return real(owners)
        return drop

    monkeypatch.setattr(Session, "commit", commit)
    monkeypatch.setattr(CR, "drop_owned", recorded(CR.drop_owned))
    monkeypatch.setattr(AR, "drop_owned", recorded(AR.drop_owned))

    cid = _setup_course(client)
    _open(client, cid)
    seen.clear()
    assert client.delete(f"/api/courses/{cid}", json={"confirm": True}).status_code == 200
    assert seen[-2:] == [("commit", True), ("drop", True)]

    _make_admin()
    admin = app.test_client()
    _login(admin, "admin")
    edu = SessionLocal().query(M.User).filter_by(email="edu@example.org").one().id
    seen.clear()
    assert admin.delete(f"/api/admin/users/{edu}").status_code == 200
    assert seen[-2:] == [("commit", True), ("drop", True)]


def test_an_account_made_under_the_id_of_a_deleted_one_reaches_none_of_its_favorites(
        app, favorites, monkeypatch):
    """SQLite gives the id of a deleted account to the next account made.
    Where the favourites of the deleted one stayed in the store, the new one
    neither finds them nor removes them."""
    import my_app.routes.admin_users_routes as AU
    monkeypatch.setattr(AU, "drop_owned", lambda owners: -1)
    _make_admin()
    admin = app.test_client()
    _login(admin, "admin")
    old = _make_educator()
    edu = app.test_client()
    _login(edu, "edu@example.org")
    assert _star(edu, "run_edu").status_code == 201
    assert admin.delete(f"/api/admin/users/{old}").status_code == 200
    assert "run_edu" in _stored(favorites)

    assert _make_educator(email="new@example.org") == old
    fresh = app.test_client()
    assert _login(fresh, "new@example.org").status_code == 200
    assert _mine(fresh) == []
    assert fresh.delete(f"/api/favorites/run_edu?device_id={TABLET}").status_code == 403
