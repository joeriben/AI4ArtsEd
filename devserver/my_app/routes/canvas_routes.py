"""
Canvas Workflow Routes - API endpoints for Canvas Workflow Builder

LLM model selection with a dynamic local LLM list.
The cloud half of the LLM list is the platform's chat-model list (chat_routes).

Provides:
- /api/canvas/interception-configs - List available interception configs
- /api/canvas/output-configs - List available output/generation configs
- /api/canvas/llm-models - LLM models: the local ones live, the cloud ones from the chat-model list
- /api/canvas/keep - Keep the board as a run of its own, for the favourites strip
"""
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request, Response
import json
import re

from schemas.engine.model_selector import ModelSelector
from my_app.services.canvas_recorder import CanvasRecorder, get_canvas_recorder, cleanup_canvas_recorder
from my_app.services.canvas_executor import CanvasWorkflowExecutor, as_seed
from my_app.services.pipeline_recorder import generate_run_id
from my_app.services.safety_level_resolver import resolve_safety_level
from my_app.services.streaming_response import events_with_heartbeat
import config

logger = logging.getLogger(__name__)

def _load_cloud_models_from_matrix():
    """
    The cloud models a canvas node can pick: the platform's chat-model list
    (chat_routes._cloud_chat_models_from_matrix -- the register's models over
    every provider with a key, one route per model, conform routes first), in
    the shape the canvas reads: id, name, provider, dsgvo. Until 2026-09-12
    this read every preset's role cells for itself, key or no key, and offered
    routes the installation could not take.

    Conformity is not derived here. It is a property of the service, and the
    platform has one place that records it -- flag plus the grounds it was set
    on, three-valued: True, False, or None for "nothing recorded".
    """
    from my_app.routes.chat_routes import _cloud_chat_models_from_matrix, _load_llm_matrix
    from my_app.routes.settings_routes import _recorded_conformity
    from my_app.services.llm_providers import provider as provider_entry, split_provider

    matrix = _load_llm_matrix()
    presets = matrix.get('llm_presets', {}) if isinstance(matrix, dict) else {}

    cloud_models = []
    for m in _cloud_chat_models_from_matrix(matrix):
        provider, _path = split_provider(m['id'])
        label = ((provider_entry(provider) or {}).get('label')
                 or (presets.get(provider) or {}).get('label') or provider)
        cloud_models.append({
            'id': m['id'],
            'name': f"{m['register']} ({label})",
            'provider': provider,
            'dsgvo': _recorded_conformity(provider, presets),
        })
    return cloud_models

# ============================================================================
# RANDOM PROMPT PRESETS
# ============================================================================


# Create blueprint
canvas_bp = Blueprint('canvas', __name__)

# Batch abort support
BATCH_ABORT_FLAGS = {}  # {batch_id: True/False}


def _get_schemas_path() -> Path:
    """Get the schemas directory path"""
    # Navigate from routes to devserver/schemas
    current_file = Path(__file__)
    devserver_path = current_file.parent.parent.parent  # my_app/routes -> my_app -> devserver
    return devserver_path / "schemas"


def _load_config_summaries(config_type: str) -> list:
    """
    Load config summaries from configs directory

    Args:
        config_type: 'interception' or 'output'

    Returns:
        List of config summary dicts with id, name, description, icon, color, etc.
    """
    schemas_path = _get_schemas_path()
    configs_path = schemas_path / "configs" / config_type

    if not configs_path.exists():
        logger.warning(f"Config path not found: {configs_path}")
        return []

    summaries = []

    for config_file in sorted(configs_path.glob("*.json")):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract summary info
            config_id = config_file.stem

            # Get name (multilingual dict or string)
            name_data = data.get('name', config_id)
            if isinstance(name_data, dict):
                name = name_data
            else:
                name = {'en': str(name_data), 'de': str(name_data)}

            # Get description (multilingual dict or string)
            desc_data = data.get('description', '')
            if isinstance(desc_data, dict):
                description = desc_data
            else:
                description = {'en': str(desc_data), 'de': str(desc_data)}

            # Get display properties
            display = data.get('display', {})
            icon = display.get('icon', '📦')
            color = display.get('color', '#64748b')

            # Build summary
            summary = {
                'id': config_id,
                'name': name,
                'description': description,
                'icon': icon,
                'color': color
            }

            # Add type-specific fields
            if config_type == 'interception':
                summary['category'] = data.get('category', {}).get('en', 'General')
            elif config_type == 'output':
                media_prefs = data.get('media_preferences', {})
                summary['mediaType'] = media_prefs.get('default_output', 'image')
                meta = data.get('meta', {})
                summary['backend'] = meta.get('backend', 'unknown')

            summaries.append(summary)

        except Exception as e:
            logger.error(f"Error loading config {config_file}: {e}")
            continue

    # Sort output configs by media type (image, video, audio, other) then alphabetically
    if config_type == 'output':
        media_type_order = {'image': 0, 'video': 1, 'audio': 2, 'music': 2}
        summaries.sort(key=lambda x: (
            media_type_order.get(x.get('mediaType', ''), 999),  # Media type priority
            x.get('name', {}).get('en', x.get('id', '')).lower()  # Alphabetically by EN name
        ))

    logger.info(f"Loaded {len(summaries)} {config_type} configs")
    return summaries


@canvas_bp.route('/api/canvas/llm-models', methods=['GET'])
def get_llm_models():
    """
    Get available LLM models for Canvas nodes.

    Sources (all dynamic, no hardcoded model lists):
    1. Local models (queried live from LLM backend)
    2. Cloud models: the platform's chat-model list (chat_routes._cloud_chat_models_from_matrix)
    3. Configured default model (injected if not already in list)
    """
    selector = ModelSelector()
    models = []
    local_count = 0

    # Get default model from settings (Stage 2 Interception Model)
    # Note: config value already includes provider prefix (e.g., "local/qwen3:4b")
    default_model_id = config.STAGE2_INTERCEPTION_MODEL

    # 1. Dynamic local models (all locally installed models)
    try:
        local_models = selector.get_local_models()
        for model_name in local_models:
            model_id = f"local/{model_name}"
            models.append({
                'id': model_id,
                'name': f"{model_name} (Lokal)",
                'provider': 'local',
                'tier': 'local',
                'dsgvoCompliant': True,
                'isDefault': model_id == default_model_id
            })
            local_count += 1
        logger.info(f"[Canvas LLM] Loaded {local_count} local models")
    except Exception as e:
        logger.warning(f"[Canvas LLM] Failed to load local models: {e}")

    # 2. Cloud models: the platform's chat-model list, in the canvas's shape
    cloud_models = _load_cloud_models_from_matrix()
    seen_ids = {m['id'] for m in models}  # skip local duplicates
    cloud_count = 0
    for cm in cloud_models:
        if cm['id'] not in seen_ids:
            seen_ids.add(cm['id'])
            models.append({
                'id': cm['id'],
                'name': cm['name'],
                'provider': cm['provider'],
                'tier': 'cloud',
                'dsgvoCompliant': cm['dsgvo'],
                'isDefault': cm['id'] == default_model_id
            })
            cloud_count += 1

    # 3. Ensure the configured default is always present (even if not in matrix)
    if default_model_id and not any(m['isDefault'] for m in models):
        parts = default_model_id.split('/', 1)
        provider_prefix = parts[0] if len(parts) == 2 else 'unknown'
        model_name = parts[1] if len(parts) == 2 else default_model_id
        # Same two lookups as the settings page: which service the string reaches,
        # then what the platform records about that service.
        from my_app.routes.settings_routes import _recorded_conformity, _service_reached
        models.append({
            'id': default_model_id,
            'name': f"{model_name} ({provider_prefix.title()})",
            'provider': provider_prefix,
            'tier': 'configured',
            'dsgvoCompliant': _recorded_conformity(_service_reached(default_model_id)),
            'isDefault': True
        })
        logger.info(f"[Canvas LLM] Injected configured default: {default_model_id}")

    logger.info(f"[Canvas LLM] Returning {len(models)} total models ({local_count} local + {cloud_count} cloud)")

    return jsonify({
        'status': 'success',
        'models': models,
        'count': len(models),
        'localCount': local_count
    })


# ============================================================================
# VISION MODELS
# ============================================================================

# Vision-capable local model patterns (checked against model names)
# Comprehensive list - matches "vision" or "vl" in name
VISION_CAPABLE_PATTERNS = [
    # Llama Vision
    'llama3.2-vision',
    'llama-vision',
    # LLaVA family
    'llava',
    'bakllava',
    'llava-llama3',
    # Qwen VL family (qwen-vl, qwen2-vl, qwen3-vl, etc.)
    'qwen-vl',
    'qwen2-vl',
    'qwen3-vl',
    # Other vision models
    'moondream',
    'minicpm-v',
    'cogvlm',
    'internvl',
    # Generic patterns - any model with "vision" or "-vl" in name
    'vision',
    '-vl',
]


@canvas_bp.route('/api/canvas/vision-models', methods=['GET'])
def get_vision_models():
    """
    Get available Vision models for image_evaluation nodes.

    Vision models are ALWAYS local (per Model Matrix architecture):
    - Run on local LLM backend
    - VRAM-dependent
    - DSGVO-compliant by default (no cloud APIs)

    Returns list of vision-capable local models.
    """
    selector = ModelSelector()
    models = []

    # Get default vision model from settings
    default_model_id = config.IMAGE_ANALYSIS_MODEL

    try:
        local_models = selector.get_local_models()
        for model_name in local_models:
            # Check if model is vision-capable
            base_name = model_name.split(':')[0].lower()
            is_vision = any(pattern in base_name for pattern in VISION_CAPABLE_PATTERNS)

            if is_vision:
                model_id = f"local/{model_name}"
                models.append({
                    'id': model_id,
                    'name': f"{model_name} (Vision)",
                    'provider': 'local',
                    'dsgvoCompliant': True,
                    'isDefault': model_id == default_model_id
                })

        logger.info(f"[Canvas Vision] Found {len(models)} vision models")

    except Exception as e:
        logger.warning(f"[Canvas Vision] Failed to load models: {e}")
        # Fallback to configured default
        models.append({
            'id': config.IMAGE_ANALYSIS_MODEL,
            'name': 'Default Vision Model',
            'provider': 'local',
            'dsgvoCompliant': True,
            'isDefault': True
        })

    return jsonify({
        'status': 'success',
        'models': models,
        'count': len(models)
    })


@canvas_bp.route('/api/canvas/output-configs', methods=['GET'])
def get_output_configs():
    """
    Get list of available output/generation configs

    Returns:
        {
            "configs": [
                {
                    "id": "sd35_large",
                    "name": {"en": "SD 3.5 Large", "de": "SD 3.5 Large"},
                    "description": {...},
                    "icon": "🎨",
                    "color": "#10b981",
                    "mediaType": "image",
                    "backend": "comfyui"
                },
                ...
            ]
        }
    """
    try:
        configs = _load_config_summaries('output')
        return jsonify({
            'status': 'success',
            'configs': configs,
            'count': len(configs)
        })
    except Exception as e:
        logger.error(f"Error loading output configs: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'configs': []
        }), 500


def _canvas_presets_dir() -> Path:
    """Where the ready-made workflows stand: schemas/canvas_presets."""
    return _get_schemas_path() / "canvas_presets"


@canvas_bp.route('/api/canvas/presets', methods=['GET'])
def list_canvas_presets():
    """The ready-made workflows the Canvas offers under "New".

    Each is a `.atcanvas` file of its own in schemas/canvas_presets, the same
    format a person exports, with a `preset` block that says where it hangs in
    the ring (`kind`: basic forms or explorations, `order`), what it yields
    (`medium`) and the i18n keys of its name and description. The surface reads
    them through the reader the import uses, so a preset is a workflow like any
    other; what it names -- perspectives, models, lineups, frames -- is resolved
    there when it is opened, against what this installation holds then.

    A file that cannot be read is left out and logged, not answered with an
    error: the other presets are still worth offering. That every file reads,
    and that everything it names exists, is tests/test_canvas_presets.py's.

    Resona's saved strategies (services/canvas_workflow_store.py) are something
    else and stay where they are.
    """
    presets = []
    for path in sorted(_canvas_presets_dir().glob('*.atcanvas')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as e:
            logger.error(f"[Canvas] Preset {path.name} unreadable: {e}")
            continue
        if not isinstance(data, dict) or not isinstance(data.get('preset'), dict):
            logger.error(f"[Canvas] Preset {path.name} carries no preset block")
            continue
        presets.append(data)
    presets.sort(key=lambda d: (d['preset'].get('kind') != 'basic', d['preset'].get('order', 0)))
    return jsonify({'status': 'success', 'presets': presets})



# The name the empty workflow carried until 2026-10-01 (frontend
# lib/canvasFile.ts). Nobody gave it, so it is no name.
_LEGACY_DEFAULT_NAME = 'New Workflow'

# A device id is a folder name in the run store; only the alphabet the
# frontend's ids are made of (a UUID and a date) is taken as one.
_DEVICE_ID_RE = re.compile(r'[A-Za-z0-9_-]{1,128}')


def workflow_name(workflow) -> str:
    """The name somebody gave the workflow, or an empty string."""
    name = workflow.get('name') if isinstance(workflow, dict) else None
    name = name.strip() if isinstance(name, str) else ''
    return '' if name == _LEGACY_DEFAULT_NAME else name


def _workflow_prompt(workflow: dict) -> str:
    """The prompt in the workflow's first input node that has one."""
    for node in workflow.get('nodes') or []:
        if not isinstance(node, dict) or node.get('type') != 'input':
            continue
        text = node.get('promptText')
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ''


def board_as_run(nodes: list, connections: list,
                 prompt_override=None, run_seed=None, run_index=None) -> tuple:
    """The board as one batch run ran it, for that run's workflow.json.

    A kept output reopens the board of its run in the Canvas, so the board has
    to say what the run did, in the Canvas's own nodes, and still vary when it
    is run as a batch again:
    - prompt mode: every input node carries the run's prompt, as the executor
      gives it to them (CanvasWorkflowExecutor._find_source_nodes);
    - a "Batch (+1)" seed node rendered its base plus the run's place, which
      becomes its base;
    - a run seed: a generation node with no seed node of its own was rendered
      with it (CanvasWorkflowExecutor, "Use run_seed if no connected seed
      node"), so it gets a "Batch (+1)" seed node with that base, wired as
      Resona's authoring wires one (canvas_graph_authoring.validate_and_expand).
      Alone it renders that seed; in a batch again it counts up from it.
    The executor itself still runs the board as given.
    """
    def as_run(n):
        if not isinstance(n, dict):
            return n
        if prompt_override is not None and n.get('type') == 'input':
            return {**n, 'promptText': prompt_override}
        if n.get('type') == 'seed' and n.get('seedMode') == 'increment':
            # Read as the executor reads it (as_seed). A base it cannot read
            # gave the generation no seed, which then rendered the run seed:
            # that becomes the base. Without a run seed it rendered a random
            # one, and the node stays as it was.
            base = as_seed(n.get('seedBase', 0))
            if base is None:
                return n if run_seed is None else {**n, 'seedBase': run_seed}
            return {**n, 'seedBase': base + run_index} if run_index else n
        return n

    run_nodes = [as_run(n) for n in nodes]
    run_connections = list(connections)
    if run_seed is None:
        return run_nodes, run_connections
    ids = {n.get('id') for n in run_nodes if isinstance(n, dict)}
    seeds = {n.get('id') for n in run_nodes if isinstance(n, dict) and n.get('type') == 'seed'}
    seeded = {c.get('targetId') for c in connections
              if isinstance(c, dict) and c.get('sourceId') in seeds}
    for n in list(run_nodes):
        if not isinstance(n, dict) or n.get('type') != 'generation' or n.get('id') in seeded:
            continue
        sid, k = f"{n['id']}__seed", 2
        while sid in ids:
            sid, k = f"{n['id']}__seed_{k}", k + 1
        ids.add(sid)
        x, y = n.get('x'), n.get('y')
        run_nodes.append({
            'id': sid, 'type': 'seed', 'seedMode': 'increment', 'seedBase': run_seed,
            'x': max(x - 220, 0) if isinstance(x, (int, float)) else 0,
            'y': (y + 160) if isinstance(y, (int, float)) else 0,
        })
        run_connections.append({'sourceId': sid, 'targetId': n['id'], 'label': None})
    return run_nodes, run_connections


@canvas_bp.route('/api/canvas/keep', methods=['POST'])
def keep_workflow():
    """
    Keep the board as it stands, as a run of its own.

    A favourite is a run (favorites_routes), and a board that has not run, or
    has been changed since, has none that holds it. This one holds nothing but
    the workflow, as the entity `canvas`; the favourites strip shows it, opens
    it back into the Canvas and saves it as a `.atcanvas` file.

    Body: {workflow: {name?, nodes: [...], connections: [...]}, device_id?}
    Returns 201 {status, run_id}; 400 when the body holds no workflow.
    """
    from config import JSON_STORAGE_DIR
    from my_app.services.pipeline_recorder import LivePipelineRecorder

    data = request.get_json(silent=True)
    workflow = data.get('workflow') if isinstance(data, dict) else None
    if (not isinstance(workflow, dict)
            or not isinstance(workflow.get('nodes'), list)
            or not isinstance(workflow.get('connections', []), list)):
        return jsonify({'status': 'error', 'error': 'workflow with nodes and connections expected'}), 400

    device_id = data.get('device_id')
    if device_id is not None and not (isinstance(device_id, str) and _DEVICE_ID_RE.fullmatch(device_id)):
        return jsonify({'status': 'error', 'error': 'device_id malformed'}), 400

    name = workflow_name(workflow)
    run_id = generate_run_id(suffix='canvasfile')
    recorder = LivePipelineRecorder(
        run_id=run_id,
        config_name='canvas_workflow',
        safety_level=resolve_safety_level(),
        device_id=device_id,
        base_path=JSON_STORAGE_DIR,
    )
    recorder.save_entity('canvas', workflow, metadata={
        'name': name,
        # What the strip writes on the plate: the name, else the prompt the
        # board starts from.
        'label': name or _workflow_prompt(workflow),
        'node_count': len(workflow['nodes']),
    })
    recorder.mark_complete()
    logger.info(f"[Canvas] Kept workflow {name!r} as {run_id}")
    return jsonify({'status': 'success', 'run_id': run_id}), 201



@canvas_bp.route('/api/canvas/execute-stream', methods=['POST'])
def execute_workflow_stream():
    """
    Start a canvas workflow run and stream its SSE events.

    Architecture (canvas-partial-recovery): the run no longer lives inside this
    request generator. It is started as a background job (canvas_run_service),
    which drives the UNCHANGED CanvasWorkflowExecutor on a daemon thread and
    persists every event to events.jsonl + a status.json in the recorder run
    folder. This request is a TAIL over that job's event stream. If the client
    reconnects (GET variant below with ?after=<n>), it replays what it missed —
    lossless within a live process. If the backend dies mid-run, the finished
    nodes are already on disk and reachable via /api/media/image/<run_id> and
    /api/canvas/partial/<run_id>; the run is marked `interrupted` on next start.

    Events (unchanged contract for existing consumers; run_started is additive):
    - run_started: {run_id} - FIRST event, before any node; lets the client
                              store the run id so it can reconnect / recover.
    - started: {total_nodes: N} - Execution begins (back-compat).
    - progress: {node_id, node_type, status, message} - Node starts executing.
    - node_complete: {node_id, node_type, output_preview} - Node finished.
    - complete: {results, collectorOutput, executionOrder, exportPath, run_id}.
    - error: {message} - Error occurred.
    """
    from my_app.services import canvas_run_service

    try:
        data = request.get_json()
        if not data:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'message': 'JSON request expected'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        nodes = data.get('nodes', [])
        connections = data.get('connections', [])

        if not nodes:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'message': 'No nodes provided'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        device_id = data.get('device_id')
        logger.info(f"[Canvas Stream] Starting job with {len(nodes)} nodes, {len(connections)} connections")

        # Start the background job; get the run_id back BEFORE any node runs.
        from flask import current_app
        app = current_app._get_current_object()
        # Resolved HERE, while the session is still in reach: the run itself
        # executes in a worker thread that cannot see it.
        run_safety_level = resolve_safety_level()
        run_id = canvas_run_service.start_run(
            nodes=nodes, connections=connections, device_id=device_id, app=app,
            safety_level=run_safety_level,
            lang=str(data.get('lang') or '').strip() or None,
            name=workflow_name(data.get('workflow')),
        )

        def _tail(client_gone):
            """The run's events, with the leaving signal reaching the tail.

            Handed over as a FUNCTION rather than as a generator already made,
            which is how a source under this transport asks to be told that its
            reader has gone. The RUN is not cancelled by that -- it is a
            background job, it finishes and saves what it made, and a client
            that comes back reads every event of it from events.jsonl. Only the
            following ends, instead of sitting on the run registry's lock for
            five minutes for nobody.
            """
            return canvas_run_service.iter_events(run_id, after=-1,
                                                  client_gone=client_gone)

        def generate():
            # run_started FIRST so the client can persist the run id immediately.
            yield f"event: run_started\ndata: {json.dumps({'run_id': run_id})}\n\n"
            # Back-compat: existing consumers key off `started`/total_nodes.
            yield f"event: started\ndata: {json.dumps({'total_nodes': len(nodes)})}\n\n"
            # A node waiting at the admission gate for the card emits
            # nothing, for as long as GPU_ADMISSION_ACQUIRE_TIMEOUT_S lets
            # it wait, and the tunnel in front of this server ends a
            # proxied request that has been silent for about a hundred
            # seconds. What goes out in between is an SSE comment: no
            # event, no field, nothing a reader of `data:` frames ever
            # sees. The events are untouched -- `frame` writes exactly the
            # line this loop wrote, and in the same order.
            try:
                yield from events_with_heartbeat(
                    _tail,
                    label='CANVAS-RUN-STREAM',
                    # id: carries the running event index for lossless reconnect.
                    frame=lambda rec: f"id: {rec['_i']}\nevent: {rec['type']}\ndata: {json.dumps(rec['data'])}\n\n",
                )
            except Exception as e:
                # The status line went out with the first frame, so a failure
                # from here on can only travel as this route's own error event.
                # Raised out of the generator instead, it leaves the client a
                # 200 with a torn, empty body and no word about why.
                logger.error(f"[Canvas Stream] {run_id}: {e}")
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        return Response(generate(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        })

    except Exception as e:
        err_msg = str(e)
        logger.error(f"[Canvas Stream] Setup error: {err_msg}")
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'message': err_msg})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')


# Reconnect endpoint: re-attach to a still-running (or just-finished) job and
# replay everything after a given event index. This is what makes a torn live
# stream lossless — the client keeps its run_id and picks up where it dropped.
_RUN_ID_RE = re.compile(r'^run_[A-Za-z0-9_]+$')


@canvas_bp.route('/api/canvas/execute-stream/<run_id>', methods=['GET'])
def reconnect_workflow_stream(run_id: str):
    """Re-attach to an in-flight canvas run and tail its events after ?after=<n>
    (or the Last-Event-ID header). Same SSE frame format as the POST route."""
    from my_app.services import canvas_run_service

    if not _RUN_ID_RE.match(run_id or ''):
        def bad():
            yield f"event: error\ndata: {json.dumps({'message': 'invalid run_id'})}\n\n"
        return Response(bad(), mimetype='text/event-stream')

    # Resume point: ?after=<n> wins; else Last-Event-ID; else from the start.
    after = request.args.get('after', type=int)
    if after is None:
        leid = request.headers.get('Last-Event-ID')
        try:
            after = int(leid) if leid is not None else -1
        except ValueError:
            after = -1

    def _tail(client_gone):
        """As in the POST route above: the tail is told when its reader leaves,
        and the run behind it carries on regardless."""
        return canvas_run_service.iter_events(run_id, after=after,
                                              client_gone=client_gone)

    def generate():
        yield f"event: run_started\ndata: {json.dumps({'run_id': run_id})}\n\n"
        # The same breathing as the POST route above. This is the path a
        # client reaches after it has already lost one stream, so it is the
        # one place where a second silent gap must not cost it the run.
        try:
            yield from events_with_heartbeat(
                _tail,
                label='CANVAS-RUN-RECONNECT',
                frame=lambda rec: f"id: {rec['_i']}\nevent: {rec['type']}\ndata: {json.dumps(rec['data'])}\n\n",
            )
        except Exception as e:
            logger.error(f"[Canvas Reconnect] {run_id}: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })


@canvas_bp.route('/api/canvas/runs/<run_id>/status', methods=['GET'])
def get_canvas_run_status(run_id: str):
    """Cheap status snapshot for polling: state (running|complete|error|
    interrupted|unknown) + last event index. Reads the live registry, then
    status.json on disk, then 'unknown'."""
    from my_app.services import canvas_run_service
    if not _RUN_ID_RE.match(run_id or ''):
        return jsonify({'error': 'invalid run_id'}), 400
    return jsonify(canvas_run_service.get_status(run_id))


@canvas_bp.route('/api/canvas/partial/<run_id>', methods=['GET'])
def get_canvas_partial(run_id: str):
    """Partial-result recovery for a torn run. Reads the finished outputs already
    persisted in the run's final/ folder and returns them as items with URLs that
    reuse the SAME media serve path completed runs use (/api/media/image/...).

    Response: {run_id, state, items: [{kind, url, node_label?, index}],
               prompts_pending}
      state: partial   - some but not all expected outputs are present
             complete  - the run finished (completed_at set)
             unknown   - no such run on disk
    """
    from my_app.services import canvas_run_service
    from my_app.routes.media_routes import _find_entities_by_type
    from my_app.services.pipeline_recorder import load_recorder
    from config import JSON_STORAGE_DIR

    # Strict sanitisation: only the run_ name shape; rules out path traversal.
    if not _RUN_ID_RE.match(run_id or ''):
        return jsonify({'error': 'invalid run_id'}), 400

    recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
    if recorder is None:
        return jsonify({'run_id': run_id, 'state': 'unknown',
                        'items': [], 'prompts_pending': 0}), 404

    entities = recorder.metadata.get('entities', [])
    image_entities = _find_entities_by_type(entities, 'image')

    items = []
    for idx, entity in enumerate(image_entities):
        filename = entity.get('filename')
        if not filename:
            continue
        file_path = recorder.final_folder / filename
        if not file_path.exists():
            continue
        meta = entity.get('metadata', {}) or {}
        # Only surface a label if it is trivially derivable; else index suffices.
        node_label = meta.get('node_title') or meta.get('config_id')
        item = {
            'kind': 'image',
            'url': f'/api/media/image/{run_id}/{idx}',  # same serve path as complete runs
            'index': idx,
        }
        if node_label and node_label != 'unknown':
            item['node_label'] = node_label
        items.append(item)

    # How many generations were expected but haven't landed yet. Best effort:
    # count generation nodes in workflow.json vs. images present.
    prompts_pending = 0
    try:
        wf_path = recorder.run_folder / 'workflow.json'
        if wf_path.exists():
            wf = json.loads(wf_path.read_text(encoding='utf-8'))
            gen_nodes = [n for n in wf.get('nodes', []) if n.get('type') == 'generation']
            prompts_pending = max(0, len(gen_nodes) - len(items))
    except Exception:
        prompts_pending = 0

    completed = recorder.metadata.get('completed_at') is not None
    # Cross-check the job registry: an interrupted/errored job is still 'partial'
    # from the recovery standpoint (finished pieces + a hard stop).
    state = 'complete' if completed else 'partial'
    _ = canvas_run_service  # (registry state is exposed via the status route)

    return jsonify({
        'run_id': run_id,
        'state': state,
        'items': items,
        'prompts_pending': prompts_pending,
    })


@canvas_bp.route('/api/interception/<preset_id>', methods=['GET'])
def get_interception_config(preset_id: str):
    """
    Get a single interception config by ID

    Used by the Canvas Interception node to fetch the context prompt
    when a preset is selected.

    Args:
        preset_id: The interception config ID (e.g., 'bauhaus', 'overdrive')

    Returns:
        Full config including context field with en/de translations
    """
    try:
        schemas_path = _get_schemas_path()
        config_path = schemas_path / "configs" / "interception" / f"{preset_id}.json"

        if not config_path.exists():
            return jsonify({
                'status': 'error',
                'error': f'Interception config not found: {preset_id}'
            }), 404

        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return jsonify({
            'status': 'success',
            'id': preset_id,
            'name': data.get('name', {}),
            'description': data.get('description', {}),
            'context': data.get('context', {}),
            'parameters': data.get('parameters', {}),
            'display': data.get('display', {})
        })

    except Exception as e:
        logger.error(f"Error loading interception config {preset_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@canvas_bp.route('/api/canvas/abort-batch', methods=['POST'])
def abort_batch():
    """
    Abort a running batch execution.

    Batch abort endpoint for workshop safety.

    Request body:
    {
        "batch_id": "batch_..."
    }
    """
    try:
        data = request.get_json()
        batch_id = data.get('batch_id') if data else None

        if not batch_id:
            return jsonify({'success': False, 'error': 'batch_id required'}), 400

        if batch_id in BATCH_ABORT_FLAGS:
            BATCH_ABORT_FLAGS[batch_id] = True
            logger.info(f"[Canvas Batch] Abort requested for {batch_id}")
            return jsonify({'success': True, 'message': f'Abort requested for {batch_id}'})
        else:
            return jsonify({'success': False, 'error': f'Batch {batch_id} not found or already completed'}), 404

    except Exception as e:
        logger.error(f"[Canvas Batch] Abort error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@canvas_bp.route('/api/canvas/execute-batch', methods=['POST'])
def execute_batch():
    """
    Execute a canvas workflow multiple times with SSE streaming.

    Batch execution for research data production.
    Uses CanvasWorkflowExecutor and supports abort.

    Request body:
    {
        "workflow": {"nodes": [...], "connections": [...]},
        "count": 3,                    // Number of runs (for seed variance)
        "prompts": ["prompt1", ...],   // OR list of prompts (1 prompt = 1 run)
        "device_id": "...",            // Optional device identifier
        "base_seed": 42                // Optional base seed for reproducibility
    }

    Events:
    - batch_started: {batch_id, total_runs}
    - run_start: {run_index, total_runs, run_id}
    - progress: {run_index, node_id, node_type, status, message}
    - run_complete: {run_index, run_id, export_path, results}
    - batch_complete: {batch_id, total_runs, export_paths}
    - error: {message, run_index}
    """
    from schemas.engine.prompt_interception_engine import PromptInterceptionEngine, PromptInterceptionRequest
    import time

    # Resolved before the generator starts: Flask pops the request context when
    # this view returns, and the batch runs inside the generator.
    batch_safety_level = resolve_safety_level()
    import uuid

    try:
        data = request.get_json()
        if not data:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'message': 'JSON request expected'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        workflow = data.get('workflow', {})
        nodes = workflow.get('nodes', [])
        connections = workflow.get('connections', [])
        batch_name = workflow_name(workflow)

        if not nodes:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'message': 'No nodes in workflow'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        # Determine batch mode: prompts list OR count
        prompts = data.get('prompts')  # List of input prompts
        count = data.get('count', 1)   # Number of runs (seed variance)
        device_id = data.get('device_id')
        # Optional base seed. A whole number or nothing: a cleared field in the
        # batch dialog arrives as '' and stopped the batch at its first run.
        base_seed = as_seed(data.get('base_seed'))

        if prompts and len(prompts) > 0:
            total_runs = len(prompts)
            batch_mode = 'prompts'
        else:
            total_runs = count
            batch_mode = 'seed_variance'

        batch_id = generate_run_id(suffix="canvas_batch")

        def generate(client_gone):
            """Generator that yields SSE events for batch execution using CanvasWorkflowExecutor

            `client_gone` is the transport's leaving signal (services/
            streaming_response.py). It is read at the event boundary inside the
            run below -- the one place a closed tab used to be noticed.
            """
            try:
                # Initialize abort flag
                BATCH_ABORT_FLAGS[batch_id] = False

                logger.info(f"[Canvas Batch] Starting batch {batch_id}: {total_runs} runs ({batch_mode})")

                # Send batch_started event
                yield f"event: batch_started\ndata: {json.dumps({'batch_id': batch_id, 'total_runs': total_runs, 'batch_mode': batch_mode})}\n\n"

                export_paths = []
                engine = PromptInterceptionEngine()

                for run_index in range(total_runs):
                    # The signal, read where the next run would otherwise
                    # begin. Inside the loop over `execute_with_events()`
                    # below it is reached only once a run has something to
                    # say: a departure noticed BETWEEN two runs had already
                    # made the next run's recorder and its two directories,
                    # and a run whose executor yields nothing at all -- 'No
                    # source nodes found' -- was never checked at all, so
                    # every remaining run of a malformed batch executed for a
                    # reader that had gone.
                    if client_gone.is_set():
                        logger.info(
                            f"[Canvas Batch] Batch {batch_id}: reader gone "
                            f"before run {run_index}, remaining runs dropped")
                        if batch_id in BATCH_ABORT_FLAGS:
                            del BATCH_ABORT_FLAGS[batch_id]
                        return
                    # Check abort flag before each run
                    if BATCH_ABORT_FLAGS.get(batch_id):
                        logger.info(f"[Canvas Batch] Batch {batch_id} aborted at run {run_index}")
                        yield f"event: batch_aborted\ndata: {json.dumps({'batch_id': batch_id, 'aborted_at_run': run_index, 'completed_runs': len(export_paths)})}\n\n"
                        break

                    run_id = f"{batch_id}_{run_index + 1:03d}"

                    # Get prompt override for this run (if using prompts mode)
                    prompt_override = prompts[run_index] if batch_mode == 'prompts' else None

                    # Calculate seed for this run (if using seed variance)
                    run_seed = None
                    if base_seed is not None:
                        run_seed = base_seed + run_index

                    yield f"event: run_start\ndata: {json.dumps({'run_index': run_index, 'total_runs': total_runs, 'run_id': run_id, 'seed': run_seed})}\n\n"

                    try:
                        # Initialize recorder for this run, with the board as
                        # THIS run ran it (board_as_run): a kept output reopens
                        # it in the Canvas.
                        run_nodes, run_connections = board_as_run(
                            nodes, connections, prompt_override, run_seed, run_index)
                        recorder = get_canvas_recorder(
                            run_id=run_id,
                            workflow={'name': batch_name, 'nodes': run_nodes,
                                      'connections': run_connections},
                            device_id=device_id,
                            batch_id=batch_id,
                            batch_index=run_index
                        )

                        # Create executor for this run - use recorder's device_id
                        executor = CanvasWorkflowExecutor(
                            nodes=nodes,
                            connections=connections,
                            recorder=recorder,
                            run_id=run_id,
                            engine=engine,
                            prompt_override=prompt_override,
                            run_seed=run_seed,
                            run_index=run_index,
                            device_id=recorder.device_id,  # Use recorder's device_id
                            safety_level=batch_safety_level,
                            lang=str(data.get('lang') or '').strip() or None,
                        )

                        # Execute and yield events with run_index context
                        for event_type, event_data in executor.execute_with_events():
                            # Where the GeneratorExit of a closed tab used
                            # to land. Until this stream was carried by the
                            # shared transport, abandoning the response
                            # raised it at the `yield` below and the batch
                            # stopped right here: the node in flight
                            # finished, the remaining runs never started.
                            # Read at the same boundary, the signal restores
                            # exactly that -- and it has to, because every
                            # remaining run takes a GPU lease and renders
                            # onto the shared card for nobody.
                            # BATCH_ABORT_FLAGS cannot stand in for it:
                            # nothing sets the flag on a disconnect, and the
                            # batch id lived only in the tab that closed.
                            if client_gone.is_set():
                                logger.info(
                                    f"[Canvas Batch] Batch {batch_id}: reader gone "
                                    f"during run {run_index}, remaining runs dropped")
                                # Exactly what the abort path below does. An
                                # abandoned batch used to leave both entries
                                # standing for the life of the process: its
                                # flag in BATCH_ABORT_FLAGS, keyed by a batch
                                # id nothing will ever ask about again, and
                                # the in-flight run in the recorder registry.
                                cleanup_canvas_recorder(run_id)
                                if batch_id in BATCH_ABORT_FLAGS:
                                    del BATCH_ABORT_FLAGS[batch_id]
                                return
                            # Check abort during execution
                            if BATCH_ABORT_FLAGS.get(batch_id):
                                logger.info(f"[Canvas Batch] Batch {batch_id} aborted during run {run_index}")
                                cleanup_canvas_recorder(run_id)
                                yield f"event: batch_aborted\ndata: {json.dumps({'batch_id': batch_id, 'aborted_at_run': run_index, 'completed_runs': len(export_paths)})}\n\n"
                                # Clean up abort flag
                                if batch_id in BATCH_ABORT_FLAGS:
                                    del BATCH_ABORT_FLAGS[batch_id]
                                return

                            # Add run_index to event data
                            event_data['run_index'] = run_index
                            yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"

                        # Get result
                        run_result = executor.get_result()

                        if run_result.get('success'):
                            # Mark complete and cleanup
                            recorder.mark_complete()
                            export_path = str(recorder.run_folder)
                            export_paths.append(export_path)
                            cleanup_canvas_recorder(run_id)

                            yield f"event: run_complete\ndata: {json.dumps({'run_index': run_index, 'run_id': run_id, 'export_path': export_path, 'success': True})}\n\n"
                        else:
                            cleanup_canvas_recorder(run_id)
                            yield f"event: run_error\ndata: {json.dumps({'run_index': run_index, 'run_id': run_id, 'error': run_result.get('error', 'Unknown error')})}\n\n"

                    except Exception as e:
                        logger.error(f"[Canvas Batch] Run {run_index} failed: {e}")
                        import traceback
                        traceback.print_exc()
                        cleanup_canvas_recorder(run_id)
                        yield f"event: run_error\ndata: {json.dumps({'run_index': run_index, 'run_id': run_id, 'error': str(e)})}\n\n"

                # Clean up abort flag
                if batch_id in BATCH_ABORT_FLAGS:
                    del BATCH_ABORT_FLAGS[batch_id]

                # Send batch_complete event (only if not aborted)
                if not BATCH_ABORT_FLAGS.get(batch_id):
                    yield f"event: batch_complete\ndata: {json.dumps({'batch_id': batch_id, 'total_runs': total_runs, 'completed_runs': len(export_paths), 'export_paths': export_paths})}\n\n"
                    logger.info(f"[Canvas Batch] Batch {batch_id} complete: {len(export_paths)} successful runs")

            except Exception as e:
                logger.error(f"[Canvas Batch] Fatal error: {e}")
                import traceback
                traceback.print_exc()
                # Clean up abort flag on error
                if batch_id in BATCH_ABORT_FLAGS:
                    del BATCH_ABORT_FLAGS[batch_id]
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        def _breathing_frames():
            """The frames above, over a connection that keeps breathing.

            A node waiting at the admission gate for the card produces no
            event for as long as that wait lasts, and a batch waits once
            per run. `frame` is the identity: every frame written above
            goes on the wire byte for byte, and what fills the gaps is an
            SSE comment, which reaches no consumer as an event.

            The work itself stays in `generate` above, under the name the
            safety-coverage census knows it by. It is handed over as the
            FUNCTION, not as a generator already made, so that the transport
            passes it the leaving signal it asks for.
            """
            try:
                yield from events_with_heartbeat(
                    generate, label='CANVAS-BATCH', frame=lambda s: s,
                )
            except Exception as e:
                # `generate` turns its own failures into an error event; what
                # reaches here is what the transport itself could not carry.
                # The status line is long gone, so this is the only way left to
                # say so instead of tearing the body.
                logger.error(f"[Canvas Batch] Batch {batch_id}: {e}")
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        return Response(_breathing_frames(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        })

    except Exception as e:
        err_msg = str(e)
        logger.error(f"[Canvas Batch] Setup error: {err_msg}")
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'message': err_msg})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')


