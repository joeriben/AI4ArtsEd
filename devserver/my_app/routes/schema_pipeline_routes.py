"""
Schema Pipeline Routes - API für Schema-basierte Pipeline-Execution
"""

from flask import Blueprint, request, jsonify, Response, stream_with_context
from pathlib import Path
import logging
import asyncio
import threading
import json
import uuid
import config  # Session 154: For CODING_MODEL resolution in _load_model_from_output_config
from config import OLLAMA_MAX_CONCURRENT
import requests  # For direct Ollama calls (DSGVO LLM verification)

# Schema-Engine importieren
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from schemas.engine.pipeline_executor import PipelineExecutor
from schemas.engine.prompt_interception_engine import PromptInterceptionEngine, PromptInterceptionRequest
from schemas.engine.config_loader import config_loader
from schemas.engine.progress_callback import set_progress_callback
from schemas.engine.instruction_selector import get_instruction
from schemas.engine.stage_orchestrator import (
    execute_stage1_translation,
    execute_stage1_safety,
    execute_stage1_safety_unified,
    execute_stage3_safety,
    execute_stage3_safety_code,
    build_safety_message,
    fast_filter_bilingual_86a,
    fast_filter_check,
    fast_dsgvo_check,
    llm_verify_person_name,
    llm_verify_age_filter_context
)
from my_app.utils.circuit_breaker import safety_breaker

# Execution History Tracking (OLD - DEPRECATED in Session 29)
# from execution_history import ExecutionTracker

# No-op tracker to gracefully deprecate OLD ExecutionTracker
class NoOpTracker:
    """
    Session 29: No-op tracker that does nothing.
    Replaces OLD ExecutionTracker during migration to LivePipelineRecorder.
    """
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        # Return a no-op function for any method call
        def noop(*args, **kwargs):
            pass
        return noop

# Live Pipeline Recorder - Single source of truth (Session 37 Migration Complete)
from my_app.services.pipeline_recorder import get_recorder, load_recorder, generate_run_id

logger = logging.getLogger(__name__)

# Blueprint erstellen
schema_bp = Blueprint('schema', __name__, url_prefix='/api/schema')

# Backward compatibility blueprint (no prefix) for legacy frontend endpoints
# TODO: Remove after frontend migration complete
schema_compat_bp = Blueprint('schema_compat', __name__)

# Global Pipeline-Executor (wird bei App-Start initialisiert)
pipeline_executor = None

# Ollama Request Queue - Prevent concurrent overload of 120b model
# Use threading.Semaphore because asyncio.run() runs in separate event loops
ollama_queue_semaphore = threading.Semaphore(OLLAMA_MAX_CONCURRENT)
logger.info(f"[OLLAMA-QUEUE] Initialized with max concurrent requests: {OLLAMA_MAX_CONCURRENT}")

# Cache for output_config_defaults.json
_output_config_defaults = None

# Phase 4: Intelligent Seed Logic - Global State
# Tracks last prompt, seed, and output config for iterative image correction
_last_prompt = None
_last_seed = None
_last_output_config = None

def generate_sse_event(event_type: str, data: dict) -> str:
    """
    Generate Server-Sent Events (SSE) formatted message

    Args:
        event_type: Event type (e.g., 'connected', 'chunk', 'complete', 'blocked', 'error')
        data: Event data dictionary

    Returns:
        SSE-formatted string
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

def init_schema_engine():
    """Schema-Engine initialisieren"""
    global pipeline_executor
    if pipeline_executor is None:
        schemas_path = Path(__file__).parent.parent.parent / "schemas"
        pipeline_executor = PipelineExecutor(schemas_path)

        # Config Loader initialisieren (ohne Legacy-Services vorerst)
        pipeline_executor.config_loader.initialize(schemas_path)
        pipeline_executor.backend_router.initialize()
        pipeline_executor._initialized = True

        logger.info("Schema engine initialized")

def load_output_config_defaults():
    """Load output_config_defaults.json"""
    global _output_config_defaults

    if _output_config_defaults is None:
        try:
            defaults_path = Path(__file__).parent.parent.parent / "schemas" / "output_config_defaults.json"
            with open(defaults_path, 'r', encoding='utf-8') as f:
                _output_config_defaults = json.load(f)
            logger.info("output_config_defaults.json loaded")
        except Exception as e:
            logger.error(f"Failed to load output_config_defaults.json: {e}")
            _output_config_defaults = {}

    return _output_config_defaults

_cached_vram_tier = None

def _get_cached_vram_tier() -> str:
    """Get VRAM tier, cached after first detection."""
    global _cached_vram_tier
    if _cached_vram_tier is None:
        from my_app.routes.settings_routes import detect_gpu_vram
        result = detect_gpu_vram()
        _cached_vram_tier = result.get("vram_tier", "vram_8")
        logger.info(f"[VRAM-TIER] Detected and cached: {_cached_vram_tier}")
    return _cached_vram_tier


def _resolve_vram_tier_dict(tier_dict: dict) -> str:
    """Resolve a VRAM-tier dict to a config name.

    Matches the current VRAM tier, falling through to lower tiers
    if the exact tier has no entry.

    Args:
        tier_dict: e.g. {"vram_96": "config_large", "vram_24": "config_small"}

    Returns:
        Config name string or None
    """
    vram_tier = _get_cached_vram_tier()

    # Ordered from highest to lowest
    tier_order = ["vram_96", "vram_48", "vram_32", "vram_24", "vram_16", "vram_8"]

    # Find the current tier's index
    try:
        start_idx = tier_order.index(vram_tier)
    except ValueError:
        start_idx = len(tier_order) - 1  # Default to lowest

    # Try current tier, then fall through to lower tiers
    for tier in tier_order[start_idx:]:
        if tier in tier_dict:
            config_name = tier_dict[tier]
            logger.info(f"[VRAM-TIER] {vram_tier} → matched {tier} → {config_name}")
            return config_name

    logger.info(f"[VRAM-TIER] No matching tier for {vram_tier}")
    return None


def lookup_output_config(media_type: str) -> str:
    """
    Lookup Output-Config name from output_config_defaults.json

    Supports two value formats:
    - String: direct config name
    - Dict: VRAM-tier mapping (e.g. {"vram_96": "...", "vram_32": "..."})

    Args:
        media_type: image, audio, video, music, text

    Returns:
        Config name (e.g., "sd35_large") or None if not found
    """
    defaults = load_output_config_defaults()

    if media_type not in defaults:
        logger.warning(f"Unknown media type: {media_type}")
        return None

    config_name = defaults[media_type]

    # Dict = VRAM-tier mapping
    if isinstance(config_name, dict):
        config_name = _resolve_vram_tier_dict(config_name)

    # Filter out metadata keys that start with underscore
    if config_name and not str(config_name).startswith('_'):
        logger.info(f"Output-Config lookup: {media_type} → {config_name}")
        return config_name
    else:
        logger.info(f"No Output-Config for {media_type} (config_name={config_name})")
        return None


# ============================================================================
# HELPER FUNCTIONS FOR STAGE 2
# ============================================================================

def _load_optimization_instruction(output_config_name: str):
    """Load optimization_instruction for a given output config.

    Priority: output config meta > chunk meta (fallback).
    """
    try:
        if pipeline_executor is None:
            init_schema_engine()

        output_config_obj = pipeline_executor.config_loader.get_config(output_config_name)

        # 1. Check output config meta first (authoritative)
        if output_config_obj and hasattr(output_config_obj, 'meta'):
            opt_inst = output_config_obj.meta.get('optimization_instruction')
            if opt_inst:
                logger.info(f"[LOAD-OPT] Found in output config meta for '{output_config_name}' ({len(opt_inst)} chars)")
                return opt_inst

        # 2. Fallback: load from chunk meta (.py CHUNK_META or .json meta)
        if output_config_obj and hasattr(output_config_obj, 'parameters'):
            output_chunk_name = output_config_obj.parameters.get('OUTPUT_CHUNK')
            if output_chunk_name:
                import json
                from pathlib import Path
                chunks_dir = Path(__file__).parent.parent.parent / "schemas" / "chunks"

                # 2a. Try Python chunk CHUNK_META first
                chunk_py = chunks_dir / f"{output_chunk_name}.py"
                if chunk_py.exists():
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(f"opt_{output_chunk_name}", chunk_py)
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        chunk_meta = getattr(mod, 'CHUNK_META', {})
                        opt_inst = chunk_meta.get('optimization_instruction')
                        if opt_inst:
                            logger.info(f"[LOAD-OPT] Found in Python chunk '{output_chunk_name}' CHUNK_META for '{output_config_name}' ({len(opt_inst)} chars)")
                            return opt_inst
                    except Exception as e:
                        logger.debug(f"[LOAD-OPT] Failed to load Python chunk '{output_chunk_name}': {e}")

                # 2b. Fallback to JSON chunk
                chunk_file = chunks_dir / f"{output_chunk_name}.json"
                if chunk_file.exists():
                    with open(chunk_file, 'r', encoding='utf-8') as f:
                        output_chunk = json.load(f)
                    if output_chunk and 'meta' in output_chunk:
                        opt_inst = output_chunk['meta'].get('optimization_instruction')
                        if opt_inst:
                            logger.info(f"[LOAD-OPT] Found in JSON chunk '{output_chunk_name}' meta for '{output_config_name}' ({len(opt_inst)} chars)")
                            return opt_inst
    except Exception as e:
        logger.warning(f"[LOAD-OPT] Failed to load optimization_instruction for '{output_config_name}': {e}")

    logger.warning(f"[LOAD-OPT] No optimization_instruction found for '{output_config_name}'")
    return None


def _parse_triple_prompt(text: str) -> dict | None:
    """Parse CLIP-prompt JSON from optimization output.

    Accepts 2-key {clip_l, clip_g} or legacy 3-key {clip_l, clip_g, t5}.
    T5-XXL receives the user's interception result directly (not from optimization).
    Returns dict with at least clip_l + clip_g, or None if parsing fails.
    Strips markdown code fences and <think> blocks (reasoning model artifacts).
    Falls back to regex extraction if JSON isn't cleanly parseable.
    """
    import json
    import re
    if not text or not text.strip():
        return None
    cleaned = text.strip()
    # Strip <think>...</think> blocks (reasoning model artifacts)
    cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL).strip()
    # Strip markdown code fences
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        # Remove first line (```json or ```) and last line (```)
        if lines[-1].strip() == '```':
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        cleaned = '\n'.join(lines).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and 'clip_l' in data and 'clip_g' in data:
            logger.info(f"[CLIP-PROMPT] Parsed: CLIP-L={len(data['clip_l'].split())}w, "
                        f"CLIP-G={len(data['clip_g'].split())}w"
                        f"{', T5=' + str(len(data['t5'].split())) + 'w (legacy)' if 't5' in data else ''}")
            return data
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Regex fallback: extract {clip_l, clip_g} JSON from mixed text
    json_match = re.search(r'\{[^{}]*"clip_l"\s*:\s*"[^"]*"[^{}]*"clip_g"\s*:\s*"[^"]*"[^{}]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if 'clip_l' in data and 'clip_g' in data:
                logger.info(f"[CLIP-PROMPT] Extracted from mixed text via regex: "
                            f"CLIP-L={len(data['clip_l'].split())}w, CLIP-G={len(data['clip_g'].split())}w")
                return data
        except json.JSONDecodeError:
            pass

    return None


def _load_model_from_output_config(output_config_name: str) -> str | None:
    """Load LLM model override for Stage 3 optimization from output config.

    IMPORTANT: This loads the LLM for prompt optimization, NOT the media model.
    Uses meta.optimization_model field (preferred) or meta.model as fallback
    ONLY if it's a config.py variable reference.

    Field semantics:
    - meta.optimization_model: LLM for Stage 3 (e.g., "CODING_MODEL")
    - meta.media_model: The actual media generation model (e.g., "stable-audio-open-1.0")
    - meta.model: DEPRECATED for LLM override, kept for backward compatibility

    Returns:
        Model string (e.g., "mistral/codestral-2501"), "DEFAULT", or None if not found
    """
    try:
        if pipeline_executor is None:
            init_schema_engine()

        output_config_obj = pipeline_executor.config_loader.get_config(output_config_name)

        if output_config_obj and hasattr(output_config_obj, 'meta'):
            meta = output_config_obj.meta

            # 1. Check optimization_model first (new, preferred field)
            opt_model = meta.get('optimization_model')
            if opt_model:
                if opt_model == "DEFAULT":
                    logger.info(f"[LOAD-MODEL] Config '{output_config_name}' optimization_model=DEFAULT")
                    return "DEFAULT"

                # Resolve config variable if applicable
                if hasattr(config, opt_model):
                    resolved = getattr(config, opt_model)
                    logger.info(f"[LOAD-MODEL] Resolved optimization_model config.{opt_model} → {resolved}")
                    return resolved
                else:
                    # Direct model string (e.g., "local/codestral:latest")
                    logger.info(f"[LOAD-MODEL] Using optimization_model: {opt_model}")
                    return opt_model

            # 2. Fallback: Check model field ONLY if it's a config.py variable
            # This prevents media models (e.g., "stable-audio-open-1.0") from being used as LLM
            model_value = meta.get('model')
            if model_value:
                if model_value == "DEFAULT":
                    logger.info(f"[LOAD-MODEL] Config '{output_config_name}' model=DEFAULT")
                    return "DEFAULT"

                # ONLY use if it's a config.py variable (LLM reference)
                if hasattr(config, model_value):
                    resolved = getattr(config, model_value)
                    logger.info(f"[LOAD-MODEL] Resolved legacy model config.{model_value} → {resolved}")
                    return resolved
                else:
                    # NOT a config variable = media model, ignore for LLM selection
                    logger.debug(f"[LOAD-MODEL] Ignoring media model '{model_value}' (not a config variable)")

    except Exception as e:
        logger.warning(f"[LOAD-MODEL] Failed to load model: {e}")

    logger.info(f"[LOAD-MODEL] No optimization_model in config '{output_config_name}'")
    return None


def _load_estimated_duration(output_config_name: str) -> str:
    """Load estimated_duration_seconds from output chunk meta.

    Returns:
        String value like "20-60", "5-15", "0", or "30" (fallback)
    """
    try:
        # Ensure pipeline_executor is initialized
        if pipeline_executor is None:
            init_schema_engine()

        logger.info(f"[LOAD-DURATION] Loading estimated_duration_seconds for config '{output_config_name}'")

        output_config_obj = pipeline_executor.config_loader.get_config(output_config_name)

        if output_config_obj and hasattr(output_config_obj, 'parameters'):
            output_chunk_name = output_config_obj.parameters.get('OUTPUT_CHUNK')

            if output_chunk_name:
                import json
                from pathlib import Path
                chunks_dir = Path(__file__).parent.parent.parent / "schemas" / "chunks"

                # 1. Try Python chunk CHUNK_META first
                chunk_py = chunks_dir / f"{output_chunk_name}.py"
                if chunk_py.exists():
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(f"dur_{output_chunk_name}", chunk_py)
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        chunk_meta = getattr(mod, 'CHUNK_META', {})
                        duration = chunk_meta.get('estimated_duration_seconds')
                        if duration is not None:
                            logger.info(f"[LOAD-DURATION] Found in Python chunk: {duration}")
                            return str(duration)
                    except Exception as e:
                        logger.debug(f"[LOAD-DURATION] Failed to load Python chunk '{output_chunk_name}': {e}")

                # 2. Fallback to JSON chunk
                chunk_file = chunks_dir / f"{output_chunk_name}.json"
                if chunk_file.exists():
                    with open(chunk_file, 'r', encoding='utf-8') as f:
                        output_chunk = json.load(f)
                    if output_chunk and 'meta' in output_chunk:
                        duration = output_chunk['meta'].get('estimated_duration_seconds')
                        if duration is not None:
                            logger.info(f"[LOAD-DURATION] Found in JSON chunk: {duration}")
                            return str(duration)

        logger.warning(f"[LOAD-DURATION] No duration found for '{output_config_name}', using fallback")
        return "30"  # Fallback (default when optimization skipped)

    except Exception as e:
        logger.warning(f"[LOAD-DURATION] Failed to load duration: {e}")
        return "30"  # Fallback


def _build_stage2_result(interception_result: str, optimized_prompt: str, result1, optimization_instruction):
    """Build Stage2Result for backward compatibility."""
    from dataclasses import dataclass
    from typing import Optional
    from config import STAGE2_INTERCEPTION_MODEL

    @dataclass
    class Stage2Result:
        success: bool
        interception_result: str
        optimized_prompt: str
        final_output: str
        error: Optional[str] = None
        steps: list = None
        metadata: dict = None
        execution_time: float = 0.0

        def __post_init__(self):
            if self.steps is None:
                self.steps = []
            if self.metadata is None:
                self.metadata = {}

    optimization_model_name = STAGE2_INTERCEPTION_MODEL if optimization_instruction else None

    return Stage2Result(
        success=True,
        interception_result=interception_result,
        optimized_prompt=optimized_prompt,
        final_output=optimized_prompt,
        steps=result1.steps,
        metadata={
            'interception_model': result1.metadata.get('model_used') if result1.metadata else None,
            'optimization_model': optimization_model_name,
            'two_phase_execution': True,
            'optimization_applied': optimization_instruction is not None
        },
        execution_time=result1.execution_time
    )


# ============================================================================
# NEW STAGE 2 FUNCTIONS (SEPARATED)
# ============================================================================

async def execute_optimization(
    input_text: str,
    optimization_instruction: str,
):
    """
    Optimization: Transform text using manipulate chunk + optimization_instruction

    Uses Prompt Interception through manipulate chunk:
    - TASK_INSTRUCTION = Generic transformation instruction
    - CONTEXT = optimization_instruction from output chunk (USER_RULES)
    - INPUT_TEXT = text to optimize

    Args:
        input_text: Text to optimize (typically interception_result)
        optimization_instruction: Specific transformation rules from output chunk

    Returns:
        Optimized text, or input_text on failure
    """
    logger.info(f"[OPTIMIZATION] Starting with instruction length: {len(optimization_instruction)}")
    logger.info(f"[OPTIMIZATION] Input text: '{input_text[:200]}...'")
    logger.info(f"[OPTIMIZATION] Using manipulate chunk with optimization_instruction as CONTEXT")

    # TODO [ARCHITECTURE VIOLATION]: This bypasses ChunkBuilder pipeline.
    # Should use: ChunkBuilder.build_chunk("manipulate", config, input_text)
    # Then: BackendRouter.route(chunk)
    # See: docs/ARCHITECTURE_VIOLATION_PromptInterceptionEngine.md
    from schemas.engine.prompt_interception_engine import (
        PromptInterceptionEngine,
        PromptInterceptionRequest
    )
    from config import STAGE2_INTERCEPTION_MODEL

    # Initialize PromptInterceptionEngine
    interception_engine = PromptInterceptionEngine()

    # Session 134 FIX: Correct field assignment
    # - task_instruction: HOW to transform (meta-instruction)
    # - style_prompt: WHAT rules to follow (style-specific)
    request = PromptInterceptionRequest(
        input_prompt=input_text,
        input_context='',
        style_prompt=optimization_instruction,  # Style-specific rules
        task_instruction=get_instruction("prompt_optimization"),  # Meta-instruction
        model=STAGE2_INTERCEPTION_MODEL,
        debug=False,
        parameters={"enable_thinking": False}  # Structured JSON output, no reasoning
    )

    try:
        # Execute Prompt Interception with the manipulate chunk
        response = await interception_engine.process_request(request)

        if response.success and response.output_str and response.output_str.strip():
            logger.info(f"[OPTIMIZATION] Completed via manipulate chunk: '{response.output_str[:100]}...'")
            return response.output_str
        else:
            logger.warning(f"[OPTIMIZATION] Failed or empty result: {response.error if hasattr(response, 'error') else 'Unknown'}")
            return input_text  # Fallback to input

    except Exception as e:
        logger.error(f"[OPTIMIZATION] Error in manipulate chunk execution: {e}")
        import traceback
        traceback.print_exc()
        return input_text  # Fallback to input


async def execute_stage2_interception(
    schema_name: str,
    input_text: str,
    config,
    safety_level: str,
    tracker=None,
    user_input: str = None
):
    """
    Stage 2 Interception: Pedagogical transformation using config.context

    Completely independent from optimization.
    Wikipedia research is controlled by config meta ("wikipedia": true), not by request parameters.

    Args:
        schema_name: Name of the interception config (e.g., "dada", "bauhaus")
        input_text: User input text (already safety-checked in Stage 1)
        config: Loaded interception config object
        safety_level: "kids", "youth", "adult", or "research"
        tracker: Optional execution tracker
        user_input: Optional original user input text (before safety check)

    Returns:
        Pipeline execution result with interception_result in final_output
    """
    logger.info(f"[STAGE2-INTERCEPTION] Starting for '{schema_name}'")

    if tracker is None:
        tracker = NoOpTracker()

    result = await pipeline_executor.execute_pipeline(
        config_name=schema_name,
        input_text=input_text,
        user_input=user_input if user_input is not None else input_text,
        safety_level=safety_level,
        tracker=tracker,
        config_override=config
    )

    # Extract LoRAs from interception config (Session 116: Config-based LoRA injection)
    config_loras = config.meta.get('loras', []) if hasattr(config, 'meta') and config.meta else []
    if config_loras:
        logger.info(f"[STAGE2-LORA] Extracted {len(config_loras)} LoRA(s) from config '{schema_name}': {[l['name'] for l in config_loras]}")
        if not result.metadata:
            result.metadata = {}
        result.metadata['loras'] = config_loras

    if result.success:
        logger.info(f"[STAGE2-INTERCEPTION] Completed: '{result.final_output[:100]}...'")
    else:
        logger.error(f"[STAGE2-INTERCEPTION] Failed: {result.error}")

    return result


# ============================================================================
# SHARED STAGE 2 EXECUTION FUNCTION
# ============================================================================

async def execute_stage2_with_optimization_SINGLE_RUN_VERSION(
    schema_name: str,
    input_text: str,
    config,
    safety_level: str,
    output_config: str = None,
    media_preferences = None,
    tracker = None,
    user_input: str = None
):
    """
    BACKUP VERSION: Execute Stage 2 with SINGLE LLM call (interception + optimization combined)

    This is the OLD implementation that combines pedagogical interception and model-specific
    optimization in ONE LLM call. Kept as backup for potential future use.

    REPLACED BY: execute_stage2_with_optimization() which does 2 separate LLM calls.

    Args:
        schema_name: Name of the interception config (e.g., "dada", "bauhaus")
        input_text: User input text (already safety-checked in Stage 1)
        config: Loaded interception config object
        safety_level: "kids", "youth", "adult", or "research"
        output_config: Optional output config name for optimization (e.g., "sd35_large")
        media_preferences: Optional media preferences from config
        tracker: Optional execution tracker
        user_input: Optional original user input text (before safety check)

    Returns:
        PipelineResult object with Stage 2 output
    """
    from dataclasses import replace

    logger.info(f"[STAGE2] Starting interception for '{schema_name}'")

    # ====================================================================
    # STAGE 2 OPTIMIZATION: Fetch media-specific optimization instruction
    # ====================================================================
    optimization_instruction = None

    # Determine which output config will be used
    if output_config:
        # User-selected or explicitly provided
        target_output_config = output_config
    elif media_preferences and media_preferences.get('output_configs'):
        # Use first output config from array
        target_output_config = media_preferences['output_configs'][0]
    elif media_preferences and media_preferences.get('default_output') and media_preferences.get('default_output') != 'text':
        # Lookup output config from default_output
        target_output_config = lookup_output_config(media_preferences['default_output'])
    else:
        target_output_config = None

    if target_output_config:
        logger.info(f"[STAGE2-OPT] Target output config: {target_output_config}")
        try:
            optimization_instruction = _load_optimization_instruction(target_output_config)
        except Exception as e:
            logger.warning(f"[STAGE2-OPT] Failed to load optimization instruction: {e}")

    # ====================================================================
    # Append optimization instruction to context if found
    # ====================================================================
    stage2_config = config
    if optimization_instruction:
        logger.info(f"[STAGE2-OPT] Appending optimization instruction to pipeline context")

        # Get original context (resolve i18n dict to string)
        from schemas.engine.config_loader import resolve_context_language
        original_context = resolve_context_language(config.context) if hasattr(config, 'context') else ""
        new_context = original_context + "\n\n" + optimization_instruction

        # Create modified config using dataclasses.replace()
        stage2_config = replace(
            config,
            context=new_context,
            meta={**config.meta, 'optimization_added': True}
        )
        logger.info(f"[STAGE2-OPT] Context extended with optimization instruction")

    # ====================================================================
    # Execute Stage 2 Pipeline
    # ====================================================================
    if tracker is None:
        # Use locally-defined NoOpTracker class (defined at top of file)
        tracker = NoOpTracker()

    result = await pipeline_executor.execute_pipeline(
        config_name=schema_name,
        input_text=input_text,
        user_input=user_input if user_input is not None else input_text,
        safety_level=safety_level,
        tracker=tracker,
        config_override=stage2_config
    )

    logger.info(f"[STAGE2] Interception completed: {result.success}")
    return result


async def execute_stage2_with_optimization(
    schema_name: str,
    input_text: str,
    config,
    safety_level: str,
    output_config: str = None,
    media_preferences = None,
    tracker = None,
    user_input: str = None
):
    """
    DEPRECATED: Use execute_stage2_interception() and execute_optimization() separately.

    This proxy remains for backward compatibility only.
    Calls the two new separated functions internally.

    Args:
        schema_name: Name of the interception config (e.g., "dada", "bauhaus")
        input_text: User input text (already safety-checked in Stage 1)
        config: Loaded interception config object
        safety_level: "kids", "youth", "adult", or "research"
        output_config: Optional output config name for optimization (e.g., "sd35_large")
        media_preferences: Optional media preferences from config
        tracker: Optional execution tracker
        user_input: Optional original user input text (before safety check)

    Returns:
        Dict with both interception_result and optimized_prompt (if optimization was run)
    """
    import warnings
    warnings.warn(
        "execute_stage2_with_optimization() is deprecated. "
        "Use execute_stage2_interception() and execute_optimization() separately.",
        DeprecationWarning,
        stacklevel=2
    )

    # Step 1: Interception
    result1 = await execute_stage2_interception(
        schema_name=schema_name,
        input_text=input_text,
        config=config,
        safety_level=safety_level,
        tracker=tracker,
        user_input=user_input
    )

    if not result1.success:
        return result1

    interception_result = result1.final_output

    # Step 2: Get optimization_instruction (if output config specified)
    optimization_instruction = None
    target_output_config = output_config

    if not target_output_config and media_preferences:
        if media_preferences.get('output_configs'):
            target_output_config = media_preferences['output_configs'][0]
        elif media_preferences.get('default_output') and media_preferences.get('default_output') != 'text':
            target_output_config = lookup_output_config(media_preferences['default_output'])

    if target_output_config:
        optimization_instruction = _load_optimization_instruction(target_output_config)

    # Step 3: Optimization (if instruction found)
    if optimization_instruction:
        optimized_prompt = await execute_optimization(
            input_text=interception_result,
            optimization_instruction=optimization_instruction,
        )
    else:
        optimized_prompt = interception_result

    # Return combined result (for backward compatibility)
    return _build_stage2_result(
        interception_result=interception_result,
        optimized_prompt=optimized_prompt,
        result1=result1,
        optimization_instruction=optimization_instruction
    )


@schema_bp.route('/info', methods=['GET'])
def get_schema_info():
    """Schema-System Informationen"""
    try:
        init_schema_engine()

        available_schemas = pipeline_executor.get_available_schemas()

        return jsonify({
            'status': 'success',
            'schemas_available': len(available_schemas),
            'schemas': available_schemas,
            'engine_status': 'initialized'
        })

    except Exception as e:
        logger.error(f"Schema-Info Fehler: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# ============================================================================
# NEW REFACTORED ENDPOINTS - CLEAN STAGE SEPARATION
# ============================================================================

@schema_bp.route('/pipeline/stage2', methods=['POST'])
def execute_stage2():
    """
    Execute ONLY Stage 2: Interception + Optimization

    This endpoint executes Stage 2 (prompt interception with media-specific optimization)
    and returns the result for frontend preview/editing.

    Frontend can then call /pipeline/stage3-4 with the (possibly edited) Stage 2 result.

    Request Body:
    {
        "schema": "dada",                      # Interception config
        "input_text": "Ein roter Apfel",       # User input
        "output_config": "sd35_large",         # Output config for optimization
        "safety_level": "kids",                # kids, youth, or off
        "user_language": "de"                  # User's interface language
    }

    Response:
    {
        "success": true,
        "stage2_result": "Ein roter Apfel in fragmentierter dadaistischer Form...",
        "run_id": "uuid",                      # Session ID for Stage 3-4
        "model_used": "llama3:8b",
        "backend_type": "ollama",
        "execution_time_ms": 1234
    }
    """
    import time
    import uuid

    start_time = time.time()

    try:
        # Request validation
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'JSON-Request erwartet'
            }), 400

        from config import DEFAULT_SAFETY_LEVEL as _default_safety

        schema_name = data.get('schema')
        input_text = data.get('input_text')
        safety_level = _default_safety
        output_config = data.get('output_config')  # Optional
        user_language = data.get('user_language', 'en')

        # CRITICAL: Check if frontend provides interception_result
        # If provided, Stage 2 was already executed - DO NOT run Call 1 again!
        frontend_interception_result = data.get('interception_result')  # Optional: already executed

        # Context editing support (same as /execute)
        context_prompt = data.get('context_prompt')  # Optional: user-edited meta-prompt
        context_language = data.get('context_language', 'en')  # Language of context_prompt

        if not schema_name or not input_text:
            return jsonify({
                'success': False,
                'error': 'schema und input_text sind erforderlich'
            }), 400

        # Initialize engine
        init_schema_engine()

        # Load config (note: 'config' here is a schema config, not the config module)
        config = pipeline_executor.config_loader.get_config(schema_name)
        if not config:
            return jsonify({
                'success': False,
                'error': f'Config "{schema_name}" nicht gefunden'
            }), 404

        logger.info(f"[STAGE2-ENDPOINT] Starting Stage 2 for schema '{schema_name}'")

        # ====================================================================
        # CONTEXT EDITING SUPPORT (same pattern as /execute)
        # ====================================================================
        execution_config = config
        if context_prompt:
            logger.info(f"[STAGE2-ENDPOINT] User edited context in language: {context_language}")

            # Translate to English if needed
            context_prompt_en = context_prompt
            if context_language != 'en':
                logger.info(f"[STAGE2-ENDPOINT] Translating context from {context_language} to English")

                from my_app.services.llm_backend import get_llm_backend
                from config import STAGE3_MODEL
                translation_prompt = f"Translate this educational text from {context_language} to English. Preserve pedagogical intent and technical terminology:\n\n{context_prompt}"

                try:
                    model = STAGE3_MODEL.replace("local/", "") if STAGE3_MODEL.startswith("local/") else STAGE3_MODEL
                    result = get_llm_backend().generate(model=model, prompt=translation_prompt)
                    translated = result.get("response", "").strip() if result else ""
                    if not translated:
                        logger.error("[STAGE2-ENDPOINT] Context translation failed, using original")
                        context_prompt_en = context_prompt
                    else:
                        context_prompt_en = translated
                        logger.info(f"[STAGE2-ENDPOINT] Context translated successfully")
                except Exception as e:
                    logger.error(f"[STAGE2-ENDPOINT] Context translation error: {e}")
                    context_prompt_en = context_prompt

            # Create modified config with user-edited context
            logger.info(f"[STAGE2-ENDPOINT] Creating modified config with user-edited context")

            from dataclasses import replace
            execution_config = replace(
                config,
                context=context_prompt_en,  # Use English version for pipeline
                meta={
                    **config.meta,
                    'user_edited': True,
                    'original_config': schema_name,
                    'user_language': user_language
                }
            )

        # ====================================================================
        # STAGE 1: PRE-INTERCEPTION (Safety Check)
        # ====================================================================
        logger.info(f"[STAGE2-ENDPOINT] Stage 1: Safety Check")

        stage1_start = time.time()
        
        # OLLAMA QUEUE: Wrap Stage 1 execution
        logger.info(f"[OLLAMA-QUEUE] Stage 2 Endpoint: Waiting for queue slot...")
        with ollama_queue_semaphore:
            logger.info(f"[OLLAMA-QUEUE] Stage 2 Endpoint: Acquired slot, executing Stage 1")
            is_safe, checked_text, error_message, checks_passed = asyncio.run(execute_stage1_safety_unified(
                input_text,
                safety_level,
                pipeline_executor,
                user_language=user_language
            ))
        logger.info(f"[OLLAMA-QUEUE] Stage 2 Endpoint: Released slot")

        stage1_time = (time.time() - stage1_start) * 1000  # ms

        if not is_safe:
            logger.warning(f"[STAGE2-ENDPOINT] Stage 1 BLOCKED by safety check")
            return jsonify({
                'success': False,
                'error': error_message,
                'blocked_at_stage': 1,
                'safety_level': safety_level,
                'checks_passed': checks_passed
            }), 403

        logger.info(f"[STAGE2-ENDPOINT] Stage 1 completed: Safety passed")

        # ====================================================================
        # STAGE 2: INTERCEPTION + OPTIMIZATION (Shared Function)
        # ====================================================================
        stage2_start = time.time()

        # Check if pipeline has skip_stage2 flag (graceful check)
        pipeline_def = pipeline_executor.config_loader.get_pipeline(execution_config.pipeline_name)
        skip_stage2 = pipeline_def.skip_stage2 if pipeline_def and hasattr(pipeline_def, 'skip_stage2') else False

        if skip_stage2:
            logger.info(f"[STAGE2-ENDPOINT] Stage 2: SKIPPED (pipeline '{execution_config.pipeline_name}' has skip_stage2=true)")
            logger.info(f"[STAGE2-ENDPOINT] Stage 2: Passing Stage 1 output directly")

            # Create mock result - Stage 1 output passed through unchanged
            class MockResult:
                def __init__(self, output):
                    self.success = True
                    self.final_output = output
                    self.error = None
                    self.steps = []
                    self.metadata = {'stage2_skipped': True, 'pipeline': execution_config.pipeline_name}
                    self.execution_time = 0

            result = MockResult(checked_text)
        else:
            media_preferences = execution_config.media_preferences if hasattr(execution_config, 'media_preferences') else None

            result = asyncio.run(execute_stage2_with_optimization(
                schema_name=schema_name,
                input_text=checked_text,
                config=execution_config,  # Use execution_config (may be modified with user context)
                safety_level=safety_level,
                output_config=output_config,
                media_preferences=media_preferences,
                tracker=None
            ))

        stage2_time = (time.time() - stage2_start) * 1000  # ms

        if not result.success:
            logger.error(f"[STAGE2-ENDPOINT] Stage 2 failed: {result.error}")
            return jsonify({
                'success': False,
                'error': result.error,
                'execution_time_ms': stage2_time
            }), 500

        # Extract metadata
        model_used = None
        backend_type = None
        if result.steps and len(result.steps) > 0:
            for step in reversed(result.steps):
                if step.metadata:
                    model_used = step.metadata.get('model_used', model_used)
                    backend_type = step.metadata.get('backend_type', backend_type)
                    if model_used and backend_type:
                        break

        # Generate session ID for Stage 3-4 continuation
        run_id = generate_run_id()

        total_time = (time.time() - start_time) * 1000

        logger.info(f"[STAGE2-ENDPOINT] ✅ Success! Stage 2 result: '{result.final_output[:100]}...'")

        # Build response - include both prompts if 2-phase execution
        response_data = {
            'success': True,
            'stage2_result': result.final_output,
            'run_id': run_id,
            'model_used': model_used,
            'backend_type': backend_type,
            'execution_time_ms': total_time,
            'stage1_time_ms': stage1_time,
            'stage2_time_ms': stage2_time
        }

        # Add both prompts if using new 2-phase implementation
        if hasattr(result, 'interception_result') and hasattr(result, 'optimized_prompt'):
            response_data['interception_result'] = result.interception_result
            response_data['optimized_prompt'] = result.optimized_prompt
            response_data['two_phase_execution'] = True
            response_data['optimization_applied'] = result.metadata.get('optimization_applied', False) if result.metadata else False
            logger.info(f"[STAGE2-ENDPOINT] 2-phase execution: interception + optimization")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"[STAGE2-ENDPOINT] Error: {e}")
        import traceback
        traceback.print_exc()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schema_bp.route('/pipeline/optimize/meta/<output_config>', methods=['GET'])
def get_optimization_meta(output_config: str):
    """
    Get optimization metadata for streaming

    Returns optimization_instruction and estimated_duration_seconds
    for the specified output config (used by frontend before streaming)

    Response:
    {
        "success": true,
        "optimization_instruction": "...",
        "estimated_duration_seconds": "30"
    }
    """
    try:
        logger.info(f"[OPTIMIZE-META] Getting metadata for '{output_config}'")

        # Load optimization_instruction
        optimization_instruction = _load_optimization_instruction(output_config)

        # Load estimated_duration_seconds
        estimated_duration = _load_estimated_duration(output_config)

        return jsonify({
            'success': True,
            'optimization_instruction': optimization_instruction or '',
            'estimated_duration_seconds': estimated_duration
        })

    except Exception as e:
        logger.error(f"[OPTIMIZE-META] Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schema_bp.route('/pipeline/optimize', methods=['POST'])
def optimize_prompt():
    """
    ONLY Call 2: Optimization with optimization_instruction from output chunk

    This endpoint applies media-specific optimization to already-intercepted prompts.
    Used when user selects a model AFTER interception.

    Request Body:
    {
        "input_text": "...",           # Text from interception_result box
        "output_config": "sd35_large"  # Selected model/output config
    }

    Response:
    {
        "success": true,
        "optimized_prompt": "...",
        "optimization_applied": true/false
    }
    """
    import time

    start_time = time.time()

    try:
        # Request validation
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'JSON-Request erwartet'
            }), 400

        input_text = data.get('input_text')
        output_config = data.get('output_config')

        if not input_text or not output_config:
            return jsonify({
                'success': False,
                'error': 'input_text und output_config sind erforderlich'
            }), 400

        logger.info(f"[OPTIMIZE-ENDPOINT] Starting optimization for output_config '{output_config}'")

        # Load optimization_instruction from output chunk
        optimization_instruction = _load_optimization_instruction(output_config)

        logger.info(f"[OPTIMIZE-ENDPOINT] Loaded optimization_instruction: {optimization_instruction[:200] if optimization_instruction else 'NONE'}...")

        if not optimization_instruction:
            # No optimization available - return input unchanged
            logger.info(f"[OPTIMIZE-ENDPOINT] No optimization_instruction found for '{output_config}' - returning input unchanged")
            # Load duration even when no optimization
            estimated_duration = _load_estimated_duration(output_config)
            return jsonify({
                'success': True,
                'optimized_prompt': input_text,
                'optimization_applied': False,
                'estimated_duration_seconds': estimated_duration,
                'execution_time_ms': int((time.time() - start_time) * 1000)
            })

        # Call execute_optimization() - only Call 2, NO Call 1
        logger.info(f"[OPTIMIZE-ENDPOINT] Applying optimization (instruction length: {len(optimization_instruction)})")

        optimized = asyncio.run(execute_optimization(
            input_text=input_text,
            optimization_instruction=optimization_instruction,
        ))

        execution_time = int((time.time() - start_time) * 1000)

        logger.info(f"[OPTIMIZE-ENDPOINT] Optimization complete ({execution_time}ms)")

        # Load estimated_duration_seconds using same pattern as optimization_instruction
        estimated_duration = _load_estimated_duration(output_config)

        # Check for CLIP-prompt JSON (SD3.5 per-encoder optimization)
        triple = _parse_triple_prompt(optimized)
        response_data = {
            'success': True,
            'optimized_prompt': optimized,
            'optimization_applied': True,
            'estimated_duration_seconds': estimated_duration,
            'execution_time_ms': execution_time
        }
        if triple:
            response_data['triple_prompt'] = triple
            response_data['interception_result'] = input_text  # User's text for T5 (frontend can forward to stage3-4)
            logger.info(f"[OPTIMIZE-ENDPOINT] CLIP-prompt detected, included interception_result for T5")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"[OPTIMIZE-ENDPOINT] Error: {e}")
        import traceback
        traceback.print_exc()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schema_bp.route('/pipeline/stage3-4', methods=['POST'])
def execute_stage3_4():
    """
    Execute Stage 3-4: Translation + Safety + Media Generation

    Takes the Stage 2 result (possibly edited by user) and continues with
    translation, safety check, and media generation.

    Request Body:
    {
        "stage2_result": "Ein roter Apfel in dadaistischer...",  # From /stage2 (can be edited)
        "output_config": "sd35_large",                           # Output config for media generation
        "safety_level": "kids",                                  # kids, youth, or off
        "run_id": "uuid",                                        # Optional: Session ID from /stage2
        "seed": 123456                                           # Optional: Seed for reproducible generation
    }

    Response:
    {
        "success": true,
        "media_output": {
            "url": "/media/run_xyz/image.png",
            "media_type": "image",
            "seed": 123456,
            ...
        },
        "stage3_result": "A red apple in fragmented dadaist form...",  # Translated text
        "execution_time_ms": 5678
    }
    """
    import time
    import uuid

    start_time = time.time()

    try:
        # Request validation
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'JSON-Request erwartet'
            }), 400

        stage2_result = data.get('stage2_result')
        output_config = data.get('output_config')
        safety_level = config.DEFAULT_SAFETY_LEVEL
        run_id = data.get('run_id', generate_run_id())
        seed_override = data.get('seed')
        interception_result_param = data.get('interception_result')  # Optional: user's original interception text for T5

        if not stage2_result or not output_config:
            return jsonify({
                'success': False,
                'error': 'stage2_result und output_config sind erforderlich'
            }), 400

        # Initialize engine
        init_schema_engine()

        # Get recorder for media storage
        from config import JSON_STORAGE_DIR
        recorder = get_recorder(
            run_id=run_id,
            config_name=output_config,
            safety_level=safety_level,
            base_path=JSON_STORAGE_DIR
        )

        logger.info(f"[STAGE3-4-ENDPOINT] Starting Stage 3-4 for output config '{output_config}'")
        logger.info(f"[STAGE3-4-ENDPOINT] Stage 2 result (first 100 chars): {stage2_result[:100]}...")

        # ====================================================================
        # PHASE 4: INTELLIGENT SEED LOGIC
        # ====================================================================
        # Decision happens BEFORE Stage 3 translation, based on Stage 2 result
        global _last_prompt, _last_seed, _last_output_config
        import random

        if stage2_result != _last_prompt or output_config != _last_output_config:
            # Prompt OR model changed → keep same seed (compare effect of change)
            if _last_seed is not None:
                calculated_seed = _last_seed
                logger.info(f"[PHASE4-SEED] Prompt or model CHANGED → reusing seed {calculated_seed}")
            else:
                calculated_seed = 123456789
                logger.info(f"[PHASE4-SEED] First run → using standard seed {calculated_seed}")
        else:
            # Prompt AND model unchanged → new random seed (user wants variation)
            calculated_seed = random.randint(0, 2147483647)
            logger.info(f"[PHASE4-SEED] Prompt+model UNCHANGED (re-run) → new random seed {calculated_seed}")

        # Update global state AFTER decision
        _last_prompt = stage2_result
        _last_seed = calculated_seed
        _last_output_config = output_config

        # Override with user-provided seed if specified
        if seed_override is not None:
            calculated_seed = seed_override
            logger.info(f"[PHASE4-SEED] User override → using seed {calculated_seed}")

        # ====================================================================
        # STAGE 3: TRANSLATION + PRE-OUTPUT SAFETY
        # ====================================================================
        logger.info(f"[STAGE3-4-ENDPOINT] Stage 3: Translation + Pre-Output Safety")

        stage3_start = time.time()

        # Determine media type from output config
        if 'image' in output_config.lower() or 'sd' in output_config.lower() or 'flux' in output_config.lower() or 'gpt' in output_config.lower():
            media_type = 'image'
        elif 'audio' in output_config.lower() or 'music' in output_config.lower() or 'ace' in output_config.lower():
            media_type = 'audio'
        elif 'video' in output_config.lower():
            media_type = 'video'
        elif '3d' in output_config.lower():
            media_type = '3d'
        else:
            media_type = 'image'  # Default fallback

        # CLIP-prompt detection from stage2_result
        triple_prompt = _parse_triple_prompt(stage2_result)
        if triple_prompt:
            # T5 uses the user's interception result, not the optimized CLIP prompts
            interception_text = interception_result_param or triple_prompt.get('clip_g', stage2_result)
            prompt_for_safety = interception_text
            logger.info(f"[STAGE3-4-ENDPOINT] CLIP-prompt detected, safety-checking interception result ({len(interception_text.split())}w)")
        else:
            prompt_for_safety = stage2_result

        # Execute Stage 3 safety check
        safety_result = asyncio.run(execute_stage3_safety(
            prompt_for_safety,
            safety_level,
            media_type,
            pipeline_executor,
            user_language=user_language
        ))

        stage3_time = (time.time() - stage3_start) * 1000  # ms

        if not safety_result['safe']:
            logger.warning(f"[STAGE3-4-ENDPOINT] Stage 3 BLOCKED by safety check")
            return jsonify({
                'success': False,
                'error': safety_result.get('reason', 'Content blocked by safety check'),
                'blocked_at_stage': 3,
                'safety_level': safety_level,
                'stage3_time_ms': stage3_time
            }), 403

        translated_prompt = safety_result.get('positive_prompt', prompt_for_safety)
        logger.info(f"[STAGE3-4-ENDPOINT] Stage 3 completed: Translated to '{translated_prompt[:100]}...'")

        # ====================================================================
        # STAGE 4: MEDIA GENERATION
        # ====================================================================
        logger.info(f"[STAGE3-4-ENDPOINT] Stage 4: Executing output config '{output_config}'")

        stage4_start = time.time()

        try:
            # Execute Output Pipeline with translated text
            # Use locally-defined NoOpTracker class (defined at top of file)
            tracker = NoOpTracker()

            # CLIP-prompt: set up per-encoder prompts for SD3.5
            context_override = None
            if triple_prompt:
                from schemas.engine.pipeline_executor import PipelineContext
                # CLIP-L/G from optimization, T5 = translated user's interception text
                media_prompt = triple_prompt['clip_l']
                context_override = PipelineContext(
                    input_text=media_prompt,
                    user_input=media_prompt
                )
                context_override.custom_placeholders = {
                    'prompt_2': triple_prompt['clip_g'],
                    'prompt_3': translated_prompt  # User's interception text, translated by Stage 3
                }
                logger.info(f"[CLIP-PROMPT] CLIP-L={len(media_prompt.split())}w, "
                            f"CLIP-G={len(triple_prompt['clip_g'].split())}w, T5={len(translated_prompt.split())}w (user text)")
            else:
                media_prompt = translated_prompt

            output_result = asyncio.run(pipeline_executor.execute_pipeline(
                config_name=output_config,
                input_text=media_prompt,
                user_input=media_prompt,
                tracker=tracker,
                seed_override=calculated_seed,
                context_override=context_override
            ))

            stage4_time = (time.time() - stage4_start) * 1000  # ms

            if not output_result.success:
                logger.error(f"[STAGE3-4-ENDPOINT] Stage 4 failed: {output_result.error}")
                return jsonify({
                    'success': False,
                    'error': output_result.error,
                    'stage': 'stage4',
                    'stage3_time_ms': stage3_time,
                    'stage4_time_ms': stage4_time
                }), 500

            # ====================================================================
            # MEDIA STORAGE - Download and store media locally
            # ====================================================================
            media_stored = False
            media_output_data = None

            try:
                output_value = output_result.final_output
                saved_filename = None

                # Extract seed from output_result metadata (if available)
                seed = output_result.metadata.get('seed') if output_result.metadata else None
                if seed_override is not None:
                    seed = seed_override

                # Detect generation backend and save media appropriately
                if not output_value.startswith(('http://', 'https://', 'data:')) and len(output_value) > 1000 and output_value[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/':
                    # Pure base64 string (OpenAI Images API format)
                    logger.info(f"[STAGE3-4-ENDPOINT] Decoding pure base64 string ({len(output_value)} chars)")
                    try:
                        import base64

                        # Decode base64 directly
                        image_bytes = base64.b64decode(output_value)

                        # Default to PNG format for Images API
                        image_format = 'png'

                        # Save using recorder
                        saved_filename = recorder.save_entity(
                            entity_type=f'output_{media_type}',
                            content=image_bytes,
                            metadata={
                                'config': output_config,
                                'backend': 'api',
                                'provider': 'openai',
                                'seed': seed,
                                'format': image_format,
                                'source': 'images_api_base64'
                            }
                        )
                        media_stored = True
                        logger.info(f"[STAGE3-4-ENDPOINT] Saved {media_type} from pure base64: {saved_filename}")
                    except Exception as e:
                        logger.error(f"[STAGE3-4-ENDPOINT] Failed to decode pure base64: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    logger.warning(f"[STAGE3-4-ENDPOINT] Unsupported output format for media storage (not pure base64, not HTTP URL)")

                if media_stored and saved_filename:
                    media_output_data = {
                        'url': f'/api/media/{run_id}/{saved_filename}',
                        'filename': saved_filename,
                        'run_id': run_id,
                        'media_type': media_type,
                        'config': output_config,
                        'seed': seed,
                        'media_stored': True
                    }
                    logger.info(f"[STAGE3-4-ENDPOINT] ✅ Media stored: {saved_filename}")

            except Exception as e:
                logger.error(f"[STAGE3-4-ENDPOINT] Media storage failed: {e}")
                import traceback
                traceback.print_exc()

            total_time = (time.time() - start_time) * 1000

            logger.info(f"[STAGE3-4-ENDPOINT] ✅ Success! Total time: {total_time:.0f}ms")

            return jsonify({
                'success': True,
                'media_output': media_output_data,
                'stage3_result': translated_prompt,
                'run_id': run_id,
                'execution_time_ms': total_time,
                'stage3_time_ms': stage3_time,
                'stage4_time_ms': stage4_time
            })

        except Exception as e:
            logger.error(f"[STAGE3-4-ENDPOINT] Stage 4 error: {e}")
            import traceback
            traceback.print_exc()

            return jsonify({
                'success': False,
                'error': str(e),
                'stage': 'stage4'
            }), 500

    except Exception as e:
        logger.error(f"[STAGE3-4-ENDPOINT] Error: {e}")
        import traceback
        traceback.print_exc()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



def execute_pipeline_streaming(data: dict):
    """
    Execute pipeline with SSE streaming
    Architecture: DevServer = Smart Orchestrator | Frontend = Dumb Display

    Stages:
        Stage 1: Safety Check — handled autonomously by MediaInputBox via /safety/quick
        Stage 2: Interception (streaming, character-by-character)
    """
    import time
    import os
    import requests
    from config import OLLAMA_API_BASE_URL, STAGE2_INTERCEPTION_MODEL, DEFAULT_INTERCEPTION_CONFIG, DEFAULT_SAFETY_LEVEL

    # Extract parameters
    schema_name = data.get('schema', DEFAULT_INTERCEPTION_CONFIG)
    input_text = data.get('input_text', '')
    context_prompt = data.get('context_prompt', '')
    safety_level = DEFAULT_SAFETY_LEVEL
    user_language = data.get('user_language', 'de')
    device_id = data.get('device_id')  # Session 129: For folder structure

    # Session 130: Simplified - always use run_xxx from the start
    run_id = generate_run_id()

    logger.info(f"[UNIFIED-STREAMING] Starting orchestrated pipeline for run {run_id}")
    logger.info(f"[UNIFIED-STREAMING] Schema: {schema_name}, Safety: {safety_level}, Device: {device_id}")

    # Initialize recorder for export functionality
    from config import JSON_STORAGE_DIR, STAGE2_INTERCEPTION_MODEL
    recorder = get_recorder(
        run_id=run_id,
        config_name=schema_name,
        safety_level=safety_level,
        device_id=device_id,  # Session 129
        base_path=JSON_STORAGE_DIR
    )

    # Track LLM models used at each stage
    recorder.metadata['models_used'] = {
        'stage2_interception': STAGE2_INTERCEPTION_MODEL
    }
    recorder._save_metadata()

    # Session 129: Save to prompting_process/ subfolder (research data)
    recorder.save_to_prompting_process('input', input_text)
    if context_prompt:
        recorder.save_to_prompting_process('context_prompt', context_prompt)

    try:
        # Initialize schema engine
        if pipeline_executor is None:
            init_schema_engine()

        # Send initial connection event
        yield generate_sse_event('connected', {
            'run_id': run_id,
            'schema': schema_name,
            'stages': 1
        })
        yield ''  # Force flush

        # ====================================================================
        # STAGE 1: SERVER-SIDE SAFETY GATE (fast-filters, no LLM)
        # ====================================================================
        # SAFETY-QUICK runs on blur/paste in the frontend, but is NOT guaranteed
        # (e.g. page refresh, cached text, Enter without blur). This server-side
        # check is the authoritative safety gate — it MUST run before Stage 2.
        if safety_level != 'research':
            # §86a fast-filter (language-aware)
            has_86a, found_86a = fast_filter_bilingual_86a(input_text, user_language)
            if has_86a:
                logger.warning(f"[UNIFIED-STREAMING] §86a BLOCKED: {found_86a[:3]}")
                yield generate_sse_event('blocked', {
                    'stage': 'safety',
                    'reason': f'§86a StGB: {", ".join(found_86a[:3])}'
                })
                yield ''
                return

            # DSGVO NER check — runs BEFORE age filter to ensure no personal data
            # leaves local system. This allows age filter to use external LLMs safely.
            has_pii, found_pii, spacy_ok = fast_dsgvo_check(input_text)
            if spacy_ok and has_pii:
                verify_result = llm_verify_person_name(input_text, found_pii)
                if verify_result is None:
                    safety_breaker.record_failure()
                    if safety_breaker.is_open():
                        reason = 'DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte Ollama neustarten: sudo systemctl restart ollama'
                        logger.warning(f"[UNIFIED-STREAMING] {reason}")
                        yield generate_sse_event('blocked', {'stage': 'safety', 'reason': reason})
                        yield ''
                        return
                    logger.warning(f"[UNIFIED-STREAMING] DSGVO LLM unavailable — circuit breaker recording failure")
                elif verify_result:
                    safety_breaker.record_success()
                    reason = f'DSGVO: {", ".join(found_pii[:3])}'
                    logger.warning(f"[UNIFIED-STREAMING] DSGVO BLOCKED: {reason}")
                    yield generate_sse_event('blocked', {
                        'stage': 'safety',
                        'reason': reason
                    })
                    yield ''
                    return
                else:
                    safety_breaker.record_success()

            # Age-appropriate fast-filter (kids/youth only, language-aware)
            # Fast filter triggers → LLM context check (prevents false positives)
            # Kids: uses external gpt-oss-120b (DSGVO already cleared text above)
            # Youth: uses local qwen3:1.7b
            if safety_level in ('kids', 'youth'):
                has_age, found_age = fast_filter_check(input_text, safety_level, user_language)
                if has_age:
                    filter_name = 'Kids-Filter' if safety_level == 'kids' else 'Youth-Filter'
                    logger.info(f"[UNIFIED-STREAMING] {filter_name} hit: {found_age[:3]} → LLM context check")
                    verify_result = llm_verify_age_filter_context(input_text, found_age, safety_level)
                    if verify_result is None:
                        safety_breaker.record_failure()
                        if safety_breaker.is_open():
                            reason = f'{filter_name}: Sicherheitsprüfung nicht verfügbar. Bitte Ollama neustarten: sudo systemctl restart ollama'
                            logger.warning(f"[UNIFIED-STREAMING] {reason}")
                            yield generate_sse_event('blocked', {'stage': 'safety', 'reason': reason})
                            yield ''
                            return
                        logger.warning(f"[UNIFIED-STREAMING] {filter_name} LLM unavailable — circuit breaker recording failure")
                    elif verify_result:
                        safety_breaker.record_success()
                        reason = f'{filter_name}: {", ".join(found_age[:3])}'
                        logger.warning(f"[UNIFIED-STREAMING] {filter_name} BLOCKED: {reason}")
                        yield generate_sse_event('blocked', {
                            'stage': 'safety',
                            'reason': reason
                        })
                        yield ''
                        return
                    else:
                        safety_breaker.record_success()
                        logger.info(f"[UNIFIED-STREAMING] {filter_name} false positive (LLM rejected): {found_age[:3]}")

        logger.info(f"[UNIFIED-STREAMING] Stage 1: Safety PASSED (fast-filters clear)")

        # ====================================================================
        # STAGE 2: INTERCEPTION (Character-by-Character Streaming)
        # ====================================================================
        yield generate_sse_event('stage_start', {
            'stage': 2,
            'name': 'KI kombiniert deine Idee',
            'description': 'Prompt Interception'
        })
        yield ''

        logger.info(f"[UNIFIED-STREAMING] Stage 2: Starting Interception streaming")

        # Get config for execution
        config = pipeline_executor.config_loader.get_config(schema_name)

        # Override context if custom context_prompt provided
        if context_prompt and config:
            config.context = context_prompt
            logger.info(f"[UNIFIED-STREAMING] Using custom context_prompt override")

        # Execute Stage 2 via pipeline_executor (includes Wikipedia support)
        # Use threading to enable real-time Wikipedia status events
        from concurrent.futures import ThreadPoolExecutor, Future
        from schemas.engine.pipeline_executor import WIKIPEDIA_STATUS
        import time as time_module

        tracker = NoOpTracker()
        result_holder = [None]  # Mutable container for thread result

        def run_pipeline():
            result_holder[0] = asyncio.run(pipeline_executor.execute_pipeline(
                config_name=schema_name,
                input_text=input_text,
                user_input=input_text,
                safety_level=safety_level,
                tracker=tracker,
                config_override=config
            ))

        # Start pipeline in background thread
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(run_pipeline)

        # Poll for Wikipedia status while pipeline runs
        last_wiki_status = None
        while not future.done():
            current_status = WIKIPEDIA_STATUS.get('current', {})
            if current_status.get('status') != last_wiki_status:
                last_wiki_status = current_status.get('status')
                if last_wiki_status == 'lookup':
                    yield generate_sse_event('wikipedia_lookup', {
                        'status': 'start',
                        'terms': current_status.get('terms', [])
                    })
                    yield ''
                elif last_wiki_status == 'complete':
                    yield generate_sse_event('wikipedia_lookup', {
                        'status': 'complete',
                        'terms': current_status.get('terms', [])
                    })
                    yield ''
            time_module.sleep(0.1)  # Poll every 100ms

        # Get result
        future.result()  # Raises if thread had exception
        result = result_holder[0]
        executor.shutdown(wait=False)

        # Clear Wikipedia status
        WIKIPEDIA_STATUS['current'] = {}

        accumulated = ""
        chunk_count = 0

        if result.success:
            accumulated = result.final_output
            chunk_count = 1

            # Stream the complete response as one chunk
            yield generate_sse_event('chunk', {
                'stage': 2,
                'text_chunk': accumulated,
                'accumulated': accumulated,
                'chunk_count': chunk_count
            })
            yield ''
        else:
            raise Exception(f"Interception failed: {result.error}")

        logger.info(f"[UNIFIED-STREAMING] Stage 2 complete: {len(accumulated)} chars")

        # Save interception result to prompting_process subfolder
        recorder.save_to_prompting_process('interception', accumulated)

        # Send completion event
        yield generate_sse_event('complete', {
            'stage': 2,
            'final_text': accumulated,
            'char_count': len(accumulated),
            'chunk_count': chunk_count,
            'run_id': run_id
        })
        yield ''

    except GeneratorExit:
        logger.info(f"[UNIFIED-STREAMING] Client disconnected from stream: {run_id}")
        # Generator cleanup - no re-raise needed

    except Exception as e:
        logger.error(f"[UNIFIED-STREAMING] Error in run {run_id}: {e}")
        yield generate_sse_event('error', {
            'message': str(e),
            'run_id': run_id
        })
        yield ''

    finally:
        logger.info(f"[UNIFIED-STREAMING] Cleanup complete for run: {run_id}")


# ============================================================================
# OPTIMIZATION STREAMING (Stage 2 only, no Safety Check)
# Lab Paradigm: Frontend-orchestrated, atomic service
# ============================================================================

def execute_optimization_streaming(data: dict):
    """
    Execute optimization with SSE streaming - Stage 3 ONLY.

    Lab Architecture: This is an atomic service that the frontend calls
    when the input is already safe (e.g., interception result from Stage 2).
    No Stage 1 safety check - by design.

    Use Case: Frontend has interception_result (Stage 2 output), user selected a model,
    now Stage 3 optimization transforms it for that specific model's format requirements.
    """
    import time
    import os
    from config import STAGE3_MODEL, DEFAULT_INTERCEPTION_CONFIG

    # Extract parameters
    schema_name = data.get('schema', DEFAULT_INTERCEPTION_CONFIG)
    input_text = data.get('input_text', '')  # Already safe interception result
    context_prompt = data.get('context_prompt', '')  # Optimization instruction
    run_id_param = data.get('run_id')  # Session 130: From interception for persistence
    device_id = data.get('device_id')
    output_config = data.get('output_config')  # Session 153: For model selection from output config

    # Generate run ID for logging (use param if available)
    run_id = run_id_param or generate_run_id(suffix="opt")

    logger.info(f"[OPTIMIZATION-STREAMING] Starting for run {run_id}")
    logger.info(f"[OPTIMIZATION-STREAMING] Schema: {schema_name}, Input length: {len(input_text)}")

    # Session 130: Load recorder at START (same pattern as interception)
    recorder = None
    if run_id_param and run_id_param.startswith('run_'):
        from config import JSON_STORAGE_DIR
        recorder = load_recorder(run_id_param, base_path=JSON_STORAGE_DIR)
        if recorder:
            logger.info(f"[OPTIMIZATION-STREAMING] Loaded recorder for {run_id_param}")

    try:
        # Initialize schema engine
        if pipeline_executor is None:
            init_schema_engine()

        # Send initial connection event
        yield generate_sse_event('connected', {
            'run_id': run_id,
            'schema': schema_name,
            'stages': 1  # Only Stage 3 (optimization)
        })
        yield ''

        # ====================================================================
        # STAGE 3: OPTIMIZATION (no Stage 1 - input is already safe from Stage 2)
        # ====================================================================
        yield generate_sse_event('stage_start', {
            'stage': 3,
            'name': 'Prompt Optimization',
            'description': 'Model-specific transformation'
        })
        yield ''

        logger.info(f"[OPTIMIZATION-STREAMING] Stage 3: Starting optimization")

        # TODO [ARCHITECTURE VIOLATION]: Direct Engine instantiation bypasses ChunkBuilder
        # See: docs/ARCHITECTURE_VIOLATION_PromptInterceptionEngine.md
        engine = PromptInterceptionEngine()

        # Use context_prompt as the optimization rules (style-specific)
        style_prompt = context_prompt

        # Session 134 FIX: Use prompt_optimization instruction for this stage
        task_instruction = get_instruction("prompt_optimization")

        # Determine model - Session 153: Override-Pattern for CODING_MODEL
        # If output_config has meta.model set (and != "DEFAULT"), use that
        model_override = None
        if output_config:
            model_override = _load_model_from_output_config(output_config)

        if model_override and model_override != "DEFAULT":
            model = model_override
            logger.info(f"[OPTIMIZATION-STREAMING] Using model override from {output_config}: {model}")
        else:
            model = STAGE3_MODEL
            logger.info(f"[OPTIMIZATION-STREAMING] Using default STAGE3_MODEL: {model}")
        pi_request = PromptInterceptionRequest(
            input_prompt=input_text,
            input_context='',
            style_prompt=style_prompt,
            task_instruction=task_instruction,  # Session 134: Meta-instruction
            model=model,
            debug=False,
            unload_model=False,
            parameters={"enable_thinking": False}  # Structured JSON output, no reasoning
        )
        pi_response = asyncio.run(engine.process_request(pi_request))

        if pi_response.success:
            accumulated = pi_response.output_str
            chunk_count = 1

            # Stream the complete response
            yield generate_sse_event('chunk', {
                'stage': 3,
                'text_chunk': accumulated,
                'accumulated': accumulated,
                'chunk_count': chunk_count
            })
            yield ''
        else:
            raise Exception(f"Optimization failed: {pi_response.error}")

        logger.info(f"[OPTIMIZATION-STREAMING] Stage 3 complete: {len(accumulated)} chars")

        # Session 130: Save optimized_prompt immediately after LLM generation
        if recorder:
            recorder.save_to_prompting_process('optimized_prompt', accumulated)
            logger.info(f"[OPTIMIZATION-STREAMING] Saved optimized_prompt to {run_id_param}")

        # Send completion event
        yield generate_sse_event('complete', {
            'stage': 3,
            'final_text': accumulated,
            'char_count': len(accumulated),
            'chunk_count': 1,
            'run_id': run_id
        })
        yield ''

    except GeneratorExit:
        logger.info(f"[OPTIMIZATION-STREAMING] Client disconnected: {run_id}")

    except Exception as e:
        logger.error(f"[OPTIMIZATION-STREAMING] Error in run {run_id}: {e}")
        yield generate_sse_event('error', {
            'message': str(e),
            'run_id': run_id
        })
        yield ''

    finally:
        logger.info(f"[OPTIMIZATION-STREAMING] Cleanup complete for run: {run_id}")


@schema_bp.route('/pipeline/optimize', methods=['POST', 'GET'])
def optimize_pipeline():
    """
    Optimization endpoint - Stage 3 only, no Stage 1 safety check.

    Lab Architecture: Atomic service for frontend-orchestrated workflows.
    Called when input is already safe (Stage 2 interception result).
    Transforms interception output to model-specific format (e.g., visual tokens for SD3.5).
    """
    try:
        # Request-Validation: Support both POST (JSON) and GET (query params for EventSource)
        if request.method == 'GET':
            data = {
                'schema': request.args.get('schema'),
                'input_text': request.args.get('input_text'),
                'context_prompt': request.args.get('context_prompt', ''),
                'enable_streaming': request.args.get('enable_streaming') == 'true',
                'run_id': request.args.get('run_id'),  # Session 130: For persistence
                'device_id': request.args.get('device_id'),
                'output_config': request.args.get('output_config')  # Session 154: For CODING_MODEL override
            }
        else:
            data = request.get_json()
            if not data:
                return jsonify({
                    'status': 'error',
                    'error': 'JSON-Request erwartet'
                }), 400

        # Streaming mode (primary use case)
        enable_streaming = data.get('enable_streaming', False)
        if enable_streaming:
            logger.info("[OPTIMIZATION-STREAMING] Streaming mode requested")
            return Response(
                stream_with_context(execute_optimization_streaming(data)),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no'
                }
            )

        # Non-streaming fallback (synchronous)
        schema_name = data.get('schema', DEFAULT_INTERCEPTION_CONFIG)
        input_text = data.get('input_text', '')
        context_prompt = data.get('context_prompt', '')

        if pipeline_executor is None:
            init_schema_engine()

        # TODO [ARCHITECTURE VIOLATION]: Direct Engine instantiation bypasses ChunkBuilder
        # See: docs/ARCHITECTURE_VIOLATION_PromptInterceptionEngine.md
        engine = PromptInterceptionEngine()
        from config import STAGE2_INTERCEPTION_MODEL

        # Session 134 FIX: Use prompt_optimization instruction
        task_instruction = get_instruction("prompt_optimization")

        pi_request = PromptInterceptionRequest(
            input_prompt=input_text,
            input_context='',
            style_prompt=context_prompt,
            task_instruction=task_instruction,  # Session 134: Meta-instruction
            model=STAGE2_INTERCEPTION_MODEL,
            debug=False,
            unload_model=False
        )
        pi_response = asyncio.run(engine.process_request(pi_request))

        if pi_response.success:
            return jsonify({
                'status': 'success',
                'result': pi_response.output_str
            })
        else:
            return jsonify({
                'status': 'error',
                'error': pi_response.error
            }), 500

    except Exception as e:
        logger.error(f"[OPTIMIZATION] Error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@schema_bp.route('/pipeline/safety/quick', methods=['POST'])
def safety_check_quick():
    """
    Quick safety check for text (§86a + DSGVO) and uploaded images (VLM).

    Used by MediaInputBox autonomous safety (on blur/paste) and
    ImageUploadWidget (after upload).

    Text mode (field: "text"):
        §86a fast-filter → SpaCy NER → (if PER hit) LLM verify → block/allow

    Image mode (field: "image_path"):
        VLM safety check via Ollama (kids/youth only, fail-open)

    Request Body: { "text": "..." } or { "image_path": "/path/to/uploaded.png" }
    Response: { "safe": bool, "checks_passed": [...], "error_message": str|null }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'safe': True, 'checks_passed': [], 'error_message': None})

        # IMAGE MODE: VLM safety check for uploaded images
        image_path = data.get('image_path', '').strip()
        if image_path:
            safety_level = config.DEFAULT_SAFETY_LEVEL
            if safety_level not in ('kids', 'youth'):
                return jsonify({'safe': True, 'checks_passed': ['vlm_skipped'], 'error_message': None})

            from my_app.utils.vlm_safety import vlm_safety_check
            is_safe, reason, description = vlm_safety_check(image_path, safety_level)
            if not is_safe:
                logger.warning(f"[SAFETY-QUICK] VLM image BLOCKED: {reason}")
                return jsonify({
                    'safe': False,
                    'checks_passed': ['vlm_image_check'],
                    'error_message': reason,
                    'vlm_description': description
                })
            return jsonify({'safe': True, 'checks_passed': ['vlm_image_check'], 'error_message': None, 'vlm_description': description})

        # TEXT MODE: §86a fast-filter + DSGVO NER
        text = data.get('text', '').strip()
        user_language = data.get('user_language', 'de')
        if not text:
            return jsonify({'safe': True, 'checks_passed': [], 'error_message': None})

        # Research mode: skip ALL safety checks (text + image)
        if config.DEFAULT_SAFETY_LEVEL == 'research':
            return jsonify({'safe': True, 'checks_passed': ['safety_skip'], 'error_message': None})

        checks_passed = []
        safety_level = config.DEFAULT_SAFETY_LEVEL

        # STEP 1: §86a fast-filter — instant block (language-aware)
        has_86a, found_86a = fast_filter_bilingual_86a(text, user_language)
        if has_86a:
            logger.warning(f"[SAFETY-QUICK] §86a BLOCKED: {found_86a[:3]}")
            return jsonify({
                'safe': False,
                'checks_passed': ['§86a'],
                'error_message': f'§86a StGB: {", ".join(found_86a[:3])}'
            })
        checks_passed.append('§86a')

        # STEP 2: DSGVO SpaCy NER — runs BEFORE age filter to ensure no personal
        # data leaves local system. This allows age filter to use external LLMs safely.
        has_pii, found_pii, spacy_ok = fast_dsgvo_check(text)
        if spacy_ok and has_pii:
            logger.info(f"[SAFETY-QUICK] NER triggered: {found_pii[:3]} — verifying with LLM")
            verify_result = llm_verify_person_name(text, found_pii)
            if verify_result is None:
                safety_breaker.record_failure()
                if safety_breaker.is_open():
                    logger.warning(f"[SAFETY-QUICK] DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte Ollama neustarten: sudo systemctl restart ollama")
                    return jsonify({
                        'safe': False,
                        'checks_passed': checks_passed + ['dsgvo_ner'],
                        'error_message': 'DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte Ollama neustarten: sudo systemctl restart ollama'
                    })
                logger.warning(f"[SAFETY-QUICK] DSGVO LLM unavailable — circuit breaker recording failure")
            elif verify_result:
                safety_breaker.record_success()
                logger.warning(f"[SAFETY-QUICK] DSGVO BLOCKED (LLM confirmed): {found_pii[:3]}")
                return jsonify({
                    'safe': False,
                    'checks_passed': checks_passed + ['dsgvo_ner', 'dsgvo_llm_verify'],
                    'error_message': f'DSGVO: {", ".join(found_pii[:3])}'
                })
            else:
                safety_breaker.record_success()
                logger.info(f"[SAFETY-QUICK] NER false positive (LLM rejected): {found_pii[:3]}")
        if spacy_ok:
            checks_passed.append('dsgvo_ner')

        # STEP 3: Age-appropriate fast-filter (kids/youth only, language-aware)
        # Kids: uses external gpt-oss-120b (DSGVO already cleared text above)
        # Youth: uses local qwen3:1.7b
        if safety_level in ('kids', 'youth'):
            has_age_terms, found_age_terms = fast_filter_check(text, safety_level, user_language)
            if has_age_terms:
                filter_name = 'Kids-Filter' if safety_level == 'kids' else 'Youth-Filter'
                logger.info(f"[SAFETY-QUICK] {filter_name} hit: {found_age_terms[:3]} → LLM context check")
                verify_result = llm_verify_age_filter_context(text, found_age_terms, safety_level)
                if verify_result is None:
                    safety_breaker.record_failure()
                    if safety_breaker.is_open():
                        logger.warning(f"[SAFETY-QUICK] {filter_name}: Sicherheitsprüfung nicht verfügbar")
                        return jsonify({
                            'safe': False,
                            'checks_passed': checks_passed + ['age_filter'],
                            'error_message': f'{filter_name}: Sicherheitsprüfung nicht verfügbar'
                        })
                    logger.warning(f"[SAFETY-QUICK] {filter_name} LLM unavailable — circuit breaker recording failure")
                elif verify_result:
                    safety_breaker.record_success()
                    logger.warning(f"[SAFETY-QUICK] {filter_name} BLOCKED (LLM confirmed): {found_age_terms[:3]}")
                    return jsonify({
                        'safe': False,
                        'checks_passed': checks_passed + ['age_filter', 'age_llm_verify'],
                        'error_message': f'{filter_name}: {", ".join(found_age_terms[:3])}'
                    })
                else:
                    safety_breaker.record_success()
                    logger.info(f"[SAFETY-QUICK] {filter_name} false positive (LLM rejected): {found_age_terms[:3]}")
            checks_passed.append('age_filter')

        return jsonify({'safe': True, 'checks_passed': checks_passed, 'error_message': None})

    except Exception as e:
        logger.error(f"[SAFETY-QUICK] Error: {e}")
        # Fail-open on error
        return jsonify({'safe': True, 'checks_passed': [], 'error_message': None})


@schema_bp.route('/pipeline/translate', methods=['POST'])
def translate_text():
    """
    Translation endpoint - atomic service for German→English translation.

    Lab Architecture: Translates interception result to English for media generation.
    Used in Stage 3 before passing prompt to image/video/audio models.

    Request Body:
    {
        "text": "German text to translate",
        "target_language": "en"  # Currently only 'en' supported
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'error': 'JSON-Request erwartet'}), 400

        text = data.get('text', '')
        target_language = data.get('target_language', 'en')

        if not text:
            return jsonify({'status': 'error', 'error': 'text ist erforderlich'}), 400

        if target_language != 'en':
            return jsonify({'status': 'error', 'error': 'Nur target_language=en wird unterstützt'}), 400

        logger.info(f"[TRANSLATE-ENDPOINT] Translating {len(text)} chars to {target_language}")

        if pipeline_executor is None:
            init_schema_engine()

        # Use the existing translation pipeline
        import time
        start_time = time.time()

        result = asyncio.run(pipeline_executor.execute_pipeline(
            'pre_output/translation_en',
            text,
        ))

        duration_ms = (time.time() - start_time) * 1000

        if result.success:
            translated = result.final_output
            logger.info(f"[TRANSLATE-ENDPOINT] Success in {duration_ms:.0f}ms: {translated[:100]}...")

            return jsonify({
                'status': 'success',
                'translated_text': translated,
                'source_language': 'de',
                'target_language': target_language,
                'duration_ms': duration_ms
            })
        else:
            return jsonify({
                'status': 'error',
                'error': result.error or 'Translation failed'
            }), 500

    except Exception as e:
        logger.error(f"[TRANSLATE-ENDPOINT] Error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@schema_bp.route('/pipeline/log-prompt-change', methods=['POST'])
def log_prompt_change():
    """
    Session 130: Log prompt changes to prompting_process/ folder.

    Called by frontend when user modifies text in any input box and then
    performs another action (blur event). Records ALL prompt iterations
    for research purposes.

    Request Body:
    {
        "run_id": "run_xxx",
        "entity_type": "input" | "interception" | "optimized_prompt" | "media_prompt",
        "content": "The changed text content",
        "device_id": "browser_id_date"  // For folder lookup
    }
    """
    from config import JSON_STORAGE_DIR
    from my_app.services.pipeline_recorder import load_recorder

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        run_id = data.get('run_id')
        entity_type = data.get('entity_type')
        content = data.get('content', '')

        if not run_id:
            return jsonify({'error': 'run_id required'}), 400
        if not entity_type:
            return jsonify({'error': 'entity_type required'}), 400

        # Load existing recorder
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            logger.warning(f"[LOG-PROMPT] No recorder found for {run_id}, skipping")
            return jsonify({'status': 'skipped', 'reason': 'no_recorder'}), 200

        # Save to prompting_process/ subfolder
        filename = recorder.save_to_prompting_process(entity_type, content)

        logger.info(f"[LOG-PROMPT] Saved {entity_type} change to {filename}")
        return jsonify({
            'status': 'ok',
            'filename': filename,
            'run_id': run_id
        }), 200

    except Exception as e:
        logger.error(f"[LOG-PROMPT] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# POST-GENERATION VLM SAFETY CHECK
# Analyzes generated images with a local Vision-Language Model (qwen3-vl:2b)
# to catch unsafe content that text-based checks cannot predict.
# ============================================================================

def _vlm_safety_check_image(recorder, safety_level: str) -> tuple:
    """
    Post-generation image safety check using a local VLM via Ollama.

    Delegates to vlm_safety.vlm_safety_check() helper.

    Args:
        recorder: LivePipelineRecorder with saved output_image entity
        safety_level: 'kids' or 'youth' (only these trigger VLM check)

    Returns:
        (is_safe: bool, reason: str, description: str)
        Fail-open: returns (True, '', '') on any error.
    """
    from my_app.utils.vlm_safety import vlm_safety_check

    image_path = recorder.get_entity_path('output_image')
    if not image_path or not image_path.exists():
        logger.warning("[VLM-SAFETY] No output_image entity found — skipping check")
        return (True, '', '')

    return vlm_safety_check(image_path, safety_level)


# ============================================================================
# GENERATION STREAMING (Stage 3 + Stage 4)
# Session 148: SSE for real-time badge updates
# ============================================================================

def execute_generation_streaming(data: dict):
    """
    Execute Stage 3 (Translation+Safety) + Stage 4 (Generation) with SSE streaming.

    Session 148: Enables real-time badge updates for Safety and Translation
    before media generation starts.

    Events emitted:
        - connected: Initial connection with run_id
        - stage3_start: Translation + Safety check starting
        - stage3_complete: {was_translated, safe} - triggers badges in frontend
        - blocked: Content blocked by safety check (stops here)
        - stage4_start: Media generation starting
        - complete: {media_output, run_id, loras} - final result
        - error: Error occurred
    """
    import time
    import os

    # Extract parameters
    prompt = data.get('prompt', '')
    output_config = data.get('output_config')
    seed = data.get('seed')
    safety_level = config.DEFAULT_SAFETY_LEVEL
    user_language = data.get('user_language', 'de')
    alpha_factor = data.get('alpha_factor')
    input_image = data.get('input_image')
    input_image1 = data.get('input_image1')
    input_image2 = data.get('input_image2')
    input_image3 = data.get('input_image3')
    input_text = data.get('input_text', '')
    context_prompt = data.get('context_prompt', '')
    interception_result = data.get('interception_result', '')
    interception_config = data.get('interception_config', '')
    device_id = data.get('device_id') or f"api_{os.urandom(6).hex()}"
    provided_run_id = data.get('run_id')

    # Session 151: Generation parameters (optional, gracefully ignored if config doesn't support them)
    width = data.get('width')
    height = data.get('height')
    steps = data.get('steps')
    cfg = data.get('cfg')
    negative_prompt = data.get('negative_prompt')
    sampler_name = data.get('sampler_name')
    scheduler = data.get('scheduler')
    denoise = data.get('denoise')

    # Session 153: Apply same run_id continuity logic as non-streaming mode
    # 1 Run = 1 Media Output - create new run if existing has output
    from config import JSON_STORAGE_DIR
    run_id = None
    existing_recorder = None

    if provided_run_id and provided_run_id.startswith('run_'):
        existing_recorder = load_recorder(provided_run_id, base_path=JSON_STORAGE_DIR)
        if existing_recorder:
            has_output = any(
                e.get('type', '').startswith('output_')
                for e in existing_recorder.metadata.get('entities', [])
            )
            if has_output:
                run_id = generate_run_id()
                existing_recorder = None  # Don't reuse - create new recorder later
                logger.info(f"[GENERATION-STREAMING] Previous run has output, creating new: {run_id}")
            else:
                run_id = provided_run_id
                logger.info(f"[GENERATION-STREAMING] Continuing existing run: {run_id}")

    if not run_id:
        run_id = generate_run_id()

    logger.info(f"[GENERATION-STREAMING] Starting for config '{output_config}', run {run_id}")

    try:
        if pipeline_executor is None:
            init_schema_engine()

        # Send initial connection event
        yield generate_sse_event('connected', {
            'run_id': run_id,
            'output_config': output_config
        })
        yield ''  # Force flush

        # ====================================================================
        # STAGE 3: TRANSLATION + SAFETY CHECK
        # ====================================================================
        yield generate_sse_event('stage3_start', {
            'name': 'Translation & Safety',
            'description': 'Translating and checking content safety'
        })
        yield ''

        logger.info(f"[GENERATION-STREAMING] Stage 3: Translation + Safety")

        # Determine media type from output config
        if 'code' in output_config.lower() or 'p5js' in output_config.lower() or 'tonejs' in output_config.lower():
            media_type = 'code'
        elif 'video' in output_config.lower():
            media_type = 'video'
        elif 'audio' in output_config.lower() or 'music' in output_config.lower() or 'ace' in output_config.lower():
            media_type = 'audio'
        elif '3d' in output_config.lower():
            media_type = '3d'
        else:
            media_type = 'image'

        # Execute Stage 3: Translation + Safety
        safety_result = asyncio.run(execute_stage3_safety(
            prompt,
            safety_level,
            media_type,
            pipeline_executor,
            user_language=user_language
        ))

        # Check if translation occurred
        translated_prompt = safety_result.get('positive_prompt', prompt)
        was_translated = translated_prompt and translated_prompt != prompt

        if not safety_result['safe']:
            # BLOCKED by Stage 3
            logger.warning(f"[GENERATION-STREAMING] Stage 3 BLOCKED for run {run_id}")
            yield generate_sse_event('blocked', {
                'stage': 3,
                'reason': safety_result.get('abort_reason', 'Content blocked by safety check'),
                'found_terms': safety_result.get('found_terms', []),
                'run_id': run_id,
                'checks_passed': ['translation', safety_result.get('method', 'llm_context_check')]
            })
            yield ''
            return

        # Stage 3 complete - send badge trigger event
        logger.info(f"[GENERATION-STREAMING] Stage 3 PASSED, was_translated={was_translated}")
        stage3_checks = ['translation'] if was_translated else []
        stage3_method = safety_result.get('method', 'fast_filter')
        if stage3_method != 'disabled':
            stage3_checks.append(stage3_method)
        yield generate_sse_event('stage3_complete', {
            'safe': True,
            'was_translated': was_translated,
            'checks_passed': stage3_checks
        })
        yield ''

        # ====================================================================
        # STAGE 4: MEDIA GENERATION
        # ====================================================================

        # Determine backend type + model meta BEFORE emitting stage4_start
        import contextvars
        import queue as queue_mod

        config_obj = pipeline_executor.config_loader.get_config(output_config)
        backend_type = (config_obj.meta.get('backend_type', 'comfyui')
                        if config_obj and config_obj.meta else 'comfyui')

        # Build model_meta for expert frontend (Steckbrief / denoising view)
        # Forward all meta fields except internal-only keys, add runtime overrides
        config_meta = config_obj.meta if config_obj and config_obj.meta else {}
        config_params = config_obj.parameters if config_obj and config_obj.parameters else {}
        INTERNAL_META_KEYS = {'optimization_instruction', 'stage'}
        model_meta = {k: v for k, v in config_meta.items() if k not in INTERNAL_META_KEYS}
        model_meta.update({
            'backend_type': backend_type,
            'seed': seed,
            'cfg': cfg if cfg is not None else config_params.get('CFG', config_params.get('cfg', config_params.get('cfg_scale'))),
            'steps': steps if steps is not None else config_params.get('STEPS', config_params.get('steps')),
        })

        yield generate_sse_event('stage4_start', {
            'name': 'Media Generation',
            'output_config': output_config,
            'model_meta': model_meta
        })
        yield ''

        logger.info(f"[GENERATION-STREAMING] Stage 4: Starting generation")

        # Session 153: Reuse existing recorder if continuing run, else create new
        if existing_recorder:
            recorder = existing_recorder
            logger.info(f"[GENERATION-STREAMING] Reusing existing recorder for {run_id}")
        else:
            recorder = get_recorder(
                run_id=run_id,
                config_name=output_config,
                safety_level=safety_level,
                device_id=device_id,
                base_path=JSON_STORAGE_DIR
            )

        # Save translation info
        if was_translated:
            recorder.save_entity('translation_en', translated_prompt)

        # Queue used by ComfyUI callback and as sentinel for all backends
        progress_queue = queue_mod.Queue()
        SENTINEL = object()

        # ComfyUI: inject on_progress callback via ContextVar
        logger.info(f"[GENERATION-STREAMING] Backend type: {backend_type}")
        if backend_type == 'comfyui':
            def _on_comfyui_progress(event):
                progress_queue.put(event)
            set_progress_callback(_on_comfyui_progress)

        # ── Run generation in background thread ──
        ctx = contextvars.copy_context()
        result_holder = [None]
        error_holder = [None]

        def _generation_thread():
            try:
                result_holder[0] = ctx.run(
                    asyncio.run,
                    execute_stage4_generation_only(
                        prompt=translated_prompt,
                        output_config=output_config,
                        safety_level=safety_level,
                        run_id=run_id,
                        seed=seed,
                        recorder=recorder,
                        device_id=device_id,
                        input_text=input_text,
                        context_prompt=context_prompt,
                        interception_result=interception_result,
                        interception_config=interception_config,
                        input_image=input_image,
                        input_image1=input_image1,
                        input_image2=input_image2,
                        input_image3=input_image3,
                        alpha_factor=alpha_factor,
                        width=width, height=height, steps=steps,
                        cfg=cfg, negative_prompt=negative_prompt,
                        sampler_name=sampler_name, scheduler=scheduler,
                        denoise=denoise
                    )
                )
            except Exception as e:
                error_holder[0] = e
            finally:
                progress_queue.put(SENTINEL)

        thread = threading.Thread(target=_generation_thread, daemon=True)
        thread.start()

        # ── SSE progress event loop (backend-dependent) ──
        if backend_type == 'comfyui':
            # ComfyUI: push-based via WS callback → queue
            while True:
                try:
                    item = progress_queue.get(timeout=2.0)
                except queue_mod.Empty:
                    yield ': heartbeat\n\n'
                    continue
                if item is SENTINEL:
                    break
                yield generate_sse_event('generation_progress', {
                    'percent': round(item.overall_percent * 100),
                    'preview': f'data:image/jpeg;base64,{item.preview_base64}' if item.preview_base64 else None,
                    'node': item.current_node
                })
                yield ''

        elif backend_type == 'diffusers':
            # Diffusers: poll GPU service progress endpoint
            gpu_progress_url = f"{config.GPU_SERVICE_URL}/api/diffusers/progress"
            last_step = -1
            while thread.is_alive():
                try:
                    resp = requests.get(gpu_progress_url, timeout=1).json()
                    if resp.get('active') and resp.get('step', 0) != last_step:
                        last_step = resp['step']
                        total = resp.get('total_steps', 1)
                        yield generate_sse_event('generation_progress', {
                            'percent': round((last_step / total) * 100) if total > 0 else 0,
                            'step': last_step,
                            'total_steps': total
                        })
                        yield ''
                except Exception:
                    pass
                time.sleep(1.0)

        else:
            # Other backends (heartmula, stable_audio, openai, etc.): heartbeat only
            while thread.is_alive():
                yield ': heartbeat\n\n'
                time.sleep(2.0)

        # ── Join thread + error handling ──
        thread.join(timeout=5.0)
        # Clean up ComfyUI callback
        if backend_type == 'comfyui':
            set_progress_callback(None)

        if error_holder[0]:
            raise error_holder[0]
        result = result_holder[0]

        if not result or not result['success']:
            raise Exception(result.get('error', 'Generation failed') if result else 'Generation returned no result')

        logger.info(f"[GENERATION-STREAMING] Stage 4 complete: {result['media_output']}")

        # POST-GENERATION VLM SAFETY CHECK (images only, kids/youth only)
        if media_type == 'image' and safety_level in ('kids', 'youth'):
            vlm_safe, vlm_reason, vlm_description = _vlm_safety_check_image(recorder, safety_level)
            if not vlm_safe:
                logger.warning(f"[GENERATION-STREAMING] VLM safety BLOCKED for run {run_id}: {vlm_reason}")
                yield generate_sse_event('blocked', {
                    'stage': 'vlm_safety',
                    'reason': vlm_reason,
                    'vlm_description': vlm_description,
                    'run_id': run_id,
                    'checks_passed': ['stage3', 'stage4', 'vlm_image_check']
                })
                yield ''
                return

        # Send completion event
        yield generate_sse_event('complete', {
            'status': 'success',
            'media_output': result['media_output'],
            'run_id': result['run_id'],
            'loras': result.get('loras', []),
            'was_translated': was_translated
        })
        yield ''

    except GeneratorExit:
        logger.info(f"[GENERATION-STREAMING] Client disconnected: {run_id}")

    except Exception as e:
        logger.error(f"[GENERATION-STREAMING] Error in run {run_id}: {e}")
        import traceback
        traceback.print_exc()
        yield generate_sse_event('error', {
            'message': str(e),
            'run_id': run_id
        })
        yield ''

    finally:
        logger.info(f"[GENERATION-STREAMING] Cleanup complete for run: {run_id}")


@schema_bp.route('/pipeline/generation', methods=['POST', 'GET'])
def generation_endpoint():
    """
    Generation endpoint - Stage 3 Safety (auto) + Stage 4 Media Generation.

    Session 133: Refactored to use execute_generation_stage4() helper.
    Session 148: Added SSE streaming mode for real-time badge updates.
    Lab Architecture: Each generation creates NEW run with complete context.

    Request Body: See execute_generation_stage4() docstring for parameters.
    """
    import time
    import uuid

    start_time = time.time()

    try:
        # Support both POST (JSON) and GET (query params for EventSource)
        if request.method == 'GET':
            data = {
                'prompt': request.args.get('prompt', ''),
                'output_config': request.args.get('output_config'),
                'seed': request.args.get('seed'),
                'safety_level': request.args.get('safety_level', 'youth'),
                'alpha_factor': request.args.get('alpha_factor'),
                'input_image': request.args.get('input_image'),
                'input_image1': request.args.get('input_image1'),
                'input_image2': request.args.get('input_image2'),
                'input_image3': request.args.get('input_image3'),
                'input_text': request.args.get('input_text', ''),
                'context_prompt': request.args.get('context_prompt', ''),
                'interception_result': request.args.get('interception_result', ''),
                'interception_config': request.args.get('interception_config', ''),
                'device_id': request.args.get('device_id'),
                'run_id': request.args.get('run_id'),
                'enable_streaming': request.args.get('enable_streaming') == 'true',
                # Session 151: Generation parameters (optional)
                'width': request.args.get('width', type=int),
                'height': request.args.get('height', type=int),
                'steps': request.args.get('steps', type=int),
                'cfg': request.args.get('cfg', type=float),
                'negative_prompt': request.args.get('negative_prompt'),
                'sampler_name': request.args.get('sampler_name'),
                'scheduler': request.args.get('scheduler'),
                'denoise': request.args.get('denoise', type=float)
            }
            # Convert seed to int if present
            if data['seed']:
                try:
                    data['seed'] = int(data['seed'])
                except ValueError:
                    data['seed'] = None
        else:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'error': 'JSON-Request erwartet'}), 400

        # Session 148: Streaming mode for real-time badge updates
        enable_streaming = data.get('enable_streaming', False)
        if enable_streaming:
            logger.info("[GENERATION-STREAMING] Streaming mode requested")
            return Response(
                stream_with_context(execute_generation_streaming(data)),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no'
                }
            )

        # Non-streaming mode (original behavior)
        # Extract parameters
        prompt = data.get('prompt', '')
        output_config = data.get('output_config')
        seed = data.get('seed')
        safety_level = config.DEFAULT_SAFETY_LEVEL
        alpha_factor = data.get('alpha_factor')
        input_image = data.get('input_image')
        input_image1 = data.get('input_image1')
        input_image2 = data.get('input_image2')
        input_image3 = data.get('input_image3')
        input_text = data.get('input_text', '')
        context_prompt = data.get('context_prompt', '')
        interception_result = data.get('interception_result', '')
        interception_config = data.get('interception_config', '')
        device_id = data.get('device_id') or f"api_{uuid.uuid4().hex[:12]}"
        provided_run_id = data.get('run_id')
        user_language = data.get('user_language', 'de')

        if not prompt or not output_config:
            return jsonify({'status': 'error', 'error': 'prompt und output_config sind erforderlich'}), 400

        logger.info(f"[GENERATION-ENDPOINT] Starting for config '{output_config}'")
        logger.info(f"[GENERATION-ENDPOINT] Prompt (first 100 chars): {prompt[:100]}...")

        if pipeline_executor is None:
            init_schema_engine()

        # Session 130: Handle run_id continuity (1 Run = 1 Media Output)
        from config import JSON_STORAGE_DIR
        recorder = None
        run_id = None

        if provided_run_id and provided_run_id.startswith('run_'):
            existing_recorder = load_recorder(provided_run_id, base_path=JSON_STORAGE_DIR)
            if existing_recorder:
                has_output = any(
                    e.get('type', '').startswith('output_')
                    for e in existing_recorder.metadata.get('entities', [])
                )
                if has_output:
                    run_id = generate_run_id()
                    logger.info(f"[GENERATION-ENDPOINT] Previous run has output, creating new: {run_id}")
                else:
                    run_id = provided_run_id
                    recorder = existing_recorder
                    logger.info(f"[GENERATION-ENDPOINT] Continuing existing run: {run_id}")

        # Call helper function for generation
        result = asyncio.run(execute_generation_stage4(
            prompt=prompt,
            output_config=output_config,
            safety_level=safety_level,
            seed=seed,
            recorder=recorder,
            run_id=run_id,
            device_id=device_id,
            input_text=input_text,
            context_prompt=context_prompt,
            interception_result=interception_result,
            interception_config=interception_config,
            input_image=input_image,
            input_image1=input_image1,
            input_image2=input_image2,
            input_image3=input_image3,
            alpha_factor=alpha_factor,
            user_language=user_language,
            # Session 155: Parameter Injection (replicate seed pattern)
            width=data.get('width'),
            height=data.get('height'),
            steps=data.get('steps'),
            cfg=data.get('cfg')
        ))

        # Handle result
        if not result['success']:
            if result.get('blocked'):
                return jsonify({
                    'status': 'blocked',
                    'stage': 3,
                    'reason': result['error'],
                    'found_terms': result.get('found_terms', [])
                }), 403
            return jsonify({
                'status': 'error',
                'error': result['error']
            }), 500

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"[GENERATION-ENDPOINT] Success in {duration_ms:.0f}ms")

        return jsonify({
            'status': 'success',
            'media_output': result['media_output'],
            'run_id': result['run_id'],
            'duration_ms': duration_ms,
            'loras': result.get('loras', []),
            'was_translated': result.get('was_translated', False)
        })

    except Exception as e:
        logger.error(f"[GENERATION-ENDPOINT] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(e)}), 500


async def execute_stage4_generation_only(
    prompt: str,
    output_config: str,
    safety_level: str,
    run_id: str,
    seed: int = None,
    recorder = None,
    device_id: str = None,
    input_text: str = '',
    context_prompt: str = '',
    interception_result: str = '',
    interception_config: str = '',
    input_image: str = None,
    input_image1: str = None,
    input_image2: str = None,
    input_image3: str = None,
    alpha_factor = None,
    # Session 151: Generation parameters (all optional, ignored if config doesn't support them)
    width: int = None,
    height: int = None,
    steps: int = None,
    cfg: float = None,
    negative_prompt: str = None,
    sampler_name: str = None,
    scheduler: str = None,
    denoise: float = None,
    secondary_text: str = None
) -> dict:
    """
    Stage 4 ONLY: Media generation.

    Expects an already-translated, already-safety-checked prompt.
    Does NOT call Stage 3 - pure generation only.

    Session 136: Extracted from execute_generation_stage4 for clean separation.
    Canvas workflows call this directly. Lab workflows use execute_generation_stage4
    which handles Stage 3 before calling this function.

    Args:
        prompt: Ready-to-use prompt (already translated to English if needed)
        output_config: Config ID (e.g., 'sd35_large')
        safety_level: 'kids', 'youth', 'adult', or 'research' (for metadata only)
        run_id: Run identifier (required)
        seed: Optional seed (generates random if None)
        recorder: Optional LivePipelineRecorder instance (creates new if None)
        device_id: Optional device_id for folder structure
        input_text: Original user input (for recorder)
        context_prompt: Meta-prompt used (for recorder)
        interception_result: Interception output (for recorder)
        interception_config: Interception config ID (for LoRA extraction)
        input_image: Path to input image for img2img
        input_image1/2/3: Paths for multi-image workflows
        alpha_factor: Alpha factor for Surrealizer

    Returns:
        {
            'success': bool,
            'media_output': {
                'media_type': 'image',
                'url': '/api/media/image/run_xxx/0',
                'run_id': 'run_xxx',
                'index': 0,
                'seed': 123456
            },
            'run_id': str,
            'error': Optional[str]
        }
    """
    import time
    import random

    try:
        # Initialize schema engine if needed
        if pipeline_executor is None:
            init_schema_engine()

        # Generate device_id if not provided
        if device_id is None:
            device_id = f"api_{uuid.uuid4().hex[:12]}"

        # Determine media type from output config
        if 'code' in output_config.lower() or 'p5js' in output_config.lower() or 'tonejs' in output_config.lower():
            media_type = 'code'
        elif 'video' in output_config.lower():
            media_type = 'video'
        elif 'audio' in output_config.lower() or 'music' in output_config.lower() or 'ace' in output_config.lower():
            media_type = 'audio'
        elif '3d' in output_config.lower():
            media_type = '3d'
        else:
            media_type = 'image'

        # Create recorder if not provided
        from config import JSON_STORAGE_DIR, STAGE3_MODEL
        if recorder is None:
            recorder = get_recorder(
                run_id=run_id,
                config_name=output_config,
                safety_level=safety_level,
                device_id=device_id,
                base_path=JSON_STORAGE_DIR
            )

        # Track LLM models used
        if 'models_used' not in recorder.metadata:
            recorder.metadata['models_used'] = {}
        recorder.metadata['models_used']['stage4_output'] = output_config
        recorder._save_metadata()

        # Save context entities
        if input_text:
            recorder.save_entity('input', input_text)
        if context_prompt:
            recorder.save_entity('context_prompt', context_prompt)
        if interception_result:
            recorder.save_entity('interception', interception_result)
        if interception_config:
            recorder.metadata['interception_config'] = interception_config

        # Save the prompt being used for generation
        recorder.save_entity('generation_prompt', prompt)

        # Generate seed if not provided
        if seed is None:
            seed = random.randint(0, 2147483647)
            logger.info(f"[STAGE4-GEN] Generated random seed: {seed}")
        else:
            logger.info(f"[STAGE4-GEN] Using provided seed: {seed}")

        # Build custom params
        custom_params = {}
        if alpha_factor is not None:
            custom_params['alpha_factor'] = alpha_factor

        # Session 151: Add generation parameters (gracefully ignored if not in config's input_mappings)
        if width is not None:
            custom_params['width'] = width
        if height is not None:
            custom_params['height'] = height
        if steps is not None:
            custom_params['steps'] = steps
        if cfg is not None:
            custom_params['cfg'] = cfg
        if negative_prompt is not None:
            custom_params['negative_prompt'] = negative_prompt
        if sampler_name is not None:
            custom_params['sampler_name'] = sampler_name
        if scheduler is not None:
            custom_params['scheduler'] = scheduler
        if denoise is not None:
            custom_params['denoise'] = denoise
        # Secondary text input (Canvas dual-input: tags for HeartMuLa, lyrics for ACENet, negative prompt for images)
        if secondary_text is not None:
            custom_params['TEXT_2'] = secondary_text
            custom_params['secondary_text'] = secondary_text

        # Extract LoRAs from interception config
        if interception_config:
            try:
                interception_cfg = pipeline_executor.config_loader.get_config(interception_config)
                if interception_cfg and hasattr(interception_cfg, 'meta') and interception_cfg.meta:
                    config_loras = interception_cfg.meta.get('loras', [])
                    if config_loras:
                        custom_params['loras'] = config_loras
                        logger.info(f"[STAGE4-GEN] Extracted {len(config_loras)} LoRA(s) from '{interception_config}'")
            except Exception as e:
                logger.warning(f"[STAGE4-GEN] Could not load config '{interception_config}': {e}")

        # Create context override if we have custom params
        from schemas.engine.pipeline_executor import PipelineContext
        context_override = None
        if custom_params:
            context_override = PipelineContext(input_text=prompt, user_input=prompt)
            context_override.custom_placeholders = custom_params

        logger.info(f"[STAGE4-GEN] Executing generation with config '{output_config}', prompt: {prompt[:100]}...")

        # Execute the generation pipeline
        output_result = await pipeline_executor.execute_pipeline(
            config_name=output_config,
            input_text=prompt,
            user_input=prompt,
            context_override=context_override,
            seed_override=seed,
            input_image=input_image,
            input_image1=input_image1,
            input_image2=input_image2,
            input_image3=input_image3,
            alpha_factor=alpha_factor
        )

        if not output_result.success:
            return {
                'success': False,
                'error': output_result.error or 'Generation failed',
                'run_id': run_id
            }

        # Process output based on type
        output_value = output_result.final_output
        _meta_seed = output_result.metadata.get('seed')
        result_seed = _meta_seed if _meta_seed is not None else seed

        # Cloud APIs don't support seeds — don't pretend they do
        config_obj = pipeline_executor.config_loader.get_config(output_config)
        backend_type = (config_obj.meta.get('backend_type', 'comfyui')
                        if config_obj and config_obj.meta else 'comfyui')
        if backend_type in ('openai', 'openrouter'):
            result_seed = None

        # Handle different output types
        if media_type == 'code':
            # Code output (P5.js, Tone.js, etc.)
            # Determine entity type and route based on output config
            if 'tonejs' in output_config.lower():
                code_entity_type = 'tonejs'
                code_route = f'/api/media/tonejs/{run_id}'
            else:
                code_entity_type = 'p5'
                code_route = f'/api/media/p5/{run_id}'

            if output_value and len(output_value) > 0:
                saved_filename = recorder.save_entity(
                    entity_type=code_entity_type,
                    content=output_value.encode('utf-8'),
                    metadata={'config': output_config, 'seed': result_seed, 'format': 'js'}
                )
                media_output = {
                    'media_type': 'code',
                    'url': code_route,
                    'code': output_value,
                    'run_id': run_id,
                    'seed': result_seed
                }
            else:
                return {
                    'success': False,
                    'error': 'Code generation failed',
                    'run_id': run_id
                }

        elif output_value in ('comfyui_generated', 'comfyui_direct_generated'):
            # ComfyUI Direct (WebSocket) — media bytes already in metadata
            media_files_data = output_result.metadata.get('media_files', [])
            outputs_meta = output_result.metadata.get('outputs_metadata', [])
            for idx, file_data in enumerate(media_files_data):
                file_meta = outputs_meta[idx] if idx < len(outputs_meta) else {}
                original_filename = file_meta.get('filename', '')
                file_format = original_filename.split('.')[-1] if '.' in original_filename else 'png'
                saved_filename = recorder.save_entity(
                    entity_type=f'output_{media_type}',
                    content=file_data,
                    metadata={
                        'config': output_config,
                        'seed': result_seed,
                        'format': file_format,
                        'backend': 'comfyui_direct',
                        'node_id': file_meta.get('node_id', 'unknown'),
                        'file_index': idx,
                        'total_files': len(media_files_data)
                    }
                )
            media_entities = [e for e in recorder.metadata.get('entities', []) if e.get('type') == f'output_{media_type}']
            media_index = len(media_entities) - 1 if media_entities else 0
            media_output = {
                'media_type': media_type,
                'url': f'/api/media/{media_type}/{run_id}/{media_index}',
                'run_id': run_id,
                'index': media_index,
                'seed': result_seed
            }

        elif output_value == 'diffusers_generated':
            # Session 150: Diffusers backend - image data is base64 encoded
            image_data_b64 = output_result.metadata.get('image_data')
            if image_data_b64:
                import base64
                image_bytes = base64.b64decode(image_data_b64)
                logger.info(f"[RECORDER] Saving Diffusers image: {len(image_bytes)} bytes")
                saved_filename = recorder.save_entity(
                    entity_type=f'output_{media_type}',
                    content=image_bytes,
                    metadata={
                        'config': output_config,
                        'backend': 'diffusers',
                        'model': output_result.metadata.get('model_id', 'unknown'),
                        'seed': result_seed
                    }
                )
                logger.info(f"[RECORDER] Diffusers image saved: {saved_filename}")
                media_entities = [e for e in recorder.metadata.get('entities', []) if e.get('type') == f'output_{media_type}']
                media_index = len(media_entities) - 1 if media_entities else 0
                media_output = {
                    'media_type': media_type,
                    'url': f'/api/media/{media_type}/{run_id}/{media_index}',
                    'run_id': run_id,
                    'index': media_index,
                    'seed': result_seed
                }
            else:
                return {
                    'success': False,
                    'error': 'Diffusers: No image_data in response',
                    'run_id': run_id
                }

        elif output_value in ('heartmula_generated', 'stable_audio_generated'):
            # Audio backend (HeartMuLa, Stable Audio) - audio data is base64 encoded
            audio_backend = output_result.metadata.get('backend', 'unknown')
            audio_data_b64 = output_result.metadata.get('audio_data')
            if audio_data_b64:
                import base64
                audio_bytes = base64.b64decode(audio_data_b64)
                logger.info(f"[RECORDER] Saving {audio_backend} audio: {len(audio_bytes)} bytes")
                saved_filename = recorder.save_entity(
                    entity_type=f'output_{media_type}',
                    content=audio_bytes,
                    metadata={
                        'config': output_config,
                        'backend': audio_backend,
                        'format': output_result.metadata.get('audio_format', 'mp3'),
                        'seed': result_seed
                    }
                )
                logger.info(f"[RECORDER] {audio_backend} audio saved: {saved_filename}")
                media_entities = [e for e in recorder.metadata.get('entities', []) if e.get('type') == f'output_{media_type}']
                media_index = len(media_entities) - 1 if media_entities else 0
                media_output = {
                    'media_type': media_type,
                    'url': f'/api/media/{media_type}/{run_id}/{media_index}',
                    'run_id': run_id,
                    'index': media_index,
                    'seed': result_seed
                }
            else:
                return {
                    'success': False,
                    'error': f'{audio_backend}: No audio_data in response',
                    'run_id': run_id
                }

        elif output_result.metadata.get('chunk_type') == 'python' and output_result.metadata.get('video_data'):
            # Python chunk video output (e.g. Wan 2.1 via Diffusers)
            import base64
            video_data_b64 = output_result.metadata['video_data']
            video_bytes = base64.b64decode(video_data_b64)
            video_format = output_result.metadata.get('video_format', 'mp4')
            logger.info(f"[RECORDER] Saving Python chunk video: {len(video_bytes)} bytes ({video_format})")
            saved_filename = recorder.save_entity(
                entity_type='output_video',
                content=video_bytes,
                metadata={
                    'config': output_config,
                    'backend': output_result.metadata.get('backend', 'diffusers'),
                    'media_type': 'video',
                    'seed': result_seed,
                    'size_bytes': len(video_bytes),
                    'format': video_format
                }
            )
            logger.info(f"[RECORDER] Video saved: {saved_filename}")
            media_entities = [e for e in recorder.metadata.get('entities', []) if e.get('type') == 'output_video']
            media_index = len(media_entities) - 1 if media_entities else 0
            media_output = {
                'media_type': 'video',
                'url': f'/api/media/video/{run_id}/{media_index}',
                'run_id': run_id,
                'index': media_index,
                'seed': result_seed
            }

        elif output_value == 'hunyuan3d_generated':
            # Hunyuan3D-2 3D mesh generation — saves GLB mesh + optional PNG thumbnail
            import base64
            mesh_data_b64 = output_result.metadata.get('mesh_data')
            if mesh_data_b64:
                mesh_bytes = base64.b64decode(mesh_data_b64)
                logger.info(f"[RECORDER] Saving Hunyuan3D mesh: {len(mesh_bytes)} bytes")

                # Save GLB mesh as output_3d entity
                saved_filename = recorder.save_entity(
                    entity_type='output_3d',
                    content=mesh_bytes,
                    metadata={
                        'config': output_config,
                        'backend': 'hunyuan3d',
                        'format': 'glb',
                        'seed': result_seed,
                        'size_bytes': len(mesh_bytes),
                    }
                )
                logger.info(f"[RECORDER] Hunyuan3D mesh saved: {saved_filename}")

                # Also save Blender-rendered thumbnail if available
                image_data_b64 = output_result.metadata.get('image_data')
                if image_data_b64:
                    thumbnail_bytes = base64.b64decode(image_data_b64)
                    recorder.save_entity(
                        entity_type='output_image',
                        content=thumbnail_bytes,
                        metadata={
                            'config': output_config,
                            'backend': 'blender_preview',
                            'format': 'png',
                            'seed': result_seed,
                        }
                    )
                    logger.info(f"[RECORDER] Blender thumbnail saved")

                media_entities = [e for e in recorder.metadata.get('entities', []) if e.get('type') == 'output_3d']
                media_index = len(media_entities) - 1 if media_entities else 0

                # Response includes both 3D mesh URL and optional thumbnail URL
                media_output = {
                    'media_type': '3d',
                    'url': f'/api/media/3d/{run_id}',
                    'mesh_url': f'/api/media/3d/{run_id}',
                    'run_id': run_id,
                    'index': media_index,
                    'seed': result_seed,
                }

                # Add thumbnail URL if Blender render was successful
                if image_data_b64:
                    image_entities = [e for e in recorder.metadata.get('entities', []) if e.get('type') == 'output_image']
                    thumb_index = len(image_entities) - 1 if image_entities else 0
                    media_output['thumbnail_url'] = f'/api/media/image/{run_id}/{thumb_index}'
            else:
                return {
                    'success': False,
                    'error': 'Hunyuan3D: No mesh_data in response',
                    'run_id': run_id
                }

        elif output_value == 'workflow_generated':
            # ComfyUI workflow
            filesystem_path = output_result.metadata.get('filesystem_path')
            media_files = output_result.metadata.get('media_files', [])

            if filesystem_path:
                # New workflow system: read file directly from filesystem
                import os
                if os.path.exists(filesystem_path):
                    with open(filesystem_path, 'rb') as f:
                        file_data = f.read()
                    file_format = filesystem_path.split('.')[-1] if '.' in filesystem_path else 'png'
                    saved_filename = recorder.save_entity(
                        entity_type=f'output_{media_type}',
                        content=file_data,
                        metadata={
                            'config': output_config,
                            'seed': result_seed,
                            'format': file_format,
                            'source_path': filesystem_path
                        }
                    )
                    logger.info(f"[STAGE4-GEN] Saved from filesystem: {saved_filename}")
            elif media_files:
                # Legacy: binary data in metadata
                outputs_metadata = output_result.metadata.get('outputs_metadata', [])
                for idx, file_data in enumerate(media_files):
                    file_meta = outputs_metadata[idx] if idx < len(outputs_metadata) else {}
                    entity_type = f'output_{media_type}'
                    original_filename = file_meta.get('filename', '')
                    file_format = original_filename.split('.')[-1] if '.' in original_filename else 'png'
                    saved_filename = recorder.save_entity(
                        entity_type=entity_type,
                        content=file_data,
                        metadata={
                            'config': output_config,
                            'seed': result_seed,
                            'format': file_format,
                            'node_id': file_meta.get('node_id', 'unknown'),
                            'file_index': idx,
                            'total_files': len(media_files)
                        }
                    )

            media_entities = [e for e in recorder.metadata.get('entities', []) if e.get('type') == f'output_{media_type}']
            media_index = len(media_entities) - 1 if media_entities else 0
            media_output = {
                'media_type': media_type,
                'url': f'/api/media/{media_type}/{run_id}/{media_index}',
                'run_id': run_id,
                'index': media_index,
                'seed': result_seed
            }

        else:
            # Direct output (OpenAI, Gemini, etc.)
            if output_value and output_value.startswith(('http://', 'https://')):
                # URL output - download and save
                saved_filename = await recorder.download_and_save_from_url(
                    url=output_value,
                    media_type=media_type,
                    config=output_config,
                    seed=result_seed
                )
            elif output_value and len(output_value) > 100:
                # Likely base64 data - decode and save
                import base64
                try:
                    if output_value.startswith('data:'):
                        output_value = output_value.split(',', 1)[1]
                    file_data = base64.b64decode(output_value)
                    file_format = 'png'
                    saved_filename = recorder.save_entity(
                        entity_type=f'output_{media_type}',
                        content=file_data,
                        metadata={
                            'config': output_config,
                            'seed': result_seed,
                            'format': file_format,
                            'source': 'base64'
                        }
                    )
                except Exception as e:
                    logger.error(f"[STAGE4-GEN] Failed to decode base64: {e}")

            media_entities = [e for e in recorder.metadata.get('entities', []) if e.get('type') == f'output_{media_type}']
            media_index = len(media_entities) - 1 if media_entities else 0
            media_output = {
                'media_type': media_type,
                'url': f'/api/media/{media_type}/{run_id}/{media_index}',
                'run_id': run_id,
                'index': media_index,
                'seed': result_seed
            }

        logger.info(f"[STAGE4-GEN] Success: {media_output['url']}")

        return {
            'success': True,
            'media_output': media_output,
            'run_id': run_id,
            'loras': custom_params.get('loras', [])
        }

    except Exception as e:
        logger.error(f"[STAGE4-GEN] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'run_id': run_id if run_id else 'unknown'
        }


async def execute_generation_stage4(
    prompt: str,
    output_config: str,
    safety_level: str,
    seed: int = None,
    recorder = None,
    run_id: str = None,
    device_id: str = None,
    input_text: str = '',
    context_prompt: str = '',
    interception_result: str = '',
    interception_config: str = '',
    input_image: str = None,
    input_image1: str = None,
    input_image2: str = None,
    input_image3: str = None,
    alpha_factor = None,
    skip_stage3: bool = False,
    user_language: str = 'de',
    **kwargs
):
    """
    Execute Stage 3 (Safety+Translation) + Stage 4 (Generation).

    Legacy function for Lab workflows - orchestrates Stage 3 before calling
    execute_stage4_generation_only().

    Session 136: Refactored to use execute_stage4_generation_only() internally.
    Canvas workflows should call execute_stage4_generation_only() directly.

    Args:
        prompt: Input prompt for generation (German or English)
        output_config: Config ID (e.g., 'sd35_large')
        safety_level: 'kids', 'youth', 'adult', or 'research'
        seed: Optional seed (generates random if None)
        recorder: Optional LivePipelineRecorder instance (creates new if None)
        run_id: Optional run_id (creates new if None)
        device_id: Optional device_id for folder structure
        input_text: Original user input (for recorder)
        context_prompt: Meta-prompt used (for recorder)
        interception_result: Interception output (for recorder)
        interception_config: Interception config ID (for LoRA extraction)
        input_image: Path to input image for img2img
        input_image1/2/3: Paths for multi-image workflows
        alpha_factor: Alpha factor for Surrealizer
        skip_stage3: If True, skip Stage 3 (translation+safety) - prompt is already ready
        **kwargs: Additional params

    Returns:
        {
            'success': bool,
            'media_output': {
                'media_type': 'image',
                'url': '/api/media/image/run_xxx/0',
                'run_id': 'run_xxx',
                'index': 0,
                'seed': 123456
            },
            'run_id': str,
            'error': Optional[str],
            'blocked': Optional[bool]  # True if safety check failed
        }
    """
    import time

    try:
        # Initialize schema engine if needed
        if pipeline_executor is None:
            init_schema_engine()

        # Generate run_id if not provided
        if run_id is None:
            run_id = generate_run_id()

        # Generate device_id if not provided
        if device_id is None:
            device_id = f"api_{uuid.uuid4().hex[:12]}"

        # Determine media type from output config
        if 'code' in output_config.lower() or 'p5js' in output_config.lower() or 'tonejs' in output_config.lower():
            media_type = 'code'
        elif 'video' in output_config.lower():
            media_type = 'video'
        elif 'audio' in output_config.lower() or 'music' in output_config.lower() or 'ace' in output_config.lower():
            media_type = 'audio'
        elif '3d' in output_config.lower():
            media_type = '3d'
        else:
            media_type = 'image'

        # ====================================================================
        # STAGE 3: TRANSLATION + PRE-OUTPUT SAFETY
        # ====================================================================
        if skip_stage3:
            # Prompt is already translated/ready - skip Stage 3
            translated_prompt = prompt
            logger.info(f"[STAGE3+4] Stage 3 SKIPPED (skip_stage3=True): {translated_prompt[:100]}...")
        else:
            logger.info(f"[STAGE3+4] Stage 3: Translation + Safety (level: {safety_level})")

            safety_result = await execute_stage3_safety(
                prompt,
                safety_level,
                media_type,
                pipeline_executor,
                user_language=user_language
            )

            if not safety_result['safe']:
                logger.warning(f"[STAGE3+4] Stage 3 BLOCKED")
                return {
                    'success': False,
                    'blocked': True,
                    'error': safety_result.get('abort_reason', 'Content blocked by safety check'),
                    'found_terms': safety_result.get('found_terms', []),
                    'run_id': run_id
                }

            # Get translated prompt (English) for media generation
            translated_prompt = safety_result.get('positive_prompt', prompt)
            logger.info(f"[STAGE3+4] Stage 3 PASSED, translated: {translated_prompt[:100]}...")

        # Save original prompt for metadata (before translation)
        from config import JSON_STORAGE_DIR, STAGE3_MODEL
        if recorder is None:
            recorder = get_recorder(
                run_id=run_id,
                config_name=output_config,
                safety_level=safety_level,
                device_id=device_id,
                base_path=JSON_STORAGE_DIR
            )

        # Track Stage 3 model usage
        if 'models_used' not in recorder.metadata:
            recorder.metadata['models_used'] = {}
        if not skip_stage3:
            recorder.metadata['models_used']['stage3_safety'] = STAGE3_MODEL
        recorder._save_metadata()

        # Save optimized/final prompt (German, before translation)
        recorder.save_entity('optimized_prompt', prompt)

        # Save translation (English, for media generation)
        # Track if translation actually occurred (for frontend badge)
        was_translated = translated_prompt and translated_prompt != prompt
        if was_translated:
            recorder.save_entity('translation_en', translated_prompt)

        # ====================================================================
        # STAGE 4: GENERATION (via clean function)
        # ====================================================================
        stage4_result = await execute_stage4_generation_only(
            prompt=translated_prompt,
            output_config=output_config,
            safety_level=safety_level,
            run_id=run_id,
            seed=seed,
            recorder=recorder,
            device_id=device_id,
            input_text=input_text,
            context_prompt=context_prompt,
            interception_result=interception_result,
            interception_config=interception_config,
            input_image=input_image,
            input_image1=input_image1,
            input_image2=input_image2,
            input_image3=input_image3,
            alpha_factor=alpha_factor,
            # Session 155: Parameter Injection aus kwargs
            width=kwargs.get('width'),
            height=kwargs.get('height'),
            steps=kwargs.get('steps'),
            cfg=kwargs.get('cfg')
        )

        # Add was_translated flag to result for frontend badge display
        if stage4_result.get('success'):
            stage4_result['was_translated'] = was_translated
        return stage4_result

    except Exception as e:
        logger.error(f"[STAGE3+4] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'run_id': run_id if run_id else 'unknown'
        }


@schema_bp.route('/pipeline/legacy', methods=['POST'])
def legacy_workflow():
    """
    Legacy workflow endpoint - Direct ComfyUI workflow execution WITH Stage 1 Safety.

    Lab Architecture: For workflows that bypass interception/optimization.
    Used by Surrealizer, Split&Combine, Partial Elimination, etc.

    Flow: Stage 1 (Safety) → ComfyUI Workflow (no Stage 2/3)

    Request Body:
    {
        "prompt": "User input (will be injected into workflow)",
        "output_config": "surrealization_legacy",
        "seed": 123456,
        "alpha_factor": 0,  # Surrealizer-specific
        "safety_level": "youth"  # controlled by backend config.DEFAULT_SAFETY_LEVEL
    }
    """
    import time
    import uuid

    start_time = time.time()

    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'error': 'JSON-Request erwartet'}), 400

        prompt = data.get('prompt', '')
        output_config = data.get('output_config')
        seed = data.get('seed')
        alpha_factor = data.get('alpha_factor')
        expand_prompt = data.get('expand_prompt', False)
        safety_level = config.DEFAULT_SAFETY_LEVEL
        user_language = data.get('user_language', 'de')

        # Surrealizer-specific parameters
        negative_prompt = data.get('negative_prompt')
        cfg = data.get('cfg')
        fusion_strategy = data.get('fusion_strategy')

        # Feature probing parameters
        prompt_b = data.get('prompt_b')
        probing_encoder = data.get('probing_encoder')
        transfer_dims = data.get('transfer_dims')

        # Concept algebra parameters
        prompt_c = data.get('prompt_c')
        algebra_encoder = data.get('algebra_encoder')
        scale_sub = data.get('scale_sub')
        scale_add = data.get('scale_add')

        # Additional workflow-specific parameters
        mode = data.get('mode')  # For partial_elimination
        prompt1 = data.get('prompt1')  # For split_and_combine
        prompt2 = data.get('prompt2')  # For split_and_combine
        combination_type = data.get('combination_type')  # For split_and_combine
        encoder_type = data.get('encoder_type')  # For partial_elimination: 'triple', 'clip_g', 't5xxl'
        # Partial elimination dimension parameters (calculated by frontend)
        inner_start = data.get('inner_start')
        inner_num = data.get('inner_num')
        outer_1_start = data.get('outer_1_start')
        outer_1_num = data.get('outer_1_num')
        outer_2_start = data.get('outer_2_start')
        outer_2_num = data.get('outer_2_num')

        if not prompt or not output_config:
            return jsonify({'status': 'error', 'error': 'prompt und output_config sind erforderlich'}), 400

        logger.info(f"[LEGACY-ENDPOINT] Starting for config '{output_config}'")

        if pipeline_executor is None:
            init_schema_engine()

        # ====================================================================
        # STAGE 1: SAFETY CHECK (Server responsibility, always runs)
        # ====================================================================
        logger.info(f"[LEGACY-ENDPOINT] Stage 1: Safety check (level: {safety_level})")

        is_safe, checked_text, error_message, checks_passed = asyncio.run(execute_stage1_safety_unified(
            prompt,
            safety_level,
            pipeline_executor,
            user_language=user_language
        ))

        if not is_safe:
            logger.warning(f"[LEGACY-ENDPOINT] Stage 1 BLOCKED: {error_message}")
            return jsonify({
                'status': 'blocked',
                'stage': 1,
                'reason': error_message,
                'checks_passed': checks_passed
            }), 403

        logger.info(f"[LEGACY-ENDPOINT] Stage 1 PASSED")

        # ====================================================================
        # T5 PROMPT EXPANSION (optional, user-controlled)
        # ====================================================================
        t5_prompt = None
        if expand_prompt:
            try:
                from schemas.engine.prompt_interception_engine import (
                    PromptInterceptionEngine, PromptInterceptionRequest
                )
                T5_EXPANSION_INSTRUCTION = (
                    "Expand this prompt into a rich narrative paragraph (~200 words). "
                    "Add: mood, atmosphere, sensory details, emotional depth, spatial context, associations. "
                    "Do NOT repeat the original prompt — only add new content that enriches and deepens it. "
                    "Write in the same language as the input. Output ONLY the expansion text, nothing else."
                )
                engine = PromptInterceptionEngine()
                pi_request = PromptInterceptionRequest(
                    input_prompt=prompt,
                    input_context='',
                    style_prompt=T5_EXPANSION_INSTRUCTION,
                    task_instruction='',
                    model=config.STAGE2_INTERCEPTION_MODEL,
                    debug=False
                )
                pi_response = asyncio.run(engine.process_request(pi_request))
                if pi_response.success and pi_response.output_str:
                    t5_prompt = prompt + " " + pi_response.output_str.strip()
                    logger.info(f"[LEGACY-ENDPOINT] T5 expansion: {len(prompt)} → {len(t5_prompt)} chars")
                else:
                    logger.warning(f"[LEGACY-ENDPOINT] T5 expansion failed, using original: {pi_response.error}")
            except Exception as e:
                logger.warning(f"[LEGACY-ENDPOINT] T5 expansion error (fail-open): {e}")

        # Generate run_id
        run_id = generate_run_id()

        # Initialize recorder
        from config import JSON_STORAGE_DIR
        recorder = get_recorder(
            run_id=run_id,
            config_name=output_config,
            safety_level=safety_level,
            base_path=JSON_STORAGE_DIR
        )

        # Save input text as entity (needed for favorites restore)
        recorder.save_entity(
            entity_type='input',
            content=prompt,
            metadata={'source': 'legacy_endpoint'}
        )

        # Store workflow parameters in current_state for restore
        recorder.metadata['current_state'].update({
            'alpha_factor': alpha_factor,
            'negative_prompt': negative_prompt,
            'cfg': cfg,
            'expand_prompt': expand_prompt,
            'output_config': output_config,
        })
        recorder._save_metadata()

        # Seed logic
        import random
        if seed is None:
            seed = random.randint(0, 2147483647)

        # Build custom params for workflow injection
        custom_params = {}
        if t5_prompt is not None:
            custom_params['t5_prompt'] = t5_prompt
        if alpha_factor is not None:
            custom_params['alpha_factor'] = alpha_factor
        if fusion_strategy is not None:
            custom_params['fusion_strategy'] = fusion_strategy
        if negative_prompt is not None:
            custom_params['negative_prompt'] = negative_prompt
        if cfg is not None:
            custom_params['cfg'] = cfg
        if mode is not None:
            custom_params['mode'] = mode
        if prompt1 is not None:
            custom_params['prompt1'] = prompt1
        if prompt2 is not None:
            custom_params['prompt2'] = prompt2
        if combination_type is not None:
            custom_params['combination_type'] = combination_type
        # Partial elimination dimension parameters
        if inner_start is not None:
            custom_params['inner_start'] = inner_start
        if inner_num is not None:
            custom_params['inner_num'] = inner_num
        if outer_1_start is not None:
            custom_params['outer_1_start'] = outer_1_start
        if outer_1_num is not None:
            custom_params['outer_1_num'] = outer_1_num
        if outer_2_start is not None:
            custom_params['outer_2_start'] = outer_2_start
        if outer_2_num is not None:
            custom_params['outer_2_num'] = outer_2_num
        if encoder_type is not None:
            custom_params['encoder_type'] = encoder_type
        # Feature probing parameters
        if prompt_b is not None:
            custom_params['prompt_b'] = prompt_b
        if probing_encoder is not None:
            custom_params['probing_encoder'] = probing_encoder
        if transfer_dims is not None:
            custom_params['transfer_dims'] = transfer_dims
        # Concept algebra parameters
        if prompt_c is not None:
            custom_params['prompt_c'] = prompt_c
        if algebra_encoder is not None:
            custom_params['algebra_encoder'] = algebra_encoder
        if scale_sub is not None:
            custom_params['scale_sub'] = scale_sub
        if scale_add is not None:
            custom_params['scale_add'] = scale_add

        from schemas.engine.pipeline_executor import PipelineContext
        context_override = None
        if custom_params:
            context_override = PipelineContext(input_text=prompt, user_input=prompt)
            context_override.custom_placeholders = custom_params
            logger.info(f"[LEGACY-ENDPOINT] Custom params: {list(custom_params.keys())}")

        # Execute legacy workflow directly
        output_result = asyncio.run(pipeline_executor.execute_pipeline(
            config_name=output_config,
            input_text=prompt,
            user_input=prompt,
            context_override=context_override,
            seed_override=seed,
            alpha_factor=alpha_factor
        ))

        if not output_result.success:
            return jsonify({
                'status': 'error',
                'error': output_result.error or 'Legacy workflow failed'
            }), 500

        # Handle legacy workflow output
        output_value = output_result.final_output
        _meta_seed = output_result.metadata.get('seed')
        result_seed = _meta_seed if _meta_seed is not None else seed

        if output_value == 'workflow_generated':
            # Legacy workflows return binary data directly in metadata
            media_files = output_result.metadata.get('media_files', [])
            outputs_metadata = output_result.metadata.get('outputs_metadata', [])
            media_type = output_result.metadata.get('media_type', 'image')
            workflow_json = output_result.metadata.get('workflow_json', {})

            # Extract SaveImage node titles for image labeling
            saveimage_titles = {}
            workflow_dict = workflow_json.get('workflow', workflow_json)
            for node_id, node_data in workflow_dict.items():
                if isinstance(node_data, dict) and node_data.get('class_type') == 'SaveImage':
                    title = node_data.get('_meta', {}).get('title', f'SaveImage_{node_id}')
                    saveimage_titles[node_id] = title
            if saveimage_titles:
                logger.info(f"[LEGACY-ENDPOINT] Extracted {len(saveimage_titles)} SaveImage titles: {list(saveimage_titles.values())}")

            if media_files:
                logger.info(f"[LEGACY-ENDPOINT] Saving {len(media_files)} media file(s)")
                for idx, file_data in enumerate(media_files):
                    # Get metadata for this file if available
                    file_meta = outputs_metadata[idx] if idx < len(outputs_metadata) else {}
                    entity_type = f'output_{media_type}'

                    # Determine format from filename or default
                    original_filename = file_meta.get('filename', '')
                    file_format = original_filename.split('.')[-1] if '.' in original_filename else 'png'

                    # Get node_id and lookup title
                    node_id = file_meta.get('node_id', 'unknown')
                    node_title = saveimage_titles.get(str(node_id), f'unknown_{node_id}')

                    saved_filename = recorder.save_entity(
                        entity_type=entity_type,
                        content=file_data,
                        metadata={
                            'config': output_config,
                            'seed': result_seed,
                            'format': file_format,
                            'node_id': node_id,
                            'node_title': node_title,
                            'file_index': idx,
                            'total_files': len(media_files)
                        }
                    )
                    logger.info(f"[LEGACY-ENDPOINT] Saved: {saved_filename} (title: {node_title})")

                # Create composite image if multiple outputs
                if len(media_files) > 1:
                    try:
                        logger.info(f"[LEGACY-ENDPOINT] Creating composite from {len(media_files)} images...")

                        # Use node_titles as labels (in order of outputs_metadata)
                        labels = []
                        for idx, file_meta in enumerate(outputs_metadata):
                            node_id = file_meta.get('node_id', 'unknown')
                            title = saveimage_titles.get(str(node_id), f'Image {idx+1}')
                            labels.append(title)

                        # Create composite
                        composite_data = recorder.create_composite_image(
                            image_data_list=media_files,
                            labels=labels,
                            workflow_title=output_config.replace('_', ' ').title()
                        )

                        # Save composite as new entity
                        composite_filename = recorder.save_entity(
                            entity_type='output_image_composite',
                            content=composite_data,
                            metadata={
                                'config': output_config,
                                'format': 'png',
                                'composite': True,
                                'seed': result_seed
                            }
                        )
                        logger.info(f"[LEGACY-ENDPOINT] Composite created: {composite_filename}")

                    except Exception as e:
                        logger.warning(f"[LEGACY-ENDPOINT] Composite failed: {e}")

        elif output_value == 'diffusers_generated':
            # Diffusers backend returns image data in metadata (Surrealizer, SD3.5 direct)
            image_data_b64 = output_result.metadata.get('image_data')
            if image_data_b64:
                import base64
                image_bytes = base64.b64decode(image_data_b64)
                recorder.save_entity(
                    entity_type='output_image',
                    content=image_bytes,
                    metadata={
                        'config': output_config,
                        'seed': result_seed,
                        'format': 'png',
                        'backend': 'diffusers'
                    }
                )
                logger.info(f"[LEGACY-ENDPOINT] Saved diffusers image: {len(image_bytes)} bytes")

        elif output_value == 'diffusers_attention_generated':
            # Latent Lab: Attention Cartography — image + attention maps
            image_data_b64 = output_result.metadata.get('image_data')
            if image_data_b64:
                import base64
                image_bytes = base64.b64decode(image_data_b64)
                recorder.save_entity(
                    entity_type='output_image',
                    content=image_bytes,
                    metadata={
                        'config': output_config,
                        'seed': result_seed,
                        'format': 'png',
                        'backend': 'diffusers_attention'
                    }
                )
                logger.info(f"[LEGACY-ENDPOINT] Saved attention cartography image: {len(image_bytes)} bytes")

        elif output_value == 'diffusers_probing_generated':
            # Latent Lab: Feature Probing — image + embedding analysis
            image_data_b64 = output_result.metadata.get('image_data')
            if image_data_b64:
                import base64
                image_bytes = base64.b64decode(image_data_b64)
                recorder.save_entity(
                    entity_type='output_image',
                    content=image_bytes,
                    metadata={
                        'config': output_config,
                        'seed': result_seed,
                        'format': 'png',
                        'backend': 'diffusers_probing'
                    }
                )
                logger.info(f"[LEGACY-ENDPOINT] Saved feature probing image: {len(image_bytes)} bytes")

        elif output_value == 'diffusers_algebra_generated':
            # Latent Lab: Concept Algebra — reference + result images
            result_image_b64 = output_result.metadata.get('result_image')
            if result_image_b64:
                import base64
                image_bytes = base64.b64decode(result_image_b64)
                recorder.save_entity(
                    entity_type='output_image',
                    content=image_bytes,
                    metadata={
                        'config': output_config,
                        'seed': result_seed,
                        'format': 'png',
                        'backend': 'diffusers_algebra'
                    }
                )
                logger.info(f"[LEGACY-ENDPOINT] Saved concept algebra image: {len(image_bytes)} bytes")

        elif output_value == 'diffusers_archaeology_generated':
            # Latent Lab: Denoising Archaeology — image + step snapshots
            image_data_b64 = output_result.metadata.get('image_data')
            if image_data_b64:
                import base64
                image_bytes = base64.b64decode(image_data_b64)
                recorder.save_entity(
                    entity_type='output_image',
                    content=image_bytes,
                    metadata={
                        'config': output_config,
                        'seed': result_seed,
                        'format': 'png',
                        'backend': 'diffusers_archaeology'
                    }
                )
                logger.info(f"[LEGACY-ENDPOINT] Saved denoising archaeology image: {len(image_bytes)} bytes")

        elif output_value == 'hunyuan3d_generated':
            # Hunyuan3D-2 3D mesh generation
            mesh_data_b64 = output_result.metadata.get('mesh_data')
            if mesh_data_b64:
                import base64
                mesh_bytes = base64.b64decode(mesh_data_b64)
                recorder.save_entity(
                    entity_type='output_3d',
                    content=mesh_bytes,
                    metadata={
                        'config': output_config,
                        'seed': result_seed,
                        'format': 'glb',
                        'backend': 'hunyuan3d'
                    }
                )
                logger.info(f"[LEGACY-ENDPOINT] Saved Hunyuan3D mesh: {len(mesh_bytes)} bytes")

                # Also save Blender thumbnail if available
                image_data_b64 = output_result.metadata.get('image_data')
                if image_data_b64:
                    thumbnail_bytes = base64.b64decode(image_data_b64)
                    recorder.save_entity(
                        entity_type='output_image',
                        content=thumbnail_bytes,
                        metadata={
                            'config': output_config,
                            'backend': 'blender_preview',
                            'format': 'png',
                            'seed': result_seed,
                        }
                    )

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"[LEGACY-ENDPOINT] Success in {duration_ms:.0f}ms")

        # Determine media_type from workflow metadata (set in backend_router from chunk definition)
        response_media_type = output_result.metadata.get('media_type', 'image') if output_result.metadata else 'image'
        response_data = {
            'status': 'success',
            'media_output': {
                'media_type': response_media_type,
                'url': f'/api/media/{response_media_type}/{run_id}',
                'run_id': run_id,
                'seed': result_seed
            },
            'run_id': run_id,
            'duration_ms': duration_ms
        }
        if t5_prompt is not None:
            response_data['t5_expansion'] = t5_prompt

        # Latent Lab: Include attention data + image_base64 in response
        attention_data = output_result.metadata.get('attention_data') if output_result.metadata else None
        if attention_data:
            # Include image_base64 directly so frontend doesn't need a separate media fetch
            image_b64 = output_result.metadata.get('image_data')
            if image_b64:
                attention_data['image_base64'] = image_b64
            response_data['attention_data'] = attention_data

        # Latent Lab: Include probing data + image_base64 in response
        probing_data = output_result.metadata.get('probing_data') if output_result.metadata else None
        if probing_data:
            image_b64 = output_result.metadata.get('image_data')
            if image_b64:
                probing_data['image_base64'] = image_b64
            response_data['probing_data'] = probing_data

        # Latent Lab: Include algebra data (reference + result images) in response
        algebra_data = output_result.metadata.get('algebra_data') if output_result.metadata else None
        if algebra_data:
            reference_b64 = output_result.metadata.get('reference_image')
            result_b64 = output_result.metadata.get('result_image')
            if reference_b64:
                algebra_data['reference_image'] = reference_b64
            if result_b64:
                algebra_data['result_image'] = result_b64
            algebra_data['seed'] = result_seed
            response_data['algebra_data'] = algebra_data

        # Latent Lab: Include archaeology data + image_base64 in response
        archaeology_data = output_result.metadata.get('archaeology_data') if output_result.metadata else None
        if archaeology_data:
            image_b64 = output_result.metadata.get('image_data')
            if image_b64:
                archaeology_data['image_base64'] = image_b64
            response_data['archaeology_data'] = archaeology_data

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"[LEGACY-ENDPOINT] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(e)}), 500


@schema_bp.route('/pipeline/interception', methods=['POST', 'GET'])
def interception_pipeline():
    """Stage 1 (Safety) + Stage 2 (Interception) - Lab Architecture atomic service"""
    # Phase 4: Declare global state at function start
    global _last_prompt, _last_seed, _last_output_config
    import random

    try:
        # Request-Validation: Support both POST (JSON) and GET (query params for EventSource)
        if request.method == 'GET':
            # EventSource uses GET with query params
            data = {
                'schema': request.args.get('schema'),
                'input_text': request.args.get('input_text'),
                'context_prompt': request.args.get('context_prompt', ''),
                'safety_level': request.args.get('safety_level', 'youth'),
                'enable_streaming': request.args.get('enable_streaming') == 'true',
                'device_id': request.args.get('device_id')  # Session 130: Fix missing device_id
            }
        else:
            # POST with JSON body
            data = request.get_json()
            if not data:
                return jsonify({
                    'status': 'error',
                    'error': 'JSON-Request erwartet'
                }), 400

        # Check if streaming mode is requested
        enable_streaming = data.get('enable_streaming', False)
        if enable_streaming:
            logger.info("[UNIFIED-STREAMING] Streaming mode requested")
            return Response(
                stream_with_context(execute_pipeline_streaming(data)),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no'
                }
            )

        from config import DEFAULT_SAFETY_LEVEL as _default_safety

        schema_name = data.get('schema')
        input_text = data.get('input_text')
        safety_level = _default_safety

        # Phase 2: Multilingual context editing support
        context_prompt = data.get('context_prompt')  # Optional: user-edited meta-prompt
        context_language = data.get('context_language', 'en')  # Language of context_prompt
        user_language = data.get('user_language', 'en')  # User's interface language

        # Media generation support
        output_config = data.get('output_config')  # Optional: specific output config for Stage 4 (e.g., 'sd35_large')

        # IMG2IMG support (Session 80)
        input_image = data.get('input_image')  # Optional: path to uploaded image for img2img

        # MULTI-IMAGE support (Session 86+)
        input_image1 = data.get('input_image1')  # Optional: path to first image for multi-image workflows
        input_image2 = data.get('input_image2')  # Optional: path to second image for multi-image workflows
        input_image3 = data.get('input_image3')  # Optional: path to third image for multi-image workflows

        # Stage 2 result support: use frontend-provided interception result
        interception_result = data.get('interception_result')  # Optional: frontend-provided Stage 2 output (if already executed)
        optimization_result = data.get('optimization_result')  # Optional: frontend-provided optimization output (code from Stage 2 optimization)

        # Fast regeneration support: skip Stage 1-3 with stage4_only flag
        stage4_only = data.get('stage4_only', False)  # Boolean: skip to Stage 4 (media generation) only
        seed_override = data.get('seed')  # Optional: specific seed for exact regeneration
        alpha_factor = data.get('alpha_factor')  # Optional: alpha factor for T5-CLIP fusion (Surrealizer)

        # Extract custom workflow parameters (split_and_combine, partial_elimination, surrealizer, etc.)
        # This ensures strict parallelization across all legacy workflows
        custom_params = {}
        logger.info(f"[EXTRACT-DEBUG] Request data keys: {list(data.keys())}")
        for param_name in ['prompt1', 'prompt2', 'combination_type', 'mode', 'alpha_factor',
                           'inner_start', 'inner_num', 'outer_1_start', 'outer_1_num', 'outer_2_start', 'outer_2_num']:
            if param_name in data:
                value = data.get(param_name)
                logger.info(f"[EXTRACT-DEBUG] Extracted {param_name} = {repr(value)}")
                custom_params[param_name] = value

        # CRITICAL FIX: Extract custom_placeholders for music generation (TEXT_1, TEXT_2)
        custom_placeholders = data.get('custom_placeholders', {})
        if custom_placeholders:
            logger.info(f"[CUSTOM-PLACEHOLDERS] Extracted: {list(custom_placeholders.keys())}")
            custom_params.update(custom_placeholders)

        if not schema_name or not input_text:
            return jsonify({
                'status': 'error',
                'error': 'Parameter "schema" and "input_text" erforderlich'
            }), 400

        # Schema-Engine initialisieren
        init_schema_engine()

        # Get config
        config = pipeline_executor.config_loader.get_config(schema_name)
        if not config:
            return jsonify({
                'status': 'error',
                'error': f'Config "{schema_name}" nicht gefunden'
            }), 404

        # Check if this is an output config (skip Stage 1-3 for output configs)
        is_output_config = config.meta.get('stage') == 'output'
        is_system_pipeline = config.meta.get('system_pipeline', False)

        # ====================================================================
        # SESSION 29: GENERATE UNIFIED RUN ID
        # ====================================================================
        # FIX: Generate ONE run_id used by ALL systems (not separate IDs)
        run_id = generate_run_id()
        logger.info(f"[RUN_ID] Generated unified run_id: {run_id} for {schema_name}")

        # ====================================================================
        # EXECUTION HISTORY TRACKER - DEPRECATED (Session 29)
        # ====================================================================
        # Session 29: Replaced ExecutionTracker with NoOpTracker
        # LivePipelineRecorder now handles all tracking responsibilities
        # Use locally-defined NoOpTracker class (defined at top of file)
        tracker = NoOpTracker()

        # Log pipeline start
        tracker.log_pipeline_start(
            input_text=input_text,
            metadata={'request_timestamp': data.get('timestamp')}
        )

        # ====================================================================
        # LIVE PIPELINE RECORDER - Single source of truth (Session 37 Migration)
        # ====================================================================
        from config import (
            JSON_STORAGE_DIR,
            STAGE1_TEXT_MODEL,
            STAGE2_INTERCEPTION_MODEL,
            STAGE3_MODEL
        )
        # Extract device_id from request (FIX: consistent folder structure)
        device_id = data.get('device_id')

        recorder = get_recorder(
            run_id=run_id,
            config_name=schema_name,
            safety_level=safety_level,
            device_id=device_id,  # FIX: Use device_id from request instead of hardcoded 'anonymous'
            base_path=JSON_STORAGE_DIR
        )
        recorder.set_state(0, "pipeline_starting")
        logger.info(f"[RECORDER] Initialized LivePipelineRecorder for run {run_id}")

        # Track LLM models used at each stage
        recorder.metadata['models_used'] = {
            'stage1_safety': STAGE1_TEXT_MODEL,
            'stage2_interception': STAGE2_INTERCEPTION_MODEL,
            'stage3_translation': STAGE3_MODEL
            # stage4_output will be added when output config is determined
        }
        recorder._save_metadata()

        # ====================================================================
        # PHASE 2: USER-EDITED CONTEXT HANDLING
        # ====================================================================
        # If user edited the meta-prompt (context) in Phase 2, handle translation
        # and save both language versions to exports
        modified_config = None

        if context_prompt:
            logger.info(f"[PHASE2] User edited context in language: {context_language}")

            # Save original language version
            recorder.save_entity(f'context_prompt_{context_language}', context_prompt)

            # Translate to English if needed
            context_prompt_en = context_prompt
            if context_language != 'en':
                logger.info(f"[PHASE2] Translating context from {context_language} to English...")

                from my_app.services.llm_backend import get_llm_backend
                from config import STAGE3_MODEL

                translation_prompt = f"Translate this educational text from {context_language} to English. Preserve pedagogical intent and technical terminology:\n\n{context_prompt}"

                try:
                    model = STAGE3_MODEL.replace("local/", "") if STAGE3_MODEL.startswith("local/") else STAGE3_MODEL
                    result = get_llm_backend().generate(model=model, prompt=translation_prompt)
                    translated = result.get("response", "").strip() if result else ""
                    if not translated:
                        logger.error("[PHASE2] Context translation failed, using original")
                        context_prompt_en = context_prompt
                    else:
                        context_prompt_en = translated
                        logger.info(f"[PHASE2] Context translated successfully")
                        # Save English version
                        recorder.save_entity('context_prompt_en', context_prompt_en)
                except Exception as e:
                    logger.error(f"[PHASE2] Context translation error: {e}")
                    context_prompt_en = context_prompt

            # Create modified config with user-edited context
            logger.info(f"[PHASE2] Creating modified config with user-edited context")

            from dataclasses import replace
            modified_config = replace(
                config,
                context=context_prompt_en,  # Use English version for pipeline
                meta={
                    **config.meta,
                    'user_edited': True,
                    'original_config': schema_name,
                    'user_language': user_language
                }
            )

            # Save modified config as first entity
            recorder.save_entity('config_used', modified_config.to_dict())
            logger.info(f"[RECORDER] Saved user-modified config")
        else:
            # Save original config (unmodified)
            recorder.save_entity('config_used', config.to_dict())
            logger.info(f"[RECORDER] Saved original config")

        # Use modified config for execution if available
        execution_config = modified_config if modified_config else config

        # ====================================================================
        # FAST REGENERATION: Skip Stage 1-3 if stage4_only=True
        # ====================================================================
        if stage4_only:
            logger.info(f"[FAST-REGEN] stage4_only=True: Skipping Stage 1-3, direct to Stage 4")
            # Create a mock result object for Stage 2 output
            class MockResult:
                def __init__(self, output):
                    self.success = True
                    self.final_output = output
                    self.error = None
                    self.steps = []
                    self.metadata = {}
                    self.execution_time = 0
            result = MockResult(input_text)  # input_text is already transformed text
            current_input = input_text
        else:
            # ====================================================================
            # STAGE 1: PRE-INTERCEPTION (Translation + Safety)
            # ====================================================================
            current_input = input_text

            if not is_system_pipeline and not is_output_config:
                logger.info(f"[4-STAGE] Stage 1: Pre-Interception for '{schema_name}'")
                tracker.set_stage(1)
                recorder.set_state(1, "translation_and_safety")

                # Log user input
                tracker.log_user_input_text(input_text)

                # SESSION 29: Save input entity
                recorder.save_entity('input', input_text)
                logger.info(f"[RECORDER] Saved input entity")

                # Stage 1: Safety Check (No Translation)
                # OLLAMA QUEUE: Wrap Stage 1 execution
                logger.info(f"[OLLAMA-QUEUE] Unified Pipeline: Waiting for queue slot...")
                with ollama_queue_semaphore:
                    logger.info(f"[OLLAMA-QUEUE] Unified Pipeline: Acquired slot, executing Stage 1")
                    is_safe, checked_text, error_message, checks_passed = asyncio.run(execute_stage1_safety_unified(
                        input_text,
                        safety_level,
                        pipeline_executor,
                        user_language=user_language
                    ))
                logger.info(f"[OLLAMA-QUEUE] Unified Pipeline: Released slot")

                current_input = checked_text

                if not is_safe:
                    logger.warning(f"[4-STAGE] Stage 1 BLOCKED by safety check")

                    # SESSION 29: Save checked text (even if blocked)
                    recorder.save_entity('stage1_output', checked_text)

                    # SESSION 29: Save safety error
                    recorder.save_error(
                        stage=1,
                        error_type='safety_blocked',
                        message=error_message,
                        details={'codes': ['§86a']}
                    )
                    logger.info(f"[RECORDER] Saved stage 1 blocked error")

                    # Log blocked event
                    tracker.log_stage1_blocked(
                        blocked_reason='§86a_violation',
                        blocked_codes=['§86a'],
                        error_message=error_message
                    )
                    tracker.finalize()  # Persist even though blocked

                    return jsonify({
                        'status': 'error',
                        'schema': schema_name,
                        'error': error_message,
                        'metadata': {
                            'stage': 'pre_interception',
                            'safety_codes': ['§86a'],  # Blocked by §86a StGB safety check
                            'checks_passed': checks_passed
                        }
                    }), 403

                # SESSION 29: Save stage1 output and safety results
                recorder.save_entity('stage1_output', checked_text)
                recorder.save_entity('safety', {
                    'safe': True,
                    'method': 'safety_check',
                    'codes_checked': ['§86a'],
                    'safety_level': safety_level
                })
                logger.info(f"[RECORDER] Saved stage1 output and safety entities")

                # Note: Stage 1 now only does safety check, no translation
                # Translation will be moved to Stage 3 (before media generation)

            # ====================================================================
            # STAGE 2: INTERCEPTION (Main Pipeline + Optimization)
            # ====================================================================
            tracker.set_stage(2)
            recorder.set_state(2, "interception")

            # Check if frontend already executed Stage 2 and provides result
            if interception_result or optimization_result:
                # For code output: use optimization_result (the code), not interception_result (scene description)
                # For image/audio: use interception_result (the prompt)
                stage2_output = optimization_result if optimization_result else interception_result
                logger.info(f"[4-STAGE] Stage 2: Using frontend-provided {'optimization_result (code)' if optimization_result else 'interception_result'} (already executed)")

                # Session 116: Extract LoRAs from config even when frontend provides result
                config_loras = execution_config.meta.get('loras', []) if hasattr(execution_config, 'meta') and execution_config.meta else []
                if config_loras:
                    logger.info(f"[STAGE2-LORA] Extracted {len(config_loras)} LoRA(s) from config '{schema_name}': {[l['name'] for l in config_loras]}")

                # Create mock result object to maintain interface compatibility
                class MockResult:
                    def __init__(self, output, loras=None):
                        self.success = True
                        self.final_output = output
                        self.error = None
                        self.steps = []
                        self.metadata = {'frontend_provided': True, 'has_optimization': bool(optimization_result)}
                        if loras:
                            self.metadata['loras'] = loras
                        self.execution_time = 0

                result = MockResult(stage2_output, loras=config_loras)
            else:
                # Check if pipeline has skip_stage2 flag (graceful check)
                pipeline_def = pipeline_executor.config_loader.get_pipeline(config.pipeline_name)
                skip_stage2 = pipeline_def.skip_stage2 if pipeline_def and hasattr(pipeline_def, 'skip_stage2') else False

                if skip_stage2:
                    logger.info(f"[4-STAGE] Stage 2: SKIPPED (pipeline '{config.pipeline_name}' has skip_stage2=true)")
                    logger.info(f"[4-STAGE] Stage 2: Passing Stage 1 output directly to Stage 3")

                    # Session 116: Extract LoRAs even when Stage 2 is skipped
                    config_loras = execution_config.meta.get('loras', []) if hasattr(execution_config, 'meta') and execution_config.meta else []
                    if config_loras:
                        logger.info(f"[STAGE2-LORA] Extracted {len(config_loras)} LoRA(s) from config '{schema_name}': {[l['name'] for l in config_loras]}")

                    # Create mock result - Stage 1 output passed through unchanged
                    class MockResult:
                        def __init__(self, output, loras=None):
                            self.success = True
                            self.final_output = output
                            self.error = None
                            self.steps = []
                            self.metadata = {'stage2_skipped': True, 'pipeline': config.pipeline_name}
                            if loras:
                                self.metadata['loras'] = loras
                            self.execution_time = 0

                    result = MockResult(current_input, loras=config_loras)
                else:
                    logger.info(f"[4-STAGE] Stage 2: Executing interception pipeline for '{schema_name}'")

                    # Use shared Stage 2 function (eliminates code duplication)
                    media_preferences = config.media_preferences if hasattr(config, 'media_preferences') else None
                    result = asyncio.run(execute_stage2_with_optimization(
                        schema_name=schema_name,
                        input_text=current_input,
                        config=execution_config,
                        safety_level=safety_level,
                        output_config=output_config,
                        media_preferences=media_preferences,
                        tracker=tracker,
                        user_input=data.get('user_input', input_text)
                    ))

            # Check if pipeline succeeded
            if not result.success:
                tracker.log_pipeline_error(
                    error_type='PipelineExecutionError',
                    error_message=result.error,
                    stage=2
                )
                tracker.finalize()

                return jsonify({
                    'status': 'error',
                    'schema': schema_name,
                    'error': result.error,
                    'steps_completed': len([s for s in result.steps if s.status.value == 'completed']),
                    'total_steps': len(result.steps)
                }), 500

            # Extract metadata from pipeline result
            model_used = None
            backend_type = None
            if result.steps and len(result.steps) > 0:
                # Get metadata from last successful step
                for step in reversed(result.steps):
                    if step.metadata:
                        model_used = step.metadata.get('model_used', model_used)
                        backend_type = step.metadata.get('backend_type', backend_type)
                        if model_used and backend_type:
                            break

            # Get actual total_iterations from result metadata (for recursive pipelines like Stille Post)
            total_iterations = result.metadata.get('iterations', 1) if result.metadata else 1

            # Log interception final result
            tracker.log_interception_final(
                final_text=result.final_output,
                total_iterations=total_iterations,
                config_used=schema_name,
                model_used=model_used,
                backend_type=backend_type,
                execution_time=result.execution_time
            )

            # SESSION 29: Save interception output
            recorder.save_entity('interception', result.final_output, metadata={
                'config': schema_name,
                'iterations': total_iterations,
                'model_used': model_used,
                'backend_type': backend_type
            })
            logger.info(f"[RECORDER] Saved interception entity")

        # ====================================================================
        # CONDITIONAL STAGE 3: Post-Interception Safety Check
        # ====================================================================
        # Only run Stage 3 if Stage 2 pipeline requires it (prompt_interception type)
        # Non-transformation pipelines (text_semantic_split, etc.) skip this

        pipeline_def = pipeline_executor.config_loader.get_pipeline(config.pipeline_name)
        requires_stage3 = pipeline_def.requires_interception_prompt if pipeline_def else True  # Default True for safety

        if requires_stage3 and safety_level != 'research' and isinstance(result.final_output, str):
            logger.info(f"[4-STAGE] Stage 3: Post-Interception Safety Check (pipeline requires it)")
            # TODO: Implement Stage 3 safety check on result.final_output here
            # For now, this is a placeholder - actual implementation in future session
        else:
            if not requires_stage3:
                pipeline_type = pipeline_def.pipeline_type if pipeline_def else 'unknown'
                logger.info(f"[4-STAGE] Stage 3: SKIPPED (pipeline_type={pipeline_type}, no transformation)")
            elif not isinstance(result.final_output, str):
                logger.info(f"[4-STAGE] Stage 3: SKIPPED (structured output, not text string)")

        # Response für erfolgreiche Pipeline
        response_data = {
            'status': 'success',
            'run_id': run_id,  # SESSION 30: Frontend needs run_id for status polling
            'schema': schema_name,
            'config_name': schema_name,  # Config name (same as schema for simple workflows)
            'input_text': input_text,
            'final_output': result.final_output,
            'steps_completed': len(result.steps),
            'execution_time': result.execution_time,
            'metadata': result.metadata
        }

        # ====================================================================
        # STAGE 3-4 LOOP: Multi-Output Support
        # ====================================================================
        media_preferences = config.media_preferences or {}
        default_output = media_preferences.get('default_output') if media_preferences else None
        output_configs = media_preferences.get('output_configs', [])

        # DEBUG: Log what we found
        logger.info(f"[DEBUG] media_preferences type: {type(media_preferences)}, value: {media_preferences}")
        logger.info(f"[DEBUG] default_output: {default_output}")
        logger.info(f"[DEBUG] output_configs: {output_configs}")
        logger.info(f"[DEBUG] output_config (from request): {output_config}")
        # Determine which output configs to use
        # Priority: 1) Request parameter, 2) Config output_configs array, 3) Config default_output
        if output_config:
            # HIGHEST PRIORITY: User directly selected output config from frontend
            logger.info(f"[USER-SELECTED] Using output_config from request: {output_config}")
            configs_to_execute = [output_config]
        elif output_configs:
            # Multi-Output: Use explicit output_configs array from config
            logger.info(f"[MULTI-OUTPUT] Config requests {len(output_configs)} outputs: {output_configs}")
            configs_to_execute = output_configs
        elif default_output and default_output != 'text':
            # Single-Output: Use lookup from default_output
            logger.info(f"[DEBUG] Calling lookup_output_config({default_output})")
            output_config_name = lookup_output_config(default_output)
            logger.info(f"[DEBUG] lookup returned: {output_config_name}")
            if output_config_name:
                configs_to_execute = [output_config_name]
            else:
                configs_to_execute = []
        else:
            # Text-only output
            logger.info(f"[DEBUG] No media output (default_output={default_output})")
            configs_to_execute = []

        logger.info(f"[DEBUG] configs_to_execute: {configs_to_execute}")

        # Execute Stage 3-4 for each output config
        media_outputs = []

        # CLIP-prompt detection: parse SD3.5 per-encoder prompts from Stage 2 output
        triple_prompt_data = _parse_triple_prompt(result.final_output) if isinstance(result.final_output, str) else None
        if triple_prompt_data:
            # T5 uses user's interception result directly (not LLM-optimized)
            interception_text = getattr(result, 'interception_result', None) or interception_result or result.final_output
            logger.info(f"[4-STAGE] CLIP-prompt detected — T5 will use interception result ({len(interception_text.split())}w)")

        if configs_to_execute and not is_system_pipeline and not is_output_config:
            logger.info(f"[4-STAGE] Stage 3-4 Loop: Processing {len(configs_to_execute)} output configs")

            for i, output_config_name in enumerate(configs_to_execute):
                logger.info(f"[4-STAGE] Stage 3-4 Loop iteration {i+1}/{len(configs_to_execute)}: {output_config_name}")
                tracker.set_loop_iteration(i + 1)

                # ====================================================================
                # DETERMINE MEDIA TYPE (needed for both Stage 3 and Stage 4)
                # ====================================================================
                # Extract media type from output config name BEFORE Stage 3
                # This ensures media_type is ALWAYS defined, even when stage4_only=True
                # SESSION 84: Added 'code' media type for P5.js code generation
                # SESSION 95: Added Tone.js code generation
                if 'code' in output_config_name.lower() or 'p5js' in output_config_name.lower() or 'tonejs' in output_config_name.lower():
                    media_type = 'code'
                elif 'image' in output_config_name.lower() or 'sd' in output_config_name.lower() or 'flux' in output_config_name.lower() or 'gpt' in output_config_name.lower():
                    media_type = 'image'
                elif 'audio' in output_config_name.lower():
                    media_type = 'audio'
                elif 'music' in output_config_name.lower() or 'ace' in output_config_name.lower():
                    media_type = 'music'
                elif 'video' in output_config_name.lower():
                    media_type = 'video'
                elif '3d' in output_config_name.lower():
                    media_type = '3d'
                else:
                    media_type = 'image'  # Default fallback

                # ====================================================================
                # PHASE 4: INTELLIGENT SEED LOGIC (before Stage 3)
                # ====================================================================
                # Decision happens BEFORE Stage 3 translation, based on Stage 2 result
                stage2_prompt = result.final_output  # Prompt from Stage 2 (before translation)

                if stage2_prompt != _last_prompt or output_config_name != _last_output_config:
                    # Prompt OR model changed → keep same seed (compare effect of change)
                    if _last_seed is not None:
                        calculated_seed = _last_seed
                        logger.info(f"[PHASE4-SEED] Prompt or model CHANGED → reusing seed {calculated_seed}")
                    else:
                        calculated_seed = 123456789
                        logger.info(f"[PHASE4-SEED] First run → using standard seed {calculated_seed}")
                else:
                    # Prompt AND model unchanged → new random seed (user wants variation)
                    calculated_seed = random.randint(0, 2147483647)
                    logger.info(f"[PHASE4-SEED] Prompt+model UNCHANGED (re-run) → new random seed {calculated_seed}")

                # Update global state AFTER decision
                _last_prompt = stage2_prompt
                _last_seed = calculated_seed
                _last_output_config = output_config_name

                # Override with user-provided seed if specified
                if seed_override is not None:
                    calculated_seed = seed_override
                    logger.info(f"[PHASE4-SEED] User override → using seed {calculated_seed}")

                # ====================================================================
                # STAGE 3: PRE-OUTPUT SAFETY (per output config)
                # ====================================================================
                stage_3_blocked = False

                # Skip Stage 3 ONLY if stage4_only=True (fast regeneration)
                # Note: Stage 3 now includes translation, so it runs even if safety_level='research'
                if not stage4_only:
                    tracker.set_stage(3)
                    recorder.set_state(3, "pre_output_safety")

                    # SESSION 84: Skip translation for code output (code is already in target format)
                    # Code output doesn't need translation - it's JavaScript, not natural language
                    skip_translation = (media_type == 'code')

                    if skip_translation:
                        # For code generation: Skip translation, but keep safety check
                        logger.info(f"[4-STAGE] Stage 3: Skip translation (skip_translation=true), safety only for {output_config_name}")

                        # Use Stage 2 output directly (already in target language)
                        safety_result = asyncio.run(execute_stage3_safety_code(
                            result.final_output,
                            safety_level,
                            media_type,
                            pipeline_executor
                        ))

                        # Code path: no translation, use Stage 2 output directly
                        if safety_result['safe']:
                            safety_result['positive_prompt'] = result.final_output
                    else:
                        # Standard path: Translation + Safety
                        # CLIP-prompt mode: safety-check the interception result (user's own text)
                        prompt_for_safety = interception_text if triple_prompt_data else result.final_output
                        if triple_prompt_data:
                            logger.info(f"[4-STAGE] Stage 3: Using interception result for safety+translation (user text → T5)")
                        logger.info(f"[4-STAGE] Stage 3: Translation + Safety for {output_config_name} (type: {media_type}, level: {safety_level})")

                        safety_result = asyncio.run(execute_stage3_safety(
                            prompt_for_safety,
                            safety_level,
                            media_type,
                            pipeline_executor,
                            user_language=user_language
                        ))

                    # Log Stage 3 safety check
                    tracker.log_stage3_safety_check(
                        loop_iteration=i + 1,
                        safe=safety_result['safe'],
                        method=safety_result.get('method', 'hybrid'),
                        config_used=output_config_name,
                        model_used=safety_result.get('model_used'),
                        backend_type=safety_result.get('backend_type'),
                        execution_time=safety_result.get('execution_time')
                    )

                    if not safety_result['safe']:
                        # Stage 3 blocked for this output
                        abort_reason = safety_result.get('abort_reason', 'Content blocked by safety filter')
                        logger.warning(f"[4-STAGE] Stage 3 BLOCKED for {output_config_name}: {abort_reason}")

                        # SESSION 29: Save safety_pre_output result (blocked)
                        recorder.save_entity('safety_pre_output', {
                            'safe': False,
                            'method': safety_result.get('method', 'hybrid'),
                            'media_type': media_type,
                            'safety_level': safety_level,
                            'blocked': True,
                            'abort_reason': abort_reason
                        })

                        # SESSION 29: Save stage 3 blocked error
                        recorder.save_error(
                            stage=3,
                            error_type='safety_blocked',
                            message=abort_reason,
                            details={'media_type': media_type, 'config': output_config_name}
                        )
                        logger.info(f"[RECORDER] Saved stage 3 blocked error")

                        # Log Stage 3 blocked
                        tracker.log_stage3_blocked(
                            loop_iteration=i + 1,
                            config_used=output_config_name,
                            abort_reason=abort_reason
                        )

                        media_outputs.append({
                            'config': output_config_name,
                            'status': 'blocked',
                            'reason': abort_reason,
                            'media_type': media_type,  # Add media_type for frontend
                            'safety_level': safety_level
                        })
                        stage_3_blocked = True
                        continue  # Skip Stage 4 for this output
                    else:
                        # SESSION 29: Save safety_pre_output result (passed)
                        recorder.save_entity('safety_pre_output', {
                            'safe': True,
                            'method': safety_result.get('method', 'hybrid'),
                            'media_type': media_type,
                            'safety_level': safety_level
                        })
                        logger.info(f"[RECORDER] Saved safety_pre_output entity")

        # End of skip_preprocessing else block - Stage 1-3 complete

        # ====================================================================
        # Determine prompt for Stage 4 (use translated text if Stage 3 ran)
        # ====================================================================
                # If Stage 3 ran and translated the text, use the English positive_prompt
                # Otherwise, fallback to Stage 2 output (only if stage4_only=True)
                if not stage_3_blocked and not stage4_only:
                    # Stage 3 ran - use translated English text from positive_prompt
                    translated_prompt = safety_result.get('positive_prompt', result.final_output)
                    logger.info(f"[4-STAGE] Using translated prompt from Stage 3 for media generation")
                    logger.info(f"[STAGE3-TRANSLATED] Prompt (first 200 chars): {translated_prompt[:200]}...")

                    if triple_prompt_data:
                        # CLIP-prompt mode: CLIP-L/G from optimization, T5 = translated interception result
                        prompt_for_media = triple_prompt_data['clip_l']
                        custom_params['prompt_2'] = triple_prompt_data['clip_g']
                        custom_params['prompt_3'] = translated_prompt  # User's text, translated by Stage 3
                        logger.info(f"[CLIP-PROMPT] Stage 4: CLIP-L={len(prompt_for_media.split())}w, "
                                    f"CLIP-G={len(triple_prompt_data['clip_g'].split())}w, "
                                    f"T5={len(translated_prompt.split())}w (user text)")
                    else:
                        prompt_for_media = translated_prompt

                    # Save translation (English prompt for media generation)
                    if translated_prompt != result.final_output:
                        recorder.save_entity('translation_en', translated_prompt)
                        logger.info(f"[RECORDER] Saved translation_en entity")
                else:
                    # Stage 3 skipped - use Stage 2 output directly
                    if triple_prompt_data:
                        prompt_for_media = triple_prompt_data['clip_l']
                        custom_params['prompt_2'] = triple_prompt_data['clip_g']
                        custom_params['prompt_3'] = interception_text  # User's interception text as T5
                        logger.info(f"[CLIP-PROMPT] Stage 4 (no Stage 3): T5 = interception result")
                    else:
                        prompt_for_media = result.final_output
                    logger.info(f"[4-STAGE] Using Stage 2 output directly (Stage 3 skipped)")

        # ====================================================================
        # STAGE 4: OUTPUT (Media Generation)
        # ====================================================================
                if not stage_3_blocked:
                    logger.info(f"[4-STAGE] Stage 4: Executing output config '{output_config_name}'")
                    tracker.set_stage(4)
                    recorder.set_state(4, "media_generation")

                    # Track Stage 4 model in metadata
                    if 'models_used' not in recorder.metadata:
                        recorder.metadata['models_used'] = {}
                    recorder.metadata['models_used']['stage4_output'] = output_config_name
                    recorder._save_metadata()
                    logger.info(f"[RECORDER] Updated models_used with stage4_output: {output_config_name}")

                    try:
                        # Session 116: Pass config-specific LoRAs to Stage 4
                        from config import LORA_TRIGGERS
                        config_loras = result.metadata.get('loras', []) if result.metadata else []
                        if config_loras:
                            custom_params['loras'] = config_loras
                            logger.info(f"[LORA] Using config-specific LoRAs: {[l['name'] for l in config_loras]}")
                        elif LORA_TRIGGERS:
                            custom_params['loras'] = LORA_TRIGGERS
                            logger.debug(f"[LORA] Using global LORA_TRIGGERS ({len(LORA_TRIGGERS)} LoRAs)")

                        # Create context with custom placeholders if we have any custom parameters
                        # This ensures strict parallelization across all legacy workflows
                        from schemas.engine.pipeline_executor import PipelineContext
                        context_override = None
                        if custom_params:
                            context_override = PipelineContext(
                                input_text=prompt_for_media,
                                user_input=prompt_for_media
                            )
                            context_override.custom_placeholders = custom_params
                            logger.info(f"[CUSTOM-PARAMS] Injecting custom placeholders: {list(custom_params.keys())}")

                        # Execute Output-Pipeline with translated/transformed text
                        output_result = asyncio.run(pipeline_executor.execute_pipeline(
                            config_name=output_config_name,
                            input_text=prompt_for_media,  # Use translated English text from Stage 3!
                            user_input=prompt_for_media,
                            context_override=context_override,  # NEW: Pass custom parameters uniformly
                            seed_override=calculated_seed,  # Phase 4: Intelligent seed
                            input_image=input_image,  # Session 80: IMG2IMG support
                            input_image1=input_image1,  # Session 86+: Multi-image support (image 1)
                            input_image2=input_image2,  # Session 86+: Multi-image support (image 2, optional)
                            input_image3=input_image3,  # Session 86+: Multi-image support (image 3, optional)
                            alpha_factor=alpha_factor  # Surrealizer: T5-CLIP fusion alpha (backwards compat)
                        ))

                        # Add media output to results
                        if output_result.success:
                            # ====================================================================
                            # MEDIA STORAGE - Download and store media locally
                            # ====================================================================
                            logger.info(f"[MEDIA-STORAGE-DEBUG] Starting media storage for config: {output_config_name}")
                            logger.info(f"[MEDIA-STORAGE-DEBUG] output_result.success: {output_result.success}")
                            logger.info(f"[MEDIA-STORAGE-DEBUG] output_result.final_output length: {len(output_result.final_output) if output_result.final_output else 0}")
                            logger.info(f"[MEDIA-STORAGE-DEBUG] output_result.final_output starts with: {output_result.final_output[:100] if output_result.final_output else 'EMPTY'}")
                            logger.info(f"[MEDIA-STORAGE-DEBUG] output_result.metadata keys: {list(output_result.metadata.keys())}")

                            media_stored = False
                            media_output_data = None

                            try:
                                output_value = output_result.final_output
                                saved_filename = None

                                # Extract seed from output_result metadata (if available)
                                seed = output_result.metadata.get('seed')

                                logger.info(f"[MEDIA-STORAGE-DEBUG] output_value type: {type(output_value)}, length: {len(output_value) if output_value else 0}")
                                logger.info(f"[MEDIA-STORAGE-DEBUG] Checking routing conditions...")

                                # ====================================================================
                                # PYTHON CHUNKS: Direct storage path (parallel to JSON chunk routing)
                                # ====================================================================
                                # Python chunks (.py) return bytes directly with base64 in metadata
                                # This bypasses the marker-based routing used by JSON chunks
                                if output_result.metadata.get('chunk_type') == 'python':
                                    logger.info(f"[PYTHON-CHUNK-ROUTE] Detected Python chunk, using direct storage path")

                                    import base64

                                    # Check for audio data (music/audio chunks)
                                    audio_data_b64 = output_result.metadata.get('audio_data')
                                    if audio_data_b64:
                                        logger.info(f"[PYTHON-CHUNK-ROUTE] Audio data found: {len(audio_data_b64)} chars base64")
                                        audio_bytes = base64.b64decode(audio_data_b64)
                                        audio_format = output_result.metadata.get('audio_format', 'mp3')

                                        # Save audio directly
                                        saved_filename = recorder.save_entity(
                                            entity_type=f'output_{media_type}',  # e.g. output_music
                                            content=audio_bytes,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': output_result.metadata.get('backend', 'unknown'),
                                                'media_type': 'music',
                                                'seed': seed,
                                                'size_bytes': len(audio_bytes),
                                                'format': audio_format
                                            }
                                        )
                                        logger.info(f"[PYTHON-CHUNK-ROUTE] Audio saved: {saved_filename}")
                                        media_stored = True

                                        # Create media output data for frontend
                                        chunk_media_type = output_result.metadata.get('media_type', media_type)
                                        media_output_data = {
                                            'config': output_config_name,
                                            'status': 'success',
                                            'media_type': chunk_media_type,
                                            'filename': saved_filename,
                                            'url': f'/api/media/{chunk_media_type}/{run_id}'
                                        }

                                    # Check for image data (image chunks)
                                    elif output_result.metadata.get('image_data'):
                                        image_data_b64 = output_result.metadata.get('image_data')
                                        logger.info(f"[PYTHON-CHUNK-ROUTE] Image data found: {len(image_data_b64)} chars base64")
                                        image_bytes = base64.b64decode(image_data_b64)
                                        image_format = output_result.metadata.get('image_format', 'png')

                                        # Save image directly
                                        saved_filename = recorder.save_entity(
                                            entity_type='output_image',
                                            content=image_bytes,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': output_result.metadata.get('backend', 'unknown'),
                                                'media_type': 'image',
                                                'seed': seed,
                                                'size_bytes': len(image_bytes),
                                                'format': image_format
                                            }
                                        )
                                        logger.info(f"[PYTHON-CHUNK-ROUTE] Image saved: {saved_filename}")
                                        media_stored = True

                                        # Create media output data for frontend
                                        media_output_data = {
                                            'config': output_config_name,
                                            'status': 'success',
                                            'media_type': 'image',
                                            'filename': saved_filename,
                                            'url': f'/api/media/runs/{run_id}/{saved_filename}'
                                        }

                                    # Check for video data (video chunks)
                                    elif output_result.metadata.get('video_data'):
                                        video_data_b64 = output_result.metadata.get('video_data')
                                        logger.info(f"[PYTHON-CHUNK-ROUTE] Video data found: {len(video_data_b64)} chars base64")
                                        video_bytes = base64.b64decode(video_data_b64)
                                        video_format = output_result.metadata.get('video_format', 'mp4')

                                        saved_filename = recorder.save_entity(
                                            entity_type='output_video',
                                            content=video_bytes,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': output_result.metadata.get('backend', 'unknown'),
                                                'media_type': 'video',
                                                'seed': seed,
                                                'size_bytes': len(video_bytes),
                                                'format': video_format
                                            }
                                        )
                                        logger.info(f"[PYTHON-CHUNK-ROUTE] Video saved: {saved_filename}")
                                        media_stored = True

                                        media_output_data = {
                                            'config': output_config_name,
                                            'status': 'success',
                                            'media_type': 'video',
                                            'filename': saved_filename,
                                            'url': f'/api/media/video/{run_id}'
                                        }

                                    # Check for 3D mesh data (Hunyuan3D chunks)
                                    elif output_result.metadata.get('mesh_data'):
                                        mesh_data_b64 = output_result.metadata.get('mesh_data')
                                        logger.info(f"[PYTHON-CHUNK-ROUTE] Mesh data found: {len(mesh_data_b64)} chars base64")
                                        mesh_bytes = base64.b64decode(mesh_data_b64)

                                        saved_filename = recorder.save_entity(
                                            entity_type='output_3d',
                                            content=mesh_bytes,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': output_result.metadata.get('backend', 'hunyuan3d'),
                                                'media_type': '3d',
                                                'seed': seed,
                                                'size_bytes': len(mesh_bytes),
                                                'format': output_result.metadata.get('mesh_format', 'glb'),
                                            }
                                        )
                                        logger.info(f"[PYTHON-CHUNK-ROUTE] Mesh saved: {saved_filename}")
                                        media_stored = True

                                        # Also save Blender thumbnail if available
                                        thumb_b64 = output_result.metadata.get('image_data')
                                        if thumb_b64:
                                            thumbnail_bytes = base64.b64decode(thumb_b64)
                                            recorder.save_entity(
                                                entity_type='output_image',
                                                content=thumbnail_bytes,
                                                metadata={
                                                    'config': output_config_name,
                                                    'backend': 'blender_preview',
                                                    'format': 'png',
                                                    'seed': seed,
                                                }
                                            )

                                        media_output_data = {
                                            'config': output_config_name,
                                            'status': 'success',
                                            'media_type': '3d',
                                            'filename': saved_filename,
                                            'url': f'/api/media/3d/{run_id}',
                                            'mesh_url': f'/api/media/3d/{run_id}',
                                        }

                                    else:
                                        logger.error(f"[PYTHON-CHUNK-ROUTE] No audio_data, image_data, video_data, or mesh_data in metadata")
                                        media_stored = False
                                        media_output_data = {
                                            'config': output_config_name,
                                            'status': 'error',
                                            'error': 'Python chunk returned no media data'
                                        }

                                    # Skip all marker-based routing below (early exit from routing logic)
                                    # media_stored=True prevents JSON chunk routing from running

                                # ====================================================================
                                # JSON CHUNKS: Marker-based routing (legacy, but still supported)
                                # ====================================================================
                                # Only run if Python chunk didn't already handle storage
                                # SESSION 84: Handle code output (P5.js, SonicPi, etc.)
                                # SESSION 95: Added Tone.js support
                                if not media_stored and media_type == 'code':
                                    logger.info(f"[STAGE4-CODE] Handling code output for {output_config_name}")

                                    # Determine entity type and route based on output config
                                    if 'tonejs' in output_config_name.lower():
                                        code_entity_type = 'tonejs'
                                        code_framework = 'tonejs'
                                        code_route = f'/api/media/tonejs/{run_id}'
                                    else:
                                        code_entity_type = 'p5'
                                        code_framework = 'p5js'
                                        code_route = f'/api/media/p5/{run_id}'

                                    # Code is already in output_value (from API response)
                                    if isinstance(output_value, str) and len(output_value) > 0:
                                        # Save code as entity
                                        saved_filename = recorder.save_entity(
                                            entity_type=code_entity_type,
                                            content=output_value.encode('utf-8'),
                                            metadata={
                                                'config': output_config_name,
                                                'backend': output_result.metadata.get('backend', 'openrouter'),
                                                'model': output_result.metadata.get('model', 'unknown'),
                                                'language': 'javascript',
                                                'framework': code_framework,
                                                'seed': seed,
                                                'format': 'js'
                                            }
                                        )
                                        logger.info(f"[STAGE4-CODE] Saved code entity: {saved_filename}")
                                        media_stored = True

                                        # Create media output data for frontend
                                        media_output_data = {
                                            'config': output_config_name,
                                            'status': 'success',
                                            'media_type': 'code',
                                            'filename': saved_filename,
                                            'url': code_route,
                                            'code': output_value  # Include code in response
                                        }
                                    else:
                                        logger.error(f"[STAGE4-CODE] Code generation failed: empty output")
                                        media_stored = False
                                        media_output_data = {
                                            'config': output_config_name,
                                            'status': 'error',
                                            'error': 'Code generation failed: empty output'
                                        }

                                # Detect generation backend and download appropriately
                                elif not media_stored and output_value in ('comfyui_generated', 'comfyui_direct_generated'):
                                    # ComfyUI Direct (WebSocket) — media bytes in metadata
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: comfyui_direct_generated")
                                    media_files_data = output_result.metadata.get('media_files', [])
                                    outputs_meta = output_result.metadata.get('outputs_metadata', [])
                                    for idx, file_data in enumerate(media_files_data):
                                        file_meta = outputs_meta[idx] if idx < len(outputs_meta) else {}
                                        original_filename = file_meta.get('filename', '')
                                        file_format = original_filename.split('.')[-1] if '.' in original_filename else 'png'
                                        saved_filename = recorder.save_entity(
                                            entity_type=f'output_{media_type}',
                                            content=file_data,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': 'comfyui_direct',
                                                'seed': seed,
                                                'format': file_format,
                                                'node_id': file_meta.get('node_id', 'unknown'),
                                                'file_index': idx,
                                                'total_files': len(media_files_data)
                                            }
                                        )
                                    if media_files_data:
                                        media_stored = True
                                        logger.info(f"[RECORDER] ComfyUI direct: saved {len(media_files_data)} file(s)")
                                elif not media_stored and output_value == 'diffusers_generated':
                                    # Session 150: Diffusers backend - image data is base64 encoded
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: diffusers_generated")
                                    image_data_b64 = output_result.metadata.get('image_data')
                                    if image_data_b64:
                                        import base64
                                        image_bytes = base64.b64decode(image_data_b64)
                                        logger.info(f"[RECORDER] Saving Diffusers image: {len(image_bytes)} bytes")
                                        saved_filename = recorder.save_entity(
                                            entity_type=f'output_{media_type}',
                                            content=image_bytes,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': 'diffusers',
                                                'model': output_result.metadata.get('model_id', 'unknown'),
                                                'seed': seed
                                            }
                                        )
                                        logger.info(f"[RECORDER] Diffusers image saved: {saved_filename}")
                                    else:
                                        logger.error("[DIFFUSERS] No image_data in response metadata")
                                        saved_filename = None
                                elif not media_stored and output_value in ('heartmula_generated', 'stable_audio_generated'):
                                    # Audio backend (HeartMuLa, Stable Audio) - audio data is base64 encoded
                                    audio_backend = output_result.metadata.get('backend', 'unknown')
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: {output_value}")
                                    audio_data_b64 = output_result.metadata.get('audio_data')
                                    if audio_data_b64:
                                        import base64
                                        audio_bytes = base64.b64decode(audio_data_b64)
                                        logger.info(f"[RECORDER] Saving {audio_backend} audio: {len(audio_bytes)} bytes")
                                        saved_filename = recorder.save_entity(
                                            entity_type=f'output_{media_type}',
                                            content=audio_bytes,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': audio_backend,
                                                'format': output_result.metadata.get('audio_format', 'mp3'),
                                                'seed': seed
                                            }
                                        )
                                        logger.info(f"[RECORDER] {audio_backend} audio saved: {saved_filename}")
                                    else:
                                        logger.error(f"[{audio_backend.upper()}] No audio_data in response metadata")
                                        saved_filename = None
                                elif not media_stored and output_value == 'hunyuan3d_generated':
                                    # Hunyuan3D-2 3D mesh generation
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: hunyuan3d_generated")
                                    mesh_data_b64 = output_result.metadata.get('mesh_data')
                                    if mesh_data_b64:
                                        import base64
                                        mesh_bytes = base64.b64decode(mesh_data_b64)
                                        logger.info(f"[RECORDER] Saving Hunyuan3D mesh: {len(mesh_bytes)} bytes")
                                        saved_filename = recorder.save_entity(
                                            entity_type='output_3d',
                                            content=mesh_bytes,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': 'hunyuan3d',
                                                'format': 'glb',
                                                'seed': seed,
                                                'size_bytes': len(mesh_bytes),
                                            }
                                        )
                                        logger.info(f"[RECORDER] Hunyuan3D mesh saved: {saved_filename}")
                                        media_stored = True

                                        # Also save Blender thumbnail if available
                                        image_data_b64 = output_result.metadata.get('image_data')
                                        if image_data_b64:
                                            thumbnail_bytes = base64.b64decode(image_data_b64)
                                            recorder.save_entity(
                                                entity_type='output_image',
                                                content=thumbnail_bytes,
                                                metadata={
                                                    'config': output_config_name,
                                                    'backend': 'blender_preview',
                                                    'format': 'png',
                                                    'seed': seed,
                                                }
                                            )
                                    else:
                                        logger.error("[HUNYUAN3D] No mesh_data in response metadata")
                                        saved_filename = None

                                elif not media_stored and output_value == 'workflow_generated':
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: workflow_generated")
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] Metadata keys: {list(output_result.metadata.keys())}")
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] legacy_workflow: {output_result.metadata.get('legacy_workflow', 'NOT_FOUND')}")

                                    # Check if this is a legacy workflow
                                    is_legacy_workflow = output_result.metadata.get('legacy_workflow', False)
                                    download_all = output_result.metadata.get('download_all', False)

                                    def _extract_saveimage_titles(workflow_json: dict) -> dict:
                                        """Extract SaveImage node titles from workflow JSON.
                                        Returns: {node_id: title}
                                        """
                                        titles = {}
                                        workflow_dict = workflow_json.get('workflow', workflow_json)
                                        for node_id, node_data in workflow_dict.items():
                                            if node_data.get('class_type') == 'SaveImage':
                                                title = node_data.get('_meta', {}).get('title', f'SaveImage_{node_id}')
                                                titles[node_id] = title
                                        return titles

                                    if is_legacy_workflow:
                                        # Legacy workflow: media files already downloaded by service
                                        logger.info(f"[4-STAGE] Legacy workflow detected - saving media files")

                                        # 1. Save workflow JSON for reproducibility
                                        workflow_json = output_result.metadata.get('workflow_json')
                                        if workflow_json:
                                            try:
                                                recorder.save_workflow_json(
                                                    workflow=workflow_json,
                                                    entity_type='workflow_archive'
                                                )
                                                logger.info(f"[RECORDER] ✓ Saved workflow JSON")

                                                # Extract seed from workflow Node 3 (KSampler) for metadata
                                                if 'workflow' in workflow_json or '3' in workflow_json:
                                                    workflow_dict = workflow_json.get('workflow', workflow_json)
                                                    if '3' in workflow_dict and 'inputs' in workflow_dict['3']:
                                                        injected_seed = workflow_dict['3']['inputs'].get('seed')
                                                        if injected_seed is not None:
                                                            seed = injected_seed
                                                            logger.info(f"[RECORDER] ✓ Extracted seed from workflow Node 3: {seed}")
                                            except Exception as e:
                                                logger.error(f"[RECORDER] Failed to save workflow JSON: {e}")

                                        # 2. Save ALL media files (binary data from metadata)
                                        media_files = output_result.metadata.get('media_files', [])
                                        outputs_metadata = output_result.metadata.get('outputs_metadata', [])
                                        prompt_id = output_result.metadata.get('prompt_id')

                                        # IMMEDIATE CLEANUP: Remove binary data from metadata before it goes into response dicts
                                        # This prevents "Object of type bytes is not JSON serializable" errors
                                        if 'media_files' in output_result.metadata:
                                            del output_result.metadata['media_files']
                                        if 'outputs_metadata' in output_result.metadata:
                                            del output_result.metadata['outputs_metadata']

                                        # Extract SaveImage node titles for image labeling
                                        saveimage_titles = _extract_saveimage_titles(workflow_json) if workflow_json else {}
                                        if saveimage_titles:
                                            logger.info(f"[RECORDER] ✓ Extracted {len(saveimage_titles)} SaveImage node titles")

                                        if media_files:
                                            saved_filenames = []
                                            for idx, file_data in enumerate(media_files):
                                                try:
                                                    # Get metadata for this file
                                                    file_metadata = outputs_metadata[idx] if idx < len(outputs_metadata) else {}

                                                    # Get node_id and lookup title
                                                    node_id = file_metadata.get('node_id', 'unknown')
                                                    node_title = saveimage_titles.get(node_id, f'unknown_{node_id}')

                                                    # Build metadata for recorder
                                                    entity_metadata = {
                                                        'config': output_config_name,
                                                        'backend': 'comfyui_legacy',
                                                        'prompt_id': prompt_id,
                                                        'file_index': idx,
                                                        'total_files': len(media_files),
                                                        'node_id': node_id,
                                                        'node_title': node_title,
                                                        'original_filename': file_metadata.get('filename', 'unknown')
                                                    }

                                                    if seed is not None:
                                                        entity_metadata['seed'] = seed

                                                    # Save as entity
                                                    filename = recorder.save_entity(
                                                        entity_type=f'output_{media_type}',
                                                        content=file_data,
                                                        metadata=entity_metadata
                                                    )
                                                    saved_filenames.append(filename)
                                                    logger.info(f"[RECORDER] ✓ Saved {media_type} {idx+1}/{len(media_files)}: {filename}")

                                                except Exception as e:
                                                    logger.error(f"[RECORDER] Failed to save file {idx+1}: {e}")

                                            logger.info(f"[RECORDER] ✓ Saved {len(saved_filenames)}/{len(media_files)} file(s)")
                                            saved_filename = saved_filenames[0] if saved_filenames else None

                                            # If multiple images were generated, create composite automatically
                                            if len(media_files) > 1:
                                                try:
                                                    logger.info(f"[COMPOSITE] Creating composite from {len(media_files)} images...")

                                                    # Auto-generate labels
                                                    labels = [f"Image {i+1}" for i in range(len(media_files))]

                                                    # Create composite
                                                    composite_data = recorder.create_composite_image(
                                                        image_data_list=media_files,
                                                        labels=labels,
                                                        workflow_title=output_config_name.replace('_', ' ').title()
                                                    )

                                                    # Save composite as new entity
                                                    composite_filename = recorder.save_entity(
                                                        entity_type='output_image_composite',
                                                        content=composite_data,
                                                        metadata={
                                                            'config': output_config_name,
                                                            'format': 'png',
                                                            'backend': 'comfyui_legacy',
                                                            'prompt_id': prompt_id,
                                                            'composite': True,
                                                            'source_files': saved_filenames,
                                                            'seed': seed
                                                        }
                                                    )

                                                    logger.info(f"[COMPOSITE] ✓ Created: {composite_filename}")

                                                except Exception as e:
                                                    logger.warning(f"[COMPOSITE] Failed (using individual images): {e}")
                                        else:
                                            logger.warning(f"[RECORDER] No media_files in metadata for legacy workflow")
                                            saved_filename = None

                                        # Clean up binary data from metadata before JSON response
                                        if 'media_files' in output_result.metadata:
                                            logger.info(f"[RECORDER] Removing binary media_files from metadata ({len(output_result.metadata['media_files'])} files)")
                                            del output_result.metadata['media_files']
                                        if 'outputs_metadata' in output_result.metadata:
                                            del output_result.metadata['outputs_metadata']
                                        if 'workflow_json' in output_result.metadata:
                                            del output_result.metadata['workflow_json']
                                    else:
                                        # Standard workflow: media from filesystem or direct bytes
                                        filesystem_path = output_result.metadata.get('filesystem_path')
                                        wf_media_files = output_result.metadata.get('media_files', [])

                                        if wf_media_files:
                                            # ComfyUI Direct: media bytes already available
                                            wf_outputs_meta = output_result.metadata.get('outputs_metadata', [])
                                            for idx, file_data in enumerate(wf_media_files):
                                                file_meta = wf_outputs_meta[idx] if idx < len(wf_outputs_meta) else {}
                                                original_fn = file_meta.get('filename', '')
                                                file_fmt = original_fn.split('.')[-1] if '.' in original_fn else 'png'
                                                saved_filename = recorder.save_entity(
                                                    entity_type=f'output_{media_type}',
                                                    content=file_data,
                                                    metadata={
                                                        'config': output_config_name,
                                                        'backend': 'comfyui_direct',
                                                        'seed': seed,
                                                        'format': file_fmt,
                                                        'node_id': file_meta.get('node_id', 'unknown'),
                                                        'file_index': idx,
                                                        'total_files': len(wf_media_files)
                                                    }
                                                )
                                            # Clean binary data from metadata
                                            if 'media_files' in output_result.metadata:
                                                del output_result.metadata['media_files']
                                            if 'outputs_metadata' in output_result.metadata:
                                                del output_result.metadata['outputs_metadata']
                                            logger.info(f"[RECORDER] Saved {len(wf_media_files)} file(s) from ComfyUI direct")
                                        elif filesystem_path:
                                            try:
                                                with open(filesystem_path, 'rb') as f:
                                                    file_data = f.read()

                                                saved_filename = recorder.save_entity(
                                                    entity_type=f'output_{media_type}',
                                                    content=file_data,
                                                    metadata={
                                                        'config': output_config_name,
                                                        'backend': 'comfyui',
                                                        'seed': seed,
                                                        'filesystem_path': filesystem_path
                                                    }
                                                )
                                                logger.info(f"[RECORDER] Saved {media_type} from filesystem: {saved_filename}")
                                            except Exception as e:
                                                logger.error(f"[RECORDER] Failed to save {media_type} from filesystem: {e}")
                                                saved_filename = None
                                        else:
                                            logger.warning(f"[RECORDER] No filesystem_path or media_files in metadata for workflow_generated")
                                            saved_filename = None
                                elif not media_stored and (output_value.startswith('http://') or output_value.startswith('https://')):
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: http/https URL")
                                    # API-based generation (GPT-5, Replicate, etc.) - URL
                                    logger.info(f"[RECORDER] Downloading from URL: {output_value}")
                                    saved_filename = asyncio.run(recorder.download_and_save_from_url(
                                        url=output_value,
                                        media_type=media_type,
                                        config=output_config_name,
                                        seed=seed
                                    ))
                                elif not media_stored and not output_value.startswith(('http://', 'https://', 'data:')) and len(output_value) > 1000 and output_value[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/':
                                    # Pure base64 string (OpenAI Images API format)
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: Pure base64 (OpenAI Images API)")
                                    logger.info(f"[RECORDER] Decoding pure base64 string ({len(output_value)} chars)")
                                    try:
                                        import base64

                                        # Decode base64 directly (no data URI parsing needed)
                                        image_bytes = base64.b64decode(output_value)

                                        # Default to PNG format for Images API
                                        image_format = 'png'

                                        # Save using recorder.save_entity
                                        saved_filename = recorder.save_entity(
                                            entity_type=f'output_{media_type}',
                                            content=image_bytes,
                                            metadata={
                                                'config': output_config_name,
                                                'backend': 'api',
                                                'provider': 'openai',
                                                'seed': seed,
                                                'format': image_format,
                                                'source': 'images_api_base64'
                                            }
                                        )
                                        logger.info(f"[RECORDER] Saved {media_type} from pure base64: {saved_filename}")
                                    except Exception as e:
                                        logger.error(f"[RECORDER] Failed to decode pure base64: {e}")
                                        import traceback
                                        traceback.print_exc()
                                        saved_filename = None
                                elif not media_stored and output_value.startswith('data:'):
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: data: URI (base64 with mime type)")
                                    # API-based generation with base64 data URI (e.g., some API providers)
                                    logger.info(f"[RECORDER] Decoding base64 data URI ({len(output_value)} chars)")
                                    try:
                                        import base64
                                        import re

                                        # Extract mime type and base64 data from data URI
                                        # Format: data:image/png;base64,iVBORw0KGgo...
                                        match = re.match(r'data:([^;]+);base64,(.+)', output_value)
                                        if match:
                                            mime_type = match.group(1)
                                            base64_data = match.group(2)

                                            # Decode base64
                                            image_bytes = base64.b64decode(base64_data)

                                            # Detect format from mime type
                                            format_map = {
                                                'image/png': 'png',
                                                'image/jpeg': 'jpg',
                                                'image/webp': 'webp',
                                                'image/gif': 'gif'
                                            }
                                            image_format = format_map.get(mime_type, 'png')

                                            # Save using recorder.save_entity
                                            saved_filename = recorder.save_entity(
                                                entity_type=f'output_{media_type}',
                                                content=image_bytes,
                                                metadata={
                                                    'config': output_config_name,
                                                    'backend': 'api',
                                                    'provider': 'openrouter',
                                                    'seed': seed,
                                                    'format': image_format,
                                                    'source': 'data_uri'
                                                }
                                            )
                                            logger.info(f"[RECORDER] Saved {media_type} from data URI: {saved_filename}")
                                        else:
                                            logger.error(f"[RECORDER] Invalid data URI format")
                                            saved_filename = None
                                    except Exception as e:
                                        logger.error(f"[RECORDER] Failed to decode data URI: {e}")
                                        import traceback
                                        traceback.print_exc()
                                        saved_filename = None
                                elif not media_stored:
                                    logger.info(f"[MEDIA-STORAGE-DEBUG] ✓ Matched: ComfyUI prompt_id (fallback)")
                                    # ComfyUI generation - prompt_id
                                    logger.info(f"[RECORDER] Downloading from ComfyUI: {output_value}")

                                    # Save prompt_id for potential SSE streaming
                                    recorder.save_prompt_id(output_value, media_type)

                                    # Download and save media immediately (blocking, but necessary for media API)
                                    saved_filename = asyncio.run(recorder.download_and_save_from_comfyui(
                                        prompt_id=output_value,
                                        media_type=media_type,
                                        config=output_config_name,
                                        seed=seed
                                    ))

                                if saved_filename:
                                    media_stored = True
                                    logger.info(f"[RECORDER] Media stored successfully in run {run_id}: {saved_filename}")
                                else:
                                    media_stored = False
                                    logger.warning(f"[RECORDER] Failed to store media for run {run_id}")

                            except Exception as e:
                                logger.error(f"[RECORDER] Error downloading/storing media: {e}")
                                import traceback
                                traceback.print_exc()

                            # Log Stage 4 output (using run_id as file_path now)
                            tracker.log_output_image(
                                loop_iteration=i + 1,
                                config_used=output_config_name,
                                file_path=run_id if media_stored else output_result.final_output,
                                model_used=output_result.metadata.get('model_used', 'unknown'),
                                backend_type=output_result.metadata.get('backend_type', 'comfyui'),
                                metadata=output_result.metadata,
                                execution_time=output_result.execution_time
                            )

                            # Use media_output_data if it was created (for code, etc.), otherwise create generic object
                            if media_output_data is not None:
                                # Add run_id to existing media_output_data
                                media_output_data['run_id'] = run_id
                                media_output_data['execution_time'] = output_result.execution_time
                                media_output_data['metadata'] = output_result.metadata
                                media_outputs.append(media_output_data)
                            else:
                                # Generic object for image/video/audio
                                media_outputs.append({
                                    'config': output_config_name,
                                    'status': 'success',
                                    'run_id': run_id,  # NEW: Unified identifier for media
                                    'output': run_id if media_stored else output_result.final_output,  # Use run_id if stored, fallback to raw output
                                    'media_type': media_type,
                                    'media_stored': media_stored,  # Indicates if media was successfully stored
                                    'execution_time': output_result.execution_time,
                                    'metadata': output_result.metadata
                                })
                            logger.info(f"[4-STAGE] Stage 4 successful for {output_config_name}: run_id={run_id}, media_stored={media_stored}")
                        else:
                            # Media generation failed
                            media_outputs.append({
                                'config': output_config_name,
                                'status': 'error',
                                'media_type': media_type,  # Add media_type for frontend
                                'error': output_result.error
                            })
                            logger.error(f"[4-STAGE] Stage 4 failed for {output_config_name}: {output_result.error}")

                    except Exception as e:
                        logger.error(f"[4-STAGE] Exception during Stage 4 for {output_config_name}: {e}")
                        media_outputs.append({
                            'config': output_config_name,
                            'status': 'error',
                            'media_type': media_type,  # Add media_type for frontend
                            'error': str(e)
                        })

            # Add media outputs to response
            if len(media_outputs) == 1:
                # Single output: Use old format for backward compatibility
                response_data['media_output'] = media_outputs[0]
            else:
                # Multiple outputs: Use array format
                response_data['media_outputs'] = media_outputs
                response_data['media_output_count'] = len(media_outputs)

        elif not configs_to_execute and default_output and default_output != 'text':
            # No output config found for default_output
            logger.info(f"[AUTO-MEDIA] No Output-Config available for {default_output}")
            response_data['media_output'] = {
                'status': 'not_available',
                'message': f'No Output-Config for {default_output}'
            }

        # ====================================================================
        # FINALIZE EXECUTION HISTORY
        # ====================================================================
        # Log pipeline completion
        outputs_generated = len(media_outputs) if media_outputs else 0
        tracker.log_pipeline_complete(
            total_duration=result.execution_time if result else 0.0,
            outputs_generated=outputs_generated
        )

        # Persist execution history to storage
        tracker.finalize()
        logger.info(f"[TRACKER] Execution history saved: {tracker.execution_id}")

        # Visual separator for easier run distinction in terminal
        total_time = result.execution_time if result else 0.0
        logger.info("=" * 80)
        logger.info(f"{'RUN COMPLETED':^80}")
        logger.info("=" * 80)
        logger.info(f"  Run ID: {run_id}")
        logger.info(f"  Config: {schema_name}")
        logger.info(f"  Total Time: {total_time:.2f}s")
        logger.info(f"  Outputs: {outputs_generated}")
        logger.info("=" * 80)

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Pipeline-Execution Fehler: {e}")
        import traceback
        traceback.print_exc()

        # Try to finalize tracker even on error (fail-safe)
        try:
            if 'tracker' in locals():
                tracker.log_pipeline_error(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    stage=0
                )
                tracker.finalize()
        except Exception as tracker_error:
            logger.warning(f"[TRACKER] Failed to finalize on error: {tracker_error}")

        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# NOTE: Status endpoint is in pipeline_routes.py, not here
# Use /api/pipeline/{run_id}/status (not /api/schema/pipeline/{run_id}/status)

@schema_bp.route('/pipeline/test', methods=['POST'])
def test_pipeline():
    """Test-Endpoint für direkte Prompt-Interception"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'error': 'JSON-Request erwartet'}), 400

        input_prompt = data.get('input_prompt')
        style_prompt = data.get('style_prompt', '')
        input_context = data.get('input_context', '')
        model = data.get('model', 'local/gemma2:9b')

        if not input_prompt:
            return jsonify({'status': 'error', 'error': 'Parameter "input_prompt" erforderlich'}), 400

        # Session 134 FIX: Support task_instruction in test endpoint
        # Allow override via request, default to artistic_transformation
        instruction_type = data.get('instruction_type', 'transformation')
        task_instruction = data.get('task_instruction', get_instruction(instruction_type))

        # TODO [ARCHITECTURE VIOLATION]: Direct Engine instantiation bypasses ChunkBuilder
        # See: docs/ARCHITECTURE_VIOLATION_PromptInterceptionEngine.md
        from schemas.engine.prompt_interception_engine import PromptInterceptionRequest
        engine = PromptInterceptionEngine()

        request_obj = PromptInterceptionRequest(
            input_prompt=input_prompt,
            input_context=input_context,
            style_prompt=style_prompt,
            task_instruction=task_instruction,  # Session 134: Meta-instruction
            model=model,
            debug=data.get('debug', False)
        )
        
        response = asyncio.run(engine.process_request(request_obj))
        
        if response.success:
            return jsonify({
                'status': 'success',
                'input_prompt': input_prompt,
                'output_str': response.output_str,
                'model_used': response.model_used,
                'metadata': {
                    'output_float': response.output_float,
                    'output_int': response.output_int,
                    'output_binary': response.output_binary
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'error': response.error
            }), 500
            
    except Exception as e:
        logger.error(f"Test-Pipeline Fehler: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@schema_bp.route('/schemas', methods=['GET'])
def list_schemas():
    """Verfügbare Schemas auflisten"""
    try:
        init_schema_engine()

        schemas = []
        for schema_name in pipeline_executor.get_available_schemas():
            schema_info = pipeline_executor.get_schema_info(schema_name)
            if schema_info:
                schemas.append(schema_info)

        return jsonify({
            'status': 'success',
            'schemas': schemas
        })

    except Exception as e:
        logger.error(f"Schema-List Fehler: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@schema_bp.route('/chunk-metadata', methods=['GET'])
def get_chunk_metadata():
    """Serve chunk metadata for hover cards (Q/Spd ratings + durations from chunks)"""
    try:
        chunks = {}
        chunks_dir = Path(__file__).parent.parent.parent / "schemas" / "chunks"

        # JSON chunks
        for chunk_file in chunks_dir.glob("output_*.json"):
            try:
                with open(chunk_file, 'r') as f:
                    chunk = json.load(f)
                    chunk_name = chunk.get('name', chunk_file.stem)

                    chunks[chunk_name] = {
                        'name': chunk_name,
                        'meta': chunk.get('meta', {})
                    }
            except Exception as e:
                logger.error(f"Error loading chunk {chunk_file}: {e}")
                continue

        # Python chunks — extract CHUNK_META
        for chunk_file in chunks_dir.glob("output_*.py"):
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(chunk_file.stem, chunk_file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                chunk_meta = getattr(mod, 'CHUNK_META', None)
                if chunk_meta:
                    chunk_name = chunk_meta.get('name', chunk_file.stem)
                    chunks[chunk_name] = {
                        'name': chunk_name,
                        'meta': chunk_meta
                    }
            except Exception as e:
                logger.error(f"Error loading Python chunk {chunk_file}: {e}")
                continue

        return jsonify(chunks)

    except Exception as e:
        logger.error(f"Chunk metadata error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# ============================================================================
# BACKWARD COMPATIBILITY ENDPOINTS (Legacy Frontend Support)
# These endpoints have NO URL prefix and match the old workflow_routes.py API
# ============================================================================
# STATUS: DEPRECATED as of 2025-10-28
# REASON: workflow.js (dropdown system) replaced by workflow-browser.js (cards)
# KEEP: /pipeline_configs_metadata (used by workflow-browser.js)
# REMOVE: /list_workflows, /workflow_metadata (only used by deprecated workflow.js)
# ============================================================================

# DEPRECATED: /list_workflows - Only used by old dropdown system (workflow.js.obsolete)
# @schema_compat_bp.route('/list_workflows', methods=['GET'])
# def list_workflows_compat():
#     """List available Schema-Pipeline configs (replaces workflow_routes.py)"""
#     try:
#         init_schema_engine()
#
#         # Return Schema-Pipelines as dev/config_name format (matches old API)
#         schema_workflows = []
#         for schema_name in pipeline_executor.get_available_schemas():
#             schema_workflows.append(f"dev/{schema_name}")
#
#         logger.info(f"Schema-Pipelines returned: {len(schema_workflows)}")
#
#         return jsonify({"workflows": schema_workflows})
#     except Exception as e:
#         logger.error(f"Error listing workflows: {e}")
#         return jsonify({"error": "Failed to list workflows"}), 500


# DEPRECATED: /workflow_metadata - Only used by old dropdown system (workflow.js.obsolete)
# @schema_compat_bp.route('/workflow_metadata', methods=['GET'])
# def workflow_metadata_compat():
#     """Get Schema-Pipeline metadata (replaces workflow_routes.py)"""
#     try:
#         init_schema_engine()
#
#         metadata = {
#             "categories": {
#                 "dev": {
#                     "de": "Schema-Pipelines (Interception Configs)",
#                     "en": "Schema Pipelines (Interception Configs)"
#                 }
#             },
#             "workflows": {}
#         }
#
#         # Add Schema-Pipeline metadata
#         for schema_name in pipeline_executor.get_available_schemas():
#             schema_info = pipeline_executor.get_schema_info(schema_name)
#             if schema_info:
#                 # Format: dev_config_name (workflow.js expects this format)
#                 workflow_id = f"dev_{schema_name}"
#
#                 config = schema_info.get('config', {})
#                 meta = config.get('meta', {})
#
#                 metadata["workflows"][workflow_id] = {
#                     "category": "dev",
#                     "name": config.get('name', {'de': schema_name, 'en': schema_name}),
#                     "description": config.get('description', {
#                         'de': schema_info.get('description', ''),
#                         'en': schema_info.get('description', '')
#                     }),
#                     "file": f"dev/{schema_name}"
#                 }
#
#         logger.info(f"Schema-Pipeline metadata returned: {len(metadata['workflows'])} configs")
#
#         return jsonify(metadata)
#     except Exception as e:
#         logger.error(f"Error getting workflow metadata: {e}")
#         return jsonify({"error": "Failed to get workflow metadata"}), 500


@schema_compat_bp.route('/pipeline_configs_metadata', methods=['GET'])
def pipeline_configs_metadata_compat():
    """
    Get metadata for all pipeline configs (Expert Mode Karten-Browser)
    Reads directly from config files
    """
    try:
        init_schema_engine()

        # Read metadata directly from config files
        configs_metadata = []
        schemas_path = Path(__file__).parent.parent.parent / "schemas"
        configs_path = schemas_path / "configs"

        if not configs_path.exists():
            return jsonify({"error": "Configs directory not found"}), 404

        # Recursive glob to support subdirectories (interception/, output/, user_configs/)
        for config_file in sorted(configs_path.glob("**/*.json")):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                # Filter: Only show active Stage 2 (interception) configs
                # Skip: output configs, deactivated configs, user configs, other stages
                relative_path_str = str(config_file.relative_to(configs_path))

                # Skip deactivated configs (in deactivated/ subdirectory)
                if "deactivated" in relative_path_str:
                    continue

                # Skip user configs (in user_configs/ subdirectory)
                if "user_configs" in relative_path_str:
                    continue

                # Only show interception configs (Stage 2)
                stage = config_data.get("meta", {}).get("stage", "")
                if stage != "interception":
                    continue  # Don't show output configs or other stages in legacy frontend

                # Calculate config ID (relative path without .json)
                # Example: interception/dada.json → "dada"
                #          user_configs/doej/test.json → "u_doej_test" (handled by config_loader)
                relative_path = config_file.relative_to(configs_path)
                parts = relative_path.parts

                # Use same naming logic as config_loader.py
                if len(parts) >= 2 and parts[0] == "user_configs":
                    # User config: u_username_filename
                    username = parts[1]
                    stem = config_file.stem
                    config_id = f"u_{username}_{stem}"
                    owner = username  # User-created
                elif parts[0] in ["interception", "output"]:
                    # Main system configs: just the stem
                    config_id = config_file.stem
                    owner = "system"  # System config
                else:
                    # Other system configs: keep path
                    config_id = str(relative_path.with_suffix('')).replace('\\', '/')
                    owner = "system"  # System config

                # Extract metadata fields directly from config
                metadata = {
                    "id": config_id,
                    "name": config_data.get("name", {}),  # Multilingual
                    "description": config_data.get("description", {}),  # Multilingual
                    "category": config_data.get("category", {}),  # Multilingual
                    "pipeline": config_data.get("pipeline", "unknown")
                }

                # Add optional metadata fields if present
                if "display" in config_data:
                    metadata["display"] = config_data["display"]

                if "tags" in config_data:
                    metadata["tags"] = config_data["tags"]

                if "audience" in config_data:
                    metadata["audience"] = config_data["audience"]

                if "media_preferences" in config_data:
                    metadata["media_preferences"] = config_data["media_preferences"]

                # Add meta fields (includes stage, owner, etc.)
                if "meta" in config_data:
                    metadata["meta"] = config_data["meta"]
                else:
                    metadata["meta"] = {}

                # Inject owner if not present
                if "owner" not in metadata["meta"]:
                    metadata["meta"]["owner"] = owner

                configs_metadata.append(metadata)

            except Exception as e:
                logger.error(f"Error reading config {config_file}: {e}")
                continue

        logger.info(f"Loaded metadata for {len(configs_metadata)} pipeline configs")

        return jsonify({"configs": configs_metadata})

    except Exception as e:
        logger.error(f"Error loading pipeline configs metadata: {e}")
        return jsonify({"error": "Failed to load configs metadata"}), 500


@schema_compat_bp.route('/pipeline_configs_with_properties', methods=['GET'])
def pipeline_configs_with_properties():
    """
    Get metadata for all pipeline configs WITH properties for Phase 1 property-based selection.
    Returns configs with properties field + property pairs structure.

    NEW: Phase 1 Property Quadrants implementation (Session 35)
    """
    try:
        init_schema_engine()

        # Feature flag for property symbols (Session 40)
        ENABLE_PROPERTY_SYMBOLS = True  # Set to False to disable symbols

        # Property pairs v2 with symbols and tooltips (Session 40)
        property_pairs_v2 = [
            {
                "id": 1,
                "pair": ["chill", "chaotic"],  # NOTE: Labels use predictable/unpredictable. IDs kept for backward compat (24+ configs)
                "symbols": {"chill": "🎯", "chaotic": "🎲"},
                "labels": {
                    "de": {"chill": "vorhersagbar", "chaotic": "unvorhersagbar"},
                    "en": {"chill": "predictable", "chaotic": "unpredictable"}
                },
                "tooltips": {
                    "de": {
                        "chill": "Output ist erwartbar und steuerbar",
                        "chaotic": "Output ist unvorhersehbar und unberechenbar"
                    },
                    "en": {
                        "chill": "Output is expected and controllable",
                        "chaotic": "Output is unpredictable and unforeseeable"
                    }
                }
            },
            {
                "id": 2,
                "pair": ["narrative", "algorithmic"],
                "symbols": {"narrative": "✍️", "algorithmic": "🔢"},
                "labels": {
                    "de": {"narrative": "semantisch", "algorithmic": "syntaktisch"},
                    "en": {"narrative": "semantic", "algorithmic": "syntactic"}
                },
                "tooltips": {
                    "de": {
                        "narrative": "Schreiben: Bedeutung und Kontext",
                        "algorithmic": "Rechnen: Regeln und Schritte"
                    },
                    "en": {
                        "narrative": "Writing: meaning and context",
                        "algorithmic": "Calculating: rules and steps"
                    }
                }
            },
            {
                "id": 3,
                "pair": ["historical", "contemporary"],
                "symbols": {"historical": "🏛️", "contemporary": "🏙️"},
                "labels": {
                    "de": {"historical": "museal", "contemporary": "lebendig"},
                    "en": {"historical": "museum", "contemporary": "contemporary"}
                },
                "tooltips": {
                    "de": {
                        "historical": "Museumsgebäude (historisch, eingefroren)",
                        "contemporary": "Wolkenkratzer (gegenwärtig, lebendig)"
                    },
                    "en": {
                        "historical": "Museum building (historical, frozen)",
                        "contemporary": "Skyscraper (contemporary, alive)"
                    }
                }
            },
            {
                "id": 4,
                "pair": ["explore", "create"],
                "symbols": {"explore": "🔍", "create": "🎨"},
                "labels": {
                    "de": {"explore": "austesten", "create": "artikulieren"},
                    "en": {"explore": "test AI", "create": "articulate"}
                },
                "tooltips": {
                    "de": {
                        "explore": "KI challengen, kritisch hinterfragen (Detektiv)",
                        "create": "Künstlerisch ausdrücken, gestalten (Künstler)"
                    },
                    "en": {
                        "explore": "Challenge AI, critically question (detective)",
                        "create": "Artistically express, create (artist)"
                    }
                }
            },
            {
                "id": 5,
                "pair": ["playful", "serious"],
                "symbols": {"playful": "🪁", "serious": "🔧"},
                "labels": {
                    "de": {"playful": "verspielt", "serious": "ernst"},
                    "en": {"playful": "playful", "serious": "serious"}
                },
                "tooltips": {
                    "de": {
                        "playful": "Spielerisch, viele Freiheitsgrade (Drachen)",
                        "serious": "Ernst, strukturiert, Genrekonventionen (Werkzeug)"
                    },
                    "en": {
                        "playful": "Playful, many degrees of freedom (kite)",
                        "serious": "Serious, structured, genre conventions (tool)"
                    }
                }
            }
        ]

        # Legacy property pairs (for backward compatibility)
        property_pairs = [
            ["chill", "chaotic"],
            ["narrative", "algorithmic"],
            ["historical", "contemporary"],
            ["explore", "create"],
            ["playful", "serious"]
        ]

        # Read metadata directly from config files
        configs_metadata = []
        schemas_path = Path(__file__).parent.parent.parent / "schemas"
        configs_path = schemas_path / "configs"

        if not configs_path.exists():
            return jsonify({"error": "Configs directory not found"}), 404

        # Excluded directories (deactivated, deprecated, backups, tmp, etc.)
        EXCLUDED_DIRS = {"temporarily_deactivated", "deactivated", "deprecated", "archive", ".obsolete", "tmp", "backup", "backups", "backup_20251114"}

        # Recursive glob to support subdirectories (interception/, output/, user_configs/)
        for config_file in sorted(configs_path.glob("**/*.json")):
            try:
                # Filter: Skip configs in excluded directories
                relative_path = config_file.relative_to(configs_path)
                if any(excluded in relative_path.parts for excluded in EXCLUDED_DIRS):
                    logger.debug(f"Skipping {config_file.name} - in excluded directory")
                    continue

                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                # Filter: Skip output configs (system-only, not user-facing)
                stage = config_data.get("meta", {}).get("stage", "")
                if stage == "output":
                    continue  # Don't show output configs in frontend

                # Filter: Only include configs with properties (for Phase 1 property selection)
                if "properties" not in config_data:
                    logger.debug(f"Skipping {config_file.name} - no properties field")
                    continue

                # Calculate config ID (relative path without .json)
                parts = relative_path.parts

                # Use same naming logic as config_loader.py
                if len(parts) >= 2 and parts[0] == "user_configs":
                    # User config: u_username_filename
                    username = parts[1]
                    stem = config_file.stem
                    config_id = f"u_{username}_{stem}"
                    owner = username  # User-created
                elif parts[0] in ["interception", "output"]:
                    # Main system configs: just the stem
                    config_id = config_file.stem
                    owner = "system"  # System config
                else:
                    # Other system configs: keep path
                    config_id = str(relative_path.with_suffix('')).replace('\\', '/')
                    owner = "system"  # System config

                # Helper function to create short description
                def make_short_description(long_desc, max_length=220):
                    """
                    Create short description from long one.
                    Extracts complete sentences that fit within max_length.
                    Preserves consistency - doesn't invent new content.
                    Kid-friendly length that provides enough context to understand.

                    Strategy:
                    1. Keep full description if it fits (<= max_length)
                    2. Extract first sentence if it fits
                    3. Extract first 2 sentences if they fit
                    4. Never truncate mid-sentence - use first sentence only
                    """
                    if not long_desc:
                        return long_desc

                    # If full description fits, keep it
                    if len(long_desc) <= max_length:
                        return long_desc

                    # Split into sentences (handle '. ' and '.\n')
                    sentences = long_desc.replace('.\n', '. ').split('. ')

                    # Edge case: no proper sentences (no periods)
                    if len(sentences) == 1:
                        # Truncate at word boundary
                        if len(long_desc) > max_length:
                            truncated = long_desc[:max_length].rsplit(' ', 1)[0]
                            return truncated.strip() + '...'
                        return long_desc

                    # Try first sentence
                    first_sentence = sentences[0] + '.'
                    if len(first_sentence) <= max_length:
                        # Try adding second sentence
                        if len(sentences) >= 2:
                            two_sentences = first_sentence + ' ' + sentences[1] + '.'
                            if len(two_sentences) <= max_length:
                                return two_sentences
                        # Return just first sentence
                        return first_sentence

                    # First sentence too long - truncate at word boundary
                    truncated = long_desc[:max_length].rsplit(' ', 1)[0]
                    return truncated.strip() + '...'

                # Extract metadata fields with properties
                metadata = {
                    "id": config_id,
                    "name": config_data.get("name", {}),  # Multilingual
                    "description": config_data.get("description", {}),  # Multilingual (long version)
                    "category": config_data.get("category", {}),  # Multilingual
                    "pipeline": config_data.get("pipeline", "unknown"),
                    "properties": config_data.get("properties", [])  # NEW: Properties for filtering
                }

                # Add short descriptions for tile display
                long_desc = config_data.get("description", {})
                if isinstance(long_desc, dict):
                    metadata["short_description"] = {
                        lang: make_short_description(text)
                        for lang, text in long_desc.items()
                    }
                else:
                    metadata["short_description"] = make_short_description(long_desc)

                # Add display metadata (icon, color, difficulty, etc.)
                if "display" in config_data:
                    display = config_data["display"]
                    metadata["icon"] = display.get("icon", "🎨")
                    metadata["color"] = display.get("color", "#888888")
                    metadata["difficulty"] = display.get("difficulty", 3)

                    # Phase 1 description (agency-oriented) - NEW
                    if "phase1_description" in display:
                        metadata["phase1_description"] = display["phase1_description"]
                    else:
                        # Fallback to regular description
                        metadata["phase1_description"] = config_data.get("description", {})

                # Add tags
                if "tags" in config_data:
                    metadata["tags"] = config_data["tags"]

                # Add audience metadata
                if "audience" in config_data:
                    metadata["audience"] = config_data["audience"]

                # Add media preferences
                if "media_preferences" in config_data:
                    metadata["media_preferences"] = config_data["media_preferences"]

                # Session 116: Add LoRA info from meta for frontend display
                meta = config_data.get("meta", {})
                if meta.get("loras"):
                    metadata["loras"] = meta["loras"]

                # Add owner info
                metadata["owner"] = owner

                configs_metadata.append(metadata)

            except Exception as e:
                logger.error(f"Error reading config {config_file}: {e}")
                continue

        logger.info(f"Loaded {len(configs_metadata)} configs with properties for Phase 1")

        # Return with or without symbols based on feature flag (Session 40)
        if ENABLE_PROPERTY_SYMBOLS:
            return jsonify({
                "configs": configs_metadata,
                "property_pairs": property_pairs_v2,
                "symbols_enabled": True
            })
        else:
            return jsonify({
                "configs": configs_metadata,
                "property_pairs": property_pairs,
                "symbols_enabled": False
            })

    except Exception as e:
        logger.error(f"Error loading configs with properties: {e}")
        return jsonify({"error": "Failed to load configs with properties"}), 500


@schema_compat_bp.route('/api/config/<config_id>/context', methods=['GET'])
def get_config_context(config_id):
    """
    Get the context field for a specific config (Phase 2 - Meta-Prompt Editing)

    Returns the multilingual context field: {en: "...", de: "..."}
    or string if not yet translated.

    NEW: Phase 2 Multilingual Context Editing (Session 36)
    """
    try:
        init_schema_engine()

        # Load config
        config = config_loader.get_config(config_id)

        if not config:
            return jsonify({"error": f"Config not found: {config_id}"}), 404

        # Get context from config
        context = config.context if hasattr(config, 'context') else None

        if context is None:
            return jsonify({"error": f"Config {config_id} has no context field"}), 404

        # Return context (can be string or {en: ..., de: ...})
        return jsonify({
            "config_id": config_id,
            "context": context
        })

    except Exception as e:
        logger.error(f"Error loading context for config {config_id}: {e}")
        return jsonify({"error": f"Failed to load context: {str(e)}"}), 500


@schema_compat_bp.route('/api/config/<config_id>/pipeline', methods=['GET'])
def get_config_pipeline(config_id):
    """
    Get pipeline structure metadata for a config (Phase 2 - Dynamic UI)

    Returns pipeline metadata to determine:
    - How many input bubbles to show (input_requirements)
    - Whether to show context editing bubble (requires_interception_prompt)
    - Pipeline stage and type for UI adaptation

    NEW: Phase 2 Dynamic Pipeline Structure (Session 36)
    """
    try:
        init_schema_engine()

        # Load config
        config = config_loader.get_config(config_id)

        if not config:
            return jsonify({"error": f"Config not found: {config_id}"}), 404

        # Get pipeline metadata
        pipeline = config_loader.pipelines.get(config.pipeline_name)

        if not pipeline:
            return jsonify({"error": f"Pipeline not found: {config.pipeline_name}"}), 404

        # Return pipeline structure metadata
        return jsonify({
            "config_id": config_id,
            "pipeline_name": pipeline.name,
            "pipeline_type": pipeline.pipeline_type,
            "pipeline_stage": pipeline.pipeline_stage,
            "requires_interception_prompt": pipeline.requires_interception_prompt,
            "input_requirements": pipeline.input_requirements or {},
            "description": pipeline.description
        })

    except Exception as e:
        logger.error(f"Error loading pipeline metadata for config {config_id}: {e}")
        return jsonify({"error": f"Failed to load pipeline metadata: {str(e)}"}), 500


@schema_compat_bp.route('/api/image/analyze', methods=['POST'])
def analyze_image_endpoint():
    """
    Stage 5: Universal Image Analysis

    Analyzes an image using vision models with multiple theoretical frameworks.
    Simple endpoint that calls universal helper function.

    Request:
        {
            "run_id": "uuid",                       // Load image from recorder
            "analysis_type": "bildwissenschaftlich", // Framework (optional, default: bildwissenschaftlich)
            "prompt": "custom prompt"               // Optional custom prompt
        }

    Supported analysis_type values:
        - 'bildungstheoretisch': Jörissen/Marotzki (Bildungspotenziale)
        - 'bildwissenschaftlich': Panofsky (art-historical, default)
        - 'ethisch': Ethical analysis
        - 'kritisch': Decolonial & critical media studies

    Response:
        {
            "success": true,
            "analysis": "analysis text...",
            "analysis_type": "bildwissenschaftlich",
            "run_id": "uuid"
        }
    """
    from my_app.utils.image_analysis import analyze_image_from_run

    try:
        data = request.get_json()
        run_id = data.get('run_id')
        analysis_type = data.get('analysis_type', 'bildwissenschaftlich')  # Default: Panofsky
        custom_prompt = data.get('prompt')  # Optional

        if not run_id:
            return jsonify({'success': False, 'error': 'run_id required'}), 400

        # Validate analysis_type
        valid_types = ['bildungstheoretisch', 'bildwissenschaftlich', 'ethisch', 'kritisch']
        if analysis_type not in valid_types:
            return jsonify({'success': False, 'error': f'Invalid analysis_type. Must be one of: {valid_types}'}), 400

        logger.info(f"[IMAGE-ANALYSIS] Starting {analysis_type} analysis for run_id: {run_id}")

        # Analyze image
        analysis_text = analyze_image_from_run(run_id, prompt=custom_prompt, analysis_type=analysis_type)

        return jsonify({
            'success': True,
            'analysis': analysis_text,
            'analysis_type': analysis_type,
            'run_id': run_id
        })

    except FileNotFoundError as e:
        logger.error(f"[IMAGE-ANALYSIS] Not found: {e}")
        return jsonify({'success': False, 'error': str(e)}), 404

    except Exception as e:
        logger.error(f"[IMAGE-ANALYSIS] Failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
