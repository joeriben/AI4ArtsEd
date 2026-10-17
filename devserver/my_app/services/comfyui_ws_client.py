"""
ComfyUI WebSocket Client — Direct connection to ComfyUI

Provides real-time progress tracking, denoising previews, and clean media download
via ComfyUI's HTTP API (no filesystem access).

Architecture:
    DevServer --WebSocket--> ComfyUI (port 17804)
    - JSON events: progress, node completion, errors
    - Binary messages: denoising preview images
    - HTTP: /prompt (submit), /view (download media), /history (outputs)
"""

import asyncio
import aiohttp
import functools
import json
import logging
import re
import struct
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from my_app.services.streaming_response import note_dispatch
from my_app.utils.response_reason import reason_line

logger = logging.getLogger(__name__)


# The text fields of SD 3.5's encoders, per node class.
SD35_TEXT_FIELDS = {
    # The platform's own encode. ComfyUI's `CLIPTextEncodeSD3` stands here too:
    # a graph could carry it, and a prompt going through it would keep the weight
    # syntax the Diffusers path encoded as characters.
    "AI4ArtsEdSD3TextEncode": ("clip_l", "clip_g", "t5xxl"),
    "CLIPTextEncodeSD3": ("clip_l", "clip_g", "t5xxl"),
    "AI4ArtsEdSD3Encode": ("text",),
    # The capture node of Attention Cartography tokenizes the prompt for its
    # columns; it has to see the prompt the encoders saw.
    "AI4ArtsEdAttentionCapture": ("text",),
}

_BRACKET = re.compile(r"([()])")


def as_written(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Give SD 3.5's text encoders the prompt as it was written.

    ComfyUI's tokenizer reads something out of a prompt that no author of one
    put there: `(a phrase)` is a weight of 1.1 and the brackets themselves
    disappear, `(a phrase:1.5)` is a weight of 1.5 (comfy/sd1_clip.py
    token_weights). Diffusers encodes the characters, so every SD 3.5 picture
    this platform made before the move to ComfyUI was conditioned on the
    brackets. Measured on this machine: "a house (built 1920) in a forest" and
    "a house built 1920 in a forest" tokenize to the same ids, the first with a
    weight of 1.1 on the middle words. Backslashes put the characters back;
    escape_important reads `\\(` as a literal bracket.

    SD 3.5's nodes only. SDXL has been generated on ComfyUI through
    `CLIPTextEncode` from the beginning, so there the weight syntax is what the
    platform has always done, and taking it away here would be the same silent
    move in the other direction.

    Here rather than in the chunks: this is the door every generation goes
    through, and what the platform stores, shows and records stays the prompt
    the author wrote.

    One thing this cannot reach: a prompt carrying ` embedding:` sends ComfyUI
    looking for a file of that name, and a miss drops the rest of the line.
    The tokenizer has no escape for it.
    """
    out = dict(workflow)
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        fields = SD35_TEXT_FIELDS.get(node.get("class_type"))
        if not fields:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        written = {
            f: _BRACKET.sub(r"\\\1", inputs[f])
            for f in fields
            if isinstance(inputs.get(f), str) and ("(" in inputs[f] or ")" in inputs[f])
        }
        if written:
            out[node_id] = {**node, "inputs": {**inputs, **written}}
    return out


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

# What a node announces in the run's history, and what the file leaves this
# client as. ComfyUI's own nodes announce under the first keys (SaveImage,
# SaveAudio, the video savers); the platform's nodes announce under keys of
# their own - AI4ArtsEdKeepLatent a latent, AI4ArtsEdAttentionMaps the readout
# of Attention Cartography - so that nothing looking for pictures picks them
# up. Order per node: pictures first, as the callers that read the first file
# of a run have always found it.
ANNOUNCED_FILES = (
    ("images", "image"),
    ("audio", "audio"),
    ("genaudio", "audio"),
    ("latents", "latent"),
    ("ai4artsed_attention", "attention"),
    ("video", "video"),
    ("genvideo", "video"),
    ("gifs", "video"),
    # A mesh, the way ComfyUI's own SaveGLB announces one; the platform's
    # Hunyuan3D node announces its GLB under the same key.
    ("3d", "mesh"),
)


@dataclass
class MediaFile:
    """A single media file downloaded from ComfyUI."""
    data: bytes
    filename: str
    media_type: str  # the second column of ANNOUNCED_FILES
    subfolder: str = ""
    node_id: str = ""
    # What the producing node said about the file, verbatim. Only a latent
    # carries one today: the space it was written in, its shape and its dtype,
    # which the platform records beside it and decodes the set's mean from.
    meta: dict = field(default_factory=dict)


@dataclass
class ProgressEvent:
    """Progress update from ComfyUI WebSocket."""
    overall_percent: float  # 0.0 – 1.0
    current_percent: float  # step progress within current node
    nodes_done: int
    total_nodes: int
    current_node: Optional[str] = None
    preview_base64: Optional[str] = None  # denoising preview (JPEG base64)


# The step the card is on, for the readers that ask by polling:
# settings_routes /generation-progress, read by composables/useGenerationSteps.ts
# and useAnimationProgress.ts. One card, one prompt at a time, so the last
# progress message heard for any tracked prompt is the state of the card, and
# the pair is kept after the switch-off, which the step reader takes as the
# finished run's count. Until stage 4 of the move to ComfyUI the GPU service
# kept this pair for its Diffusers runs and the DevServer relayed it; a run on
# ComfyUI left the readers at `active: False`.
_step_lock = threading.Lock()
_step = {"step": 0, "total_steps": 0, "active": False, "prompt_id": None}


def begin_step(prompt_id: str) -> None:
    """The run under `prompt_id` is submitted: the readers see it from here on,
    at step 0 of a count still unknown, so a sampling that finishes between
    two of their polls (four steps of a turbo model) is seen as well. The GPU
    service's reader did the same at the start of a Diffusers run."""
    with _step_lock:
        _step.update(step=0, total_steps=0, active=True, prompt_id=prompt_id)


def note_step(prompt_id: str, step: int, total_steps: int) -> None:
    with _step_lock:
        _step.update(step=int(step), total_steps=int(total_steps), active=True,
                     prompt_id=prompt_id)


def end_step(prompt_id: str) -> None:
    """The run under `prompt_id` is over, one way or the other. Another
    prompt's steps, heard since, stay as they are."""
    with _step_lock:
        if _step["prompt_id"] == prompt_id:
            _step["active"] = False


def step_now() -> dict:
    """{step, total_steps, active}: the pair the GPU service's progress
    reading answered for a Diffusers run, kept here for ComfyUI's."""
    with _step_lock:
        return {k: _step[k] for k in ("step", "total_steps", "active")}


@dataclass
class GenerationResult:
    """Result of a workflow submission and tracking."""
    prompt_id: str
    media_files: list  # List[MediaFile]
    execution_time: float
    outputs_metadata: dict = field(default_factory=dict)  # Raw ComfyUI outputs dict


@dataclass
class SubmittedEvent:
    """The first thing on_progress hears: ComfyUI has the prompt, under
    this id. What a caller cancels by (schema_pipeline_routes
    _catch_up_submitted, llm_client.chat_stream) and what the LLM client
    deletes from the history by.

    A module-level class on purpose. Until 2026-09-12 this was a dataclass
    declared inside submit_and_track with `prompt_id: str = prompt_id`: a
    class body resolves a name it assigns in its own namespace and the
    module's, never in the enclosing function, so that line raised
    NameError, the `except Exception: pass` around it swallowed it, and
    no caller ever received a prompt id (since f32e5e7c).
    """
    prompt_id: str
    event_type: str = "submitted"
    overall_percent: float = 0.0
    preview_base64: str = ""
    current_node: str = ""


# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------

# Nodes that put weights on the card, and the input that names the file.
# llm_name / ai4artsed_local_llm: the platform's own node for a local language
# model (comfyui_nodes/ai4artsed_comfyui), which llm_client.py queues.
_CHECKPOINT_FIELDS = (
    "ckpt_name", "unet_name", "model_name", "vae_name",
    "clip_name", "lora_name", "llm_name",
)
_LOADER_HINTS = ("checkpointloader", "unetloader", "diffusionmodelloader",
                 "imageonlycheckpointloader", "ai4artsed_local_llm")


def _checkpoint_of(workflow) -> str:
    """The heaviest thing this workflow loads, as its name.

    A loaded checkpoint stays on the card until another needs its room, so
    this name is what decides whether the next run needs a swap. Loader
    nodes are preferred; failing
    that, any node that names a model file. Deterministic: sorted by node id,
    so the same workflow always yields the same name.
    """
    if not isinstance(workflow, dict):
        return "comfyui"
    best = None
    for node_id in sorted(workflow.keys(), key=str):
        node = workflow.get(node_id)
        if not isinstance(node, dict):
            continue
        cls = str(node.get("class_type", "")).lower()
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for f in _CHECKPOINT_FIELDS:
            v = inputs.get(f)
            if isinstance(v, str) and v:
                if f == "llm_name":
                    v = _local_model_id(v)
                elif f == "model_name" and cls == "ai4artsed_media_reading":
                    v = _reader_id(v)
                elif f == "model_name" and cls.startswith("ai4artsed_"):
                    v = _local_media_id(v)
                if any(h in cls for h in _LOADER_HINTS):
                    return v
                if best is None:
                    best = v
    return best or "comfyui"


def _local_model_id(dir_name: str) -> str:
    """The platform id of a local language model, from the folder the node
    is handed: what the model-place bar shows and what the gate keys the
    run's statistics by, the same name as the dispatch announced. A folder
    the table does not know (a model copied in by hand) keeps its name."""
    from my_app.services import local_llm_weights
    alias = local_llm_weights.alias_of_dir(dir_name)
    return f"{local_llm_weights.LOCAL_PREFIX}{alias}" if alias else dir_name


def _local_media_id(dir_name: str) -> str:
    """The platform alias of a media model of the platform's own package
    (config/local_media_weights.json), from the folder its node is handed
    under `model_name`: the name the route announced for the bar, so that
    this dispatch names the same model. A folder the table does not know
    keeps its name."""
    from my_app.services import local_media_weights
    return local_media_weights.alias_of_folder(dir_name) or dir_name


def _reader_id(dir_name: str) -> str:
    """The platform id of what the media reader loads. Its node lists the
    readers under models/media_reading AND the language models under
    models/llm in one `model_name` list (image and video are read by a
    language model), so the folder is resolved against the language-model
    table first and the media table second: the same model, loaded by
    ai4artsed_local_llm, is keyed `local/<alias>`, and one model has one
    key in the gate (finding S-035 of the code review of 2026-10-10). A folder neither table knows keeps its name."""
    from my_app.services import local_llm_weights
    alias = local_llm_weights.alias_of_dir(dir_name)
    if alias:
        return f"{local_llm_weights.LOCAL_PREFIX}{alias}"
    return _local_media_id(dir_name)


def _holds_node(entry: dict, class_type: str) -> bool:
    """Whether a history entry's workflow holds a node of this class. The
    entry's "prompt" is the queue item, [number, prompt_id, workflow,
    extra_data, outputs_to_execute]."""
    item = entry.get("prompt") if isinstance(entry, dict) else None
    workflow = item[2] if isinstance(item, list) and len(item) > 2 else None
    if not isinstance(workflow, dict):
        return False
    return any(isinstance(node, dict) and node.get("class_type") == class_type
               for node in workflow.values())


def _with_gpu_lease(fn):
    """
    Hold a gpu_service admission lease for the length of a ComfyUI generation.

    ComfyUI runs in its own process, driven from here, and knows nothing about
    what the gpu_service is doing with the same card. The lease is what makes
    "one heavy operation at a time" hold across both processes.
    """
    @functools.wraps(fn)
    async def _wrapper(self, *args, **kwargs):
        from my_app.services.gpu_lease_client import gpu_lease
        from my_app.services.generation_abort import (current_run_aborted, CURRENT_RUN_ID,
                                                       CURRENT_OUTPUT_CONFIG)
        # Cancelled before we even queue: don't take a place in line.
        if current_run_aborted():
            raise RuntimeError("generation cancelled before queueing")
        # Which checkpoint this workflow will load. Without it every ComfyUI
        # run is called "comfyui", and the gate cannot tell a video from an
        # image — it could neither group runs that share a model nor say how
        # long anybody will wait.
        workflow = args[0] if args else kwargs.get("workflow")
        model_id = _checkpoint_of(workflow)
        # Which config this is, alongside which checkpoint it loads. The
        # checkpoint decides what has to be on the card; the config decides how
        # long it will be there, and the two are not the same question.
        async with gpu_lease("comfyui", model_id, 0, label=CURRENT_RUN_ID.get() or "",
                             workload=CURRENT_OUTPUT_CONFIG.get() or ""):
            # Cancelled while waiting in line: the lease was just granted, and
            # this is the moment to give it back. Without this check the run
            # renders a full image for a closed tab — the cancel route can only
            # stop jobs that are already submitted.
            if current_run_aborted():
                raise RuntimeError("generation cancelled while waiting for the GPU")
            result = await fn(self, *args, **kwargs)
            # Cancelled while rendering: ComfyUI was told to interrupt, and an
            # interrupted job can come back without raising. Raising here
            # reaches the release with failed=True, so a truncated hold is not
            # recorded as a duration any completed run has. A run that finished
            # a breath before its abort landed loses one valid sample — it
            # never records a wrong one.
            if current_run_aborted():
                raise RuntimeError("generation cancelled while rendering")
            return result
    return _wrapper


class ComfyUISubmitError(RuntimeError):
    """ComfyUI refused a workflow, or could not be reached to submit one.

    `status` is ComfyUI's HTTP status, or 0 where the request never got an
    answer. `detail` is what ComfyUI said, read into one line.

    Three endings, three sentences. A refusal is ComfyUI judging the workflow;
    a 200 without a prompt_id is ComfyUI accepting it and naming nothing to
    track; no answer at all is ComfyUI out of reach. One prefix for all three
    would call the second one a refusal of a workflow it just accepted.
    """

    def __init__(self, status: int, detail: str):
        self.status = int(status)
        self.detail = detail or ""
        if not self.status:
            what = "ComfyUI could not be reached (no answer)"
        elif self.status == 200:
            what = "ComfyUI answered without starting the workflow (HTTP 200)"
        else:
            what = f"ComfyUI refused the workflow (HTTP {self.status})"
        super().__init__(f"{what}: {self.detail}")


class ComfyUIUploadError(RuntimeError):
    """ComfyUI refused a file for its input directory, or could not be reached with it.

    `status` is ComfyUI's HTTP status, or 0 where the request never got an
    answer. `detail` is what ComfyUI said, or the error the request ended in.
    """

    def __init__(self, status: int, detail: str):
        self.status = int(status)
        self.detail = detail or ""
        if not self.status:
            what = "ComfyUI could not be reached for the upload (no answer)"
        else:
            what = f"ComfyUI refused the upload (HTTP {self.status})"
        super().__init__(f"{what}: {self.detail}")


# How much of a refusal travels. Beyond this it stops being a cause and starts
# being a listing: the surfaces that show it give a sentence's worth of room,
# and three of them render it without a clamp. The whole body is logged.
_REASON_CHARS = 300
_DETAIL_CHARS = 160
# Beyond a handful of broken nodes the line is a listing again. What is cut is
# counted, so nobody reads five and thinks that was all of it.
_NODES_SHOWN = 5
_ERRORS_SHOWN = 3


def _read_comfyui_refusal(body: str) -> str:
    """ComfyUI's refusal, as one line naming the node and what is wrong with it.

    A rejected workflow comes back as `error` (type, message, details) and
    `node_errors` keyed by node id, each carrying its `class_type` and its own
    list of messages. That structure is the whole value of the answer — a
    missing checkpoint reads as "CheckpointLoaderSimple: Value not in list",
    which says what to install, where 500 characters of raw JSON say nothing.

    The two halves can overlap. `error.details` is built by joining
    "{message}: {details}" over the errors of the OUTPUT nodes (execution.py,
    validate_prompt), and `node_errors` carries the errors of every node —
    so where the broken node is itself an output node, both halves say the
    same thing, over several lines. Where the nodes are named they say it
    better, with the class name, and `details` is dropped. Where they are not
    — a custom node this installation lacks answers with `node_errors: {}` and
    the sentence "Node 'X' not found. The custom node may not be installed." —
    `error` is all there is, and it carries the cause on its own.

    One limit worth knowing: the list of what IS installed comes only while
    there are at most 20 of them. Beyond that ComfyUI writes "(list of length
    N)" instead (execution.py, validate_inputs), so a missing LoRA names
    itself but has nothing to be compared against.
    """
    text = (body or "").strip()
    if not text:
        return "empty answer"
    try:
        data = json.loads(text)
    except Exception:
        return reason_line(text, _REASON_CHARS)
    if not isinstance(data, dict):
        # JSON that is a number, a list or a bare null. It carries no field to
        # read, so what came is all there is to say about it.
        return reason_line(text, _REASON_CHARS) or "no reason given"

    node_lines = []
    node_errors = data.get("node_errors")
    if isinstance(node_errors, dict):
        shown = 0
        for node_id, entry in node_errors.items():
            if not isinstance(entry, dict):
                continue
            if shown >= _NODES_SHOWN:
                node_lines.append(f"and {len(node_errors) - shown} more")
                break
            shown += 1
            klass = str(entry.get("class_type") or f"node {node_id}")
            for one in (entry.get("errors") or [])[:_ERRORS_SHOWN]:
                if not isinstance(one, dict):
                    continue
                said = reason_line(one.get("message") or one.get("type") or "",
                                   _DETAIL_CHARS)
                # `details` for a missing file carries the WHOLE list of what
                # IS installed, which is hundreds of characters of noise around
                # one useful name. The line travels onto surfaces that have room
                # for a sentence; the full body stays in the log beside it.
                extra = reason_line(one.get("details") or "", _DETAIL_CHARS)
                if said or extra:
                    node_lines.append(
                        f"{klass}: {said}{f' ({extra})' if extra else ''}")

    parts = []
    err = data.get("error")
    if isinstance(err, dict):
        head = reason_line(err.get("message") or err.get("type") or "",
                           _REASON_CHARS)
        if head:
            parts.append(head)
        detail = reason_line(err.get("details") or "", _DETAIL_CHARS)
        if detail and not node_lines and detail != head:
            parts.append(detail)
    elif err:
        parts.append(reason_line(err, _REASON_CHARS))
    parts.extend(node_lines)

    return (reason_line(" \u2014 ".join(p for p in parts if p), _REASON_CHARS)
            or reason_line(text, _REASON_CHARS)
            or "no reason given")


class ComfyUIWebSocketClient:
    """
    Direct WebSocket client to ComfyUI.

    Provides workflow submission, progress tracking, and media download.
    """

    def __init__(self, base_url: Optional[str] = None, ws_url: Optional[str] = None):
        if base_url is None:
            from config import COMFYUI_URL
            base_url = COMFYUI_URL
        if ws_url is None:
            # Derive ws:// from http://
            ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")

        self.base_url = base_url
        self.ws_url = ws_url
        self.client_id = str(uuid.uuid4())

        logger.info(f"[COMFYUI-WS] Initialized client: HTTP={base_url}, WS={ws_url}, client_id={self.client_id[:8]}...")

    # ------------------------------------------------------------------
    # Core: Submit workflow and track via WebSocket
    # ------------------------------------------------------------------

    @_with_gpu_lease
    async def submit_and_track(
        self,
        workflow: Dict[str, Any],
        timeout: Optional[int] = 480,
        on_progress: Optional[Callable[[ProgressEvent], None]] = None,
        on_event: Optional[Callable[[str, dict], None]] = None,
        before_submit: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> GenerationResult:
        """
        Submit a workflow to ComfyUI and track execution via WebSocket.

        Args:
            workflow: ComfyUI workflow JSON (the prompt dict).
            timeout: Maximum seconds to wait for completion. None waits for
                the run to end however long it takes: a language model
                writes until it stops, and a ceiling on that is the hard
                read timeout rule 5 forbids (llm_client.py passes None).
            on_progress: Optional callback for progress events.
            on_event: Optional callback for the events of the platform's own
                nodes, every message whose type starts with "ai4artsed."
                (the pieces of an answer while a language model writes it):
                called with (type, data) as they arrive.
            before_submit: awaited under the lease, right before the workflow
                goes up: for what the workflow needs in ComfyUI's input
                directory and must not lie there through a wait for the
                card, which a restart empties (my_app/services/latent_decoder.py).
                What it raises ends the run before anything is submitted.

        Returns:
            GenerationResult with downloaded media files.

        Raises:
            TimeoutError: If execution exceeds timeout.
            ComfyUISubmitError: If ComfyUI refused the workflow or could not be
                reached — carrying the status and what ComfyUI said about it.
            RuntimeError: If ComfyUI reports an execution error.
        """
        start_time = time.time()

        # Per-request client_id: ComfyUI's sockets dict is keyed by clientId,
        # so concurrent requests sharing the same clientId overwrite each other
        # and only the last-connected WS receives events. (server.py:254-255)
        request_client_id = str(uuid.uuid4())

        # 1. The socket, BEFORE the submission. ComfyUI hands a message
        # addressed to a client to the socket it knows under that id and
        # drops it when none is connected yet (server.py, send_json); a
        # prompt that starts before the socket is up loses its first events
        # -- the first pieces of an answer a language model writes. The id
        # is chosen here, so the socket can be up before the prompt exists.
        # A socket that cannot be opened is no reason to hold the run: the
        # prompt is submitted either way and followed by polling.
        import websockets
        ws_url = f"{self.ws_url}/ws?clientId={request_client_id}"
        ws_connection = websockets.connect(
            ws_url,
            max_size=100 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )
        try:
            ws = await ws_connection.__aenter__()
        except Exception as e:
            logger.warning(f"[COMFYUI-WS] WebSocket connection failed: {e}. "
                           f"Falling back to history polling.")
            ws = None
        try:
            return await self._submit_then_track(
                workflow, request_client_id, ws, total_nodes=len(workflow),
                timeout=timeout, on_progress=on_progress, on_event=on_event,
                start_time=start_time, before_submit=before_submit)
        finally:
            if ws is not None:
                await ws_connection.__aexit__(None, None, None)

    async def _submit_then_track(self, workflow, request_client_id, ws, total_nodes, timeout,
                                 on_progress, on_event, start_time, before_submit=None):
        """submit_and_track, from the submission on, with the socket open."""
        if before_submit is not None:
            await before_submit()
        # 2. Submit workflow via HTTP
        # No `if not prompt_id` here any more: the submission answers with an
        # id or raises saying why, so there is no silence left to translate
        # into a sentence of this function's own invention.
        prompt_id = await self._submit_workflow(workflow, request_client_id)

        logger.info(f"[COMFYUI-WS] Workflow submitted: {prompt_id}")

        # The prompt id goes to the callback first thing: what a cancel and
        # the history deletion go by. A callback that raises is logged with
        # its cause and the run is tracked on; the id is in the log line.
        if on_progress:
            try:
                on_progress(SubmittedEvent(prompt_id=prompt_id))
            except Exception as e:
                logger.warning(f"[COMFYUI-WS] on_progress refused the submitted event "
                               f"for {prompt_id}: {e!r}")

        # Named under the run this context belongs to, for a cancel that has
        # no progress callback to learn the id from (generation_abort.note_prompt).
        # A run cancelled between the gate's last look and this submission had
        # no prompt to name yet and is interrupted here.
        # Inside the `try`, so that its `finally` forgets the prompt whatever
        # ends the run.
        from my_app.services import generation_abort
        noted_run = generation_abort.CURRENT_RUN_ID.get()

        # 3. Track execution via WebSocket
        try:
            begin_step(prompt_id)
            if generation_abort.note_prompt(noted_run, prompt_id):
                logger.info(f"[COMFYUI-WS] Run {noted_run} was cancelled before {prompt_id} "
                            f"could be named; interrupting it")
                await self.cancel_job(prompt_id)
            if ws is None:
                raise ConnectionError("no websocket")
            await self._track_execution(
                ws=ws,
                prompt_id=prompt_id,
                total_nodes=total_nodes,
                timeout=timeout,
                on_progress=on_progress,
                start_time=start_time,
                on_event=on_event,
            )
        except TimeoutError:
            # Cancel the zombie job in ComfyUI before propagating
            await self.cancel_job(prompt_id)
            raise
        except RuntimeError:
            raise
        except Exception as e:
            # Only fall back to polling for WebSocket failures
            logger.warning(f"[COMFYUI-WS] WebSocket tracking failed: {e}. Falling back to history polling.")
            await self._poll_until_complete(prompt_id, timeout=timeout, start_time=start_time)
        finally:
            end_step(prompt_id)
            generation_abort.forget_prompt(noted_run, prompt_id)

        # 4. Download media via HTTP
        execution_time = time.time() - start_time
        media_files, outputs_metadata = await self._download_outputs(prompt_id)

        logger.info(
            f"[COMFYUI-WS] Generation complete: {len(media_files)} file(s) in {execution_time:.1f}s"
        )

        return GenerationResult(
            prompt_id=prompt_id,
            media_files=media_files,
            execution_time=execution_time,
            outputs_metadata=outputs_metadata,
        )

    # ------------------------------------------------------------------
    # HTTP: Workflow submission
    # ------------------------------------------------------------------

    async def _submit_workflow(self, workflow: Dict[str, Any],
                               client_id: Optional[str] = None) -> str:
        """POST workflow to ComfyUI /prompt endpoint, or raise with the cause.

        One of two doors to /prompt — this one carries every generation that
        goes through the schema pipeline; `comfyui_service.submit_workflow` is
        the synchronous twin used by the model preload and the warm-ahead (the
        third, `legacy_workflow_service`'s own, went on 2026-10-10 with nothing
        calling it). It used to answer a refusal with `None`: the status and the
        sentence ComfyUI wrote went into the log, and the caller turned the
        silence into the fixed words "Failed to submit workflow to ComfyUI".
        A refusal here is the most informative message ComfyUI ever sends — it
        names the node and says what is wrong with it, which is exactly what a
        missing model, a missing custom node or a mistyped input looks like.
        So it travels now (ComfyUISubmitError), and the platform can print the
        cause instead of a sentence that fits every failure equally badly.

        `client_id` defaults to a fresh one: ComfyUI keys its sockets by it, and
        a caller that tracks nothing needs no identity of its own. It used to be
        required, which made the two calls in workflow_streaming_routes (removed 2026-10-10) raise
        TypeError before they ever reached ComfyUI.
        """
        payload = {
            "prompt": as_written(workflow),
            "client_id": client_id or str(uuid.uuid4()),
        }

        # The heaviest thing this workflow loads is what the card ends up
        # holding, and `_checkpoint_of` already reads it to decide whether the
        # next run needs a swap. A workflow naming no model file answers
        # "comfyui", which is the true answer for a run whose weights this
        # platform never picked.
        note_dispatch(_checkpoint_of(workflow), local=True)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/prompt",
                    json=payload,
                    # A bound, and the only one on this path. /prompt is a
                    # handshake: ComfyUI validates the workflow, queues it and
                    # answers an id — the rendering happens in its own worker
                    # thread, so the answer comes in well under a second even
                    # with the card busy. The generation itself is tracked over
                    # the websocket and has no deadline at all.
                    #
                    # It needs one because the submission runs inside the GPU
                    # admission slot, whose heartbeat keeps beating while it
                    # waits: a ComfyUI that accepts the connection and then
                    # says nothing would hold the card against every other run
                    # for as long as the process lives. Two minutes is four
                    # times the deadline that stood here before and cannot
                    # plausibly cut off a healthy submission.
                    timeout=aiohttp.ClientTimeout(sock_connect=10, sock_read=120),
                ) as response:
                    # Text first, then JSON from the text: `response.json()`
                    # raises on a body that is not JSON, and that raise used to
                    # leave through the branch below, which reports status 0 —
                    # "no answer" for an answer that did arrive, with a status
                    # that says what happened.
                    error_text = await response.text()
                    if response.status == 200:
                        try:
                            result = json.loads(error_text)
                        except Exception:
                            result = None
                        prompt_id = (result or {}).get("prompt_id") if isinstance(result, dict) else None
                        if not prompt_id:
                            logger.error(
                                f"[COMFYUI-WS] 200 without a prompt_id: {error_text[:4000]}")
                            raise ComfyUISubmitError(
                                200,
                                f"no prompt_id in the answer \u2014 {_read_comfyui_refusal(error_text)}")
                        return prompt_id
                    detail = _read_comfyui_refusal(error_text)
                    # Twice on purpose: the short reason is what travels to a
                    # surface, the whole answer is what whoever reads logs needs
                    # — a missing checkpoint's `details` names every checkpoint
                    # that IS there, which is the list to compare against.
                    logger.error(
                        f"[COMFYUI-WS] Submit refused: {response.status} — {detail}")
                    logger.error(
                        f"[COMFYUI-WS] ComfyUI said, in full: {error_text[:4000]}")
                    raise ComfyUISubmitError(response.status, detail)
        # `note_dispatch(None)` in both: the workflow was never queued, so
        # nothing is at that checkpoint. A run that carries on after this —
        # another config of the same press — would otherwise show the name of a
        # model that never started (services/streaming_response.py).
        except ComfyUISubmitError:
            note_dispatch(None, local=True)
            raise
        except Exception as e:
            note_dispatch(None, local=True)
            # Reaching ComfyUI failed at all — refused connection, no route,
            # a socket that died mid-answer. Named apart from a refusal,
            # because the two need different things done about them.
            logger.error(f"[COMFYUI-WS] Submit error: {e}")
            raise ComfyUISubmitError(0, f"{type(e).__name__}: {e}") from e

    # ------------------------------------------------------------------
    # WebSocket: Execution tracking
    # ------------------------------------------------------------------

    async def _track_execution(
        self,
        ws,
        prompt_id: str,
        total_nodes: int,
        timeout: Optional[int],
        on_progress: Optional[Callable],
        start_time: float,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        """Track workflow execution via WebSocket events, on the socket that
        was opened under this request's client id before the prompt was
        submitted (submit_and_track)."""
        # Race condition guard: check if execution already completed before WS connected
        if await self._check_already_completed(prompt_id):
            # Finished before the socket was up. Step 4 downloads the
            # outputs either way; without this return the loop waits for
            # events that will never arrive, until the timeout fires and
            # cancel_job destroys a job that was already done.
            if on_progress:
                on_progress(ProgressEvent(
                    overall_percent=1.0,
                    current_percent=1.0,
                    nodes_done=total_nodes,
                    total_nodes=total_nodes,
                ))
            return

        nodes_done = 0
        current_step = 0
        max_steps = 1
        our_execution_started = False

        while True:
            # Check timeout. None is no ceiling (submit_and_track).
            elapsed = time.time() - start_time
            if timeout is not None and elapsed > timeout:
                raise TimeoutError(f"Execution timeout after {timeout}s")

            try:
                wait = 30 if timeout is None else min(30, timeout - elapsed)
                raw = await asyncio.wait_for(ws.recv(), timeout=wait)
            except asyncio.TimeoutError:
                # No message for 30s. A prompt that is neither queued nor
                # running nor finished will send none, ever: it was
                # deleted from the queue, or ComfyUI restarted and lost
                # it. Said now rather than waited for without end.
                await self._require_known(prompt_id)
                continue

            # Binary message = denoising preview
            if isinstance(raw, bytes):
                preview_b64 = self._parse_binary_preview(raw)
                if preview_b64 and on_progress:
                    step_progress = current_step / max_steps if max_steps > 0 else 0
                    overall = (nodes_done + step_progress) / total_nodes if total_nodes > 0 else 0
                    on_progress(ProgressEvent(
                        overall_percent=min(overall, 0.99),
                        current_percent=step_progress,
                        nodes_done=nodes_done,
                        total_nodes=total_nodes,
                        preview_base64=preview_b64,
                    ))
                continue

            # JSON message
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            data = msg.get("data", {})

            if msg_type == "status":
                # Broadcast on every change of the queue: a prompt
                # queued, taken up, finished -- or deleted, which is the
                # one change ComfyUI reports to nobody by name
                # (execution.py, delete_queue_item). So the queue and
                # the history are asked whether ours is still there.
                await self._require_known(prompt_id)
                continue

            # Filter: only react to OUR prompt
            # Check prompt_id on EVERY event (not just execution_start)
            # to handle the race where execution_start fires before WS connects
            event_prompt_id = data.get("prompt_id")
            if event_prompt_id == prompt_id:
                if not our_execution_started:
                    our_execution_started = True
                    logger.info(f"[COMFYUI-WS] Tracking execution: {prompt_id} (first event: {msg_type})")
            elif event_prompt_id and event_prompt_id != prompt_id:
                # Event for a different prompt — skip
                continue

            if msg_type == "execution_start":
                continue

            # Skip events until we've seen at least one event for our prompt
            if not our_execution_started:
                continue

            if msg_type == "executing":
                node = data.get("node")
                if node is None:
                    # node=None means execution finished
                    logger.info(f"[COMFYUI-WS] Execution finished: {prompt_id}")
                    if on_progress:
                        on_progress(ProgressEvent(
                            overall_percent=1.0,
                            current_percent=1.0,
                            nodes_done=total_nodes,
                            total_nodes=total_nodes,
                        ))
                    return
                else:
                    nodes_done += 1
                    current_step = 0
                    max_steps = 1
                    if on_progress:
                        overall = nodes_done / total_nodes if total_nodes > 0 else 0
                        on_progress(ProgressEvent(
                            overall_percent=min(overall, 0.99),
                            current_percent=0.0,
                            nodes_done=nodes_done,
                            total_nodes=total_nodes,
                            current_node=node,
                        ))

            elif msg_type == "execution_cached":
                cached_nodes = data.get("nodes", [])
                nodes_done += len(cached_nodes)
                logger.debug(f"[COMFYUI-WS] {len(cached_nodes)} nodes cached")

            elif msg_type == "progress":
                current_step = data.get("value", 0)
                max_steps = data.get("max", 1)
                note_step(prompt_id, current_step, max_steps)
                if on_progress:
                    step_progress = current_step / max_steps if max_steps > 0 else 0
                    overall = (nodes_done + step_progress) / total_nodes if total_nodes > 0 else 0
                    on_progress(ProgressEvent(
                        overall_percent=min(overall, 0.99),
                        current_percent=step_progress,
                        nodes_done=nodes_done,
                        total_nodes=total_nodes,
                    ))

            elif msg_type == "execution_error":
                error_msg = data.get("exception_message", "Unknown error")
                node_type = data.get("node_type", "unknown")
                logger.error(f"[COMFYUI-WS] Execution error in {node_type}: {error_msg}")
                raise RuntimeError(f"ComfyUI execution error in {node_type}: {error_msg}")

            elif msg_type == "execution_interrupted":
                # An interrupt is a cancelled run, not a completed one.
                # Without this branch the loop ends on executing(node=None)
                # as if the run had finished: the truncated hold would be
                # released as valid, and the abort mark that the wrapper
                # checks afterwards can be erased by a retry that reuses
                # the run id. The filter above guarantees this is OUR
                # prompt — cancel_job targets one prompt_id.
                logger.info(f"[COMFYUI-WS] Execution interrupted: {prompt_id}")
                raise RuntimeError(f"ComfyUI execution interrupted: {prompt_id}")

            elif msg_type == "executed":
                # Final output from a node — execution will end with executing(node=None) next
                pass

            elif isinstance(msg_type, str) and msg_type.startswith("ai4artsed."):
                # An event of one of the platform's own nodes, sent to
                # this client (PromptServer.send_sync with the executing
                # prompt's client id). Handed on as it is.
                if on_event is not None:
                    on_event(msg_type, data)

    async def _check_already_completed(self, prompt_id: str) -> bool:
        """Whether the job was already finished before the WebSocket was up.

        True means the outputs are in /history and the caller can stop waiting.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        history = await response.json()
                        if history and prompt_id in history:
                            entry = history[prompt_id]
                            status_str = entry.get("status", {}).get("status_str", "")
                            if status_str == "error":
                                msgs = entry.get("status", {}).get("messages", [])
                                error_msg = "Unknown error"
                                for msg in msgs:
                                    if isinstance(msg, list) and msg[0] == "execution_error":
                                        error_msg = msg[1].get("exception_message", error_msg)
                                raise RuntimeError(f"ComfyUI execution error: {error_msg}")
                            if entry.get("outputs"):
                                logger.info(f"[COMFYUI-WS] Execution already completed (pre-WS)")
                                return True  # Outputs are downloaded by step 4
        except RuntimeError:
            raise
        except Exception:
            pass  # History check failed, continue with WS tracking
        return False

    async def _require_known(self, prompt_id: str) -> None:
        """Raise unless ComfyUI still has the prompt: queued, running, or in
        its history. The queue is asked first and the history second, in
        that order, because a prompt leaves the queue and enters the history
        under one lock and never goes the other way. ComfyUI refusing the
        connection is the same answer said differently: the process is
        gone, and its queue with it."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/queue",
                                       timeout=aiohttp.ClientTimeout(total=15)) as response:
                    queue = await response.json() if response.status == 200 else {}
                for item in list(queue.get("queue_running", [])) + list(queue.get("queue_pending", [])):
                    # item: [number, prompt_id, prompt, extra_data, outputs_to_execute]
                    if isinstance(item, list) and len(item) > 1 and item[1] == prompt_id:
                        return
                async with session.get(f"{self.base_url}/history/{prompt_id}",
                                       timeout=aiohttp.ClientTimeout(total=15)) as response:
                    history = await response.json() if response.status == 200 else {}
                if history and prompt_id in history:
                    return
        except asyncio.TimeoutError:
            # The question went unanswered within its 15 s (ComfyUI's HTTP
            # answers slowly while the card is busy): no verdict about the
            # prompt, and the next status message or idle wake-up asks
            # again. Left to propagate, the TimeoutError would be taken
            # for the run's own ceiling and cancel a prompt that is fine.
            # Before the connection clause: aiohttp's own timeout errors
            # are connection errors too.
            logger.warning(f"[COMFYUI-WS] ComfyUI did not answer whether prompt {prompt_id} "
                           f"still exists; asked again on the next message")
            return
        except aiohttp.ClientConnectionError as e:
            raise RuntimeError(f"ComfyUI at {self.base_url} refused the connection while "
                               f"prompt {prompt_id} was tracked ({e}); a prompt survives no "
                               f"restart of ComfyUI") from e
        raise RuntimeError(f"prompt {prompt_id} is neither queued nor running nor in ComfyUI's "
                           f"history: deleted from the queue, or ComfyUI restarted and lost it")

    async def forget_prompts_of(self, class_type: str) -> int:
        """Take every prompt out of ComfyUI's history whose workflow holds a
        node of this class, and say how many. One GET of the history, one
        POST. For the prompts of the local language model a DevServer
        process left behind when it ended mid-run (llm_client
        .forget_left_prompts); no ComfyUI means nothing to take out."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/history",
                                       timeout=aiohttp.ClientTimeout(total=60)) as response:
                    history = await response.json() if response.status == 200 else {}
                ids = [pid for pid, entry in history.items() if _holds_node(entry, class_type)]
                if ids:
                    await session.post(f"{self.base_url}/history", json={"delete": ids},
                                       timeout=aiohttp.ClientTimeout(total=60))
                return len(ids)
        except aiohttp.ClientConnectionError:
            return 0

    async def forget_prompt(self, prompt_id: str) -> None:
        """Take a finished prompt out of ComfyUI's history, inputs and all.
        Best effort: a failure is logged and changes nothing about the
        answer already read."""
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{self.base_url}/history",
                    json={"delete": [prompt_id]},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception as e:
            logger.warning(f"[COMFYUI-WS] History entry {prompt_id} could not be deleted: {e!r}")

    # ------------------------------------------------------------------
    # Fallback: History polling (when WebSocket fails)
    # ------------------------------------------------------------------

    async def _poll_until_complete(
        self,
        prompt_id: str,
        timeout: Optional[int] = 480,
        poll_interval: float = 2.0,
        start_time: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Poll /history until workflow completes. Fallback for WebSocket failures."""
        if start_time is None:
            start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if timeout is not None and elapsed > timeout:
                raise TimeoutError(f"Polling timeout after {timeout}s for {prompt_id}")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.base_url}/history/{prompt_id}",
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as response:
                        if response.status == 200:
                            history = await response.json()
                            if history and prompt_id in history:
                                entry = history[prompt_id]
                                status = entry.get("status", {}).get("status_str", "")
                                if status == "error":
                                    raise RuntimeError(f"ComfyUI workflow error: {entry.get('status')}")
                                outputs = entry.get("outputs", {})
                                if outputs:
                                    logger.info(f"[COMFYUI-WS] Poll: completed after {elapsed:.1f}s")
                                    return entry
                            else:
                                # Not finished: still queued or running, or
                                # gone (deleted, or ComfyUI restarted), which
                                # no amount of polling would tell apart.
                                await self._require_known(prompt_id)
            except RuntimeError:
                raise
            except Exception as e:
                # A poll that failed to reach ComfyUI, or an answer it could
                # not read. Asked once more whether the prompt still exists:
                # a refused connection is ComfyUI gone, and its prompt with
                # it, which raises here instead of polling on for ever.
                # The 15 s of a poll going by unanswered land here too, on
                # purpose: since Python 3.11 aiohttp's timeout IS the
                # TimeoutError, and re-raised it would be taken for the
                # run's own ceiling (raised above, outside this try) and
                # end a run that is fine. ComfyUI answers nothing for
                # minutes while a node holds the interpreter (the mesh
                # extraction of Hunyuan3D, measured 2026-09-14: the socket
                # closed on a ping, then a poll's silence ended the run at
                # 98 s of 342), and the next poll finds the outputs.
                logger.debug(f"[COMFYUI-WS] Poll error: {e!r}")
                await self._require_known(prompt_id)

            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Binary preview parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_binary_preview(data: bytes) -> Optional[str]:
        """Parse binary WebSocket message into base64-encoded preview image.

        ComfyUI binary message format:
        - Bytes 0-3: event type (uint32)
        - Bytes 4-7: format info (uint32)
        - Bytes 8+: image data (JPEG or PNG)
        """
        import base64

        if len(data) < 8:
            return None

        # Event type 1 = preview image, 2 = final output
        try:
            event_type = struct.unpack(">I", data[:4])[0]
        except struct.error:
            return None

        if event_type not in (1, 2):
            return None

        image_data = data[8:]
        if len(image_data) < 100:
            return None

        return base64.b64encode(image_data).decode("ascii")

    # ------------------------------------------------------------------
    # HTTP: Download outputs after completion
    # ------------------------------------------------------------------

    async def _download_outputs(self, prompt_id: str) -> tuple:
        """Download all media files from a completed workflow.

        Returns:
            (media_files: List[MediaFile], outputs_metadata: dict)
        """
        media_files = []
        outputs_metadata = {}

        # 1. Get history to find output filenames
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status != 200:
                        logger.error(f"[COMFYUI-WS] History fetch failed: {response.status}")
                        return media_files, outputs_metadata

                    history = await response.json()

        except Exception as e:
            logger.error(f"[COMFYUI-WS] History fetch error: {e}")
            return media_files, outputs_metadata

        if prompt_id not in history:
            logger.error(f"[COMFYUI-WS] prompt_id {prompt_id} not in history")
            return media_files, outputs_metadata

        entry = history[prompt_id]
        outputs = entry.get("outputs", {})

        # 2. Download every file the nodes announced, kind by kind.
        return await self._announced_files(outputs), outputs

    async def _announced_files(self, outputs: dict) -> List[MediaFile]:
        """Every file the nodes of a run announced (ANNOUNCED_FILES, kind by
        kind per node), fetched from /view. A file that was announced and
        then refused stops the run with the cause: a chunk that reads the
        first file of a run would otherwise read another one, and one that
        reads a file by node would report the announcement as missing.
        """
        media_files: List[MediaFile] = []
        async with aiohttp.ClientSession() as session:
            for node_id, node_output in outputs.items():
                for key, media_type in ANNOUNCED_FILES:
                    for one in node_output.get(key, []):
                        try:
                            file_data = await self._view(
                                session, one["filename"],
                                one.get("subfolder", ""), one.get("type", "output")
                            )
                        except Exception as exc:
                            raise RuntimeError(
                                f"ComfyUI announced {one['filename']} at node {node_id} "
                                f"and fetching it failed: {exc}"
                            ) from exc
                        media_files.append(MediaFile(
                            data=file_data,
                            filename=one["filename"],
                            media_type=media_type,
                            subfolder=one.get("subfolder", ""),
                            node_id=node_id,
                            meta=one.get("meta") or {},
                        ))
        return media_files

    async def _view(
        self, session: aiohttp.ClientSession,
        filename: str, subfolder: str, type_name: str,
    ) -> bytes:
        """One file from ComfyUI's /view endpoint; raises with the cause when
        it does not come."""
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": type_name,
        }
        async with session.get(
            f"{self.base_url}/view",
            params=params,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as response:
            if response.status != 200:
                raise RuntimeError(f"/view answered HTTP {response.status} for {filename}")
            data = await response.read()
            logger.debug(f"[COMFYUI-WS] Downloaded {filename}: {len(data)} bytes")
            return data

    async def _download_view(
        self, session: aiohttp.ClientSession,
        filename: str, subfolder: str, type_name: str,
    ) -> Optional[bytes]:
        """Download a single file via ComfyUI /view endpoint; None, with the
        cause logged, when it does not come."""
        try:
            return await self._view(session, filename, subfolder, type_name)
        except Exception as e:
            logger.error(f"[COMFYUI-WS] Download error {filename}: {e}")
            return None

    # ------------------------------------------------------------------
    # Image upload (for img2img workflows)
    # ------------------------------------------------------------------

    async def upload_file(self, data: bytes, filename: str) -> str:
        """The bytes into ComfyUI's input directory under this name, or raises.

        ComfyUI's /upload/image writes what it is given, as it is, under the
        name; a picture for img2img and a kept latent go up the same way.

        Returns:
            The name ComfyUI stored the file under.

        Raises:
            ComfyUIUploadError: with ComfyUI's status and what it said, or with
                the error the request ended in.
        """
        form = aiohttp.FormData()
        form.add_field(
            "image", data,
            filename=filename,
            content_type="image/png",
        )
        form.add_field("overwrite", "true")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/upload/image",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 413:
                        # aiohttp's client_max_size, set by ComfyUI's
                        # --max-upload-size (2_start_comfyui.sh raises it
                        # for the recordings and videos the media readers
                        # take); the body is aiohttp's own page.
                        raise ComfyUIUploadError(
                            413, f"the file {filename} ({len(data) / 2**20:.0f} MB) is larger than "
                                 f"ComfyUI's upload limit (--max-upload-size)")
                    if response.status != 200:
                        body = (await response.text())[:_DETAIL_CHARS]
                        raise ComfyUIUploadError(response.status, body)
                    result = await response.json()
        except ComfyUIUploadError:
            raise
        except Exception as e:
            raise ComfyUIUploadError(0, f"{type(e).__name__}: {e}") from e
        uploaded_name = result.get("name", filename)
        logger.info(f"[COMFYUI-WS] Uploaded {uploaded_name}")
        return uploaded_name

    async def upload_image(self, image_data: bytes, filename: str) -> Optional[str]:
        """Upload image to ComfyUI for img2img workflows.

        Args:
            image_data: Raw image bytes.
            filename: Target filename.

        Returns:
            Uploaded filename as returned by ComfyUI, or None on failure (the
            cause is logged; `upload_file` is the call that carries it).
        """
        try:
            return await self.upload_file(image_data, filename)
        except ComfyUIUploadError as e:
            logger.error(f"[COMFYUI-WS] Upload failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Check if ComfyUI is accessible via GET /system_stats."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/system_stats",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get ComfyUI queue status."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/queue",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        queue_running = len(data.get("queue_running", []))
                        queue_pending = len(data.get("queue_pending", []))
                        return {
                            "queue_running": queue_running,
                            "queue_pending": queue_pending,
                            "total": queue_running + queue_pending,
                        }
        except Exception as e:
            logger.debug(f"[COMFYUI-WS] Queue status unavailable: {e}")

        return {"queue_running": 0, "queue_pending": 0, "total": 0}


    async def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get history for a specific prompt_id."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 200:
                        history = await response.json()
                        if prompt_id in history:
                            return history[prompt_id]
        except Exception as e:
            logger.error(f"[COMFYUI-WS] History error: {e}")
        return None


    async def cancel_job(self, prompt_id: str) -> None:
        """Cancel a specific job: remove it from the queue if pending,
        interrupt it if running.

        In that order. A prompt goes from pending to running and never
        back, so after the delete it is either gone or running, and the
        interrupt finds it. The other way round (until 2026-09-13) left a
        gap: a prompt the worker took between the two requests was skipped
        by the interrupt (not running yet) and missed by the delete (no
        longer pending), and ran to its end for nobody.
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Remove from pending queue
                await session.post(
                    f"{self.base_url}/queue",
                    json={"delete": [prompt_id]},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
                # Interrupt if currently executing
                await session.post(
                    f"{self.base_url}/interrupt",
                    json={"prompt_id": prompt_id},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
                logger.info(f"[COMFYUI-WS] Cancelled job: {prompt_id}")
        except Exception as e:
            logger.debug(f"[COMFYUI-WS] Cancel job best-effort failed: {e}")

    # ------------------------------------------------------------------
    # Legacy compatibility helpers
    # ------------------------------------------------------------------

    async def wait_for_completion(
        self,
        prompt_id: str,
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> Optional[Dict[str, Any]]:
        """Compatibility method: poll history until complete (like old clients).

        Returns the history entry dict, or None on timeout.
        """
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"[COMFYUI-WS] Timeout ({timeout}s) waiting for {prompt_id}")
                return None

            entry = await self.get_history(prompt_id)
            if entry:
                outputs = entry.get("outputs", {})
                if outputs:
                    logger.info(f"[COMFYUI-WS] Completed after {elapsed:.1f}s")
                    return entry
                status = entry.get("status", {}).get("status_str", "")
                if status == "error":
                    logger.error(f"[COMFYUI-WS] Workflow failed: {entry.get('status')}")
                    return None

            await asyncio.sleep(poll_interval)

    async def get_generated_images(self, history_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract image file info from a history entry (compatibility with comfyui_client)."""
        images = []
        for node_id, node_output in history_entry.get("outputs", {}).items():
            for img in node_output.get("images", []):
                images.append({
                    "filename": img.get("filename"),
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output"),
                    "node_id": node_id,
                })
        return images

    async def get_generated_audio(self, history_entry: Dict[str, Any]) -> List[str]:
        """Extract audio file paths from a history entry."""
        audio_files = []
        for node_output in history_entry.get("outputs", {}).values():
            for key in ("audio", "genaudio"):
                for aud in node_output.get(key, []):
                    filename = aud.get("filename")
                    if filename:
                        subfolder = aud.get("subfolder", "")
                        audio_files.append(f"{subfolder}/{filename}" if subfolder else filename)
        return audio_files

    async def get_generated_video(self, history_entry: Dict[str, Any]) -> List[str]:
        """Extract video file paths from a history entry."""
        video_files = []
        for node_output in history_entry.get("outputs", {}).values():
            for key in ("video", "genvideo", "gifs"):
                for vid in node_output.get(key, []):
                    filename = vid.get("filename")
                    if filename:
                        subfolder = vid.get("subfolder", "")
                        video_files.append(f"{subfolder}/{filename}" if subfolder else filename)
        return video_files

    async def get_image(
        self, filename: str, subfolder: str = "", folder_type: str = "output"
    ) -> Optional[bytes]:
        """Download a single file via /view (compatibility with comfyui_client.get_image)."""
        async with aiohttp.ClientSession() as session:
            return await self._download_view(session, filename, subfolder, folder_type)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_client: Optional[ComfyUIWebSocketClient] = None


def get_comfyui_ws_client(base_url: Optional[str] = None) -> ComfyUIWebSocketClient:
    """Get singleton ComfyUI WebSocket client."""
    global _client
    if _client is None:
        _client = ComfyUIWebSocketClient(base_url)
    return _client
