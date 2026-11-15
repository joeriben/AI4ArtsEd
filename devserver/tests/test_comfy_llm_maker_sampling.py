#!/usr/bin/env python3
"""The sampling of Qwen 3.5 and 3.8 in thinking mode: the values their maker gives.

devserver/config/local_llm_weights.json carries, on the rows of these models,
a "sampling" block with the model card's set for the thinking mode
(README.md, "Best Practices"). _comfy_llm.maker_sampling reads it;
_local_llm.generate samples a chat with the think block with it on either
way, ComfyUI's or transformers', in place of the caller's temperature and
repetition penalty, and leaves a chat without the block, a raw prompt and a
call at temperature 0 as they came.

  * Every block in the table holds the set with every value as a number.
  * The blocks against the model cards where the models are installed
    (skipped otherwise): every row with a block or with weights in
    ComfyUI's format carries one, and its values are the card's.
  * maker_sampling reads the table again when it changes, answers None for
    a row without a block or a table that is gone, and refuses a gap or a
    value no draw takes.
  * What ComfyUI's generate gets for the draw, from _comfy_llm.generate
    itself, and that the installed ComfyUI takes every argument of it.
  * The dispatch in _local_llm.generate, and the transformers way with the
    presence penalty the node applies there.

Run: pytest devserver/tests/test_comfy_llm_maker_sampling.py -q
"""
import ast
import json
import os
import re
import sys
import threading
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from file_modules import DEVSERVER, load_module
from test_comfy_llm_stop_watch import PACKAGE, _comfyui, _function, native  # noqa: F401 (fixture)
from test_local_llm_finite import _HF, _Tok

TABLE = DEVSERVER / "config" / "local_llm_weights.json"
KEYS = ("temperature", "top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty")
PAIR = re.compile(r"`(\w+)=([0-9.]+)`")

# Values none of which a caller below sends, so that a caller's value that
# gets through shows.
THINKING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05,
            "presence_penalty": 1.5, "repetition_penalty": 1.0}
AS_FLOATS = {k: float(v) for k, v in THINKING.items()}


def _rows():
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    return [row for row in table["models"].values() if isinstance(row, dict)]


# ---------------------------------------------------------------------------
# The table.

def test_every_sampling_block_holds_the_thinking_set_with_every_value_as_a_number():
    blocks = [(row["dir"], row["sampling"]) for row in _rows() if "sampling" in row]
    assert blocks, "no row of the table carries a sampling block"
    for dir_name, block in blocks:
        assert set(block) == {"thinking"}, f"{dir_name}: {sorted(block)}"
        values = block["thinking"]
        assert set(values) == set(KEYS), f"{dir_name}: {sorted(values)}"
        for key, value in values.items():
            assert isinstance(value, (int, float)) and not isinstance(value, bool), \
                f"{dir_name} {key}: {value!r}"
        assert values["temperature"] > 0, f"{dir_name}: a set is for sampling"
        assert values["top_k"] == int(values["top_k"]) >= 1, f"{dir_name}: top_k"
        assert 0 < values["top_p"] <= 1, f"{dir_name}: top_p"


def _card_sets(readme: str):
    """The sets of the card's "Best Practices" section, by their label. The
    label stands before the values on the same line (Qwen 3.8) or on the
    line above them (Qwen 3.5)."""
    section = readme.split("## Best Practices", 1)[1].split("\n## ", 1)[0]
    sets, label = {}, None
    for line in section.splitlines():
        pairs = PAIR.findall(line)
        head = (line.split("`", 1)[0] if pairs else line).strip(" \t-*:")
        if head:
            label = head
        if pairs and label is not None:
            sets[label] = {key: float(value) for key, value in pairs}
    return sets


def _card_thinking_set(sets):
    """The card's set for the thinking mode: the one for general tasks where
    the card gives one per kind of task (Qwen 3.5), the only one otherwise."""
    found = [values for label, values in sets.items()
             if label.lower().startswith("thinking")
             and (" for " not in label.lower() or "general tasks" in label.lower())]
    assert len(found) == 1, f"{len(found)} sets for the thinking mode among {sorted(sets)}"
    return found[0]


def test_the_blocks_are_the_sets_of_the_model_cards():
    import config
    root = Path(config.COMFYUI_BASE_PATH) / "models" / "llm"
    checked = 0
    for row in _rows():
        if not (row.get("comfy_weights") or "sampling" in row):
            continue
        readme = root / row["dir"] / "README.md"
        if not readme.is_file():
            continue
        text = readme.read_text(encoding="utf-8")
        assert "## Best Practices" in text, f"{readme} has no section 'Best Practices'"
        assert "sampling" in row, f"{row['dir']}: its card gives sampling sets, its row carries none"
        card = _card_thinking_set(_card_sets(text))
        table = {key: float(value) for key, value in row["sampling"]["thinking"].items()}
        assert table == card, f"{row['dir']}: the table says {table}, the card {card}"
        checked += 1
    if not checked:
        pytest.skip(f"no model with a sampling block has its folder under {root}")


# ---------------------------------------------------------------------------
# maker_sampling.

def _with_table(native, monkeypatch, tmp_path, models):
    path = tmp_path / "local_llm_weights.json"
    path.write_text(json.dumps({"models": models}), encoding="utf-8")
    monkeypatch.setattr(native, "_table_file", lambda: path)
    monkeypatch.setitem(native._table_cache, "stamp", None)
    return path


def test_maker_sampling_gives_the_thinking_set_of_the_row(native, monkeypatch, tmp_path):
    _with_table(native, monkeypatch, tmp_path, {
        "a": {"dir": "Maker--Model", "sampling": {"thinking": THINKING}},
        "b": {"dir": "Other--Model"}})
    found = native.maker_sampling("Maker--Model")
    assert found == AS_FLOATS
    assert all(type(value) is float for value in found.values())
    assert native.maker_sampling("Other--Model") is None
    assert native.maker_sampling("Not--In-The-Table") is None


def test_maker_sampling_reads_the_table_again_and_forgets_it_when_it_is_gone(native, monkeypatch, tmp_path):
    path = _with_table(native, monkeypatch, tmp_path,
                       {"a": {"dir": "Maker--Model", "sampling": {"thinking": THINKING}}})
    assert native.maker_sampling("Maker--Model")["top_k"] == 20.0
    before = path.stat()
    path.write_text(json.dumps({"models": {"a": {"dir": "Maker--Model", "sampling": {
        "thinking": {**THINKING, "top_k": 30}}}}}), encoding="utf-8")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 10 ** 9))
    assert native.maker_sampling("Maker--Model")["top_k"] == 30.0
    path.unlink()
    assert native.maker_sampling("Maker--Model") is None


@pytest.mark.parametrize("broken", [
    {"instruct": THINKING},
    {"thinking": {k: v for k, v in THINKING.items() if k != "min_p"}},
    {"thinking": {**THINKING, "presence_penalty": None}},
    {"thinking": {**THINKING, "top_k": True}},
    {"thinking": {**THINKING, "temperature": float("nan")}},
    {"thinking": {**THINKING, "temperature": 0.0}},
    {"thinking": {**THINKING, "top_k": 0}},
    {"thinking": {**THINKING, "top_k": 20.5}},
    {"thinking": {**THINKING, "temperature": float("inf")}},
    {"thinking": {**THINKING, "presence_penalty": float("nan")}},
    {"thinking": {**THINKING, "top_p": 1.5}},
    {"thinking": {**THINKING, "top_p": 0.0}},
    {"thinking": {**THINKING, "min_p": -0.1}},
    {"thinking": {**THINKING, "min_p": 1.5}},
    {"thinking": {**THINKING, "repetition_penalty": 0.0}},
])
def test_maker_sampling_refuses_a_gap_or_a_value_no_draw_takes(native, monkeypatch, tmp_path, broken):
    _with_table(native, monkeypatch, tmp_path, {"a": {"dir": "Maker--Model", "sampling": broken}})
    with pytest.raises(ValueError, match="Maker--Model"):
        native.maker_sampling("Maker--Model")


# ---------------------------------------------------------------------------
# The draw on ComfyUI's way.

# The folder's generation config as _load reads it; values no fixed number
# in the code would hit.
FOLDER = {"top_k": 50, "top_p": 0.9, "repetition_penalty": 1.1}


def _loaded(native, monkeypatch):
    """A loaded model as _comfy_llm.generate reads it, with a clip.generate
    that records what it was given and writes no token."""
    given = {}

    class Tokenizer:
        def apply_chat_template(self, turns, tokenize=False, add_generation_prompt=True,
                                enable_thinking=True):
            return "the prompt"

        def __call__(self, text, add_special_tokens=False):
            return types.SimpleNamespace(input_ids=[5, 6, 7])

        def decode(self, ids, skip_special_tokens=False):
            return "".join("w" for _ in ids)

    class Transformer:
        # generate puts its checked sample_token on the instance and takes
        # it off again; the class keeps its own, as ComfyUI's does.
        def __init__(self):
            self.model = types.SimpleNamespace(
                config=types.SimpleNamespace(stop_tokens=[1], vocab_size=100))

        def sample_token(self, *a, **k):
            return None

    def clip_generate(tokens, **kw):
        given.clear()
        given.update(kw)
        return []

    loaded = types.SimpleNamespace(
        tokenizer=Tokenizer(), lock=threading.Lock(), image_pad_id=None,
        patcher=types.SimpleNamespace(load_device="cpu"),
        transformer=Transformer(),
        clip=types.SimpleNamespace(cond_stage_model=types.SimpleNamespace(clip_name="qwen35"),
                                   generate=clip_generate),
        stop_ids=(1,), eos_texts=("<|im_end|>",), dir_name="Maker--Model",
        file="/models/some.safetensors", sampling=dict(FOLDER))
    monkeypatch.setattr(native, "get_loaded", lambda dir_name, file: loaded)
    monkeypatch.setattr(native, "_reserve_bytes", lambda *a: 0)
    monkeypatch.setattr(native, "_book", lambda n, reserve: None)
    return given


def test_comfyuis_generate_draws_with_the_makers_set_or_the_folders_config(native, monkeypatch):
    _local(native)      # _comfy_llm.generate imports from it
    given = _loaded(native, monkeypatch)
    chat = [{"role": "user", "content": "hello"}]
    drawn = ("temperature", "top_k", "top_p", "min_p", "repetition_penalty", "presence_penalty")

    native.generate("Maker--Model", "/models/some.safetensors", chat, [], None,
                    1.0, 1.0, 1, 64, None, True, AS_FLOATS)
    assert {k: given[k] for k in drawn} == {
        "temperature": 1.0, "top_k": 20, "top_p": 0.95, "min_p": 0.05,
        "repetition_penalty": 1.0, "presence_penalty": 1.5}
    assert type(given["top_k"]) is int and given["do_sample"] is True

    native.generate("Maker--Model", "/models/some.safetensors", chat, [], None,
                    0.3, 1.3, 1, 64, None, False)
    assert {k: given[k] for k in drawn} == {
        "temperature": 0.3, "top_k": 50, "top_p": 0.9, "min_p": 0.0,
        "repetition_penalty": 1.3, "presence_penalty": 0.0}

    native.generate("Maker--Model", "/models/some.safetensors", chat, [], None,
                    0.3, None, 1, 64, None, False)
    assert given["repetition_penalty"] == 1.1, "without the caller's, the folder's"


def test_the_installed_comfyui_takes_every_argument_of_the_draw(native):
    root = _comfyui()
    tree = ast.parse((root / "comfy" / "sd.py").read_text(encoding="utf-8"))
    generate = _function(tree, "CLIP", "generate")
    names = {a.arg for a in generate.args.args + generate.args.kwonlyargs}
    folder = types.SimpleNamespace(sampling=dict(FOLDER))
    for maker in (None, AS_FLOATS):
        missing = set(native._sampling_args(folder, maker, None)) - names
        assert not missing, f"CLIP.generate of the installed ComfyUI takes no {sorted(missing)}"


# ---------------------------------------------------------------------------
# The dispatch, and the transformers way.

def _local(native):
    """_local_llm beside the fixture's _comfy_llm, which its generate imports."""
    pytest.importorskip("transformers")
    return load_module("ai4artsed_comfyui._local_llm", PACKAGE / "_local_llm.py", register=True)


def test_a_chat_with_the_think_block_takes_the_makers_set_and_every_other_call_the_callers(
        native, monkeypatch):
    llm = _local(native)
    asked, seen = [], []

    def maker_sampling(dir_name):
        asked.append(dir_name)
        return dict(AS_FLOATS)

    def answer(dir_name, file, messages, pils, prompt, temperature, repetition_penalty, seed,
               context_tokens, on_token, enable_thinking, maker=None):
        seen.append((temperature, repetition_penalty, maker))
        return {}

    monkeypatch.setattr(native, "maker_sampling", maker_sampling)
    monkeypatch.setattr(native, "weights_file", lambda dir_name, fmt=None: "/models/some.safetensors")
    monkeypatch.setattr(native, "generate", answer)
    chat = [{"role": "user", "content": "hello"}]
    llm.generate("Some--Model", messages=chat, temperature=0.3, repetition_penalty=1.5)
    llm.generate("Some--Model", messages=chat, temperature=0.3, repetition_penalty=1.5,
                 enable_thinking=False)
    llm.generate("Some--Model", prompt="hello", temperature=0.3, repetition_penalty=1.5)
    llm.generate("Some--Model", messages=chat, temperature=0.0, repetition_penalty=1.5)
    assert asked == ["Some--Model"]
    assert seen == [(1.0, 1.0, AS_FLOATS), (0.3, 1.5, None), (0.3, 1.5, None), (0.0, 1.5, None)]


def _on_transformers(native, monkeypatch, maker):
    llm = _local(native)
    import torch
    hf = _HF(torch)
    built = types.SimpleNamespace(
        lock=threading.Lock(), vision=False, tokenizer=_Tok(), config=None,
        module=types.SimpleNamespace(hf=hf), eos_ids=(), eos_texts=("",), dir_name="Maker--Model")
    monkeypatch.setattr(llm, "get_built", lambda dir_name: built)
    monkeypatch.setattr(llm, "_kv_cache_bytes", lambda config, n: 0)
    monkeypatch.setattr(llm, "_on_card", lambda b, reserve: torch.device("cpu"))
    monkeypatch.setattr(native, "weights_file", lambda dir_name, fmt=None: None)
    monkeypatch.setattr(native, "maker_sampling", lambda dir_name: dict(maker))
    return llm, hf


def _run(llm):
    # _HF hands the guard nan scores, and the guard ends the run; what
    # matters here is what generate was given.
    with pytest.raises(RuntimeError, match="no token can be taken"):
        llm.generate("Maker--Model", messages=[{"role": "user", "content": "hello"}],
                     temperature=0.3, repetition_penalty=1.5, context_tokens=64)


def test_the_transformers_way_takes_the_makers_set_and_its_presence_penalty(native, monkeypatch, caplog):
    llm, hf = _on_transformers(native, monkeypatch, AS_FLOATS)
    with caplog.at_level("INFO"):
        _run(llm)
    given = {key: hf.seen.get(key) for key in ("temperature", "top_k", "top_p", "min_p",
                                               "repetition_penalty", "do_sample")}
    assert given == {"temperature": 1.0, "top_k": 20, "top_p": 0.95, "min_p": 0.05,
                     "repetition_penalty": 1.0, "do_sample": True}
    assert "presence_penalty" not in hf.seen
    presence = [p for p in hf.seen["logits_processor"] if isinstance(p, llm._Presence)]
    assert len(presence) == 1 and presence[0].penalty == 1.5
    assert presence[0].prompt_len == hf.seen["input_ids"].shape[1], "the prompt is not penalised"
    assert "the caller sent temperature 0.3, repetition penalty 1.5" in caplog.text


def test_a_min_p_or_presence_penalty_of_0_adds_nothing_on_the_transformers_way(native, monkeypatch):
    llm, hf = _on_transformers(native, monkeypatch, {**AS_FLOATS, "min_p": 0.0, "presence_penalty": 0.0})
    _run(llm)
    assert "min_p" not in hf.seen, "a min_p of 0 adds a filter that filters nothing"
    assert not any(isinstance(p, llm._Presence) for p in hf.seen["logits_processor"])


def test_the_presence_penalty_counts_what_the_answer_wrote_and_not_the_prompt(native):
    llm = _local(native)
    import torch
    presence = llm._Presence(prompt_len=3, penalty=1.5)
    scores = torch.zeros(2, 6)
    # Rows: prompt 1 2 3, then the answer so far.
    ids = torch.tensor([[1, 2, 3, 4, 4], [1, 2, 3, 5, 1]])
    out = presence(ids, scores.clone())
    assert out[0].tolist() == [0.0, 0.0, 0.0, 0.0, -1.5, 0.0], "a token written twice loses 1.5 once"
    assert out[1].tolist() == [0.0, -1.5, 0.0, 0.0, 0.0, -1.5]
    assert presence(ids[:, :3], scores.clone()).tolist() == scores.tolist(), "the prompt is not counted"
