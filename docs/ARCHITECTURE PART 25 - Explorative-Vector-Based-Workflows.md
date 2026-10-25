# DevServer Architecture

**Part 25: Explorative Vector-Based Workflows**

---

## Overview

Explorative vector-based workflows operate directly in the embedding space of generative models rather than through conventional text prompting. Instead of describing *what* to generate, users manipulate *how* the model interprets their input by steering the mathematical relationship between multiple text encoders.

These workflows bypass Stage 2 (Prompt Interception) to preserve the raw prompt for vector-space manipulation. They represent a distinct mode of creative interaction — not prompt-guided generation, but embedding-space exploration.

**Key Characteristic:** The creative control moves from *language* (prompting) to *geometry* (vector arithmetic in latent space).

---

## Hallucinator (formerly Surrealizer)

**Display Name:** Hallucinator (renamed from Surrealizer: the effect is genuine AI hallucination, not stylistic surrealism)
**Internal IDs:** `surrealizer` (configs, pipeline, route, Vue filename — unchanged)
**Two Backends:** Diffusers (active, primary) and Legacy ComfyUI (preserved)

### The Mechanism: Token-Level CLIP-L/T5 Extrapolation

The Hallucinator exploits the fact that SD3.5 uses two fundamentally different text encoders:
- **CLIP-L** (77 tokens, 768-dim): Trained on image-text pairs. "Thinks" visually.
- **T5-XXL** (512 tokens, 4096-dim): Trained on pure text. "Thinks" linguistically.

Both encode the same prompt, but produce entirely different vector representations. The alpha slider controls extrapolation intensity. **How** the extrapolation is distributed across the token sequence depends on the **Fusion Strategy**:

#### Fusion Strategies

The core formula `(1 - α) · CLIP-L + α · T5` applies to the first 77 positions where both encoders have data. The critical question is: what happens to T5 tokens beyond position 77, where CLIP-L has no data (implicitly 0)?

**`dual_alpha`** (default):
```
fused[0:77]  = (1 - α·0.15) · CLIP-L + (α·0.15) · T5   ← gentle distortion (structural anchor)
fused[77:]   = α · T5                                     ← full extrapolation (aesthetic surprise)
```
Designed for **kontingente Ähnlichkeit**: the first 77 tokens preserve structural recognizability via CLIP-L's visual grounding, while the extended T5 tokens are fully extrapolated into unexplored vector space. The image looks related to the prompt but the execution surprises.

**`normalized`**:
```
fused[0:77]  = (1 - α) · CLIP-L + α · T5    ← full LERP
fused[77:]   = α · T5                         ← same formula (CLIP=0)
→ then: each token L2-normalized to mean T5 magnitude
```
Same extrapolation direction as `dual_alpha` but with controlled magnitude — L2 normalization prevents extreme tokens from dominating attention in the MMDiT. More uniform distortion across the image.

**`legacy`** (original behavior, preserved for comparison):
```
fused[0:77]  = (1 - α) · CLIP-L + α · T5    ← extrapolation zone
fused[77:]   = T5 (unchanged, 1×)             ← semantic anchor
```
Original ComfyUI behavior. Works well with short prompts (<77 tokens) where all tokens fall in the LERP zone. With long prompts, unmodified T5 tokens at 1× magnitude dilute the hallucination effect — at α=25, the extrapolated tokens are at 25× while the rest stays at 1×.

**Why this creates hallucinations (not just "surreal" images):**
- At α=0: Pure CLIP-L → normal image
- At α=1: Pure T5 → still fairly normal (different but coherent)
- At α=20: `(1-20)·CLIP-L + 20·T5 = -19·CLIP-L + 20·T5`
  The embedding is pushed **19× past T5's representation**, into a region of the 4096-dimensional vector space that the model has **never encountered during training**. The model must interpret these out-of-distribution vectors, producing genuine AI hallucinations.

**Alpha ranges (empirical):**
| Range | Effect |
|-------|--------|
| α = 0 | Normal image (CLIP-L only) |
| α = 1 | Pure T5 (still coherent) |
| α = 2–10 | Beginning to lose coherence |
| **α = 15–35** | **Hallucination sweet spot** |
| α > 50 | Extreme distortion, may lose all coherence |
| α > 76 | Blackout (embeddings too extreme) |
| Negative α | Extrapolation in reverse direction (see below) |

**Negative α — qualitatively different hallucinations:**

At α=-10, the formula yields `11·CLIP-L_padded + (-10)·T5`. This is not simply "less T5". The dimensional asymmetry between CLIP-L (768 real dimensions, padded to 4096 with zeros) and T5 (full 4096 dimensions) creates a fundamentally different effect:

| Dimensions | Effect at α = -10 |
|---|---|
| **0–767** (CLIP-L lives here) | 11·CLIP-L - 10·T5 → amplified visual signal with subtracted linguistic |
| **768–4095** (CLIP-L = 0 here) | 0 + (-10)·T5 = **inverted T5 vectors** |

The upper 3328 dimensions receive **negated** T5 values. In the SD3 transformer's cross-attention mechanism (MMDiT), both K and V projections are negated: `K_neg = -K_original`, `V_neg = -V_original`. After softmax, this **inverts the attention distribution** — text tokens that would normally be most important are ignored, while insignificant tokens dominate. The value vectors are also negated, producing inverted feature contributions.

**Result:** Positive α produces linguistically driven hallucinations (extrapolation past T5). Negative α produces visually driven hallucinations with actively disrupted semantics (CLIP-L amplified, T5 attention patterns inverted). Both are out-of-distribution, but from opposite directions in vector space.

### Deep Dive: Geometric Intuition

#### The Parametric Line: Interpolation vs Extrapolation

CLIP-L and T5-XXL encode the same prompt into **different points** in embedding space. Think of each token embedding as a point in high-dimensional space:

```
CLIP-L("Haus") → Point C = [0.3, -0.7, 0.1, ...]   (768 dims, zero-padded to 4096)
T5-XXL("Haus") → Point T = [0.5, -0.2, 0.8, ...]    (4096 dims)
```

The LERP formula `fused(α) = (1-α)·C + α·T` defines a **parametric line** through both points:

```
     C ──────────── T ──────────────────────────────────────── α=20
     α=0    α=0.5   α=1
     ←  interpolation  →←          extrapolation (terra incognita)              →
```

- **α ∈ [0, 1]**: Interpolation between two known points. Both CLIP-L and T5 produce sensible embeddings, so the blend is also sensible. The model has seen similar inputs during training.
- **α > 1**: Extrapolation past T5. At α=20, the embedding is pushed **19× past T5's representation** in the C→T direction. This region of vector space was **never encountered during training**.

**Why this produces hallucinations, not just noise:** The DiT decoder (SD3.5's Diffusion Transformer) was trained on embeddings within a bounded manifold. Out-of-distribution inputs trigger three effects:

1. **Feature amplification**: Whatever T5 "sees differently" from CLIP-L gets magnified. If T5 associates "Haus" more strongly with warmth/shelter than CLIP-L does, at α=20 this warmth/shelter dimension is 19× exaggerated — producing dreamlike imagery where the concept of "home" visually dominates.
2. **Feature suppression**: CLIP-L's contributions are multiplied by `(1-α) = -19`, actively negating visual literalism. The model is pushed away from photographic representations.
3. **Decoder non-linearity**: The DiT's attention mechanism and layer norms create non-linear responses to extreme inputs. Unlike a linear system (where 20× input → 20× output), the transformer produces unpredictable but internally coherent compositions — genuine hallucinations rather than simple amplification.

#### Dimension-Padding: From 768d to 4096d

CLIP-L lives in 768 dimensions, T5-XXL in 4096. You cannot add vectors of different lengths — `(3,5) + (2,7,1)` is undefined. The solution is **zero-padding**:

```python
clip_l_padded = F.pad(clip_l_embeds, (0, 4096 - 768))
# [x₁, x₂, ..., x₇₆₈, 0, 0, 0, ..., 0]
#  └── 768 real values ──┘└── 3328 zeros ──┘
```

This creates a **structural asymmetry** — the 4096 dimensions split into two zones with fundamentally different behavior:

```
Dimension:   1 ──────────── 768 │ 769 ──────────────── 4096
CLIP-L:      │  has signal       │ │  zero (no signal)        │
T5:          │  has signal       │ │  has signal              │
Fusion:      │  real competition │ │  pure T5 × α             │
```

**Zone 1 (Dim 1-768):** Both encoders contribute. The LERP formula genuinely blends visual and semantic representations.

**Zone 2 (Dim 769-4096):** CLIP-L has nothing to say (zeros). The formula reduces to `(1-α)·0 + α·T5 = α·T5` — pure T5, scaled by alpha. At α=20, T5's signal in these 3328 dimensions is **20× amplified** with no CLIP-L counterweight.

**T5's structural "home advantage":** At α=1 (pure T5), 768/4096 = **18.75%** of dimensions are blended, while **81.25%** are pure T5. T5 dominates even at theoretically "balanced" alpha. At α=20, Zone 1 becomes `-19·CLIP + 20·T5` (T5-dominant), and Zone 2 becomes `20·T5` (T5-only). The entire 4096-dimensional vector is overwhelmingly T5-driven.

**Why zero-padding works (and is the right choice):**

| Method | Approach | Drawback |
|---|---|---|
| **Projection layer** | Train a matrix W (768→4096) mapping CLIP-L into T5-space | Requires training data, doesn't exist pre-trained |
| **PCA/SVD alignment** | Align principal axes of both spaces | Complex, result not guaranteed meaningful |
| **Zero-padding** | Embed CLIP-L into the first 768 dims of a 4096-dim space | Simple, training-free, semantically correct |

Zero-padding is not a hack — it is the natural embedding of a low-dimensional subspace into a higher-dimensional space. The zeros in Dim 769-4096 correctly express: *"CLIP-L has no representation in these semantic dimensions."*

**2D analogy:** Imagine CLIP lives in 1D and T5 in 2D:

```
CLIP("Haus")  = [3]        → padded: [3, 0]
T5("Haus")    = [5, 7]

LERP at α=0.5:  [0.5·3 + 0.5·5,  0.5·0 + 0.5·7]  = [4.0, 3.5]
LERP at α=20:   [-19·3 + 20·5,   -19·0 + 20·7]    = [43, 140]
```

The second dimension (T5-exclusive) scales linearly with α and has no CLIP counterweight. At high α, T5's "extra knowledge" dominates the output.

#### Blackout Asymmetry: Why Negative α Fails at ≈-30, Positive at ≈+75

**Three phases of decreasing α:**

| Phase | Range | Formula example (α=-X) | Effect |
|---|---|---|---|
| CLIP-dominant | α ≈ -1.5 to 0 | 2.5·CLIP - 1.5·T5 | Flatter, more literal — like a stock photo |
| Losing coherence | α ≈ -4 to -18 | 19·CLIP - 18·T5 | Embedding magnitude ≈ 19× normal |
| Blackout | α < -30 | 31·CLIP - 30·T5 | Magnitude ≈ 31× normal → system collapse |

**Why extreme magnitudes cause blackout:**

1. **Softmax saturation:** The DiT's cross-attention computes `softmax(Q·K^T / √d)`. When K vectors are 30× normal magnitude, the dot products become enormous. Softmax of `[100, 1, 2]` ≈ `[1.0, 0.0, 0.0]` — one token captures all attention, the rest are ignored. The model effectively "sees" only a single token.

2. **Float16 numerical limits:** Half-precision floats range ±65504. At 30× normal magnitude, intermediate products in matrix multiplications can overflow to `inf` or produce `NaN`, corrupting the entire computation.

3. **Latent-space divergence:** The predicted noise values become so large that the Euler sampler diverges after the first step — each denoising step amplifies the error instead of reducing it.

4. **VAE decoder saturation:** The VAE expects latent values in a learned range. Extreme values are clipped to the output range (0-255), producing a uniform color — typically black or gray.

**Why the asymmetry? Why -30 but +75?**

The root cause is the zero-padding in Dim 769-4096:

| Direction | Dim 1-768 | Dim 769-4096 | Total OOD severity |
|---|---|---|---|
| **α = +20** | -19·CLIP + 20·T5 (magnitude ~20×) | +20·T5 (scaled, same sign) | Magnitude only |
| **α = -20** | 21·CLIP - 20·T5 (magnitude ~21×) | **-20·T5** (negated sign!) | Magnitude **+ sign inversion** |

At positive α, Dim 769-4096 receives `α·T5` — the T5 values are amplified but maintain their original sign. The DiT has seen positive-ish values in these dimensions during training.

At negative α, Dim 769-4096 receives `α·T5` where α<0 — the T5 values are **negated**. The DiT has never seen negative values where it always learned positive patterns. This is **doubly out-of-distribution**: wrong magnitude AND wrong sign. The attention mechanism (MMDiT) receives inverted K and V projections, producing fundamentally broken attention patterns.

This sign-inversion effect in 81.25% of dimensions (3328 out of 4096) causes the negative direction to reach blackout roughly **2.5× faster** than the positive direction.

---

### Implementation

#### Backend 1: Diffusers (Primary)

**File:** `gpu_service/services/diffusers_backend.py` (primary), `devserver/my_app/services/diffusers_backend.py` (in-process fallback)
**Method:** `DiffusersImageGenerator.generate_image_with_fusion(fusion_strategy=...)`

Uses individual SD3 pipeline text encoders directly (bypasses `encode_prompt()`):

```python
def _fuse_prompt(clip_text: str, t5_text: str):
    # Encoding (shared across all strategies):
    clip_l_embeds, clip_l_pooled = pipe._get_clip_prompt_embeds(clip_text, clip_model_index=0)
    clip_padded = F.pad(clip_l_embeds, (0, 4096 - clip_l_embeds.shape[-1]))  # (1, 77, 4096)
    pooled = F.pad(clip_l_pooled, (0, 1280))   # (1, 2048): 768d real + 1280d zeros
    t5_embeds = pipe._get_t5_prompt_embeds(t5_text, max_sequence_length=512)

    if fusion_strategy == "dual_alpha":
        alpha_core = alpha_factor * 0.15  # gentle on core
        fused_core = (1 - alpha_core) * clip_padded + alpha_core * t5[:77]
        fused_ext = alpha_factor * t5[77:]  # full extrapolation
        fused = cat([fused_core, fused_ext])

    elif fusion_strategy == "normalized":
        clip_full = F.pad(clip_padded, (0, 0, 0, t5_len - 77))  # zeros beyond 77
        fused = (1 - alpha_factor) * clip_full + alpha_factor * t5_embeds
        ref_norm = t5_embeds.norm(dim=-1, keepdim=True).mean()
        fused = fused * (ref_norm / fused.norm(dim=-1, keepdim=True).clamp(min=1e-8))

    else:  # legacy
        fused_part = (1 - alpha_factor) * clip_padded + alpha_factor * t5[:77]
        fused = cat([fused_part, t5[77:]])  # append unchanged

    return fused, pooled
```

**Key design decisions (Diffusers backend):**

1. **CLIP-L only — no CLIP-G anywhere:** Matches the original ComfyUI workflow which loads only `clip_l.safetensors`. CLIP-G is absent from both fused tokens AND pooled output. Real CLIP-G pooled would give the DiT visual anchoring that fights extrapolation.
2. **Output shape (1, 512, 4096) instead of standard (1, 589, 4096):** The SD3 transformer uses flexible attention — any sequence length works. 512 = 77 fused + 435 extended tokens.
3. **Private method `_get_clip_prompt_embeds`:** Stable in diffusers v0.36.0, protected by `hasattr` guard.
4. **Negative prompt fused with same alpha and strategy:** Matches ComfyUI workflow (both fusion nodes receive the same alpha). All 4 embedding tensors passed to pipeline, fully bypassing `encode_prompt()`.
5. **Why not `encode_prompt()` with different prompt strings?** Because `encode_prompt()` returns **joint embeddings** (CLIP-L + CLIP-G + T5 concatenated). Blending two joint embeddings destroys the CLIP signal instead of extrapolating between encoder spaces. See "Failed approach" below.
6. **Three strategies, one formula:** All strategies share the same encoding and pooled output. Only the fusion math differs. The `fusion_strategy` parameter flows: Vue → legacy endpoint → pipeline executor (custom_placeholders) → backend_router → GPU service. Default is `dual_alpha` everywhere (backend_router fallback, chunk config, Vue ref).
7. **dual_alpha core factor (0.15):** Empirical choice — at α=25 this gives core_α≈3.75, enough to gently shift toward T5 without destroying CLIP-L's visual anchor. The 0.15 multiplier is hardcoded, not user-configurable, to keep the UI simple (one slider, one strategy selector).

**Failed approach (pre-fix):**
```python
# BROKEN: blends joint SD3 embeddings
clip_embeds = pipe.encode_prompt(prompt, prompt, "", 512)   # CLIP active, T5 empty
t5_embeds = pipe.encode_prompt("", "", prompt, 512)         # CLIP empty, T5 active
blended = (1 - α) * clip_embeds + α * t5_embeds

# At α=20, the CLIP region (tokens 0-76) becomes:
#   -19 * CLIP(prompt) + 20 * CLIP("")
# This DESTROYS the CLIP signal instead of extrapolating toward T5.
# Result: α=10 already extreme, α=25 white/blank image.
```

#### Backend 2: Legacy ComfyUI (Preserved)

**Key Nodes (from `chunks/legacy_surrealization.json`):**
- **Node 43:** `ai4artsed_text_prompt` — User prompt input
- **Node 50:** `set t5-Influence` — Alpha factor control (-75 to +75)
- **Node 68:** Prompt optimization for T5 encoder (250 words, rich paragraph, outputs `#a=XX`)
- **Node 69:** Prompt optimization for CLIP-L (50 words, token-reordered)
- **Node 70:** Auto-alpha extraction (parses `#a=XX` from T5-optimized prompt)
- **Nodes 51/52:** `ai4artsed_t5_clip_fusion` — Token-level LERP + append

**Note:** The ComfyUI workflow uses **two different prompts** (CLIP-optimized and T5-optimized) and **auto-alpha calculation**. The Diffusers backend currently uses the same prompt for both encoders and user-controlled alpha.

#### Alpha Factor Control

**Range:** -75 to +75, default 0 (normal). Sweet spot: 15–35.

**Frontend (surrealizer.vue):**
```typescript
const alphaFaktor = ref<number>(0)  // Slider default

// Slider UI:
// - 5 labels: "extrem", "invers", "normal", "halluziniert", "extrem"
// - Color gradient: purple → blue → pink
// - Value display shows: α = <value>

// API call (ComfyUI since 14.09.2026; the Diffusers twin answers to
// 'surrealization_diffusers' until stage 8 of the move):
const response = await axios.post('/api/schema/pipeline/direct', {
  prompt: inputText.value,
  output_config: 'surrealization',
  alpha_factor: mappedAlpha.value,  // Raw alpha value, no mapping
  seed: currentSeed.value
})
```

**Backend routing (backend_router.py:1795-1808):**
- Detects `alpha_factor` + `fusion_mode: 't5_clip_alpha'` in diffusers_config
- Routes to `backend.generate_image_with_fusion()` instead of `generate_image()`

#### Seed Logic (the seed automatic)

**Purpose:** experiment on the same noise, and ask for a variation by pressing again.

**Where:** `composables/useSeedAutomatic.ts`, used by `views/surrealizer.vue` since 2026-10-03, and the same day by the other instruments of the Latent Lab whose seed field is not fixed by design (consumers and exceptions are listed in `docs/ELEMENT_STRUCTURE_REGISTRY.md`). It is the platform's rule (PART 01, section 3) for an instrument with a seed field (`components/SeedControl.vue`):

- an input changed since the picture on the surface was made (prompt, the three factors, the layout of the T5 block, the pooled vector, negative prompt, CFG) → **same seed**
- nothing changed → **new seed** (drawn below 2^31)
- a seed typed into the field → **that seed**, and the automatic goes on from it
- tick „Random variation" → **new seed on every run**
- first run → the number in the field (123456789 unless typed)

The seed that goes out is written into the field. The yardstick is the run whose picture stands on the surface: one that arrived, or one laid back from the run strip or the favourites. A failed or blocked run is not: pressing again with nothing changed sends its seed again, and a change takes the picture's seed. A number counts as typed when it is not the one the automatic last put into the field. The yardstick is kept in sessionStorage (`lat_lab_ef_seed_yardstick`), so a reload or a change of tab does not forget it; an instance taken down by a change of tab writes nothing more.

Until 2026-10-03 the page sent the field's number unless the tick was set, and under the tick it kept the seed whenever an input changed.

**Testing:** `composables/__tests__/useSeedAutomatic.spec.ts`. The seed is recorded with each picture and stands on the back of its card.

---

## File Locations

### Hallucinator
- **Pipeline:** `devserver/schemas/pipelines/surrealizer.json`
- **Interception config:** `devserver/schemas/configs/interception/surrealizer.json`
- **Output config (ComfyUI, the surfaces' config since 14.09.2026):** `devserver/schemas/configs/output/surrealization.json`
- **Chunk (ComfyUI):** `devserver/schemas/chunks/output_image_surrealizer_comfyui.py`; the fusion node `AI4ArtsEdSD3Fusion` in `comfyui_nodes/ai4artsed_sd3_conditioning.py`
- **Output config (Diffusers):** `devserver/schemas/configs/output/surrealization_diffusers.json`
- **Output config (Legacy):** `devserver/schemas/configs/output/surrealization_legacy.json`
- **Chunk (Diffusers):** `devserver/schemas/chunks/output_image_surrealizer_diffusers.py`
- **Chunk (Legacy):** `devserver/schemas/chunks/legacy_surrealization.json`
- **GPU Service backend:** `gpu_service/services/diffusers_backend.py` (generate_image_with_fusion, five strategies plus the research options after '#')
- **GPU Service route:** `gpu_service/routes/diffusers_routes.py` (/api/diffusers/generate/fusion)
- **DevServer client:** `devserver/my_app/services/diffusers_client.py` (HTTP wrapper)
- **DevServer fallback:** `devserver/my_app/services/diffusers_backend.py` (in-process, mirrors GPU service)
- **Backend router:** `devserver/schemas/engine/backend_router.py` (fusion_strategy dispatch)
- **Frontend:** `public/ai4artsed-frontend/src/views/surrealizer.vue`
- **ComfyUI custom node (reference):** `~/ai/SwarmUI/dlbackend/ComfyUI/custom_nodes/ai4artsed_comfyui/ai4artsed_t5_clip_fusion.py`

---

## Historical Context

### Architecture Failure of the Original ComfyUI Approach
The original ComfyUI approach had severe architectural problems:
- Stage 3 Translation Bug: German text reached English-only T5 model
- Placeholder Population Failure: `{{T5_PROMPT}}` and `{{CLIP_PROMPT}}` never replaced
- JSON Parsing Failures: LLMs added meta-commentary despite instructions

### Failed Slider Attempt
A first attempt to add the alpha slider failed because the convention-based routing was not followed (see `ARCHITECTURE PART 22`, Historical Context).

### Diffusers Migration
Successfully migrated from ComfyUI to Diffusers with token-level fusion.
See: `docs/DEVELOPMENT_DECISIONS.md`

---

## References

- `ARCHITECTURE PART 22` — Legacy Workflow Architecture (routing, conventions, migration patterns)
- `ARCHITECTURE PART 08` — Backend Routing
- `ARCHITECTURE PART 12` — Frontend Architecture
- `docs/DEVELOPMENT_DECISIONS.md` — Hallucinator Diffusers-backend decisions

---

**Document Status:** Active (2026-02-08)
**Maintainer:** AI4ArtsEd Development Team
**Last Updated:** Hallucinator Diffusers backend, geometric deep-dive
