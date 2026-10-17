# Architecture: Stage 2 Separation & Prompt Interception

**Critical Architectural Insights**

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

**The rule:** The CONTEXT processes the INPUT prompt. That is what Prompt Interception is: the CONTEXT changes the input.

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

**The rule:** The frontend is a canvas of possibilities. At almost any point the user can do almost anything, and no burnt-in process logic gets in the way.

**Translation to architecture:**
- User clicks "Start" → Clear action: Call `/stage2` for interception
- User clicks Model → Clear action: Call `/optimize` for optimization
- No complex orchestration logic in backend
- Each user interaction maps to ONE specific endpoint

---

## 5. No Workarounds - Use the Modularität

### ❌ Wrong: Band-Aid Fixes

**Example:**
```python
# BAD: Adding flags to control behavior
skip_execution = data.get('skip_execution', False)
if skip_execution:
    # Workaround: Skip some logic
    ...
```

**Problem:** Obscures the modular design. Creates technical debt.

### ✅ Right: Leverage Modular Architecture

**The requirement:** Start 1 triggers one action that refers to the two boxes above it, and the click on the model triggers one action that refers to the box directly above it.

**The solution:**
- Start 1 → Uses boxes above it → `/stage2` endpoint
- Model click → Uses box above it → `/optimize` endpoint
- No flags, no complex logic, no workarounds

**System design principle:** The schema DevServer system is modular for the sake of flexibility.

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

**The rule:** There is no scenario in which a warning box for a missing `optimization_instruction` is meaningful.

**Principle:**
- Missing `optimization_instruction` → Normal: Just return input text
- LLM timeout → Error: Show user notification
- Invalid input → Error: Show user notification

**Don't warn about:**
- System working as designed
- Different code paths being taken
- Optional features not being used

---

## 7. Die Lesemenge: ein Satz im Prompt, keine Grenze im Transport

Bis 2026-08-05 schnitt `BackendRouter` die Antwort einer Interception an einer
UI_MODE-abhaengigen `max_tokens`-Grenze ab (kids 400, youth 600, expert 800
Token). Das ist entfernt und darf nicht zurueckkehren: harte Ausgabe-Obergrenzen
sind auf dieser Plattform ohne Ausnahme verboten, weil sie
mitten im Satz abschneiden. `UI_MODE_WORD_LIMITS` und `UI_MODE_MAX_TOKENS_SAFETY`
gibt es nicht mehr.

Die Laenge steht seitdem als Satz im Prompt:
`instruction_selector.get_reading_volume_clause()`, angehaengt von
`chunk_builder.build_chunk()` und nur dort — und nur an einen Baustein, dessen
Config `meta.stage == 'interception'` fuehrt und deren Pipeline nicht schleift.

```
Interception:  ChunkBuilder (haengt die Klausel an) → BackendRouter → Engine → LLM
Adaption:      execute_optimization() → Engine → LLM  (ohne Klausel)
```

**Warum nur dort:** Was die Interception schreibt, liest ein Mensch. Was die
Adaption schreibt, liest ein Encoder. Eine Uebersetzung wird nicht gekuerzt, und
eine Sicherheitspruefung liest niemand.

| UI_MODE | Klausel (Stand 2026-09-07) |
|---------|----------------------------|
| easy (alt: kids)   | at most 100 words |
| medium (alt: youth)| at most 200 words |
| expert             | at most 300 words |

Ein Wert ausserhalb dieser drei laesst die Klausel still entfallen.

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
- `/devserver/schemas/engine/prompt_interception_engine.py` - LLM routing engine
- `/devserver/schemas/engine/backend_router.py` - reiner Transport; die entfernten UI_MODE-Grenzen sassen hier
- `/devserver/schemas/engine/instruction_selector.py` - `READING_VOLUME_WORDS` und die Klausel
- `/devserver/schemas/chunks/output_image_sd35_large.json` - Example with `optimization_instruction` in meta

---

## Related Documentation

- [ARCHITECTURE PART 01 - 4-Stage Orchestration Flow](./ARCHITECTURE%20PART%2001%20-%204-Stage%20Orchestration%20Flow.md) - Overall system flow
- [ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities](./ARCHITECTURE%20PART%2020%20-%20Stage2-Pipeline-Capabilities.md) - Stage 2 design philosophy
- [DEVELOPMENT_DECISIONS.md](./DEVELOPMENT_DECISIONS.md) - Stage 2 separation decision entry

---

**Last Updated:** Stage 2 Optimization Separation
