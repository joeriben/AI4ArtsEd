#!/usr/bin/env python3
"""Every apparatus Resona authors is written down, and what is written opens.

Because apparatus runs kept failing to appear, every allegedly built run is
exported, in a format the Canvas can import, so that a
run missing from the board can be told apart from a run that was never built.

The accepted file is a CanvasWorkflow — the shape canvasStore.loadWorkflow reads
(public/ai4artsed-frontend/src/types/canvas.ts). That the Canvas actually opens
one of these files is asserted on the other side, against a fixture written by
this very code: public/ai4artsed-frontend/src/views/__tests__/canvas_import.spec.ts.

Run:  python3 -m pytest devserver/tests/test_canvas_graph_export.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import canvas_graph_export as cge
from my_app.services.canvas_graph_authoring import (
    RESONA_CANVAS_CONFIGS, summarize_graph, to_canvas_workflow, validate_and_expand,
)

CFG = sorted(RESONA_CANVAS_CONFIGS)[0]

# Two generations off one input, each behind its own lens, read by one comparison:
# the shape an apparatus takes when it is a comparison, and the shape that shows
# whether the layout puts a waiting node behind everything it waits for.
GRAPH = {
    "nodes": [
        {"id": "in", "type": "input", "promptText": "ein Haus am Feldrand"},
        {"id": "lens", "type": "interception", "contextPrompt": "Sieh es als Ort."},
        {"id": "genA", "type": "generation", "configId": CFG, "seed": 7},
        {"id": "genB", "type": "generation", "configId": CFG, "seed": 7},
        {"id": "readA", "type": "image_evaluation", "imageEvaluationPrompt": "Was steht da?"},
        {"id": "readB", "type": "image_evaluation", "imageEvaluationPrompt": "Was steht da?"},
        {"id": "cmp", "type": "comparison_evaluator", "comparisonCriteria": "Was trennt sie?"},
    ],
    "connections": [
        {"sourceId": "in", "targetId": "lens"},
        {"sourceId": "lens", "targetId": "genA"},
        {"sourceId": "in", "targetId": "genB"},
        {"sourceId": "genA", "targetId": "readA"},
        {"sourceId": "genB", "targetId": "readB"},
        {"sourceId": "readA", "targetId": "cmp"},
        {"sourceId": "readB", "targetId": "cmp"},
    ],
}


@pytest.fixture
def payload():
    p, err = validate_and_expand(GRAPH)
    assert err is None, err
    return p


@pytest.fixture
def models_configured(monkeypatch):
    """The platform's model roles, as an installation has them.

    config.py ships them empty on purpose — the values live in
    user_settings.json and reload_user_settings() writes them at startup, and a
    server whose roles are blank refuses to boot (_check_required_models,
    my_app/__init__.py). A bare pytest process never boots, so the roles are
    blank here and have to be set for the tests that ask what the file names.
    The values are deliberately not real model names.
    """
    import config
    monkeypatch.setattr(config, "STAGE2_INTERCEPTION_MODEL", "test/thinking-role", raising=False)
    monkeypatch.setattr(config, "STAGE3_MODEL", "test/translation-role", raising=False)
    monkeypatch.setattr(config, "IMAGE_ANALYSIS_MODEL", "test/seeing-role", raising=False)


@pytest.fixture
def here(tmp_path, monkeypatch):
    monkeypatch.setattr(cge, "EXPORT_DIR", tmp_path / "runs")
    monkeypatch.setattr(cge, "REJECTED_DIR", tmp_path / "runs" / "rejected")
    return tmp_path


def test_every_node_has_a_place_on_the_board(payload):
    """CanvasNode declares x, y and config non-optional; a node short of one of
    them renders at `left: undefinedpx` and the graph arrives as a heap."""
    wf = to_canvas_workflow(payload, name="Perspektive gegen Rohtext")
    assert wf["nodes"], "the expansion produced no nodes"
    for n in wf["nodes"]:
        assert isinstance(n["x"], int), n
        assert isinstance(n["y"], int), n
        assert isinstance(n["config"], dict), n


def test_the_envelope_is_the_one_the_canvas_reads(payload):
    wf = to_canvas_workflow(payload, name="Perspektive gegen Rohtext",
                            description="zwei Wege auf dasselbe Motiv")
    assert wf["type"] == "canvas_workflow"
    assert wf["name"] == "Perspektive gegen Rohtext"
    assert wf["description"] == "zwei Wege auf dasselbe Motiv"
    assert isinstance(wf["id"], str) and wf["id"]
    assert wf["createdAt"] and wf["updatedAt"]


def test_no_edge_points_backwards(payload):
    """Every node stands behind everything it waits for — the longest path, so a
    node fed by two chains of unequal length clears both."""
    wf = to_canvas_workflow(payload, name="x")
    x = {n["id"]: n["x"] for n in wf["nodes"]}
    for c in wf["connections"]:
        assert x[c["sourceId"]] < x[c["targetId"]], c


def test_nodes_in_one_column_do_not_sit_on_each_other(payload):
    wf = to_canvas_workflow(payload, name="x")
    spots = [(n["x"], n["y"]) for n in wf["nodes"]]
    assert len(set(spots)) == len(spots)


def test_the_authored_fields_travel_untouched(payload):
    wf = to_canvas_workflow(payload, name="x")
    by_id = {n["id"]: n for n in wf["nodes"]}
    assert by_id["in"]["promptText"] == "ein Haus am Feldrand"
    assert by_id["lens"]["contextPrompt"] == "Sieh es als Ort."
    assert by_id["genA"]["configId"] == CFG
    assert by_id["cmp"]["comparisonCriteria"] == "Was trennt sie?"
    # The seed became a source node during expansion and keeps its Canvas keys.
    seeds = [n for n in wf["nodes"] if n["type"] == "seed"]
    assert seeds and all(s["seedMode"] == "fixed" and s["seedValue"] == 7 for s in seeds)


def test_an_accepted_apparatus_is_written_as_a_workflow(here, payload):
    path = cge.record_accepted("Perspektive gegen Rohtext", payload,
                               motivation="zwei Wege", summary="input -> generation",
                               intent_id="gi_deadbeef", device_id="dev-1")
    assert path is not None and path.exists()
    wf = json.loads(path.read_text(encoding="utf-8"))
    assert wf["type"] == "canvas_workflow"
    assert wf["id"] == "gi_deadbeef"
    assert all("x" in n and "y" in n for n in wf["nodes"])
    assert wf["resona"]["device_id"] == "dev-1"


def test_a_refused_apparatus_is_written_too(here):
    """The model reached for the tool and was refused. That is a third case, and
    a room that sees no run has to be able to tell it from the other two."""
    path = cge.record_rejected("Kaputter Apparat", {"nodes": []},
                               "graph.nodes must be a non-empty list of node objects.")
    assert path is not None and path.exists()
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["error"].startswith("graph.nodes")
    assert body["authored_graph"] == {"nodes": []}
    # Deliberately not a workflow: there is nothing to import.
    assert "type" not in body


def test_a_write_that_fails_never_breaks_the_turn(payload, monkeypatch):
    monkeypatch.setattr(cge, "EXPORT_DIR", Path("/proc/nonexistent/nope"))
    assert cge.record_accepted("x", payload) is None


# ---------------------------------------------------------------------------
# What the Canvas needs before it will run the file again
# ---------------------------------------------------------------------------

def _canvas_errors(wf):
    """canvasStore.validationErrors, in Python.

    Kept beside the original (public/ai4artsed-frontend/src/stores/canvas.ts,
    isWorkflowValid / validationErrors) because that is the gate the imported
    file meets: every one of these leaves Run and Batch disabled.
    """
    nodes = wf["nodes"]
    errs = []
    kinds = [n.get("type") for n in nodes]
    if "input" not in kinds and "image_input" not in kinds and "random_prompt" not in kinds:
        errs.append("Missing source node")
    if "collector" not in kinds:
        errs.append("Missing collector node")
    for n in nodes:
        t = n.get("type")
        if t == "generation" and not n.get("configId"):
            errs.append("Generation node missing output config")
        if t in ("interception", "translation") and not n.get("llmModel"):
            errs.append(f"{t} node needs LLM selection")
        if t == "image_evaluation" and not n.get("visionModel"):
            errs.append("Image Analysis node needs Vision model selection")
        if t == "random_prompt" and not (n.get("randomPromptModel") and n.get("randomPromptPreset")):
            errs.append("Random Prompt node needs LLM and preset")
        if t == "image_input" and not (n.get("imageData") or {}).get("image_path"):
            errs.append("Image Input node needs image upload")
    return errs


def test_the_imported_apparatus_is_one_the_canvas_will_run(payload, models_configured):
    """Openable is not enough. An apparatus that imports with a dead Run button
    is a picture of a run, and the room cannot do anything with a picture."""
    wf = to_canvas_workflow(payload, name="Perspektive gegen Rohtext")
    assert _canvas_errors(wf) == []


def test_one_collector_gathers_the_ends_and_the_images(payload):
    wf = to_canvas_workflow(payload, name="x")
    cols = [n for n in wf["nodes"] if n["type"] == "collector"]
    assert len(cols) == 1
    cid = cols[0]["id"]
    feeding = {c["sourceId"] for c in wf["connections"] if c["targetId"] == cid}
    # the comparison is where this apparatus ends, and both pictures are in it
    assert "cmp" in feeding
    assert {"genA", "genB"} <= feeding
    # a reading is not an end: it feeds the comparison
    assert "readA" not in feeding and "readB" not in feeding


def test_the_collector_is_never_fed_by_a_parameter(payload):
    """A seed reaches generation and nothing else (canvas_executor accepts_seed),
    so an edge from it to the collector would be a line on the board that
    carries nothing."""
    wf = to_canvas_workflow(payload, name="x")
    kind = {n["id"]: n["type"] for n in wf["nodes"]}
    cid = next(n["id"] for n in wf["nodes"] if n["type"] == "collector")
    for c in wf["connections"]:
        if c["targetId"] == cid:
            assert kind[c["sourceId"]] not in ("seed", "resolution", "quality"), c


def test_an_authored_collector_is_not_doubled():
    graph = {
        "nodes": [
            {"id": "in", "type": "input", "promptText": "ein Haus"},
            {"id": "lens", "type": "interception", "contextPrompt": "Sieh es als Ort."},
        ],
        "connections": [{"sourceId": "in", "targetId": "lens"}],
    }
    p, err = validate_and_expand(graph)
    assert err is None, err
    p["nodes"].append({"id": "collector", "type": "collector"})
    p["connections"].append({"sourceId": "lens", "targetId": "collector"})
    wf = to_canvas_workflow(p, name="x")
    assert len([n for n in wf["nodes"] if n["type"] == "collector"]) == 1


def test_a_text_only_apparatus_gets_its_collector_too(models_configured):
    graph = {
        "nodes": [
            {"id": "in", "type": "input", "promptText": "ein Haus"},
            {"id": "lens", "type": "interception", "contextPrompt": "Sieh es als Ort."},
        ],
        "connections": [{"sourceId": "in", "targetId": "lens"}],
    }
    p, err = validate_and_expand(graph)
    assert err is None, err
    wf = to_canvas_workflow(p, name="x")
    assert _canvas_errors(wf) == []


def test_every_thinking_node_names_the_model_it_ran_on(payload, models_configured):
    """The executor reads the platform setting when a node names no model; the
    Canvas refuses to run a node that names none. So the file names the one the
    executor would have read — the same value, from the same function."""
    from my_app.services.canvas_executor import _configured_canvas_model
    wf = to_canvas_workflow(payload, name="x")
    by_id = {n["id"]: n for n in wf["nodes"]}
    assert by_id["lens"]["llmModel"] == _configured_canvas_model("STAGE2_INTERCEPTION_MODEL")
    assert by_id["cmp"]["comparisonLlmModel"] == _configured_canvas_model("STAGE2_INTERCEPTION_MODEL")
    assert by_id["readA"]["visionModel"] == _configured_canvas_model("IMAGE_ANALYSIS_MODEL")


def test_a_model_the_room_named_itself_is_left_alone():
    graph = {
        "nodes": [
            {"id": "in", "type": "input", "promptText": "ein Haus"},
            {"id": "lens", "type": "interception", "contextPrompt": "Als Ort.",
             "llmModel": "some/model-the-room-picked"},
        ],
        "connections": [{"sourceId": "in", "targetId": "lens"}],
    }
    p, err = validate_and_expand(graph)
    assert err is None, err
    wf = to_canvas_workflow(p, name="x")
    lens = next(n for n in wf["nodes"] if n["id"] == "lens")
    assert lens["llmModel"] == "some/model-the-room-picked"


def test_an_authored_question_is_not_hidden_behind_a_framework(payload):
    """StageModule shows the question field only for the preset 'custom' and
    otherwise prints a framework name. A node carrying a question and no preset
    would open claiming a framework it does not run."""
    wf = to_canvas_workflow(payload, name="x")
    read = next(n for n in wf["nodes"] if n["id"] == "readA")
    assert read["imageEvaluationPreset"] == "custom"
    assert read["imageEvaluationPrompt"] == "Was steht da?"


def test_a_framework_the_room_chose_stays_the_framework():
    graph = {
        "nodes": [
            {"id": "in", "type": "input", "promptText": "ein Haus"},
            {"id": "gen", "type": "generation", "configId": CFG},
            {"id": "read", "type": "image_evaluation",
             "imageEvaluationPreset": "bildwissenschaftlich",
             "imageEvaluationPrompt": "Was steht da?"},
        ],
        "connections": [
            {"sourceId": "in", "targetId": "gen"},
            {"sourceId": "gen", "targetId": "read"},
        ],
    }
    p, err = validate_and_expand(graph)
    assert err is None, err
    wf = to_canvas_workflow(p, name="x")
    read = next(n for n in wf["nodes"] if n["id"] == "read")
    assert read["imageEvaluationPreset"] == "bildwissenschaftlich"


def test_the_two_readings_arrive_at_numbered_inputs(payload):
    """CanvasWorkspace routes a comparison's incoming edges by these labels;
    unlabelled, both land on the same point and the numbered connectors read as
    unconnected."""
    wf = to_canvas_workflow(payload, name="x")
    into_cmp = [c for c in wf["connections"] if c["targetId"] == "cmp"]
    assert sorted(c["label"] for c in into_cmp) == ["input-1", "input-2"]


# ---------------------------------------------------------------------------
# One authoring, one file
# ---------------------------------------------------------------------------

def test_two_apparatus_in_the_same_second_are_two_files(here, payload):
    """A round runs its tool calls in a tight loop and the stamp resolves to the
    whole second, so this is the ordinary path, not a contrived one."""
    a = cge.record_accepted("Gleicher Titel", payload, intent_id="gi_aaaaaaaa")
    b = cge.record_accepted("Gleicher Titel", payload, intent_id="gi_bbbbbbbb")
    assert a and b and a != b
    assert len(list(cge.EXPORT_DIR.glob("*.json"))) == 2


def test_two_refusals_in_the_same_second_are_two_files(here):
    """Here the whole content of the file is the reason, so an overwrite loses
    the first reason entirely."""
    a = cge.record_rejected("Kaputt", {"nodes": []}, "erster Grund")
    b = cge.record_rejected("Kaputt", {"nodes": []}, "zweiter Grund")
    assert a and b and a != b
    reasons = {json.loads(p.read_text(encoding="utf-8"))["error"]
               for p in cge.REJECTED_DIR.glob("*.json")}
    assert reasons == {"erster Grund", "zweiter Grund"}


def test_a_title_in_another_script_still_names_its_own_file(here, payload):
    """This platform ships uk and ko. Stripping to [a-z0-9] collapsed every
    Cyrillic, Korean, Greek and Chinese title into the same word."""
    a = cge.record_accepted("빛과 그림자", payload, intent_id="gi_11111111")
    b = cge.record_accepted("Світло і тінь", payload, intent_id="gi_22222222")
    assert a and b and a.name != b.name
    assert "빛과" in a.name and "світло" in b.name


def test_a_title_of_only_punctuation_still_gets_a_name(here, payload):
    p = cge.record_accepted("!!! ??? ...", payload, intent_id="gi_33333333")
    assert p and "apparatus" in p.name


def test_a_long_title_is_cut_and_the_files_stay_apart(here, payload):
    """48 characters of title, and two titles that agree over the first 48 are
    a real case — a room names its variants by their tail."""
    stem = "ein sehr langer titel der die ganze absicht des apparats benennt"
    a = cge.record_accepted(stem + " Variante A", payload, intent_id="gi_44444444")
    b = cge.record_accepted(stem + " Variante B", payload, intent_id="gi_55555555")
    assert a and b and a.name != b.name
    assert len(cge._slug(stem + " Variante A")) <= 48


# ---------------------------------------------------------------------------
# The tool: one expansion, handed over once
# ---------------------------------------------------------------------------

_TWO_GENERATIONS = {
    "nodes": [
        {"id": "in", "type": "input", "promptText": "ein Haus am Feldrand"},
        {"id": "lens", "type": "interception", "contextPrompt": "Sieh es als Ort."},
        {"id": "genA", "type": "generation", "configId": CFG},
        {"id": "genB", "type": "generation", "configId": CFG},
    ],
    "connections": [
        {"sourceId": "in", "targetId": "lens"},
        {"sourceId": "lens", "targetId": "genA"},
        {"sourceId": "in", "targetId": "genB"},
    ],
}


def _seed_of(nodes):
    seeds = [n["seedValue"] for n in nodes if n.get("type") == "seed"]
    assert len(seeds) == 1, seeds
    return seeds[0]


def test_the_file_and_the_run_are_the_same_apparatus(here):
    """validate_and_expand draws a fresh random seed for a comparison, so a
    second expansion is a DIFFERENT apparatus. The file on disk, the journal and
    the board have to be the one the room ran — the shared seed is the whole
    point of a comparison."""
    from my_app.services.tool_registry import get_tool_registry, take_authored_graph
    take_authored_graph()
    result = get_tool_registry().execute(
        "run_canvas_graph", {"title": "Zwei Wege", "graph": _TWO_GENERATIONS})
    assert result.startswith("Apparatus 'Zwei Wege' validated"), result
    handed = take_authored_graph()
    assert handed is not None
    written = list(cge.EXPORT_DIR.glob("*.json"))
    assert len(written) == 1
    on_disk = json.loads(written[0].read_text(encoding="utf-8"))
    assert _seed_of(on_disk["nodes"]) == _seed_of(handed["workflow"]["nodes"])
    assert on_disk["id"] == handed["intent_id"]


def test_the_apparatus_is_handed_over_exactly_once(here):
    from my_app.services.tool_registry import get_tool_registry, take_authored_graph
    take_authored_graph()
    get_tool_registry().execute(
        "run_canvas_graph", {"title": "Zwei Wege", "graph": _TWO_GENERATIONS})
    assert take_authored_graph() is not None
    assert take_authored_graph() is None


def test_a_refused_apparatus_hands_over_nothing(here):
    from my_app.services.tool_registry import get_tool_registry, take_authored_graph
    take_authored_graph()
    result = get_tool_registry().execute(
        "run_canvas_graph", {"title": "Kaputt", "graph": {"nodes": []}})
    assert result.startswith("Error:")
    assert take_authored_graph() is None


def test_a_missing_title_is_written_down_as_a_refusal(here):
    """The one refusal that returns before the graph is even looked at. Without
    a file, a model that reached for the tool and was turned away looks exactly
    like a model that never reached for it."""
    from my_app.services.tool_registry import get_tool_registry
    result = get_tool_registry().execute("run_canvas_graph", {"graph": _TWO_GENERATIONS})
    assert result.startswith("Error:")
    written = list(cge.REJECTED_DIR.glob("*.json"))
    assert len(written) == 1
    body = json.loads(written[0].read_text(encoding="utf-8"))
    assert body["title"] is None
    assert "title" in body["error"]
    assert body["authored_graph"]["nodes"], "the graph the model sent is in the file"


def test_a_blank_model_role_is_never_filled_with_an_invention(payload, monkeypatch):
    """An installation whose roles are blank does not boot, so this cannot reach
    a room — but the export must not paper over it either. A name written here
    that nothing configured would be a model literal in the code, which this
    platform forbids outright."""
    import config
    monkeypatch.setattr(config, "STAGE2_INTERCEPTION_MODEL", "", raising=False)
    wf = to_canvas_workflow(payload, name="x")
    lens = next(n for n in wf["nodes"] if n["id"] == "lens")
    assert "llmModel" not in lens


# ---------------------------------------------------------------------------
# The fixture the Canvas test reads
# ---------------------------------------------------------------------------
# "Importable" is a claim about two pieces of code that never meet. It is
# asserted on the other side of the seam, against a file this code wrote —
# public/ai4artsed-frontend/src/views/__tests__/fixtures/apparatus_export.json.
# A fixture nobody regenerates stops describing the exporter the first time the
# exporter changes, and then it proves the shape of a past release. So it is
# regenerated from here and compared, and the comparison is the test.
#
#   Regenerate:  venv/bin/python devserver/tests/test_canvas_graph_export.py

FIXTURE = (Path(__file__).resolve().parents[2] / "public" / "ai4artsed-frontend"
           / "src" / "views" / "__tests__" / "fixtures" / "apparatus_export.json")
FIXTURE_TITLE = "Perspektive gegen Rohtext"
FIXTURE_MOTIVATION = "zwei Wege auf dasselbe Motiv"
# The clock and the dice are the two things that differ between two correct
# runs, and GRAPH sets its own seed, so stilling the clock is enough.
FIXTURE_STAMP = "2026-09-09T00:00:00+00:00"
# Model roles as an installation has them, in values no installation uses.
FIXTURE_ROLES = {
    "STAGE2_INTERCEPTION_MODEL": "test/thinking-role",
    "STAGE3_MODEL": "test/translation-role",
    "IMAGE_ANALYSIS_MODEL": "test/seeing-role",
}


def _fixture_body(into: Path) -> dict:
    payload, err = validate_and_expand(GRAPH)
    assert err is None, err
    path = cge.record_accepted(
        FIXTURE_TITLE, payload,
        motivation=FIXTURE_MOTIVATION, summary=summarize_graph(payload),
        intent_id="gi_fixture", device_id="fixture",
    )
    assert path is not None, "the fixture could not be written"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["createdAt"] = FIXTURE_STAMP
    body["updatedAt"] = FIXTURE_STAMP
    body["resona"]["recorded_at"] = FIXTURE_STAMP
    return body


def test_the_fixture_still_shows_what_this_code_writes(here, models_configured):
    assert FIXTURE.exists(), f"{FIXTURE} is missing — regenerate it"
    fresh = _fixture_body(cge.EXPORT_DIR)
    committed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fresh == committed, (
        "the exporter and the Canvas fixture have come apart — regenerate with "
        "venv/bin/python devserver/tests/test_canvas_graph_export.py"
    )


if __name__ == "__main__":
    import tempfile
    import config as _config
    for _role, _value in FIXTURE_ROLES.items():
        setattr(_config, _role, _value)
    with tempfile.TemporaryDirectory() as _tmp:
        cge.EXPORT_DIR = Path(_tmp)
        cge.REJECTED_DIR = Path(_tmp) / "rejected"
        _body = _fixture_body(cge.EXPORT_DIR)
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(_body, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"wrote {FIXTURE}")
