"""A job ComfyUI had already finished before the socket was up.

`_track_execution` opens the WebSocket and then asks `/history` whether the
job finished in the gap. Until 2026-09-09 it threw that answer away: the
helper returned bare `None` on both paths, and the caller discarded it. A job
that was already done therefore fell into the event loop and waited for
`executing(node=None)`, which ComfyUI had already sent to nobody -- until the
timeout fired and `submit_and_track` called `cancel_job` on finished work.

Seen on 2026-09-09 02:02: a Denoising Archaeology run held the GPU lease for
its full 600 s budget and was then cancelled, with the image sitting in
/history the whole time.

Two things are held in place here: that the helper reports what it found, and
that the caller stops waiting when it did.
"""
import asyncio
import os
import sys
import time

import pytest
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from my_app.services import comfyui_ws_client as WS
from my_app.services.comfyui_ws_client import ComfyUIWebSocketClient


# --------------------------------------------------------------------------
# The shapes ComfyUI's /history actually returns
# --------------------------------------------------------------------------

def _finished(prompt_id):
    return {prompt_id: {"status": {"status_str": "success", "completed": True},
                        "outputs": {"save_video": {"images": [{"filename": "x.mp4"}]}}}}


def _still_running(prompt_id):
    return {prompt_id: {"status": {"status_str": "running", "completed": False},
                        "outputs": {}}}


def _failed(prompt_id):
    return {prompt_id: {"status": {"status_str": "error", "messages": [
        ["execution_error", {"exception_message": "CUDA out of memory"}]]},
        "outputs": {}}}


class _Response:
    def __init__(self, payload, status=200):
        self._payload, self.status = payload, status

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    def __init__(self, payload, status=200):
        self._payload, self._status = payload, status

    def get(self, url, timeout=None):
        return _Response(self._payload, self._status)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _history_says(monkeypatch, payload, status=200):
    monkeypatch.setattr(WS.aiohttp, "ClientSession",
                        lambda *a, **kw: _Session(payload, status))


# --------------------------------------------------------------------------
# The helper reports what it found
# --------------------------------------------------------------------------

def test_a_finished_job_is_reported_as_finished(monkeypatch):
    _history_says(monkeypatch, _finished("p1"))
    client = ComfyUIWebSocketClient()
    assert asyncio.run(client._check_already_completed("p1")) is True


def test_a_running_job_is_not(monkeypatch):
    _history_says(monkeypatch, _still_running("p1"))
    client = ComfyUIWebSocketClient()
    assert asyncio.run(client._check_already_completed("p1")) is False


def test_an_unknown_prompt_is_not(monkeypatch):
    _history_says(monkeypatch, {})
    client = ComfyUIWebSocketClient()
    assert asyncio.run(client._check_already_completed("p1")) is False


def test_an_unreachable_history_is_not_taken_for_finished(monkeypatch):
    """The check is a shortcut, not a verdict: if it cannot ask, the socket runs."""
    def _boom(*a, **kw):
        raise OSError("connection refused")
    monkeypatch.setattr(WS.aiohttp, "ClientSession", _boom)
    client = ComfyUIWebSocketClient()
    assert asyncio.run(client._check_already_completed("p1")) is False


def test_a_failed_job_still_raises(monkeypatch):
    """The error path predates this change and must survive it."""
    _history_says(monkeypatch, _failed("p1"))
    client = ComfyUIWebSocketClient()
    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        asyncio.run(client._check_already_completed("p1"))


# --------------------------------------------------------------------------
# The caller stops waiting
# --------------------------------------------------------------------------

class _NeverSpeaks:
    """A socket that would hang: recv() must not be reached."""

    async def recv(self):
        raise AssertionError("the event loop was entered for a finished job")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _socket_that_hangs(monkeypatch):
    monkeypatch.setattr(websockets, "connect", lambda *a, **kw: _NeverSpeaks())


def _track(client, on_progress=None, timeout=600):
    # A real start_time: with 0.0 the loop would trip its own timeout check
    # before ever reaching recv(), and the test would pass for the wrong reason.
    # The socket is opened by submit_and_track since 2026-09-12 (before the
    # submission, so no event is lost) and handed in; here it is the one
    # that must never be read.
    return asyncio.run(client._track_execution(
        ws=_NeverSpeaks(), prompt_id="p1", total_nodes=17, timeout=timeout,
        on_progress=on_progress, start_time=time.time()))


def test_tracking_returns_at_once_for_a_finished_job(monkeypatch):
    _socket_that_hangs(monkeypatch)
    client = ComfyUIWebSocketClient()

    async def _finished_already(_prompt_id):
        return True
    client._check_already_completed = _finished_already

    _track(client)          # AssertionError from recv() if the loop was entered


def test_the_surface_is_told_the_run_is_done(monkeypatch):
    """The normal path ends on a 100 % event; the shortcut must not skip it."""
    _socket_that_hangs(monkeypatch)
    client = ComfyUIWebSocketClient()

    async def _finished_already(_prompt_id):
        return True
    client._check_already_completed = _finished_already

    seen = []
    _track(client, on_progress=seen.append)
    assert seen, "no progress event was emitted"
    assert seen[-1].overall_percent == 1.0
    assert seen[-1].nodes_done == 17


def test_an_unfinished_job_still_enters_the_loop(monkeypatch):
    """Without this the shortcut would swallow every ordinary run."""
    _socket_that_hangs(monkeypatch)
    client = ComfyUIWebSocketClient()

    async def _not_yet(_prompt_id):
        return False
    client._check_already_completed = _not_yet

    with pytest.raises(AssertionError, match="event loop was entered"):
        _track(client)
