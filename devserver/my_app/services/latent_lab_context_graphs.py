"""
The graphs of the embedding research series on ComfyUI, and one way to run them.

Four instruments write into the text stream of SD 3.5's joint blocks. The nodes
are comfyui_nodes/ai4artsed_sd3_context.py. Their Diffusers twin for the
Decomposition stays in gpu_service/services/diffusers_backend.py
(generate_image_with_decomposition, research path, decision of 2026-09-19); the
twins generate_image_with_fusion_scheduled, _position_probe, _delayed_kickin and
_delayed_kickin_cumulative were struck on 2026-10-10. The schedule tables below
are the twin's DECOMP_* tables. Each builder returns the API-format
graph one run submits, the way the chunks build theirs
(schemas/engine/comfyui_chunk_support.py); the caller decides checkpoint, seed
and size.

    fusion_scheduled_graph    the Fusion Workbench's cell: the Surrealizer's fusion
                              written into the text stream at the entry blocks, in a
                              step window (routes/fusion_workbench_routes.py)
    decomposition_graph       the Decomposition's cells, one delta node each, chained
                              on the model (the research route; the surface that ran
                              it left on 2026-09-19)
    position_probe_graph      one stream's slice from a probe prompt, over a block
                              range and a step range
    delayed_kickin_graph      the full prompt from a step on, at one block: written in
                              directly at block 0, past it recorded in two pre-runs at
                              the same seed and replayed
    cumulative_kickin_graph   the same over blocks 0..up_to_block

`run_graph` submits a graph through the ws client, which takes the GPU lease, and
returns the saved picture; a synchronous route runs it through
my_app/services/own_loop.py.
"""

import logging

logger = logging.getLogger(__name__)

# The twin's DECOMP_STEP_BANDS and DECOMP_LAYER_BANDS: fractions of the run,
# `lo <= step / steps < hi`, the last one open to 1.01 so that a window can name
# the end; and the block ranges of SD 3.5 Large's 38 joint blocks, whose first
# block is where a band's injection enters.
STEP_BANDS = {
    "composition": (0.0, 0.32),
    "semantics": (0.32, 0.68),
    "detail": (0.68, 1.01),
}
LAYER_BANDS = {
    "shallow": (0, 10),
    "middle": (10, 23),
    "deep": (23, 38),
}
STREAMS = ("clip_l", "clip_g", "t5")

# The far end of a step window; the node's widget reaches the same number.
WINDOW_END = 1.01

# The one node every graph here saves through, read by `run_graph`.
SAVE_NODE_ID = "40"

# The node ids of the sampler branch, shared so that a test can find them.
SAMPLER_NODE_ID = "20"
DECODE_NODE_ID = "22"
LATENT_NODE_ID = "3"
MODEL_NODE_ID = "5"


def _frame(checkpoint, width, height):
    """Loaders, T5 length, empty latent: what every graph here opens with."""
    from schemas.engine.comfyui_chunk_support import (
        CLIP_NODE, checkpoint_loader, t5_length, triple_clip_loader,
    )
    return {
        MODEL_NODE_ID: checkpoint_loader(checkpoint),
        "7": triple_clip_loader(),
        CLIP_NODE: t5_length(),
        LATENT_NODE_ID: {
            "inputs": {"width": int(width), "height": int(height), "batch_size": 1},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "Empty latent"},
        },
    }


def _sampler(model, positive, negative, seed, steps, cfg, title="Sample",
             sampler_name="euler", scheduler="normal"):
    return {
        "inputs": {
            "model": model, "positive": positive, "negative": negative,
            "latent_image": [LATENT_NODE_ID, 0], "seed": int(seed), "steps": int(steps),
            "cfg": float(cfg), "sampler_name": sampler_name, "scheduler": scheduler,
            "denoise": 1,
        },
        "class_type": "KSampler",
        "_meta": {"title": title},
    }


def _finish(graph, samples):
    """Decode and save what `samples` names."""
    graph[DECODE_NODE_ID] = {
        "inputs": {"samples": samples, "vae": [MODEL_NODE_ID, 2]},
        "class_type": "VAEDecode",
        "_meta": {"title": "Decode"},
    }
    graph[SAVE_NODE_ID] = {
        "inputs": {"filename_prefix": "ComfyUI", "images": [DECODE_NODE_ID, 0]},
        "class_type": "SaveImage",
        "_meta": {"title": "Save"},
    }
    return graph


def _fraction_window(window):
    """[lo, hi] as the twin read `step_window`: two fractions of the run."""
    try:
        lo, hi = window
        lo, hi = float(lo), float(hi)
    except (TypeError, ValueError):
        raise ValueError(
            f"step_window is a pair [lo, hi] of fractions of the run, got {window!r}")
    return lo, hi


def scheduled_windows(step_window, step_bands):
    """The step windows one scheduled fusion injects in: the free window where
    it is given, else the named bands, each its own pair (the twin checks
    `phase in step_bands` at every step)."""
    if step_window is not None:
        return [_fraction_window(step_window)]
    names = list(STEP_BANDS) if step_bands is None else list(step_bands)
    for name in names:
        if name not in STEP_BANDS:
            raise ValueError(f"unknown step_band {name!r}; valid={list(STEP_BANDS)}")
    return [STEP_BANDS[name] for name in names]


def scheduled_blocks(layer_entry, layer_bands):
    """The blocks a scheduled fusion enters at: the one named, else the first
    block of each named band."""
    if layer_entry is not None:
        try:
            return [int(layer_entry)]
        except (TypeError, ValueError):
            raise ValueError(f"layer_entry is a block index, got {layer_entry!r}")
    names = list(LAYER_BANDS) if layer_bands is None else list(layer_bands)
    for name in names:
        if name not in LAYER_BANDS:
            raise ValueError(f"unknown layer_band {name!r}; valid={list(LAYER_BANDS)}")
    return [LAYER_BANDS[name][0] for name in names]


def fusion_scheduled_graph(prompt, t5_prompt, negative_prompt, checkpoint, strategy,
                           alpha, blocks, windows, width, height, steps, cfg, seed):
    """The Fusion Workbench's cell.

    The sampler runs on the fusion at alpha 0 under `legacy` -- the CLIP block
    with T5's tail, the twin's `fused_0` -- for both sides; at the entry blocks,
    inside each window, the text stream is replaced by the fusion at alpha under
    the strategy, the positive entries by the prompt's, the negative by the
    negative prompt's fused the same way (the twin's `enc_pos_A` / `enc_neg_A`).
    """
    from schemas.engine.comfyui_chunk_support import sd3_assemble, sd3_encode, sd3_fusion
    graph = _frame(checkpoint, width, height)
    graph["10"] = sd3_encode(prompt, title="Encode the CLIP side", empty_padding="empty_prompt")
    t5_from = "10"
    if t5_prompt != prompt:
        graph["11"] = sd3_encode(t5_prompt, title="Encode the T5 side",
                                 empty_padding="empty_prompt")
        t5_from = "11"
    graph["14"] = sd3_encode(negative_prompt, title="Encode the negative",
                             empty_padding="empty_prompt")
    graph["12"] = sd3_fusion(["10", 0], [t5_from, 0], 0.0, "legacy", "The run's positive")
    graph["13"] = sd3_assemble(["12", 0], "Positive")
    graph["15"] = sd3_fusion(["14", 0], ["14", 0], 0.0, "legacy", "The run's negative")
    graph["16"] = sd3_assemble(["15", 0], "Negative")
    graph["17"] = sd3_fusion(["10", 0], [t5_from, 0], alpha, strategy, "Fuse CLIP and T5")
    graph["18"] = sd3_assemble(["17", 0], "Positive, fused")
    graph["19"] = sd3_fusion(["14", 0], ["14", 0], alpha, strategy,
                             "Fuse the negative the same way")
    graph["21"] = sd3_assemble(["19", 0], "Negative, fused")
    model = [MODEL_NODE_ID, 0]
    # No block or no window: nothing is written, the run is the alpha-0 fusion
    # (the twin installed no hook then and sampled plain).
    for k, (lo, hi) in enumerate(windows if blocks else []):
        node_id = str(30 + k)
        graph[node_id] = {
            "inputs": {
                "model": model, "positive": ["18", 0], "negative": ["21", 0],
                "blocks": ",".join(str(b) for b in blocks),
                "step_from": lo, "step_to": hi,
            },
            "class_type": "AI4ArtsEdSD3ContextReplace",
            "_meta": {"title": "Write the fusion into the text stream"},
        }
        model = [node_id, 0]
    graph[SAMPLER_NODE_ID] = _sampler(model, ["13", 0], ["16", 0], seed, steps, cfg)
    return _finish(graph, [SAMPLER_NODE_ID, 0])


def normalized_cells(cells, per_stream):
    """The twin's cell list: explicit cells checked one by one, an empty prompt an
    inactive cell, and one delta per (step, layer, stream), the last prompt named
    for a place standing (the twin kept them in a dict keyed by the place);
    without them the per-stream prompts spread over their bands.

    `per_stream` is {stream: (prompt, step_bands, layer_bands)}, each band list
    None for all.
    """
    out = []
    if cells:
        by_place = {}
        for i, cell in enumerate(cells):
            if not isinstance(cell, dict):
                raise ValueError(f"cells[{i}] must be a dict, got {type(cell)}")
            step, layer, stream = cell.get("step"), cell.get("layer"), cell.get("stream")
            prompt = cell.get("prompt")
            if step not in STEP_BANDS:
                raise ValueError(f"cells[{i}].step={step!r}; valid: {sorted(STEP_BANDS)}")
            if layer not in LAYER_BANDS:
                raise ValueError(f"cells[{i}].layer={layer!r}; valid: {sorted(LAYER_BANDS)}")
            if stream not in STREAMS:
                raise ValueError(f"cells[{i}].stream={stream!r}; valid: {sorted(STREAMS)}")
            if not prompt or not str(prompt).strip():
                continue
            by_place[(step, layer, stream)] = str(prompt)
        return [{"step": step, "layer": layer, "stream": stream, "prompt": prompt}
                for (step, layer, stream), prompt in by_place.items()]
    for stream in STREAMS:
        prompt, step_bands, layer_bands = per_stream.get(stream, (None, None, None))
        if not prompt:
            continue
        for name, table, bands in (("step", STEP_BANDS, step_bands),
                                   ("layer", LAYER_BANDS, layer_bands)):
            invalid = set(bands or []) - set(table)
            if invalid:
                raise ValueError(
                    f"{stream}_{name}_bands: invalid bands {invalid}; valid: {sorted(table)}")
        for step in (step_bands or list(STEP_BANDS)):
            for layer in (layer_bands or list(LAYER_BANDS)):
                out.append({"step": step, "layer": layer, "stream": stream, "prompt": prompt})
    return out


def decomposition_graph(source_prompt, cells, alpha, negative_prompt, checkpoint,
                        width, height, steps, cfg, seed):
    """The Decomposition run: the source sampled, and per cell one delta node
    on the model, chained. Each unique override prompt is encoded once."""
    from schemas.engine.comfyui_chunk_support import negative_encode, text_encode
    graph = _frame(checkpoint, width, height)
    graph["1"] = text_encode(source_prompt, title="Source")
    graph["6"] = negative_encode(negative_prompt)
    encoded = {}
    model = [MODEL_NODE_ID, 0]
    for k, cell in enumerate(cells):
        prompt = cell["prompt"]
        if prompt not in encoded:
            node_id = str(50 + len(encoded))
            graph[node_id] = text_encode(prompt, title=f"Override {len(encoded) + 1}")
            encoded[prompt] = node_id
        lo, hi = STEP_BANDS[cell["step"]]
        node_id = str(60 + k)
        graph[node_id] = {
            "inputs": {
                "model": model, "base": ["1", 0], "override": [encoded[prompt], 0],
                "stream": cell["stream"], "block": LAYER_BANDS[cell["layer"]][0],
                "step_from": lo, "step_to": hi, "alpha": float(alpha),
            },
            "class_type": "AI4ArtsEdSD3ContextDelta",
            "_meta": {"title": f"{cell['step']} x {cell['layer']} x {cell['stream']}"},
        }
        model = [node_id, 0]
    graph[SAMPLER_NODE_ID] = _sampler(model, ["1", 0], ["6", 0], seed, steps, cfg)
    return _finish(graph, [SAMPLER_NODE_ID, 0])


def position_probe_graph(baseline_prompt, probe_prompt, probe_stream, probe_step_range,
                         probe_block_range, negative_prompt, checkpoint, width, height,
                         steps, cfg, seed):
    """The position probe: the baseline sampled, one stream's slice replaced by
    the probe's at every block of the range, during the steps of the range."""
    from schemas.engine.comfyui_chunk_support import negative_encode, text_encode
    if probe_stream not in STREAMS:
        raise ValueError(f"probe_stream={probe_stream!r}; valid: {sorted(STREAMS)}")
    if not isinstance(probe_step_range, (list, tuple)) or len(probe_step_range) != 2:
        raise ValueError(f"probe_step_range must be [lo, hi], got {probe_step_range!r}")
    step_lo, step_hi = int(probe_step_range[0]), int(probe_step_range[1])
    if not (0 <= step_lo < step_hi <= int(steps)):
        raise ValueError(
            f"probe_step_range=[{step_lo},{step_hi}) must satisfy 0 <= lo < hi <= steps={steps}")
    if not isinstance(probe_block_range, (list, tuple)) or len(probe_block_range) != 2:
        raise ValueError(f"probe_block_range must be [lo, hi], got {probe_block_range!r}")
    block_lo, block_hi = int(probe_block_range[0]), int(probe_block_range[1])
    if not (0 <= block_lo < block_hi):
        raise ValueError(
            f"probe_block_range=[{block_lo},{block_hi}) must satisfy 0 <= lo < hi")
    graph = _frame(checkpoint, width, height)
    graph["1"] = text_encode(baseline_prompt, title="Baseline")
    graph["2"] = text_encode(probe_prompt, title="Probe")
    graph["6"] = negative_encode(negative_prompt)
    graph["30"] = {
        "inputs": {
            "model": [MODEL_NODE_ID, 0], "base": ["1", 0], "probe": ["2", 0],
            "stream": probe_stream, "block_from": block_lo, "block_to": block_hi,
            # The twin compared step indices; step / steps against lo / steps
            # and hi / steps is the same comparison.
            "step_from": step_lo / int(steps), "step_to": step_hi / int(steps),
        },
        "class_type": "AI4ArtsEdSD3ContextProbe",
        "_meta": {"title": "Write the probe's slice into the text stream"},
    }
    graph[SAMPLER_NODE_ID] = _sampler(["30", 0], ["1", 0], ["6", 0], seed, steps, cfg)
    return _finish(graph, [SAMPLER_NODE_ID, 0])


def _kickin_with_prerun(graph, block_from, block_to, kickin_step, seed, steps, cfg):
    """Two pre-runs at the same seed, one on each prompt, record what the blocks
    receive; the main run replays them, the early run's frames before the
    kick-in step and the full run's from it on, and frees the recordings."""
    graph["31"] = {
        "inputs": {"model": [MODEL_NODE_ID, 0], "block_from": block_from, "block_to": block_to},
        "class_type": "AI4ArtsEdSD3ContextCapture",
        "_meta": {"title": "Record the early run"},
    }
    graph["23"] = _sampler(["31", 0], ["1", 0], ["6", 0], seed, steps, cfg,
                           title="Pre-run, early prompt")
    graph["32"] = {
        "inputs": {"model": [MODEL_NODE_ID, 0], "block_from": block_from, "block_to": block_to},
        "class_type": "AI4ArtsEdSD3ContextCapture",
        "_meta": {"title": "Record the full run"},
    }
    graph["24"] = _sampler(["32", 0], ["2", 0], ["6", 0], seed, steps, cfg,
                           title="Pre-run, full prompt")
    graph["33"] = {
        "inputs": {
            "model": [MODEL_NODE_ID, 0], "early": ["31", 1], "full": ["32", 1],
            "kickin_step": int(kickin_step),
            "samples_early": ["23", 0], "samples_full": ["24", 0],
        },
        "class_type": "AI4ArtsEdSD3ContextReplay",
        "_meta": {"title": "Replay: early, then full"},
    }
    graph[SAMPLER_NODE_ID] = _sampler(["33", 0], ["1", 0], ["6", 0], seed, steps, cfg)
    graph["34"] = {
        "inputs": {"samples": [SAMPLER_NODE_ID, 0], "early": ["31", 1], "full": ["32", 1]},
        "class_type": "AI4ArtsEdSD3ContextRelease",
        "_meta": {"title": "Free the recordings"},
    }
    return _finish(graph, ["34", 0])


def delayed_kickin_graph(prompt_early, prompt_full, kickin_step, block, negative_prompt,
                         checkpoint, width, height, steps, cfg, seed):
    """The delayed kick-in at one block: the early prompt sampled, the full
    prompt's text stream written in at the block from the kick-in step on.

    At block 0 what the block receives is the embedded conditioning and nothing
    else, so it is written in directly; past block 0 it is what the blocks
    before made of it, and that is recorded in two pre-runs and replayed.
    """
    from schemas.engine.comfyui_chunk_support import negative_encode, text_encode
    kickin_step, block, steps = int(kickin_step), int(block), int(steps)
    if kickin_step < 0:
        raise ValueError(f"kickin_step must be >= 0, got {kickin_step}")
    if block < 0:
        raise ValueError(f"the hook block must be >= 0, got {block}")
    graph = _frame(checkpoint, width, height)
    graph["1"] = text_encode(prompt_early, title="Early prompt")
    graph["2"] = text_encode(prompt_full, title="Full prompt")
    graph["6"] = negative_encode(negative_prompt)
    if block == 0:
        graph["30"] = {
            "inputs": {
                "model": [MODEL_NODE_ID, 0], "positive": ["2", 0], "blocks": "0",
                # `cur_step >= kickin_step` as a fraction window; a kick-in past
                # the run's end injects nowhere, as it did.
                "step_from": min(kickin_step / steps, WINDOW_END), "step_to": WINDOW_END,
            },
            "class_type": "AI4ArtsEdSD3ContextReplace",
            "_meta": {"title": "The full prompt from the kick-in step on"},
        }
        graph[SAMPLER_NODE_ID] = _sampler(["30", 0], ["1", 0], ["6", 0], seed, steps, cfg)
        return _finish(graph, [SAMPLER_NODE_ID, 0])
    return _kickin_with_prerun(graph, block, block + 1, kickin_step, seed, steps, cfg)


def cumulative_kickin_graph(prompt_early, prompt_full, kickin_step, up_to_block,
                            negative_prompt, checkpoint, width, height, steps, cfg, seed):
    """The cumulative kick-in: recorded and replayed at every block from 0 up to
    and including `up_to_block`."""
    from schemas.engine.comfyui_chunk_support import negative_encode, text_encode
    kickin_step, up_to_block = int(kickin_step), int(up_to_block)
    if kickin_step < 0:
        raise ValueError(f"kickin_step must be >= 0, got {kickin_step}")
    if up_to_block < 0:
        raise ValueError(f"up_to_block must be >= 0, got {up_to_block}")
    graph = _frame(checkpoint, width, height)
    graph["1"] = text_encode(prompt_early, title="Early prompt")
    graph["2"] = text_encode(prompt_full, title="Full prompt")
    graph["6"] = negative_encode(negative_prompt)
    return _kickin_with_prerun(graph, 0, up_to_block + 1, kickin_step, seed, steps, cfg)


async def checkpoint_of(model_id, tag):
    """The checkpoint a run loads: the model named, or SD 3.5 Large, the model
    the 38-block tables above describe and the twin's default; and the model
    id the run is recorded under."""
    from my_app.services.latent_lab_model import LATENT_LAB_LARGE, get_latent_lab_unet
    from schemas.engine.comfyui_chunk_support import checkpoint_for
    model_id = model_id or LATENT_LAB_LARGE
    unet_id, _pipeline_class = get_latent_lab_unet()
    checkpoint = checkpoint_for(model_id, LATENT_LAB_LARGE, unet_id)
    if checkpoint is None:
        raise ValueError(
            f"[{tag}] No ComfyUI checkpoint mapped for {model_id!r}. Extend "
            f"schemas/engine/comfyui_chunk_support.py::checkpoint_for and make sure "
            f"download_models.sh fetches the file."
        )
    return checkpoint, model_id


async def run_graph(workflow, workload, tag):
    """One graph through the ws client, which takes the GPU lease: the saved
    picture, base64. `workload` is what the gate files the run's duration under."""
    from my_app.services.comfyui_manager import get_comfyui_manager
    from my_app.services.comfyui_ws_client import get_comfyui_ws_client
    from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
    from schemas.engine.comfyui_chunk_support import checkpoint_available, final_image

    if not await get_comfyui_manager().ensure_comfyui_available():
        raise RuntimeError("ComfyUI is not available")
    client = get_comfyui_ws_client()
    checkpoint = workflow[MODEL_NODE_ID]["inputs"]["ckpt_name"]
    if await checkpoint_available(client.base_url, checkpoint, tag) is False:
        raise RuntimeError(
            f"ComfyUI has no checkpoint {checkpoint!r}. ./download_models.sh fetches it.")
    token = CURRENT_OUTPUT_CONFIG.set(workload)
    try:
        result = await client.submit_and_track(workflow, timeout=None)
    finally:
        CURRENT_OUTPUT_CONFIG.reset(token)
    image = final_image(result, SAVE_NODE_ID)
    if image is None:
        raise RuntimeError(f"[{tag}] ComfyUI answered without a picture (prompt {result.prompt_id})")
    return image
