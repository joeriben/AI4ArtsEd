"""The encoder forward passes of encode_prompt_info run under the plant-wide
slot.

encode_prompt_info took the diffusers-load slot for a load and then ran three
encoder forward passes (CLIP-L, CLIP-G, T5) in a worker thread with no slot,
under the inference lock alone; the coverage check counted the method as
covered because it mentions load_model (finding S-003 of the code review of 2026-10-10). Rule 15 admits every forward.

Read structurally, because the test venv carries no torch and the forward
cannot run here: the worker the method hands its forward to is the backend's
slot-taking runner, _locked_generate, which takes the slot and then the lock.
"""
import ast
import os

BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "services", "diffusers_backend.py")


def _encode_prompt_info():
    tree = ast.parse(open(BACKEND, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "encode_prompt_info":
            return node
    raise AssertionError("encode_prompt_info is gone")


def test_the_forward_is_handed_to_the_slot_taking_runner():
    handed = []
    for node in ast.walk(_encode_prompt_info()):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "to_thread"):
            handed.append(ast.unparse(node.args[0]))
    assert handed, "encode_prompt_info runs no worker any more; read it again"
    assert all(h == "self._locked_generate" for h in handed), (
        "a worker of encode_prompt_info runs a forward past the slot: " + ", ".join(handed))


def test_the_runner_takes_the_slot_for_the_model_it_is_given():
    """_locked_generate keyed the slot by the request's context variable or
    the last model loaded; the describing call names its own model."""
    tree = ast.parse(open(BACKEND, encoding="utf-8").read())
    runner = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_locked_generate")
    assert [a.arg for a in runner.args.args] == ["self", "fn", "model_id"]


def test_the_model_is_kept_from_eviction_from_its_load_on():
    """Every generation of this backend takes its model's refcount right after
    the load (PART 27), so a load of another model cannot take it off the card
    before the forward. encode_prompt_info took the count only after the three
    tokenizers had run (until the second review of 2026-10-10): the count is
    taken before the pipeline is read off the cache, and given back in a
    finally that covers the forward."""
    fn = _encode_prompt_info()
    src = ast.unparse(fn)
    take = "self._model_in_use[model_id] = self._model_in_use.get(model_id, 0) + 1"
    assert src.count(take) == 1, "the encoder path takes its refcount once"
    assert src.index(take) < src.index("pipe = self._pipelines[model_id]"), (
        "the refcount is taken after the pipeline was read off the cache")
    guarded = [n for n in ast.walk(fn) if isinstance(n, ast.Try) and n.finalbody
               and "self._model_in_use[model_id] -= 1" in ast.unparse(n.finalbody)]
    assert len(guarded) == 1
    body = ast.unparse(guarded[0].body)
    assert "pipe = self._pipelines[model_id]" in body
    assert "_tokenize(pipe.tokenizer" in body
    assert "asyncio.to_thread(self._locked_generate, _encode, model_id)" in body
