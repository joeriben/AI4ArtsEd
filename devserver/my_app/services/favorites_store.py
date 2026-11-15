"""
Favorites store — single owner of favorites.json (path, load, save).

Rule #13 (NO PARALLEL ELEMENT STRUCTURES): favorites_routes.py and
tool_registry.py previously each had an inline favorites.json reader.
This module is the one canonical reader/writer.

The two consumer families keep deliberately different error contracts:
- favorites_routes.py (read-write): the listing reads with load_favorites(),
  which is lenient — a missing or corrupt file yields a fresh default
  document, errors are logged, never raised. A writer, and a route that
  decides by what the store holds, reads with load_favorites_strict(), which
  raises on a file it cannot read: read leniently, an unreadable store became
  the empty default, and the writer saved a store holding its own entry
  alone. save_favorites() returns bool, never raises.
- tool_registry.py Resona tools (read-only): read_favorites_raw() is
  strict — it raises, so each tool keeps its own user-facing wording
  for missing/corrupt data.

Location: config.JSON_STORAGE_DIR / "favorites.json". The config
attribute is read at CALL time, never bound at import time — tests
monkeypatch config.JSON_STORAGE_DIR (see tests/test_resona_favorites_tool.py).

Every writer reads the whole document, changes it and writes it back. Two
writers at once, a star and the deletion of a course, each wrote back what
they had read, and the later one undid the earlier. A writer holds the store
for its read, change and write (`editing`); the server is one process with
several threads (server.py), so a lock in this module reaches all of them.
`save_favorites` writes a new file and puts it in place of the old one: a
reader that came while the file was being written found it empty and took the
empty default, and an add then saved a store holding one entry.
"""
import json
import logging
import os
import stat
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

FAVORITES_FILENAME = "favorites.json"

_EDITING = threading.RLock()

# The accounts whose favourites drop_owned took out, by id and stamp. A star
# that set out under one of them before it was deleted is refused when it
# reaches the store (routes/favorites_routes.py, add_favorite), so that nothing
# is kept under an account that is gone. In memory: the server is one process,
# and after a restart no session of a deleted account is left to send one.
_DROPPED: set = set()


@contextmanager
def editing():
    """Hold the store for one read, change and write."""
    with _EDITING:
        yield


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


def load_favorites_strict(storage_dir: Optional[Path] = None) -> dict:
    """
    The store for a writer, read under `editing`, and for a route that decides
    by what it holds. A missing or an empty file, and a document without
    favourites, hold none; a file that cannot be read or parsed, or whose
    favourites are no list, raises.
    """
    favorites_file = get_favorites_file(storage_dir)
    if not favorites_file.exists():
        return default_favorites_data()
    text = favorites_file.read_text(encoding="utf-8")
    if not text.strip():
        return default_favorites_data()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("favorites.json holds no document of favourites")
    data.setdefault('favorites', [])
    if not isinstance(data['favorites'], list):
        raise ValueError("favorites.json holds no list of favourites")
    return data


def was_dropped(owner_id, stamp) -> bool:
    """Whether drop_owned has taken out the favourites of this account. Asked
    under `editing`."""
    return (owner_id, stamp) in _DROPPED


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
    written = None
    try:
        # Ensure directory exists
        favorites_file.parent.mkdir(parents=True, exist_ok=True)

        # Written beside the store and put in its place whole: a reader finds
        # the old document or the new one, never a file half written. A store
        # that is a link is written where the link points.
        target = Path(os.path.realpath(favorites_file))
        handle, written = tempfile.mkstemp(
            dir=target.parent, prefix=".favorites.", suffix=".tmp")
        with os.fdopen(handle, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        # mkstemp makes a file only its owner may read; the store keeps the
        # mode it had.
        os.chmod(written, stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644)
        os.replace(written, target)
        return True
    except Exception as e:
        logger.error(f"[FAVORITES] Error saving favorites: {e}")
        if written is not None and os.path.exists(written):
            os.remove(written)
        return False


def drop_owned(owners, storage_dir: Optional[Path] = None) -> int:
    """
    Remove the favourites kept under the given accounts.

    Each account is named by its id and the moment it was made, as an entry
    names its owner (routes/favorites_routes.py, `_asker`): SQLite gives the id
    of a deleted account to the next account made. Called where accounts are
    deleted (a course with its places, an account on its own), so that their
    favourites go with them, as their perspectives go by the database's
    cascade. Entries kept without an account are not touched.

    Returns how many were removed, or -1 where the store could not be read as
    a store or not be written. It raises nothing: the accounts are deleted by
    then, and the request that deleted them has succeeded.
    """
    names = {(owner_id, stamp) for owner_id, stamp in owners}
    if not names:
        return 0
    try:
        with editing():
            _DROPPED.update(names)
            data = load_favorites_strict(storage_dir)
            favorites = data['favorites']
            kept = [fav for fav in favorites
                    if not isinstance(fav, dict)
                    or fav.get('owner_id') is None
                    or (fav.get('owner_id'), fav.get('owner_stamp')) not in names]
            removed = len(favorites) - len(kept)
            if removed == 0:
                return 0
            data['favorites'] = kept
            return removed if save_favorites(data, storage_dir) else -1
    except Exception as e:
        logger.error(f"[FAVORITES] The favourites of deleted accounts were not removed: {e}")
        return -1
