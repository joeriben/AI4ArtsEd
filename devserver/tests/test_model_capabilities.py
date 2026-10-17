"""
Tests for the measured model capabilities (my_app/services/model_capabilities).

The platform used to decide from the provider prefix whether a model takes an image.
The guess was wrong for mammouth/glm-5.2 -- the model behind CHAT_HELPER_MODEL --
whose refusal is a final 404, so every image turn died with a 500. Settings now
measures it, and the same machinery measures whether a model reaches for a tool,
because Resona and the idea development mode are handed tool definitions and simply
never act when the model cannot use them.

What is held here is not that a measurement is accurate -- that needs a live model --
but that only defensible verdicts are ever written, and that the transport floors
stand above every measurement. A wrong record is worse than no record: a false
"cannot" on image routes every image turn through the local description for good.

Run: python3 -m pytest devserver/tests/test_model_capabilities.py -q
"""
import base64
import io
import json
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.services import model_capabilities as mc
from my_app.utils import vision_support


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    path = tmp_path / "model_capabilities.json"
    monkeypatch.setattr(mc, "STORE_FILE", path)
    return path


# ---------------------------------------------------------------------------
# Keys and transport
# ---------------------------------------------------------------------------

def test_local_prefix_is_not_part_of_the_key():
    """user_settings.json holds IMAGE_ANALYSIS_MODEL as 'local/qwen3-vl:4b', and
    a role may name the same model bare. One fact, one key."""
    assert mc.canonical("local/qwen3-vl:4b") == mc.canonical("qwen3-vl:4b")
    assert mc.canonical("  Local/Qwen3-VL:4b ") == "qwen3-vl:4b"


def test_provider_prefix_is_part_of_the_key():
    assert mc.canonical("mammouth/glm-5.2") != mc.canonical("openrouter/glm-5.2")


def test_transport_split_matches_the_runtime():
    assert mc.is_local("qwen3-vl:2b") is True         # bare name -> GPU service
    assert mc.is_local("local/qwen3-vl:4b") is True
    assert mc.is_local("mammouth/glm-5.2") is False
    assert mc.is_local("openrouter/mistralai/mistral-large-latest") is False


# ---------------------------------------------------------------------------
# The floors: read from the code, never measured, never overridable
# ---------------------------------------------------------------------------

def test_ionos_cannot_be_handed_an_image():
    assert mc.get_recorded("ionos/openai/gpt-oss-120b", "image") is False


def test_a_local_model_cannot_be_handed_tools():
    """LLMClient.chat accepts `tools` and ignores it, in its own docstring."""
    assert mc.get_recorded("local/qwen3-vl:4b", "tools") is False
    assert mc.get_recorded("qwen3:1.7b", "tools") is False


def test_a_local_model_without_a_vision_tower_is_a_floor():
    """config/local_llm_weights.json says which local checkpoint carries a
    vision tower. A probe would build the model (minutes, other built
    models dropped for it) to be refused the picture afterwards."""
    from my_app.services import local_llm_weights as w
    blind = next(a for a, e in w.models().items() if not e.get("vision"))
    seeing = next(a for a, e in w.models().items() if e.get("vision"))
    assert mc.get_recorded(f"local/{blind}", "image") is False
    assert mc.get_recorded(blind, "image") is False
    assert mc.floor_for(seeing, "image") is None
    assert mc.floor_for("local/nothing:1b", "image") is None


def test_a_floor_costs_no_call(monkeypatch):
    def dispatch(*a, **k):
        raise AssertionError("a floor must not reach a provider")

    monkeypatch.setattr("my_app.routes.chat_routes._dispatch_single_model", dispatch)
    for model, capability in (("ionos/x", "image"), ("local/qwen3-vl:4b", "tools")):
        result = mc.probe(model, capability)
        assert result["verdict"] == "cannot"
        assert result["recorded"] is False


def test_no_measurement_can_lift_a_floor():
    """A recorded 'can' on IONOS would turn a visible failure into a fluent answer
    about a picture nobody looked at."""
    mc.record("ionos/openai/gpt-oss-120b", "image", True, "hand-edited nonsense")
    assert mc.get_recorded("ionos/openai/gpt-oss-120b", "image") is False
    assert vision_support.is_vision_capable("ionos/openai/gpt-oss-120b") is False


# ---------------------------------------------------------------------------
# The test image
# ---------------------------------------------------------------------------

def test_test_image_is_a_readable_jpeg_inside_the_envelope():
    b64, digits = mc.build_test_image()
    assert re.fullmatch(r"\d{5}", digits)
    img = Image.open(io.BytesIO(base64.b64decode(b64)))
    assert img.format == "JPEG"
    assert 64 <= max(img.size) <= 768


def test_digits_are_not_constant():
    assert len({mc.build_test_image()[1] for _ in range(12)}) > 1


def test_digit_extraction_tolerates_how_small_models_answer():
    """Measured replies from qwen3-vl:2b: '022', '.70', '`14927`'."""
    assert mc._digits_of("`14927`") == "14927"
    assert mc._digits_of(".70") == "70"
    assert mc._digits_of("") == ""


# ---------------------------------------------------------------------------
# image: what may be written down
# ---------------------------------------------------------------------------

def _teach_digits(monkeypatch):
    real = mc.build_test_image

    def build():
        b64, digits = real()
        mc._LAST_DIGITS_FOR_TEST = digits
        return b64, digits

    monkeypatch.setattr(mc, "build_test_image", build)


def test_a_local_model_is_never_recorded_as_blind(monkeypatch):
    """The local client returns None for a model that takes no image, one that is not
    installed and a VRAM shortage alike. None of that can mean 'cannot'."""
    class DeadBackend:
        def chat(self, **kwargs):
            return None

    monkeypatch.setattr("my_app.services.llm_backend.get_llm_backend", lambda: DeadBackend())
    result = mc.probe("local/qwen3-vl:4b", "image")
    assert result["verdict"] == "unclear"
    assert result["recorded"] is False
    assert mc.get_recorded("local/qwen3-vl:4b", "image") is None


def test_a_local_model_that_reads_the_digits_is_recorded(monkeypatch):
    captured = {}

    class SeeingBackend:
        def chat(self, **kwargs):
            captured.update(kwargs)
            return {"content": "the number is " + mc._LAST_DIGITS_FOR_TEST}

    _teach_digits(monkeypatch)
    monkeypatch.setattr("my_app.services.llm_backend.get_llm_backend", lambda: SeeingBackend())

    assert mc.probe("local/qwen3-vl:4b", "image")["verdict"] == "can"
    assert mc.get_recorded("qwen3-vl:4b", "image") is True   # either spelling finds it
    assert captured["images"], "the probe must actually send an image"


def test_the_answer_may_arrive_in_the_thinking_field(monkeypatch):
    class ThinkingBackend:
        def chat(self, **kwargs):
            return {"content": "", "thinking": mc._LAST_DIGITS_FOR_TEST}

    _teach_digits(monkeypatch)
    monkeypatch.setattr("my_app.services.llm_backend.get_llm_backend", lambda: ThinkingBackend())
    assert mc.probe("local/qwen3-vl:4b", "image")["verdict"] == "can"


def test_only_a_quoted_refusal_is_recorded_as_cannot(monkeypatch):
    """A status code plus the word 'image' also matches 'Invalid image data', which is
    an encoding fault on a model that sees perfectly well."""
    def refusing(msg):
        def dispatch(*a, **k):
            raise Exception(msg)
        return dispatch

    monkeypatch.setattr("my_app.routes.chat_routes._dispatch_single_model",
                        refusing('API Error: 404\n{"message":"No endpoints found that support image input"}'))
    assert mc.probe("mammouth/glm-5.2", "image")["verdict"] == "cannot"
    assert mc.get_recorded("mammouth/glm-5.2", "image") is False

    monkeypatch.setattr("my_app.routes.chat_routes._dispatch_single_model",
                        refusing('API Error: 400\n{"message":"Invalid image data"}'))
    result = mc.probe("mammouth/some-other-model", "image")
    assert result["verdict"] == "unclear"
    assert mc.get_recorded("mammouth/some-other-model", "image") is None


def test_an_unreachable_provider_records_nothing(monkeypatch):
    def dispatch(*a, **k):
        raise Exception('API Error: 429\n{"message":"rate limited"}')

    monkeypatch.setattr("my_app.routes.chat_routes._dispatch_single_model", dispatch)
    assert mc.probe("mammouth/claude-opus-5", "image")["verdict"] == "unreachable"
    assert mc.get_recorded("mammouth/claude-opus-5", "image") is None


def test_a_fluent_wrong_answer_records_nothing(monkeypatch):
    monkeypatch.setattr("my_app.routes.chat_routes._dispatch_single_model",
                        lambda *a, **k: {"content": "I see a picture of a cat."})
    assert mc.probe("mammouth/claude-opus-5", "image")["verdict"] == "unclear"
    assert mc.get_recorded("mammouth/claude-opus-5", "image") is None


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------

def test_a_model_that_calls_the_offered_tool_is_recorded(monkeypatch):
    seen = {}

    def dispatch(model, messages, **kwargs):
        seen.update(kwargs)
        return {"content": "", "tool_calls": [
            {"function": {"name": mc.TOOL_NAME, "arguments": '{"value": 7}'}}]}

    monkeypatch.setattr("my_app.routes.chat_routes._dispatch_single_model", dispatch)
    assert mc.probe("mammouth/claude-opus-5", "tools")["verdict"] == "can"
    assert mc.get_recorded("mammouth/claude-opus-5", "tools") is True
    assert seen["tools"], "the probe must actually offer a tool"
    assert seen["image_b64"] is None, "the tools probe must not also send an image"


def test_prose_instead_of_a_tool_call_records_nothing(monkeypatch):
    monkeypatch.setattr("my_app.routes.chat_routes._dispatch_single_model",
                        lambda *a, **k: {"content": "Sure, I would call report_number(7)."})
    result = mc.probe("mammouth/claude-opus-5", "tools")
    assert result["verdict"] == "unclear"
    assert mc.get_recorded("mammouth/claude-opus-5", "tools") is None


def test_the_two_capabilities_do_not_overwrite_each_other(monkeypatch):
    mc.record("mammouth/x", "image", True, "read the test image")
    mc.record("mammouth/x", "tools", False, "provider refused")
    assert mc.get_recorded("mammouth/x", "image") is True
    assert mc.get_recorded("mammouth/x", "tools") is False


def test_an_unknown_capability_is_refused():
    with pytest.raises(ValueError):
        mc.probe("mammouth/x", "telepathy")


# ---------------------------------------------------------------------------
# What the runtime does with it
# ---------------------------------------------------------------------------

def test_the_measurement_is_the_only_source():
    """No model name appears in the decision any more. An unmeasured model is not
    handed a picture, whatever it is called and whoever hosts it."""
    assert vision_support.is_vision_capable("someprovider/some-model") is False
    mc.record("someprovider/some-model", "image", True, "read the test image")
    assert vision_support.is_vision_capable("someprovider/some-model") is True


def test_forgetting_returns_to_not_knowing():
    mc.record("someprovider/some-model", "image", True, "read the test image")
    assert vision_support.is_vision_capable("someprovider/some-model") is True
    assert mc.forget("someprovider/some-model", "image") is True
    assert vision_support.is_vision_capable("someprovider/some-model") is False
    assert mc.forget("someprovider/some-model", "image") is False


def test_an_unreadable_store_does_not_take_the_platform_down(store):
    store.write_text("{ this is not json", encoding="utf-8")
    assert mc.load_store() == {}
    assert vision_support.is_vision_capable("someprovider/some-model") is False


def test_the_store_is_written_as_readable_json(store):
    mc.record("mammouth/glm-5.2", "image", False, "No endpoints found that support image input")
    entry = json.loads(store.read_text(encoding="utf-8"))["mammouth/glm-5.2"]
    assert entry["model_string"] == "mammouth/glm-5.2"
    assert entry["image"]["can"] is False
    assert entry["image"]["checked"].startswith("20")
    assert "No endpoints" in entry["image"]["evidence"]


# ---------------------------------------------------------------------------
# The overview the Settings table renders
# ---------------------------------------------------------------------------

def test_every_role_that_is_handed_an_image_or_a_tool_is_listed():
    """Two claims about the code, both load-bearing for the table: the three chat
    roles reach is_vision_capable, and only two of them are handed tools."""
    assert set(mc.ROLE_REQUIREMENTS) == {
        "CHAT_HELPER_MODEL", "PERSONA_MODEL", "RESONA_MODEL",
        "IMAGE_ANALYSIS_MODEL", "CODING_MODEL",
    }
    assert mc.ROLE_REQUIREMENTS["PERSONA_MODEL"] == ("image", "thinking", "tools")
    assert mc.ROLE_REQUIREMENTS["IMAGE_ANALYSIS_MODEL"] == ("image",)
    # Every requirement must be part of the vocabulary the table renders.
    for requires in mc.ROLE_REQUIREMENTS.values():
        assert set(requires) <= set(mc.CAPABILITIES)
    assert set(mc.MEASURABLE) <= set(mc.CAPABILITIES)


def test_the_overview_speaks_only_about_the_configured_model():
    """A settings row is about the model in its field. What a request reaches when that
    model fails is decided at request time out of the model matrix -- by provider, by
    credential, by the data-protection gate. There is no named fallback to print, and a
    row that printed one would be asserting a fact the platform does not hold."""
    overview = mc.role_overview()
    for role, entry in overview.items():
        assert "chain" not in entry, f"{role} still carries a chain into the interface"
        assert set(entry) == {"requires", "measurable", "model", "local",
                              "known", "fixed", "evidence", "checked"}
        for field in ("known", "fixed", "evidence", "checked"):
            assert set(entry[field]) <= set(entry["measurable"]), field


def test_a_verdict_travels_with_its_evidence():
    """A red slot without a sentence and a date behind it is a judgement the operator
    cannot check and cannot argue with."""
    overview = mc.role_overview()
    for role, entry in overview.items():
        for capability, verdict in entry["known"].items():
            if verdict is None or entry["fixed"].get(capability):
                continue
            assert entry["evidence"].get(capability), f"{role}/{capability} has no evidence"
            assert entry["checked"].get(capability), f"{role}/{capability} has no date"


def test_every_role_appears_even_without_a_model():
    overview = mc.role_overview()
    assert set(overview) == set(mc.ROLE_REQUIREMENTS)
    for entry in overview.values():
        assert isinstance(entry["model"], str)


def test_a_role_with_no_model_configured_does_not_crash(monkeypatch):
    monkeypatch.setattr("my_app.routes.chat_routes.get_user_setting", lambda k, default=None: "")
    monkeypatch.setattr("config.CHAT_HELPER_MODEL", "", raising=False)
    overview = mc.role_overview()
    assert overview["CHAT_HELPER_MODEL"]["model"] == ""
    assert overview["CHAT_HELPER_MODEL"]["known"] == {}


def test_a_requirement_without_a_probe_cannot_be_measured():
    """Stating a requirement and testing one are different things; the module refuses
    to produce a verdict where there is no test."""
    for capability in mc.CAPABILITIES:
        if capability in mc.MEASURABLE:
            continue
        with pytest.raises(ValueError):
            mc.probe("someprovider/some-model", capability)
