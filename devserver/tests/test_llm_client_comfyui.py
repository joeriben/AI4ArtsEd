#!/usr/bin/env python3
"""The local LLM client queues ComfyUI prompts of the platform's own node.

Stage 3 of the move to ComfyUI: services/llm_client no
longer speaks to the GPU service; every local chat, raw completion and image
reading is one prompt of ai4artsed_local_llm, tracked over ComfyUI's
websocket. What this file holds it to: the prompt it builds, the contracts its
callers have always had (chat -> content/thinking/tool_calls or None; generate
-> response/thinking or None; chat_stream -> token/done/error and the
connection-ending callable), and no output cap and no read timeout anywhere
on the way (rule 5).

Run: pytest devserver/tests/test_llm_client_comfyui.py -q
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import llm_client
from my_app.services import local_llm_weights as w

ALIAS = next(iter(w.models()))
DIR = w.dir_name(ALIAS)


@pytest.fixture()
def installed(monkeypatch):
    monkeypatch.setattr(w, "is_installed", lambda model_id: w.entry(model_id) is not None)


def _result(**ui):
    outputs = {llm_client.NODE_ID: {k: [v] for k, v in ui.items()}}
    return SimpleNamespace(prompt_id="p1", media_files=[], execution_time=0.1, outputs_metadata=outputs)


def test_the_prompt_is_one_node_of_the_package(installed):
    c = llm_client.LLMClient()
    wf = c._workflow(f"local/{ALIAS}", messages=[{"role": "user", "content": "hi"}],
                     images=["QUJD"], temperature=0.3, repetition_penalty=1.1, stream=True)
    assert list(wf) == [llm_client.NODE_ID]
    node = wf[llm_client.NODE_ID]
    assert node["class_type"] == "ai4artsed_local_llm"
    i = node["inputs"]
    assert i["llm_name"] == DIR
    assert json.loads(i["messages"]) == [{"role": "user", "content": "hi"}]
    assert i["raw"] is False and i["stream"] is True
    assert json.loads(i["images_b64"]) == ["QUJD"]
    assert i["temperature"] == 0.3 and i["repetition_penalty"] == 1.1
    assert isinstance(i["seed"], int)
    assert "max_tokens" not in i and "max_new_tokens" not in i
    raw = c._workflow(ALIAS, prompt="Say yes.")[llm_client.NODE_ID]["inputs"]
    assert raw["messages"] == "Say yes." and raw["raw"] is True
    assert "images_b64" not in raw and "repetition_penalty" not in raw
    # Two prompts for the same call differ in their seed: ComfyUI would answer
    # the second from its cache otherwise.
    a = c._workflow(ALIAS, prompt="x")[llm_client.NODE_ID]["inputs"]["seed"]
    b = c._workflow(ALIAS, prompt="x")[llm_client.NODE_ID]["inputs"]["seed"]
    assert a != b


def test_an_unknown_or_uninstalled_model_is_refused_by_name(monkeypatch):
    c = llm_client.LLMClient()
    with pytest.raises(LookupError, match="not a local model"):
        c._workflow("nothing:1b", prompt="x")
    monkeypatch.setattr(w, "is_installed", lambda model_id: False)
    with pytest.raises(LookupError, match="not installed"):
        c._workflow(ALIAS, prompt="x")


def test_chat_and_generate_keep_their_contracts(installed, monkeypatch):
    seen = {}

    def fake_track(workflow, on_progress=None, on_event=None):
        seen["workflow"] = workflow
        return _result(content="the answer", thinking="hm", finish_reason="stop",
                       prompt_tokens=12, completion_tokens=3)

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(fake_track))
    c = llm_client.LLMClient()
    r = c.chat(f"local/{ALIAS}", [{"role": "user", "content": "q"}], images=["QUJD"], temperature=0.2)
    assert r == {"content": "the answer", "thinking": "hm", "tool_calls": None, "finish_reason": "stop"}
    assert seen["workflow"][llm_client.NODE_ID]["inputs"]["raw"] is False
    g = c.generate(ALIAS, "raw prompt", temperature=0.0)
    assert g == {"response": "the answer", "thinking": "hm", "finish_reason": "stop"}
    assert seen["workflow"][llm_client.NODE_ID]["inputs"]["raw"] is True
    assert seen["workflow"][llm_client.NODE_ID]["inputs"]["messages"] == "raw prompt"


def test_a_failed_run_answers_none_and_says_why(installed, monkeypatch, caplog):
    def failing(workflow, on_progress=None, on_event=None):
        raise RuntimeError("ComfyUI execution error in ai4artsed_local_llm: no room")

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(failing))
    c = llm_client.LLMClient()
    assert c.chat(ALIAS, [{"role": "user", "content": "q"}]) is None
    assert c.generate(ALIAS, "p") is None
    assert "no room" in caplog.text
    # A model nothing offers is a LookupError inside, None outside.
    assert c.chat("nothing:1b", [{"role": "user", "content": "q"}]) is None
    assert c.generate("nothing:1b", "p") is None


def test_a_run_without_the_nodes_answer_is_a_failure(installed, monkeypatch):
    monkeypatch.setattr(llm_client.LLMClient, "_track",
                        staticmethod(lambda workflow, on_progress=None, on_event=None:
                                     SimpleNamespace(prompt_id="p", media_files=[], execution_time=0,
                                                     outputs_metadata={})))
    assert llm_client.LLMClient().chat(ALIAS, [{"role": "user", "content": "q"}]) is None


def test_the_stream_hands_on_the_pieces_then_the_reason(installed, monkeypatch):
    def fake_track(workflow, on_progress=None, on_event=None):
        on_progress(SimpleNamespace(event_type="submitted", prompt_id="p1"))
        for piece in ("Hel", "lo"):
            on_event(llm_client.TOKEN_EVENT, {"prompt_id": "p1", "node": "1", "text": piece})
        on_event("ai4artsed.other", {"text": "ignored"})
        return _result(content="Hello", thinking="", finish_reason="stop",
                       prompt_tokens=1, completion_tokens=2)

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(fake_track))
    ended = []
    items = list(llm_client.LLMClient().chat_stream(
        ALIAS, [{"role": "user", "content": "q"}], on_connection=ended.append))
    assert items == [("token", "Hel"), ("token", "lo"), ("done", "stop")]
    assert len(ended) == 1 and callable(ended[0])


def test_the_stream_says_when_it_broke_and_when_it_was_ended(installed, monkeypatch, caplog):
    def failing(workflow, on_progress=None, on_event=None):
        on_event(llm_client.TOKEN_EVENT, {"text": "par"})
        raise RuntimeError("ComfyUI execution error in ai4artsed_local_llm: gone")

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(failing))
    items = list(llm_client.LLMClient().chat_stream(ALIAS, [{"role": "user", "content": "q"}]))
    assert items[0] == ("token", "par")
    assert items[1][0] == "error" and "gone" in items[1][1]

    cancelled = []

    def interrupted(workflow, on_progress=None, on_event=None):
        on_progress(SimpleNamespace(event_type="submitted", prompt_id="p9"))
        # The caller ends the run while it writes; ComfyUI reports the interruption.
        raise RuntimeError("ComfyUI execution interrupted: p9")

    class FakeClient:
        async def cancel_job(self, prompt_id):
            cancelled.append(prompt_id)

    import my_app.services.comfyui_ws_client as ws
    monkeypatch.setattr(ws, "get_comfyui_ws_client", lambda base_url=None: FakeClient())
    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(interrupted))
    items = list(llm_client.LLMClient().chat_stream(
        ALIAS, [{"role": "user", "content": "q"}], on_connection=lambda end: end()))
    assert _soon(lambda: cancelled == ["p9"])
    assert items == [("error", "the caller ended this connection")]


def _soon(condition, seconds=5.0):
    """The cancel runs on a thread of its own (llm_client, end_it)."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def test_the_run_can_be_ended_from_inside_the_tracking_loop(installed, monkeypatch):
    """The ComfyUI client reports the prompt id from inside its own loop, and
    a reader that had already left ends the run from right there: with
    asyncio.run that was a refusal ("cannot be called from a running event
    loop"), swallowed by the client, and the run went on for nobody."""
    cancelled = []

    class FakeClient:
        async def cancel_job(self, prompt_id):
            cancelled.append(prompt_id)

    import my_app.services.comfyui_ws_client as ws
    monkeypatch.setattr(ws, "get_comfyui_ws_client", lambda base_url=None: FakeClient())

    def on_the_loop(workflow, on_progress=None, on_event=None):
        async def tracking():
            on_progress(SimpleNamespace(event_type="submitted", prompt_id="p3"))
            await asyncio.sleep(0.05)
            raise RuntimeError("ComfyUI execution interrupted: p3")
        return asyncio.run(tracking())

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(on_the_loop))
    items = list(llm_client.LLMClient().chat_stream(
        ALIAS, [{"role": "user", "content": "q"}], on_connection=lambda end: end()))
    assert _soon(lambda: cancelled == ["p3"])
    assert items == [("error", "the caller ended this connection")]


def test_a_reader_that_leaves_ends_the_run(installed, monkeypatch):
    """close() on the stream between two pieces -- the comparison surface's
    repetition break, a route's finally -- interrupts the prompt at ComfyUI
    instead of leaving the model writing for nobody. And a reader that left
    before ComfyUI had even taken the prompt ends it the moment it is
    known."""
    import threading
    cancelled = []
    monkeypatch.setattr(llm_client, "_cancel_at_comfyui", cancelled.append)
    gate = threading.Event()

    def writing(workflow, on_progress=None, on_event=None):
        on_progress(SimpleNamespace(event_type="submitted", prompt_id="p5"))
        on_event(llm_client.TOKEN_EVENT, {"text": "one"})
        gate.wait(5)
        raise RuntimeError("ComfyUI execution interrupted: p5")

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(writing))
    stream = llm_client.LLMClient().chat_stream(ALIAS, [{"role": "user", "content": "q"}])
    assert next(stream) == ("token", "one")
    stream.close()
    assert _soon(lambda: cancelled == ["p5"])
    gate.set()

    cancelled.clear()
    taken = threading.Event()

    def taken_late(workflow, on_progress=None, on_event=None):
        on_event(llm_client.TOKEN_EVENT, {"text": "early"})
        taken.wait(5)
        on_progress(SimpleNamespace(event_type="submitted", prompt_id="p6"))
        raise RuntimeError("ComfyUI execution interrupted: p6")

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(taken_late))
    stream = llm_client.LLMClient().chat_stream(ALIAS, [{"role": "user", "content": "q"}])
    assert next(stream) == ("token", "early")
    stream.close()
    assert cancelled == []
    taken.set()
    assert _soon(lambda: cancelled == ["p6"])

    # A stream read to its end has nothing left to end.
    def done(workflow, on_progress=None, on_event=None):
        on_progress(SimpleNamespace(event_type="submitted", prompt_id="p7"))
        return _result(content="x", thinking="", finish_reason="stop", prompt_tokens=1, completion_tokens=1)

    cancelled.clear()
    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(done))
    assert list(llm_client.LLMClient().chat_stream(ALIAS, [{"role": "user", "content": "q"}]))[-1] == ("done", "stop")
    time.sleep(0.1)
    assert cancelled == []


def test_the_stream_hands_out_what_the_socket_missed(installed, monkeypatch):
    """The answer off the history is the whole of it. Pieces the socket
    missed at the end are handed out before "done"; a beginning it missed
    cannot be handed out after the rest and is an error that says so."""
    def tail_lost(workflow, on_progress=None, on_event=None):
        on_event(llm_client.TOKEN_EVENT, {"text": "Hel"})
        return _result(content="Hello world", thinking="", finish_reason="stop",
                       prompt_tokens=1, completion_tokens=3)

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(tail_lost))
    items = list(llm_client.LLMClient().chat_stream(ALIAS, [{"role": "user", "content": "q"}]))
    assert items == [("token", "Hel"), ("token", "lo world"), ("done", "stop")]

    def head_lost(workflow, on_progress=None, on_event=None):
        on_event(llm_client.TOKEN_EVENT, {"text": "lo world"})
        return _result(content="Hello world", thinking="", finish_reason="stop",
                       prompt_tokens=1, completion_tokens=3)

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(head_lost))
    items = list(llm_client.LLMClient().chat_stream(ALIAS, [{"role": "user", "content": "q"}]))
    assert items[0] == ("token", "lo world")
    assert items[1][0] == "error" and "not its beginning" in items[1][1]


def test_the_rest_of_an_answer():
    assert llm_client._rest_of("Hello", "Hello") == ""
    assert llm_client._rest_of("Hello", "\n\nHello\n") == ""
    assert llm_client._rest_of("Hello world", "Hel") == "lo world"
    assert llm_client._rest_of("Hello world", "Hello ") == "world"
    assert llm_client._rest_of("Hello world", "") == "Hello world"
    assert llm_client._rest_of("Hello world", "world") is None


def test_the_pool_thread_carries_the_run_id_and_not_the_output_config(installed, monkeypatch):
    """The lease of an LLM run is labelled with the request's run id and
    keyed by the model, never by the image config a safety check runs
    inside of: the gate times image configs by that key."""
    from my_app.services.generation_abort import CURRENT_RUN_ID, CURRENT_OUTPUT_CONFIG
    seen = {}

    def fake_track(workflow, on_progress=None, on_event=None):
        seen["run"] = CURRENT_RUN_ID.get()
        seen["config"] = CURRENT_OUTPUT_CONFIG.get()
        return _result(content="ok", thinking="", finish_reason="stop", prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(llm_client.LLMClient, "_track", staticmethod(fake_track))
    run_token = CURRENT_RUN_ID.set("run-77")
    config_token = CURRENT_OUTPUT_CONFIG.set("sd35_large")
    try:
        assert llm_client.LLMClient().chat(ALIAS, [{"role": "user", "content": "q"}])["content"] == "ok"
    finally:
        CURRENT_RUN_ID.reset(run_token)
        CURRENT_OUTPUT_CONFIG.reset(config_token)
    assert seen == {"run": "run-77", "config": None}


def test_a_reading_of_the_text_lab_is_one_prompt_tracked_like_a_chat(monkeypatch):
    """run_node: one prompt of one node, queued over the websocket with no
    ceiling on the wait (submit_and_track, timeout=None), filed with the gate
    under the workload the caller names, or under its model without one,
    and taken out of the history afterwards. Empty outputs are a failure."""
    from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
    seen = []
    forgotten = []

    class FakeClient:
        def __init__(self, outputs):
            self.outputs = outputs

        async def submit_and_track(self, workflow, timeout=None, on_progress=None, on_event=None):
            seen.append({"workflow": workflow, "timeout": timeout, "config": CURRENT_OUTPUT_CONFIG.get()})
            on_progress(SimpleNamespace(event_type="submitted", prompt_id="p9"))
            return SimpleNamespace(prompt_id="p9", media_files=[], execution_time=0.1,
                                   outputs_metadata=self.outputs)

        async def forget_prompt(self, prompt_id):
            forgotten.append(prompt_id)

    import my_app.services.comfyui_ws_client as ws
    wrote = {llm_client.NODE_ID: {"result": [json.dumps({"scores": [[1.0]]})]}}
    monkeypatch.setattr(ws, "get_comfyui_ws_client", lambda base_url=None: FakeClient(wrote))
    config_token = CURRENT_OUTPUT_CONFIG.set("sd35_large")
    try:
        out = llm_client.LLMClient.run_node("ai4artsed_llm_option_scores", {"llm_name": "x"},
                                            workload="text:bias-probe")
        plain = llm_client.LLMClient.run_node("ai4artsed_llm_option_scores", {"llm_name": "x"})
    finally:
        CURRENT_OUTPUT_CONFIG.reset(config_token)
    assert json.loads(out["result"]) == {"scores": [[1.0]]} and plain == out
    assert seen[0]["workflow"] == {llm_client.NODE_ID: {"class_type": "ai4artsed_llm_option_scores",
                                                        "inputs": {"llm_name": "x"}}}
    assert [s["timeout"] for s in seen] == [None, None]
    assert [s["config"] for s in seen] == ["text:bias-probe", None]
    assert forgotten == ["p9", "p9"]
    monkeypatch.setattr(ws, "get_comfyui_ws_client", lambda base_url=None: FakeClient({}))
    with pytest.raises(RuntimeError, match="without the node's answer"):
        llm_client.LLMClient.run_node("ai4artsed_llm_option_scores", {"llm_name": "x"})


def test_the_prompt_leaves_comfyuis_history_after_the_run(monkeypatch):
    """ComfyUI keeps a run's inputs -- the conversation, the picture -- in
    its history until the process ends; the client deletes the entry once
    the answer is read, and after a run that failed as well."""
    forgotten = []

    class FakeClient:
        def __init__(self, outcome):
            self.outcome = outcome

        async def submit_and_track(self, workflow, timeout=None, on_progress=None, on_event=None):
            on_progress(SimpleNamespace(event_type="submitted", prompt_id="p5"))
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

        async def forget_prompt(self, prompt_id):
            forgotten.append(prompt_id)

    import my_app.services.comfyui_ws_client as ws
    good = _result(content="ok", thinking="", finish_reason="stop", prompt_tokens=1, completion_tokens=1)
    monkeypatch.setattr(ws, "get_comfyui_ws_client", lambda base_url=None: FakeClient(good))
    assert llm_client.LLMClient._track({"1": {}}) is good
    assert forgotten == ["p5"]
    monkeypatch.setattr(ws, "get_comfyui_ws_client",
                        lambda base_url=None: FakeClient(RuntimeError("execution error")))
    with pytest.raises(RuntimeError, match="execution error"):
        llm_client.LLMClient._track({"1": {}})
    assert forgotten == ["p5", "p5"]


def test_the_stream_refuses_an_unknown_model_by_name(installed):
    items = list(llm_client.LLMClient().chat_stream("nothing:1b", [{"role": "user", "content": "q"}]))
    assert len(items) == 1 and items[0][0] == "error" and "not a local model" in items[0][1]


def test_vlm_models_come_off_the_table(monkeypatch):
    c = llm_client.LLMClient()
    entries = c.vlm_models()
    assert entries is not None and entries
    assert all(m["vision"] for m in entries)
    assert all(m["backend"] == "llm" for m in entries), "the word the Image Understanding surface preselects by"
    monkeypatch.setattr(w, "vision_models", lambda: (_ for _ in ()).throw(OSError("table gone")))
    assert c.vlm_models() is None


def test_no_cap_and_no_read_timeout_on_the_way():
    """Rule 5: the client passes the ComfyUI client timeout=None and the node no
    output cap; no caller can hand it a timeout any more."""
    source = Path(llm_client.__file__).read_text(encoding="utf-8")
    assert "timeout=None" in source
    assert "timeout=" not in source.replace("timeout=None", "")
    assert "max_tokens" not in source.replace("max_new_tokens", "")


def test_the_prompts_an_earlier_process_left_are_taken_out(monkeypatch):
    """A DevServer that ended mid-run never reached the deletion in _tracked;
    the next start takes every prompt of the node out of ComfyUI's history --
    and, since stage 5, every prompt of the two nodes the Text Lab's probes
    queue the same way (run_node)."""
    from my_app.services.text_probes import REP_ENGINEERING_NODE, SCORES_NODE
    asked = []

    class FakeClient:
        async def forget_prompts_of(self, class_type):
            asked.append(class_type)
            return 2

    import my_app.services.comfyui_ws_client as ws
    monkeypatch.setattr(ws, "get_comfyui_ws_client", lambda base_url=None: FakeClient())
    swept = [llm_client.NODE_CLASS, SCORES_NODE, REP_ENGINEERING_NODE]
    assert llm_client.forget_left_prompts() == 6
    assert asked == swept
    thread = llm_client.forget_left_prompts_in_background()
    thread.join(5)
    assert not thread.is_alive() and asked == swept * 2


def test_a_reason_is_never_empty():
    assert llm_client._said(RuntimeError("gone")) == "gone"
    assert llm_client._said(TimeoutError()) == "TimeoutError"
