"""
Tests that every voice this platform answers with knows what speaks here.

Why it exists: an answer said "am liebsten wuerde ich mit Ihrer Idee anfangen".
Two things are wrong with that sentence and only one of them is the pronoun.
It attributes a wish — and wanting is a property of someone, while what answers
is distributed across separate models on separate machines and is not one
intelligence. The plural is therefore not a house style but a true description,
which is also why it can be given as the reason when someone asks why the
platform talks that way.

Three prompts already carried a version of the ban on simulated feeling, each
in its own words, and Resona carried none — which is where the wish appeared.
SELF_REFERENCE_BLOCK states it once, from the ground up, and reaches every
branch through the single composition gate.

What is enforced (the enforcement, never the wording of a draft):
  - every voice this platform speaks with carries the block,
  - the block stops at the three experimental arms, whose system prompt is the
    user's own material or a deliberately bare baseline — writing into those
    would falsify the instrument,
  - it is stated once per prompt, never restated per branch,
  - no voice carries a name for itself, in the prompt or in the handbook it
    reads back through lookup_reference.

Run: python3 -m pytest devserver/tests/test_platform_self_reference.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.routes.chat_routes import (
    AI_PERSONA_SYSTEM_PROMPT,
    SELF_REFERENCE_BLOCK,
    _SELF_REFERENCE_EXEMPT_MODES,
    _build_resona_modules_context,
    build_system_prompt,
)

# Names the chat used to answer to. A name is one more way of claiming a single
# someone, so no voice carries one for itself any more. They may still appear as
# labels of PLACES — the modes registry names the pages a group can go to — which
# is why the check strips that note before looking.
RETIRED_NAMES = ("Trashy", "Persona")

HEADING = SELF_REFERENCE_BLOCK.splitlines()[0]

# Every branch of the composition gate that is this platform speaking.
VOICES = {
    "general": None,
    "persona": {"persona_mode": True},
    "resona/workshop": {"resona_mode": True, "resona_situation": "workshop",
                        "device_id": "t"},
    "resona/consulting": {"resona_mode": True, "resona_situation": "consulting",
                          "device_id": "t"},
    "resona/nachklapp": {"resona_mode": True, "resona_situation": "nachklapp",
                         "device_id": "t"},
    # Five compare voices stood here until 2026-08-25, when the agent in the
    # column beside each comparison was removed in favour of Help — the same
    # move Representation Engineering made a day earlier.
    "session": {"media_type": "image", "config_name": "sd35_large"},
    # Explaining an experiment result. The reader is 13, which is exactly why
    # this one has to say what speaks here. Representation Engineering had a
    # second entry here until 2026-08-24, when its interpreting agent was
    # removed in favour of Help.
    "interpret/compare": {"interpretation_mode": "compare"},
}

# The instruments. Their system prompt is the object of study, not a voice.
ARMS = {
    "system_prompt_compare": {"system_prompt_compare_mode": True,
                              "custom_system_prompt": "Answer in one word."},
    "system_prompt_compare/empty": {"system_prompt_compare_mode": True,
                                    "custom_system_prompt": ""},
    "llm_model_compare": {"llm_model_compare_mode": True,
                          "custom_system_prompt": "Be terse."},
    "temperature_compare": {"temperature_compare_mode": True},
}


@pytest.mark.parametrize("name", sorted(VOICES))
def test_every_platform_voice_carries_the_block(name):
    prompt = build_system_prompt(context=VOICES[name], language="de")
    assert SELF_REFERENCE_BLOCK in prompt, (
        f"The {name} voice answers without knowing what speaks here. Every "
        "branch composes through build_system_prompt for exactly this reason: "
        "the block is appended once, so a branch added later cannot miss it. "
        "If this branch must be exempt, put it in _SELF_REFERENCE_EXEMPT_MODES "
        "with the reason, rather than letting it fall through silently."
    )


@pytest.mark.parametrize("name", sorted(ARMS))
def test_the_experimental_arms_stay_untouched(name):
    prompt = build_system_prompt(context=ARMS[name], language="de")
    assert SELF_REFERENCE_BLOCK not in prompt, (
        f"The {name} arm carries the platform's own block. That arm's system "
        "prompt is what is being studied — the user's own text, or a bare "
        "baseline held constant so one variable shows. Writing several hundred "
        "words into it makes the comparison measure something else."
    )


def test_the_exempt_modes_are_named_not_guessed():
    assert set(_SELF_REFERENCE_EXEMPT_MODES) == {
        "system_prompt_compare_mode",
        "llm_model_compare_mode",
        "temperature_compare_mode",
    }, (
        "The exemption list changed. It is the one place where a voice is "
        "allowed to answer without stating what speaks here, so a addition "
        "belongs in a commit that says why."
    )


@pytest.mark.parametrize("name", sorted(VOICES))
def test_the_block_is_stated_once(name):
    prompt = build_system_prompt(context=VOICES[name], language="de")
    assert prompt.count(HEADING) == 1, (
        f"The {name} prompt states the block {prompt.count(HEADING)} times. A "
        "second copy in a branch is how a shared rule drifts: the copies stop "
        "matching and the branch quietly wins. It is composed once, at the gate."
    )


@pytest.mark.parametrize("name", sorted(VOICES))
def test_no_voice_carries_a_name_for_itself(name):
    prompt = build_system_prompt(context=VOICES[name], language="de")
    # The modes note names pages, not selves; a page label is not a self-name.
    modes = _build_resona_modules_context()
    if modes and modes in prompt:
        prompt = prompt.replace(modes, " ")
    found = [n for n in RETIRED_NAMES if n in prompt]
    assert not found, (
        f"The {name} voice still carries {found}. A name is answered to, and "
        "what answers here is distributed across processes — there is no one to "
        "hold it. Removing it from the prompt is not enough on its own: the "
        "handbook is read back through lookup_reference, so a name left standing "
        "there comes home as the chat's own name in the next answer."
    )


def test_the_persona_prompt_does_not_command_a_self_introduction():
    for phrase in ("introduce yourself as", "state your name"):
        assert phrase not in AI_PERSONA_SYSTEM_PROMPT, (
            f"The persona prompt still commands {phrase!r}. That instruction is "
            "what produced a named self in the opening line, ahead of anything "
            "the block downstream could say about it."
        )


def test_unknown_experiment_type_raises_instead_of_falling_back():
    """An unknown experiment type used to fall back to the bias prompt, which
    would explain a representation-engineering run with bias instructions — a
    confident wrong explanation, delivered to a 13-year-old. It must fail."""
    with pytest.raises(KeyError):
        build_system_prompt({"interpretation_mode": "no-such-experiment"})
