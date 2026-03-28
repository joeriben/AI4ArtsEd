"""
Canvas Workflow Routes - API endpoints for Canvas Workflow Builder

Session 129: Phase 2 Implementation
Session 133: Curated LLM model selection + dynamic local LLM

Provides:
- /api/canvas/interception-configs - List available interception configs
- /api/canvas/output-configs - List available output/generation configs
- /api/canvas/llm-models - Curated LLM selection + dynamic local LLM models
- /api/canvas/workflows - Save/load workflow definitions (future)
"""
import logging
import asyncio
import random
from pathlib import Path
from flask import Blueprint, jsonify, request, Response
import json

from schemas.engine.model_selector import ModelSelector
from my_app.services.canvas_recorder import CanvasRecorder, get_canvas_recorder, cleanup_canvas_recorder
from my_app.services.canvas_executor import CanvasWorkflowExecutor
from my_app.services.pipeline_recorder import generate_run_id
import config

logger = logging.getLogger(__name__)

def _load_cloud_models_from_matrix():
    """
    Load cloud LLM models from hardware_matrix.json (single source of truth).
    Returns deduplicated list of model dicts with id, name, provider, dsgvo.
    """
    import os
    matrix_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'hardware_matrix.json')
    try:
        import json
        with open(matrix_path) as f:
            matrix = json.load(f)
    except Exception as e:
        logger.warning(f"[Canvas LLM] Failed to load hardware_matrix.json: {e}")
        return []

    seen_ids = set()
    cloud_models = []
    for _provider_key, preset in matrix.get('llm_presets', {}).items():
        label = preset.get('label', _provider_key.title())
        provider = preset.get('EXTERNAL_LLM_PROVIDER', _provider_key)
        dsgvo = preset.get('DSGVO_CONFORMITY', False)
        for _role, model_id in preset.get('models', {}).items():
            if model_id and model_id not in seen_ids:
                seen_ids.add(model_id)
                # Derive display name from model_id (provider/model-name → model-name (Label))
                parts = model_id.split('/', 1)
                display_name = parts[1] if len(parts) == 2 else model_id
                cloud_models.append({
                    'id': model_id,
                    'name': f"{display_name} ({label})",
                    'provider': provider,
                    'dsgvo': dsgvo
                })
    return cloud_models

# ============================================================================
# RANDOM PROMPT PRESETS (Session 140)
# ============================================================================

RANDOM_PROMPT_PRESETS = {
    'clean_image': {
        'systemPrompt': """You are an inventive creative. Your task is to invent a vivid, detailed image prompt.

IMPORTANT - Generate CLEAN, MEDIA-NEUTRAL images:
- NO camera or photographic references (no film, no camera, no lens)
- NO optical effects (no wide-angle, no telephoto, no macro)
- NO depth of field or bokeh
- NO motion blur or any blur effects
- NO "retro", "vintage", or nostalgic styling
- NO film grain, vignette, or post-processing artifacts

Think globally. Avoid cultural clichés.
Subject matter: scenes, objects, animals, nature, technology, culture, people, homes, family, work, holiday, urban, rural, trivia, intricate details.
Be verbose, provide rich visual details about colors, lighting, textures, composition, atmosphere.
Transform the prompt strictly following the context if provided.
NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER.""",
        'userPromptTemplate': 'Generate a creative image prompt.'
    },
    'photo': {
        'systemPrompt': """You are an inventive creative. Your task is to invent a REALISTIC photographic image prompt.

Think globally. Avoid cultural clichés. Avoid "retro" style descriptions.
Describe contemporary everyday motives: scenes, objects, animals, nature, tech, culture, people, homes, family, work, holiday, urban, rural, trivia, details.
Choose either unlikely, untypical or typical photographical sujets. Be verbose, provide intricate details.
Always begin your output with: "{film_description} of".
Transform the prompt strictly following the context if provided.
NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER.""",
        'userPromptTemplate': 'Generate a creative photographic image prompt.'
    },
    'artform': {
        'systemPrompt': """You generate artform transformation instructions from an artist practice perspective.

IMPORTANT: NEVER use "in the style of" - instead frame as artistic practice, technique, or creative process.

Good examples:
- "Render this as a Japanese Noh theatre performance"
- "Transform this into a Yoruba praise poem"
- "Compose this as a Maori chant"
- "Frame this message through Cubist fragmentation"
- "Present this as an Afro-futurist myth"
- "Choreograph this as a Bharatanatyam narrative"
- "Inscribe this as Egyptian hieroglyphics"
- "Express this through Aboriginal dot painting technique"

Think globally across all cultures and art practices.
Focus on the DOING - the artistic practice, not imitation.
Output ONLY the transformation instruction, nothing else.""",
        'userPromptTemplate': 'Generate a creative artform transformation instruction.'
    },
    'instruction': {
        'systemPrompt': """You generate creative transformation instructions.
Your output is a single instruction that transforms content in an unusual, creative way.
Examples: nature language, theatrical play, nostalgic robot voice, rhythmic rap, animal fable, alien explanation, philosophical versions (Wittgenstein, Heidegger, Adorno), ancient manuscript, bedtime story for post-human child, internal monologue of a tree, forgotten folk song lyrics, spy messages, protest chant, underwater civilization dialect, extinct animal conversation, dream sequence, poetic weather forecast, love letter to future generation, etc.
Be wildly creative and unexpected.
Output ONLY the transformation instruction, nothing else.""",
        'userPromptTemplate': 'Generate a creative transformation instruction.'
    },
    'language': {
        'systemPrompt': """You suggest a random language from around the world.
Choose from major world languages, regional languages, or less common languages.
Consider: European, Asian, African, Indigenous American, Pacific languages.
Output ONLY the language name in English, nothing else.
Example outputs: "Swahili", "Bengali", "Quechua", "Welsh", "Tagalog" """,
        'userPromptTemplate': 'Suggest a random language.'
    }
}

PHOTO_FILM_TYPES = {
    'random': None,
    'Kodachrome': 'a Kodachrome film slide',
    'Ektachrome': 'an Ektachrome film slide',
    'Portra 400': 'a Kodak Portra 400 color negative',
    'Portra 800': 'a Kodak Portra 800 color negative',
    'Ektar 100': 'a Kodak Ektar 100 color negative',
    'Fuji Pro 400H': 'a Fujifilm Pro 400H color negative',
    'Fuji Superia': 'a Fujifilm Superia color negative',
    'CineStill 800T': 'a CineStill 800T tungsten-balanced color negative',
    'Ilford HP5': 'an Ilford HP5 Plus black and white negative',
    'Ilford Delta 400': 'an Ilford Delta 400 black and white negative',
    'Ilford FP4': 'an Ilford FP4 Plus black and white negative',
    'Ilford Pan F': 'an Ilford Pan F Plus 50 black and white negative',
    'Ilford XP2': 'an Ilford XP2 Super chromogenic black and white negative',
    'Tri-X 400': 'a Kodak Tri-X 400 black and white negative'
}

# Create blueprint
canvas_bp = Blueprint('canvas', __name__)

# Session 150: Batch abort support
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
    2. Cloud models from hardware_matrix.json (single source of truth)
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

    # 2. Cloud models from hardware_matrix.json (single source of truth)
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
        dsgvo_providers = {p[0] for p in config.DSGVO_SAFE_PROVIDERS}
        models.append({
            'id': default_model_id,
            'name': f"{model_name} ({provider_prefix.title()})",
            'provider': provider_prefix,
            'tier': 'configured',
            'dsgvoCompliant': provider_prefix in dsgvo_providers or provider_prefix == 'local',
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
# VISION MODELS (Session 152)
# ============================================================================

# Vision-capable local model patterns (checked against model names)
# Session 152: Comprehensive list - matches "vision" or "vl" in name
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

    Session 152: Vision models are ALWAYS local (per Model Matrix architecture):
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


@canvas_bp.route('/api/canvas/workflows', methods=['GET'])
def list_workflows():
    """
    List saved canvas workflows

    TODO: Implement in Phase 3
    """
    return jsonify({
        'status': 'success',
        'workflows': [],
        'message': 'Workflow persistence not yet implemented'
    })


@canvas_bp.route('/api/canvas/workflows', methods=['POST'])
def save_workflow():
    """
    Save a canvas workflow

    TODO: Implement in Phase 3
    """
    return jsonify({
        'status': 'error',
        'message': 'Workflow persistence not yet implemented'
    }), 501


@canvas_bp.route('/api/canvas/execute', methods=['POST'])
def execute_workflow():
    """
    Execute a canvas workflow using simple Tracer approach.

    Session 134: Complete rewrite - Tracer follows connections through the graph,
    passing data between nodes. At forks (evaluation), the score determines the path.

    Data Types:
    - text: string
    - image: dict with url, media_type, etc.

    Node Signatures:
    - input: () → text
    - interception: text → text
    - translation: text → text
    - generation: text → image
    - evaluation: text|image → text (+ decides output path)
    - display: text|image → (terminal)
    - collector: text|image → (terminal)
    """
    from schemas.engine.prompt_interception_engine import PromptInterceptionEngine, PromptInterceptionRequest
    import time
    import uuid

    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'error': 'JSON request expected'}), 400

        nodes = data.get('nodes', [])
        connections = data.get('connections', [])

        if not nodes:
            return jsonify({'status': 'error', 'error': 'No nodes provided'}), 400

        logger.info(f"[Canvas Tracer] Starting with {len(nodes)} nodes, {len(connections)} connections")

        # Build graph
        node_map = {n['id']: n for n in nodes}
        # outgoing[node_id] = [(target_id, label), ...]
        outgoing = {n['id']: [] for n in nodes}
        incoming = {n['id']: [] for n in nodes}
        for conn in connections:
            src = conn.get('sourceId')
            tgt = conn.get('targetId')
            label = conn.get('label')  # 'passthrough', 'commented', 'commentary', 'feedback', or None
            if src and tgt:
                outgoing[src].append({'target': tgt, 'label': label})
                incoming[tgt].append({'source': src, 'label': label})

        # Find source nodes: input node + random_prompt nodes with no incoming connections
        source_nodes = []
        input_node = None
        for n in nodes:
            ntype = n.get('type')
            if ntype == 'input':
                input_node = n
                source_nodes.append(n)
            elif ntype == 'random_prompt' and not incoming.get(n['id']):
                # random_prompt without input = standalone source
                source_nodes.append(n)

        if not source_nodes:
            return jsonify({'status': 'error', 'error': 'No source nodes found (need input or standalone random_prompt)'}), 400

        # Execution state
        results = {}
        collector_items = []
        comparison_inputs = {}  # Session 147: {node_id: [{label, text, source}, ...]}
        execution_trace = []
        engine = PromptInterceptionEngine()
        canvas_run_id = generate_run_id(suffix="canvas")

        # Session 149: Initialize CanvasRecorder for export
        # Get device_id from request if provided
        device_id = data.get('device_id')
        recorder = get_canvas_recorder(
            run_id=canvas_run_id,
            workflow={'nodes': nodes, 'connections': connections},
            device_id=device_id
        )

        # Safety limit for feedback loops
        MAX_TOTAL_EXECUTIONS = 50
        execution_count = [0]  # Use list for nonlocal mutation

        def execute_node(node, input_data, data_type, source_node_id=None, source_node_type=None):
            """Execute a single node and return (output_data, output_type, metadata)"""
            node_id = node['id']
            node_type = node.get('type')

            logger.info(f"[Canvas Tracer] Executing {node_id} ({node_type})")

            if node_type == 'input':
                output = node.get('promptText', '')
                results[node_id] = {'type': 'input', 'output': output, 'error': None}
                # Session 149: Save to recorder
                if output:
                    recorder.save_entity(node_id=node_id, node_type='input', content=output)
                return output, 'text', None

            elif node_type == 'random_prompt':
                # Session 140: Random Prompt Node with presets
                preset = node.get('randomPromptPreset', 'clean_image')
                llm_model = node.get('randomPromptModel', 'local/mistral-nemo')
                film_type = node.get('randomPromptFilmType', 'random')
                custom_system = node.get('randomPromptSystemPrompt')

                # Get preset config
                preset_config = RANDOM_PROMPT_PRESETS.get(preset, RANDOM_PROMPT_PRESETS['clean_image'])
                system_prompt = custom_system or preset_config['systemPrompt']
                user_prompt_template = preset_config['userPromptTemplate']

                # Handle photo preset film type
                if preset == 'photo':
                    if film_type == 'random':
                        film_type = random.choice([k for k in PHOTO_FILM_TYPES.keys() if k != 'random'])
                    film_desc = PHOTO_FILM_TYPES.get(film_type, 'a photograph')
                    system_prompt = system_prompt.replace('{film_description}', film_desc)

                # Build user prompt with optional context
                if input_data and str(input_data).strip():
                    user_prompt = f"Context: {input_data.strip()}\n\n{user_prompt_template}"
                else:
                    user_prompt = user_prompt_template

                req = PromptInterceptionRequest(
                    input_prompt=user_prompt,
                    style_prompt=system_prompt,
                    model=llm_model,
                    temperature=0.9,  # High variance for creative outputs
                    debug=True
                )
                response = asyncio.run(engine.process_request(req))
                output = response.output_str if response.success else ''

                results[node_id] = {
                    'type': 'random_prompt',
                    'output': output,
                    'preset': preset,
                    'film_type': film_type if preset == 'photo' else None,
                    'error': response.error if not response.success else None,
                    'model': response.model_used
                }
                # Session 149: Save to recorder
                if output:
                    recorder.save_entity(node_id=node_id, node_type='random_prompt', content=output,
                                        metadata={'preset': preset, 'model': response.model_used})
                logger.info(f"[Canvas Tracer] Random Prompt ({preset}): '{output[:50]}...'")
                return output, 'text', None

            elif node_type == 'interception':
                llm_model = node.get('llmModel', 'local/mistral-nemo')
                context_prompt = node.get('contextPrompt', '')

                if not input_data:
                    results[node_id] = {'type': 'interception', 'output': '', 'error': 'No input'}
                    return '', 'text', None

                req = PromptInterceptionRequest(
                    input_prompt=input_data,
                    style_prompt=context_prompt,
                    model=llm_model,
                    debug=True
                )
                response = asyncio.run(engine.process_request(req))
                output = response.output_str if response.success else ''
                results[node_id] = {
                    'type': 'interception',
                    'output': output,
                    'error': response.error if not response.success else None,
                    'model': response.model_used
                }
                # Session 149: Save to recorder
                if output:
                    recorder.save_entity(node_id=node_id, node_type='interception', content=output,
                                        metadata={'model': response.model_used})
                logger.info(f"[Canvas Tracer] Interception: '{output[:50]}...'")
                return output, 'text', None

            elif node_type == 'translation':
                llm_model = node.get('llmModel', 'local/mistral-nemo')
                translation_prompt = node.get('translationPrompt', 'Translate to English:')

                if not input_data:
                    results[node_id] = {'type': 'translation', 'output': '', 'error': 'No input'}
                    return '', 'text', None

                req = PromptInterceptionRequest(
                    input_prompt=input_data,
                    style_prompt=translation_prompt,
                    model=llm_model,
                    debug=True
                )
                response = asyncio.run(engine.process_request(req))
                output = response.output_str if response.success else ''
                results[node_id] = {
                    'type': 'translation',
                    'output': output,
                    'error': response.error if not response.success else None,
                    'model': response.model_used
                }
                # Session 149: Save to recorder
                if output:
                    recorder.save_entity(node_id=node_id, node_type='translation', content=output,
                                        metadata={'model': response.model_used})
                return output, 'text', None

            elif node_type == 'seed':
                # Session 149: Seed node for reproducible generation
                seed_mode = node.get('seedMode', 'fixed')
                seed_value = node.get('seedValue', 42)
                seed_base = node.get('seedBase', 0)

                if seed_mode == 'fixed':
                    output_seed = seed_value
                elif seed_mode == 'random':
                    output_seed = random.randint(0, 2**32 - 1)
                elif seed_mode == 'increment':
                    # Increment mode uses seedBase, incremented by batch run_index
                    # For single runs, just use seedBase
                    output_seed = seed_base
                else:
                    output_seed = seed_value

                results[node_id] = {'type': 'seed', 'output': output_seed, 'error': None, 'seedMode': seed_mode}
                logger.info(f"[Canvas Tracer] Seed: {output_seed} (mode={seed_mode})")
                return output_seed, 'seed', None

            elif node_type == 'generation':
                # Session 136: Use execute_stage4_generation_only directly
                # Canvas handles translation via Translation node, so we skip Stage 3 entirely
                from my_app.routes.schema_pipeline_routes import execute_stage4_generation_only
                from config import DEFAULT_SAFETY_LEVEL

                config_id = node.get('configId')
                if not config_id:
                    results[node_id] = {'type': 'generation', 'output': None, 'error': 'No config'}
                    return None, 'image', None

                # Session 149: Check for seed from connected seed node
                # Look for incoming 'seed' labeled connection
                generation_seed = None
                for inc in incoming.get(node_id, []):
                    source_id = inc.get('source')
                    source_node = node_map.get(source_id)
                    if source_node and source_node.get('type') == 'seed':
                        seed_result = results.get(source_id)
                        if seed_result and seed_result.get('output') is not None:
                            generation_seed = int(seed_result['output'])
                            logger.info(f"[Canvas Tracer] Generation using seed from node {source_id}: {generation_seed}")
                            break

                # Get prompt from text connection (not seed)
                prompt_data = None
                if isinstance(input_data, int):
                    # Input is a seed, not a prompt - look for prompt from other connections
                    for inc in incoming.get(node_id, []):
                        source_id = inc.get('source')
                        source_node = node_map.get(source_id)
                        if source_node and source_node.get('type') != 'seed':
                            source_result = results.get(source_id)
                            if source_result and isinstance(source_result.get('output'), str):
                                prompt_data = source_result['output']
                                break
                else:
                    prompt_data = input_data

                if not prompt_data:
                    results[node_id] = {'type': 'generation', 'output': None, 'error': 'No input'}
                    return None, 'image', None

                try:
                    # Call Stage 4 only - prompt is already translated by Canvas Translation node
                    gen_result = asyncio.run(execute_stage4_generation_only(
                        prompt=prompt_data,
                        output_config=config_id,
                        safety_level=DEFAULT_SAFETY_LEVEL,
                        run_id=canvas_run_id,
                        device_id=None,
                        seed=generation_seed  # Session 149: Pass seed if available
                    ))
                    if gen_result['success']:
                        output = gen_result['media_output']
                        results[node_id] = {'type': 'generation', 'output': output, 'error': None, 'configId': config_id}
                        # Session 149: Save image to recorder
                        if output and output.get('url'):
                            recorder.save_image_from_url(
                                node_id=node_id,
                                url=output['url'],
                                config_id=config_id,
                                seed=output.get('seed')
                            )
                        logger.info(f"[Canvas Tracer] Generation: {output['url']}")
                        return output, 'image', None
                    else:
                        results[node_id] = {'type': 'generation', 'output': None, 'error': gen_result.get('error'), 'configId': config_id}
                        return None, 'image', None
                except Exception as e:
                    results[node_id] = {'type': 'generation', 'output': None, 'error': str(e), 'configId': config_id}
                    return None, 'image', None

            elif node_type == 'evaluation':
                llm_model = node.get('llmModel', 'local/mistral-nemo')
                evaluation_prompt = node.get('evaluationPrompt', '')
                output_type_setting = node.get('outputType', 'all')

                # Convert input to text for evaluation
                if isinstance(input_data, dict) and input_data.get('url'):
                    eval_input = f"[Media: {input_data.get('media_type', 'image')} at {input_data.get('url')}]"
                else:
                    eval_input = input_data or ''

                if not eval_input:
                    results[node_id] = {
                        'type': 'evaluation',
                        'outputs': {'passthrough': '', 'commented': '', 'commentary': ''},
                        'metadata': {'binary': None, 'score': None, 'active_path': None},
                        'error': 'No input'
                    }
                    return '', 'text', {'binary': None, 'score': None, 'active_path': None}

                # Build evaluation instruction
                instruction = f"{evaluation_prompt}\n\n"
                instruction += "Provide your evaluation in the following format:\n\n"
                instruction += "COMMENTARY: [Your detailed evaluation and feedback]\n"
                if output_type_setting in ['score', 'all']:
                    instruction += "SCORE: [Numeric score from 0 to 10 only]\n"
                instruction += "\nIMPORTANT: SCORE must be 0-10. Scores < 5 = FAILED, >= 5 = PASSED."

                req = PromptInterceptionRequest(
                    input_prompt=eval_input,
                    style_prompt=instruction,
                    model=llm_model,
                    debug=True
                )
                response = asyncio.run(engine.process_request(req))

                if not response.success:
                    results[node_id] = {
                        'type': 'evaluation',
                        'outputs': {'passthrough': '', 'commented': '', 'commentary': ''},
                        'metadata': {'binary': None, 'score': None, 'active_path': None},
                        'error': response.error
                    }
                    return '', 'text', {'binary': None, 'score': None, 'active_path': None}

                # Parse response
                commentary = ''
                score = None

                if 'COMMENTARY:' in response.output_str:
                    parts = response.output_str.split('COMMENTARY:')[1]
                    commentary = parts.split('SCORE:')[0].strip() if 'SCORE:' in parts else parts.strip()
                else:
                    commentary = response.output_str

                if response.output_float is not None:
                    score = float(response.output_float)
                elif 'SCORE:' in response.output_str:
                    import re
                    score_part = response.output_str.split('SCORE:')[1].split('\n')[0]
                    nums = re.findall(r'\d+\.?\d*', score_part)
                    if nums:
                        score = float(nums[0])

                if score is not None and (score < 0 or score > 10):
                    score = None

                binary_result = score >= 5.0 if score is not None else False
                active_path = 'passthrough' if binary_result else 'commented'

                passthrough_text = eval_input
                commented_text = f"{eval_input}\n\nFEEDBACK: {commentary}"
                commentary_text = commentary

                results[node_id] = {
                    'type': 'evaluation',
                    'outputs': {
                        'passthrough': passthrough_text,
                        'commented': commented_text,
                        'commentary': commentary_text
                    },
                    'metadata': {
                        'binary': binary_result,
                        'score': score,
                        'active_path': active_path
                    },
                    'error': None,
                    'model': response.model_used
                }
                # Session 149: Save evaluation to recorder
                if commentary_text:
                    recorder.save_entity(node_id=node_id, node_type='evaluation', content=commentary_text,
                                        metadata={'score': score, 'binary': binary_result, 'active_path': active_path, 'model': response.model_used})
                logger.info(f"[Canvas Tracer] Evaluation: score={score}, binary={binary_result}, path={active_path}")

                # Return the appropriate output based on binary result
                output_text = passthrough_text if binary_result else commented_text
                return output_text, 'text', {'binary': binary_result, 'score': score, 'active_path': active_path}

            elif node_type == 'display':
                # Session 135: Display node (tap/observer) - records but doesn't propagate in flow
                display_title = node.get('title', 'Display')
                display_mode = node.get('displayMode', 'inline')
                results[node_id] = {
                    'type': 'display',
                    'output': input_data,
                    'error': None,
                    'displayData': {
                        'title': display_title,
                        'mode': display_mode,
                        'content': input_data,
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
                    }
                }
                logger.info(f"[Canvas Tracer] Display (tap): '{display_title}'")
                # Return None to signal this is a tap/observer (not part of main flow)
                return None, data_type, None

            elif node_type == 'collector':
                # Collector gathers what arrives - use old format for frontend compatibility
                # Include metadata from source node if available (e.g., evaluation score/binary)
                source_result = results.get(source_node_id, {}) if source_node_id else {}
                source_metadata = source_result.get('metadata')

                collector_item = {
                    'nodeId': source_node_id or node_id,
                    'nodeType': source_node_type or data_type,
                    'output': input_data,
                    'error': None
                }

                # For evaluation nodes, wrap output with metadata for frontend
                if source_node_type == 'evaluation' and source_metadata:
                    collector_item['output'] = {
                        'text': input_data,
                        'metadata': source_metadata
                    }

                collector_items.append(collector_item)
                results[node_id] = {
                    'type': 'collector',
                    'output': collector_items,
                    'error': None
                }
                logger.info(f"[Canvas Tracer] Collector: {len(collector_items)} items")
                return input_data, data_type, None  # Terminal

            elif node_type == 'comparison_evaluator':
                # Session 147: Multi-input comparison evaluator
                # Accumulate inputs like Collector, run LLM comparison when all inputs arrive
                llm_model = node.get('comparisonLlmModel', 'local/mistral-nemo')
                criteria = node.get('comparisonCriteria', '')
                expected_count = len(incoming.get(node_id, []))

                # Initialize buffer for this node if not exists
                if node_id not in comparison_inputs:
                    comparison_inputs[node_id] = []

                # Add this input to the buffer
                input_num = len(comparison_inputs[node_id]) + 1
                comparison_inputs[node_id].append({
                    'label': f'Text {input_num}',
                    'text': input_data or '',
                    'source': source_node_id
                })

                current_count = len(comparison_inputs[node_id])
                logger.info(f"[Canvas Tracer] Comparison Evaluator: received {current_count}/{expected_count} inputs")

                # Check if all expected inputs have arrived
                if current_count < expected_count:
                    # Not all inputs yet - store partial result, don't proceed
                    results[node_id] = {
                        'type': 'comparison_evaluator',
                        'output': None,
                        'error': None,
                        'status': 'waiting',
                        'inputs_received': current_count,
                        'inputs_expected': expected_count
                    }
                    # Signal waiting state via metadata to prevent propagation
                    return None, 'text', {'waiting': True}

                # All inputs received - run comparison
                inputs_list = comparison_inputs[node_id]

                # Format inputs for LLM
                formatted_inputs = "\n\n".join([
                    f"=== {inp['label']} (Quelle: {inp['source']}) ===\n{inp['text']}"
                    for inp in inputs_list
                ])

                instruction = f"""Analysiere und vergleiche die folgenden {len(inputs_list)} Texte systematisch.

{formatted_inputs}

EVALUATIONSKRITERIEN:
{criteria if criteria else 'Allgemeiner Vergleich nach Qualität, Klarheit und Vollständigkeit'}

Deine Analyse soll:
1. Jeden Text einzeln kurz charakterisieren (mit Bezug auf "Text 1", "Text 2" etc.)
2. Systematische Vergleiche anstellen
3. Gemäß der Kriterien bewerten
4. Eine Gesamteinschätzung geben

Strukturiere deine Antwort klar und beziehe dich immer auf die Text-Nummern."""

                req = PromptInterceptionRequest(
                    input_prompt="Führe die Analyse durch.",
                    style_prompt=instruction,
                    model=llm_model,
                    debug=True
                )
                response = asyncio.run(engine.process_request(req))
                output = response.output_str if response.success else ''

                results[node_id] = {
                    'type': 'comparison_evaluator',
                    'output': output,
                    'error': response.error if not response.success else None,
                    'model': response.model_used,
                    'metadata': {
                        'input_count': len(inputs_list),
                        'sources': [inp['source'] for inp in inputs_list]
                    }
                }
                # Session 149: Save comparison to recorder
                if output:
                    recorder.save_entity(node_id=node_id, node_type='comparison_evaluator', content=output,
                                        metadata={'input_count': len(inputs_list), 'sources': [inp['source'] for inp in inputs_list], 'model': response.model_used})
                logger.info(f"[Canvas Tracer] Comparison complete: {len(output)} chars")
                return output, 'text', None

            else:
                results[node_id] = {'type': node_type, 'output': None, 'error': f'Unknown type: {node_type}'}
                return None, 'text', None

        def trace(node_id, input_data, data_type, source_node_id=None, source_node_type=None):
            """Trace through the graph starting from node_id with given input"""
            execution_count[0] += 1
            if execution_count[0] > MAX_TOTAL_EXECUTIONS:
                logger.warning(f"[Canvas Tracer] Max executions ({MAX_TOTAL_EXECUTIONS}) reached, stopping")
                return

            node = node_map.get(node_id)
            if not node:
                return

            execution_trace.append(node_id)

            # Execute this node (pass source info for collector)
            output_data, output_type, metadata = execute_node(node, input_data, data_type, source_node_id, source_node_type)

            # Check if node is waiting for more inputs (comparison_evaluator)
            if metadata and metadata.get('waiting'):
                logger.info(f"[Canvas Tracer] Node {node_id} waiting for more inputs, not propagating")
                return

            # Get outgoing connections
            next_conns = outgoing.get(node_id, [])
            if not next_conns:
                return  # Terminal node

            node_type = node.get('type')

            # For evaluation nodes: filter connections based on score
            if node_type == 'evaluation' and metadata:
                active_path = metadata.get('active_path')  # 'passthrough' or 'commented'
                filtered_conns = []
                for conn in next_conns:
                    label = conn.get('label')
                    # Include if: no label, commentary (always), matches active_path, or feedback when commented
                    if not label:
                        filtered_conns.append(conn)
                    elif label == 'commentary':
                        filtered_conns.append(conn)
                    elif label == active_path:
                        filtered_conns.append(conn)
                    elif label == 'feedback' and active_path == 'commented':
                        filtered_conns.append(conn)
                next_conns = filtered_conns
                logger.info(f"[Canvas Tracer] Evaluation fork: active_path={active_path}, following {len(next_conns)} connections")

            # Session 135: Separate display nodes from flow (tap/observer pattern)
            display_conns = []
            flow_conns = []
            for conn in next_conns:
                target_node = node_map.get(conn['target'])
                if target_node and target_node.get('type') == 'display':
                    display_conns.append(conn)
                else:
                    flow_conns.append(conn)

            # Session 135: Execute display nodes in parallel (fire-and-forget)
            for conn in display_conns:
                target_id = conn['target']
                target_node = node_map.get(target_id)
                if not target_node:
                    continue
                # Execute display but don't recurse
                execute_node(target_node, output_data, output_type, node_id, node_type)

            # Follow each active flow connection (non-display)
            for conn in flow_conns:
                target_id = conn['target']
                target_node = node_map.get(target_id)
                if not target_node:
                    continue

                # Data type compatibility check
                target_type = target_node.get('type')
                accepts_text = target_type in ['random_prompt', 'interception', 'translation', 'generation', 'evaluation', 'collector', 'display', 'comparison_evaluator']
                accepts_image = target_type in ['evaluation', 'collector', 'display']
                accepts_seed = target_type == 'generation'  # Session 149: seed → generation

                if output_type == 'text' and not accepts_text:
                    logger.warning(f"[Canvas Tracer] Type mismatch: {node_id} outputs text, {target_id} ({target_type}) doesn't accept it")
                    continue
                if output_type == 'image' and not accepts_image:
                    logger.warning(f"[Canvas Tracer] Type mismatch: {node_id} outputs image, {target_id} ({target_type}) doesn't accept it")
                    continue
                if output_type == 'seed' and not accepts_seed:
                    logger.warning(f"[Canvas Tracer] Type mismatch: {node_id} outputs seed, {target_id} ({target_type}) doesn't accept it")
                    continue

                # For evaluation with specific output paths
                if node_type == 'evaluation' and metadata:
                    conn_label = conn.get('label')
                    # Get the right output based on connection label
                    if conn_label == 'commentary':
                        trace_data = results[node_id]['outputs']['commentary']
                    elif conn_label == 'passthrough':
                        trace_data = results[node_id]['outputs']['passthrough']
                    elif conn_label in ['commented', 'feedback']:
                        trace_data = results[node_id]['outputs']['commented']
                    else:
                        trace_data = output_data
                else:
                    trace_data = output_data

                # Recurse - pass source node info for collector
                trace(target_id, trace_data, output_type, node_id, node_type)

        # Start tracing from all source nodes (input + standalone random_prompt)
        for src_node in source_nodes:
            src_type = src_node.get('type')
            if src_type == 'input':
                input_text = src_node.get('promptText', '')
                logger.info(f"[Canvas Tracer] Starting from input: '{input_text[:50]}...'")
            else:
                logger.info(f"[Canvas Tracer] Starting from {src_type}: {src_node['id']}")
            trace(src_node['id'], None, 'text')  # Source nodes don't receive data

        logger.info(f"[Canvas Tracer] Complete. {execution_count[0]} executions, {len(collector_items)} collected items")
        logger.info(f"[Canvas Tracer] Trace: {' -> '.join(execution_trace)}")

        # Session 149: Mark recorder complete and cleanup
        recorder.mark_complete()
        cleanup_canvas_recorder(canvas_run_id)

        return jsonify({
            'status': 'success',
            'results': results,
            'collectorOutput': collector_items,
            'executionOrder': execution_trace,
            'exportPath': str(recorder.run_folder)  # Session 149: Return export path
        })

    except Exception as e:
        logger.error(f"[Canvas Tracer] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        # Session 149: Cleanup recorder on error
        if 'canvas_run_id' in locals() and 'recorder' in locals():
            cleanup_canvas_recorder(canvas_run_id)
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@canvas_bp.route('/api/canvas/execute-stream', methods=['POST'])
def execute_workflow_stream():
    """
    Execute a canvas workflow with SSE streaming for live progress updates.

    Session 141: SSE streaming endpoint - yields events IMMEDIATELY as each node executes.
    Session 150: Refactored to use CanvasWorkflowExecutor for shared execution logic.

    Events:
    - started: {total_nodes: N} - Execution begins
    - progress: {node_id, node_type, status, message} - Node starts executing
    - node_complete: {node_id, output_preview} - Node finished
    - complete: {results, collectorOutput, executionOrder} - All done
    - error: {message} - Error occurred
    """
    from schemas.engine.prompt_interception_engine import PromptInterceptionEngine
    import time
    import uuid

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

        def generate():
            """Generator that yields SSE events using CanvasWorkflowExecutor"""
            canvas_run_id = None
            try:
                logger.info(f"[Canvas Stream] Starting with {len(nodes)} nodes, {len(connections)} connections")

                # Send started event IMMEDIATELY
                yield f"event: started\ndata: {json.dumps({'total_nodes': len(nodes)})}\n\n"

                # Initialize
                engine = PromptInterceptionEngine()
                canvas_run_id = generate_run_id(suffix="canvas")
                device_id = data.get('device_id')

                recorder = get_canvas_recorder(
                    run_id=canvas_run_id,
                    workflow={'nodes': nodes, 'connections': connections},
                    device_id=device_id
                )

                # Create executor and run - use recorder's device_id (may be auto-generated)
                executor = CanvasWorkflowExecutor(
                    nodes=nodes,
                    connections=connections,
                    recorder=recorder,
                    run_id=canvas_run_id,
                    engine=engine,
                    device_id=recorder.device_id  # Use recorder's device_id, not the original
                )

                # Execute and yield events
                for event_type, event_data in executor.execute_with_events():
                    yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"

                # Get result and complete
                result = executor.get_result()
                if not result.get('success'):
                    yield f"event: error\ndata: {json.dumps({'message': result.get('error', 'Unknown error')})}\n\n"
                    cleanup_canvas_recorder(canvas_run_id)
                    return

                # Mark complete and cleanup
                recorder.mark_complete()
                export_path = str(recorder.run_folder)
                cleanup_canvas_recorder(canvas_run_id)

                logger.info(f"[Canvas Stream] Complete. Trace: {' -> '.join(result['execution_trace'])}")

                yield f"event: complete\ndata: {json.dumps({'results': result['results'], 'collectorOutput': result['collector_items'], 'executionOrder': result['execution_trace'], 'exportPath': export_path})}\n\n"

            except Exception as e:
                logger.error(f"[Canvas Stream] Fatal error: {e}")
                import traceback
                traceback.print_exc()
                if canvas_run_id:
                    cleanup_canvas_recorder(canvas_run_id)
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        return Response(generate(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        })

    except Exception as e:
        logger.error(f"[Canvas Stream] Setup error: {e}")
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')


@canvas_bp.route('/api/interception/<preset_id>', methods=['GET'])
def get_interception_config(preset_id: str):
    """
    Get a single interception config by ID (Session 146)

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

    Session 150: Batch abort endpoint for workshop safety.

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

    Session 149: Batch execution for research data production.
    Session 150: Refactored to use CanvasWorkflowExecutor + abort support.

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

        if not nodes:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'message': 'No nodes in workflow'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        # Determine batch mode: prompts list OR count
        prompts = data.get('prompts')  # List of input prompts
        count = data.get('count', 1)   # Number of runs (seed variance)
        device_id = data.get('device_id')
        base_seed = data.get('base_seed')  # Optional base seed

        if prompts and len(prompts) > 0:
            total_runs = len(prompts)
            batch_mode = 'prompts'
        else:
            total_runs = count
            batch_mode = 'seed_variance'

        batch_id = generate_run_id(suffix="canvas_batch")

        def generate():
            """Generator that yields SSE events for batch execution using CanvasWorkflowExecutor"""
            try:
                # Initialize abort flag
                BATCH_ABORT_FLAGS[batch_id] = False

                logger.info(f"[Canvas Batch] Starting batch {batch_id}: {total_runs} runs ({batch_mode})")

                # Send batch_started event
                yield f"event: batch_started\ndata: {json.dumps({'batch_id': batch_id, 'total_runs': total_runs, 'batch_mode': batch_mode})}\n\n"

                export_paths = []
                engine = PromptInterceptionEngine()

                for run_index in range(total_runs):
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
                        # Initialize recorder for this run
                        recorder = get_canvas_recorder(
                            run_id=run_id,
                            workflow={'nodes': nodes, 'connections': connections},
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
                            device_id=recorder.device_id  # Use recorder's device_id
                        )

                        # Execute and yield events with run_index context
                        for event_type, event_data in executor.execute_with_events():
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

        return Response(generate(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        })

    except Exception as e:
        logger.error(f"[Canvas Batch] Setup error: {e}")
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')


