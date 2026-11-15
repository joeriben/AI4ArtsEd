"""The canvas offers the platform's chat-model list (canvas_routes, 2026-09-12).

Until then canvas_routes._load_cloud_models_from_matrix read every preset's
role cells for itself, key or no key. Now it is the list the chat-model
pickers are filled from (useChatModels), in the canvas's own shape: id, name,
register, provider, dsgvo -- since 2026-10-27 the chosen provider's models,
as the Latent Lab offers them.
"""
import sys
from pathlib import Path

DEVSERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEVSERVER))

from my_app.routes import canvas_routes, chat_routes  # noqa: E402
from my_app.services.llm_providers import provider  # noqa: E402

MATRIX = {"llm_presets": {
    "mammouth": {"label": "Mammouth AI", "DSGVO_CONFORMITY": True, "DSGVO_NOTE": "recorded"},
    "openai": {"label": "OpenAI", "DSGVO_CONFORMITY": False, "DSGVO_NOTE": "recorded"},
}}


GLM = {"id": "mammouth/glm-5.3", "label": "glm-5.3", "register": "glm-5.3",
       "available": True, "installable": False}
GPT = {"id": "openai/gpt-5.6-terra", "label": "gpt-5.6-terra", "register": "gpt-5.6-terra",
       "available": True, "installable": False}


def _lists(asked):
    """Every keyed provider's list, and the chosen one's alone -- not known
    where no provider was named, as chat_routes answers it."""
    def listed(matrix, active=None, only_active=False):
        asked.append((active, only_active))
        if not only_active:
            return [GLM, GPT]
        if active is None:
            return None
        return [m for m in (GLM, GPT) if m["id"].startswith(active + "/")]
    return listed


def test_the_canvas_list_is_the_chosen_providers_in_the_canvas_shape(monkeypatch):
    asked = []
    monkeypatch.setattr(chat_routes, "_load_llm_matrix", lambda: MATRIX)
    monkeypatch.setattr(chat_routes, "_chosen_provider", lambda: "mammouth")
    monkeypatch.setattr(chat_routes, "_cloud_chat_models_from_matrix", _lists(asked))
    # The name carries the provider table's label, not the preset's.
    mammouth = provider("mammouth")["label"]
    assert canvas_routes._load_cloud_models_from_matrix() == [
        {"id": "mammouth/glm-5.3", "name": f"glm-5.3 ({mammouth})", "register": "glm-5.3",
         "provider": "mammouth", "dsgvo": True},
    ]
    assert asked == [("mammouth", True)]


def test_a_choice_that_cannot_be_read_offers_every_keyed_provider(monkeypatch):
    asked = []
    monkeypatch.setattr(chat_routes, "_load_llm_matrix", lambda: MATRIX)
    monkeypatch.setattr(chat_routes, "_chosen_provider", lambda: None)
    monkeypatch.setattr(chat_routes, "_cloud_chat_models_from_matrix", _lists(asked))
    mammouth, openai = provider("mammouth")["label"], provider("openai")["label"]
    assert canvas_routes._load_cloud_models_from_matrix() == [
        {"id": "mammouth/glm-5.3", "name": f"glm-5.3 ({mammouth})", "register": "glm-5.3",
         "provider": "mammouth", "dsgvo": True},
        {"id": "openai/gpt-5.6-terra", "name": f"gpt-5.6-terra ({openai})", "register": "gpt-5.6-terra",
         "provider": "openai", "dsgvo": False},
    ]
    assert asked == [(None, True), (None, False)]
