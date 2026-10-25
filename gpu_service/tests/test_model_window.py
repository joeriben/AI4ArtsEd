"""The window and the budget come out of the model file, and are checked against it.

Rule 15 closes on "a rule without a count is an intention". The count here is:
no entry carries a typed context window, and the KV figure the coordinator is
told matches what the file declares — including the head sizes the file gives
explicitly, which is where the first version of this arithmetic was 12 GB short
for Qwen 3.5 4B.
"""
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.llm_backend import (  # noqa: E402
    MODEL_CONFIGS,
    _gguf_metadata,
    kv_cache_mb,
    resolve_window,
)

_TS = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_SF = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?",
       10: "Q", 11: "q", 12: "d"}


def _independent_header(path):
    """A second reader, written from the GGUF specification rather than from
    the one under test, so an error in the walk cannot agree with itself."""
    out = {}
    with open(path, "rb") as f:
        assert f.read(4) == b"GGUF"
        struct.unpack("<I", f.read(4))[0]
        struct.unpack("<Q", f.read(8))[0]
        for _ in range(struct.unpack("<Q", f.read(8))[0]):
            klen = struct.unpack("<Q", f.read(8))[0]
            key = f.read(klen).decode("utf-8", "replace")
            vtype = struct.unpack("<I", f.read(4))[0]
            if vtype == 8:
                vlen = struct.unpack("<Q", f.read(8))[0]
                value = f.read(vlen).decode("utf-8", "replace")
            elif vtype == 9:
                etype = struct.unpack("<I", f.read(4))[0]
                count = struct.unpack("<Q", f.read(8))[0]
                if etype == 8:
                    for _ in range(count):
                        f.seek(struct.unpack("<Q", f.read(8))[0], 1)
                    value = None
                else:
                    raw = [struct.unpack("<" + _SF[etype], f.read(_TS[etype]))[0]
                           for _ in range(count)]
                    value = max(raw) if raw else None
            else:
                value = struct.unpack("<" + _SF[vtype], f.read(_TS[vtype]))[0]
            out[key] = value
    return out


def _present():
    return [(alias, c) for alias, c in MODEL_CONFIGS.items()
            if os.path.exists(c["model_path"])]


def test_no_entry_carries_a_typed_window():
    """The table declares None; the number arrives from the file or not at all."""
    import re
    src = open(os.path.join(os.path.dirname(__file__), "..", "services",
                            "llm_backend.py")).read()
    table = src[src.index("MODEL_CONFIGS = {"):src.index("\n}\n", src.index("MODEL_CONFIGS = {"))]
    typed = re.findall(r'"n_ctx":\s*(\d+)', table)
    assert typed == [], f"a context window was typed into the table: {typed}"


@pytest.mark.skipif(not _present(), reason="no model files on this host")
def test_window_is_the_one_the_file_declares():
    for alias, config in _present():
        resolve_window(alias)
        declared = _independent_header(config["model_path"])
        arch = declared["general.architecture"]
        assert config["n_ctx"] == declared[f"{arch}.context_length"], alias


@pytest.mark.skipif(not _present(), reason="no model files on this host")
def test_kv_uses_the_head_sizes_the_file_declares():
    """embedding_length / head_count is a guess, and for four of the models on
    this host it is the wrong one — Qwen 3.5 4B declares 256 where the division
    gives 160, which is a 12 GB error at that model's window."""
    for alias, config in _present():
        path = config["model_path"]
        d = _independent_header(path)
        arch = d["general.architecture"]
        layers = d[f"{arch}.block_count"]
        kv_heads = d[f"{arch}.attention.head_count_kv"]
        fallback = d[f"{arch}.embedding_length"] // d[f"{arch}.attention.head_count"]
        k = d.get(f"{arch}.attention.key_length", fallback)
        v = d.get(f"{arch}.attention.value_length", fallback)
        n_ctx = d[f"{arch}.context_length"]
        swa = d.get(f"{arch}.attention.sliding_window")

        expected = layers * n_ctx * kv_heads * (k + v) * 2 / (1024 * 1024)
        got = kv_cache_mb(path, n_ctx)
        if swa and swa < n_ctx:
            # A sliding window makes the cache smaller, never larger.
            assert got <= expected + 1, alias
        else:
            assert abs(got - expected) < 1, f"{alias}: {got} vs {expected}"


@pytest.mark.skipif(not _present(), reason="no model files on this host")
def test_budget_covers_weights_and_cache():
    for alias, config in _present():
        resolve_window(alias)
        weights = os.path.getsize(config["model_path"]) / (1024 * 1024)
        cache = kv_cache_mb(config["model_path"], config["n_ctx"])
        assert config["estimated_vram_mb"] >= weights + cache, alias


@pytest.mark.skipif(not _present(), reason="no model files on this host")
def test_a_replaced_file_is_read_again():
    alias, config = _present()[0]
    resolve_window(alias)
    config["n_ctx"] = 4096          # as if somebody had typed one
    config["_window_from"] = "stale"
    resolve_window(alias)
    assert config["n_ctx"] != 4096, "a stale stamp did not force a re-read"


def test_metadata_refuses_a_file_that_is_not_gguf(tmp_path):
    bogus = tmp_path / "not.gguf"
    bogus.write_bytes(b"XXXX" + b"\0" * 64)
    with pytest.raises(ValueError):
        _gguf_metadata(str(bogus))


# ── Synthetic headers, for the shapes no file on this host has ──────────────

def _write_gguf(path, arch, kv, version=3):
    """A minimal GGUF header. kv maps a full key name to (type_id, value)."""
    with open(path, "wb") as f:
        f.write(b"GGUF")
        f.write(struct.pack("<I", version))
        f.write(struct.pack("<Q", 0))                 # tensor count
        f.write(struct.pack("<Q", len(kv) + 1))       # kv count
        def put_str(text):
            raw = text.encode("utf-8")
            f.write(struct.pack("<Q", len(raw))); f.write(raw)
        put_str("general.architecture")
        f.write(struct.pack("<I", 8)); put_str(arch)
        for key, (vtype, value) in kv.items():
            put_str(key)
            f.write(struct.pack("<I", vtype))
            if vtype == 8:
                put_str(value)
            elif vtype == 7:
                f.write(struct.pack("<?", value))
            else:
                f.write(struct.pack("<" + _SF[vtype], value))


def _base(arch):
    return {
        f"{arch}.context_length": (4, 32768),
        f"{arch}.block_count": (4, 8),
        f"{arch}.embedding_length": (4, 512),
        f"{arch}.attention.head_count": (4, 8),
        f"{arch}.attention.head_count_kv": (4, 2),
    }


def test_an_architecture_name_with_a_dot_is_stripped_by_name(tmp_path):
    p = tmp_path / "dotted.gguf"
    _write_gguf(str(p), "qwen3.5", _base("qwen3.5"))
    m = _gguf_metadata(str(p))
    assert m["context_length"] == 32768
    assert m["block_count"] == 8


def test_head_count_kv_may_be_absent(tmp_path):
    """llama.cpp reads it optional and falls back to head_count; a valid
    multi-head file that leaves it out has to stay loadable."""
    arch = "mha"
    kv = _base(arch)
    del kv[f"{arch}.attention.head_count_kv"]
    p = tmp_path / "mha.gguf"
    _write_gguf(str(p), arch, kv)
    assert _gguf_metadata(str(p))["attention.head_count_kv"] == 8


def test_a_window_written_as_a_bool_is_refused(tmp_path):
    """int(True) is 1, and a child spawned with a window of one token is worse
    than one that never spawns."""
    arch = "boolish"
    kv = _base(arch)
    kv[f"{arch}.context_length"] = (7, True)
    p = tmp_path / "boolish.gguf"
    _write_gguf(str(p), arch, kv)
    with pytest.raises(ValueError):
        _gguf_metadata(str(p))


def test_an_unknown_value_type_says_so(tmp_path):
    p = tmp_path / "future.gguf"
    _write_gguf(str(p), "future", _base("future"))
    raw = bytearray(p.read_bytes())
    marker = b"future.block_count"
    at = raw.index(marker) + len(marker)
    raw[at:at + 4] = struct.pack("<I", 42)
    p.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="value type"):
        _gguf_metadata(str(p))


@pytest.mark.skipif(not [c for _, c in _present() if c.get("mmproj_path")],
                    reason="no vision model on this host")
def test_a_projector_is_part_of_the_budget():
    """llama.cpp puts the mmproj on the card with the weights unless it is told
    not to, and this service never tells it not to."""
    for alias, config in _present():
        mmproj = config.get("mmproj_path")
        if not mmproj or not os.path.exists(mmproj):
            continue
        resolve_window(alias)
        both = (os.path.getsize(config["model_path"]) + os.path.getsize(mmproj)) / (1024 * 1024)
        assert config["estimated_vram_mb"] >= both, alias


def test_the_micro_batch_is_the_one_the_child_spawns_with():
    from services.llm_child import UBATCH_SIZE
    from services.llm_backend import _UBATCH
    assert _UBATCH == UBATCH_SIZE
