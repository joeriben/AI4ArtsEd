#!/usr/bin/env python3
"""What the speech route checks before a synthesiser speaks.

What is to be spoken, and a speaker described in words, pass the intake before
anything is translated. What the synthesiser receives passes the check before
the model: the sentence as written, or its English rendering beside the
original where the synthesiser has no voice for the language, and the
description. A refusal answers 403 with the block message, and nothing is
synthesised.

The gate functions, the translation and the synthesis are stubbed; nothing here
asks a model.
"""
import base64
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.speech_routes as routes
import my_app.services.watermark_service as watermark
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         REASON_CONTENT, REASON_PERSONAL_DATA, Verdict)
from schemas.engine import pipeline_executor as PE

SPEECH = "/api/speech"

AT_THE_INTAKE = "refuse-at-the-intake"
BEFORE_THE_MODEL = "refuse-before-the-model"


class Chunk:
    """A synthesiser with a voice for German and English, and none for Hebrew."""
    ALLOWED_SAFETY_LEVELS = ("kids", "youth", "adult", "research")
    CHUNK_META = {"supported_languages": ["de", "en"], "english_fallback": True}


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(routes.speech_bp)
    return app.test_client()


@pytest.fixture
def ran(monkeypatch):
    """The checks, the translation and the synthesis recorded where they are
    reached, in that order. A text with AT_THE_INTAKE in it is refused at the
    intake, one with BEFORE_THE_MODEL before the model. The view resolves
    "youth"."""
    reached = []
    monkeypatch.setattr(routes, "resolve_safety_level", lambda: "youth")
    monkeypatch.setattr(routes, "_system_chunk", lambda system: Chunk)

    async def translate(text):
        reached.append(("translate", text))
        return f"EN: {text}"

    class Executor:
        async def execute_pipeline(self, config_name, input_text, safety_level, **_):
            reached.append(("speak", input_text, safety_level))
            audio = base64.b64encode(b"RIFF").decode()
            return SimpleNamespace(success=True, metadata={
                "audio_data": audio, "seed": 7, "voice": "even", "f0_hz": 110.0})

    def intake(fields, *, level):
        reached.append(("intake", dict(fields), level))
        for name, text in fields.items():
            if AT_THE_INTAKE in str(text or ""):
                return Verdict(False, CHECKPOINT_INTAKE, level, name, REASON_PERSONAL_DATA,
                               "a name")
        return Verdict(True, CHECKPOINT_INTAKE, level)

    def before_model(texts, *, level, originals=(), **_):
        reached.append(("before_model", dict(texts), dict(originals), level))
        for name, text in texts.items():
            if BEFORE_THE_MODEL in str(text or ""):
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_CONTENT,
                               "a text")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    monkeypatch.setattr(routes, "_translate_to_english", translate)
    monkeypatch.setattr(PE, "executor", Executor())
    monkeypatch.setattr(routes, "check_intake_texts", intake)
    monkeypatch.setattr(routes, "check_before_model", before_model)
    monkeypatch.setattr(watermark, "watermark_media_bytes", lambda audio, *a, **k: audio)
    return reached


def test_a_sentence_with_a_voice_is_checked_as_written(client, ran):
    res = client.post(SPEECH, json={"text": "Ein Haus am See.", "language": "de"})
    assert res.status_code == 200
    assert ran == [
        ("intake", {"text": "Ein Haus am See.", "voice_description": ""}, "youth"),
        ("before_model", {"text": "Ein Haus am See.", "voice_description": ""}, {},
         "youth"),
        ("speak", "Ein Haus am See.", "youth"),
    ]


def test_a_sentence_without_a_voice_is_checked_in_the_english_it_is_spoken_in(client, ran):
    """The English rendering is what the synthesiser speaks. It is checked
    beside the original, and the original passed the intake before anything
    was translated."""
    res = client.post(SPEECH, json={"text": "bayit leyad ha-agam", "language": "he"})
    assert res.status_code == 200
    assert [r[0] for r in ran] == ["intake", "translate", "before_model", "speak"]
    assert ran[2] == ("before_model", {"text": "EN: bayit leyad ha-agam", "voice_description": ""},
                      {"text": "bayit leyad ha-agam"}, "youth")


def test_a_described_speaker_passes_both_checks(client, ran):
    res = client.post(SPEECH, json={"text": "Ein Haus.", "language": "de", "system": "voxcpm",
                                    "voice_description": "eine alte Stimme"})
    assert res.status_code == 200
    assert ran[0][1]["voice_description"] == "eine alte Stimme"
    assert ran[1][1]["voice_description"] == "eine alte Stimme"


def test_a_sentence_refused_at_the_intake_is_neither_translated_nor_spoken(client, ran):
    res = client.post(SPEECH, json={"text": f"a {AT_THE_INTAKE}", "language": "he"})
    assert res.status_code == 403
    body = res.get_json()
    assert body["error"] == "safety_blocked"
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert body["safety_block"]["field"] == "text"
    assert [r[0] for r in ran] == ["intake"]


def test_a_description_refused_before_the_model_is_not_spoken(client, ran):
    res = client.post(SPEECH, json={"text": "Ein Haus.", "language": "de", "system": "voxcpm",
                                    "voice_description": f"a {BEFORE_THE_MODEL}"})
    assert res.status_code == 403
    body = res.get_json()
    assert body["safety_block"]["checkpoint"] == CHECKPOINT_BEFORE_MODEL
    assert body["safety_block"]["field"] == "voice_description"
    assert "speak" not in [r[0] for r in ran]


def test_the_level_is_the_one_the_view_resolved(client, ran, monkeypatch):
    monkeypatch.setattr(routes, "resolve_safety_level", lambda: "kids")
    client.post(SPEECH, json={"text": "Ein Haus.", "language": "de"})
    assert {r[-1] for r in ran} == {"kids"}
