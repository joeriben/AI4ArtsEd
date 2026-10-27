"""
Canvas Workflow Executor - Core execution engine for Canvas workflows

Extracted from canvas_routes.py to provide shared execution logic
for both single execution and batch execution endpoints.

Usage:
    executor = CanvasWorkflowExecutor(nodes, connections, recorder, run_id, engine,
                                      safety_level=<resolved at the request boundary>)

The level must be resolved by the caller, while the request is still
current — the run itself may execute in a worker thread that cannot see
the session. An executor that is not told the level uses the strictest.
    for event_type, event_data in executor.execute_with_events():
        # Handle progress/node_complete events
    result = executor.get_result()
"""
import logging
import asyncio
import random
import time
from typing import Dict, List, Any, Optional, Generator, Tuple
from my_app.services.safety_level_resolver import STRICTEST

from schemas.engine.prompt_interception_engine import PromptInterceptionEngine, PromptInterceptionRequest
from my_app.services.translation_instruction import (
    CANVAS_TRANSLATION_INSTRUCTION, CANVAS_TRANSLATION_LANGUAGE, language_name,
)


def _configured_canvas_model(config_attr: str) -> str:
    """Resolve a canvas LLM node's model from the platform's centralized config
    (devserver/config.py) -- the same STAGE*_MODEL the main 4-stage pipeline uses --
    instead of a hardcoded micro-model. No local fallback: the main pipeline
    consumes these same STAGE*_MODEL values directly with no per-call default, and
    _check_required_models() (my_app/__init__.py) already refuses to boot if one is
    blank -- a silent fallback here would just reopen that gap one layer down.
    Root-cause fix: canvas LLM nodes historically defaulted to 'local/mistral-nemo',
    silently bypassing STAGE*_MODEL for any node authored without an explicit model
    (e.g. Resona's graphs -> garbage translation)."""
    import config
    return (getattr(config, config_attr, "") or "").strip()


# The Model Adaption node's presets (types/canvas.ts, ModelAdaptionPreset) as
# the output config whose adaption instruction each one runs. The two presets
# that name a model family point at that family's config; neither of them
# carries an instruction today, so both pass the text on (for SD3.5 by decision,
# 59eab5a8; flux2 has never had one). The two that name a medium take that
# medium's entry in schemas/output_config_defaults.json, the file the backend
# reads when a request names a medium and no config. 'none' is in neither table
# and passes the text on.
_ADAPTION_CONFIGS = {'sd35': 'sd35_large', 'flux': 'flux2'}
_ADAPTION_MEDIA = {'video': 'video', 'audio': 'audio'}


def _load_interception_context(config_id: str, lang: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Load the context (lens instruction) of a configured interception config.

    Instrument fidelity (2026-07-16): lets a canvas interception node run the
    platform's REAL lens text instead of an authored paraphrase. Returns
    (context, None) on success or ('', error_message) on failure. Language
    resolution: requested lang -> 'en' -> any available.
    """
    import json as _json
    from pathlib import Path as _Path

    # The id must be the stem of a configured lens. A character class let no
    # accent through, and 'clichéfilter_v2', which canvas_graph_authoring offers,
    # was refused as invalid; a name that is no stem reaches no path either way.
    cfg_dir = _Path(__file__).parent.parent.parent / "schemas" / "configs" / "interception"
    lenses = {p.stem: p for p in cfg_dir.glob("*.json")}
    safe = (config_id or "").lower()
    if safe not in lenses:
        return '', f"unknown interception configId '{config_id}' — no such lens is configured"
    cfg_path = lenses[safe]
    try:
        cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as e:
        return '', f"interception config '{safe}' unreadable: {e}"
    # A canvas interception node is ONE text model call. A config on another
    # pipeline (the song, the image and Latent Lab instruments) carries no lens
    # instruction: its context, where it has one, describes the instrument.
    # The text pipelines are the ones a perspective may run on.
    from my_app.services.course_prompt_resolver import ALLOWED_PIPELINES
    pipeline_name = cfg.get("pipeline") or ""
    if pipeline_name not in ALLOWED_PIPELINES:
        return '', (f"interception config '{safe}' runs on the pipeline "
                    f"'{pipeline_name}', which is no text pipeline; a canvas "
                    f"interception node is one text model call")
    # A lens whose pipeline loops
    # (the chained translation) has its meaning in the loop -- its context text
    # is one link, written for a step that is handed a target language the
    # canvas has no notion of. Running that text once would put an instruction
    # into the graph that names a language nobody set. Refused by name, so the
    # graph says what is missing instead of quietly producing nonsense.
    if pipeline_name:
        pipe_path = cfg_path.parent.parent.parent / "pipelines" / f"{pipeline_name}.json"
        try:
            loops = bool(_json.loads(pipe_path.read_text(encoding="utf-8"))
                         .get("meta", {}).get("supports_loop"))
        except Exception:
            loops = False
        if loops:
            return '', (f"interception config '{safe}' runs on the looping pipeline "
                        f"'{pipeline_name}' — its context text is ONE link of a chain "
                        f"and needs a target language per step, which a single canvas "
                        f"interception node has no way to give it")
    contexts = cfg.get("context") or {}
    if not isinstance(contexts, dict) or not contexts:
        return '', f"interception config '{safe}' has no context texts"
    wanted = (lang or "en").strip().lower()
    context = contexts.get(wanted) or contexts.get("en")
    if not context:
        context = next(iter(contexts.values()))
    if not str(context or "").strip():
        # user_defined: every language empty; the node would run with no instruction
        return '', f"interception config '{safe}' has no context texts"
    return str(context), None


logger = logging.getLogger(__name__)


def _field_text(value) -> str:
    """A node's text field, stripped; a saved or authored node can carry anything there."""
    return value.strip() if isinstance(value, str) else ''


def as_seed(value) -> Optional[int]:
    """A seed field as a whole number, or None where it holds none.

    The Canvas stores whole numbers, but a hand-edited file, a Resona-authored
    node or a cleared form field can hand over a string, a float or nothing,
    and arithmetic on those stopped the whole run. A seed node that reads None
    gives its generation no seed, which then takes the batch's run seed where
    there is one and a random one otherwise (`_execute_generation`).
    """
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None

# ============================================================================
# CONSTANTS (copied from canvas_routes.py for isolation)
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

Think globally across all cultures and art practices.
Focus on the DOING - the artistic practice, not imitation.
Be specific about techniques, materials, and cultural context.
NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER.""",
        'userPromptTemplate': 'Generate an artform transformation instruction.'
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

NODE_TYPE_LABELS = {
    'input': 'Processing Input',
    'image_input': 'Loading Image',
    'random_prompt': 'Generating Random Prompt',
    'interception': 'Running Interception',
    'translation': 'Translating',
    'model_adaption': 'Model Adaption',
    'generation': 'Generating Media',
    'evaluation': 'Evaluating',
    'image_evaluation': 'Analyzing Image',
    'display': 'Display',
    'collector': 'Collecting Results',
    'comparison_evaluator': 'Comparing Inputs',
    'seed': 'Processing Seed',
    'resolution': 'Setting Resolution',
    'quality': 'Setting Quality'
}

MAX_TOTAL_EXECUTIONS = 50


def canvas_stage3_verdict(prompt: str, secondary_text: Optional[str], safety_level: str,
                          lang: Optional[str], device_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """The flow's Stage 3 on what a Canvas generation is about to receive; None if it may.

    The flow checks every text before it reaches a media model
    (execute_generation_stage4); the Canvas calls Stage 4 alone, and until
    2026-10-02 nothing on it looked at such a text, whichever node wrote it --
    an input wired straight to a video model went through unread at every
    level. Here the same function is asked at every level, as the flow asks
    it, and decides as it does there: at kids, youth and open it translates for
    its own check, filters §86a and asks the safety classifier the level's
    question; at adult and research it lets the text pass unasked.

    Only the verdict is read. What the generation receives is what the board
    wired to it -- translating is a node of its own here -- so every text is
    checked as given (`as_given`): at kids the classifier reads the
    translation AND the text the model will get, never the translation alone.

    A check that cannot run refuses, as one that runs without a verdict does,
    and stops only the node that asked.
    """
    try:
        import my_app.routes.schema_pipeline_routes as spr
        from schemas.engine.stage_orchestrator import execute_stage3_safety

        if spr.pipeline_executor is None:
            spr.init_schema_engine()
        result: Dict[str, Any] = {'safe': True}
        # The prompt's translation is kept for the device, as the flow keeps
        # it; the second text's is not (no device_id), as the flow keeps none
        # of a text it checks beside the prompt -- it would push the prompt's
        # out of the one place the device has.
        for text, device in ((prompt, device_id), (secondary_text, None)):
            if not text:
                continue
            # Stage 3 names its medium for its log only; there is no more to it.
            result = asyncio.run(execute_stage3_safety(
                text, safety_level, 'canvas', spr.pipeline_executor,
                user_language=lang or 'de', device_id=device, as_given=True,
            ))
            if not result.get('safe'):
                break
    except Exception as e:
        logger.error(f"[Canvas] Stage 3 could not run: {e}", exc_info=True)
        return {'stage': 3, 'reason': f'the safety check could not run: {e}',
                'found_terms': [], 'operational': True}
    if result.get('safe'):
        return None
    return {
        'stage': 3,
        'reason': result.get('abort_reason') or 'Content blocked by safety check',
        'found_terms': result.get('found_terms') or [],
        'operational': result.get('method') in ('llm_check_failed', 'translation_failed'),
    }


class CanvasWorkflowExecutor:
    """
    Core execution engine for Canvas workflows.

    Responsibilities:
    - Build graph from nodes/connections
    - Execute nodes via work queue
    - Track results, collector items, execution trace
    - Yield events for SSE streaming

    NOT responsible for:
    - SSE formatting (caller's job)
    - Recorder lifecycle management (passed in, caller manages)
    - HTTP response handling
    """

    def __init__(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
        recorder: Any,  # CanvasRecorder instance
        run_id: str,
        engine: PromptInterceptionEngine,
        prompt_override: Optional[str] = None,
        run_seed: Optional[int] = None,
        device_id: Optional[str] = None,
        safety_level: Optional[str] = None,
        lang: Optional[str] = None,
        run_index: Optional[int] = None
    ):
        self.nodes = nodes
        self.connections = connections
        self.recorder = recorder
        self.run_id = run_id
        self.engine = engine
        self.prompt_override = prompt_override
        self.run_seed = run_seed
        # The run's place in a batch (0, 1, 2, ...); None outside a batch.
        self.run_index = run_index
        self.device_id = device_id
        # Resolved at the request boundary and handed in: the run executes in a
        # worker thread with no session, so it cannot be looked up here. An
        # executor that is not told the level gets the strictest one.
        self.safety_level = safety_level or STRICTEST
        # Which language a reading on this canvas is written in. Resolved at the
        # request boundary like the safety level; None means the instance's own.
        self.lang = lang

        # Execution state
        self.results: Dict[str, Any] = {}
        self.collector_items: List[Dict[str, Any]] = []
        # Per generation node: what its card shows on the back. Deliberately not
        # part of `self.results` — see _execute_generation.
        self.card_meta: Dict[str, Dict[str, Any]] = {}
        self.comparison_inputs: Dict[str, List[Dict[str, Any]]] = {}
        self.generation_text_inputs: Dict[str, List[Dict[str, Any]]] = {}
        self.execution_trace: List[str] = []
        self.execution_count = 0
        self.node_errors: List[Dict[str, Any]] = []  # fail-closed: nodes whose failure stopped their branch
        self._final_result: Optional[Dict[str, Any]] = None

        # Build graph
        self.node_map: Dict[str, Dict[str, Any]] = {n['id']: n for n in nodes}
        self.outgoing: Dict[str, List[Dict[str, Any]]] = {n['id']: [] for n in nodes}
        self.incoming: Dict[str, List[Dict[str, Any]]] = {n['id']: [] for n in nodes}

        for conn in connections:
            src = conn.get('sourceId')
            tgt = conn.get('targetId')
            label = conn.get('label')
            if src and tgt:
                self.outgoing[src].append({'target': tgt, 'label': label})
                self.incoming[tgt].append({'source': src, 'label': label})

    def execute_with_events(self) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        """
        Execute the workflow using iterative work queue.

        Yields:
            Tuple of (event_type, event_data) for each progress update:
            - ('progress', {node_id, node_type, status, message})
            - ('node_complete', {node_id, node_type, output_preview})

        After iteration completes, call get_result() to get final result.
        """
        # Find source nodes
        source_nodes = self._find_source_nodes()
        if not source_nodes:
            self._final_result = {'success': False, 'error': 'No source nodes found'}
            return

        # Initialize work queue
        work_queue = [{
            'node_id': src_node['id'],
            'input_data': None,
            'data_type': 'text',
            'source_node_id': None,
            'source_node_type': None,
            'connection_label': None
        } for src_node in source_nodes]

        # Execute work queue
        while work_queue and self.execution_count < MAX_TOTAL_EXECUTIONS:
            work_item = work_queue.pop(0)
            node_id = work_item['node_id']
            node = self.node_map.get(node_id)
            if not node:
                continue

            node_type = node.get('type')
            self.execution_count += 1
            self.execution_trace.append(node_id)

            # Yield progress event
            yield ('progress', {
                'node_id': node_id,
                'node_type': node_type,
                'status': 'executing',
                'message': NODE_TYPE_LABELS.get(node_type, f'Executing {node_type}...')
            })

            # Execute the node
            output_data, output_type, metadata = self._execute_node(
                node,
                work_item['input_data'],
                work_item['data_type'],
                work_item['source_node_id'],
                work_item['source_node_type'],
                work_item.get('connection_label')
            )

            # Yield node_complete event
            yield ('node_complete', {
                'node_id': node_id,
                'node_type': node_type,
                'output_preview': self._get_output_preview(output_data, output_type)
            })

            # Check if node is waiting for more inputs (comparison_evaluator)
            if metadata and metadata.get('waiting'):
                logger.info(f"[Canvas Executor] Node {node_id} waiting for more inputs")
                continue

            # Fail-closed (2026-07-16): a node that recorded an error does not
            # feed its downstream nodes. Before this, a failed image_evaluation
            # passed '' onward and comparison_evaluator confabulated a full
            # analysis from empty inputs.
            node_error = (self.results.get(node_id) or {}).get('error')
            if node_error:
                entry = {'node_id': node_id, 'node_type': node_type, 'error': node_error}
                blocked = (self.results.get(node_id) or {}).get('blocked')
                if blocked:
                    entry['blocked'] = blocked
                self.node_errors.append(entry)
                logger.error(f"[Canvas Executor] Node {node_id} failed ({node_error}) — downstream nodes will not run")
                continue

            # Add next nodes to work queue
            next_nodes = self._get_next_nodes(node_id, output_data, output_type, metadata)
            work_queue.extend(next_nodes)

        logger.info(f"[Canvas Executor] Complete. {self.execution_count} executions, {len(self.collector_items)} collected")
        logger.info(f"[Canvas Executor] Trace: {' -> '.join(self.execution_trace)}")

        # Fail-closed epilogue: nodes stuck waiting because an upstream branch
        # failed get an explicit error instead of a silent 'waiting' status.
        if self.node_errors:
            for nid, res in self.results.items():
                if isinstance(res, dict) and res.get('status') == 'waiting' and not res.get('error'):
                    res['error'] = 'did not run: an upstream node failed, inputs stayed missing'

        self._final_result = {
            'success': not self.node_errors,
            'results': self.results,
            'collector_items': self.collector_items,
            # What each generation's card shows on its back; see _execute_generation.
            'card_meta': self.card_meta,
            'execution_trace': self.execution_trace,
            'errors': self.node_errors,
        }
        # One authoritative failure message, built where the failures are known.
        # Every consumer reads result['error'] (the run worker, the batch route,
        # status.json) -- a key the executor never set, so each of them fell back
        # to the literal 'Unknown error' while the real cause sat unread in
        # 'errors'. Fixed here, not in the readers, so they all agree.
        if self.node_errors:
            self._final_result['error'] = '; '.join(
                f"{e.get('node_id')} ({e.get('node_type')}): {e.get('error')}"
                for e in self.node_errors
            )

    def get_result(self) -> Dict[str, Any]:
        """Get the final execution result after execute_with_events() completes."""
        if self._final_result is None:
            return {'success': False, 'error': 'Execution not completed'}
        return self._final_result

    def _find_source_nodes(self) -> List[Dict[str, Any]]:
        """Find source nodes: input nodes + image_input + standalone random_prompt nodes + parameter nodes."""
        source_nodes = []
        for n in self.nodes:
            ntype = n.get('type')
            if ntype == 'input':
                # Apply prompt override if provided
                if self.prompt_override is not None:
                    n = dict(n)  # Copy to avoid mutating original
                    n['promptText'] = self.prompt_override
                source_nodes.append(n)
            elif ntype == 'image_input':
                # Image input nodes are always source nodes
                source_nodes.append(n)
            elif ntype == 'random_prompt' and not self.incoming.get(n['id']):
                source_nodes.append(n)
            elif ntype == 'seed':
                # Seed nodes are always source nodes (no incoming connections)
                source_nodes.append(n)
            elif ntype == 'resolution':
                # Resolution nodes are always source nodes
                source_nodes.append(n)
            elif ntype == 'quality':
                # Quality nodes are always source nodes
                source_nodes.append(n)
        return source_nodes

    def _get_output_preview(self, output_data: Any, data_type: str) -> Optional[Dict[str, Any]]:
        """Generate a preview of output data for SSE events."""
        if output_data is None:
            return None
        if data_type == 'image' and isinstance(output_data, dict):
            return {'type': 'image', 'url': output_data.get('url', '')}
        if isinstance(output_data, str):
            preview = output_data[:100] + '...' if len(output_data) > 100 else output_data
            return {'type': 'text', 'preview': preview}
        return {'type': 'unknown'}

    def _execute_node(
        self,
        node: Dict[str, Any],
        input_data: Any,
        data_type: str,
        source_node_id: Optional[str] = None,
        source_node_type: Optional[str] = None,
        connection_label: Optional[str] = None
    ) -> Tuple[Any, str, Optional[Dict[str, Any]]]:
        """Execute a single node and return (output_data, output_type, metadata)."""
        node_id = node['id']
        node_type = node.get('type')

        logger.info(f"[Canvas Executor] Executing {node_id} ({node_type})")

        if node_type == 'input':
            return self._execute_input(node, node_id)
        elif node_type == 'image_input':
            return self._execute_image_input(node, node_id)
        elif node_type == 'random_prompt':
            return self._execute_random_prompt(node, node_id, input_data)
        elif node_type == 'interception':
            return self._execute_interception(node, node_id, input_data)
        elif node_type == 'translation':
            return self._execute_translation(node, node_id, input_data)
        elif node_type == 'model_adaption':
            return self._execute_model_adaption(node, node_id, input_data)
        elif node_type == 'seed':
            return self._execute_seed(node, node_id)
        elif node_type == 'resolution':
            return self._execute_resolution(node, node_id)
        elif node_type == 'quality':
            return self._execute_quality(node, node_id)
        elif node_type == 'generation':
            return self._execute_generation(node, node_id, input_data, connection_label)
        elif node_type == 'evaluation':
            return self._execute_evaluation(node, node_id, input_data)
        elif node_type == 'image_evaluation':
            return self._execute_image_evaluation(node, node_id, input_data, data_type)
        elif node_type == 'display':
            return self._execute_display(node, node_id, input_data, data_type)
        elif node_type == 'collector':
            return self._execute_collector(node, node_id, input_data, data_type, source_node_id, source_node_type)
        elif node_type == 'comparison_evaluator':
            return self._execute_comparison_evaluator(node, node_id, input_data, source_node_id, connection_label)
        else:
            self.results[node_id] = {'type': node_type, 'output': None, 'error': f'Unknown type: {node_type}'}
            return None, 'text', None

    # =========================================================================
    # Node execution methods
    # =========================================================================

    def _execute_input(self, node: Dict[str, Any], node_id: str) -> Tuple[str, str, None]:
        output = node.get('promptText', '')
        self.results[node_id] = {'type': 'input', 'output': output, 'error': None}
        if output:
            self.recorder.save_entity(node_id=node_id, node_type='input', content=output)
        return output, 'text', None

    def _execute_image_input(self, node: Dict[str, Any], node_id: str) -> Tuple[Optional[Dict[str, Any]], str, None]:
        """Execute image_input node - outputs uploaded image data."""
        image_data = node.get('imageData')

        if not image_data or not image_data.get('image_path'):
            self.results[node_id] = {'type': 'image_input', 'output': None, 'error': 'No image uploaded'}
            return None, 'image', None

        # Build image output dict (same format as generation output)
        output = {
            'url': image_data.get('preview_url', f"/api/media/uploads/{image_data['image_id']}"),
            'media_type': 'image',
            'source': 'upload',
            'image_path': image_data['image_path'],  # Absolute path for backend
            'image_id': image_data['image_id'],
            'width': image_data.get('resized_size', [1024, 1024])[0],
            'height': image_data.get('resized_size', [1024, 1024])[1]
        }

        self.results[node_id] = {'type': 'image_input', 'output': output, 'error': None}
        logger.info(f"[Canvas Executor] Image Input: {output['url']}")

        return output, 'image', None

    def _execute_image_evaluation(self, node: Dict[str, Any], node_id: str,
                                   input_data: Any, data_type: str) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        """Execute image_evaluation node - Vision-LLM analysis of images."""
        from my_app.utils.image_analysis import analyze_image
        from my_app.services.reading_frames import prompt as frame_prompt

        # Fail-closed vision default (2026-07-16): the old default
        # 'local/llama3.2-vision:latest' is unknown to the GPU service's
        # MODEL_CONFIGS registry — every unconfigured image_evaluation died
        # with "Unknown model" and fed '' downstream. The fallback is the role the
        # operator configures in Settings, not a name written in here: a model
        # spelled into code outlives the model itself, and the platform then cannot
        # be reconfigured without an edit (see tests/test_no_model_literals.py).
        import config
        from my_app.services.model_capabilities import is_local
        vision_model = node.get('visionModel') or config.IMAGE_ANALYSIS_MODEL
        if not is_local(vision_model):
            # analyze_image posts to the local GPU service and nowhere else. A cloud
            # string here dies one frame later as "Unknown model", which names nothing
            # the operator can act on -- so name the setting instead.
            raise ValueError(
                f"image evaluation needs a local vision model, but IMAGE_ANALYSIS_MODEL "
                f"is set to '{vision_model}'. Set it to a model the local backend serves, "
                f"or give this node its own visionModel."
            )
        chosen_preset = node.get('imageEvaluationPreset')
        preset = chosen_preset or 'bildwissenschaftlich'
        custom_prompt = node.get('imageEvaluationPrompt', '')
        # A prompt authored with no preset chosen IS the instruction. The tool
        # description offers image_evaluation {imageEvaluationPrompt} and never
        # mentions presets, so every authored reading had its question silently
        # replaced by the default framework. The human UI always sends a preset
        # and is unaffected.
        authored_prompt_wins = bool(custom_prompt) and not chosen_preset

        # Validate input is an image
        if data_type != 'image' or not isinstance(input_data, dict):
            self.results[node_id] = {
                'type': 'image_evaluation',
                'output': '',
                'error': 'Expected image input'
            }
            return '', 'text', None

        # An image reference, in whatever shape the source node produced it:
        # image_input carries an absolute path, generation only a media URL.
        # Both are references — media_ref resolves them, nothing is assumed.
        image_ref = input_data.get('image_path') or input_data.get('url')
        media_kind = input_data.get('media_type') or 'image'

        # A generation node reports every output as 'image' (see below), so an
        # audio or video URL can arrive here. A vision model cannot read it.
        if media_kind != 'image':
            self.results[node_id] = {
                'type': 'image_evaluation',
                'output': '',
                'error': f'this node reads images — {media_kind} cannot be read by a vision model'
            }
            return '', 'text', None

        if not image_ref:
            self.results[node_id] = {
                'type': 'image_evaluation',
                'output': '',
                'error': 'No image reference on the incoming data'
            }
            return '', 'text', None

        # Determine analysis prompt
        if custom_prompt and (preset == 'custom' or authored_prompt_wins):
            analysis_prompt = custom_prompt
        else:
            # The frame's own text, written to answer in this run's language.
            analysis_prompt = frame_prompt(preset, self.lang)
            if analysis_prompt is None:
                analysis_prompt = "Analyze this image thoroughly."
                logger.warning(f"[Canvas Executor] Image eval preset '{preset}' not found, using fallback")

        try:
            # Use existing image analysis helper (calls local VLM)
            # Pass selected vision model from node
            analysis_text = analyze_image(
                image_ref=image_ref,
                prompt=analysis_prompt,
                analysis_type=preset,
                model=vision_model,
                index=input_data.get('index'),
            )

            self.results[node_id] = {
                'type': 'image_evaluation',
                'output': analysis_text,
                'metadata': {'preset': preset},
                'error': None,
                'model': vision_model
            }

            if analysis_text:
                self.recorder.save_entity(
                    node_id=node_id,
                    node_type='image_evaluation',
                    content=analysis_text,
                    metadata={'preset': preset, 'model': vision_model}
                )

            logger.info(f"[Canvas Executor] Image Evaluation: {len(analysis_text)} chars")
            return analysis_text, 'text', None

        except Exception as e:
            error_msg = f"Vision analysis failed: {str(e)}"
            self.results[node_id] = {
                'type': 'image_evaluation',
                'output': '',
                'error': error_msg
            }
            logger.error(f"[Canvas Executor] {error_msg}")
            return '', 'text', None

    def _execute_random_prompt(self, node: Dict[str, Any], node_id: str, input_data: Any) -> Tuple[str, str, None]:
        preset = node.get('randomPromptPreset', 'clean_image')
        llm_model = node.get('randomPromptModel') or _configured_canvas_model('STAGE2_INTERCEPTION_MODEL')
        film_type = node.get('randomPromptFilmType', 'random')
        custom_system = node.get('randomPromptSystemPrompt')

        preset_config = RANDOM_PROMPT_PRESETS.get(preset, RANDOM_PROMPT_PRESETS['clean_image'])
        system_prompt = custom_system or preset_config['systemPrompt']
        user_prompt_template = preset_config['userPromptTemplate']

        # Token limit instruction
        token_limit = node.get('randomPromptTokenLimit', 75)
        if token_limit <= 75:
            system_prompt += "\n\nCRITICAL: Your output MUST NOT exceed 50 words. Be concise — comma-separated visual keywords, no full sentences."
        else:
            system_prompt += "\n\nYour output should be a detailed, verbose paragraph of 150-300 words. Provide rich visual details about colors, lighting, textures, composition, atmosphere."

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
            input_prompt=user_prompt, style_prompt=system_prompt,
            model=llm_model, debug=True
        )
        response = asyncio.run(self.engine.process_request(req))
        output = response.output_str if response.success else ''

        self.results[node_id] = {
            'type': 'random_prompt', 'output': output,
            'preset': preset, 'film_type': film_type if preset == 'photo' else None,
            'error': response.error if not response.success else None,
            'model': response.model_used
        }
        if output:
            self.recorder.save_entity(node_id=node_id, node_type='random_prompt', content=output,
                                     metadata={'preset': preset, 'model': response.model_used})
        logger.info(f"[Canvas Executor] Random Prompt ({preset}): '{output[:50]}...' if output else ''")
        return output, 'text', None

    def _execute_interception(self, node: Dict[str, Any], node_id: str, input_data: Any) -> Tuple[str, str, None]:
        llm_model = node.get('llmModel') or _configured_canvas_model('STAGE2_INTERCEPTION_MODEL')
        context_prompt = node.get('contextPrompt', '')

        # Instrument fidelity (2026-07-16): an interception node may reference
        # one of the platform's configured lenses by configId instead of
        # carrying an ad-hoc contextPrompt. The real lens text runs, so a claim
        # about "the platform's perspective" is about the platform's perspective —
        # not about a paraphrase of it.
        config_id = (node.get('configId') or '').strip()
        config_used = None
        if config_id:
            context_prompt, cfg_err = _load_interception_context(
                config_id, node.get('configLang')
            )
            if cfg_err:
                self.results[node_id] = {'type': 'interception', 'output': '', 'error': cfg_err}
                logger.error(f"[Canvas Executor] Interception {node_id}: {cfg_err}")
                return '', 'text', None
            config_used = config_id

        if not input_data:
            self.results[node_id] = {'type': 'interception', 'output': '', 'error': 'No input'}
            return '', 'text', None

        # No perspective, no step: the node is the flow's empty zone ("Du
        # bestimmst" with nothing filled in), and there the user's wording goes
        # on verbatim (config_loader.wants_passthrough).
        # The flow still runs the step so a Wikipedia lookup can overrule the
        # wording; this node does no lookups, so the run could only ever end in
        # the passthrough, and the model is not asked at all. The age check is
        # not this step's: it runs where the text meets the
        # media model, in _execute_generation, as Stage 3 does in the flow.
        if not (context_prompt or '').strip():
            # A node that names a perspective and carries none of its words is
            # not the empty zone: its text did not arrive (a failed fetch on
            # the board). Passed on, the prompt would come back unchanged under
            # the perspective's name.
            lens = (node.get('interceptionPreset') or '').strip()
            if lens and lens != 'user_defined' and not config_used:
                error = f"the perspective '{lens}' carries no text; choose it again"
                self.results[node_id] = {'type': 'interception', 'output': '', 'error': error}
                logger.error(f"[Canvas Executor] Interception {node_id}: {error}")
                return '', 'text', None
            self.results[node_id] = {
                'type': 'interception', 'output': input_data, 'error': None,
                'model': None, 'config_id': config_used, 'passthrough': True,
            }
            self.recorder.save_entity(node_id=node_id, node_type='interception', content=input_data,
                                     metadata={'model': None, 'config_id': config_used, 'passthrough': True})
            logger.info(f"[Canvas Executor] Interception {node_id}: no perspective, passthrough")
            return input_data, 'text', None

        # The interception node is the Canvas's Stage 2, so it gets what Stage 2
        # gets: the platform's task instruction, and with it the cultural-respect
        # rule and the safety prefix for this run's level. Without it the lens
        # text stood alone as the instruction (2026-09-07). A star standing on
        # its own in the text keeps its place, as it does in Stage 2
        # (PLACEHOLDER_CLAUSE); here the clause rides on the instruction, since
        # the engine assembles this prompt itself and writes the Context last.
        from schemas.engine.instruction_selector import get_instruction, get_placeholder_clause
        req = PromptInterceptionRequest(
            input_prompt=input_data, style_prompt=context_prompt,
            task_instruction=(get_instruction('transformation',
                                              safety_level=self.safety_level)
                              + get_placeholder_clause(input_data, 'Prompt')),
            model=llm_model, debug=True
        )
        response = asyncio.run(self.engine.process_request(req))
        output = response.output_str if response.success else ''
        error = response.error if not response.success else None
        # The refusal the safety prefix asks for is a block of this node, not
        # its text (finding S-015 of the code review of 2026-10-10).
        from schemas.engine.instruction_selector import is_safety_refusal
        if is_safety_refusal(output):
            logger.warning(f"[Canvas Executor] Interception refused by the model ({node_id})")
            error, output = output, ''

        self.results[node_id] = {
            'type': 'interception', 'output': output,
            'error': error,
            'model': response.model_used,
            'config_id': config_used,
        }
        if output:
            self.recorder.save_entity(node_id=node_id, node_type='interception', content=output,
                                     metadata={'model': response.model_used, 'config_id': config_used})
        logger.info(f"[Canvas Executor] Interception: '{output[:50]}'")
        return output, 'text', None

    def _execute_translation(self, node: Dict[str, Any], node_id: str, input_data: Any) -> Tuple[str, str, None]:
        llm_model = node.get('llmModel') or _configured_canvas_model('STAGE3_MODEL')
        instruction = _field_text(node.get('translationPrompt'))
        language = _field_text(node.get('translationLanguage'))
        # A field left empty is the default the node shows in it. An own
        # instruction with no language chosen names its language itself, as
        # every one did before the node had a language (2026-10-24).
        if not instruction:
            instruction = CANVAS_TRANSLATION_INSTRUCTION
            language = language or CANVAS_TRANSLATION_LANGUAGE

        if not input_data:
            self.results[node_id] = {'type': 'translation', 'output': '', 'error': 'No input'}
            return '', 'text', None

        # Built here, not by the engine: the engine's own assembly appends its
        # rules for running prose, among them "reply in the language of the
        # input", the opposite of a translation.
        parts = [instruction]
        if language:
            parts.append(f"Target language: {language_name(language)}")
        parts.append(f"Text:\n{str(input_data).strip()}")
        prompt = "\n\n".join(parts)
        req = PromptInterceptionRequest(
            input_prompt=input_data, prebuilt_prompt=prompt,
            model=llm_model, debug=True
        )
        response = asyncio.run(self.engine.process_request(req))
        output = response.output_str if response.success else ''

        self.results[node_id] = {
            'type': 'translation', 'output': output,
            'error': response.error if not response.success else None,
            'model': response.model_used
        }
        if output:
            self.recorder.save_entity(node_id=node_id, node_type='translation', content=output,
                                     metadata={'model': response.model_used})
        return output, 'text', None

    def _execute_model_adaption(self, node: Dict[str, Any], node_id: str,
                                input_data: Any) -> Tuple[str, str, None]:
        """Adapt the incoming prompt to the media model the node names.

        The step the flow runs between Prompt Interception and generation
        (/pipeline/optimize, execute_optimization): the adaption instruction of
        the target's output config, carried out by the model that config names
        for its adaption, else by the Stage 2 interception model, as there. A
        target whose config has no instruction passes the text on unchanged;
        for SD3.5 that is a decision (59eab5a8), and flux2 has none either.
        Where the flow falls back to the unadapted text when the model fails,
        this node stops its branch with the error, like every canvas node.
        Until 2026-09-27 the executor had no branch for this node, and every
        chain through it ended there without a message.
        """
        from my_app.routes.schema_pipeline_routes import (
            _load_optimization_instruction, _load_optimization_model,
            load_output_config_defaults,
        )
        from schemas.engine.instruction_selector import get_instruction

        if not input_data:
            self.results[node_id] = {'type': 'model_adaption', 'output': '', 'error': 'No input'}
            return '', 'text', None

        preset = node.get('modelAdaptionPreset') or 'none'
        config_id = _ADAPTION_CONFIGS.get(preset)
        if preset in _ADAPTION_MEDIA:
            config_id = (load_output_config_defaults() or {}).get(_ADAPTION_MEDIA[preset])
        instruction = _load_optimization_instruction(config_id) if config_id else None

        if not instruction:
            self.results[node_id] = {
                'type': 'model_adaption', 'output': input_data, 'error': None,
                'config_id': config_id, 'adapted': False,
            }
            self.recorder.save_entity(node_id=node_id, node_type='model_adaption', content=input_data,
                                     metadata={'config_id': config_id, 'adapted': False})
            logger.info(f"[Canvas Executor] Model Adaption {node_id}: '{preset}' has no instruction, text passes on")
            return input_data, 'text', None

        model = (_load_optimization_model(config_id)
                 or _configured_canvas_model('STAGE2_INTERCEPTION_MODEL'))
        req = PromptInterceptionRequest(
            input_prompt=input_data, input_context='', style_prompt=instruction,
            task_instruction=get_instruction('prompt_optimization'),
            model=model, debug=True, unload_model=False,
            parameters={'enable_thinking': False},
        )
        response = asyncio.run(self.engine.process_request(req))
        output = response.output_str if response.success else ''

        self.results[node_id] = {
            'type': 'model_adaption', 'output': output,
            'error': response.error if not response.success else None,
            'model': response.model_used, 'config_id': config_id, 'adapted': bool(output),
        }
        if output:
            self.recorder.save_entity(node_id=node_id, node_type='model_adaption', content=output,
                                     metadata={'model': response.model_used, 'config_id': config_id,
                                               'adapted': True})
        logger.info(f"[Canvas Executor] Model Adaption {node_id} ({config_id}): '{output[:50]}'")
        return output, 'text', None

    def _execute_seed(self, node: Dict[str, Any], node_id: str) -> Tuple[int, str, None]:
        seed_mode = node.get('seedMode', 'fixed')
        seed_value = node.get('seedValue', 42)
        seed_base = node.get('seedBase', 0)

        if seed_mode == 'fixed':
            output_seed = seed_value
        elif seed_mode == 'random':
            output_seed = random.randint(0, 2**32 - 1)
        elif seed_mode == 'batch' and self.run_seed is not None:
            # Use run_seed from batch execution
            output_seed = self.run_seed
        elif seed_mode == 'increment':
            # "Batch (+1)" on the Canvas: the base, plus the run's place in a
            # batch; the base alone outside one (types/canvas.ts `seedBase`).
            # It fell through to the bare base here, so every run of a batch
            # rendered with one seed.
            base = as_seed(seed_base)
            output_seed = None if base is None else base + (self.run_index or 0)
        else:
            output_seed = seed_base

        self.results[node_id] = {'type': 'seed', 'output': output_seed, 'error': None, 'seedMode': seed_mode}
        logger.info(f"[Canvas Executor] Seed: {output_seed} (mode={seed_mode})")
        return output_seed, 'seed', None

    def _execute_resolution(self, node: Dict[str, Any], node_id: str) -> Tuple[Dict[str, int], str, None]:
        """Execute resolution node - outputs width/height."""
        preset = node.get('resolutionPreset', 'square_1024')
        width = node.get('resolutionWidth', 1024)
        height = node.get('resolutionHeight', 1024)

        # Apply preset if not custom
        if preset == 'square_1024':
            width, height = 1024, 1024
        elif preset == 'portrait_768x1344':
            width, height = 768, 1344
        elif preset == 'landscape_1344x768':
            width, height = 1344, 768
        # 'custom' uses the explicit width/height values

        output = {'width': width, 'height': height}
        self.results[node_id] = {'type': 'resolution', 'output': output, 'error': None, 'preset': preset}
        logger.info(f"[Canvas Executor] Resolution: {width}x{height} (preset={preset})")
        return output, 'resolution', None

    def _execute_quality(self, node: Dict[str, Any], node_id: str) -> Tuple[Dict[str, Any], str, None]:
        """Execute quality node - outputs steps/cfg."""
        steps = node.get('qualitySteps', 25)
        cfg = node.get('qualityCfg', 5.5)

        output = {'steps': steps, 'cfg': cfg}
        self.results[node_id] = {'type': 'quality', 'output': output, 'error': None}
        logger.info(f"[Canvas Executor] Quality: steps={steps}, cfg={cfg}")
        return output, 'quality', None

    def _execute_generation(self, node: Dict[str, Any], node_id: str, input_data: Any,
                             connection_label: Optional[str] = None) -> Tuple[Any, str, Optional[Dict[str, Any]]]:
        from my_app.routes.schema_pipeline_routes import execute_stage4_generation_only

        config_id = node.get('configId')
        if not config_id:
            self.results[node_id] = {'type': 'generation', 'output': None, 'error': 'No config'}
            return None, 'image', None

        # --- Input accumulation (comparison_evaluator pattern) ---
        parameter_types = {'seed', 'resolution', 'quality'}
        expected_text = sum(
            1 for inc in self.incoming.get(node_id, [])
            if self.node_map.get(inc.get('source'), {}).get('type') not in parameter_types
        )

        if node_id not in self.generation_text_inputs:
            self.generation_text_inputs[node_id] = []

        # Accumulate text input from this call (skip parameter data)
        if isinstance(input_data, str):
            self.generation_text_inputs[node_id].append({
                'label': connection_label,
                'text': input_data
            })

        current_count = len(self.generation_text_inputs[node_id])
        logger.info(f"[Canvas Executor] Generation: {current_count}/{expected_text} text inputs")

        # Wait until all text inputs have been accumulated
        if expected_text > 1 and current_count < expected_text:
            return None, 'image', {'waiting': True}

        # --- All inputs received: determine primary and secondary ---
        text_inputs = self.generation_text_inputs[node_id]
        prompt_data = None
        secondary_text = None

        if len(text_inputs) == 1:
            prompt_data = text_inputs[0]['text']  # Single input → always primary
        elif len(text_inputs) >= 2:
            for ti in text_inputs:
                if ti['label'] == 'input-1':
                    prompt_data = ti['text']
                elif ti['label'] == 'input-2':
                    secondary_text = ti['text']
            # Fallback if labels missing
            if not prompt_data:
                prompt_data = text_inputs[0]['text']
                if len(text_inputs) > 1 and secondary_text is None:
                    secondary_text = text_inputs[1]['text']

        if secondary_text:
            logger.info(f"[Canvas Executor] Generation: primary={len(prompt_data or '')} chars, secondary={len(secondary_text)} chars")

        if not prompt_data:
            self.results[node_id] = {'type': 'generation', 'output': None, 'error': 'No input'}
            return None, 'image', None

        blocked = self._stage3_check(prompt_data, secondary_text)
        if blocked:
            self.results[node_id] = {'type': 'generation', 'output': None, 'error': blocked['reason'],
                                     'configId': config_id, 'blocked': blocked}
            logger.warning(f"[Canvas Executor] Generation {node_id}: refused at stage 3")
            return None, 'image', None

        # Ensure connected parameter nodes have executed (lazy dependency resolution)
        parameter_types_to_execute = ('seed', 'resolution', 'quality')
        for inc in self.incoming.get(node_id, []):
            source_id = inc.get('source')
            source_node = self.node_map.get(source_id)
            if source_node and source_node.get('type') in parameter_types_to_execute:
                if source_id not in self.results:
                    logger.info(f"[Canvas Executor] Generation triggering {source_node.get('type')} node {source_id}")
                    self._execute_node(source_node, None, 'parameter', None, None)

        # Collect parameters from connected parameter nodes
        generation_seed = None
        generation_width = None
        generation_height = None
        generation_steps = None
        generation_cfg = None

        for inc in self.incoming.get(node_id, []):
            source_id = inc.get('source')
            source_node = self.node_map.get(source_id)
            if not source_node:
                continue

            source_type = source_node.get('type')
            source_result = self.results.get(source_id)

            if source_type == 'seed' and source_result and source_result.get('output') is not None:
                generation_seed = int(source_result['output'])
            elif source_type == 'resolution' and source_result and source_result.get('output'):
                res_output = source_result['output']
                generation_width = res_output.get('width')
                generation_height = res_output.get('height')
            elif source_type == 'quality' and source_result and source_result.get('output'):
                quality_output = source_result['output']
                generation_steps = quality_output.get('steps')
                generation_cfg = quality_output.get('cfg')

        logger.info(f"[Canvas Executor] Generation params: seed={generation_seed}, width={generation_width}, height={generation_height}, steps={generation_steps}, cfg={generation_cfg}")

        # Use run_seed if no connected seed node (for batch execution)
        if generation_seed is None and self.run_seed is not None:
            generation_seed = self.run_seed

        try:
            # Each generation runs in its OWN sub-run (canvas run_id + node_id): an
            # isolated recorder, metadata.json and media URL. Sharing the canvas
            # run_id made every generation mint /<run>/0 (index collision), let the
            # canvas recorder clobber the pipeline recorder's output_image entity in
            # the shared metadata.json, and made both overwrite the same
            # _active_recorders cache slot -> media endpoint 404 -> card hung.
            gen_result = asyncio.run(execute_stage4_generation_only(
                prompt=prompt_data, output_config=config_id,
                safety_level=self.safety_level, run_id=f"{self.run_id}__{node_id}",
                device_id=self.device_id,
                seed=generation_seed,
                width=generation_width,
                height=generation_height,
                steps=generation_steps,
                cfg=generation_cfg,
                secondary_text=secondary_text,
                alpha_factor=node.get('alpha_factor'),
                fusion_strategy=node.get('fusion_strategy')
            ))
            if gen_result['success']:
                output = gen_result['media_output']
                # Propagate model metadata for Output Drawer attribution
                metadata = {
                    'config_id': config_id,
                    'display_name': config_id,  # Frontend resolves localized name
                    'seed': output.get('seed') if output else None,
                    'steps': generation_steps,
                    'cfg': generation_cfg,
                }
                # 2026-08-19: what the card in the output surface shows on its
                # BACK — the prompt, the model's sheet, the time, and the sub-run
                # the media URL carries. Without them that card had no back side
                # to turn to and the surface printed a config id and stopped.
                #
                # Carried in its OWN channel, not in the node result and not in
                # the collected item. Both of those go out twice in the
                # completion event -- `results` holds the generation node AND
                # the collector node, whose output IS the item list -- so a
                # sheet placed in either was serialised three times. Measured
                # for sd35_large the sheet is 8.2 kB per generation node. In
                # `card_meta` it is in the event once, keyed by node, and it is
                # in the run record for graphs that have no collector at all
                # (every graph Resona authors: canvas_graph_authoring.py).
                self.card_meta[node_id] = {
                    'prompt': prompt_data,
                    'model_meta': gen_result.get('model_meta'),
                    'created_at': int(time.time() * 1000),
                    'run_id': f"{self.run_id}__{node_id}",
                }
                self.results[node_id] = {'type': 'generation', 'output': output, 'error': None, 'configId': config_id, 'metadata': metadata}
                if output and output.get('url'):
                    self.recorder.save_image_from_url(
                        node_id=node_id,
                        url=output['url'],
                        config_id=config_id,
                        seed=output.get('seed')
                    )
                logger.info(f"[Canvas Executor] Generation: {output.get('url', 'no url')}")
                return output, 'image', None
            else:
                self.results[node_id] = {'type': 'generation', 'output': None, 'error': gen_result.get('error'), 'configId': config_id}
                if gen_result.get('blocked'):
                    # The picture check after generation (kids/youth): the
                    # board shows it in the platform's safety window.
                    self.results[node_id]['blocked'] = {
                        'stage': gen_result.get('stage') or 'vlm_safety',
                        'reason': gen_result.get('vlm_reason') or gen_result.get('error') or '',
                        'found_terms': [],
                        'vlm_description': gen_result.get('vlm_description'),
                    }
                return None, 'image', None
        except Exception as e:
            self.results[node_id] = {'type': 'generation', 'output': None, 'error': str(e), 'configId': config_id}
            return None, 'image', None

    def _stage3_check(self, prompt: str, secondary_text: Optional[str]) -> Optional[Dict[str, Any]]:
        """The flow's Stage 3 on what this run's generation is about to receive."""
        return canvas_stage3_verdict(prompt, secondary_text, self.safety_level,
                                     self.lang, self.device_id)

    def _execute_evaluation(self, node: Dict[str, Any], node_id: str, input_data: Any) -> Tuple[str, str, Dict[str, Any]]:
        llm_model = node.get('llmModel') or _configured_canvas_model('STAGE2_INTERCEPTION_MODEL')
        evaluation_prompt = node.get('evaluationPrompt', '')
        output_type_setting = node.get('outputType', 'all')

        if isinstance(input_data, dict) and input_data.get('url'):
            eval_input = f"[Media: {input_data.get('media_type', 'image')} at {input_data.get('url')}]"
        else:
            eval_input = input_data or ''

        if not eval_input:
            self.results[node_id] = {
                'type': 'evaluation',
                'outputs': {'pass': '', 'fail': '', 'commentary': ''},
                'metadata': {'binary': None, 'score': None, 'active_path': None},
                'error': 'No input'
            }
            return '', 'text', {'binary': None, 'score': None, 'active_path': None}

        instruction = f"{evaluation_prompt}\n\nProvide your evaluation in the following format:\n\nCOMMENTARY: [Your detailed evaluation and feedback]\n"
        if output_type_setting in ['score', 'all']:
            instruction += "SCORE: [Numeric score from 0 to 10 only]\n"
        instruction += "\nIMPORTANT: SCORE must be 0-10. Scores < 5 = FAILED, >= 5 = PASSED."

        req = PromptInterceptionRequest(
            input_prompt=eval_input, style_prompt=instruction,
            model=llm_model, debug=True
        )
        response = asyncio.run(self.engine.process_request(req))

        if not response.success:
            self.results[node_id] = {
                'type': 'evaluation',
                'outputs': {'pass': '', 'fail': '', 'commentary': ''},
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
        active_path = 'pass' if binary_result else 'fail'
        passthrough_text = eval_input
        commented_text = f"{eval_input}\n\nFEEDBACK: {commentary}"

        self.results[node_id] = {
            'type': 'evaluation',
            'outputs': {'pass': passthrough_text, 'fail': commented_text, 'commentary': commentary},
            'metadata': {'binary': binary_result, 'score': score, 'active_path': active_path},
            'error': None, 'model': response.model_used
        }
        if commentary:
            self.recorder.save_entity(node_id=node_id, node_type='evaluation', content=commentary,
                                     metadata={'score': score, 'binary': binary_result, 'active_path': active_path, 'model': response.model_used})
        logger.info(f"[Canvas Executor] Evaluation: score={score}, path={active_path}")
        return passthrough_text if binary_result else commented_text, 'text', {'binary': binary_result, 'score': score, 'active_path': active_path}

    def _execute_display(self, node: Dict[str, Any], node_id: str, input_data: Any, data_type: str) -> Tuple[None, str, None]:
        display_title = node.get('title', 'Display')
        display_mode = node.get('displayMode', 'inline')
        self.results[node_id] = {
            'type': 'display', 'output': input_data, 'error': None,
            'displayData': {'title': display_title, 'mode': display_mode, 'content': input_data, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')}
        }
        logger.info(f"[Canvas Executor] Display: '{display_title}'")
        return None, data_type, None

    def _execute_collector(self, node: Dict[str, Any], node_id: str, input_data: Any, data_type: str,
                          source_node_id: Optional[str], source_node_type: Optional[str]) -> Tuple[Any, str, None]:
        source_result = self.results.get(source_node_id, {}) if source_node_id else {}
        source_metadata = source_result.get('metadata')
        collector_item = {'nodeId': source_node_id or node_id, 'nodeType': source_node_type or data_type, 'output': input_data, 'error': None}
        # Always propagate metadata for Output Drawer attribution
        if source_metadata:
            if source_node_type == 'evaluation':
                collector_item['output'] = {'text': input_data, 'metadata': source_metadata}
            collector_item['metadata'] = source_metadata
        self.collector_items.append(collector_item)
        self.results[node_id] = {'type': 'collector', 'output': self.collector_items, 'error': None}
        logger.info(f"[Canvas Executor] Collector: {len(self.collector_items)} items")
        return input_data, data_type, None

    def _execute_comparison_evaluator(self, node: Dict[str, Any], node_id: str, input_data: Any,
                                      source_node_id: Optional[str], connection_label: Optional[str]) -> Tuple[Any, str, Optional[Dict[str, Any]]]:
        llm_model = node.get('comparisonLlmModel') or _configured_canvas_model('STAGE2_INTERCEPTION_MODEL')
        criteria = node.get('comparisonCriteria', '')
        expected_count = len(self.incoming.get(node_id, []))

        # Fail-closed (2026-07-16): an empty reading is not comparable material.
        # Comparing around it would hand the LLM a leading instruction and no
        # substance — the recipe for a confabulated pseudo-finding.
        if not (input_data or '').strip():
            error_msg = f"refused: empty input from '{source_node_id}' — nothing to compare"
            self.results[node_id] = {
                'type': 'comparison_evaluator', 'output': '', 'error': error_msg
            }
            logger.error(f"[Canvas Executor] Comparison {node_id}: {error_msg}")
            return '', 'text', None

        if node_id not in self.comparison_inputs:
            self.comparison_inputs[node_id] = []

        # Use connection label for ordering
        pipe_num = 0
        if connection_label and connection_label.startswith('input-'):
            try:
                pipe_num = int(connection_label.split('-')[1])
            except (ValueError, IndexError):
                pipe_num = len(self.comparison_inputs[node_id]) + 1
        else:
            pipe_num = len(self.comparison_inputs[node_id]) + 1

        self.comparison_inputs[node_id].append({
            'label': f'Text {pipe_num}',
            'pipe_num': pipe_num,
            'text': input_data or '',
            'source': source_node_id
        })

        current_count = len(self.comparison_inputs[node_id])
        logger.info(f"[Canvas Executor] Comparison: {current_count}/{expected_count} inputs (pipe {pipe_num})")

        if current_count < expected_count:
            self.results[node_id] = {
                'type': 'comparison_evaluator', 'output': None, 'error': None,
                'status': 'waiting', 'inputs_received': current_count, 'inputs_expected': expected_count
            }
            return None, 'text', {'waiting': True}

        # All inputs received - sort and run comparison
        inputs_list = sorted(self.comparison_inputs[node_id], key=lambda x: x.get('pipe_num', 0))
        formatted_inputs = "\n\n".join([
            f"=== {inp['label']} (Quelle: {inp['source']}) ===\n{inp['text']}"
            for inp in inputs_list
        ])

        instruction = f"""Analysiere und vergleiche die folgenden {len(inputs_list)} Texte systematisch.

{formatted_inputs}

EVALUATIONSKRITERIEN:
{criteria if criteria else 'Allgemeiner Vergleich nach Qualität, Klarheit und Vollständigkeit'}

Strukturiere deine Antwort klar und beziehe dich auf die Text-Nummern."""

        req = PromptInterceptionRequest(
            input_prompt="Führe die Analyse durch.",
            style_prompt=instruction, model=llm_model, debug=True
        )
        response = asyncio.run(self.engine.process_request(req))
        output = response.output_str if response.success else ''

        self.results[node_id] = {
            'type': 'comparison_evaluator', 'output': output,
            'error': response.error if not response.success else None,
            'model': response.model_used,
            'metadata': {'input_count': len(inputs_list), 'sources': [inp['source'] for inp in inputs_list]}
        }
        if output:
            self.recorder.save_entity(node_id=node_id, node_type='comparison_evaluator', content=output,
                                     metadata={'input_count': len(inputs_list), 'sources': [inp['source'] for inp in inputs_list], 'model': response.model_used})
        logger.info(f"[Canvas Executor] Comparison complete: {len(output)} chars")
        return output, 'text', None

    def _get_next_nodes(self, node_id: str, output_data: Any, output_type: str,
                        metadata: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get list of next nodes to execute based on connections."""
        node = self.node_map.get(node_id)
        node_type = node.get('type') if node else None

        # Parameter nodes (seed, resolution, quality) don't propagate to next nodes.
        # Their results are stored and the Generation node fetches them from self.results.
        # This prevents double-execution of Generation when both Input and Seed connect to it.
        if node_type in ('seed', 'resolution', 'quality'):
            return []

        next_conns = self.outgoing.get(node_id, [])
        if not next_conns:
            return []

        # For evaluation nodes: filter based on score
        # Labels 'pass'/'fail'/'feedback'/'commentary' are evaluation routing labels.
        # Any other label (e.g. 'input-1') is a target-side port identifier and
        # should follow the pass path (the normal forward direction).
        if node_type == 'evaluation' and metadata:
            EVAL_ROUTING_LABELS = {'passthrough', 'pass', 'commented', 'fail', 'feedback', 'commentary'}
            active_path = metadata.get('active_path')
            is_pass = active_path in ('passthrough', 'pass')
            filtered = []
            for conn in next_conns:
                label = conn.get('label')
                if not label:
                    filtered.append(conn)
                elif label not in EVAL_ROUTING_LABELS:
                    # Target-side label (e.g. "input-1") — follow on pass path
                    if is_pass:
                        filtered.append(conn)
                elif label == 'commentary':
                    filtered.append(conn)
                elif label in ('passthrough', 'pass'):
                    if is_pass:
                        filtered.append(conn)
                elif label in ('commented', 'fail', 'feedback'):
                    if not is_pass:
                        filtered.append(conn)
            next_conns = filtered

        result = []
        for conn in next_conns:
            target_id = conn['target']
            target_node = self.node_map.get(target_id)
            if not target_node:
                continue

            target_type = target_node.get('type')
            accepts_text = target_type in ['random_prompt', 'interception', 'translation', 'model_adaption', 'generation', 'evaluation', 'collector', 'display', 'comparison_evaluator']
            accepts_image = target_type in ['image_evaluation', 'evaluation', 'collector', 'display', 'generation']
            accepts_seed = target_type == 'generation'
            # Resolution and quality nodes output to generation
            accepts_resolution = target_type == 'generation'
            accepts_quality = target_type == 'generation'

            if output_type == 'text' and not accepts_text:
                continue
            if output_type == 'image' and not accepts_image:
                continue
            if output_type == 'seed' and not accepts_seed:
                continue
            if output_type == 'resolution' and not accepts_resolution:
                continue
            if output_type == 'quality' and not accepts_quality:
                continue

            # Determine the data to pass
            if node_type == 'evaluation' and metadata:
                conn_label = conn.get('label')
                if conn_label == 'commentary':
                    trace_data = self.results[node_id]['outputs']['commentary']
                elif conn_label in ('passthrough', 'pass'):
                    trace_data = self.results[node_id]['outputs']['pass']
                elif conn_label in ('commented', 'fail', 'feedback'):
                    trace_data = self.results[node_id]['outputs']['fail']
                else:
                    # Target-side label (e.g. "input-1"): use pass output
                    trace_data = self.results[node_id]['outputs']['pass']
            else:
                trace_data = output_data

            result.append({
                'node_id': target_id,
                'input_data': trace_data,
                'data_type': output_type,
                'source_node_id': node_id,
                'source_node_type': node_type,
                'connection_label': conn.get('label')
            })

        return result
