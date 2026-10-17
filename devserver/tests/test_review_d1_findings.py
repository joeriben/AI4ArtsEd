"""Five findings of the code review of 2026-10-10, held by one test each.

S-010  Two configs named after ACE-Step ran HeartMuLa (their pipeline carries
       output_music_heartmula), one ran ComfyUI's own AceStep nodes while the
       installer cloned a package no chunk uses; all three are retired, and
       the music default names the config that runs the chunk under its own
       name.
S-013  Three ComfyUI nodes caught every exception and returned their input, so
       a run whose fusion failed sampled a picture without the fusion under a
       successful run. They raise.
S-029  The hidden flag stands in three places in the shipped configs and was
       read in four combinations; one reading, every place.
S-052  The only stage-2 path of both living routes was marked deprecated and
       warned on every call.
S-059  The ComfyUI-backed Composable Diffusion config was named "(Diffusers)"
       beside the Diffusers twin of the same name.
"""
import ast
import json
import sys
import warnings
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DEVSERVER = REPO / "devserver"
sys.path.insert(0, str(DEVSERVER))

CONFIGS = DEVSERVER / "schemas/configs/output"
NODES = REPO / "comfyui_nodes/ai4artsed_comfyui"


# --- S-010 -------------------------------------------------------------------

def test_the_acestep_configs_are_retired_and_the_music_default_runs_its_own_chunk():
    for name in ("acestep_simple", "acestep_longnarrativeprompts", "acenet_t2instrumental"):
        assert not (CONFIGS / f"{name}.json").exists(), name
        assert (CONFIGS / f"{name}.json.disabled").exists(), name
    defaults = json.loads((DEVSERVER / "schemas/output_config_defaults.json").read_text(encoding="utf-8"))
    music = defaults["music"]
    config = json.loads((CONFIGS / f"{music}.json").read_text(encoding="utf-8"))
    pipeline = json.loads((DEVSERVER / "schemas/pipelines" / f"{config['pipeline']}.json").read_text(encoding="utf-8"))
    chunks = pipeline.get("chunks", [])
    named = (config.get("parameters") or {}).get("OUTPUT_CHUNK")
    chunks = [named if c == "{{OUTPUT_CHUNK}}" else c for c in chunks]
    assert "output_music_heartmula" in chunks, (music, chunks)
    assert "heartmula" in music


def test_the_installer_clones_no_package_no_chunk_uses():
    text = (REPO / "install_comfyui_nodes.sh").read_text(encoding="utf-8")
    assert "sound-lab.git" not in text
    assert "[1/2]" in text and "[2/2]" in text and "[3/3]" not in text


# --- S-013 -------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "ai4artsed_t5_clip_fusion.py",
    "ai4artsed_conditioning_fusion.py",
    "ai4artsed_vector_dimension_eliminator.py",
])
def test_a_node_that_fails_does_not_hand_back_its_input(name):
    """Read as a syntax tree: the node files import torch, which the test venv
    does not carry. No `except` in them returns a value."""
    tree = ast.parse((NODES / name).read_text(encoding="utf-8"), filename=name)
    returning = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return):
                    returning.append(inner.lineno)
    assert returning == [], f"{name}: an except returns a value at line(s) {returning}"


# --- S-029 -------------------------------------------------------------------

def test_the_hidden_flag_is_read_the_same_everywhere():
    from schemas.engine.config_loader import config_is_hidden
    assert config_is_hidden({"hidden": True})
    assert config_is_hidden({"meta": {"hidden": True}})
    assert config_is_hidden({"display": {"hidden": True}})
    assert not config_is_hidden({"display": {"hidden": False}, "meta": {}})
    assert not config_is_hidden({})
    assert not config_is_hidden(None)
    # The four readers read it the one way and not their own.
    for rel in ("my_app/routes/schema_pipeline_routes.py",
                "my_app/routes/settings_routes.py",
                "my_app/services/model_availability_service.py",
                "my_app/services/lora_register.py"):
        text = (DEVSERVER / rel).read_text(encoding="utf-8")
        assert "config_is_hidden" in text, rel
        assert '.get("hidden")' not in text, rel
        assert 'get("display", {}).get("hidden"' not in text, rel


# --- S-052 -------------------------------------------------------------------

def test_the_stage2_composition_is_not_deprecated(monkeypatch):
    import asyncio
    from my_app.routes import schema_pipeline_routes as R

    async def interception(**kwargs):
        return R._ClassifierResult(success=True, final_output="written")

    monkeypatch.setattr(R, "execute_stage2_interception", interception)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        result = asyncio.run(R.execute_stage2_with_optimization(
            schema_name="bauhaus", input_text="a house", config=None, safety_level="open"))
    assert result.final_output == "written"
    assert [w for w in seen if issubclass(w.category, DeprecationWarning)] == []


# --- S-059 -------------------------------------------------------------------

def test_no_comfyui_config_is_named_after_diffusers():
    named = []
    for path in sorted(CONFIGS.glob("*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        backend = (config.get("meta") or {}).get("backend_type")
        name = config.get("name") or {}
        english = name.get("en", "") if isinstance(name, dict) else str(name)
        if backend == "comfyui" and "diffusers" in english.lower():
            named.append(f"{path.name}: {english}")
    assert named == [], named
