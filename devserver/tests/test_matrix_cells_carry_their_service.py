"""Every model cell of the matrix carries its service when the file is written
(settings_routes._prefix_cells, 2026-09-12).

The operator types the path as the provider publishes it into the provider's
column; the platform id '<service>/<path>' is composed on the way into the
file, never shown and never asked for. Until then a cloud cell typed without
'/' was a LOCAL model to is_local(), and one typed as 'openai/gpt-oss-120b'
into the IONOS column went to OpenAI with the OpenAI key.
"""
import copy
import json
import sys
from pathlib import Path

DEVSERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEVSERVER))

from my_app.routes import settings_routes as sr  # noqa: E402


def _composed(matrix):
    m = copy.deepcopy(matrix)
    sr._prefix_cells(m)
    return m


def test_a_cloud_cell_gets_its_columns_service_and_only_that_one():
    m = _composed({"llm_presets": {
        "ionos": {"models": {"A": "openai/gpt-oss-120b", "B": "ionos/openai/gpt-oss-120b"}},
        "openrouter": {"models": {"A": "anthropic/claude-sonnet-5"}},
        "mammouth": {"models": {"A": " glm-5.3 "}},
        "bedrock": {"models": {"A": "eu.anthropic.claude-sonnet-4-5"}},
    }})
    assert m["llm_presets"]["ionos"]["models"] == {"A": "ionos/openai/gpt-oss-120b",
                                                   "B": "ionos/openai/gpt-oss-120b"}
    assert m["llm_presets"]["openrouter"]["models"]["A"] == "openrouter/anthropic/claude-sonnet-5"
    assert m["llm_presets"]["mammouth"]["models"]["A"] == "mammouth/glm-5.3"
    assert m["llm_presets"]["bedrock"]["models"]["A"] == "bedrock/eu.anthropic.claude-sonnet-4-5"


def test_the_chat_models_are_cells_of_the_same_column():
    m = _composed({"llm_presets": {"mammouth": {
        "models": {}, "chat_models": ["glm-5.3", " kimi-k3 ", "mammouth/gpt-5.6-terra", "local/x", "", None]}}})
    assert m["llm_presets"]["mammouth"]["chat_models"] == [
        "mammouth/glm-5.3", "mammouth/kimi-k3", "mammouth/gpt-5.6-terra", "local/x", "", None]


def test_the_local_and_the_vision_cells_carry_local():
    m = _composed({
        "local_llm_presets": {"vram_16": {"models": {"A": "qwen3.5:9b", "B": "local/qwen3.5:27b"}}},
        "vision_presets": {"vram_16": {"IMAGE_ANALYSIS_MODEL": "qwen3-vl:4b"}},
    })
    assert m["local_llm_presets"]["vram_16"]["models"] == {"A": "local/qwen3.5:9b",
                                                            "B": "local/qwen3.5:27b"}
    assert m["vision_presets"]["vram_16"] == {"IMAGE_ANALYSIS_MODEL": "local/qwen3-vl:4b"}


def test_a_local_id_in_a_cloud_column_stays_local():
    """A working configuration that stays on this machine; no provider
    publishes a path starting with 'local/'."""
    m = _composed({"llm_presets": {"mammouth": {"models": {"A": "local/qwen3.5:9b"}}}})
    assert m["llm_presets"]["mammouth"]["models"]["A"] == "local/qwen3.5:9b"


def test_what_is_not_a_path_is_written_as_it_came():
    """This composes, it does not validate: empty cells are dropped by the
    page, and a preset that is not a dict was written before too."""
    raw = {"llm_presets": {
        "ionos": {"models": {"C": "", "D": "  ", "E": 5, "F": None}},
        "mammouth": "garbage", "mistral": None, "openai": ["x"],
        "not-a-provider": {"models": {"A": "y"}},
    }, "local_llm_presets": {"vram_8": "garbage"}, "vision_presets": {"vram_8": None}}
    assert _composed(raw) == raw
    for bad in (None, [], "x", 7, {"llm_presets": []}, {"llm_presets": {"ionos": {"models": []}}}):
        sr._prefix_cells(bad)


def test_composing_twice_is_composing_once():
    once = _composed({"llm_presets": {"ionos": {"models": {"A": "openai/gpt-oss-120b"}}},
                      "local_llm_presets": {"vram_16": {"models": {"A": "qwen3.5:9b"}}}})
    assert _composed(once) == once


def test_the_shipped_register_already_carries_every_service():
    """The composer changes nothing in the file as it ships: every cell there
    is written with its service, which is the form this keeps."""
    shipped = json.loads((DEVSERVER / "hardware_matrix.defaults.json").read_text())
    assert _composed(shipped) == shipped
