"""
Tests for the Latent Lab instrument "Mean Images".

Three parts, since the mean moved:
- the overlay arithmetic in my_app/services/mean_images.py, checked against
  what it claims: the mean of k identical images IS that image, the relief of a
  set with no fine texture is mid grey everywhere, and a contact sheet has the
  measure its set size says.
- the mean BEFORE the decoder: the latent arithmetic, and the route's decision
  between the two means. No GPU is reached — the decode is replaced.
- the variants route, checked on what it rejects and on how it reports a model
  that came back with fewer distinct variants than were asked for. The model
  call and the translation are replaced; nothing here reaches a model.

Run: python3 -m pytest devserver/tests/test_mean_images.py -q
(from the worktree root; also works from devserver/ directly)
"""

import base64
import io
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest
from PIL import Image

from my_app.services import mean_images


def _decode(b64: str) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"), dtype=float)


def _noise(width: int = 64, height: int = 64, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3)).astype(float)


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------

def test_mean_of_identical_images_is_that_image():
    """k copies average to the copy — the claim every mean cell rests on."""
    one = _noise(seed=7)
    stack, resized = mean_images.stack_images([one] * 9)
    assert resized is False
    assert np.array_equal(mean_images.mean_image(stack), one)
    # And through the PNG the surface actually receives.
    assert np.array_equal(_decode(mean_images.compose([one] * 9)["mean"]), one)


def test_mean_of_two_flats_is_their_average():
    dark = np.full((16, 16, 3), 40.0)
    light = np.full((16, 16, 3), 200.0)
    stack, _ = mean_images.stack_images([dark, light])
    assert np.allclose(mean_images.mean_image(stack), 120.0)


def test_relief_of_a_flat_image_is_mid_grey_everywhere():
    """No fine texture, no residual: the relief is 128 across the plate."""
    flat = np.full((48, 48, 3), 90.0)
    stack, _ = mean_images.stack_images([flat] * 4)
    relief = mean_images.relief_image(stack)
    assert np.allclose(relief, mean_images.MID_GREY)
    assert np.all(_decode(mean_images.compose([flat] * 4)["relief"]) == 128)


def test_relief_of_a_textured_image_leaves_mid_grey():
    """A set that shares its texture answers with something other than grey."""
    textured = _noise(seed=3)
    stack, _ = mean_images.stack_images([textured] * 5)
    relief = mean_images.relief_image(stack)
    assert not np.allclose(relief, mean_images.MID_GREY)


def test_relief_is_the_measured_high_pass_sigma_3_gain_4():
    """
    The two numbers the reading rests on, pinned to a pattern whose answer can
    be written down independently: sigma = 3 and gain = 4, on the luminance,
    around mid grey. The instrument is read against a measurement made with
    exactly these (2026-09-03); a silent change of either would move every
    relief cell and nothing would say so.
    """
    # One bright pixel in the middle of a black plate. Its high-pass residual at
    # that pixel is the pixel itself minus what a gaussian of sigma 3 leaves
    # there; the same gaussian, computed here, is what the claim is checked on.
    from scipy.ndimage import gaussian_filter

    plate = np.zeros((41, 41, 3))
    plate[20, 20] = 255.0
    stack, _ = mean_images.stack_images([plate])
    relief = mean_images.relief_image(stack)

    luminance = plate.mean(-1)
    expected = 128.0 + (luminance - gaussian_filter(luminance, 3.0)) * 4.0
    assert np.allclose(relief[..., 0], expected)
    assert np.allclose(relief[..., 1], relief[..., 0])
    assert np.allclose(relief[..., 2], relief[..., 0])
    # And the constants themselves, so a change has to come here as well.
    assert (mean_images.RELIEF_SIGMA, mean_images.RELIEF_GAIN) == (3.0, 4.0)
    assert mean_images.MID_GREY == 128.0


@pytest.mark.parametrize(
    "count, cols, rows",
    [(5, 3, 2), (20, 5, 4), (50, 8, 7)],
)
def test_contact_sheet_measures(count, cols, rows):
    """The three sizes the instrument offered until the axis came, unchanged."""
    assert mean_images.sheet_columns(count) == cols
    stack, _ = mean_images.stack_images([_noise(seed=i) for i in range(count)])
    sheet = mean_images.contact_sheet(stack)
    tile = mean_images.SHEET_TILE
    assert sheet.shape == (rows * tile, cols * tile, 3)


def test_a_short_set_keeps_its_size_layout():
    """A refusal takes an image out of a set of twenty; the sheet stays 5 wide."""
    assert mean_images.sheet_columns(19) == 5
    stack, _ = mean_images.stack_images([_noise(seed=i) for i in range(19)])
    sheet = mean_images.contact_sheet(stack)
    tile = mean_images.SHEET_TILE
    assert sheet.shape == (4 * tile, 5 * tile, 3)


# `const PER_CELL_MIN` / `PER_CELL_MAX` in the surface — the ends of the axis a
# visitor moves the set size along.
_PER_CELL_ENDS_IN_THE_SURFACE = re.compile(
    r"const PER_CELL_MIN = (\d+)\nconst PER_CELL_MAX = (\d+)"
)


def test_the_axis_of_the_surface_ends_where_the_route_stops():
    """
    The two places a set size is written down say the same thing.

    The surface lets a visitor set any count between the ends of its axis, and
    the route caps what one press may ask for. An axis whose top end passes the
    route's ceiling asks for a run the route answers with 400; one that stops
    short takes sizes away from the surface without saying so.
    """
    from my_app.routes.mean_images_routes import MAX_PER_CELL

    surface = (
        Path(__file__).resolve().parents[2]
        / "public/ai4artsed-frontend/src/views/latent_lab/mean_images.vue"
    )
    found = _PER_CELL_ENDS_IN_THE_SURFACE.search(surface.read_text(encoding="utf-8"))
    assert found, "the surface carries no PER_CELL_MIN / PER_CELL_MAX any more"
    low, high = int(found.group(1)), int(found.group(2))

    assert high == MAX_PER_CELL
    # Two pictures are the smallest set that HAS a mean; one is the picture.
    assert low >= 2


def test_every_size_of_the_axis_has_a_sheet_that_holds_it():
    """
    A layout for every count the axis offers, and none of them ragged.

    The three offered sizes had a layout each until 2026-09-04; the axis brought
    forty-seven more counts with it, and a sheet is read at a glance — so every
    one of them has to come out square or nearly so, with room for its images.
    """
    from my_app.routes.mean_images_routes import MAX_PER_CELL

    for count in range(2, MAX_PER_CELL + 1):
        cols = mean_images.sheet_columns(count)
        rows = (count + cols - 1) // cols
        assert cols * rows >= count
        assert 0 <= cols - rows <= 1


def test_mixed_sizes_are_brought_to_the_first_image_and_said_so():
    first = _noise(width=64, height=64, seed=1)
    second = _noise(width=32, height=48, seed=2)
    stack, resized = mean_images.stack_images([first, second])
    assert resized is True
    assert stack.shape == (2, 64, 64, 3)
    assert mean_images.compose([first, second])["resized"] is True


def test_a_set_of_one_carries_no_contact_sheet():
    """A sheet of one image would be a second copy of that image."""
    one = _noise(seed=5)
    out = mean_images.compose([one])
    assert out["sheet"] is None
    assert out["count"] == 1
    assert np.array_equal(_decode(out["mean"]), one)


def test_a_set_of_two_carries_one():
    out = mean_images.compose([_noise(seed=1), _noise(seed=2)])
    assert isinstance(out["sheet"], str)


def test_compose_carries_the_count_and_the_measure():
    arrays = [_noise(seed=i) for i in range(9)]
    out = mean_images.compose(arrays)
    assert out["count"] == 9
    assert (out["width"], out["height"]) == (64, 64)
    assert set(out) >= {"mean", "relief", "sheet", "count", "resized", "width", "height"}


def test_compose_needs_at_least_one_image():
    with pytest.raises(ValueError):
        mean_images.compose([])


# ---------------------------------------------------------------------------
# Reading a model's answer
# ---------------------------------------------------------------------------

def test_parse_variants_takes_a_json_array():
    got = mean_images.parse_variants('["b sentence", "c sentence"]', "a sentence", 2)
    assert got == ["b sentence", "c sentence"]


def test_parse_variants_finds_an_array_inside_prose():
    answer = 'Here you are:\n```json\n["one thing", "another thing"]\n```'
    assert mean_images.parse_variants(answer, "a sentence", 2) == ["one thing", "another thing"]


def test_parse_variants_drops_repetitions_and_the_original():
    answer = '["a sentence", "b sentence", "B SENTENCE", "", "c sentence"]'
    assert mean_images.parse_variants(answer, "a sentence", 4) == ["b sentence", "c sentence"]


def test_parse_variants_answers_empty_where_there_is_no_array():
    assert mean_images.parse_variants("I would rather not.", "a sentence", 3) == []


@pytest.mark.parametrize(
    "answer, expected",
    [
        # The array wrapped in an object, with a remark beside it.
        (
            '{"variants": ["a small house", "a tiny house"], "note": "these differ in size"}',
            ["a small house", "a tiny house"],
        ),
        # A sentence AFTER the array, carrying brackets of its own. The greedy
        # search this replaced read to the last bracket in the answer and lost
        # the whole round over it.
        (
            '["one","two"]\n\nEach keeps the "same objects" [as asked].',
            ["one", "two"],
        ),
        # A sentence in front and a bracketed note behind.
        (
            'Here is ["a red house","a house in red"]. Note [1]: the word "house" stays.',
            ["a red house", "a house in red"],
        ),
        # Brackets inside a value of the wrapping object.
        (
            '{"note": "see the [list] below", "variants": ["one", "two"]}',
            ["one", "two"],
        ),
        # A list of objects is an answer in the wrong shape and carries no variant.
        ('[{"variant": "one"}]', []),
        # A bracketed note IN FRONT of the array. It decodes as a list of one
        # number, and the reading used to stop at it and never reach the four.
        (
            'Note [1] follows.\n["one","two","three","four"]',
            ["one", "two", "three", "four"],
        ),
        # The same note in front, and the array behind it cut off. Nothing
        # decodes, so the salvage has to find the array past the note.
        (
            'Here they are [1]:\n["a red house", "a house in red", "a cri',
            ["a red house", "a house in red"],
        ),
        # Entries of punctuation alone carry no line and are dropped.
        ('["...", "!?!", "a house"]', ["a house"]),
    ],
)
def test_parse_variants_reads_the_array_and_nothing_else(answer, expected):
    assert mean_images.parse_variants(answer, "a sentence", 5) == expected


def test_parse_variants_takes_a_repetition_by_case_and_ending():
    """"A HOUSE." and "a house" are one sentence, and one picture in the mean."""
    got = mean_images.parse_variants('["a house.", "A red house!", "a red house"]', "a house", 5)
    assert got == ["A red house!"]


@pytest.mark.parametrize(
    "answer, taken, expected",
    [
        # A model that numbers its answer. The counter belongs to the listing,
        # and it would otherwise reach the image prompt as digits.
        (
            '["1. a red house", "2) a house in red", "3. a crimson house"]',
            (),
            ["a red house", "a house in red", "a crimson house"],
        ),
        # The numbered form of a line an earlier round already wrote is that
        # line, and counts once.
        ('["7. a red house", "a blue house"]', ("a red house",), ["a blue house"]),
        # A sentence that opens with a number and carries no list punctuation
        # behind it keeps the number: it is part of what the sentence says.
        ('["12 chairs around a table"]', (), ["12 chairs around a table"]),
        # The mark written tight against the line, and the mark held off the
        # digit by a space: the counter is the listing's in all three shapes.
        (
            '["7.A house by the river", "7)a house in red", "7 . a crimson house"]',
            (),
            ["A house by the river", "a house in red", "a crimson house"],
        ),
        # A digit behind the mark makes it a decimal point, and the measure
        # keeps the number it is.
        ('["1.5 metres of rope"]', (), ["1.5 metres of rope"]),
        # Four digits carry a year, and the line stays whole.
        ('["2024. a house"]', (), ["2024. a house"]),
        # The counter written tight against a line an earlier round already
        # wrote: that line, and it counts once.
        ('["7.A red house"]', ("a red house",), []),
    ],
)
def test_a_numbered_answer_keeps_the_sentence_and_drops_the_counter(answer, taken, expected):
    assert mean_images.parse_variants(answer, "a street", 5, taken=taken) == expected


def test_the_taken_listing_stays_bounded():
    """A set of fifty must not put all fifty into the next turn."""
    taken = [f"line {i}" for i in range(40)]
    turn = mean_images.variants_messages("a street", 12, taken=taken)[1]["content"]
    # Quoted, so "line 2" is not found inside "line 24".
    listed = [line for line in taken if f'"{line}"' in turn]
    assert listed == taken[-mean_images.TAKEN_LISTED:]


def test_parse_variants_salvages_an_array_that_was_cut_off():
    """A window that ran out costs the last entry, and nothing before it."""
    assert mean_images.parse_variants('["one", "two", "thr', "a sentence", 5) == ["one", "two"]


@pytest.mark.parametrize(
    "answer, expected",
    [
        # A closing bracket INSIDE a variant. Read as the array's close, it hid
        # the whole salvage and cost every complete entry.
        (
            '["a house ] a barn", "a red house", "a gre',
            ["a house ] a barn", "a red house"],
        ),
        # A bracket pair inside a variant, and the array cut off behind it.
        (
            '["a house [seen from the street]", "a red house", "a cri',
            ["a house [seen from the street]", "a red house"],
        ),
        # An opening bracket inside a variant. Taken for the array's own, it
        # started the scan mid-sentence and returned the separators.
        (
            '["a house [seen from the street", "a red house", "a cri',
            ["a house [seen from the street", "a red house"],
        ),
    ],
)
def test_parse_variants_salvages_past_brackets_inside_a_variant(answer, expected):
    """A bracket inside a variant is that variant's text, not the array's."""
    assert mean_images.parse_variants(answer, "a street", 5) == expected


def test_parse_variants_reads_past_the_instruction_a_model_repeated():
    """
    The system prompt shows the answer's shape as `["...", "..."]`. A model that
    states its instruction before answering carries that example in its text,
    ahead of the real array.
    """
    lines = [f"variant line {i}" for i in range(20, 32)]
    answer = (
        "I will answer with a JSON array of strings and nothing else, "
        'for example ["...", "..."]. Here are the 12 variants: '
        + json.dumps(lines)
    )
    assert mean_images.parse_variants(answer, "a street", 12) == lines


def test_parse_variants_drops_what_an_earlier_round_already_took():
    """Case and spacing are no difference between two sentences."""
    answer = '["A  Second   Line", "a third line"]'
    got = mean_images.parse_variants(answer, "a sentence", 5, taken=["a second line"])
    assert got == ["a third line"]


def test_parse_variants_reads_past_the_listing_a_round_restated():
    """
    From round two on the turn lists what is already written, and a model that
    restates that listing before it answers puts a full, well-formed array of
    KNOWN lines ahead of its new ones. Read as the answer, it dedups away to
    nothing and the round is lost.
    """
    taken = [f"line {i}" for i in range(4)]
    fresh = [f"line {i}" for i in range(4, 12)]
    content = (
        "The four already written are "
        + json.dumps(taken)
        + ". Here are 8 new ones: "
        + json.dumps(fresh)
    )
    assert mean_images.parse_variants(content, "a street", 12, taken=taken) == fresh


def test_parse_variants_salvages_nothing_out_of_the_example_shape():
    """
    An answer cut off inside the `["...", "..."]` the instruction shows. The
    salvage reads the one complete literal, and it carries no line.
    """
    assert mean_images.parse_variants('For example ["...", "..', "a street", 5) == []


def test_the_salvage_starts_at_the_innermost_bracket_nothing_closes():
    """Two open brackets, and the cut-off array is the LAST of them."""
    assert mean_images.parse_variants('["one", ["two", "thr', "a street", 5) == ["two"]


@pytest.mark.parametrize(
    "answer, taken, expected",
    [
        # A complete array nested inside the cut-off one. `_decode_array`
        # reaches it before the salvage does, and it is the answer.
        ('["one", ["two"], "three", "fo', (), ["two"]),
        # The same text where that nested array holds nothing new. Now no `[`
        # decodes to a usable list, the salvage runs from the outer bracket, and
        # it stops at the `]` that closed the nested one — "three" stands behind
        # that bracket and is never read.
        ('["one", ["two"], "three", "fo', ("two",), ["one"]),
    ],
)
def test_the_salvage_stops_at_the_first_bracket_outside_a_string(answer, taken, expected):
    assert mean_images.parse_variants(answer, "a street", 5, taken=taken) == expected


def test_a_nest_too_deep_for_json_is_an_answer_without_an_array():
    """
    `json` descends one frame per bracket and gives up over the stack, not over
    the text. Uncaught, that `RecursionError` left the route answering 500 to a
    text a model wrote.
    """
    assert mean_images.parse_variants("[" * 3000 + '"a house"', "a street", 5) == ["a house"]


# ---------------------------------------------------------------------------
# The variants route
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    from flask import Flask
    from my_app.routes.mean_images_routes import mean_images_bp

    app = Flask(__name__)
    app.register_blueprint(mean_images_bp)
    return app.test_client()


@pytest.fixture()
def no_model(monkeypatch):
    """Neither the translation nor the variants call reaches a model."""
    import my_app.routes.chat_routes as chat_routes
    import my_app.routes.schema_pipeline_routes as schema_routes

    answers = {"variants": '["a second line", "a third line"]', "calls": []}

    def helper(*args, **kwargs):
        answers["calls"].append(args)
        answer = answers["variants"]
        # A test that wants a different answer per round writes a callable here
        # and receives the number of the round.
        if callable(answer):
            answer = answer(len(answers["calls"]))
        return {"content": answer}

    monkeypatch.setattr(schema_routes, "translate_one", lambda text, lang="en": f"EN: {text}")
    monkeypatch.setattr(chat_routes, "call_chat_helper", helper)
    return answers


def test_variants_rejects_an_empty_prompt(client, no_model):
    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "  ", "n": 9})
    assert res.status_code == 400
    assert "prompt" in res.get_json()["error"]


def test_variants_rejects_a_missing_body(client, no_model):
    res = client.post('/api/latent-lab/mean-images/variants', data="", content_type="application/json")
    assert res.status_code == 400


@pytest.mark.parametrize("n", [0, -3, 51, "many", 9.5, 9.0, True, None, [9]])
def test_variants_rejects_an_impossible_n(client, no_model, n):
    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "a street", "n": n})
    assert res.status_code == 400
    assert "n" in res.get_json()["error"]


def test_variants_answers_with_the_translation_first(client, no_model):
    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "eine Strasse", "n": 3})
    assert res.status_code == 200
    body = res.get_json()
    assert body["translation_en"] == "EN: eine Strasse"
    assert body["variants"][0] == "EN: eine Strasse"
    assert body["variants"] == ["EN: eine Strasse", "a second line", "a third line"]
    assert body["shortfall"] == 0


def test_variants_of_one_asks_no_model_for_variants(client, no_model):
    """The reference column alone still needs the English text, and nothing more."""
    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "eine Strasse", "n": 1})
    body = res.get_json()
    assert body["variants"] == ["EN: eine Strasse"]
    assert body["shortfall"] == 0
    # The chat helper was never reached: a set of one has no variants to ask for,
    # and a call made anyway would be a paid turn for an answer nobody reads.
    assert no_model["calls"] == []


def test_variants_of_more_than_one_does_ask(no_model, client):
    """The counter the test above rests on moves when a call is in fact made."""
    client.post('/api/latent-lab/mean-images/variants', json={"prompt": "a street", "n": 3})
    assert len(no_model["calls"]) == 1


def test_variants_reports_a_shortfall_and_pads_with_nothing(client, no_model):
    no_model["variants"] = '["only this one"]'
    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "a street", "n": 9})
    body = res.get_json()
    assert body["variants"] == ["EN: a street", "only this one"]
    assert body["shortfall"] == 7
    # Every further round asked for the rest and wrote the same sentence again,
    # which counts as nothing; the ceiling is what ends them.
    assert len(no_model["calls"]) == 3


# The number one recorded call asked for, out of the turn the route sent.
_ASKED_FOR = re.compile(r"Write (\d+) (?:NEW )?variants")


def _asked_for(call) -> int:
    return int(_ASKED_FOR.search(call[0][1]["content"]).group(1))


def test_variants_are_collected_in_rounds_and_the_rounds_add_up(client, no_model):
    """
    The largest set is asked for a round at a time, and what the rounds wrote is
    what the surface receives.
    """
    per_call = mean_images.VARIANTS_PER_CALL

    def fresh_ones(round_number):
        start = (round_number - 1) * per_call
        # Every round after the first is told what the round before it wrote —
        # without that listing a model answers the same twelve sentences again
        # and the set stops growing at the size of one round.
        if round_number > 1:
            turn = no_model["calls"][-1][0][1]["content"]
            assert f'"line {start - 1}"' in turn, turn
        return json.dumps([f"line {i}" for i in range(start, start + per_call)])

    no_model["variants"] = fresh_ones
    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "a street", "n": 50})
    body = res.get_json()

    assert len(no_model["calls"]) == 5
    # No round asks a model for more than one window's worth.
    assert [_asked_for(call) for call in no_model["calls"]] == [12, 12, 12, 12, 1]
    assert all(_asked_for(call) <= per_call for call in no_model["calls"])
    # The union of the rounds, in the order they were written, behind the
    # translation.
    assert body["variants"] == ["EN: a street"] + [f"line {i}" for i in range(49)]
    assert body["shortfall"] == 0


def test_a_round_in_the_wrong_shape_is_asked_again(client, no_model):
    """
    An answer this parser cannot read costs its round and nothing more: the
    next one is a fresh draw and is worth a turn.
    """
    per_call = mean_images.VARIANTS_PER_CALL

    def unreadable_then_proper(round_number):
        if round_number == 1:
            return '[{"variant": "one"}, {"variant": "two"}]'
        return json.dumps([f"line {i}" for i in range(per_call)])

    no_model["variants"] = unreadable_then_proper
    res = client.post(
        '/api/latent-lab/mean-images/variants',
        json={"prompt": "a street", "n": per_call + 1},
    )
    body = res.get_json()

    assert len(no_model["calls"]) == 2
    assert body["variants"] == ["EN: a street"] + [f"line {i}" for i in range(per_call)]
    assert body["shortfall"] == 0


def test_rounds_that_are_all_unreadable_end_at_the_ceiling(client, no_model):
    """A model answering prose costs its rounds and nothing else."""
    no_model["variants"] = "I would rather not."

    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "a street", "n": 5})
    assert res.status_code == 200
    body = res.get_json()

    # ceil(4 / 12) + 2 rounds, and the answer is the translation with nothing on it.
    assert len(no_model["calls"]) == 3
    assert body["variants"] == ["EN: a street"]
    assert body["shortfall"] == 4


def test_a_round_that_adds_nothing_is_asked_again_up_to_the_ceiling(client, no_model):
    """
    A model that writes the same twelve sentences again is asked again: the next
    turn is a fresh draw and may carry a set this one did not. What bounds the
    cost is the ceiling, and every round of the run is spent reaching it.
    """
    per_call = mean_images.VARIANTS_PER_CALL
    no_model["variants"] = json.dumps([f"line {i}" for i in range(per_call)])

    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "a street", "n": 50})
    body = res.get_json()

    assert body["variants"] == ["EN: a street"] + [f"line {i}" for i in range(per_call)]
    assert body["shortfall"] == 49 - per_call
    assert len(no_model["calls"]) == math.ceil(49 / per_call) + 2


def test_a_round_that_restates_what_is_written_carries_its_new_lines(client, no_model):
    """
    The round-two shape that used to end a run short: the answer lists the four
    variants already written before it writes eight new ones.
    """
    first = [f"line {i}" for i in range(4)]
    second = [f"line {i}" for i in range(4, 12)]

    def restating(round_number):
        if round_number == 1:
            return json.dumps(first)
        return (
            "The four already written are "
            + json.dumps(first)
            + ". Here are 8 new ones: "
            + json.dumps(second)
        )

    no_model["variants"] = restating
    res = client.post('/api/latent-lab/mean-images/variants', json={"prompt": "a street", "n": 13})
    body = res.get_json()

    assert len(no_model["calls"]) == 2
    assert body["variants"] == ["EN: a street"] + first + second
    assert body["shortfall"] == 0


# ---------------------------------------------------------------------------
# The overlay route
# ---------------------------------------------------------------------------

def test_overlay_rejects_an_empty_set(client):
    res = client.post('/api/latent-lab/mean-images/overlay', json={"run_ids": []})
    assert res.status_code == 400


def test_overlay_rejects_more_than_a_set(client):
    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": [f"run_{i}" for i in range(51)]},
    )
    assert res.status_code == 400


def test_overlay_lays_the_resolved_runs_over_each_other(client, monkeypatch, tmp_path):
    """The resolver of /api/media/image/<run_id>/0 is the one that is asked."""
    import my_app.routes.media_routes as media_routes

    one = _noise(seed=11)
    path = tmp_path / "image.png"
    Image.fromarray(one.astype(np.uint8)).save(path)

    monkeypatch.setattr(
        media_routes, "_resolve_image",
        lambda run_id, index: ((path, "png", 0), None) if run_id != "gone" else (None, ("x", 404)),
    )

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "gone", "run_b"]},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["count"] == 2
    assert body["missing"] == ["gone"]
    # Two copies of one image average to that image.
    assert np.array_equal(_decode(body["mean"]), one)
    assert isinstance(body["sheet"], str)


def test_overlay_without_a_record_writes_nothing_and_says_so(client, monkeypatch, tmp_path):
    """The composite alone is a complete answer; `run_id` is simply empty."""
    import my_app.routes.media_routes as media_routes

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=2).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    res = client.post('/api/latent-lab/mean-images/overlay', json={"run_ids": ["run_a", "run_b"]})
    assert res.status_code == 200
    assert res.get_json()["run_id"] is None


@pytest.fixture()
def sitting(monkeypatch, tmp_path):
    """An open sitting whose runs are written into a folder of this test's own."""
    import config
    import my_app.services.latent_lab_recorder as lab

    recorder = lab.LatentLabRecorder(
        session_id="sitting_1",
        latent_lab_tool="mean_images",
        device_id="dev",
        base_path=tmp_path,
    )
    monkeypatch.setitem(lab._active_recorders, "sitting_1", recorder)
    # The addresses this sitting hands out are resolved through the platform's
    # single resolver, which reads `config.JSON_STORAGE_DIR` at call time — so
    # they are looked up here and nothing touches the real exports.
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", str(tmp_path))
    return {"base": tmp_path, "recorder": recorder}


def _stored(ref):
    """The picture one address hands out, as pixels.

    Pixels rather than bytes: the AI-origin marking goes into the file's
    metadata and leaves every pixel where it was, so a comparison by pixel says
    the two are the same picture whatever else the file carries.
    """
    from my_app.utils.media_ref import resolve_media_ref

    with Image.open(resolve_media_ref(ref)) as img:
        return np.asarray(img.convert("RGB"), dtype=float)


def _run_metadata(base, run_id):
    folder = next(Path(base).glob(f"*/*/{run_id}"))
    return json.loads((folder / "metadata.json").read_text(encoding="utf-8"))


def test_a_recorded_cell_becomes_a_run_of_its_own(client, monkeypatch, sitting, tmp_path):
    """
    The composite is an address the moment it exists.

    The whole raster is written at the very end, so a question about a finished
    cell while the rest is still filling used to have nothing to open.
    """
    import my_app.routes.media_routes as media_routes
    from my_app.utils.media_ref import find_media_entities

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=4).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b", "run_c"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "seedFixed",
                "seed": 424242,
                "translation_en": "a street at night",
            },
        },
    )
    assert res.status_code == 200
    run_id = res.get_json()["run_id"]
    assert isinstance(run_id, str) and run_id

    metadata = _run_metadata(sitting["base"], run_id)
    assert metadata["parameters"]["part"] == "cell"
    assert metadata["parameters"]["run_ids"] == ["run_a", "run_b", "run_c"]

    # The ORDER `view_run` reads: the account first, because it reads every text
    # output aloud, then the mean, because it shows the FIRST image.
    written = [e["type"] for e in metadata["entities"] if e["type"].startswith("output_")]
    assert written == ["output_text", "output_image", "output_image", "output_image"]

    images = find_media_entities(metadata["entities"], "image")
    assert [e["metadata"]["view"] for e in images] == ["mean", "relief", "images"]

    folder = next(Path(sitting["base"]).glob(f"*/*/{run_id}"))
    account = next(folder.glob("final/*_output_text.txt")).read_text(encoding="utf-8")
    assert "Mean image of 3 pictures" in account
    assert "SD 3.5 Large" in account
    assert "424242" in account
    # Single typographic quotes: Help sets this whole account inside double
    # quotes of its own, and with double quotes here the line ended `"."`.
    assert account.endswith("The prompt in English: ‘a street at night’.")


def test_a_set_of_one_is_recorded_without_a_sheet(client, monkeypatch, sitting, tmp_path):
    """The mean IS that picture, so there is no contact sheet to write."""
    import my_app.routes.media_routes as media_routes
    from my_app.utils.media_ref import find_media_entities

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=6).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a"],
            "record": {
                "session_id": "sitting_1",
                "model": "flux2",
                "model_label": "Flux 2",
                "axis": "promptFixed",
                "seed": None,
                "translation_en": "a street",
            },
        },
    )
    run_id = res.get_json()["run_id"]
    metadata = _run_metadata(sitting["base"], run_id)
    assert [e["metadata"]["view"] for e in find_media_entities(metadata["entities"], "image")] == [
        "mean", "relief",
    ]
    folder = next(Path(sitting["base"]).glob(f"*/*/{run_id}"))
    account = next(folder.glob("final/*_output_text.txt")).read_text(encoding="utf-8")
    assert account.startswith("The single picture of this cell.")


def test_the_reference_axis_is_not_a_set_and_is_not_recorded(client, monkeypatch, sitting, tmp_path):
    """
    A reference cell holds ONE picture, and that picture is a pipeline run with
    an address already. The surface sends no record for it; this pins the other
    side, so a request that does carry one writes no second address for it.
    """
    import my_app.routes.media_routes as media_routes

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=12).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "reference",
                "seed": 424242,
                "translation_en": "a street",
            },
        },
    )
    assert res.status_code == 200
    assert res.get_json()["run_id"] is None
    # Nothing at all was written into the sitting.
    assert list(Path(sitting["base"]).glob("*/*/run_*")) == []
    assert sitting["recorder"].generation == 0


@pytest.mark.parametrize(
    "record",
    [
        "sitting_1",
        {"model": "sd35_large", "axis": "seedFixed"},
        {"session_id": "  ", "axis": "seedFixed"},
        {"session_id": "sitting_1", "axis": "reference"},
        {"session_id": "sitting_1", "axis": "seedFixed", "seed": "424242"},
        {"session_id": "no_such_sitting", "axis": "seedFixed", "seed": 424242},
        {"session_id": "sitting_1", "axis": "seedFixed", "seed": None},
    ],
)
def test_a_record_that_cannot_be_used_costs_the_address_and_not_the_composite(
    client, monkeypatch, sitting, tmp_path, record
):
    """A malformed record is a warning, never a 400: the composite is the point."""
    import my_app.routes.media_routes as media_routes

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=8).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"], "record": record},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["run_id"] is None
    assert isinstance(body["mean"], str)


def test_overlay_of_a_single_run_carries_no_sheet(client, monkeypatch, tmp_path):
    import my_app.routes.media_routes as media_routes

    one = _noise(seed=13)
    path = tmp_path / "single.png"
    Image.fromarray(one.astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    body = client.post('/api/latent-lab/mean-images/overlay', json={"run_ids": ["run_a"]}).get_json()
    assert body["count"] == 1
    assert body["sheet"] is None
    assert np.array_equal(_decode(body["mean"]), one)


def test_overlay_answers_404_where_no_run_carried_an_image(client, monkeypatch):
    import my_app.routes.media_routes as media_routes

    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: (None, ("x", 404)))
    res = client.post('/api/latent-lab/mean-images/overlay', json={"run_ids": ["a", "b"]})
    assert res.status_code == 404
    assert res.get_json()["missing"] == ["a", "b"]


def test_the_addresses_in_the_answer_resolve_to_the_pictures_in_the_answer(
    client, monkeypatch, sitting, tmp_path
):
    """`refs` is how the surface names these pictures instead of sending them up.

    The whole raster is written at the end out of the cells that stand on the
    page. Each cell is a run already, so the raster names its pictures by their
    address; if those addresses pointed anywhere else, the raster would be a
    record of pictures nobody ever saw.
    """
    import my_app.routes.media_routes as media_routes

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=21).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b", "run_c"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "seedFixed",
                "seed": 424242,
                "translation_en": "a street at night",
            },
        },
    ).get_json()

    run_id = body["run_id"]
    assert body["refs"] == {
        "mean": f"/api/media/image/{run_id}/0",
        "relief": f"/api/media/image/{run_id}/1",
        "images": f"/api/media/image/{run_id}/2",
    }
    assert np.array_equal(_stored(body["refs"]["mean"]), _decode(body["mean"]))
    assert np.array_equal(_stored(body["refs"]["relief"]), _decode(body["relief"]))
    assert np.array_equal(_stored(body["refs"]["images"]), _decode(body["sheet"]))


def test_a_picture_that_was_not_written_moves_the_addresses_after_it(
    client, monkeypatch, sitting, tmp_path
):
    """The numbers come off what WAS written, never off what was sent in.

    One output that cannot be written costs that output and not the run, so the
    run then holds two pictures where three were meant. Counted off the outputs
    sent in, the contact sheet's address would name the relief's place — and the
    raster would store the sheet under the relief's picture.
    """
    import my_app.routes.media_routes as media_routes
    import my_app.services.latent_lab_recorder as lab

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=22).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    # The relief, and nothing else, cannot be written. It is the SECOND of the
    # three pictures, so the contact sheet moves up into its place. Told apart
    # by its BYTES: the recorder has to receive the plates as `compose` made
    # them, before the route marks the page's copy — a marked relief carries
    # the time of its marking and would no longer match.
    refused = base64.b64decode(mean_images.compose([mean_images.load_image(path)] * 2)["relief"])
    marked = lab._marked

    def one_picture_fails(raw, entity_type, entity_metadata):
        if raw == refused:
            raise OSError("the relief could not be written")
        return marked(raw, entity_type, entity_metadata)

    monkeypatch.setattr(lab, "_marked", one_picture_fails)

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "seedFixed",
                "seed": 424242,
                "translation_en": "a street",
            },
        },
    ).get_json()

    run_id = body["run_id"]
    assert body["refs"] == {
        "mean": f"/api/media/image/{run_id}/0",
        "images": f"/api/media/image/{run_id}/1",
    }
    assert np.array_equal(_stored(body["refs"]["images"]), _decode(body["sheet"]))


def test_a_held_seed_that_is_missing_costs_the_address_and_not_the_composite(
    client, monkeypatch, sitting, tmp_path
):
    """The held-seed axis is ABOUT its seed, and a cell may not claim one it has not got."""
    import my_app.routes.media_routes as media_routes

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=23).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "seedFixed",
                "seed": None,
                "translation_en": "a street",
            },
        },
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["run_id"] is None
    assert body["refs"] == {}
    assert isinstance(body["mean"], str)
    assert list(Path(sitting["base"]).glob("*/*/run_*")) == []
    assert sitting["recorder"].generation == 0


def test_the_axis_that_draws_its_seeds_is_recorded_without_one(
    client, monkeypatch, sitting, tmp_path
):
    """The other axis draws a fresh seed per picture and has none to hold."""
    import my_app.routes.media_routes as media_routes

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=25).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {
                "session_id": "sitting_1",
                "model": "flux2",
                "model_label": "Flux 2",
                "axis": "promptFixed",
                "seed": None,
                "translation_en": "a street",
            },
        },
    ).get_json()
    assert isinstance(body["run_id"], str)
    assert _run_metadata(sitting["base"], body["run_id"])["parameters"]["seed"] is None


def test_only_the_runs_a_picture_came_from_are_recorded(
    client, monkeypatch, sitting, tmp_path
):
    """The parameters of a cell are what a later reader recomputes it from.

    A run whose image could not be read went into nothing. Listed among the run
    ids it would say a picture of it is in the mean, and `count` would disagree
    with the list beside it.
    """
    import my_app.routes.media_routes as media_routes

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=24).astype(np.uint8)).save(path)
    monkeypatch.setattr(
        media_routes, "_resolve_image",
        lambda run_id, index: (None, ("x", 404)) if run_id == "gone" else ((path, "png", 0), None),
    )

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "gone", "run_b"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "seedFixed",
                "seed": 424242,
                "translation_en": "a street",
            },
        },
    ).get_json()

    assert body["missing"] == ["gone"]
    parameters = _run_metadata(sitting["base"], body["run_id"])["parameters"]
    assert parameters["run_ids"] == ["run_a", "run_b"]
    assert parameters["count"] == len(parameters["run_ids"]) == body["count"]


def _disclosure_of(b64: str, folder: Path) -> dict:
    """What the platform's own reader finds in one answered picture. The
    reader takes a path, so the picture is written into this test's folder."""
    from my_app.services.watermark_service import read_media_disclosure

    target = folder / "answered.png"
    target.write_bytes(base64.b64decode(b64))
    return read_media_disclosure(str(target))


def _naming_the_model(monkeypatch):
    """The disclosure names the model only while the installation says so
    (`metadata_include_model`); the coded default holds it on, and a test
    about the model must not turn on what an installation's settings hold."""
    import config

    monkeypatch.setattr(config, "WATERMARK", {**config.WATERMARK, "metadata_include_model": True})


def test_the_answered_plates_carry_the_ai_origin_disclosure(client, monkeypatch, tmp_path):
    """The cell shows and downloads the answer's copy until the raster is
    written back, so that copy is the one that has to be marked, with or
    without a record."""
    import my_app.routes.media_routes as media_routes
    from my_app.services.watermark_service import DIGITAL_SOURCE_TYPE_AI

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=31).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    body = client.post('/api/latent-lab/mean-images/overlay', json={"run_ids": ["run_a", "run_b"]}).get_json()
    for view in ("mean", "relief", "sheet"):
        found = _disclosure_of(body[view], tmp_path)
        assert found["marked"], view
        assert found["digital_source_type"] == DIGITAL_SOURCE_TYPE_AI, view


def test_the_answered_plates_and_the_stored_plates_each_name_the_model(
    client, monkeypatch, sitting, tmp_path
):
    """Both copies carry the disclosure, and both name the model the cell was
    drawn with: the recorder marks what it writes, and the route marks what it
    answers."""
    import my_app.routes.media_routes as media_routes
    from my_app.services.watermark_service import read_media_disclosure
    from my_app.utils.media_ref import resolve_media_ref

    _naming_the_model(monkeypatch)
    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=32).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "seedFixed",
                "seed": 424242,
                "translation_en": "a street",
            },
        },
    ).get_json()
    for ref, key in (("mean", "mean"), ("relief", "relief"), ("images", "sheet")):
        stored = read_media_disclosure(resolve_media_ref(body["refs"][ref]))
        answered = _disclosure_of(body[key], tmp_path)
        for found in (stored, answered):
            assert found["marked"], key
            assert "model=sd35_large" in found["description"], key


@pytest.mark.parametrize("refusal", ["the sitting has ended", "the recorder refuses the write"])
def test_a_refused_record_still_names_the_model_on_the_answered_plates(
    client, monkeypatch, sitting, tmp_path, refusal
):
    """A record the recorder has to refuse costs the address and not the
    disclosure: what the page shows still says which model drew the set.
    Both refusals: no open sitting for the record, and a recorder that
    raises on the write."""
    import my_app.routes.media_routes as media_routes

    _naming_the_model(monkeypatch)
    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=33).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    session_id = "sitting_1"
    if refusal == "the sitting has ended":
        session_id = "no_such_sitting"
    else:
        def refuses(**kwargs):
            raise OSError("the disk is full")

        monkeypatch.setattr(sitting["recorder"], "record", refuses)

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {
                "session_id": session_id,
                "model": "sd35_large",
                "axis": "seedFixed",
                "seed": 424242,
            },
        },
    ).get_json()
    assert body["run_id"] is None and body["refs"] == {}
    for view in ("mean", "relief", "sheet"):
        assert "model=sd35_large" in _disclosure_of(body[view], tmp_path)["description"], view


def test_a_composite_says_it_is_one_and_what_it_was_computed_from(
    client, monkeypatch, sitting, tmp_path
):
    """A mean is no render, and whoever reads the run back has to be told so."""
    import my_app.routes.media_routes as media_routes
    from my_app.services.latent_lab_recorder import name_plate
    from my_app.utils.media_ref import find_media_entities

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=26).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image", lambda run_id, index: ((path, "png", 0), None))

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b", "run_c"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "seedFixed",
                "seed": 424242,
                "translation_en": "a street",
            },
        },
    ).get_json()

    images = find_media_entities(
        _run_metadata(sitting["base"], body["run_id"])["entities"], "image"
    )
    assert [e["metadata"]["plate"] for e in images] == ["composite", "composite", "composite"]
    assert [e["metadata"]["reading"] for e in images] == [
        {"view": "mean", "pictures": 3},
        {"view": "relief", "pictures": 3},
        {"view": "images", "pictures": 3},
    ]
    said = name_plate(images[0]["metadata"])
    assert "computed from several renders" in said
    assert "view: mean, pictures: 3" in said


# ---------------------------------------------------------------------------
# The mean before the decoder
# ---------------------------------------------------------------------------

def _latent(value: float, channels: int = 4, size: int = 8) -> np.ndarray:
    return np.full((channels, size, size), value, dtype=np.float32)


def _npy(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def test_the_mean_of_two_latents_is_their_average():
    """The one claim the whole latent path rests on."""
    mean = mean_images.mean_latent([_latent(2.0), _latent(6.0)])
    assert mean.shape == (4, 8, 8)
    assert np.allclose(mean, 4.0)
    assert mean.dtype == np.float32


def test_a_latent_of_another_measure_is_refused_naming_both_shapes():
    """
    Two measures are two pictures' worth of noise. Bringing one to the other
    would interpolate numbers no decoder ever wrote, so the set is refused —
    and the caller then takes the pixel mean, which CAN join two measures.
    """
    with pytest.raises(ValueError) as raised:
        mean_images.mean_latent([_latent(1.0, size=8), _latent(1.0, size=16)])
    said = str(raised.value)
    assert "(4, 8, 8)" in said and "(4, 16, 16)" in said


def test_mean_latent_needs_at_least_one():
    with pytest.raises(ValueError):
        mean_images.mean_latent([])


@pytest.mark.parametrize("shape", [(4, 8, 8), (1, 4, 8, 8)])
def test_a_stored_latent_is_read_with_or_without_its_batch_axis(shape, tmp_path):
    """
    A single picture is denoised in a batch of one, and what is written carries
    that axis or does not. Either way one latent comes back.
    """
    path = tmp_path / "latent.npy"
    np.save(path, np.full(shape, 3.5, dtype=np.float16), allow_pickle=False)
    array = mean_images.load_latent(path)
    assert array.shape == (4, 8, 8)
    assert array.dtype == np.float32
    assert np.allclose(array, 3.5)


def test_a_latent_of_the_wrong_rank_says_what_it_received(tmp_path):
    path = tmp_path / "latent.npy"
    np.save(path, np.zeros((4, 8), dtype=np.float16), allow_pickle=False)
    with pytest.raises(ValueError) as raised:
        mean_images.load_latent(path)
    assert "(4, 8)" in str(raised.value)


def test_a_latent_survives_the_trip_to_the_decoder():
    """What is sent is what numpy reads back — the decode gets the mean itself."""
    mean = mean_images.mean_latent([_latent(1.0), _latent(3.0)])
    read = np.load(io.BytesIO(mean_images.latent_npy_bytes(mean)), allow_pickle=False)
    assert np.array_equal(read, mean)
    assert read.dtype == np.float32


def test_compose_takes_a_mean_that_was_made_elsewhere():
    """
    The latent mean is the cell's mean; relief and sheet stay what they are,
    read off the decoded singles, and `count` is the number of pictures.
    """
    made = _noise(seed=31)
    elsewhere = mean_images.to_png_bytes(np.full((64, 64, 3), 77.0))
    composed = mean_images.compose([made] * 4, mean_png=elsewhere)
    assert np.all(_decode(composed["mean"]) == 77)
    assert composed["count"] == 4
    assert np.array_equal(_decode(composed["relief"]),
                          _decode(mean_images.compose([made] * 4)["relief"]))
    assert composed["sheet"] is not None


# ---------------------------------------------------------------------------
# What the cell says it is
# ---------------------------------------------------------------------------

def test_the_account_names_where_the_averaging_happened():
    """
    A latent mean keeps the local sharpness of a single picture and a pixel mean
    has less than half of it. Whoever reads the run back has to be told which of
    the two is in front of them, or the difference reads as one between the sets.
    """
    from my_app.routes.mean_images_routes import cell_account

    latent = cell_account("SD 3.5 Large", "seedFixed", 20, 424242, "a house", "latent")
    assert latent.startswith(
        "Mean of 20 pictures, taken before the decoder: "
        "their latents were averaged and decoded once."
    )
    pixel = cell_account("Flux 2", "seedFixed", 20, 424242, "a house", "pixel")
    assert pixel.startswith("Mean image of 20 pictures, averaged pixel by pixel.")
    # Both still say what was held and what was moved.
    assert "all on seed 424242" in latent and "all on seed 424242" in pixel


@pytest.mark.parametrize("kind", ["latent", "pixel"])
def test_a_set_of_one_is_neither_mean(kind):
    """One picture was averaged nowhere, and the account says so under both."""
    from my_app.routes.mean_images_routes import cell_account

    said = cell_account("SD 3.5 Large", "promptFixed", 1, None, "a house", kind)
    assert said.startswith("The single picture of this cell.")


# ---------------------------------------------------------------------------
# The overlay route, deciding between the two means
# ---------------------------------------------------------------------------

# What the GPU service says about a latent it wrote. The two names travel in the
# record and are read back out of it — the decode of a set is done by the model
# that made the set, and no file on this platform names it as a literal.
_LATENT_META = {
    "model_id": "a-model/for-this-test",
    "pipeline_class": "APipelineForThisTest",
    "scaling_factor": 1.5,
    "shift_factor": 0.5,
    "shape": [4, 8, 8],
    "dtype": "float16",
}


@pytest.fixture()
def latent_runs(monkeypatch, tmp_path):
    """
    Runs on disk that kept a latent, read back the way the route reads them.

    Real recorders, real entities, real files: what is under test is the whole
    lookup — the platform's entity-selection rule, the recorder's folder and the
    meta the chunk wrote — and a stubbed `_latent_of` would test none of it.
    """
    import config
    import my_app.services.pipeline_recorder as pr

    base = tmp_path / "runs"
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", str(base))

    def make(run_id: str, value: float, meta=_LATENT_META, shape=(4, 8, 8),
             array=None):
        recorder = pr.LivePipelineRecorder(
            run_id=run_id, config_name="sd35_large", safety_level="open",
            device_id="dev", base_path=base,
        )
        recorder.save_entity(
            entity_type="output_image",
            content=mean_images.to_png_bytes(_noise(seed=1)),
            metadata={"format": "png"},
        )
        if meta is not None:
            recorder.save_entity(
                entity_type="output_latent",
                content=_npy(
                    np.full(shape, value, dtype=np.float16) if array is None
                    else np.asarray(array, dtype=np.float16)),
                metadata={"format": "npy", "latent": meta},
            )
        monkeypatch.setitem(pr._active_recorders, run_id, recorder)
        return recorder

    return make


@pytest.fixture()
def checked_run(monkeypatch, tmp_path):
    """A run recorded at a level that checks pictures, with its verdict on the
    picture: passed, turned back, or not yet there (`mark_entity_safety`)."""
    import config
    import my_app.services.pipeline_recorder as pr

    base = tmp_path / "runs"
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", str(base))

    def make(run_id: str, safe, value: float = 3.0):
        recorder = pr.LivePipelineRecorder(
            run_id=run_id, config_name="sd35_large", safety_level="kids",
            device_id="dev", base_path=base,
        )
        recorder.save_entity(
            entity_type="output_image",
            content=mean_images.to_png_bytes(_noise(seed=1)),
            metadata={"format": "png"},
        )
        if safe is not None:
            sequence = recorder.metadata["entities"][-1]["sequence"]
            recorder.mark_entity_safety(sequence, safe=safe, reason="" if safe else "test")
        recorder.save_entity(
            entity_type="output_latent",
            content=_npy(np.full((4, 8, 8), value, dtype=np.float16)),
            metadata={"format": "npy", "latent": _LATENT_META},
        )
        monkeypatch.setitem(pr._active_recorders, run_id, recorder)
        return recorder

    return make


@pytest.fixture()
def decoder(monkeypatch):
    """The decode in ComfyUI, replaced. Nothing here reaches a card."""
    import my_app.services.latent_decoder as latent_decoder

    seen = {"calls": [], "png": mean_images.to_png_bytes(np.full((64, 64, 3), 55.0))}

    async def decode_in_comfyui(meta, latent_npy):
        seen["calls"].append({
            "model_id": meta["model_id"],
            "pipeline_class": meta["pipeline_class"],
            "latent": np.load(io.BytesIO(latent_npy), allow_pickle=False),
        })
        answer = seen.get("raises")
        if answer is not None:
            raise answer
        return seen["png"]

    monkeypatch.setattr(latent_decoder, "decode_in_comfyui", decode_in_comfyui)
    return seen


@pytest.fixture()
def open_level(monkeypatch):
    """A level that asks for no image check, and a checker that records a call."""
    import my_app.services.safety_level_resolver as resolver
    import my_app.utils.vlm_safety as vlm_safety

    seen = {"level": "open", "calls": [], "answer": (True, "", "")}
    monkeypatch.setattr(resolver, "resolve_safety_level", lambda: seen["level"])

    def check(image_path, safety_level):
        seen["calls"].append((str(image_path), safety_level))
        return seen["answer"]

    monkeypatch.setattr(vlm_safety, "vlm_safety_check", check)
    return seen


def _one_image(monkeypatch, tmp_path):
    """Every run answers with the same picture, so the pixel mean is knowable."""
    import my_app.routes.media_routes as media_routes

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=17).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image",
                        lambda run_id, index: ((path, "png", 0), None))
    return path


# ---------------------------------------------------------------------------
# The set drawn as the tensor it is, while it is still being made
# ---------------------------------------------------------------------------

def test_the_drawing_does_not_depend_on_which_picture_came_first():
    """The window belongs to the SET: shuffle the arrivals, get the same plate.

    This is what a window fitted on the first latent could not do. Across the
    178 latents stored on the dev host a single one's per-channel standard
    deviation runs 0.17 to 1.19, so which picture happened to come back first
    decided how loud every later step of that set looked — a spread wider than
    the settling the sequence exists to show.
    """
    rng = np.random.default_rng(3)
    many = [rng.normal(0.3, spread, size=(4, 8, 8)).astype(np.float32)
            for spread in (0.2, 0.5, 1.1, 0.4, 0.8)]
    drawn = mean_images.latent_view(many)
    for order in ([4, 0, 3, 1, 2], [2, 1, 0, 4, 3]):
        assert np.allclose(drawn, mean_images.latent_view([many[i] for i in order]),
                           atol=1e-3)


def test_one_picture_is_drawn_as_itself_and_fills_the_plate():
    """n = 1 is that picture's own middle and its own spread.

    Three standard deviations over the byte range: a channel fills the plate and
    barely clips. A window twice too wide makes every step flat grey, one twice
    too narrow makes it a black-and-white mask, and both would pass an assertion
    on the shape alone.
    """
    rng = np.random.default_rng(5)
    one = rng.normal(0.0, 1.0, size=(4, 16, 16)).astype(np.float32)
    drawn = mean_images.latent_view([one])
    assert np.allclose(drawn, mean_images.latent_view([one, one]))
    assert 35.0 < float(drawn.std()) < 48.0
    # A loose ceiling, and deliberately loose: a real single SD 3.5 latent loses
    # up to 2 % of its plate to the ends, because it is the loud step of the
    # sequence. What this catches is a window off by an order of magnitude.
    assert float(((drawn <= 0.0) | (drawn >= 255.0)).mean()) < 0.05


def test_a_flat_latent_is_drawn_mid_grey_instead_of_dividing_by_nothing():
    flat = np.full((4, 8, 8), 1.25, dtype=np.float32)
    view = mean_images.latent_view([flat])
    assert np.allclose(view, mean_images.MID_GREY)


def test_the_drawing_fades_exactly_insofar_as_the_pictures_disagree():
    """The yardstick stays at ONE picture's loudness, so the fading IS the reading.

    Twenty unrelated pictures average toward the middle. Twenty copies of one
    picture do not move at all. Re-fitting the window on the running mean would
    rescale the first case away and both would come back as loud as a single
    picture — which is what the old test could not tell apart.
    """
    rng = np.random.default_rng(11)
    apart = [rng.normal(0.0, 1.0, size=(4, 16, 16)).astype(np.float32)
             for _ in range(20)]
    one = float(np.abs(mean_images.latent_view(apart[:1]) - mean_images.MID_GREY).mean())
    twenty = float(np.abs(mean_images.latent_view(apart) - mean_images.MID_GREY).mean())
    assert twenty < one / 3.0

    assert np.allclose(mean_images.latent_view([apart[0]] * 20),
                       mean_images.latent_view(apart[:1]))


def test_the_width_is_the_average_of_the_pictures_own_spreads():
    """Not the spread of the pooled set, and not the loudest picture's.

    Four quiet latents and one loud one, all independent. The yardstick is the
    average of the individual standard deviations — (4 x 0.25 + 2.0) / 5 = 0.6 —
    while the mean of the five has a standard deviation of sqrt(4.25) / 5 =
    0.412, so the plate stands at 255 x 0.412 / (6 x 0.6) = 29 grey levels.

    Pooling the set into one standard deviation would put the yardstick at 0.922
    and the plate at 19; measuring the loudest picture would put it at 2.0 and
    the plate at 9. Both of those are independent of the order of arrival, so
    the shuffle test above cannot tell them apart from the rule this platform
    actually wants — and a set whose pictures differ in loudness is the ordinary
    case here, not a contrived one.
    """
    rng = np.random.default_rng(53)
    quiet = [rng.normal(0.0, 0.25, size=(4, 64, 64)).astype(np.float32)
             for _ in range(4)]
    loud = rng.normal(0.0, 2.0, size=(4, 64, 64)).astype(np.float32)

    drawn = mean_images.latent_view([*quiet, loud])
    assert 25.0 < float(drawn.std()) < 34.0


def test_the_plate_keeps_to_the_byte_range_and_reaches_both_ends():
    """Three standard deviations are the window, and the window has edges.

    A latent with one far outlier drives the raw plate well past both ends. What
    comes back is clipped to them AND reaches them: a plate that never reaches
    them would mean a window quietly wider than it says, and one that runs past
    them would wrap when it is cast to bytes.
    """
    rng = np.random.default_rng(59)
    latent = rng.normal(0.0, 1.0, size=(4, 16, 16)).astype(np.float32)
    latent[:3, 0, 0] = 40.0
    latent[:3, 0, 1] = -40.0

    drawn = mean_images.latent_view([latent])
    assert float(drawn.min()) == 0.0
    assert float(drawn.max()) == 255.0


def test_the_planes_are_the_first_three_channels_in_that_order():
    """Not one channel three times over, and not back to front."""
    rng = np.random.default_rng(23)
    latent = rng.normal(0.0, 1.0, size=(4, 12, 12)).astype(np.float32)
    drawn = mean_images.latent_view([latent])
    for left, right in ((0, 1), (0, 2), (1, 2)):
        assert not np.allclose(drawn[..., left], drawn[..., right])
    for index in range(3):
        matched = np.corrcoef(latent[index].ravel(), drawn[..., index].ravel())[0, 1]
        assert float(matched) > 0.99


def test_a_latent_that_is_not_a_number_is_refused_rather_than_drawn_black():
    """A NaN takes its whole colour plane with it, and black says nothing.

    Centre and spread come out NaN, every pixel of the plane with them, and the
    cast to bytes writes an all-black plate that stands in the cell as "the set
    so far".
    """
    rng = np.random.default_rng(29)
    good = rng.normal(0.0, 1.0, size=(4, 8, 8)).astype(np.float32)
    for spoiled in (np.nan, np.inf, -np.inf):
        bad = good.copy()
        bad[0, 0, 0] = spoiled
        with pytest.raises(ValueError):
            mean_images.latent_view([bad, good])


def test_a_stored_latent_that_is_not_a_number_will_not_load(tmp_path):
    """Refused at the one place every caller comes through.

    Averaged such a file takes the whole set with it, and decoded it is
    undefined — so neither the drawing nor the overlay ever sees it.
    """
    path = tmp_path / "spoiled.npy"
    np.save(path, np.full((4, 8, 8), np.nan, dtype=np.float32), allow_pickle=False)
    with pytest.raises(ValueError):
        mean_images.load_latent(path)


def test_a_latent_of_fewer_than_three_channels_repeats_its_last_one():
    rng = np.random.default_rng(31)
    grey = mean_images.latent_view([rng.normal(0.0, 1.0, size=(1, 8, 8)).astype(np.float32)])
    assert np.allclose(grey[..., 0], grey[..., 1])
    assert np.allclose(grey[..., 1], grey[..., 2])

    two = mean_images.latent_view([rng.normal(0.0, 1.0, size=(2, 8, 8)).astype(np.float32)])
    assert not np.allclose(two[..., 0], two[..., 1])
    assert np.allclose(two[..., 1], two[..., 2])


def test_a_latent_without_channels_is_refused_by_name():
    """Not an IndexError out of the plane loop: a stated refusal."""
    with pytest.raises(ValueError):
        mean_images.latent_view([np.zeros((0, 8, 8), dtype=np.float32)])


def test_latents_of_two_measures_are_not_drawn_together():
    with pytest.raises(ValueError):
        mean_images.latent_view([np.zeros((4, 8, 8)), np.zeros((4, 16, 16))])


def test_the_preview_draws_the_running_mean(client, latent_runs, open_level):
    rng = np.random.default_rng(41)
    latent_runs("run_a", 0.0, array=rng.normal(0.0, 1.0, size=(4, 8, 8)))
    latent_runs("run_b", 0.0, array=rng.normal(0.0, 1.0, size=(4, 8, 8)))

    body = client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_a", "run_b"]}).get_json()

    assert body["status"] == "success"
    assert body["count"] == 2
    # The measure of the latent, not of the picture: the drawing is the tensor.
    drawn = _decode(body["preview"])
    assert drawn.shape == (8, 8, 3)
    # And it CARRIES the set. A plate of one value is what a constant latent
    # draws, and it would pass every assertion above while showing nothing.
    assert float(drawn.std()) > 1.0
    # No card was asked for anything — there is no decoder fixture in this test
    # at all, and a decode would have reached for one.


def test_the_preview_is_drawn_at_the_levels_that_check_pictures(
    client, latent_runs, open_level
):
    """A workshop runs at kids or youth, and the cell builds up there too.
    What is drawn is the tensor: at 1024 pixels 128 by 128, three of sixteen
    channels as three colours."""
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0)
    for level in ("kids", "youth"):
        open_level["level"] = level
        body = client.post('/api/latent-lab/mean-images/latent-preview',
                           json={"run_ids": ["run_a", "run_b"]}).get_json()
        assert body["preview"]
        assert body["count"] == 2


def test_a_picture_the_check_turned_back_stays_out_of_the_drawing(
    client, latent_runs, open_level, checked_run
):
    """The drawing is made of the pictures the platform would hand out: the
    rule `entity_cleared_for_delivery` answers by, over the run's own record."""
    open_level["level"] = "kids"
    checked_run("run_blocked", safe=False)
    body = client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_blocked"]}).get_json()
    assert body["preview"] is None
    assert body["count"] == 0

    checked_run("run_passed", safe=True)
    body = client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_blocked", "run_passed"]}).get_json()
    assert body["preview"]
    assert body["count"] == 1


def test_a_picture_still_being_checked_joins_the_drawing_one_step_later(
    client, open_level, checked_run
):
    """No verdict yet is no clearance: the run comes in when its picture has
    one, which is the seconds the check lasts. The answer says WHICH nothing it
    is, because the cell asks again for this one and stops asking for a row
    that keeps no latents."""
    open_level["level"] = "youth"
    checked_run("run_pending", safe=None)
    body = client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_pending"]}).get_json()
    assert body["preview"] is None
    assert body["count"] == 0
    assert body["why"] == "not_yet"


def test_the_answer_says_which_nothing_it_is(
    client, latent_runs, open_level, checked_run
):
    open_level["level"] = "kids"
    latent_runs("run_none", 2.0, meta=None)          # a row that keeps no latent
    assert client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_none"]}).get_json()["why"] == "no_latents"

    checked_run("run_blocked", safe=False)
    assert client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_blocked"]}).get_json()["why"] == "not_yet"

    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0, shape=(4, 16, 16))
    assert client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_a", "run_b"]}).get_json()["why"] == "mixed_set"


def test_a_level_that_did_not_resolve_draws_only_what_the_check_cleared(
    client, latent_runs, monkeypatch, checked_run
):
    import my_app.services.safety_level_resolver as resolver

    def boom():
        raise RuntimeError("the session is gone")

    monkeypatch.setattr(resolver, "resolve_safety_level", boom)
    checked_run("run_blocked", safe=False)
    body = client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_blocked"]}).get_json()
    assert body["preview"] is None

    latent_runs("run_a", 2.0)
    body = client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_a"]}).get_json()
    assert body["preview"]


def test_the_preview_says_nothing_for_a_row_that_keeps_no_latents(
    client, latent_runs, open_level
):
    """The ComfyUI rows keep none. That is ordinary and says nothing."""
    latent_runs("run_a", 2.0, meta=None)
    body = client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_a"]}).get_json()
    assert body["status"] == "success"
    assert body["preview"] is None
    assert body["count"] == 0


def test_the_preview_says_nothing_for_a_set_of_two_measures(
    client, latent_runs, open_level
):
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0, shape=(4, 16, 16))
    body = client.post('/api/latent-lab/mean-images/latent-preview',
                       json={"run_ids": ["run_a", "run_b"]}).get_json()
    assert body["preview"] is None


@pytest.mark.parametrize("run_ids", [None, [], "run_a", [""], [7], ["a"] * 51])
def test_the_preview_refuses_an_impossible_request(
    client, open_level, run_ids
):
    res = client.post('/api/latent-lab/mean-images/latent-preview',
                      json={"run_ids": run_ids})
    assert res.status_code == 400


def test_a_set_that_all_kept_its_latents_is_averaged_before_the_decoder(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """
    The mean is what the decode returned, and it was taken over the LATENTS.
    Relief and contact sheet stay what they are: they are read off the decoded
    singles and say what the set shares in its texture.
    """
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0)

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    ).get_json()

    assert body["mean_kind"] == "latent"
    assert body["count"] == 2
    assert np.all(_decode(body["mean"]) == 55)
    assert body["relief"] and body["sheet"]

    assert len(decoder["calls"]) == 1
    call = decoder["calls"][0]
    assert call["model_id"] == _LATENT_META["model_id"]
    assert call["pipeline_class"] == _LATENT_META["pipeline_class"]
    assert np.allclose(call["latent"], 4.0)


def test_a_set_of_one_is_the_picture_and_asks_for_no_decode(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """
    Nothing was averaged, so there is nothing to average before a decoder. The
    cell IS the recorded picture: decoding its latent again would spend the card
    — and a second image check — on a picture the run already holds and already
    passed.
    """
    one = _noise(seed=17)
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a"]},
    ).get_json()

    assert body["mean_kind"] == "pixel"
    assert body["count"] == 1
    assert decoder["calls"] == []
    assert open_level["calls"] == []
    assert np.array_equal(_decode(body["mean"]), one)


def test_one_run_without_a_latent_takes_the_whole_set_pixel_by_pixel(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """A mixed set is no error — it is what the rows without a latent path are."""
    one = _noise(seed=17)
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0, meta=None)

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    ).get_json()

    assert body["mean_kind"] == "pixel"
    assert decoder["calls"] == []
    # Two copies of one picture average to that picture.
    assert np.array_equal(_decode(body["mean"]), one)


def test_two_models_in_one_set_are_averaged_pixel_by_pixel(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """Latents of two models are not comparable numbers, and the answer says so."""
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0, meta={**_LATENT_META, "model_id": "another/model"})

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    ).get_json()

    assert body["mean_kind"] == "pixel"
    assert decoder["calls"] == []


def test_two_measures_in_one_set_are_averaged_pixel_by_pixel(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0, shape=(4, 16, 16))

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    ).get_json()

    assert body["mean_kind"] == "pixel"
    assert decoder["calls"] == []


def test_a_decode_that_failed_is_an_error_and_never_the_other_mean(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """
    Falling back to the pixel mean here would hand back a different picture
    under the same name, and the cell would report a sharpness it does not have.
    """
    from my_app.services.latent_decoder import LatentDecodeError

    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0)
    decoder["raises"] = LatentDecodeError("the decoder ran out of memory")

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    )
    assert res.status_code == 502
    body = res.get_json()
    assert body["status"] == "error"
    assert "the decoder ran out of memory" in body["error"]
    assert "mean" not in body


def test_a_card_that_is_taken_says_so_and_keeps_its_own_status(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """Busy is not broken: the same request works in a moment."""
    from my_app.services.gpu_lease_client import GpuBusyError

    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0)
    decoder["raises"] = GpuBusyError("a training holds the card", reason="holder")

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    )
    assert res.status_code == 503
    assert "busy" in res.get_json()["error"]
    assert "a training holds the card" in res.get_json()["error"]


def test_a_mean_the_check_turns_back_is_answered_and_not_recorded(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level, sitting, caplog
):
    """
    The decoded mean is a picture nobody has looked at, so it is checked like a
    generated one. A refusal is no failure — it is an answer, and nothing of the
    cell is written down.
    """
    import logging

    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0)
    open_level["level"] = "kids"
    open_level["answer"] = (False, "Bild nicht freigegeben", "a described picture")

    # `latent_runs` moved the storage; the sitting writes into its own.
    written_before = len(list(Path(sitting["base"]).glob("*/*/run_*")))
    caplog.set_level(logging.WARNING, logger="my_app.routes.mean_images_routes")

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {
                "session_id": "sitting_1",
                "model": "sd35_large",
                "model_label": "SD 3.5 Large",
                "axis": "seedFixed",
                "seed": 424242,
                "translation_en": "a house",
            },
        },
    )
    assert res.status_code == 200
    body = res.get_json()
    # The fields the rest of this platform blocks in, so one surface reads all
    # of its refusals the same way.
    assert body == {
        "status": "blocked",
        "blocked": True,
        "stage": "vlm_safety",
        "reason": "Bild nicht freigegeben",
        "vlm_description": "a described picture",
    }
    assert len(open_level["calls"]) == 1
    assert open_level["calls"][0][1] == "kids"
    # The checker reads a FILE, and the scratch it read is gone again.
    assert not Path(open_level["calls"][0][0]).exists()
    # Nothing of the cell was written.
    assert len(list(Path(sitting["base"]).glob("*/*/run_*"))) == written_before
    # This log line is the only trace on this side: the instrument keeps the
    # refusal per cell on the surface, and without the run ids nobody could say
    # afterwards WHICH pictures the blocked mean was taken from.
    said = "\n".join(r.getMessage() for r in caplog.records)
    assert "run_a" in said and "run_b" in said
    assert "kids" in said and "Bild nicht freigegeben" in said


def test_an_open_level_asks_no_image_check(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """The two levels that check a generated picture are the two checked here."""
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0)

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    ).get_json()

    assert body["mean_kind"] == "latent"
    assert open_level["calls"] == []


def test_the_recorded_cell_carries_the_kind_of_mean_it_holds(
    client, monkeypatch, sitting, tmp_path
):
    """
    A cell read back a year later has to say where its mean was taken: its
    parameters carry it, every plate carries it, and the account says it in
    words.
    """
    import my_app.routes.media_routes as media_routes
    from my_app.utils.media_ref import find_media_entities

    path = tmp_path / "image.png"
    Image.fromarray(_noise(seed=29).astype(np.uint8)).save(path)
    monkeypatch.setattr(media_routes, "_resolve_image",
                        lambda run_id, index: ((path, "png", 0), None))

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {
                "session_id": "sitting_1",
                "model": "commoncanvas_xl_c",
                "model_label": "CommonCanvas XL C",
                "axis": "seedFixed",
                "seed": 424242,
                "translation_en": "a house",
            },
        },
    ).get_json()

    assert body["mean_kind"] == "pixel"
    stored = _run_metadata(sitting["base"], body["run_id"])
    assert stored["parameters"]["mean_kind"] == "pixel"
    images = find_media_entities(stored["entities"], "image")
    assert [e["metadata"]["mean_kind"] for e in images] == ["pixel", "pixel", "pixel"]
    account = next(e for e in stored["entities"] if e["type"] == "output_text")
    said = (Path(next(Path(sitting["base"]).glob(f"*/*/{body['run_id']}")))
            / "final" / account["filename"]).read_text(encoding="utf-8")
    assert said.startswith("Mean image of 2 pictures, averaged pixel by pixel.")


# ---------------------------------------------------------------------------
# A latent that is THERE and cannot be used
# ---------------------------------------------------------------------------

def _latent_file(recorder) -> Path:
    """The one .npy a run of the fixture wrote."""
    written = sorted(Path(recorder.final_folder).glob("*.npy"))
    assert len(written) == 1, f"expected one latent, found {written}"
    return written[0]


def test_a_latent_that_will_not_load_names_its_run_and_fails(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """
    A truncated file is a fault of this platform's own store, not a run that
    kept nothing. Falling through to the pixel mean would answer it with a
    DIFFERENT picture under the name of the one that was asked for.
    """
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    broken = latent_runs("run_b", 6.0)
    _latent_file(broken).write_bytes(b"\x93NUMPY-and-then-nothing")

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    )
    assert res.status_code == 502
    body = res.get_json()
    assert body["status"] == "error"
    assert "run_b" in body["error"]
    assert decoder["calls"] == []


def test_a_stored_latent_that_names_no_model_is_not_quietly_a_pixel_mean(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """
    Both names come out of the record. An entity that carries neither cannot be
    decoded by anything, and guessing a model here is exactly what this platform
    does not do — so the request fails and says which run is missing what.
    """
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0,
                meta={k: v for k, v in _LATENT_META.items() if k != "model_id"})

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    )
    assert res.status_code == 502
    assert "run_b" in res.get_json()["error"]
    assert decoder["calls"] == []


def test_a_run_that_kept_no_latent_at_all_is_still_the_ordinary_case(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """
    Having none and having a broken one are different states. This is the first:
    it is what every ComfyUI row is in, and it costs the latent mean and nothing
    else.
    """
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0, meta=None)

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    ).get_json()
    assert body["mean_kind"] == "pixel"
    assert body["count"] == 2
    assert decoder["calls"] == []


def test_two_pipeline_classes_in_one_set_are_averaged_pixel_by_pixel(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level
):
    """
    One model name is not enough to make a set one set. Two pipeline classes are
    two ways of reading the same numbers, and the decode would be done by one of
    them for latents the other wrote.
    """
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0,
                meta={**_LATENT_META, "pipeline_class": "AnotherPipelineForThisTest"})

    body = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={"run_ids": ["run_a", "run_b"]},
    ).get_json()
    assert body["mean_kind"] == "pixel"
    assert decoder["calls"] == []


def test_an_image_check_that_could_not_run_is_never_a_pass(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level, sitting
):
    """
    The decode is already spent and the picture exists; what is missing is a
    judgement on it. An absent judgement is not a pass, and it is not a refusal
    either — it is this platform saying it could not look.
    """
    import my_app.utils.vlm_safety as vlm_safety

    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0)
    open_level["level"] = "kids"

    def breaks(image_path, safety_level):
        raise OSError("no space left on device")

    monkeypatch.setattr(vlm_safety, "vlm_safety_check", breaks)
    written_before = len(list(Path(sitting["base"]).glob("*/*/run_*")))

    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {"session_id": "sitting_1", "model": "sd35_large",
                       "model_label": "SD 3.5 Large", "axis": "seedFixed",
                       "seed": 424242, "translation_en": "a house"},
        },
    )
    assert res.status_code == 500
    body = res.get_json()
    assert body["status"] == "error"
    assert "no space left on device" in body["error"]
    assert "blocked" not in body
    assert len(list(Path(sitting["base"]).glob("*/*/run_*"))) == written_before


def test_the_same_set_that_passes_the_check_is_recorded(
    client, monkeypatch, tmp_path, latent_runs, decoder, open_level, sitting
):
    """
    The guard on the two tests above: they both assert that NOTHING was written,
    and that assertion is worth nothing unless the identical set, checked and
    passed, does write. It writes.
    """
    _one_image(monkeypatch, tmp_path)
    latent_runs("run_a", 2.0)
    latent_runs("run_b", 6.0)
    open_level["level"] = "kids"
    open_level["answer"] = (True, "", "")

    before = len(list(Path(sitting["base"]).glob("*/*/run_*")))
    res = client.post(
        '/api/latent-lab/mean-images/overlay',
        json={
            "run_ids": ["run_a", "run_b"],
            "record": {"session_id": "sitting_1", "model": "sd35_large",
                       "model_label": "SD 3.5 Large", "axis": "seedFixed",
                       "seed": 424242, "translation_en": "a house"},
        },
    )
    assert res.status_code == 200
    assert res.get_json()["run_id"]
    assert len(list(Path(sitting["base"]).glob("*/*/run_*"))) == before + 1


def test_the_answer_carries_the_measure_of_the_mean_it_returns():
    """
    The decoder answers in the model's own measure, which is not the measure the
    singles were read at. `width`/`height` describe the picture that is handed
    back; `resized` goes on describing the STACK the relief and sheet came from.
    """
    made = _noise(seed=41)
    elsewhere = mean_images.to_png_bytes(np.full((1024, 1024, 3), 77.0))
    composed = mean_images.compose([made] * 3, mean_png=elsewhere)

    assert (composed["width"], composed["height"]) == (1024, 1024)
    assert _decode(composed["mean"]).shape[:2] == (1024, 1024)
    # Read off the singles, unchanged, and the stack was of one measure.
    assert _decode(composed["relief"]).shape[:2] == (64, 64)
    assert composed["resized"] is False
