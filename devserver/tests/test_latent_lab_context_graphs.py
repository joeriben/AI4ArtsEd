"""
The graphs of the embedding research series, and the routes that run them.

my_app/services/latent_lab_context_graphs.py builds the ComfyUI graph of a
scheduled fusion, a Decomposition run, a position probe and a delayed kick-in on
the SD 3.5 context nodes; routes/fusion_workbench_routes.py runs them for the
Fusion Workbench and for the research scripts under devserver/testfiles. What
is checked here:

  * the schedule tables and how a request's bands and windows become blocks
    and fraction windows, as the Diffusers twin read them;
  * the cell list of a Decomposition run, explicit or spread per stream;
  * every graph: which node writes what, chained on the model, sampled on the
    conditioning the twin sampled on, saved through the one save node;
  * the routes' bodies, their refusals and the status each failure carries.

Nothing here reaches ComfyUI or a card.
"""

import asyncio
import sys

import pytest

from file_modules import DEVSERVER

sys.path.insert(0, str(DEVSERVER))

from my_app.services import latent_lab_context_graphs as graphs  # noqa: E402

CHECKPOINT = "OfficialStableDiffusion/sd3.5_large.safetensors"
SIZE = dict(negative_prompt="", checkpoint=CHECKPOINT, width=768, height=1024,
            steps=25, cfg=5.5, seed=11)


def _node_ids(graph, class_type):
    return [k for k, v in graph.items() if v["class_type"] == class_type]


def _frame_holds(graph):
    from schemas.engine.comfyui_chunk_support import CLIP_NODE, T5_LENGTH
    assert graph[graphs.MODEL_NODE_ID]["inputs"]["ckpt_name"] == CHECKPOINT
    assert graph[CLIP_NODE]["inputs"]["min_length"] == T5_LENGTH
    assert graph[graphs.LATENT_NODE_ID]["inputs"] == {"width": 768, "height": 1024, "batch_size": 1}
    assert graph[graphs.SAVE_NODE_ID]["class_type"] == "SaveImage"
    assert graph[graphs.SAVE_NODE_ID]["inputs"]["images"] == [graphs.DECODE_NODE_ID, 0]
    assert graph[graphs.DECODE_NODE_ID]["inputs"]["vae"] == [graphs.MODEL_NODE_ID, 2]


# --- the tables and the schedules --------------------------------------------

def test_the_bands_are_the_twins_tables():
    assert graphs.STEP_BANDS == {"composition": (0.0, 0.32), "semantics": (0.32, 0.68),
                                 "detail": (0.68, 1.01)}
    assert graphs.LAYER_BANDS == {"shallow": (0, 10), "middle": (10, 23), "deep": (23, 38)}
    assert graphs.STREAMS == ("clip_l", "clip_g", "t5")
    assert graphs.WINDOW_END == 1.01


def test_the_windows_and_blocks_of_a_scheduled_fusion_come_from_the_request():
    assert graphs.scheduled_windows(None, None) == [(0.0, 0.32), (0.32, 0.68), (0.68, 1.01)]
    assert graphs.scheduled_windows([0.3, 0.7], ["detail"]) == [(0.3, 0.7)]
    assert graphs.scheduled_windows(None, ["semantics"]) == [(0.32, 0.68)]
    with pytest.raises(ValueError, match="unknown step_band 'middle'"):
        graphs.scheduled_windows(None, ["middle"])
    with pytest.raises(ValueError, match=r"step_window is a pair \[lo, hi\]"):
        graphs.scheduled_windows("0.3-0.7", None)
    assert graphs.scheduled_blocks(10, ["deep"]) == [10]
    assert graphs.scheduled_blocks(None, None) == [0, 10, 23]
    assert graphs.scheduled_blocks(None, ["deep", "shallow"]) == [23, 0]
    with pytest.raises(ValueError, match="unknown layer_band 'detail'"):
        graphs.scheduled_blocks(None, ["detail"])
    with pytest.raises(ValueError, match="layer_entry is a block index"):
        graphs.scheduled_blocks("ten", None)


def test_the_cells_are_checked_one_by_one_or_spread_per_stream():
    cells = [{"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a lantern"},
             {"step": "composition", "layer": "shallow", "stream": "clip_l", "prompt": "  "}]
    assert graphs.normalized_cells(cells, {}) == [
        {"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a lantern"}]
    # One delta per place, the last prompt named, at the place's first position;
    # a cell named twice runs once (the twin's dict keyed by the place).
    twice = [{"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a lantern"},
             {"step": "semantics", "layer": "middle", "stream": "clip_g", "prompt": "a wall"},
             {"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a moon"},
             {"step": "detail", "layer": "deep", "stream": "t5", "prompt": ""}]
    assert graphs.normalized_cells(twice, {}) == [
        {"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a moon"},
        {"step": "semantics", "layer": "middle", "stream": "clip_g", "prompt": "a wall"}]
    for bad, message in (
        ([{"step": "late", "layer": "deep", "stream": "t5", "prompt": "x"}], r"cells\[0\].step='late'"),
        ([{"step": "detail", "layer": "top", "stream": "t5", "prompt": "x"}], r"cells\[0\].layer='top'"),
        ([{"step": "detail", "layer": "deep", "stream": "pooled", "prompt": "x"}], r"cells\[0\].stream='pooled'"),
        (["detail"], r"cells\[0\] must be a dict"),
    ):
        with pytest.raises(ValueError, match=message):
            graphs.normalized_cells(bad, {})
    spread = graphs.normalized_cells(None, {
        "clip_l": (None, None, None),
        "clip_g": ("a wall", ["semantics"], None),
        "t5": ("a lantern", None, ["deep"]),
    })
    assert spread == [
        {"step": "semantics", "layer": "shallow", "stream": "clip_g", "prompt": "a wall"},
        {"step": "semantics", "layer": "middle", "stream": "clip_g", "prompt": "a wall"},
        {"step": "semantics", "layer": "deep", "stream": "clip_g", "prompt": "a wall"},
        {"step": "composition", "layer": "deep", "stream": "t5", "prompt": "a lantern"},
        {"step": "semantics", "layer": "deep", "stream": "t5", "prompt": "a lantern"},
        {"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a lantern"},
    ]
    with pytest.raises(ValueError, match="t5_layer_bands: invalid bands"):
        graphs.normalized_cells([], {"t5": ("a lantern", None, ["top"])})


# --- the graphs ----------------------------------------------------------------

def test_the_scheduled_fusion_samples_on_alpha_zero_and_writes_the_fusion_in_the_windows():
    from schemas.engine.comfyui_chunk_support import CLIP_NODE
    g = graphs.fusion_scheduled_graph(
        prompt="a house", t5_prompt="a house", strategy="centered_fade", alpha=25.0,
        blocks=[10], windows=[(0.32, 0.68)], **SIZE)
    _frame_holds(g)
    assert g["10"]["inputs"] == {"clip": [CLIP_NODE, 0], "text": "a house", "empty_padding": "empty_prompt"}
    assert "11" not in g  # one prompt, one encode
    assert g["14"]["inputs"]["text"] == ""
    # the run's own conditioning: the fusion at alpha 0 under legacy, both sides
    assert g["12"]["inputs"] == {"clip_side": ["10", 0], "t5_side": ["10", 0], "alpha": 0.0, "strategy": "legacy"}
    assert g["15"]["inputs"] == {"clip_side": ["14", 0], "t5_side": ["14", 0], "alpha": 0.0, "strategy": "legacy"}
    assert g["13"]["inputs"] == {"parts": ["12", 0]} and g["16"]["inputs"] == {"parts": ["15", 0]}
    # what is written in: the fusion at alpha under the strategy, the negative fused alike
    assert g["17"]["inputs"] == {"clip_side": ["10", 0], "t5_side": ["10", 0], "alpha": 25.0, "strategy": "centered_fade"}
    assert g["19"]["inputs"] == {"clip_side": ["14", 0], "t5_side": ["14", 0], "alpha": 25.0, "strategy": "centered_fade"}
    assert g["30"] == {
        "inputs": {"model": ["5", 0], "positive": ["18", 0], "negative": ["21", 0],
                   "blocks": "10", "step_from": 0.32, "step_to": 0.68},
        "class_type": "AI4ArtsEdSD3ContextReplace",
        "_meta": {"title": "Write the fusion into the text stream"},
    }
    assert g[graphs.SAMPLER_NODE_ID]["inputs"] == {
        "model": ["30", 0], "positive": ["13", 0], "negative": ["16", 0],
        "latent_image": ["3", 0], "seed": 11, "steps": 25, "cfg": 5.5,
        "sampler_name": "euler", "scheduler": "normal", "denoise": 1,
    }
    assert g[graphs.DECODE_NODE_ID]["inputs"]["samples"] == [graphs.SAMPLER_NODE_ID, 0]


def test_a_scheduled_fusion_over_bands_chains_one_replacement_per_window():
    g = graphs.fusion_scheduled_graph(
        prompt="a house", t5_prompt="a house, expanded", strategy="slerp", alpha=0.5,
        blocks=[0, 10, 23], windows=graphs.scheduled_windows(None, None), **SIZE)
    assert g["11"]["inputs"]["text"] == "a house, expanded"
    assert g["12"]["inputs"]["t5_side"] == ["11", 0] and g["17"]["inputs"]["t5_side"] == ["11", 0]
    assert g["15"]["inputs"]["t5_side"] == ["14", 0]  # the negative fuses with itself
    assert [g[k]["inputs"]["model"] for k in ("30", "31", "32")] == [["5", 0], ["30", 0], ["31", 0]]
    assert [(g[k]["inputs"]["step_from"], g[k]["inputs"]["step_to"]) for k in ("30", "31", "32")] == [
        (0.0, 0.32), (0.32, 0.68), (0.68, 1.01)]
    assert all(g[k]["inputs"]["blocks"] == "0,10,23" for k in ("30", "31", "32"))
    assert g[graphs.SAMPLER_NODE_ID]["inputs"]["model"] == ["32", 0]


def test_the_decomposition_chains_one_delta_per_cell_and_encodes_each_prompt_once():
    from schemas.engine.comfyui_chunk_support import CLIP_NODE
    cells = [
        {"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a lantern"},
        {"step": "composition", "layer": "shallow", "stream": "clip_l", "prompt": "a wall"},
        {"step": "semantics", "layer": "middle", "stream": "clip_g", "prompt": "a lantern"},
    ]
    g = graphs.decomposition_graph(source_prompt="a house", cells=cells, alpha=-0.25, **SIZE)
    _frame_holds(g)
    assert g["1"]["inputs"]["t5xxl"] == "a house" and g["1"]["inputs"]["clip"] == [CLIP_NODE, 0]
    assert g["6"]["inputs"]["clip_l"] == "" and g["6"]["inputs"]["empty_padding"] == "empty_prompt"
    assert g["50"]["inputs"]["t5xxl"] == "a lantern" and g["51"]["inputs"]["t5xxl"] == "a wall"
    assert "52" not in g
    assert g["60"]["inputs"] == {"model": ["5", 0], "base": ["1", 0], "override": ["50", 0],
                                 "stream": "t5", "block": 23, "step_from": 0.68, "step_to": 1.01,
                                 "alpha": -0.25}
    assert g["61"]["inputs"] == {"model": ["60", 0], "base": ["1", 0], "override": ["51", 0],
                                 "stream": "clip_l", "block": 0, "step_from": 0.0, "step_to": 0.32,
                                 "alpha": -0.25}
    assert g["62"]["inputs"] == {"model": ["61", 0], "base": ["1", 0], "override": ["50", 0],
                                 "stream": "clip_g", "block": 10, "step_from": 0.32, "step_to": 0.68,
                                 "alpha": -0.25}
    assert all(g[k]["class_type"] == "AI4ArtsEdSD3ContextDelta" for k in ("60", "61", "62"))
    sampler = g[graphs.SAMPLER_NODE_ID]["inputs"]
    assert sampler["model"] == ["62", 0] and sampler["positive"] == ["1", 0] and sampler["negative"] == ["6", 0]
    # no cell: the source alone, sampled on the loader's model
    bare = graphs.decomposition_graph(source_prompt="a house", cells=[], alpha=1.0, **SIZE)
    assert bare[graphs.SAMPLER_NODE_ID]["inputs"]["model"] == ["5", 0]
    assert not _node_ids(bare, "AI4ArtsEdSD3ContextDelta")


def test_the_position_probe_converts_the_step_range_to_the_twins_fractions():
    g = graphs.position_probe_graph(
        baseline_prompt="a house", probe_prompt="a lantern", probe_stream="clip_g",
        probe_step_range=[5, 10], probe_block_range=[3, 8], **SIZE)
    _frame_holds(g)
    assert g["2"]["inputs"]["t5xxl"] == "a lantern"
    assert g["30"]["inputs"] == {"model": ["5", 0], "base": ["1", 0], "probe": ["2", 0],
                                 "stream": "clip_g", "block_from": 3, "block_to": 8,
                                 "step_from": 0.2, "step_to": 0.4}
    assert g["30"]["class_type"] == "AI4ArtsEdSD3ContextProbe"
    assert g[graphs.SAMPLER_NODE_ID]["inputs"]["model"] == ["30", 0]
    assert g[graphs.SAMPLER_NODE_ID]["inputs"]["positive"] == ["1", 0]
    for kwargs, message in (
        (dict(probe_step_range=[10, 5]), r"probe_step_range=\[10,5\) must satisfy"),
        (dict(probe_step_range=[0, 26]), r"probe_step_range=\[0,26\) must satisfy"),
        (dict(probe_step_range=[0]), r"probe_step_range must be \[lo, hi\]"),
        (dict(probe_block_range=[8, 3]), r"probe_block_range=\[8,3\) must satisfy"),
        (dict(probe_stream="pooled"), "probe_stream='pooled'"),
    ):
        base = dict(baseline_prompt="a house", probe_prompt="a lantern", probe_stream="t5",
                    probe_step_range=[5, 10], probe_block_range=[3, 8], **SIZE)
        with pytest.raises(ValueError, match=message):
            graphs.position_probe_graph(**{**base, **kwargs})


def test_the_kickin_at_block_zero_writes_the_full_prompt_from_the_step_on():
    g = graphs.delayed_kickin_graph(prompt_early="a house", prompt_full="a house with a lantern",
                                    kickin_step=8, block=0, **SIZE)
    _frame_holds(g)
    assert g["1"]["inputs"]["t5xxl"] == "a house" and g["2"]["inputs"]["t5xxl"] == "a house with a lantern"
    assert g["30"] == {
        "inputs": {"model": ["5", 0], "positive": ["2", 0], "blocks": "0",
                   "step_from": 8 / 25, "step_to": 1.01},
        "class_type": "AI4ArtsEdSD3ContextReplace",
        "_meta": {"title": "The full prompt from the kick-in step on"},
    }
    sampler = g[graphs.SAMPLER_NODE_ID]["inputs"]
    assert sampler["model"] == ["30", 0] and sampler["positive"] == ["1", 0]
    assert not _node_ids(g, "AI4ArtsEdSD3ContextCapture")
    # a kick-in past the run's end injects nowhere, as it did
    late = graphs.delayed_kickin_graph(prompt_early="a", prompt_full="b", kickin_step=30, block=0, **SIZE)
    assert late["30"]["inputs"]["step_from"] == 1.01
    with pytest.raises(ValueError, match="kickin_step must be >= 0"):
        graphs.delayed_kickin_graph(prompt_early="a", prompt_full="b", kickin_step=-1, block=0, **SIZE)


def test_the_kickin_past_block_zero_records_two_pre_runs_at_the_seed_and_replays_them():
    g = graphs.delayed_kickin_graph(prompt_early="a house", prompt_full="a house with a lantern",
                                    kickin_step=8, block=5, **SIZE)
    _frame_holds(g)
    for node_id in ("31", "32"):
        assert g[node_id]["class_type"] == "AI4ArtsEdSD3ContextCapture"
        assert g[node_id]["inputs"] == {"model": ["5", 0], "block_from": 5, "block_to": 6}
    early, full = g["23"]["inputs"], g["24"]["inputs"]
    assert early["model"] == ["31", 0] and early["positive"] == ["1", 0]
    assert full["model"] == ["32", 0] and full["positive"] == ["2", 0]
    assert early["seed"] == full["seed"] == 11 and early["steps"] == full["steps"] == 25
    assert g["33"]["inputs"] == {"model": ["5", 0], "early": ["31", 1], "full": ["32", 1],
                                 "kickin_step": 8, "samples_early": ["23", 0], "samples_full": ["24", 0]}
    assert g["33"]["class_type"] == "AI4ArtsEdSD3ContextReplay"
    main = g[graphs.SAMPLER_NODE_ID]["inputs"]
    assert main["model"] == ["33", 0] and main["positive"] == ["1", 0] and main["seed"] == 11
    assert g["34"]["inputs"] == {"samples": [graphs.SAMPLER_NODE_ID, 0], "early": ["31", 1], "full": ["32", 1]}
    assert g["34"]["class_type"] == "AI4ArtsEdSD3ContextRelease"
    assert g[graphs.DECODE_NODE_ID]["inputs"]["samples"] == ["34", 0]
    assert "30" not in g


def test_the_cumulative_kickin_covers_the_blocks_up_to_the_named_one():
    g = graphs.cumulative_kickin_graph(prompt_early="a house", prompt_full="a house with a lantern",
                                       kickin_step=8, up_to_block=3, **SIZE)
    assert g["31"]["inputs"] == {"model": ["5", 0], "block_from": 0, "block_to": 4}
    assert g["32"]["inputs"] == g["31"]["inputs"]
    assert g["33"]["inputs"]["kickin_step"] == 8
    with pytest.raises(ValueError, match="up_to_block must be >= 0"):
        graphs.cumulative_kickin_graph(prompt_early="a", prompt_full="b", kickin_step=0, up_to_block=-1, **SIZE)


def test_every_graph_saves_through_the_one_node_the_runner_reads():
    kickin = dict(prompt_early="a", prompt_full="b", kickin_step=1)
    for g in (
        graphs.fusion_scheduled_graph(prompt="a", t5_prompt="a", strategy="legacy", alpha=1.0,
                                      blocks=[0], windows=[(0.0, 1.01)], **SIZE),
        graphs.decomposition_graph(source_prompt="a", cells=[], alpha=1.0, **SIZE),
        graphs.position_probe_graph(baseline_prompt="a", probe_prompt="b", probe_stream="t5",
                                    probe_step_range=[0, 1], probe_block_range=[0, 1], **SIZE),
        graphs.delayed_kickin_graph(block=0, **kickin, **SIZE),
        graphs.delayed_kickin_graph(block=2, **kickin, **SIZE),
        graphs.cumulative_kickin_graph(up_to_block=1, **kickin, **SIZE),
    ):
        assert _node_ids(g, "SaveImage") == [graphs.SAVE_NODE_ID]
        assert g[graphs.SAVE_NODE_ID]["inputs"]["images"] == [graphs.DECODE_NODE_ID, 0]


# --- the checkpoint and the runner --------------------------------------------

def test_the_checkpoint_is_the_models_named_or_large(monkeypatch):
    """The block tables count 38 blocks: without a model named, the run is
    SD 3.5 Large, whatever card the Latent Lab resolver would answer for."""
    from my_app.services import latent_lab_model

    async def resolver():
        return "some/other"

    monkeypatch.setattr(latent_lab_model, "get_latent_lab_model_id", resolver)
    assert asyncio.run(graphs.checkpoint_of(None, "T")) == (
        CHECKPOINT, latent_lab_model.LATENT_LAB_LARGE)
    unet_id, _pipeline_class = latent_lab_model.get_latent_lab_unet()
    assert asyncio.run(graphs.checkpoint_of(unet_id, "T")) == (
        "OfficialStableDiffusion/sdxl_base.safetensors", unet_id)
    with pytest.raises(ValueError, match=r"\[T\] No ComfyUI checkpoint mapped for 'some/other'"):
        asyncio.run(graphs.checkpoint_of("some/other", "T"))


class _Result:
    prompt_id = "p-7"

    def __init__(self, files):
        self.media_files = files


class _File:
    def __init__(self, node_id, media_type, data):
        self.node_id, self.media_type, self.data = node_id, media_type, data


class _Client:
    base_url = "http://comfy.test"

    def __init__(self, files):
        self.files, self.submitted = files, []

    async def submit_and_track(self, workflow, timeout):
        from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
        self.submitted.append((workflow, timeout, CURRENT_OUTPUT_CONFIG.get()))
        return _Result(self.files)


def _runner(monkeypatch, files):
    from my_app.services import comfyui_manager, comfyui_ws_client
    from schemas.engine import comfyui_chunk_support

    class _Manager:
        async def ensure_comfyui_available(self):
            return True

    async def available(base_url, checkpoint, tag):
        return True

    client = _Client(files)
    monkeypatch.setattr(comfyui_manager, "get_comfyui_manager", lambda: _Manager())
    monkeypatch.setattr(comfyui_ws_client, "get_comfyui_ws_client", lambda: client)
    monkeypatch.setattr(comfyui_chunk_support, "checkpoint_available", available)
    return client


def test_the_runner_submits_under_the_workload_without_a_cap_and_reads_the_saved_picture(monkeypatch):
    client = _runner(monkeypatch, [_File("40", "image", b"png-bytes")])
    g = graphs.decomposition_graph(source_prompt="a", cells=[], alpha=1.0, **SIZE)
    image = asyncio.run(graphs.run_graph(g, "decomposition", "T"))
    assert image == "cG5nLWJ5dGVz"  # base64 of the bytes
    workflow, timeout, workload = client.submitted[0]
    assert workflow is g and timeout is None and workload == "decomposition"
    from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
    assert CURRENT_OUTPUT_CONFIG.get() != "decomposition"  # put back after the run
    _runner(monkeypatch, [_File("22", "image", b"x")])
    with pytest.raises(RuntimeError, match=r"\[T\] ComfyUI answered without a picture \(prompt p-7\)"):
        asyncio.run(graphs.run_graph(g, "decomposition", "T"))


# --- the routes ----------------------------------------------------------------

@pytest.fixture
def routes():
    from my_app.routes import fusion_workbench_routes
    return fusion_workbench_routes


def test_the_size_and_the_seed_read_as_the_twins_routes_read_them(routes):
    assert routes._size_and_seed({"seed": 5}) == (1024, 1024, 25, 5.5, 5)
    assert routes._size_and_seed({"width": "768", "height": 512, "steps": "30", "cfg_scale": "4",
                                  "seed": "9"}) == (768, 512, 30, 4.0, 9)
    drawn = routes._size_and_seed({})[4]
    assert 0 <= drawn <= 2 ** 32 - 1
    assert routes._size_and_seed({"seed": -1})[4] != -1
    # null in the body is the field left out; a value that is no number is
    # refused with its name and value, a 400 through _run.
    assert routes._size_and_seed({"seed": None, "width": None, "cfg_scale": None})[:2] == (1024, 1024)
    with pytest.raises(ValueError, match="seed 'x': a number"):
        routes._size_and_seed({"seed": "x"})
    with pytest.raises(ValueError, match="steps \\[25\\]: a number"):
        routes._size_and_seed({"steps": [25]})


def test_the_fusions_of_the_workbench_are_named_and_the_options_stay_with_the_twin(routes):
    assert routes.WORKBENCH_FUSIONS == ("centered_fade", "legacy", "dual_alpha", "slerp", "normalized")
    assert routes._fusion_named(None) == "legacy"
    assert routes._fusion_named("slerp") == "slerp"
    with pytest.raises(ValueError, match="'original' is none of"):
        routes._fusion_named("original")
    with pytest.raises(ValueError, match="the options after '#' \\(norm_t5_to_clip\\) run on the Diffusers twin"):
        routes._fusion_named("legacy#norm_t5_to_clip")


def test_each_instrument_builds_its_graph_from_its_body(routes, monkeypatch):
    async def checkpoint_of(model_id, tag):
        return CHECKPOINT, model_id or "resolved/model"

    monkeypatch.setattr(graphs, "checkpoint_of", checkpoint_of)
    body = {"prompt": "a house", "fusion_strategy": "centered_fade", "alpha_factor": 25,
            "step_window": [0.32, 0.68], "layer_entry": 10, "seed": 3, "model_id": "named/model"}
    g, model_id, seed = asyncio.run(routes._graph_for("generate", body))
    assert (model_id, seed) == ("named/model", 3)
    assert g["17"]["inputs"]["alpha"] == 25.0 and g["30"]["inputs"]["blocks"] == "10"
    assert g["30"]["inputs"]["step_from"] == 0.32
    g, model_id, _seed = asyncio.run(routes._graph_for("decomposition", {
        "source_prompt": "a house", "alpha": 4.0,
        "cells": [{"step": "detail", "layer": "deep", "stream": "t5", "prompt": "a lantern"}]}))
    assert model_id == "resolved/model" and g["60"]["inputs"]["alpha"] == 1.0  # clamped
    g, _m, _s = asyncio.run(routes._graph_for("position_probe", {
        "baseline_prompt": "a", "probe_prompt": "b", "probe_stream": "t5",
        "probe_step_range": [0, 5], "probe_block_range": [0, 2], "steps": 10}))
    assert g["30"]["inputs"]["step_to"] == 0.5
    g, _m, _s = asyncio.run(routes._graph_for("delayed_kickin", {
        "prompt_early": "a", "prompt_full": "b", "kickin_step": 4, "block_range": [7, 9]}))
    assert g["31"]["inputs"] == {"model": ["5", 0], "block_from": 7, "block_to": 8}
    g, _m, _s = asyncio.run(routes._graph_for("delayed_kickin", {"prompt_early": "a", "prompt_full": "b",
                                                                 "kickin_step": 0}))
    assert g["30"]["inputs"]["blocks"] == "0" and g["30"]["inputs"]["step_from"] == 0.0
    g, _m, _s = asyncio.run(routes._graph_for("delayed_kickin_cumulative", {
        "prompt_early": "a", "prompt_full": "b", "kickin_step": 2, "up_to_block": 4}))
    assert g["31"]["inputs"]["block_to"] == 5
    with pytest.raises(ValueError, match=r"block_range must be \[lo, hi\]"):
        asyncio.run(routes._graph_for("delayed_kickin", {"prompt_early": "a", "prompt_full": "b",
                                                         "kickin_step": 0, "block_range": [7]}))


def test_a_run_answers_with_the_picture_or_the_status_its_failure_carries(routes, monkeypatch):
    from my_app.services.gpu_lease_client import GpuBusyError
    calls = []

    async def checkpoint_of(model_id, tag):
        return CHECKPOINT, "resolved/model"

    def run_graph_with(outcome):
        async def run_graph(graph, workload, tag):
            calls.append((workload, tag))
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return run_graph

    marked = []
    monkeypatch.setattr(graphs, "checkpoint_of", checkpoint_of)
    monkeypatch.setattr("my_app.services.watermark_service.watermark_result_metadata",
                        lambda payload, meta, extra_keys: marked.append((payload["seed"], meta, extra_keys)))
    body = {"prompt": "a house", "seed": 12, "enable_streaming": True}

    monkeypatch.setattr(graphs, "run_graph", run_graph_with("aW1n"))
    assert routes._run("generate", body) == ({"success": True, "image_base64": "aW1n", "seed": 12}, 200)
    assert calls == [("fusion_scheduled", "FUSION-WORKBENCH-GENERATE")]
    assert marked == [(12, {"seed": 12}, ("image_base64",))]

    assert routes._run("generate", {"seed": 1}) == ({"success": False, "error": "prompt required"}, 400)
    assert routes._run("position_probe", {"baseline_prompt": "a"}) == (
        {"success": False, "error": "probe_prompt required"}, 400)
    # Presence, as the twin's routes checked: the probe's empty baseline passes.
    assert routes._run("position_probe", {"baseline_prompt": "", "probe_prompt": "a"}) == (
        {"success": False, "error": "probe_step_range required"}, 400)
    assert routes._run("delayed_kickin", {"prompt_early": "a", "prompt_full": "b"}) == (
        {"success": False, "error": "kickin_step required"}, 400)
    assert routes._run("delayed_kickin_cumulative",
                       {"prompt_early": "a", "prompt_full": "b", "kickin_step": 3}) == (
        {"success": False, "error": "up_to_block required"}, 400)
    assert routes._run("generate", {"prompt": "a", "fusion_strategy": "original"}) == (
        {"success": False, "error": "fusion_strategy 'original' is none of centered_fade, legacy, "
                                    "dual_alpha, slerp, normalized"}, 400)
    monkeypatch.setattr(graphs, "run_graph", run_graph_with(GpuBusyError("queue full")))
    payload, status = routes._run("generate", body)
    assert status == 503 and payload["error"] == "the card is busy: queue full"
    monkeypatch.setattr(graphs, "run_graph", run_graph_with(RuntimeError("node 30 refused: Block 40")))
    assert routes._run("decomposition", {"source_prompt": "a"}) == (
        {"success": False, "error": "node 30 refused: Block 40"}, 500)


RESEARCH_ROUTES = ("decomposition", "position_probe", "delayed_kickin", "delayed_kickin_cumulative")


def _app(routes, monkeypatch, level):
    from flask import Flask
    from my_app.services import safety_level_resolver
    monkeypatch.setattr(safety_level_resolver, "resolve_safety_level", lambda: level)
    app = Flask(__name__)
    app.register_blueprint(routes.fusion_workbench_bp)
    return app


def test_the_research_routes_stand_beside_generate_and_refuse_a_missing_field(routes, monkeypatch):
    app = _app(routes, monkeypatch, "research")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert {"/api/fusion_workbench/generate", "/api/fusion_workbench/expand_t5",
            "/api/fusion_workbench/decomposition", "/api/fusion_workbench/position_probe",
            "/api/fusion_workbench/delayed_kickin",
            "/api/fusion_workbench/delayed_kickin_cumulative"} <= rules
    # Each route is a function of its own name, registered through a `.route`
    # decorator and not by hand.
    for kind in RESEARCH_ROUTES:
        assert app.view_functions[f"fusion_workbench.{kind}"].__name__ == kind
    client = app.test_client()
    answer = client.post("/api/fusion_workbench/delayed_kickin", json={"prompt_early": "a"})
    assert answer.status_code == 400 and answer.get_json() == {"success": False, "error": "prompt_full required"}
    answer = client.post("/api/fusion_workbench/position_probe", data="[1]", content_type="application/json")
    assert answer.status_code == 400 and answer.get_json()["success"] is False


def test_the_research_routes_answer_at_the_research_level_only(routes, monkeypatch):
    client = _app(routes, monkeypatch, "open").test_client()
    for kind in RESEARCH_ROUTES:
        answer = client.post(f"/api/fusion_workbench/{kind}", json={"source_prompt": "a"})
        assert answer.status_code == 403
        assert answer.get_json() == {
            "success": False,
            "error": f"{kind} runs at the research level only; this installation runs at 'open'"}
    # /generate stands as it stood (docs/WORK_ORDER_CONTENT_CHECKING.md, A7).
    client = _app(routes, monkeypatch, "kids").test_client()
    answer = client.post("/api/fusion_workbench/generate", json={})
    assert answer.status_code == 400 and answer.get_json() == {"success": False, "error": "prompt required"}

