# ARCHITECTURE PART 29 — Safety System

**Status:** Authoritative
**Last Updated:** 2026-03-04 (Session 245)
**Scope:** Complete safety architecture — levels, filters, enforcement points, legal basis

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

Four canonical levels, defined in `devserver/config.py`:

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

**Function:** `execute_stage1_gpt_oss_unified()`

```
Input text
  │
  ├─ research → SKIP ALL (early return)
  │
  ├─ STEP 1: §86a Fast-Filter (~0.001s)
  │    Bilingual keyword matching (DE+EN)
  │    Hit → LLM context verification → BLOCK or allow
  │
  ├─ STEP 2: Age-Appropriate Fast-Filter
  │    Skip for adult/research
  │    kids/youth → filter list match → LLM verification → BLOCK or allow
  │
  └─ STEP 3: DSGVO SpaCy NER (~50-100ms)
       Models: de_core_news_lg + xx_ent_wiki_sm (2 models only!)
       PER entity detected → LLM verification (false-positive reduction)
       Confirmed PER → BLOCK
```

#### Stage 1 LLM Routing (CRITICAL — do not mix up)

Each Stage 1 step uses a **different model for a different reason**. The logic:

| Step | Fast-Filter | LLM Model | Prompt Format | Why this model |
|------|------------|-----------|---------------|----------------|
| **§86a** | `fast_filter_bilingual_86a()` | `SAFETY_MODEL` (llama-guard3:1b) | S1-S13 template (`safety_llamaguard.json`) | §86a = criminal law → needs structured harm taxonomy (S1-S13) to distinguish "Heil Hitler" from "Geschichte des Hakenkreuzes" |
| **Age Filter** | `fast_filter_check()` | `DSGVO_VERIFY_MODEL` (qwen3:1.7b) | `"Is this appropriate for ages {6-12/13-17}? SAFE/UNSAFE"` | Age-appropriateness = subjective judgement → needs general-purpose LLM, NOT a guard model (guard models classify crimes, not age suitability) |
| **DSGVO NER** | `fast_dsgvo_check()` (SpaCy) | `DSGVO_VERIFY_MODEL` (qwen3:1.7b) | `"Is this a person name? SAFE/UNSAFE"` | Name recognition = factual question → needs general-purpose LLM |

**Why Llama Guard fails for the Age Filter:** Llama Guard's S1-S13 categories detect content that "enables, encourages, or excuses" crimes. "Blut" (blood) or "vampire" is not a crime — Llama Guard says "safe". But it's inappropriate for a 6-year-old. Only a general-purpose model can make that age-appropriateness judgement.

**Why a general-purpose model fails for §86a:** A simple "SAFE/UNSAFE" question about Nazi symbols gives no structured framework for distinguishing educational from glorifying context. Llama Guard's S1-S13 taxonomy (especially S1: violent crimes, S4: hate) provides exactly that structure.

**Key files:**
- `devserver/schemas/engine/stage_orchestrator.py` — orchestration logic
- `devserver/schemas/data/stage1_safety_*.json` — filter term lists
- `devserver/schemas/configs/pre_interception/` — LLM prompt configs

### 3.2 SAFETY-QUICK — Frontend Pre-Check (`schema_pipeline_routes.py`)

**Endpoint:** `POST /api/schema/pipeline/safety/quick`

Called from two places in the frontend:

1. **MediaInputBox** — automatically on `blur` and `paste` events (all text input boxes)
2. **`startGeneration()`** in `text_transformation.vue` — synchronous gate before Stage 3-4

The second caller (Session 244) closes a gap: if a user edits the optimized prompt box and clicks "Generate" without blurring, MediaInputBox's blur/paste check wouldn't have fired. The pre-generation check ensures the age fast-filter always runs before generation, regardless of how the user triggers it.

**Text mode** (field: `text`):
```
research → SKIP (return safe=true, checks_passed=['safety_skip'])
adult    → §86a fast-filter + DSGVO NER (no age filter)
youth    → §86a fast-filter + age filter + LLM verify + DSGVO NER
kids     → §86a fast-filter + age filter + LLM verify + DSGVO NER
```

**Image mode** (field: `image_path`):
```
research/adult → SKIP (vlm_skipped)
youth/kids     → VLM safety check via Ollama
```

**CRITICAL — Complementary roles of SAFETY-QUICK vs Stage 3 (Session 244 insight):**

| Check | What it catches | Mechanism | Example |
|-------|----------------|-----------|---------|
| **SAFETY-QUICK** (age filter) | Age-inappropriate but legal content | Fuzzy keyword match + LLM context verify | "Ein Kind wird von einem Monster angegriffen" → blocked by "monster, verletzen" |
| **Stage 3** (Llama-Guard S1-S13) | Criminal/harmful content categories | S1-S13 structured classification | Terrorism instructions, weapons, hate speech |

Llama-Guard's S1-S13 categories focus on content that "enables, encourages, or excuses" crimes — a fantasy monster scenario is NOT a crime and passes S1-S13. Only the age fast-filter in SAFETY-QUICK catches age-inappropriate-but-legal content. These two checks are **complementary, not redundant**.

### 3.3 Stage 3 — Pre-Output Safety (`stage_orchestrator.py`)

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
      └─ Fail-closed on error/timeout
```

**Tiered translation** (Session 183): Translation-for-safety is decoupled from translation-for-generation. Youth+ users can explore how models react to their native language. The translate button in MediaInputBox remains available for manual use. Kids still get auto-translated English prompts for better model output quality.

**Session 244 redesign:** Previously, Stage 3 ran two sequential Llama-Guard calls: an age fast-filter + LLM verify (STEP 3b), then a pipeline-based safety chunk with the wrong prompt format (STEP 4). The pipeline chunk used a free-form question template on `llama-guard3:1b` — a guard model trained on structured S1-S13 categories. This caused false positives (e.g. Lagos scene → S4). Now replaced with a single unconditional `_llm_safety_check_generation()` call using the proper S1-S13 template. The age fast-filter was redundant with Stage 1 (MediaInputBox `/safety/quick` already covers it).

Stage 3 catches prompts that pass all fast-filters but would generate harmful imagery. Example: "Wesen sind feindselig zueinander und fügen einander Schaden zu" — passes keyword filters but generates harmful content for children.

**Code safety:** `execute_stage3_safety_code()` — same skip logic for generated code (JavaScript, Ruby, etc.)

### 3.4 Post-Generation VLM Check (`schema_pipeline_routes.py`)

**Scope:** Images only, kids/youth only

After Stage 4 generates an image, a local VLM (qwen3-vl:2b via Ollama) analyzes the actual pixels before delivery to frontend.

```
media_type != 'image' → SKIP
safety_level not in (kids, youth) → SKIP
VLM → "safe" → SSE 'complete'
VLM → "unsafe" → SSE 'blocked' (stage: 'vlm_safety')
VLM → error → fail-open → SSE 'complete'
```

**Config:** `VLM_SAFETY_MODEL` in `config.py`
**Technical note:** qwen3-vl uses thinking mode — analysis in `message.thinking`, decision in `message.content`. Both checked. `num_predict: 500` minimum.

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

### 4.2 Age-Appropriate Fast-Filter

**Function:** `fast_filter_check()` in `stage_orchestrator.py`

Fuzzy matching against level-specific filter lists:
- `stage1_safety_filters_kids.json`
- `stage1_safety_filters_youth.json`

On match → **general-purpose LLM** (`DSGVO_VERIFY_MODEL`, qwen3:1.7b) with simple age-appropriate prompt: "Is this appropriate for ages 6-12/13-17? SAFE/UNSAFE". NOT Llama Guard — guard models classify crimes, not age suitability.

### 4.3 DSGVO SpaCy NER

**Function:** `fast_dsgvo_check()` in `stage_orchestrator.py`

Only 2 SpaCy models loaded (prevents cross-language false positives):
- `de_core_news_lg` — German NER
- `xx_ent_wiki_sm` — Multilingual NER

**Two-layer false positive reduction:**

1. **POS-tag pre-filter** (milliseconds, no LLM): SpaCy PER entities are checked for PROPN tokens. Entities consisting only of non-PROPN tokens (e.g. "Schräges Fenster" = ADJ+NOUN) are discarded immediately. This eliminates most SpaCy false positives before any LLM call.

2. **LLM verification** (`llm_verify_person_name()`): Remaining PER entities (those with at least one PROPN token) are verified by a local LLM. The prompt asks: "Are these flagged words actually person names, or false positives?" Response: `SAFE` (false positive) or `UNSAFE` (actual name → block).

**Dedicated model:** `config.DSGVO_VERIFY_MODEL` (configurable in Settings UI, default: `qwen3:1.7b`). Must be a **general-purpose model** — guard models (llama-guard) classify content safety categories, not "is this a name?". Recommended VRAM-efficient options: qwen3:1.7b, gemma3:1b, qwen2.5:1.5b, llama3.2:1b.

**CRITICAL: Local-only.** The `llm_verify_person_name()` function ALWAYS runs via local Ollama — never external APIs. Sending detected personal names to Mistral/Anthropic/OpenAI for verification would itself be a DSGVO violation.

**Thinking model support:** Some models use thinking mode — reasoning in `message.thinking`, answer in `message.content`. Under VRAM pressure, `content` may be empty while the answer exists only in `thinking`. The code checks both fields: first `content`, then falls back to extracting SAFE/UNSAFE from `thinking`. `num_predict: 500` minimum.

**Fail-closed with Circuit Breaker (Session 218):** If neither `content` nor `thinking` yields a SAFE/UNSAFE answer, the system blocks. A circuit breaker (`my_app/utils/circuit_breaker.py`) tracks consecutive failures — after 3 failures, it triggers the Ollama watchdog for automatic restart before falling back to a human-readable error message. See Section 4.5 for details.

**Lesson learned (Session 175):** Running all 12 SpaCy models causes cross-language confusion (e.g., `en_core_web_lg` flags "Der Eiffelturm" as PERSON).

**Lesson learned (Session 181):** The LLM prompt must ask "is this a person name?" (SAFE/UNSAFE), not "is this a real existing person?" (JA/NEIN). The latter blocks common names ("Karl Meier") while passing real professors ("Benjamin Jörissen"). Guard models are unsuitable — they answer "safe" because the text content is harmless, not because the entity is or isn't a name.

### 4.4 VLM Image Analysis

**Function:** `vlm_safety_check()` in `my_app/utils/vlm_safety.py`

Post-generation visual analysis. Different prompts per safety level:
- Kids (6-12): Checks for violence, nudity, unsettling/traumatizing content
- Youth (14-18): Adapted thresholds for teenagers

**Fail-open:** VLM errors never block generation.

### 4.5 Circuit Breaker + Ollama Self-Healing (Session 218)

**Problem:** When Ollama becomes unresponsive, all LLM verification calls (DSGVO NER, age filter) return None. Without mitigation, this either blocks all workshop activity (hard fail-closed) or lets unsafe content through (fail-open).

**Solution:** Three-layer defense:

```
LLM call returns None
  │
  ├─ Record failure in CircuitBreaker
  │   └─ Counter < 3 → log + continue (transient tolerance)
  │   └─ Counter ≥ 3 → Circuit OPEN
  │         │
  │         ├─ Attempt auto-restart (Ollama Watchdog)
  │         │   └─ sudo systemctl restart ollama
  │         │   └─ Health check loop (max 30s)
  │         │   └─ Success → Circuit CLOSED, proceed normally
  │         │
  │         └─ Restart failed → fail-closed with admin message:
  │             "Sicherheitsprüfung nicht verfügbar.
  │              Bitte Ollama neustarten: sudo systemctl restart ollama"
  │
  └─ LLM responds (SAFE/UNSAFE) → record_success() → reset counter
```

**Circuit Breaker states:**
- **CLOSED** (normal): LLM calls pass through
- **OPEN** (3+ failures): triggers self-healing, then fail-closed if healing fails
- **HALF_OPEN** (after 30s cooldown): one probe call tests recovery

**Watchdog constraints:**
- Max 1 restart per 5 minutes (prevents crash loops)
- Thread-safe (lock prevents concurrent restarts)
- Graceful degradation: if passwordless sudo is not configured, falls back to admin message

**Setup (one-time):**
```bash
sudo ./0_setup_ollama_watchdog.sh
```
This creates `/etc/sudoers.d/ai4artsed-ollama` granting passwordless `systemctl restart/start/stop ollama`.

**Key files:**
- `devserver/my_app/utils/circuit_breaker.py` — Circuit breaker with self-healing integration
- `devserver/my_app/utils/ollama_watchdog.py` — Ollama restart + health check
- `0_setup_ollama_watchdog.sh` — Sudoers setup script

---

## 5. Flow Summary

```
User Input
  │
  ├─ [Frontend] MediaInputBox on blur/paste
  │   └─ POST /safety/quick (§86a + age filter + DSGVO, text)
  │   └─ POST /safety/quick (VLM, uploaded images)
  │
  ├─ [Stage 1] execute_stage1_gpt_oss_unified()
  │   └─ §86a fast-filter → Age filter → DSGVO NER
  │
  ├─ [Stage 2] Prompt Interception (no safety)
  │
  ├─ [Frontend] startGeneration() pre-generation gate
  │   └─ POST /safety/quick on final prompt (catches edits without blur)
  │
  ├─ [Stage 3] execute_stage3_safety()
  │   └─ Translation + §86a filter + single Llama-Guard S1-S13 check (kids/youth)
  │
  ├─ [Stage 4] Media Generation
  │
  └─ [Post-Gen] VLM Image Check (kids/youth, images only)
        └─ Safe → deliver | Unsafe → SSE 'blocked'
```

### 5.1 Canvas Workflows — Intentionally Unfiltered

Canvas routes (`/api/canvas/execute`, `/execute-stream`, `/execute-batch`) have **no safety enforcement by design**. Canvas is restricted to `adult` and `research` safety levels only — kids/youth cannot access it. Since `adult` skips age-appropriate checks and `research` skips all checks, no input filtering is needed on Canvas routes. Stage 3 safety still applies during generation for `adult`.

---

## 6. Configuration

### config.py

```python
DEFAULT_SAFETY_LEVEL = 'kids'          # Default, overridden by user_settings.json
SAFETY_MODEL = 'llama-guard3:1b'       # Guard model — §86a context check (Stage 1) + pre-generation check (Stage 3)
DSGVO_VERIFY_MODEL = 'qwen3:1.7b'     # General-purpose model — age filter (Stage 1) + DSGVO NER verify (Stage 1)
VLM_SAFETY_MODEL = 'qwen3-vl:2b'      # Ollama model for image checks
OLLAMA_TIMEOUT_SAFETY = 30             # Short timeout for safety verification
OLLAMA_TIMEOUT_DEFAULT = 120           # Standard LLM calls
```

**Session 244 change:** Stage 3 now calls `_llm_safety_check_generation()` directly with `SAFETY_MODEL` (llama-guard3:1b) using the proper S1-S13 template — no longer routes through `safety_check_kids/youth` chunks. Those chunks are now dead code (kept for reference, not called).

### user_settings.json

```json
{
  "DEFAULT_SAFETY_LEVEL": "research"
}
```

Loaded at startup by `reload_user_settings()` in `my_app/__init__.py`. Legacy `"off"` values are normalized to `"research"`.

### Settings UI

`SettingsView.vue` — Safety Level dropdown with descriptive info boxes per level. Research mode shows red warning about restricted use (see LICENSE.md §3(e)).

---

## 7. Legal Integration

The research mode restriction is codified in `LICENSE.md` §3(e):
- Requires institutional affiliation (university, Forschungseinrichtung)
- Requires documented research purpose
- Requires ethical oversight (Ethikkommission/IRB)
- Prohibits exposure of unfiltered outputs to minors
- Violation = license termination (§7) + scientific integrity impairment (§4, §14 UrhG)

---

## 8. Key Files

| File | Role |
|------|------|
| `devserver/config.py` | Safety level defaults, VLM model config, timeouts |
| `devserver/my_app/__init__.py` | Legacy "off" → "research" normalization |
| `devserver/schemas/engine/stage_orchestrator.py` | Stage 1 + Stage 3 safety logic |
| `devserver/my_app/routes/schema_pipeline_routes.py` | SAFETY-QUICK endpoint, VLM post-gen check |
| `devserver/my_app/utils/vlm_safety.py` | VLM image analysis |
| `devserver/my_app/utils/circuit_breaker.py` | Circuit breaker with Ollama self-healing |
| `devserver/my_app/utils/ollama_watchdog.py` | Automatic Ollama restart on failure |
| `devserver/schemas/chunks/safety_check_kids.json` | ~~Dead code~~ (Stage 3 no longer uses pipeline chunks, Session 244) |
| `devserver/schemas/chunks/safety_check_youth.json` | ~~Dead code~~ (Stage 3 no longer uses pipeline chunks, Session 244) |
| `devserver/schemas/data/stage1_safety_filters_*.json` | Filter term lists |
| `0_setup_ollama_watchdog.sh` | Passwordless sudo setup for self-healing |
| `public/.../views/text_transformation.vue` | Pre-generation `/safety/quick` gate in `startGeneration()` |
| `public/.../views/SettingsView.vue` | Safety level dropdown UI |
| `LICENSE.md` §3(e) | Research mode legal restrictions |

---

## 9. Historical Context

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

---

## 10. Related Documents

- `docs/reference/safety-architecture-matters.md` — Original §86a failure analysis (Session 14)
- `docs/HANDOVER_SAFETY_REFACTORING.md` — Planned endpoint separation (2026-01-26)
- `docs/ARCHITECTURE PART 01 - 4-Stage Orchestration Flow.md` — Pipeline overview
- `LICENSE.md` §3(e), §4 — Legal framework for safety system
