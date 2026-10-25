"""
Config Loader - Replaces schema_registry.py
Loads configs (user-facing) + pipelines (structural templates)
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


# Directory names that never hold configs, however deep they sit under configs/.
#
# The loader globs `configs/**/*.json`, so anything dropped into the tree became
# a config like any other: a backup snapshot from 2025-11-09 under configs/tmp/
# resolved to 36 configs, 30 of which passed as offerable perspectives and were
# listed in the course palette beside the live ones under the SAME display name
# ("Bauhaus", "Overdrive", ...), each carrying a max_tokens cap the live configs
# had shed months earlier. The property-picker endpoint had this exclusion; the
# loader that every other caller reads from did not. This is now the one place
# that names them -- schema_pipeline_routes imports it rather than repeating it.
EXCLUDED_CONFIG_DIRS = frozenset({
    "tmp", "backup", "backups", "backup_20251114",
    "deactivated", "temporarily_deactivated", "deprecated",
    "archive", ".obsolete",
})


def resolve_context_language(context, language=None):
    """Resolve context to string — handles both str and {en:..., de:...} dict."""
    if context is None:
        return ''
    if isinstance(context, str):
        return context
    if isinstance(context, dict):
        if language is None:
            from config import DEFAULT_LANGUAGE
            language = DEFAULT_LANGUAGE
        return context.get(language, context.get('en', ''))
    return str(context)


def config_is_hidden(cfg) -> bool:
    """Whether a config file keeps itself out of every selection.

    The flag stands in three places in the shipped configs: at the top
    (`hidden`), under `meta` and under `display`. Until 2026-10-10 four readers
    read four combinations of them, and the property picker, reading the top
    level alone, offered perspectives marked hidden under `meta` or `display`
    (finding S-029 of the code review of 2026-10-10). One reading, every place."""
    if not isinstance(cfg, dict):
        return False
    return bool(
        cfg.get("hidden")
        or (cfg.get("meta") or {}).get("hidden")
        or (cfg.get("display") or {}).get("hidden")
    )


def wants_passthrough(config, effective_context: str, safety_level: str) -> bool:
    """Does this run owe the user their prompt verbatim?

    A config opts in with `meta.passthrough_when_context_empty: true`. With no
    context filled in — "Du bestimmst" / user_defined, i.e. every run where
    nobody picked a perspective — Stage 2 must not elaborate the prompt.

    At EVERY safety level, kids and youth included. Stage 2 is
    not a safety instrument: the age check runs in Stage 1 on what the user wrote
    and in Stage 3 on the prompt that goes to the model. Keeping Stage 2
    mandatory for the young meant that precisely their prompts were the ones
    rewritten by a model nobody had asked for — an instruction on a drawing came
    back as an invented beach scene, and the drawing was gone.

    It used to clear `chunks`, which meant no step ran at all — and with it no
    Wikipedia research, because research is something the MODEL does while it
    works. A prompt about the most important Igbo ritual of the 16th century
    then went to the image model as a question, and what came back was
    invented. So the step runs, and the caller decides afterwards: the
    user's wording stands, UNLESS the model had to look something up — then what
    it wrote with those articles is the answer, which is the whole point of
    looking anything up.
    """
    if not config:
        return False
    if not (getattr(config, 'meta', None) or {}).get('passthrough_when_context_empty'):
        return False
    if effective_context and effective_context.strip():
        return False
    return True


@dataclass
class Pipeline:
    """Pipeline definition (structural template - NO content)"""
    name: str
    description: str
    chunks: List[str]

    # Phase 2: Pipeline structure metadata for dynamic frontend UI
    pipeline_type: Optional[str] = None  # "prompt_interception", "media_generation", "multi_prompt", etc.
    pipeline_stage: Optional[str] = None  # "1", "2", "3", "4" (4-stage pre-interception system)
    requires_interception_prompt: bool = False  # Show context editing bubble in Phase 2
    input_requirements: Optional[Dict[str, int]] = None  # {"texts": 1, "images": 0}
    skip_stage2: bool = False  # If True, Stage 2 execution is skipped (passthrough)
    # HOW the step is to be carried out, by name out of instruction_selector
    # .INSTRUCTION_TYPES. chunk_builder._get_task_instruction() has read this
    # off the pipeline object since the three-part prompt was introduced, and
    # five pipeline files have declared one all along -- but the field was
    # never on the dataclass, so every Stage 2 fell back to "transformation".
    # Those five name types that redirect there anyway (config_loader has no
    # entry for "translation", "image_transformation",
    # "multi_image_transformation"; "artistic_transformation" is its alias), so
    # honouring the field changes nothing for them. The chained translation is
    # the first pipeline whose step is genuinely a different HOW.
    instruction_type: Optional[str] = None

    # Legacy fields
    required_fields: List[str] = None
    defaults: Dict[str, Any] = None
    meta: Dict[str, Any] = None

@dataclass
class Config:
    """Config definition (user-facing content + metadata)"""
    name: str  # Internal name (filename without .json)
    pipeline: str  # Pipeline reference
    display_name: Dict[str, str]  # Multilingual names {"en": "...", "de": "..."}
    description: Dict[str, str]  # Multilingual descriptions
    category: Optional[Dict[str, str]] = None
    context: Optional[Any] = None  # str or Dict[str, str] for i18n
    # Welcher Anweisungstyp diese Perspektive braucht. Die Pipeline bleibt
    # erste Instanz; das hier greift, wo sie schweigt.
    instruction_type: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    media_preferences: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

@dataclass
class ResolvedConfig:
    """Resolved config - pipeline + config merged for execution"""
    name: str
    display_name: Dict[str, str]
    description: Dict[str, str]
    pipeline_name: str
    chunks: List[str]
    context: Optional[Any]  # str or Dict[str, str] for i18n
    instruction_type: Optional[str]
    parameters: Dict[str, Any]
    media_preferences: Optional[Dict[str, Any]]
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ResolvedConfig to dict for serialization

        DEPRECATED: Only needed for legacy frontend (port 17801) debug tool.
        New Vue frontend does not use this method.
        """
        return {
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'pipeline': self.pipeline_name,
            'chunks': self.chunks,
            'context': self.context,
            'parameters': self.parameters,
            'media_preferences': self.media_preferences,
            'meta': self.meta
        }

class ConfigLoader:
    """
    Config Loader - Central registry for configs and pipelines
    Replaces SchemaRegistry with new architecture
    """

    _instance: Optional['ConfigLoader'] = None
    _initialized: bool = False

    def __new__(cls) -> 'ConfigLoader':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.pipelines: Dict[str, Pipeline] = {}
            self.configs: Dict[str, Config] = {}
            self.resolved_configs: Dict[str, ResolvedConfig] = {}
            self.base_path: Optional[Path] = None
            ConfigLoader._initialized = True

    def initialize(self, schemas_path: Path) -> None:
        """Initialize loader and load all definitions"""
        self.base_path = schemas_path
        self._load_pipelines()
        self._load_configs()
        self._resolve_configs()
        logger.info(f"ConfigLoader initialized: {len(self.pipelines)} pipelines, {len(self.configs)} configs, {len(self.resolved_configs)} resolved")

    def _load_pipelines(self) -> None:
        """Load pipeline definitions from pipelines/*.json"""
        if not self.base_path:
            logger.error("ConfigLoader not initialized")
            return

        pipelines_path = self.base_path / "pipelines"
        if not pipelines_path.exists():
            logger.warning(f"Pipelines path not found: {pipelines_path}")
            return

        for pipeline_file in pipelines_path.glob("*.json"):
            try:
                pipeline = self._load_pipeline_file(pipeline_file)
                if pipeline:
                    self.pipelines[pipeline.name] = pipeline
                    logger.debug(f"Pipeline loaded: {pipeline.name}")
            except Exception as e:
                logger.error(f"Error loading pipeline {pipeline_file}: {e}")

    def _load_pipeline_file(self, pipeline_file: Path) -> Optional[Pipeline]:
        """Load single pipeline file"""
        try:
            with open(pipeline_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return Pipeline(
                name=data.get('name', pipeline_file.stem),
                description=data.get('description', ''),
                chunks=data.get('chunks', []),
                # Phase 2: Pipeline structure metadata
                pipeline_type=data.get('pipeline_type'),
                pipeline_stage=data.get('pipeline_stage'),
                requires_interception_prompt=data.get('requires_interception_prompt', False),
                input_requirements=data.get('input_requirements', {}),
                skip_stage2=data.get('skip_stage2', False),
                instruction_type=data.get('instruction_type'),
                # Legacy fields
                required_fields=data.get('required_fields', []),
                defaults=data.get('defaults', {}),
                meta=data.get('meta', {})
            )
        except Exception as e:
            logger.error(f"Error parsing pipeline {pipeline_file}: {e}")
            return None

    def _load_configs(self) -> None:
        """Load config definitions from configs/**/*.json (recursive)"""
        if not self.base_path:
            logger.error("ConfigLoader not initialized")
            return

        # Try configs first (new architecture), fall back to old structure
        configs_path = self.base_path / "configs"
        if not configs_path.exists():
            # Fallback: try old schema_data directory
            configs_path = self.base_path / "schema_data"
            logger.warning(f"Using legacy schema_data directory: {configs_path}")

        if not configs_path.exists():
            logger.warning(f"Configs path not found: {configs_path}")
            return

        # Recursive glob to support subdirectories (pre_interception/, pre_output/, etc.)
        for config_file in configs_path.glob("**/*.json"):
            try:
                relative_parts = config_file.relative_to(configs_path).parts
                if any(part in EXCLUDED_CONFIG_DIRS for part in relative_parts):
                    logger.debug(f"Config skipped (excluded directory): {config_file}")
                    continue
                config = self._load_config_file(config_file, configs_path)
                if config:
                    self.configs[config.name] = config
                    logger.debug(f"Config loaded: {config.name}")
            except Exception as e:
                logger.error(f"Error loading config {config_file}: {e}")

    def _load_config_file(self, config_file: Path, configs_base_path: Path) -> Optional[Config]:
        """Load single config file"""
        try:
            logger.debug(f"Loading config file: {config_file}")
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"JSON loaded successfully from {config_file}")

            # Calculate relative path from configs directory for internal name
            # Example: configs/pre_interception/safety.json → pre_interception/safety
            try:
                relative_path = config_file.relative_to(configs_base_path)
                parts = relative_path.parts

                # Determine config name and owner based on folder structure
                if len(parts) >= 2 and parts[0] == "user_configs":
                    # User config: user_configs/username/my_config.json → u_username_my_config
                    username = parts[1]
                    stem = config_file.stem
                    config_name_from_path = f"u_{username}_{stem}"
                    owner = username
                    logger.debug(f"User config detected: username={username}, name={config_name_from_path}")
                elif parts[0] in ["interception", "output"]:
                    # Main system configs: use just the stem (no path prefix)
                    config_name_from_path = config_file.stem
                    owner = "system"
                else:
                    # Other system configs (pre_interception, pre_output, etc.): keep path
                    config_name_from_path = str(relative_path.with_suffix('')).replace('\\', '/')
                    owner = "system"
            except ValueError:
                # Fallback if relative_to fails
                config_name_from_path = config_file.stem
                owner = "system"

            # Support both new format and legacy format
            # IMPORTANT: When "name" field is a dict (multilingual), use relative path as internal name
            json_name_field = data.get('name')
            if isinstance(json_name_field, dict):
                # name is multilingual, use relative path as internal name
                config_name = config_name_from_path
                display_name = json_name_field
            else:
                # name is string or missing, use relative path as internal name
                config_name = json_name_field or config_name_from_path
                display_name = {'en': config_name, 'de': config_name}

            logger.debug(f"Config name: {config_name}, display_name: {display_name}")

            # New format: "pipeline" field
            pipeline = data.get('pipeline')

            # Legacy format fallback: "workflow_type" field
            if not pipeline:
                pipeline = data.get('workflow_type')
                if pipeline:
                    logger.warning(f"Config {config_name} uses legacy 'workflow_type' field, should use 'pipeline'")

            if not pipeline:
                logger.error(f"Config {config_name} missing 'pipeline' field")
                return None

            # Extract description
            json_desc = data.get('description')
            if isinstance(json_desc, dict):
                description = json_desc
            else:
                description = {'en': '', 'de': ''}

            logger.debug(f"Creating Config object for {config_name}")

            # Pass through context as-is (str or {en:..., de:...} dict)
            # Language resolution happens at point of use via resolve_context_language()
            context = data.get('context')

            # Auto-inject meta.owner field
            meta = data.get('meta', {})
            if 'owner' not in meta:
                meta['owner'] = owner  # Set owner from folder structure
                logger.debug(f"Auto-injected meta.owner = '{owner}' for config '{config_name}'")

            return Config(
                name=config_name,
                pipeline=pipeline,
                display_name=display_name,
                description=description,
                category=data.get('category'),
                context=context,
                instruction_type=data.get('instruction_type'),
                parameters=data.get('parameters'),
                media_preferences=data.get('media_preferences'),
                meta=meta
            )
        except Exception as e:
            logger.error(f"Error parsing config {config_file}: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    def _resolve_configs(self) -> None:
        """Resolve configs with pipelines to create executable definitions"""
        for config_name, config in self.configs.items():
            pipeline = self.pipelines.get(config.pipeline)
            if not pipeline:
                logger.error(f"Pipeline '{config.pipeline}' for config '{config_name}' not found")
                continue

            # Merge pipeline defaults + config overrides
            parameters = {}
            if pipeline.defaults and 'parameters' in pipeline.defaults:
                parameters.update(pipeline.defaults['parameters'])
            if config.parameters:
                parameters.update(config.parameters)

            # Resolve placeholders in chunk names (e.g., {{OUTPUT_CHUNK}})
            resolved_chunks = []
            for chunk_name in pipeline.chunks:
                # Replace placeholders like {{OUTPUT_CHUNK}} with values from parameters
                resolved_chunk_name = chunk_name
                if '{{' in chunk_name and '}}' in chunk_name:
                    # Extract placeholder name
                    import re
                    placeholders = re.findall(r'\{\{(\w+)\}\}', chunk_name)
                    for placeholder in placeholders:
                        if placeholder in parameters:
                            resolved_chunk_name = resolved_chunk_name.replace(
                                f'{{{{{placeholder}}}}}',
                                str(parameters[placeholder])
                            )
                            logger.debug(f"Resolved chunk placeholder: {chunk_name} → {resolved_chunk_name}")
                resolved_chunks.append(resolved_chunk_name)

            # Create resolved config
            resolved = ResolvedConfig(
                name=config.name,
                display_name=config.display_name,
                description=config.description,
                pipeline_name=config.pipeline,
                chunks=resolved_chunks,
                context=config.context,
                instruction_type=config.instruction_type,
                parameters=parameters,
                media_preferences=config.media_preferences,
                meta={**(pipeline.meta or {}), **(config.meta or {})}
            )

            self.resolved_configs[config_name] = resolved
            logger.debug(f"Config resolved: {config_name} → {config.pipeline}")

    def get_config(self, name: str) -> Optional[ResolvedConfig]:
        """Get resolved config by name"""
        return self.resolved_configs.get(name)

    def list_configs(self) -> List[str]:
        """List all resolved config names"""
        return list(self.resolved_configs.keys())

    def list_pipelines(self) -> List[str]:
        """List all pipeline names"""
        return list(self.pipelines.keys())

    def get_pipeline(self, name: str) -> Optional[Pipeline]:
        """Get pipeline by name"""
        return self.pipelines.get(name)

    def is_available(self, name: str) -> bool:
        """Check if config is available"""
        return name in self.resolved_configs

# Singleton instance
config_loader = ConfigLoader()
