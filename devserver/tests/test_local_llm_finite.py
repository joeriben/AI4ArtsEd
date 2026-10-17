"""
The local-LLM node ends a run whose scores no token can be taken from.

On 2026-09-15 Qwen3.8-27B-FP8, built by transformers 5.2.0 with all 64
gate_proj scales left UNEXPECTED, was asked to read a picture on the
Bildverstaendnis surface and produced scores torch.multinomial refused (nan or
inf); the assert on the device poisoned the CUDA context, and ComfyUI ended
under a core dump, every run through it with it (Nebenbefund 113). The node
now reads the scores on the host before a token is taken from them
(_local_llm._Finite) and ends that run in Python, with the cause in the
sentence. A -inf among finite scores is a masked token and passes.
"""
import sys
import threading
import types

import pytest
from comfy_stubs import ModelPatcher

from file_modules import REPO, load_module

PACKAGE = REPO / "comfyui_nodes" / "ai4artsed_comfyui"


@pytest.fixture
def llm(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
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
    for name, mod in (("comfy", comfy), ("comfy.model_management", mm), ("comfy.model_patcher", mp),
                      ("folder_paths", fp)):
        monkeypatch.setitem(sys.modules, name, mod)
    parent = types.ModuleType("ai4artsed_comfyui")
    parent.__path__ = [str(PACKAGE)]
    monkeypatch.setitem(sys.modules, "ai4artsed_comfyui", parent)
    load_module("ai4artsed_comfyui._repetition_guard", PACKAGE / "_repetition_guard.py", register=True)
    load_module("ai4artsed_comfyui._snapshot", PACKAGE / "_snapshot.py", register=True)
    # _card binds the stubs above at import; loaded afresh here, so that _card
    # calls this fixture's stubs, which a test's monkeypatch reaches. A _card
    # left in sys.modules by another test file would call that file's stubs.
    load_module("ai4artsed_comfyui._card", PACKAGE / "_card.py", register=True)
    return load_module("ai4artsed_comfyui._local_llm", PACKAGE / "_local_llm.py", register=True), torch


def test_finite_scores_pass_through_unchanged(llm):
    mod, torch = llm
    scores = torch.tensor([[0.1, -2.0, 3.5]])
    out = mod._Finite("Some--Model", 1)(torch.tensor([[1, 2, 3]]), scores)
    assert out is scores


def test_a_masked_token_passes(llm):
    """-inf is what transformers' own processors write for a token they
    forbid (no-repeat n-grams, minimum length, suppressed tokens); softmax
    makes it a zero, and multinomial draws from the rest."""
    mod, torch = llm
    scores = torch.tensor([[0.1, float("-inf"), 3.5]])
    out = mod._Finite("Some--Model", 1)(torch.tensor([[1, 2, 3]]), scores)
    assert out is scores


@pytest.mark.parametrize("row", [
    [0.1, float("nan"), 3.5],
    [0.1, float("inf"), 3.5],
    [float("-inf"), float("-inf"), float("-inf")],
], ids=["nan", "+inf", "no finite value"])
def test_scores_no_token_can_be_taken_from_end_the_run_with_model_and_count(llm, row):
    mod, torch = llm
    scores = torch.tensor([row])
    with pytest.raises(RuntimeError) as err:
        mod._Finite("Qwen--Qwen3.8-27B-FP8", 2)(torch.tensor([[1, 2, 3, 4]]), scores)
    text = str(err.value)
    assert "Qwen--Qwen3.8-27B-FP8" in text
    assert "no token can be taken from" in text
    assert "after 2 generated tokens" in text
    assert "LOAD REPORT" in text


def test_a_bad_row_in_a_batch_is_found(llm):
    mod, torch = llm
    scores = torch.tensor([[0.1, -2.0, 3.5], [float("-inf")] * 3])
    with pytest.raises(RuntimeError):
        mod._Finite("Some--Model", 1)(torch.tensor([[1, 2, 3], [1, 2, 3]]), scores)


class _Tok:
    """A tokenizer with one id per word and a chat template that is the words."""
    eos_token_id = 0
    pad_token_id = None

    def apply_chat_template(self, messages, **kw):
        import torch
        ids = [1 + (ord(c) % 90) for m in messages for c in str(m.get("content", ""))][:6]
        t = torch.tensor([ids])
        return {"input_ids": t, "attention_mask": torch.ones_like(t)}

    def decode(self, ids, skip_special_tokens=True):
        return " ".join("w" for _ in ids)


class _HF:
    """A model whose first scores are nan: what generate receives from the
    node is the guard, and the guard is what has to answer."""

    def __init__(self, torch):
        self.torch = torch
        self.seen = None

    def generate(self, **kw):
        self.seen = kw
        scores = self.torch.full((1, 5), float("nan"))
        for proc in kw["logits_processor"]:
            proc(kw["input_ids"], scores)
        raise AssertionError("sampling was reached with nan scores")


def test_generate_wires_the_guard_and_hands_its_sentence_to_the_caller(llm, monkeypatch):
    mod, torch = llm
    hf = _HF(torch)
    built = types.SimpleNamespace(
        lock=threading.Lock(), vision=False, tokenizer=_Tok(), config=None,
        module=types.SimpleNamespace(hf=hf), eos_ids=(), eos_texts=("",), dir_name="Broken--Model")
    monkeypatch.setattr(mod, "get_built", lambda d: built)
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: 0)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    with pytest.raises(RuntimeError) as err:
        mod.generate("Broken--Model", messages=[{"role": "user", "content": "hello"}],
                     temperature=0.7, context_tokens=64)
    assert "Broken--Model produced scores no token can be taken from" in str(err.value)
    assert "after 0 generated tokens" in str(err.value)
    procs = hf.seen["logits_processor"]
    assert any(isinstance(p, mod._Finite) for p in procs)
    assert hf.seen["do_sample"] is True
