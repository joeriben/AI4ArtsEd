#!/usr/bin/env python3
"""
Tests for the one reader that talks to OpenAI-compatible cloud providers
(my_app/services/openai_style_stream.py).

Written on 2026-09-03, when the reader was lifted out of chat_routes.py so the
pipeline engine and the image check could stop keeping provider tables of their
own. Two things are held here.

The first is the shape of an answer as it arrives in pieces. A streamed answer
is not one object; it is a sequence of fragments that only becomes an answer
because this reader assembles it, and every caller downstream is written
against the assembled shape. So the deltas are served as real bytes over a real
socket rather than handed to a patched function: the SSE grammar, the chunk
that carries only usage, the tool call whose arguments arrive in slices, and a
connection that stops in the middle are all properties of the transport, and
none of them exist in a mock.

The second is finish_reason, and it is the reason this file matters more than
its subject suggests. The image check refuses a child's picture when the model
that judged it stopped because it ran out of room rather than because it was
done: an answer cut off mid-sentence is not a verdict. The reader did not read
that field at all until now, so moving the check onto it would have retired the
truncation guard in silence — no error, no log line, just a truncated rating
read as a finished one. The tests below pin the field, 'length' included.

Run: python3 -m pytest devserver/tests/test_openai_style_stream.py -q
"""
import json
import sys
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import openai_style_stream as oss

# Not a real model id. The platform must hold no knowledge about any particular
# model, and a test that named one would be pinning the thing that was removed.
MODEL = "some-model-under-test"
PROVIDER = "mammouth"


# ---------------------------------------------------------------------------
# A provider that really answers over a socket
# ---------------------------------------------------------------------------
# Each entry in the queue is one scripted response, consumed by one request.
# The bodies the client sent are kept, because "asked again WITHOUT
# stream_options" is a claim about a request, not about a return value.

def sse(payload) -> bytes:
    """One SSE frame, the way a provider writes them."""
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")


def chunk(delta=None, finish=None, usage=None) -> dict:
    """One chat.completion.chunk. A chunk carrying only usage has no choices —
    that is what the providers send when stream_options was accepted."""
    out = {"id": "x", "object": "chat.completion.chunk", "choices": []}
    if delta is not None or finish is not None:
        choice = {"index": 0, "delta": delta or {}}
        if finish is not None:
            choice["finish_reason"] = finish
        out["choices"] = [choice]
    if usage is not None:
        out["usage"] = usage
    return out


DONE = b"data: [DONE]\n\n"


def _open_stream(handler, charset=None):
    """Headers for a streamed answer. Chunked, because that is how a provider
    that does not know the length of its answer in advance sends one — and
    because a chunked body is what can be left unfinished (see sse_cut).

    The default names NO charset, which is the case that breaks: requests then
    reads a text/* body as ISO-8859-1 and every umlaut comes back wrong."""
    content_type = "text/event-stream"
    if charset:
        content_type += f"; charset={charset}"
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Transfer-Encoding", "chunked")
    handler.end_headers()


def _write_chunk(handler, data: bytes):
    handler.wfile.write(f"{len(data):X}\r\n".encode("ascii") + data + b"\r\n")
    handler.wfile.flush()


def sse_ok(frames, charset=None):
    """A well-behaved streamed answer: 200, event-stream, frames, [DONE]."""
    def program(handler):
        _open_stream(handler, charset)
        for frame in frames:
            _write_chunk(handler, frame)
        _write_chunk(handler, DONE)
        handler.wfile.write(b"0\r\n\r\n")
        handler.wfile.flush()
    return program


def http_error(status, body):
    """A provider that refuses before it has written a byte of answer."""
    def program(handler):
        raw = body.encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw)
    return program


def sse_cut(frames):
    """An answer that stops in the middle: some chunks arrive, the terminating
    zero-chunk never does, and the socket closes. This is a stream breaking
    while it is being read, which is a real failure — not something to ask
    again about."""
    def program(handler):
        _open_stream(handler)
        for frame in frames:
            _write_chunk(handler, frame)
        handler.close_connection = True
        try:
            handler.connection.close()
        except OSError:
            pass
    return program


def sse_cut_but_terminated(frames):
    """An answer that stops in the middle and is then closed off PROPERLY: the
    frames that had arrived, and a well-formed terminating zero-chunk after
    them. That is what a proxy in between writes when it gives up on the origin.
    Nothing at the HTTP layer is malformed, nothing raises — and the answer is a
    fragment. Compare sse_cut above, which omits the terminating chunk and is
    the only one of the three shapes that the transport itself refuses."""
    def program(handler):
        _open_stream(handler)
        for frame in frames:
            _write_chunk(handler, frame)
        handler.wfile.write(b"0\r\n\r\n")
        handler.wfile.flush()
    return program


def sse_cut_under_connection_close(frames):
    """The same fragment delivered the other legal way: no Content-Length, no
    chunked framing, `Connection: close` — and the close itself is where the
    body ends. Written by hand rather than through _open_stream, because this
    shape is defined by the headers it does NOT send."""
    def program(handler):
        handler.wfile.write(b"HTTP/1.1 200 OK\r\n"
                            b"Content-Type: text/event-stream\r\n"
                            b"Connection: close\r\n\r\n")
        for frame in frames:
            handler.wfile.write(frame)
        handler.wfile.flush()
        handler.close_connection = True
    return program


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            body = None
        self.server.requests.append(body)
        self.server.paths.append(self.path)
        if not self.server.programs:
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        program = self.server.programs.popleft()
        try:
            program(self)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def log_message(self, *args):
        pass


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """A client that hangs up is the subject of two of these tests, not a
        fault of the provider standing in here. Kept quiet, so that a passing
        run reads as a passing run."""


class _Provider:
    def __init__(self):
        self.server = _Server(("127.0.0.1", 0), _Handler)
        self.server.programs = deque()
        self.server.requests = []
        self.server.paths = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        host, port = self.server.server_address
        return f"http://{host}:{port}/v1/chat/completions"

    def script(self, *programs):
        self.server.programs.extend(programs)

    @property
    def requests(self):
        return self.server.requests

    @property
    def paths(self):
        """The request paths, in the order the requests arrived."""
        return self.server.paths

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class _Ledger:
    """Stands in for the usage tracker so the tests never write into the real
    ledger, and so 'the numbers arrived' is something to assert on."""
    def __init__(self):
        self.entries = []

    def log(self, **kw):
        self.entries.append(kw)


@pytest.fixture()
def provider(monkeypatch):
    p = _Provider()
    monkeypatch.setitem(oss._OPENAI_STYLE_PROVIDERS, PROVIDER, lambda: (p.url, "test-key"))
    yield p
    p.close()


@pytest.fixture()
def ledger(monkeypatch):
    book = _Ledger()
    monkeypatch.setattr(oss, "get_usage_tracker", lambda: book)
    return book


@pytest.fixture()
def no_waiting(monkeypatch):
    """Records the backoff instead of sleeping it. The waits are real seconds in
    production and would be real seconds here."""
    waits = []
    monkeypatch.setattr(oss.time, "sleep", lambda s: waits.append(s))
    return waits


def run(provider_name=PROVIDER, **kw):
    """Drive the generator to its end. Returns (tokens, result)."""
    tokens, result = [], None
    for kind, payload in oss._stream_openai_style(
            provider_name, [{"role": "user", "content": "hallo"}], MODEL, 0.7, None, **kw):
        if kind == "token":
            tokens.append(payload)
        else:
            result = payload
    return tokens, result


# ---------------------------------------------------------------------------
# 1. The answer, as it assembles
# ---------------------------------------------------------------------------

def test_content_deltas_assemble_in_the_order_they_arrived(provider, ledger):
    provider.script(sse_ok([
        sse(chunk({"role": "assistant", "content": None})),
        sse(chunk({"content": "Der "})),
        sse(chunk({"content": "Fluss "})),
        sse(chunk({"content": "steigt."})),
        sse(chunk({}, finish="stop")),
    ]))
    tokens, result = run()
    assert tokens == ["Der ", "Fluss ", "steigt."]
    assert result["content"] == "Der Fluss steigt."
    assert result["thinking"] is None
    assert result["tool_calls"] is None


def test_reasoning_lands_in_thinking_and_never_in_content(provider, ledger):
    """Both spellings the providers use, and neither of them reaches the room:
    what streams to a person is the answer, not the model's own muttering."""
    provider.script(sse_ok([
        sse(chunk({"reasoning_content": "Erst prüfe ich "})),
        sse(chunk({"reasoning": "die Jahreszeit. "})),
        sse(chunk({"content": "Im Winter."})),
        sse(chunk({}, finish="stop")),
    ]))
    tokens, result = run()
    assert tokens == ["Im Winter."]
    assert result["content"] == "Im Winter."
    assert result["thinking"] == "Erst prüfe ich die Jahreszeit. "


def test_reasoning_alone_is_returned_as_reasoning_not_promoted_to_answer(provider, ledger):
    """The reader does not decide whether reasoning may stand in for an answer.
    It hands both back and lets the caller choose — chat substitutes, the
    pipeline engine refuses to. A model that produced only reasoning has
    produced something, so this is not the empty case either."""
    provider.script(sse_ok([
        sse(chunk({"reasoning_content": "Ich überlege noch."})),
        sse(chunk({}, finish="stop")),
    ]))
    tokens, result = run()
    assert tokens == []
    assert result["content"] == ""
    assert result["thinking"] == "Ich überlege noch."


def test_a_provider_that_names_utf_8_is_read_as_it_asked(provider, ledger):
    """The other half of the encoding rule: a declared charset is obeyed, so the
    silent-case default cannot override a provider that said what it sends."""
    provider.script(sse_ok([
        sse(chunk({"content": "Grüße aus Nürnberg — mit Strich."})),
        sse(chunk({}, finish="stop")),
    ], charset="utf-8"))
    _, result = run()
    assert result["content"] == "Grüße aus Nürnberg — mit Strich."


def test_a_provider_that_names_no_charset_is_still_read_as_utf_8(provider, ledger):
    """Server-sent events are defined as UTF-8, and most providers send
    text/event-stream with no charset parameter at all. requests then falls back
    to ISO-8859-1, which turned every umlaut in a German answer into mojibake —
    and this reader now carries the pipeline's text as well as the chat's."""
    provider.script(sse_ok([
        sse(chunk({"content": "Grüße aus Nürnberg — mit Strich."})),
        sse(chunk({}, finish="stop")),
    ]))
    tokens, result = run()
    assert tokens == ["Grüße aus Nürnberg — mit Strich."]
    assert result["content"] == "Grüße aus Nürnberg — mit Strich."


# ---------------------------------------------------------------------------
# 2. finish_reason — the field the image check reads
# ---------------------------------------------------------------------------

def test_finish_reason_is_captured(provider, ledger):
    provider.script(sse_ok([
        sse(chunk({"content": "fertig"})),
        sse(chunk({}, finish="stop")),
    ]))
    _, result = run()
    assert result["finish_reason"] == "stop"


def test_a_cut_off_answer_is_marked_length(provider, ledger):
    """The safety-critical one. The image check blocks a child's picture when
    the verdict model stopped at 'length', because a rating that broke off
    mid-sentence is not a rating. If this key ever goes missing the guard stops
    working without saying so."""
    provider.script(sse_ok([
        sse(chunk({"content": "Das Bild zeigt einen"})),
        sse(chunk({}, finish="length")),
    ]))
    _, result = run()
    assert result["finish_reason"] == "length"
    assert result["content"] == "Das Bild zeigt einen"


def test_finish_reason_riding_on_the_last_content_chunk_is_still_seen(provider, ledger):
    """Some providers put it on the chunk that carries the final token instead
    of on a chunk of its own."""
    provider.script(sse_ok([
        sse(chunk({"content": "kurz"}, finish="length")),
    ]))
    _, result = run()
    assert result["finish_reason"] == "length"


def test_a_usage_only_last_chunk_does_not_erase_the_finish_reason(provider, ledger):
    """The usage chunk carries an empty choices array. Reading finish_reason out
    of it unconditionally would overwrite what the real last choice said."""
    provider.script(sse_ok([
        sse(chunk({"content": "ja"}, finish="length")),
        sse(chunk(usage={"prompt_tokens": 3, "completion_tokens": 1})),
    ]))
    _, result = run()
    assert result["finish_reason"] == "length"


# ---------------------------------------------------------------------------
# 2b. A stream that never said it was finished
# ---------------------------------------------------------------------------
# The one that put a picture in front of a child, on 2026-09-04. Before this
# reader existed the whole answer was parsed with response.json(), and a body
# cut in the middle is not JSON — the failure raised by itself. Read frame by
# frame it fell silent instead: the loop simply ran out of lines, finish_reason
# stayed None, every guard keyed on that field missed, and the fragment that had
# arrived was handed on as the whole answer. A verdict cut after the word SAFE
# read as a verdict of SAFE.
#
# Both shapes below are legal HTTP and neither raises by itself. The third
# shape, a chunked body with no terminating chunk, is the one the transport
# already refused — see "a stream that breaks mid-answer" further down, which is
# exactly that case and is why these two went unnoticed.

def test_a_body_cut_under_connection_close_is_not_a_finished_answer(provider, ledger):
    provider.script(sse_cut_under_connection_close([sse(chunk({"content": "SAFE"}))]))
    with pytest.raises(Exception) as excinfo:
        run()
    message = str(excinfo.value)
    assert "without saying it had finished" in message
    assert PROVIDER in message and MODEL in message


def test_a_chunked_body_a_proxy_closed_off_is_not_a_finished_answer(provider, ledger):
    """Measured over a real socket: the frames that arrived, then a terminating
    zero-chunk written by something that is not the model."""
    provider.script(sse_cut_but_terminated([sse(chunk({"content": "SAFE"}))]))
    with pytest.raises(Exception) as excinfo:
        run()
    assert "without saying it had finished" in str(excinfo.value)


def test_a_torn_stream_counts_as_availability_and_never_as_a_refusal():
    """What the wording of that message is FOR. A chat turn may try the next
    candidate when a stream tore; it may never do so when a provider refused,
    and one classifier tells the two apart by the words in the message alone."""
    from my_app.routes.chat_routes import is_retriable_llm_error
    assert is_retriable_llm_error(Exception(
        "mammouth stream for model m ended without saying it had finished — the "
        "connection closed after 4 characters of answer with no terminal "
        "marker, so what arrived may be a fragment")) is True


def test_a_stream_cut_after_its_finish_reason_HAS_finished(provider, ledger):
    """The half of the rule that keeps it narrow. Either marker is enough, so a
    provider that named why it stopped has delivered its answer; what a cut
    after that costs is the [DONE] sentinel and the usage chunk — the token
    count, not the text. Only a stream that gave NEITHER marker is refused."""
    provider.script(sse_cut_but_terminated([
        sse(chunk({"content": "fertig"}, finish="stop")),
    ]))
    _, result = run()
    assert result["content"] == "fertig"
    assert result["finish_reason"] == "stop"


def test_a_stream_that_wrote_only_the_done_sentinel_HAS_finished(provider, ledger):
    """And the other half. A provider that ends with [DONE] and never writes a
    finish_reason has still said the answer is over, and is not refused for it —
    which is what makes this a rule about the END of a stream rather than a new
    requirement on finish_reason."""
    provider.script(sse_ok([sse(chunk({"content": "fertig"}))]))
    _, result = run()
    assert result["content"] == "fertig"
    assert result["finish_reason"] is None


# ---------------------------------------------------------------------------
# 2c. Two terminal reasons in one stream
# ---------------------------------------------------------------------------

def test_two_different_terminal_reasons_in_one_stream_are_refused(provider, ledger):
    """A stream carries ONE terminal reason. This reader took the last one until
    2026-09-04, so 'length' followed by 'stop' arrived as 'stop' — a truncated
    answer passing for a finished one at every guard that reads the field.
    Taking the first instead would lose a 'length' that arrived late, so neither
    is chosen: the contradiction is raised, and every caller blocks on it."""
    provider.script(sse_ok([
        sse(chunk({"content": "SAFE for children as long as"}, finish="length")),
        sse(chunk({}, finish="stop")),
    ]))
    with pytest.raises(Exception) as excinfo:
        run()
    message = str(excinfo.value)
    assert "'length'" in message and "'stop'" in message


def test_the_same_terminal_reason_twice_is_a_repetition_and_passes(provider, ledger):
    """Only a DIFFERENT second value contradicts the first. A provider that
    writes the same word twice has said one thing twice."""
    provider.script(sse_ok([
        sse(chunk({"content": "fertig"}, finish="stop")),
        sse(chunk({}, finish="stop")),
    ]))
    _, result = run()
    assert result["finish_reason"] == "stop"


# ---------------------------------------------------------------------------
# 3. Tool calls arriving in fragments
# ---------------------------------------------------------------------------

def test_tool_call_fragments_reassemble_into_the_blocking_shape(provider, ledger):
    provider.script(sse_ok([
        sse(chunk({"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                   "function": {"name": "lookup_", "arguments": ""}}]})),
        sse(chunk({"tool_calls": [{"index": 0, "function": {"name": "reference"}}]})),
        sse(chunk({"tool_calls": [{"index": 0, "function": {"arguments": "{\"q\": "}}]})),
        sse(chunk({"tool_calls": [{"index": 0, "function": {"arguments": "\"Fluss\"}"}}]})),
        sse(chunk({}, finish="tool_calls")),
    ]))
    tokens, result = run(tools=[{"type": "function", "function": {"name": "lookup_reference"}}])
    assert tokens == []
    assert result["tool_calls"] == [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "lookup_reference", "arguments": '{"q": "Fluss"}'},
    }]
    assert result["finish_reason"] == "tool_calls"


def test_two_tool_calls_stay_apart_and_keep_their_order(provider, ledger):
    provider.script(sse_ok([
        sse(chunk({"tool_calls": [{"index": 1, "id": "b", "function": {"name": "second"}}]})),
        sse(chunk({"tool_calls": [{"index": 0, "id": "a", "function": {"name": "first"}}]})),
        sse(chunk({"tool_calls": [{"index": 0, "function": {"arguments": "{}"}},
                                  {"index": 1, "function": {"arguments": "{}"}}]})),
        sse(chunk({}, finish="tool_calls")),
    ]))
    _, result = run(tools=[{"type": "function", "function": {"name": "first"}}])
    assert [tc["id"] for tc in result["tool_calls"]] == ["a", "b"]


# ---------------------------------------------------------------------------
# 4. Usage
# ---------------------------------------------------------------------------

def test_usage_from_the_final_chunk_reaches_the_ledger(provider, ledger):
    provider.script(sse_ok([
        sse(chunk({"content": "kurz"})),
        sse(chunk({}, finish="stop")),
        sse(chunk(usage={"prompt_tokens": 41, "completion_tokens": 7})),
    ]))
    run()
    assert ledger.entries == [{"model": MODEL, "provider": PROVIDER, "stage": "chat",
                               "input_tokens": 41, "output_tokens": 7}]


def test_the_caller_names_the_stage_it_books_under(provider, ledger):
    """A verdict is not chat. The image check must not have its tokens booked
    against the chat surface's line in the ledger."""
    provider.script(sse_ok([
        sse(chunk({"content": "SAFE"})),
        sse(chunk({}, finish="stop")),
        sse(chunk(usage={"prompt_tokens": 10, "completion_tokens": 2})),
    ]))
    run(stage="stage3")
    assert ledger.entries[0]["stage"] == "stage3"


# ---------------------------------------------------------------------------
# 5. What the request itself carries
# ---------------------------------------------------------------------------

def test_no_cap_and_no_read_timeout_unless_a_caller_asks(provider, ledger):
    """An output cap truncates substance mid-sentence, and a read timeout kills
    a model that is still thinking. Neither is sent unless a caller passes one."""
    provider.script(sse_ok([sse(chunk({"content": "x"})), sse(chunk({}, finish="stop"))]))
    run()
    sent = provider.requests[0]
    assert "max_tokens" not in sent
    assert sent["stream"] is True
    assert oss.LLM_TIMEOUT[0] > 0


def test_a_cap_passed_by_a_caller_is_forwarded(provider, ledger):
    provider.script(sse_ok([sse(chunk({"content": "x"})), sse(chunk({}, finish="stop"))]))
    list(oss._stream_openai_style(PROVIDER, [{"role": "user", "content": "hi"}],
                                  MODEL, 0.7, 64000))
    assert provider.requests[0]["max_tokens"] == 64000


def test_stream_options_refused_with_400_causes_exactly_one_re_open(provider, ledger):
    """A provider that does not know the field must not cost the turn. It is
    asked again without it — once, and the second request carries everything
    else unchanged."""
    provider.script(
        http_error(400, '{"error": "unknown field: stream_options"}'),
        sse_ok([sse(chunk({"content": "doch"})), sse(chunk({}, finish="stop"))]),
    )
    tokens, result = run()
    assert result["content"] == "doch"
    assert len(provider.requests) == 2
    assert "stream_options" in provider.requests[0]
    assert "stream_options" not in provider.requests[1]
    assert provider.requests[1]["messages"] == provider.requests[0]["messages"]


# ---------------------------------------------------------------------------
# 6. Asking again — only before the first byte
# ---------------------------------------------------------------------------

CLOUDFLARE_524 = (
    "<html><head><title>524: A timeout occurred</title></head>"
    "<body>Error 524 — the origin did not respond in time.</body></html>"
)


def test_a_524_before_the_first_byte_is_asked_again(provider, ledger, no_waiting):
    """Cloudflare answers 524 when the origin has produced nothing for about a
    hundred seconds. Nothing was billed and nothing was shown, so asking again
    is free of consequence — and the second attempt is where this reader
    usually gets its answer."""
    provider.script(
        http_error(524, CLOUDFLARE_524),
        sse_ok([sse(chunk({"content": "endlich"})), sse(chunk({}, finish="stop"))]),
    )
    _, result = run()
    assert result["content"] == "endlich"
    assert len(provider.requests) == 2
    assert len(no_waiting) == 1 and 1.0 <= no_waiting[0] <= 1.5


def test_three_524s_raise_with_the_status_and_the_body_intact(provider, ledger, no_waiting):
    """Both halves of the message are load-bearing: is_retriable_llm_error reads
    the text, and a 524 currently only falls through to the next model because
    the word 'timeout' stands in Cloudflare's HTML."""
    provider.script(*[http_error(524, CLOUDFLARE_524) for _ in range(3)])
    with pytest.raises(Exception) as excinfo:
        run()
    message = str(excinfo.value)
    assert message.startswith("API Error: 524\n")
    assert "timeout" in message.lower()
    assert len(provider.requests) == 3
    assert [round(w) for w in no_waiting] == [1, 2]

    from my_app.routes.chat_routes import is_retriable_llm_error
    assert is_retriable_llm_error(excinfo.value) is True


def test_a_400_that_is_not_about_stream_options_is_not_asked_again(provider, ledger, no_waiting):
    """A refusal is not an availability failure. It is raised as it came."""
    provider.script(
        http_error(400, '{"error": "content policy violation"}'),
        http_error(400, '{"error": "content policy violation"}'),
    )
    with pytest.raises(Exception) as excinfo:
        run()
    assert "content policy" in str(excinfo.value)
    # One re-open, because stream_options was in the payload; then it stands.
    assert len(provider.requests) == 2
    assert no_waiting == []

    from my_app.routes.chat_routes import is_retriable_llm_error
    assert is_retriable_llm_error(excinfo.value) is False


def test_a_stream_that_breaks_mid_answer_raises_and_is_not_asked_again(provider, ledger, no_waiting):
    """Once bytes are flowing the answer is being paid for and, on the chat
    surface, already being read. A second attempt would bill the first half
    twice and could hand the room two beginnings of one text."""
    provider.script(
        sse_cut([sse(chunk({"content": "Der Fluss"}))]),
        sse_ok([sse(chunk({"content": "zweiter Versuch"})), sse(chunk({}, finish="stop"))]),
    )
    with pytest.raises(Exception):
        run()
    assert len(provider.requests) == 1
    assert no_waiting == []


def test_an_empty_stream_raises_naming_provider_and_model(provider, ledger):
    provider.script(sse_ok([]))
    with pytest.raises(Exception) as excinfo:
        run()
    assert PROVIDER in str(excinfo.value)
    assert MODEL in str(excinfo.value)


def test_a_missing_key_raises_before_anything_is_sent(monkeypatch, provider):
    monkeypatch.setitem(oss._OPENAI_STYLE_PROVIDERS, PROVIDER, lambda: (provider.url, ""))
    with pytest.raises(Exception) as excinfo:
        run()
    assert "API Key not configured" in str(excinfo.value)
    assert provider.requests == []


# ---------------------------------------------------------------------------
# 7. The blocking entry point
# ---------------------------------------------------------------------------

def _answer_frames():
    return [
        sse(chunk({"reasoning_content": "kurz nachgedacht"})),
        sse(chunk({"content": "Ja, "})),
        sse(chunk({"content": "sicher."})),
        sse(chunk({"tool_calls": [{"index": 0, "id": "t1", "type": "function",
                                   "function": {"name": "note", "arguments": "{}"}}]})),
        sse(chunk({}, finish="length")),
        sse(chunk(usage={"prompt_tokens": 5, "completion_tokens": 4})),
    ]


def test_the_blocking_entry_point_returns_the_generators_terminal_result(provider, ledger):
    """One reader, two ways of consuming it — and no second consumption loop
    that could fall out of step with this one."""
    provider.script(sse_ok(_answer_frames()), sse_ok(_answer_frames()))
    _, streamed = run()
    blocking = oss.call_openai_style(PROVIDER, [{"role": "user", "content": "hallo"}], MODEL)
    assert blocking == streamed
    assert set(blocking) == {"content", "thinking", "tool_calls", "finish_reason"}
    assert blocking["finish_reason"] == "length"


def test_the_blocking_entry_point_raises_what_the_generator_raises(provider, ledger, no_waiting):
    provider.script(*[http_error(524, CLOUDFLARE_524) for _ in range(3)])
    with pytest.raises(Exception) as excinfo:
        oss.call_openai_style(PROVIDER, [{"role": "user", "content": "hallo"}], MODEL)
    assert str(excinfo.value).startswith("API Error: 524\n")


def test_there_is_exactly_one_openai_style_reader_in_the_tree():
    """Project rule 13. The reader was duplicated into provider tables in two
    other modules once; the tables drifted until one of them no longer pointed
    at the provider it named."""
    root = Path(__file__).resolve().parents[1]
    owners = []
    for path in list(root.glob("my_app/**/*.py")) + list(root.glob("schemas/**/*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "def _stream_openai_style" in text:
            owners.append(str(path.relative_to(root)))
    assert owners == ["my_app/services/openai_style_stream.py"]


# ---------------------------------------------------------------------------
# 8. What the classifier makes of what this reader raises
# ---------------------------------------------------------------------------
# The reader raises "API Error: <status>\n<body>", and is_retriable_llm_error in
# chat_routes.py decides from that one string whether the turn may try the next
# candidate. Cloudflare's 52x range used to fall through only because the word
# "timeout" stands in the styled HTML page Cloudflare serves — an accident of a
# page, not a contract, and gone the moment a proxy answers tersely. Since
# 2026-09-04 the statuses themselves are listed, and this pair holds the line: a
# bare 52x falls through, and a refusal never does.
# (Imported inside each test, as the two above do: chat_routes pulls in the web
# layer, and this file's subject is reachable without it.)

def test_a_52x_with_a_terse_body_falls_through_to_the_next_candidate():
    from my_app.routes.chat_routes import is_retriable_llm_error
    assert is_retriable_llm_error(Exception("API Error: 521\nweb server is down")) is True
    # And with no body at all, which is what a bare proxy in front of a provider
    # returns.
    assert is_retriable_llm_error(Exception("API Error: 521\n")) is True


def test_the_whole_cloudflare_range_counts_as_an_availability_failure():
    from my_app.routes.chat_routes import is_retriable_llm_error
    for status in range(520, 528):
        assert is_retriable_llm_error(Exception(f"API Error: {status}\n")) is True


def test_a_refusal_is_not_retriable_however_it_is_worded():
    """Evaluated first, and it stays first. A prompt one provider refused must
    not be carried to a laxer one: that is not falling through, it is shopping
    for a yes."""
    from my_app.routes.chat_routes import is_retriable_llm_error
    for body in ('{"error": "content policy violation"}',
                 '{"error": {"code": "moderation_blocked"}}',
                 "the model refused to answer"):
        assert is_retriable_llm_error(Exception(f"API Error: 400\n{body}")) is False


def test_a_refusal_that_arrives_with_a_52x_status_is_still_a_refusal():
    """Both lists can match one message. The refusal wins, because a moderation
    body must not become retriable merely because a number stands beside it."""
    from my_app.routes.chat_routes import is_retriable_llm_error
    assert is_retriable_llm_error(
        Exception('API Error: 521\n{"error": "content policy violation"}')) is False


# ---------------------------------------------------------------------------
# 9. The second dialect: Anthropic's messages API
# ---------------------------------------------------------------------------
# Added 2026-09-04, when the last unstreamed cloud call on the platform was put
# on this transport. It is a second GRAMMAR, not a second reader: everything
# from "open the request" to "close the connection" is the same function the
# five above use, and the tests in this section are about what a frame MEANS.
#
# The wire is different enough to be worth naming. Events are named rather than
# interchangeable, each one preceded by an `event:` line the opener skips; the
# data object repeats the name in a "type" field; content blocks are addressed
# by index; there is no [DONE] sentinel, the stream ends at message_stop; and
# an error can arrive inside a 200 response, which is a shape the other dialect
# cannot produce at all.

ANTHROPIC_PROVIDER = "anthropic"


def anth(payload) -> bytes:
    """One Anthropic SSE frame, with the `event:` line a provider writes."""
    return (f"event: {payload['type']}\n"
            + "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")


def text_block(index=0):
    return anth({"type": "content_block_start", "index": index,
                 "content_block": {"type": "text", "text": ""}})


def text_delta(text, index=0):
    return anth({"type": "content_block_delta", "index": index,
                 "delta": {"type": "text_delta", "text": text}})


def anthropic_end(stop_reason="end_turn", output_tokens=None):
    """The two frames that close every answer in this dialect."""
    delta = {"type": "message_delta", "delta": {"stop_reason": stop_reason,
                                                "stop_sequence": None}}
    if output_tokens is not None:
        delta["usage"] = {"output_tokens": output_tokens}
    return [anth(delta), anth({"type": "message_stop"})]


def sse_anthropic(frames, charset=None):
    """A well-behaved streamed answer in this dialect: no [DONE], ever."""
    def program(handler):
        _open_stream(handler, charset)
        for frame in frames:
            _write_chunk(handler, frame)
        handler.wfile.write(b"0\r\n\r\n")
        handler.wfile.flush()
    return program


@pytest.fixture()
def anthropic_provider(monkeypatch):
    p = _Provider()
    monkeypatch.setitem(oss._ANTHROPIC_STYLE_PROVIDERS, ANTHROPIC_PROVIDER,
                        lambda: (p.url.replace("/chat/completions", "/messages"),
                                 "test-key"))
    yield p
    p.close()


def run_anthropic(**kw):
    """Drive the Anthropic generator to its end. Returns (tokens, result)."""
    tokens, result = [], None
    for kind, payload in oss._stream_anthropic_style(
            ANTHROPIC_PROVIDER, [{"role": "user", "content": "hallo"}], MODEL, **kw):
        if kind == "token":
            tokens.append(payload)
        else:
            result = payload
    return tokens, result


def test_anthropic_text_deltas_assemble_in_the_order_they_arrived(anthropic_provider, ledger):
    anthropic_provider.script(sse_anthropic([
        anth({"type": "message_start", "message": {"usage": {"input_tokens": 9}}}),
        text_block(),
        text_delta("Der "),
        text_delta("Fluss "),
        text_delta("steigt."),
        anth({"type": "content_block_stop", "index": 0}),
        *anthropic_end(),
    ]))
    tokens, result = run_anthropic()
    assert tokens == ["Der ", "Fluss ", "steigt."]
    assert result["content"] == "Der Fluss steigt."
    assert result["thinking"] is None
    assert result["tool_calls"] is None


def test_anthropic_reasoning_lands_in_thinking_and_never_in_content(anthropic_provider, ledger):
    """A thinking block streams thinking_delta events, and this reader keeps
    them apart from the answer — the pipeline engine's refusal to let reasoning
    stand in for an answer is only possible while the two are apart."""
    anthropic_provider.script(sse_anthropic([
        anth({"type": "content_block_start", "index": 0,
              "content_block": {"type": "thinking", "thinking": ""}}),
        anth({"type": "content_block_delta", "index": 0,
              "delta": {"type": "thinking_delta", "thinking": "Erst prüfe ich "}}),
        anth({"type": "content_block_delta", "index": 0,
              "delta": {"type": "thinking_delta", "thinking": "die Jahreszeit. "}}),
        anth({"type": "content_block_stop", "index": 0}),
        text_block(1),
        text_delta("Im Winter.", 1),
        *anthropic_end(),
    ]))
    tokens, result = run_anthropic()
    assert tokens == ["Im Winter."]
    assert result["content"] == "Im Winter."
    assert result["thinking"] == "Erst prüfe ich die Jahreszeit. "


def test_an_anthropic_answer_that_is_only_reasoning_states_no_content(anthropic_provider, ledger):
    """Nothing is promoted. The caller decides, and the pipeline engine decides
    against — a model that thought and then said nothing has failed its
    request."""
    anthropic_provider.script(sse_anthropic([
        anth({"type": "content_block_start", "index": 0,
              "content_block": {"type": "thinking", "thinking": ""}}),
        anth({"type": "content_block_delta", "index": 0,
              "delta": {"type": "thinking_delta", "thinking": "Ich überlege noch."}}),
        # The signature that closes a thinking block: recognised, and kept out
        # of both fields. It is not text, and this platform never hands a
        # thinking block back to the API.
        anth({"type": "content_block_delta", "index": 0,
              "delta": {"type": "signature_delta", "signature": "EqQBCgIYAhIM"}}),
        *anthropic_end(),
    ]))
    tokens, result = run_anthropic()
    assert tokens == []
    assert result["content"] == ""
    assert result["thinking"] == "Ich überlege noch."


def test_an_anthropic_answer_that_ran_out_of_room_is_marked_length(anthropic_provider, ledger):
    """The safety-critical one, and the reason stop_reason is translated at all.
    The image check blocks a verdict that stopped because it had no room left,
    and it recognises that state by the word 'length'. Anthropic calls it
    'max_tokens'. If the mapping went missing, a truncated rating would read as
    a finished one and nothing would say so."""
    anthropic_provider.script(sse_anthropic([
        text_block(),
        text_delta("Das Bild zeigt einen"),
        *anthropic_end(stop_reason="max_tokens"),
    ]))
    _, result = run_anthropic()
    assert result["finish_reason"] == "length"
    assert result["content"] == "Das Bild zeigt einen"


@pytest.mark.parametrize("stop_reason,expected", [
    ("end_turn", "stop"),
    ("stop_sequence", "stop"),
    ("max_tokens", "length"),
    ("tool_use", "tool_calls"),
    # Not in the table, and deliberately not forced into it: neither a finished
    # answer nor a truncated one, so it arrives as itself rather than as a
    # normal ending that no guard would look at twice.
    ("refusal", "refusal"),
    ("pause_turn", "pause_turn"),
])
def test_every_stop_reason_arrives_under_a_name_the_platform_reads(
        anthropic_provider, ledger, stop_reason, expected):
    anthropic_provider.script(sse_anthropic([
        text_block(), text_delta("kurz"), *anthropic_end(stop_reason=stop_reason),
    ]))
    _, result = run_anthropic()
    assert result["finish_reason"] == expected


def test_a_ping_changes_nothing(anthropic_provider, ledger):
    """Streams may carry any number of them, and one arriving between deltas
    must not end the answer, split it, or count as a frame with meaning."""
    anthropic_provider.script(sse_anthropic([
        anth({"type": "ping"}),
        text_block(),
        anth({"type": "ping"}),
        text_delta("Der Fluss"),
        anth({"type": "ping"}),
        text_delta(" steigt."),
        *anthropic_end(),
    ]))
    tokens, result = run_anthropic()
    assert tokens == ["Der Fluss", " steigt."]
    assert result["content"] == "Der Fluss steigt."
    assert result["finish_reason"] == "stop"


def test_an_unknown_event_type_is_ignored_rather_than_treated_as_a_fault(
        anthropic_provider, ledger):
    """The API's versioning policy says new event types may appear. A reader
    that failed on one would break on a day nobody deployed anything."""
    anthropic_provider.script(sse_anthropic([
        text_block(),
        anth({"type": "an_event_type_from_a_later_api_version", "index": 0}),
        text_delta("trotzdem"),
        *anthropic_end(),
    ]))
    _, result = run_anthropic()
    assert result["content"] == "trotzdem"


def test_an_error_event_raises_with_what_the_provider_actually_said(
        anthropic_provider, ledger, no_waiting):
    """This dialect can report a failure inside a 200 response — an overload
    arrives as an event, where the other dialect would have answered 529. The
    message is raised as it came, because the classifier that decides whether
    the turn may try another candidate reads that text."""
    anthropic_provider.script(sse_anthropic([
        anth({"type": "message_start", "message": {"usage": {"input_tokens": 4}}}),
        anth({"type": "error",
              "error": {"type": "overloaded_error", "message": "Overloaded"}}),
    ]))
    with pytest.raises(Exception) as excinfo:
        run_anthropic()
    message = str(excinfo.value)
    assert "overloaded_error" in message
    assert "Overloaded" in message
    # Bytes had already been read, so nothing is asked again.
    assert len(anthropic_provider.requests) == 1
    assert no_waiting == []

    from my_app.routes.chat_routes import is_retriable_llm_error
    assert is_retriable_llm_error(excinfo.value) is True


def test_two_content_blocks_do_not_mix_however_they_are_indexed(anthropic_provider, ledger):
    """Blocks are addressed by index, and a delta belongs to the block that
    index opened. A tool call's argument slices carry no name of their own, so
    losing the index would concatenate them into the text — or into the wrong
    tool."""
    anthropic_provider.script(sse_anthropic([
        text_block(0),
        text_delta("Ich schaue nach.", 0),
        anth({"type": "content_block_stop", "index": 0}),
        anth({"type": "content_block_start", "index": 1,
              "content_block": {"type": "tool_use", "id": "toolu_1",
                                "name": "lookup_reference", "input": {}}}),
        anth({"type": "content_block_delta", "index": 1,
              "delta": {"type": "input_json_delta", "partial_json": '{"q": '}}),
        anth({"type": "content_block_delta", "index": 1,
              "delta": {"type": "input_json_delta", "partial_json": '"Fluss"}'}}),
        anth({"type": "content_block_stop", "index": 1}),
        *anthropic_end(stop_reason="tool_use"),
    ]))
    tokens, result = run_anthropic(tools=[{"name": "lookup_reference"}])
    assert tokens == ["Ich schaue nach."]
    assert result["content"] == "Ich schaue nach."
    assert result["tool_calls"] == [{
        "id": "toolu_1",
        "type": "function",
        "function": {"name": "lookup_reference", "arguments": '{"q": "Fluss"}'},
    }]
    assert result["finish_reason"] == "tool_calls"


def test_two_tool_calls_keep_their_own_arguments(anthropic_provider, ledger):
    anthropic_provider.script(sse_anthropic([
        anth({"type": "content_block_start", "index": 0,
              "content_block": {"type": "tool_use", "id": "a", "name": "first",
                                "input": {}}}),
        anth({"type": "content_block_delta", "index": 0,
              "delta": {"type": "input_json_delta", "partial_json": '{"n": 1}'}}),
        anth({"type": "content_block_start", "index": 1,
              "content_block": {"type": "tool_use", "id": "b", "name": "second",
                                "input": {}}}),
        anth({"type": "content_block_delta", "index": 1,
              "delta": {"type": "input_json_delta", "partial_json": '{"n": 2}'}}),
        *anthropic_end(stop_reason="tool_use"),
    ]))
    _, result = run_anthropic(tools=[{"name": "first"}, {"name": "second"}])
    assert [(tc["id"], tc["function"]["arguments"]) for tc in result["tool_calls"]] \
        == [("a", '{"n": 1}'), ("b", '{"n": 2}')]


def test_the_tool_call_shape_is_the_one_the_other_dialect_produces(anthropic_provider,
                                                                   ledger):
    """So that a tool loop upstream cannot tell which provider answered."""
    anthropic_provider.script(sse_anthropic([
        anth({"type": "content_block_start", "index": 0,
              "content_block": {"type": "tool_use", "id": "t1", "name": "note",
                                "input": {}}}),
        anth({"type": "content_block_delta", "index": 0,
              "delta": {"type": "input_json_delta", "partial_json": "{}"}}),
        *anthropic_end(stop_reason="tool_use"),
    ]))
    _, result = run_anthropic(tools=[{"name": "note"}])
    assert set(result["tool_calls"][0]) == {"id", "type", "function"}
    assert set(result["tool_calls"][0]["function"]) == {"name", "arguments"}


def test_the_anthropic_stream_ends_at_message_stop_without_a_done_sentinel(
        anthropic_provider, ledger):
    """There is no [DONE] here. A reader waiting for one would hold the
    connection open until the socket closed under it."""
    anthropic_provider.script(sse_anthropic([
        text_block(), text_delta("fertig"), *anthropic_end(),
    ]))
    _, result = run_anthropic()
    assert result["content"] == "fertig"


def test_an_anthropic_stream_cut_before_message_stop_is_not_a_finished_answer(
        anthropic_provider, ledger):
    anthropic_provider.script(sse_cut_but_terminated([
        text_block(), text_delta("Das Bild zeigt einen"),
    ]))
    with pytest.raises(Exception) as excinfo:
        run_anthropic()
    assert "without saying it had finished" in str(excinfo.value)


def test_an_anthropic_stop_reason_without_message_stop_is_still_not_the_end(
        anthropic_provider, ledger):
    """Where the two dialects part, and deliberately the stricter reading. In
    chat-completions the finish_reason rides on the last chunk of the answer.
    Here the stop_reason arrives in message_delta, which this API sends BEFORE
    the final usage counts and before the message is closed — so a stream cut
    between message_delta and message_stop is not an answer that ended, it is an
    answer interrupted just after it said how it would end."""
    anthropic_provider.script(sse_cut_but_terminated([
        text_block(), text_delta("kurz"),
        anth({"type": "message_delta", "delta": {"stop_reason": "end_turn"}}),
    ]))
    with pytest.raises(Exception) as excinfo:
        run_anthropic()
    assert "without saying it had finished" in str(excinfo.value)


def test_two_different_stop_reasons_are_refused_in_this_dialect_too(
        anthropic_provider, ledger):
    """Held on both grammars, because the guards downstream read one field and
    do not know which dialect filled it."""
    anthropic_provider.script(sse_anthropic([
        text_block(), text_delta("kurz"),
        anth({"type": "message_delta", "delta": {"stop_reason": "max_tokens"}}),
        anth({"type": "message_delta", "delta": {"stop_reason": "end_turn"}}),
        anth({"type": "message_stop"}),
    ]))
    with pytest.raises(Exception) as excinfo:
        run_anthropic()
    message = str(excinfo.value)
    assert "'length'" in message and "'stop'" in message


def test_the_anthropic_request_carries_the_ceiling_its_api_requires(anthropic_provider,
                                                                     ledger):
    """max_tokens is a required field here, so a number has to stand in it. It
    is the model ceiling, and no temperature is invented for a config that
    named none — the model applies its own, as it did before this call was
    streamed."""
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"),
                                             *anthropic_end()]))
    run_anthropic()
    sent = anthropic_provider.requests[0]
    assert sent["max_tokens"] == oss.ANTHROPIC_MAX_TOKENS_CEILING >= 64000
    assert "temperature" not in sent
    assert sent["stream"] is True
    # stream_options belongs to the other dialect and must not leak into this
    # payload: the re-ask in the opener is keyed on the field being present.
    assert "stream_options" not in sent


def test_a_cap_and_a_temperature_a_caller_asked_for_are_forwarded(anthropic_provider,
                                                                   ledger):
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"),
                                             *anthropic_end()]))
    run_anthropic(temperature=0.2, max_tokens=64000)
    sent = anthropic_provider.requests[0]
    assert sent["max_tokens"] == 64000
    assert sent["temperature"] == 0.2


def test_anthropic_usage_from_both_places_reaches_the_ledger(anthropic_provider, ledger):
    """The input count arrives with message_start and the output count with
    message_delta, so neither frame alone carries the whole line."""
    anthropic_provider.script(sse_anthropic([
        anth({"type": "message_start", "message": {"usage": {"input_tokens": 41,
                                                             "output_tokens": 1}}}),
        text_block(), text_delta("kurz"),
        *anthropic_end(output_tokens=7),
    ]))
    run_anthropic(stage="stage2")
    assert ledger.entries == [{"model": MODEL, "provider": ANTHROPIC_PROVIDER,
                               "stage": "stage2", "input_tokens": 41,
                               "output_tokens": 7}]


def test_an_anthropic_answer_that_says_nothing_at_all_raises(anthropic_provider, ledger):
    anthropic_provider.script(sse_anthropic([*anthropic_end()]))
    with pytest.raises(Exception) as excinfo:
        run_anthropic()
    assert ANTHROPIC_PROVIDER in str(excinfo.value)
    assert MODEL in str(excinfo.value)


def test_a_missing_anthropic_key_raises_before_anything_is_sent(monkeypatch,
                                                                anthropic_provider):
    monkeypatch.setitem(oss._ANTHROPIC_STYLE_PROVIDERS, ANTHROPIC_PROVIDER,
                        lambda: (anthropic_provider.url, ""))
    with pytest.raises(Exception) as excinfo:
        run_anthropic()
    assert "API Key not configured" in str(excinfo.value)
    assert anthropic_provider.requests == []


def test_a_524_before_the_first_anthropic_byte_is_asked_again(anthropic_provider, ledger,
                                                              no_waiting):
    """The opener is shared, so this dialect inherits the retry the other one
    has — the same twelve statuses, the same three attempts, and only before
    the first byte. That is what let the retry loop around the unstreamed call
    be removed rather than merely moved."""
    anthropic_provider.script(
        http_error(524, CLOUDFLARE_524),
        sse_anthropic([text_block(), text_delta("endlich"), *anthropic_end()]),
    )
    _, result = run_anthropic()
    assert result["content"] == "endlich"
    assert len(anthropic_provider.requests) == 2


def test_the_blocking_anthropic_entry_point_returns_the_same_four_keys(
        anthropic_provider, ledger):
    """A caller that switches dialects has nothing to rewrite, and the guards
    that read these keys keep working whichever one answered."""
    frames = [text_block(), text_delta("Ja, sicher."), *anthropic_end("max_tokens")]
    anthropic_provider.script(sse_anthropic(frames), sse_anthropic(list(frames)))
    _, streamed = run_anthropic()
    blocking = oss.call_anthropic_style(ANTHROPIC_PROVIDER,
                                        [{"role": "user", "content": "hallo"}], MODEL)
    assert blocking == streamed
    assert set(blocking) == {"content", "thinking", "tool_calls", "finish_reason"}
    assert blocking["finish_reason"] == "length"


def test_the_two_dialect_tables_do_not_overlap():
    """Each reader looks its provider up in its own table. Anthropic in the
    chat-completions table would point /v1/chat/completions at an address
    that speaks /v1/messages."""
    assert ANTHROPIC_PROVIDER not in oss._OPENAI_STYLE_PROVIDERS
    assert ANTHROPIC_PROVIDER in oss._ANTHROPIC_STYLE_PROVIDERS
    assert set(oss._OPENAI_STYLE_PROVIDERS).isdisjoint(oss._ANTHROPIC_STYLE_PROVIDERS)


def test_there_is_exactly_one_cloud_transport_in_the_tree():
    """Project rule 13, held against the shape a second dialect invites: two
    readers side by side, one per dialect. There is one opener and two grammars
    instead, so the opener is what has to stay unique — a second dialect that
    brought its own would be the fifth copy of this frame loop in this tree.

    The probe is the opener's name and not iter_lines: the local station has
    stream readers of its own (llm_client, text_client, text_routes and the
    proxy in chat_routes), which are a different subject and not cloud
    providers."""
    root = Path(__file__).resolve().parents[1]
    owners = []
    for path in list(root.glob("my_app/**/*.py")) + list(root.glob("schemas/**/*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "def _stream_sse" in text:
            owners.append(str(path.relative_to(root)))
    assert owners == ["my_app/services/openai_style_stream.py"]


# ---------------------------------------------------------------------------
# One entry point, the dialect from the table (2026-09-12)
# ---------------------------------------------------------------------------
# Until then every caller kept a ladder of prefixes and picked an entry point
# itself, and the chat surface's ladder sent 'anthropic/' and 'openai/' to
# OpenRouter. stream_chat/call_chat name a provider; config/llm_providers.json
# says what it speaks.

def _last_request_shape(p: _Provider) -> str:
    """Which dialect the last request to a fake provider was spoken in, by the
    path it arrived on: each dialect has an endpoint of its own."""
    path = p.paths[-1]
    if path.endswith("/chat/completions"):
        return "chat_completions"
    if path.endswith("/messages"):
        return "messages"
    return path


def test_call_chat_speaks_chat_completions_to_a_provider_the_table_says_does(provider, ledger):
    provider.script(sse_ok([sse(chunk({"content": "ja"}, finish="stop"))]))
    result = oss.call_chat(PROVIDER, [{"role": "user", "content": "hallo"}], MODEL)
    assert result["content"] == "ja"
    assert _last_request_shape(provider) == "chat_completions"
    assert "stream_options" in provider.requests[0]


def test_call_chat_speaks_messages_to_a_provider_the_table_says_does(anthropic_provider, ledger):
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("ja"), *anthropic_end()]))
    result = oss.call_chat(ANTHROPIC_PROVIDER, [{"role": "user", "content": "hallo"}], MODEL)
    assert result["content"] == "ja"
    assert _last_request_shape(anthropic_provider) == "messages"
    assert "stream_options" not in anthropic_provider.requests[0]


def test_call_chat_refuses_a_name_the_table_does_not_carry():
    with pytest.raises(Exception) as excinfo:
        oss.call_chat("no-such-provider", [{"role": "user", "content": "hallo"}], MODEL)
    assert "no-such-provider" in str(excinfo.value)


def test_no_temperature_means_the_engines_default_on_chat_completions_and_none_on_messages(
        provider, anthropic_provider, ledger):
    """The pipeline engine always sent 0.7 to a chat-completions provider where
    a config named no temperature, and nothing to the messages dialect, where
    the model applies its own. Both defaults live in the reader now."""
    provider.script(sse_ok([sse(chunk({"content": "x"}, finish="stop"))]))
    oss.call_chat(PROVIDER, [{"role": "user", "content": "hallo"}], MODEL)
    assert provider.requests[0]["temperature"] == 0.7
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"), *anthropic_end()]))
    oss.call_chat(ANTHROPIC_PROVIDER, [{"role": "user", "content": "hallo"}], MODEL)
    assert "temperature" not in anthropic_provider.requests[0]


def test_the_messages_dialect_says_the_platforms_conversation_its_own_way(anthropic_provider,
                                                                          ledger):
    """The chat surface keeps its history in the chat-completions shape. On
    this dialect the system prompt is a top-level field, a tool carries an
    input_schema, a tool call is a tool_use block with an object for input,
    and a tool's answer is a tool_result block in a user turn."""
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"), *anthropic_end()]))
    history = [
        {"role": "system", "content": "Antworte kurz."},
        {"role": "user", "content": "Wie spät?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "clock", "arguments": "{\"zone\": \"Europe/Berlin\"}"}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "14:00"},
    ]
    tools = [{"type": "function", "function": {
        "name": "clock", "description": "the time",
        "parameters": {"type": "object", "properties": {"zone": {"type": "string"}}}}}]
    oss.call_chat(ANTHROPIC_PROVIDER, history, MODEL, tools=tools)
    sent = anthropic_provider.requests[0]
    assert sent["system"] == "Antworte kurz."
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant", "user"]
    assert sent["messages"][1]["content"] == [
        {"type": "tool_use", "id": "call_1", "name": "clock", "input": {"zone": "Europe/Berlin"}}]
    assert sent["messages"][2]["content"] == [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "14:00"}]
    assert sent["tools"] == [{"name": "clock", "description": "the time",
                              "input_schema": {"type": "object",
                                               "properties": {"zone": {"type": "string"}}}}]


def test_the_answers_to_one_round_of_tool_calls_go_back_in_one_user_turn(anthropic_provider,
                                                                        ledger):
    """The chat surface appends one tool message per call. This API wants the
    results of one round in ONE user turn, and its documentation says that
    results split over turns teach the model to stop calling tools in
    parallel."""
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"), *anthropic_end()]))
    history = [
        {"role": "user", "content": "Wie spät ist es in Berlin und in Seoul?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "clock", "arguments": "{\"zone\": \"Europe/Berlin\"}"}},
            {"id": "c2", "type": "function",
             "function": {"name": "clock", "arguments": "{\"zone\": \"Asia/Seoul\"}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "14:00"},
        {"role": "tool", "tool_call_id": "c2", "content": "21:00"},
    ]
    oss.call_chat(ANTHROPIC_PROVIDER, history, MODEL)
    sent = anthropic_provider.requests[0]
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant", "user"]
    assert sent["messages"][2]["content"] == [
        {"type": "tool_result", "tool_use_id": "c1", "content": "14:00"},
        {"type": "tool_result", "tool_use_id": "c2", "content": "21:00"}]


def test_a_second_round_of_tool_answers_is_its_own_turn(anthropic_provider, ledger):
    """Merging stops at the turn boundary: the results of the NEXT round go
    into the next user turn, after the assistant's next calls."""
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"), *anthropic_end()]))
    call = lambda cid: {"id": cid, "type": "function",
                        "function": {"name": "clock", "arguments": "{}"}}
    history = [
        {"role": "user", "content": "?"},
        {"role": "assistant", "content": "", "tool_calls": [call("c1")]},
        {"role": "tool", "tool_call_id": "c1", "content": "a"},
        {"role": "assistant", "content": "", "tool_calls": [call("c2")]},
        {"role": "tool", "tool_call_id": "c2", "content": "b"},
    ]
    oss.call_chat(ANTHROPIC_PROVIDER, history, MODEL)
    sent = anthropic_provider.requests[0]
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant", "user",
                                                     "assistant", "user"]
    assert [b["tool_use_id"] for b in sent["messages"][2]["content"]] == ["c1"]
    assert [b["tool_use_id"] for b in sent["messages"][4]["content"]] == ["c2"]


def test_an_assistant_turn_before_the_first_user_turn_is_left_out(anthropic_provider, ledger):
    """The API takes a user turn first. A surface that opens with a greeting
    of its own hands it over as an assistant turn; sent as such, the request
    is a 400 before the person's words are read."""
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"), *anthropic_end()]))
    history = [
        {"role": "system", "content": "Antworte kurz."},
        {"role": "assistant", "content": "Hallo, womit kann ich helfen?"},
        {"role": "user", "content": "Wie spät?"},
    ]
    oss.call_chat(ANTHROPIC_PROVIDER, history, MODEL)
    sent = anthropic_provider.requests[0]
    assert sent["system"] == "Antworte kurz."
    assert sent["messages"] == [{"role": "user", "content": "Wie spät?"}]


def test_whitespace_beside_a_tool_call_sends_the_call_alone(anthropic_provider, ledger):
    """A text block in this dialect is never empty; a call turn whose text was
    a bare newline sends the tool_use block alone, and an assistant turn that
    carried nothing at all is left out."""
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"), *anthropic_end()]))
    history = [
        {"role": "user", "content": "?"},
        {"role": "assistant", "content": "\n", "tool_calls": [
            {"id": "c", "type": "function", "function": {"name": "look", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c", "content": "ein Bild"},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "und?"},
    ]
    oss.call_chat(ANTHROPIC_PROVIDER, history, MODEL)
    sent = anthropic_provider.requests[0]
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant", "user", "user"]
    assert sent["messages"][1]["content"] == [
        {"type": "tool_use", "id": "c", "name": "look", "input": {}}]


def test_a_refusal_that_arrives_with_nothing_else_is_raised_as_a_refusal(anthropic_provider,
                                                                          ledger):
    """This dialect declines with HTTP 200, stop_reason "refusal" and no
    content at all. Raised as "empty response" it read as an availability
    failure to the chain and was tried again on the next candidate."""
    anthropic_provider.script(sse_anthropic([*anthropic_end(stop_reason="refusal")]))
    with pytest.raises(Exception) as excinfo:
        oss.call_chat(ANTHROPIC_PROVIDER, [{"role": "user", "content": "hallo"}], MODEL)
    assert "refused" in str(excinfo.value)
    assert "empty response" not in str(excinfo.value)


def test_a_refusal_that_arrives_with_words_is_the_answer_with_that_reason(anthropic_provider,
                                                                           ledger):
    """The other case: text came, and then the stop. That is an answer, with
    finish_reason 'refusal' for the caller to read, not an exception."""
    anthropic_provider.script(sse_anthropic([
        text_block(), text_delta("Dazu "), *anthropic_end(stop_reason="refusal")]))
    result = oss.call_chat(ANTHROPIC_PROVIDER, [{"role": "user", "content": "hallo"}], MODEL)
    assert result["content"] == "Dazu "
    assert result["finish_reason"] == "refusal"


@pytest.mark.parametrize("dialect", ["chat_completions", "messages"])
def test_nothing_a_caller_passes_can_stand_in_for_the_conversation(
        provider, anthropic_provider, ledger, dialect):
    """extra_payload carries one provider's private fields. It is written
    into the request first, so the model, the conversation and the streaming
    switch are the reader's, whatever a caller put in it -- and on the
    messages dialect so is the ceiling, which that API requires as a number.
    (What the table may put into such a payload is tested with the table.)"""
    history = [{"role": "user", "content": "hallo"}]
    smuggled = {"stream": False, "messages": [], "model": "another"}
    if dialect == "chat_completions":
        provider.script(sse_ok([sse(chunk({"content": "x"}, finish="stop"))]))
        oss.call_chat(PROVIDER, history, MODEL, extra_payload=smuggled)
        sent = provider.requests[0]
    else:
        anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"), *anthropic_end()]))
        oss.call_chat(ANTHROPIC_PROVIDER, history, MODEL,
                      extra_payload={**smuggled, "max_tokens": 5})
        sent = anthropic_provider.requests[0]
        assert sent["max_tokens"] == oss.ANTHROPIC_MAX_TOKENS_CEILING
    assert sent["model"] == MODEL
    assert sent["stream"] is True
    assert sent["messages"][0]["role"] == "user"


def test_the_messages_dialect_puts_the_picture_in_what_the_person_wrote(anthropic_provider,
                                                                        ledger):
    anthropic_provider.script(sse_anthropic([text_block(), text_delta("x"), *anthropic_end()]))
    history = [
        {"role": "user", "content": "was ist das?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c", "type": "function", "function": {"name": "look", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c", "content": "ein Bild"},
    ]
    oss.call_chat(ANTHROPIC_PROVIDER, history, MODEL, image_b64="QUJD")
    sent = anthropic_provider.requests[0]
    # The picture sits in the person's message, and the tool's answer -- a user
    # turn in this dialect -- is untouched.
    assert sent["messages"][0]["content"][1]["source"]["data"] == "QUJD"
    assert sent["messages"][2]["content"] == [
        {"type": "tool_result", "tool_use_id": "c", "content": "ein Bild"}]


def test_stream_chat_withholds_the_picture_from_a_connection_that_takes_none(monkeypatch,
                                                                            ledger):
    """The floor under services/model_capabilities, declared in the table as
    "image_input": false and applied where the request is built, so no caller
    can pass it by."""
    from my_app.services import llm_providers as lp
    p = _Provider()
    monkeypatch.setitem(lp.providers(), "blind-provider", {
        "label": "Blind", "dialect": lp.CHAT_COMPLETIONS, "api_url": p.url,
        "env_var": "BLIND_API_KEY", "key_file": "blind.key", "key_prefix": "",
        "image_input": False,
    })
    monkeypatch.setitem(oss._OPENAI_STYLE_PROVIDERS, "blind-provider",
                        lambda: (p.url, "test-key"))
    try:
        p.script(sse_ok([sse(chunk({"content": "x"}, finish="stop"))]))
        oss.call_chat("blind-provider", [{"role": "user", "content": "was ist das?"}], MODEL,
                      image_b64="QUJD")
        sent = p.requests[0]
    finally:
        p.close()
    assert sent["messages"] == [{"role": "user", "content": "was ist das?"}]

