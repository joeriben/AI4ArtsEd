"""The training place and the platform's checks.

The dropped images pass the intake before any of them is kept, at the level
of the request; a refused one refuses its handful and leaves a set that is
already here as it was. What the describing model writes is checked at the
result before it is set where the list is read: a refused sentence is
withheld, a check without an answer counts as no answer. A start takes the
project name, the trigger words and the sentences in at the intake, and every
picture it trains on, before anything of an earlier project of that name is
deleted.

No model is called: the gate functions are stubbed where the code calls them.
"""
import io
import json
import threading
from types import SimpleNamespace

import pytest
from flask import Flask

from my_app.routes import training_routes as routes
from my_app.services import training_service as T
from my_app.services.safety_gate import Verdict


class Gate:
    """Stands in for the gate: records what it is asked, and refuses or gives
    no answer where it is told to."""

    def __init__(self):
        self.intake = []
        self.result = []
        self.refuse_field = None
        self.reason_key = "image_content"
        self.refuse_text = None
        self.unanswered_text = None

    def check_intake(self, material, *, level, kind, field):
        self.intake.append((material, level, kind, field))
        if field == self.refuse_field:
            return Verdict(False, "intake", level, field, self.reason_key, "")
        return Verdict(True, "intake", level, field)

    def check_result_text(self, text, *, level, field="text"):
        self.result.append((text, level, field))
        if text == self.refuse_text:
            return Verdict(False, "result", level, field, "content", "")
        if text == self.unanswered_text:
            return Verdict(False, "result", level, field, "unavailable", "no answer")
        return Verdict(True, "result", level, field)


class NoThread:
    """The describing thread, held back: the test calls the describing itself."""

    started = []

    def __init__(self, target, args, daemon):
        self.target, self.args = target, args

    def start(self):
        NoThread.started.append(self.args)


class Upload:
    """What the training place reads from an upload: a name and a stream."""

    def __init__(self, name, data=b"picture"):
        self.filename = name
        self.file = io.BytesIO(data)


@pytest.fixture
def place(monkeypatch, tmp_path):
    monkeypatch.setattr(T, "DATASET_BASE_DIR", tmp_path / "datasets")
    monkeypatch.setattr(T, "STAGING_DIR", tmp_path / "datasets" / ".staging")
    monkeypatch.setattr(T.TrainingService, "get_gpu_vram", lambda self: 96.0)
    svc = T.TrainingService()
    NoThread.started = []
    monkeypatch.setattr(T, "threading", SimpleNamespace(Thread=NoThread, Lock=threading.Lock))
    return svc


@pytest.fixture
def gate(monkeypatch):
    g = Gate()
    monkeypatch.setattr(T, "check_intake", g.check_intake)
    monkeypatch.setattr(T, "check_result_text", g.check_result_text)
    return g


def _stage(place, names, level="youth"):
    out = place.stage_and_describe([Upload(n, n.encode()) for n in names], level=level)
    return out["token"]


# ── Describing ──────────────────────────────────────────────────────────────

def test_the_pictures_pass_the_intake_at_the_level_before_any_is_kept(place, gate):
    out = place.stage_and_describe([Upload("a.png", b"one"), Upload("b.jpg", b"two")],
                                   level="youth")
    assert gate.intake == [(b"one", "youth", "image", "images[0]"),
                           (b"two", "youth", "image", "images[1]")]
    staged = T.STAGING_DIR / out["token"]
    # The bytes the intake saw are the bytes that are kept.
    assert (staged / "001.png").read_bytes() == b"one"
    assert (staged / "002.jpg").read_bytes() == b"two"
    assert [i["withheld"] for i in out["items"]] == [False, False]
    # The describing gets the level of the request.
    assert NoThread.started[0][2] == "youth"


def test_a_refused_picture_keeps_none_of_its_handful(place, gate):
    gate.refuse_field = "images[1]"
    with pytest.raises(T.PicturesRefused) as refused:
        place.stage_and_describe([Upload("a.png"), Upload("b.png")], level="kids")
    assert refused.value.verdict.field == "images[1]"
    assert not T.STAGING_DIR.exists() or not any(T.STAGING_DIR.iterdir())
    assert NoThread.started == []


def test_a_refused_handful_leaves_the_set_that_is_here_as_it_was(place, gate):
    token = _stage(place, ["a.png"])
    gate.refuse_field = "images[0]"
    with pytest.raises(T.PicturesRefused):
        place.stage_and_describe([Upload("b.png")], token=token, level="youth")
    assert [p.name for p in (T.STAGING_DIR / token).iterdir()] == ["001.png"]
    assert [i["file"] for i in place.description_status(token)["items"]] == ["001.png"]


def test_a_sentence_is_set_only_after_the_check_at_the_result(place, gate, monkeypatch):
    monkeypatch.setattr(T, "CAPTION_ENABLED", True)
    monkeypatch.setattr(T.TrainingService, "_describe_image",
                        lambda self, path: f"a picture called {path.name}")
    token = _stage(place, ["a.png", "b.png", "c.png"])
    gate.refuse_text = "a picture called 002.png"
    gate.unanswered_text = "a picture called 003.png"
    items = place.description_status(token)["items"]
    place._describe_staged(token, list(items), "kids")
    assert [(i["caption"], i["failed"], i["withheld"]) for i in items] == [
        ("a picture called 001.png", False, False),
        (None, False, True),
        (None, True, False),
    ]
    assert gate.result == [
        ("a picture called 001.png", "kids", "captions[0]"),
        ("a picture called 002.png", "kids", "captions[1]"),
        ("a picture called 003.png", "kids", "captions[2]"),
    ]
    assert place.description_status(token)["running"] is False


def test_a_picture_the_model_did_not_answer_for_is_not_checked(place, gate, monkeypatch):
    monkeypatch.setattr(T, "CAPTION_ENABLED", True)

    def no_answer(self, path):
        raise RuntimeError("the model answered nothing")

    monkeypatch.setattr(T.TrainingService, "_describe_image", no_answer)
    token = _stage(place, ["a.png"])
    items = place.description_status(token)["items"]
    place._describe_staged(token, list(items), "youth")
    assert (items[0]["caption"], items[0]["failed"], items[0]["withheld"]) == (None, True, False)
    assert gate.result == []


# ── Starting ────────────────────────────────────────────────────────────────

def _earlier_project():
    earlier = T.DATASET_BASE_DIR / "MeineSonne"
    earlier.mkdir(parents=True, exist_ok=True)
    (earlier / "earlier.txt").write_text("an earlier run")
    return earlier


def test_a_start_takes_the_staged_pictures_in_before_an_earlier_project_is_deleted(place, gate):
    token = _stage(place, ["a.png", "b.png"])
    earlier = _earlier_project()
    gate.intake.clear()
    gate.refuse_field = "images[1]"
    with pytest.raises(T.PicturesRefused):
        place.create_project("Meine Sonne", [], "sonne", staging_token=token,
                             captions=["eins", "zwei"], level="kids")
    assert (earlier / "earlier.txt").exists()
    assert sorted(p.name for p in (T.STAGING_DIR / token).iterdir()) == ["001.png", "002.png"]
    assert [(m.name, lvl, k, f) for m, lvl, k, f in gate.intake] == [
        ("001.png", "kids", "image", "images[0]"),
        ("002.png", "kids", "image", "images[1]"),
    ]


def test_a_start_trains_on_staged_pictures_that_passed(place, gate):
    token = _stage(place, ["a.png", "b.png"])
    result = place.create_project("Meine Sonne", [], "sonne", staging_token=token,
                                  captions=["eins", "zwei"], level="youth")
    assert result["image_count"] == 2
    assert not (T.STAGING_DIR / token).exists()


def test_a_start_with_uploads_takes_them_in_before_anything_is_written(place, gate):
    earlier = _earlier_project()
    gate.refuse_field = "images[0]"
    with pytest.raises(T.PicturesRefused):
        place.create_project("Meine Sonne", [Upload("a.png", b"one")], "sonne", level="youth")
    assert (earlier / "earlier.txt").exists()
    assert gate.intake == [(b"one", "youth", "image", "images[0]")]


# ── The routes ──────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(routes.training_bp)
    monkeypatch.setattr(routes, "resolve_safety_level", lambda: "youth")
    return app.test_client()


def _refusal(field, reason_key):
    return Verdict(False, "intake", "youth", field, reason_key, "")


def test_describe_hands_the_level_on(client, monkeypatch):
    seen = {}

    def stage(images, token=None, *, level):
        seen.update(level=level, names=[i.filename for i in images], token=token)
        return {"token": "t", "running": True, "items": []}

    monkeypatch.setattr(routes.training_service, "stage_and_describe", stage)
    r = client.post("/api/training/describe",
                    data={"images": [(io.BytesIO(b"x"), "a.png")], "token": "t0"},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    assert seen == {"level": "youth", "names": ["a.png"], "token": "t0"}


def test_describe_answers_a_refused_picture_with_the_block(client, monkeypatch):
    def refuse(images, token=None, *, level):
        raise T.PicturesRefused(_refusal("images[0]", "image_content"))

    monkeypatch.setattr(routes.training_service, "stage_and_describe", refuse)
    r = client.post("/api/training/describe",
                    data={"images": [(io.BytesIO(b"x"), "a.png")]},
                    content_type="multipart/form-data")
    assert r.status_code == 403
    body = r.get_json()
    assert body["error"] == "safety_blocked"
    assert body["safety_block"]["reason_key"] == "image_content"
    assert body["safety_block"]["field"] == "images[0]"


@pytest.fixture
def start(client, monkeypatch):
    """The start route with a recording intake and a project that is only noted."""
    asked, created = [], {}
    refuse = {}

    def intake(material, *, level, kind, field):
        asked.append((material, level, kind, field))
        if field in refuse:
            return _refusal(field, refuse[field])
        return Verdict(True, "intake", level, field)

    def intake_texts(fields, *, level):
        for name, text in fields.items():
            verdict = intake(text, level=level, kind="text", field=name)
            if not verdict.passed:
                return verdict
        return Verdict(True, "intake", level)

    def create(name, images, trigger, **kw):
        created.update(name=name, trigger=trigger, **kw)
        return {"project_name": name}

    monkeypatch.setattr(routes, "check_intake", intake)
    monkeypatch.setattr(routes, "check_intake_texts", intake_texts)
    monkeypatch.setattr(routes.training_service, "create_project", create)
    monkeypatch.setattr(routes.training_service, "start_training_process", lambda name: True)
    return SimpleNamespace(client=client, asked=asked, created=created, refuse=refuse)


FORM = {"project_name": "Meine Sonne", "trigger_word": "sonne", "staging_token": "t",
        "captions": json.dumps(["eins", "zwei"])}


def test_a_start_takes_name_trigger_and_sentences_in(start):
    r = start.client.post("/api/training/start", data=FORM)
    assert r.status_code == 200
    assert [(m, lvl, k, f) for m, lvl, k, f in start.asked] == [
        ("Meine Sonne", "youth", "text", "project_name"),
        ("sonne", "youth", "text", "trigger_word"),
        ("eins", "youth", "text", "captions[0]"),
        ("zwei", "youth", "text", "captions[1]"),
    ]
    assert start.created["level"] == "youth"


@pytest.mark.parametrize("field", ["trigger_word", "captions[1]"])
def test_a_refused_text_starts_nothing(start, field):
    start.refuse[field] = "personal_data"
    r = start.client.post("/api/training/start", data=FORM)
    assert r.status_code == 403
    block = r.get_json()["safety_block"]
    assert (block["reason_key"], block["field"]) == ("personal_data", field)
    assert start.created == {}


def test_a_refused_picture_at_the_start_answers_with_the_block(start, monkeypatch):
    def refuse(*args, **kw):
        raise T.PicturesRefused(_refusal("images[3]", "image_content"))

    monkeypatch.setattr(routes.training_service, "create_project", refuse)
    r = start.client.post("/api/training/start", data=FORM)
    assert r.status_code == 403
    assert r.get_json()["safety_block"]["field"] == "images[3]"
