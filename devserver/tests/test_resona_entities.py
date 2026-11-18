#!/usr/bin/env python3
"""What a room worked out gets a card, and the card says where it came from.

The entities a room works out are represented on the canvas (not only the
produced media), if need be only as memory anchors.

Five kinds. The library passage may lie on the surface because the library holds
knowledge it has PROCESSED and never the original text; an
external page carries its link and none of its body, which is the same reason
read the other way round. A teaching scenario of the use reports comes whole,
because no page of the platform shows the scenarios (2026-11-15).

Run:  python3 -m pytest devserver/tests/test_resona_entities.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import chat_routes
from my_app.services import resona_entities as re_
from my_app.services.canvas_graph_authoring import RESONA_CANVAS_CONFIGS
from my_app.services.tool_registry import get_tool_registry


# The turn is under test here, not what it checks.
pytestmark = pytest.mark.usefixtures("chat_checks_pass")

CFG = sorted(RESONA_CANVAS_CONFIGS)[0]

GRAPH = {
    "nodes": [
        {"id": "i", "type": "input", "promptText": "ein Haus"},
        {"id": "g", "type": "generation", "configId": CFG},
    ],
    "connections": [{"sourceId": "i", "targetId": "g"}],
}


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    with app.test_request_context("/api/chat", json={}):
        yield


# --- The kept strategy -------------------------------------------------------

def test_a_kept_strategy_becomes_a_card():
    """The strongest case: a strategy the group keeps is meant to outlive the
    conversation, and the board showed nothing for it at all."""
    result = get_tool_registry().execute("canvas_graph_library", {
        "action": "save",
        "title": "Verniedlichung: Zufallsmotiv durch Harmonisierungs-Linse",
        "description": "für den Einstieg",
        "application_type": "verwandlung",
        "memo": "die Linse macht aus jedem Motiv etwas Freundliches",
        "graph": GRAPH,
    })
    assert result.startswith("Kept strategy"), result
    card = re_.from_tool_call("canvas_graph_library", {}, result)
    assert card is not None
    assert card["kind"] == "apparatus"
    assert card["name"] == "Verniedlichung: Zufallsmotiv durch Harmonisierungs-Linse"
    assert card["detail"] == "die Linse macht aus jedem Motiv etwas Freundliches"
    assert any(f.startswith("cw_") and "v1" in f for f in card["facts"]), card["facts"]
    assert "verwandlung" in card["facts"]
    assert any("input" in f and "generation" in f for f in card["facts"]), card["facts"]


def test_the_strategy_is_handed_over_once():
    get_tool_registry().execute("canvas_graph_library", {
        "action": "save", "title": "Einmal", "graph": GRAPH})
    assert re_.from_tool_call("canvas_graph_library", {}, "ok") is not None
    assert re_.from_tool_call("canvas_graph_library", {}, "ok") is None


def test_listing_the_repertoire_lays_nothing_down():
    """Reading the shelf is not working something out."""
    get_tool_registry().execute("canvas_graph_library", {"action": "list"})
    assert re_.from_tool_call("canvas_graph_library", {}, "Strategies (0)") is None


# --- The note ----------------------------------------------------------------

def test_a_note_becomes_a_card():
    card = re_.from_tool_call("remember", {
        "kind": "Beobachtung",
        "content": "Die Gruppe arbeitet lieber mit Klang als mit Bild.",
    }, "noted")
    assert card["kind"] == "note"
    assert card["name"] == "Beobachtung"
    assert card["detail"] == "Die Gruppe arbeitet lieber mit Klang als mit Bild."


def test_a_note_without_words_is_no_card():
    assert re_.from_tool_call("remember", {"kind": "Beobachtung", "content": "  "}, "x") is None


# --- The library passage -----------------------------------------------------

@pytest.fixture
def a_document(monkeypatch):
    monkeypatch.setattr(re_, "_build", re_._build)  # keep the name bound for clarity
    from my_app.services import knowledge_library as kl
    monkeypatch.setattr(kl, "doc_card", lambda doc_id: {
        "doc_id": doc_id,
        "title": "AI competency framework for students",
        "authors": "UNESCO",
        "year": 2024,
        "lizenz": "CC BY-SA 3.0 IGO",
        "url": "https://unesdoc.unesco.org/ark:/48223/pf0000391105",
    } if doc_id == "unesco_ai_students" else None)


def test_a_library_passage_becomes_a_card(a_document):
    passage = "TITLE: AI competency framework\n\nDie Rahmung unterscheidet vier Stufen. " * 40
    card = re_.from_tool_call("read_knowledge",
                              {"doc_id": "unesco_ai_students"}, passage)
    assert card["kind"] == "document"
    assert card["name"] == "AI competency framework for students"
    assert card["key"] == "doc:unesco_ai_students"
    assert card["detail"], "the passage that was read stands on the back"
    assert len(card["detail"]) <= re_.EXCERPT_CHARS
    assert "UNESCO · 2024" in card["facts"]
    assert "CC BY-SA 3.0 IGO" in card["facts"]
    assert any(f.startswith("https://unesdoc") for f in card["facts"])


def test_a_document_the_library_does_not_know_still_gets_its_name(a_document):
    card = re_.from_tool_call("read_knowledge", {"doc_id": "kein_dokument"}, "…")
    assert card["name"] == "kein_dokument"
    assert card["facts"] == []


def test_two_sections_of_one_document_are_two_cards(a_document):
    a = re_.from_tool_call("read_knowledge",
                           {"doc_id": "unesco_ai_students", "section": "Ethik"}, "…")
    b = re_.from_tool_call("read_knowledge",
                           {"doc_id": "unesco_ai_students", "section": "Didaktik"}, "…")
    assert a["key"] != b["key"]


# --- The page ----------------------------------------------------------------

PAGE = (
    "PAGE: Kunst und Künstliche Intelligenz — Tagung\n"
    "URL: https://example.org/tagung\n"
    "LICENCE: all rights reserved\n\n"
    "Der ganze Text der Seite, den niemand hierher kopiert."
)


def test_a_page_becomes_a_card_of_its_link():
    card = re_.from_tool_call("read_webpage", {"url": "https://example.org/tagung"}, PAGE)
    assert card["kind"] == "page"
    assert card["name"] == "Kunst und Künstliche Intelligenz — Tagung"
    assert card["facts"] == ["https://example.org/tagung"]


def test_the_page_text_stays_on_the_page():
    """Someone else wrote it. The card is a way back to it, not a copy of it."""
    card = re_.from_tool_call("read_webpage", {"url": "https://example.org/tagung"}, PAGE)
    assert card["detail"] == ""
    assert "niemand hierher kopiert" not in str(card)


def test_a_page_read_that_says_nothing_useful_falls_back_to_the_url():
    card = re_.from_tool_call("read_webpage", {"url": "https://example.org/x"}, "")
    assert card["name"] == "https://example.org/x"


# --- Everything else ---------------------------------------------------------

# --- The teaching scenario ---------------------------------------------------

def test_an_opened_scenario_becomes_a_card_with_its_whole_wording():
    """No page of the platform shows the teaching scenarios: the card is the
    one place the educator can read the scenario a proposal rests on, so its
    back carries all of it, unclipped, one part per paragraph. The report's
    uncertainty stays off the card: it speaks in the first person of the
    report's author, whom nobody at the board can name. The instrument is
    named in the conversation's language; the source travels as data."""
    from my_app.services import platform_items as pi
    rec, scen = pi.scenario_by_id("07/S1")
    card = re_.from_tool_call("read_scenario", {"id": "07/S1"}, "what the tool said")
    assert card["kind"] == "scenario"
    assert card["key"] == "scenario:07/S1"
    assert card["name"] == scen["title"]
    parts = ("setting", "text", "sequence", "subject_link")
    for key in parts:
        assert " ".join(scen[key].split()) in card["detail"], key
    assert len(card["detail"].split("\n\n")) == sum(1 for k in parts if scen.get(k))
    assert "Sequence: " in card["detail"] and "Subject link: " in card["detail"]
    assert scen.get("uncertainty")
    assert " ".join(scen["uncertainty"].split()) not in card["detail"]
    assert "Uncertainty" not in card["detail"]
    assert len(card["detail"]) > re_.EXCERPT_CHARS
    names = (pi.item_for_route(rec["route"]) or {}).get("names") or {}
    en = names.get("en") or rec["name"]
    assert card["facts"] == [f"{en} ({rec['route']})"]
    assert card["source"] == {"version": str(pi.USE_REPORTS.get("version")),
                              "scenario": "07/S1"}
    de = re_.from_tool_call("read_scenario", {"id": "07/S1"}, "", language="de")
    assert de["facts"] == [f"{names.get('de') or en} ({rec['route']})"]


def test_every_spelling_of_one_scenario_is_one_card():
    keys = {re_.from_tool_call("read_scenario", {"id": raw}, "")["key"]
            for raw in ("07/S1", "7 S1", "07-s1", " 7/1 ")}
    assert keys == {"scenario:07/S1"}


def test_a_scenario_that_is_not_there_is_no_card():
    for raw in ("07/S99", "99/S1", "nope", "", None, 7):
        assert re_.from_tool_call("read_scenario", {"id": raw}, "x") is None, raw


def test_a_tool_that_worked_nothing_out_lays_nothing_down():
    for name in ("lookup_knowledge", "search_websites", "generate_media",
                 "run_canvas_graph", "view_run", "recall"):
        assert re_.from_tool_call(name, {"query": "x"}, "some result") is None, name


def test_a_card_that_cannot_be_written_never_breaks_the_turn(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no")
    monkeypatch.setattr(re_, "_build", boom)
    assert re_.from_tool_call("remember", {"content": "x"}, "ok") is None


# --- The way to the board ----------------------------------------------------

def _rounds(*plans):
    state = {"i": 0}

    def helper(**kwargs):
        plan = plans[min(state["i"], len(plans) - 1)]
        state["i"] += 1
        toks, end = plan
        for t in toks:
            yield ("token", t)
        yield ("result", end)

    return helper


def _answer(content, tool_calls=None):
    return {"content": content, "thinking": None, "tool_calls": tool_calls,
            "model_used": "stand-in/one"}


import json

KEEP_CALL = [{
    "id": "call_1", "type": "function",
    "function": {"name": "canvas_graph_library",
                 "arguments": json.dumps({"action": "save", "title": "Zwei Wege",
                                          "memo": "hat im Kurs getragen",
                                          "graph": GRAPH})},
}]


def test_the_card_goes_out_before_the_closing_sentence(app_ctx, monkeypatch):
    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", _rounds(
        ([], _answer("", KEEP_CALL)),
        (["Aufbewahrt."], _answer("Aufbewahrt.")),
    ))
    evs = list(chat_routes._chat_events({
        "message": "heb das auf",
        "context": {"resona_mode": True, "language": "de", "device_id": "test-device"},
    }))
    kinds = [e["type"] for e in evs]
    assert "entity" in kinds, kinds
    assert kinds.index("entity") < kinds.index("done"), kinds
    card = [e["entity"] for e in evs if e["type"] == "entity"][0]
    assert card["name"] == "Zwei Wege"
    assert card["detail"] == "hat im Kurs getragen"
    # And again in the closing payload: the blocking mouth reads nothing else.
    assert evs[-1]["worked_entities"] == [card]


SCENARIO_CALL = [{
    "id": "call_s", "type": "function",
    "function": {"name": "read_scenario", "arguments": json.dumps({"id": "07/S1"})},
}]


def test_a_scenario_read_on_together_lays_its_card(app_ctx, monkeypatch):
    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", _rounds(
        ([], _answer("", SCENARIO_CALL)),
        (["Gelesen."], _answer("Gelesen.")),
    ))
    evs = list(chat_routes._chat_events({
        "message": "welches Szenario passt?",
        "context": {"resona_mode": True, "language": "de", "device_id": "test-device"},
    }))
    cards = [e["entity"] for e in evs if e["type"] == "entity"]
    assert [c["key"] for c in cards] == ["scenario:07/S1"], cards
    assert evs[-1]["worked_entities"] == cards


def test_help_reads_the_same_scenario_and_lays_nothing_down(app_ctx, monkeypatch):
    """Help reads the scenarios too, and has no board: no card, and no
    sentence telling the model there is one."""
    seen = {}

    def execute_spy(name, args, **kw):
        out = real_execute(name, args, **kw)
        seen[name] = out
        return out

    registry = get_tool_registry()
    real_execute = registry.execute
    monkeypatch.setattr(registry, "execute", execute_spy)
    monkeypatch.setattr(chat_routes, "call_chat_helper_stream", _rounds(
        ([], _answer("", SCENARIO_CALL)),
        (["Gelesen."], _answer("Gelesen.")),
    ))
    evs = list(chat_routes._chat_events({
        "message": "welches Szenario passt?",
        "context": {"language": "de"},
    }))
    assert "read_scenario" in seen, list(seen)
    assert "on the board" not in seen["read_scenario"]
    assert not [e for e in evs if e["type"] == "entity"]
    assert not evs[-1].get("worked_entities")
