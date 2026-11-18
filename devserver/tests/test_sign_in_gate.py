"""
Nothing without a sign-in, and the conditions of use agreed to with it
(docs/DEVELOPMENT_DECISIONS.md, 2026-11-15).

Covers:
- The two lists of lab/sign_in_gate.py are the decided ones, and every route
  they name exists: a route renamed or removed would leave a name that opens
  nothing, and its successor closed.
- The gate: an unnamed route answers 401 `sign_in_required` without a sign-in
  and its view never runs; a public route passes; a route of the server's own
  services passes from this machine and nowhere else; a preflight passes; a
  path no route has stays 404.
- Signed in is an account with a password that agreed to the conditions with
  this sign-in, or a place: the settings password alone, a session from before
  the agreement and a deactivated account are not signed in.
- The sign-in: an account that has not agreed to the version that stands gets
  409 `terms_required` with the version and no session; the agreement needs
  the version and a language of the frontend; it is kept as a row, once, and
  /api/auth/me names it. A new version asks again. A place agrees to nothing.
- The settings: the machine the server runs on is no admin any more; the
  settings password and a sign-in as an admin are; the lease of the card is
  open to this machine without a session and writes none.
- /exports/json/ gives out the files of a run, and nothing else in the
  directory.

Run: python3 -m pytest devserver/tests/test_sign_in_gate.py -q
"""
import ast
import datetime as _dt
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP_DB = Path(tempfile.mkdtemp(prefix="sign_in_gate_test_")) / "lab_test.db"
os.environ["AI4ARTSED_DB_PATH"] = str(_TMP_DB)

import pytest
from flask import Blueprint, Flask, jsonify

from my_app.lab.db import Base, engine, SessionLocal
from my_app.lab import models as M
from my_app.lab import sign_in_gate, terms
from my_app.lab.auth_service import hash_password
from my_app.routes.auth_routes import auth_bp
from my_app.routes.courses_routes import courses_bp
from my_app.utils.url_ids import install_row_id_converter

ROUTES_DIR = Path(__file__).resolve().parents[1] / "my_app" / "routes"


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


# Stand-ins for routes of the app, under the names the lists use, so that the
# gate decides on the endpoint as it does in the app.
_ran = []

settings_stub = Blueprint("settings", __name__, url_prefix="/api/settings")
gpu_gate_stub = Blueprint("gpu_gate", __name__, url_prefix="/api/gpu-gate")
closed_stub = Blueprint("closed", __name__, url_prefix="/api/closed")


@settings_stub.route("/safety-level")
def get_safety_level():
    _ran.append("safety")
    return jsonify(level="kids")


@gpu_gate_stub.route("/lease", methods=["POST"])
def acquire_lease():
    _ran.append("lease")
    return jsonify(ok=True)


@closed_stub.route("/runs", methods=["GET", "POST"])
def runs():
    _ran.append("runs")
    return jsonify(runs=[])


@pytest.fixture
def app():
    a = Flask(__name__)
    a.secret_key = "test-secret"
    install_row_id_converter(a)
    a.register_blueprint(auth_bp)
    a.register_blueprint(courses_bp)
    a.register_blueprint(settings_stub)
    a.register_blueprint(gpu_gate_stub)
    a.register_blueprint(closed_stub)
    sign_in_gate.install(a)
    _ran.clear()
    yield a
    SessionLocal.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_user(role, email=None, username=None, password="secret12", active=True):
    db = SessionLocal()
    u = M.User(email=email, username=username, role=role, display_name="",
               password_hash=hash_password(password), is_active=active)
    db.add(u)
    db.commit()
    return u.id


def _agree(identifier, client, password="secret12", language="de"):
    return client.post("/api/auth/login", json={
        "identifier": identifier, "password": password,
        "accept_terms": terms.TERMS_VERSION, "language": language,
    })


def _rows(user_id):
    return SessionLocal().query(M.TermsAcceptance).filter_by(user_id=user_id).all()


# ---------------------------------------------------------------------------
# The lists
# ---------------------------------------------------------------------------
def test_the_lists_are_the_decided_ones():
    """A change here is a decision about who reaches what without a sign-in:
    it is made in sign_in_gate.py with its reason, and here."""
    assert sign_in_gate.PUBLIC_ENDPOINTS == {
        "static.serve_spa",
        "auth.login",
        "auth.participant_login",
        "auth.logout",
        "auth.me",
        "settings.get_safety_level",
        "settings.get_ui_mode",
    }
    assert sign_in_gate.MACHINE_ENDPOINTS == {
        "gpu_gate.acquire_lease",
        "gpu_gate.heartbeat_lease",
        "gpu_gate.release_lease",
        "chat.chat_proxy",
        "chat.chat_models",
    }


def _endpoints_in_routes():
    """`<blueprint>.<view>` for every view a blueprint in my_app/routes
    registers with a route decorator, read from the source."""
    found = set()
    for path in sorted(ROUTES_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                    and getattr(node.value.func, "id", None) == "Blueprint"
                    and node.value.args and isinstance(node.value.args[0], ast.Constant)):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names[target.id] = node.value.args[0].value
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                call = deco if isinstance(deco, ast.Call) else None
                func = call.func if call is not None else None
                if (isinstance(func, ast.Attribute) and func.attr in ("route", "get", "post", "put", "delete", "patch")
                        and isinstance(func.value, ast.Name) and func.value.id in names):
                    found.add(f"{names[func.value.id]}.{node.name}")
    return found


def test_every_listed_route_exists():
    endpoints = _endpoints_in_routes()
    assert "auth.login" in endpoints  # the reader reads
    missing = (sign_in_gate.PUBLIC_ENDPOINTS | sign_in_gate.MACHINE_ENDPOINTS) - endpoints
    assert not missing, f"named in lab/sign_in_gate.py, found in no route: {sorted(missing)}"


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------
def test_an_unnamed_route_is_closed_without_a_sign_in(client):
    for method in ("get", "post"):
        resp = getattr(client, method)("/api/closed/runs")
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "sign_in_required"}
    assert _ran == []


def test_a_public_route_passes(client):
    assert client.get("/api/settings/safety-level").status_code == 200
    assert client.get("/api/auth/me").get_json()["user"] is None
    assert _ran == ["safety"]


def test_a_path_without_a_route_stays_404(client):
    assert client.get("/api/nowhere").status_code == 404


def test_a_preflight_passes(client):
    assert client.options("/api/closed/runs").status_code == 200
    assert _ran == []


def test_the_services_of_this_machine_pass_from_it_alone(client):
    assert client.post("/api/gpu-gate/lease").status_code == 200
    # Through the tunnel the request is from elsewhere, whatever the address.
    resp = client.post("/api/gpu-gate/lease", headers={"CF-Connecting-IP": "203.0.113.9"})
    assert resp.status_code == 401
    resp = client.post("/api/gpu-gate/lease", environ_base={"REMOTE_ADDR": "192.0.2.4"})
    assert resp.status_code == 401
    assert _ran == ["lease"]
    with client.session_transaction() as s:
        assert dict(s) == {}


@pytest.mark.parametrize("header", [
    {"CF-Ray": "8d0c0a0b0c0d0e0f-FRA"},
    {"CDN-Loop": "cloudflare"},
    {"X-Forwarded-For": "203.0.113.9"},
    {"X-Real-IP": "203.0.113.9"},
    {"Forwarded": "for=203.0.113.9"},
])
def test_a_request_through_a_proxy_is_from_elsewhere(client, header):
    """Behind the tunnel every request comes from 127.0.0.1. Where the zone
    drops CF-Connecting-IP, the other headers of the proxy still name it."""
    assert client.post("/api/gpu-gate/lease", headers=header).status_code == 401
    assert _ran == []


def test_this_machine_is_signed_in_nowhere_else(client):
    """The machine the server runs on was the first admin until 2026-11-15."""
    assert client.get("/api/closed/runs").status_code == 401


def test_an_account_that_agreed_is_signed_in(client):
    _make_user(M.Role.educator, email="edu@example.org")
    assert _agree("edu@example.org", client).status_code == 200
    assert client.get("/api/closed/runs").status_code == 200
    assert client.get("/api/auth/me").get_json()["user"]["role"] == "educator"


def test_a_session_without_the_agreement_is_not_signed_in(client):
    """A session from before 2026-11-15 carries the account and no agreement."""
    uid = _make_user(M.Role.educator, email="edu@example.org")
    assert _agree("edu@example.org", client).status_code == 200
    with client.session_transaction() as s:
        s.pop(terms.SESSION_KEY)
    assert client.get("/api/closed/runs").status_code == 401
    assert client.get("/api/auth/me").get_json()["user"] is None
    # Signing in again is enough: the agreement is kept.
    resp = client.post("/api/auth/login", json={"identifier": "edu@example.org", "password": "secret12"})
    assert resp.status_code == 200
    assert client.get("/api/closed/runs").status_code == 200
    assert len(_rows(uid)) == 1


def test_the_settings_password_alone_is_no_sign_in(client):
    _make_user(M.Role.admin, username="admin")
    with client.session_transaction() as s:
        s["settings_authenticated"] = True
    assert client.get("/api/closed/runs").status_code == 401
    assert client.get("/api/auth/me").get_json()["user"] is None


def test_a_deactivated_account_is_signed_in_no_longer(client):
    uid = _make_user(M.Role.educator, email="edu@example.org")
    assert _agree("edu@example.org", client).status_code == 200
    db = SessionLocal()
    db.get(M.User, uid).is_active = False
    db.commit()
    SessionLocal.remove()
    assert client.get("/api/closed/runs").status_code == 401


def test_the_gate_closes_where_the_sign_in_cannot_be_read(client, monkeypatch):
    _make_user(M.Role.educator, email="edu@example.org")
    assert _agree("edu@example.org", client).status_code == 200

    def broken():
        raise RuntimeError("the lab database refuses")
    monkeypatch.setattr("my_app.lab.auth_service.current_user", broken)
    assert client.get("/api/closed/runs").status_code == 401


def test_me_says_where_the_sign_in_cannot_be_read(client, monkeypatch):
    """A refusal of the lab database is no sign-out: /me says it could not
    read the sign-in, and the page keeps its own until an answer reads it."""
    _make_user(M.Role.educator, email="edu@example.org")
    assert _agree("edu@example.org", client).status_code == 200

    def broken():
        raise RuntimeError("the lab database refuses")
    monkeypatch.setattr("my_app.lab.auth_service.current_user", broken)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["user"] is None
    assert resp.get_json()["unverified"] is True
    monkeypatch.undo()
    me = client.get("/api/auth/me").get_json()
    assert me["user"] is not None
    assert "unverified" not in me


def test_a_place_is_signed_in_without_an_agreement(client):
    _make_user(M.Role.educator, email="edu@example.org")
    assert _agree("edu@example.org", client).status_code == 200
    cid = client.post("/api/courses", json={"title": "A", "safety_level": "youth"}).get_json()["course"]["id"]
    until = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=2)
    assert client.put(f"/api/courses/{cid}/access", json={"until": until.isoformat()}).status_code == 200
    code = client.post(f"/api/courses/{cid}/places", json={"count": 1}).get_json()["places"][0]["code"]

    device = client.application.test_client()
    assert device.get("/api/closed/runs").status_code == 401
    assert device.post("/api/auth/participant-login", json={"code": code}).status_code == 200
    assert device.get("/api/closed/runs").status_code == 200
    me = device.get("/api/auth/me").get_json()
    assert me["user"]["role"] == "participant"
    assert "terms" not in me


# ---------------------------------------------------------------------------
# The agreement at the sign-in
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", [M.Role.educator, M.Role.admin])
def test_the_first_sign_in_asks_for_the_agreement(client, role):
    uid = _make_user(role, username="acct")
    resp = client.post("/api/auth/login", json={"identifier": "acct", "password": "secret12"})
    assert resp.status_code == 409
    assert resp.get_json() == {"error": "terms_required", "terms_version": terms.TERMS_VERSION}
    assert client.get("/api/auth/me").get_json()["user"] is None
    assert _rows(uid) == []


def test_a_wrong_password_never_shows_the_conditions(client):
    _make_user(M.Role.educator, username="acct")
    resp = client.post("/api/auth/login", json={"identifier": "acct", "password": "wrong"})
    assert resp.status_code == 401


def test_the_agreement_names_the_version_that_stands(client):
    uid = _make_user(M.Role.educator, username="acct")
    resp = client.post("/api/auth/login", json={
        "identifier": "acct", "password": "secret12", "accept_terms": "2000-01-01", "language": "de"})
    assert resp.status_code == 409
    assert _rows(uid) == []


@pytest.mark.parametrize("language", [None, "", "xx", 7, "DE"])
def test_the_agreement_needs_a_language_of_the_frontend(client, language):
    uid = _make_user(M.Role.educator, username="acct")
    body = {"identifier": "acct", "password": "secret12", "accept_terms": terms.TERMS_VERSION}
    if language is not None:
        body["language"] = language
    assert client.post("/api/auth/login", json=body).status_code == 400
    assert _rows(uid) == []
    assert client.get("/api/auth/me").get_json()["user"] is None


def test_the_agreement_is_kept_once_and_shown(client):
    uid = _make_user(M.Role.educator, username="acct")
    resp = _agree("acct", client, language="zh-hant")
    assert resp.status_code == 200
    rows = _rows(uid)
    assert [(r.version, r.language) for r in rows] == [(terms.TERMS_VERSION, "zh-hant")]
    me = client.get("/api/auth/me").get_json()
    assert me["terms"]["version"] == terms.TERMS_VERSION
    assert me["terms"]["language"] == "zh-hant"
    agreed_at = _dt.datetime.fromisoformat(me["terms"]["accepted_at"])
    assert agreed_at.utcoffset() == _dt.timedelta(0)
    # A later sign-in on another device is asked nothing and adds nothing.
    other = client.application.test_client()
    assert other.post("/api/auth/login", json={"identifier": "acct", "password": "secret12"}).status_code == 200
    assert len(_rows(uid)) == 1


def test_a_new_version_asks_again_and_keeps_the_old_row(client, monkeypatch):
    uid = _make_user(M.Role.educator, username="acct")
    assert _agree("acct", client).status_code == 200
    monkeypatch.setattr(terms, "TERMS_VERSION", "2099-01-01")
    # The session of the old version is signed in no longer.
    assert client.get("/api/closed/runs").status_code == 401
    resp = client.post("/api/auth/login", json={"identifier": "acct", "password": "secret12"})
    assert resp.status_code == 409
    assert resp.get_json()["terms_version"] == "2099-01-01"
    assert _agree("acct", client, language="en").status_code == 200
    assert sorted(r.version for r in _rows(uid)) == ["2026-03-17", "2099-01-01"]
    assert client.get("/api/auth/me").get_json()["terms"]["version"] == "2099-01-01"


def test_a_sign_out_takes_the_agreement_of_the_session_with_it(client):
    _make_user(M.Role.educator, username="acct")
    assert _agree("acct", client).status_code == 200
    client.post("/api/auth/logout")
    with client.session_transaction() as s:
        assert terms.SESSION_KEY not in s
    assert client.get("/api/closed/runs").status_code == 401


def test_a_place_sign_in_takes_the_agreement_of_the_browser_with_it(client):
    """A leader signed in on a device that then enters as a place: the place
    is not the account that agreed."""
    _make_user(M.Role.educator, email="edu@example.org")
    assert _agree("edu@example.org", client).status_code == 200
    cid = client.post("/api/courses", json={"title": "A", "safety_level": "youth"}).get_json()["course"]["id"]
    until = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=2)
    client.put(f"/api/courses/{cid}/access", json={"until": until.isoformat()})
    code = client.post(f"/api/courses/{cid}/places", json={"count": 1}).get_json()["places"][0]["code"]
    assert client.post("/api/auth/participant-login", json={"code": code}).status_code == 200
    with client.session_transaction() as s:
        assert terms.SESSION_KEY not in s


# ---------------------------------------------------------------------------
# The settings
# ---------------------------------------------------------------------------
@pytest.fixture
def settings_app():
    """The real decorators on routes of their own, without the gate."""
    from my_app.routes.settings_routes import (
        check_auth, require_machine_or_settings_auth, require_settings_auth,
    )
    from my_app.routes.settings_routes import authenticate
    a = Flask(__name__)
    a.secret_key = "test-secret"
    install_row_id_converter(a)
    a.register_blueprint(auth_bp)
    a.register_blueprint(courses_bp)
    a.add_url_rule("/auth", "auth", authenticate, methods=["POST"])
    a.add_url_rule("/s", "s", require_settings_auth(lambda: jsonify(ok=True)))
    a.add_url_rule("/m", "m", require_machine_or_settings_auth(lambda: jsonify(ok=True)))
    a.add_url_rule("/check", "check", check_auth)
    yield a
    SessionLocal.remove()


def test_every_settings_route_needs_the_settings_but_the_named_ones():
    """The routes of the settings blueprint that a sign-in alone reaches: the
    sign-in to the settings itself, and what the header and the generations
    read on every page (filter level, interface mode, DSGVO chip, energy
    chips, progress). Everything else is the settings' own (2026-11-15: the
    backend status, the GPU info and the list of language models were open
    to every place)."""
    from my_app.routes import settings_routes as sr
    guarded = {
        sr.require_settings_auth(lambda: None).__code__,
        sr.require_machine_or_settings_auth(lambda: None).__code__,
    }
    a = Flask(__name__)
    a.register_blueprint(sr.settings_bp)
    open_to_a_sign_in = sorted(
        endpoint for endpoint, view in a.view_functions.items()
        if endpoint.startswith("settings.") and view.__code__ not in guarded)
    assert open_to_a_sign_in == [
        "settings.authenticate",
        "settings.check_auth",
        "settings.get_dsgvo_setting",
        "settings.get_generation_progress",
        "settings.get_gpu_realtime",
        "settings.get_safety_level",
        "settings.get_ui_mode",
    ]


def test_this_machine_is_no_settings_admin(settings_app):
    c = settings_app.test_client()
    assert c.get("/s").status_code == 401
    assert c.get("/check").get_json() == {"authenticated": False}
    with c.session_transaction() as s:
        assert "settings_authenticated" not in s


def test_the_settings_password_and_an_admin_sign_in_open_the_settings(settings_app):
    c = settings_app.test_client()
    with c.session_transaction() as s:
        s["settings_authenticated"] = True
    assert c.get("/s").status_code == 200

    _make_user(M.Role.admin, username="admin")
    admin = settings_app.test_client()
    assert _agree("admin", admin).status_code == 200
    elsewhere = {"REMOTE_ADDR": "192.0.2.4"}
    assert admin.get("/s", environ_base=elsewhere).status_code == 200
    assert admin.get("/check", environ_base=elsewhere).get_json() == {"authenticated": True}


def test_a_leader_sign_in_does_not_open_the_settings(settings_app):
    _make_user(M.Role.educator, username="edu")
    c = settings_app.test_client()
    assert _agree("edu", c).status_code == 200
    assert c.get("/s").status_code == 401


def test_a_leader_sign_in_ends_the_settings_of_the_browser(settings_app):
    """Somebody opened the settings with the password in this browser; a
    course leader signing in there next does not inherit them."""
    _make_user(M.Role.educator, username="edu")
    c = settings_app.test_client()
    with c.session_transaction() as s:
        s["settings_authenticated"] = True
    assert c.get("/s").status_code == 200
    assert _agree("edu", c).status_code == 200
    assert c.get("/s").status_code == 401
    with c.session_transaction() as s:
        assert "settings_authenticated" not in s


def _signed_in_place(app):
    """A device signed in with the code of a place of an open course."""
    _make_user(M.Role.educator, email="lead@example.org")
    leader = app.test_client()
    assert _agree("lead@example.org", leader).status_code == 200
    cid = leader.post("/api/courses", json={"title": "A", "safety_level": "youth"}).get_json()["course"]["id"]
    until = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=2)
    assert leader.put(f"/api/courses/{cid}/access", json={"until": until.isoformat()}).status_code == 200
    code = leader.post(f"/api/courses/{cid}/places", json={"count": 1}).get_json()["places"][0]["code"]
    device = app.test_client()
    assert device.post("/api/auth/participant-login", json={"code": code}).status_code == 200
    return device


def test_a_place_does_not_open_the_settings(settings_app):
    """A place sees what was made under its code
    (docs/DEVELOPMENT_DECISIONS.md, 2026-11-15): the settings password is not
    tried for it, and a flag in its session opens nothing."""
    device = _signed_in_place(settings_app)
    resp = device.post("/auth", json={"password": "whatever"})
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "place_cannot_open_settings"}
    with device.session_transaction() as s:
        assert "settings_authenticated" not in s
        s["settings_authenticated"] = True
    assert device.get("/s").status_code == 401
    assert device.get("/m", environ_base={"REMOTE_ADDR": "192.0.2.4"}).status_code == 401
    assert device.get("/check").get_json() == {"authenticated": False}


def test_the_lease_route_is_open_to_this_machine_and_writes_nothing(settings_app):
    c = settings_app.test_client()
    assert c.get("/m").status_code == 200
    with c.session_transaction() as s:
        assert dict(s) == {}
    assert c.get("/m", headers={"CF-Connecting-IP": "203.0.113.9"}).status_code == 401


# ---------------------------------------------------------------------------
# /exports/json/
# ---------------------------------------------------------------------------
def test_the_exports_give_out_no_file_beside_the_runs(tmp_path, monkeypatch):
    import config
    from my_app.routes.static_routes import static_bp
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", str(tmp_path))
    (tmp_path / "favorites.json").write_text('{"favorites": []}')
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "areas.json").write_text("{}")
    a = Flask(__name__)
    a.register_blueprint(static_bp)
    c = a.test_client()
    assert c.get("/exports/json/favorites.json").status_code == 404
    assert c.get("/exports/json/knowledge/areas.json").status_code == 404
