#!/usr/bin/env python3
"""
An injected LoRA reaches the TEXT ENCODERS, not only the transformer.

Why this test exists. `_inject_lora_nodes` found the CLIP source by the class
name `DualCLIPLoader`. Later `output_image_sd35_large.json` swapped that
loader for `TripleCLIPLoader`, to stop dropping the CLIP-L prompt; the injector
was not swapped with it. From then until 2026-08-29 the chain fell back to the
checkpoint's CLIP output — and `sd3.5_large.safetensors` carries no text encoder
at all — so the LoraLoader received `clip=None`, and the text-encode nodes went
on reading the untouched loader, because only `model` consumers were rewired.

The cost was the ENCODER HALF of every adapter, on every ComfyUI run:
`sd35_destroyednegative.safetensors` holds 1923 tensors, 792 of them `lora_te1`
and `lora_te2`. Thirty days of ComfyUI's log held 3168 lines `lora key not
loaded`, every one `lora_te*` and not one `lora_unet*`. Those are the weights
that bind a trigger word to what was trained.

Nothing failed while it was broken — an image came out, and it was the image of
an adapter running at 59 %. That is what this test is for.

Run: python3 -m pytest devserver/tests/test_lora_injection.py -q
"""
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "devserver"))

from schemas.engine.backend_router import BackendRouter  # noqa: E402

CHUNKS = REPO / "devserver/schemas/chunks"


def _workflow(name: str) -> dict:
    chunk = json.loads((CHUNKS / name).read_text(encoding="utf-8"))
    return json.loads(json.dumps(chunk.get("workflow") or chunk))


def _inject(workflow: dict, strength: float = 0.7) -> dict:
    router = BackendRouter.__new__(BackendRouter)
    return router._inject_lora_nodes(
        workflow, [{"name": "sd35_test.safetensors", "strength": strength}]
    )


def _nodes(workflow: dict, class_type: str) -> list:
    return [
        node_id
        for node_id, node in workflow.items()
        if isinstance(node, dict) and node.get("class_type") == class_type
    ]


def _encoders(workflow: dict) -> list:
    """The text encoders, found by the WIRE: the nodes the samplers read their
    `positive` and `negative` conditioning from.

    By class name they were `CLIPTextEncodeSD3` until 10.09.2026 (5a8a6338),
    when every SD 3.5 graph here took the platform's own `AI4ArtsEdSD3TextEncode`
    instead; the test kept the old name and stopped at its own precondition
    while the injection was fine. What an encoder IS in this graph is what
    conditions the sampler, so that is what this looks for.
    """
    found = []
    for node_id in _nodes(workflow, "KSampler"):
        for key in ("positive", "negative"):
            wired = workflow[node_id]["inputs"].get(key)
            if isinstance(wired, list) and len(wired) == 2 and wired[0] not in found:
                found.append(wired[0])
    return found


def _clip_chain(workflow: dict, node_id: str) -> list:
    """The nodes a CLIP passes through on its way to `node_id`, nearest first.

    A graph puts nodes between the loader and its text encoders - since
    09.09.2026 every SD 3.5 graph here reads its CLIP through a
    `T5TokenizerOptions`. What this test is about is the chain, not one hop:
    the adapter has to stand somewhere on it.
    """
    passed = []
    wired = workflow[node_id]["inputs"].get("clip")
    while isinstance(wired, list) and len(wired) == 2 and wired[0] in workflow:
        passed.append(wired[0])
        wired = workflow[wired[0]]["inputs"].get("clip")
    return passed


def test_text_encoders_read_the_lora_chain():
    """The regression itself: every consumer of CLIP goes through the adapter."""
    out = _inject(_workflow("output_image_sd35_large.json"))

    chain = _nodes(out, "LoraLoader")
    assert chain, "no LoraLoader was injected"
    last = chain[-1]

    encoders = _encoders(out)
    assert encoders, "the chunk has no text encoders — this test would pass vacuously"
    for node_id in encoders:
        assert last in _clip_chain(out, node_id), (
            f"node {node_id} reads CLIP over {_clip_chain(out, node_id)} "
            f"instead of the LoRA chain — its `lora_te*` weights are dropped"
        )


def test_the_chain_reads_the_real_loader_not_the_checkpoint():
    """The first link takes CLIP from whatever actually feeds the encoders.

    By the WIRE and not by the loader's name, so a chunk that swaps
    TripleCLIPLoader for another loader keeps working.
    """
    workflow = _workflow("output_image_sd35_large.json")
    encoder = _encoders(workflow)[0]
    loader = _clip_chain(workflow, encoder)[-1]

    out = _inject(workflow)
    first = _nodes(out, "LoraLoader")[0]
    assert out[first]["inputs"]["clip"] == [loader, 0], (
        f"the chain reads {out[first]['inputs']['clip']}, but the encoders were "
        f"fed from node {loader}"
    )


def test_the_transformer_still_goes_through_the_chain():
    """What already worked has to keep working."""
    out = _inject(_workflow("output_image_sd35_large.json"))
    last = _nodes(out, "LoraLoader")[-1]
    samplers = _nodes(out, "KSampler")
    assert samplers, "no sampler in the chunk"
    for node_id in samplers:
        assert out[node_id]["inputs"]["model"] == [last, 0]


@pytest.mark.parametrize("strength", [0.0, 0.7, 1.0])
def test_one_strength_reaches_both_halves(strength):
    """Scale 0 is the reference run of the LoRA surfaces, and it is only a
    reference if BOTH strengths are zero — ComfyUI's `LoraLoader.load_lora`
    returns model and clip untouched exactly then, before the file is opened."""
    out = _inject(_workflow("output_image_sd35_large.json"), strength)
    node = out[_nodes(out, "LoraLoader")[0]]["inputs"]
    assert node["strength_model"] == strength
    assert node["strength_clip"] == strength
