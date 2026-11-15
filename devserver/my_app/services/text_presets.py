"""The model rows of the Latent Text Lab, read off the one table of local
language models, config/local_llm_weights.json.

Stage 5 of the move to ComfyUI. The GPU service answered
/api/text/presets from its configuration and loaded a named model from the
Hugging Face cache on demand; since the move a model of these rows is a
folder under <ComfyUI>/models/llm/, whole or not there, and the surfaces are
told which. The rows stood in a table of their own, config/text_presets.json,
until 2026-11-08; since then an entry of the one table says where its model
stands on them ('text_rows'), and this module is a view of that table in the
shape the Text Lab read before: {row: {key: member}}, a member carrying the
repository as `id`. The lists are a didactic choice, and this module adds two
facts per member: whether its weights are installed, and whether it fits the
card.

A model is named by its repository (what the surfaces send) or by its alias
in the table; both find the same entry until the surfaces send the alias.

Fit is read against the card's size (services/gpu_card): ComfyUI takes other
models off the card to make room, so the card's size is the measure. The
loader runs a checkpoint as shipped (BF16, or the FP8 the maker published);
there is no quantized load, so `suggested_quant` is "bf16" where the model
fits and None where it does not, the two values the Representation
Engineering surface reads. A member whose entry says trust_remote_code is
held back with that reason: the loader executes no code from a repository.

Besides the rows, one pseudo-row, ALL ("all"): every member of every row
once, smallest first, with the model a surface starts on. The
Representation Engineering surface reads it since 2026-11-08, at the
project lead's word that it offer every text model in one list.
"""
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import config

from my_app.services import local_llm_weights

logger = logging.getLogger(__name__)

DEVSERVER_ROOT = config.DEVSERVER_DIR
# The one table the rows are read off.
TABLE_FILE = local_llm_weights.TABLE_FILE

# What a load takes beyond the weights, as the GPU service counted it: the
# activations of a reading and the key/value cache of a short generation.
FIT_MARGIN = 1.1

# The pseudo-row that answers every member of every row in one list. It is
# no row of the table: available_scenarios does not name it, and the model
# picker, which composes its lineups from the rows, never sees it.
ALL = "all"

# The table's key for the alias the Representation Engineering surface
# starts on.
DEFAULT_KEY = "representation_engineering_default"

# The fields of an entry a member carries besides its repository and its
# row's description.
_MEMBER_FIELDS = ("vram_gb", "params_b", "revision", "trust_remote_code")


def _on_rows(model_id: str) -> Optional[Tuple[str, dict]]:
    """(alias, entry) for a model on a row of the Text Lab, by its repository
    or by its alias ('local/' allowed); None for anything else, a value
    that is no string included (the routes take it from a request body)."""
    if not isinstance(model_id, str):
        return None
    e = local_llm_weights.entry(model_id)
    if e is not None:
        return (local_llm_weights.resolve_alias(model_id), e) if e.get("text_rows") else None
    for alias, e in local_llm_weights.models().items():
        if e["repo"] == model_id and e.get("text_rows"):
            return alias, e
    return None


def _member(alias: str, entry: dict, place: dict) -> dict:
    """A member as the rows carried it: the repository as `id`, the row's
    description, the Text Lab's fields of the entry, and its alias."""
    m = {"id": entry["repo"], "alias": alias, "description": place["description"]}
    for key in _MEMBER_FIELDS:
        if key in entry:
            m[key] = entry[key]
    return m


def scenarios() -> Dict[str, Dict[str, dict]]:
    """{row: {key: member}}, rows and keys in the order the head of the table
    names them ('text_rows': {row: [key, ...]}). A place an entry names that
    the head does not list, a key two entries take, and a listed key no entry
    takes are each refused with KeyError: the two halves say the same thing."""
    table = local_llm_weights.register()
    order: Dict[str, list] = table["text_rows"]
    placed: Dict[str, Dict[str, dict]] = {row: {} for row in order}
    for alias, e in table["models"].items():
        for row, place in (e.get("text_rows") or {}).items():
            if row not in placed or place["key"] not in order[row]:
                raise KeyError(f"{alias} stands on {row!r} under {place['key']!r}, which the "
                               f"head of {TABLE_FILE.name} does not list")
            if place["key"] in placed[row]:
                raise KeyError(f"{alias} and {placed[row][place['key']]['alias']} both stand "
                               f"on {row!r} under {place['key']!r}")
            placed[row][place["key"]] = _member(alias, e, place)
    empty = [f"{row}.{key}" for row, keys in order.items() for key in keys if key not in placed[row]]
    if empty:
        raise KeyError(f"no entry of {TABLE_FILE.name} stands on {', '.join(empty)}")
    return {row: {key: placed[row][key] for key in keys} for row, keys in order.items()}


def member_of(model_id: str) -> Optional[dict]:
    """The member a model is on the rows (as its first row carries it), by its
    repository or its alias; None for a model that is on no row."""
    found = _on_rows(model_id)
    if not found:
        return None
    alias, e = found
    place = next(iter(e["text_rows"].values()))
    return _member(alias, e, place)


def folder_of(model_id: str) -> str:
    """The folder under models/llm/ a repository is linked to: its id with
    the slash written as two dashes. download_textlab_models.sh writes the
    link under this name, ComfyUI's loader lists it, and the node is handed
    it. The table's 'dir' is the same name (test_local_llm_weights holds
    that)."""
    return model_id.replace("/", "--")


def dir_name(model_id: str) -> Optional[str]:
    """The folder of a member of the rows, or None for a model that is on no
    row."""
    found = _on_rows(model_id)
    return found[1]["dir"] if found else None


def held_back(model_id: str) -> Optional[str]:
    """Why a member of the rows is offered on no picker, or None.

    ComfyUI's loader (comfyui_nodes/ai4artsed_comfyui/_local_llm) reads a
    checkpoint's config with transformers' own classes and executes no code
    from the repository. A member whose entry says trust_remote_code stands
    on its row with this reason and runs nowhere until that entry is
    decided."""
    found = _on_rows(model_id)
    if found and found[1].get("trust_remote_code"):
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


def _listed(member: dict, card_gb: float) -> dict:
    m = dict(member)
    fits = float(member["vram_gb"]) * FIT_MARGIN < card_gb
    m["installed"] = is_installed(member["id"])
    m["dir"] = folder_of(member["id"])
    m["fits_bf16"] = fits
    m["suggested_quant"] = "bf16" if fits else None
    m["held_back"] = held_back(member["id"])
    return m


def _all_members(rows: Dict[str, Dict[str, dict]]) -> Dict[str, dict]:
    """Every member of every row once, keyed by its folder, smallest first.

    A member that stands on several rows is taken as its first row carries
    it, and says in `rows` and `keys` where it stands (in table order).
    Ordered by `params_b`, then `vram_gb`, then id.
    """
    found: Dict[str, dict] = {}
    for row, members in rows.items():
        for key, member in members.items():
            entry = found.setdefault(member["id"], {"member": member, "rows": [], "keys": []})
            entry["rows"].append(row)
            entry["keys"].append(key)
    ordered = sorted(found.values(), key=lambda e: (float(e["member"].get("params_b", 0)),
                                                    float(e["member"]["vram_gb"]),
                                                    e["member"]["id"]))
    out = {}
    for e in ordered:
        m = dict(e["member"])
        m["rows"], m["keys"] = e["rows"], e["keys"]
        out[folder_of(m["id"])] = m
    return out


def listing(scenario: str) -> dict:
    """What /api/text/presets answers for one row, or for ALL.

    `presets` holds the members whose weights are installed and that the
    loader runs, keyed as the row keys them; `missing` the rest of the row
    in the same shape, each saying whether it is installed and, where the
    loader runs it nowhere, why (`held_back`). The pickers read `presets`
    and compare what is there. Raises CardUnreadable while the card's size
    cannot be read; the route answers 503 with the cause.

    For ALL the answer holds every member of every row once, keyed by its
    folder name, smallest first, each with the `rows` and `keys` it stands
    under; `default` is the repository of the table's
    representation_engineering_default and `default_key` its folder while
    that member is in `presets`, else None. The Representation Engineering
    surface reads this since 2026-11-08: every text model of the Text Lab,
    in one list.
    """
    rows = scenarios()
    if scenario != ALL and scenario not in rows:
        raise KeyError(f"no row {scenario!r} in {TABLE_FILE.name}; rows: {sorted(rows)} or {ALL!r}")
    card_gb = _card_gb()
    members = _all_members(rows) if scenario == ALL else rows[scenario]
    presets, missing = {}, {}
    for key, member in members.items():
        m = _listed(member, card_gb)
        (presets if m["installed"] and not m["held_back"] else missing)[key] = m
    answer = {
        "presets": presets,
        "missing": missing,
        "scenario": scenario,
        "available_scenarios": list(rows.keys()),
        "total_vram_gb": round(card_gb, 1),
        "models_root": str(local_llm_weights.models_root()),
    }
    if scenario == ALL:
        alias = local_llm_weights.register().get(DEFAULT_KEY)
        start = member_of(alias) if alias else None
        default = start["id"] if start else None
        answer["default"] = default
        answer["default_key"] = folder_of(default) if default and folder_of(default) in presets else None
    return answer
