# DevServer Architecture
**AI4ArtsEd Development Server - Complete Technical Reference**

> **Last Updated:** 2025-11-26
> **Status:** AUTHORITATIVE - 4-Stage Orchestration Architecture Documented (v2.0.0-alpha.1) + Stage 2 Refactoring
> **Version:** 3.1 (4-Stage Flow + Stage 2 Separation: Interception & Optimization isolated)

---
THIS IS A MULTI-PART-DOCUMENTATION:
Pattern: ARCHITECTURE PART XX - SUBJECTMATTER.md

Use it accordingly.

THIS FILE IS ABOUT THE 4-STAGE-ORCHESTRATION.

---

## 🏗️ MANDATORY: File Structure Rules

**⚠️ CRITICAL: NEVER create new directories without consulting these rules.**

### Root Level (`/ai4artsed_webserver/`)

**ONLY these directories are allowed at project root:**
- `server/` - ⚠️ LEGACY - DO NOT TOUCH
- `public/` - ✅ Vue-based frontend (new architecture)
- `docs/` - ✅ Project documentation (authoritative architecture docs)
- `devserver/` - ✅ NEW ARCHITECTURE (work here)
- `exports/` - ✅ Pipeline run storage (`/json/`, `/media/`)
- `workflows/` - ✅ ComfyUI workflows (if applicable)

### DevServer Level (`/devserver/`)

**ONLY these directories are allowed at devserver root:**
- **Core files:** `server.py`, `config.py`, `CLAUDE.md`
- `schemas/` - Pipeline system (chunks, pipelines, configs, engine)
- `my_app/` - Application code (routes, services)
- `tests/` - Test files
- `archive/` - Deprecated code (DO NOT EDIT)

**❌ FORBIDDEN at devserver root:**
- New service modules → Put in `/devserver/my_app/services/`
- New route modules → Put in `/devserver/my_app/routes/`
- Documentation → Use `/docs/` (project root)
- Frontend projects → Use `/public/` (project root)

### Documentation Structure

**ALL documentation MUST go in:** `/docs/` (project root)

**Current structure:**
- `ARCHITECTURE PART XX - *.md` - Technical reference (AUTHORITATIVE)
- `DEVELOPMENT_DECISIONS.md` - Decision history
- `README_FIRST.md` - Mandatory reading for new sessions (if exists)
- `devserver_todos.md` - Task tracking

**❌ FORBIDDEN:**
- `/devserver/docs/` - Session-specific docs must go in `/docs/`
- Documentation in random locations

### Service Module Location

**ALL service modules MUST go in:** `/devserver/my_app/services/`

**Examples:**
- ✅ `/devserver/my_app/services/ollama_service.py`
- ✅ `/devserver/my_app/services/comfyui_service.py`
- ✅ `/devserver/my_app/services/media_storage.py`
- ✅ `/devserver/my_app/services/pipeline_recorder/` (if directory)
- ❌ `/devserver/pipeline_recorder/` - WRONG LOCATION

### Frontend Location

**Active frontend:** `/public/` (project root)

**Current status:**
- ✅ `/public/` - Vue-based frontend (new architecture)
- `/devserver/public_dev/` and `/public_dev/` (the pre-Vue client) - removed 2026-10-10 together with the routes only that client called (`/run_workflow_stream`, `/workflow-status-poll`, `/api/export-session`, `/api/download-session`, `/sse/*`, `/api/active-users`, `/api/queue-status`, `/config`)

**Server configuration:** `config.py` → `PUBLIC_DIR = Path(__file__).parent.parent / "public"`

### Why These Rules?

1. **Consistency:** All sessions follow same structure
2. **Clarity:** No guessing where files belong
3. **Maintainability:** Easy to find and modify code
4. **Documentation:** Single source of truth in `/docs/`
5. **Architecture Transparency:** Structure reflects design decisions

**If you need to create new directories:** Ask the user first.

---

# PART I: ORCHESTRATION

---

## 1. 4-Stage Orchestration Flow

**⭐ AUTHORITATIVE SECTION - Read this first before implementing any flow logic**

**Version:** 2.3 (2025-11-26 - Stage 2 Functions Separated - Interception & Optimization isolated)
**Previous Version:** 2.2 (2025-11-23 - Stage 2 Split into 2-Phase Execution)
**Source:** Consolidated from 4_STAGE_ARCHITECTURE.md

### 1.1 Executive Summary

**DevServer orchestrates a 4-stage flow where:**
- **Stage 1**, the intake, checks each new piece of the user's material once, before Stage 2
- **Stage 2** executes the main pipeline (can be complex: loops, branches, multiple outputs)
- **Stage 3-4** run once PER OUTPUT REQUEST from Stage 2 (not once per pipeline): the translation and the check before the model, then the generation

**Key Principle:** Pipelines are DUMB (declare inputs/outputs), DevServer is SMART (knows safety rules).

The checks sit at three places: the intake, the step before a media model, and the result before it leaves the server. Section 1.7 describes them; `devserver/my_app/services/safety_gate.py` holds them.

### 1.2 Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ DevServer (schema_pipeline_routes.py)                          │
│ ROLE: Smart Orchestrator - Knows 4-Stage Flow & Safety Rules   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ STAGE 1: Intake (check_intake, once per piece of material)     │
│ ════════════════════════════════════════════════════════════   │
│   Every new piece of the user's material, on the server:       │
│   - texts: names of living private individuals and addresses   │
│     with a house number (name recogniser, address pattern;     │
│     after a hit the classifier's name question)                │
│   - uploaded pictures (kids, youth): the level's picture       │
│     question                                                   │
│                                                                 │
│   Text stays in its original language for Stage 2.             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ STAGE 2: Interception + Optimization (Main Pipeline)           │
│ ════════════════════════════════════════════════════════════   │
│   **2-PHASE EXECUTION** (2025-11-23):                         │
│   **REFACTORED** (2025-11-26):                                │
│                                                                 │
│   Phase 1: INTERCEPTION (Pedagogical Transformation)          │
│     execute_stage2_interception() [NEW]                       │
│     - Uses: config.context (pädagogischer Context)            │
│     - Model: STAGE2_INTERCEPTION_MODEL (from config.py)       │
│     - Output: interception_result (editierbar)                │
│     - CRITICAL: Zero access to optimization_instruction       │
│                                                                 │
│   Phase 2: OPTIMIZATION (Model-specific Refinement)           │
│     execute_optimization() [NEW]                              │
│     - Uses: output_config.optimization_instruction ONLY       │
│     - Model: STAGE2_INTERCEPTION_MODEL (from config.py)       │
│     - Input: interception_result (from Phase 1)               │
│     - Output: optimized_prompt (editierbar)                   │
│     - CRITICAL: Zero access to config.context                 │
│     - NOTE: optimization_instruction goes in CONTEXT field    │
│            (USER_RULES), NOT appended to existing context     │
│                                                                 │
│   Why Split?                                                  │
│   - CRITICAL BUG FIX: config.context was contaminating opt.   │
│   - Old code: context = config.context + opt_instruction ❌   │
│   - New code: opt_instruction IS the context, separate call ✅ │
│   - Each function has single responsibility                   │
│   - Isolation prevents future context leakage                 │
│   - See DEVELOPMENT_DECISIONS.md "Active Decision NEW" section│
│                                                                 │
│   DEPRECATED: execute_stage2_with_optimization()              │
│   - Kept for backward compatibility (calls both funcs)        │
│   - Emits DeprecationWarning - guides future refactoring      │
│   - To be removed after a safe period                         │
│                                                                 │
│   PipelineExecutor.execute_pipeline(config, inputs)            │
│   - DUMB: Just executes chunks                                 │
│   - NO pre-processing, NO safety checks, NO translation       │
│   - CAN: loop, branch, request multiple outputs               │
│                                                                 │

#### Media-Specific Optimization (Config Override Pattern)

**Feature:** Extend Stage 2 context with output-specific optimization instructions

**Use Case:** SD3.5 Large uses Dual CLIP architecture (clip_g + t5xxl) requiring specialized prompt optimization

**Implementation Pattern:**
1. Output config declares `OUTPUT_CHUNK` parameter pointing to chunk name
2. DevServer loads chunk JSON directly from filesystem
3. Extract `meta.optimization_instruction` from output chunk
4. Use `dataclasses.replace()` to create modified config with extended context
5. Pass `config_override` to pipeline executor

**Code Example:**
```python
from dataclasses import replace

# Load optimization instruction from output chunk metadata
optimization_instruction = output_chunk['meta'].get('optimization_instruction')

if optimization_instruction:
    # Get original context
    original_context = config.context if hasattr(config, 'context') else ""
    new_context = original_context + "\n\n" + optimization_instruction

    # Create modified config using dataclasses.replace()
    stage2_config = replace(
        config,
        context=new_context,
        meta={**config.meta, 'optimization_added': True}
    )

    # Execute pipeline with overridden config
    result = await pipeline_executor.execute_pipeline(
        config_name=schema_name,
        input_text=input_text,
        config_override=stage2_config
    )
```

**Why This Pattern:**
- ✅ Single LLM call combines interception + optimization (pedagogical constraint)
- ✅ Optimization instruction stored in output chunk where model config lives
- ✅ Fetched at runtime based on selected output config
- ✅ Non-invasive: Original config unchanged, override applied dynamically

**Critical Implementation Notes:**
- ⚠️ MUST use `dataclasses.replace()`, NOT `Config.from_dict()` (doesn't exist)
- ⚠️ MUST load chunks directly from filesystem, NOT via `ConfigLoader.get_chunk()` (doesn't exist)
- ⚠️ MUST use `await` for pipeline execution, NOT `asyncio.run()` (can't nest event loops)

**Bug History:** 2025-11-22 - Fixed 3 critical implementation bugs that prevented this feature from working

│   Pipeline returns: PipelineResult {                           │
│     final_output: "transformed + optimized text (orig lang)",  │
│     output_requests: [                                         │
│       {type: "image", prompt: "...", params: {...}},          │
│       {type: "audio", prompt: "...", params: {...}}           │
│     ]                                                          │
│   }                                                            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ STAGE 3-4: For EACH output_request from Stage 2                │
│ ════════════════════════════════════════════════════════════   │
│   FOR EACH request in pipeline_result.output_requests:         │
│                                                                 │
│     STAGE 3a: Translation (if needed)                          │
│       - IF source_language != 'en': Translate DE → EN         │
│       - Media generation requires English prompts             │
│       - User can edit BEFORE this stage (in original lang)    │
│                                                                 │
│     STAGE 3b: The check before the model (check_before_model)  │
│       - the §86a lists of every language over the original     │
│         and the English version                                │
│       - then the safety classifier with the level's question   │
│       - If blocked: no Stage 4; the block message goes back    │
│                                                                 │
│     STAGE 4: Media Generation                                  │
│       - Execute output config (e.g., gpt5_image)              │
│       - Generate media with English prompt                     │
│       - Return media reference (prompt_id, URL, etc.)         │
│                                                                 │
│     AT THE RESULT: check_result_image (kids, youth): every     │
│       picture of the run, before it leaves the server          │
│                                                                 │
│   Collect all generated media + metadata                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Separation of Concerns

#### What Pipelines Declare (DUMB)

**Pipeline configs declare ONLY input/output structure:**

```json
{
  "name": "complex_interception",
  "input_requirements": {
    "texts": 2,           // "I need 2 text inputs"
    "images": 1           // "I need 1 image input"
  },
  "chunks": ["manipulate", "translate", ...],
  "control_flow": "iterative",
  "meta": {
    "max_iterations": 8,
    "supports_multiple_outputs": true
  }
}
```

**Pipelines DO NOT declare:**
- ❌ Safety requirements (DevServer knows this)
- ❌ Translation needs (DevServer knows: text → translate)
- ❌ Pre-processing steps (DevServer runs the intake)
- ❌ When to run safety checks (the routes call the three checks, section 1.7)

#### What DevServer Knows (SMART)

**DevServer holds the safety rules in one module, `my_app/services/safety_gate.py`.**
The routes call its checks at three places (section 1.7); no pipeline config names a check.

**Why non-redundant?**
- If a run brings two texts, the intake reads both
- No duplication in pipeline configs
- Change safety rules in ONE place (DevServer)
- Prevents inconsistencies

### 1.4 Stage-by-Stage Flow

[See above, 1.2 Core Architecture and IMPLEMENTATION_PLAN_4_STAGE_REFACTORING.md]

### 1.5 Complex Pipeline Examples

#### Example 1: Simple Text Transformation + Image

**User Input:** "EIne Blume auf der Wiese"
**Config:** overdrive.json
**Execution Mode:** fast
**Safety Level:** kids

**Flow:**
```
┌─ STAGE 1 (Run ONCE) ─────────────────────────────────────────┐
│ Input: "EIne Blume auf der Wiese"                            │
│ → Intake: PASSED (no private person named, no address)      │
└──────────────────────────────────────────────────────────────┘

┌─ STAGE 2 (Main Pipeline) ────────────────────────────────────┐
│ Pipeline: overdrive (text_transformation)                    │
│ Input: "EIne Blume auf der Wiese"                            │
│ → manipulate chunk with overdrive context                    │
│ Output: "In the vast, undulating sea of emerald..."         │
│                                                              │
│ Output Requests: [                                           │
│   {type: "image", prompt: "In the vast, undulating..."}     │
│ ]                                                            │
└──────────────────────────────────────────────────────────────┘

┌─ STAGE 3-4 (Run ONCE per output request) ───────────────────┐
│ Request #1: image                                            │
│                                                              │
│ STAGE 3: The check before the model                         │
│   Prompt: "In the vast, undulating..."                      │
│   → Lists and the classifier's question → PASSED            │
│                                                              │
│ STAGE 4: Media Generation                                   │
│   Lookup: image/fast → gpt5_image                           │
│   → execute_pipeline('gpt5_image', prompt) [NO STAGE 1-3!]  │
│   → Returns: prompt_id "abc123"                             │
└──────────────────────────────────────────────────────────────┘
```

**The bug of 2025-11 (fixed, see 1.6; no check runs inside `execute_pipeline()` now):**
```
✅ Stage 1 runs once → Good
✅ Stage 2 runs once → Good
✅ Stage 3 runs once → Good
❌ Stage 4 calls execute_pipeline('gpt5_image', ...)
   → execute_pipeline() runs Stage 1-3 AGAIN! → BAD
   → Translation runs on already-English text
   → Safety runs twice
   → Wasted time + API calls
```

#### Example 3: Multi-Output (Model Comparison)

**Scenario:** Generate same prompt with multiple models for comparison

**Config:** `image_comparison.json`
```json
{
  "pipeline": "text_transformation",
  "context": "Pass through unchanged",
  "media_preferences": {
    "output_configs": ["sd35_large", "gpt5_image"]
  }
}
```

**Flow:**
```
Input: "Eine Blume auf der Wiese"
  ↓
Stage 1: the intake (once)
  → PASSED
  ↓
Stage 2: text_transformation (once)
  → "Eine Blume auf der Wiese" (pass-through)
  ↓
Stage 3-4 Loop: FOR EACH output_config
  ├─ Iteration 1: sd35_large
  │  ├─ Stage 3: The check before the model ✅
  │  └─ Stage 4: ComfyUI workflow → image_1.png
  └─ Iteration 2: gpt5_image
     ├─ Stage 3: The check before the model ✅
     └─ Stage 4: OpenRouter API → image_2.png

Response: {
  "media_outputs": [
    {"config": "sd35_large", "output": "prompt_id_1"},
    {"config": "gpt5_image", "output": "base64_data"}
  ]
}
```

**Key Points:**
✅ Stage 1 runs once (not 2x) - the intake reads the input once
✅ Stage 2 runs once (not 2x) - no redundant pipeline
✅ Stage 3-4 loop per output - each gets independent safety check
✅ Efficient: Only outputs require duplication, not inputs

**Use Cases:**
- Model comparison (SD3.5 vs GPT-5)
- Multi-format output (image + audio)
- Multi-resolution output (1024px + 2048px)

**Implementation:** See `schema_pipeline_routes.py` Stage 3-4 Loop

#### Example 4: Recursive Pipeline (Stille Post)

**Scenario:** 8-iteration translation loop (Chinese Whispers)

**Config:** `stillepost.json`
```json
{
  "pipeline": "text_transformation_recursive",
  "parameters": {
    "iterations": 8,
    "use_random_languages": true,
    "final_language": "en"
  }
}
```

**Flow:**
```
Input: "Eine Blume auf der Wiese"
  ↓
Stage 1: the intake (once)
  → PASSED
  ↓
Stage 2: text_transformation_recursive (once, loops internally)
  Iteration 1: translate to Hindi
  Iteration 2: translate to Polish
  ...
  Iteration 8: translate to English
  → "The Dutch translation of..." (mangled text)
  ↓
Stage 3: The check before the model ✅
  ↓
Stage 4: Media Generation → image.png
```

**Key Points:**
✅ Stage 1 runs once (not 8x) - Critical test PASSED
✅ Loop runs INSIDE Stage 2 pipeline
✅ Config controls loop behavior (iterations, languages, final_language)
❌ Does NOT call execute_pipeline() recursively

**Pedagogical Goal:**
- Students see prompt degradation over iterations
- "Stille Post" (Chinese Whispers) workflow
- User-editable configs for different iteration counts

**Implementation:** See `pipeline_executor.py` _execute_recursive_pipeline_steps()

### 1.6 Implementation Status

**Since 2026-11-01** the checks are the three of section 1.7, in `my_app/services/safety_gate.py`; the routes in `schema_pipeline_routes.py` call them. The list below is the status of 2025-11-26.

**Current (v2.3 - 2025-11-26 with Stage 2 Refactoring):**
- ✅ Stage 1-3 logic in `schema_pipeline_routes.py` - CORRECT
- ✅ PipelineExecutor is DUMB engine - CORRECT
- ✅ Non-redundant safety rules - IMPLEMENTED
- ✅ Recursive Pipeline System - IMPLEMENTED
- ✅ Multi-Output Support - IMPLEMENTED
- ✅ LivePipelineRecorder as single source of truth - IMPLEMENTED
- ✅ stage4_only feature for fast regeneration - FIXED
- ✅ Stage 2 split into 2-phase execution - IMPLEMENTED
- ✅ execution_mode parameter REMOVED - REFACTORED
- ✅ Centralized model selection via config.py - IMPLEMENTED
- ✅ Stage 2 functions SEPARATED (Interception & Optimization isolated) - CRITICAL FIX
  - ✅ `execute_stage2_interception()` - Pure pedagogical transformation
  - ✅ `execute_optimization()` - Pure model-specific refinement (isolation prevents context leakage)
  - ✅ `execute_stage2_with_optimization()` - Deprecated proxy (backward compatible)

**Validation Tests:**
- ✅ Stillepost (8 iterations): Stage 1 ran once (not 8x) - PASSED
- ✅ Image Comparison (2 outputs): Stage 1 ran once (not 2x) - PASSED
- ✅ Simple config (dada): Stage 1-4 all ran once - PASSED
- ✅ Logs confirm clean execution (no redundancy) - PASSED
- ✅ media_type UnboundLocalError fixed - PASSED

**Architecture Proven Correct:**
- DevServer = Smart Orchestrator ✅
- PipelineExecutor = Dumb Engine ✅
- Non-Redundant Safety Rules ✅
- Scalable to Complex Flows ✅
- LivePipelineRecorder = Single Source of Truth ✅

**See:**
- `docs/DEVELOPMENT_DECISIONS.md` for design rationale
- `schema_pipeline_routes.py` for orchestration code
- `pipeline_executor.py` for execution engine

### 1.7 Safety: The Three Checks

**Since 2026-11-01.** Every check sits at one of three places, and each place is one function in `devserver/my_app/services/safety_gate.py`. The routes call them; no pipeline config names a check.

| Place | Function | Reads | kids, youth | adult |
|---|---|---|---|---|
| **Intake** (Stage 1) | `check_intake()`, `check_intake_texts()` | every new piece of the user's material, once: typed text, uploaded pictures and documents | names of living private individuals and addresses with a house number; uploaded pictures: the level's picture question | names and addresses |
| **Before the model** (Stage 3) | `check_before_model()` | everything a media model receives, after the last step a language model takes | the §86a lists of every language over the original and the English version, then the safety classifier with the level's question, after a list hit also the symbol question; a picture handed to the model needs a verdict | the same, with the question for adult; pictures are not checked |
| **At the result** | `check_result_image()`, `check_result_text()`, `check_result_code()` | a picture before it leaves the server, a text a language model wrote before it is shown, code before it runs in a browser | pictures: the level's picture question; texts: the §86a lists of every language, then the level's text question, after a list hit also the symbol question; code: the same, and a list of constructs dangerous in a browser, after a hit the code question | texts and code, with the question for adult, code without that list; pictures are not checked |

**The chats** (Together, Contesting, the Help and the platform voice; since 2026-11-08) check what goes in. Their intake checks names and addresses and runs the §86a lists of every language, with the symbol question after a list hit (`check_intake(kind="chat")`); the level's text question is not asked. It covers the message, the page state, the context's texts, the notes on the board, the names of the media on the page and every line of the history. What their model writes leaves unchecked, piece by piece as it is written. Their system message closes with an instruction that names the safety level and carries the classifier's criteria for that level (`level_instruction`, read from `safety_classifier.LEVEL_INSTRUCTS`), at kids, youth and adult; research gets none. The tolerances of the less strict levels, which the result check asks as well, are left out because they contradict the stricter measure. Their restrictions stand in the stricter one, two of adult's only by category, so kids and youth are also told the adult measure's list of symbols and its rule for a text that depicts a Nazi crime. The instruction names itself the measure of every reply and says that the platform's checks judge what is passed to a generator. At kids and youth the reasoning a model delivers apart from its reply is not sent, and a reply that is only the reasoning counts as none; reasoning written into the reply text (`<think>`) is not removed. It stands after the page state, the page's entries and the listing of the surface. A picture sent as data passes the image intake. A chat's reply counts as no new material only where it comes back in a chat's history (`remember_chat_reply`). What a chat model reads from storage (a run's texts, a run's stored conversation, a favourite's note, a remembered note, Together's journal, a kept strategy) reaches it at kids and youth only where the level it was written at opens there (`safety_gate.run_opens_at`), and an upload only with its pass for the level. The history route, the journal route and the favourites' list show a stored line, a journal event and a note by the same rule, and a favourite brought to Together's board reaches the model by it (`_brought_at`). What a chat model reads of something stored is input as well: the context of the run a chat is opened on, `view_run`, `lookup_shared_favorites`, `view_favorite` and the strategy store (`canvas_graph_library`). At kids and youth they hand it nothing of a run made at a less strict level or at none, by the rule the favourites' restore asks (`safety_gate.run_opens_at`); canvas runs record their level, and the strategy store keeps the least strict level any of a strategy's texts was written at. A tool runs only when the turn offered it. The comparisons of the Latent Lab run on the same chat turn, get no instruction, no tools and no thinking, and keep the result check on their whole answer.

At research no check runs and no model is asked. The file check of an upload is not one of these checks and runs at every level. A PDF uploaded to the knowledge library also goes through three lists, the §86a list among them, and there a hit alone rejects the document (`upload_gate.py`).

**Rules for all three:**
- The level is resolved once per request, on the request thread, and handed to every check.
- A check that gets no answer blocks. The block says that a check could not be carried out, never that the material was rated.
- A pass is remembered per material and level while the process runs. A pass at a looser level does not answer for a stricter one.
- The safety prefix before a language model checks nothing. Where the model answers with the refusal the prefix asks for (`is_safety_refusal()`), the route reports a block.

**The block message.** Every block answer carries `safety_block`:

```json
{
  "checkpoint": "intake | before_model | result | refusal",
  "field": "the request field, where it is known",
  "reason_key": "personal_data | content | symbol | image_content | code | unavailable | refusal | ...",
  "reason": "the sentence the platform has shown for it"
}
```

A request carries it in the answer's body, most routes with the status 403; a stream sends it in a `blocked` event. The frontend picks its sentence by `reason_key` (`safetyBlockMessageKey()` in `useGenerationStream.ts`).

**Delivery.** At kids and youth a recorded picture is delivered only with a verdict that answers for the level (`pipeline_recorder.py`).

---

## 2. Model Selection Architecture

**⭐ AUTHORITATIVE SECTION - Centralized model configuration**

**Version:** 1.0 (2025-11-23 - execution_mode removal)

### 2.1 Executive Summary

**DEPRECATED Architecture (before the execution_mode removal):**
- execution_mode parameter ('eco', 'fast', 'local', 'remote') passed in API calls
- Model selection logic scattered across backend/frontend
- Hardcoded values in multiple locations
- Code duplication and inconsistency

**NEW Architecture:**
- **execution_mode parameter COMPLETELY REMOVED**
- All models configured CENTRALLY in `devserver/config.py`
- NO hardcoded model names in Vue components or API routes
- Single source of truth for model selection

### 2.2 Centralized Model Configuration

**Location:** `<repo>/devserver/config.py`

**Model Constants:**
```python
# Stage-specific model assignments
STAGE1_TEXT_MODEL = "..."                        # Translation of a written prompt
STAGE2_INTERCEPTION_MODEL = "mistral-nemo"       # Pedagogical transformation
STAGE3_MODEL = "..."                             # Translation for the media model
SAFETY_MODEL = "..."                             # The safety classifier every check asks
# ... etc
```

**Why This Pattern:**
- ✅ Change models in ONE location (config.py)
- ✅ NO hardcoded values in application code
- ✅ Consistent model usage across all flows
- ✅ Easy to switch between local/cloud models
- ✅ Follows "NO WORKAROUNDS" principle

### 2.3 Migration Summary

**Removed from API Calls:**
- `/pipeline/stage2` endpoint: No longer accepts execution_mode
- Frontend (text_transformation.vue): Removed execution_mode from 3 API calls
- Backend routes: Model selection via config.py constants ONLY

**Chunk Configuration:**
- OLD: `"model": "mistral-nemo"` (hardcoded)
- NEW: `"model": "STAGE2_INTERCEPTION_MODEL"` (references config.py)

**Example: manipulate.json**
```json
{
  "chunk_name": "manipulate",
  "model": "STAGE2_INTERCEPTION_MODEL",
  "meta": {
    "task_type": "standard"
  }
}
```

### 2.4 Future Model Switching

**To change models system-wide:**
1. Edit `devserver/config.py`
2. Change constant value (e.g., `STAGE2_INTERCEPTION_MODEL = "claude-3.5-haiku"`)
3. NO code changes required in routes, Vue components, or chunks
4. Restart devserver

**To switch between local/cloud:**
- Update config.py constants to point to cloud models
- Ensure API keys configured in environment
- NO architectural changes required

### 2.5 Architectural Principles

This refactoring follows the project's core principles:
- ❌ **NO prefix hacks** - Model names not prefixed with "00-" for load order
- ❌ **NO temporary fixes** - execution_mode removed, not "improved"
- ✅ **Fix root problems** - Centralized configuration eliminates duplication
- ✅ **Clean, maintainable code** - Single source of truth in config.py


---

## 3. Phase 4: Intelligent Seed Logic

**Added:** 2025-11-28 - Iterative image correction workflow

### 3.1 Purpose

Enable two distinct workflows:
- **Iterative correction**: User changes prompt → wants to refine SAME image (keep seed)
- **Re-generation**: User re-runs unchanged prompt → wants DIFFERENT image (new seed)

### 3.2 Logic

**Per-Device State** (`schema_pipeline_routes.py:83-85`):
```python
_seed_state_lock = threading.Lock()
_seed_state: dict = {}   # device_id → {"prompt", "seed", "output_config", "ts"}
_SEED_STATE_TTL = 3600   # entries expire after 1 hour
```
Keyed by `device_id` and guarded by a lock, so parallel workshop clients do not
share a seed. (Originally two module globals — see 3.8.)

**Decision Flow** (Before Stage 3, After Stage 2):
```python
if stage2_prompt != state["prompt"] or output_config != state["output_config"]:
    # Prompt OR model CHANGED → keep seed (compare the effect of the change)
    seed = state["seed"] or 123456789   # First run = standard seed
else:
    # Prompt AND model UNCHANGED → new random seed (variation)
    seed = random.randint(0, 2147483647)

if seed_override is not None:   # explicit user seed always wins
    seed = seed_override
```
The output config is part of the comparison: switching model at an unchanged
prompt keeps the seed, so the two models are compared on the same noise.

### 3.3 Timing in 4-Stage Flow

```
Stage 1: Intake ✅
  ↓
Stage 2: Interception ✅
  ↓
🎯 PHASE 4: SEED DECISION (HERE!)
  - Compare: stage2_prompt vs _last_prompt
  - Decide: reuse / new / first-run seed
  ↓
Stage 3: Translation + the check before the model ✅
  ↓
Stage 4: Media Generation (with calculated seed) ✅
```

**Why after Stage 2?** Captures pedagogical transformation (the meaningful prompt)
**Why before Stage 3?** Translation doesn't change semantic intent

### 3.4 Example Workflow

```
1. "cat" → First run → seed 123456789 → Image A
2. "cat" → Unchanged → seed 789456 → Image B (different)
3. "green cat" → Changed → seed 789456 → Image B + green (iterate)
```

### 3.5 Propagation Chain

1. **DevServer** (`schema_pipeline_routes.py:1712, 5924`): `seed_override=calculated_seed`
2. **PipelineExecutor** (`pipeline_executor.py:119`): Parameter added
3. **Context** (`pipeline_executor.py:179`): `custom_placeholders['seed_override']`
4. **Chunks** (`pipeline_executor.py:586`): `parameters['seed']` (lowercase!)

**Step 4 is unconditional and lives in exactly one place.** It applies to every
chunk regardless of backend; a backend with no use for a seed ignores the
parameter. Do not narrow it by `backend_type` — see 3.9.

**The receiving end is part of the contract.** A Python chunk must declare
`seed` in its `execute()` signature. Every Python chunk ends its signature with
`**kwargs`, so an undeclared `seed` is swallowed without error and the chunk
falls back to its own `random.randint()` — the failure is silent. Guarded by
`devserver/tests/test_python_chunk_seed_policy.py`.

### 3.6 Design Decisions

**Backend-only state** (not frontend):
- ✅ Simplicity (no frontend complexity)
- ✅ Single source of truth
- ❌ Resets on server restart (acceptable - rare)

**Standard seed 123456789**:
- Reproducible research baseline
- Consistent first-run behavior
- Enables comparative studies

**Comparison point = Stage 2 output**:
- Captures pedagogical transformation
- Pre-translation (language-agnostic intent)

### 3.7 Code Locations

- `schema_pipeline_routes.py:83-103` - Per-device state, TTL, lock
- `schema_pipeline_routes.py:1596-1620` - Decision logic (stage3-4 endpoint)
- `schema_pipeline_routes.py:5707-5731` - Decision logic (unified endpoint)
- `pipeline_executor.py:119, 179, 586` - Propagation
- `devserver/tests/test_python_chunk_seed_policy.py` - Chunk-side policy guard

### 3.8 Known Limitations

- State lost on server restart (acceptable — rare)
- Language switches trigger false "prompt changed"
- ~~Single-user only (not thread-safe)~~ — resolved: state is per `device_id`
  under a lock, entries expire after 1 hour

### 3.9 Regression: the seed that reached nothing (2026-02-05 - 2026-08-03)

Step 4 carried an exception for `backend_type == 'python'`, added in `94b93a85`
for HeartMuLa. On the day it was written it was narrow — HeartMuLa was the only
Python chunk in the repo. It was never revisited, and it did not need to change
to do damage: `5d5daf3f` (2026-03-01) migrated six Diffusers JSON chunks to
Python chunks, moving SD3.5, FLUX.2, Surrealizer, Attention Cartography and
Feature Probing under an exception written for music. Every chunk born as a
Python chunk afterwards inherited it.

For six months the seed set in the UI reached none of them; each generated at
its own `random.randint()`. Nothing was reproducible and no A/B comparison of
two parameter settings was valid. Fixed in `2148e9b7` by restoring step 4 as
specified here.

**The lesson is in the cut, not the bug.** The exception was scoped by
*execution path* (`backend_type`), which is not a stable property — chunks move
between paths. The population under the exception grew while the exception
itself stood still. Scope conditions on this chain by capability, or not at all.

---

## 4. SSE Streaming for Stage-by-Stage Progress

**Added:** 2026-01-30 - Real-time UI updates during generation

### 4.1 Purpose

Enable frontend to show stage-specific badges (Safety Approved, Translated) at the **correct time** - after Stage 3 completes, before Stage 4 begins.

**Previous Problem:**
- Badges appeared after entire generation completed (too late)
- Safety badge used fake 300ms delay (not accurate)
- No real-time feedback during Stage 3 (Translation + Safety)

**Solution:**
- SSE (Server-Sent Events) streaming mode for `/generation` endpoint
- Backend emits events at stage boundaries
- Frontend shows badges when `stage3_complete` event arrives

### 4.2 SSE Event Flow

```
Frontend                          Backend (/generation)
   │                                   │
   │─────── GET ?enable_streaming=true ────────>│
   │                                   │
   │<────── event: connected ──────────│
   │        {run_id, output_config}    │
   │                                   │
   │<────── event: stage3_start ───────│
   │                                   │
   │        [Stage 3: Translation + Safety Check]
   │                                   │
   │<────── event: stage3_complete ────│
   │        {safe: true,               │
   │         was_translated: true}     │
   │        ↓                          │
   │   [SHOW BADGES NOW!]              │
   │                                   │
   │<────── event: stage4_start ───────│
   │        ↓                          │
   │   [START PROGRESS ANIMATION]      │
   │                                   │
   │        [Stage 4: Media Generation]
   │                                   │
   │<────── event: complete ───────────│
   │        {media_output, run_id,     │
   │         loras, was_translated}    │
   │                                   │
```

### 4.3 Backend Implementation

**Location:** `schema_pipeline_routes.py`

**Generator Function:**
```python
def execute_generation_streaming(data: dict):
    """SSE-Generator für Stage 3+4"""

    # Stage 3: Translation + the check before the model
    yield generate_sse_event('stage3_start', {...})

    verdict = check_before_model({'prompt': translated_prompt}, level=safety_level,
                                 originals={'prompt': prompt})
    was_translated = translated_prompt != prompt

    if not verdict.passed:
        yield generate_sse_event('blocked', {'reason': verdict.reason,
                                             'safety_block': verdict.block(), ...})
        return

    yield generate_sse_event('stage3_complete', {
        'safe': True,
        'was_translated': was_translated,
        'checks_passed': [...]
    })

    # Stage 4: Generation
    yield generate_sse_event('stage4_start', {})

    result = await execute_stage4_generation_only(...)

    yield generate_sse_event('complete', {
        'media_output': result['media_output'],
        'run_id': result['run_id'],
        'loras': result.get('loras', [])
    })
```

**Endpoint Modification:**
```python
@schema_bp.route('/pipeline/generation', methods=['POST', 'GET'])
def generation_endpoint():
    # Support GET for EventSource
    if request.method == 'GET':
        data = {param: request.args.get(param) for param in PARAMS}

    # Streaming mode
    if data.get('enable_streaming'):
        return Response(
            stream_with_context(execute_generation_streaming(data)),
            mimetype='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
        )

    # Non-streaming fallback (original behavior)
    ...
```

### 4.4 Frontend Implementation

**Shared Composable:** `useGenerationStream.ts`

```typescript
export function useGenerationStream() {
  const showSafetyApprovedStamp = ref(false)
  const showTranslatedStamp = ref(false)
  const generationProgress = ref(0)
  const currentStage = ref<'idle' | 'stage3' | 'stage4' | 'complete'>('idle')

  async function executeWithStreaming(params): Promise<GenerationResult> {
    const eventSource = new EventSource(buildSSEUrl(params))

    eventSource.addEventListener('stage3_complete', (e) => {
      const data = JSON.parse(e.data)
      showSafetyApprovedStamp.value = data.safe
      showTranslatedStamp.value = data.was_translated
    })

    eventSource.addEventListener('stage4_start', () => {
      // Start progress animation here
    })

    // ... complete, blocked, error handlers
  }

  return { showSafetyApprovedStamp, showTranslatedStamp, ... }
}
```

**Views Using Composable:**
- `text_transformation.vue`
- `image_transformation.vue`
- `multi_image_transformation.vue`

### 4.5 Stage Separation Summary

| Stage | Function | Endpoint | SSE Event |
|-------|----------|----------|-----------|
| Stage 1 | The intake: names of private individuals, addresses; at kids/youth uploaded pictures | `/interception` | `blocked` where it refuses, nothing where it passes |
| Stage 2 | Prompt Interception; its text goes through the check at the result before it is shown | `/interception` | `stage_start/complete (stage: 2)` |
| Stage 3 | Translation + the check before the model | `/generation` | `stage3_start/complete` |
| Stage 4 | Media Generation | `/generation` | `stage4_start/complete` |
| Post-4 | The check at the result: the run's pictures (kids/youth only) | `/generation` | `blocked` (`safety_block.checkpoint`: `result`) |

**Endpoint Bundling (by design):**
- `/interception` = Stage 1 + Stage 2 (input processing)
- `/generation` = Stage 3 + Stage 4 + the picture check after generation (output generation)

**Clean Internal Separation:**
- `check_intake()`, `check_intake_texts()` - Stage 1
- `execute_pipeline()` (via PipelineExecutor) - Stage 2; its text through `check_result_text()`
- `check_before_model()` - Stage 3
- `execute_stage4_generation_only()` - Stage 4
- `check_result_image()` - the pictures after Stage 4

#### The Picture Check After Generation

The checks before generation (the intake, the check before the model) read the **prompt**, but cannot predict what the image generator actually produces. A harmless prompt can generate disturbing content. The check at the result closes this gap:

```
Stage 4 complete (picture saved to disk)
  ↓
safety_level in ('kids', 'youth') and the run recorded a picture?
  ↓ no  → COMPLETE (no picture check at adult and research)
  ↓ yes
check_result_image() for every picture of the run:
  - the safety classifier is asked the level's picture question
  - the verdict is written onto the recorded picture, with its level
  ↓ passed     → SSE 'complete' (normal flow)
  ↓ refused    → SSE 'blocked' (checkpoint 'result', reason_key 'image_content')
  ↓ no verdict → SSE 'blocked' (checkpoint 'result', reason_key 'unavailable')
```

**Key design decisions:**
- **No verdict is a block**: a check that gave no answer stops the run and is said as a check that could not be carried out, never as a rating of the picture
- **kids/youth only**: adult and research skip the check
- **Every picture the run recorded**: the preview a 3D run stores as a picture included; sound and video as a whole are not checked at the result
- **Delivery**: a recorded picture without a verdict that answers for the level is not delivered
- **Complements, not replaces**: the intake and the check before the model stay as the checks before generation

### 4.6 Design Decisions

**Why SSE instead of Split Requests?**
- ✅ Single connection, no race conditions
- ✅ If connection drops, everything stops cleanly
- ✅ No state synchronization issues between two requests
- ❌ Split would risk: Stage 3 succeeds, network drops, no Stage 4

**Why Shared Composable?**
- ✅ DRY: Same SSE logic for all 3 views
- ✅ Consistent badge behavior
- ✅ Single place to modify streaming logic

**Why "→ EN" instead of Flag Icon?**
- ✅ Neutral, no political connotation
- ✅ Clear meaning: "translated to English"
- ❌ 🇬🇧 flag was problematic (colonialism, UK-centrism)

---

**Document Version:** 2.4
**Last Updated:** 2026-01-30
**Status:** v2.2.0-alpha - 2-Phase Stage 2 + Centralized Models + Phase 4 Seeds + SSE Streaming
