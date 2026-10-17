"""The answer from Wikimedia says when it is unfinished, and it is now read.

The detail call asks 40 files for all their categories at once. MediaWiki caps
a batch at 500 rows for a client without apihighlimits, and says so in
``continue.clcontinue``; the files past the cut come back with NO ``categories``
key. Nothing here looked at that word until 2026-09-09, and an empty list is
what a file with no categories at all sends. Both screens read that list --
``_is_ai_generated`` in the search, ``_is_explicit`` before a picture is shown
-- so 21 of 40 files were cleared by screens that had nothing to look at.

Measured against the live archive the same day, term "painting": 500 rows and
21 empty lists before, 1177 rows and none empty after.

The shapes below are MediaWiki's own (formatversion 2: ``query.pages`` is a
list, and a continuation carries only the property that was cut off).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from my_app.services import commons_service as C


def _page(pageid, title, categories, with_info=True):
    page = {"pageid": pageid, "title": title,
            "categories": [{"title": f"Category:{c}"} for c in categories]}
    if with_info:
        page["imageinfo"] = [{"descriptionurl": f"https://example/{pageid}",
                              "thumburl": f"https://example/{pageid}.jpg"}]
    return page


def _answer(pages, cont=None):
    out = {"query": {"pages": pages}}
    if cont:
        out["continue"] = cont
    return out


def _replies(monkeypatch, answers):
    """Hand out the prepared answers in order; record what was asked."""
    asked = []

    def _fake(params):
        asked.append(dict(params))
        return answers[len(asked) - 1] if len(asked) <= len(answers) else None

    monkeypatch.setattr(C, "_api_get", _fake)
    return asked


# --------------------------------------------------------------------------
# Following the continuation
# --------------------------------------------------------------------------

def test_a_finished_answer_is_taken_as_it_is(monkeypatch):
    asked = _replies(monkeypatch, [_answer([_page(1, "File:a", ["Art"])])])
    out = C._api_get_complete({"action": "query"})
    assert len(asked) == 1
    assert out["query"]["pages"][0]["categories"] == [{"title": "Category:Art"}]


def test_the_cut_off_categories_are_fetched_and_joined(monkeypatch):
    first = _answer([_page(1, "File:a", ["Art"]), _page(2, "File:b", [])],
                    cont={"clcontinue": "1|Art", "continue": "||imageinfo"})
    # A continuation carries only what was cut off: categories, no imageinfo.
    second = _answer([_page(1, "File:a", ["Paintings"], with_info=False),
                      _page(2, "File:b", ["Nudity"], with_info=False)])
    asked = _replies(monkeypatch, [first, second])

    out = C._api_get_complete({"action": "query", "cllimit": "max"})

    assert len(asked) == 2
    assert asked[1]["clcontinue"] == "1|Art", "the continuation was not sent back"
    pages = {p["title"]: p for p in out["query"]["pages"]}
    assert [c["title"] for c in pages["File:a"]["categories"]] == \
        ["Category:Art", "Category:Paintings"]
    assert [c["title"] for c in pages["File:b"]["categories"]] == ["Category:Nudity"]
    assert "continue" not in out


def test_the_first_answers_imageinfo_survives_the_merge(monkeypatch):
    """The continuation has none; overwriting would lose the thumbnail and licence."""
    first = _answer([_page(1, "File:a", ["Art"])],
                    cont={"clcontinue": "1|Art"})
    second = _answer([_page(1, "File:a", ["Paintings"], with_info=False)])
    _replies(monkeypatch, [first, second])

    out = C._api_get_complete({"action": "query"})
    assert out["query"]["pages"][0]["imageinfo"][0]["descriptionurl"]


def test_a_page_that_only_the_continuation_names_is_kept(monkeypatch):
    first = _answer([_page(1, "File:a", ["Art"])], cont={"clcontinue": "1|Art"})
    second = _answer([_page(2, "File:b", ["Sculpture"], with_info=False)])
    _replies(monkeypatch, [first, second])

    out = C._api_get_complete({"action": "query"})
    assert {p["title"] for p in out["query"]["pages"]} == {"File:a", "File:b"}


def test_pages_as_a_mapping_merge_too(monkeypatch):
    """formatversion 1 shape. The service asks for 2, but the merge does not care."""
    first = {"query": {"pages": {"1": _page(1, "File:a", ["Art"])}},
             "continue": {"clcontinue": "1|Art"}}
    second = {"query": {"pages": {"1": _page(1, "File:a", ["Paintings"], with_info=False)}}}
    _replies(monkeypatch, [first, second])

    out = C._api_get_complete({"action": "query"})
    assert len(out["query"]["pages"]["1"]["categories"]) == 2


# --------------------------------------------------------------------------
# What happens when it cannot be finished
# --------------------------------------------------------------------------

def test_an_answer_that_never_finishes_is_not_returned_half(monkeypatch):
    endless = [_answer([_page(1, "File:a", ["Art"])], cont={"clcontinue": "1|Art"})
               for _ in range(C.MAX_CONTINUATIONS + 5)]
    asked = _replies(monkeypatch, endless)

    assert C._api_get_complete({"action": "query"}) is None
    assert len(asked) == C.MAX_CONTINUATIONS + 1


def test_a_failed_continuation_discards_the_whole_answer(monkeypatch):
    first = _answer([_page(1, "File:a", ["Art"])], cont={"clcontinue": "1|Art"})
    _replies(monkeypatch, [first, None])

    assert C._api_get_complete({"action": "query"}) is None


def test_a_first_call_that_fails_stays_a_failure(monkeypatch):
    _replies(monkeypatch, [None])
    assert C._api_get_complete({"action": "query"}) is None


# --------------------------------------------------------------------------
# The screens never see a half answer
# --------------------------------------------------------------------------

def test_the_search_says_unaskable_rather_than_screening_on_half(monkeypatch):
    """``None`` means the archive could not be asked -- the row says so.

    The alternative is the state this replaces: a picture cleared by two screens
    that were handed an empty category list.
    """
    C._search_cache._data.pop("cont-test", None)

    search = _answer([])
    search["query"] = {"search": [{"title": "File:a"}, {"title": "File:b"}]}
    detail = _answer([_page(1, "File:a", ["Art"])], cont={"clcontinue": "1|Art"})
    _replies(monkeypatch, [search, detail, None])

    assert C.search_images("cont-test") is None
