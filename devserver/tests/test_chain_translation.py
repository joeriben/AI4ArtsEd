#!/usr/bin/env python3
"""The chained translation is a CHAIN: nine model calls, each reading the last.

Between 2026-02-12 and 2026-09-06 this preset made ONE call whose instruction
described the whole chain, and the loop it was moved off had two faults that
made the single call look better: the `manipulate` chunk reads
`{{INPUT_TEXT}}`, which the chunk builder fills with the text Stage 1 checked
on EVERY pass, so nine links translated the same original nine times; and
`{{TARGET_LANGUAGE}}` written inside a config's own context is never resolved,
because placeholder replacement is one pass in dict order and CONTEXT is
substituted after it. The tests below hold the three things that fix costs:

  * the LINK reads the link before it (chunk `manipulate_recursive`),
  * the link is TOLD its language by the chunk template, not by the config text,
  * the link keeps the whole safety chain — the kids/youth prefix AND the
    cultural-respect block, which a custom task instruction would have replaced
    wholesale, on the one preset that runs through eight languages of several
    continents every single time.

Plus the two ends of a chain that does not finish: a link that answers with the
refusal the safety prefix asks for stops the chain and IS the result (it used to
be carried into the next language and paraphrased into prose under a run that
reported success), and a link that answers with nothing fails the run instead of
being handed on as an empty text.

Everything is mocked. No model is called, no network is touched.

Run: python3 -m pytest devserver/tests/test_chain_translation.py -q
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from schemas.engine import pipeline_executor as PE
from schemas.engine.chunk_builder import ChunkBuilder
from schemas.engine.config_loader import config_loader
from schemas.engine.instruction_selector import (
    CULTURAL_RESPECT_PRINCIPLES, INSTRUCTION_TYPES, SAFETY_PREFIXES,
    SAFETY_REFUSAL_SENTENCE, get_instruction,
    STRUCTURAL_TRANSFORMATION,
    CHAIN_LANGUAGE_RULE,
    READING_VOLUME_WORDS,
)

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
CONFIG = "stillepost"
PIPELINE = "text_transformation_recursive"
CHUNK = "manipulate_recursive"

# The block that must read the same in "transformation" and in
# "chain_translation". Held here as a literal on purpose: rewording it in one
# instruction type and not the other fails this test rather than shipping a
# chain that has quietly lost it.
CULTURAL_RESPECT = """CULTURAL RESPECT PRINCIPLES:
- When describing cultural practices, heritages, or non-Western contexts: Use the same neutral, fact-based approach as for Western contexts
- FORBIDDEN: Exoticizing, romanticizing, or mystifying cultural practices
- FORBIDDEN: Orientalist tropes (exotic, mysterious, timeless, ancient wisdom, etc.)
- FORBIDDEN: Homogenizing diverse cultures into aesthetic stereotypes"""


@pytest.fixture(scope="module")
def loader():
    config_loader.initialize(SCHEMAS)
    return config_loader


# --- the instruction -------------------------------------------------------

def test_cultural_respect_is_the_same_text_in_both_instruction_types():
    # Both bodies are composed from CULTURAL_RESPECT_PRINCIPLES; this holds the
    # wording itself, so rewriting the constant is a decision someone makes here
    # too rather than one that slips through.
    assert CULTURAL_RESPECT == CULTURAL_RESPECT_PRINCIPLES
    for name in ("transformation", "chain_translation"):
        assert CULTURAL_RESPECT in INSTRUCTION_TYPES[name]["default"], name


def test_a_self_written_task_instruction_cannot_drop_the_cultural_rule():
    """A kept perspective replaces the instruction type's text whole.

    Anyone logged in may fork a preset and write their own task instruction --
    including a fork of THIS preset, whose pipeline loops, where the loss would
    be paid once per link. The rule is the platform's, so it is put back.
    """
    own = get_instruction("chain_translation",
                          custom_override="Schreib es als Liste von Gerüchen.",
                          safety_level="kids")
    assert CULTURAL_RESPECT_PRINCIPLES in own
    assert own.startswith(SAFETY_PREFIXES["kids"])


def test_the_cultural_rule_is_not_pasted_in_twice():
    carried = "Do it sideways.\n\n" + CULTURAL_RESPECT_PRINCIPLES
    assert get_instruction("transformation", custom_override=carried).count(
        CULTURAL_RESPECT_PRINCIPLES) == 1


def test_chain_link_is_told_to_answer_in_the_target_language():
    chain = INSTRUCTION_TYPES["chain_translation"]["default"]
    assert "ALWAYS reply in the language of the Input." not in chain
    assert "ALWAYS reply in the Target language" in chain


def test_chain_link_is_not_told_it_may_leave_something_out():
    chain = INSTRUCTION_TYPES["chain_translation"]["default"]
    assert "300 words" not in chain
    assert "adds\nnothing and leaves nothing out" in chain


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_safety_prefix_rides_on_the_chain_instruction(level):
    assert get_instruction("chain_translation", safety_level=level).startswith(
        SAFETY_PREFIXES[level]
    )


def test_refusal_sentence_is_the_one_the_prefixes_ask_for():
    for level, prefix in SAFETY_PREFIXES.items():
        assert SAFETY_REFUSAL_SENTENCE in prefix, level


# --- the wiring ------------------------------------------------------------

def test_preset_runs_on_the_looping_pipeline(loader):
    cfg = loader.get_config(CONFIG)
    assert cfg.pipeline_name == PIPELINE
    assert cfg.chunks == [CHUNK]
    assert cfg.parameters["iterations"] > 1
    assert cfg.parameters["use_random_languages"] is True
    # "source" is what makes the last link go back to the language the person
    # wrote in; a fixed code would end every chain in that one language.
    assert cfg.parameters["final_language"] == "source"


def test_pipeline_declares_the_chain_instruction_type(loader):
    assert loader.get_pipeline(PIPELINE).instruction_type == "chain_translation"


def test_chain_chunk_reads_the_previous_link_and_names_the_language():
    template = json.loads((SCHEMAS / "chunks" / f"{CHUNK}.json").read_text())["template"]
    assert "{{PREVIOUS_OUTPUT}}" in template
    assert "{{TARGET_LANGUAGE}}" in template
    assert "{{TASK_INSTRUCTION}}" in template   # the safety prefix rides here
    # The whole point: NOT the run input, which is the same text on every pass.
    assert "{{INPUT_TEXT}}" not in template


# --- the assembled prompt --------------------------------------------------

def _build(loader, safety_level="open"):
    cfg = loader.get_config(CONFIG)
    return ChunkBuilder(SCHEMAS).build_chunk(
        chunk_name=cfg.chunks[0],
        resolved_config=cfg,
        pipeline=loader.get_pipeline(cfg.pipeline_name),
        context={
            "input_text": "Ein Haus am Fluss.",
            "user_input": "Ein Haus am Fluss.",
            "previous_output": "A house by the river.",
            "custom_placeholders": {"TARGET_LANGUAGE": "Japanese",
                                    "TARGET_LANGUAGE_CODE": "ja"},
        },
        safety_level=safety_level,
        context_language="de",
    )["prompt"]


def test_link_prompt_carries_the_previous_link_not_the_run_input(loader):
    prompt = _build(loader)
    assert "A house by the river." in prompt
    assert "Ein Haus am Fluss." not in prompt


def test_link_prompt_names_the_language_in_words(loader):
    prompt = _build(loader)
    assert "Target language: Japanese" in prompt
    assert "{{" not in prompt


def test_link_prompt_carries_no_reading_volume_clause(loader):
    # A translation renders what is there. Nine links each told they may drop
    # material compound the losses.
    #
    # Gegen den KOPF der Klausel, nicht gegen ihren Rumpf: bis 2026-09-07 stand
    # hier "leave something out" -- ein Satz aus dem Rumpf, der am selben Tag neu
    # geschrieben wurde, womit die Zusicherung gruen blieb, ohne noch etwas zu
    # pruefen. "Length: at most" ist die erste Zeile jeder Fassung.
    prompt = _build(loader)
    assert "Length: at most" not in prompt
    for words in READING_VOLUME_WORDS.values():
        assert f"at most {words} words" not in prompt


def test_link_prompt_keeps_the_age_prefix_and_the_cultural_block(loader):
    prompt = _build(loader, safety_level="kids")
    assert SAFETY_PREFIXES["kids"] in prompt
    assert CULTURAL_RESPECT in prompt


# --- the loop --------------------------------------------------------------

def _run_chain(loader, fake_step, context_language="de"):
    cfg = loader.get_config(CONFIG)
    ctx = PE.PipelineContext(input_text="Ein Haus am Fluss.",
                             user_input="Ein Haus am Fluss.")
    steps = [PE.PipelineStep(step_id="s", chunk_name=cfg.chunks[0])]
    original = PE.PipelineExecutor._execute_single_step
    PE.PipelineExecutor._execute_single_step = fake_step
    try:
        return asyncio.run(PE.PipelineExecutor(SCHEMAS)._execute_recursive_pipeline_steps(
            CONFIG, steps, ctx, None, resolved_config=cfg,
            safety_level="open", run_id="t", context_language=context_language,
        ))
    finally:
        PE.PipelineExecutor._execute_single_step = original


async def _echo_link(self, step, context, **kw):
    return context.get_previous_output() + " >" + context.custom_placeholders["TARGET_LANGUAGE_CODE"]


def test_each_link_reads_the_one_before_it(loader):
    result = _run_chain(loader, _echo_link)
    assert result.status is PE.PipelineStatus.COMPLETED
    sequence = result.metadata["language_sequence"]
    assert result.metadata["links_completed"] == len(sequence)
    # One marker per link, in order: the text was carried, not rebuilt.
    assert result.final_output == "Ein Haus am Fluss. " + " ".join(">" + c for c in sequence)


def test_the_chain_comes_back_to_the_language_it_started_in(loader):
    sequence = _run_chain(loader, _echo_link).metadata["language_sequence"]
    assert sequence[-1] == "de"
    # And never passes through it on the way: a link into the language the text
    # is already in changes nothing.
    assert "de" not in sequence[:-1]


def test_without_a_detected_language_the_chain_ends_in_english(loader):
    sequence = _run_chain(loader, _echo_link, context_language=None).metadata["language_sequence"]
    assert sequence[-1] == "en"


def test_a_refusal_ends_the_chain_and_is_the_result(loader):
    seen = {"n": 0}

    async def refusing_link(self, step, context, **kw):
        seen["n"] += 1
        if seen["n"] == 3:
            return SAFETY_REFUSAL_SENTENCE + " Der Text ist dafür nicht geeignet."
        return context.get_previous_output() + " >"

    result = _run_chain(loader, refusing_link)
    assert result.status is PE.PipelineStatus.COMPLETED
    assert result.metadata["safety_refusal_at"] == 3
    assert result.metadata["links_completed"] == 3
    assert result.final_output.startswith(SAFETY_REFUSAL_SENTENCE)


def test_a_link_that_answers_with_nothing_fails_the_run(loader):
    seen = {"n": 0}

    async def empty_link(self, step, context, **kw):
        seen["n"] += 1
        return "" if seen["n"] == 4 else context.get_previous_output() + " >"

    result = _run_chain(loader, empty_link)
    assert result.status is PE.PipelineStatus.FAILED
    assert result.metadata["failed_at"] == 4
    assert result.metadata["links_completed"] == 3
    # The record still says what the chain was going to be.
    assert len(result.metadata["language_sequence"]) == result.metadata["iterations"]


# --- the wire between the two ----------------------------------------------
#
# Everything above builds the prompt the way a test can: it hands the chunk
# builder the pipeline object, the target language, the age level. Production
# did not hand over the pipeline -- `_execute_single_step` left the argument
# out, the builder fell back to "artistic_transformation" for every step of
# every pipeline, and `"instruction_type": "chain_translation"` in the pipeline
# JSON reached nothing. The links were told "ALWAYS reply in the language of
# the Input" while the same prompt named a target language, and the models
# wrote out the contradiction instead of the translation. Twenty green tests
# said nothing about it, because each one supplied by hand exactly the argument
# the run was missing.
#
# So the tests below supply NOTHING. They put a recorder where the chunk
# builder sits and let the real loop run into it: what the loop passes is what
# the models get, and every hand-set value above is here read back out of the
# call the loop actually made.


def _capture_first_link(loader, safety_level="open", context_language="de",
                        seed_previous=None):
    """Run the real loop until it asks for a prompt; return what it asked with."""
    captured = {}

    class Recorder:
        def build_chunk(self, **kw):
            captured.update(kw)
            # BaseException on purpose: the loop catches Exception per link and
            # would turn a plain error into a failed step and carry on.
            raise SystemExit

    ex = PE.PipelineExecutor(SCHEMAS)
    ex.chunk_builder = Recorder()
    cfg = loader.get_config(CONFIG)
    ctx = PE.PipelineContext(input_text="Ein Haus am Fluss.",
                             user_input="Ein Haus am Fluss.")
    if seed_previous:
        ctx.add_output(seed_previous)
    steps = [PE.PipelineStep(step_id="s", chunk_name=cfg.chunks[0])]
    try:
        asyncio.run(ex._execute_recursive_pipeline_steps(
            CONFIG, steps, ctx, None, resolved_config=cfg,
            safety_level=safety_level, run_id="t",
            context_language=context_language))
    except SystemExit:
        pass
    assert captured, "the loop finished without ever asking for a prompt"
    return captured


def test_the_run_hands_the_builder_the_pipeline(loader):
    kw = _capture_first_link(loader)
    assert kw.get("pipeline") is not None, (
        "the step asked for a prompt without saying which pipeline it belongs "
        "to; the builder then guesses the instruction type"
    )
    assert kw["pipeline"].name == "text_transformation_recursive"
    assert kw["pipeline"].instruction_type == "chain_translation"


def test_the_prompt_the_run_assembles_names_the_target_language(loader):
    from schemas.engine.random_language_selector import SUPPORTED_LANGUAGES

    kw = _capture_first_link(loader)
    prompt = ChunkBuilder(SCHEMAS).build_chunk(**kw)["prompt"]

    assert "ALWAYS reply in the Target language" in prompt
    # The sentence that made a model argue with itself for a whole answer.
    assert "ALWAYS reply in the language of the Input" not in prompt

    # Spelled out, and drawn by the LOOP -- not written into the call by a test.
    name = kw["context"]["custom_placeholders"]["TARGET_LANGUAGE"]
    assert name in set(SUPPORTED_LANGUAGES.values()), name
    assert f"Target language: {name}" in prompt
    assert "{{" not in prompt


def test_the_run_hands_the_builder_the_previous_link(loader):
    """The link reads the link before it -- read off the call, not the fake."""
    kw = _capture_first_link(loader, seed_previous="A house by the river.")
    prompt = ChunkBuilder(SCHEMAS).build_chunk(**kw)["prompt"]
    assert "A house by the river." in prompt
    # The run input is the same text on every pass; that was the old fault.
    assert "Ein Haus am Fluss." not in prompt


def test_the_run_hands_the_builder_the_age_level_and_the_language(loader):
    from schemas.engine.instruction_selector import SAFETY_PREFIXES

    kw = _capture_first_link(loader, safety_level="kids")
    assert kw["context_language"] == "de"
    prompt = ChunkBuilder(SCHEMAS).build_chunk(**kw)["prompt"]
    assert SAFETY_PREFIXES["kids"] in prompt


def test_the_loop_turns_the_research_offer_off(loader):
    """Nine links, each able to re-run itself for lookups it has nothing to do."""
    kw = _capture_first_link(loader)
    assert kw["context"]["custom_placeholders"].get("_SKIP_WIKIPEDIA") is True


def test_the_assembled_prompt_is_what_the_model_is_asked(loader):
    """Everything else stops at the builder's return value. This follows it out."""
    seen = {}

    async def spy(request):
        seen["prompt"] = request.prompt
        return PE.BackendResponse(success=True, content="Ein Haus am Fluss.",
                                  metadata={})

    ex = PE.PipelineExecutor(SCHEMAS)
    ex.backend_router.process_request = spy
    cfg = loader.get_config(CONFIG)
    step = PE.PipelineStep(step_id="loop_1", chunk_name=cfg.chunks[0])
    ctx = PE.PipelineContext(input_text="Ein Haus am Fluss.",
                             user_input="Ein Haus am Fluss.")
    ctx.custom_placeholders["_SKIP_WIKIPEDIA"] = True
    ctx.custom_placeholders["TARGET_LANGUAGE"] = "Japanese"
    ctx.custom_placeholders["TARGET_LANGUAGE_CODE"] = "ja"

    out = asyncio.run(ex._execute_single_step(
        step, ctx, resolved_config=cfg, safety_level="open",
        context_language="de"))

    assert out == "Ein Haus am Fluss."
    assert "ALWAYS reply in the Target language" in seen["prompt"]
    assert "Target language: Japanese" in seen["prompt"]


def test_a_single_call_preset_keeps_its_instruction(loader):
    """Handing the pipeline over changes ONE pipeline. This is the other case."""
    captured = {}

    class Recorder:
        def build_chunk(self, **kw):
            captured.update(kw)
            raise SystemExit

    ex = PE.PipelineExecutor(SCHEMAS)
    ex.chunk_builder = Recorder()
    cfg = loader.get_config("bauhaus")
    step = PE.PipelineStep(step_id="s", chunk_name=cfg.chunks[0])
    ctx = PE.PipelineContext(input_text="Ein Haus am Fluss.",
                             user_input="Ein Haus am Fluss.")
    ctx.custom_placeholders["_SKIP_WIKIPEDIA"] = True
    try:
        asyncio.run(ex._execute_single_step(
            step, ctx, resolved_config=cfg, safety_level="open",
            context_language="de"))
    except SystemExit:
        pass

    assert captured["pipeline"].name == "text_transformation"
    prompt = ChunkBuilder(SCHEMAS).build_chunk(**captured)["prompt"]
    # Gegen die Konstanten, nicht gegen einen abgetippten Satz: eine Umformulierung
    # des Aufgabensatzes soll diesen Test nicht faellen, ein vertauschter Typ schon.
    assert STRUCTURAL_TRANSFORMATION in prompt
    assert CHAIN_LANGUAGE_RULE not in prompt


# --- what a person's own instruction may not take with it ------------------
#
# A kept perspective can be forked off any preset and carries its own task
# instruction, which replaces the type's text whole. Two things in that text
# belong to the platform rather than to the type, and both are put back:
# the cultural-respect rule, and — on a chain — the rule that makes a link a
# translation at all. Without the second, nine links apply the fork's
# instruction to their own output and nothing is ever rendered into the
# language the loop names.


def test_a_fork_of_the_chain_still_translates():
    from schemas.engine.instruction_selector import (
        get_instruction, CHAIN_LANGUAGE_RULE, CULTURAL_RESPECT_PRINCIPLES)

    own = "Render the text in the plainest words you have."
    out = get_instruction("chain_translation", custom_override=own)

    assert own in out
    assert CHAIN_LANGUAGE_RULE in out
    assert CULTURAL_RESPECT_PRINCIPLES in out
    # The act comes before the manner.
    assert out.index(CHAIN_LANGUAGE_RULE) < out.index(own)


def test_a_fork_elsewhere_is_not_turned_into_a_translation():
    from schemas.engine.instruction_selector import (
        get_instruction, CHAIN_LANGUAGE_RULE)

    own = "Render the text in the plainest words you have."
    out = get_instruction("transformation", custom_override=own)
    assert CHAIN_LANGUAGE_RULE not in out


def test_the_refusal_is_exempt_from_the_target_language(loader):
    """Otherwise a refusal comes back translated and the chain carries it on.

    The prefix names one German sentence to refuse with; the chain orders the
    target language and no other. Detection is a substring match on that
    German sentence (pipeline_executor), so a translated refusal is not seen
    as one: the remaining links paraphrase it and the run reports success.
    """
    from schemas.engine.instruction_selector import SAFETY_REFUSAL_SENTENCE

    for level in ("kids", "youth"):
        kw = _capture_first_link(loader, safety_level=level)
        prompt = ChunkBuilder(SCHEMAS).build_chunk(**kw)["prompt"]
        assert SAFETY_REFUSAL_SENTENCE in prompt
        assert "One exception: where the SAFETY rules above require a refusal" in prompt
        assert "word for word, in the language they give it in" in prompt


# --- leave the event loop as it was found ----------------------------------
#
# asyncio.run() closes its loop and leaves none current for the thread. Files
# that run after this one call asyncio.get_event_loop() and get "There is no
# current event loop" -- 23 tests in test_diffusers_chunk_migration.py fail
# for no reason of their own, and only when this file happens to run first.

@pytest.fixture(autouse=True)
def _restore_event_loop():
    yield
    asyncio.set_event_loop(asyncio.new_event_loop())
