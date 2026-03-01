"""
Backend-Router: Multi-Backend-Support für Schema-Pipelines
"""
import logging
from typing import Dict, Any, Optional, AsyncGenerator, Tuple, Union, List
from dataclasses import dataclass
from enum import Enum
import asyncio
from pathlib import Path
import json

from my_app.services.pipeline_recorder import load_recorder
from config import JSON_STORAGE_DIR, COMFYUI_BASE_PATH, LORA_TRIGGERS, COMFYUI_DIRECT
from schemas.engine.progress_callback import get_progress_callback

logger = logging.getLogger(__name__)


def _find_entity_by_type(entities: list, media_type: str) -> dict:
    """Find entity in entities array by media type."""
    for entity in entities:
        entity_type = entity.get('type', '')
        if entity_type == f'output_{media_type}':
            return entity
    for entity in entities:
        if entity.get('type') == media_type:
            return entity
    return None


def _resolve_media_url_to_path(url_or_path: str) -> str:
    """
    Resolve media URL to filesystem path.

    Handles both URL formats:
    - /api/media/image/<run_id>
    - /api/media/image/<run_id>/<index>

    Resolves to actual file path. Otherwise returns the input unchanged.
    """
    if url_or_path.startswith('/api/media/image/'):
        path_part = url_or_path.replace('/api/media/image/', '')
        # Handle both /run_id and /run_id/index formats
        parts = path_part.split('/')
        run_id = parts[0]
        try:
            recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
            if recorder:
                image_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'image')
                if image_entity:
                    # Session 130: Files are in final/ subfolder
                    resolved_path = str(recorder.final_folder / image_entity['filename'])
                    logger.info(f"[URL-RESOLVE] {url_or_path} → {resolved_path}")
                    return resolved_path
        except Exception as e:
            logger.error(f"[URL-RESOLVE] Failed to resolve {url_or_path}: {e}")

    return url_or_path


def _adapt_workflow_for_multi_image(workflow: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dynamically adapt workflow based on number of provided images.
    Removes unused LoadImage and Scale nodes when fewer than 3 images are provided.

    Args:
        workflow: Complete ComfyUI workflow dictionary
        parameters: Request parameters containing input_image1/2/3

    Returns:
        Modified workflow with unused nodes removed
    """
    # Detect which images are provided
    has_image1 = 'input_image1' in parameters and parameters['input_image1']
    has_image2 = 'input_image2' in parameters and parameters['input_image2']
    has_image3 = 'input_image3' in parameters and parameters['input_image3']

    logger.info(f"[MULTI-IMAGE-ADAPT] Images provided: image1={has_image1}, image2={has_image2}, image3={has_image3}")

    # Remove unused LoadImage and Scale nodes
    removed_nodes = []

    if not has_image2:
        if '120' in workflow:
            del workflow['120']  # LoadImage 2
            removed_nodes.append('120 (LoadImage 2)')
        if '122' in workflow:
            del workflow['122']  # Scale 2
            removed_nodes.append('122 (Scale 2)')

    if not has_image3:
        if '121' in workflow:
            del workflow['121']  # LoadImage 3
            removed_nodes.append('121 (LoadImage 3)')
        if '123' in workflow:
            del workflow['123']  # Scale 3
            removed_nodes.append('123 (Scale 3)')

    if removed_nodes:
        logger.info(f"[MULTI-IMAGE-ADAPT] Removed unused nodes: {', '.join(removed_nodes)}")

    # Update TextEncodeQwenImageEditPlus nodes - remove unused image inputs
    for node_id in ['115:110', '115:111']:
        if node_id in workflow:
            inputs = workflow[node_id].get('inputs', {})
            removed_inputs = []

            if not has_image2 and 'image2' in inputs:
                del inputs['image2']
                removed_inputs.append('image2')

            if not has_image3 and 'image3' in inputs:
                del inputs['image3']
                removed_inputs.append('image3')

            if removed_inputs:
                logger.info(f"[MULTI-IMAGE-ADAPT] Node {node_id}: Removed inputs {', '.join(removed_inputs)}")

    return workflow


class BackendType(Enum):
    """Backend-Typen"""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    MISTRAL = "mistral"
    AWS_BEDROCK = "bedrock"
    COMFYUI = "comfyui"
    # Session 149: New inference backends for SwarmUI/ComfyUI independence
    TRITON = "triton"      # NVIDIA Triton Inference Server (batched, multi-user)
    DIFFUSERS = "diffusers"  # Direct HuggingFace Diffusers (TensorRT optional)
    # Python chunks: Self-contained executable Python modules (HeartMuLa, future backends)
    PYTHON = "python"

@dataclass
class BackendRequest:
    """Request für Backend-Verarbeitung"""
    backend_type: BackendType
    model: str
    prompt: str
    parameters: Dict[str, Any]
    stream: bool = False

@dataclass 
class BackendResponse:
    """Response von Backend"""
    success: bool
    content: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class BackendRouter:
    """Router für verschiedene KI-Backends"""

    def __init__(self):
        self.backends: Dict[BackendType, Any] = {}
        self._initialized = False

        # Initialize manager for auto-recovery (ComfyUI direct or SwarmUI legacy)
        if COMFYUI_DIRECT:
            from my_app.services.comfyui_manager import get_comfyui_manager
            self.comfyui_manager = get_comfyui_manager()
            # Alias for backward compatibility in methods that reference swarmui_manager
            self.swarmui_manager = self.comfyui_manager
            logger.info("[ROUTER] Using COMFYUI_DIRECT mode (WebSocket client)")
        else:
            from my_app.services.swarmui_manager import get_swarmui_manager
            self.swarmui_manager = get_swarmui_manager()
            self.comfyui_manager = self.swarmui_manager
            logger.info("[ROUTER] Using legacy SwarmUI mode")
    
    def initialize(self, ollama_service=None, workflow_logic_service=None, comfyui_service=None):
        """Router mit Legacy-Services initialisieren"""
        if ollama_service:
            self.backends[BackendType.OLLAMA] = ollama_service
            logger.info("Ollama-Backend registriert")
        
        if comfyui_service:
            self.backends[BackendType.COMFYUI] = comfyui_service
            logger.info("ComfyUI-Backend registriert")
            
        self._initialized = True
        logger.info(f"Backend-Router initialisiert mit {len(self.backends)} Backends")

    async def _fallback_to_comfyui(self, chunk: Dict[str, Any], chunk_name: str, prompt: str, parameters: Dict[str, Any], reason: str) -> BackendResponse:
        """
        Generic fallback to ComfyUI for direct backends.

        Loads the fallback_chunk from chunk meta and executes it via ComfyUI workflow.
        Used by all direct backends (diffusers, stable_audio, heartmula, etc.) when
        they are unavailable or fail.

        Args:
            chunk: Current chunk configuration (must have meta.fallback_chunk)
            chunk_name: Name of the current chunk (for logging)
            prompt: The prompt to pass to fallback
            parameters: Parameters to pass to fallback
            reason: Why fallback was triggered (for logging)

        Returns:
            BackendResponse from ComfyUI fallback, or error if no fallback available
        """
        fallback_chunk_name = chunk.get('meta', {}).get('fallback_chunk')

        if not fallback_chunk_name:
            logger.error(f"[FALLBACK] No fallback_chunk defined in {chunk_name}.meta")
            return BackendResponse(
                success=False,
                content="",
                error=f"Direct backend unavailable ({reason}) and no fallback_chunk defined"
            )

        logger.info(f"[FALLBACK] {chunk_name}: {reason} -> falling back to ComfyUI chunk '{fallback_chunk_name}'")

        fallback_chunk = self._load_output_chunk(fallback_chunk_name)
        if not fallback_chunk:
            logger.error(f"[FALLBACK] Fallback chunk '{fallback_chunk_name}' not found")
            return BackendResponse(
                success=False,
                content="",
                error=f"Fallback chunk '{fallback_chunk_name}' not found"
            )

        return await self._process_workflow_chunk(fallback_chunk_name, prompt, parameters, fallback_chunk)

    async def process_request(self, request: BackendRequest) -> Union[BackendResponse, AsyncGenerator[str, None]]:
        """Request an entsprechendes Backend weiterleiten"""
        try:
            # IMPORTANT: Detect actual backend from model prefix, not template backend_type
            # This allows execution_mode to override the template's backend_type
            actual_backend = self._detect_backend_from_model(request.model, request.backend_type)

            # Check if this is an Output-Chunk request (has workflow dict OR unknown backend type)
            # Output-Chunks can be:
            # 1. Python chunks (backend_type not in known LLM backends)
            # 2. JSON chunks with workflow dict
            is_output_chunk = (
                isinstance(request.prompt, dict) or  # Workflow dict
                actual_backend not in [BackendType.OLLAMA, BackendType.OPENROUTER, BackendType.ANTHROPIC,
                                      BackendType.OPENAI, BackendType.MISTRAL, BackendType.AWS_BEDROCK, BackendType.COMFYUI]
            )

            if is_output_chunk:
                # Output-Chunk: Route to _process_output_chunk
                # Extract chunk_name from parameters (set by ChunkBuilder)
                chunk_name = request.parameters.get('_chunk_name') or request.parameters.get('chunk_name')
                if not chunk_name:
                    # Fallback: Try to infer from metadata or fail gracefully
                    logger.warning("[ROUTER] Output-Chunk detected but no chunk_name in parameters")
                    chunk_name = "unknown"

                logger.info(f"[ROUTER] Routing Output-Chunk: {chunk_name} (backend_type={actual_backend.value})")
                return await self._process_output_chunk(chunk_name, request.prompt, request.parameters)

            # Schema-Pipelines: All LLM providers via Prompt Interception Engine
            if actual_backend in [BackendType.OLLAMA, BackendType.OPENROUTER, BackendType.ANTHROPIC, BackendType.OPENAI, BackendType.MISTRAL, BackendType.AWS_BEDROCK]:
                # Create modified request with detected backend for proper routing
                modified_request = BackendRequest(
                    backend_type=actual_backend,
                    model=request.model,
                    prompt=request.prompt,
                    parameters=request.parameters,
                    stream=request.stream
                )
                return await self._process_prompt_interception_request(modified_request)
            elif actual_backend == BackendType.COMFYUI:
                # ComfyUI braucht kein registriertes Backend - verwendet direkt ComfyUI-Client
                return await self._process_comfyui_request(None, request)
            else:
                return BackendResponse(
                    success=False,
                    content="",
                    error=f"Backend-Typ {actual_backend.value} nicht implementiert"
                )
        except Exception as e:
            logger.error(f"Fehler bei Backend-Verarbeitung: {e}")
            return BackendResponse(
                success=False,
                content="",
                error=str(e)
            )
    
    def _detect_backend_from_model(self, model: str, fallback_backend: BackendType) -> BackendType:
        """
        Detect backend from model prefix
        This allows execution_mode to override template's backend_type

        Supported prefixes:
        - local/model-name → OLLAMA (local inference)
        - bedrock/model-name → AWS_BEDROCK (Anthropic via AWS Bedrock, EU region)
        - anthropic/model-name → ANTHROPIC (direct API)
        - openai/model-name → OPENAI (direct API)
        - mistral/model-name → MISTRAL (direct API, EU-based)
        - openrouter/provider/model-name → OPENROUTER (aggregator API)

        Args:
            model: Model string (may have provider prefix)
            fallback_backend: Fallback if no prefix detected

        Returns:
            Detected backend type
        """
        # Empty model or prefix-only → use fallback
        # This is important for Proxy-Chunks (output_image) which have empty model
        if not model or model in ["local/", "bedrock/", "openrouter/", "anthropic/", "openai/", "mistral/", ""]:
            logger.debug(f"[BACKEND-DETECT] Model '{model}' empty or prefix-only → {fallback_backend.value} (fallback)")
            return fallback_backend

        # Check provider prefixes
        if model.startswith("bedrock/"):
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → AWS_BEDROCK (Anthropic via AWS EU)")
            return BackendType.AWS_BEDROCK
        elif model.startswith("anthropic/"):
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → ANTHROPIC (direct API)")
            return BackendType.ANTHROPIC
        elif model.startswith("openai/"):
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → OPENAI (direct API)")
            return BackendType.OPENAI
        elif model.startswith("mistral/"):
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → MISTRAL (EU-based direct API)")
            return BackendType.MISTRAL
        elif model.startswith("openrouter/"):
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → OPENROUTER (aggregator)")
            return BackendType.OPENROUTER
        elif model.startswith("local/"):
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → OLLAMA (local)")
            return BackendType.OLLAMA
        else:
            # No prefix, use fallback
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → {fallback_backend.value} (fallback)")
            return fallback_backend
    
    async def _process_prompt_interception_request(self, request: BackendRequest) -> BackendResponse:
        """Schema-Pipeline-Request über Prompt Interception Engine

        Architecture fix: ChunkBuilder builds the complete prompt via manipulate.json template.
        We pass it directly to the engine — no destructive parse/rebuild cycle.
        Previously, _parse_template_to_prompt_format() split the prompt on '\\n\\n' which
        destroyed the Task/Context/Prompt structure and dropped sections like CULTURAL RESPECT.
        """
        try:
            from .prompt_interception_engine import PromptInterceptionEngine, PromptInterceptionRequest

            # Model already has prefix from ModelSelector - use as-is!
            model = request.model
            logger.info(f"[BACKEND] Using model: {model}")

            # Pass pre-built prompt directly — ChunkBuilder already assembled it correctly
            pi_engine = PromptInterceptionEngine()
            pi_request = PromptInterceptionRequest(
                input_prompt="",
                prebuilt_prompt=request.prompt,
                model=model,
                debug=request.parameters.get('debug', False),
                unload_model=request.parameters.get('unload_model', False),
                parameters=request.parameters,
            )
            
            # Engine-Request ausführen
            pi_response = await pi_engine.process_request(pi_request)

            if pi_response.success:
                # Use backend from modified_request (already set correctly in process_request)
                # Note: request here is the modified_request which has backend_type=actual_backend
                return BackendResponse(
                    success=True,
                    content=pi_response.output_str,
                    metadata={
                        'model_used': pi_response.model_used,
                        'backend_type': request.backend_type.value
                    }
                )
            else:
                return BackendResponse(
                    success=False,
                    content="",
                    error=pi_response.error
                )
                
        except Exception as e:
            logger.error(f"Prompt Interception Engine Fehler: {e}")
            return BackendResponse(
                success=False,
                content="",
                error=f"Prompt Interception Engine Fehler: {str(e)}"
            )
    
    def _parse_template_to_prompt_format(self, template_result: str) -> tuple[str, str, str]:
        """Parse Template-Result zu Task+Context+Prompt Format"""
        # Template-Result ist bereits fertig aufgebaut aus ChunkBuilder
        # Für Schema-Pipelines: Template enthält INSTRUCTIONS + INPUT_TEXT/PREVIOUS_OUTPUT
        
        # Einfache Heuristik: Teile bei ersten Doppel-Newlines
        parts = template_result.split('\n\n', 2)
        
        if len(parts) >= 3:
            # Task: Instructions, Context: leer, Prompt: Text
            style_prompt = parts[0]
            input_context = ""  
            input_prompt = parts[2] if len(parts) > 2 else parts[1]
        elif len(parts) == 2:
            # Instructions + Text
            style_prompt = parts[0]
            input_context = ""
            input_prompt = parts[1]
        else:
            # Nur Text
            style_prompt = ""
            input_context = ""
            input_prompt = template_result
        
        return input_prompt, input_context, style_prompt
    
    async def _process_ollama_request(self, ollama_service, request: BackendRequest) -> BackendResponse:
        """Ollama-Request verarbeiten - Legacy-Service nutzen"""
        try:
            # Legacy ollama_service.py wiederverwenden
            if hasattr(ollama_service, 'generate_completion'):
                result = await ollama_service.generate_completion(
                    model=request.model,
                    prompt=request.prompt,
                    **request.parameters
                )
            elif hasattr(ollama_service, 'generate'):
                result = await ollama_service.generate(
                    model=request.model,
                    prompt=request.prompt,
                    **request.parameters
                )
            else:
                # Fallback auf direkte API-Calls
                result = await ollama_service.call_api(
                    model=request.model,
                    prompt=request.prompt,
                    **request.parameters
                )
            
            return BackendResponse(
                success=True,
                content=result.get('response', ''),
                metadata=result
            )
            
        except Exception as e:
            logger.error(f"Ollama-Backend-Fehler: {e}")
            return BackendResponse(
                success=False,
                content="",
                error=f"Ollama-Service-Fehler: {str(e)}"
            )
    
    async def _process_direct_request(self, workflow_service, request: BackendRequest) -> BackendResponse:
        """Direct-Request verarbeiten - Legacy workflow_logic_service nutzen"""
        try:
            # Legacy workflow_logic_service.py wiederverwenden
            result = await workflow_service.process_text(
                text=request.prompt,
                parameters=request.parameters
            )
            
            return BackendResponse(
                success=True,
                content=result.get('processed_text', request.prompt),
                metadata=result
            )
            
        except Exception as e:
            logger.error(f"Direct-Backend-Fehler: {e}")
            return BackendResponse(
                success=False,
                content="",
                error=f"Workflow-Service-Fehler: {str(e)}"
            )
    
    async def _process_comfyui_request(self, comfyui_service, request: BackendRequest) -> BackendResponse:
        """ComfyUI-Request verarbeiten mit Output-Chunks oder Legacy-Workflow-Generator"""
        try:
            # Schema-Pipeline-Output ist der optimierte Prompt
            schema_output = request.prompt

            # Check if we have an output_chunk specified
            output_chunk_name = request.parameters.get('output_chunk')

            if output_chunk_name:
                # Python chunks (new standard) bypass JSON type-routing
                chunk_py_path = Path(__file__).parent.parent / "chunks" / f"{output_chunk_name}.py"
                if chunk_py_path.exists():
                    return await self._process_output_chunk(output_chunk_name, schema_output, request.parameters)

                # Load JSON chunk to check type (legacy)
                chunk = self._load_output_chunk(output_chunk_name)

                if not chunk:
                    return BackendResponse(
                        success=False,
                        content="",
                        error=f"Output-Chunk '{output_chunk_name}' not found"
                    )

                # Route based on chunk type
                if chunk.get('type') == 'text_passthrough':
                    # Text passthrough: return input unchanged (code output, frontend handles display)
                    logger.info(f"[TEXT-PASSTHROUGH] Chunk {output_chunk_name}: returning input as-is for frontend processing")
                    return BackendResponse(
                        success=True,
                        content=schema_output,
                        metadata={
                            'chunk_name': output_chunk_name,
                            'media_type': chunk.get('media_type', 'code'),
                            'backend_type': chunk.get('backend_type'),
                            'frontend_processor': chunk.get('meta', {}).get('frontend_processor'),
                            'passthrough': True
                        }
                    )
                elif chunk.get('type') == 'api_output_chunk':
                    # API-based generation (OpenRouter, Replicate, etc.)
                    return await self._process_api_output_chunk(output_chunk_name, schema_output, request.parameters, chunk)
                else:
                    # ComfyUI workflow-based generation
                    return await self._process_output_chunk(output_chunk_name, schema_output, request.parameters)
            else:
                # LEGACY PATH: Use deprecated comfyui_workflow_generator
                # This will be removed after all chunks are migrated
                logger.warning("Using deprecated comfyui_workflow_generator - migrate to Output-Chunks!")
                return await self._process_comfyui_legacy(schema_output, request.parameters)

        except Exception as e:
            logger.error(f"ComfyUI-Backend-Fehler: {e}")
            import traceback
            traceback.print_exc()
            return BackendResponse(
                success=False,
                content="",
                error=f"ComfyUI-Service-Fehler: {str(e)}"
            )

    async def _process_output_chunk(self, chunk_name: str, prompt: str, parameters: Dict[str, Any]) -> BackendResponse:
        """Process Output-Chunk: Route based on execution mode and media type

        NOTE: For output chunks, the 'prompt' parameter contains the workflow dict,
        and the actual text prompt is in parameters['prompt'] or parameters.get('previous_output').

        - Python Chunks (.py): Execute directly via importlib
        - Legacy Workflows: Use complete workflow passthrough with title-based prompt injection
        - Images: Use SwarmUI /API/GenerateText2Image (simple, fast)
        - Audio/Video: Use custom workflow submission via /ComfyBackendDirect
        """
        try:
            # 1. Check for Python-Chunk first (new standard)
            chunk_py_path = Path(__file__).parent.parent / "chunks" / f"{chunk_name}.py"
            if chunk_py_path.exists():
                logger.info(f"[ROUTER] Detected Python chunk: {chunk_name}.py")
                result = await self._execute_python_chunk(chunk_py_path, parameters)
                if result.success:
                    return result

                # Fallback: Read CHUNK_META.fallback_chunk from the loaded module
                import sys
                module = sys.modules.get(f"chunk_{chunk_name}")
                fallback_name = getattr(module, 'CHUNK_META', {}).get('fallback_chunk') if module else None
                if fallback_name:
                    text_prompt = parameters.get('prompt', '') or parameters.get('PREVIOUS_OUTPUT', '') or parameters.get('TEXT_1', '')
                    logger.info(f"[FALLBACK] Python chunk '{chunk_name}' failed ({result.error}), trying '{fallback_name}'")
                    fallback_chunk = self._load_output_chunk(fallback_name)
                    if fallback_chunk:
                        return await self._process_workflow_chunk(fallback_name, text_prompt, parameters, fallback_chunk)
                return result

            # 2. Load Output-Chunk from JSON (legacy)
            chunk = self._load_output_chunk(chunk_name)
            if not chunk:
                return BackendResponse(
                    success=False,
                    content="",
                    error=f"Output-Chunk '{chunk_name}' not found (.json or .py)"
                )

            media_type = chunk.get('media_type', 'image')
            execution_mode = chunk.get('execution_mode', 'standard')
            backend_type = chunk.get('backend_type', 'comfyui')
            logger.info(f"Loaded Output-Chunk: {chunk_name} ({media_type} media, {execution_mode} mode, {backend_type} backend)")

            # FIX: Extract text prompt from parameters (not from 'prompt' param which is workflow dict)
            text_prompt = parameters.get('prompt', '') or parameters.get('PREVIOUS_OUTPUT', '')
            logger.info(f"[DEBUG-FIX] Extracted text_prompt from parameters: '{text_prompt[:200]}...'" if text_prompt else f"[DEBUG-FIX] ⚠️ No text prompt in parameters!")

            # Session 149: Route based on backend_type FIRST (before execution_mode)
            # This enables alternative backends (Triton, Diffusers) without ComfyUI
            if backend_type == 'triton':
                logger.info(f"[ROUTER] Using Triton backend for '{chunk_name}'")
                return await self._process_triton_chunk(chunk_name, text_prompt, parameters, chunk)
            elif backend_type == 'heartmula':
                logger.info(f"[ROUTER] Using HeartMuLa backend for '{chunk_name}'")
                return await self._process_heartmula_chunk(chunk_name, text_prompt, parameters, chunk)
            elif backend_type == 'stable_audio':
                logger.info(f"[ROUTER] Using Stable Audio backend for '{chunk_name}'")
                return await self._process_stable_audio_chunk(chunk_name, text_prompt, parameters, chunk)

            # 2. Route based on execution mode (for ComfyUI backend)
            if execution_mode == 'legacy_workflow':
                # TODO (2026 Refactoring): Move this logic into pipeline itself
                # Legacy workflow: complete workflow passthrough
                return await self._process_legacy_workflow(chunk, text_prompt, parameters)

            # 3. Then route based on media type (standard mode)
            if media_type == 'image':
                # Check if chunk requires workflow mode (custom nodes like Qwen VL, Mistral CLIP)
                requires_workflow = chunk.get('requires_workflow', False)
                # Check if LoRAs are configured (config-specific or global)
                has_loras = bool(parameters.get('loras', LORA_TRIGGERS))

                if requires_workflow or has_loras:
                    logger.info(f"[ROUTER] Using workflow API for '{chunk_name}' (requires_workflow={requires_workflow}, has_loras={has_loras})")
                    return await self._process_workflow_chunk(chunk_name, text_prompt, parameters, chunk)
                else:
                    logger.info(f"[ROUTER] Using SwarmUI simple API for '{chunk_name}'")
                    return await self._process_image_chunk_simple(chunk_name, text_prompt, parameters, chunk)
            else:
                # For audio/video: use custom workflow submission
                return await self._process_workflow_chunk(chunk_name, text_prompt, parameters, chunk)

        except Exception as e:
            logger.error(f"Error processing Output-Chunk '{chunk_name}': {e}")
            import traceback
            traceback.print_exc()
            return BackendResponse(
                success=False,
                content="",
                error=f"Output-Chunk processing error: {str(e)}"
            )

    async def _process_image_chunk_simple(self, chunk_name: str, prompt: str, parameters: Dict[str, Any], chunk: Dict[str, Any]) -> BackendResponse:
        """Process image chunks — routes to ComfyUI direct (WS) or SwarmUI legacy based on config."""
        try:
            # Extract parameters from input_mappings
            import sys
            from pathlib import Path
            devserver_path = Path(__file__).parent.parent.parent
            if str(devserver_path) not in sys.path:
                sys.path.insert(0, str(devserver_path))

            input_mappings = chunk['input_mappings']
            input_data = {'prompt': prompt, **parameters}

            import random

            # Get model from checkpoint mapping
            model = parameters.get('checkpoint') or input_mappings.get('checkpoint', {}).get('default', 'sd3.5_large')
            if not model.endswith('.safetensors'):
                model = f"{model}.safetensors"

            positive_prompt = input_data.get('prompt', prompt)
            negative_prompt = input_data.get('negative_prompt') or input_mappings.get('negative_prompt', {}).get('default', '')

            media_type = chunk.get('media_type', 'image')
            if media_type == 'image':
                width = int(input_data.get('width') or input_mappings.get('width', {}).get('default', 1024))
                height = int(input_data.get('height') or input_mappings.get('height', {}).get('default', 1024))
            else:
                width = None
                height = None

            steps = int(input_data.get('steps') or input_mappings.get('steps', {}).get('default', 25))
            cfg_scale = float(input_data.get('cfg') or input_mappings.get('cfg', {}).get('default', 7.0))

            seed = input_data.get('seed') or input_mappings.get('seed', {}).get('default', 'random')
            if seed == 'random' or seed == -1:
                seed = random.randint(0, 2**32 - 1)
                logger.info(f"Generated random seed: {seed}")
            else:
                seed = int(seed)

            # ── COMFYUI_DIRECT: If chunk has a workflow, use submit_and_track ──
            if COMFYUI_DIRECT and chunk.get('workflow'):
                return await self._process_workflow_chunk(chunk_name, prompt, parameters, chunk)

            # ── COMFYUI_DIRECT: Simple image (no workflow) ──
            if COMFYUI_DIRECT:
                from my_app.services.comfyui_ws_client import get_comfyui_ws_client

                logger.info("[COMFYUI-DIRECT] Ensuring ComfyUI is available...")
                if not await self.comfyui_manager.ensure_comfyui_available():
                    return BackendResponse(success=False, content="", error="ComfyUI not available")

                client = get_comfyui_ws_client()
                if not await client.health_check():
                    return BackendResponse(success=False, content="", error="ComfyUI not reachable")

                # Build minimal workflow JSON for simple text2image
                workflow = self._build_simple_t2i_workflow(
                    prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    model=model,
                    width=width or 1024,
                    height=height or 1024,
                    steps=steps,
                    cfg_scale=cfg_scale,
                    seed=seed,
                )

                logger.info(f"[COMFYUI-DIRECT] Generating image: model={model}, steps={steps}, size={width}x{height}")

                result = await client.submit_and_track(workflow, timeout=parameters.get('timeout', 300), on_progress=get_progress_callback())

                if not result.media_files:
                    return BackendResponse(success=False, content="", error="ComfyUI generated no output")

                return BackendResponse(
                    success=True,
                    content="comfyui_direct_generated",
                    metadata={
                        'chunk_name': chunk_name,
                        'media_type': media_type,
                        'prompt_id': result.prompt_id,
                        'media_files': [f.data for f in result.media_files],
                        'outputs_metadata': [{'filename': f.filename, 'type': f.media_type, 'node_id': f.node_id} for f in result.media_files],
                        'comfyui_direct': True,
                        'seed': seed,
                        'model': model,
                        'parameters': {
                            'width': width,
                            'height': height,
                            'steps': steps,
                            'cfg_scale': cfg_scale
                        }
                    }
                )

            # ── LEGACY: SwarmUI path ──
            logger.info("[SWARMUI-TEXT2IMAGE] Ensuring SwarmUI is available...")
            if not await self.swarmui_manager.ensure_swarmui_available():
                logger.error("[SWARMUI-TEXT2IMAGE] Failed to start SwarmUI")
                return BackendResponse(
                    success=False,
                    content="",
                    error="SwarmUI server not available (failed to auto-start)"
                )

            from my_app.services.swarmui_client import get_swarmui_client

            client = get_swarmui_client()
            is_healthy = await client.health_check()

            if not is_healthy:
                logger.warning("SwarmUI server not reachable after auto-start")
                return BackendResponse(
                    success=False,
                    content="",
                    error="SwarmUI server not available"
                )

            logger.info(f"[SWARMUI] Generating image with model={model}, steps={steps}, size={width}x{height}")
            image_paths = await client.generate_image(
                prompt=positive_prompt,
                model=model,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed
            )

            if not image_paths:
                return BackendResponse(
                    success=False,
                    content="",
                    error="SwarmUI failed to generate image"
                )

            logger.info(f"[SWARMUI] Generated {len(image_paths)} image(s)")

            return BackendResponse(
                success=True,
                content="swarmui_generated",
                metadata={
                    'chunk_name': chunk_name,
                    'media_type': chunk.get('media_type'),
                    'image_paths': image_paths,
                    'swarmui_available': True,
                    'seed': seed,
                    'model': model,
                    'parameters': {
                        'width': width,
                        'height': height,
                        'steps': steps,
                        'cfg_scale': cfg_scale
                    }
                }
            )

        except Exception as e:
            logger.error(f"Error processing Output-Chunk '{chunk_name}': {e}")
            import traceback
            traceback.print_exc()
            return BackendResponse(
                success=False,
                content="",
                error=f"Output-Chunk processing error: {str(e)}"
            )

    @staticmethod
    def _build_simple_t2i_workflow(
        prompt: str, negative_prompt: str, model: str,
        width: int, height: int, steps: int, cfg_scale: float, seed: int,
    ) -> Dict[str, Any]:
        """Build a minimal ComfyUI workflow JSON for simple text-to-image generation.

        This replaces SwarmUI's /API/GenerateText2Image which internally builds
        the same kind of workflow.
        """
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": model},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 1],
                },
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["1", 1],
                },
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1,
                },
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["1", 2],
                },
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["6", 0],
                    "filename_prefix": "ai4artsed",
                },
            },
        }

    async def _process_workflow_chunk(self, chunk_name: str, prompt: str, parameters: Dict[str, Any], chunk: Dict[str, Any]) -> BackendResponse:
        """Process audio/video/image chunks using custom ComfyUI workflows.

        Routes to ComfyUI direct (WebSocket) or SwarmUI legacy based on COMFYUI_DIRECT config.
        """
        try:
            # 1. Load workflow from chunk
            workflow = chunk.get('workflow')
            if not workflow:
                return BackendResponse(
                    success=False,
                    content="",
                    error=f"No workflow found in chunk '{chunk_name}'"
                )

            media_type = chunk.get('media_type', 'unknown')
            logger.info(f"[WORKFLOW-CHUNK] Processing {media_type} chunk: {chunk_name}")

            # 1.5. Inject LoRA nodes (Session 116: config-specific or global fallback)
            loras = parameters.get('loras', LORA_TRIGGERS)
            if loras:
                logger.info(f"[LORA] Injecting {len(loras)} LoRA(s): {[l['name'] for l in loras]}")
                workflow = self._inject_lora_nodes(workflow, loras)

            # 2. Detect mapping format and apply input mappings
            input_mappings = chunk.get('input_mappings', {})
            input_data = {'prompt': prompt, **parameters}

            first_mapping = next(iter(input_mappings.values()), {})
            if 'node_id' in first_mapping:
                logger.info(f"[WORKFLOW-CHUNK] Using node-based mappings")
                workflow, generated_seed = self._apply_input_mappings(workflow, input_mappings, input_data)
            else:
                logger.info(f"[WORKFLOW-CHUNK] Using template-based mappings")
                workflow_str = json.dumps(workflow)
                generated_seed = None

                for key, mapping in input_mappings.items():
                    value = input_data.get(key)
                    if value is None:
                        value = mapping.get('default', '')

                    if key == "seed":
                        if value == "random":
                            import random
                            value = random.randint(0, 2**32 - 1)
                        generated_seed = value
                        logger.info(f"Generated seed: {generated_seed}")

                    placeholder = mapping.get('template', f'{{{{{key.upper()}}}}}')
                    workflow_str = workflow_str.replace(placeholder, str(value))
                    logger.debug(f"Replaced '{placeholder}' with '{str(value)[:50]}...'")

                workflow = json.loads(workflow_str)

            # ── COMFYUI_DIRECT: WebSocket submit + track ──
            if COMFYUI_DIRECT:
                from my_app.services.comfyui_ws_client import get_comfyui_ws_client

                logger.info("[COMFYUI-DIRECT] Ensuring ComfyUI is available...")
                if not await self.comfyui_manager.ensure_comfyui_available():
                    return BackendResponse(success=False, content="", error="ComfyUI not available")

                client = get_comfyui_ws_client()
                if not await client.health_check():
                    return BackendResponse(success=False, content="", error="ComfyUI not reachable")

                logger.info(f"[COMFYUI-DIRECT] Submitting {media_type} workflow")
                timeout = parameters.get('timeout', 600)

                result = await client.submit_and_track(workflow, timeout=timeout, on_progress=get_progress_callback())

                if not result.media_files:
                    return BackendResponse(
                        success=False, content="",
                        error=f"No {media_type} files in workflow output"
                    )

                logger.info(f"[COMFYUI-DIRECT] Workflow complete: {len(result.media_files)} file(s) in {result.execution_time:.1f}s")

                return BackendResponse(
                    success=True,
                    content="workflow_generated",
                    metadata={
                        'chunk_name': chunk_name,
                        'media_type': media_type,
                        'prompt_id': result.prompt_id,
                        'comfyui_direct': True,
                        'media_files': [f.data for f in result.media_files],
                        'outputs_metadata': [
                            {'filename': f.filename, 'type': f.media_type,
                             'subfolder': f.subfolder, 'node_id': f.node_id}
                            for f in result.media_files
                        ],
                        'seed': generated_seed,
                        'workflow_completed': True,
                    }
                )

            # ── LEGACY: SwarmUI path ──
            import sys
            devserver_path = Path(__file__).parent.parent.parent
            if str(devserver_path) not in sys.path:
                sys.path.insert(0, str(devserver_path))

            logger.info("[SWARMUI-WORKFLOW] Ensuring SwarmUI is available...")
            if not await self.swarmui_manager.ensure_swarmui_available():
                logger.error("[SWARMUI-WORKFLOW] Failed to start SwarmUI")
                return BackendResponse(
                    success=False,
                    content="",
                    error="SwarmUI server not available (failed to auto-start)"
                )

            from my_app.services.swarmui_client import get_swarmui_client

            client = get_swarmui_client()
            is_healthy = await client.health_check()

            if not is_healthy:
                logger.warning("SwarmUI server not reachable after auto-start")
                return BackendResponse(
                    success=False,
                    content="",
                    error="SwarmUI server not available"
                )

            logger.info(f"[WORKFLOW-CHUNK] Submitting {media_type} workflow to SwarmUI")
            prompt_id = await client.submit_workflow(workflow)

            if not prompt_id:
                return BackendResponse(
                    success=False,
                    content="",
                    error="Failed to submit workflow to SwarmUI"
                )

            logger.info(f"[WORKFLOW-CHUNK] Workflow submitted: {prompt_id}")

            timeout = parameters.get('timeout', 600)
            history = await client.wait_for_completion(prompt_id, timeout=timeout)

            if not history:
                return BackendResponse(
                    success=False,
                    content="",
                    error="Timeout or error waiting for workflow completion"
                )

            logger.info(f"[WORKFLOW-CHUNK] Workflow completed: {prompt_id}")

            # Legacy: Extract media files from filesystem (the glob hack)
            import os
            import glob

            if media_type == 'image':
                output_dir = f'{COMFYUI_BASE_PATH}/output'
                file_extension = 'png'
            elif media_type == 'audio':
                output_dir = f'{COMFYUI_BASE_PATH}/output/audio'
                file_extension = 'mp3'
            elif media_type == 'video':
                output_dir = f'{COMFYUI_BASE_PATH}/output/video'
                file_extension = 'mp4'
            else:
                logger.warning(f"Unknown media type '{media_type}', using audio directory")
                output_dir = f'{COMFYUI_BASE_PATH}/output/audio'
                file_extension = 'mp3'

            filesystem_path = None
            if os.path.exists(output_dir):
                files = glob.glob(f"{output_dir}/*.{file_extension}")
                if files:
                    most_recent = max(files, key=os.path.getmtime)
                    filesystem_path = most_recent
                    logger.info(f"[WORKFLOW-CHUNK] Found {media_type} file: {filesystem_path}")

            if not filesystem_path:
                logger.error(f"[WORKFLOW-CHUNK] No {media_type} files found in {output_dir}")
                return BackendResponse(
                    success=False,
                    content="",
                    error=f"No {media_type} files found in workflow output"
                )

            return BackendResponse(
                success=True,
                content="workflow_generated",
                metadata={
                    'chunk_name': chunk_name,
                    'media_type': media_type,
                    'prompt_id': prompt_id,
                    'filesystem_path': filesystem_path,
                    'swarmui_available': True,
                    'seed': generated_seed,
                    'workflow_completed': True
                }
            )

        except Exception as e:
            logger.error(f"Error processing workflow chunk '{chunk_name}': {e}")
            import traceback
            traceback.print_exc()
            return BackendResponse(
                success=False,
                content="",
                error=f"Workflow chunk processing error: {str(e)}"
            )

    async def _process_legacy_workflow(self, chunk: Dict[str, Any], prompt: str, parameters: Dict[str, Any]) -> BackendResponse:
        """Process legacy workflow: Complete workflow passthrough with title-based prompt injection.

        Routes to ComfyUI direct (WebSocket) or SwarmUI legacy based on COMFYUI_DIRECT config.
        """
        try:
            chunk_name = chunk.get('name', 'unknown')
            media_type = chunk.get('media_type', 'image')

            logger.info(f"[LEGACY-WORKFLOW] Processing legacy workflow: {chunk_name}")
            logger.info(f"[DEBUG-PROMPT] Received prompt parameter: '{prompt[:200]}...'" if prompt else f"[DEBUG-PROMPT] Prompt is EMPTY or None: {repr(prompt)}")
            logger.info(f"[DEBUG-PROMPT] Received parameters: {list(parameters.keys())}")

            # Get workflow from chunk
            workflow = chunk.get('workflow')
            if not workflow:
                return BackendResponse(
                    success=False,
                    content="",
                    error="No workflow definition in legacy chunk"
                )

            # Apply ALL input_mappings (element1, element2, combination_type, seed, etc.)
            generated_seed = None
            input_mappings = chunk.get('input_mappings', {})
            if input_mappings:
                input_data = {'prompt': prompt, **parameters}
                logger.info(f"[LEGACY-WORKFLOW] Applying input_mappings for: {list(input_mappings.keys())}")
                workflow, generated_seed = self._apply_input_mappings(workflow, input_mappings, input_data)
                if generated_seed is not None:
                    logger.info(f"[LEGACY-WORKFLOW] Generated seed: {generated_seed}")

            # Handle encoder_type for partial elimination workflow
            encoder_type = parameters.get('encoder_type')
            if encoder_type and encoder_type != 'triple':
                workflow = self._apply_encoder_type(workflow, encoder_type)
                logger.info(f"[LEGACY-WORKFLOW] Applied encoder_type: {encoder_type}")

            # Legacy: Apply seed randomization from input_mappings (DEPRECATED - handled by _apply_input_mappings above)
            if False and input_mappings and 'seed' in input_mappings:
                import random
                seed_mapping = input_mappings['seed']
                seed_value = parameters.get('seed', seed_mapping.get('default', 'random'))
                if seed_value == 'random' or seed_value == -1:
                    seed_value = random.randint(0, 2**32 - 1)
                seed_node_id = seed_mapping.get('node_id')
                seed_field = seed_mapping.get('field', 'inputs.noise_seed')
                if seed_node_id and seed_node_id in workflow:
                    field_parts = seed_field.split('.')
                    target = workflow[seed_node_id]
                    for part in field_parts[:-1]:
                        target = target.setdefault(part, {})
                    target[field_parts[-1]] = seed_value

            # Handle alpha_factor for T5-CLIP fusion workflows
            if input_mappings and 'alpha' in input_mappings and 'alpha_factor' in parameters:
                alpha_mapping = input_mappings['alpha']
                alpha_value = parameters['alpha_factor']

                logger.info(f"[LEGACY-WORKFLOW] Injecting alpha_factor={alpha_value}")

                alpha_node_id = alpha_mapping.get('node_id')
                alpha_field = alpha_mapping.get('field', 'inputs.value')
                if alpha_node_id and alpha_node_id in workflow:
                    field_parts = alpha_field.split('.')
                    target = workflow[alpha_node_id]
                    for part in field_parts[:-1]:
                        target = target.setdefault(part, {})
                    target[field_parts[-1]] = alpha_value
                    logger.info(f"[ALPHA-INJECT] Injected alpha={alpha_value} into node {alpha_node_id}.{alpha_field}")

            # Handle combination_type for split_and_combine workflows (array of mappings)
            if input_mappings and 'combination_type' in input_mappings and 'combination_type' in parameters:
                combination_value = parameters['combination_type']
                combination_mappings = input_mappings['combination_type']

                logger.info(f"[LEGACY-WORKFLOW] Injecting combination_type={combination_value}")

                if isinstance(combination_mappings, dict):
                    combination_mappings = [combination_mappings]

                for mapping in combination_mappings:
                    node_id = mapping.get('node_id')
                    field_path = mapping.get('field', 'inputs.interpolation_method')

                    if node_id and node_id in workflow:
                        field_parts = field_path.split('.')
                        target = workflow[node_id]
                        for part in field_parts[:-1]:
                            target = target.setdefault(part, {})
                        target[field_parts[-1]] = combination_value
                        logger.info(f"[COMBINATION-INJECT] Injected combination_type={combination_value} into node {node_id}.{field_path}")

            # Handle image uploads (single + multi)
            await self._handle_legacy_image_uploads(workflow, input_mappings, parameters)

            # Handle multi-image uploads
            multi_image_keys = ['input_image1', 'input_image2', 'input_image3']
            has_multi_image = any(key in input_mappings for key in multi_image_keys)

            if input_mappings and has_multi_image:
                await self._handle_legacy_multi_image_uploads(
                    workflow, input_mappings, parameters, multi_image_keys
                )

            # Adapt workflow dynamically for multi-image (remove unused nodes)
            if has_multi_image:
                workflow = _adapt_workflow_for_multi_image(workflow, parameters)

            # ── COMFYUI_DIRECT: Use WS client for execution ──
            if COMFYUI_DIRECT:
                from my_app.services.comfyui_ws_client import get_comfyui_ws_client
                from my_app.services.legacy_workflow_service import LegacyWorkflowService

                # Still use LegacyWorkflowService for prompt injection logic
                legacy_svc = LegacyWorkflowService.__new__(LegacyWorkflowService)
                workflow, injection_success = legacy_svc._inject_prompt(workflow, prompt, chunk)
                if not injection_success:
                    logger.warning("[LEGACY-WORKFLOW] Prompt injection failed, continuing anyway")

                # Replace LLM model names
                workflow = legacy_svc._replace_llm_models(workflow)

                logger.info("[COMFYUI-DIRECT] Ensuring ComfyUI is available...")
                if not await self.comfyui_manager.ensure_comfyui_available():
                    return BackendResponse(success=False, content="", error="ComfyUI not available")

                client = get_comfyui_ws_client()
                timeout = parameters.get('timeout', 300)

                result = await client.submit_and_track(workflow, timeout=timeout, on_progress=get_progress_callback())

                logger.info(f"[LEGACY-WORKFLOW] Completed: {len(result.media_files)} file(s)")

                return BackendResponse(
                    success=True,
                    content="workflow_generated",
                    metadata={
                        'chunk_name': chunk_name,
                        'media_type': media_type,
                        'prompt_id': result.prompt_id,
                        'legacy_workflow': True,
                        'comfyui_direct': True,
                        'media_files': [f.data for f in result.media_files],
                        'outputs_metadata': [
                            {'node_id': f.node_id, 'type': f.media_type,
                             'filename': f.filename, 'subfolder': f.subfolder}
                            for f in result.media_files
                        ],
                        'seed': generated_seed,
                    }
                )

            # ── LEGACY: SwarmUI path ──
            from my_app.services.legacy_workflow_service import get_legacy_workflow_service

            service = get_legacy_workflow_service()
            logger.info(f"[LEGACY-WORKFLOW] Using service base URL: {service.base_url}")

            result = await service.execute_workflow(
                workflow=workflow,
                prompt=prompt,
                chunk_config=chunk
            )

            logger.info(f"[LEGACY-WORKFLOW] Completed: {len(result['media_files'])} file(s) downloaded")

            return BackendResponse(
                success=True,
                content="workflow_generated",
                metadata={
                    'chunk_name': chunk_name,
                    'media_type': media_type,
                    'prompt_id': result['prompt_id'],
                    'legacy_workflow': True,
                    'media_files': result['media_files'],
                    'outputs_metadata': result['outputs_metadata'],
                    'workflow_json': result['workflow_json'],
                    'seed': generated_seed,
                }
            )

        except Exception as e:
            logger.error(f"[LEGACY-WORKFLOW] Error: {e}")
            import traceback
            traceback.print_exc()
            return BackendResponse(
                success=False,
                content="",
                error=f"Legacy workflow error: {str(e)}"
            )

    async def _handle_legacy_image_uploads(
        self, workflow: Dict[str, Any], input_mappings: Dict[str, Any], parameters: Dict[str, Any]
    ):
        """Handle single input_image upload for img2img workflows."""
        if not (input_mappings and 'input_image' in input_mappings and 'input_image' in parameters):
            return

        image_mapping = input_mappings['input_image']
        source_path = _resolve_media_url_to_path(parameters['input_image'])
        source_file = Path(source_path)

        if COMFYUI_DIRECT:
            from my_app.services.comfyui_ws_client import get_comfyui_ws_client

            logger.info("[LEGACY-WORKFLOW] Uploading image via ComfyUI WS client...")
            if not await self.comfyui_manager.ensure_comfyui_available():
                logger.error("[LEGACY-WORKFLOW] ComfyUI not available for image upload")
                return

            client = get_comfyui_ws_client()
            with open(source_path, 'rb') as f:
                image_data = f.read()

            uploaded_filename = await client.upload_image(image_data, source_file.name)
        else:
            import aiohttp

            logger.info("[LEGACY-WORKFLOW] Ensuring SwarmUI available for image upload...")
            if not await self.swarmui_manager.ensure_swarmui_available():
                logger.error("[LEGACY-WORKFLOW] SwarmUI not available, image upload will fail")
                return

            comfyui_url = "http://127.0.0.1:7821"
            upload_url = f"{comfyui_url}/upload/image"
            uploaded_filename = None

            try:
                async with aiohttp.ClientSession() as session:
                    with open(source_path, 'rb') as f:
                        form = aiohttp.FormData()
                        form.add_field('image', f, filename=source_file.name, content_type='image/png')
                        form.add_field('overwrite', 'true')

                        async with session.post(upload_url, data=form) as response:
                            if response.status == 200:
                                result = await response.json()
                                uploaded_filename = result.get('name', source_file.name)
                            else:
                                logger.error(f"[LEGACY-WORKFLOW] Failed to upload image: HTTP {response.status}")
            except Exception as e:
                logger.error(f"[LEGACY-WORKFLOW] Error uploading image: {e}")

        if uploaded_filename:
            logger.info(f"[LEGACY-WORKFLOW] Uploaded image: {uploaded_filename}")
            image_node_id = image_mapping.get('node_id')
            image_field = image_mapping.get('field', 'inputs.image')
            if image_node_id and image_node_id in workflow:
                field_parts = image_field.split('.')
                target = workflow[image_node_id]
                for part in field_parts[:-1]:
                    target = target.setdefault(part, {})
                target[field_parts[-1]] = uploaded_filename

    async def _handle_legacy_multi_image_uploads(
        self, workflow: Dict[str, Any], input_mappings: Dict[str, Any],
        parameters: Dict[str, Any], multi_image_keys: List[str]
    ):
        """Handle multi-image uploads (input_image1/2/3)."""
        if COMFYUI_DIRECT:
            from my_app.services.comfyui_ws_client import get_comfyui_ws_client

            logger.info("[LEGACY-WORKFLOW] Multi-image upload via ComfyUI WS client...")
            if not await self.comfyui_manager.ensure_comfyui_available():
                return

            client = get_comfyui_ws_client()

            for image_key in multi_image_keys:
                if image_key not in input_mappings or image_key not in parameters or not parameters[image_key]:
                    continue

                image_mapping = input_mappings[image_key]
                source_path = _resolve_media_url_to_path(parameters[image_key])
                source_file = Path(source_path)

                try:
                    with open(source_path, 'rb') as f:
                        image_data = f.read()
                    uploaded_filename = await client.upload_image(image_data, source_file.name)
                    if uploaded_filename:
                        image_node_id = image_mapping.get('node_id')
                        image_field = image_mapping.get('field', 'inputs.image')
                        if image_node_id and image_node_id in workflow:
                            field_parts = image_field.split('.')
                            target = workflow[image_node_id]
                            for part in field_parts[:-1]:
                                target = target.setdefault(part, {})
                            target[field_parts[-1]] = uploaded_filename
                            logger.info(f"[LEGACY-WORKFLOW] Injected {image_key}: {uploaded_filename}")
                except Exception as e:
                    logger.error(f"[LEGACY-WORKFLOW] Error uploading {image_key}: {e}")
        else:
            import aiohttp

            logger.info("[LEGACY-WORKFLOW] Ensuring SwarmUI available for multi-image upload...")
            await self.swarmui_manager.ensure_swarmui_available()

            comfyui_url = "http://127.0.0.1:7821"
            upload_url = f"{comfyui_url}/upload/image"

            for image_key in multi_image_keys:
                if image_key not in input_mappings or image_key not in parameters or not parameters[image_key]:
                    logger.info(f"[LEGACY-WORKFLOW] {image_key} is empty (optional), skipping")
                    continue

                image_mapping = input_mappings[image_key]
                source_path = _resolve_media_url_to_path(parameters[image_key])
                source_file = Path(source_path)

                try:
                    async with aiohttp.ClientSession() as session:
                        with open(source_path, 'rb') as f:
                            form = aiohttp.FormData()
                            form.add_field('image', f, filename=source_file.name, content_type='image/png')
                            form.add_field('overwrite', 'true')

                            async with session.post(upload_url, data=form) as response:
                                if response.status == 200:
                                    result = await response.json()
                                    uploaded_filename = result.get('name', source_file.name)
                                    logger.info(f"[LEGACY-WORKFLOW] Uploaded {image_key}: {uploaded_filename}")

                                    image_node_id = image_mapping.get('node_id')
                                    image_field = image_mapping.get('field', 'inputs.image')
                                    if image_node_id and image_node_id in workflow:
                                        field_parts = image_field.split('.')
                                        target = workflow[image_node_id]
                                        for part in field_parts[:-1]:
                                            target = target.setdefault(part, {})
                                        target[field_parts[-1]] = uploaded_filename
                                else:
                                    logger.error(f"[LEGACY-WORKFLOW] Failed to upload {image_key}: HTTP {response.status}")
                except Exception as e:
                    logger.error(f"[LEGACY-WORKFLOW] Error uploading {image_key}: {e}")
                    import traceback
                    traceback.print_exc()

    def _inject_legacy_prompt(self, workflow: Dict[str, Any], prompt: str, config: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """Inject prompt into legacy workflow using title-based node search

        This is a direct port of the legacy server's prompt injection logic:
        - Search for node with _meta.title matching target_title
        - Inject into inputs.value or inputs.text field
        - Fallback to node_id if title search fails

        Args:
            workflow: Complete ComfyUI workflow
            prompt: User prompt to inject
            config: Prompt injection configuration from legacy_config

        Returns:
            Tuple[Dict, bool]: (modified_workflow, injection_success)
        """
        target_title = config.get('target_title', 'ai4artsed_text_prompt')
        fallback_node_id = config.get('fallback_node_id')

        logger.info(f"[LEGACY-INJECT] Searching for node with title '{target_title}'")

        # Method 1: Search by _meta.title (preferred)
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict):
                meta_title = node_data.get('_meta', {}).get('title')
                if meta_title == target_title:
                    # Found target node - inject into inputs
                    inputs = node_data.get('inputs', {})

                    # Try 'value' field first, then 'text' field
                    if 'value' in inputs:
                        node_data['inputs']['value'] = prompt
                        logger.info(f"[LEGACY-INJECT] ✓ Injected prompt into node {node_id}.inputs.value (title match)")
                        return workflow, True
                    elif 'text' in inputs:
                        node_data['inputs']['text'] = prompt
                        logger.info(f"[LEGACY-INJECT] ✓ Injected prompt into node {node_id}.inputs.text (title match)")
                        return workflow, True
                    else:
                        logger.warning(f"[LEGACY-INJECT] Found node {node_id} with title '{target_title}' but no 'value' or 'text' field")

        # Method 2: Fallback to node_id (if configured)
        if fallback_node_id and fallback_node_id in workflow:
            node_data = workflow[fallback_node_id]
            inputs = node_data.get('inputs', {})

            if 'value' in inputs:
                node_data['inputs']['value'] = prompt
                logger.warning(f"[LEGACY-INJECT] ⚠ Injected prompt into fallback node {fallback_node_id}.inputs.value")
                return workflow, True
            elif 'text' in inputs:
                node_data['inputs']['text'] = prompt
                logger.warning(f"[LEGACY-INJECT] ⚠ Injected prompt into fallback node {fallback_node_id}.inputs.text")
                return workflow, True

        # Injection failed
        logger.error(f"[LEGACY-INJECT] ✗ Failed to inject prompt - no node with title '{target_title}' found")
        if fallback_node_id:
            logger.error(f"[LEGACY-INJECT] Fallback node_id '{fallback_node_id}' also not found or has no suitable input field")

        return workflow, False

    async def _process_api_output_chunk(self, chunk_name: str, prompt: str, parameters: Dict[str, Any], chunk: Dict[str, Any]) -> BackendResponse:
        """Process API-based Output-Chunk (OpenRouter, Replicate, etc.)"""
        try:
            logger.info(f"Processing API Output-Chunk: {chunk_name} ({chunk.get('media_type', 'unknown')} media)")

            # Build API request with deep copy to avoid mutation
            import copy
            api_config = chunk['api_config']
            request_body = copy.deepcopy(api_config['request_body'])

            # Apply input mappings
            for param_name, mapping in chunk['input_mappings'].items():
                field_path = mapping['field']
                value = parameters.get(param_name, prompt if param_name == 'prompt' else mapping.get('default'))

                # Set nested value (e.g., "request_body.messages[1].content")
                self._set_nested_value(request_body, field_path.replace('request_body.', ''), value)

            # Get API key from .key file based on provider
            provider = api_config.get('provider', 'openrouter')
            if provider == 'openai':
                key_file = 'openai.key'
                key_name = 'OpenAI'
            elif provider == 'anthropic':
                key_file = 'anthropic.key'
                key_name = 'Anthropic'
            else:
                key_file = 'openrouter.key'
                key_name = 'OpenRouter'

            api_key = self._load_api_key(key_file)
            if not api_key:
                error_msg = f"{key_name} API key not found. Create '{key_file}' file in devserver root."
                logger.error(error_msg)
                return BackendResponse(success=False, error=error_msg)

            # Build headers
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ai4artsed.com",
                "X-Title": "AI4ArtsEd DevServer"
            }

            # Make API call
            import aiohttp
            async with aiohttp.ClientSession() as session:
                logger.debug(f"POST {api_config['endpoint']} with model {api_config['model']}")
                async with session.post(
                    api_config['endpoint'],
                    json=request_body,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Debug: Log the response structure
                        logger.debug(f"API Response: {json.dumps(data, indent=2)[:500]}...")

                        # Check if this is an async API (job-based)
                        async_polling_config = api_config.get('async_polling', {})
                        if async_polling_config.get('enabled', False):
                            # Async API: Poll for completion
                            logger.info(f"[ASYNC-API] Job created, starting polling...")
                            output_mapping = chunk.get('output_mapping', {})

                            # Poll until completed
                            final_data = await self._poll_async_job(
                                session=session,
                                initial_response=data,
                                async_config=async_polling_config,
                                headers=headers,
                                api_key=api_key
                            )

                            if not final_data:
                                return BackendResponse(success=False, content="", error="Async job polling failed")

                            # Extract media URL from completed job
                            media_url = await self._extract_media_from_async_response(final_data, output_mapping, chunk['media_type'])
                            if not media_url:
                                return BackendResponse(success=False, content="", error="No media URL in completed job")

                            # Download media from URL
                            logger.info(f"[ASYNC-API] Downloading {chunk['media_type']} from URL...")
                            media_data = await self._download_media_from_url(session, media_url, chunk['media_type'])

                            if not media_data:
                                return BackendResponse(success=False, content="", error="Failed to download media")

                            logger.info(f"[ASYNC-API] Successfully downloaded {chunk['media_type']} ({len(media_data)} bytes)")

                            return BackendResponse(
                                success=True,
                                content=media_data,
                                metadata={
                                    'chunk_name': chunk_name,
                                    'media_type': chunk['media_type'],
                                    'provider': api_config['provider'],
                                    'model': api_config['model'],
                                    'media_url': media_url,
                                    'async_job': True
                                }
                            )
                        else:
                            # Synchronous API: Extract immediately
                            output_mapping = chunk.get('output_mapping', {})
                            mapping_type = output_mapping.get('type', 'chat_completion_with_image')

                            if mapping_type == 'images_api_base64':
                                # OpenAI Images API: extract from data[0].b64_json
                                logger.info(f"[API-OUTPUT] Using Images API extraction")
                                image_data = self._extract_image_from_images_api(data, output_mapping)
                            else:
                                # Chat Completions API: extract from choices[0].message
                                logger.info(f"[API-OUTPUT] Using Chat Completions extraction")
                                image_data = self._extract_image_from_chat_completion(data, output_mapping)

                            if not image_data:
                                logger.error("No image found in API response")
                                return BackendResponse(success=False, content="", error="No image found in response", metadata={})

                            logger.info(f"API generation successful: Generated image data ({len(image_data)} chars)")

                            return BackendResponse(
                                success=True,
                                content=image_data,
                                metadata={
                                    'chunk_name': chunk_name,
                                    'media_type': chunk['media_type'],
                                    'provider': api_config['provider'],
                                    'model': api_config['model'],
                                    'image_data': image_data
                                }
                            )
                    else:
                        error_text = await response.text()
                        logger.error(f"API error {response.status}: {error_text}")
                        return BackendResponse(success=False, content="", error=f"API error: {response.status}")

        except Exception as e:
            logger.error(f"Error processing API Output-Chunk '{chunk_name}': {e}")
            import traceback
            traceback.print_exc()
            return BackendResponse(
                success=False,
                content="",
                error=f"API Output-Chunk processing error: {str(e)}"
            )

    def _extract_image_from_chat_completion(self, data: Dict, output_mapping: Dict) -> Optional[str]:
        """Extract image URL from chat completion response with multimodal content"""
        try:
            message = data['choices'][0]['message']

            # GPT-5 Image: Check message.images array first
            if 'images' in message and isinstance(message['images'], list) and len(message['images']) > 0:
                first_image = message['images'][0]
                if 'image_url' in first_image and 'url' in first_image['image_url']:
                    return first_image['image_url']['url']

            # Fallback: Check message.content for image_url items
            content = message.get('content', '')
            if isinstance(content, list):
                for item in content:
                    if item.get('type') == 'image_url':
                        return item['image_url']['url']

            return None
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Failed to extract image from response: {e}")
            return None

    def _extract_image_from_images_api(self, data: Dict, output_mapping: Dict) -> Optional[str]:
        """Extract base64 image data from OpenAI Images API response

        Expected format:
        {
            "created": 1234567890,
            "data": [
                {"b64_json": "base64_image_data"}
            ]
        }
        """
        try:
            extract_path = output_mapping.get('extract_path', 'data[0].b64_json')
            logger.info(f"[IMAGES-API] Extracting from path: {extract_path}")

            # Images API standard response
            if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                first_image = data['data'][0]
                if 'b64_json' in first_image:
                    b64_data = first_image['b64_json']
                    logger.info(f"[IMAGES-API] Successfully extracted base64 data ({len(b64_data)} chars)")
                    return b64_data

            logger.error(f"[IMAGES-API] No base64 data found in response. Keys: {list(data.keys())}")
            return None
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"[IMAGES-API] Failed to extract image from Images API response: {e}")
            return None

    async def _poll_async_job(self, session, initial_response: Dict, async_config: Dict, headers: Dict, api_key: str) -> Optional[Dict]:
        """Poll async job until completed

        Args:
            session: aiohttp ClientSession
            initial_response: Initial API response containing job_id
            async_config: async_polling configuration from chunk
            headers: HTTP headers for polling requests
            api_key: API key for authentication

        Returns:
            Final completed job response or None if failed/timeout
        """
        import asyncio

        # Extract job_id from initial response
        job_id_path = async_config.get('job_id_path', 'id')
        job_id = initial_response.get(job_id_path)
        if not job_id:
            logger.error(f"[ASYNC-POLL] No job_id found at path '{job_id_path}' in response")
            return None

        logger.info(f"[ASYNC-POLL] Job ID: {job_id}")

        # Get polling configuration
        status_endpoint_template = async_config.get('status_endpoint')
        poll_interval = async_config.get('poll_interval_seconds', 5)
        max_duration = async_config.get('max_poll_duration_seconds', 300)
        status_field = async_config.get('status_field', 'status')
        completed_status = async_config.get('completed_status', 'completed')
        failed_status = async_config.get('failed_status', 'failed')
        in_progress_statuses = async_config.get('in_progress_statuses', ['queued', 'in_progress', 'generating'])

        # Build status endpoint URL
        status_endpoint = status_endpoint_template.replace('{job_id}', job_id)

        start_time = asyncio.get_event_loop().time()
        poll_count = 0

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_duration:
                logger.error(f"[ASYNC-POLL] Timeout after {elapsed:.1f}s (max: {max_duration}s)")
                return None

            poll_count += 1
            logger.info(f"[ASYNC-POLL] Poll #{poll_count} - Checking job status...")

            try:
                async with session.get(status_endpoint, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[ASYNC-POLL] Status check failed: {response.status} - {error_text}")
                        await asyncio.sleep(poll_interval)
                        continue

                    job_data = await response.json()
                    current_status = job_data.get(status_field, 'unknown')
                    logger.info(f"[ASYNC-POLL] Job status: {current_status}")

                    if current_status == completed_status:
                        logger.info(f"[ASYNC-POLL] Job completed after {poll_count} polls ({elapsed:.1f}s)")
                        return job_data
                    elif current_status == failed_status:
                        error = job_data.get('error', 'Unknown error')
                        logger.error(f"[ASYNC-POLL] Job failed: {error}")
                        return None
                    elif current_status in in_progress_statuses:
                        logger.debug(f"[ASYNC-POLL] Job still {current_status}, waiting {poll_interval}s...")
                        await asyncio.sleep(poll_interval)
                    else:
                        logger.warning(f"[ASYNC-POLL] Unknown status '{current_status}', continuing to poll...")
                        await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"[ASYNC-POLL] Polling error: {e}")
                await asyncio.sleep(poll_interval)

    async def _extract_media_from_async_response(self, data: Dict, output_mapping: Dict, media_type: str) -> Optional[str]:
        """Extract media URL from completed async job response

        Args:
            data: Completed job response
            output_mapping: output_mapping configuration from chunk
            media_type: Type of media (video, audio, etc.)

        Returns:
            Media URL or None if not found
        """
        try:
            extract_path = output_mapping.get('extract_path', 'video.url')
            logger.info(f"[ASYNC-EXTRACT] Extracting {media_type} URL from path: {extract_path}")

            # Navigate the path (e.g., "video.url" -> data['video']['url'])
            parts = extract_path.split('.')
            current = data
            for part in parts:
                if part in current:
                    current = current[part]
                else:
                    logger.error(f"[ASYNC-EXTRACT] Path '{extract_path}' not found in response. Available keys: {list(data.keys())}")
                    return None

            if isinstance(current, str):
                logger.info(f"[ASYNC-EXTRACT] Found {media_type} URL: {current[:100]}...")
                return current
            else:
                logger.error(f"[ASYNC-EXTRACT] Expected string URL, got {type(current)}")
                return None

        except Exception as e:
            logger.error(f"[ASYNC-EXTRACT] Failed to extract media URL: {e}")
            return None

    async def _download_media_from_url(self, session, url: str, media_type: str) -> Optional[str]:
        """Download media file from URL and return as base64

        Args:
            session: aiohttp ClientSession
            url: Media file URL
            media_type: Type of media (video, audio, image)

        Returns:
            Base64-encoded media data or None if download failed
        """
        import base64

        try:
            logger.info(f"[MEDIA-DOWNLOAD] Downloading {media_type} from URL...")
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"[MEDIA-DOWNLOAD] Download failed: HTTP {response.status}")
                    return None

                media_bytes = await response.read()
                logger.info(f"[MEDIA-DOWNLOAD] Downloaded {len(media_bytes)} bytes")

                # Encode to base64
                base64_data = base64.b64encode(media_bytes).decode('utf-8')
                logger.info(f"[MEDIA-DOWNLOAD] Encoded to base64 ({len(base64_data)} chars)")
                return base64_data

        except Exception as e:
            logger.error(f"[MEDIA-DOWNLOAD] Download error: {e}")
            return None

    async def _process_triton_chunk(self, chunk_name: str, prompt: str, parameters: Dict[str, Any], chunk: Dict[str, Any]) -> BackendResponse:
        """Process image generation using NVIDIA Triton Inference Server

        Session 149: Alternative backend for workshop scenarios with multiple users.
        Triton provides dynamic batching for efficient multi-user inference.

        Args:
            chunk_name: Name of the output chunk
            prompt: Text prompt for generation
            parameters: Generation parameters (width, height, steps, etc.)
            chunk: Chunk configuration with triton_config

        Returns:
            BackendResponse with generated image
        """
        try:
            from my_app.services.triton_client import get_triton_client
            from config import TRITON_ENABLED
            import random

            # Check if Triton is enabled
            if not TRITON_ENABLED:
                logger.warning(f"[TRITON] Backend disabled in config, falling back to ComfyUI")
                # Fallback to ComfyUI workflow
                return await self._process_workflow_chunk(chunk_name, prompt, parameters, chunk)

            client = get_triton_client()

            # Health check
            if not await client.health_check():
                logger.warning(f"[TRITON] Server not available, falling back to ComfyUI")
                return await self._process_workflow_chunk(chunk_name, prompt, parameters, chunk)

            # Extract parameters from chunk config
            input_mappings = chunk.get('input_mappings', {})
            triton_config = chunk.get('triton_config', {})

            model_name = triton_config.get('model_name', 'stable_diffusion_pipeline')

            # Get generation parameters
            width = int(parameters.get('width') or input_mappings.get('width', {}).get('default', 1024))
            height = int(parameters.get('height') or input_mappings.get('height', {}).get('default', 1024))
            steps = int(parameters.get('steps') or input_mappings.get('steps', {}).get('default', 25))
            cfg_scale = float(parameters.get('cfg') or input_mappings.get('cfg', {}).get('default', 4.5))
            negative_prompt = parameters.get('negative_prompt') or input_mappings.get('negative_prompt', {}).get('default', '')

            # Seed handling
            seed = parameters.get('seed') or input_mappings.get('seed', {}).get('default', 'random')
            if seed == 'random' or seed == -1:
                seed = random.randint(0, 2**32 - 1)
                logger.info(f"[TRITON] Generated random seed: {seed}")
            else:
                seed = int(seed)

            # Generate image via Triton
            logger.info(f"[TRITON] Generating image: model={model_name}, steps={steps}, size={width}x{height}")

            image_bytes = await client.generate_image(
                prompt=prompt,
                model_name=model_name,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed
            )

            if not image_bytes:
                logger.error("[TRITON] Generation failed, falling back to ComfyUI")
                return await self._process_workflow_chunk(chunk_name, prompt, parameters, chunk)

            # Return with binary image data
            import base64
            return BackendResponse(
                success=True,
                content="triton_generated",
                metadata={
                    'chunk_name': chunk_name,
                    'media_type': chunk.get('media_type', 'image'),
                    'backend': 'triton',
                    'model_name': model_name,
                    'seed': seed,
                    'image_data': base64.b64encode(image_bytes).decode('utf-8'),
                    'parameters': {
                        'width': width,
                        'height': height,
                        'steps': steps,
                        'cfg_scale': cfg_scale
                    }
                }
            )

        except Exception as e:
            logger.error(f"[TRITON] Error processing chunk '{chunk_name}': {e}")
            import traceback
            traceback.print_exc()

            # Fallback to ComfyUI on error
            logger.info(f"[TRITON] Falling back to ComfyUI due to error")
            return await self._process_workflow_chunk(chunk_name, prompt, parameters, chunk)

    async def _process_heartmula_chunk(self, chunk_name: str, prompt: str, parameters: Dict[str, Any], chunk: Dict[str, Any]) -> BackendResponse:
        """Process music generation using HeartMuLa (heartlib)

        Session XXX: Music generation backend using HeartMuLa library.
        Generates music from lyrics and style tags using LLM + Audio Codec.

        Args:
            chunk_name: Name of the output chunk
            prompt: Text prompt (used as fallback for lyrics)
            parameters: Generation parameters including lyrics, tags, etc.
            chunk: Chunk configuration

        Returns:
            BackendResponse with generated audio
        """
        try:
            from my_app.services.heartmula_backend import get_heartmula_backend
            from config import HEARTMULA_ENABLED
            import random
            import base64

            # Check if HeartMuLa backend is enabled
            if not HEARTMULA_ENABLED:
                logger.warning(f"[HEARTMULA] Backend disabled in config")
                return BackendResponse(
                    success=False,
                    content="",
                    error="HeartMuLa backend is disabled in config (HEARTMULA_ENABLED=false)"
                )

            backend = get_heartmula_backend()

            # Check availability (heartlib, models, GPU)
            if not await backend.is_available():
                logger.error(f"[HEARTMULA] Backend not available")
                return BackendResponse(
                    success=False,
                    content="",
                    error="HeartMuLa backend not available. Check if heartlib is installed and models are downloaded."
                )

            # Extract parameters from chunk config
            input_mappings = chunk.get('input_mappings', {})

            # Get lyrics and tags from parameters
            # music_generation pipeline provides TEXT_1 (lyrics) and TEXT_2 (tags)
            lyrics = parameters.get('lyrics') or parameters.get('TEXT_1', '')
            tags = parameters.get('tags') or parameters.get('TEXT_2', '')

            # Fallback: use prompt as lyrics if not provided
            if not lyrics and prompt:
                lyrics = prompt

            if not lyrics:
                logger.error("[HEARTMULA] No lyrics provided")
                return BackendResponse(
                    success=False,
                    content="",
                    error="No lyrics provided for music generation"
                )

            # Get generation parameters
            temperature = float(parameters.get('temperature') or input_mappings.get('temperature', {}).get('default', 1.0))
            topk = int(parameters.get('topk') or input_mappings.get('topk', {}).get('default', 70))
            cfg_scale = float(parameters.get('cfg_scale') or input_mappings.get('cfg_scale', {}).get('default', 3.0))
            max_audio_length_ms = int(parameters.get('max_audio_length_ms') or input_mappings.get('max_audio_length_ms', {}).get('default', 240000))

            # Seed handling
            seed = parameters.get('seed') or input_mappings.get('seed', {}).get('default', 'random')
            if seed == 'random' or seed == -1:
                seed = random.randint(0, 2**32 - 1)
                logger.info(f"[HEARTMULA] Generated random seed: {seed}")
            else:
                seed = int(seed)

            # Generate music via HeartMuLa
            logger.info(f"[HEARTMULA] Generating music: lyrics={len(lyrics)} chars, tags={tags[:100] if tags else 'none'}...")

            audio_bytes = await backend.generate_music(
                lyrics=lyrics,
                tags=tags,
                temperature=temperature,
                topk=topk,
                cfg_scale=cfg_scale,
                max_audio_length_ms=max_audio_length_ms,
                seed=seed,
                output_format="mp3"
            )

            if not audio_bytes:
                logger.error("[HEARTMULA] Generation failed")
                return BackendResponse(
                    success=False,
                    content="",
                    error="HeartMuLa music generation failed"
                )

            # Return with binary audio data (base64 encoded)
            return BackendResponse(
                success=True,
                content="heartmula_generated",
                metadata={
                    'chunk_name': chunk_name,
                    'media_type': 'music',
                    'backend': 'heartmula',
                    'seed': seed,
                    'audio_data': base64.b64encode(audio_bytes).decode('utf-8'),
                    'audio_format': 'mp3',
                    'parameters': {
                        'lyrics_length': len(lyrics),
                        'tags': tags,
                        'temperature': temperature,
                        'topk': topk,
                        'cfg_scale': cfg_scale,
                        'max_audio_length_ms': max_audio_length_ms
                    }
                }
            )

        except Exception as e:
            logger.error(f"[HEARTMULA] Error processing chunk '{chunk_name}': {e}")
            import traceback
            traceback.print_exc()

            return BackendResponse(
                success=False,
                content="",
                error=f"HeartMuLa error: {str(e)}"
            )

    async def _process_stable_audio_chunk(self, chunk_name: str, prompt: str, parameters: Dict[str, Any], chunk: Dict[str, Any]) -> BackendResponse:
        """Process audio generation using Stable Audio Open (Diffusers)

        Session 163: Audio generation backend using HuggingFace Diffusers StableAudioPipeline.
        Generates sound effects and ambient audio from text prompts.
        Falls back to ComfyUI via meta.fallback_chunk if unavailable.

        Args:
            chunk_name: Name of the output chunk
            prompt: Text prompt describing desired audio
            parameters: Generation parameters including duration, steps, etc.
            chunk: Chunk configuration (must have meta.fallback_chunk for ComfyUI fallback)

        Returns:
            BackendResponse with generated audio
        """
        try:
            from my_app.services.stable_audio_backend import get_stable_audio_backend
            from my_app.services.backend_registry import get_backend_registry
            import random
            import base64

            # Check if Stable Audio backend is enabled via registry
            registry = get_backend_registry()
            if not registry.is_enabled("stable_audio"):
                return await self._fallback_to_comfyui(chunk, chunk_name, prompt, parameters, "Backend disabled in config")

            backend = get_stable_audio_backend()

            # Check availability (diffusers, GPU)
            if not await backend.is_available():
                return await self._fallback_to_comfyui(chunk, chunk_name, prompt, parameters, "Backend not available (missing packages or GPU)")

            # Extract parameters from chunk config
            input_mappings = chunk.get('input_mappings', {})

            # Get prompt from parameters
            audio_prompt = parameters.get('prompt') or parameters.get('PREVIOUS_OUTPUT', '') or prompt

            if not audio_prompt:
                logger.error("[STABLE_AUDIO] No prompt provided")
                return BackendResponse(
                    success=False,
                    content="",
                    error="No prompt provided for audio generation"
                )

            # Get generation parameters
            duration_seconds = float(parameters.get('duration_seconds') or input_mappings.get('duration_seconds', {}).get('default', 30.0))
            negative_prompt = parameters.get('negative_prompt') or input_mappings.get('negative_prompt', {}).get('default', '')
            steps = int(parameters.get('steps') or input_mappings.get('steps', {}).get('default', 100))
            cfg_scale = float(parameters.get('cfg_scale') or input_mappings.get('cfg_scale', {}).get('default', 7.0))

            # Seed handling
            seed = parameters.get('seed') or input_mappings.get('seed', {}).get('default', 'random')
            if seed == 'random' or seed == -1:
                seed = random.randint(0, 2**32 - 1)
                logger.info(f"[STABLE_AUDIO] Generated random seed: {seed}")
            else:
                seed = int(seed)

            # Output format
            output_format = parameters.get('output_format') or input_mappings.get('output_format', {}).get('default', 'mp3')

            # Generate audio via Stable Audio
            logger.info(f"[STABLE_AUDIO] Generating audio: prompt='{audio_prompt[:100]}...', duration={duration_seconds}s")

            audio_bytes = await backend.generate_audio(
                prompt=audio_prompt,
                negative_prompt=negative_prompt,
                duration_seconds=duration_seconds,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed,
                output_format=output_format
            )

            if not audio_bytes:
                return await self._fallback_to_comfyui(chunk, chunk_name, prompt, parameters, "Generation returned empty result")

            # Return with binary audio data (base64 encoded)
            return BackendResponse(
                success=True,
                content="stable_audio_generated",
                metadata={
                    'chunk_name': chunk_name,
                    'media_type': 'audio',
                    'backend': 'stable_audio',
                    'seed': seed,
                    'audio_data': base64.b64encode(audio_bytes).decode('utf-8'),
                    'audio_format': output_format,
                    'parameters': {
                        'prompt': audio_prompt[:200],
                        'duration_seconds': duration_seconds,
                        'steps': steps,
                        'cfg_scale': cfg_scale
                    }
                }
            )

        except Exception as e:
            logger.error(f"[STABLE_AUDIO] Error processing chunk '{chunk_name}': {e}")
            import traceback
            traceback.print_exc()

            # Fallback to ComfyUI on error
            try:
                from my_app.services.backend_registry import get_backend_registry
                registry = get_backend_registry()
                if registry.should_fallback_to_comfyui():
                    return await self._fallback_to_comfyui(chunk, chunk_name, prompt, parameters, f"Exception: {str(e)}")
            except Exception:
                pass

            return BackendResponse(
                success=False,
                content="",
                error=f"Stable Audio error: {str(e)}"
            )

    def _set_nested_value(self, obj: Any, path: str, value: Any):
        """Set nested value in dict or list using path notation (e.g., 'messages[1].content')"""
        import re
        parts = re.split(r'\.|\[|\]', path)
        parts = [p for p in parts if p]  # Remove empty strings

        current = obj
        for i, part in enumerate(parts[:-1]):
            if part.isdigit():
                current = current[int(part)]
            else:
                current = current[part]

        final_key = parts[-1]
        if final_key.isdigit():
            current[int(final_key)] = value
        else:
            current[final_key] = value

    def _load_api_key(self, key_filename: str) -> Optional[str]:
        """Load API key from .key file in devserver root directory"""
        try:
            # Path to devserver root (3 levels up from this file)
            devserver_root = Path(__file__).parent.parent.parent
            key_path = devserver_root / key_filename

            if not key_path.exists():
                logger.warning(f"API key file not found: {key_path}")
                return None

            with open(key_path, 'r', encoding='utf-8') as f:
                api_key = f.read().strip()

            if not api_key:
                logger.warning(f"API key file is empty: {key_path}")
                return None

            logger.info(f"Loaded API key from {key_filename}")
            return api_key

        except Exception as e:
            logger.error(f"Error reading API key file '{key_filename}': {e}")
            return None

    def _load_output_chunk(self, chunk_name: str) -> Optional[Dict[str, Any]]:
        """Load Output-Chunk from schemas/chunks/ directory"""
        try:
            chunk_path = Path(__file__).parent.parent / "chunks" / f"{chunk_name}.json"

            if not chunk_path.exists():
                logger.error(f"Output-Chunk file not found: {chunk_path}")
                return None

            with open(chunk_path, 'r', encoding='utf-8') as f:
                chunk = json.load(f)

            # Validate it's an Output-Chunk (output_chunk, api_output_chunk, or text_passthrough)
            chunk_type = chunk.get('type')
            if chunk_type not in ['output_chunk', 'api_output_chunk', 'text_passthrough']:
                logger.error(f"Chunk '{chunk_name}' is not an Output-Chunk (type: {chunk_type})")
                return None

            # Validate required fields based on type, execution_mode, and backend_type
            execution_mode = chunk.get('execution_mode', 'standard')
            backend_type = chunk.get('backend_type', 'comfyui')

            # Direct backends (no ComfyUI workflow needed)
            DIRECT_BACKENDS = ['stable_audio', 'diffusers', 'heartmula', 'triton']

            if chunk_type == 'output_chunk':
                if execution_mode == 'legacy_workflow':
                    # Legacy workflows have different requirements
                    required_fields = ['workflow', 'backend_type']
                    # Optional but recommended: legacy_config
                elif backend_type in DIRECT_BACKENDS:
                    # Direct backends: no workflow required (they call Python backends directly)
                    required_fields = ['input_mappings', 'output_mapping', 'backend_type']
                else:
                    # Standard ComfyUI output chunks
                    required_fields = ['workflow', 'input_mappings', 'output_mapping', 'backend_type']
            elif chunk_type == 'api_output_chunk':
                required_fields = ['api_config', 'input_mappings', 'output_mapping', 'backend_type']
            elif chunk_type == 'text_passthrough':
                # Text passthrough: no backend execution, returns input unchanged
                # Used for code output where generation happens in Stage 2 optimization
                required_fields = ['backend_type', 'media_type']

            missing = [f for f in required_fields if f not in chunk]
            if missing:
                logger.error(f"Output-Chunk '{chunk_name}' missing fields: {missing}")
                return None

            return chunk

        except Exception as e:
            logger.error(f"Error loading Output-Chunk '{chunk_name}': {e}")
            return None

    async def _execute_python_chunk(self, chunk_path: Path, parameters: Dict[str, Any]) -> BackendResponse:
        """
        Execute Python-based Output-Chunk.

        Python chunks are the new standard (JSON chunks are deprecated).
        The chunk must have an async execute() function that takes parameters and returns bytes.

        Args:
            chunk_path: Path to the .py chunk file
            parameters: Dict with chunk parameters (TEXT_1, TEXT_2, etc.)

        Returns:
            BackendResponse with generated media bytes
        """
        try:
            import importlib.util
            import sys

            chunk_name = chunk_path.stem
            logger.info(f"[PYTHON-CHUNK] Loading chunk: {chunk_name}")

            # Load module dynamically
            spec = importlib.util.spec_from_file_location(f"chunk_{chunk_name}", chunk_path)
            if not spec or not spec.loader:
                return BackendResponse(
                    success=False,
                    content="",
                    error=f"Failed to load Python chunk: {chunk_path}"
                )

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Verify execute() function exists
            if not hasattr(module, 'execute'):
                return BackendResponse(
                    success=False,
                    content="",
                    error=f"Python chunk '{chunk_name}' missing execute() function"
                )

            logger.info(f"[PYTHON-CHUNK] Executing {chunk_name}.execute() with {len(parameters)} parameters")

            # Call execute() with parameters
            result = await module.execute(**parameters)

            # Python chunks can return structured dicts (not just bytes)
            if isinstance(result, dict):
                content_marker = result.pop('content_marker', f"{chunk_name}_generated")
                logger.info(f"[PYTHON-CHUNK] Dict return with marker: {content_marker}")
                return BackendResponse(
                    success=True,
                    content=content_marker,
                    metadata={
                        "chunk_type": "python",
                        "chunk_name": chunk_name,
                        **result
                    }
                )

            # Result should be bytes (audio/image/video data)
            if not isinstance(result, bytes):
                logger.warning(f"[PYTHON-CHUNK] execute() returned {type(result)}, expected bytes")
                # Try to convert if it's a string path
                if isinstance(result, str) and Path(result).exists():
                    with open(result, 'rb') as f:
                        result = f.read()
                    logger.info(f"[PYTHON-CHUNK] Converted file path to bytes ({len(result)} bytes)")

            logger.info(f"[PYTHON-CHUNK] Success - generated {len(result)} bytes")

            # For audio/music chunks, return in format expected by routes
            # (content=marker_string, audio_data in metadata as base64)
            if chunk_name.startswith('output_music_') or chunk_name.startswith('output_audio_'):
                import base64
                # Extract backend name (e.g., "output_music_heartmula" -> "heartmula")
                backend_name = chunk_name.replace('output_music_', '').replace('output_audio_', '')
                return BackendResponse(
                    success=True,
                    content=f"{backend_name}_generated",  # e.g. "heartmula_generated"
                    metadata={
                        "chunk_type": "python",
                        "chunk_name": chunk_name,
                        "media_type": "music" if "music" in chunk_name else "audio",
                        "backend": backend_name,
                        "audio_data": base64.b64encode(result).decode('utf-8'),
                        "audio_format": "mp3",
                        "size_bytes": len(result)
                    }
                )

            # For video chunks, return video data as base64 in metadata
            if chunk_name.startswith('output_video_'):
                import base64
                backend_name = chunk_name.replace('output_video_', '')
                return BackendResponse(
                    success=True,
                    content=f"{backend_name}_generated",
                    metadata={
                        "chunk_type": "python",
                        "chunk_name": chunk_name,
                        "media_type": "video",
                        "backend": backend_name,
                        "video_data": base64.b64encode(result).decode('utf-8'),
                        "video_format": "mp4",
                        "size_bytes": len(result)
                    }
                )

            # For other chunks, return bytes as-is (images, etc.)
            return BackendResponse(
                success=True,
                content=result,
                metadata={
                    "chunk_type": "python",
                    "chunk_name": chunk_name,
                    "size_bytes": len(result)
                }
            )

        except TypeError as e:
            # Parameter mismatch
            logger.error(f"[PYTHON-CHUNK] Parameter mismatch: {e}")
            return BackendResponse(
                success=False,
                content="",
                error=f"Parameter error in {chunk_path.name}: {str(e)}"
            )
        except Exception as e:
            logger.error(f"[PYTHON-CHUNK] Execution failed: {e}")
            import traceback
            traceback.print_exc()
            return BackendResponse(
                success=False,
                content="",
                error=f"Python chunk execution failed: {str(e)}"
            )

    def _inject_lora_nodes(self, workflow: Dict, loras: list) -> Dict:
        """
        Inject LoraLoader nodes into workflow.
        Chains: Checkpoint -> LoRA1 -> LoRA2 -> ... -> KSampler

        Args:
            workflow: ComfyUI workflow dict
            loras: List of dicts with 'name' and 'strength' keys

        Returns:
            Modified workflow with LoRA nodes injected
        """
        import copy
        workflow = copy.deepcopy(workflow)

        # 1. Find CheckpointLoader node (source of model)
        checkpoint_node_id = None
        for node_id, node in workflow.items():
            if isinstance(node, dict) and node.get('class_type') == 'CheckpointLoaderSimple':
                checkpoint_node_id = node_id
                break

        if not checkpoint_node_id:
            logger.warning("[LORA] No CheckpointLoaderSimple found, skipping injection")
            return workflow

        # 2. Find nodes that consume model from checkpoint
        # and find CLIP source (for SD3.5: DualCLIPLoader)
        clip_source = None
        model_consumers = []
        for node_id, node in workflow.items():
            if isinstance(node, dict) and 'inputs' in node:
                inputs = node['inputs']
                # Check if this node takes model from checkpoint
                if inputs.get('model') == [checkpoint_node_id, 0]:
                    model_consumers.append(node_id)
                # Find CLIP source (DualCLIPLoader for SD3.5)
                if node.get('class_type') == 'DualCLIPLoader':
                    clip_source = [node_id, 0]

        if not model_consumers:
            logger.warning("[LORA] No model consumers found, skipping injection")
            return workflow

        # 3. Insert LoraLoader nodes (chained)
        # Find next available node ID
        existing_ids = [int(k) for k in workflow.keys() if k.isdigit()]
        next_id = max(existing_ids) + 1 if existing_ids else 100

        prev_model_source = [checkpoint_node_id, 0]
        prev_clip_source = clip_source or [checkpoint_node_id, 1]

        for i, lora in enumerate(loras):
            lora_node_id = str(next_id + i)
            workflow[lora_node_id] = {
                "inputs": {
                    "lora_name": lora["name"],
                    "strength_model": lora.get("strength", 1.0),
                    "strength_clip": lora.get("strength", 1.0),
                    "model": prev_model_source,
                    "clip": prev_clip_source
                },
                "class_type": "LoraLoader",
                "_meta": {"title": f"LoRA: {lora['name']}"}
            }
            prev_model_source = [lora_node_id, 0]
            prev_clip_source = [lora_node_id, 1]
            logger.info(f"[LORA] Injected LoraLoader node {lora_node_id}: {lora['name']}")

        # 4. Update model consumers to use last LoRA output
        for consumer_id in model_consumers:
            workflow[consumer_id]['inputs']['model'] = prev_model_source
            logger.info(f"[LORA] Updated node {consumer_id} to receive model from LoRA chain")

        return workflow

    def _apply_encoder_type(self, workflow: Dict, encoder_type: str) -> Dict:
        """Apply encoder_type to workflow - swap CLIPLoader configuration

        Args:
            workflow: The ComfyUI workflow dict
            encoder_type: One of 'triple', 'clip_g', 't5xxl'

        Returns:
            Modified workflow dict
        """
        # Find the CLIPLoader node (typically node 39 in partial_elimination)
        clip_loader_node_id = None
        for node_id, node in workflow.items():
            class_type = node.get('class_type', '')
            if class_type in ['TripleCLIPLoader', 'DualCLIPLoader', 'CLIPLoader']:
                clip_loader_node_id = node_id
                break

        if not clip_loader_node_id:
            logger.warning(f"[ENCODER-TYPE] No CLIPLoader found in workflow, skipping encoder_type application")
            return workflow

        logger.info(f"[ENCODER-TYPE] Found CLIPLoader at node {clip_loader_node_id}, applying encoder_type={encoder_type}")

        if encoder_type == 'clip_g':
            # Single CLIP-G encoder (1280 dimensions)
            workflow[clip_loader_node_id] = {
                "inputs": {
                    "clip_name": "clip_g.safetensors",
                    "type": "sd3",
                    "device": "default"
                },
                "class_type": "CLIPLoader",
                "_meta": {"title": "CLIPLoader (CLIP-G only)"}
            }
        elif encoder_type == 't5xxl':
            # Single T5-XXL encoder (4096 dimensions)
            workflow[clip_loader_node_id] = {
                "inputs": {
                    "clip_name": "t5xxl_enconly.safetensors",
                    "type": "sd3",
                    "device": "default"
                },
                "class_type": "CLIPLoader",
                "_meta": {"title": "CLIPLoader (T5-XXL only)"}
            }
        # 'triple' case is handled by the default workflow (no modification needed)

        return workflow

    def _apply_input_mappings(self, workflow: Dict, mappings: Dict[str, Any], input_data: Dict[str, Any]) -> Tuple[Dict, Optional[int]]:
        """Apply input_mappings to workflow - inject prompts and parameters

        Supports two formats:
        1. Single mapping: "key": {"node_id": "X", "field": "Y"}
        2. Multi-node mapping: "key": [{"node_id": "X", "field": "Y"}, {...}]

        Returns:
            Tuple[Dict, Optional[int]]: (modified_workflow, generated_seed)
        """
        import random

        generated_seed = None

        for key, mapping_or_list in mappings.items():
            # Get value from input_data
            value = input_data.get(key)
            logger.info(f"[INPUT-MAPPING-DEBUG] Key='{key}', Value='{str(value)[:100] if value else repr(value)}'")

            # Convert single mapping to list for uniform processing
            mapping_list = mapping_or_list if isinstance(mapping_or_list, list) else [mapping_or_list]

            # Get default value from first mapping if value is None
            if value is None and len(mapping_list) > 0:
                first_mapping = mapping_list[0]
                if isinstance(first_mapping, dict):
                    value = first_mapping.get('default')

            # Try source placeholder if still None
            if value is None and len(mapping_list) > 0:
                first_mapping = mapping_list[0]
                if isinstance(first_mapping, dict):
                    source = first_mapping.get('source', '')
                    if source == '{{PREVIOUS_OUTPUT}}':
                        value = input_data.get('prompt', '')

            # Special handling for seed
            if key == "seed":
                if value == "random":
                    value = random.randint(0, 2**32 - 1)
                generated_seed = value
                logger.info(f"Generated seed: {generated_seed}")

            # Apply value to ALL nodes in the mapping list
            if value is not None:
                for mapping in mapping_list:
                    if not isinstance(mapping, dict):
                        logger.warning(f"Skipping invalid mapping for '{key}': {mapping}")
                        continue

                    node_id = mapping.get('node_id')
                    field = mapping.get('field')

                    if not node_id or not field:
                        logger.warning(f"Skipping incomplete mapping for '{key}': missing node_id or field")
                        continue

                    field_path = field.split('.')

                    # Navigate to the nested field (e.g., "inputs.value" -> workflow[node_id]['inputs']['value'])
                    target = workflow.setdefault(node_id, {})
                    for part in field_path[:-1]:
                        target = target.setdefault(part, {})

                    # Set the final value
                    target[field_path[-1]] = value

                    logger.info(f"✓ Injected '{key}' = '{str(value)[:50]}' to node {node_id}.{mapping['field']}")

        return workflow, generated_seed

    async def _extract_output_media(self, client, history: Dict, output_mapping: Dict) -> List[Dict[str, Any]]:
        """Extract generated media based on output_mapping"""
        try:
            node_id = output_mapping['node_id']
            media_type = output_mapping['output_type']  # 'image', 'audio', 'video'

            # Use appropriate extraction method based on media_type
            if media_type == 'image':
                return await client.get_generated_images(history)
            elif media_type == 'audio':
                return await client.get_generated_audio(history)
            elif media_type == 'video':
                return await client.get_generated_video(history)
            else:
                logger.warning(f"Unknown media type: {media_type}, using generic extraction")
                return await client.get_generated_images(history)

        except Exception as e:
            logger.error(f"Error extracting output media: {e}")
            return []

    async def _process_comfyui_legacy(self, schema_output: str, parameters: Dict[str, Any]) -> BackendResponse:
        """LEGACY: ComfyUI-Request mit deprecated comfyui_workflow_generator

        NOW USES: SwarmUI client's /ComfyBackendDirect passthrough instead of direct port 7821
        """
        try:
            # Workflow-Template aus Parameters extrahieren
            workflow_template = parameters.get('workflow_template', 'sd35_standard')

            # ComfyUI-Workflow-Generator verwenden (DEPRECATED)
            try:
                from .comfyui_workflow_generator import get_workflow_generator
                # Import relativ zum devserver root
                import sys
                from pathlib import Path
                devserver_path = Path(__file__).parent.parent.parent
                if str(devserver_path) not in sys.path:
                    sys.path.insert(0, str(devserver_path))
                from my_app.services.swarmui_client import get_swarmui_client

                # 1. Workflow generieren
                generator = get_workflow_generator(Path(__file__).parent.parent)
                workflow = generator.generate_workflow(
                    template_name=workflow_template,
                    schema_output=schema_output,
                    parameters=parameters
                )

                if not workflow:
                    return BackendResponse(
                        success=False,
                        content="",
                        error=f"Workflow-Template '{workflow_template}' nicht verfügbar"
                    )

                logger.info(f"ComfyUI-Workflow generiert: {len(workflow)} Nodes für Template '{workflow_template}' (DEPRECATED)")

                # 2. SwarmUI Client holen (now handles ComfyUI via /ComfyBackendDirect)
                client = get_swarmui_client()
                is_healthy = await client.health_check()

                if not is_healthy:
                    logger.warning("SwarmUI/ComfyUI server not reachable, returning workflow only")
                    return BackendResponse(
                        success=True,
                        content="workflow_generated_only",
                        metadata={
                            'workflow_generated': True,
                            'template': workflow_template,
                            'workflow': workflow,
                            'comfyui_available': False,
                            'message': 'Workflow generated but ComfyUI server not available'
                        }
                    )

                # 3. Workflow an ComfyUI senden
                prompt_id = await client.submit_workflow(workflow)

                if not prompt_id:
                    return BackendResponse(
                        success=False,
                        content="",
                        error="Failed to submit workflow to ComfyUI"
                    )

                logger.info(f"Workflow submitted to ComfyUI: {prompt_id}")

                # 4. Optional: Auf Fertigstellung warten (wenn wait_for_completion Parameter gesetzt)
                if parameters.get('wait_for_completion', False):
                    timeout = parameters.get('timeout', 300)
                    history = await client.wait_for_completion(prompt_id, timeout=timeout)

                    if history:
                        # Generierte Bilder extrahieren
                        images = await client.get_generated_images(history)
                        return BackendResponse(
                            success=True,
                            content=prompt_id,
                            metadata={
                                'workflow_generated': True,
                                'template': workflow_template,
                                'prompt_id': prompt_id,
                                'completed': True,
                                'images': images,
                                'comfyui_available': True
                            }
                        )
                    else:
                        return BackendResponse(
                            success=False,
                            content=prompt_id,
                            error="Timeout or error waiting for completion",
                            metadata={
                                'workflow_generated': True,
                                'template': workflow_template,
                                'prompt_id': prompt_id,
                                'completed': False,
                                'comfyui_available': True
                            }
                        )
                else:
                    # Sofort zurückkehren mit prompt_id
                    return BackendResponse(
                        success=True,
                        content=prompt_id,
                        metadata={
                            'workflow_generated': True,
                            'template': workflow_template,
                            'prompt_id': prompt_id,
                            'submitted': True,
                            'comfyui_available': True,
                            'message': 'Workflow submitted to ComfyUI queue'
                        }
                    )

            except ImportError as e:
                logger.error(f"ComfyUI modules nicht verfügbar: {e}")
                return BackendResponse(
                    success=False,
                    content="",
                    error="ComfyUI integration not available"
                )

        except Exception as e:
            logger.error(f"ComfyUI-Legacy-Backend-Fehler: {e}")
            import traceback
            traceback.print_exc()
            return BackendResponse(
                success=False,
                content="",
                error=f"ComfyUI-Legacy-Service-Fehler: {str(e)}"
            )
    
    def is_backend_available(self, backend_type: BackendType) -> bool:
        """Prüfen ob Backend verfügbar ist"""
        return backend_type in self.backends
    
    def get_available_backends(self) -> list[BackendType]:
        """Liste aller verfügbaren Backends"""
        return list(self.backends.keys())

# Singleton-Instanz
router = BackendRouter()
