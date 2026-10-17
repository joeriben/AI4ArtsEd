"""§86a fast filter: phrase terms match word for word, at word boundaries.

The filter searches terms from six characters up with Levenshtein tolerance, so
that deliberate obfuscation ("Ha1kenkreuz") is still caught. Across a phrase that
tolerance used to run over the spaces, and two edits are enough to turn a
one-letter word into any other: the term "ss symbol" matched the ordinary phrase
"a symbol" and hard-blocked every English text containing it — at kids and youth
a hard block, so precisely the young were cut off. What blocked
the run that surfaced this was a machine reading of a child's drawing: "the bird
as a symbolic companion".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas.engine.stage_orchestrator import fast_filter_bilingual_86a as f86a


def hit(text, lang='en'):
    found, terms = f86a(text, lang)
    return found, terms


class TestNoFalsePositives:
    def test_a_symbol_is_not_an_ss_symbol(self):
        found, terms = hit('The bird as a symbolic companion or observer.')
        assert not found, terms

    def test_plain_symbol_sentence(self):
        found, terms = hit('The sailboat is a symbol of travel and the bird a symbol of freedom.')
        assert not found, terms

    def test_his_flag_is_not_is_flag(self):
        found, terms = hit('He raised his flag on the beach.')
        assert not found, terms

    def test_raw_terror_is_not_raf_terror(self):
        found, terms = hit('The film shows raw terror in the faces of the crowd.')
        assert not found, terms

    def test_german_reading_of_a_drawing(self):
        found, terms = hit('Der Vogel ist ein Symbol der Freiheit, das Segelboot ein Symbol der Reise.', 'de')
        assert not found, terms


class TestStillCaught:
    def test_ss_symbol(self):
        found, terms = hit('a photo of an ss symbol on a wall')
        assert found and 'ss symbol' in terms, terms

    def test_ss_symbol_hyphenated(self):
        found, terms = hit('ein Foto mit SS-Symbol an der Wand', 'de')
        assert found, terms

    def test_ss_symbol_obfuscated(self):
        found, terms = hit('a photo of an ss symb0l on a wall')
        assert found, terms

    def test_plural_of_a_phrase_term(self):
        found, terms = hit('photographs of concentration camps in 1945')
        assert found and 'concentration camp' in terms, terms

    def test_singular_of_a_plural_phrase_term(self):
        found, terms = hit('a drawing of an ss rune')
        assert found and 'ss runes' in terms, terms

    def test_sieg_heil(self):
        found, terms = hit('the crowd shouting sieg heil')
        assert found and 'sieg heil' in terms, terms

    def test_single_word_term_still_fuzzy(self):
        # Unchanged path: single words keep their obfuscation tolerance.
        found, terms = hit('ein ha1kenkreuz an der Wand', 'de')
        assert found, terms

    def test_swastika(self):
        found, terms = hit('a swastika painted on the door')
        assert found and 'swastika' in terms, terms
