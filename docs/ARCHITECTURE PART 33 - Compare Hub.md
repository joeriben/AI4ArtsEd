# ARCHITECTURE PART 33 — Compare Hub

## Overview

The Compare Hub (`/compare`) provides three comparison modes for investigating how AI systems produce different outputs from controlled variations. Each mode varies exactly one dimension while keeping everything else constant.

## Three Comparison Modes

### 1. Language Comparison
**Varies**: Input language | **Constant**: Model, seed
- User enters a prompt in any language
- Prompt is translated to all selected languages via `/api/schema/pipeline/translate` (LLM auto-detects source)
- Same model + same seed generates one image per language
- Reveals CLIP/T5 encoding bias — whose visual culture the model absorbed

### 2. Model Comparison
**Varies**: Image generation model | **Constant**: Prompt, seed
- Two preset lineups:
  - **Current Top Models**: SD 3.5 Large (diffusers), Flux 2 (ComfyUI), Gemini 3 Pro (cloud)
  - **SD History**: SD 1.5 (2022), SDXL (2023), SD 3.5 Large (2024)
- Same prompt + seed across all models
- Note: Same seed ≠ same image cross-model (different latent spaces). Seed ensures reproducibility within a model.

### 3. Temperature Comparison
**Varies**: LLM temperature (0, 0.5, 1.0) | **Constant**: Model, prompt
- Chat-based: sends same message to LLM at three temperature levels
- Model selector: local Ollama models + cloud models via `model_override` parameter
- `enable_thinking=False` for this mode — thinking models suppress temperature effects

## Safety

All modes go through the platform's safety system:
- **Stage 3**: Llama Guard S1-S13 check runs for ALL generation requests (even with `skip_stage3_translation=true`, safety check still executes — only translation is skipped)
- **Stage 4 VLM**: Post-generation image check for kids/youth safety levels
- Older models (SD 1.5, SDXL) have no built-in safety, but platform safety wraps around them

## Trashy (ComparisonChat) — Mode-Aware

`ComparisonChat.vue` accepts a `compare-type` prop (`'language'` | `'model'`), forwarded via `context.compare_type` in the chat request.

Backend routing in `build_system_prompt()`:
- `compare_type == 'model'` → `MODEL_COMPARISON_SYSTEM_PROMPT_TEMPLATE` (architecture evolution, parameter counts, training data differences)
- Default → `COMPARISON_SYSTEM_PROMPT_TEMPLATE` (CLIP/T5 encoding bias, language representation gaps)
- `temperature_compare_mode` has its own path (minimal system prompt, no comparison context)

## Key Files

| File | Purpose |
|------|---------|
| `views/compare_hub.vue` | Tab container (Language → Model → Temperature) |
| `views/compare/language_comparison.vue` | Language comparison with chip selector |
| `views/compare/model_comparison.vue` | Model comparison with preset toggle |
| `views/compare/temperature_comparison.vue` | Temperature comparison with model selector |
| `components/ComparisonChat.vue` | Trashy sidebar (shared, mode-aware via prop) |
| `chat_routes.py` | System prompts: `COMPARISON_SYSTEM_PROMPT_TEMPLATE`, `MODEL_COMPARISON_SYSTEM_PROMPT_TEMPLATE` |
| `schema_pipeline_routes.py` | `/pipeline/translate` (LLM auto-detect), `/pipeline/generation` (SSE streaming) |
| `schemas/configs/output/sd15.json` | SD 1.5 output config (ComfyUI, 512px) |
| `schemas/configs/output/sdxl.json` | SDXL output config (ComfyUI, 1024px) |

## Translation Endpoint

`/api/schema/pipeline/translate` is a generic translator:
- Receives `text` + `target_language`
- LLM auto-detects source language
- Handles any source→target pair including same-language (returns unchanged)
- `enable_thinking=False` prevents reasoning leak in translation output
- No hardcoded source language assumptions
