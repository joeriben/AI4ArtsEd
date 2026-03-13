"""
Chunk-Builder: Template-System mit Placeholder-Replacement
REFACTORED for new architecture (JSON configs)
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import json
import re
import logging

logger = logging.getLogger(__name__)


def get_model_family(model_name: str) -> str:
    """
    Determine model family from model name for prompt variant selection.

    Args:
        model_name: Full model identifier (e.g., "local/llama4:scout", "bedrock/eu.anthropic.claude-sonnet-4-5")

    Returns:
        "llama" | "mistral" | "default"
    """
    if not model_name:
        return "default"

    model_lower = model_name.lower()

    # Llama family detection
    if any(x in model_lower for x in ["llama", "meta-llama"]):
        return "llama"

    # Mistral family detection
    if any(x in model_lower for x in ["mistral", "mixtral", "ministral", "magistral"]):
        return "mistral"

    # Default (Claude, OpenAI, Qwen, DeepSeek, etc.)
    return "default"


@dataclass
class ChunkTemplate:
    """Template für einen Verarbeitungs-Chunk"""
    name: str
    template: Any  # Can be str or Dict[str, str] for {"system": "...", "prompt": "..."}
    backend_type: str
    model: str
    parameters: Dict[str, Any]
    placeholders: List[str]
    workflow: Optional[Dict[str, Any]] = None  # For output_chunks with ComfyUI workflows
    chunk_type: Optional[str] = None  # 'processing_chunk', 'output_chunk', etc.

class ChunkBuilder:
    """Builder für Template-basierte Chunks mit Placeholder-Replacement"""

    def __init__(self, schemas_path: Path):
        self.schemas_path = schemas_path
        self.templates: Dict[str, ChunkTemplate] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Alle Chunk-Templates laden"""
        chunks_path = self.schemas_path / "chunks"
        if not chunks_path.exists():
            logger.warning(f"Chunks-Pfad nicht gefunden: {chunks_path}")
            return

        for template_file in chunks_path.glob("*.json"):
            try:
                template = self._load_template_file(template_file)
                if template:
                    self.templates[template.name] = template
                    logger.debug(f"Template geladen: {template.name}")
            except Exception as e:
                logger.error(f"Fehler beim Laden von Template {template_file}: {e}")

    def _load_template_file(self, template_file: Path) -> Optional[ChunkTemplate]:
        """Einzelnes Template-File laden"""
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Template kann string oder dict sein
            template_data = data.get('template', '')

            # Load workflow field for output_chunks (Phase 2A)
            workflow_data = data.get('workflow') or data.get('workflow_api')
            chunk_type = data.get('type', 'processing_chunk')

            # Placeholders extrahieren basierend auf Template-Typ
            if isinstance(template_data, dict):
                # Dict template: Placeholders aus allen Werten extrahieren
                placeholders = []
                for value in template_data.values():
                    if isinstance(value, str):
                        placeholders.extend(re.findall(r'\{\{([^}]+)\}\}', value))
                placeholders = list(set(placeholders))  # Duplikate entfernen
                logger.debug(f"Dict template in {template_file.name}: {list(template_data.keys())}")
            elif isinstance(template_data, str):
                # String template: Direkt extrahieren
                placeholders = re.findall(r'\{\{([^}]+)\}\}', template_data)
            else:
                # Ungültiger Typ: Als leer behandeln
                logger.warning(f"Ungültiger Template-Typ in {template_file.name}: {type(template_data)}")
                template_data = ''
                placeholders = []

            return ChunkTemplate(
                name=data.get('name', template_file.stem),
                template=template_data,
                backend_type=data.get('backend_type', 'ollama'),
                model=data.get('model', ''),
                parameters=data.get('parameters', {}),
                placeholders=placeholders,
                workflow=workflow_data,  # Phase 2A
                chunk_type=chunk_type  # Phase 2A
            )

        except Exception as e:
            logger.error(f"Fehler beim Parsen von {template_file}: {e}")
            return None

    def _get_template_with_variant(self, chunk_name: str, model_name: str = None) -> Optional[ChunkTemplate]:
        """
        Get template with model-specific variant if available.

        Tries to load model-family-specific variant first (e.g., optimize_clip_prompt_llama),
        falls back to default template if variant not found.

        Args:
            chunk_name: Base chunk name (e.g., "optimize_clip_prompt")
            model_name: Model identifier for variant selection (e.g., "local/llama4:scout")

        Returns:
            ChunkTemplate for the appropriate variant, or None if not found
        """
        # Get base template first (needed for model auto-detection)
        base_template = self.templates.get(chunk_name)

        # Determine model name: explicit override > template's model field (resolved)
        effective_model = model_name
        if not effective_model and base_template:
            # Auto-detect from template's model field
            template_model = base_template.model
            if template_model:
                # Resolve config variable if needed (e.g., "STAGE2_OPTIMIZATION_MODEL" -> "local/llama4:scout")
                import config
                if hasattr(config, template_model):
                    effective_model = getattr(config, template_model)
                    logger.debug(f"[CHUNK-VARIANT] Auto-detected model from config.{template_model} -> {effective_model}")
                else:
                    effective_model = template_model

        # Determine model family
        model_family = get_model_family(effective_model) if effective_model else "default"

        # Try model-specific variant first (only for non-default families)
        if model_family != "default":
            variant_name = f"{chunk_name}_{model_family}"
            variant_template = self.templates.get(variant_name)
            if variant_template:
                logger.info(f"[CHUNK-VARIANT] Using {model_family} variant: '{variant_name}'")
                return variant_template
            else:
                logger.debug(f"[CHUNK-VARIANT] No {model_family} variant found for '{chunk_name}', using default")

        # Fall back to default template
        return base_template

    def build_chunk(self,
                    chunk_name: str,
                    resolved_config: Any,  # ResolvedConfig from config_loader
                    context: Dict[str, Any],
                    pipeline: Any = None,
                    model_override: str = None,
                    safety_level: str = None) -> Dict[str, Any]:
        """
        Chunk mit Template und resolved config erstellen

        Args:
            chunk_name: Name of chunk template
            resolved_config: ResolvedConfig object from config_loader
            context: Execution context (input_text, previous_output, etc.)
            pipeline: Pipeline object (for accessing instruction_type)
            model_override: Optional model name for variant selection
            safety_level: Safety level ('kids', 'youth', etc.) — injects safety prefix when 'kids'
        """
        # Check if Python chunk exists (new standard for Output-Chunks)
        from pathlib import Path
        chunk_py_path = Path(__file__).parent.parent / "chunks" / f"{chunk_name}.py"
        if chunk_py_path.exists():
            logger.info(f"[CHUNK-BUILD] Detected Python chunk: {chunk_name}.py")
            # Python chunks don't need template processing - return minimal request
            # The actual execution happens in backend_router._execute_python_chunk()
            parameters = dict(resolved_config.parameters) if resolved_config.parameters else {}
            parameters['_chunk_name'] = chunk_name

            # Map TEXT_1, TEXT_2 from context (defaults)
            if 'input_text' in context:
                parameters['TEXT_1'] = context['input_text']
            if 'previous_output' in context:
                parameters['TEXT_1'] = context['previous_output']  # Override with previous output if exists
            if 'user_input' in context:
                parameters['TEXT_2'] = context['user_input']

            # Override with custom_placeholders (higher priority - explicit values from frontend)
            if context.get('custom_placeholders'):
                parameters.update(context['custom_placeholders'])

            return {
                'backend_type': 'python',  # Special marker for Python chunks
                'model': '',  # Python chunks don't use model
                'prompt': {},  # Empty workflow dict
                'parameters': parameters,
                'metadata': {
                    'chunk_name': chunk_name,
                    'config_name': resolved_config.name,
                    'chunk_type': 'python_chunk',
                    'is_python_chunk': True
                }
            }

        # Model-specific variant selection
        template = self._get_template_with_variant(chunk_name, model_override)
        if not template:
            raise ValueError(f"Template '{chunk_name}' nicht gefunden")

        # Get instruction text from config context (former metaprompt)
        from .config_loader import resolve_context_language
        instruction_text = resolve_context_language(resolved_config.context)

        # INSTRUCTION-TYPE SYSTEM: Get TASK_INSTRUCTION for prompt interception
        task_instruction = self._get_task_instruction(resolved_config, pipeline, safety_level=safety_level)

        # Build context for placeholder replacement
        replacement_context = {
            # Legacy placeholders (backward compatibility)
            'INSTRUCTION': instruction_text,
            'INSTRUCTIONS': instruction_text,

            # New three-part prompt interception structure
            'TASK_INSTRUCTION': task_instruction,
            'CONTEXT': instruction_text,  # Config context = artistic attitude

            # Input placeholders
            'INPUT_TEXT': context.get('input_text', ''),
            'PREVIOUS_OUTPUT': context.get('previous_output', ''),
            'USER_INPUT': context.get('user_input', ''),

            **context.get('custom_placeholders', {}),
            **resolved_config.parameters  # Add config parameters for placeholder replacement
        }

        # Placeholder-Replacement in template (type-safe)
        if isinstance(template.template, dict):
            # Dict template: Process dict and serialize to string
            processed_dict = self._process_dict_template(template.template, replacement_context)
            processed_template = self._serialize_dict_to_string(processed_dict)
            logger.debug(f"[CHUNK-BUILD] Processed dict template for '{chunk_name}'")
        elif isinstance(template.template, str):
            # String template: Use existing replacement logic
            processed_template = self._replace_placeholders(template.template, replacement_context)
        else:
            # Fallback for unexpected types
            logger.error(f"Unexpected template type for '{chunk_name}': {type(template.template)}")
            processed_template = str(template.template)

        # Debug: Log the built prompt
        logger.debug(f"[CHUNK-BUILD] Chunk '{chunk_name}' prompt preview: {processed_template[:200]}...")

        # Check if this is a proxy chunk (no template, no model)
        # Proxy chunks route to specialized output chunks via parameters
        if isinstance(template.template, str):
            template_is_empty = not template.template.strip()
        elif isinstance(template.template, dict):
            # Dict template is empty if all values are empty
            template_is_empty = all(not str(v).strip() for v in template.template.values())
        else:
            template_is_empty = True

        is_proxy_chunk = template_is_empty and not template.model.strip()

        # Model-Override: Check config.meta.model_override first, then template.model
        # Skip model selection for proxy chunks
        if is_proxy_chunk:
            final_model = ""  # Proxy chunks don't need a model
            logger.debug(f"[CHUNK-BUILD] '{chunk_name}' is a proxy chunk - skipping model selection")
        else:
            base_model = resolved_config.meta.get('model_override') or template.model

            # Check if base_model is a config variable name (e.g., "STAGE2_MODEL")
            # If yes, look it up from config.py; if no, use as-is (backward compatibility)
            import config

            if hasattr(config, base_model):
                final_model = getattr(config, base_model)
                logger.debug(f"[CHUNK-BUILD] '{chunk_name}' model from config.{base_model} → {final_model}")
            else:
                # Not a config variable - use directly (backward compatibility with hardcoded models)
                final_model = base_model
                logger.debug(f"[CHUNK-BUILD] '{chunk_name}' using direct model: {final_model}")

        # Merge parameters: template params + config params (config overrides template)
        merged_parameters = {**template.parameters, **resolved_config.parameters}

        # Apply placeholder replacement to parameter values
        processed_parameters = self._replace_placeholders_in_dict(merged_parameters, replacement_context)

        # PHASE 2B: Detect output chunks (have workflow field OR are api_output/text_passthrough type)
        is_output_chunk = bool(template.workflow) or template.chunk_type in ('api_output_chunk', 'text_passthrough')

        # Chunk-Request zusammenstellen
        if is_output_chunk:
            # Output chunk: workflow dict with replaced placeholders
            logger.debug(f"[CHUNK-BUILD] '{chunk_name}' is output chunk (type={template.chunk_type})")
            if template.workflow:
                processed_workflow = self._process_workflow_placeholders(template.workflow, replacement_context)
            else:
                processed_workflow = {}  # api_output_chunk/text_passthrough: no workflow, router re-loads JSON

            # Include chunk_name in parameters for router detection (Python chunks)
            processed_parameters['_chunk_name'] = chunk_name

            # Ensure text prompt is available in parameters for backend_router
            # (router re-loads JSON workflow and needs prompt text for input_mappings injection)
            processed_parameters['PREVIOUS_OUTPUT'] = replacement_context.get('PREVIOUS_OUTPUT', '')

            chunk_request = {
                'backend_type': template.backend_type,
                'model': final_model,
                'prompt': processed_workflow,  # Dict, not string
                'parameters': processed_parameters,
                'metadata': {
                    'chunk_name': chunk_name,
                    'config_name': resolved_config.name,
                    'chunk_type': template.chunk_type or 'output_chunk',
                    'has_workflow': bool(template.workflow),
                    'workflow_nodes': len(processed_workflow) if processed_workflow else 0,
                    **resolved_config.meta
                }
            }
            logger.debug(f"[CHUNK-BUILD] Output chunk '{chunk_name}' built with {len(processed_workflow) if processed_workflow else 0} workflow nodes")
        else:
            # Processing chunk: string prompt (existing behavior)
            chunk_request = {
                'backend_type': template.backend_type,
                'model': final_model,
                'prompt': processed_template,
                'parameters': processed_parameters,
                'metadata': {
                    'chunk_name': chunk_name,
                    'config_name': resolved_config.name,
                    'template_placeholders': template.placeholders,
                    'template_model': template.model,
                    'final_model': final_model,
                    **resolved_config.meta
                }
            }
            logger.debug(f"[CHUNK-BUILD] Processing chunk '{chunk_name}' built with Config {resolved_config.name}")

        return chunk_request

    def _get_task_instruction(self, resolved_config: Any, pipeline: Any, safety_level: str = None) -> str:
        """
        Get TASK_INSTRUCTION using instruction-type system.

        Mirrors original ComfyUI prompt_interception node: Task + Context + Prompt

        Priority:
            1. Config's custom task_instruction (if provided)
            2. Pipeline's instruction_type (default)
            3. Fallback to "artistic_transformation"

        When safety_level='kids', a safety prefix is prepended to the instruction.
        """
        from .instruction_selector import get_instruction

        # Check for custom override in config
        custom_instruction = getattr(resolved_config, 'task_instruction', None)

        # Get instruction_type from pipeline
        instruction_type = getattr(pipeline, 'instruction_type', 'artistic_transformation') if pipeline else 'artistic_transformation'

        return get_instruction(instruction_type, custom_instruction, safety_level=safety_level)

    def _replace_placeholders(self, template: str, replacements: Dict[str, Any]) -> str:
        """Placeholder durch Werte ersetzen"""
        result = template

        # Placeholder ersetzen
        for placeholder, value in replacements.items():
            pattern = f'{{{{{placeholder}}}}}'
            result = result.replace(pattern, str(value))

        # Überprüfung auf nicht ersetzte Placeholders
        remaining_placeholders = re.findall(r'\{\{([^}]+)\}\}', result)
        if remaining_placeholders:
            logger.warning(f"Nicht ersetzte Placeholders: {remaining_placeholders}")

        return result

    def _replace_placeholders_in_dict(self, data: Dict[str, Any], replacements: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively replace placeholders in dictionary values"""
        result = {}

        for key, value in data.items():
            if isinstance(value, str):
                # Apply placeholder replacement to string values
                processed_value = value
                for placeholder, replacement in replacements.items():
                    pattern = f'{{{{{placeholder}}}}}'
                    processed_value = processed_value.replace(pattern, str(replacement))
                result[key] = processed_value
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                result[key] = self._replace_placeholders_in_dict(value, replacements)
            elif isinstance(value, list):
                # Process lists (in case there are string elements)
                result[key] = [
                    self._replace_placeholders(item, replacements) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                # Keep non-string values as-is
                result[key] = value

        return result

    def get_available_templates(self) -> List[str]:
        """Liste aller verfügbaren Templates"""
        return list(self.templates.keys())

    def get_template_placeholders(self, template_name: str) -> Optional[List[str]]:
        """Placeholders für ein Template abrufen"""
        template = self.templates.get(template_name)
        return template.placeholders if template else None

    def validate_chunk_request(self, chunk_name: str, resolved_config: Any, context: Dict[str, Any]) -> List[str]:
        """Chunk-Request validieren und fehlende Daten auflisten"""
        errors = []

        template = self.templates.get(chunk_name)
        if not template:
            errors.append(f"Template '{chunk_name}' nicht gefunden")
            return errors

        # Required Placeholders prüfen
        required_context = ['input_text']
        for required in required_context:
            if required not in context:
                errors.append(f"Erforderlicher Context '{required}' fehlt")

        return errors

    def _process_dict_template(self, template_dict: Dict[str, Any], replacements: Dict[str, Any]) -> Dict[str, str]:
        """
        Process dict template with placeholder replacement

        Supported formats:
        1. {"system": "...", "prompt": "..."}  - Separate system and user prompt
        2. {"user": "..."}                      - Single user prompt
        3. {"prompt": "..."}                    - Single prompt (legacy)

        Returns dict with processed string values
        """
        result = {}

        for key, value in template_dict.items():
            if isinstance(value, str):
                # Apply placeholder replacement to each string value
                processed_value = self._replace_placeholders(value, replacements)
                result[key] = processed_value
            else:
                # Keep non-string values as-is (shouldn't happen in practice)
                result[key] = value

        return result

    def _serialize_dict_to_string(self, template_dict: Dict[str, str]) -> str:
        """
        Serialize dict template to Task/Context/Prompt string format
        for backward compatibility with backend_router

        Formats:
        - {"system": X, "prompt": Y} → "Task:\nX\n\nContext:\n\nPrompt:\nY"
        - {"user": X} → "Task:\n\n\nContext:\n\nPrompt:\nX"
        - {"prompt": X} → "Task:\n\n\nContext:\n\nPrompt:\nX"

        This ensures dict templates work with the existing backend routing
        that expects Task/Context/Prompt format.
        """
        system = template_dict.get('system', '')
        prompt = template_dict.get('prompt', template_dict.get('user', ''))

        # Build three-part structure compatible with prompt_interception_engine
        return f"Task:\n{system}\n\nContext:\n\nPrompt:\n{prompt}"

    def _process_workflow_placeholders(self, workflow: Dict[str, Any], replacements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process ComfyUI workflow and replace placeholders in all string values.

        Recursively walks workflow structure and replaces {{PLACEHOLDER}} patterns.
        Used for output_chunks in pipelines (Phase 2B).

        Args:
            workflow: ComfyUI workflow dict from chunk template
            replacements: Dict of placeholder values (from context.custom_placeholders)

        Returns:
            Workflow dict with all placeholders replaced
        """
        import copy

        # Deep copy to avoid mutating template
        processed_workflow = copy.deepcopy(workflow)

        # Reuse existing recursive replacement logic
        return self._replace_placeholders_in_dict(processed_workflow, replacements)
