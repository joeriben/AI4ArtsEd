"""A perspective may say how its result is carried into English.

A result that lives in a register -- a way of speaking, not a set of words --
is plain prose again once a translator is asked for neither register in
particular. The perspective says on its own config which register the English
side gets, Stage 3 reads it there, and every run that says nothing keeps the
translator it has always had -- to the byte.

No perspective carries a wording today: Slang and Word Game were the two that
did, and both were taken off the platform on 06.09.2026. The slot stays, and so
does the test, on a config written here.
"""

import asyncio
from pathlib import Path

import pytest

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"

from schemas.engine.chunk_builder import ChunkBuilder
from schemas.engine.config_loader import ConfigLoader
from schemas.engine.stage_orchestrator import (
    _get_translation_cache_entry,
    _update_translation_cache,
    translation_context,
    translation_instruction_for,
)

WITHOUT_WORDING = "mad_world"

# What a perspective would say about its own register. Written here since no
# preset carries one; the mechanism reads meta, not a name.
WORDING = (
    "The source is written in German youth slang. Say it in the British youth "
    "slang of urban UK as it is really spoken. The whole answer is English."
)
TEXT = "Da steht ein Haus mitten in der Pampa."

# The translator's prompt as it stood before a perspective could add to it. A
# run that brings no wording must still produce exactly this.
TRANSLATOR_PROMPT_AS_IT_STANDS = (
    "You are a precise German-to-English translator for AI image generation prompts.\n\n"
    "TASK: Translate the German text below into English. Preserve the meaning and "
    "artistic intent exactly.\n\n"
    "RULES:\n"
    "1. If input contains German words (ein, eine, der, die, das, steht, liegt, zeigt, "
    "etc.) → TRANSLATE TO ENGLISH\n"
    "2. If input is already in English → return unchanged\n"
    "3. Preserve the descriptive style and structure\n"
    "4. Output ONLY the translation, no explanations\n"
    "5. Never add or remove information\n\n"
    "German text:\n" + TEXT + "\n\n"
    "English translation:"
)


@pytest.fixture(scope="module")
def loader():
    cl = ConfigLoader()
    cl.initialize(SCHEMAS)
    return cl


@pytest.fixture
def with_wording(loader):
    """A perspective that says how its result is carried into English."""
    from dataclasses import replace
    base = loader.get_config(WITHOUT_WORDING)
    meta = dict(getattr(base, 'meta', None) or {})
    meta["translation_instruction"] = WORDING
    return replace(base, meta=meta)


def _translator_prompt(custom_placeholders):
    builder = ChunkBuilder(SCHEMAS)
    cl = ConfigLoader()
    cl.initialize(SCHEMAS)
    request = builder.build_chunk(
        "translate",
        cl.get_config("pre_output/translation_en"),
        {"input_text": TEXT, "custom_placeholders": custom_placeholders},
    )
    return request["prompt"]


def test_the_perspective_carries_its_own_wording(with_wording):
    instruction = translation_instruction_for(with_wording)
    assert instruction, "a perspective says how its result is carried over"
    assert "British youth slang" in instruction


def test_a_perspective_that_says_nothing_answers_nothing(loader):
    assert translation_instruction_for(loader.get_config(WITHOUT_WORDING)) is None
    assert translation_instruction_for(None) is None


def test_a_kept_perspective_keeps_the_wording_it_was_forked_from(with_wording):
    """A kept perspective has no config file; it carries the meta it inherited.

    The resolver therefore takes the resolved config, never the name: a name
    like custom:<id> answers nothing in the loader, and the register would fall
    away for exactly the runs that inherited it.
    """
    from dataclasses import replace
    kept = replace(with_wording, name="custom:somebody-kept-this",
                   context="Ihre eigene Fassung des Metaprompts.")
    # Gegen den WERT, nicht gegen die andere Rueckgabe: eine Aufloesung ueber den
    # Namen antwortet auf beiden Seiten None, und ein Vergleich zweier Nichtse
    # haelt genau dann, wenn die Formulierung fuer alle verloren ist.
    assert translation_instruction_for(with_wording) == WORDING
    assert translation_instruction_for(kept) == WORDING


def test_without_a_wording_the_translator_prompt_is_the_one_it_has_always_been():
    """The slot costs nothing where nobody fills it -- to the byte."""
    assert _translator_prompt({}) == TRANSLATOR_PROMPT_AS_IT_STANDS


def test_with_a_wording_it_stands_in_the_translator_prompt(with_wording):
    instruction = translation_instruction_for(with_wording)
    context = translation_context(TEXT, instruction)
    prompt = _translator_prompt(context.custom_placeholders)
    assert "British youth slang" in prompt
    assert prompt.count(TEXT) == 1, "the text to translate stands once"
    assert prompt.index("British youth slang") < prompt.index("German text:"), (
        "the wording belongs to the rules, ahead of the text it rules on")
    assert "6." not in prompt, (
        "the wording is labelled, not numbered: a chunk that grows a rule 6 of "
        "its own would otherwise carry two")


def test_no_wording_leaves_the_translator_prompt_alone():
    for wording in (None, "   "):
        context = translation_context(TEXT, wording)
        assert "TRANSLATION_INSTRUCTION" not in context.custom_placeholders
        assert _translator_prompt(context.custom_placeholders) == TRANSLATOR_PROMPT_AS_IT_STANDS


def test_a_translation_looks_nothing_up():
    """The translator is asked its own prompt, once, and nothing else.

    Without the opt-out the executor appended the Wikipedia research offer; the
    model answered with lookup markers, and every lookup ran the whole
    translation again, up to three times -- with GLM 5.3 91 to 429 s
    (22.-26.09.2026). A marker the model writes anyway is reduced to its term,
    not followed.
    """
    from schemas.engine import pipeline_executor as PE
    from schemas.engine.config_loader import config_loader
    config_loader.initialize(SCHEMAS)
    asked = []

    async def model(request):
        asked.append(request.prompt)
        return PE.BackendResponse(
            success=True, metadata={},
            content='There is a house in the middle of the <wiki lang="de">Pampa</wiki>.')

    executor = PE.PipelineExecutor(SCHEMAS)
    executor.backend_router.process_request = model
    config = config_loader.get_config("pre_output/translation_en")
    step = PE.PipelineStep(step_id="translate", chunk_name=config.chunks[0])
    # Stage 3 calls execute_pipeline without a level, so the executor's default
    # of kids is what a real translation runs under.
    out = asyncio.run(executor._execute_single_step(
        step, translation_context(TEXT), resolved_config=config, safety_level="kids"))

    assert asked == [TRANSLATOR_PROMPT_AS_IT_STANDS]
    assert out == "There is a house in the middle of the Pampa."


class _Executor:
    """Stands in for the executor and keeps the context each translation brings."""

    def __init__(self):
        self.calls = []

    async def execute_pipeline(self, config_name, text, context_override=None, **kwargs):
        self.calls.append((config_name, context_override))

        class Result:
            success = True
            final_output = "There is a house in the middle of nowhere."
            steps = []
        return Result()


def _looked_nothing_up(executor):
    assert executor.calls, "the translation ran"
    for config_name, context in executor.calls:
        assert config_name == "pre_output/translation_en"
        assert context is not None, "a translation without its context runs with research on"
        assert context.custom_placeholders.get("_SKIP_WIKIPEDIA") is True


def test_stage3_translates_without_looking_anything_up():
    from schemas.engine.stage_orchestrator import execute_stage3_safety
    executor = _Executor()
    # research with a forced translation translates and runs no check, so
    # nothing but the translation is exercised
    asyncio.run(execute_stage3_safety(TEXT, "research", "image", executor,
                                      force_translation=True))
    _looked_nothing_up(executor)


def test_the_encoder_halves_are_translated_without_looking_anything_up():
    from my_app.routes.schema_pipeline_routes import _translate_encoder_text
    executor = _Executor()
    asyncio.run(_translate_encoder_text(TEXT, "caption", executor))
    _looked_nothing_up(executor)


def test_speech_translates_without_looking_anything_up(monkeypatch):
    from schemas.engine import pipeline_executor as PE
    from my_app.routes.speech_routes import _translate_to_english
    executor = _Executor()
    monkeypatch.setattr(PE, "executor", executor)
    asyncio.run(_translate_to_english(TEXT))
    _looked_nothing_up(executor)


def test_a_cached_translation_is_not_handed_to_a_run_of_another_wording():
    """Two runs on one device, one of them with a register of its own."""
    device = "a device that ran both"
    _update_translation_cache(device, TEXT, "plain prose", "")
    entry = _get_translation_cache_entry(device)
    assert entry["instruction"] == "", "what it was made under is stored with it"
    assert entry["translated"] == "plain prose"

    _update_translation_cache(device, TEXT, "bare slang", "say it in slang")
    entry = _get_translation_cache_entry(device)
    assert entry["instruction"] == "say it in slang"
    assert entry["translated"] == "bare slang"

def test_no_perspective_writes_at_the_translator_itself(loader):
    """A perspective used to append a line addressed to the translator.

    That line had no effect -- the result came back as plain English anyway --
    and it stood in the text a student reads. It is gone; this keeps it gone,
    across every perspective rather than the one it stood in.
    """
    gesehen = set()
    for name in loader.list_configs():
        context = getattr(loader.get_config(name), 'context', None)
        fassungen = context.values() if isinstance(context, dict) else (
            [context] if isinstance(context, str) else [])
        for text in fassungen:
            gesehen.add(name)
            assert "Translator-LLM" not in text, name
            assert "DO NOT TRANSLATE" not in text, name

    # Gegen die Dateien auf der Platte, nicht gegen eine Zahl: eine Schleife, die
    # Perspektiven uebergeht, wird sonst still gruen. Perspektiven ohne Text
    # zaehlen als gesehen, sobald der Loader sie kennt.
    dateien = {p.stem for p in (SCHEMAS / "configs" / "interception").glob("*.json")}
    ohne_text = {n for n in dateien
                 if not getattr(loader.get_config(n), 'context', None)}
    assert dateien - ohne_text <= gesehen, (
        "diese Perspektiven wurden uebergangen: %s" % sorted(dateien - ohne_text - gesehen))
