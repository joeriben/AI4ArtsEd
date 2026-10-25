"""
Favorites store — single owner of favorites.json (path, load, save).

Rule #13 (NO PARALLEL ELEMENT STRUCTURES): favorites_routes.py and
tool_registry.py previously each had an inline favorites.json reader.
This module is the one canonical reader/writer.

The two consumer families keep deliberately different error contracts:
- favorites_routes.py (read-write): load_favorites() is lenient — a
  missing or corrupt file yields a fresh default document, errors are
  logged, never raised; save_favorites() returns bool, never raises.
- tool_registry.py Resona tools (read-only): read_favorites_raw() is
  strict — it raises, so each tool keeps its own user-facing wording
  for missing/corrupt data.

Location: config.JSON_STORAGE_DIR / "favorites.json". The config
attribute is read at CALL time, never bound at import time — tests
monkeypatch config.JSON_STORAGE_DIR (see tests/test_resona_favorites_tool.py).
"""
import json
import logging
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

FAVORITES_FILENAME = "favorites.json"


def default_favorites_data() -> dict:
    """Fresh empty favorites document (a NEW dict per call, never a shared constant)."""
    return {
        "version": "1.0",
        "mode": "global",
        "favorites": []
    }


def get_favorites_file(storage_dir: Optional[Path] = None) -> Path:
    """
    Resolve the favorites.json path.

    If storage_dir is None, config.JSON_STORAGE_DIR is read at call time
    (never bound at import time — tests monkeypatch it).
    """
    if storage_dir is None:
        storage_dir = config.JSON_STORAGE_DIR
    return Path(storage_dir) / FAVORITES_FILENAME


def read_favorites_raw(storage_dir: Optional[Path] = None) -> dict:
    """
    Strict read: parse favorites.json and return the document as-is.

    Raises FileNotFoundError/OSError/json.JSONDecodeError on missing or
    corrupt data — no logging, no fallback. Consumers (the read-only
    Resona tools) keep their own user-facing wording for these cases.
    """
    return json.loads(get_favorites_file(storage_dir).read_text(encoding="utf-8"))


def load_favorites(storage_dir: Optional[Path] = None) -> dict:
    """
    Load favorites from disk (lenient routes semantics: missing or corrupt
    file yields a fresh default document; errors are logged, never raised).

    Returns:
        dict with version, mode, and favorites list
    """
    favorites_file = get_favorites_file(storage_dir)
    if not favorites_file.exists():
        return default_favorites_data()

    try:
        with open(favorites_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[FAVORITES] Error loading favorites: {e}")
        return default_favorites_data()


def save_favorites(data: dict, storage_dir: Optional[Path] = None) -> bool:
    """
    Save favorites to disk (routes semantics: parent directory auto-created,
    failures logged and reported as False, never raised).

    Args:
        data: Favorites data dict

    Returns:
        True if successful, False otherwise
    """
    favorites_file = get_favorites_file(storage_dir)
    try:
        # Ensure directory exists
        favorites_file.parent.mkdir(parents=True, exist_ok=True)

        with open(favorites_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"[FAVORITES] Error saving favorites: {e}")
        return False
