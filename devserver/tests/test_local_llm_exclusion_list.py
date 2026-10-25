"""The FP8 exclusion list of a checkpoint is read for what it names.

Qwen ships the dense Qwen3.8-27B-FP8 with `modules_to_not_convert` entries
`model.language_model.layers.N.mlp.gate` for every layer, the router of an MoE
sibling that this model does not have. transformers 5 matches an entry as an
unanchored prefix (quantizers/quantizers_utils.py should_convert_module:
`re.match(key, name)`), so `mlp.gate` excluded `mlp.gate_proj` from the FP8
conversion: gate_proj stayed a bf16 Linear over FP8 bytes, its
`weight_scale_inv` was reported UNEXPECTED for all 64 layers, and the model
answered "革革革革" (Nebenbefund 113; 2026-09-21, transformers 5.17.0).
_local_llm._read_config drops such an entry; these tests pin what is dropped
and what is not.
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from test_local_llm_finite import llm  # noqa: F401  (the fixture: the node module with ComfyUI stubbed)


TENSORS = [
    "lm_head.weight",
    "model.embed_tokens.weight",
    "model.language_model.layers.0.mlp.gate_proj.weight",
    "model.language_model.layers.0.mlp.gate_proj.weight_scale_inv",
    "model.language_model.layers.0.mlp.up_proj.weight",
    "model.language_model.layers.0.mlp.up_proj.weight_scale_inv",
    "model.language_model.layers.0.mlp.down_proj.weight",
    "model.language_model.layers.0.mlp.down_proj.weight_scale_inv",
    "model.language_model.layers.0.linear_attn.A_log",
    "model.language_model.layers.0.linear_attn.in_proj_qkvz.weight",     # bf16, no scale
    "model.language_model.layers.0.linear_attn.in_proj_ba.weight",       # bf16, no scale
    "model.language_model.layers.10.mlp.gate_proj.weight",
    "model.language_model.layers.10.mlp.gate_proj.weight_scale_inv",
    "model.visual.blocks.0.attn.proj.weight",
    "model.visual.blocks.0.mlp.linear_fc1.weight",
]


def test_a_ghost_entry_that_prefixes_a_quantised_module_is_dropped(llm):
    mod, _ = llm
    false = mod._false_prefixes(
        ["model.language_model.layers.0.mlp.gate", "model.language_model.layers.0.mlp.shared_expert_gate"],
        TENSORS)
    assert false == {"model.language_model.layers.0.mlp.gate"}


def test_entries_that_name_something_stay(llm):
    entries = [
        "lm_head",                                            # a module
        "model.embed_tokens",                                 # a module
        "model.visual",                                       # a subtree
        "model.visual.",                                      # a subtree, trailing dot
        "model.language_model.layers.0.linear_attn.A_log",    # a tensor
        "model.language_model.layers.0.mlp.gate_proj",        # the module itself
        "visual.blocks.0.attn.proj",                          # a suffix spelling
        "model.decoder.layer.*",                              # a regex
        "fc1",                                                # a bare suffix
    ]
    mod, _ = llm
    assert mod._false_prefixes(entries, TENSORS) == set()


def test_a_stem_over_modules_saved_without_a_scale_stays(llm):
    """`in_proj` before in_proj_qkvz and in_proj_ba in bf16: the list keeps
    them out of the conversion on purpose, and dropping the stem would put
    them in, with no scales to convert by."""
    mod, _ = llm
    assert mod._false_prefixes(["model.language_model.layers.0.linear_attn.in_proj"], TENSORS) == set()


def test_a_stem_over_a_subtree_stays(llm):
    """`layers.1` with no layer 1 begins layers.10 and everything under it;
    the layer itself carries no scale, so the stem is not a ghost over
    quantised modules and stays (transformers keeps layer 10 out with it)."""
    mod, _ = llm
    assert mod._false_prefixes(["model.language_model.layers.1"], TENSORS) == set()


def test_read_config_drops_the_ghost_entries_on_the_config_object(llm, tmp_path, monkeypatch):
    mod, _ = llm
    snapshot = tmp_path / "Qwen--Dense-FP8"
    snapshot.mkdir()
    (snapshot / "model.safetensors.index.json").write_text(json.dumps(
        {"weight_map": {name: "model-00001-of-00001.safetensors" for name in TENSORS}}))
    exclusions = ["lm_head", "model.language_model.layers.0.mlp.gate",
                  "model.visual.blocks.0.attn.proj"]
    config = type("Cfg", (), {})()
    config.quantization_config = {"quant_method": "fp8", "modules_to_not_convert": list(exclusions)}
    transformers = pytest.importorskip("transformers")
    monkeypatch.setattr(transformers.AutoConfig, "from_pretrained", staticmethod(lambda p: config))
    out = mod._read_config(str(snapshot))
    assert out is config
    assert out.quantization_config["modules_to_not_convert"] == [
        "lm_head", "model.visual.blocks.0.attn.proj"]


def test_read_config_leaves_a_quantization_config_that_is_no_dict_alone(llm, tmp_path, monkeypatch, caplog):
    mod, _ = llm
    config = type("Cfg", (), {})()
    config.quantization_config = type("Q", (), {"modules_to_not_convert": ["x"]})()
    transformers = pytest.importorskip("transformers")
    monkeypatch.setattr(transformers.AutoConfig, "from_pretrained", staticmethod(lambda p: config))
    with caplog.at_level("WARNING"):
        assert mod._read_config(str(tmp_path)) is config
    assert "quantization_config is a Q; the renaming and the exclusion-list check read a dict" in caplog.text


def _safetensors_bytes(names):
    header = json.dumps({"__metadata__": {"format": "pt"},
                         **{n: {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]} for n in names}}).encode()
    return struct.pack("<Q", len(header)) + header + b"\0\0\0\0"


def test_tensor_names_read_the_header_when_there_is_no_index(llm, tmp_path):
    mod, _ = llm
    snapshot = tmp_path / "single-file"
    snapshot.mkdir()
    (snapshot / "model.safetensors").write_bytes(_safetensors_bytes(["a.weight"]))
    assert mod._tensor_names(str(snapshot)) == ["a.weight"]


def test_tensor_names_fall_through_to_the_headers_when_the_index_names_nothing(llm, tmp_path):
    mod, _ = llm
    snapshot = tmp_path / "empty-index"
    snapshot.mkdir()
    (snapshot / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {}}))
    (snapshot / "model.safetensors").write_bytes(_safetensors_bytes(["a.weight"]))
    assert mod._tensor_names(str(snapshot)) == ["a.weight"]


def test_tensor_names_skip_a_file_whose_header_cannot_be_read(llm, tmp_path, caplog):
    """A git-lfs pointer under the suffix reads as a header of 10^17 bytes; a
    file of four bytes has no header; a truncated header is no JSON. Each is
    named in the log and left out, and the readable file's names come
    through."""
    mod, _ = llm
    snapshot = tmp_path / "mixed"
    snapshot.mkdir()
    (snapshot / "a-pointer.safetensors").write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
    (snapshot / "b-short.safetensors").write_bytes(b"\0\0\0\0")
    (snapshot / "c-cut.safetensors").write_bytes(struct.pack("<Q", 40) + b"{\"a.weight\": {")
    (snapshot / "d-whole.safetensors").write_bytes(_safetensors_bytes(["d.weight"]))
    with caplog.at_level("WARNING"):
        assert mod._tensor_names(str(snapshot)) == ["d.weight"]
    for name in ("a-pointer", "b-short", "c-cut"):
        assert f"{name}.safetensors: header not read" in caplog.text
