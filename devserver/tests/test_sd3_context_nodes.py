"""
The text stream of SD 3.5's joint blocks, written into on ComfyUI.

The node family (comfyui_nodes/ai4artsed_sd3_context.py) carries four
instruments of the embedding research series that the Diffusers twin
(gpu_service/services/diffusers_backend.py) ran with a forward pre-hook: the
scheduled fusion of the Fusion Workbench, the Decomposition's cells, the
position probe and the delayed kick-in. What is checked here, against numbers
set by hand:

  * the step and the window, read the way the twin compared them
    (lo <= step / steps < hi), and the sides of a batch, read from the sampler;
  * the stream slices in the conditioning's layout, and the probe's slice of
    the embedded stream;
  * each writer: what it writes on which entries, and what it leaves alone;
  * the composition of two replacements at one block;
  * the recording of a run and its replay before and from the kick-in step;
  * the nodes' refusals, and the names the graphs use.

Every tensor here is small; nothing needs a card.
"""

import copy
import inspect
import sys
import types

import pytest

torch = pytest.importorskip("torch")

from file_modules import REPO, load_module

NODE_FILE = REPO / "comfyui_nodes" / "ai4artsed_sd3_context.py"
ATTENTION_FILE = REPO / "comfyui_nodes" / "ai4artsed_attention_capture.py"

# A conditioning of SD 3.5's shape: 77 CLIP positions and a T5 tail, 4096 wide.
POSITIONS, WIDTH = 77 + 5, 4096
STEPS = 25


@pytest.fixture
def node():
    return load_module("ai4artsed_sd3_context_under_test", NODE_FILE)


def _schedule():
    return torch.linspace(1.0, 0.0, STEPS + 1)


def _options(step, sides=(0, 1)):
    """transformer_options as calc_cond_batch hands them to a block at `step`."""
    schedule = _schedule()
    return {"sigmas": schedule[step:step + 1], "sample_sigmas": schedule,
            "cond_or_uncond": list(sides)}


class _Patcher:
    """ModelPatcher as the nodes use it: the diffusion model's blocks and
    context embedder, the patch tables, and a clone that copies them."""

    def __init__(self, blocks=38, hidden=8, processor=None):
        torch.manual_seed(0)
        self.model = types.SimpleNamespace(diffusion_model=types.SimpleNamespace(
            joint_blocks=[object()] * blocks,
            context_embedder=torch.nn.Linear(WIDTH, hidden),
            context_processor=processor,
        ))
        self.model_options = {"transformer_options": {}}

    def clone(self):
        twin = _Patcher.__new__(_Patcher)
        twin.model = self.model
        twin.model_options = copy.deepcopy(self.model_options)
        return twin

    def set_model_patch_replace(self, patch, name, block_name, number):
        table = self.model_options["transformer_options"].setdefault("patches_replace", {})
        table.setdefault(name, {})[(block_name, number)] = patch

    def replacements(self):
        return self.model_options["transformer_options"].get("patches_replace", {}).get("dit", {})


def _cond(value, positions=POSITIONS):
    """A CONDITIONING of one entry holding `value` everywhere."""
    return [[torch.full((1, positions, WIDTH), float(value)), {}]]


def _txt(patcher, batch=2, seed=1):
    hidden = patcher.model.diffusion_model.context_embedder.out_features
    return torch.randn((batch, POSITIONS, hidden), generator=torch.Generator().manual_seed(seed))


def _embed(patcher, conditioning):
    with torch.no_grad():
        return patcher.model.diffusion_model.context_embedder(conditioning[0][0])


# --- what is shared with the attention module ---------------------------------

def test_the_readers_of_the_step_and_the_blocks_are_the_attention_modules_own(node, tmp_path, monkeypatch):
    """One reading of the sampler's sigmas on the platform. ComfyUI registers a
    single-file node under its full path, so the text is held equal instead of
    imported."""
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: str(tmp_path)
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)
    attention = load_module("ai4artsed_attention_capture_for_context", ATTENTION_FILE)
    for name in ("step_of", "parse_layers"):
        assert inspect.getsource(getattr(node, name)) == inspect.getsource(getattr(attention, name))


# --- the step, the window, the sides -----------------------------------------

def test_the_window_is_compared_as_the_twin_compared_it(node):
    assert node.position(_options(8)) == (8, STEPS)
    assert node.steps_of({"sample_sigmas": _schedule()}) == STEPS
    # 8 / 25 = 0.32 enters the semantics band; 7 / 25 stays in composition;
    # 17 / 25 = 0.68 is the detail band's first step.
    assert node.in_window(_options(8), 0.32, 0.68)
    assert not node.in_window(_options(7), 0.32, 0.68)
    assert not node.in_window(_options(17), 0.32, 0.68)
    assert node.in_window(_options(17), 0.68, 1.01)
    assert node.in_window(_options(24), 0.68, 1.01)
    with pytest.raises(RuntimeError, match="did not say which step"):
        node.position({"cond_or_uncond": [0, 1]})


def test_the_sides_of_a_batch_come_from_the_sampler(node):
    txt = torch.zeros((2, 3, 4))
    assert node.sides_of(txt, {"cond_or_uncond": [0, 1]}) == [0, 1]
    assert node.sides_of(txt, {"cond_or_uncond": [1, 0]}) == [1, 0]
    assert node.sides_of(txt, {"cond_or_uncond": [1]}) == [1, 1]
    assert node.sides_of(torch.zeros((4, 3, 4)), {"cond_or_uncond": [0, 1]}) == [0, 0, 1, 1]
    with pytest.raises(RuntimeError, match="do not divide"):
        node.sides_of(torch.zeros((3, 3, 4)), {"cond_or_uncond": [0, 1]})
    with pytest.raises(RuntimeError, match="did not say which entries"):
        node.sides_of(txt, {})


# --- the conditionings --------------------------------------------------------

def test_one_conditioning_of_one_tensor_is_taken_and_every_other_shape_refused(node):
    assert node.cond_tensor(_cond(1), "positive").shape == (1, POSITIONS, WIDTH)
    with pytest.raises(RuntimeError, match="positive holds 2 conditionings"):
        node.cond_tensor(_cond(1) + _cond(2), "positive")
    with pytest.raises(RuntimeError, match="positive holds no conditionings"):
        node.cond_tensor(None, "positive")
    with pytest.raises(RuntimeError, match=r"carries no \[batch, positions, width\] tensor"):
        node.cond_tensor([[torch.zeros((3, 4)), {}]], "base")


def test_a_stream_is_swapped_in_the_conditionings_own_layout(node):
    base, override = torch.zeros((1, POSITIONS, WIDTH)), torch.ones((1, POSITIONS, WIDTH))
    clip_l = node.with_stream(base, override, "clip_l", "the override")
    assert clip_l[:, :77, :768].eq(1).all() and clip_l.sum() == 77 * 768
    clip_g = node.with_stream(base, override, "clip_g", "the override")
    assert clip_g[:, :77, 768:2048].eq(1).all() and clip_g.sum() == 77 * 1280
    t5 = node.with_stream(base, override, "t5", "the override")
    assert t5[:, 77:, :].eq(1).all() and t5.sum() == (POSITIONS - 77) * WIDTH
    assert base.sum() == 0  # the base is left as it was
    with pytest.raises(RuntimeError, match="is no stream"):
        node.with_stream(base, override, "pooled", "the override")
    with pytest.raises(RuntimeError, match="stands on 82 positions and the override on 90"):
        node.with_stream(base, torch.ones((1, 90, WIDTH)), "t5", "the override")
    with pytest.raises(RuntimeError, match="holds no SD 3.5 CLIP block"):
        node.with_stream(torch.zeros((1, 10, 64)), torch.ones((1, 10, 64)), "clip_l", "x")


def test_the_embedder_is_the_models_own_and_computes_a_conditioning_once(node):
    patcher = _Patcher()
    embed = node.Embedder(patcher)
    like = torch.zeros((2, POSITIONS, 8))
    first = embed("positive", _cond(1)[0][0], like)
    assert torch.equal(first, _embed(patcher, _cond(1)))
    assert embed("positive", _cond(2)[0][0], like) is first  # the key names the run's tensor
    assert embed("negative", _cond(2)[0][0], like) is not first
    embed.check_block(37)
    with pytest.raises(RuntimeError, match="Block 38 does not exist: this model has 38"):
        embed.check_block(38)
    with pytest.raises(RuntimeError, match="through a processor"):
        node.Embedder(_Patcher(processor=object()))
    no_blocks = types.SimpleNamespace(model=types.SimpleNamespace(diffusion_model=object()))
    with pytest.raises(RuntimeError, match="no joint blocks"):
        node.Embedder(no_blocks)


# --- the replacement and the writers ------------------------------------------

def test_a_replacement_writes_the_text_and_hands_the_block_on(node):
    patcher = _Patcher().clone()
    seen = []

    def write(txt, options):
        seen.append(options["sigmas"])
        return txt + 1

    node.install(patcher, 3, write)
    replaced = patcher.replacements()[("double_block", 3)]
    args = {"txt": torch.zeros((2, 3, 4)), "img": torch.ones((2, 5, 4)), "vec": None,
            "transformer_options": _options(0)}
    extra = {"original_block": lambda a: {"txt": a["txt"] * 10, "img": a["img"]}}
    out = replaced(args, extra)
    assert out["txt"].eq(10).all() and out["img"] is args["img"]
    assert args["txt"].eq(0).all()  # the block's own args are left alone
    assert len(seen) == 1

    # a second replacement at the same block runs first and hands on to the first
    node.install(patcher, 3, lambda txt, options: txt + 100)
    out = patcher.replacements()[("double_block", 3)](args, extra)
    assert out["txt"].eq(1010).all()

    # with an embedder, what it holds is dropped after the pass of the last step
    embed = node.Embedder(_Patcher())
    node.install(patcher, 4, lambda txt, options: embed("k", _cond(1)[0][0], txt), embed)
    replaced = patcher.replacements()[("double_block", 4)]
    replaced({**args, "transformer_options": _options(STEPS - 2)}, extra)
    assert list(embed.cache) == ["k"]
    replaced({**args, "transformer_options": _options(STEPS - 1)}, extra)
    assert embed.cache == {}


def test_replacing_writes_each_side_its_conditioning_inside_the_window(node):
    patcher = _Patcher()
    embed = node.Embedder(patcher)
    pos, neg = _cond(1)[0][0], _cond(-1)[0][0]
    txt = _txt(patcher)
    write = node.replacing(embed, pos, neg, 0.32, 0.68)
    out = write(txt, _options(8, sides=(1, 0)))
    assert torch.equal(out[0], _embed(patcher, _cond(-1))[0])  # entry 0 is the negative here
    assert torch.equal(out[1], _embed(patcher, _cond(1))[0])
    assert write(txt, _options(7)) is txt
    without = node.replacing(embed, pos, None, 0.0, 1.01)(txt, _options(0))
    assert torch.equal(without[0], _embed(patcher, _cond(1))[0])
    assert torch.equal(without[1], txt[1])
    with pytest.raises(RuntimeError, match="The positive stands on 90 positions"):
        node.replacing(node.Embedder(patcher), _cond(1, positions=90)[0][0], None,
                       0.0, 1.01)(txt, _options(0))


def test_adding_adds_alpha_times_the_delta_on_the_positive_entries_only(node):
    patcher = _Patcher()
    embed = node.Embedder(patcher)
    base, modified = _cond(1)[0][0], node.with_stream(_cond(1)[0][0], _cond(3)[0][0], "t5", "o")
    txt = _txt(patcher)
    out = node.adding(embed, base, modified, -0.5, 0.0, 0.32)(txt, _options(0))
    delta = _embed(patcher, [[modified, {}]])[0] - _embed(patcher, _cond(1))[0]
    assert torch.allclose(out[0], txt[0] - 0.5 * delta)
    assert torch.equal(out[1], txt[1])
    assert node.adding(embed, base, modified, 1.0, 0.0, 0.32)(txt, _options(8)) is txt


def test_probing_replaces_one_streams_slice_of_the_embedded_stream(node):
    patcher = _Patcher(hidden=2048)
    embed = node.Embedder(patcher)
    modified = node.with_stream(_cond(1)[0][0], _cond(3)[0][0], "clip_l", "p")
    txt = _txt(patcher)
    out = node.probing(embed, modified, "clip_l", 0.0, 1.01)(txt, _options(3))
    target = _embed(patcher, [[modified, {}]])[0]
    assert torch.equal(out[0, :77, :768], target[:77, :768])
    assert torch.equal(out[0, 77:, :], txt[0, 77:, :])
    assert torch.equal(out[0, :77, 768:], txt[0, :77, 768:])
    assert torch.equal(out[1], txt[1])


# --- recording and replay -----------------------------------------------------

def test_a_run_is_recorded_per_side_and_replayed_before_and_from_the_kickin(node):
    patcher = _Patcher()
    early, full = node.Trajectory([5]), node.Trajectory([5])
    for trajectory, seed in ((early, 10), (full, 20)):
        writer = node.recording(trajectory, 5)
        for step in range(STEPS):
            txt = _txt(patcher, seed=seed + step)
            assert writer(txt, _options(step)) is txt
    assert torch.equal(early.frame(5, 3, 0), _txt(patcher, seed=13)[0:1])
    assert torch.equal(early.frame(5, 3, 1), _txt(patcher, seed=13)[1:2])
    replay = node.replaying(early, full, 10, 5)
    fresh = torch.zeros((2, POSITIONS, 8))
    assert torch.equal(replay(fresh, _options(9)), _txt(patcher, seed=19))
    assert torch.equal(replay(fresh, _options(10)), _txt(patcher, seed=30))
    # sides in the sampler's other order, and one side alone
    assert torch.equal(replay(fresh, _options(9, sides=(1, 0))), _txt(patcher, seed=19).flip(0))
    assert torch.equal(replay(fresh[:1], _options(9, sides=(0,))), _txt(patcher, seed=19)[0:1])
    with pytest.raises(RuntimeError, match="early run's recording has no frame for block 6"):
        node.replaying(early, full, 10, 6)(fresh, _options(0))
    with pytest.raises(RuntimeError, match="frame for block 5, step 0 is"):
        replay(torch.zeros((2, 90, 8)), _options(0))
    early.clear()
    assert early.frame(5, 3, 0) is None


# --- the nodes ----------------------------------------------------------------

def test_the_replace_node_installs_at_the_named_blocks_on_a_clone(node):
    model = _Patcher()
    (patched,) = node.AI4ArtsEdSD3ContextReplace().patch(
        model, _cond(1), "10, 23", 0.32, 0.68, negative=_cond(-1))
    assert sorted(patched.replacements()) == [("double_block", 10), ("double_block", 23)]
    assert model.replacements() == {}
    with pytest.raises(RuntimeError, match="Block 40 does not exist"):
        node.AI4ArtsEdSD3ContextReplace().patch(model, _cond(1), "40", 0.0, 1.01)
    with pytest.raises(RuntimeError, match="two fractions of the run between 0 and 1.01"):
        node.AI4ArtsEdSD3ContextReplace().patch(model, _cond(1), "0", 0.0, 2.0)
    with pytest.raises(ValueError, match="blocks names no block"):
        node.AI4ArtsEdSD3ContextReplace().patch(model, _cond(1), "", 0.0, 1.01)


def test_two_delta_nodes_at_one_block_add_both_deltas(node):
    """The Decomposition's cells chain on the MODEL; the twin summed the deltas
    of a (phase, band) and added the sum once."""
    model = _Patcher()
    base = _cond(1)
    (once,) = node.AI4ArtsEdSD3ContextDelta().patch(model, base, _cond(3), "t5", 10, 0.0, 0.32, 1.0)
    (twice,) = node.AI4ArtsEdSD3ContextDelta().patch(once, base, _cond(5), "clip_g", 10, 0.0, 0.32, 0.5)
    assert list(once.replacements()) == [("double_block", 10)]
    txt = _txt(model)
    args = {"txt": txt, "img": None, "vec": None, "transformer_options": _options(2)}
    out = twice.replacements()[("double_block", 10)](args, {"original_block": lambda a: a})
    embed_base = _embed(model, base)[0]
    d1 = _embed(model, [[node.with_stream(base[0][0], _cond(3)[0][0], "t5", "o"), {}]])[0] - embed_base
    d2 = _embed(model, [[node.with_stream(base[0][0], _cond(5)[0][0], "clip_g", "o"), {}]])[0] - embed_base
    assert torch.allclose(out["txt"][0], txt[0] + d1 + 0.5 * d2, atol=1e-6)
    assert torch.equal(out["txt"][1], txt[1])


def test_the_probe_node_covers_the_block_range_and_refuses_an_empty_one(node):
    model = _Patcher()
    (patched,) = node.AI4ArtsEdSD3ContextProbe().patch(
        model, _cond(1), _cond(2), "t5", 5, 8, 0.0, 0.4)
    assert sorted(patched.replacements()) == [("double_block", b) for b in (5, 6, 7)]
    with pytest.raises(RuntimeError, match=r"\[8, 8\) names no block"):
        node.AI4ArtsEdSD3ContextProbe().patch(model, _cond(1), _cond(2), "t5", 8, 8, 0.0, 1.01)
    with pytest.raises(RuntimeError, match="Block 38 does not exist"):
        node.AI4ArtsEdSD3ContextProbe().patch(model, _cond(1), _cond(2), "t5", 37, 39, 0.0, 1.01)


def test_capture_replay_and_release_carry_a_run_from_one_sampler_to_the_next(node):
    model = _Patcher()
    capture = node.AI4ArtsEdSD3ContextCapture()
    changed = capture.IS_CHANGED(model=None, block_from=0, block_to=1)
    assert changed != changed  # NaN: never from the cache
    early_model, early = capture.patch(model, 5, 6)
    full_model, full = capture.patch(model, 5, 6)
    assert early.blocks == [5] and list(early_model.replacements()) == [("double_block", 5)]
    replay = node.AI4ArtsEdSD3ContextReplay()
    with pytest.raises(RuntimeError, match="early run recorded nothing"):
        replay.patch(model, early, full, 3, {"samples": None}, {"samples": None})
    for trajectory, patched in ((early, early_model), (full, full_model)):
        for step in range(STEPS):
            args = {"txt": _txt(model, seed=step), "img": None, "vec": None,
                    "transformer_options": _options(step)}
            patched.replacements()[("double_block", 5)](args, {"original_block": lambda a: a})
    (replayed,) = replay.patch(model, early, full, 3, {"samples": None}, {"samples": None})
    assert list(replayed.replacements()) == [("double_block", 5)]
    _other_model, other = capture.patch(model, 4, 6)
    with pytest.raises(RuntimeError, match="different blocks"):
        replay.patch(model, early, other, 3, {"samples": None}, {"samples": None})
    samples = {"samples": torch.zeros((1, 16, 4, 4))}
    assert node.AI4ArtsEdSD3ContextRelease().release(samples, early, full) == (samples,)
    assert early.frames == {} and full.frames == {}


def test_a_recording_is_held_off_the_card_and_a_capture_node_drops_its_previous_run(node):
    model = _Patcher()
    capture = node.AI4ArtsEdSD3ContextCapture()
    first_model, first = capture.patch(model, 5, 6)
    txt = _txt(model)
    first_model.replacements()[("double_block", 5)](
        {"txt": txt, "img": None, "vec": None, "transformer_options": _options(0)},
        {"original_block": lambda a: a})
    frame = first.frame(5, 0, 0)
    assert frame.device.type == "cpu" and torch.equal(frame[0], txt[0])  # entry 0 is the positive
    # the same node object, run again: the frames its previous run left are gone
    capture.patch(model, 5, 6)
    assert first.frames == {}


def test_the_nodes_are_registered_under_the_names_the_graphs_use(node):
    assert set(node.NODE_CLASS_MAPPINGS) == {
        "AI4ArtsEdSD3ContextReplace", "AI4ArtsEdSD3ContextDelta", "AI4ArtsEdSD3ContextProbe",
        "AI4ArtsEdSD3ContextCapture", "AI4ArtsEdSD3ContextReplay", "AI4ArtsEdSD3ContextRelease",
    }
    assert set(node.NODE_DISPLAY_NAME_MAPPINGS) == set(node.NODE_CLASS_MAPPINGS)
    assert node.AI4ArtsEdSD3ContextCapture.RETURN_TYPES == ("MODEL", "AI4ARTSED_SD3_CONTEXT_TRAJECTORY")
