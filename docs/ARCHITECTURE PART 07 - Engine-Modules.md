# DevServer Architecture

**Part 7: Engine Modules**

---


### Core Engine Architecture

```
schemas/engine/
├── config_loader.py          # Load configs and pipelines
├── chunk_builder.py           # Build chunks with placeholder replacement
├── pipeline_executor.py       # Execute complete pipelines
├── backend_router.py          # Route to appropriate backend
├── model_selector.py          # Task-based model selection
├── instruction_selector.py    # Instruction-type selection for 3-part prompts
├── comfyui_workflow_generator.py  # DEPRECATED - workflows now embedded in chunks
└── prompt_interception_engine.py  # DEPRECATED - replaced by pipeline system
```

---

### 1. config_loader.py

**Purpose:** Load and manage configs and pipelines

**Key Classes:**
```python
@dataclass
class Config:
    pipeline: str
    name: dict
    description: dict
    category: dict
    context: str              # Complete instruction text
    parameters: dict
    media_preferences: dict
    meta: dict
    display: dict
    tags: dict
    audience: dict

@dataclass
class Pipeline:
    name: str
    description: str
    chunks: List[str]
    required_configs: List[str]
    config_mappings: dict
    meta: dict

class ConfigLoader:
    def __init__(self, schemas_path: Path):
        self.configs: Dict[str, Config] = {}
        self.pipelines: Dict[str, Pipeline] = {}
        self._load_all()
```

**Key Methods:**
- `get_config(config_name: str) -> Config`
- `get_pipeline(pipeline_name: str) -> Pipeline`
- `list_configs() -> List[str]`
- `get_config_info(config_name: str) -> dict`

---

### 2. chunk_builder.py

**Purpose:** Build chunks with placeholder replacement

**Chunk Types (Session 48):**
- **Processing Chunks:** LLM-based text processing (Ollama, OpenRouter)
  - Template: String or Dict `{"system": "...", "prompt": "..."}`
  - Output: String prompt for backend execution
- **Output Chunks:** Media generation with ComfyUI workflows
  - Template: Can be empty (proxy chunk) or string
  - Workflow: Dict with ComfyUI API workflow JSON
  - Output: Dict with placeholders replaced in workflow

**Key Data Structures:**
```python
@dataclass
class ChunkTemplate:
    name: str
    template: Any  # str or Dict[str, str] for {"system": "...", "prompt": "..."}
    backend_type: str
    model: str
    parameters: Dict[str, Any]
    placeholders: List[str]
    workflow: Optional[Dict[str, Any]] = None  # For output_chunks with ComfyUI workflows
    chunk_type: Optional[str] = None  # 'processing_chunk', 'output_chunk', etc.
```

**Key Functionality:**
```python
class ChunkBuilder:
    def build_chunk(
        self,
        chunk_name: str,
        resolved_config: ResolvedConfig,
        context: dict,
        execution_mode: str = 'eco',
        pipeline: Any = None
    ) -> Dict[str, Any]:
        # 1. Get chunk template
        template = self.templates.get(chunk_name)

        # 2. Build replacement context
        instruction_text = resolved_config.context or ''
        task_instruction = self._get_task_instruction(resolved_config, pipeline)

        replacement_context = {
            # Legacy placeholders (backward compatibility)
            'INSTRUCTION': instruction_text,
            'INSTRUCTIONS': instruction_text,

            # New three-part prompt interception structure
            'TASK_INSTRUCTION': task_instruction,
            'CONTEXT': instruction_text,

            # Input placeholders
            'INPUT_TEXT': context.get('input_text', ''),
            'PREVIOUS_OUTPUT': context.get('previous_output', ''),
            'USER_INPUT': context.get('user_input', ''),

            **context.get('custom_placeholders', {}),
            **resolved_config.parameters
        }

        # 3. Type-safe template processing (Session 48)
        if isinstance(template.template, dict):
            # Dict template: {"system": "...", "prompt": "..."}
            processed_dict = self._process_dict_template(template.template, replacement_context)
            processed_template = self._serialize_dict_to_string(processed_dict)
        elif isinstance(template.template, str):
            # String template
            processed_template = self._replace_placeholders(template.template, replacement_context)

        # 4. Detect output chunks (Session 48)
        is_output_chunk = bool(template.workflow)

        if is_output_chunk:
            # Output chunk: workflow dict with replaced placeholders
            processed_workflow = self._process_workflow_placeholders(
                template.workflow,
                replacement_context
            )

            return {
                'backend_type': template.backend_type,
                'model': final_model,
                'prompt': processed_workflow,  # Dict, not string
                'parameters': processed_parameters,
                'metadata': {
                    'chunk_type': 'output_chunk',
                    'has_workflow': True,
                    'workflow_nodes': len(processed_workflow)
                }
            }
        else:
            # Processing chunk: string prompt (existing behavior)
            return {
                'backend_type': template.backend_type,
                'model': final_model,
                'prompt': processed_template,  # String
                'parameters': processed_parameters,
                'metadata': {'chunk_type': 'processing_chunk'}
            }
```

**Output Chunk Workflow Placeholder Replacement (Session 48):**
```python
def _process_workflow_placeholders(self, workflow: Dict[str, Any], replacements: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process ComfyUI workflow and replace placeholders in all string values.

    Recursively walks workflow structure and replaces {{PLACEHOLDER}} patterns.
    Used for output_chunks in pipelines.

    Example:
        workflow = {"5": {"inputs": {"text": "{{CLIP_PROMPT}}"}}}
        replacements = {"CLIP_PROMPT": "mountains, clouds"}
        → {"5": {"inputs": {"text": "mountains, clouds"}}}

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
```

**Dict Template Support (Session 48):**
Dict templates enable separate system/user prompts for LLM API compatibility:
```json
{
  "template": {
    "system": "You are a CLIP prompt optimization expert.",
    "prompt": "Optimize this prompt: {{INPUT_TEXT}}"
  }
}
```

This gets serialized to Task/Context/Prompt format for backend compatibility:
```
Task:
You are a CLIP prompt optimization expert.

Context:

Prompt:
Optimize this prompt: <user input>
```

**Note:** After consolidation, we removed `TASK` and `CONTEXT` placeholder aliases - they were redundant and caused duplication.

---

### 3. pipeline_executor.py

**Purpose:** Execute complete pipelines by orchestrating chunks

**Key Functionality:**
```python
class PipelineExecutor:
    async def execute_pipeline(
        self,
        config_name: str,
        input_text: str,
        user_input: str = None,
        mode: str = "eco"
    ) -> PipelineResult:
        # 1. Load config and pipeline
        config = self.config_loader.get_config(config_name)
        pipeline = self.config_loader.get_pipeline(config.pipeline)

        # 2. Execute chunks in sequence
        context = {'input_text': input_text, 'user_input': user_input or input_text}
        steps = []

        for i, chunk_name in enumerate(pipeline.chunks):
            # Build chunk
            chunk = self.chunk_builder.build_chunk(chunk_name, config, context)

            # Execute via backend router
            result = await self.backend_router.route(chunk, mode)

            # Update context for next chunk
            context['previous_output'] = result.output
            steps.append(result)

        # 3. Return complete result
        return PipelineResult(
            final_output=context['previous_output'],
            steps=steps,
            execution_time=...,
            metadata=...
        )
```

---

### 4. backend_router.py

**Purpose:** Route chunks to appropriate backends (Ollama, ComfyUI, OpenRouter)

**Key Functionality:**
```python
class BackendRouter:
    async def route(
        self,
        chunk: ProcessedChunk,
        mode: str = "eco"
    ) -> ChunkResult:
        backend_type = chunk.backend_type

        if backend_type == "ollama":
            return await self._route_ollama(chunk, mode)
        elif backend_type == "comfyui":
            return await self._route_comfyui(chunk)
        elif backend_type == "openrouter":
            return await self._route_openrouter(chunk)
        else:
            raise ValueError(f"Unknown backend: {backend_type}")

    async def _route_ollama(self, chunk, mode):
        # Model selection based on task_type
        if chunk.model.startswith('task:'):
            task_name = chunk.model.split(':', 1)[1]
            model = self.model_selector.select_model(task_name, mode)
        else:
            model = chunk.model

        # Execute via Ollama service
        return await ollama_service.generate(model, chunk.prompt, chunk.parameters)
```

**UI_MODE Length Enforcement (Session 285):**

BackendRouter applies UI_MODE-adaptive length limits in `_process_prompt_interception_request()` before passing the request to `PromptInterceptionEngine`. This ensures interception output (student-facing) respects word budgets, while optimization (machine-consumed, called directly via engine) is unconstrained.

```
Interception path:  ChunkBuilder → BackendRouter (applies limits) → Engine → LLM
Optimization path:  execute_optimization() → Engine → LLM  (no limits)
```

**Backend Types:**
- `ollama`: Local LLM server (mistral-nemo, llama3.2, gemma2, etc.)
- `comfyui`: Local ComfyUI server (SD3.5, Flux1, Stable Audio, AceStep)
- `openrouter`: Cloud API (Claude, GPT-4, Gemini, etc.)

---

### 5. model_selector.py

**Purpose:** Task-based model selection (eco vs fast modes)

**Task Categories:**
```python
def _define_task_categories(self) -> Dict[str, Dict[str, str]]:
    return {
        "security": {
            "eco": "local/llama-guard-3-8b",
            "fast": "local/llama-guard-3-8b",  # Always local
            "description": "Content moderation"
        },
        "vision": {
            "eco": "local/llava:13b",
            "fast": "local/llava:13b",  # Always local (DSGVO)
            "description": "Image analysis"
        },
        "translation": {
            "eco": "local/qwen2.5-translator",
            "fast": "openrouter/anthropic/claude-3.5-haiku",
            "description": "Language translation"
        },
        "standard": {
            "eco": "local/mistral-nemo",
            "fast": "openrouter/mistralai/mistral-nemo",
            "description": "General text tasks"
        },
        "advanced": {
            "eco": "local/mistral-small:24b",
            "fast": "openrouter/google/gemini-2.5-pro",
            "description": "Complex reasoning, creativity"
        },
        "data_extraction": {
            "eco": "local/gemma3:4b",
            "fast": "openrouter/google/gemma-3-4b-it",
            "description": "Structured data extraction"
        }
    }
```

**Usage in Chunks:**
```json
{
  "model": "task:translation",  // Uses task-based selection
  "meta": {
    "task_type": "translation"
  }
}
```

**Execution Modes:**
- `eco`: Free local models (slower, privacy-preserving, DSGVO-compliant)
- `fast`: Paid cloud APIs (faster, higher quality, requires API keys)

---

### 6. instruction_selector.py

**Purpose:** Instruction-type selection for Prompt Interception (3-part prompts)

**Location:** `devserver/schemas/engine/instruction_selector.py`

**Pedagogical Background:**
The original ComfyUI `ai4artsed_prompt_interception` custom node used a 3-part prompt structure:
```python
full_prompt = (
    f"Task:\n{style_prompt.strip()}\n\n"
    f"Context:\n{input_context.strip()}\nPrompt:\n{input_prompt.strip()}"
)
```

This has been restored in DevServer's `manipulate` chunk with proper instruction-type system.

**Instruction Types:**
```python
INSTRUCTION_TYPES = {
    "artistic_transformation": {
        "description": "Transform prompt through artistic/cultural lens (Prompt Interception)",
        "default": """Transform the input_prompt into a description according to the instructions
defined in the input_context. Explicitely communicate the input_context as cultural cf. artistic
cf. intervening context. Also communicate genres/artistic traditions in a concrete way (i.e. is
it a dance, a photo, a painting, a song, a movie, a statue/sculpture? how should it be translated
into media?)

This is not a linguistic translation, but an aesthetic, semantic and structural transformation.
Be verbose!

Reconstruct all entities and their relations as specified, ensuring that:
- Each entity is retained – or respectively transformed – as instructed.
- Each relation is altered in line with the particular aesthetics, genre-typical traits, and logic
  of the "Context". Be explicit about visual aesthetics in terms of materials, techniques, composition,
  and overall atmosphere. Mention the input_context als cultural, cf. artistic, c.f intervening context
  in your OUTPUT explicitely.

Output only the transformed description as plain descriptive text. Be aware if the output is something
depicted (like a ritual or any situation) OR itself a cultural artefact (such as a specific drawing
technique). Describe accordingly. In your output, communicate which elements are most important for an
succeeding media generation.

DO NOT USE ANY META-TERMS, NO HEADERS, STRUCTURAL MARKERS WHATSOEVER. DO NOT EXPLAIN YOUR REASONING.
JUST PUT OUT THE TRANSFORMED DESCRIPTIVE TEXT."""
    },
    "passthrough": {
        "description": "No transformation - direct pass-through (for testing/debugging)",
        "default": """Output the input_prompt exactly as provided, with no modification or transformation."""
    }
}
```

**Usage in Pipelines:**
```json
{
  "name": "text_transformation",
  "instruction_type": "artistic_transformation",
  "chunks": ["manipulate"]
}
```

**Usage in Configs (Config-Level Override):**
```json
{
  "pipeline": "text_transformation",
  "instruction_type": "artistic_transformation",
  "context": "You are an artist working in the spirit of Dadaism...",
  "name": {"en": "Dadaism"}
}
```

**Priority System (Mirrors model_selector):**
1. **Config-level override**: `config.task_instruction` (custom instruction text)
2. **Pipeline-level default**: `pipeline.instruction_type` → looks up instruction in INSTRUCTION_TYPES
3. **System fallback**: "artistic_transformation"

**3-Part Prompt Structure:**
The `manipulate` chunk template implements the ComfyUI prompt_interception structure:
```
Task:
{{TASK_INSTRUCTION}}

Context:
{{CONTEXT}}

Prompt:
{{INPUT_TEXT}}
```

Where:
- `TASK_INSTRUCTION`: From instruction_selector (how to transform)
- `CONTEXT`: From config.context (artistic attitude/cultural background)
- `INPUT_TEXT`: User's input (the prompt to be transformed)

**Implementation:**
```python
# In chunk_builder.py
def _get_task_instruction(self, resolved_config, pipeline):
    from .instruction_selector import get_instruction

    # Check for custom override in config
    custom_instruction = getattr(resolved_config, 'task_instruction', None)

    # Get instruction_type from pipeline or config
    instruction_type = getattr(pipeline, 'instruction_type', 'artistic_transformation')

    return get_instruction(instruction_type, custom_instruction)
```

**Benefits:**
- **Transparency**: ENDUSER can see instruction in config/pipeline
- **Editability**: Configs can override instruction type
- **Consistency**: Mirrors model_selector architecture
- **Pedagogical**: Maintains original ComfyUI prompt_interception concept

---

### 7. comfyui_workflow_generator.py

**Status:** ⚠️ **DEPRECATED** - Will be removed in future cleanup

**Historical Purpose:** Generated ComfyUI workflows dynamically from Python templates

**Why Deprecated:**
- Output-Chunks now contain complete ComfyUI API workflows embedded in JSON
- No dynamic generation needed - server fills placeholders and submits directly
- Simplifies architecture - workflows are data, not code
- See "Output Chunk" documentation above for new approach

**Migration Path:**
- Extract workflows from `comfyui_workflow_generator.py` templates
- Convert to Output-Chunk JSON format with `input_mappings` and `output_mapping`
- Store in `schemas/chunks/output_*.json`
- Update backend_router to process Output-Chunks instead of calling generator

---


### 8. prompt_interception_engine.py

**Status:** ✅ **ACTIVE** - Backend proxy layer

**Purpose:** Routes Ollama/OpenRouter API calls with fallback handling

**Role:** Backend proxy (NOT a chunk or pipeline)
- Routes all Ollama/OpenRouter requests from BackendRouter
- Handles model fallbacks and error recovery
- Provides unified API interface for both backends

**Architecture Position:**
```
Chunk (manipulate.json)
  → ChunkBuilder
    → BackendRouter.route()
      → PromptInterceptionEngine (backend proxy)
        → Ollama/OpenRouter API
```

**Key Methods:**
- `process_request()` - Main processing with fallback logic (pure LLM routing, no policy)
- `_call_ollama()` - Direct Ollama API calls
- `_call_openrouter()` - Direct OpenRouter API calls
- `_find_ollama_fallback()` / `_find_openrouter_fallback()` - Model fallback logic

**Exported Constants** (used by BackendRouter for interception-path limits):
- `UI_MODE_WORD_LIMITS` - Word budget per UI_MODE (kids=80, youth=150, expert=250)
- `UI_MODE_MAX_TOKENS_SAFETY` - Token safety cap per UI_MODE (kids=400, youth=600, expert=800)

**Usage:**
1. `backend_router.py` - Routes all Ollama/OpenRouter chunks through this (with UI_MODE limits applied by BackendRouter)
2. `schema_pipeline_routes.py` - Direct optimization calls (no UI_MODE limits — output is machine-consumed)

**Note:** Previously marked as DEPRECATED in docs - this was incorrect. Module is actively used. The engine is a pure LLM router — UI_MODE length limits are enforced by BackendRouter (interception path), not by the engine itself.

---

### 9. output_config_selector.py

**Purpose:** Select default output config based on media type and execution mode

**Architecture Principle:** Separation of concerns
- Pre-pipeline configs (dada.json) suggest media type via `media_preferences.default_output`
- Pre-pipeline configs DO NOT choose specific models
- This module provides centralized mapping: `media_type + execution_mode → output_config`

**Key Classes:**
```python
@dataclass
class MediaOutput:
    """Track generated media throughout pipeline"""
    media_type: str  # "image", "audio", "music", "video"
    prompt_id: str   # ComfyUI queue ID
    output_mapping: Dict[str, Any]
    config_name: str
    status: str  # "queued", "generating", "completed", "failed"
    metadata: Optional[Dict[str, Any]]

@dataclass
class ExecutionContext:
    """Track expected and actual media throughout execution"""
    config_name: str
    execution_mode: str  # "eco" or "fast"
    expected_media_type: str
    generated_media: List[MediaOutput]
    text_outputs: List[str]
```

**Selection Logic:**
```python
# Example: Image generation in eco mode
media_type = "image"
execution_mode = "eco"
→ Returns "sd35_large" (Stable Diffusion 3.5 Large, local)

# Example: Image generation in fast mode
media_type = "image"
execution_mode = "fast"
→ Returns "dalle3" (DALL-E 3 via OpenRouter)
```

**Benefits:**
- Centralized default logic
- Clean separation: pre-pipeline configs focus on pedagogy, not technical model selection
- Easy to update default models without touching config files

---

### 10. stage_orchestrator.py

**Purpose:** Helper functions for 4-stage pipeline architecture

**Context:** Extracted from `pipeline_executor.py` for Phase 2 refactoring
- DevServer (schema_pipeline_routes.py) orchestrates Stage 1-3
- PipelineExecutor becomes a "dumb" executor (just runs chunks)
- These helper functions support the smart orchestrator

**Key Functions:**

#### Safety Filtering (Hybrid Approach)
```python
def load_filter_terms() -> Dict[str, List[str]]:
    """Load safety filter terms (cached)"""
    # Loads from:
    # - youth_kids_safety_filters.json (Stage 3: Kids/Youth)
    # - stage1_safety_filters.json (Stage 1: CSAM/Violence/Hate)

def check_stage1_safety(text: str) -> Tuple[bool, Optional[str]]:
    """Fast string-matching for critical terms"""
    # Blocks: CSAM, extreme violence, hate speech
    # Returns: (is_safe, blocked_reason)

def check_stage3_safety(text: str, safety_level: str) -> Tuple[bool, Optional[str]]:
    """Age-appropriate content filtering"""
    # safety_level: "kids" (8-12) or "youth" (13-17)
    # Checks for age-inappropriate content
```

#### Bilingual §86a Compliance (Germany)
```python
def check_86a_violation(text: str) -> Tuple[bool, Optional[str]]:
    """Check for prohibited symbols under German law"""
    # Detects: Nazi symbols, terrorist symbols, extremist codes
    # Bilingual: German and English terms
    # Returns: (is_violation, explanation)
```

**Workflow Integration:**
1. Stage 1: User input → `check_stage1_safety()` + `check_86a_violation()`
2. Stage 3: Pre-output → `check_stage3_safety(safety_level)`
3. If blocked → Return error to user with explanation

**Files:**
- `schemas/engine/stage_orchestrator.py` - Main helpers
- `schemas/youth_kids_safety_filters.json` - Stage 3 filters
- `schemas/stage1_safety_filters.json` - Stage 1 filters

---

### 11. random_language_selector.py

**Purpose:** Random language selection for translation pipelines

**Use Case:** Pedagogical feature for multilingual exploration
- Students can request "random language" translation
- System selects from 15 supported languages
- Supports exclusion list (e.g., exclude source language)

**Supported Languages:**
- European: English, German, French, Spanish, Italian, Portuguese, Dutch, Polish, Russian, Turkish
- Asian: Chinese, Japanese, Korean, Hindi
- Middle Eastern: Arabic

**Key Function:**
```python
def get_random_language(exclude: Optional[List[str]] = None) -> str:
    """
    Get random language code, optionally excluding certain languages
    
    Args:
        exclude: List of language codes to exclude (e.g., ['de', 'en'])
    
    Returns:
        Language code (e.g., 'fr', 'es', 'ja')
    """
```

**Example Usage:**
```python
# Student requests random translation from German
source_lang = 'de'
target_lang = get_random_language(exclude=['de'])
# → Might return 'ja' (Japanese), 'ar' (Arabic), etc.
```

**Pedagogical Value:**
- Encourages exploration of non-English languages
- Discovers linguistic patterns across cultures
- Breaks English-centric assumptions

---

## 12. Services & Lifecycle Management

### SwarmUI Manager (swarmui_manager.py)

**Location:** `devserver/my_app/services/swarmui_manager.py`

**Purpose:** Automatic lifecycle management for SwarmUI backend

**Pattern:** Singleton with lazy initialization (on-demand)

**Core Responsibility:** Ensure SwarmUI is available when needed, auto-start if not running

#### Architecture Overview

```python
class SwarmUIManager:
    """Manages SwarmUI lifecycle: startup, health checks, auto-recovery

    Design Pattern: Singleton with lazy initialization
    Thread Safety: asyncio.Lock for concurrent startup attempts
    """

    def __init__(self):
        # Ports
        self.swarmui_port = 7801  # REST API
        self.comfyui_port = 7821  # ComfyUI backend

        # Concurrency control
        self._startup_lock = asyncio.Lock()
        self._is_starting = False

        # Configuration (from config.py)
        self._auto_start_enabled = SWARMUI_AUTO_START
        self._startup_timeout = SWARMUI_STARTUP_TIMEOUT
        self._health_check_interval = SWARMUI_HEALTH_CHECK_INTERVAL
```

#### Key Methods

**1. ensure_swarmui_available() → bool**
- Main entry point for all services needing SwarmUI
- Guarantees SwarmUI is running (auto-starts if needed)
- Returns True if available, False if auto-start disabled/failed

**Flow:**
1. Quick health check (no lock needed)
2. If healthy → return True immediately
3. If unhealthy → Acquire lock (prevent race conditions)
4. Double-check after lock (another thread might have started)
5. Start SwarmUI if still needed
6. Wait for ready state

**2. is_healthy() → bool**
- Checks BOTH ports (7801 + 7821)
- Reuses health_check() from swarmui_client and comfyui_client
- Returns True only if both are responsive

**3. _start_swarmui() → bool**
- Executes `2_start_swarmui.sh` via subprocess.Popen
- Runs in background (non-blocking, detached process)
- Waits for ready state via polling
- Returns True if startup successful within timeout

**4. _wait_for_ready() → bool**
- Polls health endpoints every 2 seconds
- Timeout: 120 seconds (configurable)
- Logs progress and warnings
- Returns True if ready, False on timeout

#### Concurrency Safety (Critical)

**Problem:** Multiple concurrent requests could trigger simultaneous SwarmUI startup attempts.

**Solution: Double-Check Locking Pattern**
```python
async def ensure_swarmui_available(self) -> bool:
    # 1. Quick check (no lock)
    if await self.is_healthy():
        return True

    # 2. Acquire lock
    async with self._startup_lock:
        # 3. Double-check after lock
        if await self.is_healthy():
            logger.info("[SWARMUI-MANAGER] Another thread started SwarmUI")
            return True

        # 4. Only ONE thread proceeds with startup
        return await self._start_swarmui()
```

**Why This Works:**
- First healthy check avoids lock overhead when already running
- Lock prevents concurrent startup attempts
- Second check avoids duplicate starts if another thread just finished
- Only one thread ever executes _start_swarmui()

#### Integration Points

**1. LegacyWorkflowService** (`legacy_workflow_service.py:95`)
```python
# Step 2.5: Ensure SwarmUI is available
logger.info("[LEGACY-SERVICE] Ensuring SwarmUI is available...")
if not await self.swarmui_manager.ensure_swarmui_available():
    raise Exception("Failed to start SwarmUI - cannot submit workflow")
```

**2. BackendRouter** (`backend_router.py`)
```python
# Constructor (line 150)
def __init__(self):
    self.backends: Dict[BackendType, Any] = {}
    self._initialized = False
    from my_app.services.swarmui_manager import get_swarmui_manager
    self.swarmui_manager = get_swarmui_manager()

# Before SwarmUI Text2Image (line 550)
if not await self.swarmui_manager.ensure_swarmui_available():
    return BackendResponse(success=False, error="SwarmUI not available")

# Before SwarmUI Workflow (line 684)
if not await self.swarmui_manager.ensure_swarmui_available():
    return BackendResponse(success=False, error="SwarmUI not available")

# Before image upload - single (line 893)
if not await self.swarmui_manager.ensure_swarmui_available():
    logger.error("[LEGACY-WORKFLOW] SwarmUI not available, upload will fail")

# Before image upload - multi (line 941)
await self.swarmui_manager.ensure_swarmui_available()
```

#### Configuration

**Location:** `devserver/config.py`

```python
# SWARMUI AUTO-RECOVERY CONFIGURATION
SWARMUI_AUTO_START = os.environ.get("SWARMUI_AUTO_START", "true").lower() == "true"
SWARMUI_STARTUP_TIMEOUT = int(os.environ.get("SWARMUI_STARTUP_TIMEOUT", "120"))  # seconds
SWARMUI_HEALTH_CHECK_INTERVAL = float(os.environ.get("SWARMUI_HEALTH_CHECK_INTERVAL", "2.0"))  # seconds
```

**Environment Variable Overrides:**
```bash
export SWARMUI_AUTO_START=false          # Disable auto-start (for testing)
export SWARMUI_STARTUP_TIMEOUT=180       # Increase timeout to 3 minutes
export SWARMUI_HEALTH_CHECK_INTERVAL=1.0 # Poll every 1 second
```

#### Startup Script Enhancement

**File:** `2_start_swarmui.sh`

**Key Addition:**
```bash
# Start SwarmUI without opening browser (--launch_mode none)
./launch-linux.sh --launch_mode none
```

**Why Command-Line Argument:**
- Overrides `LaunchMode: web` in SwarmUI's `Settings.fds`
- Works on ANY SwarmUI installation (no settings file modification)
- Prevents browser tab from opening and hiding the frontend
- Portable solution for third-party installations

**SwarmUI's Implementation:**
```csharp
// src/Core/Program.cs
LaunchMode = GetCommandLineFlag("launch_mode", ServerSettings.LaunchMode);
```

#### Benefits

1. **Independence:** DevServer starts without requiring SwarmUI to be running
2. **Crash Recovery:** Automatic recovery from SwarmUI runtime crashes
3. **User Experience:** No manual intervention needed, frontend stays visible
4. **Performance:** Lazy initialization - only starts when actually needed
5. **Safety:** Race-condition proof with double-check locking
6. **Flexibility:** Configurable via environment variables
7. **Portability:** Works with any SwarmUI installation

#### Error Handling

**Scenario 1: Script Not Found**
```python
if not script_path.exists():
    logger.error(f"[SWARMUI-MANAGER] Startup script not found: {script_path}")
    logger.error("[SWARMUI-MANAGER] Please start SwarmUI manually")
    return False
```

**Scenario 2: Startup Timeout (120s)**
```python
if elapsed > self._startup_timeout:
    logger.error(f"[SWARMUI-MANAGER] Timeout after {self._startup_timeout}s")
    logger.error("[SWARMUI-MANAGER] Check SwarmUI logs for startup issues")
    return False
```

**Scenario 3: Auto-Start Disabled**
```python
if not self._auto_start_enabled:
    logger.warning("[SWARMUI-MANAGER] Auto-start disabled, SwarmUI not available")
    return False
```

#### Logging & Monitoring

**Startup Sequence:**
```
[SWARMUI-TEXT2IMAGE] Ensuring SwarmUI is available...
[SWARMUI-MANAGER] SwarmUI not available, starting...
[SWARMUI-MANAGER] Starting SwarmUI via: /path/to/2_start_swarmui.sh
[SWARMUI-MANAGER] SwarmUI process started (PID: 12345)
[SWARMUI-MANAGER] Waiting for SwarmUI (timeout: 120s)...
[SWARMUI-MANAGER] Still waiting... (15.2s elapsed)
[SWARMUI-MANAGER] ✓ SwarmUI ready! (took 45.2s)
```

**Health Check Logs (Debug Level):**
```
[SWARMUI-MANAGER] Already healthy
[SWARMUI-MANAGER] Health check: SwarmUI=True, ComfyUI=True
[SWARMUI-MANAGER] Health check failed: Cannot connect to host
```

#### Design Decisions

**Why Lazy (On-Demand) vs. Eager (Startup)?**
- ✅ Faster DevServer startup (no 60s wait)
- ✅ Handles runtime crashes (not just startup)
- ✅ Only loads when needed (user might not use media generation)
- ✅ Better separation of concerns

**Why Singleton Pattern?**
- ✅ Single source of truth for SwarmUI state
- ✅ Prevents duplicate managers with conflicting locks
- ✅ Shared across all services needing SwarmUI

**Why Double-Check Locking?**
- ✅ Avoids lock overhead when already running (common case)
- ✅ Prevents race conditions (only ONE startup attempt)
- ✅ Industry-standard concurrency pattern

#### Testing Considerations

**Manual Test Cases:**
1. **Cold Start:** Stop SwarmUI, trigger image generation → Auto-starts
2. **Runtime Crash:** Generate image, kill SwarmUI, generate again → Auto-recovery
3. **Concurrent Requests:** Stop SwarmUI, send 5 requests → Only ONE startup
4. **Disabled Auto-Start:** Set `SWARMUI_AUTO_START=false` → Graceful error
5. **Timeout:** Block port 7821, trigger generation → Timeout after 120s

**Expected Metrics:**
- Startup time: 30-60 seconds (depends on hardware)
- Health check overhead: <10ms per check
- Lock contention: Minimal (only during startup window)

---

## Summary: Complete Engine Module List

### Core Execution
1. ✅ **config_loader.py** - Load configs and pipelines
2. ✅ **chunk_builder.py** - Build chunks with placeholder replacement
3. ✅ **pipeline_executor.py** - Execute complete pipelines
4. ✅ **backend_router.py** - Route to appropriate backends

### Intelligence & Selection
5. ✅ **model_selector.py** - Task-based model selection (eco vs fast)
6. ✅ **instruction_selector.py** - Instruction-type selection for prompts
7. ✅ **output_config_selector.py** - Select output config by media type
8. ✅ **random_language_selector.py** - Random language for translations

### Backend & Routing
9. ✅ **prompt_interception_engine.py** - Backend proxy for Ollama/OpenRouter
10. ⚠️ **comfyui_workflow_generator.py** - DEPRECATED (use Output-Chunks)

### Orchestration & Safety
11. ✅ **stage_orchestrator.py** - 4-stage helpers & safety filtering

### Services & Lifecycle
12. ✅ **swarmui_manager.py** - SwarmUI auto-recovery & lifecycle management

**Total: 12 modules** (11 active, 1 deprecated)

---

## 13. Dependencies & Requirements

### Required Python Packages

**Critical:** The following packages are required for backend routing functionality:

#### aiohttp
- **Version:** 3.13.2 (or compatible)
- **Required by:** ComfyUI/SwarmUI client modules
- **Import locations:**
  - `devserver/my_app/services/comfyui_client.py:5`
  - `devserver/my_app/services/swarmui_client.py:5`
- **Failure mode:** If missing, Stage 4 media generation fails with "No run_id returned from API"
- **Why not obvious:** Import occurs at function call time (line 333 in `backend_router.py`), not at module load time
- **Fix:** `pip install aiohttp` in production virtualenv

**Production Deployment Note:** Always verify `requirements.txt` installation in production environment before starting backend service. Missing dependencies will cause silent failures during media generation stages.

