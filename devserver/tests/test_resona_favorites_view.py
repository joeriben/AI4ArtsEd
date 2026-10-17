"""
Tests for view_favorite (Resona's image perception, 2026-07-03) and the
situation-block prompt composition (core + workshop/planning + GIVEN NOW).

The live vision call (GPU-service VLM) is not unit-tested here — only the
handler's guard paths; the vision path is smoke-tested on the dev server.

Run: python3 -m pytest devserver/tests/test_resona_favorites_view.py -q
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import config
from my_app.services.tool_registry import get_tool_registry


@pytest.fixture()
def registry():
    return get_tool_registry()


@pytest.fixture()
def fav_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    return tmp_path


def _write_favorites(storage: Path, favorites: list):
    (storage / "favorites.json").write_text(
        json.dumps({"version": "1.0", "mode": "global", "favorites": favorites}),
        encoding="utf-8",
    )


def test_view_requires_run_id(registry, fav_storage):
    assert registry.execute("view_favorite", {}).startswith("Error: run_id is required")


def test_view_rejects_non_favorite(registry, fav_storage):
    _write_favorites(fav_storage, [{"run_id": "run_a", "media_type": "image"}])
    result = registry.execute("view_favorite", {"run_id": "run_b"})
    assert "not among the shared favorites" in result


def test_view_handles_missing_run_data(registry, fav_storage):
    _write_favorites(fav_storage, [{"run_id": "run_a", "media_type": "image"}])
    result = registry.execute("view_favorite", {"run_id": "run_a"})
    assert "no longer on disk" in result


def test_favorites_listing_carries_run_id(registry, fav_storage):
    _write_favorites(
        fav_storage,
        [{
            "run_id": "run_xyz",
            "media_type": "image",
            "added_at": "2026-07-03T10:00:00",
            "user_note": "unser Wald",
        }],
    )
    result = registry.execute("lookup_shared_favorites", {})
    assert "run_id=run_xyz" in result


def test_prompt_composition_workshop_default():
    from my_app.routes.chat_routes import build_system_prompt

    p = build_system_prompt({"resona_mode": True, "device_id": "test-compose-a"}, "de")
    assert "THE WORKSHOP SITUATION" in p
    assert "THE PLANNING SITUATION" not in p
    assert "GIVEN NOW:" in p
    assert "PROCESS SCAFFOLDS" in p  # C0 contract survived the v2 restructuring


def test_prompt_composition_consulting():
    from my_app.routes.chat_routes import build_system_prompt

    p = build_system_prompt(
        {"resona_mode": True, "resona_situation": "consulting", "device_id": "test-compose-b"},
        "de",
    )
    assert "THE PLANNING SITUATION" in p
    assert "THE WORKSHOP SITUATION" not in p
    assert "GIVEN NOW:" in p


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
