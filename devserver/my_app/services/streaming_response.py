"""
Streaming response utilities to prevent Cloudflare timeouts.

The edge in front of this server ends any proxied request whose origin has sent
no byte for about 100 seconds and hands the browser a 524. The work behind the
long routes here runs on regardless: it finishes, it saves what it made, and its
answer is thrown away. So a long answer travels as a stream that keeps
breathing, and the payload a plain POST would have returned arrives in the
terminal frame.

That transport is held in ONE place for every route that needs it, and it comes
in two shapes because the work does: `streamed_answer` for work that RETURNS a
result, `events_with_heartbeat` for work that YIELDS its events as it goes. Both
are `_pumped` — one thread under a copied context, a frame before the first wait
and every two seconds after it, and a run that carries on when the reader leaves.
What separates them is what an ENDING means: the answer shape writes it into a
terminal frame with an HTTP status beside it, the event shape raises it, because
the route above that one already turns an exception into an event of its own and
the order of what it has already written has to hold.

They stood in two files until 2026-09-04, when `services/streaming_events.py`
held the event shape — two files for one transport, on the day this platform
reduced four copies of its stream handling to one.

"""
import contextvars
import functools
import inspect
import json
import threading
import time
import logging
import queue
from typing import (Any, Callable, Iterable, Iterator, Optional, Tuple,
                    Union)
from flask import (Response, current_app, has_app_context, jsonify, request,
                   stream_with_context)

logger = logging.getLogger(__name__)


# The two words a caller writes into its body to ask for its answer as a
# stream. They say how the answer is to come back from HERE and nothing else,
# so a route that FORWARDS a body strips them first -- see
# `without_transport_flags`. On this platform "enable_streaming" already names
# two different protocols depending on which route reads it, which is why the
# second word exists at all: /pipeline/interception keeps the first for its
# older Stage-1-and-2 event protocol and reads the second for this transport.
#
# They live here because this module writes the frames `services/directRun.ts`
# reads, and these two words are what that same file writes back -- one
# handshake, one place. Two identical copies stood in the Crossmodal Lab and
# Fusion Workbench proxies until 2026-09-05.
STREAM_FLAG = 'enable_streaming'
ANSWER_STREAM_FLAG = 'enable_answer_streaming'
TRANSPORT_FLAGS = (STREAM_FLAG, ANSWER_STREAM_FLAG)


def without_transport_flags(data: dict) -> dict:
    """`data` without the words that asked for the stream.

    A proxy forwards what its caller sent. These two are no part of that: the
    station behind the proxy is asked for one generation either way, and a flag
    that travels on is a flag some station will one day read as its own.
    """
    return {k: v for k, v in data.items() if k not in TRANSPORT_FLAGS}


def asks_for_the_stream(data: Any,
                        flag: Union[str, Tuple[str, ...]] = TRANSPORT_FLAGS
                        ) -> bool:
    """Whether this body asked for its answer as a stream.

    EITHER word opens it, and a caller that wrote only
    `enable_answer_streaming` -- the newer and the more specific of the two,
    and the one a reader of services/directRun.ts would copy -- was handed the
    plain unprotected body by fourteen of the fifteen sites that read this:
    thirteen `answered_either_way` gates and the two routes that read this
    predicate on its own. The fifteenth is the interception route below.

    THREE protocols answer to these words on this platform, and only the first
    is the one this module carries:

      * this shared answer transport, whose terminal frame is `complete` with
        `{http_status, body}` -- every `answered_either_way` route;
      * /pipeline/interception's Stage-1-and-2 EVENT protocol, which reads the
        older word over GET to an EventSource and writes `connected`,
        `stage_start`, `chunk` and a `complete` of its own with no status in
        it;
      * /pipeline/generate/stream's GENERATION event protocol, which also
        reads the older word and whose `complete` carries `{status,
        media_output, run_id, loras, was_translated}`.

    Both of the other two are opened by the OLDER word alone, and each of
    those two routes refuses the newer word by name rather than answering a
    caller in a shape it did not ask for.

    `postStreamedRun` writes both words, so no caller was losing its stream on
    2026-09-05. What stood there was a protection that depended on picking the
    right synonym, on a server whose whole exposure is that a long answer
    without the stream is thrown away by the edge.

    `flag` narrows this back to ONE word where a word means something else:
    /pipeline/interception passes ANSWER_STREAM_FLAG, because there
    `enable_streaming` names its older Stage-1-and-2 event protocol -- a
    different stream, over GET, with no terminal frame -- and opening THIS one
    for it would answer a caller in a shape it did not ask for.

    A body that is not an object asked for nothing. Refusing it is the route's
    business and not this predicate's, which would otherwise turn a caller's
    mistake into a plain answer nobody named -- `object_body` below is where
    that refusal is written, once.
    """
    if not isinstance(data, dict):
        return False
    words = (flag,) if isinstance(flag, str) else flag
    return any(said_yes(data.get(word)) for word in words)


def said_yes(value: Any) -> bool:
    """Whether a body wrote YES here, read strictly.

    `bool(value)` was the test until 2026-09-05, and `bool("false")` is True:
    a caller writing `"enable_answer_streaming": "false"` -- the shape a hand-
    written curl and a query string copied into a JSON body both produce --
    opened the very transport it had just declined, and so did `"no"`, `2` and
    `[0]`. A flag nobody can spell NO in is not a flag.

    Three spellings say yes: the JSON `true`, the number 1, and the string
    "true" in any case, which is what `request.args.get(...) == 'true'` already
    reads on the GET arms of this platform. Everything else is a no -- every
    other string, every other number, and every object -- because a value this
    predicate cannot read is not a request for a transport, and the safe answer
    to an unreadable request is the plain body the route has always had.

    Read by `asks_for_the_stream` above and by the two gates in
    my_app/routes/schema_pipeline_routes.py that read a word straight out of
    their body, so the platform holds ONE reading of these words rather than
    one per site.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() == 'true'
    return False


NOT_AN_OBJECT = "the request body must be a JSON object"


def object_body(silent: bool = False, envelope: Optional[dict] = None):
    """The request body as an object, or the refusal a caller has earned.

    Returns ``(data, None)`` or ``(None, (payload, http_status))``.

    This lives beside the flag because the same change made it necessary. Work
    on this transport runs on a thread that cannot reach `request`, so every
    route reads its body at the boundary and passes it down -- which moved the
    dict operations out of the runs' own `try`. A body that is no JSON OBJECT --
    `"hello"`, `[1, 2]` -- then reached `.items()` or `.get()` and came back as
    an HTML 500 page or a 500 carrying an AttributeError: a fault of this server,
    named where a caller's mistake stands.

    `envelope` is the shape the calling surface reads a refusal in: the two GPU
    proxies answer `{"success": False, ...}` because their pages branch on that
    field, and the media readings answer with `error` alone. `silent` is passed
    through to Flask -- without it a body that is not JSON at all is Flask's own
    400, which is the answer those routes have always given.
    """
    data = request.get_json(silent=silent) or {}
    if isinstance(data, dict):
        return data, None
    payload = dict(envelope or {})
    payload['error'] = NOT_AN_OBJECT
    return None, (payload, 400)


# Whether the code running now is the WORK this module carries, rather than the
# thread that serves the request.
#
# A contextvar and not a thread-local, because the work inherits a COPY of the
# request thread's context (`contextvars.copy_context` in `_pumped`) and a mark
# set inside that copy travels wherever the copy goes -- including into a
# `contextvars.copy_context().run(...)` the work starts for itself.
#
# It is NOT carried into a plain `threading.Thread` the work starts: such a
# thread begins with an empty context and reads the default, False. The
# fail-safe still holds there, and by the other half of the same rule --
# `has_request_context()` is False on a bare thread, which is the case the
# resolver already answered with the strictest level before this mark existed.
# What the mark adds is the ONE case that half cannot see: a worker of this
# transport, where the copied context keeps the request context alive.
_off_the_request_thread: contextvars.ContextVar = contextvars.ContextVar(
    'ai4artsed_off_the_request_thread', default=False)


def runs_off_the_request_thread() -> bool:
    """True where this call is NOT on the thread that serves the request.

    Read by my_app/services/safety_level_resolver.py, which owes the STRICTEST
    level anywhere it cannot see the session it is meant to read. That resolver
    told the two apart with `has_request_context()` alone, and this transport
    ended that: the work runs under a copy of the request thread's context, so
    `_cv_request` is live on the worker -- and stays live after the real request
    context has been torn down. The guard read True, the warning never fired,
    and a worker asking for the level got the installation setting where the
    module's own text promised the strictest one. Measured on 2026-09-05 with
    the installation set to the open level and no course pinned: a bare daemon
    thread answered `kids` with a warning, the worker here answered `open`,
    silently.
    """
    return _off_the_request_thread.get()


def _asks_for_the_leaving_signal(work: Callable) -> bool:
    """Whether `work` named the leaving signal -- and a refusal where it cannot say.

    The signal is opted into by DECLARING a `client_gone` parameter, so the
    opt-in is worth exactly as much as the signature this transport gets to
    read. A site handing over `lambda: run(data)` hands over a signature with no
    parameters in it: the answer is False, it is False for every lambda ever
    written here, and it would stay False on the day `run` grew the parameter.
    All seven routes converted on 2026-09-04 were written that way, which put
    the opt-in out of reach of every one of them, silently.

    So sites hand the work over WITH ITS ARGUMENTS -- `streamed_answer(run,
    data, label=...)`, or `functools.partial(run, data)`, whose signature
    `inspect.signature` resolves down to the parameters still open. Both
    spellings keep the declaration readable.

    A lambda is not refused outright, because a lambda that IS the work hides
    nothing: `lambda: ({'ok': True}, 200)` wraps no declaration. What is refused
    is the trap itself -- a lambda whose body reaches for something that DOES
    declare `client_gone` -- and `_a_declaration_this_lambda_hides` below is what
    looks. So the opt-in can no longer be lost quietly: either the transport
    reads it, or the site is told, by name, what it buried.

    Raised at CALL time and not at the first frame: by then the route has handed
    Flask a 200, and the client would read a torn body in place of a fault.
    """
    try:
        parameters = inspect.signature(work).parameters
    except (TypeError, ValueError) as e:
        raise TypeError(
            "the work handed to this transport has no signature to read "
            f"({e}); hand over a function, or functools.partial(function, *args)"
        ) from e
    if 'client_gone' in parameters:
        return True
    hidden = _a_declaration_this_lambda_hides(work)
    if hidden:
        raise TypeError(
            f"this lambda hides {hidden}, which asks for the leaving signal by "
            "declaring `client_gone` -- the lambda's own signature does not, so "
            "the signal would never be handed on. Pass the work with its "
            "arguments instead: streamed_answer(run, *args), or "
            "functools.partial(run, *args)."
        )
    return False


def _a_declaration_this_lambda_hides(work) -> str:
    """The name of a function a lambda reaches for that DOES declare the signal.

    Empty where `work` is no lambda, or where nothing it names declares it.

    Read out of the lambda's own code object: the global names it references and
    what its closure cells hold. Deliberately narrow -- a call reached through an
    attribute, or a callable built while the lambda runs, is not seen here. It
    catches the shape that actually happened on 2026-09-04, `lambda: run(data)`
    at seven sites, and the static guard in tests/test_sse_transport_answer_sites
    .py is the other half: no route may hand this transport a lambda at all.
    """
    if not (inspect.isfunction(work) and work.__name__ == '<lambda>'):
        return ''
    reachable = [(name, work.__globals__.get(name))
                 for name in work.__code__.co_names]
    for name, cell in zip(work.__code__.co_freevars, work.__closure__ or ()):
        try:
            reachable.append((name, cell.cell_contents))
        except ValueError:
            # A cell not yet filled -- a recursive closure being built. Nothing
            # to read, and nothing to say about it.
            continue
    for name, candidate in reachable:
        if not callable(candidate):
            continue
        try:
            if 'client_gone' in inspect.signature(candidate).parameters:
                return name
        except (TypeError, ValueError):
            continue
    return ''


class UnwritableEvent(Exception):
    """An event the caller's `frame` could not put on the wire.

    A fault of its own, and that is the whole reason it exists. The `finally`
    in `events_with_heartbeat` ends the pumped loop, and ending the loop is
    what tells the source that its reader has gone -- so a `frame` that raised
    used to arrive at the source as a DEPARTURE. It is not one: the client is
    still there, still reading, and the canvas run stream and its reconnect
    twin write their frames with `json.dumps` over a record, which is a thing
    that can fail on its own. Carried out of here under its own name, it
    reaches the route as the fault it is, and the tail behind it is left alone.
    """


def generate_sse_event(event_type: str, data: dict) -> str:
    """
    Generate Server-Sent Events (SSE) formatted message

    Args:
        event_type: Event type (e.g., 'connected', 'chunk', 'complete', 'blocked', 'error')
        data: Event data dictionary

    Returns:
        SSE-formatted string
    """
    return f"event: {event_type}\ndata: {_json_body(data)}\n\n"


# ---------------------------------------------------------------------------
# WHICH MODEL A RUN IS AT, WRITTEN ON THE CONNECTION THAT RUN ALREADY HOLDS
# ---------------------------------------------------------------------------
#
# The device waiting for this answer is the device the answer belongs to, so
# nothing has to be looked up and nothing has to be held plant-wide: the name
# travels back the way the picture does. A register of what runs where, asked
# by the browser once a second, stood on this platform from 2026-09-07 to
# 2026-09-09 and was removed (5d7d6688).
#
# The holder is a MUTABLE OBJECT, put into the contextvar on the request thread
# before the work starts. `contextvars.copy_context()` copies the REFERENCE, so
# the worker writes into the same object the heartbeat out here reads -- a
# value a worker sets in a contextvar of its own is invisible from the request
# thread, which is the trap this shape exists to avoid.
#
# Nothing is added to the wire that was not going out already: the two-second
# beat is written either way, and where there is news it is written as a frame
# carrying the name instead of as a comment carrying nothing.

class RunPlace:
    """What this ONE request has last sent a model, and whether it ran here."""

    def __init__(self):
        self._lock = threading.Lock()
        self._at = None    # (model, local), or None while nothing has run

    def note(self, model: Optional[str], local: bool) -> None:
        with self._lock:
            if model:
                self._at = (model, local)
            elif self._at is not None:
                # A dispatch that failed, or one that named no model. The run
                # is at nothing now and SAYS so on the next beat, because the
                # page keeps what it was last told: the name of a call that
                # came back empty stood in the bar until a later dispatch
                # replaced it or the run ended. A run that has never reached a
                # model has nothing to take back and stays quiet.
                self._at = (None, local)

    def at(self):
        """What this run is at, or None while it has reached no model.

        Read on EVERY beat and not only where it changed. A beat writes a byte
        either way, so saying it again costs nothing, and a page that dropped
        the line has it back within one beat. Saying it ONLY on the change made
        the line unrecoverable: this end had said it once and would not say it
        again, so a single wrong clear on the page emptied the bar for the rest
        of a run — and the page has several honest reasons to clear, from a
        second short call on the same surface to its own run ending.
        """
        with self._lock:
            return self._at


_run_place: contextvars.ContextVar = contextvars.ContextVar(
    "ai4artsed_run_place", default=None)


def note_dispatch(model: Optional[str], *, local: bool) -> None:
    """Say what is being sent, from the place that sends it.

    Called by the four clients that reach a model -- `openai_style_stream`,
    `llm_client`, `diffusers_client`, `comfyui_ws_client` -- with the identifier
    THEY put on the wire, never with what a config asked for: the engine can
    send a model other than the one requested, and the platform holds the sent
    one to be the true answer (tests/test_interception_model_choice.py).

    `local` is the part an id cannot say. A repository id carries its PUBLISHER
    in front (`stabilityai/...`), which says nothing about where the picture was
    made, so whoever hands the id over says where it went.

    Outside a streamed request there is no holder and this does nothing. A
    pooled thread can still carry the holder of a stream that has ended; a write
    into it reaches an object nobody reads any more, and the next streamed
    request on that thread installs a fresh one before its first beat.
    """
    place = _run_place.get()
    if place is not None:
        place.note(model, local)


def _under_a_run_place(frames: Iterable[str]) -> Iterator[str]:
    """The frames of ONE stream, with a holder of its own around them.

    The set has to be UNDONE, and that is the whole reason this wrapper exists
    rather than a plain `set` beside the Response. The frames are pumped on a
    POOLED worker thread — waitress keeps sixty-four of them — and a contextvar
    that is only ever set stays on that thread for the life of the process. Two
    consequences were reproduced on 2026-09-09: a later request that reaches a
    model writes its name into the holder of a stream that ended long ago, and
    the next stream on that thread reads it out and opens by naming a model
    nobody on that connection asked for.

    Nested sets are fine and are what the two install sites below do on a route
    that goes through both: a generator shares its caller's context, the inner
    holder shadows the outer for as long as it is open, and the two resets
    happen innermost first.
    """
    token = _run_place.set(RunPlace())
    try:
        yield from frames
    finally:
        _forget_run_place(token)


def _forget_run_place(token) -> None:
    """Put back what the contextvar held before this stream.

    Guarded, because a Token may only be reset in the context it was made in: a
    generator closed from somewhere else would raise here and tear a stream that
    had otherwise finished. Failing to put it back costs one stale holder on one
    pooled thread; raising costs the answer.
    """
    try:
        _run_place.reset(token)
    except ValueError:  # pragma: no cover - a close from another context
        _run_place.set(None)


def _json_body(data: dict) -> str:
    """The frame's JSON, written the way this app writes a JSON body.

    A route under `streamed_answer` answers one question two ways: without the
    streaming flag it returns `jsonify(payload)`, with it that same payload
    travels inside the terminal frame written here. Under a bare `json.dumps`
    the two were the same fields in a different order -- Flask's JSON provider
    sorts keys, `json.dumps` keeps insertion order -- so a recording of one
    transport could not be held against the other.

    So the app's OWN provider writes it, which also brings its `default=`
    handler along: a payload holding a date or a UUID leaves the streamed route
    exactly as it leaves the blocking one, instead of raising inside the
    generator.

    That provider is reachable from BOTH threads this transport runs on. The
    terminal frame is written in the generator, which `stream_with_context`
    runs inside the request's own context; and a source that writes its own
    frames -- the interception route's Wikipedia notices, the image reading's
    pieces -- calls this from the worker, where `_pumped`'s copied context
    keeps the app context alive and `has_app_context()` is True. The note here
    said no frame was written on the worker, which was never true of the event
    shape.

    Where there is no app to ask -- this module under a unit test, or a stream
    built outside a request -- DefaultJSONProvider's own settings are written
    out instead. test_streamed_answer.py holds the two spellings equal, so this
    is one policy written twice rather than two policies.

    `separators` is the compact form `jsonify` uses outside debug mode. It is
    stated because `dumps` alone leaves a space after every comma and colon, and
    a Latent Lab terminal frame carries base64 images.
    """
    if has_app_context():
        return current_app.json.dumps(data, separators=(",", ":"))
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def heartbeat_comment(elapsed: float = 0.0, nth: int = 0) -> str:
    """The byte, and where the run has reached a model, the name of that model.

    The comment goes out on every beat and is what the edge counts as traffic:
    a client reading `data:` frames never sees it, and this transport's whole
    contract is that it keeps arriving. Where the run is AT a model, a
    `model_place` frame rides with it, and goes on riding with it for as long
    as the run is at that model — so the name arrives within a beat of the
    dispatch, rather than with the finished answer, which could only say what
    has RUN and not what is running.

    A frame whose `model` is null says the opposite: this run is at NO model
    any more, which is what a failed dispatch leaves behind. It is sent only
    where a model was named before it, so a run that has reached none says
    nothing at all.

    The frame is written on every beat and not only where it changed. Said
    once, the line could not be recovered: a page has several honest reasons to
    clear it — its own run ending, a second and shorter call on the same
    surface — and this end had already said its piece and would not say it
    again.

    It is written from here because here is the one place every streamed route
    on this platform passes through, and because this is the request thread:
    the holder (`RunPlace`) is shared with the work, so this reads out what the
    work wrote in.

    `elapsed` and `nth` are what `_pumped` hands every heartbeat writer, and
    this one uses neither. They carry defaults so that a loop writing its OWN
    beat -- the generation stream still polls a GPU service by hand -- can say
    `heartbeat_comment()` and take the platform's byte from here instead of
    spelling out a fourth copy of `': heartbeat\\n\\n'`.
    """
    place = _run_place.get()
    if place is not None:
        at = place.at()
        if at is not None:
            model, local = at
            return ': heartbeat\n\n' + generate_sse_event(
                'model_place', {'model': model, 'local': local})
    return ': heartbeat\n\n'


def _complete_event(payload: dict, http_status: int) -> str:
    """The terminal frame: what a plain POST would have handed back.

    Body and status together, so the client can reproduce exactly the answer it
    would have had without the stream.
    """
    return generate_sse_event('complete', {'http_status': http_status, 'body': payload})


def _failure_event(error: BaseException) -> str:
    """The terminal frame of a run that raised, with the real cause in it.

    A message that only says something failed cannot be acted on, and the status
    travels with it for the same reason.
    """
    return generate_sse_event('complete', {
        'http_status': 500,
        # An ending with nothing to say is named by its type instead. Some
        # carry no text at all -- str(MemoryError()) is the empty string -- and
        # an empty message is the one thing this frame exists to prevent.
        'body': {'status': 'error',
                 'error': str(error) or f'the run ended with {type(error).__name__}'},
    })


def _as_reportable(error: BaseException) -> Exception:
    """A worker's ending, in a shape the terminal frame can carry.

    One ending arrives here that the frame could not carry: a BaseException
    that is no Exception -- `SystemExit`, `KeyboardInterrupt`, a cancellation --
    travels straight past the `except Exception` every route above this module
    is written with, and leaves the client a torn stream with no word about
    why. It is named by its TYPE, which is the one thing every ending has, and
    its message is added where it has one.

    An Exception reaches its route AS ITSELF. What it IS is part of what it
    says: a route that answers a `requests.Timeout` differently from anything
    else can do so only while the type survives the trip up. A rule that
    weighed the MESSAGE too handed every Exception with nothing to say to the
    generic handler instead -- `str(MemoryError())` is the empty string, and a
    `requests.Timeout` can be raised with no text at all. An empty message
    makes a poor frame; a changed type makes a wrong answer.
    """
    if isinstance(error, Exception):
        return error
    detail = str(error)
    return Exception(f"the run ended with {type(error).__name__}"
                     + (f": {detail}" if detail else ""))


def _pumped(
    source: Callable[[], Iterable[Any]],
    *,
    label: str,
    interval: float,
    heartbeat: Callable[[float, int], str],
) -> Iterator[Tuple[str, Any]]:
    """The loop both transports in this module are made of, and its only copy.

    `source` is called ON A THREAD OF ITS OWN, and whatever it yields travels to
    this generator through an unbounded queue — so a stretch in which the work
    says nothing (a model that has not written its first token, a GPU slot still
    being waited for) is a stretch in which the caller above is free to write.

    What comes back is a pair. `('beat', text)` is a frame ready for the wire.
    `('item', x)` is one thing the work produced. `('error', e)` is how the work
    ended — and it is the CALLER that says what an ending means, because that is
    the one thing the two transports below answer differently: one writes it
    into a terminal frame with an HTTP status beside it, the other raises it so
    that a route which already turns an exception into an event of its own keeps
    doing exactly that, in the same order.

    A beat goes out BEFORE the first wait, so the connection carries a byte from
    the start rather than from the work's first sign of life.

    THE BEAT IS PRODUCED HERE, on the request thread, by `items.get(timeout=
    interval)` -- so it needs the GIL to come round. Work that holds the GIL
    inside ONE C call breathes not at all while that call runs, and this loop
    cannot tell that apart from work that is merely slow. Measured on
    2026-09-05: a 5.86 s call holding the GIL throughout produced zero frames,
    not even the pre-wait beat, because the beat before it is a `yield` the
    consumer only reaches once the GIL is free. A sleeping stand-in cannot show
    this -- `time.sleep` releases the GIL, which is why every test of this
    cadence passes over it.

    Of the sources on this transport, the one that can reach that length in a
    single C call is the SpaCy pass in the Stage-1 gate: a long text through a
    transformer pipeline is one call into compiled code. It is bounded by the
    length of the text a visitor typed rather than by a model's answer, and it
    is far under the edge's hundred seconds; the model calls behind every other
    source spend their time in socket reads, which release the GIL. So this is
    a limitation to know about rather than an open window -- and where one
    opens, the fix is in the WORK (a release point inside it), not a second
    thread here.

    `interval` is a cadence, not a limit. Nothing here ends the work, and there
    is deliberately NO ceiling on how long it may take: a run under this
    transport can legitimately sit in the plant-wide GPU queue for an hour and a
    half, and a timeout in this loop would end it in exactly the way the whole
    arrangement exists to prevent.

    The work inherits THIS context (`contextvars.copy_context`), which under
    Flask is what carries the request and app context onto the worker thread. A
    thread that started empty would carry no run id and no output config for the
    admission gate to label its work with, and no app context to reach the
    platform's storage through. What a worker must NOT take from here is the
    safety level: the resolver reads the session, so every caller resolves the
    level at the request boundary and passes it into its work — see the
    docstring of my_app/services/safety_level_resolver.py, which was written
    after a whole surface ran a kids course at the installation level.

    A reader that leaves closes this generator; the work runs to its end anyway
    and saves what it made, which is what a Latent Lab image and a chat turn's
    history both depend on. The queue is unbounded on purpose, so a reader that
    stopped reading can never leave the worker blocked on a put with a turn half
    written.

    That is also why the leaving is OFFERED here. On a thread, a closed tab is
    no longer visible at all: before this transport existed the departure
    arrived as a `GeneratorExit` at the source's own `yield`, and for the canvas
    batch and the text proxy that was the only cancellation they had. So a
    source that declares a `client_gone` parameter is handed a
    `threading.Event`, set below when this generator ends however it ends. It is
    an OFFER and never a cancellation: work holding something scarce -- the GPU
    slot, an upstream connection, the runs of a batch nobody is watching -- can
    look at it and stop, while a source that does not name it runs to its end
    exactly as it did before.
    """
    items: "queue.Queue[tuple]" = queue.Queue()
    # Before the copy, so the work shares this stream's holder: see
    # `_under_a_run_place`, which does the same around a whole route's frames.
    # It stands here as well because five streamed routes build their Response
    # themselves and never reach `sse_response` — chat, three canvas runs and
    # the text proxy.
    place_token = _run_place.set(RunPlace())
    ctx = contextvars.copy_context()
    client_gone = threading.Event()
    takes_the_signal = _asks_for_the_leaving_signal(source)

    def _work():
        try:
            # Marked before anything else runs here, and inside the copied
            # context, so everything the work reaches can tell which thread it
            # is on. A safety check that cannot see the session owes the
            # strictest level, and `has_request_context()` cannot tell it that
            # any more -- see `runs_off_the_request_thread` above.
            _off_the_request_thread.set(True)
            for item in (source(client_gone=client_gone) if takes_the_signal
                         else source()):
                items.put(("item", item))
        except BaseException as e:  # noqa: BLE001 - handed to the reader, not swallowed
            # BaseException and not Exception. A cancellation, a MemoryError or
            # an interpreter being torn down is not an Exception, and one of
            # those used to leave the answer shape with nothing at all: it then
            # raised KeyError: 'result' and the terminal frame carried the whole
            # message "'result'", which names nothing anybody can act on. The
            # run failed closed either way — what was missing was the reason.
            # Nothing is re-raised: this thread is ending regardless, and the
            # generator below is what has to say so.
            items.put(("error", e))
        finally:
            items.put(("end", None))

    thread = threading.Thread(target=lambda: ctx.run(_work), daemon=True)
    try:
        try:
            thread.start()
        except BaseException as e:  # noqa: BLE001 - reported, not swallowed
            # The one failure that lands BEFORE the first frame. A process that
            # has run out of threads raises "can't start new thread" right here,
            # inside the generator -- and a route that hands its generator
            # straight to Flask has already sent its 200, so the client would
            # read an empty body, torn, with nothing in it saying why. Passed to
            # the caller as an ending like any other, it becomes that caller's
            # terminal frame or that caller's error event instead.
            logger.error("[%s] The worker thread could not be started: %s",
                         label, e)
            yield ("error", e)
            return

        started = time.time()
        beats = 1
        sent = 0
        yield ("beat", heartbeat(0.0, beats))
        while True:
            try:
                kind, payload = items.get(timeout=interval)
            except queue.Empty:
                beats += 1
                yield ("beat", heartbeat(time.time() - started, beats))
                continue
            if kind == "item":
                sent += 1
                yield ("item", payload)
            elif kind == "error":
                logger.error("[%s] The work raised after %d event(s): %s",
                             label, sent, payload)
                yield ("error", payload)
                return
            else:
                return
    finally:
        # However this generator ends -- drained, abandoned by a closed tab, or
        # torn by the caller raising -- there is no reader from here on.
        client_gone.set()
        _forget_run_place(place_token)


def streamed_answer(
    run: Callable[..., Tuple[dict, int]],
    *args: Any,
    label: str,
    heartbeat: Callable[[float, int], str] = heartbeat_comment,
    result_frame: Callable[[dict, int], str] = _complete_event,
    failure_frame: Callable[[BaseException], str] = _failure_event,
    interval: float = 2.0,
) -> Iterator[str]:
    """One answer, carried by a connection that keeps breathing.

    `run` is the work, and `*args` are its arguments. It must not reach for
    `request` — see the note on the context in `_pumped` — and it returns the
    `(payload, http_status)` the non-streaming route would have returned. The
    arguments travel HERE rather than inside a `lambda` at the call site,
    because a lambda hides the work's signature and with it the one thing this
    transport reads off it; `_asks_for_the_leaving_signal` says what that cost.
    It
    runs on a thread of its own, and while it runs a frame goes out every two
    seconds. That is far inside the ~100 s of silence the edge cuts at, and the
    margin costs a few bytes a minute.

    Nothing is invented here. This is the heartbeat the generation stream and
    the canvas run stream have always sent; what this function does is hold it
    in one place, so a route that needs it imports the loop instead of writing
    another copy of it.

    `heartbeat`, `result_frame` and `failure_frame` write the frames. Their
    defaults are the platform's own format — a comment while the work runs, an
    `event: complete` carrying `{http_status, body}` at the end — which is what
    `services/directRun.ts` reads on the other side. A caller that speaks a
    different wire format passes its own three writers and keeps the loop.

    A work function that declares a `client_gone` parameter is handed a
    `threading.Event` that is set when the stream ends. That is an OFFER and
    never a cancellation: work holding something scarce, the GPU slot above all,
    can look at it and stop instead of running out its timeout for nobody, while
    work that ignores it runs to the end and still saves what it made — which is
    what a Latent Lab run does when a tab is closed mid-image. The event itself
    is `_pumped`'s, so both shapes in this module offer one signal and not two.

    Returns the frames. Most callers want `answered_either_way` below instead:
    it reads the flag, wraps these frames in the Response every streamed route
    on this platform hands back, and answers the same question as one JSON body
    where no stream was asked for. Fourteen routes wrote that block out by hand
    until 2026-09-05, headers included, and a stream whose headers drift is a
    stream nginx buffers. Take the frames raw only where the shape genuinely
    differs.
    """
    # Read HERE, and not inside the generator: a refusal belongs to the site
    # that wrote it, and by the time Flask pulls the first frame that site has
    # already answered 200.
    takes_the_signal = _asks_for_the_leaving_signal(run)
    return _answer_frames(
        run, args, takes_the_signal, label=label, heartbeat=heartbeat,
        result_frame=result_frame, failure_frame=failure_frame,
        interval=interval)


def _answer_frames(run, args, takes_the_signal, *, label, heartbeat,
                   result_frame, failure_frame, interval) -> Iterator[str]:
    """`streamed_answer`'s frames, split off so that its check above raises
    where the caller stands rather than at the first frame."""
    def once(client_gone):
        """The work, as a source that yields exactly once.

        One result is one item, and that is the whole difference in SHAPE
        between this transport and `events_with_heartbeat` below. Everything
        else — the thread, the copied context, the cadence, the frame before the
        first wait, the leaving signal, the run that carries on when the reader
        leaves — is `_pumped`, once.

        The parameter is named so that `_pumped` hands the signal down here.
        Whether `run` itself wants it is `run`'s own business.
        """
        yield (run(*args, client_gone=client_gone) if takes_the_signal
               else run(*args))

    frames = _pumped(once, label=label, interval=interval, heartbeat=heartbeat)
    answered = False
    try:
        try:
            for kind, payload in frames:
                if kind == "beat":
                    yield payload
                elif kind == "item":
                    answered = True
                    result, http_status = payload
                    yield result_frame(result, http_status)
                    yield ''
                else:
                    raise _as_reportable(payload)

            if not answered:
                # The clause above makes this very nearly unreachable, and
                # "very nearly" is why it says what happened rather than
                # falling into a KeyError whose entire message is the name of a
                # dictionary key.
                raise Exception(f"the {label} worker ended without a result "
                                f"and without an error")

        except GeneratorExit:
            # A closed tab. The run keeps going and saves what it made, exactly
            # as it did while the edge was cutting the POST; only the streaming
            # ends here.
            logger.info("[%s] Client disconnected", label)
            raise

        except Exception as e:
            logger.error("[%s] Error: %s", label, e)
            import traceback
            traceback.print_exc()
            yield failure_frame(e)
            yield ''
    finally:
        # Reached on a normal end and on GeneratorExit alike — the latter is
        # what a closed browser tab looks like from here. Ending the pumped loop
        # is what sets the leaving signal; left to the collector that would
        # still happen in CPython, by refcount, and "would still happen" is not
        # a property to hang a GPU lease on.
        frames.close()


def events_with_heartbeat(
    events: Union[Iterable[Any], Callable[..., Iterable[Any]]],
    *,
    label: str,
    frame: Callable[[Any], str],
    heartbeat: Callable[[float, int], str] = heartbeat_comment,
    interval: float = 2.0,
) -> Iterator[str]:
    """Hand on every event of `events` as it occurs, and breathe in between.

    The transport above, for work that arrives as a SEQUENCE. A chat turn hands
    over pieces of an answer as they are written, and a shape that can only let
    something out when its work RETURNS would trade a first byte that comes too
    late for a whole answer that comes at once — which is the thing the
    streaming surfaces were built to stop. A route with one result belongs under
    `streamed_answer`; a route with a stream of events belongs here.

    `events` is the work, in either of two spellings: the events themselves — a
    generator already made, which is what most callers hand over — or the
    FUNCTION that makes them. Handing the function over is what lets a source
    ASK for the leaving signal, by declaring a `client_gone` parameter, exactly
    as work under `streamed_answer` does; `_pumped` holds the one event and
    reads the one signature. A source that names nothing runs as it always has.
    `frame` turns one item into what goes on the wire; `heartbeat` writes the
    frames in between.

    A `frame` that RAISES ends this stream as `UnwritableEvent`, which the
    route above catches like any other failure of its stream — and, unlike
    every other ending here, without telling the source that its reader has
    gone, because it has not.

    What the work raises is raised HERE, after every event it produced before
    the failure has gone out. A route that turns an exception into an event of
    its own therefore keeps doing exactly that, and in the same order. That is
    the one thing this shape decides differently from `streamed_answer`, which
    has a terminal frame to put a failure into and no earlier event whose order
    it would disturb.

    A source needing ARGUMENTS hands them over as `functools.partial`, which
    keeps its signature readable; a `lambda` that wraps the call is refused,
    for the reason `_asks_for_the_leaving_signal` gives, and so is an
    already-made generator whose function declared the signal -- see
    `_a_declaration_this_generator_hides`. Both refusals say the same thing:
    what this transport can hand the signal to is a signature, and a spelling
    that hides one hides the opt-in with it.
    """
    source = _one_source(events)
    # Read HERE, and not inside the generator: a refusal belongs to the site
    # that wrote it, and by the time Flask pulls the first frame that site has
    # already answered 200.
    _asks_for_the_leaving_signal(source)
    return _event_frames(source, label=label, frame=frame, heartbeat=heartbeat,
                         interval=interval)


def _one_source(events):
    """The two spellings of `events`, as the one function `_pumped` calls.

    A generator already made passes through as itself -- unless the function it
    came from declared the leaving signal, which no generator object can hand
    on; that is refused here rather than run without it.
    """
    # Which of the two spellings this is. Not `callable()`: an object that is
    # both callable and iterable -- a Mock above all -- answers yes to it, and
    # is then CALLED, so its `__iter__` never runs and the stream is silently
    # empty instead of being what it was written to be. A function, a method
    # and a generator function are what "the function that makes them" can
    # actually be here; everything else is the events themselves. A
    # `functools.partial` stands with the functions: it is how a source that
    # needs arguments keeps the signature this transport reads.
    if (inspect.isfunction(events) or inspect.ismethod(events)
            or inspect.isgeneratorfunction(events)
            or isinstance(events, functools.partial)):
        return events

    _a_declaration_this_generator_hides(events)

    def already_made():
        """The events themselves, handed on as they are.

        A named function and not a lambda, because a lambda is refused here --
        and this one is no wrapper hiding a declaration: what it closes over is
        a sequence, which has no signature to hide.
        """
        return events

    return already_made


def _a_declaration_this_generator_hides(events) -> None:
    """Refuse a generator whose function DECLARED the leaving signal.

    The same trap `_a_declaration_this_lambda_hides` catches, in the other
    spelling this transport accepts. `events_with_heartbeat(_work())` hands
    over a generator OBJECT, and a generator object has no signature to read:
    `_asks_for_the_leaving_signal` sees `already_made()` below, answers False,
    and would go on answering False on the day `_work` grew the parameter. Five
    sources converted on 2026-09-05 were written that way, and at one of them
    -- the Stage-1 gate -- the work holds a slot in the plant-wide LLM queue
    while it runs, so a reader who left held that slot until the model answered.

    Read off the generator's own code object, which is the one thing an
    already-made generator still carries: `gi_code`, and the argument names at
    the front of its `co_varnames`. So the opt-in can no longer be lost
    quietly -- either the transport reads it, or the site is told what it
    buried.

    Raised at CALL time and not at the first frame: by then the route has
    handed Flask a 200, and the client would read a torn body in place of a
    fault.
    """
    code = getattr(events, 'gi_code', None)
    if code is None:
        return
    declared = code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]
    if 'client_gone' in declared:
        raise TypeError(
            f"this generator was made from {code.co_name}, which asks for the "
            "leaving signal by declaring `client_gone` -- a generator object "
            "has no signature, so the signal would never be handed on. Pass "
            f"the FUNCTION instead: events_with_heartbeat({code.co_name}, "
            "...), or functools.partial with its arguments."
        )


def _event_frames(source, *, label, frame, heartbeat, interval) -> Iterator[str]:
    """`events_with_heartbeat`'s frames, split off for the same reason
    `_answer_frames` is: so that the check above raises where the caller
    stands rather than at the first frame."""
    frames = _pumped(source, label=label, interval=interval, heartbeat=heartbeat)
    unwritable = False
    try:
        for kind, payload in frames:
            if kind == "beat":
                yield payload
            elif kind == "item":
                try:
                    written = frame(payload)
                except Exception as e:
                    # Not a departure, and it must not be reported as one: the
                    # `finally` below ends the pumped loop, and ending the loop
                    # sets the leaving signal, which would cut a tail whose
                    # reader is still at the other end reading. The fault goes
                    # up under its own name instead, for the route above to
                    # turn into its own error event -- swallowing it would
                    # leave an event that never reached the wire unmentioned.
                    unwritable = True
                    logger.error("[%s] An event could not be written to the "
                                 "wire: %s", label, e)
                    raise UnwritableEvent(
                        f"the {label} stream could not write an event: {e}"
                    ) from e
                yield written
            else:
                # Normalised the way the answer shape normalises it. Raised raw,
                # a SystemExit or a KeyboardInterrupt travels straight past the
                # `except Exception` every route above this one is written with,
                # and the stream tears with no terminal frame in it at all.
                raise _as_reportable(payload)
    finally:
        # Same reason as in `streamed_answer`: this is what ends the pumped
        # loop, and ending it is what tells a source that the reader has gone.
        # Left undone for exactly one ending -- an event the caller could not
        # write -- because there the reader has NOT gone.
        if not unwritable:
            frames.close()


def sse_response(frames: Iterable[str]) -> Response:
    """The Response every streamed route on this platform hands back.

    `stream_with_context` holds the request context open around the generator,
    which is what lets the terminal frame be written with this app's own JSON
    provider (see `_json_body`). The two headers are no decoration: nginx
    buffers a proxied response by default, and a buffered stream is an origin
    that has sent nothing — which is the 524 this whole transport exists to
    prevent, reinstated at the last hop. `Cache-Control` says the same to
    anything else on the way.

    A `RunPlace` of this stream's own goes round the frames here, and a second
    one goes round the pumped loop in `_pumped`: between them they cover both
    shapes of streamed route on this platform, the ones that hand their frames
    to this function and the five that build a Response of their own. Either
    wrapper is on the REQUEST THREAD, so the `contextvars.copy_context()` in
    `_pumped` copies the reference onto the worker. See `note_dispatch`.
    """
    return Response(
        stream_with_context(_under_a_run_place(frames)),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


def answered_either_way(data: Any, run: Callable[..., Tuple[dict, int]],
                        *args: Any, label: str,
                        flag: Union[str, Tuple[str, ...]] = TRANSPORT_FLAGS,
                        **frame_writers):
    """One question, answered the way its caller asked for it.

    `data` is the body the flag is read from; `run` and `*args` are the work,
    which returns the `(payload, http_status)` both ways back are made of. With
    the flag the answer travels as this platform's SSE stream, without it as the
    one JSON body it always was — and it is the SAME work either way, which is
    the whole contract the transport tests hold each route to.

    This block stood written out at fourteen sites on 2026-09-05, headers
    included. One of them differed: /pipeline/safety/quick guards its blocking
    branch with a `try` of its own, so that both ways back refuse alike, and it
    therefore keeps its own gate and takes only `sse_response` from here.

    Either word opens the stream -- see `asks_for_the_stream`. `flag` narrows
    that to one word for the one route where the older word means something
    else (/pipeline/interception, which passes ANSWER_STREAM_FLAG).
    `**frame_writers` go on to `streamed_answer`: `failure_frame` above all,
    where a route's refusal has a shape of its own.
    """
    if asks_for_the_stream(data, flag):
        return sse_response(
            streamed_answer(run, *args, label=label, **frame_writers))

    payload, http_status = run(*args)
    return jsonify(payload), http_status

