"""
LLM Backend — local LLM/VLM inference through supervised llama-server children.

One child process per alias, spawned and ended by this service (see
services/llm_child.py), reserved for before it starts and booked in the VRAM
coordinator by its measured per-PID figure. The public surface is the one the
in-process engine had — chat, chat_stream, generate, the model lists, the
eviction hook — because the routes, the safety chain and the Compare Hub all
call it unchanged.

WHY A CHILD. Three failure classes, and only the first of them was ever within
reach of a better estimate:

  * A crash takes one alias instead of the whole service. Eleven SIGSEGVs
    stand in the journal between 2026-08-15 and 2026-08-29, all inside the
    image encoder, each of them killing every content check running at that
    moment. And the load-time check that needs no estimate at all is available
    here: the build logs the encoder's compute buffer only when it was really
    reserved, so its absence refuses the load.
  * The Python chat handler's bookkeeping — which damaged every second image
    reading — is not on this path; llama-server does its own.
  * A GGUF that aborts on load, or a model whose template the handlers do not
    know, costs a child instead of being excluded.

WHAT DID NOT CHANGE. No output caps: `max_tokens` travels only when the caller
gave one. No read timeout on the parent side. No fallback of any kind — a child
that dies is an error with its exit code, never a quiet retry somewhere else.
The </think> partition, the RepetitionGuard and the finish_reason vocabulary
("stop", "length", "repetition") are what they were.
"""

import base64
import codecs
import contextlib
import json
import logging
import os
import subprocess
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from services.repetition_guard import RepetitionGuard
from services.llm_child import (
    ChildStartupError,
    ChildState,
    ChildSupervisor,
    InFlightRequest,
    SupervisedChild,
    unblock_stream,
)
# The registry, the alias table and the refusal class stay where they are: they
# describe the models, not the engine. Importing them costs nothing — llm_backend imports llama_cpp and
# torch inside its methods, never at module level — and no in-process backend
# object is ever constructed unless LLM_ENGINE says so.
from services.llm_backend import (
    MODEL_ALIASES,
    MODEL_CONFIGS,
    ModelLoadRefused,
    VLM_VISION_COMPUTE_MB,
    _budget_breakdown,
    load_floor_mb,
    resolve_window,
)

logger = logging.getLogger(__name__)

__all__ = [
    "LLMBackend", "ChildDied", "ChildRequestError", "ModelLoadRefused",
    "MODEL_CONFIGS", "MODEL_ALIASES", "VLM_VISION_COMPUTE_MB", "resolve_window",
    "get_llm_backend", "reset_llm_backend",
]


class ChildDied(RuntimeError):
    """The child stopped answering in the middle of a generation.

    Raised above all where a stream ended without its terminator. That case has
    exactly one honest reading — the answer is incomplete and nobody knows how
    incomplete — so it must never arrive at a caller as finish_reason "stop":
    the image safety check reads that field and would pass a truncated reading
    as a finished one.
    """

    def __init__(self, alias: str, exit_code: Optional[int],
                 log_tail: Optional[List[str]] = None, detail: str = "",
                 ended: Optional[str] = None):
        self.alias = alias
        self.exit_code = exit_code
        self.log_tail = list(log_tail or [])
        # "the process is still running" is the right half of the diagnosis
        # only where the process dying WAS the question. Where the connection
        # ended under a healthy child, saying it is still running reads as the
        # cause, and sends the reader after the wrong thing.
        ended = ended or (f"exit {exit_code}" if exit_code is not None
                          else "the process is still running")
        tail = (" | ".join(self.log_tail[-5:])) if self.log_tail else "no output recorded"
        message = detail or f"{alias}'s server stopped answering"
        super().__init__(f"{message} ({ended}): {tail}")


class ChildRequestError(RuntimeError):
    """The child answered, and what it answered was an error.

    `status` is what the child said; `route_status` is what this service says on
    to its callers — a 503 stays a 503 (the child is loading or busy, the same
    request works later), everything else becomes a 500 with the child's own
    sentence, so the DevServer log carries the cause instead of "inference
    failed".
    """

    def __init__(self, alias: str, status: int, message: str):
        self.alias = alias
        self.status = int(status)
        self.message = message
        super().__init__(f"{alias}: {message} (HTTP {self.status})")

    @property
    def route_status(self) -> int:
        return 503 if self.status == 503 else 500


# =============================================================================
# SSE
# =============================================================================

def iter_sse_events(response: Any,
                    on_activity: Optional[Callable[[], None]] = None
                    ) -> Iterator[Tuple[str, str]]:
    """Yield (event, data) for a text/event-stream body, per the grammar.

    Written out rather than taken from a library because every one of these
    rules has a shape in llama.cpp's output that would otherwise be misread:

      * a line starting with ':' is a comment (the keep-alive ping),
      * the field/value split is on the FIRST colon, and one leading space of
        the value is stripped — JSON payloads contain colons throughout,
      * `data` accumulates across lines and is joined with newlines,
      * the event ends at the blank line, not at the chunk boundary,
      * bytes are decoded as UTF-8 incrementally, so a character split across
        two HTTP chunks arrives whole instead of as two replacement marks.

    A frame the child never terminated is DISCARDED, with a warning naming what
    was thrown away. Half a frame is half a JSON object; handing it on would
    turn a connection that broke into an answer that parsed, and the caller
    would then see a stream ending without its terminator — which is exactly
    what happened, and what the death path exists to report.
    """
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    buffer = ""
    event = ""
    data_lines: List[str] = []

    def _take(line: str):
        nonlocal event, data_lines
        if line == "":
            if data_lines:
                out = (event or "message", "\n".join(data_lines))
                event, data_lines = "", []
                return out
            event = ""
            return None
        if line.startswith(":"):
            return None
        field, sep, value = line.partition(":")
        if sep and value.startswith(" "):
            value = value[1:]
        if not sep:
            field, value = line, ""
        if field == "data":
            data_lines.append(value)
        elif field == "event":
            event = value
        return None

    # chunk_size=None: llama-server serves the stream chunked (cpp-httplib's
    # chunked content provider), and this yields one HTTP chunk as it arrives.
    # A fixed size would make the library wait for that many bytes on a body
    # that is not chunked, which hands the caller the whole answer at once —
    # and the repetition guard would then never see a growing text at all.
    for chunk in response.iter_content(chunk_size=None):
        if not chunk:
            continue
        if on_activity is not None:
            # Anything at all, before it is parsed: a keep-alive comment says
            # the child is working just as a token does, and the bound that
            # watches a silent generation must see both.
            on_activity()
        buffer += decoder.decode(chunk)
        while "\n" in buffer:
            line, _, buffer = buffer.partition("\n")
            out = _take(line.rstrip("\r"))
            if out is not None:
                yield out

    buffer += decoder.decode(b"", final=True)
    if buffer:
        # Accumulates like any other line; it cannot be the blank line that
        # ends a frame, so nothing is dispatched from here.
        _take(buffer.rstrip("\r"))
    if data_lines:
        discarded = "\n".join(data_lines)
        logger.warning("[LLM] The stream ended inside an event; %d character(s) "
                       "discarded rather than passed on as an answer: %.200s",
                       len(discarded), discarded)


# =============================================================================
# Images
# =============================================================================

_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def sniff_image_mime(payload: bytes) -> Optional[str]:
    """The image type these bytes actually are, or None.

    The callers hand over base64 without saying what it is, and the in-process
    path declared everything image/jpeg. This build discards the declaration
    too — handle_media in server-common.cpp pushes the raw bytes on and mtmd
    sniffs them — so the declared type is read by people rather than by the
    server. It is derived from the bytes all the same: a data URL that says PNG
    over JPEG bytes is a lie in a log somebody will one day debug against, and
    the moment a build starts believing the declaration, a wrong one becomes a
    decode error for a reading nobody can repeat.
    """
    for magic, mime in _MAGIC:
        if payload.startswith(magic):
            return mime
    if payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return "image/webp"
    return None


def data_url_for(image_b64: str) -> str:
    """A data URL with the MIME the bytes carry. Unknown bytes go as JPEG."""
    if image_b64.startswith("data:"):
        return image_b64
    head = image_b64[:44]  # 44 base64 characters = 33 bytes, no padding needed
    mime = None
    try:
        mime = sniff_image_mime(base64.b64decode(head, validate=False))
    except Exception:  # noqa: BLE001
        mime = None
    if mime is None:
        logger.warning("[LLM] Image bytes match no known signature — sending it "
                       "as image/jpeg")
        mime = "image/jpeg"
    return f"data:{mime};base64,{image_b64}"


# =============================================================================
# The backend
# =============================================================================

class LLMBackend:
    """Local LLM/VLM inference, one supervised llama-server per alias."""

    # The coordinator hands this method one NVML snapshot per collection pass;
    # see services/vram_coordinator.VRAMBackend.
    ACCEPTS_NVML_SNAPSHOT = True

    def __init__(self, supervisor: Optional[ChildSupervisor] = None,
                 coordinator: Any = None, register: bool = True):
        self._coordinator = coordinator
        self._supervisor = supervisor or self._build_supervisor()
        # Global, as it always was: one load at a time across all aliases, so
        # that two large loads never read off the disk and onto the card
        # together. Never held across an HTTP call.
        self._load_lock = threading.Lock()
        self._build_cache: Optional[str] = None

        if register:
            self._register_with_coordinator()
        logger.info("[LLM] Initialized: supervised llama-server children (%s)",
                    self._supervisor.binary)

    # --------------------------------------------------------------- plumbing

    @staticmethod
    def _build_supervisor() -> ChildSupervisor:
        from config import (LLAMA_SERVER_BIN, LLM_CHILD_LOAD_CEILING_S,
                            LLM_CHILD_PORT_BASE, LLM_CHILD_PORT_COUNT,
                            LLM_CHILD_SOCKET_TIMEOUT_S, LLM_CHILD_STALL_S,
                            LLM_CHILD_STATE_DIR, LLM_CHILD_WARMUP_STALL_S)
        return ChildSupervisor(
            binary=LLAMA_SERVER_BIN,
            port_base=LLM_CHILD_PORT_BASE,
            port_count=LLM_CHILD_PORT_COUNT,
            socket_timeout_s=LLM_CHILD_SOCKET_TIMEOUT_S,
            stall_s=LLM_CHILD_STALL_S,
            load_ceiling_s=LLM_CHILD_LOAD_CEILING_S,
            warmup_stall_s=LLM_CHILD_WARMUP_STALL_S,
            state_dir=str(LLM_CHILD_STATE_DIR),
            nvml_pid_mb=_coordinator_pid_mb,
            nvml_invalidate=_coordinator_invalidate_nvml,
        )

    def _get_coordinator(self):
        if self._coordinator is not None:
            return self._coordinator
        try:
            from services.vram_coordinator import get_vram_coordinator
            return get_vram_coordinator()
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] VRAM coordinator unavailable: %s", e)
            return None

    def _register_with_coordinator(self) -> None:
        """Announce the backend, the children's PIDs, and how to end them.

        The PID registration is what keeps a child out of the foreign column:
        it runs in another process, so without it the coordinator would count
        20 GB of our own model as somebody else's, warn about it, and offer it
        to kill-foreign.
        """
        coordinator = self._get_coordinator()
        if coordinator is None:
            return
        try:
            coordinator.register_backend(self)
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] Failed to register with VRAM coordinator: %s", e)
            return

        def _announce(child: SupervisedChild) -> None:
            coordinator.register_owned(
                child.pid, child.starttime, f"llm child — {child.alias}",
                confirm=_confirm_owned(child))

        def _withdraw(child: SupervisedChild) -> None:
            # With the starttime: a PID is reused within hours on a busy box,
            # and a corpse withdrawn late must not take out the entry of the
            # live child that inherited its number.
            coordinator.unregister_owned(child.pid, child.starttime)

        try:
            self._supervisor.set_owner_hooks(_announce, _withdraw)
            coordinator.register_owned_terminator("llm", self.terminate_all)
            logger.info("[LLM] Registered with VRAM coordinator")
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] Could not register child ownership: %s", e)

    # =========================================================================
    # VRAMBackend protocol
    # =========================================================================

    def get_backend_id(self) -> str:
        return "llm"

    def receive_nvml_snapshot(self, nvml_info: Optional[Dict[str, Any]]) -> None:
        """Book every child from ONE NVML enumeration (see llm_child.update_ledger)."""
        if nvml_info is None:
            self._supervisor.update_ledger(None)
            return
        by_pid: Dict[int, Optional[float]] = {}
        for proc in nvml_info.get("processes", []) or []:
            pid = proc.get("pid")
            if not isinstance(pid, int):
                continue
            by_pid[pid] = (None if proc.get("vram_unknown")
                           else float(proc.get("vram_mb") or 0.0))
        self._supervisor.update_ledger(by_pid)

    def get_registered_models(self) -> List[Dict[str, Any]]:
        from services.vram_coordinator import EvictionPriority
        return [
            {
                "model_id": child.alias,
                "vram_mb": child.vram_mb,
                "priority": EvictionPriority.LOW,  # a child is cheap to respawn
                "last_used": child.last_used,
                "in_use": child.in_use,
            }
            for child in self._supervisor.snapshot()
            if child.state is ChildState.READY
        ]

    def evict_model(self, model_id: str) -> bool:
        """Coordinator hook. Refuses while a request is in flight."""
        return self.unload(model_id, force=False)

    # =========================================================================
    # Loading / unloading
    # =========================================================================

    @staticmethod
    def _resolve_alias(model: str) -> str:
        model = model.replace("local/", "") if model.startswith("local/") else model
        return MODEL_ALIASES.get(model, model)

    @staticmethod
    def _needs_vision(config: Dict[str, Any]) -> bool:
        """True exactly when this child will build an image encoder.

        For a child that is decided by one thing: whether --mmproj is on the
        command line. The in-process engine had to ask which Python handler
        class it was about to construct; there is no such class here.
        """
        return bool(config.get("mmproj_path"))

    def unload(self, model: str, force: bool = False) -> bool:
        """End a child. False if it is busy (without force), absent, or survived."""
        return self._supervisor.unload(self._resolve_alias(model), force=force)

    def terminate_all(self, reason: str = "shutdown") -> None:
        """End every child — shutdown, and the coordinator's emergency reclaim."""
        self._supervisor.terminate_all(reason)

    def _acquire(self, model: str) -> SupervisedChild:
        """A READY child for this alias, refcount raised. Raises ModelLoadRefused."""
        alias = self._resolve_alias(model)
        # Before anything, so that only a death recorded during THIS attempt can
        # be reported as its cause. Aliases outlive children by hours.
        began = time.monotonic()
        child = self._supervisor.acquire(alias)
        if child is not None:
            return child
        # A death met HERE is answered by loading, which is what happens next.
        self._supervisor.take_death(alias)

        self._load(alias)

        child = self._supervisor.acquire(alias)
        if child is not None:
            return child

        death = self._supervisor.take_death(alias, after=began)
        if death is not None:
            # It was started for this request and did not survive to serve it.
            # Reported as the death it is, with the exit code and the last lines
            # — a refused load would say the model never reached the card, and
            # send the caller back to try again into a model that crashes.
            raise ChildDied(
                alias, death.get("exit_code"), death.get("log_tail"),
                f"{alias}'s server died before the request it was started for "
                f"could run")
        # Loaded and gone again: an eviction ran between the two lines.
        raise ModelLoadRefused(
            f"model {alias} could not be loaded: it was evicted between its "
            f"load and its use")

    def _load(self, alias: str) -> None:
        """Bring up the child for this alias. Raises ModelLoadRefused.

        The shape is the one the in-process load had, because the reasons have
        not changed: the plant-wide slot is taken with a short deadline and
        given up rather than waited for (what children see must not queue behind
        a video render), and the room is RESERVED across the load, because
        between the grant and the weights arriving nothing in NVML's reading
        shows that it is spoken for.
        """
        config = MODEL_CONFIGS.get(alias)
        if not config:
            raise ModelLoadRefused(f"model {alias} could not be loaded: unknown model")
        if not os.path.exists(config["model_path"]):
            raise ModelLoadRefused(
                f"model {alias} could not be loaded: model file not found: "
                f"{config['model_path']}")
        mmproj = config.get("mmproj_path")
        if mmproj and not os.path.exists(mmproj):
            raise ModelLoadRefused(
                f"model {alias} could not be loaded: mmproj not found: {mmproj}")
        if not self.is_available():
            raise ModelLoadRefused(
                f"model {alias} could not be loaded: {self._supervisor.binary} is "
                f"not an executable file — build llama.cpp or set LLAMA_SERVER_BIN")

        with self._load_lock:
            existing = self._supervisor.get(alias)
            if existing is not None:
                # READY is a record of what was true when it answered /health.
                # A request that waited here behind another alias's load may be
                # looking at a child that died in the meantime, and returning on
                # the record alone hands it exactly the corpse this whole path
                # exists to avoid.
                if existing.state is ChildState.READY and existing.reap() is None:
                    return
                # Otherwise: a child stuck in LOADING — the wreck of an attempt
                # that never reached its own cleanup — or one whose process is
                # gone. Either way it holds a port and possibly memory, and
                # nothing will ever hand it out.
                logger.warning("[LLM] %s stands in state %s (exit %s) and is being "
                               "replaced", alias, existing.state.value, existing.poll())
                self._supervisor.unload(alias, force=True)

            # The window and the room it costs come from the model's own file;
            # a model fetched after import is resolved here.
            resolve_window(alias)
            if config.get("n_ctx") is None:
                raise ModelLoadRefused(
                    f"model {alias} could not be loaded: its file declares no "
                    f"context length, and this service does not invent one")

            needs_vision = self._needs_vision(config)
            # What the coordinator has to guarantee is the floor: the child is
            # spawned with `--fit on` and no `-c`, so llama.cpp sizes the cache
            # to the memory the card has instead of reserving the whole window.
            # Asking for the whole window here reserved 82 GB for a model that
            # runs in 16 (measured 2026-09-09) and refused loads that fit.
            floor_mb = load_floor_mb(config)
            estimated_mb = float(floor_mb if floor_mb is not None
                                 else config["estimated_vram_mb"])
            if needs_vision:
                estimated_mb += VLM_VISION_COMPUTE_MB

            try:
                from services.gpu_admission import get_gpu_admission, GpuBusy
                from services.vram_coordinator import EvictionPriority as _EP
            except Exception as e:  # noqa: BLE001
                # Outside the inner try on purpose: GpuBusy would be an unbound
                # name in the except clause below if this import ever failed.
                logger.warning("[LLM] Could not consult the GPU gate: %s", e)
                self._load_gated(alias, config, needs_vision, estimated_mb)
                return

            with contextlib.ExitStack() as gate:
                lease = None
                try:
                    lease = gate.enter_context(get_gpu_admission().slot(
                        "llm-load", alias, 0, _EP.NORMAL, timeout_s=5.0))
                except GpuBusy:
                    logger.warning("[LLM] Loading %s without the GPU slot — the card "
                                   "is busy and a content check must not queue "
                                   "behind a render", alias)
                except Exception as e:  # noqa: BLE001
                    logger.warning("[LLM] Could not consult the GPU gate: %s", e)
                try:
                    self._load_gated(alias, config, needs_vision, estimated_mb)
                except BaseException:
                    if lease is not None:
                        # A refused load reports itself by raising; without this
                        # the gate would file the attempt as a valid duration.
                        lease.failed = True
                    raise

    @staticmethod
    def _blind_refusal(alias: str, detail: str) -> str:
        """Why an image encoder is never built against a figure nobody measured.

        These rails come from the in-process engine unchanged, and the child's
        own check does NOT replace them. They act at different moments and on
        different failures: this one refuses BEFORE anything is spawned, when
        free VRAM cannot be verified against the other processes on the card;
        the compute-buffer line in the child's log refuses AFTER the load, when
        the buffer was silently not produced. Dropping the first would mean
        loading a 9 GB model blind and finding out from the second.
        """
        return (
            f"{alias} carries an image encoder and free VRAM cannot be verified "
            f"against the other processes on this card ({detail}). Loading it "
            f"blind would risk the encoder finding no room for its compute "
            f"buffer, which llama.cpp does not report and this service does not "
            f"survive, so the load is refused instead."
        )

    def _refuse_blind(self, alias: str, detail: str) -> None:
        reason = self._blind_refusal(alias, detail)
        logger.error("[LLM] %s", reason)
        raise ModelLoadRefused(f"model {alias} could not be loaded: {reason}")

    @staticmethod
    def _fit_target_mb(coordinator) -> Optional[int]:
        """The room llama-server has to leave free on the card.

        `--fit` fills the device up to this margin, so the margin is what the
        rest of the platform keeps: everything the coordinator would NOT hand
        this load. Derived from the card and from what stands on it right now,
        which is what makes the neighbour — ComfyUI holding a checkpoint,
        another child mid-answer — the bound instead of a number typed here.
        llama.cpp's own default of 1024 MB is the floor: below it a card that
        reads as empty would be filled to the last megabyte.
        """
        try:
            total = float(coordinator.get_total_vram_mb())
            obtainable = float(coordinator.get_obtainable_vram_mb())
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] Could not ask the coordinator for the fit "
                           "margin (%s) — llama.cpp keeps its own default", e)
            return None
        if total <= 0:
            return None
        return int(max(1024.0, total - obtainable))

    def _load_gated(self, alias: str, config: Dict[str, Any], needs_vision: bool,
                    estimated_mb: float) -> None:
        """The spawn itself, with the slot taken and the room reserved."""
        coordinator = self._get_coordinator()
        reservation = None
        if coordinator is None:
            if needs_vision:
                self._refuse_blind(alias, "the coordinator could not be consulted")
        else:
            # Asked before the request, so that a refusal on this ground never
            # leaves a reservation standing.
            authoritative = False
            try:
                authoritative = bool(coordinator.has_authoritative_reading())
            except Exception as e:  # noqa: BLE001
                logger.warning("[LLM] Could not check the VRAM sensor: %s", e)
            if needs_vision and not authoritative:
                self._refuse_blind(alias, "NVML is not answering")

            granted, shortfall = True, None
            try:
                from services.vram_coordinator import EvictionPriority
                granted, shortfall, reservation = coordinator.request_vram_detailed(
                    "llm", estimated_mb, EvictionPriority.NORMAL, hold=True)
            except Exception as e:  # noqa: BLE001
                logger.warning("[LLM] VRAM coordinator request failed: %s", e)
                if needs_vision:
                    self._refuse_blind(alias, f"the request itself failed: {e}")
            if not granted:
                # A measured shortfall is a refusal, and for a vision model it is
                # a refusal either way: it reached this line only with an
                # authoritative reading behind it. A shortfall reported by a
                # coordinator whose sensors are all gone is not a measurement at
                # all — free VRAM reads 0 there and every content check on the
                # platform would stop — so the TEXT path goes ahead and says so.
                if needs_vision or self._sensor_can_read_the_card(coordinator):
                    breakdown = _budget_breakdown(config, estimated_mb)
                    reason = (f"VRAM shortfall for {alias}: needed {estimated_mb:.0f}MB "
                              f"({breakdown}) — {shortfall or 'no detail recorded'}")
                    logger.error("[LLM] %s", reason)
                    self._release(coordinator, reservation)
                    raise ModelLoadRefused(f"model {alias} could not be loaded: {reason}")
                logger.warning("[LLM] Coordinator reports no room for %s, but nothing "
                               "can read the card right now — loading anyway rather "
                               "than stopping the checks", alias)

        try:
            self._supervisor.start(alias, config, needs_vision,
                                   fit_target_mb=self._fit_target_mb(coordinator))
        except ChildStartupError as e:
            # The last lines travel with the refusal: the exit code says THAT it
            # failed, and only the child's own output says why.
            tail = " | ".join(e.log_tail[-5:])
            reason = f"model {alias} could not be loaded: {e}"
            if e.exit_code is not None:
                reason += f" (exit {e.exit_code})"
            if tail:
                reason += f" — last lines: {tail}"
            logger.error("[LLM] %s", reason)
            raise ModelLoadRefused(reason) from e
        finally:
            # The promise ends with the attempt either way: on success the
            # memory is on the card and NVML counts it, on failure nothing was
            # taken. Holding it longer makes the card look fuller than it is.
            self._release(coordinator, reservation)

    @staticmethod
    def _release(coordinator: Any, reservation: Optional[str]) -> None:
        if reservation is None or coordinator is None:
            return
        try:
            coordinator.release_reservation(reservation)
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] Could not release the VRAM reservation: %s", e)

    @staticmethod
    def _sensor_can_read_the_card(coordinator: Any) -> bool:
        try:
            if coordinator.has_authoritative_reading():
                return True
        except Exception:  # noqa: BLE001
            pass
        try:
            import torch
            return bool(torch.cuda.is_available())
        except Exception:  # noqa: BLE001
            return False

    # =========================================================================
    # Inference
    # =========================================================================

    def chat(self, model: str, messages: list, images: Optional[list] = None,
             temperature: float = 0.7, max_tokens: Optional[int] = None,
             repetition_penalty: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Chat completion, joined from chat_stream so both paths end alike.

        A blocking caller gets what a streaming one gets: the repetition stop,
        and a finish_reason saying how the answer ended. The </think> partition
        is unchanged — with --reasoning-format none the thoughts stay in the
        content, exactly where the in-process engine left them.
        """
        try:
            pieces: List[str] = []
            finish_reason = "stop"
            for kind, value in self.chat_stream(
                model=model, messages=messages, images=images,
                temperature=temperature, max_tokens=max_tokens,
                repetition_penalty=repetition_penalty,
            ):
                if kind == "token":
                    pieces.append(value)
                else:
                    finish_reason = value or "stop"

            text = "".join(pieces).strip()
            thinking = None
            if "</think>" in text:
                head, _, tail = text.partition("</think>")
                thinking = head.replace("<think>", "").strip() or None
                text = tail.strip()
            elif "<think>" in text:
                # The block was opened and never closed: the generation ended
                # inside the reasoning, at the context ceiling or under the
                # repetition guard. Everything after the opener is thinking and
                # stays thinking -- passed on as `content` it stood on the
                # surface as the answer, with the platform's own instructions
                # quoted back inside it (measured on the language model
                # comparison, Qwen 4b, 2026-09-06). What is left is what the
                # model wrote BEFORE it began, which is usually nothing, and an
                # empty answer is what a run that never finished one is.
                head, _, tail = text.partition("<think>")
                thinking = tail.strip() or None
                text = head.strip()

            return {
                "content": text,
                "thinking": thinking,
                "tool_calls": None,
                "finish_reason": finish_reason,
            }
        except (ModelLoadRefused, ChildDied, ChildRequestError):
            # Passed through with the cause intact. None here would tell the
            # route "inference failed" for a child that said exactly why.
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("[LLM] Chat failed (%s): %s", model, e)
            return None

    def chat_stream(self, model: str, messages: list, images: Optional[list] = None,
                    temperature: float = 0.7, max_tokens: Optional[int] = None,
                    repetition_penalty: Optional[float] = None):
        """Chat completion handed out while it is still being written.

        Yields ("token", str) per content piece and ("finish", reason) last —
        "stop", "length" or "repetition". Without that last item a caller cannot
        tell a finished reading from a cut one, so a stream that ends without
        the child's terminator raises instead of inventing one.
        """
        child = self._acquire(model)
        try:
            payload: Dict[str, Any] = {
                "messages": self._build_messages_with_images(messages, images),
                "temperature": temperature,
                "stream": True,
                # Explicit: llama-cpp-python defaulted to 1.0 and this build's
                # own documentation disagrees with itself about the server
                # default. Parity of the sampler comes before everything else.
                "repeat_penalty": (1.0 if repetition_penalty is None
                                   else float(repetition_penalty)),
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if images:
                # No prefix reuse on the image path at all. Reusing a cached
                # prefix across two readings is precisely the shape the damaged
                # second reading had, and a reading is worth more than the
                # prefill it saves.
                payload["cache_prompt"] = False

            yield from self._stream(child, "/v1/chat/completions", payload, chat=True)
        finally:
            self._supervisor.release(child)

    def generate(self, model: str, prompt: str,
                 temperature: float = 0.7, max_tokens: Optional[int] = None,
                 repetition_penalty: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Raw text completion."""
        child = self._acquire(model)
        try:
            payload: Dict[str, Any] = {
                "prompt": prompt,
                "temperature": temperature,
                "stream": True,
                "repeat_penalty": (1.0 if repetition_penalty is None
                                   else float(repetition_penalty)),
            }
            if max_tokens is not None:
                payload["n_predict"] = max_tokens

            pieces: List[str] = []
            finish_reason = "stop"
            for kind, value in self._stream(child, "/completion", payload, chat=False):
                if kind == "token":
                    pieces.append(value)
                else:
                    finish_reason = value or "stop"
            return {
                "response": "".join(pieces).strip(),
                "thinking": None,
                "finish_reason": finish_reason,
            }
        except (ModelLoadRefused, ChildDied, ChildRequestError):
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("[LLM] Generate failed (%s): %s", model, e)
            return None
        finally:
            self._supervisor.release(child)

    # ------------------------------------------------------------- the stream

    # =========================================================================
    # Classification
    # =========================================================================

    #: The system line the classifier was trained with, verbatim from its model
    #: card. It is fixed: the policy travels in the user message, not here.
    CLASSIFIER_SYSTEM = (
        "Judge whether the Document meets the requirements based on the Query "
        'and the Instruction provided. Note that the answer can only be "yes" '
        'or "no".'
    )

    @staticmethod
    def _yes_no_side(token: str) -> Optional[str]:
        """Which side of the answer this token is, or None for anything else.

        The tokenizer writes the word with a leading word-boundary mark and in
        whatever case the sampler reached it in. Only the word itself decides;
        a token that merely begins with those letters ("nonsense") is not an
        answer and is left out.
        """
        word = token.strip().lstrip("\u2581").strip().lower()
        if word == "yes":
            return "yes"
        if word == "no":
            return "no"
        return None

    def classify(self, model: str, instruct: str, query: str, document: str,
                 images: Optional[list] = None) -> Optional[float]:
        """How strongly this model answers yes to `query` about `document`.

        Returns a probability between 0 and 1, or None where no answer could be
        read. None is not a low score: the caller blocks on it, because a check
        that produced no answer checked nothing (the oldest of the five failure
        patterns of this chain -- a verdict that stays out becomes a release).

        The answer is one token. The score is the softmax over the yes and no
        logprobs at that one position, which is what makes a threshold possible
        at all; reading the word alone would throw away everything between a
        model that is sure and one that is not. No output cap is set: the model
        stops itself after the word, and a cap here would be a silent limit on
        a path where silence is the failure.
        """
        # The alias has to be a model that can answer this protocol at all.
        # Without this the wrong model behind SAFETY_MODEL was silent: a guard
        # trained to write "safe"/"unsafe" produced a well-formed score over
        # two tokens it never meant to emit, with HTTP 200, and no layer above
        # could tell it from a real verdict. The live setting still names that
        # guard, so this is the check that turns a mis-set role into a named
        # refusal instead of a number.
        config = MODEL_CONFIGS.get(MODEL_ALIASES.get(model, model)) or {}
        if not config.get("classifier"):
            raise ModelLoadRefused(
                f"model {model} is not a safety classifier: it cannot answer a "
                f"policy with yes or no, and any score read off it would be "
                f"noise. Set SAFETY_MODEL to a model declared classifier: True."
            )

        child = self._acquire(model)
        try:
            user = (f"<Instruct>: {instruct}\n\n"
                    f"<Query>: {query}\n\n"
                    f"<Document>: {document}")
            messages = [
                {"role": "system", "content": self.CLASSIFIER_SYSTEM},
                {"role": "user", "content": user},
            ]
            payload: Dict[str, Any] = {
                "messages": self._build_messages_with_images(messages, images),
                "temperature": 0.0,
                "stream": False,
                "repeat_penalty": 1.0,
                "logprobs": True,
                "top_logprobs": 20,
            }
            if images:
                # Same reason as the reading path: a cached prefix carried
                # across two pictures produced the damaged second reading.
                payload["cache_prompt"] = False

            data = self._post_json(child, "/v1/chat/completions", payload)
            return self._score_from_logprobs(child.alias, data)
        finally:
            self._supervisor.release(child)

    def _post_json(self, child: SupervisedChild, path: str,
                   payload: Dict[str, Any]) -> Dict[str, Any]:
        """One blocking request to the child, answered as parsed JSON.

        The streaming path cannot serve this: the logprobs of the first
        position arrive in the response body, not as an event. Everything else
        is kept the same -- the connection is registered with the child so a
        dying child ends the wait, and there is a connect timeout and no read
        timeout, because a read timeout would report a slow model as a broken
        one.
        """
        import requests

        session = requests.Session()
        response = None

        def _close_from_outside() -> None:
            nonlocal response
            with contextlib.suppress(Exception):
                if response is not None:
                    response.close()
            with contextlib.suppress(Exception):
                session.close()

        request = child.begin_request(_close_from_outside)
        try:
            try:
                response = session.post(child.base_url() + path, json=payload,
                                        timeout=(5.0, None))
            except requests.RequestException as e:
                raise self._died(child, f"{child.alias}: the request to its server "
                                        f"failed ({e})", request=request) from e
            if response.status_code != 200:
                status, message = self._read_error_body(response)
                raise ChildRequestError(child.alias, status, message)
            try:
                return response.json()
            except ValueError as e:
                # A 200 whose body is not JSON. Without this the decode error
                # went past the route's handler and reached the caller as an
                # HTML 500 with no [LLM] line naming the cause -- fail-closed,
                # but blind.
                raise self._died(child, f"{child.alias}: its server answered 200 "
                                        f"with a body that is not JSON ({e})",
                                 request=request) from e
        finally:
            child.end_request(request)
            with contextlib.suppress(Exception):
                if response is not None:
                    response.close()
            with contextlib.suppress(Exception):
                session.close()

    def _score_from_logprobs(self, alias: str,
                             data: Dict[str, Any]) -> Optional[float]:
        """Read the yes/no probability off the first generated position.

        Two things have to hold before there is a number at all, and an
        adversarial review of 2026-09-23 found the first one missing:

        * **The model has to have ANSWERED.** The card's contract is that it
          emits one token, `yes` or `no`. The first version of this method only
          looked for those two words among the twenty likeliest tokens and
          renormalised whatever it found, without ever asking what the model
          actually wrote. A model that wrote something else entirely -- the
          wrong model behind the alias, a refusal, a preamble -- still had
          `yes` and `no` somewhere in that tail with a millionth of the mass
          each, and their ratio is then noise. Noise below 0.5 is a RELEASE.
          The emitted token is read first now, and anything but an answer is no
          verdict.
        * **Both sides have to be there**, or there is no two-way softmax to
          compute and this method does not invent one.

        The mass of each side is SUMMED over the spellings the vocabulary
        offers (leading space, capitalisation) rather than taken at its
        maximum: a side whose mass splits across two spellings would otherwise
        be counted at the larger half alone, and near the threshold that moves
        verdicts.

        Every way this can fail to produce a number returns None, and the log
        line says which one it was: the caller turns None into a block, and an
        operator reading "the answer was neither yes nor no" needs to see that
        rather than a score nobody can account for.
        """
        import math

        try:
            choice = data["choices"][0]
            content = (choice.get("logprobs") or {}).get("content") or []
        except (KeyError, IndexError, TypeError):
            logger.error("[LLM] %s: the classification answer has no choices", alias)
            return None
        if not content:
            logger.error("[LLM] %s: the classification answer carries no logprobs "
                         "-- the server was asked for them and sent none", alias)
            return None

        first = content[0]
        said = (choice.get("message") or {}).get("content", "")
        answered = self._yes_no_side(str(first.get("token", "")))
        if answered is None:
            logger.error("[LLM] %s: the first token it generated is %r, which is "
                         "neither yes nor no -- no verdict (it wrote %.60r)",
                         alias, first.get("token"), said)
            return None

        mass: Dict[str, float] = {"yes": 0.0, "no": 0.0}
        for entry in first.get("top_logprobs") or []:
            side = self._yes_no_side(str(entry.get("token", "")))
            if side is None:
                continue
            value = entry.get("logprob")
            if value is None:
                continue
            try:
                mass[side] += math.exp(float(value))
            except (TypeError, ValueError, OverflowError):
                continue

        if mass["yes"] <= 0.0 or mass["no"] <= 0.0:
            logger.error("[LLM] %s: it answered %r, but the other side carries no "
                         "mass among the twenty likeliest first tokens -- no "
                         "verdict", alias, answered)
            return None

        return mass["yes"] / (mass["yes"] + mass["no"])
    def _stream(self, child: SupervisedChild, path: str, payload: Dict[str, Any],
                chat: bool):
        """POST and read the child's event stream. Yields tokens, then the finish.

        The connection is the cancel button. A repetition stop closes the
        response AND the session, which the child sees as a disconnect and
        answers by cancelling its slot; a generator the consumer abandons ends
        the same way through the finally.
        """
        import requests

        url = child.base_url() + path
        session = requests.Session()
        response = None
        guard = RepetitionGuard()
        finish_reason: Optional[str] = None
        said_done = False

        # Registered before the POST, so a request that is ended while it is
        # still waiting for headers is reachable too. The closer reads the
        # response out of the enclosing scope: it does not exist yet, and by the
        # time anybody calls this it usually does.
        def _close_from_outside() -> None:
            # Shut the socket down; do NOT close from here. Closing a streaming
            # response from another thread waits on the buffer lock the reader
            # holds (see unblock_stream), so the closer would hang instead of
            # the stream ending — and this closer runs on the reaper thread,
            # which every child-level bound depends on. The reader lets go the
            # moment the socket is shut, and the `finally` below closes both.
            if response is not None:
                unblock_stream(response)
            # Kept from before the fix, and it is the weaker half: a connection
            # that is checked out of the pool — which is every connection this
            # closer cares about — is not in the pool to be closed. It reaches
            # the idle ones, and it costs nothing.
            with contextlib.suppress(Exception):
                session.close()

        request = child.begin_request(_close_from_outside)
        try:
            try:
                response = session.post(
                    url, json=payload, stream=True,
                    headers={"Accept": "text/event-stream"},
                    # Connect timeout only. A reading has no deadline here: the
                    # ceiling is the model's own context, and a read timeout
                    # would cut a long answer in half and call it an error.
                    timeout=(5.0, None))
            except requests.RequestException as e:
                raise self._died(child, f"{child.alias}: the request to its server "
                                        f"failed ({e})", request=request) from e

            if response.status_code != 200:
                status, message = self._read_error_body(response)
                raise ChildRequestError(child.alias, status, message)

            events = self._events(child, response, request)
            for event, data in events:
                if event == "error":
                    status, message = self._error_from_payload(data)
                    raise ChildRequestError(child.alias, status, message)
                if data == "[DONE]":
                    said_done = True
                    break
                try:
                    chunk = json.loads(data)
                except ValueError:
                    logger.warning("[LLM] %s sent a chunk that is not JSON: %.200s",
                                   child.alias, data)
                    continue
                if isinstance(chunk, dict) and chunk.get("error"):
                    status, message = self._error_from_payload(data)
                    raise ChildRequestError(child.alias, status, message)

                piece, chunk_finish = (self._read_chat_chunk(chunk) if chat
                                       else self._read_completion_chunk(chunk))
                if piece:
                    yield ("token", piece)
                if chunk_finish:
                    finish_reason = chunk_finish
                if piece and guard.feed(piece):
                    finish_reason = "repetition"
                    logger.info("[LLM] %s repeated %s and was stopped",
                                child.alias, guard.describe())
                    break
                if finish_reason:
                    self._read_to_the_end(child, events)
                    break

            if finish_reason is None:
                raise self._ended_without_terminator(child, said_done, request)
            yield ("finish", finish_reason)
        finally:
            child.end_request(request)
            # Both, and in this order: closing only the response leaves the
            # connection in the pool, and the child goes on generating into a
            # socket nobody reads.
            if response is not None:
                with contextlib.suppress(Exception):
                    response.close()
            with contextlib.suppress(Exception):
                session.close()

    @staticmethod
    def _read_to_the_end(child: SupervisedChild, events: Iterator[Tuple[str, str]]) -> None:
        """After the finish chunk, read on until [DONE] or the body ends.

        Closing the connection the moment the answer is complete is a client
        disconnect as far as the child is concerned: it logs a cancelled slot
        for every ordinary request, and that line is the one the platform reads
        to tell a repetition stop from a normal end. Two frames at most stand
        between the finish chunk and [DONE]; the bound is there so that a child
        which never stops writing cannot hold the caller here.

        Nothing that happens in here can fail the request. The answer is already
        complete and its finish reason recorded; a child that crashes in the
        moment between its last chunk and its [DONE] has given the caller
        everything it asked for, and turning that into a 500 would throw away a
        finished reading over a courtesy.
        """
        try:
            for index, (_, data) in enumerate(events):
                if data == "[DONE]":
                    return
                if index >= 64:
                    logger.warning("[LLM] %s kept writing after it said the answer "
                                   "was finished — dropping the connection",
                                   child.alias)
                    return
        except Exception as e:  # noqa: BLE001
            logger.info("[LLM] %s ended the connection right after the answer "
                        "(%s) — the answer itself is complete",
                        child.alias, type(e).__name__)

    def _events(self, child: SupervisedChild, response: Any,
                request: Optional[InFlightRequest] = None):
        """The child's events, with a broken connection named for what it is.

        A child that segfaults mid-answer leaves the HTTP body unfinished, and
        the library reports that as a transport error. Passed through as one it
        would reach the route as "inference failed" — the sentence that says
        nothing. It is the child dying, and it says so, with the exit code.
        """
        import requests

        stamp = request.note_progress if request is not None else child.note_progress
        iterator = iter_sse_events(response, on_activity=stamp)
        while True:
            try:
                yield next(iterator)
            except StopIteration:
                return
            except (requests.RequestException, OSError, ValueError,
                    AttributeError) as e:
                # The last two are what a stream closed under its own reader
                # raises: the library hands back a raw connection that is gone,
                # and reading it is an AttributeError or an I/O-on-closed-file
                # ValueError rather than anything socket-shaped. Reaching the
                # caller unconverted they would arrive as "inference failed",
                # which is the one thing this whole path exists to prevent.
                raise self._died(
                    child,
                    f"{child.alias}'s server broke off the answer ({type(e).__name__})",
                    request=request,
                ) from e

    @staticmethod
    def _read_chat_chunk(chunk: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """(content, finish_reason) of one /v1/chat/completions chunk.

        `choices` is empty on the chunk that carries only timings — reading
        [0] there is an IndexError in the middle of a finished answer.
        `tool_calls` maps to "stop": the model came to its own end.

        A finish_reason this build does not use today maps to "length", never to
        "stop". "stop" is a claim — the model finished what it had to say — and
        the safety chain reads that field: a reading that ended for a reason
        nobody here knows must arrive as an answer that may be incomplete.
        """
        choices = chunk.get("choices") or []
        if not choices:
            return None, None
        choice = choices[0] or {}
        piece = (choice.get("delta") or {}).get("content")
        raw_finish = choice.get("finish_reason")
        if not raw_finish:
            return piece, None
        if raw_finish == "length":
            return piece, "length"
        if raw_finish in ("stop", "tool_calls"):
            return piece, "stop"
        logger.warning("[LLM] Unknown finish_reason %r — reported as 'length', "
                       "because an end nobody here knows is an answer that may "
                       "be cut", raw_finish)
        return piece, "length"

    @staticmethod
    def _read_completion_chunk(chunk: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """(content, finish_reason) of one /completion chunk.

        The terminator here is `"stop": true`; `stop_type` says which kind of
        end it was. `truncated` means the prompt did not fit and the beginning
        was dropped — an answer to something other than what was asked, which
        the caller has to be able to see, so it is reported as "length".
        """
        piece = chunk.get("content")
        if not chunk.get("stop"):
            return piece, None
        stop_type = chunk.get("stop_type") or ""
        if chunk.get("truncated") or stop_type == "limit":
            return piece, "length"
        if stop_type in ("eos", "word"):
            return piece, "stop"
        logger.warning("[LLM] Unknown stop_type %r — reported as 'length', because "
                       "an end nobody here knows is an answer that may be cut",
                       stop_type)
        return piece, "length"

    def _ended_without_terminator(self, child: SupervisedChild,
                                  said_done: bool = False,
                                  request: Optional[InFlightRequest] = None) -> ChildDied:
        """The stream stopped and never said how the answer finished.

        Three different events wear this shape and the message says which. A
        child that crashed carries its exit code. A child that is still up
        either closed the connection — the slot was cancelled, a proxy cut in —
        or wrote its [DONE] and skipped the finish chunk, which is a different
        fault entirely: the answer arrived complete as far as the child was
        concerned, and the field the safety chain reads is simply missing.
        """
        if request is not None and request.ended_reason:
            # Closed from outside while it was being read: the body simply
            # stops, and it stops because a bound was reached — not because
            # anything about this child is wrong.
            return ChildDied(
                child.alias, None, child.log_tail(),
                f"{child.alias}: {request.ended_reason}",
                ended="this service ended this request; the child is still serving")
        code = child.exit_code_after(0.5)
        ended_by_us = (f"; this service had ended it: {child.end_reason}"
                       if child.end_reason else "")
        if code is not None:
            self._retire(child, f"its process ended mid-answer (exit {code})")
            return ChildDied(
                child.alias, code, child.log_tail(),
                f"{child.alias}'s server ended the stream without saying how the "
                f"answer finished, and its process is gone{ended_by_us}")
        # "Its process is still up" is true wherever we get past the branch
        # above, and it is the wrong half of the diagnosis as soon as THIS
        # service is the one that ended the child: a bound was reached, and
        # that is the only part anybody can act on.
        if said_done:
            return ChildDied(
                child.alias, None, child.log_tail(),
                f"{child.alias}'s server marked the answer complete ([DONE]) "
                f"without ever sending a finish reason, so how it ended is "
                f"unknown and it is treated as cut{ended_by_us}",
                ended=("this service ended it while the answer was in flight"
                       if child.end_reason else
                       "its process is still up — the stream was complete, the "
                       "answer's own ending was left out"))
        return ChildDied(
            child.alias, None, child.log_tail(),
            f"{child.alias}'s server ended the stream without saying how the "
            f"answer finished{ended_by_us}",
            ended=("this service ended it while the answer was in flight"
                   if child.end_reason else
                   "its process is still up — the connection ended, the answer "
                   "stayed unfinished"))

    def _died(self, child: SupervisedChild, detail: str,
              request: Optional[InFlightRequest] = None) -> ChildDied:
        if request is not None and request.ended_reason:
            # This service closed THIS stream, and the child is untouched and
            # still serving. Nothing below applies: there is no exit code to
            # wait for and nothing to retire, and the one thing worth saying is
            # which bound was reached.
            return ChildDied(
                child.alias, None, child.log_tail(),
                f"{child.alias}: {request.ended_reason}",
                ended="this service ended this request; the child is still serving")
        # exit_code_after, not poll: a child that crashed mid-answer closes its
        # socket a moment before the kernel reports it gone, and "still running"
        # is the wrong half of the diagnosis to hand somebody.
        code = child.exit_code_after(0.5)
        if child.end_reason:
            # The connection broke because this service ended the child. Without
            # this the caller reads a transport error and never learns that a
            # bound was reached, which is the only part worth acting on.
            detail = f"{detail}; this service had ended it: {child.end_reason}"
        if code is not None:
            self._retire(child, f"its process died during a request (exit {code})")
        return ChildDied(child.alias, code, child.log_tail(), detail)

    def _retire(self, child: SupervisedChild, reason: str) -> None:
        """Take a child whose process is gone out of the registry, now.

        THIS REQUEST STILL FAILS — a generation is never quietly run a second
        time. What this changes is the next one: without it the dead child stays
        registered until the reaper's next pass, and every request that arrives
        in between is handed a port nothing listens on. A crash cost one reading
        and then all of them for several seconds; it should cost one.

        A child that is still running keeps its place: a connection that broke
        under a healthy process is a lost answer, not a lost model.
        """
        try:
            self._supervisor.retire(child, reason)
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] Could not take %s out of the registry: %s",
                           child.alias, e)

    @staticmethod
    def _error_from_payload(data: str) -> Tuple[int, str]:
        try:
            payload = json.loads(data)
        except ValueError:
            return 500, data[:400]
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            code = error.get("code")
            status = code if isinstance(code, int) and 100 <= code < 600 else 500
            return status, str(error.get("message") or error.get("type") or error)[:400]
        if isinstance(error, str):
            return 500, error[:400]
        return 500, data[:400]

    @staticmethod
    def _read_error_body(response: Any) -> Tuple[int, str]:
        try:
            body = response.text
        except Exception:  # noqa: BLE001
            body = ""
        _, message = LLMBackend._error_from_payload(body) if body else (0, "")
        return response.status_code, (message or f"HTTP {response.status_code}")

    def _build_messages_with_images(self, messages: list,
                                    images: Optional[list] = None) -> list:
        """Convert images to OpenAI multimodal content parts."""
        if not images:
            return messages

        result = []
        images_injected = False
        for msg in messages:
            m = dict(msg)
            if not images_injected and m.get("role") == "user":
                content_parts = [{"type": "text", "text": m.get("content", "")}]
                for img_b64 in images:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": data_url_for(img_b64)},
                    })
                m["content"] = content_parts
                images_injected = True
            result.append(m)
        return result

    # =========================================================================
    # Status
    # =========================================================================

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """What is resident, with the process behind it named.

        READY children only. A child that is still reading weights off disk, or
        one that is being killed, is not a model anybody can use — and this list
        is read as "what you can ask right now", by the model pickers and by the
        operator deciding what to unload.

        pid/port/state are additive: an operator who has to reach a wedged child
        — `/api/llm/unload` with force, or the journal lines under
        [LLM-CHILD <alias>] — needs to know which process it is.
        """
        return [
            {
                "id": child.alias,
                "vram_mb": child.vram_mb,
                "in_use": child.in_use,
                "last_used": child.last_used,
                "pid": child.pid,
                "port": child.port,
                "state": child.state.value,
            }
            for child in self._supervisor.snapshot()
            if child.state is ChildState.READY
        ]

    def get_available_models(self) -> List[str]:
        """The aliases whose files lie on disk.

        Availability is meant literally: this list feeds the model-role pickers,
        which carry no availability flag of their own, so a registered but
        undownloaded alias would arrive there as a selectable option that fails
        at load time.
        """
        def _on_disk(config: Dict[str, Any]) -> bool:
            if not os.path.exists(config["model_path"]):
                return False
            mmproj = config.get("mmproj_path")
            return os.path.exists(mmproj) if mmproj else True

        all_models = [alias for alias, config in MODEL_CONFIGS.items() if _on_disk(config)]
        all_models.extend(
            alias for alias, target in MODEL_ALIASES.items()
            if target in MODEL_CONFIGS and _on_disk(MODEL_CONFIGS[target])
        )
        return all_models

    def get_chat_models(self) -> List[Dict[str, Any]]:
        """Chat-capable models with availability, for Compare Hub."""
        return [
            {
                "id": alias,
                "display_name": config.get("display_name", alias),
                "available": os.path.exists(config["model_path"]),
                # What a load of this model costs THIS engine: the floor it
                # needs before --fit decides how much cache the card affords.
                "estimated_vram_mb": int(load_floor_mb(config)
                                        or config.get("estimated_vram_mb", 0)),
                "installable": bool(config.get("hf_repo_id")),
                "approx_download_mb": config.get("approx_download_mb", 0),
            }
            for alias, config in MODEL_CONFIGS.items()
            if config.get("chat_capable", False)
        ]

    def get_vlm_models(self) -> List[Dict[str, Any]]:
        """Image-reading models with availability, for Compare Hub."""
        return [
            {
                "id": alias,
                "display_name": config.get("display_name", alias),
                "available": (os.path.exists(config["model_path"])
                              and os.path.exists(config.get("mmproj_path", ""))),
                # What a load of this model costs THIS engine: the floor it
                # needs before --fit decides how much cache the card affords.
                "estimated_vram_mb": int(load_floor_mb(config)
                                        or config.get("estimated_vram_mb", 0)),
                "installable": bool(config.get("hf_repo_id")),
                "approx_download_mb": config.get("approx_download_mb", 0),
            }
            for alias, config in MODEL_CONFIGS.items()
            if config.get("vlm_capable", False)
        ]

    def is_available(self) -> bool:
        """True when the llama-server binary is there and can be run."""
        binary = self._supervisor.binary
        return os.path.isfile(binary) and os.access(binary, os.X_OK)

    def get_engine_info(self) -> Dict[str, Any]:
        """What answers /api/llm/health: the engine, its binary, its build.

        The build string comes from the cache and never from the binary: see
        probe_build. Before the probe has run it is absent rather than wrong.
        """
        return {
            "backend": "llama-server",
            "binary": self._supervisor.binary,
            "build": self._build_cache or None,
        }

    def probe_build(self) -> Optional[str]:
        """Ask the binary for its version. STARTUP ONLY, once per process.

        `llama-server --version` initialises CUDA on this build — it opens the
        device, takes a context and gives it back. Harmless at startup, and
        emphatically not something to do while a health request is being served
        and a model may be loading on the same card.
        """
        return self._binary_build()

    def _binary_build(self) -> Optional[str]:
        """The build string from `llama-server --version`, asked once per process."""
        if self._build_cache is not None:
            return self._build_cache or None
        if not self.is_available():
            self._build_cache = ""
            return None
        try:
            result = subprocess.run(
                [self._supervisor.binary, "--version"],
                capture_output=True, timeout=30, check=False)
            text = (result.stdout or b"").decode("utf-8", "replace") + \
                   (result.stderr or b"").decode("utf-8", "replace")
            for line in text.splitlines():
                if line.strip().startswith("version:"):
                    self._build_cache = line.strip()
                    return self._build_cache
            self._build_cache = text.strip().splitlines()[-1] if text.strip() else ""
        except Exception as e:  # noqa: BLE001
            logger.warning("[LLM] Could not read the llama-server version: %s", e)
            self._build_cache = ""
        return self._build_cache or None


def _confirm_owned(child: SupervisedChild) -> Callable[[], bool]:
    """The callback the coordinator asks before treating a PID as ours."""
    from services.llm_child import owns

    def _confirm() -> bool:
        return child.pid is not None and owns(child.pid, child.starttime, child.alias)

    return _confirm


def _coordinator_invalidate_nvml() -> None:
    """Drop the coordinator's cached enumeration — the card has just changed."""
    try:
        from services.vram_coordinator import get_vram_coordinator
        get_vram_coordinator().invalidate_nvml_cache()
    except Exception:  # noqa: BLE001
        pass


def _coordinator_pid_mb(pid: int, max_age_s: Optional[float] = None) -> Optional[float]:
    """One PID's GPU memory per NVML, or None when it holds none.

    `max_age_s` travels through to the coordinator: the supervisor polls this
    several times a second while it waits, and asks for a fresh enumeration only
    where a figure a second old would answer the wrong question.
    """
    try:
        from services.vram_coordinator import get_vram_coordinator
        coordinator = get_vram_coordinator()
        if max_age_s is None:
            return coordinator.get_process_vram_mb(pid)
        return coordinator.get_process_vram_mb(pid, max_age_s=max_age_s)
    except Exception:  # noqa: BLE001
        return None


# =============================================================================
# Singleton
# =============================================================================

_backend: Optional[Any] = None
_backend_lock = threading.Lock()


def get_llm_backend():
    """The one LLM backend of this process, per LLM_ENGINE.

    Exactly one engine is ever constructed. The older in-process module is not
    even asked for a backend unless LLM_ENGINE says "inprocess": two of them
    would be two claims on the same card, one of them invisible to the other.
    """
    global _backend
    if _backend is not None:
        return _backend
    with _backend_lock:
        if _backend is not None:
            return _backend
        try:
            from config import LLM_ENGINE
        except Exception:  # noqa: BLE001
            LLM_ENGINE = "child"
        engine = str(LLM_ENGINE).strip().lower()
        if engine not in ("child", "inprocess"):
            # Refused rather than fallen back on: a misspelling that quietly
            # selects the default hides which engine is running, and the two
            # differ in whether a crashing model takes the service with it.
            raise RuntimeError(
                f"LLM_ENGINE={LLM_ENGINE!r} names no engine. The two spellings "
                f"are 'child' (one supervised llama-server per model, the "
                f"default) and 'inprocess' (llama-cpp-python inside this "
                f"service).")
        logger.info("[LLM] Engine: %s", engine)
        if engine == "inprocess":
            from services.llm_backend import get_llm_backend as _in_process_backend
            logger.warning("[LLM] LLM_ENGINE=inprocess — running llama-cpp-python "
                           "in this process; a model crash takes the service with it")
            _backend = _in_process_backend()
        else:
            _backend = LLMBackend()
        return _backend


def reset_llm_backend() -> None:
    """Drop the singleton (tests, and the engine switch in a manual run)."""
    global _backend
    with _backend_lock:
        _backend = None
