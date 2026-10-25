"""The gate in the DevServer's process (stage 7 of the move to ComfyUI).

One heavy operation on the card at a time. The gate used to be a module of
the GPU service and this process leased it over HTTP; since stage 7 it lives
here, every lease is a call, the card is read through the driver, and room is
made by asking ComfyUI to unload. These tests run the gate with a sensor of
their own and a ComfyUI of their own, so nothing here touches a card.
"""
import asyncio
import importlib.util
import inspect
import json
import logging
import sys
import threading
import time
import types

import pytest

from file_modules import REPO, load_module

sys.path.insert(0, str(REPO / "devserver"))
PACKAGE = REPO / "comfyui_nodes" / "ai4artsed_comfyui"

from my_app.services import gpu_gate as G  # noqa: E402
from my_app.services import gpu_lease_client as L  # noqa: E402


@pytest.fixture(autouse=True)
def the_measurements_stay_out_of_the_live_file(tmp_path, monkeypatch):
    """Every release records a hold; the live file under /var/tmp is the
    workshop's own measurement and must not learn about model-a."""
    from my_app.services import gpu_model_stats as stats
    monkeypatch.setenv("GATE_MODEL_STATS_PATH", str(tmp_path / "gate_model_stats.json"))
    monkeypatch.setattr(stats, "_stats", None)
    yield
    monkeypatch.setattr(stats, "_stats", None)


class Sensor:
    """A card that says what the test tells it to."""

    def __init__(self, free=60000.0, total=98000.0, configured=True):
        self.configured = configured
        self.why = "" if configured else "NVMLError_LibraryNotFound: NVML Shared Library Not Found"
        self.free = free
        self.total = total
        self.readings = 0

    def free_mb(self):
        self.readings += 1
        return self.free

    def name(self):
        return "Test Card"

    def read(self):
        if self.free is None:
            return None
        return {"total_mb": self.total, "used_mb": self.total - self.free, "free_mb": self.free,
                "foreign_mb": 0.0, "processes": []}


def a_gate(monkeypatch, sensor=None, **settings):
    """A gate with fast clocks; the reaper runs every 20 ms."""
    import config
    fast = {"GPU_ADMISSION_REAPER_INTERVAL_S": 0.02, "GPU_ADMISSION_HEARTBEAT_TIMEOUT_S": 0.2,
            "GPU_ADMISSION_FREE_WAIT_S": 0.3, "GPU_ADMISSION_POST_LOAD_RESERVE_S": 0.0}
    fast.update(settings)
    for k, v in fast.items():
        monkeypatch.setattr(config, k, v, raising=False)
    return G.GpuGate(sensor=sensor if sensor is not None else Sensor())


class Posts:
    """requests.post as the test sees it: what was asked, and how ComfyUI answers."""

    def __init__(self, status=200, raises=None, on_call=None):
        self.calls = []
        self.status_code = status
        self.raises = raises
        self.on_call = on_call
        self.text = ""

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        if self.raises:
            raise self.raises
        if self.on_call:
            self.on_call()
        return self


def in_thread(fn, *args):
    box = {}

    def run():
        try:
            box["value"] = fn(*args)
        except BaseException as e:  # noqa: BLE001
            box["error"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, box


# ---------------------------------------------------------------------------
# One slot, and the order in which it is handed out.

def test_the_second_operation_waits_until_the_first_has_released(monkeypatch):
    gate = a_gate(monkeypatch)
    first = gate.acquire("comfyui", "sd35", 0, label="run-1")
    t, box = in_thread(gate.acquire, "comfyui", "sd35", 0, 2, "run-2")
    time.sleep(0.1)
    assert "value" not in box and gate.get_status()["waiting"][0]["label"] == "run-2"
    gate.release(first)
    t.join(2)
    assert "value" in box
    assert gate.get_status()["active"]["label"] == "run-2"
    gate.release(box["value"])
    assert gate.get_status()["active"] is None


def test_a_run_whose_model_is_resident_goes_before_one_that_would_swap(monkeypatch):
    gate = a_gate(monkeypatch)
    held = gate.acquire("comfyui", "model-a", 0, label="a-1")
    tb, bb = in_thread(gate.acquire, "comfyui", "model-b", 0, 2, "b-1")
    time.sleep(0.05)
    ta, ba = in_thread(gate.acquire, "comfyui", "model-a", 0, 2, "a-2")
    time.sleep(0.05)
    plan = gate.plan()
    assert [q["label"] for q in plan["queue"]] == ["a-2", "b-1"]
    assert plan["queue"][0]["model_already_loaded"] is True
    gate.release(held)
    ta.join(2)
    assert "value" in ba and "value" not in bb
    assert gate.get_status()["waiting"][0]["overtaken"] == 1
    gate.release(ba["value"])
    tb.join(2)
    gate.release(bb["value"])


def test_nobody_is_passed_more_often_than_the_bound(monkeypatch):
    gate = a_gate(monkeypatch, GPU_ADMISSION_MAX_OVERTAKES=1)
    held = gate.acquire("comfyui", "model-a", 0, label="a-0")
    tb, bb = in_thread(gate.acquire, "comfyui", "model-b", 0, 2, "b")
    time.sleep(0.05)
    t1, b1 = in_thread(gate.acquire, "comfyui", "model-a", 0, 2, "a-1")
    time.sleep(0.05)
    t2, b2 = in_thread(gate.acquire, "comfyui", "model-a", 0, 2, "a-2")
    time.sleep(0.05)
    gate.release(held)
    t1.join(2)
    assert "value" in b1                       # passed b once
    gate.release(b1["value"])
    tb.join(2)
    assert "value" in bb and "value" not in b2  # b goes now, a-2 waits
    gate.release(bb["value"])
    t2.join(2)
    gate.release(b2["value"])


def test_a_long_hold_turns_the_next_one_away_at_once_and_names_itself(monkeypatch):
    gate = a_gate(monkeypatch)
    gate.acquire("lora_training", "lora", 0, label="training")
    with pytest.raises(G.GpuBusy) as caught:
        gate.acquire("comfyui", "sd35", 0, label="run")
    assert caught.value.reason == "long_hold"
    assert caught.value.holder_kind == "lora_training"
    assert "LoRA training" in str(caught.value)


def test_a_full_queue_is_refused_with_the_count(monkeypatch):
    gate = a_gate(monkeypatch, GPU_ADMISSION_MAX_WAITERS=1)
    held = gate.acquire("comfyui", "sd35", 0)
    t, box = in_thread(gate.acquire, "comfyui", "sd35", 0)
    time.sleep(0.05)
    with pytest.raises(G.GpuBusy) as caught:
        gate.acquire("comfyui", "sd35", 0)
    assert caught.value.reason == "queue_full" and caught.value.waiting == 1
    gate.release(held)
    t.join(2)
    gate.release(box["value"])


def test_a_wait_that_runs_out_says_so(monkeypatch):
    gate = a_gate(monkeypatch)
    gate.acquire("comfyui", "sd35", 0)
    with pytest.raises(G.GpuBusy) as caught:
        gate.acquire("comfyui", "sd35", 0, timeout_s=0.1)
    assert caught.value.reason == "wait_timeout"


# ---------------------------------------------------------------------------
# The heartbeat is the holder's sign of life.

def test_a_lease_without_a_heartbeat_is_reaped_and_the_next_one_goes(monkeypatch):
    gate = a_gate(monkeypatch)
    token = gate.acquire("comfyui", "sd35", 0, label="gone")
    t, box = in_thread(gate.acquire, "comfyui", "sd35", 0, 2, "next")
    t.join(3)
    assert "value" in box, "the reaper did not free the slot"
    assert gate.heartbeat(token) is False
    assert gate.get_status()["resident_model"] is None  # nobody said what finished loading
    gate.release(box["value"])


def test_a_heartbeat_keeps_the_lease_alive(monkeypatch):
    gate = a_gate(monkeypatch)
    token = gate.acquire("comfyui", "sd35", 0)
    for _ in range(6):
        time.sleep(0.1)
        assert gate.heartbeat(token) is True
    assert gate.get_status()["active"] is not None
    assert gate.release(token) is True


# ---------------------------------------------------------------------------
# Memory: the driver's reading, and room asked of ComfyUI.

def test_a_run_that_asks_for_no_room_is_only_serialised(monkeypatch):
    sensor = Sensor(free=100.0)
    gate = a_gate(monkeypatch, sensor=sensor)
    posts = Posts()
    monkeypatch.setattr("requests.post", posts)
    token = gate.acquire("comfyui", "sd35", 0)
    assert posts.calls == []
    gate.release(token)


def test_short_room_asks_comfyui_to_unload_and_admits_once_the_room_is_there(monkeypatch):
    import config
    sensor = Sensor(free=4000.0)
    gate = a_gate(monkeypatch, sensor=sensor)
    gate._last_key = "sd35"

    def freed():
        sensor.free = 30000.0
    posts = Posts(on_call=freed)
    monkeypatch.setattr("requests.post", posts)
    token = gate.acquire("voxcpm-load", "voxcpm", 6774)
    url, kw = posts.calls[0]
    assert url == f"http://127.0.0.1:{config.COMFYUI_PORT}/free"
    assert kw["json"] == {"unload_models": True, "free_memory": True}
    assert gate.get_status()["resident_model"] is None  # what ComfyUI held is gone
    assert gate.get_status()["last_free_ask"] == "ComfyUI was asked to unload its models"
    gate.release(token)


def test_room_that_stays_short_is_refused_with_both_numbers_and_what_was_asked(monkeypatch):
    sensor = Sensor(free=4000.0)
    gate = a_gate(monkeypatch, sensor=sensor)
    posts = Posts()
    monkeypatch.setattr("requests.post", posts)
    with pytest.raises(G.GpuBusy) as caught:
        gate.acquire("voxcpm-load", "voxcpm", 6774)
    e = caught.value
    assert e.reason == "no_memory" and e.free_mb == 4000.0 and e.required_mb == 6774
    assert "6774MB" in str(e) and "4000MB free" in str(e)
    assert "ComfyUI was asked to unload its models and" in str(e)
    assert "later the room was still short" in str(e)
    assert gate.get_status()["active"] is None  # the refused lease holds nothing


def test_a_comfyui_that_does_not_take_the_request_is_named_in_the_refusal(monkeypatch):
    gate = a_gate(monkeypatch, sensor=Sensor(free=4000.0))
    monkeypatch.setattr("requests.post", Posts(raises=ConnectionError("refused")))
    with pytest.raises(G.GpuBusy) as caught:
        gate.acquire("voxcpm-load", "voxcpm", 6774)
    assert "ComfyUI did not take the request to unload" in str(caught.value)
    assert "refused" in str(caught.value)


def test_comfyui_is_not_asked_twice_within_the_gap(monkeypatch):
    gate = a_gate(monkeypatch, sensor=Sensor(free=4000.0))
    posts = Posts()
    monkeypatch.setattr("requests.post", posts)
    for _ in range(2):
        with pytest.raises(G.GpuBusy):
            gate.acquire("voxcpm-load", "voxcpm", 6774)
    assert len(posts.calls) == 1


def test_a_sensor_that_stops_answering_refuses_after_three_misses_and_names_the_hardware(monkeypatch):
    sensor = Sensor(free=None)
    sensor.why = "NVMLError_GpuIsLost"
    gate = a_gate(monkeypatch, sensor=sensor)
    for _ in range(2):
        gate.release(gate.acquire("comfyui", "sd35", 0))   # a miss is a hiccup
    with pytest.raises(G.GpuBusy) as caught:
        gate.acquire("comfyui", "sd35", 0)
    assert str(caught.value).startswith("GPU not reachable")
    assert "NVMLError_GpuIsLost" in str(caught.value)
    assert caught.value.reason == "sensor_lost"    # never "busy": nobody is told to try again
    assert gate.get_status()["degraded"] is True
    sensor.free = 50000.0
    gate.release(gate.acquire("comfyui", "sd35", 0))       # answering again: admitted
    assert gate.get_status()["degraded"] is False


def test_without_a_sensor_the_gate_serialises_and_says_so_once(monkeypatch, caplog):
    gate = a_gate(monkeypatch, sensor=Sensor(configured=False, free=None))
    with caplog.at_level("WARNING"):
        gate.release(gate.acquire("voxcpm-load", "voxcpm", 6774))
        gate.release(gate.acquire("voxcpm-load", "voxcpm", 6774))
    said = [r.getMessage() for r in caplog.records if "NVML not configured" in r.getMessage()]
    assert len(said) == 1
    assert gate.get_status()["sensor"] == "none"


# ---------------------------------------------------------------------------
# What the gate tells about the queue, and about the card.

def test_the_plan_gives_each_waiting_run_its_place(monkeypatch):
    gate = a_gate(monkeypatch)
    held = gate.acquire("comfyui", "sd35", 0, label="running")
    t1, b1 = in_thread(gate.acquire, "comfyui", "sd35", 0, 2, "second")
    time.sleep(0.05)
    t2, b2 = in_thread(gate.acquire, "comfyui", "flux", 0, 2, "third")
    time.sleep(0.05)
    plan = gate.plan()
    assert plan["active"]["label"] == "running"
    assert [(q["position"], q["label"]) for q in plan["queue"]] == [(1, "second"), (2, "third")]
    assert plan["queue_length"] == 2
    gate.release(held)
    t1.join(2)
    gate.release(b1["value"])
    t2.join(2)
    gate.release(b2["value"])


def test_the_card_reading_names_comfyuis_models_and_the_gate_beside_them(monkeypatch):
    sensor = Sensor(free=60000.0, total=98000.0)
    gate = a_gate(monkeypatch, sensor=sensor)
    monkeypatch.setattr(G, "read_comfyui_card", lambda port, **kw: {
        "reachable": True, "error": "", "free_mb": 59000.0, "total_mb": 98000.0,
        "loaded_models": [{"model": "SD3", "vram_mb": 16000.0, "size_mb": 16000.0, "in_use": True},
                          {"model": "stable_audio:stable-audio-open-small", "vram_mb": 2000.0,
                           "size_mb": 2000.0, "in_use": False}]})
    status = gate.vram_status()
    assert status["free_mb"] == 60000.0 and status["total_mb"] == 98000.0
    assert status["nvml_available"] is True
    assert status["registered_backends"] == ["comfyui"]
    assert [m["model"] for m in status["loaded_models"]] == ["SD3", "stable_audio:stable-audio-open-small"]
    assert status["loaded_models"][0] == {"backend": "comfyui", "model": "SD3", "vram_mb": 16000.0,
                                          "priority": "-", "in_use": 1, "last_used": None,
                                          "source": "card"}
    assert status["comfyui"]["reachable"] is True
    assert status["gate"]["active"] is None


def test_a_comfyui_that_does_not_answer_leaves_the_model_list_empty_and_says_why(monkeypatch):
    gate = a_gate(monkeypatch, sensor=Sensor())
    monkeypatch.setattr(G, "read_comfyui_card", lambda port, **kw: {
        "reachable": False, "error": "ComfyUI is not answering http://127.0.0.1:1/ai4artsed/card",
        "loaded_models": []})
    status = gate.vram_status()
    assert status["loaded_models"] == [] and status["registered_backends"] == []
    assert status["comfyui"]["reachable"] is False
    assert "not answering" in status["comfyui"]["error"]


def test_the_card_is_asked_of_the_node_package(monkeypatch):
    class Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"free_mb": 1.0, "total_mb": 2.0, "loaded_models": [{"model": "SD3"}]}
    calls = []

    def get(url, **kw):
        calls.append((url, kw))
        return Resp()
    monkeypatch.setattr("requests.get", get)
    out = G.read_comfyui_card("17804")
    assert calls[0][0] == "http://127.0.0.1:17804/ai4artsed/card"
    assert calls[0][1]["timeout"][1] is not None    # an administrative request, bounded
    assert out["reachable"] is True and out["loaded_models"] == [{"model": "SD3"}]


def test_processes_on_the_card_are_labelled_by_what_they_are_to_the_platform(monkeypatch):
    import os
    import config
    me = os.getpid()
    port = str(config.COMFYUI_PORT)
    monkeypatch.setattr(G, "_proc_parent", lambda pid: me if pid == 11 else 1)
    monkeypatch.setattr(G, "_proc_cwd", lambda pid: "/x/ai/gpu_service" if pid == 16 else "/x/ai")
    assert G._label_process(me, "python server.py", me, port) == "self"
    # A child by what it runs, named like the lease kind that holds the slot for it.
    assert G._label_process(11, "/usr/bin/blender --background", me, port) == "blender"
    assert G._label_process(11, "/x/kohya/venv/bin/python /x/kohya/sd-scripts/sd3_train_network.py "
                            "--config_file c.toml", me, port) == "lora_training"
    assert G._label_process(11, "python worker.py", me, port) == "child"
    # A ComfyUI this process started is a child too, and reads as ComfyUI.
    assert G._label_process(11, f"python main.py --port {port}", me, port) == "comfyui"
    assert G._label_process(12, f"python main.py --port {port} --listen", me, port) == "comfyui"
    assert G._label_process(13, f"python main.py --port {port}5", me, port) == "foreign"
    assert G._label_process(14, "python voxcpm_service/server.py", me, port) == "voxcpm"
    assert G._label_process(15, "python train.py", me, port) == "foreign"
    assert G._label_process(16, "python server.py", me, port) == "gpu_service"
    # Without the port handed in, ComfyUI cannot be told apart — and is not
    # guessed at from a config import inside the reading.
    assert G._label_process(12, f"python main.py --port {port} --listen", me) == "foreign"


# ---------------------------------------------------------------------------
# The client: a lease is a call on the gate in this process.

class FakeGate:
    def __init__(self, busy=None, alive=True):
        self.calls = []
        self.busy = busy
        self.alive = alive

    def acquire(self, kind, model_id, required_mb, priority=2, label="", workload="", timeout_s=None):
        self.calls.append(("acquire", kind, model_id, required_mb, label, workload, timeout_s))
        if self.busy:
            raise self.busy
        return "tok-1"

    def heartbeat(self, token):
        self.calls.append(("heartbeat", token))
        return self.alive

    def release(self, token, failed=False):
        self.calls.append(("release", token, failed))
        return True


def test_the_sync_lease_takes_and_gives_back_the_slot(monkeypatch):
    gate = FakeGate()
    monkeypatch.setattr(L, "get_gpu_gate", lambda: gate)
    with L.gpu_lease_sync("voxcpm", "voxcpm", 0, label="speak", workload="voxcpm:speak") as token:
        assert token == "tok-1"
    assert gate.calls[0] == ("acquire", "voxcpm", "voxcpm", 0, "speak", "voxcpm:speak", None)
    assert gate.calls[-1] == ("release", "tok-1", False)


def test_a_body_that_raises_gives_the_slot_back_as_failed(monkeypatch):
    gate = FakeGate()
    monkeypatch.setattr(L, "get_gpu_gate", lambda: gate)
    with pytest.raises(RuntimeError, match="broke"):
        with L.gpu_lease_sync("comfyui", "sd35", 0):
            raise RuntimeError("the render broke")
    assert gate.calls[-1] == ("release", "tok-1", True)


def test_the_gates_refusal_reaches_the_caller_with_its_token(monkeypatch):
    gate = FakeGate(busy=G.GpuBusy("device busy: a LoRA training is running", reason="long_hold",
                                   holder_kind="lora_training"))
    monkeypatch.setattr(L, "get_gpu_gate", lambda: gate)
    with pytest.raises(L.GpuBusyError) as caught:
        with L.gpu_lease_sync("comfyui", "sd35", 0):
            pass
    assert caught.value.reason == "long_hold" and caught.value.holder_kind == "lora_training"
    assert "LoRA training" in str(caught.value)
    assert not any(c[0] == "release" for c in gate.calls)


def test_the_sync_lease_beats_while_it_is_held(monkeypatch):
    gate = FakeGate()
    monkeypatch.setattr(L, "get_gpu_gate", lambda: gate)
    with L.gpu_lease_sync("comfyui", "sd35", 0, heartbeat_interval_s=0.05):
        time.sleep(0.3)
    assert sum(1 for c in gate.calls if c[0] == "heartbeat") >= 3


def test_the_async_lease_does_the_same_without_blocking_the_loop(monkeypatch):
    gate = FakeGate()
    monkeypatch.setattr(L, "get_gpu_gate", lambda: gate)

    async def run():
        async with L.gpu_lease("comfyui", "sd35", 0, heartbeat_interval_s=0.05, label="r") as token:
            assert token == "tok-1"
            await asyncio.sleep(0.2)
    asyncio.run(run())
    assert gate.calls[0][:2] == ("acquire", "comfyui") and gate.calls[0][4] == "r"
    assert sum(1 for c in gate.calls if c[0] == "heartbeat") >= 2
    assert gate.calls[-1] == ("release", "tok-1", False)


def test_the_async_refusal_is_the_same_error(monkeypatch):
    gate = FakeGate(busy=G.GpuBusy("device busy: 40 operations already waiting", reason="queue_full",
                                   waiting=40))
    monkeypatch.setattr(L, "get_gpu_gate", lambda: gate)

    async def run():
        async with L.gpu_lease("comfyui", "sd35", 0):
            pass
    with pytest.raises(L.GpuBusyError) as caught:
        asyncio.run(run())
    assert caught.value.reason == "queue_full" and caught.value.waiting == 40


def test_the_client_no_longer_asks_another_service():
    src = inspect.getsource(L)
    assert "import requests" not in src and "import aiohttp" not in src
    assert "GPU_SERVICE_URL" not in src
    assert "unleased" not in src.split('"""', 2)[2]   # the word survives only in the docstring's history


# ---------------------------------------------------------------------------
# The routes: the gate on HTTP for whoever is not this process.

@pytest.fixture()
def app(monkeypatch):
    from flask import Flask
    from my_app.routes import gpu_gate_routes as R
    gate = a_gate(monkeypatch)
    monkeypatch.setattr(R, "get_gpu_gate", lambda: gate)
    a = Flask(__name__)
    a.register_blueprint(R.gpu_gate_bp)
    a.config["TESTING"] = True
    a.secret_key = "a key for the settings guard's session"
    return a


def test_a_lease_over_http_lives_on_its_token(app):
    c = app.test_client()
    r = c.post("/api/gate/lease/acquire", json={"kind": "research", "model_id": "sd35", "label": "r1"})
    assert r.status_code == 200
    token = r.get_json()["token"]
    assert c.get("/api/gate/status").get_json()["active"]["label"] == "r1"
    assert c.post("/api/gate/lease/heartbeat", json={"token": token}).status_code == 200
    shown = c.get("/api/gate/plan").get_json()["active"]["id"]
    assert shown != token                     # the readings name the lease, never its token
    assert c.get("/api/gate/status").get_json()["active"]["id"] == shown
    assert c.post("/api/gate/lease/release", json={"token": shown}).get_json() == {"ok": False}
    assert c.post("/api/gate/lease/release", json={"token": token}).get_json() == {"ok": True}
    assert c.post("/api/gate/lease/heartbeat", json={"token": token}).status_code == 404
    assert c.get("/api/gate/status").get_json()["active"] is None


def test_a_refusal_over_http_carries_its_token(app):
    c = app.test_client()
    c.post("/api/gate/lease/acquire", json={"kind": "lora_training", "model_id": "lora"})
    r = c.post("/api/gate/lease/acquire", json={"kind": "research", "model_id": "sd35"})
    assert r.status_code == 503
    body = r.get_json()
    assert body["code"] == "gpu_busy" and body["busy_reason"] == "long_hold"
    assert body["holder_kind"] == "lora_training"
    assert "LoRA training" in body["detail"] and body["error"] == body["detail"]
    assert L.GpuBusyError.from_payload(body).reason == "long_hold"


def test_the_stats_and_the_advice_answer(app):
    c = app.test_client()
    stats = c.get("/api/gate/stats").get_json()
    assert set(stats) == {"models", "trusted_samples", "spread_limit"}
    advice = c.get("/api/gate/prefetch-advice").get_json()
    assert advice["recommended"] is None and advice["reason"] == "prefetch disabled"
    assert c.post("/api/gate/prefetch-claim", json={"model_id": "sd35"}).get_json() == {"claimed": True}
    assert c.post("/api/gate/prefetch-claim", json={"model_id": "flux"}).get_json() == {"claimed": False}
    assert c.post("/api/gate/prefetch-done", json={"model_id": "sd35"}).get_json() == {"ok": True}
    assert c.post("/api/gate/prefetch-claim", json={}).status_code == 400


def test_the_card_answers_over_http(app, monkeypatch):
    monkeypatch.setattr(G, "read_comfyui_card", lambda port, **kw: {
        "reachable": True, "error": "", "loaded_models": [{"model": "SD3", "vram_mb": 1.0, "in_use": False}]})
    body = app.test_client().get("/api/gate/vram").get_json()
    assert body["loaded_models"][0]["model"] == "SD3"
    assert body["gate"]["active"] is None


def test_a_body_that_is_not_an_object_is_refused_not_crashed(app):
    c = app.test_client()
    assert c.post("/api/gate/lease/acquire", json=[1, 2]).status_code == 400
    assert c.post("/api/gate/lease/acquire", json={"required_mb": "much"}).status_code == 400
    assert c.post("/api/gate/lease/heartbeat", json=[1]).status_code == 404
    assert c.post("/api/gate/lease/release", json="x").get_json() == {"ok": False}


# ---------------------------------------------------------------------------
# What ComfyUI answers about its card, from the node package.

class _Patcher:
    def __init__(self, inner):
        self.model = inner


class _Loaded:
    def __init__(self, patcher, loaded, size, used):
        self._patcher = patcher
        self._loaded = loaded
        self._size = size
        self.currently_used = used

    @property
    def model(self):
        return self._patcher

    def model_loaded_memory(self):
        return self._loaded

    def model_memory(self):
        return self._size


def test_the_package_lists_what_comfyui_holds(monkeypatch):
    class SD3:
        pass
    mm = types.ModuleType("comfy.model_management")
    mm.get_torch_device = lambda: "cuda:0"
    mm.get_free_memory = lambda dev: 60 * 1024 ** 3
    mm.get_total_memory = lambda dev: 96 * 1024 ** 3
    first, third = _Patcher(SD3()), _Patcher(SD3())
    mm.current_loaded_models = [_Loaded(first, 16 * 1024 ** 3, 16 * 1024 ** 3, True),
                                _Loaded(_Patcher(None), 0, 0, False),
                                _Loaded(third, 8 * 1024 ** 3, 16 * 1024 ** 3, False)]
    comfy = types.ModuleType("comfy")
    comfy.model_management = mm
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", mm)
    queue = types.SimpleNamespace(currently_running={7: "a prompt"})
    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(prompt_queue=queue, routes=None))
    monkeypatch.setitem(sys.modules, "server", server)
    routes = load_module("ai4artsed_card_routes_under_test", PACKAGE / "_card_routes.py", register=True)
    out = routes.card()
    assert out["free_mb"] == 60 * 1024 and out["total_mb"] == 96 * 1024
    names = [m["model"] for m in out["loaded_models"]]
    assert sorted(names) == ["NoneType", "SD3", "SD3 #2"]
    assert [m["vram_mb"] for m in out["loaded_models"]] == [16 * 1024.0, 0.0, 8 * 1024.0]
    assert [m["size_mb"] for m in out["loaded_models"]] == [16 * 1024.0, 0.0, 16 * 1024.0]
    assert [m["in_use"] for m in out["loaded_models"]] == [True, False, False]
    # The number follows the object, not the place in the list: ComfyUI moves
    # the model it just used to the front, and the two lines must not swap.
    assert (names[0] == "SD3") == (id(first) < id(third))
    mm.current_loaded_models.reverse()
    assert [m["model"] for m in routes.card()["loaded_models"]] == list(reversed(names))
    # A model kept on the CPU (a text encoder under --lowvram) has nothing on the card.
    offloaded = _Loaded(_Patcher(SD3()), 0, 4 * 1024 ** 3, False)
    offloaded.device = "cpu"
    mm.current_loaded_models.append(offloaded)
    assert len(routes.card()["loaded_models"]) == 3
    # The card idle: ComfyUI keeps its "used" mark until it frees memory,
    # and the mark alone would call every model of the last run busy.
    queue.currently_running = {}
    assert [m["in_use"] for m in routes.card()["loaded_models"]] == [False, False, False]


def test_a_station_model_is_named_by_its_station_and_key(monkeypatch):
    """The route reads the registries of the package's _card; here the
    package is a stand-in with a _card of the test's own."""
    module = object()
    patcher = _Patcher(module)

    class Registry:
        name = "stable_audio"

        def keys(self):
            return ["stable-audio-open-small"]

        def peek(self, key):
            return types.SimpleNamespace(patcher=patcher, module=module)
    pkg = types.ModuleType("ai4artsed_pkg_under_test")
    pkg.__path__ = []
    card = types.ModuleType("ai4artsed_pkg_under_test._card")
    card._registries = [Registry()]
    monkeypatch.setitem(sys.modules, "ai4artsed_pkg_under_test", pkg)
    monkeypatch.setitem(sys.modules, "ai4artsed_pkg_under_test._card", card)
    spec = importlib.util.spec_from_file_location("ai4artsed_pkg_under_test._card_routes",
                                                  PACKAGE / "_card_routes.py")
    routes = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, routes)
    spec.loader.exec_module(routes)
    assert routes._station_name(patcher, module) == "stable_audio:stable-audio-open-small"
    assert routes._station_name(_Patcher(None), None) == ""


def test_the_package_registers_the_card_route():
    init = (PACKAGE / "__init__.py").read_text()
    assert "_card_routes" in init and "_card_routes.install()" in init
    src = (PACKAGE / "_card_routes.py").read_text()
    assert '"/ai4artsed/card"' in src


# ---------------------------------------------------------------------------
# The readers that left the GPU service in this stage.

def test_the_forecast_reads_the_gate_in_process():
    from my_app.routes import schema_pipeline_routes as S
    src = inspect.getsource(S._gate_plan)
    assert "get_gpu_gate" in src and "GPU_SERVICE_URL" not in src
    assert not hasattr(S, "_gate_plan_cache") and not hasattr(S, "_gate_session")


def test_the_forecast_places_a_run_from_the_gates_plan(monkeypatch):
    from my_app.routes import schema_pipeline_routes as S
    gate = a_gate(monkeypatch)
    monkeypatch.setattr(G, "get_gpu_gate", lambda: gate)
    held = gate.acquire("comfyui", "sd35", 0, label="run-a")
    t, box = in_thread(gate.acquire, "comfyui", "sd35", 0, 2, "run-b")
    time.sleep(0.05)
    assert S._gate_place("run-a") == (0, 0.0)
    ahead, _seconds = S._gate_place("run-b")
    assert ahead == 1
    assert S._gate_place("run-c") == (None, None)
    gate.release(held)
    t.join(2)
    gate.release(box["value"])


def test_the_settings_page_and_resona_read_the_card_through_the_gate():
    from my_app.routes import settings_routes as SR
    from my_app.services import resona_hardware as RH
    from my_app.services import gpu_warm_ahead as W
    for module in (SR, RH, W):
        code = "\n".join(line for line in inspect.getsource(module).splitlines()
                         if not line.strip().startswith("#"))
        assert "get_gpu_gate" in code
        assert "/api/health" not in code
        assert "/api/gpu/admission" not in code


def test_resona_reads_comfyuis_models_through_the_gate(monkeypatch):
    from my_app.services import resona_hardware as RH

    class Gate:
        def vram_status(self, **kw):
            assert kw["card_timeout"][1] <= 3   # on the prompt's path: a short read
            return {"comfyui": {"reachable": True},
                    "loaded_models": [
                        {"backend": "comfyui", "model": "SD3", "vram_mb": 1.0, "source": "card"},
                        # The processes on the card, named by their command
                        # lines, are for the settings page, not for a prompt.
                        {"backend": "gpu_service", "model": "llama-server -m q.gguf",
                         "vram_mb": 16.0, "source": "driver"}]}
    monkeypatch.setattr(G, "get_gpu_gate", lambda: Gate())
    assert RH._read_loaded_models() == [{"backend": "comfyui", "model": "SD3", "vram_mb": 1.0,
                                         "source": "card"}]

    class Down:
        def vram_status(self, **kw):
            return {"comfyui": {"reachable": False, "error": "x"}, "loaded_models": []}
    monkeypatch.setattr(G, "get_gpu_gate", lambda: Down())
    assert RH._read_loaded_models() is None


def test_the_gate_is_registered_on_the_app():
    src = (REPO / "devserver" / "my_app" / "__init__.py").read_text()
    assert "gpu_gate_bp" in src and "register_blueprint(gpu_gate_bp)" in src


def test_the_gate_settings_stand_in_the_devservers_config():
    import config
    for name in ("GPU_ADMISSION_ACQUIRE_TIMEOUT_S", "GPU_ADMISSION_HEARTBEAT_TIMEOUT_S",
                 "GPU_ADMISSION_MAX_WAITERS", "GPU_ADMISSION_AFFINITY", "GPU_ADMISSION_PREFETCH",
                 "GPU_ADMISSION_FREE_WAIT_S"):
        assert hasattr(config, name), name
    assert config.GPU_ADMISSION_PREFETCH is False


# ---------------------------------------------------------------------------
# What the three reviews of the stage-7 build asked for (2026-09-15).

def test_a_lease_refused_without_an_ask_leaves_the_resident_model_known(monkeypatch):
    """Turned away at admission, nothing ran and nothing was unloaded — the
    next same-model run must still be priced warm."""
    sensor = Sensor(free=4000.0)
    gate = a_gate(monkeypatch, sensor=sensor)
    sensor.free = 60000.0
    gate.release(gate.acquire("comfyui", "sd35", 0))
    assert gate.get_status()["resident_model"] == "sd35"
    sensor.free = 4000.0
    gate._last_free_ask_at = time.time()          # asked a moment ago: not asked again
    monkeypatch.setattr("requests.post", Posts())
    with pytest.raises(G.GpuBusy) as caught:
        gate.acquire("voxcpm-load", "voxcpm", 6774)
    assert "not asked again" in str(caught.value)
    assert gate.get_status()["resident_model"] == "sd35"
    assert gate.get_status()["active"] is None


def test_the_heartbeat_is_kept_while_admission_waits_for_the_room(monkeypatch):
    """The holder has no token during the wait; the reaper must not take the
    lease from under it."""
    sensor = Sensor(free=4000.0)
    # The wait reads the card every 0.5 s; a heartbeat timeout of 0.6 s
    # would be exceeded by the wait itself if the lease were not stamped.
    gate = a_gate(monkeypatch, sensor=sensor, GPU_ADMISSION_HEARTBEAT_TIMEOUT_S=0.6,
                  GPU_ADMISSION_FREE_WAIT_S=3.0)

    def freed_later():
        threading.Timer(1.3, lambda: setattr(sensor, "free", 30000.0)).start()
    monkeypatch.setattr("requests.post", Posts(on_call=freed_later))
    token = gate.acquire("voxcpm-load", "voxcpm", 6774)
    status = gate.get_status()
    assert status["active"] is not None            # not reaped during the wait
    assert gate.release(token) is True


def test_the_status_carries_no_token(monkeypatch):
    gate = a_gate(monkeypatch)
    token = gate.acquire("comfyui", "sd35", 0)
    status = gate.get_status()
    assert "lease_tokens" not in status and status["leases"] == 1
    # The lease is named, and the name releases nothing.
    assert status["active"]["id"] != token and gate.release(status["active"]["id"]) is False
    assert gate.release(token) is True


def test_every_process_of_the_platforms_is_on_the_list(monkeypatch):
    """ComfyUI's models as ComfyUI lists them, the rest of its process as one
    line, the VoxCPM worker and the GPU service as one line each — so own,
    foreign and free add up to the card (98000 = 63000 own + 5000 foreign +
    30000 free). The strangers stay where they were."""
    sensor = Sensor(free=30000.0, total=98000.0)
    sensor.read = lambda: {
        "total_mb": 98000.0, "used_mb": 68000.0, "free_mb": 30000.0, "foreign_mb": 5000.0,
        "processes": [
            {"pid": 1, "vram_mb": 0.0, "vram_unknown": True, "foreign": False, "owned": False,
             "label": "self", "cmdline": "python server.py"},
            {"pid": 2, "vram_mb": 31000.0, "vram_unknown": False, "foreign": False, "owned": False,
             "label": "comfyui", "cmdline": "python main.py --port 17804"},
            {"pid": 3, "vram_mb": 6774.0, "vram_unknown": False, "foreign": False, "owned": False,
             "label": "voxcpm", "cmdline": "python voxcpm_service/server.py"},
            {"pid": 4, "vram_mb": 25226.0, "vram_unknown": False, "foreign": False, "owned": False,
             "label": "gpu_service", "cmdline": "python server.py"},
            {"pid": 5, "vram_mb": 5000.0, "vram_unknown": False, "foreign": True, "owned": False,
             "label": "foreign", "cmdline": "python train.py"},
        ]}
    gate = a_gate(monkeypatch, sensor=sensor)
    monkeypatch.setattr(G, "read_comfyui_card", lambda port, **kw: {
        "reachable": True, "error": "", "free_mb": 30000.0, "total_mb": 98000.0,
        "loaded_models": [{"model": "SD3", "vram_mb": 26000.0, "size_mb": 26000.0, "in_use": False}]})
    token = gate.acquire("voxcpm", "voxcpm", 0)
    status = gate.vram_status()
    rows = status["loaded_models"]
    gate.release(token)
    by_backend = {(r["backend"], r["model"]): r for r in rows}
    assert ("comfyui", "SD3") in by_backend and by_backend[("comfyui", "SD3")]["source"] == "card"
    beyond = [r for r in rows if r["backend"] == "comfyui" and r["model"] != "SD3"]
    assert len(beyond) == 1 and beyond[0]["vram_mb"] == 5000.0   # 31000 - 26000
    assert beyond[0]["source"] == "driver"
    vox = [r for r in rows if r["backend"] == "voxcpm"]
    assert len(vox) == 1 and vox[0]["vram_mb"] == 6774.0 and vox[0]["in_use"] == 1
    assert vox[0]["model"] == "voxcpm_service/server.py" and vox[0]["source"] == "driver"
    svc = [r for r in rows if r["backend"] == "gpu_service"]
    assert len(svc) == 1 and svc[0]["vram_mb"] == 25226.0 and svc[0]["in_use"] == 0
    assert svc[0]["vram_unknown"] is False
    assert not [r for r in rows if r["backend"] in ("self", "foreign")]
    own = sum(r["vram_mb"] for r in rows)
    assert own == 26000.0 + 5000.0 + 6774.0 + 25226.0
    assert own + status["foreign_vram_mb"] + status["free_mb"] == status["total_mb"]
    # The GPU service names itself on its leases, and its line reads "in use"
    # while one of them holds the slot — whatever kind the lease carries.
    token = gate.acquire("diffusers", "sd35", 0, holder="gpu_service")
    rows = gate.vram_status()["loaded_models"]
    gate.release(token)
    assert [r for r in rows if r["backend"] == "gpu_service"][0]["in_use"] == 1
    assert [r for r in rows if r["backend"] == "voxcpm"][0]["in_use"] == 0

    # ComfyUI up, its list not there: its whole process as one line that says so.
    monkeypatch.setattr(G, "read_comfyui_card", lambda port, **kw: {
        "reachable": False, "error": "ComfyUI answered http://127.0.0.1:1/ai4artsed/card with HTTP 404: x",
        "loaded_models": []})
    rows = gate.vram_status()["loaded_models"]
    comfy = [r for r in rows if r["backend"] == "comfyui"]
    assert len(comfy) == 1 and comfy[0]["vram_mb"] == 31000.0
    assert "HTTP 404" in comfy[0]["model"]


def test_a_comfyui_without_the_list_is_logged_as_well_as_reported(monkeypatch, caplog):
    class Resp:
        status_code = 404
        text = "not found"

        def json(self):
            return {}
    monkeypatch.setattr("requests.get", lambda url, **kw: Resp())
    monkeypatch.setattr(G, "_card_warned_at", 0.0)
    with caplog.at_level(logging.WARNING, logger="my_app.services.gpu_gate"):
        out = G.read_comfyui_card("17804")
        again = G.read_comfyui_card("17804")
    assert out["reachable"] is False and "HTTP 404" in out["error"] and again["reachable"] is False
    warnings = [r for r in caplog.records if "HTTP 404" in r.getMessage()]
    assert len(warnings) == 1                       # once in a while, not once per poll
    assert "package loaded" in warnings[0].getMessage()


def test_the_card_read_is_short(monkeypatch):
    calls = []

    class Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"free_mb": 1.0, "total_mb": 2.0, "loaded_models": []}
    monkeypatch.setattr("requests.get", lambda url, **kw: calls.append(kw) or Resp())
    G.read_comfyui_card("17804")
    assert calls[0]["timeout"][1] <= 5
    G.read_comfyui_card("17804", timeout=(2, 3))
    assert calls[1]["timeout"] == (2, 3)


def test_the_measurements_have_a_file_of_their_own_seeded_from_the_old_hosts(tmp_path, monkeypatch):
    from my_app.services import gpu_model_stats as S
    old = tmp_path / "gpu_model_stats.json"
    old.write_text(json.dumps({"version": 1, "models": {
        "hold:comfyui:sd35": {"samples": 5, "mean": 40.0}}}))
    own = tmp_path / "gate_model_stats.json"
    monkeypatch.setattr(S, "_SEED_PATH", str(old))
    stats = S.ModelStats(path=str(own))
    assert stats.snapshot() != {}                # the old host's readings came over
    stats.flush()
    assert own.exists()                          # and are written to the own file from now on
    assert json.loads(old.read_text())["models"]["hold:comfyui:sd35"]["samples"] == 5   # untouched
    assert S._DEFAULT_PATH != S._SEED_PATH and S._DEFAULT_PATH.endswith("gate_model_stats.json")
    # A second start reads the own file, not the seed.
    old.unlink()
    assert S.ModelStats(path=str(own)).snapshot() == stats.snapshot()


def test_the_writing_routes_are_for_this_machine(app):
    """A visitor through the tunnel reads the gate and takes nothing from it."""
    c = app.test_client()
    outside = {"CF-Connecting-IP": "203.0.113.7"}
    assert c.get("/api/gate/status", headers=outside).status_code == 200
    assert c.get("/api/gate/plan", headers=outside).status_code == 200
    assert c.post("/api/gate/lease/acquire", json={"kind": "x"}, headers=outside).status_code == 401
    assert c.post("/api/gate/lease/release", json={"token": "t"}, headers=outside).status_code == 401
    assert c.post("/api/gate/lease/heartbeat", json={"token": "t"}, headers=outside).status_code == 401
    assert c.post("/api/gate/prefetch-claim", json={"model_id": "m"}, headers=outside).status_code == 401
    assert c.post("/api/gate/prefetch-done", json={"model_id": "m"}, headers=outside).status_code == 401
    # Another machine on the network: the address decides, whatever Host it names.
    lan = {"REMOTE_ADDR": "192.168.1.5"}
    assert c.post("/api/gate/lease/acquire", json={"kind": "x"}, environ_base=lan).status_code == 401
    assert c.post("/api/gate/lease/acquire", json={"kind": "x"}, environ_base=lan,
                  headers={"Host": "localhost"}).status_code == 401
    assert c.get("/api/gate/status", environ_base=lan).status_code == 200
    assert c.get("/api/gate/status").get_json()["active"] is None
    r = c.post("/api/gate/lease/acquire", json={"kind": "research", "model_id": "sd35"})
    assert r.status_code == 200
    c.post("/api/gate/lease/release", json={"token": r.get_json()["token"]})


def test_a_lease_nobody_ever_reported_in_on_is_collected_after_the_grace(monkeypatch, caplog):
    """A client that dropped its connection while it waited gets a token
    nobody holds; that lease goes after the grace, not after the whole
    heartbeat timeout. One that reported in once lives on."""
    gate = a_gate(monkeypatch, GPU_ADMISSION_HEARTBEAT_TIMEOUT_S=5.0,
                  GPU_ADMISSION_FIRST_BEAT_GRACE_S=0.1)
    with caplog.at_level(logging.WARNING, logger="my_app.services.gpu_gate"):
        token = gate.acquire("comfyui", "sd35", 0)
        time.sleep(0.3)
    assert gate.get_status()["active"] is None
    assert gate.heartbeat(token) is False
    assert [r for r in caplog.records if "never reported in" in r.getMessage()]
    token2 = gate.acquire("comfyui", "sd35", 0)
    time.sleep(0.05)
    assert gate.heartbeat(token2) is True
    time.sleep(0.3)
    assert gate.get_status()["active"] is not None
    gate.release(token2)


def test_room_that_comfyui_cannot_make_is_refused_without_the_ask(monkeypatch):
    """Until stage 8 the GPU service keeps models of its own on the card,
    and only its coordinator frees them. A shortfall larger than what
    ComfyUI holds is refused with the figures, and ComfyUI is left alone."""
    sensor = Sensor(free=4000.0)
    sensor.read = lambda: {
        "total_mb": 98000.0, "used_mb": 94000.0, "free_mb": 4000.0, "foreign_mb": 0.0,
        "processes": [
            {"pid": 2, "vram_mb": 5000.0, "vram_unknown": False, "foreign": False, "owned": False,
             "label": "comfyui", "cmdline": "python main.py --port 17804"},
            {"pid": 4, "vram_mb": 85000.0, "vram_unknown": False, "foreign": False, "owned": False,
             "label": "gpu_service", "cmdline": "python server.py"},
        ]}
    gate = a_gate(monkeypatch, sensor=sensor)
    posts = Posts()
    monkeypatch.setattr("requests.post", posts)
    with pytest.raises(G.GpuBusy) as caught:
        gate.acquire("voxcpm-load", "voxcpm", 12000)
    assert not posts.calls                                   # ComfyUI was never asked
    msg = str(caught.value)
    assert "ComfyUI holds 5000MB" in msg and "3000MB short" in msg
    assert "gpu_service (85000MB)" in msg
    assert caught.value.free_mb == 4000.0 and caught.value.required_mb == 12000.0
    assert gate.get_status()["last_free_ask"] == msg.split("; ", 1)[1]
    # A shortfall ComfyUI can cover is asked for, as before.

    def freed():
        sensor.free = 30000.0
    posts = Posts(on_call=freed)
    monkeypatch.setattr("requests.post", posts)
    token = gate.acquire("voxcpm-load", "voxcpm", 8000)
    assert len(posts.calls) == 1
    gate.release(token)


def test_a_holder_that_cleared_comfyui_says_so_at_the_release(app):
    """The GPU service's coordinator may ask ComfyUI to free everything
    during a hold; the release carries that, and the gate stops believing
    the model resident."""
    from my_app.routes import gpu_gate_routes as R
    gate = R.get_gpu_gate()
    c = app.test_client()
    r = c.post("/api/gate/lease/acquire", json={"kind": "diffusers", "model_id": "sd35",
                                              "holder": "gpu_service"})
    token = r.get_json()["token"]
    assert c.get("/api/gate/status").get_json()["active"]["holder"] == "gpu_service"
    c.post("/api/gate/lease/release", json={"token": token, "cleared_comfyui": False})
    assert gate.get_status()["resident_model"] is not None
    token = c.post("/api/gate/lease/acquire", json={"kind": "diffusers", "model_id": "sd35",
                                                   "holder": "gpu_service"}).get_json()["token"]
    c.post("/api/gate/lease/release", json={"token": token, "cleared_comfyui": True})
    assert gate.get_status()["resident_model"] is None


def test_a_binary_on_the_card_is_named_without_the_hosts_paths():
    line = G._short_cmdline("/home/u/ai/llama.cpp/build/bin/llama-server -m /home/u/models/q.gguf "
                            "--port 18000 --n-gpu-layers 99")
    assert line == "llama-server -m q.gguf"
    assert G._short_cmdline("/usr/bin/blender --background") == "blender"
    assert G._short_cmdline("python voxcpm_service/server.py") == "voxcpm_service/server.py"
    assert G._short_cmdline("") == ""


def test_the_driver_is_read_for_compute_and_graphics_contexts(monkeypatch):
    """A Blender render is a graphics context; the same process on both
    lists is one line; a process the driver cannot attribute keeps
    `vram_unknown` instead of a zero."""
    import os
    mb = 1024 ** 2
    fake = types.ModuleType("pynvml")
    fake.nvmlDeviceGetMemoryInfo = lambda h: types.SimpleNamespace(
        total=98000 * mb, used=40000 * mb, free=58000 * mb)
    fake.nvmlDeviceGetComputeRunningProcesses = lambda h: [
        types.SimpleNamespace(pid=21, usedGpuMemory=30000 * mb),
        types.SimpleNamespace(pid=22, usedGpuMemory=None)]
    fake.nvmlDeviceGetGraphicsRunningProcesses = lambda h: [
        types.SimpleNamespace(pid=22, usedGpuMemory=None),
        types.SimpleNamespace(pid=23, usedGpuMemory=9000 * mb)]
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    me = os.getpid()
    lines = {21: "python main.py --port 17804", 22: "python x.py", 23: "/usr/bin/blender -b s.blend"}
    monkeypatch.setattr(G, "_proc_cmdline", lambda pid: lines[pid])
    monkeypatch.setattr(G, "_proc_parent", lambda pid: me if pid == 23 else 1)
    monkeypatch.setattr(G, "_proc_cwd", lambda pid: "/x")
    s = G.CardSensor.__new__(G.CardSensor)
    s.configured, s.why, s._handle, s._comfyui_port = True, "", object(), "17804"
    reading = s.read()
    assert [p["pid"] for p in reading["processes"]] == [21, 22, 23]
    by = {p["pid"]: p for p in reading["processes"]}
    assert by[21]["label"] == "comfyui" and by[21]["vram_mb"] == 30000.0
    assert by[23]["label"] == "blender" and by[23]["owned"] is True and by[23]["vram_mb"] == 9000.0
    assert by[22]["label"] == "foreign" and by[22]["vram_unknown"] is True and by[22]["vram_mb"] == 0.0
    assert reading["foreign_mb"] == 0.0 and reading["free_mb"] == 58000.0
