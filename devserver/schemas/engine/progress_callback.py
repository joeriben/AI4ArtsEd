"""
ContextVar for ComfyUI on_progress callback.

Used by schema_pipeline_routes (SSE generator) to inject a callback
that backend_router passes through to submit_and_track.
Non-streaming paths leave the var at None (safe default).
"""
import contextvars
from typing import Callable, Optional

_progress_callback: contextvars.ContextVar[Optional[Callable]] = contextvars.ContextVar(
    '_progress_callback', default=None
)


def set_progress_callback(callback: Optional[Callable]) -> contextvars.Token:
    return _progress_callback.set(callback)


def get_progress_callback() -> Optional[Callable]:
    return _progress_callback.get()
