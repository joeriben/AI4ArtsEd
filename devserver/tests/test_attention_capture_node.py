"""
Attention Cartography on ComfyUI: the readout and the graph.

The node (comfyui_nodes/ai4artsed_attention_capture.py) reads the attention
SD 3.5's joint blocks put on the words while the picture is made, the way
gpu_service/services/attention_processors_sd3.py read it on the Diffusers
pipeline. What is checked here, against numbers computed by hand:

  * the steps and blocks the readout is set to, from the twin's rules;
  * the columns: which positions of the joint text sequence carry a word, on
    the tokenizers' own markers (CLIP-L's "</w>", T5's U+2581);
  * the map: softmax(QK^T / sqrt(d)) over ALL keys, the image rows' weights on
    the text columns, with the text in FRONT of the image (ComfyUI's order),
    summed over batch entries and heads and divided by their count - the same
    whether negative and positive passed as one batch or one after the other;
  * what passes through untouched: the image self-attention of a dual block,
    a step that is none of the chosen, the function's own result;
  * the file the second node writes and the key it announces under;
  * the chunk's graph and how it reads the file back.

Every tensor here is small; nothing needs a card.
"""

import json
import math
import sys
import types

import pytest

torch = pytest.importorskip("torch")

from file_modules import DEVSERVER, REPO, load_module

NODE_FILE = REPO / "comfyui_nodes" / "ai4artsed_attention_capture.py"
CHUNK_FILE = DEVSERVER / "schemas" / "chunks" / "output_image_attention_cartography_comfyui.py"


@pytest.fixture
def node(tmp_path, monkeypatch):
    """The node file, loaded with a `folder_paths` that lives in tmp_path."""
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: str(tmp_path)
    folder_paths.get_save_image_path = (
        lambda prefix, out: (str(tmp_path), prefix, 7, "", prefix))
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)
    return load_module("ai4artsed_attention_capture_under_test", NODE_FILE)


def _chunk():
    sys.path.insert(0, str(DEVSERVER))
    return load_module("attention_cartography_comfyui_under_test", CHUNK_FILE)


# --- the steps and the blocks ------------------------------------------------

def test_the_blocks_are_read_from_the_text_the_surface_sends(node):
    assert node.parse_layers("3,9,17") == [3, 9, 17]
    assert node.parse_layers(" 3 , 9 ,") == [3, 9]
    with pytest.raises(ValueError, match="'x' is no block index"):
        node.parse_layers("3,x")
    with pytest.raises(ValueError, match="names no block"):
        node.parse_layers("")
    with pytest.raises(ValueError, match="capture_layers '3,3': a block is named twice"):
        node.parse_layers("3,3")
    with pytest.raises(ValueError, match="blocks 'x': 'x' is no block index"):
        node.parse_layers("x", "blocks")


def test_the_steps_are_every_nth_from_the_first_and_the_last_always(node):
    """generate_image_with_attention: range(0, steps, n), and steps - 1 appended
    when the range missed it."""
    assert node.capture_steps(25, 1) == list(range(25))
    assert node.capture_steps(25, 10) == [0, 10, 20, 24]
    assert node.capture_steps(25, 25) == [0, 24]
    assert node.capture_steps(1, 1) == [0]
    with pytest.raises(ValueError, match="steps must be at least 1"):
        node.capture_steps(0, 1)
    with pytest.raises(ValueError, match="capture_every_n_steps must be at least 1"):
        node.capture_steps(25, 0)


def test_the_step_is_the_schedule_position_of_the_passs_sigma(node):
    schedule = torch.tensor([1.0, 0.7, 0.4, 0.0])
    assert node.step_of({"sigmas": torch.tensor([0.7]), "sample_sigmas": schedule}) == 1
    assert node.step_of({"sigmas": torch.tensor([0.41, 0.41]), "sample_sigmas": schedule}) == 2
    assert node.step_of({"sigmas": torch.tensor([1.0]), "sample_sigmas": schedule}) == 0
    assert node.step_of({"sample_sigmas": schedule}) is None
    assert node.step_of({"sigmas": torch.tensor([0.7])}) is None


# --- the columns -------------------------------------------------------------

class _HFClip:
    """convert_ids_to_tokens / convert_tokens_to_string of a CLIP tokenizer,
    on a handful of ids. 12 and 13 are one word in two subtokens. The fast
    tokenizer of transformers 5 (ComfyUI's, measured 2026-09-14) hands the
    word-final marker back in convert_tokens_to_string; the slow one strips it.
    The node strips it either way."""
    NAMES = {10: "a</w>", 11: "house</w>", 12: "hou", 13: "se</w>", 14: "lake</w>"}

    def convert_ids_to_tokens(self, tid):
        return self.NAMES[tid]

    def convert_tokens_to_string(self, raws):
        return "".join(raws)


class _HFT5:
    NAMES = {20: "▁a", 21: "▁house", 22: "▁la", 23: "ke"}

    def convert_ids_to_tokens(self, tid):
        return self.NAMES[tid]


class _SubTokenizer:
    def __init__(self, hf, start, end, pad):
        self.tokenizer = hf
        self.start_token, self.end_token, self.pad_token = start, end, pad


class _Tokenizers:
    def __init__(self):
        self.clip_l = _SubTokenizer(_HFClip(), 49406, 49407, 49407)
        self.t5xxl = _SubTokenizer(_HFT5(), None, 1, 0)


class _FakeCLIP:
    """clip.tokenize as ComfyUI's CLIP hands it out: per encoder, chunks of
    (id, weight) pairs, CLIP-L padded with its end token to 77, T5 with 0 to
    the length the graph asked for."""

    def __init__(self, l_ids, t5_ids, t5_len=512):
        l_chunk = [(49406, 1.0)] + [(t, 1.0) for t in l_ids] + [(49407, 1.0)]
        l_chunk += [(49407, 1.0)] * (77 - len(l_chunk))
        t5_chunk = [(t, 1.0) for t in t5_ids] + [(1, 1.0)]
        t5_chunk += [(0, 1.0)] * (t5_len - len(t5_chunk))
        self._by_encoder = {"l": [l_chunk], "g": [l_chunk], "t5xxl": [t5_chunk]}
        self.tokenizer = _Tokenizers()

    def tokenize(self, text):
        return self._by_encoder


def test_the_columns_are_the_word_positions_of_both_tokenizers(node):
    """"a house lake": CLIP-L columns start after BOS, T5's at 77 + position;
    a word in two subtokens is one group; BOS, EOS and padding get no column."""
    clip = _FakeCLIP(l_ids=[10, 12, 13, 14], t5_ids=[20, 21, 22, 23])
    tokens, groups, tokens_t5, groups_t5, columns = node.word_columns(clip, "a house lake")
    assert tokens == ["a", "hou", "se", "lake"]
    assert groups == [[0], [1, 2], [3]]
    assert tokens_t5 == ["a", "house", "la", "ke"]
    assert groups_t5 == [[0], [1], [2, 3]]
    assert columns == [1, 2, 3, 4, 77, 78, 79, 80]


def test_a_prompt_of_nothing_gives_no_column(node):
    clip = _FakeCLIP(l_ids=[], t5_ids=[])
    tokens, groups, tokens_t5, groups_t5, columns = node.word_columns(clip, "")
    assert (tokens, groups, tokens_t5, groups_t5, columns) == ([], [], [], [], [])


def test_a_prompt_past_the_t5_window_is_refused(node):
    """ComfyUI's T5 grows with the text; the map reads the twin's 512, which is
    also the platform's T5 length option."""
    from schemas.engine.comfyui_chunk_support import T5_LENGTH
    assert node.T5_WINDOW == T5_LENGTH
    clip = _FakeCLIP(l_ids=[10], t5_ids=[20] * 520)
    with pytest.raises(RuntimeError, match="runs to 521 T5 positions and the map reads 512"):
        node.word_columns(clip, "a " * 520)
    clip = _FakeCLIP(l_ids=[10], t5_ids=[20] * 511)
    assert len(node.word_columns(clip, "a " * 511)[2]) == 511


# --- the map -----------------------------------------------------------------

N_TXT, N_IMG, HEADS, DIM = 3, 4, 2, 4


def _qkv(batch, seed):
    g = torch.Generator().manual_seed(seed)
    shape = (batch, N_TXT + N_IMG, HEADS * DIM)
    return (torch.randn(shape, generator=g), torch.randn(shape, generator=g),
            torch.randn(shape, generator=g))


def _by_hand(q, k, cols):
    """softmax(QK^T / sqrt(d)) per batch entry and head, the image rows' weights
    on the text columns, text in front: keys 0:N_TXT, queries N_TXT onwards."""
    b = q.shape[0]
    qh = q.reshape(b, N_TXT + N_IMG, HEADS, DIM).transpose(1, 2)
    kh = k.reshape(b, N_TXT + N_IMG, HEADS, DIM).transpose(1, 2)
    total = torch.zeros((N_IMG, len(cols)))
    for entry in range(b):
        for head in range(HEADS):
            scores = qh[entry, head] @ kh[entry, head].T / math.sqrt(DIM)
            weights = torch.softmax(scores, dim=-1)
            total += weights[N_TXT:, :N_TXT][:, cols]
    return total


def _readout(node, steps=(0,), layers=(3,), cols=(0, 2)):
    return node.Readout(list(layers), list(steps), list(cols), ([], [], [], []))


def _sentinel(*args, **kwargs):
    return ("attention as ComfyUI computed it", args, kwargs)


def test_the_map_is_the_softmax_by_hand_with_the_text_in_front(node):
    q, k, v = _qkv(batch=2, seed=1)
    readout = _readout(node)
    out = node.read_attention(_sentinel, q, k, v, HEADS, readout, 0, 3, N_TXT, N_IMG,
                              transformer_options={}, _inside_attn_wrapper=True)
    # the picture's attention is the function's own, called with what it was given
    assert out[0] == "attention as ComfyUI computed it"
    assert len(out[1]) == 4 and out[1][0] is q and out[1][1] is k and out[1][2] is v
    assert out[1][3] == HEADS
    assert out[2] == {"transformer_options": {}, "_inside_attn_wrapper": True}
    expected = _by_hand(q, k, [0, 2])
    assert torch.allclose(readout.sums[(0, 3)], expected, atol=1e-5)
    assert readout.counted[(0, 3)] == 2 * HEADS
    assert (readout.n_img, readout.n_txt) == (N_IMG, N_TXT)
    maps = readout.maps()
    assert list(maps) == ["step_0"] and list(maps["step_0"]) == ["layer_3"]
    assert node.QUANT == 10000  # the twin's scale, attention_processors_sd3.py
    quantized = (expected / (2 * HEADS) * node.QUANT).round().to(torch.int32).tolist()
    assert maps["step_0"]["layer_3"] == quantized


def test_two_passes_of_one_each_weigh_like_one_pass_of_two(node):
    """ComfyUI runs negative and positive as one batch when it can and one after
    the other when it cannot; the twin averaged over its batch of two."""
    q, k, v = _qkv(batch=2, seed=2)
    together = _readout(node)
    node.read_attention(_sentinel, q, k, v, HEADS, together, 0, 3, N_TXT, N_IMG)
    apart = _readout(node)
    for entry in range(2):
        node.read_attention(_sentinel, q[entry:entry + 1], k[entry:entry + 1],
                            v[entry:entry + 1], HEADS, apart, 0, 3, N_TXT, N_IMG)
    assert apart.counted[(0, 3)] == together.counted[(0, 3)] == 2 * HEADS
    assert torch.allclose(apart.sums[(0, 3)], together.sums[(0, 3)], atol=1e-5)
    assert apart.maps() == together.maps()


def test_the_readout_accumulates_in_float32_from_half_inputs(node):
    q, k, v = (t.half() for t in _qkv(batch=1, seed=3))
    readout = _readout(node)
    node.read_attention(_sentinel, q, k, v, HEADS, readout, 0, 3, N_TXT, N_IMG)
    assert readout.sums[(0, 3)].dtype == torch.float32


def test_the_heads_are_summed_in_float32_too(node, monkeypatch):
    """Half precision rounds 1 + 2^-11 to 1; the heads of a slice are cast
    before they are summed, so the map carries what they weighed together."""
    q, k, v = (t.half() for t in _qkv(batch=1, seed=5))
    weights = torch.zeros((HEADS, N_IMG, N_TXT + N_IMG), dtype=torch.float16)
    weights[0] = 1.0
    weights[1:] = 2.0 ** -11
    monkeypatch.setattr(torch, "softmax", lambda scores, dim=-1: weights[: scores.shape[0]])
    readout = _readout(node, cols=(0, 2))
    node.read_attention(_sentinel, q, k, v, HEADS, readout, 0, 3, N_TXT, N_IMG)
    together = 1.0 + (HEADS - 1) * 2.0 ** -11
    assert torch.equal(readout.sums[(0, 3)], torch.full((N_IMG, 2), together))


def test_a_step_that_is_none_of_the_chosen_is_left_alone(node):
    q, k, v = _qkv(batch=1, seed=4)
    readout = _readout(node, steps=(0, 24))
    for step in (1, 23, None):
        out = node.read_attention(_sentinel, q, k, v, HEADS, readout, step, 3, N_TXT, N_IMG)
        assert out[0] == "attention as ComfyUI computed it"
    assert readout.sums == {}


def test_the_image_self_attention_of_a_dual_block_passes_through(node):
    """A dual block (SD 3.5 Medium) calls the attention a second time on the
    image positions alone; its lengths are not the joint ones."""
    g = torch.Generator().manual_seed(5)
    q = torch.randn((1, N_IMG, HEADS * DIM), generator=g)
    readout = _readout(node)
    out = node.read_attention(_sentinel, q, q, q, HEADS, readout, 0, 3, N_TXT, N_IMG)
    assert out[0] == "attention as ComfyUI computed it"
    assert readout.sums == {}


def test_a_mask_on_the_joint_attention_is_refused(node):
    q, k, v = _qkv(batch=1, seed=6)
    readout = _readout(node)
    with pytest.raises(RuntimeError, match="carries a mask"):
        node.read_attention(_sentinel, q, k, v, HEADS, readout, 0, 3, N_TXT, N_IMG,
                            mask=torch.zeros((N_TXT + N_IMG, N_TXT + N_IMG)))


def test_heads_are_read_in_slices_and_the_sum_is_the_same(node, monkeypatch):
    """HEADS_AT_ONCE bounds the scores held at once; the map does not depend on it."""
    q, k, v = _qkv(batch=1, seed=7)
    whole = _readout(node)
    node.read_attention(_sentinel, q, k, v, HEADS, whole, 0, 3, N_TXT, N_IMG)
    monkeypatch.setattr(node, "HEADS_AT_ONCE", 1)
    sliced = _readout(node)
    node.read_attention(_sentinel, q, k, v, HEADS, sliced, 0, 3, N_TXT, N_IMG)
    assert torch.allclose(whole.sums[(0, 3)], sliced.sums[(0, 3)], atol=1e-5)


# --- the block replacement ---------------------------------------------------

def test_the_replacement_runs_the_original_block_with_the_override_set(node):
    readout = _readout(node, steps=(1,))
    replaced = node.block_replacement(readout, 3)
    schedule = torch.tensor([1.0, 0.5, 0.0])
    options = {"sigmas": torch.tensor([0.5]), "sample_sigmas": schedule, "patches": {}}
    q, k, v = _qkv(batch=1, seed=8)
    args = {"img": q[:, N_TXT:], "txt": q[:, :N_TXT], "vec": torch.zeros(1),
            "transformer_options": options}
    seen = {}

    def original_block(block_args):
        seen.update(block_args)
        override = block_args["transformer_options"]["optimized_attention_override"]
        # wrap_attn's call: (func, q, k, v, heads=..., transformer_options=..., _inside_attn_wrapper=True)
        return override(_sentinel, q, k, v, heads=HEADS,
                        transformer_options=block_args["transformer_options"],
                        _inside_attn_wrapper=True)

    out = replaced(args, {"original_block": original_block})
    assert out[0] == "attention as ComfyUI computed it"
    assert len(out[1]) == 4 and out[1][0] is q and out[1][3] == HEADS
    assert out[2]["_inside_attn_wrapper"] is True
    # img, txt and vec went on as they came; the options went on as a copy
    assert seen["img"] is args["img"] and seen["txt"] is args["txt"] and seen["vec"] is args["vec"]
    assert "optimized_attention_override" not in options
    assert seen["transformer_options"]["patches"] is options["patches"]
    # the readout took the step from the sigma and the lengths from the block's inputs
    assert (1, 3) in readout.sums
    assert torch.allclose(readout.sums[(1, 3)], _by_hand(q, k, [0, 2]), atol=1e-5)


def test_the_override_takes_heads_positionally_too(node):
    readout = _readout(node, steps=(0,))
    replaced = node.block_replacement(readout, 3)
    options = {"sigmas": torch.tensor([1.0]), "sample_sigmas": torch.tensor([1.0, 0.0])}
    q, k, v = _qkv(batch=1, seed=9)
    args = {"img": q[:, N_TXT:], "txt": q[:, :N_TXT], "vec": None, "transformer_options": options}

    def original_block(block_args):
        override = block_args["transformer_options"]["optimized_attention_override"]
        return override(_sentinel, q, k, v, HEADS, None, transformer_options={})

    out = replaced(args, {"original_block": original_block})
    assert len(out[1]) == 5 and out[1][0] is q and out[1][3] == HEADS and out[1][4] is None
    assert (0, 3) in readout.sums


# --- the capture node's checks ------------------------------------------------

class _Patcher:
    def __init__(self, blocks):
        self.model = types.SimpleNamespace(
            diffusion_model=types.SimpleNamespace(joint_blocks=[object()] * blocks))
        self.replacements = []

    def clone(self):
        # ModelPatcher.clone copies the patch tables: a replacement set on the
        # clone stays off the loader's cached model.
        twin = _Patcher(len(self.model.diffusion_model.joint_blocks))
        twin.replacements = list(self.replacements)
        return twin

    def set_model_patch_replace(self, patch, name, block_name, number):
        self.replacements.append((name, block_name, number, patch))


def test_the_capture_node_patches_the_named_blocks_and_nothing_else(node):
    clip = _FakeCLIP(l_ids=[10, 11], t5_ids=[20, 21])
    model = _Patcher(blocks=38)
    patched, readout = node.AI4ArtsEdAttentionCapture().patch(
        model, clip, "a house", "3,9,17", 25, 10)
    assert [(n, b, i) for n, b, i, _ in patched.replacements] == [
        ("dit", "double_block", 3), ("dit", "double_block", 9), ("dit", "double_block", 17)]
    assert patched is not model and model.replacements == []
    assert readout.layers == [3, 9, 17]
    assert readout.steps == [0, 10, 20, 24]
    assert readout.columns == [1, 2, 77, 78]
    assert readout.tokens == (["a", "house"], [[0], [1]], ["a", "house"], [[0], [1]])


def test_a_block_the_model_lacks_and_a_model_without_joint_blocks_are_refused(node):
    clip = _FakeCLIP(l_ids=[10], t5_ids=[20])
    with pytest.raises(RuntimeError, match="Block 40 does not exist: this model has 38"):
        node.AI4ArtsEdAttentionCapture().patch(_Patcher(38), clip, "a", "3,40", 25, 1)
    no_blocks = types.SimpleNamespace(model=types.SimpleNamespace(diffusion_model=object()))
    with pytest.raises(RuntimeError, match="no joint blocks"):
        node.AI4ArtsEdAttentionCapture().patch(no_blocks, clip, "a", "3", 25, 1)


def test_a_prompt_with_no_word_is_refused(node):
    with pytest.raises(RuntimeError, match="tokenizes to no word"):
        node.AI4ArtsEdAttentionCapture().patch(_Patcher(38), _FakeCLIP([], []), "", "3", 25, 1)


def test_the_capture_node_is_never_served_from_the_cache(node):
    changed = node.AI4ArtsEdAttentionCapture.IS_CHANGED(model=None, clip=None, text="a")
    assert changed != changed  # NaN: no two runs compare equal


# --- the maps node -----------------------------------------------------------

def _filled_readout(node):
    readout = _readout(node, steps=(0, 1), layers=(3,), cols=(1, 2))
    readout.tokens = (["a", "house"], [[0], [1]], ["a", "house"], [[0], [1]])
    # 6 image positions on a latent of 4 x 6: a swap of height and width
    # would show in the record.
    readout.n_img, readout.n_txt = 6, 589
    for step in (0, 1):
        readout.add(step, 3, torch.full((6, 2), 0.25), 4)
    return readout


def test_the_maps_node_writes_the_record_and_announces_it_under_its_own_key(node, tmp_path):
    readout = _filled_readout(node)
    samples = {"samples": torch.zeros((1, 16, 4, 6))}
    answer = node.AI4ArtsEdAttentionMaps().write(readout, samples, "ai4artsed_attention")
    assert answer["result"] == (samples,)
    announced = answer["ui"]["ai4artsed_attention"]
    assert announced == [{"filename": "ai4artsed_attention_00007_.json", "subfolder": "",
                          "type": "output"}]
    record = json.loads((tmp_path / announced[0]["filename"]).read_text(encoding="utf-8"))
    assert record["tokens"] == ["a", "house"]
    assert record["word_groups"] == [[0], [1]]
    assert record["tokens_t5"] == ["a", "house"]
    assert record["word_groups_t5"] == [[0], [1]]
    assert record["clip_token_count"] == 2
    assert record["attention_maps"] == {"step_0": {"layer_3": [[625, 625]] * 6},
                                        "step_1": {"layer_3": [[625, 625]] * 6}}
    assert record["spatial_resolution"] == [2, 3]
    assert record["image_resolution"] == [32, 48]
    assert record["capture_layers"] == [3]
    assert record["capture_steps"] == [0, 1]
    assert record["text_positions"] == 589


def test_the_maps_node_refuses_an_empty_readout_and_a_latent_of_another_size(node):
    empty = _readout(node)
    with pytest.raises(RuntimeError, match="Nothing was read out"):
        node.AI4ArtsEdAttentionMaps().write(empty, {"samples": torch.zeros((1, 16, 4, 4))}, "x")
    with pytest.raises(RuntimeError, match="holds 6 image positions, the latent 4 x 4 = 16"):
        node.AI4ArtsEdAttentionMaps().write(_filled_readout(node),
                                            {"samples": torch.zeros((1, 16, 8, 8))}, "x")


def test_a_step_the_sampler_passed_by_is_refused_with_its_number(node):
    readout = _filled_readout(node)
    del readout.sums[(1, 3)], readout.counted[(1, 3)]
    with pytest.raises(RuntimeError, match=r"1 of the 2 \(step, block\) maps were never read, "
                                           r"the first at step 1, block 3"):
        node.AI4ArtsEdAttentionMaps().write(readout, {"samples": torch.zeros((1, 16, 4, 6))}, "x")


def test_a_latent_of_odd_size_is_refused_by_the_pictures_size(node):
    """The model pads an odd latent to its patch; the maps would then lie on a
    grid the picture has not got."""
    with pytest.raises(RuntimeError, match="The picture is 1000 x 1008: width and height have to be multiples of 16"):
        node.AI4ArtsEdAttentionMaps().write(_filled_readout(node),
                                            {"samples": torch.zeros((1, 16, 126, 125))}, "x")


def test_the_nodes_are_registered_under_the_names_the_graph_uses(node):
    assert set(node.NODE_CLASS_MAPPINGS) == {"AI4ArtsEdAttentionCapture", "AI4ArtsEdAttentionMaps"}
    assert node.NODE_CLASS_MAPPINGS["AI4ArtsEdAttentionCapture"] is node.AI4ArtsEdAttentionCapture
    assert node.AI4ArtsEdAttentionMaps.OUTPUT_NODE is True


# --- the chunk ---------------------------------------------------------------

def _graph(prompt="a house", negative="", layers="3,9,17", every_n=1):
    # None of these is the chunk's default: a builder that wrote DEFAULTS
    # instead of what it was given would show here.
    return _chunk()._build_workflow(
        prompt=prompt, negative_prompt=negative,
        checkpoint="OfficialStableDiffusion/sd3.5_large.safetensors",
        layers_text=layers, every_n=every_n, width=768, height=1024, steps=30, cfg=5.0,
        seed=11, sampler_name="euler_ancestral", scheduler="sgm_uniform",
    )


def test_the_default_sampler_calls_the_model_once_at_every_step_of_the_schedule():
    # step_of attributes a pass to the nearest sigma of the schedule; a
    # second-order sampler (heun, dpm_2) evaluates between two sigmas as
    # well, and those passes would be read onto a neighbouring step.
    assert _chunk().DEFAULTS["sampler_name"] == "euler"


def test_the_graph_samples_the_patched_model_and_writes_the_maps_after_the_sampler():
    from schemas.engine.comfyui_chunk_support import CLIP_NODE, T5_LENGTH
    chunk = _chunk()
    g = _graph()
    capture = g[chunk.CAPTURE_NODE_ID]
    assert capture["class_type"] == "AI4ArtsEdAttentionCapture"
    assert capture["inputs"] == {
        "model": ["5", 0], "clip": [CLIP_NODE, 0], "text": "a house",
        "capture_layers": "3,9,17", "steps": 30, "capture_every_n_steps": 1,
    }
    # the prompt the node tokenizes is the prompt the encoder gets, at the T5 length
    assert g["1"]["class_type"] == "AI4ArtsEdSD3TextEncode"
    assert g["1"]["inputs"] == {"clip_l": "a house", "clip_g": "a house", "t5xxl": "a house",
                                "empty_padding": "empty_prompt", "clip": [CLIP_NODE, 0]}
    assert g["6"]["inputs"]["clip_l"] == "" and g["6"]["inputs"]["empty_padding"] == "empty_prompt"
    assert g[CLIP_NODE]["inputs"]["min_length"] == T5_LENGTH
    assert g["20"]["class_type"] == "KSampler"
    assert g["20"]["inputs"] == {
        "model": [chunk.CAPTURE_NODE_ID, 0], "positive": ["1", 0], "negative": ["6", 0],
        "latent_image": ["3", 0], "seed": 11, "steps": 30, "cfg": 5.0,
        "sampler_name": "euler_ancestral", "scheduler": "sgm_uniform", "denoise": 1,
    }
    assert g["3"]["inputs"] == {"width": 768, "height": 1024, "batch_size": 1}
    maps = g[chunk.MAPS_NODE_ID]
    assert maps["class_type"] == "AI4ArtsEdAttentionMaps"
    assert maps["inputs"] == {"readout": [chunk.CAPTURE_NODE_ID, 1], "samples": ["20", 0],
                              "filename_prefix": "ai4artsed_attention"}
    # the decode reads the latent through the maps node, so the maps are written
    # before the picture is saved
    assert g["22"]["inputs"] == {"samples": [chunk.MAPS_NODE_ID, 0], "vae": ["5", 2]}
    assert g[chunk.SAVE_NODE_ID]["class_type"] == "SaveImage"
    assert g[chunk.SAVE_NODE_ID]["inputs"]["images"] == ["22", 0]


def test_a_size_off_the_grid_is_refused_before_anything_is_submitted(monkeypatch):
    import asyncio
    import my_app.services.latent_lab_capabilities as capabilities

    async def able():
        return {"attention_cartography": True}

    monkeypatch.setattr(capabilities, "get_latent_lab_capabilities", able)
    with pytest.raises(ValueError, match="multiples of 16, got 1000x1024"):
        asyncio.run(_chunk().execute(prompt="a house", width=1000, height=1024))


def test_the_layers_the_surface_sends_become_the_nodes_text():
    chunk = _chunk()
    assert chunk._layers_text([3, 9, 17]) == "3,9,17"
    assert chunk._layers_text("3, 9") == "3,9"
    with pytest.raises(ValueError, match="'x' is no block index"):
        chunk._layers_text(["3", "x"])
    with pytest.raises(ValueError, match="names no block"):
        chunk._layers_text([])


class _File:
    def __init__(self, data, media_type="attention", node_id="31", filename="m.json"):
        self.data, self.media_type, self.node_id, self.filename = data, media_type, node_id, filename


class _Result:
    prompt_id = "p-1"

    def __init__(self, files):
        self.media_files = files


def test_the_record_is_read_from_the_announced_file_and_checked_for_its_keys():
    chunk = _chunk()
    # The ten keys the Diffusers twin returned
    # (output_image_attention_cartography_diffusers.py, execute) and the
    # surface reads (views/latent_lab/attention_cartography.vue).
    assert chunk.RECORD_KEYS == (
        "tokens", "word_groups", "tokens_t5", "word_groups_t5", "clip_token_count",
        "attention_maps", "spatial_resolution", "image_resolution", "capture_layers",
        "capture_steps")
    record = {key: [] for key in chunk.RECORD_KEYS}
    record["tokens"] = ["a", "house"]
    record["attention_maps"] = {"step_0": {"layer_3": [[1]]}}
    good = _File(json.dumps(record).encode("utf-8"))
    assert chunk.attention_record(_Result([_File(b"png", media_type="image", node_id="40"), good])) == record
    with pytest.raises(RuntimeError, match="announced no maps file"):
        chunk.attention_record(_Result([_File(b"png", media_type="image", node_id="40")]))
    with pytest.raises(RuntimeError, match="is no JSON"):
        chunk.attention_record(_Result([_File(b"{not json")]))
    short = dict(record)
    del short["word_groups_t5"], short["capture_steps"]
    with pytest.raises(RuntimeError, match="lacks word_groups_t5, capture_steps"):
        chunk.attention_record(_Result([_File(json.dumps(short).encode("utf-8"))]))
    no_tokens = dict(record, tokens=[])
    with pytest.raises(RuntimeError, match="m.json carries 0 tokens and maps of 1 steps"):
        chunk.attention_record(_Result([_File(json.dumps(no_tokens).encode("utf-8"))]))
    no_maps = dict(record, attention_maps={})
    with pytest.raises(RuntimeError, match="m.json carries 2 tokens and maps of 0 steps"):
        chunk.attention_record(_Result([_File(json.dumps(no_maps).encode("utf-8"))]))


def test_the_ws_client_fetches_the_announced_file_as_attention_and_escapes_the_nodes_text():
    sys.path.insert(0, str(DEVSERVER))
    from my_app.services.comfyui_ws_client import ANNOUNCED_FILES, SD35_TEXT_FIELDS, as_written
    assert ("ai4artsed_attention", "attention") in ANNOUNCED_FILES
    assert [k for k, _ in ANNOUNCED_FILES][0] == "images"
    assert SD35_TEXT_FIELDS["AI4ArtsEdAttentionCapture"] == ("text",)
    g = _graph(prompt="a house (built 1920)")
    written = as_written(g)
    chunk = _chunk()
    assert written[chunk.CAPTURE_NODE_ID]["inputs"]["text"] == "a house \\(built 1920\\)"
    assert written["1"]["inputs"]["t5xxl"] == "a house \\(built 1920\\)"


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_every_announced_file_is_fetched_by_its_kind_and_a_refused_one_stops_the_run(monkeypatch):
    import asyncio
    sys.path.insert(0, str(DEVSERVER))
    import my_app.services.comfyui_ws_client as ws

    monkeypatch.setattr(ws.aiohttp, "ClientSession", _Session)
    client = ws.ComfyUIWebSocketClient(base_url="http://comfy.test")
    fetched = []

    async def view(session, filename, subfolder, type_name):
        fetched.append((filename, subfolder, type_name))
        if filename == "gone.png":
            raise RuntimeError("/view answered HTTP 404 for gone.png")
        return filename.encode("utf-8")

    monkeypatch.setattr(client, "_view", view)
    outputs = {
        "31": {"ai4artsed_attention": [{"filename": "m.json", "subfolder": "", "type": "output"}]},
        "40": {"images": [{"filename": "a.png", "type": "output"}],
               "latents": [{"filename": "l.latent", "meta": {"space": "sd3"}}]},
        "50": {"gifs": [{"filename": "v.mp4", "subfolder": "video", "type": "temp"}],
               "genaudio": [{"filename": "s.flac"}]},
    }
    files = asyncio.run(client._announced_files(outputs))
    assert [(f.node_id, f.media_type, f.filename, f.subfolder, f.data, f.meta) for f in files] == [
        ("31", "attention", "m.json", "", b"m.json", {}),
        ("40", "image", "a.png", "", b"a.png", {}),
        ("40", "latent", "l.latent", "", b"l.latent", {"space": "sd3"}),
        ("50", "audio", "s.flac", "", b"s.flac", {}),
        ("50", "video", "v.mp4", "video", b"v.mp4", {}),
    ]
    assert fetched[3] == ("s.flac", "", "output") and fetched[4] == ("v.mp4", "video", "temp")
    outputs["40"]["images"].append({"filename": "gone.png"})
    with pytest.raises(RuntimeError, match="announced gone.png at node 40 and fetching it failed: "
                                           "/view answered HTTP 404"):
        asyncio.run(client._announced_files(outputs))
