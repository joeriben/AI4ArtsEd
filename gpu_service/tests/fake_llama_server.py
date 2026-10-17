#!/usr/bin/env python3
"""
A stand-in for llama-server, spawned as a real child by the tests.

Not a mock object: the supervisor's whole job is process work — a pipe that
fills, a PID that vanishes, a port that is taken, a socket the client closes
mid-answer — and none of that exists in a patched function. So this is a real
process with a real HTTP server, and the tests drive it through the same
supervisor the service uses.

It accepts llama-server's own command line (build_argv produces it) and reads
only --port, --alias and --mmproj from it; everything else is tolerated and
ignored. WHAT it does is chosen by environment, which the child inherits from
the test:

  FAKE_LLAMA_MODE            ready (default) | never_silent | never_chatty
                             | never_dots | bind_error | exit | noisy
  FAKE_LLAMA_HEALTH_DELAY_S  seconds of 503 before /health turns 200
  FAKE_LLAMA_EXIT_CODE       exit code for mode "exit"
  FAKE_LLAMA_BIND_FAIL_PORT  fail with a bind complaint on exactly this port
  FAKE_LLAMA_NO_VISION_LINE  never print the compute-buffer line, even with --mmproj
  FAKE_LLAMA_VISION_LINE_DELAY_S  print it this many seconds after /health turns 200
  FAKE_LLAMA_STATUS          answer both inference endpoints with this status
  FAKE_LLAMA_CHAT            which /v1/chat/completions script to play
  FAKE_LLAMA_COMPLETION      which /completion script to play
  FAKE_LLAMA_IGNORE_SIGTERM  ignore SIGTERM, so the supervisor has to escalate
  FAKE_LLAMA_WORK_LINE       index into WORK_LINES: the one work line the
                             "prefill" script writes (all of them by default)
  FAKE_LLAMA_TICK            run the /slots decode counter while a request is
                             in flight (a child that is working, whether or not
                             anybody is reading its answer)
  FAKE_LLAMA_CHAT_FAIL_FIRST answer the FIRST chat request with 500 and every
                             one after it normally — a child that was not ready
                             for its first image and is for the second
  FAKE_LLAMA_IMAGE_MARK      a file to append to whenever a request carries an
                             image. A test turns "the encoder has been fed" into
                             the bigger NVML figure a real card reports from
                             that moment on, which is the whole subject of the
                             load-time warm-up.

Three of those are switchable at runtime through GET /control, because a test
that needs a LOADED child to behave differently cannot reach into the
environment it was spawned with: chat, completion, status, and — for the
progress bound — tick, decoded and slots_hang (a /slots that never answers,
which is what a wedged main task loop looks like from outside).

Two kinds of script live here and the difference matters. Most of them are
shapes THIS build actually produces, and a test against one of those says what
the platform will meet. A few — an `event: error` frame, an empty `choices`
array, one JSON object split across two `data:` lines — this build does not
produce today; they are marked DEFENSIVE where they stand, and the tests using
them pin the parser against the SSE grammar rather than against llama.cpp.

It also records what it was sent (GET /last-request) and what happened to the
connection (GET /stats, GET /slots), because "the client hung up and the slot
went idle" is an assertion about the child, not about the caller.

Model identifiers never appear here. The tests register synthetic aliases.
"""

import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {
    "ready_at": 0.0,
    "alias": "",
    "port": 0,
    "mmproj": "",
    "model_path": "",
    "n_ctx": 0,
    "last_request": None,
    "last_path": "",
    "requests": 0,
    "disconnects": 0,
    "processing": False,
    # Switchable while the child runs (GET /control?chat=...&completion=...&
    # status=...). The environment only seeds them: a test that wants a LOADED
    # child to behave differently cannot reach into an environment the child
    # inherited at spawn.
    "chat": "plain",
    "completion": "plain",
    "status": "",
    # Which non-streaming yes/no answer the classification path gets. It is a
    # different endpoint shape, not a different script: the score is read off
    # the logprobs of the first generated position, and those arrive in a JSON
    # body, never as an event.
    "verdict": "no",
    # What /slots reports, and whether it reports at all. The real server
    # answers /slots out of its main task loop, so a wedged loop cannot answer
    # it; "slots_hang" is how that silence is played back here. "tick" runs the
    # decode counter while a request is in flight, which is what a server that
    # is working looks like from outside, with or without a reader.
    "decoded": 0,
    "tick": 0,
    "slots_hang": 0,
    # Requests that handed the model a picture. Counted separately from
    # "requests": the warm-up's whole claim is that an IMAGE reached the child
    # before the load let go of its reservation.
    "images": 0,
    # Chat requests refused by FAKE_LLAMA_CHAT_FAIL_FIRST.
    "chat_failures": 0,
}

LOOP_SENTENCE = "This is a repeated sentence that is long enough. "

# The lines THIS build writes while it is feeding the model, copied from its
# source rather than from the engine's markers: a typo on the engine's side has
# to fail a test, and it cannot if both sides read from the same string.
# llama.cpp 59d8402 — tools/server/server-context.cpp:2605 and :2581,
# tools/mtmd/mtmd-helper.cpp:358, :367, :287 and :297.
WORK_LINES = [
    "slot update_slots: id  0 | task 0 | prompt processing progress, "
    "n_tokens = 512, batch.n_tokens = 512, progress = 0.250000",
    "slot update_slots: id  0 | task 0 | prompt processing done, "
    "n_tokens = 2048, batch.n_tokens = 512",
    "encoding image slice...",
    "image slice encoded in 137 ms",
    "decoding image batch 1/3, n_tokens_batch = 256",
    "image decoded (batch 1/3) in 312 ms",
]


def carries_an_image(body) -> bool:
    """True when this request hands the model a picture.

    The shape is the OpenAI content-part list, which is what mtmd is fed
    through: a `content` array with an `image_url` part in it.
    """
    if not isinstance(body, dict):
        return False
    for message in body.get("messages") or []:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return True
    return False


def emit(line: str) -> None:
    """A line the way llama-server writes them: stdout, flushed at once."""
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def parse_argv(argv):
    for index, item in enumerate(argv):
        nxt = argv[index + 1] if index + 1 < len(argv) else ""
        if item == "--port":
            STATE["port"] = int(nxt)
        elif item == "--alias":
            STATE["alias"] = nxt
        elif item in ("--mmproj", "-mm"):
            STATE["mmproj"] = nxt
        elif item == "-m":
            STATE["model_path"] = nxt
        elif item == "-c":
            STATE["n_ctx"] = int(nxt)


# =============================================================================
# The scripts. Each yields raw bytes to write, a float to sleep, or "die".
# =============================================================================

def sse(payload) -> bytes:
    # ensure_ascii=False on purpose: llama.cpp writes raw UTF-8, so a character
    # can straddle two TCP writes. Escaped \uXXXX would never produce that.
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")


def delta(content=None, finish=None) -> dict:
    choice = {"index": 0, "delta": ({"content": content} if content is not None else {})}
    if finish is not None:
        choice["finish_reason"] = finish
    return {"id": "x", "object": "chat.completion.chunk", "choices": [choice]}


def opening() -> bytes:
    """The first chunk of every real answer: the role, and a null content."""
    return sse({"id": "x", "object": "chat.completion.chunk",
                "choices": [{"index": 0,
                             "delta": {"role": "assistant", "content": None}}]})


def closing(finish="stop") -> bytes:
    """The last chunk: the finish reason, with the timings beside it."""
    return sse({"id": "x", "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                "timings": {"prompt_n": 7, "predicted_n": 2,
                            "predicted_per_second": 42.0}})


def verdict_body(name):
    """The non-streaming answer of a model asked to write one word.

    llama.cpp puts the logprobs of every generated position in
    choices[0].logprobs.content; content[0] is the first one, which for this
    protocol is the whole answer. The figures below are logprobs of the raw
    softmax over the full vocabulary, which is what the server sends when
    post_sampling_probs is off -- so temperature and repeat penalty cannot
    move them.

    "split" and "preamble" are the two that carry a claim:

    * split      -- the yes side reaches the vocabulary as two spellings.
                    Summed it is 0.446 against 0.301 and the picture is held
                    back; read at the larger single spelling alone it is 0.426
                    against 0.301 and the same answer lets the picture out.
    * preamble   -- the model wrote something that is not an answer, with yes
                    and no far down its tail. Their ratio there is noise, and
                    noise under the threshold is a RELEASE. This is the shape
                    an adversarial review found on 2026-09-23.
    """
    tables = {
        "no": ("no", [("no", -0.01), ("yes", -4.6)]),
        "yes": ("yes", [("yes", -0.02), ("no", -3.9)]),
        "split": ("yes", [("yes", -1.5), ("\u2581Yes", -1.5), ("no", -1.2)]),
        "preamble": ("Sure", [("Sure", -0.1), ("no", -11.5), ("yes", -13.8)]),
        "only_yes": ("yes", [("yes", -0.02), ("maybe", -3.9)]),
        "no_logprobs": ("no", []),
    }
    if name == "no_choices":
        return {"object": "chat.completion", "choices": []}
    token, table = tables[name]
    return {
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": token},
            "finish_reason": "stop",
            "logprobs": {"content": [{
                "token": token,
                "logprob": table[0][1] if table else -0.01,
                "top_logprobs": [{"token": t, "logprob": lp} for t, lp in table],
            }]} if table else {"content": []},
        }],
        "timings": {"prompt_n": 30, "predicted_n": 1},
    }


def chat_script(name):
    if name == "no_done":
        yield sse(delta("Hello"))
        yield sse(delta(" world"))
        yield sse(delta(finish="stop"))
        return
    if name == "empty_choices":
        # DEFENSIVE. This build sends the timings ON the finish chunk and needs
        # stream_options.include_usage — which this platform never sends — to
        # produce an empty choices array at all. Kept because reading choices[0]
        # without looking is an IndexError in the middle of a finished answer.
        yield sse({"id": "x", "choices": [], "timings": {"predicted_ms": 1}})
        yield sse(delta("Hello"))
        yield sse({"id": "x", "choices": [], "timings": {"predicted_ms": 2}})
        yield sse(delta(finish="stop"))
        yield b"data: [DONE]\n\n"
        return
    if name == "finish_with_content":
        # DEFENSIVE. This build closes with a content-free chunk; a chunk that
        # carries both would silently drop its last piece in a reader that takes
        # the finish flag as "nothing more here".
        yield sse(delta("Hello"))
        yield sse(delta(" world", finish="stop"))
        yield b"data: [DONE]\n\n"
        return
    if name == "length":
        yield opening()
        yield sse(delta("as far as it got"))
        yield closing("length")
        yield b"data: [DONE]\n\n"
        return
    if name == "tool_calls":
        yield opening()
        yield sse(delta("done"))
        yield closing("tool_calls")
        yield b"data: [DONE]\n\n"
        return
    if name == "unknown_finish":
        # A finish reason this platform has no reading for. Not produced today;
        # a build that adds one must not have it arrive as a finished answer.
        yield opening()
        yield sse(delta("as far as it got"))
        yield closing("content_filter")
        yield b"data: [DONE]\n\n"
        return
    if name == "cut":
        yield sse(delta("half an ans"))
        return  # a whole frame, then the body ends with no terminator
    if name == "done_without_finish":
        # The stream says the answer is complete and never says how it ended.
        # A different fault from a broken connection, and the field the safety
        # chain reads is the one that is missing.
        yield opening()
        yield sse(delta("Hello"))
        yield b"data: [DONE]\n\n"
        return
    if name == "abort":
        # The connection is cut mid-body while THIS PROCESS STAYS UP: a proxy in
        # between, a slot reset, a network that went. The client sees a body
        # that stops in the middle of the chunked stream — a transport failure,
        # and emphatically not a death.
        yield opening()
        yield sse(delta("half an ans"))
        yield "abort"
        return
    if name == "prefill":
        # Working, and nothing to show for it yet: a long prompt or an image
        # being fed to the model. No frame is written for the whole of it, the
        # decode counter stands at zero throughout, and the only sign of life is
        # the line the server writes per batch. Nothing here may ever be cut.
        yield opening()
        # One shape at a time when a test names one (FAKE_LLAMA_WORK_LINE), all
        # of them in turn otherwise.
        chosen = os.environ.get("FAKE_LLAMA_WORK_LINE", "").strip()
        lines = ([WORK_LINES[int(chosen)]] if chosen.isdigit() else WORK_LINES)
        for index in range(12):
            yield 0.25
            yield "log:" + lines[index % len(lines)]
        yield sse(delta("Hello world"))
        yield closing("stop")
        yield b"data: [DONE]\n\n"
        return
    if name == "wedge":
        # Accepts the request, answers the headers, and then writes nothing at
        # all — a llama-server that survived a CUDA error. No read timeout will
        # ever end this, by rule; only a progress bound can.
        yield 3600.0
        return
    if name == "slow":
        # Slow but working: a frame every 0.4 s. Nothing here may ever be cut.
        for index in range(8):
            yield 0.4
            yield sse(delta(f"piece {index} "))
        yield closing("stop")
        yield b"data: [DONE]\n\n"
        return
    if name == "die_after_finish":
        # Everything the caller asked for, and then the process goes before it
        # can write its [DONE].
        yield opening()
        yield sse(delta("Hello"))
        yield sse(delta(" world"))
        yield closing("stop")
        yield 0.05
        yield "die"
        return
    if name == "half_frame":
        # The body ends cleanly in the MIDDLE of a frame: no blank line, so the
        # frame was never dispatched. Half a JSON object handed on as an answer
        # is the one outcome worse than losing it.
        yield opening()
        yield sse(delta("Hello"))
        yield b'data: {"id": "x", "object": "chat.completion.chunk", "choices": [{"index'
        return
    if name == "die":
        yield sse(delta("half an ans"))
        yield 0.05
        yield "die"
        return
    if name == "die_at_once":
        # Headers, then the process goes, with no frame at all in between: what
        # an image encoder that found no compute buffer does to a real child.
        yield 0.05
        yield "die"
        return
    if name == "event_error":
        # DEFENSIVE. This build names its errors in the data payload and sends
        # no `event:` field at all; the SSE grammar has one, so the parser
        # answers for it.
        yield sse(delta("starting"))
        yield b"event: error\ndata: {\"error\": {\"code\": 500, \"message\": \"the slot is gone\"}}\n\n"
        return
    if name == "data_error":
        yield b"data: {\"error\": {\"code\": 400, \"message\": \"the request exceeds the available context size\"}}\n\n"
        return
    if name == "utf8":
        # One multibyte character deliberately cut in half between two writes,
        # so a parser that decodes each chunk on its own produces two
        # replacement marks where one character belongs.
        blob = sse(delta("Grüße, 日本語"))
        cut = blob.index(b"\xe6")  # inside the first CJK character
        yield blob[:cut + 1]
        yield 0.05
        yield blob[cut + 1:]
        yield sse(delta(finish="stop"))
        return
    if name == "comment_multiline":
        yield b": keep-alive ping\n\n"
        # DEFENSIVE for the split payload: this build writes each chunk on one
        # `data:` line. Per the grammar two lines are joined with a NEWLINE
        # before the value is read, so the split is put where a newline is legal
        # JSON whitespace rather than inside a token.
        yield (b'data: {"id": "x", "choices": [{"index": 0,\n'
               b'data:  "delta": {"content": "split"}}]}\n\n')
        yield sse(delta(finish="stop"))
        return
    if name == "thinking":
        # A reasoning model's template opens <think> in the PROMPT, so what comes
        # back carries the closing tag alone.
        yield opening()
        yield sse(delta("weighing it up"))
        yield sse(delta("</think>"))
        yield sse(delta("the answer"))
        yield closing("stop")
        yield b"data: [DONE]\n\n"
        return
    if name == "loop":
        yield opening()
        for _ in range(4000):
            yield sse(delta(LOOP_SENTENCE))
            yield 0.005
        yield closing("stop")
        yield b"data: [DONE]\n\n"
        return
    # "plain" — the shape of every ordinary answer from this build: the role
    # chunk, the content, the finish chunk carrying the timings, [DONE].
    yield opening()
    yield sse(delta("Hello"))
    yield sse(delta(" world"))
    yield closing("stop")
    yield b"data: [DONE]\n\n"


def completion_script(name):
    if name == "limit":
        yield sse({"content": "as far as", "stop": False})
        yield sse({"content": " it got", "stop": True, "stop_type": "limit",
                   "truncated": False})
        return
    if name == "truncated":
        yield sse({"content": "an answer to a shortened prompt", "stop": False})
        yield sse({"content": "", "stop": True, "stop_type": "eos", "truncated": True})
        return
    if name == "word":
        yield sse({"content": "up to the stop word", "stop": False})
        yield sse({"content": "", "stop": True, "stop_type": "word"})
        return
    if name == "unknown_stop_type":
        yield sse({"content": "as far as it got", "stop": False})
        yield sse({"content": "", "stop": True, "stop_type": "something_new"})
        return
    if name == "cut":
        yield sse({"content": "half an ans", "stop": False})
        return
    if name == "loop":
        for _ in range(4000):
            yield sse({"content": LOOP_SENTENCE, "stop": False})
            yield 0.005
        yield sse({"content": "", "stop": True, "stop_type": "eos"})
        return
    # "plain"
    yield sse({"content": "ok", "stop": False})
    yield sse({"content": "!", "stop": True, "stop_type": "eos"})


# =============================================================================
# HTTP
# =============================================================================

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Silent on purpose: the supervisor's stall bound watches for NEW log
        # lines, and a server that narrated its own health polls would report
        # progress for the whole time it is failing to start.
        return

    # ------------------------------------------------------------------- GET

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            if time.time() >= STATE["ready_at"]:
                self._json(200, {"status": "ok"})
            else:
                self._json(503, {"error": {"code": 503, "message": "Loading model"}})
            return
        if path == "/props":
            self._json(200, {
                "model_path": STATE["model_path"],
                "n_ctx": STATE["n_ctx"],
                "modalities": {"vision": bool(STATE["mmproj"]), "audio": False},
            })
            return
        if path == "/slots":
            if STATE["slots_hang"]:
                # The main loop has stopped turning: the METRICS task this
                # endpoint posts is never picked up, and the caller waits until
                # it gives up. Bounded so a test teardown is not held here.
                deadline = time.time() + 30.0
                while STATE["slots_hang"] and time.time() < deadline:
                    time.sleep(0.05)
            self._json(200, [{
                "id": 0,
                "n_ctx": STATE["n_ctx"],
                "is_processing": STATE["processing"],
                # The real build nests it in a list of one; see
                # tools/server/server-context.cpp to_json.
                "next_token": [{
                    "has_next_token": STATE["processing"],
                    "n_decoded": STATE["decoded"],
                }],
            }])
            return
        if path == "/last-request":
            self._json(200, {"path": STATE["last_path"], "body": STATE["last_request"]})
            return
        if path == "/control":
            from urllib.parse import parse_qs, urlparse
            for key, values in parse_qs(urlparse(self.path).query).items():
                if key in ("chat", "completion", "status", "verdict"):
                    STATE[key] = values[0]
                elif key in ("tick", "slots_hang", "decoded"):
                    STATE[key] = int(values[0])
            self._json(200, {"chat": STATE["chat"], "completion": STATE["completion"],
                             "status": STATE["status"], "verdict": STATE["verdict"],
                             "tick": STATE["tick"],
                             "slots_hang": STATE["slots_hang"],
                             "decoded": STATE["decoded"]})
            return
        if path == "/stats":
            self._json(200, {"requests": STATE["requests"],
                             "disconnects": STATE["disconnects"],
                             "images": STATE["images"],
                             "chat_failures": STATE["chat_failures"],
                             "processing": STATE["processing"]})
            return
        self._json(404, {"error": {"code": 404, "message": "not found"}})

    # ------------------------------------------------------------------ POST

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            STATE["last_request"] = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            STATE["last_request"] = {"_unparsed": raw.decode("utf-8", "replace")}
        STATE["last_path"] = path
        STATE["requests"] += 1
        # Every arriving request writes these, whatever happens next — which is
        # why a counter of ALL log lines cannot tell a working child from a
        # wedged one that is being sent request after request.
        emit("srv  params_from_: Chat format: Content-only")
        emit("slot launch_slot_: id  0 | task %d | processing task"
             % STATE["requests"])

        # Refused before anything is counted as encoded: a request that fails
        # here fed the model nothing, and a test watching for the image must
        # see it only for the attempt that got through.
        if (path == "/v1/chat/completions"
                and os.environ.get("FAKE_LLAMA_CHAT_FAIL_FIRST")
                and STATE["chat_failures"] == 0):
            STATE["chat_failures"] += 1
            self._json(500, {"error": {"code": 500,
                                       "message": "failed to process image"}})
            return

        if carries_an_image(STATE["last_request"]):
            STATE["images"] += 1
            # The lines mtmd writes while it encodes one, so the parent's work
            # counter moves for an image here exactly as it does in production.
            for line in WORK_LINES[2:]:
                emit(line)
            mark = os.environ.get("FAKE_LLAMA_IMAGE_MARK", "").strip()
            if mark:
                with open(mark, "a", encoding="utf-8") as handle:
                    handle.write("%d\n" % STATE["images"])

        forced = STATE["status"].strip()
        if forced:
            code = int(forced)
            self._json(code, {"error": {
                "code": code,
                "message": ("Loading model" if code == 503
                            else "the request exceeds the available context size"),
            }})
            return

        if path == "/v1/chat/completions":
            if (STATE["last_request"] or {}).get("stream") is False:
                # The real server answers an unstreamed request with a JSON
                # body, and the classification path needs exactly that: a
                # logprob is not an event.
                if STATE["verdict"] == "not_json":
                    body = b"<html><body>Internal Server Error</body></html>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self._json(200, verdict_body(STATE["verdict"]))
                return
            self._stream(chat_script(STATE["chat"]))
            return
        if path == "/completion":
            self._stream(completion_script(STATE["completion"]))
            return
        self._json(404, {"error": {"code": 404, "message": "not found"}})

    # --------------------------------------------------------------- plumbing

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self, script):
        """Serve an event stream the way cpp-httplib does: chunked.

        The encoding is not a detail. A body that is neither chunked nor
        length-delimited can only end at the close of the connection, and every
        HTTP client then hands the caller the WHOLE answer at once — which
        silently disables the repetition guard, because there is nothing to feed
        it until the model has already written everything.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        STATE["processing"] = True
        ended = False
        try:
            for item in script:
                if isinstance(item, str) and item.startswith("log:"):
                    # A line on stdout and nothing on the socket: the shape of a
                    # child that is working on the prompt, not on the answer.
                    emit(item[4:])
                    continue
                if item == "die":
                    sys.stdout.flush()
                    os._exit(int(os.environ.get("FAKE_LLAMA_EXIT_CODE", "9")))
                if item == "abort":
                    # Half a body and then nothing: the socket goes, the process
                    # stays. Returning here skips the chunked terminator, which
                    # is what makes the client call it a transport failure.
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    self.close_connection = True
                    emit("srv  the connection was cut, the server is still here")
                    return
                if isinstance(item, float):
                    time.sleep(item)
                    continue
                self.wfile.write(b"%x\r\n" % len(item) + item + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
            ended = True
        except (BrokenPipeError, ConnectionResetError):
            # The reader hung up mid-answer. This is what a repetition stop
            # looks like from in here, and llama-server answers it by cancelling
            # the slot — so the slot goes idle and the disconnect is counted.
            STATE["disconnects"] += 1
            emit("srv  cancel_tasks: the client disconnected, cancelling the slot")
        finally:
            STATE["processing"] = False
        self.close_connection = not ended


# =============================================================================
# Startup
# =============================================================================

def _tick_forever():
    """The decode counter, moving while a request is in flight and tick is on."""
    while True:
        time.sleep(0.1)
        if STATE["tick"] and STATE["processing"]:
            STATE["decoded"] += 1


def main():
    if "--version" in sys.argv:
        # The real binary answers this without loading anything, and the engine
        # asks it once for /api/llm/health.
        emit("version: 1 (fake)")
        emit("built with a stand-in for llama-server")
        return

    parse_argv(sys.argv[1:])
    mode = os.environ.get("FAKE_LLAMA_MODE", "ready").strip()
    STATE["tick"] = int(os.environ.get("FAKE_LLAMA_TICK", "0") or 0)
    threading.Thread(target=_tick_forever, name="fake-tick", daemon=True).start()

    if os.environ.get("FAKE_LLAMA_IGNORE_SIGTERM"):
        # A wedged child answers the polite signal with nothing at all, and the
        # supervisor has to escalate. Real: a llama-server inside a CUDA call
        # runs its handler only once the call returns.
        import signal as _signal
        _signal.signal(_signal.SIGTERM, _signal.SIG_IGN)
    STATE["chat"] = os.environ.get("FAKE_LLAMA_CHAT", "plain")
    STATE["verdict"] = os.environ.get("FAKE_LLAMA_VERDICT", "no")
    STATE["completion"] = os.environ.get("FAKE_LLAMA_COMPLETION", "plain")
    STATE["status"] = os.environ.get("FAKE_LLAMA_STATUS", "")

    emit(f"build: 1 (fake) with a stand-in for llama-server, alias {STATE['alias']}")
    emit(f"main: loading model from {STATE['model_path']}")

    fail_port = os.environ.get("FAKE_LLAMA_BIND_FAIL_PORT", "").strip()
    if mode == "bind_error" or (fail_port and STATE["port"] == int(fail_port)):
        emit(f"main: couldn't bind HTTP server socket, hostname: 127.0.0.1, "
             f"port: {STATE['port']} (address already in use)")
        sys.exit(1)

    if mode == "exit":
        emit("load_model: failed to load the model: unknown model architecture")
        sys.exit(int(os.environ.get("FAKE_LLAMA_EXIT_CODE", "1")))

    vision_delay = float(os.environ.get("FAKE_LLAMA_VISION_LINE_DELAY_S", "0") or 0)
    if STATE["mmproj"] and not os.environ.get("FAKE_LLAMA_NO_VISION_LINE"):
        def _vision_lines():
            emit(f"clip_model_loader: loading model from {STATE['mmproj']}")
            emit("alloc_compute_meta:      CUDA0 compute buffer size =  4728.07 MiB")

        if vision_delay > 0:
            # The projector is built AFTER the language model, and /health can
            # answer 200 in between. Delayed on purpose so the grace period is
            # tested rather than assumed.
            threading.Timer(vision_delay, _vision_lines).start()
        else:
            _vision_lines()

    if mode == "noisy":
        # More than the 64 KB a pipe holds. A supervisor that did not drain the
        # child's output would block it here, and the block is indistinguishable
        # from a model that stopped loading.
        for index in range(240):
            emit(f"load_tensors: layer {index:03d} " + "." * 300)

    delay = float(os.environ.get("FAKE_LLAMA_HEALTH_DELAY_S", "0") or 0)
    if mode in ("never_silent", "never_chatty", "never_dots"):
        STATE["ready_at"] = time.time() + 10 ** 9
    else:
        STATE["ready_at"] = time.time() + delay

    if mode == "never_chatty":
        def _chatter():
            while True:
                emit("load_tensors: still reading the model off disk")
                time.sleep(0.2)
        threading.Thread(target=_chatter, daemon=True).start()

    if mode == "never_dots":
        # The load bar as llama.cpp actually writes it: LOG_CONT, no newline,
        # for as long as the copy takes. A supervisor that counted LINES would
        # see nothing at all here and kill a model that is loading normally.
        def _dots():
            while True:
                sys.stdout.write(".")
                sys.stdout.flush()
                time.sleep(0.05)
        threading.Thread(target=_dots, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", STATE["port"]), Handler)
    server.daemon_threads = True
    emit(f"main: server is listening on http://127.0.0.1:{STATE['port']}")
    try:
        server.serve_forever(poll_interval=0.05)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
