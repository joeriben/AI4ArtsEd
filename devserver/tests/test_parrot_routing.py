#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The re-enactment chain's routing table, and the one place it can drift.

The routing table: music and text -> HeartMuLa, music alone -> SA3 Music,
speech alone -> VoxCPM2, neither -> SA3 SFX, and a hand-pick beats all four.

The rankings below are the measured ones from
`testfiles/probe_parrot_routing.py` plus the cases three review passes
constructed to break an earlier version of the rule. This test does not call a
model; it replays rankings through the decision so a change to the rule has to
face them again.
"""
import re
import sys

import pytest

from file_modules import DEVSERVER

sys.path.insert(0, str(DEVSERVER))

from my_app.services import parrot_service as ps  # noqa: E402

FRONTEND = (DEVSERVER.parent / "public" / "ai4artsed-frontend" / "src"
            / "views" / "cover_band.vue")


def ranking(scores):
    return [{"label": label, "score": score} for label, score in scores.items()]


# Measured 2026-08-12 by testfiles/probe_parrot_routing.py, MuQ-MuLan, top of
# the list; the full rankings are in that script's output.
MEASURED = {
    "brown noise": ranking({
        "no voice at all": 0.544, "noise, not music": 0.514,
        "humming without words": 0.427, "metal": 0.406, "throat singing": 0.404,
        "a voice speaking, not singing": 0.22, "silence": 0.31,
    }),
    "sung pop": ranking({
        "pop song": 0.588, "a voice speaking, not singing": 0.389,
        "several voices singing together": 0.349, "carnatic vocal music": 0.293,
        "sad and slow": 0.269, "no voice at all": 0.24, "noise, not music": 0.19,
        "silence": 0.13,
    }),
    "german speech": ranking({
        "a voice speaking, not singing": 0.592, "a single voice singing alone": 0.518,
        "several voices singing together": 0.515, "no voice at all": 0.509,
        "hip hop": 0.466, "noise, not music": 0.393, "silence": 0.229,
    }),
    "synth chords": ranking({
        "hip hop": 0.377, "calm and quiet": 0.347, "humming without words": 0.293,
        "no voice at all": 0.283, "synthesizer": 0.264,
        "a voice speaking, not singing": 0.21, "a single voice singing alone": 0.19,
        "noise, not music": 0.18, "silence": 0.12,
    }),
}

# Constructed by the review passes against an earlier rule, each one a case that
# routed to the wrong machine then.
CONSTRUCTED = {
    "a-cappella choir": ranking({
        "several voices singing together": 0.58, "a single voice singing alone": 0.44,
        "carnatic vocal music": 0.41, "classical orchestra": 0.39, "folk song": 0.37,
        "a voice speaking, not singing": 0.33, "throat singing": 0.30,
        "a clean studio recording": 0.28, "happy and upbeat": 0.26,
        "silence": 0.11, "noise, not music": 0.09, "no voice at all": 0.05,
    }),
    "instrumental jazz trio": ranking({
        "jazz": 0.60, "solo piano": 0.52, "drum kit": 0.44,
        "a voice speaking, not singing": 0.35, "a clean studio recording": 0.33,
        "no voice at all": 0.30, "calm and quiet": 0.29,
        "a single voice singing alone": 0.20, "several voices singing together": 0.14,
        "silence": 0.10, "noise, not music": 0.08,
    }),
    "words in a quiet room": ranking({
        "silence": 0.31, "a voice speaking, not singing": 0.30, "calm and quiet": 0.28,
        "a clean studio recording": 0.22, "noise, not music": 0.20,
        "solo piano": 0.15, "folk song": 0.12, "no voice at all": 0.11,
    }),
}


@pytest.mark.parametrize("case,rank,transcription,expected", [
    # what was heard              ranking                 transcriber wrote        machine
    ("brown noise",   MEASURED["brown noise"],   "The train is now arriving", ps.SFX_CONFIG),
    ("sung pop",      MEASURED["sung pop"],      "The sun creeps in",         ps.SONG_CONFIG),
    ("german speech", MEASURED["german speech"], "Guten Tag, dies ist",       ps.SPEECH_CONFIG),
    ("synth chords",  MEASURED["synth chords"],  "××××",  ps.MUSIC_CONFIG),
    # A choir has no instrument in it. If singing counted against music, this
    # would be spoken back by a TTS — on a page that asks people to sing.
    ("a-cappella choir", CONSTRUCTED["a-cappella choir"], "wir singen", ps.SONG_CONFIG),
    # The transcriber invents words for anything, and the speaking label sits in
    # this model's cross-category leakage. In music the words question is asked
    # of the SINGING labels, which is what keeps this one instrumental.
    ("instrumental jazz trio", CONSTRUCTED["instrumental jazz trio"], "you", ps.MUSIC_CONFIG),
    # Top-1 "silence" settles the music question, not the words question.
    ("words in a quiet room", CONSTRUCTED["words in a quiet room"],
     "könnt ihr mich hören", ps.SPEECH_CONFIG),
    # No words at all is the empty-room case the page invites, and the table
    # sends it to the sound model.
    ("speech, nothing transcribed", MEASURED["german speech"], "", ps.SFX_CONFIG),
    ("speech, only whitespace", MEASURED["german speech"], "   \n", ps.SFX_CONFIG),
])
def test_table(case, rank, transcription, expected):
    assert ps.resolve_singer(rank, transcription) == expected, case


@pytest.mark.parametrize("unusable", [
    None,
    [],
    [{"label": "pop song", "similarity": 0.62}],   # a shape without "score"
    [{"score": 0.5}],                              # ...and one without "label"
    "not a list at all",
])
def test_unusable_ranking_falls_back_to_the_declared_default(unusable):
    """Never route from the other ranking: CLAP scored the speaking label
    -0.118 on clean speech while giving jazz .277, so it does not degrade the
    answer, it inverts it. The song config is what ran here before the table."""
    assert ps.resolve_singer(unusable, "guten tag") == ps.SONG_CONFIG


@pytest.mark.parametrize("picked", [
    "", "stableaudio_open", "../../etc/passwd", "HEARTMULA_STANDARD",
    "keys", "__class__", None, "  heartmula_standard  ",
])
def test_a_pick_that_is_not_one_is_not_an_error(picked):
    """`?config=` is whatever the URL carried. An unknown value is not a pick."""
    got = ps.resolve_singer(MEASURED["sung pop"], "la la", picked)
    assert got in ps.SINGER_NAMES


@pytest.mark.parametrize("picked", list(dict(ps.SOUND_CONFIGS)))
def test_a_hand_pick_beats_the_table(picked):
    assert ps.resolve_singer(MEASURED["sung pop"], "la la", picked) == picked


def test_every_route_lands_on_a_config_that_exists():
    out = DEVSERVER / "schemas" / "configs" / "output"
    for config_id, _ in ps.SOUND_CONFIGS:
        assert (out / f"{config_id}.json").is_file(), config_id


def test_the_page_offers_exactly_what_the_chain_can_choose():
    """The node names the machines; parrot_service picks one. If the two lists
    drift, the page either hides a machine that runs or offers one that cannot,
    and a hand-picked id the backend does not know silently becomes auto-routing
    while the button still says it was chosen by hand."""
    source = FRONTEND.read_text(encoding="utf-8")
    block = re.search(r"const SINGERS = \[(.*?)\n\]", source, re.S)
    assert block, "SINGERS array not found in cover_band.vue"
    on_page = re.findall(r"\{\s*id:\s*'([^']+)',\s*label:\s*'([^']+)'\s*\}",
                         block.group(1))
    assert on_page == list(ps.SOUND_CONFIGS), (
        f"cover_band.vue offers {on_page}, parrot_service routes to "
        f"{list(ps.SOUND_CONFIGS)}"
    )


def test_the_labels_the_rule_compares_are_labels_the_ranker_can_return():
    """The rule reads label strings. A vocabulary rename would leave every
    comparison silently returning None instead of raising."""
    from my_app.services.local_media_weights import music_tag_vocabulary
    vocabulary = set(music_tag_vocabulary())
    named = (set(ps._VOICE_LABELS) | {ps._NO_VOICE_LABEL}
             | set(ps._NOT_MUSIC_LABELS) | ps._NEITHER_SIDE)
    missing = [label for label in sorted(named) if label not in vocabulary]
    assert not missing, f"not in music_tag_vocabulary: {missing}"
