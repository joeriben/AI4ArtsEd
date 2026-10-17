"""
Tests for lookup_shared_favorites — Resona's first perception window
(user-granted 2026-07-02): read-only sight of the workshop's SHARED favorites
as text traces (their words, the platform's transformation, notes) — never
the rendered media. Pool is currently server-global; workshop-ID scoping
arrives with the workshop-leader accounts.

Covers:
- registration: present in scope='resona', absent from the universal scope
- empty pool (no favorites.json / empty list)
- listing with text traces via pipeline_recorder (input + interception),
  most-recent-first order, user_note included
- favorites whose run data is gone are still listed, marked as such
- limit clamping and query filtering (incl. no-match message)

Run: python3 -m pytest devserver/tests/test_resona_favorites_tool.py -q
(from the worktree root; also works from devserver/ directly)
"""

import json
import sys
from pathlib import Path

# devserver/tests/... -> parents[1] == devserver/ (same convention as the
# other resona tests / chat_routes.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import config
from my_app.services.tool_registry import get_tool_registry


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage(tmp_path, monkeypatch):
    """Point the tool's storage dir at a temp dir (handler reads it lazily)."""
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    return tmp_path


def _write_favorites(storage: Path, favorites: list):
    (storage / "favorites.json").write_text(
        json.dumps({"version": "1.0", "mode": "global", "favorites": favorites}),
        encoding="utf-8",
    )


def _fav(run_id: str, media_type: str = "image", note: str = "", added: str = "2026-07-02T10:00:00"):
    return {
        "run_id": run_id,
        "device_id": "dev-a",
        "added_at": added,
        "media_type": media_type,
        "user_id": "anonymous",
        "user_note": note,
    }


class _FakeRecorder:
    """Minimal stand-in for pipeline_recorder's recorder object: the handler
    only touches .metadata and .final_folder."""

    def __init__(self, folder: Path, config_name: str, input_text: str, transformed: str = ""):
        folder.mkdir(parents=True, exist_ok=True)
        self.final_folder = folder
        entities = [{"type": "input", "filename": "input.txt"}]
        (folder / "input.txt").write_text(input_text, encoding="utf-8")
        if transformed:
            entities.append({"type": "interception", "filename": "interception.txt"})
            (folder / "interception.txt").write_text(transformed, encoding="utf-8")
        self.metadata = {"config_name": config_name, "entities": entities}


@pytest.fixture()
def fake_recorders(storage, monkeypatch):
    """Registry of run_id -> _FakeRecorder, wired into load_recorder."""
    recorders = {}

    def _load(run_id, base_path=None):
        return recorders.get(run_id)

    import my_app.services.pipeline_recorder as pr
    monkeypatch.setattr(pr, "load_recorder", _load)
    return recorders


def _execute(args: dict) -> str:
    return get_tool_registry().execute("lookup_shared_favorites", args)


# ---------------------------------------------------------------------------
# Registration / scope
# ---------------------------------------------------------------------------

def test_registered_in_resona_scope_only():
    registry = get_tool_registry()
    resona_tools = {t["function"]["name"] for t in registry.get_openai_format(scope="resona")}
    universal_tools = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    assert "lookup_shared_favorites" in resona_tools
    assert "lookup_shared_favorites" not in universal_tools


# ---------------------------------------------------------------------------
# Empty pool
# ---------------------------------------------------------------------------

def test_no_favorites_file(storage):
    result = _execute({})
    assert "No shared favorites yet" in result


def test_empty_favorites_list(storage):
    _write_favorites(storage, [])
    result = _execute({})
    assert "No shared favorites yet" in result


# ---------------------------------------------------------------------------
# Listing with text traces
# ---------------------------------------------------------------------------

def test_lists_text_traces_most_recent_first(storage, fake_recorders):
    # Stored most-recent-first, as favorites_routes POST inserts at index 0.
    _write_favorites(storage, [
        _fav("run_new", note="unser Wald"),
        _fav("run_old", media_type="audio"),
    ])
    fake_recorders["run_new"] = _FakeRecorder(
        storage / "run_new", "sd35_large",
        "Man steht im Wald, ein Feuer brennt",
        "A forest scene without fire",
    )
    fake_recorders["run_old"] = _FakeRecorder(
        storage / "run_old", "stableaudio_open",
        "Wind weht durch die Blaetter",
    )

    result = _execute({})
    assert "2 kept in total, showing 2" in result
    assert result.index("Feuer brennt") < result.index("Wind weht")  # order
    assert 'their note: "unser Wald"' in result
    assert 'what the platform made of it: "A forest scene without fire"' in result
    assert "sd35_large" in result and "stableaudio_open" in result


def test_missing_run_data_still_listed(storage, fake_recorders):
    _write_favorites(storage, [_fav("run_gone")])
    result = _execute({})
    assert "1 kept in total, showing 1" in result
    assert "run data no longer on disk" in result


# ---------------------------------------------------------------------------
# Limit and query
# ---------------------------------------------------------------------------

def test_limit_clamps_and_caps(storage, fake_recorders):
    favs = [_fav(f"run_{i}") for i in range(5)]
    _write_favorites(storage, favs)
    for i in range(5):
        fake_recorders[f"run_{i}"] = _FakeRecorder(storage / f"run_{i}", "sd35_large", f"Bild Nummer {i}")

    result = _execute({"limit": 2})
    assert "5 kept in total, showing 2" in result
    result = _execute({"limit": "not-a-number"})
    assert "showing 5" in result  # falls back to default 8, only 5 exist


def test_query_filters_and_reports_no_match(storage, fake_recorders):
    _write_favorites(storage, [_fav("run_a"), _fav("run_b")])
    fake_recorders["run_a"] = _FakeRecorder(storage / "run_a", "sd35_large", "ein Feuer im Herbstwald")
    fake_recorders["run_b"] = _FakeRecorder(storage / "run_b", "sd35_large", "eine Katze, die kratzt")

    result = _execute({"query": "feuer"})
    assert "showing 1 matching 'feuer'" in result
    assert "Herbstwald" in result and "Katze" not in result

    result = _execute({"query": "xyz-nichts"})
    assert "none matches 'xyz-nichts'" in result
