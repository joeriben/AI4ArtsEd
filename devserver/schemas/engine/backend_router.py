"""
Backend-Router: Multi-Backend-Support für Schema-Pipelines
"""
import base64
import logging
from typing import Dict, Any, Optional, AsyncGenerator, Tuple, Union, List
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json

from my_app.services.pipeline_recorder import load_recorder
from my_app.services.llm_providers import (
    credentials as provider_credentials, names as provider_names,
    provider as provider_entry, provider_of,
)
from config import JSON_STORAGE_DIR, LORA_TRIGGERS, COMFYUI_MAX_QUEUE_DEPTH, COMFYUI_TIMEOUT
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
        from my_app.services.pipeline_recorder import SafetyRefusal
        try:
            recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
            if recorder:
                image_entity = _find_entity_by_type(recorder.metadata.get('entities', []), 'image')
                if image_entity:
                    # Files are in final/ subfolder
                    # A picture the content check withheld may not come back in
                    # as the SOURCE of the next generation either — what is made
                    # from it carries it forward, and the new run's own record
                    # says nothing about where its input came from.
                    resolved_path = str(recorder.checked_entity_path(image_entity))
                    logger.info(f"[URL-RESOLVE] {url_or_path} → {resolved_path}")
                    return resolved_path
        except SafetyRefusal:
            raise
        except Exception as e:
            logger.error(f"[URL-RESOLVE] Failed to resolve {url_or_path}: {e}")

    return url_or_path


def _adapt_workflow_for_multi_image(workflow: Dict[str, Any], parameters: Dict[str, Any],
                                    adaptation: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Drop what the chunk declares unused when an optional image is absent.

    `adaptation` is the chunk's own `multi_image_adaptation`: per optional
    image parameter, the nodes to remove and the encoder inputs to drop when
    that image was not provided. Until 2026-10-10 the node ids of the one
    chunk that takes three images (output_image_qwen_2511_multi) stood here in
    the router, which broke in silence as soon as the chunk renumbered them
    (finding S-031 of the code review of 2026-10-10). A chunk that declares nothing is left as it is.
    """
    removed_nodes = []
    dropped_inputs = []
    for image_key, rule in (adaptation or {}).items():
        if parameters.get(image_key):
            continue
        for node_id in rule.get('remove_nodes') or []:
            if node_id in workflow:
                del workflow[node_id]
                removed_nodes.append(node_id)
        for node_id, names in (rule.get('drop_inputs') or {}).items():
            inputs = (workflow.get(node_id) or {}).get('inputs', {})
            for name in names:
                if name in inputs:
                    del inputs[name]
                    dropped_inputs.append(f"{node_id}.{name}")
    if removed_nodes:
        logger.info(f"[MULTI-IMAGE-ADAPT] Removed unused nodes: {', '.join(removed_nodes)}")
    if dropped_inputs:
        logger.info(f"[MULTI-IMAGE-ADAPT] Dropped unused inputs: {', '.join(dropped_inputs)}")
    return workflow


class BackendType(Enum):
    """Backend-Typen"""
    LOCAL_LLM = "local_llm"
    # One member per provider in config/llm_providers.json, with the
    # provider's name as its value: _detect_backend_from_model builds the
    # member from the table, so a provider missing here is a ValueError there.
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    MAMMOUTH = "mammouth"
    MISTRAL = "mistral"
    IONOS = "ionos"
    AWS_BEDROCK = "bedrock"
    COMFYUI = "comfyui"
    # Direct inference backend
    DIFFUSERS = "diffusers"  # Direct HuggingFace Diffusers
    # Python chunks: Self-contained executable Python modules (HeartMuLa, future backends)
    PYTHON = "python"
    PASSTHROUGH = "passthrough"  # text_passthrough chunks: no backend, frontend renders

    @classmethod
    def _missing_(cls, value):
        """Backward compat: accept legacy 'ollama' value during migration."""
        if value == "ollama":
            return cls.LOCAL_LLM
        return None


# The backends a schema pipeline's text step runs on: this machine, and every
# provider in the table. A request on one of these goes to the Prompt
# Interception Engine; anything else is an output chunk.
_LLM_BACKENDS = frozenset({BackendType.LOCAL_LLM} | {BackendType(n) for n in provider_names()})


@dataclass
class BackendRequest:
    """Request für Backend-Verarbeitung"""
    backend_type: BackendType
    model: str
    prompt: str
    parameters: Dict[str, Any]
    stream: bool = False
    # What the usage tracker books this request's tokens under: set by the
    # executor from the config's stage (pipeline_executor.usage_stage_of).
    usage_stage: str = 'stage2'

@dataclass 
class BackendResponse:
    """Response von Backend"""
    success: bool
    content: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def _random_seed() -> int:
    """A fresh seed where a request said 'random' (three sites until 2026-10-10)."""
    return random.randint(0, 2**32 - 1)


def _set_node_field(workflow: dict, node_id: str, field: str, value) -> None:
    """Write `value` into workflow[node_id] under the dotted `field` path
    ("inputs.image"), creating the intermediate dicts; the caller has checked
    that the node is in the workflow."""
    field_parts = field.split('.')
    target = workflow[node_id]
    for part in field_parts[:-1]:
        target = target.setdefault(part, {})
    target[field_parts[-1]] = value


async def _queue_refusal(client, what: str):
    """(refusal, queue depth): the one refusal that really is a full queue.

    It says so in the same terms as the gate, so the surface has one place to
    read a busy state from. Three submission paths carried this block until
    2026-10-10; `what` names the path in the warning as each of them did."""
    queue_status = await client.get_queue_status()
    queue_depth = queue_status.get("total", 0)
    if queue_depth >= COMFYUI_MAX_QUEUE_DEPTH:
        logger.warning(f"[COMFYUI] Queue full ({queue_depth}/{COMFYUI_MAX_QUEUE_DEPTH}), rejecting {what}")
        return BackendResponse(
            success=False, content="",
            error=f"ComfyUI queue full ({queue_depth} pending). Please try again in a moment.",
            metadata={"busy": {"reason": "queue_full", "holder_kind": "",
                               "waiting": queue_depth}},
        ), queue_depth
    return None, queue_depth

class BackendRouter:
    """Router für verschiedene KI-Backends"""

    def __init__(self):
        self.backends: Dict[BackendType, Any] = {}
        self._initialized = False

        # Initialize ComfyUI manager for auto-recovery
        from my_app.services.comfyui_manager import get_comfyui_manager
        self.comfyui_manager = get_comfyui_manager()
        logger.info("[ROUTER] ComfyUI manager initialized")
    
    def initialize(self, llm_service=None, workflow_logic_service=None, comfyui_service=None):
        """Router mit Legacy-Services initialisieren"""
        if llm_service:
            self.backends[BackendType.LOCAL_LLM] = llm_service
            logger.info("Local LLM backend registriert")
        
        if comfyui_service:
            self.backends[BackendType.COMFYUI] = comfyui_service
            logger.info("ComfyUI-Backend registriert")
            
        self._initialized = True
        logger.info(f"Backend-Router initialisiert mit {len(self.backends)} Backends")

    @staticmethod
    def _is_card_fault(reason: Optional[str]) -> bool:
        """The card is the problem, so a second model on it is no answer.

        Falling back here would start a different model for the same press —
        which this platform does not do — and would put a second heavy operation
        on a card that just said it has no room. The person waiting is told to
        wait; the run they asked for is the run they get.

        The three shapes this takes, all read from what the failing side sends:

          device busy         the gate, while another run holds the card
          gpu not reachable   the gate, after the driver stopped answering
          out of memory       torch, in the words of CUDA's own allocator
                              ("CUDA out of memory. Tried to allocate ...")

        Out of memory was missing until 2026-09-07, and it is the one that
        mattered most: an exhausted card sent the run to the ComfyUI twin, which
        made the picture on the same exhausted card and reported success. The
        run was then booked under the config nobody had run.
        """
        if not reason:
            return False
        low = str(reason).lower()
        return ("device busy" in low
                or "gpu not reachable" in low
                or "out of memory" in low)

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
        if self._is_card_fault(reason):
            logger.info(f"[FALLBACK] {chunk_name}: the card is the problem ({reason}) — "
                        f"not switching models")
            return BackendResponse(success=False, content="", error=reason)

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
                actual_backend not in _LLM_BACKENDS and actual_backend is not BackendType.COMFYUI
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
            if actual_backend in _LLM_BACKENDS:
                # Create modified request with detected backend for proper routing
                modified_request = BackendRequest(
                    backend_type=actual_backend,
                    model=request.model,
                    prompt=request.prompt,
                    parameters=request.parameters,
                    stream=request.stream,
                    usage_stage=request.usage_stage,
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
        - local/model-name → LOCAL_LLM (local inference)
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
        # Empty model, prefix-only ("local/", "<provider>/") or no prefix at
        # all → use fallback. This is important for Proxy-Chunks (output_image)
        # which have empty model.
        head, _, path = (model or "").partition("/")
        if not path:
            logger.debug(f"[BACKEND-DETECT] Model '{model}' empty, prefix-only or bare → {fallback_backend.value} (fallback)")
            return fallback_backend

        # The first segment names the service: 'local' is this machine, and the
        # table (config/llm_providers.json) says which other names are
        # providers. Until 2026-09-12 a ladder of six prefixes stood here and
        # knew neither ionos/ nor mammouth/, which therefore took the fallback.
        if head == "local":
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → LOCAL_LLM (local)")
            return BackendType.LOCAL_LLM
        provider = provider_of(model)
        if provider is not None:
            backend = BackendType(provider)
            logger.debug(f"[BACKEND-DETECT] Model '{model}' → {backend.name} ({provider_entry(provider)['label']})")
            return backend
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

            # No length guidance and no token clamp here. Both used to sit at
            # this point, keyed on the deployment-wide UI_MODE, and both hit
            # EVERY chunk that passes through — translation and the safety
            # checks included, which is not where a reading limit belongs. The
            # reading volume is now a filter-dependent clause on the
            # interception meta-prompt (instruction_selector), and output caps
            # are permitted only where a provider API demands the field.
            #
            # The safety ceiling that briefly returned here (2026-08-05) is
            # gone for good: the Stage-3 Llama-Guard call it protected now
            # checks long text in bounded windows and stops the run when no
            # verdict exists (stage_orchestrator, work order A1) — an output
            # cap is not part of the safety chain any more.
            prompt = request.prompt
            params = dict(request.parameters)

            # Pass pre-built prompt directly — ChunkBuilder already assembled it correctly
            pi_engine = PromptInterceptionEngine()
            pi_request = PromptInterceptionRequest(
                input_prompt="",
                prebuilt_prompt=prompt,
                model=model,
                debug=params.get('debug', False),
                unload_model=params.get('unload_model', False),
                parameters=params,
                usage_stage=request.usage_stage,
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
                        'backend_type': request.backend_type.value,
                        # Which branch of the engine actually ran, service prefix
                        # included. Additive beside the two above: they keep the
                        # meaning they had, and a reader that has to name the
                        # model a text was written by reads this one.
                        'dispatched_model': pi_response.dispatched_model,
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
    
    
    async def _process_comfyui_request(self, comfyui_service, request: BackendRequest) -> BackendResponse:
        """ComfyUI-Request verarbeiten mit Output-Chunks oder Legacy-Workflow-Generator"""
        try:
            # Schema-Pipeline-Output ist der optimierte Prompt
            schema_output = request.prompt

            # Check if we have an output_chunk specified
            output_chunk_name = request.parameters.get('output_chunk') or request.parameters.get('OUTPUT_CHUNK')

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
                # No output_chunk specified — this should not happen in current pipelines
                logger.error("ComfyUI request without output_chunk parameter — all pipelines must specify OUTPUT_CHUNK")
                return BackendResponse(
                    success=False,
                    content="",
                    error="No output_chunk specified. All pipelines must define OUTPUT_CHUNK in their config."
                )

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
        - Images: Use ComfyUI simple text2image workflow
        - Audio/Video: Use custom workflow submission via ComfyUI WebSocket
        """
        try:
            # 1. Check for Python-Chunk first (new standard)
            chunk_py_path = Path(__file__).parent.parent / "chunks" / f"{chunk_name}.py"
            if chunk_py_path.exists():
                # Same rule as the has_loras branch below, only earlier: a chunk
                # that cannot apply LoRAs names the one that can, and a run that
                # carries them goes there instead of failing quietly.
                if parameters.get('loras'):
                    lora_chunk = self._lora_chunk_for(chunk_py_path)
                    if lora_chunk and lora_chunk != chunk_name:
                        logger.info(f"[ROUTER] '{chunk_name}' cannot apply LoRAs — "
                                    f"running '{lora_chunk}' instead")
                        return await self._process_output_chunk(lora_chunk, prompt, parameters)
                logger.info(f"[ROUTER] Detected Python chunk: {chunk_name}.py")
                result = await self._execute_python_chunk(chunk_py_path, parameters)
                if result.success:
                    return result

                # Fallback: Read CHUNK_META.fallback_chunk from the loaded module
                import sys
                module = sys.modules.get(f"chunk_{chunk_name}")
                fallback_name = getattr(module, 'CHUNK_META', {}).get('fallback_chunk') if module else None
                if fallback_name and self._is_card_fault(result.error):
                    logger.info(f"[FALLBACK] Python chunk '{chunk_name}': the card is the "
                                f"problem ({result.error}) — not switching to '{fallback_name}'")
                    return result
                if fallback_name:
                    logger.info(f"[FALLBACK] Python chunk '{chunk_name}' failed ({result.error}), trying '{fallback_name}'")
                    # Re-enter _process_output_chunk so fallback works for both .py and .json chunks
                    return await self._process_output_chunk(fallback_name, None, parameters)
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
            chunk_type = chunk.get('type', 'output_chunk')
            logger.info(f"Loaded Output-Chunk: {chunk_name} ({media_type} media, {execution_mode} mode, {backend_type} backend)")

            # FIX: Extract text prompt from parameters (not from 'prompt' param which is workflow dict)
            # Fallback chain: prompt → PREVIOUS_OUTPUT → prompt_3 (user text/T5) → TEXT_1 (clip_l)
            # prompt_3 preferred over TEXT_1 because it's natural language (TEXT_1 may be CLIP keywords)
            text_prompt = (
                parameters.get('prompt', '')
                or parameters.get('PREVIOUS_OUTPUT', '')
                or parameters.get('prompt_3', '')
                or parameters.get('TEXT_1', '')
            )
            logger.info(f"[DEBUG-FIX] Extracted text_prompt from parameters: '{text_prompt[:200]}...'" if text_prompt else f"[DEBUG-FIX] ⚠️ No text prompt in parameters!")

            # Route by chunk type FIRST — api_output_chunk and text_passthrough bypass ComfyUI entirely
            if chunk_type == 'api_output_chunk':
                logger.info(f"[ROUTER] Using API output for '{chunk_name}' (backend: {backend_type})")
                return await self._process_api_output_chunk(chunk_name, text_prompt, parameters, chunk)
            elif chunk_type == 'text_passthrough':
                logger.info(f"[ROUTER] Using text passthrough for '{chunk_name}'")
                return BackendResponse(
                    success=True,
                    content=text_prompt,
                    metadata={
                        'chunk_name': chunk_name,
                        'backend_type': backend_type,
                        'frontend_processor': chunk.get('meta', {}).get('frontend_processor'),
                        'passthrough': True
                    }
                )

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
                    logger.info(f"[ROUTER] Using ComfyUI simple API for '{chunk_name}'")
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
        """Process image chunks via ComfyUI WebSocket."""
        try:
            # Extract parameters from input_mappings
            import sys
            from pathlib import Path
            devserver_path = Path(__file__).parent.parent.parent
            if str(devserver_path) not in sys.path:
                sys.path.insert(0, str(devserver_path))

            input_mappings = chunk['input_mappings']
            input_data = {'prompt': prompt, **parameters}


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
                seed = _random_seed()
                logger.info(f"Generated random seed: {seed}")
            else:
                seed = int(seed)

            # If chunk has a workflow, use submit_and_track
            if chunk.get('workflow'):
                return await self._process_workflow_chunk(chunk_name, prompt, parameters, chunk)

            # Simple image (no workflow)
            from my_app.services.comfyui_ws_client import get_comfyui_ws_client

            logger.info("[COMFYUI] Ensuring ComfyUI is available...")
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

            # Queue depth guard: reject early instead of waiting for timeout
            refusal, queue_depth = await _queue_refusal(client, "simple t2i")
            if refusal is not None:
                return refusal

            logger.info(f"[COMFYUI] Generating image: model={model}, steps={steps}, size={width}x{height} (queue: {queue_depth})")

            result = await client.submit_and_track(workflow, timeout=parameters.get('timeout', COMFYUI_TIMEOUT), on_progress=get_progress_callback())

            latent_b64, latent_meta, media = _split_off_latent(
                result.media_files, chunk.get('latent_decoder'))

            if not media:
                return BackendResponse(success=False, content="", error="ComfyUI generated no output")

            return BackendResponse(
                success=True,
                content="comfyui_generated",
                metadata={
                    'chunk_name': chunk_name,
                    'media_type': media_type,
                    'prompt_id': result.prompt_id,
                    **({'latent_data': latent_b64,
                        'latent_meta': latent_meta} if latent_b64 else {}),
                    'media_files': [f.data for f in media],
                    'outputs_metadata': [{'filename': f.filename, 'type': f.media_type, 'node_id': f.node_id} for f in media],
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
        """Build a minimal ComfyUI workflow JSON for simple text-to-image generation."""
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
        """Process audio/video/image chunks using custom ComfyUI workflows via WebSocket."""
        try:
            # 1. Load workflow from chunk (deepcopy: chunk is cached, concurrent
            # requests would mutate the same dict via input_mappings)
            import copy
            workflow = copy.deepcopy(chunk.get('workflow'))
            if not workflow:
                return BackendResponse(
                    success=False,
                    content="",
                    error=f"No workflow found in chunk '{chunk_name}'"
                )

            media_type = chunk.get('media_type', 'unknown')
            logger.info(f"[WORKFLOW-CHUNK] Processing {media_type} chunk: {chunk_name}")

            # 1.5. Inject LoRA nodes (config-specific or global fallback)
            loras = parameters.get('loras', LORA_TRIGGERS)
            if loras:
                logger.info(f"[LORA] Injecting {len(loras)} LoRA(s): {[l['name'] for l in loras]}")
                workflow = self._inject_lora_nodes(workflow, loras)

            # 2. Detect mapping format and apply input mappings
            input_mappings = chunk.get('input_mappings', {})
            input_data = {'prompt': prompt, **parameters}

            # ComfyUI fallback: if chunk has no triple-prompt support but prompt_3
            # (user's original text) is available, use it as main prompt instead of
            # the optimized clip_l keywords which would look terrible on single-prompt workflows
            if 'prompt_3' in parameters and 'prompt_3' not in input_mappings:
                logger.info(f"[WORKFLOW-CHUNK] No prompt_3 mapping — using user text (T5) as main prompt for ComfyUI fallback")
                input_data['prompt'] = parameters['prompt_3']

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
                            value = _random_seed()
                        generated_seed = value
                        logger.info(f"Generated seed: {generated_seed}")

                    placeholder = mapping.get('template', f'{{{{{key.upper()}}}}}')
                    workflow_str = workflow_str.replace(placeholder, str(value))
                    logger.debug(f"Replaced '{placeholder}' with '{str(value)[:50]}...'")

                workflow = json.loads(workflow_str)

            # Submit workflow via ComfyUI WebSocket
            from my_app.services.comfyui_ws_client import get_comfyui_ws_client

            logger.info("[COMFYUI] Ensuring ComfyUI is available...")
            if not await self.comfyui_manager.ensure_comfyui_available():
                return BackendResponse(success=False, content="", error="ComfyUI not available")

            client = get_comfyui_ws_client()
            if not await client.health_check():
                return BackendResponse(success=False, content="", error="ComfyUI not reachable")

            # Queue depth guard: reject early instead of waiting for timeout
            refusal, queue_depth = await _queue_refusal(client, f"{media_type} submission")
            if refusal is not None:
                return refusal

            # An input image reaches ComfyUI as an upload, as on the legacy path:
            # LoadImage accepts only files inside ComfyUI's input directory
            # (upstream since 0.28, here since the update to 0.36), and the
            # mapping above wrote the value it was given. The upload writes the
            # stored name over it, under the lease right before the workflow
            # goes up, because a restart during the wait empties that directory.
            async def upload_input_image():
                await self._handle_legacy_image_uploads(workflow, input_mappings, parameters)

            logger.info(f"[COMFYUI] Submitting {media_type} workflow (queue: {queue_depth})")
            timeout = parameters.get('timeout', COMFYUI_TIMEOUT)

            result = await client.submit_and_track(workflow, timeout=timeout, on_progress=get_progress_callback(),
                                                   before_submit=upload_input_image)

            latent_b64, latent_meta, media = _split_off_latent(
                result.media_files, chunk.get('latent_decoder'))

            if not media:
                return BackendResponse(
                    success=False, content="",
                    error=f"No {media_type} files in workflow output"
                )

            logger.info(f"[COMFYUI] Workflow complete: {len(media)} file(s) in {result.execution_time:.1f}s")

            metadata = {
                'chunk_name': chunk_name,
                'media_type': media_type,
                'prompt_id': result.prompt_id,
                'media_files': [f.data for f in media],
                'outputs_metadata': [
                    {'filename': f.filename, 'type': f.media_type,
                     'subfolder': f.subfolder, 'node_id': f.node_id}
                    for f in media
                ],
                'seed': generated_seed,
                'workflow_completed': True,
            }
            if latent_b64:
                # The same two keys the Diffusers sink fills, read by
                # _save_output_latent in schema_pipeline_routes.
                metadata['latent_data'] = latent_b64
                metadata['latent_meta'] = latent_meta

            return BackendResponse(
                success=True,
                content="workflow_generated",
                metadata=metadata,
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
        """Process legacy workflow: Complete workflow passthrough with title-based prompt injection."""
        try:
            chunk_name = chunk.get('name', 'unknown')
            media_type = chunk.get('media_type', 'image')

            logger.info(f"[LEGACY-WORKFLOW] Processing legacy workflow: {chunk_name}")
            logger.info(f"[DEBUG-PROMPT] Received prompt parameter: '{prompt[:200]}...'" if prompt else f"[DEBUG-PROMPT] Prompt is EMPTY or None: {repr(prompt)}")
            logger.info(f"[DEBUG-PROMPT] Received parameters: {list(parameters.keys())}")

            # Get workflow from chunk (deepcopy: chunk is cached, concurrent
            # requests would mutate the same dict via input_mappings)
            import copy
            workflow = copy.deepcopy(chunk.get('workflow'))
            if not workflow:
                return BackendResponse(
                    success=False,
                    content="",
                    error="No workflow definition in legacy chunk"
                )

            # Apply ALL input_mappings (prompt, seed, image inputs, etc.)
            generated_seed = None
            input_mappings = chunk.get('input_mappings', {})
            if input_mappings:
                input_data = {'prompt': prompt, **parameters}
                logger.info(f"[LEGACY-WORKFLOW] Applying input_mappings for: {list(input_mappings.keys())}")
                workflow, generated_seed = self._apply_input_mappings(workflow, input_mappings, input_data)
                if generated_seed is not None:
                    logger.info(f"[LEGACY-WORKFLOW] Generated seed: {generated_seed}")

            # Handle alpha_factor for T5-CLIP fusion workflows
            if input_mappings and 'alpha' in input_mappings and 'alpha_factor' in parameters:
                alpha_mapping = input_mappings['alpha']
                alpha_value = parameters['alpha_factor']

                logger.info(f"[LEGACY-WORKFLOW] Injecting alpha_factor={alpha_value}")

                alpha_node_id = alpha_mapping.get('node_id')
                alpha_field = alpha_mapping.get('field', 'inputs.value')
                if alpha_node_id and alpha_node_id in workflow:
                    _set_node_field(workflow, alpha_node_id, alpha_field, alpha_value)
                    logger.info(f"[ALPHA-INJECT] Injected alpha={alpha_value} into node {alpha_node_id}.{alpha_field}")

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
                workflow = _adapt_workflow_for_multi_image(
                    workflow, parameters, chunk.get('multi_image_adaptation'))

            from my_app.services.comfyui_ws_client import get_comfyui_ws_client
            from my_app.services.legacy_workflow_service import inject_prompt, replace_llm_models

            workflow, injection_success = inject_prompt(workflow, prompt, chunk)
            if not injection_success:
                logger.warning("[LEGACY-WORKFLOW] Prompt injection failed, continuing anyway")

            # Replace LLM model names
            workflow = replace_llm_models(workflow)

            logger.info("[COMFYUI] Ensuring ComfyUI is available...")
            if not await self.comfyui_manager.ensure_comfyui_available():
                return BackendResponse(success=False, content="", error="ComfyUI not available")

            client = get_comfyui_ws_client()

            # Queue depth guard: reject early instead of waiting for timeout
            refusal, queue_depth = await _queue_refusal(client, "legacy workflow")
            if refusal is not None:
                return refusal

            timeout = parameters.get('timeout', COMFYUI_TIMEOUT)

            result = await client.submit_and_track(workflow, timeout=timeout, on_progress=get_progress_callback())

            # No legacy workflow keeps a latent today. The split stands here
            # anyway: the day one does, a latent handed on as a picture is a
            # defect nothing would report.
            latent_b64, latent_meta, media = _split_off_latent(
                result.media_files, chunk.get('latent_decoder'))

            logger.info(f"[LEGACY-WORKFLOW] Completed: {len(media)} file(s)")

            return BackendResponse(
                success=True,
                content="workflow_generated",
                metadata={
                    'chunk_name': chunk_name,
                    'media_type': media_type,
                    'prompt_id': result.prompt_id,
                    'legacy_workflow': True,
                    **({'latent_data': latent_b64,
                        'latent_meta': latent_meta} if latent_b64 else {}),
                    'media_files': [f.data for f in media],
                    'outputs_metadata': [
                        {'node_id': f.node_id, 'type': f.media_type,
                         'filename': f.filename, 'subfolder': f.subfolder}
                        for f in media
                    ],
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

        from my_app.services.comfyui_ws_client import get_comfyui_ws_client

        logger.info("[LEGACY-WORKFLOW] Uploading image via ComfyUI WS client...")
        if not await self.comfyui_manager.ensure_comfyui_available():
            logger.error("[LEGACY-WORKFLOW] ComfyUI not available for image upload")
            return

        client = get_comfyui_ws_client()
        with open(source_path, 'rb') as f:
            image_data = f.read()

        uploaded_filename = await client.upload_image(image_data, source_file.name)

        if uploaded_filename:
            logger.info(f"[LEGACY-WORKFLOW] Uploaded image: {uploaded_filename}")
            image_node_id = image_mapping.get('node_id')
            image_field = image_mapping.get('field', 'inputs.image')
            if image_node_id and image_node_id in workflow:
                _set_node_field(workflow, image_node_id, image_field, uploaded_filename)

    async def _handle_legacy_multi_image_uploads(
        self, workflow: Dict[str, Any], input_mappings: Dict[str, Any],
        parameters: Dict[str, Any], multi_image_keys: List[str]
    ):
        """Handle multi-image uploads (input_image1/2/3)."""
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
                        _set_node_field(workflow, image_node_id, image_field, uploaded_filename)
                        logger.info(f"[LEGACY-WORKFLOW] Injected {image_key}: {uploaded_filename}")
            except Exception as e:
                logger.error(f"[LEGACY-WORKFLOW] Error uploading {image_key}: {e}")
                import traceback
                traceback.print_exc()

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

            # The chunk names its provider; the table says where that
            # provider's key is kept and reads it the way every other cloud
            # call on the platform does. Until 2026-09-12 a ladder here mapped
            # three names to key files and gave every other name -- mistral,
            # ionos, a typo -- the OpenRouter key.
            provider = api_config.get('provider')
            entry = provider_entry(provider or "")
            if entry is None:
                error_msg = (f"Output chunk {chunk_name} names provider '{provider}', "
                             f"which config/llm_providers.json does not carry.")
                logger.error(error_msg)
                return BackendResponse(success=False, error=error_msg)
            _, api_key = provider_credentials(provider)
            if not api_key:
                error_msg = (f"{entry['label']} API key not found. Set {entry.get('env_var')} "
                             f"or create '{entry.get('key_file')}' in devserver root.")
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
                                choice = data.get('choices', [{}])[0] if isinstance(data, dict) else {}
                                finish_reason = choice.get('finish_reason', '') if isinstance(choice, dict) else ''
                                usage = data.get('usage', {}) if isinstance(data, dict) else {}
                                items = data.get('data') if isinstance(data, dict) else None
                                empty_result_list = isinstance(items, list) and len(items) == 0
                                if finish_reason in ('content_filter', 'safety'):
                                    error_msg = f"Content safety filter: API refused image generation (finish_reason={finish_reason})"
                                    logger.error(f"[CONTENT-SAFETY] {error_msg}")
                                elif empty_result_list and usage.get('output_tokens') == 0:
                                    # Multimodal chat models served through an images endpoint (Gemini 3 Pro Image)
                                    # answer story-shaped prompts with TEXT. The endpoint adapter drops that text and
                                    # returns an empty result list with zero image tokens. Not a safety rejection.
                                    error_msg = ("The model returned text instead of an image. "
                                                 "A prompt that reads like a story gets continued as a story. "
                                                 "Describe what should be seen in the picture instead.")
                                    logger.error(f"[TEXT-NOT-IMAGE] {error_msg} usage={usage}")
                                else:
                                    keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
                                    error_msg = f"No image data in API response (HTTP 200, keys={keys})"
                                    logger.error(f"[API-OUTPUT] {error_msg} usage={usage}")
                                return BackendResponse(success=False, content="", error=error_msg, metadata={})

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
                        # Truncate HTML error pages (e.g. Cloudflare 504) to avoid log spam
                        if '<html' in error_text.lower():
                            error_text = f"[HTML error page truncated] Status {response.status}"
                        elif len(error_text) > 500:
                            error_text = error_text[:500] + '...'
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
            # Check finish_reason for content-filter stops (OpenRouter/Gemini)
            choice = data.get('choices', [{}])[0]
            finish_reason = choice.get('finish_reason', '')
            if finish_reason in ('content_filter', 'safety'):
                logger.warning(f"[CONTENT-SAFETY] API refused generation: finish_reason='{finish_reason}'")
                return None

            message = choice.get('message', {})
            if not message:
                logger.warning("[CONTENT-SAFETY] Empty message in API response — likely content-safety rejection")
                return None

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

            # No image found — check if there's a text-only response (content-safety refusal)
            text_content = ''
            if isinstance(content, str):
                text_content = content
            elif isinstance(content, list):
                text_content = ' '.join(item.get('text', '') for item in content if item.get('type') == 'text')

            if text_content:
                logger.warning(f"[CONTENT-SAFETY] API returned text without image (probable content-safety refusal): "
                               f"'{text_content[:200]}'")
            else:
                logger.warning("[CONTENT-SAFETY] API returned empty response without image — likely content-safety rejection")

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

            items = data.get('data')
            if not isinstance(items, list):
                detail = f"no result list (type={type(items).__name__})"
            elif not items:
                detail = "result list is empty (model produced no image)"
            else:
                first = items[0]
                detail = f"result[0] keys={list(first.keys()) if isinstance(first, dict) else type(first).__name__}"
            logger.error(f"[IMAGES-API] No base64 data found in response. {detail}, "
                         f"usage={data.get('usage')}, top-level keys={list(data.keys())}")
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
            DIRECT_BACKENDS = ['diffusers', 'heartmula']

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
        # Bound before the try, so the handler below can name it whatever the
        # chunk did.
        from my_app.services.gpu_lease_client import GpuBusyError

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
            # Erst ausfuehren, dann veroeffentlichen. Andersherum lag ein halb
            # ausgefuehrtes Modul unter seinem Namen, und der Rueckfall-Weg
            # (`_process_output_chunk`, `sys.modules.get(...)`) konnte es aus
            # einem anderen Thread lesen: `CHUNK_META` leer, `fallback_chunk`
            # still uebersprungen. Fuer HeartMuLa folgenlos, fuer
            # `output_image_sd35_diffusers` nicht. Wirft `exec_module`, steht
            # jetzt gar nichts unter dem Namen statt eines kaputten Moduls.
            spec.loader.exec_module(module)
            sys.modules[spec.name] = module

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
            if (chunk_name.startswith('output_music_')
                    or chunk_name.startswith('output_audio_')
                    or chunk_name.startswith('output_speech_')):
                import base64
                # Extract backend name (e.g., "output_music_heartmula" -> "heartmula")
                backend_name = (chunk_name
                                .replace('output_music_', '')
                                .replace('output_audio_', '')
                                .replace('output_speech_', ''))
                # The format comes from the chunk, not from a guess: HeartMuLa
                # returns mp3, the speech chunks return wav, and mislabelling the bytes
                # makes them unplayable in the browser.
                audio_format = (getattr(module, 'CHUNK_META', {}) or {}).get('output_format', 'mp3')
                return BackendResponse(
                    success=True,
                    content=f"{backend_name}_generated",  # e.g. "heartmula_generated"
                    metadata={
                        "chunk_type": "python",
                        "chunk_name": chunk_name,
                        "media_type": "music" if "music" in chunk_name else "audio",
                        "backend": backend_name,
                        "audio_data": base64.b64encode(result).decode('utf-8'),
                        "audio_format": audio_format,
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

        except GpuBusyError as e:
            # A busy card is a state, not a breakdown, and WHICH busy is the
            # only thing the person turned away can act on. It travels beside
            # the sentence instead of inside it: read off prose at the far end,
            # every one of these arrived as "queue full". The gate's own words
            # stay the message, without the "chunk execution failed" dressing —
            # they are what the hover shows.
            logger.info(f"[PYTHON-CHUNK] Card busy ({e.reason}): {e}")
            return BackendResponse(
                success=False,
                content="",
                error=str(e),
                metadata={"busy": {"reason": e.reason,
                                   "holder_kind": e.holder_kind,
                                   "waiting": e.waiting}},
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

    def _lora_chunk_for(self, chunk_py_path: Path) -> Optional[str]:
        """The chunk a python chunk names for runs that carry LoRAs.

        Read, not imported: importing a chunk to ask a question about it would
        pull a model backend in as a side effect.
        """
        import ast
        try:
            source = chunk_py_path.read_text(encoding='utf-8')
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            return None

        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(getattr(target, 'id', None) == 'CHUNK_META' for target in node.targets):
                continue
            try:
                meta = ast.literal_eval(node.value)
            except ValueError:
                return None
            return meta.get('lora_chunk') if isinstance(meta, dict) else None
        return None

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
        # Where the text encoders get their CLIP from, found by FOLLOWING THE
        # WIRE rather than by the name of the loader node.
        #
        # It matched `DualCLIPLoader` by name until 2026-08-29; the mismatch
        # dates from when output_image_sd35_large.json swapped that
        # loader for `TripleCLIPLoader` to stop dropping the CLIP-L prompt. The
        # injector was not swapped with it, so `clip_source` stayed None, the
        # chain fell back to the checkpoint's CLIP output — and
        # `sd3.5_large.safetensors` carries no text encoder at all (1168
        # tensors: 923 MMDiT, 244 VAE, zero `text_encoder`). The LoraLoader
        # therefore got `clip=None` and built no key map, and the text-encode
        # nodes went on reading the untouched loader anyway, because only
        # `model` consumers were rewired below.
        #
        # What that cost: the ENCODER HALF of every adapter, on every run.
        # `sd35_destroyednegative` holds 1923 tensors, 792 of them `lora_te1`
        # and `lora_te2` — 41 %. Thirty days of ComfyUI's log hold 3168 lines
        # `lora key not loaded`, all of them `lora_te*` and not one
        # `lora_unet*`. Those are the weights that bind the trigger word to
        # what was trained, so an adapter answered to its trigger with the
        # trigger's own untouched embedding.
        #
        # By the wire it holds for any loader: DualCLIPLoader, TripleCLIPLoader,
        # CLIPLoader, or a checkpoint that brings its own encoders.
        clip_source = None
        clip_consumers = []
        model_consumers = []
        for node_id, node in workflow.items():
            if isinstance(node, dict) and 'inputs' in node:
                inputs = node['inputs']
                # Check if this node takes model from checkpoint
                if inputs.get('model') == [checkpoint_node_id, 0]:
                    model_consumers.append(node_id)
                wired = inputs.get('clip')
                if isinstance(wired, list) and len(wired) == 2:
                    if clip_source is None:
                        clip_source = list(wired)
                    # Only the consumers of THAT source go through the chain. A
                    # workflow with a second, separate CLIP keeps it.
                    if list(wired) == clip_source:
                        clip_consumers.append(node_id)

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

        # 5. And the text encoders, or the chain's CLIP output hangs unused and
        #    the adapter's `lora_te*` weights never reach an encoder.
        for consumer_id in clip_consumers:
            workflow[consumer_id]['inputs']['clip'] = prev_clip_source
            logger.info(f"[LORA] Updated node {consumer_id} to receive CLIP from LoRA chain")

        return workflow

    def _apply_input_mappings(self, workflow: Dict, mappings: Dict[str, Any], input_data: Dict[str, Any]) -> Tuple[Dict, Optional[int]]:
        """Apply input_mappings to workflow - inject prompts and parameters

        Supports two formats:
        1. Single mapping: "key": {"node_id": "X", "field": "Y"}
        2. Multi-node mapping: "key": [{"node_id": "X", "field": "Y"}, {...}]

        Returns:
            Tuple[Dict, Optional[int]]: (modified_workflow, generated_seed)
        """

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
                    value = _random_seed()
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



def _split_off_latent(media_files, decoder=None):
    """(latent as base64 or None, what describes it, the media without it).

    A kept latent travels the same road as a picture -- announced by
    AI4ArtsEdKeepLatent, fetched by the ws client -- and must leave it again
    before anything downstream reads the media files as pictures.

    The description is what the node measured off the array it wrote, plus the
    `latent_decoder` its chunk declares. Both halves are required: without a
    model to decode it by, a stored latent is one the platform HAS and cannot
    use, and the instrument refuses those rather than quietly showing a
    different picture under the same name.
    """
    latent_b64 = None
    latent_meta = {}
    dropped = 0
    media = []
    for f in media_files:
        if f.media_type != "latent":
            media.append(f)
        elif latent_b64 is None:
            latent_b64 = base64.b64encode(f.data).decode("ascii")
            latent_meta = dict(f.meta or {})
        else:
            dropped += 1
    if dropped:
        logger.warning(
            f"[COMFYUI] {dropped} further latent(s) arrived and were dropped: "
            f"the contract downstream holds one latent per run"
        )
    if latent_b64 is not None:
        named = {k: v for k, v in (decoder or {}).items() if not k.startswith("_")}
        latent_meta.update(named)
        missing = [k for k in ("model_id", "pipeline_class") if not latent_meta.get(k)]
        if missing:
            # Kept and undecodable is worse than not kept: the instrument would
            # answer the whole set with an error. Drop it and say why; the set
            # is then meaned pixel by pixel, as it was before the chunk asked.
            logger.warning(
                f"[COMFYUI] a latent was kept but its chunk declares no "
                f"{', '.join(missing)} - dropping it rather than storing one "
                f"nothing can decode"
            )
            return None, {}, media
    return latent_b64, latent_meta, media
