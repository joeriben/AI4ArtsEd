"""The model rows of the Latent Text Lab, off the table config/text_presets.json.

Stage 5 of the move to ComfyUI. The GPU service answered
/api/text/presets from its configuration and loaded a named model from the
Hugging Face cache on demand; since the move a model of these rows is a
folder under <ComfyUI>/models/llm/, whole or not there, and the surfaces are
told which. The lists are the rows the table carries, a didactic choice, and
this module adds two facts per member: whether its weights are installed,
and whether it fits the card.

Fit is read against the card's size (services/gpu_card): ComfyUI takes other
models off the card to make room, so the card's size is the measure. The
loader runs a checkpoint as shipped (BF16, or the FP8 the maker published);
there is no quantized load, so `suggested_quant` is "bf16" where the model
fits and None where it does not, the two values the Representation
Engineering surface reads. A member whose row entry says trust_remote_code
is held back with that reason: the loader executes no code from a repository.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

import config

from my_app.services import local_llm_weights

logger = logging.getLogger(__name__)

DEVSERVER_ROOT = config.DEVSERVER_DIR
TABLE_FILE = DEVSERVER_ROOT / "config" / "text_presets.json"

# What a load takes beyond the weights, as the GPU service counted it: the
# activations of a reading and the key/value cache of a short generation.
FIT_MARGIN = 1.1


def _table() -> dict:
    with open(TABLE_FILE, encoding="utf-8") as f:
        return json.load(f)


def scenarios() -> Dict[str, Dict[str, dict]]:
    """{row: {key: member}} as the table carries it."""
    return _table()["scenarios"]


def member_of(model_id: str) -> Optional[dict]:
    """The row entry of a member, by its repository id; None for an id that
    is on no row."""
    for row in scenarios().values():
        for member in row.values():
            if member["id"] == model_id:
                return member
    return None


def folder_of(model_id: str) -> str:
    """The folder under models/llm/ a repository is linked to: its id with
    the slash written as two dashes. download_textlab_models.sh writes the
    link under this name, ComfyUI's loader lists it, and the node is handed
    it."""
    return model_id.replace("/", "--")


def dir_name(model_id: str) -> Optional[str]:
    """The folder of a member of the rows, or None for an id that is on no
    row."""
    return folder_of(model_id) if member_of(model_id) else None


def held_back(model_id: str) -> Optional[str]:
    """Why a member of the rows is offered on no picker, or None.

    ComfyUI's loader (comfyui_nodes/ai4artsed_comfyui/_local_llm) reads a
    checkpoint's config with transformers' own classes and executes no code
    from the repository. A member whose row entry says trust_remote_code
    stands on its row with this reason and runs nowhere until that entry is
    decided."""
    member = member_of(model_id)
    if member and member.get("trust_remote_code"):
        return "needs code from its repository (trust_remote_code), which the loader does not execute"
    return None


def weights_dir(model_id: str) -> Optional[Path]:
    d = dir_name(model_id)
    return local_llm_weights.models_root() / d if d else None


def is_installed(model_id: str) -> bool:
    """Whole under models/llm/ (config.json, no part in flight, every shard)."""
    d = weights_dir(model_id)
    return bool(d) and local_llm_weights.folder_is_whole(d)


def _card_gb() -> float:
    """The card's size in GiB, off ComfyUI (services/gpu_card). CardUnreadable
    while it cannot be read, and the row is refused with it: a fit said
    against no card would be a guess."""
    from my_app.services.gpu_card import read_sync
    return read_sync().total_vram_gb


def _member(member: dict, card_gb: float) -> dict:
    m = dict(member)
    fits = float(member["vram_gb"]) * FIT_MARGIN < card_gb
    m["installed"] = is_installed(member["id"])
    m["dir"] = folder_of(member["id"])
    m["fits_bf16"] = fits
    m["suggested_quant"] = "bf16" if fits else None
    m["held_back"] = held_back(member["id"])
    return m


def listing(scenario: str) -> dict:
    """What /api/text/presets answers for one row.

    `presets` holds the members whose weights are installed and that the
    loader runs, keyed as the table keys them; `missing` the rest of the row
    in the same shape, each saying whether it is installed and, where the
    loader runs it nowhere, why (`held_back`). The pickers read `presets`
    and compare what is there. Raises CardUnreadable while the card's size
    cannot be read; the route answers 503 with the cause.
    """
    rows = scenarios()
    if scenario not in rows:
        raise KeyError(f"no row {scenario!r} in {TABLE_FILE.name}; rows: {sorted(rows)}")
    card_gb = _card_gb()
    presets, missing = {}, {}
    for key, member in rows[scenario].items():
        m = _member(member, card_gb)
        (presets if m["installed"] and not m["held_back"] else missing)[key] = m
    return {
        "presets": presets,
        "missing": missing,
        "scenario": scenario,
        "available_scenarios": list(rows.keys()),
        "total_vram_gb": round(card_gb, 1),
        "models_root": str(local_llm_weights.models_root()),
    }
