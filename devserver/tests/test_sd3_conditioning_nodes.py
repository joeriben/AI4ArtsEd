#!/usr/bin/env python3
"""What the SD 3.5 conditioning nodes do with the parts they hand around.

Stage 4 of the ComfyUI migration. The
node family carries the arithmetic three Latent Lab instruments need, and two of
its properties are the ones a reader of the surface relies on:

  * an empty prompt contributes NOTHING, rather than the encoding of the empty
    string, which is a vector like any other and would move the picture;
  * the distance the surface prints is the distance the Diffusers instrument
    printed - measured over the assembled token stream, pooled left out
    (gpu_service/services/embedding_analyzer.py).

The tests reach the node file directly and put a stand-in class where ComfyUI's
`SD3ClipModel` would be: the node asks `isinstance` of it, and importing the real
one pulls in comfy.model_management, which reads sys.argv and picks a device.

Run: pytest devserver/tests/test_sd3_conditioning_nodes.py
"""

import sys
import types

import pytest

torch = pytest.importorskip("torch")

from file_modules import DEVSERVER, REPO, load_module

NODE_FILE = REPO / "comfyui_nodes" / "ai4artsed_sd3_conditioning.py"
CHUNKS = DEVSERVER / "schemas" / "chunks"

sys.path.insert(0, str(DEVSERVER))


class StandInSD3ClipModel:
    """Where ComfyUI's SD3ClipModel stands in the node's family check."""


for _name in ("comfy", "comfy.text_encoders", "comfy.text_encoders.sd3_clip"):
    sys.modules.setdefault(_name, types.ModuleType(_name))
sys.modules["comfy.text_encoders.sd3_clip"].SD3ClipModel = StandInSD3ClipModel

N = load_module("ai4artsed_sd3_conditioning", NODE_FILE)


class FakeCLIP:
    """A CLIP object with the three encoders present and no tokenizer at all.

    `tokenize` raising is the assertion: a path that reaches it has not taken the
    short circuit the test is about.
    """

    def __init__(self, model):
        self.cond_stage_model = model
        self.layer_idx = None

    def tokenize(self, text):
        raise AssertionError(f"the encoders were asked to encode {text!r}")


def _sd3_clip():
    model = StandInSD3ClipModel()
    model.clip_l, model.clip_g, model.t5xxl = object(), object(), object()
    return FakeCLIP(model)


def _parts(clip_seq=77, t5_seq=154, seed=0):
    """Parts the way the three encoders write them: two widths and two lengths."""
    g = torch.Generator().manual_seed(seed)
    return {
        "clip_l": torch.randn((1, clip_seq, 768), generator=g),
        "clip_g": torch.randn((1, clip_seq, 1280), generator=g),
        "t5": torch.randn((1, t5_seq, 4096), generator=g),
        "pooled_l": torch.randn((1, 768), generator=g),
        "pooled_g": torch.randn((1, 1280), generator=g),
    }


def _algebra(a, b, c, encoder="all", sub=1.0, add=1.0):
    answer = N.AI4ArtsEdSD3Algebra().combine(a, b, c, encoder, sub, add)
    return answer["result"]


# --- an empty prompt --------------------------------------------------------

def test_an_empty_prompt_contributes_nothing():
    empty = N._empty_parts()
    assert empty["clip_l"].shape == (1, 0, 768)
    assert empty["clip_g"].shape == (1, 0, 1280)
    assert empty["t5"].shape == (1, 0, 4096)
    assert torch.equal(empty["pooled_l"], torch.zeros((1, 768)))
    assert torch.equal(empty["pooled_g"], torch.zeros((1, 1280)))


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_an_empty_prompt_never_reaches_the_encoders(text):
    parts = N._encode_parts(_sd3_clip(), text)
    assert set(N.PART_KEYS) <= parts.keys()
    assert parts["filled"] == {"clip_l": 0, "clip_g": 0, "t5": 0}


def test_b_left_empty_leaves_a_plus_c():
    """The defect this is against: `A - 1*enc("") + 1*C` moves the picture by the
    encoding of the empty string, which the reader never asked for."""
    a, c = _parts(seed=1), _parts(seed=2)
    out, _l2 = _algebra(a, N._empty_parts(), c)
    for key in ("clip_l", "clip_g", "t5", "pooled_l", "pooled_g"):
        assert torch.equal(out[key], a[key] + c[key]), key


def test_a_run_that_changes_nothing_reports_exactly_zero():
    a = _parts(seed=3)
    out, l2 = _algebra(a, N._empty_parts(), N._empty_parts())
    for key in N.PART_KEYS:
        assert torch.equal(out[key], a[key]), key
    assert l2 == 0.0


def test_everything_empty_still_conditions_on_seventy_seven_positions():
    """What ComfyUI answers with when all three token lists are empty."""
    cond, pooled = N._assemble(N._empty_parts())
    assert cond.shape == (1, 77, 4096)
    assert not cond.any()
    assert pooled.shape == (1, 2048)
    assert not pooled.any()


# --- the distance -----------------------------------------------------------

def test_the_distance_is_the_one_the_diffusers_instrument_reported():
    """Twin: `(result - embed_a).norm(p=2)` on the ASSEMBLED token stream
    (gpu_service/services/embedding_analyzer.py). Doing the arithmetic on the
    parts and assembling afterwards has to come out at the same number as
    assembling first and doing the arithmetic on the assembled tensors."""
    a, b, c = _parts(seed=4), _parts(seed=5), _parts(seed=6)
    _out, l2 = _algebra(a, b, c, encoder="all", sub=0.8, add=1.3)

    cond_a, _ = N._assemble(a)
    cond_b, _ = N._assemble(b)
    cond_c, _ = N._assemble(c)
    as_the_twin_did = cond_a - 0.8 * cond_b + 1.3 * cond_c
    expected = float((as_the_twin_did - cond_a).norm(p=2))

    assert l2 == pytest.approx(expected, rel=1e-5)


def test_the_distance_leaves_the_pooled_vector_out():
    """Same token streams, another pooled vector: the same distance. Folding the
    pooled deltas in would give the twin's label to another quantity."""
    a, b, c = _parts(seed=7), _parts(seed=8), _parts(seed=9)
    loud = dict(c)
    loud["pooled_l"] = c["pooled_l"] * 100
    loud["pooled_g"] = c["pooled_g"] * 100

    quiet_out, quiet_l2 = _algebra(a, b, c)
    loud_out, loud_l2 = _algebra(a, b, loud)

    assert loud_l2 == pytest.approx(quiet_l2, rel=1e-6)
    assert not torch.equal(loud_out["pooled_l"], quiet_out["pooled_l"])


def test_t5_alone_leaves_the_pooled_vector_where_a_put_it():
    a, b, c = _parts(seed=10), _parts(seed=11), _parts(seed=12)
    out, _l2 = _algebra(a, b, c, encoder="t5")
    assert torch.equal(out["pooled_l"], a["pooled_l"])
    assert torch.equal(out["pooled_g"], a["pooled_g"])
    assert torch.equal(out["clip_l"], a["clip_l"])
    assert not torch.equal(out["t5"], a["t5"])


# --- which text encoders these nodes are for --------------------------------

def test_a_text_encoder_of_another_family_is_refused():
    """HiDream carries clip_l, clip_g and t5xxl too, reads CLIP-L at another
    layer and conditions on a fourth stream this assembly would drop. Testing
    the attributes let it through without an error and with a wrong picture."""

    class HiDreamTEModel:
        pass

    other = HiDreamTEModel()
    other.clip_l, other.clip_g, other.t5xxl = object(), object(), object()
    with pytest.raises(RuntimeError, match="HiDreamTEModel"):
        N._encode_parts(FakeCLIP(other), "a house")


@pytest.mark.parametrize("missing", ["clip_l", "clip_g", "t5xxl"])
def test_a_clip_without_all_three_encoders_is_refused(missing):
    clip = _sd3_clip()
    setattr(clip.cond_stage_model, missing, None)
    with pytest.raises(RuntimeError, match=missing):
        N._encode_parts(clip, "a house")


# --- the assembly -----------------------------------------------------------

def test_the_assembly_puts_clip_in_front_of_t5():
    parts = _parts(clip_seq=77, t5_seq=154, seed=13)
    cond, pooled = N._assemble(parts)
    assert cond.shape == (1, 77 + 154, 4096)
    assert torch.equal(cond[0, 0, :768], parts["clip_l"][0, 0])
    assert torch.equal(cond[0, 0, 768:2048], parts["clip_g"][0, 0])
    assert not cond[0, 0, 2048:].any()
    assert torch.equal(cond[0, 77:], parts["t5"][0])
    assert pooled.shape == (1, 2048)


def test_a_shorter_prompt_is_filled_out_rather_than_cutting_a_short():
    """A is the prompt whose picture this is; cutting all three to the shortest
    would shorten it too. Where B does not reach, it contributes nothing."""
    a = _parts(t5_seq=231, seed=14)
    b = _parts(t5_seq=154, seed=15)
    out, _l2 = _algebra(a, b, N._empty_parts(), encoder="t5", sub=1.0, add=0.0)
    assert out["t5"].shape == a["t5"].shape
    assert torch.equal(out["t5"][:, 154:], a["t5"][:, 154:])


# --- the node and the chunk agree -------------------------------------------

def test_the_node_offers_the_default_the_chunk_asks_for():
    chunk = load_module("concept_algebra_comfyui",
                  CHUNKS / "output_image_concept_algebra_comfyui.py")
    offered = N.AI4ArtsEdSD3Algebra.INPUT_TYPES()["required"]["encoder"]
    assert offered[1]["default"] == chunk.DEFAULTS["algebra_encoder"]
    assert chunk.DEFAULTS["algebra_encoder"] in N.ENCODERS


# --- one place for the two loader nodes (docs/ELEMENT_STRUCTURE_REGISTRY.md) --

USES_THE_SHARED_LOADERS = [
    "output_image_attention_cartography_comfyui.py",
    "output_image_concept_algebra_comfyui.py",
    "output_image_composable_diffusion_comfyui.py",
    "output_image_feature_probing_comfyui.py",
    "output_image_surrealizer_comfyui.py",
    "output_image_denoising_archaeology_comfyui.py",
]

# Denoising Archaeology was the first ComfyUI chunk of the Latent Lab and carried
# private copies of checkpoint_for, checkpoint_available, final_image and the two
# loader nodes until 2026-10-10. The list stays, empty, for the next one.
BUILDS_THEM_PRIVATELY: list[str] = []


@pytest.mark.parametrize("name", USES_THE_SHARED_LOADERS)
def test_the_sd35_chunks_read_the_loader_nodes_from_one_place(name):
    text = (CHUNKS / name).read_text(encoding="utf-8")
    assert "triple_clip_loader(" in text, f"{name} does not use the shared loader"
    assert "checkpoint_loader(checkpoint" in text, f"{name} does not use the shared loader"
    assert "clip_name1" not in text, (
        f"{name} builds a TripleCLIPLoader of its own again "
        f"(docs/ELEMENT_STRUCTURE_REGISTRY.md)")


def test_the_chunk_that_still_builds_them_privately_is_the_declared_one():
    private = [p.name for p in sorted(CHUNKS.glob("*_comfyui.py"))
               if "clip_name1" in p.read_text(encoding="utf-8")]
    assert private == BUILDS_THEM_PRIVATELY, (
        "a ComfyUI chunk builds the SD 3.5 loader nodes privately without being "
        "named here. Use schemas/engine/comfyui_chunk_support.py.")


def test_the_shared_loaders_name_the_three_files_download_models_fetches():
    from schemas.engine.comfyui_chunk_support import (
        SD35_TEXT_ENCODERS, checkpoint_loader, triple_clip_loader,
    )
    assert SD35_TEXT_ENCODERS == ("clip_l.safetensors", "clip_g.safetensors",
                                  "t5xxl_fp16.safetensors")
    loader = triple_clip_loader()
    assert loader["class_type"] == "TripleCLIPLoader"
    assert [loader["inputs"][f"clip_name{i}"] for i in (1, 2, 3)] == list(SD35_TEXT_ENCODERS)
    assert "_meta" in loader
    assert "_meta" not in triple_clip_loader(title=None)

    ckpt = checkpoint_loader("OfficialStableDiffusion/sd3.5_large.safetensors")
    assert ckpt["class_type"] == "CheckpointLoaderSimple"
    assert ckpt["inputs"]["ckpt_name"] == "OfficialStableDiffusion/sd3.5_large.safetensors"
    assert "_meta" not in checkpoint_loader("x", title=None)


def test_the_algebra_graph_still_loads_a_checkpoint_and_three_encoders():
    chunk = load_module("concept_algebra_comfyui",
                  CHUNKS / "output_image_concept_algebra_comfyui.py")
    workflow = chunk._build_workflow(
        prompt_a="a", prompt_b="b", prompt_c="c", negative_prompt="",
        checkpoint="OfficialStableDiffusion/sd3.5_large.safetensors", encoder="all",
        scale_sub=1.0, scale_add=1.0, width=1024, height=1024, steps=25, cfg=4.5,
        seed=1, sampler_name="euler", scheduler="normal",
    )
    assert workflow["5"]["class_type"] == "CheckpointLoaderSimple"
    assert workflow["7"]["inputs"]["clip_name3"] == "t5xxl_fp16.safetensors"
    assert workflow["13"]["class_type"] == "AI4ArtsEdSD3Algebra"


# --- the window the measurement rests on ------------------------------------

def _chunk(tokens):
    return [(t, 1.0) for t in tokens]


def test_clip_l_keeps_the_end_token_its_padding_is_made_of():
    """CLIP-L pads with its own end token (49407 for both), so the trailing run
    swallows the EOS the prompt put there. That one position is content."""
    filled = N._filled_in_chunk(_chunk([49406, 320, 1212, 49407, 49407, 49407]),
                                pad_token=49407, end_token=49407)
    assert filled == 4


def test_clip_g_and_t5_pad_with_something_else():
    assert N._filled_in_chunk(_chunk([49406, 320, 49407, 0, 0]),
                              pad_token=0, end_token=49407) == 3
    assert N._filled_in_chunk(_chunk([3, 9, 629, 1, 0, 0]),
                              pad_token=0, end_token=1) == 4


def test_a_chunk_of_nothing_but_padding_is_empty():
    assert N._filled_in_chunk(_chunk([0, 0, 0]), pad_token=0, end_token=1) == 0


def test_an_embedding_in_the_token_list_ends_the_padding_run():
    """A textual inversion stands there as a tensor. Comparing it with an id
    would raise, or worse, answer for a whole tensor."""
    tokens = [(49406, 1.0), (torch.zeros(768), 1.0), (0, 1.0), (0, 1.0)]
    assert N._filled_in_chunk(tokens, pad_token=0, end_token=1) == 2


def test_the_window_of_the_assembled_sequence_has_two_blocks():
    """CLIP-L and CLIP-G stand side by side over the first block and T5 follows,
    so the CLIP padding sits in the middle rather than at the end."""
    a = _parts(clip_seq=77, t5_seq=154, seed=20)
    b = _parts(clip_seq=77, t5_seq=154, seed=21)
    a["filled"] = {"clip_l": 6, "clip_g": 5, "t5": 8}
    b["filled"] = {"clip_l": 4, "clip_g": 7, "t5": 11}
    assert N._window_all(a, b) == [(0, 7), (77, 88)]


def test_the_window_never_reaches_past_the_clip_block():
    a = _parts(clip_seq=77, seed=22)
    b = _parts(clip_seq=77, seed=23)
    a["filled"] = {"clip_l": 999, "clip_g": 0, "t5": 3}
    b["filled"] = {"clip_l": 0, "clip_g": 0, "t5": 0}
    assert N._window_all(a, b)[0] == (0, 77)


def test_a_window_that_names_nothing_yields_nothing():
    """Falling back to the whole padded sequence would answer a measurement over
    the padding under the name of a measurement over the content."""
    delta = torch.randn((1, 77, 768))
    assert N._in_window(delta, []).shape == (1, 0, 768)
    assert N._in_window(delta, [(0, 6)]).shape == (1, 6, 768)
    assert N._in_window(delta, [(0, 2), (10, 13)]).shape == (1, 5, 768)


# --- which dimensions a run names -------------------------------------------

@pytest.mark.parametrize("written,expected", [
    ("", []),
    ("   ", []),
    ("3", [3]),
    ("3,17, 42", [3, 17, 42]),
    ("3;17", [3, 17]),
    ("3,3,3", [3]),
])
def test_the_named_dimensions_are_read_from_text(written, expected):
    assert N._dimensions_named(written, 4096, "all") == expected


@pytest.mark.parametrize("written", ["-1", "4096", "900000", "x", "12,4096"])
def test_a_selection_that_does_not_fit_the_encoder_ends_the_run(written):
    """A selection made against one encoder and sent to another is a stale form.
    The Diffusers instrument failed on the index; dropping it here would return
    prompt A's own picture under the caption of a transfer."""
    with pytest.raises(RuntimeError):
        N._dimensions_named(written, 4096, "all")


def test_the_error_names_the_encoder_that_has_no_such_dimension():
    with pytest.raises(RuntimeError, match="clip_l"):
        N._dimensions_named("3000", 768, "clip_l")


# --- the probe --------------------------------------------------------------

def _probe(a, b, encoder="all", dims="", transfer=False):
    answer = N.AI4ArtsEdSD3Probe().probe(a, b, encoder, dims, transfer)
    return answer["result"][0], answer["ui"]["ai4artsed_probe"][0]


def _pair(seed_a=30, seed_b=31, filled=None):
    a, b = _parts(seed=seed_a), _parts(seed=seed_b)
    a["filled"] = b["filled"] = dict(filled or {"clip_l": 6, "clip_g": 6, "t5": 8})
    return a, b


def test_the_first_pass_measures_and_changes_nothing():
    a, b = _pair()
    out, said = _probe(a, b)
    for key in N.PART_KEYS:
        assert torch.equal(out[key], a[key]), key
    assert "assembled" not in out
    assert said["num_transferred"] if False else "transferred_dims" not in said
    assert len(said["diff_per_dim"]) == 4096
    assert said["content_positions"] == 14
    assert said["content_ranges"] == [[0, 6], [77, 85]]


def test_the_measurement_is_the_one_the_diffusers_instrument_reported():
    """Twin: mean |B - A| per dimension over the named positions, and the L2 over
    the same positions (gpu_service/services/embedding_analyzer.py)."""
    a, b = _pair(seed_a=32, seed_b=33)
    _out, said = _probe(a, b, encoder="t5")

    delta = (b["t5"] - a["t5"])[:, :8, :]
    expected = delta.abs().mean(dim=1).squeeze(0)

    assert said["total_l2"] == pytest.approx(float(delta.norm(p=2)), rel=1e-5)
    assert said["top_values"][0] == pytest.approx(float(expected.max()), rel=1e-5)
    assert said["top_dims"][0] == int(expected.argmax())
    assert said["embed_dim"] == 4096
    assert said["top_values"] == sorted(said["top_values"], reverse=True)


def test_naming_dimensions_writes_only_those_and_only_in_the_window():
    a, b = _pair(seed_a=34, seed_b=35)
    out, said = _probe(a, b, encoder="t5", dims="7,900", transfer=True)

    moved = out["t5"]
    assert torch.equal(moved[:, :8, 7], b["t5"][:, :8, 7])
    assert torch.equal(moved[:, :8, 900], b["t5"][:, :8, 900])
    assert torch.equal(moved[:, 8:, :], a["t5"][:, 8:, :]), "wrote past the window"
    untouched = [d for d in range(0, 4096, 97) if d not in (7, 900)]
    assert torch.equal(moved[:, :, untouched], a["t5"][:, :, untouched])
    assert said["transferred_dims"] == [7, 900]
    assert said["num_transferred"] == 2
    assert 0 < said["captured_pct"] < 100
    assert said["change_l2"] <= said["total_diff_l2"]


def test_the_whole_selection_accounts_for_the_whole_difference():
    a, b = _pair(seed_a=36, seed_b=37)
    _out, said = _probe(a, b, encoder="clip_l", transfer=True,
                        dims=",".join(str(d) for d in range(768)))
    assert said["captured_pct"] == pytest.approx(100.0, abs=1e-3)


def test_the_sequence_that_was_measured_is_the_sequence_that_is_sampled():
    """What the probe wrote goes to the sampler as it stands, with no second
    assembly between the measurement and the picture."""
    a, b = _pair(seed_a=38, seed_b=39)
    out, _said = _probe(a, b, encoder="all", dims="100,3000", transfer=True)
    assert "assembled" in out
    cond, pooled = N._assemble(out)
    assert torch.equal(cond, out["assembled"])
    assert torch.equal(pooled, torch.cat([a["pooled_l"], a["pooled_g"]], dim=-1))

    clip_len = a["clip_l"].shape[1]
    # dimension 100 sits in CLIP-L over the first block and in T5 after it
    assert torch.equal(cond[:, :6, 100], b["clip_l"][:, :6, 100])
    assert torch.equal(cond[:, clip_len:clip_len + 8, 3000],
                       b["t5"][:, :8, 3000])
    # and outside the window the sequence is still A's
    assert torch.equal(cond[:, 6:clip_len, 100], a["clip_l"][:, 6:, 100])
    assert torch.equal(cond[:, clip_len + 8:, 3000], a["t5"][:, 8:, 3000])


def test_the_first_pass_reports_no_transfer_at_all():
    a, b = _pair(seed_a=40, seed_b=41)
    out, said = _probe(a, b, encoder="all", dims="12,34", transfer=False)
    assert "assembled" not in out
    assert torch.equal(out["t5"], a["t5"])
    assert "change_l2" not in said
    assert "transferred_dims" not in said


def test_a_second_pass_that_names_nothing_reports_zeros():
    """The Diffusers instrument answered an empty selection as a run that moved
    nothing, with the statistics of nothing, rather than as a first pass."""
    a, b = _pair(seed_a=42, seed_b=43)
    out, said = _probe(a, b, encoder="all", dims="", transfer=True)
    assert said["transferred_dims"] == []
    assert said["num_transferred"] == 0
    assert said["change_l2"] == 0.0
    assert said["captured_pct"] == 0.0
    assert torch.equal(N._assemble(out)[0], N._assemble(a)[0])


def test_the_window_never_counts_what_was_cut_off_b():
    """B is laid against A before anything is compared, so what B fills past A's
    length is gone. Counting it named a window wider than the comparison."""
    a, b = _pair(seed_a=44, seed_b=45)
    a["filled"] = {"clip_l": 6, "clip_g": 6, "t5": 8}
    b["filled"] = {"clip_l": 200, "clip_g": 200, "t5": 900}
    clip_len, t5_len = a["clip_l"].shape[1], a["t5"].shape[1]
    assert N._window_all(a, b) == [(0, clip_len), (clip_len, clip_len + t5_len)]
    assert N._window_one(a, b, "t5") == t5_len


def test_the_arithmetic_does_not_inherit_a_sequence_the_probe_assembled():
    """A graph that puts an Algebra after a Probe would otherwise hand the
    probe's tensor to the sampler and throw the arithmetic away in silence."""
    a, b = _pair(seed_a=46, seed_b=47)
    probed, _said = _probe(a, b, encoder="all", dims="100", transfer=True)
    assert "assembled" in probed

    out, l2 = N.AI4ArtsEdSD3Algebra().combine(
        probed, N._empty_parts(), _parts(seed=48), "t5", 1.0, 1.0)["result"]
    assert "assembled" not in out
    assert l2 > 0
    clip_len = min(out["clip_l"].shape[1], out["clip_g"].shape[1])
    assert torch.equal(N._assemble(out)[0][:, clip_len:], out["t5"])


def test_the_parts_a_node_hands_on_carry_their_own_window():
    """`dict()` is shallow: a shared window dict would let a later write reach
    into another node's cached output."""
    a, b = _pair(seed_a=49, seed_b=50)
    out, _said = _probe(a, b, encoder="t5", dims="7", transfer=True)
    assert out["filled"] == a["filled"]
    assert out["filled"] is not a["filled"]


# --- the fusion (the Surrealizer) -------------------------------------------
# The arithmetic of gpu_service/services/diffusers_backend.py::
# generate_image_with_fusion, strategy by strategy, on parts instead of on the
# pipeline's encoders. Nothing is derived again: the numbers below are the
# twin's formulas evaluated by hand.

def _fusion(clip_side, t5_side, alpha, strategy):
    return N.AI4ArtsEdSD3Fusion().fuse(clip_side, t5_side, alpha, strategy)[0]


@pytest.mark.parametrize("strategy, alpha, expected", [
    # centered_fade: h = 1, t = alpha. -h is CLIP alone, 0 both at 1, +h T5 alone.
    ("centered_fade", -1.0, (1.0, 0.0)),
    ("centered_fade", -0.5, (1.0, 0.5)),
    ("centered_fade", 0.0, (1.0, 1.0)),
    ("centered_fade", 0.5, (0.5, 1.0)),
    ("centered_fade", 1.0, (0.0, 1.0)),
    ("centered_fade", 25.0, (-24.0, 25.0)),
    ("centered_fade", -3.0, (3.0, -2.0)),
    # the LERP
    ("legacy", 0.3, (0.7, 0.3)),
    ("legacy", 40.0, (-39.0, 40.0)),
    ("dual_alpha", 0.3, (0.7, 0.3)),
    ("normalized", 0.3, (0.7, 0.3)),
    # original: anchors 0 and 1, t = 2 * alpha - 1 across the band, the LERP past it
    ("original", 0.0, (1.0, 0.0)),
    ("original", 0.25, (1.0, 0.5)),
    ("original", 0.5, (1.0, 1.0)),
    ("original", 0.75, (0.5, 1.0)),
    ("original", 1.0, (0.0, 1.0)),
    ("original", 2.0, (-1.0, 2.0)),
    ("original", -1.0, (2.0, -1.0)),
])
def test_the_fusion_weights_are_the_twins(strategy, alpha, expected):
    assert N._fusion_weights(strategy, alpha) == pytest.approx(expected)


def test_the_core_is_the_weighted_sum_and_the_tail_is_t5s_own():
    a = _parts(clip_seq=77, t5_seq=512, seed=60)
    out = _fusion(a, a, 0.5, "centered_fade")
    fused = out["assembled"]
    assert fused.shape == (1, 512, 4096)
    block = N._clip_block(a)
    assert torch.allclose(fused[:, :77], 0.5 * block + 1.0 * a["t5"][:, :77])
    assert torch.equal(fused[:, 77:], a["t5"][:, 77:])
    for key in ("pooled_l", "pooled_g"):
        assert torch.equal(out[key], a[key]), key


def test_past_the_band_one_weight_inverts_and_nothing_is_clamped():
    a = _parts(clip_seq=77, t5_seq=154, seed=61)
    fused = _fusion(a, a, 25.0, "centered_fade")["assembled"]
    block = N._clip_block(a)
    assert torch.allclose(fused[:, :77], -24.0 * block + 25.0 * a["t5"][:, :77],
                          atol=1e-4)


def test_dual_alpha_scales_the_tail_by_a_fraction_of_alpha():
    a = _parts(clip_seq=77, t5_seq=154, seed=62)
    fused = _fusion(a, a, 20.0, "dual_alpha")["assembled"]
    block = N._clip_block(a)
    assert torch.allclose(fused[:, :77], -19.0 * block + 20.0 * a["t5"][:, :77],
                          atol=1e-4)
    assert torch.allclose(fused[:, 77:], 0.15 * 20.0 * a["t5"][:, 77:])


def test_normalized_scales_each_tail_position_to_the_cores_mean_length():
    """The twin: core = (1 - alpha) * clip + alpha * t5 over the block,
    core_mag = core.norm(dim=-1).mean(), every tail position scaled to it."""
    a = _parts(clip_seq=77, t5_seq=154, seed=63)
    fused = _fusion(a, a, 20.0, "normalized")["assembled"]
    core = -19.0 * N._clip_block(a) + 20.0 * a["t5"][:, :77]
    assert torch.allclose(fused[:, :77], core, atol=1e-4)
    core_mag = core.norm(dim=-1).mean()
    tail_norms = fused[:, 77:].norm(dim=-1)
    assert torch.allclose(tail_norms, core_mag.expand_as(tail_norms), rtol=1e-4)
    # the direction of every tail position is T5's own
    cos = torch.nn.functional.cosine_similarity(fused[:, 77:], a["t5"][:, 77:], dim=-1)
    assert torch.allclose(cos, torch.ones_like(cos), atol=1e-5)


def test_legacy_leaves_the_tail_untouched():
    a = _parts(clip_seq=77, t5_seq=154, seed=64)
    fused = _fusion(a, a, 40.0, "legacy")["assembled"]
    assert torch.equal(fused[:, 77:], a["t5"][:, 77:])


def test_original_runs_clip_l_alone():
    """The 2025 workflow: CLIP-G's dimensions and its pooled half are zero, and
    the CLIP block carries CLIP-L's 768 with the rest of the 4096 empty."""
    a = _parts(clip_seq=77, t5_seq=100, seed=65)
    out = _fusion(a, a, 0.25, "original")
    assert not out["clip_g"].any()
    assert not out["pooled_g"].any()
    assert torch.equal(out["pooled_l"], a["pooled_l"])
    fused = out["assembled"]
    padded_l = torch.nn.functional.pad(a["clip_l"], (0, 4096 - 768))
    assert torch.allclose(fused[:, :77], 1.0 * padded_l + 0.5 * a["t5"][:, :77])
    assert torch.equal(fused[:, 77:], a["t5"][:, 77:])


def test_the_t5_side_may_be_another_prompt_and_the_pooled_vector_stays_clips():
    clip_side, t5_side = _parts(seed=66), _parts(seed=67)
    out = _fusion(clip_side, t5_side, 0.0, "centered_fade")
    fused = out["assembled"]
    assert torch.allclose(fused[:, :77], N._clip_block(clip_side) + t5_side["t5"][:, :77])
    assert torch.equal(fused[:, 77:], t5_side["t5"][:, 77:])
    assert torch.equal(out["pooled_l"], clip_side["pooled_l"])
    assert torch.equal(out["pooled_g"], clip_side["pooled_g"])


def test_the_core_is_cut_to_the_clip_block_and_a_shorter_t5_is_refused():
    """`interp_len = min(77, clip_len)` in the twin, whose T5 was never shorter
    than the block (max(77, len) or 512). A CLIP block short of 77 cuts the
    core to its length and T5 goes on from there; a T5 short of 77 is refused
    rather than cutting the core quietly."""
    a = _parts(clip_seq=40, t5_seq=154, seed=68)
    fused = _fusion(a, a, 0.0, "legacy")["assembled"]
    assert fused.shape == (1, 154, 4096)
    assert torch.allclose(fused[:, :40], N._clip_block(a))
    assert torch.equal(fused[:, 40:], a["t5"][:, 40:])
    short = _parts(clip_seq=77, t5_seq=40, seed=69)
    with pytest.raises(RuntimeError, match="T5 stands on 40 positions"):
        _fusion(short, short, 0.0, "legacy")


def test_an_empty_side_is_refused_and_the_switch_is_named():
    a = _parts(seed=69)
    with pytest.raises(RuntimeError, match="empty_padding=empty_prompt"):
        _fusion(a, N._empty_parts(), 0.0, "centered_fade")
    with pytest.raises(RuntimeError, match="empty_padding=empty_prompt"):
        _fusion(N._empty_parts(), a, 0.0, "centered_fade")


def test_a_fusion_the_node_does_not_run_is_refused():
    a = _parts(seed=70)
    with pytest.raises(RuntimeError, match="sphere"):
        _fusion(a, a, 0.5, "sphere")


def test_slerp_turns_the_core_on_the_sphere_and_keeps_the_tail():
    """The twin's slerp_tokens: at alpha 0 the CLIP reading, at 1 T5's, in
    between the direction turned by alpha * theta with the length run linearly;
    the tail is T5's own."""
    a, b = _parts(seed=71), _parts(seed=72)
    block = N._clip_block(a).float()[:, :77]
    t5 = b["t5"].float()
    at_0 = _fusion(a, b, 0.0, "slerp")["assembled"]
    at_1 = _fusion(a, b, 1.0, "slerp")["assembled"]
    assert torch.allclose(at_0[:, :77], block, atol=1e-4)
    assert torch.allclose(at_1[:, :77], t5[:, :77], atol=1e-4)
    assert torch.equal(at_0[:, 77:], t5[:, 77:])
    half = _fusion(a, b, 0.5, "slerp")["assembled"][:, :77]
    u_a = torch.nn.functional.normalize(block, dim=-1)
    u_b = torch.nn.functional.normalize(t5[:, :77], dim=-1)
    theta = torch.acos((u_a * u_b).sum(-1, keepdim=True).clamp(-1, 1))
    turned = (torch.sin(0.5 * theta) * u_a + torch.sin(0.5 * theta) * u_b) / torch.sin(theta)
    length = 0.5 * block.norm(dim=-1, keepdim=True) + 0.5 * t5[:, :77].norm(dim=-1, keepdim=True)
    assert torch.allclose(half, turned * length, atol=1e-4)


def test_the_fusion_writes_its_own_sequence_and_the_sampler_gets_it():
    """A probe upstream leaves an assembled sequence in the parts; the fusion
    must not hand that one on. And what the fusion wrote is what
    `AI4ArtsEdSD3Assemble` passes to the sampler."""
    a = _parts(seed=71)
    a["assembled"] = torch.zeros((1, 3, 4096))
    out = _fusion(a, a, 0.0, "centered_fade")
    assert out["assembled"].shape == (1, 154, 4096)
    cond, pooled = N._assemble(out)
    assert torch.equal(cond, out["assembled"])
    assert torch.equal(pooled, torch.cat([a["pooled_l"], a["pooled_g"]], dim=-1))
    # and the input was left alone
    assert a["assembled"].shape == (1, 3, 4096)


def test_the_fusion_is_computed_in_float32():
    """Half inputs, float32 arithmetic. At alpha 25 the products leave fp16's
    resolution: a fusion computed in half and cast up afterwards stands about
    1e-1 off the float32 reference."""
    a = _parts(seed=72)
    half = {k: (v.half() if torch.is_tensor(v) else v) for k, v in a.items()}
    out = _fusion(half, half, 25.0, "centered_fade")["assembled"]
    assert out.dtype == torch.float32
    block, t5 = N._clip_block(half).float(), half["t5"].float()
    reference = torch.cat([-24.0 * block[:, :77] + 25.0 * t5[:, :77], t5[:, 77:]], dim=1)
    assert torch.allclose(out, reference, atol=1e-3)


def test_the_encode_switch_sends_the_empty_prompt_to_the_encoders():
    """Under "empty_prompt" the empty string is encoded like any text, which is
    what the Surrealizer's negative side is made of."""
    with pytest.raises(AssertionError, match="encode ''"):
        N._encode_parts(_sd3_clip(), "", "empty_prompt")
    assert N._encode_parts(_sd3_clip(), "", "none")["filled"] == {"clip_l": 0, "clip_g": 0, "t5": 0}
    offered = N.AI4ArtsEdSD3Encode.INPUT_TYPES()["optional"]["empty_padding"]
    assert offered[0] == ["none", "empty_prompt"] and offered[1]["default"] == "none"
    # and the node's own method hands the switch on; left out, it is "none"
    node = N.AI4ArtsEdSD3Encode()
    with pytest.raises(AssertionError, match="encode ''"):
        node.encode(_sd3_clip(), "", empty_padding="empty_prompt")
    assert node.encode(_sd3_clip(), "")[0]["filled"] == {"clip_l": 0, "clip_g": 0, "t5": 0}


# --- the fusion node and the Surrealizer chunk agree ------------------------

def _surrealizer():
    return load_module("surrealizer_comfyui", CHUNKS / "output_image_surrealizer_comfyui.py")


def test_the_node_and_the_chunk_name_the_same_fusions():
    """The node runs every fusion of the two instruments; the Surrealizer's
    chunk offers the node's list without `slerp` (the sphere is off the
    Surrealizer), the Fusion Workbench's route the node's without
    `original`. The two switches of the three factors, T5_ROWS and POOLED,
    are the node's lists as they stand."""
    chunk = _surrealizer()
    assert tuple(n for n in N.FUSIONS if n != "slerp") == chunk.FUSIONS
    assert chunk.T5_ROWS == tuple(N.T5_ROWS)
    assert chunk.POOLED == tuple(N.POOLED)
    assert "slerp" in N.FUSIONS and "slerp" not in chunk.FUSIONS
    assert chunk.DEFAULTS["fusion_strategy"] in N.FUSIONS
    offered = N.AI4ArtsEdSD3Fusion.INPUT_TYPES()["required"]["strategy"]
    assert offered[0] == N.FUSIONS
    from my_app.routes.fusion_workbench_routes import WORKBENCH_FUSIONS
    assert set(WORKBENCH_FUSIONS) == set(N.FUSIONS) - {"original"}


def _graph(strategy="centered_fade", clip_prompt="a house", t5_prompt="a house",
           negative="", alpha=0.5):
    return _surrealizer()._build_workflow(
        clip_prompt=clip_prompt, t5_prompt=t5_prompt, negative_prompt=negative,
        checkpoint="OfficialStableDiffusion/sd3.5_large.safetensors",
        strategy=strategy, alpha=alpha, width=1024, height=1024, steps=25, cfg=5.5,
        seed=1, sampler_name="euler", scheduler="normal",
    )


def test_the_surrealizer_graph_fuses_both_sides_the_same_way():
    # A strategy and an alpha off the node's defaults, and an alpha that is its
    # own complement under no strategy: a fusion node left at its defaults, or
    # a negative fused at 1 - alpha, would show.
    g = _graph("dual_alpha", alpha=20.0)
    chunk = _surrealizer()
    fusion = g[chunk.FUSION_NODE_ID]
    assert fusion["class_type"] == "AI4ArtsEdSD3Fusion"
    assert g["15"]["class_type"] == "AI4ArtsEdSD3Fusion"
    for node in (fusion, g["15"]):
        assert node["inputs"]["alpha"] == 20.0
        assert node["inputs"]["strategy"] == "dual_alpha"
    # one prompt: the same encode feeds both sides, and the encoders run once
    assert fusion["inputs"]["clip_side"] == ["10", 0]
    assert fusion["inputs"]["t5_side"] == ["10", 0]
    assert "11" not in g
    # the negative is the encoding of the empty string, fused at the same alpha
    assert g["14"]["inputs"]["text"] == ""
    assert g["14"]["inputs"]["empty_padding"] == "empty_prompt"
    assert g["15"]["inputs"] == {"clip_side": ["14", 0], "t5_side": ["14", 0],
                                 "alpha": 20.0, "strategy": "dual_alpha"}
    # What the sampler gets is the fused sequence on both sides. ComfyUI runs
    # what an output depends on: a graph that assembled the raw encodes would
    # leave the fusion nodes unrun and raise nothing.
    assert g["13"]["class_type"] == "AI4ArtsEdSD3Assemble"
    assert g["13"]["inputs"] == {"parts": [chunk.FUSION_NODE_ID, 0]}
    assert g["16"]["class_type"] == "AI4ArtsEdSD3Assemble"
    assert g["16"]["inputs"] == {"parts": ["15", 0]}
    assert g["20"]["class_type"] == "KSampler"
    assert g["20"]["inputs"] == {
        "model": ["5", 0], "positive": ["13", 0], "negative": ["16", 0],
        "latent_image": ["3", 0], "seed": 1, "steps": 25, "cfg": 5.5,
        "sampler_name": "euler", "scheduler": "normal", "denoise": 1,
    }
    assert g["3"]["class_type"] == "EmptyLatentImage"
    assert g["3"]["inputs"] == {"width": 1024, "height": 1024, "batch_size": 1}
    assert g["22"]["class_type"] == "VAEDecode"
    assert g["22"]["inputs"] == {"samples": ["20", 0], "vae": ["5", 2]}
    assert g[chunk.SAVE_NODE_ID]["class_type"] == "SaveImage"
    assert g[chunk.SAVE_NODE_ID]["inputs"]["images"] == ["22", 0]


def test_two_prompts_give_t5_its_own_encode():
    from schemas.engine.comfyui_chunk_support import CLIP_NODE
    g = _graph(clip_prompt="a house", t5_prompt="a house by a river")
    assert g["11"]["inputs"]["text"] == "a house by a river"
    assert g["11"]["inputs"]["empty_padding"] == "empty_prompt"
    # the T5 side reads the platform's length like the CLIP side; the route
    # sends two prompts under centered_fade, so this is the graph that runs
    assert g["11"]["inputs"]["clip"] == [CLIP_NODE, 0]
    assert g["12"]["inputs"]["clip_side"] == ["10", 0]
    assert g["12"]["inputs"]["t5_side"] == ["11", 0]


def test_t5_stands_at_the_platforms_length_except_under_original():
    from schemas.engine.comfyui_chunk_support import CLIP_NODE, T5_LENGTH
    g = _graph("centered_fade")
    assert g[CLIP_NODE]["class_type"] == "T5TokenizerOptions"
    assert g[CLIP_NODE]["inputs"]["min_length"] == T5_LENGTH
    for enc in ("10", "14"):
        assert g[enc]["inputs"]["clip"] == [CLIP_NODE, 0]
    g = _graph("original", t5_prompt="another text")
    assert CLIP_NODE not in g
    for enc in ("10", "11", "14"):
        assert g[enc]["inputs"]["clip"] == ["7", 0]


@pytest.mark.parametrize("named, refused_for", [
    ("centered_fade#path=sphere", "path=sphere"),
    ("legacy#t5len=77#pooled=zero", "t5len=77, pooled=zero"),
    ("sphere", "sphere"),
    ("original_cg", "original_cg"),
    ("", "''"),
])
def test_a_fusion_the_graph_cannot_run_is_refused_with_its_name(named, refused_for):
    with pytest.raises(ValueError, match=__import__("re").escape(refused_for)):
        _surrealizer()._fusion_named(named)


def test_the_bare_names_pass():
    chunk = _surrealizer()
    for name in chunk.FUSIONS:
        assert chunk._fusion_named(name) == name


def test_original_needs_its_own_t5_text_and_loras_are_refused():
    import asyncio
    chunk = _surrealizer()
    with pytest.raises(ValueError, match="original fusion needs its own T5 text"):
        asyncio.run(chunk.execute(prompt="a house", fusion_strategy="original",
                                  alpha_factor=0.5))
    with pytest.raises(ValueError, match="no LoRA"):
        asyncio.run(chunk.execute(prompt="a house", fusion_strategy="centered_fade",
                                  alpha_factor=0.5, loras=[{"name": "x"}]))
    with pytest.raises(ValueError, match="No prompt"):
        asyncio.run(chunk.execute(prompt="   ", fusion_strategy="centered_fade"))


# --- the three factors on the table -----------------------------------------

def _three(parts, a, b, c, t5_rows="full", pooled="clip"):
    return N.AI4ArtsEdSD3ThreeFactors().weigh(parts, a, b, c, t5_rows, pooled)[0]


def test_the_three_factors_write_the_table_the_concept_describes():
    """Rows 0..76 are a * CLIP + b * T5[0..76]; under them the whole T5 block
    times c, 589 rows in all."""
    p = _parts(clip_seq=77, t5_seq=512, seed=80)
    out = _three(p, -14.0, 15.0, 0.5)
    table = out["assembled"]
    assert table.shape == (1, 589, 4096)
    block = N._clip_block(p)
    assert torch.allclose(table[:, :77], -14.0 * block + 15.0 * p["t5"][:, :77])
    assert torch.allclose(table[:, 77:], 0.5 * p["t5"])
    for key in ("pooled_l", "pooled_g"):
        assert torch.equal(out[key], p[key]), key


def test_standard_is_the_sequence_comfyui_assembles_itself():
    """(1, 0, 1, full, clip) is ComfyUI's own assembly of the parts, bit for bit."""
    p = _parts(clip_seq=77, t5_seq=512, seed=81)
    out = _three(p, 1.0, 0.0, 1.0, "full")
    cond, _pooled = N._assemble({k: v for k, v in p.items() if k != "assembled"})
    assert torch.equal(out["assembled"], cond)


@pytest.mark.parametrize("alpha", [0.0, 5.0, 15.0, 35.0])
def test_the_line_a_plus_b_one_in_the_tail_layout_is_legacy_to_the_bit(alpha):
    """(1 - alpha, alpha, 1, tail, clip) and `AI4ArtsEdSD3Fusion` under legacy at
    alpha are the same tensor: the Surrealizer of 2025 is a line in this
    node's parameter space, and a stored run on it is reproduced exactly."""
    p = _parts(clip_seq=77, t5_seq=512, seed=82)
    ours = _three(p, 1.0 - alpha, alpha, 1.0, "tail")["assembled"]
    theirs = _fusion(p, p, alpha, "legacy")["assembled"]
    assert ours.shape == theirs.shape == (1, 512, 4096)
    assert torch.equal(ours, theirs)


def test_c_zero_puts_zeros_in_the_t5_blocks_place():
    p = _parts(clip_seq=77, t5_seq=512, seed=83)
    table = _three(p, 1.0, 0.0, 0.0)["assembled"]
    assert table.shape == (1, 589, 4096)
    assert torch.equal(table[:, 77:], torch.zeros((1, 512, 4096)))
    assert torch.equal(table[:, :77], N._clip_block(p))


def test_the_tail_layout_drops_t5s_head_and_keeps_512_rows():
    p = _parts(clip_seq=77, t5_seq=512, seed=84)
    table = _three(p, 1.0, 0.0, 1.0, "tail")["assembled"]
    assert table.shape == (1, 512, 4096)
    assert torch.equal(table[:, 77:], p["t5"][:, 77:])


def test_a_layout_the_node_does_not_lay_is_refused():
    p = _parts(clip_seq=77, t5_seq=512, seed=85)
    with pytest.raises(RuntimeError, match="t5_rows 'sideways'"):
        _three(p, 1.0, 0.0, 1.0, "sideways")


def test_pooled_zero_puts_zeros_in_the_pooled_vectors_place_and_leaves_the_table():
    """The pooled vector goes to the modulation, not into the table: under
    pooled="zero" both CLIP pooled vectors are zeros of their own shape and
    the table is the one pooled="clip" writes."""
    p = _parts(clip_seq=77, t5_seq=512, seed=89)
    kept = _three(p, -14.0, 15.0, 1.0, "tail", "clip")
    zeroed = _three(p, -14.0, 15.0, 1.0, "tail", "zero")
    assert torch.equal(kept["assembled"], zeroed["assembled"])
    for key in ("pooled_l", "pooled_g"):
        assert torch.equal(kept[key], p[key]), key
        assert zeroed[key].shape == p[key].shape
        assert torch.equal(zeroed[key], torch.zeros_like(p[key])), key
    # what the sampler gets: the joined pooled vector, 2048 zeros
    _cond, pooled = N._assemble(zeroed)
    assert pooled.shape[-1] == 768 + 1280
    assert torch.equal(pooled, torch.zeros_like(pooled))
    # the input kept its own
    assert not torch.equal(p["pooled_g"], torch.zeros_like(p["pooled_g"]))
    with pytest.raises(RuntimeError, match="pooled 'half'"):
        _three(p, 1.0, 0.0, 1.0, "full", "half")


def test_the_three_factors_are_computed_in_float32_and_write_their_own_sequence():
    p = _parts(clip_seq=77, t5_seq=512, seed=86)
    p["assembled"] = torch.zeros((1, 3, 4096))
    half = {k: (v.half() if torch.is_tensor(v) else v) for k, v in p.items()}
    out = _three(half, -24.0, 25.0, 1.0)
    assert out["assembled"].dtype == torch.float32
    block, t5 = N._clip_block(half).float(), half["t5"].float()
    reference = torch.cat([-24.0 * block + 25.0 * t5[:, :77], t5], dim=1)
    assert torch.allclose(out["assembled"], reference, atol=1e-3)
    # what the node wrote is what the sampler gets, and the input kept its own
    cond, _ = N._assemble(out)
    assert torch.equal(cond, out["assembled"])
    assert p["assembled"].shape == (1, 3, 4096)


def test_a_t5_shorter_than_the_block_and_an_empty_side_are_refused():
    short = _parts(clip_seq=77, t5_seq=40, seed=87)
    with pytest.raises(RuntimeError, match="at least 77"):
        _three(short, 1.0, 0.0, 1.0)
    empty = _parts(clip_seq=0, t5_seq=512, seed=88)
    with pytest.raises(RuntimeError, match="empty_padding=empty_prompt"):
        _three(empty, 1.0, 0.0, 1.0)


def test_the_node_offers_the_layouts_and_the_standard_as_its_defaults():
    offered = N.AI4ArtsEdSD3ThreeFactors.INPUT_TYPES()["required"]
    assert offered["t5_rows"][0] == N.T5_ROWS == ["full", "tail"]
    assert offered["t5_rows"][1]["default"] == "full"
    assert offered["pooled"][0] == N.POOLED == ["clip", "zero"]
    assert offered["pooled"][1]["default"] == "clip"
    assert (offered["a"][1]["default"], offered["b"][1]["default"], offered["c"][1]["default"]) == (1.0, 0.0, 1.0)
    assert "AI4ArtsEdSD3ThreeFactors" in N.NODE_CLASS_MAPPINGS
    assert "AI4ArtsEdSD3ThreeFactors" in N.NODE_DISPLAY_NAME_MAPPINGS


def _graph_three(a=1.0, b=0.0, c=1.0, t5_rows="full", negative="", pooled="clip"):
    return _surrealizer()._build_workflow(
        clip_prompt="a house", t5_prompt="a house", negative_prompt=negative,
        checkpoint="OfficialStableDiffusion/sd3.5_large.safetensors",
        strategy=None, alpha=None, width=1024, height=1024, steps=25, cfg=5.5,
        seed=1, sampler_name="euler", scheduler="normal",
        factors=(a, b, c, t5_rows, pooled),
    )


def test_the_surrealizer_graph_puts_the_three_factors_on_both_sides():
    from schemas.engine.comfyui_chunk_support import CLIP_NODE, T5_LENGTH
    g = _graph_three(-14.0, 15.0, 0.5, "full", negative="blurry", pooled="zero")
    chunk = _surrealizer()
    node = g[chunk.FUSION_NODE_ID]
    assert node["class_type"] == "AI4ArtsEdSD3ThreeFactors"
    assert node["inputs"] == {"parts": ["10", 0], "a": -14.0, "b": 15.0, "c": 0.5,
                              "t5_rows": "full", "pooled": "zero"}
    # one prompt, one encode; no T5-side encode
    assert "11" not in g
    assert g["10"]["inputs"]["text"] == "a house"
    assert g["10"]["inputs"]["empty_padding"] == "empty_prompt"
    # the negative goes the same way under the same factors
    assert g["14"]["inputs"]["text"] == "blurry"
    assert g["15"]["class_type"] == "AI4ArtsEdSD3ThreeFactors"
    assert g["15"]["inputs"] == {"parts": ["14", 0], "a": -14.0, "b": 15.0, "c": 0.5,
                                 "t5_rows": "full", "pooled": "zero"}
    assert g["13"]["inputs"] == {"parts": [chunk.FUSION_NODE_ID, 0]}
    assert g["16"]["inputs"] == {"parts": ["15", 0]}
    assert g["20"]["inputs"]["positive"] == ["13", 0]
    assert g["20"]["inputs"]["negative"] == ["16", 0]
    # T5 at the platform's length, so the block has its 512 rows
    assert g[CLIP_NODE]["inputs"]["min_length"] == T5_LENGTH
    for enc in ("10", "14"):
        assert g[enc]["inputs"]["clip"] == [CLIP_NODE, 0]


def test_the_chunk_takes_the_three_factors_together_or_not_at_all():
    import asyncio
    chunk = _surrealizer()
    with pytest.raises(ValueError, match="factor_b"):
        asyncio.run(chunk.execute(prompt="a house", factor_a=1.0, factor_c=1.0))
    with pytest.raises(ValueError, match="t5_rows"):
        asyncio.run(chunk.execute(prompt="a house", factor_a=1.0, factor_b=0.0,
                                  factor_c=1.0, t5_rows="sideways"))
    with pytest.raises(ValueError, match="one prompt"):
        asyncio.run(chunk.execute(prompt="a house", factor_a=1.0, factor_b=0.0,
                                  factor_c=1.0, t5_prompt="another text"))
    with pytest.raises(ValueError, match="alpha_factor"):
        asyncio.run(chunk.execute(prompt="a house", factor_a=1.0, factor_b=0.0,
                                  factor_c=1.0, alpha_factor=5.0))
    with pytest.raises(ValueError, match="is not a number"):
        asyncio.run(chunk.execute(prompt="a house", factor_a="x", factor_b=0.0,
                                  factor_c=1.0))
    with pytest.raises(ValueError, match="pooled"):
        asyncio.run(chunk.execute(prompt="a house", factor_a=1.0, factor_b=0.0,
                                  factor_c=1.0, pooled="half"))
    with pytest.raises(ValueError, match="factor_a"):
        asyncio.run(chunk.execute(prompt="a house", pooled="zero"))
    assert chunk._factors_named(1, "0", 1.0, None) == (1.0, 0.0, 1.0, "full", "clip")
    assert chunk._factors_named(-14, 15, 0.5, "tail") == (-14.0, 15.0, 0.5, "tail", "clip")
    assert chunk._factors_named(0, 0, 1.0, "full", "zero") == (0.0, 0.0, 1.0, "full", "zero")
    assert chunk.DEFAULTS["t5_rows"] == "full"
    assert chunk.DEFAULTS["pooled"] == "clip"
