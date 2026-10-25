"""Every measure of the AILit coverage file reaches Help.

The measures live in devserver/my_app/knowledge/ailit_coverage.json and reach
Help by two roads: the catalogue platform_items.json carries them for the
instruments that have an entry there, and platform_items.place_for_view /
place_for_route serve them for the pages that have none (Flow, Canvas,
Contesting, Together, the Tokenizer of the Transformers Lab by the view they
report; the Overview of the Latent Lab by the route the frontend sends).
Before 2026-09-19 the second road did not exist, and Flow, the page with the
most measures of all, reached nobody.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from file_modules import REPO

COVERAGE = REPO / "devserver/my_app/knowledge/ailit_coverage.json"

# What the frontend really sends for the pages without a catalogue entry
# (usePageContext.formatPageContextForLLM): the view name when the page sets a
# context, the route when it sets none. The four modes write their Vue stem,
# the Transformers Lab writes `latent_text_lab.<tab>` for a tab without a
# context of its own, the overview writes nothing and keeps the address it
# was opened under, /latent-lab/intro included.
SENT = {
    "/x2x-flow": "[AKTUELLER KONTEXT]\nAktive Ansicht: x2x_flow",
    "/canvas": "[AKTUELLER KONTEXT]\nAktive Ansicht: canvas_workflow",
    "/contesting": "[AKTUELLER KONTEXT]\nAktive Ansicht: ai_persona",
    "/together": "[AKTUELLER KONTEXT]\nAktive Ansicht: resona",
    "/latent-lab/tokenization": "[AKTUELLER KONTEXT]\nAktive Ansicht: latent_text_lab.tokens",
    "/latent-lab/overview": "[Kontext: Aktive Seite = /latent-lab/overview]",
}
KEPT_ADDRESS = "[Kontext: Aktive Seite = /latent-lab/intro]"
# The line goals() renders once per measure; the rubric of lookup_place names
# the scenario too, so the bare words would count one more.
MEASURE = "  In the Classroom, S. "


def _coverage() -> dict:
    return json.loads(COVERAGE.read_text(encoding="utf-8"))


def test_support_rows_and_by_route_agree():
    # Two sections of the same file, compared against each other: a route
    # that drops out of by_route while its support rows stay would otherwise
    # pass unnoticed, and the count above in build_platform_items.py is read
    # by nobody.
    data = _coverage()
    expected: dict = {}
    for row in data["support"]:
        route = row["place"]["route"]
        if route.startswith("/"):
            expected[route] = expected.get(route, 0) + 1
    got = {route: len(goals) for route, goals in data["by_route"].items()}
    assert got == expected, {r: (expected.get(r), got.get(r)) for r in set(expected) | set(got)
                             if expected.get(r) != got.get(r)}
    # The cross-cutting functions (no route) stand in by_part under their key.
    expected_parts: dict = {}
    for row in data["support"]:
        if not row["place"]["route"].startswith("/"):
            expected_parts[row["place"]["key"]] = expected_parts.get(row["place"]["key"], 0) + 1
    got_parts = {key: len(goals) for key, goals in data["by_part"].items()}
    assert got_parts == expected_parts, (expected_parts, got_parts)
    assert sum(got.values()) + sum(got_parts.values()) == len(data["support"])


def test_every_supported_route_reaches_help():
    from my_app.services import platform_items as pi
    data = _coverage()
    catalogue_routes = {item.get("route") for item in pi.ITEMS.values()}
    for route, goals in data["by_route"].items():
        assert goals, f"{route}: by_route entry without measures"
        if route in catalogue_routes:
            item = next(i for i in pi.ITEMS.values() if i.get("route") == route)
            assert len(item.get("ailit", {}).get("goals") or []) == len(goals), \
                f"{route}: the catalogue carries {len(item.get('ailit', {}).get('goals') or [])} of {len(goals)} measures"
            assert pi.goals(item).count(MEASURE) == len(goals)
        else:
            assert route in SENT, f"{route}: no catalogue item, and this test does not know what its page sends"
            place = pi.place_for_route(route)
            assert place, f"{route}: neither a catalogue item nor a place in the coverage file"
            assert pi.goals(place).count(MEASURE) == len(goals)


def test_pages_without_catalogue_entry_are_reached_by_what_they_send():
    from my_app.routes.chat_routes import ITEM_FOR_VIEW, _goals_block_for
    data = _coverage()
    for route, context in SENT.items():
        block = _goals_block_for(context)
        assert block.count(MEASURE) == len(data["by_route"][route]), \
            f"{route}: {context!r} yields {block.count(MEASURE)} measures"
        assert "Praxis-Szenario" in block
    assert _goals_block_for(KEPT_ADDRESS).count(MEASURE) == len(data["by_route"]["/latent-lab/overview"])
    assert _goals_block_for("") == ""
    assert _goals_block_for("nothing here") == ""
    # A view name in both maps would be served twice; the catalogue wins and
    # the coverage file's copy would be dead.
    for place in data["places"]:
        for view in place.get("views") or []:
            assert view not in ITEM_FOR_VIEW, f"{place['key']}: view {view} is also a catalogue view"


def test_lookup_place_answers_by_english_and_german_names():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    data = _coverage()
    flow = registry.execute("lookup_place", {"place": "Flow"})
    assert "/x2x-flow" in flow
    assert flow.count(MEASURE) == len(data["by_route"]["/x2x-flow"])
    # A German name of a catalogue page reaches the catalogue item, with the
    # page's own text before the measures.
    voice = registry.execute("lookup_place", {"place": "Stimmen-Vergleich"})
    assert "no catalogue text" not in voice, voice[:200]
    assert voice.count(MEASURE) == len(data["by_route"]["/latent-lab/voices"])
    overview = registry.execute("lookup_place", {"place": "Überblick"})
    assert overview.startswith("Overview (Überblick)"), overview[:80]
    assert "handbook" not in overview
    miss = registry.execute("lookup_place", {"place": "a place that is not here"})
    assert "not in this catalogue" in miss
    # The miss text names Flow among what can be asked for; the list under
    # it has to carry it, and the pages and functions without catalogue text.
    for name in ("Flow", "Canvas", "Contesting", "Together", "Overview", "Tokenizer", "AI marking"):
        assert name in miss, f"{name} missing from the miss text"
    empty = registry.execute("lookup_place", {"place": ""})
    assert "Flow" in empty and "AI marking" in empty


def test_lookup_place_answers_a_function_by_name():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    data = _coverage()
    marking = registry.execute("lookup_place", {"place": "KI-Kennzeichnung"})
    assert marking.startswith("AI marking (KI-Kennzeichnung)"), marking[:80]
    assert "no route of its own" in marking
    assert marking.count(MEASURE) == len(data["by_part"]["fn_marking"])
