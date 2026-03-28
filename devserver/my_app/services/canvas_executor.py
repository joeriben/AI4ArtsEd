"""
Canvas Workflow Executor - Core execution engine for Canvas workflows

Session 150: Extracted from canvas_routes.py to provide shared execution logic
for both single execution and batch execution endpoints.

Usage:
    executor = CanvasWorkflowExecutor(nodes, connections, recorder, run_id, engine)
    for event_type, event_data in executor.execute_with_events():
        # Handle progress/node_complete events
    result = executor.get_result()
"""
import logging
import asyncio
import random
import time
from typing import Dict, List, Any, Optional, Generator, Tuple

from schemas.engine.prompt_interception_engine import PromptInterceptionEngine, PromptInterceptionRequest

logger = logging.getLogger(__name__)

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
        device_id: Optional[str] = None
    ):
        self.nodes = nodes
        self.connections = connections
        self.recorder = recorder
        self.run_id = run_id
        self.engine = engine
        self.prompt_override = prompt_override
        self.run_seed = run_seed
        self.device_id = device_id

        # Execution state
        self.results: Dict[str, Any] = {}
        self.collector_items: List[Dict[str, Any]] = []
        self.comparison_inputs: Dict[str, List[Dict[str, Any]]] = {}
        self.generation_text_inputs: Dict[str, List[Dict[str, Any]]] = {}
        self.execution_trace: List[str] = []
        self.execution_count = 0
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

            # Add next nodes to work queue
            next_nodes = self._get_next_nodes(node_id, output_data, output_type, metadata)
            work_queue.extend(next_nodes)

        logger.info(f"[Canvas Executor] Complete. {self.execution_count} executions, {len(self.collector_items)} collected")
        logger.info(f"[Canvas Executor] Trace: {' -> '.join(self.execution_trace)}")

        self._final_result = {
            'success': True,
            'results': self.results,
            'collector_items': self.collector_items,
            'execution_trace': self.execution_trace
        }

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
                # Session 152: Image input nodes are always source nodes
                source_nodes.append(n)
            elif ntype == 'random_prompt' and not self.incoming.get(n['id']):
                source_nodes.append(n)
            elif ntype == 'seed':
                # Session 151: Seed nodes are always source nodes (no incoming connections)
                source_nodes.append(n)
            elif ntype == 'resolution':
                # Session 151: Resolution nodes are always source nodes
                source_nodes.append(n)
            elif ntype == 'quality':
                # Session 151: Quality nodes are always source nodes
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
        """Session 152: Execute image_input node - outputs uploaded image data."""
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
        """Session 152: Execute image_evaluation node - Vision-LLM analysis of images."""
        from my_app.utils.image_analysis import analyze_image
        from config import IMAGE_ANALYSIS_PROMPTS, DEFAULT_LANGUAGE

        vision_model = node.get('visionModel', 'local/llama3.2-vision:latest')
        preset = node.get('imageEvaluationPreset', 'bildwissenschaftlich')
        custom_prompt = node.get('imageEvaluationPrompt', '')

        # Validate input is an image
        if data_type != 'image' or not isinstance(input_data, dict):
            self.results[node_id] = {
                'type': 'image_evaluation',
                'output': '',
                'error': 'Expected image input'
            }
            return '', 'text', None

        # Get image path (prefer absolute path, fallback to URL)
        image_path = input_data.get('image_path')
        image_url = input_data.get('url')

        if not image_path and not image_url:
            self.results[node_id] = {
                'type': 'image_evaluation',
                'output': '',
                'error': 'No image path or URL'
            }
            return '', 'text', None

        # Determine analysis prompt
        if preset == 'custom' and custom_prompt:
            analysis_prompt = custom_prompt
        else:
            # Use configured prompts from config.py
            try:
                analysis_prompt = IMAGE_ANALYSIS_PROMPTS[preset][DEFAULT_LANGUAGE]
            except KeyError:
                analysis_prompt = "Analyze this image thoroughly."
                logger.warning(f"[Canvas Executor] Image eval preset '{preset}' not found, using fallback")

        try:
            # Use existing image analysis helper (calls local VLM)
            # Note: analyze_image handles both file paths and base64
            # Session 152: Pass selected vision model from node
            analysis_text = analyze_image(
                image_path=image_path or image_url,
                prompt=analysis_prompt,
                analysis_type=preset,
                model=vision_model
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
        llm_model = node.get('randomPromptModel', 'local/mistral-nemo')
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
        llm_model = node.get('llmModel', 'local/mistral-nemo')
        context_prompt = node.get('contextPrompt', '')

        if not input_data:
            self.results[node_id] = {'type': 'interception', 'output': '', 'error': 'No input'}
            return '', 'text', None

        req = PromptInterceptionRequest(
            input_prompt=input_data, style_prompt=context_prompt,
            model=llm_model, debug=True
        )
        response = asyncio.run(self.engine.process_request(req))
        output = response.output_str if response.success else ''

        self.results[node_id] = {
            'type': 'interception', 'output': output,
            'error': response.error if not response.success else None,
            'model': response.model_used
        }
        if output:
            self.recorder.save_entity(node_id=node_id, node_type='interception', content=output,
                                     metadata={'model': response.model_used})
        logger.info(f"[Canvas Executor] Interception: '{output[:50]}...' if output else ''")
        return output, 'text', None

    def _execute_translation(self, node: Dict[str, Any], node_id: str, input_data: Any) -> Tuple[str, str, None]:
        llm_model = node.get('llmModel', 'local/mistral-nemo')
        translation_prompt = node.get('translationPrompt', 'Translate to English:')

        if not input_data:
            self.results[node_id] = {'type': 'translation', 'output': '', 'error': 'No input'}
            return '', 'text', None

        req = PromptInterceptionRequest(
            input_prompt=input_data, style_prompt=translation_prompt,
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
        else:
            output_seed = seed_base

        self.results[node_id] = {'type': 'seed', 'output': output_seed, 'error': None, 'seedMode': seed_mode}
        logger.info(f"[Canvas Executor] Seed: {output_seed} (mode={seed_mode})")
        return output_seed, 'seed', None

    def _execute_resolution(self, node: Dict[str, Any], node_id: str) -> Tuple[Dict[str, int], str, None]:
        """Session 151: Execute resolution node - outputs width/height."""
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
        """Session 151: Execute quality node - outputs steps/cfg."""
        steps = node.get('qualitySteps', 25)
        cfg = node.get('qualityCfg', 5.5)

        output = {'steps': steps, 'cfg': cfg}
        self.results[node_id] = {'type': 'quality', 'output': output, 'error': None}
        logger.info(f"[Canvas Executor] Quality: steps={steps}, cfg={cfg}")
        return output, 'quality', None

    def _execute_generation(self, node: Dict[str, Any], node_id: str, input_data: Any,
                             connection_label: Optional[str] = None) -> Tuple[Any, str, Optional[Dict[str, Any]]]:
        from my_app.routes.schema_pipeline_routes import execute_stage4_generation_only
        from config import DEFAULT_SAFETY_LEVEL

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

        # Session 155: Ensure connected parameter nodes have executed (lazy dependency resolution)
        parameter_types_to_execute = ('seed', 'resolution', 'quality')
        for inc in self.incoming.get(node_id, []):
            source_id = inc.get('source')
            source_node = self.node_map.get(source_id)
            if source_node and source_node.get('type') in parameter_types_to_execute:
                if source_id not in self.results:
                    logger.info(f"[Canvas Executor] Generation triggering {source_node.get('type')} node {source_id}")
                    self._execute_node(source_node, None, 'parameter', None, None)

        # Session 151: Collect parameters from connected parameter nodes
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
            gen_result = asyncio.run(execute_stage4_generation_only(
                prompt=prompt_data, output_config=config_id,
                safety_level=DEFAULT_SAFETY_LEVEL, run_id=self.run_id,
                device_id=self.device_id,
                seed=generation_seed,
                width=generation_width,
                height=generation_height,
                steps=generation_steps,
                cfg=generation_cfg,
                secondary_text=secondary_text
            ))
            if gen_result['success']:
                output = gen_result['media_output']
                # Session 256: Propagate model metadata for Output Drawer attribution
                metadata = {
                    'config_id': config_id,
                    'display_name': config_id,  # Frontend resolves localized name
                    'seed': output.get('seed') if output else None,
                    'steps': generation_steps,
                    'cfg': generation_cfg,
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
                return None, 'image', None
        except Exception as e:
            self.results[node_id] = {'type': 'generation', 'output': None, 'error': str(e), 'configId': config_id}
            return None, 'image', None

    def _execute_evaluation(self, node: Dict[str, Any], node_id: str, input_data: Any) -> Tuple[str, str, Dict[str, Any]]:
        llm_model = node.get('llmModel', 'local/mistral-nemo')
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
        # Session 256: Always propagate metadata for Output Drawer attribution
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
        llm_model = node.get('comparisonLlmModel', 'local/mistral-nemo')
        criteria = node.get('comparisonCriteria', '')
        expected_count = len(self.incoming.get(node_id, []))

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

        # Session 151: Parameter nodes (seed, resolution, quality) don't propagate to next nodes.
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
            accepts_text = target_type in ['random_prompt', 'interception', 'translation', 'generation', 'evaluation', 'collector', 'display', 'comparison_evaluator']
            accepts_image = target_type in ['image_evaluation', 'evaluation', 'collector', 'display', 'generation']
            accepts_seed = target_type == 'generation'
            # Session 151: Resolution and quality nodes output to generation
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
