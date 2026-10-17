#!/usr/bin/env python3
"""Guard: SD 3.5 is conditioned on the same text on both backends.

Two settings decide how much text an SD 3.5 model actually receives, and both
are invisible in the picture parameters:

  1. How many positions the T5 stream carries. The Diffusers backend passes
     max_sequence_length=512 wherever it generates a picture, so a prompt has
     always reached the transformer on 77 CLIP + 512 T5 positions. ComfyUI's
     T5XXLTokenizer starts at min_length=77 and grows only with the prompt: a
     short prompt arrives on 154 positions instead of 589 unless the graph says
     otherwise. The graph says so through a T5TokenizerOptions node in front of
     the text encoders.

  2. What an empty negative prompt encodes to. `empty_padding: "none"` leaves
     the token lists empty and SD3ClipModel puts zeros in their place; the
     Diffusers twins hand `negative_prompt or None` to a pipeline that encodes
     the empty string through all three encoders. At cfg 4.5 the two are
     different pictures, so every graph here sets "empty_prompt".

Both were silently lost when the image path moved to ComfyUI. This test holds
them for every SD 3.5 graph the platform submits, and holds the number against
the Diffusers backend so the two cannot drift apart again.

The fusion line is the one exception, and it is a deliberate one: its Diffusers
side runs T5 at the prompt's own length ON PURPOSE, to reproduce what ComfyUI
did (`diffusers_backend.py::generate_image_with_fusion`, "min_length=77 as in
ComfyUI; beyond that the text decides"). Those graphs are named in FUSION below,
and the test still requires them to be named - a new graph cannot join them by
accident.

Run: pytest devserver/tests/test_sd35_conditioning_length.py
"""

import inspect
import json
import logging
import re
import sys

import pytest

from file_modules import DEVSERVER, load_module

CHUNKS = DEVSERVER / "schemas" / "chunks"
GPU_SERVICE = DEVSERVER.parent / "gpu_service" / "services"
PASSES_A_LENGTH = (GPU_SERVICE / "diffusers_backend.py",)

# The loaders that put SD 3.5's text encoders into a graph. A `type` of "sd3"
# marks the two-file and one-file loaders; TripleCLIPLoader is SD 3.5 by itself.
SD3_LOADERS = ("TripleCLIPLoader", "DualCLIPLoader", "CLIPLoader")

# The fusion line. Its Diffusers counterpart runs T5 at the prompt's own length
# deliberately, so putting these graphs on 512 would break the pairing rather
# than restore it. Each entry says which instrument it belongs to.
FUSION = {
    "legacy_surrealization.json": "Surrealizer, legacy workflow (surrealization_legacy)",
    "output_vector_fusion_clip_sd35.json": "Vector fusion (vector_fusion_generation)",
    "dual_encoder_fusion_image.json": "Dual encoder fusion (dual_encoder_fusion)",
}

# What a builder gets asked for, by parameter name. A chunk whose builder takes
# a name that is missing here fails loudly rather than being skipped.
ARGUMENTS = {
    "alpha": 0.0,
    "backbone": "sd35",
    "capture_every_n": 2,
    "cfg": 4.5,
    "checkpoint": "OfficialStableDiffusion/sd3.5_large.safetensors",
    "clip_prompt": "a house",
    "concepts": [{"prompt": "a house", "weight": 1.0}],
    "encoder": "all",
    "every_n": 1,
    # The surrealizer chunk's fusion line (since 876ee3ba, 2026-09-15): the
    # three factors replace alpha/strategy. None means the chunk builds the
    # alpha/strategy fusion instead, which is the graph this file guards for
    # the FUSION set; the factors graph is exercised by name below.
    "factors": None,
    "height": 1024,
    "layers_text": "3,9,17",
    "negative_prompt": "",
    "normalize_weights": True,
    "prompt": "a house",
    "prompt_a": "a house",
    "prompt_b": "a hut",
    "prompt_c": "a tent",
    "sampler_name": "euler",
    "scale_add": 1.0,
    "scale_sub": 1.0,
    "scheduler": "normal",
    "seed": 1,
    "shift": 3.0,
    "steps": 25,
    "strategy": "centered_fade",
    "t5_prompt": "a house",
    "transfer": False,
    "transfer_dims": "",
    "width": 1024,
}


def _t5_length():
    """The platform's number, read from the module the graphs build with."""
    sys.path.insert(0, str(DEVSERVER))
    from schemas.engine.comfyui_chunk_support import T5_LENGTH
    return T5_LENGTH


def _load(path):
    sys.path.insert(0, str(DEVSERVER))
    return load_module(f"chunk_{path.stem}", path)


def _built(path):
    """Every graph a ComfyUI chunk builds, named after its arguments."""
    module = _load(path)
    builder = getattr(module, "_build_workflow", None)
    if builder is None:
        return {}
    parameters = inspect.signature(builder).parameters
    unknown = [n for n in parameters if n not in ARGUMENTS]
    assert not unknown, (
        f"{path.name}: _build_workflow takes {unknown}, which this test cannot "
        f"fill. Add the name to ARGUMENTS."
    )
    kwargs = {n: ARGUMENTS[n] for n in parameters}
    if "backbone" in parameters:
        return {
            f"{path.name} (sd35)": builder(**{**kwargs, "backbone": "sd35"}),
            f"{path.name} (sdxl)": builder(**{**kwargs, "backbone": "sdxl"}),
        }
    return {path.name: builder(**kwargs)}


def is_encoder(node):
    """Whether this node turns text into conditioning."""
    return str(node.get("class_type", "")).startswith(
        ("CLIPTextEncode", "AI4ArtsEdSD3Encode", "AI4ArtsEdSD3TextEncode"))


def drives_sd3(workflow):
    """Whether this graph loads SD 3.5's text encoders."""
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        kind = node.get("class_type")
        if kind == "TripleCLIPLoader":
            return True
        if kind in SD3_LOADERS and node.get("inputs", {}).get("type") == "sd3":
            return True
    return False


def graphs():
    """Every SD 3.5 graph the platform submits to ComfyUI, by name."""
    out = {}
    for path in sorted(CHUNKS.glob("*.json")):
        content = json.loads(path.read_text())
        workflow = content.get("workflow") or content.get("legacy_workflow")
        if content.get("backend_type") == "comfyui" and workflow:
            out[path.name] = workflow
    for path in sorted(CHUNKS.glob("*_comfyui.py")):
        out.update(_built(path))
    return {name: workflow for name, workflow in out.items() if drives_sd3(workflow)}


ALL_GRAPHS = graphs()
CONDITIONED = {n: w for n, w in ALL_GRAPHS.items() if n.split(" (")[0] not in FUSION}


def test_the_platform_has_sd35_graphs_on_comfyui():
    """A test that found nothing would pass every assertion below."""
    assert len(CONDITIONED) >= 7, sorted(CONDITIONED)


def test_the_fusion_graphs_are_all_still_there():
    """A name in FUSION that no longer exists would silently exempt nothing."""
    found = {n.split(" (")[0] for n in ALL_GRAPHS}
    assert set(FUSION) <= found, sorted(set(FUSION) - found)


@pytest.mark.parametrize("name", sorted(CONDITIONED))
def test_every_encoder_reads_its_clip_through_the_t5_length(name):
    workflow = CONDITIONED[name]
    encoders = [i for i, n in workflow.items() if isinstance(n, dict) and is_encoder(n)]
    assert encoders, f"{name}: no text encoder - this graph would pass vacuously"
    for node_id in encoders:
        wired = workflow[node_id]["inputs"].get("clip")
        assert isinstance(wired, list) and len(wired) == 2, (
            f"{name}: node {node_id} takes no CLIP from a node"
        )
        source = workflow.get(wired[0], {})
        assert source.get("class_type") == "T5TokenizerOptions", (
            f"{name}: node {node_id} reads its CLIP from "
            f"{source.get('class_type')} instead of T5TokenizerOptions, so its "
            f"T5 stream is as long as the prompt makes it"
        )
        assert source["inputs"]["min_length"] == _t5_length(), (
            f"{name}: node {node_id} is conditioned on "
            f"{source['inputs']['min_length']} T5 positions, the Diffusers side "
            f"on {_t5_length()}"
        )


@pytest.mark.parametrize("name", sorted(CONDITIONED))
def test_an_empty_negative_goes_through_all_three_encoders(name):
    for node_id, node in CONDITIONED[name].items():
        if not isinstance(node, dict) or node.get("class_type") != "CLIPTextEncodeSD3":
            continue
        assert node["inputs"].get("empty_padding") == "empty_prompt", (
            f"{name}: node {node_id} pads an empty prompt with "
            f"{node['inputs'].get('empty_padding')!r}; the Diffusers twin encodes "
            f"the empty string through all three encoders"
        )


@pytest.mark.parametrize("source", PASSES_A_LENGTH, ids=lambda p: p.name)
def test_the_number_is_the_one_the_diffusers_side_passes(source):
    """Both sides carry 512 as a literal; neither may move without the other."""
    text = source.read_text()
    passed = {int(n) for n in re.findall(
        r"""max_sequence_length["']?\s*[:=]\s*(\d+)""", text)}
    assert passed == {_t5_length()}, (
        f"{source.name} conditions on {sorted(passed)} T5 positions, the ComfyUI "
        f"graphs on {_t5_length()}"
    )


def test_the_only_computed_length_is_the_fusion_one():
    """A length in a variable hides from the check above; there may be one.

    Two computed lengths live in the fusion path, both on purpose: the natural
    length (`t5_natural_len`, there since the gate was written) reproduces
    ComfyUI's own tokenization, and the research length (`_t5_max_len`, the
    t5len= option of Folge-Reihe I, since 56c23507 2026-09-13) sets a length a
    study asks for. Both stay in generate_image_with_fusion; nowhere else may
    a length hide in a variable."""
    text = (GPU_SERVICE / "diffusers_backend.py").read_text()
    names = set(re.findall(r"max_sequence_length\s*=\s*([A-Za-z_]\w*)", text))
    assert names == {"t5_natural_len", "_t5_max_len"}, (
        f"{sorted(names)} pass a computed T5 length. Only the fusion path may - "
        f"it reproduces ComfyUI's own tokenization on purpose, and the research "
        f"option t5len= sets a length a study asks for."
    )


# ---------------------------------------------------------------------------
# And the third thing that decides what the encoders receive: whether a bracket
# in the prompt is a bracket. ComfyUI reads `(a phrase)` as a weight of 1.1 and
# drops the characters; Diffusers encodes them. `as_written` escapes them on the
# way to SD 3.5's encoders, and leaves every other node alone.

def _as_written():
    sys.path.insert(0, str(DEVSERVER))
    from my_app.services.comfyui_ws_client import as_written
    return as_written


def _node(kind, **inputs):
    return {"class_type": kind, "inputs": inputs}


def test_brackets_reach_sd35_as_brackets():
    written = "a house (built 1920) in a forest"
    out = _as_written()({
        "1": _node("CLIPTextEncodeSD3", clip_l=written, clip_g=written, t5xxl=written),
        "2": _node("AI4ArtsEdSD3Encode", text=written),
    })
    for node_id, fields in (("1", ("clip_l", "clip_g", "t5xxl")), ("2", ("text",))):
        for field in fields:
            assert out[node_id]["inputs"][field] == (
                r"a house \(built 1920\) in a forest"
            ), (node_id, field, out[node_id]["inputs"][field])


def test_sdxl_keeps_the_weight_syntax_it_always_had():
    """SDXL never ran on Diffusers here, so nothing about it is being restored."""
    written = "a house (built 1920) in a forest"
    out = _as_written()({"1": _node("CLIPTextEncode", text=written)})
    assert out["1"]["inputs"]["text"] == written


def test_a_prompt_without_brackets_is_left_alone():
    written = "a house in a forest"
    graph = {"1": _node("CLIPTextEncodeSD3", clip_l=written, clip_g=written, t5xxl=written)}
    out = _as_written()(graph)
    assert out["1"] is graph["1"]


def test_the_workflow_the_caller_holds_is_not_changed():
    """What the platform records and shows stays the prompt its author wrote."""
    written = "a house (built 1920) in a forest"
    graph = {"1": _node("CLIPTextEncodeSD3", clip_l=written, clip_g=written, t5xxl=written)}
    _as_written()(graph)
    assert graph["1"]["inputs"]["clip_l"] == written


def test_every_text_field_of_the_encoders_is_covered():
    """A field left out would carry the weight syntax through unnoticed."""
    sys.path.insert(0, str(DEVSERVER))
    from my_app.services.comfyui_ws_client import SD35_TEXT_FIELDS
    for name, workflow in CONDITIONED.items():
        for node_id, node in workflow.items():
            if not isinstance(node, dict) or not is_encoder(node):
                continue
            fields = SD35_TEXT_FIELDS.get(node["class_type"])
            assert fields, f"{name}: {node['class_type']} has no text fields declared"
            carries = {k for k, v in node["inputs"].items() if isinstance(v, str)}
            assert carries <= set(fields) | {"empty_padding"}, (
                f"{name}: node {node_id} carries text in {sorted(carries - set(fields))}"
            )


# ---------------------------------------------------------------------------
# And the weights behind those encoders. The Diffusers path loaded
# stable-diffusion-3.5-large's text_encoder_3 in float16, so the standard graphs
# read t5xxl_fp16.safetensors. The fusion line reproduces a ComfyUI workflow
# that has always loaded the F8_E4M3 file, and LTX-Video loads that same file by
# name, so both files stay on disk (docs/installation/MODELS_REQUIRED.md).

T5_FP16 = "t5xxl_fp16.safetensors"
T5_FP8 = "t5xxl_enconly.safetensors"


def t5_files(workflow):
    """Every T5 weight file the CLIP loaders of a graph name."""
    found = set()
    for node in workflow.values():
        if not isinstance(node, dict) or node.get("class_type") not in SD3_LOADERS:
            continue
        for field, value in node.get("inputs", {}).items():
            if field.startswith("clip_name") and isinstance(value, str) and "t5" in value:
                found.add(value)
    return found


@pytest.mark.parametrize("name", sorted(CONDITIONED))
def test_the_standard_graphs_read_the_fp16_t5(name):
    assert t5_files(CONDITIONED[name]) == {T5_FP16}, (
        f"{name} names {sorted(t5_files(CONDITIONED[name]))}. The Diffusers path "
        f"loaded these exact weights, byte for byte; {T5_FP8} holds the same 220 "
        f"encoder tensors in F8_E4M3."
    )


@pytest.mark.parametrize("name", sorted(FUSION))
def test_the_fusion_graphs_keep_the_file_they_reproduce(name):
    assert t5_files(ALL_GRAPHS[name]) == {T5_FP8}, (
        f"{name} names {sorted(t5_files(ALL_GRAPHS[name]))}. This graph rebuilds "
        f"a ComfyUI workflow whose loaders are the reference, and its Diffusers "
        f"counterpart mirrors them: {FUSION[name]}."
    )


def test_the_shared_loader_names_the_fp16_t5():
    """triple_clip_loader() puts these three names into every Latent Lab graph."""
    sys.path.insert(0, str(DEVSERVER))
    from schemas.engine.comfyui_chunk_support import SD35_TEXT_ENCODERS
    assert SD35_TEXT_ENCODERS[2] == T5_FP16, SD35_TEXT_ENCODERS


# ---------------------------------------------------------------------------
# And the fourth thing that decides what the encoders receive: how many blocks
# of 77 CLIP gets to see. ComfyUI's SDTokenizer emits ceil(n/75) of them for a
# longer prompt and SD3ClipModel lays them end to end; the Diffusers twin cut at
# 77 and let T5 carry the rest, which is what sd35_large.json's notes field
# prescribes. `AI4ArtsEdSD3TextEncode` restores that cut, and it does it inside
# ComfyUI on the token lists, with the tokenizer that then encodes them.

OWN_ENCODE = "AI4ArtsEdSD3TextEncode"
COMFY_ENCODE = "CLIPTextEncodeSD3"
NODE_FILE = DEVSERVER.parent / "comfyui_nodes" / "ai4artsed_sd3_conditioning.py"

# The SD 3.5 graphs that condition CLIP through plain `CLIPTextEncode`. All three
# belong to the fusion line, which reproduces an original ComfyUI workflow: that
# is what those graphs ARE, and the window is no part of it. They are named here
# so that a new graph cannot join them by accident, and each entry says how its
# text reaches the encoder.
FUSION_LINE = {
    "legacy_surrealization.json":
        "its CLIP text is made inside ComfyUI by ai4artsed_prompt_interception",
    "output_vector_fusion_clip_sd35.json":
        "its prompt parts sit on PrimitiveString nodes, and one CLIPTextEncode "
        "feeds CLIP and T5 from the same field",
    "dual_encoder_fusion_image.json":
        "node 5 encodes clip_l alone and node 6 t5xxl alone",
}


def test_the_fusion_graphs_are_all_still_named():
    """A graph leaves this list by being moved onto the node, never by being
    renamed."""
    stems = {n.split(" (")[0] for n in ALL_GRAPHS}
    assert set(FUSION_LINE) <= stems, sorted(set(FUSION_LINE) - stems)


@pytest.mark.parametrize("name", sorted(ALL_GRAPHS))
def test_no_graph_encodes_sd35_through_comfyuis_own_node(name):
    """ComfyUI's own `CLIPTextEncodeSD3` hands CLIP every block the prompt makes.

    Over ALL_GRAPHS on purpose: CONDITIONED drops the fusion line for a reason
    belonging to the T5 length, and those three graphs are exactly the ones this
    question is open in, so inheriting that exemption would have hidden them.
    """
    stem = name.split(" (")[0]
    if stem in FUSION_LINE:
        pytest.skip(FUSION_LINE[stem])
    kinds = {node.get("class_type") for node in ALL_GRAPHS[name].values()
             if isinstance(node, dict)}
    assert COMFY_ENCODE not in kinds, (
        f"{name} encodes through {COMFY_ENCODE}, which gives CLIP as many blocks "
        f"of 77 as the prompt makes. Use {OWN_ENCODE}."
    )


@pytest.mark.parametrize("name", sorted(CONDITIONED))
def test_every_encoder_of_every_graph_holds_the_clip_window(name):
    """A graph reaches the window through one of our two nodes, or not at all."""
    stem = name.split(" (")[0]
    if stem in FUSION_LINE:
        pytest.skip(FUSION_LINE[stem])
    for node_id, node in CONDITIONED[name].items():
        if not isinstance(node, dict) or not is_encoder(node):
            continue
        assert node["class_type"] in (OWN_ENCODE, "AI4ArtsEdSD3Encode"), (
            f"{name}: node {node_id} is a {node['class_type']}, which holds no "
            f"window."
        )


def test_the_shared_encoder_builder_names_our_node():
    """Every graph that takes its negative encoder from the shared module gets
    the window with it."""
    source = (DEVSERVER / "schemas" / "engine" / "comfyui_chunk_support.py").read_text(
        encoding="utf-8")
    assert f'"class_type": "{OWN_ENCODE}"' in source
    assert COMFY_ENCODE not in source


def test_the_window_is_one_block():
    """SD 3.5 was trained on one block of 77 positions at each CLIP encoder."""
    source = NODE_FILE.read_text(encoding="utf-8")
    assert re.search(r"^CLIP_BLOCKS = 1$", source, re.M), "CLIP_BLOCKS moved off 1"


def test_the_cut_runs_on_the_token_lists_and_spares_t5():
    """On `l` and `g`, never on `t5xxl`: T5 is the encoder that carries the
    detail, and the graphs put it on 512 positions."""
    source = NODE_FILE.read_text(encoding="utf-8")
    body = re.split(r"\n(?:def |class )",
                    source.split("def _within_clip_window(tokens):")[1])[0]
    assert 'for stream in ("l", "g"):' in body, body[:400]
    assert "t5xxl" not in body, body[:400]


def test_both_encoding_paths_hold_the_window():
    """The platform's plain encode and the Latent Lab's per-encoder one make the
    same cut, so a null run of Concept Algebra and an ordinary SD 3.5 picture are
    made the same way."""
    source = NODE_FILE.read_text(encoding="utf-8")
    for fn in ("def encode(self, clip, clip_l, clip_g, t5xxl, empty_padding):",
               "def _encode_parts(clip, text, empty_padding=\"none\"):"):
        body = re.split(r"\n(?:def |class )", source.split(fn)[1])[0]
        assert "_within_clip_window(tokens)" in body, fn


def test_the_node_is_registered_under_the_name_the_graphs_use():
    source = NODE_FILE.read_text(encoding="utf-8")
    assert f'"{OWN_ENCODE}": {OWN_ENCODE},' in source
    assert f'"{OWN_ENCODE}": "AI4ArtsEd SD3 Text Encode' in source
