"""The VoxCPM2 worker takes the lease that covers its own load (finding S-005 of the code review of 2026-10-10).

Until 2026-10-10 the DevServer took `voxcpm-load` around STARTING the worker,
and only when it started it; a worker started by hand (2_start_voxcpm.sh) put
6774 MiB on the card that the coordinator learned of only when the next hold
measured them as foreign. Rule 15: whatever loads weights takes the lease that
covers the load. The worker is stdlib-only and runs in its own venv, so it asks
the DevServer's gate over HTTP (the way the GPU service does), and this test
stands a gate of its own up to watch the order: acquire, load under the hold
with heartbeats, release.
"""
import importlib.util
import json
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKER = REPO / "voxcpm_service" / "server.py"


def _load_worker():
    spec = importlib.util.spec_from_file_location("voxcpm_worker_under_test", WORKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Gate:
    """A gate that records what it is asked, answering as told. The last
    acquire answer repeats."""

    def __init__(self, acquire_answers=None, port=0):
        self.calls = []
        self.acquire_answers = list(acquire_answers or [(200, {"token": "t-1"})])
        self.lock = threading.Lock()
        gate = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                with gate.lock:
                    gate.calls.append((self.path, body, time.monotonic()))
                    if self.path.endswith("/acquire"):
                        if len(gate.acquire_answers) > 1:
                            status, payload = gate.acquire_answers.pop(0)
                        else:
                            status, payload = gate.acquire_answers[0]
                    else:
                        status, payload = 200, {"ok": True}
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def paths(self):
        with self.lock:
            return [path for path, _, _ in self.calls]

    def body_of(self, suffix):
        with self.lock:
            return next(body for path, body, _ in self.calls if path.endswith(suffix))

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class _Model:
    def __init__(self):
        self.tts_model = types.SimpleNamespace(sample_rate=48000,
                                               config=types.SimpleNamespace(max_length=4096))


def _stub_voxcpm(monkeypatch, on_load):
    """A `voxcpm` package whose from_pretrained calls `on_load` and returns a model."""
    module = types.ModuleType("voxcpm")

    class VoxCPM:
        @staticmethod
        def from_pretrained(model_id, load_denoiser=True):
            on_load(model_id, load_denoiser)
            return _Model()

    module.VoxCPM = VoxCPM
    monkeypatch.setitem(sys.modules, "voxcpm", module)


@pytest.fixture()
def worker(monkeypatch):
    module = _load_worker()
    monkeypatch.setattr(module, "GATE_HEARTBEAT_S", 0.05)
    monkeypatch.setattr(module, "GATE_RETRY_GAP_S", 0.05)
    monkeypatch.setattr(module, "GATE_RETRY_CEILING_S", 0.1)
    return module


def test_the_load_runs_under_the_hold_with_heartbeats_and_gives_it_back(worker, monkeypatch):
    gate = _Gate()
    monkeypatch.setenv("AI4ARTSED_DEVSERVER_URL", gate.url)
    seen = {}

    def on_load(model_id, load_denoiser):
        seen["gate_state"] = worker._gate_state
        seen["acquired_before"] = gate.paths().count("/api/gate/lease/acquire")
        seen["load_denoiser"] = load_denoiser
        time.sleep(0.25)  # long enough for heartbeats

    _stub_voxcpm(monkeypatch, on_load)
    try:
        worker._load()
    finally:
        gate.close()
    assert worker._model is not None and worker._load_error == ""
    assert seen == {"gate_state": "held", "acquired_before": 1, "load_denoiser": False}
    paths = gate.paths()
    assert paths[0] == "/api/gate/lease/acquire"
    assert paths[-1] == "/api/gate/lease/release"
    assert paths.count("/api/gate/lease/heartbeat") >= 1
    acquire = gate.body_of("/acquire")
    assert acquire["kind"] == "voxcpm-load" and acquire["model_id"] == "voxcpm"
    assert acquire["required_mb"] == float(worker.VRAM_MB) and acquire["holder"] == "voxcpm_service"
    assert gate.body_of("/release") == {"token": "t-1", "failed": False}
    assert worker._gate_state == "released"


def test_a_load_that_fails_gives_the_hold_back_as_failed(worker, monkeypatch):
    gate = _Gate()
    monkeypatch.setenv("AI4ARTSED_DEVSERVER_URL", gate.url)

    def on_load(model_id, load_denoiser):
        raise RuntimeError("no weights here")

    _stub_voxcpm(monkeypatch, on_load)
    try:
        worker._load()
    finally:
        gate.close()
    assert worker._model is None and "no weights here" in worker._load_error
    assert gate.body_of("/release")["failed"] is True


def test_a_refused_turn_is_asked_for_again(worker, monkeypatch):
    gate = _Gate(acquire_answers=[(503, {"error": "busy", "busy_reason": "queue"}),
                                  (200, {"token": "t-2"})])
    monkeypatch.setenv("AI4ARTSED_DEVSERVER_URL", gate.url)
    _stub_voxcpm(monkeypatch, lambda *a: None)
    try:
        worker._load()
    finally:
        gate.close()
    assert worker._model is not None
    assert gate.paths().count("/api/gate/lease/acquire") == 2
    assert gate.paths()[-1] == "/api/gate/lease/release"


def test_a_gate_without_lease_routes_lets_the_load_go_ahead_once_said(worker, monkeypatch):
    gate = _Gate(acquire_answers=[(404, {"error": "not found"})])
    monkeypatch.setenv("AI4ARTSED_DEVSERVER_URL", gate.url)
    _stub_voxcpm(monkeypatch, lambda *a: None)
    try:
        worker._load()
    finally:
        gate.close()
    assert worker._model is not None
    assert worker._gate_state == "absent"
    assert gate.paths() == ["/api/gate/lease/acquire"]


def test_a_gate_that_is_not_there_yet_is_waited_for(worker, monkeypatch):
    """Nothing goes on the card while the gate does not answer; the load
    starts once it does."""
    first = _Gate()
    port = first.port
    first.close()  # the port refuses connections now
    monkeypatch.setenv("AI4ARTSED_DEVSERVER_URL", "http://127.0.0.1:%d" % port)
    loaded_at = {}
    _stub_voxcpm(monkeypatch, lambda *a: loaded_at.setdefault("t", time.monotonic()))
    thread = threading.Thread(target=worker._load, daemon=True)
    thread.start()
    time.sleep(0.3)
    assert worker._gate_state == "waiting" and worker._model is None and "t" not in loaded_at
    try:
        gate = _Gate(port=port)  # the gate comes up on the same port
    except OSError:
        pytest.skip("the port was taken meanwhile")
    try:
        thread.join(timeout=5)
    finally:
        gate.close()
    assert not thread.is_alive()
    assert worker._model is not None and worker._gate_state == "released"
    assert gate.paths()[0] == "/api/gate/lease/acquire"


def test_the_devserver_holds_no_load_lease_and_the_worker_does():
    backend = (REPO / "devserver" / "my_app" / "services" / "voxcpm_backend.py").read_text(encoding="utf-8")
    assert "voxcpm-load" not in backend
    assert 'gpu_lease("voxcpm", "voxcpm", 0' in backend
    source = WORKER.read_text(encoding="utf-8")
    assert 'gpu_lease("voxcpm-load", "voxcpm", VRAM_MB' in source
    assert "import requests" not in source and "from my_app" not in source


def test_a_torn_answer_from_the_gate_is_asked_again(worker, monkeypatch):
    """http.client raises its own family for a torn answer (IncompleteRead,
    BadStatusLine); none is an OSError, and until 2026-10-10 one of them ended
    the load for good (second review of the same day)."""
    import http.client
    answers = [http.client.IncompleteRead(b""), http.client.BadStatusLine(""), (200, {"token": "t-9"})]

    def post(path, body, timeout):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(worker, "_gate_post", post)
    assert worker._acquire("voxcpm-load", "voxcpm", 1.0, "", "") == "t-9"
    assert worker._gate_state == "held"
