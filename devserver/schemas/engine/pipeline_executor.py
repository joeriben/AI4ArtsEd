"""
Pipeline-Executor: Central orchestration for config-based pipelines
REFACTORED for new architecture (config_loader instead of schema_registry)
ENHANCED with 4-Stage Pre-Interception System
ENHANCED with Wikipedia Research capability
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
import time
import json

from .config_loader import config_loader, ResolvedConfig
from .chunk_builder import ChunkBuilder
from .backend_router import BackendRouter, BackendRequest, BackendResponse, BackendType
from .wikipedia_processor import extract_markers, format_wiki_content, remove_markers

logger = logging.getLogger(__name__)

# Wikipedia status for real-time UI feedback, keyed by run_id for per-request isolation.
# Key: run_id (str), Value: {'status': 'lookup'|'complete'|None, 'terms': [...], 'timestamp': float}
# Callers without run_id fall back to key 'current' (backward compat).
WIKIPEDIA_STATUS = {}

def _cleanup_wikipedia_status(max_age_seconds: int = 300):
    """Remove WIKIPEDIA_STATUS entries older than max_age_seconds."""
    import time
    now = time.time()
    # list() and pop(), because this runs on every execute_pipeline call: two
    # threads can be in here at once, and a third can be adding an entry from a
    # wiki-enabled interception. Iterating the live dict raises RuntimeError, a
    # second del of the same key raises KeyError, and either one escaping here
    # would abort an unrelated generation for the sake of housekeeping.
    stale = [k for k, v in list(WIKIPEDIA_STATUS.items())
             if isinstance(v, dict) and now - v.get('timestamp', 0) > max_age_seconds]
    for k in stale:
        WIKIPEDIA_STATUS.pop(k, None)


def _wikipedia_metadata(context: 'PipelineContext') -> Dict[str, Any]:
    """What the model had to look up while it wrote this run.

    A text resting on retrieved articles is not the same kind of text as one
    written from the model alone, and nothing in the text says which it is -- so
    a reader laying two runs side by side is told. BOTH success returns carry
    it: the recursive path used to return neither field, and a run through it
    looked exactly like a run that had looked nothing up.

    One entry per (term, language) that was actually asked of Wikipedia, in ask
    order, each with whether an article came back. The count is the length of
    that list rather than a second tally, because a number and a list counting
    different things disagree -- and they did, wherever one term was asked in
    two languages.

    Read from the context's own wikipedia field, never from custom_placeholders:
    see PipelineContext for what a model can write into that dict.
    """
    terms = list(context.wikipedia.get('terms') or [])
    return {
        "wikipedia_lookups": len(terms),
        "wikipedia_terms": terms,
    }


class PipelineStatus(Enum):
    """Pipeline execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

@dataclass
class PipelineStep:
    """Single pipeline step"""
    step_id: str
    chunk_name: str
    status: PipelineStatus = PipelineStatus.PENDING
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PipelineContext:
    """Pipeline context for data exchange between steps"""
    input_text: str
    user_input: str
    previous_outputs: List[str] = field(default_factory=list)
    custom_placeholders: Dict[str, Any] = field(default_factory=dict)
    pipeline_metadata: Dict[str, Any] = field(default_factory=dict)
    # What this run looked up while it was written: 'terms' (one entry per ask,
    # in ask order), 'asked', 'lookups', 'status'. Written by the lookup code
    # below and by nothing else.
    #
    # Its own field, because custom_placeholders is not the executor's: every
    # step's output is JSON-parsed key by key into that dict, so a model
    # answering {"_wikipedia_fetched_terms": [{"term": "Bauhaus", ...}]} wrote
    # the record of its own research -- and one level up, that record decides
    # whether a run still hands the user their prompt back verbatim. The same
    # dict is injected into every chunk's backend parameters, so the
    # bookkeeping travelled into the next model request as well.
    wikipedia: Dict[str, Any] = field(default_factory=dict)
    
    def get_previous_output(self) -> str:
        """Get last pipeline output"""
        return self.previous_outputs[-1] if self.previous_outputs else self.input_text
    
    def add_output(self, output: str) -> None:
        """Add pipeline output"""
        self.previous_outputs.append(output)

@dataclass
class PipelineResult:
    """Pipeline execution result"""
    config_name: str  # Changed from schema_name
    status: PipelineStatus
    steps: List[PipelineStep]
    final_output: str = ""  # Pipeline output as string (JSON parsing goes to context.custom_placeholders)
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Pipeline succeeded if status is COMPLETED"""
        return self.status == PipelineStatus.COMPLETED

class PipelineExecutor:
    """Central pipeline orchestration"""
    
    def __init__(self, schemas_path: Path):
        self.schemas_path = schemas_path
        self.config_loader = config_loader
        self.chunk_builder = ChunkBuilder(schemas_path)
        self.backend_router = BackendRouter()
        self._initialized = False
        
    def initialize(self, llm_service=None, workflow_logic_service=None, comfyui_service=None):
        """Initialize pipeline executor with legacy services"""
        self.config_loader.initialize(self.schemas_path)
        self.backend_router.initialize(
            llm_service=llm_service,
            workflow_logic_service=workflow_logic_service,
            comfyui_service=comfyui_service
        )
        self._initialized = True
        logger.info("Pipeline-Executor initialized")
    
    async def execute_pipeline(
        self,
        config_name: str,
        input_text: str,
        user_input: Optional[str] = None,
        safety_level: str = 'kids',
        tracker=None,
        config_override=None,  # Phase 2: Optional pre-modified config
        context_override: Optional[PipelineContext] = None,  # Multi-stage: Pre-populated context
        seed_override: Optional[int] = None,  # Phase 4: Intelligent seed for media generation
        input_image: Optional[str] = None,  # IMG2IMG support - path to input image
        input_image1: Optional[str] = None,  # Multi-image support - path to image 1
        input_image2: Optional[str] = None,  # Multi-image support - path to image 2 (optional)
        input_image3: Optional[str] = None,  # Multi-image support - path to image 3 (optional)
        alpha_factor: Optional[float] = None,  # Surrealizer: T5-CLIP fusion alpha factor
        run_id: Optional[str] = None,  # Per-request key for WIKIPEDIA_STATUS isolation
        context_language: Optional[str] = None  # Detected INPUT language for i18n context variant (Stage 2)
    ) -> PipelineResult:
        """Execute complete pipeline with 4-Stage Pre-Interception System

        Args:
            config_override: Optional pre-modified Config object (Phase 2 user edits)
                           If provided, uses this instead of loading from config_name
        """
        # Auto-initialization if needed. _initialized is per instance, but the
        # ConfigLoader it guards is a process-wide singleton — so a second
        # executor (the routes held their own instance beside the module
        # singleton at the foot of this file until 2026-10-10; a test may still
        # build one) would otherwise re-read every pipeline and config from
        # disk, inside whichever request happened to come first. Ask the loader
        # instead of the flag; nothing in the platform reloads configs at runtime.
        if not self._initialized:
            if not self.config_loader.resolved_configs:
                logger.info("Auto-initialization: Config-Loader and Backend-Router")
                self.config_loader.initialize(self.schemas_path)
            self.backend_router.initialize()
            self._initialized = True

        # Clean up stale Wikipedia status entries
        _cleanup_wikipedia_status()

        logger.info(f"[PIPELINE] Executing config '{config_name}'")

        # Which output config the GPU work below belongs to, for the gate's
        # duration statistics. Here rather than at the callers: a media run
        # reaches this method from the streaming route, its non-streaming twin,
        # /execute/stage3-4, the canvas executor, the canvas route and the
        # interception surface, and a key set at some of them is a key that
        # depends on which button was pressed. The staged helper pipelines
        # (pre_interception/…, pre_output/…) are named with a prefix and are
        # not what a run is producing.
        if config_name and "/" not in config_name:
            try:
                from my_app.services.generation_abort import CURRENT_OUTPUT_CONFIG
                CURRENT_OUTPUT_CONFIG.set(config_name)
            except Exception:
                pass

        # Get config (use override if provided, otherwise load)
        if config_override:
            logger.info(f"[PHASE2] Using user-modified config override")
            resolved_config = config_override
        else:
            resolved_config = self.config_loader.get_config(config_name)

        if not resolved_config:
            return PipelineResult(
                config_name=config_name,
                status=PipelineStatus.FAILED,
                steps=[],
                error=f"Config '{config_name}' not found"
            )

        logger.info(f"Config '{config_name}' loaded: Pipeline='{resolved_config.pipeline_name}', Chunks={resolved_config.chunks}")

        # ====================================================================
        # DUMB EXECUTOR: Just execute chunks (Stage 1-3 in DevServer now)
        # ====================================================================

        # Create pipeline context (or use override for multi-stage workflows)
        if context_override:
            context = context_override
            logger.info(f"[CONTEXT-OVERRIDE] Using pre-populated context with {len(context.custom_placeholders)} custom placeholders")
        else:
            context = PipelineContext(
                input_text=input_text,
                user_input=user_input or input_text
            )

        # Phase 4: Add seed_override to context if provided
        if seed_override is not None:
            context.custom_placeholders['seed_override'] = seed_override
            logger.info(f"[PHASE4-SEED] Added seed_override to context: {seed_override}")

        # Add input_image to context if provided (IMG2IMG support)
        if input_image is not None:
            context.custom_placeholders['input_image'] = input_image
            logger.info(f"[IMG2IMG] Added input_image to context: {input_image}")

        # Add multi-image paths to context if provided
        if input_image1 is not None:
            context.custom_placeholders['input_image1'] = input_image1
            logger.info(f"[MULTI-IMG] Added input_image1 to context: {input_image1}")
        if input_image2 is not None:
            context.custom_placeholders['input_image2'] = input_image2
            logger.info(f"[MULTI-IMG] Added input_image2 to context: {input_image2}")
        if input_image3 is not None:
            context.custom_placeholders['input_image3'] = input_image3
            logger.info(f"[MULTI-IMG] Added input_image3 to context: {input_image3}")

        # Surrealizer: Add alpha_factor to context if provided (T5-CLIP fusion)
        if alpha_factor is not None:
            context.custom_placeholders['alpha_factor'] = alpha_factor
            logger.info(f"[SURREALIZER] Added alpha_factor to context: {alpha_factor}")

        # Plan pipeline steps
        steps = self._plan_pipeline_steps(resolved_config)

        result = await self._execute_pipeline_steps(config_name, steps, context, tracker=tracker, resolved_config=resolved_config, safety_level=safety_level, run_id=run_id, context_language=context_language)

        logger.info(f"Pipeline for config '{config_name}' completed: {result.status}")
        return result
    
    
    def _plan_pipeline_steps(self, resolved_config: ResolvedConfig) -> List[PipelineStep]:
        """Plan pipeline steps from resolved config"""
        steps = []

        for i, chunk_name in enumerate(resolved_config.chunks):
            step = PipelineStep(
                step_id=f"step_{i+1}_{chunk_name}",
                chunk_name=chunk_name
            )
            steps.append(step)

        logger.debug(f"Pipeline planned: {len(steps)} steps for config '{resolved_config.name}' (Pipeline: {resolved_config.pipeline_name})")
        return steps
    
    async def _execute_pipeline_steps(self, config_name: str, steps: List[PipelineStep], context: PipelineContext, tracker=None, *, resolved_config=None, safety_level=None, run_id=None, context_language=None) -> PipelineResult:
        """Execute pipeline steps sequentially (or recursively if pipeline supports it)"""

        # Check if this is a recursive pipeline
        if resolved_config and resolved_config.pipeline_name == 'text_transformation_recursive':
            return await self._execute_recursive_pipeline_steps(config_name, steps, context, tracker, resolved_config=resolved_config, safety_level=safety_level, run_id=run_id, context_language=context_language)

        # Normal sequential execution
        start_time = time.time()
        completed_steps = []

        for step in steps:
            try:
                step.status = PipelineStatus.RUNNING
                output = await self._execute_single_step(step, context, tracker=tracker, resolved_config=resolved_config, safety_level=safety_level, run_id=run_id, context_language=context_language)

                step.status = PipelineStatus.COMPLETED
                step.output_data = output
                context.add_output(output)

                # Log chunk output for debugging (especially useful for translate chunk)
                logger.info(f"[CHUNK-OUTPUT] {step.chunk_name}: {output[:200]}...")

                # AUTO-PARSE JSON: If output is valid JSON dict, add to custom_placeholders
                # This enables multi-stage workflows where Stage 2 outputs structured data
                try:
                    parsed_output = json.loads(output)
                    if isinstance(parsed_output, dict):
                        # Convert keys to uppercase for placeholder consistency
                        for key, value in parsed_output.items():
                            placeholder_key = key.upper()
                            context.custom_placeholders[placeholder_key] = value
                        logger.info(f"[JSON-AUTO-PARSE] Parsed output and added {len(parsed_output)} placeholders: {list(parsed_output.keys())}")
                except (json.JSONDecodeError, TypeError, ValueError):
                    # Not JSON or not a dict - treat as normal string output
                    pass

                completed_steps.append(step)
                logger.debug(f"Step {step.step_id} successful: {len(output)} chars output")

            except Exception as e:
                step.status = PipelineStatus.FAILED
                step.error = str(e)
                completed_steps.append(step)

                logger.error(f"Step {step.step_id} failed: {e}")

                return PipelineResult(
                    config_name=config_name,
                    status=PipelineStatus.FAILED,
                    steps=completed_steps,
                    error=f"Step {step.step_id} failed: {e}",
                    execution_time=time.time() - start_time
                )

        final_output = context.get_previous_output()

        # Merge backend metadata from last step (contains image_paths, seed, etc.)
        result_metadata = {
            "total_steps": len(steps),
            "input_length": len(context.input_text),
            "output_length": len(final_output),
            "pipeline_name": resolved_config.pipeline_name if resolved_config else None,
            **_wikipedia_metadata(context),
        }

        # Add backend metadata from last completed step
        if completed_steps:
            last_step_metadata = completed_steps[-1].metadata
            # Merge backend-specific keys into result metadata.
            #
            # This list is a gate, not a passthrough: a key a chunk returns and
            # this list does not name is dropped here without a word. That is
            # what happened to `latent_data` / `latent_meta` on 2026-09-04 — the
            # GPU service kept the picture's final latent and the client carried
            # it back, and every cell of Mean Images still said its mean was
            # taken pixel by pixel, because the latent stopped at this line.
            # A key that has to reach a run is named in THREE places: the chunk
            # that returns it, the route that writes it down, and here.
            for key in ['image_paths', 'seed', 'voice', 'model', 'media_type', 'parameters', 'filesystem_path', 'prompt_id', 'workflow_completed', 'legacy_workflow', 'media_files', 'outputs_metadata', 'workflow_json', 'download_all', 'chunk_name', 'chunk_type', 'image_data', 'audio_data', 'audio_format', 'video_data', 'video_format', 'mesh_data', 'mesh_format', 'size_bytes', 'model_id', 'backend', 'attention_data', 'probing_data', 'algebra_data', 'composable_data', 'reference_image', 'result_image', 'archaeology_data', 'f0_hz', 'latent_data', 'latent_meta']:
                if key in last_step_metadata:
                    result_metadata[key] = last_step_metadata[key]

        # AI-Origin Disclosure (EU AI Act Art. 50) at the one point every
        # caller passes: the base64 media in this metadata is what the page
        # displays AND what its download buttons hand out. The recorder marks
        # the copy that goes to disk; without this, the copy that goes to the
        # user carried nothing.
        try:
            from my_app.services.watermark_service import watermark_result_metadata
            watermark_result_metadata(result_metadata, {
                'model': result_metadata.get('model') or result_metadata.get('model_id'),
                'seed': result_metadata.get('seed'),
            })
        except Exception as e:
            logger.warning(f"[WATERMARK] not applied to result metadata ({e})")

        return PipelineResult(
            config_name=config_name,
            status=PipelineStatus.COMPLETED,
            steps=completed_steps,
            final_output=final_output,
            execution_time=time.time() - start_time,
            metadata=result_metadata
        )

    async def _execute_recursive_pipeline_steps(self, config_name: str, steps: List[PipelineStep], context: PipelineContext, tracker=None, *, resolved_config=None, safety_level=None, run_id=None, context_language=None) -> PipelineResult:
        """Execute recursive pipeline with internal loop (e.g., Stille Post)"""
        from .random_language_selector import get_random_language, get_language_name

        start_time = time.time()
        completed_steps = []

        # Read loop configuration from config parameters
        config_params = resolved_config.parameters or {}
        iterations = config_params.get('iterations', 8)
        use_random = config_params.get('use_random_languages', True)
        final_language = config_params.get('final_language', 'en')
        fixed_languages = config_params.get('languages', [])

        # The chain comes back to the language the person wrote in. Written as a
        # language code, `final_language` names a fixed one; written as "source",
        # it names theirs — context_language is the DETECTED input language the
        # Stage 2 caller resolved (`_detect_input_language`), so a German entry
        # returns German and a Korean one Korean.
        if isinstance(final_language, str) and final_language.strip().lower() == 'source':
            final_language = context_language or 'en'

        # A translation chain has nothing to look up, and the research offer is
        # made on EVERY step: nine steps would each invite <wiki> markers and
        # re-run themselves up to WIKIPEDIA_MAX_ITERATIONS times. Same opt-out
        # music generation uses (_execute_single_step reads this placeholder).
        context.custom_placeholders['_SKIP_WIKIPEDIA'] = True

        # Set stage 2 context for tracker
        if tracker:
            tracker.set_stage(2)

        # Generate language sequence
        if use_random:
            # Generate random language sequence
            # The source language stays out of the chain: a step that translates
            # into the language the text is already in changes nothing, and the
            # game is about losing the original, not revisiting it.
            languages = []
            for i in range(iterations - 1):
                lang = get_random_language(
                    exclude=(languages[-1:] if languages else []) + [final_language]
                )
                languages.append(lang)
            languages.append(final_language)  # Always end with final_language
            logger.info(f"[RECURSIVE-PIPELINE] Random language sequence: {languages}")
        else:
            # Use fixed language list from config
            languages = fixed_languages
            if len(languages) < iterations:
                logger.warning(f"[RECURSIVE-PIPELINE] Fixed languages list too short ({len(languages)} < {iterations}), padding with final_language")
                languages = languages + [final_language] * (iterations - len(languages))
            languages = languages[:iterations]  # Trim to iterations
            logger.info(f"[RECURSIVE-PIPELINE] Fixed language sequence: {languages}")

        # Set when a link answers with the refusal the safety prefix asks for.
        # It holds that link's number, and it ends the chain.
        from .instruction_selector import is_safety_refusal
        refused_at = None

        # Execute loop: one step per language
        for i, target_lang in enumerate(languages):
            step = PipelineStep(
                step_id=f"loop_{i+1}_{target_lang}",
                chunk_name=steps[0].chunk_name if steps else "manipulate"
            )

            try:
                step.status = PipelineStatus.RUNNING

                # Add target_language to custom placeholders
                context.custom_placeholders['TARGET_LANGUAGE'] = get_language_name(target_lang)
                context.custom_placeholders['TARGET_LANGUAGE_CODE'] = target_lang

                logger.info(f"[RECURSIVE-LOOP] Iteration {i+1}/{iterations}: Translating to {get_language_name(target_lang)} ({target_lang})")

                output = await self._execute_single_step(step, context, tracker=tracker, resolved_config=resolved_config, safety_level=safety_level, run_id=run_id, context_language=context_language)

                # A link that hands on nothing ends the chain. get_previous_output()
                # tests the LIST, not the element, so an empty string would be
                # carried on and every remaining link would be asked to translate
                # it -- and the run would still report itself complete.
                if not (output or '').strip():
                    raise ValueError(
                        f"link {i+1}/{iterations} into {get_language_name(target_lang)} "
                        f"returned no text"
                    )

                step.status = PipelineStatus.COMPLETED
                step.output_data = output
                context.add_output(output)

                completed_steps.append(step)
                logger.debug(f"[RECURSIVE-LOOP] Iteration {i+1} successful: {len(output)} chars")

                # A refusal is an answer to the person, not a text to translate.
                # The safety prefix tells the model to reply with this sentence
                # instead of transforming; carrying it into the next link would
                # paraphrase it through the remaining languages and hand back
                # mangled prose under a successful run. The single-call version
                # made the refusal the result, and so does this.
                if is_safety_refusal(output):
                    refused_at = i + 1
                    logger.info(f"[RECURSIVE-LOOP] Link {refused_at} refused; chain stops here")

                # Log iteration to tracker (if available)
                if tracker:
                    # Where this link read FROM: the link before it, and for the
                    # first one the language the person actually wrote in.
                    from_lang = languages[i-1] if i > 0 else (context_language or 'en')
                    to_lang = target_lang

                    # Extract metadata from step
                    model_used = step.metadata.get('model_used') if step.metadata else None
                    backend_type = step.metadata.get('backend_type') if step.metadata else None

                    # Calculate iteration execution time (approximate from step timing)
                    iteration_time = time.time() - start_time - sum(
                        getattr(s, 'execution_time', 0) or 0 for s in completed_steps[:-1]
                    )

                    try:
                        tracker.log_interception_iteration(
                            iteration_num=i+1,
                            result_text=output,
                            from_lang=from_lang,
                            to_lang=to_lang,
                            model_used=model_used or 'unknown',
                            config_used=config_name
                        )
                    except Exception as log_error:
                        logger.warning(f"[TRACKER] Failed to log iteration {i+1}: {log_error}")

                if refused_at is not None:
                    break

            except Exception as e:
                step.status = PipelineStatus.FAILED
                step.error = str(e)
                completed_steps.append(step)

                logger.error(f"[RECURSIVE-LOOP] Iteration {i+1} failed: {e}")

                return PipelineResult(
                    config_name=config_name,
                    status=PipelineStatus.FAILED,
                    steps=completed_steps,
                    error=f"Loop iteration {i+1} failed: {e}",
                    execution_time=time.time() - start_time,
                    # A broken chain is still a chain that ran: the links before
                    # the break are real model calls with real text, and their
                    # outputs sit in `steps`. Without the sequence and the count
                    # beside them the record could not say WHICH link broke or
                    # what it was going into.
                    metadata={
                        "pipeline_name": resolved_config.pipeline_name,
                        "iterations": iterations,
                        "language_sequence": languages,
                        "links_completed": len(completed_steps) - 1,
                        "failed_at": i + 1,
                    }
                )

        final_output = context.get_previous_output()

        # The recursive path is a second success return. It carries no media
        # today, but a comment claiming "the one point every caller passes"
        # was only true of the sequential one.
        recursive_metadata = {}

        return PipelineResult(
            config_name=config_name,
            status=PipelineStatus.COMPLETED,
            steps=completed_steps,
            final_output=final_output,
            execution_time=time.time() - start_time,
            metadata={
                **recursive_metadata,
                **_wikipedia_metadata(context),
                "total_steps": len(completed_steps),
                "input_length": len(context.input_text),
                "output_length": len(final_output),
                "pipeline_name": resolved_config.pipeline_name,
                "iterations": iterations,
                "language_sequence": languages,
                # How far the chain actually got. Equal to `iterations` on an
                # ordinary run; smaller when a link refused, and then this says
                # the output is that refusal rather than a translation.
                "links_completed": len(completed_steps),
                "safety_refusal_at": refused_at,
            }
        )
    
    
    async def _execute_single_step(self, step: PipelineStep, context: PipelineContext, tracker=None, *, resolved_config=None, safety_level=None, run_id=None, context_language=None) -> str:
        """Execute single pipeline step with Wikipedia research capability

        Wikipedia Research (always available; the model asks when it lacks knowledge):
        - After LLM output, check for <wiki> markers
        - If markers found, fetch Wikipedia content and re-execute
        - Maximum iterations configurable (WIKIPEDIA_MAX_ITERATIONS)
        - Language auto-detected from input (falls back to WIKIPEDIA_FALLBACK_LANGUAGE)
        - Opt-OUT per request via _SKIP_WIKIPEDIA (music generation, the chain
          translation and the translation into English have nothing to research)

        This is not a capability a config grants. Whether knowledge is missing is
        something only the model can tell, and it tells us by emitting a marker;
        a flag in a config file cannot know it in advance. Between 2026-02-07 and
        2026-08-15 it was an opt-in, and 17 configs never got the flag — including
        every path a run takes when nobody picked a perspective.
        """
        import config
        from my_app.services.wikipedia_service import get_wikipedia_service
        from .wikipedia_prompt_helper import get_wikipedia_instructions, build_wikipedia_context_block

        # Wikipedia: always on. Opt-OUT per request for pipelines with nothing
        # to research (music generation, the chain translation and the
        # translation into English set _SKIP_WIKIPEDIA).
        wikipedia_enabled = not context.custom_placeholders.get('_SKIP_WIKIPEDIA')

        # Wikipedia iteration tracking
        wiki_iteration = 0
        if wikipedia_enabled:
            max_wiki_iterations = getattr(config, 'WIKIPEDIA_MAX_ITERATIONS', 3)
            max_lookups = getattr(config, 'WIKIPEDIA_MAX_LOOKUPS_PER_ITERATION', 5)
        else:
            max_wiki_iterations = 0
            max_lookups = 0
            logger.info("[WIKI] Research skipped for this request (_SKIP_WIKIPEDIA)")

        # Key for WIKIPEDIA_STATUS: use run_id if provided, else 'current' for backward compat
        wiki_status_key = run_id or 'current'

        fallback_language = getattr(config, 'WIKIPEDIA_FALLBACK_LANGUAGE', 'de')

        # Get input language from context (set by Stage 1 translation)
        input_language = context.custom_placeholders.get('INPUT_LANGUAGE', fallback_language)

        # Initialize WIKIPEDIA_CONTEXT if wikipedia is enabled
        if wikipedia_enabled and 'WIKIPEDIA_CONTEXT' not in context.custom_placeholders:
            context.custom_placeholders['WIKIPEDIA_CONTEXT'] = ''

        # Track already-fetched terms across iterations to prevent duplicates
        fetched_terms: set = set()  # (term_lower, lang)

        while True:
            chunk_context = {
                "input_text": context.input_text,
                "user_input": context.user_input,
                "previous_output": context.get_previous_output(),
                "custom_placeholders": context.custom_placeholders
            }

            # Debug: Log chunk context
            logger.info(f"[CHUNK-CONTEXT] input_text: '{chunk_context['input_text'][:50]}...'")
            logger.info(f"[CHUNK-CONTEXT] previous_output: '{chunk_context['previous_output'][:50]}...'")

            # The chunk builder reads the TYPE of the task instruction off the
            # pipeline. This call left the pipeline out, so every step of every
            # pipeline fell back to "artistic_transformation" and a pipeline
            # that declares its own type declared it into the void.
            # The chained translation is the first one that owes a different
            # type than "transform this": each link was told "ALWAYS reply in
            # the language of the Input" while the same prompt named a target
            # language, and the model spent its answer on the contradiction.
            # The five other pipelines that declare a type keep the instruction
            # they have -- four name a type instruction_selector leaves
            # undefined, and one names the default.
            pipeline_obj = (
                self.config_loader.get_pipeline(resolved_config.pipeline_name)
                if getattr(resolved_config, 'pipeline_name', None)
                else None
            )

            chunk_request = self.chunk_builder.build_chunk(
                chunk_name=step.chunk_name,
                resolved_config=resolved_config,
                context=chunk_context,
                pipeline=pipeline_obj,
                safety_level=safety_level,
                context_language=context_language
            )

            # Wikipedia: append instructions + context to prompt if enabled
            if wikipedia_enabled and isinstance(chunk_request['prompt'], str):
                wiki_context = context.custom_placeholders.get('WIKIPEDIA_CONTEXT', '')
                wiki_context_block = build_wikipedia_context_block(wiki_context)
                chunk_request['prompt'] += wiki_context_block + get_wikipedia_instructions()

            step.input_data = chunk_request['prompt']
            step.metadata.update(chunk_request['metadata'])

            # Make the run's safety level and language visible to chunks that
            # must decide on them themselves. output_speech_supertonic refuses
            # fail-closed when the level is absent, so this must be injected for
            # every chunk, not only where a caller happens to pass it.
            # Fill in, never overwrite: a config that names one of these
            # itself has decided it, and the run must not silently win over it.
            if safety_level and 'safety_level' not in chunk_request['parameters']:
                chunk_request['parameters']['safety_level'] = safety_level
            if context_language and 'context_language' not in chunk_request['parameters']:
                chunk_request['parameters']['context_language'] = context_language

            # Phase 4: Add seed_override to parameters if present in context.
            # Step 4 of the Intelligent Seed propagation chain — see
            # docs/ARCHITECTURE PART 01, section 3.5. It applies to every chunk;
            # a backend that has no use for a seed simply ignores the parameter.
            if 'seed_override' in context.custom_placeholders:
                seed_value = context.custom_placeholders['seed_override']
                chunk_request['parameters']['seed'] = seed_value  # lowercase!
                logger.info(f"[PHASE4-SEED] Injected seed into chunk parameters: {seed_value}")

            # Add input_image to parameters if present in context (IMG2IMG support)
            if 'input_image' in context.custom_placeholders:
                image_path = context.custom_placeholders['input_image']
                chunk_request['parameters']['input_image'] = image_path
                logger.info(f"[IMG2IMG] Injected input_image into chunk parameters: {image_path}")

            # Add multi-image paths to parameters if present in context
            for i in range(1, 4):
                key = f'input_image{i}'
                if key in context.custom_placeholders:
                    image_path = context.custom_placeholders[key]
                    chunk_request['parameters'][key] = image_path
                    logger.info(f"[MULTI-IMG] Injected {key} into chunk parameters: {image_path}")

            # Surrealizer: Add alpha_factor to parameters if present in context (T5-CLIP fusion)
            if 'alpha_factor' in context.custom_placeholders:
                alpha_value = context.custom_placeholders['alpha_factor']
                chunk_request['parameters']['alpha_factor'] = alpha_value
                logger.info(f"[SURREALIZER] Injected alpha_factor into chunk parameters: {alpha_value}")

            # Add ALL custom placeholders to parameters (for legacy workflows with input_mappings)
            # Generation parameters OVERRIDE defaults from output_config
            # These are user-provided values that take priority over config defaults
            GENERATION_OVERRIDE_PARAMS = {'width', 'height', 'steps', 'cfg', 'negative_prompt', 'sampler_name', 'scheduler', 'denoise'}

            logger.info(f"[DEBUG-PARAMS] custom_placeholders keys: {list(context.custom_placeholders.keys())}")
            logger.info(f"[DEBUG-PARAMS] chunk_request['parameters'] keys before injection: {list(chunk_request['parameters'].keys())}")
            for key, value in context.custom_placeholders.items():
                if key in GENERATION_OVERRIDE_PARAMS:
                    # Generation params: User values ALWAYS override defaults
                    old_value = chunk_request['parameters'].get(key, 'N/A')
                    chunk_request['parameters'][key] = value
                    logger.info(f"[CUSTOM-PARAMS] Override '{key}': {old_value} → {value}")
                elif key not in chunk_request['parameters']:
                    # Other params: Only inject if not already present
                    chunk_request['parameters'][key] = value
                    logger.info(f"[CUSTOM-PARAMS] Injected '{key}' = '{str(value)[:50]}' into chunk parameters")
                else:
                    logger.info(f"[CUSTOM-PARAMS] Skipped '{key}' - already in parameters with value: {chunk_request['parameters'][key]}")

            backend_request = BackendRequest(
                backend_type=BackendType(chunk_request['backend_type']),
                model=chunk_request['model'],
                prompt=chunk_request['prompt'],
                parameters=chunk_request['parameters'],
                usage_stage=usage_stage_of(resolved_config),
            )

            response = await self.backend_router.process_request(backend_request)

            if isinstance(response, BackendResponse):
                if response.success:
                    # Merge ALL backend metadata into step.metadata (preserves image_paths, seed, etc.)
                    step.metadata.update(response.metadata)
                    # Ensure fallbacks for critical fields
                    step.metadata['model_used'] = response.metadata.get('model_used', chunk_request['model'])
                    step.metadata['backend_type'] = response.metadata.get('backend_type', chunk_request['backend_type'])
                    # final_model was written by the chunk builder BEFORE the
                    # call, out of the config -- it says which model was asked
                    # for. The engine routes by its own rules and can reach
                    # another one, so where it reports what it dispatched to,
                    # that replaces the request. Nothing else about the step
                    # changes; a caller reading final_model then reads the model
                    # the text was actually written by.
                    dispatched_model = response.metadata.get('dispatched_model')
                    if dispatched_model:
                        step.metadata['final_model'] = dispatched_model

                    output = response.content

                    # ================================================================
                    # WIKIPEDIA RESEARCH LOOP
                    # ================================================================
                    # Check for <wiki> markers in output
                    markers = extract_markers(output)

                    if not markers or wiki_iteration >= max_wiki_iterations:
                        # No markers or max iterations reached - return output
                        if markers:
                            # Markers present but not resolved (skip or max iterations) - strip them
                            logger.info(f"[WIKI-LOOP] Completed after {wiki_iteration} iteration(s)")
                            output = remove_markers(output)
                        return output

                    # Markers found - fetch Wikipedia content
                    logger.info(f"[WIKI-LOOP] Iteration {wiki_iteration + 1}: Found {len(markers)} marker(s)")

                    # Build lookup terms with language resolution + deduplication
                    lookup_terms = []
                    # The model's own reason for each lookup, by term. Passed to
                    # the UI verbatim and never checked — it is what makes the
                    # model's estimate of its own limits readable.
                    lookup_reasons = {}
                    # What THIS answer already asks for. fetched_terms carries the
                    # earlier iterations; within one answer nothing carried, so a
                    # term the model wrote twice was fetched twice, stood twice in
                    # the context block and twice on the source cards.
                    asked_here = set()
                    for marker in markers:
                        lang = marker.language if marker.language else input_language
                        # Case-folded on BOTH halves, the same normalisation the
                        # record below dedups on -- keyed on the raw language,
                        # the two disagreed for the same ask written 'de' and 'DE'.
                        key = (marker.term.lower(), lang.lower())
                        if key in fetched_terms or key in asked_here:
                            logger.debug(f"[WIKI-DEDUP] Skipping already-fetched: '{marker.term}' ({lang})")
                            continue
                        asked_here.add(key)
                        if marker.reason:
                            lookup_reasons[marker.term.lower()] = marker.reason
                        lookup_terms.append((marker.term, lang))
                        logger.info(f"[WIKI-LOOKUP] '{marker.term}' ({lang})")
                        if len(lookup_terms) >= max_lookups:
                            break

                    # All markers were duplicates - strip and return
                    if not lookup_terms:
                        logger.info(f"[WIKI-DEDUP] All {len(markers)} marker(s) are duplicates, stripping and returning")
                        return remove_markers(output)

                    # Store Wikipedia status for real-time UI feedback
                    # Include language information for correct links
                    # For "start" status, we don't have real results yet, so use placeholders
                    terms_with_lang = [
                        {'term': t[0], 'lang': t[1], 'title': t[0], 'url': '',
                         'success': False, 'extract': '',
                         'why': lookup_reasons.get(t[0].lower(), '')}
                        for t in lookup_terms
                    ]
                    WIKIPEDIA_STATUS[wiki_status_key] = {
                        'status': 'lookup',
                        'terms': terms_with_lang,
                        'timestamp': time.time()
                    }
                    context.wikipedia['status'] = 'lookup'
                    context.wikipedia['asked'] = [t[0] for t in lookup_terms]

                    # Fetch Wikipedia content
                    try:
                        wiki_service = get_wikipedia_service(
                            cache_ttl=getattr(config, 'WIKIPEDIA_CACHE_TTL', 3600)
                        )
                        results = await wiki_service.lookup_multiple(lookup_terms, max_lookups=max_lookups)

                        # Format and add to context
                        wiki_content = format_wiki_content(results)
                        existing_content = context.custom_placeholders.get('WIKIPEDIA_CONTEXT', '')

                        if existing_content:
                            context.custom_placeholders['WIKIPEDIA_CONTEXT'] = existing_content + '\n\n' + wiki_content
                        else:
                            context.custom_placeholders['WIKIPEDIA_CONTEXT'] = wiki_content

                        logger.info(f"[WIKI-LOOP] Added {len(wiki_content)} chars to WIKIPEDIA_CONTEXT")

                        # Record fetched terms to prevent duplicate lookups in next iteration
                        for term, lang in lookup_terms:
                            fetched_terms.add((term.lower(), lang.lower()))
                        # And WHICH terms, kept across the iterations in the
                        # order the model asked for them, each with the language
                        # it was asked in and whether an article came back. A run
                        # that looked something up wrote with what it found, so
                        # two runs of the same prompt can differ for that reason
                        # alone, and a reader comparing them has to be able to
                        # see it -- which a bare count says happened without
                        # saying what did.
                        #
                        # One entry per (term, language) ASKED: the term as the
                        # model wrote it and the language it asked in, joined by
                        # position with the result for that ask (lookup_multiple
                        # answers in ask order). The result's own term and
                        # language are the lookup's: it lowercases the code,
                        # replaces one it does not serve with the fallback, and
                        # hands back the cache's folded term -- so recorded from
                        # there, two asks that differed only in language became
                        # one entry while two lookups had run, and the term shown
                        # was one nobody had asked for.
                        looked_up = context.wikipedia.setdefault('terms', [])
                        recorded = {(str(e.get('term') or '').lower(),
                                     str(e.get('lang') or '').lower())
                                    for e in looked_up if isinstance(e, dict)}
                        for (term, lang), r in zip(lookup_terms, results):
                            key = (term.lower(), lang.lower())
                            if key in recorded:
                                continue
                            recorded.add(key)
                            looked_up.append({'term': term, 'lang': lang,
                                              'found': bool(getattr(r, 'success', False))})
                        # Whether anything was looked up at all decides, one level
                        # up, whether a verbatim passthrough still applies.
                        context.wikipedia['lookups'] = len(looked_up)

                        # Update status to complete
                        # Include REAL Wikipedia results (title, url) not just search terms
                        # Include ALL terms (also not found) for transparency
                        results_with_urls = [
                            {
                                'term': r.term,
                                'lang': r.language,
                                'title': r.title if r.success else r.term,
                                'url': r.url,
                                'success': r.success,
                                # 2026-08-12: the retrieved text goes along. The
                                # flow surface lays each lookup on the board as
                                # a source card — the term on the front, the
                                # article and this text on the back. Without it
                                # the card could only link, not show.
                                'extract': r.extract,
                                # And why the model went looking. Its own words,
                                # unchecked — that is the point of showing it.
                                'why': lookup_reasons.get(r.term.lower(), '')
                            }
                            for r in results
                            # No filter - send ALL terms for transparency
                        ]

                        found_count = sum(1 for r in results_with_urls if r['success'])
                        logger.info(f"[WIKI-LOOP] Found {found_count}/{len(results_with_urls)} Wikipedia articles:")
                        for r in results_with_urls:
                            logger.info(f"  - {r['lang']}: {r['title']} -> {r['url']}")

                        WIKIPEDIA_STATUS[wiki_status_key] = {
                            'status': 'complete',
                            'terms': results_with_urls,  # Real results with URLs!
                            'timestamp': time.time()
                        }
                        context.wikipedia['status'] = 'complete'

                    except Exception as e:
                        logger.warning(f"[WIKI-LOOP] Wikipedia lookup failed: {e}")
                        WIKIPEDIA_STATUS[wiki_status_key] = {'status': None, 'terms': [], 'timestamp': time.time()}
                        context.wikipedia['status'] = 'error'
                        # Continue without Wikipedia content

                    wiki_iteration += 1
                    # Loop continues with enriched context

                else:
                    raise RuntimeError(f"Backend error: {response.error}")
            else:
                raise RuntimeError("Streaming not supported in single steps")
    
    def get_available_configs(self) -> List[str]:
        """List all available configs"""
        return self.config_loader.list_configs()
    
    def get_config_info(self, config_name: str) -> Optional[Dict[str, Any]]:
        """Get config information"""
        resolved_config = self.config_loader.get_config(config_name)
        if not resolved_config:
            return None

        return {
            "name": resolved_config.name,
            "display_name": resolved_config.display_name,
            "description": resolved_config.description,
            "pipeline_name": resolved_config.pipeline_name,
            "chunks": resolved_config.chunks,
            "parameters": resolved_config.parameters,
            "meta": resolved_config.meta
        }
    
    # Backward compatibility aliases
    def get_available_schemas(self) -> List[str]:
        """Backward compatibility: List all available configs"""
        return self.get_available_configs()
    
    def get_schema_info(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """Backward compatibility: Get config information"""
        return self.get_config_info(schema_name)

# Singleton instance
executor = PipelineExecutor(Path(__file__).parent.parent)


# The stage a run's tokens are booked under (my_app/services/usage_tracker), by
# the stage the config declares in its meta. Until 2026-10-10 the interception
# engine carried an attribute nothing set, and every cloud call of a
# translation before stage 4, or of a text output in stage 4, was booked as
# stage 2 (finding S-032 of the code review of 2026-10-10).
USAGE_STAGE_OF_CONFIG_STAGE = {
    'pre_interception': 'stage1',
    'interception': 'stage2',
    'pre_output': 'stage3',
    'output': 'stage4',
}


def usage_stage_of(resolved_config) -> str:
    meta = getattr(resolved_config, 'meta', None) or {}
    return USAGE_STAGE_OF_CONFIG_STAGE.get(meta.get('stage'), 'stage2')
