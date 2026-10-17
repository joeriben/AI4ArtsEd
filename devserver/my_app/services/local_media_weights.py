"""The media stations' models, from one table.

config/local_media_weights.json says what a media alias IS on this
installation: the station it belongs to (Stable Audio 3, ImageBind, MMAudio,
HeartMuLa, Hunyuan3D 2, the media readers), where its weights come from, the
folder under ComfyUI's models/<station>/ they are written to. The installer
(services/local_media_install) downloads from it, the ComfyUI clients resolve
an alias to that folder with it, the backend status of the settings page
reads it. Whether that folder holds a whole model is decided in the node
package, once for both sides (comfyui_nodes/ai4artsed_comfyui/_whole.py,
stdlib only, loaded by path the way local_llm_weights loads _snapshot.py):
the station lists what it can load with the same function. Until stage 6 of
the move to ComfyUI the same knowledge stood in
gpu_service/config.py and in the backends of the GPU service, and the
DevServer asked that service over HTTP.

The weights themselves are loaded by ComfyUI, under its own memory management
(comfyui_nodes/ai4artsed_comfyui/_card.py and the station modules beside it).
This module never touches them; it says where they are and whether they are
complete. The same shape as services/local_llm_weights, which does this for
the language models; a reader of the reading block may name one of those
('local/' prefix), and `reader_dir` resolves it through that table.
"""
import importlib.util
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import config

from my_app.services import local_llm_weights

logger = logging.getLogger(__name__)

DEVSERVER_ROOT = config.DEVSERVER_DIR
TABLE_FILE = DEVSERVER_ROOT / "config" / "local_media_weights.json"
WHOLE_CHECK = local_llm_weights.SNAPSHOT_CHECK.parent / "_whole.py"


@lru_cache(maxsize=1)
def _table() -> dict:
    with open(TABLE_FILE) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _whole():
    spec = importlib.util.spec_from_file_location("ai4artsed_whole", WHOLE_CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stations() -> Dict[str, dict]:
    """Every station, in table order: folder, display_name, library."""
    return _table()["stations"]


def models() -> Dict[str, dict]:
    """Every alias, in table order, with its entry."""
    return _table()["models"]


def entry(alias: str) -> Optional[dict]:
    """The table entry an alias names, or None for one the table does not know."""
    return models().get(alias)


def models_root() -> Path:
    """<ComfyUI>/models, from the platform's ComfyUI path."""
    from config import COMFYUI_BASE_PATH
    return Path(COMFYUI_BASE_PATH) / "models"


def station_root(station: str) -> Path:
    """<ComfyUI>/models/<the station's folder>."""
    return models_root() / stations()[station]["folder"]


def weights_dir(alias: str) -> Optional[Path]:
    """Where the alias's weights live once downloaded; None for an unknown alias."""
    e = entry(alias)
    return station_root(e["station"]) / e["dir"] if e else None


def dir_name(alias: str) -> Optional[str]:
    """The folder name ComfyUI's node is given for this alias -- what the node
    lists and what the DevServer sends. None for an unknown alias."""
    e = entry(alias)
    return e["dir"] if e else None


def folder_missing(station: str, path) -> Optional[str]:
    """What the folder lacks to be a whole model of the station, as the node
    package decides it (_whole.missing: the files the station reads when it
    builds, no huggingface_hub '.incomplete' part in flight, the hub's own
    staging folder .cache/ left out), or None when it is whole. Asked of the
    installer's staging folder before it is renamed into place."""
    return _whole().missing(station, str(path))


def folder_is_whole(station: str, path) -> bool:
    return folder_missing(station, path) is None


def is_installed(alias: str) -> bool:
    """True when the weights are on disk and whole (folder_is_whole)."""
    e = entry(alias)
    d = weights_dir(alias)
    return e is not None and d is not None and folder_is_whole(e["station"], d)


def installed_aliases() -> List[str]:
    """The aliases whose weights are whole, in table order."""
    return [alias for alias in models() if is_installed(alias)]


def aliases_of_station(station: str) -> List[str]:
    """The aliases of one station, in table order."""
    return [alias for alias, e in models().items() if e["station"] == station]


def alias_of_dir(station: str, dir_name_: str) -> Optional[str]:
    """The alias whose weights folder this is, within a station; None for a
    folder the table does not know (somebody copied a model in by hand)."""
    for alias, e in models().items():
        if e["station"] == station and e["dir"] == dir_name_:
            return alias
    return None


def alias_of_folder(dir_name_: str) -> Optional[str]:
    """The alias whose weights folder this is, whatever the station: what a
    node's `model_name` input is read back as (comfyui_ws_client, for the
    bar that names the model a run is at). None for a folder the table does
    not know. No two entries share a folder, across stations either
    (tests/test_local_media_weights.py)."""
    for alias, e in models().items():
        if e["dir"] == dir_name_:
            return alias
    return None


def _listing(alias: str, e: dict) -> dict:
    """One model as the settings page and the installer list it: the shape
    of local_llm_weights._listing, with the station in place of the
    language models' backend word."""
    return {
        "id": alias,
        "display_name": e.get("display_name", alias),
        "available": is_installed(alias),
        "installable": True,
        "approx_download_mb": int(round(float(e.get("size_gb") or 0) * 1024)),
        "backend": e["station"],
        "station": e["station"],
        "gated": bool(e.get("gated")),
        "repo": e.get("repo") or e.get("url") or "",
    }


def listing() -> List[dict]:
    """Every alias of the table, installed or not, in table order."""
    return [_listing(alias, e) for alias, e in models().items()]


# ---------------------------------------------------------------------------
# The reading block: which reader answers which task, and what it is told.

def reading() -> dict:
    return _table()["reading"]


def reader_alias(task: str) -> str:
    """The alias of the reader for a task (audio, video, image, lyrics,
    music_tags), as the table spells it; a 'local/' alias names an entry of
    the language-model table."""
    readers = reading()["readers"]
    if task not in readers:
        raise KeyError(f"no reader for {task!r}; the table knows {sorted(readers)}")
    return readers[task]


def reader_dir(task: str) -> Tuple[str, str]:
    """(alias, folder name) of the reader for a task. The folder name is what
    the node ai4artsed_media_reading is given; for a 'local/' alias it comes
    from the language-model table, and the node lists both folders."""
    alias = reader_alias(task)
    if alias.startswith(local_llm_weights.LOCAL_PREFIX):
        d = local_llm_weights.dir_name(alias)
    else:
        d = dir_name(alias)
    if not d:
        raise KeyError(f"the reader {alias!r} for {task!r} is in no table")
    return alias, d



def reader_trusts_remote_code(task: str) -> bool:
    """Whether the reader's checkpoint carries its own modeling code that
    transformers has to be allowed to run (MiDashengLM does), declared per
    model in the table and nowhere else."""
    return bool((entry(reader_alias(task)) or {}).get("trust_remote_code"))


def prompt(kind: str) -> str:
    """The prompt the readers are given: 'audio_system', 'audio', 'video',
    'image'."""
    return reading()["prompts"][kind]


def music_tag_vocabulary() -> List[str]:
    return list(reading()["music_tag_vocabulary"])


def center_label_embeddings() -> bool:
    return bool(reading().get("center_label_embeddings"))


# ---------------------------------------------------------------------------
# The Stable Audio tier policy, read by services/stable_audio_tier.

def stable_audio_policy() -> dict:
    return _table()["stable_audio"]
