"""Findings of the code review of 2026-10-10, package D2, held by one test each.

S-026  The Diffusers client carried a model id as the default of nine methods;
       every caller names the model, so the parameter has no default.
S-031  The router removed the nodes of one chunk by their ids; the chunk now
       declares what to drop and the router reads it.
S-032  The interception engine booked every cloud call under an attribute
       nothing set; the executor says which stage a config is and the request
       carries it.
S-012  Five sampling numbers were accepted, bounded and stored while no model
       call read them.
S-011  The output configs on JSON chunks carried an uppercase generation block
       that nothing on the generation path read, and the sheet on a card's
       back stood in with those numbers. A config on a Python chunk keeps its
       block: the router calls execute(**parameters) and the chunk takes the
       keys as named parameters (second review of 2026-10-10, which found
       four values the first pass had struck).
S-036  The LLM client's docstring claimed every local inference ran on the
       node package; the classify path runs on the GPU service.
S-039  Three sentences of the Flow's description contradicted the surface.
"""
import ast
import copy
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
DEVSERVER = REPO / "devserver"
sys.path.insert(0, str(DEVSERVER))

CONFIGS = DEVSERVER / "schemas/configs"
CHUNKS = DEVSERVER / "schemas/chunks"


# --- S-026 -------------------------------------------------------------------

def test_the_diffusers_client_takes_the_model_it_is_told():
    from my_app.services.diffusers_client import DiffusersClient
    for name, member in inspect.getmembers(DiffusersClient, inspect.iscoroutinefunction):
        if not name.startswith("generate_"):
            continue
        param = inspect.signature(member).parameters.get("model_id")
        assert param is not None, name
        assert param.default is inspect.Parameter.empty, f"{name} defaults its model"


def test_the_gpu_service_names_its_default_model_once():
    gpu = REPO / "gpu_service"
    literal = "stabilityai/stable-diffusion-3.5-large"
    carriers = []
    for path in sorted(list((gpu / "routes").glob("*.py")) + list((gpu / "services").glob("*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prose = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                        and isinstance(body[0].value.value, str):
                    prose.update(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if number in prose or line.lstrip().startswith("#"):
                continue
            if literal in line:
                carriers.append(f"{path.relative_to(REPO)}:{number}")
    assert carriers == [], carriers
    assert f'DEFAULT_MODEL_ID = "{literal}"' in (gpu / "config.py").read_text(encoding="utf-8")


# --- S-031 -------------------------------------------------------------------

def _qwen_chunk():
    return json.loads((CHUNKS / "output_image_qwen_2511_multi.json").read_text(encoding="utf-8"))


def test_the_router_names_no_node_of_any_chunk():
    source = (DEVSERVER / "schemas/engine/backend_router.py").read_text(encoding="utf-8")
    for node_id in _qwen_chunk()["workflow"]:
        assert f"'{node_id}'" not in source and f'"{node_id}"' not in source, node_id


@pytest.mark.parametrize("provided, gone_nodes, gone_inputs", [
    ({"input_image1": "a.png"},
     {"120", "121", "122", "123"}, {"image2", "image3"}),
    ({"input_image1": "a.png", "input_image2": "b.png"},
     {"121", "123"}, {"image3"}),
    ({"input_image1": "a.png", "input_image2": "b.png", "input_image3": "c.png"},
     set(), set()),
    ({"input_image1": "a.png", "input_image2": ""},
     {"120", "121", "122", "123"}, {"image2", "image3"}),
])
def test_the_adaptation_follows_the_chunks_declaration(provided, gone_nodes, gone_inputs):
    from schemas.engine.backend_router import _adapt_workflow_for_multi_image
    chunk = _qwen_chunk()
    before = copy.deepcopy(chunk["workflow"])
    after = _adapt_workflow_for_multi_image(copy.deepcopy(before), provided,
                                            chunk["multi_image_adaptation"])
    assert set(before) - set(after) == gone_nodes
    for encoder in ("115:110", "115:111"):
        assert set(before[encoder]["inputs"]) - set(after[encoder]["inputs"]) == gone_inputs
    # Nothing else changed.
    for node_id in after:
        if node_id in ("115:110", "115:111"):
            continue
        assert after[node_id] == before[node_id], node_id


def test_a_chunk_that_declares_nothing_is_left_as_it_is():
    from schemas.engine.backend_router import _adapt_workflow_for_multi_image
    workflow = {"120": {"inputs": {"image2": 1}}}
    assert _adapt_workflow_for_multi_image(copy.deepcopy(workflow), {"input_image1": "a"}, None) == workflow


# --- S-032 -------------------------------------------------------------------

def test_the_usage_stage_follows_the_configs_stage():
    from schemas.engine.pipeline_executor import usage_stage_of
    assert usage_stage_of(SimpleNamespace(meta={"stage": "pre_interception"})) == "stage1"
    assert usage_stage_of(SimpleNamespace(meta={"stage": "interception"})) == "stage2"
    assert usage_stage_of(SimpleNamespace(meta={"stage": "pre_output"})) == "stage3"
    assert usage_stage_of(SimpleNamespace(meta={"stage": "output"})) == "stage4"
    assert usage_stage_of(SimpleNamespace(meta={})) == "stage2"
    assert usage_stage_of(None) == "stage2"


def test_every_shipped_config_declares_a_stage_the_table_knows():
    from schemas.engine.pipeline_executor import USAGE_STAGE_OF_CONFIG_STAGE
    from schemas.engine.config_loader import EXCLUDED_CONFIG_DIRS
    unknown = []
    for path in sorted(CONFIGS.rglob("*.json")):
        if EXCLUDED_CONFIG_DIRS & set(path.relative_to(CONFIGS).parts):
            continue
        if "user_configs" in path.relative_to(CONFIGS).parts:
            continue
        stage = (json.loads(path.read_text(encoding="utf-8")).get("meta") or {}).get("stage")
        if stage not in USAGE_STAGE_OF_CONFIG_STAGE:
            unknown.append(f"{path.relative_to(CONFIGS)}: {stage!r}")
    assert unknown == [], unknown


def test_the_engine_books_the_stage_the_request_carries():
    source = (DEVSERVER / "schemas/engine/prompt_interception_engine.py").read_text(encoding="utf-8")
    assert "_current_stage" not in source
    assert source.count("stage=usage_stage") == 2
    executor = (DEVSERVER / "schemas/engine/pipeline_executor.py").read_text(encoding="utf-8")
    assert "usage_stage=usage_stage_of(resolved_config)" in executor


# --- S-012 -------------------------------------------------------------------

RETIRED = {"top_p", "top_k", "min_p", "presence_penalty", "frequency_penalty"}
# What a parameter can reach: the engine's two model calls, and the chunks that
# read a key of their own (text_transformation_recursive).
READ_BY_A_MODEL_CALL = {"temperature", "max_tokens", "repetition_penalty", "enable_thinking"}
READ_BY_A_CHUNK = {"iterations", "use_random_languages", "final_language"}


def test_a_kept_perspective_may_carry_only_what_is_read():
    from my_app.routes.interception_prompts_routes import ALLOWED_PARAM_KEYS, _PARAM_BOUNDS
    assert ALLOWED_PARAM_KEYS <= READ_BY_A_MODEL_CALL | READ_BY_A_CHUNK
    assert set(_PARAM_BOUNDS) <= ALLOWED_PARAM_KEYS
    assert not RETIRED & ALLOWED_PARAM_KEYS


def test_the_engine_reads_what_the_table_says():
    source = (DEVSERVER / "schemas/engine/prompt_interception_engine.py").read_text(encoding="utf-8")
    for key in READ_BY_A_MODEL_CALL:
        assert f'"{key}"' in source, key
    for key in RETIRED:
        assert f'"{key}"' not in source and f"'{key}'" not in source, key


def test_no_shipped_config_or_chunk_carries_a_retired_sampling_number():
    from schemas.engine.config_loader import EXCLUDED_CONFIG_DIRS

    def carries(obj):
        if isinstance(obj, dict):
            return (set(obj) & RETIRED) or any(carries(v) for v in obj.values())
        if isinstance(obj, list):
            return any(carries(v) for v in obj)
        return False

    found = []
    for path in sorted(CONFIGS.rglob("*.json")):
        if EXCLUDED_CONFIG_DIRS & set(path.relative_to(CONFIGS).parts):
            continue
        if carries(json.loads(path.read_text(encoding="utf-8"))):
            found.append(str(path.relative_to(DEVSERVER)))
    for path in sorted(CHUNKS.glob("*.json")):
        if carries(json.loads(path.read_text(encoding="utf-8"))):
            found.append(str(path.relative_to(DEVSERVER)))
    assert found == [], found


# --- S-011 -------------------------------------------------------------------

def _execute_parameter_names(chunk_py: Path) -> set:
    tree = ast.parse(chunk_py.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "execute":
            return {a.arg for a in node.args.args + node.args.kwonlyargs}
    return set()


def test_an_uppercase_key_in_an_output_config_is_one_its_python_chunk_names():
    """A config on a JSON chunk carries no uppercase block: the router fills the
    workflow from the chunk's lowercase mappings. A config on a Python chunk
    carries only the keys `execute` names, which the router passes as
    `execute(**parameters)`."""
    found = []
    for path in sorted((CONFIGS / "output").glob("*.json")):
        params = json.loads(path.read_text(encoding="utf-8")).get("parameters") or {}
        upper = [k for k in params if k.isupper() and k != "OUTPUT_CHUNK"]
        if not upper:
            continue
        chunk_py = CHUNKS / f"{params.get('OUTPUT_CHUNK')}.py"
        if not chunk_py.exists():
            found.append(f"{path.name}: {upper} on a JSON chunk")
            continue
        unnamed = sorted(set(upper) - _execute_parameter_names(chunk_py))
        if unnamed:
            found.append(f"{path.name}: {unnamed} not named by {chunk_py.name}")
    assert found == [], found


def test_the_four_values_the_second_review_restored():
    """The second review of 2026-10-10 found four values the first pass had
    struck although their Python chunks read them; these are the values that
    stood before, and they differ from the chunks' DEFAULTS."""
    def params(name):
        return json.loads((CONFIGS / "output" / f"{name}.json").read_text(encoding="utf-8"))["parameters"]
    assert params("sd35_large_diffusers")["CFG"] == 5.5
    assert params("stableaudio_music")["SECONDS"] == 47.6
    assert params("stableaudio_open")["SECONDS"] == 47.6
    assert params("stableaudio_sfx")["SECONDS"] == 12.0


def test_the_sheet_stands_in_with_the_chunks_numbers():
    from my_app.services.model_meta import build_model_meta
    ltx = json.loads((CHUNKS / "output_video_ltx.json").read_text(encoding="utf-8"))["input_mappings"]
    config = SimpleNamespace(meta={"backend_type": "comfyui"},
                             parameters={"OUTPUT_CHUNK": "output_video_ltx", "seed": "random"})
    sheet = build_model_meta(config)
    assert sheet["steps"] == ltx["steps"]["default"]
    assert sheet["cfg"] == ltx["cfg"]["default"]
    # What the run reports wins over the chunk's default.
    assert build_model_meta(config, steps=9, cfg=1.5)["steps"] == 9
    assert build_model_meta(config, steps=9, cfg=1.5)["cfg"] == 1.5
    # A config on a Python chunk has no mapping to read: nothing is invented.
    python_chunk = SimpleNamespace(meta={"backend_type": "diffusers"},
                                   parameters={"OUTPUT_CHUNK": "output_image_sd35_diffusers"})
    assert build_model_meta(python_chunk)["steps"] is None
    # A config on a Python chunk carries its steering in uppercase; the sheet
    # reads it after the lowercase keys.
    steered = SimpleNamespace(meta={"backend_type": "diffusers"},
                              parameters={"OUTPUT_CHUNK": "output_image_sd35_diffusers", "CFG": 5.5, "STEPS": 25})
    assert build_model_meta(steered)["cfg"] == 5.5
    assert build_model_meta(steered)["steps"] == 25


# --- S-036 -------------------------------------------------------------------

def test_the_llm_client_names_the_classify_path_as_the_exception():
    doc = ast.get_docstring(ast.parse((DEVSERVER / "my_app/services/llm_client.py").read_text(encoding="utf-8")))
    assert "safety_classifier.score" in doc
    assert "Every local inference (safety verification" not in doc


# --- S-039 -------------------------------------------------------------------

def test_the_flows_description_matches_its_surface():
    view = (REPO / "public/ai4artsed-frontend/src/views/x2x_flow.vue").read_text(encoding="utf-8")
    description = view.split("pageDescription:", 1)[1].split("pageContent:", 1)[0]
    # Four ways in, as addOptions lists them.
    assert view.count("{ id: 'text', d: D_TEXT") == 1
    assert "{ id: 'document', d: D_PDF" in view
    assert "die vier Wege auf, Material hereinzuholen — Text, Bild, Skizze, Dokument" in description
    # A click opens a perspective bubble and a LoRA tile (onFixtureClick).
    assert "openPerspEdit(b))" in view and "openLoraEdit(l))" in view
    assert "ein Klick auf ihre Blase öffnet sie zum Lesen und Ändern" in description
    assert "Ein Klick auf die Kachel öffnet ihre Stärke" in description
    assert "langer Druck auf ihre Blase" not in description
    assert "Doppelklick ebenso" not in description
