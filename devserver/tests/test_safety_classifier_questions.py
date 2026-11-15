"""The classifier's questions, read as text, without a model.

my_app/services/safety_classifier.py holds what the safety chain asks: one
instruct per level and one question per medium. What the model answers cannot
be shown without it; what is asked can:

  * each checked level has a question for each medium its checks ask about;
    adult has none for a picture or a video, because adult checks neither;
  * the video question is the picture question about a video, and goes to
    the video reader in the classifier's form, with the system line the
    classifier is sent;
  * kids, youth and adult name no age;
  * the symbols and the rule on Nazi perpetrators and Nazi crimes stand in the
    instruct of each of them, and each says how its lists apply to a text;
  * every question is one yes/no question;
  * the symbol question follows level and medium, and only adult's carries the
    exception for a historical, scientific or artistic context;
  * a level asks its own question and then the question of every less strict
    checked level, so that it refuses whatever a less strict level refuses, by
    construction and not by the wording of its instruct; the symbol questions
    follow the same order;
  * the code question has one place for the constructs the list found;
  * an address counts with its house number.

Run: python3 -m pytest devserver/tests/test_safety_classifier_questions.py -q
"""

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import safety_classifier as sc

WORDED = ("kids", "youth", "adult")
CONTEXT = "historical, scientific or artistic context"
AGE = re.compile(r"\bages?\b|\baged\b|\d+\s*(?:-|\u2013|to)\s*\d+|years? old|year-old",
                 re.IGNORECASE)


@pytest.mark.parametrize("level, media", [
    ("kids", {"prompt", "image", "video", "text"}),
    ("youth", {"prompt", "image", "video", "text"}),
    ("adult", {"prompt", "text"}),
])
def test_each_checked_level_has_its_questions(level, media):
    assert sc.LEVEL_INSTRUCTS[level].strip()
    assert set(sc.LEVEL_QUERIES[level]) == media


def test_open_is_no_level_with_questions():
    """Gone on 2026-11-01. A value that still carries it is asked as a level
    nobody knows: the child's question."""
    assert "open" not in sc.LEVEL_INSTRUCTS
    assert "open" not in sc.LEVEL_QUERIES
    assert sc.policy_for_level("open", "text") == (
        sc.LEVEL_INSTRUCTS["kids"], sc.LEVEL_QUERIES["kids"]["text"])


def test_research_is_asked_nothing():
    assert "research" not in sc.LEVEL_INSTRUCTS
    assert "research" not in sc.LEVEL_QUERIES


@pytest.mark.parametrize("level", WORDED)
def test_no_age_is_named(level):
    for text in (sc.LEVEL_INSTRUCTS[level], *sc.LEVEL_QUERIES[level].values()):
        assert not AGE.search(text), AGE.search(text).group(0)


@pytest.mark.parametrize("level", WORDED)
def test_symbols_and_the_rule_on_nazi_crimes_stand_in_every_level(level):
    instruct = sc.LEVEL_INSTRUCTS[level]
    assert "Nazi perpetrators or Nazi crimes" in instruct
    assert "hate symbol" in instruct or "swastika" in instruct


@pytest.mark.parametrize("level", WORDED)
def test_every_instruct_says_how_its_lists_apply_to_a_text(level):
    assert "For a text, apply" in sc.LEVEL_INSTRUCTS[level]


def _questions():
    for level, queries in sc.LEVEL_QUERIES.items():
        for medium, query in queries.items():
            yield f"{level}/{medium}", query
    for name in ("SYMBOL_POLICY", "SYMBOL_TEXT_POLICY", "ADULT_SYMBOL_POLICY",
                 "ADULT_SYMBOL_TEXT_POLICY", "NAME_POLICY", "CODE_POLICY"):
        yield name, getattr(sc, name)[1]


@pytest.mark.parametrize("name, query", list(_questions()))
def test_every_question_is_one_yes_no_question(name, query):
    assert query.split()[0] in ("Is", "Does"), name
    assert query.endswith("?") and query.count("?") == 1, name


@pytest.mark.parametrize("level, medium, policy", [
    ("adult", "prompt", "ADULT_SYMBOL_POLICY"),
    ("adult", "text", "ADULT_SYMBOL_TEXT_POLICY"),
    (" Adult ", "text", "ADULT_SYMBOL_TEXT_POLICY"),
    ("kids", "prompt", "SYMBOL_POLICY"),
    ("kids", "text", "SYMBOL_TEXT_POLICY"),
    ("youth", "prompt", "SYMBOL_POLICY"),
    ("youth", "text", "SYMBOL_TEXT_POLICY"),
    ("open", "prompt", "SYMBOL_POLICY"),
    ("banana", "prompt", "SYMBOL_POLICY"),
])
def test_the_symbol_question_follows_level_and_medium(level, medium, policy):
    assert sc.symbol_policy_for(level, medium) == getattr(sc, policy)


def test_only_adult_has_the_exception_for_a_context():
    for instruct, query in (sc.ADULT_SYMBOL_POLICY, sc.ADULT_SYMBOL_TEXT_POLICY):
        assert CONTEXT in instruct and CONTEXT in query
    for instruct, query in (sc.SYMBOL_POLICY, sc.SYMBOL_TEXT_POLICY):
        assert "context" not in instruct + query
    assert CONTEXT in sc.LEVEL_QUERIES["adult"]["prompt"]
    assert CONTEXT in sc.LEVEL_QUERIES["adult"]["text"]


def test_the_code_question_has_one_place_for_what_the_list_found():
    query = sc.CODE_POLICY[1]
    assert query.count("{patterns}") == 1
    assert "{" not in query.replace("{patterns}", "")


def test_an_address_counts_with_its_house_number():
    assert "house number" in sc.NAME_POLICY[1]


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_the_video_question_is_the_picture_question_about_a_video(level):
    queries = sc.LEVEL_QUERIES[level]
    assert queries["video"] == queries["image"].replace("image", "video")


def test_a_video_is_asked_in_the_classifier_form():
    system, prompt = sc.video_question(sc.policy_for_level("kids", "video"))
    assert system == sc.CLASSIFIER_SYSTEM
    assert prompt == (f"<Instruct>: {sc.LEVEL_INSTRUCTS['kids']}\n\n"
                      f"<Query>: {sc.LEVEL_QUERIES['kids']['video']}\n\n"
                      "<Document>: The document is the video below.")


def test_the_system_line_is_the_one_the_classifier_is_sent():
    """A copy of the GPU service's, so the two are compared here."""
    source = (Path(__file__).resolve().parents[2]
              / "gpu_service" / "services" / "llm_child_backend.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    sent = [ast.literal_eval(node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "CLASSIFIER_SYSTEM"
                    for t in node.targets)]
    assert sent == [sc.CLASSIFIER_SYSTEM]


def test_the_question_for_a_level_and_a_medium():
    kids_picture = (sc.LEVEL_INSTRUCTS["kids"], sc.LEVEL_QUERIES["kids"]["image"])
    assert sc.policy_for_level("youth", "video") == \
        (sc.LEVEL_INSTRUCTS["youth"], sc.LEVEL_QUERIES["youth"]["video"])
    assert sc.policy_for_level("youth", "text") == \
        (sc.LEVEL_INSTRUCTS["youth"], sc.LEVEL_QUERIES["youth"]["text"])
    assert sc.policy_for_level("adult") == \
        (sc.LEVEL_INSTRUCTS["adult"], sc.LEVEL_QUERIES["adult"]["prompt"])
    assert sc.policy_for_level("banana") == \
        (sc.LEVEL_INSTRUCTS["kids"], sc.LEVEL_QUERIES["kids"]["prompt"])
    assert sc.policy_for_level("kids", "sound") == kids_picture
    assert sc.policy_for_level("adult", "image") == kids_picture, \
        "adult checks no picture; asked about one, it is asked the strictest question"


# ── The chain ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level, medium, chain", [
    ("kids", "prompt", ["kids", "youth", "adult"]),
    ("kids", "text", ["kids", "youth", "adult"]),
    ("kids", "image", ["kids", "youth"]),
    ("kids", "video", ["kids", "youth"]),
    ("youth", "prompt", ["youth", "adult"]),
    ("youth", "text", ["youth", "adult"]),
    ("youth", "image", ["youth"]),
    ("youth", "video", ["youth"]),
    ("adult", "prompt", ["adult"]),
    ("adult", "text", ["adult"]),
    ("adult", "image", []),
    ("adult", "video", []),
    ("open", "text", ["kids", "youth", "adult"]),
    ("banana", "prompt", ["kids", "youth", "adult"]),
    (" Kids ", "image", ["kids", "youth"]),
])
def test_a_level_asks_its_own_question_and_every_less_strict_levels(level, medium, chain):
    """On 2026-11-07 kids let a prompt pass ("88" and "HH" on a wall) that
    youth refused, with the sentence on number codes standing in both instructs
    word for word. The order of the levels holds by construction since."""
    asked = sc.policies_for_level(level, medium)
    assert [name for name, _ in asked] == chain
    for name, policy in asked:
        assert policy == (sc.LEVEL_INSTRUCTS[name], sc.LEVEL_QUERIES[name][medium])


def test_a_stricter_level_asks_every_question_a_looser_one_asks():
    from my_app.services.safety_level_resolver import SAFETY_LEVELS_STRICTEST_FIRST
    levels = [name for name in SAFETY_LEVELS_STRICTEST_FIRST if name in sc.LEVEL_INSTRUCTS]
    assert levels == ["kids", "youth", "adult"]
    for medium in ("prompt", "image", "video", "text"):
        for i, stricter in enumerate(levels):
            for looser in levels[i + 1:]:
                if medium in sc.LEVEL_QUERIES[stricter]:
                    assert set(sc.policies_for_level(looser, medium)) <= \
                        set(sc.policies_for_level(stricter, medium)), (stricter, looser, medium)


def test_research_is_in_no_chain():
    for level in ("kids", "youth", "adult"):
        for medium in ("prompt", "image", "video", "text"):
            assert "research" not in [name for name, _ in sc.policies_for_level(level, medium)]


@pytest.mark.parametrize("level, medium, chain", [
    ("kids", "prompt", [("kids", "SYMBOL_POLICY"), ("adult", "ADULT_SYMBOL_POLICY")]),
    ("kids", "text", [("kids", "SYMBOL_TEXT_POLICY"), ("adult", "ADULT_SYMBOL_TEXT_POLICY")]),
    ("youth", "prompt", [("youth", "SYMBOL_POLICY"), ("adult", "ADULT_SYMBOL_POLICY")]),
    ("youth", "text", [("youth", "SYMBOL_TEXT_POLICY"), ("adult", "ADULT_SYMBOL_TEXT_POLICY")]),
    ("adult", "prompt", [("adult", "ADULT_SYMBOL_POLICY")]),
    ("adult", "text", [("adult", "ADULT_SYMBOL_TEXT_POLICY")]),
    ("banana", "text", [("kids", "SYMBOL_TEXT_POLICY"), ("adult", "ADULT_SYMBOL_TEXT_POLICY")]),
])
def test_the_symbol_questions_follow_the_same_order(level, medium, chain):
    assert sc.symbol_policies_for(level, medium) == [(name, getattr(sc, policy))
                                                     for name, policy in chain]

