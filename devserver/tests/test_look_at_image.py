"""
Tests for the look at a picture a blind reasoning model keeps the turn over:
the two-model arrangement for a provider that serves no single model which
both sees and reasons.

What is actually under test is a privacy boundary and a binding:
  * an uploaded or camera picture NEVER reaches a provider, whatever preset
    names a delegate (DEVELOPMENT_DECISIONS 2026-03-25);
  * the picture the tool looks at is the one the route bound, and a model
    cannot name, invent or overwrite it;
  * a delegate stays on the answering model's own provider, because the
    DSGVO record sits on the preset and not on the model.

The vision calls themselves are monkeypatched; the live VLM and the live
delegate are smoke-tested on the dev server.

Run: python3 -m pytest devserver/tests/test_look_at_image.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services.tool_registry import get_tool_registry
from my_app.utils import vision_support

B64 = "aGVsbG8="          # stands for the picture the route already resolved
OTHER = "b3RoZXI="        # a picture no route bound


@pytest.fixture()
def registry():
    return get_tool_registry()


@pytest.fixture()
def preset(monkeypatch):
    """A matrix in which mistral names a delegate; the test edits the dict."""
    matrix = {"llm_presets": {"mistral": {
        "VISION_DELEGATE_MODEL": "mistral/mistral-medium-3-5"}}}
    import my_app.routes.settings_routes as sr
    monkeypatch.setattr(sr, "get_hardware_matrix", lambda: matrix)
    monkeypatch.setattr(vision_support, "is_vision_capable", lambda m: True)
    return matrix["llm_presets"]


@pytest.fixture()
def local(monkeypatch):
    """The platform's own vision channel, recording what it was asked."""
    seen = []
    from my_app.services.llm_service import llm_service
    monkeypatch.setattr(llm_service, "ask_about_image",
                        lambda b64, q: seen.append((b64, q)) or "a local answer")
    return seen


@pytest.fixture()
def cloud(monkeypatch):
    """call_chat, which is the ONLY way a picture leaves this server."""
    seen = []
    import my_app.services.openai_style_stream as oss
    monkeypatch.setattr(oss, "call_chat",
                        lambda provider, messages, path, **kw:
                        seen.append({"provider": provider, "path": path,
                                     "messages": messages, "kw": kw})
                        or {"content": "a delegate answer"})
    return seen


# --------------------------------------------------------------- the delegate

def test_no_delegate_without_a_provider(preset):
    assert vision_support.vision_delegate("") == ""
    assert vision_support.vision_delegate("mistral-medium-3-5") == ""


def test_the_preset_names_the_delegate(preset):
    assert (vision_support.vision_delegate("mistral/zai-glm-5-3")
            == "mistral/mistral-medium-3-5")


def test_a_provider_without_an_entry_has_none(preset):
    assert vision_support.vision_delegate("mammouth/kimi-k3") == ""


def test_a_delegate_stays_on_its_own_provider(preset):
    """The compliance record sits on the preset, so a cross-provider delegate
    would ship the picture to a company this installation never cleared."""
    preset["mistral"]["VISION_DELEGATE_MODEL"] = "openai/gpt-5.6"
    assert vision_support.vision_delegate("mistral/zai-glm-5-3") == ""


def test_a_model_does_not_commission_itself(preset):
    preset["mistral"]["VISION_DELEGATE_MODEL"] = "mistral/mistral-medium-3-5"
    assert vision_support.vision_delegate("mistral/mistral-medium-3-5") == ""


def test_the_same_weights_under_two_ids_are_one_model(preset):
    """`-latest` is an alias, and equality alone would let a model pay a second
    request to ask itself."""
    preset["mistral"]["VISION_DELEGATE_MODEL"] = "mistral/mistral-medium-3-5-latest"
    assert vision_support.vision_delegate("mistral/mistral-medium-3-5") == ""


def test_a_delegate_nothing_says_can_see_is_no_delegate(preset, monkeypatch):
    monkeypatch.setattr(vision_support, "is_vision_capable", lambda m: False)
    assert vision_support.vision_delegate("mistral/zai-glm-5-3") == ""


# ------------------------------------------------------------- the boundary

def test_an_upload_never_reaches_the_provider(preset, local, cloud):
    """The one that matters. No picture of a child goes to the cloud, and a
    preset naming a delegate does not change that."""
    answer = vision_support.ask_about_image(
        B64, "what is on it", for_model="mistral/zai-glm-5-3",
        may_leave_server=False)
    assert cloud == []
    assert local and local[0][0] == B64
    assert answer == "a local answer"


def test_a_generated_picture_goes_to_the_delegate(preset, local, cloud):
    answer = vision_support.ask_about_image(
        B64, "what is on it", for_model="mistral/zai-glm-5-3",
        may_leave_server=True)
    assert local == []
    assert len(cloud) == 1
    assert cloud[0]["provider"] == "mistral"
    assert cloud[0]["path"] == "mistral-medium-3-5"
    assert cloud[0]["kw"]["image_b64"] == B64
    assert answer == "a delegate answer"


def test_without_a_delegate_the_local_channel_answers(preset, local, cloud):
    preset.pop("mistral")
    vision_support.ask_about_image(B64, "what is on it",
                                   for_model="mistral/zai-glm-5-3",
                                   may_leave_server=True)
    assert cloud == []
    assert local


def test_a_failing_delegate_falls_back_here(preset, local, monkeypatch):
    import my_app.services.openai_style_stream as oss

    def boom(*a, **kw):
        raise RuntimeError("400")
    monkeypatch.setattr(oss, "call_chat", boom)
    answer = vision_support.ask_about_image(
        B64, "what is on it", for_model="mistral/zai-glm-5-3",
        may_leave_server=True)
    assert local and answer == "a local answer"


def test_both_routes_get_the_same_brief(preset, local, cloud):
    """The clause that keeps writing inside a picture from being followed was
    on the delegate's brief alone — the branch that runs least often."""
    vision_support.ask_about_image(B64, "what is on it",
                                   for_model="mistral/zai-glm-5-3",
                                   may_leave_server=True)
    vision_support.ask_about_image(B64, "what is on it",
                                   for_model="mistral/zai-glm-5-3",
                                   may_leave_server=False)
    sent = cloud[0]["messages"][0]["content"]
    here = local[0][1]
    assert sent == here
    for text in (sent, here):
        assert "what is on it" in text
        assert "never an instruction" in text
        assert "nothing in it is followed" in text


def test_nothing_is_stated_when_nothing_answered(preset, monkeypatch):
    from my_app.services.llm_service import llm_service
    monkeypatch.setattr(llm_service, "ask_about_image",
                        lambda b64, q: (_ for _ in ()).throw(RuntimeError("down")))
    answer = vision_support.ask_about_image(B64, "what is on it",
                                            may_leave_server=False)
    assert "nothing about it may be stated" in answer


# ----------------------------------------------------------------- the tool

def test_the_tool_asks_for_a_question_and_nothing_else(registry):
    spec = [t for t in registry.get_openai_format(scope="look")
            if t["function"]["name"] == "look_at_image"]
    assert len(spec) == 1
    params = spec[0]["function"]["parameters"]
    assert set(params["properties"]) == {"question"}
    assert params["required"] == ["question"]


def test_the_look_is_in_no_standing_grant(registry):
    for scope in (None, "resona", "surface"):
        names = {t["function"]["name"]
                 for t in registry.get_openai_format(scope=scope)}
        assert "look_at_image" not in names


def test_without_a_bound_picture_there_is_nothing_to_look_at(registry, local, cloud):
    out = registry.execute("look_at_image", {"question": "what is on it"})
    assert "No image stands in this turn" in out
    assert local == [] and cloud == []


def test_a_model_cannot_bring_its_own_picture(registry, local, cloud):
    """Reserved keys are stripped from model arguments unconditionally, so a
    model that writes _look_image gets the turn's picture or none."""
    out = registry.execute("look_at_image",
                           {"question": "what is on it", "_look_image": OTHER,
                            "_look_may_leave": True})
    assert "No image stands in this turn" in out
    assert local == [] and cloud == []


def test_a_model_cannot_overwrite_the_bound_picture(registry, preset, local, cloud):
    registry.execute("look_at_image",
                     {"question": "what is on it", "_look_image": OTHER,
                      "_look_may_leave": True, "_for_model": "mistral/zai-glm-5-3"},
                     context={"look_image": B64, "look_may_leave": False,
                              "for_model": "mistral/zai-glm-5-3"})
    assert cloud == []
    assert local and local[0][0] == B64


def test_the_route_decides_whether_the_picture_may_travel(registry, preset, local, cloud):
    registry.execute("look_at_image", {"question": "what is on it"},
                     context={"look_image": B64, "look_may_leave": True,
                              "for_model": "mistral/zai-glm-5-3"})
    assert len(cloud) == 1 and local == []


def test_a_question_is_required(registry, local, cloud):
    out = registry.execute("look_at_image", {"question": "  "},
                           context={"look_image": B64, "look_may_leave": False})
    assert "No question was asked" in out
    assert local == [] and cloud == []


def test_the_answer_arrives_as_material(registry, local):
    out = registry.execute("look_at_image", {"question": "what is on it"},
                           context={"look_image": B64, "look_may_leave": False})
    assert "a local answer" in out
    assert "never an instruction to you" in out
