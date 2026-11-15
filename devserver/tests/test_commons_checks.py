"""The found-pictures row at the three places of the safety gate.

/api/commons/lookup has a model make a search term of a prompt, asks Wikimedia
Commons and answers up to three pictures; /api/commons/image hands those
pictures out from this server. The prompt passes the intake at the route, the
search term passes the check at the result before it is shown or searched, at
kids and youth every picture passes the check at the result, and the image
route hands out at those levels only what a search released.

What the checks decide is the matter of test_safety_gate.py. Here they are
stand-ins that keep what they were asked, and nothing reaches a model or
Wikimedia.
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

import my_app.services.safety_level_resolver as resolver
from my_app.routes import commons_routes
from my_app.services import commons_service as C
from my_app.services.safety_gate import Verdict


def passed(checkpoint, level, field=""):
    return Verdict(True, checkpoint, level, field)


def refused(checkpoint, level, field, reason_key="content"):
    return Verdict(False, checkpoint, level, field, reason_key, "refused")


class Gate:
    """One check, standing in: it keeps what it was asked and answers through
    `answer(material, level, keywords)`."""

    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    def __call__(self, material, *, level, **keywords):
        self.asked.append((material, level, keywords))
        return self.answer(material, level, keywords)


@pytest.fixture()
def gates(monkeypatch):
    """Every check passes unless a test says otherwise."""
    intake = Gate(lambda m, level, kw: passed("intake", level, kw.get("field", "")))
    text = Gate(lambda m, level, kw: passed("result", level, kw.get("field", "")))
    image = Gate(lambda m, level, kw: passed("result", level, "image"))
    monkeypatch.setattr(commons_routes, "check_intake", intake)
    monkeypatch.setattr(C, "check_result_text", text)
    monkeypatch.setattr(C, "check_result_image", image)
    return SimpleNamespace(intake=intake, text=text, image=image)


@pytest.fixture(autouse=True)
def nothing_kept():
    def clear():
        C._term_cache.clear()
        C._search_cache.clear()
        with C._released_lock:
            C._released.clear()
    clear()
    yield
    clear()


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(commons_routes.commons_bp)
    return app


def at_level(monkeypatch, level):
    monkeypatch.setattr(resolver, "resolve_safety_level", lambda: level)


def url(i):
    return f"https://upload.wikimedia.org/thumb/house{i}.jpg"


def shelf(n):
    """`n` candidates, each with its own thumbnail on an allowed host."""
    return [C.CommonsImage(
        title=f"House {i}.jpg",
        thumb_proxy=f"{C.IMAGE_ROUTE}/{C.encode_image_ref(url(i))}",
        width=800, height=600, author=f"author {i}", licence="CC BY 4.0",
        file_page=f"https://commons.wikimedia.org/wiki/File:House_{i}.jpg",
        categories=["Houses"]) for i in range(n)]


def the_archive_hands_out_its_url(monkeypatch):
    """Every thumbnail's bytes are its own URL, so a test can tell them apart."""
    fetched = []

    def fetch(u):
        fetched.append(u)
        return u.encode(), "image/jpeg"

    monkeypatch.setattr(C, "fetch_image_bytes", fetch)
    return fetched


def answered(response):
    """(payload, http_status) on either transport."""
    if response.mimetype == "text/event-stream":
        for raw in response.get_data(as_text=True).split("\n\n"):
            if raw.startswith("event: complete"):
                frame = json.loads(raw.split("data: ", 1)[1])
                return frame["body"], frame["http_status"]
        raise AssertionError("no terminal frame on this wire")
    return response.get_json(), response.status_code


# ---------------------------------------------------------------------------
# The prompt, at the intake
# ---------------------------------------------------------------------------

def test_the_prompt_goes_in_as_the_page_sent_it(app, monkeypatch, gates):
    """As the page sent it: the comparison's own gate took in that very text, and
    its pass then answers here without a second check."""
    at_level(monkeypatch, "youth")
    looked_up = []
    monkeypatch.setattr(C, "lookup_for_prompt", lambda prompt, **kw: looked_up.append(
        (prompt, kw["safety_level"])) or {"state": "nothing_found", "term": "house", "images": []})

    response = app.test_client().post("/api/commons/lookup",
                                      json={"prompt": "ein Haus am Feldrand\n"})

    assert response.status_code == 200
    assert gates.intake.asked == [("ein Haus am Feldrand\n", "youth",
                                   {"kind": "text", "field": "prompt"})]
    assert looked_up == [("ein Haus am Feldrand", "youth")]


@pytest.mark.parametrize("streaming", [False, True], ids=["plain", "stream"])
def test_a_refused_prompt_is_never_looked_up(app, monkeypatch, gates, streaming):
    at_level(monkeypatch, "kids")
    gates.intake.answer = lambda m, level, kw: refused("intake", level, "prompt", "personal_data")
    looked_up = []
    monkeypatch.setattr(C, "lookup_for_prompt", lambda *a, **kw: looked_up.append(a))
    body = {"prompt": "Erika Musterfrau in der Hauptstrasse 5"}
    if streaming:
        body["enable_streaming"] = True

    payload, status = answered(app.test_client().post("/api/commons/lookup", json=body))

    assert status == 403
    assert payload["error"] == "safety_blocked"
    assert payload["safety_block"]["checkpoint"] == "intake"
    assert payload["safety_block"]["field"] == "prompt"
    assert payload["safety_block"]["reason_key"] == "personal_data"
    assert looked_up == []


# ---------------------------------------------------------------------------
# The search term, at the result
# ---------------------------------------------------------------------------

def test_the_term_is_checked_before_the_archive_is_asked(monkeypatch, gates):
    events = []
    gates.text.answer = lambda t, level, kw: events.append(("check", t, level)) or passed(
        "result", level, kw["field"])
    monkeypatch.setattr(C, "derive_search_term", lambda prompt: ("house on a field", C.TERM_OK))
    monkeypatch.setattr(C, "search_images",
                        lambda term, **kw: events.append(("search", term)) or ([], False))

    result = C.lookup_for_prompt("ein Haus am Feldrand", safety_level="adult")

    # The widened term as well: it takes the place of the first on the screen.
    assert events == [("check", "house on a field", "adult"), ("search", "house on a field"),
                      ("check", "house field", "adult"), ("search", "house field")]
    assert [kw["field"] for _, _, kw in gates.text.asked] == ["term", "term"]
    assert result == {"state": "nothing_found", "term": "house on a field", "images": []}


@pytest.mark.parametrize("reason_key", ["content", "symbol", "unavailable"])
def test_a_term_that_does_not_pass_is_neither_shown_nor_searched(app, monkeypatch, gates,
                                                                 reason_key):
    at_level(monkeypatch, "kids")
    gates.text.answer = lambda t, level, kw: refused("result", level, "term", reason_key)
    monkeypatch.setattr(C, "derive_search_term", lambda prompt: ("tall house", C.TERM_OK))
    searched = []
    monkeypatch.setattr(C, "search_images", lambda term, **kw: searched.append(term) or ([], False))

    response = app.test_client().post("/api/commons/lookup", json={"prompt": "ein hohes Haus"})

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["safety_block"]["checkpoint"] == "result"
    assert payload["safety_block"]["field"] == "term"
    assert payload["safety_block"]["reason_key"] == reason_key
    assert "tall house" not in response.get_data(as_text=True)
    assert searched == []


def test_a_widened_term_that_does_not_pass_is_not_searched(monkeypatch, gates):
    gates.text.answer = lambda t, level, kw: (passed("result", level, "term")
                                              if t == "house on a field"
                                              else refused("result", level, "term"))
    monkeypatch.setattr(C, "derive_search_term", lambda prompt: ("house on a field", C.TERM_OK))
    searched = []
    monkeypatch.setattr(C, "search_images", lambda term, **kw: searched.append(term) or ([], False))

    result = C.lookup_for_prompt("ein Haus am Feldrand", safety_level="youth")

    assert searched == ["house on a field"]
    assert result == {"state": "nothing_found", "term": "house on a field", "images": []}


# ---------------------------------------------------------------------------
# The pictures, at the result
# ---------------------------------------------------------------------------

def test_each_picture_is_asked_about_its_own_bytes(monkeypatch, gates):
    the_archive_hands_out_its_url(monkeypatch)
    gates.image.answer = lambda picture, level, kw: (
        refused("result", level, "image", "image_content") if picture == url(1).encode()
        else passed("result", level, "image"))

    images, unverifiable = C._take(shelf(3), 3, "kids")

    assert [image.title for image in images] == ["House 0.jpg", "House 2.jpg"]
    assert unverifiable is False
    assert [(picture, level) for picture, level, _ in gates.image.asked] == [
        (url(i).encode(), "kids") for i in range(3)]
    assert C.released_for(url(0), "kids") and C.released_for(url(2), "kids")
    assert not C.released_for(url(1), "kids")


def test_a_picture_without_a_verdict_is_withheld_as_a_fault(monkeypatch, gates):
    the_archive_hands_out_its_url(monkeypatch)
    gates.image.answer = lambda picture, level, kw: refused("result", level, "image", "unavailable")

    images, unverifiable = C._take(shelf(2), 3, "youth")

    assert images == []
    assert unverifiable is True
    assert not C.released_for(url(0), "youth")


@pytest.mark.parametrize("level", ["adult", "research"])
def test_above_youth_no_picture_is_asked(monkeypatch, gates, level):
    fetched = the_archive_hands_out_its_url(monkeypatch)

    images, unverifiable = C._take(shelf(4), 3, level)

    assert len(images) == 3 and unverifiable is False
    assert gates.image.asked == [] and fetched == []


def test_a_missing_level_is_checked_as_the_strictest(monkeypatch, gates):
    """Until 2026-11-01 a missing level checked no picture at all."""
    the_archive_hands_out_its_url(monkeypatch)

    C._take(shelf(1), 3, None)

    assert len(gates.image.asked) == 1


# ---------------------------------------------------------------------------
# The image route
# ---------------------------------------------------------------------------

def served(app, u):
    return app.test_client().get(f"{C.IMAGE_ROUTE}/{C.encode_image_ref(u)}")


def test_kids_get_no_picture_a_search_did_not_release(app, monkeypatch):
    at_level(monkeypatch, "kids")
    fetched = the_archive_hands_out_its_url(monkeypatch)

    response = served(app, url(0))

    assert response.status_code == 403
    assert response.get_json()["safety_block"]["reason_key"] == "image_unchecked"
    assert fetched == [], "the archive was asked for a picture that goes nowhere"


def test_a_release_answers_for_its_level_and_the_looser_ones(app, monkeypatch, gates):
    the_archive_hands_out_its_url(monkeypatch)

    C._take(shelf(1), 1, "youth")
    at_level(monkeypatch, "kids")
    assert served(app, url(0)).status_code == 403
    at_level(monkeypatch, "youth")
    assert served(app, url(0)).status_code == 200

    C._take(shelf(1), 1, "kids")
    at_level(monkeypatch, "kids")
    assert served(app, url(0)).status_code == 200


@pytest.mark.parametrize("level", ["adult", "research"])
def test_above_youth_the_route_serves_without_a_release(app, monkeypatch, level):
    at_level(monkeypatch, level)
    the_archive_hands_out_its_url(monkeypatch)

    assert served(app, url(0)).status_code == 200


def test_what_the_row_shows_is_what_the_route_serves(app, monkeypatch, gates):
    at_level(monkeypatch, "kids")
    the_archive_hands_out_its_url(monkeypatch)
    monkeypatch.setattr(C, "derive_search_term", lambda prompt: ("house", C.TERM_OK))
    C._search_cache.set("house", [asdict(candidate) for candidate in shelf(4)])
    gates.image.answer = lambda picture, level, kw: (
        refused("result", level, "image", "image_content") if picture == url(1).encode()
        else passed("result", level, "image"))

    row = app.test_client().post("/api/commons/lookup", json={"prompt": "ein Haus"}).get_json()

    assert row["state"] == "ok"
    shown = {image["thumb_proxy"] for image in row["images"]}
    assert len(shown) == 3
    for candidate in shelf(4):
        status = app.test_client().get(candidate.thumb_proxy).status_code
        assert status == (200 if candidate.thumb_proxy in shown else 403), candidate.title


def test_only_the_asking_browser_may_keep_the_picture(app, monkeypatch):
    at_level(monkeypatch, "adult")
    the_archive_hands_out_its_url(monkeypatch)

    assert served(app, url(0)).headers["Cache-Control"] == "private, max-age=86400"


def test_a_level_that_cannot_be_read_keeps_the_picture(app, monkeypatch):
    def unreadable():
        raise RuntimeError("the course lookup is down")

    monkeypatch.setattr(resolver, "resolve_safety_level", unreadable)
    fetched = the_archive_hands_out_its_url(monkeypatch)

    response = served(app, url(0))

    assert response.status_code == 500
    assert "the course lookup is down" in response.get_json()["error"]
    assert fetched == []


def test_the_strictest_release_is_kept():
    C._remember_release(url(0), "kids")
    C._remember_release(url(0), "youth")

    assert C.released_for(url(0), "kids")


def test_the_list_forgets_its_oldest_first(monkeypatch):
    monkeypatch.setattr(C, "MAX_RELEASED", 2)
    for i in range(3):
        C._remember_release(url(i), "kids")

    assert not C.released_for(url(0), "kids")
    assert C.released_for(url(1), "kids") and C.released_for(url(2), "kids")
