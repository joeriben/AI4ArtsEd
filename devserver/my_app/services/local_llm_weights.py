"""The local language and image-reading models, from one table.

config/local_llm_weights.json says what a local alias IS on this installation:
the Hugging Face repository its weights come from, the folder under ComfyUI's
models/llm/ they are written to, and whether the checkpoint reads images. The
installer downloads from it, the ComfyUI client resolves an alias to that
folder with it, and the model lists of the settings page and the comparison
surfaces are read off it. Until stage 3 of the move to ComfyUI the same
knowledge stood in the GPU service's GGUF registry, MODEL_CONFIGS in
gpu_service/services/llm_backend.py, and the DevServer asked that service for
it over HTTP.

The weights themselves are loaded by ComfyUI, under its own memory management
(comfyui_nodes/ai4artsed_comfyui/_local_llm.py). This module never touches
them; it says where they are and whether they are complete.
"""
import importlib.util
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import config

logger = logging.getLogger(__name__)

DEVSERVER_ROOT = config.DEVSERVER_DIR
TABLE_FILE = DEVSERVER_ROOT / "config" / "local_llm_weights.json"

# Whether a folder holds a whole snapshot is decided in the node package, once
# for both sides (comfyui_nodes/ai4artsed_comfyui/_snapshot.py, stdlib only);
# the node lists what it can load with the same function. Loaded by path: the
# package is no Python package of the DevServer's, and its other modules
# import torch and ComfyUI.
SNAPSHOT_CHECK = DEVSERVER_ROOT.parent / "comfyui_nodes" / "ai4artsed_comfyui" / "_snapshot.py"

# The folder under ComfyUI's models directory that holds every local language
# model, one sub-folder per repository. ComfyUI's node registers the same name
# with folder_paths, so the two sides list the same directory.
MODELS_SUBDIR = "llm"

# The prefix a platform id carries for a model on this machine. Stripped here,
# once; the table is keyed without it.
LOCAL_PREFIX = "local/"


@lru_cache(maxsize=1)
def _table() -> dict:
    with open(TABLE_FILE) as f:
        return json.load(f)


def models() -> Dict[str, dict]:
    """Every alias, in table order, with its entry."""
    return _table()["models"]


@lru_cache(maxsize=1)
def _snapshot():
    spec = importlib.util.spec_from_file_location("ai4artsed_snapshot", SNAPSHOT_CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_alias(model_id: str) -> str:
    """The table's key for a platform id: 'local/' stripped, a second-name
    alias (the table's "aliases" block) mapped to the entry it names, everything
    else as it came. What comes back may still be unknown to the table; entry()
    says so."""
    name = model_id[len(LOCAL_PREFIX):] if model_id.startswith(LOCAL_PREFIX) else model_id
    return _table().get("aliases", {}).get(name, name)


def entry(model_id: str) -> Optional[dict]:
    """The table entry a platform id names, or None for a model the table does
    not know -- a cloud id, a GGUF-era name nothing offers any more."""
    return models().get(resolve_alias(model_id))


def models_root() -> Path:
    """<ComfyUI>/models/llm, from the platform's ComfyUI path."""
    from config import COMFYUI_BASE_PATH
    return Path(COMFYUI_BASE_PATH) / "models" / MODELS_SUBDIR


def weights_dir(model_id: str) -> Optional[Path]:
    """Where the alias's weights live once downloaded; None for an unknown id."""
    e = entry(model_id)
    return models_root() / e["dir"] if e else None


def dir_name(model_id: str) -> Optional[str]:
    """The folder name ComfyUI's node is given for this alias -- what the node
    lists and what the DevServer sends. None for an unknown id."""
    e = entry(model_id)
    return e["dir"] if e else None


def folder_is_whole(path) -> bool:
    """The node package's test of a whole snapshot (_snapshot.complete: the
    config, no '.incomplete' part, every shard the index names), on a folder
    by path -- the installer's staging folder before it is renamed."""
    return bool(_snapshot().complete(str(path)))


def is_installed(model_id: str) -> bool:
    """True when the snapshot is on disk and whole (folder_is_whole)."""
    d = weights_dir(model_id)
    return d is not None and folder_is_whole(d)


def installed_aliases() -> List[str]:
    """The aliases whose snapshot is whole, in table order: what the role
    pickers of the settings page offer, which carry no availability flag of
    their own."""
    return [alias for alias in models() if is_installed(alias)]


def installed_dir_names() -> List[str]:
    """The folder names under models/llm that hold a complete snapshot, in
    table order. What the node's dropdown will offer, read from the same disk."""
    return [e["dir"] for alias, e in models().items() if is_installed(alias)]


def alias_of_dir(dir_name_: str) -> Optional[str]:
    """The alias whose weights folder this is; None for a folder the table
    does not know (somebody copied a model in by hand)."""
    for alias, e in models().items():
        if e["dir"] == dir_name_:
            return alias
    return None


def _listing(alias: str, e: dict) -> dict:
    """One model as the lists of the comparison surfaces carry it.

    The shape is the one the GPU service's chat-models and vlm-models lists
    answered with (id, display_name, available, installable,
    approx_download_mb, backend), so the routes that read them
    (chat_routes.list_chat_models, chat_vlm_models) and the composables behind
    them keep reading what they read. Every entry of the table is installable
    from the surface; a gated one needs HF_TOKEN, which the precheck says.
    'backend' keeps the value "llm" the language-model station answered with:
    the Image Understanding surface preselects the models of that station
    (vlm_analysis_comparison.vue) and tells them apart from the readers of the
    media-analysis station by this word, which names the kind of station, and
    the station is ComfyUI now.
    """
    return {
        "id": alias,
        "display_name": e.get("display_name", alias),
        "available": is_installed(alias),
        "installable": True,
        "approx_download_mb": int(round(float(e.get("size_gb") or 0) * 1024)),
        "backend": "llm",
        "chat_capable": bool(e.get("chat_capable")),
        "vision": bool(e.get("vision")),
        "gated": bool(e.get("gated")),
        "repo": e["repo"],
    }


def listing() -> List[dict]:
    """Every alias of the table, installed or not, in table order."""
    return [_listing(alias, e) for alias, e in models().items()]


def chat_models() -> List[dict]:
    """The models the platform offers on its comparison surfaces."""
    return [m for m in listing() if m["chat_capable"]]


def vision_models() -> List[dict]:
    """The models that read images."""
    return [m for m in listing() if m["vision"]]
