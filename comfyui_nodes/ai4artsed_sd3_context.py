"""
AI4ArtsEd - the text stream of SD 3.5's transformer, written into per block and
per step (ComfyUI custom nodes)

Stage 4 of the move to ComfyUI.
Four instruments of the embedding research series work on the same place in the
model: the text tokens a joint block receives, after the context embedder has
projected the conditioning into the transformer's width. The Diffusers twin
(gpu_service/services/diffusers_backend.py) reached that place with a forward
pre-hook on the block that swapped `encoder_hidden_states`; here it is ComfyUI's
block replacement, `patches_replace["dit"][("double_block", i)]`, which
mmdit.py forward_core_with_concat hands the block's txt and img and asks for the
block's answer. The replacement writes into txt and runs the block as it is.

    AI4ArtsEdSD3ContextReplace   txt <- embed(positive) on the positive entries,     scheduled fusion
                                 embed(negative) on the negative ones, in a step     (Fusion Workbench);
                                 window, at the named blocks                         delayed kick-in at block 0
    AI4ArtsEdSD3ContextDelta     txt += alpha * (embed(base with one stream from     Decomposition, one cell
                                 the override) - embed(base)), positive entries
    AI4ArtsEdSD3ContextProbe     one stream's slice of txt <- the same slice of      position probe
                                 embed(base with that stream from the probe),
                                 positive entries, at every block of a range
    AI4ArtsEdSD3ContextCapture   txt recorded per block, step and side               delayed kick-in past
    AI4ArtsEdSD3ContextReplay    txt <- one run's recording before the kick-in       block 0, per block
                                 step, the other run's from it on                     or cumulative
    AI4ArtsEdSD3ContextRelease   the recordings freed once the picture is sampled

`embed` is the model's own context_embedder, applied inside the run to the
conditioning in the dtype and on the device the block computes in, so what is
written in is what block 0 would have received for that conditioning. The twin
computed it once before the run, in its pipeline's dtype; the values are the
same values.

What the twin did with the batch is kept: it saw [negative; positive] as one
batch of two and wrote the positive half, or both halves, by position. ComfyUI
batches the two sides when it can and otherwise runs them one after the other at
the same sigma, and says which entries are which
(transformer_options["cond_or_uncond"], samplers.py calc_cond_batch); the
nodes read that rather than the position, and the recording of a run is kept
per side for the same reason.

The step of a pass is read from the sigmas, as ai4artsed_attention_capture.py
reads it; a test holds the two readings together. The window an instrument names
is compared the way the twin compared it, `lo <= step / steps < hi` with the step
counted from zero, so that a schedule written for the twin runs here unchanged.

Two replacements at one block are composed rather than the second overwriting
the first: a replacement installed by these nodes writes its txt and then hands
the block to whatever stood at that key before it, or to the original block. The
cells of a Decomposition run chain on the MODEL that way; the twin summed their
deltas and added the sum once, here each cell adds its own, and the two differ
in the order of a floating-point sum and in nothing else.

The recordings of the kick-in instruments are held in host memory and each
frame goes back to the card at the step that replays it: a run over all 38
blocks of SD 3.5 Large at 25 steps holds some 5 GB per recorded run, and the
executor keeps a node's outputs past the run, on the card had they been left
there. Release frees them after the main run; a run whose main sampler raised
never reaches Release, so a Capture node also frees what its own previous run
left. What the embedder computed for a cell is dropped after the pass of the
run's last step for the same reason: the executor keeps the MODEL a node
handed out, and the replacement in it, for every cell ever run.
"""

import logging

import torch

logger = logging.getLogger(__name__)

# The positions the two CLIP encoders fill, and the widths they write at
# inside the assembled conditioning: CLIP-L at 0:768, CLIP-G at 768:2048, both
# on the first 77 positions; T5 on the positions after, at every dimension
# (gpu_service/services/diffusers_backend.py, DECOMP_STREAM_SLICES, which the
# Diffusers decomposition path keeps). The probe takes the same slices of the
# EMBEDDED stream, where its Diffusers twin took them (that twin was struck
# from the backend on 2026-10-10).
STREAM_SLICES = {
    "clip_l": (slice(0, 77), slice(0, 768)),
    "clip_g": (slice(0, 77), slice(768, 2048)),
    "t5": (slice(77, None), slice(None, None)),
}
STREAMS = ["clip_l", "clip_g", "t5"]

# What the two CLIP slices need of a conditioning: the block of 77 positions,
# and CLIP-G's upper edge.
CLIP_POSITIONS = 77
CLIP_WIDTH = 2048

# The twin's DECOMP_STEP_BANDS run to 1.01 so that a window can name the end of
# the run; the widgets reach that far.
WINDOW_MAX = 1.01


def parse_layers(text, field="capture_layers"):
    """Block indices from "3,9,17"; `field` names the input in a refusal."""
    out = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ValueError(f"{field} {text!r}: {part!r} is no block index")
        out.append(int(part))
    if not out:
        raise ValueError(f"{field} names no block")
    if len(set(out)) != len(out):
        # The second replacement of a block would overwrite the first, and
        # the block would be named twice in what the run reports.
        raise ValueError(f"{field} {text!r}: a block is named twice")
    return out


def step_of(transformer_options):
    """Which step of the schedule a forward pass belongs to, or None.

    The sampler writes the pass's sigma into transformer_options["sigmas"]
    (samplers.py calc_cond_batch) and the whole schedule into
    ["sample_sigmas"] (CFGGuider.inner_sample); the step is the schedule
    position of the sigma. Euler calls the model once per step.
    """
    sigmas = transformer_options.get("sigmas")
    schedule = transformer_options.get("sample_sigmas")
    if sigmas is None or schedule is None:
        return None
    sigma = torch.as_tensor(sigmas).detach().flatten()[0].float().cpu()
    schedule = torch.as_tensor(schedule).detach().flatten().float().cpu()
    if schedule.numel() == 0:
        return None
    return int(torch.argmin((schedule - sigma).abs()).item())


def steps_of(transformer_options):
    """How many steps the run has: the schedule holds one sigma more."""
    schedule = transformer_options.get("sample_sigmas")
    if schedule is None:
        return None
    return max(1, int(torch.as_tensor(schedule).flatten().numel()) - 1)


def position(transformer_options):
    """(step, steps) of a pass; a pass without a schedule is refused rather than
    written into at a step nobody named."""
    step = step_of(transformer_options)
    steps = steps_of(transformer_options)
    if step is None or steps is None:
        raise RuntimeError(
            "The sampler did not say which step this pass is (no sigmas in "
            "transformer_options); the SD 3.5 context nodes run under ComfyUI's "
            "samplers."
        )
    return step, steps


def in_window(transformer_options, lo, hi):
    """The twin's comparison: frac = step / steps, and lo <= frac < hi."""
    step, steps = position(transformer_options)
    frac = step / steps
    return lo <= frac < hi


def sides_of(txt, transformer_options):
    """For every entry of the batch, which side it carries: 0 the positive, 1
    the negative. calc_cond_batch lists the sides in batch order, one chunk of
    equal size each."""
    order = transformer_options.get("cond_or_uncond")
    if not order:
        raise RuntimeError(
            "The sampler did not say which entries of the batch are positive and "
            "which negative (no cond_or_uncond in transformer_options); the "
            "SD 3.5 context nodes run under ComfyUI's samplers."
        )
    n = int(txt.shape[0])
    if n % len(order) != 0:
        raise RuntimeError(
            f"A batch of {n} entries carries {len(order)} sides; the sides do "
            f"not divide it."
        )
    per = n // len(order)
    return [int(order[j // per]) for j in range(n)]


def cond_tensor(conditioning, name):
    """The one tensor a CONDITIONING carries, [1, positions, 4096]."""
    if not isinstance(conditioning, (list, tuple)) or len(conditioning) != 1:
        held = len(conditioning) if isinstance(conditioning, (list, tuple)) else "no"
        raise RuntimeError(
            f"{name} holds {held} conditionings; these nodes write one in. "
            f"Encode one prompt for it."
        )
    tensor = conditioning[0][0]
    if not torch.is_tensor(tensor) or tensor.dim() != 3:
        raise RuntimeError(f"{name} carries no [batch, positions, width] tensor.")
    return tensor


def with_stream(base, override, stream, override_name):
    """`base` with one encoder's stream taken from `override`, in the
    conditioning's own layout (STREAM_SLICES). The twin swapped the slice
    before the embedder; so does this."""
    if stream not in STREAM_SLICES:
        raise RuntimeError(f"{stream!r} is no stream; the streams are {', '.join(STREAMS)}.")
    if base.shape != override.shape:
        raise RuntimeError(
            f"The base stands on {base.shape[1]} positions and {override_name} on "
            f"{override.shape[1]}; the two have to be encoded alike, at the same "
            f"T5 length."
        )
    if base.shape[1] < CLIP_POSITIONS or base.shape[2] < CLIP_WIDTH:
        raise RuntimeError(
            f"A conditioning of {base.shape[1]} positions and width {base.shape[2]} "
            f"holds no SD 3.5 CLIP block of {CLIP_POSITIONS} x {CLIP_WIDTH}."
        )
    tok, dim = STREAM_SLICES[stream]
    out = base.clone()
    out[:, tok, dim] = override[:, tok, dim]
    return out


class Embedder:
    """The model's context embedder on one conditioning, computed once per run
    in the dtype and on the device the block computes in."""

    def __init__(self, model):
        diffusion = getattr(model.model, "diffusion_model", None)
        blocks = getattr(diffusion, "joint_blocks", None)
        embedder = getattr(diffusion, "context_embedder", None)
        if blocks is None or embedder is None:
            raise RuntimeError(
                "This model has no joint blocks with a context embedder. The "
                "SD 3.5 context nodes write into SD 3.5's MMDiT; load the SD 3.5 "
                "checkpoint."
            )
        if getattr(diffusion, "context_processor", None) is not None:
            raise RuntimeError(
                "This model runs its context through a processor before the "
                "embedder; these nodes write in what the embedder alone makes."
            )
        self.embedder = embedder
        self.n_blocks = len(blocks)
        self.cache = {}

    def forget(self):
        self.cache.clear()

    def check_block(self, block):
        if not 0 <= block < self.n_blocks:
            raise RuntimeError(
                f"Block {block} does not exist: this model has {self.n_blocks} "
                f"joint blocks (0 to {self.n_blocks - 1})."
            )

    def __call__(self, key, conditioning, like):
        """embed(conditioning), [1, positions, hidden], as the block computes."""
        held = self.cache.get(key)
        if held is None or held.dtype != like.dtype or held.device != like.device:
            with torch.no_grad():
                held = self.embedder(
                    conditioning.to(device=like.device, dtype=like.dtype)).detach()
            self.cache[key] = held
        return held


def _fits(target, txt, what):
    if tuple(target.shape[1:]) != tuple(txt.shape[1:]):
        raise RuntimeError(
            f"{what} stands on {target.shape[1]} positions at width "
            f"{target.shape[2]}, the block's text on {txt.shape[1]} at "
            f"{txt.shape[2]}; the conditioning written in has to be encoded like "
            f"the one the sampler runs."
        )


def install(patched, block, write, embed=None):
    """A replacement at `block` that gives `write` the block's txt and hands the
    block on: to the replacement that stood at that key before, or to the
    original block. With `embed`, what it holds is dropped after the pass of
    the run's last step: the executor keeps the MODEL this went into, and this
    replacement with it, across runs."""
    before = (patched.model_options.get("transformer_options", {})
              .get("patches_replace", {}).get("dit", {}).get(("double_block", block)))

    def replaced(args, extra):
        options = args["transformer_options"]
        args = {**args, "txt": write(args["txt"], options)}
        if embed is not None:
            step, steps = position(options)
            if step >= steps - 1:
                embed.forget()
        if before is not None:
            return before(args, extra)
        return extra["original_block"](args)

    patched.set_model_patch_replace(replaced, "dit", "double_block", block)


def replacing(embed, positive, negative, lo, hi):
    """txt <- embed(positive) on the positive entries and embed(negative) on the
    negative ones, inside the window. Without a negative the negative entries
    stay as they are."""
    def write(txt, options):
        if not in_window(options, lo, hi):
            return txt
        out = txt.clone()
        for j, side in enumerate(sides_of(txt, options)):
            source = positive if side == 0 else negative
            if source is None:
                continue
            target = embed(side, source, txt)
            _fits(target, txt, "The positive" if side == 0 else "The negative")
            out[j] = target[0]
        return out
    return write


def adding(embed, base, modified, alpha, lo, hi):
    """txt += alpha * (embed(modified) - embed(base)) on the positive entries,
    inside the window: the twin's delta of one Decomposition cell."""
    def write(txt, options):
        if not in_window(options, lo, hi):
            return txt
        delta = (embed("modified", modified, txt) - embed("base", base, txt)) * alpha
        _fits(delta, txt, "The cell's conditioning")
        out = txt.clone()
        for j, side in enumerate(sides_of(txt, options)):
            if side == 0:
                out[j] = txt[j] + delta[0]
        return out
    return write


def probing(embed, modified, stream, lo, hi):
    """One stream's slice of txt <- the same slice of embed(modified) on the
    positive entries, inside the window. The slice is taken of the embedded
    stream, where the twin took it."""
    tok, dim = STREAM_SLICES[stream]

    def write(txt, options):
        if not in_window(options, lo, hi):
            return txt
        target = embed("probe", modified, txt)
        _fits(target, txt, "The probe's conditioning")
        out = txt.clone()
        for j, side in enumerate(sides_of(txt, options)):
            if side == 0:
                out[j][tok, dim] = target[0][tok, dim]
        return out
    return write


class Trajectory:
    """What one run's blocks received, per (block, step, side)."""

    def __init__(self, blocks):
        self.blocks = list(blocks)
        self.frames = {}

    def record(self, block, step, sides, txt):
        for side in sorted(set(sides)):
            rows = [j for j, s in enumerate(sides) if s == side]
            self.frames[(block, step, side)] = txt[rows].detach().cpu()

    def frame(self, block, step, side):
        return self.frames.get((block, step, side))

    def clear(self):
        self.frames.clear()


def recording(trajectory, block):
    """txt kept, txt unchanged."""
    def write(txt, options):
        step, _steps = position(options)
        trajectory.record(block, step, sides_of(txt, options), txt)
        return txt
    return write


def replaying(early, full, kickin_step, block):
    """txt <- the early run's frame before the kick-in step, the full run's from
    it on: `cur_step >= kickin_step`, as the twin switched."""
    def write(txt, options):
        step, _steps = position(options)
        source, name = (full, "full") if step >= kickin_step else (early, "early")
        sides = sides_of(txt, options)
        out = txt.clone()
        for side in sorted(set(sides)):
            frame = source.frame(block, step, side)
            if frame is None:
                raise RuntimeError(
                    f"The {name} run's recording has no frame for block {block}, "
                    f"step {step}, side {side}: the three samplers have to run "
                    f"the same schedule on the same conditionings."
                )
            rows = [j for j, s in enumerate(sides) if s == side]
            if frame.shape[0] != len(rows) or tuple(frame.shape[1:]) != tuple(txt.shape[1:]):
                raise RuntimeError(
                    f"The {name} run's frame for block {block}, step {step} is "
                    f"{tuple(frame.shape)}, the block's text {tuple(txt.shape)}."
                )
            for k, j in enumerate(rows):
                out[j] = frame[k].to(device=txt.device, dtype=txt.dtype)
        return out
    return write


def _window(step_from, step_to):
    lo, hi = float(step_from), float(step_to)
    if not (0.0 <= lo <= WINDOW_MAX and 0.0 <= hi <= WINDOW_MAX):
        raise RuntimeError(
            f"A window is two fractions of the run between 0 and {WINDOW_MAX}, "
            f"not [{lo}, {hi})."
        )
    return lo, hi


def _window_inputs():
    return {
        "step_from": ("FLOAT", {"default": 0.0, "min": 0.0, "max": WINDOW_MAX, "step": 0.01,
                                "tooltip": "From this fraction of the run on (step / steps)."}),
        "step_to": ("FLOAT", {"default": WINDOW_MAX, "min": 0.0, "max": WINDOW_MAX, "step": 0.01,
                              "tooltip": "Up to, and excluding, this fraction of the run."}),
    }


class AI4ArtsEdSD3ContextReplace:
    """The text stream of the named blocks replaced, in a step window."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "positive": ("CONDITIONING", {
                    "tooltip": "What the positive entries receive, embedded."}),
                "blocks": ("STRING", {"default": "0",
                                      "tooltip": "Block indices, \"10\" or \"0,10,23\"."}),
                **_window_inputs(),
            },
            "optional": {
                "negative": ("CONDITIONING", {
                    "tooltip": "What the negative entries receive. Left out, they "
                               "keep what the sampler gave them."}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "AI4ArtsEd/latent lab"

    def patch(self, model, positive, blocks, step_from, step_to, negative=None):
        indices = parse_layers(blocks, "blocks")
        lo, hi = _window(step_from, step_to)
        embed = Embedder(model)
        for block in indices:
            embed.check_block(block)
        pos = cond_tensor(positive, "positive")
        neg = cond_tensor(negative, "negative") if negative is not None else None
        patched = model.clone()
        for block in indices:
            install(patched, block, replacing(embed, pos, neg, lo, hi), embed)
        logger.info("[AI4ArtsEd] SD3 Context Replace: blocks %s, window [%s, %s)", indices, lo, hi)
        return (patched,)


class AI4ArtsEdSD3ContextDelta:
    """One cell of a Decomposition run: alpha times the difference one stream
    makes, added to the text stream at one block in a step window."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "base": ("CONDITIONING", {"tooltip": "The source prompt, all three encoders."}),
                "override": ("CONDITIONING", {"tooltip": "The cell's prompt, all three encoders."}),
                "stream": (STREAMS, {"default": "t5"}),
                "block": ("INT", {"default": 0, "min": 0, "max": 10000,
                                  "tooltip": "The block the band enters at."}),
                **_window_inputs(),
                "alpha": ("FLOAT", {"default": 1.0, "min": -1.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "AI4ArtsEd/latent lab"

    def patch(self, model, base, override, stream, block, step_from, step_to, alpha):
        lo, hi = _window(step_from, step_to)
        embed = Embedder(model)
        embed.check_block(block)
        base_t = cond_tensor(base, "base")
        modified = with_stream(base_t, cond_tensor(override, "override"), stream, "the override")
        patched = model.clone()
        install(patched, block, adding(embed, base_t, modified, float(alpha), lo, hi), embed)
        logger.info("[AI4ArtsEd] SD3 Context Delta: %s at block %s, window [%s, %s), alpha %s",
                    stream, block, lo, hi, float(alpha))
        return (patched,)


class AI4ArtsEdSD3ContextProbe:
    """One stream's slice of the text stream replaced at every block of a range,
    in a step window."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "base": ("CONDITIONING", {"tooltip": "The baseline prompt, all three encoders."}),
                "probe": ("CONDITIONING", {"tooltip": "The probe prompt, all three encoders."}),
                "stream": (STREAMS, {"default": "t5"}),
                "block_from": ("INT", {"default": 0, "min": 0, "max": 10000}),
                "block_to": ("INT", {"default": 1, "min": 1, "max": 10000,
                                     "tooltip": "Excluded: the blocks are block_from up to here."}),
                **_window_inputs(),
            },
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "AI4ArtsEd/latent lab"

    def patch(self, model, base, probe, stream, block_from, block_to, step_from, step_to):
        lo, hi = _window(step_from, step_to)
        block_from, block_to = int(block_from), int(block_to)
        if not block_from < block_to:
            raise RuntimeError(
                f"The block range [{block_from}, {block_to}) names no block.")
        embed = Embedder(model)
        embed.check_block(block_from)
        embed.check_block(block_to - 1)
        modified = with_stream(cond_tensor(base, "base"), cond_tensor(probe, "probe"),
                               stream, "the probe")
        patched = model.clone()
        for block in range(block_from, block_to):
            install(patched, block, probing(embed, modified, stream, lo, hi), embed)
        logger.info("[AI4ArtsEd] SD3 Context Probe: %s at blocks %s..%s, window [%s, %s)",
                    stream, block_from, block_to - 1, lo, hi)
        return (patched,)


class AI4ArtsEdSD3ContextCapture:
    """The text stream of a block range recorded, per step and side, while the
    sampler runs."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "block_from": ("INT", {"default": 0, "min": 0, "max": 10000}),
                "block_to": ("INT", {"default": 1, "min": 1, "max": 10000,
                                     "tooltip": "Excluded: the blocks are block_from up to here."}),
            },
        }

    RETURN_TYPES = ("MODEL", "AI4ARTSED_SD3_CONTEXT_TRAJECTORY")
    RETURN_NAMES = ("model", "trajectory")
    FUNCTION = "patch"
    CATEGORY = "AI4ArtsEd/latent lab"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Never from the cache: the recording is the run's, and a cached model
        # patch would hand a later run the frames of an earlier one.
        return float("nan")

    def patch(self, model, block_from, block_to):
        block_from, block_to = int(block_from), int(block_to)
        if not block_from < block_to:
            raise RuntimeError(
                f"The block range [{block_from}, {block_to}) names no block.")
        embed = Embedder(model)
        embed.check_block(block_from)
        embed.check_block(block_to - 1)
        trajectory = Trajectory(range(block_from, block_to))
        # The executor keeps this object per node id across runs. The frames of
        # its previous run are dropped here as well as at Release: a run whose
        # main sampler raised never reached Release.
        held, self._held = getattr(self, "_held", None), trajectory
        if held is not None:
            held.clear()
        patched = model.clone()
        for block in trajectory.blocks:
            install(patched, block, recording(trajectory, block))
        logger.info("[AI4ArtsEd] SD3 Context Capture: blocks %s..%s", block_from, block_to - 1)
        return (patched, trajectory)


class AI4ArtsEdSD3ContextReplay:
    """The recorded text stream of two runs written back: the early run's before
    the kick-in step, the full run's from it on, at every recorded block."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "early": ("AI4ARTSED_SD3_CONTEXT_TRAJECTORY",),
                "full": ("AI4ARTSED_SD3_CONTEXT_TRAJECTORY",),
                "kickin_step": ("INT", {"default": 0, "min": 0, "max": 10000,
                                        "tooltip": "From this step on the full run's "
                                                   "frames are written; 0 is the full run "
                                                   "throughout."}),
                "samples_early": ("LATENT", {"tooltip": "The early pre-run's output: taken "
                                                        "so that this node runs after it."}),
                "samples_full": ("LATENT", {"tooltip": "The full pre-run's output: taken "
                                                       "so that this node runs after it."}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "AI4ArtsEd/latent lab"

    def patch(self, model, early, full, kickin_step, samples_early, samples_full):
        if early.blocks != full.blocks:
            raise RuntimeError(
                f"The two recordings cover different blocks ({early.blocks[0]}.."
                f"{early.blocks[-1]} and {full.blocks[0]}..{full.blocks[-1]}); "
                f"record both runs over the same range."
            )
        for name, trajectory in (("early", early), ("full", full)):
            if not trajectory.frames:
                raise RuntimeError(
                    f"The {name} run recorded nothing: the MODEL its sampler ran "
                    f"must be the one AI4ArtsEdSD3ContextCapture handed out."
                )
        embed = Embedder(model)
        for block in early.blocks:
            embed.check_block(block)
        patched = model.clone()
        for block in early.blocks:
            install(patched, block, replaying(early, full, int(kickin_step), block))
        logger.info("[AI4ArtsEd] SD3 Context Replay: blocks %s..%s, kick-in at step %s, %d + %d frames",
                    early.blocks[0], early.blocks[-1], int(kickin_step),
                    len(early.frames), len(full.frames))
        return (patched,)


class AI4ArtsEdSD3ContextRelease:
    """The recordings freed once the picture is sampled; the latent goes on."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT", {"tooltip": "The main run's output: passed on, and "
                                                  "taken so that this node runs after it."}),
                "early": ("AI4ARTSED_SD3_CONTEXT_TRAJECTORY",),
            },
            "optional": {
                "full": ("AI4ARTSED_SD3_CONTEXT_TRAJECTORY",),
            },
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "release"
    CATEGORY = "AI4ArtsEd/latent lab"

    def release(self, samples, early, full=None):
        freed = len(early.frames)
        early.clear()
        if full is not None:
            freed += len(full.frames)
            full.clear()
        logger.info("[AI4ArtsEd] SD3 Context Release: %d frames freed", freed)
        return (samples,)


NODE_CLASS_MAPPINGS = {
    "AI4ArtsEdSD3ContextReplace": AI4ArtsEdSD3ContextReplace,
    "AI4ArtsEdSD3ContextDelta": AI4ArtsEdSD3ContextDelta,
    "AI4ArtsEdSD3ContextProbe": AI4ArtsEdSD3ContextProbe,
    "AI4ArtsEdSD3ContextCapture": AI4ArtsEdSD3ContextCapture,
    "AI4ArtsEdSD3ContextReplay": AI4ArtsEdSD3ContextReplay,
    "AI4ArtsEdSD3ContextRelease": AI4ArtsEdSD3ContextRelease,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AI4ArtsEdSD3ContextReplace": "AI4ArtsEd SD3 Context Replace (per block, per step)",
    "AI4ArtsEdSD3ContextDelta": "AI4ArtsEd SD3 Context Delta (one Decomposition cell)",
    "AI4ArtsEdSD3ContextProbe": "AI4ArtsEd SD3 Context Probe (one stream's slice)",
    "AI4ArtsEdSD3ContextCapture": "AI4ArtsEd SD3 Context Capture (record a run)",
    "AI4ArtsEdSD3ContextReplay": "AI4ArtsEd SD3 Context Replay (delayed kick-in)",
    "AI4ArtsEdSD3ContextRelease": "AI4ArtsEd SD3 Context Release (free the recordings)",
}
