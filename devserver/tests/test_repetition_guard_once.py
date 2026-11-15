#!/usr/bin/env python3
"""A loop the repetition guard stopped, in its once form.

On 2026-10-29 qwen3-vl:4b, translating a Korean prompt into Quechua on the
canvas, wrote 'kuyu, kanki, yana, kancha, ' over and over; the guard stopped
it and the engine refused the answer, so the translation node ended the run
with an error. Since 2026-10-31 a repetition stands once and the run goes
on (docs/DEVELOPMENT_DECISIONS.md). The node hands the answer on as written,
and beside it the answer with what repeated in it standing in it once
(RepetitionGuard.once); the Canvas translation, Interception and Model
Adaption nodes take that form (test_interception_local_branch.py,
test_canvas_translation_node.py, test_canvas_interception_passthrough.py,
test_canvas_model_adaption.py).

The pieces are cut as the node's streamer cuts them: a word with the space
after it, and in Chinese and Japanese one sign, a comma held back and sent
with the sign after it.

Run: pytest devserver/tests/test_repetition_guard_once.py -q
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_local_llm_finite import llm  # noqa: F401  (the fixture: the node module with ComfyUI stubbed)
from test_local_llm_thinking_switch import _Tok, _built

UNIT = "kuyu, kanki, yana, kancha, "               # the unit of 2026-10-29
ONCE = "Kay wasiqa kuyu, kanki, yana, kancha,"
SEGMENT = "The house stands in a landscape of fields and animals."
SECOND = "The sky is grey over the barn and the fields."
S = "Kay wasiqa hatun pampapi sayan uywakunawan."
P = "Pampapi uywakuna puriykachanku sumaqta."


def _words(text):
    return re.findall(r"\S+\s*", text)


def _signs(text):
    pieces, held = [], ""
    for ch in text:
        held += ch
        if ch.isalnum():
            pieces.append(held)
            held = ""
    return pieces + ([held] if held else [])


def _fed(llm, pieces):
    """The guard fed `pieces` up to the one that made it fire, and the answer
    up to there, as the node collects it."""
    mod, _ = llm
    guard = mod.RepetitionGuard()
    answered = []
    for piece in pieces:
        answered.append(piece)
        if guard.feed(piece):
            break
    assert guard.triggered
    return guard, "".join(answered)


def _once(llm, text, split=_words):
    guard, answer = _fed(llm, split(text))
    return guard.once(answer)


# --- a loop: the first round stays ---------------------------------------------

def test_the_loop_of_2026_10_29_keeps_its_first_round(llm):
    assert _once(llm, "Kay wasiqa " + UNIT * 12) == ONCE


def test_a_chinese_loop_keeps_its_first_round_whole(llm):
    # The piece that fires carries the comma of one round and the first
    # sign of the next.
    assert _once(llm, "翻译：" + "库尤，坎基，亚纳，坎查，" * 15, _signs) == "翻译：库尤，坎基，亚纳，坎查，"


def test_a_japanese_loop_keeps_its_first_round_whole(llm):
    round_ = "家は広い野原に立っています。空は灰色で、遠くに赤い納屋があります。"
    assert _once(llm, round_ * 12, _signs) == round_


def test_a_word_written_over_and_over_inside_the_round_is_not_the_loop(llm):
    assert _once(llm, "Kay wasiqa " + ("kuyu, " + "yana, " * 7) * 12) == \
        "Kay wasiqa kuyu, " + "yana, " * 6 + "yana,"


def test_a_short_word_written_more_often_than_the_rounds_is_not_the_loop(llm):
    assert _once(llm, "Das Lied geht so: " + ("Tra " + "la " * 15) * 14) == \
        "Das Lied geht so: Tra " + "la " * 14 + "la"


def test_a_word_written_over_and_over_stands_once(llm):
    assert _once(llm, "Wasi " + "no " * 40) == "Wasi no"


def test_a_round_keeps_its_end_where_the_text_before_it_ends_the_same_way(llm):
    assert _once(llm, "Pampa hatun. " + "Inti lluqsimun hatun. " * 12) == \
        "Pampa hatun. Inti lluqsimun hatun."
    first = "家は広い野原に立っています。"
    round_ = "空は灰色で、遠くに赤い納屋があります。"
    assert _once(llm, first + round_ * 12, _signs) == first + round_
    first = "房子矗立在一片广阔的田野上。"
    round_ = "天空是灰色的，远处有一个红色的谷仓。"
    assert _once(llm, first + round_ * 12, _signs) == first + round_


@pytest.mark.parametrize("text, once, split", [
    ("मैदान बड़ा है। " + "सूरज उगता है। " * 14,
     "मैदान बड़ा है। सूरज उगता है।", _words),
    ("सूरज उगता है, और पक्षी गाते हैं। " * 12,
     "सूरज उगता है, और पक्षी गाते हैं।", _words),
    ("هل الحقل كبير؟ " + "هل البيت كبير؟ " * 14,
     "هل الحقل كبير؟ هل البيت كبير؟", _words),
    ('Sie ruft: "Komm her." ' * 12, 'Sie ruft: "Komm her."', _words),
    ("Il dit : « Viens ici. » " * 12, "Il dit : « Viens ici. »", _words),
    ("他说：“过来。”" * 14, "他说：“过来。”", _signs),
    ("彼は言った「来て。」" * 14, "彼は言った「来て。」", _signs),
    ("Es ist z. B. ein Haus und z. B. ein Feld, " * 12, "Es ist z. B. ein Haus und z. B. ein Feld,", _words),
])
def test_a_round_ends_where_its_sentence_ends(llm, text, once, split):
    """Devanagari, Arabic and the quotes after a stop end a sentence; an
    abbreviation inside the round ends none."""
    assert _once(llm, text, split) == once


def test_a_loop_of_list_numbers_keeps_its_round(llm):
    assert _once(llm, "1.\n" * 40) == "1."
    assert _once(llm, "12. 13. " * 20) == "12. 13."


# The loop of 2026-10-31 at the Interception node: 144 characters, no full stop.
LONG_ROUND = ("not a myth, not a legend, not a story, not a memory, not a dream, not a fantasy, "
              "not a reality, not a truth, not a lie, not a truth, not a lie, ")


def test_a_loop_of_a_round_longer_than_sixty_characters_stops_at_its_third_round(llm):
    before = "The figure is not a person, it is a unit of observation, "
    guard, answer = _fed(llm, _words(before + LONG_ROUND * 6))
    assert guard.reason == "loop" and "3x" in guard.describe()
    assert len(answer) <= len(before) + 3 * len(LONG_ROUND)
    once = guard.once(answer)
    assert once.startswith(before) and once.count("not a myth") == 1


def test_a_long_passage_written_twice_in_a_row_goes_on(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not any(guard.feed(piece) for piece in _words(LONG_ROUND * 2 + "and that is all there is to it"))


def _round_of(length):
    """A unit of `length` characters of different words, without a stop."""
    text, n = "", 0
    while len(text) < length:
        text += f"wort{n} "
        n += 1
    return text[:length - 1] + " "


@pytest.mark.parametrize("length", [61, 144, 500])
def test_a_round_of_up_to_five_hundred_characters_stops_at_its_third_round(llm, length):
    unit = _round_of(length)
    guard, answer = _fed(llm, _words(unit * 4))
    assert guard.reason == "loop" and len(answer) == 3 * length
    assert guard.describe() == "the unit %r 3x without a break" % unit


def test_a_round_of_more_than_five_hundred_characters_goes_on(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not any(guard.feed(piece) for piece in _words(_round_of(501) * 4))


def test_a_unit_of_up_to_sixty_characters_has_ten_rounds(llm):
    # Twice the unit is a round of more than sixty characters, and three of
    # them are six of the unit.
    unit = _round_of(31)
    guard, answer = _fed(llm, _words(unit * 12))
    assert answer.count(unit) == 10
    assert guard.describe() == "the unit %r 10x without a break" % unit


def test_a_long_round_of_more_than_twenty_lines_stops_at_its_third_round(llm):
    # The count takes up to twenty segments for a round.
    lines = "".join(f"Zeile {n}\n" for n in range(25))
    guard, answer = _fed(llm, _words(lines * 5))
    assert guard.reason == "loop" and len(answer) == 3 * len(lines)


def test_a_long_round_a_sentence_ends_in_is_left_to_the_count(llm):
    unit = _round_of(80) + "Ende. " + _round_of(40)
    guard, _ = _fed(llm, _words(unit * 5))
    assert guard.reason == "round"


def test_a_long_round_keeps_no_part_of_the_next(llm):
    # Its clause ends in the second round, further on than sixty characters.
    unit = ("the long winding road through the hills and valleys past the old mill "
            "and the rivers, and on ")
    assert _once(llm, "Answer: " + unit * 6) == "Answer: " + unit.strip()


def test_two_long_rounds_stand_once(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard(repeat_limit=2)
    answer = ""
    for piece in _words(LONG_ROUND * 4):
        answer += piece
        if guard.feed(piece):
            break
    assert guard.reason == "loop" and guard.once(answer) == LONG_ROUND.strip()


def test_what_stands_before_a_loop_stays_as_written(llm):
    before = "Dr. Mamani kam am Morgen. Dr. Quispe ging am Abend. "
    assert _once(llm, before + "Kay wasiqa " + UNIT * 12) == before + ONCE


# --- a passage: each one stays at its first place ------------------------------

def test_what_stands_between_the_copies_stays(llm):
    # A passage between other lines stops the answer at its tenth copy.
    between = [f"Line {n} stands between two of the copies." for n in range(1, 10)]
    copies = [SEGMENT, SEGMENT.upper()] * 5
    text = "".join(f"{copy}\n{line}\n" for copy, line in zip(copies, between)) + SEGMENT + "\n"
    assert _once(llm, text) == SEGMENT + "\n" + "\n".join(between)


def test_a_repeated_block_stands_once(llm):
    assert _once(llm, (SEGMENT + " " + SECOND + " ") * 3) == SEGMENT + " " + SECOND


def test_every_sentence_of_a_repeated_block_stands_once(llm):
    assert _once(llm, S + " Inti lluqsimun. " + (S + " " + P + " ") * 3) == \
        S + " Inti lluqsimun. " + P


def test_a_sentence_ending_the_way_the_copy_ends_keeps_its_end(llm):
    first = "Die Kinder spielen im Garten."
    copy = "Die Hunde laufen schnell über die Wiese und bellen."
    assert _once(llm, first + " " + (copy + " ") * 4) == first + " " + copy


def test_what_stands_before_the_first_copy_stays_as_written(llm):
    before = "Bist du da? Ja. Hast du Hunger? Ja. Dann komm. Am 1. Mai blühen die Bäume. Am 1. Juni ernten wir. "
    assert _once(llm, before + (SEGMENT + " ") * 3) == before + SEGMENT


@pytest.mark.parametrize("block", [
    "Dann komm sofort zu uns nach Hause, mein liebes Kind. Bist du da? Ja. Hast du Hunger? Ja.",
    "Dr. Mamani kam am Morgen in das große Haus am Fluss. Dr. Quispe ging am Abend aus dem Haus.",
    "Das Bild zeigt z. B. einen Hund auf der großen Wiese. Daneben steht z. B. eine Katze.",
    "Wir wohnen seit vielen Jahren in der Hauptstraße Nr. 5. Unser Nachbar wohnt gegenüber in Nr. 7.",
])
def test_what_repeats_inside_the_first_round_of_a_block_stays(llm, block):
    assert _once(llm, (block + " ") * 3) == block


@pytest.mark.parametrize("label", ["Übersetzung: ", "**Übersetzung:** "])
def test_a_label_before_the_first_copy_makes_it_a_copy(llm, label):
    sentence = "Das Haus steht in einer Landschaft aus Feldern."
    assert _once(llm, label + sentence + " " + (sentence + " ") * 3) == label + sentence


def test_the_short_first_sentence_of_a_block_stands_once(llm):
    assert _once(llm, ("Wasi. " + S + " ") * 4) == "Wasi. " + S


def test_a_heading_line_of_a_block_stands_once(llm):
    assert _once(llm, ("Runasimipi:\n" + SEGMENT + "\n\n") * 4) == "Runasimipi:\n" + SEGMENT


def test_an_abbreviation_is_no_list_mark(llm):
    sentence = "Dr. Mamani wasinqa hatun pampapi sayan uywakunawan."
    assert _once(llm, (sentence + " ") * 4) == sentence


def test_a_list_mark_goes_with_its_copy(llm):
    # The numbers are list marks and keep nothing apart: the third copy
    # stops the answer.
    assert _once(llm, "".join(f"{i}. {SEGMENT} " for i in range(1, 4))) == "1. " + SEGMENT
    assert _once(llm, "".join(f"{i}. {SEGMENT}\n" for i in range(1, 4))) == "1. " + SEGMENT


def test_a_list_mark_goes_with_a_passage_that_stood_before(llm):
    other = "Chaypi wasi hatun pampapi sayan, uywakunawan puriykachanku."
    assert _once(llm, S + " Inti lluqsimun. " + ("1. " + S + " 2. " + other + " ") * 3) == \
        S + " Inti lluqsimun. 2. " + other


def test_a_short_answer_that_stood_before_stays_in_the_round(llm):
    # Only passages of the length the guard counts are compared.
    block = "Hast du Hunger? Ja. Dann komm sofort zu uns nach Hause, mein liebes Kind."
    assert _once(llm, "Bist du da? Ja. " + (block + " ") * 3) == "Bist du da? Ja. " + block


def test_a_passage_ending_in_a_short_answer_that_stood_before_stays(llm):
    passage = "Ich komme morgen früh zu dir, ganz sicher, ja."
    assert _once(llm, "Bist du da? Ja. " + (passage + " ") * 3) == "Bist du da? Ja. " + passage


# --- a run: its first round, found by its segments ------------------------------

@pytest.mark.parametrize("before, round_", [
    ("Hier ist ein Gedicht:\n\n",
     "Der Wind weht leise, über Felder und Wald\nDie Sonne sinkt, der Abend wird kalt\n\n"),
    ("Übersetzung:\n", "kay wasiqa, hatun pampapi sayan uywakunawan.\n"),
    ("Gern.\n", "die Kinder spielen im Garten hinter dem Haus. Der Hund bellt laut.\n"),
    ("Antwort:\n", "Die Orange, frisch gepresst, enthält viel Vitamin C.\n"),
    ("Mein Vorschlag:\n", "Wenn es regnet, nehmen wir den Bus. Das ist Plan B.\n"),
    ("Gern:\n\n", "Das Haus, das im Feld steht, ist alt.\n\n**Quelle: Wikipedia**\n\n"),
    ("## Übersetzung\n\n", "Kay wasiqa, hatun pampapi sayan uywakunawan\n"),
    ("Code:\n", "        ergebnis = berechne(alle_zeilen, schritt=1)\n"),
    ("Ein Lied:\nWir gehen fort, ganz weit\n",
     "Die Felder liegen still im Licht\nDer Himmel ist grau, ganz weit\n"),
])
def test_a_round_ends_with_its_last_segment(llm, before, round_):
    """Rounds that end in a line break: with no stop, after an abbreviation,
    beginning in lower case, rhyming with the text before."""
    assert _once(llm, before + round_ * 3) == (before + round_).strip()


@pytest.mark.parametrize("before, round_, split", [
    ("Wasser\n", "Das Kind trinkt ein Glas Wasser\n", _words),
    ("Komm her.\n", "Er ruft laut zu seinem Bruder: Komm her.\n", _words),
    ("Seite 7.\n", "Die Antwort steht im Buch auf Seite 7.\n", _words),
    ("Ich gehe. Komm sofort her. ", "Er sagt zu dem Kind: Komm sofort her. ", _words),
    ("تعال هنا.\n", "تنادي الأم ابنها من الحديقة بصوت عال: تعال هنا.\n", _words),
    ("过来。\n", "妈妈在院子里大声地对孩子们喊道：过来。快点过来吃饭吧，饭菜都要凉了。过来。\n", _signs),
])
def test_a_round_that_begins_a_line_or_a_sentence_keeps_its_end(llm, before, round_, split):
    """The text before it ends the way the round ends, and the round still
    begins where its first segment begins."""
    assert _once(llm, before + round_ * 3, split) == (before + round_).strip()


def test_a_round_cut_inside_its_sentence_begins_after_the_sentence_before(llm):
    assert _once(llm, "Bonjour. " + "Il dit : « Viens ici. » " * 8) == "Bonjour. Il dit : « Viens ici. »"


def test_a_round_cut_inside_its_sentence_begins_after_the_line_before(llm):
    assert _once(llm, "Réponse :\n" + "Il dit à son fils : « Viens ici tout de suite. » " * 12) == \
        "Réponse :\nIl dit à son fils : « Viens ici tout de suite. »"


@pytest.mark.parametrize("text, once", [
    ("Ich nehme heute gern die Nummer Nr. 7.\n" * 3, "Ich nehme heute gern die Nummer Nr. 7."),
    ("Ich nehme heute gern die Nummer Nr. 7. " * 3, "Ich nehme heute gern die Nummer Nr. 7."),
    ("".join(f"{i}. Wir treffen uns morgen im Raum Nr. 7.\n" for i in (1, 2, 3)),
     "1. Wir treffen uns morgen im Raum Nr. 7."),
    ("".join(f"The answer is printed in the book on p. {n}.\n" for n in (12, 13, 14)),
     "The answer is printed in the book on p. 12."),
    ("Siehe Kap. 2. " + "Die Lösung steht im Buch auf S. 12. " * 3,
     "Siehe Kap. 2. Die Lösung steht im Buch auf S. 12."),
    ("The answer is printed in the book on p. 12.\nYes.\n" + "The answer is printed in the book on p. 12.\n" * 3,
     "The answer is printed in the book on p. 12.\nYes."),
    ("".join(f"The answer is printed in the book on p. {n}. " for n in (12, 13, 14)),
     "The answer is printed in the book on p. 12."),
    ("".join(f"{i}. Wir treffen uns morgen im Raum Nr. 7. " for i in (1, 2, 3)),
     "1. Wir treffen uns morgen im Raum Nr. 7."),
    ("1. Wir treffen uns morgen im Raum Nr. 7. " * 3, "1. Wir treffen uns morgen im Raum Nr. 7."),
    ("Bitte kommt morgen alle pünktlich zur Schule. Wir treffen uns im Raum Nr. 7. "
     + "Bitte kommt morgen alle pünktlich zur Schule. " * 3,
     "Bitte kommt morgen alle pünktlich zur Schule. Wir treffen uns im Raum Nr. 7."),
])
def test_a_number_after_an_abbreviation_ends_its_round(llm, text, once):
    """A list mark that closes the line of the round goes with the round,
    and goes with a passage that stood already before it."""
    assert _once(llm, text) == once


def test_a_round_reaching_back_into_a_word_begins_where_the_guard_counted_it(llm):
    # The text before ends the way the round ends from inside "Lui" on; a
    # round begun there would end inside "ici".
    once = _once(llm, "Das sagt Lui. » " + "Il dit : « Viens ici. » " * 8)
    assert once.startswith("Das sagt Lui. » Il dit : « Viens ici.")
    assert once.count("Il dit") == 1


def test_a_round_begins_with_all_the_marks_before_it(llm):
    assert _once(llm, "Die Lösung steht im Buch auf S. 12. 1. --- " * 4) == \
        "Die Lösung steht im Buch auf S. 12. 1. ---"


def test_a_list_mark_before_a_copy_that_goes_goes_with_it(llm):
    assert _once(llm, "Die Lösung steht im Buch auf S. 12.\nJa.\n"
                 + "- Die Lösung steht im Buch auf S. 12.\nJa.\n" * 3) == \
        "Die Lösung steht im Buch auf S. 12.\nJa."


@pytest.mark.parametrize("before, round_, kept", [
    ("Ich hoffe, das hilft dir weiter beim Lernen.\n",
     "Die Fotosynthese wandelt Licht in Energie um, und ich hoffe, das hilft dir weiter beim Lernen.\n",
     "Fotosynthese"),
    ("Früher glaubten viele Menschen nicht, die Erde dreht sich um die Sonne.\n",
     "Die Erde dreht sich um die Sonne.\nDas wissen wir heute ganz sicher.\n",
     "\nDie Erde dreht sich um die Sonne."),
])
def test_a_sentence_that_stood_only_inside_another_stays_in_the_round(llm, before, round_, kept):
    assert kept in _once(llm, before + round_ * 3)


def test_a_passage_of_thirty_characters_that_stood_before_goes(llm):
    sentence = "Wir lesen heute ein Buch dazu."
    other = "Der Himmel ist grau über der Scheune."
    assert _once(llm, sentence + "\n" + (sentence + "\n" + other + "\n") * 3) == sentence + "\n" + other


def test_a_number_after_a_kept_passage_stays_with_it(llm):
    assert _once(llm, S + "\n" + (S + " Wir treffen uns morgen im Raum Nr. 7.\n") * 3) == \
        S + "\nWir treffen uns morgen im Raum Nr. 7."


def test_empty_lines_between_the_copies_keep_nothing_apart(llm):
    assert _once(llm, SEGMENT + "\n\n" + SEGMENT + "\n" + SEGMENT + "\n\n" + SEGMENT + "\n") == SEGMENT


def test_a_round_after_a_full_stop_in_lower_case_keeps_its_end(llm):
    assert _once(llm, "Essen. " + "und dann gehen wir nach Hause zum Essen. " * 3) == \
        "Essen. und dann gehen wir nach Hause zum Essen."


def test_two_rounds_keep_the_list_mark_of_the_second_out(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard(repeat_limit=2)
    answer = ""
    for piece in _words("".join(f"{i}. Wir treffen uns morgen im großen Raum. " for i in range(1, 7))):
        answer += piece
        if guard.feed(piece):
            break
    assert guard.once(answer) == "1. Wir treffen uns morgen im großen Raum."


def test_a_rule_written_over_and_over_stands_once(llm):
    rule = "-" * 40
    assert _once(llm, (rule + "\n") * 60) == rule
    assert _once(llm, "Liste:\n1. Apfel und Birne.\n" + "---\n" * 60) == "Liste:\n1. Apfel und Birne.\n---"
    assert _once(llm, "Hallo Welt.\n\n" + "---\n" * 60) == "Hallo Welt.\n\n---"
    assert _once(llm, "Hallo Welt.\n1.\n2.\n" + "---\n" * 60) == "Hallo Welt.\n1.\n2.\n---"


def test_rounds_alike_but_for_their_case_keep_the_first_as_written(llm):
    asked = "Bist du noch da? " * 3
    assert _once(llm, SEGMENT.upper() + " " + asked + (SEGMENT + " " + asked) * 2) == \
        SEGMENT.upper() + " " + asked.strip()
    before = "Bist du da? Ja. Hast du Hunger? "
    assert _once(llm, before + "JA. NEIN. VIELLEICHT. MORGEN WIEDER. "
                 + "Ja. Nein. Vielleicht. Morgen wieder. " * 2) == \
        before + "JA. NEIN. VIELLEICHT. MORGEN WIEDER."


def test_a_passage_of_digits_stands_once(llm):
    counted = "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12."
    assert _once(llm, (counted + " ") * 4) == counted


def test_a_sentence_that_holds_the_passage_is_no_copy_of_it(llm):
    first = "Chaypi kay wasiqa hatun pampapi sayan uywakunawan."
    assert _once(llm, first + " " + S + " Inti lluqsimun. " + (S + " ") * 3) == \
        first + " " + S + " Inti lluqsimun."


def test_the_beginning_of_the_next_copy_goes(llm):
    guard, _ = _fed(llm, [SEGMENT + " " + SECOND + "\n"] * 3)
    assert guard.once((SEGMENT + " " + SECOND + "\n") * 3 + "The hou") == SEGMENT + " " + SECOND
    assert guard.once((SEGMENT + "\n") * 3 + "4.") == SEGMENT


# --- what has no once form, and what stays as written --------------------------

def test_an_answer_the_guard_did_not_stop_has_no_once_form(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    assert not guard.feed("A house. A house. ")
    assert guard.once("A house. A house.") == ""


def test_a_loop_in_the_think_block_leaves_the_answer_as_written(llm):
    mod, _ = llm
    guard = mod.RepetitionGuard()
    for _ in range(3):
        guard.feed_split(SEGMENT + "\n", "", SEGMENT + "\n")
    assert guard.triggered and guard.in_think
    assert guard.once("Wasi.") == "Wasi."


# --- the node: generate() hands the answer on as written, and its once form ---

class _RawTok(_Tok):
    """The same tokenizer, taking a raw prompt as well."""

    def __call__(self, text, return_tensors=None):
        import torch
        t = torch.tensor([self.ids(text.split())])
        return {"input_ids": t, "attention_mask": torch.ones_like(t)}


def _generate(llm, monkeypatch, pieces, thinking=True, raw=False):
    mod, torch = llm
    tok = _RawTok()
    monkeypatch.setattr(mod, "get_built", lambda d: _built(torch, tok, pieces, False))
    monkeypatch.setattr(mod, "_kv_cache_bytes", lambda c, n: 0)
    monkeypatch.setattr(mod, "_on_card", lambda b, r: torch.device("cpu"))
    if raw:
        return mod.generate("Some--Model", prompt="translate this",
                            temperature=0.0, context_tokens=4096)
    return mod.generate("Some--Model", messages=[{"role": "user", "content": "translate this"}],
                        temperature=0.0, context_tokens=4096, enable_thinking=thinking)


def test_the_node_hands_a_looped_answer_on_as_written_and_once(llm, monkeypatch):
    out = _generate(llm, monkeypatch, ["</think>", "\n\n"] + _words("Kay wasiqa " + UNIT * 12))
    assert out["finish_reason"] == "repetition"
    assert out["content"].startswith("Kay wasiqa " + UNIT * 9)
    assert out["once"] == ONCE


def test_a_finished_answer_has_no_once_form(llm, monkeypatch):
    out = _generate(llm, monkeypatch, ["</think>", "\n\n", "Wasi."])
    assert out["finish_reason"] == "stop"
    assert out["once"] == ""


def test_a_raw_completion_has_no_once_form(llm, monkeypatch):
    out = _generate(llm, monkeypatch, [SEGMENT, "\n"] * 4, raw=True)
    assert out["finish_reason"] == "repetition"
    assert out["once"] == ""


def test_a_loop_of_whole_think_blocks_puts_no_reasoning_into_the_once_form(llm, monkeypatch):
    # Thinking switched off, and the model opens and closes its own block
    # over and over: the unit the guard saw spans the block, tags and all.
    out = _generate(llm, monkeypatch, ["<think>Ich ", "darf ", "das ", "nicht ", "sagen.</think>\n"] * 12,
                    thinking=False)
    assert out["finish_reason"] == "repetition"
    assert out["once"] == ""


def test_a_long_round_with_an_empty_think_block_in_it_stands_once(llm, monkeypatch):
    # The unit the guard saw carries the tags; the answer repeats the round
    # without them.
    unit = _round_of(99)
    out = _generate(llm, monkeypatch, (["<think></think>"] + _words(unit)) * 6, thinking=False)
    assert out["finish_reason"] == "repetition"
    assert out["once"] == unit.strip()


def test_a_loop_in_a_block_opened_after_the_answer_keeps_the_answer(llm, monkeypatch):
    answer = "Das Bild zeigt das Haus Nr. 1."
    out = _generate(llm, monkeypatch, _words(answer + "<think>" + "kuyu kanki " * 30), thinking=False)
    assert out["finish_reason"] == "repetition"
    assert out["once"] == answer
    out = _generate(llm, monkeypatch, ["Ok.<think>" + "abcd" * 12], thinking=False)
    assert out["once"] == "Ok."
