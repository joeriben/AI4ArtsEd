"""Platform items — what the labs and Compare say about their own technology.

platform_items.json is that wording, moved out of the i18n catalogue unchanged
(built by scripts/build_platform_items.py) so it survives the pages being
emptied. This module is the one place that reads it: chat_routes injects the
item for the page somebody stands on, and the lookup_place tool answers for any
of them.

The id carries the nesting (latent_lab.image.composable), because 21 of the 24
items are tabs with no route of their own.

An item carries `name`, the handle it is found by, and `names`, the label the
page shows in every language the frontend ships. What a model is handed names
an item by display_name(): the label in the conversation language, with the
English label in brackets where the two differ, so the model names a page the
way the visitor's screen does.

Since 2026-11-06 the module also reads use_reports.json, the versioned use
reports (docs/use_reports/v<version>/, built by scripts/build_use_reports.py): one
report per instrument, written in the first person, with what was done on the
page, what its controls did and what came out (since 2026-11-14), where a
newcomer stumbles, what a user needs to know, use possibilities, teaching
scenarios and
the mapping of those scenarios to the AI literacy framework of OECD / European
Union 2026 (CC BY 4.0), with the framework's wording and pages. A report is
joined to a page by route. use_report_block() renders it; render() does not,
because the page's own text and a use report are different kinds of
statement. The pages without a catalogue item (Flow, Together, Contesting,
Canvas and the Overview of the Latent Lab) stand in the record's `places`, with the
view names their pages send, and are reached through place_for_view(),
place_for_route() and find_place(). The tools lookup_scenarios and
read_scenario read USE_REPORTS directly. Until 2026-11-06 this place was held
by ailit_coverage.json, built from docs/ailit/unterstuetzung.tsv, which
remains in the repository as a record. Its rows without a part reach the
agents again as the record's `unreached`: the measures that reading found no
part for and no scenario of the reports reaches, with the reason, which
lookup_scenarios gives where a competence has no mapped scenario (2026-11-08).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ITEMS_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "platform_items.json"

# Order matters: it is the order a reader needs them in.
FIELDS = (
    ("brief", "Kurz"),
    ("what", "Was"),
    ("how", "Wie"),
    ("technical", "Technisch"),
    ("limits", "Grenze, die der Ort selbst nennt"),
    ("hints", "Was an den Bedienelementen steht"),
    ("reading", "Zum Nachlesen"),
)


def _load() -> Dict[str, dict]:
    try:
        if not ITEMS_PATH.exists():
            logger.warning("Platform items not found: %s", ITEMS_PATH)
            return {}
        with open(ITEMS_PATH, "r", encoding="utf-8") as f:
            items = {it["id"]: it for it in json.load(f).get("items", [])}
        logger.info("Loaded %d platform items", len(items))
        return items
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load platform items: %s", e)
        return {}


ITEMS: Dict[str, dict] = _load()

# The use reports, structured and versioned (built by
# scripts/build_use_reports.py from docs/use_reports/v<version>/). Joined to a
# page by route.
USE_REPORTS_PATH = ITEMS_PATH.parent / "use_reports.json"


def _load_use_reports() -> dict:
    """The record, keyed for the callers: `by_route` (route -> instrument
    record, in report order), `places` (the routes without a catalogue item,
    with the view names and earlier addresses their pages send), and the
    framework wording with its pages; `unreached` (competence|level -> the
    German text for the measures no part of the platform carries). A missing
    or malformed file logs an error and yields {}: Help then carries no report
    block, nothing fails."""
    try:
        with open(USE_REPORTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        instruments = [r for r in data.get("instruments") or []
                       if isinstance(r, dict) and isinstance(r.get("route"), str) and r["route"]]
        by_route = {r["route"]: r for r in sorted(instruments, key=lambda r: str(r.get("number") or ""))}
        places = [p for p in data.get("places") or []
                  if isinstance(p, dict) and isinstance(p.get("route"), str) and p["route"]]
        if not data.get("version"):
            logger.warning("The use reports %s carry no version", USE_REPORTS_PATH)
        out = {
            "version": str(data.get("version") or ""),
            "source": dict(data.get("source") or {}),
            "levels": [x for x in data.get("levels") or [] if isinstance(x, str)],
            "competences": [c.get("code") for c in data.get("competences") or []
                            if isinstance(c, dict) and isinstance(c.get("code"), str)],
            "by_route": by_route,
            "places": places,
            "expectations": dict(data.get("expectations") or {}),
            "classroom": dict(data.get("classroom") or {}),
            "expectation_pages": dict(data.get("expectation_pages") or {}),
            "classroom_pages": dict(data.get("classroom_pages") or {}),
            "unreached": (dict(data["unreached"])
                          if isinstance(data.get("unreached"), dict) else {}),
        }
        n_scen = sum(len(r.get("scenarios") or []) for r in by_route.values())
        logger.info("Loaded use reports V %s: %d instruments from %s, %d scenarios, %d places without catalogue item",
                    out["version"] or "unknown", len(by_route), out["source"].get("folder") or "an unnamed folder",
                    n_scen, len(places))
        return out
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load the use reports %s: %s", USE_REPORTS_PATH, e)
        return {}


USE_REPORTS: dict = _load_use_reports()

NO_THRESHOLD = "The framework sets no threshold at which a competence counts as covered."


def get(item_id: str) -> Optional[dict]:
    return ITEMS.get(item_id)


def display_name(item: dict, language: Optional[str] = None) -> str:
    """The item's label in `language` as the page shows it, followed by the
    English label in brackets where the two differ ("Stereotypen-Analyse
    (Stereotype Analysis)"). The English label alone when the language is
    English, not given, or not one the frontend ships, which is what the
    frontend itself shows then; `name` for an item without `names`."""
    names = item.get("names") or {}
    english = names.get("en") or item.get("name") or item.get("id") or ""
    local = names.get(language or "en") or english
    return local if local == english else f"{local} ({english})"


def _names_of(item: dict) -> List[str]:
    """Every name an item can be asked for by: its handle and its label in
    each shipped language."""
    return [n.lower() for n in [item.get("name") or "", *(item.get("names") or {}).values()] if n]


def find(query: str) -> Optional[dict]:
    """The item a person means, by id or by name.

    Exact id first, then an exact name (the handle or the label in any
    shipped language, since a model in a German conversation says
    "Stereotypen-Analyse"), then a handle or id that contains the query, and
    only when none does, a label that contains it — the model will say
    "Encoder Fusion" far more often than "latent_lab.image.fusion". The
    handles go before the labels so that a one-word English query
    ("Language") keeps finding the page it found when only handles were
    searched.
    """
    q = (query or "").strip().lower()
    if not q:
        return None
    for item in ITEMS.values():
        if item["id"].lower() == q:
            return item
    for item in ITEMS.values():
        if q in _names_of(item):
            return item
    hits = [it for it in ITEMS.values()
            if q in (it.get("name") or "").lower() or q in it["id"].lower()]
    if not hits:
        hits = [it for it in ITEMS.values() if any(q in n for n in _names_of(it))]
    return hits[0] if len(hits) == 1 else None


def report_for_route(route: str) -> Optional[dict]:
    """The use report of the page at `route`, or None."""
    if not route:
        return None
    rec = (USE_REPORTS.get("by_route") or {}).get(route)
    return rec if isinstance(rec, dict) else None


def _place_item(place: dict) -> Optional[dict]:
    """A page of the use reports in the shape use_report_block() renders,
    or None when no report stands for its route."""
    route = place.get("route") or ""
    rec = report_for_route(route)
    if not rec:
        return None
    return {
        "id": "place:" + route,
        "name": rec.get("name") or place.get("name") or route,
        "route": route,
        "report": rec,
    }


def place_for_view(stem: str) -> Optional[dict]:
    """The page without catalogue item whose view sends `stem`, with its report."""
    for place in USE_REPORTS.get("places") or []:
        if stem and stem in (place.get("views") or []):
            return _place_item(place)
    return None


def place_for_route(route: str) -> Optional[dict]:
    """The page without catalogue item at `route`, with its report. An
    earlier address a page still answers under (the overview as
    /latent-lab/intro) counts as its route; the record lists them as
    `aliases`."""
    for place in USE_REPORTS.get("places") or []:
        if route and (place.get("route") == route or route in (place.get("aliases") or [])):
            return _place_item(place)
    return None


def item_for_route(route: str) -> Optional[dict]:
    """The catalogue item at `route`, or None. A page of the use reports
    found by find_place() may be one the catalogue holds; the item is the
    answer then, with the page's own text before the report."""
    if not route:
        return None
    for item in ITEMS.values():
        if item.get("route") == route:
            return item
    return None


def place_menu() -> str:
    """The pages with a use report and no catalogue item, one per line, for
    the answer that lists what can be asked for. The catalogue's own menu()
    lists its items alone."""
    lines = []
    for place in USE_REPORTS.get("places") or []:
        route = place.get("route") or ""
        if item_for_route(route):
            continue
        item = _place_item(place)
        if item:
            lines.append(f"{item['name']}  [{route}]")
    return "\n".join(lines)


def find_place(query: str) -> Optional[dict]:
    """The page of the use reports a person means: by route (or an earlier
    address), by name or an alias of the record (the German page name), by
    the report's number ("22"), or by a name that contains the query when
    exactly one does. Any of the 33 reports can be
    found; the caller asks item_for_route() whether the catalogue holds the
    page and prefers that item."""
    q = (query or "").strip().lower()
    if not q:
        return None
    records = list((USE_REPORTS.get("by_route") or {}).values())
    for place in USE_REPORTS.get("places") or []:
        if q in [a.lower() for a in place.get("aliases") or []]:
            return _place_item(place)
    num = q.zfill(2) if q.isdigit() else ""
    for rec in records:
        if q == (rec.get("route") or "").lower() or q == (rec.get("name") or "").lower() \
                or (num and num == str(rec.get("number") or "")) \
                or q in [a.lower() for a in rec.get("aliases") or [] if isinstance(a, str)]:
            return _place_item(rec)
    hits = [rec for rec in records if q in (rec.get("name") or "").lower()]
    return _place_item(hits[0]) if len(hits) == 1 else None


def render(item: dict, language: Optional[str] = None) -> str:
    """One item as text: where it sits, what it is, how it works. Names in
    `language` (display_name)."""
    lines: List[str] = []
    parent = ITEMS.get(item.get("parent") or "")
    if parent:
        brief = (parent.get("technical") or {}).get("brief")
        if brief:
            lines.append(f"{display_name(parent, language)}: {brief}")
    lines.append(display_name(item, language))
    if item.get("route"):
        lines.append(f"Route: {item['route']}")
    tech = item.get("technical") or {}
    for key, label in FIELDS:
        value = tech.get(key)
        if value:
            lines.append(f"{label}: {value}")
    return "\n\n".join(x for x in lines if x)


def format_mapping_entry(entry: dict) -> str:
    """One (a) or (b) entry of a report's mapping, with the framework's
    Learner Expectation and "In the Classroom" example verbatim and their
    pages, then the report's text. "" for a malformed entry."""
    if not isinstance(entry, dict):
        return ""
    comp, level = entry.get("competence"), entry.get("level")
    if not isinstance(comp, str) or not comp or not isinstance(level, str) or not level:
        return ""
    cell = f"{comp}|{level}"
    expectation = entry.get("expectation") or (USE_REPORTS.get("expectations") or {}).get(cell)
    if not isinstance(expectation, str) or not expectation:
        return ""
    epage = (USE_REPORTS.get("expectation_pages") or {}).get(cell)
    parts = [f"{comp} {level} — Learner Expectation"
             + (f" (p. {epage})" if epage else "") + f": \"{expectation}\""]
    classroom = (USE_REPORTS.get("classroom") or {}).get(cell)
    if isinstance(classroom, str) and classroom:
        cpage = (USE_REPORTS.get("classroom_pages") or {}).get(cell)
        parts.append("In the Classroom" + (f" (p. {cpage})" if cpage else "") + f": \"{classroom}\"")
    text = entry.get("text")
    if isinstance(text, str) and text:
        parts.append(text)
    return " | ".join(parts)


def format_scenario(scen: dict) -> str:
    """One scenario of section 8 on one line: id, title, setting, text and
    its labelled tail. "" for a malformed one."""
    if not isinstance(scen, dict) or not isinstance(scen.get("id"), str):
        return ""
    head = f"{scen['id']} — {scen.get('title') or ''}".rstrip()
    if scen.get("setting"):
        head += f" ({scen['setting']})"
    out = [head + "."]
    for key, label in (("text", None), ("sequence", "Sequence"),
                       ("subject_link", "Subject link"), ("uncertainty", "Uncertainty")):
        value = scen.get(key)
        if isinstance(value, str) and value:
            out.append(f"{label}: {value}" if label else value)
    return " ".join(out)


# A scenario id as the tools take it: '22/S1', also '22 S1', '22-S1', '22/s1'.
SCENARIO_ID = re.compile(r"^\s*(\d{1,2})\s*[/\s-]\s*s?(\d+)\s*$", re.I)

# A sentence ends at a full stop, question or exclamation mark (with any
# closing quotation mark or bracket) before a capital, an opening bracket or an
# opening quotation mark; not after an abbreviation, not inside brackets and
# not inside a quotation.
_BOUNDARY = re.compile("[.!?][\"\u201d\u2019)]*\\s+(?=[A-Z(\"\u201c\u201e])")
_CLOSERS = "\"\u201d\u2019)"
_ABBREVIATIONS = {"e.g", "i.e", "etc", "cf", "vs", "ca", "approx", "fig", "no", "nr",
                  "p", "pp", "z.b", "d.h", "u.a", "bzw", "vgl", "st", "dr", "prof"}
# The list gives whole sentences up to at least this many characters, so an
# opening like "The seed stays as it is." is followed by what the group does.
OPENING_MIN = 160
# A first sentence longer than this is cut at its last semicolon, comma or
# space before it and marked with an ellipsis; read_scenario gives it whole.
OPENING_MAX = 320


def scenario_by_id(raw: Any) -> Optional[tuple]:
    """(record, scenario) for an id like '07/S1', or None.

    The id as read_scenario takes it (SCENARIO_ID). None for anything that is
    no id, a number no report carries, or a scenario the report does not hold.
    """
    m = SCENARIO_ID.match(raw) if isinstance(raw, str) else None
    if not m:
        return None
    num, sid = m.group(1).zfill(2), f"S{int(m.group(2))}"
    for rec in (USE_REPORTS.get("by_route") or {}).values():
        if str(rec.get("number")) != num:
            continue
        for scen in rec.get("scenarios") or []:
            if isinstance(scen, dict) and scen.get("id") == sid:
                return rec, scen
        return None
    return None


def _sentence_ends(text: str):
    """The positions after which a sentence of `text` ends (_BOUNDARY)."""
    for m in _BOUNDARY.finditer(text):
        end = m.start() + 1
        while end < len(text) and text[end] in _CLOSERS:
            end += 1
        head = text[:end]
        if text[m.start()] == ".":
            word = re.search(r"([\w.]+)\.$", text[:m.start() + 1])
            if word and word.group(1).lower().rstrip(".") in _ABBREVIATIONS:
                continue
            if word and len(word.group(1)) == 1 and word.group(1).isalpha():
                continue  # an initial or a single-letter list mark
        if head.count("(") > head.count(")"):
            continue
        if head.count('"') % 2 or \
                head.count("\u201c") + head.count("\u201e") > head.count("\u201d"):
            continue
        yield end


def scenario_opening(scen: dict) -> str:
    """The opening of a scenario's text in the report's wording: whole
    sentences up to at least OPENING_MIN characters, or the whole text; cut
    with an ellipsis where that runs past OPENING_MAX."""
    text = scen.get("text") if isinstance(scen, dict) else None
    if not isinstance(text, str) or not text.strip():
        return ""
    text = " ".join(text.split())
    opening = text
    for end in _sentence_ends(text):
        if end >= OPENING_MIN:
            opening = text[:end].strip()
            break
    if len(opening) <= OPENING_MAX:
        return opening
    head = opening[:OPENING_MAX]
    for mark in ("; ", ", ", " "):
        cut = head.rfind(mark)
        if cut >= OPENING_MIN:
            return head[:cut].rstrip(" ,;") + " \u2026"
    return head.rstrip() + " \u2026"


def format_scenario_listed(scen: dict, number: str) -> str:
    """One scenario of section 8 as a line of a list: id, title, setting, the
    opening of its text (scenario_opening) and its subject link. Its sequence,
    the rest of its text and its uncertainty come with read_scenario. "" for a
    malformed one."""
    if not isinstance(scen, dict) or not isinstance(scen.get("id"), str):
        return ""
    head = f"{number}/{scen['id']} — {scen.get('title') or ''}".rstrip()
    if scen.get("setting"):
        head += f" ({scen['setting']})"
    out = [head + "."]
    opening = scenario_opening(scen)
    if opening:
        out.append(opening)
    link = scen.get("subject_link")
    if isinstance(link, str) and link:
        out.append(f"Subject link: {link}")
    return " ".join(out)


def scenario_card_text(scen: dict) -> str:
    """A scenario in full for its card on the board: setting, text, sequence
    and subject link, one paragraph each, in the report's wording ("Sequence:"
    and "Subject link:" are the report's own words). The title stands on the
    front of the card. The uncertainty line stays with read_scenario: its "I"
    is the report's author, whom the card does not name, and on Together's
    board it would read as Together speaking."""
    if not isinstance(scen, dict):
        return ""
    parts = []
    for key, label in (("setting", None), ("text", None), ("sequence", "Sequence"),
                       ("subject_link", "Subject link")):
        value = scen.get(key)
        if isinstance(value, str) and value.strip():
            value = " ".join(value.split())
            parts.append(f"{label}: {value}" if label else value)
    return "\n\n".join(parts)


def use_report_block(item: dict, language: Optional[str] = None,
                     scenarios_in_full: bool = True) -> str:
    """The use report of this page, with its version, or "" when none stands for it.

    Kept apart from render(): that text is what the page says about its own
    technology, this one is a first-person use report of the page: what was
    done on it, what its controls did and what came out (sections 1 to 3;
    since 2026-11-14 the agents' description of what the page is and does,
    in place of the handbook's page entry),
    then teaching scenarios and the mapping of those
    scenarios to the AI literacy framework (OECD / European Union 2026) in
    the framework's wording. Joined by the item's route; an item built by
    _place_item() carries the report already. Malformed data is skipped, so a
    hand-edited record cannot take Help down on that page. A catalogue item is
    named in `language` (display_name); a page without one by the report's
    name.

    With scenarios_in_full=False the teaching scenarios stand as a list
    (format_scenario_listed): id, title, setting, opening, subject link. Together reads them so, because a scenario it builds on is then
    opened with read_scenario, and that lays it on the board, the one place
    the educator can read it (2026-11-15).
    """
    if not isinstance(item, dict):
        return ""
    rec = item.get("report")
    if not isinstance(rec, dict):
        rec = report_for_route(item.get("route") or "")
    if not isinstance(rec, dict):
        return ""
    version = USE_REPORTS.get("version") or "unknown"
    name = (display_name(item, language) if item.get("names")
            else rec.get("name") or item.get("name") or "")
    route = rec.get("route") or item.get("route") or ""
    out: List[str] = [
        f"Use report V {version} for {name} ({route}), written in the first person. "
        "Say what it says; never speak as its author. "
        "Its \"Uncertainty\" lines and its \"presumably\" name what was not verified. "
        "Sections 1 to 3 record how the page was used, in its English interface, "
        "when the report was written. Where they name the circumstances of that use (a "
        "stuck or restarted service, the waiting queue of that day, the browser's "
        "console, the assignment the use followed), that is not the page and stays "
        "out of the room. Where what the person sees differs from them, what the "
        "person sees counts."
    ]
    sections = {s.get("number"): s.get("text") for s in rec.get("sections") or []
                if isinstance(s, dict)}
    titles = {s.get("number"): s.get("title") for s in rec.get("sections") or []
              if isinstance(s, dict)}
    # Sections 1 to 3 under the report's own titles ("What I did", "What the
    # controls did", "What came out"): since 2026-11-14 the description of
    # what the page is and does, in place of the handbook's page entry.
    for number in (1, 2, 3):
        text, title = sections.get(number), titles.get(number)
        if isinstance(text, str) and text.strip() and isinstance(title, str) and title.strip():
            out.append(f"{title.strip()} (section {number}):\n{text.strip()}")
    for number, title in ((5, "Where a newcomer stumbles"), (6, "What a user needs to know")):
        text = sections.get(number)
        if isinstance(text, str) and text.strip():
            out.append(f"{title} (section {number}):\n{text.strip()}")
    possibilities = [p for p in rec.get("possibilities") or [] if isinstance(p, str) and p]
    note = rec.get("possibilities_note")
    note = note.strip() if isinstance(note, str) else ""
    if possibilities:
        out.append("Use possibilities (section 7):\n" + "\n".join(f"- {p}" for p in possibilities)
                   + (f"\n\n{note}" if note else ""))
    elif note:
        out.append(f"Use possibilities (section 7):\n{note}")
    number = str(rec.get("number") or "")
    if scenarios_in_full:
        scenarios = [s for s in (format_scenario(x) for x in rec.get("scenarios") or []) if s]
    else:
        scenarios = [s for s in (format_scenario_listed(x, number)
                                 for x in rec.get("scenarios") or []) if s]
    if scenarios:
        intro = rec.get("scenarios_intro")
        head = "Teaching scenarios (section 8):"
        if isinstance(intro, str) and intro.strip():
            head += " " + intro.strip()
        if not scenarios_in_full:
            head += (" Listed by title, setting, the opening of the text and subject link; "
                     f"read_scenario('{number}/S1') gives one in full and lays it "
                     "on the board as a card.")
        out.append(head + "\n" + "\n".join(scenarios))
    mapping = rec.get("mapping") if isinstance(rec.get("mapping"), dict) else {}
    a_lines = [x for x in (format_mapping_entry(e) for e in mapping.get("a") or []) if x]
    b_lines = [x for x in (format_mapping_entry(e) for e in mapping.get("b") or []) if x]
    beyond = mapping.get("beyond")
    non_fits = mapping.get("non_fits")
    if a_lines or b_lines or beyond or non_fits:
        lines = ["AI-literacy mapping (OECD / European Union 2026; the platform's own reading, "
                 "the framework names no page):"]
        if a_lines:
            lines.append("(a) 100 % hits — the scenario contains the activity of the "
                         "framework's \"In the Classroom\" example at that level:")
            lines += a_lines
        if b_lines:
            lines.append("(b) mutatis mutandis — with the modification named:")
            lines += b_lines
        if isinstance(beyond, str) and beyond:
            lines.append(f"Beyond the framework: {beyond}")
        if isinstance(non_fits, str) and non_fits:
            lines.append(f"Non-fits: {non_fits}")
        lines.append(NO_THRESHOLD)
        out.append("\n".join(lines))
    return "\n\n".join(out)


def menu(language: Optional[str] = None) -> str:
    """Every place this catalogue holds, nested, so a caller can pick one.

    Names only, in `language` (display_name) — the text comes from asking for
    one of them.
    """
    if not ITEMS:
        return ""
    lines = []
    for item in ITEMS.values():
        depth = item["id"].count(".")
        lines.append("  " * depth + f"{display_name(item, language)}  [{item['id']}]")
    return "\n".join(lines)
