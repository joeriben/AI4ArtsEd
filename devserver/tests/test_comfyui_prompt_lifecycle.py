"""What the ComfyUI client says and does about one prompt's life.

Held in place here, all of it on the client alone with a faked transport:

- The "submitted" event: on_progress hears the prompt id first thing,
  through submit_and_track itself. Until 2026-09-12 the event was a
  dataclass declared inside the method with `prompt_id: str = prompt_id`,
  which raises NameError in a class body, and the `except Exception: pass`
  around it swallowed that: the image cancel
  (schema_pipeline_routes._cancel_comfyui_for) never had an id to cancel
  by, since f32e5e7c.
- The polling fallback: a poll that cannot reach ComfyUI asks once whether
  the prompt still exists (_require_known) and raises when the connection
  is refused, instead of polling a restarted ComfyUI for ever under
  timeout=None. A question that goes unanswered within its 15 s is no
  verdict: the tracking goes on and asks again. Neither is a poll that
  goes unanswered: since Python 3.11 aiohttp's timeout is the builtin
  TimeoutError, the run's ceiling is raised outside the poll, and only
  that one ends the run (2026-09-14: a Hunyuan3D run ended at 98 s of
  342 because the poll's silence was re-raised as the ceiling).
- cancel_job takes a pending prompt out of the queue BEFORE it interrupts
  a running one: a prompt goes from pending to running and never back, so
  the other order left a gap in which a prompt the worker had just taken
  was skipped by both.
- forget_prompts_of: the history entries whose workflow holds a node of
  the class, deleted in one POST; the count says how many.

Run: pytest devserver/tests/test_comfyui_prompt_lifecycle.py -q
"""
import asyncio
import os
import sys

import pytest
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from my_app.services import comfyui_ws_client as WS
from my_app.services.comfyui_ws_client import ComfyUIWebSocketClient


def test_on_progress_hears_the_prompt_id_through_submit_and_track(monkeypatch):
    heard = []

    async def submitted(self, workflow, client_id=None):
        return "p-42"

    class _NoSocket:
        """websockets.connect answers with a connection object whose
        __aenter__ does the connecting; here that is what fails."""
        async def __aenter__(self):
            raise OSError("no socket in this test")

        async def __aexit__(self, *exc):
            return False

    def no_socket(*a, **k):
        return _NoSocket()

    async def polled(self, prompt_id, timeout=480, poll_interval=2.0, start_time=None):
        return {"outputs": {}, "status": {"status_str": "success"}}

    monkeypatch.setattr(ComfyUIWebSocketClient, "_submit_workflow", submitted)
    monkeypatch.setattr(ComfyUIWebSocketClient, "_poll_until_complete", polled)
    monkeypatch.setattr(websockets, "connect", no_socket)

    async def downloads(self, prompt_id):
        return [], {}
    monkeypatch.setattr(ComfyUIWebSocketClient, "_download_outputs", downloads)

    # The lease around submit_and_track is the gate's business, held apart
    # here: a lease that is granted at once.
    import contextlib
    from my_app.services import gpu_lease_client

    @contextlib.asynccontextmanager
    async def granted(*a, **k):
        yield None
    monkeypatch.setattr(gpu_lease_client, "gpu_lease", granted)

    client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    asyncio.run(client.submit_and_track({"1": {"class_type": "x", "inputs": {}}},
                                        on_progress=heard.append))
    first = heard[0]
    assert first.event_type == "submitted"
    assert first.prompt_id == "p-42"
    assert isinstance(first, WS.SubmittedEvent)


class _Refusing:
    def get(self, url, timeout=None):
        raise WS.aiohttp.ClientConnectionError("connection refused")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_a_poll_that_cannot_reach_comfyui_stops_with_the_reason(monkeypatch):
    monkeypatch.setattr(WS.aiohttp, "ClientSession", lambda *a, **k: _Refusing())
    client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    with pytest.raises(RuntimeError, match="refused the connection"):
        asyncio.run(client._poll_until_complete("p-1", timeout=None, poll_interval=0.01))


class _Slow:
    def get(self, url, timeout=None):
        raise asyncio.TimeoutError()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_an_unanswered_question_is_no_verdict(monkeypatch, caplog):
    monkeypatch.setattr(WS.aiohttp, "ClientSession", lambda *a, **k: _Slow())
    client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    assert asyncio.run(client._require_known("p-1")) is None
    assert "did not answer" in caplog.text


class _Recording:
    """A session that records every POST, in order."""
    def __init__(self, posts):
        self._posts = posts

    def post(self, url, json=None, timeout=None):
        self._posts.append((url.rsplit("/", 1)[-1], json))
        return _Done()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Answer:
    """One GET's answer: the status and the json."""

    def __init__(self, payload):
        self.status = 200
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _SilentThenDone:
    """A ComfyUI whose loop is held for a while: the first polls go
    unanswered (aiohttp's timeout), then the history holds the outputs."""

    def __init__(self, silent_polls, prompt_id):
        self.silent = silent_polls
        self.polls = 0
        self.prompt_id = prompt_id

    def get(self, url, timeout=None):
        self.polls += 1
        if self.polls <= self.silent:
            raise asyncio.TimeoutError()
        return _Answer({self.prompt_id: {"status": {"status_str": "success"},
                                         "outputs": {"1": {"mesh": [{"filename": "m.glb"}]}}}})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_a_poll_that_goes_unanswered_is_not_the_end_of_the_run(monkeypatch):
    # Since Python 3.11 aiohttp's timeout is the builtin TimeoutError; taken
    # for the run's own ceiling it ended a Hunyuan3D run at 98 s of 342
    # (2026-09-14), while the node was still writing. Both the poll and the
    # question that follows it go unanswered here; the run is polled on.
    session = _SilentThenDone(silent_polls=4, prompt_id="p-1")
    monkeypatch.setattr(WS.aiohttp, "ClientSession", lambda *a, **k: session)
    client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    entry = asyncio.run(client._poll_until_complete("p-1", timeout=None, poll_interval=0.01))
    assert entry["outputs"]["1"]["mesh"][0]["filename"] == "m.glb"
    assert session.polls > 4


def test_the_run_has_its_own_ceiling_still(monkeypatch):
    # The ceiling a caller sets (the schema pipeline passes one) is raised
    # outside the poll, with its sentence, and is the one TimeoutError left.
    session = _SilentThenDone(silent_polls=10 ** 6, prompt_id="p-1")
    monkeypatch.setattr(WS.aiohttp, "ClientSession", lambda *a, **k: session)
    client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    with pytest.raises(TimeoutError, match="Polling timeout after"):
        asyncio.run(client._poll_until_complete("p-1", timeout=0, poll_interval=0.01,
                                                start_time=0.0))


class _Done:
    def __await__(self):
        if False:
            yield
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_a_cancel_takes_the_prompt_out_of_the_queue_before_it_interrupts(monkeypatch):
    posts = []
    monkeypatch.setattr(WS.aiohttp, "ClientSession", lambda *a, **k: _Recording(posts))
    client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    asyncio.run(client.cancel_job("p-3"))
    assert posts == [("queue", {"delete": ["p-3"]}), ("interrupt", {"prompt_id": "p-3"})]


class _History:
    """GET /history answers with these entries; POSTs are recorded."""
    def __init__(self, entries, posts):
        self._entries, self._posts = entries, posts

    def get(self, url, timeout=None):
        return _Payload(self._entries)

    def post(self, url, json=None, timeout=None):
        self._posts.append(json)
        return _Done()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Payload:
    def __init__(self, payload):
        self._payload, self.status = payload, 200

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _entry(class_type):
    return {"prompt": [3, "x", {"1": {"class_type": class_type, "inputs": {}}}, {}, ["1"]],
            "outputs": {}, "status": {"status_str": "success"}}


def test_the_prompts_of_a_node_class_leave_the_history_together(monkeypatch):
    posts = []
    entries = {"a": _entry("ai4artsed_local_llm"), "b": _entry("KSampler"),
               "c": _entry("ai4artsed_local_llm"), "d": {"prompt": "odd", "outputs": {}}}
    monkeypatch.setattr(WS.aiohttp, "ClientSession", lambda *a, **k: _History(entries, posts))
    client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    assert asyncio.run(client.forget_prompts_of("ai4artsed_local_llm")) == 2
    assert posts == [{"delete": ["a", "c"]}]

    posts.clear()
    monkeypatch.setattr(WS.aiohttp, "ClientSession", lambda *a, **k: _History({"b": _entry("KSampler")}, posts))
    assert asyncio.run(client.forget_prompts_of("ai4artsed_local_llm")) == 0
    assert posts == []

    monkeypatch.setattr(WS.aiohttp, "ClientSession", lambda *a, **k: _Refusing())
    assert asyncio.run(client.forget_prompts_of("ai4artsed_local_llm")) == 0
