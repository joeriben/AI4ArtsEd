"""/pipeline/translate runs over the intake and the check at the result.

What the caller sent passes the intake before any model is asked, and a refusal
there ends the request. Pieces this server handed out itself, from a corpus it
serves, are its own material and ask nothing there. What the model wrote is
checked at the result before the answer leaves; a piece that came back as it
went is not read again. A set of pieces is checked as one text and withheld as
a whole, a set out of the store is checked at the level of whoever asks, and
only a set that passed is kept.

The gate's own functions stand in here; what they decide is tested in
test_safety_gate.py. No model is called and nothing is written to the store.
"""
import threading
from types import SimpleNamespace

import pytest
from flask import Flask

from my_app.routes import schema_pipeline_routes as R
from my_app.services import translation_cache as TC
from my_app.services.safety_gate import (
    CHECKPOINT_INTAKE,
    CHECKPOINT_RESULT,
    REASON_CONTENT,
    REASON_PERSONAL_DATA,
    Verdict,
)

ROUTE = "/api/schema/pipeline/translate"
TEXT = "Ein Haus steht am See."
TRANSLATED = "A house stands by the lake."
PIECES = ["Zwei Leute warten.", "Wer wartet?", "Niemand", "Unbekannt"]
# The last piece comes back as it went.
TRANSLATED_PIECES = ["Two people are waiting.", "Who is waiting?", "Nobody", "Unbekannt"]
CHANGED = "\n".join(TRANSLATED_PIECES[:3])
CORPUS = {"texts": PIECES, "target_language": "de", "cache_scope": "bbq"}


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(R.schema_bp)
    return app.test_client()


class Checks:
    """The intake and the check at the result, standing in: they record what
    they were asked and refuse the field they are told to."""

    def __init__(self):
        self.intake = []
        self.result = []
        self.refuse_intake = None
        self.refuse_result = None

    def check_intake_texts(self, fields, *, level):
        self.intake.append((dict(fields), level))
        if self.refuse_intake in fields:
            return Verdict(False, CHECKPOINT_INTAKE, level, self.refuse_intake,
                           REASON_PERSONAL_DATA, "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def check_result_text(self, text, *, level, field="text"):
        self.result.append((field, text, level))
        if field == self.refuse_result:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT,
                           "not for this level")
        return Verdict(True, CHECKPOINT_RESULT, level, field)


@pytest.fixture
def checks(monkeypatch):
    stand_in = Checks()
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "youth")
    monkeypatch.setattr(R, "check_intake_texts", stand_in.check_intake_texts)
    monkeypatch.setattr(R, "check_result_text", stand_in.check_result_text)
    return stand_in


@pytest.fixture
def model(monkeypatch):
    """Both translations replaced: a single text comes back as `model.one`, a
    set as `model.pieces`. `model.asked` records what was sent."""
    stand_in = SimpleNamespace(one=TRANSLATED, pieces=list(TRANSLATED_PIECES), asked=[])

    def translate_one(text, target_language="en"):
        stand_in.asked.append(text)
        return stand_in.one

    def translate_list(texts, lang_name, style=None):
        stand_in.asked.append(list(texts))
        return list(stand_in.pieces)

    monkeypatch.setattr(R, "translate_one", translate_one)
    monkeypatch.setattr(R, "_translate_list", translate_list)
    return stand_in


@pytest.fixture
def store(monkeypatch):
    """The permanent store, standing in: a lookup finds `store.held`, and
    `store.kept` records what was written. What this server served is kept in
    memory, as in the store itself, and starts empty here."""
    stand_in = SimpleNamespace(held=None, kept=[])
    monkeypatch.setattr(TC, "lookup", lambda scope, lang, texts: stand_in.held)
    monkeypatch.setattr(TC, "store", lambda scope, lang, texts, translated:
                        stand_in.kept.append((scope, list(translated))))
    monkeypatch.setattr(TC, "_admitted", {})
    return stand_in


# ── one text ────────────────────────────────────────────────────────────────

def test_the_intake_takes_the_text(client, checks, model):
    response = client.post(ROUTE, json={"text": TEXT, "target_language": "en"})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["translated_text"] == TRANSLATED
    assert checks.intake == [({"text": TEXT}, "youth")]
    assert model.asked == [TEXT]


def test_a_refused_text_reaches_no_model(client, checks, model):
    checks.refuse_intake = "text"
    response = client.post(ROUTE, json={"text": TEXT})
    assert response.status_code == 403
    body = response.get_json()
    assert body["status"] == "blocked"
    assert body["safety_block"] == {"checkpoint": "intake", "field": "text",
                                    "reason_key": "personal_data", "reason": "a name"}
    assert model.asked == [] and checks.result == []


def test_what_the_model_wrote_is_checked_before_it_leaves(client, checks, model):
    response = client.post(ROUTE, json={"text": TEXT})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.result == [("translated_text", TRANSLATED, "youth")]


def test_a_refused_translation_is_withheld(client, checks, model):
    checks.refuse_result = "translated_text"
    response = client.post(ROUTE, json={"text": TEXT})
    assert response.status_code == 403
    body = response.get_json()
    assert body["safety_block"] == {"checkpoint": "result", "field": "translated_text",
                                    "reason_key": "content", "reason": "not for this level"}
    assert TRANSLATED not in response.get_data(as_text=True)


def test_a_text_that_comes_back_as_it_went_is_not_read_again(client, checks, model):
    model.one = " Ein Haus  steht am See. "
    response = client.post(ROUTE, json={"text": TEXT})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.result == []


# ── a set of pieces ─────────────────────────────────────────────────────────

def test_a_set_passes_the_intake_as_one_text(client, checks, model, store):
    response = client.post(ROUTE, json={"texts": PIECES, "target_language": "en"})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["translated_texts"] == TRANSLATED_PIECES
    assert checks.intake == [({"texts": "\n".join(PIECES)}, "youth")]


def test_a_refused_set_reaches_no_model(client, checks, model, store):
    checks.refuse_intake = "texts"
    response = client.post(ROUTE, json={"texts": PIECES})
    assert response.status_code == 403
    assert response.get_json()["safety_block"]["field"] == "texts"
    assert model.asked == [] and checks.result == []


def test_the_pieces_the_model_changed_are_checked_as_one_text(client, checks, model, store):
    response = client.post(ROUTE, json={"texts": PIECES})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.result == [("translated_texts", CHANGED, "youth")]


def test_a_set_whose_pieces_all_came_back_is_not_read_again(client, checks, model, store):
    model.pieces = list(PIECES)
    response = client.post(ROUTE, json={"texts": PIECES})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.result == []


def test_a_refused_set_is_withheld_whole_and_not_kept(client, checks, model, store):
    checks.refuse_result = "translated_texts"
    response = client.post(ROUTE, json=CORPUS)
    assert response.status_code == 403
    body = response.get_json()
    assert body["safety_block"]["field"] == "translated_texts"
    assert "translated_texts" not in body
    assert store.kept == []


def test_only_a_set_that_passed_is_kept(client, checks, model, store):
    response = client.post(ROUTE, json=CORPUS)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert store.kept == [("bbq", TRANSLATED_PIECES)]


def test_a_set_out_of_the_store_is_checked_at_the_level_of_whoever_asks(
        client, checks, model, store, monkeypatch):
    store.held = list(TRANSLATED_PIECES)
    monkeypatch.setattr(R, "resolve_safety_level", lambda: "kids")
    checks.refuse_result = "translated_texts"
    response = client.post(ROUTE, json=CORPUS)
    assert response.status_code == 403
    assert model.asked == []
    assert checks.result == [("translated_texts", CHANGED, "kids")]


def test_pieces_this_server_served_ask_nothing_at_the_intake(client, checks, model, store):
    TC.admit("bbq", PIECES)
    response = client.post(ROUTE, json=CORPUS)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == []
    # What the model wrote from them is checked all the same.
    assert checks.result == [("translated_texts", CHANGED, "youth")]


@pytest.mark.parametrize("served,body", [
    (PIECES[:3], CORPUS),
    (PIECES, {**CORPUS, "cache_scope": "winobias"}),
    (PIECES, {"texts": PIECES, "target_language": "de"}),
], ids=["one piece nobody served", "another scope", "no scope"])
def test_a_set_this_server_did_not_serve_so_goes_through_the_intake(
        client, checks, model, store, served, body):
    TC.admit("bbq", served)
    response = client.post(ROUTE, json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert checks.intake == [({"texts": "\n".join(PIECES)}, "youth")]


# ── the level ───────────────────────────────────────────────────────────────

def test_the_streamed_answer_is_checked_at_the_level_of_the_session(client, checks, model,
                                                                     monkeypatch):
    """The run goes on on a worker of the stream transport, where the resolver
    answers the strictest level: the level is read on the request thread."""
    request_thread = threading.current_thread()
    monkeypatch.setattr(R, "resolve_safety_level",
                        lambda: "youth" if threading.current_thread() is request_thread
                        else "kids")
    response = client.post(ROUTE, json={"text": TEXT, "enable_streaming": True})
    assert "event: complete" in response.get_data(as_text=True)
    assert checks.intake == [({"text": TEXT}, "youth")]
    assert checks.result == [("translated_text", TRANSLATED, "youth")]


def test_a_level_that_cannot_be_resolved_runs_nothing(client, checks, model, monkeypatch):
    def boom():
        raise RuntimeError("the course lookup is down")

    monkeypatch.setattr(R, "resolve_safety_level", boom)
    response = client.post(ROUTE, json={"text": TEXT})
    assert response.status_code == 500
    assert response.mimetype == "application/json"
    assert "the course lookup is down" in response.get_json()["error"]
    assert checks.intake == [] and model.asked == []
