"""
Every output config's run names the model it generated with.

The provenance card, the media entries of the run record and the AI-Origin
Disclosure name the model by `model_used` in the metadata of the BackendResponse
(backend_router.py). It is reported by the place that ran the model, in the
form that place names it:

  - a ComfyUI workflow: the files its loaders load, read off the workflow as it
    is submitted (comfyui_ws_client.models_in_workflow, on every
    GenerationResult);
  - an API chunk: the `model` its request body names;
  - a Python chunk: the `model_used` key of the dict its `execute` returns.

Until 2026-10-31 the card named the config's `display_name`, which on the
Latent Lab's instruments names the instrument and on the Stable Audio presets
the preset, and the chunks that reported a model did so under three keys.

Run: pytest devserver/tests/test_model_used_coverage.py
"""

import ast
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from file_modules import DEVSERVER
from test_output_config_carry_list import (
    CHUNK_DIR, _chunks_a_config_reaches, _configs, _pipelines,
)

sys.path.insert(0, str(DEVSERVER))

from my_app.services import comfyui_ws_client  # noqa: E402
from my_app.services.comfyui_ws_client import models_in_workflow  # noqa: E402
from my_app.services.model_meta import build_model_meta  # noqa: E402

# The chunks whose run loads no model, each with the reason. This list only
# shrinks: a chunk that comes to load a model reports it and leaves the list
# (test_the_exceptions_still_hold).
NO_MODEL_RUNS = {
    "output_code_p5js": "text_passthrough: the run hands on the code the "
                        "Adaption wrote before it, in the /optimize request",
    "output_code_tonejs": "text_passthrough: the run hands on the code the "
                          "Adaption wrote before it, in the /optimize request",
    "output_speech_espeak": "eSpeak NG speaks from rules; it is the synthesiser "
                            "from before AI the voices comparison sets beside "
                            "the models, and it loads no weights",
}


def _fallback_of(name: str):
    """The chunk the router runs when this Python chunk cannot
    (CHUNK_META["fallback_chunk"]), or None."""
    path = CHUNK_DIR / f"{name}.py"
    if not path.is_file():
        return None
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "CHUNK_META" for t in node.targets)):
            return (ast.literal_eval(node.value) or {}).get("fallback_chunk") or None
    return None


def _chunks_of_the_output_configs() -> list:
    """Every chunk an output config's run can end in, its fallbacks included."""
    pipelines = _pipelines()
    found = set()
    for config in _configs().values():
        names, _where = _chunks_a_config_reaches(config, pipelines)
        for name in names:
            while name and name not in found:
                found.add(name)
                name = _fallback_of(name)
    return sorted(found)


def _own_nodes(func):
    """The nodes of a function's body, without those of functions defined in it."""
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    stack = [node for node in func.body if not isinstance(node, nested)]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(child for child in ast.iter_child_nodes(node)
                     if not isinstance(child, nested))


def _names_model_used(node) -> bool:
    return isinstance(node, ast.Dict) and any(
        isinstance(k, ast.Constant) and k.value == "model_used" for k in node.keys)


def _what_execute_returns_without_a_model(path: Path) -> list:
    """The returns of the chunk's `execute` that carry no `model_used`: a dict
    literal without the key, or a name not bound to one with it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    execute = next((n for n in tree.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name == "execute"), None)
    if execute is None:
        return ["no execute()"]
    bound = {}
    for node in _own_nodes(execute):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.setdefault(target.id, []).append(node.value)
    missing = []
    for node in _own_nodes(execute):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        if _names_model_used(value):
            continue
        if (isinstance(value, ast.Name) and bound.get(value.id)
                and all(_names_model_used(v) for v in bound[value.id])):
            continue
        missing.append(f"line {node.lineno}: return {ast.unparse(value) if value else ''}")
    return missing


@pytest.mark.parametrize("name", _chunks_of_the_output_configs())
def test_the_chunk_of_every_output_config_reports_its_model(name):
    if name in NO_MODEL_RUNS:
        pytest.skip(NO_MODEL_RUNS[name])
    py, js = CHUNK_DIR / f"{name}.py", CHUNK_DIR / f"{name}.json"
    if py.is_file():
        missing = _what_execute_returns_without_a_model(py)
        assert not missing, (
            f"{name}.execute returns without `model_used`: {missing}. The router "
            f"hands the dict on as the BackendResponse's metadata, and the card "
            f"names the model by that key.")
        return
    chunk = json.loads(js.read_text(encoding="utf-8"))
    if isinstance(chunk.get("workflow"), dict):
        assert models_in_workflow(chunk["workflow"]), (
            f"{name}: no node of its workflow loads a model "
            f"(comfyui_ws_client.models_in_workflow reads CheckpointLoaderSimple, "
            f"UNETLoader and the platform's own nodes).")
        return
    request = ((chunk.get("api_config") or {}).get("request_body") or {})
    assert isinstance(request.get("model"), str) and request["model"], (
        f"{name}: neither a workflow nor an API request body that names a model; "
        f"the router reports `model_used` from one of the two.")


def test_the_exceptions_still_hold():
    reached = set(_chunks_of_the_output_configs())
    for name in NO_MODEL_RUNS:
        assert name in reached, f"{name} is no output config's chunk any more; take it off the list"
        py, js = CHUNK_DIR / f"{name}.py", CHUNK_DIR / f"{name}.json"
        if js.is_file():
            assert json.loads(js.read_text(encoding="utf-8")).get("type") == "text_passthrough", name
        else:
            assert "model_used" not in py.read_text(encoding="utf-8"), (
                f"{name} reports a model now; take it off NO_MODEL_RUNS")


def test_the_executor_hands_model_used_on():
    """A key a chunk returns reaches the run only through the executor's list
    (pipeline_executor.py: "named in THREE places")."""
    source = (DEVSERVER / "schemas" / "engine" / "pipeline_executor.py").read_text(encoding="utf-8")
    gate = next(m.group(0) for m in re.finditer(r"for key in \[[^\]]*\]", source)
                if "'latent_meta'" in m.group(0))
    assert "'model_used'" in gate


# --- the media stations hand the model on ------------------------------------

def _stand_in_for_the_run(monkeypatch, media_type, ui=None):
    """The node's run at ComfyUI, as run_node_files answers it, with the
    model the run loaded under a name of its own."""
    from my_app.services.comfyui_ws_client import MediaFile
    from my_app.services.llm_client import LLMClient

    def run_node_files(cls, class_type, inputs, workload=None):
        return ui or {}, [MediaFile(data=b"made", filename="f", media_type=media_type)], "the-loaded-model"

    monkeypatch.setattr(LLMClient, "run_node_files", classmethod(run_node_files))


def test_stable_audio_hands_on_the_model_its_run_loaded(monkeypatch):
    from my_app.services.stable_audio_client import StableAudioClient
    _stand_in_for_the_run(monkeypatch, "audio")
    monkeypatch.setattr(StableAudioClient, "_model_dir", staticmethod(lambda kind="music": "folder"))
    assert StableAudioClient().generate_audio_sync("rain") == (b"made", "the-loaded-model")


def test_heartmula_hands_on_the_model_its_run_loaded(monkeypatch):
    from my_app.services.heartmula_client import HeartMuLaClient
    _stand_in_for_the_run(monkeypatch, "audio")
    monkeypatch.setattr(HeartMuLaClient, "_first_installed", lambda self: ("alias", "folder", "3B"))
    assert HeartMuLaClient().generate_music_sync("[Verse] la", "pop") == (b"made", "the-loaded-model")


def test_hunyuan3d_hands_on_the_model_its_run_loaded(monkeypatch):
    from my_app.services.hunyuan3d_client import Hunyuan3DClient
    _stand_in_for_the_run(monkeypatch, "mesh", ui={"seed": 7})
    monkeypatch.setattr(Hunyuan3DClient, "_first_installed", lambda self: ("alias", "folder"))
    assert Hunyuan3DClient().generate_mesh_sync("aW1hZ2U=") == (b"made", 7, "the-loaded-model")


# --- the reading of a ComfyUI workflow ---------------------------------------

def test_a_workflow_is_named_by_its_loader_and_not_by_encoders_vae_or_lora():
    workflow = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "maker/model.safetensors"}},
        "5": {"class_type": "TripleCLIPLoader", "inputs": {"clip_name1": "clip_l.safetensors"}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": "vae.safetensors"}},
        "7": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "style.safetensors"}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0]}},
    }
    assert models_in_workflow(workflow) == "maker/model.safetensors"


def test_two_experts_are_both_named():
    workflow = {
        "37": {"class_type": "UNETLoader", "inputs": {"unet_name": "high_noise.safetensors"}},
        "56": {"class_type": "UNETLoader", "inputs": {"unet_name": "low_noise.safetensors"}},
    }
    assert models_in_workflow(workflow) == "high_noise.safetensors + low_noise.safetensors"


def test_a_node_of_the_platform_is_named_by_its_alias(monkeypatch):
    """The name the dispatch announces for the model-place bar (_checkpoint_of)."""
    from my_app.services import local_media_weights
    monkeypatch.setattr(local_media_weights, "alias_of_folder",
                        lambda folder: "the-alias" if folder == "the-folder" else None)
    workflow = {"1": {"class_type": "ai4artsed_stable_audio",
                      "inputs": {"model_name": "the-folder", "prompt": "rain"}}}
    assert models_in_workflow(workflow) == "the-alias"
    assert comfyui_ws_client._checkpoint_of(workflow) == "the-alias"


def test_a_workflow_without_a_loader_names_nothing():
    assert models_in_workflow({"1": {"class_type": "KSampler", "inputs": {}}}) == ""
    assert models_in_workflow(None) == ""


# --- the sheet -----------------------------------------------------------------

def test_the_sheet_carries_the_model_the_run_reported():
    config = SimpleNamespace(meta={"display_name": "Concept Algebra (SD 3.5)"}, parameters={})
    sheet = build_model_meta(config, model_used="sd3.5_large.safetensors")
    assert sheet["model_used"] == "sd3.5_large.safetensors"
    assert sheet["display_name"] == "Concept Algebra (SD 3.5)"


def test_no_model_on_the_sheet_without_a_report():
    config = SimpleNamespace(meta={"display_name": "Declared"}, parameters={})
    assert "model_used" not in build_model_meta(config)
    assert "model_used" not in build_model_meta(config, model_used="")
