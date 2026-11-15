#!/usr/bin/env python3
"""Gemma 4 thinks between <|channel>thought and <channel|>, not between
<think> and </think>.

Until 2026-11-14 the node knew only Qwen's pair, and an image read on
Gemma 4 E4B came back with its whole plan and both tags in front of the
description. The block is held back from the stream and returned as
"thinking", as Qwen's is.

Run: python3 -m pytest devserver/tests/test_local_llm_gemma4_channel.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_local_llm_finite import llm  # noqa: F401  (the fixture: the node module with ComfyUI stubbed)
from test_local_llm_thinking_switch import _Tok, _built


def _run(llm, monkeypatch, pieces, flag=False):
    mod, torch = llm
    tok = _Tok()
    monkeypatch.setattr(mod, "get_built", lambda d: _built(torch, tok, pieces, True))
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: 0)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    shown = []
    out = mod.generate("Some--Model", messages=[{"role": "user", "content": "describe"}],
                       temperature=0.0, context_tokens=4096, enable_thinking=flag,
                       on_token=shown.append)
    return out, "".join(shown)


@pytest.mark.parametrize("flag", [False, True], ids=["template closed", "template opened"])
def test_the_channel_is_thinking_and_the_rest_is_the_answer(llm, monkeypatch, flag):
    # With the template opening a Qwen block, Gemma's tags do not arise; the
    # case stands here so that the walk is shown to keep both pairs apart.
    pieces = ["<|channel>", "thought", "\n", "Plan: look", " at it.", "<channel|>",
              "A farmhouse", " in a field."]
    if flag:
        pieces = ["</think>"] + pieces
    out, shown = _run(llm, monkeypatch, pieces, flag)
    assert out["content"] == "A farmhouse in a field."
    assert out["thinking"] == "Plan: look at it."
    assert shown.strip() == "A farmhouse in a field."


def test_a_block_ends_at_the_closer_of_its_own_opener(llm, monkeypatch):
    # A Qwen closer inside Gemma's channel is text of the channel.
    out, _ = _run(llm, monkeypatch, ["<|channel>", "thought\n", "a </think> b", "<channel|>", "answer"])
    assert (out["content"], out["thinking"]) == ("answer", "a </think> b")


def test_an_answer_without_a_channel_is_untouched(llm, monkeypatch):
    out, shown = _run(llm, monkeypatch, ["This vintage", " photograph."])
    assert (out["content"], out["thinking"], shown) == ("This vintage photograph.", None, "This vintage photograph.")


def test_a_closer_without_an_opener_is_ordinary_text(llm, monkeypatch):
    out, _ = _run(llm, monkeypatch, ["a <channel|> b"])
    assert out["content"] == "a <channel|> b"
