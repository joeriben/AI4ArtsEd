#!/usr/bin/env python3
"""The lines of a checklist preset stand ONCE, and they travel to the surface.

Two presets put the same VisionReward properties at their two poles, and their
contexts spell each property out as one line. What a surface sets has to be
EXACTLY the line the writing model reads out of the preset itself -- otherwise a
comparison runs between a wording and a paraphrase of it, and the difference is
an artefact of this repository rather than of what was compared.

So the lines are data as well as prose: `meta.dimension_lines`, keyed by the
dimension. Since the rebuild of 2026-09-04 the surface composes its line from
`meta.dimensions_verbatim` for the step its axis stands at, and these lines are
what that composition yields at the outermost step -- which is exactly why prose
and data have to keep agreeing. They stand in ONE wording — the source's, untranslated — and that
wording stands in the context of every language the preset speaks. The tests
below hold prose and data together in BOTH directions -- every stored line stands verbatim in the
context it was taken from, and the context carries no dimension line the data
does not -- and the keys are exactly the keys of `meta.dimensions_verbatim`, in
that order, which is the order a checklist is read in.

The last test is the route: a config that carries the lines hands them out, a
config that carries none answers exactly as it did before.

Nothing is called. No model, no network.

Run: python3 -m pytest devserver/tests/test_dimension_lines.py -q
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R

CONFIGS = Path(__file__).resolve().parents[1] / "schemas" / "configs" / "interception"

# The two poles of one checklist. Named, not discovered: a test that looked for
# "every config with dimension_lines" would go green on the day both files are
# gone.
POLES = ("aesthetic", "anti_aesthetic")

# A config on the same list that carries no lines, so the route's answer can be
# shown to be additive rather than universal.
WITHOUT_LINES = "bauhaus"


# What separates a dimension's key from what it says. The presets write it with
# spaces around it, and it is what makes a key readable back off a line.
SEPARATOR = " \u2014 "


def _preset(name):
    return json.loads((CONFIGS / f"{name}.json").read_text(encoding="utf-8"))


def _stands_as_a_whole_line(context, line):
    """Whether the line is one of the context's OWN lines, not merely inside one.

    A substring test goes green where the context's line has GROWN under the data
    ("REALISM -- the details are realistic and razor sharp" against a stored
    "REALISM -- the details are realistic"): the writing model then reads more than
    the data holds, which is exactly the drift this file exists to catch.
    """
    return line in [row.strip() for row in context.split("\n")]


def _key_of(line):
    """The dimension a line names: everything before the first separator.

    Read whole rather than as a prefix. `line.startswith(f"{key} ")` cannot tell
    COLOUR from COLOUR QUALITY, so a COLOUR entry carrying the COLOUR QUALITY line
    passed -- and the data would then hold a line for a property it does not name.
    """
    head, sep, _ = line.partition(SEPARATOR)
    return head if sep else ""


def _paragraphs(context):
    """The context as its blocks: runs of non-empty lines, stripped."""
    out, current = [], []
    for row in context.split("\n"):
        row = row.strip()
        if row:
            current.append(row)
        elif current:
            out.append(current)
            current = []
    if current:
        out.append(current)
    return out


def _dimension_lines_in(context, stored):
    """The context's checklist BLOCK, whole, as its own lines.

    Read as a block rather than by the look of a line. A recogniser that decides
    from the shape of a line ("a key in capitals, then the separator", "a key of
    one or two words") has to be told what a key may look like, and it is wrong
    twice over: a dimension whose key it did not foresee stands in the prose
    unseen -- which is exactly the drift the reverse check exists for -- and a
    sentence of the prose that happens to fit is read as a dimension the data
    lacks. The checklist stands in the context as one block between blank lines,
    so the block is what is compared: every line of it, in its order, against the
    stored lines. Anything that joins that block, whatever it looks like, is
    seen; nothing outside it is mistaken for a line.

    A stored line that stands in NO block, or in more than one, returns the empty
    list here and fails the comparison -- which is what it should do.
    """
    blocks = [p for p in _paragraphs(context) if any(line in p for line in stored)]
    return blocks[0] if len(blocks) == 1 else []


@pytest.mark.parametrize("name", POLES)
class TestTheLinesAreTheContext:
    def test_every_line_stands_verbatim_in_the_context(self, name):
        """What the data says is what the model reads -- character for character."""
        preset = _preset(name)
        lines = preset["meta"]["dimension_lines"]
        assert set(preset["context"]) >= {"en", "de"}, (
            f"{name}: a pole speaks en and de; the checklist stands in the "
            f"context of each of them"
        )
        for lang, context in preset["context"].items():
            for key, line in lines.items():
                assert _stands_as_a_whole_line(context, line), (
                    f"{name}: the line for {key} is not a line of the {lang} "
                    f"context of the preset -- prose and data have drifted apart"
                )

    def test_the_context_sets_nothing_the_data_does_not(self, name):
        """The other direction: the model reads no requirement the data lacks.

        The check above runs from the data into the prose, so a context that KEEPS
        every stored line and grows one BESIDE it goes green on it -- a second, sharper
        REALISM line, or a whole SHARPNESS the data never heard of. The writing model
        then reads a property the data does not carry, and the difference between the
        two rows is again an artefact of this repository.

        So the two sides are the same lines: as many, and the same text.
        """
        preset = _preset(name)
        stored = list(preset["meta"]["dimension_lines"].values())
        for lang, context in preset["context"].items():
            assert _dimension_lines_in(context, stored) == stored, (
                f"{name}: the checklist block of the {lang} context and the "
                f"stored lines are not the same lines, or not in the same order "
                f"-- prose and data have drifted apart"
            )

    def test_the_keys_are_the_checklist_in_its_order(self, name):
        """One entry per dimension, in the order the checklist is read in."""
        preset = _preset(name)
        keys = [entry["key"] for entry in preset["meta"]["dimensions_verbatim"]]
        assert list(preset["meta"]["dimension_lines"]) == keys, name

    def test_a_line_names_its_own_dimension(self, name):
        """The line carries the key it is filed under, as it does on the surface."""
        preset = _preset(name)
        for key, line in preset["meta"]["dimension_lines"].items():
            assert _key_of(line) == key, f"{name}/{key}: {line!r}"


def test_the_two_checks_catch_the_drift_they_are_for():
    """The checks above, put against the two mutations a looser test let through.

    Both were live until 2026-09-04: the line was looked for as a SUBSTRING of the
    context, and the key was read as a PREFIX of the line.
    """
    context = (
        "Clarity \u2014 very clear\n"
        "Detail realism \u2014 realistic and razor sharp\n"
    )
    assert _stands_as_a_whole_line(context, "Clarity \u2014 very clear")
    # The context's line has grown while the data kept the short one.
    assert not _stands_as_a_whole_line(context, "Detail realism \u2014 realistic")

    assert _key_of("Clarity \u2014 very clear") == "Clarity"
    # "Color Aesthetic"'s line filed under "Color": a prefix test cannot see it.
    assert _key_of("Color Aesthetic \u2014 beautiful colors") != "Color"
    # And a line with no separator at all names no dimension.
    assert _key_of("Color Brightness bright") == ""


def test_the_reverse_check_catches_what_only_the_prose_says():
    """The drift a one-way check cannot see, put against the reverse one.

    Both contexts below keep every stored line, so reading from the data into the prose
    finds everything it looks for and goes green -- while the model reads one property
    more than the instrument can set.
    """
    stored = [
        "Clarity \u2014 very clear",
        "Detail realism \u2014 realistic",
    ]
    frame_before = "Keep what the INPUT is about \u2014 choose two of these.\n\n"
    frame_after = "\n\nWrite this into ONE description \u2014 no commentary.\n"
    intact = frame_before + "\n".join(stored) + frame_after
    assert _dimension_lines_in(intact, stored) == stored

    # The stored line kept, and a sharper one added beneath it.
    grown = frame_before + "\n".join(
        stored + ["Detail realism \u2014 realistic and razor sharp"]
    ) + frame_after
    assert all(_stands_as_a_whole_line(grown, line) for line in stored)
    assert _dimension_lines_in(grown, stored) != stored

    # A dimension that stands in the prose alone -- and one whose key no
    # shape-guessing recogniser would have foreseen: three words, and a word that
    # is not English.
    for unforeseen in (
        "Composition and framing \u2014 balanced",
        "Sch\u00e4rfe \u2014 sehr scharf",
        "Sub-object pairing \u2014 coordinated",
    ):
        added = frame_before + "\n".join(stored + [unforeseen]) + frame_after
        assert all(_stands_as_a_whole_line(added, line) for line in stored)
        assert _dimension_lines_in(added, stored) != stored, unforeseen

    # And the prose AROUND the block is no dimension line, however it is built --
    # including a sentence of two words before the separator, which a
    # shape-guessing recogniser read as a dimension.
    for prose in (
        "You answer the INPUT as a PHOTOGRAPH. It is a photograph throughout "
        "\u2014 taken with a camera.",
        "Note \u2014 no justification, no commentary.",
        "Above all \u2014 keep what the INPUT is about.",
    ):
        assert _dimension_lines_in(
            frame_before + "\n".join(stored) + "\n\n" + prose + "\n", stored
        ) == stored, prose


def test_the_block_is_read_in_the_order_the_data_is_written_in():
    """The prose order IS the data order -- the checklist is read in one order."""
    for name in POLES:
        preset = _preset(name)
        stored = list(preset["meta"]["dimension_lines"].values())
        for context in preset["context"].values():
            assert _dimension_lines_in(context, stored) == stored, name


def _instrument():
    """The surface's own source, so the constants it draws with can be read."""
    return (
        Path(__file__).resolve().parents[2]
        / "public/ai4artsed-frontend/src/views/latent_lab/aesthetic_poles.vue"
    ).read_text(encoding="utf-8")


def _ranks(entry, side):
    """Whether a pole's own word stands on that pole's side of the neutral one.

    The rule the instrument applies, in the same terms: side -1 is the pole
    whose words stand ABOVE the neutral one in the source's scale.
    """
    scale = entry.get("visionreward_option_scale")
    neutral = entry.get("visionreward_option_neutral")
    option = entry.get("visionreward_option")
    if not isinstance(scale, list) or neutral not in scale or option not in scale:
        return False
    if side < 0:
        return scale.index(option) < scale.index(neutral)
    return scale.index(option) > scale.index(neutral)


def _rankable_keys():
    """The properties BOTH poles can be ranked on, in checklist order."""
    good, anti = (
        {e["key"]: e for e in _preset(n)["meta"]["dimensions_verbatim"]} for n in POLES
    )
    return [
        key
        for key, entry in good.items()
        if _ranks(entry, -1) and key in anti and _ranks(anti[key], 1)
    ]


def test_enough_properties_can_be_ranked():
    """The checklist is the presets' data, and a handle can be put on it.

    The instrument draws nothing: every property whose scale
    both poles print alike carries a handle, and the surface says so when none
    does (`tooFewProperties`). What has to hold is that an edit to the scales
    cannot quietly empty the checklist -- the pool IS the presets. Ten of the
    eleven are rankable; `Main object` stands out because its scale prints
    `prominent` at both ends (`meta.scale_note`).
    """
    pool = _rankable_keys()
    assert len(pool) >= 10, pool


def test_every_property_says_which_word_the_ranking_counts_from():
    """`visionreward_option_neutral`, and it stands in its own scale.

    The steps the axis swings by are counted from that word, and it cannot be
    worked out: `Detail realism` runs realistic - neutral - unrealistic - very
    unrealistic - greatly unrealistic, where the neutral word is the second of
    five and not the middle one. A missing or a misspelt one drops its property
    out of every draw in silence.
    """
    for name in POLES:
        for entry in _preset(name)["meta"]["dimensions_verbatim"]:
            neutral = entry.get("visionreward_option_neutral")
            assert isinstance(neutral, str) and neutral, (name, entry["key"])
            assert neutral in entry["visionreward_option_scale"], (
                name,
                entry["key"],
                neutral,
            )


def test_the_frame_keeps_one_place_for_the_drawn_properties():
    """`{PROPERTIES}`, once, in every language the preset speaks.

    The surface writes the drawn lines into the frame in place of that word. A
    frame without it runs as prose with no properties in it, and both rows
    still return pictures -- so the loss would show neither on the surface nor
    in the record.
    """
    for name in POLES:
        preset = _preset(name)
        frame = preset["meta"].get("context_frame")
        assert isinstance(frame, dict) and frame, name
        assert set(frame) == set(preset["context"]), name
        for lang, text in frame.items():
            assert text.count("{PROPERTIES}") == 1, (name, lang)


def test_the_two_poles_carry_the_same_dimensions():
    """The comparison the instrument draws needs both poles to say the same
    things -- otherwise a drawn property would set a line in one row and nothing
    in the other."""
    a, b = (_preset(n)["meta"] for n in POLES)
    assert [e["key"] for e in a["dimensions_verbatim"]] == [
        e["key"] for e in b["dimensions_verbatim"]
    ]
    assert list(a["dimension_lines"]) == list(b["dimension_lines"])
    # And they are at DIFFERENT poles: an identical line in both would make the
    # two halves of the instrument one.
    for key in a["dimension_lines"]:
        assert a["dimension_lines"][key] != b["dimension_lines"][key], key


@pytest.fixture
def client(monkeypatch):
    """The config list, served from the files in the tree.

    The engine is not started: the endpoint reads the config files off disk and
    the executor it would build reaches for a backend router, which is a service
    and not a fixture.
    """
    monkeypatch.setattr(R, "init_schema_engine", lambda: None)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_compat_bp)
    return app.test_client()


class TestTheRouteHandsThemOut:
    def _configs(self, client):
        res = client.get("/pipeline_configs_with_properties")
        assert res.status_code == 200
        return {c["id"]: c for c in res.get_json()["configs"]}

    def test_a_pole_carries_its_lines_to_the_surface(self, client):
        configs = self._configs(client)
        for name in POLES:
            assert name in configs, f"{name} is not on the list the surfaces read"
            served = configs[name]["dimension_lines"]
            assert served == _preset(name)["meta"]["dimension_lines"]

    def test_the_checklist_order_travels_as_a_list(self, client):
        """The order the checklist is read in, beside the lines.

        A JSON object is serialised here with its keys SORTED, so the order
        `dimension_lines` is written in does not reach a surface: read off the
        object's keys, the checklist comes out alphabetical (Background,
        Clarity, Color Aesthetic, ...) where the preset reads it in the order of
        the source's own tables (Object pairing, Main object, Richness,
        Background, ...). A list keeps the order it was built with, so the order travels
        as one -- and it is that list a surface reads the checklist in, never the
        object's keys.
        """
        configs = self._configs(client)
        for name in POLES:
            order = configs[name]["dimension_order"]
            assert order == [
                entry["key"] for entry in _preset(name)["meta"]["dimensions_verbatim"]
            ], name
            # The same dimensions the lines are filed under, whatever order those
            # arrived in.
            assert set(configs[name]["dimension_lines"]) == set(order), name

    def test_the_scales_travel_whole(self, client):
        """What the axis counts on: the ordered scale, its neutral word, this
        pole's own word. The surface can work out none of the three from the one
        line, so a route that stopped sending them would leave the instrument
        with an empty draw and no cause anywhere."""
        configs = self._configs(client)
        for name in POLES:
            scales = configs[name]["dimension_scales"]
            for entry in _preset(name)["meta"]["dimensions_verbatim"]:
                sent = scales[entry["key"]]
                assert sent["scale"] == entry["visionreward_option_scale"], (name, entry["key"])
                assert sent["neutral"] == entry["visionreward_option_neutral"], (name, entry["key"])
                assert sent["option"] == entry["visionreward_option"], (name, entry["key"])

    def test_the_frame_travels_with_its_place_in_it(self, client):
        """And the frame text the surface fills. It is sent for a config that
        carries one, whether or not that config also carries lines: the two are
        different data, and a preset with a frame alone would otherwise reach the
        surface as a preset whose poles never arrived."""
        configs = self._configs(client)
        for name in POLES:
            frame = configs[name]["context_frame"]
            assert frame == _preset(name)["meta"]["context_frame"], name
            for lang, text in frame.items():
                assert text.count("{PROPERTIES}") == 1, (name, lang)

    def test_a_config_without_lines_answers_as_before(self, client):
        configs = self._configs(client)
        assert WITHOUT_LINES in configs
        assert "dimension_lines" not in configs[WITHOUT_LINES]
        assert "dimension_order" not in configs[WITHOUT_LINES]
        assert "dimension_scales" not in configs[WITHOUT_LINES]
        assert "context_frame" not in configs[WITHOUT_LINES]


def _word_at(entry, side, steps):
    """The word the axis stands at, exactly as the surface works it out.

    Kept in the same terms as `lineFor` in
    `public/ai4artsed-frontend/src/views/latent_lab/aesthetic_poles.vue`: count
    from the neutral word, `steps` to this pole's side, and stop at the end of
    the scale where it ends before the axis does.
    """
    scale = entry["visionreward_option_scale"]
    i_neutral = scale.index(entry["visionreward_option_neutral"])
    i = min(len(scale) - 1, max(0, i_neutral + side * steps))
    return scale[i]


# How far the axis of the instrument swings, and the two sides it swings to.
# Held against the Vue file below, so that a change there reaches these tests.
AXIS_STEPS = 2
SIDES = {POLES[0]: -1, POLES[1]: 1}


def test_the_axis_reaches_the_stored_line_at_each_pole():
    """At a pole's own word the axis says what the preset's context says.

    The surface composes `<key> - <word>` for the place its handle stands at,
    and the presets carry the line for their own extreme word. Since the swing
    was dropped for the five levels, `"best"` and `"worst"` set
    exactly the index of the preset's own option, so the composed line and the
    stored one have to be the same string -- or surface and preset would put a
    different requirement to the model under one name, the drift this file
    exists to catch.
    """
    for name in POLES:
        preset = _preset(name)
        lines = preset["meta"]["dimension_lines"]
        for entry in preset["meta"]["dimensions_verbatim"]:
            key = entry["key"]
            if key not in _rankable_keys():
                continue
            word = entry["visionreward_option"]
            assert word in entry["visionreward_option_scale"], (name, key)
            assert f"{key}{SEPARATOR}{word}" == lines[key], (name, key)


def test_one_step_stands_between_the_two_poles_where_the_scale_allows_it():
    """And one step in is a DIFFERENT word, wherever the scale has one.

    Otherwise the axis would cost two rows and every picture in them for a text
    that did not change. Where a scale ends before the axis does, the word stays
    -- that is the clamp, and it is named here rather than left to be discovered.
    """
    unchanged = {-1: [], 1: []}
    for name, side in ((POLES[0], -1), (POLES[1], 1)):
        for entry in _preset(name)["meta"]["dimensions_verbatim"]:
            if entry["key"] not in _rankable_keys():
                continue
            if _word_at(entry, side, 1) == _word_at(entry, side, 2):
                unchanged[side].append(entry["key"])
    # Both poles have to have SOMETHING the axis moves, or the control is a
    # control over nothing.
    assert len(unchanged[-1]) < len(_rankable_keys())
    assert len(unchanged[1]) < len(_rankable_keys())
