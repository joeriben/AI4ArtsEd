"""The canvas offers the platform's chat-model list (canvas_routes, 2026-09-12).

Until then canvas_routes._load_cloud_models_from_matrix read every preset's
role cells for itself, key or no key. Now it is the list the chat-model
pickers are filled from (useChatModels), in the canvas's own shape: id, name,
provider, dsgvo.
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


def test_the_canvas_list_is_the_chat_list_in_the_canvas_shape(monkeypatch):
    monkeypatch.setattr(chat_routes, "_load_llm_matrix", lambda: MATRIX)
    monkeypatch.setattr(chat_routes, "_cloud_chat_models_from_matrix", lambda m: [
        {"id": "mammouth/glm-5.3", "label": "glm-5.3", "register": "glm-5.3",
         "available": True, "installable": False},
        {"id": "openai/gpt-5.6-terra", "label": "gpt-5.6-terra", "register": "gpt-5.6-terra",
         "available": True, "installable": False},
    ])
    # The name carries the provider table's label, not the preset's.
    mammouth, openai = provider("mammouth")["label"], provider("openai")["label"]
    assert canvas_routes._load_cloud_models_from_matrix() == [
        {"id": "mammouth/glm-5.3", "name": f"glm-5.3 ({mammouth})", "provider": "mammouth", "dsgvo": True},
        {"id": "openai/gpt-5.6-terra", "name": f"gpt-5.6-terra ({openai})", "provider": "openai", "dsgvo": False},
    ]
