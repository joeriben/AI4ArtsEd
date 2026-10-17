"""Whether a model folder under models/llm/ holds a whole snapshot.

Read from both sides of the seam: the ComfyUI node lists the folders it can
load (_local_llm.installed_dirs), and the DevServer says which aliases are
installed (my_app/services/local_llm_weights.py, which loads this module by
path, the way _platform_credentials.py loads a DevServer module). One
definition, so the two lists agree.

Whole means: config.json is there; no file of the download is still a
huggingface_hub '.incomplete' part (the hub writes each file under that
suffix and renames it when it is whole, so a download that was cut off leaves
the suffix behind); and every weights file the snapshot's own index names is
there. The last check is what a cut-off download between two shards leaves
nothing else to see by: config.json is in place, no part is in flight, and a
shard is simply absent. The walk takes the dot-folders with it: the hub
stages a local_dir download under .cache/huggingface/ and moves each file
into the folder when it is whole, so a part there is a download in flight.

`missing` names the first thing a folder lacks, for the sentence an installer
answers with; `complete` is that being None. The media stations' checks
(_whole.py) are built on the same two functions.

Stdlib only.
"""
import json
import os
from typing import Optional, Tuple

WEIGHTS_SUFFIXES: Tuple[str, ...] = (".safetensors",)


def part_in_flight(path: str) -> Optional[str]:
    """The relative path of a huggingface_hub '.incomplete' part anywhere
    under the folder, or None."""
    for root, _dirs, files in os.walk(path):
        for f in sorted(files):
            if f.endswith(".incomplete"):
                return os.path.relpath(os.path.join(root, f), path)
    return None


def missing(path: str, weights_suffixes: Tuple[str, ...] = WEIGHTS_SUFFIXES) -> Optional[str]:
    """What the folder lacks to be a whole snapshot, as a phrase naming the
    file ("model-00002-of-00004.safetensors is missing"), or None when it is
    whole. `weights_suffixes` says what counts as a weights file where no
    index names the shards (the media readers accept pytorch_model.bin too)."""
    if not os.path.isdir(path):
        return "the folder is absent"
    if not os.path.isfile(os.path.join(path, "config.json")):
        return "config.json is missing"
    part = part_in_flight(path)
    if part is not None:
        return f"{part} is a part still in flight"
    index = os.path.join(path, "model.safetensors.index.json")
    if os.path.isfile(index):
        try:
            with open(index) as f:
                shards = sorted(set(json.load(f).get("weight_map", {}).values()))
        except (OSError, ValueError):
            return "model.safetensors.index.json is unreadable"
        if not shards:
            return "model.safetensors.index.json names no shard"
        for s in shards:
            if not os.path.isfile(os.path.join(path, s)):
                return f"{s} is missing"
        return None
    if any(f.endswith(weights_suffixes) for f in os.listdir(path)):
        return None
    return "no weights file (" + " or ".join(weights_suffixes) + ") is there"


def complete(path: str) -> bool:
    return missing(path) is None
