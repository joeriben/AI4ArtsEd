"""
What production lets a cache keep of the routes behind the sign-in
(my_app/__init__.py, `add_header`; config.CACHE_STRATEGY), since 2026-11-15.

Production marks the answers of /api/config/, /api/models/ and
/pipeline_configs_ as cacheable for five minutes. Every one of those routes
needs a sign-in now (my_app/lab/sign_in_gate.py). A refusal kept for five
minutes would outlast the sign-in that follows it, and an answer marked
`public` could be handed by a shared cache (the Cloudflare edge) to a browser
that is not signed in. Only an answer is kept, and privately.

Run: python3 -m pytest devserver/tests/test_gate_cache_headers.py -q
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault(
    "AI4ARTSED_DB_PATH",
    str(Path(tempfile.mkdtemp(prefix="gate_cache_test_")) / "lab_test.db"),
)

import pytest


@pytest.fixture
def app(monkeypatch):
    import my_app
    from my_app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    monkeypatch.setattr(my_app, "DISABLE_API_CACHE", False)
    return app


def test_a_refusal_of_the_gate_is_not_kept(app):
    resp = app.test_client().get("/pipeline_configs_with_properties")
    assert resp.status_code == 401
    assert "max-age" not in resp.headers.get("Cache-Control", "")


def test_an_answer_behind_the_gate_is_kept_privately(app):
    from lab_sign_in import sign_in_admin
    client = sign_in_admin(app.test_client())
    resp = client.get("/pipeline_configs_with_properties")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "private, max-age=300"
