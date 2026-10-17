"""
Tests for Resona "spricht Graphen" — canvas graph authoring, workflow store, and
the two new registry tools (run_canvas_graph, canvas_graph_library).

Covers:
- validate_and_expand: rejects unknown node type / unknown configId (msg lists
  valid ids) / cycle / missing input / >4 generation nodes / bad connection refs
  / param-node connected to a non-generation node.
- expansion: inline seed+width+height+steps+cfg on a generation node become
  seed/resolution/quality source nodes wired to it, and the inline keys are
  stripped from the generation node.
- summarize_graph: returns a compact (<=200 char) human line.
- canvas_workflow_store: save -> list -> get roundtrip (tmp_path STORAGE_DIR),
  query filtering, id sanitization (get_workflow("../../etc") -> None).
- registry tools: run_canvas_graph happy ("Apparatus '…' validated") + error
  ("Error: …"); canvas_graph_library save/list/get through registry.execute.
- RESONA_CORE_PROMPT contains "BUILDING APPARATUS" + both tool names.
- every RESONA_CANVAS_CONFIGS id has an output config file on disk.

Run: python3 -m pytest devserver/tests/test_resona_canvas_graphs.py -q
(from the worktree root; also works from devserver/ directly)
"""

import re
import sys
from pathlib import Path

# devserver/tests/test_resona_canvas_graphs.py -> parents[1] == devserver/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import canvas_graph_authoring as cga
from my_app.services import canvas_workflow_store as store
from my_app.services.tool_registry import get_tool_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linear_graph(config_id="sd35_large", **gen_extra):
    """input -> interception -> translation -> generation(config_id, **gen_extra)."""
    gen = {"id": "gn1", "type": "generation", "configId": config_id}
    gen.update(gen_extra)
    return {
        "nodes": [
            {"id": "in1", "type": "input", "promptText": "a tree"},
            {"id": "ic1", "type": "interception", "contextPrompt": "see it as a memory of loss"},
            {"id": "tr1", "type": "translation"},
            gen,
        ],
        "connections": [
            {"sourceId": "in1", "targetId": "ic1"},
            {"sourceId": "ic1", "targetId": "tr1"},
            {"sourceId": "tr1", "targetId": "gn1"},
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Redirect the workflow store to throwaway tmp_path so tests never touch
    real exports/json/canvas_workflows/."""
    monkeypatch.setattr(store, "STORAGE_DIR", tmp_path / "canvas_workflows")
    yield


# ---------------------------------------------------------------------------
# validate_and_expand — happy path
# ---------------------------------------------------------------------------

def test_valid_linear_graph_passes():
    payload, err = cga.validate_and_expand(_linear_graph())
    assert err is None
    assert payload is not None
    types = sorted(n["type"] for n in payload["nodes"])
    assert types == ["generation", "input", "interception", "translation"]
    # labels normalized on connections
    assert all(set(c.keys()) == {"sourceId", "targetId", "label"} for c in payload["connections"])


def test_shape_rejects_non_dict_and_empty_nodes():
    p, e = cga.validate_and_expand("not a graph")
    assert p is None and "object" in e
    p, e = cga.validate_and_expand({"nodes": []})
    assert p is None and "non-empty" in e


# ---------------------------------------------------------------------------
# validate_and_expand — rejections
# ---------------------------------------------------------------------------

def test_unknown_node_type_rejected():
    g = {"nodes": [{"id": "a", "type": "frobnicate"}]}
    p, e = cga.validate_and_expand(g)
    assert p is None
    assert "unknown type" in e
    assert "frobnicate" in e


def test_unknown_config_id_rejected_and_lists_valid():
    g = {
        "nodes": [
            {"id": "in1", "type": "input"},
            {"id": "gn1", "type": "generation", "configId": "not_a_real_config"},
        ],
        "connections": [{"sourceId": "in1", "targetId": "gn1"}],
    }
    p, e = cga.validate_and_expand(g)
    assert p is None
    assert "not_a_real_config" in e
    # error message lists valid ids
    assert "sd35_large" in e
    assert re.search(r"\bsurrealization\b", e)


def test_cycle_rejected():
    g = {
        "nodes": [
            {"id": "in1", "type": "input"},
            {"id": "a", "type": "interception"},
            {"id": "b", "type": "interception"},
        ],
        "connections": [
            {"sourceId": "in1", "targetId": "a"},
            {"sourceId": "a", "targetId": "b"},
            {"sourceId": "b", "targetId": "a"},
        ],
    }
    p, e = cga.validate_and_expand(g)
    assert p is None
    assert "acyclic" in e


def test_missing_input_node_rejected():
    g = {
        "nodes": [
            {"id": "ic1", "type": "interception"},
            {"id": "gn1", "type": "generation", "configId": "flux2"},
        ],
        "connections": [{"sourceId": "ic1", "targetId": "gn1"}],
    }
    p, e = cga.validate_and_expand(g)
    assert p is None
    assert "input" in e


def test_more_than_four_generation_nodes_rejected():
    nodes = [{"id": "in1", "type": "input"}]
    conns = []
    for k in range(5):
        nodes.append({"id": f"g{k}", "type": "generation", "configId": "flux2"})
        conns.append({"sourceId": "in1", "targetId": f"g{k}"})
    p, e = cga.validate_and_expand({"nodes": nodes, "connections": conns})
    assert p is None
    assert "generation" in e and "4" in e


def test_bad_connection_refs_rejected():
    g = {
        "nodes": [{"id": "in1", "type": "input"}, {"id": "gn1", "type": "generation", "configId": "flux2"}],
        "connections": [{"sourceId": "in1", "targetId": "ghost"}],
    }
    p, e = cga.validate_and_expand(g)
    assert p is None
    assert "ghost" in e


def test_param_node_to_non_generation_rejected():
    g = {
        "nodes": [
            {"id": "in1", "type": "input"},
            {"id": "s1", "type": "seed", "seedMode": "fixed", "seedValue": 1},
            {"id": "ic1", "type": "interception"},
        ],
        "connections": [
            {"sourceId": "in1", "targetId": "ic1"},
            {"sourceId": "s1", "targetId": "ic1"},
        ],
    }
    p, e = cga.validate_and_expand(g)
    assert p is None
    assert "generation" in e


def test_generation_to_generation_rejected():
    g = {
        "nodes": [
            {"id": "in1", "type": "input"},
            {"id": "g1", "type": "generation", "configId": "flux2"},
            {"id": "g2", "type": "generation", "configId": "sd35_large"},
        ],
        "connections": [
            {"sourceId": "in1", "targetId": "g1"},
            {"sourceId": "g1", "targetId": "g2"},
        ],
    }
    p, e = cga.validate_and_expand(g)
    assert p is None


def test_unreachable_node_rejected():
    g = {
        "nodes": [
            {"id": "in1", "type": "input"},
            {"id": "g1", "type": "generation", "configId": "flux2"},
            {"id": "orphan", "type": "interception"},
        ],
        "connections": [{"sourceId": "in1", "targetId": "g1"}],
    }
    p, e = cga.validate_and_expand(g)
    assert p is None
    assert "orphan" in e and "reachable" in e


def test_generation_to_evaluation_allowed():
    g = {
        "nodes": [
            {"id": "in1", "type": "input"},
            {"id": "g1", "type": "generation", "configId": "flux2"},
            {"id": "ev1", "type": "evaluation", "evaluationPrompt": "what do you see?"},
        ],
        "connections": [
            {"sourceId": "in1", "targetId": "g1"},
            {"sourceId": "g1", "targetId": "ev1"},
        ],
    }
    p, e = cga.validate_and_expand(g)
    assert e is None
    assert p is not None


# ---------------------------------------------------------------------------
# Expansion: inline convenience keys -> param source nodes
# ---------------------------------------------------------------------------

def test_inline_params_expand_to_source_nodes_and_strip_keys():
    g = _linear_graph(seed=42, width=1024, height=768, steps=25, cfg=5.5)
    payload, err = cga.validate_and_expand(g)
    assert err is None

    by_type = {}
    for n in payload["nodes"]:
        by_type.setdefault(n["type"], []).append(n)

    # generation node no longer carries the inline keys
    gen = by_type["generation"][0]
    for k in ("seed", "width", "height", "steps", "cfg"):
        assert k not in gen

    # a seed node exists, wired to the generation node
    assert len(by_type.get("seed", [])) == 1
    seed_node = by_type["seed"][0]
    assert seed_node["seedMode"] == "fixed"
    assert seed_node["seedValue"] == 42

    # a resolution node exists with custom preset + w/h
    assert len(by_type.get("resolution", [])) == 1
    res_node = by_type["resolution"][0]
    assert res_node["resolutionPreset"] == "custom"
    assert res_node["resolutionWidth"] == 1024
    assert res_node["resolutionHeight"] == 768

    # a quality node exists with steps + cfg
    assert len(by_type.get("quality", [])) == 1
    q_node = by_type["quality"][0]
    assert q_node["qualitySteps"] == 25
    assert q_node["qualityCfg"] == 5.5

    # each param node is connected to the generation node
    gid = gen["id"]
    param_ids = {seed_node["id"], res_node["id"], q_node["id"]}
    wired = {c["sourceId"] for c in payload["connections"] if c["targetId"] == gid}
    assert param_ids <= wired


def test_out_of_range_inline_params_rejected():
    for bad in [{"seed": -1}, {"width": 10, "height": 10}, {"steps": 999}, {"cfg": 99}]:
        p, e = cga.validate_and_expand(_linear_graph(**bad))
        assert p is None, f"expected rejection for {bad}"


def test_width_without_height_rejected():
    p, e = cga.validate_and_expand(_linear_graph(width=1024))
    assert p is None
    assert "width and height" in e


# ---------------------------------------------------------------------------
# summarize_graph
# ---------------------------------------------------------------------------

def test_summarize_graph_is_short_and_descriptive():
    payload, _ = cga.validate_and_expand(_linear_graph())
    s = cga.summarize_graph(payload)
    assert len(s) <= 200
    assert "input" in s
    assert "generation" in s
    assert "sd35_large" in s


def test_summarize_graph_multi_generation_count():
    g = {
        "nodes": [
            {"id": "in1", "type": "input"},
            {"id": "g1", "type": "generation", "configId": "sd35_large"},
            {"id": "g2", "type": "generation", "configId": "surrealization"},
        ],
        "connections": [
            {"sourceId": "in1", "targetId": "g1"},
            {"sourceId": "in1", "targetId": "g2"},
        ],
    }
    payload, _ = cga.validate_and_expand(g)
    s = cga.summarize_graph(payload)
    assert len(s) <= 200
    assert "sd35_large" in s and re.search(r"\bsurrealization\b", s)


# ---------------------------------------------------------------------------
# canvas_workflow_store
# ---------------------------------------------------------------------------

def test_store_save_list_get_roundtrip():
    payload, _ = cga.validate_and_expand(_linear_graph())
    rec = store.save_strategy(
        "Loss lens",
        payload,
        description="a memory apparatus",
        application_type="verwandlung",
        memo="built to see the tree as loss",
    )
    import re
    assert re.match(r"^cw_[a-f0-9]{8}$", rec["id"])
    assert rec["title"] == "Loss lens"
    assert rec["application_type"] == "verwandlung"
    assert len(rec["versions"]) == 1
    assert rec["versions"][0]["version"] == 1
    assert rec["versions"][0]["memo"] == "built to see the tree as loss"
    assert rec["versions"][0]["feedback"] == []
    assert rec["created_at"] == rec["updated_at"]

    listing = store.list_strategies()
    assert len(listing) == 1
    assert listing[0]["id"] == rec["id"]
    assert listing[0]["title"] == "Loss lens"
    assert listing[0]["application_type"] == "verwandlung"
    assert listing[0]["version_count"] == 1
    assert listing[0]["latest_memo"] == "built to see the tree as loss"

    got = store.get_strategy(rec["id"])
    assert got is not None
    assert got["selected_version"]["workflow"]["nodes"] == payload["nodes"]


def test_store_list_filters_by_application_type():
    payload, _ = cga.validate_and_expand(_linear_graph())
    store.save_strategy("Side by side", payload, application_type="vergleich")
    store.save_strategy("Turn it over", payload, application_type="Verwandlung")
    store.save_strategy("Untyped one", payload)
    assert len(store.list_strategies()) == 3
    # exact, case-insensitive
    assert len(store.list_strategies(application_type="vergleich")) == 1
    assert len(store.list_strategies(application_type="verwandlung")) == 1
    assert len(store.list_strategies(application_type="VERWANDLUNG")) == 1
    assert len(store.list_strategies(application_type="einstieg")) == 0


def test_store_add_version_requires_memo_and_bumps():
    import time
    payload, _ = cga.validate_and_expand(_linear_graph())
    rec = store.save_strategy("Growing", payload)
    sid = rec["id"]
    before_updated = rec["updated_at"]

    # empty / missing memo rejected
    with pytest.raises(ValueError):
        store.add_version(sid, payload, memo="   ")
    with pytest.raises(ValueError):
        store.add_version(sid, payload, memo=None)

    time.sleep(0.01)
    updated = store.add_version(sid, payload, memo="added a second lens")
    assert len(updated["versions"]) == 2
    assert updated["versions"][-1]["version"] == 2
    assert updated["versions"][-1]["memo"] == "added a second lens"
    assert updated["updated_at"] >= before_updated
    assert updated["updated_at"] != before_updated


def test_store_add_feedback_targets_version():
    payload, _ = cga.validate_and_expand(_linear_graph())
    rec = store.save_strategy("Feedbacked", payload)
    sid = rec["id"]
    store.add_version(sid, payload, memo="v2")

    # empty note rejected
    with pytest.raises(ValueError):
        store.add_feedback(sid, note="")

    # explicit version param lands on v1
    r1 = store.add_feedback(sid, note="v1 observation", version=1)
    v1 = next(v for v in r1["versions"] if v["version"] == 1)
    v2 = next(v for v in r1["versions"] if v["version"] == 2)
    assert len(v1["feedback"]) == 1
    assert v1["feedback"][0]["note"] == "v1 observation"
    assert "ts" in v1["feedback"][0]
    assert len(v2["feedback"]) == 0

    # default lands on latest (v2)
    r2 = store.add_feedback(sid, note="latest observation")
    v2b = next(v for v in r2["versions"] if v["version"] == 2)
    assert len(v2b["feedback"]) == 1
    assert v2b["feedback"][0]["note"] == "latest observation"

    # unknown explicit version rejected
    with pytest.raises(ValueError):
        store.add_feedback(sid, note="nope", version=99)


def test_store_version_cap_rejected(monkeypatch):
    monkeypatch.setattr(store, "MAX_VERSIONS", 3)
    payload, _ = cga.validate_and_expand(_linear_graph())
    rec = store.save_strategy("Capped", payload)
    sid = rec["id"]
    store.add_version(sid, payload, memo="v2")
    store.add_version(sid, payload, memo="v3")
    with pytest.raises(ValueError):
        store.add_version(sid, payload, memo="v4 over cap")


def test_store_feedback_cap_rejected(monkeypatch):
    monkeypatch.setattr(store, "MAX_FEEDBACK_PER_VERSION", 2)
    payload, _ = cga.validate_and_expand(_linear_graph())
    rec = store.save_strategy("FB capped", payload)
    sid = rec["id"]
    store.add_feedback(sid, note="one")
    store.add_feedback(sid, note="two")
    with pytest.raises(ValueError):
        store.add_feedback(sid, note="three over cap")


def test_store_get_selected_version():
    payload_v1, _ = cga.validate_and_expand(_linear_graph(config_id="sd35_large"))
    payload_v2, _ = cga.validate_and_expand(_linear_graph(config_id="flux2"))
    rec = store.save_strategy("Versioned", payload_v1)
    sid = rec["id"]
    store.add_version(sid, payload_v2, memo="switched generator")

    got_v1 = store.get_strategy(sid, version=1)
    assert got_v1["selected_version"]["version"] == 1
    v1_gens = [n for n in got_v1["selected_version"]["workflow"]["nodes"] if n["type"] == "generation"]
    assert v1_gens[0]["configId"] == "sd35_large"

    got_latest = store.get_strategy(sid)
    assert got_latest["selected_version"]["version"] == 2

    # nonexistent version falls back to latest
    got_bad = store.get_strategy(sid, version=99)
    assert got_bad["selected_version"]["version"] == 2


def test_store_migrate_legacy_flat_file(tmp_path):
    import json
    # tmp storage is monkeypatched by the autouse fixture; write a legacy file.
    store.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    payload, _ = cga.validate_and_expand(_linear_graph())
    legacy = {
        "id": "cw_deadbe01",
        "name": "Old flat lens",
        "description": "from yesterday",
        "author": "resona",
        "created_at": "2026-07-02T09:00:00+00:00",
        "workflow": payload,
    }
    (store.STORAGE_DIR / "cw_deadbe01.json").write_text(
        json.dumps(legacy), encoding="utf-8"
    )

    got = store.get_strategy("cw_deadbe01")
    assert got is not None
    assert got["title"] == "Old flat lens"
    assert got["application_type"] == ""
    assert got["created_at"] == "2026-07-02T09:00:00+00:00"
    assert got["updated_at"] == "2026-07-02T09:00:00+00:00"
    assert len(got["versions"]) == 1
    assert got["versions"][0]["version"] == 1
    assert got["versions"][0]["memo"] is None
    assert got["versions"][0]["feedback"] == []
    assert got["versions"][0]["workflow"]["nodes"] == payload["nodes"]

    # legacy file still lists, and can be revised (persists the migrated shape)
    assert len(store.list_strategies()) == 1
    store.add_feedback("cw_deadbe01", note="held up well")
    reread = store.get_strategy("cw_deadbe01")
    assert len(reread["versions"][0]["feedback"]) == 1


def test_store_query_filters_by_name_and_description():
    payload, _ = cga.validate_and_expand(_linear_graph())
    store.save_workflow("Alpha apparatus", payload, description="about memory")
    store.save_workflow("Beta apparatus", payload, description="about colour")
    assert len(store.list_workflows(query="memory")) == 1
    assert len(store.list_workflows(query="apparatus")) == 2
    assert len(store.list_workflows(query="nonexistent-xyz")) == 0


def test_store_get_rejects_traversal_and_bad_ids():
    assert store.get_workflow("../../etc/passwd") is None
    assert store.get_workflow("cw_ZZZZ") is None
    assert store.get_workflow("not_an_id") is None
    assert store.get_workflow("cw_deadbeef") is None  # well-formed but absent


def test_store_save_rejects_empty_name():
    payload, _ = cga.validate_and_expand(_linear_graph())
    with pytest.raises(ValueError):
        store.save_workflow("   ", payload)


# ---------------------------------------------------------------------------
# Registry tools
# ---------------------------------------------------------------------------

def test_run_canvas_graph_happy_path():
    registry = get_tool_registry()
    result = registry.execute(
        "run_canvas_graph",
        {"title": "Loss lens", "graph": _linear_graph(), "motivation": "to see the tree as memory"},
    )
    assert result.startswith("Apparatus 'Loss lens' validated")


def test_run_canvas_graph_error_path():
    registry = get_tool_registry()
    result = registry.execute(
        "run_canvas_graph",
        {"title": "Bad", "graph": {"nodes": [{"id": "x", "type": "frobnicate"}]}},
    )
    assert result.startswith("Error:")


def test_run_canvas_graph_requires_title():
    registry = get_tool_registry()
    result = registry.execute("run_canvas_graph", {"graph": _linear_graph()})
    assert result.startswith("Error:")


def test_canvas_graph_library_save_list_get_via_registry():
    registry = get_tool_registry()
    payload_graph = _linear_graph()

    saved = registry.execute(
        "canvas_graph_library",
        {
            "action": "save",
            "title": "Kept lens",
            "graph": payload_graph,
            "description": "worth returning to",
            "application_type": "verwandlung",
            "memo": "why I kept it",
        },
    )
    assert saved.startswith("Kept strategy 'Kept lens'")
    assert "version 1" in saved
    assert "verwandlung" in saved

    listed = registry.execute("canvas_graph_library", {"action": "list"})
    assert "Kept lens" in listed
    assert "verwandlung" in listed

    # application_type filter through the tool
    filtered = registry.execute(
        "canvas_graph_library", {"action": "list", "application_type": "einstieg"}
    )
    assert "No strategies kept yet" in filtered

    # extract the minted id from the store to fetch it back
    wid = store.list_strategies()[0]["id"]
    got = registry.execute("canvas_graph_library", {"action": "get", "workflow_id": wid})
    assert got.startswith(f"Strategy 'Kept lens' ({wid})")
    assert "run_canvas_graph" in got
    assert "v1" in got


def test_canvas_graph_library_bad_action():
    registry = get_tool_registry()
    result = registry.execute("canvas_graph_library", {"action": "frobnicate"})
    assert result.startswith("Error:")


def test_canvas_graph_library_save_rejects_invalid_graph():
    registry = get_tool_registry()
    result = registry.execute(
        "canvas_graph_library",
        {"action": "save", "name": "Bad", "graph": {"nodes": [{"id": "x", "type": "nope"}]}},
    )
    assert result.startswith("Error:")


def test_canvas_graph_library_get_missing():
    registry = get_tool_registry()
    result = registry.execute("canvas_graph_library", {"action": "get", "workflow_id": "cw_deadbeef"})
    assert result.startswith("Error:")


# ---------------------------------------------------------------------------
# Prompt + config-file integrity
# ---------------------------------------------------------------------------

def test_resona_core_prompt_teaches_building_apparatus():
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT
    assert "BUILDING APPARATUS" in RESONA_CORE_PROMPT
    assert "run_canvas_graph" in RESONA_CORE_PROMPT
    assert "canvas_graph_library" in RESONA_CORE_PROMPT


def test_all_canvas_configs_have_a_file_on_disk():
    # devserver/tests/… -> parents[1] == devserver/
    configs_dir = Path(__file__).resolve().parents[1] / "schemas" / "configs" / "output"
    present = {p.stem for p in configs_dir.glob("*.json")}
    missing = [cid for cid in cga.RESONA_CANVAS_CONFIGS if cid not in present]
    assert not missing, f"RESONA_CANVAS_CONFIGS with no output config file: {missing}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


def test_generation_to_comparison_rejected_with_teaching_hint():
    """The executor does not propagate images to comparison_evaluator; the
    validator must fail loudly and point at image_evaluation (live-smoke
    finding 2026-07-03: the cmp node silently never ran)."""
    from my_app.services.canvas_graph_authoring import validate_and_expand

    graph = {
        "nodes": [
            {"id": "i", "type": "input", "promptText": "x"},
            {"id": "g", "type": "generation", "configId": "sd35_large"},
            {"id": "c", "type": "comparison_evaluator", "comparisonCriteria": "y"},
        ],
        "connections": [
            {"sourceId": "i", "targetId": "g"},
            {"sourceId": "g", "targetId": "c"},
        ],
    }
    payload, err = validate_and_expand(graph)
    assert payload is None
    assert "image_evaluation" in err


def test_image_evaluation_bridge_to_comparison_is_valid():
    """generation -> image_evaluation (vision read) -> comparison_evaluator."""
    from my_app.services.canvas_graph_authoring import validate_and_expand, summarize_graph

    graph = {
        "nodes": [
            {"id": "i", "type": "input", "promptText": "x"},
            {"id": "la", "type": "interception", "contextPrompt": "lens a"},
            {"id": "lb", "type": "interception", "contextPrompt": "lens b"},
            {"id": "ga", "type": "generation", "configId": "sd35_large"},
            {"id": "gb", "type": "generation", "configId": "surrealization"},
            {"id": "ra", "type": "image_evaluation", "imageEvaluationPrompt": "read a"},
            {"id": "rb", "type": "image_evaluation", "imageEvaluationPrompt": "read b"},
            {"id": "c", "type": "comparison_evaluator", "comparisonCriteria": "compare"},
        ],
        "connections": [
            {"sourceId": "i", "targetId": "la"},
            {"sourceId": "i", "targetId": "lb"},
            {"sourceId": "la", "targetId": "ga"},
            {"sourceId": "lb", "targetId": "gb"},
            {"sourceId": "ga", "targetId": "ra"},
            {"sourceId": "gb", "targetId": "rb"},
            {"sourceId": "ra", "targetId": "c"},
            {"sourceId": "rb", "targetId": "c"},
        ],
    }
    payload, err = validate_and_expand(graph)
    assert err is None, err
    assert "image_evaluation" in summarize_graph(payload)


def test_text_may_not_enter_image_evaluation():
    from my_app.services.canvas_graph_authoring import validate_and_expand

    graph = {
        "nodes": [
            {"id": "i", "type": "input", "promptText": "x"},
            {"id": "r", "type": "image_evaluation"},
        ],
        "connections": [{"sourceId": "i", "targetId": "r"}],
    }
    payload, err = validate_and_expand(graph)
    assert payload is None
    assert "may not connect" in err


# ---------------------------------------------------------------------------
# Strategy repertoire — tool actions revise / feedback + get(version)
# ---------------------------------------------------------------------------

def _save_via_tool(registry, title="Rep strat", application_type="reihe"):
    registry.execute(
        "canvas_graph_library",
        {
            "action": "save",
            "title": title,
            "graph": _linear_graph(),
            "description": "a repertoire strategy",
            "application_type": application_type,
        },
    )
    return store.list_strategies()[0]["id"]


def test_tool_revise_happy_and_errors():
    registry = get_tool_registry()
    sid = _save_via_tool(registry)

    # happy: adds v2
    ok = registry.execute(
        "canvas_graph_library",
        {"action": "revise", "workflow_id": sid, "graph": _linear_graph(config_id="flux2"),
         "memo": "swapped the generator"},
    )
    assert "revised to version 2" in ok
    assert "memo noted" in ok
    assert store.get_strategy(sid)["versions"][-1]["version"] == 2

    # error: revise without memo
    e1 = registry.execute(
        "canvas_graph_library",
        {"action": "revise", "workflow_id": sid, "graph": _linear_graph()},
    )
    assert e1.startswith("Error:") and "memo" in e1

    # error: revise unknown id
    e2 = registry.execute(
        "canvas_graph_library",
        {"action": "revise", "workflow_id": "cw_deadbeef", "graph": _linear_graph(),
         "memo": "x"},
    )
    assert e2.startswith("Error:")

    # error: revise with invalid graph
    e3 = registry.execute(
        "canvas_graph_library",
        {"action": "revise", "workflow_id": sid,
         "graph": {"nodes": [{"id": "x", "type": "nope"}]}, "memo": "x"},
    )
    assert e3.startswith("Error:")


def test_tool_feedback_happy_and_errors():
    registry = get_tool_registry()
    sid = _save_via_tool(registry)
    store.add_version(sid, _linear_graph(), memo="v2")

    # happy: default latest (v2)
    ok = registry.execute(
        "canvas_graph_library",
        {"action": "feedback", "workflow_id": sid, "note": "the room lit up"},
    )
    assert ok.startswith("Feedback noted on 'Rep strat' v2")

    # happy: explicit version 1
    ok2 = registry.execute(
        "canvas_graph_library",
        {"action": "feedback", "workflow_id": sid, "note": "v1 was flatter", "version": 1},
    )
    assert "v1" in ok2
    v1 = next(v for v in store.get_strategy(sid)["versions"] if v["version"] == 1)
    assert v1["feedback"][0]["note"] == "v1 was flatter"

    # error: feedback without note
    e1 = registry.execute(
        "canvas_graph_library", {"action": "feedback", "workflow_id": sid}
    )
    assert e1.startswith("Error:") and "note" in e1

    # error: feedback unknown id
    e2 = registry.execute(
        "canvas_graph_library",
        {"action": "feedback", "workflow_id": "cw_deadbeef", "note": "x"},
    )
    assert e2.startswith("Error:")


def test_tool_get_with_version_returns_that_workflow():
    registry = get_tool_registry()
    sid = _save_via_tool(registry)  # v1 uses sd35_large
    store.add_version(sid, _linear_graph(config_id="flux2"), memo="to flux2")

    got_v1 = registry.execute(
        "canvas_graph_library", {"action": "get", "workflow_id": sid, "version": 1}
    )
    assert '"configId": "sd35_large"' in got_v1
    assert '"configId": "flux2"' not in got_v1.split("run_canvas_graph", 1)[1]

    got_latest = registry.execute(
        "canvas_graph_library", {"action": "get", "workflow_id": sid}
    )
    assert '"configId": "flux2"' in got_latest


def test_tool_save_requires_title():
    registry = get_tool_registry()
    e = registry.execute(
        "canvas_graph_library", {"action": "save", "graph": _linear_graph()}
    )
    assert e.startswith("Error:") and "title" in e


# ---------------------------------------------------------------------------
# Prompt: NACHKLAPP block + situation routing
# ---------------------------------------------------------------------------

def test_resona_nachklapp_block_exists():
    from my_app.routes import chat_routes
    assert hasattr(chat_routes, "RESONA_NACHKLAPP_BLOCK")
    assert "NACHKLAPP" in chat_routes.RESONA_NACHKLAPP_BLOCK


def test_prompt_routes_nachklapp():
    from my_app.routes.chat_routes import build_system_prompt

    p = build_system_prompt(
        {"resona_mode": True, "resona_situation": "nachklapp", "device_id": "test-nk"},
        "de",
    )
    assert "NACHKLAPP" in p
    assert "THE WORKSHOP SITUATION" not in p
    assert "THE PLANNING SITUATION" not in p


def test_prompt_workshop_and_consulting_still_route():
    from my_app.routes.chat_routes import build_system_prompt

    w = build_system_prompt(
        {"resona_mode": True, "device_id": "test-nk-w"}, "de"
    )
    assert "THE WORKSHOP SITUATION" in w
    assert "NACHKLAPP" not in w

    c = build_system_prompt(
        {"resona_mode": True, "resona_situation": "consulting", "device_id": "test-nk-c"},
        "de",
    )
    assert "THE PLANNING SITUATION" in c
    assert "NACHKLAPP" not in c


def test_building_apparatus_mentions_repertoire():
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT
    assert "grown repertoire" in RESONA_CORE_PROMPT


# ---------------------------------------------------------------------------
# Gegenmaßnahmen 2026-07-16: Instrumenten-Treue + Methode + fail-closed
# ---------------------------------------------------------------------------

def _two_gen_graph(**extra_by_id):
    """input -> tr -> 2x generation (comparison shape). extra_by_id lets a test
    put inline keys on gn1/gn2."""
    gn1 = {"id": "gn1", "type": "generation", "configId": "sd35_large"}
    gn2 = {"id": "gn2", "type": "generation", "configId": "sd35_large"}
    gn1.update(extra_by_id.get("gn1", {}))
    gn2.update(extra_by_id.get("gn2", {}))
    return {
        "nodes": [
            {"id": "in1", "type": "input", "promptText": "a tree"},
            {"id": "tr1", "type": "translation"},
            gn1,
            gn2,
        ],
        "connections": [
            {"sourceId": "in1", "targetId": "tr1"},
            {"sourceId": "tr1", "targetId": "gn1"},
            {"sourceId": "tr1", "targetId": "gn2"},
        ],
    }


def test_two_unseeded_generations_share_one_seed():
    payload, err = cga.validate_and_expand(_two_gen_graph())
    assert err is None
    seed_nodes = [n for n in payload["nodes"] if n["type"] == "seed"]
    assert len(seed_nodes) == 1
    assert seed_nodes[0]["seedMode"] == "fixed"
    sid = seed_nodes[0]["id"]
    targets = sorted(
        c["targetId"] for c in payload["connections"] if c["sourceId"] == sid
    )
    assert targets == ["gn1", "gn2"]


def test_explicit_seed_disables_shared_seed():
    payload, err = cga.validate_and_expand(_two_gen_graph(gn1={"seed": 42}))
    assert err is None
    seed_nodes = [n for n in payload["nodes"] if n["type"] == "seed"]
    # only the explicit seed node for gn1; no auto-shared seed appears
    assert len(seed_nodes) == 1
    assert seed_nodes[0]["seedValue"] == 42


def test_single_generation_gets_no_shared_seed():
    payload, err = cga.validate_and_expand(_linear_graph())
    assert err is None
    assert not [n for n in payload["nodes"] if n["type"] == "seed"]


def test_interception_config_id_accepted(monkeypatch):
    monkeypatch.setattr(cga, "_interception_config_ids", lambda: {"bauhaus"})
    g = _linear_graph()
    g["nodes"][1] = {"id": "ic1", "type": "interception", "configId": "bauhaus"}
    payload, err = cga.validate_and_expand(g)
    assert err is None
    ic = next(n for n in payload["nodes"] if n["type"] == "interception")
    assert ic["configId"] == "bauhaus"


def test_interception_unknown_config_id_rejected(monkeypatch):
    monkeypatch.setattr(cga, "_interception_config_ids", lambda: {"bauhaus"})
    g = _linear_graph()
    g["nodes"][1] = {"id": "ic1", "type": "interception", "configId": "nope"}
    payload, err = cga.validate_and_expand(g)
    assert payload is None
    assert "unknown configId" in err


def test_interception_config_id_and_context_prompt_conflict():
    g = _linear_graph()
    g["nodes"][1] = {
        "id": "ic1", "type": "interception",
        "configId": "bauhaus", "contextPrompt": "also a paraphrase",
    }
    payload, err = cga.validate_and_expand(g)
    assert payload is None
    assert "not both" in err


def test_interception_without_lens_rejected():
    g = _linear_graph()
    g["nodes"][1] = {"id": "ic1", "type": "interception"}
    payload, err = cga.validate_and_expand(g)
    assert payload is None
    assert "needs a lens" in err


def test_summarize_graph_shows_lens_config():
    g = _linear_graph()
    g["nodes"][1] = {"id": "ic1", "type": "interception", "configId": "bauhaus"}
    import unittest.mock as um
    with um.patch.object(cga, "_interception_config_ids", lambda: {"bauhaus"}):
        payload, err = cga.validate_and_expand(g)
    assert err is None
    assert "lens:bauhaus" in cga.summarize_graph(payload)


def test_load_interception_context_real_config():
    from my_app.services.canvas_executor import _load_interception_context
    ctx, err = _load_interception_context("bauhaus", "de")
    assert err is None
    # "Aufgabe" allein: der Name der Perspektive steht auch in der englischen
    # Fassung, und ein oder darauf laesst eine Antwort in falscher Sprache durch.
    assert "Aufgabe" in ctx
    ctx_en, err_en = _load_interception_context("bauhaus", None)
    assert err_en is None and ctx_en
    _, err_unknown = _load_interception_context("does_not_exist_xyz", None)
    assert err_unknown and "unknown" in err_unknown


def test_comparison_evaluator_refuses_empty_input():
    from unittest.mock import MagicMock
    from my_app.services.canvas_executor import CanvasWorkflowExecutor

    nodes = [
        {"id": "r1", "type": "image_evaluation"},
        {"id": "r2", "type": "image_evaluation"},
        {"id": "cmp", "type": "comparison_evaluator", "comparisonCriteria": "compare"},
    ]
    connections = [
        {"sourceId": "r1", "targetId": "cmp"},
        {"sourceId": "r2", "targetId": "cmp"},
    ]
    ex = CanvasWorkflowExecutor(
        nodes=nodes, connections=connections,
        recorder=MagicMock(), run_id="run_test", engine=MagicMock(),
    )
    out, dtype, meta = ex._execute_comparison_evaluator(
        nodes[2], "cmp", "", source_node_id="r1", connection_label=None
    )
    assert out == ""
    assert ex.results["cmp"]["error"]
    assert "refused" in ex.results["cmp"]["error"]
    # the engine was never asked to confabulate anything
    ex.engine.process_request.assert_not_called()


def test_canvas_vision_falls_back_to_the_configured_role():
    """An image_evaluation node that names no model reads the platform's
    IMAGE_ANALYSIS_MODEL, never a name written into the code.

    The original of this test (2026-07-16) pinned one literal against another:
    a dead 'llama3.2-vision:latest' default had produced 'Unknown model' 500s
    and fed empty readings into comparisons, and the fix at the time was a
    different literal. The platform has since forbidden model names in code
    outright (test_no_model_literals.py) and the default became the configured
    role, which is what this asserts now — the same guarantee, one layer up:
    a role an installation sets and _check_required_models refuses to boot
    without."""
    import inspect
    from my_app.services import canvas_executor as ce
    src = inspect.getsource(ce.CanvasWorkflowExecutor._execute_image_evaluation)
    assert "node.get('visionModel') or config.IMAGE_ANALYSIS_MODEL" in src
    # The old shape, a literal as the second argument, is what this forbids.
    assert "node.get('visionModel'," not in src


def test_view_run_registered_and_fails_closed():
    reg = get_tool_registry()
    result = reg.execute("view_run", {"run_id": "run_does_not_exist_xyz"}, context=None)
    assert result.startswith("Error")
    bad = reg.execute("view_run", {"run_id": "../../etc/passwd"}, context=None)
    assert bad.startswith("Error")


def test_core_prompt_perception_and_grounding_rules():
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT
    assert "view_run" in RESONA_CORE_PROMPT
    assert "expert's confidence" not in RESONA_CORE_PROMPT
    assert "read_knowledge" in RESONA_CORE_PROMPT
    assert "SHARED LANGUAGE" in RESONA_CORE_PROMPT


def test_fach_kompass_composes_into_resona_prompt():
    from my_app.routes.chat_routes import build_system_prompt, RESONA_FACH_KOMPASS
    assert RESONA_FACH_KOMPASS, "fachlicher_kompass.md missing or empty"
    p = build_system_prompt({"resona_mode": True, "device_id": "test-fk"}, "de")
    assert "WORKING POSITION" in p


def test_planning_block_receives_before_proposing():
    """No unasked finished plans, no pseudo-question batteries, no empty
    caveats: the educator's artistic-pedagogical idea is the axis."""
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT, RESONA_PLANNING_BLOCK

    # planning: receive first; the educator's idea is the axis
    assert "the educator's own artistic-pedagogical idea" in RESONA_PLANNING_BLOCK
    assert "First movement: receive" in RESONA_PLANNING_BLOCK
    assert "never as an opening bid" in RESONA_PLANNING_BLOCK
    # the old commands that produced instant unasked plans are gone
    assert "Never open with questions" not in RESONA_PLANNING_BLOCK
    assert "Propose first" not in RESONA_PLANNING_BLOCK
    # questions are earned; substance is read, not conjured
    assert "Substance is read, not conjured" in RESONA_PLANNING_BLOCK
    # a battery of clarifying questions is deferral, not listening
    assert "is not listening; it is deferral" in RESONA_PLANNING_BLOCK
    # core: turns open rather than close; caveats need a named mechanism;
    # reading beats disclaiming
    assert "opens more than it closes" in RESONA_CORE_PROMPT
    assert "naming its mechanism" in RESONA_CORE_PROMPT
    assert "not to disclaim" in RESONA_CORE_PROMPT


def test_no_prefabricated_categories_offered():
    """Offering binary alternatives prescribes the categories a
    decision is taken in. That framing belongs to the counterpart; supplying it
    pre-empts the thinking that would have drawn the distinction. The prompt
    must carry this as a disposition, not only as a banned sentence form.

    Prompt text is hard-wrapped, so every check runs on whitespace-normalised
    text - a reflow must not silently disarm this test.

    Each assertion guards a DETERMINATION, named in the comment above it,
    never a particular draft's wording. When the prompt is rewritten,
    the string moves to whatever sentence now carries that determination. A
    test that freezes phrasing turns into the accretion mechanism it was meant
    to guard against; it did exactly that with the agent-coined "costume"
    metaphor, which has no referent on this platform and is gone.
    """
    from my_app.routes.chat_routes import (
        RESONA_CORE_PROMPT,
        RESONA_PLANNING_BLOCK,
        RESONA_WORKSHOP_BLOCK,
    )

    def flat(text):
        return " ".join(text.split())

    core = flat(RESONA_CORE_PROMPT)
    planning = flat(RESONA_PLANNING_BLOCK)
    workshop = flat(RESONA_WORKSHOP_BLOCK)

    # disposition: the people draw the lines, and the drawing is the thinking
    assert "the making is the thinking" in core
    # a line drawn out loud forecloses the thinking that would have drawn it
    assert "it cannot be unseen" in core
    # say what is there; do not pre-sort it into a structure
    assert "describe, do not structure" in core

    # consequence: service question and offered either-or are both banned
    assert "drawing the categories of a decision is the decision" in core
    assert "open means it names no options" in core

    # the instructions that COMMANDED the move are gone from every block
    assert "sharpens a decision" not in core
    assert "turn an accident into a choice" not in core
    assert "Sharpen the decision" not in workshop

    # planning: framing belongs to the educator, not only the pick
    assert "its framing no less than its outcome" in planning
    assert "never laid out to be picked from" in planning

    # prompts are English; no German example sentences
    for name, block in (("core", core), ("planning", planning), ("workshop", workshop)):
        for german in ("Soll ich", "Wollt ihr", "eher A oder B", "Reizt dich"):
            assert german not in block, f"German example sentence in {name}: {german}"
