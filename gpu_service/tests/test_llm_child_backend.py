#!/usr/bin/env python3
"""
The llama-server child engine, against a real child process and no GPU.

Everything here spawns tests/fake_llama_server.py through the same supervisor
the service uses. That is the point: the failures this engine exists to survive
are process failures — a child that exits at load, one that never becomes
healthy, one that dies mid-answer, a pipe that fills, a port that is taken, a
socket the reader closes — and none of them can be produced by patching a
function.

No model is ever loaded, no GPU is touched, and no real model identifier appears:
the aliases here are synthetic and are put into MODEL_CONFIGS for the duration
of a test.

Run:
    venv/bin/python -m pytest gpu_service/tests/test_llm_child_backend.py -q
"""

import base64
import contextlib
import json
import logging
import os
import signal
import socket
import struct
import subprocess
import sys
import textwrap
import threading
import time
import types

import pytest

GPU_SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GPU_SERVICE_DIR not in sys.path:
    sys.path.insert(0, GPU_SERVICE_DIR)

import requests  # noqa: E402

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)
# The lines the real build writes, from the fake that plays them back. Read from
# there rather than from the engine's own markers on purpose: a typo in a marker
# has to fail a test, and it cannot if both sides read the same string.
from fake_llama_server import WORK_LINES  # noqa: E402

from services.gpu_admission import GpuBusy  # noqa: E402
from services import llm_child  # noqa: E402
from services.llm_child import (
    CHILD_ENV_MARKER,
    VISION_WARMUP_PX,
    ChildState,
    ChildStartupError,
    ChildStateFile,
    ChildSupervisor,
    build_argv,
    install_shutdown_hooks,
    read_starttime,
    scan_and_kill_orphans,
    unblock_stream,
    warmup_image_data_url,
)
from services.llm_child_backend import (  # noqa: E402
    _coordinator_invalidate_nvml,
    ChildDied,
    ChildRequestError,
    LLMBackend,
    MODEL_CONFIGS,
    ModelLoadRefused,
    data_url_for,
    sniff_image_mime,
)

FAKE_SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "fake_llama_server.py")

TEXT_ALIAS = "fake:1b"
VISION_ALIAS = "fake-vl:1b"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 48
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 48
GIF = b"GIF89a" + b"\x00" * 48
WEBP = b"RIFF" + b"\x2a\x00\x00\x00" + b"WEBP" + b"\x00" * 40
NOT_AN_IMAGE = b"\x01\x02\x03\x04" + b"\x00" * 48


# =============================================================================
# Doubles for everything that would touch the card
# =============================================================================

class FakeCoordinator:
    """The VRAM coordinator, reduced to what this engine asks of it."""

    def __init__(self, granted=True, authoritative=True):
        self.granted = granted
        self.authoritative = authoritative
        self.shortfall = "nothing left to evict"
        self.backends = []
        self.owned = {}
        self.owned_history = []
        self.terminators = {}
        self.requests = []
        self.released = []
        self.invalidated = 0
        # Everything the engine asked of the card, in order, so a test can say
        # what happened BEFORE the next load asked for room.
        self.events = []
        self.free_mb = 40000.0

    def register_backend(self, backend):
        self.backends.append(backend)

    def register_owned(self, pid, starttime, label, confirm=None):
        self.owned[pid] = {"starttime": starttime, "label": label, "confirm": confirm}
        self.owned_history.append(pid)

    def unregister_owned(self, pid, starttime=None):
        # Keyed by PID AND starttime, as the real one is: a corpse withdrawn
        # late must not take out the entry of the child that inherited its
        # number.
        entry = self.owned.get(pid)
        if entry is None:
            return
        if starttime is not None and entry["starttime"] != starttime:
            return
        self.owned.pop(pid, None)

    def invalidate_nvml_cache(self):
        self.invalidated += 1
        self.events.append(("invalidate",))

    def register_owned_terminator(self, key, terminate):
        self.terminators[key] = terminate

    def request_vram_detailed(self, who, mb, priority, hold=False):
        self.requests.append({"who": who, "mb": mb, "hold": hold})
        self.events.append(("request", mb))
        if not self.granted:
            return False, self.shortfall, None
        return True, None, f"token-{len(self.requests)}"

    def release_reservation(self, token):
        self.released.append(token)

    def has_authoritative_reading(self):
        return self.authoritative

    def get_free_vram_mb(self, use_cache=False):
        return self.free_mb

    def get_process_vram_mb(self, pid):
        return None


class StubGate:
    """The admission gate: records the ask, and can answer that the card is busy."""

    def __init__(self):
        self.calls = []
        self.busy = False

    @contextlib.contextmanager
    def slot(self, kind, model_id, required_mb, priority, timeout_s=None,
             label="", workload=""):
        self.calls.append({"kind": kind, "model_id": model_id,
                           "required_mb": required_mb, "timeout_s": timeout_s})
        if self.busy:
            raise GpuBusy("the card is busy")
        lease = types.SimpleNamespace(failed=False)
        yield lease


def free_port_base(count=8):
    """A port range nothing is listening on right now."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def model_config(model_path, mmproj_path=None, n_ctx=4096, n_gpu_layers=-1,
                 estimated_vram_mb=1500):
    config = {
        "model_path": str(model_path),
        "n_ctx": n_ctx,
        "n_gpu_layers": n_gpu_layers,
        "estimated_vram_mb": estimated_vram_mb,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Fake text model",
        "approx_download_mb": 10,
    }
    if mmproj_path:
        config.update({
            "mmproj_path": str(mmproj_path),
            "chat_capable": False,
            "vlm_capable": True,
            "display_name": "Fake vision model",
        })
    return config


class Sandbox:
    """One engine, one temp state directory, one fake binary."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.model = tmp_path / "weights.gguf"
        self.model.write_bytes(b"GGUF" + b"\x00" * 32)
        self.mmproj = tmp_path / "projector.gguf"
        self.mmproj.write_bytes(b"GGUF" + b"\x00" * 32)
        self.state_dir = tmp_path / "state"
        self.state_dir.mkdir()
        self.coordinator = FakeCoordinator()
        self.gate = StubGate()
        # What the card really holds, and what a CACHED read still shows. The
        # coordinator serves an enumeration up to a second old, so a test can
        # leave a stale figure standing and see who reads it.
        self.nvml = {}
        self.nvml_cached = {}
        # How often a PID's figure was actually read, so a test can tell a wait
        # that happened from one that was skipped.
        self.nvml_reads = {}
        # A test that needs the figure to MOVE — the card growing under an
        # encoder that has just been fed — puts a callable here instead.
        self.nvml_hook = None
        self._made = []

        MODEL_CONFIGS[TEXT_ALIAS] = model_config(self.model)
        MODEL_CONFIGS[VISION_ALIAS] = model_config(self.model, self.mmproj)

        monkeypatch.setattr("services.gpu_admission.get_gpu_admission",
                            lambda: self.gate)
        monkeypatch.setattr("services.vram_coordinator.get_vram_coordinator",
                            lambda: self.coordinator)

    def env(self, **values):
        for key, value in values.items():
            self.monkeypatch.setenv(key, str(value))

    def nvml_pid_mb(self, pid, max_age_s=None):
        self.nvml_reads[pid] = self.nvml_reads.get(pid, 0) + 1
        if self.nvml_hook is not None:
            return self.nvml_hook(pid, max_age_s)
        if max_age_s == 0.0:
            return self.nvml.get(pid)
        return self.nvml_cached.get(pid, self.nvml.get(pid))

    def supervisor(self, stall_s=1.0, start_reaper=False, port_count=8,
                   binary=None, run_orphan_scan=False, load_ceiling_s=900.0,
                   warmup_stall_s=60.0):
        return ChildSupervisor(
            binary=binary or FAKE_SERVER,
            port_base=free_port_base(),
            port_count=port_count,
            socket_timeout_s=2592000,
            stall_s=stall_s,
            load_ceiling_s=load_ceiling_s,
            warmup_stall_s=warmup_stall_s,
            state_dir=str(self.state_dir),
            nvml_pid_mb=self.nvml_pid_mb,
            # Through the production wrapper, not straight at the fake: the
            # wrapper swallows every exception, so a rename of the coordinator
            # method would go unnoticed forever while a test wired directly to
            # it stayed green. get_vram_coordinator is monkeypatched above, so
            # this still ends at the fake.
            nvml_invalidate=_coordinator_invalidate_nvml,
            reaper_interval_s=0.1,
            run_orphan_scan=run_orphan_scan,
            start_reaper=start_reaper,
        )

    def backend(self, **kwargs):
        supervisor = kwargs.pop("supervisor", None) or self.supervisor(**kwargs)
        backend = LLMBackend(supervisor=supervisor, coordinator=self.coordinator)
        self._made.append(backend)
        return backend

    def close(self):
        for backend in self._made:
            with contextlib.suppress(Exception):
                backend.terminate_all("test teardown")
        MODEL_CONFIGS.pop(TEXT_ALIAS, None)
        MODEL_CONFIGS.pop(VISION_ALIAS, None)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    box = Sandbox(tmp_path, monkeypatch)
    box.env(FAKE_LLAMA_MODE="ready", FAKE_LLAMA_HEALTH_DELAY_S="0")
    try:
        yield box
    finally:
        box.close()


def child_of(backend, alias=TEXT_ALIAS):
    return backend._supervisor.get(alias)


def fake_get(child, path, **kwargs):
    return requests.get(child.base_url() + path, timeout=5, **kwargs).json()


def control(child, **values):
    """Change what a RUNNING child does. Its environment was fixed at spawn."""
    query = "&".join(f"{k}={v}" for k, v in values.items())
    return requests.get(child.base_url() + "/control?" + query, timeout=5).json()


def state_pids(backend):
    """The PIDs the state file names right now."""
    return [entry["pid"] for entry in backend._supervisor.state_file.read()]


def ended_unreaped(pid):
    """True once the process has ended and is collectible — WITHOUT collecting it.

    wait() here would do the engine's work for it: a collected child answers
    poll() with its exit code straight away, and the check under test — a
    request meeting a corpse nobody has collected yet — would never happen.
    WNOWAIT reports the end and leaves the status where it is, for the engine
    to find.

    Reading the state out of /proc instead would be wrong twice over: the
    thread-group leader of a multithreaded child shows "Z" while the other
    threads are still being torn down, and in that window waitpid() answers
    "not yet" — measured here, and it made this look like a defect in the
    engine when it was only a test that declared the death too early.
    """
    try:
        return os.waitid(os.P_PID, pid,
                         os.WEXITED | os.WNOWAIT | os.WNOHANG) is not None
    except ChildProcessError:
        return True                                   # already collected
    except OSError:
        return True


def wait_until(predicate, timeout=5.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


# =============================================================================
# The spawn line
# =============================================================================

def test_argv_carries_every_flag(tmp_path):
    config = model_config(tmp_path / "w.gguf", tmp_path / "p.gguf", n_ctx=16384)
    argv = build_argv(config, 17810, "fake:1b", "/opt/llama-server", 2592000,
                      fit_target_mb=22528)
    assert argv == [
        "/opt/llama-server",
        "-m", str(tmp_path / "w.gguf"),
        "--mmproj", str(tmp_path / "p.gguf"),
        # No -c: llama.cpp reads the window out of the model, which is the only
        # place it is a property of the weights and not of a table.
        # Explicit BECAUSE it is the default: llama.cpp fills every absent flag
        # from LLAMA_ARG_*, so an environment variable could otherwise cap every
        # answer the platform produces.
        "-n", "-1",
        "-ngl", "all",
        "-np", "1",
        "--slots",
        "-b", "512",
        "-ub", "512",
        # The cache is sized to the card, down to --fit-ctx at the least,
        # instead of the whole window being reserved at load.
        "--fit", "on",
        "--fit-target", "22528",
        "--no-context-shift",
        "--jinja",
        "--reasoning-format", "none",
        # The switch, and the budget. `--reasoning` is what turns thinking on
        # (enable_reasoning = 1 plus the template default enable_thinking =
        # "true"); `--reasoning-budget` only sizes it, and is written out at its
        # own default so LLAMA_ARG_THINK_BUDGET cannot end every thought at its
        # first token.
        "--reasoning", "on",
        "--reasoning-budget", "-1",
        "-cram", "0",
        "--no-webui",
        "--host", "127.0.0.1",
        "--port", "17810",
        "--alias", "fake:1b",
        "-to", "2592000",
    ]


def test_argv_without_a_projector_passes_no_mmproj(tmp_path):
    argv = build_argv(model_config(tmp_path / "w.gguf", n_ctx=4096), 17811,
                      "fake:1b", "/opt/llama-server", 600)
    assert "--mmproj" not in argv
    # A window typed into the config reaches no spawn line any more.
    assert "-c" not in argv
    assert argv[argv.index("--fit") + 1] == "on"
    # Without a margin from the caller, llama.cpp keeps its own default.
    assert "--fit-target" not in argv
    assert argv[argv.index("-to") + 1] == "600"


def test_argv_passes_a_layer_count_through(tmp_path):
    argv = build_argv(model_config(tmp_path / "w.gguf", n_gpu_layers=24), 17812,
                      "fake:1b", "/opt/llama-server", 600)
    assert argv[argv.index("-ngl") + 1] == "24"


# =============================================================================
# Readiness, refusal, the ledger
# =============================================================================

def test_a_child_becomes_ready_and_is_registered_as_ours(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)

    child = child_of(backend)
    assert child.state is ChildState.READY
    assert child.pid and child.starttime
    assert fake_get(child, "/health")["status"] == "ok"

    # Announced to the coordinator the moment it was spawned, so the load window
    # is never counted as foreign VRAM.
    assert child.pid in sandbox.coordinator.owned
    assert sandbox.coordinator.owned[child.pid]["starttime"] == child.starttime
    assert sandbox.coordinator.owned[child.pid]["confirm"]() is True

    # The room was asked for and given back once the child was up.
    assert sandbox.coordinator.requests[0]["hold"] is True
    assert sandbox.coordinator.released == ["token-1"]

    loaded = backend.get_loaded_models()[0]
    assert loaded["id"] == TEXT_ALIAS
    assert loaded["pid"] == child.pid
    assert loaded["port"] == child.port
    assert loaded["state"] == "ready"


def test_the_load_takes_the_slot_briefly_and_gives_it_up_when_busy(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    assert sandbox.coordinator.requests
    call = sandbox.gate.calls[0]
    assert call["kind"] == "llm-load"
    assert call["model_id"] == TEXT_ALIAS
    assert call["timeout_s"] == 5.0

    # A busy card must not stop a content check: the load goes ahead unslotted.
    backend.unload(TEXT_ALIAS)
    sandbox.gate.busy = True
    backend._load(TEXT_ALIAS)
    assert child_of(backend).state is ChildState.READY


def test_health_delay_is_waited_out(sandbox):
    sandbox.env(FAKE_LLAMA_HEALTH_DELAY_S="1.0")
    backend = sandbox.backend(stall_s=30.0)
    started = time.monotonic()
    backend._load(TEXT_ALIAS)
    assert time.monotonic() - started >= 0.9
    assert child_of(backend).state is ChildState.READY


def test_a_child_that_exits_at_load_is_refused_with_its_exit_code(sandbox):
    sandbox.env(FAKE_LLAMA_MODE="exit", FAKE_LLAMA_EXIT_CODE="7")
    backend = sandbox.backend()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(TEXT_ALIAS)
    message = str(refused.value)
    assert "exit 7" in message
    assert "unknown model architecture" in message  # its own last lines travel
    assert child_of(backend) is None
    assert sandbox.coordinator.released == ["token-1"]


def test_a_child_that_never_becomes_ready_and_says_nothing_is_refused(sandbox):
    sandbox.env(FAKE_LLAMA_MODE="never_silent")
    backend = sandbox.backend(stall_s=1.0)
    started = time.monotonic()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(TEXT_ALIAS)
    assert "wrote nothing, read nothing off disk and moved no GPU memory" in str(
        refused.value)
    # The bound is a bound: it ends the load, and it does so in its own time.
    assert 1.0 <= time.monotonic() - started < 15.0
    assert child_of(backend) is None


def test_a_child_that_keeps_writing_is_given_time(sandbox):
    """Progress is progress: silence AND a still card AND no disk reads stall.

    Bounded by the ceiling rather than by the clock of this test — the child
    writes a line every 200 ms forever, so what is asserted is that the stall
    bound stays out of its way for many times its own length.
    """
    sandbox.env(FAKE_LLAMA_MODE="never_chatty")
    backend = sandbox.backend(stall_s=0.5, load_ceiling_s=900.0)
    outcome = []

    def _load():
        try:
            backend._load(TEXT_ALIAS)
            outcome.append("ready")
        except BaseException as e:  # noqa: BLE001
            outcome.append(e)

    worker = threading.Thread(target=_load, daemon=True)
    worker.start()
    worker.join(timeout=4.0)
    assert worker.is_alive(), f"the load ended after 4s of visible progress: {outcome}"

    child = child_of(backend)
    backend.unload(TEXT_ALIAS, force=True)
    worker.join(timeout=10.0)
    assert not child.is_alive()


def test_a_chatty_child_that_never_becomes_healthy_hits_the_ceiling(sandbox):
    """The ceiling is what ends a load that shows progress and never arrives.

    Without it such a child holds the plant-wide load lock for as long as it
    keeps writing — and with the lock, every content check on the platform.
    """
    sandbox.env(FAKE_LLAMA_MODE="never_chatty")
    backend = sandbox.backend(stall_s=30.0, load_ceiling_s=1.5)
    started = time.monotonic()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(TEXT_ALIAS)
    took = time.monotonic() - started

    message = str(refused.value)
    assert "1s" in message or "2s" in message, message   # the ceiling, named
    assert "30s" in message, "the stall bound is named too, so both are visible"
    assert 1.5 <= took < 20.0
    assert child_of(backend) is None


def test_the_load_lock_lets_the_second_alias_through_afterwards(sandbox):
    """One load at a time across all aliases — and the queue does move on."""
    sandbox.env(FAKE_LLAMA_HEALTH_DELAY_S="1.0")
    backend = sandbox.backend(stall_s=30.0)
    order = []

    def _load(alias):
        backend._load(alias)
        order.append(alias)

    first = threading.Thread(target=_load, args=(TEXT_ALIAS,), daemon=True)
    first.start()
    time.sleep(0.2)                      # the first one holds the lock now
    second = threading.Thread(target=_load, args=(VISION_ALIAS,), daemon=True)
    second.start()

    first.join(timeout=20.0)
    second.join(timeout=20.0)
    assert order == [TEXT_ALIAS, VISION_ALIAS]
    assert child_of(backend, TEXT_ALIAS).state is ChildState.READY
    assert child_of(backend, VISION_ALIAS).state is ChildState.READY


def test_the_nvml_figure_alone_also_counts_as_progress(sandbox):
    """A silent child that is filling the card is loading, and is left alone.

    The stall bound is set to more than one NVML polling interval on purpose:
    the card is read once a second while the cheap signals are read four times
    a second, and a bound shorter than that interval would be deciding between
    two readings rather than between two states.
    """
    sandbox.env(FAKE_LLAMA_MODE="never_silent")
    backend = sandbox.backend(stall_s=2.5)
    outcome = []
    stop = threading.Event()

    def _grow():
        mb = 0.0
        while not stop.wait(0.2):
            mb += 500.0
            child = child_of(backend)
            if child is not None and child.pid:
                sandbox.nvml[child.pid] = mb

    def _load():
        try:
            backend._load(TEXT_ALIAS)
            outcome.append("ready")
        except BaseException as e:  # noqa: BLE001
            outcome.append(e)

    grower = threading.Thread(target=_grow, daemon=True)
    grower.start()
    worker = threading.Thread(target=_load, daemon=True)
    worker.start()
    worker.join(timeout=4.0)
    stop.set()
    assert worker.is_alive(), f"a child that is filling the card was refused: {outcome}"

    child = child_of(backend)
    backend.unload(TEXT_ALIAS, force=True)
    worker.join(timeout=10.0)
    assert not child.is_alive()


def test_more_than_a_pipe_holds_does_not_wedge_the_load(sandbox):
    """A pipe nobody drains fills at 64 KB, and a blocked child looks stalled."""
    sandbox.env(FAKE_LLAMA_MODE="noisy")
    backend = sandbox.backend(stall_s=5.0)
    backend._load(TEXT_ALIAS)
    assert child_of(backend).state is ChildState.READY


def test_a_taken_port_is_tried_once_more(sandbox):
    supervisor = sandbox.supervisor(stall_s=5.0)
    doomed = supervisor._free_port()
    sandbox.env(FAKE_LLAMA_BIND_FAIL_PORT=doomed)
    backend = sandbox.backend(supervisor=supervisor)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    assert child.state is ChildState.READY
    assert child.port != doomed


def test_a_shortfall_the_sensor_measured_refuses_the_load(sandbox):
    sandbox.coordinator.granted = False
    sandbox.coordinator.authoritative = True
    backend = sandbox.backend()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(TEXT_ALIAS)
    assert "VRAM shortfall" in str(refused.value)
    assert "nothing left to evict" in str(refused.value)
    assert child_of(backend) is None


def test_a_shortfall_nothing_could_measure_does_not_stop_the_checks(sandbox, monkeypatch):
    sandbox.coordinator.granted = False
    sandbox.coordinator.authoritative = False
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False)))
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    assert child_of(backend).state is ChildState.READY



# =============================================================================
# The load-time vision warm-up
# =============================================================================
#
# What the child was admitted on is the compute buffer llama.cpp RESERVES at
# load. What it allocates when it is first fed an image is another 488-686 MB on
# this card, and until this warm-up existed that happened on a reader's request,
# outside anybody's reservation, with the failure llama.cpp does not report.


def image_mark(sandbox, tmp_path):
    """Let the fake say when an image reached it, and grow the card when it has.

    The NVML figure moves by 600 MB from the moment the encoder has been fed,
    which is what a real card does and what the load line is supposed to report.
    """
    mark = tmp_path / "image-was-encoded"
    sandbox.env(FAKE_LLAMA_IMAGE_MARK=str(mark))

    def reading(pid, max_age_s=None):
        # Nothing for a process that is gone, as the card reports it: a figure
        # that outlives the PID would hold every teardown at the bound that
        # waits for the memory to come back.
        if not os.path.exists("/proc/%d" % pid):
            return None
        return 1600.0 if mark.exists() else 1000.0

    sandbox.nvml_hook = reading
    return mark


def test_a_vision_load_feeds_the_encoder_one_image_at_the_token_cap(sandbox, tmp_path):
    mark = image_mark(sandbox, tmp_path)
    backend = sandbox.backend()
    backend._load(VISION_ALIAS)
    child = child_of(backend, VISION_ALIAS)

    assert mark.exists(), "no image reached the child during the load"
    body = fake_get(child, "/last-request")["body"]
    parts = body["messages"][0]["content"]
    url = next(part["image_url"]["url"] for part in parts
               if part["type"] == "image_url")
    png = base64.b64decode(url.split(",", 1)[1])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR carries the size, and the size is the point: below 2048 the encoder
    # asks for less than it will ask for later, and the buffer this load is
    # holding room for is not the one the first reader's image will build.
    # The literal, not the constant: a test that reads the same figure the code
    # does would go on passing if somebody halved it, and half of it is below
    # the cap the measurement established.
    assert struct.unpack(">II", png[16:24]) == (2048, 2048)
    assert VISION_WARMUP_PX == 2048
    # Nothing was capped on the way out.
    assert "max_tokens" not in body and "n_predict" not in body


def test_the_load_line_carries_what_the_encoder_took(sandbox, tmp_path, caplog):
    image_mark(sandbox, tmp_path)
    backend = sandbox.backend()
    with caplog.at_level(logging.INFO):
        backend._load(VISION_ALIAS)
    line = next(record.message for record in caplog.records
                if "is ready on port" in record.message)
    assert "image encoder warmed at 2048x2048" in line
    assert "1000MB -> 1600MB (+600MB)" in line


def test_the_encoder_is_fed_before_the_room_is_given_back(sandbox, tmp_path):
    """The reservation is the whole reason this happens at load time."""
    mark = image_mark(sandbox, tmp_path)
    held = []
    original = sandbox.coordinator.release_reservation

    def release(token):
        held.append(mark.exists())
        return original(token)

    sandbox.coordinator.release_reservation = release
    backend = sandbox.backend()
    backend._load(VISION_ALIAS)
    assert held and all(held), "the room was released before the image arrived"


def test_the_child_is_booked_at_its_grown_figure(sandbox, tmp_path):
    """A child booked at its pre-warm-up size is one an eviction underrates.

    `vram_mb` is what the coordinator is told this child holds, and after the
    warm-up that is several hundred megabytes more than at readiness.
    """
    image_mark(sandbox, tmp_path)
    backend = sandbox.backend()
    backend._load(VISION_ALIAS)
    child = child_of(backend, VISION_ALIAS)
    assert child.vram_mb == 1600.0
    assert child.alias in {entry["alias"] for entry
                           in backend._supervisor.state_file.read()}


def test_a_text_child_is_never_handed_an_image(sandbox, tmp_path):
    mark = image_mark(sandbox, tmp_path)
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend, TEXT_ALIAS)
    assert not mark.exists()
    assert fake_get(child, "/stats")["images"] == 0


def test_a_child_that_dies_on_the_warm_up_image_is_refused(sandbox):
    """The crash happens here, under the load, instead of on a reader's image."""
    sandbox.env(FAKE_LLAMA_CHAT="die_at_once")
    backend = sandbox.backend()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(VISION_ALIAS)
    assert "warm-up image" in str(refused.value)
    assert backend._supervisor.get(VISION_ALIAS) is None
    assert wait_until(lambda: not sandbox.coordinator.owned), \
        "a child that never came up is still registered on the card"


def test_a_warm_up_that_fails_twice_refuses_the_load(sandbox):
    """FAIL CLOSED, and this is the whole reason the warm-up exists.

    Every rail in front of the load held here — the card was readable, the room
    was granted, the compute-buffer line is in the log — and not one of them
    covers what is missing: the encoder's own buffers, which llama.cpp
    allocates on the first image and does not report the failure of. A child
    admitted without them is booked at a figure that leaves them out, and the
    first reader's image asks the card for them against nobody's reservation.
    """
    sandbox.env(FAKE_LLAMA_STATUS="500")
    backend = sandbox.backend()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(VISION_ALIAS)
    assert "warm-up image" in str(refused.value)
    assert "the child answered 500" in str(refused.value)
    assert backend._supervisor.get(VISION_ALIAS) is None
    # The room is given back: _load_gated releases in its finally, whatever the
    # load did. A refusal that kept the reservation would take the card with it.
    assert sandbox.coordinator.released, "the reservation was never released"
    assert wait_until(lambda: not sandbox.coordinator.owned), \
        "a child that was refused is still registered on the card"


def test_a_warm_up_that_fails_once_is_asked_again(sandbox, tmp_path, caplog):
    """A single failed request may not cost the alias — the room is still held.

    The retry happens inside the load, so it happens under the reservation the
    coordinator granted for it. That is the difference between asking again and
    leaving it to the first reader.
    """
    image_mark(sandbox, tmp_path)
    sandbox.env(FAKE_LLAMA_CHAT_FAIL_FIRST="1")
    backend = sandbox.backend()
    with caplog.at_level(logging.INFO):
        backend._load(VISION_ALIAS)
    child = child_of(backend, VISION_ALIAS)

    assert child.state is ChildState.READY
    assert "asking once more" in caplog.text
    # The figure the coordinator is given is the one AFTER the encoder built
    # its buffers, on the attempt that got through.
    assert child.vram_mb == 1600.0
    line = next(record.message for record in caplog.records
                if "is ready on port" in record.message)
    assert "1000MB -> 1600MB (+600MB)" in line
    assert fake_get(child, "/stats")["chat_failures"] == 1
    assert fake_get(child, "/stats")["images"] == 1


def test_the_warm_up_carries_a_bound_of_its_own(sandbox):
    """Because it holds the plant-wide load lock while it waits.

    The reaper's clock would end this child too, but only after the bound every
    ordinary generation gets — and every other load on the platform stands
    behind this one meanwhile. The reaper is off in this test, so what ends it
    can only be the warm-up's own bound.
    """
    sandbox.env(FAKE_LLAMA_CHAT="wedge")
    backend = sandbox.backend(stall_s=600.0, start_reaper=False,
                              warmup_stall_s=1.0)
    outcome = {}

    # In a thread with a bound around the JOIN, never inline: a bound that stops
    # working stops this test too, and a test that hangs says nothing to
    # anybody. It hung here once — the bound reached its branch and deadlocked
    # closing the stream from this side (see unblock_stream).
    def load():
        try:
            backend._load(VISION_ALIAS)
            outcome["end"] = "admitted"
        except BaseException as e:  # noqa: BLE001
            outcome["end"] = e

    started = time.monotonic()
    worker = threading.Thread(target=load, daemon=True)
    worker.start()
    worker.join(30.0)
    took = time.monotonic() - started

    assert not worker.is_alive(), f"the bound did not act ({took:.0f}s)"
    assert isinstance(outcome["end"], ModelLoadRefused), outcome["end"]
    assert "stopped working while encoding the warm-up" in str(outcome["end"])
    assert "load lock" in str(outcome["end"])
    assert took < 30.0, f"the bound did not act ({took:.0f}s)"
    assert backend._supervisor.get(VISION_ALIAS) is None
    assert wait_until(lambda: not sandbox.coordinator.owned)


def test_a_blocked_reader_is_let_go_of_without_waiting_for_it():
    """unblock_stream shuts the socket down and never closes from outside.

    The distinction is the whole point: `close()` takes the reader's buffer lock
    and waits for a read that is not coming back, which is how the warm-up's
    bound came to hang inside its own escape hatch.
    """
    class Raw:
        def __init__(self):
            self.did = []

        def shutdown(self):
            self.did.append("shutdown")

        def close(self):
            self.did.append("close")

    class Response:
        def __init__(self, raw):
            self.raw = raw
            self.closed = False

        def close(self):
            self.closed = True

    raw = Raw()
    response = Response(raw)
    unblock_stream(response)
    assert raw.did == ["shutdown"]
    assert not response.closed

    # An older urllib3 without shutdown(): nothing happens, and nothing hangs.
    class Old:
        def close(self):
            raise AssertionError("close() must never be called from outside")

    unblock_stream(Response(Old()))
    unblock_stream(object())


def test_the_warm_up_is_covered_by_the_clock_that_ends_a_wedged_child(sandbox):
    """No read timeout ends this, by rule. The child-level bound does.

    A child that accepts the image and then does nothing at all is the failure
    the warm-up is most likely to meet, and it must not be able to hold the load
    — and with it the plant-wide load lock — for ever.

    The load runs in a thread with a bound around the JOIN, not around the
    request: nothing in the load path may carry a read timeout, so an engine
    that lost the clock would hang here, and a test that hangs with it says
    nothing to anybody.
    """
    sandbox.env(FAKE_LLAMA_CHAT="wedge")
    # The warm-up's own bound is far away here, so what ends this child is the
    # reaper — the clock that covers a child holding a request, whatever the
    # request is.
    backend = sandbox.backend(stall_s=1.0, start_reaper=True, warmup_stall_s=600.0)
    outcome = {}

    def load():
        try:
            backend._load(VISION_ALIAS)
            outcome["end"] = "admitted"
        except BaseException as e:  # noqa: BLE001
            outcome["end"] = e

    worker = threading.Thread(target=load, daemon=True)
    worker.start()
    worker.join(30.0)
    assert not worker.is_alive(), "the wedged warm-up was never ended"
    assert isinstance(outcome["end"], ModelLoadRefused), outcome["end"]
    assert "no progress" in str(outcome["end"]) or "warm-up image" in str(outcome["end"])
    assert backend._supervisor.get(VISION_ALIAS) is None


def test_the_warm_up_image_is_built_once_and_is_a_real_png(tmp_path):
    """No asset on disk: an install cannot be missing what is computed."""
    first = warmup_image_data_url()
    assert warmup_image_data_url() is first
    png = base64.b64decode(first.split(",", 1)[1])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (VISION_WARMUP_PX, VISION_WARMUP_PX)
    # Small enough that a load pays nothing for it.
    assert len(png) < 200_000


# =============================================================================
# The vision fail-closed check
# =============================================================================

def test_a_vision_child_that_never_reserved_its_buffer_is_refused(sandbox):
    sandbox.env(FAKE_LLAMA_NO_VISION_LINE="1")
    backend = sandbox.backend()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(VISION_ALIAS)
    assert "compute buffer" in str(refused.value)
    assert backend._supervisor.get(VISION_ALIAS) is None


def test_a_vision_child_that_logged_its_buffer_is_admitted(sandbox):
    backend = sandbox.backend()
    backend._load(VISION_ALIAS)
    child = backend._supervisor.get(VISION_ALIAS)
    assert child.state is ChildState.READY
    assert fake_get(child, "/props")["modalities"]["vision"] is True
    # The vision surcharge is asked for on top of the weights.
    assert sandbox.coordinator.requests[0]["mb"] == 1500 + 1024


def test_a_text_child_is_not_asked_for_the_vision_surcharge(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    assert sandbox.coordinator.requests[0]["mb"] == 1500


def test_the_compute_buffer_line_is_given_a_moment_to_arrive(sandbox):
    """/health answers before the projector is built. Two seconds of grace."""
    sandbox.env(FAKE_LLAMA_VISION_LINE_DELAY_S="0.8")
    backend = sandbox.backend(stall_s=30.0)
    backend._load(VISION_ALIAS)
    child = backend._supervisor.get(VISION_ALIAS)
    assert child.state is ChildState.READY
    assert child._saw_vision_buffer is True


@pytest.mark.parametrize("blindness", ["no coordinator", "no sensor", "request raised"])
def test_a_vision_load_is_refused_wherever_the_card_cannot_be_read(sandbox, blindness):
    """The three rails the in-process engine had, unchanged.

    The compute-buffer line in the child's log is an ADDITIONAL guard, not a
    replacement: it fires after 9 GB have already gone onto the card, and only
    for the encoder. These three refuse before anything is spawned.
    """
    if blindness == "no coordinator":
        backend = sandbox.backend()
        backend._coordinator = None
        sandbox.monkeypatch.setattr("services.vram_coordinator.get_vram_coordinator",
                                    lambda: (_ for _ in ()).throw(RuntimeError("gone")))
    elif blindness == "no sensor":
        sandbox.coordinator.authoritative = False
        backend = sandbox.backend()
    else:
        def _raises(*args, **kwargs):
            raise RuntimeError("the coordinator itself failed")
        sandbox.coordinator.request_vram_detailed = _raises
        backend = sandbox.backend()

    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(VISION_ALIAS)
    assert "image encoder" in str(refused.value)
    assert backend._supervisor.get(VISION_ALIAS) is None


@pytest.mark.parametrize("blindness", ["no coordinator", "no sensor", "request raised"])
def test_a_text_load_goes_ahead_where_a_vision_load_is_refused(sandbox, blindness):
    """The rails are about the image encoder. Text checks must keep running."""
    if blindness == "no coordinator":
        backend = sandbox.backend()
        backend._coordinator = None
        sandbox.monkeypatch.setattr("services.vram_coordinator.get_vram_coordinator",
                                    lambda: (_ for _ in ()).throw(RuntimeError("gone")))
    elif blindness == "no sensor":
        sandbox.coordinator.authoritative = False
        backend = sandbox.backend()
    else:
        def _raises(*args, **kwargs):
            raise RuntimeError("the coordinator itself failed")
        sandbox.coordinator.request_vram_detailed = _raises
        backend = sandbox.backend()

    backend._load(TEXT_ALIAS)
    assert child_of(backend).state is ChildState.READY


def test_a_vision_shortfall_is_refused_even_with_no_sensor_left(sandbox, monkeypatch):
    """The text path may proceed on an unmeasurable card; the image path never."""
    sandbox.coordinator.granted = False
    sandbox.coordinator.authoritative = True   # gets past the sensor rail
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False)))
    backend = sandbox.backend()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(VISION_ALIAS)
    assert "VRAM shortfall" in str(refused.value)


# =============================================================================
# What goes on the wire
# =============================================================================

def test_the_child_inherits_no_llama_arg_environment(sandbox):
    """Every flag absent from the command line is filled from LLAMA_ARG_*.

    A value in this service's environment would reach into the child's context
    size, its sampling or its authentication without appearing in the spawn line
    anybody reads. It is stripped; our own marker is what stays.
    """
    sandbox.env(LLAMA_ARG_N_PREDICT="16", LLAMA_ARG_CTX_SIZE="256",
                LLAMA_API_KEY="a-secret", LLAMA_UNRELATED="kept")
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    with open(f"/proc/{child.pid}/environ", "rb") as handle:
        entries = handle.read().split(b"\0")
    names = {e.split(b"=", 1)[0].decode() for e in entries if b"=" in e}

    assert not [n for n in names if n.startswith("LLAMA_ARG_")]
    assert "LLAMA_API_KEY" not in names
    assert "LLAMA_UNRELATED" in names, "only llama.cpp's own reach is cut"
    assert CHILD_ENV_MARKER in names


def test_no_cap_travels_unless_the_caller_gave_one(sandbox):
    backend = sandbox.backend()
    backend.chat(TEXT_ALIAS, [{"role": "user", "content": "hello"}])
    body = fake_get(child_of(backend), "/last-request")["body"]
    assert "max_tokens" not in body
    assert body["repeat_penalty"] == 1.0
    assert body["stream"] is True
    assert "cache_prompt" not in body

    backend.chat(TEXT_ALIAS, [{"role": "user", "content": "hello"}],
                 max_tokens=64, repetition_penalty=1.15)
    body = fake_get(child_of(backend), "/last-request")["body"]
    assert body["max_tokens"] == 64
    assert body["repeat_penalty"] == 1.15


def test_generate_passes_n_predict_only_when_asked(sandbox):
    backend = sandbox.backend()
    backend.generate(TEXT_ALIAS, "a prompt")
    last = fake_get(child_of(backend), "/last-request")
    assert last["path"] == "/completion"
    assert "n_predict" not in last["body"]
    assert last["body"]["repeat_penalty"] == 1.0

    backend.generate(TEXT_ALIAS, "a prompt", max_tokens=32)
    assert fake_get(child_of(backend), "/last-request")["body"]["n_predict"] == 32


def test_images_switch_off_prefix_reuse_and_carry_their_own_mime(sandbox):
    backend = sandbox.backend()
    payload = base64.b64encode(PNG).decode("ascii")
    backend.chat(VISION_ALIAS, [{"role": "user", "content": "what is this"}],
                 images=[payload])
    body = fake_get(backend._supervisor.get(VISION_ALIAS), "/last-request")["body"]
    assert body["cache_prompt"] is False
    parts = body["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "what is this"}
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize("raw,expected", [
    (JPEG, "image/jpeg"),
    (PNG, "image/png"),
    (GIF, "image/gif"),
    (WEBP, "image/webp"),
])
def test_the_mime_comes_from_the_bytes(raw, expected):
    assert sniff_image_mime(raw) == expected
    assert data_url_for(base64.b64encode(raw).decode("ascii")).startswith(
        f"data:{expected};base64,")


def test_bytes_that_match_nothing_go_as_jpeg(caplog):
    assert sniff_image_mime(NOT_AN_IMAGE) is None
    with caplog.at_level(logging.WARNING):
        url = data_url_for(base64.b64encode(NOT_AN_IMAGE).decode("ascii"))
    assert url.startswith("data:image/jpeg;base64,")
    assert any("no known signature" in record.message for record in caplog.records)


def test_a_data_url_is_left_alone():
    assert data_url_for("data:image/webp;base64,AAAA") == "data:image/webp;base64,AAAA"


# =============================================================================
# What comes back
# =============================================================================

def test_a_plain_answer_arrives_whole(sandbox):
    """The real shape: a role chunk with null content, then text, then timings."""
    backend = sandbox.backend()
    result = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "hello"}])
    assert result["content"] == "Hello world"
    assert result["finish_reason"] == "stop"
    assert result["thinking"] is None


def test_an_ordinary_request_is_no_disconnect_for_the_child(sandbox):
    """Read to [DONE], so a finished answer never looks like a cancellation.

    Dropping the connection on the finish chunk makes the child log a cancelled
    slot for every ordinary request — and that log line is what tells a
    repetition stop from a normal end.
    """
    backend = sandbox.backend()
    backend.chat(TEXT_ALIAS, [{"role": "user", "content": "hello"}])
    child = child_of(backend)
    assert fake_get(child, "/stats")["disconnects"] == 0
    assert fake_get(child, "/slots")[0]["is_processing"] is False

    backend.generate(TEXT_ALIAS, "x")
    assert fake_get(child, "/stats")["disconnects"] == 0


def test_thoughts_are_split_off_at_the_closing_tag(sandbox):
    """--reasoning-format none leaves the thoughts in content, as before."""
    sandbox.env(FAKE_LLAMA_CHAT="thinking")
    backend = sandbox.backend()
    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["thinking"] == "weighing it up"
    assert answer["content"] == "the answer"

    # The pieces themselves are handed out unsplit; only chat() partitions.
    seen = [v for kind, v in backend.chat_stream(
        TEXT_ALIAS, [{"role": "user", "content": "x"}]) if kind == "token"]
    assert seen == ["weighing it up", "</think>", "the answer"]


def test_empty_choices_are_skipped(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="empty_choices")
    backend = sandbox.backend()
    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])["content"] == "Hello"


def test_content_and_finish_reason_in_one_chunk(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="finish_with_content")
    backend = sandbox.backend()
    seen = list(backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]))
    assert seen == [("token", "Hello"), ("token", " world"), ("finish", "stop")]


def test_done_may_be_absent(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="no_done")
    backend = sandbox.backend()
    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])["content"] == "Hello world"


def test_the_context_ceiling_is_reported_as_length(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="length")
    backend = sandbox.backend()
    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])["finish_reason"] == "length"


def test_tool_calls_end_the_answer_as_stop(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="tool_calls")
    backend = sandbox.backend()
    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])["finish_reason"] == "stop"


def test_an_unknown_finish_reason_is_reported_as_length(sandbox, caplog):
    """"stop" is a claim that the model said everything it had to say.

    The safety chain reads that field. An end nobody here has a reading for must
    arrive as an answer that may be cut, never as a finished one.
    """
    sandbox.env(FAKE_LLAMA_CHAT="unknown_finish")
    backend = sandbox.backend()
    with caplog.at_level(logging.WARNING):
        answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["finish_reason"] == "length"
    assert "content_filter" in caplog.text


def test_an_unknown_stop_type_is_reported_as_length(sandbox, caplog):
    sandbox.env(FAKE_LLAMA_COMPLETION="unknown_stop_type")
    backend = sandbox.backend()
    with caplog.at_level(logging.WARNING):
        answer = backend.generate(TEXT_ALIAS, "x")
    assert answer["finish_reason"] == "length"
    assert "something_new" in caplog.text


def test_a_character_split_across_two_chunks_arrives_whole(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="utf8")
    backend = sandbox.backend()
    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])["content"] == "Grüße, 日本語"


def test_comments_and_multi_line_data_follow_the_grammar(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="comment_multiline")
    backend = sandbox.backend()
    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])["content"] == "split"


# =============================================================================
# Failure: never "stop"
# =============================================================================

def test_a_child_that_dies_mid_stream_is_an_error(sandbox):
    """A crash mid-answer reaches the caller as a death, with its exit code."""
    sandbox.env(FAKE_LLAMA_CHAT="die", FAKE_LLAMA_EXIT_CODE="9")
    backend = sandbox.backend()
    seen = []
    with pytest.raises(ChildDied) as died:
        for item in backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]):
            seen.append(item)
    assert died.value.exit_code == 9
    assert "broke off the answer" in str(died.value)
    # The library calls a half-written body a transport error; passed on as one
    # it would reach the route as "inference failed".
    assert "ChunkedEncodingError" in str(died.value)
    assert not any(kind == "finish" for kind, _ in seen)


def test_a_stream_cut_short_is_an_error_not_a_finished_answer(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="cut")
    backend = sandbox.backend()
    seen = []
    with pytest.raises(ChildDied):
        for item in backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]):
            seen.append(item)
    assert seen == [("token", "half an ans")]
    assert ("finish", "stop") not in seen
    # The child is alive; only the answer is gone.
    assert child_of(backend).is_alive()


def test_half_a_frame_is_discarded_rather_than_handed_on(sandbox, caplog):
    """A frame with no blank line after it was never finished being written.

    Passing it on would turn a connection that broke into an answer that parsed.
    What the caller gets instead is the stream ending without its terminator,
    which is what happened.
    """
    sandbox.env(FAKE_LLAMA_CHAT="half_frame")
    backend = sandbox.backend()
    seen = []
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ChildDied) as died:
            for item in backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]):
                seen.append(item)

    assert seen == [("token", "Hello")]
    assert "ended inside an event" in caplog.text
    assert "discarded" in caplog.text
    assert "without saying how the answer finished" in str(died.value)
    # The child is fine; the connection is what ended. Saying "still running"
    # as the reason would send the reader after the wrong thing.
    assert "still up" in str(died.value)
    assert child_of(backend).is_alive()


def test_done_without_a_finish_reason_is_its_own_fault(sandbox):
    """Complete for the child, unfinished for everybody who reads the answer."""
    sandbox.env(FAKE_LLAMA_CHAT="done_without_finish")
    backend = sandbox.backend()
    with pytest.raises(ChildDied) as died:
        backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    message = str(died.value)
    assert "[DONE]" in message
    assert "treated as cut" in message
    assert "still up" in message
    assert child_of(backend).is_alive()


def test_the_memory_coming_back_is_what_ends_a_termination(sandbox):
    """Reaped and returned are two moments, and the second one is the one booked."""
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    sandbox.nvml[child.pid] = 900.0

    def _give_it_back():
        time.sleep(0.6)
        sandbox.nvml.pop(child.pid, None)
        # The cached enumeration still says the memory is there. Asking through
        # it would report a card that never empties, and every termination would
        # end at its deadline with the child filed as a survivor.
        sandbox.nvml_cached[child.pid] = 900.0

    threading.Thread(target=_give_it_back, daemon=True).start()
    started = time.monotonic()
    assert backend.unload(TEXT_ALIAS) is True
    assert time.monotonic() - started >= 0.5, "it waited for the card, not just the PID"
    assert child.pid not in sandbox.coordinator.owned


def test_an_error_event_carries_the_childs_message(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="event_error")
    backend = sandbox.backend()
    with pytest.raises(ChildRequestError) as failed:
        backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert failed.value.status == 500
    assert "the slot is gone" in str(failed.value)


def test_an_error_payload_carries_the_childs_message(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="data_error")
    backend = sandbox.backend()
    with pytest.raises(ChildRequestError) as failed:
        backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert failed.value.status == 400
    assert failed.value.route_status == 500
    assert "exceeds the available context size" in str(failed.value)


def test_a_child_that_is_still_loading_answers_503(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    control(child_of(backend), status=503)
    with pytest.raises(ChildRequestError) as failed:
        backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert failed.value.status == 503
    assert failed.value.route_status == 503


def test_a_refused_request_answers_400_and_is_reported_as_500(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    control(child_of(backend), status=400)
    with pytest.raises(ChildRequestError) as failed:
        backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert failed.value.status == 400
    assert failed.value.route_status == 500


# =============================================================================
# /completion
# =============================================================================

def test_completion_reports_the_end_it_had(sandbox):
    backend = sandbox.backend()
    assert backend.generate(TEXT_ALIAS, "x") == {
        "response": "ok!", "thinking": None, "finish_reason": "stop"}


@pytest.mark.parametrize("scenario,expected", [
    ("limit", "length"),
    ("truncated", "length"),
    ("word", "stop"),
])
def test_completion_stop_types(sandbox, scenario, expected):
    sandbox.env(FAKE_LLAMA_COMPLETION=scenario)
    backend = sandbox.backend()
    assert backend.generate(TEXT_ALIAS, "x")["finish_reason"] == expected


def test_a_completion_cut_short_is_an_error(sandbox):
    sandbox.env(FAKE_LLAMA_COMPLETION="cut")
    backend = sandbox.backend()
    with pytest.raises(ChildDied):
        backend.generate(TEXT_ALIAS, "x")


# =============================================================================
# The repetition guard
# =============================================================================

def test_a_looping_answer_is_stopped_and_the_child_is_disconnected(sandbox):
    sandbox.env(FAKE_LLAMA_CHAT="loop")
    backend = sandbox.backend()
    started = time.monotonic()
    result = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert result["finish_reason"] == "repetition"

    # It was STOPPED, not read to the end. The looping script runs for about
    # twenty seconds; an answer that arrives in one piece at the end of it means
    # the pieces were buffered somewhere and the guard never saw a growing text
    # — which is the guard silently doing nothing at all.
    assert time.monotonic() - started < 5.0
    assert len(result["content"]) < 1000

    child = child_of(backend)
    assert wait_until(lambda: fake_get(child, "/stats")["disconnects"] >= 1, timeout=3.0)
    assert wait_until(lambda: fake_get(child, "/slots")[0]["is_processing"] is False,
                      timeout=1.0)
    # The child survives the cancellation and serves the next request.
    control(child, chat="plain")
    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])["content"] == "Hello world"


def test_a_looping_completion_is_stopped_too(sandbox):
    sandbox.env(FAKE_LLAMA_COMPLETION="loop")
    backend = sandbox.backend()
    assert backend.generate(TEXT_ALIAS, "x")["finish_reason"] == "repetition"


# =============================================================================
# Eviction, unloading, reaping
# =============================================================================

def test_eviction_is_refused_while_a_request_is_in_flight(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = backend._supervisor.acquire(TEXT_ALIAS)
    assert child.in_use == 1

    assert backend.evict_model(TEXT_ALIAS) is False
    assert child.is_alive()
    assert child_of(backend) is child

    backend._supervisor.release(child)
    assert backend.evict_model(TEXT_ALIAS) is True
    assert not child.is_alive()
    assert child_of(backend) is None
    assert child.pid not in sandbox.coordinator.owned


def test_a_request_is_never_handed_a_child_that_is_being_killed(sandbox):
    """Mid-eviction the registry has already let go of the child.

    Marking it DYING and taking it out of the registry happen before the first
    signal, so `acquire` — which hands out READY children only — can no longer
    reach it while it is being ended.
    """
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    at_terminate = threading.Event()
    may_continue = threading.Event()
    original = child.terminate

    def _slow_terminate(reason=""):
        at_terminate.set()
        may_continue.wait(10.0)
        return original(reason)

    child.terminate = _slow_terminate
    outcome = {}
    evicting = threading.Thread(
        target=lambda: outcome.update(evicted=backend.evict_model(TEXT_ALIAS)),
        daemon=True)
    evicting.start()
    assert at_terminate.wait(5.0)

    assert backend._supervisor.acquire(TEXT_ALIAS) is None
    assert child.state is ChildState.DYING
    assert child_of(backend) is None

    may_continue.set()
    evicting.join(timeout=15.0)
    assert outcome["evicted"] is True


def test_an_eviction_and_a_request_never_both_win(sandbox):
    """The decision and the removal are one critical section.

    Split in two, a request landing between them is handed a child whose
    eviction has already been decided — it gets a port that stops answering a
    moment later. Either the request comes first and the eviction is refused, or
    the eviction comes first and there is nothing to acquire.
    """
    # A wide port range: twenty spawns and kills in a row leave ports in
    # TIME_WAIT, and the bind probe passes over every one of them.
    backend = sandbox.backend(port_count=64)
    for _ in range(20):
        backend._load(TEXT_ALIAS)
        child = child_of(backend)
        start = threading.Barrier(2)
        result = {}

        def _evict():
            start.wait(5.0)
            result["evicted"] = backend.evict_model(TEXT_ALIAS)

        def _acquire():
            start.wait(5.0)
            result["acquired"] = backend._supervisor.acquire(TEXT_ALIAS)

        threads = [threading.Thread(target=_evict, daemon=True),
                   threading.Thread(target=_acquire, daemon=True)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20.0)

        acquired = result.get("acquired")
        if acquired is not None:
            assert result["evicted"] is False, (
                "a child was handed out AND killed in the same moment")
            assert acquired.is_alive()
            assert acquired.state is ChildState.READY
            backend._supervisor.release(acquired)
            backend.unload(TEXT_ALIAS, force=True)
        else:
            assert result["evicted"] is True
            assert not child.is_alive()


def test_force_unload_takes_a_busy_child_anyway(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = backend._supervisor.acquire(TEXT_ALIAS)
    assert backend.unload(TEXT_ALIAS, force=False) is False
    assert backend.unload(TEXT_ALIAS, force=True) is True
    assert not child.is_alive()


def test_unloading_what_is_not_there_says_so(sandbox):
    backend = sandbox.backend()
    assert backend.unload(TEXT_ALIAS) is False


def test_a_child_that_died_is_reaped_out_of_the_registry(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    os.kill(child.pid, signal.SIGKILL)
    assert wait_until(lambda: child.poll() is not None, timeout=5.0)

    backend._supervisor.reap_once()
    assert child_of(backend) is None
    assert backend.get_registered_models() == []
    assert child.pid not in sandbox.coordinator.owned
    assert backend._supervisor.state_file.read() == []


def test_a_request_after_a_crash_gets_a_new_child_in_that_request(sandbox):
    """A crash costs one reading, not every reading until a sweep notices.

    No reaper runs in this test on purpose: the request path itself has to
    notice that the process behind a READY entry is gone, take it out, and load
    a new one — which is what the request after a crash actually met.
    """
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    first = child_of(backend)
    os.kill(first.pid, signal.SIGKILL)
    # Waited for in /proc and left uncollected: nothing in this test may reap
    # the corpse, or the request path would be handed a child that already
    # knows its exit code and the check under test would never run.
    assert wait_until(lambda: ended_unreaped(first.pid), timeout=5.0)
    assert first._proc.returncode is None, \
        "the corpse is still uncollected, which is what a request really meets"

    started = time.monotonic()
    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world"
    assert time.monotonic() - started < 30.0

    second = child_of(backend)
    assert second is not first and second.pid != first.pid
    assert second.state is ChildState.READY
    assert first.pid not in sandbox.coordinator.owned
    assert second.pid in sandbox.coordinator.owned
    assert state_pids(backend) == [second.pid], \
        "the file the next start reads names the living child and nobody else"


def test_a_child_that_died_mid_answer_is_gone_before_the_error_arrives(sandbox):
    """The registry lets go in the same request that met the death.

    The failed request still fails — a generation is never quietly run a second
    time — but the next one starts a child instead of being handed the corpse.
    """
    sandbox.env(FAKE_LLAMA_CHAT="die", FAKE_LLAMA_EXIT_CODE="9")
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    dead = child_of(backend)

    with pytest.raises(ChildDied) as died:
        list(backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]))
    assert died.value.exit_code == 9

    assert child_of(backend) is None, "and no reaper ran to do it"
    assert dead.pid not in sandbox.coordinator.owned
    assert backend.get_loaded_models() == []

    sandbox.env(FAKE_LLAMA_CHAT="plain")
    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world"
    assert child_of(backend).pid != dead.pid


def test_a_stream_that_ends_without_its_terminator_keeps_the_child(sandbox):
    """The "cut" script ends its body properly, with no finish reason in it.

    So this is the bookkeeping half of a truncated answer: the request fails —
    an answer whose end nobody can vouch for is never handed on as finished —
    and the child, which did nothing wrong and holds a loaded model, keeps its
    place. A NEGATIVE GUARD, and a weak one: nothing breaks here, the stream
    simply ends early, so it passes with the whole crash-detach change reverted
    and it does not catch a retire() that fires on a living child either
    (measured: it survives that mutant). The test below is the one that does —
    there the transport really breaks under a process that is still up.
    """
    sandbox.env(FAKE_LLAMA_CHAT="cut")
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    with pytest.raises(ChildDied):
        list(backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]))

    assert child_of(backend) is child
    assert child.is_alive()
    assert child.pid in sandbox.coordinator.owned


def test_a_transport_that_broke_under_a_living_child_keeps_the_child(sandbox):
    """The socket goes, the process stays: a lost answer, not a lost model.

    The child cuts the connection in the middle of the chunked body and goes on
    running — a proxy in between, a slot reset, a network that went. Nothing
    here may take it out of the registry: it holds a loaded model, and a
    retire() on an unknown exit code would leave that model on the card with
    nothing left in the registry to signal at shutdown.

    What this pins is retire()'s liveness guard, and only that. The backend's
    own "only retire on a known exit code" is a second line of the same
    defence, and measured: with `_died` made to retire whatever the exit code,
    this test still passes as long as the guard stands, and fails once both are
    gone.
    """
    sandbox.env(FAKE_LLAMA_CHAT="abort")
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    with pytest.raises(ChildDied) as died:
        list(backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]))
    assert died.value.exit_code is None
    assert "still running" in str(died.value)

    assert child_of(backend) is child
    assert child.is_alive() and child.poll() is None
    assert child.pid in sandbox.coordinator.owned
    assert state_pids(backend) == [child.pid]

    # And the next request is served by that same process — no reload, because
    # nothing was lost but one answer.
    control(child, chat="plain")
    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world"
    assert child_of(backend).pid == child.pid


def test_a_child_that_answers_nothing_at_all_is_ended_by_the_progress_bound(sandbox):
    """A llama-server that survived a CUDA error: it accepts and never writes.

    No read timeout will ever end this, by rule. What ends it is the same
    progress bound that watches a load — no frame, no line, no GPU memory
    moving — and it must give the refcount, and with it the model, back.
    """
    sandbox.env(FAKE_LLAMA_CHAT="wedge")
    backend = sandbox.backend(stall_s=1.0, start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    started = time.monotonic()
    with pytest.raises(ChildDied) as died:
        list(backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]))
    took = time.monotonic() - started
    assert took < 20.0, "the bound ended it, nothing waited for an answer"
    assert "no progress" in str(died.value), \
        "the caller learns that a bound was reached, not just that a socket closed"

    assert wait_until(lambda: child_of(backend) is None, timeout=10.0)
    assert child.in_use == 0, "the refcount came back with the failed request"
    assert wait_until(lambda: child.pid not in sandbox.coordinator.owned, timeout=10.0)

    sandbox.env(FAKE_LLAMA_CHAT="plain")
    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world"
    assert child_of(backend).pid != child.pid


def test_a_slow_answer_is_never_cut_by_that_bound(sandbox):
    """The control: slow IS progress. One frame per 0.4s under a 1s bound.

    Without this the test above would be satisfied by a bound that cuts every
    answer a model takes its time over — which is the failure this whole design
    exists to avoid.
    """
    sandbox.env(FAKE_LLAMA_CHAT="slow")
    # Five times the longest silence this script produces. Tight to the frame
    # interval, one scheduler hiccup would fail it and the failure would say
    # nothing about the bound. Still load-bearing: at a bound of zero the very
    # first gap ends the child.
    backend = sandbox.backend(stall_s=2.0, start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["finish_reason"] == "stop"
    assert answer["content"].startswith("piece 0 ")
    assert answer["content"].endswith("piece 7"), "every frame arrived, none was cut"
    assert child_of(backend) is child, "it was never ended"
    assert child.in_use == 0


def test_a_death_the_card_has_not_caught_up_with_still_loads(sandbox):
    """The corpse's memory is still in NVML's reading. The next load goes ahead.

    A cached enumeration outlives the process it lists, and the answer to that
    is to have it re-read — not to wait for it, and not to start freeing other
    people's models against a figure that names a dead child.
    """
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    first = child_of(backend)
    # What the card says, and what a cached read still shows, for a PID that is
    # about to be gone. Neither ever clears in this test.
    sandbox.nvml[first.pid] = 1500.0
    sandbox.nvml_cached[first.pid] = 1500.0
    before = len(sandbox.coordinator.requests)

    os.kill(first.pid, signal.SIGKILL)
    assert wait_until(lambda: ended_unreaped(first.pid), timeout=5.0)

    started = time.monotonic()
    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world"
    assert time.monotonic() - started < 20.0, \
        "the wait for the memory to come back is bounded; a stale reading never clears"

    assert len(sandbox.coordinator.requests) - before == 1, \
        "one load asked for room once; nothing asked twice on the way"
    assert sandbox.coordinator.invalidated >= 1, \
        "the cached enumeration was dropped rather than acted on"
    assert child_of(backend).pid != first.pid


def test_a_child_that_dies_before_it_can_serve_is_reported_as_the_death_it_is(sandbox):
    """Loaded for this request, gone before it could run it.

    Not a refused load: that reads as "the model never reached the card" and
    sends the caller back to try again into a model that crashes. The exit code
    and the last lines travel with it.
    """
    backend = sandbox.backend(start_reaper=False)
    original = type(backend)._load

    def _load_then_lose_it(self, alias):
        original(self, alias)
        child = self._supervisor.get(alias)
        os.kill(child.pid, signal.SIGKILL)
        assert wait_until(lambda: ended_unreaped(child.pid), timeout=5.0)

    sandbox.monkeypatch.setattr(type(backend), "_load", _load_then_lose_it)

    with pytest.raises(ChildDied) as died:
        backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert died.value.exit_code == -signal.SIGKILL
    assert "died before the request it was started for" in str(died.value)
    assert died.value.log_tail, "the child's own last lines came with it"
    assert not isinstance(died.value, ModelLoadRefused), \
        "the class decides the status: 500 with the cause, not a 503 'try again'"
    assert child_of(backend) is None
    assert state_pids(backend) == []


def test_a_death_found_under_a_busy_child_leaves_the_holder_its_own_object(sandbox):
    """One request holds the child; the next one finds it dead and loads.

    The holder's release() must land on the object it was handed and on nothing
    else. Booked against the alias instead, it would decrement the NEW child's
    refcount — the count that decides whether an eviction may take it.
    """
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    held = backend._supervisor.acquire(TEXT_ALIAS)     # a stream in flight
    assert held is not None and held.in_use == 1

    os.kill(held.pid, signal.SIGKILL)
    assert wait_until(lambda: ended_unreaped(held.pid), timeout=5.0)

    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world"
    fresh = child_of(backend)
    assert fresh is not held
    assert fresh.in_use == 0, "the new child carries nobody else's refcount"
    assert held.pid not in sandbox.coordinator.owned
    assert state_pids(backend) == [fresh.pid]

    backend._supervisor.release(held)                  # the holder's finally
    assert held.in_use == 0
    assert fresh.in_use == 0, "released by identity, not by alias"
    assert backend.unload(TEXT_ALIAS) is True, \
        "the busy check reads the living child's own count"


def test_two_requests_meeting_the_same_crash_start_one_child_between_them(sandbox):
    """Both find the corpse. One load happens, one child exists, room is asked once."""
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    first = child_of(backend)
    os.kill(first.pid, signal.SIGKILL)
    assert wait_until(lambda: ended_unreaped(first.pid), timeout=5.0)

    spawned_before = len(sandbox.coordinator.owned_history)
    asked_before = len(sandbox.coordinator.requests)
    answers, errors = [], []
    ready = threading.Barrier(2)

    def _ask():
        ready.wait()
        try:
            answers.append(backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}]))
        except Exception as e:                          # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_ask) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not errors, f"both requests were served: {errors}"
    assert [a["content"] for a in answers] == ["Hello world", "Hello world"]
    assert len(sandbox.coordinator.owned_history) - spawned_before == 1, \
        "one child was started, not one per request"
    assert len(sandbox.coordinator.requests) - asked_before == 1, \
        "and room was asked for once"
    assert child_of(backend) is not None
    assert state_pids(backend) == [child_of(backend).pid]


def test_a_crash_the_reaper_finds_is_settled_before_the_next_load(sandbox):
    """A crash with nobody waiting is still a crash the next request pays for.

    The reaper finds it, and unless the card is given time to let the memory go
    and the coordinator told to re-read, the content check arriving milliseconds
    later asks for room against an enumeration that still lists the exited PID:
    nothing is evictable, because the child is out of the registry, so a model
    that is already gone refuses the next load and has ComfyUI asked to free
    VRAM for it.
    """
    backend = sandbox.backend(start_reaper=True)
    backend._load(TEXT_ALIAS)
    first = child_of(backend)
    # The card goes on listing the corpse for the whole of this test.
    sandbox.nvml[first.pid] = 1500.0
    sandbox.nvml_cached[first.pid] = 1500.0
    reads_before = sandbox.nvml_reads.get(first.pid, 0)

    os.kill(first.pid, signal.SIGKILL)
    assert wait_until(lambda: child_of(backend) is None, timeout=10.0)
    # Two invalidations: one the moment it was forgotten, one after the wait for
    # the card. The second is the settle finishing, which is what the next
    # request depends on.
    assert wait_until(lambda: sandbox.coordinator.invalidated >= 2, timeout=15.0)
    assert sandbox.nvml_reads.get(first.pid, 0) - reads_before >= 3, \
        "the reaper waited for the card to let go, rather than only saying so"

    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world", "no false shortfall"

    kinds = [event[0] for event in sandbox.coordinator.events]
    assert kinds.count("request") == 2, "one load asked for room, then the other"
    assert kinds[-1] == "request"
    assert "invalidate" in kinds[1:-1], \
        "and the stale reading was dropped before the second one asked"


def test_a_death_is_never_handed_to_a_request_that_met_something_else(sandbox):
    """A death explains the attempt it was written during, and no other.

    The record is keyed by alias, and an alias outlives its children by hours.
    Left standing, this morning's crash becomes the answer given this afternoon
    to a request that found no child because an eviction took it — a 500 with a
    foreign exit code and somebody else's last lines, where the truth is a 503
    and "try again".
    """
    backend = sandbox.backend(start_reaper=False)
    supervisor = backend._supervisor
    backend._load(TEXT_ALIAS)
    first = child_of(backend)
    os.kill(first.pid, signal.SIGKILL)
    assert wait_until(lambda: ended_unreaped(first.pid), timeout=5.0)

    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])["content"] \
        == "Hello world"
    assert supervisor._deaths == {}, "the record went with the child it explained"

    # Later: the load succeeds and an eviction takes the child before it is used.
    original = type(backend)._load

    def _load_then_evict(self, alias):
        original(self, alias)
        self._supervisor.unload(alias, force=True)

    sandbox.monkeypatch.setattr(type(backend), "_load", _load_then_evict)
    assert backend.unload(TEXT_ALIAS) is True
    with pytest.raises(ModelLoadRefused) as refused:
        backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert "evicted between its load and its use" in str(refused.value)

    # And a record that outlives its child by any route is not consumed either.
    supervisor._deaths[TEXT_ALIAS] = {"exit_code": -9, "log_tail": ["from hours ago"],
                                      "at": time.monotonic() - 4 * 3600, "pid": 1}
    assert supervisor.take_death(TEXT_ALIAS, after=time.monotonic()) is None
    assert supervisor.take_death(TEXT_ALIAS) is None, "it was dropped, not kept"


def test_an_older_state_snapshot_never_overwrites_a_newer_one(sandbox):
    """Numbered, because they are written outside the lock that made them."""
    supervisor = sandbox.supervisor()
    newer = [{"alias": "b", "pid": 2, "starttime": 2, "port": 2, "started_at": 2.0}]
    older = [{"alias": "a", "pid": 1, "starttime": 1, "port": 1, "started_at": 1.0}]
    assert supervisor._write_state_entries(2, newer) is True
    assert supervisor._write_state_entries(1, older) is False
    assert supervisor.state_file.read() == newer


def test_two_writers_leave_the_file_holding_the_newer_snapshot(sandbox):
    """Through _write_state itself, with the first write held up mid-flight.

    What this pins is the write lock: the second writer blocks behind the
    delayed first one, so the writes land in registry order and the file ends
    up holding what the registry looked like LAST. (The sequence guard that
    drops an older snapshot is pinned by the older-snapshot test above, which
    drives the helper with inverted numbers.) Without the lock, the delayed
    write lands afterwards and the next start of this service reads a file
    that names nobody while a child of ours is on the card.
    """
    supervisor = sandbox.supervisor()
    entered = threading.Event()
    let_go = threading.Event()
    real_write = supervisor.state_file.write
    calls = []

    def _write(entries):
        calls.append(entries)
        if len(calls) == 1:
            entered.set()
            let_go.wait(timeout=10.0)
        real_write(entries)

    supervisor.state_file.write = _write
    older = threading.Thread(target=supervisor._write_state)   # an empty registry
    older.start()
    assert entered.wait(timeout=5.0)

    entry = {"alias": "b", "pid": 4242, "starttime": 7, "port": 1, "started_at": 1.0}
    arrived = types.SimpleNamespace(as_state_entry=lambda: dict(entry))
    with supervisor.state_lock:
        supervisor._children["b"] = arrived
    newer = threading.Thread(target=supervisor._write_state)
    newer.start()
    newer.join(timeout=2.0)          # queued behind the older one, by design

    let_go.set()
    older.join(timeout=10.0)
    newer.join(timeout=10.0)
    with supervisor.state_lock:
        supervisor._children.pop("b", None)

    assert supervisor.state_file.read() == [entry], \
        "the file holds the newest registry, whatever order the writes landed in"


def test_a_stalled_state_file_does_not_hold_the_registry(sandbox):
    """The write is outside state_lock, and it has to be.

    An eviction holds the coordinator's request lock while it waits on unload,
    and unload takes state_lock. A state directory that has stopped answering
    would otherwise stall every load on the platform behind one write.
    """
    supervisor = sandbox.supervisor()
    in_write = threading.Event()
    let_it_finish = threading.Event()
    took_the_lock = threading.Event()
    real_write = supervisor.state_file.write

    def _slow_write(entries):
        in_write.set()
        assert let_it_finish.wait(timeout=10.0)
        real_write(entries)

    supervisor.state_file.write = _slow_write
    writer = threading.Thread(target=supervisor._write_state)
    writer.start()
    assert in_write.wait(timeout=5.0)

    def _take_it():
        with supervisor.state_lock:
            took_the_lock.set()

    other = threading.Thread(target=_take_it)
    other.start()
    try:
        assert took_the_lock.wait(timeout=3.0), \
            "the registry was held for the whole of a write that never returned"
    finally:
        let_it_finish.set()
        writer.join(timeout=5.0)
        other.join(timeout=5.0)


def test_arriving_requests_do_not_keep_a_wedged_child_alive(sandbox):
    """The traffic a wedged alias attracts is not evidence that it is working.

    Every request that ARRIVES makes the child write its own log lines, and the
    safety chain keeps sending checks to the same alias — so a bound that
    watched the child's log at all would be refreshed by exactly the load under
    which it has to act, and the model would never come back.
    """
    sandbox.env(FAKE_LLAMA_CHAT="wedge")
    backend = sandbox.backend(stall_s=1.0, start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    errors = []
    askers = []
    stop = threading.Event()

    def _ask():
        if stop.is_set():
            # Once the child is gone the next request would LOAD one, and a
            # thread still doing that after the test ends leaves a server
            # behind. The join below is the guarantee; this is the cheap half.
            return
        try:
            list(backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]))
        except Exception as e:                          # noqa: BLE001
            errors.append(e)

    def _drip():
        # A check every 0.3s against a one-second bound, without pause: the
        # shape of the safety chain meeting an alias that has stopped
        # answering. Three arrivals fall inside every bound-length window (four
        # of them have landed by the time the bound is first reached), so any
        # mark that a mere arrival moves would keep this child alive for as long
        # as the traffic lasts.
        while not stop.wait(0.3):
            asker = threading.Thread(target=_ask, daemon=True)
            askers.append(asker)
            asker.start()

    dripper = threading.Thread(target=_drip, daemon=True)
    dripper.start()
    try:
        assert wait_until(lambda: child_of(backend) is None, timeout=10.0), \
            "the arriving requests kept the wedged child alive"
    finally:
        stop.set()
        dripper.join(timeout=5.0)
        for asker in askers:
            asker.join(timeout=15.0)

    assert not any(asker.is_alive() for asker in askers), \
        "a request still in flight here would outlive the test and its child"
    assert errors and all(isinstance(e, ChildDied) for e in errors)
    assert any("no progress" in str(e) for e in errors)
    assert sum("launch_slot_" in line for line in child.log_tail(80)) >= 3, \
        "each arrival did write its lines — they simply do not count"


def test_a_child_whose_slots_are_moving_is_never_cut(sandbox):
    """No frame for seconds, and not a stall: the model is decoding.

    Whether anything reaches the reader is the reader's business — the child
    says what it has decoded, and a child that is decoding is working.
    """
    sandbox.env(FAKE_LLAMA_CHAT="wedge", FAKE_LLAMA_TICK="1")
    backend = sandbox.backend(stall_s=1.0, start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    errors = []

    def _ask():
        try:
            list(backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]))
        except Exception as e:                          # noqa: BLE001
            errors.append(e)

    asking = threading.Thread(target=_ask, daemon=True)
    asking.start()
    assert wait_until(lambda: child.in_use > 0, timeout=5.0)
    assert wait_until(lambda: child.slot_counter() > 5, timeout=5.0)

    time.sleep(3.0)                                     # three times the bound
    assert child_of(backend) is child, "it was decoding the whole time"
    assert not errors

    control(child, tick=0)                              # and now it stops
    asking.join(timeout=30)
    assert len(errors) == 1 and isinstance(errors[0], ChildDied)
    assert "no progress" in str(errors[0])
    assert wait_until(lambda: child_of(backend) is None, timeout=10.0)


def test_a_child_whose_slots_never_answer_is_cut(sandbox):
    """Silence from /slots IS the evidence: it is served by the main task loop.

    A llama-server whose loop has stopped turning answers nothing there, however
    healthy its socket looks — so a probe that times out counts as no progress,
    never as the benefit of the doubt.
    """
    sandbox.env(FAKE_LLAMA_CHAT="wedge", FAKE_LLAMA_TICK="1")
    backend = sandbox.backend(stall_s=1.0, start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    control(child, slots_hang=1)

    with pytest.raises(ChildDied) as died:
        list(backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}]))
    assert "no progress" in str(died.value)
    assert wait_until(lambda: child_of(backend) is None, timeout=10.0)


@pytest.mark.parametrize("index", range(len(WORK_LINES)),
                         ids=[line[:34].strip() for line in WORK_LINES])
def test_a_child_working_on_the_prompt_is_never_cut(sandbox, index):
    """A long prompt, or an image: seconds of work with no frame and no token.

    The decode counter stands at zero for the whole of a prefill, so the lines
    the child writes per batch and per image slice are what carry it — and they
    are counted apart from the lines it writes when a request merely arrives.

    One case per line the build actually writes, both the ones that open a piece
    of work and the ones that close it. A marker with a typo in it would leave
    exactly one of these red, and a VLM prefill cut in production.
    """
    sandbox.env(FAKE_LLAMA_CHAT="prefill", FAKE_LLAMA_WORK_LINE=index)
    backend = sandbox.backend(stall_s=1.0, start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world"
    assert answer["finish_reason"] == "stop"
    assert child_of(backend) is child, "three seconds of prefill under a one-second bound"


def test_a_consumer_that_stops_reading_does_not_cost_the_child(sandbox):
    """The reader stops; the child does not. It must not be ended for that.

    Frames are stamped where they are consumed, so a caller that stops pulling
    looks exactly like a child that stopped writing. The child's own slots tell
    the two apart.

    THE CONSUMER-SIDE HALF ONLY. Eight small frames fit in the socket buffer, so
    the fake never blocks in its own write and this says nothing about what a
    real server does under back-pressure. That half is not a test but a reading
    of the build: the result queue it decodes into is unbounded, cited next to
    the probe in llm_child.py.
    """
    sandbox.env(FAKE_LLAMA_CHAT="slow", FAKE_LLAMA_TICK="1")
    # Four seconds, and the pause below is 2.5: a reader that comes back inside
    # the bound loses nothing at all. Past it, the request itself is ended and
    # the child kept — which is the test after this one.
    backend = sandbox.backend(stall_s=4.0, start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    stream = backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert next(stream)[0] == "token"
    time.sleep(2.5)                                     # nobody is reading
    assert child_of(backend) is child
    assert child.in_use == 1

    rest = list(stream)
    assert ("finish", "stop") in rest
    assert child_of(backend) is child


def test_one_stream_that_stops_draining_is_ended_without_the_child(sandbox):
    """A reader that stopped taking its answer must not cost everyone the model.

    With one slot the child finishes that answer, releases the slot and serves
    the next caller — so every child-level signal keeps moving while the
    abandoned request holds its refcount, and the refcount refuses every
    eviction of a perfectly healthy model. The request is ended and nothing
    else: the child goes on serving, and the caller learns which bound it met.
    """
    sandbox.env(FAKE_LLAMA_CHAT="slow")
    backend = sandbox.backend(stall_s=1.0, start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    abandoned = backend.chat_stream(TEXT_ALIAS, [{"role": "user", "content": "a"}])
    assert next(abandoned)[0] == "token", "frames flowed, and then the reader stopped"

    served = []
    errors = []

    def _keep_reading():
        try:
            served.extend(backend.chat_stream(
                TEXT_ALIAS, [{"role": "user", "content": "b"}]))
        except Exception as e:                          # noqa: BLE001
            errors.append(e)

    other = threading.Thread(target=_keep_reading)
    other.start()
    try:
        # Long enough for the bound to be reached with the abandoned stream
        # untouched, while the other one is served frame by frame.
        time.sleep(2.5)
        with pytest.raises(ChildDied) as died:
            list(abandoned)
    finally:
        other.join(timeout=60)

    assert "received nothing for" in str(died.value)
    assert "still serving" in str(died.value), "the child is not the fault here"
    assert not errors, f"the other caller was served throughout: {errors}"
    assert ("finish", "stop") in served

    assert child_of(backend) is child and child.is_alive()
    assert wait_until(lambda: child.in_use == 0, timeout=10.0), \
        "both refcounts came back"
    assert backend.chat(TEXT_ALIAS, [{"role": "user", "content": "c"}])["content"]


def test_the_bound_that_ended_a_child_is_named_in_the_error(sandbox):
    """A stream that ends cleanly after we ended the child says so.

    "Its process is still up — the connection ended" is true and useless: it
    reads as the cause and sends whoever gets it after a network fault. The one
    thing worth acting on is that this service applied a bound.
    """
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    child.end_reason = "no progress for 180s while 1 request(s) were waiting for it"

    for said_done in (False, True):
        error = backend._ended_without_terminator(child, said_done=said_done)
        assert "no progress for 180s" in str(error)
        assert "still up" not in str(error)


def test_a_reaping_pass_stands_down_the_moment_a_sweep_takes_over(sandbox):
    """Two passes over the same children is one too many.

    A shutdown sweep signals every child and collects them against one
    deadline. A reaping pass that goes on working through that list either
    races it for the same process or, by filing a survivor, restarts the very
    thread the sweep just stood down.
    """
    supervisor = sandbox.supervisor()
    backend = sandbox.backend(supervisor=supervisor)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    os.kill(child.pid, signal.SIGKILL)
    assert wait_until(lambda: ended_unreaped(child.pid), timeout=5.0)

    supervisor.stop()                       # what terminate_all does first
    supervisor.reap_once()
    assert child_of(backend) is child, "the pass stood down; the sweep owns them now"

    supervisor._stop.clear()
    supervisor.reap_once()
    assert child_of(backend) is None, "and does the work again once it may"


def test_nothing_but_the_sweep_may_bring_the_reaper_back(sandbox):
    """Filing a survivor restarts the reaper — and the sweep files survivors.

    So every path that re-arms is refused while a sweep is running, except the
    sweep's own call at the end of it, which is what brings the reaper back for
    the children the sweep could not collect.
    """
    supervisor = sandbox.supervisor(start_reaper=True)
    supervisor.stop()
    supervisor._sweeping = True
    try:
        supervisor._ensure_reaper()
        assert supervisor._stop.is_set(), "somebody re-armed it mid-sweep"
        supervisor._ensure_reaper(force=True)
        assert not supervisor._stop.is_set(), "the sweep's own call must still work"
    finally:
        supervisor._sweeping = False
        supervisor.stop()


def test_a_survivor_is_taken_off_the_books_before_any_waiting(sandbox):
    """A child that outlasted SIGKILL holds its model until somebody says so.

    The rest of a pass waits: two seconds for a corpse's memory to come back,
    up to three for a busy child's slots to answer. Behind those, a survivor's
    memory stays booked to a process that no longer exists for a whole pass
    longer than it has to.
    """
    supervisor = sandbox.supervisor()
    backend = sandbox.backend(supervisor=supervisor)

    backend._load(VISION_ALIAS)
    survivor = child_of(backend, VISION_ALIAS)
    with supervisor.state_lock:
        supervisor._detach_locked(survivor)
        supervisor._dying.append(survivor)
    os.kill(survivor.pid, signal.SIGKILL)
    assert wait_until(lambda: ended_unreaped(survivor.pid), timeout=5.0)

    backend._load(TEXT_ALIAS)
    crashed = child_of(backend)
    # Its memory never comes back in this test, so its settle runs the full
    # bound — which is exactly the wait the survivor must not be behind.
    sandbox.nvml[crashed.pid] = 1500.0
    sandbox.nvml_cached[crashed.pid] = 1500.0
    os.kill(crashed.pid, signal.SIGKILL)
    assert wait_until(lambda: ended_unreaped(crashed.pid), timeout=5.0)

    withdrawn = []
    supervisor.set_owner_hooks(supervisor._on_register,
                               lambda c: withdrawn.append(c))
    pass_thread = threading.Thread(target=supervisor.reap_once)
    pass_thread.start()
    try:
        assert wait_until(lambda: survivor in withdrawn, timeout=1.0), \
            "the survivor waited behind the corpse's settle"
    finally:
        pass_thread.join(timeout=30)


def test_the_reaper_thread_does_the_same_by_itself(sandbox):
    backend = sandbox.backend(start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    os.kill(child.pid, signal.SIGKILL)
    assert wait_until(lambda: child_of(backend) is None, timeout=5.0)


def test_only_ready_children_count_as_loaded(sandbox):
    """A child still reading weights off disk is not a model anybody can ask."""
    sandbox.env(FAKE_LLAMA_MODE="never_chatty")
    backend = sandbox.backend(stall_s=30.0)
    outcome = []

    def _load():
        # The forced unload below ends this load; the refusal is the point of
        # the test's teardown, not a failure of it.
        try:
            backend._load(TEXT_ALIAS)
        except ModelLoadRefused as e:
            outcome.append(e)

    worker = threading.Thread(target=_load, daemon=True)
    worker.start()
    assert wait_until(lambda: child_of(backend) is not None, timeout=10.0)

    assert child_of(backend).state is ChildState.LOADING
    assert backend.get_loaded_models() == []
    assert backend.get_registered_models() == []

    backend.unload(TEXT_ALIAS, force=True)
    worker.join(timeout=15.0)


def test_a_child_that_ignores_sigterm_is_killed_and_reaped(sandbox):
    """SIGTERM, the bound, SIGKILL — and the exit code is collected.

    A child nobody waits for stays a zombie, and a zombie answers os.kill(pid,0)
    exactly like a running process.
    """
    sandbox.env(FAKE_LLAMA_IGNORE_SIGTERM="1")
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)

    started = time.monotonic()
    assert backend.unload(TEXT_ALIAS) is True
    took = time.monotonic() - started

    assert took >= 1.0, "the polite signal was given its time first"
    assert took < 10.0, "and the whole escalation stayed inside the bound"
    assert child.poll() is not None, "the exit code was collected"
    assert child.pid not in sandbox.coordinator.owned


def test_a_child_whose_memory_lingers_is_handed_to_the_reaper(sandbox):
    """Gone from the process table is not the same as gone from the card.

    While NVML still lists the PID the memory is still booked, so the child
    stays on the dying list — and the reaper takes it off once the figure goes.
    """
    backend = sandbox.backend(start_reaper=False)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    sandbox.nvml[child.pid] = 1500.0        # the card still holds it

    assert backend.unload(TEXT_ALIAS) is False, "not gone while its memory stands"
    assert child.poll() is not None
    assert child in backend._supervisor._dying
    assert child.pid in sandbox.coordinator.owned, "still ours, still booked"

    sandbox.nvml.pop(child.pid)             # the driver gave it back
    backend._supervisor.reap_once()
    assert child not in backend._supervisor._dying
    assert child.pid not in sandbox.coordinator.owned
    assert backend._supervisor.state_file.read() == []


def test_a_child_that_dies_after_the_finish_chunk_still_delivers(sandbox):
    """The answer was complete before the connection was.

    Reading on to [DONE] is a courtesy to the child — it keeps an ordinary
    request from looking like a cancellation. A child that crashes in that
    moment has already given the caller everything it asked for.
    """
    sandbox.env(FAKE_LLAMA_CHAT="die_after_finish", FAKE_LLAMA_EXIT_CODE="9")
    backend = sandbox.backend()
    answer = backend.chat(TEXT_ALIAS, [{"role": "user", "content": "x"}])
    assert answer["content"] == "Hello world"
    assert answer["finish_reason"] == "stop"


def test_a_load_bar_without_newlines_counts_as_progress(sandbox):
    """llama.cpp prints its load bar as dots with no newline (LOG_CONT).

    Counting LINES, a supervisor sees nothing at all for the whole copy phase
    and kills a model that is loading normally. What moves is the byte count.
    """
    sandbox.env(FAKE_LLAMA_MODE="never_dots")
    backend = sandbox.backend(stall_s=0.75, load_ceiling_s=900.0)
    outcome = []

    def _load():
        try:
            backend._load(TEXT_ALIAS)
            outcome.append("ready")
        except ModelLoadRefused as e:
            outcome.append(e)

    worker = threading.Thread(target=_load, daemon=True)
    worker.start()
    assert wait_until(lambda: child_of(backend) is not None, timeout=10.0)
    child = child_of(backend)

    # The startup lines are written before the bar begins; the baseline is
    # taken once the last of them has gone past.
    assert wait_until(lambda: any("listening" in line for line in child.log_tail(10)),
                      timeout=10.0)
    time.sleep(0.2)
    lines_before, bytes_before = child.log_seq, child._log_bytes
    worker.join(timeout=3.0)
    assert worker.is_alive(), f"a child writing its load bar was refused: {outcome}"
    assert child.log_seq == lines_before, "not one finished line in all that time"
    assert child._log_bytes > bytes_before, "and the bytes are what showed it was alive"

    backend.unload(TEXT_ALIAS, force=True)
    worker.join(timeout=15.0)


def test_survivors_are_reaped_after_a_sweep_with_no_load_after_it(sandbox):
    """The reaper stands down for the sweep and comes back for what it left.

    An emergency reclaim ends every child and the service goes on serving. With
    the reaper stopped and nothing spawned afterwards, a survivor would keep its
    memory booked in the coordinator for the life of the process.
    """
    sandbox.env(FAKE_LLAMA_IGNORE_SIGTERM="1")
    backend = sandbox.backend(start_reaper=True)
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    sandbox.nvml[child.pid] = 900.0          # the card does not let go

    backend._supervisor.terminate_all("emergency reclaim", bound_s=10.0)
    assert child.poll() is not None, "SIGTERM was ignored, SIGKILL was not"
    assert child in backend._supervisor._dying
    assert child.pid in sandbox.coordinator.owned

    sandbox.nvml.pop(child.pid)              # the driver gives it back
    assert wait_until(lambda: child not in backend._supervisor._dying, timeout=10.0), \
        "no load followed the sweep, and nothing else would ever take it off"
    assert child.pid not in sandbox.coordinator.owned


def test_a_child_is_withdrawn_from_the_coordinator_exactly_once(sandbox):
    """Two paths can end the same child; the PID registry is keyed by PID.

    Withdrawing twice would take out the entry of whatever child the kernel has
    since given that number to.
    """
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    withdrawn = []
    backend._supervisor.set_owner_hooks(
        backend._supervisor._on_register, lambda c: withdrawn.append(c.pid))

    assert backend.unload(TEXT_ALIAS) is True
    backend._supervisor.reap_once()
    backend._supervisor._forget(child, terminate=False, reason="")
    assert withdrawn == [child.pid]


def test_a_detached_child_does_not_take_a_reused_port_with_it(sandbox):
    """The port is given up together with the registry entry, and only then."""
    supervisor = sandbox.supervisor()
    backend = sandbox.backend(supervisor=supervisor)
    backend._load(TEXT_ALIAS)
    first = child_of(backend)
    port = first.port
    backend.unload(TEXT_ALIAS)

    backend._load(TEXT_ALIAS)
    second = child_of(backend)
    second.port = port                       # as if it had been given the number
    with supervisor.state_lock:
        supervisor._ports_in_use.add(port)
        supervisor._detach_locked(first)     # the late second detach of the old one
    assert port in supervisor._ports_in_use


def test_the_measured_figure_is_booked_the_moment_the_child_is_ready(sandbox):
    """A fresh child at 0 MB is room an eviction would believe it can hand out."""
    real_start = ChildSupervisor.start

    def _start(self, alias, config, needs_vision, fit_target_mb=None):
        # The reading exists before READY, as it does on a real card: the
        # weights are on it by the time /health answers.
        def _measured(pid, max_age_s=None):
            return 4321.0
        self.nvml_pid_mb = _measured
        return real_start(self, alias, config, needs_vision)

    sandbox.monkeypatch.setattr(ChildSupervisor, "start", _start)
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)

    assert child_of(backend).vram_mb == 4321.0
    assert backend.get_registered_models()[0]["vram_mb"] == 4321.0
    assert backend.get_loaded_models()[0]["vram_mb"] == 4321.0

    # Let the teardown see the memory come back.
    child_of(backend)._nvml_pid_mb = lambda pid, max_age_s=None: None


def test_ownership_needs_the_starttime_to_match(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    confirm = sandbox.coordinator.owned[child.pid]["confirm"]
    assert confirm() is True

    # The same PID, born at another moment, is a stranger.
    child.starttime = (child.starttime or 0) + 1
    assert confirm() is False


# =============================================================================
# The ledger
# =============================================================================

def test_the_ledger_follows_the_measured_figure_and_holds_it_when_nvml_is_mute(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    pid = child_of(backend).pid

    backend.receive_nvml_snapshot({"processes": [{"pid": pid, "vram_mb": 1234.0}]})
    assert backend.get_registered_models()[0]["vram_mb"] == 1234.0

    # NVML threw, or is not configured: the last figure stands. Dropping to zero
    # here would invite an eviction to believe the card is empty.
    backend.receive_nvml_snapshot(None)
    assert backend.get_registered_models()[0]["vram_mb"] == 1234.0

    # NVML lists the process but cannot attribute its memory.
    backend.receive_nvml_snapshot({"processes": [
        {"pid": pid, "vram_mb": 0, "vram_unknown": True}]})
    assert backend.get_registered_models()[0]["vram_mb"] == 1234.0

    # The PID is not listed at all: not a memory figure. The reaper decides.
    backend.receive_nvml_snapshot({"processes": []})
    assert backend.get_registered_models()[0]["vram_mb"] == 1234.0

    backend.receive_nvml_snapshot({"processes": [{"pid": pid, "vram_mb": 999.0}]})
    assert backend.get_registered_models()[0]["vram_mb"] == 999.0


def test_the_coordinator_takes_one_snapshot_and_offers_it(sandbox, monkeypatch):
    """The protocol extension itself: one enumeration per collection pass."""
    from services.vram_coordinator import VRAMCoordinator

    coordinator = VRAMCoordinator.__new__(VRAMCoordinator)
    coordinator._backends = {}
    coordinator._owned_pids = {}
    coordinator._owned_lock = threading.Lock()
    coordinator._nvml_cache = None
    coordinator._nvml_cache_at = 0.0
    coordinator._nvml_cache_lock = threading.Lock()
    taken = []

    def _snapshot():
        taken.append(1)
        return {"processes": [{"pid": 4242, "vram_mb": 77.0}]}

    coordinator._get_nvml_memory_info = _snapshot

    received = []

    class Receiving:
        def get_backend_id(self):
            return "receiving"

        def receive_nvml_snapshot(self, info):
            received.append(info)

        def get_registered_models(self):
            return [{"model_id": "fake:1b", "vram_mb": 77.0, "in_use": 0, "last_used": 0}]

    class Plain:
        def get_backend_id(self):
            return "plain"

        def get_registered_models(self):
            return []

    coordinator._backends = {"receiving": Receiving(), "plain": Plain()}
    models = coordinator._collect_all_models()
    assert len(taken) == 1
    assert received == [{"processes": [{"pid": 4242, "vram_mb": 77.0}]}]
    assert [m.model_id for m in models] == ["fake:1b"]


def test_an_owned_pid_is_ours_not_foreign():
    from services.vram_coordinator import VRAMCoordinator

    coordinator = VRAMCoordinator.__new__(VRAMCoordinator)
    coordinator._owned_pids = {}
    coordinator._owned_lock = threading.Lock()
    coordinator._owned_terminators = {}
    coordinator._nvml_available = True
    coordinator._nvml_handle = object()
    coordinator._nvml_cache = None
    coordinator._nvml_cache_at = 0.0
    coordinator._nvml_cache_lock = threading.Lock()

    alive = {"ours": True}
    coordinator.register_owned(4242, 99, "llm child — fake:1b",
                               confirm=lambda: alive["ours"])

    class Proc:
        def __init__(self, pid, used):
            self.pid = pid
            self.usedGpuMemory = used

    fake_pynvml = types.SimpleNamespace(
        nvmlDeviceGetMemoryInfo=lambda h: types.SimpleNamespace(
            total=100 * 1024 ** 2, used=60 * 1024 ** 2, free=40 * 1024 ** 2),
        nvmlDeviceGetComputeRunningProcesses=lambda h: [
            Proc(4242, 30 * 1024 ** 2), Proc(5151, 20 * 1024 ** 2), Proc(6262, None)],
    )
    with_module = {"pynvml": fake_pynvml}
    saved = sys.modules.get("pynvml")
    sys.modules.update(with_module)
    try:
        coordinator._read_proc_cmdline = lambda pid: f"cmd-{pid}"
        info = coordinator._get_nvml_memory_info()
    finally:
        if saved is None:
            sys.modules.pop("pynvml", None)
        else:
            sys.modules["pynvml"] = saved

    by_pid = {p["pid"]: p for p in info["processes"]}
    assert by_pid[4242]["owned"] is True
    assert by_pid[4242]["foreign"] is False
    assert by_pid[4242]["label"] == "llm child — fake:1b"
    assert by_pid[4242]["cmdline"] == "cmd-4242"
    assert by_pid[5151]["foreign"] is True
    # 20 MB of stranger, and not the 30 MB of our own child on top of it.
    assert info["foreign_mb"] == 20.0
    # NVML listed a process without a figure: "unknown" is not "zero".
    assert by_pid[6262]["vram_unknown"] is True
    assert VRAMCoordinator._process_tag(by_pid[4242]) == "[llm child — fake:1b]"

    # Ownership ends the moment the registrar stops confirming it.
    alive["ours"] = False
    assert coordinator._owned_labels() == {}


def test_emergency_reclaim_ends_owned_children_first():
    from services.vram_coordinator import VRAMCoordinator

    coordinator = VRAMCoordinator.__new__(VRAMCoordinator)
    coordinator._owned_pids = {}
    coordinator._owned_lock = threading.Lock()
    coordinator._owned_terminators = {}
    ended = []
    coordinator.register_owned_terminator("llm", lambda reason="": ended.append(reason))
    coordinator.terminate_owned("the sensor is gone")
    assert ended == ["the sensor is gone"]


def test_a_terminator_that_raises_is_not_run_twice():
    """Its arity is decided at registration, from the signature.

    Decided by calling and catching TypeError, a TypeError raised INSIDE the
    termination of a child looked like the wrong number of arguments — and ran
    the whole termination a second time.
    """
    from services.vram_coordinator import VRAMCoordinator

    coordinator = VRAMCoordinator.__new__(VRAMCoordinator)
    coordinator._owned_terminators = {}
    calls = []

    def _raises_inside(reason=""):
        calls.append(reason)
        raise TypeError("something deep inside the termination")

    coordinator.register_owned_terminator("llm", _raises_inside)
    coordinator.terminate_owned("the sensor is gone")
    assert calls == ["the sensor is gone"]

    without_reason = []
    coordinator._owned_terminators = {}
    coordinator.register_owned_terminator("other", lambda: without_reason.append(1))
    coordinator.terminate_owned("ignored")
    assert without_reason == [1]


def test_the_reclaim_ends_our_children_before_it_touches_comfyui(monkeypatch):
    """Order matters: they are the blind spot the reclaim is called to remove.

    ComfyUI's restart takes tens of seconds and is the noisiest step on the
    platform; ending the children first means the card is already ours by the
    time it runs.
    """
    from services.vram_coordinator import VRAMCoordinator
    import services.vram_coordinator as module

    coordinator = VRAMCoordinator.__new__(VRAMCoordinator)
    coordinator._owned_pids = {}
    coordinator._owned_lock = threading.Lock()
    coordinator._owned_terminators = {}
    coordinator._nvml_cache = None
    coordinator._nvml_cache_at = 0.0
    coordinator._nvml_cache_lock = threading.Lock()
    coordinator._get_nvml_memory_info = lambda: None
    coordinator._find_pid_for_port = lambda port: (None, "")

    order = []
    coordinator.register_owned_terminator(
        "llm", lambda reason="": order.append("owned children"))

    class _Sock:
        def settimeout(self, _):
            pass

        def connect_ex(self, _):
            return 0            # ComfyUI answers, so the restart step runs

        def close(self):
            pass

    monkeypatch.setattr(module, "socket", types.SimpleNamespace(
        socket=lambda *a, **k: _Sock(), AF_INET=2, SOCK_STREAM=1))
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: order.append("comfyui restart") or
                        types.SimpleNamespace(returncode=0, stderr=b""))
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    monkeypatch.setattr("services.gpu_admission.get_gpu_admission",
                        lambda: types.SimpleNamespace(
                            forget_resident=lambda reason="": None))

    coordinator.emergency_reclaim_foreign()
    assert order == ["owned children", "comfyui restart"]


def test_a_process_nvml_cannot_attribute_has_no_figure_at_all():
    """"unknown" is not "zero" — and the child's own wait reads None as gone."""
    from services.vram_coordinator import VRAMCoordinator

    coordinator = VRAMCoordinator.__new__(VRAMCoordinator)
    coordinator._nvml_cache = None
    coordinator._nvml_cache_at = 0.0
    coordinator._nvml_cache_lock = threading.Lock()
    coordinator._get_nvml_memory_info = lambda: {"processes": [
        {"pid": 11, "vram_mb": 0.0, "vram_unknown": True},
        {"pid": 22, "vram_mb": 700.0, "vram_unknown": False},
    ]}

    assert coordinator.get_process_vram_mb(11) is None
    assert coordinator.get_process_vram_mb(22) == 700.0
    assert coordinator.get_process_vram_mb(33) is None


def test_the_enumeration_is_reused_for_a_second_or_so():
    """Enumerating walks every process; the supervisor asks several times a second."""
    from services.vram_coordinator import VRAMCoordinator

    coordinator = VRAMCoordinator.__new__(VRAMCoordinator)
    coordinator._nvml_cache = None
    coordinator._nvml_cache_at = 0.0
    coordinator._nvml_cache_lock = threading.Lock()
    walks = []
    coordinator._get_nvml_memory_info = lambda: (
        walks.append(1) or {"processes": [{"pid": 11, "vram_mb": 5.0}]})

    for _ in range(8):
        coordinator.get_process_vram_mb(11)
    assert len(walks) == 1

    # The caller that must be current says so, and refreshes it for the others.
    coordinator.get_process_vram_mb(11, max_age_s=0.0)
    assert len(walks) == 2


# =============================================================================
# What survives this process
# =============================================================================

def test_the_orphan_scan_kills_only_what_it_can_prove_is_ours(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    ours = child_of(backend)

    stranger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        stranger_starttime = read_starttime(stranger.pid)
        state_file = backend._supervisor.state_file
        entries = state_file.read()
        assert [e["pid"] for e in entries] == [ours.pid]
        entries.append({"alias": TEXT_ALIAS, "pid": stranger.pid,
                        "starttime": stranger_starttime, "port": 1})
        entries.append({"alias": TEXT_ALIAS, "pid": ours.pid,
                        "starttime": (ours.starttime or 0) + 1, "port": 2})
        state_file.write(entries)

        killed = scan_and_kill_orphans(state_file)

        assert killed == 1, "only the entry that passed all three checks"
        assert wait_until(lambda: ours.poll() is not None, timeout=5.0)
        assert stranger.poll() is None, "a process without our marker is left alone"
        assert state_file.read() == []
    finally:
        stranger.kill()
        stranger.wait(timeout=5)


def test_a_child_of_another_service_is_never_signalled(sandbox):
    """The marker is compared whole: <parent pid>:<alias>, not the alias alone.

    A second GPU service on the same box runs children for the same models. An
    entry whose marker names a different parent is that service's child, and
    killing it is exactly the accident the marker exists to prevent.
    """
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    ours = child_of(backend)
    state_file = backend._supervisor.state_file

    # The same live child, recorded as if another service's run had spawned it.
    with open(state_file.path, "w", encoding="utf-8") as handle:
        json.dump({"parent_pid": os.getpid() + 1, "written_at": time.time(),
                   "children": [ours.as_state_entry()]}, handle)

    assert scan_and_kill_orphans(state_file) == 0
    time.sleep(0.3)
    assert ours.poll() is None, "another service's child was left alone"
    assert llm_child.owns(ours.pid, ours.starttime, TEXT_ALIAS,
                          parent_pid=os.getpid() + 1) is False
    assert llm_child.owns(ours.pid, ours.starttime, TEXT_ALIAS) is True


def test_a_state_file_without_a_parent_kills_nothing(sandbox):
    """No parent PID, no proof of ownership — and no signal."""
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    ours = child_of(backend)
    state_file = backend._supervisor.state_file
    with open(state_file.path, "w", encoding="utf-8") as handle:
        json.dump({"children": [ours.as_state_entry()]}, handle)

    assert scan_and_kill_orphans(state_file) == 0
    time.sleep(0.3)
    assert ours.poll() is None


def test_the_state_directory_is_refused_inside_the_working_tree(sandbox):
    """The file describes this machine. A checkout is not where that belongs."""
    repo = os.path.dirname(GPU_SERVICE_DIR)
    with pytest.raises(RuntimeError) as refused:
        llm_child.resolve_state_dir(os.path.join(repo, "gpu_service", "state"))
    assert "working tree" in str(refused.value)

    with pytest.raises(RuntimeError) as relative:
        llm_child.resolve_state_dir("state/llm")
    assert "absolute" in str(relative.value)

    assert (llm_child.resolve_state_dir(str(sandbox.state_dir))
            == os.path.realpath(str(sandbox.state_dir)))


def test_the_state_file_names_the_live_children(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    entry = backend._supervisor.state_file.read()[0]
    assert entry["alias"] == TEXT_ALIAS
    assert entry["pid"] == child.pid
    assert entry["starttime"] == child.starttime
    assert entry["port"] == child.port

    backend.unload(TEXT_ALIAS)
    assert backend._supervisor.state_file.read() == []


def test_the_marker_names_this_parent_and_this_alias(sandbox):
    backend = sandbox.backend()
    backend._load(TEXT_ALIAS)
    child = child_of(backend)
    marker = llm_child.read_child_marker(child.pid)
    assert marker == f"{os.getpid()}:{TEXT_ALIAS}"
    assert llm_child.owns(child.pid, child.starttime, TEXT_ALIAS) is True
    assert llm_child.owns(child.pid, child.starttime, "another:alias") is False
    assert llm_child.owns(child.pid, (child.starttime or 0) + 1, TEXT_ALIAS) is False


def test_sigterm_on_the_service_ends_its_children(sandbox, tmp_path):
    """The handler, in a real process, with a real signal."""
    runner = tmp_path / "runner.py"
    runner.write_text(textwrap.dedent(f"""
        import json, os, sys, time
        sys.path.insert(0, {GPU_SERVICE_DIR!r})
        from services.llm_child import ChildSupervisor, install_shutdown_hooks

        supervisor = ChildSupervisor(
            binary={FAKE_SERVER!r},
            port_base={free_port_base()},
            port_count=8,
            socket_timeout_s=600,
            stall_s=30.0,
            state_dir={str(sandbox.state_dir)!r},
            run_orphan_scan=False,
            start_reaper=False,
        )
        install_shutdown_hooks(supervisor.terminate_all)
        child = supervisor.start({TEXT_ALIAS!r}, {model_config(sandbox.model)!r}, False)
        print(json.dumps({{"child": child.pid}}), flush=True)
        while True:
            time.sleep(0.2)
    """), encoding="utf-8")

    service = subprocess.Popen([sys.executable, str(runner)], stdout=subprocess.PIPE,
                               env={**os.environ, "FAKE_LLAMA_MODE": "ready"})
    try:
        line = service.stdout.readline()
        child_pid = json.loads(line)["child"]
        assert llm_child.pid_alive(child_pid)

        os.kill(service.pid, signal.SIGTERM)
        service.wait(timeout=20)
        assert wait_until(lambda: not llm_child.pid_alive(child_pid), timeout=10.0)
    finally:
        with contextlib.suppress(Exception):
            service.kill()
            service.wait(timeout=5)


# =============================================================================
# The surface the routes and the Compare Hub read
# =============================================================================

def test_availability_is_the_binary(sandbox, tmp_path):
    assert sandbox.backend().is_available() is True
    missing = sandbox.backend(binary=str(tmp_path / "no-such-binary"))
    assert missing.is_available() is False
    with pytest.raises(ModelLoadRefused) as refused:
        missing._load(TEXT_ALIAS)
    assert "LLAMA_SERVER_BIN" in str(refused.value)


def test_the_engine_names_itself(sandbox):
    backend = sandbox.backend()
    info = backend.get_engine_info()
    assert info["backend"] == "llama-server"
    assert info["binary"] == FAKE_SERVER
    # `llama-server --version` opens the CUDA device on this build, so the
    # health endpoint answers from the cache and never runs the binary itself.
    assert info["build"] is None

    assert backend.probe_build().startswith("version:")
    assert backend.get_engine_info()["build"].startswith("version:")


def test_the_version_is_never_read_on_a_request_path(sandbox, monkeypatch):
    """Asking the binary initialises CUDA — startup may, a request may not."""
    backend = sandbox.backend()
    ran = []
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: ran.append(a) or types.SimpleNamespace(
                            stdout=b"version: 1 (fake)\n", stderr=b""))

    for _ in range(3):
        backend.get_engine_info()
    assert ran == []

    backend.probe_build()
    assert len(ran) == 1
    backend.probe_build()
    assert len(ran) == 1, "asked once per process, then remembered"


def test_the_model_lists_read_the_registry(sandbox):
    backend = sandbox.backend()
    assert TEXT_ALIAS in backend.get_available_models()
    assert VISION_ALIAS in backend.get_available_models()
    assert any(m["id"] == TEXT_ALIAS and m["available"] for m in backend.get_chat_models())
    assert any(m["id"] == VISION_ALIAS and m["available"] for m in backend.get_vlm_models())

    MODEL_CONFIGS[TEXT_ALIAS]["model_path"] = str(sandbox.tmp_path / "gone.gguf")
    assert TEXT_ALIAS not in backend.get_available_models()


def test_an_unknown_alias_is_refused_by_name(sandbox):
    backend = sandbox.backend()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load("nothing:0b")
    assert "unknown model" in str(refused.value)


def test_a_missing_projector_is_refused_before_anything_starts(sandbox):
    MODEL_CONFIGS[VISION_ALIAS]["mmproj_path"] = str(sandbox.tmp_path / "gone.gguf")
    backend = sandbox.backend()
    with pytest.raises(ModelLoadRefused) as refused:
        backend._load(VISION_ALIAS)
    assert "mmproj not found" in str(refused.value)


def test_the_engine_switch_builds_exactly_one_engine(monkeypatch):
    import services.llm_child_backend as module

    made = []
    monkeypatch.setattr(module, "LLMBackend", lambda: made.append("child") or "child")
    monkeypatch.setattr("services.llm_backend.get_llm_backend",
                        lambda: made.append("inprocess") or "inprocess")

    monkeypatch.setattr("config.LLM_ENGINE", "child")
    module.reset_llm_backend()
    assert module.get_llm_backend() == "child"
    assert made == ["child"]

    monkeypatch.setattr("config.LLM_ENGINE", "inprocess")
    module.reset_llm_backend()
    assert module.get_llm_backend() == "inprocess"
    assert made == ["child", "inprocess"]
    module.reset_llm_backend()


def test_a_route_answers_a_broken_engine_with_a_reason(monkeypatch):
    """A raise from get_llm_backend() reaches the DevServer as "500 Server Error".

    The message that names the variable and its value is exactly what the log
    needs, so it goes into the body — and 503, because nothing was attempted.
    """
    import services.llm_child_backend as backend_module
    import routes.llm_routes as routes
    from flask import Flask

    monkeypatch.setattr("config.LLM_ENGINE", "ollama")
    backend_module.reset_llm_backend()
    app = Flask(__name__)
    app.register_blueprint(routes.llm_bp, url_prefix="/api/llm")
    try:
        with app.test_client() as client:
            response = client.get("/api/llm/health")
    finally:
        backend_module.reset_llm_backend()

    assert response.status_code == 503
    body = response.get_json()
    assert "ollama" in body["error"]
    assert "'child'" in body["error"]


def test_an_engine_nobody_knows_is_refused_by_name(monkeypatch):
    """A misspelling that quietly selects the default hides which engine runs.

    The two differ in whether a crashing model takes the whole service with it,
    which is not something to find out from a journal three days later.
    """
    import services.llm_child_backend as module

    monkeypatch.setattr("config.LLM_ENGINE", "ollama")
    module.reset_llm_backend()
    try:
        with pytest.raises(RuntimeError) as refused:
            module.get_llm_backend()
    finally:
        module.reset_llm_backend()
    message = str(refused.value)
    assert "ollama" in message
    assert "'child'" in message and "'inprocess'" in message


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
