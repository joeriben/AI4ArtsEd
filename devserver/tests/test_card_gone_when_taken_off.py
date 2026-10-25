"""A model ComfyUI takes off the card is released and forgotten.

Measured 2026-09-21 on the development machine (62 GB of RAM): after two days
the ComfyUI process stood at 35.5 GB resident and 51.5 GB in swap, and the 27B
language model (28.7 GB of weights) was refused for RAM. The RAM held what
ComfyUI had taken off the card -- its own way with a model it evicts is a copy
on the offload device -- and the package's loader read every model into RAM
whole before ComfyUI moved it. Since then (_card.GoneWhenTakenOff,
_card.announce_on_card, _local_llm._build) a language model is read from disk
straight onto the card, and a model ComfyUI takes off the card is released and
forgotten; the next call reads it again. These tests pin that path against the
ComfyUI calls it hangs on.
"""
import math
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from test_local_llm_finite import llm  # noqa: F401  (the fixture: the node module with ComfyUI stubbed)


def _card_of(mod):
    return sys.modules["ai4artsed_comfyui._card"]


def _held(card, torch, key="Some--Model"):
    container = card.Container(lin=torch.nn.Linear(4, 4))
    return card.Held(key=key, patcher=card.wrap(container), module=container,
                     weight_bytes=card.module_bytes(container))


def test_a_model_comfyui_takes_off_the_card_is_released_and_forgotten(llm, monkeypatch):
    """LoadedModel.model_unload ends in detach(), which calls unpatch_model
    with the offload device. The base class would move the weights there;
    the package's patcher frees them (meta) and the registry forgets the
    model, so the next get() builds again."""
    mod, torch = llm
    card = _card_of(mod)
    mm = sys.modules["comfy.model_management"]
    monkeypatch.setattr(mm, "get_torch_device", lambda: torch.device("cuda"))
    registry = card.Registry("Test", 3)
    builds = []

    def build(key):
        builds.append(key)
        return _held(card, torch, key)

    held = registry.get("Some--Model", build, 0)
    assert registry.peek("Some--Model") is held
    assert held.patcher.load_device == torch.device("cuda")

    held.patcher.detach()          # what LoadedModel.model_unload calls

    assert registry.peek("Some--Model") is None
    assert all(p.device.type == "meta" for p in held.module.parameters())
    assert held.module.model_loaded_weight_memory == 0
    registry.get("Some--Model", build, 0)
    assert builds == ["Some--Model", "Some--Model"]


def test_a_taken_off_model_outlives_the_walk_until_the_next_get(llm, monkeypatch):
    """free_memory (comfy/model_management.py) reads the patcher after
    model_unload returns and pops the entry by index after its loop: the
    last reference to a model taken off goes at the next get(), not inside
    the walk."""
    import gc
    import weakref
    mod, torch = llm
    card = _card_of(mod)
    mm = sys.modules["comfy.model_management"]
    monkeypatch.setattr(mm, "get_torch_device", lambda: torch.device("cuda"))
    registry = card.Registry("Test", 3)
    held = registry.get("Some--Model", lambda key: _held(card, torch, key), 0)
    alive = weakref.ref(held)
    patcher = held.patcher
    del held
    patcher.detach()               # what LoadedModel.model_unload calls
    del patcher
    gc.collect()
    assert alive() is not None     # waits in _taken_off
    assert registry.peek("Some--Model") is None
    registry.get("Other--Model", lambda key: _held(card, torch, key), 0)
    gc.collect()
    assert alive() is None


def test_a_load_of_a_released_model_is_refused_with_the_cause(llm, monkeypatch):
    """partially_load with the patches changed would unpatch to RAM and load
    again; on a released model the base class's load would fail on the
    first meta tensor. The refusal names what happened instead."""
    mod, torch = llm
    card = _card_of(mod)
    mm = sys.modules["comfy.model_management"]
    monkeypatch.setattr(mm, "get_torch_device", lambda: torch.device("cuda"))
    held = _held(card, torch)
    held.patcher.detach()
    with pytest.raises(RuntimeError) as e:
        held.patcher.load(torch.device("cuda"), full_load=True)
    assert "taken off the card by ComfyUI and released" in str(e.value)


def test_a_tensor_kept_as_a_plain_attribute_leaves_the_card_too(llm, monkeypatch):
    """torch.nn.utils.weight_norm keeps the computed weight as a plain
    attribute, outside Module.to (stable_audio_tools' autoencoders)."""
    mod, torch = llm
    card = _card_of(mod)
    mm = sys.modules["comfy.model_management"]
    monkeypatch.setattr(mm, "get_torch_device", lambda: torch.device("cuda"))
    held = _held(card, torch)
    held.module.lin.computed = torch.zeros(4)
    held.patcher.detach()
    assert held.module.lin.computed.device.type == "meta"


def test_the_room_is_asked_again_after_a_collection_before_a_refusal(llm, monkeypatch):
    """A build that failed on the card leaves its tensors in a traceback
    cycle; room_for collects once before it refuses, and refuses with the
    number after the collection."""
    import gc
    mod, torch = llm
    card = _card_of(mod)
    mm = sys.modules["comfy.model_management"]
    free = iter([10, 10 ** 12])
    collected = []
    monkeypatch.setattr(mm, "get_free_memory", lambda device: next(free))
    monkeypatch.setattr(gc, "collect", lambda *a, **k: collected.append(True))
    card.room_for(7 * 2**30, 0, "Some--Model")
    assert collected == [True]

    free = iter([10, 20])
    with pytest.raises(RuntimeError) as e:
        card.room_for(7 * 2**30, 0, "Some--Model")
    assert "out of memory on the card for Some--Model" in str(e.value)
    assert collected == [True, True]


def test_nothing_is_given_up_in_part(llm):
    mod, torch = llm
    card = _card_of(mod)
    held = _held(card, torch)
    assert held.patcher.partially_unload(torch.device("cpu"), 10 ** 9) == 0
    assert all(p.device.type == "cpu" for p in held.module.parameters())


def test_a_call_without_weights_or_to_the_card_moves_nothing(llm, monkeypatch):
    """partially_load with unchanged patches calls unpatch_model without
    weights; that goes to the base class and the model stays."""
    mod, torch = llm
    card = _card_of(mod)
    mm = sys.modules["comfy.model_management"]
    monkeypatch.setattr(mm, "get_torch_device", lambda: torch.device("cuda"))
    registry = card.Registry("Test", 3)
    held = registry.get("Some--Model", lambda key: _held(card, torch, key), 0)
    held.patcher.unpatch_model(torch.device("cpu"), unpatch_weights=False)
    assert registry.peek("Some--Model") is held
    assert all(p.device.type == "cpu" for p in held.module.parameters())


def test_forgetting_collects_nothing_and_ignores_a_stranger(llm, monkeypatch):
    mod, torch = llm
    card = _card_of(mod)
    import gc
    monkeypatch.setattr(gc, "collect", lambda *a, **k: pytest.fail("forget() must not collect garbage"))
    registry = card.Registry("Test", 3)
    held = registry.get("Some--Model", lambda key: _held(card, torch, key), 0)
    stranger = _held(card, torch, "Other--Model")
    card.forget(stranger.patcher)
    assert registry.peek("Some--Model") is held
    card.forget(held.patcher)
    assert registry.peek("Some--Model") is None


def test_a_model_read_onto_the_card_is_announced_as_loaded(llm, monkeypatch):
    """The counters ModelPatcher.load writes after a full load, then the one
    call that registers a model with ComfyUI (load_models_gpu)."""
    mod, torch = llm
    card = _card_of(mod)
    mm = sys.modules["comfy.model_management"]
    monkeypatch.setattr(mm, "get_torch_device", lambda: torch.device("cuda"))
    calls = []
    monkeypatch.setattr(mm, "load_models_gpu", lambda models, **kw: calls.append((models, kw)))
    held = _held(card, torch)
    card.announce_on_card(held.patcher)
    module = held.module
    assert module.device == torch.device("cuda")
    assert module.model_lowvram is False
    assert module.model_loaded_weight_memory == held.patcher.model_size() == 4 * 4 * 4 + 4 * 4
    assert module.current_weight_patches_uuid == held.patcher.patches_uuid
    assert calls == [([held.patcher], {"force_full_load": True})]


def test_the_registry_refuses_only_what_ram_and_swap_together_cannot_hold(llm, monkeypatch):
    mod, torch = llm
    card = _card_of(mod)
    psutil = pytest.importorskip("psutil")
    monkeypatch.setattr(psutil, "virtual_memory", lambda: types.SimpleNamespace(available=1 * 2**30))
    monkeypatch.setattr(psutil, "swap_memory", lambda: types.SimpleNamespace(free=2 * 2**30))
    registry = card.Registry("Test", 3)

    def build(key):
        return _held(card, torch, key)

    registry.get("Fits--In--Ram--And--Swap", build, int(2.5 * 2**30))
    with pytest.raises(RuntimeError) as e:
        registry.get("Fits--Nowhere", build, 4 * 2**30)
    assert "4.0 GB read into RAM" in str(e.value)
    assert "1.0 GB of RAM and 2.0 GB of swap are free" in str(e.value)
    assert registry.peek("Fits--Nowhere") is None


def test_a_build_onto_the_card_asks_the_registry_nothing_about_ram(llm, monkeypatch):
    mod, torch = llm
    card = _card_of(mod)
    psutil = pytest.importorskip("psutil")
    monkeypatch.setattr(psutil, "virtual_memory", lambda: pytest.fail("RAM was asked about"))
    registry = card.Registry("Test", 3)
    registry.get("Some--Model", lambda key: _held(card, torch, key), 0)


def test_build_makes_room_reads_onto_the_card_and_announces(llm, tmp_path, monkeypatch):
    """The order of _local_llm._build: room on the card, the read with a
    device_map naming the card, the announcement."""
    mod, torch = llm
    card = _card_of(mod)
    mm = sys.modules["comfy.model_management"]
    from transformers import AutoModelForCausalLM, AutoTokenizer
    order = []
    monkeypatch.setattr(mm, "free_memory", lambda *a, **k: order.append(("free_memory", a[0])))
    monkeypatch.setattr(mm, "load_models_gpu", lambda models, **kw: order.append(("load_models_gpu", kw)))

    def fake_model(path, **kw):
        order.append(("from_pretrained", kw.get("device_map")))
        return types.SimpleNamespace(generation_config=types.SimpleNamespace(eos_token_id=0), eval=lambda: None)

    def fake_tokenizer(path):
        return types.SimpleNamespace(eos_token_id=0, decode=lambda ids: "")

    monkeypatch.setattr(AutoModelForCausalLM, "from_pretrained", staticmethod(fake_model))
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", staticmethod(fake_tokenizer))
    monkeypatch.setattr(mod, "weights_path", lambda d: str(tmp_path))
    monkeypatch.setattr(mod, "_missing_requirements", lambda p: [])
    monkeypatch.setattr(mod, "_weight_bytes", lambda p: 7 * 2**30)
    monkeypatch.setattr(mod, "_read_config", lambda p: types.SimpleNamespace(
        model_type="q", attn_logit_softcapping=None))
    built = mod._build("Some--Model")
    assert [step for step, _ in order] == ["free_memory", "from_pretrained", "load_models_gpu"]
    assert order[0][1] == math.ceil(7 * 2**30 * 1.1)    # the weights and a tenth beside them
    assert order[1][1] == {"": "cpu"}                    # the stub's card
    assert order[2][1] == {"force_full_load": True}
    assert isinstance(built.patcher, card.GoneWhenTakenOff)
    assert built.module.model_loaded_weight_memory == built.patcher.model_size()
    assert built.weight_bytes == 7 * 2**30
