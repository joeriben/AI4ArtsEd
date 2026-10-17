"""Every administrative free of ComfyUI holds the card first.

`/free` takes every weight off the card, the ones of a run mid-forward too.
Until 2026-10-10 the training page's clear-VRAM, the workshop's clear-all and
the training service's cleanup before a run posted it on their own, past the
gate; the gate's own ask during admission was the only one that held the slot
(finding S-004 of the code review of 2026-10-10). services/gpu_gate.free_comfyui is the one path now: a lease, the
posts, and the gate forgetting what it believed resident.
"""
import contextlib
import os
import re
from types import SimpleNamespace

import pytest

MY_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "my_app")


class _Resp:
    def __init__(self, status_code=200):
        self.status_code = status_code


def _wire(monkeypatch, busy=None, status_code=200):
    from my_app.services import gpu_gate as G
    from my_app.services import gpu_lease_client as L
    log = []

    @contextlib.contextmanager
    def lease(kind, model_id="comfyui", required_mb=0, label="", **kw):
        if busy is not None:
            raise L.GpuBusyError(busy, reason="held", holder_kind="lora_training")
        log.append(("lease", kind, label, kw.get("timeout_s")))
        yield "token-1"
        log.append(("release",))

    monkeypatch.setattr(L, "gpu_lease_sync", lease)

    def post(url, **kw):
        log.append(("post", url.rsplit("/", 1)[-1], kw.get("json")))
        return _Resp(status_code)

    monkeypatch.setattr("requests.post", post)
    gate = SimpleNamespace(forget_resident=lambda why="": log.append(("forget", why)))
    monkeypatch.setattr(G, "get_gpu_gate", lambda: gate)
    return G, log


def test_the_free_holds_the_card_around_the_posts(monkeypatch):
    G, log = _wire(monkeypatch)
    resp = G.free_comfyui("a test", interrupt=True, free_memory=True, timeout=7, wait_s=3)
    assert resp.status_code == 200
    # The interrupt before the lease (it is for the run that holds the card),
    # the forget after the release (release() notes the hold as resident).
    assert log == [
        ("post", "interrupt", None),
        ("lease", "comfyui-free", "a test", 3),
        ("post", "free", {"unload_models": True, "free_memory": True}),
        ("release",),
        ("forget", "a test"),
    ]


def test_without_interrupt_only_free_is_posted(monkeypatch):
    G, log = _wire(monkeypatch)
    G.free_comfyui("a test")
    assert [e for e in log if e[0] == "post"] == [("post", "free", {"unload_models": True})]


def test_a_refusal_by_comfyui_keeps_what_the_gate_believes(monkeypatch):
    G, log = _wire(monkeypatch, status_code=500)
    resp = G.free_comfyui("a test")
    assert resp.status_code == 500
    assert ("forget", "a test") not in log


def test_a_held_card_frees_nothing(monkeypatch):
    from my_app.services.gpu_lease_client import GpuBusyError
    G, log = _wire(monkeypatch, busy="the card is held by a training")
    with pytest.raises(GpuBusyError):
        G.free_comfyui("a test")
    assert [e for e in log if e[0] != "post"] == []  # no free, no forget; the interrupt is not the gate's


def test_nothing_else_posts_free_to_comfyui():
    """Outside services/gpu_gate.py no file under my_app names ComfyUI's /free
    in a request: the three callers of 2026-10-10 go through free_comfyui."""
    offenders = []
    for root, _dirs, files in os.walk(MY_APP):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            if path.endswith(os.path.join("services", "gpu_gate.py")):
                continue
            text = open(path, encoding="utf-8").read()
            for number, line in enumerate(text.splitlines(), 1):
                if re.search(r"""/free['"]""", line):
                    offenders.append(f"{os.path.relpath(path, MY_APP)}:{number}")
    assert not offenders, (
        "ComfyUI's /free is posted past the gate; use services/gpu_gate.free_comfyui:\n  "
        + "\n  ".join(offenders))
