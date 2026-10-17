"""
Tests for the GIVEN MODES AND PAGES note — the platform pole of Resona's
context.

Why it exists: Resona mediates between the platform (her inner Other) and the
situation in the room (the outer one). The library pole was equipped — a scope
note, a duty to open sources — while the platform pole was not: nothing in her
context said which modes and pages exist, so she had to already know a mode was
there in order to look it up, and a question about where something could be
tried came back as a description of the idea instead of a place.

What is enforced here (the enforcement, never the wording of a draft):
  - every registered mode reaches the rendered note with its route,
  - every route in the registry exists in the frontend router,
  - every research doc_id resolves to a committed condensation, so a handle
    offered to read_knowledge is never dead,
  - the areas marked research_based actually carry research,
  - the note reaches the composed Resona system prompt,
  - the note is derived from the registry, not authored in the prompt: what the
    registry says is what the prompt gets.

Run: python3 -m pytest devserver/tests/test_resona_platform_modules.py -q
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.routes.chat_routes import (
    _MODULES_PATH,
    _RESEARCH_DIR,
    _build_resona_modules_context,
    build_system_prompt,
)

from file_modules import REPO

ROUTER = REPO / "public/ai4artsed-frontend/src/router/index.ts"


@pytest.fixture(scope="module")
def registry():
    return json.loads(_MODULES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def note():
    return _build_resona_modules_context()


def test_registry_is_not_empty(registry):
    assert len(registry["modules"]) >= 10, "the platform has more modes than this"


def test_every_mode_reaches_the_note_with_its_route(registry, note):
    for m in registry["modules"]:
        assert m["name"] in note, f"{m['id']}: name missing from the note"
        assert m["route"] in note, f"{m['id']}: route missing from the note"


def _matcher(path: str) -> re.Pattern:
    """One declared router path as a pattern a concrete address matches.

    A literal comparison stopped working the day a page took a parameter: the
    Latent Lab declares `/latent-lab/:instrument?`, and every address the note
    offers for it — `/latent-lab`, `/latent-lab/intro` — is a concrete instance
    of that path, never the string itself. `:name?` swallows its segment and
    the slash before it; `:name` requires one.
    """
    out = ""
    for seg in path.split("/")[1:]:
        if seg.startswith(":"):
            out += "(?:/[^/]+)?" if seg.endswith("?") else "/[^/]+"
        else:
            out += "/" + re.escape(seg)
    return re.compile("^" + (out or "/") + "$")


def test_every_route_exists_in_the_frontend_router(registry):
    """A route offered to a group has to lead somewhere."""
    router = ROUTER.read_text(encoding="utf-8")
    matchers = [
        _matcher(path)
        for path in set(re.findall(r"path:\s*'([^']+)'", router))
        if path.startswith("/")
    ]
    for m in registry["modules"]:
        assert any(p.match(m["route"]) for p in matchers), (
            f"{m['id']}: {m['route']} is not a route in the frontend router"
        )

def test_every_research_doc_id_resolves(registry):
    """A doc_id in the note is a handle for read_knowledge; a dead one sends
    her looking for a source that is not there."""
    known = {f.stem for f in _RESEARCH_DIR.glob("*.md")}
    assert known, "no research condensations found at all"
    for m in registry["modules"]:
        for label, ids in (m.get("research") or {}).items():
            for doc_id in ids:
                assert doc_id in known, f"{m['id']} / {label}: unknown doc_id {doc_id}"


def test_research_based_modes_carry_research(registry, note):
    marked = [m for m in registry["modules"] if m.get("research_based")]
    assert marked, "the research-built areas are the point of this note"
    for m in marked:
        ids = [i for g in (m.get("research") or {}).values() for i in g]
        assert ids, f"{m['id']} is marked research_based but names no study"
        assert m.get("research_note"), f"{m['id']} names studies but not why"
        for doc_id in ids:
            assert doc_id in note, f"{m['id']}: {doc_id} never reaches the note"


def test_note_reaches_the_resona_system_prompt():
    prompt = build_system_prompt(
        context={"resona_mode": True, "resona_situation": "workshop"},
        language="de",
    )
    assert "GIVEN MODES AND PAGES" in prompt
    assert "/latent-lab" in prompt and "/compare" in prompt


def test_note_follows_the_registry(monkeypatch):
    """The prompt must not carry a second, hand-written copy of the inventory:
    what the registry says is what she is told."""
    import my_app.routes.chat_routes as cr

    monkeypatch.setattr(cr, "_MODULES_CACHE", None)
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT

    registry = json.loads(_MODULES_PATH.read_text(encoding="utf-8"))
    for m in registry["modules"]:
        if len(m["route"]) < 3:  # "/" alone matches any URL in the prompt
            continue
        assert m["route"] not in RESONA_CORE_PROMPT, (
            f"{m['id']}: the route is written into the prompt as well — "
            "the inventory lives in platform_modules.json, one place only"
        )
