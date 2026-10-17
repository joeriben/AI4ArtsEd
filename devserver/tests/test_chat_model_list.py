"""The chat-model list over every keyed provider (chat_routes, 2026-09-12).

Until then the cloud half of the list was the ACTIVE provider's role cells
and `chat_models`; a surface that compares models was as full as that one
provider's offer. Now: the register's models, one entry each, through one
provider -- a route recorded as conform first, the active provider next, then
the table's order. What the register records about a provider keeps none out:
it orders them and travels with the entry, for the mark the surfaces show
beside the model. The reach list (config/model_providers.json) and this
installation's own cells are the two sources.
"""
import sys
from pathlib import Path

import pytest

DEVSERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEVSERVER))

from my_app.routes import chat_routes  # noqa: E402
from my_app.services import llm_providers as lp  # noqa: E402
from my_app.services import model_reach  # noqa: E402

TABLE = lp.names()

GLM = {"glm-5.3": {"openrouter": "z-ai/glm-5.3", "mammouth": "glm-5.3"}}


@pytest.fixture()
def world(monkeypatch):
    """The four things the list is built from, each set by a test. The
    register is empty by default, which limits nothing."""
    state = {"reach": {}, "keyed": set(), "active": "none", "register": {}}
    monkeypatch.setattr(chat_routes, "model_reach", lambda: state["reach"])
    monkeypatch.setattr(chat_routes, "has_key", lambda name: name in state["keyed"])
    monkeypatch.setattr(chat_routes, "get_user_setting",
                        lambda key, default=None: state["active"])
    monkeypatch.setattr(chat_routes, "load_register", lambda: state["register"])
    return state


def _presets(**per_provider):
    """A matrix with one preset per named provider: True/False is the recorded
    conformity WITH its grounds, None a preset that records nothing."""
    presets = {}
    for p, recorded in per_provider.items():
        presets[p] = {"models": {}}
        if recorded is not None:
            presets[p].update({"DSGVO_CONFORMITY": recorded, "DSGVO_NOTE": "recorded"})
    return {"llm_presets": presets}


def _list(matrix):
    return chat_routes._cloud_chat_models_from_matrix(matrix)


def _ids(matrix):
    return [(m["id"], m["register"]) for m in _list(matrix)]


# ------------------------------------------------------------ one route


def test_one_entry_per_model_through_the_active_provider(world):
    world["reach"] = GLM
    world["keyed"] = {"openrouter", "mammouth"}
    world["active"] = "mammouth"
    assert _list(_presets(openrouter=True, mammouth=True)) == [
        {"id": "mammouth/glm-5.3", "label": "glm-5.3", "register": "glm-5.3",
         "available": True, "installable": False}]


def test_without_the_active_provider_the_tables_order_decides(world):
    world["reach"] = GLM
    world["keyed"] = {"openrouter", "mammouth"}
    world["active"] = "none"
    first = next(p for p in TABLE if p in world["keyed"])
    [entry] = _list(_presets(openrouter=True, mammouth=True))
    assert entry["id"].startswith(f"{first}/")
    assert entry["register"] == "glm-5.3"


def test_a_route_recorded_as_conform_comes_before_the_active_provider(world):
    """Where the text goes is decided by what the register records. A flag
    without its grounds records nothing."""
    world["reach"] = GLM
    world["keyed"] = {"openrouter", "mammouth"}
    world["active"] = "openrouter"
    [entry] = _list(_presets(openrouter=None, mammouth=True))
    assert entry["id"] == "mammouth/glm-5.3"
    ungrounded = {"llm_presets": {"openrouter": {"models": {}},
                                  "mammouth": {"DSGVO_CONFORMITY": True}}}
    [entry] = _list(ungrounded)
    assert entry["id"] == "openrouter/z-ai/glm-5.3"


# ------------------------------------------------- which providers at all


def test_a_provider_without_a_key_reaches_nothing(world):
    world["reach"] = {"glm-5.3": {"openrouter": "z-ai/glm-5.3"}}
    world["keyed"] = {"mammouth"}
    world["active"] = "mammouth"
    assert _list(_presets(openrouter=True, mammouth=True)) == []


def test_no_key_anywhere_means_no_cloud_model(world):
    world["reach"] = GLM
    assert _list(_presets(openrouter=True, mammouth=True)) == []


@pytest.mark.parametrize("recorded", [False, None])
def test_a_provider_not_recorded_as_conform_is_offered_and_ranked_last(world, recorded):
    """The record keeps no route out of the list: it travels with the entry,
    and the surfaces show it beside the model. What it decides is the order --
    a conform route comes first, whatever the operator set as active, so a
    model goes through a non-conform provider only where no conform one
    reaches it."""
    world["reach"] = {"glm-5.3": {"openrouter": "z-ai/glm-5.3"}}
    world["keyed"] = {"openrouter", "mammouth"}
    world["active"] = "mammouth"
    assert _ids(_presets(openrouter=recorded, mammouth=True)) == [("openrouter/z-ai/glm-5.3", "glm-5.3")]
    world["reach"] = GLM
    world["active"] = "openrouter"
    [entry] = _list(_presets(openrouter=recorded, mammouth=True))
    assert entry["id"] == "mammouth/glm-5.3"


def test_a_keyed_provider_without_a_preset_offers_nothing(world):
    """Active or not: the preset is where a provider's record lives, and the
    gate answers such a provider's ids as register_broken."""
    world["reach"] = {"glm-5.3": {"openrouter": "z-ai/glm-5.3"}}
    world["keyed"] = {"openrouter"}
    world["active"] = "openrouter"
    assert _list({"llm_presets": {"mammouth": {"models": {}}}}) == []


def test_a_matrix_without_presets_offers_nothing(world):
    """An unreadable matrix fails closed, as the list did before."""
    world["reach"] = GLM
    world["keyed"] = {"mammouth"}
    world["active"] = "mammouth"
    for matrix in ({}, {"llm_presets": {}}, {"llm_presets": []}, "garbage"):
        assert _list(matrix) == []


def test_a_preset_that_is_not_one_costs_that_provider_and_nothing_else(world):
    world["reach"] = GLM
    world["keyed"] = {"openrouter", "mammouth"}
    world["active"] = "openrouter"
    matrix = _presets(mammouth=True)
    matrix["llm_presets"]["openrouter"] = "broken"
    assert _ids(matrix) == [("mammouth/glm-5.3", "glm-5.3")]


def test_malformed_cells_cost_the_cells_and_not_the_provider(world):
    """The provider's record stands; what its cells would have added is lost."""
    world["reach"] = GLM
    world["keyed"] = {"openrouter", "mammouth"}
    world["active"] = "openrouter"
    matrix = _presets(openrouter=True, mammouth=True)
    matrix["llm_presets"]["openrouter"].update({"models": ["not-a-dict"], "chat_models": "not-a-list"})
    assert _ids(matrix) == [("openrouter/z-ai/glm-5.3", "glm-5.3")]


# ------------------------------------------------------------ the register


def test_the_list_is_limited_to_the_registers_models(world):
    world["reach"] = {"glm-5.3": {"mammouth": "glm-5.3"}, "unknown-to-the-register": {"mammouth": "x"}}
    world["keyed"] = {"mammouth"}
    world["active"] = "mammouth"
    world["register"] = {"models": {"glm-5.3": {}, "kimi-k3": {}}}
    matrix = _presets(mammouth=True)
    matrix["llm_presets"]["mammouth"]["models"] = {"A": "mammouth/kimi-k3", "B": "mammouth/codestral-latest"}
    assert _ids(matrix) == [("mammouth/glm-5.3", "glm-5.3"), ("mammouth/kimi-k3", "kimi-k3")]


def test_an_unreadable_register_limits_nothing(world, monkeypatch):
    """Missing, of another shape, or raising on the way in: the cells stand
    as they are. A cell without a name after its last slash is no model."""
    world["keyed"] = {"mammouth"}
    world["active"] = "mammouth"
    matrix = _presets(mammouth=True)
    matrix["llm_presets"]["mammouth"]["models"] = {"A": "mammouth/whatever", "B": "mammouth/glm-5.3/"}

    def _raises():
        raise PermissionError("no")

    for register in ({}, {"models": []}, [1], _raises):
        world["register"] = register
        if callable(register):
            monkeypatch.setattr(chat_routes, "load_register", register)
        assert _ids(matrix) == [("mammouth/whatever", "whatever")]


def test_the_register_name_is_carried_where_the_provider_calls_it_otherwise(world):
    """The hand-kept 'declared' block: Mistral ships Mistral Large 3 as
    mistral-large-2512. The id is the provider's, the label and the register
    name the register's, and the lineups key on the latter."""
    world["reach"] = {"mistral-large-3": {"mistral": "mistral-large-2512"}}
    world["keyed"] = {"mistral"}
    world["active"] = "mistral"
    [entry] = _list(_presets(mistral=True))
    assert entry["id"] == "mistral/mistral-large-2512"
    assert entry["label"] == "mistral-large-3"
    assert entry["register"] == "mistral-large-3"


# ------------------------------------------------------------- the cells


def test_this_installations_cells_add_what_the_reach_list_lacks(world):
    world["reach"] = {"mistral-large-3": {"mistral": "mistral-large-2512"}}
    world["keyed"] = {"mistral"}
    world["active"] = "mistral"
    world["register"] = {"models": {"mistral-large-3": {}, "magistral-medium": {}, "ministral-8b": {}}}
    matrix = _presets(mistral=True)
    matrix["llm_presets"]["mistral"].update({
        "models": {"STAGE2_INTERCEPTION_MODEL": "mistral/mistral-large-2512",
                   "CHAT_HELPER_MODEL": "mistral/magistral-medium"},
        "chat_models": ["mistral/mistral-large-2512", "mistral/ministral-8b"],
        "chat_fallback_models": ["mistral/mistral-large-2411"],
    })
    # The reach entry stands once, under the register's name; the two cells
    # the reach list lacks follow, under their own last segment; the fallback
    # list stays out.
    assert _ids(matrix) == [("mistral/mistral-large-2512", "mistral-large-3"),
                            ("mistral/magistral-medium", "magistral-medium"),
                            ("mistral/ministral-8b", "ministral-8b")]


def test_a_cell_wins_over_the_reach_list_for_the_same_model_at_the_same_provider(world):
    """The cell is what the operator configured; the reach entry is what the
    catalogue said on the day."""
    world["reach"] = {"glm-5.3": {"openrouter": "z-ai/glm-5.3"}}
    world["keyed"] = {"openrouter"}
    world["active"] = "openrouter"
    matrix = _presets(openrouter=True)
    matrix["llm_presets"]["openrouter"]["models"] = {"A": "openrouter/~z-ai/glm-5.3"}
    assert _ids(matrix) == [("openrouter/~z-ai/glm-5.3", "glm-5.3")]


def test_a_cell_of_another_column_is_not_this_providers_model(world):
    world["keyed"] = {"mistral"}
    world["active"] = "mistral"
    matrix = _presets(mistral=True)
    matrix["llm_presets"]["mistral"]["models"] = {
        "STAGE2_INTERCEPTION_MODEL": "mammouth/glm-5.3",
        "CHAT_HELPER_MODEL": "a-bare-name",
        "PERSONA_MODEL": "",
        "RESONA_MODEL": "mistral/ ",
        "CODING_MODEL": None,
    }
    matrix["llm_presets"]["mistral"]["chat_models"] = [None, 5, "mistral/"]
    assert _list(matrix) == []


# ------------------------------------------------------------- the file


def test_the_reach_file_is_read_as_one_answer(monkeypatch, tmp_path):
    """'declared' stands beside 'reach' and wins where both name a provider;
    a missing file, or one of another shape, is an empty answer with a log
    line, not an error; a blank id is no id."""
    f = tmp_path / "model_providers.json"
    f.write_text('''{"reach": {"m": {"openrouter": "x/m", "mistral": "m-old", "ionos": "  "}},
                     "declared": {"m": {"_source": "https://example.org", "mistral": " m-2512 "}},
                     "n": "ignored"}''')
    monkeypatch.setattr(model_reach, "REACH_FILE", f)
    assert model_reach.reach() == {"m": {"openrouter": "x/m", "mistral": "m-2512"}}
    monkeypatch.setattr(model_reach, "REACH_FILE", tmp_path / "missing.json")
    assert model_reach.reach() == {}
    f.write_text('[1, 2]')
    monkeypatch.setattr(model_reach, "REACH_FILE", f)
    assert model_reach.reach() == {}


def test_the_shipped_reach_list_names_only_table_providers_and_register_models():
    import json
    register = json.loads((DEVSERVER / "config" / "model_register.json").read_text())
    reach = model_reach.reach()
    assert reach, "the shipped reach list is empty or unreadable"
    for name, per_provider in reach.items():
        assert name in register["models"], f"{name}: not in the register"
        for p in per_provider:
            assert p in TABLE, f"{name}: {p} is not a provider of the table"
