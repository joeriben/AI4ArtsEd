#!/usr/bin/env python3
"""enable_thinking=False reaches the model's chat template.

Until 16.09.2026 services/llm_client accepted the flag and dropped it, the
node applied every chat template with enable_thinking=True, and the chat
route's piecewise path for a local model had no parameter for it at all. A
local reasoning model therefore thought on every call, where the caller had
asked for no reasoning included: the safety verdict of the image check
(utils/vlm_safety, enable_thinking=False) and the three comparison modes of
the chat route. On the System Prompts comparison the 9B thought until the
repetition guard stopped it and answered nothing, three presets out of
three.

What this file holds: the client writes the flag into the node's prompt on
the chat and the stream path; the chat route's local stream hands it on; the
node hands it to apply_chat_template; and a prompt that ends with the empty,
closed think block a template writes for enable_thinking=False is read as
closed, so the whole answer is content.

Run: pytest devserver/tests/test_local_llm_thinking_switch.py -q
"""
import sys
import threading
import types
from pathlib import Path
from file_modules import load_module
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from my_app.services import llm_client
from my_app.services import local_llm_weights as w
from test_local_llm_finite import llm  # noqa: F401  (the fixture: the node module with ComfyUI stubbed)

ALIAS = next(iter(w.models()))


@pytest.fixture()
def installed(monkeypatch):
    monkeypatch.setattr(w, "is_installed", lambda model_id: w.entry(model_id) is not None)


def _result(**ui):
    outputs = {llm_client.NODE_ID: {k: [v] for k, v in ui.items()}}
    return SimpleNamespace(prompt_id="p1", media_files=[], execution_time=0.1, outputs_metadata=outputs)


def _inputs(workflow):
    return workflow[llm_client.NODE_ID]["inputs"]


# --------------------------------------------------------------------------
# The client: the flag is in the node's prompt
# --------------------------------------------------------------------------

def test_the_prompt_carries_the_flag_and_thinking_is_the_default(installed):
    c = llm_client.LLMClient()
    turn = [{"role": "user", "content": "hi"}]
    assert _inputs(c._workflow(ALIAS, messages=turn))["enable_thinking"] is True
    assert _inputs(c._workflow(ALIAS, messages=turn, enable_thinking=False))["enable_thinking"] is False
    assert _inputs(c._workflow(ALIAS, messages=turn, stream=True, enable_thinking=False))["enable_thinking"] is False


def test_chat_hands_the_flag_to_the_node(installed, monkeypatch):
    seen = []

    def fake_track(workflow, on_progress=None, on_event=None):
        seen.append(_inputs(workflow)["enable_thinking"])
        return _result(content="ok", thinking="", finish_reason="stop", prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(fake_track))
    c = llm_client.LLMClient()
    turn = [{"role": "user", "content": "q"}]
    assert c.chat(ALIAS, turn, enable_thinking=False)["content"] == "ok"
    assert c.chat(ALIAS, turn)["content"] == "ok"
    assert seen == [False, True]


def test_the_stream_hands_the_flag_to_the_node(installed, monkeypatch):
    seen = []

    def fake_track(workflow, on_progress=None, on_event=None):
        seen.append(_inputs(workflow)["enable_thinking"])
        on_event(llm_client.TOKEN_EVENT, {"prompt_id": "p1", "node": "1", "text": "ok"})
        return _result(content="ok", thinking="", finish_reason="stop", prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(fake_track))
    turn = [{"role": "user", "content": "q"}]
    assert list(llm_client.LLMClient().chat_stream(ALIAS, turn, enable_thinking=False)) == [
        ("token", "ok"), ("done", "stop")]
    assert list(llm_client.LLMClient().chat_stream(ALIAS, turn)) == [("token", "ok"), ("done", "stop")]
    assert seen == [False, True]


# --------------------------------------------------------------------------
# The chat route: the local stream hands the flag on
# --------------------------------------------------------------------------

class _Backend:
    def __init__(self, seen):
        self.seen = seen

    def chat_stream(self, **kw):
        self.seen.append(kw.get("enable_thinking"))
        yield ("token", "ok")
        yield ("done", "stop")


def test_the_chat_routes_local_stream_hands_the_flag_on(monkeypatch):
    from my_app.routes import chat_routes
    from my_app.services import llm_backend

    seen = []
    monkeypatch.setattr(llm_backend, "get_llm_backend", lambda: _Backend(seen))
    turn = [{"role": "user", "content": "q"}]
    off = list(chat_routes._dispatch_single_model_stream(
        f"local/{ALIAS}", turn, 0.7, None, False, None, None))
    on = list(chat_routes._dispatch_single_model_stream(
        f"local/{ALIAS}", turn, 0.7, None, True, None, None))
    assert off[-1] == ("result", {"content": "ok", "thinking": None, "tool_calls": None})
    assert on[-1] == off[-1]
    assert seen == [False, True]


def test_the_chat_helpers_chain_carries_the_flag_to_the_local_stream(monkeypatch):
    """The way the three comparison modes go (chat_routes, the compare call:
    enable_thinking=not (...)): call_chat_helper_stream with a model picked
    by hand, down to the node's prompt."""
    from my_app.routes import chat_routes
    from my_app.services import llm_backend

    seen = []
    monkeypatch.setattr(llm_backend, "get_llm_backend", lambda: _Backend(seen))
    items = list(chat_routes.call_chat_helper_stream(
        [{"role": "user", "content": "q"}], temperature=0.7, enable_thinking=False,
        model_override=f"local/{ALIAS}"))
    assert items[0] == ("token", "ok")
    assert items[-1][0] == "result" and items[-1][1]["content"] == "ok"
    assert seen == [False]


# --------------------------------------------------------------------------
# The node: the flag reaches the template, the closed block is read as closed
# --------------------------------------------------------------------------

class _Tok:
    """A tokenizer at the granularity of the real one: the two tags, the
    line breaks and the role word are one token each, as in Qwen 3.5's
    vocabulary, so the last eight tokens of a closed ending decode to
    `\n<|im_start|>assistant\n<think>\n\n</think>\n\n` -- opener and closer both
    inside the window -- and those of an open ending to `...<think>\n`."""
    eos_token_id = 0
    pad_token_id = None

    def __init__(self):
        self.seen = []
        self.vocab = {}

    def ids(self, pieces):
        return [self.vocab.setdefault(p, 1 + len(self.vocab)) for p in pieces]

    def apply_chat_template(self, messages, **kw):
        import torch
        self.seen.append(kw.get("enable_thinking"))
        pieces = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            pieces += ["<|im_start|>", m.get("role", "user"), "\n"] + content.split() + ["<|im_end|>", "\n"]
        pieces += ["<|im_start|>", "assistant", "\n", "<think>"]
        pieces += ["\n\n", "</think>", "\n\n"] if kw.get("enable_thinking") is False else ["\n"]
        t = torch.tensor([self.ids(pieces)])
        return {"input_ids": t, "attention_mask": torch.ones_like(t)}

    def decode(self, ids, skip_special_tokens=True):
        back = {v: k for k, v in self.vocab.items()}
        return "".join(back[i] for i in ids)


class _HF:
    """A model that writes a fixed answer, one token per piece, through the streamer."""

    def __init__(self, torch, tok, pieces):
        self.torch = torch
        self.ids = tok.ids(pieces)

    def generate(self, **kw):
        self.seen = kw
        streamer = kw["streamer"]
        streamer.put(kw["input_ids"])           # the prompt; skipped (skip_prompt=True)
        for i in self.ids:
            streamer.put(self.torch.tensor([[i]]))
        streamer.end()


def _built(torch, tok, pieces, vision):
    hf = _HF(torch, tok, pieces)
    return types.SimpleNamespace(
        lock=threading.Lock(), vision=vision, tokenizer=tok,
        processor=types.SimpleNamespace(apply_chat_template=tok.apply_chat_template) if vision else None,
        config=None, module=types.SimpleNamespace(hf=hf), eos_ids=(), eos_texts=("",),
        dir_name="Some--Model")


CASES = [
    # flag, what the model writes, content, thinking
    (False, ["yes,", " plainly"], "yes, plainly", None),
    (True, ["hm", " hm", "</think>", "yes"], "yes", "hm hm"),
]


@pytest.mark.parametrize("vision", [False, True], ids=["text model", "vision model"])
@pytest.mark.parametrize("flag, pieces, content, thinking", CASES, ids=["off", "on"])
def test_the_node_hands_the_flag_to_the_template_and_reads_the_block_off_the_prompt(
        llm, monkeypatch, vision, flag, pieces, content, thinking):
    mod, torch = llm
    tok = _Tok()
    monkeypatch.setattr(mod, "get_built", lambda d: _built(torch, tok, pieces, vision))
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: 0)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    shown = []
    out = mod.generate("Some--Model", messages=[{"role": "user", "content": "hello there"}],
                       temperature=0.0, context_tokens=4096, enable_thinking=flag,
                       on_token=shown.append)
    assert tok.seen == [flag]
    assert out["content"] == content
    assert out["thinking"] == thinking
    # The stream carries the same answer, outside the block, whichever way
    # the template ended the prompt.
    assert "".join(shown).strip() == content


def test_the_node_thinks_unless_told_otherwise(llm, monkeypatch):
    """generate without the flag: the template is applied with thinking on,
    the way the proxy's in-workflow runs call it (_devserver.chat)."""
    mod, torch = llm
    tok = _Tok()
    monkeypatch.setattr(mod, "get_built", lambda d: _built(torch, tok, ["hm", "</think>", "yes"], False))
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: 0)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    out = mod.generate("Some--Model", messages=[{"role": "user", "content": "hello"}],
                       temperature=0.0, context_tokens=4096)
    assert tok.seen == [True]
    assert (out["content"], out["thinking"]) == ("yes", "hm")


def test_the_node_class_takes_the_flag_and_thinking_is_its_default(llm, monkeypatch):
    mod, torch = llm
    package = Path(__file__).resolve().parents[2] / "comfyui_nodes" / "ai4artsed_comfyui"
    node_mod = load_module("ai4artsed_comfyui.ai4artsed_local_llm",
                           package / "ai4artsed_local_llm.py")
    node = node_mod.ai4artsed_local_llm
    monkeypatch.setattr(node_mod, "installed_dirs", lambda: ["Some--Model"])
    assert node.INPUT_TYPES()["optional"]["enable_thinking"] == ("BOOLEAN", {"default": True})

    seen = {}

    def fake_generate(dir_name, **kw):
        seen.update(kw)
        return {"content": "ok", "thinking": None, "finish_reason": "stop",
                "prompt_tokens": 1, "completion_tokens": 1}

    monkeypatch.setattr(node_mod, "generate", fake_generate)
    node().run("Some--Model", "hello", 0.7, 1)
    assert seen["enable_thinking"] is True
    node().run("Some--Model", "hello", 0.7, 1, enable_thinking=False)
    assert seen["enable_thinking"] is False


# --------------------------------------------------------------------------
# The stop tokens: the tokenizer's end-of-turn token beside the config's
# --------------------------------------------------------------------------

@pytest.mark.parametrize("generation_eos, tokenizer_eos, stop", [
    (248044, 248046, (248044, 248046)),          # the 9B: derived config, one id; tokenizer <|im_end|>
    ([248046, 248044], 248046, (248046, 248044)),  # a generation config that names both
    (None, 7, (7,)),
    ([3, None], None, (3,)),
])
def test_the_stop_tokens_are_the_configs_and_the_tokenizers_end_of_turn(llm, generation_eos, tokenizer_eos, stop):
    """Qwen 3.5 4B and 9B ship no generation_config.json; the one derived
    from config.json names <|endoftext|> alone, and the model's <|im_end|>
    stopped nothing (16.09.2026: every answer ended in the tag)."""
    mod, _ = llm
    assert mod._stop_ids(generation_eos, tokenizer_eos) == stop


def test_build_puts_the_union_and_its_texts_on_the_built_model(llm, monkeypatch, tmp_path):
    """The measured case: the generation config names <|endoftext|> alone,
    the tokenizer names <|im_end|>; Built carries both ids, and their texts
    in the same order. The stubbing of test_text_probes' _build test."""
    mod, torch = llm
    from transformers import AutoModelForCausalLM, AutoTokenizer
    texts = {0: "<|endoftext|>", 2: "<|im_end|>"}
    fake_model = lambda path, **kw: types.SimpleNamespace(
        generation_config=types.SimpleNamespace(eos_token_id=0), eval=lambda: None)
    fake_tokenizer = lambda path: types.SimpleNamespace(
        eos_token_id=2, decode=lambda ids: "".join(texts[i] for i in ids))
    monkeypatch.setattr(AutoModelForCausalLM, "from_pretrained", staticmethod(fake_model))
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", staticmethod(fake_tokenizer))
    monkeypatch.setattr(mod, "weights_path", lambda d: str(tmp_path))
    monkeypatch.setattr(mod, "_missing_requirements", lambda p: [])
    monkeypatch.setattr(mod, "_weight_bytes", lambda p: 0)
    monkeypatch.setattr(mod, "_read_config", lambda p: types.SimpleNamespace(
        model_type="q", attn_logit_softcapping=None))
    built = mod._build("Some--Model")
    assert built.eos_ids == (0, 2)
    assert built.eos_texts == ("<|endoftext|>", "<|im_end|>")


def test_the_end_of_turn_token_reaches_neither_the_content_nor_the_stream(llm, monkeypatch):
    """16.09.2026: the model ends its turn with <|im_end|>, the streamer
    decodes it as text (skip_special_tokens=False), and the answer carried
    it. Stripped from the content and held out of the stream by the texts
    Built carries for the stop ids."""
    mod, torch = llm
    tok = _Tok()
    built = _built(torch, tok, ["Grün.", "<|im_end|>"], False)
    built.eos_texts = ("<|endoftext|>", "<|im_end|>")
    monkeypatch.setattr(mod, "get_built", lambda d: built)
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: 0)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    shown = []
    out = mod.generate("Some--Model", messages=[{"role": "user", "content": "hello"}],
                       temperature=0.0, context_tokens=4096, enable_thinking=False,
                       on_token=shown.append)
    assert out["content"] == "Grün."
    assert "<|im_end|>" not in "".join(shown)


def test_generate_hands_the_stop_tokens_to_the_model(llm, monkeypatch):
    mod, torch = llm
    tok = _Tok()
    built = _built(torch, tok, ["yes"], False)
    built.eos_ids = (5, 9)
    monkeypatch.setattr(mod, "get_built", lambda d: built)
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: 0)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    mod.generate("Some--Model", messages=[{"role": "user", "content": "hello"}],
                 temperature=0.0, context_tokens=4096, enable_thinking=False)
    assert built.module.hf.seen["eos_token_id"] == [5, 9]


def test_the_media_reader_stops_at_the_same_tokens(llm, monkeypatch):
    """_media_reading._answer generates on the same Built (the image and
    video readings of the Flow page); it is handed Built.eos_ids too."""
    mod, torch = llm
    import importlib
    reader = importlib.import_module("ai4artsed_comfyui._media_reading")
    seen = {}
    tok = _Tok()
    hf = _HF(torch, tok, ["a", " picture"])

    def generate(**kw):
        seen.update(kw)
        hf.generate(**kw)

    model = types.SimpleNamespace(generate=generate)
    inputs = {"input_ids": torch.tensor([tok.ids(["hello"])])}
    text = reader._answer(model, tok, inputs, 64, 1, 1, "Some--Model", eos_ids=(5, 9))
    assert text == "a picture"
    assert seen["eos_token_id"] == [5, 9]
    reader._answer(model, tok, inputs, 64, 1, 1, "Some--Model")
    assert "eos_token_id" not in seen or seen["eos_token_id"] == [5, 9]
