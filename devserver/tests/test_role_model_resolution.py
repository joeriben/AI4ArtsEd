"""A role field takes a model the way its provider names it; the platform id
is made in the backend (settings_routes.resolve_role_model, 2026-09-12).

The settings page never shows the prefix that makes a path a platform id, so
what it sends is a provider's path, the register's name, a local model's name,
or an id it read back. What is resolved is the MODEL; the route is the one the
pickers offer for it (chat_routes._cloud_routes: conform first, the active
provider next, then the table).
"""
import sys
from pathlib import Path

DEVSERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEVSERVER))

from my_app.routes import settings_routes as sr  # noqa: E402

WORLD = {
    "local": ["qwen3.5:9b", "llama-guard3:1b"],
    "order": ["mammouth", "openrouter", "openai"],
    "routes": {
        "glm-5.3": {"mammouth": "glm-5.3", "openrouter": "z-ai/glm-5.3"},
        "gpt-5.6-terra": {"mammouth": "gpt-5.6-terra", "openrouter": "openai/gpt-5.6-terra",
                          "openai": "gpt-5.6-terra"},
        "claude-sonnet-5": {"openrouter": "anthropic/claude-sonnet-5",
                            "anthropic": "claude-sonnet-5"},
        "mistral-large-3": {"mistral": "mistral-large-2512"},
    },
}


def test_a_providers_path_names_the_model_and_the_route_is_the_lists():
    """OpenRouter's path, Mammouth's path, the register's name: one model,
    one route -- the first in the order that reaches it."""
    assert sr.resolve_role_model("z-ai/glm-5.3", WORLD) == "mammouth/glm-5.3"
    assert sr.resolve_role_model("glm-5.3", WORLD) == "mammouth/glm-5.3"
    assert sr.resolve_role_model("GLM-5.3", WORLD) == "mammouth/glm-5.3"


def test_a_path_that_is_also_another_providers_id_names_the_same_model():
    """'openai/gpt-5.6-terra' is OpenRouter's path and OpenAI's own id; both
    name gpt-5.6-terra, and neither is stored as the OpenAI direct route while
    a provider ahead of it in the order reaches the model."""
    assert sr.resolve_role_model("openai/gpt-5.6-terra", WORLD) == "mammouth/gpt-5.6-terra"
    assert sr.resolve_role_model("openrouter/openai/gpt-5.6-terra", WORLD) == "mammouth/gpt-5.6-terra"
    assert sr.resolve_role_model("mammouth/gpt-5.6-terra", WORLD) == "mammouth/gpt-5.6-terra"


def test_a_path_of_a_provider_without_a_key_still_names_the_model():
    """Anthropic holds no key here (it is not in the order), but its own id
    and OpenRouter's path for the model both find the route that exists."""
    assert sr.resolve_role_model("anthropic/claude-sonnet-5", WORLD) == "openrouter/anthropic/claude-sonnet-5"
    assert sr.resolve_role_model("claude-sonnet-5", WORLD) == "openrouter/anthropic/claude-sonnet-5"


def test_a_model_no_keyed_provider_reaches_is_stored_as_written():
    """Mistral is not in the order: the model is named, the route is nobody's."""
    assert sr.resolve_role_model("mistral-large-3", WORLD) == "mistral-large-3"
    assert sr.resolve_role_model("mistral/mistral-large-2512", WORLD) == "mistral/mistral-large-2512"


def test_a_name_the_local_station_lists_is_a_local_model():
    """Whatever a provider calls one of its own: the station's name wins, in
    the form it was written, with the station's spelling."""
    world = dict(WORLD, routes=dict(WORLD["routes"], **{"qwen3.5:9b": {"mammouth": "qwen3.5:9b"}}))
    assert sr.resolve_role_model("qwen3.5:9b", world) == "qwen3.5:9b"
    assert sr.resolve_role_model("local/qwen3.5:9b", world) == "local/qwen3.5:9b"
    assert sr.resolve_role_model("LOCAL/QWEN3.5:9B", world) == "local/qwen3.5:9b"
    assert sr.resolve_role_model("llama-guard3:1b", world) == "llama-guard3:1b"


def test_what_nobody_names_is_stored_as_written():
    assert sr.resolve_role_model("gemma3:4b", WORLD) == "gemma3:4b"
    assert sr.resolve_role_model("nobody/nothing", WORLD) == "nobody/nothing"
    assert sr.resolve_role_model("mammouth/gemini-3.6-flash", WORLD) == "mammouth/gemini-3.6-flash"
    assert sr.resolve_role_model("  ", WORLD) == ""


def test_the_world_is_read_once_per_save_and_ranked_by_the_saved_provider(monkeypatch):
    """One list build for every field of a save, ranked by the provider the
    save makes active -- not the one still on disk."""
    from my_app.routes import chat_routes
    asked = []
    monkeypatch.setattr(chat_routes, "list_chat_models",
                        lambda: ([{"id": "local/qwen3.5:9b", "service": "local"}], False, {"m": 1}))
    monkeypatch.setattr(chat_routes, "_cloud_routes",
                        lambda matrix, active=None: asked.append(active) or (["openrouter"], WORLD["routes"]))
    world = sr._model_world(active="openrouter")
    assert asked == ["openrouter"]
    assert world["local"] == ["qwen3.5:9b"]
    assert sr.resolve_role_model("glm-5.3", world) == "openrouter/z-ai/glm-5.3"
