"""platform_items + lookup_place — the catalogue as something to ask.

The load-bearing points: the catalogue reaches BOTH agents (the page injection
was only ever the help agent's, and only for the tile in front of the person),
a name works as well as an id because a model will say "Encoder Fusion", and a
miss comes back with the menu instead of an invented answer. A page is named
in the conversation language, with the English label in brackets where the two
differ, because the visitor's screen carries the label of their language.
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


def test_find_prefers_the_handle_and_falls_back_to_the_labels():
    """A one-word English query resolves as it did when only handles were
    searched; a label in another language is found when no handle has it."""
    from my_app.services import platform_items as pi
    assert pi.find("Language")["id"] == "compare.language"
    assert pi.find("Cultural")["id"] == "latent_lab.image.census"
    assert pi.find("Analysis")["id"] == "compare.vlm_analysis"
    assert pi.find("Stereotypen")["id"] == "latent_lab.image.census"
    assert pi.find("Stereotypen-Analyse")["id"] == "latent_lab.image.census"


def test_mean_images_stands_in_the_category_the_column_shows():
    """latent_lab.vue, GROUPS: `mean` is listed under `compare`."""
    from my_app.services import platform_items as pi
    assert pi.get("latent_lab.image.mean")["parent"] == "compare"


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


def _build_script():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_platform_items.py"
    spec = importlib.util.spec_from_file_location("build_platform_items", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_item_carries_a_label_in_every_shipped_language():
    from my_app.services import platform_items as pi
    shipped, _ = _build_script().shipped_catalogues()
    for item_id, item in pi.ITEMS.items():
        names = item.get("names") or {}
        assert set(names) == set(shipped), f"{item_id}: {sorted(names)}"


def test_display_name_in_the_conversation_language():
    from my_app.services import platform_items as pi
    census = pi.get("latent_lab.image.census")
    language = pi.get("compare.language")
    assert pi.display_name(census, "de") == "Stereotypen-Analyse (Stereotype Analysis)"
    assert pi.display_name(language, "de") == "Sprachverständnis (Language Understanding)"
    assert pi.display_name(census, "en") == "Stereotype Analysis"
    assert pi.display_name(language, "en") == "Language Understanding"
    assert pi.display_name(census) == "Stereotype Analysis"


def test_a_language_without_its_own_string_gets_the_english_name_alone():
    from my_app.services import platform_items as pi
    build = _build_script()
    catalogues = {
        "en": {"compare": {"tabs": {"census": "Stereotype Analysis"}}},
        "de": {"compare": {"tabs": {"census": "Stereotypen-Analyse"}}},
        "xx": {"compare": {"tabs": {}}},
    }
    names = build.names_for("compare.tabs.census", catalogues, "en")
    assert names == {"en": "Stereotype Analysis", "de": "Stereotypen-Analyse",
                     "xx": "Stereotype Analysis"}
    item = {"id": "latent_lab.image.census", "name": "handle", "names": names}
    assert pi.display_name(item, "xx") == "Stereotype Analysis"
    assert pi.display_name(item, "de") == "Stereotypen-Analyse (Stereotype Analysis)"
    assert build.names_for("compare.tabs.missing", catalogues, "en") is None


def test_lookup_place_names_the_page_in_the_conversation_language():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    for query in ("Stereotype Analysis", "Stereotypen-Analyse", "latent_lab.image.census"):
        de = registry.execute("lookup_place", {"place": query}, language="de")
        assert de.startswith("Stereotypen-Analyse (Stereotype Analysis)\n\n"), de[:80]
        assert ("Use report V 1.0 for Stereotypen-Analyse (Stereotype Analysis) "
                "(/latent-lab/cultural-un-known)") in de
        en = registry.execute("lookup_place", {"place": query}, language="en")
        assert en.startswith("Stereotype Analysis\n\n"), en[:80]
        assert "Stereotypen-Analyse" not in en
    lang_de = registry.execute("lookup_place", {"place": "Sprachverständnis"}, language="de")
    assert lang_de.startswith("Sprachverständnis (Language Understanding)\n\n"), lang_de[:80]
    menu_de = registry.execute("lookup_place", {}, language="de")
    assert "Stereotypen-Analyse (Stereotype Analysis)  [latent_lab.image.census]" in menu_de
    # The language is the request's, never the model's.
    forged = registry.execute("lookup_place", {"place": "Stereotype Analysis", "_language": "de"})
    assert forged.startswith("Stereotype Analysis\n\n"), forged[:80]


def test_page_blocks_of_the_system_prompt_name_the_page_in_the_conversation_language():
    from my_app.routes.chat_routes import _item_block_for, _use_report_block_for
    sent = "[AKTUELLER KONTEXT]\nAktive Ansicht: default_census"
    assert "Stereotypen-Analyse (Stereotype Analysis)" in _item_block_for(sent, "de")
    assert "Stereotypen-Analyse" not in _item_block_for(sent, "en")
    assert ("Use report V 1.0 for Stereotypen-Analyse (Stereotype Analysis)"
            in _use_report_block_for(sent, "de"))
    assert "Use report V 1.0 for Stereotype Analysis (" in _use_report_block_for(sent, "en")
