"""
The tokenizers, answered on ComfyUI's HTTP server.

Registered on PromptServer when the package loads, the way a node package
adds its own endpoints. Off the queue on purpose: the window count is asked
before every run of a config that declares a window, and the comparison
instrument asks on every sentence typed; both would otherwise wait behind
every picture in the queue for an answer that reads a vocabulary file.

    POST /ai4artsed/text/tokenizer-facts      {model_ids: [...]}  -> {id: {available, window, matrix}}
    POST /ai4artsed/text/tokenize             {text, model_id}
    POST /ai4artsed/text/token-count          {text, encoder}  encoder: clip_l | clip_g | t5
    POST /ai4artsed/text/encoder-rows         {text, t5_min_length?} -> {clip: {rows..}, t5: {rows..}}

Which tokenizers the comparison instrument offers is the DevServer's table;
the routes take the repository id they are given and read it from the
Hugging Face cache of this machine.

The work runs in the loop's executor: the first call for a tokenizer parses
its vocabulary (a second for the larger ones), and ComfyUI's loop carries the
progress of every running prompt in the meantime. A text over MAX_TEXT_CHARS
is refused with 413 before any of it is read.
"""

import asyncio
import logging
import sys

from aiohttp import web

from . import _tokenizers

logger = logging.getLogger(__name__)

# The instrument shows sentences and the window count reads one prompt; a
# text of this length is a hundred prompts and costs the executor well under
# a second. Beyond it the request is refused unread: five megabytes took 17 s
# of one thread and held the loop, and with it the progress of every running
# prompt, for up to 0.7 s at a time (measured 2026-09-14).
MAX_TEXT_CHARS = 100_000
MAX_MODEL_IDS = 64


def _answer(result):
    status = result.pop("http_status", 200) if isinstance(result, dict) else 200
    return web.json_response(result, status=status)


async def _body(request):
    """The request's JSON object, or None where the body is something else.

    aiohttp's own refusals pass through as they are: a body over the server's
    size limit answers 413 from aiohttp itself, and this is no place to turn
    that into "text required".
    """
    try:
        data = await request.json()
    except web.HTTPException:
        raise
    except Exception:
        return None
    return data if isinstance(data, dict) else None


async def _run(fn, *args):
    """The work, in the loop's executor; a failure answers as JSON with its cause."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, fn, *args)
    except Exception as e:
        logger.error(f"[AI4ArtsEd tokenizers] {fn.__name__} failed: {e}")
        return {"error": f"{fn.__name__} failed: {e}", "http_status": 500}


def _no_object():
    return {"error": "body is not a JSON object", "http_status": 400}


def _too_long():
    return {"error": f"text is longer than {MAX_TEXT_CHARS} characters", "http_status": 413}


def register(routes):
    @routes.post("/ai4artsed/text/tokenizer-facts")
    async def tokenizer_facts(request):
        data = await _body(request)
        if data is None:
            return _answer(_no_object())
        model_ids = data.get("model_ids")
        if not isinstance(model_ids, list) or not all(isinstance(m, str) and m for m in model_ids):
            return _answer({"error": "model_ids required, a list of repository ids", "http_status": 400})
        if len(model_ids) > MAX_MODEL_IDS:
            return _answer({"error": f"model_ids: at most {MAX_MODEL_IDS} in one call", "http_status": 413})
        return _answer(await _run(_tokenizers.facts, model_ids))

    @routes.post("/ai4artsed/text/tokenize")
    async def tokenize(request):
        data = await _body(request)
        if data is None:
            return _answer(_no_object())
        text, model_id = data.get("text"), data.get("model_id")
        if not isinstance(text, str) or not text or not isinstance(model_id, str) or not model_id:
            return _answer({"error": "text and model_id required", "http_status": 400})
        if len(text) > MAX_TEXT_CHARS:
            return _answer(_too_long())
        return _answer(await _run(_tokenizers.tokenize, text, model_id))

    @routes.post("/ai4artsed/text/token-count")
    async def token_count(request):
        data = await _body(request)
        if data is None:
            return _answer(_no_object())
        text, encoder = data.get("text"), data.get("encoder")
        if not isinstance(text, str) or not text or not isinstance(encoder, str) or not encoder:
            return _answer({"error": "text and encoder required", "http_status": 400})
        if len(text) > MAX_TEXT_CHARS:
            return _answer(_too_long())
        return _answer(await _run(_tokenizers.count_tokens, text, encoder))

    @routes.post("/ai4artsed/text/encoder-rows")
    async def encoder_rows(request):
        data = await _body(request)
        if data is None:
            return _answer(_no_object())
        text = data.get("text")
        if not isinstance(text, str) or not text:
            return _answer({"error": "text required", "http_status": 400})
        if len(text) > MAX_TEXT_CHARS:
            return _answer(_too_long())
        t5_min_length = data.get("t5_min_length", _tokenizers.T5_ROWS_DEFAULT)
        # 10000 is what ComfyUI's own T5TokenizerOptions node lets a graph set.
        if (not isinstance(t5_min_length, int) or isinstance(t5_min_length, bool)
                or not 1 <= t5_min_length <= 10000):
            return _answer({"error": "t5_min_length: a positive integer up to 10000",
                            "http_status": 400})
        return _answer(await _run(_tokenizers.encoder_rows, text, t5_min_length))


def install():
    """Register the routes on the running PromptServer; False where there is none.

    ComfyUI imports its `server` module before it loads any node package, so
    the running server is taken from `sys.modules`: an import by name from
    anywhere else (a test, a script with another `server.py` first on the
    path) would load that other module, and `PromptServer.instance` exists
    only once the server is constructed. A fault here is logged, and the
    package's nodes stay registered.
    """
    server = sys.modules.get("server")
    instance = getattr(getattr(server, "PromptServer", None), "instance", None)
    routes = getattr(instance, "routes", None)
    if routes is None:
        return False
    try:
        register(routes)
    except Exception as e:
        logger.error(f"[AI4ArtsEd tokenizers] the routes stay unregistered: {e}")
        return False
    return True
