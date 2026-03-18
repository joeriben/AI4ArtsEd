# Architecture Part 32: Dialogic AI Persona

## 1. Concept

The AI Persona page (`/persona`) inverts the standard generation flow. Instead of "user writes prompt, machine generates", the machine is an aesthetically opinionated conversation partner that decides autonomously:
- **Whether** to generate (it may refuse)
- **What** to generate (it chooses the prompt)
- **Which medium** to generate (image, audio, video, 3D, code)
- **Which model** to use (it chooses the output config)

The human's role shifts from consumer to interlocutor. This is pedagogically intentional: it forces articulation, reflection, and argumentation rather than consumption.

## 2. Architecture

### 2.1 No New Endpoints

The entire page is built from existing infrastructure:
- **Chat**: `/api/chat` with `context.persona_mode = true`
- **Generation**: `/api/schema/pipeline/generation` via `useGenerationStream`
- **Favorites**: `/api/favorites` via `useFavoritesStore`

### 2.2 System Prompt Routing

```
chat_routes.py:build_system_prompt()
  ├── context.persona_mode     → AI_PERSONA_SYSTEM_PROMPT
  ├── context.workshop_planning → WORKSHOP_PLANNING_SYSTEM_PROMPT
  ├── context.comparison_mode   → COMPARISON_SYSTEM_PROMPT_TEMPLATE
  └── run_id / default          → SESSION / GENERAL prompt
```

### 2.3 Generation Trigger Flow

```
1. User sends message → /api/chat (persona_mode)
2. LLM responds with text + optional [GENERATE: config_id | prompt]
3. Frontend parses markers via regex
4. For each marker: spawnGeneration(configId, prompt)
   → useGenerationStream().executeWithStreaming()
   → new floating MediaOutputBox appears
5. Text (sans markers) is spoken via speechSynthesis
```

### 2.4 Available Configs

The system prompt receives available configs via `draft_context`:
```
sd35_large, flux2_diffusers, gemini_3_pro_image, gpt_image_1,
stableaudio, heartmula_standard, p5js_code, tonejs_code,
wan22_t2v_video_fast, ltx_video, hunyuan3d_text_to_3d
```

The LLM chooses based on aesthetic intent. Not all configs work with single-prompt input (e.g. `heartmula_standard` requires dual input). The generation pipeline handles validation.

## 3. Frontend Architecture

### 3.1 Floating MediaOutputBoxes

Each generation spawns a draggable `MediaOutputBox` at an auto-calculated position.

**Reactivity pattern**: `shallowRef<MediaBox[]>` + `triggerRef`
- `shallowRef` prevents Vue from deep-unwrapping `Ref` types inside `useGenerationStream()` return values
- `triggerRef(mediaBoxes)` after in-place mutations (drag, favorite, generation complete)
- Array replacement for add/remove (`[...mediaBoxes.value, box]`, `.filter()`)

**Placement algorithm**: Grid-based, 320x340px boxes, 20px margins, viewport-clamped. First free position in left-to-right, top-to-bottom scan. Dragging overrides auto-position.

### 3.2 Marker Parsing

Two marker types:
- `[PROMPT: suggestion]` — rendered as clickable button (fills input)
- `[GENERATE: config_id | prompt text]` — stripped from display, triggers generation

### 3.3 Browser TTS

`speechSynthesis` API (free, no backend). Markers stripped before speaking. Language auto-detected from user preferences. Toggle button in chat header.

## 4. Persona Identity

The system prompt defines a machine that:
- Has aesthetic judgement (from training data) but no emotions
- Generates only when the conversation convinces it
- May refuse ("That does not convince me.")
- May generate unsolicited when dialogue becomes inspiring
- Chooses medium and model autonomously
- Speaks directly, without filler or pleasantries
- Pushes back on cliches
- References art, music, film from its training data

All content remains age-appropriate (9-17, educators present). Safety systems apply normally.

## 5. Files

| File | Role |
|------|------|
| `src/views/ai_persona.vue` | Page component |
| `devserver/my_app/routes/chat_routes.py` | `AI_PERSONA_SYSTEM_PROMPT` + routing |
| `src/router/index.ts` | `/persona` route |
| `src/assets/icons/volume_up_*.svg` | TTS on icon |
| `src/assets/icons/volume_off_*.svg` | TTS off icon |
