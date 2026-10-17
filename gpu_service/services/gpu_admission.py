"""
GpuAdmission — plant-wide serialization gate for heavy GPU operations.

One card, one heavy operation at a time. Every heavy op — diffusers, heartmula,
stable-audio, mmaudio, hunyuan3d in this process, ComfyUI through a remote lease
held by the DevServer — takes the single slot before it allocates, and holds it
until it is done.

Why a slot instead of a better estimate. What a model will cost cannot be known
before it is loaded, so the coordinator's pre-flight number is a guess and stays
one. What CAN be known is that nobody else is allocating at the same moment.
Measured 2026-08-18: the coordinator evicted, computed 49,392 MB free, and the
load ran out of memory anyway, because four other loads were in flight in the
same second. No sharper estimate would have caught that; taking turns does.

The slot covers BOTH allocating phases, loading and the forward pass. The 30 GB
that overflowed the card last night were allocated while loading, not while
generating.

Reentrant per thread: a generation that loads a model on its own thread must not
block on a slot it already holds.

Plain `threading`, acquired INSIDE the to_thread worker. Never an asyncio
primitive: the routes spin up a fresh event loop per request, and an asyncio
primitive shared across loops loses wakeups and wedges the thread.

Since stage 7 of the move to ComfyUI
the plant-wide gate is the DevServer's (devserver/my_app/services/gpu_gate.py):
ComfyUI's runs, the VoxCPM worker and a LoRA training lease it there, and
nothing leases this one from outside any more. This service stands until
stage 8, and while it stands it must not be a second gate on the same card:
every hold here is also a lease there, taken before the local slot and given
back with it (_lease_upstream, _release_upstream). The slot here still
orders this process's own routes among themselves, and the memory is still
this process's business — the lease there is for the turn, not the room.
A hold that cannot get the turn there is refused, with the reason in the
sentence (_lease_upstream says which cases there are); a DevServer without
gate routes is the one exception, because its own lease client then leases
this gate.
"""

import logging
import os
import threading
from contextvars import ContextVar
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


# Which DevServer run the operation in this request belongs to. ComfyUI
# leases carry it directly; a diffusers call arrives over HTTP, so the route
# puts it here and the backend reads it when it takes the slot. Without it the
# forecast cannot see the main image path at all — it would show a child
# "preparing" while their picture is already being drawn.
CURRENT_RUN_LABEL: "ContextVar[str]" = ContextVar("gpu_run_label", default="")
# Which output config the current request is producing. Durations are measured
# against this, not against the model: one checkpoint serves several configs,
# and their mean is a duration none of them has.
CURRENT_WORKLOAD: "ContextVar[str]" = ContextVar("gpu_workload", default="")
# Which model THIS request asked for. The diffusers backend keeps several
# pipelines at once and remembers only the last one loaded, so a run that gave
# the slot back between its load and its forward pass could come back to find
# another request had moved that marker — and then queued under the wrong
# model, and had its memory filed under it.
CURRENT_MODEL: "ContextVar[str]" = ContextVar("gpu_model", default="")


# Where the DevServer's gate answers, found the way the node package finds the
# DevServer (comfyui_nodes/ai4artsed_comfyui/_devserver.py): AI4ARTSED_DEVSERVER_URL,
# else http://127.0.0.1:<PORT>, PORT being the variable the DevServer reads
# and 17802 its default. On a production host the DevServer answers on
# 17801, and the unit install_systemd_services.sh writes for this service
# sets PORT to the backend's port for that reason.
_UPSTREAM_DEFAULT_PORT = "17802"
# What this service calls itself on the DevServer's gate, so its rows on the
# settings page read "in use" while a hold of its is on the card.
UPSTREAM_HOLDER = "gpu_service"
# A DevServer that does not answer is asked again for this long, at this
# gap — a restart of it takes seconds — before the hold is refused.
_UPSTREAM_RETRY_S = 30.0
_UPSTREAM_RETRY_GAP_S = 2.0


def upstream_url() -> str:
    url = os.environ.get("AI4ARTSED_DEVSERVER_URL", "").strip()
    if not url:
        url = f"http://127.0.0.1:{os.environ.get('PORT', _UPSTREAM_DEFAULT_PORT)}"
    return url.rstrip("/")


def _remaining(timeout_s: Optional[float], since: float) -> Optional[float]:
    """What is left of a caller's budget after `since`; None stays None."""
    if timeout_s is None:
        return None
    return max(0.0, float(timeout_s) - (time.time() - since))


def carry_the_run(body) -> None:
    """Whose run the request carrying `body` belongs to, on this thread.

    All three marks unconditionally, the empty case included: a waitress thread
    serves one request after another, and a mark left standing files the next
    run's figures under the last one's name.

    `body` is whatever came off the wire. A bare list or a string is a body
    that parsed, so nothing here assumes a mapping.
    """
    label = workload = model = ""
    try:
        if isinstance(body, dict):
            label = str(body.get("run_label") or "")
            workload = str(body.get("workload") or "")
            model = str(body.get("model_id") or "")
    except Exception:  # noqa: BLE001 — a mark may not cost a request
        label = workload = model = ""
    CURRENT_RUN_LABEL.set(label)
    CURRENT_WORKLOAD.set(workload)
    CURRENT_MODEL.set(model)


# Kinds whose hold is measured in hours, not in the seconds a generation takes.
# A LoRA training keeps the card for one to three hours; queueing behind it is
# not waiting, it is hanging. Whoever meets one is turned away at once with a
# sentence that says which, instead of parking a worker thread until the
# acquire budget runs out.
# Below this many seconds left on the running operation, reading the next
# model's files ahead is competing with a load that is about to start on the
# same disk. Only ever applied when the remaining time was actually MEASURED -
# an unknown duration goes ahead, because reading is abortable and a partial
# read still helps.
PAGE_WARM_MIN_REMAINING_S = 20.0

LONG_HOLD_KINDS = frozenset({"lora_training"})

# What to call a long hold when the sentence leaves the machine room. The kind
# is an internal name; the person who pressed a button and is being turned away
# reads this instead.
LONG_HOLD_NAMES = {"lora_training": "a LoRA training"}


class GpuBusy(Exception):
    """
    The GPU cannot admit an operation: the queue was full, the wait ran out, or
    the memory is physically not there after eviction.

    Callers MUST pass this on as HTTP 503. Never as an out-of-memory error, never
    as a silent None — a caller that cannot tell "busy" from "broken" retries the
    wrong one.
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
        # on 2026-08-28. The token travels with the 503 so that the sentence a
        # person reads is chosen from the state, never from prose matching.
        self.reason = reason or "busy"
        # long_hold: the lease kind that is holding the card (lora_training),
        # so the surface can say what it is doing.
        self.holder_kind = holder_kind
        # queue_full: how many were already in line when this one was refused.
        self.waiting = waiting


@dataclass
class Lease:
    kind: str          # 'diffusers' | 'heartmula' | 'comfyui' | ...
    model_id: str
    required_mb: float
    priority: int      # EvictionPriority value
    source: str        # 'local' | 'remote'
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
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
    upstream_token: str = ""   # the DevServer gate's token for this hold; empty: not leased there
    upstream_trouble: bool = False   # the last heartbeat there failed; said once, asked again each tick
    comfyui_cleared: bool = False    # the coordinator asked ComfyUI to free everything during this hold

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
        base = (self.model_id or self.kind)
        return base


class GpuAdmission:
    """Single-slot, plant-wide admission gate. Singleton via get_gpu_admission()."""

    def __init__(self):
        self._cv = threading.Condition()
        self._active: Optional[Lease] = None
        self._waiters: List[Lease] = []              # FIFO
        self._remote_leases: Dict[str, Lease] = {}   # token -> active remote lease
        self._local = threading.local()              # per-thread reentrancy depth
        self._degraded = False          # runtime sensor loss; heavy ops are refused
        self._warned_no_sensor = False  # one-time deployment warning
        self._blind_samples = 0         # consecutive failed sensor readings
        self._last_reclaim_at = 0.0     # when a known state was last forced
        self._ema_hold_s = 0.0          # moving average of how long a run holds the slot
        self._last_key: Optional[str] = None   # what ran last = what is resident
        self._overtakes_granted = 0     # how often affinity reordered, for the record
        self._prefetch_in_flight: Optional[str] = None   # at most one warm-up at a time
        self._prefetch_started_at = 0.0
        self._reserved_key: Optional[str] = None   # just loaded — its own run goes next
        self._reserved_until = 0.0

        import config as _cfg
        self._acquire_timeout_s = float(getattr(_cfg, "GPU_ADMISSION_ACQUIRE_TIMEOUT_S", 900.0))
        self._heartbeat_timeout_s = float(getattr(_cfg, "GPU_ADMISSION_HEARTBEAT_TIMEOUT_S", 30.0))
        self._reaper_interval_s = float(getattr(_cfg, "GPU_ADMISSION_REAPER_INTERVAL_S", 5.0))
        self._max_waiters = int(getattr(_cfg, "GPU_ADMISSION_MAX_WAITERS", 8))
        self._blind_samples_to_declare = int(getattr(_cfg, "GPU_ADMISSION_BLIND_SAMPLES", 3))
        self._max_hold_s = float(getattr(_cfg, "GPU_ADMISSION_MAX_HOLD_S", 2400.0))
        self._reclaim_cooldown_s = float(getattr(_cfg, "GPU_ADMISSION_RECLAIM_COOLDOWN_S", 600.0))
        self._ema_hold_s = float(getattr(_cfg, "GPU_ADMISSION_ASSUMED_RUN_S", 90.0))
        self._affinity_enabled = bool(getattr(_cfg, "GPU_ADMISSION_AFFINITY", True))
        self._affinity_max_overtakes = int(getattr(_cfg, "GPU_ADMISSION_MAX_OVERTAKES", 3))
        self._affinity_max_wait_s = float(getattr(_cfg, "GPU_ADMISSION_AFFINITY_MAX_WAIT_S", 300.0))
        self._page_warm_in_flight: Optional[str] = None
        self._prefetch_enabled = bool(getattr(_cfg, "GPU_ADMISSION_PREFETCH", True))
        self._prefetch_headroom_mb = float(getattr(_cfg, "GPU_ADMISSION_PREFETCH_HEADROOM_MB", 10240.0))
        self._prefetch_min_remaining_s = float(getattr(_cfg, "GPU_ADMISSION_PREFETCH_MIN_REMAINING_S", 45.0))
        self._post_load_reserve_s = float(getattr(_cfg, "GPU_ADMISSION_POST_LOAD_RESERVE_S", 5.0))

        self._reaper = threading.Thread(
            target=self._reaper_loop, name="gpu-admission-reaper", daemon=True
        )
        self._reaper.start()
        logger.info(
            "[GPU-ADMISSION] Initialized (one slot; acquire_timeout=%.0fs, "
            "heartbeat_timeout=%.0fs, max_waiters=%d)",
            self._acquire_timeout_s, self._heartbeat_timeout_s, self._max_waiters
        )

    # ------------------------------------------------------------------ slot
    @contextmanager
    def slot(self, kind: str, model_id: str, required_mb: float, priority: int,
             timeout_s: Optional[float] = None, label: str = "", workload: str = ""):
        """
        Hold the plant-wide slot across an allocating phase. Use INSIDE the
        to_thread worker:

            with get_gpu_admission().slot('heartmula', model_id, peak_mb, EvictionPriority.NORMAL):
                <load, or forward pass>

        Waits FIFO for the slot, runs admission while holding it, then yields.
        Raises GpuBusy when the queue is full, the wait runs out, or the memory
        is not there. Nested use on the same thread passes straight through.

        timeout_s shortens the wait for callers that would rather go ahead
        unserialized than queue — the safety chain's model loads, above all.
        """
        if getattr(self._local, "depth", 0) > 0:
            self._local.depth += 1
            try:
                yield None
            finally:
                self._local.depth -= 1
            return

        lease = Lease(kind=kind, model_id=model_id, required_mb=float(required_mb),
                      priority=int(priority), source="local", label=label,
                      workload=workload)
        started = time.time()
        self._lease_upstream(lease, timeout_s)  # the plant-wide turn, or raises GpuBusy
        try:
            # One budget for both waits: what the turn there took is spent.
            self._wait_for_slot(lease, _remaining(timeout_s, started))   # claims the slot, or raises
        except BaseException:
            lease.failed = True
            self._release_upstream(lease)
            raise
        self._local.depth = 1
        try:
            self._admit(lease)            # eviction + revalidation; raises GpuBusy
            yield lease
        except BaseException:
            # A load that raised put nothing on the card, so no run of it is
            # coming and nothing may be held open for one.
            lease.failed = True
            raise
        finally:
            self._local.depth = 0
            self._release_active(lease)

    # ------------------------------------------------------- remote lease API
    def acquire_remote(self, kind: str, model_id: str, required_mb: float, priority: int,
                       label: str = "", workload: str = "",
                       timeout_s: Optional[float] = None) -> str:
        """
        Take the slot for a heavy op running in another process (the DevServer
        driving ComfyUI). Returns a token; the slot stays held until release() or
        until the reaper finds the heartbeat gone. Raises GpuBusy.

        timeout_s shortens the wait for a caller that would rather hear "busy"
        than queue for the full acquire budget.
        """
        lease = Lease(kind=kind, model_id=model_id, required_mb=float(required_mb),
                      priority=int(priority), source="remote", label=label,
                      workload=workload)
        started = time.time()
        self._lease_upstream(lease, timeout_s)
        try:
            self._wait_for_slot(lease, _remaining(timeout_s, started))
        except BaseException:
            lease.failed = True
            self._release_upstream(lease)
            raise
        with self._cv:
            self._remote_leases[lease.id] = lease
        try:
            self._admit(lease)
        except BaseException:
            # Refused at admission: nothing ran. Without the flag, a lease
            # whose admission raised after the admitted_at stamp recorded its
            # near-zero age as a valid hold.
            lease.failed = True
            self._release_active(lease)
            raise
        # Admission can take a while — eviction, in the worst case a ComfyUI
        # restart. The heartbeat clock starts once the token is on its way back,
        # or the reaper could collect a lease whose holder never had a chance to
        # report in.
        with self._cv:
            lease.last_heartbeat = time.time()
        logger.info("[GPU-ADMISSION] Remote lease acquired: %s (%s/%s)", lease.id, kind, model_id)
        return lease.id

    def heartbeat(self, token: str) -> bool:
        with self._cv:
            lease = self._remote_leases.get(token)
            if lease is None:
                return False
            lease.last_heartbeat = time.time()
            return True

    def release(self, token: str, failed: bool = False) -> bool:
        with self._cv:
            lease = self._remote_leases.pop(token, None)
            if lease is None:
                return False
            if failed:
                # The remote owner reports the run did not complete — aborted
                # in the queue, or a render that was interrupted. Mirrors what
                # slot() records when a local body raises: the held time is
                # not a duration any completed run has.
                lease.failed = True
            if self._active is lease:
                self._note_hold(lease)
                self._active = None
            self._cv.notify_all()
        self._release_upstream(lease)
        logger.info("[GPU-ADMISSION] Remote lease released: %s", token)
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
            from services.gpu_model_stats import get_model_stats
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
            logger.debug("[GPU-ADMISSION] Could not record model statistics: %s", e)

    # Kinds whose inference does NOT take the slot. Loading them does — the
    # weights land on the card — but nothing of that model ever queues
    # afterwards, so holding the card open for it is pure idle time in a room
    # that is waiting. Only the safety chain's language models are like this;
    # every other backend runs its forward pass inside the slot.
    _RUN_KINDS_WITHOUT_A_SLOT = frozenset({"llm"})

    def _load_is_claimable(self, lease: Lease) -> bool:
        """Does a run of this model come back through the gate after loading?

        Only then is it worth holding the slot for it. `diffusers-load` is
        followed by `diffusers` on the same key, and `heartmula-load` by
        `heartmula`. This cannot be decided from the measurements: the very
        first load of a model has no run recorded yet, and that first load is
        exactly the one whose handover was seen to fail.
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
            # eat the whole pool and take the safety checks down with it, so the
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
                logger.info("[GPU-ADMISSION] %s/%s goes ahead of %d waiting — %s "
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
        physical reading, evict our own idle models to make room, and admit — or
        raise GpuBusy on a real, physical shortfall.

        Failsafe by design, which is neither fail-open nor fail-closed. The
        decision rests on the physical sensor: NVML free memory, foreign
        processes included.

        - Sensor answering: trust it, evict, admit.
        - Sensor lost at runtime (it answered at startup, it is blind now — GPU
          off the bus, driver crash): do not guess against the per-process torch
          figure, which cannot see other processes at all. Force a known state
          instead: reclaim every foreign holder, so the blind spot is gone and
          the reading is truth again. If it is still blind afterwards, heavy
          operations are refused — with a message that names a hardware fault,
          not a busy card — and the reclaim is tried again after a cooldown, so
          a driver that comes back brings the plant back with it.
        - NVML never configured: a deployment matter, not a runtime failure. Say
          so once, loudly, and do not thrash.

        Coordinator failures are not swallowed — they surface, and the caller's
        finally releases the slot.
        """
        from services.vram_coordinator import get_vram_coordinator, EvictionPriority
        coord = get_vram_coordinator()

        prio = lease.priority
        if not isinstance(prio, EvictionPriority):
            try:
                prio = EvictionPriority(int(prio))
            except Exception:
                prio = EvictionPriority.NORMAL

        if coord.has_authoritative_reading():
            if self._degraded:
                logger.info("[GPU-ADMISSION] VRAM sensor is answering again — degraded state cleared")
            self._blind_samples = 0
            self._degraded = False
        elif not coord.nvml_configured():
            if not self._warned_no_sensor:
                self._warned_no_sensor = True
                logger.error(
                    "[GPU-ADMISSION] NVML not configured (pynvml missing or "
                    "VRAM_USE_NVML=false): admission runs on a per-process estimate "
                    "that cannot see foreign VRAM. DEPLOYMENT issue — install "
                    "nvidia-ml-py and set VRAM_USE_NVML=true. Heavy ops proceed "
                    "WITHOUT a plant-wide memory guarantee until that is fixed.")
        else:
            # The sensor answered at startup and does not answer now. One failed
            # sample is a hiccup, not a diagnosis — a single miss used to be worth
            # a ComfyUI restart, which is a large action on thin evidence.
            self._blind_samples += 1
            if self._blind_samples < self._blind_samples_to_declare:
                logger.warning("[GPU-ADMISSION] VRAM sensor missed a reading (%d/%d) admitting %s",
                               self._blind_samples, self._blind_samples_to_declare, lease.kind)
            else:
                self._degraded = True
                # Never on behalf of a ComfyUI lease: the reclaim restarts
                # ComfyUI, and the lease exists precisely to do something there
                # — run a workflow, or warm a checkpoint for the runs after it.
                # And never without the plant-wide lease: whether a workshop
                # run is on ComfyUI is known to the gate that hands out the
                # turns, and a hold that has no turn there cannot know.
                since_last = time.time() - self._last_reclaim_at
                may_reclaim = (not lease.kind.startswith("comfyui")
                               and bool(lease.upstream_token)
                               and since_last > self._reclaim_cooldown_s)
                if may_reclaim:
                    # The reclaim now ends this service's own llama-server
                    # children first, before it touches ComfyUI: they are the
                    # standing exception to "this process is the only GPU user",
                    # and the sensor that could see them is the one that just
                    # went. Any reading in flight dies with its child, the
                    # request says so, and the next content check spawns a new
                    # one — which is the cheapest of the losses on this path.
                    logger.error(
                        "[GPU-ADMISSION] VRAM sensor LOST at runtime admitting %s/%s — "
                        "forcing a known state via foreign reclaim (once per episode)",
                        lease.kind, lease.model_id)
                    self._last_reclaim_at = time.time()
                    coord.emergency_reclaim_foreign()

                if coord.has_authoritative_reading():
                    logger.info("[GPU-ADMISSION] Sensor is truth again after reclaim — admitting")
                    self._blind_samples = 0
                    self._degraded = False
                else:
                    # Still blind. Admitting here would mean allocating against a
                    # figure that cannot see other processes — which is how the
                    # card ran dry in the first place. Heavy operations wait; the
                    # safety checks are not gated and keep running — the reclaim
                    # above ended the children they run in, so the first check
                    # after it waits for a respawn rather than being refused.
                    # Deliberately NOT worded as "busy": this is a hardware
                    # fault, and telling somebody to try again in a moment sends
                    # them into a loop that cannot succeed.
                    raise GpuBusy(
                        "GPU not reachable: the VRAM sensor is not answering, so no "
                        "heavy operation can run. Check the driver / nvidia-smi."
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
                logger.warning("[GPU-ADMISSION] Warm-up of %s has not finished in 120s — "
                               "admitting %s anyway rather than holding the queue",
                               pf, lease.model_id)
                break
            logger.info("[GPU-ADMISSION] %s waits for the warm-up of %s to finish",
                        lease.model_id, pf)
            # This wait happens with the slot already held, before the caller
            # has been handed its token — so a remote lease would sit here
            # burning its own heartbeat budget and be reaped mid-admission,
            # handing back a dead token while the run went ahead unslotted.
            with self._cv:
                lease.last_heartbeat = time.time()
            time.sleep(1.0)

        # The starting reading, so the run's own footprint can be measured
        # against it while it holds the slot (sampled by the reaper).
        try:
            f0 = coord.get_free_vram_mb(use_cache=False)
            if f0 > 0:
                lease.free_at_admit_mb = f0
                lease.min_free_mb = f0
                lease.max_free_mb = f0
        except Exception:
            pass

        if lease.required_mb <= 0:
            # Serialization only: this op reserves its own memory through the
            # coordinator on its load path, which now also runs inside the slot.
            logger.info("[GPU-ADMISSION] Admitted %s/%s (serialize only, lease %s)",
                        lease.kind, lease.model_id, lease.id)
            return

        # The coordinator decides against its own figure — free memory minus
        # what it has promised to loads that are still landing — and it is asked
        # for the sentence that goes with the decision. Formulating the refusal
        # from the raw reading instead produced messages that contradicted
        # themselves: while a reservation stood, the request could be refused
        # with more raw megabytes free than the operation needed, and the line a
        # person read said "20000MB free < 15000MB needed". free_mb below stays
        # the physical reading in both refusals — it is what the card reports,
        # and the sentence beside it now says why that was not enough.
        ok, shortfall, _token = coord.request_vram_detailed(
            lease.kind, lease.required_mb, prio)
        free = coord.get_free_vram_mb(use_cache=False)
        if not ok:
            raise GpuBusy(
                "device busy: %s cannot get %.0fMB — %s"
                % (lease.kind, lease.required_mb,
                   shortfall or "the coordinator refused without detail"),
                free_mb=free, required_mb=lease.required_mb,
                reason="no_memory",
            )
        # The gate's own belt-check, deliberately on the raw reading: it can only
        # add refusals to the coordinator's grant, and here the raw numbers are
        # the true ones — the card really does hold less than this operation
        # needs, whatever anyone has been promised.
        if free < lease.required_mb:
            raise GpuBusy(
                "device busy: %.0fMB free < %.0fMB needed for %s after eviction"
                % (free, lease.required_mb, lease.kind),
                free_mb=free, required_mb=lease.required_mb,
                reason="no_memory",
            )
        logger.info("[GPU-ADMISSION] Admitted %s/%s (need %.0fMB, free %.0fMB, lease %s)",
                    lease.kind, lease.model_id, lease.required_mb, free, lease.id)

    def _release_active(self, lease: Lease) -> None:
        with self._cv:
            self._remote_leases.pop(lease.id, None)
            if self._active is lease:
                self._note_hold(lease)
                self._active = None
            self._cv.notify_all()
        self._release_upstream(lease)

    # ------------------------------------------------- the plant-wide lease
    def _lease_upstream(self, lease: Lease, timeout_s: Optional[float]) -> None:
        """Take this hold's turn on the DevServer's gate, before the local slot.

        Blocks for as long as that gate makes it wait; the wait is bounded
        there (its GPU_ADMISSION_ACQUIRE_TIMEOUT_S), not here, and timeout_s
        travels along for a caller that would rather hear "busy". Its refusal
        is raised as GpuBusy with the DevServer's own sentence and token.
        `required_mb` goes as 0: the turn is what is leased there, the room
        stays this process's business (_admit evicts its own idle models and
        asks ComfyUI, which no other gate could do for it).

        What happens when that gate hands out no lease is decided here case
        by case, because "nobody else is competing for the card" is a claim
        this process has no way to check:

          - no connection: asked again every _UPSTREAM_RETRY_GAP_S for up to
            _UPSTREAM_RETRY_S (a restart of the DevServer takes seconds; a
            caller's shorter timeout_s bounds it further), then refused as
            GpuBusy(reason="gate_unreachable"). A DevServer on another port
            is up and driving ComfyUI while this one posts into the void, so
            going ahead would be the unserialised run the gate exists to
            prevent. The sentence names the URL and the two variables that
            set it.
          - HTTP 404: the DevServer has no gate routes — a build from before
            stage 7, whose own lease client leases THIS gate. Then this gate
            is the plant's, and the hold goes ahead, said once per hold.
          - 401, 403, 5xx, 200 without a token: the DevServer is up and
            answering, and the hold is refused with the status and the body
            (reason "gate_refused"). A 401 means the URL is not loopback: the
            settings guard admits this machine only.
        """
        url = f"{upstream_url()}/api/gate/lease/acquire"
        body: Dict[str, Any] = {"kind": lease.kind, "model_id": lease.model_id,
                                "required_mb": 0, "label": lease.label,
                                "workload": lease.workload, "holder": UPSTREAM_HOLDER}
        if timeout_s is not None:
            body["timeout_s"] = float(timeout_s)
        import requests
        retry_s = (_UPSTREAM_RETRY_S if timeout_s is None
                   else min(_UPSTREAM_RETRY_S, float(timeout_s)))
        give_up_at = time.time() + retry_s
        said = False
        while True:
            try:
                # No read bound: the answer comes when the turn is ours, and
                # the gate there bounds the wait itself.
                resp = requests.post(url, json=body, timeout=(5, None))
                break
            except Exception as e:  # noqa: BLE001 — the cause goes into the sentence
                if time.time() < give_up_at:
                    if not said:
                        logger.warning("[GPU-ADMISSION] The DevServer's gate at %s did not "
                                       "answer (%s: %s) — asked again for up to %.0fs",
                                       url, type(e).__name__, e, retry_s)
                        said = True
                    time.sleep(_UPSTREAM_RETRY_GAP_S)
                    continue
                raise GpuBusy(
                    "the DevServer's gate at %s did not answer for %.0fs (%s: %s); the card's "
                    "turn is handed out there, and AI4ARTSED_DEVSERVER_URL or PORT in this "
                    "service's environment says where it is"
                    % (url, retry_s, type(e).__name__, e),
                    reason="gate_unreachable",
                )
        if resp.status_code == 503:
            try:
                payload = resp.json() or {}
            except Exception:  # noqa: BLE001
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            raise GpuBusy(
                str(payload.get("detail") or payload.get("error")
                    or "HTTP 503 from %s: %s" % (url, resp.text[:200].strip() or "(empty body)")),
                free_mb=float(payload.get("free_mb") or 0.0),
                required_mb=float(payload.get("required_mb") or 0.0),
                reason=str(payload.get("busy_reason") or ""),
                holder_kind=str(payload.get("holder_kind") or ""),
                waiting=int(payload.get("waiting") or 0),
            )
        if resp.status_code == 404:
            logger.warning("[GPU-ADMISSION] %s/%s runs on this gate alone: the DevServer at %s "
                           "has no gate routes (HTTP 404), so its lease client leases this one",
                           lease.kind, lease.model_id, url)
            return
        token = ""
        if resp.status_code == 200:
            try:
                token = str((resp.json() or {}).get("token") or "")
            except Exception:  # noqa: BLE001
                token = ""
        if not token:
            hint = (" — the guard there admits this machine only; is the URL loopback?"
                    if resp.status_code in (401, 403) else "")
            raise GpuBusy(
                "the DevServer's gate at %s refused the card's turn: HTTP %s %s%s"
                % (url, resp.status_code, resp.text[:200].strip() or "(empty body)", hint),
                reason="gate_refused",
            )
        lease.upstream_token = token
        logger.info("[GPU-ADMISSION] %s/%s holds the plant-wide lease %s",
                    lease.kind, lease.model_id, token)

    def _heartbeat_upstream(self, lease: Lease) -> None:
        """Keep the plant-wide lease alive; the reaper calls this every tick
        for every hold that carries a token — the active one and the ones
        waiting behind it for the local slot, which hold their turn there
        already. Only a gate that answers that it no longer knows the token
        (HTTP 404: it reaped the lease, or the DevServer restarted) ends the
        lease here too: the hold runs on without the guarantee, and that is
        said once. Any other trouble — no answer, a pool there with no
        thread free, another status — keeps the token: the next tick asks
        again, and a lease that is still known there is given back at the
        end instead of being forgotten with the card's turn."""
        token = lease.upstream_token
        if not token:
            return
        url = f"{upstream_url()}/api/gate/lease/heartbeat"
        try:
            import requests
            resp = requests.post(url, json={"token": token}, timeout=(2, 5))
        except Exception as e:  # noqa: BLE001
            if not lease.upstream_trouble:
                lease.upstream_trouble = True
                logger.warning("[GPU-ADMISSION] The plant-wide lease %s of %s/%s could not be "
                               "kept alive (%s: %s) — asked again next tick",
                               token, lease.kind, lease.model_id, type(e).__name__, e)
            return
        if resp.status_code == 200:
            if lease.upstream_trouble:
                lease.upstream_trouble = False
                logger.info("[GPU-ADMISSION] The plant-wide lease %s answers again", token)
            return
        if resp.status_code == 404:
            # Given back meanwhile: then the answer was about a lease that
            # ended on purpose, and there is nothing to say.
            if lease.upstream_token == token:
                lease.upstream_token = ""
                logger.error("[GPU-ADMISSION] The plant-wide lease %s of %s/%s is gone (the "
                             "DevServer's gate no longer knows it) — this hold no longer "
                             "holds the card's turn", token, lease.kind, lease.model_id)
            return
        if not lease.upstream_trouble:
            lease.upstream_trouble = True
            logger.warning("[GPU-ADMISSION] The DevServer's gate answered HTTP %s to the "
                           "heartbeat of %s (%s/%s) — asked again next tick",
                           resp.status_code, token, lease.kind, lease.model_id)

    def _release_upstream(self, lease: Lease) -> None:
        token = lease.upstream_token
        if not token:
            return
        lease.upstream_token = ""
        url = f"{upstream_url()}/api/gate/lease/release"
        try:
            import requests
            # `cleared_comfyui`: the coordinator asked ComfyUI to free
            # everything during this hold, and the gate there believes the
            # same resident model this one did until it is told.
            resp = requests.post(url, json={"token": token, "failed": bool(lease.failed),
                                            "cleared_comfyui": bool(lease.comfyui_cleared)},
                                 timeout=(2, 10))
        except Exception as e:  # noqa: BLE001
            logger.warning("[GPU-ADMISSION] The plant-wide lease %s could not be given back "
                           "(%s: %s); the DevServer's reaper collects it",
                           token, type(e).__name__, e)
            return
        if resp.status_code != 200:
            logger.warning("[GPU-ADMISSION] The DevServer's gate answered HTTP %s to the release "
                           "of %s; its reaper collects what is left", resp.status_code, token)

    def release_upstream_leases(self, reason: str) -> None:
        """Give every plant-wide lease back — on the way out of this process,
        so the card's turn does not stay with a hold that no longer exists
        until the DevServer's reaper finds the heartbeat gone."""
        with self._cv:
            leased = [x for x in [self._active, *self._waiters, *self._remote_leases.values()]
                      if x is not None and x.upstream_token]
        seen = set()
        for x in leased:
            if id(x) in seen:
                continue
            seen.add(id(x))
            logger.warning("[GPU-ADMISSION] Giving the plant-wide lease of %s/%s back: %s",
                           x.kind, x.model_id, reason)
            x.failed = True
            self._release_upstream(x)

    def _reaper_loop(self) -> None:
        while True:
            time.sleep(self._reaper_interval_s)
            try:
                with self._cv:
                    if (self._prefetch_in_flight
                            and time.time() - self._prefetch_started_at > 300):
                        logger.warning("[GPU-ADMISSION] Prefetch claim for %s expired — "
                                       "releasing it so warming can happen again",
                                       self._prefetch_in_flight)
                        self._prefetch_in_flight = None
                    leased = [x for x in [self._active, *self._waiters,
                                          *self._remote_leases.values()]
                              if x is not None and x.upstream_token]
                seen = set()
                for x in leased:
                    if id(x) in seen:
                        continue
                    seen.add(id(x))
                    # Outside the lock: a request to another process is
                    # nothing to hold every waiter for.
                    self._heartbeat_upstream(x)
                self._sample_active_footprint()
                reaped: Optional[Lease] = None
                forced: Optional[Lease] = None
                with self._cv:
                    a = self._active
                    if a is not None and a.source == "remote":
                        age = time.time() - a.last_heartbeat
                        if age > self._heartbeat_timeout_s:
                            logger.warning(
                                "[GPU-ADMISSION] Reaping dead remote lease %s (%s) — "
                                "no heartbeat for %.0fs", a.id, a.kind, age)
                            self._active = None
                            self._remote_leases.pop(a.id, None)
                            reaped = a
                            # Nobody told us what finished loading. Keeping the
                            # previous belief would point affinity at a model
                            # that is not there any more.
                            self._last_key = None
                            self._cv.notify_all()
                    elif a is not None and a.source == "local":
                        # A local operation cannot report in, so its only signal is
                        # how long it has held the slot. Without this, one wedged
                        # CUDA call or one stalled model download stops the whole
                        # plant — every backend and the other process with it —
                        # until somebody restarts the service. Letting the next
                        # operation in may cost memory; a silent full stop costs
                        # the workshop.
                        held = time.time() - (a.admitted_at or a.created_at)
                        if held > self._max_hold_s:
                            logger.error(
                                "[GPU-ADMISSION] %s/%s has held the slot for %.0fs (limit %.0fs) — "
                                "releasing it so the plant can move. The operation itself is NOT "
                                "cancelled and may still be allocating; watch for memory pressure.",
                                a.kind, a.model_id, held, self._max_hold_s)
                            self._active = None
                            self._last_key = None
                            forced = a
                            self._cv.notify_all()
                if reaped is not None:
                    reaped.failed = True
                    self._release_upstream(reaped)
                if forced is not None:
                    # The same decision plant-wide: the next operation may go.
                    forced.failed = True
                    self._release_upstream(forced)
            except Exception as e:
                logger.error("[GPU-ADMISSION] Reaper error: %s", e)

    def prefetch_advice(self) -> Dict[str, Any]:
        """Which model could be warmed right now, beside the running one.

        The gate says whether there is room and time; it does not itself know
        how to warm a ComfyUI model — the workflows live in the DevServer, and
        that is who acts on this.

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
            from services.gpu_model_stats import get_model_stats
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
        # yet, which is why the flag is off. A correction needs a real mapping
        # from a lease model_id to the declared table; the keys do not match by
        # substring (`sd35_large_fp16` vs `stabilityai/stable-diffusion-3.5-large`),
        # and a mapping that silently misses is worse than none.

        try:
            from services.vram_coordinator import get_vram_coordinator
            coord = get_vram_coordinator()
            if not coord.has_authoritative_reading():
                out["reason"] = "no trustworthy VRAM reading"
                return out
            free = coord.get_free_vram_mb(use_cache=False)
        except Exception as e:
            out["reason"] = f"could not read free VRAM: {e}"
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

    def page_cache_advice(self) -> Dict[str, Any]:
        """Whose FILES could be read into RAM right now, beside the running run.

        The sibling of prefetch_advice with everything about VRAM taken out,
        because this fills the kernel's page cache and allocates nothing on the
        card. The three reasons GPU_ADMISSION_PREFETCH stays switched off all
        concern a footprint estimate that is a lower bound; here there is no
        footprint, so they fall away and this advice can be acted on.

        What remains is the part that was never in doubt: something is running,
        somebody is waiting, and that somebody needs DIFFERENT weights than the
        ones in use. A wrong answer here wastes disk reads and nothing else.
        """
        out: Dict[str, Any] = {"recommended": None, "reason": ""}
        with self._cv:
            a = self._active
            if a is None:
                out["reason"] = "nothing running - the next run has the disk to itself"
                return out
            if self._page_warm_in_flight:
                out["reason"] = f"already reading {self._page_warm_in_flight}"
                return out
            resident = a.affinity_key
            now = time.time()
            nxt = self._pick_from(list(self._waiters), resident, now)
            held = now - (a.admitted_at or a.created_at)
            _exp = self._expected_hold_s(a, self._last_key)
            remaining = None if _exp is None else max(0.0, _exp - held)

        if nxt is None:
            out["reason"] = "nobody waiting"
            return out
        if nxt.affinity_key == resident:
            out["reason"] = "next run uses the weights already in use"
            return out
        if remaining is not None and remaining < PAGE_WARM_MIN_REMAINING_S:
            # Only when the remaining time is actually MEASURED. Unknown goes
            # ahead: reading is abortable, and a partial read still helps the
            # load that follows. What this avoids is competing for the disk
            # with a load that is seconds away.
            out["reason"] = (f"only {remaining:.0f}s left on the running run - "
                             f"the disk belongs to whoever loads next")
            return out

        out["recommended"] = {
            "kind": nxt.kind,
            "model_id": nxt.model_id,
            "affinity_key": nxt.affinity_key,
            "label": nxt.label,
            # Which run currently holds the card. The reader uses it to warm
            # each waiting model ONCE per running job instead of on a timer.
            "active_id": a.id,
            "running_has_left_s": None if remaining is None else round(remaining),
        }
        out["reason"] = "time to read the next model off the disk"
        return out

    def page_warm_claim(self, affinity_key: str) -> bool:
        """Claim the single reading slot. False if one is already running."""
        with self._cv:
            if self._page_warm_in_flight:
                return False
            self._page_warm_in_flight = affinity_key
            return True

    def page_warm_done(self, affinity_key: str) -> None:
        with self._cv:
            if self._page_warm_in_flight == affinity_key:
                self._page_warm_in_flight = None

    def page_warm_still_wanted(self, affinity_key: str) -> bool:
        """Whether anybody is still waiting for these weights.

        False the moment the run is admitted: from then on it is loading, and
        a second reader on the same disk takes bandwidth from it rather than
        giving any.
        """
        with self._cv:
            return any(w.affinity_key == affinity_key for w in self._waiters)

    def forget_resident(self, why: str = "") -> None:
        """Whatever we believed was loaded is gone.

        Called when ComfyUI has been told to free everything, or after a
        forced reclaim. Without this the queue would keep being reordered
        toward a model that is no longer on the card — the reorder would then
        cost a load instead of saving one, which is worse than not reordering
        at all.
        """
        with self._cv:
            if self._active is not None:
                # The DevServer's gate believes the same thing and is told
                # when this hold is given back (_release_upstream).
                self._active.comfyui_cleared = True
            if self._last_key is not None:
                logger.info("[GPU-ADMISSION] Forgetting resident model %s (%s)",
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
        try:
            from services.vram_coordinator import get_vram_coordinator
            free = get_vram_coordinator().get_free_vram_mb(use_cache=False)
        except Exception:
            return
        if free <= 0:
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
            from services.gpu_model_stats import get_model_stats
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
                # not things. Without this cut, the honesty rule below would
                # silence the best-measured figure in the system — the
                # SD3.5 load itself.
                return stats.hold_estimate_s(lease.kind, lease.stats_key)

            will_be_resident = (lease.affinity_key == resident_key)
            includes_load = False
            if will_be_resident:
                est = measured(lease.kind)
            else:
                # A cold reading already has the load inside it — that is what
                # makes it cold. Only when there is none does the warm figure
                # plus a separately measured load stand in, which is how the
                # diffusers path has always worked: there the load is a lease
                # of its own and is measured apart.
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
        or the safety check, and only the DevServer sees them.
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
                    "label": a.label,
                    "source": a.source, "required_mb": a.required_mb,
                    # Since it was ADMITTED, as everywhere else in this file:
                    # counting the queue in would make a run that has just begun
                    # look like the oldest thing on the card.
                    "held_s": round(now - (a.admitted_at or a.created_at), 1),
                    "heartbeat_age_s": round(now - a.last_heartbeat, 1),
                    # Whether this hold has the card's turn on the DevServer's
                    # gate; the coordinator asks ComfyUI to free only then.
                    "plant_wide_lease": bool(a.upstream_token),
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
                "max_hold_s": self._max_hold_s,
                "remote_lease_tokens": list(self._remote_leases.keys()),
                "degraded": self._degraded,
                "affinity_enabled": self._affinity_enabled,
                "overtakes_granted": self._overtakes_granted,
            }


_admission: Optional["GpuAdmission"] = None
_admission_singleton_lock = threading.Lock()


def get_gpu_admission() -> "GpuAdmission":
    global _admission
    if _admission is None:
        with _admission_singleton_lock:
            if _admission is None:
                _admission = GpuAdmission()
    return _admission


def answered_with_failure(result) -> bool:
    """Did this view answer with something other than a result?

    The `failed` mark used to ride on exceptions alone. A view that catches its
    own trouble and RETURNS — a 400 for missing parameters, a 500 for a backend
    that came back empty, a load that reports `success: false` with a 200 on it
    — ended its `with` block normally, and the hold was booked as a valid
    measurement of how long that model takes. Eighteen such places stood in
    seven gated views (2026-08-18).

    That is not a bookkeeping detail. The hold feeds the shared ordering EMA
    and overwrites the residency belief under its own key, so the next run of
    ANOTHER surface counts as cold and files its warm success in that surface's
    cold bucket.

    A body saying `success: false` counts even at 200: a load that loaded
    nothing held the card for a length that says nothing about loading.
    Streamed and passthrough responses are left alone — their body is not there
    to be read, and reading it would consume it.
    """
    body = result
    if isinstance(result, tuple) and result:
        body = result[0]
        for part in result[1:]:
            if isinstance(part, bool):
                continue                      # not a status code
            if isinstance(part, int) and part >= 400:
                return True
            if isinstance(part, str) and part[:3].isdigit() and int(part[:3]) >= 400:
                return True

    data = body if isinstance(body, dict) else None
    if data is None and hasattr(body, "status_code"):
        try:
            if body.status_code >= 400:
                return True
            if (not getattr(body, "is_streamed", False)
                    and not getattr(body, "direct_passthrough", False)
                    and getattr(body, "is_json", False)):
                data = body.get_json(silent=True)
        except Exception:
            return False
    return isinstance(data, dict) and data.get("success") is False


def gated(kind: str, model_id: str = "", required_mb: float = 0):
    """
    Flask decorator: hold the slot for the whole request.

    For backends that do their loading and their forward pass inside one
    coroutine which the route runs to completion on this thread. Do NOT combine
    with a slot taken inside the backend on a worker thread — the gate is
    reentrant per thread, and a worker thread is a different thread.

    A view that answers with a failure marks its lease (`answered_with_failure`)
    — centrally, so a new error return cannot quietly become a measurement.
    """
    import functools

    def _decorate(view):
        @functools.wraps(view)
        def _wrapped(*args, **kwargs):
            from services.vram_coordinator import EvictionPriority
            with get_gpu_admission().slot(kind, model_id or kind, required_mb,
                                          EvictionPriority.NORMAL) as lease:
                result = view(*args, **kwargs)
                # None when the gate passed through reentrantly — then the
                # outer slot owns the mark.
                if lease is not None and answered_with_failure(result):
                    logger.info(
                        f"[GATE] {kind}: view answered with a failure, "
                        f"hold not counted as a measurement")
                    lease.failed = True
                return result
        return _wrapped
    return _decorate


def run_admitted(kind: str, model_id: str, required_mb: float, fn):
    """
    Run fn holding the slot. For backends whose forward pass already runs in a
    worker thread:

        await asyncio.to_thread(run_admitted, 'stable_audio', model_id, 0, _generate)
    """
    from services.vram_coordinator import EvictionPriority
    with get_gpu_admission().slot(kind, model_id, required_mb, EvictionPriority.NORMAL):
        return fn()


def release_upstream_leases(reason: str) -> None:
    """On the way out of this process every plant-wide lease goes back
    (GpuAdmission.release_upstream_leases). Nothing is built for it: a
    process that never took a hold has nothing to give back."""
    admission = _admission
    if admission is not None:
        admission.release_upstream_leases(reason)
