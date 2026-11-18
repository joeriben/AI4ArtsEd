"""
The plan card is read on its own.

Why it exists: the plan Together wrote for "Unlikely Constellations"
(2026-11-15) said "Jedes Paar" in three steps. The scenario speaks of the
class; Together had divided the group into pairs itself, because of the queue
at the graphics card, and said so only in the paragraph before the plan. The
plan lies on the board as a card of its own (resona.vue, plan-node), so the
card carried a group that nothing on it introduced. The rule stands in the
tail, which every situation composes, so it holds in the workshop and after it
as well as in planning.

Run: python3 -m pytest devserver/tests/test_resona_plan_card.py -q
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.routes.chat_routes import build_system_prompt


@pytest.mark.parametrize("situation", ["workshop", "consulting", "nachklapp"])
def test_the_plan_card_introduces_what_its_steps_name(situation):
    prompt = re.sub(r"\s+", " ", build_system_prompt(
        context={"resona_mode": True, "resona_situation": situation,
                 "device_id": "test-plan-card"},
        language="de",
    ))
    assert "The card is read on its own, apart from the reply around it" in prompt
    assert ("whatever a step names (a group such as pairs, a material, a term, "
            "a part of a scenario) is introduced inside the block, in the "
            "Zweck/Purpose line or in the step where it first appears") in prompt
    assert ("a choice the plan makes itself, such as dividing the group into "
            "pairs, stands in the block with its reason") in prompt
