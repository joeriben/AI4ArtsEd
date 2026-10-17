#!/usr/bin/env python3
"""A fallback that hides itself is worse than none.

Stage 0.5 B of the ComfyUI migration.

Two chunks name a ComfyUI twin in CHUNK_META.fallback_chunk, and the router runs
it when the direct backend fails. Both halves of that were wrong until
2026-09-07:

  * The suppression asked only whether the card was BUSY or unreachable. A card
    that ran out of memory fell through, and the twin made the picture on the
    same exhausted card.
  * The substitution was reported by the direct endpoint alone. The streaming
    route, the flow surface's own route and the canvas — the ways people
    actually generate — passed a media_output that named nothing, so a run was
    booked under the config nobody had run. The two do not make the same picture
    out of the same seed.

Run: pytest devserver/tests/test_fallback_is_honest.py
"""

import ast
import re
import sys

import pytest

from file_modules import REPO

ROUTER = REPO / "devserver" / "schemas" / "engine" / "backend_router.py"
ROUTES = REPO / "devserver" / "my_app" / "routes" / "schema_pipeline_routes.py"

sys.path.insert(0, str(REPO / "devserver"))


def _predicate():
    from schemas.engine.backend_router import BackendRouter
    return BackendRouter._is_card_fault


# The wordings that reach the router, each from the side that writes it.
@pytest.mark.parametrize("reason", [
    "Device busy",
    "GPU not reachable",
    # torch's own allocator, verbatim in shape
    "CUDA out of memory. Tried to allocate 2.00 GiB. GPU 0 has a total capacity of ...",
    "torch.OutOfMemoryError: CUDA out of memory",
])
def test_a_card_fault_keeps_the_run_on_the_chunk_that_was_asked_for(reason):
    assert _predicate()(reason) is True, (
        f"{reason!r} reads as a working card, so the run would be handed to a "
        f"second model on the same card")


# A backend that broke for its own reasons is what the fallback exists for.
@pytest.mark.parametrize("reason", [
    "Model file not found: sd3.5_large.safetensors",
    "Connection refused",
    "diffusers backend unavailable",
    "",
    None,
])
def test_a_backend_fault_still_reaches_the_fallback(reason):
    assert _predicate()(reason) is False, (
        f"{reason!r} reads as a card fault, so the fallback that exists for it "
        f"would be skipped")


def _function_source(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(path.read_text(encoding="utf-8"), node)
    raise AssertionError(f"{path.name} holds no function {name!r}")


def _enclosing_writes_of(path, key):
    """Names of the functions that WRITE `key` — as a dict entry or by
    subscript — anywhere in the file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    writers = set()
    for parent in ast.walk(tree):
        if not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(parent):
            if isinstance(node, ast.Dict):
                if any(isinstance(k, ast.Constant) and k.value == key
                       for k in node.keys):
                    writers.add(parent.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Subscript)
                            and isinstance(target.slice, ast.Constant)
                            and target.slice.value == key):
                        writers.add(parent.name)
    return writers


def _stub_config(chunk_name):
    class _Config:
        parameters = {'OUTPUT_CHUNK': chunk_name} if chunk_name else {}

    class _Loader:
        def get_config(self, _config_id):
            return _Config() if chunk_name is not None else None

    class _Executor:
        config_loader = _Loader()

    return _Executor()


class _Answer:
    def __init__(self, metadata):
        self.metadata = metadata


def _fields(monkeypatch, requested, actual_metadata):
    from my_app.routes import schema_pipeline_routes as routes
    monkeypatch.setattr(routes, 'pipeline_executor', _stub_config(requested))
    return routes._generator_fields('some_config', _Answer(actual_metadata))


def test_a_substitution_is_seen(monkeypatch):
    """The case the whole thing exists for: the config named one chunk and
    another one wrote the file."""
    fields = _fields(monkeypatch, 'output_image_sd35_diffusers',
                     {'chunk_name': 'output_image_sd35_large'})
    assert fields['generator'] == 'output_image_sd35_large'
    assert fields['generator_requested'] == 'output_image_sd35_diffusers'
    assert fields['generator_substituted'] is True


def test_the_ordinary_run_is_not_called_a_substitution(monkeypatch):
    fields = _fields(monkeypatch, 'output_image_sd35_large',
                     {'chunk_name': 'output_image_sd35_large'})
    assert fields['generator_substituted'] is False


@pytest.mark.parametrize("requested,metadata", [
    # The chunk that ran said nothing about itself.
    ('output_image_sd35_large', {}),
    ('output_image_sd35_large', None),
    # The config reaches its chunk through the pipeline and names none itself.
    (None, {'chunk_name': 'output_music_heartmula'}),
])
def test_a_substitution_is_only_ever_claimed_when_both_names_are_known(
        monkeypatch, requested, metadata):
    """Half a reading is a guess. Where one of the two names is missing the
    answer is False — never a claim built on the one that is there."""
    fields = _fields(monkeypatch, requested, metadata)
    assert fields['generator_substituted'] is False


def test_the_reading_stands_in_one_place():
    """Rule 13. The direct endpoint kept its own copy until 2026-09-07, and
    there are three ways into stage 4 that could each grow one."""
    writers = _enclosing_writes_of(ROUTES, 'generator_substituted')
    assert writers == {'_generator_fields'}, (
        f"'generator_substituted' is written in {sorted(writers)}. It belongs in "
        f"_generator_fields alone; every caller reads it from there.")


def test_every_way_into_stage_four_reads_it():
    """Three ways in, none of which meets the others. A new one that forgets
    this is a surface where a substituted run looks like an ordinary one."""
    text = ROUTES.read_text(encoding="utf-8")
    for function in ('execute_stage4_generation_only',
                     '_run_interception_pipeline',
                     '_run_direct_workflow'):
        source = _function_source(ROUTES, function)
        assert '_generator_fields(' in source, (
            f"{function} no longer reads which generator ran, so a substituted "
            f"run reaches the surface unmarked.")
    assert text.count('def _generator_fields(') == 1


def test_the_switch_is_consulted_where_the_fallback_is_decided():
    """The predicate alone decides nothing. Both places that can hand a run to
    a second model have to ask it."""
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"))
    asked_in = set()
    for parent in ast.walk(tree):
        if not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(parent):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == '_is_card_fault'):
                asked_in.add(parent.name)
    assert '_process_output_chunk' in asked_in, (
        "_process_output_chunk hands a failed Python chunk to its ComfyUI twin "
        "without asking whether the card is the problem.")
    assert '_fallback_to_comfyui' in asked_in, (
        "_fallback_to_comfyui no longer asks whether the card is the problem.")


# ---------------------------------------------------------------------------
# The whole trip, in one place. Every station of it dropped the reason once.
# ---------------------------------------------------------------------------

BACKENDS = REPO / "gpu_service" / "services"


class _FakeResponse:
    """What the gpu_service sends when a generation broke."""

    def __init__(self, payload, status=500, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text or str(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def test_the_reason_survives_the_trip():
    """CUDA says it, the route sends it, the client lifts it out, the chunk
    raises it, the router wraps it — and the switch reads it. Each station
    dropped it before 2026-09-07, and the switch was then deciding on a
    sentence that fit every failure there is."""
    from my_app.services.gpu_lease_client import BackendGenerationError

    said = "CUDA out of memory. Tried to allocate 2.00 GiB. GPU 0 has a total capacity of 94.97 GiB"
    lifted = BackendGenerationError.from_response(
        _FakeResponse({"success": False, "error": said}))
    # _execute_python_chunk wraps whatever the chunk raised.
    at_the_switch = f"Python chunk execution failed: {lifted}"

    assert "out of memory" in str(lifted).lower(), (
        f"the client flattened the reason to {lifted!r}")
    assert _predicate()(at_the_switch) is True, (
        f"the switch reads {at_the_switch!r} as a working card, so the run "
        f"would be handed to a second model on the same card")


def test_an_html_error_page_never_travels():
    """A server's own error page carries its file paths, and those have no
    business on a workshop screen. The judgement lives in reason_line."""
    from my_app.services.gpu_lease_client import BackendGenerationError

    page = "<!DOCTYPE html><html><head><title>500 Internal Server Error</title>"
    lifted = BackendGenerationError.from_response(
        _FakeResponse(None, status=500, text=page))
    assert "<" not in str(lifted), f"an error page reached the caller: {lifted!r}"


@pytest.mark.parametrize("backend,method", [
    ("diffusers_backend.py", "generate_image"),
    ("stable_audio_backend.py", "generate_audio"),
])
def test_the_backends_raise_rather_than_return_nothing(backend, method):
    """The first station. `return None` in the catch-all is where the reason
    used to die, and nothing downstream could put it back."""
    path = BACKENDS / backend
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == method):
            continue
        for handler in [h for n in ast.walk(node) if isinstance(n, ast.Try)
                        for h in n.handlers]:
            names = ast.dump(handler.type or ast.Constant(None))
            if "Exception" not in names or "GpuBusy" in names:
                continue
            returns_nothing = any(
                isinstance(inner, ast.Return)
                and (inner.value is None
                     or (isinstance(inner.value, ast.Constant)
                         and inner.value.value is None))
                for inner in handler.body)
            assert not returns_nothing, (
                f"{backend}::{method} answers a broken generation with None, so "
                f"the reason stays in this service's log and the caller gets "
                f"one sentence for every failure there is")
        return
    raise AssertionError(f"{backend} holds no {method}")
