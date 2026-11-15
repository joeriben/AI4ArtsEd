#!/usr/bin/env python3
"""The stop list that reads the tokens along, against ComfyUI's decode loops.

comfyui_nodes/ai4artsed_comfyui/_comfy_llm.py runs Qwen 3.5 and 3.8 on
ComfyUI's own implementation, whose two decode loops return the answer whole.
The module puts a list of its own on the model config's stop_tokens for one
generate (_Watch) and reads each token when the loop asks `token in
stop_tokens`. That holds as long as ComfyUI asks where it asked in the
release the module was checked against. This file holds three things:

  * _Watch against loops written here in the three forms ComfyUI asks in
    (the plain loop, the loop head of the MTP decode, its generator
    expression per step), with a halt, and with a window of one token.
  * The pinned release: the module's PINNED_COMFYUI and the row of
    docs/installation/SOFTWARE_VERSIONS.md name the same one.
  * The installed ComfyUI, read with ast: the places that ask, how many per
    function, where the list comes from when none is handed in, and that
    the encoder hands none in. Skipped where no ComfyUI checkout is
    installed (config.COMFYUI_BASE_PATH).

Run: pytest devserver/tests/test_comfy_llm_stop_watch.py -q
"""
import ast
import re
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from comfy_stubs import ModelPatcher
from file_modules import DEVSERVER, load_module

REPO = DEVSERVER.parent
PACKAGE = REPO / "comfyui_nodes" / "ai4artsed_comfyui"
VERSIONS = REPO / "docs" / "installation" / "SOFTWARE_VERSIONS.md"
STOP = [900, 901]


@pytest.fixture
def native(monkeypatch, tmp_path):
    """_comfy_llm with ComfyUI stood in for, as test_local_llm_finite does."""
    torch = pytest.importorskip("torch")
    mm = types.ModuleType("comfy.model_management")
    mm.processing_interrupted = lambda: False
    mm.throw_exception_if_processing_interrupted = lambda: None
    mm.load_models_gpu = lambda *a, **k: None
    mm.get_torch_device = lambda: torch.device("cpu")
    mm.unet_offload_device = lambda: torch.device("cpu")
    mm.free_memory = lambda *a, **k: None
    mm.soft_empty_cache = lambda: None
    mm.get_free_memory = lambda *a, **k: 2 ** 40
    mm.minimum_inference_memory = lambda: 0
    mm.extra_reserved_memory = lambda: 0
    mm.should_use_bf16 = lambda device=None: True
    mm.current_loaded_models = []
    mp = types.ModuleType("comfy.model_patcher")
    mp.ModelPatcher = ModelPatcher
    comfy = types.ModuleType("comfy")
    comfy.model_management = mm
    comfy.model_patcher = mp
    fp = types.ModuleType("folder_paths")
    fp.models_dir = str(tmp_path)
    fp.add_model_folder_path = lambda *a, **k: None
    fp.get_folder_paths = lambda name: [str(tmp_path / name)]
    fp.get_full_path = lambda folder, name: None
    for name, mod in (("comfy", comfy), ("comfy.model_management", mm), ("comfy.model_patcher", mp),
                      ("folder_paths", fp)):
        monkeypatch.setitem(sys.modules, name, mod)
    parent = types.ModuleType("ai4artsed_comfyui")
    parent.__path__ = [str(PACKAGE)]
    monkeypatch.setitem(sys.modules, "ai4artsed_comfyui", parent)
    load_module("ai4artsed_comfyui._repetition_guard", PACKAGE / "_repetition_guard.py", register=True)
    load_module("ai4artsed_comfyui._snapshot", PACKAGE / "_snapshot.py", register=True)
    load_module("ai4artsed_comfyui._card", PACKAGE / "_card.py", register=True)
    return load_module("ai4artsed_comfyui._comfy_llm", PACKAGE / "_comfy_llm.py", register=True)


# The three forms ComfyUI asks in. The function names are the frame names
# _Watch tells the askers apart by.

def generate(stop_tokens, tokens, max_length):
    """comfy/text_encoders/llama.py, BaseGenerate.generate: one question per
    token, after it was appended."""
    out = []
    for token in tokens[:max_length]:
        out.append(token)
        if token in stop_tokens:
            break
    return out


def _generate_mtp(stop_tokens, steps, max_length):
    """comfy/text_encoders/qwen35.py, _generate_mtp: the first token is taken
    before the loop; the loop head asks about the last token; each step
    commits several tokens, asks about each in a generator expression and
    drops what follows a stop token."""
    ids = [steps[0][0]]
    rest = [steps[0][1:]] + steps[1:]
    step = 0
    while len(ids) < max_length and ids[-1] not in stop_tokens:
        if step >= len(rest):
            break
        commit = list(rest[step][:max_length - len(ids)])
        step += 1
        stop = next((i for i, t in enumerate(commit) if t in stop_tokens), None)
        if stop is not None:
            commit = commit[:stop + 1]
        ids.extend(commit)
    return ids


def _watch(native, halt_at=None):
    seen = []

    def sink(token):
        seen.append(token)
        return halt_at is not None and len(seen) >= halt_at

    return native._Watch(STOP, sink), seen


def test_the_plain_loop_is_read_token_by_token(native):
    watch, seen = _watch(native)
    out = generate(watch, [5, 6, 7, 900, 8], 10)
    assert out == [5, 6, 7, 900] == seen == watch.seen
    assert not watch.unknown and not watch.halted


def test_the_plain_loop_halts_where_the_sink_says(native):
    watch, seen = _watch(native, halt_at=2)
    out = generate(watch, [5, 6, 7, 8], 10)
    assert out == [5, 6] == watch.seen
    assert watch.halted
    assert 123 in watch, "a halt has to stay answered, whoever asks next"


def test_the_mtp_loop_is_read_once_per_token(native):
    watch, seen = _watch(native)
    out = _generate_mtp(watch, [[5, 6, 7], [8, 9], [10, 901, 11], [12]], 50)
    assert out == [5, 6, 7, 8, 9, 10, 901]
    assert watch.seen == out, "the loop head asks about tokens the step asked about before"
    assert not watch.unknown


def test_the_mtp_loop_halts_inside_a_step(native):
    watch, seen = _watch(native, halt_at=5)
    out = _generate_mtp(watch, [[5, 6, 7], [8, 9, 10], [11]], 50)
    assert out == [5, 6, 7, 8, 9], "the token the halt fell on is the last one committed"
    assert watch.seen == out and watch.halted


def test_the_mtp_loop_halts_on_its_first_token(native):
    watch, seen = _watch(native, halt_at=1)
    out = _generate_mtp(watch, [[5, 6, 7], [8]], 50)
    assert out == [5] == watch.seen


def test_a_window_of_one_token_leaves_before_it_asks(native):
    """The MTP loop takes its first token and, with room for one, leaves
    before any question: nothing is read along, and _comfy_llm.generate reads
    that one token from what came back."""
    watch, seen = _watch(native)
    out = _generate_mtp(watch, [[5, 6, 7]], 1)
    assert out == [5] and watch.seen == []


def test_the_length_cut_inside_a_step_is_read_as_committed(native):
    watch, seen = _watch(native)
    out = _generate_mtp(watch, [[5, 6], [7, 8, 9, 10]], 4)
    assert out == [5, 6, 7, 8] == watch.seen


def test_an_unknown_asker_is_answered_and_named(native):
    watch, seen = _watch(native)

    def somebody_else():
        return 900 in watch, 5 in watch

    assert somebody_else() == (True, False)
    assert watch.seen == [] and watch.unknown == {"somebody_else": 2}


def test_the_watch_is_a_list_of_the_stop_tokens(native):
    watch, _ = _watch(native)
    assert isinstance(watch, list) and list(watch) == STOP and len(watch) == 2


def test_the_reserve_follows_the_measurement(native):
    """Qwen 3.8 27B, ComfyUI 0.44.2, 2026-11-10: for a prompt of 2,223
    tokens and max_length 63,313 ComfyUI allocated 4,749,687,296 bytes of
    caches and states (messung_paket4.jsonl of the build run); the formula's
    caches and states have to cover that to within one MiB."""
    config = types.SimpleNamespace(
        hidden_size=5120, num_hidden_layers=64, num_attention_heads=24, num_key_value_heads=4, head_dim=256,
        layer_types=[("full_attention" if i % 4 == 3 else "linear_attention") for i in range(64)],
        linear_num_value_heads=48, linear_num_key_heads=16, linear_key_head_dim=128,
        linear_value_head_dim=128, conv_kernel_size=4)
    transformer = types.SimpleNamespace(model=types.SimpleNamespace(config=config), mtp=object())
    prompt, max_length = 2223, 63313
    booked = native._reserve_bytes(transformer, prompt, max_length, None)
    caches_and_states = (booked - native.FIXED_WORK_BYTES
                         - prompt * 5120 * native.PREFILL_BYTES_PER_TOKEN_AND_WIDTH)
    assert abs(caches_and_states - 4_749_687_296) < 2 ** 20
    # No cap below the window: the reserve grows with every position.
    assert native._reserve_bytes(transformer, prompt, max_length + 1, None) > booked


def test_scores_no_token_can_be_taken_from_end_the_run_before_the_draw(native):
    """What _local_llm._Finite does on the transformers way: a nan, a +inf
    or a row without a finite value never reaches torch.multinomial."""
    import torch
    drawn = []

    def sample_token(logits, *args, **kwargs):
        drawn.append(tuple(logits.shape))
        return torch.zeros(logits.shape[0], 1, dtype=torch.long)

    model = types.SimpleNamespace(dir_name="some-model", file="/models/some.safetensors")
    reader = types.SimpleNamespace(tokens=7)
    checked = native._finite_sampling(model, reader, sample_token)

    good = torch.zeros(2, 5)
    good[0, 1] = float("-inf")          # a masked token among finite scores passes
    assert checked(good, 0.7, do_sample=True).shape == (2, 1)
    assert drawn == [(2, 5)]

    for bad in (torch.tensor([[0.0, float("nan")]]), torch.tensor([[0.0, float("inf")]]),
                torch.tensor([[0.0, 1.0], [float("-inf"), float("-inf")]])):
        with pytest.raises(RuntimeError, match="after 7 generated tokens"):
            checked(bad, 0.7)
    assert drawn == [(2, 5)], "a draw was made from scores none can be taken from"


def test_a_load_that_ram_does_not_hold_drops_this_ways_older_models_first(native, monkeypatch, tmp_path):
    """ComfyUI's loader keeps a model's weights in host RAM (card run M4b,
    2026-11-10: two 27B left 4,350 MiB of 62 GB available). A load says
    what its file weighs; while RAM does not hold that and the headroom, the
    oldest model of this way goes, and a model already held is handed out
    without a question about RAM."""
    import comfy.model_management as mm
    mm.cleanup_models_gc = lambda: None

    class Module:
        pass

    def held(key):
        return types.SimpleNamespace(key=key, module=Module(), patcher=object(), weight_bytes=0)

    loaded = []

    def load(key):
        loaded.append(key)
        return held(key)

    files = {}
    for name, size in (("a", 30), ("b", 30), ("c", 10)):
        files[name] = tmp_path / f"{name}.safetensors"
        files[name].write_bytes(b"0" * size)
    registry = native._card.Registry("LLM (ComfyUI), test", 3)
    monkeypatch.setattr(native, "_registry", registry)
    monkeypatch.setattr(native, "_load", load)
    monkeypatch.setattr(native, "_ram_headroom", lambda: 8)
    # RAM as a ledger: 62 in all, what the registry holds is taken from it.
    sizes = {f"{n}|{f}": f.stat().st_size for n, f in files.items()}
    monkeypatch.setattr(native, "_ram_available", lambda: 62 - sum(sizes[k] for k in registry.keys()))

    key = {n: f"{n}|{f}" for n, f in files.items()}
    native.get_loaded("a", str(files["a"]))
    assert registry.keys() == [key["a"]]
    # 32 available, b needs 30 + 8: a goes first.
    native.get_loaded("b", str(files["b"]))
    assert registry.keys() == [key["b"]]
    # 32 available, c needs 10 + 8: b stays.
    native.get_loaded("c", str(files["c"]))
    assert registry.keys() == [key["b"], key["c"]]
    # Held models are handed out as they are, whatever RAM says.
    monkeypatch.setattr(native, "_ram_available", lambda: 0)
    native.get_loaded("b", str(files["b"]))
    assert registry.keys() == [key["b"], key["c"]] and loaded == [key["a"], key["b"], key["c"]]
    # 22 available, a needs 30 + 8: the older one (c, b was used last) goes, then b.
    monkeypatch.setattr(native, "_ram_available", lambda: 62 - sum(sizes[k] for k in registry.keys()))
    native.get_loaded("a", str(files["a"]))
    assert registry.keys() == [key["a"]]


def test_the_pinned_release_is_the_documented_one(native):
    text = VERSIONS.read_text(encoding="utf-8")
    row = next((line for line in text.splitlines() if line.startswith("| `dlbackend/ComfyUI/`")), None)
    assert row, "SOFTWARE_VERSIONS.md has no row for dlbackend/ComfyUI/"
    assert f"v{native.PINNED_COMFYUI}" in row, (
        f"_comfy_llm.PINNED_COMFYUI is {native.PINNED_COMFYUI} and the row of SOFTWARE_VERSIONS.md "
        f"names another release; the two are changed together, after this file ran against the new one")
    assert re.search(r"\b[0-9a-f]{8}\b", row), "the row names no commit"


# ---------------------------------------------------------------------------
# The installed ComfyUI.

def _comfyui() -> Path:
    import config
    root = Path(config.COMFYUI_BASE_PATH)
    if not (root / "comfy" / "text_encoders" / "qwen35.py").is_file():
        pytest.skip(f"no ComfyUI with its own Qwen 3.5 model under {root}")
    return root


def _function(tree, class_name, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return item
    raise AssertionError(f"{class_name}.{name} is gone")


def _questions(function):
    """(inside a generator expression?, operator) for every `x in
    stop_tokens` / `x not in stop_tokens` of a function."""
    found = []

    def walk(node, in_genexpr):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 \
                and isinstance(node.ops[0], (ast.In, ast.NotIn)) \
                and isinstance(node.comparators[0], ast.Name) and node.comparators[0].id == "stop_tokens":
            found.append((in_genexpr, type(node.ops[0]).__name__))
        for child in ast.iter_child_nodes(node):
            walk(child, in_genexpr or isinstance(node, ast.GeneratorExp))

    walk(function, False)
    return found


def _defaults_to_the_config(function, source, expression):
    segment = ast.get_source_segment(source, function)
    assert re.search(r"if stop_tokens is None:\s*\n\s*stop_tokens = " + re.escape(expression), segment), (
        f"{function.name} no longer takes its stop tokens from {expression} when none are handed in")


def test_the_installed_comfyui_is_the_pinned_release(native):
    root = _comfyui()
    text = (root / "comfyui_version.py").read_text(encoding="utf-8")
    found = re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)
    assert found == native.PINNED_COMFYUI, (
        f"ComfyUI under {root} is {found}; _comfy_llm was checked against {native.PINNED_COMFYUI}. "
        f"When the tests below pass against it, move PINNED_COMFYUI and SOFTWARE_VERSIONS.md together")


def test_the_plain_loop_asks_once_per_token_in_generate():
    root = _comfyui()
    source = (root / "comfy" / "text_encoders" / "llama.py").read_text(encoding="utf-8")
    function = _function(ast.parse(source), "BaseGenerate", "generate")
    assert _questions(function) == [(False, "In")], (
        "BaseGenerate.generate asks `in stop_tokens` elsewhere than once, in its own frame: "
        f"{_questions(function)}")
    _defaults_to_the_config(function, source, "self.model.config.stop_tokens")


def test_the_mtp_loop_asks_in_its_head_and_once_per_step():
    root = _comfyui()
    source = (root / "comfy" / "text_encoders" / "qwen35.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = _function(tree, "Qwen35", "_generate_mtp")
    assert sorted(_questions(function)) == [(False, "NotIn"), (True, "In")], (
        "_generate_mtp asks about its stop tokens elsewhere than in the loop head and in one "
        f"generator expression: {_questions(function)}")
    segment = ast.get_source_segment(source, function)
    assert re.search(r"if stop_tokens is None:\s*\n\s*stop_tokens = cfg\.stop_tokens", segment)
    assert re.search(r"cfg = self\.model\.config\b", segment), "_generate_mtp reads another config"
    assert "+ max_length + 7" in segment, "the cap of the MTP decode moved (MTP_EXTRA_POSITIONS)"
    # Qwen35.generate hands on what it was given, to either loop.
    outer = _function(tree, "Qwen35", "generate")
    assert not _questions(outer)


def test_the_encoder_hands_no_stop_tokens_in():
    """Qwen35ClipModel.generate calls the model's generate without
    stop_tokens, so both loops fetch the config's list -- the one _Watch
    stands in for."""
    root = _comfyui()
    source = (root / "comfy" / "text_encoders" / "qwen35.py").read_text(encoding="utf-8")
    function = _function(ast.parse(source), "Qwen35ClipModel", "generate")
    calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "generate"]
    assert calls, "Qwen35ClipModel.generate calls no generate"
    for call in calls:
        assert "stop_tokens" not in {k.arg for k in call.keywords}
    assert "stop_tokens" not in {a.arg for a in function.args.args}


def test_a_token_is_drawn_in_sample_token_and_nowhere_else():
    """_finite_sampling stands in front of sample_token for a run. It covers
    every draw as long as torch.multinomial is called there alone and the
    MTP decode reaches it through self."""
    root = _comfyui()
    llama = (root / "comfy" / "text_encoders" / "llama.py").read_text(encoding="utf-8")
    qwen = (root / "comfy" / "text_encoders" / "qwen35.py").read_text(encoding="utf-8")

    def draws(tree):
        return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "multinomial"]

    tree = ast.parse(llama)
    inside = draws(_function(tree, "BaseGenerate", "sample_token"))
    assert len(inside) == 1 and len(draws(tree)) == 1, (
        "llama.py draws a token elsewhere than once in BaseGenerate.sample_token")
    qwen_tree = ast.parse(qwen)
    assert not draws(qwen_tree), "qwen35.py draws a token itself"
    function = _function(qwen_tree, "Qwen35", "_generate_mtp")
    calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "sample_token"]
    assert calls and all(isinstance(c.func.value, ast.Name) and c.func.value.id == "self" for c in calls), (
        "_generate_mtp reaches sample_token otherwise than through self")
