"""
Cross-layer abort signal for a generation run.

The SSE route tracks cancellation per device, but it frees that state the
moment the stream closes — while the generation thread may still be waiting
its turn for the GPU. This registry outlives the stream: the route marks the
run, and the ComfyUI client checks the mark once its lease is granted, so a
cancelled run gives its turn back instead of rendering for a closed tab.

The run id travels as a ContextVar. The generation routes set it before they
copy the context for the generation thread, and `ended_when_its_reader_leaves`
sets it around the model work of the Prompt Interception and the adaption,
so every layer below — orchestrator, backend router, ComfyUI client — can ask
"was my run aborted?" without the run id being threaded through each
signature.
"""

import asyncio
import contextlib
import contextvars
import logging
import threading
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# Set by the generation routes before the generation thread's context is
# copied, and by `ended_when_its_reader_leaves` around the work it watches.
CURRENT_RUN_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "ai4artsed_current_run_id", default=None
)

# The output config this run is producing, travelling the same way. It is what
# the gate measures durations against: one checkpoint serves several configs —
# the same wan2.2 weights run a short video and a long one — and a duration
# averaged across both describes neither. The model id stays what it was; it
# answers a different question, namely what has to be on the card.
CURRENT_OUTPUT_CONFIG: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "ai4artsed_current_output_config", default=None
)

_lock = threading.Lock()
_aborted: dict[str, float] = {}   # run_id -> when it was marked

_TTL_S = 2 * 3600


def _sweep_locked(now: float) -> None:
    stale = [rid for rid, ts in _aborted.items() if now - ts > _TTL_S]
    for rid in stale:
        _aborted.pop(rid, None)


def mark(run_id: Optional[str]) -> None:
    """Record that this run was cancelled or its client went away."""
    if not run_id:
        return
    now = time.time()
    with _lock:
        _sweep_locked(now)
        _aborted[run_id] = now


def unmark(run_id: Optional[str]) -> None:
    """A fresh stream for this run supersedes an old cancel.

    Run ids are reused on retry (the frontend sends its interception run id
    back, and the backend keeps the id while the run has no output). A person
    who cancelled and presses again means THIS run — the old mark must not
    refuse the new press.
    """
    if not run_id:
        return
    with _lock:
        _aborted.pop(run_id, None)


def is_aborted(run_id: Optional[str]) -> bool:
    if not run_id:
        return False
    with _lock:
        _sweep_locked(time.time())
        return run_id in _aborted


def current_run_aborted() -> bool:
    """True if the run this context belongs to was cancelled."""
    return is_aborted(CURRENT_RUN_ID.get())


# The prompts ComfyUI holds for a run right now, by run id. The streaming
# generation route learns a prompt id through its progress callback and stores
# it in its tracker entry; nothing else passes one. A station node run through
# llm_client.run_node_files (the song, the 3D mesh), the interception route's
# own Stage 4 and the non-streaming generation route left the cancel with no
# prompt to interrupt, and the card computed on for a run that was stopped
# (2026-10-01, the Flow's song). The ComfyUI client notes every
# prompt it submits under the run id of its context
# (comfyui_ws_client._submit_then_track); the cancel reads them here. The
# non-streaming generation route sets no run id in its context, so nothing is
# noted for it.
_prompts: dict[str, set[str]] = {}


def note_prompt(run_id: Optional[str], prompt_id: Optional[str]) -> bool:
    """Record that ComfyUI holds this prompt for this run, and say whether
    the run is already cancelled.

    One lock with `mark`: a cancel either marks the run before the prompt is
    noted, and the caller hears True and interrupts the prompt itself, or
    after, and finds the prompt in `prompts_of`.
    """
    if not run_id or not prompt_id:
        return False
    with _lock:
        _prompts.setdefault(run_id, set()).add(prompt_id)
        _sweep_locked(time.time())
        return run_id in _aborted


def forget_prompt(run_id: Optional[str], prompt_id: Optional[str]) -> None:
    """The prompt has ended; there is nothing left at ComfyUI to interrupt."""
    if not run_id or not prompt_id:
        return
    with _lock:
        held = _prompts.get(run_id)
        if held is not None:
            held.discard(prompt_id)
            if not held:
                _prompts.pop(run_id, None)


def prompts_of(run_id: Optional[str]) -> list[str]:
    """The prompts ComfyUI holds for this run now."""
    if not run_id:
        return []
    with _lock:
        return sorted(_prompts.get(run_id, ()))


class WatchedRun:
    """What `ended_when_its_reader_leaves` hands the work inside it."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        # Set, under the helper's lock, when the run is marked for its stream.
        self.left = False

    @property
    def ended(self) -> bool:
        """Whether this run has ended: its stream ended while the work ran, or
        it was stopped (an adopted id that a stop has marked).

        Read inside the `with` before a model call is started, and after it
        before anything is checked or answered. A run that has ended answers
        nobody: what a local model wrote for it was cut off at the card, and
        what a cloud model wrote ran to its end for nobody.
        """
        return self.left or is_aborted(self.run_id)


@contextlib.contextmanager
def ended_when_its_reader_leaves(client_gone: Optional[threading.Event], *,
                                 kind: str, label: str,
                                 run_id: Optional[str] = None):
    """A run id for the work inside, and the end of that work at ComfyUI once
    the stream it answers has ended.

    The work inside runs under a run id (`CURRENT_RUN_ID`), and the ComfyUI
    client notes every prompt it submits for it under that id (`note_prompt`).
    When `client_gone` is set -- the leaving signal of the stream transport
    (`streaming_response._pumped`), or a stream's own end -- the run is marked
    and every prompt it holds at ComfyUI is cancelled: taken out of the queue,
    or interrupted where it runs. The mark keeps it so for what comes after: a
    prompt this run submits later is refused at the lease, or interrupted the
    moment it is named (`comfyui_ws_client._with_gpu_lease`,
    `_submit_then_track`). A signal already set when the work begins marks the
    run before any of it is submitted.

    A prompt running on the card takes the interrupt at its next check; a
    language model checks between tokens, so loading its weights and reading
    the prompt in run to their end first.

    Only prompts at ComfyUI are ended. A call to a cloud model holds no card,
    is not reached from here, and runs to its end; the caller reads
    `WatchedRun.ended` after the `with` and answers nothing for that run.

    The cancel is sent again every two seconds, for every prompt the run
    still holds at ComfyUI, until the work has ended. ComfyUI answers both of
    its requests with 200 whether or not they found the prompt, and a prompt
    that went from the queue to the card between them clears the interrupt
    as it starts; the cancel sent again finds it running. A prompt that has
    ended is forgotten by the client (`forget_prompt`) and is not asked for
    any more.

    `run_id` adopts the id of a run that is registered already (the
    interception route's, which a stop finds by its device): the prompts are
    noted under it, so the stop's own cancel reaches them, and the watcher
    takes the stop's mark as it takes the leaving, also where there is no
    stream to watch. Its mark is left standing when the work ends, because
    the run that owns the id reads it afterwards. Without `run_id` the work
    gets an id of its own, `kind` as its prefix, and its mark is taken away
    when the work ends.

    With `client_gone` None and no `run_id` -- a caller that asked for one
    JSON body, where no leaving can be seen and nobody else knows the id --
    the work gets its run id and nothing else.
    """
    adopted = run_id is not None
    run = WatchedRun(run_id if adopted else f"{kind}_{uuid.uuid4().hex}")
    finished = threading.Event()
    lock = threading.Lock()
    token = None
    # From the run id on inside the `try`: a watcher that cannot start leaves
    # neither the run id set nor an own id marked.
    try:
        token = CURRENT_RUN_ID.set(run.run_id)
        if client_gone is not None and client_gone.is_set():
            mark(run.run_id)
            run.left = True
        if client_gone is not None or adopted:
            threading.Thread(target=_stop_when_ended,
                             args=(run, client_gone, finished, lock, label),
                             name=f"{kind}-ended", daemon=True).start()
        yield run
    finally:
        # Under the watcher's lock: once the work has ended, nothing marks the
        # run any more, so a mark taken away here stays away.
        with lock:
            finished.set()
            if not adopted:
                unmark(run.run_id)
        if token is not None:
            CURRENT_RUN_ID.reset(token)


def _stop_when_ended(run: WatchedRun, client_gone: Optional[threading.Event],
                     finished: threading.Event, lock: threading.Lock,
                     label: str) -> None:
    """The watcher of `ended_when_its_reader_leaves`, on a thread of its own."""
    taken: set[str] = set()   # prompts a cancel went through for; for the log
    told = warned = False
    while not finished.is_set():
        # Wakes the moment the stream ends; looks at a stop's mark and at
        # `finished` twice a second meanwhile.
        left = client_gone.wait(0.5) if client_gone is not None else False
        if not left and not is_aborted(run.run_id):
            if client_gone is None:
                finished.wait(0.5)
            continue
        with lock:
            if finished.is_set():
                return
            if left:
                mark(run.run_id)
                run.left = True
        held = prompts_of(run.run_id)
        failed = []
        fresh = 0
        for prompt_id in held:
            try:
                from my_app.services.comfyui_ws_client import get_comfyui_ws_client
                cause = asyncio.run(get_comfyui_ws_client().try_cancel_job(prompt_id))
            except Exception as e:  # noqa: BLE001 - reported, and asked again below
                cause = repr(e)
            if cause:
                failed.append(f"{prompt_id}: {cause}")
            elif prompt_id not in taken:
                taken.add(prompt_id)
                fresh += 1
        if not told:
            told = True
            why = "its stream ended" if left else "it was stopped"
            said = (f"{fresh} of {len(held)} prompt(s) at ComfyUI cancelled" if held
                    else "no prompt of it at ComfyUI")
            logger.info(f"[{label}] Run {run.run_id} ends, {why}; {said}")
        elif fresh:
            logger.info(f"[{label}] Run {run.run_id}: {fresh} more prompt(s) at ComfyUI cancelled")
        if failed:
            (logger.debug if warned else logger.warning)(
                f"[{label}] Run {run.run_id}: cancel not taken ({'; '.join(failed)}); "
                f"asked again in 2 s")
            warned = True
        finished.wait(2)
