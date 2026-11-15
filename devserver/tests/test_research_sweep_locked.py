"""The research sweep answers at the research level only.

The sweep (dev_routes: the kick-in study) sends two prompts to the card as
they were typed, past every check of the chain, and hands out the pictures,
the datasets and the states made of them. Each of its seven routes refuses
every level but research, before it reads anything of the request. The pixel
template editor in the same blueprint stays open.

Run: python3 -m pytest devserver/tests/test_research_sweep_locked.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import dev_routes

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
LAUNCH = {"dataset_id": "ds_b", "prompt_early": "a lake", "prompt_full": "a lake at dusk", "seed": 7}

SWEEP = [
    ("post", "/api/dev/research-sweep/launch"),
    ("get", "/api/dev/kickin/flach/strip.png"),
    ("get", "/api/dev/kickin-research/datasets"),
    ("get", "/api/dev/kickin-research/ds_a/perblock/status"),
    ("get", "/api/dev/kickin-research/ds_a/perblock/0/kickin_00.png"),
    ("get", "/api/dev/kickin-research/ds_a/cumulative/status"),
    ("get", "/api/dev/kickin-research/ds_a/cumulative/0/kickin_00.png"),
]


@pytest.fixture
def sweep(monkeypatch, tmp_path):
    """The blueprint over a dataset and a band of its own, at a level the test
    sets, with no process started."""
    state = {"level": "research", "spawned": []}
    monkeypatch.setattr(dev_routes, "resolve_safety_level", lambda: state["level"])

    base = tmp_path / "kickin"
    for kind, prefix in (("perblock", "block"), ("cumulative", "upto")):
        done = base / "ds_a" / kind / f"{prefix}_00"
        done.mkdir(parents=True)
        (done / "kickin_00.png").write_bytes(PNG)
        (done / "summary.json").write_text("{}")
    (base / "ds_a" / "metadata.json").write_text(json.dumps({"title": "a"}))
    monkeypatch.setattr(dev_routes, "KICKIN_RESEARCH_BASE", base)

    band = tmp_path / "band_flach"
    band.mkdir()
    (band / "strip.png").write_bytes(PNG)
    monkeypatch.setitem(dev_routes.KICKIN_BANDS, "flach", band)

    root = tmp_path / "project"
    (root / "venv" / "bin").mkdir(parents=True)
    (root / "venv" / "bin" / "python").write_text("")
    monkeypatch.setattr(dev_routes, "PROJECT_ROOT", root)
    monkeypatch.setattr(dev_routes.subprocess, "Popen", lambda *a, **k: state["spawned"].append(a[0]))

    templates = tmp_path / "pixelTemplates.json"
    templates.write_text(json.dumps({"dot": [[1]]}))
    monkeypatch.setattr(dev_routes, "PIXEL_TEMPLATES_FILE", templates)

    app = Flask(__name__)
    app.register_blueprint(dev_routes.dev_bp)
    client = app.test_client()
    client.state = state
    return client


def call(client, method, url, body=None):
    if method == "post":
        return client.post(url, json=body if body is not None else LAUNCH)
    return client.get(url)


@pytest.mark.parametrize("level", ["kids", "youth", "adult"])
@pytest.mark.parametrize("method, url", SWEEP, ids=[u for _, u in SWEEP])
def test_every_route_of_the_sweep_refuses_below_research(sweep, level, method, url):
    sweep.state["level"] = level
    r = call(sweep, method, url)
    assert r.status_code == 403
    assert "research level only" in r.get_json()["error"]
    assert sweep.state["spawned"] == []


@pytest.mark.parametrize("method, url", SWEEP, ids=[u for _, u in SWEEP])
def test_at_research_the_sweep_answers(sweep, method, url):
    r = call(sweep, method, url)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]


def test_at_research_a_launch_starts_the_sweep(sweep):
    r = sweep.post("/api/dev/research-sweep/launch", json=LAUNCH)
    assert r.get_json()["success"] is True
    assert len(sweep.state["spawned"]) == 1


def test_at_research_the_datasets_and_states_are_read(sweep):
    assert [d["id"] for d in sweep.get("/api/dev/kickin-research/datasets").get_json()["datasets"]] == ["ds_a"]
    assert sweep.get("/api/dev/kickin-research/ds_a/perblock/status").get_json()["completed_blocks"] == [0]
    assert sweep.get("/api/dev/kickin-research/ds_a/perblock/0/kickin_00.png").data == PNG


@pytest.mark.parametrize("method, url, body", [
    ("get", "/api/dev/kickin/no_such_band/strip.png", None),
    ("get", "/api/dev/kickin-research/a..b/perblock/status", None),
    ("get", "/api/dev/kickin-research/ds_a/perblock/99/kickin_00.png", None),
    ("post", "/api/dev/research-sweep/launch", {}),
], ids=["unknown-band", "unsafe-id", "block-out-of-range", "empty-launch"])
def test_a_refused_caller_learns_nothing_of_the_sweep(sweep, method, url, body):
    """Below research the answer is the refusal, whatever was asked: not a 404
    for a band that is not there, not a 400 for a request the sweep would turn
    down."""
    sweep.state["level"] = "kids"
    assert call(sweep, method, url, body).status_code == 403


def test_the_pixel_template_editor_stays_open(sweep):
    sweep.state["level"] = "kids"
    r = sweep.get("/api/dev/pixel-templates")
    assert r.status_code == 200
    assert "dot" in r.get_json()
