"""
Tests for the Lab User/Course system — Phase 0 (auth + seed + fail-safe init).

Covers (BAUPLAN P0 acceptance):
- Seed is idempotent (2x create_all + seed => exactly 1 admin).
- Login happy path (educator created via the model) + wrong password => 401.
- /me with and without a session.
- require_role gate (educator passes its own role; participant is 403; admin
  always passes; unauthenticated is 401).
- Settings-admin bridge (session['settings_authenticated'] => acts as admin).
- Participant-login endpoint is live under the feature (P1: real, not a 501 stub;
  since 2026-09-23 a device enters with the code of a place; validates input
  and rejects an unknown code with 401).
- Lab failure does NOT block app start: init_lab with a broken DB engine
  returns False instead of raising.

The whole Lab DB is redirected to a throwaway file via AI4ARTSED_DB_PATH, set
BEFORE importing the lab modules (db.py binds its engine at import time). Each
test starts from an empty schema.

Run: python3 -m pytest devserver/tests/test_lab_auth.py -q
(from the worktree root; also works from devserver/ directly)
"""
import os
import sys
import tempfile
from pathlib import Path

# devserver/tests/test_lab_auth.py -> parents[1] == devserver/
# Mirrors the sys.path convention used by the other devserver tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Redirect the lab DB to a throwaway file BEFORE importing the lab package,
# because my_app.lab.db creates its engine at import time from this env var.
_TMP_DB = Path(tempfile.mkdtemp(prefix="lab_test_")) / "lab_test.db"
os.environ["AI4ARTSED_DB_PATH"] = str(_TMP_DB)

import pytest
from flask import Flask

from my_app.lab.db import Base, engine, SessionLocal, init_db
from my_app.lab import models as M
from my_app.lab.auth_service import hash_password
from my_app.lab.seed import seed_admin, SETTINGS_PASSWORD_FILE
from my_app.routes.auth_routes import auth_bp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_schema():
    """Drop + recreate all tables before each test → deterministic empty DB."""
    SessionLocal.remove()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    SessionLocal.remove()


@pytest.fixture
def app():
    """Minimal Flask app carrying only the auth blueprint + a secret key."""
    a = Flask(__name__)
    a.secret_key = "test-secret"
    a.register_blueprint(auth_bp)
    yield a
    SessionLocal.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_educator(email="edu@example.org", password="secret12", active=True):
    db = SessionLocal()
    u = M.User(
        email=email,
        role=M.Role.educator,
        display_name="Edu",
        password_hash=hash_password(password),
        is_active=active,
    )
    db.add(u)
    db.commit()
    return u


# ---------------------------------------------------------------------------
# Seed idempotency
# ---------------------------------------------------------------------------
def test_seed_idempotent(monkeypatch):
    """2x create_all + seed => exactly one admin. Uses a known hash so no
    dependency on the real settings_password.key."""
    monkeypatch.setattr(
        "my_app.lab.seed.SETTINGS_PASSWORD_FILE",
        Path("/nonexistent/settings_password.key"),
    )
    init_db()
    seed_admin()
    init_db()
    seed_admin()  # second run must be a no-op

    db = SessionLocal()
    admins = db.query(M.User).filter(M.User.role == M.Role.admin).all()
    assert len(admins) == 1
    assert admins[0].username == "admin"


def test_seed_reuses_settings_hash(monkeypatch, tmp_path):
    """When settings_password.key exists, the admin reuses its hash verbatim
    (so the legacy login and the new login agree)."""
    known_hash = hash_password("mkjdU4dz8H3!F")
    keyfile = tmp_path / "settings_password.key"
    keyfile.write_text(known_hash)
    monkeypatch.setattr("my_app.lab.seed.SETTINGS_PASSWORD_FILE", keyfile)

    seed_admin()
    db = SessionLocal()
    admin = db.query(M.User).filter(M.User.role == M.Role.admin).first()
    assert admin is not None
    assert admin.password_hash == known_hash


# ---------------------------------------------------------------------------
# Login happy path + failures
# ---------------------------------------------------------------------------
def test_login_happy_path(client):
    _make_educator()
    resp = client.post("/api/auth/login", json={"identifier": "edu@example.org", "password": "secret12"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user"]["role"] == "educator"
    assert body["user"]["identifier"] == "edu@example.org"
    # No password hash must ever leak to the client.
    assert "password_hash" not in body["user"]


def test_login_wrong_password_401(client):
    _make_educator()
    resp = client.post("/api/auth/login", json={"identifier": "edu@example.org", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Invalid credentials"


def test_login_unknown_user_401(client):
    resp = client.post("/api/auth/login", json={"identifier": "nobody@example.org", "password": "whatever"})
    assert resp.status_code == 401


def test_login_inactive_user_401(client):
    _make_educator(active=False)
    resp = client.post("/api/auth/login", json={"identifier": "edu@example.org", "password": "secret12"})
    assert resp.status_code == 401


def test_login_missing_fields_400(client):
    resp = client.post("/api/auth/login", json={"identifier": "", "password": ""})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /me with / without session, and logout
# ---------------------------------------------------------------------------
def test_me_without_session(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["user"] is None


def test_me_with_session_then_logout(client):
    _make_educator()
    client.post("/api/auth/login", json={"identifier": "edu@example.org", "password": "secret12"})
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["user"]["identifier"] == "edu@example.org"

    client.post("/api/auth/logout")
    resp2 = client.get("/api/auth/me")
    assert resp2.get_json()["user"] is None


# ---------------------------------------------------------------------------
# Participant login is REAL in P1 (the P0 501 stub is gone). The places and
# their codes are covered in test_lab_courses.py; here we only assert the
# endpoint is live under the auth blueprint and validates input. (No place
# exists in this app, so any code resolves to no place -> 401.)
# ---------------------------------------------------------------------------
def test_participant_login_missing_code_400(client):
    resp = client.post("/api/auth/participant-login", json={"code": ""})
    assert resp.status_code == 400


def test_participant_login_unknown_code_401_not_501(client):
    resp = client.post("/api/auth/participant-login", json={"code": "AAAAA"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid_code"


# ---------------------------------------------------------------------------
# require_role gate
# ---------------------------------------------------------------------------
def _role_probe_app():
    """A tiny app exposing role-gated routes to exercise the decorators."""
    from my_app.lab.auth_service import require_role, require_auth
    a = Flask(__name__)
    a.secret_key = "test-secret"
    a.register_blueprint(auth_bp)

    @a.route("/probe/educator")
    @require_role(M.Role.educator)
    def _educator_only():
        return {"ok": True}

    @a.route("/probe/admin")
    @require_role(M.Role.admin)
    def _admin_only():
        return {"ok": True}

    @a.route("/probe/any")
    @require_auth
    def _any():
        return {"ok": True}

    return a


def test_require_role_unauthenticated_401():
    c = _role_probe_app().test_client()
    assert c.get("/probe/educator").status_code == 401
    assert c.get("/probe/any").status_code == 401


def test_require_role_educator_passes_own_role():
    app = _role_probe_app()
    c = app.test_client()
    _make_educator()
    c.post("/api/auth/login", json={"identifier": "edu@example.org", "password": "secret12"})
    assert c.get("/probe/educator").status_code == 200
    # Educator is NOT admin.
    assert c.get("/probe/admin").status_code == 403


def test_require_role_participant_forbidden_on_educator():
    import datetime as _dt
    from my_app.lab.place_codes import issue_code

    app = _role_probe_app()
    c = app.test_client()
    db = SessionLocal()
    course = M.Course(
        name="C", safety_level="youth",
        access_until=_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=1),
    )
    p = M.User(role=M.Role.participant, password_hash="!")
    db.add_all([course, p])
    db.flush()
    place = M.CourseMembership(course_id=course.id, user_id=p.id, place_number=1)
    db.add(place)
    db.flush()
    code = issue_code(db, place)
    db.commit()
    assert c.post("/api/auth/participant-login", json={"code": code}).status_code == 200
    assert c.get("/probe/any").status_code == 200
    assert c.get("/probe/educator").status_code == 403
    assert c.get("/probe/admin").status_code == 403


def test_require_role_admin_passes_everything():
    app = _role_probe_app()
    c = app.test_client()
    db = SessionLocal()
    a = M.User(username="admin", role=M.Role.admin, password_hash=hash_password("secret12"))
    db.add(a)
    db.commit()
    c.post("/api/auth/login", json={"identifier": "admin", "password": "secret12"})
    assert c.get("/probe/educator").status_code == 200
    assert c.get("/probe/admin").status_code == 200


# ---------------------------------------------------------------------------
# Settings-admin bridge: session['settings_authenticated'] acts as admin
# ---------------------------------------------------------------------------
def test_settings_admin_bridge_grants_admin():
    """A request already authenticated as the legacy settings-admin is treated
    as the seeded admin user — including for admin-gated routes."""
    seed_admin()  # ensure a seeded admin exists
    app = _role_probe_app()
    c = app.test_client()

    # Simulate the legacy settings login by setting its session flag directly.
    with c.session_transaction() as sess:
        sess["settings_authenticated"] = True

    assert c.get("/probe/admin").status_code == 200
    me = c.get("/api/auth/me").get_json()
    assert me["user"] is not None
    assert me["user"]["role"] == "admin"


def test_settings_admin_bridge_without_seeded_admin_is_anonymous():
    """If the flag is set but no admin row exists yet, current_user() is None
    (no crash) and admin routes stay forbidden."""
    app = _role_probe_app()
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["settings_authenticated"] = True
    assert c.get("/api/auth/me").get_json()["user"] is None
    assert c.get("/probe/admin").status_code == 401


# ---------------------------------------------------------------------------
# Fail-safe init: a broken DB must NOT block app start
# ---------------------------------------------------------------------------
def test_init_lab_failsafe_returns_false(monkeypatch):
    """init_lab swallows DB errors and returns False (server keeps starting)."""
    from my_app import lab

    def _boom():
        raise RuntimeError("simulated DB failure")

    # Patch the symbol init_lab imports lazily.
    monkeypatch.setattr("my_app.lab.db.init_db", _boom)
    a = Flask(__name__)
    a.secret_key = "test-secret"
    ok = lab.init_lab(a)
    assert ok is False  # did not raise, reported failure


def test_init_lab_success_returns_true():
    from my_app import lab
    a = Flask(__name__)
    a.secret_key = "test-secret"
    ok = lab.init_lab(a)
    assert ok is True


def test_db_module_import_with_broken_path_does_not_raise():
    """ROOT-CAUSE guard: importing my_app.lab.db with an unusable DB path must
    NOT raise at import time — otherwise the auth blueprint import (which imports
    SessionLocal at module load) would crash create_app before the fail-safe.

    Runs in a subprocess so the shared module-level engine of this test process
    is left untouched. Uses a path under /proc that cannot be mkdir'd.
    """
    import subprocess

    devserver_dir = str(Path(__file__).resolve().parents[1])
    code = (
        "import sys; sys.path.insert(0, r'%s');"
        "import my_app.lab.db as d;"
        "import my_app.routes.auth_routes as ar;"  # this is the real import chain
        "print('IMPORT_OK', ar.auth_bp.name)"
    ) % devserver_dir
    env = dict(os.environ)
    env["AI4ARTSED_DB_PATH"] = "/proc/nonexistent_ro_dir/lab.db"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert proc.returncode == 0, f"import crashed: {proc.stderr}"
    assert "IMPORT_OK" in proc.stdout
