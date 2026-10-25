# DevServer Architecture

**Part 9: Model Selection**

---

## ⚠️ DEPRECATED (2025-11-23)

**This document describes an OBSOLETE task-based model selection system.**

**What changed:** The execution_mode parameter and task-based selection have been REPLACED with centralized configuration in `devserver/config.py`.

**Migration:** See `ARCHITECTURE PART 01 - Section 2: Model Selection Architecture` for current implementation.

**Current system:**
- Models defined as constants in `config.py` (e.g., `STAGE2_INTERCEPTION_MODEL`)
- Chunks reference config constants instead of hardcoded model names
- NO execution_mode parameter in API calls

**Retained for historical reference only.**

---


### Task-Based Selection System

**Purpose:** Select optimal LLM based on task requirements and execution mode

**Implementation:** `schemas/engine/model_selector.py`

### Task Categories

>>> OUTDATED! CHECK THE ACTUAL MODEL SELECTOR. IF YOU READ THIS: UPDATE THE MODELS BELOW AND COMMENT AS "UPDATED (DATE)"

| Task Type | Eco Model | Fast Model | Use Case |
|-----------|-----------|------------|----------|
| **security** | llama-guard-3-8b (local) | llama-guard-3-8b (local) | Content moderation (always local) |
| **vision** | llava:13b (local) | llava:13b (local) | Image analysis (DSGVO) |
| **translation** | qwen2.5-translator (local) | claude-3.5-haiku (cloud) | Language translation |
| **standard** | mistral-nemo (local) | mistral-nemo (cloud) | General text tasks |
| **advanced** | mistral-small:24b (local) | gemini-2.5-pro (cloud) | Complex reasoning |
| **data_extraction** | gemma3:4b (local) | gemma-3-4b-it (cloud) | Structured extraction |


### Usage in Chunks

**Option 1: Task-based selection (recommended):**
```json
{
  "model": "task:translation",
  "meta": {
    "task_type": "translation"
  }
}
```

**Option 2: Direct model specification:**
```json
{
  "model": "mistral-nemo:latest",
  "meta": {
    "task_type": "standard"
  }
}
```

### Execution Mode Behavior

**Eco Mode (default):**
- Uses local Ollama models
- Free, privacy-preserving, DSGVO-compliant
- Slower inference
- No API costs

**Fast Mode:**
- Uses cloud APIs (OpenRouter)
- Paid, requires API key
- Faster inference, higher quality
- For security/vision tasks: Still uses local models (DSGVO)

---

