"""
Which model an adapter was trained over, read from the adapter's own file.

Which model an adapter was trained over belongs in the adapter's own metadata,
not in a user-settable field. A row of tick boxes in the Settings makes
the model look like a preference, and a wrong tick puts an adapter into a
workflow that was not trained for it — the one error the register was built to
stop (`my_app/services/lora_register.py`).

A safetensors file begins with an eight-byte little-endian length and that many
bytes of JSON. `__metadata__` in that JSON is where a trainer writes what it
trained over, and two fields say it:

  - `modelspec.architecture`, from the SAI model spec the file also names in
    `modelspec.sai_model_spec`. Every sd-scripts training of this place writes
    it, with `/lora` on the end because the file is an adapter and not a
    checkpoint. All four registered adapters carry
    `stable-diffusion-3-5-large/lora`.
  - `ss_base_model_version`, the trainer's own field. It is all the downloaded
    Flux 2 adapter in the folder carries, where it reads `flux2`; beside the
    field above the same SD 3.5 files read `5-large`.

The two spellings are NOT reconciled here. An output config names the strings
it accepts (`meta.lora_base`, read by `lora_register.carrier_configs`), so the
vocabulary of model names stays in data and a base is added by reading what
such a file says, never by guessing a string.

A file that carries neither field names no model, and an adapter that names no
model is offered to no workflow: the accelerators of the video pipelines lie in
the same folder and carry no `__metadata__` at all.

Location: devserver/my_app/services/lora_base.py
"""
from __future__ import annotations

import json
import logging
import struct
from pathlib import Path
from typing import Dict, Tuple

from config import LORA_OUTPUT_DIR

logger = logging.getLogger(__name__)

# The JSON header a trainer writes is a few hundred kilobytes at most — the
# largest in this folder is 44 KB. A length beyond this is not a header this
# platform can use, and reading it would pull an arbitrary slice of a
# multi-gigabyte file into memory.
_MAX_HEADER_BYTES = 8 * 1024 * 1024

# What a file was read to say, keyed by its name and the moment it was written,
# so a project retrained under the same name is read again.
_cache: Dict[Tuple[str, int, int], str] = {}


def declared_base(file: str) -> str:
    """The model the file says it was trained over, lower case, or "" where it
    says nothing, is not there, or holds no header this can read."""
    try:
        path = LORA_OUTPUT_DIR / file
        stat = path.stat()
    except (OSError, TypeError, ValueError):
        return ""
    key = (str(file), stat.st_mtime_ns, stat.st_size)
    hit = _cache.get(key)
    if hit is None:
        hit = _read_base(path)
        _cache[key] = hit
    return hit


def forget(file: str = "") -> None:
    """Drop what was read, for one file or for all of them. The cache is keyed
    by the write moment, so this is for a test that writes the same bytes
    twice, never for a file that changed."""
    if not file:
        _cache.clear()
        return
    for key in [k for k in _cache if k[0] == str(file)]:
        del _cache[key]


def _read_base(path: Path) -> str:
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
            if len(head) < 8:
                return ""
            length = struct.unpack("<Q", head)[0]
            if length <= 0 or length > _MAX_HEADER_BYTES:
                logger.info(
                    f"[LORA-BASE] {path.name!r} opens with a header of {length} bytes, "
                    f"past the {_MAX_HEADER_BYTES} this reads; no model read from it"
                )
                return ""
            body = fh.read(length)
            if len(body) < length:
                return ""
            meta = json.loads(body.decode("utf-8"))
    except (OSError, ValueError, struct.error, UnicodeDecodeError) as e:
        logger.info(f"[LORA-BASE] '{path.name}' carries no header this can read: {e}")
        return ""
    fields = meta.get("__metadata__") if isinstance(meta, dict) else None
    if not isinstance(fields, dict):
        return ""

    spec = fields.get("modelspec.architecture")
    if isinstance(spec, str) and spec.strip():
        base = spec.strip().lower()
        # `…/lora` says the file is an adapter, which the folder already says.
        return base[: -len("/lora")] if base.endswith("/lora") else base

    trainer = fields.get("ss_base_model_version")
    if isinstance(trainer, str) and trainer.strip():
        return trainer.strip().lower()
    return ""
