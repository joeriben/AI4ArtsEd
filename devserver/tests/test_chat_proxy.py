#!/usr/bin/env python3
"""POST /api/chat/proxy: the DevServer as the LLM proxy for the ComfyUI nodes.

The nodes in comfyui_nodes/ai4artsed_comfyui/ send their LLM calls here so
that keys, the provider table and the fallback the settings page regulates
stay in one place. What this file holds the route to:

  - "platform/<ROLE>" goes to call_chat_helper as a ROLE, which is the path
    the settings' fallback chain (build_model_candidate_chain) sits on;
  - a model id goes as model_override -- exactly that model, no fallback, the
    platform's rule for a model picked by hand -- and only when this
    installation offers it (list_chat_models, the pickers' own list);
  - no output cap is passed (rule 5);
  - a failed call answers 502 with its cause, an unknown role or model 400;
  - a caller inside ComfyUI's executor ("runs_inside_comfyui") gets a local
    model as the instruction to run it there ("run_in_caller"), since the
    DevServer runs local models BY ComfyUI, one prompt at a time (stage 3 of
    the move to ComfyUI).

Run: pytest devserver/tests/test_chat_proxy.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import chat_routes


@pytest.fixture()
def client(monkeypatch):
    calls = []

    def fake_helper(messages, **kwargs):
        calls.append({"messages": messages, **kwargs})
        return {"content": "answer", "model_used": kwargs.get("model_override") or "resolved/model"}

    monkeypatch.setattr(chat_routes, "call_chat_helper", fake_helper)
    monkeypatch.setattr(chat_routes, "list_chat_models",
                        lambda: ([{"id": "openrouter/some/model"}, {"id": "local/some:7b"}], False, {}))
    app = Flask(__name__)
    app.register_blueprint(chat_routes.chat_bp)
    app.calls = calls
    return app.test_client()


MESSAGES = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]


def test_a_role_takes_the_settings_fallback_path(client):
    r = client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/STAGE2_INTERCEPTION_MODEL",
                                             "temperature": 0.7})
    assert r.status_code == 200, r.get_json()
    assert r.get_json() == {"content": "answer", "model_used": "resolved/model"}
    call = client.application.calls[0]
    assert call["role"] == "STAGE2_INTERCEPTION_MODEL"
    assert call["model_override"] is None
    assert call["temperature"] == 0.7
    assert call["messages"] == MESSAGES


def test_a_model_id_runs_exactly_and_only_when_offered(client):
    r = client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "openrouter/some/model"})
    assert r.status_code == 200, r.get_json()
    call = client.application.calls[0]
    assert call["model_override"] == "openrouter/some/model"
    assert call["role"] is None
    assert call["temperature"] is None
    r = client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "openrouter/not/offered"})
    assert r.status_code == 400
    assert "not a model this installation offers" in r.get_json()["error"]
    assert len(client.application.calls) == 1


def test_no_output_cap_is_passed(client):
    client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/CHAT_HELPER_MODEL"})
    assert "max_tokens" not in client.application.calls[0]


def test_an_unknown_role_is_refused(client):
    r = client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/NO_SUCH_MODEL"})
    assert r.status_code == 400
    assert "names no model role" in r.get_json()["error"]
    r = client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/JSON_STORAGE_DIR"})
    assert r.status_code == 400
    assert client.application.calls == []


def test_a_failed_call_carries_its_cause(client, monkeypatch):
    def failing(messages, **kwargs):
        raise RuntimeError("provider answered 429: quota")
    monkeypatch.setattr(chat_routes, "call_chat_helper", failing)
    r = client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/SAFETY_MODEL"})
    assert r.status_code == 502
    assert r.get_json()["error"] == "provider answered 429: quota"


def test_the_image_goes_along(client):
    client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/IMAGE_ANALYSIS_MODEL",
                                         "image_b64": "abc"})
    assert client.application.calls[0]["image_b64"] == "abc"


def test_a_caller_inside_comfyui_runs_a_local_model_itself(client, monkeypatch):
    def helper(messages, **kwargs):
        client.application.calls.append({"messages": messages, **kwargs})
        if kwargs.get("local_in_caller"):
            return {"content": "", "model_used": "local/some:7b",
                    "run_in_caller": {"llm_name": "Some--Model", "messages": messages, "image_b64": None}}
        return {"content": "answer", "model_used": "local/some:7b"}
    monkeypatch.setattr(chat_routes, "call_chat_helper", helper)
    r = client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/SAFETY_MODEL",
                                             "runs_inside_comfyui": True})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["run_in_caller"] == {"llm_name": "Some--Model", "messages": MESSAGES, "image_b64": None}
    assert r.get_json()["model_used"] == "local/some:7b"
    assert client.application.calls[0]["local_in_caller"] is True
    # Without the flag the DevServer runs the model itself, and the answer carries no instruction.
    r = client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/SAFETY_MODEL"})
    assert r.get_json() == {"content": "answer", "model_used": "local/some:7b"}
    assert client.application.calls[1]["local_in_caller"] is False


def test_the_chain_hands_a_local_model_to_a_caller_inside_comfyui(monkeypatch):
    """call_chat_helper itself: a local candidate is not dispatched for such
    a caller but answered as the instruction, with the messages as the chain
    fitted them; a candidate that is not installed ends the chain."""
    from my_app.services import local_llm_weights as w
    alias = next(iter(w.models()))
    dispatched = []
    monkeypatch.setattr(chat_routes, "_dispatch_single_model",
                        lambda *a, **k: dispatched.append(a[0]) or {"content": "x"})
    monkeypatch.setattr(w, "is_installed", lambda model_id: True)
    r = chat_routes.call_chat_helper(MESSAGES, model_override=f"local/{alias}", local_in_caller=True)
    assert dispatched == []
    assert r["run_in_caller"]["llm_name"] == w.dir_name(alias)
    assert r["run_in_caller"]["messages"] == MESSAGES
    assert r["model_used"] == f"local/{alias}"
    monkeypatch.setattr(w, "is_installed", lambda model_id: False)
    with pytest.raises(Exception, match="not an installed local model"):
        chat_routes.call_chat_helper(MESSAGES, model_override=f"local/{alias}", local_in_caller=True)
    # The same call without the flag dispatches as before.
    chat_routes.call_chat_helper(MESSAGES, model_override=f"local/{alias}")
    assert dispatched == [f"local/{alias}"]


def test_a_caller_inside_comfyui_gets_no_description_of_the_picture(monkeypatch):
    """The account of a picture for a model that cannot see it is a call of
    the image reader, and for a caller inside ComfyUI that call would queue
    behind the caller's own prompt. The turn ends with that said, and the
    describer is never called."""
    from my_app.utils import vision_support
    described = []
    monkeypatch.setattr(vision_support, "messages_with_description",
                        lambda messages, image_b64: described.append(image_b64) or messages)
    monkeypatch.setattr(vision_support, "is_vision_capable", lambda model: False)
    with pytest.raises(Exception, match="reads no pictures"):
        chat_routes.call_chat_helper(MESSAGES, model_override="local/blind:1b", image_b64="QUJD",
                                     local_in_caller=True)
    assert described == []
    # Outside ComfyUI the account is made, as before.
    monkeypatch.setattr(chat_routes, "_dispatch_single_model", lambda *a, **k: {"content": "x"})
    chat_routes.call_chat_helper(MESSAGES, model_override="local/blind:1b", image_b64="QUJD")
    assert described == ["QUJD"]


def test_a_local_call_hands_the_picture_beside_the_messages(monkeypatch):
    """The node places the picture for the model's chat template and
    announces the room its vision tower needs; a picture written into a
    message (the cloud dialects' image_url part) is refused there. So the
    two local callers pass `images` and leave the messages as they are."""
    from my_app.services import llm_backend
    seen = []

    class Backend:
        def chat(self, **kwargs):
            seen.append(kwargs)
            return {"content": "read", "thinking": None, "tool_calls": None, "finish_reason": "stop"}

        def chat_stream(self, **kwargs):
            seen.append(kwargs)
            yield ("token", "read")
            yield ("done", "stop")

    monkeypatch.setattr(llm_backend, "get_llm_backend", lambda: Backend())
    chat_routes._call_local_llm_chat(MESSAGES, "local/seer:4b", 0.7, None, image_b64="QUJD")
    list(chat_routes._stream_local_llm(MESSAGES, "local/seer:4b", 0.7, None, image_b64="QUJD"))
    assert len(seen) == 2
    for call in seen:
        assert call["images"] == ["QUJD"]
        assert call["messages"] == MESSAGES
        assert all(isinstance(m["content"], str) for m in call["messages"])


def test_the_request_shape_is_checked(client):
    assert client.post("/api/chat/proxy", json={"model": "platform/CHAT_HELPER_MODEL"}).status_code == 400
    assert client.post("/api/chat/proxy", json={"messages": [], "model": "platform/CHAT_HELPER_MODEL"}).status_code == 400
    assert client.post("/api/chat/proxy", json={"messages": MESSAGES}).status_code == 400
    assert client.post("/api/chat/proxy", json={"messages": MESSAGES, "model": "platform/CHAT_HELPER_MODEL",
                                                "temperature": "warm"}).status_code == 400
    assert client.application.calls == []
