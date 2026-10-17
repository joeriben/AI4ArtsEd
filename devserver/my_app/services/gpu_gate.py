"""
The gate: one heavy operation on the card at a time, plant-wide.

One card, one heavy operation at a time. Every process that puts weights on
the card or runs them — ComfyUI, driven from this process; VoxCPM in its own
process; Blender; a LoRA training — takes the single slot before it allocates,
through a lease (gpu_lease_client.py), and holds it until it is done. So does
the GPU service, until stage 8 takes it down: every hold of its own is a lease
here, taken over HTTP (routes/gpu_gate_routes.py) before its local slot.

Why a slot instead of a better estimate. What a model will cost cannot be
known before it is loaded, so any pre-flight number is a guess and stays one.
What CAN be known is that nobody else is allocating at the same moment.
Measured 2026-08-18: the coordinator of the time evicted, computed 49,392 MB
free, and the load ran out of memory anyway, because four other loads were in
flight in the same second. No sharper estimate would have caught that; taking
turns does.

The slot covers BOTH allocating phases, loading and the forward pass. The
30 GB that overflowed the card one night were allocated while loading, not
while generating.

Where it lives. Until stage 7 of the move to ComfyUI the gate was a module of
the GPU service (gpu_service/services/gpu_admission.py) and this process
leased it over HTTP. The GPU service is being taken down; the gate is not —
it serialises processes that outlive the take-down — so it lives here now, in
the process every lease holder already runs in or is driven from. A lease is
a call, not a request: nothing waits on a socket to itself. The one thing the
old host had that this one has not is a torch allocator of its own, and the
memory layer is rebuilt for that:

  - the card's free memory is read from the driver (NVML), which sees every
    process on the card, this one included;
  - room is made by asking ComfyUI to unload what it holds (POST /free) —
    nothing is evicted here, because nothing is loaded here. Until stage 8
    the GPU service keeps models resident as well, and it is not asked from
    here: what it holds is freed by its own coordinator, and a lease that
    needs that room is refused with the figures;
  - a sensor that stops answering refuses heavy operations with a sentence
    that names the hardware, and admits again the moment it answers. The old
    host restarted ComfyUI to get a truthful reading back; from here that
    would be a large action on thin evidence, and it is not taken.

Plain `threading`, acquired on a worker thread. Never an asyncio primitive:
the routes spin up a fresh event loop per request, and an asyncio primitive
shared across loops loses wakeups and wedges the thread.
"""

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Kinds whose hold is measured in hours, not in the seconds a generation takes.
# A LoRA training keeps the card for one to three hours; queueing behind it is
# not waiting, it is hanging. Whoever meets one is turned away at once with a
# sentence that says which, instead of parking a worker thread until the
# acquire budget runs out.
LONG_HOLD_KINDS = frozenset({"lora_training"})

# What to call a long hold when the sentence leaves the machine room. The kind
# is an internal name; the person who pressed a button and is being turned away
# reads this instead.
LONG_HOLD_NAMES = {"lora_training": "a LoRA training"}

# Two asks of ComfyUI closer together than this find nothing the first did not
# already take, and each one is an interruption for whatever ComfyUI is doing.
_FREE_ASK_MIN_GAP_S = 10.0


class GpuBusy(Exception):
    """
    The GPU cannot admit an operation: the queue was full, the wait ran out, or
    the memory is physically not there after ComfyUI was asked to make room.

    Callers MUST pass this on as busy (HTTP 503, GpuBusyError). Never as an
    out-of-memory error, never as a silent None — a caller that cannot tell
    "busy" from "broken" retries the wrong one.
    """

    def __init__(self, message: str, free_mb: float = 0.0, required_mb: float = 0.0,
                 reason: str = "", holder_kind: str = "", waiting: int = 0):
        super().__init__(message)
        self.free_mb = free_mb
        self.required_mb = required_mb
        # WHICH refusal this is, as a token. The sentence above says the same
        # thing in words, and a surface that reads the words drifts the moment
        # a word changes: all four refusals arrived at the workshop tables as
        # "queue full", including the six hours a LoRA training held the card
        # on 2026-08-28. The token travels with the refusal so that the
        # sentence a person reads is chosen from the state, never from prose
        # matching.
        self.reason = reason or "busy"
        # long_hold: the lease kind that is holding the card (lora_training),
        # so the surface can say what it is doing.
        self.holder_kind = holder_kind
        # queue_full: how many were already in line when this one was refused.
        self.waiting = waiting


@dataclass
class Lease:
    kind: str          # 'comfyui' | 'voxcpm' | 'lora_training' | ...
    model_id: str
    required_mb: float
    priority: int      # carried for the record; nothing is evicted by priority here
    source: str        # 'remote': the holder is another process (ComfyUI, VoxCPM, ...)
    # `id` names the lease wherever the gate is read — the status, the plan,
    # the log. `token` is what releases it and stays with its holder: the
    # readings are open to every visitor of the settings page.
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    token: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)
    admitted_at: float = 0.0   # set when the slot is actually taken, not when queued
    last_heartbeat: float = field(default_factory=time.time)
    label: str = ""            # the run this belongs to, so a queue can be read
    overtaken: int = 0         # how often somebody behind was let through first
    free_at_admit_mb: float = 0.0   # free VRAM the moment this run was let in
    min_free_mb: float = 0.0        # least free VRAM seen while it ran
    max_free_mb: float = 0.0        # most free VRAM seen while it ran
    failed: bool = False            # the body raised; this run loaded nothing
    workload: str = ""         # the output config, when the caller named one
    was_resident: bool = True  # was the model already on the card when this started
    refused: bool = False      # turned away at admission: nothing ran, the card is as it was
    holder: str = ""           # the process holding it, where the lease came over HTTP ("gpu_service")
    beats: int = 0             # heartbeats received; none within the grace after granting: the holder is gone
    granted_at: float = 0.0    # when the token went to its holder (admission done)

    @property
    def stats_key(self) -> str:
        """What durations are recorded against.

        The output config where one is known, the model otherwise. NOT the
        affinity key: a checkpoint answers "what has to be on the card", a
        config answers "how long will it be there", and several configs share
        one checkpoint here.

        What is measured: 93 runs of the wan2.2 video weights spread from 10.8 s
        to 170.1 s, a range whose middle of 19.9 s is a duration none of them
        had. What is NOT established is that config mixing is the whole cause —
        the ComfyUI lease covers loading and running together, so a cold start
        sits inside the same reading, and this split cannot separate that. It
        removes one identified source of the spread; whether the rest of it
        survives is a question for the measurements, not for this comment.

        A LOAD is the exception and stays keyed by model: how long weights take
        to arrive is a property of the bytes, not of what is asked of them
        afterwards, and the surcharge is looked up by model id.
        """
        if self.kind.endswith("-load"):
            return self.model_id or self.kind
        return self.workload or self.model_id or self.kind

    @property
    def weights_id(self) -> str:
        """The model itself, for the records that really are about the model."""
        return self.model_id or self.kind

    @property
    def stats_kind(self) -> str:
        """Cold and warm are recorded apart, because they are not one thing.

        On the ComfyUI path there is no separate load lease at all — the
        checkpoint comes off disk inside the submitted workflow, so loading and
        running sit in ONE reading. Measured over 94 real runs of a single
        config with fixed resolution, frame count and step count: 74 of them
        between 10 and 19 s, one at 170 s. Nothing about the work differed;
        the long ones are the ones that had to load first. Averaged together
        they produce a number no run has, and the spread gate then silences the
        model entirely — which is what happened to video.

        Loads are not bucketed: a load is cold by definition, and its key is
        looked up as "<kind>-load" elsewhere.
        """
        if self.kind.endswith("-load"):
            return self.kind
        return self.kind if self.was_resident else f"{self.kind}-cold"

    @property
    def affinity_key(self) -> str:
        """What has to be loaded for this run.

        Two runs with the same key can follow each other without a model
        change; two with different keys cost a swap. The load and the forward
        pass of the same model share a key — the load is what makes the model
        resident for the pass that follows.
        """
        return self.model_id or self.kind


class CardSensor:
    """The card as the driver reports it: free and total memory, and who holds
    what, through NVML. Sees every process on the card, which is the reason it
    stands here rather than a torch figure of this process — this process
    allocates nothing on the card, and a torch figure would read zero.

    `configured` says whether NVML came up at start: a sensor that never
    answered is a deployment matter (nvidia-ml-py missing, no driver), one
    that answered and stopped is a runtime loss, and the gate treats the two
    apart. `read()` answers None whenever the driver does not answer now.
    """

    def __init__(self, comfyui_port: str = ""):
        self.configured = False
        self.why = ""
        self._handle = None
        self._comfyui_port = str(comfyui_port or "")
        try:
            import pynvml
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.configured = True
        except Exception as e:  # noqa: BLE001 — the reason is kept, not the exception
            self.why = f"{type(e).__name__}: {e}"

    def free_mb(self) -> Optional[float]:
        """Free memory on the card in MB, or None when the driver does not answer."""
        if not self.configured:
            return None
        try:
            import pynvml
            return pynvml.nvmlDeviceGetMemoryInfo(self._handle).free / (1024 * 1024)
        except Exception as e:  # noqa: BLE001
            self.why = f"{type(e).__name__}: {e}"
            return None

    def name(self) -> str:
        if not self.configured:
            return ""
        try:
            import pynvml
            raw = pynvml.nvmlDeviceGetName(self._handle)
            return raw.decode() if isinstance(raw, bytes) else str(raw)
        except Exception:  # noqa: BLE001
            return ""

    def read(self) -> Optional[Dict[str, Any]]:
        """Memory and processes in one reading, or None.

        Every process is labelled by what it is to this platform: this process,
        a child of it (Blender, a LoRA training), ComfyUI's instance (found
        by the port on its command line), the VoxCPM worker, the GPU service
        (by the directory it runs in, until stage 8 takes it down), or
        foreign. The driver keeps two lists, compute and graphics contexts;
        a Blender render is on the second one, so both are read. `foreign_mb`
        counts the strangers only. NVML reports no memory for a process it cannot
        attribute; that stays `vram_unknown`, apart from a zero, because a
        reading that took the one for the other would call a resident model
        nothing.
        """
        if not self.configured:
            return None
        try:
            import pynvml
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            procs = []
            seen_pids = set()
            for read_list in (pynvml.nvmlDeviceGetComputeRunningProcesses,
                              pynvml.nvmlDeviceGetGraphicsRunningProcesses):
                try:
                    listed = read_list(self._handle)
                except Exception:  # noqa: BLE001 — the memory reading stands without the list
                    listed = []
                for proc in listed:
                    if int(proc.pid) in seen_pids:
                        continue      # on both lists: one process, one line
                    seen_pids.add(int(proc.pid))
                    procs.append(proc)
        except Exception as e:  # noqa: BLE001
            self.why = f"{type(e).__name__}: {e}"
            return None
        me = os.getpid()
        processes = []
        foreign_mb = 0.0
        for proc in procs:
            pid = int(proc.pid)
            unknown = proc.usedGpuMemory is None
            vram_mb = (proc.usedGpuMemory or 0) / (1024 * 1024)
            cmdline = _proc_cmdline(pid)
            label = _label_process(pid, cmdline, me, self._comfyui_port)
            foreign = label == "foreign"
            if foreign:
                foreign_mb += vram_mb
            processes.append({
                "pid": pid,
                "vram_mb": round(vram_mb, 1),
                "vram_unknown": unknown,
                "foreign": foreign,
                "owned": label in _CHILD_LABELS,
                "label": label,
                "cmdline": cmdline,
            })
        return {
            "total_mb": round(mem.total / (1024 * 1024), 1),
            "used_mb": round(mem.used / (1024 * 1024), 1),
            "free_mb": round(mem.free / (1024 * 1024), 1),
            "foreign_mb": round(foreign_mb, 1),
            "processes": processes,
        }


def _proc_cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return fh.read(512).replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return ""


def _proc_parent(pid: int) -> Optional[int]:
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="replace") as fh:
            tail = fh.read().rsplit(")", 1)[1].split()
        return int(tail[1])
    except (OSError, IndexError, ValueError):
        return None


def _short_cmdline(cmdline: str) -> str:
    """What a process runs, for a line on the settings page: the script with
    its directory (`voxcpm_service/server.py`), or for a binary its name and
    the file it was given with -m (`llama-server -m <model file>`). Two
    llama-server children of the GPU service must not read alike, and no
    line carries the host's paths."""
    words = cmdline.split()
    if not words:
        return ""
    scripts = [p for p in words if p.endswith(".py")]
    if scripts:
        return "/".join(scripts[0].split("/")[-2:])
    line = os.path.basename(words[0])
    if "-m" in words[1:]:
        at = words.index("-m", 1)
        if at + 1 < len(words):
            line += " -m " + os.path.basename(words[at + 1])
    return line[:80]


def _proc_cwd(pid: int) -> str:
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return ""


_CHILD_LABELS = ("child", "blender", "lora_training")


def _child_label(cmdline: str) -> str:
    """What a child of this process is, by what it runs: Blender renders the
    3D preview (lease kind `blender`), kohya's sd3_train_network.py trains a
    LoRA (kind `lora_training`) — named like the kind, so the line reads
    "in use" while that lease holds the slot. Any other child keeps the
    plain label."""
    words = cmdline.split()
    first = os.path.basename(words[0]) if words else ""
    if first.startswith("blender"):
        return "blender"
    if any(w.endswith("train_network.py") for w in words):
        return "lora_training"
    return "child"


def _label_process(pid: int, cmdline: str, me: int, comfyui_port: str = "") -> str:
    """'self' | 'comfyui' | 'blender' | 'lora_training' | 'child' | 'voxcpm' |
    'gpu_service' | 'foreign' — what a process on the card is to this
    platform. ComfyUI is recognised by the port it was started on, which
    stands on its command line, and before the parent is looked at: a
    ComfyUI this process started (comfyui_manager) is a child too, and its
    models are listed by name. A child by what it runs (_child_label); the
    VoxCPM worker by its service directory on the command line (it is
    started through a shell, so it is no child of this process); the GPU
    service, until stage 8 takes it down, by the directory it runs in (its
    command line is `python server.py`, which says nothing). A ComfyUI
    started with the port further than 512 bytes along reads as foreign,
    and the command line beside the label says so."""
    if pid == me:
        return "self"
    if comfyui_port and cmdline and _names_port(cmdline, comfyui_port):
        return "comfyui"
    if _proc_parent(pid) == me:
        return _child_label(cmdline)
    if "voxcpm_service" in cmdline:
        return "voxcpm"
    if os.path.basename(_proc_cwd(pid)) == "gpu_service":
        return "gpu_service"
    return "foreign"


def _names_port(cmdline: str, port: str) -> bool:
    import re
    return re.search(rf"(?<!\d){re.escape(port)}(?!\d)", cmdline) is not None


class GpuGate:
    """Single-slot, plant-wide admission gate. Singleton via get_gpu_gate()."""

    def __init__(self, sensor: Optional[CardSensor] = None):
        self._cv = threading.Condition()
        self._active: Optional[Lease] = None
        self._waiters: List[Lease] = []              # FIFO
        self._leases: Dict[str, Lease] = {}          # token -> active lease
        self._degraded = False          # runtime sensor loss; heavy ops are refused
        self._warned_no_sensor = False  # one-time deployment warning
        self._blind_samples = 0         # consecutive failed sensor readings
        self._ema_hold_s = 0.0          # moving average of how long a run holds the slot
        self._last_key: Optional[str] = None   # what ran last = what is resident
        self._overtakes_granted = 0     # how often affinity reordered, for the record
        self._prefetch_in_flight: Optional[str] = None   # at most one warm-up at a time
        self._prefetch_started_at = 0.0
        self._reserved_key: Optional[str] = None   # just loaded — its own run goes next
        self._reserved_until = 0.0
        self._last_free_ask_at = 0.0    # when ComfyUI was last asked to unload
        self._last_free_ask_note = "not asked yet"

        import config as _cfg
        self._acquire_timeout_s = float(getattr(_cfg, "GPU_ADMISSION_ACQUIRE_TIMEOUT_S", 5400.0))
        self._heartbeat_timeout_s = float(getattr(_cfg, "GPU_ADMISSION_HEARTBEAT_TIMEOUT_S", 120.0))
        self._first_beat_grace_s = float(getattr(_cfg, "GPU_ADMISSION_FIRST_BEAT_GRACE_S", 30.0))
        self._reaper_interval_s = float(getattr(_cfg, "GPU_ADMISSION_REAPER_INTERVAL_S", 5.0))
        self._max_waiters = int(getattr(_cfg, "GPU_ADMISSION_MAX_WAITERS", 40))
        self._blind_samples_to_declare = int(getattr(_cfg, "GPU_ADMISSION_BLIND_SAMPLES", 3))
        self._ema_hold_s = float(getattr(_cfg, "GPU_ADMISSION_ASSUMED_RUN_S", 90.0))
        self._affinity_enabled = bool(getattr(_cfg, "GPU_ADMISSION_AFFINITY", True))
        self._affinity_max_overtakes = int(getattr(_cfg, "GPU_ADMISSION_MAX_OVERTAKES", 3))
        self._affinity_max_wait_s = float(getattr(_cfg, "GPU_ADMISSION_AFFINITY_MAX_WAIT_S", 300.0))
        self._prefetch_enabled = bool(getattr(_cfg, "GPU_ADMISSION_PREFETCH", False))
        self._prefetch_headroom_mb = float(getattr(_cfg, "GPU_ADMISSION_PREFETCH_HEADROOM_MB", 10240.0))
        self._prefetch_min_remaining_s = float(getattr(_cfg, "GPU_ADMISSION_PREFETCH_MIN_REMAINING_S", 45.0))
        self._post_load_reserve_s = float(getattr(_cfg, "GPU_ADMISSION_POST_LOAD_RESERVE_S", 5.0))
        self._free_wait_s = float(getattr(_cfg, "GPU_ADMISSION_FREE_WAIT_S", 30.0))
        self._comfyui_port = str(getattr(_cfg, "COMFYUI_PORT", ""))

        self._sensor = sensor if sensor is not None else CardSensor(self._comfyui_port)
        if not self._sensor.configured:
            logger.error(
                "[GPU-GATE] The card's memory cannot be read (NVML: %s). Admission "
                "serialises the heavy operations and cannot check the room they "
                "ask for — a DEPLOYMENT matter: nvidia-ml-py in the DevServer's "
                "venv, and a driver that answers nvidia-smi.", self._sensor.why)

        self._reaper = threading.Thread(
            target=self._reaper_loop, name="gpu-gate-reaper", daemon=True
        )
        self._reaper.start()
        logger.info(
            "[GPU-GATE] Initialized (one slot; acquire_timeout=%.0fs, "
            "heartbeat_timeout=%.0fs, max_waiters=%d, sensor=%s)",
            self._acquire_timeout_s, self._heartbeat_timeout_s, self._max_waiters,
            "NVML" if self._sensor.configured else "none")

    # ---------------------------------------------------------------- leases
    def acquire(self, kind: str, model_id: str, required_mb: float, priority: int = 2,
                label: str = "", workload: str = "",
                timeout_s: Optional[float] = None, holder: str = "") -> str:
        """
        Take the slot for a heavy operation. Returns a token; the slot stays
        held until release() or until the reaper finds the heartbeat gone.
        Raises GpuBusy.

        timeout_s shortens the wait for a caller that would rather hear "busy"
        than queue for the full acquire budget. `holder` names the process
        behind a lease taken over HTTP (the GPU service says "gpu_service"),
        so its line on the settings page reads "in use" while it holds.
        """
        lease = Lease(kind=kind, model_id=model_id, required_mb=float(required_mb),
                      priority=int(priority), source="remote", label=label,
                      workload=workload, holder=holder)
        self._wait_for_slot(lease, timeout_s)
        with self._cv:
            self._leases[lease.token] = lease
        try:
            self._admit(lease)
        except BaseException:
            # Refused at admission: nothing ran. Without the flags, a lease
            # whose admission raised after the admitted_at stamp recorded its
            # near-zero age as a valid hold, and forgot what is resident
            # although the card is as it was.
            lease.failed = True
            lease.refused = True
            self._release_active(lease)
            raise
        # Admission can take a while — ComfyUI unloading its models, in the
        # worst case the whole free-wait. The heartbeat clock starts once the
        # token is on its way back, or the reaper could collect a lease whose
        # holder never had a chance to report in.
        with self._cv:
            lease.last_heartbeat = time.time()
            lease.granted_at = lease.last_heartbeat
        logger.info("[GPU-GATE] Lease acquired: %s (%s/%s)", lease.id, kind, model_id)
        return lease.token

    def heartbeat(self, token: str) -> bool:
        with self._cv:
            lease = self._leases.get(token)
            if lease is None:
                return False
            lease.last_heartbeat = time.time()
            lease.beats += 1
            return True

    def release(self, token: str, failed: bool = False) -> bool:
        with self._cv:
            lease = self._leases.pop(token, None)
            if lease is None:
                return False
            if failed:
                # The owner reports the run did not complete — aborted in the
                # queue, or a render that was interrupted. The held time is
                # not a duration any completed run has.
                lease.failed = True
            if self._active is lease:
                self._note_hold(lease)
                self._active = None
            self._cv.notify_all()
        logger.info("[GPU-GATE] Lease released: %s", lease.id)
        return True

    # ---------------------------------------------------------------- internals
    def _note_hold(self, lease: Lease) -> None:
        """Remember how long that run held the slot.

        Reported, not acted on. The queue length alone says nothing about the
        wait — twenty images and twenty videos are the same number and a very
        different afternoon — so this is what an operator can look at. It is
        deliberately NOT used to turn anyone away. Caller holds _cv.
        """
        if not lease.admitted_at:
            return
        if lease.refused:
            # Turned away at admission: nothing ran, so there is no hold to
            # measure and no new resident. Where ComfyUI was asked to make
            # room on the way, forget_resident() has already said so.
            return
        held = time.time() - lease.admitted_at
        if held <= 0:
            return
        if not lease.failed:
            # The ordering EMA stands in for the duration of runs nobody has
            # measured. An aborted hold is slot occupancy, but it is not a run
            # duration — a handful of closed tabs multiplied the EMA toward
            # its 10 s floor and distorted the simulated order.
            self._ema_hold_s = max(10.0, min(900.0, 0.7 * self._ema_hold_s + 0.3 * held))
        # What ran last is what is loaded — the signal affinity reads. A FAILED
        # run that had to LOAD answers "unknown", not "me": claiming residency
        # priced the same-model retry with the warm figure while the card had
        # to load — the one direction the forecast promised never to err in.
        # A failed run whose model was already resident is the opposite case:
        # its failure unloads nothing, and answering "unknown" there sent the
        # NEXT same-model run into the cold bucket with a warm success —
        # two of those and the spread gate silences the config for good.
        self._last_key = (None if (lease.failed and not lease.was_resident)
                          else lease.affinity_key)
        # A load exists FOR the run that follows it, and that run queues a
        # moment after the load lets go. Without this short reservation
        # another model slips into that moment and the load was paid for
        # nothing — measured: a video took the slot between SD3.5's load and
        # SD3.5's own image.
        if (lease.kind.endswith("-load") and not lease.failed
                and self._load_is_claimable(lease)):
            self._reserved_key = lease.affinity_key
            self._reserved_until = time.time() + self._post_load_reserve_s
        try:
            from my_app.services.gpu_model_stats import get_model_stats
            stats = get_model_stats()
            # A run that died in the slot held it for a length that says
            # nothing about how long that model takes, and it is exactly the
            # kind of short reading that drags an average down.
            if not lease.failed:
                stats.record_hold(lease.stats_kind, lease.stats_key, held,
                                  model_id=lease.weights_id)
            # Free memory fell by this much while the run owned the slot, and
            # with the slot held nothing else was allocating — so the drop is
            # this run's own footprint, measured rather than declared.
            top = max(lease.max_free_mb, lease.free_at_admit_mb)
            if top > 0 and lease.min_free_mb > 0 and not lease.failed:
                used = top - lease.min_free_mb
                if used > 0:
                    # Footprint stays keyed by MODEL: what a config costs in
                    # memory is what its weights cost, and two configs on one
                    # checkpoint occupy the same card.
                    stats.record_footprint(lease.kind, lease.model_id, used)
        except Exception as e:
            logger.debug("[GPU-GATE] Could not record model statistics: %s", e)

    # Kinds whose inference does NOT take the slot. Loading them does — the
    # weights land on the card — but nothing of that model ever queues
    # afterwards, so holding the card open for it is pure idle time in a room
    # that is waiting. The safety chain's language models were like this;
    # every other holder runs its forward pass inside the slot.
    _RUN_KINDS_WITHOUT_A_SLOT = frozenset({"llm"})

    def _load_is_claimable(self, lease: Lease) -> bool:
        """Does a run of this model come back through the gate after loading?

        Only then is it worth holding the slot for it. `voxcpm-load` is
        followed by `voxcpm` on the same key. This cannot be decided from the
        measurements: the very first load of a model has no run recorded yet,
        and that first load is exactly the one whose handover was seen to fail.
        """
        run_kind = lease.kind[:-len("-load")]
        return run_kind not in self._RUN_KINDS_WITHOUT_A_SLOT

    def _pick_next_locked(self) -> Optional[Lease]:
        """Whose turn it is. Caller holds _cv.

        Order of precedence, and the order matters:

        1. Anybody who has waited too long, or has been passed too often,
           goes now. This is checked FIRST and in arrival order, so no amount
           of affinity can push a person past the bound. Being overtaken is a
           loan against a fixed limit, never an open one.
        2. Otherwise, whoever needs the model that is already loaded. A swap
           between two models costs a load — measured at 110 s for SD3.5
           Large — and that time is paid by everybody still in line, not just
           by the run that caused it. Grouping the same model saves the whole
           room a load per switch.
        3. Otherwise the head of the queue, as before.

        Deterministic: every waiting thread evaluates this under the same lock
        on the same state, so exactly one of them sees itself here.
        """
        return self._pick_from(self._waiters, self._last_key, time.time())

    def _wait_for_slot(self, lease: Lease, timeout_s: Optional[float] = None) -> None:
        budget = self._acquire_timeout_s if timeout_s is None else float(timeout_s)
        deadline = time.time() + budget
        with self._cv:
            # A waiting request parks a worker thread. Unbounded waiting would
            # eat the whole pool and take the pages down with it, so the
            # queue has an end and says so instead of letting everything silt up.
            # A hold measured in hours is not something to queue behind. The
            # waiter would park a worker thread for the whole acquire budget and
            # then be told "busy" anyway; said at once, it is the same answer
            # without the dead time, and it names what is holding the card.
            active = self._active
            if (active is not None
                    and active.kind in LONG_HOLD_KINDS
                    and lease.kind not in LONG_HOLD_KINDS):
                raise GpuBusy(
                    "device busy: %s is running and will hold the card for a while yet"
                    % LONG_HOLD_NAMES.get(active.kind, "a long operation"),
                    reason="long_hold", holder_kind=active.kind,
                )
            if len(self._waiters) >= self._max_waiters:
                raise GpuBusy(
                    "device busy: %d operations already waiting for the GPU" % len(self._waiters),
                    reason="queue_full", waiting=len(self._waiters),
                )
            # No refusal on an estimate, and none on a queue that is merely long.
            # Whoever pressed keeps their place: turning somebody away sends them
            # to the BACK of the line when they press again, while others move up
            # past them. Waiting is fair, being sent to the back is not.
            self._waiters.append(lease)
            try:
                while not (self._active is None and self._pick_next_locked() is lease
                           and not self._reserved_for_someone_else(lease)):
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        raise GpuBusy(
                            "device busy: waited %.0fs for the GPU" % budget,
                            reason="wait_timeout",
                        )
                    self._cv.wait(timeout=min(remaining, 1.0))
            except BaseException:
                if lease in self._waiters:
                    self._waiters.remove(lease)
                self._cv.notify_all()
                raise
            # Everybody this run passed carries one more overtake, and the
            # bound above turns that into a guarantee: after a fixed number
            # they go next, whatever is resident.
            idx = self._waiters.index(lease)
            if idx > 0:
                for w in self._waiters[:idx]:
                    w.overtaken += 1
                self._overtakes_granted += 1
                _now = time.time()
                if (_now - lease.created_at) >= self._affinity_max_wait_s:
                    why = "it has waited past the fairness limit"
                elif lease.overtaken >= self._affinity_max_overtakes:
                    why = "it has been passed as often as it may be"
                elif (self._reserved_key is not None
                      and lease.affinity_key == self._reserved_key):
                    why = "its model was just loaded for it"
                else:
                    why = "its model is already loaded"
                logger.info("[GPU-GATE] %s/%s goes ahead of %d waiting — %s "
                            "(they have been passed %s times so far, limit %d)",
                            lease.kind, lease.model_id, idx, why,
                            [w.overtaken for w in self._waiters[:idx]],
                            self._affinity_max_overtakes)
            self._waiters.remove(lease)
            if self._reserved_key is not None and lease.affinity_key == self._reserved_key:
                self._reserved_key = None
            self._active = lease
            # Whether this run finds its model on the card or has to put it
            # there decides its duration more than anything else about it, and
            # only this moment knows the answer.
            lease.was_resident = (lease.affinity_key == self._last_key)
            lease.admitted_at = time.time()
            lease.last_heartbeat = lease.admitted_at

    def _admit(self, lease: Lease) -> None:
        """
        The slot is held, so nothing else is allocating. Establish a trustworthy
        physical reading, make room if the operation asks for some, and admit —
        or raise GpuBusy on a real, physical shortfall.

        Failsafe by design, which is neither fail-open nor fail-closed. The
        decision rests on the physical sensor: NVML free memory, every process
        on the card included.

        - Sensor answering: trust it, make room, admit.
        - Sensor lost at runtime (it answered at start, it is blind now — GPU
          off the bus, driver crash): one missed reading is a hiccup, not a
          diagnosis; after GPU_ADMISSION_BLIND_SAMPLES in a row heavy
          operations are refused — with a message that names a hardware fault,
          not a busy card — and admitted again the moment the sensor answers.
        - NVML never configured: a deployment matter, not a runtime failure. Say
          so once, loudly, serialise, and do not thrash.

        Room is made by asking ComfyUI to unload its models (POST /free), once
        per admission and never twice within _FREE_ASK_MIN_GAP_S; then the
        sensor is read until the room is there or GPU_ADMISSION_FREE_WAIT_S has
        passed. Nothing is evicted from this process, because nothing is
        loaded in it.
        """
        free = self._sensor.free_mb()
        if free is not None:
            if self._degraded:
                logger.info("[GPU-GATE] VRAM sensor is answering again — degraded state cleared")
            self._blind_samples = 0
            self._degraded = False
        elif not self._sensor.configured:
            if not self._warned_no_sensor:
                self._warned_no_sensor = True
                logger.error(
                    "[GPU-GATE] NVML not configured (%s): admission serialises "
                    "the heavy operations and cannot see the card's memory. "
                    "DEPLOYMENT issue — install nvidia-ml-py in the DevServer's "
                    "venv. Heavy ops proceed WITHOUT a memory guarantee until "
                    "that is fixed.", self._sensor.why)
        else:
            # The sensor answered at start and does not answer now. One failed
            # sample is a hiccup, not a diagnosis.
            self._blind_samples += 1
            if self._blind_samples < self._blind_samples_to_declare:
                logger.warning("[GPU-GATE] VRAM sensor missed a reading (%d/%d) admitting %s",
                               self._blind_samples, self._blind_samples_to_declare, lease.kind)
            else:
                self._degraded = True
                # Admitting here would mean allocating against a figure nobody
                # has. Deliberately NOT worded as "busy": this is a hardware
                # fault, and telling somebody to try again in a moment sends
                # them into a loop that cannot succeed.
                raise GpuBusy(
                    "GPU not reachable: the VRAM sensor is not answering (%s), so no "
                    "heavy operation can run. Check the driver / nvidia-smi."
                    % (self._sensor.why or "no reading"),
                    # Its own token, so no surface reads "busy" off it and
                    # tells somebody to try again in a moment.
                    reason="sensor_lost",
                )

        # A warm-up may be putting another model on the card right now. It was
        # started for whoever was next in line, and if that is this run, the
        # warm-up IS this run's load — go ahead. If it is a different model,
        # wait for it to finish: admitting now would mean two heavy
        # allocations at once, which is the one thing this gate exists to
        # prevent. The wait is short and bounded; a warm-up is a tiny job.
        deadline = time.time() + 120.0
        while True:
            with self._cv:
                pf = self._prefetch_in_flight
                if not pf or pf == lease.affinity_key:
                    break
            if time.time() > deadline:
                logger.warning("[GPU-GATE] Warm-up of %s has not finished in 120s — "
                               "admitting %s anyway rather than holding the queue",
                               pf, lease.model_id)
                break
            logger.info("[GPU-GATE] %s waits for the warm-up of %s to finish",
                        lease.model_id, pf)
            # This wait happens with the slot already held, before the caller
            # has been handed its token — so the lease would sit here burning
            # its own heartbeat budget and be reaped mid-admission, handing
            # back a dead token while the run went ahead unslotted.
            with self._cv:
                lease.last_heartbeat = time.time()
            time.sleep(1.0)

        # The starting reading, so the run's own footprint can be measured
        # against it while it holds the slot (sampled by the reaper).
        if free is not None and free > 0:
            lease.free_at_admit_mb = free
            lease.min_free_mb = free
            lease.max_free_mb = free

        if lease.required_mb <= 0:
            # Serialization only: a ComfyUI run makes its own room inside the
            # workflow, a warm VoxCPM worker has its weights already.
            logger.info("[GPU-GATE] Admitted %s/%s (serialize only, lease %s)",
                        lease.kind, lease.model_id, lease.id)
            return
        if free is None:
            logger.warning("[GPU-GATE] Admitted %s/%s asking for %.0fMB WITHOUT a memory "
                           "check — the sensor is not configured (lease %s)",
                           lease.kind, lease.model_id, lease.required_mb, lease.id)
            return

        note = "the card holds enough"
        if free < lease.required_mb:
            asked, note = self._ask_comfyui_to_free(lease, free)
            if asked:
                asked_at = time.time()
                free = self._wait_for_room(lease.required_mb, free, lease)
                if free < lease.required_mb:
                    # Asked, and the room did not come — a different state of
                    # the world from "asked, and it did", and from "never
                    # asked": the time waited is what tells a ComfyUI that
                    # unloaded nothing from one that was still rendering when
                    # the wait ran out.
                    note = ("ComfyUI was asked to unload its models and %.0fs later "
                            "the room was still short" % (time.time() - asked_at))
        if free < lease.required_mb:
            raise GpuBusy(
                "device busy: %s cannot get %.0fMB — %.0fMB free; %s"
                % (lease.kind, lease.required_mb, free, note),
                free_mb=free, required_mb=lease.required_mb,
                reason="no_memory",
            )
        logger.info("[GPU-GATE] Admitted %s/%s (need %.0fMB, free %.0fMB, lease %s)",
                    lease.kind, lease.model_id, lease.required_mb, free, lease.id)

    def _ask_comfyui_to_free(self, lease: Lease, free: float):
        """Ask ComfyUI to unload everything it holds. (asked, note).

        `asked` False means the request was never sent, and the note says why;
        the two are kept apart because "ComfyUI freed nothing" and "ComfyUI
        was never asked" are different states of the world, and a refusal
        that names the wrong one sends the operator to the wrong place.

        Safe to ask with the slot held: no platform run is on ComfyUI while
        this lease holds the card. A warm-up of the warm-ahead worker may be;
        the worker claims a prefetch first, and admission waited for that
        above.
        """
        now = time.time()
        since = now - self._last_free_ask_at
        if since < _FREE_ASK_MIN_GAP_S:
            note = ("ComfyUI was asked to unload %.0fs ago and is not asked again "
                    "within %.0fs" % (since, _FREE_ASK_MIN_GAP_S))
            self._last_free_ask_note = note
            return False, note
        if not self._comfyui_port:
            note = "ComfyUI's port is not configured, so it cannot be asked to unload"
            self._last_free_ask_note = note
            return False, note
        # What ComfyUI holds is the most the ask can free. Until stage 8 the
        # GPU service keeps models of its own resident, and only its own
        # coordinator frees those: a shortfall larger than ComfyUI's holdings
        # is refused with the figures instead of being answered with an
        # unload that cannot make the room.
        reading = self._sensor.read()
        if reading is not None:
            comfy_mb = sum(p["vram_mb"] for p in reading["processes"] if p["label"] == "comfyui")
            others = ["%s (%.0fMB)" % (p["label"], p["vram_mb"]) for p in reading["processes"]
                      if p["label"] not in ("self", "comfyui") and p["vram_mb"] > 0]
            if comfy_mb > 0 and free + comfy_mb < lease.required_mb:
                note = ("ComfyUI holds %.0fMB and freeing all of it would still leave %.0fMB "
                        "short; the rest of the card is held by %s, and only those processes "
                        "free what they hold"
                        % (comfy_mb, lease.required_mb - free - comfy_mb,
                           ", ".join(others) or "processes the driver could not attribute"))
                self._last_free_ask_note = note
                return False, note
        self._last_free_ask_at = now
        with self._cv:
            # The holder has no token yet and cannot report in, and the
            # request below is allowed a minute; the reaper must not collect
            # the lease meanwhile.
            lease.last_heartbeat = now
        url = f"http://127.0.0.1:{self._comfyui_port}/free"
        logger.info("[GPU-GATE] %s/%s needs %.0fMB and %.0fMB are free — asking ComfyUI "
                    "to unload its models", lease.kind, lease.model_id,
                    lease.required_mb, free)
        try:
            import requests
            # An administrative request, not a model call. ComfyUI answers it
            # at once and sets two flags; the unload itself runs on its prompt
            # worker, after the prompt that is executing if one is — which is
            # why the room is waited for (_wait_for_room) and never read off
            # this answer.
            resp = requests.post(url, json={"unload_models": True, "free_memory": True},
                                 timeout=(5, 60))
        except Exception as e:  # noqa: BLE001 — the reason goes into the sentence
            note = f"ComfyUI did not take the request to unload ({type(e).__name__}: {e})"
            self._last_free_ask_note = note
            return False, note
        if not 200 <= resp.status_code < 300:
            note = f"ComfyUI answered the request to unload with HTTP {resp.status_code}"
            self._last_free_ask_note = note
            return False, note
        # Everything ComfyUI held is going, so the gate must stop believing
        # any of it is still loaded — or the queue keeps being reordered
        # toward a model that is not on the card.
        self.forget_resident("ComfyUI was asked to free everything")
        note = "ComfyUI was asked to unload its models"
        self._last_free_ask_note = note
        return True, note

    def _wait_for_room(self, required_mb: float, free: float, lease: Lease) -> float:
        """Read the sensor until `required_mb` are free or the wait is over.
        The last reading, so a refusal can say what the card held at the end.

        The lease's heartbeat is refreshed while this waits: the holder has no
        token yet and cannot report in, and the reaper must not collect a
        lease whose admission is still making room."""
        deadline = time.time() + self._free_wait_s
        last = free
        while time.time() < deadline:
            with self._cv:
                lease.last_heartbeat = time.time()
            time.sleep(0.5)
            now_free = self._sensor.free_mb()
            if now_free is None:
                continue
            last = now_free
            if last >= required_mb:
                break
        logger.info("[GPU-GATE] %.0fMB free after ComfyUI was asked to unload", last)
        return last

    def _release_active(self, lease: Lease) -> None:
        with self._cv:
            self._leases.pop(lease.token, None)
            if self._active is lease:
                self._note_hold(lease)
                self._active = None
            self._cv.notify_all()

    def _reaper_loop(self) -> None:
        while True:
            time.sleep(self._reaper_interval_s)
            try:
                with self._cv:
                    if (self._prefetch_in_flight
                            and time.time() - self._prefetch_started_at > 300):
                        logger.warning("[GPU-GATE] Prefetch claim for %s expired — "
                                       "releasing it so warming can happen again",
                                       self._prefetch_in_flight)
                        self._prefetch_in_flight = None
                self._sample_active_footprint()
                with self._cv:
                    a = self._active
                    if a is not None:
                        now = time.time()
                        age = now - a.last_heartbeat
                        # A lease nobody ever reported in on is a holder that
                        # left before the token reached it — a client that
                        # dropped its connection while it waited — and it
                        # would hold the slot for the whole heartbeat timeout.
                        never = (a.beats == 0 and a.granted_at > 0
                                 and now - a.granted_at > self._first_beat_grace_s)
                        if age > self._heartbeat_timeout_s or never:
                            logger.warning(
                                "[GPU-GATE] Reaping dead lease %s (%s) — %s", a.id, a.kind,
                                "granted %.0fs ago and never reported in" % (now - a.granted_at)
                                if never else "no heartbeat for %.0fs" % age)
                            self._active = None
                            self._leases.pop(a.token, None)
                            # Nobody told us what finished loading. Keeping the
                            # previous belief would point affinity at a model
                            # that is not there any more.
                            self._last_key = None
                            self._cv.notify_all()
            except Exception as e:
                logger.error("[GPU-GATE] Reaper error: %s", e)

    def prefetch_advice(self) -> Dict[str, Any]:
        """Which model could be warmed right now, beside the running one.

        The gate says whether there is room and time; it does not itself know
        how to warm a ComfyUI model — the workflows live in the routes, and
        the warm-ahead worker is who acts on this.

        Every condition here has to hold, and each one exists because its
        absence is how a card runs dry:
          - the sensor is answering and the gate is not degraded,
          - something is running, with enough time left to be worth it,
          - the next run in the plan needs a DIFFERENT model,
          - that model's footprint has been MEASURED, not declared,
          - free memory covers it with the configured room to spare.
        """
        out: Dict[str, Any] = {"recommended": None, "reason": ""}
        if not self._prefetch_enabled:
            out["reason"] = "prefetch disabled"
            return out
        if self._degraded:
            out["reason"] = "gate degraded — no speculative allocation"
            return out

        with self._cv:
            a = self._active
            if a is None:
                out["reason"] = "nothing running — the next run has the card to itself"
                return out
            resident = a.affinity_key
            now = time.time()
            nxt = self._pick_from(list(self._waiters), resident, now)
            held = now - (a.admitted_at or a.created_at)
            _exp = self._expected_hold_s(a, self._last_key)
            remaining = None if _exp is None else max(0.0, _exp - held)
            in_flight = self._prefetch_in_flight

        if in_flight:
            out["reason"] = f"already warming {in_flight}"
            return out
        if nxt is None:
            out["reason"] = "nobody waiting"
            return out
        if nxt.affinity_key == resident:
            out["reason"] = "next run uses the model that is already loaded"
            return out
        if remaining is None:
            out["reason"] = ("no measured duration for the running model — "
                             "how much time is left is not known")
            return out
        if remaining < self._prefetch_min_remaining_s:
            out["reason"] = (f"only {remaining:.0f}s left on the running operation — "
                             f"not enough to finish a load beside it")
            return out

        try:
            from my_app.services.gpu_model_stats import get_model_stats
            need = get_model_stats().vram_estimate_mb(nxt.kind, nxt.model_id, trusted_only=True)
        except Exception as e:
            out["reason"] = f"statistics unavailable: {e}"
            return out
        if need is None:
            out["reason"] = (f"{nxt.model_id} has no measured footprint yet — "
                             f"a guess is exactly how the card ran dry")
            return out

        # NOTE: `need` is a LOWER BOUND, not a size — see the comment on
        # GPU_ADMISSION_PREFETCH in config.py. Nothing here corrects for that
        # yet, which is why the flag is off.

        free = self._sensor.free_mb()
        if free is None:
            out["reason"] = "no trustworthy VRAM reading"
            return out

        room = free - need - self._prefetch_headroom_mb
        if room < 0:
            out["reason"] = (f"{free:.0f}MB free, {nxt.model_id} needs {need:.0f}MB "
                             f"plus {self._prefetch_headroom_mb:.0f}MB to spare")
            return out

        out["recommended"] = {
            "kind": nxt.kind,
            "model_id": nxt.model_id,
            "affinity_key": nxt.affinity_key,
            "source": nxt.source,
            "label": nxt.label,
            "measured_mb": round(need),
            "free_mb": round(free),
            "room_to_spare_mb": round(room),
            "running_has_left_s": round(remaining),  # remaining is known here
        }
        out["reason"] = "room and time to warm the next model beside the running one"
        return out

    def forget_resident(self, why: str = "") -> None:
        """Whatever we believed was loaded is gone.

        Called when ComfyUI has been told to free everything. Without this the
        queue would keep being reordered toward a model that is no longer on
        the card — the reorder would then cost a load instead of saving one,
        which is worse than not reordering at all.
        """
        with self._cv:
            if self._last_key is not None:
                logger.info("[GPU-GATE] Forgetting resident model %s (%s)",
                            self._last_key, why or "card was cleared")
                self._last_key = None

    def prefetch_claim(self, model_id: str) -> bool:
        """Claim the single prefetch slot. False if one is already running."""
        with self._cv:
            if self._prefetch_in_flight:
                return False
            self._prefetch_in_flight = model_id
            self._prefetch_started_at = time.time()
            return True

    def prefetch_done(self, model_id: str) -> None:
        with self._cv:
            if self._prefetch_in_flight == model_id:
                self._prefetch_in_flight = None

    def _sample_active_footprint(self) -> None:
        """Track the low-water mark of free memory for the running operation.

        Reading NVML happens outside the lock; only the assignment is inside.
        """
        with self._cv:
            a = self._active
            base = a.free_at_admit_mb if a else 0.0
        if a is None or base <= 0:
            return
        free = self._sensor.free_mb()
        if free is None or free <= 0:
            return
        with self._cv:
            if self._active is not a:
                return
            if free < a.min_free_mb:
                a.min_free_mb = free
            # Also the high-water mark. A run that has to load first EVICTS
            # first, and eviction RAISES free memory — so the reading taken at
            # admission is on the wrong side of it. Measuring from the peak
            # instead means the drop is the model, not the model minus whatever
            # was thrown out to make room for it.
            if free > a.max_free_mb:
                a.max_free_mb = free

    def _expected_hold_s(self, lease: Lease,
                         resident_key: Optional[str]) -> Optional[float]:
        """How long this run will hold the slot, or None when nobody knows.

        Measured for this model, or not answered at all. The running average
        over every model on the card used to stand in here, and it reads as
        knowledge while being none: a video and a safety check are the same
        number to it, and that number then reached a child as "about two
        minutes". A model that has to be loaded first is charged the load as
        well — that is the whole reason the order matters.
        """
        est = None
        try:
            from my_app.services.gpu_model_stats import get_model_stats
            stats = get_model_stats()

            def measured(kind: str):
                """This config's own record, or the model's coarser one.

                The model record mixes the configs that share a checkpoint, so
                it is the second answer, not the first — but it is measurement,
                and it passes the same two gates. Without it, re-keying to the
                config threw away a hundred good samples per model and the
                platform went quiet about waits it had been getting right.
                """
                v = stats.hold_estimate_s(kind, lease.stats_key)
                if v is None and lease.stats_key != lease.model_id:
                    v = stats.hold_estimate_s(kind, lease.model_id)
                return v

            if lease.kind.endswith("-load"):
                # A load lease prices itself: its one bucket is load-inclusive
                # by definition ("a load is cold by definition"), so the
                # cold/warm split and a load surcharge on top of a load are
                # not things.
                return stats.hold_estimate_s(lease.kind, lease.stats_key)

            will_be_resident = (lease.affinity_key == resident_key)
            includes_load = False
            if will_be_resident:
                est = measured(lease.kind)
            else:
                # A cold reading already has the load inside it — that is what
                # makes it cold. Only when there is none does the warm figure
                # plus a separately measured load stand in.
                est = measured(f"{lease.kind}-cold")
                includes_load = est is not None
                if est is None:
                    est = measured(lease.kind)

            if est is not None and not will_be_resident and not includes_load:
                # What a REAL load costs. The average answers something else: a
                # load of a model that turns out to be resident already returns
                # in milliseconds and is recorded too, which drags the mean far
                # below any load that actually happens (measured 6.6s against a
                # 28.4s load).
                load_est = stats.load_estimate_s(f"{lease.kind}-load", lease.model_id)
                if load_est:
                    est += load_est
                else:
                    # A warm figure with no measured load on top is not what a
                    # cold run costs. On the ComfyUI path the load has no lease
                    # of its own and can be minutes — measured on one and the
                    # same config: 21.0 s warm against 132.1 s cold. Saying
                    # nothing is the honest answer; a cold bucket that fills
                    # with real runs and passes the two gates then speaks
                    # measured — a promise the spread gate may defer, never
                    # a number invented meanwhile.
                    est = None
        except Exception:
            est = None
        return None if est is None else float(est)

    def plan(self) -> Dict[str, Any]:
        """The queue as it will actually run, with the wait each place implies.

        This is what the gate knows: who holds the card, who is in line, in
        which order they will go under the current policy, and how long each
        one is expected to take. It says nothing about runs that have not
        reached the gate yet — those are in translation, Prompt Interception
        or the safety check, and only the routes see them.
        """
        import dataclasses as _dc
        with self._cv:
            now = time.time()
            a = self._active
            resident = self._last_key

            # How much of the running operation is still to come. Everything
            # below happens after that, so the replay starts there.
            # When the running operation has outlived its estimate, nobody
            # knows when the card frees up — and then nobody knows when anyone
            # in the queue starts either. That has to travel: a "starts in 0 s"
            # under a running job whose remaining time reads "unknown" is the
            # same lie one line further down.
            ahead_s = 0.0
            ahead_known = True
            exp_active = None
            if a is not None:
                held = now - (a.admitted_at or a.created_at)
                exp_active = self._expected_hold_s(a, resident)
                if exp_active is None:
                    ahead_known = False
                else:
                    ahead_s = exp_active - held
                    if ahead_s <= 0:
                        ahead_s, ahead_known = 0.0, False

            # Replay the policy against COPIES, and let the copies age. Two
            # things decide the order that a frozen snapshot cannot see: a
            # waiter passed often enough goes next, and a waiter waiting long
            # enough goes next. Both accrue while the queue drains, so a
            # simulation that does neither shows an order the gate will not
            # honour — measured: position 9 promised where the gate ran 4, and
            # in one case the run shown last went first.
            real_by_id = {w.id: w for w in self._waiters}
            pool = [_dc.replace(w) for w in self._waiters]
            queue = []
            sim_resident = a.affinity_key if a is not None else resident
            sim_now = now + ahead_s
            start_s = ahead_s
            chain_known = ahead_known
            guard = 0
            pos = 0
            while pool and guard < 200:
                guard += 1
                pick = self._pick_from(pool, sim_resident, sim_now)
                if pick is None:
                    break
                idx = pool.index(pick)
                for w in pool[:idx]:
                    w.overtaken += 1
                pool.remove(pick)
                own = self._expected_hold_s(pick, sim_resident)
                pos += 1
                real = real_by_id.get(pick.id)
                queue.append({
                    "position": pos,
                    "id": pick.id,
                    "kind": pick.kind,
                    "model_id": pick.model_id,
                    "label": pick.label,
                    "source": pick.source,
                    "waiting_s": round(now - pick.created_at, 1),
                    "overtaken": (real.overtaken if real is not None
                                  else pick.overtaken),
                    "model_already_loaded": pick.affinity_key == sim_resident,
                    "expected_run_s": None if own is None else round(own, 1),
                    "expected_start_in_s": (round(start_s, 1) if chain_known
                                            else None),
                })
                # For the ORDER an unknown duration still has to move the
                # clock, or the fairness bounds below never age and the replay
                # shows an order the gate will not honour. The platform-wide
                # average is good enough for that. For the reported TIME it is
                # not good enough, and there the unknown travels on.
                sim_now += own if own is not None else self._ema_hold_s
                if own is None:
                    chain_known = False
                else:
                    start_s += own
                sim_resident = pick.affinity_key
            order = queue

            return {
                "active": None if a is None else {
                    "id": a.id, "kind": a.kind, "model_id": a.model_id,
                    "label": a.label, "source": a.source,
                    "held_s": round(now - (a.admitted_at or a.created_at), 1),
                    # None, not 0, once a run has outlived its estimate.
                    # Reporting 0 tells a whole room "about to start" while a
                    # video that was quoted 10s has been running for 200.
                    "expected_remaining_s": (
                        None if exp_active is None else
                        (lambda rem: None if rem <= 0 else round(rem, 1))(
                            exp_active - (now - (a.admitted_at or a.created_at)))
                    ),
                },
                "resident_model": resident,
                "queue": queue,
                "queue_length": len(order),
                "affinity_enabled": self._affinity_enabled,
                "max_overtakes": self._affinity_max_overtakes,
                "affinity_max_wait_s": self._affinity_max_wait_s,
                "overtakes_granted": self._overtakes_granted,
                "acquire_timeout_s": self._acquire_timeout_s,
            }

    def _reserved_for_someone_else(self, lease: Lease) -> bool:
        """A model was just loaded for a run that has not queued yet.

        Its own run is milliseconds away — it queues as soon as the load
        returns — so the card waits those milliseconds instead of starting a
        different model and throwing the load away. Bounded by
        GPU_ADMISSION_POST_LOAD_RESERVE_S, and never applied to a run that is
        itself past a fairness bound (checked first in _pick_from).
        """
        if self._reserved_key is None or time.time() >= self._reserved_until:
            return False
        if not self._affinity_enabled:
            return False
        if lease.affinity_key == self._reserved_key:
            return False
        # NOTE: deliberately NOT conditioned on a matching waiter being
        # present. The run this is held for has not queued yet — that is the
        # entire situation the reservation addresses. The card idling for the
        # reserve window is the price, and it is bounded by
        # GPU_ADMISSION_POST_LOAD_RESERVE_S; what must not happen is arming it
        # for a run that is never coming, which is handled where it is armed.
        now = time.time()
        if (now - lease.created_at) >= self._affinity_max_wait_s:
            return False
        if lease.overtaken >= self._affinity_max_overtakes:
            return False
        return True

    def _pick_from(self, pool: List[Lease], resident: Optional[str],
                   now: float) -> Optional[Lease]:
        """The dequeue policy over an arbitrary list — used by the live gate on
        its own queue and by plan() on a copy. One rule, one implementation."""
        if not pool:
            return None
        for w in pool:
            if (now - w.created_at) >= self._affinity_max_wait_s:
                return w
            if w.overtaken >= self._affinity_max_overtakes:
                return w
        # Held open for a run whose model was just loaded for it. Checked after
        # the fairness bounds above, so it can never starve anybody, and it
        # lapses by itself within seconds.
        if (self._affinity_enabled and self._reserved_key is not None
                and now < self._reserved_until):
            for w in pool:
                if w.affinity_key == self._reserved_key:
                    return w

        head = pool[0]
        if not self._affinity_enabled or resident is None:
            return head
        if head.affinity_key == resident:
            return head
        for w in pool:
            if w.affinity_key == resident:
                return w
        return head

    def get_status(self) -> Dict[str, Any]:
        with self._cv:
            a = self._active
            now = time.time()
            return {
                "active": None if a is None else {
                    "id": a.id, "kind": a.kind, "model_id": a.model_id,
                    "label": a.label, "holder": a.holder,
                    "source": a.source, "required_mb": a.required_mb,
                    # Since it was ADMITTED, as everywhere else in this file:
                    # counting the queue in would make a run that has just begun
                    # look like the oldest thing on the card.
                    "held_s": round(now - (a.admitted_at or a.created_at), 1),
                    "heartbeat_age_s": round(now - a.last_heartbeat, 1),
                },
                "waiting": [
                    {"kind": w.kind, "model_id": w.model_id, "source": w.source,
                     "label": w.label, "overtaken": w.overtaken,
                     "waiting_s": round(now - w.created_at, 1)}
                    for w in self._waiters
                ],
                "resident_model": self._last_key,
                "max_waiters": self._max_waiters,
                "typical_run_s": round(self._ema_hold_s, 1),
                "acquire_timeout_s": self._acquire_timeout_s,
                "heartbeat_timeout_s": self._heartbeat_timeout_s,
                # A count, never the tokens: the status is read by every
                # visitor of the settings page, and a token releases a slot
                # (`active.id` is the lease's name, not its token).
                "leases": len(self._leases),
                "degraded": self._degraded,
                "sensor": "NVML" if self._sensor.configured else "none",
                "last_free_ask": self._last_free_ask_note,
                "affinity_enabled": self._affinity_enabled,
                "overtakes_granted": self._overtakes_granted,
            }

    # ------------------------------------------------------------------ card
    def card_name(self) -> str:
        """The card's name as the driver reports it; empty without a sensor."""
        return self._sensor.name()

    def vram_status(self, card_timeout=(5, 5)) -> Dict[str, Any]:
        """The card and what is on it, in the shape the coordinator of the
        old host answered on /api/health/vram: free and total memory, the
        models resident (ComfyUI's, asked of it), the processes on the card
        with the foreign ones marked, and the gate's own state beside them.

        Two sources, each answering for what it sees: the driver for memory
        and processes, ComfyUI for the models it holds. `comfyui.reachable`
        says whether the second one answered; when it did not, the list
        carries ComfyUI's process as one line that says so, rather than
        pretending the card is clear.

        Every byte the driver attributes to a process of the platform's is
        in `loaded_models`, so a reader that adds own, foreign and free gets
        the card: ComfyUI's models as ComfyUI lists them, what its process
        holds beyond them as one line, and every other process of the
        platform's — the VoxCPM worker, a Blender child, the GPU service
        until stage 8 — as one line under its label. The old host listed the
        models it had loaded itself and called every other process foreign;
        this one loads nothing and reads them all from the driver.

        `card_timeout` bounds the read of ComfyUI's list — a walk over a
        list, not a model call. The settings page can wait five seconds for
        it; the workshop companion's prompt cannot.
        """
        reading = self._sensor.read()
        card = read_comfyui_card(self._comfyui_port, timeout=card_timeout)
        with self._cv:
            a = self._active
            active_kind = a.kind if a is not None else ""
            active_holder = a.holder if a is not None else ""
        models = []
        listed_mb = 0.0
        for m in card.get("loaded_models") or []:
            vram_mb = round(float(m.get("vram_mb") or 0.0), 1)
            listed_mb += vram_mb
            models.append({
                "backend": "comfyui",
                "model": m.get("model", ""),
                "vram_mb": vram_mb,
                "priority": "-",
                "in_use": 1 if m.get("in_use") else 0,
                "last_used": None,
                # `card`: a model, as ComfyUI lists it. `driver`: a process,
                # as the driver attributes memory to it. The companion's
                # prompt names the models and leaves the processes out.
                "source": "card",
            })
        for proc in ([] if reading is None else reading["processes"]):
            label = proc["label"]
            if label in ("self", "foreign"):
                continue
            held = proc["vram_mb"]
            if label == "comfyui":
                if card.get("reachable"):
                    held = round(held - listed_mb, 1)
                    what = "beyond the models listed: context, activations, cache"
                else:
                    what = "resident, unlisted: %s" % (card.get("error") or "ComfyUI did not answer")
                if held <= 0:
                    continue
            else:
                what = _short_cmdline(proc["cmdline"]) or "pid %d" % proc["pid"]
            models.append({
                "backend": label,
                "model": what,
                "vram_mb": held,
                "vram_unknown": bool(proc.get("vram_unknown")),
                "priority": "-",
                # In use while the process holding the slot is this one —
                # the GPU service names itself on its leases — or a lease of
                # the kind the label stands for holds it (voxcpm-load,
                # blender, lora_training).
                "in_use": 1 if ((active_holder and active_holder == label)
                                or (active_kind and active_kind.startswith(label))) else 0,
                "last_used": None,
                "source": "driver",
            })
        out: Dict[str, Any] = {
            "free_mb": None if reading is None else reading["free_mb"],
            "total_mb": None if reading is None else reading["total_mb"],
            "nvml_available": reading is not None,
            "registered_backends": ["comfyui"] if card.get("reachable") else [],
            "loaded_models": models,
            "gpu_processes": [] if reading is None else reading["processes"],
            "foreign_vram_mb": None if reading is None else reading["foreign_mb"],
            "nvml_free_mb": None if reading is None else reading["free_mb"],
            "nvml_used_mb": None if reading is None else reading["used_mb"],
            "comfyui": {"reachable": bool(card.get("reachable")),
                        "error": card.get("error", ""),
                        "free_mb": card.get("free_mb"),
                        "total_mb": card.get("total_mb")},
            "gate": self.get_status(),
        }
        if reading is None:
            out["sensor_error"] = self._sensor.why
        return out


# A ComfyUI that is up and answers without the list is a deployment fault —
# the package not loaded there, or a ComfyUI without the route — and the page
# only shows "unreachable" for it. The sentence that says which goes to the
# log as well, once in a while: the page and the companion ask every few
# seconds, and a fault that stands for an hour is one line, not a thousand.
_CARD_WARN_GAP_S = 600.0
_card_warned_at = 0.0


def _warn_about_the_card(text: str) -> None:
    global _card_warned_at
    now = time.time()
    if now - _card_warned_at >= _CARD_WARN_GAP_S:
        _card_warned_at = now
        logger.warning("[GPU-GATE] %s", text)


def free_comfyui(label: str, *, interrupt: bool = False, free_memory: bool = False,
                 timeout: float = 30.0, wait_s: Optional[float] = None):
    """Ask ComfyUI to unload everything it holds, with the card held.

    THE unload path for every administrative free (the training page's
    clear-VRAM, the workshop's clear-all, the training service's cleanup
    before a run): POST /interrupt when asked, BEFORE the lease, because the
    interrupt is for the run that holds the card and a lease granted only
    once nothing runs would come too late for it; then a lease on the gate,
    so that nothing is taken out from under a run mid-forward, and POST
    /free under it; and on ComfyUI's 200, AFTER the release, the gate
    forgets what it believed resident: release() notes the hold's own
    affinity key as the resident, which undid a forget made inside the hold
    (second review of 2026-10-10).
    Until 2026-10-10 the three callers posted /free on their own, past the
    gate (finding S-004 of the code review of 2026-10-10). The gate's own ask during admission stays where it is
    (_ask_comfyui_to_free): that one already holds the slot.

    Returns the /free response. Raises GpuBusyError when the gate refuses
    the lease within wait_s, requests' errors when ComfyUI cannot be reached.
    """
    import requests
    import config
    from my_app.services.gpu_lease_client import gpu_lease_sync
    if interrupt:
        requests.post(f"{config.COMFYUI_URL}/interrupt", timeout=5)
    with gpu_lease_sync("comfyui-free", "comfyui", 0, label=label, timeout_s=wait_s):
        payload = {"unload_models": True}
        if free_memory:
            payload["free_memory"] = True
        response = requests.post(f"{config.COMFYUI_URL}/free", json=payload, timeout=timeout)
    if response.status_code == 200:
        get_gpu_gate().forget_resident(label)
    return response


def read_comfyui_card(port: str, timeout=(5, 5)) -> Dict[str, Any]:
    """What ComfyUI holds on the card, asked of the platform's node package
    (GET /ai4artsed/card). {reachable, error, free_mb, total_mb,
    loaded_models: [{model, vram_mb, size_mb, in_use}]}; on any failure
    `reachable` is False and `error` says why, with an empty list. The read
    is bounded: a walk over a list, not a model call, and the settings page
    and the companion's prompt wait on it."""
    out: Dict[str, Any] = {"reachable": False, "error": "", "loaded_models": []}
    if not port:
        out["error"] = "ComfyUI's port is not configured"
        return out
    url = f"http://127.0.0.1:{port}/ai4artsed/card"
    try:
        import requests
        resp = requests.get(url, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        out["error"] = f"ComfyUI is not answering {url} ({type(e).__name__}: {e})"
        return out
    if resp.status_code != 200:
        out["error"] = f"ComfyUI answered {url} with HTTP {resp.status_code}: {resp.text[:200]}"
        _warn_about_the_card(out["error"] + " — is the ai4artsed_comfyui package loaded there?")
        return out
    try:
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        out["error"] = f"ComfyUI answered {url} with something that is not JSON ({e})"
        _warn_about_the_card(out["error"])
        return out
    if not isinstance(data, dict) or not isinstance(data.get("loaded_models"), list):
        out["error"] = f"ComfyUI answered {url} without a model list: {str(data)[:200]}"
        _warn_about_the_card(out["error"])
        return out
    out["reachable"] = True
    out["free_mb"] = data.get("free_mb")
    out["total_mb"] = data.get("total_mb")
    out["loaded_models"] = data["loaded_models"]
    return out


_gate: Optional["GpuGate"] = None
_gate_singleton_lock = threading.Lock()


def get_gpu_gate() -> "GpuGate":
    global _gate
    if _gate is None:
        with _gate_singleton_lock:
            if _gate is None:
                _gate = GpuGate()
    return _gate
