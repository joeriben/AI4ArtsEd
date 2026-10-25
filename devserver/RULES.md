# DevServer MANDATORY RULES
**Read this BEFORE making ANY code changes**

---

## 0. FUNDAMENTAL WORK RULES (NON-NEGOTIABLE!)

### RTFM - Read The Documentation FIRST
**Before any task:** Read the relevant documentation in `docs/`
- `docs/ARCHITECTURE.md` - System architecture and design
- `docs/DEVELOPMENT_DECISIONS.md` - Why decisions were made
- GitHub Issues (`gh issue list`) - Current tasks and priorities (`docs/devserver_todos.md` was retired on 2026-09-08)
- This file (`RULES.md`) - Mandatory principles

**When confused:** Re-read the docs, don't guess!

### NEVER Delete Files - Mark as .obsolete Instead
**NEVER use `rm` command!**

Instead:
```bash
# ❌ WRONG
rm old_file.py

# ✅ CORRECT
mv old_file.py old_file.py.obsolete
# or
mv old_file.py old_file.obsolete.py
```

**Rationale:**
- Preserves history for recovery
- Allows comparison with previous versions
- Prevents accidental deletion of needed code
- Makes git diffs clearer

**Exception:** Only delete `.obsolete` files after explicit user confirmation.

---

## 1. TWO FUNDAMENTAL USE CASES (DO NOT MIX!)

### Interception-Pipelines (Orchestrierung)
**Nature:** Complex, intelligent, recursive
- Can have **multiple steps**
- Can be **recursive** (pipeline calls pipeline)
- Can **request media outputs** (server starts Output-Pipelines)
- The **"smart" orchestration layer**
- Examples: dada.json, bauhaus.json (30 configs)
- Pipeline: `text_transformation` (or more complex future pipelines)

**Example Flow:**
```
Interception-Pipeline: "Transform text in Dada style, then generate 3 image variants"
  → Step 1: Transform text
  → Step 2: Server starts 3x Output-Pipeline
  → Step 3: Collect results
```

### Output-Pipelines (Primitive Generators)
**Nature:** ALWAYS simple, ALWAYS primitive
- **ALWAYS only 1-2 inputs** (text, or text+image)
- **ALWAYS only 1 output** (one media file)
- **NO orchestration**, just: Input(s) → Media
- Architecturally flexible, but **functionally dumb**
- Examples: sd35_large.json, flux1_dev.json (4+ configs)
- Pipeline: `single_text_media_generation` or `dual_text_media_generation`

**Example Flow:**
```
Output-Pipeline: Takes 1 text prompt → Returns 1 image
(knows NOTHING about context, orchestration, or complexity)
```

---

## 2. CHUNK TYPES

### Processing Chunks (LLM Text Transformation)
- Name: `manipulate`
- Backend: Ollama or OpenRouter
- Purpose: Text transformation via LLM
- Used in: Interception-Pipelines

### Output Chunks (Media Generation)
- Names: `output_image_sd35_large`, `output_audio_stable_audio`, etc.
- Backend: ComfyUI or OpenRouter/OpenAI
- Purpose: Generate media
- **Contains:** Complete ComfyUI API workflow as JSON
- Used in: Output-Pipelines

**CRITICAL:** Output-Chunks contain **embedded ComfyUI API workflows**, not Python code that generates workflows!

---

## 3. CHUNK SELECTION LOGIC

**Server selects chunk, NOT config!**

**⚠️ UPDATED:** The execution_mode parameter system was removed. Model selection is now centralized in `devserver/config.py`.

Selection based on:
1. `media_type` (from config.media_preferences.default_output)
2. ~~`execution_mode` (eco/fast)~~ **[DEPRECATED]** → Model/backend now determined by constants in config.py

**~~Matrix:~~ [DEPRECATED - Historical Reference Only]**
| media_type | ~~eco mode~~ | ~~fast mode~~ |
|------------|----------|-----------|
| image | comfyui_image_generation | openrouter_image_generation |
| audio | comfyui_audio_generation | (fallback to eco) |
| music | comfyui_music_generation | (fallback to eco) |

**Current Reality:**
- Models are selected via constants: STAGE1_MODEL, STAGE2_INTERCEPTION_MODEL, STAGE3_MODEL, etc.
- Backend routing determined by which model constant is configured
- No dynamic eco/fast switching - change constants in config.py and restart server

**Config's job:** Specify media_type and parameters
**Server's job:** Select appropriate chunk based on config.py model constants

---

## 4. NAMING CONVENTIONS

### Chunks
- Processing: `manipulate` (generic)
- Output: `output_[media]_[model]_[variant]`
  - ✅ `output_image_sd35_large`
  - ❌ `output_image_sd35_standard` (NO "standard" - that's config-level!)

### Pipelines
- Named by INPUT type, NOT output type
- ✅ `single_text_media_generation` (input: 1 text)
- ✅ `dual_text_media_generation` (input: 2 texts)
- ❌ `image_generation` (output-focused name)

### Configs
- Interception: Descriptive (dada, bauhaus, overdrive)
- Output: Model + variant (sd35_large, flux1_dev, acestep_standard)
- "standard" is OK here (config-level concept)

---

## 5. ARCHITECTURE PRINCIPLES

### Backend Transparency
- Same pipeline can use **any backend**
- OpenRouter can handle BOTH:
  - Text transformation (Interception)
  - Image generation (Output)
- Backend choice based on execution_mode, NOT use case

### Pipeline Design
- **Input-type-based**, not output-type-based
- **Backend-agnostic**, media-agnostic
- Chunks are **NOT hardcoded** in pipeline definition
- Server dynamically selects chunks at runtime

### Separation of Concerns
**Three Layers:**
1. Chunks (primitives) - HOW to execute
2. Pipelines (orchestration) - WHAT sequence
3. Configs (content) - WITH what instructions

**No Fourth Layer!** Instruction text belongs in configs, not external registries.

---

## 6. COMMON MISTAKES TO AVOID

❌ **"Output-Pipeline should not have manipulate chunk"**
- Correct! Output-Pipelines are primitive, don't orchestrate

❌ **"Config chooses which chunk to use"**
- Wrong! Server chooses chunk based on media_type + execution_mode

❌ **"Chunk names contain 'standard'"**
- Wrong! That's a config-level concept, not chunk-level

❌ **"ComfyUI is for media, Ollama is for text"**
- Oversimplification! OpenRouter can do both

❌ **"Pipeline generates workflows dynamically"**
- Wrong! Output-Chunks contain pre-defined ComfyUI workflows

---

## BEFORE MAKING CHANGES - CHECKLIST

□ **Did I read the relevant docs?** (ARCHITECTURE.md, DEVELOPMENT_DECISIONS.md, RULES.md)
□ **Am I using `rm`?** (NEVER! Use .obsolete instead)
□ Which use case am I working on? (Interception OR Output)
□ Does my change follow naming conventions?
□ Am I adding complexity to Output-Pipelines? (DON'T!)
□ Am I hardcoding chunks in pipeline definition? (DON'T!)
□ Did I confuse config-level and chunk-level concepts?

---

## QUICK REFERENCE

**Interception Config Example:**
```json
{
  "pipeline": "text_transformation",
  "context": "Transform text in Dada style...",
  "media_preferences": {"default_output": "image"}
}
```

**Output Config Example:**
```json
{
  "pipeline": "single_text_media_generation",
  "parameters": {
    "OUTPUT_CHUNK": "output_image_sd35_large",
    "WIDTH": 1024, "HEIGHT": 1024
  },
  "media_preferences": {"default_output": "image"}
}
```

**Key Difference:**
- Interception has rich `context` field (instructions for LLM)
- Output has `OUTPUT_CHUNK` parameter (which chunk to use)

---

**Last Updated:** 2025-10-27 (Added: RTFM rule, .obsolete file marking rule)
**Maintain this file!** Update when architecture decisions change.
