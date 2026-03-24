# Architecture: Stage 2 Separation & Prompt Interception

**Session 76 - Critical Architectural Insights**

> This document captures the core architectural principles learned when implementing the Stage 2 Optimization separation. These insights prevent common mistakes when working with Prompt Interception and the two-phase Stage 2 flow.

---

## Table of Contents

1. [Two Separate Endpoints for Two Separate Operations](#1-two-separate-endpoints-for-two-separate-operations)
2. [Prompt Interception MUST Use the manipulate Chunk](#2-prompt-interception-must-use-the-manipulate-chunk)
3. [optimization_instruction Placement](#3-optimization_instruction-placement-in-prompt-interception)
4. [Frontend Should Make Clear, Direct API Calls](#4-frontend-should-make-clear-direct-api-calls)
5. [No Workarounds - Use the Modularität](#5-no-workarounds---use-the-modularität)
6. [Info Bubbles and User Feedback](#6-info-bubbles-and-user-feedback)

---

## 1. Two Separate Endpoints for Two Separate Operations

### ❌ Wrong Approach: Single Endpoint with Complex Logic

**Initial mistake:** We tried to use a single `/execute_stage2` endpoint with a `skip_execution` flag to handle both interception and optimization.

```python
# BAD: One endpoint tries to do two different things
@app.route('/pipeline/stage2')
def execute_stage2():
    skip_execution = data.get('skip_execution', False)
    if skip_execution:
        # Do optimization only
        ...
    else:
        # Do interception + optimization
        ...
```

**Problem:** Backend must "guess" what the user wants based on flags. This is fragile and confusing.

### ✅ Correct Architecture: Two Clear Endpoints

```python
# GOOD: Two endpoints for two operations
@app.route('/pipeline/stage2')          # Call 1: Interception
def execute_stage2():
    # ONLY: Interception with config.context
    ...

@app.route('/pipeline/optimize')        # Call 2: Optimization
def optimize_prompt():
    # ONLY: Optimization with optimization_instruction
    ...
```

### Principle: URL Communicates Intent

| User Action | Endpoint | Purpose |
|-------------|----------|---------|
| Clicks "Start" Button | `/pipeline/stage2` | Interception with config.context |
| Selects Model | `/pipeline/optimize` | Optimization with optimization_instruction |

**Why this matters:**
- No flags or complex decision logic needed
- Each endpoint has ONE clear responsibility
- Frontend explicitly says what it wants
- Easy to understand and maintain

---

## 2. Prompt Interception MUST Use the manipulate Chunk

### ❌ Wrong Approach: Direct LLM Call

```python
# BAD: Manual prompt building
full_prompt = (
    f"Task:\nTransform the INPUT according to the rules provided by the CONTEXT.\n\n"
    f"Context:\n{optimization_instruction}\n\n"
    f"Prompt:\n{input_text}"
)

# Direct backend call bypasses Prompt Interception architecture
response = await backend_router.process_request(backend_request)
```

**Problem:** Bypasses the manipulate chunk and Prompt Interception structure. Results are poor because the LLM doesn't understand the structure correctly.

### ✅ Correct Approach: Use PromptInterceptionEngine

```python
# GOOD: Use PromptInterceptionEngine with proper structure
from schemas.engine.prompt_interception_engine import (
    PromptInterceptionEngine,
    PromptInterceptionRequest
)

interception_engine = PromptInterceptionEngine()

request = PromptInterceptionRequest(
    input_prompt=input_text,                    # INPUT_TEXT (Prompt)
    input_context=optimization_instruction,     # CONTEXT (USER_RULES)
    style_prompt="Transform the INPUT according to the rules provided by the CONTEXT. Preserve structural aspects of the INPUT and follow all instructions in the CONTEXT precisely.",  # TASK_INSTRUCTION
    model=STAGE2_INTERCEPTION_MODEL
)

response = await interception_engine.process_request(request)
optimized_text = response.output_str
```

### The manipulate Chunk Template

The manipulate chunk (`/devserver/schemas/chunks/manipulate.json`) provides the correct 3-part structure:

```
Task:
{{TASK_INSTRUCTION}}

Context:
{{CONTEXT}}

Important: Respond in the same language as the input prompt below.

Prompt:
{{INPUT_TEXT}}
```

**Why this matters:**
- The 3-part structure is proven to work for Prompt Interception
- PromptInterceptionEngine handles model selection, fallbacks, and error handling
- Direct LLM calls produce inferior results

---

## 3. optimization_instruction Placement in Prompt Interception

### Critical Understanding: The 3-Part Structure

```
TASK_INSTRUCTION  →  Generic instruction (HOW to transform)
CONTEXT (USER_RULES) →  Specific transformation rules (WHAT to do)
INPUT_TEXT        →  The text to transform
```

### ❌ Common Mistakes

**Mistake 1:** Putting optimization_instruction in TASK_INSTRUCTION
```python
# BAD
style_prompt=optimization_instruction  # Wrong place!
input_context=""
```

**Mistake 2:** Concatenating optimization_instruction with input
```python
# BAD
input_prompt=f"{input_text}\n\n{optimization_instruction}"
```

### ✅ Correct Placement

```python
# GOOD
request = PromptInterceptionRequest(
    input_prompt=input_text,                # INPUT_TEXT
    input_context=optimization_instruction, # CONTEXT (USER_RULES) ← Correct!
    style_prompt="Transform the INPUT according to the rules provided by the CONTEXT.",  # TASK_INSTRUCTION
    model=STAGE2_INTERCEPTION_MODEL
)
```

### Why CONTEXT is Correct

- **CONTEXT (USER_RULES):** This is where specific transformation rules belong
- **TASK_INSTRUCTION:** Generic instruction that applies to all transformations
- **INPUT_TEXT:** The actual content to transform

**From user feedback:**
> "NEINNEINNEINNEIN der INPUT Prompt wird vom CONTEXT bearbeitet. Das nennt sich INTERCEPTION... CONTEXT verändert... IST DAS SO SCHWER ZU VERSTEHEN?"

---

## 4. Frontend Should Make Clear, Direct API Calls

### ❌ Wrong: Frontend Sends Everything, Backend Decides

```javascript
// BAD: Backend must guess intent
const response = await axios.post('/api/schema/pipeline/stage2', {
  schema: selectedSchema,
  context_prompt: contextPrompt,
  output_config: selectedModel,  // Mixed concerns!
  // Backend must figure out: "Do I do interception? Optimization? Both?"
})
```

### ✅ Right: Frontend Explicitly States Intent

```javascript
// GOOD: "Start" button → Interception
async function runInterception() {
  const response = await axios.post('/api/schema/pipeline/stage2', {
    schema: pipelineStore.selectedConfig?.id,
    input_text: inputText.value,
    context_prompt: contextPrompt.value,
    // NO output_config - this is pure interception
  })
}

// GOOD: Model selection → Optimization
async function runOptimization() {
  const response = await axios.post('/api/schema/pipeline/optimize', {
    input_text: interceptionResult.value,  // Text from interception_result box
    output_config: selectedConfig.value    // Selected model
    // NO schema, NO context_prompt - only optimization!
  })
}
```

### Principle: Frontend is a "Possibility Canvas"

**From user feedback:**
> "Das Frontend ist ein Möglichkeits-Canvas, an dem ich jederzeit an fast jeder Stelle fast alles tun kann was ich will, ohne von irgendwelchen eingebrannten Prozesslogiken behelligt zu werden."

**Translation to architecture:**
- User clicks "Start" → Clear action: Call `/stage2` for interception
- User clicks Model → Clear action: Call `/optimize` for optimization
- No complex orchestration logic in backend
- Each user interaction maps to ONE specific endpoint

---

## 5. No Workarounds - Use the Modularität

### ❌ Wrong: Band-Aid Fixes

**Example from this session:**
```python
# BAD: Adding flags to control behavior
skip_execution = data.get('skip_execution', False)
if skip_execution:
    # Workaround: Skip some logic
    ...
```

**Problem:** Obscures the modular design. Creates technical debt.

### ✅ Right: Leverage Modular Architecture

**From user frustration:**
> "Ich kann - als Mensch - wirklich nicht verstehen wieso Start1 nicht einfach eine Aktion auslösen kann die sich auf die zwei Boxen VOR/OBERHALB von Start 1 beziehen, und der Klick auf das Modell eine Aktion auslösen kann, die sich auf die Box DIREKT DARÜBER bezieht."

**The solution:**
- Start 1 → Uses boxes above it → `/stage2` endpoint
- Model click → Uses box above it → `/optimize` endpoint
- No flags, no complex logic, no workarounds

**System design principle:**
> "WOZU habe ich das ganze Schemadevserver-System denn so modular ausgelegt? Für Flexibilität"

**Use the modularity:**
- Separate endpoints for separate operations
- Separate chunks for separate transformations
- Separate configs for separate media types

---

## 6. Info Bubbles and User Feedback

### ❌ Wrong: Notifications for Normal Behavior

```vue
<!-- BAD: Showing info for normal system behavior -->
<div v-if="!hasOptimization && selectedConfig">
  <p>{{ selectedConfig }} benötigt keine Prompt-Optimierung...</p>
</div>
```

**Problem:** If `optimization_instruction` is missing from an output chunk, the system simply passes the input through. This is **normal behavior**, not an error or exceptional case.

### ✅ Right: Only Notify for Actionable Issues

**From user feedback:**
> "Es gibt KEIN Szenario in dem die von Dir eingefügte Warnbox Sinn ergibt."

**Principle:**
- Missing `optimization_instruction` → Normal: Just return input text
- LLM timeout → Error: Show user notification
- Invalid input → Error: Show user notification

**Don't warn about:**
- System working as designed
- Different code paths being taken
- Optional features not being used

---

## 7. UI_MODE Length Limits: Interception Only (Session 285)

### Principle: Limits Belong to the Interception Path, Not the Engine

UI_MODE-based length limits (word guidance + max_tokens safety cap) are enforced by `BackendRouter`, not by `PromptInterceptionEngine`. The engine is a pure LLM router.

```
Interception:  ChunkBuilder → BackendRouter (applies limits) → Engine → LLM
Optimization:  execute_optimization() → Engine → LLM  (no limits)
```

**Why:** Interception output is student-facing (readability matters). Optimization output is machine-consumed (Stage 4 needs full token budget, e.g. 4096 for p5.js code).

**Limits (applied in BackendRouter only):**
| UI_MODE | Word guidance | max_tokens cap |
|---------|--------------|----------------|
| kids    | 80 words     | 400 tokens     |
| youth   | 150 words    | 600 tokens     |
| expert  | 250 words    | 800 tokens     |

---

## File References

These principles apply to:

### Backend
- `/devserver/my_app/routes/schema_pipeline_routes.py`
  - `execute_optimization()` — calls engine directly (no UI_MODE limits)
  - `/pipeline/stage2` endpoint — interception via BackendRouter (with limits)
  - `/pipeline/optimize` endpoint

### Frontend
- `/public/ai4artsed-frontend/src/views/text_transformation.vue`
  - `runInterception()` - calls `/stage2`
  - `runOptimization()` - calls `/optimize`
  - `selectConfig()` - triggers optimization on model selection

### Schema Engine
- `/devserver/schemas/chunks/manipulate.json` - Prompt Interception template
- `/devserver/schemas/engine/prompt_interception_engine.py` - LLM routing engine (exports `UI_MODE_WORD_LIMITS`, `UI_MODE_MAX_TOKENS_SAFETY`)
- `/devserver/schemas/engine/backend_router.py` - Applies UI_MODE limits in interception path
- `/devserver/schemas/chunks/output_image_sd35_large.json` - Example with `optimization_instruction` in meta

---

## Related Documentation

- [ARCHITECTURE PART 01 - 4-Stage Orchestration Flow](./ARCHITECTURE%20PART%2001%20-%204-Stage%20Orchestration%20Flow.md) - Overall system flow
- [ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities](./ARCHITECTURE%20PART%2020%20-%20Stage2-Pipeline-Capabilities.md) - Stage 2 design philosophy
- [DEVELOPMENT_DECISIONS.md](./DEVELOPMENT_DECISIONS.md) - Session 76 decision entry
- [DEVELOPMENT_LOG.md](../DEVELOPMENT_LOG.md) - Session 76 timeline

---

**Last Updated:** Session 76 - Stage 2 Optimization Separation
