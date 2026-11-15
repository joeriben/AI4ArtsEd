"""Every use report (V 1.0) reaches Help and the lookup tools.

The reports live in docs/use_reports/v1.0/ and are built into
devserver/my_app/knowledge/use_reports.json by
devserver/scripts/build_use_reports.py. They reach Help by two roads: a page
with a catalogue item in platform_items.json is joined by its route, and the
pages without one (Flow, Together, Contesting, Canvas, the Overview of the
Latent Lab) stand in the record's `places` and are joined by the view they
send or, for the overview, by the route; the Model Comparison of the
Transformers Lab and the Tokenizer have had a catalogue item since 3c30e8d1
and go the first road. lookup_place, lookup_scenarios and read_scenario
read the same record.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from file_modules import REPO

USE_REPORTS = REPO / "devserver/my_app/knowledge/use_reports.json"

# What the frontend really sends for the pages without a catalogue item
# (usePageContext.formatPageContextForLLM): the view name when the page sets a
# context, the route when it sets none. The modes write their Vue stem; the
# overview writes nothing and keeps the address it was opened under,
# /latent-lab/intro included. The Model Comparison of the Transformers Lab
# (view system_prompt_across_models) and the Tokenizer (latent_text_lab.tokens,
# a tab the lab names) have a catalogue item since 3c30e8d1 and stand in
# ITEM_FOR_VIEW, see test_the_two_pages_with_new_catalogue_text_reach_help.
SENT = {
    "/x2x-flow": "[AKTUELLER KONTEXT]\nAktive Ansicht: x2x_flow",
    "/together": "[AKTUELLER KONTEXT]\nAktive Ansicht: resona",
    "/contesting": "[AKTUELLER KONTEXT]\nAktive Ansicht: ai_persona",
    "/canvas": "[AKTUELLER KONTEXT]\nAktive Ansicht: canvas_workflow",
    "/latent-lab/overview": "[Kontext: Aktive Seite = /latent-lab/overview]",
}
KEPT_ADDRESS = "[Kontext: Aktive Seite = /latent-lab/intro]"
# The line format_mapping_entry() renders once per (a) or (b) entry.
ENTRY = "Learner Expectation (p."


def _record() -> dict:
    return json.loads(USE_REPORTS.read_text(encoding="utf-8"))


def _entries(rec: dict) -> int:
    return len(rec["mapping"]["a"]) + len(rec["mapping"]["b"])


def test_record_loads_with_version_and_33_instruments():
    from my_app.services import platform_items as pi
    data = _record()
    assert data["version"] == "1.0"
    assert len(data["instruments"]) == 33
    assert pi.USE_REPORTS["version"] == "1.0"
    assert len(pi.USE_REPORTS["by_route"]) == 33


def test_every_instrument_route_reaches_help():
    from my_app.services import platform_items as pi
    from my_app.routes.chat_routes import _use_report_block_for
    data = _record()
    places = {p["route"]: p for p in data["places"]}
    for rec in data["instruments"]:
        route = rec["route"]
        item = pi.item_for_route(route)
        if item:
            block = pi.use_report_block(item)
            assert pi.display_name(item) in block, f"{route}: block does not name {pi.display_name(item)}"
            assert block.count(ENTRY) == _entries(rec), \
                f"{route}: {block.count(ENTRY)} of {_entries(rec)} mapping entries"
        else:
            assert route in places, f"{route}: neither a catalogue item nor a place"
            assert route in SENT, f"{route}: this test does not know what its page sends"
            block = _use_report_block_for(SENT[route])
            assert rec["name"] in block, f"{route}: {SENT[route]!r} does not reach the report"
            assert block.count(ENTRY) == _entries(rec)
    overview = next(r for r in data["instruments"] if r["route"] == "/latent-lab/overview")
    assert _use_report_block_for(KEPT_ADDRESS).count(ENTRY) == _entries(overview)
    assert overview["name"] in _use_report_block_for(KEPT_ADDRESS)


def test_empty_or_unknown_context_yields_nothing():
    from my_app.routes.chat_routes import _use_report_block_for
    assert _use_report_block_for("") == ""
    assert _use_report_block_for("nothing here") == ""
    assert _use_report_block_for("[AKTUELLER KONTEXT]\nAktive Ansicht: no_such_view") == ""
    assert _use_report_block_for("[Kontext: Aktive Seite = /no/such/page]") == ""


def test_place_views_are_not_catalogue_views():
    # A view name in both maps would be served twice; the catalogue wins and
    # the place's copy would be dead.
    from my_app.routes.chat_routes import ITEM_FOR_VIEW
    for place in _record()["places"]:
        for view in place["views"]:
            assert view not in ITEM_FOR_VIEW, f"{place['route']}: view {view} is also a catalogue view"


def test_the_two_pages_with_new_catalogue_text_reach_help():
    """Since 3c30e8d1 the Model Comparison of the Transformers Lab and the
    Tokenizer have a catalogue item. Help on those pages gets the item's own
    text through ITEM_FOR_VIEW and the use report by the item's route; until
    2026-11-08 both views had no row, so Help got the report alone and the
    record's build refused the two routes."""
    from my_app.routes.chat_routes import _item_block_for, _use_report_block_for
    for view, route, shown in (
            ("system_prompt_across_models", "/latent-lab/system-prompt-across-models", "Model Comparison"),
            ("latent_text_lab.tokens", "/latent-lab/tokenization", "Tokenizer")):
        ctx = f"[AKTUELLER KONTEXT]\nAktive Ansicht: {view}"
        own = _item_block_for(ctx)
        assert f"Route: {route}" in own, (view, own[:200])
        report = _use_report_block_for(ctx)
        assert f"Use report V 1.0 for {shown} ({route})" in report, (view, report[:200])
    assert all(p["route"] not in ("/latent-lab/system-prompt-across-models", "/latent-lab/tokenization")
               for p in _record()["places"])


def test_lookup_place_returns_the_report():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    data = _record()
    by_name = {r["name"]: r for r in data["instruments"]}
    # The header names a page the catalogue holds as its surface labels it
    # (platform_items.display_name, 516f9e7d) and a page without a catalogue
    # item by the report's name. The labels stand here as literals, so a
    # display_name that fell back to the id would be caught.
    shown_as = {"Flow": "Flow", "Composable Diffusion": "Composable Diffusion",
                "Overview": "Overview",
                "Model Comparison (Transformers Lab)": "Model Comparison"}
    for name, shown in shown_as.items():
        text = registry.execute("lookup_place", {"place": name})
        rec = by_name[name]
        assert f"Use report V 1.0 for {shown} ({rec['route']})" in text, (name, text[:200])
        assert text.count(ENTRY) == _entries(rec), name
    flow = registry.execute("lookup_place", {"place": "Flow"})
    assert flow.startswith("Flow\n\nRoute: /x2x-flow\n\nThis part has no catalogue text of its own.")
    miss = registry.execute("lookup_place", {"place": "a place that is not here"})
    assert "not in this catalogue" in miss
    for name in ("Flow", "Together", "Tokenizer"):
        assert name in miss, f"{name} missing from the miss text"


def test_lookup_scenarios():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    by_comp = registry.execute("lookup_scenarios", {"competence": "Create 2 Basic"})
    assert re.search(r"^22/S1 — Weight by hand, weight by number", by_comp, re.M), by_comp[:400]
    short = registry.execute("lookup_scenarios", {"duration": "45 min", "limit": 200})
    hits = [ln for ln in short.splitlines() if re.match(r"^\d\d/S\d+ — ", ln)]
    assert hits
    for ln in hits:
        setting = ln.split(" · ")[0]
        assert "45 min" in setting, ln
    overview = registry.execute("lookup_scenarios", {})
    assert "22 Composable Diffusion (/latent-lab/composable-diffusion): 6 scenarios" in overview
    assert len([ln for ln in overview.splitlines() if ln.endswith(" scenarios")]) == 33
    miss = registry.execute("lookup_scenarios", {"query": "zzz-no-such-scenario"})
    assert miss.startswith("No teaching scenario"), miss
    assert "query='zzz-no-such-scenario'" in miss


def test_lookup_scenarios_says_what_the_platform_does_not_hold():
    """A competence no mapping entry reaches is answered with the record's
    `unreached` text per level (the rows without a part of
    docs/ailit/unterstuetzung.tsv), and without the pointer to further
    calls, so the model has the whole answer in one round."""
    from my_app.services.tool_registry import (SCENARIO_NULL_COMPLETE, SCENARIO_NULL_PREFIX,
                                               get_tool_registry)
    from my_app.services import platform_items as pi
    registry = get_tool_registry()
    data = _record()
    unreached = data["unreached"]
    assert pi.USE_REPORTS["unreached"] == unreached
    mapped = {e["competence"] for r in data["instruments"] for cat in ("a", "b")
              for e in r["mapping"][cat]}
    unmapped = [c["code"] for c in data["competences"] if c["code"] not in mapped]
    assert "Engage 4" in unmapped, unmapped
    # Every competence without a mapped scenario has a text for each level.
    for code in unmapped:
        for lv in data["levels"]:
            assert f"{code}|{lv}" in unreached, (code, lv)
    text = registry.execute("lookup_scenarios", {"competence": "Engage 4"})
    assert text.startswith(SCENARIO_NULL_PREFIX) and SCENARIO_NULL_COMPLETE in text
    assert "is mapped to Engage 4." in text
    for lv in data["levels"]:
        assert f"- Engage 4 {lv}: {unreached[f'Engage 4|{lv}']}" in text
    assert "kein Empfehlungssystem" in text
    assert "without a filter" not in text
    one = registry.execute("lookup_scenarios", {"competence": "Engage 4 Advanced"})
    assert f"- Engage 4 Advanced: {unreached['Engage 4|Advanced']}" in one
    assert "- Engage 4 Basic:" not in one
    assert "- Engage 4 Intermediate:" not in one
    # A level no scenario is mapped to and no row of the record reaches: the
    # answer is complete too, with the levels at which the competence is mapped.
    mapped_cells = {(e["competence"], e["level"]) for r in data["instruments"]
                    for cat in ("a", "b") for e in r["mapping"][cat] if e["scenarios"]}
    gaps = [(c["code"], lv) for c in data["competences"] for lv in data["levels"]
            if (c["code"], lv) not in mapped_cells and f"{c['code']}|{lv}" not in unreached
            and any((c["code"], o) in mapped_cells for o in data["levels"])]
    assert gaps
    code, lv = gaps[0]
    gap = registry.execute("lookup_scenarios", {"competence": f"{code} {lv}"})
    assert gap.startswith(SCENARIO_NULL_PREFIX) and SCENARIO_NULL_COMPLETE in gap
    assert f"is mapped to {code} {lv}." in gap
    assert "gives no reason" in gap
    assert "Mapped at the other levels:" in gap
    assert "without a filter" not in gap
    assert gap.rstrip().endswith("Nothing further is to be looked up for this question.")
    # The reports are the source: no row of `unreached` is a cell a scenario is
    # mapped to.
    assert not {tuple(k.split("|")) for k in unreached} & mapped_cells
    # A free-text miss keeps the pointer to the list of instruments and claims
    # no finality.
    miss = registry.execute("lookup_scenarios", {"query": "zzz"})
    assert miss.startswith(SCENARIO_NULL_PREFIX)
    assert SCENARIO_NULL_COMPLETE not in miss
    assert "nothing matches this filter" in miss
    both = registry.execute("lookup_scenarios", {"competence": "Engage 4", "instrument": "flow"})
    assert both.startswith(SCENARIO_NULL_PREFIX) and SCENARIO_NULL_COMPLETE not in both
    assert "none matches these filters together" in both


def test_the_together_prompt_takes_the_null_answer_as_complete():
    """The paragraph on places, scenarios and measures stands in the Help
    prompts only; Together's prompt is the Resona core, so its tool list
    carries the same rule for lookup_scenarios."""
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT
    # Whitespace-normalised: the prompt is hard-wrapped.
    P = " ".join(RESONA_CORE_PROMPT.split())
    assert "lookup_scenarios(" in P
    assert "no other tool is tried for the same question" in P
    assert "without naming the framework or its publishers" in P


def test_read_scenario():
    from my_app.services import platform_items as pi
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    data = _record()
    rec = next(r for r in data["instruments"] if r["number"] == "22")
    text = registry.execute("read_scenario", {"id": "22/S1"})
    assert "Weight by hand, weight by number" in text
    assert "Sequence: 20 min paper composition" in text
    cell = "Create 2 Basic"
    exp = data["expectations"]["Create 2|Basic"]
    cls = data["classroom"]["Create 2|Basic"]
    assert f"(a) 100 % hit: {cell} — Learner Expectation (p. " in text
    assert f'"{exp}"' in text and f'"{cls}"' in text
    assert rec["mapping"]["beyond"] in text
    assert pi.NO_THRESHOLD in text
    for variant in ("22 S1", "22-S1", "22/s1"):
        assert registry.execute("read_scenario", {"id": variant}) == text, variant
    missing = registry.execute("read_scenario", {"id": "22/S9"})
    for s in rec["scenarios"]:
        assert f"22/{s['id']}" in missing
    nobody = registry.execute("read_scenario", {"id": "99/S1"})
    assert "Composable Diffusion" in nobody and "Flow" in nobody


def test_new_tools_in_both_scopes():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    universal = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    resona = {t["function"]["name"] for t in registry.get_openai_format(scope="resona")}
    for name in ("lookup_place", "lookup_scenarios", "read_scenario"):
        assert name in universal and name in resona, name


def _instrument(number: str) -> dict:
    return next(r for r in _record()["instruments"] if r["number"] == number)


def test_mapping_lines_parse_one_per_bullet():
    rec = _instrument("03")
    create1 = {e["level"]: e for e in rec["mapping"]["a"] if e["competence"] == "Create 1"}
    assert create1["Basic"]["text"] == "" and create1["Basic"]["scenarios"] == []
    assert create1["Intermediate"]["scenarios"] == ["S2"]
    assert sum(len(r["mapping"]["a"]) for r in _record()["instruments"]) == 168


def test_subject_link_after_a_closing_quote():
    s2 = next(s for s in _instrument("31")["scenarios"] if s["id"] == "S2")
    assert s2["subject_link"] == "speech recognition, language identification, confidence."
    assert s2["text"].endswith('"')


def test_canvas_block_carries_the_section_7_note():
    from my_app.services import platform_items as pi
    block = pi.use_report_block(pi.place_for_route("/canvas"))
    assert "Not tried: the loop" in block


def test_lookup_place_by_number_and_german_name():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    look = lambda q: registry.execute("lookup_place", {"place": q})  # noqa: E731
    assert look("1").startswith("Flow\n\nRoute: /x2x-flow")
    assert look("2").startswith("Together\n\nRoute: /together")
    assert "Use report V 1.0 for Composable Diffusion" in look("22")
    # By a name that ends in a digit (the catalogue's handle since 3c30e8d1),
    # read as a name and not as a report number; and by route.
    assert "Use report V 1.0 for Bias Research 1 (/latent-lab/bias-archaeology)" in look("Bias Research 1")
    assert "Use report V 1.0 for Bias Research 1 (/latent-lab/bias-archaeology)" in look("/latent-lab/bias-archaeology")
    assert "Use report V 1.0 for Voice Comparison (/latent-lab/voices)" in look("Stimmen-Vergleich")
    assert "Use report V 1.0 for Overview (/latent-lab/overview)" in look("Überblick")
    assert "Use report V 1.0 for Interception Scope" in look("Wirkungsvergleich")


def test_lookup_scenarios_arguments():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    run = lambda a: registry.execute("lookup_scenarios", a)  # noqa: E731
    unknown = run({"competence": "Engage 9"})
    assert unknown == ("'Engage 9' is not a competence of the framework; the competences are "
                       "Engage 1–7, Create 1–4, Manage 1–4, Shape 1–4, optionally with a level "
                       "Basic / Intermediate / Advanced.")
    assert run({"competence": ["Engage 2"]}) == "competence must be a text, not a list."
    assert run({"instrument": 22}) == run({"instrument": "22"})
    assert run({"instrument": 22}).startswith("22/S1 — ")
    nonformal = run({"form": "non-formal", "limit": 500})
    assert nonformal.startswith(("0", "1", "2", "3"))
    for variant in ("nonformal", "non formal", "Non-Formal"):
        assert run({"form": variant, "limit": 500}) == nonformal, variant
    assert run({"form": "formal", "limit": 500}) != nonformal


def test_multi_line_context_reaches_the_flow_report():
    from my_app.routes.chat_routes import _use_report_block_for
    block = _use_report_block_for("[AKTUELLER KONTEXT]\nAktive Ansicht: x2x_flow\nSchritt: 2\nPrompt: ein Haus")
    assert "Use report V 1.0 for Flow (/x2x-flow)" in block


def test_every_block_carries_sections_1_to_3_and_not_4():
    """Since 2026-11-14 a page's use report is what Help and Together know of
    what the page is and does: sections 1 to 3 (what was done on it, what its
    controls did, what came out) reach the agents with 5 to 9, under the
    report's own titles. Section 4 and the session line record the
    circumstances of the run and stay out."""
    from my_app.services import platform_items as pi
    for rec in _record()["instruments"]:
        route = rec["route"]
        numbers = [s["number"] for s in rec["sections"]]
        assert numbers == [1, 2, 3, 5, 6, 7, 8, 9], f"{route}: sections {numbers}"
        item = pi.item_for_route(route) or pi.place_for_route(route)
        assert item, f"{route}: neither a catalogue item nor a place"
        block = pi.use_report_block(item)
        for s in rec["sections"][:3]:
            assert f"{s['title']} (section {s['number']}):\n{s['text']}" in block, \
                f"{route}: section {s['number']} does not reach the block"
        assert "(section 4)" not in block, f"{route}: section 4 in the block"


# A view that keeps its handbook entry although Help joins it to a report:
# the page is its own, the report is of another one.
OWN_PAGE_WITHOUT_REPORT = {
    # /surrealizer-flow, a form of Encoder Fusion drawn as a flow. ITEM_FOR_VIEW
    # joins it to the Encoder Fusion item, whose report was written on
    # /latent-lab/encoder-fusion, a different surface (2026-11-14).
    "surrealizer_flow",
}


def _redirects() -> dict:
    """Old address -> the address the router sends it to, chains followed
    (/silly-parrot -> /cover-band -> /latent-lab/re-enactment)."""
    text = (REPO / "public/ai4artsed-frontend/src/router/index.ts").read_text(encoding="utf-8")
    pairs = dict(re.findall(r"path:\s*'([^']+)',\s*redirect:\s*'([^']+)'", text))
    out = {}
    for start in pairs:
        target, seen = pairs[start], {start}
        while target in pairs and target not in seen:
            seen.add(target)
            target = pairs[target]
        out[start] = target
    return out


def test_no_page_with_a_use_report_keeps_a_handbook_entry():
    """A page with a use report is described by the report. Its entry in the
    handbook (trashy_interface_reference.txt) was taken out on 2026-11-14; an
    entry brought back would describe the page a second time, from the older
    text, next to the report. Checked on every entry Help can inject
    (PAGE_ENTRIES reads the whole file), by the route the entry names and
    the address that route redirects to, and by the view, the road Help
    takes. Every numbered line of SECTION 2 has to parse as an entry header,
    or an entry could slip past this test into lookup_reference."""
    from my_app.routes.chat_routes import PAGE_ENTRIES, _PAGE_HEADER, _use_report_block_for
    from my_app.services import platform_items as pi
    text = (REPO / "devserver/trashy_interface_reference.txt").read_text(encoding="utf-8")
    section = text.split("\nSECTION 2:", 1)[1].split("\nSECTION 3:", 1)[0]
    for line in section.splitlines():
        if re.match(r"\s*\d+\.", line):
            assert _PAGE_HEADER.match(line.rstrip()), f"not an entry header: {line!r}"
    assert PAGE_ENTRIES
    redirects = _redirects()
    for view, block in PAGE_ENTRIES.items():
        found = re.search(r"route\s+(\S+?)\)", block.splitlines()[0])
        assert found, f"{view}: the entry names no route"
        for route in {found.group(1), redirects.get(found.group(1))} - {None}:
            assert not pi.report_for_route(route) and not pi.place_for_route(route), \
                f"{view}: {route} has a use report and still an entry in the handbook"
        if view not in OWN_PAGE_WITHOUT_REPORT:
            context = f"[AKTUELLER KONTEXT]\nAktive Ansicht: {view}"
            assert not _use_report_block_for(context), \
                f"{view}: its page has a use report and still an entry in the handbook"


def test_every_handbook_section_has_an_id_and_every_id_a_section():
    """lookup_reference offers the sections the parser finds. An id without a
    section is offered and answers 'not found'; a section without an id
    surfaces as section_N. Sections 3b, 6 and 7 left on 2026-11-14 together
    with their ids."""
    from my_app.services.tool_registry import _SECTION_IDS, _parse_sections
    sections = _parse_sections(REPO / "devserver/trashy_interface_reference.txt")
    assert set(sections) == set(_SECTION_IDS.values())
    for gone in ("canvas_mode", "experimental_workflows", "lora_training"):
        assert gone not in sections
