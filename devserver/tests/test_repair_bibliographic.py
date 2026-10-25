"""
Tests for the bibliographic repair script (devserver/scripts/repair_bibliographic_ids.py).

The load-bearing logic is the DO-NO-HARM heuristic: a plausible existing title +
a low-confidence identification must be KEPT (skipped), while a blank/known-bad
title is replaced whenever the identifier found one, and a high-confidence
identification always applies. The LLM is mocked; the plan is asserted without
any writes.

Run: python3 -m pytest devserver/tests/test_repair_bibliographic.py -q
"""

import importlib
import sys
from pathlib import Path

# devserver/tests/... -> parents[1] == devserver/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pytest


def _load_repair():
    import repair_bibliographic_ids as r
    return importlib.reload(r)


# ---------------------------------------------------------------------------
# Pure heuristics
# ---------------------------------------------------------------------------

def test_title_plausibility_heuristic():
    r = _load_repair()
    # Known-bad byline / masthead / chapter-head -> not plausible.
    assert not r._title_is_plausible("Ernst wAgnEr", "art105413")
    assert not r._title_is_plausible("IJRCAAE", "aug100500")
    assert not r._title_is_plausible("Künstlerische Strategien",
                                     "oa9783839449851-seiten-93-189-seiten-3-48")
    # Blank / a bare question / a filename-slug title -> not plausible.
    assert not r._title_is_plausible("", "x")
    assert not r._title_is_plausible(
        "Welche Rolle spielt der Faktor Beziehung?", "oa…-49-66")
    assert not r._title_is_plausible("Digitale Sympoiesis und kulturelle Resilienz",
                                     "digitale-sympoiesis-und-kulturelle-resilienz")
    # A real, distinct work title -> plausible (must be protected).
    assert r._title_is_plausible(
        "TIBET: Identifying and Evaluating Biases in Text-to-Image Generative Models",
        "chinchure-et-al-2024-tibet-identifying-and-evaluating-biases-in-text-t")
    assert r._title_is_plausible(
        "Stable Diffusion Exposed: Gender Bias from Prompt to Image",
        "wu-et-al-2023-stable-diffusion-exposed-gender-bias-from-prompt")


def test_looks_like_doc_id():
    r = _load_repair()
    assert r._looks_like_doc_id("Digitale Sympoiesis und kulturelle Resilienz",
                                "digitale-sympoiesis-und-kulturelle-resilienz-alte")
    assert not r._looks_like_doc_id(
        "A Completely Different Human Title", "some-unrelated-doc-id-2020")


# ---------------------------------------------------------------------------
# Plan logic (LLM + item source mocked)
# ---------------------------------------------------------------------------

def _install_mocks(r, monkeypatch, *, item, rec, raw_exists=True):
    """Point the repair module's dependencies at fakes: the Tier-O item source,
    the identifier, and the raw.md existence."""
    import my_app.services.knowledge_library as kl
    import my_app.services.knowledge_processing as kp

    monkeypatch.setattr(kl, "get_operator_item", lambda doc_id: item, raising=False)
    monkeypatch.setattr(kp, "identify_bibliographic",
                        lambda raw_md, hinweis="", doc_id="", llm=None: rec, raising=False)

    class _P:
        def __init__(self, ok):
            self._ok = ok
        def exists(self):
            return self._ok
        def read_text(self, encoding="utf-8"):
            return "## raw title page\n\nbody"
    monkeypatch.setattr(r, "_raw_md_path", lambda doc_id: _P(raw_exists), raising=False)


def _rec(**over):
    from my_app.services.knowledge_processing import BiblioRecord
    return BiblioRecord(**over)


def test_plan_replaces_known_bad_title_even_low_confidence(monkeypatch):
    r = _load_repair()
    item = {"titel": "Ernst wAgnEr", "autor": "", "jahr": "", "quelle": "",
            "hinweis": "IJRCAAE 2023 …"}
    rec = _rec(titel="Education for Sustainable Development",
               autoren=["Ernst Wagner"], jahr=2023, quelle="IJRCAAE",
               confidence="low")   # even LOW confidence: the existing title is known-bad
    _install_mocks(r, monkeypatch, item=item, rec=rec)
    plan = r._plan_document("art105413")
    assert plan.action == "would-update"
    assert plan.changes["titel"] == "Education for Sustainable Development"
    assert plan.changes["autor"] == "Ernst Wagner"
    assert plan.changes["jahr"] == 2023
    assert plan.changes["quelle"] == "IJRCAAE"


def test_plan_keeps_plausible_title_on_low_confidence(monkeypatch):
    r = _load_repair()
    good = "Stable Diffusion Exposed: Gender Bias from Prompt to Image"
    item = {"titel": good, "autor": "", "jahr": "", "quelle": "", "hinweis": ""}
    # A low-confidence identifier offering a DIFFERENT title must NOT overwrite a
    # plausible existing title — but it may still fill the blank autor.
    rec = _rec(titel="Some Other Guessed Title", autoren=["A. Wu"],
               jahr=None, quelle=None, confidence="low")
    _install_mocks(r, monkeypatch, item=item, rec=rec)
    plan = r._plan_document("wu-et-al-2023-stable-diffusion-exposed-gender-bias-from-prompt")
    assert "titel" not in plan.changes           # kept: plausible + low confidence
    assert plan.changes.get("autor") == "A. Wu"  # blank autor still filled
    assert plan.action == "would-update"


def test_plan_overwrites_plausible_title_on_high_confidence(monkeypatch):
    r = _load_repair()
    item = {"titel": "Systematic Prejudices", "autor": "", "jahr": "",
            "quelle": "", "hinweis": ""}
    rec = _rec(titel="Challenging systematic prejudices",
               untertitel="an investigation into gender bias in text-to-image models",
               autoren=["UNESCO", "IRCAI"], jahr=2024, confidence="high")
    _install_mocks(r, monkeypatch, item=item, rec=rec)
    plan = r._plan_document("unesco-2024-challenging-systematic-prejudices-an-investigatio")
    # high confidence -> the fuller identified title replaces the truncated one.
    assert plan.changes["titel"].startswith("Challenging systematic prejudices")
    assert plan.action == "would-update"


def test_plan_skips_when_identifier_finds_nothing(monkeypatch):
    r = _load_repair()
    good = "Digitale Sympoiesis und kulturelle Resilienz"
    item = {"titel": good, "autor": "B. Jörissen", "jahr": "2022",
            "quelle": "", "hinweis": ""}
    rec = _rec(titel=None, autoren=[], jahr=None, quelle=None, confidence="low")
    _install_mocks(r, monkeypatch, item=item, rec=rec)
    plan = r._plan_document("jorissen-2022-digitale-sympoiesis-und-kulturelle-resilienz-alte")
    assert plan.action == "skipped"
    assert not plan.changes


def test_plan_does_not_overwrite_supplied_author(monkeypatch):
    r = _load_repair()
    item = {"titel": "Decolonizing Arts Education. Skizze",
            "autor": "Carmen Mörsch", "jahr": "2021", "quelle": "", "hinweis": ""}
    # Identifier offers a different author, but the operator-provided autor must win.
    rec = _rec(titel="Decolonizing Arts Education. Skizze",
               autoren=["Someone Else"], jahr=2021, confidence="high")
    _install_mocks(r, monkeypatch, item=item, rec=rec)
    plan = r._plan_document("morsch-2021-decolonizing-arts-education-skizze-zu-einer-diskr")
    assert "autor" not in plan.changes           # supplied author untouched
    assert "titel" not in plan.changes           # identical title -> no change
    assert "jahr" not in plan.changes            # already 2021


def test_plan_reports_missing_raw(monkeypatch):
    r = _load_repair()
    item = {"titel": "X", "autor": "", "jahr": "", "quelle": "", "hinweis": ""}
    _install_mocks(r, monkeypatch, item=item, rec=_rec(), raw_exists=False)
    plan = r._plan_document("some-doc")
    assert plan.action == "no-raw"
    assert not plan.changes


def test_plan_missing_item_is_error(monkeypatch):
    r = _load_repair()
    _install_mocks(r, monkeypatch, item=None, rec=_rec())
    plan = r._plan_document("nope")
    assert plan.action == "error"
