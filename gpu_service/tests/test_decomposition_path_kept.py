"""The decomposition path of the Diffusers backend stays (decision of 2026-09-19).

DEVELOPMENT_DECISIONS.md, 2026-09-19, "Die Decomposition ist entfernt": the
surface went, and "Forschungswege werden nicht abgebaut" kept the route
/api/diffusers/generate/decomposition, generate_image_with_decomposition in the
backend and the DevServer client of the same name, the way to the path once its
chunk was gone. eb07734 and d6d3617 (2026-10-10) struck all of it as unreached;
these tests hold it. Read as source, because the backend imports torch, which
this venv does not carry.
"""
import ast
import os

GPU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(GPU)
ROUTE = "/api/diffusers/generate/decomposition"
METHOD = "generate_image_with_decomposition"
BACKEND_CLASS = "DiffusersImageGenerator"


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def _class(tree, name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"no class {name}")


def _only_method(cls, name):
    """The one definition Python binds: exactly one, so no later twin shadows it."""
    found = [n for n in cls.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    assert len(found) == 1, f"{cls.name}.{name} defined {len(found)} times"
    return found[0]


def _module_constant(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    return None


def _calls(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            yield sub


def _backend():
    tree = ast.parse(_read(GPU, "services", "diffusers_backend.py"))
    return tree, _only_method(_class(tree, BACKEND_CLASS), METHOD)


def test_the_backend_keeps_the_method_in_its_class():
    _, method = _backend()
    assert isinstance(method, ast.AsyncFunctionDef)
    assert [a.arg for a in method.args.args] == [
        "self", "source_prompt", "cells",
        "clip_l_prompt", "clip_l_step_bands", "clip_l_layer_bands",
        "clip_g_prompt", "clip_g_step_bands", "clip_g_layer_bands",
        "t5_prompt", "t5_step_bands", "t5_layer_bands",
        "alpha", "model_id", "negative_prompt", "width", "height",
        "steps", "cfg_scale", "seed", "callback",
    ]
    defaults = [ast.unparse(d) for d in method.args.defaults]
    assert defaults == ["None"] * 10 + ["1.0", "DEFAULT_MODEL_ID", "''", "1024", "1024",
                                         "25", "5.5", "-1", "None"]


def _guards(method):
    """How a generation path takes its model and the card, independent of its arguments.

    The admission and residency work planned for this backend changes these calls in
    every path at once; comparing a path with generate_image instead of with fixed
    strings lets that work go through while a path that drops a guard on its own fails.
    """
    loads, locked, released_in_finally = set(), [], False
    for node in ast.walk(method):
        if isinstance(node, ast.Call):
            callee = ast.unparse(node.func)
            if callee.startswith("self.") and ("load" in callee or "admission" in callee
                                               or "using" in callee):
                loads.add(callee)
            if callee == "asyncio.to_thread" and node.args and \
                    ast.unparse(node.args[0]) == "self._locked_generate":
                locked.append(node)
        if isinstance(node, ast.Try):
            if any("_model_in_use" in ast.unparse(s) or "_using" in ast.unparse(s)
                   for s in node.finalbody):
                released_in_finally = True
    return loads, len(locked), released_in_finally, locked


def test_the_method_takes_its_model_and_the_card_as_generate_image_does():
    tree, method = _backend()
    reference = _only_method(_class(tree, BACKEND_CLASS), "generate_image")
    mine, theirs = _guards(method), _guards(reference)
    assert mine[:3] == theirs[:3], (mine[:3], theirs[:3])
    assert mine[1] == 1 and mine[2], "one forward under the inference lock, released in finally"


def test_the_forward_runs_only_inside_the_locked_function():
    """Nothing calls the pipeline or the encoders outside the function _locked_generate runs,
    and nothing calls that function directly."""
    _, method = _backend()
    locked_fn = ast.unparse(_guards(method)[3][0].args[1])
    inner = next(n for n in ast.walk(method)
                 if isinstance(n, ast.FunctionDef) and n.name == locked_fn)
    inside = {id(n) for n in ast.walk(inner)}
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        callee = ast.unparse(node.func)
        if callee == locked_fn:
            raise AssertionError(f"{locked_fn}() called directly, outside the lock")
        if callee == "pipe" or callee.endswith(("encode_prompt", "_prompt_embeds", "context_embedder")):
            assert id(node) in inside, f"{callee} runs outside {locked_fn}"


def test_the_method_reads_the_tables():
    _, method = _backend()
    source = ast.unparse(method)
    for name in ("DECOMP_STEP_BANDS", "DECOMP_LAYER_BANDS", "DECOMP_STREAM_SLICES",
                 "DECOMP_VALID_STREAMS", "DECOMP_VALID_STEP_BANDS", "DECOMP_VALID_LAYER_BANDS"):
        assert name in source, name


def test_the_backend_keeps_the_tables_with_their_values():
    tree, _ = _backend()
    values = {name: _module_constant(tree, name) for name in (
        "DECOMP_STEP_BANDS", "DECOMP_LAYER_BANDS", "DECOMP_STREAM_SLICES",
        "DECOMP_VALID_STREAMS", "DECOMP_VALID_STEP_BANDS", "DECOMP_VALID_LAYER_BANDS")}
    assert all(v is not None for v in values.values()), values
    assert ast.literal_eval(values["DECOMP_STEP_BANDS"]) == {
        "composition": (0.0, 0.32), "semantics": (0.32, 0.68), "detail": (0.68, 1.01)}
    assert ast.literal_eval(values["DECOMP_LAYER_BANDS"]) == {
        "shallow": (0, 10), "middle": (10, 23), "deep": (23, 38)}
    assert ast.unparse(values["DECOMP_STREAM_SLICES"]) == (
        "{'clip_l': (slice(0, 77), slice(0, 768)), "
        "'clip_g': (slice(0, 77), slice(768, 2048)), "
        "'t5': (slice(77, None), slice(None, None))}")
    assert ast.unparse(values["DECOMP_VALID_STREAMS"]) == "set(DECOMP_STREAM_SLICES.keys())"
    assert ast.unparse(values["DECOMP_VALID_STEP_BANDS"]) == "set(DECOMP_STEP_BANDS.keys())"
    assert ast.unparse(values["DECOMP_VALID_LAYER_BANDS"]) == "set(DECOMP_LAYER_BANDS.keys())"


def _route():
    source = _read(GPU, "routes", "diffusers_routes.py")
    tree = ast.parse(source)
    handlers = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "generate_decomposition"]
    assert len(handlers) == 1
    handler = handlers[0]
    assert any(ast.unparse(d) == f"diffusers_bp.route('{ROUTE}', methods=['POST'])"
               for d in handler.decorator_list)
    return handler


def test_the_route_calls_the_method_with_every_field_it_takes():
    handler = _route()
    calls = [c for c in _calls(handler)
             if isinstance(c.func, ast.Attribute) and c.func.attr == METHOD]
    assert len(calls) == 1
    params = {a.arg for a in _backend()[1].args.args} - {"self", "callback"}
    assert {kw.arg for kw in calls[0].keywords} == params


def _route_reads():
    """The keys the route takes from the request body."""
    keys = set()
    for call in _calls(_route()):
        if (isinstance(call.func, ast.Attribute) and call.func.attr == "get"
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "data"):
            keys.add(call.args[0].value)
    for sub in ast.walk(_route()):
        if (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
                and sub.value.id == "data" and isinstance(sub.slice, ast.Constant)):
            keys.add(sub.slice.value)
    return keys


def test_the_devserver_client_sends_what_the_route_reads():
    source = _read(REPO, "devserver", "my_app", "services", "diffusers_client.py")
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and any(isinstance(m, ast.AsyncFunctionDef) and m.name == METHOD for m in n.body))
    method = _only_method(cls, METHOD)
    names = [a.arg for a in method.args.args]
    # The model id is data in the client since 2026-10-10: required, no default.
    required = names[:len(names) - len(method.args.defaults)]
    assert required == ["self", "source_prompt", "model_id"]
    assert f"'{ROUTE}'" in ast.get_source_segment(source, method)
    posts = [c for c in _calls(method) if any(
        isinstance(a, ast.Constant) and a.value == ROUTE for a in c.args)]
    assert len(posts) == 1, "one call that posts to the route"
    payload = next(a for a in posts[0].args if isinstance(a, ast.Name))
    assigned = [n.value for n in ast.walk(method) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == payload.id for t in n.targets)]
    assert len(assigned) == 1 and isinstance(assigned[0], ast.Dict)
    sent = {k.value for k in assigned[0].keys}
    assert sent == _route_reads()
