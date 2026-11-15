#!/usr/bin/env python3
"""What the text instruments of the Latent Lab check.

Every text a person sends passes the intake before anything reads it: the text
the tokenizer cuts, the text the encoder rows lay out, the contrast pairs and
the text Representation Engineering continues. What Representation Engineering
writes passes the result check before it is shown, and one refused text refuses
the answer. The level is resolved in the view, also where the work runs on a
thread of its own.

The gate, the tokenizer client and the probes are stubbed; nothing here asks a
model.
"""
import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.text_routes as routes
from my_app.services import text_client
from my_app.services import text_probes
from my_app.services.safety_gate import (CHECKPOINT_INTAKE, CHECKPOINT_RESULT, REASON_CONTENT,
                                         REASON_PERSONAL_DATA, Verdict)

AT_THE_INTAKE = "refuse-at-the-intake"
AT_THE_RESULT = "refuse-at-the-result"


@pytest.fixture
def gate(monkeypatch):
    """The checks, recorded where they are reached. A text with AT_THE_INTAKE
    in it is refused at the intake, one with AT_THE_RESULT at the result. The
    views resolve "youth"."""
    reached = []

    def intake(fields, *, level):
        reached.append(("intake", dict(fields), level))
        for name, text in fields.items():
            if AT_THE_INTAKE in str(text or ""):
                return Verdict(False, CHECKPOINT_INTAKE, level, name, REASON_PERSONAL_DATA,
                               "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def result(text, *, level, field="text"):
        reached.append(("result", text, level, field))
        if AT_THE_RESULT in str(text or ""):
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT, "a text")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(routes, "resolve_safety_level", lambda: "youth")
    monkeypatch.setattr(routes, "check_intake_texts", intake)
    monkeypatch.setattr(routes, "check_result_text", result)
    return reached


@pytest.fixture
def web():
    app = Flask(__name__)
    app.register_blueprint(routes.text_bp)
    return app.test_client()


class Client:
    """The tokenizer's side on ComfyUI, recording what it is asked to cut."""
    def __init__(self):
        self.cut = []

    async def tokenize(self, text, model_id):
        self.cut.append(text)
        return {"model_id": model_id, "tokens": [], "count": 0, "vocab": 1, "matrix": 1,
                "window": 1}

    async def encoder_rows(self, text, length):
        self.cut.append(text)
        return {"clip": {"rows": []}, "t5": {"rows": []}}


@pytest.fixture
def client(monkeypatch):
    fake = Client()
    monkeypatch.setattr(text_client, "get_text_client", lambda: fake)
    return fake


@pytest.mark.parametrize("path", ["/api/text/tokenize", "/api/text/encoder-rows"])
def test_a_text_refused_at_the_intake_is_not_cut(gate, web, client, path):
    model_id = routes._tokenizer_catalogue()[0]["id"]
    answer = web.post(path, json={"text": f"a {AT_THE_INTAKE}", "model_id": model_id})
    assert answer.status_code == 403
    assert answer.get_json()["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert client.cut == []
    assert gate == [("intake", {"text": f"a {AT_THE_INTAKE}"}, "youth")]


@pytest.mark.parametrize("path", ["/api/text/tokenize", "/api/text/encoder-rows"])
def test_a_text_that_passed_the_intake_is_cut(gate, web, client, path):
    model_id = routes._tokenizer_catalogue()[0]["id"]
    answer = web.post(path, json={"text": "ein Haus", "model_id": model_id})
    assert answer.status_code == 200
    assert client.cut == ["ein Haus"]


@pytest.fixture
def probe(monkeypatch):
    """Representation Engineering, answering with one generation per strength."""
    asked = []

    def rep_engineering(**kwargs):
        asked.append(kwargs)
        text = kwargs["test_text"] or ""
        return {"model_id": kwargs["model_id"], "target_layer": 3,
                "generations": [{"alpha": a, "text": f"{text} and so on"}
                                for a in (kwargs["alphas"] or [])]}

    monkeypatch.setattr(text_probes, "rep_engineering", rep_engineering)
    return asked


PAIRS = [{"positive": "warm", "negative": "cold"}, {"positive": "near", "negative": "far"}]


def test_the_pairs_and_the_text_pass_the_intake_before_the_model_reads_them(gate, probe):
    payload, status = routes._run_rep_engineering(
        {"contrast_pairs": PAIRS, "model_id": "m", "test_text": "Once", "alphas": [0.0, 2.0]},
        "kids")
    assert status == 200
    assert gate[0] == ("intake", {"contrast_pairs": "warm\ncold\nnear\nfar",
                                  "test_text": "Once"}, "kids")
    assert [g[1] for g in gate[1:]] == ["Once and so on", "Once and so on"]
    assert {g[2] for g in gate[1:]} == {"kids"}
    assert len(probe) == 1


def test_a_refused_pair_reaches_no_model(gate, probe):
    pairs = [{"positive": f"a {AT_THE_INTAKE}", "negative": "cold"}]
    payload, status = routes._run_rep_engineering(
        {"contrast_pairs": pairs, "model_id": "m", "test_text": "Once", "alphas": [1.0]},
        "youth")
    assert status == 403
    assert payload["safety_block"]["field"] == "contrast_pairs"
    assert probe == []


def test_one_refused_generation_refuses_the_answer(gate, probe):
    payload, status = routes._run_rep_engineering(
        {"contrast_pairs": PAIRS, "model_id": "m", "test_text": f"x {AT_THE_RESULT}",
         "alphas": [1.0]}, "youth")
    assert status == 403
    assert payload["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert "generations" not in payload


def test_the_view_resolves_the_level_and_hands_it_on(gate, web, monkeypatch):
    handed = []

    def run(data, level):
        handed.append(level)
        return {"ok": True}, 200

    monkeypatch.setattr(routes, "_run_rep_engineering", run)
    answer = web.post("/api/text/rep-engineering", json={"contrast_pairs": PAIRS, "model_id": "m"})
    assert answer.status_code == 200
    assert handed == ["youth"]


def test_the_bbq_views_resolve_the_level_themselves(gate, web, monkeypatch):
    seen = []
    monkeypatch.setattr(text_probes, "bbq_overview", lambda level: seen.append(level) or {})
    assert web.get("/api/text/bbq-overview").status_code == 200
    assert seen == ["youth"]
