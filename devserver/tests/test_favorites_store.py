"""
Tests for my_app/services/favorites_store.py — the single canonical
reader/writer of favorites.json (Rule #13: favorites_routes.py and
tool_registry.py previously each had an inline reader).

Covers both deliberate error contracts:
- lenient routes semantics: load_favorites() yields a FRESH default
  document on missing or corrupt data (never a shared constant);
  save_favorites() auto-creates parent dirs, returns bool, never raises.
- strict Resona-tool semantics: read_favorites_raw() raises on missing
  or corrupt data.

Run: python3 -m pytest devserver/tests/test_favorites_store.py -q
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
from my_app.services.favorites_store import (
    FAVORITES_FILENAME,
    default_favorites_data,
    get_favorites_file,
    load_favorites,
    read_favorites_raw,
    save_favorites,
)


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    """Point the store at a temp dir (config is read at CALL time)."""
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    return tmp_path


def _doc(favorites: list) -> dict:
    return {"version": "1.0", "mode": "global", "favorites": favorites}


def _write_corrupt(storage: Path):
    (storage / FAVORITES_FILENAME).write_text("{not json!!!", encoding="utf-8")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def test_get_favorites_file_resolves_under_patched_dir(storage):
    assert get_favorites_file() == storage / FAVORITES_FILENAME


def test_get_favorites_file_explicit_dir_wins_over_config(storage):
    elsewhere = storage / "elsewhere"
    assert get_favorites_file(elsewhere) == elsewhere / FAVORITES_FILENAME


# ---------------------------------------------------------------------------
# load_favorites (lenient routes semantics)
# ---------------------------------------------------------------------------

def test_load_missing_file_returns_default(storage):
    assert load_favorites() == _doc([])


def test_load_corrupt_json_returns_default(storage):
    _write_corrupt(storage)
    assert load_favorites() == _doc([])


def test_defaults_are_fresh_objects_per_call(storage):
    # missing-file default vs corrupt-file default: distinct dicts with no
    # shared mutable state (routes append to the list they get back).
    d_missing = load_favorites()
    _write_corrupt(storage)
    d_corrupt = load_favorites()
    assert d_missing is not d_corrupt
    assert d_missing["favorites"] is not d_corrupt["favorites"]
    d_missing["favorites"].append({"run_id": "x"})
    assert d_corrupt["favorites"] == []
    # and default_favorites_data itself mints a new dict on every call
    assert default_favorites_data() is not default_favorites_data()


# ---------------------------------------------------------------------------
# save_favorites round-trip
# ---------------------------------------------------------------------------

def test_save_load_round_trip(storage):
    data = _doc([{"run_id": "run-1", "media_type": "image", "user_note": "unser Wald"}])
    assert save_favorites(data) is True
    assert load_favorites() == data
    assert read_favorites_raw() == data


def test_save_creates_parent_dirs(storage):
    nested = storage / "a" / "b"
    assert not nested.exists()
    assert save_favorites(_doc([]), nested) is True
    assert (nested / FAVORITES_FILENAME).exists()
    assert load_favorites(nested) == _doc([])


# ---------------------------------------------------------------------------
# read_favorites_raw (strict tool semantics)
# ---------------------------------------------------------------------------

def test_read_raw_missing_file_raises(storage):
    with pytest.raises(FileNotFoundError):
        read_favorites_raw()


def test_read_raw_corrupt_json_raises(storage):
    _write_corrupt(storage)
    with pytest.raises(json.JSONDecodeError):
        read_favorites_raw()


# ---------------------------------------------------------------------------
# save failure contract
# ---------------------------------------------------------------------------

def test_save_failure_returns_false_without_raising(storage):
    # 'blocked' is a FILE, so blocked/sub can never become a directory —
    # the parent mkdir fails and save must swallow it into False.
    blocked = storage / "blocked"
    blocked.write_text("a file, not a directory", encoding="utf-8")
    assert save_favorites(_doc([]), blocked / "sub") is False
