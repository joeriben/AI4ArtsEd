"""
Tests for the image path through the chat fallback chain.

Written after 2026-08-12, when a probe of the live providers showed that
CHAT_HELPER_MODEL (mammouth/glm-5.2) is not a vision model at all. Mammouth
answered a generated image with

    HTTP 404 "No endpoints found that support image input"

which `is_retriable_llm_error` does not match — so there was no fall-through
either: every ChatOverlay / surrealizer image analysis died with a 500. The
capability rule had simply assumed that any cloud prefix means "sees images".

Two rules are held here:
  1. Capability comes from a measurement, never from the model's name or prefix.
  2. An image turn never falls through to a candidate that cannot see it — the
     gate used to check only the FIRST candidate while the image was handed to
     every one the chain reached (ionos drops it silently and says nothing).

Run: python3 -m pytest devserver/tests/test_vision_fallback_chain.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import model_capabilities
from my_app.utils.vision_support import is_vision_capable


@pytest.fixture
def fresh_model():
    """A model string no test has recorded anything for. Not a real model name: the
    platform must hold no knowledge about any particular model, so a test that pins
    behaviour to one would be pinning the very thing that was removed."""
    return "someprovider/some-model"


@pytest.fixture(autouse=True)
def empty_capability_store(tmp_path, monkeypatch):
    """is_vision_capable reads what Settings recorded, so on a box where an operator
    has run the check that file exists -- without this the same test would pass or
    fail depending on it."""
    monkeypatch.setattr(model_capabilities, "STORE_FILE", tmp_path / "empty.json")


# ---------------------------------------------------------------------------
# 1. Capability: evidence beats the prefix guess
# ---------------------------------------------------------------------------

def test_nothing_measured_means_no_image_is_handed_over(fresh_model):
    """The whole class of failure this replaces: a model nobody measured used to be
    assumed capable because of its prefix. Now it is simply not handed the picture --
    the turn runs on the local description instead of dying at the provider."""
    assert is_vision_capable(fresh_model) is False
    assert is_vision_capable("") is False


def test_a_measurement_decides_in_both_directions(fresh_model):
    model_capabilities.record(fresh_model, "image", True, "read the test image")
    assert is_vision_capable(fresh_model) is True
    model_capabilities.record(fresh_model, "image", False, "provider refused")
    assert is_vision_capable(fresh_model) is False


def test_the_lookup_does_not_care_how_the_model_is_spelled(fresh_model):
    model_capabilities.record(fresh_model, "image", True, "read the test image")
    assert is_vision_capable(fresh_model.upper()) is True


def test_the_ionos_floor_stands_without_any_measurement():
    """The table says the IONOS connection takes no picture ("image_input":
    false in config/llm_providers.json), and the reader builds the request
    without one."""
    assert is_vision_capable("ionos/openai/gpt-oss-120b") is False


# ---------------------------------------------------------------------------
# 2. The chain — no candidate is dropped; a blind one is handed an account instead
#    (call_chat_helper, the loop over the candidate chain)

CHAIN = ["someprovider/model-a", "someprovider/model-b",
         "someprovider/model-c", "ionos/some-model"]


def _sees(model):
    model_capabilities.record(model, "image", True, "read the test image")


def _substitution_plan(chain, has_image):
    """Which candidate gets the picture and which gets an account of it.

    Mirrors the rule in call_chat_helper: the chain is never shortened, and a candidate
    that cannot take the picture is called without it and with the account in the
    messages instead.
    """
    if not has_image:
        return [(c, "as is") for c in chain]
    return [(c, "image" if is_vision_capable(c) else "account") for c in chain]


def test_no_candidate_is_dropped_from_an_image_turn():
    """An image turn used to lose every candidate that could not see, which left it with
    no fall-back at all. An answer written from the account beats no answer."""
    _sees("someprovider/model-b")
    plan = _substitution_plan(CHAIN, has_image=True)
    assert [c for c, _ in plan] == CHAIN


def test_only_a_seeing_candidate_is_handed_the_picture():
    _sees("someprovider/model-b")
    _sees("someprovider/model-c")
    plan = dict(_substitution_plan(CHAIN, has_image=True))
    assert plan["someprovider/model-b"] == "image"
    assert plan["someprovider/model-c"] == "image"
    assert plan["ionos/some-model"] == "account"      # the connection drops images
    assert plan["someprovider/model-a"] == "account"  # never measured, so never handed one


def test_a_chain_nobody_measured_still_runs():
    plan = dict(_substitution_plan(CHAIN, has_image=True))
    assert set(plan.values()) == {"account"}


def test_a_text_turn_is_untouched():
    assert [c for c, how in _substitution_plan(CHAIN, has_image=False)] == CHAIN


def test_the_account_replaces_the_picture_without_disturbing_the_original():
    """The substitution returns a copy: a blind candidate must not leave the account
    behind in the messages for the next candidate, which may be able to see."""
    from my_app.utils import vision_support as vs

    messages = [{"role": "system", "content": "sys"},
                {"role": "user", "content": "what is in this picture?"}]
    original = [dict(m) for m in messages]
    vs.describe_image_for_fallback = lambda _b64: "a red apple on a white table"

    out = vs.messages_with_description(messages, "not-a-real-image")
    assert messages == original, "the caller's messages were modified"
    assert "a red apple on a white table" in out[-1]["content"]
    assert "did NOT see this image" in out[-1]["content"]
    assert out[-1]["content"].endswith("what is in this picture?")
    assert out[0] == {"role": "system", "content": "sys"}
