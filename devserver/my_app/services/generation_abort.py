"""
Cross-layer abort signal for a generation run.

The SSE route tracks cancellation per device, but it frees that state the
moment the stream closes — while the generation thread may still be waiting
its turn for the GPU. This registry outlives the stream: the route marks the
run, and the ComfyUI client checks the mark once its lease is granted, so a
cancelled run gives its turn back instead of rendering for a closed tab.

The run id travels as a ContextVar. The SSE route sets it before it copies
the context for the generation thread, so every layer below — orchestrator,
backend router, ComfyUI client — can ask "was my run aborted?" without the
run id being threaded through each signature.
"""

import contextvars
import threading
import time
from typing import Optional

# Set by the SSE route before the generation thread's context is copied.
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
