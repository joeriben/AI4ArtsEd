"""
The one reader for this platform's cloud providers.

Five of this installation's cloud providers — mammouth, openrouter, mistral,
ionos and openai — speak OpenAI chat-completions, and every one of them can
hand its answer over piece by piece instead of in one block. That is ONE reader
for all five, and one reader for every part of the platform that talks to them:
what differs between the providers is the address and the key, and both come
out of the table below.

The sixth, Anthropic, speaks its own dialect and joined on 2026-09-04. It did
not become a second reader. Reading a streamed answer is a transport and a
grammar; only the grammar differs between the two, so there is one opener here
and two grammars handed to it — see "One opener, two grammars" below. The
module keeps the name it was given when it served one dialect, because callers
import it by that name.

It lived in my_app/routes/chat_routes.py until 2026-09-03. It sits here because
a routes module is not a place two non-route callers can import from: the
pipeline engine and the image check each grew a provider table of their own
while the reader was locked away, and those tables drifted apart — the IONOS
address in one of them had stopped pointing at IONOS. Two
implementations of one behaviour are a bug, so there is one here and the
callers import it.

Streaming is not a nicety. Two things rest on it:

  * A room reads slower than a model writes. Children in a workshop must not
    wait for complete text blocks when they can already read the incoming
    text. The wait for the last token is dead time among people.

  * The mammouth endpoint sits behind Cloudflare, which answers HTTP 524 when
    the origin produces no byte for about a hundred seconds. Measured on the
    development box on 2026-09-03: the same reasoning request died at 524
    after ~125 s unstreamed, and finished in 1.6 s with the first delta at
    1.29 s when asked with stream=True. Streaming removes the failure class
    rather than working around it.

This module decides nothing about content. It reports what the provider sent —
the answer, the reasoning, the tool calls, why the model stopped — and every
caller applies its own policy to that.
"""

import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import requests

# Every cloud answer this module opens says which model it is opening, on the
# connection the run is already holding open (`note_dispatch`). The comment that
# stood here named a register in the GPU service that was removed on 2026-09-09.
from config import ANTHROPIC_MAX_TOKENS_CEILING, LLM_TIMEOUT
from my_app.services.streaming_response import note_dispatch
from my_app.services.usage_tracker import get_usage_tracker, extract_usage
from my_app.services.llm_providers import (
    CHAT_COMPLETIONS, MESSAGES, credentials, names as provider_names,
    provider as provider_entry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Where to reach each provider, and with which key
# ---------------------------------------------------------------------------
# One table, config/llm_providers.json, read through services/llm_providers.
# Until 2026-09-12 six copies of the same loader stood here, one per provider,
# each with its own address, key file and environment variable spelled out; the
# pipeline engine kept a seventh copy of the same facts.


# The version of the messages API this platform asks for. Anthropic requires
# the header on every request and pins behaviour to the date it names.
ANTHROPIC_API_VERSION = "2023-06-01"

# The ceiling Anthropic's required max_tokens field carries and the (connect,
# read) timeout of every LLM call are config.py's; the read side stays
# unbounded there because deep-reasoning models (e.g. mammouth/qwen3.7-plus)
# can take minutes to respond, and a capped read timeout silently truncates
# the call and triggers fallback to a different, weaker model - corrupting
# model provenance.


# Also from chat_routes.py, and also unchanged. It travelled with the reader
# because the reader calls it: leaving it behind would have meant either a
# second copy of it here, or this module importing a routes module, and the
# whole point of the move is that it does not.
def _inject_image_into_messages(messages: list, image_b64: str, provider_format: str) -> list:
    """
    Inject a base64 image into the last user message using provider-specific format.

    Args:
        messages: List of message dicts
        image_b64: Base64-encoded image string
        provider_format: One of 'openai', 'anthropic'

    Returns:
        New list with image injected into the last user message
    """
    import copy
    result = copy.deepcopy(messages)

    # Find last user message
    for i in range(len(result) - 1, -1, -1):
        if result[i].get('role') == 'user':
            text_content = result[i].get('content', '')

            if provider_format == 'openai':
                result[i]['content'] = [
                    {"type": "text", "text": text_content},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            elif provider_format == 'anthropic':
                result[i]['content'] = [
                    {"type": "text", "text": text_content},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}}
                ]

            break

    return result


# ---------------------------------------------------------------------------
# The answer while it is being written
# ---------------------------------------------------------------------------
# Which of the providers above can be reached this way, and with whose
# credentials. Adding a further OpenAI-compatible provider is one line here:
# openai was added on 2026-09-04 and cost exactly that line plus its getter.
# Built from the table, keyed by name so a test can stand a provider of its
# own in here. Each value answers (api_url, api_key) when called.
_OPENAI_STYLE_PROVIDERS = {
    name: (lambda n=name: credentials(n)) for name in provider_names(CHAT_COMPLETIONS)
}


# One table per dialect, both built from the provider table. Each reader
# below looks its provider up in its own, so a chat-completions request is
# never built for a /v1/messages address or the other way round. Which
# dialect an id reaches is decided once, in stream_chat, from the table.
_ANTHROPIC_STYLE_PROVIDERS = {
    name: (lambda n=name: credentials(n)) for name in provider_names(MESSAGES)
}


# Statuses worth asking again about, and how often. Taken from the retry loop
# that already stood in the pipeline engine's streaming Mistral call: the 52x
# block is Cloudflare's, and 524 in particular is the origin-timeout this
# reader exists to prevent — it can still arrive when the provider's own
# upstream stalls before the first byte.
_RETRY_STATUSES = (429, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527)
_MAX_ATTEMPTS = 3

# How long a provider may ask us to wait before we stop waiting and let the
# failure travel. The wait itself is the provider's to name -- every service in
# both dialect lists sends `Retry-After` on 429 and 503, and until 2026-09-09
# nothing on this platform read that header. The doubling below gave up about
# four seconds after the first 429, whatever number the provider had named, and
# the chain then fell through to a DIFFERENT model: the same harm to provenance
# this module's read timeout exists to prevent. This ceiling is ours, not the
# provider's -- above it the service is saying it is gone for a while, and a
# room waiting in silence is worse than an answer that says what happened.
_RETRY_AFTER_CEILING = 120.0


def _retry_after_seconds(response) -> Optional[float]:
    """The wait the provider named, in seconds. ``None`` when it named none.

    RFC 9110 allows both forms and providers use both: a count of seconds, or
    an HTTP date.
    """
    raw = (response.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def _merge_tool_call_delta(acc: dict, delta_calls: list):
    """Collect tool calls arriving in fragments, keyed by their index.

    A streamed tool call comes apart across chunks: the id and the function
    name in the first one, the arguments in slices after it. Reassembled here
    into exactly the shape the blocking path returns, so the tool loop upstream
    cannot tell the two transports apart.
    """
    for i, tc in enumerate(delta_calls or []):
        if not isinstance(tc, dict):
            continue
        idx = tc.get("index", i)
        slot = acc.setdefault(idx, {"id": "", "type": "function",
                                    "function": {"name": "", "arguments": ""}})
        if tc.get("id"):
            slot["id"] = tc["id"]
        if tc.get("type"):
            slot["type"] = tc["type"]
        fn = tc.get("function") or {}
        if fn.get("name"):
            slot["function"]["name"] += fn["name"]
        if fn.get("arguments"):
            slot["function"]["arguments"] += fn["arguments"]


# ---------------------------------------------------------------------------
# One opener, two grammars
# ---------------------------------------------------------------------------
# Reading a streamed answer is two jobs, and only one of them differs between
# providers. TRANSPORT is opening the request, asking again for the twelve
# statuses that mean "not yet" and only before the first byte, the
# stream_options re-ask, the message a non-200 is raised with, the UTF-8 rule
# for a body whose charset nobody named, walking the SSE frames, and closing
# the connection when the answer ends or breaks. GRAMMAR is what one frame
# MEANS. Every provider here shares the first; only the second differs.
#
# So _stream_sse below is the one opener and a grammar object is handed to it.
# Anthropic was the last cloud call on this platform that sent its request and
# then waited for the whole answer in silence (until 2026-09-04): it could not
# join the other five when they were streamed because it speaks its own
# dialect, and a second reader beside this one would have been the fifth copy
# of the same frame loop in this tree. It is a second grammar instead.


class _Answer:
    """The answer as it accumulates: written by a grammar, read by the opener.

    `usage` holds an object shaped for extract_usage — one with a "usage" key —
    because the two dialects report their token counts in different places and
    the ledger wants one shape.
    """

    def __init__(self):
        self.content = ""
        self.thinking = ""
        self.tool_acc: dict = {}
        self.usage: Optional[dict] = None
        self.finish_reason: Optional[str] = None


def _note_terminal_reason(answer: _Answer, reason: str):
    """Record why the model stopped, and refuse a second, different answer to it.

    A stream carries ONE terminal reason: the chat-completions spec puts a
    finish_reason on the final chunk of a choice, and the messages API sends
    one stop_reason in its message_delta. A provider that names a second
    different one has contradicted itself, and neither of the two things a
    reader could quietly do here is safe. Keeping the first loses a 'length'
    that arrived late. Keeping the last is what this reader did until
    2026-09-04, and it let 'length' be overwritten by 'stop' — a truncated
    answer passing for a finished one at every guard that reads this field,
    which is all of them: the image check, the kids/youth text gate and the
    Llama-Guard escalation each recognise a cut-off verdict by the word
    'length' and by nothing else.

    So a second DIFFERENT value is raised rather than resolved. The same value
    twice is a repetition and changes nothing. Raising is what makes the state
    visible: every caller of this reader treats an exception as a failure it
    cannot resolve and blocks, and a stream whose own account of how it ended
    contradicts itself is exactly such a failure.
    """
    if answer.finish_reason is None or answer.finish_reason == reason:
        answer.finish_reason = reason
        return
    raise Exception(f"stream reported two different terminal reasons: "
                    f"{answer.finish_reason!r} then {reason!r} — "
                    f"a stream carries one, so neither can be trusted")


class _ChatCompletionsGrammar:
    """What one frame means to a provider that speaks OpenAI chat-completions."""

    def __init__(self):
        # Whether the [DONE] sentinel has arrived. Kept because a stream that
        # was cut and a stream that finished look alike from the frame loop:
        # both simply stop producing lines. See ended() below.
        self._saw_done = False
        # The shapes this stream has already reported as unreadable, as the
        # sentences that were logged for them. One line per shape and stream:
        # a shape repeats on every frame, and a log that repeats with it
        # buries the one thing it has to say.
        self._reported: set = set()

    def ended(self, answer: _Answer) -> bool:
        """Whether what has been read says the answer is OVER.

        Two things say so in this dialect and either one is enough: the [DONE]
        sentinel, and a finish_reason on some chunk. The spec puts a
        finish_reason on the last chunk of a choice, and the providers here
        write [DONE] after it — so the disjunction holds even where a proxy
        drops the sentinel, or where a provider ends without one. A stream that
        says neither did not end; it stopped.
        """
        return self._saw_done or answer.finish_reason is not None

    def feed(self, data: str, answer: _Answer):
        """Read one `data:` payload.

        Returns (pieces of the answer to hand on, whether the stream is over).
        """
        if data == "[DONE]":
            self._saw_done = True
            return (), True
        try:
            chunk = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return (), False
        if isinstance(chunk.get("usage"), dict):
            answer.usage = chunk
        choices = chunk.get("choices") or []
        if not choices:
            return (), False
        # Why finish_reason is read and returned, so that nobody deletes it as
        # an unused key: the image check refuses a child's picture when the
        # verdict model stopped because it ran out of room rather than because
        # it was done, since an answer cut off mid-sentence is not a verdict and
        # must not be read as one. That guard needs this field. A reader that
        # dropped it would let a truncated rating pass for a finished one, and
        # the failure would be silent.
        if choices[0].get("finish_reason"):
            _note_terminal_reason(answer, choices[0]["finish_reason"])
        delta = choices[0].get("delta") or {}
        tokens = []
        piece, reasoned = self._split_content(delta.get("content"))
        if piece:
            answer.content += piece
            tokens.append(piece)
        if reasoned:
            answer.thinking += reasoned
        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
        if isinstance(reasoning, str):
            answer.thinking += reasoning
        elif reasoning:
            # The field, in the shape the blocks come in. A provider that sends
            # a list in `content` is the reason this reader exists, and nothing
            # says it keeps a string here; read raw, this line raised the same
            # TypeError one line below the one that was fixed.
            spoken, thought = self._split_content(reasoning)
            answer.thinking += spoken + thought
        if reasoned and reasoning:
            self._report("reasoning in a content block and in reasoning_content "
                         "at once", read_as="both")
        if delta.get("tool_calls"):
            _merge_tool_call_delta(answer.tool_acc, delta["tool_calls"])
        return tokens, False

    def _split_content(self, content) -> tuple:
        """A delta's `content` as (answer text, reasoning), in either shape.

        This dialect puts a string here, and every provider in the table did
        until Mistral began serving Z.ai's GLM 5.3 as `zai-glm-5-3`. That model
        answers in content BLOCKS inside the chat-completions envelope: a list
        of {"type": "thinking", "thinking": [{"type": "text", "text": ...}]} and
        {"type": "text", "text": ...} objects, in the streamed delta as well as
        in a finished message. `answer.content += piece` raised TypeError on the
        first frame that carried one, so every role this installation pointed at
        that model failed before a word of the answer arrived (measured
        2026-09-22). Mistral's other models answer with a string, `zai-glm-5-2`
        among them, which is why the shape arrived on one model rather than on a
        whole column.

        Reasoning stays out of the answer text for the reason _content_delta
        gives on the other dialect: the pipeline engine refuses to let a model's
        reasoning stand in for an answer it never gave, and that refusal is only
        possible while the two are apart.

        Every shape that cannot be placed is REPORTED, and nothing is dropped
        without a word. A block the reader fails to read does not reach the
        room as a short answer: where the answer text ends up empty and the
        reasoning does not, the chat surface shows the reasoning in its place
        (its own policy, stated at the substitution in routes/chat_routes), so
        the model's reasoning stands in for the answer it did give, put there
        by this reader. Silence is also what let the block list itself run for
        as long as it did.
        """
        if isinstance(content, str):
            return content, ""
        if not isinstance(content, list):
            if content is not None:
                self._report(f"a content of type {type(content).__name__}")
            return "", ""
        text, reasoned = [], []
        for block in content:
            if isinstance(block, str):
                # A bare string inside a content list can be nothing else than
                # answer text, so it is read. It is also reported: no provider
                # in the table sends this shape, and one that starts to is
                # worth seeing before it is worth trusting.
                text.append(block)
                self._report("a bare string in the content list", read_as="text")
            elif not isinstance(block, dict):
                self._report(f"a content block of type {type(block).__name__}")
            elif block.get("type") == "text":
                text += self._block_text(block, "text", "a text block")
            elif block.get("type") == "thinking":
                reasoned += self._block_text(block, "thinking", "a thinking block")
            elif block.get("type") == "reasoning_content":
                inner = block.get("reasoningText")
                reasoned += self._block_text(inner if isinstance(inner, dict) else {},
                                             "text", "a reasoning_content block")
            else:
                # An f-string, so that a type which is not a string -- and so
                # could not be put in a set -- is reported instead of raising
                # out of the frame loop, which is the failure this whole
                # method exists to remove.
                self._report(f"a content block of type {block.get('type')!r}")
        return "".join(text), "".join(reasoned)

    def _block_text(self, block: dict, field: str, what: str) -> list:
        """The strings under `field` of one block, in either shape it comes in.

        Mistral nests: a thinking block's `thinking` is a LIST of
        {"type": "text", "text": ...} rather than a string. Nothing says a text
        block may not nest the same way, and a block that reads as empty is how
        an answer goes missing, so both shapes are read here rather than only
        the one that has been seen.

        A field that holds something and yields no text is reported. Silence
        there costs more than a gap: where the answer text is empty and the
        reasoning is not, the chat surface puts the reasoning in its place
        (its own policy, stated at the substitution in routes/chat_routes), so
        a dropped answer block is not a short answer on screen but the model's
        reasoning standing in for the answer it did give.
        """
        value = block.get(field)
        if isinstance(value, str):
            return [value]
        out = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    out.append(item["text"])
        if not out and value not in (None, "", [], {}):
            self._report(f"{what} whose {field} is a {type(value).__name__}")
        return out

    def _report(self, what: str, read_as: str = "nothing"):
        """Say ONCE per stream that a shape was met that this reader cannot place.

        Once, because the shape repeats on every frame of the stream. At all,
        because a shape dropped in silence is how a part of an answer passes
        for the whole of one -- and that is how the block list itself went
        unnoticed until a run broke on it.
        """
        if what in self._reported:
            return
        self._reported.add(what)
        logger.warning(f"[STREAM] {what} — read as {read_as}")


# Anthropic's stop_reason answers the same question as OpenAI's finish_reason
# and answers it in different words, so it is translated here rather than at
# every caller. "max_tokens" is the one that carries weight: the image check
# blocks a verdict that stopped because it ran out of room, and it recognises
# that state by the word "length". A reason this table does not know is passed
# through unchanged, so that a new one is visible as itself instead of being
# quietly rendered as a normal ending — "refusal" and "pause_turn" are neither
# a finished answer nor a truncated one, and no guard here should treat them as
# either.
_ANTHROPIC_STOP_REASONS = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


class _MessagesGrammar:
    """What one frame means to Anthropic's messages API.

    Named events rather than a run of interchangeable chunks: a message opens,
    content blocks open and close inside it addressed by index, and the message
    ends at message_stop — there is no [DONE] sentinel. Each event's data
    object repeats its name in a "type" field, so the `event:` lines the opener
    skips carry nothing this grammar needs.

    Anthropic's versioning policy says new event types may appear, so anything
    unrecognised is ignored rather than treated as a fault.
    """

    def __init__(self):
        # Content-block index -> the tool call that block opened. A tool call's
        # arguments arrive as JSON text in slices addressed to the index, and
        # nothing in a slice says which tool it belongs to.
        self._tool_blocks: dict = {}
        # Whether the event that ends a message has arrived. See ended() below.
        self._saw_message_stop = False

    def ended(self, answer: _Answer) -> bool:
        """Whether what has been read says the answer is OVER.

        One thing says so in this dialect: message_stop. There is no [DONE]
        sentinel here, and a stop_reason is not accepted in its place — it
        arrives in message_delta, which the API sends BEFORE the final usage
        counts and before the message is closed. A stream cut between the two
        has an answer that may still be growing.
        """
        return self._saw_message_stop

    def feed(self, data: str, answer: _Answer):
        try:
            event = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return (), False
        kind = event.get("type")

        if kind == "content_block_delta":
            return self._content_delta(event, answer), False

        if kind == "content_block_start":
            self._open_block(event, answer)
            return (), False

        if kind == "message_delta":
            stop = (event.get("delta") or {}).get("stop_reason")
            if stop:
                _note_terminal_reason(answer,
                                      _ANTHROPIC_STOP_REASONS.get(stop, stop))
            self._note_usage(event.get("usage"), answer)
            return (), False

        if kind == "message_start":
            self._note_usage((event.get("message") or {}).get("usage"), answer)
            return (), False

        if kind == "error":
            # An error arrives inside a 200 response here, so nothing in the
            # opener would notice one. It is raised carrying what the provider
            # actually said: the classifier that decides whether a turn may try
            # the next candidate reads that text, and a sentence of our own
            # would strand a retriable failure as an unrecognised one. No retry
            # follows — bytes have been read, and the opener asks again only
            # before the first of them.
            err = event.get("error") if isinstance(event.get("error"), dict) else {}
            raise Exception(f"anthropic stream error: "
                            f"{err.get('type') or 'error'}: "
                            f"{err.get('message') or data}")

        # message_stop ends the stream. content_block_stop, ping, and every
        # event type this grammar has not been taught change nothing.
        if kind == "message_stop":
            self._saw_message_stop = True
            return (), True
        return (), False

    def _open_block(self, event: dict, answer: _Answer):
        """Note a tool_use block, so its argument slices have somewhere to go."""
        block = event.get("content_block") or {}
        index = event.get("index")
        if block.get("type") != "tool_use" or index is None:
            return
        # Assembled into exactly the shape the chat-completions grammar
        # produces, so a tool loop upstream cannot tell the two dialects apart.
        slot = {"id": block.get("id") or "", "type": "function",
                "function": {"name": block.get("name") or "", "arguments": ""}}
        answer.tool_acc[index] = slot
        self._tool_blocks[index] = slot

    def _content_delta(self, event: dict, answer: _Answer):
        delta = event.get("delta") or {}
        kind = delta.get("type")
        if kind == "text_delta":
            piece = delta.get("text")
            if piece:
                answer.content += piece
                return [piece]
        elif kind == "thinking_delta":
            # Reasoning, and it stays out of content. The pipeline engine
            # refuses to let a model's reasoning stand in for an answer it never
            # gave, and that refusal is only possible while the two are apart.
            answer.thinking += delta.get("thinking") or ""
        elif kind == "input_json_delta":
            # Addressed to the block that opened it, which is why the index is
            # kept: two tool calls in one answer would otherwise concatenate
            # into one unparseable argument string.
            slot = self._tool_blocks.get(event.get("index"))
            if slot is not None:
                slot["function"]["arguments"] += delta.get("partial_json") or ""
        elif kind == "signature_delta":
            # The signature that lets a thinking block be handed back to the API
            # on a later turn. This platform never returns thinking blocks, and
            # a signature is not text anybody reads — so it is recognised here
            # and deliberately kept out of both fields, rather than falling
            # through as something unknown.
            pass
        return []

    @staticmethod
    def _note_usage(usage, answer: _Answer):
        """Collect the token counts, which arrive in two places.

        The input count comes with message_start and the output count with
        message_delta, and the message_delta counts are cumulative — so a later
        value replaces an earlier one instead of adding to it.
        """
        if not isinstance(usage, dict):
            return
        merged = dict((answer.usage or {}).get("usage") or {})
        merged.update({k: v for k, v in usage.items() if v is not None})
        answer.usage = {"usage": merged}


def _stream_sse(provider: str, api_url: str, headers: dict, payload: dict,
                grammar, model: str, stage: str):
    """Open one streamed request and read it to its end.

    Yields ('token', text) for each piece of the answer as it is written, then
    exactly one ('result', dict) carrying content, thinking, tool_calls and
    finish_reason. Nothing here looks inside a frame: what a frame means is the
    grammar's business, and everything this function does is true of every
    provider on the platform.

    Content and thinking stay apart. This reader does not decide whether a
    model's reasoning may stand in for an answer it never gave: the chat
    surface makes that substitution at its own call site, the pipeline engine
    deliberately refuses to and logs the reasoning instead. Reasoning is
    collected but never yielded as a token — what streams into a room is the
    answer, not the model's own muttering.
    """
    tag = f"[{stage.upper()}]"

    # What goes out, said from where it goes out — one call for both dialects,
    # because both of them end here. The service is put in front: its own model
    # id does not carry it (`glm-5.3`), and the platform reads a language step's
    # place off exactly that prefix (src/lib/modelPlace.ts). An id that brings
    # one of its own — OpenRouter's `deepseek/deepseek-v4-pro` — keeps it, and
    # the service in front of it is still where the text is sent.
    note_dispatch(f"{provider}/{model}", local=False)

    def _open(body):
        return requests.post(api_url, headers=headers, data=json.dumps(body),
                             stream=True, timeout=LLM_TIMEOUT)

    # Asking again is allowed HERE and nowhere after: nothing has been billed
    # and nothing has been shown while the provider has not sent a byte. Once
    # the stream is running, a break is a real failure and is raised — a retry
    # would pay for the first half of an answer a second time and could hand
    # the room two beginnings of one text.
    response = None
    for attempt in range(_MAX_ATTEMPTS):
        response = _open(payload)
        if response.status_code == 400 and "stream_options" in payload:
            logger.info(f"{tag} {provider} refused stream_options — asking again without it")
            response.close()
            payload.pop("stream_options")
            response = _open(payload)
        if response.status_code not in _RETRY_STATUSES or attempt == _MAX_ATTEMPTS - 1:
            break
        status = response.status_code
        named = _retry_after_seconds(response)
        if named is not None and named > _RETRY_AFTER_CEILING:
            # Left open on purpose: the block below reads the body off it.
            logger.warning(f"{tag} HTTP {status} from {provider} stream, "
                           f"Retry-After names {named:.0f}s — beyond the "
                           f"{_RETRY_AFTER_CEILING:.0f}s this reader waits")
            break
        response.close()
        wait = named if named is not None else (2 ** attempt) + random.uniform(0, 0.5)
        source = "Retry-After" if named is not None else "doubling"
        logger.warning(f"{tag} HTTP {status} from {provider} stream, "
                       f"attempt {attempt+1}/{_MAX_ATTEMPTS}, "
                       f"waiting {wait:.1f}s ({source})")
        time.sleep(wait)

    if response.status_code != 200:
        body = response.text
        response.close()
        # Both halves are load-bearing. is_retriable_llm_error in chat_routes.py
        # classifies a failure by looking for substrings, and a Cloudflare 524
        # currently only counts as retriable because the word "timeout" appears
        # in the HTML body Cloudflare returns. Drop either the status or the
        # body and a whole class of failures silently stops falling through.
        raise Exception(f"API Error: {response.status_code}\n{body}")

    # Server-sent events are defined as UTF-8. requests does not know that: given
    # a text/* content type with no charset parameter it falls back to
    # ISO-8859-1, and iter_lines(decode_unicode=True) then hands back every
    # umlaut as mojibake — on a platform whose working language is German, and
    # into a pipeline that would carry the damage into a generated image. A
    # provider that names its charset keeps the one it named; only the silent
    # case is decided here.
    if "charset" not in (response.headers.get("Content-Type") or "").lower():
        response.encoding = "utf-8"

    answer = _Answer()
    try:
        for raw in response.iter_lines(decode_unicode=True):
            if not raw:
                continue
            line = raw.strip()
            # Only the data lines carry anything. Anthropic writes an `event:`
            # line in front of each of them naming the same type its data
            # object repeats, so skipping those loses nothing.
            if not line.startswith("data:"):
                continue
            tokens, finished = grammar.feed(line[len("data:"):].strip(), answer)
            for piece in tokens:
                yield ("token", piece)
            if finished:
                break
    finally:
        response.close()

    # A stream that never said it was finished did not finish. Until this reader
    # existed the same failure raised by itself: the answer was parsed with
    # response.json(), and a body cut in the middle is not JSON. Read frame by
    # frame it fell silent instead. Proven over real sockets on 2026-09-04, with
    # no provider involved: a body sent under `Connection: close` and cut after a
    # content delta, and a chunked body cut and then closed off with a proper
    # terminal 0-chunk — which is what a proxy writes when it gives up on the
    # origin — both leave this loop with no error at all, and what had arrived
    # was handed on as the whole answer. Only a chunked body with NO terminal
    # chunk still raised.
    #
    # Every guard downstream is keyed on finish_reason, and such a stream sets
    # none: a verdict cut after the word SAFE showed a child the picture the
    # check had been asked about. So it is raised here, where the callers'
    # existing except paths block on it, which is what they are for.
    #
    # The word "connection" stands in the message deliberately:
    # is_retriable_llm_error in chat_routes.py reads that text to decide whether
    # a chat turn may try the next candidate, and a torn stream is an
    # availability failure rather than a refusal.
    if not grammar.ended(answer):
        raise Exception(f"{provider} stream for model {model} ended without "
                        f"saying it had finished — the connection closed after "
                        f"{len(answer.content)} characters of answer with no "
                        f"terminal marker, so what arrived may be a fragment")

    tool_calls = [answer.tool_acc[k] for k in sorted(answer.tool_acc)] or None
    # A model that says nothing, reasons about nothing and asks for nothing has
    # failed, whatever the status code said. Reasoning alone still counts as an
    # answer having been produced; whether it may BE the answer is the caller's
    # decision, not this one's.
    if not answer.content and not answer.thinking and not tool_calls:
        if answer.finish_reason == "refusal":
            # The messages dialect declines with HTTP 200, stop_reason
            # "refusal" and no content. Raised under that word, because the
            # word is what the chain's classifier reads: a refusal is never
            # tried again on the next candidate, an "empty response" is.
            raise Exception(f"{provider} refused the request for model {model} "
                            f"(stop_reason=refusal)")
        raise Exception(f"{provider} returned empty response for model {model}")

    if answer.usage:
        inp, out = extract_usage(answer.usage, provider)
        if inp or out:
            get_usage_tracker().log(model=model, provider=provider,
                                    stage=stage, input_tokens=inp, output_tokens=out)

    logger.info(f"{tag} {provider} stream: {len(answer.content)} chars, "
                f"tool_calls={len(tool_calls) if tool_calls else 0}, "
                f"finish_reason={answer.finish_reason}")
    yield ("result", {"content": answer.content, "thinking": answer.thinking or None,
                      "tool_calls": tool_calls, "finish_reason": answer.finish_reason})


def _stream_openai_style(provider: str, messages: list, model: str, temperature: float,
                         max_tokens: Optional[int], tools: list = None, image_b64: str = None,
                         stage: str = "chat", extra_payload: Optional[dict] = None):
    """Yield ('token', text) as the answer is written, then ('result', dict).

    Everything after the request is the opener above; what stands here is the
    request one of the five OpenAI-compatible providers expects.

    `stage` names the caller for the usage ledger and the log line, so a
    verdict call is not booked as chat. `extra_payload` carries request fields
    that only one provider knows; see the payload below for the case it exists
    for.
    """
    api_url, api_key = _OPENAI_STYLE_PROVIDERS[provider]()
    if not api_key:
        raise Exception(f"{provider} API Key not configured")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    effective_messages = _inject_image_into_messages(messages, image_b64, 'openai') if image_b64 else messages

    payload = {
        # Request fields one provider understands and the others do not,
        # straight from the caller. IONOS is the case this exists for: its
        # reasoning models cannot be told to stop thinking, but
        # reasoning_effort="low" keeps them from spending a whole turn on
        # chain-of-thought when the caller needs a structured answer. Written
        # FIRST, so nothing a caller passes can stand in for the model, the
        # conversation or the temperature, or switch this transport off.
        **(extra_payload or {}),
        "model": model,
        "messages": effective_messages,
        "temperature": temperature,
        "stream": True,
        # Asked for so the usage tracker keeps its numbers on this transport
        # too; a provider that does not know the field gets the request again
        # without it (see the opener) rather than failing the turn.
        "stream_options": {"include_usage": True},
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if tools:
        payload["tools"] = tools

    yield from _stream_sse(provider, api_url, headers, payload,
                           _ChatCompletionsGrammar(), model, stage)


def _messages_dialect_request(messages: list, tools: Optional[list],
                              image_b64: Optional[str]) -> Tuple[str, list, Optional[list]]:
    """The conversation as the messages API wants it: (system, messages, tools).

    Every caller on this platform keeps its conversation in the chat-completions
    shape: the system prompt is a message with role "system", a tool is
    {"type": "function", "function": {...}}, an assistant's tool calls sit in
    "tool_calls" with their arguments as a JSON string, and a tool's answer is a
    message with role "tool". The messages API says the same things
    differently: the system prompt is a top-level field, a tool carries an
    input_schema, a tool call is a tool_use block whose input is an object, and
    a tool's answer is a tool_result block inside a user turn. Until 2026-09-12
    this dialect was sent single user messages only, so none of this had a
    caller; the chat surface reaches it now, with its history and its tools.

    The picture goes into the last user message BEFORE the roles are
    translated, so it lands in what the person wrote and never in a tool's
    answer (which is a user turn in this dialect and would be found first).

    Three rules of this API that the chat-completions shape does not have:
    the answers to one round of tool calls go back in ONE user turn (the
    documentation says so, and says that splitting them teaches the model to
    stop calling tools in parallel); the first turn is a user turn, so an
    assistant remark the surface wrote before the person said anything is
    left out here, with a log line; and a text block is never empty, so an
    assistant turn that carried only whitespace beside its tool calls sends
    the calls alone, and one that carried nothing at all is left out.
    """
    if image_b64:
        messages = _inject_image_into_messages(messages, image_b64, "anthropic")
    system_parts = []
    out = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if role == "system":
            if content:
                system_parts.append(content if isinstance(content, str) else json.dumps(content))
            continue
        if role == "assistant" and not out:
            logger.info("messages dialect: an assistant turn before the first user turn "
                        "is left out, the API takes a user turn first")
            continue
        if role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id") or "",
                "content": content if isinstance(content, str) else json.dumps(content),
            }
            last = out[-1] if out else None
            if (last and last["role"] == "user" and isinstance(last["content"], list)
                    and last["content"] and last["content"][0].get("type") == "tool_result"):
                last["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
            continue
        if role == "assistant" and m.get("tool_calls"):
            blocks = []
            if isinstance(content, str) and content.strip():
                blocks.append({"type": "text", "text": content})
            for tc in m["tool_calls"]:
                fn = tc.get("function") or {}
                args = fn.get("arguments")
                try:
                    parsed = json.loads(args) if isinstance(args, str) and args.strip() else (args or {})
                except json.JSONDecodeError as e:
                    # A malformed history is not repaired here; the call that
                    # produced it failed, and this one says so.
                    raise Exception(f"tool call {fn.get('name')!r} carries arguments "
                                    f"that are not JSON: {e}")
                blocks.append({"type": "tool_use", "id": tc.get("id") or "",
                               "name": fn.get("name") or "", "input": parsed})
            out.append({"role": "assistant", "content": blocks})
            continue
        if role == "assistant" and (content is None or (isinstance(content, str) and not content.strip())):
            logger.info("messages dialect: an assistant turn with no text and no tool call is left out")
            continue
        out.append({"role": role, "content": content})

    translated_tools = None
    if tools:
        translated_tools = []
        for t in tools:
            fn = t.get("function") if t.get("type") == "function" else None
            if fn is None:
                translated_tools.append(t)  # already in this dialect's shape
                continue
            translated_tools.append({
                "name": fn.get("name") or "",
                "description": fn.get("description") or "",
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
            })
    return "\n\n".join(system_parts), out, translated_tools


def _stream_anthropic_style(provider: str, messages: list, model: str,
                            temperature: Optional[float] = None,
                            max_tokens: Optional[int] = None, tools: list = None,
                            stage: str = "chat", image_b64: Optional[str] = None,
                            extra_payload: Optional[dict] = None):
    """The same, for a provider that speaks Anthropic's messages API.

    What stands here is where the two dialects part: /v1/messages instead of
    /v1/chat/completions, the key in x-api-key instead of an Authorization
    header, a required version header, and max_tokens as a field the API
    refuses the request without. The conversation itself is translated by
    _messages_dialect_request above.

    Temperature is sent only when a caller asked for one. The unstreamed call
    this replaced did the same, so the model applies its own default where no
    config named a number — quietly sending 0.7 there would change what every
    existing config produces.
    """
    api_url, api_key = _ANTHROPIC_STYLE_PROVIDERS[provider]()
    if not api_key:
        raise Exception(f"{provider} API Key not configured")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "Content-Type": "application/json",
    }
    system, effective_messages, effective_tools = _messages_dialect_request(
        messages, tools, image_b64)
    payload = {
        # Request fields from the caller come FIRST, as in the other dialect:
        # nothing passed in can switch this transport off, lower the ceiling
        # below what the API requires the field to carry, or stand in for
        # the conversation.
        **(extra_payload or {}),
        "model": model,
        # Required by this API, which is the only reason a number stands here.
        "max_tokens": max_tokens if max_tokens is not None else ANTHROPIC_MAX_TOKENS_CEILING,
        "messages": effective_messages,
        "stream": True,
    }
    if system:
        payload["system"] = system
    if temperature is not None:
        payload["temperature"] = temperature
    if effective_tools:
        payload["tools"] = effective_tools

    yield from _stream_sse(provider, api_url, headers, payload,
                           _MessagesGrammar(), model, stage)


def _drain(stream, provider: str, model: str) -> dict:
    """Run a stream to its end and return its terminal result.

    Both blocking entry points share this, so there is no second consumption
    loop to fall out of step with the first — the same reason the streaming
    readers share one opener.
    """
    result = None
    for kind, payload in stream:
        if kind == "result":
            result = payload
    if result is None:
        # The generator either raises or yields a result, so this is a bug in
        # this module rather than a provider failure. Named as such.
        raise Exception(f"{provider} stream ended without a result for model {model}")
    return result


def call_openai_style(provider: str, messages: list, model: str, temperature: float = 0.7,
                      max_tokens: Optional[int] = None, tools: list = None,
                      image_b64: str = None, stage: str = "chat",
                      extra_payload: Optional[dict] = None) -> dict:
    """Run the stream to its end and return the result dict, for callers that
    need the whole answer.

    The pipeline engine and the image check want a finished text, not pieces of
    one. They get it from the same reader the chat surface streams from, so
    there is no second consumption loop to fall out of step with this one — and
    no second provider table behind it. The dict is exactly what the generator
    yields as its terminal ('result', …): content, thinking, tool_calls,
    finish_reason.
    """
    return _drain(
        _stream_openai_style(provider, messages, model, temperature, max_tokens,
                             tools=tools, image_b64=image_b64, stage=stage,
                             extra_payload=extra_payload),
        provider, model)


def call_anthropic_style(provider: str, messages: list, model: str,
                         temperature: Optional[float] = None,
                         max_tokens: Optional[int] = None, tools: list = None,
                         stage: str = "chat", image_b64: Optional[str] = None,
                         extra_payload: Optional[dict] = None) -> dict:
    """The same for the Anthropic dialect: the whole answer, in the same dict.

    Deliberately the same four keys as above — content, thinking, tool_calls,
    finish_reason — so a caller that stops asking one provider and starts
    asking the other has nothing to rewrite, and so the guards that read those
    keys keep working whichever dialect answered.
    """
    return _drain(
        _stream_anthropic_style(provider, messages, model, temperature=temperature,
                                max_tokens=max_tokens, tools=tools, stage=stage,
                                image_b64=image_b64, extra_payload=extra_payload),
        provider, model)


# ---------------------------------------------------------------------------
# One request, whichever dialect the provider speaks
# ---------------------------------------------------------------------------
def stream_chat(provider: str, messages: list, model: str,
                temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                tools: list = None, image_b64: Optional[str] = None,
                stage: str = "chat", extra_payload: Optional[dict] = None):
    """Yield ('token', text)… ('result', dict) from a provider named by the table.

    A caller — the chat surface, the pipeline engine, the image check — names
    a provider and the model path as that provider publishes it, and nothing
    else. Which endpoint answers, which header carries the key and which
    grammar reads the answer follow from config/llm_providers.json. Until
    2026-09-12 each caller kept a ladder of prefixes of its own, and the chat
    surface's ladder sent 'anthropic/' and 'openai/' to OpenRouter under a
    name OpenRouter does not carry.

    temperature None means the caller did not ask for one. A
    chat-completions provider is then asked with 0.7, the default the
    platform has always sent it; the messages dialect leaves the field out and
    the model applies its own, which is what every existing config on that
    dialect produces -- and the models the platform's Anthropic preset names
    answer 400 to the field, so a default sent there would end every turn. A
    temperature a caller DID ask for is sent to either dialect as asked; where
    the model rejects it, the provider's error names the field, which is the
    answer that caller has to see.

    A provider whose entry says "image_input": false is not handed the
    picture. That is the floor under the measurements in
    services/model_capabilities: a property of the connection, not of any
    model behind it, applied where the request is built so that no caller
    can pass it by. A provider whose entry says "bedrock" is not reached
    here at all; its callers keep the AWS SDK path.
    """
    entry = provider_entry(provider)
    if entry is None:
        raise Exception(f"Unknown provider '{provider}'")
    label = entry.get("label", provider)
    dialect = entry.get("dialect")
    if image_b64 and entry.get("image_input") is False:
        logger.info(f"[{stage}] {label}: image withheld, this connection takes none")
        image_b64 = None
    if dialect == CHAT_COMPLETIONS:
        yield from _stream_openai_style(
            provider, messages, model, 0.7 if temperature is None else temperature,
            max_tokens, tools=tools, image_b64=image_b64, stage=stage,
            extra_payload=extra_payload)
    elif dialect == MESSAGES:
        yield from _stream_anthropic_style(
            provider, messages, model, temperature=temperature, max_tokens=max_tokens,
            tools=tools, stage=stage, image_b64=image_b64, extra_payload=extra_payload)
    else:
        raise Exception(f"{label} speaks '{dialect}', which is not reached over HTTP here")


def call_chat(provider: str, messages: list, model: str,
              temperature: Optional[float] = None, max_tokens: Optional[int] = None,
              tools: list = None, image_b64: Optional[str] = None,
              stage: str = "chat", extra_payload: Optional[dict] = None) -> dict:
    """The whole answer from stream_chat, in the four-key dict."""
    return _drain(
        stream_chat(provider, messages, model, temperature=temperature,
                    max_tokens=max_tokens, tools=tools, image_b64=image_b64,
                    stage=stage, extra_payload=extra_payload),
        provider, model)
