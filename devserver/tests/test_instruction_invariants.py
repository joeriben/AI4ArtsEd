#!/usr/bin/env python3
"""Two things in a task instruction belong to the platform, not to its type.

They were held by devserver/tests/test_chain_translation.py, which went with the
preset it was written for on 2026-09-06. Neither is about that preset:

  * The CULTURAL RESPECT block. A person who is logged in can fork a perspective
    and write their own task instruction (interception_prompts_routes checks its
    type and its length, and nothing else); that text replaces the whole body of
    the instruction type. get_instruction puts the block back.
  * The refusal sentence. Three places carry it: the constant, and the two
    safety prefixes, which tell the model to answer WITH it. Until 2026-10-10
    two comparison pages in the frontend recognised a refusal by matching on a
    copy of the sentence; the backend reads it in one place now
    (instruction_selector.is_safety_refusal) and answers a block at stage 2,
    so no frontend file may carry the sentence (finding S-015 of the code review of 2026-10-10).

Run: python3 -m pytest devserver/tests/test_instruction_invariants.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas.engine.instruction_selector import (
    CULTURAL_RESPECT_PRINCIPLES,
    INSTRUCTION_TYPES,
    READING_VOLUME_WORDS,
    SAFETY_PREFIXES,
    SAFETY_REFUSAL_SENTENCE,
    get_instruction,
    get_reading_volume_clause,
)

FRONTEND_SRC = Path(__file__).resolve().parents[2] / "public/ai4artsed-frontend/src"


# --- the cultural block ----------------------------------------------------

def test_the_interception_instruction_carries_the_cultural_block():
    """Named, not inferred: the block belongs to the type that INTERCEPTS.

    The media-side types (prompt_optimization, triple_prompt_optimization) put
    a text into a shape an image model reads and describe no culture, and
    `passthrough` is a no-op. Asserting over every type would either be wrong
    about them or quietly weaken into a filter that lets a future type through.
    """
    assert CULTURAL_RESPECT_PRINCIPLES in INSTRUCTION_TYPES["transformation"]["default"]
    # The legacy alias resolves to it, and so does an unknown type -- neither
    # may become a way around the block.
    assert CULTURAL_RESPECT_PRINCIPLES in get_instruction("artistic_transformation")
    assert CULTURAL_RESPECT_PRINCIPLES in get_instruction("a type nobody defined")


def test_a_self_written_task_instruction_cannot_drop_the_cultural_block():
    own = "Rewrite the input as a list of the objects you can name in it."
    out = get_instruction("transformation", custom_override=own)
    assert own in out
    assert CULTURAL_RESPECT_PRINCIPLES in out


def test_the_cultural_block_is_not_pasted_in_twice():
    own = "Do it plainly.\n\n" + CULTURAL_RESPECT_PRINCIPLES
    out = get_instruction("transformation", custom_override=own)
    assert out.count("CULTURAL RESPECT PRINCIPLES:") == 1


def test_the_age_prefix_survives_a_self_written_instruction():
    own = "Rewrite the input as a list of the objects you can name in it."
    for level in ("kids", "youth"):
        out = get_instruction("transformation", custom_override=own,
                              safety_level=level)
        assert out.startswith(SAFETY_PREFIXES[level]), level
        assert CULTURAL_RESPECT_PRINCIPLES in out


# --- the refusal sentence --------------------------------------------------

def test_both_prefixes_ask_for_the_sentence_the_constant_names():
    for level, prefix in SAFETY_PREFIXES.items():
        assert SAFETY_REFUSAL_SENTENCE in prefix, level


# What the two comparison surfaces matched until 2026-10-10 (a second German
# fragment beside the sentence, three English literals), as fragments: a
# matcher on any of them is the fault, whatever else it adds.
REFUSAL_FRAGMENTS = (
    "kann ich dich nicht unterst",
    "cannot support you",
    "i can't help",
)


def test_the_frontend_matches_on_no_sentence():
    """A refusal reaches a surface as a block (status blocked, stage 2), never
    as a sentence to match: no .vue/.ts/.js under src/ outside i18n/ (which
    may DISPLAY a sentence) and outside the specs carries a fragment of the
    sentence. Out of Python's reach, so it is checked as text."""
    assert SAFETY_REFUSAL_SENTENCE.lower().startswith("hierbei " + REFUSAL_FRAGMENTS[0])
    carrying = sorted(
        str(f.relative_to(FRONTEND_SRC))
        for f in FRONTEND_SRC.rglob("*")
        if f.suffix in (".vue", ".ts", ".js")
        and "i18n" not in f.relative_to(FRONTEND_SRC).parts
        and "__tests__" not in f.relative_to(FRONTEND_SRC).parts
        and not f.name.endswith(".spec.ts")
        and any(n in f.read_text(encoding="utf-8").lower() for n in REFUSAL_FRAGMENTS)
    )
    assert carrying == [], carrying


def test_the_backend_reads_the_sentence_in_one_place():
    from schemas.engine.instruction_selector import is_safety_refusal
    assert is_safety_refusal(SAFETY_REFUSAL_SENTENCE)
    assert is_safety_refusal("  " + SAFETY_REFUSAL_SENTENCE.lower() + " weil ...")
    assert is_safety_refusal("Hierbei kann ich dich nicht unterstuetzen.")  # a model's spelling, logged 2026-03-18
    assert not is_safety_refusal("a house by the lake")


# --- die Lesemengen-Klausel ------------------------------------------------
#
# Sie ist die einzige Laengenangabe, die eine Einstellung setzt, und sie stand
# bis 2026-09-07 ohne jede Zusicherung da: eine Zahl in der Tabelle, ein
# Altname in config, ein Tor in chunk_builder, und keine Zeile, die faellt,
# wenn eines davon verrutscht.

def test_the_table_answers_for_every_mode_the_interface_offers():
    """Die drei Modi der Auswahl, und fuer jeden eine Zahl."""
    assert set(READING_VOLUME_WORDS) == {"easy", "medium", "expert"}
    zahlen = [READING_VOLUME_WORDS[m] for m in ("easy", "medium", "expert")]
    assert zahlen == sorted(zahlen), "die Grenze waechst mit dem Modus"


def test_every_mode_and_every_legacy_name_gets_its_clause():
    import config
    vorher = getattr(config, "UI_MODE", None)
    try:
        for name, erwartet in (("easy", "easy"), ("medium", "medium"),
                               ("expert", "expert"), ("kids", "easy"),
                               ("youth", "medium"), ("EXPERT", "expert"),
                               ("  easy  ", "easy")):
            config.UI_MODE = name
            assert (f"at most {READING_VOLUME_WORDS[erwartet]} words"
                    in get_reading_volume_clause()), name
        # Was die Auswahl nicht kennt, bekommt keine Grenze -- still, und das
        # ist der Grund, warum POST /api/settings/ den Wert nicht frei lassen
        # sollte. Hier steht nur, DASS es so ist.
        for name in ("", None, 3, "open", "adult", "quatsch"):
            config.UI_MODE = name
            assert get_reading_volume_clause() == "", repr(name)
    finally:
        config.UI_MODE = vorher


def test_the_clause_says_what_to_keep_when_it_asks_to_shorten():
    """Sie nennt eine Obergrenze UND die Richtung der Kuerzung.

    Ohne die zweite Haelfte laesst ein Modell das Teure fallen, und das Teure
    ist der Umbau der Gegenstaende und ihrer Beziehungen -- also die
    Interception selbst.
    """
    import config
    vorher = getattr(config, "UI_MODE", None)
    try:
        config.UI_MODE = "easy"
        klausel = get_reading_volume_clause()
        assert klausel.startswith("\n\nLength: at most ")
        assert "entities" in klausel and "relations" in klausel
    finally:
        config.UI_MODE = vorher
