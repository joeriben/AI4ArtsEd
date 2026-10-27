"""A `*` standing on its own in the text an interception is handed keeps its place.

The Default Census puts a reference at every such star of its base prompt, and
the perspective ring on that field writes the intercepted text back into it.
The rule that keeps the stars (instruction_selector.PLACEHOLDER_CLAUSE) is
written after the text only where the text carries such a star, and only on an
interception: every other run reads what it read before.

Run: python3 -m pytest devserver/tests/test_placeholder_clause.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from schemas.engine.chunk_builder import ChunkBuilder
from schemas.engine.config_loader import ConfigLoader
from schemas.engine.instruction_selector import get_placeholder_clause

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
LINE = "a * person in typical clothing in a typical * environment"


@pytest.fixture(scope="module")
def loader():
    cl = ConfigLoader()
    cl.initialize(SCHEMAS)
    return cl


def _prompt(loader, chunk, config, context):
    return ChunkBuilder(SCHEMAS).build_chunk(chunk, loader.get_config(config), context)["prompt"]


@pytest.mark.parametrize("text", [
    "* first meal of the day", "a * wedding", "typical * work", "a person feeling *", LINE,
])
def test_a_star_standing_on_its_own_is_a_placeholder(text):
    assert get_placeholder_clause(text, "Prompt").strip().startswith("PLACEHOLDER: each * in the Prompt")


@pytest.mark.parametrize("text", [
    "a person in typical clothing", "a *very* small house", "3*4 windows", "**bold**",
    "*waves*", "house*", None,
])
def test_a_star_touching_a_word_or_a_star_is_none(text):
    assert get_placeholder_clause(text, "Prompt") == ""


def test_an_interception_with_a_star_carries_the_rule_after_the_prompt(loader):
    prompt = _prompt(loader, "manipulate", "bauhaus", {"input_text": LINE})
    rule = get_placeholder_clause(LINE, "Prompt").strip()
    assert rule in prompt
    assert prompt.index("Prompt:\n" + LINE) < prompt.index(rule)


def test_an_interception_without_a_placeholder_does_not(loader):
    for text in ("a person in typical clothing", "a *very* small house"):
        assert "PLACEHOLDER:" not in _prompt(loader, "manipulate", "bauhaus", {"input_text": text})


def test_a_chained_link_reads_the_star_in_the_text_it_is_handed(loader):
    """The link writes PREVIOUS_OUTPUT under "Text:", not the run input."""
    prompt = _prompt(loader, "manipulate_recursive", "stillepost",
                     {"input_text": "a person", "previous_output": "ein * Mensch"})
    assert get_placeholder_clause("*", "Text").strip() in prompt
    prompt = _prompt(loader, "manipulate_recursive", "stillepost",
                     {"input_text": "a * person", "previous_output": "ein Mensch"})
    assert "PLACEHOLDER:" not in prompt


@pytest.mark.parametrize("chunk, config", [
    ("translate", "pre_output/translation_en"),
    ("manipulate", "pre_interception/safety_llamaguard"),
])
def test_no_step_but_the_interception_gets_it(loader, chunk, config):
    assert "PLACEHOLDER:" not in _prompt(loader, chunk, config, {"input_text": LINE})
