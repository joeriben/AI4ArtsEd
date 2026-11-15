"""The safety gate's six functions, without a model.

my_app/services/safety_gate.py carries the three places where the platform
checks: the intake, the check before the model, and the result. These tests
stand every model in with a stub and show what is asked of them:

  * research asks nothing;
  * no answer is a block, a failed translation for the check as well;
  * a list hit brings the symbol question, and decides nothing by itself;
  * a picture without a verdict is refused at kids, and a pass at youth does
    not answer for kids;
  * each of the five ways a picture is referred to finds its verdict, and a
    path outside the uploads and the run folders has none;
  * code with fetch( brings the code question, which names what was found;
  * a video is put the level's question in the classifier's form, by the
    video reader, and a check that gave no answer writes no verdict;
  * without a level there is no call.

The questions are read from the classifier's own tables, so that a change of
wording does not change what these tests show.

Run: python3 -m pytest devserver/tests/test_safety_gate.py -q
"""

import base64
import copy
import io
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image

import config
from my_app.services import media_analysis_client
from my_app.services import safety_classifier
from my_app.services import safety_gate as gate
from my_app.utils import vlm_safety
from schemas.engine import stage_orchestrator


# ── Stand-ins ───────────────────────────────────────────────────────────────

class FakeClassifier:
    """Stands in for safety_classifier.score. Answers by the question asked."""

    def __init__(self):
        self.calls = []
        self.answers = {}
        self.default = 0.0

    def __call__(self, instruct, query, document, images=None):
        self.calls.append((query, document))
        for needle, value in self.answers.items():
            if needle == query:
                return value
        return self.default

    def asked(self, query):
        return [document for q, document in self.calls if q == query]


class FakeImageCheck:
    def __init__(self):
        self.calls = []
        self.safe = True
        self.operational = False

    def __call__(self, path, level):
        self.calls.append((str(path), level))
        if self.safe:
            return True, "", ""
        if self.operational:
            return False, vlm_safety.VLM_OPERATIONAL_BLOCK_MESSAGE, ""
        return False, vlm_safety.VLM_CONTENT_BLOCK_MESSAGE, ""


class FakeVideoCheck:
    """Stands in for the video reader's yes/no question (score_video)."""

    def __init__(self):
        self.calls = []
        self.value = 0.0
        self.raises = None

    def score_video(self, path, system_prompt, prompt):
        self.calls.append((str(path), system_prompt, prompt))
        if self.raises is not None:
            raise self.raises
        if self.value is None:
            media_analysis_client.LAST_REASON.set("the reader is not installed")
        return self.value


class FakeRecorder:
    def __init__(self):
        self.marks = []

    def mark_entity_safety(self, sequence, safe, reason="", description="", level=None):
        self.marks.append((sequence, safe, level))
        return True


def prompt_question(level):
    return safety_classifier.LEVEL_QUERIES[level]["prompt"]


def text_question(level):
    return safety_classifier.LEVEL_QUERIES[level]["text"]


def code_question(*patterns):
    """The code question as the gate asks it, naming what the list found."""
    return safety_classifier.CODE_POLICY[1].replace("{patterns}", ", ".join(patterns))


def code_questions(fake):
    """The documents the code question was asked about, whatever it named."""
    stem = safety_classifier.CODE_POLICY[1].split("{patterns}")[0]
    return [document for query, document in fake.calls if query.startswith(stem)]


SYMBOL_QUESTION = safety_classifier.SYMBOL_POLICY[1]
SYMBOL_TEXT_QUESTION = safety_classifier.SYMBOL_TEXT_POLICY[1]
ADULT_SYMBOL_QUESTION = safety_classifier.ADULT_SYMBOL_POLICY[1]
ADULT_SYMBOL_TEXT_QUESTION = safety_classifier.ADULT_SYMBOL_TEXT_POLICY[1]
NAME_QUESTION = safety_classifier.NAME_POLICY[1]


@pytest.fixture
def classifier(monkeypatch):
    fake = FakeClassifier()
    monkeypatch.setattr(safety_classifier, "score", fake)
    return fake


@pytest.fixture
def names(monkeypatch):
    """The name recogniser: available, and finding nothing unless told to."""
    state = {"found": [], "available": True}

    def fake(text):
        return bool(state["found"]), list(state["found"]), state["available"]

    monkeypatch.setattr(stage_orchestrator, "fast_dsgvo_check", fake)
    return state


@pytest.fixture
def translation(monkeypatch):
    calls = []
    state = {"english": lambda text: f"EN: {text}"}

    def fake(text, instruction=None):
        calls.append(text)
        return state["english"](text)

    monkeypatch.setattr(gate, "_translate_for_check", fake)
    state["calls"] = calls
    return state


@pytest.fixture
def images(monkeypatch):
    fake = FakeImageCheck()
    monkeypatch.setattr(vlm_safety, "vlm_safety_check", fake)
    return fake


@pytest.fixture
def videos(monkeypatch):
    fake = FakeVideoCheck()
    monkeypatch.setattr(media_analysis_client, "get_media_analysis_client", lambda: fake)
    return fake


@pytest.fixture
def storage(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads_tmp"
    runs = tmp_path / "json"
    uploads.mkdir()
    runs.mkdir()
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", uploads)
    monkeypatch.setattr(config, "JSON_STORAGE_DIR", runs)
    return uploads, runs


@pytest.fixture(autouse=True)
def fresh_memory():
    gate._RELEASED.clear()
    with gate._TRANSLATIONS_LOCK:
        gate._TRANSLATIONS.clear()
    stage_orchestrator._dsgvo_verify_cache.clear()
    yield
    gate._RELEASED.clear()


def png_bytes(colour=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", (80, 80), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def write_upload(uploads, upload_id, colour=(200, 30, 30)):
    path = uploads / f"{upload_id}.png"
    path.write_bytes(png_bytes(colour))
    return path


def write_run(runs, run_id, *, run_level, verdict=None, kind="output_image"):
    """A recorded run with one picture, as the recorder writes it to disk."""
    folder = runs / "2026-10-30" / "dev_test" / run_id
    (folder / "final").mkdir(parents=True)
    filename = "01_output_image.png"
    (folder / "final" / filename).write_bytes(png_bytes())
    entity = {"type": kind, "sequence": 1, "filename": filename, "metadata": {}}
    if verdict is not None:
        entity["metadata"]["safety"] = verdict
    (folder / "metadata.json").write_text(json.dumps({
        "run_id": run_id, "config_name": "test", "safety_level": run_level,
        "safety_verdicts": True, "entities": [entity],
    }))
    return folder / "final" / filename


# ── The level ───────────────────────────────────────────────────────────────

class TestTheLevel:
    def test_no_level_no_call(self, classifier, names, translation, images, videos):
        calls = [
            lambda: gate.check_intake("Max Muster", kind="text", field="prompt"),
            lambda: gate.check_before_model({"prompt": "a dog"}),
            lambda: gate.check_result_image(b"", ),
            lambda: gate.check_result_video("clip.mp4"),
            lambda: gate.check_result_text("a text"),
            lambda: gate.check_result_code("let x = 1"),
        ]
        for call in calls:
            with pytest.raises(TypeError):
                call()
        assert classifier.calls == []
        assert translation["calls"] == []
        assert images.calls == []
        assert videos.calls == []

    def test_an_unknown_level_is_checked_as_kids(self, classifier, translation):
        verdict = gate.check_before_model({"prompt": "a dog"}, level="banana")
        assert verdict.passed and verdict.level == "kids"
        assert classifier.asked(prompt_question("kids"))

    def test_a_pass_answers_for_its_level_and_every_looser_one(self):
        assert gate.counts_for("kids", "youth")
        assert gate.counts_for("youth", "youth")
        assert not gate.counts_for("youth", "kids")
        assert gate.counts_for("youth", "adult")
        assert not gate.counts_for("nonsense", "research")


class TestResearch:
    def test_research_asks_nothing(self, classifier, names, translation, images, videos,
                                   storage, tmp_path):
        uploads, _ = storage
        recorder = FakeRecorder()
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not looked at")
        verdicts = [
            gate.check_intake("Max Mustermann, Hauptstraße 12", level="research",
                              kind="text", field="prompt"),
            gate.check_intake(png_bytes(), level="research", kind="image", field="image"),
            gate.check_intake(["Hakenkreuz"], level="research", kind="document", field="document"),
            gate.check_intake("Hakenkreuz", level="research", kind="chat", field="message"),
            gate.check_before_model({"prompt": "Hakenkreuz"}, level="research",
                                    images=[str(uploads / "missing.png")]),
            gate.check_result_image(png_bytes(), level="research", recorder=recorder, entity=1),
            gate.check_result_video(clip, level="research", recorder=recorder, entity=3),
            gate.check_result_text("Hakenkreuz", level="research"),
            gate.check_result_code("fetch('x')", level="research", recorder=recorder, entity=2),
        ]
        assert all(v.passed for v in verdicts)
        assert classifier.calls == []
        assert translation["calls"] == []
        assert images.calls == []
        assert videos.calls == []
        assert recorder.marks == []


# ── 1. The intake ───────────────────────────────────────────────────────────

class TestIntakeText:
    def test_nothing_found_nothing_asked(self, classifier, names):
        verdict = gate.check_intake("a dog in the snow", level="kids", kind="text", field="prompt")
        assert verdict.passed
        assert classifier.calls == []

    def test_a_name_brings_the_name_question(self, classifier, names):
        names["found"] = ["Name: Max Mustermann"]
        classifier.answers[NAME_QUESTION] = 0.9
        verdict = gate.check_intake("Max Mustermann paints", level="youth", kind="text",
                                    field="context_prompt")
        assert not verdict.passed
        assert verdict.reason_key == gate.REASON_PERSONAL_DATA
        assert verdict.checkpoint == gate.CHECKPOINT_INTAKE
        assert verdict.field == "context_prompt"
        assert len(classifier.asked(NAME_QUESTION)) == 1

    def test_the_name_question_can_release(self, classifier, names):
        names["found"] = ["Name: Paul Klee"]
        verdict = gate.check_intake("like Paul Klee", level="adult", kind="text", field="prompt")
        assert verdict.passed
        assert len(classifier.asked(NAME_QUESTION)) == 1

    def test_an_address_brings_the_name_question(self, classifier, names):
        verdict = gate.check_intake("ein Haus in der Hauptstraße 12", level="kids",
                                    kind="text", field="prompt")
        assert verdict.passed
        asked = classifier.asked(NAME_QUESTION)
        assert len(asked) == 1 and "Hauptstraße 12" in asked[0]

    def test_without_the_recogniser_the_question_is_always_asked(self, classifier, names):
        names["available"] = False
        gate.check_intake("a dog", level="kids", kind="text", field="prompt")
        assert len(classifier.asked(NAME_QUESTION)) == 1

    def test_no_answer_is_a_block(self, classifier, names):
        names["found"] = ["Name: Max Mustermann"]
        classifier.answers[NAME_QUESTION] = None
        verdict = gate.check_intake("Max Mustermann", level="kids", kind="text", field="prompt")
        assert not verdict.passed and verdict.operational

    def test_the_breaker_counts_the_name_question(self, classifier, names, monkeypatch):
        """The breaker decides nothing. It is told when the name question
        failed and when it answered, and only then."""
        counted = []
        monkeypatch.setattr(gate.safety_breaker, "record_failure",
                            lambda: counted.append("failed"))
        monkeypatch.setattr(gate.safety_breaker, "record_success",
                            lambda: counted.append("answered"))
        names["found"] = ["Name: Max Mustermann"]
        classifier.answers[NAME_QUESTION] = None
        gate.check_intake("Max Mustermann", level="kids", kind="text", field="prompt")
        classifier.answers[NAME_QUESTION] = 0.0
        gate.check_intake("Max Mustermann malt", level="kids", kind="text", field="prompt")
        names["found"] = []
        gate.check_intake("ein Hund", level="kids", kind="text", field="prompt")
        assert counted == ["failed", "answered"]

    def test_once_per_text(self, classifier, names):
        names["found"] = ["Name: Paul Klee"]
        for level in ("youth", "youth", "adult"):
            # The name check keeps answers of its own for a minute; without
            # them, what is left is the gate's memory.
            stage_orchestrator._dsgvo_verify_cache.clear()
            gate.check_intake("like Paul Klee", level=level, kind="text", field="prompt")
        assert len(classifier.asked(NAME_QUESTION)) == 1

    def test_a_released_result_is_no_new_material(self, classifier, names):
        assert gate.check_result_text("Max Mustermann was here", level="kids").passed
        names["found"] = ["Name: Max Mustermann"]
        verdict = gate.check_intake("Max Mustermann was here", level="kids", kind="text",
                                    field="history")
        assert verdict.passed
        assert classifier.asked(NAME_QUESTION) == []

    def test_several_fields(self, classifier, names):
        names["found"] = ["Name: Max Mustermann"]
        classifier.answers[NAME_QUESTION] = 0.9
        verdict = gate.check_intake_texts({"prompt": "", "prompt_b": "Max Mustermann"}, level="kids")
        assert not verdict.passed and verdict.field == "prompt_b"
        assert verdict.reason_key == gate.REASON_PERSONAL_DATA


class TestIntakeChat:
    """What a chat turn takes in: names and addresses, the lists, and after a
    list hit the symbol question. The level's text question is not asked."""

    HIT = "Das Hakenkreuz in der Kunstgeschichte"

    @pytest.mark.parametrize("level", ["kids", "youth", "adult"])
    def test_no_text_question_of_any_level(self, classifier, names, level):
        for asked in ("kids", "youth", "adult"):
            classifier.answers[text_question(asked)] = 0.9
        assert gate.check_intake("eine Nachricht", level=level, kind="chat",
                                 field="message").passed
        assert classifier.calls == []

    def test_a_list_hit_brings_the_symbol_question(self, classifier, names):
        assert gate.check_intake(self.HIT, level="youth", kind="chat",
                                 field="message").passed
        assert classifier.asked(SYMBOL_TEXT_QUESTION) == [self.HIT]
        assert classifier.asked(text_question("youth")) == []

    def test_the_symbol_question_refuses(self, classifier, names):
        classifier.answers[SYMBOL_TEXT_QUESTION] = 0.9
        verdict = gate.check_intake(self.HIT, level="youth", kind="chat", field="message")
        assert not verdict.passed and verdict.reason_key == gate.REASON_SYMBOL
        assert verdict.checkpoint == gate.CHECKPOINT_INTAKE
        assert verdict.field == "message"

    def test_a_list_that_cannot_be_read_is_a_block(self, classifier, names, monkeypatch):
        def broken(_texts):
            raise RuntimeError("list file missing")

        monkeypatch.setattr(gate, "_symbol_terms", broken)
        verdict = gate.check_intake("eine Nachricht", level="adult", kind="chat",
                                    field="message")
        assert not verdict.passed and verdict.operational

    def test_a_name_is_refused_before_the_lists(self, classifier, names):
        names["found"] = ["Name: Max Mustermann"]
        classifier.answers[NAME_QUESTION] = 0.9
        verdict = gate.check_intake("Max Mustermann und das Hakenkreuz", level="adult",
                                    kind="chat", field="message")
        assert verdict.reason_key == gate.REASON_PERSONAL_DATA
        assert classifier.asked(ADULT_SYMBOL_TEXT_QUESTION) == []

    def test_no_answer_is_a_block(self, classifier, names):
        classifier.answers[ADULT_SYMBOL_TEXT_QUESTION] = None
        verdict = gate.check_intake(self.HIT, level="adult", kind="chat", field="message")
        assert not verdict.passed and verdict.operational

    def test_once_per_text(self, classifier, names):
        gate.check_intake(self.HIT, level="youth", kind="chat", field="message")
        gate.check_intake(self.HIT, level="youth", kind="chat", field="history")
        assert len(classifier.asked(SYMBOL_TEXT_QUESTION)) == 1

    def test_a_pass_of_the_names_alone_does_not_answer_for_the_lists(self, classifier, names):
        gate.check_intake(self.HIT, level="youth", kind="text", field="prompt")
        assert classifier.calls == []
        gate.check_intake(self.HIT, level="youth", kind="chat", field="message")
        assert len(classifier.asked(SYMBOL_TEXT_QUESTION)) == 1

    REPLY = "Eine Antwort über das Hakenkreuz."

    def test_the_chats_reply_comes_back_in_the_history_as_no_new_material(
            self, classifier, names):
        gate.remember_chat_reply(self.REPLY, level="kids")
        assert gate.check_intake(self.REPLY, level="kids", kind="chat",
                                 field="history").passed
        assert classifier.calls == []

    def test_a_reply_sent_back_as_a_message_is_new_material(self, classifier, names):
        gate.remember_chat_reply(self.REPLY, level="kids")
        classifier.answers[SYMBOL_TEXT_QUESTION] = 0.9
        assert not gate.check_intake(self.REPLY, level="kids", kind="chat",
                                     field="message").passed
        assert classifier.asked(SYMBOL_TEXT_QUESTION) == [self.REPLY]

    def test_a_reply_does_not_pass_the_result_check(self, classifier, names):
        """The chats do not check their replies: a reply that comes back as a
        prompt, a caption or a card is asked what any text is asked."""
        gate.remember_chat_reply(self.REPLY, level="kids")
        classifier.answers[text_question("kids")] = 0.9
        assert not gate.check_result_text(self.REPLY, level="kids").passed
        assert classifier.asked(text_question("kids")) == [self.REPLY]

    def test_a_reply_does_not_pass_the_intake_of_a_prompt(self, classifier, names):
        gate.remember_chat_reply("Max Mustermann was here", level="kids")
        names["found"] = ["Name: Max Mustermann"]
        classifier.answers[NAME_QUESTION] = 0.9
        assert not gate.check_intake("Max Mustermann was here", level="kids", kind="text",
                                     field="prompt").passed

    def test_a_reply_written_at_adult_is_new_material_at_kids(self, classifier, names):
        gate.remember_chat_reply(self.REPLY, level="adult")
        gate.check_intake(self.REPLY, level="kids", kind="chat", field="history")
        assert classifier.asked(SYMBOL_TEXT_QUESTION) == [self.REPLY]

    def test_several_fields(self, classifier, names):
        classifier.answers[ADULT_SYMBOL_TEXT_QUESTION] = 0.9
        verdict = gate.check_intake_texts({"message": "", "context": self.HIT},
                                          level="adult", kind="chat")
        assert not verdict.passed and verdict.field == "context"


class TestIntakeImage:
    def test_kids_asks_the_picture_question(self, images):
        verdict = gate.check_intake(png_bytes(), level="kids", kind="image", field="image")
        assert verdict.passed
        assert images.calls and images.calls[0][1] == "kids"

    def test_adult_is_not_asked(self, images):
        assert gate.check_intake(png_bytes(), level="adult", kind="image", field="image").passed
        assert images.calls == []

    def test_a_refusal_and_a_fault_are_told_apart(self, images):
        images.safe = False
        refused = gate.check_intake(png_bytes(), level="kids", kind="image", field="image")
        assert not refused.passed and refused.reason_key == gate.REASON_IMAGE_CONTENT
        images.operational = True
        fault = gate.check_intake(png_bytes((1, 2, 3)), level="kids", kind="image", field="image")
        assert not fault.passed and fault.operational

    def test_a_picture_the_disk_cannot_take_is_a_fault(self, images, monkeypatch, caplog):
        """The check reads a file. A picture that came as data and cannot be
        written down was never looked at: withheld as a fault, with its cause."""
        def full(**_):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(gate.tempfile, "mkstemp", full)
        caplog.set_level(logging.ERROR, logger="my_app.services.safety_gate")
        verdict = gate.check_intake(png_bytes((4, 5, 6)), level="kids", kind="image",
                                    field="image")
        assert not verdict.passed and verdict.operational
        assert images.calls == []
        assert "No space left on device" in caplog.text

    def test_the_verdict_is_kept_beside_the_upload(self, images, storage):
        uploads, _ = storage
        path = write_upload(uploads, "u-1")
        verdict = gate.check_intake(path, level="youth", kind="image", field="image")
        assert gate.record_upload_verdict("u-1", verdict)
        assert gate.upload_cleared_for("u-1", "youth")
        assert gate.upload_cleared_for("u-1", "adult")
        assert not gate.upload_cleared_for("u-1", "kids")
        assert not gate.upload_cleared_for("../u-1", "youth")


class TestIntakeDocument:
    def test_a_list_hit_asks_the_text_question_not_the_symbol_question(self, classifier, names):
        verdict = gate.check_intake(["Ein Bericht über das Hakenkreuz."], level="youth",
                                    kind="document", field="document")
        assert verdict.passed
        assert len(classifier.asked(text_question("youth"))) == 1
        assert classifier.asked(SYMBOL_QUESTION) == []
        assert classifier.asked(SYMBOL_TEXT_QUESTION) == []

    def test_at_adult_the_text_question_of_adult(self, classifier, names):
        verdict = gate.check_intake(["Ein Bericht über das Hakenkreuz."], level="adult",
                                    kind="document", field="document")
        assert verdict.passed
        assert len(classifier.asked(text_question("adult"))) == 1

    def test_a_refused_section_is_named(self, classifier, names):
        classifier.answers[text_question("kids")] = 0.8
        verdict = gate.check_intake(["Ein Garten.", "Das Hakenkreuz."], level="kids",
                                    kind="document", field="document")
        assert not verdict.passed and verdict.field == "document[1]"
        assert verdict.reason_key == gate.REASON_CONTENT

    def test_kids_refuses_the_section_youth_refuses(self, classifier, names):
        classifier.answers[text_question("youth")] = 0.8
        verdict = gate.check_intake(["Das Hakenkreuz."], level="kids",
                                    kind="document", field="document")
        assert not verdict.passed and verdict.reason_key == gate.REASON_CONTENT
        assert len(classifier.asked(text_question("kids"))) == 1
        assert len(classifier.asked(text_question("youth"))) == 1

    def test_names_section_by_section(self, classifier, names):
        names["found"] = ["Name: Max Mustermann"]
        classifier.answers[NAME_QUESTION] = 0.9
        verdict = gate.check_intake(["Max Mustermann"], level="adult", kind="document",
                                    field="document")
        assert not verdict.passed and verdict.reason_key == gate.REASON_PERSONAL_DATA


# ── 2. Before the model ─────────────────────────────────────────────────────

class TestBeforeModel:
    def test_both_versions_are_asked(self, classifier, translation):
        verdict = gate.check_before_model({"prompt": "ein Hund"}, level="youth")
        assert verdict.passed
        assert classifier.asked(prompt_question("youth")) == ["ein Hund", "EN: ein Hund"]

    def test_a_given_translation_is_the_english_version(self, classifier, translation):
        gate.check_before_model({"prompt": "a dog"}, originals={"prompt": "ein Hund"},
                                level="kids")
        assert translation["calls"] == []
        assert classifier.asked(prompt_question("kids")) == ["ein Hund", "a dog"]

    def test_a_failed_translation_is_a_block(self, classifier, translation):
        translation["english"] = lambda text: None
        verdict = gate.check_before_model({"prompt": "ein Hund"}, level="kids")
        assert not verdict.passed and verdict.operational
        assert classifier.calls == []

    def test_no_answer_is_a_block(self, classifier, translation):
        classifier.default = None
        verdict = gate.check_before_model({"prompt": "a dog"}, level="youth")
        assert not verdict.passed and verdict.operational

    @pytest.mark.parametrize("value", [["ein Hund"], {"de": "ein Hund"}, 3, b"ein Hund"])
    def test_what_is_no_text_is_withheld_unread(self, classifier, translation, value):
        """The model would receive what the check cannot read as a text."""
        verdict = gate.check_before_model({"prompt": "a dog", "negative_prompt": value},
                                          level="adult")
        assert not verdict.passed and verdict.operational
        assert verdict.field == "negative_prompt"

    def test_none_and_an_empty_text_are_no_text(self, classifier, translation):
        verdict = gate.check_before_model({"prompt": "a dog", "negative_prompt": None,
                                           "prompt_3": "  "},
                                          originals={"prompt": "ein Hund"}, level="kids")
        assert verdict.passed
        assert classifier.asked(prompt_question("kids")) == ["ein Hund", "a dog"]

    def test_a_list_hit_brings_the_symbol_question(self, classifier, translation):
        verdict = gate.check_before_model({"prompt": "ein Hakenkreuz"}, level="kids")
        assert verdict.passed, "a list hit alone decides nothing"
        assert classifier.asked(SYMBOL_QUESTION)
        classifier.answers[SYMBOL_QUESTION] = 0.95
        verdict = gate.check_before_model({"negative_prompt": "ein Hakenkreuz"}, level="kids")
        assert not verdict.passed
        assert verdict.reason_key == gate.REASON_SYMBOL
        assert verdict.field == "negative_prompt"

    def test_at_adult_the_symbol_question_with_the_exception_for_a_context(
            self, classifier, translation):
        assert gate.check_before_model({"prompt": "ein Hakenkreuz"}, level="adult").passed
        assert classifier.asked(ADULT_SYMBOL_QUESTION)
        assert classifier.asked(SYMBOL_QUESTION) == []

    def test_the_lists_of_every_language(self, classifier, translation):
        translation["english"] = lambda text: "a harmless sentence"
        gate.check_before_model({"prompt": "gamalı haç"}, level="youth")
        assert classifier.asked(SYMBOL_QUESTION), "a Turkish term is looked for in any interface"

    def test_the_level_question_refuses(self, classifier, translation):
        classifier.answers[prompt_question("kids")] = 0.7
        verdict = gate.check_before_model({"prompt": "ein Hund"}, level="kids")
        assert not verdict.passed and verdict.reason_key == gate.REASON_CONTENT
        assert verdict.checkpoint == gate.CHECKPOINT_BEFORE_MODEL

    def test_adult_asks_its_own_question(self, classifier, translation):
        classifier.answers[prompt_question("adult")] = 0.8
        verdict = gate.check_before_model({"prompt": "ein Hund"}, level="adult")
        assert not verdict.passed and verdict.reason_key == gate.REASON_CONTENT
        assert classifier.asked(prompt_question("adult")) == ["ein Hund"]
        assert classifier.asked(prompt_question("kids")) == []

    def test_kids_refuses_what_youth_refuses(self, classifier, translation):
        """The levels are ordered by construction, not by wording. On
        2026-11-07 kids let a prompt pass ("88" and "HH" on a wall) that youth
        refused, with the sentence on number codes standing in both instructs
        word for word: a level asks its own question and then the question of
        every less strict level, and the first yes refuses."""
        classifier.answers[prompt_question("youth")] = 0.8
        verdict = gate.check_before_model({"prompt": "ein Hund"}, level="kids")
        assert not verdict.passed and verdict.reason_key == gate.REASON_CONTENT
        assert classifier.asked(prompt_question("kids")) == ["ein Hund"]
        assert classifier.asked(prompt_question("youth")) == ["ein Hund"]

    def test_youth_refuses_what_adult_refuses(self, classifier, translation):
        classifier.answers[prompt_question("adult")] = 0.8
        verdict = gate.check_before_model({"prompt": "ein Hund"}, level="youth")
        assert not verdict.passed and verdict.reason_key == gate.REASON_CONTENT
        assert classifier.asked(prompt_question("adult")) == ["ein Hund"]
        assert classifier.asked(prompt_question("kids")) == []

    def test_the_questions_go_strictest_first_and_stop_at_the_first_yes(
            self, classifier, translation):
        classifier.answers[prompt_question("kids")] = 0.8
        assert not gate.check_before_model({"prompt": "ein Hund"}, level="kids").passed
        assert classifier.asked(prompt_question("youth")) == []
        assert classifier.asked(prompt_question("adult")) == []

    def test_every_question_of_the_chain_is_asked_about_both_versions(
            self, classifier, translation):
        assert gate.check_before_model({"prompt": "ein Hund"}, level="kids").passed
        for level in ("kids", "youth", "adult"):
            assert classifier.asked(prompt_question(level)) == ["ein Hund", "EN: ein Hund"]

    def test_kids_refuses_the_symbol_adult_refuses(self, classifier, translation):
        classifier.answers[ADULT_SYMBOL_QUESTION] = 0.95
        verdict = gate.check_before_model({"prompt": "ein Hakenkreuz"}, level="kids")
        assert not verdict.passed and verdict.reason_key == gate.REASON_SYMBOL
        assert classifier.asked(SYMBOL_QUESTION) and classifier.asked(ADULT_SYMBOL_QUESTION)

    def test_a_level_without_a_question_is_withheld(self, classifier, translation, monkeypatch):
        queries = copy.deepcopy(safety_classifier.LEVEL_QUERIES)
        queries.pop("youth")
        monkeypatch.setattr(safety_classifier, "LEVEL_QUERIES", queries)
        verdict = gate.check_before_model({"prompt": "a dog"}, level="youth")
        assert not verdict.passed and verdict.operational
        assert classifier.calls == []


class TestImageReferences:
    def test_a_picture_without_a_verdict_is_refused_at_kids(self, classifier, translation, storage):
        uploads, _ = storage
        write_upload(uploads, "u-2")
        verdict = gate.check_before_model({}, level="kids", images=["u-2"])
        assert not verdict.passed
        assert verdict.reason_key == gate.REASON_IMAGE_UNCHECKED

    def test_a_pass_at_youth_does_not_answer_for_kids(self, storage):
        uploads, _ = storage
        write_upload(uploads, "u-3")
        gate.record_upload_verdict("u-3", gate.Verdict(True, gate.CHECKPOINT_INTAKE, "youth"))
        assert gate.check_before_model({}, level="youth", images=["u-3"]).passed
        verdict = gate.check_before_model({}, level="kids", images=["u-3"])
        assert not verdict.passed and verdict.reason_key == gate.REASON_IMAGE_UNCHECKED

    def test_the_five_references_find_their_verdict(self, storage, images):
        uploads, runs = storage
        path = write_upload(uploads, "u-4")
        gate.record_upload_verdict("u-4", gate.Verdict(True, gate.CHECKPOINT_INTAKE, "kids"))
        write_run(runs, "run_gate_five", run_level="kids", verdict={"safe": True, "level": "kids"})

        assert gate.image_reference_cleared(str(path), "kids")                      # 1. path
        assert gate.image_reference_cleared(path, "kids")
        assert gate.image_reference_cleared("u-4", "kids")                           # 2. upload id
        assert gate.image_reference_cleared("/api/media/uploads/u-4", "kids")        # 3.
        assert gate.image_reference_cleared("/api/media/image/run_gate_five/0", "kids")  # 4.
        assert gate.image_reference_cleared("run_gate_five", "kids")
        data_url = "data:image/png;base64," + base64.b64encode(png_bytes()).decode()  # 5.
        assert gate.check_before_model({}, level="kids", images=[data_url]).passed
        assert images.calls, "a picture that comes as data is judged when it comes"

    def test_a_run_picture_by_its_path(self, storage):
        _, runs = storage
        picture = write_run(runs, "run_gate_path", run_level="youth",
                            verdict={"safe": True, "level": "youth"})
        assert gate.image_reference_cleared(str(picture), "youth")
        assert not gate.image_reference_cleared(str(picture), "kids")

    def test_an_old_verdict_counts_at_the_level_of_its_run(self, storage):
        _, runs = storage
        write_run(runs, "run_gate_old", run_level="youth", verdict={"safe": True})
        assert gate.image_reference_cleared("/api/media/image/run_gate_old/0", "youth")
        assert not gate.image_reference_cleared("/api/media/image/run_gate_old/0", "kids")

    def test_an_unchecked_run_picture_has_no_verdict(self, storage):
        _, runs = storage
        write_run(runs, "run_gate_adult", run_level="adult")
        assert not gate.image_reference_cleared("/api/media/image/run_gate_adult/0", "youth")

    def test_a_path_elsewhere_has_no_verdict(self, storage, tmp_path):
        elsewhere = tmp_path / "elsewhere.png"
        elsewhere.write_bytes(png_bytes())
        assert not gate.image_reference_cleared(str(elsewhere), "youth")
        assert not gate.image_reference_cleared("/etc/passwd", "youth")
        assert not gate.image_reference_cleared("/api/media/audio/run_x/0", "youth")

    def test_adult_does_not_ask_about_pictures(self, classifier, translation, storage):
        uploads, _ = storage
        write_upload(uploads, "u-5")
        assert gate.check_before_model({}, level="adult", images=["u-5"]).passed


# ── 3. At the result ────────────────────────────────────────────────────────

class TestResultImage:
    def test_the_verdict_is_written_with_its_level(self, images):
        recorder = FakeRecorder()
        verdict = gate.check_result_image(png_bytes(), level="youth", recorder=recorder, entity=7)
        assert verdict.passed
        assert recorder.marks == [(7, True, "youth")]

    def test_adult_is_not_checked(self, images):
        recorder = FakeRecorder()
        assert gate.check_result_image(png_bytes(), level="adult", recorder=recorder, entity=7).passed
        assert images.calls == [] and recorder.marks == []

    def test_a_missing_file_is_a_block(self, images, tmp_path):
        verdict = gate.check_result_image(tmp_path / "nothing.png", level="kids")
        assert not verdict.passed and verdict.operational

    def test_a_refusal_is_written_with_its_level(self, images):
        recorder = FakeRecorder()
        images.safe = False
        verdict = gate.check_result_image(png_bytes(), level="kids", recorder=recorder, entity=7)
        assert not verdict.passed and not verdict.operational
        assert recorder.marks == [(7, False, "kids")]

    def test_a_check_that_did_not_run_writes_no_verdict(self, images, tmp_path):
        """No verdict leaves the picture withheld all the same, and a later
        check can still clear it; a fault written down as a refusal could not
        be lifted."""
        recorder = FakeRecorder()
        images.safe, images.operational = False, True
        verdict = gate.check_result_image(png_bytes(), level="youth", recorder=recorder, entity=7)
        assert not verdict.passed and verdict.operational
        verdict = gate.check_result_image(tmp_path / "nothing.png", level="kids",
                                          recorder=recorder, entity=8)
        assert not verdict.passed and verdict.operational
        assert recorder.marks == []

    def test_a_picture_the_disk_cannot_take_is_a_fault(self, images, monkeypatch, caplog):
        """The same at the result, where a picture stands in a response body."""
        def full(**_):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(gate.tempfile, "mkstemp", full)
        caplog.set_level(logging.ERROR, logger="my_app.services.safety_gate")
        verdict = gate.check_result_image(png_bytes(), level="youth")
        assert not verdict.passed and verdict.operational
        assert images.calls == []
        assert "No space left on device" in caplog.text

    def test_a_write_that_fails_leaves_no_scratch_behind(self, images, monkeypatch, tmp_path):
        def read_only(prefix="", suffix="", **_):
            name = str(tmp_path / f"{prefix}picture{suffix}")
            # Opened for reading only: the write fails, as it does on a full disk.
            return os.open(name, os.O_RDONLY | os.O_CREAT), name

        monkeypatch.setattr(gate.tempfile, "mkstemp", read_only)
        verdict = gate.check_result_image(png_bytes(), level="kids")
        assert not verdict.passed and verdict.operational
        assert images.calls == []
        assert list(tmp_path.iterdir()) == []


class TestResultVideo:
    @pytest.fixture
    def clip(self, tmp_path):
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"a video")
        return path

    def test_the_level_question_in_the_classifier_form(self, videos, clip):
        """The classifier takes no video; its question goes to the video
        reader, with the classifier's system line, instruct and query."""
        recorder = FakeRecorder()
        verdict = gate.check_result_video(clip, level="youth", recorder=recorder, entity=5)
        assert verdict.passed
        assert verdict.checkpoint == gate.CHECKPOINT_RESULT and verdict.field == "video"
        system_prompt, prompt = safety_classifier.video_question(
            safety_classifier.policy_for_level("youth", "video"))
        assert videos.calls == [(str(clip), system_prompt, prompt)]
        assert system_prompt == safety_classifier.CLASSIFIER_SYSTEM
        assert safety_classifier.LEVEL_INSTRUCTS["youth"] in prompt
        assert safety_classifier.LEVEL_QUERIES["youth"]["video"] in prompt
        assert recorder.marks == [(5, True, "youth")]

    def test_kids_is_asked_its_own_question(self, videos, clip):
        gate.check_result_video(clip, level="kids")
        assert safety_classifier.LEVEL_QUERIES["kids"]["video"] in videos.calls[0][2]
        assert safety_classifier.LEVEL_INSTRUCTS["kids"] in videos.calls[0][2]

    def test_kids_is_asked_youths_question_as_well(self, videos, clip):
        """A pass of the reader per question: kids' first, then youth's, so
        that kids refuses the video youth refuses. youth asks its own alone."""
        assert gate.check_result_video(clip, level="kids").passed
        assert len(videos.calls) == 2
        assert safety_classifier.LEVEL_QUERIES["youth"]["video"] in videos.calls[1][2]
        assert safety_classifier.LEVEL_INSTRUCTS["youth"] in videos.calls[1][2]
        videos.calls.clear()
        assert gate.check_result_video(clip, level="youth").passed
        assert len(videos.calls) == 1

    def test_adult_is_not_checked(self, videos, clip):
        recorder = FakeRecorder()
        assert gate.check_result_video(clip, level="adult", recorder=recorder, entity=5).passed
        assert videos.calls == [] and recorder.marks == []

    @pytest.mark.parametrize("value, passed", [(0.49, True), (0.5, False), (0.97, False)])
    def test_the_threshold_of_the_classifier(self, videos, clip, value, passed):
        videos.value = value
        assert gate.check_result_video(clip, level="kids").passed is passed

    def test_a_refusal_is_written_with_its_level(self, videos, clip):
        recorder = FakeRecorder()
        videos.value = 0.8
        verdict = gate.check_result_video(clip, level="kids", recorder=recorder, entity=5)
        assert not verdict.passed and not verdict.operational
        assert verdict.reason_key == gate.REASON_VIDEO_CONTENT
        assert verdict.block()["reason_key"] == "video_content"
        assert recorder.marks == [(5, False, "kids")]

    @pytest.mark.parametrize("failure", ["none", "raises", "missing"])
    def test_a_check_that_did_not_run_is_a_block_and_writes_no_verdict(
            self, videos, clip, tmp_path, failure):
        """No verdict leaves the video withheld all the same, and a later check
        can still clear it; a fault written down as a refusal could not be
        lifted."""
        recorder = FakeRecorder()
        path = clip
        if failure == "none":
            videos.value = None
        elif failure == "raises":
            videos.raises = RuntimeError("ComfyUI is not answering")
        else:
            path = tmp_path / "nothing.mp4"
        verdict = gate.check_result_video(path, level="youth", recorder=recorder, entity=5)
        assert not verdict.passed and verdict.operational
        assert recorder.marks == []
        if failure == "missing":
            assert videos.calls == []

    def test_delivery_calls_a_refused_video_a_video(self):
        assert gate.delivery_block("blocked", field="video")["reason_key"] == \
            gate.REASON_VIDEO_CONTENT
        assert gate.delivery_block("unchecked", field="video")["reason_key"] == \
            gate.REASON_UNCHECKED
        assert gate.delivery_block("blocked", field="video")["field"] == "video"


class TestPreview:
    """A picture shown while it is being made has no verdict of its own."""

    @pytest.mark.parametrize("level", ["kids", "youth", None, "banana"])
    def test_held_back_where_pictures_are_checked(self, level):
        assert gate.preview_for("data:image/jpeg;base64,AAAA", level=level) is None

    @pytest.mark.parametrize("level", ["adult", "research"])
    def test_goes_out_where_no_picture_is_checked(self, level):
        assert gate.preview_for("data:image/jpeg;base64,AAAA", level=level) == \
            "data:image/jpeg;base64,AAAA"

    def test_not_without_a_level(self):
        with pytest.raises(TypeError):
            gate.preview_for("data:image/jpeg;base64,AAAA")


class TestResultText:
    def test_the_text_question_of_the_level(self, classifier):
        classifier.answers[text_question("adult")] = 0.6
        verdict = gate.check_result_text("a text", level="adult", field="wikipedia_reason")
        assert not verdict.passed and verdict.reason_key == gate.REASON_CONTENT
        assert verdict.checkpoint == gate.CHECKPOINT_RESULT
        assert verdict.field == "wikipedia_reason"

    def test_kids_refuses_the_text_youth_refuses(self, classifier):
        classifier.answers[text_question("youth")] = 0.8
        verdict = gate.check_result_text("a text", level="kids")
        assert not verdict.passed and verdict.reason_key == gate.REASON_CONTENT
        assert classifier.asked(text_question("kids")) == ["a text"]
        assert classifier.asked(text_question("youth")) == ["a text"]

    def test_a_list_hit_brings_the_symbol_question_for_a_text(self, classifier):
        assert gate.check_result_text("Das Hakenkreuz in der Kunstgeschichte", level="youth").passed
        assert classifier.asked(SYMBOL_TEXT_QUESTION)
        assert classifier.asked(SYMBOL_QUESTION) == []

    def test_at_adult_the_symbol_question_for_a_text_with_the_exception(self, classifier):
        assert gate.check_result_text("Das Hakenkreuz in der Kunstgeschichte", level="adult").passed
        assert classifier.asked(ADULT_SYMBOL_TEXT_QUESTION)
        assert classifier.asked(SYMBOL_TEXT_QUESTION) == []

    def test_a_released_text_is_not_asked_again(self, classifier):
        gate.check_result_text("a text", level="kids")
        # kids asks its own text question and those of youth and adult.
        assert len(classifier.calls) == 3
        for level in ("kids", "youth", "adult"):
            assert classifier.asked(text_question(level)) == ["a text"]
        gate.check_result_text("a text", level="youth")
        assert len(classifier.calls) == 3

    def test_a_pass_at_youth_does_not_answer_for_kids(self, classifier):
        gate.check_result_text("a text", level="youth")
        gate.check_result_text("a text", level="kids")
        # youth's question once at youth and once in kids' chain; kids' once.
        assert len(classifier.asked(text_question("youth"))) == 2
        assert len(classifier.asked(text_question("kids"))) == 1


class TestResultCode:
    def test_fetch_brings_the_code_question(self, classifier):
        recorder = FakeRecorder()
        code = "fetch('https://example.org')"
        classifier.answers[code_question("fetch(")] = 0.9
        verdict = gate.check_result_code(code, level="kids", recorder=recorder, entity=3)
        assert not verdict.passed and verdict.reason_key == gate.REASON_CODE
        assert classifier.asked(code_question("fetch(")) == [code], \
            "the question names what the list found; the document is the sketch"
        assert recorder.marks == [(3, False, "kids")]

    def test_the_question_names_every_construct_found(self, classifier):
        code = "localStorage.setItem('best', 3); fetch('scores.json')"
        assert gate.check_result_code(code, level="youth").passed
        assert classifier.asked(code_question("localStorage.", "fetch(")) == [code]

    def test_ordinary_code_asks_only_the_text_question(self, classifier):
        verdict = gate.check_result_code("function draw() { circle(10, 10, 5) }", level="kids")
        assert verdict.passed
        assert code_questions(classifier) == []
        assert classifier.asked(text_question("kids"))

    def test_adult_runs_no_pattern_list(self, classifier):
        assert gate.check_result_code("fetch('x')", level="adult").passed
        assert code_questions(classifier) == []

    def test_without_a_code_question_flagged_code_is_withheld(self, classifier, monkeypatch):
        monkeypatch.delattr(safety_classifier, "CODE_POLICY")
        recorder = FakeRecorder()
        verdict = gate.check_result_code("localStorage.setItem('a', 1)", level="youth",
                                         recorder=recorder, entity=3)
        assert not verdict.passed and verdict.operational
        assert recorder.marks == [], "a check that did not run writes no verdict"


# ── The pieces it is built on ───────────────────────────────────────────────

def test_the_list_of_every_language_finds_what_two_languages_miss():
    found, _ = stage_orchestrator.fast_filter_bilingual_86a("gamalı haç", "de")
    assert not found
    found, terms = stage_orchestrator.fast_filter_86a_all_languages("gamalı haç")
    assert found and terms


def test_the_block_message():
    verdict = gate.Verdict(False, gate.CHECKPOINT_BEFORE_MODEL, "kids", "prompt_b",
                           gate.REASON_SYMBOL, "GRUND: §86a StGB")
    assert verdict.block() == {"checkpoint": "before_model", "field": "prompt_b",
                               "reason_key": "symbol", "reason": "GRUND: §86a StGB"}


@pytest.mark.parametrize("text, expected", [
    ("Hauptstraße 12", ["Hauptstraße 12"]),
    ("Berliner Straße 5a", ["Straße 5a"]),
    ("221B Baker Street", ["221B Baker Street"]),
    ("im Jahr 1945", []),
    ("Hauptstraße 1234", []),
    ("ein Hund im Park", []),
])
def test_addresses(text, expected):
    assert gate.find_addresses(text) == expected
