#!/usr/bin/env python3
"""The repetition guard counts a think block apart.

On 2026-10-29 Qwen 3.8 27B, translating a Quechua text on the canvas,
glossed one word three times in its think block -- '"uywankunawan" = with
animals.' -- and the guard stopped it there after 3,932 characters, before it
had written a word of the answer: a model that reasons repeats what it
checks. Inside the block a segment that recurs between other lines now ends
the generation at its tenth occurrence, a run written three times in a row at
its third round, and the block and the answer keep separate counts. Since
2026-10-31 the answer counts the same way; until then its third identical
segment of 30 characters or more ended it, wherever it stood. The periodic
rule reads the pieces whole, tags included.

Run: pytest devserver/tests/test_repetition_guard_think_block.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_local_llm_finite import llm  # noqa: F401  (the fixture: the node module with ComfyUI stubbed)
from test_local_llm_thinking_switch import _Tok, _built

GLOSS = '"uywankunawan" = with animals.'          # the line of 2026-10-29
LINE = "The suffix -kuna marks the plural of the noun."


def _check(n):
    return f"Check {n}: the case ending stays as it was written."


def _think(guard, text):
    return guard.feed_split(text, "", text)


def test_a_line_between_other_lines_ends_the_run_at_its_tenth_occurrence(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    for n in range(1, 11):
        assert _think(guard, LINE + "\n") is (n == 10)
        if n < 10:
            assert not _think(guard, _check(n) + "\n")
    assert guard.reason == "segment" and guard.in_think
    assert guard.describe() == "the same passage 10x in its think block: %r" % LINE.lower()


def test_short_lines_between_the_copies_keep_them_apart(llm):
    # The likely shape of 2026-10-29: the gloss, a hesitation, the gloss again.
    mod, _ = llm
    guard = mod.RepetitionGuard()
    for line in (GLOSS, "Hmm.", GLOSS, "Wait, let me check.", GLOSS):
        assert not _think(guard, line + "\n")


def test_a_run_written_three_times_in_a_row_ends_at_the_third_round(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    paragraph = [LINE, "Hmm.", _check(1)]
    fired = [_think(guard, line + "\n") for _ in range(3) for line in paragraph]
    assert fired == [False] * 8 + [True]
    assert guard.reason == "round" and guard.in_think
    assert guard.describe() == "the same run 3x in a row in its think block: %r" % (
        " / ".join(s.lower() for s in paragraph))


def test_a_line_between_other_lines_ends_the_answer_at_its_tenth_occurrence(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    for n in range(1, 11):
        assert guard.feed(LINE + "\n") is (n == 10)
        if n < 10:
            assert not guard.feed(_check(n) + "\n")
    assert guard.reason == "segment" and not guard.in_think
    assert guard.describe() == "the same passage 10x: %r" % LINE.lower()


def test_a_run_in_the_answer_ends_at_its_third_round(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    paragraph = [LINE, _check(1), "Short."]
    fired = [guard.feed(line + "\n") for _ in range(3) for line in paragraph]
    assert fired == [False] * 8 + [True]
    assert guard.reason == "round" and not guard.in_think
    assert guard.describe() == "the same run 3x in a row: %r" % (
        " / ".join(s.lower() for s in paragraph))


def test_a_line_written_three_times_in_a_row_ends_the_answer(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert [guard.feed(LINE + "\n") for _ in range(3)] == [False, False, True]
    assert guard.reason == "round" and not guard.in_think


def test_a_line_numbered_anew_each_time_ends_the_answer_at_its_third_copy(llm):
    # A list mark keeps nothing apart.
    mod, _ = llm
    guard = mod.RepetitionGuard()
    line = "Variant 0 of the sentence that keeps coming back here."
    assert [guard.feed(f"{n}. {line}\n") for n in range(1, 4)] == [False, False, True]
    assert guard.reason == "round"


def test_a_poem_of_four_stanzas_ending_on_the_same_line_runs_to_its_end(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    line = "Und der Wind trägt meine Lieder über das weite Land."
    stanzas = ["Am Morgen steht der Nebel tief im Tal.", "Am Mittag glüht der Stein am Wegesrand.",
               "Am Abend singt die Amsel auf dem Dach.", "In der Nacht ruht das Dorf im Schein."]
    assert [guard.feed(piece + "\n") for stanza in stanzas for piece in (stanza, line, "")] == \
        [False] * 12


def test_the_block_and_the_answer_count_apart(llm):
    # A translation drafted twice in the block and given once as the answer.
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not _think(guard, LINE + "\n")
    assert not _think(guard, _check(1) + "\n")
    assert not _think(guard, LINE + "\n")
    assert not guard.feed(LINE + "\n")


@pytest.mark.parametrize("line", ["---\n", "---\n\n", "---\n \n", "•••\n", "#" * 29 + "\n",
                                  "-" * 40 + "\n", "_" * 12 + "\n", "=====\n"])
def test_the_same_rule_sixty_times_in_a_row_ends_the_generation(llm, line):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert [_think(guard, line) for _ in range(60)] == [False] * 59 + [True]
    assert guard.reason == "marks" and guard.in_think
    guard = mod.RepetitionGuard()
    assert [guard.feed(line) for _ in range(60)] == [False] * 59 + [True]
    assert guard.once(line * 60) == line.strip()
    assert "60x" in guard.describe()


def test_a_line_between_the_rules_begins_their_count_again(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    rules = ["---\n"] * 59
    assert not any(guard.feed(piece) for piece in rules + ["Ja.\n"] + rules)


def test_another_mark_between_the_rules_begins_their_count_again(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not any(guard.feed(piece) for piece in ["---\n"] * 59 + ["***\n"] + ["---\n"] * 59)


def test_the_block_and_the_answer_count_rules_apart(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not any(_think(guard, "---\n") for _ in range(30))
    assert not any(guard.feed("---\n") for _ in range(30))


def test_a_list_of_numbers_runs_to_its_end(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not any(guard.feed(f"{n}.\n") for n in range(1, 101))
    guard = mod.RepetitionGuard()
    assert not guard.feed("Wir zählen: " + " ".join(f"{n}." for n in range(1, 101)) + "\n")


def test_a_worksheet_of_numbered_blanks_runs_to_its_end(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not any(guard.feed(piece) for piece in
                   ["Arbeitsblatt:\n"] + [f"{n}. {'_' * 12}\n" for n in range(1, 21)])


def test_a_line_numbered_anew_each_time_ends_the_block_at_its_third_copy(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    line = "Fold the paper in half along the dotted line."
    assert [_think(guard, f"{n}. {line}\n") for n in range(1, 4)] == [False, False, True]
    assert guard.reason == "round" and guard.in_think


def test_a_run_of_twenty_segments_is_the_longest_round(llm):
    mod, _ = llm
    lines = [f"Line {n} of the paragraph that is written again." for n in range(21)]
    guard = mod.RepetitionGuard()
    fired = [guard.feed(line + "\n") for _ in range(3) for line in lines[:20]]
    assert fired == [False] * 59 + [True] and guard.reason == "round"
    guard = mod.RepetitionGuard()
    assert not any(guard.feed(line + "\n") for _ in range(3) for line in lines)


def test_a_run_counts_from_thirty_characters(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert [guard.feed("x" * 30 + "\n") for _ in range(3)] == [False, False, True]
    guard = mod.RepetitionGuard()
    assert not any(guard.feed("x" * 29 + "\n") for _ in range(3))


@pytest.mark.parametrize("mark", ["1)", "-", "---", "*", ">"])
def test_a_mark_on_its_own_line_keeps_no_copies_apart(llm, mark):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert [guard.feed(piece) for _ in range(3) for piece in (mark + "\n", LINE + "\n")] == \
        [False] * 5 + [True]


def test_the_block_and_the_answer_count_passages_apart(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    for n in range(1, 6):
        assert not _think(guard, LINE + "\n" + _check(n) + "\n")
    for n in range(1, 6):
        assert not guard.feed(LINE + "\n" + _check(n) + "\n")


def test_a_run_in_the_block_and_one_in_the_answer_are_two_runs(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not _think(guard, LINE + "\n")
    assert not _think(guard, LINE + "\n")
    assert not guard.feed(LINE + "\n")


def test_a_short_loop_in_the_think_block_ends_as_before(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    fired = [_think(guard, "and the, ") for _ in range(10)]
    assert fired == [False] * 9 + [True]
    assert guard.reason == "loop" and guard.in_think


def _generate(llm, monkeypatch, pieces):
    mod, torch = llm
    tok = _Tok()
    monkeypatch.setattr(mod, "get_built", lambda d: _built(torch, tok, pieces, False))
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: 0)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    return mod.generate("Some--Model", messages=[{"role": "user", "content": "translate this"}],
                        temperature=0.0, context_tokens=4096, enable_thinking=True)


def test_generate_hands_the_guard_the_piece_and_both_sides_of_it(llm, monkeypatch):
    # One piece of the stream carries the end of the block, the closer and
    # the start of the answer ('Check.</think>\n\n'); the guard gets it whole
    # for the periodic rule and split for the counts.
    mod, _ = llm
    fed = []

    class _Recording(mod.RepetitionGuard):
        def feed_split(self, piece, answer, thought):
            fed.append((piece, answer, thought))
            return super().feed_split(piece, answer, thought)

    monkeypatch.setattr(mod, "RepetitionGuard", _Recording)
    out = _generate(llm, monkeypatch, [GLOSS, "\n", "Check.", "</think>", "\n\n", "с", " животните"])
    assert out["content"] == "с животните"
    assert "".join(p for p, _, _ in fed) == GLOSS + "\nCheck.</think>\n\nс животните"
    assert "".join(t for _, _, t in fed) == GLOSS + "\nCheck."
    assert "".join(a for _, a, _ in fed) == "\n\nс животните"


def test_a_word_checked_three_times_in_the_block_gets_its_answer(llm, monkeypatch):
    pieces = []
    for n in range(3):
        pieces += [GLOSS, "\n", _check(n), "\n"]
    pieces += ["</think>", "\n\n", "с", " животните"]
    out = _generate(llm, monkeypatch, pieces)
    assert out["finish_reason"] == "stop"
    assert out["content"] == "с животните"


def test_a_loop_of_empty_blocks_is_still_stopped(llm, monkeypatch):
    # The tags carry this loop's period; the counts see nothing in it.
    out = _generate(llm, monkeypatch, ["</think>", "\n\n", "<think>", "\n\n"] * 12)
    assert out["finish_reason"] == "repetition"


def test_a_line_looping_in_the_block_is_still_stopped(llm, monkeypatch):
    out = _generate(llm, monkeypatch, [LINE, "\n"] * 4)
    assert out["finish_reason"] == "repetition"
