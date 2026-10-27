"""
LLM Client — the DevServer's local language models, run by ComfyUI.

Every local inference but one (image reading, the local half of the
comparison surfaces, the chat) is one prompt of the platform's own node
ai4artsed_local_llm
(comfyui_nodes/ai4artsed_comfyui/), queued at ComfyUI like a picture and
tracked over its websocket (services/comfyui_ws_client). The weights are on
the card under ComfyUI's memory management, which moves language and
diffusion models on and off the card as ONE allocator. Until stage 3 of
the move to ComfyUI the models were the GPU service's
llama-server children, reached over /api/llm/*, and that process and ComfyUI
allocated the same card apart from each other.

The one is the classify reading of the safety chain
(services/safety_classifier.score, POST /api/llm/classify on the GPU
service): the node package has no reading for it, and it stays there as
the exception the decision of 2026-09-17 names (finding S-036 of the code review of 2026-10-10).

Which folder an alias names is the table config/local_llm_weights.json
(services/local_llm_weights). Cloud LLM calls (Stage 1-3 interception) go
through backend_router.
"""

import asyncio
import contextvars
import json
import logging
import queue
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from my_app.services import local_llm_weights
from my_app.services.streaming_response import note_dispatch

logger = logging.getLogger(__name__)

# No output cap: the node writes until the model stops or the context window
# is full, where the answer comes back with finish_reason "length", said
# plainly rather than cut in silence. Caps are permitted only where a provider
# API requires the field. No read timeout either: the ComfyUI client connects
# with its own short timeouts and waits for the run without a ceiling
# (timeout=None below); a hard read timeout throws away a slow answer.

# The one node of the prompt, and its class in the package.
NODE_ID = "1"
NODE_CLASS = "ai4artsed_local_llm"
# The websocket event the node sends for every piece of an answer while it is
# written (comfyui_nodes/ai4artsed_comfyui/_local_llm.py, TOKEN_EVENT).
TOKEN_EVENT = "ai4artsed.llm.token"


def _body_reason(resp) -> str:
    """A service's own error text, ready to append to a log line.

    An HTTPError stringifies to the status and the URL and nothing else, so a
    503 that says "VRAM shortfall ..." reaches a log as "503 Server Error".
    Best effort by design: no body, no JSON, no error field — then there is
    nothing to add and the line stays as it was. Read by the training service
    for its own HTTP calls.

    The cut is wide because of what arrives in that field: the last lines a
    failed child wrote, and those lines ARE the diagnosis.
    """
    if resp is None:
        return ""
    try:
        error = (resp.json() or {}).get("error")
    except Exception:
        return ""
    return f" — {str(error)[:1200]}" if error else ""


def _first(values) -> Any:
    """ComfyUI carries a node's ui output as a list per key."""
    if isinstance(values, list):
        return values[0] if values else None
    return values


def _rest_of(content: str, streamed: str) -> Optional[str]:
    """What of the whole answer the stream has yet to hand out: "" when the
    pieces were all of it, the tail when they were its beginning, None when
    they were something else (a beginning the socket missed). Compared
    without the whitespace the answer is trimmed by at its ends."""
    whole, seen = content.strip(), streamed.strip()
    if whole == seen:
        return ""
    if not whole.startswith(seen):
        return None
    tail = whole[len(seen):]
    # Whitespace the last piece ended with is in the reader's hands already.
    held = streamed[len(streamed.rstrip()):]
    if held and tail.startswith(held):
        tail = tail[len(held):]
    return tail


def _cancel_at_comfyui(prompt_id: str) -> None:
    """Interrupt a running prompt, take a waiting one out of the queue."""
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    asyncio.run(get_comfyui_ws_client().cancel_job(prompt_id))


def upload_input(data: bytes, filename: str) -> str:
    """The bytes into ComfyUI's input directory under this name, and the
    name they were stored under: what a node that reads a file is handed
    (ai4artsed_media_reading takes a file of that directory by name). The
    upload is the ComfyUI client's, which is asynchronous; this runs it on
    a thread of its own, so it can be called from a Flask thread and from a
    chunk that already holds a loop alike. Raises comfyui_ws_client.
    ComfyUIUploadError with ComfyUI's status and what it said."""
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    client = get_comfyui_ws_client()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, client.upload_file(data, filename)).result()


def _said(e: BaseException) -> str:
    """An exception as a reason: its text, or its type where it has none
    (a bare TimeoutError stringifies to nothing)."""
    return str(e) or type(e).__name__


def forget_left_prompts() -> int:
    """Take out of ComfyUI's history every prompt of the node that an
    earlier DevServer process left there, and say how many.

    A run ends with the deletion of its history entry (_tracked); a process
    that ends while a run stands never reaches it, ComfyUI runs the prompt
    to its end and keeps the entry -- the conversation and, for an image
    reading, the picture -- readable at /history until ComfyUI restarts or
    ten thousand prompts later. Called once per start, on a thread of its
    own (my_app.create_app); ComfyUI not being up means nothing to take
    out.
    """
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    from my_app.services.text_probes import REP_ENGINEERING_NODE, SCORES_NODE
    client = get_comfyui_ws_client()

    async def sweep():
        # The readings of the Text Lab travel the same way (run_node) and
        # leave the same kind of entry: the contrast pairs and the corpus
        # sentences of a run.
        return sum([await client.forget_prompts_of(c)
                    for c in (NODE_CLASS, SCORES_NODE, REP_ENGINEERING_NODE)])
    return asyncio.run(sweep())


def forget_left_prompts_in_background() -> threading.Thread:
    """forget_left_prompts on a daemon thread: the start of the DevServer
    waits for no ComfyUI."""
    def sweep():
        try:
            count = forget_left_prompts()
        except Exception as e:
            logger.warning(f"[LLM-CLIENT] The prompts an earlier process left in ComfyUI's "
                           f"history could not be taken out: {_said(e)}")
            return
        if count:
            logger.info(f"[LLM-CLIENT] {count} prompt(s) of the local language model, left in "
                        f"ComfyUI's history by an earlier process, taken out")

    thread = threading.Thread(target=sweep, name="llm-history-sweep", daemon=True)
    thread.start()
    return thread


class LLMClient:
    """Client for local LLM inference, run by ComfyUI."""

    def __init__(self):
        logger.info("[LLM-CLIENT] Initialized: local language models run by ComfyUI")

    # ------------------------------------------------------------------
    # The prompt, the run, the answer
    # ------------------------------------------------------------------

    def _workflow(self, model: str, messages: Optional[list] = None, prompt: Optional[str] = None,
                  images: Optional[List[str]] = None, temperature: float = 0.7,
                  repetition_penalty: Optional[float] = None, stream: bool = False,
                  enable_thinking: bool = True) -> Dict[str, Any]:
        """The one-node prompt for this call, or LookupError for a model that
        is not a local model of this installation.

        A conversation goes as JSON and the node applies the model's chat
        template; a raw prompt goes as it is (raw=True). `enable_thinking`
        goes to that template: False closes the think block in the prompt
        where the template has the switch (Qwen 3, 3.5, 3.8, SmolLM3), and
        the model answers without reasoning first; a raw prompt passes
        through no template, so the flag acts on nothing there. The seed is drawn
        here: ComfyUI answers a prompt whose inputs it has seen before from
        its cache, and a fresh seed is what makes every call a run.
        """
        dir_name = local_llm_weights.dir_name(model)
        if dir_name is None:
            raise LookupError(f"{model} is not a local model this installation knows "
                              f"(config/local_llm_weights.json)")
        if not local_llm_weights.is_installed(model):
            raise LookupError(f"{model} is not installed under {local_llm_weights.models_root()} "
                              f"(download_llm_models.sh or the Download entry of a model list "
                              f"installs it)")
        inputs: Dict[str, Any] = {
            "llm_name": dir_name,
            "messages": prompt if prompt is not None else json.dumps(messages, ensure_ascii=False),
            "raw": prompt is not None,
            "temperature": float(temperature),
            "seed": random.getrandbits(63),
            "stream": bool(stream),
            "enable_thinking": bool(enable_thinking),
        }
        if images:
            inputs["images_b64"] = json.dumps(list(images))
        if repetition_penalty is not None:
            inputs["repetition_penalty"] = float(repetition_penalty)
        return {NODE_ID: {"class_type": NODE_CLASS, "inputs": inputs}}

    @staticmethod
    async def _tracked(workflow: Dict[str, Any], on_progress: Optional[Callable],
                       on_event: Optional[Callable[[str, dict], None]]):
        """Queue the prompt, wait for the run, and take the prompt out of
        ComfyUI's history afterwards, whichever way the run ended.

        ComfyUI keeps every prompt it ran in its history, inputs included --
        the conversation and, for an image reading, the picture -- readable
        by anything on this machine (/history, no login) until the process
        ends or ten thousand prompts later. The platform's rule for the
        pictures of a workshop is that they stay where they were handed in;
        the answer has been read off the history by the time this returns,
        so the entry is deleted. Best effort: a deletion that fails is
        logged and changes nothing about the answer.
        """
        from my_app.services.comfyui_ws_client import get_comfyui_ws_client
        client = get_comfyui_ws_client()
        submitted: Dict[str, str] = {}

        def _progress(ev):
            if getattr(ev, "event_type", None) == "submitted":
                submitted["prompt_id"] = ev.prompt_id
            if on_progress is not None:
                on_progress(ev)

        try:
            return await client.submit_and_track(workflow, timeout=None,
                                                 on_progress=_progress, on_event=on_event)
        finally:
            if submitted.get("prompt_id"):
                await client.forget_prompt(submitted["prompt_id"])

    @classmethod
    def _track(cls, workflow: Dict[str, Any], on_progress: Optional[Callable] = None,
               on_event: Optional[Callable[[str, dict], None]] = None):
        """Queue the prompt and wait for the run, on this thread's own loop.

        `asyncio.run` leaves the thread it ran on without a current event
        loop, and everything around this client is synchronous, so this is
        only ever called on a pool thread (see `_run`), which keeps the loop
        it made to itself. No ceiling on the wait: the node writes until the
        model stops (timeout=None, submit_and_track); a prompt that vanishes
        from ComfyUI (deleted, or ComfyUI restarted) ends the wait with an
        error that says so.
        """
        return asyncio.run(cls._tracked(workflow, on_progress, on_event))

    @staticmethod
    def _context(workload: Optional[str] = None) -> contextvars.Context:
        """A COPY of this request's context for the pool thread, with the
        output config taken out or replaced by the workload a caller names.

        The pool thread starts with an EMPTY context. Without the copy the
        run reached ComfyUI carrying nothing this request knows: not the run
        id the GPU gate labels a run with, and not the holder that says which
        model the run is at (`note_dispatch`). The same bridge as
        mean_images_routes.decode. The output config is dropped on the way:
        the gate keys its expected durations by it (`stats_key`), and a
        safety check that runs inside an image run would otherwise be timed
        as that image config. The model id is the key for these runs, and
        a reading of the Text Lab names its own (`run_node`).
        """
        from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
        ctx = contextvars.copy_context()
        ctx.run(CURRENT_OUTPUT_CONFIG.set, workload or None)
        return ctx

    @classmethod
    def _run(cls, workflow: Dict[str, Any], workload: Optional[str] = None):
        """`_track` on a pool thread, in a copy of this context (`_context`)."""
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(cls._context(workload).run, cls._track, workflow).result()

    @staticmethod
    def _answer(result) -> Dict[str, Any]:
        """What the node wrote, off the run's /history entry."""
        out = (result.outputs_metadata or {}).get(NODE_ID) or {}
        content = _first(out.get("content"))
        if content is None:
            raise RuntimeError(f"the run {result.prompt_id} ended without the node's answer in its outputs")
        thinking = _first(out.get("thinking")) or None
        return {
            "content": content,
            "thinking": thinking,
            "finish_reason": _first(out.get("finish_reason")) or "stop",
            "prompt_tokens": _first(out.get("prompt_tokens")),
            "completion_tokens": _first(out.get("completion_tokens")),
        }

    @classmethod
    def run_node(cls, class_type: str, inputs: Dict[str, Any],
                 workload: Optional[str] = None) -> Dict[str, Any]:
        """One prompt of one node of the platform's package, and what the
        node wrote: its ui outputs off the run's /history entry, each value
        a list. The readings of the Text Lab (services/text_probes) go this
        way; the run is queued, tracked and taken out of the history exactly
        as a chat is (_run, _tracked). `workload` is the key the gate files
        the run's duration under (its stats key); without one the run is
        keyed by its model, as a chat is."""
        return cls.run_node_files(class_type, inputs, workload)[0]

    @classmethod
    def run_node_files(cls, class_type: str, inputs: Dict[str, Any],
                       workload: Optional[str] = None) -> Tuple[Dict[str, Any], list]:
        """`run_node`, with the files the node announced beside what it
        wrote: (the ui outputs, [comfyui_ws_client.MediaFile] in the order
        of the announcement). The media stations answer this way -- a sound
        under "audio", a mesh under "3d" (ANNOUNCED_FILES): the tracking
        fetches each file off /view before the run's history entry is taken
        out, so the bytes outlive the entry. `workload` as in `run_node`; a
        chunk hands over its output config, so the run is timed as that
        config, the way a picture's run is."""
        workflow = {NODE_ID: {"class_type": class_type, "inputs": inputs}}
        result = cls._run(workflow, workload)
        out = (result.outputs_metadata or {}).get(NODE_ID) or {}
        if not out:
            raise RuntimeError(f"the run {result.prompt_id} ended without the node's answer in its outputs")
        return ({k: _first(v) if isinstance(v, list) else v for k, v in out.items()},
                list(result.media_files or []))


    def _chat(self, model: str, messages: list, images: Optional[List[str]] = None,
              temperature: float = 0.7, max_new_tokens: Optional[int] = None,
              repetition_penalty: Optional[float] = None,
              enable_thinking: bool = True) -> Optional[Dict[str, Any]]:
        """Chat: one prompt of the node, the conversation through the model's
        chat template."""
        try:
            workflow = self._workflow(model, messages=messages, images=images,
                                      temperature=temperature, repetition_penalty=repetition_penalty,
                                      enable_thinking=enable_thinking)
            # Said on the payload's way out, so what is announced is by
            # construction the model the run is asked for. `local=True`:
            # everything in this client runs on this machine, and the model
            # id itself cannot say that (see `note_dispatch`).
            note_dispatch(model, local=True)
            answer = self._answer(self._run(workflow))
            return {
                "content": answer["content"],
                "thinking": answer["thinking"],
                "tool_calls": None,
                "finish_reason": answer["finish_reason"],
            }
        except Exception as e:
            # Nothing is at this model any more, and that is said rather than
            # left standing: a run goes on after a call that failed, and the
            # bar would otherwise carry the name until a later dispatch
            # replaced it (`note_dispatch` in services/streaming_response.py).
            note_dispatch(None, local=True)
            logger.error(f"[LLM-CLIENT] Chat failed ({model}): {_said(e)}")
            return None

    def _generate(self, model: str, prompt: str,
                  temperature: float = 0.7, max_new_tokens: Optional[int] = None,
                  repetition_penalty: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Raw completion: the prompt goes to the model as it is, no chat
        template, the way the safety check (Llama Guard), the age check and
        the two context translations of schema_pipeline_routes (Nr. 121)
        are written. The pipeline engine's prompts, the translation chunk
        among them, go through `chat` since 2026-09-16 (one user message
        through the template; prompt_interception_engine._call_local_llm)."""
        try:
            workflow = self._workflow(model, prompt=prompt, temperature=temperature,
                                      repetition_penalty=repetition_penalty)
            note_dispatch(model, local=True)
            answer = self._answer(self._run(workflow))
            return {
                "response": answer["content"],
                "thinking": answer["thinking"],
                "finish_reason": answer["finish_reason"],
            }
        except Exception as e:
            note_dispatch(None, local=True)      # at nothing now; see `_chat`
            logger.error(f"[LLM-CLIENT] Generate failed ({model}): {_said(e)}")
            return None

    def chat_stream(self, model: str, messages: list, images: Optional[List[str]] = None,
                    temperature: float = 0.7, max_new_tokens: Optional[int] = None,
                    repetition_penalty: Optional[float] = None,
                    on_connection: Optional[Callable[[Callable[[], None]], None]] = None,
                    enable_thinking: bool = True):
        """Chat, handed on while it is written.

        `enable_thinking` as in `chat`: False and the model answers without
        reasoning first, where its chat template has the switch.

        Yields ("token", str) for every piece the node publishes on the
        websocket (the answer outside its think block), ("done", reason) as
        the last item of a generation that ended by itself ("stop", "length"
        -- the context ceiling -- or "repetition"), and ("error", str) when
        it broke off, which can happen after part of the answer has already
        been handed out, so the caller keeps what it has and says what went
        wrong.

        `on_connection` is called ONCE, with a zero-argument callable that
        ends this run, as soon as ComfyUI has taken the prompt. It exists
        because a caller cannot end this reading through the generator:
        `close()` on a generator that is EXECUTING raises, and this one is
        executing for the whole of every gap in which a model writes nothing.
        The callable interrupts the run at ComfyUI (cancel_job), the tracking
        raises, and that comes back out of here as ("error", ...).

        A reader that leaves between two pieces -- `close()` on this
        generator while it waits, or an exception in the reading loop -- ends
        the run the same way: the prompt is interrupted at ComfyUI, or taken
        out of its queue when it is not yet known, once it is.
        """
        try:
            workflow = self._workflow(model, messages=messages, images=images,
                                      temperature=temperature, repetition_penalty=repetition_penalty,
                                      stream=True, enable_thinking=enable_thinking)
        except Exception as e:
            # An unknown or uninstalled model (LookupError), or a table that
            # could not be read: said the same way, as this stream's error.
            logger.error(f"[LLM-CLIENT] Chat stream failed ({model}): {_said(e)}")
            yield ("error", _said(e))
            return

        events: "queue.Queue" = queue.Queue()
        # Set by the callable handed out below, in whichever thread calls it.
        # A tracking that breaks off after the run was interrupted on purpose
        # is no failure, and is logged as what it is.
        ended_by_caller = False
        # The prompt's id once ComfyUI has it (the "submitted" event), and
        # whether the reader left while the run stood: whichever of the two
        # comes second ends the run.
        submitted: List[str] = []
        abandoned = False
        # True once the run thread has handed over its result or its failure;
        # after that there is nothing at ComfyUI left to end.
        finished = False

        def cancel(prompt_id: str) -> None:
            # On a thread of its own: the caller may end the run from inside
            # the "submitted" callback, on the tracking loop's thread (a
            # reader that had already left when the prompt was taken), where
            # asyncio.run would refuse to start a second loop.
            threading.Thread(target=_cancel_at_comfyui, args=(prompt_id,),
                             name=f"llm-cancel-{prompt_id[:8]}", daemon=True).start()

        def on_event(kind: str, data: dict):
            if kind == TOKEN_EVENT:
                piece = data.get("text") or ""
                if piece:
                    events.put(("token", piece))

        def on_progress(ev):
            # The client reports the prompt id first thing, as a "submitted"
            # event; from then on the run can be ended by name.
            if getattr(ev, "event_type", None) != "submitted":
                return
            prompt_id = ev.prompt_id
            submitted.append(prompt_id)
            if abandoned:
                cancel(prompt_id)
                return
            if on_connection is not None:
                def end_it():
                    nonlocal ended_by_caller
                    ended_by_caller = True
                    cancel(prompt_id)

                on_connection(end_it)

        note_dispatch(model, local=True)
        ctx = self._context()
        streamed: List[str] = []

        def run():
            try:
                events.put(("result", self._track(workflow, on_progress=on_progress, on_event=on_event)))
            except BaseException as e:      # handed to the reading side below
                events.put(("failure", e))

        # shutdown(wait=False) at the end: a caller that stops reading while
        # the model still writes closes this generator, and the thread must
        # not hold that caller until the run is over -- the caller's own
        # `end_it` is what ends the run.
        pool = ThreadPoolExecutor(max_workers=1)
        pool.submit(ctx.run, run)
        try:
            while True:
                kind, payload = events.get()
                if kind != "token":
                    finished = True
                if kind == "token":
                    streamed.append(payload)
                    yield ("token", payload)
                elif kind == "result":
                    try:
                        answer = self._answer(payload)
                    except Exception as e:
                        note_dispatch(None, local=True)
                        logger.error(f"[LLM-CLIENT] Chat stream failed ({model}): {_said(e)}")
                        yield ("error", _said(e))
                        return
                    # The answer off the history is the whole of it; the
                    # pieces are what the socket carried. A piece the socket
                    # missed is handed out now, so what the reader holds at
                    # "done" is the answer and never less.
                    missing = _rest_of(answer["content"], "".join(streamed))
                    if missing is None:
                        note_dispatch(None, local=True)
                        reason = (f"the socket carried {sum(len(p) for p in streamed)} characters "
                                  f"of an answer of {len(answer['content'])}, and they are not "
                                  f"its beginning; the answer is whole in the run's history")
                        logger.error(f"[LLM-CLIENT] Chat stream failed ({model}): {reason}")
                        yield ("error", reason)
                        return
                    if missing:
                        yield ("token", missing)
                    yield ("done", answer["finish_reason"])
                    return
                else:
                    e = payload
                    if ended_by_caller:
                        # Asked for, so not a failure: the caller ended this
                        # run and the tracking broke off because of that.
                        # What it raised stays in the line, because the day
                        # it is something else this is where it will be read.
                        reason = "the caller ended this connection"
                        logger.info(f"[LLM-CLIENT] Chat stream for {model} ended by "
                                    f"the caller; the tracking came back with: {e}")
                    else:
                        note_dispatch(None, local=True)  # at nothing now; see `_chat`
                        reason = _said(e)
                        logger.error(f"[LLM-CLIENT] Chat stream failed ({model}): {reason}")
                    yield ("error", reason)
                    return
        finally:
            if not finished:
                # The reader left while the model wrote (close() on this
                # generator, or an exception in the reading loop): the run
                # is ended at ComfyUI now, or as soon as its id is known.
                abandoned = True
                if submitted:
                    cancel(submitted[0])
            pool.shutdown(wait=False)

    def vlm_models(self) -> Optional[List[Dict[str, Any]]]:
        """The models that read images, off the table, each with whether it
        is installed and which station serves it ("backend").

        None means the question could not be put -- here, the table is
        unreadable -- while an empty list means it holds no such model.
        Folding the two together turns a missing table into a gap in the
        offering.
        """
        try:
            return local_llm_weights.vision_models()
        except Exception as e:
            logger.warning(f"[LLM-CLIENT] VLM model list unavailable: {e}")
            return None

    # =========================================================================
    # Public API (unchanged signatures for all callers)
    # =========================================================================

    def chat(self, model: str, messages: list, images: Optional[list] = None,
             temperature: float = 0.7, max_new_tokens: Optional[int] = None,
             keep_alive: str = "10m",
             repetition_penalty: Optional[float] = None,
             enable_thinking: bool = True,
             tools: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """Messages-based chat.

        Returns {"content": str, "thinking": str|None, "tool_calls": None,
        "finish_reason": str} or None on failure.

        `enable_thinking` reaches the node and, through it, the model's chat
        template: False closes the think block in the prompt where the
        template has the switch (Qwen 3, 3.5, 3.8, SmolLM3: an empty, closed
        think block at the end of the prompt), and the model answers without
        reasoning first; a template without the switch ignores it. From
        10a6dac2 (28.03.2026) to 16.09.2026 the flag was dropped here, and on
        the node every reasoning model thought on every call, the safety
        verdict and the System Prompts comparison included.

        Note: keep_alive, tools and max_new_tokens are accepted for
        backward compatibility and ignored: the node holds no model past
        ComfyUI's own management, takes no tools, sets no cap and waits
        without a ceiling.
        """
        return self._chat(model, messages, images, temperature, max_new_tokens,
                          repetition_penalty, enable_thinking=enable_thinking)

    def generate(self, model: str, prompt: str,
                 temperature: float = 0.7, max_new_tokens: Optional[int] = None,
                 keep_alive: str = "10m",
                 repetition_penalty: Optional[float] = None,
                 enable_thinking: bool = True) -> Optional[Dict[str, Any]]:
        """Raw prompt generation.

        Returns {"response": str, "thinking": str|None, "finish_reason": str}
        or None on failure.

        Note: keep_alive and max_new_tokens are accepted for backward
        compatibility and ignored (see `chat`); so is enable_thinking here,
        because a raw prompt passes through no chat template and there is no
        think block for the flag to close -- a caller that wants no reasoning
        on a raw prompt writes that into the prompt itself.
        """
        return self._generate(model, prompt, temperature, max_new_tokens,
                              repetition_penalty)


def node_failure_status(e: BaseException) -> int:
    """The HTTP status a route answers with when run_node(_files) raised:
    the status that says which side failed. 503 while the card is held
    (GpuBusyError), while ComfyUI is out of reach (a submit that got no
    answer), or when the node refused the run for room on the card ("out of
    memory", the words _card's refusal opens with); 400 where ComfyUI refused
    the workflow (an input it would not take); 413 where ComfyUI refused a
    file as too large; 502 for any other refusal; 500 for a run that started
    and broke off."""
    from my_app.services.comfyui_ws_client import ComfyUISubmitError, ComfyUIUploadError
    from my_app.services.gpu_lease_client import GpuBusyError
    if isinstance(e, GpuBusyError):
        return 503
    if isinstance(e, ComfyUIUploadError):
        return 413 if e.status == 413 else 503 if e.status == 0 else 502
    if isinstance(e, ComfyUISubmitError):
        return 503 if e.status == 0 else 400 if e.status == 400 else 502
    if "out of memory" in (str(e) or "").lower():
        return 503
    return 500
