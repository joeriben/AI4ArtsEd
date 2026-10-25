"""
AI4ArtsEd Attention Cartography for ComfyUI: the attention SD 3.5's joint blocks
put on the words, read out while the picture is made.

Stage 4 of the move to ComfyUI. What
gpu_service/services/attention_processors_sd3.py did on the Diffusers
pipeline, on the chosen joint blocks at the chosen steps: the attention is
computed a second time by hand, softmax(QK^T / sqrt(d)), and the weight every
image position puts on every text position is kept, averaged over the batch
and the heads, cut to the text columns that carry a word, and quantized to
ten-thousandths. The picture itself is made with ComfyUI's own attention; the
readout stands beside it and changes nothing in it.

Two nodes. AI4ArtsEdAttentionCapture patches a MODEL: for each chosen block it
registers a block replacement (`patches_replace["dit"][("double_block", i)]`,
read in mmdit.py forward_core_with_concat), and the replacement runs the
original block with `optimized_attention_override` set for that block alone
(attention.py wrap_attn hands the override the function it would have called,
with the block's q, k, v). The override is where the readout happens.
AI4ArtsEdAttentionMaps takes the readout and the sampled LATENT - the latent
for the order alone, it has to run after the sampler - and writes the maps and
the tokens to a JSON file in the output directory, announced under a key of
its own, the way AI4ArtsEdKeepLatent announces a latent.

Where the two ways differ, and how it is bridged:

  * The order of the joint sequence. ComfyUI's block puts the text in FRONT
    of the image positions (_block_mixing: cat((context, x))); the Diffusers
    processor put the image first. The readout takes the text keys at 0:n_txt
    and the image queries from n_txt on, and stores [image, text] as before.
  * The batch. Diffusers ran negative and positive as one batch of two and
    averaged over both; ComfyUI batches them when it can and otherwise runs
    them one after the other at the same sigma. The readout sums per (step,
    block) and counts the batch entries and heads it summed, and the map is
    that sum over that count - the same mean either way.
  * The accumulation is float32. The Diffusers processor took its mean in the
    model's half precision; the map is the same map, quantized from a sum that
    carried its digits.
  * The tokens come from the CLIP object the graph encodes with, so the columns
    are the columns of the conditioning that was actually sampled: the CLIP
    block is chunk 0 of the tokenizer's output, T5 stands at the length the
    T5TokenizerOptions node gave it.

The readout is per run. The capture node is never served from the cache
(IS_CHANGED), so a second run with the same settings captures again instead of
adding to what the first one saw, and the sampler after it runs again too.
"""

import json
import logging
import math
import os

import torch

import folder_paths

logger = logging.getLogger(__name__)

# The Diffusers processor's scale: (map * 10000).round(), int32.
QUANT = 10000

# The T5 positions the map reads: the Diffusers instrument cut T5 at 512
# (max_sequence_length), ComfyUI lets it grow with the text. A prompt past
# this is refused rather than cut without a word, and a cond that outgrew the
# empty negative would otherwise be batched against it repeated, or on a
# separate call, whose text sequence the columns do not fit. The platform's
# T5 length option is the same number (schemas/engine/comfyui_chunk_support.py,
# T5_LENGTH); a test holds the two together.
T5_WINDOW = 512

# Heads read out at once. Scores for one head at 1024 x 1024 are
# 4096 x (589 + 4096) values; eight of them in half precision are ~300 MB.
HEADS_AT_ONCE = 8

# SD 3's patch: two latent pixels per image position, each way.
PATCH = 2


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


def capture_steps(steps, every_n):
    """The steps read out: every n-th from the first, and the last one always
    (gpu_service/services/diffusers_backend.py, generate_image_with_attention)."""
    steps, every_n = int(steps), int(every_n)
    if steps < 1:
        raise ValueError(f"steps must be at least 1, got {steps}")
    if every_n < 1:
        raise ValueError(f"capture_every_n_steps must be at least 1, got {every_n}")
    picked = list(range(0, steps, every_n))
    if steps - 1 not in picked:
        picked.append(steps - 1)
    return picked


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


def word_columns(clip, text):
    """The tokens the two tokenizers make of the text, grouped into words, and
    the columns of the joint text sequence that carry them.

    The Diffusers backend's reading, on ComfyUI's tokenizers: CLIP-L's BPE marks
    a word-final subtoken with "</w>", T5's SentencePiece a word-initial one with
    U+2581. CLIP-L's columns are its positions in chunk 0 (the block the
    platform encodes, BOS at 0), T5's are 77 + position. Special tokens (start,
    end, pad) carry no word and get no column.

    Returns (tokens, word_groups, tokens_t5, word_groups_t5, columns).
    """
    by_encoder = clip.tokenize(text)
    tok = clip.tokenizer

    tokens, groups, columns = [], [], []
    l_chunks = by_encoder.get("l") or []
    if l_chunks:
        hf = tok.clip_l.tokenizer
        special = {tok.clip_l.start_token, tok.clip_l.end_token, tok.clip_l.pad_token}
        current, prev_raw = [], None
        for pos, entry in enumerate(l_chunks[0]):
            tid = entry[0]
            if not isinstance(tid, int) or tid in special:
                continue
            raw = hf.convert_ids_to_tokens(tid)
            index = len(tokens)
            columns.append(pos)
            is_word_start = index == 0 or (prev_raw is not None and prev_raw.endswith("</w>"))
            try:
                display = hf.convert_tokens_to_string([raw])
            except Exception:
                display = raw
            # The slow CLIP tokenizer strips the marker in convert_tokens_to_string
            # (and decodes the bytes); the fast one of transformers 5 keeps it.
            tokens.append(display.replace("</w>", " ").strip())
            if is_word_start and current:
                groups.append(current)
                current = []
            current.append(index)
            prev_raw = raw
        if current:
            groups.append(current)

    tokens_t5, groups_t5 = [], []
    t5_chunks = by_encoder.get("t5xxl") or []
    if t5_chunks:
        held = sum(len(chunk) for chunk in t5_chunks)
        if len(t5_chunks) > 1 or held > T5_WINDOW:
            raise RuntimeError(
                f"The prompt runs to {held} T5 positions and the map reads "
                f"{T5_WINDOW}, the length the Diffusers instrument cut at. "
                f"Shorten the prompt."
            )
        hf_t5 = tok.t5xxl.tokenizer
        special_t5 = {tok.t5xxl.end_token, tok.t5xxl.pad_token}
        current = []
        for pos, entry in enumerate(t5_chunks[0]):
            tid = entry[0]
            if not isinstance(tid, int) or tid in special_t5:
                continue
            raw = hf_t5.convert_ids_to_tokens(tid)
            index = len(tokens_t5)
            columns.append(77 + pos)
            is_word_start = raw.startswith("▁")
            tokens_t5.append(raw.lstrip("▁"))
            if is_word_start and current:
                groups_t5.append(current)
                current = []
            current.append(index)
        if current:
            groups_t5.append(current)

    return tokens, groups, tokens_t5, groups_t5, columns


class Readout:
    """What one run captures.

    Sums per (step, block) over every batch entry and head that passed, and the
    count of them, so that negative and positive weigh the same whether ComfyUI
    ran them as one batch or one after the other.
    """

    def __init__(self, layers, steps, columns, tokens):
        self.layers = list(layers)
        self.steps = list(steps)
        self.columns = list(columns)
        self.tokens = tokens  # (tokens, word_groups, tokens_t5, word_groups_t5)
        self.sums = {}
        self.counted = {}
        self.n_img = None
        self.n_txt = None

    def add(self, step, layer, summed, entries):
        key = (step, layer)
        if key in self.sums:
            self.sums[key] += summed
            self.counted[key] += entries
        else:
            self.sums[key] = summed
            self.counted[key] = entries

    def maps(self):
        """{step_N: {layer_M: [[int]]}}, quantized the way the twin did."""
        out = {}
        for (step, layer), total in sorted(self.sums.items()):
            mean = total / self.counted[(step, layer)]
            out.setdefault(f"step_{step}", {})[f"layer_{layer}"] = \
                (mean * QUANT).round().to(torch.int32).tolist()
        return out


def read_attention(func, q, k, v, heads, readout, step, layer, n_txt, n_img,
                   *rest, **kwargs):
    """The override: the picture's attention as ComfyUI computes it, and beside
    it the readout of the text weights, when this pass is one to read.

    `func` is the attention ComfyUI would have called; it is called first, with
    everything it was given, and its result returned unchanged. The readout
    only happens for the joint attention (q holds n_txt + n_img positions);
    the image self-attention of an x_block_self_attn block has other lengths
    and passes through.
    """
    out = func(q, k, v, heads, *rest, **kwargs)
    if step is None or step not in readout.steps:
        return out
    mask = kwargs.get("mask", rest[0] if len(rest) > 0 else None)
    skip_reshape = kwargs.get("skip_reshape", rest[2] if len(rest) > 2 else False)
    if skip_reshape:
        qh, kh = q, k
    else:
        b, l, hd = q.shape
        qh = q.reshape(b, l, heads, hd // heads).transpose(1, 2)
        kh = k.reshape(b, k.shape[1], heads, hd // heads).transpose(1, 2)
    if qh.shape[2] != n_txt + n_img or kh.shape[2] != n_txt + n_img:
        return out
    if mask is not None:
        # SD 3.5 passes none. A map read under a mask this code did not apply
        # would be a different map than the picture was made with.
        raise RuntimeError("Attention Capture: this joint attention carries a "
                           "mask, which the readout does not apply.")
    with torch.no_grad():
        batch, n_heads, _, dim = qh.shape
        scale = 1.0 / math.sqrt(dim)
        cols = torch.as_tensor(readout.columns, device=q.device, dtype=torch.long)
        acc = torch.zeros((n_img, cols.numel()), dtype=torch.float32, device=q.device)
        q_img = qh[:, :, n_txt:, :]
        for entry in range(batch):
            for first in range(0, n_heads, HEADS_AT_ONCE):
                last = min(first + HEADS_AT_ONCE, n_heads)
                scores = torch.matmul(
                    q_img[entry, first:last], kh[entry, first:last].transpose(-2, -1)
                ) * scale
                weights = torch.softmax(scores, dim=-1)[:, :, :n_txt]
                acc += weights[:, :, cols].float().sum(dim=0)
        readout.n_img, readout.n_txt = n_img, n_txt
        readout.add(step, layer, acc.cpu(), batch * n_heads)
    return out


def block_replacement(readout, layer):
    """The replacement for joint block `layer`: the original block, with the
    override set for its attention calls and nothing else changed."""
    def replaced(args, extra):
        options = dict(args["transformer_options"])
        step = step_of(options)
        n_txt = args["txt"].shape[1]
        n_img = args["img"].shape[1]

        def override(func, q, k, v, *rest, **kwargs):
            # wrap_attn hands over (func, q, k, v, heads=..., mask=...,
            # transformer_options=..., _inside_attn_wrapper=True); everything
            # goes on to func as it came, the wrapper key included.
            if "heads" in kwargs:
                heads = kwargs.pop("heads")
            else:
                heads, rest = rest[0], rest[1:]
            return read_attention(func, q, k, v, heads, readout, step, layer,
                                  n_txt, n_img, *rest, **kwargs)

        options["optimized_attention_override"] = override
        return extra["original_block"]({**args, "transformer_options": options})
    return replaced


class AI4ArtsEdAttentionCapture:
    """Patches a MODEL to read out the attention of chosen joint blocks."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP", {"tooltip": "The CLIP the graph encodes with; "
                                             "read for its tokenizers."}),
                "text": ("STRING", {"multiline": True,
                                    "tooltip": "The positive prompt, as encoded."}),
                "capture_layers": ("STRING", {"default": "3,9,17"}),
                "steps": ("INT", {"default": 25, "min": 1, "max": 10000}),
                "capture_every_n_steps": ("INT", {"default": 1, "min": 1, "max": 10000}),
            },
        }

    RETURN_TYPES = ("MODEL", "AI4ARTSED_ATTENTION_READOUT")
    RETURN_NAMES = ("model", "readout")
    FUNCTION = "patch"
    CATEGORY = "AI4ArtsEd/latent lab"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Never from the cache: the readout is the run's, and a cached model
        # patch would carry the last run's sums into this one.
        return float("nan")

    def patch(self, model, clip, text, capture_layers, steps, capture_every_n_steps):
        layers = parse_layers(capture_layers)
        blocks = getattr(getattr(model.model, "diffusion_model", None), "joint_blocks", None)
        if blocks is None:
            raise RuntimeError(
                "This model has no joint blocks. Attention Cartography reads "
                "SD 3.5's MMDiT; load the SD 3.5 checkpoint."
            )
        for layer in layers:
            if layer >= len(blocks):
                raise RuntimeError(
                    f"Block {layer} does not exist: this model has {len(blocks)} "
                    f"joint blocks (0 to {len(blocks) - 1})."
                )
        picked = capture_steps(steps, capture_every_n_steps)
        tokens, groups, tokens_t5, groups_t5, columns = word_columns(clip, text)
        if not columns:
            raise RuntimeError(
                "The prompt tokenizes to no word: nothing to read the attention on."
            )
        readout = Readout(layers, picked, columns, (tokens, groups, tokens_t5, groups_t5))
        patched = model.clone()
        for layer in layers:
            patched.set_model_patch_replace(
                block_replacement(readout, layer), "dit", "double_block", layer)
        logger.info("[AI4ArtsEd] Attention Capture: blocks %s, steps %s, %d CLIP-L and "
                    "%d T5 tokens, %d columns", layers, picked, len(tokens),
                    len(tokens_t5), len(columns))
        return (patched, readout)


class AI4ArtsEdAttentionMaps:
    """Writes what a run read out, once the sampler has run."""

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "readout": ("AI4ARTSED_ATTENTION_READOUT",),
                "samples": ("LATENT", {"tooltip": "The sampler's output: read for "
                                                  "its size, and taken so that this "
                                                  "node runs after the sampler."}),
                "filename_prefix": ("STRING", {"default": "ai4artsed_attention"}),
            },
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "write"
    OUTPUT_NODE = True
    CATEGORY = "AI4ArtsEd/latent lab"

    def write(self, readout, samples, filename_prefix):
        if not readout.sums:
            raise RuntimeError(
                "Nothing was read out: no forward pass of a chosen block fell on "
                "a chosen step. The MODEL the sampler ran must be the one "
                "AI4ArtsEdAttentionCapture handed out."
            )
        missing = [(step, layer) for step in readout.steps for layer in readout.layers
                   if (step, layer) not in readout.sums]
        if missing:
            # The surface draws nothing for a step it has no map of and says
            # nothing about it; a run whose sampler passed a step of the
            # schedule by is refused here with the step.
            raise RuntimeError(
                f"{len(missing)} of the {len(readout.steps) * len(readout.layers)} "
                f"(step, block) maps were never read, the first at step "
                f"{missing[0][0]}, block {missing[0][1]}: the sampler has to call "
                f"the model once at every step of its schedule."
            )
        latent = samples["samples"]
        lat_h, lat_w = int(latent.shape[-2]), int(latent.shape[-1])
        if lat_h % PATCH or lat_w % PATCH:
            # The model pads a latent of odd size to its patch (mmdit.py
            # pad_to_patch_size), and the maps then lie on a grid the picture
            # has not got.
            raise RuntimeError(
                f"The picture is {lat_w * 8} x {lat_h * 8}: width and height have "
                f"to be multiples of {PATCH * 8} for the maps to lie on it."
            )
        spatial = [lat_h // PATCH, lat_w // PATCH]
        if spatial[0] * spatial[1] != readout.n_img:
            raise RuntimeError(
                f"The readout holds {readout.n_img} image positions, the latent "
                f"{spatial[0]} x {spatial[1]} = {spatial[0] * spatial[1]}: this "
                f"latent is not the one the maps were read from."
            )
        tokens, groups, tokens_t5, groups_t5 = readout.tokens
        record = {
            "tokens": tokens,
            "word_groups": groups,
            "tokens_t5": tokens_t5,
            "word_groups_t5": groups_t5,
            "clip_token_count": len(tokens),
            "attention_maps": readout.maps(),
            "spatial_resolution": spatial,
            "image_resolution": [lat_h * 8, lat_w * 8],
            "capture_layers": readout.layers,
            "capture_steps": readout.steps,
            "text_positions": readout.n_txt,
        }
        full_folder, filename, counter, subfolder, _prefix = \
            folder_paths.get_save_image_path(filename_prefix, self.output_dir)
        name = f"{filename}_{counter:05}_.json"
        with open(os.path.join(full_folder, name), "w", encoding="utf-8") as fh:
            json.dump(record, fh)
        logger.info("[AI4ArtsEd] Attention Maps: %d (step, block) maps of %d x %d -> %s",
                    len(readout.sums), readout.n_img, len(readout.columns), name)
        return {
            "ui": {
                # Its own key, so nothing that looks for pictures picks it up;
                # the DevServer's ws client fetches it as media_type "attention".
                "ai4artsed_attention": [{
                    "filename": name, "subfolder": subfolder, "type": "output",
                }],
            },
            "result": (samples,),
        }


NODE_CLASS_MAPPINGS = {
    "AI4ArtsEdAttentionCapture": AI4ArtsEdAttentionCapture,
    "AI4ArtsEdAttentionMaps": AI4ArtsEdAttentionMaps,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AI4ArtsEdAttentionCapture": "AI4ArtsEd Attention Capture (joint blocks)",
    "AI4ArtsEdAttentionMaps": "AI4ArtsEd Attention Maps (write out)",
}
