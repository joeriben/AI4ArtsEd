#!/usr/bin/env python3
"""A graph can run Composable Diffusion, and a picture nothing stored is a failure.

On 2026-11-04 a card built by Resona failed with "Need at least 2 concepts": a
generation node hands a chunk one prompt, and this instrument reads a list. Each
text connected to the node is now one concept. The same run would then have
reported success with nothing on the card, because the stage-4 path knew two of
the six image markers of the Latent Lab chunks and handed out a URL for the rest.

The intake, the check before the model and Stage 4 are stubbed where the
question is who receives what.
"""
import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import my_app.routes.schema_pipeline_routes as spr
from my_app.services import canvas_executor
from my_app.services import canvas_graph_authoring as cga
from my_app.services.canvas_executor import CanvasWorkflowExecutor, board_intake, intake_refusal
from my_app.services.safety_gate import (CHECKPOINT_BEFORE_MODEL, CHECKPOINT_INTAKE,
                                         REASON_CONTENT, Verdict)


class _Recorder:
    def save_entity(self, **kw):
        pass

    def save_image_from_url(self, **kw):
        pass


class _Engine:
    async def process_request(self, req):
        raise AssertionError("no language model belongs in this test")


def _graph(texts, **keys):
    nodes = [{"id": f"in{i}", "type": "input", "promptText": t} for i, t in enumerate(texts)]
    nodes.append({"id": "gen", "type": "generation", "configId": "composable_diffusion", **keys})
    return {"nodes": nodes,
            "connections": [{"sourceId": f"in{i}", "targetId": "gen"} for i in range(len(texts))]}


# --- authoring ---------------------------------------------------------------

def test_the_graph_of_2026_11_04_is_refused_and_told_how():
    payload, err = cga.validate_and_expand(_graph(["a disc AND a cone AND gauze"]))
    assert payload is None
    assert "2 to 5" in err and "1 are connected" in err and "own input node" in err


def test_six_concepts_are_refused():
    assert cga.validate_and_expand(_graph(list("abcdef")))[0] is None


def test_two_to_five_concepts_pass_with_their_keys():
    for n in (2, 5):
        payload, err = cga.validate_and_expand(
            _graph(list("abcde")[:n], concept_weights=[1] * n, combine_at="conditioning"))
        assert err is None
        gen = next(x for x in payload["nodes"] if x["id"] == "gen")
        assert gen["concept_weights"] == [1] * n and gen["combine_at"] == "conditioning"


def test_a_parameter_node_is_no_concept():
    graph = _graph(["a"], seed=3)
    assert cga.validate_and_expand(graph)[0] is None


def test_the_same_source_twice_is_one_concept():
    graph = _graph(["a", "b"])
    graph["connections"].append({"sourceId": "in0", "targetId": "gen"})
    assert cga.validate_and_expand(graph)[1] is None
    graph["connections"].pop(1)
    assert cga.validate_and_expand(graph)[0] is None


@pytest.mark.parametrize("weights", [[1], [1, 2, 3], [1, 3], [1, "1"], [1, True], "1,1"])
def test_weights_that_do_not_fit_are_refused(weights):
    assert "concept_weights" in cga.validate_and_expand(_graph(["a", "b"], concept_weights=weights))[1]


def test_an_unknown_place_is_refused():
    assert "combine_at" in cga.validate_and_expand(_graph(["a", "b"], combine_at="latent"))[1]


def test_a_weight_of_the_other_sign_passes_in_both_places():
    """The instrument keeps it: in the embedding the interpolation runs past the others."""
    for place in ("score", "conditioning"):
        assert cga.validate_and_expand(
            _graph(["a", "b"], concept_weights=[1, -0.5], combine_at=place))[1] is None


@pytest.mark.parametrize("weights", [[0, 0], [1, -1], [0.5, 0.5, -1]])
def test_weights_the_node_cannot_interpolate_are_refused(weights):
    texts = list("abc")[:len(weights)]
    err = cga.validate_and_expand(_graph(texts, concept_weights=weights, combine_at="conditioning"))[1]
    assert "share to interpolate" in err
    assert cga.validate_and_expand(_graph(texts, concept_weights=weights))[1] is None


def test_an_empty_input_is_no_concept():
    err = cga.validate_and_expand(_graph(["a", "  ", "b"]))[1]
    assert "in1" in err and "no text" in err


def test_the_keys_belong_to_this_instrument():
    graph = {"nodes": [{"id": "in", "type": "input", "promptText": "a"},
                       {"id": "gen", "type": "generation", "configId": "sd35_large",
                        "combine_at": "score"}],
             "connections": [{"sourceId": "in", "targetId": "gen"}]}
    assert "composable_diffusion" in cga.validate_and_expand(graph)[1]


def test_every_concept_config_has_a_file_on_disk():
    configs = Path(__file__).resolve().parents[1] / "schemas" / "configs" / "output"
    for config_id in cga.CONCEPT_CONFIGS:
        assert (configs / f"{config_id}.json").exists()


# --- what Resona is told -----------------------------------------------------

@pytest.mark.parametrize("config_id, name", [("concept_algebra", "Concept Algebra"),
                                             ("feature_probing", "Dimension Explorer")])
def test_an_instrument_no_graph_can_run_is_refused_with_its_reason(config_id, name):
    graph = {"nodes": [{"id": "in", "type": "input", "promptText": "a"},
                       {"id": "gen", "type": "generation", "configId": config_id}],
             "connections": [{"sourceId": "in", "targetId": "gen"}]}
    payload, err = cga.validate_and_expand(graph)
    assert payload is None
    assert name in err and "own page" in err


def test_nothing_is_offered_and_page_only_at_once():
    assert not set(cga.PAGE_ONLY_INSTRUMENTS) & set(cga.RESONA_CANVAS_CONFIGS)


def test_the_tool_description_says_what_a_graph_cannot_run():
    from my_app.services.tool_registry import get_tool_registry
    schema = json.dumps(get_tool_registry()._tools["run_canvas_graph"]["schema"])
    assert "NOT AVAILABLE IN A GRAPH" in schema
    assert "Concept Algebra reads three texts" in schema
    assert "Dimension Explorer reads two texts" in schema
    assert "concept_algebra =" not in schema and "feature_probing =" not in schema


def test_the_core_prompt_keeps_them_on_their_pages():
    from my_app.routes.chat_routes import RESONA_CORE_PROMPT
    assert "Dimension Explorer and Concept\nAlgebra run only on their own pages" in RESONA_CORE_PROMPT


# --- executor ----------------------------------------------------------------

@pytest.fixture
def stages(monkeypatch):
    """The intake, the check before the model and Stage 4 as stand-ins.

    Until 2026-11-01 the Canvas ran Stage 1 on every concept and Stage 3 on the
    joined line. Now the board's texts pass the intake (board_intake, which the
    route runs before the executor), and every text the chunk receives passes
    the check before the model: the joined line and each concept by its name.
    """
    seen = {"intake": [], "before_model": [], "stage4": []}

    def intake(text, *, level, kind="text", field=""):
        seen["intake"].append((text, level, field))
        if isinstance(text, str) and "Wolfsangel" in text:
            return Verdict(False, CHECKPOINT_INTAKE, level, field, REASON_CONTENT,
                           "blocked at the intake")
        return Verdict(True, CHECKPOINT_INTAKE, level, field)

    def before_model(texts, *, level, **kw):
        seen["before_model"].append(dict(texts))
        for name, text in texts.items():
            if isinstance(text, str) and "forbidden" in text:
                return Verdict(False, CHECKPOINT_BEFORE_MODEL, level, name, REASON_CONTENT,
                               "blocked before the model")
        return Verdict(True, CHECKPOINT_BEFORE_MODEL, level)

    async def stage4(**kw):
        seen["stage4"].append(kw)
        return {"success": True, "media_output": {"url": "/api/media/image/x/0", "seed": 7},
                "model_meta": None}

    monkeypatch.setattr(canvas_executor, "check_intake", intake)
    monkeypatch.setattr(canvas_executor, "check_before_model", before_model)
    monkeypatch.setattr(canvas_executor, "run_llm_steps", lambda chunk, prompt: {})
    monkeypatch.setattr(canvas_executor, "_output_chunk", lambda config_id: None)
    monkeypatch.setattr(spr, "execute_stage4_generation_only", stage4)
    monkeypatch.setattr(spr, "pipeline_executor", object())
    return seen


def _run(graph, level="kids"):
    ex = CanvasWorkflowExecutor(graph["nodes"], graph["connections"], _Recorder(), "run_test",
                                _Engine(), safety_level=level, lang="de", device_id="dev_1")
    list(ex.execute_with_events())
    return ex


def test_every_text_arrives_as_a_concept_with_its_weight(stages):
    _run(_graph(["a disc", "a cone", "gauze"], concept_weights=[1, 0.5, -1], combine_at="score"))
    call = stages["stage4"][0]
    assert call["concepts"] == [{"prompt": "a disc", "weight": 1},
                                {"prompt": "a cone", "weight": 0.5},
                                {"prompt": "gauze", "weight": -1}]
    assert call["combine_at"] == "score"
    assert call["secondary_text"] is None
    assert call["prompt"] == "a disc + a cone + gauze"


def test_weights_follow_the_edges_not_the_arrival(stages):
    """The first edge's branch has a step more to go, so its text comes in last."""
    graph = _graph(["a", "b"], concept_weights=[0.25, 0.75])
    graph["nodes"].append({"id": "t", "type": "translation", "translationLanguage": "en"})
    graph["connections"][0] = {"sourceId": "t", "targetId": "gen"}
    graph["connections"].append({"sourceId": "in0", "targetId": "t"})

    ex = CanvasWorkflowExecutor(graph["nodes"], graph["connections"], _Recorder(), "run_test",
                                _Engine(), safety_level="research", lang="de", device_id="dev_1")
    ex._execute_translation = lambda node, node_id, data: (f"EN {data}", "text", None)
    list(ex.execute_with_events())

    assert stages["stage4"][0]["concepts"] == [{"prompt": "EN a", "weight": 0.25},
                                               {"prompt": "b", "weight": 0.75}]


def test_without_weights_every_concept_counts_one(stages):
    _run(_graph(["a", "b"]))
    assert [c["weight"] for c in stages["stage4"][0]["concepts"]] == [1.0, 1.0]


def test_the_check_before_the_model_reads_every_concept_before_any_model(stages):
    ex = _run(_graph(["a", "something forbidden"]))
    assert stages["before_model"] == [{"prompt": "a + something forbidden", "secondary_text": None,
                                       "concepts[0]": "a", "concepts[1]": "something forbidden"}]
    assert stages["stage4"] == []
    assert ex.results["gen"]["safety_block"]["checkpoint"] == "before_model"


@pytest.mark.parametrize("level", ["kids", "youth", "adult"])
def test_the_intake_reads_every_concept_as_written_at_every_level(stages, level):
    """The route runs the board's intake before the executor (canvas_routes):
    the text of every input node, as written, at every level."""
    graph = _graph(["a", "eine Wolfsangel"])
    verdict, node = board_intake(graph["nodes"], level=level)
    assert [(t, lv) for t, lv, _ in stages["intake"] if t] == [("a", level), ("eine Wolfsangel", level)]
    assert not verdict.passed and not verdict.operational and node["id"] == "in1"
    event = intake_refusal(verdict, node)
    assert event["errors"][0]["safety_block"]["checkpoint"] == "intake"
    assert event["results"]["in1"]["safety_block"]["field"] == "nodes[in1].promptText"
    assert stages["before_model"] == [] and stages["stage4"] == []


def test_what_was_checked_is_what_generates(stages):
    _run(_graph(["a disc", "a cone"]))
    call = stages["stage4"][0]
    read = stages["before_model"][0]
    assert [c["prompt"] for c in call["concepts"]] == [read["concepts[0]"], read["concepts[1]"]]
    assert read["prompt"] == call["prompt"]


def _through_translation(graph, ex_level="research"):
    ex = CanvasWorkflowExecutor(graph["nodes"], graph["connections"], _Recorder(), "run_test",
                                _Engine(), safety_level=ex_level, lang="de", device_id="dev_1")
    ex._execute_translation = lambda node, node_id, data: (f"EN {data}", "text", None)
    list(ex.execute_with_events())
    return ex


def test_a_source_that_answers_twice_never_fires_the_node_on_one_concept(stages):
    """a and b both feed t, t and c feed the node; c comes in behind two translations."""
    graph = {"nodes": [{"id": "a", "type": "input", "promptText": "a"},
                       {"id": "b", "type": "input", "promptText": "b"},
                       {"id": "c", "type": "input", "promptText": "c"},
                       {"id": "t", "type": "translation"},
                       {"id": "t2", "type": "translation"},
                       {"id": "t3", "type": "translation"},
                       {"id": "gen", "type": "generation", "configId": "composable_diffusion"}],
             "connections": [{"sourceId": "a", "targetId": "t"}, {"sourceId": "b", "targetId": "t"},
                             {"sourceId": "t", "targetId": "gen"}, {"sourceId": "c", "targetId": "t2"},
                             {"sourceId": "t2", "targetId": "t3"}, {"sourceId": "t3", "targetId": "gen"}]}
    ex = _through_translation(graph)
    assert stages["stage4"] and all(len(c["concepts"]) == 2 for c in stages["stage4"])
    assert ex.get_result()["success"] is True


def test_a_concept_that_never_arrives_is_said(stages):
    """An evaluation that took the other path leaves the node short of a text."""
    graph = _graph(["a", "b"])
    graph["nodes"].append({"id": "e", "type": "evaluation", "evaluationPrompt": "x"})
    graph["connections"][0] = {"sourceId": "e", "targetId": "gen", "label": "pass"}
    graph["connections"].append({"sourceId": "in0", "targetId": "e"})
    ex = CanvasWorkflowExecutor(graph["nodes"], graph["connections"], _Recorder(), "run_test",
                                _Engine(), safety_level="research", lang="de", device_id="dev_1")

    def failed(node, node_id, data):
        ex.results[node_id] = {"type": "evaluation", "error": None,
                               "outputs": {"pass": "", "fail": data, "commentary": ""}}
        return data, "text", {"binary": False, "score": 1, "active_path": "fail"}

    ex._execute_evaluation = failed
    list(ex.execute_with_events())
    assert stages["stage4"] == []
    result = ex.get_result()
    assert result["success"] is False and "no text arrived from e" in result["error"]


def test_a_text_that_arrives_empty_stops_the_node(stages):
    ex = _through_translation(_graph(["a", "b", "c"]))
    assert len(stages["stage4"][0]["concepts"]) == 3
    stages["stage4"].clear()
    graph = _graph(["a", "b", "c"])
    graph["nodes"].append({"id": "t", "type": "translation"})
    graph["connections"][1] = {"sourceId": "t", "targetId": "gen"}
    graph["connections"].append({"sourceId": "in1", "targetId": "t"})
    ex = CanvasWorkflowExecutor(graph["nodes"], graph["connections"], _Recorder(), "run_test",
                                _Engine(), safety_level="research", lang="de", device_id="dev_1")
    ex._execute_translation = lambda node, node_id, data: ("  ", "text", None)
    list(ex.execute_with_events())
    assert stages["stage4"] == []
    assert "no text arrived from t" in ex.results["gen"]["error"]


def test_one_wire_on_the_board_is_said_before_any_check(stages):
    """A hand-wired board has no authoring step in front of it."""
    graph = {"nodes": [{"id": "in", "type": "input", "promptText": "a"},
                       {"id": "gen", "type": "generation", "configId": "composable_diffusion"}],
             "connections": [{"sourceId": "in", "targetId": "gen"}]}
    ex = _run(graph)
    assert stages["before_model"] == [] and stages["stage4"] == []
    assert "2 to 5" in ex.results["gen"]["error"]


def test_a_config_with_one_prompt_gets_none_of_it(stages):
    graph = _graph(["a"])
    graph["nodes"][-1]["configId"] = "sd35_large"
    _run(graph)
    call = stages["stage4"][0]
    assert call["prompt"] == "a" and call["concepts"] is None


# --- stage 4 -----------------------------------------------------------------

class _Result:
    success = True
    error = None

    def __init__(self, marker, metadata):
        self.final_output = marker
        self.metadata = metadata


class _Config:
    meta = {"backend_type": "comfyui"}


def _stage4(monkeypatch, tmp_path, marker, metadata, **kw):
    import config
    from my_app.services import pipeline_recorder as recorder_mod

    monkeypatch.setattr(config, "JSON_STORAGE_DIR", tmp_path)
    recorder_mod._active_recorders.clear()
    seen = {}

    class _Executor:
        class config_loader:
            @staticmethod
            def get_config(name):
                return _Config()

        async def execute_pipeline(self, **call):
            seen["custom"] = call["context_override"].custom_placeholders \
                if call.get("context_override") else {}
            return _Result(marker, metadata)

    monkeypatch.setattr(spr, "pipeline_executor", _Executor())
    monkeypatch.setattr(spr, "_generator_fields", lambda *a: {"generator_substituted": False})
    monkeypatch.setattr("my_app.services.model_meta.build_model_meta", lambda *a, **k: None)
    result = asyncio.run(spr.execute_stage4_generation_only(
        prompt="a + b", output_config="composable_diffusion", safety_level="research",
        run_id="run_concepts", seed=1, **kw))
    return result, seen


PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


@pytest.mark.parametrize("marker", ["diffusers_composable_generated", "diffusers_attention_generated"])
def test_the_image_of_a_latent_lab_chunk_is_stored(monkeypatch, tmp_path, marker):
    result, _ = _stage4(monkeypatch, tmp_path, marker, {"image_data": PNG_B64, "seed": 1})
    assert result["success"] is True
    assert list(tmp_path.rglob("*.png"))
    record = json.loads(next(tmp_path.rglob("metadata.json")).read_text())
    image = next(e for e in record["entities"] if e["type"] == "output_image")
    assert image["metadata"]["backend"] == "comfyui"


def test_the_chunk_receives_what_the_direct_route_hands_it(monkeypatch, tmp_path):
    concepts = [{"prompt": "a", "weight": 1}, {"prompt": "b", "weight": -1}]
    _, seen = _stage4(monkeypatch, tmp_path, "diffusers_composable_generated",
                      {"image_data": PNG_B64, "seed": 1}, concepts=concepts, combine_at="score")
    assert json.loads(seen["custom"]["concepts"]) == concepts
    assert seen["custom"]["combine_at"] == "score"


def test_a_marker_nothing_stores_is_a_failure(monkeypatch, tmp_path):
    result, _ = _stage4(monkeypatch, tmp_path, "diffusers_unknown_generated", {"seed": 1})
    assert result["success"] is False
    assert "diffusers_unknown_generated" in result["error"]
    assert "stores nothing" in result["error"]
