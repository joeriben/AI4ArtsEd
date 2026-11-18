#!/usr/bin/env python3
"""The card is booked for the key/value cache a run fills, not for its window.

Until 2026-11-16 the node booked the cache of the whole window before the
first token (_local_llm.generate and _media_reading._describe_visual: 64k;
_media_reading.describe_audio: MiDashengLM's 32,768): for Qwen 1.5 7B 32 GiB
beside 15 GB of weights, for a chat that fills a few thousand positions.
Since then CacheBooking books the prompt, one step (CACHE_STEP_TOKENS) and the
pass over the prompt with the load, and one step more each time the sequence
reaches what is booked, never past the window.

What this file holds: generate and the three readers book the prompt and one
step, whatever the window; the booking asks ComfyUI for one step more when
the sequence reaches it, counting the prompt where the sequence leaves it
out, with the generating model's own load kept on the card, and never
past the window; a sliding-window
layer is counted with its window; a card without room for the next step ends
the run at the token after it with the card's sentence, after what was
already streamed, and an answer that ended at that token stands whole; all
generations ask transformers for the cache that grows.

Run: pytest devserver/tests/test_cache_booking.py -q
"""
import sys
import threading
import types
from types import SimpleNamespace

import pytest

from test_local_llm_finite import llm  # noqa: F401  (the node module with ComfyUI stubbed)
from test_video_check_reading import package  # noqa: F401  (_media_reading with ComfyUI stubbed)


class _Tok:
    eos_token_id = 0
    pad_token_id = None

    def apply_chat_template(self, messages, **kw):
        import torch
        t = torch.tensor([[5] * 10])
        return {"input_ids": t, "attention_mask": torch.ones_like(t)}

    def decode(self, ids, skip_special_tokens=True):
        return "x" * len(ids)


class _HF:
    """Writes `n` tokens, asking the stopping criteria after each the way
    transformers does, with the whole sequence."""

    def __init__(self, torch, n):
        self.torch, self.n = torch, n

    def generate(self, **kw):
        self.seen = kw
        streamer = kw["streamer"]
        ids = kw["input_ids"]
        streamer.put(ids)
        try:
            for _ in range(self.n):
                ids = self.torch.cat([ids, self.torch.tensor([[7]])], dim=1)
                streamer.put(self.torch.tensor([[7]]))
                for criterion in kw["stopping_criteria"]:
                    criterion(ids, None)
        finally:
            streamer.end()


def _built(torch, hf):
    return types.SimpleNamespace(
        lock=threading.Lock(), vision=False, tokenizer=_Tok(), processor=None,
        config=None, module=types.SimpleNamespace(hf=hf), eos_ids=(), eos_texts=("",),
        dir_name="Some--Model", patcher=object())


def _refuse(to_load, reserve, name, keep=None):
    raise RuntimeError(f"out of memory on the card for {name}")


def test_generate_books_the_prompt_and_one_step_whatever_the_window(llm, monkeypatch):
    mod, torch = llm
    hf = _HF(torch, 3)
    booked = []
    monkeypatch.setattr(mod, "get_built", lambda d: _built(torch, hf))
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: n)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: booked.append(r) or torch.device("cpu"))
    out = mod.generate("Some--Model", messages=[{"role": "user", "content": "hi"}],
                       temperature=0.0, context_tokens=65536, enable_thinking=False)
    assert booked == [10 + mod.CACHE_STEP_TOKENS]
    assert out["completion_tokens"] == 3
    assert hf.seen["cache_implementation"] == "dynamic"
    assert any(isinstance(c, mod.CacheBooking) for c in hf.seen["stopping_criteria"])


def test_the_first_booking_holds_the_pass_over_the_prompt(llm, monkeypatch):
    mod, torch = llm
    from ai4artsed_comfyui._comfy_llm import PREFILL_BYTES_PER_TOKEN_AND_WIDTH
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: n)
    config = SimpleNamespace(text_config=SimpleNamespace(hidden_size=64))
    booking = mod.CacheBooking(SimpleNamespace(patcher=object()), config, 10, 65536, "Some--Model")
    assert booking.first_reserve() == 10 + mod.CACHE_STEP_TOKENS + 10 * 64 * PREFILL_BYTES_PER_TOKEN_AND_WIDTH


def test_the_booking_asks_for_one_step_more_where_the_sequence_reaches_it(llm, monkeypatch):
    mod, torch = llm
    monkeypatch.setattr(mod, "CACHE_STEP_TOKENS", 4)
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: n * 100)
    asked = []
    monkeypatch.setattr(mod._card, "room_for",
                        lambda to_load, reserve, name, keep=None: asked.append((to_load, reserve, name)))
    booking = mod.CacheBooking(SimpleNamespace(patcher=object()), None, 10, 65536, "Some--Model")
    for length in range(11, 14):
        assert not bool(booking(torch.zeros((1, length), dtype=torch.long), None).any())
    assert asked == []
    booking(torch.zeros((1, 14), dtype=torch.long), None)
    assert asked == [(0, 4 * 100, "Some--Model")]
    for length in range(15, 18):
        booking(torch.zeros((1, length), dtype=torch.long), None)
    assert len(asked) == 1
    booking(torch.zeros((1, 18), dtype=torch.long), None)
    assert len(asked) == 2


def test_no_booking_reaches_past_the_window(llm, monkeypatch):
    mod, torch = llm
    monkeypatch.setattr(mod, "CACHE_STEP_TOKENS", 4)
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: n * 100)
    asked = []
    monkeypatch.setattr(mod._card, "room_for", lambda to_load, reserve, name, keep=None: asked.append(reserve))
    assert mod.CacheBooking(SimpleNamespace(patcher=object()), None, 10, 12, "M").first_reserve() == 12 * 100
    booking = mod.CacheBooking(SimpleNamespace(patcher=object()), None, 10, 16, "M")
    assert booking.first_reserve() == 14 * 100
    for length in range(11, 17):
        booking(torch.zeros((1, length), dtype=torch.long), None)
    assert asked == [2 * 100]


def test_a_sequence_without_the_prompt_counts_it(llm, monkeypatch):
    """MiDashengLM hands the criteria the new tokens alone."""
    mod, torch = llm
    monkeypatch.setattr(mod, "CACHE_STEP_TOKENS", 4)
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: n)
    asked = []
    monkeypatch.setattr(mod._card, "room_for", lambda *a, **k: asked.append(a))
    booking = mod.CacheBooking(SimpleNamespace(patcher=object()), None, 10, 65536, "Reader", offset=10)
    booking(torch.zeros((1, 3), dtype=torch.long), None)
    assert asked == []
    booking(torch.zeros((1, 4), dtype=torch.long), None)
    assert len(asked) == 1


def test_the_step_keeps_the_generating_model_and_a_refusal_carries_the_cards_sentence(llm, monkeypatch):
    """Through the real _card.room_for: the load of the generating model is
    kept while others are taken off, and with no room left the card's own
    sentence ends the run, at the token after the refusal."""
    mod, torch = llm
    monkeypatch.setattr(mod, "CACHE_STEP_TOKENS", 4)
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: n * 2 ** 20)
    mm = mod.comfy.model_management
    held = SimpleNamespace(patcher=object())
    ours, other = SimpleNamespace(model=held.patcher), SimpleNamespace(model=object())
    kept = []
    monkeypatch.setattr(mm, "current_loaded_models", [other, ours])
    monkeypatch.setattr(mm, "free_memory", lambda needed, device, keep_loaded=(): kept.append(list(keep_loaded)))
    monkeypatch.setattr(mm, "get_free_memory", lambda *a, **k: 0)
    booking = mod.CacheBooking(held, None, 10, 65536, "Some--Model")
    booking(torch.zeros((1, 14), dtype=torch.long), None)
    assert kept == [[ours]]
    with pytest.raises(RuntimeError, match=r"^out of memory on the card for Some--Model.*broke off after 5 tokens"):
        booking(torch.zeros((1, 15), dtype=torch.long), None)


def test_a_card_without_room_for_the_next_step_ends_the_run_after_what_was_streamed(llm, monkeypatch):
    mod, torch = llm
    monkeypatch.setattr(mod, "CACHE_STEP_TOKENS", 2)
    monkeypatch.setattr(mod, "get_built", lambda d: _built(torch, _HF(torch, 5)))
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: n)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    monkeypatch.setattr(mod._card, "room_for", _refuse)
    shown = []
    with pytest.raises(RuntimeError, match="out of memory on the card for Some--Model.*broke off after 3 tokens"):
        mod.generate("Some--Model", messages=[{"role": "user", "content": "hi"}],
                     temperature=0.0, context_tokens=65536, enable_thinking=False,
                     on_token=shown.append)
    assert "".join(shown) == "xxx"


def test_an_answer_that_ends_at_the_refused_step_stands_whole(llm, monkeypatch):
    mod, torch = llm
    monkeypatch.setattr(mod, "CACHE_STEP_TOKENS", 2)
    monkeypatch.setattr(mod, "get_built", lambda d: _built(torch, _HF(torch, 2)))
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: n)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    monkeypatch.setattr(mod._card, "room_for", _refuse)
    out = mod.generate("Some--Model", messages=[{"role": "user", "content": "hi"}],
                       temperature=0.0, context_tokens=65536, enable_thinking=False)
    assert out["content"] == "xx"
    assert out["completion_tokens"] == 2


def test_a_sliding_window_layer_is_counted_with_its_window(llm):
    mod, torch = llm
    layer = SimpleNamespace(num_key_value_heads=2, head_dim=8, sliding_window=16)
    config = SimpleNamespace(num_hidden_layers=3, sliding_window=16, per_layer_config=[layer] * 3,
                             layer_types=["sliding_attention", "full_attention", "linear_attention"])
    per_position = 2 * 2 * 8 * 2
    assert mod._kv_cache_bytes(config, 10) == per_position * (10 + 10)
    assert mod._kv_cache_bytes(config, 100) == per_position * (16 + 100)


class _Inputs(dict):
    def to(self, device=None, dtype=None):
        return self


class _Reader:
    config = SimpleNamespace()
    dtype = None

    def generate(self, **kw):
        self.seen = kw
        kw["streamer"].end()


def test_the_image_reader_books_the_prompt_and_one_step(package, monkeypatch):
    torch, read = package.torch, package.reading
    reader = _Reader()
    built = SimpleNamespace(lock=threading.Lock(), tokenizer=_Tok(), config=SimpleNamespace(),
                            module=SimpleNamespace(hf=reader), eos_ids=(0,), patcher=object())
    booked = []
    monkeypatch.setattr(read._local_llm, "get_built", lambda name: built)
    monkeypatch.setattr(read._local_llm, "_on_card", lambda b, r: booked.append(r) or torch.device("cpu"))
    monkeypatch.setattr(read._local_llm, "_kv_cache_bytes", lambda config, tokens: tokens)
    monkeypatch.setattr(read, "_visual_inputs", lambda b, messages, video: _Inputs(
        input_ids=torch.zeros((1, 9), dtype=torch.long)))
    read.describe_image("Qwen--Qwen3-VL-8B-Instruct", "/in/picture.png", "Describe.")
    assert booked == [read.IMAGE_RESERVE_BYTES + 9 + read._local_llm.CACHE_STEP_TOKENS]
    assert reader.seen["cache_implementation"] == "dynamic"
    assert any(isinstance(c, read._local_llm.CacheBooking) for c in reader.seen["stopping_criteria"])


def test_the_audio_reader_books_the_prompt_and_one_step_and_counts_the_prompt(package, monkeypatch):
    torch, read = package.torch, package.reading
    reader = _Reader()
    processor = SimpleNamespace(
        tokenizer=_Tok(),
        apply_chat_template=lambda messages, **kw: _Inputs(input_ids=torch.zeros((1, 7), dtype=torch.long)))
    held = SimpleNamespace(lock=threading.Lock(), module=SimpleNamespace(hf=reader),
                           extra={"processor": processor}, key="mispeech--midashenglm-7b",
                           patcher=object())
    booked = []
    monkeypatch.setitem(sys.modules, "librosa",
                        SimpleNamespace(load=lambda path, sr=None, mono=True: ([0.0] * 16, 16000)))
    monkeypatch.setattr(read, "_get", lambda name, build: held)
    monkeypatch.setattr(read._card, "on_card", lambda h, r, key: booked.append(r) or torch.device("cpu"))
    monkeypatch.setattr(read._local_llm, "_kv_cache_bytes", lambda config, tokens: tokens)
    read.describe_audio("mispeech--midashenglm-7b", "/in/sound.wav", "Describe.", "SYSTEM")
    assert booked == [read.AUDIO_RESERVE_BYTES + 7 + read._local_llm.CACHE_STEP_TOKENS]
    assert reader.seen["cache_implementation"] == "dynamic"
    booking = next(c for c in reader.seen["stopping_criteria"] if isinstance(c, read._local_llm.CacheBooking))
    assert booking.offset == 7
