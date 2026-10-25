# AI4ArtsEd ComfyUI Nodes - Dev Log

## 2026-09-12

### Forked into ai4artsed_webserver, keys from the platform

This package is now `comfyui_nodes/ai4artsed_comfyui/` in the ai4artsed_webserver
repository, copied whole from `github.com/joeriben/ai4artsed_comfyui_nodes`
(0.7, commit ddd40dd of 2026-01-20), and developed there from here on. The origin stays a ComfyUI-only package.

- No `openrouter.key` / `stabilityai.key` next to the sources any more. The two
  key nodes read the platform's key through `_platform_credentials.py`, which
  loads the DevServer's own key reader by path: `OPENROUTER_API_KEY`, else
  `devserver/openrouter.key`; `STABILITY_API_KEY`, else `devserver/stability.key`.
- The LLM nodes (prompt interception, both randomizers, the safety switch, image
  analysis) call no provider. Their calls go to the DevServer, which acts as
  their LLM proxy (`_devserver.py`: `GET /api/chat/models` for the dropdown,
  `POST /api/chat/proxy` for the call). The DevServer resolves the model, holds
  the keys and the provider table, and applies the fallback the settings page
  regulates. The `api_key` and `unload_model` inputs are gone with that.
- No fallback chain in the nodes. `find_openrouter_fallback`,
  `find_ollama_fallback` and the probe `test_openrouter_model` are gone: a
  failing call raises with the DevServer's answer, and no other model answers
  in a node's place (the platform's rule since 2026-08-17). The fallback that
  exists is the settings' one, behind `platform/<ROLE>` in the dropdown.
- No model id in the code. A dropdown offers the node's platform role
  (`platform/STAGE2_INTERCEPTION_MODEL`, ...) and then every model this
  installation offers, by the DevServer's list.
- A missing key is reported by the key nodes by name (which variable, which
  file), not handed on as an empty string.

## 2026-01-19

### Photo Prompt Randomizer - Film Types & Editable Prompt

**Film Type Selector:**
- Dropdown with 14 analog film stocks + random option
- Slide films: Kodachrome, Ektachrome
- Color negative: Portra 400/800, Ektar 100, Fuji Pro 400H/Superia, CineStill 800T
- B&W: Ilford HP5/Delta 400/FP4/Pan F/XP2, Kodak Tri-X 400
- `{film_description}` placeholder in prompt gets replaced by selected film

**Editable System Prompt:**
- System prompt now visible and editable in node UI
- Users can customize prompt generation behavior
- `{film_description}` placeholder for film type injection

**Improved Default Prompt:**
```
You are an inventive creative. Your task is to invent a REALISTIC photographic image prompt.

Think globally. Avoid cultural clichés. Avoid "retro" style descriptions.
Describe contemporary everyday motives: scenes, objects, animals, nature, tech, culture, people, homes, family, work, holiday, urban, rural, trivia, details.

Choose either unlikely, untypical or typical photographical sujets for realistic photographic images. Be verbose, provide intricate details.

Always begin your output with: "{film_description} of".
Transform the prompt strictly following the context if provided.

NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER, STRICTLY FOLLOW THE INSTRUCTION.
```

**UI Cleanup:**
- Removed `debug` field (unnecessary clutter)
- Final inputs: random_seed, film_type, system_prompt, model, unload_model, api_key (opt), context (opt)

---

## 2026-01-18

### Photo Prompt Randomizer Node

**Problem:** ComfyUI executes nodes only when inputs change. Integer nodes can be randomized but don't connect to string inputs.

**Solution:** New node `ai4artsed_photo_prompt_randomizer`:
- INT input `random_seed` for cache-breaking (connected to Integer Randomizer)
- `IS_CHANGED()` returning `float("nan")` forces re-execution
- LLM generates photographic prompts with Kodachrome style

**System Prompt:**
```
You are an inventive creative. Your task is to invent a REALISTIC photographic
image prompt. Choose either unlikely, untypical or typical photographical sujets
for realistic photographic images. Be verbose, provide intricate details.
Always begin your output with: "An Kodachrome film slide of".
Transform the prompt strictly following the context.
NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER, STRICTLY FOLLOW THE INSTRUCTION.
```

**Workflow:**
```
[Integer Randomizer] --INT--> [Photo Prompt Randomizer] --STRING--> [T5-CLIP]
```

### Model List Update

Added new models to both `prompt_interception` and `photo_prompt_randomizer`:

| Model | Price | Tag |
|-------|-------|-----|
| anthropic/claude-sonnet-4.5 | $3.00/$15.00 | multilingual |
| openai/gpt-oss-120b | $0.50/$2.00 | reasoning |
| openai/gpt-oss-20b | $0.10/$0.40 | reasoning |

All existing models retained for backwards compatibility.

### Git SSH Fix

Switched remote from HTTPS to SSH for persistent authentication:
```bash
git remote set-url origin git@github.com:joeriben/ai4artsed_comfyui_nodes.git
```

---

## Earlier Changes

See git log for history:
```bash
git log --oneline
```
