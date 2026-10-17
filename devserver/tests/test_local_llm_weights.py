#!/usr/bin/env python3
"""The table of local language models, and what reads it.

config/local_llm_weights.json says what a local alias IS: the Hugging Face
repository, the folder under ComfyUI's models/llm/, whether the checkpoint
reads images. Stage 3 of the move to ComfyUI: the DevServer
resolves an alias to that folder for the ComfyUI node (services/llm_client),
the installer downloads from it, and the model lists are read off it. This
file holds the table to its shape, the register to the table, and the reader
to what the routes expect of it.

Run: pytest devserver/tests/test_local_llm_weights.py -q
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from file_modules import DEVSERVER

REPO = DEVSERVER.parent
TABLE = DEVSERVER / "config" / "local_llm_weights.json"
REGISTER = DEVSERVER / "hardware_matrix.defaults.json"
SNAPSHOT_CHECK = REPO / "comfyui_nodes" / "ai4artsed_comfyui" / "_snapshot.py"

_ALIAS = re.compile(r"^[\w.-]+:(\d+(\.\d+)?b|latest)$|^[a-z0-9-]+$")


def _table():
    return json.loads(TABLE.read_text(encoding="utf-8"))


def test_every_entry_carries_what_the_readers_read():
    table = _table()
    models = table["models"]
    assert models, "the table names no model"
    dirs = set()
    for alias, e in models.items():
        assert _ALIAS.match(alias), f"{alias}: not spelled like a local alias"
        assert "/" in e["repo"] and e["repo"].count("/") == 1, f"{alias}: repo is not owner/name"
        assert e["dir"] == e["repo"].replace("/", "--"), (
            f"{alias}: dir is not the repo with '/' written as '--' -- the node lists that folder")
        assert e["dir"] not in dirs, f"{alias}: two aliases share the folder {e['dir']}"
        dirs.add(e["dir"])
        assert e.get("display_name"), f"{alias}: no display_name"
        assert isinstance(e.get("chat_capable"), bool), f"{alias}: chat_capable is not a bool"
        assert isinstance(e.get("vision"), bool), f"{alias}: vision is not a bool"
        assert isinstance(e.get("size_gb"), (int, float)) and e["size_gb"] > 0, f"{alias}: no size_gb"
        for key in ("ignore", "requires"):
            if key in e:
                assert isinstance(e[key], list) and all(isinstance(x, str) for x in e[key]), f"{alias}: {key}"
    for second, first in table.get("aliases", {}).items():
        assert first in models, f"alias {second} -> {first}, which the table does not hold"
        assert second not in models, f"alias {second} is also an entry"


def test_the_register_names_only_models_the_table_holds():
    """A preset naming a local model the table does not know is a picker
    offering something nothing can install or run."""
    from my_app.services import local_llm_weights as w
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    unknown = []

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, f"{path}/{k}")
        elif isinstance(x, list):
            for v in x:
                walk(v, path)
        elif isinstance(x, str) and x.startswith(w.LOCAL_PREFIX):
            if w.entry(x) is None:
                unknown.append(f"{path}: {x}")

    walk(register, "")
    assert not unknown, "The shipped register names local models the table does not hold:\n  " + "\n  ".join(unknown)


def test_the_local_defaults_are_in_the_table():
    """What config.py names as a local default has to be installable
    (stage 3 of the move to ComfyUI). The safety classifier is
    not checked here: its weights belong to the GPU service and stand outside
    this table (my_app/services/safety_classifier.py)."""
    import config
    from my_app.services import local_llm_weights as w
    for key in ("KNOWLEDGE_QUERY_TRANSLATION_MODEL", "CAPTION_VLM_MODEL",
                "CAPTION_CLEANUP_MODEL"):
        value = getattr(config, key, "")
        if value:
            assert w.entry(value) is not None, f"config.{key} = {value!r} is not in the table"


def test_resolution_and_listing_shape():
    from my_app.services import local_llm_weights as w
    alias = next(iter(w.models()))
    e = w.models()[alias]
    assert w.resolve_alias(f"{w.LOCAL_PREFIX}{alias}") == alias
    assert w.dir_name(alias) == e["dir"]
    assert w.dir_name(f"{w.LOCAL_PREFIX}{alias}") == e["dir"]
    assert w.entry("nothing/of/this") is None and w.dir_name("nothing:1b") is None
    for second, first in w._table().get("aliases", {}).items():
        assert w.resolve_alias(second) == first
    row = w.listing()[0]
    # The shape chat_routes.list_chat_models and chat_vlm_models read.
    for key in ("id", "display_name", "available", "installable", "approx_download_mb", "backend"):
        assert key in row, f"listing lacks {key}"
    assert row["backend"] == "llm", "vlm_analysis_comparison.vue preselects models whose backend is 'llm'"
    assert row["installable"] is True
    assert isinstance(row["available"], bool)
    assert all(m["chat_capable"] for m in w.chat_models())
    assert all(m["vision"] for m in w.vision_models())


def test_installed_means_a_whole_snapshot(tmp_path, monkeypatch):
    """config.json alone is not a model; a shard the index names has to be
    there, and no part may still be in flight. The same function decides on
    both sides (the node's _snapshot.py)."""
    from my_app.services import local_llm_weights as w
    assert w.SNAPSHOT_CHECK == SNAPSHOT_CHECK and SNAPSHOT_CHECK.exists()
    monkeypatch.setattr(w, "models_root", lambda: tmp_path)
    alias = next(iter(w.models()))
    d = tmp_path / w.dir_name(alias)
    d.mkdir()
    assert not w.is_installed(alias)
    (d / "config.json").write_text("{}")
    assert not w.is_installed(alias), "a config without weights counted as installed"
    (d / "model.safetensors.index.json").write_text(json.dumps(
        {"weight_map": {"a": "model-00001-of-00002.safetensors", "b": "model-00002-of-00002.safetensors"}}))
    (d / "model-00001-of-00002.safetensors").write_bytes(b"x")
    assert not w.is_installed(alias), "a missing shard counted as installed"
    (d / "model-00002-of-00002.safetensors").write_bytes(b"x")
    assert w.is_installed(alias)
    cache = d / ".cache" / "huggingface" / "download"
    cache.mkdir(parents=True)
    (cache / "model-00002-of-00002.safetensors.incomplete").write_bytes(b"")
    assert not w.is_installed(alias), "a part in flight counted as installed"
    (cache / "model-00002-of-00002.safetensors.incomplete").unlink()
    assert w.installed_aliases() == [alias]
    assert w.installed_dir_names() == [w.dir_name(alias)]
    assert w.alias_of_dir(w.dir_name(alias)) == alias
    # A single-file snapshot has no index; any safetensors file is the model.
    other = [a for a in w.models() if a != alias][0]
    d2 = tmp_path / w.dir_name(other)
    d2.mkdir()
    (d2 / "config.json").write_text("{}")
    assert not w.is_installed(other)
    (d2 / "model.safetensors").write_bytes(b"x")
    assert w.is_installed(other)
