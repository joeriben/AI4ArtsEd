#!/usr/bin/env python3
"""What a chat turn checks.

Every text the turn takes from the request into the model's prompt passes the
intake before any model is asked: the message, the page state, the context's
texts, the notes on the board, the list of media on the page and each line of
the history. The intake asks about names and addresses and about what the text
says (kind "chat"). A refusal ends the turn with status 403 and the block
message. A refused line of the history is left out of the prompt instead, so
that one refused message does not end every turn after it.

What a chat model writes is not checked (2026-11-08): the answer goes out as it
is written, and the cards and the backs of what a tool call built go out as
they are. The thinking goes out above youth; at kids and youth it is not sent,
and a reply that is only the thinking counts as none (2026-11-14). The comparisons of the Latent Lab, on the same turn, keep
the result check: their answer passes it whole before anything of it leaves.
They have no tools and send no thinking, whatever other mode a request names.

A tool runs only when the turn offered it. A turn that offered no tools and is
answered with tool calls ends with an error.

A picture sent as data comes from no run and no upload; it passes the image
intake before the turn goes on.

The checks, the chat model and the tools are stand-ins; nothing here asks a
model.
"""
import json
import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.routes import chat_routes
from my_app.services.safety_gate import (
    CHECKPOINT_INTAKE, CHECKPOINT_RESULT, REASON_CONTENT, REASON_PERSONAL_DATA, Verdict,
)

REFUSED = "Erika Mustermann, Hauptstrasse 5"


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    with app.test_request_context("/api/chat", json={}):
        yield


@pytest.fixture
def gate(monkeypatch):
    """The intake, recorded where it is reached. A text holding REFUSED is refused."""
    reached = []

    def refusal(level, field):
        return Verdict(False, CHECKPOINT_INTAKE, level, field, REASON_PERSONAL_DATA, "a name")

    def intake_texts(fields, *, level, kind="text"):
        reached.append(("texts", dict(fields), level, kind))
        for name, text in fields.items():
            if REFUSED in str(text or ""):
                return refusal(level, name)
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def intake(material, *, level, kind, field):
        reached.append(("line", material, level, field, kind))
        if REFUSED in str(material or ""):
            return refusal(level, field)
        return Verdict(True, CHECKPOINT_INTAKE, level, field)

    monkeypatch.setattr(chat_routes, "check_intake_texts", intake_texts)
    monkeypatch.setattr(chat_routes, "check_intake", intake)
    return reached


@pytest.fixture
def model(monkeypatch):
    """The chat model: what it was handed, and a short answer."""
    calls = []

    def helper(**kwargs):
        calls.append(kwargs)
        yield ("token", "Gut.")
        yield ("result", {"content": "Gut.", "thinking": None, "tool_calls": None,
                          "model_used": "stand-in/one"})

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    return calls


def turn(data, level="youth"):
    return list(chat_routes._chat_events(data, level))


def fields_checked(gate):
    return [entry[1] for entry in gate if entry[0] == "texts"]


def test_a_refused_message_ends_the_turn_before_any_model(app_ctx, gate, model, monkeypatch):
    described = []
    monkeypatch.setattr(chat_routes, "_brought_captions",
                        lambda items, level: described.append(items) or {})
    evs = turn({"message": f"Schreib an {REFUSED}",
                "context": {"resona_mode": True, "language": "de", "device_id": "t"}})
    assert [e["type"] for e in evs] == ["error"]
    assert evs[0]["status"] == 403
    assert evs[0]["safety_block"]["checkpoint"] == "intake"
    assert evs[0]["safety_block"]["field"] == "message"
    # Neither the chat model nor the one that describes brought pictures.
    assert model == [] and described == []


def test_every_text_of_the_request_reaches_the_intake(app_ctx, gate, model):
    turn({
        "message": "Was siehst du?",
        "draft_context": "Eingabe: ein Haus am See",
        "context": {"input_text": "ein Haus am See",
                    "interception_text": "Ein Haus, vom Wasser aus gesehen",
                    "config_name": "sd35_large"},
        "surface_media": [{"run_id": "run_123", "label": "Zeile 1, Spalte 2"}],
    })
    fields = fields_checked(gate)[0]
    assert fields["message"] == "Was siehst du?"
    assert fields["draft_context"] == "Eingabe: ein Haus am See"
    assert "ein Haus am See" in fields["context"]
    assert "Ein Haus, vom Wasser aus gesehen" in fields["context"]
    # The list as the request supplies it: the names the page gives and the
    # ids, without the platform's text around them.
    assert "Zeile 1, Spalte 2" in fields["surface_media"]
    assert "run_123" in fields["surface_media"]
    assert "MEDIA ON THIS SURFACE" not in fields["surface_media"]


def test_the_intake_asks_about_what_every_text_says(app_ctx, gate, model):
    turn({"message": "Was siehst du?", "draft_context": "Eingabe: ein Haus am See",
          "history": [{"role": "user", "content": "vorher"},
                      {"role": "assistant", "content": "Ein ruhiges Motiv."}]})
    assert [e[3] for e in gate if e[0] == "texts"] == ["chat"]
    assert [e[4] for e in gate if e[0] == "line"] == ["chat", "chat"]


def test_the_line_in_which_the_page_says_what_it_is_goes_on_its_own(app_ctx, gate, model):
    page = "Was diese Seite ist: Die Seite Together, eine Begleitung für Workshops."
    turn({"message": "Hallo",
          "draft_context": f"Aktive Ansicht: resona\n{page}\nEingabe: ein Haus"})
    fields = fields_checked(gate)[0]
    assert fields["page_description"] == page
    assert fields["draft_context"] == "Aktive Ansicht: resona\n\nEingabe: ein Haus"
    # Checked in two parts, handed to the model whole.
    assert page in model[0]["messages"][0]["content"]


def test_a_refused_page_state_ends_the_turn(app_ctx, gate, model):
    evs = turn({"message": "Was meinst du?", "draft_context": f"Eingabe: {REFUSED}"})
    assert evs[-1]["type"] == "error"
    assert evs[-1]["safety_block"]["field"] == "draft_context"
    assert model == []


def test_the_notes_on_the_board_reach_the_intake(app_ctx, gate, model, monkeypatch):
    monkeypatch.setattr(chat_routes, "_brought_captions", lambda items, level: {})
    evs = turn({"message": "Was liegt da?",
                "context": {"resona_mode": True, "language": "de", "device_id": "t",
                            "brought_items": [{"kind": "text",
                                               "excerpt": f"Notiz: {REFUSED}"}]}})
    assert fields_checked(gate)[0]["notes"] == f"Notiz: {REFUSED}"
    assert evs[-1]["type"] == "error"
    assert evs[-1]["safety_block"]["field"] == "notes"
    assert model == []


def test_a_comparison_system_prompt_passes_the_intake_as_written(app_ctx, gate, model):
    prompt = "Du bist ein Dichter.\n\nAntworte in Versen."
    turn({"message": "Hallo",
          "context": {"system_prompt_compare_mode": True, "custom_system_prompt": prompt}})
    assert fields_checked(gate)[0]["context"] == prompt
    # Checked, not rewritten: the model is handed the prompt as it was written.
    assert model[0]["messages"][0] == {"role": "system", "content": prompt}


def test_each_line_of_the_history_passes_the_intake(app_ctx, gate, model):
    history = [{"role": "user", "content": "Ein Haus am See"},
               {"role": "assistant", "content": "Ein ruhiges Motiv."}]
    turn({"message": "Und weiter?", "history": history})
    assert [(e[1], e[3]) for e in gate if e[0] == "line"] == [
        ("Ein Haus am See", "history"), ("Ein ruhiges Motiv.", "history")]


def test_a_refused_line_of_the_history_stays_out_of_the_prompt(app_ctx, gate, model):
    evs = turn({"message": "Und weiter?",
                "history": [{"role": "user", "content": "Ein Haus am See"},
                            {"role": "assistant", "content": "Ein ruhiges Motiv."},
                            {"role": "user", "content": f"Schreib an {REFUSED}"},
                            {"role": "assistant", "content": "Das ging nicht."}]})
    handed = [m["content"] for m in model[0]["messages"] if m["role"] != "system"]
    assert not any(REFUSED in c for c in handed)
    assert "Ein Haus am See" in handed[0]
    # The turn goes on: one refused message does not end every turn after it.
    assert evs[-1]["type"] == "done"


def test_the_level_of_the_view_reaches_every_intake(app_ctx, gate, model):
    turn({"message": "Hallo", "history": [{"role": "user", "content": "vorher"}]},
         level="adult")
    assert gate and {entry[2] for entry in gate} == {"adult"}


def test_the_blocking_mouth_answers_a_refusal_with_403(gate, model, monkeypatch):
    monkeypatch.setattr(chat_routes, "resolve_safety_level", lambda: "kids")
    app = Flask(__name__)
    with app.test_request_context("/api/chat", json={"message": f"An {REFUSED}"}):
        response, status = chat_routes.chat()
        body = response.get_json()
    assert status == 403
    assert body["safety_block"]["field"] == "message"
    assert gate[0][2] == "kids"
    assert model == []


# ── What the model writes ───────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def released_not_recorded(monkeypatch):
    """The cache of released texts stays untouched. A test that asks for
    `remembered` gets the recording one instead: pytest sets up autouse
    fixtures first."""
    monkeypatch.setattr(chat_routes, "remember_chat_reply",
                        lambda text, *, level: None)


@pytest.fixture
def remembered(monkeypatch):
    kept = []
    monkeypatch.setattr(chat_routes, "remember_chat_reply",
                        lambda text, *, level: kept.append((text, level)))
    return kept


@pytest.fixture
def no_result_check(monkeypatch):
    """The result check fails every test that reaches it."""
    def reached(*args, **kwargs):
        raise AssertionError("a chat turn asked the result check")

    monkeypatch.setattr(chat_routes, "check_result_text", reached)


@pytest.fixture
def results(monkeypatch):
    """The result check, recorded. A text holding "VERBOTEN" is refused."""
    log = []

    def check(text, *, level, field="text"):
        log.append((field, text, level))
        if "VERBOTEN" in str(text or ""):
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT, "nein")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(chat_routes, "check_result_text", check)
    return log


class _Registry:
    """The tools these tests call, offered in every scope; each answers that it
    worked."""

    NAMES = ("remember", "canvas_graph_library", "run_canvas_graph", "generate_media")

    def get_openai_format(self, scope=None):
        return [{"type": "function", "function": {"name": name}} for name in self.NAMES]

    def list_names(self):
        return list(self.NAMES)

    def execute(self, name, args, context=None, *, level=None, language=None):
        return "ok"


@pytest.fixture
def tools(monkeypatch):
    from my_app.services import tool_registry
    monkeypatch.setattr(tool_registry, "get_tool_registry", lambda: _Registry())
    return tool_registry


def plays(monkeypatch, *rounds):
    """The chat model, playing the given rounds in order: (pieces, end), where
    the end is a result or an exception raised after the pieces."""
    seen = {"round": 0}

    def helper(**kwargs):
        pieces, end = rounds[min(seen["round"], len(rounds) - 1)]
        seen["round"] += 1
        for piece in pieces:
            yield ("token", piece)
        if isinstance(end, BaseException):
            raise end
        yield ("result", end)

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    return seen


def answer(content, tool_calls=None, thinking=None):
    return {"content": content, "thinking": thinking, "tool_calls": tool_calls,
            "model_used": "stand-in/one"}


def call(name, **args):
    return [{"id": "call_1", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]


@pytest.mark.parametrize("level", ["kids", "youth", "adult", "research"])
def test_the_answer_goes_out_as_it_is_written(app_ctx, gate, no_result_check, monkeypatch,
                                              level):
    plays(monkeypatch, (["Erster ", "Absatz.\n\nZwei", "ter Absatz."],
                        answer("Erster Absatz.\n\nZweiter Absatz.")))
    evs = turn({"message": "Hallo"}, level=level)
    assert [(e["type"], e.get("text")) for e in evs[:-1]] == [
        ("token", "Erster "), ("token", "Absatz.\n\nZwei"), ("token", "ter Absatz.")]
    assert evs[-1]["type"] == "done"
    assert evs[-1]["reply"] == "Erster Absatz.\n\nZweiter Absatz."


def test_an_answer_written_in_one_piece_travels_in_done(app_ctx, gate, no_result_check,
                                                        monkeypatch):
    plays(monkeypatch, ([], answer("Eins.\n\nZwei.\n")))
    evs = turn({"message": "Hallo"})
    assert [e["type"] for e in evs] == ["done"]
    assert evs[-1]["reply"] == "Eins.\n\nZwei."


def test_a_cut_answer_ships_what_it_wrote(app_ctx, gate, no_result_check, monkeypatch):
    plays(monkeypatch, (["Halb ", "fertig"], ConnectionError("reset")))
    evs = turn({"message": "Hallo"})
    assert [e["type"] for e in evs] == ["token", "token", "done"]
    assert evs[-1]["reply"] == "Halb fertig"
    assert evs[-1]["broke_off"] == "reset"


@pytest.mark.parametrize("level", ["adult", "research"])
def test_the_thinking_goes_out_as_written_above_youth(app_ctx, gate, no_result_check,
                                                      monkeypatch, level):
    plays(monkeypatch, (["Gut."], answer("Gut.", thinking="Erst lesen.")))
    assert turn({"message": "Hallo"}, level=level)[-1]["thinking"] == "Erst lesen."


@pytest.mark.parametrize("level", ["kids", "youth"])
def test_the_thinking_is_not_sent_at_kids_and_youth(app_ctx, gate, no_result_check,
                                                    monkeypatch, level):
    plays(monkeypatch, (["Gut."], answer("Gut.", thinking="Erst lesen.")))
    evs = turn({"message": "Hallo"}, level=level)
    assert evs[-1]["type"] == "done" and evs[-1]["reply"] == "Gut."
    assert evs[-1]["thinking"] is None
    assert "Erst lesen." not in json.dumps(evs)


@pytest.mark.parametrize("level, ends", [
    ("kids", "error"), ("youth", "error"), ("adult", "done")])
def test_a_reply_that_is_only_the_thinking(app_ctx, gate, no_result_check, monkeypatch,
                                           level, ends):
    """call_chat_helper_stream hands on the reasoning of a model that reasoned and
    then said nothing as its reply; at kids and youth that is no reply."""
    plays(monkeypatch, ([], answer("Erst lesen.", thinking="Erst lesen.")))
    evs = turn({"message": "Hallo"}, level=level)
    assert [e["type"] for e in evs] == [ends]
    assert ("Erst lesen." in json.dumps(evs)) is (ends == "done")


@pytest.mark.parametrize("level, withdrawn", [
    ("kids", False), ("youth", False), ("adult", True)])
def test_a_round_of_reasoning_is_no_draft_the_evidence_duty_withdraws(
        app_ctx, gate, no_result_check, tools, monkeypatch, level, withdrawn):
    """A draft that fails the evidence duty is withdrawn into the room and
    handed back to the model. At kids and youth a round that is only the
    reasoning is no draft: nothing of it goes out or back."""
    from my_app.services import evidence_duty
    monkeypatch.setattr(evidence_duty, "validate",
                        lambda text, ledger, user_text=None: ["v"] if text.strip() else [])
    sent = []

    def helper(**kwargs):
        sent.append(json.dumps(kwargs["messages"]))
        if len(sent) == 1:
            yield ("result", answer("Ich denke nach.", thinking="Ich denke nach."))
        else:
            yield ("result", answer("Gut."))

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    evs = turn({"message": "Hallo", "context": {"resona_mode": True, "language": "de",
                                                "device_id": "t"}}, level=level)
    said = json.dumps(evs) + " ".join(sent[1:])
    assert ("Ich denke nach." in said) is withdrawn
    assert ("withdraw" in [e["type"] for e in evs]) is withdrawn
    assert evs[-1]["type"] == ("done" if withdrawn else "error")


def test_a_card_in_the_models_words_goes_out_as_written(app_ctx, gate, no_result_check,
                                                        tools, monkeypatch):
    plays(monkeypatch,
          ([], answer("", call("remember", kind="Notiz", content="Die Gruppe mag Klang."))),
          (["Notiert."], answer("Notiert.")))
    # Cards are laid only by a turn with a board, which is Together's
    # (2026-11-15); remember is Together's tool.
    evs = turn({"message": "merk dir das",
                "context": {"resona_mode": True, "language": "de", "device_id": "t"}})
    assert "entity" in [e["type"] for e in evs]
    assert evs[-1]["type"] == "done"


def test_the_back_of_a_medium_goes_out_as_written(app_ctx, gate, no_result_check, tools,
                                                  monkeypatch):
    plays(monkeypatch,
          ([], answer("", call("generate_media", config_id="sd35_large", prompt="ein Haus",
                               motivation="zum Vergleich"))),
          (["Fertig."], answer("Fertig.")))
    done = turn({"message": "mach ein Bild"})[-1]
    assert done["type"] == "done"
    assert [(m["prompt"], m["motivation"]) for m in done["generated_media"]] == [
        ("ein Haus", "zum Vergleich")]


def test_an_apparatus_is_handed_over_as_built(app_ctx, gate, no_result_check, tools,
                                              monkeypatch):
    graph = {"title": "Zwei Wege", "motivation": "zum Vergleich", "summary": "ein Bild",
             "intent_id": "gi_1", "workflow": {"nodes": []}}
    monkeypatch.setattr(tools, "take_authored_graph", lambda: graph)
    plays(monkeypatch,
          ([], answer("", call("run_canvas_graph", title="x", motivation="y", graph={}))),
          (["Gebaut."], answer("Gebaut.")))
    evs = turn({"message": "bau etwas"})
    assert [e["graph"] for e in evs if e["type"] == "graph"] == [graph]
    assert evs[-1]["generated_graphs"] == [graph]


def test_a_tool_rounds_preamble_is_taken_back(app_ctx, gate, no_result_check, tools,
                                              monkeypatch):
    plays(monkeypatch,
          (["Ich sehe kurz nach."],
           answer("Ich sehe kurz nach.", call("remember", kind="Notiz", content="x"))),
          (["Gefunden."], answer("Gefunden.")))
    evs = turn({"message": "schau nach"})
    assert [e["type"] for e in evs][:2] == ["token", "discard"]
    assert evs[-1]["reply"] == "Gefunden."


def test_the_answer_is_remembered_at_the_level_of_the_view(app_ctx, gate, remembered,
                                                           monkeypatch):
    plays(monkeypatch, (["Gut.\n"], answer("Gut.\n")))
    turn({"message": "Hallo"}, level="adult")
    assert remembered == [("Gut.", "adult")]


# ── The comparisons of the Latent Lab ───────────────────────────────────────

COMPARISONS = [{"system_prompt_compare_mode": True, "custom_system_prompt": "Du bist ein Dichter."},
               {"llm_model_compare_mode": True},
               {"temperature_compare_mode": True}]


@pytest.mark.parametrize("context", COMPARISONS)
def test_a_comparisons_answer_passes_the_result_check_whole_before_it_leaves(
        app_ctx, gate, results, monkeypatch, context):
    plays(monkeypatch, (["Erster ", "Absatz.\n\nZweiter."], answer("Erster Absatz.\n\nZweiter.")))
    evs = turn({"message": "Hallo", "context": context}, level="kids")
    assert [e["type"] for e in evs] == ["done"]
    assert evs[-1]["reply"] == "Erster Absatz.\n\nZweiter."
    assert results == [("reply", "Erster Absatz.\n\nZweiter.", "kids")]


def test_a_refused_comparison_answer_ends_the_turn(app_ctx, gate, results, monkeypatch):
    plays(monkeypatch, (["Das ist ", "VERBOTEN."], answer("Das ist VERBOTEN.")))
    evs = turn({"message": "Hallo", "context": COMPARISONS[0]})
    assert [e["type"] for e in evs] == ["error"]
    assert evs[0]["status"] == 403
    assert evs[0]["safety_block"]["checkpoint"] == "result"
    assert evs[0]["safety_block"]["field"] == "reply"


def test_a_comparison_has_no_tools_whatever_else_the_request_names(app_ctx, gate, results,
                                                                    monkeypatch):
    sent = []

    def helper(**kwargs):
        sent.append(kwargs)
        yield ("result", answer("Gut."))

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    monkeypatch.setattr(chat_routes, "_brought_captions", lambda items, level: {})
    evs = turn({"message": "Hallo",
                "context": {**COMPARISONS[1], "resona_mode": True, "language": "de",
                            "device_id": "t"}}, level="kids")
    assert evs[-1]["type"] == "done"
    assert sent[0]["tools"] is None
    assert results == [("reply", "Gut.", "kids")]


def test_a_comparison_sends_no_thinking_and_does_not_check_it(app_ctx, gate, results,
                                                              monkeypatch):
    plays(monkeypatch, (["Gut."], answer("Gut.", thinking="VERBOTEN")))
    evs = turn({"message": "Hallo", "context": COMPARISONS[1]}, level="kids")
    assert [e["type"] for e in evs] == ["done"]
    assert evs[-1]["reply"] == "Gut."
    assert evs[-1]["thinking"] is None
    assert results == [("reply", "Gut.", "kids")]


def test_a_picture_sent_as_data_passes_the_image_intake(app_ctx, gate, model):
    picture = f"data:image/png;base64,{REFUSED}"
    evs = turn({"message": "Was siehst du?", "image_path": picture}, level="kids")
    assert [e["type"] for e in evs] == ["error"]
    assert evs[0]["status"] == 403
    assert evs[0]["safety_block"]["field"] == "image"
    assert ("line", picture, "kids", "image", "image") in gate
    assert model == []


def _recording(monkeypatch, offered):
    """A registry that offers `offered` and records what it is asked to run."""
    ran = []

    class Recording(_Registry):
        NAMES = tuple(offered)

        def execute(self, name, args, context=None, *, level=None, language=None):
            ran.append(name)
            return "ok"

    from my_app.services import tool_registry
    monkeypatch.setattr(tool_registry, "get_tool_registry", lambda: Recording())
    return ran


def test_a_tool_the_turn_did_not_offer_is_not_run(app_ctx, gate, no_result_check,
                                                  monkeypatch):
    """The registry holds every tool, and a provider can name one it was not given."""
    ran = _recording(monkeypatch, ["remember"])
    rounds = [answer("", call("view_run", run_id="r1")), answer("Fertig.")]
    sent = []

    def helper(**kwargs):
        sent.append(kwargs)
        yield ("result", rounds[len(sent) - 1])

    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", helper)
    evs = turn({"message": "zeig den Lauf"})
    assert evs[-1]["type"] == "done"
    assert ran == []
    assert [m["content"] for m in sent[-1]["messages"] if m.get("role") == "tool"] == [
        "Error: Unknown tool 'view_run'"]


def test_a_turn_without_tools_answered_with_tool_calls_ends(app_ctx, gate, no_result_check,
                                                            monkeypatch):
    ran = _recording(monkeypatch, ["remember"])
    plays(monkeypatch, ([], answer("", call("remember", kind="Notiz", content="x"))))
    evs = turn({"message": "Hallo", "context": {"persona_mode": True, "language": "de"}})
    assert [e["type"] for e in evs] == ["error"]
    assert "although none were offered" in evs[0]["details"]
    assert ran == []
