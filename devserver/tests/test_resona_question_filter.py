"""
Tests for the deterministic delivery filter — the choose-one closing question
never reaches the group.

Operator decision 2026-07-31: three prompt-level attempts at three different
causes each softened the move and none stopped it, so the guarantee moves out
of the prompt and into the code. Resona may write the sentence; it is cut
before delivery, and the next turn is told the count, never the sentence.

What is enforced:
  - both conditions required: a question mark AND either a volition ask or a
    disjunction. Curiosity questions survive.
  - every interface language, not just German (ten locales ship).
  - the removed sentence never comes back through her own transcript.
  - the notice carries a count and no fragment of what was cut.
  - the notice is consumed, so it is said once.
  - markdown structure survives; a paragraph that WAS the question disappears
    instead of leaving a hole.

Run: python3 -m pytest devserver/tests/test_resona_question_filter.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services.resona_question_filter import (
    filter_reply,
    is_offered_choice,
    note_removed,
    take_notice,
)


# --- the move, in each of the ten interface languages ----------------------
OFFERED = [
    "Möchtet ihr das lieber mit eigenen Bildern probieren?",
    "Soll ich das einmal laufen lassen?",
    "Willst du den Übergang als Mischung oder als Zeit?",
    "Would you like me to run it once?",
    "Shall we start with the fusion or with the canvas?",
    "Voulez-vous commencer par la fusion ?",
    "¿Prefieres empezar por la fusión o por el lienzo?",
    "Bunu görsellerle mi yoksa kelimelerle mi denemek istersiniz?",
    "융합으로 시작할까요, 아니면 캔버스로 시작할까요?",
    "Чи хочете почати зі злиття?",
    "Искате ли да започнем със сливането?",
    "هل تريد أن نبدأ بالدمج؟",
    "האם אתם רוצים להתחיל עם המיזוג?",
    # disjunction alone is enough, without any asking verb
    "Der Übergang als Mischung, als Zeit, oder als selbstgebauter Weg?",
]

# --- what must survive: questions that neither ask for a decision nor offer --
KEPT = [
    "Was passiert, wenn das Modell den Begriff behält?",
    "Wo genau sitzt die Grenze zwischen Rauschen und Form?",
    "What does the model keep when a concept is subtracted?",
    "Die Bildfusion nimmt bis zu drei Bilder und ersetzt damit den Textprompt.",
    "Es gibt Bildfusion, Canvas oder das Latent Lab.",  # disjunction, no question
]


@pytest.mark.parametrize("sentence", OFFERED)
def test_offered_choices_are_recognised(sentence):
    assert is_offered_choice(sentence), sentence


@pytest.mark.parametrize("sentence", KEPT)
def test_other_sentences_survive(sentence):
    assert not is_offered_choice(sentence), sentence


def test_offered_choice_does_not_reach_the_group():
    reply = (
        "Die Bildfusion nimmt bis zu drei Bilder.\n\n"
        "Soll ich das einmal an eurem Motiv zeigen?"
    )
    delivered, removed = filter_reply(reply)
    assert removed == 1
    assert "Soll ich" not in delivered
    assert "Die Bildfusion nimmt bis zu drei Bilder." in delivered


def test_structure_survives_and_leaves_no_hole():
    reply = (
        "Erster Absatz mit einem Satz.\n\n"
        "Möchtet ihr A oder B?\n\n"
        "Dritter Absatz."
    )
    delivered, removed = filter_reply(reply)
    assert removed == 1
    assert delivered == "Erster Absatz mit einem Satz.\n\nDritter Absatz."


def test_only_the_question_leaves_its_paragraph():
    reply = "Das Latent Lab öffnet den Vorgang. Möchtet ihr das sehen? Es braucht Advanced Mode."
    delivered, removed = filter_reply(reply)
    assert removed == 1
    assert "Möchtet ihr" not in delivered
    assert "Das Latent Lab öffnet den Vorgang." in delivered
    assert "Es braucht Advanced Mode." in delivered


def test_empty_and_clean_replies_are_untouched():
    assert filter_reply("") == ("", 0)
    clean = "Die Bildfusion nimmt bis zu drei Bilder.\n\nDas Latent Lab öffnet den Vorgang."
    assert filter_reply(clean) == (clean, 0)


# --- the notice ------------------------------------------------------------
def test_notice_carries_a_count_and_no_fragment_of_what_was_cut():
    device = "test-device-notice"
    take_notice(device)  # drain
    reply = "Ein Satz. Soll ich das einmal an eurem Motiv zeigen?"
    delivered, removed = filter_reply(reply)
    note_removed(device, removed)
    notice = take_notice(device)
    assert "One sentence" in notice
    for fragment in ("Soll ich", "Motiv", "zeigen"):
        assert fragment not in notice, f"the notice repeats {fragment!r}"


def test_notice_is_said_once():
    device = "test-device-once"
    take_notice(device)
    note_removed(device, 2)
    first = take_notice(device)
    assert "2 sentences" in first
    assert take_notice(device) == ""


def test_no_notice_without_a_cut():
    assert take_notice("test-device-quiet") == ""
    assert take_notice(None) == ""


# --- abbreviation dots (live miss 2026-08-05) ------------------------------
def test_abbreviation_dots_do_not_shield_the_move():
    """gemini-3.6-flash closed a planning turn with exactly the banned shape.
    is_offered_choice saw it; filter_reply did not, because "z. B." split the
    sentence and no fragment held both a marker and the question mark."""
    reply = (
        "Jede Gruppe zeigt genau ein Bild.\n\n"
        "Soll die Reihe eher analytisch-kritisch weitergehen (z. B. Klischees, "
        "Filterblasen und Sehgewohnheiten untersuchen) oder "
        "gestalterisch-experimentell (z. B. hybride Porträts aus eigenen "
        "analogen Fotos/Zeichnungen und KI-Überarbeitungen)?"
    )
    delivered, removed = filter_reply(reply)
    assert removed == 1
    assert "Soll die Reihe" not in delivered
    assert "Jede Gruppe zeigt genau ein Bild." in delivered


@pytest.mark.parametrize("reply", [
    "Der Vergleich hält alles fest und bewegt eine Sache (z. B. die Sprache).",
    "Das Latent Lab braucht Advanced Mode, vgl. die Sicherheitseinstellungen.",
    "Es sind ca. 25 Schritte, u. a. die groben Farbfelder zuerst.",
    "Cho et al. zählen die Verteilung über Berufe hinweg aus.",
])
def test_abbreviations_survive_untouched(reply):
    """Masking must be invisible: nothing removed, nothing rewritten."""
    assert filter_reply(reply) == (reply, 0)


# --- delivered as written --------------------------------------------------
@pytest.mark.parametrize("reply", [
    # a dot inside a version, a file name, a time: no sentence ends there
    "SD 3.5 macht scharfe Bilder. FLUX.2 ist neuer. Was meint ihr?",
    "Das Bild heisst bild.png und steht da seit 14.30 Uhr.",
    # a quoted question before a comma is part of its sentence
    "Schau dir das Bild an. \u201eWarum?\u201c, fragt jemand in der Runde.",
    # the writer's own spacing stays
    "Zwei Saetze.  Mit zwei Leerzeichen dazwischen.",
    "Nun\u2026ja. So ist das.",
])
def test_delivered_byte_identical_where_nothing_is_removed(reply):
    """Since 2026-09-18 the voice speaks the stream's sentences as they
    arrive; a delivered text cut or spaced differently from the stream sent
    the voice back to the first sentence. Where nothing is removed, the line
    is delivered as written."""
    assert filter_reply(reply) == (reply, 0)


def test_removal_leaves_the_rest_as_written():
    reply = "Satz eins. M\u00f6chtet ihr A oder B? Satz drei."
    assert filter_reply(reply) == ("Satz eins. Satz drei.", 1)
