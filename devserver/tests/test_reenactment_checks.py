#!/usr/bin/env python3
"""What the Re-enactment chain checks on its way to the song.

What was heard passes the intake before the page shows it or anything is made
from it. The reading, a language model's rendering of those words, passes the
check of the result before it is shown. The lyrics and the tags pass the check
before the model before the page shows them, and the same verdict stands for
the song: with the English rendering beside the lyrics where the speaking voice
gets one, made before the check. A refused station is a failed event with the
block message and none of the refused text.

The machines, the writer, the singer and the checks are stubbed; nothing here
asks a model.
"""
import base64
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.parrot_routes as routes
import my_app.services.media_analysis_client as analysis
import my_app.services.parrot_service as ps
import my_app.services.watermark_service as watermark
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         CHECKPOINT_RESULT, REASON_CONTENT,
                                         REASON_PERSONAL_DATA, Verdict)
from schemas.engine import pipeline_executor as PE

AT_THE_INTAKE = "refuse-at-the-intake"
AT_THE_RESULT = "refuse-at-the-result"
BEFORE_THE_MODEL = "refuse-before-the-model"


class Machines:
    """The ranker and the transcriber: the recording was heard as German."""
    heard = {"text": "ein Lied am See", "language": "german"}

    def tag(self, path, model=None):
        return [{"label": "a single voice singing alone", "score": 0.9}]

    def transcribe(self, path, language=None):
        return dict(self.heard)


@pytest.fixture
def chain(monkeypatch, tmp_path):
    """The stations, recorded where they are reached, in order. A text with
    AT_THE_INTAKE in it is refused at the intake, one with AT_THE_RESULT at the
    result, one with BEFORE_THE_MODEL before the model."""
    reached = []
    machines = Machines()
    written = {"tags": "pop, warm", "lyrics": "la la am See", "styled": True}

    def read_in(text, target):
        reached.append(("read_in", text, target))
        return f"{target}: {text}"

    def write_song(ranking, second, transcription, seconds):
        reached.append(("write", transcription))
        return dict(written)

    def sing(song, song_ms, config_id, lang=None, english=None):
        reached.append(("sing", config_id, lang, english))
        return b"ID3", "mp3"

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

    def before_model(texts, *, level, originals=(), **_):
        reached.append(("before_model", dict(texts), dict(originals), level))
        for name, text in texts.items():
            if BEFORE_THE_MODEL in str(text or ""):
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_CONTENT,
                               "a text")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    monkeypatch.setattr(analysis, "get_media_analysis_client", lambda: machines)
    monkeypatch.setattr(ps, "_recording_seconds", lambda path: 12.0)
    monkeypatch.setattr(ps, "_writer_model", lambda: "writer")
    monkeypatch.setattr(ps, "_read_in", read_in)
    monkeypatch.setattr(ps, "_write_song", write_song)
    monkeypatch.setattr(ps, "_sing", sing)
    monkeypatch.setattr(ps, "check_intake_texts", intake)
    monkeypatch.setattr(ps, "check_result_text", result)
    monkeypatch.setattr(ps, "check_before_model", before_model)
    monkeypatch.setattr(watermark, "watermark_media_bytes", lambda audio, *a, **k: audio)

    class Chain:
        def run(self, singer=ps.SONG_CONFIG, reading="en", level="youth"):
            path = str(tmp_path / "recording.wav")
            return [e for e in ps.run_chain(path, reading=reading, singer=singer, level=level)
                    if e["status"] != "running"]

    run = Chain()
    run.reached, run.machines, run.written = reached, machines, written
    return run


def test_every_station_passes_its_check_before_it_is_shown(chain):
    events = chain.run()
    assert [(e["station"], e["status"]) for e in events] == [
        ("ranked", "done"), ("words", "done"), ("reading", "done"),
        ("written", "done"), ("sung", "done")]
    assert [r[0] for r in chain.reached] == [
        "intake", "read_in", "result", "write", "before_model", "sing"]
    assert chain.reached[0] == ("intake", {"transcription": "ein Lied am See"}, "youth")
    assert chain.reached[2] == ("result", "English: ein Lied am See", "youth", "reading")
    assert chain.reached[4] == ("before_model", {"lyrics": "la la am See", "tags": "pop, warm"},
                                {}, "youth")


def test_words_refused_at_the_intake_are_not_shown_and_nothing_is_made_of_them(chain):
    chain.machines.heard = {"text": f"a {AT_THE_INTAKE}", "language": "german"}
    events = chain.run()
    refused = events[-1]
    assert (refused["station"], refused["status"]) == ("words", "failed")
    assert refused["safety_block"]["checkpoint"] == CHECKPOINT_INTAKE
    assert "text" not in refused
    assert [r[0] for r in chain.reached] == ["intake"]


def test_a_refused_reading_is_not_shown_and_the_chain_goes_on(chain):
    chain.machines.heard = {"text": f"a {AT_THE_RESULT}", "language": "german"}
    events = chain.run()
    reading = next(e for e in events if e["station"] == "reading")
    assert reading["status"] == "failed" and "text" not in reading
    assert reading["safety_block"]["field"] == "reading"
    assert events[-1]["station"] == "sung"


def test_lyrics_refused_before_the_model_are_neither_shown_nor_sung(chain):
    chain.written["lyrics"] = f"la {BEFORE_THE_MODEL}"
    events = chain.run()
    refused = events[-1]
    assert (refused["station"], refused["status"]) == ("written", "failed")
    assert refused["safety_block"]["checkpoint"] == CHECKPOINT_BEFORE_MODEL
    assert "lyrics" not in refused and "tags" not in refused
    assert "sing" not in [r[0] for r in chain.reached]


def test_the_speaking_voice_gets_its_english_rendering_before_the_check(chain):
    """The rendering is a language model's text, and the voice may speak it:
    it is made before the check, checked beside the lyrics, and handed in. The
    page is read in German here, so there is no reading station."""
    chain.run(singer=ps.SPEECH_CONFIG, reading="de")
    assert [r[0] for r in chain.reached] == [
        "intake", "write", "read_in", "before_model", "sing"]
    assert chain.reached[2] == ("read_in", "la la am See", "English")
    assert chain.reached[3] == ("before_model",
                                {"lyrics": "English: la la am See", "tags": "pop, warm"},
                                {"lyrics": "la la am See"}, "youth")
    assert chain.reached[4] == ("sing", ps.SPEECH_CONFIG, "de", "English: la la am See")


def test_the_singer_writes_no_text_of_its_own(monkeypatch):
    """Nothing rewrites the text between the check and the machine: the speaking
    voice is handed the rendering run_chain made, and _sing asks no language
    model for one."""
    handed = []

    def read_in(text, target):
        raise AssertionError("_sing asked a language model for a rendering")

    class Executor:
        async def execute_pipeline(self, config_name, input_text, user_input,
                                   context_override, **_):
            handed.append((config_name, dict(context_override.custom_placeholders)))
            audio = base64.b64encode(b"RIFF").decode()
            return SimpleNamespace(success=True, error=None,
                                   metadata={"audio_data": audio, "audio_format": "wav"})

    monkeypatch.setattr(ps, "_read_in", read_in)
    monkeypatch.setattr(PE, "executor", Executor())
    song = {"tags": "pop", "lyrics": "bayit leyad ha-agam", "styled": True}
    sung = ps._sing(song, 12_000, ps.SPEECH_CONFIG, lang="he", english="a house by the lake")
    assert sung == (b"RIFF", "wav")
    assert handed == [(ps.SPEECH_CONFIG, {"TEXT_1": "bayit leyad ha-agam",
                                          "text_en": "a house by the lake"})]


def test_the_level_travels_with_the_chain(chain):
    chain.run(level="kids")
    assert {r[-1] for r in chain.reached if r[0] in ("intake", "before_model")} == {"kids"}
    assert {r[2] for r in chain.reached if r[0] == "result"} == {"kids"}


def test_the_view_resolves_the_level_and_hands_it_on(monkeypatch, tmp_path):
    """The stream runs after the view has returned, where the request is no
    longer there: the level is resolved in the view."""
    (tmp_path / "recording.wav").write_bytes(b"RIFF")
    handed = []

    def run_chain(path, language=None, reading=None, singer=None, *, level):
        handed.append(level)
        yield {"station": "ranked", "status": "running"}

    monkeypatch.setattr(routes, "resolve_safety_level", lambda: "youth")
    monkeypatch.setattr(ps, "recording_dir", lambda recording_id: str(tmp_path))
    monkeypatch.setattr(ps, "run_chain", run_chain)
    app = Flask(__name__)
    app.register_blueprint(routes.parrot_bp)
    res = app.test_client().get("/api/parrot/stream/abc")
    assert "complete" in res.get_data(as_text=True)
    assert handed == ["youth"]
