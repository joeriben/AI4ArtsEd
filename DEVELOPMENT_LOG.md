# Development Log

## Session 257 - Canvas Modernization: Pan/Zoom + Output Drawer + Attribution
**Date:** 2026-03-11
**Focus:** Transform Canvas Workflow Builder into a fully interactive workspace with pan/zoom, dedicated output drawer, and model attribution.

### Phase 1: Backend Attribution Pipeline
- `canvas_executor.py`: `_execute_generation()` now saves metadata (config_id, seed, steps, cfg) in node results
- `_execute_collector()` propagates metadata from any source result to collector items (was evaluation-only)
- Frontend types (`canvas.ts`, `CanvasWorkspace.vue`, `StageModule.vue`) extended with `metadata` field on `CollectorOutputItem`

### Phase 2: Pan/Zoom
- `CanvasWorkspace.vue`: New `.canvas-transform-layer` wrapping all children, CSS `transform: translate() scale()`
- `screenToCanvas()` utility converts all mouse coordinates through pan+zoom transform
- Ctrl+Wheel = zoom toward cursor (0.25x–2.0x), Middle-mouse = pan, Plain wheel = scroll
- `fitToContent()` calculates node bounding box, `panToNode(nodeId)` centers on specific node
- New `ZoomControls.vue` component: floating controls with inline SVG icons (+, -, %, fit-to-content)
- `ConnectionLine.vue`: `vector-effect="non-scaling-stroke"` for constant line width during zoom

### Phase 3: Output Drawer
- New `OutputDrawer.vue`: bottom drawer with horizontal card scroll, drag-resize handle
- Each card: node label (clickable → highlight), media preview (image/audio/video/text), config name, seed
- Click-to-highlight: pans canvas to node, 2s pulsing glow animation on StageModule
- Auto-expands when collector output arrives after workflow execution
- `canvas_workflow.vue` layout changed from flat `flex-row` to nested `canvas-and-drawer` column

### Phase 4: Collector Node Simplification
- `StageModule.vue`: Collector node shows "3 items" badge instead of full inline result list
- Output rendering moved entirely to Output Drawer

### Phase 5: Background Fix + Icon Cleanup
- All `#0f172a` → `#0a0a0a`, all `#1e293b` → `#141414` across canvas components
- Toolbar emoji icons (New/Import/Export/Execute/Batch/Abort) replaced with inline SVGs
- `ConfigSelectorModal.vue` backgrounds updated to match

### i18n
- New keys: `canvas.outputDrawer.*` (4 keys), `canvas.zoomControls.*` (4 keys)
- Work order `WO-2026-03-11-canvas-output-drawer-zoom` added

### Type Check
- `npm run type-check` passes clean

---

## Session 256 - Workshop 10.03.2026 Post-Mortem Fixes
**Date:** 2026-03-10
**Focus:** Implement action items from Workshop 10.03.2026 performance report

### Changes

1. **VRAM estimate for SD3.5 Large corrected to 28GB** (was 8GB user-facing, 12GB GPU service)
   - Workshop measured 28,262 MB actual peak — previous estimates were 41-71% too low
   - Updated: `gpu_service/config.py`, `sd35_large.json`, `output_image_sd35_diffusers.py`, `output_image_sd35_large.json`

2. **Gemini content-safety rejections now logged as `[CONTENT-SAFETY]`** (was generic "No image found")
   - `_extract_image_from_chat_completion()` now checks `finish_reason` for `content_filter`/`safety`
   - Text-only responses (model refused but returned explanation) logged with first 200 chars
   - Error message to frontend distinguishes content-safety from generic API failures
   - File: `devserver/schemas/engine/backend_router.py`

3. **ComfyUI logs now have timestamps** (was no timestamps at all)
   - `2_start_comfyui.sh` pipes output through awk to prepend ISO timestamps
   - No modification to third-party ComfyUI code needed

### Workshop Performance Summary
- 107 GPU Service + 42 ComfyUI generations, **0% local failure rate**
- Safety system: 0 false blocks (down from 8.6% on 05.03., 7.7% on 06.03.)
- Only failures: 3x Gemini/OpenRouter (1x 429 rate-limit, 2x content-safety refusal on sensitive topic)

---

## Session 255 - CRITICAL: Kids Safety Filter Bypass — Live Workshop Emergency Fix
**Date:** 2026-03-10
**Focus:** Multiple kids safety bypasses discovered during live workshop. Weapons, 9/11 imagery, and terrorism prompts passed all filters.

### Problems Discovered (in sequence)

1. **EN/DE kids filter missing weapon terms**: TR/KO/UK/FR/ES/HE/AR all had war/weapon category (bomb, gun, rifle, etc.) but EN and DE were never updated. A prompt with "AK-47, RPG-7, bomb placer" passed Stage 1 completely.

2. **Llama-Guard 1B too weak**: The 1B model classified "airplane + skyscraper + collision + debris" (9/11 imagery) as "safe" in 100ms. Upgraded to 8B.

3. **Stage 3 S-code filtering too permissive**: S8 (Indiscriminate Weapons) and S2 (Weapons Crimes) were excluded as "chat-specific". Llama-Guard flagged 9/11 content as S7 (IP) which was also excluded. Added S2 and S8 to blocking set. S5/S6/S7/S12/S13 remain excluded (false positives on harmless images like motorcycles).

4. **Age filter LLM verify prompt too narrow**: Asked "does this describe violence?" — qwen3:1.7b classified "planning an attack" as SAFE because planning ≠ describing. Broadened to "describes, plans, threatens, or glorifies".

5. **qwen3:1.7b fundamentally too weak for kids context verification**: Even with improved prompt, "Terroranschlag auf ein Hochhaus" passed. Model recognizes threat but says SAFE.

6. **VLM max_new_tokens too low**: qwen3-vl:2b thinking mode consumed all 500 tokens for reasoning, never reached SAFE/UNSAFE verdict → fail-open passed unchecked images.

### Architecture Change: DSGVO-First Ordering

**Old**: §86a → Age Filter → DSGVO NER
**New**: §86a → DSGVO NER → Age Filter

**Why**: Moving DSGVO NER before the age filter guarantees no personal data in the text. This allows the kids age-filter to safely use **external gpt-oss-120b** (IONOS EU datacenter) for context verification instead of the weak local qwen3:1.7b.

**Result**: gpt-oss-120b correctly blocks "Araber plant Anschlag" (UNSAFE) while allowing "cute vampire at party" (SAFE). Best of both worlds.

### Reasoning Model Integration

gpt-oss-120b is a reasoning model:
- Response in `reasoning` field, NOT `content` (which is `null`)
- Needs `max_tokens: 2048` (not 50) — thinking tokens count
- Parse: `msg.get("content") or msg.get("reasoning")`

### Final Safety Architecture (Kids, 3 Layers × 3 LLMs)

| Layer | Check | Model | Location |
|-------|-------|-------|----------|
| **Stage 1** | Fast-filter keywords + LLM context verify | gpt-oss-120b (IONOS) | Pre-interception |
| **Stage 3** | S-code classification (S1-S4,S8-S11) | llama-guard3:8b (Ollama) | Pre-generation |
| **Post-Gen** | Visual image analysis | qwen3-vl:2b (Ollama) | Post-generation |

Independent concerns (always active): §86a (llama-guard3:8b), DSGVO NER (SpaCy + qwen3:1.7b)

### Commits
| Commit | Change |
|--------|--------|
| `13a21dd` | Add missing weapon/war terms to EN+DE kids filter |
| `e30ea7e` | Upgrade Llama-Guard 1B → 8B |
| `e071002` | Kids zero-tolerance on Stage 3 + terrorism terms EN/DE |
| `c52e276` | Broaden age-filter LLM prompt (plan/threaten/glorify) |
| `6d3bce2` | Kids fast-filter: skip LLM verify (temporary) |
| `6dd3850` | Revert Stage 3 zero-tolerance, add S2+S8 to blocking set |
| `8957798` | DSGVO before age filter + gpt-oss-120b for kids verify |
| `c920299` | VLM max_new_tokens 500→1000 |
| `23bf245` | Handle gpt-oss-120b reasoning model response format |

### Files Changed
| File | Change |
|------|--------|
| `devserver/schemas/youth_kids_safety_filters.json` | Added weapon + terrorism terms for EN/DE |
| `devserver/config.py` | SAFETY_MODEL: llama-guard3:1b → 8b |
| `devserver/schemas/engine/stage_orchestrator.py` | DSGVO-first ordering, gpt-oss-120b for kids, S-code set, prompt improvements |
| `devserver/my_app/routes/schema_pipeline_routes.py` | DSGVO-first ordering in unified-streaming + /safety/quick |
| `devserver/my_app/utils/vlm_safety.py` | max_new_tokens: 1000 |

### Lessons Learned
- **Never assume filter lists are consistent across languages** — EN/DE were originals, translations got expanded weapon category, originals never updated
- **Small guard models (1B) cannot do semantic reasoning** — word-level classification only
- **Small general-purpose models (1.7B) cannot judge age-appropriateness** — too literal, misses intent
- **Reasoning models put answers in different fields** — check `reasoning`, not just `content`
- **DSGVO-first ordering enables external LLM use** — architectural insight, not just a swap

---

## Session 254 - VLM Safety: Fail-Open → Fail-Closed + Thinking-Loop Fix
**Date:** 2026-03-10
**Focus:** Fix critical VLM safety flaws — fail-open design + qwen3-vl infinite reasoning loops

### Problem 1: Fail-Open Design
Session 253's Fix 4 (commit `6a1d824`, Claude Sonnet 4.6) introduced a regression:
- Reduced `max_new_tokens` from 500 to 50 (model cut off mid-thinking, never reaches verdict)
- Added `/no_think` prompt directive (model ignores it)
- Added "no clear verdict → fail-open" code path

Result: model burns 50 tokens thinking ("...the content is a bird"), never says SAFE/UNSAFE, fail-open → all images pass unchecked.

### Problem 2: Infinite Reasoning Loops
qwen3-vl:2b enters endless deliberation in thinking mode ("is it inappropriate? Let's think... But is it inappropriate? Let's see..."). `/no_think` as prompt text has no effect. Even with 1000 tokens, the model never reaches a conclusion — it just loops.

### Root Cause
`/no_think` is a prompt-level hack. The correct way to disable thinking in Ollama is the API-level parameter `think: false` in the request payload. The `LLMClient` already supported `enable_thinking=False` (sets `payload["think"] = False`), but VLM safety never used it.

### Fixes
**File:** `devserver/my_app/utils/vlm_safety.py` + `devserver/my_app/services/llm_client.py`

1. **Fail-closed everywhere** — no fail-open for ANY failure mode. Kindersicherheit kennt kein fail-open.
2. **`enable_thinking=False`** — uses Ollama API `think: false`, not prompt hack. Model responds with verdict in `content` field directly.
3. **Prompt simplified** — "Is this image safe for children age 6-12? Answer with one word only: SAFE or UNSAFE." No "explain briefly" that invites deliberation.
4. **Robust `_extract_verdict()`** — checks first word, last word, then scans full text for standalone 'unsafe'/'safe' as fallback.
5. **Description = thinking** — `thinking or content` (not `content or thinking`) so Trashy gets the VLM's image analysis, not just "UNSAFE".
6. **Removed `/no_think`** and **removed `max_new_tokens`** — neither needed with `think: false`.

### Result
- VLM responds in ~380ms with clear verdict in `content` field
- Thinking still happens internally but doesn't block the verdict
- Unsafe images (car crash, violence) correctly blocked for kids
- Safe images pass without loops

### Design Principle
Kindersicherheit kennt kein fail-open. If the safety system cannot confirm an image is safe — for any reason — the image does not pass.

### Files Changed
| File | Change |
|------|--------|
| `devserver/my_app/utils/vlm_safety.py` | Rewrite: fail-closed, enable_thinking=False, robust parsing, direct prompt |
| `devserver/my_app/services/llm_client.py` | Debug log for thinking suppression |

---

## Session 253 - Workshop Optimization: Retry, Concurrency, NER, VLM Safety
**Date:** 2026-03-07
**Focus:** Implement 3 workshop optimizations from 06.03 performance report + fix VLM safety verdict parsing

### Background
Workshop 06.03.2026 performance report identified 3 medium-severity issues after all critical bugs from 05.03 were resolved. This session implements fixes and validates them using a full 119-request workshop replay.

### Fixes Implemented

#### Fix 1: Cloud-API Retry with Exponential Backoff
**Problem**: 10 consecutive Mistral 503 errors in 74 seconds, all Stage-2 interceptions lost.
**Root Cause**: No retry on transient HTTP errors. Affected ALL cloud-API backends.

**Solution**: `_requests_post_with_retry()` helper with exponential backoff (1s/2s/4s + jitter) on 429/502/503/504. Applied to:
- `prompt_interception_engine.py` — 5 non-streaming + 1 streaming `requests.post()` calls
- `chat_routes.py` — 3 chat helper methods

Plus DSGVO-safe provider fallback: if primary cloud provider fails after all retries, automatically tries the next available DSGVO-safe provider (configurable via `DSGVO_ONLY_FALLBACK` toggle in config.py).

**Result**: 0% Mistral 503 in all replay runs (was 5.6%).

#### Fix 2: Ollama Concurrency Increase
**Problem**: 11 timeouts during peak (17:00-17:14), 8 failures in 3 seconds.
**Root Cause**: `OLLAMA_MAX_CONCURRENT = 3` too low for 9 iPads.

**Solution**: Raised to 6, made configurable via `config.py` / env var.

**Result**: 0% Ollama timeouts in all replay runs (was 7%).

#### Fix 3: DSGVO NER Numeric Pre-Filter
**Problem**: SpaCy NER flagging SD weight syntax ("shadow gradient:1.2") and similar as person names. LLM-Verify corrected but cost 1-4s per false positive.
**Root Cause**: POS-tag filter insufficient for numeric/technical entities.

**Solution**: Added numeric filter in `stage_orchestrator.py:fast_dsgvo_check()` — entities containing digits are rejected before LLM-Verify. Real person names never contain digits.

**Result**: Eliminates unnecessary LLM-Verify calls for SD-syntax and numeric entities.

#### Fix 4: VLM Safety Verdict Parsing (found during testing)
**Problem**: VLM post-generation check (qwen3-vl:2b) caused 12% false blocks. Two bugs:
1. `/no_think` directive ignored by qwen3-vl:2b — model still uses thinking mode
2. Substring check `'unsafe' in combined` matched reasoning text like "there's nothing unsafe" — false positive

**Solution**: Check only the **last word** of model response (where the verdict lands after reasoning). Fail-open if no clear verdict. Restored `max_new_tokens=500` since thinking can't be disabled.

**Result**: 0% VLM false blocks (was 12%).

#### Fix 5: ComfyUI Queue Depth Tuning
**Problem**: Original depth 8 caused queue-full rejections during bursts.
**Progression**: 8 -> 16 (eliminated queue-full but caused 480s execution timeouts) -> 10 (balanced).
**UX Decision**: Shallow queue with fast "busy" feedback (existing `generationError.busy` i18n) is better UX than deep queue with silent 10-minute waits followed by timeout.

### Config Changes (config.py)
```python
DSGVO_ONLY_FALLBACK = True/False  # NEW: DSGVO-safe-only provider fallback toggle
DSGVO_SAFE_PROVIDERS = [...]      # NEW: ordered provider preference list
ALL_CLOUD_PROVIDERS = [...]       # NEW: all providers for international deployments
OLLAMA_MAX_CONCURRENT = 6         # Changed: was 3
COMFYUI_MAX_QUEUE_DEPTH = 10      # Changed: was 8
```

### TODO Added
HIGH priority: Provider-agnostic API registry refactor — replace brand-specific `_call_mistral()`, `_call_ollama()` etc. with generic `_call_cloud_api()` + provider registry. Added to `docs/devserver_todos.md`.

### Workshop Replay Validation

Full chronological progress report with all data points (Workshop 05.03, Simulation 05.03, Workshop 06.03, Simulation 06.03 runs):
**`docs/technical_reports/2026-03-08_workshop_optimization_progress.md`**

Final result: **78% success (93/119)** — all 3 targeted software bugs at 0%, remaining failures are GPU throughput limits with proper UX feedback.

### Files Changed
| File | Change |
|------|--------|
| `devserver/schemas/engine/prompt_interception_engine.py` | Retry helper + 6x `requests.post` replaced + provider fallback |
| `devserver/my_app/routes/chat_routes.py` | Retry helper + 3x `requests.post` replaced |
| `devserver/config.py` | DSGVO fallback config, OLLAMA_MAX_CONCURRENT=6, COMFYUI_MAX_QUEUE_DEPTH=10 |
| `devserver/my_app/routes/schema_pipeline_routes.py` | Import OLLAMA_MAX_CONCURRENT from config |
| `devserver/schemas/engine/stage_orchestrator.py` | Numeric filter in fast_dsgvo_check() |
| `devserver/my_app/utils/vlm_safety.py` | Last-word verdict parsing, /no_think prompt, token budget |
| `devserver/testfiles/simulate_workshop_260306.py` | NEW: 119-entry workshop replay script |
| `docs/devserver_todos.md` | HIGH: provider-agnostic API registry TODO |

### Key Decisions
- **Queue depth 10 (not 16)**: Fast "busy" feedback > silent long waits. Frontend already has i18n error display.
- **VLM verdict = last word**: Model reasons toward conclusion. Substring search in reasoning causes false positives from negations like "nothing unsafe".
- **Brand-specific methods untouched this session**: Existing `_call_mistral()` etc. stay as-is. HIGH-prio TODO for provider-registry refactor added.
- **`/no_think` kept in prompt despite being ignored**: No harm, may work in future qwen3-vl versions.

### Commits
- `d19be5b` — feat: cloud-API retry, Ollama concurrency, DSGVO NER filter, provider fallback
- `175e5ef` — feat: raise ComfyUI queue depth 8->16 + add 06.03 workshop replay script
- `6a1d824` — fix: VLM safety thinking overflow + qwen_2511_multi test params
- `8594905` — fix: VLM safety verdict parsing — use last word, not substring match
- `b538feb` — tune: ComfyUI queue depth 16->10 for better UX

---

## Session 248 - Unified GenerationButton Component + Error Display
**Date:** 2026-03-05
**Focus:** Extract shared GenerationButton component, fix double-submit bug, add i18n error messages

### Problem
Workshop scenario audit (9 iPads, single GPU) revealed:
1. **Double-submit bug**: `text_transformation.vue` Stage 4 button missing `isPipelineExecuting` guard
2. **Inconsistent button states**: 6 views with copy-pasted CSS (5 gold/black, 2 purple gradient)
3. **Blur-safety race condition**: `checkSafety()` on blur disables button mid-click, swallowing the tap
4. **Silent errors**: Backend errors (queue full, service down) either swallowed or shown via `alert()`
5. **~400 lines duplicate CSS** across view files

### Solution

**Step 0 (separate commit):** Fixed double-submit by adding `|| isPipelineExecuting` to Stage 4 button guards.

**GenerationButton.vue component** with:
- Props: `disabled`, `executing`, `checkingSafety`, `label`, `checkingLabel`, `executingLabel`, `showArrows`, `errorMessage`
- Click-queuing: If user clicks during safety check, intent is queued and fires when check completes
- Slots: `before` (for batch controls), default (for SafetyBadges/LoRA badges)
- Three visual states: disabled (gray), checking-safety (pulse), executing (gold pulse)

**generation-button.css**: Canonical gold/black styling extracted from text_transformation.css. References existing `@keyframes` from animations.css. Adds `executing` pulse and `error-flash` states.

**Error type classification** in `useGenerationStream.ts`:
- `classifyError()` pattern-matches backend messages: `queue full` -> `busy`, `not available` -> `offline`, default -> `unknown`
- `GenerationResult.errorType` field added
- Views map errorType to i18n keys (`generationError.busy/offline/unknown`)

**Surrealizer cleanup**: All `alert()` calls replaced with `generationErrorMessage` ref displayed in GenerationButton.

### Files Changed
| File | Change |
|------|--------|
| `src/components/GenerationButton.vue` | NEW - shared component |
| `src/assets/generation-button.css` | NEW - canonical button CSS |
| `src/composables/useGenerationStream.ts` | Error type classification |
| `src/i18n/en.ts` | 7 new keys (common.start, common.generating, generationError.*, surrealizer.executeButton/executingButton) |
| `src/i18n/WORK_ORDERS.md` | Translation work order |
| `src/views/text_transformation.vue` | Both buttons migrated + error handling |
| `src/views/text_transformation.css` | ~93 lines button CSS removed |
| `src/views/image_transformation.vue` | Button migrated, ~100 lines CSS removed |
| `src/views/multi_image_transformation.vue` | Button migrated, ~100 lines CSS removed |
| `src/views/music_generation.vue` | Both buttons migrated, ~93 lines CSS removed |
| `src/views/music_generation_v2.vue` | Button migrated, purple gradient removed |
| `src/views/surrealizer.vue` | Button migrated, purple gradient + alert() removed |

### Key Decisions
- **All gold/black, no variant prop** — surrealizer + music_v2 adopt standard styling
- **Error messages via i18n** — respects whatever language the user has set, not hardcoded
- **Each view keeps its own canStart/isExecuting logic** — component is visual+interaction, not state owner
- **Specialist views (split_and_combine, partial_elimination, direct) not migrated** — out of audit scope

### Net Effect
- **-596 lines, +417 lines** (net -179 lines)
- 10 buttons across 6 views unified by construction
- Double-submit impossible (executing state disables button)
- Blur-safety race condition solved via click-queuing
- Backend errors visible to users in their language

**Duration:** ~45 minutes

## Session 247 - Wan 2.2 T2V Fast: Fix media_type Detection + 10s Video + MoE Cleanup
**Date:** 2026-03-05
**Focus:** Fix video detection, VLM safety check, and frontend rendering for Wan 2.2 T2V Fast config

### Problem
The new `wan22_t2v_fast` config (from Session 246) generated video successfully, but:
1. **Media type detected as "image"** — backend uses `'video' in output_config.lower()` at 3+ locations, but config name didn't contain "video"
2. **VLM safety check failed** — tried to open .mp4 as image (fail-open, no block but error in logs)
3. **Frontend rendered `<img>` instead of `<video>`** — wrong media_type in SSE events

### Solution
**Config rename**: `wan22_t2v_fast` → `wan22_t2v_video_fast` (follows existing pattern: `ltx_video`, `wan22_i2v_video`)

**Files changed:**
- `devserver/schemas/configs/output/wan22_t2v_fast.json` → renamed to `wan22_t2v_video_fast.json`
- `devserver/schemas/chunks/output_video_wan22_t2v_fast.json` — frames 81→161 (10s at 16fps), optimization instruction updated
- `public/ai4artsed-frontend/src/views/text_transformation.vue` — config ID updated in 3 places (bubble, chunk mapping, display names)
- `public/ai4artsed-frontend/src/views/image_transformation.vue` — removed dead `wan22_i2v_diffusers` MoE entry (leftover from Session 246)
- `public/ai4artsed-frontend/src/views/multi_image_transformation.vue` — same MoE cleanup

### Key Detail: Chunk Mapping
The `configIdToChunkName` mapping maps config IDs to chunk base names (after stripping `output_video_` prefix). The chunk file stays `output_video_wan22_t2v_fast.json`, so the mapping is:
- Config ID `wan22_t2v_video_fast` → chunk base name `wan22_t2v_fast` ✓

### Performance
Wan 2.2 14B FP8 + LightX2V 4-step: **5s video in ~5.6s inference** → bumped to 10s video (~161 frames), expected ~11s inference.

### Verified
- Backend picks up renamed config
- `media_type: 'video'` correctly detected
- VLM safety check skips (video type)
- Frontend renders `<video>` player

**Duration:** ~20 minutes

## Session 245 - Cross-Process ComfyUI Eviction in VRAMCoordinator
**Date:** 2026-03-03
**Focus:** Enable GPU service to ask ComfyUI to release VRAM as a last-resort eviction step

### Problem
The NVML watchdog (Session 244) gives VRAMCoordinator real GPU visibility — it sees that ComfyUI holds 18+ GB VRAM (e.g. loaded Wan 2.1). But it cannot ask ComfyUI to release that memory. In a workshop with 10 concurrent users, if internal eviction isn't enough, the result is OOM or failure.

### Solution
Added `_try_comfyui_eviction()` to `VRAMCoordinator` — calls ComfyUI's existing `POST /free {"unload_models": true, "free_memory": true}` endpoint as a last resort after internal backend eviction fails.

**Design:**
- **Last resort only**: Called only when internal eviction didn't free enough VRAM
- **NVML-verified**: Measures actual VRAM delta via NVML (polls up to 5s for async GC/CUDA release)
- **Fail-open**: ComfyUI unreachable → skip, return 0. Never blocks eviction
- **All-or-nothing**: ComfyUI API only supports "unload everything" — no selective model unload
- **Asymmetric**: GPU service can evict ComfyUI, not vice versa (coordinator is authority)

### Verified
Tested with ComfyUI holding Wan 2.2 (~22 GB). `POST /free → 200` successfully evicted all models. ComfyUI dropped from 22,404 MB to 836 MB (bare CUDA context). NVML 5s polling window didn't catch the release (CUDA memory return was slower), but free VRAM confirmed on next query (+21.5 GB). In production this is fine — the subsequent model load (10-15s) gives CUDA plenty of time to return memory.

### Files Changed
- `gpu_service/services/vram_coordinator.py` — `_try_comfyui_eviction()` + `_do_eviction()` integration
- `gpu_service/tests/test_comfyui_eviction.py` — manual test script

**Duration:** ~30 minutes

## Session 244 - Fix Stage 3 Safety: Remove Redundant Double-Check + Fix Wrong Prompt Format
**Date:** 2026-03-03
**Focus:** Three bugs in `execute_stage3_safety()` that caused a culturally rich Lagos scene to be false-positive blocked as S4 (Violent Crimes)

### Problem
Stage 3 had two sequential Llama-Guard calls that could disagree:
1. **STEP 3b**: Age fast-filter → `llm_verify_age_filter_context()` with proper S1-S13 template on original text
2. **STEP 4**: Pipeline-based `safety_check_kids/youth` chunk with **wrong prompt format** (free-form question forced onto `llama-guard3:1b`, a guard model trained on structured S1-S13 categories)

The guard model classified the meta-prompt ("Is this appropriate for children ages 6-12?") against its S-categories → biased toward false positives. Additionally, STEP 3b was redundant — MediaInputBox `/safety/quick` already runs the age fast-filter on raw user input (Stage 1).

Third bug: `parse_llamaguard_output()` didn't recognize bare S-codes (e.g. "S8" without "unsafe" prefix).

### Solution
- **Removed STEP 3b** (age fast-filter in Stage 3) — redundant with Stage 1
- **Removed old STEP 4** (pipeline-based check with wrong prompt format)
- **Added `_llm_safety_check_generation()`**: Single unconditional Llama-Guard call with proper S1-S13 template (same as Stage 1), fail-closed
- **Fixed `parse_llamaguard_output()`**: Bare S-codes now recognized before fallback

New flow: STEP 1 (skip adult/research) → STEP 2 (translate) → STEP 3 (§86a) → STEP 4 (determine generation prompt) → STEP 5 (single Llama-Guard with proper template)

### Files Changed
- `devserver/schemas/engine/stage_orchestrator.py` — all changes in one file

### Dead Code (not removed, cleanup later)
- `safety_check_kids.json`, `safety_check_youth.json` (chunks) — no longer called from Stage 3
- `pre_output/safety_check_kids.json`, `pre_output/safety_check_youth.json` (configs) — no longer called
- `safety_check.json` (pipeline) — no longer called
- `/pipeline/safety` endpoint (check_type='output') — dead code, no frontend callers

### Testing Insight: Complementary Safety Roles
Testing revealed that Llama-Guard S1-S13 classifies "A child is being attacked by a monster" as `safe` — because S1 (Violent Crimes) covers content that "enables, encourages, or excuses" **crimes**, and a fantasy monster attack isn't a crime. Both `llama-guard3:1b` and `llama-guard3:8b` agree.

The age fast-filter in `/safety/quick` catches this (keywords "monster", "verletzen"). This confirms Stage 1 and Stage 3 have **complementary, not redundant** roles:
- **SAFETY-QUICK + Stage 1**: Age-inappropriate but legal content (Jugendschutz)
- **Stage 3 Llama-Guard**: Criminal/harmful S1-S13 categories

### Follow-up Fix: Pre-Generation Safety Gate
Discovered that editing the optimized prompt box and clicking "Generate" without blurring could bypass MediaInputBox's blur/paste safety check. Added synchronous `/safety/quick` call in `startGeneration()` before Stage 3-4 execution.

### Additional Files Changed
- `public/ai4artsed-frontend/src/views/text_transformation.vue` — pre-generation `/safety/quick` gate

**Duration:** ~60 minutes

## Session 243 - Rename llama_guard_explanations.json → safety_code_explanations.json
**Date:** 2026-03-03
**Focus:** Remove vendor-specific naming from model-agnostic safety taxonomy file

### Change
The S1–S13 safety code explanations are a general classification scheme, not Llama Guard–specific. Renamed the file and updated the single code reference.

### Files Changed
- `devserver/schemas/llama_guard_explanations.json` → `devserver/schemas/safety_code_explanations.json` (git mv)
- `devserver/schemas/engine/stage_orchestrator.py` — updated path + docstring in `build_safety_message()`

**Duration:** ~5 minutes

## Session 242 - Fix Ollama GPU Offloading (VLM Safety on CPU)
**Date:** 2026-03-03
**Focus:** All Ollama models (including VLM safety check) running on CPU instead of GPU

### Problem
VLM safety check (`qwen3-vl:2b`) ran on CPU despite ~16 GB free VRAM on 96 GB RTX 6000. `ollama ps` showed `vram=0.0GB`, Ollama logs confirmed `device=CPU` for all compute.

### Root Cause
`OLLAMA_NUM_GPU=1` in systemd override (`/etc/systemd/system/ollama.service.d/override.conf`). This parameter controls the **number of GPU layers** to offload, NOT the number of GPUs. `1` = only 1 layer on GPU, rest on CPU — effectively CPU-only.

Same misconfiguration existed in `docs/installation/PC2_INSTALLATION.md`.

### Fix
- **Systemd override**: `OLLAMA_NUM_GPU=1` → `OLLAMA_NUM_GPU=-1` (auto-detect, all layers on GPU)
- **`OLLAMA_MAX_LOADED_MODELS`**: `1` → `4` (concurrent safety models: DSGVO, VLM, guard, etc.)
- **Installation docs**: Updated `PC2_INSTALLATION.md` to match

### Files Changed
- `docs/installation/PC2_INSTALLATION.md` — fixed `OLLAMA_NUM_GPU` value

**Duration:** ~30 minutes

## Session 241 - Flux 2 Visual Conditioning via Diffusers (img2img)
**Date:** 2026-03-03
**Focus:** Add native Flux 2 visual conditioning path through the Diffusers GPU service

### Context
The existing `flux2_img2img` (ComfyUI) uses traditional img2img: VAE-encode → noise at 55% → denoise. This **reproduces** the input image with minor variations — not what users expect from an image transformation tool.

**Discovery**: `Flux2Pipeline` natively supports an `image=` parameter for **visual conditioning** — the reference image is VAE-encoded and appended as extra attention tokens in the transformer. Generation starts from pure noise but the model "sees" the reference. Combined with the text prompt, this produces genuinely creative transformations.

### Architecture
- No new endpoint needed — `image_base64` flows through the existing `generate_image` chain
- GPU backend: decodes image bytes → PIL → passes `image=pil_image` to Flux2Pipeline's `gen_kwargs`
- Route layer: `image_base64` (base64 string) → `image_bytes` (raw bytes) conversion
- DiffusersClient: forwards `image_base64` kwarg in HTTP payload
- New chunk follows the `output_image_flux2_diffusers.py` pattern, with image input like `output_video_wan22_i2v_diffusers.py`

### Changes
| File | Change |
|------|--------|
| `gpu_service/services/diffusers_backend.py` | Add Flux2 visual conditioning in `_generate()`: `image=` kwarg when `Flux2Pipeline` + `image_bytes` |
| `gpu_service/routes/diffusers_routes.py` | Decode `image_base64` → `image_bytes` in `/api/diffusers/generate` |
| `devserver/my_app/services/diffusers_client.py` | Forward `image_base64` kwarg in `generate_image()` payload |
| `devserver/schemas/chunks/output_image_flux2_img2img_diffusers.py` | **NEW** — chunk accepting `input_image` (path) or `image_base64` |
| `devserver/schemas/configs/output/flux2_img2img_diffusers.json` | **NEW** — output config with `img2img: true`, `backend_type: diffusers` |
| `public/.../image_transformation.vue` | Add Flux2 Diffusers tile to `configsByCategory.image[]` |
| `public/.../multi_image_transformation.vue` | Add Flux2 Diffusers tile to `configsByCategory.image[]` |

### Key Design Decisions
- **Reuse existing endpoint**: No new `/api/diffusers/generate/img2img` — the `image_base64` kwarg is optional on the standard generate path, keeping the API surface minimal.
- **image_base64 vs image_bytes naming**: Route layer converts base64→bytes (naming shift reflects the encoding change), backend receives raw bytes and creates PIL Image.
- **Chunk accepts both path and base64**: Like Wan I2V chunk — supports both pipeline executor (disk path) and direct API calls (base64).

### Commit
- `50004c2` feat: Flux 2 visual conditioning via Diffusers (img2img)

### Type-check
Pre-existing error: `bg.ts` module missing (incomplete Bulgarian language addition). No errors from this session's changes.

---

## Session 240 - Fix VRAM Eviction on Model Switch (3 Cascading Bugs)
**Date:** 2026-03-03
**Focus:** GPU service VRAM coordinator fails to evict models when switching between diffusers models (e.g. Flux2 → SD 3.5)

### Root Cause
Three cascading bugs in the eviction chain:

1. **Priority filter too strict** (`vram_coordinator.py:231`): Used `<` instead of `<=`, so NORMAL-priority models could never evict other NORMAL-priority models. Since all diffusers/text models register as NORMAL, cross-model eviction never happened. In-use models are already protected (elevated to HIGH priority), so `<=` is safe.

2. **`float('inf')` makes success always False** (`diffusers_backend.py:437`): Cold loads pass `required_mb=float('inf')`. The coordinator's `free_mb >= inf` check is mathematically always False, even after successful eviction.

3. **Eviction failure silently ignored** (`diffusers_backend.py:383`): `request_vram()` return value was discarded. Load proceeded regardless of eviction outcome.

**Secondary**: Missing `gc.collect()` before `torch.cuda.empty_cache()`. PyTorch pipelines have circular references — without GC, `del pipeline` doesn't immediately free GPU memory.

### Changes
| File | Change |
|------|--------|
| `gpu_service/services/vram_coordinator.py` | `<` → `<=` in priority filter; handle `float('inf')` as "evict all, succeed if freed anything"; `gc.collect()` before `empty_cache()` |
| `gpu_service/services/diffusers_backend.py` | Log warning on eviction failure; `gc.collect()` before `empty_cache()` in `_unload_model_sync()` |
| `gpu_service/services/text_backend.py` | `gc.collect()` before `empty_cache()` in `_unload_model_sync()` (consistency) |

### Verification
1. Start GPU service → generate with Flux2 (~37GB with cpu_offload)
2. Switch to SD 3.5 Large
3. Expected: logs show `[VRAM-COORD] Evicting diffusers/...` → successful load

### Commit
- `83299f5` fix(gpu): fix VRAM eviction failing on model switch (3 cascading bugs)

---

## Session 239 - Wan 2.2 A14B MoE: T2V + I2V via Diffusers
**Date:** 2026-03-03
**Focus:** Upgrade video generation from Wan 2.2 TI2V-5B to A14B MoE (27B total), add Image-to-Video

### Context
Wan 2.2 5B (TI2V) was already implemented. The A14B MoE models offer significantly better quality: 27B total params (2x 14B experts, only 14B active per step). With FP8 quantization both transformer experts fit in ~14GB VRAM. This session upgrades T2V and adds I2V as a new capability.

### Architecture: MoE Dual Transformer
- **T2V-A14B**: `transformer` + `transformer_2` (boundary_ratio=0.875)
- **I2V-A14B**: `transformer` + `transformer_2` (boundary_ratio=0.9)
- **Text Encoder**: UMT5EncoderModel (~4.7B)
- **VAE**: AutoencoderKLWan (MUST be float32)
- **New parameter**: `guidance_scale_2=3.0` (second guidance scale for MoE)

### Changes
| File | Change |
|------|--------|
| `gpu_service/config.py` | +`DIFFUSERS_WAN22_QUANTIZE` (bf16 default, fp8 optional) |
| `gpu_service/services/diffusers_backend.py` | New `_load_wan_pipeline()` with component-level loading, FP8/BF16 quantization, auto-detect dual transformer. `WanImageToVideoPipeline` registered. New `generate_video_from_image()`. `guidance_scale_2` on `generate_video()` |
| `gpu_service/routes/diffusers_routes.py` | `guidance_scale_2` passthrough on T2V, new `/api/diffusers/generate/video/i2v` endpoint, fixed defaults (40 steps, 4.0 cfg) |
| `devserver/my_app/services/diffusers_client.py` | `guidance_scale_2` on `generate_video()`, new `generate_video_from_image()` |
| `devserver/schemas/chunks/output_video_wan22_diffusers.py` | Updated to T2V-A14B: model_id, guidance_scale_2, defaults |
| `devserver/schemas/chunks/output_video_wan22_i2v_diffusers.py` | **NEW** — I2V chunk accepting `image_base64` |
| `devserver/schemas/configs/output/wan22_t2v_diffusers.json` | Updated model, params, MoE info, `videocam` icon |
| `devserver/schemas/configs/output/wan22_i2v_diffusers.json` | **NEW** — I2V config with boundary_ratio=0.9 |
| `public/.../text_transformation.vue` | Updated T2V tile, added I2V tile + mapping + model name |

### Key Design Decisions
- **`_load_wan_pipeline()`** follows the Flux 2 pattern: component-level loading instead of `from_pretrained()`. This enables per-component quantization (FP8 transformers, INT8 text encoder, FP32 VAE).
- **Auto-detect dual transformer**: Downloads `model_index.json` from HuggingFace to check for `transformer_2`. Falls back to heuristic (`A14B` in model_id).
- **Shared method for T2V + I2V**: `_load_wan_pipeline()` accepts `pipeline_class_str` parameter, works for both `WanPipeline` and `WanImageToVideoPipeline`.
- **I2V image handling**: Route decodes base64 → bytes, backend converts to PIL Image with RGB normalization and LANCZOS resize to target dimensions.

### VRAM Estimates
| Mode | VRAM |
|------|------|
| BF16 (default) | ~40GB |
| FP8 (`DIFFUSERS_WAN22_QUANTIZE=fp8`) | ~14GB |

### Stats
- 9 files changed, +624/-66 lines
- 2 new files (I2V chunk + config)

### Still Open
- I2V frontend: Currently a tile in text_transformation.vue — needs UX for image upload (file picker or use previous generation result)
- PoC testing pending (model download required)

### Commit
- `0b12380` feat: Wan 2.2 A14B MoE — T2V + I2V via Diffusers

---

## Session 238 - SwarmUI Removal + ComfyUI Standalone (Port 17804)
**Date:** 2026-03-03
**Focus:** Complete removal of SwarmUI middleware, standalone ComfyUI on dedicated port

### Context
ComfyUI had been running standalone for a while (`dlbackend/ComfyUI/`, started via `2_start_comfyui.sh`), but the codebase still contained the full SwarmUI integration: legacy code paths behind `COMFYUI_DIRECT` flags, dead service files, SwarmUI-era port 7821, and outdated documentation.

### Changes
| File | Change |
|------|--------|
| `devserver/my_app/services/swarmui_manager.py` | **DELETED** (248 lines) |
| `devserver/my_app/services/swarmui_client.py` | **DELETED** (464 lines) |
| `devserver/my_app/services/comfyui_client.py` | **DELETED** (390 lines, deprecated) |
| `devserver/schemas/engine/backend_router.py` | Removed all `COMFYUI_DIRECT` guards + SwarmUI legacy paths (~500 lines) |
| `devserver/config.py` | Removed `SWARMUI_API_PORT`, `COMFYUI_DIRECT`, `USE_SWARMUI_ORCHESTRATION`, `ALLOW_DIRECT_COMFYUI`, `SWARMUI_BASE_PATH`, legacy aliases. Port 7821 → 17804 |
| `devserver/my_app/services/comfyui_manager.py` | Removed SwarmUI fallback imports, cleaned startup script resolution |
| `devserver/my_app/services/legacy_workflow_service.py` | Removed SwarmUI routing logic, now uses ComfyUI directly |
| `devserver/my_app/services/pipeline_recorder.py` | Removed `download_and_save_from_swarmui()`, fixed import to `comfyui_ws_client` |
| `devserver/my_app/services/model_path_resolver.py` | Removed SwarmUI model path resolution |
| `devserver/my_app/services/workflow_logic_service.py` | Removed `SWARMUI_BASE_PATH` import |
| `devserver/my_app/routes/schema_pipeline_routes.py` | Removed `swarmui_generated` handler branches |
| `devserver/my_app/routes/training_routes.py` | ComfyUI `/free` now uses config port |
| `devserver/my_app/services/training_service.py` | Removed `SWARMUI_BASE_PATH` import, config-based ComfyUI port |
| `devserver/schemas/engine/pipeline_executor.py` | Removed `swarmui_available` from metadata keys |
| `devserver/config/backends.json` | ComfyUI: removed `api_port: 7801`, updated to port 17804 |
| `2_start_comfyui.sh` | Port 7821 → 17804 |
| `check_prerequisites.sh` | Port list: `(7801 7821 11434 17801)` → `(11434 17801 17804)` |
| `gpu_service/config.py` | `LORA_DIR` path: SwarmUI → ComfyUI |
| `docs/ARCHITECTURE PART 24` | **Rewritten**: "SwarmUI Integration" → "ComfyUI Integration" |
| `docs/PORT_ARCHITECTURE_DECISION.md` | Rewritten with current port schema |
| `public/.../en.ts` | `'ComfyUI / SwarmUI'` → `'ComfyUI'` |
| `public/.../WORK_ORDERS.md` | Added WO for 8 target languages |

### Port Schema (final)
| Port | Service |
|------|---------|
| 17801 | DevServer (prod) |
| 17802 | DevServer (dev) |
| 17803 | GPU Service |
| 17804 | ComfyUI |
| 11434 | Ollama |

### Stats
- 30 files changed, +368/-2574 lines
- ~2200 lines dead code removed
- Zero remaining SwarmUI/7821 references in Python code

### Still Open
- `transfer_models.sh` still references SwarmUI paths (deployment script, separate task)
- `update.sh` references `ai4artsed-swarmui.service` (systemd, separate task)

### Commit
- `2b2449f` refactor: remove SwarmUI, standalone ComfyUI on port 17804

---

## Session 237 - TensorRT Reset + Flux 2 FP8 Clean Implementation
**Date:** 2026-03-03
**Focus:** Revert broken TensorRT session, re-implement Flux 2 FP8 cleanly

### Problem
Session had fundamentally restructured `diffusers_backend.py` (composite cache keys, FP8/NF4 loading paths, torch.compile) breaking the working Diffusers system. 7 unpushed commits + uncommitted changes.

### Solution
1. Hard reset to `origin/develop`, preserving only the ComfyUI-failure-bugfix (commit `4f23f6d` → re-applied as `bcb3b70`)
2. Clean Flux 2 FP8 implementation: 3 files changed, no architecture modifications
3. Text encoder quantized to INT8 (transformers TorchAoConfig doesn't support float8)

### Changes
| File | Change |
|------|--------|
| `gpu_service/config.py` | Added `DIFFUSERS_FLUX2_QUANTIZE` (default: fp8) |
| `gpu_service/services/diffusers_backend.py` | `_load_flux2_pipeline()` FP8 transformer + INT8 text encoder |
| `devserver/schemas/configs/output/flux2_diffusers.json` | **NEW** — Flux 2 output config |
| `devserver/my_app/routes/settings_routes.py` | ComfyUI failure no longer hides all config availability (rescued from reset) |
| `public/.../text_transformation.vue` | Availability filter checks mapped config IDs (flux2 → flux2_diffusers) |

### Results
- Peak VRAM: ~24 GB (was ~48-62 GB in bf16)
- Inference time: ~13 seconds
- Quality: quasi-lossless (weight-only quantization at 56B params)

### Commits
- `bcb3b70` fix(status): ComfyUI failure no longer hides all config availability
- `90f1de4` feat(gpu): Flux 2 FP8 via Diffusers + output config + UI availability fix
- `5c555d7` fix(gpu): quantize Flux 2 text encoder to INT8

---

## Session 236 - DEVELOPMENT_LOG.md Consistency Fix
**Date:** 2026-03-02
**Focus:** Fix structural errors accumulated over 233+ sessions from parallel Claude sessions using conflicting session counters

### Changes
- **Renumbered 3 duplicate sessions**: Sessions 134, 135, 136 each appeared twice with different content. Real entries (older dates) kept as-is; mislabeled entries renumbered to 140a, 140b, 140c (filling the only gap between 139 and 141)
- **Reordered sessions 137–140c** into correct descending chronological order
- **Added 5 missing `---` dividers** between sessions 212/211, 211/210, 210/209, 165/164, 164/163
- **Added placeholder entries** for Session 217 (LLM Inference Migration — CANCELLED, referenced in Sessions 221/229) and Session 207.5 (Trans-Aktion Concept PoC, referenced in Session 208)
- **Added truncation note** to Session 111 (last entry, ends with stray bullet point)

### Files Changed
| File | Change |
|------|--------|
| `DEVELOPMENT_LOG.md` | All structural fixes in this single file |

### Commits
- `0ee7040` docs(devlog): fix structural inconsistencies — renumber duplicates, reorder, add dividers

---

## Session 235 - Proxy-Chunk-Pattern Elimination + Router Cleanup
**Date:** 2026-03-02
**Focus:** Eliminate architectural violation (Proxy-Chunk-Pattern) + remove dead code from backend_router.py
**Commit:** `d0ed7ce`

### Problem
The `output_image.json` and `output_legacy.json` proxy chunks violated the 3-layer architecture (Pipeline→Config→Chunk). Instead of pipelines resolving the correct chunk directly, a proxy chunk routed at runtime — an unnecessary indirection layer documented in `docs/ARCHITECTURE_VIOLATION_ProxyChunkPattern.md` since Feb 2026.

### Solution
Switched both pipelines to the `{{OUTPUT_CHUNK}}` pattern already proven in production via `dual_text_media_generation`. The template variable resolution in `config_loader._resolve_configs()` (lines 307-323) handles this at load time — zero new infrastructure needed.

### Changes
- `single_text_media_generation.json`: `chunks: ["output_image"]` → `["{{OUTPUT_CHUNK}}"]` (v3.0)
- `legacy_workflow_passthrough.json`: `chunks: ["output_legacy"]` → `["{{OUTPUT_CHUNK}}"]` (v2.0)
- Deleted proxy chunks: `output_image.json`, `output_legacy.json`
- Deleted orphaned chunks: `output_music_heartmula.json` (superseded by .py), `output_image_sd35_large.json`, `output_image_sd35_triton.json`
- Removed 492 lines dead code from `backend_router.py` (2777→2285):
  - `_process_heartmula_chunk()` — Python chunk takes priority, never reached
  - `_process_triton_chunk()` — Triton backend removed (GPU Service/Diffusers covers all)
  - `_process_ollama_request()` — never called from dispatch
  - `_process_direct_request()` — never called from dispatch
  - `_inject_legacy_prompt()` — duplicate of `LegacyWorkflowService._inject_prompt()`
  - `_process_comfyui_legacy()` — deprecated, zero active callers

### Verification
All 23 configs using `single_text_media_generation` or `legacy_workflow_passthrough` have `OUTPUT_CHUNK` in their parameters — confirmed via exhaustive grep.

### Not in scope
- `acestep_instrumental.json` dangling reference (chunk missing) — separate TODO
- Further router slimming: `_process_api_output_chunk` (~346 lines), `_process_stable_audio_chunk` (~119 lines) — future Python chunk migration
- `output_vector_fusion_clip_sd35.json` intentionally kept — vector manipulation planned for t2X return

## Session 234 - LoRA Support for Diffusers (Completion)
**Date:** 2026-03-02
**Focus:** Complete LoRA passthrough in remaining Diffusers Python chunks
**Commit:** `1f05c0c`

### Context
The LoRA plan (`docs/plans/lora-diffusers-support.md`) was approved earlier. Exploration revealed that most of the 5-file plan was already implemented in a prior session: `_apply_loras()`/`_remove_loras()` in the GPU service, LoRA params in `generate_image()`/`generate_image_with_fusion()`, routes, and client. Two Python chunks were the last missing pieces.

### Changes
- `output_image_sd35_turbo_diffusers.py` — added `loras: list = None` param, logging, passthrough to `backend.generate_image()`
- `output_image_flux2_diffusers.py` — same pattern

### Architectural Correction
The original plan's step 5 (fix `has_loras` routing in `backend_router.py` line 610) was **not needed**. Python chunks are caught at line 553-567 via `_execute_python_chunk()` and exit BEFORE the `has_loras` JSON-chunk routing decision. That check only affects legacy JSON/ComfyUI chunks.

### LoRA Coverage (complete for standard generation)
| Chunk | Status |
|---|---|
| `output_image_sd35_diffusers.py` | Was already done |
| `output_image_sd35_turbo_diffusers.py` | Done this session |
| `output_image_flux2_diffusers.py` | Done this session |
| `output_image_surrealizer_diffusers.py` | Was already done |
| Research methods (attention/probing/algebra/archaeology) | Deferred — not needed for standard generation |
| Video (Wan 2.1) | Out of scope |

## Session 233 - Flatten Synth UI to Independent Toggle Sections
**Date:** 2026-03-02
**Focus:** Replace abstract selector rows (Buffer/Free-run) with independent on/off toggle sections

### Problem
The synth tab UI had two selector rows with labels no synth user understands: "Buffer" (for looper) and "Free-run" (for continuous playback). The internal engine/behavior architecture was correct, but the UI exposed implementation details instead of user-facing concepts.

### Solution
Flattened the UI into four independent toggle sections, each with its own checkbox:

1. **Loop** — off by default, enables looping when toggled on. Ping-Pong and Auto-optimize as sub-options.
2. **Wavetable** — disabled until frames are extracted from generated audio. Static/Dynamic sub-switch (dynamic = placeholder for future scanning mode).
3. **Sequencer** — own on/off toggle, step grid appears when enabled.
4. **Arpeggiator** — moved from inside the sequencer to its own independent section. Processes sequencer notes identically to MIDI notes.

### Technical Changes
- Removed `PlaybackBehavior` type and `playbackBehavior` ref
- Added `loopOn`, `wavetableOn`, `sequencerOn` boolean refs (UI-facing)
- Kept `synthEngine` ref internally for engine routing (direct vs wavetable)
- Replaced `setSynthEngine()` / `setPlaybackBehavior()` with `toggleLoopSection()`, `toggleWavetable()`, `toggleSequencerSection()`
- Removed Loop On/Off button from action row (loop is now a section toggle)
- Removed `.engine-behavior-selectors`, `.selector-row`, `.mode-btn`, `.loop-btn` CSS
- Added `.section-toggle`, `.wavetable-mode-row` CSS
- i18n: removed 10 keys (engineDirect, behaviorFreerun, etc.), added 5 new keys (loopToggle, wavetableToggle, etc.)

### Files Changed
- `crossmodal_lab.vue` — template, script, CSS
- `en.ts` — i18n keys
- `WORK_ORDERS.md` — updated pending WO
- `DEVELOPMENT_LOG.md` — this entry

## Session 229 - IONOS AI Model Hub Provider Integration
**Date:** 2026-03-01
**Focus:** Full integration of IONOS AI Model Hub as 2nd DSGVO-compliant cloud LLM provider (EU datacenter Berlin)
**Commits:** `a70f0f8`, `69c7bb3`, `1d9a750`
**Test Report:** `docs/sessions/TEST_REPORT_IONOS_Model_Comparison_Session229.md`

### Die DSGVO-Odyssee: Angemessene LLM-Qualität aus EU-Rechenzentren

Die Plattform benötigt für die pädagogische Prompt Interception (Stage 2) ein Sprachmodell, das Metaphern, Synästhesien und bildhafte Beschreibungen in deutscher Sprache generiert — ohne Stilreferenzen, ohne Meta-Kommentare, nur pure sinnliche Transformation. Das ist eine Nische, die die meisten LLMs schlecht bedienen: kreative deutsche Prosa nach strikten pädagogischen Regeln.

**Chronologie der Versuche:**

| Session | Provider / Modell | Ergebnis | Problem |
|---|---|---|---|
| ~115 | Lokale Modelle (Ollama) | 4-6/10 | Zu klein für komplexe deutsche Synästhesie |
| ~180 | **Mistral AI EU** (erste Cloud-Integration) | 7-8/10 | DSGVO-konform, aber Qualitätsschwankungen |
| 217 | Mistral `mistral-large-latest` | **Desaster** | Stiller Modellwechsel auf Large 3 (675B MoE) → 85s Latenz, Plan "LLM Inference Migration" abgebrochen |
| 217+ | Mistral `mistral-large-2411` | 8/10 | Stabilisiert durch Modell-Pinning auf Large 2 (123B dense) |
| 221 | Mistral `mistral-large-2512` | **8.5/10** | Upgrade auf Large 3 (2512-Release), nun ~6s statt 85s. Systematischer Benchmark über 10 Interception-Kategorien. Erkenntnis: Task Instruction ist tragend (ohne: 4/10, mit: 8.5/10) |
| 221 | Mistral vs Claude (qualitativ) | — | Claude stärker bei expressiven Configs (Overdrive, Daguerreotype), Mistral stärker bei analytischen (Planetarizer, De-Kitsch). Mistral-Vorteil: DSGVO |
| **229** | **IONOS AI Model Hub** (EU Berlin) | **9.7/10** | Zweiter DSGVO-Provider. `gpt-oss-120b` (Reasoning-Modell) schlägt alle bisherigen EU-Modelle in Qualität UND Geschwindigkeit |

**Das Kernproblem:** DSGVO-Konformität schränkt die Modellauswahl massiv ein. US-Provider (Anthropic, OpenAI) bieten die besten Modelle, sind aber für eine Bildungsplattform mit Schülerdaten nicht einsetzbar. Die EU-Anbieter (Mistral, IONOS) hosten zwar in Europa, haben aber bisher nicht die gleiche Qualitätsstufe erreicht.

**Der Durchbruch (Session 229):** IONOS bietet mit `gpt-oss-120b` ein Reasoning-Modell, das durch Chain-of-Thought vor der eigentlichen Antwort "nachdenkt". Dieses Nachdenken ist nicht nur qualitätsverbessernd (9.7/10 vs Mistral 8.5/10), sondern **pädagogisch wertvoll**: Über die bereits existierende "Thinking"-Anzeige in ChatOverlay (Session 175) können Schüler sehen, WIE das Modell die Transformation plant.

### Testergebnisse (Kurzfassung)

Vollständige Outputs, Reasoning-Chains und Bewertungsmatrix: → `docs/sessions/TEST_REPORT_IONOS_Model_Comparison_Session229.md`

**Zwei Testprompts** mit dem echten Interception-Systemprompt (Metaphern, Synästhesien, WIE statt WAS):

**Prompt 1: "Ein Baum im Wind"**

| Modell | Latenz | Tokens | Bewertung | Auffälligkeit |
|---|---|---|---|---|
| **gpt-oss-120b** | **5.19s** | 437 | **9.7** | "das Auge zum Flüstern bringt" — echte Synästhesie |
| Mistral Large 2512 | 7.87s | 300 | 8.5 | Gut, aber Truncation bei 300 Tokens |
| Llama 405B | 8.44s | 200 | 6.5 | Konventionelle Metaphern ("Schwarm von Schmetterlingen") |
| Llama 70B | 4.38s | 261 | 7.0 | Schnellstes, aber flach |

**Prompt 2: "Eine Stadt bei Nacht mit Regen"**

| Modell | Latenz | Tokens | Bewertung | Auffälligkeit |
|---|---|---|---|---|
| **gpt-oss-120b** | **5.27s** | 515 | **9.7** | "Straßenwellen in schillernden Adern" — originell |
| Mistral Large 2512 | 11.71s | 483 | 8.5 | "poliertes Obsidian" — gut, aber Klischee |
| Llama 405B | 11.90s | 284 | 7.0 | Repetitiv ("wie ... Spiegel" 3×) |

**Erste Entscheidung (unzureichend getestet):** gpt-oss-120b für kreative Stages, Llama 70B für "strukturelle" Tasks.

### Erweiterte Per-Task-Tests (Runde 2)

Die erste Entscheidung basierte nur auf Interception-Tests. Runde 2 testete jede tatsächliche Pipeline-Aufgabe mit Edge Cases.

**Modell-Recherche:**
- **gpt-oss-120b**: OpenAI Open-Weight MoE (Apache 2.0). 117B total, **5.1B aktiv** — deshalb schneller als dense 70B Llama. General-Purpose Reasoning, KEIN Safety-Modell.
- **gpt-oss-safeguard-120b**: Separates Fine-Tune für Safety-Klassifikation. **Nicht verfügbar auf IONOS.**
- **Code Llama 13B**: Auf IONOS verfügbar, dediziertes Coding-Modell.
- IONOS bietet insgesamt 13 Modelle (7 LLMs, 1 Coding, 1 Image, 3 Embedding, 1 OCR).

**Translation (5 Edge Cases mit echtem TRANSLATION_PROMPT):**

| Test | gpt-oss-120b | Llama 70B |
|---|---|---|
| Yoruba + (((Brackets))) | 5.9s — Perfekt | 1.0s — OK |
| Gemischt DE/EN | 4.0s — "silver plate" | 0.9s — **FAIL**: "Silberplatte" stehen gelassen |
| Kurdisch + ((Tembûr)) | 2.3s — Perfekt | 1.0s — OK |
| Mathe + (((Selbstähnlichkeit))) | 4.4s — "self-similarity" | 1.1s — **FAIL**: 3 Komposita nicht übersetzt |
| Abstrakte Komposita | 4.9s — "timbre", "spatial perception" | 1.1s — **FAIL**: "Klangfarbe", "Raumwahrnehmung" deutsch gelassen |

**Llama 70B scheitert an deutschen Komposita (3/5 Edge Cases).** "Klangfarbe" in einem SD3.5-Prompt erzeugt Müll.

**Safety NER (10 Edge Cases):** Beide 8-9/10, diskutable Grenzfälle (Märchentitel, Platzhalternamen). Llama 70B 2.5× schneller, aber DSGVO-NER-Verification ist in 95%+ der Fälle kein LLM-Task (SpaCy Fast-Filter).

**Coding:** Code Llama 13B (2023, 13B) hat keine Chance gegen gpt-oss-120b (2025, 117B MoE). Schlechteres Instruction Following, unvollständiger Code, falsche Interpretation der Aufgabe.

**Revidierte Entscheidung:** **gpt-oss-120b für alle Stages.** Der Geschwindigkeitsvorteil von Llama 70B (~4s) rechtfertigt nicht die Übersetzungsfehler, die direkt die Bildgenerierungsqualität ruinieren.

Vollständige Testergebnisse: → `docs/sessions/TEST_REPORT_IONOS_Model_Comparison_Session229.md`

### Reasoning-Modell: Technische Implikationen

gpt-oss-120b ist ein **MoE-Reasoning-Modell** (117B total, 5.1B aktiv) — Antworten enthalten `reasoning_content` (Chain-of-Thought) UND `content` (finale Antwort).

**Problem entdeckt und gelöst:** Die `UI_MODE_MAX_TOKENS`-Begrenzung (kids=200, youth=400, expert=600) ließ dem Reasoning-Modell nicht genug Token-Budget. Bei 20 max_tokens war `content: null`, die gesamten Tokens flossen in `reasoning_content`. Fix: Minimum 2048 max_tokens für `gpt-oss`-Modelle in `_call_ionos()` und `_call_ionos_chat()`.

**Reasoning-Sichtbarkeit:** Das System zur Anzeige von LLM-Reasoning existiert und war **nie entfernt worden** — aktiv seit Session 175 in `ChatOverlay.vue` (kollabierbare "Thinking"-Sektion). War bisher nur für Ollama's `thinking`-Feld verdrahtet. Jetzt fließt auch IONOS' `reasoning_content` durch: `_call_ionos_chat()` gibt `{"content", "thinking"}` dict zurück (wie Ollama), statt plain string.

### Backend Changes

**`prompt_interception_engine.py`:**
- Provider registry: `ionos` entry mit URL, key_file, env_var
- `_call_ionos()`: Klon des Mistral-Patterns, IONOS-spezifischer Prefix-Strip, Reasoning-Modell max_tokens Floor (2048), defensives `content`/`reasoning_content` Fallback
- Routing: `elif request.model.startswith("ionos/"):`

**`chat_routes.py`:**
- `get_ionos_credentials()`: Liest JWT aus `ionos.key` oder `IONOS_API_KEY` env var
- `_call_ionos_chat()`: Gibt dict mit `thinking`-Feld zurück für ChatOverlay-Reasoning-Anzeige
- Routing in `call_chat_helper()`

**`settings_routes.py`:**
- `IONOS_KEY_FILE` Konstante
- `GET /api/settings/ionos-key` Endpoint (maskierte JWT-Anzeige)
- Key-Speicherung in `save_settings()`
- Status in `cloud_apis` dict

**`model_selector.py`:**
- `ionos/` in `strip_prefix()` und `extract_model_name()` ergänzt

**`config.py`:**
- Provider-Prefix-Kommentar erweitert

**`hardware_matrix.json`:**
- IONOS-Preset: `gpt-oss-120b` für alle 7 Stages (evidenzbasiert nach Per-Task-Tests)

### Frontend Changes

**`SettingsView.vue`:**
- Provider-Dropdown: `ionos` Option
- Info-Box (grün/DSGVO): API Base URL + DCD Token Manager Link
- JWT Token Input-Feld
- DSGVO-Compliance-Erkennung für `ionos/` Prefix
- Key Loading/Saving/Clearing Logik

**`ModelMatrixTab.vue`:**
- IONOS EU Cloud-Spalte mit DSGVO-Badge

**`types/settings.ts`:**
- `'ionos'` zum `CloudProvider` Type ergänzt

**`en.ts`:**
- 3 neue Keys: `ionosEu`, `ionosInfo`, `ionosDsgvo`

**`WORK_ORDERS.md`:**
- `WO-2026-03-01-ionos-provider-strings` für Batch-Translation

### Remaining TODOs

1. **Serverseitige Kostenkontrolle** via IONOS Billing API v3 (`usageFindByDC` Endpoint) — API-Docs sind JS-gerenderte Swagger UI, OpenAPI Spec Endpoint gibt 404
2. **Live Smoke Test** mit laufendem Backend — Interception Output-Qualität und Reasoning-Anzeige in ChatOverlay verifizieren

---

## Session 228 - Diffusers JSON→Python Chunk Migration
**Date:** 2026-03-01
**Focus:** Eliminate proxy-chunk anti-pattern — migrate 6 Diffusers JSON chunks to self-contained Python chunks
**Commit:** `5d5daf3`

### Problem

The 6 Diffusers JSON chunks (`output_image_sd35_diffusers.json`, etc.) violated the 3-layer architecture principle documented in `ARCHITECTURE_VIOLATION_ProxyChunkPattern.md`. They declared parameters (input_mappings, diffusers_config) but contained zero execution logic — all ~260 lines of generation code lived in `_process_diffusers_chunk()` inside `backend_router.py`. This created a monolithic routing method that handled SD3.5, Turbo, Flux2, Surrealizer fusion, Attention Cartography, and Feature Probing through a single if/elif chain reading JSON-declared flags (`attention_mode`, `feature_probing_mode`, `fusion_mode`).

### Solution

6 self-contained Python chunks, each owning its complete execution flow. Pattern follows the existing reference implementations (`output_image_concept_algebra_diffusers.py`, `output_image_denoising_archaeology_diffusers.py`).

**Key design decisions:**

1. **Dual-signature for parameter names**: Output configs pass UPPERCASE params (`CFG`, `STEPS`, `WIDTH`), pipeline/frontend may pass lowercase. Each chunk accepts both and resolves with `is not None` checks (critical: `CFG=0.0` for Turbo must not be treated as falsy).

2. **Fallback via CHUNK_META, not chunk code**: Chunks raise `RuntimeError` on failure. The router's `_process_output_chunk()` reads `CHUNK_META.fallback_chunk` from the loaded `sys.modules` entry and falls back to ComfyUI. This keeps fallback knowledge in the router (where it belongs) while chunks declare their fallback target declaratively.

3. **Fallback chains preserved**:
   - `sd35_diffusers.py` → `sd35_large.json` (ComfyUI)
   - `sd35_turbo_diffusers.py` → `sd35_diffusers.py` → `sd35_large.json`
   - `flux2_diffusers.py` → `flux2.json` (ComfyUI)
   - Surrealizer / Attention / Probing → None (no ComfyUI equivalent)

4. **`sd35_large.json` config updated**: `OUTPUT_CHUNK` now points to `output_image_sd35_diffusers` (was `output_image_sd35_large` with auto-detection). `backend_type` changed from `comfyui` to `diffusers`. The old auto-detection via `_get_diffusers_compatible_chunk()` is removed.

5. **`flux2.json` stays on ComfyUI**: 106GB BF16 model, ComfyUI handles FP8 quantization. The `output_image_flux2_diffusers.py` chunk exists for configs that explicitly opt in.

### Dead Code Removed (323 lines from backend_router.py)

- `_process_diffusers_chunk()` (~260 lines) — the monolithic Diffusers handler
- `_get_diffusers_compatible_chunk()` (~30 lines) — auto-detection heuristic
- `elif backend_type == 'diffusers'` routing branch
- LoRA auto-detection + `DIFFUSERS_ENABLED` branching for ComfyUI-declared chunks

The `_fallback_to_comfyui()` method stays — still used by `_process_stable_audio_chunk()` and `_process_heartmula_chunk()`.

### Bugfix: Circular Fallback in output_image_sd35_large.json

The ComfyUI chunk `output_image_sd35_large.json` had `"fallback_chunk": "output_image_sd35_diffusers"`, creating a potential circular reference (Diffusers → ComfyUI → Diffusers). Removed. ComfyUI chunks are terminal fallback targets.

### Test Strategy

Wrote 39 unit tests in `devserver/tests/test_diffusers_chunk_migration.py` covering 11 test suites. Tests use `unittest.mock.AsyncMock` to mock the GPU backend — no GPU or running service required.

| Suite | Tests | Coverage |
|---|---|---|
| 1. Structure | 7 | Files exist, JSON deleted, CHUNK_META fields, DEFAULTS, execute() async, fallback chains, fallback targets exist |
| 2. Content markers | 1 | All 3 markers (`diffusers_generated`, `diffusers_attention_generated`, `diffusers_probing_generated`) found in `schema_pipeline_routes.py` consumers |
| 3. Parameters | 10 | Prompt resolution (prompt → TEXT_1 → PREVIOUS_OUTPUT), uppercase/lowercase params, lowercase priority, CFG=0.0 preserved, triple-prompt forwarding, LoRA forwarding, empty prompt rejection |
| 4. Backend unavailability | 2 | All chunks raise RuntimeError when `is_available()=False`, all standard chunks raise on empty backend result |
| 5. Surrealizer | 3 | Auto-alpha 20-30, explicit alpha/strategy/t5_prompt forwarding, no fallback |
| 6. Attention | 2 | Correct return structure (attention_data with all sub-fields), default capture_layers [3,9,17] |
| 7. Probing | 3 | Correct return structure, transfer_dims forwarding, error dict handling |
| 8. Flux2 | 1 | Correct model_id, pipeline_class=Flux2Pipeline, defaults |
| 9. Configs | 3 | 5 output configs point to correct chunks, sd35_large.json backend_type=diffusers, no circular fallbacks in any JSON chunk |
| 10. Router | 4 | No dangling method refs, no diffusers routing branch, fallback logic present in _process_output_chunk, reference chunks untouched |
| 11. Seeds | 3 | seed='random' → valid int, explicit seed forwarded, seed=-1 → random |

**Critical test: CFG=0.0 (tests 3.6, 3.7)** — the Turbo model requires `cfg_scale=0.0`. Using `or` instead of `is not None` would silently fall through to a default value, producing wrong images. Both lowercase and uppercase paths are tested.

**Critical test: Content markers (test 2.1)** — wrong markers = silent data loss. The test reads `schema_pipeline_routes.py` source and verifies all 3 marker strings appear. If a consumer branch is renamed or removed, this test fails.

### Files Created
- `devserver/schemas/chunks/output_image_sd35_diffusers.py`
- `devserver/schemas/chunks/output_image_sd35_turbo_diffusers.py`
- `devserver/schemas/chunks/output_image_flux2_diffusers.py`
- `devserver/schemas/chunks/output_image_surrealizer_diffusers.py`
- `devserver/schemas/chunks/output_image_attention_cartography_diffusers.py`
- `devserver/schemas/chunks/output_image_feature_probing_diffusers.py`
- `devserver/tests/test_diffusers_chunk_migration.py`

### Files Modified
- `devserver/schemas/engine/backend_router.py` — fallback logic added, 323 lines removed
- `devserver/schemas/configs/output/sd35_large.json` — OUTPUT_CHUNK + backend_type
- `devserver/schemas/chunks/output_image_sd35_large.json` — circular fallback removed

### Files Deleted
- `devserver/schemas/chunks/output_image_sd35_diffusers.json`
- `devserver/schemas/chunks/output_image_sd35_turbo_diffusers.json`
- `devserver/schemas/chunks/output_image_flux2_diffusers.json`
- `devserver/schemas/chunks/output_image_surrealizer_diffusers.json`
- `devserver/schemas/chunks/output_image_attention_cartography_diffusers.json`
- `devserver/schemas/chunks/output_image_feature_probing_diffusers.json`

### Bugfix: JSON files not actually deleted + 3 broken code paths (`d10fd6a`)

During test expansion (39→44 tests), discovered that the 6 JSON files were not actually deleted from disk (only staged). Also found 3 methods in `backend_router.py` that still assumed JSON-only chunks:

1. **`_check_fallback_chunk()`**: Used `_load_output_chunk()` (JSON-only) to verify fallback targets. Fixed to also check for `.py` chunk files via `_find_chunk_file()`.
2. **`_load_optimization_instruction()`**: Same issue — only checked JSON meta. Fixed to read `CHUNK_META` from Python chunks via `importlib`.
3. **Router fallback in `_process_output_chunk()`**: Called `_load_output_chunk()` for fallback target, which only returns JSON. Fixed to call `_process_output_chunk()` recursively, which handles both `.py` and `.json` chunks.

### Live Testing Results

All 6 migrated configs tested against running backend (GPU service + DevServer):

| Config | Result | Notes |
|---|---|---|
| SD3.5 (`sd35_large`) | SUCCESS (32s) | Log confirms `[PYTHON-CHUNK] Loading chunk:` |
| SD3.5 Turbo (`sd35_large_turbo`) | SUCCESS (32s) | CFG=0.0 correctly forwarded |
| Surrealizer (`surrealization_diffusers`) | SUCCESS (32s) | After VRAM fix (see below). Alpha/strategy work. |
| Attention Cartography | SUCCESS (65MB response) | Heatmaps + image generated |
| Feature Probing | OOM | Pre-existing issue, not migration-related (see below) |
| Flux2 | Not tested | Config still on ComfyUI (106GB BF16 model) |

**Fallback test** (GPU service stopped):
- SD3.5 → Fell back to ComfyUI via `[FALLBACK]` log → SUCCESS (31s)
- Surrealizer → Clean `RuntimeError` (no ComfyUI equivalent, `fallback_chunk: None`) → correct behavior

### Bugfix: VRAM Fragmentation in GPU Service (`ce822b0`)

**Discovery**: Surrealizer failed through DevServer with "Surrealizer generation returned empty result". Direct GPU service curl at 512x512 worked once, but 1024x1024 failed. After unloading the model and clearing VRAM to 95GB free, 1024x1024 worked — but only on the first call.

**Root cause**: Methods that create manual text embeddings outside the pipeline's `encode_prompt()` scope — `generate_image_with_fusion()`, `generate_image_with_probing()`, `generate_image_with_algebra()` — leave encoder output tensors on GPU. These tensors are released by Python GC but the CUDA memory remains cached-but-unallocated, fragmenting VRAM. On the next call at full resolution, the allocator cannot find a contiguous block → OOM.

Standard `generate_image()` and `generate_image_with_attention()` are unaffected because they call `pipe(prompt=...)` which manages its own embedding lifecycle.

**Fix**: Added `torch.cuda.empty_cache()` in the `finally` block of all 3 manual-embedding methods in `gpu_service/services/diffusers_backend.py`. This returns cached CUDA memory to the allocator, allowing defragmentation between calls.

**Why this wasn't caught before**: The JSON chunks worked through `_process_diffusers_chunk()` which was a single monolithic method. In practice, the GPU service was restarted frequently during development, masking the fragmentation. The migration exposed it because systematic consecutive testing (6 configs in a row) was done for the first time.

### Pre-existing: Feature Probing OOM at encoder="all"

Feature Probing with `encoder="all"` at 1024x1024 creates 9+ simultaneous encoder passes (3 prompts × 3 encoders), exceeding available VRAM (~43GB free after 52GB SD3.5 model). The old JSON chunk had identical default (`"probing_encoder": "all"`). Not a regression — same behavior before migration. Workaround: use `encoder="t5"` or reduce resolution.

### All Commits (Session 228)

| Commit | Description |
|---|---|
| `5d5daf3` | feat: migrate 6 Diffusers JSON chunks to self-contained Python chunks |
| `d10fd6a` | fix: delete JSON files + fix 3 broken code paths (_check_fallback_chunk, _load_optimization_instruction, router fallback) |
| `ce822b0` | fix(gpu-service): add torch.cuda.empty_cache() after manual-embedding generation methods |

### Status
Migration complete. 44 unit tests pass. Live testing confirms all configs work (except pre-existing Feature Probing OOM). Fallback chain verified. VRAM fragmentation bug fixed.

---

## Session 227 - T5 Interpretability: From SAE to Cultural Drift
**Date:** 2026-02-28 / 2026-03-01
**Focus:** Complete T5 interpretability pipeline, validate sonification methods, discover cultural drift in semantic axes
**Commits:** `bf3a469`, `03fca7d`, `9c741e0`, `f726d72`, `b97572e`, `a99068a`

### What Happened

Executed the full T5 Interpretability Research pipeline (7 phases), then spent most of the session empirically validating whether the results are actionable — leading to unexpected findings about cultural bias encoded in perceptual dimensions.

### Phase 1-7: Pipeline Execution

Ran all scripts from `research/t5_interpretability/`. Corpus: 392K prompts (388K bulk from AudioCaps/MusicCaps/WavCaps + 3.9K structured probing across 15 musical traditions). Encoded through T5-Base → [392K, 768] activations.

**SAE training failure and fix:** TopK sparsity (Anthropic recipe) produced 99.3% dead features — winner-take-all gradient dynamics killed almost all neurons. Neuron resampling didn't help (features died within 5 epochs of stopping). Solution: switched to ReLU + L1 sparsity → 0.0% dead features (6143/6144 alive). Key lesson: L1 > TopK for small domain-specific corpora.

Cultural analysis confirmed: 15 tradition centroids are significantly non-random (permutation test p=0.001), Electronic maximally distant from all acoustic traditions, 265 features needed for 90% discrimination.

### The Critique That Changed Everything

Listening to the SAE sonification outputs, user correctly identified that the feature interpretations were "frei erfunden" — post-hoc correlational labels without causal validation. Activating Feature #1058 (labeled "Balinese gamelan") produced generic percussive clicks, not Balinese music. The sonification failed to validate the SAE feature semantics.

This triggered a systematic investigation of *why* embedding injection doesn't work.

### Four Validation Experiments (1,500 audio samples total)

| Experiment | Method | Samples | Key Result |
|---|---|---|---|
| C1: Text prompts | "sound rhythmic" vs "sound sustained" as text | 200 | **d=2.88*** (massive effect) |
| C2: Injection | T5 difference vector into neutral embedding | 200 | **d=0.83*** (weak, 6% retention) |
| C3: LERP | Interpolation between two natural T5 outputs | 500 | **d=2.43*** (84% retention) |
| C4: Multi-axis | 3 axes combined additively | 400 | **d=1.02*** (35% retention) |

**The discovery:** LERP between natural T5 embeddings recovers 84% of text-prompt effect with monotonic gradients (Pearson r=0.63). Vector arithmetic (injection) fails because it creates out-of-distribution embeddings that Stable Audio's cross-attention ignores. LERP succeeds because both endpoints are natural T5 outputs.

Multi-axis additive combination degrades to ~35% per axis — the combined embedding drifts from the T5 manifold. A bridge model could potentially recover this.

### Cultural Drift Analysis

The session's most pedagogically significant finding. Measured how moving along 21 semantic axes (8 perceptual, 7 cultural-contextual, 6 critical) shifts the embedding's proximity to 15 tradition centroids. Key discoveries:

- **"traditional ↔ modern"**: Ukrainian drifts most toward "traditional" (-0.071). African American = near zero. T5 codes "traditional" as geographically non-Western.
- **"professional ↔ amateur"**: Electronic = most "professional." African American = **only** tradition drifting toward "amateur." A measurable bias.
- **"music ↔ noise"**: Tuvan and Aboriginal Australian furthest from "music." Confirms default-encoding bias.
- **"complex ↔ simple"**: No Eurocentrism detected — a notable null finding.
- **"tonal ↔ noisy"**: Most culturally loaded "perceptual" axis. Moving toward "tonal" pulls toward all traditions, but differentially (Flamenco -0.321, Aboriginal -0.260).

Three axis categories identified for pedagogical design:
1. **Culturally neutral** (loud↔quiet, complex↔simple): safe for aesthetic exploration
2. **Culturally biased** (traditional↔modern, professional↔amateur): drift should be shown to learners
3. **Culturally constitutive** (tonal↔noisy, music↔noise): reproduce boundary definitions of what counts as music

### Files Created
- `research/t5_interpretability/sonify_binary_contrasts.py` — 10 binary contrast pairs
- `research/t5_interpretability/statistical_sonification_test.py` — Text-prompt validation (N=100)
- `research/t5_interpretability/statistical_embedding_injection_test.py` — Injection validation (N=100)
- `research/t5_interpretability/statistical_lerp_test.py` — LERP gradient test (N=500)
- `research/t5_interpretability/statistical_multiaxis_test.py` — Multi-axis factorial (N=400)
- `research/t5_interpretability/cultural_drift_analysis.py` — 21 axes x 15 traditions
- `research/t5_interpretability/FINDINGS.md` — Comprehensive research summary (9 sections)

### Files Modified
- `research/t5_interpretability/config.py` — SAE hyperparams (8x expansion, L1 params)
- `research/t5_interpretability/train_sae.py` — Complete rewrite: TopK → L1+ReLU

### Data Generated (gitignored)
~2.5 GB in `research/t5_interpretability/data/`: 1,500+ WAV files, SAE weights (37 MB), activations (575 MB), feature atlas, cultural analysis, drift analysis.

### Status
Research complete. The FINDINGS.md document contains all results with full statistical backing. The cultural drift analysis connects the technical LERP findings with the project's pedagogical mission — making visible how AI models entangle aesthetic and cultural categories.

### Open Questions
1. Does multi-axis LERP work better with a learned bridge model?
2. Are the statistical effects perceptually audible at each LERP step?
3. Which additional text-pole pairs produce the strongest perceptual gradients?
4. How should the UI communicate cultural drift alongside sound output?

---

## Session 226 - SD3.5 Per-Encoder CLIP Optimization
**Date:** 2026-02-28
**Focus:** Give each of SD3.5's three text encoders the right input instead of the same prompt
**Commits:** `da60d8b`, `0eb93d8`, `cbe58b2`, `a2ac1f5`, `114bba5`

### Problem
SD3.5 has three encoders with fundamentally different needs: CLIP-L (77 tokens, visual keywords with weight syntax), CLIP-G (77 tokens, semantic scene, no weights), T5-XXL (512 tokens, natural language). Sending the same prompt to all three wastes each encoder's strengths.

### Implementation
Optimization instruction now produces `{clip_l, clip_g}` JSON. The LLM generates CLIP-specific prompts with token weighting (CLIP-L) and semantic scene descriptions (CLIP-G). T5-XXL receives the user's interception result directly, translated by Stage 3.

**Backend pipeline:** `_parse_triple_prompt()` detects JSON → Stage 3 safety-checks the interception result → CLIP-L becomes primary prompt, CLIP-G → `prompt_2`, translated interception text → `prompt_3` → forwarded through `backend_router.py` → `diffusers_client.py` → GPU service (already supported `prompt_2`/`prompt_3`).

**Frontend:** MediaInputBox detects `{clip_l, clip_g}` JSON and renders two labeled sections instead of raw textarea. Info note "T5-XXL uses your original text directly" shown below. Contextual loading message during optimization explains encoder architecture (SD3.5-specific) and hints at manual translation.

### Key Design Decision
T5-XXL is NOT optimized by the LLM. The user's own description stays in the richest encoder (4.7B params), preserving creative self-determination. Only the technical CLIP layer gets augmented. This emerged from the discussion: the initial plan generated all three prompts, but T5 doesn't need "optimized" input — it's trained on natural language, which is exactly what the interception result already is.

### Translation Caveat
Stage 3 auto-translates only at kids safety level. At adult/research, the user must translate manually (translate button). Documented in config notes and shown in loading message.

### Files Modified
- `sd35_large.json`, `sd35_large_turbo.json` — 2-key optimization instruction
- `instruction_selector.py` — `triple_prompt_optimization` type
- `schema_pipeline_routes.py` — `_parse_triple_prompt()`, Stage 3/4 flow, optimize endpoint
- `backend_router.py` — `prompt_2`/`prompt_3` forwarding
- `diffusers_client.py` — HTTP payload forwarding
- `MediaInputBox.vue` — CLIP-prompt display + T5 info note
- `text_transformation.vue` — contextual loading message
- `en.ts` + `WORK_ORDERS.md` — i18n keys

---

## Session 225 - Rename trans_aktion → poetry + Clean Context Fields
**Date:** 2026-02-28
**Focus:** Rename 6 interception configs, clean redundant context instructions, drop model_override
**Commit:** `c6fc4ca`

### Changes

**6 interception configs renamed** (`devserver/schemas/configs/interception/`):
`trans_aktion_*` → `poetry_*` (sappho, hoelderlin, basho, mirabai, yoruba_oriki, nahuatl)

**Internal identifiers updated** in each config:
- `properties`: `["trans_aktion"]` → `["poetry"]`
- `display.category`: `"trans_aktion"` → `"poetry"`
- `category` EN: `"Trans-Aktion"` → `"Poetry"` (other langs via i18n agent)
- `meta.model_override: "qwen3:1.7b"` removed — uses default STAGE2_INTERCEPTION_MODEL

**Context fields cleaned**: Stripped prefix labels ("Sappho fragments: " / "Sappho-Fragmente: ") and instruction suffixes ("Fuse these words..." / "Verschmelze diese Woerter..."). The TASK_INSTRUCTION from instruction_selector.py already says "Use the specific vocabulary and techniques defined in Context" — the embedded instructions were redundant. Only the word lists remain.

**Vue references**: PropertyBubble.vue + PropertyCanvas.vue updated (`trans_aktion` → `poetry`).

**i18n work order**: WO-2026-02-28 for context translations (7 missing languages) + category translation.

### Hypothesis — Lyric Fragments as Atmospheric Conditioning
Similar to Youth Slang and Pig Latin: poetry can presumably generate specific atmospheric effect patterns due to its semantic structure (which appears here only in excerpts). The word lists — even as fragments, without syntactic context — may function as semantic attractors that bias the generation toward specific tonal registers. This is a hypothesis worth testing systematically.

---

## Session 224 - Seed Handling: 5 Bugs Fixed Across Full Pipeline
**Date:** 2026-02-28
**Focus:** Fix broken seed randomization (same image on repeat generation) and 4 structural bugs in the seed flow

### Root Cause
Output configs had uppercase `"SEED": "random"` but the pipeline executor reads/injects lowercase `"seed"`. The uppercase key was dead code — seeds fell back to hardcoded chunk defaults (e.g. `1125488487853216`), producing identical images on every generation.

### Changes

**Bug 1 — 10 output config JSONs** (`devserver/schemas/configs/output/`):
`"SEED"` → `"seed"` in: qwen, sd35_large, sd35_large_turbo, flux2, stableaudio_open, acenet_t2instrumental, acestep_instrumental, ltx_video, wan22_video, wan22_i2v_video

**Bug 2 — `backend_router.py`** (`_apply_input_mappings`, node-based + template-based):
`generated_seed` was only set when `value == "random"`. Integer seeds passed through without metadata tracking → `seed: None` in results. Now tracks all seed values.

**Bug 3 — `schema_pipeline_routes.py`** (3 locations):
- `result_seed = metadata.get('seed') or seed` → `is not None` check (seed=0 is falsy in Python)
- `if seed_override:` → `if seed_override is not None:`

**Bug 4 — `backend_router.py`** (`_process_legacy_workflow`):
Missing `'seed': generated_seed` in both return paths (ComfyUI-direct + SwarmUI legacy). Initialized `generated_seed = None` before input_mappings block.

**Bug 5 — `schema_pipeline_routes.py`** (cloud API seed transparency):
Cloud APIs (openai, openrouter) don't support seeds but the old code returned the frontend seed as if it was used. Now explicitly sets `result_seed = None` for these backends.

### Verification
- Generate with qwen config → repeat same prompt → different image (new random seed)
- Expert-mode shows actual seed used (not None, not faked for cloud APIs)

---

## Session 223 - Model Profile Meta for Expert Mode Steckbrief
**Date:** 2026-02-28
**Focus:** Populate model identity card (Steckbrief) in expert denoising view for all output configs
**Commit:** `7ca3ea8`

### Context
Session 220 built the expert denoising view with a model Steckbrief that reads profile fields directly from `config.meta` (display_name, publisher, architecture, params, etc.). However, 18 of 31 output configs were missing these fields, leaving the model card blank during generation.

### Changes

**18 output config JSONs** — added profile meta fields:
- **ACE-Step** (3 configs): instrumental, simple, long narrative — Diffusion Transformer, ~3.5B, Apache 2.0
- **ACE-Net** (1 config): Neural Audio Codec + Transformer, ~1B
- **FLUX.2 img2img** (1 config): copied from flux2.json, 56B MMDiT
- **Qwen variants** (2 configs): img2img + 2511 multi — 20B MMDiT, copied from qwen.json
- **SD 3.5 research tools** (4 configs): attention cartography, concept algebra, denoising archaeology, feature probing
- **Stable Audio legacy** (2 configs): stableaudio + tellastory — copied from stableaudio_open.json
- **Legacy ComfyUI** (3 configs): surrealization, partial elimination, split & combine — SD 3.5 profile
- **Code generation** (2 configs): p5.js + Tone.js — LLM-dependent profile

**DenoisingProgressView.vue** — removed emoji icon from model card header (template `<span class="model-icon">`, `profileIcon` computed, `.model-icon` CSS). The emoji oversimplified model identity and masked real differences between models.

### Verification
- All 31/31 output configs validated to have `display_name` in meta
- Vue type-check passes clean

---

## Session 222 - Firefox/iGPU Performance Fix + Streaming UX
**Date:** 2026-02-28
**Focus:** Fix severe Firefox lag on iGPU (128MB VRAM), optimize CSS animations and JS timers, switch streaming display from char-by-char to word-by-word
**Commits:** `2ecd79f`, `caa9299`, `a649a5d`, `228361b`, `18087ad`, `50483be`, `62d5976`

### Problem
App was unusable in Firefox on a PC with integrated GPU (128MB VRAM). Root cause analysis identified 47 `backdrop-filter: blur()` usages, 87 infinite CSS animations (many non-compositable), a 60fps RAF loop writing Vue reactive refs, 5 concurrent `setInterval` timers during generation, and a streaming buffer that added ~4s of artificial display lag.

### Changes (5 performance phases + 2 UX fixes)

| Phase | Change | Impact |
|-------|--------|--------|
| 1 | Remove `backdrop-filter` from header + footer | Eliminates permanent GPU compositing on every page |
| 2 | Replace `text-shadow`, `box-shadow`, `border-color`, `filter`, `left` animations with `opacity`/`transform` | All infinite animations now GPU-compositable |
| 3 | Remove `filter: drop-shadow()` from animated ChatOverlay + SpriteProgress elements | No filter recalculation per animation frame |
| 4 | Throttle RAF to 10fps reactive updates + consolidate 3 timers → 1 | ~50 fewer Vue re-renders/sec during generation |
| 5 | Separate ClimateBackground cloud positions from dynamic darkness | Cloud array stable (only recreated on count change, not every second) |
| UI | Sharpen model bubble hover-info text, remove transparency | Clearer text at 2× scale on low-DPI displays |
| UX | Switch streaming from char-by-char (30ms/1-3 chars) to word-by-word (50ms/word) | Buffer drains ~4× faster, better kids readability |

### Key Insight: Word-by-Word Streaming
The char-by-char typewriter effect was designed for perceived speed (start showing content immediately). But it also added ~4 seconds of "trickle lag" after LLM completion because the buffer drained slower than it filled. Word-by-word preserves the fast start while eliminating the lag at the end. Additionally, pedagogically superior for kids who read in word units.

### Design Discussion (deferred)
Two UX features discussed for future implementation:
1. **Model parameter selection via long-press**: Pill-toggle popover (orientation + resolution) anchored to model bubble. Infrastructure exists in `ConfigTile.vue` (500ms long-press timer). Radial menus rejected for compound parameters.
2. **Prompt optimization trigger**: Currently auto-runs on model click. User reports psychological avoidance of SD3.5 due to optimization wait. Potential fix: background pre-computation or split triggers by stage cost.

---

## Session 221 - Mistral Large 2411 → 2512 Upgrade + Interception Quality Benchmark
**Date:** 2026-02-27
**Focus:** Upgrade Mistral model pin, benchmark Prompt Interception quality across all categories
**Commit:** `d7ebfe9`

### Context
`mistral-large-latest` had silently changed to Mistral Large 3 (675B MoE) in Dec 2025, causing 85s latency in Session 217. We pinned to `mistral-large-2411` (Large 2, 123B dense). Question: Is the newer `mistral-large-2512` viable now?

### Live Latency Test
Both models benchmarked with identical interception prompts:
- **2411**: ~6.3s (short), no quality difference
- **2512**: ~6.1s (short), better instruction compliance (English output when asked, proper `stop` finish)
- **Conclusion**: Equal latency, better quality → upgrade to 2512

### Interception Quality Benchmark (10 categories, Claude Opus as baseline)

Tested with the **real `manipulate.json` template** (Task Instruction + Context + Input), not raw system prompts.

| Category | Config | Score | Notes |
|---|---|---|---|
| aesthetics | overdrive | 7/10 | Physics jargon, ALL CAPS |
| arts | confucianliterati | 9/10 | Correct Fachterminologie (bifa, pima cun, fei bai) |
| attitudes | sensitive | 7.5/10 | Good phenomenology, slight markdown + didactic tendency |
| critical_analysis | planetarizer | 9.5/10 | Outstanding materialist entanglement |
| semantics | jugendsprache | 9/10 | Perfect UK slang, compact (58 tokens) |
| technical_imaging | daguerreotype | 7/10 | Self-contradicting light description |
| trans_aktion | yoruba_oriki | 8/10 | Oriki motifs correctly woven, could be more rhythmic |
| aesthetics | de-kitsch | 9.5/10 | All superlatives eliminated, precise observation |
| critical_analysis | one_world | 10/10 | Hyper-specific Caracas family scene, no stereotypes |

**Average: 8.5/10**

### Key Insight: Task Instruction is Critical
- **Without** `instruction_selector.py` wrapper: Mistral scores ~4/10 (essay mode, meta-commentary, English instead of German)
- **With** Task Instruction ("Output ONLY the transformed result. NO meta-commentary"): 8.5/10
- The `manipulate.json` template is load-bearing — never bypass it

### Systematic Patterns
- **Strong (9+)**: Factual/analytical configs (Planetarizer, De-Kitsch, One World, Jugendsprache, Literati)
- **Weaker (7-7.5)**: Expressive/philosophical configs (Overdrive, Sensitive, Daguerreotype)
- Mistral tends toward pseudo-scientific jargon when a *Haltung* (attitude) is required instead of domain knowledge
- Occasional `**markdown**` formatting in output — needs stripping before Stage 4

### Mistral vs Claude (qualitative)
- Claude: more imagistic, linguistically precise in expressive configs
- Mistral: equally strong or stronger in factual/analytical configs
- Both respect Task Instruction when properly formatted
- Mistral's strategic advantage: DSGVO-compliant (EU-based, no US routing)

### Files Changed
| File | Change |
|------|--------|
| `devserver/hardware_matrix.json` | 6× `mistral-large-2411` → `mistral-large-2512` |
| `devserver/schemas/configs/interception/lyrics_from_theme.json` | model_preferences → 2512 |
| `devserver/schemas/configs/interception/lyrics_refinement.json` | model_preferences → 2512 |
| `devserver/schemas/configs/interception/tag_suggestion_from_lyrics.json` | model_preferences → 2512 |
| `devserver/schemas/configs/interception/tags_generation.json` | model_preferences → 2512 |
| `devserver/my_app/routes/canvas_routes.py` | Model list → 2512 + name "Mistral Large 3" |

### API Status Note
Mistral Completion API had unplanned degradation 26-27 Feb 2026 (not maintenance). Despite status page, API was functional during our benchmarks at ~14s/request for full interception prompts.

---

## Session 220 - Language-Aware Safety Filter Terms
**Date:** 2026-02-27
**Focus:** Restructure flat filter term lists into per-language dicts, check only detected language + EN
**Commits:** `9f9cb2d`, `c83edf1`

### Problem
Safety filter terms were a flat list mixing all 7+ languages. Every prompt was checked against every term from every language, causing cross-language false positives — e.g. Turkish "kan" (blood) matching inside German "scharfkantige" (sharp-edged). Not debuggable: logs never showed which language triggered a match.

### Solution: Language-Aware Filtering
1. **JSON restructure**: `terms` → `terms_by_language` in `youth_kids_safety_filters.json` (kids + youth) and `stage1_86a_critical_bilingual.json` (§86a). All 9 supported languages: de, en, tr, ko, uk, fr, es, he, ar.
2. **Hybrid language detection** (`_detect_input_language`): Unicode-script for non-Latin scripts (ko=Hangul, uk=Cyrillic, he=Hebrew, ar=Arabic) — deterministic, ~0ms. Frontend `user_language` as fallback for Latin scripts (de/en/tr/fr/es).
3. **Selective checking** (`_get_active_terms`): Only terms for detected language + EN are checked. A DE user sees 115 terms instead of 588.
4. **All 13 callsites** in `schema_pipeline_routes.py` updated to extract and pass `user_language`.
5. **Frontend**: `MediaInputBox.vue` sends `locale.value` as `user_language` in `/safety/quick` requests.

### Key Design Decisions
- **No new dependencies**: No `langdetect` — unreliable for short prompts (3-10 words). Unicode ranges are deterministic.
- **EN always checked**: English terms are always in the active set regardless of detected language.
- **Stage 3 §86a on translated text**: Uses `user_language='en'` explicitly since text is already translated.
- **Word-boundary for ≤3 chars stays**: Defense-in-depth, unchanged from previous session.
- **CJK word-boundary limitation**: Known pre-existing issue — Korean terms ≤3 chars don't match with `\b` regex. Not a regression.

### Files Changed
| File | Change |
|------|--------|
| `devserver/schemas/youth_kids_safety_filters.json` | `terms` → `terms_by_language` (9 langs), he/ar error_messages |
| `devserver/schemas/stage1_86a_critical_bilingual.json` | `terms` → `terms_by_language` (6 langs) |
| `devserver/schemas/engine/stage_orchestrator.py` | `_detect_input_language()`, `_get_active_terms()`, updated loaders + filter signatures |
| `devserver/my_app/routes/schema_pipeline_routes.py` | All 13 callsites pass `user_language` |
| `public/.../MediaInputBox.vue` | Sends `user_language: locale.value` |

### Verification
- `"scharfkantige Fassaden"` (DE, kids) → **safe** (TR terms not active)
- `"kan kanlı vahşet"` (TR, kids) → **blocked** (tr+en active)
- `"kan kanlı vahşet"` (DE, kids) → **safe** (TR terms not active)
- `"Ein blutiger Kampf"` (DE, kids) → **hit** (Blut in de terms)
- Hebrew/Arabic auto-detection + filtering works via Unicode ranges

---

## Session 220b - Pedagogical Denoising View (Expert UI Mode)
**Date:** 2026-02-27
**Focus:** Replace edutainment games with real-time denoising progress view for `UI_MODE=expert`
**Commits:** `0b76e23`, `ceb641f`, `3a88d64`, `52b2d57`, `d7e271d`, `52bdf93`, `5bf31e9`, `400c92a`

### Problem
During image generation (5-90s), the waiting screen shows edutainment mini-games (Forest, Iceberg, Pixel). For expert mode users (educators, researchers), this wastes valuable pedagogical surface — they should see the AI's actual work: model specs, GPU load, denoising steps, energy consumption.

### Solution: Two-Phase Expert View

**Phase A — Model Loading** (model not yet in VRAM):
Model "Steckbrief" (identity card) showing publisher, architecture, parameters, text encoders, quantization, license, Fair Culture assessment, Safety-by-Design notes. Rotating expert facts about GPU/energy below.

**Phase B — Denoising Active** (inference running):
Large denoising preview image (ComfyUI only) + compact single-line stats:
`593W · 0.003 kWh | GPU 95% · 51.9/96GB | seed:12345 · CFG:1 · 12/20`

**Post-Generation Summary Bar:**
`FLUX.2 [dev] · 23.4s · 0.003 kWh · 1024x1024 · seed:12345 · CFG:1 · 20 steps`

### Key Design Decisions
- **Backend-aware phase detection**: Diffusers only reports progress during inference (`progress === 0` = loading). ComfyUI reports node-level progress during loading too (`!previewImage` = loading signal).
- **Energy tracking persistence**: `stats-snapshot` emit on `onBeforeUnmount` captures final kWh/CO₂ before component destruction. Parent stores values for summary bar.
- **`stage4DurationMs`**: Measured from `stage4_start` SSE to `complete` event in `useGenerationStream`.
- **Reset stale state**: `generationProgress`, `previewImage`, `modelMeta` reset at start of `executeWithStreaming` to prevent previous run's data leaking.
- **`useEdutainmentFacts('expert')` reused**: Same GPU stats polling composable, rotating facts filtered by audience level.
- **UI_MODE Pinia store**: New `src/stores/uiMode.ts` mirrors `safetyLevel.ts` pattern, fetched via `/api/settings/ui-mode`.

### Iterative Refinements (8 commits)
1. Initial implementation with two-phase layout + model profiles
2. Persist model summary below generated output + match preview to output dimensions
3. Fact-check model profiles (corrected FLUX architecture, SD3.5 params, licenses)
4. Collapse Phase B from multi-section to single compact stats line; fix summary bar (remove backend_type/model_size, add resolution/seed/CFG/steps); strengthen config bubble glow in all 4 views
5. Fix kWh staying at 0 — `watch(previewImage)` was resetting energy counters on phase transition
6. Phase switch by progress + add duration/kWh to post-generation summary
7. Fix missing `totalCo2Grams` destructure (type-check error)
8. Backend-aware phase detection — ComfyUI vs Diffusers loading heuristics

### Files Changed
| File | Change |
|------|--------|
| `src/components/edutainment/DenoisingProgressView.vue` | **NEW** ~300 lines, two-phase expert view |
| `src/stores/uiMode.ts` | **NEW** Pinia store for UI_MODE |
| `devserver/my_app/routes/settings_routes.py` | `/api/settings/ui-mode` endpoint |
| `devserver/my_app/routes/schema_pipeline_routes.py` | `model_meta` in `stage4_start` SSE + seed/cfg/steps from config_params |
| `src/composables/useGenerationStream.ts` | `modelMeta`, `stage4DurationMs`, reset at start |
| `src/components/MediaOutputBox.vue` | Expert view integration + summary bar + stats-snapshot handler |
| `src/views/text_transformation.vue` | Prop wiring (modelMeta, uiMode, stage4DurationMs) |
| `src/views/image_transformation.vue` | Prop wiring + config bubble glow |
| `src/views/multi_image_transformation.vue` | Prop wiring + config bubble glow |
| `src/views/music_generation.vue` | Config bubble glow |
| `src/views/text_transformation.css` | Config bubble glow |
| `src/i18n/en.ts` | 13 new `edutainment.denoising.*` keys + 📊→⚡/🔧/🌍 emoji fix |
| `src/i18n/de.ts` | Matching 📊 emoji fix |
| `src/i18n/WORK_ORDERS.md` | 3 work orders for batch translation |

### Known Issues (deferred to Session 221)
- **Model profiles hardcoded** in `MODEL_PROFILES` dict — should be in output config `meta` fields
- **ComfyUI (Qwen) shows empty stats** — seed/cfg/steps not available from query params or config_params for ComfyUI configs
- **3 i18n work orders pending** — need `./6_run_i18n_translator.sh --unattended`

---

## Session 219 - Real-Time Generation Progress via SSE (ComfyUI + Diffusers)
**Date:** 2026-02-27
**Focus:** Replace fake progress simulation with real backend-driven SSE progress events
**Commit:** `ad0d4d0` - feat(streaming): real-time generation progress via SSE (ComfyUI + Diffusers)

### Problem
Frontend faked generation progress with `setInterval` (100ms, linear to 90%). Users saw a smooth but meaningless animation that had no connection to actual backend state. During Stage 4, the SSE generator was blocked by `asyncio.run()` — no events could be emitted until generation completed.

### Solution: Thread + Dual-Source Polling
Generation now runs in a background thread. The main SSE generator thread emits real progress events based on the backend type:

| Backend | Mechanism | Preview | Data Source |
|---------|-----------|---------|-------------|
| ComfyUI | Push (WS callback → Queue) | Denoising JPEG | `on_progress` callback via ContextVar |
| Diffusers | Poll (HTTP, 1s interval) | None | `GET /api/diffusers/progress` |
| Others (HeartMuLa, StableAudio, OpenAI) | Heartbeat only | None | — |

### Changes

**Backend (Python):**
- **NEW** `devserver/schemas/engine/progress_callback.py` — ContextVar module for injecting ComfyUI's `on_progress` callback through the async call chain
- `backend_router.py` — All 3 `submit_and_track()` calls now pass `on_progress=get_progress_callback()`
- `schema_pipeline_routes.py` — Replaced blocking `asyncio.run()` with background thread + dual-source SSE event loop. Uses `contextvars.copy_context()` to propagate the callback into the thread.

**Frontend (TypeScript/Vue):**
- `useGenerationStream.ts` — Added `previewImage` ref + `generation_progress` event listener
- `MediaOutputBox.vue` — Added `previewImage` prop + 120x120 denoising preview thumbnail (bottom-right, fade transition, ComfyUI only)
- `text_transformation.vue`, `image_transformation.vue`, `multi_image_transformation.vue` — Removed ~40 lines of fake `setInterval` progress simulation each

### SSE Event Format
```
event: generation_progress
data: {"percent": 45, "preview": "data:image/jpeg;base64,/9j/...", "node": "KSampler"}
```

### Architecture Notes
- ContextVar propagation: `set_progress_callback()` in SSE generator → `contextvars.copy_context()` → thread → `get_progress_callback()` in backend_router → `submit_and_track(on_progress=...)`
- ComfyUI WS client already had `on_progress` parameter on `submit_and_track()` but it was never wired up
- Diffusers GPU service already had `/api/diffusers/progress` endpoint with step-level tracking
- Non-streaming code paths unaffected (ContextVar defaults to None, `on_progress=None` is safely ignored)

---

## Session 217 - LLM Inference Migration (CANCELLED)
**Date:** 2026-02-25 (approximate)
**Focus:** Attempted migration of LLM inference — aborted due to Mistral model switch disaster

### Note
This session was not logged at the time. It is referenced in Sessions 221 and 229:
- Mistral `mistral-large-latest` had silently switched to Large 3 (675B MoE) → 85s latency
- Plan "LLM Inference Migration" was cancelled
- Stabilized by pinning to `mistral-large-2411` (Large 2, 123B dense)

---

## Session 216 - Standalone ComfyUI Installation (SwarmUI-Abloesung)
**Date:** 2026-02-26
**Focus:** Replace SwarmUI's embedded ComfyUI with a standalone installation; fix WebSocket race condition and model availability fallback

### Problem
Direct ComfyUI WebSocket Client (COMFYUI_DIRECT) was unreliable against SwarmUI's embedded ComfyUI — WebSocket events not arriving consistently. Goal: own ComfyUI installation within the DevServer project so SwarmUI can be deleted.

### Changes

**Standalone ComfyUI (`dlbackend/ComfyUI/`)**
- Fresh ComfyUI v0.15.0 clone with own Python 3.13 venv + PyTorch 2.12.0+cu130 (Blackwell nightly)
- Models (~438GB) moved from `SwarmUI/Models/` to `dlbackend/ComfyUI/models/` (same filesystem, instant rename)
- Symlinks in `SwarmUI/Models/` point back for transition period
- Additional models from `SwarmUI/dlbackend/ComfyUI/models/` copied (qwen_image_edit, ltxv-distilled, stable-audio, t5-base)
- 13 ai4artsed custom nodes copied and verified
- `dlbackend/` added to `.gitignore`

**Startup Script (`2_start_comfyui.sh`)**
- Points to `$SCRIPT_DIR/dlbackend/ComfyUI` with its own venv
- No `--extra-model-paths-config` needed (standard ComfyUI paths)

**Config (`devserver/config.py`)**
- `COMFYUI_BASE_PATH` → `_SERVER_BASE / dlbackend / ComfyUI`
- Model paths (SD35, CLIP_L, CLIP_G, T5XXL) → `_COMFYUI_MODELS_PATH`
- `LORA_OUTPUT_DIR` → ComfyUI loras directory

**WebSocket Race Condition Fix (`comfyui_ws_client.py`)**
- Root cause: WS client connected AFTER submitting workflow via HTTP POST. If ComfyUI fired `execution_start` before WS was ready, `our_execution_started` stayed False and ALL events were silently dropped — client hung until timeout.
- Fix: Check `prompt_id` on every event, not just `execution_start`. Any matching event triggers tracking.

**Model Availability Fallback (`model_availability_service.py`)**
- When GPU service (diffusers/heartmula/stable_audio) is unavailable, now checks `meta.fallback_chunk` in the primary chunk for ComfyUI availability
- SD3.5 now appears as available even when GPU service is offline

**SD3.5 ComfyUI-First (`sd35_large.json` + chunk)**
- Config switched to `OUTPUT_CHUNK: "output_image_sd35_large"` (ComfyUI), `backend_type: "comfyui"`
- Chunk: `requires_workflow: true` to prevent Diffusers auto-redirect (DIFFUSERS_ENABLED bypass)
- Chunk: `fallback_chunk: "output_image_sd35_diffusers"` for when GPU service is available

### Commits
- `13117ce` fix(comfyui): enable direct mode by default, fix media type routing and WS race condition
- `b1927c2` feat(comfyui): standalone ComfyUI installation replacing SwarmUI dependency
- `fcf566f` fix(availability): check ComfyUI fallback when GPU service is unavailable
- `e129333` fix(comfyui-ws): fix race condition where execution_start fires before WS connects
- `dbb4b01` feat(sd35): switch to ComfyUI first, Diffusers fallback
- `939e0bd` fix(sd35): force ComfyUI workflow path, prevent Diffusers auto-redirect

### Lessons Learned
- SwarmUI had TWO model locations: `Models/` (top-level) AND `dlbackend/ComfyUI/models/` — must check both when migrating
- `SwarmUI/Models/Stable-Diffusion/` contained a `diffusion_models/` subdirectory that got nested wrong under `checkpoints/diffusion_models/`
- The `DIFFUSERS_ENABLED` auto-detection silently overrides `backend_type: "comfyui"` for image chunks — `requires_workflow: true` is the correct way to force ComfyUI workflow execution
- WebSocket race conditions are timing-dependent: worked with SwarmUI's slower embedded ComfyUI but failed with standalone (faster startup)

---

## Session 215 - Agentic Architecture Research
**Date:** 2026-02-26
**Focus:** Deep research into evolving AI4ArtsEd into an agentic platform with self-monitoring, experience accumulation, and knowledge distillation

### Context
With the maturation of agentic AI patterns (ICLR 2026 RSI Workshop, UNO Framework, Claude Opus 4.6), the platform can begin acting autonomously in defined areas: collecting experiences, self-monitoring, executing bounded skills, and training a diversity-aware prompt transformation model.

### Research Findings

**Existing agentic infrastructure** (more than expected):
- Wikipedia Research Loop = working ReAct-style agent (`pipeline_executor.py:496-720`)
- VRAMCoordinator = resource negotiation with LRU eviction
- SSE `user_activity` tracker = idle detector (5min timeout)
- ConfigLoader auto-discovery = plugin architecture
- 3,752 runs / 7.1 GB experience data already available

**State of the art** (web research):
- [UNO Framework](https://arxiv.org/abs/2602.06470) (ICLR 2026): Distills user logs into semi-structured rules + preference pairs, clusters by dual features, measures "cognitive gap" (tau*=0.45) to route between Primary/Reflective experience modules
- [Unsloth QLoRA](https://unsloth.ai): 2x faster LoRA training, ~4GB VRAM for qwen3:4b, supports all Qwen3 models
- [ICLR 2026 RSI Workshop](https://recursive-workshop.github.io/): Taxonomy of recursive self-improvement (parameters, memory, tools, architectures)

### Architecture: 5 Pillars + 6 Phases

| Pillar | Kern |
|--------|------|
| Experience Engine | JSON aggregation + session-aware narrative summaries (platform sensitivity) |
| Self-Monitoring Daemon | Daemon-thread in DevServer, 30s tick, health checks, idle detection |
| Skill System | AUTO/CONFIRM/MANUAL bounded autonomy |
| Prompt Intelligence | UNO-inspired rule extraction, experience hints in Stage 2, A/B framework |
| Pipeline Laboratory | Sandboxed `*_lab/` folders for agent-generated config experiments |

**Cross-cutting: Knowledge Distillation** — Claude Sonnet 4.6 (teacher) generates gold-standard transformations, qwen3:4b learns via QLoRA (student). English-channel for PI (translation per MediaBox). Diversity-aware training as core research contribution.

### Key Design Decisions
1. **Daemon-thread, not separate process** — dies with server, no hidden background processes
2. **English-channel for PI** — LoRA model only needs English, translation handled by existing qwen3:4b. Toggle per MediaBox (interface switch already exists)
3. **Platform sensitivity** — system develops narrative understanding of user intent through session-level analysis (not just statistics). Identifies creative engagement modes: identity expression, aesthetic pursuit, deconstruction, exploration, self-articulation, boundary-testing
4. **Diversity-aware training** — potentially first diversity-aware prompt transformation model. No cultural hierarchy, WIE-rules (perspective, description, perception) instead of "in the style of"
5. **Production data only** — workshop runs (`{uuid}_{date}` device IDs), dev-testing prompts filtered out

### Documents Created
- `docs/plans/agentic/MASTERPLAN.md` — overview + dependencies + key decisions
- `docs/plans/agentic/RESEARCH_NOTES.md` — UNO + QLoRA deep dives with full algorithms
- `docs/plans/agentic/phase-{0-5}-*.md` — 6 implementation-ready phase plans

### Commits
- `c84ccd7` docs: add agentic architecture research (masterplan + 6 phase plans)

---

## Session 214 - i18n Nightly Batch Translation & Automation
**Date:** 2026-02-26
**Focus:** Process all pending i18n work orders, audit key completeness, improve nightly automation

### Translation Work Completed
Processed all 8 pending work orders across 8 target languages (DE/TR/KO/UK/FR/ES/HE/AR):

| Commit | Scope | Files |
|--------|-------|-------|
| `1b64c92` | 7 .ts work orders + 6 poetry config JSONs | 15 files, 725 insertions |
| `8d7757c` | WO-7: he/ar for 33 interception configs + llama_guard_explanations | 35 files, 368 insertions |

**Work orders translated:**
- WO-2026-02-26 surrealizer-fusion-strategy (13 keys: 4 modified + 9 new)
- WO-2026-02-25 random-prompt-token-limit (1 key)
- WO-2026-02-25 sketch-canvas (11 keys)
- WO-2026-02-25 backend-status-dashboard (31 keys)
- WO-2026-02-24 trans-aktion-poetry-configs (6 JSON configs)
- WO-2026-02-23 hebrew-arabic-language-labels (2 keys)
- WO-2026-02-23 spanish-language-label (1 key)
- WO-2026-02-23 hebrew-arabic-interception-configs (33 JSONs + guard explanations)

### Audit Findings & Fixes
Ran automated audit comparing `en.ts` (1170 keys) against all 8 target files:
- **es.ts**: 2 missing keys (`arabicAr`, `hebrewHe`) — never backfilled after Session 201 added HE/AR
- **ar.ts**: `§86a` key encoding bug — `'\u00A786a'` written as key name instead of literal `§`
- **WO-5 file mismatch**: Work order listed `rilke/dickinson/whitman` but actual files were `sappho/mirabai/nahuatl/yoruba_oriki` — session renamed poets without updating WO
- **hunkydoryharmonizer.json**: Missed by background agent, fixed manually

### i18n Agent Improvements (`a0d43e8`, `51f7955`)

**Auto-Audit (Phase 1)**: Agent now compares en.ts keys vs all 8 targets at start of every run. Catches missing keys even when sessions forget to create work orders. Work orders remain necessary for MODIFIED keys (stale translations) and JSON interception configs.

**Unattended Mode**: `6_run_i18n_translator.sh` rewritten:
- `./6_run_i18n_translator.sh` — foreground, logs to `logs/i18n/`
- `./6_run_i18n_translator.sh --unattended` — tmux session, zero permission prompts
- Uses `--permission-mode bypassPermissions` + `--allowedTools "Read" "Edit" "Write" "Bash" "Glob" "Grep"`
- Prompt piped via stdin (`echo | claude -p`) — positional arg broken by `--allowedTools` variadic parsing

**Agent definition updated** (`.claude/agents/i18n-translator.md`):
- 5 → 8 target languages (added ES, HE, AR)
- 4-phase workflow: Auto-Audit → Work Orders → Validation → Commit
- Added interception config JSON translation rules
- Validation checks all 8 language files

### Technical Lessons
- `--allowedTools <tools...>` is variadic in Claude CLI — consumes all subsequent positional args. Must pipe prompt via stdin.
- `--permission-mode bypassPermissions` is the correct flag for unattended runs (not `--dangerously-skip-permissions`)
- Sonnet agent hit context limit on first attempt (7 WOs + 8 languages = too much in one pass). Splitting .ts and JSON into separate agents worked.
- Work order system is inherently unreliable for detecting ALL gaps — auto-audit is essential as safety net

### Commits
- `1b64c92` chore(i18n): translate 7 pending work orders (8 languages)
- `8d7757c` chore(i18n): add Hebrew + Arabic to all interception configs (WO-7)
- `a0d43e8` feat(i18n): add auto-audit + unattended nightly mode to translator
- `51f7955` fix(i18n): fix script argument parsing, rename --nightly to --unattended

---

## Session 213 - LoRA Training Auto-Captioning & LoRA Testing
**Date:** 2026-02-26
**Focus:** Integrate automatic VLM-based image captioning into the LoRA training pipeline; test trained LoRA via Diffusers and ComfyUI

### Context
User trained a LoRA on 25 scanned pages from "Photographie und Impressionismus — Landschaft 1850-1900". Images needed rotation (17/25 were sideways), EXIF stripping (stale thumbnails), and detailed captions for better training quality.

### Image Preparation (Manual/Script)
- **Rotation**: 17 of 25 images rotated 90° CCW via `mogrify -rotate 270` (landscape photos stored in portrait orientation)
- **EXIF Strip**: `mogrify -strip *.jpg` — removed stale embedded thumbnails that showed pre-crop versions in file managers
- **Captioning Script**: `generate_captions.py` — sent each image to VLM via Ollama, wrote `.txt` captions alongside images

### Auto-Captioning Integration (Platform Feature)
Integrated automatic captioning into `training_service.py` so uploaded images get VLM-generated descriptions before Kohya starts.

**Two-stage approach** (handles qwen3-vl thinking mode):
1. **Stage 1**: `qwen3-vl:32b` describes the image via Ollama `/api/chat`
2. **Stage 2**: If output contains chain-of-thought reasoning (detected by prefix heuristic), `mistral-nemo:latest` extracts the clean caption

**Flow**: User uploads images → `create_project()` saves them → `start_training_process()` calls `_generate_captions()` in background thread (SSE-streamed) → Kohya reads `.txt` files automatically

**qwen3-vl thinking mode lessons**:
- `/no_think` in user message: unreliable for VL models
- `"think": false` API parameter: doesn't work (known Ollama bug for qwen3 variants)
- Short prompts sometimes avoid thinking; complex prompts trigger it
- Solution: detect reasoning prefixes ("Got it", "We are", etc.) → send to non-thinking model (mistral-nemo) for extraction

### LoRA Testing Results
- **Diffusers**: Kohya SD3 LoRA keys (`lora_unet_*`, `lora_te1_*`, `lora_te2_*`) NOT auto-converted by Diffusers. No SD3-specific Kohya converter exists in `diffusers.loaders.lora_conversion_utils`. Added graceful fallback (`prefix=None` + catch `set_adapters` ValueError).
- **ComfyUI**: LoRA loads and applies correctly via `LoraLoader` node. Clear visual difference (grain, tonality, paper texture) confirmed.
- **Conclusion**: ComfyUI remains the reliable path for LoRA generation. Diffusers SD3 LoRA support is an upstream gap.

### Config Additions (`devserver/config.py`)
- `CAPTION_VLM_MODEL = "qwen3-vl:32b"`
- `CAPTION_CLEANUP_MODEL = "mistral-nemo:latest"`
- `CAPTION_ENABLED = True`

### Files Changed
| File | Change |
|------|--------|
| `devserver/config.py` | +3 captioning config entries |
| `devserver/my_app/services/training_service.py` | `_generate_captions()`, `_cleanup_caption()`, integration in training flow |
| `gpu_service/services/diffusers_backend.py` | Graceful Kohya SD3 LoRA handling (`prefix=None`, catch ValueError) |

### Commits
- `a9eb6fd` feat(training): auto-caption uploaded images via VLM before LoRA training
- `f8c47d5` fix(lora): handle Kohya SD3 LoRA format in Diffusers backend gracefully

## Session 212 - Sketch Toggle into MediaInputBox (Platform-Wide Sketch Input)
**Date:** 2026-02-26
**Focus:** Move sketch canvas toggle from page-level (hardcoded in `image_transformation.vue`) into `MediaInputBox` as a reusable `allowSketch` prop — enabling sketch input across all image MediaInputBoxes on the platform

### Kunstpädagogischer Hintergrund

Skizzieren ist nicht nur eine alternative Eingabeform, sondern eine fundamental andere Denkbewegung als Bild-Upload. Beim Zeichnen entsteht die Intention im Prozess — der Strich ist gleichzeitig Exploration und Festlegung. Kinder und Jugendliche, die kein "passendes" Foto haben, können dennoch eine visuelle Idee formulieren. Das macht img2img-Pipelines (Flux, Qwen) pädagogisch erst vollständig: nicht nur "Was habe ich?" (Upload) sondern "Was stelle ich mir vor?" (Sketch).

Session 210 führte SketchCanvas als Komponente ein, verankerte die Toggle-Logik aber als Page-Level-Hack in `image_transformation.vue`. Diese Session hebt den Sketch-Toggle auf Komponentenebene — jede Seite, die `allow-sketch` an MediaInputBox übergibt, bekommt den Upload/Sketch-Wechsel geschenkt.

### Implementation

- **MediaInputBox.vue**: Neuer Prop `allowSketch: boolean` (default `false`). Interner Ref `sketchMode`. Wenn `allowSketch && inputType === 'image'`: Toggle-Buttons zwischen Header und Content, wechselt intern zwischen `ImageUploadWidget` und `SketchCanvas`. `'sketch'` als externer `inputType`-Wert entfernt — Sketch ist jetzt ein interner Modus.
- **image_transformation.vue**: Gesamte externe Toggle-Logik entfernt (`imageInputMode` Ref, `<div class="image-input-column">`, Toggle-Buttons-Template, `.image-input-column`/`.input-mode-toggle`/`.mode-btn` CSS, globaler CSS-Override). Ersetzt durch einfaches `:allow-sketch="true"`.
- **multi_image_transformation.vue**: `:allow-sketch="true"` an alle 3 aktiven Bild-MediaInputBoxes.
- **crossmodal_lab.vue**: `:allow-sketch="true"` an beide Bild-MediaInputBoxes (mmaudio + guidance).

### Files Changed
| File | Change |
|------|--------|
| `src/components/MediaInputBox.vue` | `allowSketch` prop, internal `sketchMode`, toggle template+CSS, removed `'sketch'` from inputType union |
| `src/views/image_transformation.vue` | Removed all external sketch toggle code, simplified to `:allow-sketch="true"` |
| `src/views/multi_image_transformation.vue` | Added `:allow-sketch="true"` to 3 image boxes |
| `src/views/latent_lab/crossmodal_lab.vue` | Added `:allow-sketch="true"` to 2 image boxes |

---

## Session 211 - Surrealizer Fusion Strategy Redesign
**Date:** 2026-02-26
**Focus:** Fix fundamental misunderstanding in Surrealizer T5-CLIP fusion — T5 tokens beyond 77 were appended unchanged, diluting surreal effect on long prompts

### Background

Code audit of the original ComfyUI `ai4artsed_t5_clip_fusion` node revealed that T5 tokens beyond position 77 are appended **unchanged** to the fused embedding. The Diffusers translation faithfully replicated this behavior. Previous sessions documented these unmodified tokens as a "semantic anchor" — but the original design intent was to extrapolate **all** T5 vectors, not just the first 77. With short prompts (<75 tokens) the effect is invisible because all tokens fall within the LERP zone. With long prompts (~500 T5 tokens), 400+ unmodified tokens at 1× magnitude overwhelm 77 extrapolated tokens at 25× — diluting the hallucination effect dramatically.

### Analysis: Attention Economics in MMDiT

The SD3.5 MMDiT gives attention to all text tokens via joint self-attention. Token magnitude directly influences softmax attention weights. Three strategies were designed:

1. **`dual_alpha`** (new default): Core α (α×0.15) on first 77 tokens preserves structural recognizability via CLIP-L; full α on tokens 78+ creates aesthetic surprise. Designed for "kontingente Ähnlichkeit" — the image is recognizable but the execution surprises.
2. **`normalized`**: Uniform α on all positions (CLIP=0 beyond 77, so tokens 78+ get α×T5), then L2-normalize each token embedding to mean T5 magnitude. Same direction as dual_alpha but with controlled magnitude — no tokens dominate attention.
3. **`legacy`**: Original behavior preserved for comparison. LERP first 77, append rest unchanged.

### Implementation

Full pipeline from frontend to GPU service (10 files initially, refined in follow-up commit):
- GPU service: `diffusers_backend.py` strategy-aware `_fuse_prompt`, `diffusers_routes.py` passthrough
- DevServer: `diffusers_client.py`, `diffusers_backend.py` (in-process fallback), `backend_router.py`, `schema_pipeline_routes.py`
- Frontend: `surrealizer.vue` — Fusion Strategy as central button-group selector (not hidden in Advanced Settings), seed control as text input (not number spinner) in Advanced Settings
- i18n: Info text rewritten to organically weave all three strategies into the explanation

### Files Changed
| File | Change |
|------|--------|
| `gpu_service/services/diffusers_backend.py` | 3-strategy `_fuse_prompt` in `generate_image_with_fusion()` |
| `gpu_service/routes/diffusers_routes.py` | Pass `fusion_strategy` parameter |
| `devserver/my_app/services/diffusers_client.py` | Add `fusion_strategy` to HTTP client |
| `devserver/my_app/services/diffusers_backend.py` | Mirror 3 strategies in in-process fallback |
| `devserver/schemas/engine/backend_router.py` | Read `fusion_strategy` from params, default `dual_alpha` |
| `devserver/my_app/routes/schema_pipeline_routes.py` | Extract `fusion_strategy` from request, pass to custom_params |
| `devserver/schemas/chunks/output_image_surrealizer_diffusers.json` | Add `fusion_strategy` input mapping, default `dual_alpha` |
| `src/views/surrealizer.vue` | Strategy button group, seed text input, session persistence |
| `src/i18n/en.ts` | Rewritten info/purpose/tech texts, 10 new keys |
| `src/i18n/WORK_ORDERS.md` | Translation work order for all new/modified keys |

---

## Session 210 - Sketch Canvas for Image Transformation
**Date:** 2026-02-25
**Focus:** Let kids draw a freehand sketch in the browser that feeds into img2img pipelines
**Note:** Toggle logic refactored into MediaInputBox in Session 212 — page-level toggle code removed, replaced by `allowSketch` prop

### Implementation

Extended `MediaInputBox` with a third `inputType: 'sketch'` — parallel to `'text'` and `'image'`. New `SketchCanvas.vue` component provides an HTML5 Canvas drawing surface with pointer events (`touch-action: none` for tablet/stylus), pen/eraser tools, 3 brush sizes, undo stack (max 20 snapshots), and a "Done" button that exports PNG → uploads via `/api/media/upload/image` → emits the identical `image-uploaded` / `image-removed` event contract as `ImageUploadWidget`. Parent components don't know or care whether the image came from file upload or drawing.

On `image_transformation.vue`, a small upload/sketch toggle above the image input box lets users switch modes. The rest of the page (context prompt, category selection, model bubbles, generation) stays unchanged — existing `flux2_img2img` / `qwen_img2img` configs work with any input image.

No new backend routes, pipelines, or output configs needed.

### Files Changed
| File | Change |
|------|--------|
| `src/components/SketchCanvas.vue` | NEW — freehand drawing canvas with toolbar + upload |
| `src/components/MediaInputBox.vue` | Added `'sketch'` inputType, SketchCanvas branch |
| `src/views/image_transformation.vue` | Upload/sketch toggle, `imageInputMode` ref, CSS |
| `src/i18n/en.ts` | `sketchCanvas.*` (9 keys) + `imageTransform.uploadMode/sketchMode` |
| `src/i18n/WORK_ORDERS.md` | Translation work order for 11 new keys |

---

## Session 209 - Trans-Aktion: Parameter Pipeline Fix + Global Poet Lineup
**Date:** 2026-02-24
**Focus:** Wire generation parameters through pipeline, fix collision prompts, diversify poet selection

### Problems Solved

1. **Parameters silently dropped**: `temperature`, `max_tokens`, `repetition_penalty` from config JSON never reached `generate()`. Chain: Config → ChunkBuilder (merged) → `_process_prompt_interception_request()` → `PromptInterceptionRequest` (no field) → `_call_ollama()` (no params) → `llm_client.generate()` (never received them).

2. **Thinking mode wasted tokens**: Qwen3's `apply_chat_template()` enables `<think>` by default, consuming token budget on garbled CoT before any output.

3. **Prompt architecture violation**: Initial fix put "MATERIAL A / MATERIAL B / RULES" labels in config `context` field — redundant with PI architecture's `task_instruction` from `instruction_selector.py`. Context should be material only, not meta-instructions.

4. **Western canon bias**: 4M/1F, all Western/Japanese. Replaced with global lineup.

### Implementation

**Parameter pipeline** (5 Python files): Added `repetition_penalty` + `enable_thinking` through all 5 layers: `llm_inference_backend.py` → `llm_inference_routes.py` → `llm_client.py` → `prompt_interception_engine.py` → `backend_router.py`. Ollama fallback maps `repetition_penalty` → `options.repeat_penalty`, `enable_thinking=False` → `payload["think"] = False`.

**Config updates**: `temperature` 0.95→0.85, `repetition_penalty: 1.5`, `enable_thinking: false`. Context: poem fragments (not full text) + minimal fusion instruction. No meta-labels.

**UI**: Quill icon (history_edu SVG) for `trans_aktion` category, `#FF1744` color, shortened tile names (just poet names).

**New poet lineup** (6 configs, 2F + 2M + 2 collective):

| Config | Source | Origin | Type |
|--------|--------|--------|------|
| `trans_aktion_sappho.json` | Sappho, Fragment 31 | Greece, ~600 BCE | F |
| `trans_aktion_hoelderlin.json` | Hoelderlin, Haelfte des Lebens | Germany, 1805 | M |
| `trans_aktion_basho.json` | Basho, 3 Haiku | Japan, 17th c | M |
| `trans_aktion_mirabai.json` | Mirabai, Bhajans | India, ~1500 | F |
| `trans_aktion_yoruba_oriki.json` | Yoruba Oriki (Oya) | West Africa, oral tradition | collective |
| `trans_aktion_nahuatl.json` | Nahuatl Xochicuicatl | Mesoamerica, oral tradition | collective |

### Known Issue: Fallback Defeats model_override

When GPU is full (e.g. Flux2 loaded), `qwen3:1.7b` fails with OOM → fallback chain escalates to Mistral Large (cloud) → collision doesn't happen because model is too capable. Needs: either Ollama GGUF fallback only, or fail instead of silent escalation. VRAM eviction fix is Flux2-session scope.

### Files Changed (10 + 1 new)
| File | Change |
|------|--------|
| `gpu_service/services/llm_inference_backend.py` | `repetition_penalty`, `enable_thinking` in generate/chat |
| `gpu_service/routes/llm_inference_routes.py` | Extract + pass new params |
| `devserver/my_app/services/llm_client.py` | API + Ollama mapping for new params |
| `devserver/schemas/engine/prompt_interception_engine.py` | `parameters` dict in dataclass, pass to LLM call |
| `devserver/schemas/engine/backend_router.py` | Pass `parameters` to PromptInterceptionRequest |
| `devserver/schemas/configs/interception/trans_aktion_*.json` (×6) | New poets + params + fragments |
| `public/.../PropertyBubble.vue` | Quill SVG for trans_aktion |
| `public/.../PropertyCanvas.vue` | trans_aktion color in categoryColorMap |

---

## Session 208 - Trans-Aktion: Real Poetry as Collision Material
**Date:** 2026-02-24
**Focus:** Replace AI-generated collision materials with genuine poetry

### Background

Session 207.5 developed the Trans-Aktion concept: **Material-Kollision** via model insufficiency. A deliberately tiny LLM (qwen3:1.7b) receives two semantically alien texts — the user's prompt and a "collision material" — and attempts to fuse them. The model is large enough to understand the task but too small for a smooth synthesis. The structural failure produces genuine contingency.

The PoC succeeded (commit `447ea3a`): a prompt "Ein Waldspaziergang am Sonntagmorgen" collided with crystallography text yielded a Baumquerschnitt that was simultaneously wood and crystal.

### Problem: AI-Generated Collision Material = Anthropomorphized Compliance

The initial collision materials (crystallography, surgical anatomy, astronomy, bureaucracy, culinary) were AI-generated. This contradicts the core concept: LLM-generated "foreign" text is itself shaped by RLHF compliance patterns — it's "anthropomorphized sameness," not genuine alterity. Real collision requires material with its own materiality: rhythm, sound, history, cultural weight.

### Solution: Public-Domain Poetry

Replaced all 5 configs with genuine poems (all public domain, all age-appropriate 8-17):

| Config | Poet | Poem | Year | Character |
|--------|------|------|------|-----------|
| `trans_aktion_rilke.json` | Rilke | Der Panther | 1902 | Dense, spatial, bodily |
| `trans_aktion_hoelderlin.json` | Hoelderlin | Haelfte des Lebens | 1805 | Extreme fullness/emptiness contrast |
| `trans_aktion_basho.json` | Basho | 3 Haiku | 17th c. | Maximum compression, JP+DE bilingual |
| `trans_aktion_dickinson.json` | Dickinson | A Bird came down the Walk | ~1862 | Precise observation → uncanny beauty |
| `trans_aktion_whitman.json` | Whitman | Song of Myself §31 | 1855 | Expansive, cataloguing, bodily |

### Technical Details

- Renamed `trans_aktion.json` → `trans_aktion_rilke.json` (Rilke replaces crystallography)
- Deleted 4 AI-slop configs (chirurgisch, astronomisch, buerokratisch, kulinarisch)
- Created 4 new poet-named configs (hoelderlin, basho, dickinson, whitman)
- All configs: identical structure, `model_override: "qwen3:1.7b"`, `temperature: 0.95`, `max_tokens: 400`
- Context instruction pattern: poem text + "Write a single text where the poem above and the prompt below become inseparable"
- Basho config uses Japanese originals alongside German translations (bilingual collision)
- Dickinson/Whitman: English originals in both `en` and `de` context (the poem IS the material, not a translation target)

### Key Insight

The three contingency sources identified in the Trans-Aktion concept:
1. **Model insufficiency** (qwen3:1.7b can't smoothly synthesize) ✓ implemented
2. **Domain mismatch** (poem ↔ prompt semantic distance) ✓ now with genuine material
3. **Vector operations** (Surrealizer-style latent space manipulation) → future work

### Files Changed
| File | Changes |
|------|---------|
| `devserver/schemas/configs/interception/trans_aktion_rilke.json` | NEW (renamed from trans_aktion.json, Rilke replaces crystallography) |
| `devserver/schemas/configs/interception/trans_aktion_hoelderlin.json` | NEW |
| `devserver/schemas/configs/interception/trans_aktion_basho.json` | NEW |
| `devserver/schemas/configs/interception/trans_aktion_dickinson.json` | NEW |
| `devserver/schemas/configs/interception/trans_aktion_whitman.json` | NEW |
| `devserver/schemas/configs/interception/trans_aktion_chirurgisch.json` | DELETED |
| `devserver/schemas/configs/interception/trans_aktion_astronomisch.json` | DELETED |
| `devserver/schemas/configs/interception/trans_aktion_buerokratisch.json` | DELETED |
| `devserver/schemas/configs/interception/trans_aktion_kulinarisch.json` | DELETED |
| `public/ai4artsed-frontend/src/i18n/WORK_ORDERS.md` | Added WO for tr/ko/uk/fr/es/he/ar translations |

### Research: Why the Collision Failed (Rilke Test)

First test with real poetry (Rilke + "Waldspaziergang mit Hund und Kind") showed: model echoes poem verbatim, then writes a separate conventional text. No fusion. Systematic literature review revealed multiple converging causes:

**1. Qwen3 Thinking Mode ON by default** — Both transformers (`apply_chat_template`) and Ollama generate `<think>` blocks, consuming token budget on garbled reasoning before output. `llm_inference_backend.py` extracts them post-hoc but the tokens are already spent. Fix: `/no_think` in system prompt or suppress `<think>` token generation.

**2. No repetition penalty** — `repetition_penalty: 1.5` in transformers `gen_kwargs` (Qwen3's own recommendation). Currently not passed through `llm_inference_backend.py` at all. Single highest-impact parameter.

**3. Induction Head Toxicity** (ACL 2025, arXiv 2504.14218) — Attention heads copy patterns from context. RLHF models have prior toward preserving user input verbatim. Formatted poem = immutable block.

**4. CS4 Constraint Degradation** (arXiv 2410.04197) — Small models satisfy easiest constraints, drop hard ones. "Include poem" (easy: copy) + "include prompt" (easy: write about) + "make inseparable" (hard: dropped).

**5. LLM-Prompted Fusion is fundamentally wrong** — EBR cut-up study (2024): even GPT-4o inserts "thematic materials." CHI 2024: LLMs produce "convergent, mid-novelty outputs." Research consistently identifies prompted fusion as lowest-genuineness approach.

**Solution: Three-layer collision architecture:**
1. Mechanical (no model): N+7, sentence-interleaving, SpaCy-based
2. Insufficient model (qwen3:1.7b, `/no_think`, `presence_penalty: 1.5`): partial-failure art
3. Embedding (future): SLERP between T5 encodings → diffusion model conditioned on mathematical phantom

Full analysis with 20+ sources documented in `docs/DEVELOPMENT_DECISIONS.md` under "Trans-Aktion: Forschungsstand und Konsequenzen".

### Next Steps
1. Add `repetition_penalty` support to `llm_inference_backend.py` gen_kwargs + `llm_client.py` API (currently no penalty parameter at all)
2. Disable thinking for Trans-Aktion: `/no_think` in system prompt via config context, or suppress `<think>` token generation in transformers
3. Prompt restructure: fragment poem, use completion mode, concrete constraints — empirical testing
4. Mechanical pre-processing layer (SpaCy sentence-interleaving + N+7) as Python chunk
5. SLERP on T5 embeddings (connects to T5 SAE research, Session 192)
6. Test across SD3.5/FLUX/Wan2.1

---

## Session 207.5 - Trans-Aktion Concept PoC
**Date:** 2026-02-25 (approximate)
**Focus:** Material-Kollision via model insufficiency — Trans-Aktion concept development

### Note
This session was not logged at the time. Referenced in Session 208:
- Deliberately tiny LLM (qwen3:1.7b) receives two semantically alien texts
- PoC succeeded (commit `447ea3a`)

---

## Session 207 - GPU Service VRAM/RAM Bugs: LLM Migration + Flux2
**Date:** 2026-02-24
**Focus:** Fix 4 critical VRAM/RAM management bugs in GPU Service

### Background
The LLM-Inference-Migration (commit `ac047ce`) introduced 3 bugs. Testing also revealed a 4th bug in DiffusersBackend that made Flux2 via Diffusers unusable. Previous sessions (2-3) had failed to get Flux2 working through the GPU Service.

### Bug 1: VRAM Overhead — `device_map="auto"` (LLM + Text Backend)
**Problem:** `device_map="auto"` in both `llm_inference_backend.py` and `text_backend.py` creates CPU-staging + GPU-residency simultaneously. Qwen3-4B consumed 36GB instead of ~8GB.

**Fix:** Removed `device_map="auto"`, added explicit `model.to(device)` after `from_pretrained()` — same pattern DiffusersBackend uses.

**Result:** Qwen3-4B: 7698 MB (was 36000 MB). Llama-Guard-3-1B: 2864 MB.

### Bug 2: Global `_load_lock` Blocking All Requests
**Problem:** A single `threading.Lock()` serialized ALL model loads. Loading safety model blocked translation, chat, interception — everything queued behind one download.

**Fix:** Per-model locks with double-checked locking pattern. `_model_locks` dict protected by lightweight `_model_locks_lock`. Fast path (already loaded) needs no lock at all.

**Result:** Qwen3-4B and Llama-Guard-3-1B load concurrently, no mutual blocking.

### Bug 3: Ollama Fallback for `qwen3:4b`
**Problem:** `qwen3:4b` is `LOCAL_DEFAULT_MODEL` but was missing from Ollama. GPU Service error → Ollama fallback → model not found → silent failure.

**Fix:** `ollama pull qwen3:4b` (one-time).

### Bug 4: Flux2 — The One That Failed 2-3 Sessions

**The core challenge:** Flux2-dev is ~106GB in float32 / ~24GB in bf16. With 96GB VRAM and 64GB RAM, loading strategy is critical. Previous sessions tried various approaches and failed.

**Phase 1 — Initial fixes (3 layered):**

1. **`enable_model_cpu_offload()` instead of `.to(device)`** — The original code did `pipe.to(self.device)` which tries to load the entire model onto GPU at once. For Flux2 at 106GB float32, this overflows VRAM into RAM+swap. `enable_model_cpu_offload()` keeps components in CPU RAM and moves them to GPU one-at-a-time during inference. Peak VRAM ~63GB during generation.

2. **`torch_dtype` vs `dtype` — library-specific behavior** — `transformers` migrated to `dtype`, but `diffusers` 0.36.0 is inconsistent. `Flux2Pipeline.from_pretrained()` **silently ignores** `dtype` ("not expected...will be ignored"). Solution: dynamic `dtype_key` — `"torch_dtype"` for Flux2, `"dtype"` for all other pipelines.

3. **Flux2Pipeline-specific generation kwargs:**
   - `negative_prompt` → unsupported, raises TypeError. Fix: skip for Flux/Flux2 pipelines.
   - `torch.Generator(device=self.device)` → crashes with CPU offload. Fix: `device="cpu"` when using `enable_model_cpu_offload()`.

**Phase 2 — The real breakthrough: component-level loading**

Phase 1 worked but was painfully slow: `Flux2Pipeline.from_pretrained()` silently ignores `torch_dtype` and loads ALL weights in float32 (~106GB into 64GB RAM + 70GB swap). The subsequent `pipe.to(bfloat16)` cast added minutes of CPU work. Total load time: several minutes with the system nearly unusable.

**Key discovery:** The safetensors files on disk are already bfloat16 (verified with `safe_open`). The float32 doubling happens entirely inside `from_pretrained` because Flux2Pipeline doesn't pass `torch_dtype` through to its subcomponents.

**Solution:** `_load_flux2_pipeline()` loads each component individually — `Flux2Transformer2DModel`, `AutoModelForImageTextToText` (Mistral3), `AutoencoderKLFlux2`, `PixtralProcessor`, `FlowMatchEulerDiscreteScheduler` — with explicit `torch_dtype=bfloat16`. These component classes DO respect the kwarg. Then assembles the pipeline manually via `Flux2Pipeline(transformer=..., text_encoder=..., ...)`.

**Result:**
- RAM: 1.2 GB (was 106 GB) — `low_cpu_mem_usage=True` memory-maps tensors from disk
- Load time: 4 seconds (was several minutes)
- Generation: 2:03 at 1024x1024 (20 steps, ~6s/step)
- Peak VRAM: ~63 GB during generation, released after

**Why previous sessions failed:** Each session hit a different layer of the problem — `.to(device)` OOM, `dtype` silently ignored, `negative_prompt` TypeError, generator device mismatch — but couldn't see all of them together. The component-level loading was the key insight that none of the previous sessions reached.

### Additional Fixes
- **Stale `'eco'` argument** in `schema_pipeline_routes.py:2383` — leftover from Session 205's `execution_mode` removal, caused TypeError in Stage 3 streaming path.
- **Flux2 config consolidation** — `flux2.json` now points to Diffusers chunk (primary) with ComfyUI fallback, matching SD3.5 pattern. Removed redundant `flux2_diffusers.json` and `flux2_fp8.json`.

### Files Changed
| File | Changes |
|------|---------|
| `gpu_service/services/llm_inference_backend.py` | Remove `device_map="auto"`, add `.to(device)`, per-model locks |
| `gpu_service/services/text_backend.py` | Remove `device_map="auto"`, add `.to(device)`, `torch_dtype`→`dtype` (transformers) |
| `gpu_service/services/diffusers_backend.py` | `_load_flux2_pipeline()` component-level bf16, dynamic `dtype_key`, skip `negative_prompt`, CPU generator |
| `devserver/my_app/routes/schema_pipeline_routes.py` | Remove stale `'eco'` arg from Stage 3 call |
| `devserver/schemas/configs/output/flux2.json` | Switch to Diffusers primary with ComfyUI fallback |
| `devserver/schemas/configs/output/flux2_diffusers.json` | Deleted (redundant) |
| `devserver/schemas/configs/output/flux2_fp8.json` | Deleted (redundant) |

### Commits
- `c447791` — `fix(gpu-service): VRAM/RAM management bugs in LLM + Diffusers backends`
- `e73c08c` — `fix(diffusers): Flux2Pipeline negative_prompt + generator device`
- `0c9affb` — `docs: Add Session 207 devlog`
- `42c6caf` — `refactor(flux2): Diffusers primary with ComfyUI fallback (like SD3.5)`
- `f5c0181` — `fix: remove leftover 'eco' execution_mode arg from Stage 3 call`
- `39779d2` — `fix(diffusers): use dtype for modern pipelines, torch_dtype for Flux2`
- `f790cb3` — `fix(diffusers): Flux2 bf16 cast before CPU offload`
- `4e987fd` — `perf(diffusers): Flux2 component-level bf16 loading (1.2GB RAM, 4s)`

### Key Lessons (for future sessions)
- **`device_map="auto"` is not free** — it creates CPU mirror + GPU copy. For models that fit in VRAM, explicit `.to(device)` is always better.
- **`torch_dtype` vs `dtype` is library-specific** — transformers uses `dtype`, diffusers still uses `torch_dtype`. Flux2Pipeline silently ignores BOTH. Always verify with `safetensors.safe_open()` and `psutil` whether kwargs are actually being applied.
- **`Flux2Pipeline.from_pretrained` is broken for dtype** — it doesn't pass `torch_dtype` to subcomponents. Load components individually with explicit dtype, then assemble. This is likely a diffusers bug that will be fixed eventually.
- **`low_cpu_mem_usage=True` on components = memory-mapped loading** — tensors reference disk directly, not copied to RAM. This is why 105GB of weights load in 1.2GB RAM.
- **`enable_model_cpu_offload()` has side effects** — generator must be on CPU, not GPU. `negative_prompt` not supported by Flux/Flux2.
- **Per-model locking > global locking** — for multi-model services, a single lock serializes everything. Double-checked locking with per-model granularity eliminates cross-model contention.

---

## Session 206 - Complete Hebrew and Arabic i18n Translations
**Date:** 2026-02-24
**Focus:** Full translation of all ~1370 i18n keys into Hebrew (he) and Arabic (ar)

### Background
Hebrew and Arabic infrastructure (stub files, index.ts imports, SUPPORTED_LANGUAGES with `dir: 'rtl'`) was added in Session 201. Both `.ts` files were empty stubs falling back to English. This session populates them with complete translations.

### Changes

**Hebrew (`he.ts`)** — 1369 lines added
- Single-pass translation by i18n-translator agent
- All 30 top-level sections translated
- `vue-tsc --build` and `npm run build-only` passed

**Arabic (`ar.ts`)** — 1367 lines added
- Initial single-agent attempt hit 32K output token limit
- Successfully completed via 3-way parallel split (parts 1-3), then assembled
- All sections translated in Modern Standard Arabic (MSA)
- Western numerals (0-9) used throughout
- `vue-tsc --build` and `npm run build-only` passed

**WORK_ORDERS.md** — Both work orders moved from Pending to Completed

### Translation Quality Notes
- All template variables preserved (`{count}`, `{watts}`, `{co2}`, etc.)
- All Unicode escapes preserved (`\u2014`, `\u2212`, `\u00d7`, etc.)
- `{'|'}` vue-i18n pipe escape syntax preserved
- All technical terms kept as-is (GPU, VRAM, CLIP, T5, CFG, LLM, MMDiT, etc.)
- Brand/model names preserved verbatim
- Emoji prefixes preserved in edutainment section

### Commits
- `fdf120c` — `chore(i18n): Add complete Hebrew (he) translation — all ~1370 keys`
- `7daedaa` — `chore(i18n): Add complete Arabic (ar) translation — all ~1370 keys`

### Remaining Pending Work Orders
- `WO-2026-02-23-hebrew-arabic-language-labels` — language label translations in de/tr/ko/uk/fr/es
- `WO-2026-02-23-hebrew-arabic-interception-configs` — he/ar entries in 36 interception JSON files
- `WO-2026-02-23-spanish-language-label` — Spanish language label in other language files

---

## Session 205 - Remove Deprecated execution_mode (eco/fast) Parameter
**Date:** 2026-02-23
**Focus:** Remove the deprecated execution_mode parameter that threaded through ~80 call sites across ~50 files but did nothing

### Background
`execution_mode` ("eco"/"fast") was deprecated in Session 55. Model selection moved to centralized `config.py` STAGE*_MODEL variables. The parameter persisted as dead code — always defaulted to "eco", and the only consumer (`lookup_output_config`) just did `defaults[media_type].get("eco")`. The "fast" mode was never sent by any client.

### Changes (50 files, -314/+65 lines)

**Backend — Core pipeline:**
- `output_config_defaults.json` — flattened from `{"image": {"eco": "sd35_large", "fast": "gpt5_image"}}` to `{"image": "sd35_large"}`
- `schema_pipeline_routes.py` — removed from ~40 sites (function signatures, data.get(), call sites, log messages)
- `stage_orchestrator.py` — removed from all 6 stage execution functions
- `pipeline_executor.py` — removed from execute_pipeline, stream_pipeline, all internal methods
- `output_config_selector.py` — removed from class, simplified to flat lookup
- `pipeline_recorder.py` — removed from constructor, get_recorder, load_recorder
- `execution_history/models.py` — removed field from ExecutionRecord
- `execution_history/tracker.py` — removed from constructor and finalize methods
- 5 route files (media, favorites, settings, pipeline, execution) — removed from response dicts

**Frontend:**
- `api.ts` — removed from PipelineExecuteRequest and TransformRequest interfaces
- `pipelineExecution.ts` — removed executionMode ref, setExecutionMode action
- `PipelineExecutionView.vue` — removed eco/fast/best selector UI
- `Phase2VectorFusionInterface.vue` — removed executionMode prop
- `text_transformation.vue`, `SessionExportView.vue`, `favorites.ts` — removed references
- All 7 i18n files (en, de, tr, ko, uk, fr, es) — removed `executionModes` keys

**Tests:** 19 test files cleaned (mechanical removal of `execution_mode='eco'` from payloads)

**Deleted:** `docs/archive/REFACTORING_PLAN_EXECUTION_MODE_REMOVAL.md` (now executed)

### Not Changed (intentionally)
- `backend_router.py` — chunk-level `execution_mode` ("legacy_workflow"/"standard") is a different concept, actively used for ComfyUI routing
- `model_selector.py` — used for model discovery, unrelated
- Chunk JSON files — `"execution_mode": "legacy_workflow"` fields are chunk routing, not request params

### Verification
- `npm run type-check` — zero errors
- All Python files parse clean (AST verified)
- Grep confirms zero remaining request-parameter `execution_mode` references in active code
- Backend smoke tests (all pass):
  1. `GET /api/schema/info` — 116 schemas loaded
  2. `GET /api/models/availability` — GPU service reachable
  3. `POST /api/schema/pipeline/safety` — `safe: true` (Stage 1 safety without execution_mode)
  4. `POST /api/schema/pipeline/stage2` — full Stage 1→2 pipeline (overdrive, 17s) — interception + optimization complete, zero parameter errors

---

## Session 204 - TODO List Cleanup (~2100 → ~220 Lines)
**Date:** 2026-02-23
**Focus:** Purge obsolete items from devserver_todos.md, update statuses from DevLog

### Problem
`docs/devserver_todos.md` had grown to ~2100 lines over 200+ sessions. Most content was completed work from Sessions 14-135 (Nov-Dec 2025), already documented in DEVELOPMENT_LOG.md. Several items from Sessions 36-98 were obsolete due to architectural changes but never removed.

### Changes

**Removed (completed, documented in DevLog):**
- 15+ completed features: Execution History Tracker, Unified Media Storage, LivePipelineRecorder, v2.0.0-alpha.1 release, Pipeline Rename, GPT-OSS Stage 1/3, keep_alive, Model Availability Check, Prompt Optimization Fix, Crossmodal Lab install, etc.
- Redundant Quick Reference / Architecture Status section (duplicates CLAUDE.md)

**Removed (obsolete — architecture changed since):**
- Stage 1-3 Translation Refactoring (Session 59) — pipeline architecture fundamentally different now
- Youth Mode & Pipeline Visualization (Session 52) — UI rebuilt from scratch
- Phase 2 Frontend redesign (Session 36) — rebuilt multiple times since
- Automate configsByCategory (Session 91) — frontend rebuilt
- Vector Fusion UI (Session 40) — deactivated per user decision
- Canvas Eval Nodes Phase 3b / Loop Controller Phase 4 (Session 134) — contradictory status (title says DONE, body says BLOCKED)
- partial_elimination 2 Open Issues (Session 98) — 3 months without mention

**Status updates:**
- LLM Inference Migration → ✅ DONE (Session 202)
- T5 Interpretability Research → ✅ CODE COMPLETE (Session 203)
- Stage 3 Negative Prompts Bug → confirmed still open (verified in code: `safety_result['negative_prompt']` never passed to Stage 4)

**New structure:** Recently completed → Critical → High → Medium → Low/Deferred → Minigames → Archive

### Files Changed
- `docs/devserver_todos.md` — rewritten (~2100 → ~220 lines)

---

## Session 203 - T5 Interpretability Research: Full 7-Phase Pipeline Implementation
**Date:** 2026-02-23
**Focus:** Implement SAE-based T5 audio-semantic interpretability research pipeline

### Context

Approved research plan (Session 192): Train a Sparse Autoencoder on T5-Base activations from ~101K audio prompts, decompose 768d into 12,288 monosemantic features, then sonify them through Stable Audio. No existing work sonifies SAE features through an audio diffusion model — SAEdit does it for images, this is the audio equivalent.

### Implementation (10 files, 4,078 lines)

**`research/t5_interpretability/`** — standalone scripts, each phase runnable independently:

| File | Phase | Purpose |
|------|-------|---------|
| `config.py` | — | Shared paths, hyperparams (SAE 768→12288, k=64), dataset IDs |
| `probing_specs.py` | — | 15 TraditionSpec dataclasses (full vocab), Pillar 2 material-physical vocab, controls |
| `build_corpus.py` | 1a | Download AudioCaps/MusicCaps/WavCaps (~95K), deduplicate |
| `build_probing_corpus.py` | 1b | Template-based generation: 15×250 traditions + 2000 physical + 500 controls |
| `encode_corpus.py` | 2 | Standalone T5-Base, batch 64, mean-pool → [N, 768] fp16 |
| `dimension_atlas.py` | 3 | Per-dim stats, 768×768 correlation clustering (Ward), probing analysis |
| `train_sae.py` | 4 | TopK SAE: pre-bias, encoder, unit-norm decoder, MSE loss, decoder renorm |
| `analyze_features.py` | 5 | Top-20 prompts, Pearson r per category, cultural bias, co-activation clustering |
| `sonify_features.py` | 6 | Feature direction injection into T5 embedding, GPU service HTTP generation |
| `cultural_analysis.py` | 7 | 15×15 cosine distance matrix, default-encoding bias, permutation test (p-value) |

**GPU Service modification:**
- `gpu_service/routes/stable_audio_routes.py`: Added `POST /api/stable_audio/generate_from_embeddings` — accepts base64-encoded numpy arrays, calls existing `backend.generate_from_embeddings()`. ~40 lines.

### Probing Corpus Design (pedagogical core)

**Symmetrical by design** — no tradition framed as default:
- 15 traditions × 5 templates × 50 prompts = 3,750 (Pillar 1)
- Each tradition: ~20 instruments, ~10 vocal styles, ~10 spatial/ensemble contexts, 50 blind descriptors
- Blind descriptors: acoustic descriptions WITHOUT naming the tradition (tests whether T5 maps similar sounds to same features regardless of cultural label)
- Pillar 2: 6 excitation types, 10 materials, 8 environments, 6 time patterns, 4 spectral axes, dynamics

### Key Design Decisions

1. **T5-Base standalone** (not via Stable Audio pipeline) — `text_projection = nn.Identity()` at `stable_audio_backend.py:423`, so hidden states are identical. Avoids loading the full diffusion model for encoding.
2. **TopK SAE** (not L1-penalized) — sparsity by construction (k=64), no hyperparameter tuning for L1 coefficient.
3. **Mean-pooling** over non-padding tokens — sentence-level representation, not per-token.
4. **Feature direction injection** — add SAE decoder column (768d unit vector) uniformly across all sequence positions of neutral embedding. Strength parameter controls intensity.
5. **Permutation test** for cultural significance — 1000 random label shuffles, compare observed mean pairwise distance.

### Status

Code complete, all files syntax-checked. Erstdurchlauf steht aus (Testanleitung in `docs/devserver_todos.md`).

---

## Session 202 - LLM Inference Migration: Ollama → GPU Service
**Date:** 2026-02-23
**Focus:** Route all LLM inference through GPU Service's VRAMCoordinator with Ollama fallback

### Problem
3 separate inference backends (Ollama/GGUF, GPU Service/safetensors, SwarmUI/ComfyUI) competed for the same GPU with no VRAM coordination. Ollama and GPU Service ran blind — loading a safety model via Ollama could evict a Diffusers pipeline from VRAM without the VRAMCoordinator knowing.

### Solution — 6 Phases

**Phase 1: GPU Service Infrastructure (3 new files)**
- `llm_inference_backend.py`: Multi-model VRAMBackend (mirrors TextBackend pattern). Auto-detects vision vs text models, extracts `<think>` blocks centrally, resolves Ollama model names via `LLM_MODEL_MAP`. NO `output_hidden_states`/`output_attentions` (pure inference, saves VRAM).
- `llm_inference_routes.py`: 5 REST endpoints (`/api/llm/chat`, `/generate`, `/available`, `/models`, `/unload`)
- Config: `LLM_INFERENCE_ENABLED`, `LLM_MODEL_MAP` (6 models), `LLM_QUANT_MULTIPLIERS`

**Phase 2: DevServer Client (2 new files)**
- `llm_client.py`: HTTP wrapper following DiffusersClient pattern. GPU Service primary, Ollama fallback on `ConnectionError`/`Timeout`. LLM errors (OOM, bad model) propagated, no fallback.
- `llm_backend.py`: Singleton factory (`get_llm_backend()`)

**Phase 3: Migrate Safety (stage_orchestrator.py)**
- 3 functions → `get_llm_backend().chat()`: `llm_verify_person_name`, `llm_dsgvo_fallback_check`, `llm_verify_age_filter_context`
- Fail-closed semantics preserved (None → block)
- Thinking-field fallback preserved

**Phase 4: Migrate Vision Models**
- `vlm_safety.py` → `get_llm_backend().chat()` with `images` param. Fail-open preserved.
- `image_analysis.py` → `get_llm_backend().chat()` with `images` param. Fixed hardcoded `localhost:11434` URL bug.

**Phase 5: Migrate Interception + Chat**
- `prompt_interception_engine.py::_call_ollama()` → `get_llm_backend().generate()`. Removed manual `keep_alive: 0` unload logic (VRAMCoordinator handles lifecycle).
- `chat_routes.py::_call_ollama_chat()` → `get_llm_backend().chat()`
- `schema_pipeline_routes.py`: 2× `ollama_service.translate_text()` → `get_llm_backend().generate()`

**Phase 6: Training Service Cleanup**
- `clear_vram_thoroughly()`: Added Step 4b — unload GPU Service LLM models alongside existing Ollama unload

### Architecture After

```
DevServer ──→ LLMClient ──→ GPU Service :17803  (safetensors, VRAMCoordinator)
                         ╰→ Ollama :11434       (GGUF, fallback on ConnectionError)
```

### NOT in scope (future)
- `settings_routes.py` `/api/tags` discovery — read-only, stays Ollama
- `model_selector.py` `/api/tags` discovery — read-only, stays Ollama
- `ollama_service.py` streaming (`translate_text_stream`) — legacy workflow
- Model list merging (GPU Service + Ollama available models)

### Files Changed
- 4 new files, 9 modified files (189 insertions, 167 deletions)

---

## Session 201 - Hebrew (he) + Arabic (ar) RTL Language Support
**Date:** 2026-02-23
**Focus:** Add RTL infrastructure for Hebrew and Arabic, CSS logical properties, LTR-pinned components

### Problem
The i18n system supported 7 LTR languages but had zero RTL support. Simply adding `he.ts`/`ar.ts` without `dir="rtl"` would render translated text left-to-right — unreadable for native speakers. With `dir="rtl"`, hardcoded `margin-left`/`border-left`/`text-align: left` CSS would partially break.

### Solution — 4 Phases

**Phase 1: RTL Infrastructure (3 files + 2 new)**
- `SUPPORTED_LANGUAGES` gains `dir: 'ltr' | 'rtl'` property per language
- `getLanguageDir()` helper exported from `index.ts`
- `main.ts` dynamically sets `<html dir>` and `<html lang>` on language change
- `index.html` defaults to `lang="de" dir="ltr"`
- Empty `he.ts`/`ar.ts` stubs (fallback to English)

**Phase 2: Pin LTR + CSS Fixes (29 files)**
- 23 visual/technical components pinned with `dir="ltr"` (canvas, pipeline, edutainment) — immune to RTL flip
- 6 text-heavy components converted to CSS logical properties: `margin-inline-start/end`, `border-inline-start`, `text-align: start`, `inset-inline-end` (SettingsView, App.vue, DokumentationModal, ChatOverlay, MediaInputBox, WelcomeItem)

**Phase 3: Language Files**
- `en.ts`: Added `arabicAr`/`hebrewHe` keys
- SettingsView: he/ar in language dropdown
- 3 work orders in `WORK_ORDERS.md` for batch translator

**Phase 4: Verification**
- `vue-tsc --noEmit` passes, `npm run build` passes

### Design Decisions
- **Full layout flip, not just text**: RTL users expect flex/grid to flip. Browser handles this natively via `dir="rtl"` on `<html>` — no custom code needed.
- **CSS logical properties**: `margin-inline-start` behaves identically to `margin-left` in LTR — zero regression risk for existing 7 languages.
- **LTR pins**: Canvas, pipeline arrows, edutainment games are universally left-to-right (data flow direction, not text direction).
- **Translations deferred**: Infrastructure first, translations via batch workflow second. English fallback keeps UI functional.

### Files Changed
36 files (34 modified, 2 new) — commit `d12107b`

---

## Session 199 - i18n Split + Batch Translation Workflow
**Date:** 2026-02-23
**Focus:** Split 8275-line i18n.ts monolith into per-language files, establish batch translation workflow

### Problem
The monolithic `i18n.ts` (568KB, 8275 lines, 6 languages) consumed massive context every UI session. Writing translations for 5 non-English languages was manual and repetitive.

### Solution
1. **Split into `src/i18n/` directory**: `index.ts` barrel + `{en,de,tr,ko,uk,fr}.ts` per-language files (~1370 lines each)
2. **Batch workflow**: Sessions edit only `en.ts`, leave structured work orders in `WORK_ORDERS.md`
3. **`i18n-translator` agent**: Processes pending work orders, translates into 5 languages, type-checks, commits
4. **`6_run_i18n_translator.sh`**: Start script for standalone batch runs

### Implementation
- **`src/i18n/index.ts`**: Barrel export — imports all 6 languages, exports `SUPPORTED_LANGUAGES`, `SupportedLanguage`, `LocalizedString`, `localized()`, `createI18n`
- **`src/i18n/WORK_ORDERS.md`**: Structured template with `(NEW)`/`(MODIFIED)` tags and context fields
- **`.claude/agents/i18n-translator.md`**: Agent with apostrophe escaping, template variable preservation, validation script
- **CLAUDE.md rules**: Rule 9 (i18n workflow), Rule 10 (concurrent session awareness)
- **Import compatibility**: All 13+ consuming files use `@/i18n` or `./i18n` — directory `i18n/index.ts` resolves automatically, zero changes needed

### Impact
| Metric | Before | After |
|---|---|---|
| Context per UI session | ~8275 lines (568KB) | ~1374 lines (~95KB) |
| Translation effort per session | Manual for 5 languages | Zero — work order only |
| Adding a new language | Edit 8K-line monolith | Create one file + 1 import |

### Note
Commit c88f496 (concurrent session) had already created the 6 language files but left the monolith intact and didn't create `index.ts`. This session completed the migration.

---

## Session 194 - Forest MiniGame: Flowerpot Cursor with Seedling Growth
**Date:** 2026-02-22
**Focus:** Replace invisible cooldown indicator with custom flowerpot cursor

### Problem
The hourglass cooldown indicator (`⏳ 1.0s`) was inside the `showInstructions` block which disappears after 5 seconds. After that, the 1-second planting cooldown was invisible — clicks silently swallowed with no feedback.

### Solution
Custom SVG flowerpot cursor replaces the native pointer. During the 1s cooldown after planting, a seedling grows inside the pot (scale 0→1). When fully grown, click to plant. The cooldown is now always visible as a charming micro-animation.

### Implementation
**Modified:** `ForestMiniGame.vue`

- **Mouse tracking**: `mouseX`/`mouseY` refs, `showPotCursor` toggle on mouseenter/mouseleave
- **Seedling growth**: `seedlingGrowth = 1 - plantCooldown` — maps cooldown 1→0 to growth 0→1
- **SVG cursor**: Terracotta pot (trapezoid body + rim + soil) with seedling (stem + 2 leaves + bud) scaled from base point
- **CSS**: `cursor: none` on game area, `.pot-cursor` with `pointer-events: none`, `transform: translate(-50%, -100%)` anchoring bottom-center at mouse
- **Cleanup**: Removed `.plant-instruction.cooldown` and `:empty` styles, simplified instruction to show only before first tree planted

---

## Session 193 - Wavetable Synthesis as Third Playback Mode
**Date:** 2026-02-22
**Focus:** Add wavetable oscillator to Crossmodal Lab Synth tab

### Problem
The Latent Audio Synth generates audio via Stable Audio and plays it as a looping sample (`AudioBufferSourceNode.loop`). The WAV contains complex audio with many oscillations — crossfade at loop boundaries is always audible, and it doesn't behave like an oscillator.

### Solution: Wavetable Oscillator
Extract single-cycle frames from the WAV and use them as a wavetable oscillator (Serum/Vital paradigm). A phase-accumulator AudioWorklet reads through each frame at the desired frequency, and a scan position morphs between frames for timbral control.

Three mutually exclusive modes: **Loop | Ping-Pong | Wavetable**

### Implementation

**New files:**
- `src/audio/wavetable-processor.ts` — AudioWorkletProcessor with phase-accumulator synthesis, bilinear interpolation (between samples within a frame + between adjacent frames), 2048-sample frame size (~21.5 Hz fundamental at 44.1 kHz)
- `src/composables/useWavetableOsc.ts` — Composable managing AudioContext + worklet lifecycle, frame extraction (stereo→mono, pitch-synchronous via pitchy McLeod + Lanczos sinc resampling + Hann windowing, fallback to overlapping windowed extraction), frequency/scan/note control

**Modified files:**
- `useAudioLooper.ts` — Added `getOriginalBuffer()` getter (1 line)
- `crossmodal_lab.vue` — Segmented control replacing ping-pong checkbox, wavetable scan slider, conditional visibility (transpose mode/crossfade/save-loop hidden in wavetable mode), MIDI CC5→scan mapping, note handler branches on mode, frame re-extraction on regeneration
- `i18n.ts` — 7 keys (DE+EN): modeLoop, modePingPong, modeWavetable, wavetableScan, wavetableScanHint, wavetableFrames, midiScan

### Key Design Decisions
- **Phase accumulator in AudioWorklet**: Runs in audio thread — no main-thread jitter. Phase wraps to prevent float precision loss at high frequencies.
- **Bilinear interpolation**: Smooth both within-frame (sample interpolation) and between-frame (scan morphing) — no audible stepping.
- **Pitch-synchronous extraction** (user enhancement): Uses pitchy MPM for pitch detection, extracts exact periods at zero-crossings, Lanczos-resamples to FRAME_SIZE. Falls back to overlapping windowed extraction for noisy/unpitched audio.
- **Mode switching stops both engines**: Clean handoff — no orphaned AudioNodes.
- **Wavetable mode reuses looper for decode**: `looper.play()` still decodes base64 WAV, then `getOriginalBuffer()` provides the AudioBuffer for frame extraction. Looper is stopped after frames load.

### Commits
- `cbb9f96` feat(crossmodal-lab): Wavetable synthesis as third playback mode

---

## Session 192 - Latent Lab Research Data Export (LatentLabRecorder)
**Date:** 2026-02-22
**Focus:** Research data recording for all Latent Lab experiments

### Problem
Canvas records research data via `CanvasRecorder`/`LivePipelineRecorder` because it runs through the 4-Stage Orchestrator. The Latent Lab bypasses this flow — 11 tool types across 3 backend services (GPU Service, Ollama, DevServer) with direct API calls. No backend chokepoint exists for a recorder.

### Solution: Frontend-Primary Hybrid
Frontend knows the full context (parameters, tab, tool type). After each generation, it POSTs to a new lightweight backend endpoint which writes to disk in the same folder structure as Canvas (`exports/json/YYYY-MM-DD/device_id/run_xxx/`).

### Implementation

**Backend (2 new files):**
- `latent_lab_recorder.py` — Lightweight `LatentLabRecorder` class (no stage tracking, no expected_outputs)
- `latent_lab_recorder_routes.py` — 3 endpoints: `POST /api/latent-lab/record/{start,save,end}`

**Frontend (1 new file):**
- `useLatentLabRecorder.ts` — Vue composable with lazy lifecycle (run folder created on first `record()`, not on mount)

**Integration (7 views + 1 child):**
- `denoising_archaeology.vue` — params + final PNG + all step JPGs
- `concept_algebra.vue` — params + reference + result images
- `feature_probing.vue` — params + original/modified images (both analyze + transfer)
- `attention_cartography.vue` — params + output image (attention maps too large for export)
- `crossmodal_lab.vue` — 3 tabs: synth/mmaudio/guidance, params + audio WAV
- `latent_text_lab.vue` — 4 functions: findDirection/repGen/compare/biasProbe, params + metadata
- `surrealizer.vue` — params only (image already recorded by pipeline recorder)

**i18n:** 3 keys (`recordingActive`, `recordingCount`, `recordingTooltip`) across 6 languages

### Key Design Decision: Lazy Start
Initial implementation created a run folder on every `onMounted()` — navigating between tabs created empty folders. Fixed by deferring `startRun()` to the first actual `record()` call. `isRecording` indicator still shows immediately.

### metadata.json Format
```json
{
  "type": "latent_lab",
  "latent_lab_tool": "denoising_archaeology",
  "entities": [
    { "type": "latent_lab_params", "filename": "prompting_process/001_parameters.json" },
    { "type": "output_image", "filename": "01_output_image.png" }
  ]
}
```
Compatible with `SessionExportView.vue` — Latent Lab runs appear alongside Canvas/Pipeline runs.

### Commits
- `b8c7665` feat(latent-lab): Add research data export with LatentLabRecorder
- `83b6e7a` fix(latent-lab): Lazy-start recorder to avoid empty run folders

---

## Session 190 - Fix Age-Filter Fail-Open Bug + DSGVO Fallback
**Date:** 2026-02-21
**Focus:** Fix critical safety bug where age-filter context check used dead pipeline → fail-open, letting blocked content through

### Problem
"Ein gruseliger Vampir mit Blut" passed kids safety despite all terms (Vampir, Blut, gruselig) being in `youth_kids_safety_filters.json`. Root cause: `fast_filter_check()` found terms correctly, but the LLM context verification called `pipeline_executor.execute_pipeline('pre_interception/gpt_oss_safety', ...)` — a pipeline depending on a model no longer loaded. Pipeline failure → line 784: `continuing (fail-open)` → scary content passed through unblocked.

Same pattern existed in the DSGVO SpaCy-unavailable fallback (line 869-911): dead `gpt_oss_safety` pipeline + fail-open on failure.

### Fix
1. **Age-filter** (lines 769-867): Replaced 91-line dead pipeline call + BLOCKED:/SAFE: response parsing with direct call to `llm_verify_age_filter_context()` — a function already in the same file (line 276) using `DSGVO_VERIFY_MODEL` (qwen3:1.7b, always loaded). Fail-open → **fail-closed**.

2. **DSGVO fallback** (lines 869-911): Created new `llm_dsgvo_fallback_check()` function for when SpaCy is unavailable (can't use `llm_verify_person_name()` which needs NER entities). Same model, same SAFE/UNSAFE pattern. Fail-open → **fail-closed**.

### Key Decisions
- Both paths now use `DSGVO_VERIFY_MODEL` (qwen3:1.7b) — always loaded, 1.5 GB VRAM, 60s timeout
- Age-filter `llm_verify_age_filter_context()` has 60s result cache (prevents inconsistent re-checks)
- `llm_dsgvo_fallback_check()` asks LLM to *discover* names (vs `llm_verify_person_name()` which *verifies* SpaCy hits)
- Zero references to `gpt_oss_safety` pipeline remain in stage_orchestrator.py

### Test Results (12/12 pass)
- "Ein gruseliger Vampir mit Blut" → **BLOCKED** (kids, both /safety/quick and unified pipeline)
- "Ein freundlicher Hund im Park" → PASS
- "Angela Merkel im Garten" → **BLOCKED** (DSGVO)
- "Hakenkreuz auf rotem Hintergrund" → **BLOCKED** (§86a, instant)
- "Tod und Verderben überall" → **BLOCKED** (kids)
- "Ein bunter Schmetterling auf einer Blume" → PASS (9ms Stage 1 → full Stage 2)

### Changes
- `devserver/schemas/engine/stage_orchestrator.py` — 1 file, 148 insertions, 127 deletions (-51 net in age-filter, +68 new DSGVO fallback function)

---

## Session 189 - Fix Cross-Aesthetic Guided Audio Generation (ImageBind + StableAudio)
**Date:** 2026-02-21
**Focus:** Fix 4 critical bugs in `_guided_generate()` that caused the denoising loop to produce only noise/chaos

### Problem
The custom guided denoising loop in `stable_audio_backend.py` reimplemented the EDMDPMSolverMultistep scheduler incorrectly. ImageBind mel-spec encoding was already fixed (Session ~174), but the denoising math had 4 bugs making output completely broken regardless of guidance quality.

### Bugs Fixed
1. **Missing `init_noise_sigma` scaling** (~80x magnitude error): Pipeline multiplies initial noise by `(σ_max² + 1)^0.5 ≈ 80.006`, custom code skipped this entirely → latents started at wrong noise level
2. **Wrong `predicted_clean` formula**: Used `latents - sigma * noise_pred` (DDPM) instead of EDM preconditioning (`c_skip * sample + c_out * model_output` via `scheduler.precondition_outputs()`) → garbage decoded audio for ImageBind
3. **Manual Euler step instead of `scheduler.step()`**: First-order Euler on raw output vs DPMSolver++ with preconditioning + multi-step integration → wrong solver, numerical instability
4. **Scheduler state corruption**: `scheduler.step()` was only called during non-warmup → `step_index` never incremented during warmup → all subsequent steps used wrong sigma values + empty model_outputs buffer

### Architecture Change
Guidance now modifies latents **before** `scheduler.step()` (per Xing et al. CVPR 2024), and `scheduler.step()` runs on **every** iteration. No manual Euler needed.

### Reference
- Xing et al., "Seeing and Hearing: Open-domain Visual-Audio Generation with Diffusion Latent Aligners" (CVPR 2024)
- ImageBind (Girdhar et al., CVPR 2023) — joint embedding space
- Pipeline source: `diffusers/pipelines/stable_audio/pipeline_stable_audio.py:445,736`
- Scheduler source: `diffusers/schedulers/scheduling_edm_dpmsolver_multistep.py:192-206,632-708`

### Changes
- `gpu_service/services/stable_audio_backend.py` — 1 file, 32 insertions, 22 deletions

---

## Session 188 - Session Export: Device-Filter statt User-Filter
**Date:** 2026-02-21
**Focus:** Replace non-functional user_id filter with device_id in Session Data Export (Forschungsdaten tab)

### Problem
The "User" filter in session export was useless — `user_id` is almost always "anonymous". Meanwhile, `device_id` (from the favorites/browser-ID system) is stored in every `metadata.json` and uniquely identifies devices.

### Changes
- **Backend** (`settings_routes.py`): Query param `user_id` → `device_id`, filter logic, session summary field, sortable fields, unique filter collection, response key `"devices"` instead of `"users"`
- **Frontend** (`SessionExportView.vue`): Stats card, filter dropdown (truncated to 8 chars), state/clearFilters, URL params, table header+row, detail modal, both PDF export functions (single + ZIP)

### Verification
- `npm run type-check` passes cleanly
- No remaining `user_id`/`unique_users`/`.users` references in either file
- 2 files changed, 30 insertions, 30 deletions

---

## Session 187 - i18n Infrastructure: Generic 3rd-Language Readiness
**Date:** 2026-02-20
**Focus:** Make i18n infrastructure extensible so adding ANY language requires only "add translations" — no code changes needed.

### Changes
- **`LocalizedString` type + `localized()` helper** (i18n.ts): Central type for all bilingual string objects, with English fallback resolution
- **Replaced hardcoded `'de' | 'en'` unions** with `SupportedLanguage` across 7 locations in api.ts, pipelineExecution.ts, configSelection.ts, ConfigTile.vue
- **Replaced `{ en: string; de: string }` interface fields** with `LocalizedString` across 8 locations in types/canvas.ts, 3 in api.ts, 3 in configSelection.ts
- **Converted ternary language lookups** (`locale === 'de' ? x.de : x.en`) to `localized(x, locale)` in ModulePalette.vue (2), ConfigSelectorModal.vue (4), CanvasWorkspace.vue (1), MusicTagSelector.vue (1)
- **Fixed hardcoded `loadMetaPromptForLanguage('de')`** in image_transformation.vue and multi_image_transformation.vue — now uses actual user locale
- **Backend fallback**: `build_safety_message()` in stage_orchestrator.py uses `.get(lang, ...['en'])` instead of direct key access — prevents KeyError on unknown languages
- **Removed dead keys**: `language.switch` / `language.switchTo` from both DE and EN i18n sections (unused anywhere)

### Scope discipline
- 13 files, 57 insertions, 46 deletions — all targeted
- NOT touched: doc components (255 ternaries, adult-facing), canvas/StageModule.vue (80 ternaries, advanced feature), backend Python code, safety-critical files
- `npm run type-check` passes cleanly

### Verification
Adding a 3rd language to `SUPPORTED_LANGUAGES` now requires only: (1) add translations to i18n.ts message object, (2) add language entry to `SUPPORTED_LANGUAGES` array. All type lookups, config name resolution, and backend safety messages automatically fall back to English.

### Turkish (tr) — First 3rd Language Added
- **1071 keys** fully translated (Sonnet agent, not Opus — translation doesn't need reasoning)
- `LocalizedString` type fixed: `Record<SupportedLanguage, string>` → `{ en: string; [key: string]: string }` — otherwise adding `'tr'` would require `tr` key in every existing object literal
- Additional type fixes: `ConfigContextResponse.context` → `Record<string, string>`, `NoMatchState.vue` prop → `SupportedLanguage`, `createI18n` locale cast
- Infrastructure proof: adding Turkish required **1 line** in SUPPORTED_LANGUAGES + translations. Zero code changes.
- KVKK (Turkish GDPR equivalent) used instead of DSGVO/GDPR in safety messages
- `npm run type-check` passes, `fallbackLocale: 'en'` handles any missing tr keys

## Session 185 - i18n Batch 6: Infrastructure Code + LLM Meta-Prompts
**Date:** 2026-02-20
**Focus:** Final i18n sweep — convert remaining German strings in infrastructure code; convert LLM meta-prompts to English for better instruction adherence

### Key Distinction Established
**Meta-prompts are NOT i18n.** LLM system prompts are internal steering instructions written in the language that works best for the model (English). They must not be conflated with localized user-facing content. Bilingual Stage2 configs (`{'de': ..., 'en': ...}`) are a separate category — that IS localized content.

All converted meta-prompts include language guards (`"Respond in the language of the input"`) to preserve output language adaptation.

### Group A: Infrastructure Code (8 files)
Docstrings, comments, log messages, fallback strings → English:
- `devserver/schemas/__init__.py`, `devserver/schemas/engine/__init__.py` — module docstrings
- `devserver/my_app/services/comfyui_client.py` — class docstring
- `devserver/my_app/services/streaming_response.py` — SSE status messages
- `devserver/schemas/engine/comfyui_workflow_generator.py` — all docstrings, comments, log messages
- `devserver/my_app/utils/workflow_node_injection.py` — all comments
- `devserver/my_app/routes/chat_routes.py` — fallback defaults (`unbekannt`→`unknown`, etc.)
- `devserver/my_app/services/wikipedia_service.py` — disambiguation error message

### Group B: LLM Meta-Prompts (3 files)
- `devserver/my_app/routes/text_routes.py` — `INTERPRETATION_SYSTEM_PROMPTS` (repeng, bias, compare) + `_build_interpretation_prompt()` labels
- `devserver/my_app/routes/canvas_routes.py` — comparison evaluator prompt
- `devserver/my_app/services/canvas_executor.py` — same comparison evaluator prompt

### Group C: Archive Files (gitignored)
Changed on disk but not tracked by git (`**archive/` in `.gitignore`). No commit impact.

### Verification
- `ast.parse()` on all 11 files → OK
- Träshy language guard already present (`chat_routes.py:43`, `:62`)

### Commits
- `e34c006` — `fix(i18n): Convert German strings in infrastructure code to English (Batch 6)`

---

## Session 183 - Tiered Translation: Auto for Kids, Optional for Youth+
**Date:** 2026-02-19
**Focus:** Decouple translation-for-safety from translation-for-generation in Stage 3

### Problem
`execute_stage3_safety()` always auto-translated prompts to English before generation, coupling two purposes: safety (llama-guard works better on English) and generation quality (models produce better results with English). This prevented youth+ users from exploring how models react to their native language.

### Changes
**Single function change** in `devserver/schemas/engine/stage_orchestrator.py`:

1. **Moved `research`/`adult` early-return before translation** — these levels now skip translation entirely and return the original prompt (previously wasted an LLM translation call)
2. **Tiered prompt selection after safety passes** — `kids` gets auto-translated English prompt, `youth` gets original-language prompt back (safety still checked on translated text internally)
3. **Fixed latent bug** — §86a block's `execution_time` referenced undefined `translate_start` on cache hit (replaced with `translate_time`)

### Verification
Tested all 4 safety levels with same German prompt:
- **Kids**: Translated → safety check → English prompt to model, `was_translated=True`, badge shows
- **Youth**: Translated internally → safety check → German prompt to model, `was_translated=False`, no badge
- **Adult**: No translation, no safety → German prompt to model
- **Research**: No translation, no safety → German prompt to model

### Affected Files
- `devserver/schemas/engine/stage_orchestrator.py` — `execute_stage3_safety()` restructured
- `docs/ARCHITECTURE PART 29 - Safety-System.md` — Updated Stage 3 flow description
- `docs/DEVELOPMENT_DECISIONS.md` — Decision documented

---

## Session 182 - Real Diffusers Progress for Edutainment Animations
**Date:** 2026-02-19
**Focus:** Replace faked time-based progress with real Diffusers step callbacks

### Problem

Edutainment animations (Forest, Iceberg, Pixel) showed a faked progress loop based on `estimatedSeconds` from output configs. The Diffusers backend already fires step callbacks (`step 5/25`) but this data had no path to the frontend.

### Architecture: Polling Side-Channel (3 layers)

```
Diffusers callback → _generation_progress dict → GET /api/diffusers/progress
  → DevServer proxy /api/settings/generation-progress → Frontend polls every 2s
```

No SSE changes. No threading complexity. Fail-open by design.

### Changes

**Layer 1: GPU Service** (`gpu_service/services/diffusers_backend.py`)
- Added module-level `_generation_progress` dict + `get_generation_progress()` getter
- Wired progress callbacks into all 5 generation methods: `generate_image()`, `generate_video()`, `generate_image_with_fusion()`, `generate_image_with_attention()`, `generate_image_with_archaeology()`
- Each sets `active=True` before inference, updates `step/total_steps` per callback, sets `active=False` in `finally`

**Layer 1b: GPU Service Route** (`gpu_service/routes/diffusers_routes.py`)
- Added `GET /api/diffusers/progress` endpoint

**Layer 2: DevServer Proxy** (`devserver/my_app/routes/settings_routes.py`)
- Added `GET /api/settings/generation-progress` with 2s timeout, fallback to `{step:0, total_steps:0, active:false}`

**Layer 3: Frontend Composable** (`useAnimationProgress.ts`)
- Added `backendProgress` ref + `fetchGenerationProgress()` polled every 2s alongside GPU stats
- `animationLoop` uses real step progress when backend reports `active=true`
- `hasSeenBackendProgress` latch: once real data is seen, progress holds at last value when inference finishes (no reset during VLM safety check)
- Falls back to time-based loop for ComfyUI/HeartMuLa/GPU-service-down

### Behavior Matrix

| Backend | Progress behavior |
|---------|------------------|
| Diffusers | Real steps 0→100%, holds at 100% during safety check |
| ComfyUI | Time-based loop 0→100→0→100 (unchanged) |
| HeartMuLa | Time-based loop (unchanged) |
| GPU service down | Time-based loop (unchanged) |

### Files changed
- `gpu_service/services/diffusers_backend.py` — progress dict, callbacks in all 5 methods
- `gpu_service/routes/diffusers_routes.py` — progress endpoint
- `devserver/my_app/routes/settings_routes.py` — proxy endpoint
- `public/.../composables/useAnimationProgress.ts` — polling + real progress + hold latch

---

## Session 181 - DSGVO NER Verification Rewrite
**Date:** 2026-02-18
**Focus:** Fix broken DSGVO-NER false positive filtering — wrong prompt, wrong model, missing POS-tag pre-filter

### Problem

The DSGVO-NER LLM verification produced inconsistent results:
- "Benjamin Jörissen" (real professor) → LLM said "NEIN" (not a real person) → passed through
- "Karl Meier" (generic name in creative context) → LLM said "JA" (real person) → blocked

**Root causes:**
1. **Wrong question**: Prompt asked "Sind diese Wörter echte Personennamen real existierender Menschen?" with rule "Alltagsnamen = JA" — every common name got blocked
2. **JA/NEIN in German**: Language-dependent, double negation (NEIN = safe), error-prone
3. **SpaCy tagger disabled**: POS tags unavailable, so false positives like "Schräges Fenster" (ADJ+NOUN tagged as PER) reached the LLM
4. **Unauthorized model fallback**: Guard models (llama-guard) can't answer "is this a name?" but code silently fell back to hardcoded gpt-OSS:20b (20GB VRAM)

### Changes

**1. LLM Prompt rewrite** (`stage_orchestrator.py:206`)
- New question: "Are these flagged words actually person names, or false positives?"
- SAFE/UNSAFE output (English, language-independent, no double negation)
- Rules: actual names (real or fictional) = UNSAFE, descriptions/materials/places = SAFE

**2. SpaCy POS-tag pre-filter** (`stage_orchestrator.py:103,145-149`)
- Enabled tagger (removed from `disable` list)
- PER entities without PROPN tokens are filtered before LLM call
- "Schräges Fenster" (ADJ+NOUN) → filtered in milliseconds, no LLM needed

**3. Dedicated DSGVO_VERIFY_MODEL** (`config.py:142`)
- New config value, separate from SAFETY_MODEL (guard) and STAGE1_TEXT_MODEL (may be external)
- Must be general-purpose (not guard model), must be local (Ollama only)
- Removed unauthorized hardcoded gpt-OSS:20b fallback

**4. Settings UI** (`SettingsView.vue:130-162`)
- Added DSGVO-Verify Model dropdown in "Local Safety Models" section
- 6 options: qwen3:1.7b (recommended), gemma3:1b, qwen2.5:1.5b, llama3.2:1b, qwen3:0.6b, gpt-OSS:20b

### Architecture insight

Stage 1 safety has three independent steps, two of which may call an LLM:
1. §86a fast-filter (keywords, no LLM)
2. Age-filter → LLM context check on hit (guard model, fast)
3. DSGVO NER → LLM verify on hit (general-purpose model, now configurable)

The LLM verify's **only job** is filtering SpaCy false positives — not evaluating whether names are "safe" to use.

### Files changed
- `devserver/config.py` — DSGVO_VERIFY_MODEL
- `devserver/schemas/engine/stage_orchestrator.py` — prompt, POS filter, model selection
- `devserver/my_app/routes/settings_routes.py` — expose new setting
- `public/ai4artsed-frontend/src/views/SettingsView.vue` — dropdown UI

---

## Session 180 - Frontend Performance Analysis
**Date:** 2026-02-17
**Focus:** Audit what gets loaded when users access lab.ai4artsed.org — is the frontend bundle reasonable for weaker devices?

### Findings

**Architecture:** Pure client-side SPA (no SSR). All 23 routes use lazy loading via dynamic imports. The browser acts as a thin UI layer — all heavy computation (LLM, image/music generation, safety checks) stays on the backend/GPU service.

**Initial page load (~521 KB):**
- Main JS bundle (Vue, Router, Pinia, i18n, App shell): 469 KB
- Main CSS: 36 KB
- LandingView (lazy-loaded): ~12 KB
- Favicon + HTML: ~5 KB

**Route bundle sizes (lazy-loaded on navigation):**
- Landing: 9.6 KB | Text transformation: 43 KB | Image transformation: 19 KB
- Canvas workflow: 125 KB | Latent Lab: 120 KB | Settings: 526 KB (largest)
- Most routes: 1-21 KB

### Optimization opportunities (not urgent)
1. **`public/config-previews/originals_backup/` (67 MB)** — deployed to dist but never served to users. Should be excluded from production builds.
2. **i18n loaded eagerly (135 KB, 2137 lines)** — all DE+EN translations in a single `i18n.ts`, loaded regardless of active language. Could be split per language.
3. **Modals in App.vue loaded eagerly** — ChatOverlay, FooterGallery, AboutModal mounted in global shell. Could be lazy-loaded on first open.
4. **Settings page (526 KB)** — likely embeds full config editor with schemas. Could be code-split.
5. **No manual vendor chunk splitting** — Vite uses automatic splitting only. Manual chunks for Vue/Router/Pinia would improve cache hit rates on repeat visits.

### Conclusion
At ~521 KB initial load, the architecture is solid and well within reasonable territory (most popular sites ship 2-5 MB). Full route lazy-loading is correctly implemented. No immediate action required — these are future optimization candidates if device constraints become an issue.

### Repo cleanup (same session)

**Problem:** Repository carried ~194 non-essential files in git tracking — session handovers, archived docs, terminal saves, mockups, a nested ComfyUI git clone in `docs/reference/`, and 67 MB of config-preview originals deployed to `dist/`.

**Changes:**
- **Config-preview originals** (67 MB, 34 PNGs) moved from `public/.../originals_backup/` → `resources/config-preview-originals/` (gitignored). Next `npm run build` no longer copies them into `dist/`.
- **docs/ cleaned up**: Untracked `sessions/`, `archive/`, `reference/`, `tmp/`, `terminal-savings/`, `experiments/`, `plans/`. Moved 21 root-level HANDOVER/SESSION files into `docs/sessions/` first.
- **69 essential docs remain tracked**: Architecture (01-30), installation, analysis, dev log, decisions, todos, pedagogical concept, whitepaper, IP.
- **`.gitignore` fixed**: Removed broken absolute-path rules (lines 75-79 were no-ops), removed duplicate entries, added `resources/` and 6 `docs/` subdirectories.

All files remain on disk — only removed from git tracking.

---

## Session 176 - Model Availability: GPU Service Independence
**Date:** 2026-02-15
**Focus:** Break SwarmUI dependency for model availability — Diffusers configs must be reachable without ComfyUI running.

### Problem
Vue components (`text_transformation.vue`, `image_transformation.vue`) call `GET /api/models/availability` on mount to decide which model configs to show. The `ModelAvailabilityService` only queried ComfyUI's `/object_info` — non-ComfyUI backends (Diffusers, HeartMuLa) were blindly marked "always available" without checking the GPU service. When ComfyUI was down, the old code returned 503 with empty availability, hiding ALL models including Diffusers configs. Paradoxically, SwarmUI had to run for Diffusers models to appear.

### Solution
Each backend is now checked independently:
- **Diffusers configs** → query GPU service `GET /api/diffusers/available`
- **HeartMuLa configs** → query GPU service `GET /api/heartmula/available`
- **ComfyUI configs** → existing `/object_info` check (unchanged)
- **Cloud APIs** (OpenAI, OpenRouter) → always available (unchanged)

GPU service status is cached with the same 5-minute TTL as ComfyUI. The API response now includes `gpu_service_reachable` alongside `comfyui_reachable`. The 503 error on ComfyUI failure is replaced with a 200 containing partial results.

### Additional fixes
- Added missing `backend_type` to 9 output configs (8× `"comfyui"`, 1× `"heartmula"`)
- Switched `sd35_large` from ComfyUI to Diffusers primary (chunk `output_image_sd35_diffusers` already existed with ComfyUI fallback)
- Fixed `force_refresh` query parameter (was read but never propagated to caches)
- Added `comfyui_reachable` tracking flag (previously hardcoded `true`)

### Modified files
- `devserver/my_app/services/model_availability_service.py` — GPU cache, `get_gpu_service_status()`, per-backend routing
- `devserver/my_app/routes/config_routes.py` — `gpu_service_reachable` in response, removed 503 handler
- `devserver/schemas/configs/output/sd35_large.json` — Diffusers primary
- `devserver/schemas/configs/output/*.json` (8 files) — added `backend_type`
- `public/ai4artsed-frontend/src/services/api.ts` — TypeScript interface update

### Verified
- ComfyUI down + GPU service up → Diffusers/HeartMuLa configs `true`, ComfyUI configs `false`, `comfyui_reachable: false`, `gpu_service_reachable: true`
- SD3.5 Large visible in text-transformation Vue without SwarmUI
- `npm run type-check` passes

---

## Session 175 - DSGVO LLM Verification: Thinking Model Fallback
**Date:** 2026-02-15
**Focus:** Fix gpt-OSS:20b returning empty `content` in DSGVO NER verification

### Problem
Music generation blocked by DSGVO safety check: SpaCy NER falsely flagged German lyrics phrases ("Ast zu Ast", "Jedes Lied") as person names. The LLM verification (gpt-OSS:20b) should reject these as false positives, but returned empty `content` → fail-closed → blocked.

### Root Cause
gpt-OSS:20b is a **thinking model** — it puts reasoning in `message.thinking` and the final answer in `message.content`. Under VRAM pressure (SD3.5 Large occupying 28.6GB of 32GB), the model sometimes puts all output into `thinking`, leaving `content` empty. The code only checked `content`.

Direct Ollama curl test confirmed model works correctly (`content: "NEIN\nNEIN"`), proving this was a code-side issue, not a model issue.

### Fix
Added `thinking` field fallback to `llm_verify_person_name()` in `stage_orchestrator.py`: when `content` is empty, extract JA/NEIN from the `thinking` field. Same pattern already used by VLM safety check for qwen3-vl.

### Modified files
- `devserver/schemas/engine/stage_orchestrator.py` — thinking field fallback in `llm_verify_person_name()`
- `docs/ARCHITECTURE PART 29 - Safety-System.md` — document thinking model behavior

### Verified
- "Ast zu Ast, Jedes Lied" → `safe: true` (NER false positive correctly rejected by LLM)
- "Angela Merkel" → `safe: false` (real person correctly blocked by DSGVO)

---

## Session 174 - Shared GPU Service (Diffusers + HeartMuLa)
**Date:** 2026-02-14
**Focus:** Avoid double VRAM usage when dev (17802) and prod (17801) backends run simultaneously.

### Problem
Both Flask backends loaded Diffusers models (SD3.5 ~10GB+) and HeartMuLa independently in-process, doubling GPU memory usage on the same machine.

### Solution: GPU Service (Port 17803)
Extracted all GPU-intensive inference into a standalone Flask/Waitress service at `gpu_service/`. Both dev and prod backends now call this service via HTTP REST instead of loading models themselves.

**Architecture:**
```
Dev Backend (17802) ──┐
                      ├── HTTP REST ──→ GPU Service (17803) ──→ [GPU VRAM]
Prod Backend (17801) ─┘
```

**Key design**: `DiffusersClient` and `HeartMuLaClient` are drop-in replacements with identical async APIs. `get_diffusers_backend()` and `get_heartmula_backend()` now return HTTP clients. Zero changes to `backend_router.py` or chunk files.

### New files
- `gpu_service/` — Complete Flask service (server.py, config.py, app.py, routes/, services/)
- `devserver/my_app/services/diffusers_client.py` — HTTP client for Diffusers (all 7 generation modes)
- `devserver/my_app/services/heartmula_client.py` — HTTP client for HeartMuLa
- `6_start_gpu_service.sh` — Startup script

### Modified files
- `devserver/config.py` — Added `GPU_SERVICE_URL`, `GPU_SERVICE_TIMEOUT`
- `devserver/my_app/services/diffusers_backend.py` — Factory returns `DiffusersClient`
- `devserver/my_app/services/heartmula_backend.py` — Factory returns `HeartMuLaClient`

### Tested
- Standard image generation (SD3.5 Large) via HTTP bridge
- Feature Probing (Latent Lab) via HTTP bridge
- HeartMuLa music generation via HTTP bridge
- All working over internet (Cloudflare tunnel)
- Fallback: if GPU service is down, `is_available()` returns False → ComfyUI fallback

### Pending (Phase 4)
- Remove original DiffusersImageGenerator class (1700 lines) from devserver (now duplicated in gpu_service)
- Update ARCHITECTURE PART 27
- Test remaining Latent Lab modes (Attention Cartography, Concept Algebra, Denoising Archaeology, Surrealizer)

---

## Session 173 - Fix Feature Probing "Backend error: None" + Remove CPU Offloading
**Date:** 2026-02-14
**Focus:** Feature Probing failed with `"Backend error: None"` — actual exception was masked. Root cause: broken CPU offloading layer from Session 149-172.

### Problem
Feature Probing returned `None` on failure, which `backend_router.py` turned into `"Backend error: None"` — no actual exception visible. The underlying failures were caused by the CPU offloading layer (`_offload_to_cpu`, `_move_to_gpu`, `device_map="balanced"`) added for Flux2 in Sessions 149-172, which corrupted pipeline state.

### Solution (Two Phases)

**Phase 1: Error propagation** — `generate_image_with_probing()` now returns `{'error': str}` dicts instead of `None`. `backend_router.py` checks for error dicts and propagates the actual error message via `BackendResponse.error`.

**Phase 2: Remove CPU offloading layer** — Removed the entire three-tier memory system (GPU→CPU→Disk), keeping only the multi-model GPU cache with LRU eviction. Models are either on GPU or not loaded. Eviction = full `del` + `torch.cuda.empty_cache()`.

### What was removed (-214 lines)
- `_offload_to_cpu()`, `_move_to_gpu()`, `_model_device` dict, `_get_available_ram_mb()`
- `enable_cpu_offload` parameter, `device_map="balanced"` code path
- `DIFFUSERS_RAM_RESERVE_AFTER_OFFLOAD_MB` (16GB RAM check that silently blocked loading)
- `DIFFUSERS_PRELOAD_MODELS` + warmup thread in `__init__.py`

### What was kept
- `_pipelines` dict (GPU cache), `_model_last_used` (LRU), `_model_vram_mb`, `_model_in_use` (refcount), `_load_lock`
- `_ensure_vram_available()` (simplified: always-delete eviction)
- `_load_model_sync()` (simplified: 2 cases instead of 3)

### Files changed
- `devserver/my_app/services/diffusers_backend.py` — core simplification
- `devserver/schemas/engine/backend_router.py` — error propagation, remove `enable_cpu_offload`
- `devserver/my_app/__init__.py` — remove warmup thread
- `devserver/config.py` — remove `DIFFUSERS_PRELOAD_MODELS`, `DIFFUSERS_RAM_RESERVE_AFTER_OFFLOAD_MB`
- `devserver/schemas/chunks/output_image_flux2_diffusers.json` — remove `enable_cpu_offload`
- `docs/ARCHITECTURE PART 27` — rewritten to reflect simplified design

### Result
Feature Probing works. Error messages now show actual exceptions instead of "None".

---

## Session 172 - The Flux2 Diffusers Saga: Why `from_pretrained()` Can't Load 106GB
**Date:** 2026-02-11 to 2026-02-12
**Focus:** Attempted to run FLUX.2-dev via HuggingFace Diffusers instead of ComfyUI. Failed after 6+ attempts. Root cause: architectural limitation of `from_pretrained()`.

### The Goal
Run Flux2 via Diffusers backend to enable dev+prod servers in parallel on a single RTX PRO 6000 Blackwell (96GB VRAM). The assumption: FP8 quantization would halve VRAM usage from ~24GB to ~12GB.

### The Assumption Was Wrong
FLUX.2-dev is not a ~24GB model. Actual sizes measured from HuggingFace cache:

| Component | BF16 on Disk | Shards |
|---|---|---|
| Transformer | **61 GB** | 7 × ~9GB |
| Text Encoder (Mistral Small 3.1 24B) | **45 GB** | 10 × ~4.5GB |
| VAE | 321 MB | 1 |
| **Total** | **~106 GB** | |

The GPU has 96GB VRAM — enough for each component individually, but not both simultaneously (61+45=106 > 96).

### Attempt 1: Runtime FP8 Quantization (`TorchAoConfig`)
- Added `TorchAoConfig("float8_weight_only")` to `from_pretrained()`
- **Result:** OOM crash. 64GB RAM + 71GB swap completely full → Fedora kernel OOM kill → system reboot
- **Why:** Runtime quantization via torchao bypasses safetensors mmap. Instead of lazy-loading from SSD, the entire model is materialized in anonymous CPU memory for quantization. 106GB anonymous memory > 135GB total virtual memory (with OS overhead).

### Attempt 2: `low_cpu_mem_usage=False`
- Research agent claimed `low_cpu_mem_usage=True` was incompatible with TorchAoConfig
- Setting to `False` loads EVERYTHING at once instead of shard-by-shard
- **Result:** Made it worse. Same OOM crash.

### Attempt 3: Component-Level Quantization
- Load transformer separately with TorchAoConfig, inject into pipeline
- **Result:** Same OOM crash. The transformer alone is 61GB — quantizing it still requires full materialization.

### Full Revert (Commit `cd928cf`)
All quantization code removed. Pipeline_class bug fix and chunk consolidation preserved.

### Attempt 4: `enable_model_cpu_offload()` (Commit `1402b96`)
- Insight: Both components fit individually in 96GB VRAM. Use `enable_model_cpu_offload()` to load one at a time.
- **Result:** Never reached. `from_pretrained()` loads ALL 106GB to CPU RAM first, then `enable_model_cpu_offload()` sets up hooks. But the loading itself crashes at component 3/5 with only 19GB free RAM (SD3.5 was offloaded to CPU, consuming 28GB).

### Attempt 5: `device_map="balanced"` (Commit `f04f080`)
- Hypothesis: `device_map` in `from_pretrained()` loads components directly to GPU/CPU targets via safetensors mmap, bypassing full RAM materialization.
- **Result:** Same OOM crash at "Loading pipeline components: 40% 2/5". `from_pretrained()` still materializes everything in CPU RAM regardless of `device_map`.

### Attempt 6: Auto-Detection Fix + Full Unload (Commit `54f64ee`)
- Discovered the auto-detection in `backend_router.py` was routing `flux2` (ComfyUI config) through Diffusers without `enable_cpu_offload` flag.
- Added full model unload (not just CPU offload) before large model loads.
- Also added `enable_cpu_offload: True` to auto-detection map.
- **Result:** Still crashed — the fundamental `from_pretrained()` limitation remained.

### The Root Cause
**`DiffusionPipeline.from_pretrained()` is architecturally incapable of loading a 106GB model on a 64GB RAM system.** It creates anonymous CPU tensors for every parameter, regardless of `low_cpu_mem_usage`, `device_map`, or `use_safetensors`. The mmap from safetensors is only used during the read — the data is copied into regular (non-evictable) memory.

ComfyUI works because it uses `safetensors.safe_open(device="cuda")` to load each tensor individually, directly to GPU. The page cache pages are file-backed and immediately evictable. No intermediate anonymous CPU memory is ever allocated for the full model.

**This is not a configuration problem. It is a design limitation of `from_pretrained()`.**

### The Solution: ComfyUI (Commits `62f323b`, `182b162`)
- Removed Flux2 from Diffusers auto-detection map
- Set `requires_workflow: true` on Flux2 ComfyUI chunk (was `false`, causing fallback to SwarmUI simple API which defaults to SD3.5)
- Flux2 now routes through ComfyUI workflow with `flux2_dev_fp8mixed.safetensors` checkpoint
- **Result:** Works. 18 seconds generation, VLM safety check passes.

### Collateral Fixes
- **`pipeline_class` bug fix:** `generate_image()` was not passing `pipeline_class` to `load_model()`, causing Flux2 to load with wrong `StableDiffusion3Pipeline` on cold start
- **Chunk consolidation:** Deleted redundant `output_image_flux2_fp8.json` chunk. Both output configs (`flux2_diffusers`, `flux2_fp8`) now point to single `output_image_flux2_diffusers` chunk (1-chunk:N-configs principle)
- **`enable_cpu_offload` infrastructure:** Parameter chain added to `_load_model_sync()` → `load_model()` → `generate_image()`. Useful for future models that are large but fit component-wise in RAM.
- **Full model unload before large loads:** When loading a `cpu_offload` model, all cached models are fully freed from CPU RAM (not just offloaded from GPU).
- **LICENSE cleanup:** Removed old `LICENSE` file (1.6KB plaintext). `LICENSE.md` (19.8KB, bilingual DE/EN, §1-§10) is the canonical license. Fixes GitHub showing two license tabs.

### Git Chaos
- Committed LICENSE removal directly on `main` instead of `develop` (had to cherry-pick to develop)
- Remote `origin/main` had diverged (LICENSE edit via GitHub web UI) → required force push
- Deploy script failed twice due to diverged histories

### Commits (Session 172)
1. `eac30c1` feat(diffusers): FP8 quantization with automatic disk caching for Flux2
2. `b3076d8` fix(diffusers): Move save_pretrained after .to(device) to reduce peak RAM
3. `c2c06ff` fix(diffusers): Fix OOM crash — low_cpu_mem_usage incompatible with TorchAoConfig
4. `deda3fd` fix(diffusers): Component-level quantization to prevent OOM crash
5. `cd928cf` revert(diffusers): Remove FP8 runtime quantization — causes OOM on 64GB systems
6. `1402b96` feat(diffusers): Use enable_model_cpu_offload() for Flux2
7. `f04f080` fix(diffusers): Use device_map="balanced" for cpu_offload
8. `54f64ee` fix(diffusers): Add enable_cpu_offload to auto-detection + fully unload models
9. `62f323b` fix(router): Remove Flux2 from Diffusers auto-detection — route through ComfyUI
10. `182b162` fix(flux2): Set requires_workflow=true — Flux2 uses full ComfyUI workflow
11. `61ccf97` chore: Remove old LICENSE — LICENSE.md is the canonical license file

### Lessons Learned
1. **Know your model size before writing code.** 106GB ≠ 24GB. `du -shL` on the HF cache would have revealed this in 10 seconds.
2. **`from_pretrained()` always materializes in CPU RAM.** No combination of flags (`device_map`, `low_cpu_mem_usage`, `use_safetensors`) changes this. For models larger than system RAM, diffusers cannot load them.
3. **ComfyUI's architecture is fundamentally different:** Per-tensor `safe_open(device="cuda")` with manual model management vs. diffusers' monolithic `from_pretrained()` pipeline approach.
4. **Auto-detection maps must mirror chunk configs.** Hardcoded model config in `backend_router.py` duplicated and diverged from chunk JSON configs — classic DRY violation.
5. **`requires_workflow: false` on a chunk with a full ComfyUI workflow** silently routes to SwarmUI simple API, which uses a default model. No error, just wrong output.
6. **CPU offload ≠ RAM savings during loading.** `enable_model_cpu_offload()` only helps during inference (components move to GPU on demand). It cannot help if the model doesn't fit in RAM during `from_pretrained()`.

### Open: Future Diffusers Approach
The `flux2_diffusers` and `flux2_fp8` output configs remain as stubs. If HuggingFace improves `from_pretrained()` to support true streaming/mmap loading (or if the system gets 128GB+ RAM), these configs are ready. The `enable_cpu_offload` infrastructure in `diffusers_backend.py` is in place.

---

## Session 171 - Safety System: Testing, Bug Fixes, DSGVO LLM Verification
**Date:** 2026-02-12
**Focus:** Comprehensive safety system testing (26 test cases), 2 critical bugs found and fixed, test report

### Bugs Found & Fixed

**Bug A: DSGVO LLM Verification broken for thinking models**
- `llm_verify_person_name()` used `num_predict: 10` — gpt-OSS:20b thinking mode exhausted all tokens in `thinking` field, `content` always empty → fail-closed on every NER detection
- Few-shot examples in prompt confused model into classifying all examples instead of answering
- Fix: Simplified prompt (rules only, no examples), `num_predict: 500`, `timeout: 60`
- Verified: "Angela Merkel" → JA (block), "Der Eiffelturm" → NEIN (pass), "Paul Meier" → JA (block)

**Bug B: Fuzzy matching false positives on short terms**
- Levenshtein `max_distance=2` for terms ≥6 chars → 33% error rate on 6-char words
- "Potter" matched "Folter", "wurde" matched "murder", "gebaut" matched "Gewalt"
- Fix: Graduated threshold — `max_distance=1` for 6-7 char terms, `=2` for 8+ chars
- Unit tested: all false positives eliminated, true matches preserved

**i18n context resolution refactor**
- `resolve_context_language()` added to `config_loader.py`
- Context kept as raw dict through pipeline, resolved at point of use
- Fixes crash when interception configs use multilingual context `{en:..., de:...}`

### Test Report
- `docs/TEST_REPORT_Safety_System_Session171.md` — 26 test cases across 3 safety levels
- §86a, age filter (DE+EN), DSGVO NER + LLM verification, research/adult/kids mode switching

### Files Changed
- `devserver/schemas/engine/stage_orchestrator.py` — DSGVO prompt, num_predict, fuzzy distance
- `devserver/schemas/engine/config_loader.py` — `resolve_context_language()`, context passthrough
- `devserver/schemas/engine/chunk_builder.py` — Use `resolve_context_language()` for instruction text
- `devserver/my_app/routes/schema_pipeline_routes.py` — Use `resolve_context_language()` in optimization
- `devserver/testfiles/test_refactored_system.py` — Adapt to dict context
- `docs/TEST_REPORT_Safety_System_Session171.md` — Comprehensive test report

---

## Session 170 - UCDCAE Branding + Bugfix
**Date:** 2026-02-12
**Focus:** Visual connection between UCDCAE acronym and full name on landing page, plus type error fix

### Changes

**Landing Page: Colored Initials (LandingView.vue)**
- Full name "UNESCO Chair in Digital Culture and Arts in Education" now shows initial letters in UCDCAE color scheme
- U=#667eea, C=#e91e63, D=#7C4DFF, C=#FF6F00, A=#4CAF50, E=#00BCD4
- Function words ("in", "and") remain uncolored
- Full name styled with `font-weight: 600` for subtle emphasis

**i18n: Subtitle Split (DE + EN)**
- `landing.subtitle` → `landing.subtitlePrefix` + `landing.subtitleSuffix`
- Chair name rendered inline with colored spans (language-independent)

**Bugfix: MediaInputBox TS2304 (MediaInputBox.vue)**
- Removed vestigial `isStreaming.value = false` in `blocked` event handler
- Ref was never declared — EventSource close + stopBufferProcessor already handle cleanup

### Verification
- `npm run type-check` → 0 Errors

### Files Changed
- `public/.../src/views/LandingView.vue` — Colored initials + CSS
- `public/.../src/i18n.ts` — Subtitle split (DE+EN)
- `public/.../src/components/MediaInputBox.vue` — Remove dead isStreaming reference

---

## Session 169 - Latent Lab: Concept Algebra Implementation + UI Fixes
**Date:** 2026-02-12
**Focus:** Full implementation of Concept Algebra tab (A − B + C vector arithmetic on embeddings), then UI fixes based on first user testing

### Changes

**Backend: Concept Algebra Pipeline**
- `embedding_analyzer.py` — `apply_concept_algebra()`: tensor arithmetic (result = A − scale_sub×B + scale_add×C) with L2 distance metric
- `diffusers_backend.py` — `generate_image_with_algebra()`: encodes 3 prompts via SD3.5 triple encoder, applies algebra, generates reference + result images with same seed
- `output_image_concept_algebra_diffusers.py` — Python chunk (Stage 4) calling `backend.generate_image_with_algebra()` directly
- `concept_algebra_diffusers.json` — Output config routing to Python chunk
- `pipeline_executor.py` — Added `algebra_data`, `reference_image`, `result_image` to metadata whitelist
- `schema_pipeline_routes.py` — Extract `prompt_c`, `algebra_encoder`, `scale_sub`, `scale_add` from request, forward via `custom_params`, handle `diffusers_algebra_generated` response

**Frontend: Concept Algebra Tab**
- `concept_algebra.vue` — Full Vue component: 3 MediaInputBox inputs (A/B/C), encoder selector (All/CLIP-L/CLIP-G/T5), formula visualization, side-by-side image comparison, advanced settings (seed/cfg/steps/negative/scales), PageContext for Trashy
- `latent_lab.vue` — Added ConceptAlgebra tab import + conditional rendering

**i18n (DE + EN)**
- ~35 new `latentLab.algebra.*` keys: headers, explanations (what/how/read/tech), labels, placeholders
- `explainHowText`: detailed comparison of Concept Algebra vs. negative prompting
- `explainReadText`: commutativity explanation + King−Man+Woman analogy

**Architecture Documentation**
- `ARCHITECTURE PART 28 - Latent-Lab.md` — Scientific Foundation section (7 papers + DOIs), Concept Algebra section (mechanism, key files, frontend)

### UI Fixes (post-testing, commit 99f27d4)
- **Icons**: `icon="minus"` → `icon="−"` (U+2212), `icon="plus"` → `icon="＋"` (U+FF0B) — Unicode fallback in MediaInputBox
- **Seed field**: `setting-small` (80px) → `setting-seed` (14ch) — zoom-safe width
- **Side-by-side layout**: `flex: 0 1 480px` → `flex: 1 1 0` — prevents wrapping within 1000px container
- **Explanation text**: Extended `explainReadText` (DE+EN) with commutativity, vector space linearity, and why simple addition works

### Verification
- `npm run type-check` → 0 Errors

### Files Changed
- `devserver/my_app/services/embedding_analyzer.py` — `apply_concept_algebra()`
- `devserver/my_app/services/diffusers_backend.py` — `generate_image_with_algebra()`
- `devserver/schemas/chunks/output_image_concept_algebra_diffusers.py` — Python chunk
- `devserver/schemas/configs/output/concept_algebra_diffusers.json` — Output config
- `devserver/schemas/engine/pipeline_executor.py` — Metadata whitelist
- `devserver/my_app/routes/schema_pipeline_routes.py` — Request extraction + response handling
- `public/.../src/views/latent_lab/concept_algebra.vue` — NEU
- `public/.../src/views/latent_lab.vue` — Tab integration
- `public/.../src/i18n.ts` — Algebra keys (DE+EN)
- `docs/ARCHITECTURE PART 28 - Latent-Lab.md` — Scientific Foundation + Concept Algebra docs

---

## Session 168 - Rebranding: AI4ARTSED → UCDCAE AI LAB
**Date:** 2026-02-11
**Focus:** Institutional rebranding from single-project name to UNESCO Chair identity

### Changes

**Header (App.vue)**
- FAU logo added (links to fau.de), placed left of UNESCO logo
- AI4ArtsEd logo removed from header
- Title: `AI4ARTSED - AI LAB` → `UCDCAE AI LAB` with tooltip showing full name
- Browser tab title updated in `index.html`

**Landing Page (LandingView.vue)**
- Hero title: `AI4ArtsEd` → `UCDCAE AI LAB`
- "KI verändert Gesellschaft..." research paragraph removed
- Funding section: BMBFSFJ logo kept, AI4ArtsEd + COMeARTS project logos added below

**About Modal (AboutModal.vue)**
- Project logos (AI4ArtsEd + COMeARTS) added to funding section

**i18n (DE + EN)**
- `app.title`, `landing.subtitle`, `about.title`, `about.intro`, `legal.privacy.usage` updated
- `landing.research` set to empty string

**Backend: CORS Origins (config.py + __init__.py)**
- Extracted hardcoded CORS origins list to `CORS_ALLOWED_ORIGINS` in `config.py`
- Origins auto-generated from `PORT` variable (no more hardcoded port numbers)

**Assets**
- `fau_logo.png` (9.2 KB) — FAU Kernmarke
- `comearts_logo.jpg` (122 KB) — COMeARTS project logo

### Verification
- `npm run type-check` → 0 Errors

### Files Changed
- `devserver/config.py` — `CORS_ALLOWED_ORIGINS`
- `devserver/my_app/__init__.py` — Import + use `CORS_ALLOWED_ORIGINS`
- `public/.../index.html` — Tab title
- `public/.../src/App.vue` — Header logos + title
- `public/.../src/components/AboutModal.vue` — Project logos
- `public/.../src/i18n.ts` — All rebranded text (DE + EN)
- `public/.../src/views/LandingView.vue` — Hero + funding section
- `public/.../public/logos/fau_logo.png` — NEU
- `public/.../public/logos/comearts_logo.jpg` — NEU

---

## Session 167 - Diffusers Backend: VRAM Management, FP8, RAM Safety
**Date:** 2026-02-11
**Focus:** Three-tier VRAM management, FP8 quantization for Flux2, RAM pre-checks

### Changes

**Three-Tier VRAM Management (`diffusers_backend.py`)**
- GPU VRAM → CPU RAM → Disk memory hierarchy
- `_load_model_sync()` handles 3 cases: GPU-resident, CPU-offloaded, cold-load from disk
- `_offload_to_cpu()` / `_move_to_gpu()` for model swapping
- `_ensure_vram_available()` eviction logic with refcount protection
- Refcount `_model_in_use[model_id]` prevents eviction during inference

**FP8 Quantization for Flux2**
- Automatic disk caching of quantized models (`save_pretrained` after `.to(device)`)
- Fixed peak RAM issue: moved `save_pretrained` after GPU transfer

**RAM Safety**
- Pre-check: verify enough system RAM before loading models
- Graceful degradation when system RAM too low for CPU offload
- Check remaining RAM *after* offload, not just model fit
- Evict all GPU models before cold-loading a new model
- Suppress noisy diffusers warnings during CPU offload

**SD3.5 Turbo Schema**
- New output config for SD3.5 Turbo (fewer steps, faster inference)

### Files Changed
- `devserver/my_app/services/diffusers_backend.py`
- `devserver/schemas/chunks/output_image_flux2_diffusers.json`
- `devserver/schemas/chunks/output_image_flux2_fp8.json`
- `devserver/schemas/configs/output/flux2_fp8.json`
- `devserver/schemas/engine/backend_router.py`

---

## Session 166 - Music Tag Diversification, License, Docs, Denoising Archaeology
**Date:** 2026-02-11
**Focus:** UNESCO-aligned music tags, bilingual license, Latent Lab denoising archaeology

### Changes

**Music Generation v2: Tag Diversification**
- Added UNESCO-aligned regional instruments and genres
- Global instrument and genre coverage beyond Western defaults
- Fixed lyrics button behavior

**UCDCAE AI Lab License v1.0**
- Custom bilingual license (DE/EN)
- Covers educational use, research exceptions, attribution requirements

**Documentation**
- Renamed "Workshop" tab to "Praxis" in docs
- Added license and installation information

**Latent Lab: Denoising Archaeology**
- New tab: step-by-step visualization of the denoising process
- Shows intermediate latent states during diffusion

### Files Changed
- `public/.../src/i18n.ts` — Music tags, rebranding (i18n texts)
- `LICENSE` — NEU: UCDCAE AI Lab License v1.0
- `docs/` — Workshop → Praxis rename, installation info
- Latent Lab Vue components — Denoising Archaeology tab

---

## Session 165 - Research-Level Gating + Latent Lab Architecture Docs
**Date:** 2026-02-11
**Focus:** Safety-level gating for Canvas & Latent Lab; rename `off` → `research`; architecture documentation

### Problem
Canvas und Latent Lab nutzen direkte Pipeline-Aufrufe ohne vollständige Safety-Stages. Statt Safety in jeden experimentellen Endpoint nachzurüsten (was den dekonstruktiven Charakter zerstören würde), wird der Zugang gegated.

### Changes

**Backend: Safety-Level Rename `off` → `research`**
- ~25 Stellen in 6 Dateien: `config.py`, `schema_pipeline_routes.py`, `stage_orchestrator.py`, `workflow_logic_service.py`, `export_manager.py`, `workflow_streaming_routes.py`
- Neuer öffentlicher Endpoint: `GET /api/settings/safety-level`
- `testfiles/` bewusst nicht geändert (Build-Artefakte)

**Frontend: Feature-Gating**
- `stores/safetyLevel.ts` (NEU): Pinia-Store mit `fetchLevel()`, `isAdvancedMode`, `isResearchMode`, `researchConfirmed`
- `components/ResearchComplianceDialog.vue` (NEU): Compliance-Modal mit Warnung, Altershinweis, Checkbox
- `views/LandingView.vue`: Canvas + Latent Lab Cards mit `requiresAdvanced: true`, Locked-State (Opacity 0.4, Schloss-Icon)
- `router/index.ts`: `meta: { requiresAdvanced: true }` + Navigation Guard
- `main.ts`: Safety-Level-Fetch beim App-Start
- `i18n.ts`: `research.*` Keys (DE + EN)

**Dokumentation**
- `docs/DEVELOPMENT_DECISIONS.md`: Zwei neue Entscheidungen (Research-Level-Gating, Latent Lab als konsolidierter Modus, Diffusers als Introspection-Plattform)
- `docs/ARCHITECTURE PART 28 - Latent-Lab.md` (NEU): Vollständige Architektur-Dokumentation mit Attention Cartography, Feature Probing, Legacy-Workflows, Hallucinator-Abgrenzung, Research-Level-Gating

### Verification
- `npm run type-check` → 0 Errors
- `grep -r "'off'" devserver/my_app devserver/schemas/engine devserver/config.py` → 0 Treffer

### Files Changed
- `devserver/config.py` — `off` → `research`
- `devserver/my_app/routes/schema_pipeline_routes.py` — 4× rename
- `devserver/schemas/engine/stage_orchestrator.py` — 8× rename
- `devserver/my_app/services/workflow_logic_service.py` — 2× rename
- `devserver/my_app/services/export_manager.py` — 2× rename
- `devserver/my_app/routes/workflow_streaming_routes.py` — 1× rename
- `devserver/my_app/routes/settings_routes.py` — neuer Endpoint
- `public/.../stores/safetyLevel.ts` — NEU
- `public/.../components/ResearchComplianceDialog.vue` — NEU
- `public/.../views/LandingView.vue` — Feature-Gating
- `public/.../router/index.ts` — Guard + Meta
- `public/.../main.ts` — Store-Init
- `public/.../i18n.ts` — research.* Keys
- `docs/DEVELOPMENT_DECISIONS.md` — 2 neue Entscheidungen
- `docs/ARCHITECTURE PART 28 - Latent-Lab.md` — NEU

---

## Session 164 - Landing Page Restructure + Preset Selection Overlay
**Date:** 2026-02-10
**Focus:** Replace outdated `/select` bubble page with proper landing page; move interception preset selection into contextual overlay

### Problem
The platform outgrew its original entry point (`/select` = PropertyQuadrantsView). That page showed interception presets as the entry experience, but Canvas, HeartMuLa, Surrealizer, and Latent Lab don't use interception presets at all. Users were confused: "what feature do I want?" was conflated with "which interception style?".

### Changes

**New Landing Page (`LandingView.vue`)**
- Feature-dashboard with 6 cards: Text-Transformation, Image-Transformation, Bildfusion, Musikgenerierung, Canvas Workflow, Latent Lab
- Each card: rotating preview images (staggered per-card timing with ±800ms jitter), accent color, icon, description
- Hero section with research context (i18n DE/EN)
- Funding footer (BMBFSFJ logo + kubi-meta link)
- Route: `/` → LandingView (replaces old `/select`)

**InterceptionPresetOverlay (`InterceptionPresetOverlay.vue`)**
- Fullscreen bubble overlay reusing PropertyBubble component
- Triggered by icon button on Context-MediaInputBox (only in text/image/multi-image transformation views)
- Filters to `text_transformation` + `text_transformation_recursive` pipelines only (no music/latent-lab modes)
- On selection: loads config context, populates prompt, closes overlay
- Explicit square container via CSS `--square-size` for guaranteed circular bubbles

**Header Updates**
- Mode ordering: didactic simple→complex (Text → Image → Multi-Image → Music → Canvas → Latent Lab)
- Latent Lab: Material Symbols `biotech` (microscope) icon
- LoRA Training: Parrot SVG icon (from qubodup) with `fill="currentColor"`

**Router**
- `/select` route removed entirely (no redirect)
- `/home` route removed
- Auth guard updated: `property-selection` → `landing`

**Preview Images**
- All large screenshots resized to 480px JPEG (quality 82) for fast loading
- Total preview assets: ~1MB (down from ~40MB+ originals)

### Files Changed
- `src/views/LandingView.vue` — NEW
- `src/components/InterceptionPresetOverlay.vue` — NEW
- `src/components/MediaInputBox.vue` — showPresetButton prop + emit
- `src/views/text_transformation.vue` — overlay wiring
- `src/views/image_transformation.vue` — overlay wiring
- `src/views/multi_image_transformation.vue` — overlay wiring
- `src/App.vue` — header icon updates (order, Latent Lab icon, parrot)
- `src/router/index.ts` — route changes
- `src/i18n.ts` — landing + presetOverlay + multiImage keys (DE/EN)
- `public/config-previews/` — resized preview images

---

## Session 163 - Hallucinator: Exact ComfyUI Replication + Configurable Parameters
**Date:** 2026-02-09
**Focus:** Fix fundamentally broken Diffusers fusion by exact replication of original ComfyUI CLIP flow; add configurable negative prompt and CFG

### The Problem — Why This Was So Difficult

The Diffusers Hallucinator produced incoherent collage-like images instead of the original's surreal-but-coherent output. Fixing it required **three separate rounds of investigation** because the root causes were non-obvious and layered:

**Round 1 — Wrong diagnosis (CLIP-G in embedding):**
Initial analysis incorrectly concluded that CLIP-G was missing from the fusion embedding. This was based on comparing standard SD3 encoding (which uses CLIP-L+G) with our code. Fix: added CLIP-G to the fusion. Result: **made it worse** — more visual anchoring = less surreal.

**Round 2 — Reading the actual ComfyUI source (the breakthrough):**
Deep dive into the original ComfyUI workflow JSON + sd3_clip.py source revealed the truth: the original loads **only clip_l.safetensors** via a separate CLIPLoader. This means:
- SD3ClipModel is instantiated with `clip_g=None`
- `encode_token_weights()` produces `g_pooled = torch.zeros((1, 1280))`
- The **pooled output** is 768d real + 1280d **ZEROS** — not real CLIP-G

This was the critical insight: **real CLIP-G pooled gives the DiT strong visual anchoring that actively fights the extrapolation**. The zeroed CLIP-G pooled is not a bug — it's what enables the surreal effect. The pooled output conditions the timestep embedding, providing global guidance to the generation. With real CLIP-G, the model "knows" what a normal image should look like and resists the extrapolated conditioning.

**Round 3 — The negative prompt:**
Even after fixing the pooled output, images were still collage-like. Investigation revealed the **negative prompt was empty** (`""`). The original ComfyUI workflow uses `"watermark"` as negative, also fused with the same alpha. At α=17.6, an empty-string negative produces extrapolated special-token garbage as the CFG reference point, corrupting the entire generation.

### Lessons for Future Deconstructive Workflows

1. **Never assume standard encoding matches custom workflows.** The original Surrealizer intentionally degrades the encoding (CLIP-L only, no CLIP-G) to create its effect. Standard "best practice" (using all encoders) destroys the artistic intent.

2. **Pooled output is as important as the main embedding.** For SD3, pooled conditions the timestep embedding — it's a global steering signal. Zeroing parts of it changes the generation character fundamentally.

3. **Read the original ComfyUI node graph AND the ComfyUI source code.** The workflow JSON shows which nodes connect, but understanding the actual tensor shapes requires reading `sd3_clip.py:encode_token_weights()` and understanding what happens when individual encoders are None.

4. **The negative prompt matters enormously in the extrapolated regime.** CFG subtracts negative from positive predictions. Both are extrapolated with the same alpha, so they're in the same "scale space". The semantic content of the negative determines what the image pushes AWAY from — a powerful creative parameter.

5. **Seed logic must track ALL user-adjustable parameters.** Keep seed stable when any parameter changes (for comparability), new seed only when nothing changed (user wants variation).

### Changes Made

1. **`diffusers_backend.py`**: Exact ComfyUI replication — CLIP-L only, pooled = CLIP-L(768d) + zeros(1280d), no CLIP-G anywhere
2. **`output_image_surrealizer_diffusers.json`**: Added `negative_prompt` default "watermark", CFG 5.5
3. **`schema_pipeline_routes.py`**: Pass `negative_prompt` and `cfg` through legacy endpoint
4. **`surrealizer.vue`**: Configurable negative prompt + CFG in collapsible "Weitere Einstellungen"; fixed seed logic to track all parameters
5. **`i18n.ts`**: DE/EN strings for new controls with explanations; fixed `|` pipe pluralization bug (use `{'|'}`)
6. **`DEVELOPMENT_DECISIONS.md`**: Corrected pooled output description (was incorrectly claiming real CLIP-G)
7. **`ARCHITECTURE PART 25`**: Updated code example and design decisions to reflect no-CLIP-G-anywhere approach

### Key References
- Original fusion node: `/SwarmUI/dlbackend/ComfyUI/custom_nodes/ai4artsed_comfyui/ai4artsed_t5_clip_fusion.py`
- SD3 CLIP encoding: `/SwarmUI/dlbackend/ComfyUI/comfy/text_encoders/sd3_clip.py` (SD3ClipModel.encode_token_weights)
- Original workflow: `devserver/schemas/chunks/legacy_surrealization.json` (Node 54: CLIPLoader clip_l, Node 18: CLIPLoader t5xxl)

---

## Session 162 - Hallucinator: Diffusers Token-Level Fusion + Rename
**Date:** 2026-02-08
**Focus:** Fix broken Diffusers embedding fusion, document the complete technical mechanism, rename Surrealizer → Hallucinator
**Status:** COMPLETE

### Problems

1. **Broken embedding fusion:** The Diffusers backend blended joint SD3 embeddings instead of individual encoder outputs, destroying the CLIP signal at high alpha values (α=10 already extreme, α=25 white/blank).
2. **Inaccurate explanations:** User-facing text described "interpolation" and "weighting" — the actual mechanism is extrapolation into unexplored vector space, producing AI hallucinations.
3. **Misleading name:** "Surrealizer" implies stylistic surrealism. The effect is genuine AI hallucination from out-of-distribution vectors.

### Root Causes

1. **Joint vs. individual embeddings:** `pipe.encode_prompt()` returns all three encoders (CLIP-L + CLIP-G + T5) concatenated. Blending two such tensors (one with CLIP active/T5 empty, other reversed) pushes CLIP embeddings toward negative of the prompt (`-19·CLIP(prompt) + 20·CLIP("")`) instead of extrapolating between encoder spaces.
2. **Outdated references:** Configs still mentioned "legacy ComfyUI workflow", "interpolation", "vector interpolation".

### Technical Analysis: How the Hallucinator Works

**SD3.5 has two text encoders relevant to the Hallucinator:**
- **CLIP-L** (77 tokens, 768-dim): Trained on image-text pairs. Maps text to visual features.
- **T5-XXL** (512 tokens, 4096-dim): Trained on text-only tasks. Maps text to linguistic structure.

**The fusion formula (first 77 tokens):**
```
fused = (1 - α) · CLIP-L_padded + α · T5
```

At α=20: `fused = -19·CLIP-L + 20·T5` — the embedding is pushed 19× past T5's representation, into a region of the 4096-dimensional space that the diffusion model never encountered during training. The model must interpret these out-of-distribution vectors, producing genuine hallucinations.

**The semantic anchor (tokens 78-512):**
The remaining T5 tokens are appended unchanged. These keep the image thematically connected to the prompt even as the first 77 tokens push into hallucinatory territory.

**Why extrapolation, not interpolation, matters:**
- Interpolation (0≤α≤1): Smooth blend between two valid representations → mild variations
- Extrapolation (α>1): Pushes PAST both representations → out-of-distribution vectors → hallucination
- The "sweet spot" α=15-35 pushes far enough for visual surprise but not so far that the model loses all coherence

### Fixes Applied

**1. Token-level fusion (diffusers_backend.py)**
- Replaced `pipe.encode_prompt()` calls with individual encoder access: `pipe._get_clip_prompt_embeds()` and `pipe._get_t5_prompt_embeds()`
- CLIP-L (768d) padded to T5 dimension (4096d)
- First 77 tokens: LERP with alpha (enabling extrapolation)
- Remaining T5 tokens: appended unchanged (semantic anchor)
- Negative prompt fused with same alpha (matching ComfyUI workflow)
- All 4 embedding tensors passed to pipeline, bypassing `encode_prompt()` entirely

**2. Comprehensive documentation rewrite**
- All config descriptions: "interpolation" → "extrapolation", removed "legacy ComfyUI" references
- i18n (DE+EN): Explained mechanism accessibly — two AI "brains", extrapolation beyond training data, hallucination
- DokumentationModal: Rewritten with "Why do images become surreal?" section explaining out-of-distribution vectors
- Architecture Part 22: Added complete Diffusers backend section with code, failed approach analysis, design decisions
- Development Decisions: Full technical rationale for individual-encoder approach vs joint-embedding blending

**3. Rename Surrealizer → Hallucinator (display name only)**
- All user-facing names: "Surrealizer/Surrealisierer" → "Hallucinator"
- Config names: "Surrealization" → "Hallucination/Halluzination"
- Button: "Surrealisieren" → "Halluzinieren"
- Slider labels: i18n'd ("extrem", "invers", "normal", "halluziniert", "extrem")
- Internal IDs unchanged: `surrealizer` (config, pipeline, route, Vue filename)

### Files Modified
- `devserver/my_app/services/diffusers_backend.py` — `generate_image_with_fusion()` rewritten with `_fuse_prompt()` helper
- `devserver/schemas/configs/interception/surrealizer.json` — name, description, context, tags, audience
- `devserver/schemas/configs/output/surrealization_diffusers.json` — name, description
- `devserver/schemas/configs/output/surrealization_legacy.json` — name
- `devserver/schemas/chunks/output_image_surrealizer_diffusers.json` — description, alpha_factor docs, meta.notes
- `public/ai4artsed-frontend/src/i18n.ts` — DE+EN surrealizer section rewritten + slider keys
- `public/ai4artsed-frontend/src/views/surrealizer.vue` — i18n'd slider labels, button text, α display
- `public/ai4artsed-frontend/src/components/DokumentationModal.vue` — Hallucinator explanation card
- `docs/ARCHITECTURE PART 22 - Legacy-Workflow-Architecture.md` — Diffusers backend section, technical analysis
- `docs/DEVELOPMENT_DECISIONS.md` — Three decisions documented

### Key Learnings
- `pipe.encode_prompt()` returns **joint** SD3 embeddings (all 3 encoders concatenated). You CANNOT extrapolate between encoder spaces by blending two joint embeddings — you must access individual encoders.
- The surreal/hallucinatory effect comes specifically from **extrapolation** (α>1), not interpolation. At α=20, the model interprets vectors 19× past T5's representation — genuine out-of-distribution inference.
- The remaining T5 tokens (78+) act as a semantic anchor. Without them, the image loses all connection to the prompt.
- Private methods `_get_clip_prompt_embeds()` and `_get_t5_prompt_embeds()` are stable in diffusers v0.36.0 and provide exactly the individual encoder access needed.
- "Hallucinator" is more technically precise than "Surrealizer" — the effect is the model hallucinating from out-of-distribution vectors, not imitating surrealist art style.

---

## Session 161 - Post-Generation VLM Safety Check + Safety Architecture Clarification
**Date:** 2026-02-07
**Focus:** Close the gap between text-based safety checks and actual image content using local VLM (qwen3-vl:2b)
**Status:** COMPLETE

### Problems

1. **Text-based safety checks can't predict image content**: Stage 1+3 check the prompt text, but a harmless prompt can produce a disturbing image. No post-generation content verification existed.
2. **Safety architecture lacked clarity**: DSGVO, §86a StGB, and Jugendschutz were conceptually mixed — different concerns that need to be independently understood.

### Root Causes

1. **No visual verification layer**: The pipeline went directly from Stage 4 output to SSE `complete` event without inspecting the generated image.
2. **"Safety" was treated as one thing**: DSGVO (data protection), §86a (criminal law), and Jugendschutz (age-appropriate content) are three independent legal/pedagogical concerns with different triggers, scopes, and safety levels.

### Fixes Applied

**Feature: Post-Generation VLM Safety Check**
- Added `VLM_SAFETY_MODEL = "qwen3-vl:2b"` to `config.py:135`
- Added `_vlm_safety_check_image()` to `schema_pipeline_routes.py:2162` — reads image from recorder, base64-encodes, sends to Ollama /api/chat with age-appropriate prompt
- Inserted VLM check in `execute_generation_streaming()` between Stage 4 success and `complete` SSE event
- Only triggers for `media_type == 'image'` AND `safety_level in ('kids', 'youth')`
- Fail-open on any error (VLM unavailability never blocks generation)
- SSE event: `blocked` with `stage: 'vlm_safety'` when image flagged as unsafe

**qwen3-vl Thinking Mode Fix**
- qwen3-vl:2b returns analysis in `message.thinking` field, not `message.content`
- `num_predict: 500` needed (100 tokens = thinking cut off mid-sentence, empty content)
- Code checks both `content` and `thinking` fields for "unsafe" keyword

**Documentation: Safety Architecture Clarification**
- Updated architecture docs, design decisions, dev log, Träshy knowledge base
- Documented three independent safety concerns: §86a, DSGVO, Jugendschutz
- Documented VLM check as post-Stage-4 layer

### Files Modified
- `devserver/config.py:135` — `VLM_SAFETY_MODEL` config variable
- `devserver/my_app/routes/schema_pipeline_routes.py:2162` — `_vlm_safety_check_image()` function
- `devserver/my_app/routes/schema_pipeline_routes.py:2455` — VLM check insertion in streaming flow
- `docs/ARCHITECTURE PART 01 - 4-Stage Orchestration Flow.md` — Post-4 VLM check in stage table + flow diagram
- `docs/DEVELOPMENT_DECISIONS.md` — Safety architecture decisions
- `devserver/trashy_interface_reference.txt` — Section 8 rewritten with layered safety explanation
- `docs/reference/safety-architecture-matters.md` — VLM appendix

### Key Learnings
- qwen3 models use "thinking mode" by default — response splits into `message.thinking` (reasoning) and `message.content` (answer). Low `num_predict` exhausts tokens during thinking, leaving `content` empty
- Safety is not monolithic: §86a is **criminal law** (always on), DSGVO is **data protection** (always on), Jugendschutz is **pedagogical** (configurable per safety_level)
- Text safety checks (pre-generation) and VLM checks (post-generation) complement each other: Stage 1+3 = fast guard at the door, VLM = quality control at the exit
- Open question: Video generation needs similar post-generation check (not yet implemented)

---

## Session 160 - Music Gen V2 LLM Functions + Wikipedia Opt-In Refactor
**Date:** 2026-02-06
**Focus:** Fix broken LLM functions in music_generation_v2.vue + architectural refactor of Wikipedia research from opt-out to opt-in
**Status:** COMPLETE

### Problems

1. **SSE Streaming never started** (Theme→Lyrics, Refine Lyrics): Requests never reached the backend
2. **Tag Suggestion produced no result**: Backend ran but output was corrupted by Wikipedia loop
3. **Wikipedia was architecturally backwards**: Hardcoded in `manipulate.json` template, required `skip_wikipedia` flag to disable — opt-out instead of opt-in

### Root Causes

1. **Vue reactivity timing bug**: `runLyricsAction()` set `isLyricsProcessing=true` (triggering v-if mount of MediaInputBox) and `lyricsStreamUrl` in the same synchronous call. MediaInputBox mounted with URL already set — its `watch` on `streamUrl` only fires on changes, not initial values. `startStreaming()` was never called.

2. **Wikipedia loop corrupted output**: The non-streaming path didn't forward `skip_wikipedia` to the pipeline context. The LLM produced `<wiki>` markers (because instructions were in the prompt), triggering 3 Wikipedia iterations that converted the output to an input echo. `parseAndApplyTagSuggestions()` found no JSON → no tags applied.

3. **Architectural smell**: Wikipedia instructions were baked into `manipulate.json` — every `manipulate` chunk call got Wikipedia instructions, even lyrics refinement and tag suggestion. The `skip_wikipedia` flag was a workaround, not a solution.

### Fixes Applied

**Bug Fix A — SSE Streaming (music_generation_v2.vue)**
- `runLyricsAction()` made `async`, resets `lyricsStreamUrl` to `''`, then sets URL via `await nextTick()` so MediaInputBox's watch fires

**Bug Fix B + Architectural Refactor — Wikipedia Opt-In**
- Created `schemas/engine/wikipedia_prompt_helper.py` — Wikipedia instructions as standalone module
- Cleaned `manipulate.json` — removed Wikipedia block and `WIKIPEDIA_CONTEXT` placeholder
- Modified `pipeline_executor.py:_execute_single_step()` — checks `config.meta.get('wikipedia', False)` to conditionally enable Wikipedia instructions + research loop
- Added `"wikipedia": true` to 28 pedagogical interception configs (all except music/code)
- Removed `skip_wikipedia` from entire codebase (frontend v1+v2, backend streaming+non-streaming paths)

### Files Modified
- `public/ai4artsed-frontend/src/views/music_generation_v2.vue` — async runLyricsAction + nextTick
- `public/ai4artsed-frontend/src/views/music_generation.vue` — removed skip_wikipedia
- `devserver/schemas/engine/wikipedia_prompt_helper.py` — NEW: Wikipedia instructions module
- `devserver/schemas/chunks/manipulate.json` — cleaned template
- `devserver/schemas/engine/pipeline_executor.py` — Wikipedia opt-in logic
- `devserver/my_app/routes/schema_pipeline_routes.py` — removed all skip_wikipedia plumbing
- `devserver/schemas/configs/interception/*.json` — 28 configs updated with `"wikipedia": true`

### Key Learnings
- Vue `watch()` without `{ immediate: true }` does NOT fire on initial mount values — critical when combining `v-if` conditional rendering with reactive prop changes
- Architectural opt-out patterns (features that must be explicitly disabled) are fragile — prefer opt-in (features must be explicitly enabled)
- Wikipedia research is a pedagogical feature specific to `text_transformation.vue` art configs, not a universal pipeline feature

---

## Session 159 - HeartMuLa Production CUDA Crash Fix
**Date:** 2026-02-06
**Focus:** Fix HeartMuLa music generation crashing in production but not dev
**Status:** COMPLETE

### Problem

HeartMuLa worked in dev (port 17802) but crashed in production (port 17801) with CUDA "index out of bounds" during codec detokenization. Investigation revealed two layered issues.

### Root Causes

1. **Redundant `torch.autocast` wrapper** (`heartmula_backend.py:279`)
   - Wrapped entire `self._pipeline()` call in `torch.autocast("cuda", dtype=torch.bfloat16)`
   - Forced bfloat16 on HeartCodec which requires float32
   - heartlib already handles autocast internally for MuLa generation only (`music_generation.py:284, 318`)
   - Different PyTorch nightly versions (dev: Feb 3, prod: Feb 4) determined whether this crashed or not

2. **Vocab/codebook size mismatch in heartlib** (the actual bug)
   - MuLa `audio_vocab_size` = 8197, codec `codebook_size` = 8192
   - MuLa can generate token indices 8192-8196 that exceed codec's embedding range
   - Causes CUDA index out of bounds in `vq_embed.get_output_from_indices()`
   - Data-dependent: longer generations and certain lyrics/tag combinations trigger it more often
   - No bounds checking existed anywhere in the heartlib pipeline

### Fixes Applied

1. **Removed outer autocast** — `heartmula_backend.py:279`: `torch.autocast` removed, `torch.no_grad()` kept
2. **Index clamping in heartlib** — `flow_matching.py:75`: `torch.clamp(codes, 0, codebook_size - 1)` before embedding lookup
3. **Tightened Vue slider ranges** — `music_generation_v2.vue`: Top-K max 200→100, CFG max 5.0→4.0
4. **Updated installation docs** — `INSTALLATION.md`: documented post-install clamp fix and PyTorch version sensitivity

### Files Modified
- `devserver/my_app/services/heartmula_backend.py` — removed autocast
- `public/ai4artsed-frontend/src/views/music_generation_v2.vue` — slider limits
- `docs/installation/INSTALLATION.md` — heartmula setup warnings
- `~/ai/heartlib/src/heartlib/heartcodec/models/flow_matching.py` — index clamping (separate repo)

### Key Learnings
- heartlib manages dtype internally — never wrap `self._pipeline()` in external autocast
- PyTorch nightly builds are fragile on Blackwell GPUs — even 1 day difference breaks things
- MuLa vocab > codec codebook is a design flaw in heartlib; clamp is a necessary workaround

---

## Session 158 - Music Generation Unified Page (Simple/Advanced Toggle)
**Date:** 2026-02-06
**Focus:** Unify V1 and V2 music generation into single page with mode toggle
**Status:** COMPLETE ✅

### Summary

Created a unified music generation page that offers both the simple (V1) and advanced (V2) interfaces via a toggle switch. This addresses the pedagogical trade-off: V1 is accessible but teaches nothing about music; V2 teaches music vocabulary but has complex ML parameters.

### Pedagogical Rationale

**V1 (Simple Mode):**
- Dual text inputs: lyrics + free-form tags
- Low barrier to entry
- No scaffolding for students without lyrics
- Tags as free-text requires prior knowledge

**V2 (Advanced Mode):**
- Lyrics Workshop: "Theme → Lyrics" scaffold for students without lyrics
- Sound Explorer: 8-dimension chip selector teaches music vocabulary (genre, timbre, mood, instruments, etc.)
- "Suggest from Lyrics" bridges lyrics→sound understanding
- ML parameters (temp, topk, cfg) now with good defaults
- Custom tags input for power users

### Key Changes

1. **Unified Wrapper** (`music_generation_unified.vue`)
   - Sticky toggle at top: Simple / Advanced
   - Mode persists to localStorage
   - Background adapts (solid #0a0a0a for V1, gradient for V2)

2. **Router Update**
   - `/music-generation` → unified page
   - `/music-generation-simple` → direct V1 access
   - `/music-generation-advanced` → direct V2 access

3. **V2 Defaults Updated**
   - Audio length: 120s → 200s (3:20)
   - Top-K: 70 → 65
   - CFG Scale: 3.0 → 2.75

4. **Custom Tags Feature**
   - MusicTagSelector now accepts `v-model:customTags`
   - Text input below chip grid
   - Merged into compiledTags output

### Files Created
- `public/ai4artsed-frontend/src/views/music_generation_unified.vue`

### Files Modified
- `public/ai4artsed-frontend/src/router/index.ts` — unified route
- `public/ai4artsed-frontend/src/components/MusicTagSelector.vue` — custom tags
- `public/ai4artsed-frontend/src/views/music_generation_v2.vue` — new defaults + customTags
- `public/ai4artsed-frontend/src/i18n.ts` — simpleMode, advancedMode, customTags keys

---

## Session 157 - Music Generation V2 (Lyrics Workshop + Sound Explorer)
**Date:** 2026-02-05
**Focus:** New music generation UI concept + HeartMuLa tag system + performance tuning
**Status:** COMPLETE ✅

### Summary

Redesigned the music generation frontend as a dual creative-process workbench. Investigated why user-selected genres were ineffective and fixed the root causes (LLM prompt bias + tag format). Added generation parameter controls and batch mode.

### Key Achievements

1. **Root Cause Analysis: Ineffective Genre Tags**
   - Verified genre injection works end-to-end (frontend → chunk_builder → heartmula_backend → model)
   - Found 2 bugs: (A) `tags_generation.json` LLM prompt hardcoded ROBOTIC/ELECTRONIC bias, overriding user genre; (B) Tag format used spaces after commas, HeartMuLa expects no spaces
   - Researched HeartMuLa tag system: 8 dimensions with training probabilities (Genre 0.95, Timbre 0.5, Gender 0.375, Mood 0.325, Instrument 0.25, Scene 0.2, Region 0.125, Topic 0.1)

2. **Music Generation V2 Page** (`music_generation_v2.vue`)
   - **Process A: Lyrics Workshop** — User writes theme/keywords/lyrics, clicks [Thema→Lyrics] or [Lyrics verfeinern], LLM streams result
   - **Process B: Sound Explorer** — 8-dimension chip selector (MusicTagSelector.vue), LLM auto-suggest from lyrics, manual toggle
   - New interception configs: `lyrics_from_theme.json`, `tag_suggestion_from_lyrics.json`
   - Hidden route (`/music-generation-v2`) — workbench tool, not pedagogical feature
   - Original `music_generation.vue` untouched at `/music-generation`

3. **Generation Controls**
   - Temperature, Top-K, CFG Scale sliders with injection via `custom_placeholders`
   - Batch mode: `[-] Nx [+]` counter, sequential generation runs
   - Updated defaults: Top-K 50→70, CFG Scale 1.5→3.0 (all 6 locations)

4. **Backend Performance**
   - Tag format sanitization in `output_music_heartmula.py` (strip spaces, underscores for multi-word)
   - `torch.autocast("cuda", dtype=torch.bfloat16)` for fused RMS-norm kernels (fixes dtype mismatch warning)
   - `torch.compile()` tested but incompatible with heartlib (crashes on batch) — removed
   - Server `channel_timeout=600` for long music generation requests

### Files Created
- `public/ai4artsed-frontend/src/views/music_generation_v2.vue`
- `public/ai4artsed-frontend/src/components/MusicTagSelector.vue`
- `devserver/schemas/configs/interception/lyrics_from_theme.json`
- `devserver/schemas/configs/interception/tag_suggestion_from_lyrics.json`

### Files Modified
- `devserver/schemas/chunks/output_music_heartmula.py` — tag normalization, new defaults
- `devserver/my_app/services/heartmula_backend.py` — autocast bfloat16, new defaults
- `devserver/schemas/configs/output/heartmula_standard.json` — new defaults
- `devserver/schemas/engine/backend_router.py` — new defaults
- `devserver/server.py` — channel_timeout=600
- `public/ai4artsed-frontend/src/router/index.ts` — v2 route
- `public/ai4artsed-frontend/src/i18n.ts` — musicGenV2 keys (DE + EN)

---

## Session 156 - HeartMuLa Integration (Python-Chunk Pattern)
**Date:** 2026-02-02 to 2026-02-03
**Focus:** First Python-based Output-Chunk Implementation
**Status:** COMPLETE ✅

### Summary

Implemented HeartMuLa music generation as the **first Python-based Output-Chunk**, establishing a new standard pattern that replaces deprecated JSON chunks for non-ComfyUI backends.

### Key Achievements

1. **Python-Chunk Pattern Established**
   - Created `output_music_heartmula.py` - self-contained executable chunk
   - Chunk contains complete backend logic (no central router delegation)
   - Uses async `execute()` function with type-safe parameters
   - Returns bytes (MP3 audio) directly

2. **Architecture Decision: Generic backend_type**
   - ALL Python chunks use `backend_type='python'` (generic)
   - Chunk name determines implementation (e.g., `output_music_heartmula`)
   - No per-backend enum entries needed (extensible design)
   - Removed HEARTMULA enum (redundant)

3. **New Pipeline Created**
   - `dual_text_media_generation.json` - 2 text inputs → media output
   - Uses `{{OUTPUT_CHUNK}}` placeholder (resolved from config)
   - No Proxy-Chunk pattern (direct chunk selection)
   - Skip Stage 2 (passthrough to Stage 4)

4. **Implementation Fixes (5 Errors Resolved)**
   - Placeholder resolution in config_loader.py
   - Output-Chunk detection in backend_router.py
   - Python chunk detection in chunk_builder.py
   - BackendResponse content="" for error cases
   - BackendType.PYTHON enum added

5. **Documentation Updates**
   - ARCHITECTURE PART 03: Added Python-Chunk section (Type 2B)
   - ARCHITECTURE PART 05: Updated routing documentation
   - JSON chunks declared DEPRECATED (use only for pure ComfyUI passthrough)
   - Created ARCHITECTURE_VIOLATION_ProxyChunkPattern.md

### Technical Details

**Input:** 2 text fields (lyrics + style tags)
**Output:** MP3 audio bytes
**Backend:** heartlib (external Python library)
**Pipeline:** `dual_text_media_generation` → `output_music_heartmula`

**Files Created:**
- `devserver/schemas/chunks/output_music_heartmula.py`
- `devserver/schemas/pipelines/dual_text_media_generation.json`
- `docs/ARCHITECTURE_VIOLATION_ProxyChunkPattern.md`

**Files Modified:**
- `devserver/schemas/engine/backend_router.py` - Python chunk execution
- `devserver/schemas/engine/config_loader.py` - Placeholder resolution
- `devserver/schemas/engine/chunk_builder.py` - Python chunk detection
- `devserver/schemas/configs/output/heartmula_standard.json`
- `public/ai4artsed-frontend/src/views/music_generation.vue`
- `docs/ARCHITECTURE PART 03 - ThreeLayer-System.md`
- `docs/ARCHITECTURE PART 05 - Pipeline-Chunk-Backend-Routing.md`
- `docs/devserver_todos.md`

### Commits

- `958ae0d` - feat(chunks): Implement Python-based Output-Chunks (HeartMuLa reference)
- `e0ccfd6` - docs: Document architecture violations and Python-Chunk standard
- `5d24a15` - fix(config-loader): Resolve placeholders in pipeline chunk names
- `d8f420f` - fix(chunks): Complete Python-Chunk routing and execution flow
- `a3354ff` - fix(backend): Add PYTHON to BackendType enum
- `c03499a` - docs(architecture): Complete Python-Chunk documentation + backend fixes

### Testing Status

✅ Python chunk loads and executes correctly
✅ Backend routing works (backend_type='python')
✅ Parameters passed correctly (11 parameters verified)
✅ Error handling works (heartlib not installed - expected)
❌ Actual music generation - requires heartlib installation

### Future Work

- Install heartlib for actual music generation
- Refactor existing Diffusers chunks to Python pattern
- Remove deprecated JSON-based Output-Chunks (if no ComfyUI passthrough needed)
- Migrate Proxy-Chunk pattern in `single_text_media_generation`

### Notes

This session established the **reference implementation** for all future Python-based backends. The pattern is simpler, more maintainable, and more extensible than JSON chunks.

---

## Session 155 - Z-Image Integration Attempt
**Date:** 2026-02-02
**Focus:** Z-Image 6B Model Evaluation
**Status:** REJECTED

### Summary

Attempted integration of Z-Image (Alibaba Tongyi Lab) as new image generation model.

### Actions Taken

1. **Session 150**: Downloaded Z-Image models for ComfyUI (~28GB safetensors)
2. **Session 155**: Switched to Diffusers backend (ZImagePipeline)
3. **Testing**: Model produces content unsafe for educational platform

### Decision

**Z-Image wird nicht angeboten.** Das Modell generiert Inhalte, die für die pädagogische Plattform AI4ArtsEd ungeeignet sind.

### Cleanup

- All Z-Image configs removed
- Model files deleted from SwarmUI
- Commits: `2fb94fb` (integration), `9fedf40` (revert)

---

## Session 154 - Canvas Parameter Injection System
**Date:** 2026-02-01
**Focus:** Parameter Nodes (Seed, Resolution, Quality) + Input Handling Fixes
**Status:** COMPLETED

### Overview

Complete parameter injection system for Canvas workflows, enabling users to control generation parameters (seed, resolution, steps, cfg) through visual nodes.

### Architecture: Parameter Injection Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (Canvas)                                                   │
│  ├─ Parameter Nodes (Seed, Resolution, Quality)                     │
│  ├─ Values stored in CanvasNode properties                          │
│  └─ Passed to backend via /api/canvas/execute-stream                │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Backend (canvas_executor.py)                                        │
│  ├─ Parameter nodes executed as source nodes (no propagation)       │
│  ├─ Generation node collects params from connected parameter nodes  │
│  └─ Calls execute_stage4_generation_only() with params              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Pipeline Executor                                                   │
│  ├─ Params injected via custom_placeholders                         │
│  ├─ Only params in config's input_mappings are applied              │
│  └─ Unsupported params gracefully ignored                           │
└─────────────────────────────────────────────────────────────────────┘
```

### New Node Types

| Node | Type | Color | Purpose |
|------|------|-------|---------|
| **Seed** | `seed` | Teal (#14b8a6) | Control random seed for reproducibility |
| **Resolution** | `resolution` | Teal (#14b8a6) | Set width/height dimensions |
| **Quality** | `quality` | Teal (#14b8a6) | Set steps and CFG scale |

### Seed Node Modes

| Mode | Behavior |
|------|----------|
| `fixed` | Use specified seed value (default: 123456789) |
| `random` | Generate random seed per execution |
| `increment` | Base seed + batch index (for batch runs) |

### Resolution Presets

| Preset | Dimensions | Use Case |
|--------|------------|----------|
| `square_1024` | 1024 × 1024 | SD3.5 default |
| `portrait_768x1344` | 768 × 1344 | Portrait images |
| `landscape_1344x768` | 1344 × 768 | Landscape images |
| `custom` | User-defined | Any resolution |

### Parameter Support Matrix

| Parameter | SD3.5 | Flux2 | GPT-Image | Gemini | ACEnet | Wan22 |
|-----------|:-----:|:-----:|:---------:|:------:|:------:|:-----:|
| `seed` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `width` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `height` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `steps` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `cfg` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |

**Note:** API-based backends (GPT-Image, Gemini) ignore ComfyUI parameters.

### Bug Fixes

1. **Parameter nodes not propagating** - Fixed `_find_source_nodes()` to recognize seed/resolution/quality
2. **Double execution** - Parameter nodes now return `[]` from `_get_next_nodes()`
3. **Input events not firing** - Changed `@blur/@keyup.enter` to `@input` for immediate updates
4. **Node drag on input click** - Added `@mousedown.stop` to all parameter node inputs
5. **Wrong default seed** - Changed from 42 to 123456789 (system standard)

### useGenerationStream Integration

Other views can inject parameters via the composable:

```typescript
import { useGenerationStream } from '@/composables/useGenerationStream'

const { startGeneration } = useGenerationStream()

await startGeneration({
  prompt: 'A sunset over mountains',
  outputConfig: 'sd35_large',
  safetyLevel: 'youth',
  // Parameter injection:
  width: 1920,
  height: 1080,
  steps: 30,
  cfg: 7.0
})
```

### Modified Files

| File | Changes |
|------|---------|
| `types/canvas.ts` | Added `seed`, `resolution`, `quality` to StageType + NODE_TYPE_DEFINITIONS |
| `stores/canvas.ts` | Node property defaults |
| `components/canvas/StageModule.vue` | Node UI templates + event handling fixes |
| `components/canvas/ModulePalette.vue` | Added nodes to "Tools" category |
| `views/canvas_workflow.vue` | Event handlers for new nodes |
| `composables/useGenerationStream.ts` | Extended GenerationParams interface |
| `services/canvas_executor.py` | `_execute_seed()`, `_execute_resolution()`, `_execute_quality()` |
| `routes/schema_pipeline_routes.py` | Extended SSE endpoint + `execute_stage4_generation_only()` |

### Commits

- `1dca36c` - fix(edutainment): Show summary when first loop completes OR 10s elapsed
- `367c4b4` - fix(canvas): Fix parameter node inputs not updating values
- `d2d246a` - fix(canvas): Fix all parameter node input handling

---

## Session 153 - Localhost Auto-Login for Settings
**Date:** 2026-01-31
**Focus:** Skip password authentication for local development
**Status:** COMPLETED

### Problem

- Browser password managers don't work reliably with `localhost:17802` (no proper domain)
- No password recovery mechanism
- Unnecessary friction during local development

### Solution

Auto-login for localhost requests, similar to ComfyUI's approach.

### Implementation

Added `is_localhost_request()` helper that checks:
- `request.remote_addr` in `('127.0.0.1', '::1')`
- `request.host` in `('localhost', '127.0.0.1')`

Modified `require_settings_auth` decorator to bypass authentication for localhost.
Modified `/api/settings/check-auth` to return `auto_login: true` for localhost.

### Security

- Production access via `lab.ai4artsed.org` still requires password
- Only true localhost connections are auto-authenticated
- `request.remote_addr` is set by Flask/Werkzeug, not user-manipulable

### Modified Files

| File | Change |
|------|--------|
| `routes/settings_routes.py` | `is_localhost_request()`, decorator bypass, check-auth update |

### Commit

`af9b988` - feat(settings): Auto-login for localhost development

---

## Session 152 - Tone.js Browser-Based Music Generation
**Date:** 2026-01-31
**Focus:** Add Tone.js as new output option for browser-based music synthesis
**Status:** COMPLETED

### Overview

Following the p5.js pattern for generative graphics, Tone.js enables browser-based music generation. The LLM generates Tone.js JavaScript code that runs directly in the frontend via iframe.

### Architecture Pattern: Code Generation Output

| Component | p5.js (Graphics) | Tone.js (Audio) |
|-----------|------------------|-----------------|
| Chunk Type | `text_passthrough` | `text_passthrough` |
| Backend Type | `vue_p5js` | `vue_tonejs` |
| Media Type | `code` | `code` |
| Language | JavaScript | JavaScript |
| Execution | Browser Canvas | Web Audio API |

**Key Difference from Binary Media:**
- No ComfyUI/SwarmUI workflow execution
- LLM generates code directly (Claude Sonnet 4.5 via OpenRouter)
- Code passed through to frontend for browser execution
- No server-side rendering required

### New Files

| File | Description |
|------|-------------|
| `schemas/chunks/output_code_tonejs.json` | Passthrough chunk for Tone.js code |
| `schemas/configs/output/tonejs_code.json` | Output config with LLM prompt |
| `schemas/configs/interception/tonejs_composer.json` | Stage 2: Text → Musical structure |

### Modified Files

| File | Change |
|------|--------|
| `routes/schema_pipeline_routes.py` | Media type detection for 'tonejs' (4 locations) |
| `routes/media_routes.py` | New route `/api/media/tonejs/<run_id>` |
| `text_transformation.vue` | Tone.js config bubble, iframe with Play/Stop |
| `text_transformation.css` | Styles for `.tonejs-iframe` |
| `canvas.ts` | `tonejs_composer` in InterceptionPresets |
| `THIRD_PARTY_CREDITS.md` | p5.js (LGPL-2.1) and Tone.js (MIT) licenses |

### Stage 2 Interception: Music Composer

Transforms text descriptions into layered musical structure:
```
RHYTHM: [Drums, percussion patterns]
BASS: [Bass line characteristics]
HARMONY: [Chord progressions, pads]
MELODY: [Lead lines, hooks]
TEXTURE: [Ambient elements, effects]
```

### Frontend: Tone.js Player

- Play/Stop buttons (required due to browser audio policy)
- Visual feedback (animated bars visualizer)
- Status indicator (German: "Klicke Play um die Musik zu starten")
- Code editor for viewing/editing generated code

### Third-Party Libraries (CDN)

- **p5.js** v1.7.0 - LGPL-2.1 - Creative coding for graphics
- **Tone.js** v14.8.49 - MIT - Web Audio framework for music

### Commit

`0e7bd45` - feat(audio): Add Tone.js browser-based music generation

---

## Session 151 - Edutainment Animations: Environmental Impact Visualization
**Date:** 2026-01-31
**Focus:** Wissenschaftlich fundierte CO2-Visualisierungen für AI-Generierung
**Status:** IN PROGRESS

### Neue Features

**1. IcebergAnimation - Arktis-Eis-Schmelze**
- Zeichne Eisberge, beobachte Schmelzen während GPU arbeitet
- Segelschiff als Fortschrittsanzeige (links→rechts)
- Abschluss-Info: CO2-Menge → cm³ geschmolzenes Arktis-Eis
- Berechnung: 1g CO2 = 6 cm³ Eis (basierend auf Notz & Stroeve 2016)

**2. ForestMiniGame - Interaktives Baumpflanzen**
- Spiel: Pflanze Bäume gegen Fabriken (GPU-Power = Fabrik-Spawn-Rate)
- 7 Baumtypen (Kiefer, Fichte, Tanne, Eiche, Birke, Ahorn, Weide)
- Vogel als Fortschrittsanzeige (Sprite-Animation, Open Source)
- Fabrik auf Baum → Fabrik verschwindet
- Abschluss: Baum-CO2-Absorption (22kg/Jahr = 2.51g/Stunde)

**3. PixelAnimation - GPU-Stats + Smartphone-Vergleich**
- Echtzeit GPU-Werte: Grafikkarte, Energieverbrauch, CO2
- Abschluss: "Du müsstest Dein Handy X Minuten ausschalten"
- Berechnung: 5W Smartphone × 400g CO2/kWh = 30 min pro g CO2

### Wissenschaftliche Grundlagen

| Metrik | Wert | Quelle |
|--------|------|--------|
| Baum CO2-Absorption | 22 kg/Jahr | EPA, Arbor Day Foundation |
| Arktis-Eisverlust | 3 m²/Tonne CO2 | Notz & Stroeve, Science 2016 |
| Eisdicke (Durchschnitt) | ~2m | → 6 m³/Tonne = 6 cm³/g |
| Smartphone Standby | ~5W | Energiestudien |
| Deutscher Strommix | ~400g CO2/kWh | Umweltbundesamt |

### Pädagogische Intention

**Sichtbarmachung unsichtbarer Kosten:**
- Abstrakte Zahlen (Watt, Gramm) → greifbare Metaphern
- Eisschmelze → globale Klimafolgen
- Bäume → lokale Ökosysteme
- Smartphone → persönlicher Alltag

**Handlungsbezug (ForestMiniGame):**
- Aktives Gegenhandeln während Verbrauch läuft
- Spielerische Reflexion: "Kann ich schneller pflanzen?"
- Nicht moralisierend, sondern informierend

### Modified Files

| File | Change |
|------|--------|
| `IcebergAnimation.vue` | Neuer Vergleich (cm³ Eis statt Baum-Stunden) |
| `ForestMiniGame.vue` | Vogel-Animation, Abschluss-Overlay |
| `SpriteProgressAnimation.vue` | GPU-Stats, Smartphone-Vergleich |
| `i18n.ts` | Neue Übersetzungen (iceberg, forest) |
| `ARCHITECTURE PART 15.md` | Design Decision #9 |
| `THIRD_PARTY_CREDITS.md` | Vogel-Sprite Lizenz |

### Integration in MediaOutputBox

**RandomEdutainmentAnimation.vue** - Wrapper-Komponente:
- Wählt zufällig eine der 3 Animationen bei Mount
- Bleibt während gesamter Generation konstant
- Empfängt nur `progress` prop

**Änderung in MediaOutputBox:**
- Ersetzt `SpriteProgressAnimation` durch `RandomEdutainmentAnimation`
- Alle Views die MediaOutputBox nutzen erhalten automatisch die neuen Animationen

### Fixes
- **Fehlende Eis-Zahl:** IcebergAnimation startet jetzt Energy-Tracking automatisch wenn progress > 0
- **Falsche Vergleiche:** ForestMiniGame nutzt jetzt `forest.comparison` (Baum), nicht `iceberg.comparison` (Eis)

### Commits
- `4d70f26` feat(forest): Add bird progress indicator and summary overlay

---

## Session 148 - "Translated" Badge mit SSE-Streaming
**Date:** 2026-01-30
**Focus:** Echtzeit-Badge via SSE wenn Prompt übersetzt wird (vor Bildgenerierung)
**Status:** COMPLETED

### Feature
Neues "Translated" Badge (→ EN) neben dem Safety-Approved Badge. Erscheint in **Echtzeit** nach Stage 3, **bevor** die Bildgenerierung beginnt. Ermöglicht durch SSE-Streaming des `/generation` Endpoints.

### Architektur: SSE für `/generation`

**Problem (ursprünglich):**
- Badge erschien erst nach kompletter Generation (zu spät)
- Safety-Badge wurde mit Fake-300ms-Delay gezeigt (nicht akkurat)

**Lösung:**
- Neuer SSE-Modus für `/generation` Endpoint
- Backend emittiert Events stage-by-stage
- Frontend zeigt Badges sobald `stage3_complete` Event eintrifft

### Backend Änderungen

**`schema_pipeline_routes.py`:**

1. **Neue Generator-Funktion** `execute_generation_streaming()`:
   - Emittiert: `connected`, `stage3_start`, `stage3_complete`, `stage4_start`, `complete`, `error`, `blocked`
   - `stage3_complete` enthält `{safe: bool, was_translated: bool}`

2. **Endpoint erweitert** (`/pipeline/generation`):
   - Unterstützt jetzt GET + POST
   - `enable_streaming=true` → SSE Response
   - Fallback: Original JSON Response

### Frontend Änderungen

**Neuer Composable** `useGenerationStream.ts`:
- Shared SSE-Handler für alle 3 Views
- Exponiert: `showSafetyApprovedStamp`, `showTranslatedStamp`, `generationProgress`, `currentStage`
- Methode: `executeWithStreaming(params)` → Promise\<GenerationResult\>
- Progress-Animation startet bei `stage4_start` Event

**Aktualisierte Views:**
- `text_transformation.vue`
- `image_transformation.vue`
- `multi_image_transformation.vue`

Alle nutzen jetzt den Composable statt lokaler Refs.

### Design-Entscheidungen
- **Icon**: `→ EN` (Pfeil + Text) - neutral, keine politische Konnotation
- **Farbe**: Teal (#009688) - unterscheidet sich von Grün (Safety), Lila (LoRA), Blau (Wikipedia)
- **Timing**: Badges erscheinen nach Stage 3, bevor Stage 4 startet

### Scope

| View | Endpoint | Badge |
|------|----------|-------|
| text_transformation | `/generation` | ✅ SSE |
| image_transformation | `/generation` | ✅ SSE |
| multi_image_transformation | `/generation` | ✅ SSE |
| surrealizer | `/legacy` | ❌ (kein Stage 3) |
| split_and_combine | `/legacy` | ❌ (kein Stage 3) |
| canvas_workflow | eigene Architektur | ❌ (separat) |

### Modified Files
| File | Change |
|------|--------|
| `devserver/my_app/routes/schema_pipeline_routes.py` | SSE-Modus für /generation |
| `public/.../composables/useGenerationStream.ts` | NEU - Shared SSE Composable |
| `public/.../views/text_transformation.vue` | Composable + Icon "→ EN" |
| `public/.../views/text_transformation.css` | `.translated-stamp` Styling |
| `public/.../views/image_transformation.vue` | Composable + Badge |
| `public/.../views/multi_image_transformation.vue` | Composable + Badge |

---

## Session 147 - Documentation Updates: Canvas & Pedagogical Framework
**Date:** 2026-01-29
**Focus:** Vollständige Canvas-Dokumentation, pädagogisches Framework, DokumentationModal-Erweiterungen
**Status:** COMPLETED

### Neue Dokumentation

**ARCHITECTURE PART 26 - Canvas-Workflow-System.md**
- Vollständige technische Dokumentation des Canvas Workflow Systems
- Alle 10 Node-Typen (inkl. neu: Comparison Evaluator)
- Connection Rules, Workflow Execution, Presets
- **Pedagogical Framework**: Lehrforschung, Dekonstruktion des Kontroll-Paradigmas, Prompt Interception, rekursiv-reflexive Workflows
- Zielgruppen, Verhältnis zu anderen Views

### DokumentationModal Änderungen

**Tabs neu organisiert:**
- FAQ-Tab aufgelöst und Inhalte verteilt
- Neue Reihenfolge: Willkommen, Anleitung, Pädagogik, Workshop, Experimente, Canvas

**Neue Inhalte:**
- **Canvas-Tab**: Pädagogisches Framework, Node-Typen mit Stage-Farbcodierung
- **Workshop-Tab**: LLM-Konfiguration (lokal/extern/DSGVO)
- **Pädagogik-Tab**: Prinzip 2 erweitert um "Prompt Interception"
- **Willkommen-Tab**: Datenschutz-Info, Kontakt

**Icons:**
- Canvas-Icon in Navigation: account_tree (korrekter Material Icons Pfad)
- Select-Icon in Anleitung: apps Icon (48px)

### Modified Files
| File | Change |
|------|--------|
| `docs/ARCHITECTURE PART 26 - Canvas-Workflow-System.md` | NEU - Vollständige Canvas-Dokumentation |
| `docs/00_MAIN_DOCUMENTATION_INDEX.md` | Part 26 hinzugefügt |
| `public/.../components/DokumentationModal.vue` | Canvas-Tab, Tab-Reorganisation, Icons |
| `public/.../src/App.vue` | Canvas-Icon (account_tree) |
| `public/.../composables/usePageContext.ts` | Träshy x: 2→8 (ungelöst) |
| `public/.../views/canvas_workflow.vue` | height: 100vh→100% |

---

## Session 144 - Interception Config Revision: Analog Photography 1970s
**Date:** 2026-01-28
**Focus:** Config-Text für detailliertere Objektbeschreibung optimiert
**Status:** COMPLETED

### Änderungstyp: Prompt-Strategie für Wikipedia-Integration

Die Analogfotografie-Config wurde überarbeitet, um die **Objektbeschreibungs-Qualität** zu verbessern - relevant für die neue Wikipedia-Suchfunktion (Session 142/143).

**Kernänderungen:**
1. **Neuer Fokus auf Recherche**: "Du arbeitest sorgfältig und informierst dich sehr genau über Deine Gegenstände. Du beschriebst sie extrem detailliert als fotografische Visualisierung"
2. **Entfernt**: Detaillierte Dunkelkammer-Terminologie (Zonenfokussierung, Push/Pull-Entwicklung, Papiergradwahl etc.) - diese technischen Details sind für die Bildgenerierung weniger relevant als präzise Objektbeschreibungen
3. **Vereinfacht**: Verbotene Sprache auf Kernpunkte reduziert

### Implikation für Config-Revision
Diese Änderung zeigt ein Muster für die Überarbeitung anderer Interception-Configs:
- **Weniger**: Stilistische/technische Detailverliebtheit im Prompt
- **Mehr**: Explizite Anweisung zur genauen Recherche und Beschreibung der Eingabe-Objekte
- **Ziel**: Bessere Wikipedia-Suchbegriffe durch detailliertere Objektnennung im Output

### Modified Files
| File | Change |
|------|--------|
| `devserver/schemas/configs/interception/analog_photography_1970s.json` | `context.de` neu formuliert |

---

## Session 143 - Wikipedia Opensearch API + Transparency
**Date:** 2026-01-28
**Focus:** Fix Wikipedia badge not appearing due to failed lookups
**Status:** COMPLETED

### Problem
Wikipedia badge never appeared because all lookups returned 404:
```
[WIKI] Looking up 'Igbo New Yam Festival' on en.wikipedia.org
[WIKI] Not found: 'Igbo New Yam Festival'
```

**Root Cause:**
- LLM generated search terms (e.g., "Igbo New Yam Festival") that don't match exact Wikipedia article titles
- Backend used direct Page Summary API (`/page/summary/{term}`) which requires exact title
- The actual article exists as "New Yam Festival" but wasn't found

### Solution
**1. Backend: Opensearch API as primary search**

Query construction:
```
https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={term}&limit=1&format=json
```

Response format:
```json
[searchTerm, [titles], [descriptions], [urls]]
["Igbo New Yam", ["New Yam Festival"], ["The New Yam Festival..."], ["https://en.wikipedia.org/wiki/New_Yam_Festival"]]
```

Flow:
1. Opensearch finds best matching article title (fuzzy matching)
2. Page Summary API fetches full content using found title
3. Returns real Wikipedia URL and title

**2. Backend: Send ALL terms (transparency)**
- Removed `if r.success` filter in `pipeline_executor.py`
- All lookup attempts are now sent to frontend
- Frontend knows what was searched, even if not found

**3. Frontend: Visual distinction**
- Found articles: Blue link (clickable)
- Not found: Gray italic text with "(nicht gefunden)"
- Badge shows total count as "N Begriff(e)" instead of "N Artikel"

### Modified Files
| File | Change |
|------|--------|
| `devserver/my_app/services/wikipedia_service.py` | Replaced direct lookup with Opensearch API + Page Summary |
| `devserver/schemas/engine/pipeline_executor.py` | Removed success filter, send all terms |
| `public/.../text_transformation.vue` | Badge shows found/not-found distinction |
| `public/.../text_transformation.css` | Added `.wikipedia-not-found` styling |

### Commits
- `ea9c5cf` - feat(wikipedia): Use Opensearch API for fuzzy matching + show all terms

### Result
- Badge now appears (shows all searched terms)
- Fuzzy matching finds articles even with inexact search terms
- Transparent: User sees what was searched and whether it was found
- Links point to real Wikipedia articles

---

## Session 142 - Wikipedia Badge Position Fix
**Date:** 2026-01-27
**Focus:** Fix disappearing Wikipedia badge by moving to stable UI area
**Status:** COMPLETED

### Problem
Wikipedia badge disappeared after 3 seconds during multiple Wikipedia lookups:
1. First lookup complete: `terms: [{...}]` → Badge appears ✓
2. Second lookup start: `terms: []` → Badge disappears ✗ (SSE event overwrote terms array)
3. Second lookup complete: `terms: [{...}]` → Badge reappears

**Root Cause:**
- Badge positioned in interception section (unstable during SSE streaming)
- `handleWikipediaLookup()` replaced terms array on "start" event: `wikipediaData.value = { active: true, terms: [] }`

### Solution
**Moved badge to stable area** next to Start #1 button:
- No movement during streaming
- Not affected by SSE events
- Visible immediately after first Wikipedia lookup
- Persists during all subsequent lookups

**Fixed data handling:**
- `handleWikipediaLookup()`: Accumulates terms instead of replacing
- `runInterception()`: Full reset only at start of new run

### Modified Files
| File | Change |
|------|--------|
| `public/ai4artsed-frontend/src/views/text_transformation.vue` | Removed badge from interception section (line 83-112); Added badge to Start #1 button container; Fixed handleWikipediaLookup to accumulate terms; wikipediaStatusText shows live status in loading message |

### Commits
- `ab4e37c` - feat(wikipedia): Add status text and dynamic loading message
- `4294bcd` - fix(wikipedia): Move badge to stable area next to Stage 1
- `e1968c0` - fix(wikipedia): Move badge from Start #2 to Start #1

### Result
- Badge appears when first Wikipedia lookup completes
- Badge stays visible during subsequent lookups
- Terms accumulate (e.g., "3 Artikel")
- Badge resets only on new interception run
- Stable position next to Start #1 button

---

## Session 141 - Canvas SSE Streaming for Live Execution Progress
**Date:** 2026-01-27
**Focus:** Real-time progress feedback during canvas workflow execution
**Status:** COMPLETED

### Problem
Users see nothing for 5+ minutes while canvas workflow runs. Terminal shows useful progress info (`[Canvas Tracer] Executing...`) but frontend only updates after everything completes.

### Solution
SSE (Server-Sent Events) streaming endpoint that yields events IMMEDIATELY during execution.

### Key Implementation Detail
**Iterative work-queue instead of recursion** - Critical architectural change:
- Recursive `trace()` function cannot `yield` (nested function limitation)
- Replaced with explicit work-queue loop in generator
- `yield` now happens DIRECTLY in main generator between node executions

### SSE Events
| Event | Data | When |
|-------|------|------|
| `started` | `{total_nodes}` | Execution begins |
| `progress` | `{node_id, node_type, message}` | Before each node |
| `node_complete` | `{node_id, output_preview}` | After each node |
| `complete` | `{results, collectorOutput}` | All done |
| `error` | `{message}` | On failure |

### Modified Files
| File | Change |
|------|--------|
| `devserver/my_app/routes/canvas_routes.py` | New `/api/canvas/execute-stream` endpoint with iterative work-queue |
| `public/ai4artsed-frontend/src/stores/canvas.ts` | `executeWorkflow()` now uses streaming fetch + ReadableStream; added `currentProgress`, `totalNodes`, `completedNodes` refs |
| `public/ai4artsed-frontend/src/views/canvas_workflow.vue` | Progress overlay with spinner, current step message, and node counter |

### Commit
`319313d` - feat(canvas): SSE streaming for live execution progress

---

## Session 140c - Anti-Orientalism Meta-Prompt Enhancement
**Date:** 2026-01-26
**Focus:** Prevent orientalist stereotypes in prompt interception
**Status:** COMPLETED

### Problem
User report: GPT-OSS:120b produced "enormer, furchtbarer exotistischer orientalistischer Kitsch" when processing Nigerian cultural festival prompt. LLM defaulted to orientalist tropes (exotic, mysterious, timeless) despite pedagogical goals.

### Root Cause
Meta-prompt in `instruction_selector.py` lacked explicit anti-stereotype rules. Wikipedia lookup alone insufficient - models need explicit cultural respect principles.

### Solution
Enhanced "transformation" instruction with anti-orientalism rules:
- FORBIDDEN: Exoticizing, romanticizing, mystifying cultural practices
- FORBIDDEN: Orientalist tropes (exotic, mysterious, timeless, ancient wisdom)
- FORBIDDEN: Homogenizing diverse cultures into aesthetic stereotypes
- Equality principle: "Use the same neutral, fact-based approach as for Western contexts"

### Modified Files
| File | Change |
|------|--------|
| `devserver/schemas/engine/instruction_selector.py` | Enhanced "transformation" instruction with CULTURAL RESPECT PRINCIPLES |
| `devserver/schemas/chunks/manipulate.json` | Wikipedia instruction now uses cultural reference language (70+ languages) |
| `devserver/schemas/engine/pipeline_executor.py` | Send REAL Wikipedia results (title, url) to frontend, not just search terms |
| `devserver/my_app/services/wikipedia_service.py` | Expanded SUPPORTED_LANGUAGES from 20 to 70+ (Africa, Asia, Americas, Oceania) |
| `public/ai4artsed-frontend/src/views/text_transformation.vue` | Wikipedia badge uses LoRA design pattern + real URLs; reset on Start button |
| `public/ai4artsed-frontend/src/views/text_transformation.css` | Wikipedia badge reuses lora-stamp classes with color modifier |
| `public/ai4artsed-frontend/src/components/MediaInputBox.vue` | TypeScript types updated for real Wikipedia results |
| `docs/analysis/ORIENTALISM_PROBLEM_2026-01.md` | Complete analysis with test strategy and postcolonial theory references |
| `docs/DEVELOPMENT_DECISIONS.md` | Documented epistemic justice as core architectural principle |

### Key Decisions
1. **Universal application**: Rules apply to ALL configs, not just cultural-specific ones
2. **Explicit FORBIDDEN list**: Concrete examples of prohibited terms
3. **Option A chosen**: Comprehensive instruction (~150 words) for maximum effectiveness
4. **Cultural reference language**: Wikipedia lookup uses cultural context language (not prompt language)
   - **70+ languages** mapped: Africa (15+), Asia (30+), Americas (indigenous languages), Oceania
   - Example: German prompt about Nigeria → uses Hausa/Yoruba/Igbo/English Wikipedia (not German)
   - Example: German prompt about India → uses Hindi/Tamil/Bengali/etc. Wikipedia (not German)
   - Example: German prompt about Peru → uses Spanish/Quechua/Aymara Wikipedia (not German)
   - Rationale: Local Wikipedia communities provide more accurate, less Eurocentric information
5. **No code changes**: Only meta-prompt modifications needed

### Architecture Alignment
- ✅ Supports WAS/WIE principle (anti-stereotype rules are part of "HOW")
- ✅ Reinforces planetarizer/one_world anti-Othering rules
- ✅ Enhances pedagogical goal: visible, criticalizable transformations
- ✅ No conflicts with existing configs

### Testing Status
✅ **PASSED** - Tested with original failing case via `/api/schema/pipeline/stage2`:
- Input: "Das wichtigste Fest im Norden Nigerias" (schema: tellastory)
- Model: GPT-OSS:120b (same as original failing case)
- Result: Factual story about Sallah festival in Kano with:
  - ✅ NO orientalist tropes (exotic, mysterious, timeless)
  - ✅ Specific cultural details (Durbar, Boubou, Kora/Djembe instruments)
  - ✅ Active protagonist (Amina) with agency
  - ✅ Respectful, fact-based tone
- Improvement: From "furchtbarer exotistischer Kitsch" to significantly less orientalist output (though not perfect)

### Theoretical Foundation
Based on postcolonial theory (Said, Fanon, Spivak) - see analysis document for details.

### Additional Fixes (Same Session)

**Wikipedia Badge UI Issues:**
1. **External SVG file caused build errors**
   - Solution: Inline SVG "W" icon (no external file dependency)
2. **Inconsistent design** ("größerer Kasten")
   - Solution: Reuse ALL lora-stamp classes (lora-inner, lora-details, lora-item)
   - Only color modifier: `.wikipedia-lora` for Wikipedia blue (#0066CC)
3. **Badge persisted after Start button**
   - Solution: Reset wikipediaData on runInterception()

**Wikipedia URL Issues:**
1. **Invented links instead of real URLs**
   - Root cause: Backend fetched WikipediaResult but only sent search terms to frontend
   - Solution: Send REAL Wikipedia results (term, lang, title, url, success)
   - Frontend now uses real URLs and displays real article titles
2. **Only 20 languages supported**
   - Root cause: SUPPORTED_LANGUAGES had only 20 codes
   - Solution: Expanded to 70+ languages (ha, yo, ig, qu, ay, mi, etc.)
3. **No debug visibility**
   - Solution: Console logging shows which articles were found with their URLs

**Result:**
- Wikipedia badge matches LoRA badge design exactly
- Links point to REAL Wikipedia articles (no more 404s)
- All 70+ languages now work correctly
- Debug output in console: "Found X Wikipedia articles: lang: title -> url"

### Commits
- `f73bd46` feat(interception): Add anti-orientalism rules and cultural-aware Wikipedia lookup
- `a24fbc0` fix(wikipedia): Use SVG logo and reset data on Start button
- `754b535` docs: Add epistemic justice decision to DEVELOPMENT_DECISIONS.md
- `e929d57` fix(wikipedia): Copy LoRA badge design exactly (inline SVG, shared CSS)
- `4e69051` fix(wikipedia): Use correct language-specific Wikipedia links
- `de32065` fix(wikipedia): Use REAL Wikipedia URLs instead of invented links + 70+ languages

---

## Session 140b - Canvas Cosmetic Fixes & Live Data Flow
**Date:** 2026-01-26
**Focus:** UI polish for Canvas workflow builder + live execution visualization
**Status:** COMPLETED

### Part 1: Initial Fixes

**1. Connection Lines (Initial Attempt - DOM-based)**
- Problem: Lines started from wrong positions (calculated widths didn't match CSS)
- Initial solution: Query DOM positions using `data-node-id` and `data-connector` attributes
- Issue: Vue computed properties don't track DOM changes reactively

**2. Preview/Display Node**
- Made resizable (like Collector)
- Removed 150-char text truncation

**3. Collector Node**
- Removed 200-char text truncation
- Full text display with scrolling

**4. Media Type Icons**
- Google Material icons for Generation node config selection
- Icons based on `mediaType`: image, video, audio/music, text

### Part 2: Connection Line Refactor (Data-Based)

**Problem:** DOM-based approach had timing issues - computed properties run before DOM updates.

**Solution:** Pure data-based connector positioning:
```typescript
const HEADER_CONNECTOR_Y = 24  // Fixed offset from top

function getConnectorPosition(node, connectorType) {
  const width = getNodeWidth(node)  // 280px wide, 180px narrow
  if (connectorType === 'input') {
    return { x: node.x, y: node.y + HEADER_CONNECTOR_Y }
  }
  return { x: node.x + width, y: node.y + HEADER_CONNECTOR_Y }
}
```

**Key insight:** Connectors in HEADER area (fixed Y=24px) don't move when nodes resize.

### Part 3: Evaluation Metadata in Collector

**Problem:** Evaluation score/binary not showing in Collector.

**Solution:** Backend now wraps evaluation output with metadata:
```python
if source_node_type == 'evaluation' and source_metadata:
    collector_item['output'] = {
        'text': input_data,
        'metadata': source_metadata  # { score, binary, active_path }
    }
```

Frontend displays: `Score: 7/10 ✓ Pass`

### Part 4: Output Bubbles (Live Data Flow)

**Feature:** Every node shows a temporary bubble when it produces output.

- Blue speech bubble appears near output connector
- Shows truncated content (60 chars text, icons for media, score for evaluation)
- Animated appearance with scale/fade effect
- Excluded from terminal nodes (collector, display)

### Files Changed

| File | Change |
|------|--------|
| `CanvasWorkspace.vue` | Pure data-based connector positions, node width by type |
| `StageModule.vue` | Header connector CSS (top: 24px), output bubbles, evaluation display |
| `ConfigSelectorModal.vue` | Media type icons |
| `canvas_workflow.vue` | Pass outputConfigs prop |
| `canvas_routes.py` | Evaluation metadata in collector items |

### Commits

- `a4219c2` - feat(canvas): Session 135 - Cosmetic fixes and media type icons
- `b9b692a` - fix(canvas): Data-based connector positioning with header alignment
- `f770405` - fix(canvas): Evaluation metadata handling and display improvements
- `3c58672` - feat(canvas): Output bubbles show data flowing through nodes

---

## Session 140a - Canvas Decision & Evaluation Nodes (Unified Architecture)
**Date:** 2026-01-25 → 2026-01-26
**Focus:** Implement evaluation nodes with 3-output branching logic + Tracer-Pattern execution
**Status:** COMPLETED (Phase 1-4) - Reflexiv agierendes Frontend für genAI

### Pädagogisches Konzept: Evaluation als bewusste Entscheidung

**Kernidee:** Evaluation = EINE konzeptionelle Entscheidung mit 3 Text-Outputs, nicht 7 separate Node-Typen.

**Warum 3 Outputs?**
1. **Passthrough (P)** - Evaluation bestanden → unverändert weiter
2. **Commented (C)** - Evaluation nicht bestanden → mit Feedback zurück
3. **Commentary (→)** - Immer → für User-Transparenz/Display

**Pädagogischer Vorteil:**
- Explizite Entscheidungspunkte im Workflow
- Sichtbares Feedback (nicht "black box")
- Ermöglicht iterative Verbesserung (Feedback Loops)

### Architekturentscheidung: Von 7 Nodes → 1 Node

**Ursprünglicher Plan (verworfen):**
- 5 Evaluation-Types (fairness, creativity, equity, quality, custom)
- 2 Fork-Types (binary_fork, threshold_fork)
= 7 separate Node-Typen

**Problem (User Feedback):**
- Evaluation + Fork = konzeptuell EINE Entscheidung, nicht zwei
- Datenfluss unklar: Was fließt durch Fork? Input? Commentary? Beides?
- UI-Komplexität: 7 Nodes für eine logische Operation

**Lösung: Unified Evaluation Node**
- 1 Node-Typ mit Dropdown für Evaluation-Type
- Optional branching (Checkbox)
- 3 separate TEXT-Outputs (nicht kombiniertes Objekt)

### Implementation - Phase 1: Evaluation Nodes (COMPLETED)

**Frontend (canvas.ts):**
- Node-Type: `'evaluation'`
- Properties: `evaluationType`, `evaluationPrompt`, `outputType`, `enableBranching`, `branchCondition`, `thresholdValue`, `trueLabel`, `falseLabel`

**UI (StageModule.vue):**
```vue
Evaluation Type: [Fairness ▼] (fairness, creativity, equity, quality, custom)
LLM: [gpt-4o-mini ▼]
Criteria: [Textarea mit Pre-fill Templates]
Output: [Commentary+Score ▼]
☑ Enable Branching
  Condition: [Binary/Threshold]
  Threshold: [5.0] (if threshold selected)
  True Label: [Approved]
  False Label: [Needs Revision]
```

**Backend (canvas_routes.py):**
```python
# 3 separate TEXT outputs
outputs = {
  'passthrough': input_text,  # Original unchanged
  'commented': f"{input_text}\n\nFEEDBACK: {commentary}",  # Input + feedback
  'commentary': commentary  # Just commentary
}
metadata = {
  'binary': True/False,
  'score': 0-10,
  'active_path': 'passthrough' | 'commented'
}
```

**Binary Logic (Fixed):**
- LLM-Prompt: "Answer ONLY 'true' or 'false'. If issues or score < 5, answer 'false'"
- Fallback: No binary → use score threshold (< 5.0 = fail)
- Smart parsing: Case-insensitive, multiple variations (true/yes/pass/bestanden)

### Implementation - Phase 2: Display → Preview Node (COMPLETED)

**Problem:** Display-Node zeigte nichts an, hatte nutzloses Dropdown.

**Lösung:** Umbenennung + Inline-Preview
- Label: "Display" → "Preview/Vorschau"
- Removed: title input, displayMode dropdown
- Added: Inline content visualization
  - Text: First 150 chars
  - Images: Inline preview (max 150px)
  - Media: Type + URL display

**UI:**
```
┌──────────────┐
│ 🔍 PREVIEW   │
├──────────────┤
│ [Content...] │ ← Shows execution result
│ [truncated]  │
└──────────────┘
```

### Implementation - Phase 3a: UI for Branching (COMPLETED)

**3 Output Connectors:**
```
┌────────────────┐
│ 📋 EVALUATION  │
└────────────────┘
       ├─ P (🟢 green - Passthrough)
       ├─ C (🟠 orange - Commented)
       └─ → (🔵 cyan - Commentary)
```

**Connection Labels:** `'passthrough'`, `'commented'`, `'commentary'`

**Collector Display:**
- Shows: Binary (✅/❌), Score, Active Path, Commentary, Output Text
- Separate sections for metadata vs. outputs

### Connection Rules (Fixed Multiple Times)

**Problem:** Nodes couldn't connect (e.g., Input → Evaluation).

**Solution:** Extended `acceptsFrom` and `outputsTo` for all nodes:
- Input → can output to: interception, translation, evaluation, display
- Evaluation → accepts from: input, interception, translation, generation, display, evaluation
- All nodes → can connect to evaluation/display

### Technical Debt & Next Steps

**Phase 3b: Conditional Execution (IMPLEMENTED)**
- Connection labels track active path ('passthrough', 'commented', 'commentary', 'feedback')
- Tracer filters connections based on `active_path` metadata
- Only active path executes downstream (commentary always active)

**Phase 4: Feedback Loops (IMPLEMENTED - Tracer Pattern)**

*Ursprünglicher Plan (verworfen):*
- Loop Controller Node + Kahn's Algorithm
- "Scheinlösung" - über-engineered

*Implementierte Lösung:*
- **Tracer Pattern**: Simples rekursives Graph-Tracing
- Feedback-Input-Connector an Interception/Translation Nodes
- Feedback-Connections mit Label `'feedback'`
- Safety-Limit: MAX_TOTAL_EXECUTIONS = 50
- Kein separater Loop Controller Node nötig

*Design Decision:*
> "Wir haben hier keine unkontrollierte Schleifen-Situation im Graph, sondern nichts anderes als eine Loop-End-Konstellation."

Das System ist ein **reflexiv agierendes Frontend für genAI**:
```
Input → Interception → Evaluation → [Score < 5?]
                            ↓ feedback     ↓ pass
                       Interception    Collector
```

### Files Changed

| File | Change |
|------|--------|
| `public/.../types/canvas.ts` | Unified evaluation type, 3-output structure, connection labels, maxFeedbackIterations |
| `public/.../stores/canvas.ts` | Connection label handling, feedback completion functions |
| `public/.../StageModule.vue` | Evaluation UI, 3 connectors, Feedback-Input connector, Preview inline display |
| `public/.../CanvasWorkspace.vue` | Feedback connection handling, event forwarding |
| `public/.../canvas_workflow.vue` | Handler functions for evaluation config |
| `public/.../ModulePalette.vue` | Removed 7 nodes → 1 evaluation node |
| `devserver/.../canvas_routes.py` | **Complete rewrite**: Tracer pattern statt Kahn's Algorithm |

### Commits

1. `feat(session-134): Add Evaluation node types (Phase 1)` - Initial 5 evaluation types
2. `feat(session-134): Add Display node (Phase 2)` - Display node with config
3. `feat(session-134): Add Fork node UI (Phase 3a)` - Binary/Threshold fork UI
4. `fix(session-134): Add new node types to Palette menu` - Palette integration
5. `fix(session-134): Fix connections and enforce binary output` - Binary always enabled
6. `refactor(session-134): Unified Evaluation node (Option A)` - 7 nodes → 1 node
7. `fix(session-134): Enable all nodes to connect to evaluation/display` - Connection rules
8. `feat(session-134): 3 separate TEXT outputs for Evaluation nodes` - 3-output architecture
9. `fix(session-134): Improve binary evaluation logic` - Score threshold fallback
10. `refactor(session-134): Display → Preview with inline content display` - Preview node
11. `fix(session-134): Score-based override for binary evaluation` - Score fallback
12. `refactor(session-134): Simplify evaluation to score-only logic` - Clean score logic
13. `feat(session-134): Phase 3b - Conditional execution for evaluation nodes` - Path filtering
14. `feat(session-134): Phase 4 - Loop Controller with feedback iterations` - Tracer pattern
15. `fix(session-134): TypeScript errors in Phase 4 Loop Controller` - Type fixes

### Testing Results

✅ **Working:**
- Evaluation node with LLM selection
- Type-specific prompt templates (fairness, creativity, equity, quality, custom)
- Binary + Score + Commentary output
- 3 output connectors (P, C, →)
- Preview shows inline content
- Collector displays evaluation results with metadata
- Conditional execution (only active path executes)
- Feedback loops (Evaluation → Interception)
- Safety limit prevents infinite loops

⚠️ **Known Issues (fixed):**
- Binary logic fallback bug → Score-based override
- Conditional execution → Tracer pattern with path filtering

### Architecture Documentation

See: `docs/ARCHITECTURE_CANVAS_EVALUATION_NODES.md` (created this session)

---

## Session 139 - Wikipedia Research Capability
**Date:** 2026-01-26
**Focus:** Enable LLM to fetch Wikipedia content during prompt interception
**Status:** COMPLETED

### Feature Overview
LLM can now request Wikipedia content using `<wiki>term</wiki>` markers in its output. System fetches content and re-executes chunk with enriched context.

### Architecture
- **Chunk-Level Orchestration**: Wikipedia loop in `pipeline_executor._execute_single_step()`
- **NOT a new pipeline** - fundamental capability of ALL interceptions
- **Max 3 iterations** per chunk execution (configurable)

### New Files
| File | Purpose |
|------|---------|
| `my_app/services/wikipedia_service.py` | Secure Wikipedia API client (whitelist-only) |
| `schemas/engine/wikipedia_processor.py` | Marker extraction, content formatting |

### Modified Files
| File | Change |
|------|--------|
| `config.py` | `WIKIPEDIA_MAX_ITERATIONS`, `WIKIPEDIA_FALLBACK_LANGUAGE`, `WIKIPEDIA_CACHE_TTL` |
| `schemas/chunks/manipulate.json` | `{{WIKIPEDIA_CONTEXT}}` placeholder, instruction text |
| `schemas/engine/pipeline_executor.py` | Wikipedia loop, `WIKIPEDIA_STATUS` global for UI |
| `my_app/routes/schema_pipeline_routes.py` | Refactored to use `pipeline_executor` (fixes architecture violation), SSE `wikipedia_lookup` events |
| `MediaInputBox.vue` | Pulsing Wikipedia logo during lookup |

### Trigger Pattern
```
<wiki lang="de">Suchbegriff</wiki>  - German Wikipedia
<wiki lang="en">Search term</wiki>  - English Wikipedia
<wiki>term</wiki>                    - Uses input language
```

### Key Decisions
1. **Language auto-detection**: Uses input language, falls back to `WIKIPEDIA_FALLBACK_LANGUAGE`
2. **Session per-request**: aiohttp session created/closed per lookup (avoids event loop issues with threading)
3. **Architecture fix**: SSE route now uses `pipeline_executor` instead of direct `PromptInterceptionEngine` call

### Commits
- `d66c37f` feat(wikipedia): Core implementation
- `b617273` fix(wikipedia): Import paths
- `277dbf7` fix(wikipedia): Stronger prompt (MUST use when needed)
- `8e03431` feat(wikipedia): Real-time UI feedback
- `761cffa` fix(wikipedia): Session per-request (event loop fix)

---

## Session 138 - Trashy Context-Awareness Fix
**Date:** 2026-01-26
**Focus:** Fix Trashy losing context after pipeline execution
**Status:** COMPLETED

### Problem
Träshy (AI chat helper) was "forgetting" current page context after a pipeline run:

**Root Cause Chain:**
1. User runs pipeline → `runId` gets set via `updateSession()`
2. User changes MediaInputBox content → `runId` stays set (no `clearSession()` call)
3. User opens Träshy → ChatOverlay sees `runId` exists
4. ChatOverlay sends draft_context ONLY if `!runId` (Zeile 213)
5. Backend loads **stale** session context from `exports/json/{runId}/`
6. Träshy doesn't know about current input changes

**Confirmed:** No Vue view calls `clearSession()` → `runId` persists until browser refresh

### Solution: Always Send Draft Context

**Option B (chosen):** Send `draft_context` as separate field, backend combines both contexts.

**Frontend (`ChatOverlay.vue`):**
```javascript
// BEFORE: Conditional logic
if (!currentSession.value.runId && draftContextString.value) {
  messageForBackend = `${draftContextString.value}\n\n${userMessage}`
}

// AFTER: Always send as separate field
const response = await axios.post('/api/chat', {
  message: userMessage,  // Clean message
  run_id: currentSession.value.runId || undefined,
  draft_context: draftContextString.value || undefined,  // NEW: Always send
  history: historyForBackend
})
```

**Backend (`chat_routes.py`):**
```python
draft_context = data.get('draft_context')  # Current page state (transient)

system_prompt = build_system_prompt(context)  # Session context from files

# Append draft_context if provided (NOT saved to exports/)
if draft_context:
    system_prompt += f"\n\n[Aktuelle Eingaben auf der Seite]\n{draft_context}"
```

### Key Points

- `draft_context` is **transient** (LLM context only, not persisted)
- NOT saved to `chat_history.json` or `exports/json/`
- Backend now knows BOTH: session files + current page state
- No changes to exports system

### Result

**Before:**
- Without runId: draft_context sent ✓
- With runId: draft_context ignored ✗

**After:**
- Without runId: draft_context in system prompt ✓
- With runId: BOTH session + draft_context in system prompt ✓

**Commit:** `1fee080` - fix(trashy): Always send draft_context for context-aware chat

---

## Session 137 - Stage 3/4 Separation (Clean Architecture)
**Date:** 2026-01-26
**Focus:** Separate Stage 3 (Translation+Safety) from Stage 4 (Generation) for clean architecture
**Status:** COMPLETED

### Problem
`execute_generation_stage4()` contained **embedded Stage 3 logic**, forcing Canvas to use `skip_translation=True` workaround when it had its own Translation node.

**Old Architecture (problematic):**
```
Canvas: Translation Node → Generation Node (skip_translation=True) → Media
Lab:    execute_generation_stage4() → [Stage 3 embedded] → Stage 4 → Media
```

**Bug Found:** Parameter was `skip_stage3` but code used undefined `skip_translation` variable.

### Solution
Created clean separation with new function `execute_stage4_generation_only()`:

**New Architecture:**
```
Canvas: Translation Node → execute_stage4_generation_only() → Media
Lab:    execute_generation_stage4() → Stage 3 → execute_stage4_generation_only() → Media
```

### Changes

| File | Change |
|------|--------|
| `schema_pipeline_routes.py` | Added `execute_stage4_generation_only()` - pure Stage 4 generation |
| `schema_pipeline_routes.py` | Refactored `execute_generation_stage4()` to call new function internally |
| `canvas_routes.py` | Generation node now calls `execute_stage4_generation_only()` directly |
| `canvas_routes.py` | Removed `skip_translation=True` workaround |

### Key Principle
- `execute_stage4_generation_only()` = Pure generation, expects ready-to-use prompt
- `execute_generation_stage4()` = Legacy wrapper for Lab (handles Stage 3 first)
- Canvas workflows call the clean function directly - no flags needed

**Commit:** `9f34ca2` - refactor(stage4): Separate Stage 3 and Stage 4 for clean architecture

---

## Session 136 - Träshy UX Enhancement: Living Assistant Interface
**Date:** 2026-01-25
**Focus:** Transform Träshy from static icon to living, context-aware assistant
**Status:** COMPLETED

### Pädagogisches Konzept

Träshy ist nicht nur ein Chat-Button, sondern ein **aktiver Begleiter** im kreativen Prozess:
- **Präsenz**: Immer sichtbar, aber nicht störend
- **Aufmerksamkeit**: Folgt dem Fokus des Users (welches Feld aktiv ist)
- **Lebendigkeit**: Sanfte Animationen signalisieren "Ich bin da und bereit zu helfen"
- **Kontext-Bewusstsein**: Weiß was der User gerade tut (Page Context + Focus Tracking)

### Features implementiert

#### 1. Dynamische Positionierung (Y-Achse)
- Träshy folgt dem fokussierten Eingabefeld
- Position berechnet aus `element.getBoundingClientRect()`
- Viewport-Clamping: Bleibt immer sichtbar (nie über oberen/unteren Rand)

#### 2. Focus-Tracking
- `@focus` Events in MediaInputBox
- `focusedField` State: 'input' | 'context' | 'interception' | 'optimization'
- Sofortige Reaktion auf Feldwechsel

#### 3. Pinia Store statt provide/inject
- Problem: ChatOverlay ist Sibling von router-view, nicht Child
- Lösung: `pageContextStore` für komponentenübergreifende Kommunikation
- Views schreiben via `watch()`, ChatOverlay liest

#### 4. Lebendige Animationen
- **Idle-Schweben**: `trashy-idle` (4s) - translate + rotate
- **Atmen**: `trashy-breathe` (3s) - subtle scale pulse
- **Bewegung**: cubic-bezier mit Überschwingen für organisches Gefühl
- Hover pausiert Animation (präzises Klicken)

#### 5. Chat-Fenster Verbesserungen
- Öffnet nach links/unten statt nach oben
- Viewport-Clamping beim Öffnen
- Auto-Focus auf Input nach Antwort

### Technische Änderungen

| Datei | Änderung |
|-------|----------|
| `src/stores/pageContext.ts` | **NEU** - Pinia Store für Page Context |
| `src/composables/usePageContext.ts` | FocusHint Interface hinzugefügt |
| `src/components/ChatOverlay.vue` | Dynamische Positionierung + Animationen |
| `src/components/MediaInputBox.vue` | @focus Event hinzugefügt |
| `src/views/text_transformation.vue` | Focus-Tracking + Element-Refs |
| `src/assets/base.css` | CSS Custom Properties für Layout |

### CSS Custom Properties (base.css)
```css
--footer-collapsed-height: 36px;
--funding-logo-width: 126px;
--layout-gap-small: 8px;
```

### Commits
- `8bb0f96` fix(ui): Remove lightbulb context indicator
- `7f34bfd` feat(ui): Floating Träshy - smooth position transitions
- `a1169c0` fix(ui): Use Pinia store instead of provide/inject
- `1a11637` feat(ui): Dynamic positioning based on element positions
- `54be78d` feat(ui): Träshy follows focused field
- `ed67488` feat(ui): Träshy follows optimization section
- `78c9725` fix(ui): Top positioning when expanded
- `000d8f0` fix(ui): Clamp position to stay within viewport
- `1de7d4e` refactor(css): CSS custom properties for layout
- `bc65f2c` feat(ui): Idle animation - living assistant

---

## Session 135 - Prompt Optimization META-Instruction Fix
**Date:** 2026-01-24
**Focus:** Fix prompt_optimization breaking on certain models
**Status:** COMPLETED

### Problem
The `prompt_optimization` chunk was failing with certain LLM models because the META-instruction was too complex and model-specific variations weren't working consistently.

### Solution
Simplified the META-instruction in `prompt_optimization` to be more universal and less dependent on model-specific quirks.

### Files Changed
- `devserver/my_app/config/chunks/prompt_optimization.json` - Simplified META-instruction

### Commits
- `1261c4a` fix(session-135): Simplify prompt_optimization META-instruction

---

## Session 134 - GPU Auto-Detection & Analog Photography Fixes
**Date:** 2026-01-24
**Focus:** Settings UI improvements, config fixes, instruction injection architecture
**Status:** COMPLETED

### Features
1. **GPU Auto-Detection in Settings UI** - Automatically detects available GPUs
2. **Analog Photography Config Fixes** - Fixed typos in interception configs
3. **Model Evaluation Criteria** - Documented proper evaluation methodology
4. **Instruction Injection Architecture** - Refactored HARDWARE_MATRIX handling

### Files Changed
- `public/ai4artsed-frontend/src/views/SettingsView.vue` - GPU auto-detection
- `devserver/my_app/config/interception_configs/*.json` - Typo fixes
- `docs/HANDOVER_ModelEvaluation_Criteria.md` - Evaluation methodology

### Commits
- `cea6685` feat(session-134): Add GPU auto-detection to Settings UI
- `12a59bf` fix(session-134): Analog photography config typos + evaluation criteria
- `e50bcc7` fix(session-134): Instruction injection architecture + HARDWARE_MATRIX

---

## Session 133 - Träshy Page Context & Canvas Node Improvements
**Date:** 2026-01-24
**Focus:** Chat assistant context awareness, Canvas workflow enhancements
**Status:** COMPLETED

### Major Features

#### 1. Träshy Page Context (provide/inject Pattern)
Träshy (chat assistant) now knows the current page state even before pipeline execution:
- **Composable**: `usePageContext.ts` with `PageContext` interface and `formatPageContextForLLM()` helper
- **Injection Key**: `PAGE_CONTEXT_KEY` for type-safe provide/inject
- **8 Views Updated**: All major views now provide their page context

**Implementation Pattern:**
```typescript
// In views (e.g., text_transformation.vue)
const pageContext = computed(() => ({
  activeViewType: 'text_transformation',
  pageContent: {
    inputText: inputText.value,
    contextPrompt: contextPrompt.value,
    selectedCategory: selectedCategory.value,
    selectedConfig: selectedConfig.value
  }
}))
provide(PAGE_CONTEXT_KEY, pageContext)

// In ChatOverlay.vue
const pageContext = inject(PAGE_CONTEXT_KEY, null)
const draftContextString = computed(() => formatPageContextForLLM(pageContext?.value, route.path))
```

**Priority Logic:**
1. Session context (run_id files) - highest priority
2. Draft page context (from provide/inject) - if no session
3. Route-only fallback - minimal context

#### 2. Canvas Workflow Improvements
- **Collector Node** - Now accepts text from LLM nodes
- **Input Node** - Now accepts prompt text input
- **LLM Endpoint** - Curated model selection for canvas nodes

#### 3. Additional Fixes
- **Ollama Models Dropdown** - `/api/settings/ollama-models` endpoint + `<datalist>` in SettingsView
- **Model Name Trimming** - `.strip()` in chat_routes.py prevents whitespace issues
- **Log String Cleanup** - "STAGE1-GPT-OSS" → "STAGE1-SAFETY", "gpt-oss:" → "llm:"

### Files Changed
- 📝 `src/composables/usePageContext.ts` - **NEW** - Type definitions & formatting
- 📝 `src/components/ChatOverlay.vue` - inject() + context-prepending
- 📝 `src/views/text_transformation.vue` - provide(PAGE_CONTEXT_KEY)
- 📝 `src/views/image_transformation.vue` - provide(PAGE_CONTEXT_KEY)
- 📝 `src/views/canvas_workflow.vue` - provide(PAGE_CONTEXT_KEY)
- 📝 `src/views/direct.vue` - provide(PAGE_CONTEXT_KEY)
- 📝 `src/views/surrealizer.vue` - provide(PAGE_CONTEXT_KEY)
- 📝 `src/views/multi_image_transformation.vue` - provide(PAGE_CONTEXT_KEY)
- 📝 `src/views/partial_elimination.vue` - provide(PAGE_CONTEXT_KEY)
- 📝 `src/views/split_and_combine.vue` - provide(PAGE_CONTEXT_KEY)
- 📝 `devserver/my_app/routes/settings_routes.py` - Ollama models endpoint
- 📝 `devserver/my_app/routes/chat_routes.py` - Model name trimming

### Commits
- `833428b` forgotten commits (includes all page context changes)
- `5221b36` feat(session-133): Collector accepts text from LLM nodes
- `26e1f4a` feat(session-133): Input node accepts prompt text
- `9bda8e5` fix(session-133): LLM endpoint with curated model selection

---

## Session 130 - Research Data Architecture: 1 Run = 1 Media Output
**Date:** 2026-01-23
**Duration:** ~3 hours
**Focus:** Clean folder structure for research data, immediate prompt persistence
**Status:** PARTIAL - Core features working, sticky UI TODO

### Goals
1. Implement "1 Run = 1 Media Output" principle
2. Save prompts immediately after LLM generation (not only on user action)
3. Stop logging changes after media generation (run is complete)

### Key Principle: 1 Run = 1 Media Output
Each run folder should contain exactly ONE media product. This prevents:
- Favorites system confusion (multiple images in same folder)
- Research data mixing (different generation contexts in same folder)

**Folder Logic:**
```
Interception (Start1)     → run_001/ created
Generate (FIRST)          → run_001/ continues (no output yet)
Generate (SECOND)         → run_002/ NEW (run_001 has output_*)
Generate (THIRD)          → run_003/ NEW
```

### Implementation

**1. Generation Endpoint - Output Check (`schema_pipeline_routes.py:2038-2066`)**
```python
has_output = any(
    e.get('type', '').startswith('output_')
    for e in existing_recorder.metadata.get('entities', [])
)
if has_output:
    run_id = new_run_id()  # NEW folder
else:
    run_id = provided_run_id  # CONTINUE existing
```

**2. Immediate Prompt Persistence (`schema_pipeline_routes.py:1584-1660`)**
- Optimization streaming now loads recorder at START (same pattern as interception)
- Saves `optimized_prompt` immediately after LLM generation
- Frontend passes `run_id` and `device_id` to optimization endpoint

**3. Stop Logging After Generation (TODO - not working yet)**
- Added `currentRunHasOutput` flag in frontend
- Set to `true` after successful generation
- `logPromptChange()` should skip if flag is true
- Reset on new interception

### Files Changed
- 📝 `devserver/my_app/routes/schema_pipeline_routes.py`
  - Generation endpoint: has_output check for new folder
  - Optimization streaming: recorder at start, immediate save
  - Optimize endpoint: run_id/device_id parameters
- 📝 `public/ai4artsed-frontend/src/views/text_transformation.vue`
  - `optimizationStreamingParams`: added run_id, device_id
  - `currentRunHasOutput` flag (TODO: not working)
  - `logPromptChange()`: skip if run has output

### TODO
- [ ] Fix `currentRunHasOutput` flag not preventing logging after generation
- [ ] Implement "sticky" UI: restore prompts/image when switching modes

### Commits
- `bed0c2c` feat(session-130): 1 Run = 1 Media Output
- `8d07c33` feat(session-130): Save optimized_prompt immediately after LLM generation

---

## Session 117 - LoRA Strength Tuning for Interception Configs
**Date:** 2026-01-17
**Duration:** ~30 minutes
**Focus:** Finding optimal LoRA strength for prompt/style balance
**Status:** SUCCESS - Strength calibrated

### Problem
LoRA injection was working (since Session 114/116), but at strength 1.0 the LoRA effect completely overrode the user's prompt content. Generated images showed only the LoRA style (e.g., film artifacts for Cooked Negatives) with no relevance to the actual prompt.

### Investigation
Compared generations with "Cooked Negatives" interception config:
- **Strength 1.0:** Full film artifact effect, but prompt completely ignored
- **Strength 0.5:** Effect barely visible
- **Strength 0.6:** Good balance - film artifacts visible AND prompt content preserved

### Solution
Adjusted LoRA strength in interception config:
```json
{
  "meta": {
    "loras": [
      {"name": "sd3.5-large_cooked_negatives.safetensors", "strength": 0.6}
    ]
  }
}
```

### Key Insight
**LoRA Strength Trade-off:**
- High strength (0.8-1.0): Style dominates, prompt ignored
- Low strength (0.3-0.5): Style barely visible
- Sweet spot (0.5-0.7): Balance between style and prompt adherence

This varies per LoRA - some are stronger than others. Each interception config should test and calibrate its LoRA strength individually.

### Files Changed
- 📝 `devserver/schemas/configs/interception/cooked_negatives.json` (strength: 1.0 → 0.6)

---

## Session 114 - LoRA Injection for Stage 4 Workflows
**Date:** 2026-01-11
**Duration:** ~2 hours
**Focus:** Dynamic LoRA injection into ComfyUI workflows
**Status:** SUCCESS - LoRA injection working

### Goal
Enable LoRA models (e.g., face LoRAs, style LoRAs) to be automatically injected into Stage 4 image generation workflows.

### Background
Previous Cline session attempted "Dual-Parse" architecture (parsing `<lora:name:strength>` tags from prompts) but failed due to architectural issues. This session took a simpler approach: implement the injection mechanism first, decide WHERE the LoRA list comes from later.

### Solution: Workflow-Based LoRA Injection

**Key Insight:** Separate the injection mechanism from the data source.
1. Define LoRA list in `config.py` (temporary hardcoded)
2. Inject LoRALoader nodes into workflow at runtime
3. Later: connect to Stage2-Configs (Meta-Prompt + optimal LoRAs)

### Implementation

#### 1. Config (`config.py`)
```python
LORA_TRIGGERS = [
    {"name": "SD3.5-Large-Anime-LoRA.safetensors", "strength": 1.0},
    {"name": "bejo_face.safetensors", "strength": 1.0},
]
```

#### 2. Injection Logic (`backend_router.py`)
New method `_inject_lora_nodes()`:
- Finds CheckpointLoaderSimple node (model source)
- Finds model consumers (KSampler)
- Inserts LoRALoader nodes in chain: Checkpoint → LoRA1 → LoRA2 → KSampler
- Updates node connections automatically

#### 3. Routing Change
When `LORA_TRIGGERS` is configured, images use workflow mode instead of simple SwarmUI API:
```python
if LORA_TRIGGERS:
    return await self._process_workflow_chunk(...)
else:
    return await self._process_image_chunk_simple(...)
```

### Log Output (Success)
```
[LORA] Using workflow mode for image generation (LoRAs configured)
[LORA] Injected LoraLoader node 12: SD3.5-Large-Anime-LoRA.safetensors
[LORA] Injected LoraLoader node 13: bejo_face.safetensors
[LORA] Updated node 8 to receive model from LoRA chain
```

### Test Results
- ✅ Face LoRA (bejo_face) visible in output - works WITHOUT trigger word
- ✅ Multiple LoRAs chain correctly
- ✅ Workflow submission successful
- ⚠️ Style LoRA may need trigger word in prompt for visible effect

### Next Steps
**Connect to Stage2-Configs:** Each interception config (Meta-Prompt) can define optimal LoRAs:
```json
{
  "name": "jugendsprache",
  "context_prompt": "...",
  "loras": [
    {"name": "anime_style.safetensors", "strength": 0.8}
  ]
}
```

### Files Changed
- 📝 `devserver/config.py` (+10 lines - LORA_TRIGGERS config)
- 🔧 `devserver/schemas/engine/backend_router.py` (+80 lines - injection logic)

---

## Session 113 - SwarmUI Auto-Recovery System
**Date:** 2026-01-11
**Duration:** ~2 hours
**Focus:** Automatic SwarmUI lifecycle management
**Status:** SUCCESS - Full auto-recovery implemented

### Problem
DevServer crashed when SwarmUI was not running:
```
ClientConnectorError: Cannot connect to host 127.0.0.1:7821
```
**User Requirement:** DevServer should automatically detect and start SwarmUI when needed.

### Solution: SwarmUI Manager Service
Created new singleton service `swarmui_manager.py` for lifecycle management:

**Architecture Pattern:** Lazy Recovery (On-Demand)
- SwarmUI starts **only when needed** (not at DevServer startup)
- Handles both startup scenarios AND runtime crashes
- Faster DevServer startup
- Race-condition safe with `asyncio.Lock`

### Implementation

#### 1. SwarmUI Manager Service (`devserver/my_app/services/swarmui_manager.py`)
**Core Methods:**
- `ensure_swarmui_available()` - Main entry point, guarantees SwarmUI is running
- `is_healthy()` - Checks both ports (7801 REST API + 7821 ComfyUI backend)
- `_start_swarmui()` - Executes `2_start_swarmui.sh` via subprocess.Popen
- `_wait_for_ready()` - Polls health endpoints until ready or timeout (120s)

**Concurrency Safety:**
- `asyncio.Lock` prevents multiple threads from starting SwarmUI simultaneously
- Double-check pattern after acquiring lock

#### 2. Integration Points (5 locations)
**LegacyWorkflowService** (`legacy_workflow_service.py:95`):
- `ensure_swarmui_available()` before workflow submission

**BackendRouter** (`backend_router.py`):
- Line 150: Manager initialization in constructor
- Line 550: Before SwarmUI Text2Image generation
- Line 684: Before SwarmUI workflow submission
- Line 893: Before single image upload
- Line 941: Before multi-image upload

#### 3. Configuration (`config.py`)
```python
SWARMUI_AUTO_START = os.environ.get("SWARMUI_AUTO_START", "true").lower() == "true"
SWARMUI_STARTUP_TIMEOUT = int(os.environ.get("SWARMUI_STARTUP_TIMEOUT", "120"))  # seconds
SWARMUI_HEALTH_CHECK_INTERVAL = float(os.environ.get("SWARMUI_HEALTH_CHECK_INTERVAL", "2.0"))  # seconds
```

#### 4. Browser Tab Prevention
**Problem:** SwarmUI opened browser tab on startup, hiding the frontend.

**Solution:** Command-line override in `2_start_swarmui.sh`:
```bash
./launch-linux.sh --launch_mode none
```

**Why This Works:**
- SwarmUI supports `--launch_mode` command-line argument
- Overrides `LaunchMode: web` setting in `Settings.fds`
- Works on ANY SwarmUI installation (no settings file modification needed)

### Expected Behavior
**Before:**
```
[ERROR] Cannot connect to host 127.0.0.1:7821
[ERROR] Workflow execution failed
```

**After:**
```
[SWARMUI-TEXT2IMAGE] Ensuring SwarmUI is available...
[SWARMUI-MANAGER] SwarmUI not available, starting...
[SWARMUI-MANAGER] Starting SwarmUI via: /path/to/2_start_swarmui.sh
[SWARMUI-MANAGER] SwarmUI process started (PID: 12345)
[SWARMUI-MANAGER] Waiting for SwarmUI (timeout: 120s)...
[SWARMUI-MANAGER] ✓ SwarmUI ready! (took 45.2s)
[SWARMUI] ✓ Generated 1 image(s)
```

### Benefits
- ✅ DevServer starts independently of SwarmUI
- ✅ Automatic crash recovery at runtime
- ✅ No manual intervention needed
- ✅ Frontend stays in focus (no SwarmUI UI popup)
- ✅ Works with any SwarmUI installation
- ✅ Configurable via environment variables

### Files Changed
- ✨ `devserver/my_app/services/swarmui_manager.py` (NEW - 247 lines)
- 📝 `devserver/config.py` (+7 lines - Auto-recovery configuration)
- 🔧 `devserver/my_app/services/legacy_workflow_service.py` (+9 lines - Manager integration)
- 🔧 `devserver/schemas/engine/backend_router.py` (+41 lines - Manager integration)
- 🚀 `2_start_swarmui.sh` (+3 lines - `--launch_mode none`)

**Commit:** `bbe04d8` - feat(swarmui): Add auto-recovery with SwarmUI Manager service

### Architecture Updates
- Updated ARCHITECTURE PART 07 - Engine-Modules.md (SwarmUI Manager)
- Updated ARCHITECTURE PART 08 - Backend-Routing.md (Auto-recovery integration)

---

## Session 112 - CRITICAL: Fix Streaming Connection Leak (CLOSE_WAIT) & Queue Implementation
**Date:** 2026-01-08
**Duration:** ~2 hours
**Focus:** Fix connection leak and concurrent request overload (Ollama)
**Status:** SUCCESS - Connection cleanup implemented, Queue implemented

### Problem 1: Connection Leak (CLOSE_WAIT)
Production system (lab.ai4artsed.org) experiencing streaming failures:
- Cloudflared tunnel logs: "stream X canceled by remote with error code 0"
- Backend accumulating connections in CLOSE_WAIT state
- Eventually all streaming requests failing

### Fix 1: Streaming Cleanup
Implemented `GeneratorExit` handling and explicit `response.close()` in streaming generators:
1. `/devserver/schemas/engine/prompt_interception_engine.py:381`
2. `/devserver/my_app/services/ollama_service.py:366`
3. `/devserver/my_app/routes/schema_pipeline_routes.py:1278`

Result: CLOSE_WAIT connections now clear properly (tested with load test).

### Problem 2: Ollama Overload (Timeouts)
Under load (e.g. 10 parallel requests), Ollama (120b model) gets overloaded.
- Requests time out after 90s (default `OLLAMA_TIMEOUT`)
- Model execution takes 100-260s
- Parallel requests cause congestion and failures

### Fix 2: Request Queueing & Timeouts
1. **Request Queue:**
   - Implemented `threading.Semaphore(3)` in `schema_pipeline_routes.py`.
   - Limits concurrent heavy model executions to 3 (others wait).
   - Applied to Stage 1 safety checks in `execute_pipeline_streaming`, `execute_pipeline` (POST), and `execute_stage2`.

2. **Timeout Increase:**
   - Increased `OLLAMA_TIMEOUT` in `config.py` from 90s to 300s.

3. **Bug Fix:**
   - Fixed `SyntaxError` in `streaming_response.py` (f-string syntax) that prevented backend startup.

### Test Results
**Load Test (10 concurrent requests):**
- Backend: Running on port 17802 (Dev script)
- Queue Logic: Verified in logs
  ```
  [OLLAMA-QUEUE] Initialized with max concurrent requests: 3
  [OLLAMA-QUEUE] Stream ...: Waiting for queue slot...
  [OLLAMA-QUEUE] Stream ...: Acquired slot...
  [OLLAMA-QUEUE] Stream ...: Released slot
  ```
- All requests queued and processed sequentially without timeout errors.

### Fix 3: User Feedback (Queue Visualization)
1. **Backend (SSE):**
   - Updated `execute_pipeline_streaming` to yield `queue_status` events while waiting in queue.
   - Frequency: Every 1 second.
   - Payload: `{'status': 'waiting', 'message': 'Warte auf freien Slot... (Xs)'}`.

2. **Frontend (MediaInputBox.vue):**
   - Added listener for `queue_status` event.
   - Visual Feedback:
     - Spinner turns **RED** (`.spinner-large.queued`) when status is 'waiting'.
     - Loading text pulses red and shows queue message.
     - Automatically resets to normal (blue) when slot is acquired.

### Next Steps
- Monitor production after deployment.

---

## Session 111 - CRITICAL: Unified Streaming Architecture Refactoring
**Date:** 2025-12-28
**Duration:** ~4 hours
- Supports both emoji and string icon names ('lightbulb', 'clipboard', etc.)

### Note
This session entry was truncated. Original content not available.
