"""
The lease: how a heavy operation takes the card's one slot.

ComfyUI generations are driven from this process; VoxCPM, Blender and a LoRA
training run in processes of their own. To keep one heavy operation on the
card at a time across all of them, the operation holds a lease on the gate
for its length — the load included, which is usually a different call than
the generation. See services/gpu_gate.py.

Since stage 7 of the move to ComfyUI the gate lives in this process, and a
lease is a call on it, not a request to another service. Two things follow.
Nothing here waits on a socket to itself, so a full thread pool cannot
deadlock the lease against the pages it serves. And there is no "unleased"
path any more: while the gate was another process, an unreachable gate let
the generation go ahead without the guarantee, because an unreachable gate
must not stop a workshop; a gate that is this process is reachable whenever
the generation is.

Waiting is bounded on the gate's side (GPU_ADMISSION_ACQUIRE_TIMEOUT_S), not
here. A second, shorter deadline here would only drop the caller while the
queue place stayed, and the operation would eventually be admitted for a
caller that is long gone.
"""

import asyncio
import contextlib
import logging
import threading

from my_app.services.gpu_gate import GpuBusy, get_gpu_gate

logger = logging.getLogger(__name__)


class BackendGenerationError(RuntimeError):
    """A backend answered that the generation broke, and in whose words.

    Beside GpuBusyError, and for the other half of the same problem: busy is not
    a failure and travels well, while a failure used to travel as nothing at
    all. A client read a 500, dropped the body, returned None, and the chunk
    said "returned empty result" — one sentence for a missing model file, a
    broken pipeline and a card with no memory left.

    The router decides on this sentence whether to hand the run to a second
    model (schemas/engine/backend_router.py, _is_card_fault). It can only decide
    it if the words survive the trip.
    """

    def __init__(self, reason: str, status: int = 0):
        self.reason = reason or "no reason given"
        self.status = int(status or 0)
        super().__init__(self.reason)

    @classmethod
    def from_response(cls, resp):
        """The service's OWN sentence, never the raw body — an HTML error page
        carries the server's file paths, and those have no business on a
        workshop screen. `reason_line` is the one place that judgement lives."""
        from my_app.utils.response_reason import reason_line
        said = ""
        try:
            said = ((resp.json() or {}).get("error") or "")
        except Exception:
            said = ""
        return cls(reason_line(said or resp.text, 300), resp.status_code)


class GpuBusyError(Exception):
    """The gate refused a lease, and WHICH of its refusals it was.

    The gate names four states apart — a long hold on the card (a training),
    a queue that is full, a wait that ran out, memory that stayed short after
    ComfyUI was asked to make room — and all four used to reach the surface
    as the single sentence "queue full". They are carried apart here:
    `reason` is the gate's token, `holder_kind` what holds the card on a long
    hold, `waiting` how many were in line. The message stays the gate's own
    sentence, for the hover.

    A refusal that arrives over HTTP without these fields comes out as the
    unnamed `busy`: the surface then says the general thing rather than a
    specific thing that would be wrong.
    """

    def __init__(self, message: str, reason: str = "busy",
                 holder_kind: str = "", waiting: int = 0):
        super().__init__(message)
        self.reason = reason or "busy"
        self.holder_kind = holder_kind
        self.waiting = waiting

    @classmethod
    def from_gate(cls, e: GpuBusy):
        return cls(str(e), reason=e.reason, holder_kind=e.holder_kind,
                   waiting=int(e.waiting or 0))

    @classmethod
    def from_payload(cls, payload, fallback: str = "device busy"):
        d = payload if isinstance(payload, dict) else {}
        try:
            waiting = int(d.get("waiting") or 0)
        except (TypeError, ValueError):
            waiting = 0
        return cls(d.get("detail") or fallback,
                   reason=d.get("busy_reason") or "busy",
                   holder_kind=d.get("holder_kind") or "",
                   waiting=waiting)

    @classmethod
    def from_response(cls, resp):
        """From a blocking `requests` 503 — body, broken body or no body.

        A refusal has to survive a body that will not parse. Letting the parse
        error out of here lands it in the caller's "unreachable" branch, and a
        busy card is then reported as one that cannot be reached at all.
        """
        try:
            payload = resp.json()
        except Exception:
            payload = None
        return cls.from_payload(payload)


def _acquire(kind, model_id, required_mb, label, workload, timeout_s) -> str:
    """The token, or GpuBusyError. Blocks for as long as the gate makes it
    wait; called on a worker thread from the async path."""
    try:
        return get_gpu_gate().acquire(kind, model_id, required_mb, label=label,
                                      workload=workload, timeout_s=timeout_s)
    except GpuBusy as e:
        raise GpuBusyError.from_gate(e) from e


def _release_sync(token: str, failed: bool = False) -> None:
    """Give the slot back with a plain call.

    Used from the async path as well, on purpose: when a generation is cancelled,
    every await raises immediately, so an awaited release would never happen
    and the whole plant would wait for the reaper. A call cannot be cancelled.
    """
    with contextlib.suppress(Exception):
        get_gpu_gate().release(token, failed=bool(failed))


def _beat(token: str) -> bool:
    """One heartbeat. False means the gate no longer knows this lease — it was
    reaped, or the process restarted — and from that moment the generation runs
    without the guarantee. Nothing here can stop it, so the least that is owed
    is saying so."""
    try:
        alive = get_gpu_gate().heartbeat(token)
    except Exception as e:  # noqa: BLE001 — a heartbeat may not end a generation
        logger.warning("[GPU-LEASE] heartbeat failed for %s: %s", token, e)
        return True
    if not alive:
        logger.error("[GPU-LEASE] Lease %s is gone — this generation is no "
                     "longer holding the GPU slot", token)
    return alive


@contextlib.contextmanager
def gpu_lease_sync(kind="comfyui", model_id="comfyui", required_mb=0, label="",
                   heartbeat_interval_s=10, workload="", timeout_s=None):
    """
    The lease for callers that are not async — the legacy workflow surface
    submits to ComfyUI and then polls for the result on its own thread, VoxCPM
    speaks on a worker thread.

    timeout_s bounds the wait on the gate's side for a caller that would rather
    hear "busy" than sit in the queue for the full acquire budget. Left unset,
    the gate decides, which is what a generation wants.
    """
    token = _acquire(kind, model_id, required_mb, label, workload, timeout_s)
    logger.info("[GPU-LEASE] Acquired %s (%s/%s, sync)", token, kind, model_id)
    stop = threading.Event()

    def _keep_alive():
        while not stop.wait(heartbeat_interval_s):
            if not _beat(token):
                return

    hb = threading.Thread(target=_keep_alive, name="gpu-lease-heartbeat", daemon=True)
    hb.start()
    failed = False
    try:
        yield token
    except BaseException:
        # Whatever ends this lease early — an abort raised into the body, a
        # cancelled task, a real crash — the run did not complete, and its
        # held time must not be recorded as if it had.
        failed = True
        raise
    finally:
        stop.set()
        _release_sync(token, failed)
        logger.info("[GPU-LEASE] Released %s (sync%s)", token,
                    ", failed" if failed else "")


@contextlib.asynccontextmanager
async def gpu_lease(kind="comfyui", model_id="comfyui", required_mb=0,
                    heartbeat_interval_s=10, label="", workload=""):
    """
    Hold a lease for a heavy operation run from this process. Waits in the
    gate's queue until the slot is free, raises GpuBusyError when the queue is
    full or the wait runs out, keeps the lease alive while it is held, and
    releases it on the way out.

    The wait happens on a worker thread: the gate is plain `threading`, and
    the event loop this runs on must keep serving the stream that is telling
    somebody where in the line they stand.
    """
    token = await asyncio.to_thread(_acquire, kind, model_id, required_mb,
                                    label, workload, None)
    logger.info("[GPU-LEASE] Acquired %s (%s/%s)", token, kind, model_id)

    async def _heartbeat_loop():
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                await asyncio.sleep(heartbeat_interval_s)
                if not _beat(token):
                    return

    hb = asyncio.create_task(_heartbeat_loop())
    failed = False
    try:
        yield token
    except BaseException:
        # Same rule as the sync twin: an early end is not a completed run.
        failed = True
        raise
    finally:
        hb.cancel()
        with contextlib.suppress(BaseException):
            await hb
        _release_sync(token, failed)
        logger.info("[GPU-LEASE] Released %s%s", token,
                    " (failed)" if failed else "")
