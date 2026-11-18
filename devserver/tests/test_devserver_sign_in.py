"""
The sign-in of the scripts that call the DevServer
(devserver/scripts/devserver_sign_in.py, 2026-11-15).

Against a real HTTP server on this machine, as the scripts call it: the
script signs in from the environment and reaches a route behind the gate,
also where the server marks its cookie Secure, as production does, and the
script calls http://localhost. An account that has not agreed to the
conditions is told to sign in in the browser; a missing sign-in is said
before anything is sent.

Run: python3 -m pytest devserver/tests/test_devserver_sign_in.py -q
"""
import asyncio
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

_TMP_DB = Path(tempfile.mkdtemp(prefix="devserver_sign_in_test_")) / "lab_test.db"
os.environ["AI4ARTSED_DB_PATH"] = str(_TMP_DB)

import pytest
from flask import Flask, jsonify
from werkzeug.serving import make_server

import devserver_sign_in as DS
from my_app.lab import models as M
from my_app.lab import sign_in_gate, terms
from my_app.lab.auth_service import hash_password
from my_app.lab.db import Base, SessionLocal, engine
from my_app.routes.auth_routes import auth_bp


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    SessionLocal.remove()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    for name in (DS.ENV_ID, DS.ENV_PASSWORD, DS.ENV_PLACE_CODE):
        monkeypatch.delenv(name, raising=False)
    DS._sessions.clear()
    yield
    DS._sessions.clear()
    SessionLocal.remove()


def _serve(secure_cookie: bool):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["SESSION_COOKIE_SECURE"] = secure_cookie
    app.register_blueprint(auth_bp)

    @app.route("/api/closed")
    def closed():
        return jsonify(ok=True)

    sign_in_gate.install(app)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://localhost:{server.server_port}"


@pytest.fixture(params=[False, True], ids=["dev-cookie", "secure-cookie"])
def server(request):
    srv, url = _serve(request.param)
    yield url
    srv.shutdown()


def _account(agreed=True):
    db = SessionLocal()
    user = M.User(username="runner", role=M.Role.educator, display_name="",
                  password_hash=hash_password("secret12"), is_active=True)
    db.add(user)
    db.commit()
    if agreed:
        terms.record(db, user, "de")
    SessionLocal.remove()


def test_without_a_sign_in_nothing_is_sent(server):
    with pytest.raises(DS.SignInError, match=DS.ENV_ID):
        DS.devserver(server)


def test_the_script_reaches_a_closed_route(server, monkeypatch):
    _account()
    monkeypatch.setenv(DS.ENV_ID, "runner")
    monkeypatch.setenv(DS.ENV_PASSWORD, "secret12")
    session = DS.devserver(server)
    assert session.get(f"{server}/api/closed").json() == {"ok": True}
    # Every later request goes through the same sign-in.
    assert DS.devserver(server) is session
    assert session.get(f"{server}/api/closed").status_code == 200


def test_an_account_without_the_agreement_is_sent_to_the_browser(server, monkeypatch):
    _account(agreed=False)
    monkeypatch.setenv(DS.ENV_ID, "runner")
    monkeypatch.setenv(DS.ENV_PASSWORD, "secret12")
    with pytest.raises(DS.SignInError, match="browser"):
        DS.devserver(server)


def test_a_wrong_password_is_refused(server, monkeypatch):
    _account()
    monkeypatch.setenv(DS.ENV_ID, "runner")
    monkeypatch.setenv(DS.ENV_PASSWORD, "wrong")
    with pytest.raises(DS.SignInError, match="401"):
        DS.devserver(server)


def test_the_async_session_reaches_a_closed_route(server, monkeypatch):
    pytest.importorskip("aiohttp")
    _account()
    monkeypatch.setenv(DS.ENV_ID, "runner")
    monkeypatch.setenv(DS.ENV_PASSWORD, "secret12")

    async def run():
        async with await DS.aiohttp_session(server) as session:
            async with session.get(f"{server}/api/closed") as resp:
                return resp.status, await resp.json()

    assert asyncio.run(run()) == (200, {"ok": True})
