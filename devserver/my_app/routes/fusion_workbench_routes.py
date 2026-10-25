"""
Fusion Workbench Routes — the embedding research series, run on ComfyUI

Latent Lab research tool: the SCHEDULED-fusion experiments of the Fusion
Workbench (the Surrealizer effect localized to Step-Band x Layer-Band cells,
swept over fusion strength alpha), and beside them the three instruments of the
same series that only the research scripts under devserver/testfiles reach:
the Decomposition's cells, the position probe and the delayed kick-in. Frontend
and scripts call /api/fusion_workbench/* -> DevServer -> ComfyUI, on the graphs
of my_app/services/latent_lab_context_graphs.py. Until stage 4 of the move to
ComfyUI these were thin proxies to the GPU service's Diffusers routes.

Deliberately BYPASSES the 4-stage pedagogical pipeline: a controlled research
sweep must send the exact operand (prompt, seed, alpha) to the card with NO
Stage-2 interception, so that image differences are attributable to the
injection schedule alone. The four research routes answer at the research
level only (`_research_run`); /generate stands as it stood, an open item of
docs/WORK_ORDER_CONTENT_CHECKING.md (A7).

Endpoints:
- POST /api/fusion_workbench/generate                   - one scheduled-fusion cell
- POST /api/fusion_workbench/expand_t5                  - the Surrealizer's T5 expander
- POST /api/fusion_workbench/decomposition              - one Decomposition run (research level)
- POST /api/fusion_workbench/position_probe             - one position probe (research level)
- POST /api/fusion_workbench/delayed_kickin             - one delayed kick-in at one block (research level)
- POST /api/fusion_workbench/delayed_kickin_cumulative  - one over blocks 0..up_to_block (research level)
"""

import functools
import logging
import random

from flask import Blueprint, request, jsonify


from my_app.services.streaming_response import (answered_either_way,
                                                note_dispatch,
                                                object_body,
                                                without_transport_flags)

logger = logging.getLogger(__name__)

fusion_workbench_bp = Blueprint('fusion_workbench', __name__, url_prefix='/api/fusion_workbench')

# The refusal shape this proxy's page reads: views/latent_lab/fusion_workbench.vue
# branches on `success` before it looks at `error`.
_proxy_body = functools.partial(object_body, envelope={"success": False})


# The fusions the workbench's strategy axis carries (the `vocab` of `strategy`
# in views/latent_lab/fusion_workbench.vue). `original` is the Surrealizer's
# 2025 workflow and no strategy of a sweep; the twin ran that name as `legacy`
# without a word, here it is refused with its name.
WORKBENCH_FUSIONS = ("centered_fade", "legacy", "dual_alpha", "slerp", "normalized")

# What the gate files a run of each instrument under.
WORKLOADS = {
    'generate': 'fusion_scheduled',
    'decomposition': 'decomposition',
    'position_probe': 'position_probe',
    'delayed_kickin': 'delayed_kickin',
    'delayed_kickin_cumulative': 'delayed_kickin_cumulative',
}


def _number(data, name, default, kind=int):
    """data[name] as a number, `default` where the body leaves it out or sends
    null; a value that is no number is refused with its name and value (a 400
    through `_run`, where `int(None)` used to be a 500 without a sentence)."""
    value = data.get(name)
    if value is None:
        return default
    try:
        return kind(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} {value!r}: a number")


def _size_and_seed(data):
    """width, height, steps, cfg, seed as the twin's routes read them; a seed of
    -1 (the surfaces' "random"), or none at all, drawn here, so the record carries
    the one that ran."""
    seed = _number(data, 'seed', -1)
    if seed < 0:
        seed = random.randint(0, 2 ** 32 - 1)
    return (_number(data, 'width', 1024), _number(data, 'height', 1024),
            _number(data, 'steps', 25), _number(data, 'cfg_scale', 5.5, float), seed)


def _fusion_named(fusion_strategy):
    """The bare name of the fusion, or the reason the name cannot run here."""
    base, *options = str(fusion_strategy or "legacy").split("#")
    if options:
        raise ValueError(
            f"fusion_strategy {fusion_strategy!r}: the options after '#' "
            f"({', '.join(options)}) run on the Diffusers twin alone")
    if base not in WORKBENCH_FUSIONS:
        raise ValueError(
            f"fusion_strategy {base!r} is none of {', '.join(WORKBENCH_FUSIONS)}")
    return base


async def _graph_for(kind, data):
    """The graph one request describes, the model it runs on and the seed it
    runs at: (graph, model_id, seed)."""
    from my_app.services import latent_lab_context_graphs as graphs

    tag = f"FUSION-WORKBENCH-{kind.upper()}"
    checkpoint, model_id = await graphs.checkpoint_of(data.get('model_id'), tag)
    width, height, steps, cfg, seed = _size_and_seed(data)
    negative = data.get('negative_prompt', '') or ''

    if kind == 'generate':
        prompt = data['prompt']
        graph = graphs.fusion_scheduled_graph(
            prompt=prompt, t5_prompt=data.get('t5_prompt') or prompt,
            negative_prompt=negative, checkpoint=checkpoint,
            strategy=_fusion_named(data.get('fusion_strategy')),
            alpha=float(data.get('alpha_factor', 20.0)),
            blocks=graphs.scheduled_blocks(data.get('layer_entry'), data.get('layer_bands')),
            windows=graphs.scheduled_windows(data.get('step_window'), data.get('step_bands')),
            width=width, height=height, steps=steps, cfg=cfg, seed=seed)
    elif kind == 'decomposition':
        per_stream = {
            stream: (data.get(f'{stream}_prompt'), data.get(f'{stream}_step_bands'),
                     data.get(f'{stream}_layer_bands'))
            for stream in graphs.STREAMS
        }
        cells = graphs.normalized_cells(data.get('cells'), per_stream)
        # The twin clamped alpha to [-1, 1] before anything ran.
        alpha = max(-1.0, min(1.0, float(data.get('alpha', 1.0))))
        graph = graphs.decomposition_graph(
            source_prompt=data['source_prompt'], cells=cells, alpha=alpha,
            negative_prompt=negative, checkpoint=checkpoint,
            width=width, height=height, steps=steps, cfg=cfg, seed=seed)
    elif kind == 'position_probe':
        graph = graphs.position_probe_graph(
            baseline_prompt=data['baseline_prompt'], probe_prompt=data['probe_prompt'],
            probe_stream=data.get('probe_stream'),
            probe_step_range=data.get('probe_step_range'),
            probe_block_range=data.get('probe_block_range'),
            negative_prompt=negative, checkpoint=checkpoint,
            width=width, height=height, steps=steps, cfg=cfg, seed=seed)
    elif kind == 'delayed_kickin':
        block_range = data.get('block_range')
        if block_range is None:
            block = 0
        elif isinstance(block_range, (list, tuple)) and len(block_range) == 2:
            # block_range[1] is ignored; the hook is installed on the single
            # block at the band's entry, as it was.
            block = int(block_range[0])
        else:
            raise ValueError(f"block_range must be [lo, hi], got {block_range!r}")
        graph = graphs.delayed_kickin_graph(
            prompt_early=data['prompt_early'], prompt_full=data['prompt_full'],
            kickin_step=data['kickin_step'], block=block,
            negative_prompt=negative, checkpoint=checkpoint,
            width=width, height=height, steps=steps, cfg=cfg, seed=seed)
    elif kind == 'delayed_kickin_cumulative':
        graph = graphs.cumulative_kickin_graph(
            prompt_early=data['prompt_early'], prompt_full=data['prompt_full'],
            kickin_step=data['kickin_step'], up_to_block=data['up_to_block'],
            negative_prompt=negative, checkpoint=checkpoint,
            width=width, height=height, steps=steps, cfg=cfg, seed=seed)
    else:
        raise ValueError(f"no instrument named {kind!r}")
    return graph, model_id, seed


def _required(kind):
    """The fields the twin's routes demanded, by presence: the position probe's
    baseline is the empty prompt by design (testfiles/test_decomposition_position_probe.py),
    so an empty string passes and only a missing field is refused."""
    return {
        'generate': ('prompt',),
        'decomposition': ('source_prompt',),
        'position_probe': ('baseline_prompt', 'probe_prompt', 'probe_step_range',
                           'probe_block_range', 'probe_stream'),
        'delayed_kickin': ('prompt_early', 'prompt_full', 'kickin_step'),
        'delayed_kickin_cumulative': ('prompt_early', 'prompt_full', 'kickin_step', 'up_to_block'),
    }[kind]


def _run(kind, data):
    """One run of one instrument on ComfyUI, and the ``(payload, http_status)``
    both ways back are made of.

    Split from the route so that one call can be answered either way. It must
    not reach for ``request``: the body is read at the request boundary and
    passed in, and a streamed answer runs this on a thread of its own.

    A schedule the run cannot be given reaches the page as the sentence that
    says why, as a 400. A card that is taken is a 503, the same request works in
    a moment. Everything else is a 500 with ComfyUI's own sentence: the node
    that refused, and what it refused.
    """
    from my_app.services import latent_lab_context_graphs as graphs
    from my_app.services.gpu_lease_client import GpuBusyError
    from my_app.services.own_loop import run_blocking

    data = without_transport_flags(data)
    for name in _required(kind):
        if name not in data:
            return {"success": False, "error": f"{name} required"}, 400

    async def one_run():
        graph, model_id, seed = await _graph_for(kind, data)
        # Which model this run is about to be drawn by, said on the connection
        # the run is already holding open (services/streaming_response.py).
        note_dispatch(model_id, local=True)
        image = await graphs.run_graph(graph, WORKLOADS[kind],
                                       f"FUSION-WORKBENCH-{kind.upper()}")
        return image, seed

    try:
        image, seed = run_blocking(one_run())
        payload = {"success": True, "image_base64": image, "seed": seed}
        # AI-Origin Disclosure (EU AI Act Art. 50): the sweep's cells go
        # straight through this route to the page, which downloads what it was
        # handed. No recorder sees them. `image_base64` is named explicitly:
        # here it is the result, elsewhere it is what a user brought in.
        try:
            from my_app.services.watermark_service import watermark_result_metadata
            watermark_result_metadata(payload, {'seed': seed}, extra_keys=('image_base64',))
        except Exception as e:
            logger.warning(f"[fusion_workbench] watermark not applied ({e})")
        return payload, 200
    # `note_dispatch(None)` in each: the run is at no model any more, and the
    # name would otherwise stand in the bar until the next dispatch replaced it.
    except ValueError as e:
        note_dispatch(None, local=True)
        return {"success": False, "error": str(e)}, 400
    except GpuBusyError as e:
        note_dispatch(None, local=True)
        return {"success": False, "error": f"the card is busy: {e}"}, 503
    except Exception as e:
        note_dispatch(None, local=True)
        logger.warning(f"[fusion_workbench] {kind} did not run: {e}")
        return {"success": False, "error": str(e)}, 500


@fusion_workbench_bp.route('/generate', methods=['POST'])
def generate():
    """One scheduled-fusion cell.

    Body: { prompt, t5_prompt?, alpha_factor, fusion_strategy, step_window?,
            layer_entry?, step_bands?, layer_bands?, negative_prompt?, width?,
            height?, steps?, cfg_scale?, seed?, model_id? }
    Returns: { success, image_base64 }

    With "enable_streaming" the answer travels as the platform's SSE stream
    instead of as one JSON body. It is the same cell; only its way back is
    different. A sweep sends these one after another, and each one stands in the
    plant-wide GPU queue before it renders -- up to
    GPU_ADMISSION_ACQUIRE_TIMEOUT_S, an hour and a half (gpu_service/config.py).
    The edge in front of this server ends a request whose origin has sent
    nothing for about 100 seconds and hands the browser a 524, which used to end
    the whole sweep on a cell the card had already made.

    The work names no `client_gone` parameter, and that is a decision rather
    than an omission: one ComfyUI run stands behind it, the station has the
    card by the time this waits at all, and leaving the call would not end the
    cell -- only lose the answer to an image already rendered. Work that could
    give something back by stopping asks for the signal by declaring the
    parameter; see `streamed_answer`.
    """
    data, refusal = _proxy_body()
    if refusal is not None:
        return jsonify(refusal[0]), refusal[1]
    return answered_either_way(data, _run, 'generate', data,
                               label='FUSION-WORKBENCH-GENERATE')


@fusion_workbench_bp.route('/expand_t5', methods=['POST'])
def expand_t5_route():
    """Run the Surrealizer T5 expander for one prompt (standalone, editable).

    Offers the same expander the Surrealizer uses, decoupled from generation so
    the Workbench can hold the expansion constant across a controlled sweep.

    Body:    { prompt }
    Returns: { success, t5_expansion }  -- the ~200-word enrichment (expansion
             only; the caller builds t5_prompt = prompt + ' ' + expansion).
    """
    from my_app.services.t5_expansion import expand_t5
    data, refusal = _proxy_body()
    if refusal is not None:
        return jsonify(refusal[0]), refusal[1]
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return jsonify({"success": False, "error": "empty prompt"}), 400
    expansion = expand_t5(prompt)
    if not expansion:
        return jsonify({"success": False, "error": "expansion failed"}), 502
    return jsonify({"success": True, "t5_expansion": expansion})


def _research_run(kind):
    """One run of one of the four research instruments, at the research level.

    Until stage 4 of the move to ComfyUI these four answered on the GPU service
    alone, on its loopback port, which no browser reaches. Here they stand behind the
    origin every page is served from, and the level this installation runs at
    decides whether they answer at all: their operand goes to the card as sent,
    past every check of the chain, which is what `research` in
    SAFETY_LEVELS_STRICTEST_FIRST names. The level is resolved on the request's
    own thread (services/safety_level_resolver.py: off it, the resolver answers
    with the strictest level), before the run leaves for its own.
    Each takes the body its Diffusers route took (gpu_service/routes/
    diffusers_routes.py) and answers the same way, { success, image_base64, seed }.
    """
    from my_app.services.safety_level_resolver import resolve_safety_level
    data, refusal = _proxy_body()
    if refusal is not None:
        return jsonify(refusal[0]), refusal[1]
    level = resolve_safety_level()
    if level != 'research':
        return jsonify({"success": False,
                        "error": f"{kind} runs at the research level only; "
                                 f"this installation runs at {level!r}"}), 403
    return answered_either_way(data, _run, kind, data,
                               label=f'FUSION-WORKBENCH-{kind.upper()}')


@fusion_workbench_bp.route('/decomposition', methods=['POST'])
def decomposition():
    """One Decomposition run: source_prompt, and cells, each a delta of one
    prompt on one (step band, layer band, stream) at alpha; no cells is the
    plain conditioning."""
    return _research_run('decomposition')


@fusion_workbench_bp.route('/position_probe', methods=['POST'])
def position_probe():
    """One position probe: baseline_prompt, probe_prompt, probe_step_range,
    probe_block_range, probe_stream."""
    return _research_run('position_probe')


@fusion_workbench_bp.route('/delayed_kickin', methods=['POST'])
def delayed_kickin():
    """One delayed kick-in at one block: prompt_early, prompt_full,
    kickin_step, block_range? ([entry, hi]: the hook stands at the entry)."""
    return _research_run('delayed_kickin')


@fusion_workbench_bp.route('/delayed_kickin_cumulative', methods=['POST'])
def delayed_kickin_cumulative():
    """One delayed kick-in over blocks 0..up_to_block: prompt_early,
    prompt_full, kickin_step, up_to_block."""
    return _research_run('delayed_kickin_cumulative')
