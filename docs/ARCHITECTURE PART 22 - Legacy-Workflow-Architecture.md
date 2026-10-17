# DevServer Architecture

**Part 22: Legacy Workflow Architecture & Convention-Based Routing**

---

## Overview

> **2026-08-12 — convention-based routing by URL is gone.** `PipelineRouter.vue`
> and the `/execute/:configId` route were removed together with the transform
> mode: the loader existed to pick one of those pages by pipeline name, and its
> fallback was `text_transformation.vue`. `/execute/:configId` redirects to
> `/x2x-flow`. The legacy workflows themselves are untouched — they are reached
> through their own routes and through the media configs, not through this
> loader. Passages below that describe the loader are the record of how it
> worked.

Legacy workflows are complete ComfyUI workflow JSON files that cannot be decomposed into DevServer's chunk system due to complex node connections and custom processing logic. They bypass Stage 2 (Prompt Interception) and pass prompts directly to ComfyUI with parameter injection.

**Key Pattern:** Config → Pipeline → Vue (Convention-based routing)

---

## Architecture Pattern

### Convention-Based Routing

**No explicit registry needed!** The system uses **filename matching convention**:

```
Pipeline JSON "name" field = Vue component filename

Example:
  pipelines/surrealizer.json → "name": "surrealizer" → views/surrealizer.vue
  pipelines/direct.json       → "name": "direct"       → views/direct.vue
```

**Complete Flow:**

```
1. User navigates to: /execute/surrealizer
2. Frontend: PipelineRouter.vue extracts configId = "surrealizer"
3. Frontend: GET /api/config/surrealizer/pipeline
4. Backend: Loads configs/interception/surrealizer.json
5. Backend: Reads "pipeline": "surrealizer"
6. Backend: Loads pipelines/surrealizer.json
7. Backend: Reads "name": "surrealizer"
8. Backend: Returns {"pipeline_name": "surrealizer", ...}
9. Frontend: Receives pipeline_name = "surrealizer"
10. Frontend: import(`../views/${pipelineName}.vue`) → surrealizer.vue
11. Vue component renders
```

**Critical File Locations:**
- **Backend route:** `devserver/my_app/routes/schema_pipeline_routes.py:2915-2955`
- **Frontend router:** `public/ai4artsed-frontend/src/views/PipelineRouter.vue:18-49`

---

## Two Types of Legacy Workflows

### 1. Production Workflows (Dedicated Vue)

**Pattern:** One config → One pipeline → One dedicated Vue

**Example: Surrealizer**
```
configs/interception/surrealizer.json
  └─ "pipeline": "surrealizer"
       └─ pipelines/surrealizer.json
            └─ "name": "surrealizer"
                 └─ views/surrealizer.vue (dedicated, no dropdown)
```

**Characteristics:**
- **Hardcoded output config** (e.g., `surrealization_legacy`)
- **No dropdown selection** - focused UX
- **Production-stable** - tested in workshops
- **Non-reusable pipeline** (`"reusable": false`)

**Use Cases:**
- Workshop-tested workflows
- Stable pedagogical tools
- Workflows with specific UI requirements (sliders, advanced controls)

### 2. Experimental Workflows (Generic Vue with Dropdown)

**Pattern:** Multiple configs → One pipeline → One generic Vue with dropdown

**Example: Direct/Hacking Lab** (currently deactivated)
```
configs/interception/direct_workflow.json
  └─ "pipeline": "direct"
       └─ pipelines/direct.json
            └─ "name": "direct"
                 └─ views/direct.vue (dropdown to select configs)
```

**Characteristics:**
- **Dropdown selection** for multiple output configs
- **Generic interface** - same UI for all experiments
- **Rapid prototyping** - no new Vue needed
- **Reusable pipeline** (`"reusable": true`)

**Use Cases:**
- Testing new ComfyUI workflows
- Research experiments
- Short-term prototypes before promoting to dedicated Vue

---

## Legacy Workflow Helpers

**File:** `devserver/my_app/services/legacy_workflow_service.py`

Two functions, called by `backend_router._process_legacy_workflow` before the
websocket client submits the workflow: `inject_prompt` (via `input_mappings`,
else by node title) and `replace_llm_models` (every prompt-interception node
on the Stage-2 model). Submission, waiting and download go through
`comfyui_ws_client.submit_and_track`, which holds the GPU lease; the module's
own door to ComfyUI (submit, poll `/history`, download `/view`) had no caller
and was removed on 2026-10-10.

### Input Mappings Pattern

**Modern pattern:**

```json
{
  "input_mappings": {
    "prompt": {
      "node_id": "43",
      "field": "inputs.value",
      "description": "User prompt input"
    },
    "alpha": {
      "node_id": "50",
      "field": "inputs.value",
      "description": "T5-CLIP fusion alpha factor"
    },
    "seed": {
      "node_id": "3",
      "field": "inputs.seed",
      "default": "random"
    }
  }
}
```

**Backend Injection (backend_router.py:739-753):**
```python
# Handle alpha_factor for T5-CLIP fusion workflows
if input_mappings and 'alpha' in input_mappings and 'alpha_factor' in parameters:
    alpha_mapping = input_mappings['alpha']
    alpha_value = parameters['alpha_factor']

    logger.info(f"[LEGACY-WORKFLOW] Injecting alpha_factor={alpha_value}")

    alpha_node_id = alpha_mapping.get('node_id')
    alpha_field = alpha_mapping.get('field', 'inputs.value')
    if alpha_node_id and alpha_node_id in workflow:
        field_parts = alpha_field.split('.')
        target = workflow[alpha_node_id]
        for part in field_parts[:-1]:
            target = target.setdefault(part, {})
        target[field_parts[-1]] = alpha_value
        logger.info(f"[LEGACY-WORKFLOW] ✓ Injected alpha into node {alpha_node_id}.{alpha_field}")
```

**Fallback pattern (legacy):**
- Title-based node search for `ai4artsed_text_prompt`
- Used when `input_mappings` not defined

---

## Hallucinator (formerly Surrealizer)

The Hallucinator is an explorative, vector-based workflow that operates directly in embedding space rather than through conventional prompting. Full documentation including mechanism, geometric deep-dive, implementation details, and historical context has been moved to:

**→ See [ARCHITECTURE PART 25 — Explorative Vector-Based Workflows](ARCHITECTURE%20PART%2025%20-%20Explorative-Vector-Based-Workflows.md)**

This document (PART 22) covers only the legacy workflow routing and conventions that apply to the Hallucinator as one instance of the legacy workflow pattern.

---

## Migration Path: Adding New Legacy Workflows

### Decision Tree

**Is this workflow stable and tested?**
- **YES** → Create dedicated Vue (Option A)
- **NO** → Add to `direct.vue` dropdown (Option B) [if reactivated]

### Option A: Dedicated Vue (Like Surrealizer)

**When to use:**
- Workshop-tested workflow
- Production-ready feature
- Custom UI needed (sliders, advanced controls)

**Steps (CRITICAL ORDER!):**

1. **FIRST: Create Vue component**
   ```bash
   cp public/ai4artsed-frontend/src/views/surrealizer.vue \
      public/ai4artsed-frontend/src/views/new_workflow.vue

   # Edit new_workflow.vue:
   # - Update API call: output_config: 'new_workflow_legacy'
   # - Customize UI as needed
   ```

2. **THEN: Create pipeline definition**
   ```bash
   # File: devserver/schemas/pipelines/new_workflow.json
   {
     "name": "new_workflow",  // MUST match Vue filename!
     "pipeline_type": "passthrough",
     "skip_stage2": true,
     "description": "Description of workflow",
     "meta": {
       "reusable": false  // Dedicated workflow
     }
   }
   ```

3. **LAST: Update config reference**
   ```bash
   # File: devserver/schemas/configs/interception/new_workflow.json
   {
     "pipeline": "new_workflow",  // Changed from "direct"
     "instruction_type": "new_workflow",
     ...
   }
   ```

4. **Restart backend** (to reload configs)
   ```bash
   ./3_start_backend_dev.sh
   ```

5. **Test routing**
   ```bash
   curl http://localhost:17802/api/config/new_workflow/pipeline | jq '.pipeline_name'
   # Should return: "new_workflow"
   ```

**Why this order matters:**
- ❌ WRONG: Change config first → Backend can't find pipeline → 404 error
- ✅ RIGHT: Create all dependencies first → No breaking changes

### Option B: Add to direct.vue Dropdown (Experimental)

**When to use:**
- Testing new workflow
- Research prototype
- Short-term experiment

**Steps:**

1. **Add to dropdown** (if direct.vue reactivated)
   ```typescript
   // In direct.vue:
   const availableConfigs: OutputConfig[] = [
     { id: 'surrealization_legacy', label: 'Surrealization' },
     { id: 'new_experiment_legacy', label: 'New Experiment' }  // Add here
   ]
   ```

2. **No pipeline changes needed** - uses `direct` pipeline

3. **Promote to dedicated Vue when stable**

---

## Common Pitfalls & Solutions

### Pitfall 1: Pipeline Name ≠ Vue Filename

**Problem:**
```json
// pipelines/surrealizer.json
{"name": "surrealizerWorkflow"}  // ❌ Vue file is surrealizer.vue
```

**Solution:** **EXACT match required (case-sensitive!)**
```json
{"name": "surrealizer"}  // ✅ Matches surrealizer.vue
```

### Pitfall 2: Wrong Order of Operations

**Problem:**
```bash
# ❌ WRONG ORDER:
1. Update config: "pipeline": "new_workflow"
2. Create pipeline
3. Create Vue
# → 404 errors between step 1 and 2!
```

**Solution:**
```bash
# ✅ CORRECT ORDER:
1. Create Vue
2. Create pipeline
3. Update config
# → No 404, all dependencies met
```

### Pitfall 3: Typo in Filename

**Problem:**
```
Pipeline: "surrealizer"
Vue:      "Surrealizer.vue"  // ❌ Capital S
```

**Solution:** Use exact lowercase match
```
Pipeline: "surrealizer"
Vue:      "surrealizer.vue"  // ✅
```

### Pitfall 4: Forgot to Restart Backend

**Problem:**
```bash
# Changed config
curl /api/config/surrealizer/pipeline
# Still returns old pipeline_name ❌
```

**Solution:**
```bash
# Restart backend to reload configs
./3_start_backend_dev.sh

curl /api/config/surrealizer/pipeline
# Now returns new pipeline_name ✅
```

### Pitfall 5: Input Mappings Not Defined

**Problem:**
```python
# Backend tries to inject alpha_factor
# But chunk JSON has no input_mappings.alpha
# → Parameter silently ignored
```

**Solution:** Define `input_mappings` in chunk JSON
```json
{
  "input_mappings": {
    "alpha": {
      "node_id": "50",
      "field": "inputs.value"
    }
  }
}
```

---

## Testing Checklist

### Backend Tests

```bash
# 1. Check pipeline routing
curl http://localhost:17802/api/config/surrealizer/pipeline | jq '.pipeline_name'
# Expected: "surrealizer"

# 2. Check config loads
curl http://localhost:17802/api/config/surrealizer/pipeline | jq '.'
# Should return full pipeline metadata

# 3. Test workflow execution (requires ComfyUI running)
curl -X POST http://localhost:17802/api/schema/pipeline/execute \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "surrealizer",
    "input_text": "test prompt",
    "output_config": "surrealization_legacy",
    "alpha_factor": 0,
    "seed": 123456789
  }'
```

### Frontend Tests

1. Navigate to `/execute/surrealizer`
   - ✓ Loads surrealizer.vue (no dropdown visible)
   - ✓ Slider appears (5 labels, gradient)
   - ✓ No console errors

2. Test workflow execution
   - ✓ Enter prompt, adjust alpha slider
   - ✓ Click execute
   - ✓ Progress animation shows
   - ✓ Image appears in output frame
   - ✓ Action toolbar visible (⭐🖨️➡️💾🔍)

3. Test parameter injection
   - ✓ Backend logs show: `[LEGACY-WORKFLOW] Injecting alpha_factor=X`
   - ✓ Backend logs show: `[LEGACY-WORKFLOW] ✓ Injected alpha into node 50`
   - ✓ Different alpha values produce different images

### Integration Tests

1. **Test routing for multiple configs**
   ```bash
   curl http://localhost:17802/api/config/surrealizer/pipeline | jq '.pipeline_name'
   # → "surrealizer"

   curl http://localhost:17802/api/config/displaced_world/pipeline | jq '.pipeline_name'
   # → "displaced_world" (if implemented)
   ```

2. **Test seed reproducibility**
   - Run same prompt + alpha + seed twice
   - ✓ Images should be identical (verify by hash)

3. **Test metadata export**
   - Download generated image metadata JSON
   - ✓ Contains: seed, alpha_factor, workflow_json

---

## Architecture Principles

### Principle 1: Convention Over Configuration

**No explicit routing registry needed.** The system uses filename matching:
```
Pipeline "name" = Vue filename → Automatic routing
```

**Benefits:**
- Less code to maintain
- No registry to update
- Fails gracefully (fallback to text_transformation.vue)

### Principle 2: Dependencies Before References

**Always create dependencies BEFORE referencing them:**
```
Vue exists → Pipeline exists → Config references → No 404 errors
```

### Principle 3: Separation of Concerns

**Three-layer architecture:**
- **Config (Stage 2):** UI metadata, user-facing properties
- **Pipeline (Stage 2):** Execution logic, stage flow
- **Vue (Frontend):** User interface, interaction patterns

Each layer has a single responsibility.

### Principle 4: Data Flow Through input_mappings

**Modern pattern:**
```
Frontend → API (alpha_factor) → Backend Router → input_mappings → Workflow Nodes
```

**No hardcoded node IDs in code!** All injection points defined in chunk JSON.

---

## Historical Context

### First slider attempt (failed)
- Attempted to add slider without understanding routing
- Confused about how to inject simple integer (alpha value)
- Did not properly copy working patterns from other Vues

### Second slider attempt (successful)
- Understood convention-based routing
- Followed correct order of operations
- Created dedicated Vue with proper separation
- Documented pattern for future use

**Key Learning:** Past failures were due to:
1. Not understanding filename convention
2. Wrong order of file creation
3. Trying to "improve" instead of copying working code

---

## Future Directions

### Planned Workflows (User mentioned 2-3 more)
- `displaced_world` - Already has config, needs dedicated Vue?
- `relational_inquiry` - Already has config, needs dedicated Vue?
- `digital_photography` - Recently added

### Reactivating Generic Hacking Lab
If needed, `direct.vue` can be reactivated by:
1. Renaming `direct_workflow.json.deactivated` → `direct_workflow.json`
2. Adding experimental workflows to `availableConfigs` array
3. Using for rapid prototyping before promoting to dedicated Vues

---

## References

### Key Architecture Documents
- `ARCHITECTURE PART 01` - 4-Stage Orchestration Flow
- `ARCHITECTURE PART 12` - Frontend Architecture
- `ARCHITECTURE PART 25` - Explorative Vector-Based Workflows (Hallucinator details)
- `DATA_FLOW_ARCHITECTURE.md` - Custom placeholders pattern

### Code Files
- **Backend routing:** `devserver/my_app/routes/schema_pipeline_routes.py:2915-2955`
- **Frontend routing:** `public/ai4artsed-frontend/src/views/PipelineRouter.vue`
- **Legacy helpers:** `devserver/my_app/services/legacy_workflow_service.py`
- **Backend router:** `devserver/schemas/engine/backend_router.py:739-753`

### Decision Record
- `docs/DEVELOPMENT_DECISIONS.md` - Hallucinator slider routing entry

### Example Workflow
- **Chunk:** `devserver/schemas/chunks/legacy_surrealization.json`
- **Output config:** `devserver/schemas/configs/output/surrealization_legacy.json`
- **Stage2 config:** `devserver/schemas/configs/interception/surrealizer.json`
- **Pipeline:** `devserver/schemas/pipelines/surrealizer.json`
- **Vue:** `public/ai4artsed-frontend/src/views/surrealizer.vue`

---

**Document Status:** Active (2026-02-08)
**Maintainer:** AI4ArtsEd Development Team
**Last Updated:** Hallucinator Diffusers backend, token-level fusion
