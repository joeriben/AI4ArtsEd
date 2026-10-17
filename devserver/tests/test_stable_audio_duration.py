#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The adaption decides how long a sound has to be, and the chunk reads it.

The x2audio flow itself produces the length specification (adaption prompt).
The adaption writes `DURATION: <seconds>` as its last line;
`output_audio_stableaudio_diffusers` takes that line off the prompt and uses the
number instead of the config's default. Measured: the same prompt
came back as 289688 bytes at 12 s, 1144206 at the config's 47.6 s, 2881453 at
120 s and 5761610 at 240 s.

The line has to survive Stage 3's translation to get here. Measured on the
running backend: „…kurzer harter Anschlag.\\nDURATION: 12" came back as „…short
hard impact.\\nDURATION: 12", the line untouched. The parser is tolerant anyway,
because a translation is a model and models are not promises.
"""
import sys
from pathlib import Path

import pytest

from file_modules import DEVSERVER, load_module

sys.path.insert(0, str(DEVSERVER))

CHUNK = (DEVSERVER / "schemas" / "chunks"
         / "output_audio_stableaudio_diffusers.py")
sa3 = load_module("sa3_chunk", CHUNK)


@pytest.mark.parametrize("prompt,seconds,left", [
    ("a bell rings once\nDURATION: 12", 12.0, "a bell rings once"),
    # An LLM told to write a bare line will still decorate it.
    ("warm pad\n\n**DURATION:** 45 seconds", 45.0, "warm pad"),
    ("x\n- length = 33s", 33.0, "x"),
    ("x\nDuration: 20,5 s", 20.5, "x"),          # a decimal comma
    ("x\ndauer: 90 sek", 90.0, "x"),             # translated after all
    ("x\nDURATION: 60.5", 60.5, "x"),
    ("x\nDURATION: 30\n\n", 30.0, "x"),          # trailing blank lines
])
def test_the_line_is_read_and_taken_off_the_prompt(prompt, seconds, left):
    text, got = sa3._take_duration(prompt)
    assert got == seconds
    assert text == left


@pytest.mark.parametrize("prompt", [
    "a bell rings once",
    "",
    # Prose ABOUT a duration is prose: only the last line counts, so this stays
    # in the prompt where it belongs.
    "the duration of the piece matters\nand then a bell",
    "DURATION follows the shape of the piece",
])
def test_a_prompt_without_a_line_is_left_alone(prompt):
    text, got = sa3._take_duration(prompt)
    assert got is None
    assert text == prompt


@pytest.mark.parametrize("asked,used", [
    (999, sa3.DURATION_MAX_SECONDS),
    (2, sa3.DURATION_MIN_SECONDS),
    (240, 240.0),
    (10, 10.0),
])
def test_a_length_outside_the_frame_is_pulled_into_it(asked, used):
    """The GPU service clamps silently; clamping here puts the number in the log
    instead. The ceiling is the platform's own, STABLE_AUDIO_MAX_DURATION."""
    _, got = sa3._take_duration(f"a sound\nDURATION: {asked}")
    assert got == used


def test_a_prompt_that_is_nothing_but_the_line_keeps_its_text():
    """An empty prompt raises in execute(). Better a prompt that says DURATION
    than no prompt at all."""
    text, got = sa3._take_duration("DURATION: 30")
    assert got == 30.0
    assert text.strip()


def test_the_adaption_is_told_to_write_the_line():
    """The parser and the instruction are two halves of one thing. If the
    instruction stops asking, every sound silently goes back to one length."""
    instruction = sa3.CHUNK_META["optimization_instruction"]
    assert "DURATION:" in instruction
    assert "10" in instruction and "240" in instruction


def test_the_frame_matches_the_platform_ceiling():
    """DURATION_MAX_SECONDS must not promise more than the GPU service renders —
    it clamps without telling anybody."""
    gpu_config = DEVSERVER.parent / "gpu_service" / "config.py"
    if not gpu_config.is_file():
        pytest.skip("gpu_service not present in this checkout")
    for line in gpu_config.read_text(encoding="utf-8").splitlines():
        if line.startswith("STABLE_AUDIO_MAX_DURATION"):
            ceiling = float(line.split("=")[1].split("#")[0].strip())
            assert sa3.DURATION_MAX_SECONDS <= ceiling
            return
    pytest.fail("STABLE_AUDIO_MAX_DURATION not found in gpu_service/config.py")

# --- Was die Prüfläufe am 2026-08-12 gebrochen haben ------------------------
# Drei adversariale Durchgänge haben genau diese Eingaben gefunden. Sie sind
# nicht theoretisch: jede von ihnen hat vorher die Länge verworfen UND die
# Anweisung als Text an das Audio-Modell durchgereicht.

@pytest.mark.parametrize("prompt,seconds,left", [
    # Ein Modell schließt seinen Block ab. Vorher kostete das die Länge.
    ("a door\nDURATION: 45\n```", 45.0, "a door"),
    ("a door\nDURATION: 45\n---", 45.0, "a door"),
    ("a door\nDURATION: 45\n***", 45.0, "a door"),
    ("a door\nDURATION: 45\n\"", 45.0, "a door"),
    # Zwei Zeilen: die letzte gilt, und BEIDE verschwinden aus dem Prompt.
    ("a door\nDURATION: 45\nDURATION: 90", 90.0, "a door"),
    # Ohne Doppelpunkt, mit Tilde.
    ("a drone\nDURATION 45", 45.0, "a drone"),
    ("a drone\nduration: ~45 s", 45.0, "a drone"),
])
def test_the_shapes_that_broke_it(prompt, seconds, left):
    text, got = sa3._take_duration(prompt)
    assert got == seconds
    assert text == left


def test_a_thousands_separator_asks_for_long_not_short():
    """`1,200` read as 1.2 turned the LONGEST request into the SHORTEST sound —
    the clamp then hid it at the floor. It has to land at the ceiling."""
    for raw in ("1,200", "1.200"):
        _, got = sa3._take_duration(f"a drone\nDURATION: {raw}")
        assert got == sa3.DURATION_MAX_SECONDS


def test_decoration_without_a_length_leaves_the_prompt_alone():
    """Walking past a closing fence may not silently eat one when there is no
    length behind it — the fence belongs to the prompt then."""
    prompt = "a door\n```"
    text, got = sa3._take_duration(prompt)
    assert got is None
    assert text == prompt


def test_the_reenactment_page_writes_its_own_length():
    """The Cover-Band page ends its text with the recording's length, so a stray
    line inside lyrics or tags cannot decide it instead. If this construction
    disappears, that page silently goes back to whatever the text happens to say.
    """
    service = (Path(__file__).resolve().parents[1] / "my_app" / "services"
               / "parrot_service.py").read_text(encoding="utf-8")
    assert 'DURATION: {song_seconds}' in service


def test_the_last_line_wins_over_one_hidden_in_the_text():
    """The failure the page guards against, exercised end to end."""
    lyrics = "und dann sang er\nDauer: 12"
    text, got = sa3._take_duration(f"{lyrics}\nDURATION: 97.3")
    assert got == 97.3
    # Beide Zeilen sind Anweisungen und gehen beide vom Prompt herunter.
    assert text == "und dann sang er"
