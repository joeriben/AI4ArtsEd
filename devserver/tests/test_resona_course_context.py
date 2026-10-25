"""
Tests for Phase P-R: Resona sees the ACTIVE COURSE as factual context.

Covers (the course block carries metadata and the group size, and explicitly
NO participant names; since 2026-09-23 a course admits places, which carry
none):
  - Place session with a course -> the composed Resona system prompt carries a
    GIVEN-COURSE block with the course title + the number of places ("N
    places"), and NEVER the code of a place (fixture has 2
    places; both codes asserted absent).
  - A place's CLIENT-supplied course_id that differs from its pinned session
    course is IGNORED — the server session course wins.
  - Educator + own course -> block present; educator + FOREIGN course -> no
    block and no error in the chat flow.
  - Anonymous (no Lab login) -> no block; existing Resona prompt is unchanged.
  - Lab DB broken (monkeypatched) -> no block, no crash (fail-safe).

The system prompt is composed by chat_routes.build_system_prompt(), which reads
the Flask session via the lab auth_service (current_user / current_course_id).
We exercise the REAL session path by mounting a tiny test-only route that calls
build_system_prompt() inside a normal request, and driving it through the Flask
test client whose session is established by the real login flows (the code of
a place / educator password login). This mirrors production exactly:
one request per call, current_user() re-resolved from the session each time.

The Lab DB is redirected to a throwaway file via AI4ARTSED_DB_PATH, set BEFORE
importing the lab modules (db.py binds its engine at import time), exactly like
test_lab_courses.py.

Run: python3 -m pytest devserver/tests/test_resona_course_context.py -q
"""
import datetime as _dt
import os
import sys
import tempfile
from pathlib import Path

# devserver/tests/test_resona_course_context.py -> parents[1] == devserver/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Redirect the lab DB to a throwaway file BEFORE importing the lab package.
_TMP_DB = Path(tempfile.mkdtemp(prefix="resona_course_ctx_test_")) / "lab_test.db"
os.environ["AI4ARTSED_DB_PATH"] = str(_TMP_DB)

import pytest
from flask import Flask, request, jsonify

from my_app.lab.db import Base, engine, SessionLocal
from my_app.lab import models as M
from my_app.lab.auth_service import hash_password
from my_app.lab.place_codes import issue_code
from my_app.routes.auth_routes import auth_bp
from my_app.routes.admin_users_routes import admin_users_bp
from my_app.routes.courses_routes import courses_bp
from my_app.routes import chat_routes


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


@pytest.fixture
def app():
    a = Flask(__name__)
    a.secret_key = "test-secret"
    a.register_blueprint(auth_bp)
    a.register_blueprint(admin_users_bp)
    a.register_blueprint(courses_bp)

    # Test-only endpoint: compose the Resona system prompt in a real request so
    # build_system_prompt() sees the live Flask session (current_user / course).
    @a.route("/__test__/resona_prompt", methods=["POST"])
    def _resona_prompt():
        ctx = (request.get_json(silent=True) or {}).get("context") or {}
        prompt = chat_routes.build_system_prompt(ctx, language="en")
        return jsonify({"prompt": prompt})

    yield a
    SessionLocal.remove()


@pytest.fixture
def client(app):
    return app.test_client()


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


def _make_course(name="Season Studio", safety="youth", description=""):
    """A course whose access window is open for the next hour."""
    db = SessionLocal()
    c = M.Course(
        name=name, safety_level=safety, description=description,
        access_until=_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=1),
    )
    db.add(c)
    db.commit()
    return c.id


def _add_educator(course_id, user_id, role=M.CourseRole.owner):
    db = SessionLocal()
    db.add(M.CourseEducator(course_id=course_id, user_id=user_id, role_in_course=role))
    db.commit()


def _add_place(course_id):
    """Add the next place to the course, as the places route does; return its code."""
    db = SessionLocal()
    number = 1 + max(
        (m.place_number or 0 for m in db.query(M.CourseMembership).filter(
            M.CourseMembership.course_id == course_id)),
        default=0,
    )
    u = M.User(role=M.Role.participant, password_hash="!")
    db.add(u)
    db.flush()
    place = M.CourseMembership(course_id=course_id, user_id=u.id, place_number=number)
    db.add(place)
    db.flush()
    code = issue_code(db, place)
    db.commit()
    return code


def _login_educator(client, email, password="secret12"):
    r = client.post("/api/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.get_json()


def _participant_login(client, code):
    return client.post("/api/auth/participant-login", json={"code": code})


def _prompt(client, context):
    r = client.post("/__test__/resona_prompt", json={"context": context})
    assert r.status_code == 200
    return r.get_json()["prompt"]


# ===========================================================================
# 1) Place session with a course -> GIVEN-COURSE block, NO codes
# ===========================================================================
def test_participant_session_injects_course_block_without_codes(client):
    course_id = _make_course(name="Season Studio", safety="youth")
    # Two places -> group size 2; their codes must never surface in the prompt.
    code = _add_place(course_id)
    other = _add_place(course_id)

    r = _participant_login(client, code)
    assert r.status_code == 200, r.get_json()

    prompt = _prompt(client, {"resona_mode": True})

    assert "GIVEN-COURSE:" in prompt
    assert 'course "Season Studio"' in prompt
    assert "youth group, 2 places." in prompt
    assert "participants remain unnamed here" in prompt

    # The core grant boundary: no code of a place anywhere in the prompt.
    for needle in (code, other):
        assert needle not in prompt, f"place code leaked into prompt: {needle!r}"


def test_participant_block_reports_phase_notes_from_description(client):
    course_id = _make_course(
        name="Sound Lab", safety="kids",
        description="Phase 2 of 3 — moving from sketches to a soundscape.",
    )
    code = _add_place(course_id)
    assert _participant_login(client, code).status_code == 200

    prompt = _prompt(client, {"resona_mode": True})
    assert "GIVEN-COURSE:" in prompt
    assert "kids group, 1 place." in prompt
    assert "Phase/notes: Phase 2 of 3 — moving from sketches to a soundscape." in prompt


# ===========================================================================
# 2) Place: client course_id != session course -> session wins
# ===========================================================================
def test_participant_client_course_id_is_ignored(client):
    real_course = _make_course(name="Real Room", safety="youth")
    other_course = _make_course(name="Other Room", safety="open")
    code = _add_place(real_course)
    # Give the OTHER course a distinctive number of places (3) to detect leakage.
    for _ in range(3):
        _add_place(other_course)
    assert _participant_login(client, code).status_code == 200

    # Client tries to point Resona at the OTHER course; the server must ignore it.
    prompt = _prompt(client, {"resona_mode": True, "course_id": other_course})

    assert 'course "Real Room"' in prompt
    assert "Other Room" not in prompt
    assert "3 places" not in prompt
    assert "youth group, 1 place." in prompt


# ===========================================================================
# 3) Educator: own course -> block; foreign course -> no block, no error
# ===========================================================================
def test_educator_own_course_injects_block(client):
    edu = _make_user(M.Role.educator, email="edu@example.org", display="Edu")
    course_id = _make_course(name="Studio One", safety="open")
    _add_educator(course_id, edu, role=M.CourseRole.owner)
    _add_place(course_id)
    _login_educator(client, "edu@example.org")

    prompt = _prompt(client, {"resona_mode": True, "course_id": course_id})
    assert "GIVEN-COURSE:" in prompt
    assert 'course "Studio One"' in prompt
    # one place and exactly one educator, both singular
    assert "open group, 1 place, 1 educator." in prompt


def test_the_course_line_counts_places_alone(client):
    """The whole line: no place yet, two educators, and a membership that is
    no place (an educator on the roster before the places, lab/db.py
    `_migrate_places`), which is not counted."""
    edu = _make_user(M.Role.educator, email="edu4@example.org", display="Edu4")
    co = _make_user(M.Role.educator, email="co@example.org", display="Co")
    course_id = _make_course(name="Studio Two", safety="kids")
    _add_educator(course_id, edu, role=M.CourseRole.owner)
    _add_educator(course_id, co, role=M.CourseRole.co_leader)
    db = SessionLocal()
    db.add(M.CourseMembership(course_id=course_id, user_id=co))
    db.commit()
    _login_educator(client, "edu4@example.org")

    prompt = _prompt(client, {"resona_mode": True, "course_id": course_id})
    start = prompt.index("GIVEN-COURSE:")
    assert prompt[start:].startswith(
        'GIVEN-COURSE: You are working within the course "Studio Two" — '
        'kids group, 0 places, 2 educators. This is factual context for your '
        'planning and counsel; participants remain unnamed here.'
    )


def test_educator_foreign_course_no_block_no_error(client):
    edu = _make_user(M.Role.educator, email="edu2@example.org", display="Edu2")
    other_owner = _make_user(M.Role.educator, email="owner@example.org", display="Owner")
    foreign = _make_course(name="Not Mine", safety="youth")
    _add_educator(foreign, other_owner, role=M.CourseRole.owner)
    _add_place(foreign)
    _login_educator(client, "edu2@example.org")

    prompt = _prompt(client, {"resona_mode": True, "course_id": foreign})
    # No leak of the foreign course, and the request still produced a valid prompt.
    assert "GIVEN-COURSE:" not in prompt
    assert "Not Mine" not in prompt
    # normal Resona prompt still composed. Marker is a core section, not a
    # self-description: the prompt states the situation, not a character.
    assert "INTERNAL EVIDENCE DUTY" in prompt


def test_educator_no_active_course_no_block(client):
    edu = _make_user(M.Role.educator, email="edu3@example.org", display="Edu3")
    _login_educator(client, "edu3@example.org")
    # No course_id in context -> presets-only, no block.
    prompt = _prompt(client, {"resona_mode": True})
    assert "GIVEN-COURSE:" not in prompt
    assert "INTERNAL EVIDENCE DUTY" in prompt


# ===========================================================================
# 4) Anonymous -> no block; Resona prompt unchanged
# ===========================================================================
def test_anonymous_session_no_block(client):
    prompt = _prompt(client, {"resona_mode": True})
    assert "GIVEN-COURSE:" not in prompt
    # Baseline Resona prompt is intact (GIVEN NOW + persona still present).
    assert "INTERNAL EVIDENCE DUTY" in prompt
    assert "GIVEN NOW:" in prompt


def test_non_resona_mode_never_injects_course_block(client):
    """Course context is Resona-only: a session-mode prompt gets no block even
    if a course_id is supplied (defensive — build_system_prompt only calls the
    helper on the resona_mode branch)."""
    course_id = _make_course(name="Season Studio", safety="youth")
    assert _participant_login(client, _add_place(course_id)).status_code == 200

    prompt = _prompt(client, {"course_id": course_id, "media_type": "image"})
    assert "GIVEN-COURSE:" not in prompt


# ===========================================================================
# 5) Lab DB broken -> no block, no crash (fail-safe)
# ===========================================================================
def test_lab_db_broken_is_failsafe(client, monkeypatch):
    course_id = _make_course(name="Season Studio", safety="youth")
    assert _participant_login(client, _add_place(course_id)).status_code == 200

    # Simulate a DB outage AFTER login: the helper imports SessionLocal lazily
    # from my_app.lab.db at call time, so patching that attribute makes every
    # session acquisition inside the helper raise. build_system_prompt must
    # swallow it (log line) and compose the prompt without a course block.
    import my_app.lab.db as lab_db

    def _boom(*a, **k):
        raise RuntimeError("lab db unavailable")

    monkeypatch.setattr(lab_db, "SessionLocal", _boom, raising=True)

    prompt = _prompt(client, {"resona_mode": True})
    # No block, but a fully-composed, working Resona prompt.
    assert "GIVEN-COURSE:" not in prompt
    assert "INTERNAL EVIDENCE DUTY" in prompt


# ===========================================================================
# 7) resona_situation: server-side derivation when the page declares nothing
#    (educator/admin without an active course -> consulting; everyone else,
#    and every failure mode, stays in the workshop frame)
# ===========================================================================
def test_educator_without_course_gets_planning_block(client):
    _make_user(M.Role.educator, email="teach@example.org")
    _login_educator(client, "teach@example.org")
    p = _prompt(client, {"resona_mode": True})
    assert "THE PLANNING SITUATION" in p
    assert "THE WORKSHOP SITUATION" not in p


def test_educator_with_active_course_stays_workshop(client):
    uid = _make_user(M.Role.educator, email="teach@example.org")
    cid = _make_course()
    _add_educator(cid, uid)
    _login_educator(client, "teach@example.org")
    p = _prompt(client, {"resona_mode": True, "course_id": cid})
    assert "THE WORKSHOP SITUATION" in p
    assert "THE PLANNING SITUATION" not in p


def test_admin_without_course_gets_planning_block(client):
    _make_user(M.Role.admin, email="root@example.org")
    _login_educator(client, "root@example.org")
    p = _prompt(client, {"resona_mode": True})
    assert "THE PLANNING SITUATION" in p


def test_participant_session_stays_workshop(client):
    cid = _make_course()
    r = _participant_login(client, _add_place(cid))
    assert r.status_code == 200
    p = _prompt(client, {"resona_mode": True})
    assert "THE WORKSHOP SITUATION" in p
    assert "THE PLANNING SITUATION" not in p


def test_anonymous_stays_workshop(client):
    p = _prompt(client, {"resona_mode": True})
    assert "THE WORKSHOP SITUATION" in p
    assert "THE PLANNING SITUATION" not in p


def test_explicit_declaration_wins_over_derivation(client):
    _make_user(M.Role.educator, email="teach@example.org")
    _login_educator(client, "teach@example.org")
    p = _prompt(client, {"resona_mode": True, "resona_situation": "workshop"})
    assert "THE WORKSHOP SITUATION" in p
    assert "THE PLANNING SITUATION" not in p


# ===========================================================================
# 8) GIVEN LIBRARY: dynamische Bestandskarte im Resona-Prompt (fail-safe)
# ===========================================================================
def test_given_library_block_appears_when_scope_present(client, monkeypatch):
    from my_app.services import knowledge_library as KL
    monkeypatch.setattr(
        KL, "scope_summary",
        lambda: "GIVEN LIBRARY: 2 published titles on this house's shelf. Sparten: Test (2).",
    )
    p = _prompt(client, {"resona_mode": True})
    assert "GIVEN LIBRARY: 2 published titles" in p


def test_given_library_failsafe_on_error(client, monkeypatch):
    from my_app.services import knowledge_library as KL

    def boom():
        raise RuntimeError("index broken")

    monkeypatch.setattr(KL, "scope_summary", boom)
    p = _prompt(client, {"resona_mode": True})
    assert "THE WORKSHOP SITUATION" in p
    assert "GIVEN LIBRARY:" not in p
