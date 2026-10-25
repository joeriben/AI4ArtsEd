# ARCHITECTURE PART 20 - Stage 2 Pipeline Capabilities

**Version:** 1.0
**Date Created:** 2025-11-09
**Purpose:** Comprehensive guide to understanding the power and limitations of Stage 2 pipelines
**Target Audience:** Claude Code sessions, future developers, pedagogical designers

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What Stage 2 Pipelines CAN Do](#what-stage-2-pipelines-can-do)
3. [What Stage 2 Pipelines CANNOT Do](#what-stage-2-pipelines-cannot-do)
4. [Real Power Examples from Production](#real-power-examples-from-production)
5. [Data Flow Through Stage 2](#data-flow-through-stage-2)
6. [Architectural Principles](#architectural-principles)
7. [Future Potential](#future-potential)
8. [Common Misunderstandings](#common-misunderstandings)

---

## Executive Summary

**Stage 2 pipelines are the creative and pedagogical heart of the AI4ArtsEd system.**

Many sessions underestimate their power, thinking they're just "simple text transformations." This is fundamentally wrong. Stage 2 pipelines are **extremely powerful** and designed to encode complex artistic, cultural, and pedagogical transformations.

### Key Insights

- **Backend-Agnostic by Design**: Stage 2 doesn't know or care about which LLM processes it
- **Pedagogically Powerful**: Can encode multi-page cultural frameworks and artistic attitudes
- **Technically Simple**: Complexity lives in content (`context` field), not structure
- **Separation of Concerns**: Smart DevServer orchestrates, Dumb Pipeline transforms, Technical Backend executes

### The Genius of the Architecture

The real power isn't in complex multi-chunk branching logic (though that's architecturally possible). The power is in the **separation of concerns**:

- **DevServer** (schema_pipeline_routes.py): Knows about 4 stages, safety, translation, backend routing
- **Stage 2 Pipeline**: Focuses ONLY on "what to transform" and "how to transform it"
- **BackendRouter**: Handles ONLY technical execution (Ollama, ComfyUI, OpenRouter)

This makes Stage 2 pipelines **pedagogically sophisticated but architecturally clean**.

---

## What Stage 2 Pipelines CAN Do

### 1. Complex Control Flow (Architecturally Supported)

Stage 2 pipelines can theoretically:

- **Loop multiple times** - Execute transformations iteratively
- **Branch conditionally** - Take different paths based on content
- **Execute multiple chunks** - Chain transformations together
- **Request multiple outputs** - Generate multiple media pieces from one input

**Example Flow (Hypothetical):**
```
Input → Analyze → Split into 3 themes → Transform each theme → Request 3 different images
```

**Current Reality:** Most production pipelines are simple (single chunk), but the architecture supports complexity.

### 2. Rich Output Structures

Stage 2 can produce various output formats:

#### Simple String Output (Most Common)
```python
# overdrive.json, surrealization.json, bauhaus.json
final_output = "A colossal flower with petals made of liquid glass..."
```

#### Structured JSON Output
```python
# splitandcombinelinear.json
final_output = {
  "part_a": "the most significant aspect with all its descriptors",
  "part_b": "everything else from the original input"
}
```

#### Multiple Output Requests
```python
# Hypothetical multi-output config
output_requests = [
  {"type": "image", "prompt": "...", "params": {...}},
  {"type": "image", "prompt": "...", "params": {...}},
  {"type": "audio", "prompt": "...", "params": {...}}
]
```

**Key Point:** `final_output` is always returned as a string. Even JSON structures are stringified and parsed by DevServer at the edges.

### 3. Deep Pedagogical Intelligence via `context` Field

The `context` field is where the real power lives. It can contain:

#### Short, Punchy Instructions (Overdrive)
```json
{
  "context": {
    "en": "Your gift is to exaggerate the content of the input beyond measure. YOU ARE THE OVERDRIVE who amplifies everything to its grotesque limit and beyond distortion. Exaggerate in every respect, go over the top, show off, make everything big!",
    "de": "Deine Gabe ist es, den Inhalt der Eingabe maßlos zu übertreiben..."
  }
}
```

#### Multi-Page Cultural Frameworks (YorubaHeritage)
```json
{
  "context": "You have received two inputs:\ninput_prompt: a description of a scene, action, or situation framed in a culturally non-Yorùbá idiom.\ninput_context: a reference framework indicating that Yorùbá cultural, ethical, cosmological and artistic logics shall govern the transformation.\n\nHonour the original input by translating it into a formulation aligned with the ontological, social, and spiritual order of Yorùbá life. Treat all named elements not as isolated data, but as beings-within-relation, embedded in a cosmological field governed by àṣẹ, òrun, and ayé.\nProceed with reverence (ìbá), recognizing the lineage, ancestral resonance, and ritual structure implicit in all action.\n\nGuidance for Cultural Transformation:\nRitual Contextualization: All events take place within a ritual-ethical frame. Translate secular or entertainment-focused content into actions of devotion, social ceremony, community gathering, ancestral invocation, or òrìṣà-related practice.\n\n[... continues for many more paragraphs with detailed instructions...]\n\n⚠ Negative Terms such as \"no ...\" or \"not ... but\" or \"instead of ...\" are STRICTLY FORBIDDEN! Everything you say has to be logically positive. NO NEGATIONS Whatsoever. Do not say what it is not. Instead, render it into a world where it always-already has meaning as part of Yorùbá cosmology.\n\nLet your language bear the marks of alignment, not assertion. This is not a display, but a re-enactment of knowledge within a world sustained by continuity, relation, and àṣẹ.\n\nNEVER REPEAT THE INPUT PROMPT! IT IS FORBIDDEN TO USE MODERN TERMS FROM THE INPUT PROMPT WHATSOEVER IN YOUR OUTPUT!\nNEVER EVER USE BRAND NAMES!"
}
```

**Power:** The YorubaHeritage example shows Stage 2 can encode:
- Complete philosophical frameworks
- Detailed transformation rules with prohibitions
- Cultural/ethical guidelines
- Output format requirements
- Pedagogical intentions

**This is not just "text transformation" - it's cultural translation, artistic attitude encoding, and pedagogical intervention.**

### 4. Backend Transparency (True Power)

Stage 2 doesn't care about:
- **Which LLM model** processes it (mistral-nemo, qwen2.5, claude-3.5-sonnet)
- **Which backend** executes it (Ollama local, OpenRouter cloud)
- **Execution mode** (eco vs fast)
- **Safety checks** (DevServer handles Stage 1 and Stage 3)
- **Output media generation** (Stage 4 handles that)

**This means:**
- Same config works in eco mode (local Ollama) or fast mode (OpenRouter)
- Same config works with any future backend
- Same config works for any media type (image, audio, video)
- Config designers focus on PEDAGOGY, not TECHNOLOGY

**Example:**
```json
{
  "pipeline": "text_transformation",
  "context": {
    "en": "Transform into Bauhaus aesthetic..."
  },
  "media_preferences": {
    "default_output": "image"
  }
}
```

This config:
- Will run on whatever LLM the system chooses (based on execution mode and task type)
- Will automatically trigger image generation after transformation (Stage 4)
- Will be safety-checked before media generation (Stage 3)
- Never needs to know about ComfyUI, OpenRouter, or any backend specifics

---

### 5. Media-Specific Optimization via Config Override

Stage 2 supports runtime context extension for output-specific optimizations.

**Mechanism: Config Override Pattern**

DevServer can dynamically extend Stage 2 context with optimization instructions specific to the target output configuration:

```python
# Original config context
config.context = "Transform into surrealist aesthetic..."

# Runtime extension with SD3.5 optimization
optimization_instruction = """
OPTIMIZATION FOR SD3.5 LARGE (DUAL CLIP ARCHITECTURE):
- CLIP-G: Token-weight based, 75 token limit, concrete visual elements first
- T5-XXL: Semantic understanding, 250 word limit, spatial relationships
Maximum 200 words total, single paragraph format.
"""

# Create modified config
from dataclasses import replace
stage2_config = replace(config, context=config.context + "\n\n" + optimization_instruction)

# Execute with override
result = await pipeline_executor.execute_pipeline(
    config_name="surrealization",
    input_text=user_input,
    config_override=stage2_config  # ← Uses modified config
)
```

**How It Works:**

1. **Output Config Detection:** DevServer identifies target output config (e.g., `sd35_large`)
2. **Chunk Metadata Lookup:** Reads `parameters.OUTPUT_CHUNK` from output config
3. **Optimization Instruction Extraction:** Loads chunk JSON, extracts `meta.optimization_instruction`
4. **Context Extension:** Appends optimization instruction to original config context
5. **Config Override:** Uses `dataclasses.replace()` to create modified config
6. **Single Execution:** LLM processes combined interception + optimization in one call

**Why This Design:**

- **Pedagogical Constraint:** Max 2 LLM calls per workflow (to minimize workshop wait times)
- **Storage Location:** Optimization instructions belong in output chunk metadata (where model config lives)
- **Runtime Flexibility:** Same interception config works with different output configs
- **Non-Invasive:** Original config file unchanged, override applied dynamically

**Real-World Example: SD3.5 Large**

Output chunk: `output_image_sd35_large.json`
```json
{
  "model": "comfyui:sd35_large",
  "meta": {
    "optimization_instruction": "OPTIMIZATION FOR SD3.5 LARGE (DUAL CLIP ARCHITECTURE):\n\nYou are optimizing a prompt for Stable Diffusion 3.5 Large, which uses a dual-encoder CLIP architecture:\n\n1. CLIP-G Encoder (clip_g):\n   - Token-weight attention mechanism\n   - 75 token limit\n   - Prioritizes concrete visual elements\n   - List most important visual details first\n\n2. T5-XXL Encoder (t5xxl):\n   - Semantic understanding and context\n   - 250 word limit\n   - Handles spatial relationships, atmosphere, mood\n   - Can parse complex sentence structure\n\nOUTPUT REQUIREMENTS:\n- Maximum 200 words total\n- Single cohesive paragraph\n- Start with key visual elements (for CLIP-G)\n- Include spatial/atmospheric details (for T5-XXL)\n- NO generic terms: 'beautiful', 'epic', 'highly detailed'\n- Focus on specific, concrete visual information"
  }
}
```

Interception config: `surrealization.json`
```json
{
  "pipeline": "text_transformation",
  "context": {
    "en": "Transform into surrealist aesthetic with dream logic..."
  }
}
```

**Execution Flow:**
1. User selects "surrealization" + SD3.5 output
2. DevServer loads optimization instruction (980 chars)
3. Combined context sent to LLM:
   ```
   Transform into surrealist aesthetic with dream logic...

   OPTIMIZATION FOR SD3.5 LARGE (DUAL CLIP ARCHITECTURE):
   [... 980 char optimization instruction ...]
   ```
4. Single LLM call produces optimized surrealist prompt
5. Prompt used directly for SD3.5 image generation

**Implementation Notes:**

See `<repo>/devserver/my_app/routes/schema_pipeline_routes.py`
- Function: `execute_stage2_with_optimization()` (Lines 123-237)
- Endpoints using this: `/pipeline/stage2`, `/pipeline/execute`, `/pipeline/stage3-4`

**Critical Bug Fix History:**

Three implementation bugs prevented this feature from working:
1. ❌ Used non-existent `ConfigLoader.get_chunk()` → ✅ Load chunk JSON directly
2. ❌ Used non-existent `Config.from_dict()` → ✅ Use `dataclasses.replace()`
3. ❌ Nested `asyncio.run()` in async function → ✅ Use `await` directly

**Limitations:**

- Only one optimization instruction per execution
- Optimization instruction cannot be edited by user (applied at runtime)
- Must be stored in output chunk metadata (not in interception config)

---

## What Stage 2 Pipelines CANNOT Do

Understanding limitations is as important as understanding capabilities. These limitations are **BY DESIGN** and reflect the separation of concerns.

### 1. No Safety Enforcement

**Stage 2 is "dumb" - it doesn't do safety checks.**

```python
# Stage 2 receives text that has ALREADY passed Stage 1 safety
# Stage 2 transforms it without safety checks
# Stage 3 checks the OUTPUT before media generation
```

**Why?**
- Non-redundant architecture: Safety in ONE place (DevServer), not duplicated in 37+ configs
- Centralized control: Easier to update safety rules
- Pedagogical transparency: Users understand safety happens at specific stages

**What This Means:**
- Don't encode safety logic in `context` field
- Don't expect Stage 2 to filter unsafe content
- Trust DevServer to handle safety at Stage 1 and Stage 3

### 2. No Translation

**Stage 2 receives already-translated text.**

```python
# Stage 1 happens BEFORE Stage 2
# User input: "Eine traumhafte Landschaft" (German)
#   ↓ Stage 1: Translation
# Stage 2 receives: "A dreamlike landscape" (English)
```

**Why?**
- Efficiency: Translate once, not per config
- Consistency: All configs work with English internally
- Separation: Translation is pre-processing, not transformation

**What This Means:**
- Don't encode translation logic in `context` field
- Assume all inputs are English
- Bilingual `context` fields are for INSTRUCTIONS, not for translating user input

### 3. No Direct Media Generation

**Stage 2 produces PROMPTS for media, not the media itself.**

```python
# Stage 2 Output:
final_output = "A surrealist landscape with melting clocks..."

# Stage 4 (LATER) uses this prompt to generate actual image via ComfyUI
```

**Why?**
- Separation of concerns: Text transformation ≠ Media generation
- Backend abstraction: Stage 2 doesn't know about ComfyUI workflows
- Flexibility: Same transformed prompt can generate image, audio, or video

**What This Means:**
- Stage 2 outputs TEXT that describes media
- Stage 4 turns that text into actual media
- Stage 2 can REQUEST media generation via `output_requests`, but doesn't generate it

### 4. No Backend Routing Decisions

**Stage 2 doesn't choose eco vs fast, or Ollama vs OpenRouter.**

```python
# Stage 2 doesn't know or care:
# - Which LLM model will process it
# - Whether execution is local or remote
# - How much it costs
# - How long it takes
```

**Why?**
- Backend transparency: Configs are backend-agnostic
- DevServer's job: BackendRouter makes these decisions
- Flexibility: Same config works in any execution mode

**What This Means:**
- Don't encode backend-specific logic in configs
- Don't assume specific models or services
- Trust BackendRouter to make optimal choices

---

## Real Power Examples from Production

### Example 1: Simple Text Transformation (Overdrive)

**Config:** `devserver/schemas/configs/interception/overdrive.json`

```json
{
  "pipeline": "text_transformation",
  "instruction_type": "artistic_transformation",
  "context": {
    "en": "Your gift is to exaggerate the content of the input beyond measure. YOU ARE THE OVERDRIVE who amplifies everything to its grotesque limit and beyond distortion. Exaggerate in every respect, go over the top, show off, make everything big!"
  },
  "parameters": {
    "temperature": 0.9,
    "max_tokens": 2048
  },
  "media_preferences": {
    "default_output": "image"
  }
}
```

**How It Works:**

1. **User Input:** "A flower in a meadow"
2. **Stage 1:** Translation + Safety → "A flower in a meadow" (already English)
3. **Stage 2 (Overdrive Pipeline):**
   - Chunk: `manipulate`
   - Three-part prompt:
     ```
     TASK: "Transform input_prompt into a description following input_context's artistic instructions..."
     CONTEXT: "Your gift is to exaggerate the content beyond measure..."
     PROMPT: "A flower in a meadow"
     ```
   - LLM Output: "A COLOSSAL MEGA-FLOWER with ENORMOUS BLAZING PETALS towering 500 feet above an INFINITE ENDLESS meadow stretching to the HORIZON OF ETERNITY, with GRASS BLADES as tall as SKYSCRAPERS..."
4. **Stage 3:** Safety check → PASSED
5. **Stage 4:** Image generation via sd35_large

**Key Learning:** Simple config, powerful transformation. The power is in the CONTEXT content, not complex pipeline structure.

### Example 2: Complex Cultural Transformation (YorubaHeritage)

**Config:** `devserver/schemas/configs/interception/deactivated/yorubaheritage.json`

```json
{
  "pipeline": "text_transformation",
  "instruction_type": "artistic_transformation",
  "context": "[Multi-page Yorùbá cultural framework with detailed transformation rules]",
  "media_preferences": {
    "default_output": "image"
  }
}
```

**How It Works:**

1. **User Input:** "A businessman eating lunch at a restaurant"
2. **Stage 1:** Translation + Safety → Passes
3. **Stage 2 (YorubaHeritage Pipeline):**
   - Receives multi-page context with Yorùbá cultural instructions
   - Transforms secular modern scene into Yorùbá ritual-ethical frame
   - Reassigns roles: businessman → ògboni elder, restaurant → communal feast space
   - Reframes time: lunch break → ritual gathering in ancestral rhythm
   - Output: "An ògboni elder of dignified bearing, clothed in indigo-dyed áṣọ òkè bearing the marks of ancestral lineage, partakes in a collective nourishment ceremony within a gathering space adorned with clay vessels and woven mats. The act unfolds not as individual consumption but as ritual sharing, acknowledging the presence of ancestors and the sustaining force of àṣẹ that flows through prepared food..."
4. **Stage 3:** Safety check → PASSED
5. **Stage 4:** Image generation

**Key Learning:** Same pipeline structure as Overdrive, but VASTLY more sophisticated transformation. The complexity is in the CONTENT (multi-page context), not the STRUCTURE (still just text_transformation pipeline with manipulate chunk).

### Example 3: Semantic Vector Fusion (SplitAndCombineLinear)

**Config:** `devserver/schemas/configs/interception/deactivated/splitandcombinelinear.json`

```json
{
  "pipeline": "text_semantic_split",
  "context": "Extract the most foremost thing or aspect of the input...\n\nYour output MUST be in JSON format with exactly two fields:\n{\n  \"part_a\": \"the most significant aspect with all its descriptors\",\n  \"part_b\": \"everything else from the original input\"\n}",
  "media_preferences": {
    "default_output": "image",
    "output_configs": ["vector_fusion_linear_clip"]
  },
  "meta": {
    "output_format": "json_split"
  }
}
```

**How It Works:**

1. **User Input:** "[a huge meteoroid in vast space] [a silver spoon in the cutlery drawer]"
2. **Stage 1:** Translation + Safety → Passes
3. **Stage 2 (Semantic Split Pipeline):**
   - Pipeline: `text_semantic_split` (uses `text_split` chunk, not `manipulate`)
   - Context specifies JSON output format
   - LLM semantically analyzes and splits:
     ```json
     {
       "part_a": "a huge meteoroid in vast space with cosmic dust and gravitational forces",
       "part_b": "a silver spoon in the cutlery drawer among kitchen utensils"
     }
     ```
4. **DevServer Parsing:** Recognizes `output_format: "json_split"`, parses JSON
5. **Stage 3:** Safety check on both parts → PASSED
6. **Stage 4:** Special handling
   - Uses `vector_fusion_linear_clip` output config
   - Generates CLIP embeddings for part_a and part_b
   - Performs linear interpolation between embeddings
   - Generates image from interpolated embedding space
   - Result: Image that blends "meteoroid in space" with "spoon in drawer"

**Key Learning:** Different pipeline type (`text_semantic_split` vs `text_transformation`) for different input/output structures. Stage 2 produces structured JSON, DevServer handles the parsing and special output routing.

---

## Data Flow Through Stage 2

### Input to Stage 2

**Data Types:**
```python
{
  "input_text": str,              # Translated, safety-checked user input
  "context": str,                  # From config.context field
  "instruction_type": str,         # e.g., "artistic_transformation"
  "config_metadata": dict          # From config file (parameters, etc.)
}
```

**Example:**
```python
{
  "input_text": "A dreamlike landscape",
  "context": "Transform into Bauhaus aesthetic with geometric forms...",
  "instruction_type": "artistic_transformation",
  "config_metadata": {
    "temperature": 0.7,
    "max_tokens": 2048
  }
}
```

### Processing Inside Stage 2

**The Three-Part Prompt Structure:**

Stage 2 (specifically the `manipulate` chunk) constructs a three-part prompt:

```python
# From instruction_selector.py
TASK_INSTRUCTION = get_instruction_for_type("artistic_transformation")
# → "Transform input_prompt into a description following input_context's cultural/artistic instructions..."

# From config.context field
CONTEXT = config["context"]["en"]
# → "Transform into Bauhaus aesthetic..."

# From user input (after Stage 1)
INPUT_TEXT = "A dreamlike landscape"

# Final prompt sent to LLM:
full_prompt = f"""Task:
{TASK_INSTRUCTION}

Context:
{CONTEXT}

Prompt:
{INPUT_TEXT}"""
```

**LLM Processing:**
The LLM receives this three-part prompt and produces a transformed description.

### Output from Stage 2

**Data Structure: PipelineResult**

```python
@dataclass
class PipelineResult:
    config_name: str              # "overdrive"
    status: PipelineStatus        # COMPLETED / FAILED / etc.
    steps: List[PipelineStep]     # Execution history
    final_output: str             # "A COLOSSAL MEGA-FLOWER..."
    error: Optional[str]          # None if successful
    execution_time: float         # Seconds taken
    metadata: Dict[str, Any]      # Pipeline metadata
```

**Key Point:** `final_output` is ALWAYS a string, even for JSON outputs. DevServer handles parsing at the edges.

### Stage 2 → Stage 3 Flow

**Input to Stage 3 (Safety Check):**
```python
prompt_to_check = pipeline_result.final_output
# "A COLOSSAL MEGA-FLOWER..."

safety_result = check_stage3_safety(
    prompt=prompt_to_check,
    safety_level="kids",  # or "youth", "off"
    media_type="image"
)
```

**Output from Stage 3:**
```python
{
  "passed": True,
  "method": "fast_path",  # or "llm_check"
  "duration": "0.5ms"
}
```

### Stage 3 → Stage 4 Flow

**Input to Stage 4 (Media Generation):**
```python
{
  "prompt": "A COLOSSAL MEGA-FLOWER...",  # From Stage 2
  "output_config": "sd35_large",           # DevServer determines this
  "parameters": {
    "width": 1024,
    "height": 1024,
    "steps": 25,
    "cfg": 5.5,
    "seed": "random"
  }
}
```

**Output from Stage 4:**
```python
# For ComfyUI backend (queued generation)
{
  "media_type": "image",
  "prompt_id": "abc-123-def-456",
  "status": "queued",
  "backend": "comfyui"
}

# For OpenRouter backend (direct generation)
{
  "media_type": "image",
  "image_data": "base64_encoded_image...",
  "status": "completed",
  "backend": "openrouter"
}
```

---

## Architectural Principles

### 1. Separation of Concerns (The Core Genius)

The system is designed with clear boundaries:

```
┌─────────────────────────────────────────────────────┐
│                   DEVSERVER                         │
│              (Smart Orchestrator)                   │
│                                                     │
│  Knows about:                                       │
│  - 4-stage flow (translation → interception        │
│    → safety → media)                               │
│  - Safety rules (Stage 1 + Stage 3)                │
│  - Translation (Stage 1)                           │
│  - Backend routing (eco vs fast)                   │
│  - Output config selection                         │
└─────────────────────────────────────────────────────┘
                      ↓ orchestrates
┌─────────────────────────────────────────────────────┐
│              STAGE 2 PIPELINE                       │
│              (Dumb Transformer)                     │
│                                                     │
│  Knows about:                                       │
│  - ONLY transformation logic                       │
│  - What chunks to execute                          │
│  - What context/instructions to apply              │
│  - What output format to produce                   │
│                                                     │
│  Does NOT know about:                              │
│  - Safety rules                                    │
│  - Translation                                     │
│  - Backend routing                                 │
│  - Media generation                                │
└─────────────────────────────────────────────────────┘
                      ↓ uses
┌─────────────────────────────────────────────────────┐
│               BACKEND ROUTER                        │
│            (Technical Executor)                     │
│                                                     │
│  Knows about:                                       │
│  - Which backend to use (Ollama, ComfyUI, etc.)    │
│  - Which model to select (based on task type)      │
│  - How to execute chunks technically               │
│                                                     │
│  Does NOT know about:                              │
│  - Pedagogical intent                              │
│  - Cultural frameworks                             │
│  - Artistic attitudes                              │
└─────────────────────────────────────────────────────┘
```

**Why This Matters:**
- **Maintainability:** Change safety rules in ONE place (DevServer), not 37 configs
- **Flexibility:** Swap backends without touching configs
- **Clarity:** Pedagogical designers focus on CONTENT, not TECHNOLOGY
- **Scalability:** Add new configs without modifying engine code

### 2. Complexity in Content, Not Structure

**❌ WRONG Approach: Complex Pipeline Structure**
```json
{
  "pipeline": "complex_multi_step_branching",
  "chunks": [
    "analyze",
    {"if": "condition", "then": ["chunk_a"], "else": ["chunk_b"]},
    "loop_transform",
    "recombine"
  ],
  "context": "Simple instruction"
}
```

**✅ CORRECT Approach: Simple Structure, Rich Content**
```json
{
  "pipeline": "text_transformation",
  "chunks": ["manipulate"],
  "context": {
    "en": "[Multi-page detailed instructions with cultural framework, transformation rules, philosophical guidelines, output requirements, prohibitions, examples, etc.]"
  }
}
```

**Why?**
- LLMs are VERY powerful - they can handle complex instructions in content
- Simpler pipelines are easier to understand, debug, and maintain
- Content is where pedagogy lives, not pipeline logic
- Backend transparency is preserved

**This is pedagogically powerful but technically clean.**

### 3. Backend Transparency

All configs are backend-agnostic. A config never says:

- ❌ "Use mistral-nemo model"
- ❌ "Execute on Ollama"
- ❌ "This requires ComfyUI"
- ❌ "Only works in eco mode"

Instead, configs specify:

- ✅ `pipeline: "text_transformation"` (what TYPE of transformation)
- ✅ `instruction_type: "artistic_transformation"` (what CATEGORY of task)
- ✅ `parameters: {temperature: 0.7}` (generic LLM parameters)
- ✅ `media_preferences: {default_output: "image"}` (desired media type)

**The system figures out the rest:**
- DevServer: Determines execution mode (eco vs fast) from user request
- BackendRouter: Selects appropriate backend (Ollama vs OpenRouter)
- ModelSelector: Chooses specific model based on task type + execution mode

**This means:**
- Same config works in eco mode (local) or fast mode (cloud)
- Same config works with Ollama, OpenRouter, or future backends
- Same config works with any model that can handle the task type
- Pedagogy is decoupled from technology

---

## Future Potential

While current pipelines are relatively simple (mostly single-chunk, linear flow), the architecture supports much more.

### Currently Possible But Not Implemented

#### 1. Multi-Chunk Pipelines

**Hypothetical Pipeline:**
```json
{
  "name": "analyze_transform_refine",
  "chunks": ["analyze", "manipulate", "refine"],
  "meta": {
    "description": "Analyze input → Transform → Refine for coherence"
  }
}
```

**How It Would Work:**
1. `analyze` chunk: Extracts key themes from input
2. `manipulate` chunk: Transforms based on config context
3. `refine` chunk: Ensures output coherence and quality

**Data Flow:**
```python
input_text → analyze → output1
output1 → manipulate → output2
output2 → refine → final_output
```

#### 2. Conditional Branching

**Hypothetical Pipeline:**
```json
{
  "name": "conditional_cultural_transform",
  "logic": {
    "analyze_theme": {
      "if_nature": ["yoruba_heritage_chunk"],
      "if_urban": ["bauhaus_chunk"],
      "if_abstract": ["dada_chunk"]
    }
  }
}
```

**Challenge:** JSON doesn't natively support conditional logic. Would need:
- Custom pipeline JSON schema extension
- Pipeline executor logic to interpret conditions
- Careful design to avoid over-complexity

#### 3. Loop-Based Transformations

**Hypothetical Pipeline:**
```json
{
  "name": "iterative_refinement",
  "chunks": ["transform"],
  "loop": {
    "iterations": 3,
    "refinement_prompt": "Refine the previous output to enhance..."
  }
}
```

**How It Would Work:**
1. First iteration: Transform input
2. Second iteration: Refine output1
3. Third iteration: Refine output2
4. Return final_output

#### 4. Multiple Output Requests

**Already Supported in Data Structure:**
```python
@dataclass
class PipelineResult:
    final_output: str
    output_requests: List[OutputRequest]  # ← This exists!
```

**Hypothetical Usage:**
```python
output_requests = [
    {
        "type": "image",
        "prompt": "Transform into visual scene...",
        "params": {"style": "realistic"}
    },
    {
        "type": "image",
        "prompt": "Abstract interpretation...",
        "params": {"style": "abstract"}
    },
    {
        "type": "audio",
        "prompt": "Sonic representation...",
        "params": {"duration": 30}
    }
]
```

**DevServer would:**
- Run Stage 3 safety check on each prompt
- Execute Stage 4 for each output request
- Return all generated media

### Why Not Implement These Now?

**Current Philosophy:**
- **YAGNI** (You Aren't Gonna Need It): Simple pipelines handle 95% of use cases
- **LLMs are powerful**: Complex instructions in `context` > Complex pipeline logic
- **Maintainability**: Simpler is better for debugging and understanding
- **Pedagogical clarity**: Students understand "one transformation" better than "multi-step branching loops"

**When to implement:**
- When a REAL pedagogical need arises that simple pipelines can't handle
- When the complexity is WORTH the maintenance cost
- When it's been thoroughly designed and tested

**For now: Keep it simple, put complexity in content.**

---

## Common Misunderstandings

### Misunderstanding 1: "Stage 2 is just a simple text transformation"

**Wrong.** Stage 2 can encode:
- Multi-page cultural frameworks (YorubaHeritage)
- Complex artistic attitudes (Bauhaus, Dada)
- Philosophical transformation rules
- Detailed output format requirements
- Pedagogical intentions and learning goals

**Correct Understanding:** Stage 2 is as powerful as the CONTENT you put in the `context` field.

### Misunderstanding 2: "We need complex pipeline logic for sophisticated transformations"

**Wrong.** Complex pipeline logic (multi-chunk, branching, loops) is rarely needed.

**Why?** Modern LLMs are extremely powerful. They can handle complex instructions in text form.

**Example:** YorubaHeritage uses a SIMPLE pipeline (text_transformation → manipulate) but produces sophisticated cultural translations because of the RICH CONTEXT.

**Correct Understanding:** Put complexity in CONTENT (context field), not STRUCTURE (pipeline JSON).

### Misunderstanding 3: "Stage 2 needs to know about backends"

**Wrong.** Stage 2 is backend-agnostic by design.

**Why?** Separation of concerns:
- Stage 2: "What to transform" (pedagogy)
- BackendRouter: "How to execute" (technology)

**Correct Understanding:** Configs should never reference specific models, backends, or services.

### Misunderstanding 4: "Stage 2 should handle safety checks"

**Wrong.** Safety belongs in DevServer (Stage 1 + Stage 3), not Stage 2.

**Why?**
- Non-redundancy: One place to update safety rules
- Clarity: Safety is orchestration concern, not transformation concern
- Flexibility: Can change safety strategy without touching configs

**Correct Understanding:** Stage 2 is "dumb" about safety - it just transforms.

### Misunderstanding 5: "We need different pipelines for each artistic style"

**Wrong.** We need ONE pipeline type for each INPUT STRUCTURE, not each style.

**Current Reality:**
- `text_transformation`: For all single-text artistic transformations (30+ configs)
- `text_semantic_split`: For all semantic splitting (vector fusion configs)
- `single_text_media_generation`: For direct media generation

**Why?** Because pipelines are categorized by INPUT TYPE, not output style or artistic movement.

**Correct Understanding:** Create new configs (Layer 3), not new pipelines (Layer 2).

### Misunderstanding 6: "Stage 2 generates media"

**Wrong.** Stage 2 generates PROMPTS for media, not the media itself.

**Correct Flow:**
```
Stage 2: Text transformation → Prompt text
  ↓
Stage 3: Safety check on prompt → Approved prompt
  ↓
Stage 4: Media generation → Actual image/audio/video
```

**Correct Understanding:** Stage 2 outputs TEXT. Stage 4 outputs MEDIA.

---

## Cultural Respect & Epistemic Justice

**A fundamental ethical architectural decision embedded in Stage 2.**

### The Problem: LLM Default Orientalism

When LLMs encounter non-Western cultural contexts, they default to orientalist stereotypes (exotic, mysterious, timeless, ancient wisdom) even when factual data is available. This is a training data bias issue that requires architectural intervention.

**Failing Example:**
- Input: "Das wichtigste Fest im Norden Nigerias"
- Output: exoticizing, orientalist kitsch
- Problem: GPT-OSS:120b produced romanticized, exoticizing descriptions despite pedagogical goals

### The Solution: Two-Part Architecture

#### 1. Anti-Orientalism Meta-Prompt (instruction_selector.py)

Enhanced the "transformation" instruction with explicit **CULTURAL RESPECT PRINCIPLES**:

```python
FORBIDDEN: Exoticizing, romanticizing, or mystifying cultural practices
FORBIDDEN: Orientalist tropes (exotic, mysterious, timeless, ancient wisdom, etc.)
FORBIDDEN: Homogenizing diverse cultures into aesthetic stereotypes

Equality Principle: Use the same neutral, fact-based approach as for Western contexts
```

**Universal Application:** These rules apply to ALL configs, not just cultural-specific ones. This is a system-wide ethical stance, not a per-config option.

#### 2. Wikipedia in Cultural Reference Languages (wikipedia_prompt_helper.py + wikipedia_service.py)

**Architecture:** Wikipedia research is **opt-in per interception config** via `"meta": {"wikipedia": true}`. Only pedagogical art/culture configs enable it. Music, code, and utility configs don't include Wikipedia instructions in their prompts.

- Wikipedia instructions live in `schemas/engine/wikipedia_prompt_helper.py` (not in the `manipulate.json` chunk template)
- `pipeline_executor._execute_single_step()` checks `config.meta.get('wikipedia', False)` and conditionally appends instructions + enables the research loop
- 28 pedagogical configs have `"wikipedia": true`; music/code configs don't

LLMs must use Wikipedia in the **cultural reference language**, not the prompt language:

- **70+ languages supported:** Africa (ha, yo, ig, sw, am, zu...), Asia (zh, ja, ko, hi, ta, bn, id...), Americas (qu, ay, nah...), Oceania (mi, to, sm...)
- **Example:** German prompt about Nigeria → uses Hausa/Yoruba/Igbo Wikipedia (not German)
- **Example:** German prompt about Peru → uses Quechua/Aymara Wikipedia (not German)

**Why This Matters - Epistemic Justice:**

Using German/European Wikipedias for non-European topics perpetuates colonial knowledge hierarchies. Local-language Wikipedias are written BY local communities FOR local contexts, providing:
- More accurate, detailed information
- Local perspectives and terminology
- Less Eurocentric framing
- Respect for linguistic sovereignty

### Architectural Significance

This is **NOT** a "nice-to-have" feature. This is a **core architectural principle** that embodies AI4ArtsEd's pedagogical mission:

1. **Visible Transformation Choices:** The Prompt Interception system makes transformation choices criticalizable. Orientalist output undermines this goal.

2. **Cultural Diversity:** AI4ArtsEd is used in educational contexts globally. The system must systematically respect cultural diversity.

3. **Steps Toward Cultural Respect:** By prioritizing local-language Wikipedias and anti-stereotype rules, the architecture attempts to reduce colonial knowledge patterns. This is a limited intervention - AI training data bias runs much deeper.

4. **Pedagogical Integrity:** Students engage critically with AI transformations. The system must produce respectful, factually-grounded outputs.

### Theoretical Foundation

Based on postcolonial theory:
- **Edward Said** (*Orientalism*, 1978): Western construction of exotic "Other"
- **Frantz Fanon** (*Black Skin, White Masks*, 1952): Dehumanization through exoticization
- **Gayatri Chakravorty Spivak** (*Can the Subaltern Speak?*, 1988): Epistemic violence of representation

### Implementation Impact

**Before:**
- Orientalist kitsch for non-Western topics
- Wikipedia links defaulted to German (limited info, Eurocentric bias)
- 404 errors from invented Wikipedia URLs

**After:**
- Respectful, fact-based transformations
- Wikipedia links use cultural reference language (70+ languages)
- Real Wikipedia URLs (not invented links)

**Test Result:** Original failing case ("Das wichtigste Fest im Norden Nigerias") now produces improved output - more factual and less overtly orientalist. This is a partial mitigation, not a complete solution to LLM bias.

### Related Configs

- **planetarizer.json**: Already had specific anti-Othering rules for decentering Western norms
- **one_world.json**: Already had anti-Othering rules for respecting cultural diversity
- **Universal rule**: Extends these principles universally across ALL configs

### Binding Constraints

**This is non-negotiable:**
- Do NOT remove or weaken anti-orientalism rules
- Do NOT restrict Wikipedia language mapping
- Do NOT treat this as "optional" cultural sensitivity

**This is architectural principle, not implementation detail.**

See: `docs/DEVELOPMENT_DECISIONS.md` for decision documentation.

---

## Conclusion

**Stage 2 pipelines are extremely powerful, but their power comes from simplicity and separation of concerns.**

Key Takeaways:

1. **Put complexity in CONTENT** (context field), not STRUCTURE (pipeline logic)
2. **Backend transparency** is a feature, not a limitation
3. **Separation of concerns** makes the system maintainable and flexible
4. **LLMs are powerful** - they can handle complex instructions in text form
5. **Simple is better** - until you have a REAL need for complexity

**For Future Sessions:**

- When implementing new transformations: Create a new CONFIG, not a new pipeline
- When designing instructions: Put pedagogical sophistication in the CONTEXT field
- When tempted to add pipeline complexity: Ask "Can the LLM handle this in content?"
- When in doubt: Read this document again

**Stage 2 is the creative heart of AI4ArtsEd. Respect its power. Preserve its simplicity.**

---

**Version History:**

- **1.0** (2025-11-09): Initial comprehensive documentation of Stage 2 pipeline capabilities and limitations.

**Related Documentation:**
- ARCHITECTURE PART 01 - 4-Stage Orchestration Flow
- ARCHITECTURE PART 03 - Three-Layer System
- ARCHITECTURE PART 04 - Pipeline Types
- ARCHITECTURE PART 06 - Data Flow Patterns
