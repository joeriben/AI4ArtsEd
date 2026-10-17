# Architecture Violation: PromptInterceptionEngine.build_full_prompt()

**Status:** DOCUMENTED - Refactoring planned for future session
**Documented:** 2026-01-24
**Priority:** MEDIUM (system works, but architecture is violated)

---

## Summary

The 3-layer architecture (Pipelines → Configs → Chunks) is bypassed at 7 locations where code directly instantiates `PromptInterceptionEngine` and manually builds prompts instead of using the `ChunkBuilder` pipeline.

---

## Architecture Comparison

### Should Be (Correct Architecture):
```
Config (context: "...")
  ↓
Pipeline (instruction_type: "artistic_transformation")
  ↓
ChunkBuilder.build_chunk()
  - Loads manipulate.json template
  - Calls instruction_selector.get_instruction()
  - Replaces {{TASK_INSTRUCTION}}, {{CONTEXT}}, {{INPUT_TEXT}}
  ↓
BackendRouter.route()
  ↓
PromptInterceptionEngine (ONLY Backend-Proxy!)
  ↓
Ollama/OpenRouter API
```

### Currently Is (Architecture Violation):
```
Code instantiates PromptInterceptionEngine directly
  ↓
Manually builds PromptInterceptionRequest
  ↓
PromptInterceptionEngine.build_full_prompt()  ← VIOLATION!
  - Builds 3-part structure itself
  - Ignores ChunkBuilder
  - Uses own format (Instruction/Input/Context)
  ↓
API Call
```

---

## Format Mismatch

| Component | Format |
|-----------|--------|
| `manipulate.json` (Correct) | `Task:` → `Context:` → `Important:...` → `Prompt:` |
| `build_full_prompt()` (Violation) | `Instruction:` → `Input:` → `Context:` |

### Key Differences:
1. **Labels**: "Task" vs "Instruction", "Prompt" vs "Input"
2. **Order**: Chunk has Context BEFORE Prompt, Engine has Input BEFORE Context
3. **Language hint**: Chunk has "Important: Respond in same language...", Engine has different formatting rules

### manipulate.json Template:
```
Task:
{{TASK_INSTRUCTION}}

Context:
{{CONTEXT}}

Important: Respond in the same language as the input prompt below.

Prompt:
{{INPUT_TEXT}}
```

### build_full_prompt() Output:
```
Instruction:
{task_instruction}

{FORMATTING_RULES}

Input:
{input_prompt}

Context:
{style_prompt}
```

---

## 7 Violation Locations

| File | Line | Function | Type |
|------|------|----------|------|
| `backend_router.py` | 254-275 | `_process_prompt_interception_request` | Manual Request building |
| `schema_pipeline_routes.py` | 313 | `execute_optimization` | Direct Engine instantiation |
| `schema_pipeline_routes.py` | 1481 | `unified_streaming_generator` | Direct Engine instantiation |
| `schema_pipeline_routes.py` | 1627 | `optimization_streaming_generator` | Direct Engine instantiation |
| `schema_pipeline_routes.py` | 1747 | Optimization (non-streaming) | Direct Engine instantiation |
| `schema_pipeline_routes.py` | 3932 | Test Endpoint | Direct Engine instantiation |

---

## Unused Chunks

These chunks exist but are NOT USED because code bypasses ChunkBuilder:

- `optimize_clip_prompt.json` (CLIP optimization, 50 words)
- `optimize_t5_prompt.json` (T5 optimization, 250 words)
- `optimize_clip_prompt_llama.json` (Llama variant)
- `optimize_t5_prompt_mistral.json` (Mistral variant)

---

## Impact If build_full_prompt() Is Removed

**WOULD BREAK:**
- Stage 2 Interception (Streaming)
- Stage 3 Optimization (Streaming + Non-Streaming)
- All Streaming endpoints
- Test endpoints
- Backend Router for Ollama/OpenRouter

**Effort for Fix:** ~5 code paths need refactoring

---

## Refactoring Plan (Option A - Full Refactoring)

### Step 1: Simplify PromptInterceptionEngine
```python
# BEFORE (current)
class PromptInterceptionEngine:
    def build_full_prompt(self, ...) -> str:  # DELETE THIS
    async def process_request(self, request) -> Response:
        full_prompt = self.build_full_prompt(...)  # Uses own format
        return await self._call_api(full_prompt, model)

# AFTER (clean)
class PromptInterceptionEngine:
    async def process_request(self, prompt_text: str, model: str) -> Response:
        return await self._call_api(prompt_text, model)
```

### Step 2: Route All Calls Through ChunkBuilder
```python
# BEFORE (violation)
engine = PromptInterceptionEngine()
request = PromptInterceptionRequest(
    input_prompt=text,
    style_prompt=context,
    task_instruction=instruction,
    model=model
)
result = await engine.process_request(request)

# AFTER (correct)
chunk = chunk_builder.build_chunk(
    chunk_name="manipulate",
    config=config,
    input_text=text
)
result = await backend_router.route(chunk)
```

### Step 3: Create Optimization Pipelines
- Create `prompt_optimization.json` pipeline
- Create config variants for CLIP/T5 optimization
- Use existing unused chunks

### Estimated Effort: 4-6 hours

---

## Why This Matters

1. **Inconsistent Behavior**: Two different prompt formats for same operations
2. **Dead Code**: 4 optimization chunks are never used
3. **Maintenance Burden**: Changes need to be made in two places
4. **Testing Complexity**: Two code paths to test for same feature
5. **Architecture Erosion**: Violates the Single Source of Truth principle

---

## Decision

**Chosen:** Option B - Document now, refactor in dedicated session

**Rationale:**
- System currently works
- Refactoring requires careful testing of all streaming endpoints
- Better to plan dedicated session for systematic fix

---

## See Also

- `devserver/schemas/chunks/manipulate.json` - Correct template format
- `devserver/schemas/engine/chunk_builder.py` - How chunks should be built
- `devserver/schemas/engine/backend_router.py` - Correct routing path
- `docs/ARCHITECTURE PART 03 - ThreeLayer-System.md` - Architecture documentation
