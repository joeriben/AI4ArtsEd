"""A stop reaches the prompt ComfyUI holds for the run, on every way a run gets there.

The cancel route interrupts a ComfyUI prompt it can name. Until 2026-10-01 it
could name one only where the streaming generation route had learned the id
through its progress callback. A station node run through
llm_client.run_node_files (the song, the 3D mesh) passes no callback, and
neither do the interception route's own Stage 4 or the non-streaming
generation route: a stop there cleared the page, and nothing at the backend
interrupted the song.

Since then the ComfyUI client notes every prompt it submits under the run id
of its context (generation_abort.note_prompt), and the cancel interrupts what
is noted under the run it finds for the device. The non-streaming generation
route sets no run id in its context and stays without a prompt to interrupt.

Everything is faked: no ComfyUI, no card.

Run: cd devserver && python3 -m pytest tests/test_cancel_reaches_comfyui.py -q
"""
import asyncio
import contextlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import websockets

from my_app.services import comfyui_ws_client as WS
from my_app.services import generation_abort
from my_app.services import gpu_lease_client
from my_app.services.comfyui_ws_client import ComfyUIWebSocketClient

RUN = "run_cancel_test"


@pytest.fixture(autouse=True)
def clean():
    """No mark and no noted prompt may leak from one test into the next."""
    generation_abort.unmark(RUN)
    for pid in generation_abort.prompts_of(RUN):
        generation_abort.forget_prompt(RUN, pid)
    yield
    generation_abort.unmark(RUN)
    for pid in generation_abort.prompts_of(RUN):
        generation_abort.forget_prompt(RUN, pid)


class _NoSocket:
    async def __aenter__(self):
        raise OSError("no socket in this test")

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def comfy(monkeypatch):
    """A ComfyUI that takes the prompt as p-1, answers the poll with a
    finished run, and records every cancel; the gate grants at once."""
    seen = {"cancelled": [], "noted_while_running": None, "on_submit": None}

    async def submitted(self, workflow, client_id=None):
        if seen["on_submit"]:
            seen["on_submit"]()
        return "p-1"

    async def polled(self, prompt_id, timeout=480, poll_interval=2.0, start_time=None):
        seen["noted_while_running"] = generation_abort.prompts_of(RUN)
        return {"outputs": {}, "status": {"status_str": "success"}}

    async def downloads(self, prompt_id):
        return [], {}

    async def cancel_job(self, prompt_id):
        seen["cancelled"].append(prompt_id)

    @contextlib.asynccontextmanager
    async def granted(*a, **k):
        yield None

    monkeypatch.setattr(ComfyUIWebSocketClient, "_submit_workflow", submitted)
    monkeypatch.setattr(ComfyUIWebSocketClient, "_poll_until_complete", polled)
    monkeypatch.setattr(ComfyUIWebSocketClient, "_download_outputs", downloads)
    monkeypatch.setattr(ComfyUIWebSocketClient, "cancel_job", cancel_job)
    monkeypatch.setattr(websockets, "connect", lambda *a, **k: _NoSocket())
    monkeypatch.setattr(gpu_lease_client, "gpu_lease", granted)

    def run():
        client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
        token = generation_abort.CURRENT_RUN_ID.set(RUN)
        try:
            return asyncio.run(client.submit_and_track({"1": {"class_type": "x", "inputs": {}}}))
        finally:
            generation_abort.CURRENT_RUN_ID.reset(token)

    seen["run"] = run
    return seen


def test_the_client_names_its_prompt_under_the_run_while_it_runs(comfy):
    comfy["run"]()
    assert comfy["noted_while_running"] == ["p-1"]
    assert generation_abort.prompts_of(RUN) == []
    assert comfy["cancelled"] == []


def test_a_run_stopped_before_its_prompt_had_a_name_is_interrupted_at_once(comfy):
    """The stop lands after the gate's last look and before the submission
    answers: nobody could name the prompt yet, so the client interrupts it."""
    comfy["on_submit"] = lambda: generation_abort.mark(RUN)
    with pytest.raises(RuntimeError, match="cancelled"):
        comfy["run"]()
    assert comfy["cancelled"] == ["p-1"]
    assert generation_abort.prompts_of(RUN) == []


def test_the_cancel_interrupts_what_is_noted_for_the_devices_run(monkeypatch):
    from my_app.routes import schema_pipeline_routes as R
    cancelled = []

    class FakeClient:
        async def cancel_job(self, prompt_id):
            cancelled.append(prompt_id)

    monkeypatch.setattr(WS, "get_comfyui_ws_client", lambda: FakeClient())
    monkeypatch.setitem(R._active_generations, "dev-cancel",
                        {"run_id": RUN, "ts": time.time(), "output_config": "heartmula_standard",
                         "phase": "generating"})
    generation_abort.note_prompt(RUN, "p-7")
    R._cancel_comfyui_for("dev-cancel")
    assert cancelled == ["p-7"]


def test_the_prompt_the_stream_learned_is_interrupted_once(monkeypatch):
    from my_app.routes import schema_pipeline_routes as R
    cancelled = []

    class FakeClient:
        async def cancel_job(self, prompt_id):
            cancelled.append(prompt_id)

    monkeypatch.setattr(WS, "get_comfyui_ws_client", lambda: FakeClient())
    monkeypatch.setitem(R._active_generations, "dev-cancel",
                        {"run_id": RUN, "ts": time.time(), "output_config": "sd35_large",
                         "phase": "generating", "comfyui_prompt_id": "p-8"})
    generation_abort.note_prompt(RUN, "p-8")
    R._cancel_comfyui_for("dev-cancel")
    assert cancelled == ["p-8"]
