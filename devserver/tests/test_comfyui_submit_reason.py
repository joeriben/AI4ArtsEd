"""What ComfyUI said about a workflow it would not run.

Until 2026-09-07 a refusal from ComfyUI was answered with `None`, and the two
callers turned that silence into a sentence of their own — "Failed to submit
workflow to ComfyUI", and on the legacy page a German one. Both fit every
failure equally badly, and the one thing ComfyUI actually sends is the one
thing that helps: the node it choked on and what is wrong with it. A missing
checkpoint says which file, and lists the ones that ARE installed to compare
against; a missing custom node says its name.

So the refusal travels now. These tests hold three things in place: that the
reader gets the real shapes right, that the submission answers with an id or
raises, and that neither caller has a sentence of its own left to fall back on.

The shapes below are ComfyUI's own, read out of the installed copy
(`dlbackend/ComfyUI/execution.py` validate_prompt / validate_inputs, and
`server.py` post_prompt), not invented for the test.
"""
import ast
import asyncio
import inspect
import io
import json
import os
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from my_app.services import comfyui_ws_client as WS
from my_app.services.comfyui_ws_client import (
    ComfyUISubmitError,
    ComfyUIWebSocketClient,
    _read_comfyui_refusal,
    _REASON_CHARS,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------
# The shapes ComfyUI actually sends
# --------------------------------------------------------------------------

def _validation_failure(installed=("anima_pencil.safetensors", "flux1-dev.safetensors")):
    """A workflow naming a checkpoint this installation does not have.

    The commonest refusal there is. `error.details` is joined over the errors
    of the OUTPUT nodes only, and the broken node here is a loader upstream of
    them — `validate_inputs` returns no reasons for the output node in that
    case (execution.py), so `details` comes back EMPTY and `node_errors`
    carries the whole cause.
    """
    return json.dumps({
        "error": {
            "type": "prompt_outputs_failed_validation",
            "message": "Prompt outputs failed validation",
            "details": "",
            "extra_info": {},
        },
        "node_errors": {
            "4": {"class_type": "CheckpointLoaderSimple",
                  "dependent_outputs": ["9"],
                  "errors": [{"type": "value_not_in_list",
                              "message": "Value not in list",
                              "details": "ckpt_name: 'sd3.5_large.safetensors' not in %s"
                                         % list(installed)}]},
        },
    })


def _output_node_failure():
    """The other half of the same refusal — the broken node IS an output node.

    This is when `error.details` fills up, by joining "{message}: {details}"
    over the errors `node_errors` already carries. Both halves then say the
    same thing, once without the class name and once with it.
    """
    per_node = [
        {"type": "value_not_in_list", "message": "Value not in list",
         "details": "filename_prefix: 'x' not in ['a', 'b']"},
        {"type": "required_input_missing", "message": "Required input is missing",
         "details": "images"},
    ]
    return json.dumps({
        "error": {
            "type": "prompt_outputs_failed_validation",
            "message": "Prompt outputs failed validation",
            "details": "\n".join("%s: %s" % (e["message"], e["details"]) for e in per_node),
            "extra_info": {},
        },
        "node_errors": {
            "9": {"class_type": "SaveImage", "dependent_outputs": ["9"],
                  "errors": per_node},
        },
    })


# `validate_inputs` returns (False, error, [], {}) for a node class that is not
# registered — so `node_errors` is EMPTY and `error` carries the whole cause.
MISSING_NODE = json.dumps({
    "error": {
        "type": "missing_node_type",
        "message": "Node 'LatentSubtract' not found. The custom node may not be installed.",
        "details": "Node ID '#7'",
        "extra_info": {"node_id": "7", "class_type": "LatentSubtract",
                       "node_title": "LatentSubtract"},
    },
    "node_errors": {},
})

NO_PROMPT = json.dumps({
    "error": {"type": "no_prompt", "message": "No prompt provided",
              "details": "No prompt provided", "extra_info": {}},
    "node_errors": {},
})

PROXY_PAGE = ("<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n"
              "<center><h1>502 Bad Gateway</h1></center>\r\n"
              "<hr><center>nginx/1.24.0</center>\r\n</body>\r\n</html>\r\n")


# --------------------------------------------------------------------------
# The reader
# --------------------------------------------------------------------------

class TestTheReader:

    def test_a_missing_checkpoint_names_the_node_and_the_file(self):
        line = _read_comfyui_refusal(_validation_failure())
        assert "CheckpointLoaderSimple" in line
        assert "sd3.5_large.safetensors" in line
        assert "Value not in list" in line

    def test_it_stays_one_line(self):
        """`error.details` arrives newline-joined. A surface gets a line."""
        for body in (_validation_failure(), _output_node_failure()):
            line = _read_comfyui_refusal(body)
            assert "\n" not in line and "\r" not in line

    def test_it_says_each_reason_once(self):
        """The old reader took `error.details` AND `node_errors`, which are the
        same reasons twice — once without the node name, once with it. This is
        the shape where they really do overlap: the broken node is an output
        node, so its errors are in both halves."""
        line = _read_comfyui_refusal(_output_node_failure())
        assert line.count("Value not in list") == 1
        assert line.count("Required input is missing") == 1
        assert "SaveImage" in line
        assert "\n" not in line

    def test_a_repeated_detail_is_said_once_where_no_node_is_named(self):
        """`no_prompt` puts the same sentence in `message` and in `details`."""
        assert _read_comfyui_refusal(NO_PROMPT) == "No prompt provided"

    def test_a_missing_custom_node_survives_an_empty_node_errors(self):
        line = _read_comfyui_refusal(MISSING_NODE)
        assert "LatentSubtract" in line
        assert "not found" in line
        assert "may not be installed" in line

    def test_the_installed_list_is_clipped_but_the_asked_for_name_survives(self):
        """The list of what IS installed runs to hundreds of characters. It is
        the thing to compare against, so it starts; it is not the cause, so it
        stops."""
        line = _read_comfyui_refusal(
            _validation_failure(installed=["m%02d.safetensors" % i for i in range(60)]))
        assert "sd3.5_large.safetensors" in line
        assert len(line) <= _REASON_CHARS + 1
        assert "…" in line

    def test_more_broken_nodes_than_fit_are_counted_not_dropped(self):
        body = json.dumps({
            "error": {"message": "Prompt outputs failed validation"},
            "node_errors": {str(i): {"class_type": "Node%d" % i,
                                     "errors": [{"message": "bad"}]} for i in range(9)},
        })
        line = _read_comfyui_refusal(body)
        assert "and 4 more" in line

    def test_an_html_error_page_does_not_travel(self):
        """A proxy's page carries the server's own paths and version and says
        nothing about the request. `utils/response_reason.py` is where that is
        decided, for this reader and for the GPU service's alike."""
        line = _read_comfyui_refusal(PROXY_PAGE)
        assert "nginx" not in line
        assert "<" not in line
        assert line == "an HTML error page"

    def test_plain_text_from_a_500_comes_through(self):
        """aiohttp's own 500 body is text, and it is worth reading."""
        line = _read_comfyui_refusal(
            "500 Internal Server Error\n\nServer got itself in trouble")
        assert "Server got itself in trouble" in line
        assert "\n" not in line

    @pytest.mark.parametrize("body", ["", "   ", "null", "[]", "{}"])
    def test_an_answer_with_nothing_in_it_still_says_something(self, body):
        assert _read_comfyui_refusal(body).strip()


# --------------------------------------------------------------------------
# The exception
# --------------------------------------------------------------------------

class TestTheException:

    def test_a_refusal_reads_as_a_refusal(self):
        e = ComfyUISubmitError(400, "CheckpointLoaderSimple: Value not in list")
        assert e.status == 400
        assert "refused" in str(e)
        assert "HTTP 400" in str(e)
        assert "CheckpointLoaderSimple" in str(e)

    def test_no_answer_reads_as_out_of_reach(self):
        e = ComfyUISubmitError(0, "ClientConnectorError: Connection refused")
        assert e.status == 0
        assert "could not be reached" in str(e)
        assert "refused the workflow" not in str(e)

    def test_an_accepted_workflow_is_not_called_a_refused_one(self):
        """ComfyUI answered 200 and named nothing to track. Calling that a
        refusal contradicts the sentence it is in."""
        e = ComfyUISubmitError(200, "no prompt_id in the answer")
        assert "refused" not in str(e)
        assert "HTTP 200" in str(e)

    def test_it_is_still_a_runtime_error(self):
        """Callers that catch RuntimeError keep catching it — and the one
        caller that did so around the submission itself was resending the
        workflow, which is why `workflow_streaming_routes` (removed 2026-10-10) caught around
        the loop lookup alone."""
        assert issubclass(ComfyUISubmitError, RuntimeError)


# --------------------------------------------------------------------------
# The submission itself
# --------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeSession:
    """Stands in for aiohttp.ClientSession. `answer` is a (status, body) pair,
    or an exception to raise instead of answering."""

    answer = (200, '{"prompt_id": "abc"}')
    seen = None

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def post(self, url, **kw):
        type(self).seen = {"url": url, **kw}
        if isinstance(_FakeSession.answer, BaseException):
            raise _FakeSession.answer
        return _FakeResponse(*_FakeSession.answer)


@pytest.fixture
def submit(monkeypatch):
    client = ComfyUIWebSocketClient(base_url="http://127.0.0.1:1")
    monkeypatch.setattr(WS.aiohttp, "ClientSession", _FakeSession)
    _FakeSession.seen = None

    def go(status_or_exc, body=""):
        _FakeSession.answer = (status_or_exc if isinstance(status_or_exc, BaseException)
                               else (status_or_exc, body))
        return asyncio.run(client._submit_workflow({"1": {"class_type": "X"}}))
    return go


class TestTheSubmission:

    def test_an_accepted_workflow_answers_with_its_id(self, submit):
        assert submit(200, '{"prompt_id": "abc", "number": 3}') == "abc"

    def test_a_refusal_carries_comfyuis_own_words_and_its_status(self, submit):
        with pytest.raises(ComfyUISubmitError) as got:
            submit(400, _validation_failure())
        assert got.value.status == 400
        assert "CheckpointLoaderSimple" in got.value.detail
        assert "sd3.5_large.safetensors" in got.value.detail

    def test_a_missing_custom_node_says_which_one(self, submit):
        with pytest.raises(ComfyUISubmitError) as got:
            submit(400, MISSING_NODE)
        assert "LatentSubtract" in got.value.detail

    def test_a_200_that_names_nothing_keeps_the_200(self, submit):
        with pytest.raises(ComfyUISubmitError) as got:
            submit(200, '{"number": 3}')
        assert got.value.status == 200

    def test_the_sync_twin_also_keeps_the_status_of_an_unreadable_answer(self, monkeypatch):
        """`requests`' own `.json()` raises a RequestException subclass, so the
        unreachable branch caught it and called an answer that arrived "no
        answer" -- the very confusion the twin above fixes."""
        from my_app.services import comfyui_service as SVC

        class _Resp:
            status_code = 200
            text = "not json at all"
            def json(self):
                raise ValueError("no json")

        monkeypatch.setattr(SVC.requests, "post", lambda *a, **k: _Resp())
        with pytest.raises(ComfyUISubmitError) as got:
            SVC.ComfyUIService().submit_workflow({"1": {"class_type": "X"}})
        assert got.value.status == 200

    def test_the_sync_twin_carries_comfyuis_words_too(self, monkeypatch):
        """The door that the model preload and the warm-ahead go through. It
        had no behaviour test at all, so a return of `""` in place of the
        raise, or a body read past the reader, went unnoticed."""
        from my_app.services import comfyui_service as SVC

        class _Resp:
            status_code = 400
            text = _validation_failure()
            def json(self):
                return json.loads(self.text)

        monkeypatch.setattr(SVC.requests, "post", lambda *a, **k: _Resp())
        with pytest.raises(ComfyUISubmitError) as got:
            SVC.ComfyUIService().submit_workflow({"1": {"class_type": "X"}})
        assert got.value.status == 400
        assert "CheckpointLoaderSimple" in got.value.detail
        assert "sd3.5_large.safetensors" in got.value.detail

    def test_the_sync_twin_keeps_an_error_page_off_the_surface(self, monkeypatch):
        from my_app.services import comfyui_service as SVC

        class _Resp:
            status_code = 502
            text = PROXY_PAGE
            def json(self):
                raise ValueError("no json")

        monkeypatch.setattr(SVC.requests, "post", lambda *a, **k: _Resp())
        with pytest.raises(ComfyUISubmitError) as got:
            SVC.ComfyUIService().submit_workflow({"1": {"class_type": "X"}})
        assert "nginx" not in got.value.detail
        assert got.value.detail == "an HTML error page"

    def test_the_sync_twin_bounds_the_handshake_the_same_way(self, monkeypatch):
        from my_app.services import comfyui_service as SVC
        seen = {}

        class _Resp:
            status_code = 200
            text = '{"prompt_id": "abc"}'
            def json(self):
                return {"prompt_id": "abc"}

        def _post(url, **kw):
            seen.update(kw)
            return _Resp()

        monkeypatch.setattr(SVC.requests, "post", _post)
        assert SVC.ComfyUIService().submit_workflow({"1": {"class_type": "X"}}) == "abc"
        connect, readfor = seen["timeout"]
        assert connect
        assert readfor and readfor >= 120

    def test_a_body_that_is_not_json_keeps_the_status_it_arrived_with(self, submit):
        """`response.json()` raises on a body that is not JSON, and that raise
        used to leave through the unreachable branch — reporting "no answer"
        for an answer that did arrive."""
        with pytest.raises(ComfyUISubmitError) as got:
            submit(200, "not json at all")
        assert got.value.status == 200

    def test_an_unreachable_comfyui_is_told_apart_from_a_refusal(self, submit):
        with pytest.raises(ComfyUISubmitError) as got:
            submit(OSError("Connection refused"))
        assert got.value.status == 0
        assert "Connection refused" in got.value.detail

    def test_a_refusal_is_not_rewritten_by_the_branch_below_it(self, submit):
        """`except ComfyUISubmitError: raise` stands before the catch-all. Drop
        it and every refusal is re-raised as status 0 — the cause survives, the
        status does not, and 'could not be reached' is then said about a
        ComfyUI that answered."""
        with pytest.raises(ComfyUISubmitError) as got:
            submit(400, _validation_failure())
        assert got.value.status == 400

    def test_the_handshake_is_bounded_and_nothing_else_is(self, submit):
        """/prompt is a handshake: ComfyUI validates, queues and answers an id,
        while the rendering runs in its own worker thread. It gets a bound
        because it runs inside the GPU slot, and a ComfyUI that accepts the
        connection and then says nothing would hold the card against every
        other run for the life of the process. Generous, because the deadline
        that stood here before (30 s) is the kind that reports a busy card as
        an unreachable one."""
        submit(200, '{"prompt_id": "abc"}')
        timeout = _FakeSession.seen["timeout"]
        assert timeout.total is None, "a total deadline would cover the answer too"
        assert timeout.sock_connect
        assert timeout.sock_read and timeout.sock_read >= 120

    def test_a_caller_that_tracks_nothing_needs_no_client_id(self, submit):
        """Two calls in workflow_streaming_routes (removed 2026-10-10) passed the workflow alone. The
        parameter used to be required, so they raised TypeError before ComfyUI
        was ever reached."""
        submit(200, '{"prompt_id": "abc"}')
        assert _FakeSession.seen["json"]["client_id"]


# --------------------------------------------------------------------------
# Nothing left to fall back on
# --------------------------------------------------------------------------

def _source_without_docstrings(path, funcname):
    """The body of a function, with docstrings removed — a claim in a comment
    or a docstring must not be able to satisfy a test about the code."""
    with io.open(os.path.join(REPO, path), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    found = []

    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == funcname:
                found.append(child)
            walk(child)
    walk(tree)
    assert len(found) == 1, "%s: found %d definitions of %s" % (path, len(found), funcname)
    fn = found[0]
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return fn, body


def _returns_none(body):
    """Any way of answering with None: `return`, `return None`, `return x`
    where x is a name bound to None — the last is caught by refusing a bare
    name return in a function whose only other returns are values."""
    for node in body:
        for n in ast.walk(node):
            if isinstance(n, ast.Return):
                if n.value is None:
                    return True
                if isinstance(n.value, ast.Constant) and n.value.value is None:
                    return True
    return False


class TestNoSilenceLeft:

    @pytest.mark.parametrize("path,funcname", [
        ("my_app/services/comfyui_ws_client.py", "_submit_workflow"),
        ("my_app/services/comfyui_service.py", "submit_workflow"),
    ])
    def test_both_doors_answer_with_an_id_or_raise(self, path, funcname):
        fn, body = _source_without_docstrings(path, funcname)
        assert not _returns_none(body), "%s.%s can still answer with None" % (path, funcname)
        raised = {ast.unparse(n.exc.func) for n in ast.walk(fn)
                  if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)}
        assert "ComfyUISubmitError" in raised, \
            "%s.%s raises %s, not the shared exception" % (path, funcname, raised)

    @pytest.mark.parametrize("path,funcname", [
        ("my_app/services/comfyui_ws_client.py", "_submit_workflow"),
        ("my_app/services/comfyui_service.py", "submit_workflow"),
    ])
    def test_the_reason_comes_from_the_reader_and_not_from_a_literal(self, path, funcname):
        """Forbidding the three sentences that stood here is not enough — a
        fourth one would pass. What has to hold is where the words come from:
        every refusal this function raises carries what the reader made of
        ComfyUI's answer."""
        fn, _ = _source_without_docstrings(path, funcname)
        # Names bound to what the reader made of the answer count as the
        # reader: `detail = _read_comfyui_refusal(text)` then `raise ...detail`.
        from_reader = {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign)
                       and "_read_comfyui_refusal" in ast.unparse(n.value)
                       for t in n.targets if isinstance(t, ast.Name)}
        raises = [n for n in ast.walk(fn)
                  if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
                  and ast.unparse(n.exc.func) == "ComfyUISubmitError"]
        assert raises, "%s.%s raises no refusal at all" % (path, funcname)
        for r in raises:
            first = r.exc.args[0] if r.exc.args else None
            if isinstance(first, ast.Constant) and first.value == 0:
                # Status 0 is "never got an answer". There is no body to read,
                # and the exception carries what the socket said instead.
                continue
            args = "".join(ast.unparse(a) for a in r.exc.args)
            assert ("_read_comfyui_refusal" in args
                    or any(name in args for name in from_reader)), (
                "%s.%s raises a sentence of its own: %s"
                % (path, funcname, ast.unparse(r)))

    @pytest.mark.parametrize("path", [
        "my_app/services/comfyui_ws_client.py",
        "my_app/services/comfyui_service.py",
        "my_app/routes/settings_routes.py",
    ])
    def test_no_caller_invents_a_sentence_for_a_silence_that_is_gone(self, path):
        """The three that existed: "Failed to submit workflow to ComfyUI",
        "ComfyUI hat kein Prompt-ID zurückgegeben." and "ComfyUI rejected
        workflow". Each stood where ComfyUI's own reason now stands. Docstrings
        may still name them — this reads the code."""
        invented = ("Failed to submit workflow",
                    "kein Prompt-ID",
                    "ComfyUI rejected workflow")
        with io.open(os.path.join(REPO, path), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        strings = [n.value for n in ast.walk(tree)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        docstrings = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                d = ast.get_docstring(n, clean=False)
                if d:
                    docstrings.add(d)
        for s in strings:
            if s in docstrings:
                continue
            for bad in invented:
                assert bad not in s, "%s still carries %r" % (path, bad)

    @pytest.mark.parametrize("path", [
        "my_app/services/comfyui_ws_client.py",
        "my_app/services/comfyui_service.py",
    ])
    def test_a_refused_workflow_is_never_submitted_a_second_time(self, path):
        """The handler in the lease route exists for "no event loop in this
        thread". While it also wrapped the submission, a refusal — a
        RuntimeError subclass — fell into it and was answered by sending the
        same workflow again, losing the first reason.

        Written against the shape, not against the exception type: `except
        Exception` around the same two lines does exactly the same thing."""
        with io.open(os.path.join(REPO, path), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            guarded = "".join(ast.unparse(b) for b in node.body)
            handled = "".join(ast.unparse(h) for h in node.handlers)
            if "submit_workflow" not in guarded:
                continue
            assert "submit_workflow" not in handled, (
                "%s: a handler around the submission submits again" % path)
