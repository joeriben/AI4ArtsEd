"""Platform items — what the labs and Compare say about their own technology.

platform_items.json is that wording, moved out of the i18n catalogue unchanged
(built by scripts/build_platform_items.py) so it survives the pages being
emptied. This module is the one place that reads it: chat_routes injects the
item for the page somebody stands on, and the lookup_place tool answers for any
of them.

The id carries the nesting (latent_lab.image.composable), because 21 of the 24
items are tabs with no route of their own.

Since 2026-09-02 an item also carries `ailit`, since 2026-09-19 the measures
of the AILit framework (OECD / European Union 2026, CC BY 4.0) this place
supports as a tool, each with the verbatim Learner Expectation and "In the
Classroom" scenario and their pages, joined by route in the build. Help was
asked what a page is for in educational terms and had nothing to answer with.
goals() renders them; render() does not, because the two are different kinds
of statement and the callers head them differently. The pages the catalogue
has no item for (Flow, Canvas, Contesting, Together, and the two Latent Lab
pages that report no view) get their measures from ailit_coverage.json
instead, through place_for_view(), place_for_route() and find_place().
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

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

# The measures per route and the parts that carry them, for the pages the
# catalogue has no item for (built by scripts/build_ailit_support.py). Help is
# told to answer from the catalogue, and for Flow, the page with the most
# measures of all, it answered with a miss (measured 2026-09-19).
COVERAGE_PATH = ITEMS_PATH.parent / "ailit_coverage.json"


def _load_coverage() -> dict:
    try:
        if not COVERAGE_PATH.exists():
            logger.warning("AILit coverage not found: %s", COVERAGE_PATH)
            return {}
        with open(COVERAGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        places = [p for p in data.get("places") or [] if isinstance(p, dict)]
        by_route = data.get("by_route") or {}
        by_part = data.get("by_part") or {}
        logger.info("Loaded AILit coverage: %d places, %d routes and %d functions with measures",
                    len(places), len(by_route), len(by_part))
        return {"places": places, "by_route": by_route, "by_part": by_part}
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load AILit coverage: %s", e)
        return {}


COVERAGE: dict = _load_coverage()


def get(item_id: str) -> Optional[dict]:
    return ITEMS.get(item_id)


def find(query: str) -> Optional[dict]:
    """The item a person means, by id or by name.

    Exact id first, then an exact name, then a name that contains the query —
    the model will say "Encoder Fusion" far more often than
    "latent_lab.image.fusion".
    """
    q = (query or "").strip().lower()
    if not q:
        return None
    for item in ITEMS.values():
        if item["id"].lower() == q:
            return item
    for item in ITEMS.values():
        if (item.get("name") or "").lower() == q:
            return item
    hits = [it for it in ITEMS.values()
            if q in (it.get("name") or "").lower() or q in it["id"].lower()]
    return hits[0] if len(hits) == 1 else None


def _place_item(place: dict) -> Optional[dict]:
    """A part of the coverage file in the shape goals() renders, or None
    when no measure is joined to it. A page is joined by its route; a
    cross-cutting function (the header, the AI marking) has no route and is
    joined by its key."""
    route = place.get("route") or ""
    if route.startswith("/"):
        goals_ = (COVERAGE.get("by_route") or {}).get(route)
    else:
        goals_ = (COVERAGE.get("by_part") or {}).get(place.get("key") or "")
    if not goals_:
        return None
    return {
        "id": place.get("key", ""),
        # English first, as the catalogue names its items; the German label
        # beside it, so the caller can print both where they differ.
        "name": place.get("name") or place.get("name_de") or place.get("key", ""),
        "name_de": place.get("name_de") or "",
        "route": place.get("route"),
        "ailit": {"goals": goals_},
    }


def place_for_view(stem: str) -> Optional[dict]:
    """The part whose page reports `stem` as its view, with its measures."""
    for place in COVERAGE.get("places") or []:
        if stem and stem in (place.get("views") or []):
            return _place_item(place)
    return None


def place_for_route(route: str) -> Optional[dict]:
    """The part at `route`, with its measures. An earlier address a page
    still answers under (the overview as /latent-lab/intro) counts as its
    route; the coverage file lists them as `aliases`."""
    for place in COVERAGE.get("places") or []:
        if route and (place.get("route") == route or route in (place.get("aliases") or [])):
            return _place_item(place)
    return None


def item_for_route(route: str) -> Optional[dict]:
    """The catalogue item at `route`, or None. A place of the coverage file
    found by its German name may be a page the catalogue holds under its
    English name; the item is the answer then, with the page's own text."""
    if not route:
        return None
    for item in ITEMS.values():
        if item.get("route") == route:
            return item
    return None


def place_menu() -> str:
    """The parts that carry measures and have no catalogue item, one per
    line, for the answer that lists what can be asked for. The catalogue's
    own menu() lists its items alone, and the miss text names Flow among
    what can be asked for."""
    lines = []
    for place in COVERAGE.get("places") or []:
        route = place.get("route") or ""
        if route.startswith("/") and any(i.get("route") == route for i in ITEMS.values()):
            continue
        item = _place_item(place)
        if not item:
            continue
        name = item["name"]
        if item.get("name_de") and item["name_de"] != name:
            name += f" ({item['name_de']})"
        where = route if route.startswith("/") else "on every page, no route of its own"
        lines.append(f"{name}  [{where}]")
    return "\n".join(lines)


def find_place(query: str) -> Optional[dict]:
    """The part a person means, by key, name, route or a name that contains
    the query. The coverage file names every part in German and English,
    so a German name resolves here where find() knows the catalogue's
    English names only; the caller asks item_for_route() whether the
    catalogue holds the page and prefers that item."""
    q = (query or "").strip().lower()
    if not q:
        return None
    places = COVERAGE.get("places") or []
    for place in places:
        names = {(place.get(k) or "").lower() for k in ("key", "name", "name_de", "route")}
        if q in names:
            return _place_item(place)
    hits = [p for p in places
            if q in (p.get("name") or "").lower() or q in (p.get("name_de") or "").lower()]
    return _place_item(hits[0]) if len(hits) == 1 else None


def render(item: dict) -> str:
    """One item as text: where it sits, what it is, how it works."""
    lines: List[str] = []
    parent = ITEMS.get(item.get("parent") or "")
    if parent:
        brief = (parent.get("technical") or {}).get("brief")
        if brief:
            lines.append(f"{parent.get('name', '')}: {brief}")
    lines.append(item.get("name", ""))
    if item.get("route"):
        lines.append(f"Route: {item['route']}")
    tech = item.get("technical") or {}
    for key, label in FIELDS:
        value = tech.get(key)
        if value:
            lines.append(f"{label}: {value}")
    return "\n\n".join(x for x in lines if x)


def goals(item: dict) -> str:
    """The measures of the AILit framework this place supports, in the
    framework's own wording, or "" when the catalogue holds none for it.

    Kept apart from render(): that text is what the page says about its own
    technology, this one is the platform's reading of the AILit framework
    (OECD / European Union 2026). The callers put it under a heading of its
    own, so the model never takes a measure for a statement the page makes.
    Per measure: the competence, the level with its verbatim Learner
    Expectation and page, the verbatim "In the Classroom" scenario with its
    page, then how this page carries the measure and a practical scenario of
    this platform (docs/ailit/unterstuetzung.tsv, German). Malformed data is
    skipped, so a hand-edited block cannot take Help down on that page.
    """
    ail = item.get("ailit")
    if not isinstance(ail, dict):
        return ""
    status_de = {"ja": "ja", "angepasst": "ja, angepasst"}
    out: List[str] = []
    for goal in ail.get("goals") or []:
        if not isinstance(goal, dict):
            continue
        title = goal.get("competence")
        expectation = goal.get("expectation")
        if not isinstance(title, str) or not title:
            continue
        if not isinstance(expectation, str) or not expectation:
            continue
        level = goal.get("level")
        if not isinstance(level, str) or not level:
            continue
        if goal.get("status") not in status_de:
            # Only a supported measure is rendered: a `nein` never leaves the
            # build, and a hand-edited one must not read as support.
            continue
        page = f", S. {goal['page']}" if goal.get("page") else ""
        out.append(f"{title}")
        out.append(f"  {level}{page}: \u201e{expectation}\u201c")
        classroom = goal.get("classroom")
        if isinstance(classroom, str) and classroom:
            cpage = f", S. {goal['classroom_page']}" if goal.get("classroom_page") else ""
            out.append(f"  In the Classroom{cpage}: \u201e{classroom}\u201c")
        how = goal.get("how_de")
        if isinstance(how, str) and how:
            st = status_de[goal["status"]]
            out.append(f"  Unterst\u00fctzung durch diese Seite ({st}): {how}")
        practice = goal.get("practice_de")
        if isinstance(practice, str) and practice:
            out.append(f"  Praxis-Szenario: {practice}")
    if not out:
        return ""
    out.append("")
    out.append("Das Rahmenwerk nennt keine Schwelle, ab der eine Kompetenz als "
               "erreicht gilt.")
    return "\n".join(out)


def menu() -> str:
    """Every place this catalogue holds, nested, so a caller can pick one.

    Names only — the text comes from asking for one of them.
    """
    if not ITEMS:
        return ""
    lines = []
    for item in ITEMS.values():
        depth = item["id"].count(".")
        lines.append("  " * depth + f"{item.get('name', item['id'])}  [{item['id']}]")
    return "\n".join(lines)
