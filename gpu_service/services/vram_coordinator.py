"""
VRAM Coordinator - Central VRAM management for all GPU backends

Enables bidirectional cross-backend eviction without loops.
NVML integration for real GPU visibility (foreign processes, zombies).
Cross-process ComfyUI eviction via POST /free (last resort).

Architecture:
                    ┌─────────────────────┐
                    │  VRAMCoordinator    │
                    │  (Singleton)        │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
    │ DiffusersBackend│ │ LLM station │ │ MMAudio, Image- │
    │ (image/video)   │ │ (child or   │ │ Bind, Stable    │
    │                 │ │  inprocess) │ │ Audio (audio)   │
    └─────────────────┘ └─────────────┘ └─────────────────┘

Key Features:
- Backends register with the coordinator
- `request_vram()` triggers cross-backend LRU eviction
- Priority system prevents evicting in-use models
- Central coordination prevents eviction loops
- NVML: sees ALL GPU processes (ComfyUI, zombies)
- Dynamic threshold: expected foreign VRAM adapts to ComfyUI state
- Port blacklist: detects SwarmUI zombies on forbidden ports
"""

import gc
import logging
import os
import re
import socket
import threading
import time
import urllib.request
import json
from typing import Optional, Dict, List, Any, Callable, Protocol, Tuple
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)

# How long the coordinator leaves ComfyUI alone after an ask that brought
# nothing back. A repeat inside this window cannot find anything the first one
# did not already take, and every request interrupts whoever is generating over
# there. An ask that DID free memory is not held back at all: that ComfyUI is
# responsive and yielding, and the next caller may need a second helping.
COMFYUI_EVICTION_COOLDOWN_S = 30.0

# The shortest gap between two asks, whatever the first one brought back. Every
# ask throws out everything ComfyUI holds, and it reads its checkpoint back from
# disk on the next generation — so even a fruitful ask must not be repeated by
# each member of a burst of loads. Five seconds is also how long the polling
# inside an ask waits for the release to appear, so the next caller reads a
# settled card rather than asking for what is already on its way.
COMFYUI_EVICTION_MIN_GAP_S = 5.0

# A granted-but-not-yet-materialized allocation is counted against the card
# until its holder releases it. Between the grant and the moment the weights are
# actually there, nothing in NVML's reading shows that the room is spoken for —
# a concurrent load then takes it, and the first one runs into a card that no
# longer holds what it was promised.
#
# The TTL is a last-resort net, nothing more: a process death takes the whole
# in-memory list with it, and every ordinary path — success and failure alike —
# releases explicitly. Only a loader that is genuinely wedged ever reaches it,
# so the figure is generous. It is derived from the amount, because the largest
# entries read tens of gigabytes off disk before they are on the card, and a
# reservation that expires mid-load withdraws the protection exactly where it
# was needed and blames a loader that did nothing wrong.
VRAM_RESERVATION_MIN_TTL_S = 600.0
# Worst-case sustained read for the model files, in MB per second. Deliberately
# far below what the machines actually manage.
VRAM_RESERVATION_MB_PER_S = 50.0


class EvictionPriority(IntEnum):
    """
    Higher priority = harder to evict.

    When Backend A (prio 2) needs VRAM and Backend B (prio 1) has models,
    A can evict B's models.

    Same priority: LRU decides.
    """
    LOW = 1       # Cache, previews, temporary models
    NORMAL = 2    # Standard models (SD3.5, Llama, etc.)
    HIGH = 3      # Currently in-use models (in_use > 0)
    CRITICAL = 4  # Never evict (system-critical)


@dataclass
class RegisteredModel:
    """Info about a registered model."""
    backend_id: str
    model_id: str
    vram_mb: float
    priority: EvictionPriority
    last_used: float
    in_use: int  # Refcount


class VRAMBackend(Protocol):
    """Protocol that backends must implement for VRAM coordination."""

    def get_registered_models(self) -> List[Dict[str, Any]]:
        """Return list of models with vram_mb, priority, last_used, in_use."""
        ...

    def evict_model(self, model_id: str) -> bool:
        """Evict a specific model. Returns True if successful."""
        ...

    def get_backend_id(self) -> str:
        """Unique identifier for this backend."""
        ...

    # OPTIONAL, and the only optional member of this protocol. A backend whose
    # models live in other processes cannot read its own figures out of torch;
    # it needs NVML, per PID. Enumerating NVML once per alias would ask the
    # driver a dozen times for one collection pass, so the coordinator takes ONE
    # snapshot and offers it here before asking for the models. A backend that
    # does not define this method is called exactly as before.
    #
    #   def receive_nvml_snapshot(self, nvml_info: Optional[Dict[str, Any]]) -> None: ...


class VRAMCoordinator:
    """
    Central VRAM management.

    Backends register here and report model loads/unloads.
    When VRAM is needed, the coordinator decides who gets evicted.
    """

    def __init__(self):
        self._backends: Dict[str, VRAMBackend] = {}
        self._request_lock = threading.Lock()
        self._eviction_in_progress = False

        # Cache for fast VRAM queries
        self._last_vram_check: float = 0
        self._cached_free_mb: float = 0
        self._cache_ttl_ms: float = 100  # 100ms cache

        # NVML state
        self._nvml_handle = None
        self._nvml_available = False

        # Warning cooldown
        self._last_foreign_warn_time: float = 0

        # Room that has been granted but is not on the card yet. Guarded by its
        # own lock, deliberately not by _request_lock: a release happens while
        # another request may be inside a multi-second eviction, and it must
        # never wait for it.
        self._reservations: List[Dict[str, Any]] = []
        self._reservation_lock = threading.Lock()
        self._reservation_seq = 0

        # ComfyUI's /free is a heavy interruption for whoever is generating
        # there, and a burst of loads used to fire one per load.
        self._last_comfyui_attempt: float = 0
        self._last_comfyui_freed_mb: float = 0.0
        self._last_comfyui_note: str = "not asked yet"

        # GPU processes this service OWNS: the llama-server children it spawned.
        # They run outside this PID, so NVML reports them like any stranger —
        # and without this registry the coordinator would count our own 20 GB
        # model as foreign, warn about it every minute, and offer it to
        # kill-foreign. Guarded by its own lock: it is read inside every NVML
        # query, including those a request holds _request_lock across.
        self._owned_pids: Dict[int, Dict[str, Any]] = {}
        self._owned_lock = threading.Lock()
        self._owned_terminators: Dict[str, Tuple[Callable[..., Any], bool]] = {}

        # One NVML enumeration serves everything asked within a second of it.
        # Enumerating walks every process on the card, and the child supervisor
        # asks per child while it waits for a load and again while it waits for
        # a termination — several times a second, for a figure that cannot have
        # changed between two of those calls.
        self._nvml_cache: Optional[Dict[str, Any]] = None
        self._nvml_cache_at: float = 0.0
        self._nvml_cache_lock = threading.Lock()

        # Initialize NVML
        self._init_nvml()

        logger.info("[VRAM-COORD] Initialized")

        # Startup VRAM scan (after NVML init)
        self._log_startup_vram()

    # =========================================================================
    # NVML Integration
    # =========================================================================

    def _init_nvml(self) -> None:
        """One-time NVML init. Fail-open if nvidia-ml-py missing."""
        from config import VRAM_USE_NVML

        if not VRAM_USE_NVML:
            logger.info("[VRAM-COORD] NVML disabled by config")
            return

        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._nvml_available = True
            logger.info("[VRAM-COORD] NVML initialized — real GPU memory visibility enabled")
        except ImportError:
            logger.warning("[VRAM-COORD] nvidia-ml-py not installed — using PyTorch-only VRAM (blind to foreign processes)")
        except Exception as e:
            logger.warning(f"[VRAM-COORD] NVML init failed: {e} — using PyTorch-only VRAM")

    # ---------------------------------------------------- owned GPU processes

    def register_owned(self, pid: Optional[int], starttime: Optional[int], label: str,
                       confirm: Optional[Callable[[], bool]] = None) -> None:
        """Declare a GPU process that this service owns and can end.

        Ownership is never inferred from a port, a model path or a command line
        — every one of those can belong to somebody else's process a moment
        later. It is asserted by whoever spawned the process, with the PID and
        the moment it was born, and it stays true only while `confirm` says the
        same process is still there. A PID is reused within hours on a busy box;
        treating a stranger that inherited one as ours would mean killing it.
        """
        if not isinstance(pid, int):
            return
        with self._owned_lock:
            self._owned_pids[pid] = {
                "starttime": starttime,
                "label": label or "owned child",
                "confirm": confirm,
            }
        logger.info("[VRAM-COORD] PID %s is ours: %s", pid, label)

    def unregister_owned(self, pid: Optional[int],
                         starttime: Optional[int] = None) -> None:
        """Give up ownership of a PID — it ended, or it is no longer ours.

        With a starttime, only that exact process is given up. The number alone
        is not an identity: a child withdrawn a moment late would otherwise take
        out the registration of whatever process the kernel has since given its
        PID to — and that process is usually the child started to replace it,
        which would then count as a stranger on the card. Without one (the
        stale-entry sweep, which has already established the process is gone)
        the entry goes either way.
        """
        if not isinstance(pid, int):
            return
        with self._owned_lock:
            if starttime is not None:
                known = self._owned_pids.get(pid)
                if known is not None and known.get("starttime") != starttime:
                    logger.info("[VRAM-COORD] PID %s now belongs to another "
                                "process of ours — the old entry is not touched", pid)
                    return
            entry = self._owned_pids.pop(pid, None)
        if entry is not None:
            logger.info("[VRAM-COORD] PID %s is no longer ours (%s)",
                        pid, entry.get("label"))

    def register_owned_terminator(self, key: str, terminate: Callable[..., Any]) -> None:
        """How to end this backend's owned processes, for the emergency path.

        Whether it takes a reason is decided HERE, once, from the signature.
        Deciding it by calling and catching TypeError meant that a TypeError
        raised INSIDE the terminator — deep in the termination of a child —
        looked like the wrong arity and ran the whole thing a second time.
        """
        import inspect
        try:
            takes_reason = bool(inspect.signature(terminate).parameters)
        except (TypeError, ValueError):
            # A callable whose signature cannot be read (a C function, some
            # partials): assume it takes the reason, as ours all do.
            takes_reason = True
        self._owned_terminators[key] = (terminate, takes_reason)

    def _owned_labels(self) -> Dict[int, str]:
        """The PIDs that count as ours right now, with their labels.

        Asks each registrar to confirm; an entry that cannot be confirmed is
        dropped here rather than lingering, so a child that died between two
        NVML reads stops being an exception to the foreign rule at once.
        """
        with self._owned_lock:
            entries = list(self._owned_pids.items())
        labels: Dict[int, str] = {}
        stale: List[int] = []
        for pid, entry in entries:
            confirm = entry.get("confirm")
            try:
                still_ours = True if confirm is None else bool(confirm())
            except Exception as e:  # noqa: BLE001
                logger.warning("[VRAM-COORD] Could not confirm PID %s: %s", pid, e)
                still_ours = False
            if still_ours:
                labels[pid] = entry.get("label") or "owned child"
            else:
                stale.append(pid)
        for pid in stale:
            self.unregister_owned(pid)
        return labels

    def terminate_owned(self, reason: str = "emergency reclaim") -> None:
        """End every owned process. Used by the emergency reclaim path only."""
        for key, (terminate, takes_reason) in list(self._owned_terminators.items()):
            try:
                terminate(reason) if takes_reason else terminate()
            except Exception as e:  # noqa: BLE001
                logger.error("[VRAM-COORD] Could not end %s's children: %s", key, e)

    def get_process_vram_mb(self, pid: int, max_age_s: float = 1.0) -> Optional[float]:
        """One PID's GPU memory per NVML. None when it holds none, or NVML is mute.

        The honest reading for a model that llama.cpp allocates outside the torch
        allocator, and for a child that is not this process at all —
        torch.cuda.memory_allocated() can answer for neither.

        None covers three different things and each of them is "no figure": the
        PID holds nothing, NVML is mute, or NVML lists the process without being
        able to attribute its memory. What it never covers is zero — a resident
        model reported as 0 MB is room this coordinator would hand out twice.
        """
        info = self._nvml_snapshot(max_age_s)
        if not info:
            return None
        for proc in info.get("processes", []):
            if proc.get("pid") == pid:
                if proc.get("vram_unknown"):
                    return None
                return float(proc.get("vram_mb") or 0.0)
        return None

    def invalidate_nvml_cache(self) -> None:
        """Forget the cached enumeration: something on the card has just changed.

        Called when a process this service owns has released its memory. The
        cache exists so that four reads a second cost one walk; a reader
        arriving right after a child died would otherwise be told, for up to a
        second, that the card still holds its model — and refuse the load that
        was waiting for exactly that room.
        """
        with self._nvml_cache_lock:
            self._nvml_cache = None
            self._nvml_cache_at = 0.0

    def _nvml_snapshot(self, max_age_s: float = 1.0) -> Optional[Dict[str, Any]]:
        """The last NVML enumeration if it is fresh enough, else a new one.

        Used by the callers that ask often and can live with a figure a moment
        old: the per-PID reading, the model collection, the status endpoint. The
        callers that must be current — the sensor-health check, free VRAM, the
        foreign-process check, the emergency path — call _get_nvml_memory_info
        directly and refresh this cache in passing.
        """
        now = time.monotonic()
        with self._nvml_cache_lock:
            if self._nvml_cache is not None and (now - self._nvml_cache_at) <= max_age_s:
                return self._nvml_cache
        info = self._get_nvml_memory_info()
        if info is not None:
            with self._nvml_cache_lock:
                self._nvml_cache = info
                self._nvml_cache_at = time.monotonic()
        return info

    def _get_nvml_memory_info(self) -> Optional[Dict[str, Any]]:
        """
        Get real GPU memory info via NVML.

        Returns dict with total_mb, used_mb, free_mb, foreign_mb, processes[].
        Returns None on failure (fail-open).

        A process this service owns — an llama-server child — is marked
        `owned: true, foreign: false` and stays out of foreign_mb. It is our
        memory, held in another PID; counting it as somebody else's would make
        the foreign-VRAM warning fire on every model load and offer our own
        checking model to kill-foreign. Its real cmdline is kept, so the log
        still says which process the label belongs to.
        """
        if not self._nvml_available or self._nvml_handle is None:
            return None

        try:
            import pynvml

            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
            total_mb = mem_info.total / (1024 * 1024)
            used_mb = mem_info.used / (1024 * 1024)
            free_mb = mem_info.free / (1024 * 1024)

            # Get all GPU processes
            our_pid = os.getpid()
            owned = self._owned_labels()
            processes = []

            try:
                gpu_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(self._nvml_handle)
            except Exception:
                gpu_procs = []

            foreign_mb = 0
            for proc in gpu_procs:
                pid = proc.pid
                # Kept apart from the figure: NVML returns no memory for a
                # process it cannot attribute, and 0 MB and "unknown" are
                # different states — a ledger that read the first as the second
                # would drop a resident model to nothing.
                unknown = proc.usedGpuMemory is None
                vram_mb = (proc.usedGpuMemory or 0) / (1024 * 1024)
                is_owned = pid in owned
                is_foreign = pid != our_pid and not is_owned
                cmdline = self._read_proc_cmdline(pid)

                if is_foreign:
                    foreign_mb += vram_mb

                processes.append({
                    "pid": pid,
                    "vram_mb": round(vram_mb, 1),
                    "vram_unknown": unknown,
                    "foreign": is_foreign,
                    "owned": is_owned,
                    "label": owned.get(pid, ""),
                    "cmdline": cmdline,
                })

            info = {
                "total_mb": round(total_mb, 1),
                "used_mb": round(used_mb, 1),
                "free_mb": round(free_mb, 1),
                "foreign_mb": round(foreign_mb, 1),
                "processes": processes,
            }
            # Every fresh enumeration serves the cache too, so a caller that
            # needed the current figure spares the next one its own walk.
            with self._nvml_cache_lock:
                self._nvml_cache = info
                self._nvml_cache_at = time.monotonic()
            return info

        except Exception as e:
            logger.warning(f"[VRAM-COORD] NVML memory query failed: {e}")
            return None

    @staticmethod
    def _read_proc_cmdline(pid: int) -> str:
        """Read /proc/{pid}/cmdline. Returns '(unknown)' on failure."""
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                raw = f.read(512)
            return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
        except Exception:
            return "(unknown)"

    @classmethod
    def _process_tag(cls, proc: Dict[str, Any]) -> str:
        """What a GPU process is called in the log.

        NVML's view is unchanged and so is every number below: the platform's own
        ComfyUI runs in another PID, it counts as foreign in foreign_mb, and this
        process cannot free its memory directly. But the eviction chain knows
        that instance and can ask it for its memory back, and printing those
        gigabytes as "[FOREIGN]" said the opposite — that nothing here could be
        reclaimed. Only the label changes; the arithmetic is untouched.

        Identified by the PID listening on the ComfyUI port. Where that listener
        cannot be resolved at all — psutil does not see sockets owned by other
        users — the command line answers instead, matched on the port as a whole
        number so that "17804" does not also accept "178042". That second route
        is weaker and says so in the label: a command line proves only what the
        process was started with, and _read_proc_cmdline sees just its first 512
        bytes, so a process started with the port further along stays [FOREIGN].

        The label stops at naming the instance. It promises nothing about
        reclaiming, because while ComfyUI holds the admission slot the chain
        deliberately does not ask it.
        """
        if proc.get("owned"):
            return "[%s]" % (proc.get("label") or "owned child")
        if not proc.get("foreign"):
            return "[self]"
        try:
            from config import COMFYUI_PORT
            pid, _ = cls._find_pid_for_port(COMFYUI_PORT)
            if pid is not None:
                if pid == proc.get("pid"):
                    return "[comfyui — platform instance]"
            elif re.search(rf"(?<!\d){COMFYUI_PORT}(?!\d)", proc.get("cmdline") or ""):
                return "[comfyui — platform instance, by command line]"
        except Exception:
            pass
        return "[FOREIGN]"

    def _get_expected_foreign_vram_mb(self) -> float:
        """
        Dynamic threshold: how much foreign VRAM is expected.

        Checks ComfyUI port + adds driver overhead.
        Adapts automatically when services start/stop.
        """
        from config import VRAM_FOREIGN_OVERHEAD_MB, COMFYUI_PORT

        expected = VRAM_FOREIGN_OVERHEAD_MB  # Base: CUDA contexts + driver + display

        # Check if expected ComfyUI is running
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", COMFYUI_PORT))
            sock.close()
            if result == 0:
                expected += 1024  # Generous estimate for idle ComfyUI
        except Exception:
            pass

        return expected

    def _check_foreign_processes(self, nvml_info: Dict[str, Any]) -> None:
        """
        Compare actual foreign VRAM vs expected.
        Warns (with 60s cooldown) if unexpected foreign VRAM detected.

        Owned children are not foreign and are skipped: they are this service's
        own models, in this service's own child processes, already in the ledger.
        """
        now = time.time()
        if now - self._last_foreign_warn_time < 60:
            return

        actual_foreign_mb = nvml_info.get("foreign_mb", 0)
        expected_foreign_mb = self._get_expected_foreign_vram_mb()

        if actual_foreign_mb > expected_foreign_mb:
            delta = actual_foreign_mb - expected_foreign_mb
            self._last_foreign_warn_time = now
            logger.warning(
                f"[VRAM-COORD] Foreign VRAM {actual_foreign_mb:.0f}MB exceeds "
                f"expected {expected_foreign_mb:.0f}MB by {delta:.0f}MB"
            )
            for proc in nvml_info.get("processes", []):
                if proc["foreign"] and not proc.get("owned"):
                    logger.warning(
                        f"[VRAM-COORD]   {self._process_tag(proc)} PID {proc['pid']} "
                        f"({proc['vram_mb']:.0f}MB): {proc['cmdline']}"
                    )

    def _check_blacklisted_ports(self) -> List[Dict[str, Any]]:
        """
        Check if any blacklisted ports (SwarmUI zombies) are active.
        Returns list of active blacklisted port info.
        """
        from config import VRAM_BLACKLISTED_PORTS

        active = []
        for port in VRAM_BLACKLISTED_PORTS:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex(("127.0.0.1", port))
                sock.close()
                if result == 0:
                    # Port is active — try to find the PID
                    pid, cmdline = self._find_pid_for_port(port)
                    entry = {"port": port, "pid": pid, "cmdline": cmdline}
                    active.append(entry)
                    logger.warning(
                        f"[VRAM-COORD] BLACKLISTED PORT {port} ACTIVE — "
                        f"AI Lab destabilization detected!"
                    )
                    if pid:
                        logger.warning(
                            f"[VRAM-COORD]   PID {pid} on port {port}: {cmdline}"
                        )
                        logger.warning(
                            f'[VRAM-COORD]   Terminate via: POST /api/health/kill-foreign '
                            f'{{"pid": {pid}}}'
                        )
            except Exception:
                pass

        return active

    @staticmethod
    def _find_pid_for_port(port: int) -> tuple:
        """Find PID listening on a port via psutil. Returns (pid, cmdline) or (None, '')."""
        try:
            import psutil
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr.port == port and conn.status == "LISTEN":
                    try:
                        proc = psutil.Process(conn.pid)
                        return conn.pid, " ".join(proc.cmdline())
                    except Exception:
                        return conn.pid, "(unknown)"
        except Exception:
            pass
        return None, ""

    def _log_startup_vram(self) -> None:
        """One-time startup scan: log VRAM state + processes + blacklisted ports."""
        nvml_info = self._get_nvml_memory_info()
        if nvml_info is None:
            logger.info("[VRAM-COORD] Startup: NVML not available, skipping detailed scan")
            return

        logger.info(
            f"[VRAM-COORD] Startup VRAM: total={nvml_info['total_mb']:.0f}MB, "
            f"used={nvml_info['used_mb']:.0f}MB, free={nvml_info['free_mb']:.0f}MB"
        )

        expected = self._get_expected_foreign_vram_mb()
        actual_foreign = nvml_info["foreign_mb"]
        logger.info(
            f"[VRAM-COORD] Expected foreign: {expected:.0f}MB, "
            f"actual foreign: {actual_foreign:.0f}MB"
        )

        if actual_foreign > expected:
            logger.warning(
                f"[VRAM-COORD] Actual foreign exceeds expected by "
                f"{actual_foreign - expected:.0f}MB"
            )
        else:
            logger.info("[VRAM-COORD] Actual foreign within expected range")

        for proc in nvml_info.get("processes", []):
            tag = self._process_tag(proc)
            logger.info(
                f"[VRAM-COORD] Startup GPU process {tag}: PID {proc['pid']}, "
                f"{proc['vram_mb']:.0f}MB — {proc['cmdline']}"
            )

        blacklisted = self._check_blacklisted_ports()
        from config import VRAM_BLACKLISTED_PORTS
        for port in VRAM_BLACKLISTED_PORTS:
            status = "ACTIVE" if any(b["port"] == port for b in blacklisted) else "clear"
            logger.info(f"[VRAM-COORD] Blacklisted port {port}={status}")

    # =========================================================================
    # Backend Registration
    # =========================================================================

    def register_backend(self, backend: VRAMBackend) -> None:
        """Register a backend for VRAM coordination."""
        backend_id = backend.get_backend_id()
        self._backends[backend_id] = backend
        logger.info(f"[VRAM-COORD] Registered backend: {backend_id}")


    # =========================================================================
    # VRAM Queries
    # =========================================================================

    def get_free_vram_mb(self, use_cache: bool = True) -> float:
        """
        Get currently free VRAM in MB.

        Prefers NVML (sees all processes) with PyTorch fallback.
        Runs foreign process checks on non-cached queries.
        """
        import torch

        now = time.time() * 1000
        if use_cache and (now - self._last_vram_check) < self._cache_ttl_ms:
            return self._cached_free_mb

        # Try NVML first (sees all GPU processes)
        nvml_info = self._get_nvml_memory_info()
        if nvml_info is not None:
            free_mb = nvml_info["free_mb"]

            # Run checks on fresh queries
            self._check_foreign_processes(nvml_info)
            self._check_blacklisted_ports()
        else:
            # Fallback: PyTorch only (blind to foreign processes)
            if not torch.cuda.is_available():
                return 0
            total = torch.cuda.get_device_properties(0).total_memory
            allocated = torch.cuda.memory_allocated(0)
            free_mb = (total - allocated) / (1024 * 1024)

        self._cached_free_mb = free_mb
        self._last_vram_check = now
        return free_mb

    def get_own_process_vram_mb(self) -> Optional[float]:
        """
        GPU memory THIS process holds, as NVML sees it. None if unreadable.

        Whole-process: every backend in this service shares the number, so it
        says nothing about a single model and must not be attributed to one.
        It answers one question honestly -- did memory actually come back --
        which torch.cuda.memory_allocated() cannot answer at all for models
        that llama.cpp allocates outside the torch allocator.

        Only the in-process LLM engine still asks (services/llm_backend.py). The
        child engine measures per child PID instead, through
        get_process_vram_mb, and gets a figure that belongs to one model.

        Read fresh, never from the second-old cache: the one question it answers
        is asked immediately after an unload, and an answer from before that
        unload would say the memory is still held.
        """
        return self.get_process_vram_mb(os.getpid(), max_age_s=0.0)

    def get_total_vram_mb(self) -> float:
        """Get total VRAM in MB."""
        import torch
        if not torch.cuda.is_available():
            return 0
        return torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)

    def get_obtainable_vram_mb(
        self,
        requester_priority: EvictionPriority = EvictionPriority.NORMAL,
        use_cache: bool = True,
    ) -> float:
        """
        VRAM a requester can obtain: free right now plus what eviction would release.

        Free VRAM answers "what is unused this second", which on a working card is
        near zero while tens of GB sit in idle models this coordinator evicts on
        request. Fit checks and quantization choices must ask this instead, or they
        report models as unloadable that in fact load fine.

        Deliberately conservative: counts only registered models that are idle and
        evictable at this priority — the same filter _do_eviction applies. Room
        that is promised to a load still landing is left out for the same reason,
        because nothing can evict it. The allocator's cached-but-unallocated
        blocks and ComfyUI's cross-process last resort are additional headroom on
        top of this figure.

        A decision value, not a display one: quantization choices are made from
        it, and one made against room another load is already taking produces a
        model that does not fit.
        """
        evictable_mb = sum(
            m.vram_mb for m in self._collect_all_models()
            if m.priority <= requester_priority and m.in_use == 0
        )
        return self._free_for_decision_mb(use_cache=use_cache) + evictable_mb

    # =========================================================================
    # Reservations
    # =========================================================================

    def _reserved_mb(self) -> float:
        """Room promised to callers that have not put it on the card yet.

        Prunes on read: a reservation older than the TTL is dropped whether or
        not anyone released it, so a caller that died mid-load cannot make the
        card look full for the rest of the process's life.
        """
        now = time.time()
        with self._reservation_lock:
            expired = [r for r in self._reservations if r["expires_at"] <= now]
            for r in expired:
                logger.warning(
                    "[VRAM-COORD] Reservation of %.0fMB for %s expired after %.0fs "
                    "without being released", r["mb"], r["tag"], r["ttl_s"]
                )
            if expired:
                self._reservations = [r for r in self._reservations if r["expires_at"] > now]
            return sum(r["mb"] for r in self._reservations)

    def _free_for_decision_mb(self, use_cache: bool = False) -> float:
        """Free VRAM as a grant decision must see it: minus what is promised.

        Only for decisions — whether a request is granted, and how much a caller
        could obtain. get_free_vram_mb() stays what NVML says and is what the
        status endpoint reports: a display that subtracted promises would show
        memory as gone that the card does not report as gone. How DEEP an
        eviction goes is measured on the physical figure too; see _do_eviction.

        While a reserved load is materializing the same megabytes are counted
        twice: NVML already sees the weights arriving AND the reservation still
        stands until the loader releases it. That is deliberate. For those few
        seconds the coordinator judges itself poorer than it is, which refuses a
        borderline second load — and a refused load is recoverable, while the
        collision this prevents is a segfault that takes the service down.
        """
        return max(0.0, self.get_free_vram_mb(use_cache=use_cache) - self._reserved_mb())

    def _add_reservation(self, mb: float, tag: str) -> str:
        """Record a granted-but-unmaterialized allocation. Returns its token.

        The lifetime grows with the amount: what has to be read off disk before
        it is on the card is what decides how long the promise must stand. See
        VRAM_RESERVATION_MIN_TTL_S for why the floor is generous.
        """
        ttl_s = max(VRAM_RESERVATION_MIN_TTL_S, float(mb) / VRAM_RESERVATION_MB_PER_S)
        with self._reservation_lock:
            self._reservation_seq += 1
            token = f"{tag}-{self._reservation_seq}"
            self._reservations.append({
                "token": token,
                "mb": float(mb),
                "tag": tag,
                "ttl_s": ttl_s,
                "expires_at": time.time() + ttl_s,
            })
        logger.debug("[VRAM-COORD] Reserved %.0fMB for %s (%s, %.0fs)", mb, tag, token, ttl_s)
        return token

    def release_reservation(self, token: Optional[str]) -> None:
        """Give back a reservation once the load has landed — or has failed.

        Both outcomes end here, and both must: after a successful load the
        memory is on the card and NVML counts it, so continuing to hold the
        promise would double-count it for the whole TTL; after a failed one
        nothing was taken at all.
        """
        if not token:
            return
        with self._reservation_lock:
            self._reservations = [r for r in self._reservations if r["token"] != token]

    # =========================================================================
    # Eviction
    # =========================================================================

    def request_vram(
        self,
        requester_id: str,
        required_mb: float,
        requester_priority: EvictionPriority = EvictionPriority.NORMAL
    ) -> bool:
        """
        Request VRAM, evicting other models if necessary.

        Args:
            requester_id: Backend ID making the request
            required_mb: How much VRAM is needed
            requester_priority: Priority of the requesting operation

        Returns:
            True if enough VRAM is now available

        Eviction Strategy:
        1. Only evict models with priority <= requester_priority (same tier: LRU)
        2. Among evictable models, use LRU order
        3. Never evict models with in_use > 0 (elevated to HIGH priority)
        4. Stop when enough VRAM is free

        Signature and return type are load-bearing: eight backends call this,
        and one of them acts on the boolean — diffusers_backend, which logs an
        incomplete eviction. A tuple here would be truthy on every refusal, so
        that one would read a shortfall as a grant. Callers that need the detail
        ask request_vram_detailed() instead.
        """
        granted, _reason, _token = self.request_vram_detailed(
            requester_id, required_mb, requester_priority)
        return granted

    def request_vram_detailed(
        self,
        requester_id: str,
        required_mb: float,
        requester_priority: EvictionPriority = EvictionPriority.NORMAL,
        hold: bool = False,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        The same request, with the shortfall sentence and an optional hold.

        Two callers, and one of them is easy to overlook when this signature
        changes: the LLM backend, which needs the reason and the hold, and the
        admission gate in gpu_admission, which is not a backend at all and
        refuses the whole operation on a False.

        Returns (granted, reason, token). reason is None on success and on
        failure says what was needed, what stood free afterwards and what became
        of the last station of the chain — including that ComfyUI was never
        asked, which a held slot or a closed port can bring about. It travels
        back with THIS call: kept in shared state it was overwritten by whatever
        request finished next, and a refusal then quoted a foreign bottleneck.

        With hold=True a granted request also reserves the amount until the
        caller releases the token. Without that, the space between the grant and
        the moment the weights are on the card is invisible to the other
        backends: a concurrent load takes it, and the first loader reaches its
        first image with the room gone. The hold binds only what asks this
        coordinator for room. ComfyUI runs in its own process, knows nothing of
        these reservations, and stays the largest holder on the card — against
        it the chain has only the eviction request, not a promise. An unbounded
        request holds nothing: "as much as possible" names no amount, and
        reserving it would refuse every later request until the TTL ran out.
        """
        with self._request_lock:
            if self._eviction_in_progress:
                logger.warning(f"[VRAM-COORD] Eviction already in progress, {requester_id} waiting")
                # Could implement queue here, for now just proceed

            self._eviction_in_progress = True

            try:
                granted, reason = self._do_eviction(
                    requester_id, required_mb, requester_priority)
            finally:
                self._eviction_in_progress = False

            token = None
            if granted and hold and required_mb != float('inf'):
                token = self._add_reservation(required_mb, requester_id)
            return granted, reason, token

    def _collect_all_models(self) -> List[RegisteredModel]:
        """Collect model info from all backends.

        ONE NVML enumeration per pass, offered to whichever backends can use it
        (see the VRAMBackend protocol). A backend whose models live in other
        processes has to read the driver to know what they hold; asking per
        alias meant one enumeration per model, several times a second while an
        eviction runs, for a figure that is the same in all of them.
        """
        all_models = []
        snapshot = None
        snapshot_taken = False

        for backend_id, backend in self._backends.items():
            try:
                receiver = getattr(backend, "receive_nvml_snapshot", None)
                if callable(receiver):
                    if not snapshot_taken:
                        snapshot = self._nvml_snapshot()
                        snapshot_taken = True
                    try:
                        receiver(snapshot)
                    except Exception as e:
                        logger.warning(
                            f"[VRAM-COORD] {backend_id} could not take the NVML "
                            f"snapshot: {e}")
                models = backend.get_registered_models()
                for m in models:
                    # Determine effective priority (in_use elevates to HIGH)
                    base_priority = m.get("priority", EvictionPriority.NORMAL)
                    in_use = m.get("in_use", 0)
                    effective_priority = EvictionPriority.HIGH if in_use > 0 else base_priority

                    all_models.append(RegisteredModel(
                        backend_id=backend_id,
                        model_id=m["model_id"],
                        vram_mb=m.get("vram_mb", 0),
                        priority=effective_priority,
                        last_used=m.get("last_used", 0),
                        in_use=in_use,
                    ))
            except Exception as e:
                logger.error(f"[VRAM-COORD] Failed to get models from {backend_id}: {e}")

        return all_models

    def _do_eviction(
        self,
        requester_id: str,
        required_mb: float,
        requester_priority: EvictionPriority
    ) -> Tuple[bool, Optional[str]]:
        """
        Core eviction logic.

        Returns (success, reason): True and None if enough VRAM is available
        after eviction, False and the shortfall sentence otherwise.

        Two readings run side by side here, and mixing them up costs models.
        WHETHER a request is granted, and HOW DEEP the eviction goes, both
        follow the free figure minus what is promised to loads still landing:
        that room is spoken for, so a promised load keeps it, and stopping the
        loop on the physical figure would leave the card under-evicted for a
        request that is then refused although eviction could have satisfied it.
        Most callers ignore a refusal and load anyway, and an under-evicted card
        is where a foreign load eats the promised room.

        Only the CROSS-PROCESS ask is gated on what the card physically lacks.
        ComfyUI can give back nothing that this coordinator has merely promised
        to somebody, and asking it throws out its checkpoint for a shortage that
        ends by itself the moment the promised load lands. The status endpoint
        keeps the plain NVML number.
        """
        import torch

        free_mb = self._free_for_decision_mb()
        is_inf = required_mb == float('inf')

        if not is_inf and free_mb >= required_mb:
            logger.debug(f"[VRAM-COORD] {requester_id}: Already have {free_mb:.0f}MB >= {required_mb:.0f}MB")
            return True, None

        needed_str = "max available" if is_inf else f"{required_mb:.0f}MB"
        logger.info(
            f"[VRAM-COORD] {requester_id} needs {needed_str}, "
            f"have {free_mb:.0f}MB, starting eviction"
        )

        # Collect all models from all backends
        all_models = self._collect_all_models()

        # Filter evictable models:
        # - priority <= requester_priority (same priority: LRU decides)
        # - in_use == 0 (not currently being used; in_use > 0 elevated to HIGH)
        # Note: We CAN evict from the same backend (requester evicting its own old models)
        evictable = [
            m for m in all_models
            if m.priority <= requester_priority
            and m.in_use == 0
        ]

        # Sort by priority (lowest first), then by last_used (oldest first)
        evictable.sort(key=lambda m: (m.priority, m.last_used))

        evicted_count = 0
        evicted_mb = 0
        # Carried alongside for the cross-process gate below and for the
        # shortfall sentence, which has to be able to say what the card holds.
        physical_free_mb = self.get_free_vram_mb(use_cache=False)

        for model in evictable:
            # The same figure the grant is judged on; see above. Reading it from
            # the 100ms cache reuses the physical reading just taken, so the
            # stop condition and the grant cannot disagree about the moment.
            if not is_inf and self._free_for_decision_mb(use_cache=True) >= required_mb:
                break

            logger.info(
                f"[VRAM-COORD] Evicting {model.backend_id}/{model.model_id} "
                f"({model.vram_mb:.0f}MB, priority={model.priority.name})"
            )

            try:
                backend = self._backends.get(model.backend_id)
                if backend and backend.evict_model(model.model_id):
                    evicted_count += 1
                    evicted_mb += model.vram_mb

                    # Break circular refs, then release CUDA memory
                    gc.collect()
                    torch.cuda.empty_cache()
                    physical_free_mb = self.get_free_vram_mb(use_cache=False)
            except Exception as e:
                logger.error(f"[VRAM-COORD] Eviction failed: {e}")

        # Final check. The physical reading is taken first and the decision
        # figure reuses it through the 100ms cache, so both describe the same
        # moment on the card.
        physical_free_mb = self.get_free_vram_mb(use_cache=False)
        free_mb = self._free_for_decision_mb(use_cache=True)

        if is_inf:
            # Unknown model size: success if we freed something or nothing to free
            success = evicted_count > 0 or len(evictable) == 0
        else:
            success = free_mb >= required_mb

        # Last resort: cross-process ComfyUI eviction — and only for a shortage
        # ComfyUI could actually cure, which means one the card itself has. When
        # the room is physically there and the refusal comes from a promise to a
        # load that is still landing, there is nothing over there to fetch: the
        # ask would throw out ComfyUI's checkpoint for a shortage that ends by
        # itself in seconds.
        #
        # An unbounded request asks even when it has already succeeded, and that
        # is deliberate: "as much as possible" is what such a caller wants, and
        # if the card is still more than half full after the internal eviction
        # ran, what remains on it belongs to ComfyUI.
        comfyui_state = "not asked — internal eviction ran to its end"
        if is_inf:
            ask_comfyui = not success or physical_free_mb < self.get_total_vram_mb() * 0.5
        else:
            ask_comfyui = not success and physical_free_mb < required_mb
            if not success and not ask_comfyui:
                comfyui_state = (
                    "not asked — the card holds the room, it is promised to a load "
                    "that is still landing"
                )
        if ask_comfyui:
            asked, comfyui_freed = self._try_comfyui_eviction()
            # The note carries the outcome in both directions. Rendering the
            # asked branch as "asked, freed 0MB" made a request that never
            # arrived, and one that was answered with an error, read as a
            # ComfyUI that had nothing to give — which sends the reader after
            # the wrong thing entirely.
            comfyui_state = (
                self._last_comfyui_note if asked
                else f"not asked — {self._last_comfyui_note}"
            )
            # Read the card again in every case, and judge on the absolute
            # figure. The delta polling inside _try_comfyui_eviction watches for
            # five seconds and reports what it saw; a release that lands later,
            # or one that another process's allocation covered while it was
            # looking, comes back as 0 there while the memory is in fact free.
            # What the requester needs is what the card holds now.
            physical_free_mb = self.get_free_vram_mb(use_cache=False)
            free_mb = self._free_for_decision_mb(use_cache=True)
            if comfyui_freed > 0:
                evicted_mb += comfyui_freed
            if is_inf:
                success = success or comfyui_freed > 0
            else:
                success = free_mb >= required_mb

        logger.info(
            f"[VRAM-COORD] Eviction complete: evicted {evicted_count} models "
            f"({evicted_mb:.0f}MB), now have {free_mb:.0f}MB, "
            f"needed {needed_str}, success={success}"
        )

        # Handed straight back to the requester that caused it. Nothing is kept:
        # a sentence deposited here for someone to pick up later was read by
        # whichever request finished next, and named a bottleneck belonging to
        # another backend.
        if success:
            return True, None

        reserved_mb = self._reserved_mb()
        reserved_note = (
            f" (a further {reserved_mb:.0f}MB is promised to loads that are still "
            f"landing and was left out of that figure)"
            if reserved_mb > 0 else ""
        )
        # Both figures, because they can be far apart: with promises standing,
        # the usable figure reads 0 while the card itself is half empty, and a
        # sentence that named only the first one described a card nobody could
        # find.
        return False, (
            f"{requester_id} needed {needed_str}, {free_mb:.0f}MB usable for new work "
            f"({physical_free_mb:.0f}MB on the card) after evicting {evicted_count} "
            f"models ({evicted_mb:.0f}MB){reserved_note}; ComfyUI: {comfyui_state}"
        )

    def _try_comfyui_eviction(self) -> tuple:
        """
        Ask ComfyUI to unload all models via POST /free.

        Last resort: only called when internal eviction wasn't enough.
        Returns (asked, freed_mb) — asked False means the request was never
        sent, and the reason for that stands in self._last_comfyui_note. The
        two are kept apart because "ComfyUI freed nothing" and "ComfyUI was
        never asked" are different states of the world, and reporting the
        second as the first is what made a shortfall message name the wrong
        cause.

        Skipped while ComfyUI holds the admission slot: unloading its models in
        the middle of the workflow it was admitted for would corrupt the very
        generation the slot was granted to protect.
        """
        from config import COMFYUI_PORT

        # A burst of loads used to fire one /free per load. For whoever is
        # generating in ComfyUI each of those is an interruption, and a repeat
        # within seconds cannot find anything the first ask did not already take.
        #
        # Two windows, because the outcome of the last ask means something. The
        # short one holds after EVERY ask: a fruitful ask emptied ComfyUI, and
        # letting each member of a burst repeat it would throw its checkpoint
        # off the card again and again while it tries to read one back. The full
        # cooldown holds only after an ask that brought nothing — there the
        # repeat has nothing to gain, and waiting it out is free. An ask that did
        # free memory is available again after a few seconds, so the second
        # content check of a pair, the one a workshop group waits on, can still
        # get its room.
        now = time.time()
        since = now - self._last_comfyui_attempt
        if since < COMFYUI_EVICTION_MIN_GAP_S:
            self._last_comfyui_note = (
                f"asked {since:.0f}s ago, the {COMFYUI_EVICTION_MIN_GAP_S:.0f}s gap "
                f"between two asks is still running"
            )
            logger.info("[VRAM-COORD] ComfyUI was asked %.0fs ago — letting it settle "
                        "before asking again", since)
            return (False, 0.0)
        if since < COMFYUI_EVICTION_COOLDOWN_S and self._last_comfyui_freed_mb <= 0:
            self._last_comfyui_note = (
                f"asked {since:.0f}s ago and nothing came back, "
                f"cooldown is {COMFYUI_EVICTION_COOLDOWN_S:.0f}s"
            )
            logger.info("[VRAM-COORD] ComfyUI was asked %.0fs ago and freed nothing — "
                        "not asking again", since)
            return (False, 0.0)

        try:
            from services.gpu_admission import get_gpu_admission
            active = get_gpu_admission().get_status().get("active") or {}
            if active.get("kind") == "comfyui":
                logger.info("[VRAM-COORD] ComfyUI holds the GPU slot — not asking it to free")
                self._last_comfyui_note = "ComfyUI holds the GPU slot"
                return (False, 0.0)
            # Since stage 7 of the move to ComfyUI the workshop's runs lease
            # the DevServer's gate, not this one, so this slot alone says
            # nothing about whether a run is on ComfyUI. Only a hold that has
            # the card's turn there knows that none is.
            if not active.get("plant_wide_lease"):
                logger.info("[VRAM-COORD] this hold has no plant-wide lease, so whether a "
                            "ComfyUI run is active is unknown — not asking it to free")
                self._last_comfyui_note = ("this hold has no plant-wide lease, so a ComfyUI "
                                           "run may be active")
                return (False, 0.0)
        except Exception as e:
            # Not knowing is not permission. Unloading ComfyUI's models under a
            # running workflow destroys somebody's generation; the alternative is
            # that this operation reports a shortfall, which is recoverable.
            logger.error("[VRAM-COORD] Could not check the admission slot (%s) — "
                         "not asking ComfyUI to free", e)
            self._last_comfyui_note = f"the admission slot could not be read ({e})"
            return (False, 0.0)

        # Check if ComfyUI port is listening
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", COMFYUI_PORT))
            sock.close()
            if result != 0:
                self._last_comfyui_note = f"nothing is listening on port {COMFYUI_PORT}"
                return (False, 0.0)
        except Exception as e:
            self._last_comfyui_note = f"port {COMFYUI_PORT} could not be probed ({e})"
            return (False, 0.0)

        # Measure VRAM before
        free_before = self.get_free_vram_mb(use_cache=False)

        logger.info("[VRAM-COORD] Requesting ComfyUI cross-process eviction (last resort)")
        self._last_comfyui_attempt = time.time()
        # Cleared before the attempt, so that a crash between here and the
        # measurement below leaves the cooldown in force rather than inviting an
        # immediate repeat.
        self._last_comfyui_freed_mb = 0.0

        # POST /free to ComfyUI
        url = f"http://localhost:{COMFYUI_PORT}/free"
        try:
            payload = json.dumps({"unload_models": True, "free_memory": True}).encode()
            req = urllib.request.Request(
                url, data=payload, method="POST",
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                status = resp.status
            logger.info(f"[VRAM-COORD] POST {url} → {status}")
        except Exception as e:
            logger.warning(f"[VRAM-COORD] ComfyUI /free request failed: {e}")
            self._last_comfyui_note = f"asked, but the /free request never arrived ({e})"
            return (True, 0.0)

        if not 200 <= status < 300:
            self._last_comfyui_note = f"asked, /free answered {status}"
            return (True, 0.0)

        # Only now, and only on an answer: everything ComfyUI held is actually
        # going, so the gate must stop believing any of it is still loaded. This
        # used to run before the POST and therefore also when the POST threw —
        # the queue then lost its model affinity while ComfyUI still held every
        # model it had.
        try:
            from services.gpu_admission import get_gpu_admission
            get_gpu_admission().forget_resident("ComfyUI was asked to free everything")
        except Exception:
            pass

        # Poll NVML for up to 5s waiting for VRAM release
        freed_mb = 0
        for _ in range(10):
            time.sleep(0.5)
            free_now = self.get_free_vram_mb(use_cache=False)
            freed_mb = free_now - free_before
            if freed_mb > 100:  # At least 100MB freed = meaningful
                break

        if freed_mb > 0:
            logger.info(
                f"[VRAM-COORD] ComfyUI freed {freed_mb:.0f}MB, "
                f"now have {self.get_free_vram_mb(use_cache=False):.0f}MB free"
            )
        else:
            logger.info("[VRAM-COORD] ComfyUI /free returned OK but no VRAM freed (may have been idle)")

        self._last_comfyui_freed_mb = max(freed_mb, 0)
        self._last_comfyui_note = f"asked, saw {max(freed_mb, 0):.0f}MB come back"
        return (True, max(freed_mb, 0))

    def has_authoritative_reading(self) -> bool:
        """
        True only if the physical sensor answers right now.

        This is the health check the admission gate rests on, and the one a
        vision model's load rests on. When it is False, get_free_vram_mb()
        quietly falls back to a per-process torch figure that cannot see other
        processes — ComfyUI above all — so a grant given against it means only
        that this process's own allocations leave room, and says nothing about
        the card. The gate must never admit against that, and an image encoder
        must never be built against it. It forces a known state instead of
        trusting it.
        """
        return self._get_nvml_memory_info() is not None

    def nvml_configured(self) -> bool:
        """
        True if NVML came up at startup. Tells a runtime sensor loss (it worked,
        it is blind now: GPU off the bus, driver crash) apart from NVML never
        having been configured, which is a deployment matter and must not send
        the gate into a reclaim loop.
        """
        return self._nvml_available

    def emergency_reclaim_foreign(self) -> None:
        """
        Force the card back to a known state by removing every foreign holder the
        platform knows of. Called only on runtime sensor loss, so that afterwards
        this process is the only one using the GPU — and torch can measure that
        reliably. The blind spot is removed, not papered over.

          - OWNED CHILDREN FIRST: the llama-server processes this service
            spawned. They are the permanent exception to "this process is the
            only GPU user", so a reclaim that left them standing would leave
            exactly the blind spot it was called to remove — torch cannot see
            them, and the sensor that could is the one that just went. They are
            also the cheapest to lose: the next request spawns one again.
          - ComfyUI: hard restart of its systemd unit, which works even when
            ComfyUI is wedged and no longer answers POST /free.
          - Blacklisted-port zombies: SIGKILL by PID.

        The backends inside this process are not touched here — they are this
        process; the gate clears them by restarting itself while idle.
        """
        import signal
        import subprocess
        from config import VRAM_BLACKLISTED_PORTS, COMFYUI_PORT, COMFYUI_SYSTEMD_UNIT

        logger.error("[VRAM-COORD] EMERGENCY (sensor lost): ending owned child "
                     "processes")
        self.terminate_owned("emergency reclaim: the VRAM sensor is gone")

        try:
            from services.gpu_admission import get_gpu_admission
            get_gpu_admission().forget_resident("foreign VRAM reclaimed")
        except Exception:
            pass

        comfy_up = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            comfy_up = (sock.connect_ex(("127.0.0.1", COMFYUI_PORT)) == 0)
            sock.close()
        except Exception:
            comfy_up = False

        if comfy_up:
            logger.error("[VRAM-COORD] EMERGENCY (sensor lost): restarting %s to reclaim foreign VRAM",
                         COMFYUI_SYSTEMD_UNIT)
            try:
                r = subprocess.run(
                    ["sudo", "-n", "/usr/bin/systemctl", "restart", COMFYUI_SYSTEMD_UNIT],
                    check=False, timeout=90,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                )
                if r.returncode != 0:
                    logger.error("[VRAM-COORD] EMERGENCY: ComfyUI restart rc=%s: %s",
                                 r.returncode, (r.stderr or b"").decode("utf-8", "replace").strip())
            except Exception as e:
                logger.error("[VRAM-COORD] EMERGENCY: ComfyUI restart failed: %s", e)

        # Only processes that NVML actually reports as GPU users are killed. A
        # listening port is not evidence that something holds VRAM, and
        # _find_pid_for_port cannot see sockets owned by other users — it returns
        # None for most of them, which would name the wrong process in the log.
        gpu_pids = set()
        info = self._get_nvml_memory_info()
        if info:
            gpu_pids = {p.get("pid") for p in info.get("processes", [])}

        for port in VRAM_BLACKLISTED_PORTS:
            try:
                pid, cmdline = self._find_pid_for_port(port)
                if pid and pid not in gpu_pids:
                    logger.warning("[VRAM-COORD] EMERGENCY: PID %s on blacklisted port %s holds no "
                                   "GPU memory — left alone (%s)", pid, port, cmdline)
                elif pid:
                    logger.error("[VRAM-COORD] EMERGENCY: SIGKILL zombie PID %s on blacklisted port %s (%s)",
                                 pid, port, cmdline)
                    os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error("[VRAM-COORD] EMERGENCY: failed to kill PID on port %s: %s", port, e)

        # Give the driver a moment to reclaim before the caller re-reads.
        time.sleep(2.0)

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status for debugging/API.

        `gpu_processes` entries carry `owned` and `label`: an llama-server child
        of this service is neither this process nor a stranger, and a reader who
        cannot tell those apart has no way to see whose the memory is.
        `foreign_vram_mb` counts strangers only — children are already in
        loaded_models, and counting them twice is what made the foreign-VRAM
        threshold fire on our own loads.

        ONE NVML enumeration for the whole answer: the model collection takes
        it, the process list below reads the same one back out of the cache.
        Two walks per status call meant the two halves of one page could
        disagree about which processes were on the card.
        """
        all_models = self._collect_all_models()

        status = {
            "free_mb": self.get_free_vram_mb(),
            "total_mb": self.get_total_vram_mb(),
            "nvml_available": self._nvml_available,
            "registered_backends": list(self._backends.keys()),
            "loaded_models": [
                {
                    "backend": m.backend_id,
                    "model": m.model_id,
                    "vram_mb": m.vram_mb,
                    "priority": m.priority.name,
                    "in_use": m.in_use,
                    "last_used": m.last_used,
                }
                for m in all_models
            ],
            "eviction_in_progress": self._eviction_in_progress,
        }

        # Add NVML-specific info
        nvml_info = self._nvml_snapshot()
        if nvml_info is not None:
            status["nvml_free_mb"] = nvml_info["free_mb"]
            status["nvml_used_mb"] = nvml_info["used_mb"]
            status["foreign_vram_mb"] = nvml_info["foreign_mb"]
            status["expected_foreign_vram_mb"] = round(self._get_expected_foreign_vram_mb(), 1)
            status["gpu_processes"] = nvml_info["processes"]
        else:
            status["nvml_free_mb"] = None
            status["nvml_used_mb"] = None
            status["foreign_vram_mb"] = None
            status["expected_foreign_vram_mb"] = None
            status["gpu_processes"] = []

        # Blacklisted ports
        status["blacklisted_ports"] = self._check_blacklisted_ports()

        return status


# =============================================================================
# Singleton
# =============================================================================

_coordinator: Optional[VRAMCoordinator] = None


def get_vram_coordinator() -> VRAMCoordinator:
    """Get VRAMCoordinator singleton."""
    global _coordinator
    if _coordinator is None:
        _coordinator = VRAMCoordinator()
    return _coordinator


