"""Flux 3 Multi takes one to ten reference images, in two chunks.

The adaption chunk writes the caption, the output chunk makes the picture. Each
declares ten image slots and what falls away when one stays empty. The route
reads every slot the chunks map, in order, and the workflow that reaches ComfyUI
holds exactly the images the request carried.
"""
import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "schemas" / "chunks"
IMAGE_CHUNK = CHUNKS / "output_image_flux3_multi.json"
ADAPTION_CHUNK = CHUNKS / "adaption_image_flux3_upsampler.json"
CONFIG = ROOT / "schemas" / "configs" / "output" / "flux3_multi.json"
LOAD_NODE = {n: str(100 + n) for n in range(1, 11)}
FIT_NODE = {n: str(300 + n) for n in range(2, 11)}


def _chunk(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _provided(count):
    return {f"input_image{n}": f"{n}.png" for n in range(1, count + 1)}


def _adapted(path, count):
    from schemas.engine.backend_router import _adapt_workflow_for_multi_image
    chunk = _chunk(path)
    return _adapt_workflow_for_multi_image(
        copy.deepcopy(chunk["workflow"]), _provided(count), chunk["multi_image_adaptation"])


def _images_of(node):
    images = {k: v for k, v in node["inputs"].items() if k.startswith("images.image")}
    return sorted(images, key=lambda k: int(k.rsplit("image", 1)[1])), images


@pytest.mark.parametrize("count", range(1, 11))
def test_the_picture_keeps_exactly_the_images_provided(count):
    workflow = _adapted(IMAGE_CHUNK, count)
    for n, node_id in LOAD_NODE.items():
        assert (node_id in workflow) == (n <= count), node_id
    names, images = _images_of(workflow["201"])
    assert names == [f"images.image{n}" for n in range(count)]
    assert all(source[0] in workflow for source in images.values())


@pytest.mark.parametrize("count", range(1, 11))
def test_the_caption_keeps_exactly_the_images_provided(count):
    workflow = _adapted(ADAPTION_CHUNK, count)
    for n, node_id in LOAD_NODE.items():
        assert (node_id in workflow) == (n <= count), node_id
    for n, node_id in FIT_NODE.items():
        assert (node_id in workflow) == (n <= count), node_id
    names, images = _images_of(workflow["211"])
    assert names == [f"images.image{n}" for n in range(count)]
    assert all(source[0] in workflow for source in images.values())


@pytest.mark.parametrize("path", (IMAGE_CHUNK, ADAPTION_CHUNK))
@pytest.mark.parametrize("count", (1, 2, 3, 10))
def test_every_remaining_link_points_at_a_node_that_is_there(path, count):
    workflow = _adapted(path, count)
    for node_id, node in workflow.items():
        for name, value in node["inputs"].items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[1], int):
                assert str(value[0]) in workflow, (node_id, name, value)


def test_the_picture_runs_no_language_model_of_its_own():
    """The caption is the prompt: a second upsampler here would rewrite what the check has passed."""
    workflow = _chunk(IMAGE_CHUNK)["workflow"]
    assert not [n for n in workflow.values() if n["class_type"] == "TextGenerate"]
    assert workflow["6"]["inputs"]["text"] == ["75", 0]


def test_the_config_names_the_adaption_and_both_chunks_exist():
    config = _chunk(CONFIG)
    assert config["parameters"]["OUTPUT_CHUNK"] == IMAGE_CHUNK.stem
    assert config["meta"]["adaption_chunk"] == ADAPTION_CHUNK.stem
    assert "optimization_instruction" not in config["meta"]


def test_the_adaption_answers_in_words():
    chunk = _chunk(ADAPTION_CHUNK)
    mapping = chunk["output_mapping"]
    assert mapping["output_type"] == "text"
    shown = chunk["workflow"][mapping["node_id"]]
    assert shown["class_type"] == "PreviewAny"
    assert chunk["workflow"][shown["inputs"]["source"][0]]["class_type"] == "TextGenerate"
    assert chunk["meta"]["display_name"]


def test_the_upsampler_sees_every_reference_whole():
    """BatchImagesNode crops to the first image's shape; stretched first, it has nothing to crop."""
    workflow = _chunk(ADAPTION_CHUNK)["workflow"]
    batch = workflow["211"]["inputs"]
    assert batch["images.image0"] == ["101", 0]
    for n, node_id in FIT_NODE.items():
        assert batch[f"images.image{n - 1}"] == [node_id, 0]
        fit = workflow[node_id]
        assert fit["class_type"] == "ImageScale"
        assert fit["inputs"]["image"] == [LOAD_NODE[n], 0]
        assert fit["inputs"]["crop"] == "disabled"
        assert (fit["inputs"]["width"], fit["inputs"]["height"]) == (["300", 0], ["300", 1])
    assert workflow["300"]["inputs"]["image"] == ["101", 0]


def test_the_reference_latents_take_the_images_as_loaded():
    latents = _chunk(IMAGE_CHUNK)["workflow"]["201"]["inputs"]
    for n, node_id in LOAD_NODE.items():
        assert latents[f"images.image{n - 1}"] == [node_id, 0]


def test_the_upsampler_has_no_output_cap_below_64k():
    workflow = _chunk(ADAPTION_CHUNK)["workflow"]
    source, _ = workflow["212"]["inputs"]["max_length"]
    assert workflow[source]["inputs"]["value"] >= 65536


def test_a_workflow_with_a_language_model_has_no_read_timeout():
    from schemas.engine.backend_router import _completion_timeout
    from config import COMFYUI_TIMEOUT
    workflow = _chunk(ADAPTION_CHUNK)["workflow"]
    assert _completion_timeout(workflow, {}) is None
    assert _completion_timeout(workflow, {"timeout": 30}) is None
    image_only = _chunk(IMAGE_CHUNK)["workflow"]
    assert _completion_timeout(image_only, {}) == COMFYUI_TIMEOUT
    assert _completion_timeout(image_only, {"timeout": 30}) == 30


@pytest.mark.parametrize("path", (IMAGE_CHUNK, ADAPTION_CHUNK))
def test_every_slot_the_chunk_maps_is_a_slot_the_route_carries(path):
    from schemas.engine.multi_image_params import MULTI_IMAGE_KEYS
    mapped = {key for key in _chunk(path)["input_mappings"] if key.startswith("input_image")}
    assert mapped == set(MULTI_IMAGE_KEYS)


def test_the_route_reads_the_slots_in_order_and_leaves_empty_ones_out():
    from schemas.engine.multi_image_params import multi_images_from
    request = {"input_image3": "c", "input_image1": "a", "input_image2": "", "input_image10": "j", "prompt": "p"}
    assert list(multi_images_from(request).items()) == [("input_image1", "a"), ("input_image3", "c"), ("input_image10", "j")]
