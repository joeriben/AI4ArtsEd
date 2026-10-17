"""A busy card is said as busy, never as a missing install (second review of
2026-10-10, package D3).

Until 2026-10-10 the DevServer took the worker's load lease itself, and a
refusal reached the router as GpuBusyError. Once the worker took the lease
(cfdcaac), the backend only polled /health, whose "gate": "waiting" nobody
read: after VOXCPM_STARTUP_TIMEOUT the chunk said "not available ... installs
it", and the worker loaded after the caller had been turned away. The queue
is the gate's time, bounded by its own budget; the startup clock stands still
in it.
"""
import time

import pytest

from my_app.services.gpu_lease_client import GpuBusyError
from my_app.services.voxcpm_backend import VoxCPMBackend


def _backend(monkeypatch, states, startup_timeout, gate_budget):
    backend = VoxCPMBackend()
    backend._startup_timeout = startup_timeout
    backend._gate_wait_budget = gate_budget
    backend._health_interval = 0.01
    it = iter(states)
    last = {"state": None}

    def health():
        try:
            last["state"] = next(it)
        except StopIteration:
            pass
        return last["state"]

    monkeypatch.setattr(backend, "_health", health)
    return backend


WAITING = {"loaded": False, "error": "", "gate": "waiting"}


def test_the_queue_does_not_count_as_startup_time(monkeypatch):
    # 40 polls of 10 ms in the queue outlast a 0.2 s startup budget; the model
    # then arrives and the wait answers True.
    backend = _backend(monkeypatch, [WAITING] * 40 + [{"loaded": True, "gate": "held"}],
                       startup_timeout=0.2, gate_budget=5.0)
    assert backend._wait_for_ready(time.time()) is True


def test_a_queue_that_outlasts_the_gates_budget_is_said_as_busy(monkeypatch):
    backend = _backend(monkeypatch, [WAITING], startup_timeout=10.0, gate_budget=0.1)
    with pytest.raises(GpuBusyError) as caught:
        backend._wait_for_ready(time.time())
    assert caught.value.reason == "wait_timeout"


def test_a_load_outside_the_queue_keeps_its_startup_clock(monkeypatch):
    backend = _backend(monkeypatch, [{"loaded": False, "error": "", "gate": "held"}],
                       startup_timeout=0.05, gate_budget=5.0)
    assert backend._wait_for_ready(time.time()) is False
