#!/usr/bin/env python3
"""The chats are told the safety level, with the measures of the level.

What the chats write leaves unchecked since 2026-11-08. Every chat's system
message closes instead with an instruction that names the safety level and
carries the measure the check applied to the chats' answers until then: the
classifier's instruct for the level, without the sentence that makes the
classifier a moderator. The instructs of the less strict levels, which the
check asks as well, are left out: they restrict nothing the level's own does
not, and their tolerances contradict it. It stands last, after the page state, the page's
entries and the listing of the surface, so that nothing a page or a person put
into the system role stands after it. A level nobody resolved, or one the list
does not know, counts as kids; research gets no instruction, as it gets no
check. The comparisons of the Latent Lab get none: their answer is checked.
The youth-protection clauses the persona and Resona carried on kids and youth
are gone.

The level is resolved in the two views, on the request thread: the streamed
turn runs on a worker of its own, where the resolver answers with the strictest
level whatever the request's level is.

Run:  python3 -m pytest devserver/tests/test_chat_youth_protection.py -q
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import chat_routes
from my_app.routes.chat_routes import build_system_prompt, level_instruction
from my_app.services.safety_classifier import LEVEL_INSTRUCTS

MARK = "SAFETY LEVEL:"
CHECKED = ["kids", "youth", "adult"]
READERS = {"kids": "children", "youth": "young people", "adult": "adults"}
CHATS = {
    "persona": {"persona_mode": True},
    "resona": {"resona_mode": True, "device_id": "test-level-instruction"},
    "help": None,
    "session": {"media_type": "image"},
    "interpretation": {
        "interpretation_mode": next(iter(chat_routes.INTERPRETATION_SYSTEM_PROMPTS)),
    },
}
COMPARISONS = [
    {"system_prompt_compare_mode": True, "custom_system_prompt": "Antworte knapp."},
    {"llm_model_compare_mode": True},
    {"temperature_compare_mode": True},
]


@pytest.fixture
def sent(monkeypatch, chat_checks_pass):
    """The system message each turn hands the chat model."""
    seen = []

    def helper(**kwargs):
        seen.append(kwargs["messages"][0]["content"])
        yield ("result", {"content": "Gut.", "thinking": None, "tool_calls": None,
                          "model_used": "stand-in/one"})

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    monkeypatch.setattr(chat_routes, "_brought_captions", lambda items, level: {})
    return seen


def system_message(sent, context, level, **request):
    data = {"message": "Hallo", **request}
    if context is not None:
        data["context"] = context
    with Flask(__name__).test_request_context("/api/chat", json={}):
        events = list(chat_routes._chat_events(data, level))
    assert events[-1]["type"] == "done", events[-1]
    return sent[-1]


@pytest.mark.parametrize("chat", list(CHATS))
@pytest.mark.parametrize("level", CHECKED)
def test_every_chat_closes_with_the_instruction_of_its_level(sent, chat, level):
    prompt = system_message(sent, CHATS[chat], level)
    assert prompt.endswith("\n\n" + level_instruction(level))
    assert prompt.count(MARK) == 1
    assert f"the safety level for {READERS[level]}." in prompt


def test_the_instruction_stands_after_what_the_page_put_into_the_system_message(sent):
    prompt = system_message(sent, None, "kids",
                            draft_context="Eingabe: ein Haus am See",
                            surface_media=[{"run_id": "run_123",
                                            "label": "Zeile 1, Spalte 2"}])
    instruction = level_instruction("kids")
    assert prompt.endswith("\n\n" + instruction)
    head = prompt[: -len(instruction)]
    assert "ein Haus am See" in head
    assert "Zeile 1, Spalte 2" in head


@pytest.mark.parametrize("chat", list(CHATS))
def test_the_composed_prompt_carries_no_instruction_of_its_own(chat):
    assert MARK not in build_system_prompt(CHATS[chat], "de", level="kids")


@pytest.mark.parametrize("level", CHECKED)
def test_the_measure_is_the_classifiers_own_without_its_role(level):
    instruction = level_instruction(level)
    criteria = instruction.split("\n\n")[1]
    assert LEVEL_INSTRUCTS[level].endswith(criteria)
    assert criteria.startswith("Apply a high tolerance" if level == "adult"
                               else "Unsuitable: ")
    assert "moderator" not in instruction
    assert "Judge what the prompt asks" not in instruction


@pytest.mark.parametrize("level, looser", [("kids", "youth"), ("kids", "adult"),
                                           ("youth", "adult")])
def test_no_tolerance_of_a_less_strict_level_is_told(level, looser):
    """The tolerances of the less strict levels contradict the stricter measure."""
    instruction = level_instruction(level)
    tolerance = {"youth": "horror without graphic depiction",
                 "adult": "Apply a high tolerance"}[looser]
    assert tolerance in LEVEL_INSTRUCTS[looser]
    assert tolerance not in instruction


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_the_frame_does_not_lift_the_word_rule(level):
    """The word rule of kids and youth holds "in any context"; the frame says
    nothing that would read as judging the sense over the word."""
    instruction = level_instruction(level)
    frame = instruction.split("\n\n", 1)[0]
    assert "the word nudity" in instruction
    assert "single word" not in frame


@pytest.mark.parametrize("level", [None, "", "open", "a-level-nobody-knows", " KIDS "])
def test_an_unknown_level_is_told_as_kids(level):
    assert level_instruction(level) == level_instruction("kids")


@pytest.mark.parametrize("chat", list(CHATS))
def test_research_is_told_nothing(sent, chat):
    assert level_instruction("research") == ""
    assert MARK not in system_message(sent, CHATS[chat], "research")


@pytest.mark.parametrize("context", COMPARISONS)
@pytest.mark.parametrize("level", ["kids", "adult"])
def test_the_comparisons_are_told_nothing(sent, context, level):
    assert MARK not in system_message(sent, context, level)


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_kids_and_youth_are_told_the_symbols_and_the_scene_rule_of_adult(level):
    """Kids and youth name hate symbols and depictions of Nazi crimes by
    category; the adult measure names the symbols and says when a text depicts
    such a crime. Before 2026-11-14 the result check asked the adult question
    at kids as well."""
    passages = level_instruction(level).split("\n\n")[2]
    for said in ("the Black Sun", "the flags and symbols of ISIS, Al-Qaeda or the PKK",
                 "number codes such as 88, 18 or 28", "the 14 Words"):
        assert said in passages and said in LEVEL_INSTRUCTS["adult"]
    assert ("Depictions of Nazi perpetrators or Nazi crimes at this level include a text "
            "that describes a scene with Nazi perpetrators") in passages
    # Not the adult tolerance, and not its exception for a context.
    assert "historical, scientific or artistic context" not in passages
    assert "reports or explains history" not in passages


def test_adult_is_told_its_own_measure_once():
    instruction = level_instruction("adult")
    assert len(instruction.split("\n\n")) == 2
    assert instruction.count("the Black Sun") == 1


def test_an_adult_instruct_without_the_symbols_fails_loudly(monkeypatch):
    monkeypatch.setitem(LEVEL_INSTRUCTS, "adult", "You are a moderator. Apply a high tolerance.")
    with pytest.raises(RuntimeError):
        level_instruction("kids")


def test_an_instruct_that_changed_its_opening_fails_loudly(monkeypatch):
    monkeypatch.setitem(LEVEL_INSTRUCTS, "youth", "Unsuitable: anything.")
    with pytest.raises(RuntimeError):
        level_instruction("youth")


def test_the_old_clauses_are_gone_and_what_stood_around_them_stays():
    persona = build_system_prompt(CHATS["persona"], "de", level="kids")
    assert ("- This is an art education platform. Educators are present.\n"
            "- The human is a workshop participant") in persona
    resona = build_system_prompt(CHATS["resona"], "de", level="kids")
    assert ("This is an art-education platform, and educators are present.\n"
            "The reply is plain conversational text") in resona
    for prompt in (persona, resona):
        assert "All content must be age-appropriate" not in prompt
        assert "All content is age-appropriate" not in prompt


CASES = re.compile(
    r"\b(abuse[sd]?|abusive|violen(?:ce|t)|threat(?:s|en|ened|ening)?|secre(?:t|ts|cy)"
    r"|danger(?:ous)?|emergenc(?:y|ies)|(?:tele)?phone|hurt(?:s|ing)?|counsell?(?:ing|or)?"
    r"|child protection|death|dead|died|trust(?:s|ed)?|harm(?:s|ed|ing)?|suicid(?:e|al)"
    r"|kill(?:s|ed|ing)?|police|helpline|crisis|afraid|parents?)\b", re.I)


@pytest.mark.parametrize("level", CHECKED)
def test_a_personal_problem_is_referred_to_the_course_leader_and_named_by_no_kind(level):
    """The chats give no psychological help: on a personal problem the reply
    says nothing about it, refers a participant to the course leader and stays
    with the work (project lead, 2026-11-14). Beside the classifier's measure and the
    passages of adult, the instruction lists no cases: all of it is scanned,
    so that a paragraph of cases added anywhere is found."""
    instruction = level_instruction(level)
    frame = instruction.split("\n\n", 1)[0]
    assert "the replies here give no psychological help" in frame
    assert ("the reply says nothing about the problem and does not continue the "
            "conversation about it; it refers a participant to the course leader in "
            "one sentence and answers only on the level of the work done here") in frame
    assert "A request for the work that comes with it is judged by the measure" in frame
    measure = chat_routes._CLASSIFIER_ROLE.sub("", LEVEL_INSTRUCTS[level], count=1)
    rest = instruction.replace(measure, "").replace(chat_routes._adult_passages(level), "")
    assert measure not in rest and len(rest) < len(instruction) - len(measure) + 1
    assert CASES.findall(rest) == []


def test_a_prompt_without_a_level_is_the_strict_one():
    """A caller that names no level gets what kids get. (The persona only:
    Resona's prompt carries the minute it was composed in.)"""
    assert build_system_prompt(CHATS["persona"], "de") == build_system_prompt(
        CHATS["persona"], "de", level="kids")


@pytest.fixture()
def app():
    a = Flask(__name__)
    a.register_blueprint(chat_routes.chat_bp)
    return a


@pytest.mark.parametrize("view, path", [("chat", "/api/chat"),
                                        ("chat_stream", "/api/chat/stream")])
def test_the_view_hands_its_level_to_the_turn(app, monkeypatch, view, path):
    seen = []

    def turn(data, level):
        seen.append(level)
        yield {"type": "done", "reply": "fertig"}

    monkeypatch.setattr(chat_routes, "resolve_safety_level", lambda: "adult")
    monkeypatch.setattr(chat_routes, "_chat_events", turn)
    with app.test_request_context(path, json={"message": "x"}):
        response = getattr(chat_routes, view)()
        if view == "chat_stream":
            for _chunk in response.response:
                pass

    assert seen == ["adult"]
