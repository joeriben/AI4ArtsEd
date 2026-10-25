"""platform_items + lookup_place — the catalogue as something to ask.

The load-bearing points: the catalogue reaches BOTH agents (the page injection
was only ever the help agent's, and only for the tile in front of the person),
a name works as well as an id because a model will say "Encoder Fusion", and a
miss comes back with the menu instead of an invented answer.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_items_load_with_ids_and_parents():
    from my_app.services import platform_items as pi
    assert pi.ITEMS, "platform_items.json did not load"
    for item_id, item in pi.ITEMS.items():
        assert item["id"] == item_id
        parent = item.get("parent")
        assert not parent or parent in pi.ITEMS, f"{item_id} points at a missing parent"


def test_find_by_name_and_id_and_miss():
    from my_app.services import platform_items as pi
    by_id = pi.find("latent_lab.image.fusion")
    assert by_id and by_id["id"] == "latent_lab.image.fusion"
    by_name = pi.find("Encoder Fusion")
    assert by_name and by_name["id"] == "latent_lab.image.fusion"
    assert pi.find("a place that is not here") is None
    assert pi.find("") is None


def test_render_carries_the_parent_line():
    from my_app.services import platform_items as pi
    item = pi.get("latent_lab.image.composable")
    text = pi.render(item)
    assert text.startswith("Diffusion Lab:"), text[:60]
    assert "Composable Diffusion" in text


def test_lookup_place_in_both_scopes_and_a_miss_lists_the_menu():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    universal = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    resona = {t["function"]["name"] for t in registry.get_openai_format(scope="resona")}
    assert "lookup_place" in universal
    assert "lookup_place" in resona

    miss = registry.execute("lookup_place", {"place": "not a place of this platform"})
    assert "not in this catalogue" in miss
    assert "latent_lab.image.fusion" in miss, "a miss must show what there is"

    empty = registry.execute("lookup_place", {})
    assert "latent_lab.image.fusion" in empty
