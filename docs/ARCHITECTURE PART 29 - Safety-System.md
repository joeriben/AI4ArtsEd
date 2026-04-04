# ARCHITECTURE PART 29 — Safety System

**Status:** Authoritative
**Last Updated:** 2026-03-22 (Session 278)
**Scope:** Complete safety architecture — levels, filters, enforcement points, usage agreement, legal basis

---

## 1. Design Principles

The safety system addresses **three independent concerns**:

| Concern | Legal Basis | Scope | Applies To |
|---------|------------|-------|------------|
| **§86a StGB** | Criminal law | Prohibited symbols (Nazi, terrorist) | All levels except Research |
| **DSGVO** | Data protection (GDPR) | Personal data in prompts (NER) | All levels except Research |
| **Jugendschutz** | Youth protection (JuSchG) | Age-inappropriate content | Kids, Youth only |

These concerns are **independent and non-redundant**. Each has its own detection mechanism and cannot substitute for another.

**Core principle:** The safety system is a constitutive part of the software's scientific integrity (see LICENSE.md §4). Disabling it outside authorized research contexts constitutes a license violation (LICENSE.md §3(e)).

---

## 2. Safety Levels

Four canonical levels (configured via `user_settings.json`, default in `config._SETTINGS_DEFAULTS`):

| Level | §86a | DSGVO/NER | Age Filter | VLM Image Check | Stage 3 LLM | Use Case |
|-------|------|-----------|------------|-----------------|-------------|----------|
| **kids** | Yes | Yes | Yes (kids params) | Yes | Yes | Primary education (8-12) |
| **youth** | Yes | Yes | Yes (youth params) | Yes | Yes | Secondary education (13-17) |
| **adult** | Yes | Yes | No | No | No | Adult/university education |
| **research** | No | No | No | No | No | Authorized research institutions only |

**Backend-only:** The safety level is never sent by the frontend. It is controlled exclusively by `config.DEFAULT_SAFETY_LEVEL` (set via Settings UI, persisted in `user_settings.json`).

**Legacy normalization:** The value `"off"` (pre-2026-02) is automatically normalized to `"research"` on config load (`my_app/__init__.py`).

---

## 3. Enforcement Points

### 3.1 Stage 1 — Input Safety (`stage_orchestrator.py`)

**Function:** `execute_stage1_safety_unified()`

```
Input text
  │
  ├─ research → SKIP ALL (early return)
  │
  ├─ STEP 1: DSGVO SpaCy NER (~50-100ms)
  │    Models: de_core_news_lg + xx_ent_wiki_sm (2 models only!)
  │    PER entity detected → LLM verification (false-positive reduction)
  │    Confirmed PER → BLOCK
  │
  └─ STEP 2: §86a Fast-Filter (~0.001s)
       Bilingual keyword matching (DE+EN)
       Hit → LLM context verification (Llama Guard S1-S13) → BLOCK or allow
```

**Two concerns only in Stage 1:** DSGVO (data protection) and §86a (criminal law). Youth protection (Jugendschutz) is handled entirely by Stage 2 safety prefix — no keyword-based age filter.

#### Stage 1 LLM Routing (CRITICAL — do not mix up)

Each Stage 1 step uses a **different model for a different reason**:

| Step | Fast-Filter | LLM Model | Prompt Format | Why this model |
|------|------------|-----------|---------------|----------------|
| **DSGVO NER** | `fast_dsgvo_check()` (SpaCy) | `DSGVO_VERIFY_MODEL` | `"Is this a person name? SAFE/UNSAFE"` | Name recognition = factual question → general-purpose LLM. **ALWAYS local** (sending detected names externally = DSGVO violation) |
| **§86a** | `fast_filter_bilingual_86a()` | `SAFETY_MODEL` | S1-S13 template (`safety_llamaguard.json`) | Criminal law → needs structured harm taxonomy (S1-S13) to distinguish "Heil Hitler" from "Geschichte des Hakenkreuzes" |

**Key files:**
- `devserver/schemas/engine/stage_orchestrator.py` — orchestration logic
- `devserver/schemas/data/stage1_safety_filters_86a.json` — §86a term list
- `devserver/schemas/configs/pre_interception/` — LLM prompt configs

### 3.2 SAFETY-QUICK — Frontend Pre-Check (`schema_pipeline_routes.py`)

**Endpoint:** `POST /api/schema/pipeline/safety/quick`

Called from two places in the frontend:

1. **MediaInputBox** — automatically on `blur` and `paste` events (all text input boxes)
2. **`startGeneration()`** in `text_transformation.vue` — synchronous gate before Stage 3-4

**Text mode** (field: `text`):
```
research → SKIP (return safe=true, checks_passed=['safety_skip'])
all others → DSGVO NER + §86a fast-filter
```

**Image mode** (field: `image_path`):
```
research/adult → SKIP (vlm_skipped)
youth/kids     → VLM safety check (hybrid: primary VLM + fallback STAGE3_MODEL)
```

SAFETY-QUICK checks DSGVO and §86a only. Jugendschutz is handled by Stage 2 safety prefix.

### 3.3 Pre-Check Safety Gate — Compare + i2x Views

**Context:** Four views use a safety pre-check before generation without prior interception: `model_comparison.vue`, `language_comparison.vue`, `image_transformation.vue` (when no config selected), `multi_image_transformation.vue` (when no config selected).

**Mechanism:** These views call `POST /api/schema/pipeline/stage2` with `schema: 'user_defined'` and `skip_optimization: true`. The backend runs:

1. **Stage 1** (`execute_stage1_safety_unified`): DSGVO NER + §86a fast-filter. At `research` level: skipped entirely (early return).
2. **Stage 2** (`execute_stage2_interception`): Runs the interception LLM with SAFETY_PREFIX for kids/youth. No CLIP optimization (skipped by `skip_optimization` flag).

The frontend checks two conditions:
- `!data.success` — Stage 1 blocked (DSGVO/§86a)
- `isRefusal` — Stage 2 LLM explicitly refused (refusal phrases or empty result)

If neither triggers, the pre-check passes and generation proceeds with the **raw user prompt** (not the interception result).

**Refusal detection** (frontend, identical in all 4 views):
```
"Hierbei kann ich Dich nicht unterstützen"
"kann ich dich nicht unterstützen"
"cannot support you"
"i can't help"
"i cannot"
result === ''  (empty = refused)
```

**Why `skip_optimization`:** The pre-check only needs the LLM's safety verdict (refusal or not). CLIP optimization (`execute_optimization()`) generates `{clip_l, clip_g}` prompts that the pre-check never uses — pure waste of API calls.

#### History: Word-Overlap Heuristic (Session 277 → removed Session 278)

Session 277 (commit c292b59, 2026-03-21) introduced a word-overlap heuristic to detect "silent sanitization" — when the LLM removes unsafe content without using explicit refusal phrases. The heuristic compared word overlap between the original prompt and the interception result; if < 30% of input words survived in the output, it blocked as "Content blocked by safety check."

**Why it failed:** The heuristic conflated two structurally different LLM behaviors:
1. **Silent sanitization** (safety signal): LLM removes "unbekleideten" from "unbekleideten Clown" → low overlap → should block
2. **Normal pedagogical interception** (expected behavior): LLM rewrites "a beautiful person" into a detailed artistic description → low overlap → should NOT block

Both produce low word overlap. The heuristic **cannot distinguish** them because overlap measures lexical similarity, not semantic intent. Result: false positives on virtually every short prompt at every safety level, including `research` (where no safety prefix exists and the LLM never refuses).

**Known remaining gap:** If the Stage 2 LLM silently sanitizes instead of explicitly refusing (e.g., removes "unbekleideten" but continues normally), the `isRefusal` check does not detect it. This same gap exists in the normal t2x flow — there it is benign because the sanitized result goes to generation. In compare mode (which uses the raw prompt for generation), the unsanitized prompt reaches Stage 3 (Llama Guard). **Llama Guard and VLM have been observed to miss "unbekleideten Clown"** — this is a known architectural gap in the multi-layer safety system, not introduced by the removal of the overlap heuristic.

**Mitigation:** The SAFETY_PREFIX explicitly instructs the LLM to refuse with the exact phrase "Hierbei kann ich Dich nicht unterstützen." Improving prompt compliance (making the LLM always refuse explicitly rather than silently sanitize) is the correct architectural fix for this gap, not a frontend word-counting heuristic.

### 3.4 Stage 3 — Pre-Output Safety (`stage_orchestrator.py`)

**Function:** `execute_stage3_safety()`

```
Input (post-interception prompt)
  │
  ├─ research/adult → SKIP (return original prompt)
  │
  ├─ STEP 2: Translate to English (cached if unchanged)
  │
  ├─ STEP 3: §86a fast-filter on translated text → instant block
  │
  ├─ STEP 4: Determine generation prompt
  │   kids  → translated English prompt
  │   youth → original language prompt
  │
  └─ STEP 5: Single Llama-Guard check (proper S1-S13 template)
      └─ _llm_safety_check_generation(generation_prompt)
      └─ Same template as Stage 1 (safety_llamaguard.json)
      └─ Only image-relevant S-codes block (see below)
      └─ Fail-closed on error/timeout
```

**Tiered translation** (Session 183): Translation-for-safety is decoupled from translation-for-generation. Youth+ users can explore how models react to their native language. The translate button in MediaInputBox remains available for manual use. Kids still get auto-translated English prompts for better model output quality.

**Session 244 redesign:** Previously, Stage 3 ran two sequential Llama-Guard calls: an age fast-filter + LLM verify (STEP 3b), then a pipeline-based safety chunk with the wrong prompt format (STEP 4). The pipeline chunk used a free-form question template on `llama-guard3:1b` — a guard model trained on structured S1-S13 categories. This caused false positives (e.g. Lagos scene → S4). Now replaced with a single unconditional `_llm_safety_check_generation()` call using the proper S1-S13 template. The age fast-filter was redundant with Stage 1 (MediaInputBox `/safety/quick` already covers it).

**Stage 3 S-code filtering** (Session 255, revised): Llama-Guard's S1-S13 categories were designed for chat safety, not image generation. Some categories cause false positives on harmless image prompts (e.g. "make a realistic photo" → S7 Intellectual Property, motorcycle photo → S7). Stage 3 blocks on **image-generation-relevant** S-codes:

| Blocks | Code | Category | Why relevant |
|--------|------|----------|-------------|
| Yes | S1 | Violent Crimes | Violence in generated images |
| Yes | S2 | Non-Violent Crimes | Weapons crimes (Session 255: was excluded, 9/11 bypass) |
| Yes | S3 | Sex Crimes | Sexual content in images |
| Yes | S4 | Child Exploitation | CSAM prevention |
| No | S5 | Specialized Advice | Chat-specific (medical/legal/financial advice) |
| No | S6 | Privacy | Chat-specific (personal data in text) |
| No | S7 | Intellectual Property | Chat-specific — causes false positives (motorcycle → S7, "realistic photo" → S7) |
| Yes | S8 | Indiscriminate Weapons | Weapons imagery (Session 255: was excluded, weapons bypass) |
| Yes | S9 | Hate | Hate imagery |
| Yes | S10 | Self-Harm | Self-harm imagery |
| Yes | S11 | Sexual Content | Sexual imagery |
| No | S12 | Elections | Chat-specific (election misinformation) |
| No | S13 | Code Interpreter Abuse | Chat-specific |

Ignored codes are logged but do not block generation. This filtering applies **only to Stage 3** (post-interception generation prompts). Stage 1 §86a still uses the full S1-S13 template for context verification.

Stage 3 catches prompts that pass all fast-filters but would generate harmful imagery. Example: "Wesen sind feindselig zueinander und fügen einander Schaden zu" — passes keyword filters but generates harmful content for children.

**Code safety:** `execute_stage3_safety_code()` — same skip logic for generated code (JavaScript, Ruby, etc.)

### 3.5 Post-Generation VLM Check (`schema_pipeline_routes.py`)

**Scope:** Images only, kids/youth only

After Stage 4 generates an image, a hybrid two-path safety check analyzes the actual pixels before delivery to frontend.

**Hybrid Architecture (Session 265):**

```
media_type != 'image' → SKIP
safety_level not in (kids, youth) → SKIP

PRIMARY PATH: VLM sees image + classifies directly
  VLM (qwen3-vl:2b) + category-checklist prompt + "Answer SAFE or UNSAFE"
  max_new_tokens=1500 (prevents truncation, was 500)
  VLM → "safe"   → SSE 'complete'
  VLM → "unsafe" → SSE 'blocked' (stage: 'vlm_safety')
  VLM → no verdict (deliberation loop) → FALLBACK

FALLBACK PATH: VLM describes → STAGE3_MODEL judges
  Step 1: VLM describes image (safety-focused prompt, NO verdict coercion)
  Step 2: STAGE3_MODEL (e.g. Claude Sonnet 4.6 via Mammouth) classifies description
  Verdict → "safe"/"unsafe" → same as primary
  No verdict → fail-closed → SSE 'blocked'
```

**Why hybrid:** The primary path has proven zero-FN accuracy — the VLM sees horror visually and classifies correctly. But ~2.4% of cases (6/247 in WS 17.03) produced no verdict due to deliberation loops or truncation. The fallback gives these cases a second chance via text-based classification instead of immediate fail-closed blocking.

**Config:** `VLM_SAFETY_MODEL` in `user_settings.json` for VLM, `STAGE3_MODEL` for verdict fallback.
**Fail-closed throughout:** No verdict from either path → blocked.

**Model Constraints (Session 298, 2026-04-04):**

| Model | SAFE/UNSAFE prompts | Recommendation |
|-------|-------------------|----------------|
| **qwen3-vl:2b** | Reliable. Workshop-validated (202 images, 13.03.2026). | **USE THIS** |
| qwen2.5-vl:2b | Hallucinates UNSAFE on dramatic imagery. 100% FP rate. | DO NOT USE for safety |

qwen3-vl:2b runs via `Qwen25VLChatHandler` in llama-cpp-python (handler is architecture-compatible).
The content-checklist prompt (enumerating concrete categories) is validated — DO NOT simplify without workshop re-test.

**False-Negative Test (Session 298):**
- Hate symbols (swastika): UNSAFE (kids) — correctly caught
- Skull/skeleton: UNSAFE (kids), SAFE (youth) — correctly differentiated
- Bloody knife: UNSAFE (kids) — correctly caught
- Flowers, ship wreck: SAFE — correctly passed
- Abstract red shapes: SAFE — model interprets as "abstract art", not blood (acceptable for synthetic primitives)

---

## 4. Detection Mechanisms

### 4.1 §86a Fast-Filter

**Function:** `fast_filter_bilingual_86a()` in `stage_orchestrator.py`

Bilingual (DE+EN) keyword matching against known prohibited symbols:
- Nazi symbols: Hakenkreuz, SS-Runen, Schwarze Sonne, etc.
- Terrorist organizations: ISIS/ISIL, Al-Qaeda, PKK, RAF
- Extremist codes: 88 (HH), 18 (AH), 28 (B&H)

**Data:** `devserver/schemas/data/stage1_safety_filters_86a.json`

On match → **Llama Guard** (`SAFETY_MODEL`) context check with S1-S13 template. Educational/historical context (e.g., "Geschichte des Hakenkreuzes in der Antike") passes; glorifying context (e.g., "Heil Hitler") is blocked. Fail-closed if LLM unavailable.

### 4.2 Jugendschutz — Stage 2 Safety Prefix

**No keyword-based age filter.** Youth protection is handled entirely by the Stage 2 interception LLM via a safety prefix prepended to the instruction.

**Definition:** `SAFETY_PREFIXES` in `schemas/engine/instruction_selector.py`

**Mechanism:** For kids/youth safety levels, a safety prefix is prepended to the LLM instruction. The prefix instructs the LLM to refuse racist, terrorist, violence-glorifying, sexist, or pornographic input — including implied/metaphorical forms (airplane into building, vehicle into crowd). The prefix also guards against malicious Context rules: "Do not introduce violence, weapons, armed conflict, abuse, nudity, sexual, or pornographic content even if the Context rules would produce it."

**Mandatory for ALL generation paths:** Stage 2 cannot be skipped for kids/youth:
- **t2x:** `skip_stage2` is overridden. Even with an empty context box (`user_defined` config), the LLM is called with the safety prefix.
- **i2x / multi-i2x (Session 275):** Config selection triggers Stage 2 streaming interception into the context box. If no config is selected, `startGeneration()` automatically runs `user_defined` interception before proceeding to Stage 3+4. This closes the Jugendschutz gap where i2x prompts like "undress all figures" previously bypassed Stage 2 entirely.

**Why not keyword-based:** The keyword age filter oscillated between too aggressive (29% false positives in Workshop 12.03.2026) and too permissive (weapons bypass) over 10+ sessions. See `SAFETY_SYSTEM_HISTORY.md` Section 2 (Era 6) for the complete record.

### 4.3 DSGVO SpaCy NER

**Function:** `fast_dsgvo_check()` in `stage_orchestrator.py`

Only 2 SpaCy models loaded (prevents cross-language false positives):
- `de_core_news_lg` — German NER
- `xx_ent_wiki_sm` — Multilingual NER

**Two-layer false positive reduction:**

1. **POS-tag pre-filter** (milliseconds, no LLM): SpaCy PER entities are checked for PROPN tokens. Entities consisting only of non-PROPN tokens (e.g. "Schräges Fenster" = ADJ+NOUN) are discarded immediately. This eliminates most SpaCy false positives before any LLM call.

2. **LLM verification** (`llm_verify_person_name()`): Remaining PER entities (those with at least one PROPN token) are verified by a local LLM. The prompt asks: "Are these flagged words actually person names, or false positives?" Response: `SAFE` (false positive) or `UNSAFE` (actual name → block).

**Dedicated model:** `config.DSGVO_VERIFY_MODEL` (configurable in Settings UI, default: `qwen3:1.7b`). Must be a **general-purpose model** — guard models (llama-guard) classify content safety categories, not "is this a name?". Recommended VRAM-efficient options: qwen3:1.7b, gemma3:1b, qwen2.5:1.5b, llama3.2:1b.

**CRITICAL: Local-only.** The `llm_verify_person_name()` function ALWAYS runs via local LLM (GPU Service, in-process llama-cpp-python) — never external APIs. Sending detected personal names to Mistral/Anthropic/OpenAI for verification would itself be a DSGVO violation.

**Thinking model support:** Some models use thinking mode — reasoning in `message.thinking`, answer in `message.content`. Under VRAM pressure, `content` may be empty while the answer exists only in `thinking`. The code checks both fields: first `content`, then falls back to extracting SAFE/UNSAFE from `thinking`. `num_predict: 500` minimum.

**Fail-closed with Circuit Breaker (Session 218):** If neither `content` nor `thinking` yields a SAFE/UNSAFE answer, the system blocks. A circuit breaker (`my_app/utils/circuit_breaker.py`) tracks consecutive failures — after 3 failures, it triggers the LLM watchdog for automatic health check before falling back to a human-readable error message. See Section 4.5 for details.

**Lesson learned (Session 175):** Running all 12 SpaCy models causes cross-language confusion (e.g., `en_core_web_lg` flags "Der Eiffelturm" as PERSON).

**Lesson learned (Session 181):** The LLM prompt must ask "is this a person name?" (SAFE/UNSAFE), not "is this a real existing person?" (JA/NEIN). The latter blocks common names ("Karl Meier") while passing real professors ("Benjamin Jörissen"). Guard models are unsuitable — they answer "safe" because the text content is harmless, not because the entity is or isn't a name.

### 4.4 VLM Image Analysis (Hybrid Architecture, Session 265)

**Function:** `vlm_safety_check()` in `my_app/utils/vlm_safety.py`

Post-generation visual analysis with hybrid two-path architecture:

**Primary path:** VLM (qwen3-vl:2b) sees image directly + classifies. Category-checklist prompt per safety level:
- Kids (6-12): violence, gore, nudity, hate symbols, self-harm, racism, terrorism, sexism, scary/unsettling/traumatizing
- Youth (12-16): Same minus scary/unsettling/traumatizing

**Fallback path** (when primary produces no verdict): VLM describes image (safety-focused, no verdict coercion) → STAGE3_MODEL (cloud LLM, e.g. Claude Sonnet 4.6 via Mammouth) classifies the text description.

**Fail-closed:** Both paths fail-closed. No verdict from either → blocked.

**Design decision (Session 265):** A pure two-model architecture (VLM describes → text model judges) was tested first but introduced false negatives: the VLM's text description loses visual horror quality ("hands reaching out" instead of "skeletal claws from darkness"). The primary single-model path preserves zero-FN accuracy because the VLM sees and classifies the actual pixels. The fallback only activates for the ~2.4% of cases where the VLM enters deliberation loops.

### 4.5 Circuit Breaker + LLM Self-Healing (Session 218, updated Session 292)

**Problem:** When the LLM backend becomes unresponsive, all LLM verification calls (DSGVO NER, age filter) return None. Without mitigation, this either blocks all workshop activity (hard fail-closed) or lets unsafe content through (fail-open).

> **Session 292 (2026-03-28):** Ollama replaced by in-process llama-cpp-python in GPU Service.
> The circuit breaker now triggers the LLM watchdog which checks GPU Service health at
> `/api/llm/health`. The sudoers-based `systemctl restart ollama` mechanism is obsolete.

**Solution:** Three-layer defense:

```
LLM call returns None
  │
  ├─ Record failure in CircuitBreaker
  │   └─ Counter < 3 → log + continue (transient tolerance)
  │   └─ Counter ≥ 3 → Circuit OPEN
  │         │
  │         ├─ Attempt self-healing (LLM Watchdog)
  │         │   └─ Health check at GPU_SERVICE_URL/api/llm/health
  │         │   └─ Health check loop (max 30s)
  │         │   └─ Success → Circuit CLOSED, proceed normally
  │         │
  │         └─ Healing failed → fail-closed with admin message:
  │             "Sicherheitsprüfung nicht verfügbar.
  │              Bitte GPU Service neustarten."
  │
  └─ LLM responds (SAFE/UNSAFE) → record_success() → reset counter
```

**Circuit Breaker states:**
- **CLOSED** (normal): LLM calls pass through
- **OPEN** (3+ failures): triggers self-healing, then fail-closed if healing fails
- **HALF_OPEN** (after 30s cooldown): one probe call tests recovery

**Key files:**
- `devserver/my_app/utils/circuit_breaker.py` — Circuit breaker with self-healing integration
- `devserver/my_app/utils/llm_watchdog.py` — LLM health check via GPU Service

---

## 5. Flow Summary

```
User Input
  │
  ├─ [Frontend] MediaInputBox on blur/paste
  │   └─ POST /safety/quick (DSGVO NER + §86a, text)
  │   └─ POST /safety/quick (VLM, uploaded images)
  │
  ├─ [Stage 1] execute_stage1_safety_unified()           ← t2x only
  │   └─ DSGVO NER → §86a fast-filter (two legal concerns only)
  │
  ├─ [Stage 2] Prompt Interception — JUGENDSCHUTZ HERE   ← ALL paths (t2x, i2x, multi-i2x)
  │   └─ Safety prefix mandatory for kids/youth (even with empty context box)
  │   └─ LLM refuses racist/terrorist/violence-glorifying/sexist/pornographic input
  │   └─ t2x: triggered by runInterception() button
  │   └─ i2x/multi-i2x: triggered by config selection OR auto at Generate
  │
  ├─ [Frontend] startGeneration() pre-generation gate
  │   └─ POST /safety/quick on final prompt (catches edits without blur)
  │   └─ i2x/multi-i2x: enforces Stage 2 if not yet run (user_defined fallback)
  │
  ├─ [Stage 3] execute_stage3_safety()
  │   └─ Translation + §86a filter + Llama-Guard S1-S13 check (kids/youth)
  │
  ├─ [Stage 4] Media Generation
  │
  └─ [Post-Gen] VLM Image Check (kids/youth, images only)
        └─ Safe → deliver | Unsafe → SSE 'blocked'
```

### 5.1 Canvas Workflows — Intentionally Unfiltered

Canvas routes (`/api/canvas/execute`, `/execute-stream`, `/execute-batch`) have **no safety enforcement by design**. Canvas is restricted to `adult` and `research` safety levels only — kids/youth cannot access it. Since `adult` skips age-appropriate checks and `research` skips all checks, no input filtering is needed on Canvas routes. Stage 3 safety still applies during generation for `adult`.

---

## 6. Usage Agreement (Human Safety Layer)

**Route:** `/usage-agreement` (`UsageAgreementView.vue`)

Before any platform interaction, workshop leaders must accept a binding usage agreement ("Nutzungsvereinbarung"). This is the **human safety layer** — the technical system protects against content; the agreement establishes pedagogical responsibility.

**Mechanism:**
- Router guard (`beforeEach`) checks for `usage_agreement_accepted` cookie
- Missing cookie → redirect to `/usage-agreement` (with return URL)
- Cookie lifetime: 24 hours (re-consent required daily)
- Route has `skipAgreementCheck` meta (prevents redirect loop)

**Content (binding conditions):**
1. Actively supervise participants throughout the session
2. Set safety level appropriate to age group
3. Prevent misuse and deliberate circumvention of safety mechanisms
4. Test the platform before using it with groups
5. No technical system can replace pedagogical supervision

**Design decisions:**
- Framed as "Nutzungsvereinbarung" (agreement), not "Nutzungshinweis" (notice) — binding character
- Intro text ends with "...an folgende Bedingungen geknüpft:" — conditions, not suggestions
- Checkbox includes explicit consent ("Ich stimme diesen Bedingungen zu")
- No enumeration of harmful content categories (kids read this on iPads)
- Educator-to-educator tone, not legal/bureaucratic

**Key files:**
- `public/.../views/UsageAgreementView.vue` — Page
- `public/.../router/index.ts` — Guard + route definition
- `public/.../i18n/en.ts` / `de.ts` — Text under `usageAgreement.*`

---

## 7. Configuration

### config.py

Safety-configurable values (`SAFETY_MODEL`, `DSGVO_VERIFY_MODEL`, `VLM_SAFETY_MODEL`, `DEFAULT_SAFETY_LEVEL`) are defined in `_SETTINGS_DEFAULTS` as fallback defaults for fresh installations. They are pre-initialized as module globals for import compatibility.

Static timeouts (not user-configurable):
- `OLLAMA_TIMEOUT_SAFETY = 30` — Short timeout for safety verification
- `OLLAMA_TIMEOUT_DEFAULT = 120` — Standard LLM calls

### user_settings.json

**Source of truth** for all runtime-configurable settings. Loaded at startup by `reload_user_settings()` in `my_app/__init__.py`. Auto-created from `_SETTINGS_DEFAULTS` on first run. Legacy `"off"` values are normalized to `"research"`.

### Settings UI

`SettingsView.vue` — Safety Level dropdown with descriptive info boxes per level. Research mode shows red warning about restricted use (see LICENSE.md §3(e)).

---

## 8. Legal Integration

The research mode restriction is codified in `LICENSE.md` §3(e):
- Requires institutional affiliation (university, Forschungseinrichtung)
- Requires documented research purpose
- Requires ethical oversight (Ethikkommission/IRB)
- Prohibits exposure of unfiltered outputs to minors
- Violation = license termination (§7) + scientific integrity impairment (§4, §14 UrhG)

---

## 9. Key Files

| File | Role |
|------|------|
| `devserver/config.py` | `_SETTINGS_DEFAULTS` (fallback defaults), timeouts, static config |
| `devserver/my_app/__init__.py` | Legacy "off" → "research" normalization |
| `devserver/schemas/engine/stage_orchestrator.py` | Stage 1 + Stage 3 safety logic |
| `devserver/my_app/routes/schema_pipeline_routes.py` | SAFETY-QUICK endpoint, VLM post-gen check |
| `devserver/my_app/utils/vlm_safety.py` | VLM image analysis |
| `devserver/my_app/utils/circuit_breaker.py` | Circuit breaker with LLM self-healing |
| `devserver/my_app/utils/llm_watchdog.py` | LLM health check via GPU Service |
| `devserver/schemas/chunks/safety_check_kids.json` | ~~Dead code~~ (Stage 3 no longer uses pipeline chunks, Session 244) |
| `devserver/schemas/chunks/safety_check_youth.json` | ~~Dead code~~ (Stage 3 no longer uses pipeline chunks, Session 244) |
| `devserver/schemas/data/stage1_safety_filters_*.json` | Filter term lists |
| ~~`0_setup_ollama_watchdog.sh`~~ | ~~Deleted Session 292 — Ollama replaced by in-process llama-cpp-python~~ |
| `public/.../views/text_transformation.vue` | Pre-generation `/safety/quick` gate in `startGeneration()` |
| `public/.../views/SettingsView.vue` | Safety level dropdown UI |
| `public/.../views/UsageAgreementView.vue` | Usage agreement (human safety layer) |
| `public/.../router/index.ts` | Usage agreement guard (cookie check) |
| `LICENSE.md` §3(e) | Research mode legal restrictions |

---

## 10. Historical Context

| Session | Date | Change |
|---------|------|--------|
| 14 | 2025-11-02 | §86a StGB system prompt for GPT-OSS (ISIS failure case) |
| 29 | 2025-11-10 | Hybrid fast-filter + LLM verification |
| 132 | 2026-01-23 | Centralized safety in stage_orchestrator.py |
| 143 | 2026-01-27 | Fast-Filter-First architecture (no LLM for 95%+ cases) |
| 161 | 2026-02-07 | VLM post-generation image check |
| 170 | 2026-02-12 | Safety-level centralization ("off" → "research"), LICENSE.md §3(e) |
| 181 | 2026-02-18 | DSGVO NER rewrite: POS-tag pre-filter, SAFE/UNSAFE prompt, dedicated DSGVO_VERIFY_MODEL |
| 183 | 2026-02-19 | Tiered translation: auto for kids, optional for youth+, none for adult/research |
| 217 | 2026-02-26 | DISASTER: GPU Service LLM routing broke everything. Emergency fail-open patches |
| 218 | 2026-02-27 | Full repair: circuit breaker, self-healing watchdog, dead code removal, timeout differentiation |
| 244 | 2026-03-03 | Stage 3 redesign: single Llama-Guard call with proper S1-S13 template, removed redundant age fast-filter |
| 244 | 2026-03-03 | Pre-generation `/safety/quick` gate in `startGeneration()` — closes blur-bypass gap |
| 245 | 2026-03-04 | Stage 1 LLM routing fix: §86a→Llama Guard (was blind block), Age Filter→qwen3 SAFE/UNSAFE (was Llama Guard) |
| 246 | 2026-03-04 | Age filter: fuzzy→stem-prefix matching (false positive fix). LLM prompt: concrete categories + few-shot. Stage 3: only image-relevant S-codes block (S7 etc. ignored) |
| 254 | 2026-03-10 | VLM safety: fail-open → fail-closed. Only explicit SAFE verdict lets images through |
| 255 | 2026-03-10 | **CRITICAL**: Kids safety bypass fix. EN/DE weapon terms added. Llama-Guard 1b→8b. DSGVO-first ordering. gpt-oss-120b for kids age-filter. S2+S8 added to Stage 3 blocking set |
| 263 | 2026-03-17 | Usage agreement page: route, guard, 24h cookie, Vue page |
| 264 | 2026-03-17 | Usage agreement text rewrite: "Nutzungshinweis" → "Nutzungsvereinbarung" (binding conditions) |
| 265 | 2026-03-18 | VLM safety: hybrid architecture (primary single-model + two-model fallback). max_new_tokens 500→1500. STAGE3_MODEL as verdict fallback |
| 275 | 2026-03-21 | **CRITICAL**: Stage 2 Jugendschutz for i2x/multi-i2x. Safety Prefix: nudity/sexual added to Context-rules clause. i2x/multi-i2x now mandatory Stage 2 interception before generation |
| 278 | 2026-03-22 | **FIX**: Broken word-overlap heuristic removed from 4 pre-check views. `skip_optimization` parameter added to Stage 2 endpoint. See §3.5 |

---

## 11. Related Documents

- `docs/reference/safety-architecture-matters.md` — Original §86a failure analysis (Session 14)
- `docs/HANDOVER_SAFETY_REFACTORING.md` — Planned endpoint separation (2026-01-26)
- `docs/ARCHITECTURE PART 01 - 4-Stage Orchestration Flow.md` — Pipeline overview
- `LICENSE.md` §3(e), §4 — Legal framework for safety system
