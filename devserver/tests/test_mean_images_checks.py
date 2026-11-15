#!/usr/bin/env python3
"""What Mean Images checks on the way to its set.

The variants route takes the prompt the user wrote and, where the surface hands
it back, the English sentence this route wrote earlier; both pass the intake
before anything is translated or varied. What the language model writes, the
English sentence and every variant, passes the check of the result before it
is varied or shown, at the level the view resolved. A refusal answers 403 with
the block message and stops the run; a refused variant refuses the set.

The gate functions, the translation and the chat call are stubbed; nothing here
asks a model. The check of the decoded mean is in test_mean_images.py.
"""
import json
import sys
import threading
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.chat_routes as chat_routes
import my_app.routes.mean_images_routes as routes
import my_app.routes.schema_pipeline_routes as schema_routes
import my_app.services.safety_level_resolver as resolver
from my_app.services.safety_gate import (CHECKPOINT_INTAKE, CHECKPOINT_RESULT, REASON_CONTENT,
                                         REASON_PERSONAL_DATA, Verdict)

VARIANTS = '/api/latent-lab/mean-images/variants'

AT_THE_INTAKE = "refuse-at-the-intake"
AT_THE_RESULT = "refuse-at-the-result"


class Reached(list):
    """What was reached, in order. `variants` is what the chat call answers,
    `translated` what the translation makes of a text."""
    variants = '["a second line", "a third line"]'

    @staticmethod
    def translated(text):
        return f"EN: {text}"


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(routes.mean_images_bp)
    return app.test_client()


@pytest.fixture
def ran(monkeypatch):
    """The checks, the translation and the chat call recorded where they are
    reached, in that order. A text with AT_THE_INTAKE in it is refused at the
    intake, one with AT_THE_RESULT at the result. The view resolves "youth"."""
    reached = Reached()
    monkeypatch.setattr(resolver, "resolve_safety_level", lambda: "youth")

    def translate(text, lang="en"):
        reached.append(("translate", text))
        return reached.translated(text)

    def chat(*args, **kwargs):
        reached.append(("chat",))
        return {"content": reached.variants}

    def intake(fields, *, level):
        reached.append(("intake", dict(fields), level))
        for name, text in fields.items():
            if AT_THE_INTAKE in str(text or ""):
                return Verdict(False, CHECKPOINT_INTAKE, level, name, REASON_PERSONAL_DATA,
                               "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def result(text, *, level, field="text"):
        reached.append(("result", text, level, field))
        if AT_THE_RESULT in text:
            return Verdict(False, CHECKPOINT_RESULT, level, field, REASON_CONTENT, "a text")
        return Verdict(True, CHECKPOINT_RESULT, level, field)

    monkeypatch.setattr(schema_routes, "translate_one", translate)
    monkeypatch.setattr(chat_routes, "call_chat_helper", chat)
    monkeypatch.setattr(routes, "check_intake_texts", intake)
    monkeypatch.setattr(routes, "check_result_text", result)
    return reached


def terminal_frame(wire: str) -> dict:
    """The streamed answer's terminal frame: the plain answer and its status."""
    for raw in wire.split("\n\n"):
        if raw.startswith("event: complete"):
            return json.loads(raw.split("data: ", 1)[1])
    raise AssertionError(f"no terminal frame on this wire: {wire[:300]!r}")


def test_the_prompt_passes_the_intake_and_what_was_written_the_result(client, ran):
    res = client.post(VARIANTS, json={"prompt": "eine Strasse", "n": 3})
    assert res.status_code == 200
    assert res.get_json()["variants"] == ["EN: eine Strasse", "a second line", "a third line"]
    assert ran == [
        ("intake", {"prompt": "eine Strasse", "translation_en": None}, "youth"),
        ("translate", "eine Strasse"),
        ("result", "EN: eine Strasse", "youth", "translation_en"),
        ("chat",),
        ("result", "a second line", "youth", "variants"),
        ("result", "a third line", "youth", "variants"),
    ]


def test_a_translation_handed_back_passes_the_intake_and_is_not_judged_again(client, ran):
    """The surface hands back the sentence this route wrote. It passes the
    intake with the prompt, and the check of the result is not asked about it
    a second time."""
    res = client.post(VARIANTS, json={"prompt": "eine Strasse", "translation_en": "a street",
                                      "n": 3})
    assert res.status_code == 200
    assert ran[0] == ("intake", {"prompt": "eine Strasse", "translation_en": "a street"},
                      "youth")
    assert [r for r in ran if r[0] == "result" and r[3] == "translation_en"] == []


def test_a_prompt_refused_at_the_intake_is_neither_translated_nor_varied(client, ran):
    res = client.post(VARIANTS, json={"prompt": f"a {AT_THE_INTAKE}", "n": 3})
    assert res.status_code == 403
    body = res.get_json()
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert body["safety_block"]["field"] == "prompt"
    assert [r[0] for r in ran] == ["intake"]


def test_a_refused_translation_is_neither_shown_nor_varied(client, ran):
    ran.translated = lambda text: f"EN {AT_THE_RESULT}"
    res = client.post(VARIANTS, json={"prompt": "eine Strasse", "n": 3})
    assert res.status_code == 403
    body = res.get_json()
    assert "translation_en" not in body and "variants" not in body
    assert body["safety_block"]["field"] == "translation_en"
    assert [r[0] for r in ran] == ["intake", "translate", "result"]


def test_a_refused_variant_refuses_the_set(client, ran):
    ran.variants = f'["a second line", "a {AT_THE_RESULT} line"]'
    res = client.post(VARIANTS, json={"prompt": "eine Strasse", "n": 3})
    assert res.status_code == 403
    body = res.get_json()
    assert "variants" not in body
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_RESULT
    assert body["safety_block"]["field"] == "variants"
    assert [r[0] for r in ran].count("chat") == 1


def test_a_refusal_is_the_same_either_way(client, ran):
    """A streamed answer carries the plain one in its terminal frame; a refusal
    is no exception."""
    body = {"prompt": "eine Strasse", "n": 3}
    ran.variants = f'["a second line", "a {AT_THE_RESULT} line"]'
    plain = client.post(VARIANTS, json=body)
    streamed = client.post(VARIANTS, json={**body, "enable_streaming": True})
    frame = terminal_frame(streamed.get_data(as_text=True))
    assert (frame["body"], frame["http_status"]) == (plain.get_json(), 403)


def test_the_level_is_resolved_in_the_view_and_travels_with_the_run(client, ran, monkeypatch):
    """A streamed answer runs the variants on a thread of their own, where the
    resolver answers the strictest level whatever the course is. The view
    resolves it on the request thread and hands it on."""
    resolved_on = []

    def level():
        resolved_on.append(threading.get_ident())
        return "adult"

    monkeypatch.setattr(resolver, "resolve_safety_level", level)
    res = client.post(VARIANTS, json={"prompt": "eine Strasse", "n": 3,
                                      "enable_streaming": True})
    assert terminal_frame(res.get_data(as_text=True))["http_status"] == 200
    assert resolved_on == [threading.get_ident()]
    assert {r[2] for r in ran if r[0] in ("intake", "result")} == {"adult"}


def test_a_level_that_cannot_be_resolved_starts_nothing(client, ran, monkeypatch):
    def down():
        raise RuntimeError("the course lookup is down")

    monkeypatch.setattr(resolver, "resolve_safety_level", down)
    res = client.post(VARIANTS, json={"prompt": "eine Strasse", "n": 3})
    assert res.status_code == 500
    assert res.mimetype == "application/json"
    assert "the course lookup is down" in res.get_json()["error"]
    assert ran == []
