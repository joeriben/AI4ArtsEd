"""
Since stage 7 of the move to ComfyUI the plant-wide gate is the DevServer's;
this service, standing until stage 8, takes its turn there for every hold
of its own (services/gpu_admission.py, _lease_upstream). What this checks:
the turn is taken before the local slot and given back with it, the
DevServer's refusal is this gate's refusal, a DevServer that does not answer
is asked again and then refused with the URL in the sentence, a DevServer
without gate routes leaves this gate the plant's, every hold that carries a
token is kept alive there, a lease the DevServer no longer knows is said
once and only a 404 says so, and on the way out every turn goes back.
"""
import logging
import os
import sys
import threading
import time
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import gpu_admission as A  # noqa: E402


class Posts:
    """requests.post as the test sees it: what was asked, and how the
    DevServer's gate answers, by the tail of the URL. An answer may be a
    list, consumed one per call, the last one standing."""

    def __init__(self, **answers):
        self.calls = []
        self.answers = answers      # acquire=(status, body) | heartbeat=... | release=...

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        for name, answer in self.answers.items():
            if url.endswith("/api/gate/lease/" + name):
                if isinstance(answer, list):
                    answer = answer.pop(0) if len(answer) > 1 else answer[0]
                if isinstance(answer, Exception):
                    raise answer
                status, body = answer
                text = body if isinstance(body, str) else str(body)

                def _json(body=body):
                    if isinstance(body, str):
                        raise ValueError("not JSON")
                    return body
                return types.SimpleNamespace(status_code=status, text=text, json=_json)
        raise AssertionError(f"unexpected request to {url}")

    def named(self, name):
        return [(u, kw) for (u, kw) in self.calls if u.endswith("/api/gate/lease/" + name)]


@pytest.fixture
def gate(monkeypatch):
    import config
    monkeypatch.setattr(config, "GPU_ADMISSION_REAPER_INTERVAL_S", 0.02, raising=False)
    monkeypatch.setattr(A, "_UPSTREAM_RETRY_S", 0.05)
    monkeypatch.setattr(A, "_UPSTREAM_RETRY_GAP_S", 0.01)
    g = A.GpuAdmission()
    # Admission proper reads the card through the coordinator; the turn is
    # what is under test here.
    monkeypatch.setattr(g, "_admit", lambda lease: None)
    return g


def _posts(monkeypatch, **answers):
    posts = Posts(**answers)
    monkeypatch.setattr("requests.post", posts)
    return posts


def test_a_hold_here_is_a_lease_there(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T1"}), heartbeat=(200, {"ok": True}),
                   release=(200, {"ok": True}))
    with gate.slot("diffusers", "sd35", 29000, 2, label="run-7", workload="sd35_large_diffusers") as lease:
        url, kw = posts.calls[0]
        assert url == A.upstream_url() + "/api/gate/lease/acquire"
        assert kw["json"] == {"kind": "diffusers", "model_id": "sd35", "required_mb": 0,
                              "label": "run-7", "workload": "sd35_large_diffusers",
                              "holder": "gpu_service"}
        assert kw["timeout"][1] is None        # the wait is bounded there, not here
        assert lease.upstream_token == "T1"
        time.sleep(0.1)
        assert posts.named("heartbeat")        # the reaper keeps it alive
        assert posts.named("heartbeat")[0][1]["json"] == {"token": "T1"}
        with gate.slot("diffusers", "sd35", 0, 2):   # nested on the same thread
            pass
        assert len(posts.named("acquire")) == 1  # ...takes no second turn
    assert posts.named("release")[-1][1]["json"] == {"token": "T1", "failed": False,
                                                     "cleared_comfyui": False}
    assert lease.upstream_token == ""
    assert gate._active is None


def test_the_devservers_refusal_is_this_gates_refusal(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=(503, {"error": "device busy: a LoRA training holds the card",
                                               "detail": "device busy: a LoRA training holds the card",
                                               "busy_reason": "long_hold", "holder_kind": "lora_training",
                                               "waiting": 2, "free_mb": 0, "required_mb": 0}))
    with pytest.raises(A.GpuBusy) as caught:
        with gate.slot("diffusers", "sd35", 29000, 2):
            pass
    e = caught.value
    assert e.reason == "long_hold" and e.holder_kind == "lora_training" and e.waiting == 2
    assert "LoRA training" in str(e)
    assert gate._active is None and not posts.named("release")


def test_a_refusal_without_a_body_names_the_url(gate, monkeypatch):
    _posts(monkeypatch, acquire=(503, "<html>Service Unavailable</html>"))
    with pytest.raises(A.GpuBusy) as caught:
        with gate.slot("diffusers", "sd35", 29000, 2):
            pass
    assert "HTTP 503 from " + A.upstream_url() in str(caught.value)
    assert "Service Unavailable" in str(caught.value)


def test_a_devserver_that_does_not_answer_is_asked_again_and_then_refused(gate, monkeypatch, caplog):
    posts = _posts(monkeypatch, acquire=ConnectionError("connection refused"))
    with caplog.at_level(logging.WARNING, logger="services.gpu_admission"):
        with pytest.raises(A.GpuBusy) as caught:
            with gate.slot("diffusers", "sd35", 29000, 2):
                pass
    e = caught.value
    assert e.reason == "gate_unreachable"
    assert A.upstream_url() in str(e) and "connection refused" in str(e)
    assert "AI4ARTSED_DEVSERVER_URL" in str(e) and "PORT" in str(e)
    assert len(posts.named("acquire")) >= 3       # asked again, at the gap
    said = [r.getMessage() for r in caplog.records if "asked again" in r.getMessage()]
    assert len(said) == 1                          # said once, whatever the number of tries
    assert gate._active is None and not posts.named("release")


def test_a_devserver_that_comes_back_in_time_hands_out_the_turn(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=[ConnectionError("refused"), ConnectionError("refused"),
                                         (200, {"token": "T9"})],
                   heartbeat=(200, {"ok": True}), release=(200, {"ok": True}))
    with gate.slot("diffusers", "sd35", 29000, 2) as lease:
        assert lease.upstream_token == "T9"
    assert len(posts.named("acquire")) == 3


def test_a_callers_short_wait_bounds_the_asking_too(gate, monkeypatch):
    monkeypatch.setattr(A, "_UPSTREAM_RETRY_S", 10.0)
    posts = _posts(monkeypatch, acquire=ConnectionError("refused"))
    started = time.time()
    with pytest.raises(A.GpuBusy):
        with gate.slot("llm-load", "q", 5000, 2, timeout_s=0.05):
            pass
    assert time.time() - started < 1.0
    assert posts.named("acquire")


def test_a_devserver_without_gate_routes_leaves_this_gate_the_plants(gate, monkeypatch, caplog):
    posts = _posts(monkeypatch, acquire=(404, {"error": "not found"}))
    with caplog.at_level(logging.WARNING, logger="services.gpu_admission"):
        with gate.slot("diffusers", "sd35", 29000, 2) as lease:
            assert lease.upstream_token == ""
            time.sleep(0.06)
    said = [r.getMessage() for r in caplog.records if "runs on this gate alone" in r.getMessage()]
    assert len(said) == 1 and "HTTP 404" in said[0]
    assert len(posts.calls) == 1               # no heartbeat, no release for a lease never taken


@pytest.mark.parametrize("status,body", [(401, {"error": "settings authentication required"}),
                                         (500, {"error": "the lease could not be taken: boom"}),
                                         (200, {"ok": True})])
def test_an_answer_without_a_token_refuses_the_hold(gate, monkeypatch, status, body):
    _posts(monkeypatch, acquire=(status, body))
    with pytest.raises(A.GpuBusy) as caught:
        with gate.slot("diffusers", "sd35", 29000, 2):
            pass
    e = caught.value
    assert e.reason == "gate_refused"
    assert ("HTTP %d" % status) in str(e) and A.upstream_url() in str(e)
    if status == 401:
        assert "loopback" in str(e)
    assert gate._active is None


def test_a_lease_the_devserver_no_longer_knows_is_said_once(gate, monkeypatch, caplog):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T2"}), heartbeat=(404, {"ok": False}),
                   release=(200, {"ok": False}))
    with caplog.at_level(logging.ERROR, logger="services.gpu_admission"):
        with gate.slot("heartmula", "hm", 11000, 2) as lease:
            time.sleep(0.15)
            assert lease.upstream_token == ""
    gone = [r for r in caplog.records if "is gone" in r.getMessage()]
    assert len(gone) == 1 and "T2" in gone[0].getMessage()
    assert len(posts.named("heartbeat")) == 1  # not asked again for a token that is gone
    assert not posts.named("release")


@pytest.mark.parametrize("trouble", [ConnectionError("reset"), (500, {"error": "boom"}),
                                     (503, {"error": "no thread free"})])
def test_a_heartbeat_that_fails_keeps_the_token_and_asks_again(gate, monkeypatch, caplog, trouble):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T6"}), heartbeat=trouble,
                   release=(200, {"ok": True}))
    with caplog.at_level(logging.WARNING, logger="services.gpu_admission"):
        with gate.slot("diffusers", "sd35", 29000, 2) as lease:
            time.sleep(0.15)
            assert lease.upstream_token == "T6"          # kept: only a 404 ends it
            assert len(posts.named("heartbeat")) >= 3    # asked again every tick
    said = [r.getMessage() for r in caplog.records if "asked again next tick" in r.getMessage()]
    assert len(said) == 1                                 # said once per lease
    assert not [r for r in caplog.records if "is gone" in r.getMessage()]
    assert posts.named("release")[-1][1]["json"]["token"] == "T6"   # and given back at the end


def test_a_heartbeat_that_answers_again_is_noted(gate, monkeypatch, caplog):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T7"}),
                   heartbeat=[ConnectionError("reset"), (200, {"ok": True})],
                   release=(200, {"ok": True}))
    with caplog.at_level(logging.INFO, logger="services.gpu_admission"):
        with gate.slot("diffusers", "sd35", 29000, 2) as lease:
            time.sleep(0.15)
            assert lease.upstream_token == "T7"
    assert [r for r in caplog.records if "answers again" in r.getMessage()]
    assert len(posts.named("heartbeat")) >= 2


def test_a_hold_waiting_for_the_local_slot_is_kept_alive_there_too(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=[(200, {"token": "A"}), (200, {"token": "B"})],
                   heartbeat=(200, {"ok": True}), release=(200, {"ok": True}))
    first_in = threading.Event()
    let_go = threading.Event()

    def _first():
        with gate.slot("diffusers", "sd35", 29000, 2):
            first_in.set()
            let_go.wait(2.0)

    t = threading.Thread(target=_first)
    t.start()
    assert first_in.wait(2.0)
    second_in = threading.Event()

    def _second():
        with gate.slot("heartmula", "hm", 11000, 2):
            second_in.set()

    t2 = threading.Thread(target=_second)
    t2.start()
    time.sleep(0.15)
    beaten = {kw["json"]["token"] for _u, kw in posts.named("heartbeat")}
    assert beaten == {"A", "B"}          # the waiter holds its turn there and is kept alive
    let_go.set()
    t.join(2.0)
    assert second_in.wait(2.0)
    t2.join(2.0)
    released = [kw["json"]["token"] for _u, kw in posts.named("release")]
    assert released == ["A", "B"]


def test_a_body_that_raises_gives_the_turn_back_as_failed(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T3"}), heartbeat=(200, {"ok": True}),
                   release=(200, {"ok": True}))
    with pytest.raises(RuntimeError):
        with gate.slot("diffusers", "sd35", 29000, 2):
            raise RuntimeError("the render broke")
    assert posts.named("release")[-1][1]["json"]["failed"] is True
    assert posts.named("release")[-1][1]["json"]["token"] == "T3"


def test_a_local_wait_that_runs_out_gives_the_turn_back(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=[(200, {"token": "A"}), (200, {"token": "B"})],
                   heartbeat=(200, {"ok": True}), release=(200, {"ok": True}))
    first_in = threading.Event()
    let_go = threading.Event()

    def _first():
        with gate.slot("diffusers", "sd35", 29000, 2):
            first_in.set()
            let_go.wait(2.0)

    t = threading.Thread(target=_first)
    t.start()
    assert first_in.wait(2.0)
    with pytest.raises(A.GpuBusy) as caught:
        with gate.slot("heartmula", "hm", 11000, 2, timeout_s=0.1):
            pass
    assert caught.value.reason == "wait_timeout"
    assert posts.named("release")[-1][1]["json"] == {"token": "B", "failed": True,
                                                     "cleared_comfyui": False}
    let_go.set()
    t.join(2.0)


def test_the_callers_budget_is_one_for_both_waits(gate, monkeypatch):
    seen = {}
    original = gate._wait_for_slot

    def _slow_acquire(url, **kw):
        time.sleep(0.05)
        return types.SimpleNamespace(status_code=200, text="", json=lambda: {"token": "T8"})

    monkeypatch.setattr("requests.post", lambda url, **kw: _slow_acquire(url, **kw)
                        if url.endswith("acquire")
                        else types.SimpleNamespace(status_code=200, text="", json=lambda: {"ok": True}))

    def _wait(lease, timeout_s=None):
        seen["timeout_s"] = timeout_s
        return original(lease, timeout_s)

    monkeypatch.setattr(gate, "_wait_for_slot", _wait)
    with gate.slot("llm-load", "q", 5000, 2, timeout_s=1.0):
        pass
    assert seen["timeout_s"] is not None and seen["timeout_s"] < 1.0
    with gate.slot("llm-load", "q", 5000, 2):
        pass
    assert seen["timeout_s"] is None


def test_a_forced_local_release_gives_the_turn_back(gate, monkeypatch, caplog):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T10"}), heartbeat=(200, {"ok": True}),
                   release=(200, {"ok": True}))
    gate._max_hold_s = 0.05
    with caplog.at_level(logging.ERROR, logger="services.gpu_admission"):
        with gate.slot("diffusers", "sd35", 29000, 2) as lease:
            time.sleep(0.2)
            assert gate._active is None                   # released here after the limit
            assert lease.upstream_token == ""             # ...and there
    releases = posts.named("release")
    assert len(releases) == 1                              # once, not again at the end
    assert releases[0][1]["json"] == {"token": "T10", "failed": True, "cleared_comfyui": False}


def test_a_reaped_remote_lease_gives_the_turn_back(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T11"}), heartbeat=(200, {"ok": True}),
                   release=(200, {"ok": True}))
    gate._heartbeat_timeout_s = 0.05
    token = gate.acquire_remote("comfyui", "sd35", 0, 2, label="r")
    time.sleep(0.2)
    assert gate._active is None and token not in gate._remote_leases
    assert posts.named("release")[-1][1]["json"] == {"token": "T11", "failed": True,
                                                     "cleared_comfyui": False}


def test_a_remote_lease_takes_its_turn_there_too(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T4"}), heartbeat=(200, {"ok": True}),
                   release=(200, {"ok": True}))
    token = gate.acquire_remote("comfyui", "sd35", 0, 2, label="r")
    assert gate._remote_leases[token].upstream_token == "T4"
    assert gate.get_status()["active"]["plant_wide_lease"] is True
    assert gate.release(token) is True
    assert posts.named("release")[-1][1]["json"]["token"] == "T4"


def test_a_comfyui_cleared_during_the_hold_travels_with_the_release(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T12"}), heartbeat=(200, {"ok": True}),
                   release=(200, {"ok": True}))
    with gate.slot("diffusers", "sd35", 29000, 2):
        gate.forget_resident("ComfyUI was asked to free everything")
    assert posts.named("release")[-1][1]["json"]["cleared_comfyui"] is True


def test_on_the_way_out_every_turn_goes_back(gate, monkeypatch, caplog):
    posts = _posts(monkeypatch, acquire=[(200, {"token": "A"}), (200, {"token": "B"})],
                   heartbeat=(200, {"ok": True}), release=(200, {"ok": True}))
    first_in = threading.Event()
    let_go = threading.Event()

    def _first():
        with gate.slot("diffusers", "sd35", 29000, 2):
            first_in.set()
            let_go.wait(2.0)

    t = threading.Thread(target=_first)
    t.start()
    assert first_in.wait(2.0)
    t2 = threading.Thread(target=lambda: gate.slot("heartmula", "hm", 11000, 2).__enter__())
    t2.daemon = True
    t2.start()
    time.sleep(0.1)
    with caplog.at_level(logging.WARNING, logger="services.gpu_admission"):
        gate.release_upstream_leases("signal 15")
    released = sorted(kw["json"]["token"] for _u, kw in posts.named("release"))
    assert released == ["A", "B"]
    assert all("signal 15" in r.getMessage() for r in caplog.records if "Giving" in r.getMessage())
    let_go.set()
    t.join(2.0)


def test_nothing_is_built_on_the_way_out(monkeypatch):
    monkeypatch.setattr(A, "_admission", None)
    A.release_upstream_leases("process exit")      # no singleton, nothing to give back


def test_a_short_wait_travels_along(gate, monkeypatch):
    posts = _posts(monkeypatch, acquire=(200, {"token": "T5"}), heartbeat=(200, {"ok": True}),
                   release=(200, {"ok": True}))
    with gate.slot("llm-load", "qwen", 5000, 2, timeout_s=2.5):
        pass
    assert posts.named("acquire")[0][1]["json"]["timeout_s"] == 2.5


def test_where_the_devserver_answers(monkeypatch):
    monkeypatch.delenv("AI4ARTSED_DEVSERVER_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert A.upstream_url() == "http://127.0.0.1:17802"
    monkeypatch.setenv("PORT", "17801")
    assert A.upstream_url() == "http://127.0.0.1:17801"
    monkeypatch.setenv("AI4ARTSED_DEVSERVER_URL", "http://10.0.0.5:17801/")
    assert A.upstream_url() == "http://10.0.0.5:17801"
