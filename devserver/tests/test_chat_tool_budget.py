#!/usr/bin/env python3
"""A chat turn whose tool budget runs out still answers (2026-11-08).

Measured on lab6000 on 2026-11-08 in the backend journal: a question about a
measure of the AI-literacy framework to which no teaching scenario is mapped
drew tool calls in five consecutive rounds and no text. The budget tripped, the
turn shipped the empty text of the exhausted round, and on a later turn the
model's reasoning went out as the reply, because the chat surface showed
reasoning for any result without content, including one that ended in tool
calls.

What this file holds:
  * reasoning stands in for an answer only when the round ended without tool
    calls, in the streaming dispatcher and in the blocking caller;
  * a spent budget is followed by one last call that keeps the tools and sends
    tool_choice "none", with the round's tool calls answered by a note instead
    of being run, and the text of that call is the reply;
  * tool calls in that last call end the turn in an error and are not run;
  * a turn that ends without any text is an error event that names the cause;
  * both dialects put tool_choice into the request only together with tools;
  * lookup_scenarios says that a competence without a mapped scenario is the
    answer, and a free-text miss points at the list;
  * the complete null answer of a competence filter stands in the evidence
    ledger as a search that ran and came back empty, so the terms of the
    reason it carries pass the evidence duty without a correction round.

Nothing here reaches a provider or a GPU: the chat helper and the provider
reader are stand-ins, and the tool registry's execute is counted, not run.

Run:  python3 -m pytest devserver/tests/test_chat_tool_budget.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from my_app.routes import chat_routes
from my_app.services import openai_style_stream as oss
from my_app.services.tool_registry import get_tool_registry

# The number of tool rounds _chat_events grants a turn without evidence
# corrections. It is a local of that function, so it is stated here.
MAX_TOOL_ITERATIONS = 5

ANSWER = "Kein Lehrszenario der Nutzungsberichte ist dieser Maßnahme zugeordnet."

LOOKUP_CALL = [{
    "id": "call_1",
    "type": "function",
    "function": {"name": "lookup_scenarios",
                 "arguments": json.dumps({"competence": "Engage 4 Advanced"})},
}]

TOOL_ROUND = {"content": "", "thinking": "I will look further.", "tool_calls": LOOKUP_CALL}

RESONA_DATA = {
    "message": "Welche Instrumente sind für AI-Lit Engage 4 advanced geeignet?",
    "context": {"resona_mode": True, "language": "de", "device_id": "test-device"},
}


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    with app.test_request_context("/api/chat", json={}):
        yield


# ---------------------------------------------------------------------------
# 1. Reasoning is shown only for a result that ended without tool calls
# ---------------------------------------------------------------------------

def _dispatched_result(monkeypatch, result):
    def fake_stream_chat(provider, messages, model, temperature, max_tokens, **kwargs):
        yield ("result", result)

    monkeypatch.setattr(chat_routes, "stream_chat", fake_stream_chat)
    out = list(chat_routes._dispatch_single_model_stream(
        "mistral/stand-in-one", [{"role": "user", "content": "x"}], 0.7,
        None, True, None, None))
    return [p for k, p in out if k == "result"][-1]


def test_reasoning_of_a_tool_round_is_not_the_reply(monkeypatch):
    payload = _dispatched_result(monkeypatch, {
        "content": "", "thinking": "plan",
        "tool_calls": [{"id": "1", "function": {"name": "x", "arguments": "{}"}}]})
    assert payload["content"] == ""


def test_reasoning_still_stands_in_for_an_answer_without_tool_calls(monkeypatch):
    payload = _dispatched_result(monkeypatch, {
        "content": "", "thinking": "plan", "tool_calls": None})
    assert payload["content"] == "plan"


def _blocking_result(monkeypatch, result):
    monkeypatch.setattr(chat_routes, "call_chat", lambda *a, **k: result)
    return chat_routes._call_cloud_chat(
        "mistral", "Stand-in", [{"role": "user", "content": "x"}],
        "stand-in-one", 0.7, None)


def test_the_blocking_caller_keeps_a_tool_rounds_reasoning_out(monkeypatch):
    out = _blocking_result(monkeypatch, {
        "content": "", "thinking": "plan",
        "tool_calls": [{"id": "1", "function": {"name": "x", "arguments": "{}"}}]})
    assert out["content"] == ""


def test_the_blocking_caller_still_shows_reasoning_without_tool_calls(monkeypatch):
    out = _blocking_result(monkeypatch, {"content": "", "thinking": "plan", "tool_calls": None})
    assert out["content"] == "plan"


# ---------------------------------------------------------------------------
# 2. A spent budget is followed by one last call in which no tool can be used
# ---------------------------------------------------------------------------

def budget_helper(calls, last_result):
    """A stand-in chat helper: tool calls while tool_choice is not "none", then
    `last_result`. Each call's tools, tool_choice and messages are recorded."""
    def helper(**kwargs):
        calls.append({"tools": kwargs.get("tools"),
                      "tool_choice": kwargs.get("tool_choice"),
                      "messages": [dict(m) for m in kwargs.get("messages") or []]})
        yield ("result", last_result if kwargs.get("tool_choice") == "none" else TOOL_ROUND)
    return helper


def run_turn(monkeypatch, last_result):
    calls, executed = [], []

    def fake_execute(name, arguments, context=None, *, level=None, language=None):
        executed.append(name)
        return ("No teaching scenario of the use reports matches "
                "competence='Engage 4 Advanced'.")

    monkeypatch.setattr(get_tool_registry(), "execute", fake_execute)
    monkeypatch.setattr(chat_routes, "call_chat_helper_stream",
                        budget_helper(calls, last_result))
    evs = list(chat_routes._chat_events(dict(RESONA_DATA)))
    return evs, calls, executed


@pytest.mark.usefixtures("chat_checks_pass")
def test_a_spent_budget_ends_in_one_last_call_without_tool_use(app_ctx, monkeypatch):
    evs, calls, executed = run_turn(
        monkeypatch, {"content": ANSWER, "thinking": None, "tool_calls": None})

    # The tools stay in every request; only the last one withholds their use.
    assert all(c["tools"] for c in calls), "tools were offered to the turn"
    assert [c["tool_choice"] for c in calls].count("none") == 1
    assert calls[-1]["tool_choice"] == "none"
    # One tool call per round, executed for every round within the budget and
    # never for the round that spent it.
    assert len(executed) == MAX_TOOL_ITERATIONS * len(LOOKUP_CALL)
    assert len(calls) == MAX_TOOL_ITERATIONS + 2

    # The round that spent the budget stands in the history with its calls,
    # each answered by the note, and no user turn is added after it.
    last = calls[-1]["messages"]
    n = len(LOOKUP_CALL)
    assert last[-(n + 1)]["role"] == "assistant"
    assert last[-(n + 1)]["tool_calls"] == LOOKUP_CALL
    for m, tc in zip(last[-n:], LOOKUP_CALL):
        assert m["role"] == "tool"
        assert m["tool_call_id"] == tc["id"]
        assert "spent" in m["content"] and "not executed" in m["content"]
    assert not any(m["role"] == "user" and "tool budget" in str(m.get("content"))
                   for m in last)

    done = evs[-1]
    assert done["type"] == "done", evs[-1]
    assert done["reply"] == ANSWER


@pytest.mark.usefixtures("chat_checks_pass")
def test_tool_calls_in_the_last_call_are_not_run(app_ctx, monkeypatch):
    evs, calls, executed = run_turn(monkeypatch, TOOL_ROUND)

    assert calls[-1]["tool_choice"] == "none"
    assert len(executed) == MAX_TOOL_ITERATIONS * len(LOOKUP_CALL)
    last = evs[-1]
    assert last["type"] == "error", last
    assert "although none were offered" in last["details"]


@pytest.mark.usefixtures("chat_checks_pass")
def test_a_turn_without_any_text_is_an_error(app_ctx, monkeypatch):
    evs, calls, _ = run_turn(
        monkeypatch, {"content": "", "thinking": None, "tool_calls": None})

    assert calls[-1]["tool_choice"] == "none"
    last = evs[-1]
    assert last["type"] == "error", last
    assert "wrote no answer" in last["details"]


# ---------------------------------------------------------------------------
# 3. Both dialects carry tool_choice, and only together with tools
# ---------------------------------------------------------------------------

TOOLS = [{"type": "function", "function": {"name": "x", "description": "d",
                                            "parameters": {"type": "object", "properties": {}}}}]


@pytest.fixture
def sent(monkeypatch):
    payloads = []

    def fake_sse(provider, api_url, headers, payload, grammar, model, stage):
        payloads.append(payload)
        yield ("result", {"content": "ok", "thinking": None, "tool_calls": None})

    monkeypatch.setattr(oss, "_stream_sse", fake_sse)
    monkeypatch.setitem(oss._OPENAI_STYLE_PROVIDERS, "stand-in-cc",
                        lambda: ("http://127.0.0.1:1/v1/chat/completions", "key"))
    monkeypatch.setitem(oss._ANTHROPIC_STYLE_PROVIDERS, "stand-in-msg",
                        lambda: ("http://127.0.0.1:1/v1/messages", "key"))
    return payloads


def test_chat_completions_sends_tool_choice_with_tools(sent):
    list(oss._stream_openai_style("stand-in-cc", [{"role": "user", "content": "x"}],
                                  "m", 0.7, None, tools=TOOLS, tool_choice="none"))
    list(oss._stream_openai_style("stand-in-cc", [{"role": "user", "content": "x"}],
                                  "m", 0.7, None, tools=None, tool_choice="none"))
    assert sent[0]["tool_choice"] == "none"
    assert "tool_choice" not in sent[1]


def test_the_messages_dialect_sends_tool_choice_as_an_object(sent):
    list(oss._stream_anthropic_style("stand-in-msg", [{"role": "user", "content": "x"}],
                                     "m", tools=TOOLS, tool_choice="none"))
    list(oss._stream_anthropic_style("stand-in-msg", [{"role": "user", "content": "x"}],
                                     "m", tools=None, tool_choice="none"))
    assert sent[0]["tool_choice"] == {"type": "none"}
    assert "tool_choice" not in sent[1]


# ---------------------------------------------------------------------------
# 4. A lookup without a match says so; a competence without a scenario is the answer
# ---------------------------------------------------------------------------

def _use_reports_or_skip():
    from my_app.services import platform_items as _pi
    if not (_pi.USE_REPORTS.get("by_route") or {}):
        pytest.skip("no use reports are loaded in this environment")


def test_a_competence_without_a_scenario_is_the_answer():
    _use_reports_or_skip()
    text = get_tool_registry().execute("lookup_scenarios", {"competence": "Engage 4"})
    assert ("This is the answer to give: no teaching scenario of the use reports "
            "is mapped to Engage 4.") in text, text
    assert "without a filter" not in text


def test_a_query_without_a_match_says_so_and_points_at_the_list():
    # A free-text miss claims no finality: the scenarios are English, so a
    # German word misses where its translation hits, and the list of
    # instruments is one call away (2026-11-08).
    _use_reports_or_skip()
    text = get_tool_registry().execute(
        "lookup_scenarios", {"query": "zzz-no-scenario-says-this-zzz"})
    assert text.startswith("No teaching scenario of the use reports matches"), text
    assert "nothing matches this filter" in text
    assert "This is the answer to give" not in text


# ---------------------------------------------------------------------------
# 5. The complete null answer is a search that ran and came back empty
# ---------------------------------------------------------------------------

# The record's reason for Engage 4 Advanced, given in the conversation's
# language, names a thing the glossary knows.
REASON_REPLY = ("Kein Lehrszenario der Nutzungsberichte ist Engage 4 Advanced zugeordnet: die "
                "Maßnahme liest Fallstudien über recommender systems sozialer Netzwerke, und die "
                "Plattform hält kein Empfehlungssystem, keine Vorhersage aus Nutzerdaten und "
                "keinen Feed. [own]")
REASON_REPLY_RESULT = {"content": REASON_REPLY, "thinking": None, "tool_calls": None}


def _two_rounds(calls, second):
    """A stand-in chat helper: the lookup round, then `second`."""
    def helper(**kwargs):
        calls.append({"tool_choice": kwargs.get("tool_choice"),
                      "messages": [dict(m) for m in kwargs.get("messages") or []]})
        yield ("result", TOOL_ROUND if len(calls) == 1 else second)
    return helper


@pytest.mark.usefixtures("chat_checks_pass")
def test_the_complete_null_answer_grounds_the_terms_of_its_reason(app_ctx, monkeypatch):
    from my_app.services import evidence_duty as ED
    _use_reports_or_skip()
    lex = ED.build_lexicon([("doc-recsys", "Recommender systems", "Somebody Else")],
                           [("recommender systems", "doc-recsys")])
    monkeypatch.setattr(ED, "load_lexicon", lambda: lex)
    # The duty, on its own: the reply trips without the entry and passes with it.
    assert ED.validate(REASON_REPLY, ledger=[], lexicon=lex, user_text=RESONA_DATA["message"])
    assert ED.validate(REASON_REPLY, ledger=[("miss", "Engage 4 Advanced")], lexicon=lex,
                       user_text=RESONA_DATA["message"]) == []
    # The turn: the real lookup_scenarios runs, the reply follows, no correction round.
    calls = []
    monkeypatch.setattr(chat_routes, "call_chat_helper_stream",
                        _two_rounds(calls, REASON_REPLY_RESULT))
    evs = list(chat_routes._chat_events(dict(RESONA_DATA)))
    assert evs[-1]["type"] == "done", evs[-1]
    assert len(calls) == 2, [c["tool_choice"] for c in calls]
    assert not any("without having looked" in str(m.get("content"))
                   for c in calls for m in c["messages"])
    tool_msgs = [m for m in calls[1]["messages"] if m.get("role") == "tool"]
    assert tool_msgs and tool_msgs[-1]["content"].startswith(
        "No teaching scenario of the use reports matches")
    assert "This is the answer to give:" in tool_msgs[-1]["content"]
