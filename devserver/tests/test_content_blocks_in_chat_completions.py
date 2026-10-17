#!/usr/bin/env python3
"""What the chat-completions reader must make of a content BLOCK.

Measured 2026-09-22. Mistral serves Z.ai's GLM 5.3 as `zai-glm-5-3`, and that
model answers in blocks inside the chat-completions envelope: `content` is a
list of {"type": "thinking", "thinking": [{"type": "text", "text": ...}]} and
{"type": "text", "text": ...} objects rather than a string, in the streamed
delta as well as in a finished message. The reader did `answer.content += piece`
and raised TypeError on the first frame that carried one, so every role of this
installation's Mistral column — Stage 1, Stage 2, Stage 3, Persona, Resona, the
chat helper, knowledge processing — failed before a word of the answer arrived.
Mistral's other models answer with a string, `zai-glm-5-2` among them, so the
shape arrived on one model and not on a whole column.

Three things have to hold and this file holds them shut.

  * A block list is read at all, in every nesting the provider uses.
  * Its reasoning stays OUT of the answer text. test_cloud_transport_callers
    guards the same for the other dialect: the pipeline engine refuses to let a
    model's reasoning stand in for an answer it never gave, and that refusal is
    only possible while the two are apart.
  * NOTHING is dropped in silence. That one carries the weight. Where the answer
    text is empty and the reasoning is not, the chat surface shows the reasoning
    in its place — its own stated policy, at routes/chat_routes — so an answer
    block this reader fails to read does not reach the room as a gap. It reaches
    it as the model's reasoning, standing in for the answer the model did give,
    put there by the reader. A shape that cannot be read is therefore logged,
    once per stream, and a shape that can be read is read.

Nothing here reaches a provider. Run:
  python3 -m pytest devserver/tests/test_content_blocks_in_chat_completions.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services.openai_style_stream import _Answer, _ChatCompletionsGrammar


def frame(**delta) -> str:
    return json.dumps({"choices": [{"index": 0, "delta": delta}]})


def read(*deltas) -> _Answer:
    """Run the deltas through one grammar and return what it wrote."""
    grammar, answer = _ChatCompletionsGrammar(), _Answer()
    for d in deltas:
        grammar.feed(frame(**d), answer)
    return answer


# --------------------------------------------------------------------------
# The shapes that carry an answer
# --------------------------------------------------------------------------

def test_a_string_content_is_still_read_as_the_answer():
    assert read({"content": "Bl"}, {"content": "au"}).content == "Blau"


def test_a_text_block_is_read_instead_of_raising():
    """The frame that used to raise TypeError, as zai-glm-5-3 sends it."""
    assert read({"content": [{"type": "text", "text": "Blau"}]}).content == "Blau"


def test_a_text_block_that_nests_the_way_a_thinking_block_does_is_still_read():
    """`thinking` holds a list of text parts on this provider. Nothing says
    `text` may not, and a block read as empty does not reach the room as a
    short answer — it reaches it as the reasoning of the same frame."""
    assert read({"content": [{"type": "text",
                              "text": [{"type": "text", "text": "Bl"},
                                       {"type": "text", "text": "au"}]}]}).content == "Blau"


def test_bare_strings_inside_a_content_list_are_read_as_the_answer():
    assert read({"content": ["Bl", "au"]}).content == "Blau"


# --------------------------------------------------------------------------
# The reasoning, and that it stays where it belongs
# --------------------------------------------------------------------------

def test_the_reasoning_of_a_block_list_stays_out_of_the_answer():
    answer = read(
        {"content": [{"type": "thinking",
                      "thinking": [{"type": "text", "text": "Der Himmel ist"}],
                      "closed": True}]},
        {"content": [{"type": "thinking",
                      "thinking": [{"type": "text", "text": " meist blau."}]}]},
        {"content": [{"type": "text", "text": "Blau"}]})
    assert answer.content == "Blau"
    assert answer.thinking == "Der Himmel ist meist blau."


def test_a_thinking_block_that_holds_a_plain_string_is_read_too():
    assert read({"content": [{"type": "thinking", "thinking": "hm"}]}).thinking == "hm"


def test_a_reasoning_content_block_is_recognised_as_reasoning():
    """The platform's other reader already knows this block type and reads its
    text out of reasoningText (the Bedrock half of routes/chat_routes). One
    platform, one answer to which block is reasoning."""
    answer = read({"content": [{"type": "reasoning_content",
                                "reasoningText": {"text": "hm"}}]})
    assert answer.content == ""
    assert answer.thinking == "hm"


def test_the_separate_reasoning_field_of_the_other_providers_still_arrives():
    assert read({"content": "Blau", "reasoning_content": "kurz überlegt"}).thinking \
        == "kurz überlegt"


def test_the_reasoning_field_in_the_block_shape_does_not_raise_either():
    """The line below the one that was fixed had the same fault: a provider
    that sends a list in `content` is not promised to send a string here."""
    answer = read({"reasoning_content": [{"type": "text", "text": "gedacht"}]})
    assert answer.thinking == "gedacht"
    assert answer.content == ""


def test_the_pieces_handed_on_are_the_answer_and_never_the_reasoning():
    """What goes out over the wire as ('token', text) is the answer alone.

    A reasoning block that leaked into it would be read on the surface as the
    model's answer, and the reader would have put it there.
    """
    grammar, answer = _ChatCompletionsGrammar(), _Answer()
    thought = frame(content=[{"type": "thinking",
                              "thinking": [{"type": "text", "text": "erst denken"}]}])
    said = frame(content=[{"type": "text", "text": "Blau"}])
    assert list(grammar.feed(thought, answer)[0]) == []
    assert list(grammar.feed(said, answer)[0]) == ["Blau"]


# --------------------------------------------------------------------------
# Nothing raises out of the frame loop, and nothing is dropped in silence
# --------------------------------------------------------------------------

@pytest.mark.parametrize("content, why", [
    ([{"type": ["text"], "text": "Blau"}], "a type that cannot go in a set"),
    ([{"type": {}, "text": "Blau"}], "a type that cannot go in a set either"),
    ([{"type": "text", "text": {"v": "Blau"}}], "a text payload in no known shape"),
    ([{"type": "tool_use", "name": "x"}], "a block type nobody here knows"),
    ([17], "a list item that is not a block"),
    ({"text": "Blau"}, "a content that is neither string nor list"),
    (42, "a content that is a number"),
])
def test_a_shape_this_reader_cannot_place_is_logged_and_never_raises(content, why, caplog):
    grammar, answer = _ChatCompletionsGrammar(), _Answer()
    with caplog.at_level("WARNING"):
        grammar.feed(frame(content=content), answer)   # must not raise
    assert answer.content == "", why
    assert [r for r in caplog.records if "[STREAM]" in r.message], \
        f"{why}: dropped without a word"


def test_a_shape_is_reported_once_per_stream_and_not_once_per_frame(caplog):
    """The shape repeats on every frame, and a log that repeats with it buries
    the one thing it has to say."""
    grammar, answer = _ChatCompletionsGrammar(), _Answer()
    with caplog.at_level("WARNING"):
        for _ in range(5):
            grammar.feed(frame(content=[{"type": "somenewthing"}]), answer)
    assert sum("somenewthing" in r.message for r in caplog.records) == 1


def test_the_next_stream_reports_the_same_shape_again(caplog):
    """The silence is per stream, so that a shape stays visible on every run
    rather than on the first one this process happened to serve."""
    with caplog.at_level("WARNING"):
        for _ in range(2):
            _ChatCompletionsGrammar().feed(frame(content=[{"type": "somenewthing"}]),
                                           _Answer())
    assert sum("somenewthing" in r.message for r in caplog.records) == 2


def test_reasoning_arriving_in_both_shapes_at_once_is_kept_and_reported(caplog):
    """Both are kept — dropping one would lose reasoning — and the frame says
    so, because no provider in the table sends both and one that starts to is
    worth seeing."""
    grammar, answer = _ChatCompletionsGrammar(), _Answer()
    with caplog.at_level("WARNING"):
        grammar.feed(frame(content=[{"type": "thinking", "thinking": "A"}],
                           reasoning_content="B"), answer)
    assert answer.thinking == "AB"
    assert any("at once" in r.message for r in caplog.records)


def test_an_empty_opening_frame_writes_nothing_and_says_nothing(caplog):
    """Mistral opens a block stream with content "" twice before the first
    block. Neither may count as a piece of the answer, and neither is a shape
    worth a log line."""
    grammar, answer = _ChatCompletionsGrammar(), _Answer()
    with caplog.at_level("WARNING"):
        grammar.feed(frame(role="assistant", content=""), answer)
        grammar.feed(frame(index=0, content=""), answer)
        grammar.feed(frame(index=0), answer)
    assert (answer.content, answer.thinking) == ("", "")
    assert [r for r in caplog.records if "[STREAM]" in r.message] == []
