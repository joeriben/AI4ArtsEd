"""Which run has asked to stop, so the card stops computing for it.

Pressing "stop" used to end the SSE stream and nothing else. On the ComfyUI
path the job was really cancelled; on the Diffusers path the page went quiet
while the card calmly finished the picture — in the log a
`Cancelled during Diffusers generation` and, eight seconds later, a
`STAGE4-GEN Success` for an image nobody would ever see. On one GPU serving
a room full of tablets, that is the next person's waiting time.

Nothing had to be invented for this. Diffusers leaves the denoising loop as
soon as `pipe._interrupt` is set, and `callback_on_step_end` — the hook that
sets it — was already passed on every generation path, used only for the
progress bar. What was missing was a flag and a way to raise it.

**The key is the run label.** Every request from the DevServer already
carries `run_label` (the run id, injected in `diffusers_client._post`), and
`diffusers_routes.before_request` puts it in `CURRENT_RUN_LABEL`. The
DevServer knows the same id. So a cancel names the run, not a slot: a stop
pressed for one run cannot end someone else's, even when the card has moved
on in between.

**A stopped run is not a failed one.** After an interrupt the pipeline does
not raise — it returns whatever half-denoised latents it has, and a caller
that does not look would hand out that mush as the result. Hence
`raise_if_cancelled()` after the call, and `GenerationCancelled` as its own
exception, kept out of the `except Exception -> return None` funnels so a
stop is never booked as a broken generation.

**Lifetime.** The mark is consumed by the run it names (`raise_if_cancelled`
takes it out) — a stop pressed a moment too late, when the picture is
already finished, leaves a mark that no run ever reads, and the sweep in
`request_cancel` clears it after `_TTL`. Run ids are unique, so a leftover
mark cannot hit a later run either way.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cancelled: dict = {}          # run_label -> when the stop was asked for
_TTL = 1800.0                  # matches the DevServer generation tracker


class GenerationCancelled(Exception):
    """The run was stopped on request. Nothing broke."""

    def __init__(self, run_label: str = ""):
        super().__init__(f"Generation cancelled for run {run_label or '?'}")
        self.run_label = run_label


def current_run_label() -> str:
    """The run this thread is working for, as the request set it."""
    try:
        from services.gpu_admission import CURRENT_RUN_LABEL
        return CURRENT_RUN_LABEL.get() or ""
    except Exception:
        return ""


def request_cancel(run_label: str) -> bool:
    """Mark a run as stopped. Returns False for an empty label."""
    if not run_label:
        return False
    now = time.time()
    with _lock:
        for stale in [k for k, t in _cancelled.items() if now - t > _TTL]:
            del _cancelled[stale]
        _cancelled[run_label] = now
    logger.info(f"[CANCEL] Stop requested for run {run_label}")
    return True


def is_cancelled(run_label: str) -> bool:
    if not run_label:
        return False
    with _lock:
        return run_label in _cancelled


def clear_cancel(run_label: str) -> None:
    with _lock:
        _cancelled.pop(run_label, None)


def interrupt_if_cancelled(pipe) -> bool:
    """Leave the denoising loop if this run has been stopped.

    Called from `callback_on_step_end`, which runs after every step. The mark
    is NOT consumed here — it fires once per step, and `raise_if_cancelled`
    still has to see it after the pipeline returns.
    """
    label = current_run_label()
    if not label or not is_cancelled(label):
        return False
    try:
        pipe._interrupt = True
    except Exception as e:                       # pragma: no cover
        logger.warning(f"[CANCEL] Could not interrupt pipeline: {e}")
        return False
    return True


def raise_if_cancelled() -> None:
    """After the pipeline returns: was this a result, or a stopped run?

    Consumes the mark, so the next run under the same label starts clean.
    """
    label = current_run_label()
    if label and is_cancelled(label):
        clear_cancel(label)
        logger.info(f"[CANCEL] Run {label} stopped mid-generation")
        raise GenerationCancelled(label)
