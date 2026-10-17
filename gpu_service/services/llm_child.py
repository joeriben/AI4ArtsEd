"""
Supervised llama-server child processes, owned by the GPU service.

One child per model alias. The service spawns it, measures it per PID through
NVML, reserves for it before it starts, and terminates it — so the VRAM
coordinator stays the single authority over what is resident, exactly as it is
for ComfyUI, with this service as the parent instead of the neighbour.

What lives here is the process side of that relationship and nothing else: the
spawn line, readiness, the ownership marker, the state file, the reaper and the
orphan scan. Inference and the VRAM bookkeeping live in llm_child_backend.py.

Two facts about llama.cpp shape almost everything below.

  * The image encoder's compute buffer is reserved with a return value upstream
    discards (ggml-org/llama.cpp#23422). A failed reserve is silent, the server
    reports itself ready, and the first image dereferences a null buffer. The
    installed build logs `alloc_compute_meta: ... compute buffer size = N MiB`
    only when the buffer was really produced, so that line — and not any
    estimate — is what a vision child is admitted on.
  * A model that aborts on load, or crashes on an image, takes the process it
    runs in. In a child that is one alias; in this service it was every content
    check running at that moment.
"""

import atexit
import base64
import contextlib
import functools
import json
import logging
import os
import signal
import socket
import struct
import subprocess
import threading
import time
import zlib
from collections import deque
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Read from /proc/<pid>/environ to tell our own children from every other
# llama-server on the box. Carries the parent PID and the alias, so an orphan
# from an earlier run of THIS service is recognisable and one belonging to a
# second GPU service is not.
CHILD_ENV_MARKER = "AI4ARTSED_LLM_CHILD"

# llama.cpp reads an environment variable for EVERY flag that is absent from the
# command line (LLAMA_ARG_<FLAG>, plus LLAMA_API_KEY). A value in this service's
# environment would therefore reach into a child's sampling, its context size or
# its authentication without appearing anywhere in the spawn line the log shows.
# The child gets its arguments from build_argv and from nothing else.
CHILD_ENV_STRIP_PREFIXES = ("LLAMA_ARG_",)
CHILD_ENV_STRIP_NAMES = ("LLAMA_API_KEY",)

# Children listen on the loopback interface, whatever the service itself binds
# to. Nothing outside this machine has any business reaching a child, and a
# service bound to 0.0.0.0 would otherwise put an unauthenticated inference
# server on the network.
CHILD_HOST = "127.0.0.1"

# Lines kept per child for the error messages. The whole output also goes to the
# service logger, so this is the tail an exception can carry, not the record.
LOG_RING_LINES = 200
LOG_TAIL_LINES = 20

READINESS_POLL_S = 0.25
# NVML enumerates every process on the card, so it is asked once a second while
# the other three progress signals — log bytes, the pipe, /proc/<pid>/io — are
# read four times a second and cost a read from /proc.
NVML_POLL_S = 1.0
# /health answers 200 the moment the language model is up, and the projector is
# built right after it. This is the window in which the compute-buffer line is
# still allowed to arrive before a vision child is refused for its absence.
VISION_LINE_GRACE_S = 2.0
# The warm-up image, at the edge where the image encoder stops growing. Measured
# on this platform's card (RTX PRO 6000, llama.cpp 59d8402, per-PID nvidia-smi,
# 2026-09-02). The registry holds four vision models; three of them were
# measured — qwen3-vl:2b, :8b and :32b, in that order in each row. qwen3-vl:4b
# was not measured: it lies between the 2b and the 8b in weights and in
# projector size, and is taken to lie inside the range as well, which is an
# inference and not a measurement.
#
#                    2b     8b     32b
#     1024x1024     +66 /  +74 / +160 MB
#     2048x2048    +488 / +550 / +686 MB
#     4096x3072    +488 / +550 / +686 MB
#     6000x4000    +488 / +550 / +686 MB
#
# The figure stops moving above 2048x2048 because the image-token count is
# capped: eight batches of n_tokens_batch = 512, ~4000 image tokens, whatever
# the picture's own size. So this is not "a big image" — it is the size at which
# the encoder has asked for everything it will ever ask for.
VISION_WARMUP_PX = 2048
# What the warm-up says while it hands over the image. Never read by anyone: the
# platform stops reading at the first frame, because by then the image has been
# encoded and the buffers exist, which is the entire purpose.
VISION_WARMUP_PROMPT = "Describe this image."
# How often the warm-up's progress is looked at while it runs. The same quarter
# second the readiness loop uses, for the same reason: it costs a read from
# /proc and an answer from the child, and nothing waits on it.
VISION_WARMUP_POLL_S = 0.25
# A child that exits this quickly with a bind complaint lost a port race; it is
# given the next port once. Everything slower is a real failure to start.
BIND_ERROR_WINDOW_S = 2.0
# Termination is bounded twice over, and both bounds are short on purpose: an
# eviction runs inside the coordinator's request lock, which every other load on
# the platform waits behind. SIGTERM, three seconds, SIGKILL, two seconds, then
# at most two more for the card to stop listing the PID — seven seconds for the
# worst child, one or two for a healthy one.
TERM_WAIT_S = 3.0
KILL_WAIT_S = 2.0
NVML_GONE_WAIT_S = 2.0

# The child's own /slots, asked once per reaper pass for a child with a request
# in flight. THE ONLY PLACE IN THIS ENGINE WITH A READ TIMEOUT, and it is not a
# model call: /slots is answered by posting a METRICS task to the server's task
# queue and waiting for the main loop to hand back the answer (llama.cpp
# 59d8402, tools/server/server-context.cpp:3399 get_slots), so it costs the card
# nothing and a main loop that has stopped turning CANNOT answer it. That
# silence is the evidence this bound is built on, which is why waiting for it
# forever would defeat the purpose.
SLOT_PROBE_TIMEOUT = (1.0, 2.0)

# Lines that mean the child is working on a generation, as opposed to lines it
# writes because a request ARRIVED. The difference is the whole point: every
# arriving request logs "srv params_from_" and "launch_slot_", so a counter of
# all lines is refreshed by the traffic that a wedged alias attracts — the
# safety chain keeps sending checks — and the child would never be given back.
# These four shapes are written while the model is being fed, one per batch and
# one per image slice (llama.cpp 59d8402: tools/server/server-context.cpp:2605
# and :2581, tools/mtmd/mtmd-helper.cpp:367 and :297).
# Both ends of each piece of work are here on purpose. The finishing lines
# alone would leave a single long piece uncovered: the clock would run from the
# END of the previous slice, and a slice that took longer than the bound would
# be cut while the encoder was inside it. Per-slice times measured on this card
# are three orders of magnitude below the bound (96-399 ms against 180 s), so
# this is headroom rather than a close call — and headroom is what it should be,
# because a bigger image, a busier card or a slower build all move that figure.
WORK_LINE_MARKERS = (
    "prompt processing progress",
    "prompt processing done",
    # mtmd writes "encoding <image|audio> slice..." and "decoding <name> batch
    # i/n" when it starts, and the two below when it finishes (llama.cpp
    # 59d8402, tools/mtmd/mtmd-helper.cpp:358, :287, :367, :297).
    "encoding ",
    "decoding ",
    "slice encoded in",
    "decoded (batch",
)
# Shutdown ends all children at once rather than one after another, so the whole
# sweep fits well inside systemd's stop timeout (45 s). An overrun is not
# survivable in a useful sense: TimeoutStopFailureMode=abort then sends SIGABRT
# for a core dump, and after TimeoutAbortSec the control group is SIGKILLed with
# the children still holding whatever they held.
TERMINATE_ALL_BOUND_S = 20.0
# Control-plane reads (/health, /props, /slots). These are not model calls: they
# answer immediately or not at all, and a poll loop that could block forever on
# one would defeat the very stall bound it implements.
CONTROL_TIMEOUT = (2.0, 5.0)

# Batch sizes as the in-process engine ran them.
BATCH_SIZE = 512
UBATCH_SIZE = 512


class ChildState(str, Enum):
    """Where a child stands. Anything but READY counts as absent."""
    LOADING = "loading"
    READY = "ready"
    DYING = "dying"


class ChildStartupError(RuntimeError):
    """A child could not be brought up, and the message says how far it got.

    Carries the exit code (None while the process is still alive) and the last
    lines it wrote, because on this path those two are the whole diagnosis: a
    model file the build cannot read, a projector the build has no loader for,
    a port taken, or a card with no room left for the encoder's buffer.
    """

    def __init__(self, alias: str, message: str, exit_code: Optional[int] = None,
                 log_tail: Optional[List[str]] = None):
        self.alias = alias
        self.exit_code = exit_code
        self.log_tail = list(log_tail or [])
        super().__init__(message)


# =============================================================================
# /proc readers — ownership rests on these two, never on a port or a model path
# =============================================================================

def read_starttime(pid: int) -> Optional[int]:
    """Field 22 of /proc/<pid>/stat: when this PID was born, in clock ticks.

    A PID alone is not an identity — the number is reused, and killing a
    stranger that inherited it is exactly the accident this file must not have.
    The pair (pid, starttime) is one, for as long as the process lives.

    The comm field holds the executable name in parentheses and may itself
    contain spaces and parentheses, so the split is on the LAST ')'.
    """
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            raw = handle.read()
    except OSError:
        return None
    try:
        after_comm = raw.rsplit(b")", 1)[1].split()
        # after_comm[0] is field 3 (state), so field 22 is index 19.
        return int(after_comm[19])
    except (IndexError, ValueError):
        return None


def read_child_marker(pid: int) -> Optional[str]:
    """The AI4ARTSED_LLM_CHILD value of a live PID, or None.

    /proc/<pid>/environ is readable for our own user's processes, which is the
    only case that matters: a child of ours runs as us.
    """
    try:
        with open(f"/proc/{pid}/environ", "rb") as handle:
            raw = handle.read()
    except OSError:
        return None
    prefix = (CHILD_ENV_MARKER + "=").encode("ascii")
    for entry in raw.split(b"\0"):
        if entry.startswith(prefix):
            return entry[len(prefix):].decode("utf-8", "replace")
    return None


def read_io_rchar(pid: int) -> Optional[int]:
    """Bytes this PID has read through read()-like calls, per /proc/<pid>/io.

    The WEAKEST of the three progress signals, and the one to trim last rather
    than first. It counts syscalls only: llama.cpp maps the weights by default,
    so the copy phase arrives through page faults and never shows here at all.
    What it does cover is the beginning — the header and metadata reads before
    the mapping — and a load with mmap turned off, where it is the only signal
    that moves for minutes.

    What carries the rest: the bytes the child WRITES (its load bar is printed
    as dots with no newline, so the byte count moves while the line count does
    not), and its NVML figure, which grows as the buffers are allocated.
    """
    try:
        with open(f"/proc/{pid}/io", "rb") as handle:
            for line in handle:
                if line.startswith(b"rchar:"):
                    return int(line.split()[1])
    except (OSError, IndexError, ValueError):
        return None
    return None


def pid_alive(pid: int) -> bool:
    """True while the PID exists at all. Says nothing about whose it is."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Alive, and owned by somebody else — which already means it is not ours.
        return True
    except OSError:
        return False


def owns(pid: int, starttime: Optional[int], alias: Optional[str] = None,
         parent_pid: Optional[int] = None) -> bool:
    """True only for a live process that is one of OUR llama-server children.

    Three independent conditions, all required: the PID is alive, it was born at
    the moment we recorded, and its environment carries our marker — the whole
    marker, `<parent pid>:<alias>`, compared as one string. Matching the alias
    alone would accept a second GPU service's child for the same model, which is
    exactly the process this must never signal.

    `parent_pid` is which parent the marker has to name. A live check leaves it
    unset and means this process; the orphan scan passes the parent PID recorded
    in the state file, because the run that spawned those children is the run
    that ended.
    """
    if not pid_alive(pid):
        return False
    if starttime is not None and read_starttime(pid) != starttime:
        return False
    marker = read_child_marker(pid)
    if marker is None:
        return False
    parent = os.getpid() if parent_pid is None else int(parent_pid)
    if alias is not None:
        return marker == f"{parent}:{alias}"
    return marker.startswith(f"{parent}:")


# =============================================================================
# Where the state file may live
# =============================================================================

def resolve_state_dir(configured: str, repo_root: Optional[str] = None) -> str:
    """The child state directory, checked. Raises RuntimeError on a bad value.

    Two conditions, and both are about where a file lands rather than what is in
    it. The path must be absolute — a relative one resolves against whatever
    directory the service happened to be started from, which for a systemd unit
    is not the one anybody had in mind. And it must lie outside the working
    tree: the file records the PIDs and ports of this machine, is rewritten on
    every registry change, and inside a checkout it would sit one `git add` away
    from a repository.

    The check runs here rather than at `config` import time on purpose. A bad
    value must cost the LLM engine and nothing else — importing `config` is the
    first line of every backend on this service, and a RuntimeError there takes
    image generation, the safety chain and the health endpoint with it.
    """
    if not str(configured).strip():
        raise RuntimeError("LLM_CHILD_STATE_DIR is empty — no directory to write to")
    path = os.path.expanduser(str(configured).strip())
    if not os.path.isabs(path):
        raise RuntimeError(
            f"LLM_CHILD_STATE_DIR must be an absolute path; {configured!r} is "
            f"relative and would follow the service's working directory")
    resolved = os.path.realpath(path)
    root = os.path.realpath(repo_root or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if resolved == root or resolved.startswith(root + os.sep):
        raise RuntimeError(
            f"LLM_CHILD_STATE_DIR resolves inside the working tree ({resolved}). "
            f"The child state file records the PIDs and ports of this machine and "
            f"must not be committable. Point it outside {root}, or leave it unset "
            f"for ~/.cache/ai4artsed/.")
    return resolved


# =============================================================================
# The spawn line
# =============================================================================

def build_argv(config: Dict[str, Any], port: int, alias: str, binary: str,
               socket_timeout_s: int, host: str = CHILD_HOST,
               fit_target_mb: Optional[int] = None) -> List[str]:
    """The exact command line for one child. Pure, so a test can assert it.

    Every flag is a decision:

      -ngl / --mmproj       MODEL_CONFIGS remains the registry; n_gpu_layers -1
                            is llama-cpp-python's "everything", which this build
                            spells 'all'.
      -np 1                 one slot. Two requests for the same alias queue in
                            the child instead of interleaving on one context.
      -n -1                 no output cap. Explicit BECAUSE it is the default:
                            llama.cpp reads LLAMA_ARG_N_PREDICT for every flag
                            absent from the command line, so an environment
                            variable could otherwise cap every answer this
                            platform produces without appearing anywhere.
      --slots               the per-slot endpoint, which the platform reads to
                            see whether a cancelled request really let go of the
                            child. Enabled by default in this build; written out
                            so a changed default cannot take it away silently.
      -b / -ub 512          as the in-process engine ran them.
      -c is NOT passed      llama.cpp reads the window out of the model when
                            -c is absent (its default is 0, "loaded from
                            model"), which is the only number that is a
                            property of the weights rather than of a table.
      --fit on              and it is what makes that affordable: llama.cpp
                            sizes the cache it actually allocates to the memory
                            the device has, down to --fit-ctx at the least,
                            instead of reserving the whole window up front. A
                            fixed -c reserved 82 GB for a 16 GB model on a card
                            three processes share (measured 2026-09-09).
      --fit-target N        the room llama-server leaves free on the card. The
                            caller derives it from what the coordinator says
                            this load may take, so the neighbour that holds
                            memory right now — ComfyUI, another child — is what
                            bounds this one, and no typed number is.
      --no-context-shift    a reading that reaches the ceiling must END there and
                            say so, not silently drop its own beginning.
      --jinja               each model's own GGUF template, instead of the seven
                            hardcoded formats the Python handlers offered.
      --reasoning-format none  thoughts stay in `content`, so the </think>
                            partition the platform already does still applies.
      --reasoning on        the switch itself, and the only one: it sets
                            enable_reasoning = 1 AND the template default
                            enable_thinking = "true" (common/arg.cpp:3066), and
                            the server then thinks for every template that
                            supports it (server-context.cpp:899-900). Without
                            it the decision is left to whatever each GGUF's own
                            template does when that variable is undefined —
                            which for the model this platform runs its pipeline
                            roles on is: no thinking at all.
      --reasoning-budget -1  no bound on the thinking itself. The build's
                            default, written out for the same reason as -n: it
                            is read from LLAMA_ARG_THINK_BUDGET when the flag is
                            absent (common/arg.cpp:3084), and a 0 there would
                            end every thought at its first token, everywhere,
                            without appearing in the spawn line.
      -cram 0               the host-RAM prompt cache defaults to 8 GiB PER
                            INSTANCE. With one instance per alias that is real
                            memory for a cache this platform does not use.
      --no-webui            nothing here serves a browser.
      --host 127.0.0.1      never on the network.
      -to                   the child's own socket read/write timeout, default
                            600 s. Set to the configured ceiling because a long
                            reading is a normal event here and 0 does not
                            disable it in cpp-httplib.
    """
    n_gpu_layers = config.get("n_gpu_layers", -1)
    layers = "all" if int(n_gpu_layers) < 0 else str(int(n_gpu_layers))

    argv = [binary, "-m", str(config["model_path"])]
    mmproj = config.get("mmproj_path")
    if mmproj:
        argv += ["--mmproj", str(mmproj)]
    argv += [
        "-n", "-1",
        "-ngl", layers,
        "-np", "1",
        "--slots",
        "-b", str(BATCH_SIZE),
        "-ub", str(UBATCH_SIZE),
        "--fit", "on",
    ]
    if fit_target_mb is not None:
        argv += ["--fit-target", str(int(fit_target_mb))]
    argv += [
        "--no-context-shift",
        "--jinja",
        "--reasoning-format", "none",
        "--reasoning", "on",
        "--reasoning-budget", "-1",
        "-cram", "0",
        "--no-webui",
        "--host", host,
        "--port", str(int(port)),
        "--alias", alias,
        "-to", str(int(socket_timeout_s)),
    ]
    return argv


@functools.lru_cache(maxsize=2)
def warmup_image_data_url(size: int = VISION_WARMUP_PX) -> str:
    """A PNG of `size` x `size`, built here, as a data URL.

    Built rather than shipped: an image on disk is one more thing an install can
    be missing, and the load path would then be deciding what to do about a
    missing asset at the worst possible moment. What the picture SHOWS makes no
    difference to what it costs — llama.cpp patchifies the pixels and caps the
    token count — so this is a diagonal pattern in eight-bit grey, which
    stb_image expands to three channels on the way in.

    Cheap on purpose: one 256-byte row rotated per line, then one zlib pass, so
    a load pays a few milliseconds and every load after the first pays nothing.
    """
    base = bytes(range(256)) * (size // 256 + 2)
    raw = b"".join(b"\x00" + base[y % 256:y % 256 + size] for y in range(size))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           # 8-bit greyscale, no interlace.
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


# =============================================================================
# One child
# =============================================================================

class InFlightRequest:
    """One stream a child is serving, with the clock that belongs to IT.

    The child-level clock cannot answer for a single request. With one slot,
    llama-server finishes one answer, releases the slot and starts the next, so
    a request whose consumer has stopped draining its socket is invisible to
    every child-level signal: the work lines move, the decode counter moves, the
    next caller's frames arrive. Meanwhile that request holds a refcount, and
    the refcount holds the whole model against every eviction — with nothing
    left that will ever end it, because the child is perfectly healthy.

    So each request carries its own last-frame time, and the reaper can end one
    request without touching the child the others are being served by.
    """

    def __init__(self, child: "SupervisedChild", close: Callable[[], None]):
        self.child = child
        self._close = close
        # Frames this request has actually received. A request that has had
        # none is not judged by this clock at all: with one slot, waiting for
        # the slot IS what a queued request does, and cutting it would end
        # perfectly good requests under load.
        self.frames = 0
        self.last_frame_at = time.monotonic()
        self.ended_reason: Optional[str] = None

    def note_progress(self) -> None:
        """A frame arrived on this stream. Stamps the request AND the child."""
        self.frames += 1
        self.last_frame_at = time.monotonic()
        self.child.note_progress()

    def end(self, reason: str) -> None:
        """Close this request's connection so its read loop lets go.

        Nothing is signalled to the child: it is serving other people, and its
        model is worth more than this one answer. The caller's read raises, the
        refcount comes back with it, and the reason travels with the error.
        """
        self.ended_reason = reason
        try:
            self._close()
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM-CHILD %s] Could not close a stalled request: %s",
                           self.child.alias, e)


class SupervisedChild:
    """One llama-server process: its output, its readiness, its end.

    The bookkeeping fields (`state`, `in_use`, `vram_mb`, `last_used`) belong to
    the supervisor's lock, not to this object's own — a child is handed out and
    given back under one lock together with the registry it lives in, and a
    second lock here would let those two disagree about whether it is busy.
    """

    def __init__(self, alias: str, config: Dict[str, Any], port: int, *,
                 binary: str, socket_timeout_s: int, stall_s: float,
                 load_ceiling_s: float = 900.0,
                 warmup_stall_s: float = 60.0,
                 nvml_pid_mb: Optional[Callable[[int], Optional[float]]] = None,
                 host: str = CHILD_HOST,
                 fit_target_mb: Optional[int] = None):
        self.alias = alias
        self.fit_target_mb = fit_target_mb
        self.config = config
        self.port = port
        self.binary = binary
        self.socket_timeout_s = socket_timeout_s
        self.stall_s = stall_s
        self.load_ceiling_s = float(load_ceiling_s)
        self.warmup_stall_s = float(warmup_stall_s)
        self.host = host
        self._nvml_pid_mb = nvml_pid_mb

        self.pid: Optional[int] = None
        self.starttime: Optional[int] = None
        self.started_at: float = 0.0
        self.argv: List[str] = []

        # Supervisor-owned bookkeeping; see the class docstring.
        self.state: ChildState = ChildState.LOADING
        self.in_use: int = 0
        self.vram_mb: float = 0.0
        self.last_used: float = 0.0

        # Set once, by whichever path withdraws it from the coordinator.
        self.withdrawn: bool = False
        # Why the supervisor ended it, so the request that was reading from it
        # can say what happened rather than only that the connection broke.
        self.end_reason: Optional[str] = None
        # Stamped by the request path on every frame that arrives on any stream
        # this child is serving — content, reasoning and keep-alive alike. It is
        # what tells a long answer from a wedged one.
        self.last_progress_at: float = 0.0
        # The reaper's view of the three generation signals between its passes.
        self._gen_marks: Optional[tuple] = None
        self._gen_moved_at: float = 0.0

        # The streams this child is serving right now, each with its own clock.
        self._in_flight: List[InFlightRequest] = []
        self._in_flight_lock = threading.Lock()

        self._proc: Optional[subprocess.Popen] = None
        self._log: deque = deque(maxlen=LOG_RING_LINES)
        self._log_lock = threading.Lock()
        self._log_seq = 0
        # Only the lines that mean work on a generation; see WORK_LINE_MARKERS.
        self._work_seq = 0
        # Bytes, not lines: llama.cpp writes its load bar as dots with no
        # newline at all (LOG_CONT), so a line counter stands still for the
        # whole of the slowest part of a cold load.
        self._log_bytes = 0
        # Set by the reader thread the moment the line goes past. Looking for
        # them in the ring buffer afterwards would miss both: a model load
        # writes far more than 200 lines.
        self._saw_vision_buffer = False
        self._saw_bind_error = False
        self._reader: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ spawn

    def spawn(self, parent_pid: Optional[int] = None) -> None:
        """Start the process and begin reading its output. Does not wait."""
        self.argv = build_argv(self.config, self.port, self.alias, self.binary,
                               self.socket_timeout_s, host=self.host,
                               fit_target_mb=self.fit_target_mb)
        env = {key: value for key, value in os.environ.items()
               if not (key.startswith(CHILD_ENV_STRIP_PREFIXES)
                       or key in CHILD_ENV_STRIP_NAMES)}
        env[CHILD_ENV_MARKER] = f"{parent_pid or os.getpid()}:{self.alias}"

        logger.info("[LLM-CHILD %s] spawning on port %s: %s",
                    self.alias, self.port, " ".join(self.argv))
        self._proc = subprocess.Popen(
            self.argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            close_fds=True,
        )
        self.pid = self._proc.pid
        self.started_at = time.time()
        # Read before anything else can be read: the pair (pid, starttime) is
        # the identity every later decision rests on, and it has to be taken
        # while we know the process is the one we just started.
        self.starttime = read_starttime(self.pid)
        self._reader = threading.Thread(
            target=self._read_output, name=f"llm-child-{self.alias}", daemon=True)
        self._reader.start()

    def _read_output(self) -> None:
        """Forward every line to the journal, keep the tail, count the bytes.

        Read in chunks rather than by line, for two reasons. The load bar is
        written as bare dots with no newline, so readline() would block on it
        for minutes and report no progress for the very phase that takes the
        longest. And the >64 KB a loading llama-server writes would otherwise
        fill the pipe and block the writer, which looks exactly like a model
        that stopped loading.
        """
        stream = self._proc.stdout if self._proc else None
        if stream is None:
            return
        pending = b""
        try:
            while True:
                chunk = stream.read1(4096)
                if not chunk:
                    break
                # Progress is measured here, before any line is complete.
                self._log_bytes += len(chunk)
                pending += chunk
                while b"\n" in pending:
                    raw, _, pending = pending.partition(b"\n")
                    self._note_line(raw.decode("utf-8", "replace").rstrip("\r"))
            if pending:
                self._note_line(pending.decode("utf-8", "replace").rstrip("\r"))
        except Exception as e:  # noqa: BLE001 — a reader that dies must not kill the child
            logger.warning("[LLM-CHILD %s] output reader stopped: %s", self.alias, e)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def note_progress(self) -> None:
        """Something arrived on a stream this child is serving. Called per frame.

        Per FRAME, and never on arrival: a request that has only just been sent
        is not evidence of anything, and stamping it here would let a wedged
        child be kept alive by the requests it is failing to answer — which is
        exactly the traffic it gets, because the safety chain goes on sending
        checks to the same alias.
        """
        self.last_progress_at = time.monotonic()

    def begin_request(self, close: Callable[[], None]) -> InFlightRequest:
        """Register a stream about to be read, and hand back its own clock."""
        request = InFlightRequest(self, close)
        with self._in_flight_lock:
            self._in_flight.append(request)
        return request

    def end_request(self, request: InFlightRequest) -> None:
        with self._in_flight_lock:
            if request in self._in_flight:
                self._in_flight.remove(request)

    def in_flight(self) -> List[InFlightRequest]:
        with self._in_flight_lock:
            return list(self._in_flight)

    def slot_counter(self) -> Optional[int]:
        """Tokens this child says it has decoded, or None if it could not say.

        Asked of the child's own /slots. Two things come back in one call and
        both are needed: the COUNTER, which grows while the model is being
        decoded whether or not anybody is reading the answer, and the ANSWER
        ITSELF, which a wedged server cannot give — /slots is served by the main
        task loop, so silence here means the loop has stopped turning.

        None is returned for every failure, and a None never counts as progress
        and never counts as movement either (see marks_moved): a probe that
        fails once must not make the next successful one look like work.
        """
        if self.port is None:
            return None
        try:
            import requests
            response = requests.get(self.base_url() + "/slots",
                                    timeout=SLOT_PROBE_TIMEOUT)
            if response.status_code != 200:
                return None
            slots = response.json()
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(slots, list):
            return None
        total = 0
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            # This build nests the counter one level down and in a list of one
            # (server-context.cpp:405 to_json); older and newer shapes put it
            # flat. Both are read, neither is required.
            token = slot.get("next_token")
            if isinstance(token, list) and token:
                token = token[0]
            if isinstance(token, dict) and isinstance(token.get("n_decoded"), int):
                total += token["n_decoded"]
            elif isinstance(slot.get("n_decoded"), int):
                total += slot["n_decoded"]
        return total

    def generation_marks(self) -> tuple:
        """The two signals that say a child with a request in flight is working.

        Frames arriving on any of its streams, and what its own slots report.
        Nothing else: bytes off the pipe and /proc rchar move during a
        generation for reasons that have nothing to do with it, its NVML figure
        is flat while it decodes, and a counter of ALL its log lines is moved by
        every request that ARRIVES — which is exactly the traffic a wedged alias
        gets, so it would keep the wedge alive under load.

        Prefill is covered twice over, and it has to be, because no frame is
        written while a prompt or an image is being processed: the work lines
        (WORK_LINE_MARKERS) are written per batch and per slice, and the slots
        answer at all only while the main loop is turning.

        The consumer cannot fake it either way. A client that stops reading
        applies backpressure to the socket and the frames stop, but the server
        goes on decoding into an unbounded result queue
        (server-queue.cpp:319 server_response::send), so the slot counter keeps
        growing and a healthy child is never cut for a slow reader.
        """
        return (self.last_progress_at, self._work_seq, self.slot_counter())

    def _note_line(self, line: str) -> None:
        """One finished line: the two flags, the ring buffer, the journal."""
        lowered = line.lower()
        if ("alloc_compute_meta" in lowered
                and "compute buffer size" in lowered
                and "cuda" in lowered):
            self._saw_vision_buffer = True
        if any(marker in lowered for marker in WORK_LINE_MARKERS):
            self._work_seq += 1
        if "bind" in lowered and ("address already in use" in lowered
                                  or "couldn't bind" in lowered
                                  or "could not bind" in lowered
                                  or "failed to bind" in lowered):
            self._saw_bind_error = True
        with self._log_lock:
            self._log.append(line)
            self._log_seq += 1
        logger.info("[LLM-CHILD %s] %s", self.alias, line)

    # -------------------------------------------------------------- readiness

    def wait_ready(self, needs_vision: bool) -> None:
        """Block until /health answers 200, or refuse with a reason.

        Four ways this ends badly and each says which: the process exited (exit
        code plus its last lines), nothing moved for the stall bound, the whole
        attempt outlasted the ceiling, or the vision buffer never appeared in
        the log although this alias carries a projector.

        The two time bounds do different work and neither replaces the other.
        The STALL bound asks whether anything is happening at all — four signals
        answer it, and a load is left alone while any of them moves: bytes off
        the child's pipe (the load bar is dots without a newline), the byte
        count /proc reports it has read from disk, its own NVML figure, and the
        finished lines. The CEILING is the wall clock of one attempt, and it
        exists because a child can produce all the progress in the world and
        still never become healthy — a chatty one would otherwise hold the
        plant-wide load lock, and with it every content check, forever.
        """
        import requests

        url = f"http://{self.host}:{self.port}/health"
        session = requests.Session()
        started = time.monotonic()
        marks = self._progress_marks(force_nvml=True)
        last_change = started
        next_nvml = started + NVML_POLL_S
        try:
            while True:
                code = self._proc.poll() if self._proc else None
                if code is not None:
                    # The reader is a thread of its own: without this, the last
                    # lines — which are the diagnosis — are still in the pipe.
                    self.drain(1.0)
                    raise ChildStartupError(
                        self.alias,
                        f"{self.alias}'s server exited during load (exit {code})",
                        exit_code=code, log_tail=self.log_tail())

                try:
                    response = session.get(url, timeout=CONTROL_TIMEOUT)
                    if response.status_code == 200:
                        break
                except Exception:
                    # Not yet listening, or still loading. Either way the two
                    # bounds below decide how long that may last.
                    pass

                now = time.monotonic()
                take_nvml = now >= next_nvml
                if take_nvml:
                    next_nvml = now + NVML_POLL_S
                current = self._progress_marks(force_nvml=take_nvml,
                                               previous=marks)
                if current != marks:
                    marks, last_change = current, now
                elif now - last_change >= self.stall_s:
                    tail = self.log_tail()
                    self.terminate("no progress while loading")
                    raise ChildStartupError(
                        self.alias,
                        f"{self.alias}'s server wrote nothing, read nothing off "
                        f"disk and moved no GPU memory for {self.stall_s:.0f}s "
                        f"and is still not answering /health — killed",
                        exit_code=self._proc.poll() if self._proc else None,
                        log_tail=tail)

                if now - started >= self.load_ceiling_s:
                    tail = self.log_tail()
                    self.terminate("load ceiling reached")
                    raise ChildStartupError(
                        self.alias,
                        f"{self.alias}'s server has been starting for "
                        f"{self.load_ceiling_s:.0f}s without answering /health "
                        f"— the per-attempt ceiling, which holds even while the "
                        f"child keeps showing progress within its {self.stall_s:.0f}s "
                        f"stall bound — killed",
                        exit_code=self._proc.poll() if self._proc else None,
                        log_tail=tail)

                time.sleep(READINESS_POLL_S)
        finally:
            session.close()

        if needs_vision:
            self._await_vision_line()

    def _await_vision_line(self) -> None:
        """The compute-buffer line, or a refusal — with a moment's grace first.

        /health answers 200 as soon as the language model is up, and the image
        encoder is built immediately after. Waiting a moment here costs a child
        that never builds one two seconds; leaving it out costs a perfectly good
        vision model that happened to answer /health first.

        Polled rather than drained: the output reader ends only with the child,
        so joining it here would wait for the very process this is about to
        admit.
        """
        deadline = time.monotonic() + VISION_LINE_GRACE_S
        while not self._saw_vision_buffer and time.monotonic() < deadline:
            time.sleep(READINESS_POLL_S)
        if self._saw_vision_buffer:
            return
        tail = self.log_tail()
        free_note = self._free_vram_note()
        self.terminate("vision compute buffer was never reserved")
        raise ChildStartupError(
            self.alias,
            f"{self.alias} reports itself ready but never logged the image "
            f"encoder's compute buffer, so that buffer was not reserved on "
            f"the GPU; the first image would dereference it{free_note} — "
            f"refused instead",
            exit_code=None, log_tail=tail)

    def warm_up_vision(self) -> str:
        """Encode one image at the token cap, while the room is still reserved.

        The compute-buffer line this child was admitted on covers the reserve
        llama.cpp does at load. It does not cover what the encoder allocates
        when it is first FED: measured on this card that is another 488 to 686
        MB, arriving on the first image and never released afterwards.

        Whose room that is decides where this belongs. On the first user image
        it is nobody's: the coordinator's promise for this load ended when the
        weights landed, the card may have filled with a render since, and
        llama.cpp reserves those buffers with a return value it discards — the
        failure this whole engine exists to keep away from a live request. Doing
        it here, before start() lets go, means the load takes what the model
        really costs and takes it once.

        Nothing is capped. One frame is read and the connection closed, because
        the image is encoded during prefill and the buffers exist by the time
        the first token comes back; the child was never told to stop writing,
        the platform simply stopped reading — the same move the per-request
        clock makes. There is no read timeout either, so a child that wedges
        here is ended by the reaper's child-level clock, which is why start()
        counts this as a request in flight before it calls.

        Returns the note the load line carries. Raises ChildStartupError if the
        image took the child down, because that is precisely what the first user
        image would have done.
        """
        before = self._nvml_reading(0.0)
        started = time.monotonic()
        size = f"{VISION_WARMUP_PX}x{VISION_WARMUP_PX}"

        detail = ""
        for attempt in (1, 2):
            detail = self._warmup_attempt()
            if not detail:
                break
            exit_code = self.reap()
            if exit_code is not None:
                raise ChildStartupError(
                    self.alias,
                    f"{self.alias} went down while encoding the warm-up image "
                    f"(exit {exit_code}), which is what the first image from a "
                    f"reader would have done instead"
                    + (f" — {detail}" if detail else ""),
                    exit_code=exit_code, log_tail=self.log_tail())
            if attempt == 1:
                logger.warning("[LLM-CHILD %s] the warm-up image was not encoded "
                               "(%s) — asking once more while the room is still "
                               "reserved", self.alias, detail)

        if detail:
            # FAIL CLOSED. The child is alive and its compute-buffer line is in
            # the log, so every rail in front of the load held — and none of them
            # covers what is missing here. Admitting it would put a vision child
            # on the card whose encoder buffers are NOT allocated and whose
            # booked figure says they are, so the first reader's image would ask
            # for those 500-700 MB against a reservation that ended at this
            # load, on a card that may have filled with a render since, through
            # the one allocation llama.cpp does not report the failure of. The
            # alias is refused instead; a refused check is recoverable.
            self.terminate("the warm-up image was never encoded")
            raise ChildStartupError(
                self.alias,
                f"{self.alias} did not encode the warm-up image in two attempts "
                f"({detail}); a vision child is admitted only with the encoder's "
                f"buffers really on the card — killed and refused",
                exit_code=self.poll(), log_tail=self.log_tail())

        took = time.monotonic() - started
        after = self._nvml_reading(0.0)
        if before is None or after is None:
            return f" — image encoder warmed at {size} in {took:.1f}s"
        return (f" — image encoder warmed at {size}: {before:.0f}MB -> "
                f"{after:.0f}MB (+{after - before:.0f}MB) in {took:.1f}s")

    def _warmup_attempt(self) -> str:
        """One image. Returns "" when it was encoded, or why it was not.

        BOUNDED BY PROGRESS, AND BOUNDED SHORT. The request itself carries a
        connect timeout and no read timeout, as every model call from here does
        — but this one is made with the plant-wide load lock and the admission
        slot held, so a child wedged in its own encoder stops every other load
        on the platform for as long as the bound allows. The reaper's clock
        would eventually end it at LLM_CHILD_STALL_S; this one is the same
        instrument (the same marks, the same marks_moved) set to the length of
        the work actually being waited for.

        The request runs in a thread of its own because iter_lines() blocks,
        and when the bound is reached the socket is shut down from here (see
        unblock_stream: CLOSING it from here would wait on the reader's own
        buffer lock and hang the bound inside its own escape hatch); the reader
        then raises and lets go.
        """
        import requests

        payload = {
            "messages": [{"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": warmup_image_data_url()}},
                {"type": "text", "text": VISION_WARMUP_PROMPT},
            ]}],
            "stream": True,
        }
        outcome: Dict[str, Any] = {"detail": "", "response": None}

        def run() -> None:
            response = None
            try:
                # Connect timeout only, as everywhere a model is called here.
                response = requests.post(self.base_url() + "/v1/chat/completions",
                                         json=payload, stream=True,
                                         timeout=(5.0, None))
                outcome["response"] = response
                if response.status_code != 200:
                    outcome["detail"] = f"the child answered {response.status_code}"
                    return
                for line in response.iter_lines():
                    self.note_progress()
                    if line and line.startswith(b"data:"):
                        return
                outcome["detail"] = "the stream ended without a single frame"
            except Exception as e:  # noqa: BLE001
                outcome["detail"] = f"{type(e).__name__}: {e}"
            finally:
                if response is not None:
                    with contextlib.suppress(Exception):
                        response.close()

        worker = threading.Thread(target=run, daemon=True,
                                  name=f"warmup-{self.alias}")
        worker.start()

        marks = self.generation_marks()
        moved_at = time.monotonic()
        while True:
            worker.join(VISION_WARMUP_POLL_S)
            if not worker.is_alive():
                return outcome["detail"]
            current = self.generation_marks()
            if marks_moved(marks, current):
                marks, moved_at = current, time.monotonic()
                continue
            if time.monotonic() - moved_at < self.warmup_stall_s:
                continue
            # Nothing arrived, nothing was written, the slots did not move.
            # The socket is shut down rather than closed (see unblock_stream:
            # closing it from here would wait on the reader's own buffer lock),
            # then the child is ended, which closes the far side as well.
            response = outcome.get("response")
            if response is not None:
                unblock_stream(response)
            self.terminate("no progress while encoding the warm-up image")
            worker.join(5.0)
            raise ChildStartupError(
                self.alias,
                f"{self.alias} stopped working while encoding the warm-up "
                f"image: no frame, no work line and no movement in its own "
                f"slots for {self.warmup_stall_s:.0f}s, with the plant-wide "
                f"load lock held — killed and refused",
                exit_code=self.poll(), log_tail=self.log_tail())

    def _progress_marks(self, force_nvml: bool,
                        previous: Optional[tuple] = None) -> tuple:
        """The four signals as one comparable tuple.

        NVML is only read when it is due (it enumerates every process on the
        card); on the other polls the previous figure is carried forward, so a
        signal that is simply not being asked never reads as movement.

        rchar counts every read() the child makes, the health polls of this very
        loop included — a few dozen bytes each, four times a second. Taken raw
        it would report progress for a stuck child for as long as anybody asks
        it how it is, so it is compared in whole mebibytes: a load that reads at
        all reads hundreds of them, and this loop could not produce one in a day.
        With the default memory-mapped load it stops moving after the header,
        which is why it is the third signal and not the first.
        """
        rchar = read_io_rchar(self.pid) if self.pid is not None else None
        rchar = None if rchar is None else rchar >> 20
        if force_nvml or previous is None:
            reading = self._nvml_reading()
        else:
            reading = previous[3]
        return (self._log_bytes, self._log_seq, rchar, reading)

    def _nvml_reading(self, max_age_s: Optional[float] = None) -> Optional[float]:
        """This child's GPU memory per NVML. `max_age_s=0.0` forces a fresh read.

        The coordinator serves an enumeration up to a second old, which is what
        a progress signal polled four times a second should have — and the wrong
        thing entirely for "is the memory back yet": a figure taken before the
        kill answers that question with the state of the world beforehand.
        """
        if self._nvml_pid_mb is None or self.pid is None:
            return None
        try:
            return self._nvml_pid_mb(self.pid, max_age_s)
        except Exception:
            return None

    def _free_vram_note(self) -> str:
        try:
            from services.vram_coordinator import get_vram_coordinator
            free_mb = get_vram_coordinator().get_free_vram_mb(use_cache=False)
            return f" (free at load: {free_mb:.0f}MB)"
        except Exception:
            return ""

    # ------------------------------------------------------------ termination

    def terminate(self, reason: str = "") -> bool:
        """End the child. Bounded at ~7 s worst case, 1-2 s typically.

        SIGTERM first, which llama-server handles and answers by closing its
        listener and returning. SIGKILL after TERM_WAIT_S, then KILL_WAIT_S for
        the kernel. Then — and this is the step that matters to the coordinator
        — wait for NVML to stop listing the PID: the process being reaped and
        its memory being back are not the same moment, and a ledger that
        believed the first would hand the room out twice.

        The bounds are deliberately short because an eviction runs inside the
        coordinator's request lock: every load on the platform waits behind this
        method, and the coordinator re-reads free VRAM after each child it ends.

        Returns True only when the process is gone AND the card no longer
        carries it. A survivor is logged with its PID and left to the reaper.
        """
        if self._proc is None:
            return True
        self.signal_term(reason)
        return self.finish_termination(time.monotonic() + TERM_WAIT_S
                                       + KILL_WAIT_S + NVML_GONE_WAIT_S)

    def signal_term(self, reason: str = "") -> None:
        """SIGTERM and nothing else. The waiting belongs to the caller.

        Shutdown signals every child before it waits for any of them: done one
        after another, a service with four children would spend four times the
        termination bound inside systemd's stop timeout.
        """
        proc = self._proc
        if proc is None:
            return
        if reason:
            # Kept on the child: the request still reading from it learns only
            # that its connection broke, and this is the sentence that says why.
            self.end_reason = reason
            logger.info("[LLM-CHILD %s] terminating (%s)", self.alias, reason)
        if proc.poll() is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                self.reap()
            except Exception as e:  # noqa: BLE001
                logger.warning("[LLM-CHILD %s] SIGTERM failed: %s", self.alias, e)

    def finish_termination(self, deadline: float) -> bool:
        """Wait out an already-signalled child, escalating, until `deadline`.

        The deadline is monotonic and shared when several children are ended at
        once, so the whole sweep is bounded rather than each child in turn.
        """
        proc = self._proc
        if proc is None:
            return True

        gone = self._wait_exit(min(TERM_WAIT_S, max(0.0, deadline - time.monotonic())))
        if not gone:
            logger.warning("[LLM-CHILD %s] PID %s ignored SIGTERM — SIGKILL",
                           self.alias, self.pid)
            try:
                proc.kill()
            except ProcessLookupError:
                # Already gone; wait() below turns it from a zombie into an
                # exit code. os.kill(pid, 0) is true for a zombie, so a child
                # nobody reaps never stops looking alive.
                gone = self.reap() is not None
            except Exception as e:  # noqa: BLE001
                logger.error("[LLM-CHILD %s] SIGKILL failed: %s", self.alias, e)
            if not gone:
                gone = self._wait_exit(
                    min(KILL_WAIT_S, max(0.0, deadline - time.monotonic())))

        if not gone:
            logger.error("[LLM-CHILD %s] PID %s survived SIGKILL — handed to the "
                         "reaper; its memory is still booked", self.alias, self.pid)
            return False

        # Its own bound, and never more than what is left of the shared one: a
        # process that exited quickly must not spend the rest of a shutdown
        # sweep waiting for the driver.
        return self._wait_nvml_gone(
            min(deadline, time.monotonic() + NVML_GONE_WAIT_S))

    def _wait_exit(self, timeout_s: float) -> bool:
        try:
            self._proc.wait(timeout=max(0.0, timeout_s))
            return True
        except subprocess.TimeoutExpired:
            return False
        except Exception:  # noqa: BLE001
            return self._proc.poll() is not None

    def reap(self) -> Optional[int]:
        """The exit code of a child that has ended, reaping it in passing.

        Popen.poll() collects the zombie, and every path that learns a child is
        gone goes through here for exactly that reason: an unreaped child keeps
        answering os.kill(pid, 0), so a supervisor that trusted that signal
        would wait for a process the kernel is only holding open for us.
        """
        if self._proc is None:
            return None
        try:
            return self._proc.poll()
        except Exception:  # noqa: BLE001
            return None

    def _wait_nvml_gone(self, deadline: Optional[float] = None) -> bool:
        """True once NVML no longer lists the PID (or cannot say)."""
        if self._nvml_pid_mb is None or self.pid is None:
            return True
        if deadline is None:
            deadline = time.monotonic() + NVML_GONE_WAIT_S
        while True:
            # Fresh every time: the whole point of this loop is that the answer
            # changes while it runs.
            if self._nvml_reading(0.0) is None:
                return True
            if time.monotonic() >= deadline:
                logger.error("[LLM-CHILD %s] PID %s is gone but still holds GPU "
                             "memory", self.alias, self.pid)
                return False
            time.sleep(READINESS_POLL_S)

    # ------------------------------------------------------------------ state

    def poll(self) -> Optional[int]:
        return self._proc.poll() if self._proc else None

    def drain(self, timeout: float = 1.0) -> None:
        """Wait for the output reader to finish, so the tail is the whole tail.

        A process that has just exited still has lines in the pipe, and the
        reader is a separate thread: reading the tail without this gives an
        error message that stops one line short of the reason.
        """
        reader = self._reader
        if reader is not None and reader.is_alive():
            reader.join(timeout=timeout)

    def exit_code_after(self, timeout: float = 0.5) -> Optional[int]:
        """The exit code, giving a dying process a moment to be one.

        A child that crashes mid-answer closes its socket before the kernel has
        reaped it, so the first poll() after a broken stream can still say None
        — and "the process is still running" is the wrong half of the diagnosis
        to put in front of somebody.
        """
        code = self.poll()
        if code is None:
            with contextlib.suppress(Exception):
                self._proc.wait(timeout=timeout)
            code = self.poll()
        if code is not None:
            self.drain(1.0)
        return code

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def log_tail(self, lines: int = LOG_TAIL_LINES) -> List[str]:
        with self._log_lock:
            return list(self._log)[-lines:]

    @property
    def log_seq(self) -> int:
        return self._log_seq

    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def as_state_entry(self) -> Dict[str, Any]:
        return {
            "alias": self.alias,
            "pid": self.pid,
            "starttime": self.starttime,
            "port": self.port,
            "started_at": self.started_at,
        }



def unblock_stream(response: Any) -> None:
    """Make a reader that is blocked inside this response let go, from outside.

    CLOSING IT DOES NOT DO THAT, and it looks as if it does. urllib3 closes the
    buffered file first (`HTTPResponse.close` -> `http.client.HTTPResponse.
    _close_conn` -> `BufferedReader.close`), and that call wants the very lock
    the reader holds while it sits in `read()`: the closer waits for the reader,
    the reader waits for bytes that are not coming, and the thread that was
    supposed to end the stream is the one that hangs. Measured here on
    2026-09-03, with the warm-up's own bound as the thread that hung.

    `HTTPResponse.shutdown()` (urllib3 2.4+) takes no lock: it shuts the socket
    down for reading, the blocked recv() returns at once, and the reader closes
    the response in its own `finally`, where closing is safe because nothing is
    reading any more. Where it is unavailable this does nothing at all — better
    a reader that waits for its child to be ended than a caller that deadlocks.
    """
    raw = getattr(response, "raw", None)
    shutdown = getattr(raw, "shutdown", None)
    if shutdown is None:
        return
    with contextlib.suppress(Exception):
        shutdown()


def marks_moved(before: tuple, after: tuple) -> bool:
    """Did any signal in a pair of generation_marks actually move?

    Not `!=`, because one of the three is allowed to be missing. A /slots probe
    that timed out is None, and None must count neither as progress nor as
    movement: compared with `!=`, a probe that fails on one pass and answers on
    the next would refresh the stall clock without a token having been decoded,
    which is precisely the shape this bound exists to catch.
    """
    if before[0] != after[0] or before[1] != after[1]:
        return True
    return (before[2] is not None and after[2] is not None
            and before[2] != after[2])

# =============================================================================
# The state file — the only thing that survives this process
# =============================================================================

class ChildStateFile:
    """Who our children were, for the next start of this service.

    One record per child — alias, PID, the moment it was born, its port — plus
    the PID of the service that spawned them, which is what lets the next run
    tell its predecessor's children from a second GPU service's. Written on
    every registry change and read exactly once, at startup, by the orphan scan.

    It lives outside the working tree (see LLM_CHILD_STATE_DIR): it describes
    the running state of this machine and has no business in a repository.
    """

    def __init__(self, path: str):
        self.path = str(path)
        self._lock = threading.Lock()

    def write(self, entries: List[Dict[str, Any]]) -> None:
        payload = {"parent_pid": os.getpid(), "written_at": time.time(),
                   "children": entries}
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                tmp = f"{self.path}.tmp.{os.getpid()}"
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                # Replace, never truncate-and-write: a reader arriving mid-write
                # would otherwise find half a file and kill nothing at all.
                os.replace(tmp, self.path)
            except OSError as e:
                logger.warning("[LLM] Could not write %s: %s", self.path, e)

    def read_payload(self) -> Dict[str, Any]:
        """The whole file, including the PID of the run that wrote it."""
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            logger.warning("[LLM] Could not read %s: %s", self.path, e)
            return {}
        return payload if isinstance(payload, dict) else {}

    def read(self) -> List[Dict[str, Any]]:
        children = self.read_payload().get("children")
        return list(children) if isinstance(children, list) else []

    def clear(self) -> None:
        self.write([])


def scan_and_kill_orphans(state_file: ChildStateFile) -> int:
    """Kill what an earlier run of this service left behind. Nothing else.

    Every entry has to pass all of `owns()` before it is signalled: alive, born
    at the recorded moment, and carrying the marker of the run that wrote the
    file, for the alias the file names. An entry that fails any of them is left
    alone and said so — the PID has been reused, or the process belongs to a
    second GPU service, and killing it would be this file doing the very thing
    it exists to prevent.

    The marker is checked TWICE for the same reason: between the SIGTERM and the
    SIGKILL the process may exit and its PID be handed to somebody else, and the
    second signal is the one that leaves no room for a mistake.
    """
    payload = state_file.read_payload()
    parent_pid = payload.get("parent_pid")
    entries = payload.get("children")
    entries = entries if isinstance(entries, list) else []
    if not isinstance(parent_pid, int):
        if entries:
            logger.warning("[LLM] Orphan scan: the state file names no parent PID "
                           "— every entry is left alone")
        state_file.clear()
        return 0

    killed = 0
    for entry in entries:
        pid = entry.get("pid")
        alias = entry.get("alias")
        starttime = entry.get("starttime")
        if not isinstance(pid, int):
            continue
        if not owns(pid, starttime, alias, parent_pid=parent_pid):
            if pid_alive(pid):
                logger.info("[LLM] Orphan scan: PID %s (%s) is alive but is not "
                            "ours — left alone", pid, alias)
            continue
        logger.warning("[LLM] Orphan scan: killing leftover child %s (PID %s)",
                       alias, pid)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except OSError as e:
            logger.error("[LLM] Orphan scan: SIGTERM for PID %s failed: %s", pid, e)
            continue
        deadline = time.monotonic() + TERM_WAIT_S
        while pid_alive(pid) and time.monotonic() < deadline:
            time.sleep(READINESS_POLL_S)
        if pid_alive(pid):
            if owns(pid, starttime, alias, parent_pid=parent_pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            else:
                logger.info("[LLM] Orphan scan: PID %s stopped being ours between "
                            "the two signals — left alone", pid)
        killed += 1
    state_file.clear()
    return killed


# =============================================================================
# The supervisor
# =============================================================================

class ChildSupervisor:
    """The registry of live children, and everything that changes it.

    `state_lock` guards `_children` and every counter on a child, and is never
    held across a spawn, an HTTP call or a wait(). The backend takes the same
    lock for the compound operations that must not be split — handing a child
    out and raising its refcount, refusing an eviction because that refcount is
    non-zero.
    """

    def __init__(self, *, binary: str, port_base: int, port_count: int,
                 socket_timeout_s: int, stall_s: float, state_dir: str,
                 load_ceiling_s: float = 900.0,
                 warmup_stall_s: float = 60.0,
                 nvml_pid_mb: Optional[Callable[..., Optional[float]]] = None,
                 nvml_invalidate: Optional[Callable[[], None]] = None,
                 reaper_interval_s: float = 5.0,
                 run_orphan_scan: bool = True, start_reaper: bool = True):
        self.binary = binary
        self.port_base = int(port_base)
        self.port_count = int(port_count)
        self.socket_timeout_s = int(socket_timeout_s)
        self.stall_s = float(stall_s)
        self.load_ceiling_s = float(load_ceiling_s)
        self.warmup_stall_s = float(warmup_stall_s)
        # Loopback, always: see CHILD_HOST. The service's own bind address has
        # no say in it.
        self.host = CHILD_HOST
        self.nvml_pid_mb = nvml_pid_mb
        # How to tell the coordinator that its enumeration is out of date. It
        # serves one up to a second old, and the moment after a child's memory
        # comes back is exactly when a second-old answer is the wrong one.
        self.nvml_invalidate = nvml_invalidate
        self.reaper_interval_s = float(reaper_interval_s)
        # Why acquire() last came back empty for an alias, so the request can
        # report the death it met instead of a load that never happened.
        self._deaths: Dict[str, Dict[str, Any]] = {}

        # The state file is written outside state_lock, and out-of-order writes
        # are dropped by sequence number rather than prevented by holding it.
        self._state_write_lock = threading.Lock()
        self._state_seq = 0
        self._state_written = 0

        self.state_lock = threading.RLock()
        self._children: Dict[str, SupervisedChild] = {}
        self._dying: List[SupervisedChild] = []
        self._ports_in_use: set = set()

        # Checked here rather than at config import: a bad value costs the LLM
        # engine, and leaves every other backend on this service running.
        self.state_dir = resolve_state_dir(state_dir)
        self.state_file = ChildStateFile(os.path.join(self.state_dir, "llm_children.json"))
        if run_orphan_scan:
            try:
                killed = scan_and_kill_orphans(self.state_file)
                if killed:
                    logger.warning("[LLM] Orphan scan ended %d leftover child(ren)", killed)
            except Exception as e:  # noqa: BLE001
                logger.error("[LLM] Orphan scan failed: %s", e)

        self._on_register: Optional[Callable[[SupervisedChild], None]] = None
        self._on_unregister: Optional[Callable[[SupervisedChild], None]] = None

        self._stop = threading.Event()
        # True while terminate_all is signalling and collecting; see
        # _ensure_reaper.
        self._sweeping = False
        self._reaper: Optional[threading.Thread] = None
        self._reaper_wanted = bool(start_reaper)
        if start_reaper:
            self._ensure_reaper()

    # ------------------------------------------------------------ owner hooks

    def set_owner_hooks(self, on_register: Optional[Callable[[SupervisedChild], None]],
                        on_unregister: Optional[Callable[[SupervisedChild], None]]) -> None:
        """Where a child is announced to, and withdrawn from, the coordinator."""
        self._on_register = on_register
        self._on_unregister = on_unregister

    # ------------------------------------------------------------------ ports

    def _free_port(self, exclude: Optional[set] = None) -> int:
        """A port in this instance's derived range that nothing is listening on.

        Bind-tested without SO_REUSEADDR, so a port still in TIME_WAIT is passed
        over rather than handed to a child that would then fail to bind.
        """
        exclude = exclude or set()
        with self.state_lock:
            taken = set(self._ports_in_use) | exclude
        for offset in range(self.port_count):
            port = self.port_base + offset
            if port in taken:
                continue
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.bind((self.host, port))
                return port
            except OSError:
                continue
            finally:
                probe.close()
        raise ChildStartupError(
            "-", f"no free port in {self.port_base}-{self.port_base + self.port_count - 1}")

    # ------------------------------------------------------------------ start

    def start(self, alias: str, config: Dict[str, Any], needs_vision: bool,
              fit_target_mb: Optional[int] = None) -> SupervisedChild:
        """Spawn a child for this alias and return it once it answers /health.

        The registration happens immediately after Popen, before readiness: the
        whole load window is then covered by the ownership marker, and NVML's
        view of a child reading 20 GB off disk never says "foreign".
        """
        self._ensure_reaper()
        tried_ports: set = set()
        last_error: Optional[ChildStartupError] = None
        for attempt in (1, 2):
            port = self._free_port(exclude=tried_ports)
            tried_ports.add(port)
            child = SupervisedChild(
                alias, config, port,
                binary=self.binary, socket_timeout_s=self.socket_timeout_s,
                stall_s=self.stall_s, load_ceiling_s=self.load_ceiling_s,
                warmup_stall_s=self.warmup_stall_s,
                nvml_pid_mb=self.nvml_pid_mb, host=self.host,
                fit_target_mb=fit_target_mb)
            try:
                child.spawn()
            except OSError as e:
                raise ChildStartupError(
                    alias, f"could not start {self.binary} for {alias}: {e}") from e

            self._register(child)
            try:
                child.wait_ready(needs_vision)
            except ChildStartupError as e:
                started_within = time.time() - child.started_at
                self._forget(child, terminate=child.is_alive(), reason="startup failed")
                bind_race = (attempt == 1 and child._saw_bind_error
                             and started_within <= BIND_ERROR_WINDOW_S)
                if bind_race:
                    logger.warning("[LLM-CHILD %s] port %s was taken between the "
                                   "probe and the bind — trying the next one",
                                   alias, port)
                    last_error = e
                    continue
                raise
            except BaseException:
                self._forget(child, terminate=True, reason="startup aborted")
                raise

            # One NVML reading at the moment of readiness, so a fresh child is
            # never listed at 0 MB: the ledger's next pass may be seconds away,
            # and an eviction reading 0 would take it for free.
            measured = child._nvml_reading(0.0)
            with self.state_lock:
                child.state = ChildState.READY
                child.last_used = time.time()
                if measured is not None:
                    child.vram_mb = float(measured)
            self._write_state()

            note = ""
            if needs_vision:
                # READY first, and counted as in use: the reaper's child-level
                # clock watches exactly that pair, and the warm-up is both the
                # first image this child sees and the likeliest place for it to
                # wedge. Without the two, a child stuck in its own encoder would
                # hold this load — and the plant-wide load lock — with nothing
                # left to end it.
                with self.state_lock:
                    child.in_use += 1
                try:
                    note = child.warm_up_vision()
                except ChildStartupError:
                    self._forget(child, terminate=child.is_alive(),
                                 reason="the warm-up image took it down")
                    raise
                finally:
                    self.release(child)
                grown = child._nvml_reading(0.0)
                with self.state_lock:
                    if grown is not None:
                        child.vram_mb = float(grown)
                self._write_state()

            logger.info("[LLM] %s is ready on port %s (PID %s)%s",
                        alias, port, child.pid, note)
            return child

        raise last_error if last_error is not None else ChildStartupError(
            alias, f"{alias} could not be started")

    def _register(self, child: SupervisedChild) -> None:
        with self.state_lock:
            self._children[child.alias] = child
            self._ports_in_use.add(child.port)
            # The alias has a live child again; an older child's death is not
            # something any later request may be handed as its cause.
            self._deaths.pop(child.alias, None)
        self._write_state()
        if self._on_register is not None:
            try:
                self._on_register(child)
            except Exception as e:  # noqa: BLE001
                logger.warning("[LLM] Could not announce %s to the coordinator: %s",
                               child.alias, e)

    def _detach_locked(self, child: SupervisedChild) -> None:
        """Take a child out of the registry. THE CALLER HOLDS state_lock.

        Marking it DYING and removing it are one step, and every decision that
        leads to an eviction has to be inside the same critical section — see
        `unload`. Between a released lock and this line, `acquire` would hand
        the child to a request that is then killed under it.

        The port is given up only together with the registry entry. Two paths
        can detach the same child — a reaping pass and an unload that crossed —
        and by the time the second one arrives the number may already belong to
        a child that has just been started on it.
        """
        if self._children.get(child.alias) is child:
            del self._children[child.alias]
            self._ports_in_use.discard(child.port)
        child.state = ChildState.DYING

    def _withdraw(self, child: SupervisedChild) -> None:
        """Tell the coordinator this child is gone. Once, whoever gets here first.

        A reaping pass and an unload can both end the same child, and the
        coordinator's owned-PID registry is keyed by PID: withdrawing twice
        would take out the entry of whatever child has since been given that
        number by the kernel.
        """
        with self.state_lock:
            if child.withdrawn:
                return
            child.withdrawn = True
        if self._on_unregister is None:
            return
        try:
            self._on_unregister(child)
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] Could not withdraw %s from the coordinator: %s",
                           child.alias, e)

    def _finish_forget(self, child: SupervisedChild, *, terminate: bool,
                       reason: str) -> bool:
        """The half of a removal that must NOT hold the lock: signals and waits."""
        self._write_state()

        gone = True
        if terminate:
            gone = child.terminate(reason)
            if not gone:
                with self.state_lock:
                    if child not in self._dying:
                        self._dying.append(child)
                # It still holds memory and a PID: the next start of this
                # service has to know about it too, and somebody has to notice
                # when it finally lets go.
                self._write_state()
                self._ensure_reaper()
        if gone:
            self._withdraw(child)
            # terminate() has already waited for the card to let go, so there is
            # nothing left to wait for here — but the coordinator serves an
            # enumeration up to a second old, and that copy still lists this
            # PID. The next load would read our own ended child as somebody
            # else's memory.
            self._invalidate_nvml()
        return gone

    def _forget(self, child: SupervisedChild, *, terminate: bool, reason: str) -> bool:
        """Drop a child from the registry, and end it if it is still running."""
        with self.state_lock:
            self._detach_locked(child)
        return self._finish_forget(child, terminate=terminate, reason=reason)

    # ----------------------------------------------------------- handing out

    def acquire(self, alias: str) -> Optional[SupervisedChild]:
        """A READY child with its refcount raised, or None. One critical section.

        The increment and the handout are the same moment on purpose: an
        eviction that read the refcount between them would find 0 and take the
        child out from under the caller.

        And the process is asked whether it is still there before it is handed
        out. READY is a record of what was true when the child answered /health;
        a crash makes it false without touching it, and the reaper's next pass
        can be seconds away. In those seconds every request for this alias used
        to be given a port nothing listens on and fail in no time at all — one
        crash, then a stream of instant 500s until a sweep noticed. A dead child
        is taken out here, and the caller loads a new one: this is a liveness
        check before use, not a retry of a request that failed.
        """
        dead: Optional[SupervisedChild] = None
        with self.state_lock:
            child = self._children.get(alias)
            if child is None or child.state is not ChildState.READY:
                return None
            # reap(), not is_alive(): it collects the zombie in the same breath,
            # and an unreaped child goes on answering every liveness signal.
            # Accepted gap: CPython's Popen._internal_poll answers None while
            # another thread holds _waitpid_lock, so a child being examined by a
            # concurrent exit_code_after can be handed out once — a window of
            # microseconds, costing one failed request.
            if child.reap() is None:
                child.in_use += 1
                child.last_used = time.time()
                # A living child answers for this alias, so nothing that died
                # before it is anybody's cause any more. Left standing, that
                # record outlives the crash by hours and is handed to the next
                # request that finds no child for an entirely different reason.
                self._deaths.pop(alias, None)
                return child
            self._detach_locked(child)
            dead = child
            self._deaths[alias] = {
                "exit_code": child.poll(),
                "log_tail": child.log_tail(),
                # Monotonic, and read: it is what tells a death written for the
                # attempt now under way from one left by an earlier child.
                "at": time.monotonic(),
                "reason": child.end_reason,
                "pid": child.pid,
                "starttime": child.starttime,
            }

        logger.error("[LLM-CHILD %s] PID %s had died before this request; taken "
                     "out of the registry and a new one will be started: %s",
                     dead.alias, dead.pid, " | ".join(dead.log_tail(5)))
        self._write_state()
        self._withdraw(dead)
        self._settle_dead(dead)
        return None

    def take_death(self, alias: str,
                   after: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """The death acquire() last met for this alias, removed as it is read.

        `after` is a monotonic mark taken before the caller's own attempt began,
        and a record older than it is dropped rather than returned. A record may
        only ever explain the attempt it was written during: the alias is the
        key, aliases outlive children by hours, and a request that finds no
        child because an eviction took it would otherwise be answered with the
        exit code and the last lines of a process that died at breakfast.
        """
        with self.state_lock:
            death = self._deaths.pop(alias, None)
        if death is None or after is None:
            return death
        if death.get("at", 0.0) >= after:
            return death
        logger.info("[LLM] Dropping a death record for %s (PID %s) that predates "
                    "this request; it explains nothing about it",
                    alias, death.get("pid"))
        return None

    def _settle_dead(self, child: SupervisedChild) -> None:
        """Wait for the card to let go of a corpse, then re-read it fresh.

        NEVER under state_lock. The request that follows is the whole reason the
        corpse was detached, and it begins by asking the coordinator for room:
        while NVML still lists the exited PID, that room reads as taken, the
        child is no longer in the registry so nothing can be evicted to make it,
        and the load is refused over a dead process's memory — with ComfyUI
        asked to give up VRAM for it. Bounded like every other wait here; on a
        timeout the load goes ahead and the PID is named.
        """
        if not child._wait_nvml_gone():
            logger.error("[LLM-CHILD %s] PID %s is gone but the card still lists "
                         "%.0fMB for it — the next load will see it as taken",
                         child.alias, child.pid, child.vram_mb)
        self._invalidate_nvml()

    def _invalidate_nvml(self) -> None:
        """Tell the coordinator its cached enumeration is out of date."""
        if self.nvml_invalidate is None:
            return
        try:
            self.nvml_invalidate()
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] Could not refresh the NVML reading: %s", e)

    def retire(self, child: SupervisedChild, reason: str,
               settle: bool = True) -> bool:
        """Take a child that has already ended out of the registry, at once.

        Called from the request path the moment a failure names a process that
        is gone. Leaving it to the reaper means the NEXT request is handed the
        same dead child — and that request is usually a content check, sent
        milliseconds later by whoever just lost this one.

        Nothing is signalled and nothing is retried here: the request that met
        the death still fails, with the exit code and the child's last lines.

        A child that is no longer in the registry belongs to whoever took it out
        — a termination in another thread parked it in `_dying` precisely
        because the card still carries it, and withdrawing it from under that
        thread would make our own memory count as a stranger's.

        `settle` is false only where the caller already holds a fresh reading in
        which this PID no longer appears; there is nothing left to wait for, and
        waiting would happen inside the coordinator's own pass.

        THE PROCESS MUST BE GONE, and an unknown exit code is not gone. Nothing
        is signalled on this path and nothing is filed in `_dying`, so a living
        child dropped here would be unregistered AND unreachable: shutdown
        signals what stands in the registry, this child no longer would, and it
        would hold its model until the next start's orphan scan found it.
        """
        with self.state_lock:
            if self._children.get(child.alias) is not child:
                return False
        if child.reap() is None:
            logger.warning("[LLM-CHILD %s] PID %s is still running — it keeps its "
                           "place (%s)", child.alias, child.pid, reason)
            return False
        logger.warning("[LLM-CHILD %s] taken out of the registry: %s",
                       child.alias, reason)
        self._forget(child, terminate=False, reason=reason)
        if settle:
            self._settle_dead(child)
        return True

    def release(self, child: SupervisedChild) -> None:
        with self.state_lock:
            child.in_use = max(0, child.in_use - 1)
            child.last_used = time.time()

    def get(self, alias: str) -> Optional[SupervisedChild]:
        with self.state_lock:
            return self._children.get(alias)

    def snapshot(self) -> List[SupervisedChild]:
        with self.state_lock:
            return list(self._children.values())

    # -------------------------------------------------------------- unloading

    def unload(self, alias: str, force: bool = False) -> bool:
        """Take a child off the card. False when it is busy, absent, or survived.

        The refcount check and the removal are ONE critical section. Split in
        two, a request arriving between them would be handed a child that is
        already being killed: `acquire` would still find it READY, raise its
        refcount, and get a port that stops answering a moment later. Inside one
        section the two orders are the only ones possible — the request comes
        first and the eviction is refused, or the eviction comes first and the
        request finds nothing to acquire.

        `force` is the operator's escape hatch for a wedged child whose refcount
        never came back; it skips the busy check and nothing else.
        """
        with self.state_lock:
            child = self._children.get(alias)
            if child is None:
                return False
            if child.in_use > 0 and not force:
                logger.info("[LLM] Not unloading %s: %d request(s) in flight",
                            alias, child.in_use)
                return False
            if child.in_use > 0:
                logger.warning("[LLM] Force-unloading %s with %d request(s) in "
                               "flight — they will fail", alias, child.in_use)
            self._detach_locked(child)
        return self._finish_forget(child, terminate=True, reason="unload")

    def terminate_all(self, reason: str = "shutdown",
                      bound_s: float = TERMINATE_ALL_BOUND_S) -> None:
        """End every child at once. The service must leave no llama-server behind.

        All of them are signalled first and collected afterwards, against one
        shared deadline. Done child by child, four children would cost four
        times the termination bound — and this runs inside systemd's stop
        timeout, which ends in a hard kill and orphaned children if it is
        exceeded.
        """
        self.stop()  # the reaper must not race the sweep for the same children
        self._sweeping = True
        try:
            self._terminate_all(reason, bound_s)
        finally:
            self._sweeping = False

    def _terminate_all(self, reason: str, bound_s: float) -> None:
        children = self.snapshot()
        if not children:
            self.state_file.clear()
            return

        with self.state_lock:
            for child in children:
                self._detach_locked(child)
        self._write_state()

        for child in children:
            child.signal_term(reason)

        deadline = time.monotonic() + float(bound_s)
        survivors = []
        for child in children:
            if child.finish_termination(deadline):
                self._withdraw(child)
            else:
                survivors.append(child)

        if survivors:
            with self.state_lock:
                for child in survivors:
                    if child not in self._dying:
                        self._dying.append(child)
            logger.error("[LLM] %d child(ren) outlasted the %.0fs shutdown bound: %s",
                         len(survivors), bound_s,
                         ", ".join(f"{c.alias} (PID {c.pid})" for c in survivors))
            self._write_state()
            # Stood down for the sweep, brought back for what the sweep left:
            # after an emergency reclaim the service goes on serving, and
            # nothing else would ever take these off the books. The only call
            # allowed to re-arm from inside a sweep, and the last thing it does.
            self._ensure_reaper(force=True)
            return
        self.state_file.clear()

    def stop(self) -> None:
        """Stand the reaper down. `start` brings it back if there is work again."""
        self._stop.set()

    def _ensure_reaper(self, force: bool = False) -> None:
        """Run the reaper thread, starting or restarting it as needed.

        `terminate_all` stops it so that a sweep and a reaping pass never work
        on the same children at once — and that call is not always a shutdown:
        the coordinator's emergency reclaim ends every child and the service
        goes on serving. Whoever spawns the next child brings the reaper back.

        `force` belongs to the sweep alone. While one is running, nothing else
        may bring the reaper back: the sweep signalled every child, a child that
        outlasts the wait is filed as a survivor, and filing one goes through
        the same path that restarts the reaper — which would put a reaping pass
        back on the very children the sweep is still collecting.
        """
        if not self._reaper_wanted:
            return
        if self._sweeping and not force:
            return
        with self.state_lock:
            self._stop.clear()
            if self._reaper is not None and self._reaper.is_alive():
                return
            self._reaper = threading.Thread(target=self._reap_forever,
                                            name="llm-child-reaper", daemon=True)
            self._reaper.start()

    # ----------------------------------------------------------------- ledger

    def update_ledger(self, by_pid: Optional[Dict[int, Optional[float]]]) -> None:
        """Book each child by what NVML measured for its PID, in one pass.

        Three states, and they mean three different things:

          * no reading at all (NVML threw, or is not configured) — keep the last
            figure. A ledger that dropped to 0 here would invite an eviction to
            believe the card is empty.
          * the PID is listed but its memory is not (`usedGpuMemory` None, which
            NVML returns for a process it cannot attribute) — keep the last
            figure and say so, once per occurrence.
          * the PID is absent — the child is gone. Not a memory figure at all,
            and not something to leave standing either: for as long as a dead
            child holds its place, its memory is shown twice over — booked under
            loaded_models and counted as a stranger's in foreign_mb, which is
            what raises an unexpected-foreign warning naming our own child.
        """
        if by_pid is None:
            return
        for child in self.snapshot():
            if child.pid is None:
                continue
            if child.pid not in by_pid:
                if child.state is ChildState.READY and child.reap() is not None:
                    logger.error("[LLM] %s (PID %s) is no longer on the card and "
                                 "its process is gone", child.alias, child.pid)
                    # settle=False: this reading is the caller's own, it was
                    # taken a moment ago, and this PID is not in it.
                    self.retire(child, "its process ended and the card no longer "
                                       "lists it", settle=False)
                continue
            measured = by_pid[child.pid]
            if measured is None:
                logger.warning("[LLM] NVML lists PID %s (%s) without a memory "
                               "figure — keeping %.0fMB", child.pid, child.alias,
                               child.vram_mb)
                continue
            with self.state_lock:
                child.vram_mb = float(measured)

    # ----------------------------------------------------------------- reaper

    def _reap_forever(self) -> None:
        while not self._stop.wait(self.reaper_interval_s):
            try:
                self.reap_once()
            except Exception as e:  # noqa: BLE001
                logger.warning("[LLM] Reaper pass failed: %s", e)

    def reap_once(self) -> None:
        """Notice children that ended by themselves, and survivors that finally did.

        A child that crashed is not a bookkeeping event that can wait: while it
        stands in the registry the coordinator believes its memory is still
        booked, and the next request would be handed a port nothing listens on.
        """
        # The survivors first, and deliberately: what follows can wait seconds
        # per child — the settle below is bounded at two, a slots probe at
        # three — and a child that outlasted SIGKILL still holds its model on
        # the card. Every pass it spends behind those waits is a pass in which
        # its memory is booked to nobody and available to no one.
        self._sweep_survivors()

        for child in self.snapshot():
            if self._stop.is_set():
                # A shutdown sweep has taken over. It works on the same
                # children, and anything done here from now on either races it
                # or re-arms the reaper it just stood down.
                return
            code = child.reap()
            if code is None:
                continue
            logger.error("[LLM-CHILD %s] exited on its own (exit %s): %s",
                         child.alias, code, " | ".join(child.log_tail(5)))
            self._forget(child, terminate=False, reason="")
            # The same settle the request path does, for the same reason. A
            # crash with no request in flight is found HERE, and the next
            # content check arrives milliseconds later: while NVML still lists
            # the exited PID its memory reads as taken, the child is out of the
            # registry so nothing can be evicted to make room, and a 20GB model
            # that is already gone refuses the next load and has ComfyUI asked
            # to give up VRAM for it. Off the request path, so the bounded wait
            # costs that request nothing.
            self._settle_dead(child)

        if self._stop.is_set():
            return
        self._end_stalled_generations()

    def _sweep_survivors(self) -> None:
        """Take off the books the children that finally let go."""
        with self.state_lock:
            survivors = list(self._dying)
        for child in survivors:
            # poll() first, and only fall back to the signal: it collects the
            # zombie AND answers. A child that died after outlasting SIGKILL is
            # held open by the kernel until somebody waits for it, and until
            # then os.kill(pid, 0) says it is alive — which would leave it in
            # this list, and its memory booked, for the life of the service.
            if child.reap() is None and (child.pid is None or pid_alive(child.pid)):
                continue
            with self.state_lock:
                if child in self._dying:
                    self._dying.remove(child)
            self._withdraw(child)
            logger.info("[LLM-CHILD %s] survivor PID %s is finally gone",
                        child.alias, child.pid)
            # It stood in the state file so the next run would find it; now
            # that it is gone, that entry would name a PID belonging to nobody.
            self._write_state()

    def _end_stalled_generations(self) -> None:
        """End a child that holds a request and has stopped working on it.

        A read timeout on the answer is the wrong instrument and stays
        forbidden: a long reading is an ordinary event here, and a deadline on
        it cuts good answers in half. What is bounded is PROGRESS — frames
        arriving, work lines written, the child's own slots moving or answering
        at all. A llama-server that survived a CUDA error accepts the request
        and does none of those; without this it holds its refcount, and with the
        refcount its whole model, until somebody restarts the service.

        A request that is receiving anything at all is never cut, and neither is
        one whose child is demonstrably still working on it.

        TWO CLOCKS, because two different things go wrong. The child stops
        working on everything — that ends the child. Or one stream stops being
        drained while the child serves the next caller quite happily — that ends
        the stream, and nothing else: its refcount is what holds the model, and
        the model is worth more than one lost answer.
        """
        now = time.monotonic()
        for child in self.snapshot():
            if self._stop.is_set():
                return
            if child.state is not ChildState.READY or child.in_use <= 0:
                child._gen_marks = None
                continue
            marks = child.generation_marks()
            moved = child._gen_marks is None or marks_moved(child._gen_marks, marks)
            if moved:
                child._gen_marks = marks
                child._gen_moved_at = now
            silent_for = now - child._gen_moved_at
            if not moved and silent_for >= self.stall_s:
                reason = (f"no progress for {silent_for:.0f}s while {child.in_use} "
                          f"request(s) were waiting for it")
                logger.error("[LLM-CHILD %s] %s — ending it", child.alias, reason)
                self._forget(child, terminate=True, reason=reason)
                continue
            self._end_stalled_requests(child, now)

    def _end_stalled_requests(self, child: SupervisedChild, now: float) -> None:
        """End single streams that stopped being read while the child worked on.

        TWO CONDITIONS, and both are about telling this apart from ordinary
        waiting. There has to be more than one stream in flight: with a single
        one, everything the child is doing IS this request — its prefill writes
        the work lines, its decode moves the counter — and cutting it would end
        exactly the long readings the whole bound is built to protect. And the
        stream has to have received frames already: one slot means the next
        request waits without a single byte until the slot is free, and that
        wait is the server doing its job.

        What is left after those two is the case this exists for: with one slot
        a task runs to its end, so a stream that had frames and then stopped
        while another task moved on is a finished answer nobody is draining.
        """
        in_flight = child.in_flight()
        if len(in_flight) < 2:
            return
        for request in in_flight:
            if request.frames <= 0 or request.ended_reason:
                continue
            silent_for = now - request.last_frame_at
            if silent_for < self.stall_s:
                continue
            reason = (f"this request received nothing for {silent_for:.0f}s while "
                      f"{child.alias} served {len(in_flight) - 1} other request(s)")
            logger.error("[LLM-CHILD %s] %s — ending the request, not the child",
                         child.alias, reason)
            request.end(reason)

    # ------------------------------------------------------------- state file

    def _write_state(self) -> None:
        """Write who our children are now, newest snapshot last.

        Two things have to hold at once, and only one of them is obvious. Two
        writers must not overtake each other — an unload's empty list landing
        after a later registration's leaves the next start of this service
        reading a file that names nobody while a child of ours is on the card.
        And the write must NOT happen under state_lock: an eviction holds the
        coordinator's request lock while it waits on unload, which takes
        state_lock, so a state directory that has stopped answering would stall
        every load on the plant behind one fsync.

        So the snapshot is numbered under the lock and written outside it, and a
        snapshot that turns out to be older than one already on disk is dropped
        instead of written. The file is small and written rarely.
        """
        with self.state_lock:
            self._state_seq += 1
            seq = self._state_seq
            entries = [c.as_state_entry() for c in self._children.values()]
            entries += [c.as_state_entry() for c in self._dying]
        self._write_state_entries(seq, entries)

    def _write_state_entries(self, seq: int, entries: List[Dict[str, Any]]) -> bool:
        """Write one numbered snapshot, unless a newer one has already landed."""
        with self._state_write_lock:
            if seq <= self._state_written:
                return False
            self._state_written = seq
            self.state_file.write(entries)
            return True


# =============================================================================
# Shutdown
# =============================================================================

_shutdown_ran = threading.Event()


def install_shutdown_hooks(terminate_all: Callable[..., Any]) -> None:
    """Make SIGTERM, SIGINT and a plain exit end the children too.

    Under the unit this service ships with (KillMode=mixed) SIGTERM goes to the
    main process alone, so this hook is not a first line in front of systemd's
    sweep — it IS the shutdown. What systemd contributes is the backstop, and it
    is built for the post-mortem rather than for the children: once the stop
    timeout has run out, TimeoutStopFailureMode=abort sends SIGABRT so this
    process dumps core, and the control group is SIGKILLed after
    TimeoutAbortSec. By then nothing orderly is happening any more; what the
    backstop preserves is the stack of whatever was holding on. A manual run, a
    `kill` on the service PID and an unhandled exit reach here the same way.
    """
    previous: Dict[int, Any] = {}

    def _run(reason: str) -> None:
        if _shutdown_ran.is_set():
            return
        _shutdown_ran.set()
        try:
            terminate_all(reason)
        except Exception as e:  # noqa: BLE001
            logger.error("[LLM] Terminating children on %s failed: %s", reason, e)

    def _handler(signum, frame):
        _run(f"signal {signum}")
        chained = previous.get(signum)
        if callable(chained):
            chained(signum, frame)
            return
        # Nothing of ours left to do: restore the default disposition and let
        # the signal do what it would have done.
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    atexit.register(_run, "process exit")
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, _handler)
        except (ValueError, OSError) as e:
            logger.warning("[LLM] Could not install the %s handler: %s", sig, e)


