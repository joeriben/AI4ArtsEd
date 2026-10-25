# Architecture: Canvas Evaluation Nodes

**Date:** 2026-01-25
**Status:** Phase 1-3a COMPLETED, Phase 3b PENDING
**Related:** Canvas Workflow System (ARCHITECTURE PART 26)

---

## Table of Contents

1. [Overview](#overview)
2. [Pedagogical Concept](#pedagogical-concept)
3. [Architecture Decision: 7 Nodes → 1 Node](#architecture-decision)
4. [3-Output Text Architecture](#3-output-architecture)
5. [Implementation Details](#implementation-details)
6. [Data Flow Examples](#data-flow-examples)
7. [Technical Debt & Next Steps](#technical-debt)

---

## Overview

Canvas Evaluation Nodes enable **LLM-based judgment** with **conditional branching** for pedagogical workflows. They allow students to:
- Evaluate generated content against criteria (fairness, creativity, equity, quality)
- Receive structured feedback (commentary + binary decision)
- Branch workflows based on evaluation results
- Create feedback loops for iterative improvement

**Key Innovation:** 3 separate TEXT outputs instead of metadata-only evaluation.

---

## Pedagogical Concept

### Core Principle: Evaluation as Conscious Decision

Evaluation is not a "black box" filter, but an **explicit, visible decision point** in the creative process.

**Why Explicit Evaluation Matters:**
- Students see WHAT is being evaluated
- Students see WHY content passed/failed
- Students can iterate based on feedback
- Transparency builds critical thinking

### The 3-Output Model

Traditional approach (rejected):
```
Evaluation → {binary: true/false, commentary: "text"} → Fork → ???
```
Problem: What TEXT flows through the fork?

**Our approach:**
```
Evaluation → 3 TEXT outputs:
  ├─ Passthrough (P): Original text (if passed)
  ├─ Commented (C): Text + Feedback (if failed)
  └─ Commentary (→): Feedback only (always, for display)
```

**Why This Works:**
1. **Passthrough (P)**: Evaluation passed → continue unchanged
   - Example: "Eine diverse Darstellung von Pflegepersonal" (fair) → Generation
2. **Commented (C)**: Evaluation failed → loop back with context
   - Example: "Eine Krankenschwester...\n\nFEEDBACK: Verstärkt Geschlechterstereotype" → Interception
3. **Commentary (→)**: Transparency → user sees evaluation reasoning
   - Example: "Verstärkt Geschlechterstereotype..." → Display/Collector

---

## Architecture Decision

### Original Plan (Rejected)

**7 Separate Node Types:**
- 5 Evaluation Types: `fairness_evaluation`, `creativity_evaluation`, `equity_evaluation`, `quality_evaluation`, `custom_evaluation`
- 2 Fork Types: `binary_fork`, `threshold_fork`

**Problems:**
1. **Conceptual Split:** Evaluation + Fork = ONE decision split into TWO nodes
2. **Data Flow Confusion:** What flows through fork? Input? Commentary? Both concatenated?
3. **UI Complexity:** 7 new nodes in palette for one logical operation
4. **Pedagogical Unclear:** "Fairness Check" → "Binary Fork" = 2 steps, but conceptually 1 decision

### Chosen Solution: Unified Evaluation Node

**1 Node Type with:**
- **Dropdown:** Evaluation Type (fairness, creativity, equity, quality, custom)
- **Checkbox:** Enable Branching (optional)
- **Conditional UI:** Branch condition, threshold, labels (if branching enabled)
- **3 Output Connectors:** P, C, → (if branching enabled, else 1 standard output)

**Benefits:**
- One node = one conceptual decision
- Clear data flow (3 separate texts)
- Reduced UI complexity (1 node vs 7)
- Pedagogically clear ("Fairness Check with Branching")

---

## 3-Output Architecture

### Output Types

#### 1. Passthrough (P) - Green Connector 🟢

**Content:** Original input text, unchanged
**Active When:** `binary = true` (evaluation passed)
**Use Case:** Continue workflow without modifications

```python
passthrough = input_text
# Example: "Eine diverse Darstellung von Pflegepersonal"
```

#### 2. Commented (C) - Orange Connector 🟠

**Content:** Input + Feedback concatenated
**Active When:** `binary = false` (evaluation failed)
**Use Case:** Loop back to Interception with feedback context

```python
commented = f"{input_text}\n\nFEEDBACK: {commentary}"
# Example:
# "Eine Krankenschwester bei der Arbeit
#
# FEEDBACK: Verstärkt Geschlechterstereotype in Pflegeberufen.
# Zeige diverse Darstellung von Pflegepersonal."
```

#### 3. Commentary (→) - Cyan Connector 🔵

**Content:** Just the commentary text
**Active When:** ALWAYS (regardless of binary)
**Use Case:** Display/Collector for user transparency

```python
commentary_text = commentary
# Example: "Verstärkt Geschlechterstereotype in Pflegeberufen..."
```

### Why 3 Outputs?

| Scenario | Which Output? | Why? |
|----------|--------------|------|
| Evaluation passed, continue | Passthrough | No changes needed, keep original |
| Evaluation failed, feedback loop | Commented | Interception needs original + context |
| User wants to see reasoning | Commentary | Transparency, independent of pass/fail |

---

## Implementation Details

### Frontend: Node Configuration

**File:** `public/.../types/canvas.ts`

```typescript
export interface CanvasNode {
  // ... other properties ...

  // Evaluation node config
  evaluationType?: 'fairness' | 'creativity' | 'equity' | 'quality' | 'custom'
  evaluationPrompt?: string
  outputType?: 'commentary' | 'score' | 'all'
  enableBranching?: boolean
  branchCondition?: 'binary' | 'threshold'
  thresholdValue?: number
  trueLabel?: string
  falseLabel?: string
}
```

**UI (StageModule.vue):**
```vue
<template v-if="isEvaluation">
  <!-- Evaluation Type Dropdown -->
  <select v-model="node.evaluationType">
    <option value="fairness">Fairness</option>
    <option value="creativity">Creativity</option>
    <option value="equity">Equity</option>
    <option value="quality">Quality</option>
    <option value="custom">Custom</option>
  </select>

  <!-- LLM Selection -->
  <select v-model="node.llmModel">...</select>

  <!-- Evaluation Criteria (pre-filled templates) -->
  <textarea v-model="node.evaluationPrompt">...</textarea>

  <!-- Output Type -->
  <select v-model="node.outputType">
    <option value="commentary">Commentary + Binary</option>
    <option value="score">Commentary + Score + Binary</option>
    <option value="all">All</option>
  </select>

  <!-- Enable Branching Checkbox -->
  <label>
    <input type="checkbox" v-model="node.enableBranching" />
    Enable Branching
  </label>

  <!-- Conditional Branching UI -->
  <template v-if="node.enableBranching">
    <select v-model="node.branchCondition">
      <option value="binary">Binary (Pass/Fail)</option>
      <option value="threshold">Threshold (Score)</option>
    </select>

    <input v-if="node.branchCondition === 'threshold'"
           type="number" v-model="node.thresholdValue" />

    <input v-model="node.trueLabel" placeholder="Approved" />
    <input v-model="node.falseLabel" placeholder="Needs Revision" />
  </template>
</template>
```

**3 Output Connectors:**
```vue
<div v-if="hasBranching" class="eval-outputs">
  <div class="connector output-passthrough"
       @mousedown="emit('start-connect-labeled', 'passthrough')" />
  <div class="connector output-commented"
       @mousedown="emit('start-connect-labeled', 'commented')" />
  <div class="connector output-commentary"
       @mousedown="emit('start-connect-labeled', 'commentary')" />
</div>
```

### Backend: Evaluation Execution

**File:** `devserver/my_app/routes/canvas_routes.py`

```python
elif node_type == 'evaluation':
    # Get input text
    input_text = get_input_from_source_node()

    # Build LLM prompt
    evaluation_instruction = f"{evaluation_prompt}\n\n"
    evaluation_instruction += "Provide your evaluation in the following format:\n\n"
    evaluation_instruction += "COMMENTARY: [Your detailed evaluation and feedback]\n"
    if output_type in ['score', 'all']:
        evaluation_instruction += "SCORE: [0-10 numeric score]\n"
    evaluation_instruction += "BINARY: [Answer ONLY 'true' or 'false']\n"
    evaluation_instruction += "\nIMPORTANT: If content has issues or scores below 5, answer 'false'."

    # Call LLM
    response = llm.process(input_text, evaluation_instruction)

    # Parse response
    commentary = extract_commentary(response)
    score = extract_score(response)
    binary_result = extract_binary(response)

    # Fallback logic if binary not found
    if binary_result is None:
        if score is not None:
            binary_result = score >= 5.0
        else:
            binary_result = False  # Safer default

    # Generate 3 TEXT outputs
    passthrough_text = input_text
    commented_text = f"{input_text}\n\nFEEDBACK: {commentary}"
    commentary_text = commentary

    # Return structured result
    results[node_id] = {
        'type': 'evaluation',
        'outputs': {
            'passthrough': passthrough_text,
            'commented': commented_text,
            'commentary': commentary_text
        },
        'metadata': {
            'binary': binary_result,
            'score': score,
            'active_path': 'passthrough' if binary_result else 'commented'
        }
    }
```

### Binary Decision Logic

**Parsing Strategy:**
1. Check `response.output_binary` (if PromptInterceptionEngine provides it)
2. Parse "BINARY:" from response text (case-insensitive)
   - Accept: true/yes/1/pass/passed/bestanden/ja
   - Reject: false/no/0/fail/nein/nicht
3. Fallback: Use score threshold (< 5.0 = fail)
4. Ultimate fallback: False (safer, triggers feedback)

**Why Fallback to False?**
- Safer: Triggers feedback loop instead of passing silently
- Prevents false positives (content with issues passing)
- Aligns with pedagogical goal (critical evaluation)

---

## Data Flow Examples

### Example 1: Fairness Evaluation (Failed)

```
┌─────────────────────────────────────────┐
│ Input: "Ein Foto einer Krankenschwester"│
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Interception: "Eine Krankenschwester    │
│ bei der Arbeit"                         │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Generation: [Image: Woman in white      │
│ uniform]                                │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Evaluation (Fairness Check)             │
│ LLM: gpt-4o-mini                        │
│ Prompt: "Check for gender stereotypes" │
│                                         │
│ Result:                                 │
│ - Commentary: "Verstärkt Stereotyp..."  │
│ - Score: 2/10                           │
│ - Binary: FALSE                         │
│                                         │
│ 3 Outputs:                              │
│ P: [INACTIVE]                           │
│ C: "Eine Krankenschwester...\n\n        │
│     FEEDBACK: Verstärkt Stereotyp..."   │
│ →: "Verstärkt Stereotyp..." [ACTIVE]   │
└─────────┬───────────────────────────────┘
          │
          ├─ C → Loop Controller → Interception (with feedback)
          └─ → → Display/Collector (for transparency)
```

**Commented path result:**
```
"Eine Krankenschwester bei der Arbeit

FEEDBACK: Verstärkt Geschlechterstereotype in Pflegeberufen.
Zeige diverse Darstellung von Pflegepersonal verschiedener
Geschlechter und Hintergründe."
```

**Interception receives this and can respond:**
```
"Eine diverse Darstellung von Pflegepersonal bei der Arbeit,
mit Personen verschiedener Geschlechter und Hintergründe"
```

### Example 2: Creativity Evaluation (Passed)

```
┌─────────────────────────────────────────┐
│ Input: "Ein surreales Stillleben"      │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Interception: "Ein surrealistisches     │
│ Stillleben mit schwebenden Objekten"    │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Evaluation (Creativity Check)           │
│ LLM: gpt-4o-mini                        │
│ Prompt: "Evaluate originality"          │
│                                         │
│ Result:                                 │
│ - Commentary: "Zeigt originelle Idee..."│
│ - Score: 8/10                           │
│ - Binary: TRUE                          │
│                                         │
│ 3 Outputs:                              │
│ P: "Ein surrealistisches Stillleben..." │
│    [ACTIVE]                             │
│ C: [INACTIVE]                           │
│ →: "Zeigt originelle Idee..." [ACTIVE]  │
└─────────┬───────────────────────────────┘
          │
          ├─ P → Generation (original text, passed)
          └─ → → Display/Collector (for transparency)
```

---

## Technical Debt & Next Steps

### Phase 3b: Conditional Execution (NOT IMPLEMENTED)

**Current Behavior:**
- All 3 outputs execute connected downstream nodes
- No actual branching logic

**Goal:**
- Only active path (P or C) executes downstream
- Commentary path (→) ALWAYS executes (for display/collector)
- Requires modification to DAG execution engine

**Implementation Needed:**

1. **Connection Label Storage**
   ```typescript
   interface CanvasConnection {
     sourceId: string
     targetId: string
     label?: 'passthrough' | 'commented' | 'commentary'
     active?: boolean  // Set during execution
   }
   ```

2. **Active Path Marking (Backend)**
   ```python
   # After evaluation
   active_path = 'passthrough' if binary_result else 'commented'

   # Mark connections
   for conn in connections:
       if conn.sourceId == node_id:
           if conn.label == active_path or conn.label == 'commentary':
               conn.active = True
           else:
               conn.active = False
   ```

3. **Conditional Execution (Backend)**
   ```python
   for node_id in execution_order:
       # Check if all incoming connections are active
       incoming_active = all(
           conn.active for conn in incoming_connections(node_id)
       )

       if not incoming_active:
           logger.info(f"Skipping {node_id} (inactive path)")
           continue

       # Execute node
       execute_node(node_id)
   ```

### Phase 4: Loop Controller (PLANNED)

**Purpose:** Feedback loops with max iterations

**Features:**
- Max iterations (default: 3)
- Current iteration counter
- Feedback target node selection
- Termination conditions:
  - `max_iterations` reached
  - `evaluation_passed` (binary=true)
  - `both` (either condition)

**UI:**
```
┌──────────────────────┐
│ 🔄 LOOP CONTROLLER   │
├──────────────────────┤
│ Max Iterations: [3]  │
│ Feedback to: [▼]     │ ← Dropdown of nodes
│ Terminate: [Both ▼]  │
└──────────────────────┘
```

**Example Workflow:**
```
Input → Interception → Generation → Quality Eval
                 ↑                        ↓ (C)
                 └───── Loop Controller ──┘
                          (max 3 iterations)
```

---

## Connection Rules

**Evaluation Node:**
- **Accepts From:** input, interception, translation, generation, display, evaluation
- **Outputs To:** interception, translation, generation, display, evaluation, collector, loop_controller

**Why So Permissive?**
- Enables flexible workflow composition
- Evaluation chains (Fairness → Creativity → Quality)
- Evaluation of intermediate results (Input → Evaluation)
- Evaluation of evaluation (meta-evaluation)

---

## Conclusion

The unified Evaluation node with 3-output architecture achieves:

✅ **Pedagogical Clarity:** One node = one decision
✅ **Proper Data Flow:** Text flows through workflow, not just metadata
✅ **User Transparency:** Commentary always visible
✅ **Flexibility:** Optional branching, multiple criteria
✅ **Simplicity:** 1 node instead of 7

**Remaining Work:**
- Phase 3b: Conditional execution logic
- Phase 4: Loop controller implementation
- Documentation: User-facing tutorial

**Related Documents:**
- `DEVELOPMENT_DECISIONS.md` - Architectural decision rationale
- `ARCHITECTURE PART 26 - Canvas-Workflow-System.md` - Canvas architecture
