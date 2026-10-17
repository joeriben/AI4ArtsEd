"""
AI4ArtsEd — SD 3.5 conditioning, addressed per encoder (ComfyUI custom nodes)

SD 3.5 conditions on three text encoders at once: CLIP-L (768), CLIP-G (1280) and
T5-XXL (4096). ComfyUI hands them out already assembled -- CLIP-L and CLIP-G side by
side, padded to 4096 and laid in front of T5 along the sequence axis, with the two
CLIP pooled vectors concatenated (`comfy/text_encoders/sd3_clip.py`). Three Latent Lab
instruments work on ONE of those encoders and leave the others alone, and none of them
can say which part of the assembled tensor is theirs.

They also need arithmetic ComfyUI's own conditioning nodes do not do: `ConditioningAverage`
clamps its strength to [0, 1] and `ConditioningCombine` concatenates lists rather than
adding vectors, so a difference, a subtraction, or a mix with a factor above one has no
carrier.

These nodes are that carrier, and they are ONE family rather than four separate builds:

    AI4ArtsEdSD3Encode      text  -> the three parts, each at its own width
    AI4ArtsEdSD3Algebra     A - sub*B + add*C on the chosen encoder
    AI4ArtsEdSD3Probe       where two prompts differ, dimension by dimension
    AI4ArtsEdSD3Fusion      T5 added onto the CLIP block, by a factor past one
    AI4ArtsEdSD3ThreeFactors  a on the CLIP block, b of T5 mixed into it, c on the T5 block
    AI4ArtsEdSD3Assemble    the parts -> CONDITIONING, as ComfyUI assembles them

The fourth instrument, the Surrealizer, works on two encoders at once: it lays T5's
reading over the block the two CLIP encoders fill and adds the two, and the factor
that makes its pictures surreal lies past one, where `ConditioningAverage` stops. It
is the same carrier with the same parts, and `AI4ArtsEdSD3Fusion` is its node.

One more node stands here that belongs to no instrument: `AI4ArtsEdSD3TextEncode`
is the platform's plain SD 3.5 encode, ComfyUI's own `CLIPTextEncodeSD3` with the
two CLIP streams held to the single block of 77 positions the model was trained
on. It is here rather than in a file of its own because the cut it makes and the
cut `_encode_parts` makes have to stay the same cut.

The assembly repeats what `SD3ClipModel.encode_token_weights` does, step for step, so a
run that changes nothing comes out where a plain `CLIPTextEncodeSD3` would.
"""

import logging
import math

import torch
import torch.nn.functional as F

from comfy.text_encoders.sd3_clip import SD3ClipModel

logger = logging.getLogger(__name__)


ENCODERS = ["clip_l", "clip_g", "t5", "all"]

# What the SD 3.5 conditioning is assembled from, and what each instrument may
# address. `pooled_l` and `pooled_g` belong to the two CLIP encoders; T5 has no
# pooled vector, which is why an instrument working on T5 leaves the pooled one
# as the base prompt encoded it.
PART_KEYS = ("clip_l", "clip_g", "t5", "pooled_l", "pooled_g")

# The width each encoder writes at, before the assembly pads the two CLIP
# streams out to T5's 4096.
PART_WIDTHS = {"clip_l": 768, "clip_g": 1280, "t5": 4096}

# Which sub-tokenizer writes which part: the key it uses in the token dict, and
# the attribute it stands under on the SD 3.5 tokenizer. The two differ for the
# CLIP encoders.
TOKENIZER_KEY = {
    "clip_l": ("l", "clip_l"),
    "clip_g": ("g", "clip_g"),
    "t5": ("t5xxl", "t5xxl"),
}


def _filled_in_chunk(chunk, pad_token, end_token):
    """How many positions of one tokenizer chunk carry the prompt.

    Padding is right-hand, so what a prompt fills is a prefix. CLIP-L pads with
    its own end token, and there the trailing run swallows the EOS the prompt
    put there; that one position is content and is given back.

    A textual-inversion embedding stands in the token list as a tensor rather
    than an id. It is never padding, so a position that does not compare as an
    integer ends the trailing run.
    """
    n = len(chunk)
    while n > 0:
        token = chunk[n - 1][0]
        if not isinstance(token, int) or token != pad_token:
            break
        n -= 1
    if pad_token == end_token and n < len(chunk):
        n += 1
    return n


def _filled_lengths(clip, tokens):
    """{part: positions the prompt fills} across all chunks of that encoder.

    The text encoders pad to a fixed width - CLIP to 77 per chunk, T5 to what the
    graph asks for, 512 here - so a four-word prompt leaves most positions holding
    the encoder's answer to padding. That answer differs between two prompts for
    reasons that have nothing to do with how the prompts differ, and averaging
    across it ranks dimensions by it. `AI4ArtsEdSD3Probe` measures in this window.
    """
    tokenizer = clip.tokenizer
    filled = {}
    for part, (key, attribute) in TOKENIZER_KEY.items():
        sub = getattr(tokenizer, attribute, None)
        chunks = tokens.get(key) or []
        if sub is None or not chunks:
            filled[part] = 0
            continue
        width = len(chunks[0])
        last = _filled_in_chunk(chunks[-1], sub.pad_token, sub.end_token)
        filled[part] = width * (len(chunks) - 1) + last
    return filled


def _empty_parts():
    """An empty prompt contributes nothing, at every encoder.

    This is the instrument's rule and no longer the platform's: `A - 1*B + 1*C`
    with B left empty is `A + C`, rather than A minus the encoding of the empty
    string, which is a vector like any other. The negative conditioning of every
    graph here goes the other way since 09.09.2026 - `empty_padding="empty_prompt"`
    encodes the empty string through all three encoders - and so does the
    Diffusers twin, which has no such branch and encodes each operand it is given
    (`gpu_service/services/diffusers_backend.py::generate_image_with_algebra`).

    The token streams have length zero; `_fit` fills them out to A's length.
    """
    return {
        "clip_l": torch.zeros((1, 0, PART_WIDTHS["clip_l"])),
        "clip_g": torch.zeros((1, 0, PART_WIDTHS["clip_g"])),
        "t5": torch.zeros((1, 0, PART_WIDTHS["t5"])),
        "pooled_l": torch.zeros((1, PART_WIDTHS["clip_l"])),
        "pooled_g": torch.zeros((1, PART_WIDTHS["clip_g"])),
        "filled": {"clip_l": 0, "clip_g": 0, "t5": 0},
    }


def _encode_parts(clip, text, empty_padding="none"):
    """The three encoders' output for one prompt, each at its own width.

    Loading and options follow `comfy.sd.CLIP.encode_from_tokens`; the difference
    is that the three sub-encoders are read separately instead of assembled.

    `empty_padding` is the switch `AI4ArtsEdSD3TextEncode` has. Under "none" an
    empty prompt contributes nothing (`_empty_parts`). Under "empty_prompt" the
    empty string goes through all three encoders like any text, which is what
    the Surrealizer's negative side is made of when the field is left empty.
    """
    model = clip.cond_stage_model
    if not isinstance(model, SD3ClipModel):
        # Other text encoders carry attributes of the same name and mean
        # something else by them: HiDream has clip_l, clip_g and t5xxl too, reads
        # CLIP-L at another layer and conditions on a fourth stream this assembly
        # would drop. Asking for the family rather than for the attributes.
        raise RuntimeError(
            f"These nodes read SD 3.5's three text encoders, and this CLIP is a "
            f"{type(model).__name__}. Load the SD 3.5 checkpoint or its triple "
            f"text encoder."
        )
    for name in ("clip_l", "clip_g", "t5xxl"):
        if getattr(model, name, None) is None:
            raise RuntimeError(
                f"This CLIP has no {name}. The SD 3.5 conditioning nodes need all "
                f"three encoders; load the SD 3.5 checkpoint or its triple text "
                f"encoder."
            )

    if not text.strip() and empty_padding == "none":
        return _empty_parts()

    tokens = clip.tokenize(text)
    # The same window the platform's own encode holds, so a null run of
    # Concept Algebra and a baseline of Feature Probing are made the way an
    # ordinary SD 3.5 picture is made.
    _within_clip_window(tokens)
    model.reset_clip_options()
    if clip.layer_idx is not None:
        model.set_clip_options({"layer": clip.layer_idx})
    clip.load_model(tokens)
    model.set_clip_options({"execution_device": clip.patcher.load_device})

    l_out, l_pooled = model.clip_l.encode_token_weights(tokens["l"])
    g_out, g_pooled = model.clip_g.encode_token_weights(tokens["g"])
    t5_out = model.t5xxl.encode_token_weights(tokens["t5xxl"])[0]

    return {
        "clip_l": l_out,
        "clip_g": g_out,
        "t5": t5_out,
        "pooled_l": l_pooled,
        "pooled_g": g_pooled,
        "filled": _filled_lengths(clip, tokens),
    }


def _clip_block(parts):
    """The two CLIP streams side by side, at T5's width: the block the sequence opens with.

    `comfy/text_encoders/sd3_clip.py`: cut to the shorter of the two, laid side by
    side, padded out to 4096.
    """
    l_out, g_out = parts["clip_l"], parts["clip_g"]
    cut = min(l_out.shape[1], g_out.shape[1])
    lg = torch.cat([l_out[:, :cut], g_out[:, :cut]], dim=-1)
    return F.pad(lg, (0, PART_WIDTHS["t5"] - lg.shape[-1]))


def _assemble(parts):
    """(cond, pooled) as ComfyUI assembles them for SD 3.5.

    `comfy/text_encoders/sd3_clip.py`: the two CLIP streams are cut to the shorter
    of the two, laid side by side, padded out to 4096 and put in FRONT of T5 along
    the sequence axis; the pooled vector is the two CLIP pooled vectors joined.
    """
    ready = parts.get("assembled")
    if ready is not None:
        # `AI4ArtsEdSD3Probe` measured on the assembled sequence and wrote into
        # it. What it wrote is what goes to the sampler: taking the sequence
        # apart into parts and building it a second time would put a
        # reconstruction between the measurement and the picture.
        return ready, torch.cat([parts["pooled_l"], parts["pooled_g"]], dim=-1)

    lg = _clip_block(parts)
    cond = torch.cat([lg, parts["t5"].to(lg)], dim=-2)
    if cond.shape[-2] == 0:
        # Every part was empty. ComfyUI answers that with 77 zero positions
        # (`SD3ClipModel.encode_token_weights`), and so does this.
        cond = torch.zeros((1, 77, 4096), device=cond.device, dtype=cond.dtype)
    pooled = torch.cat([parts["pooled_l"], parts["pooled_g"]], dim=-1)
    return cond, pooled


def _fit(other, like):
    """`other` laid against `like`: cut where it is longer, zero-filled where shorter.

    Three prompts tokenize to three lengths, and SD 3.5's sequence grows in whole
    chunks. Cutting all three to the shortest would shorten A as well, and A is
    the prompt whose picture this is; a position B does not reach contributes
    nothing there instead, which is what a zero contributes to the arithmetic.
    """
    other = other.to(device=like.device, dtype=like.dtype)
    if other.dim() < 3 or other.shape[-2] == like.shape[-2]:
        return other
    if other.shape[-2] > like.shape[-2]:
        return other[:, :like.shape[-2]]
    return F.pad(other, (0, 0, 0, like.shape[-2] - other.shape[-2]))


def _in_window(delta, ranges):
    """Only the positions the window names. Half-open, several allowed.

    A window that names nothing yields nothing. Falling back to the whole padded
    sequence would answer a measurement over the padding under the name of a
    measurement over the content.
    """
    if not ranges:
        return delta[:, :0, :]
    return torch.cat([delta[:, start:end, :] for start, end in ranges], dim=1)


def _window_one(a, b, part):
    """The longest prefix either prompt fills on one encoder, inside A's block.

    B is laid against A by `_fit` before anything is compared, so whatever B
    fills past A's length is cut and never enters the comparison. Counting it
    would name a window wider than the two prompts were ever compared over.
    """
    block = a[part].shape[-2]
    mine = (a.get("filled") or {}).get(part, 0)
    theirs = min((b.get("filled") or {}).get(part, 0), block)
    return min(max(mine, theirs), block)


def _window_all(a, b):
    """Two windows, because the assembled sequence holds two blocks.

    CLIP-L and CLIP-G stand side by side over the first block and T5 follows, so
    the CLIP padding sits in the middle of the sequence rather than at its end.
    """
    # The same cut `_assemble` makes. Taking the block length from CLIP-L alone
    # would name a T5 offset the assembled sequence does not have as soon as the
    # two CLIP streams come out at different lengths.
    clip_len = min(a["clip_l"].shape[-2], a["clip_g"].shape[-2])
    clip_filled = max(_window_one(a, b, "clip_l"), _window_one(a, b, "clip_g"))
    t5_filled = _window_one(a, b, "t5")
    return [(0, min(clip_filled, clip_len)), (clip_len, clip_len + t5_filled)]


def _dimensions_named(written, width, encoder):
    """The dimensions a run names, as indices into `encoder`.

    A selection made against one encoder and sent to another is a stale form,
    and the Diffusers instrument answered it by failing on the index. Dropping
    it instead would return prompt A's own picture under the caption of a
    transfer.
    """
    dims = []
    for piece in str(written or "").replace(";", ",").split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            index = int(piece)
        except ValueError:
            raise RuntimeError(
                f"{piece!r} is not a dimension. The selection reads: {written!r}"
            )
        if not 0 <= index < width:
            raise RuntimeError(
                f"Dimension {index} does not exist on {encoder}, which has "
                f"{width}. The selection was made against another encoder; "
                f"measure again before carrying dimensions across."
            )
        if index not in dims:
            dims.append(index)
    return dims


class AI4ArtsEdSD3Encode:
    """One prompt, encoded by all three of SD 3.5's text encoders, kept apart."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "text": ("STRING", {"multiline": True, "dynamicPrompts": True}),
            },
            "optional": {
                # As on AI4ArtsEdSD3TextEncode; see _encode_parts.
                "empty_padding": (["none", "empty_prompt"], {"default": "none"}),
            },
        }

    RETURN_TYPES = ("AI4ARTSED_SD3_PARTS",)
    RETURN_NAMES = ("parts",)
    FUNCTION = "encode"
    CATEGORY = "AI4ArtsEd/latent lab"

    def encode(self, clip, text, empty_padding="none"):
        return (_encode_parts(clip, text, empty_padding),)


class AI4ArtsEdSD3Algebra:
    """``A - scale_sub * B + scale_add * C`` on one encoder, unclamped.

    The encoders that are not chosen stay as A encoded them, so the picture keeps
    everything about the base prompt that the arithmetic did not touch. On CLIP-L
    and CLIP-G the same formula is applied to the pooled vector; T5 has none.

    Nothing is renormalized and nothing is clamped: a factor above one is the
    point of the instrument, and a result that leaves the manifold is a result of
    the instrument and not an error to be smoothed away.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "a": ("AI4ARTSED_SD3_PARTS",),
                "b": ("AI4ARTSED_SD3_PARTS",),
                "c": ("AI4ARTSED_SD3_PARTS",),
                "encoder": (ENCODERS, {"default": "all"}),
                "scale_sub": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0,
                                        "step": 0.05}),
                "scale_add": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0,
                                        "step": 0.05}),
            },
        }

    RETURN_TYPES = ("AI4ARTSED_SD3_PARTS", "FLOAT")
    RETURN_NAMES = ("parts", "l2_from_a")
    FUNCTION = "combine"
    CATEGORY = "AI4ArtsEd/latent lab"
    # The distance the arithmetic moved the conditioning is what the instrument
    # reports next to the pair of pictures. A node output alone never leaves
    # ComfyUI, so it is announced as well and travels in the run's outputs.
    OUTPUT_NODE = True

    def combine(self, a, b, c, encoder, scale_sub, scale_add):
        touched = (["clip_l", "clip_g", "t5"] if encoder == "all" else [encoder])
        if encoder in ("clip_l", "all"):
            touched_pooled = ["pooled_l"]
        else:
            touched_pooled = []
        if encoder in ("clip_g", "all"):
            touched_pooled.append("pooled_g")

        out = dict(a)
        out["filled"] = dict(a.get("filled") or {})
        # An assembled sequence upstream belongs to the node that wrote it. Left
        # standing, `_assemble` would return that one and throw this arithmetic
        # away without a word.
        out.pop("assembled", None)
        for key in touched + touched_pooled:
            x = a[key]
            y, z = _fit(b[key], x), _fit(c[key], x)
            out[key] = x - scale_sub * y + scale_add * z

        # The distance is measured where the Diffusers instrument measured it:
        # over the assembled TOKEN stream, with the pooled vector left out
        # (gpu_service/services/embedding_analyzer.py). Measuring the parts
        # instead would fold the pooled deltas into a number carrying the same
        # name, and the two would not be comparable.
        l2 = float((_assemble(out)[0] - _assemble(a)[0]).norm(p=2))
        return {
            "ui": {"ai4artsed_algebra": [{"l2_from_a": l2, "encoder": encoder}]},
            "result": (out, l2),
        }


class AI4ArtsEdSD3Probe:
    """Where two prompts differ, dimension by dimension, and what a selection does.

    Two passes over one prompt pair. The first measures: for every dimension of
    the chosen encoder, how far apart A and B stand on average, over the
    positions the prompts actually fill. The second carries a named selection of
    those dimensions from B into A and samples again, at the same seed, so the
    two pictures differ by the selection and by nothing else.

    `transfer` says which pass this is, rather than the selection being empty or
    not: a second pass that names no dimension is a run that moved nothing, and
    it reports that as zeros. A first pass reports no transfer statistics at all.

    The measurement and the writing use the same window. Ranking dimensions over
    the padding and then writing into it too would move positions no measurement
    looked at, and the picture would change for something this instrument cannot
    show.

    The window follows the tokenization the graph sets up: CLIP grows in chunks of
    77, T5 stands at 512, which is the length the Diffusers instrument has always
    used. Both measure the same positions from 09.09.2026 on, with two exceptions:
    above 75 CLIP tokens ComfyUI opens a second chunk where Diffusers cuts, and
    above 511 T5 tokens ComfyUI lets the stream grow where Diffusers cuts.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "a": ("AI4ARTSED_SD3_PARTS",),
                "b": ("AI4ARTSED_SD3_PARTS",),
                "encoder": (ENCODERS, {"default": "all"}),
                "transfer_dims": ("STRING", {"default": "", "multiline": False}),
                "transfer": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("AI4ARTSED_SD3_PARTS",)
    RETURN_NAMES = ("parts",)
    FUNCTION = "probe"
    CATEGORY = "AI4ArtsEd/latent lab"
    # The measurement is what the surface plots, and a node output alone never
    # leaves ComfyUI.
    OUTPUT_NODE = True

    def probe(self, a, b, encoder, transfer_dims, transfer=False):
        fitted = {key: _fit(b[key], a[key]) for key in ("clip_l", "clip_g", "t5")}
        fitted["pooled_l"], fitted["pooled_g"] = b["pooled_l"], b["pooled_g"]

        if encoder == "all":
            embed_a, _ = _assemble(a)
            embed_b, _ = _assemble(fitted)
            ranges = _window_all(a, b)
        else:
            embed_a, embed_b = a[encoder], fitted[encoder]
            ranges = [(0, _window_one(a, b, encoder))]

        ranges = [(start, min(end, embed_a.shape[-2])) for start, end in ranges]
        ranges = [(start, end) for start, end in ranges if end > start]

        delta = _in_window(embed_b - embed_a, ranges)
        if delta.shape[1] == 0:
            # Both prompts were empty. Nothing was measured, and the numbers say so.
            per_dim = torch.zeros(embed_a.shape[-1], device=embed_a.device)
        else:
            per_dim = delta.abs().mean(dim=1).squeeze(0)
        order = torch.topk(per_dim, k=per_dim.shape[0])
        said = {
            "encoder": encoder,
            "diff_per_dim": per_dim.cpu().tolist(),
            "top_dims": order.indices.cpu().tolist(),
            "top_values": order.values.cpu().tolist(),
            "embed_dim": int(per_dim.shape[0]),
            "total_l2": float(delta.norm(p=2)),
            "nonzero_dims": int((per_dim > 1e-6).sum()),
            "content_positions": int(delta.shape[1]),
            "content_ranges": [[start, end] for start, end in ranges],
        }

        if not transfer:
            return {"ui": {"ai4artsed_probe": [said]}, "result": (dict(a),)}

        dims = _dimensions_named(transfer_dims, int(per_dim.shape[0]), encoder)
        result = embed_a.clone()
        if dims and ranges:
            for start, end in ranges:
                result[:, start:end, dims] = embed_b[:, start:end, dims]

        change = float((result - embed_a).norm(p=2))
        total = said["total_l2"]
        # What was carried across, rather than what was asked for: with no window
        # there is nowhere to write, and reporting the request would assert a
        # transfer that did not happen.
        said["transferred_dims"] = dims if ranges else []
        said["num_transferred"] = len(dims) if ranges else 0
        said["change_l2"] = change
        said["total_diff_l2"] = total
        said["captured_pct"] = (change / total * 100) if total > 0 else 0.0

        out = dict(a)
        out["filled"] = dict(a.get("filled") or {})
        if encoder == "all":
            out["assembled"] = result
        else:
            out[encoder] = result
        return {"ui": {"ai4artsed_probe": [said]}, "result": (out,)}


# The Surrealizer's ways of mixing the two readings, by the names the surfaces
# and the stored runs carry (lib/fusionWeights.ts), and `slerp`, which the
# Fusion Workbench puts on its strategy axis. The Diffusers twin,
# gpu_service/services/diffusers_backend.py::generate_image_with_fusion, is the
# arithmetic these repeat; its research options after '#' stay there.
FUSIONS = ["centered_fade", "legacy", "dual_alpha", "normalized", "original", "slerp"]

# The positions the two readings share: the CLIP block SD 3.5 was trained on,
# and what the Diffusers twin fused (`interp_len = min(77, ...)`).
CORE_POSITIONS = 77

# centered_fade's normal band, as a half-width: its anchors sit at +/- this.
CENTERED_BAND_H = 1.0

# dual_alpha's factor on the T5 tail, against the full alpha on the core.
DUAL_ALPHA_TAIL = 0.15


def slerp_tokens(a, b, alpha):
    """Interpolate two token tensors on the sphere: the direction turns, the
    length runs linearly. The twin's `slerp_tokens`, kept as it is.

    At a given alpha the direction is the one reached by turning alpha * theta
    away from `a` in the plane the two directions span, and it carries a length
    that runs linearly from the length of `a` to the length of `b`. At alpha 0
    the result is `a`, at alpha 1 it is `b`. Past the anchors the direction
    keeps turning at alpha * theta and comes round again; the length term
    crosses zero at alpha = |a| / (|a| - |b|). Where the two directions coincide
    or oppose each other the plane is undefined, and the straight line between
    the two unit vectors is taken instead (below sin theta = 1e-6). theta is
    acos(dot), the angle the two readings stand at, so both anchors stay exact.
    Direction and length are computed in float32 and cast back to a's dtype.
    """
    a32 = a.float()
    b32 = b.float()
    a_dir = torch.nn.functional.normalize(a32, dim=-1)
    b_dir = torch.nn.functional.normalize(b32, dim=-1)
    dot = torch.clamp((a_dir * b_dir).sum(dim=-1, keepdim=True), -1.0, 1.0)
    theta = torch.acos(dot)
    sin_theta = torch.sin(theta)
    turned = torch.where(
        sin_theta < 1e-6,
        (1.0 - alpha) * a_dir + alpha * b_dir,
        (torch.sin((1.0 - alpha) * theta) * a_dir + torch.sin(alpha * theta) * b_dir)
        / sin_theta.clamp(min=1e-6),
    )
    length = ((1.0 - alpha) * a32.norm(dim=-1, keepdim=True)
              + alpha * b32.norm(dim=-1, keepdim=True))
    return (turned * length).to(a.dtype)


def _fusion_weights(strategy, alpha):
    """(w_clip, w_t5) on the core positions, unclamped.

    centered_fade: a band of half-width CENTERED_BAND_H with a ramp and no dead
    zone. t = alpha / h. t <= 0: w_clip = max(1, -t), w_t5 = 1 + t; t > 0:
    w_clip = 1 - t, w_t5 = max(1, t). alpha = -h is CLIP alone, 0 is both
    readings at 1, +h is T5 alone; past the band one weight keeps growing and
    the other inverts, and from +h on that is the LERP below.

    original: the same band on its own anchors, 0 = CLIP-L alone and 1 = T5
    alone, so t = 2 * alpha - 1 runs across it; outside it the LERP.

    legacy, dual_alpha, normalized: the LERP (1 - alpha, alpha).
    """
    if strategy == "centered_fade":
        t = alpha / CENTERED_BAND_H
        if t <= 0.0:
            return max(1.0, -t), 1.0 + t
        return 1.0 - t, max(1.0, t)
    if strategy == "original":
        t = 2.0 * alpha - 1.0
        if -1.0 <= t <= 1.0:
            return (1.0, 1.0 + t) if t <= 0.0 else (1.0 - t, 1.0)
    return 1.0 - alpha, alpha


class AI4ArtsEdSD3Fusion:
    """T5's reading laid over the CLIP block and added to it, by a factor past one.

    SD 3.5 puts the 77 positions the two CLIP encoders fill in front of T5's.
    The Surrealizer adds the two over those 77 positions instead,
    w_clip * CLIP + w_t5 * T5, and lets T5's remainder follow as the tail. The
    weights per strategy are in `_fusion_weights`; under slerp the core is
    `slerp_tokens` of the two readings at alpha instead of a weighted sum. The
    tail is T5's own under centered_fade, legacy, original and slerp;
    DUAL_ALPHA_TAIL * alpha times T5's under dual_alpha; under normalized each
    of its positions is scaled to the core's mean length. Nothing is clamped:
    the factor that makes the picture surreal lies past one.

    The CLIP side and the T5 side may be two prompts (the adapted prompts of the
    2025 workflow) or the same parts twice. The pooled vector is the CLIP side's
    and is never weighted: T5 has none.

    `original` is the 2025 workflow: CLIP-L alone, so CLIP-G's dimensions and its
    pooled half are zero, and T5 at the length of its own text, which the graph
    arranges by leaving the T5 length option out. The result is an assembled
    sequence, handed on the way `AI4ArtsEdSD3Probe` hands one on, and
    `AI4ArtsEdSD3Assemble` passes it to the sampler as it is.

    Two things the twin does differently, on record. It fuses four of the five
    strategies in fp16, its pipeline's dtype, and its longest core token (some
    1200) reaches fp16's 65504 beyond about alpha 55 under legacy, the ceiling
    the surfaces call the fp16 cliff; here every strategy is computed in
    float32, as `original` was there, and the ceiling is gone. And under
    `original` the twin pads T5 on both sides to one shared length, the longer
    of the two texts, a constraint of its pipeline; here each side runs at the
    length of its own text, as the 2025 workflow did.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip_side": ("AI4ARTSED_SD3_PARTS", {
                    "tooltip": "The prompt the two CLIP encoders read; its pooled "
                               "vector goes on."}),
                "t5_side": ("AI4ARTSED_SD3_PARTS", {
                    "tooltip": "The prompt T5 reads. The same parts again for one "
                               "prompt."}),
                "alpha": ("FLOAT", {"default": 0.0, "min": -75.0, "max": 75.0,
                                    "step": 0.05}),
                "strategy": (FUSIONS, {"default": "centered_fade"}),
            },
        }

    RETURN_TYPES = ("AI4ARTSED_SD3_PARTS",)
    RETURN_NAMES = ("parts",)
    FUNCTION = "fuse"
    CATEGORY = "AI4ArtsEd/latent lab"

    def fuse(self, clip_side, t5_side, alpha, strategy):
        if strategy not in FUSIONS:
            raise RuntimeError(
                f"{strategy!r} is no fusion of this node, which runs "
                f"{', '.join(FUSIONS)}."
            )
        alpha = float(alpha)
        out = dict(clip_side)
        out["filled"] = dict(clip_side.get("filled") or {})
        # An assembled sequence upstream belongs to the node that wrote it; the
        # fusion writes its own below.
        out.pop("assembled", None)
        if strategy == "original":
            out["clip_g"] = torch.zeros_like(clip_side["clip_g"])
            out["pooled_g"] = torch.zeros_like(clip_side["pooled_g"])

        clip_block = _clip_block(out).float()
        t5 = t5_side["t5"].to(device=clip_block.device, dtype=clip_block.dtype)
        if clip_block.shape[1] == 0 or t5.shape[1] == 0:
            raise RuntimeError(
                "The fusion needs both readings, and an empty side has no "
                "positions. Encode it with empty_padding=empty_prompt."
            )
        if t5.shape[1] < CORE_POSITIONS:
            # The twin's T5 was never shorter than the block (max(77, len) or
            # 512); a shorter one here would cut the core quietly.
            raise RuntimeError(
                f"T5 stands on {t5.shape[1]} positions and the core takes "
                f"{CORE_POSITIONS}: the T5 length option has to be at least "
                f"{CORE_POSITIONS}."
            )
        # The twin's `interp_len = min(77, clip_len)`.
        core = min(CORE_POSITIONS, clip_block.shape[1])
        if strategy == "slerp":
            fused_core = slerp_tokens(clip_block[:, :core], t5[:, :core], alpha)
            w_clip, w_t5 = float("nan"), float("nan")
        else:
            w_clip, w_t5 = _fusion_weights(strategy, alpha)
            fused_core = w_clip * clip_block[:, :core] + w_t5 * t5[:, :core]
        tail = t5[:, core:]
        if strategy == "dual_alpha":
            tail = DUAL_ALPHA_TAIL * alpha * tail
        elif strategy == "normalized":
            core_mag = fused_core.norm(dim=-1).mean()
            tail = tail * (core_mag / tail.norm(dim=-1, keepdim=True).clamp(min=1e-8))
        out["assembled"] = torch.cat([fused_core, tail], dim=1)
        logger.info(
            "[AI4ArtsEd SD3 Fusion] strategy=%s alpha=%.3f w_clip=%.3f w_t5=%.3f "
            "core %dt, tail %dt", strategy, alpha, w_clip, w_t5, core, tail.shape[1],
        )
        return (out,)


# The T5 block under the CLIP block, as `AI4ArtsEdSD3ThreeFactors` lays it:
# complete (rows 0..511, the sequence ComfyUI assembles itself) or as the tail
# (rows 77..511, the layout the Surrealizer of 2025 ran).
T5_ROWS = ["full", "tail"]

# The pooled vector the node hands on: CLIP's own (CLIP-L's 768 and CLIP-G's
# 1280 numbers, the modulation of every block), or zeros, which is what
# ComfyUI itself puts there when the CLIP encoders are absent
# (comfy/text_encoders/sd3_clip.py).
POOLED = ["clip", "zero"]


class AI4ArtsEdSD3ThreeFactors:
    """The conditioning table under three factors: a on the CLIP block, b for
    T5's rows 0..76 mixed into it cell by cell, c on the T5 block.

    SD 3.5's sequence is a table of 589 rows and 4096 columns: the 77 rows the
    two CLIP encoders fill (columns 2048..4095 zero) and, under them, the 512
    rows of T5. This node writes

        rows 0..76      a * CLIP + b * T5[0..76]
        rows 77..588    c * T5[0..511]            (t5_rows = "full")

    or, with t5_rows = "tail", T5's rows 77.. alone under the block, 512 rows
    in all:

        rows 0..76      a * CLIP + b * T5[0..76]
        rows 77..511    c * T5[77..511]

    b pairs the rows by number: T5's row i goes onto CLIP's row i, whatever
    piece of the text stands in either. Nothing is clamped and nothing is
    coupled. (1, 0, 1, full, clip) is the sequence and the vector ComfyUI
    assembles on its own;
    (1 - alpha, alpha, 1, tail, clip) is `AI4ArtsEdSD3Fusion` under legacy at
    alpha, bit for bit, on the CLIP block of 77 rows the encode node holds
    (`_within_clip_window`; a longer block stays whole here and is cut to 77
    there); (1, 0, 0, full, clip)
    puts zeros in the T5 block's place, the ablation of Esser et al. 2024,
    5.3.3. The research twin is `three_factor` in
    gpu_service/services/diffusers_backend.py. The arithmetic is float32, as in
    the fusion node.

    The pooled vector is CLIP's and takes no factor; `pooled` hands it on as
    CLIP computes it ("clip") or as zeros of the same shape ("zero"), which is
    what ComfyUI itself hands the model when no CLIP encoder runs. T5 has no
    pooled vector.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "parts": ("AI4ARTSED_SD3_PARTS", {
                    "tooltip": "The prompt, read by the three encoders; its pooled "
                               "vector goes on as `pooled` has it: as computed, or "
                               "zeros."}),
                "a": ("FLOAT", {"default": 1.0, "min": -75.0, "max": 75.0, "step": 0.05,
                                "tooltip": "Factor on the CLIP block, rows 0..76."}),
                "b": ("FLOAT", {"default": 0.0, "min": -75.0, "max": 75.0, "step": 0.05,
                                "tooltip": "Factor on T5's rows 0..76, added cell by "
                                           "cell into the CLIP block. 0 leaves the "
                                           "block CLIP's own."}),
                "c": ("FLOAT", {"default": 1.0, "min": -75.0, "max": 75.0, "step": 0.05,
                                "tooltip": "Factor on the T5 block under the CLIP "
                                           "block. 0 puts zeros in its place."}),
                "t5_rows": (T5_ROWS, {
                    "default": "full",
                    "tooltip": "full: T5's rows 0..511 under the CLIP block, 589 "
                               "rows. tail: rows 77..511 alone, 512 rows."}),
                "pooled": (POOLED, {
                    "default": "clip",
                    "tooltip": "clip: the pooled vector as CLIP-L and CLIP-G "
                               "compute it. zero: zeros in its place, as ComfyUI "
                               "itself puts them when no CLIP encoder runs."}),
            },
        }

    RETURN_TYPES = ("AI4ARTSED_SD3_PARTS",)
    RETURN_NAMES = ("parts",)
    FUNCTION = "weigh"
    CATEGORY = "AI4ArtsEd/latent lab"

    def weigh(self, parts, a, b, c, t5_rows, pooled="clip"):
        if t5_rows not in T5_ROWS:
            raise RuntimeError(f"t5_rows {t5_rows!r}: one of {', '.join(T5_ROWS)}.")
        if pooled not in POOLED:
            raise RuntimeError(f"pooled {pooled!r}: one of {', '.join(POOLED)}.")
        a, b, c = float(a), float(b), float(c)
        if not all(math.isfinite(v) for v in (a, b, c)):
            raise RuntimeError("The three factors have to be finite numbers.")
        out = dict(parts)
        out["filled"] = dict(parts.get("filled") or {})
        # An assembled sequence upstream belongs to the node that wrote it.
        out.pop("assembled", None)
        if pooled == "zero":
            out["pooled_l"] = torch.zeros_like(parts["pooled_l"])
            out["pooled_g"] = torch.zeros_like(parts["pooled_g"])

        clip_block = _clip_block(parts).float()
        t5 = parts["t5"].to(device=clip_block.device, dtype=clip_block.dtype)
        if clip_block.shape[1] == 0 or t5.shape[1] == 0:
            raise RuntimeError(
                "The three factors need both readings, and an empty side has no "
                "rows. Encode it with empty_padding=empty_prompt."
            )
        if t5.shape[1] < CORE_POSITIONS:
            raise RuntimeError(
                f"T5 stands on {t5.shape[1]} rows and the CLIP block on "
                f"{CORE_POSITIONS}: the T5 length option has to be at least "
                f"{CORE_POSITIONS}."
            )
        core = min(CORE_POSITIONS, clip_block.shape[1])
        # a on the whole block; b on the rows T5 has a partner for. The same
        # two products in the same order as the fusion node's core, so that
        # (1 - alpha, alpha, 1, tail, clip) is legacy at alpha to the bit.
        block = a * clip_block
        block[:, :core] = block[:, :core] + b * t5[:, :core]
        below = t5 if t5_rows == "full" else t5[:, core:]
        out["assembled"] = torch.cat([block, c * below], dim=1)
        logger.info(
            "[AI4ArtsEd SD3 ThreeFactors] a=%.3f b=%.3f c=%.3f t5_rows=%s pooled=%s "
            "block %dt, T5 %dt", a, b, c, t5_rows, pooled, block.shape[1], below.shape[1],
        )
        return (out,)


class AI4ArtsEdSD3Assemble:
    """The three parts, put together the way ComfyUI puts them together."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"parts": ("AI4ARTSED_SD3_PARTS",)}}

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "assemble"
    CATEGORY = "AI4ArtsEd/latent lab"

    def assemble(self, parts):
        cond, pooled = _assemble(parts)
        return ([[cond, {"pooled_output": pooled}]],)


# What SD 3.5 was trained on at its two CLIP encoders: ONE block of 77
# positions. ComfyUI's SDTokenizer emits ceil(n/75) blocks for a longer prompt
# and SD3ClipModel lays them end to end, so a 330-token prompt reaches the
# transformer on five CLIP blocks. The Diffusers backend cut at 77
# (`padding="max_length", max_length=77, truncation=True`), so every SD 3.5
# picture this platform showed before the move to ComfyUI had CLIP anchored on
# the first block and its detail carried by T5. That is also what
# `schemas/configs/output/sd35_large.json` prescribes in its own notes: "the
# CLIP encoders anchor the global gist, T5 carries the full-length detail
# beyond CLIP's 77-token window".
#
# Measured on the eight interception texts of a real course, one seed, the same
# T5 text on both sides: the extra blocks cost contrast in seven of eight
# pictures and colour in eight of eight, and past about seven blocks the picture
# collapses into a symmetric burst of light on grey.
CLIP_BLOCKS = 1


def _within_clip_window(tokens):
    """Hold the two CLIP streams to the blocks SD 3.5 was trained on.

    On the token lists and inside ComfyUI, rather than on the text and outside
    it. A cut made on the text has to decode and re-encode, which lowercases the
    prompt and puts spaces around its punctuation; a count made in another
    process has to guess what THIS tokenizer counts, and gets it wrong for
    typographic quotes, ligatures, fullwidth letters and mojibake, always
    downwards. Here the list that will be encoded is the list that is cut.

    T5 keeps every block it has: it is the encoder that carries the detail.
    """
    for stream in ("l", "g"):
        if tokens.get(stream):
            tokens[stream] = tokens[stream][:CLIP_BLOCKS]
    return tokens


class AI4ArtsEdSD3TextEncode:
    """`CLIPTextEncodeSD3`, with the CLIP streams held to their window.

    Step for step ComfyUI's own node (`comfy_extras/nodes_sd3.py`), down to
    `encode_from_tokens_scheduled`, so text-encoder hooks and LoRA schedules go
    on working. The one difference is `_within_clip_window`, applied before the
    two CLIP streams are matched in length.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "clip_l": ("STRING", {"multiline": True, "dynamicPrompts": True}),
                "clip_g": ("STRING", {"multiline": True, "dynamicPrompts": True}),
                "t5xxl": ("STRING", {"multiline": True, "dynamicPrompts": True}),
                "empty_padding": (["none", "empty_prompt"],),
            }
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "encode"
    CATEGORY = "AI4ArtsEd/conditioning"

    def encode(self, clip, clip_l, clip_g, t5xxl, empty_padding):
        no_padding = empty_padding == "none"

        tokens = clip.tokenize(clip_g)
        if len(clip_g) == 0 and no_padding:
            tokens["g"] = []

        if len(clip_l) == 0 and no_padding:
            tokens["l"] = []
        else:
            tokens["l"] = clip.tokenize(clip_l)["l"]

        if len(t5xxl) == 0 and no_padding:
            tokens["t5xxl"] = []
        else:
            tokens["t5xxl"] = clip.tokenize(t5xxl)["t5xxl"]

        _within_clip_window(tokens)

        if len(tokens["l"]) != len(tokens["g"]):
            empty = clip.tokenize("")
            while len(tokens["l"]) < len(tokens["g"]):
                tokens["l"] += empty["l"]
            while len(tokens["l"]) > len(tokens["g"]):
                tokens["g"] += empty["g"]
        return (clip.encode_from_tokens_scheduled(tokens),)

NODE_CLASS_MAPPINGS = {
    "AI4ArtsEdSD3Encode": AI4ArtsEdSD3Encode,
    "AI4ArtsEdSD3Algebra": AI4ArtsEdSD3Algebra,
    "AI4ArtsEdSD3Probe": AI4ArtsEdSD3Probe,
    "AI4ArtsEdSD3Fusion": AI4ArtsEdSD3Fusion,
    "AI4ArtsEdSD3ThreeFactors": AI4ArtsEdSD3ThreeFactors,
    "AI4ArtsEdSD3Assemble": AI4ArtsEdSD3Assemble,
    "AI4ArtsEdSD3TextEncode": AI4ArtsEdSD3TextEncode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AI4ArtsEdSD3Encode": "AI4ArtsEd SD3 Encode (per encoder)",
    "AI4ArtsEdSD3Algebra": "AI4ArtsEd SD3 Algebra",
    "AI4ArtsEdSD3Probe": "AI4ArtsEd SD3 Probe (dimension differences)",
    "AI4ArtsEdSD3Fusion": "AI4ArtsEd SD3 Fusion (T5 onto the CLIP block)",
    "AI4ArtsEdSD3ThreeFactors": "AI4ArtsEd SD3 Three Factors (a, b, c on the table)",
    "AI4ArtsEdSD3Assemble": "AI4ArtsEd SD3 Assemble",
    "AI4ArtsEdSD3TextEncode": "AI4ArtsEd SD3 Text Encode (CLIP window)",
}
