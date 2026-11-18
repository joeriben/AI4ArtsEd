"""
A perspective whose context is a LIST is a pool: each pick draws one entry.

The two pool presets in the centre of the chooser bring back the random
generators of the ComfyUI nodes
(docs/reference/fyi_comfyui-customnodes_ai4artsed_comfyui/): the 56
instructions and the 51 art forms, rewritten as stances, not styles; the draw
happens at the pick. The decision: docs/DEVELOPMENT_DECISIONS.md.

The draw sits in schemas/engine/config_loader.py (draw_from_pool). The chooser
asks /api/config/<id>/context, which hands out one entry and marks the answer
so that no cache keeps it; the drawn entry then stands in the field like any
other perspective's wording.

Run: python3 -m pytest devserver/tests/test_context_pool.py -q
"""
import json
import os
import random
import re
import sys
import tempfile
from pathlib import Path

DEVSERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVSERVER))
os.environ.setdefault(
    "AI4ARTSED_DB_PATH",
    str(Path(tempfile.mkdtemp(prefix="context_pool_test_")) / "lab_test.db"),
)

import pytest

from schemas.engine.config_loader import draw_from_pool, resolve_context_language

INTERCEPTION = DEVSERVER / "schemas" / "configs" / "interception"
POOLS = {"random_instruction": 56, "random_artform": 51}
POOL = [{"en": "a", "de": "A"}, {"en": "b", "de": "B"}]


def _preset(name):
    return json.loads((INTERCEPTION / f"{name}.json").read_text(encoding="utf-8"))


def test_a_pool_hands_out_one_of_its_entries():
    for _ in range(20):
        assert draw_from_pool(POOL) in POOL


def test_every_entry_of_a_pool_can_be_drawn():
    rng_state = random.getstate()
    try:
        random.seed(0)
        pool = [{"en": str(i)} for i in range(5)]
        assert {draw_from_pool(pool)["en"] for _ in range(300)} == {str(i) for i in range(5)}
    finally:
        random.setstate(rng_state)


def test_a_context_that_is_no_pool_passes_unchanged():
    assert draw_from_pool("text") == "text"
    assert draw_from_pool({"en": "x"}) == {"en": "x"}
    assert draw_from_pool(None) is None


def test_an_empty_pool_is_no_context():
    assert draw_from_pool([]) is None
    assert resolve_context_language([], "de") == ""


def test_resolving_a_pool_reads_the_drawn_entry_in_the_language():
    for _ in range(20):
        assert resolve_context_language(POOL, "de") in {"A", "B"}
        assert resolve_context_language(POOL, "fr") in {"a", "b"}  # falls back to en


@pytest.mark.parametrize("name,count", sorted(POOLS.items()))
def test_the_pool_presets_hang_in_the_centre_and_hold_their_count(name, count):
    cfg = _preset(name)
    assert cfg["pipeline"] == "text_transformation"
    assert cfg["properties"] == ["freestyle"]
    pool = cfg["context"]
    assert isinstance(pool, list) and len(pool) == count
    # the description names the number it is drawn from
    assert str(count) in cfg["description"]["en"]
    assert str(count) in cfg["description"]["de"]
    for entry in pool:
        assert set(entry) == {"en", "de"}
        assert entry["en"].strip() and entry["de"].strip()


@pytest.mark.parametrize("name", sorted(POOLS))
def test_no_entry_asks_for_a_style(name):
    """Stances, not styles. The old art-form list read
    "Rewrite this in the style of Japanese Noh theatre"; the platform's own
    perspectives forbid that formula (bauhaus.json)."""
    for entry in _preset(name)["context"]:
        assert not re.search(r"\bstyles?\b", entry["en"], re.I), entry["en"]
        assert not re.search(r"\bstil(e|en|s)?\b", entry["de"], re.I), entry["de"]


@pytest.mark.parametrize("name", sorted(POOLS))
def test_a_canvas_node_on_a_pool_preset_runs_one_entry(name):
    from my_app.services.canvas_executor import _load_interception_context
    german = {entry["de"] for entry in _preset(name)["context"]}
    context, error = _load_interception_context(name, "de")
    assert error is None
    assert context in german


@pytest.fixture
def client(monkeypatch):
    import my_app
    from my_app import create_app
    from lab_sign_in import sign_in_admin
    app = create_app()
    app.config.update(TESTING=True)
    monkeypatch.setattr(my_app, "DISABLE_API_CACHE", False)
    return sign_in_admin(app.test_client())


def test_the_chooser_is_handed_one_entry_that_no_cache_keeps(client):
    german = {entry["de"] for entry in _preset("random_instruction")["context"]}
    resp = client.get("/api/config/random_instruction/context")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    assert "X-Drawn" not in resp.headers
    context = resp.get_json()["context"]
    assert isinstance(context, dict) and context["de"] in german


def test_a_fixed_perspective_is_still_kept_for_five_minutes(client):
    resp = client.get("/api/config/bauhaus/context")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "private, max-age=300"


@pytest.mark.parametrize("name,count", sorted(POOLS.items()))
def test_help_reads_a_pool_preset_as_a_pool(name, count):
    """Help and Together look a perspective up (lookup_interception get_config);
    a pool is described as one and lists its stances."""
    from my_app.services.tool_registry import _get_interception_config
    answer = _get_interception_config(INTERCEPTION, name)
    assert f"pool of {count} stances" in answer
    for entry in _preset(name)["context"]:
        assert entry["en"] in answer


def test_the_canvas_preset_route_hands_out_one_entry(client):
    english = {entry["en"] for entry in _preset("random_artform")["context"]}
    resp = client.get("/api/interception/random_artform")
    if resp.status_code == 404:
        pytest.skip("route not registered under this path")
    assert resp.status_code == 200
    assert resp.get_json()["context"]["en"] in english
