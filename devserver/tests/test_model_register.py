#!/usr/bin/env python3
"""What a model IS: the register behind the card beside a model field.

The card exists so that a field naming a model also says who made it, when, and
whether its weights are open. Everything it shows is a factual claim, so the
tests here are about the register never saying more than it knows: an entry
carries the page it was read off, a lineup names only models the register can
speak about, and a word for the reader is never stored in it.

Run: python3 -m pytest devserver/tests/test_model_register.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.routes import model_register_routes as R

REGISTER = json.loads(R._REGISTER_FILE.read_text(encoding='utf-8'))
MODELS = REGISTER['models']
LINEUPS = REGISTER['interception_lineups']

OPENNESS = {'open', 'weights', 'closed'}


class TestEveryEntryCarriesItsSource:
    """A fact without a page it was read off is a fact remembered.

    The one failure this file exists to prevent is an entry written from what a
    model name sounds like. A url does not prove the fact, but it names where
    the next reader checks it, and an entry that cannot name one was not read.
    """

    @pytest.mark.parametrize('key', sorted(MODELS))
    def test_it_names_a_page(self, key):
        src = MODELS[key].get('source', '')
        assert src.startswith('https://'), f'{key} carries no source'

    @pytest.mark.parametrize('key', sorted(MODELS))
    def test_it_says_nothing_it_cannot_say(self, key):
        entry = MODELS[key]
        assert set(entry) <= {'maker', 'year', 'openness', 'params_b', 'medium', 'source'}, entry
        # The one mark the register carries besides the facts: an image network,
        # which shows its count without a size class (useModelRegister.sizeClass).
        if 'medium' in entry:
            assert entry['medium'] == 'image', entry
        if 'openness' in entry:
            assert entry['openness'] in OPENNESS, entry['openness']
        if 'year' in entry:
            assert 2000 < entry['year'] < 2100, entry['year']
        # A size that is not known is null, never zero and never absent: the
        # card tells 'no figure published' from 'nothing recorded' by it, and a
        # zero would print as a model of no size at all.
        if 'params_b' in entry and entry['params_b'] is not None:
            assert entry['params_b'] > 0, entry


class TestTheRegisterHoldsNoWordsForTheReader:
    """Openness is a STEP here, and the surface holds the word for it.

    A word in the register would be one language's word, and the same entry
    serves ten. This is the same rule the platform applies to every reason it
    hands a surface.
    """

    @pytest.mark.parametrize('key', sorted(MODELS))
    def test_no_sentence_stands_in_an_entry(self, key):
        for field, value in MODELS[key].items():
            if field in ('source',) or not isinstance(value, str):
                continue
            assert len(value.split()) <= 4, f'{key}.{field} reads as prose: {value}'


class TestALineupOnlySpeaksOfModelsTheRegisterKnows:
    """A lineup member without an entry is a field with no card.

    The lineups and the entries live in the same file, so they can drift apart
    in one edit — a model added to a lineup and not to the register looks right
    in the list and says nothing when it is asked.
    """

    @pytest.mark.parametrize('name', sorted(LINEUPS))
    def test_every_member_has_an_entry(self, name):
        missing = [m for m in LINEUPS[name] if m not in MODELS]
        assert not missing, f'{name} names models the register does not hold: {missing}'

    @pytest.mark.parametrize('name', sorted(LINEUPS))
    def test_a_lineup_compares_at_least_two(self, name):
        assert len(LINEUPS[name]) >= 2, f'{name} compares nothing'

    @pytest.mark.parametrize('name,allowed', [
        ('openWeights', {'open', 'weights'}),
        ('closedWeights', {'closed'}),
    ])
    def test_a_lineup_named_after_openness_holds_what_it_names(self, name, allowed):
        """These two names are claims about every model standing in them.

        The rows are read as the difference the name states, so one model on the
        wrong side puts a published model under „closed weights" and nothing on
        the surface says otherwise. A lineup this installation has dropped is
        skipped rather than asserted about.
        """
        members = LINEUPS.get(name)
        if members is None:
            pytest.skip(f'{name} is not in this register')
        steps = {MODELS[m].get('openness') for m in members}
        assert steps <= allowed, f'{name}: {steps}'


class TestAnIdFindsItsEntryWhicheverProviderItCameThrough:
    """The same model reaches this installation through whichever provider is
    configured. A key per provider would go silent the moment that changes."""

    @pytest.mark.parametrize('given', [
        'glm-5.3',
        'mammouth/glm-5.3',
        'openrouter/~z-ai/glm-5.3',
    ])
    def test_the_prefix_comes_off(self, given):
        assert R.bare_name(given) == 'glm-5.3'
        assert R.facts_for(given, REGISTER) is MODELS['glm-5.3']

    def test_a_model_it_does_not_hold_answers_nothing(self):
        assert R.facts_for('a-model-nobody-installed', REGISTER) is None

    def test_an_empty_id_answers_nothing(self):
        assert R.facts_for('', REGISTER) is None


class TestAnUnreadableRegisterCostsTheCardsAndNothingElse:
    def test_it_answers_empty_rather_than_raising(self, monkeypatch, tmp_path):
        monkeypatch.setattr(R, '_REGISTER_FILE', tmp_path / 'not-there.json')
        assert R.load_register() == {}
        assert R.facts_for('glm-5.3') is None


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q']))
