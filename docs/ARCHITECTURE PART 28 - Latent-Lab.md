# DevServer Architecture

**Part 28: Latent Lab — Deconstructive Model Introspection**

---

## Overview

The Latent Lab (`/latent-lab`) consolidates all deconstructive, vector-space-based operations into a single tab-based research mode. Unlike the productive generation modes (Text/Image/Music Transformation), the Latent Lab does not create finished artworks — it exposes the internal mechanics of generative AI models for exploration and education.

**Key Principle:** "What happens inside the model?" — every Latent Lab tool makes invisible model internals visible.

**Safety Level:** Reachable at every level; the lock decided on 2026-02-11 (kids and youth locked, a compliance dialog for research) was never wired, and its unwired code is gone (see Part 28a below). What checks a run is the instrument's own route (stage 1 and stage 3 of the direct route).

---

## Instrument versions

Twenty-two instruments in five categories, plus the overview standing over them,
in the order the left column renders them (`GROUPS` in `views/latent_lab.vue`).
**A version mark is set where a section of this documentation says what the
version IS** — what it fixed, what it added, what it deliberately does not
offer. Five instruments carry one today. The rest are in service without a mark,
which is a statement about the documentation and not about them.

The list itself is behind the lab: Mean Images was added on 2026-09-07 and the
three instruments of the Prompt Interception Lab, the LoRA Explorer and the
Tokenizer have no row at all. Whoever writes a section for one of them adds its
row in the same change.

| Instrument | Category | Mark | Described in |
|---|---|---|---|
| Overview | (above the categories) | — | nowhere; `flow_logic.vue` |
| AI Model Comparison | Comparison Modes | — | Part 33 §2 |
| AI Cultural Understanding | Comparison Modes | — | nowhere; came from the Image Lab 2026-08-23, where it was Default Census |
| AI Image Understanding | Comparison Modes | — | nowhere |
| AI Language Understanding | Comparison Modes | — | Part 33 §1 |
| AI Voice Comparison | Comparison Modes | **V 1.01** (2026-08-27) | Part 33 §4 |
| Denoising Archaeology | Image Lab | — (Implemented) | Part 28 §3 |
| Mean Images | Image Lab | **V 1.0** (2026-09-07) | Part 28 §5 |
| Attention Cartography | Image Lab | **V 1.0** (VRAM-gated, ≥40 GB) | Part 28, Implemented Tools §1 |
| Encoder Fusion | Image Lab | — (Implemented) | Part 28, "Encoder Fusion — mechanism correction" |
| Dimension Explorer (built as Feature Probing) | Image Lab | **V 1.1** (2026-09-28, VRAM-gated ≥40 GB) | Part 28, Implemented Tools §2 |
| Concept Algebra | Image Lab | — (Implemented) | Part 28 §4 |
| Concurrent Conditioning | Image Lab | — (Implemented) | image lab table only |
| Fusion Workbench | Image Lab | — (Implemented) | image lab table only |
| Bias Archaeology 1 | Latent Text Lab | — (Implemented) | text lab table only |
| Bias Archaeology 2 | Latent Text Lab | — (Implemented) | text lab table only |
| Representation Engineering | Latent Text Lab | **V 1.1** (2026-08-26) | Part 28, Tab 1 |
| System Prompts | Latent Text Lab | — (Implemented) | text lab table only |
| Latent Audio Synth | Crossmodal Lab | — | nowhere |
| MMAudio | Crossmodal Lab | — | nowhere |
| ImageBind Guidance | Crossmodal Lab | — | nowhere |
| Re-enactment | Crossmodal Lab | — | nowhere |
| SD 3.5 large | LoRA Training | — | nowhere |

"Nowhere" means: not in this document and not in Part 33 — eight rows, seven
instruments and the overview. What they are is written on their own surfaces and, since 2026-08-19, in
`devserver/my_app/knowledge/platform_items.json`, which Help reads. Whoever
writes the section for one of them sets its first mark in the same change.

Three things this list makes visible and does not fix.

- `latent_lab/arcimboldo_mosaic.vue` stands in the repository wired to nothing;
  it is not one of the twenty-two and has no row.
- **Part 33 §3 still describes Temperature Comparison**, a mode that has been
  removed. The section has outlived its surface, while the two modes standing
  there instead — AI Image Understanding and AI Cultural Understanding — have
  none.
- **Tab 2 and Tab 3 below describe designs the two Bias Archaeology instruments
  no longer match**: CKA between two loaded models, and suppressing token
  categories by preset. What runs today is the BBQ set of undecidable questions
  and a swapped pronoun. That is why neither row points at them.

---

## Scientific Foundation

The Latent Lab tools are grounded in six lines of research:

### Vector Arithmetic in Embedding Spaces
- **Mikolov, T. et al. (2013).** "Distributed Representations of Words and Phrases and their Compositionality." NeurIPS.
  DOI: [10.48550/arXiv.1310.4546](https://doi.org/10.48550/arXiv.1310.4546)
  — The foundational paper establishing vector arithmetic for word embeddings ("King − Man + Woman = Queen"). Demonstrates that learned embedding spaces encode semantic relationships as linear directions, enabling algebraic concept manipulation. **Basis for: Concept Algebra tab.**

### Representation Engineering
- **Zou, A. et al. (2023).** "Representation Engineering: A Top-Down Approach to AI Transparency." arXiv.
  DOI: [10.48550/arXiv.2310.01405](https://doi.org/10.48550/arXiv.2310.01405)
  — Reading and steering model behavior through manipulation of internal representations. Establishes that neural network activations encode interpretable, manipulable concepts. **Basis for: Feature Probing tab (dimension transfer).**

### Probing / Feature Attribution
- **Belinkov, Y. (2022).** "Probing Classifiers: Promises, Shortcomings, and Advances." Computational Linguistics (MIT Press).
  DOI: [10.1162/coli_a_00422](https://doi.org/10.1162/coli_a_00422)
  — Systematic survey of probing methods for understanding what information neural representations encode. **Basis for: Feature Probing tab (analysis phase).**

- **Bau, D. et al. (2020).** "Rewriting a Deep Generative Model." ECCV 2020 (Springer).
  DOI: [10.1007/978-3-030-58452-8_21](https://doi.org/10.1007/978-3-030-58452-8_21)
  — Targeted rewriting of individual features in generative models. Shows that single directions in representation space control specific visual concepts. **Basis for: Feature Probing tab (targeted dimension transfer).**

### Attention in Diffusion Models
- **Hertz, A. et al. (2022).** "Prompt-to-Prompt Image Editing with Cross Attention Control." ICLR 2023.
  DOI: [10.48550/arXiv.2208.01626](https://doi.org/10.48550/arXiv.2208.01626)
  — The key paper for attention manipulation in diffusion models. Shows that cross-attention layers control the spatial relationship between prompt tokens and image regions. **Basis for: Attention Cartography tab.**

### Latent Space Semantics in Diffusion
- **Kwon, M. et al. (2023).** "Diffusion Models Already Have a Semantic Latent Space." ICLR 2023.
  DOI: [10.48550/arXiv.2210.10960](https://doi.org/10.48550/arXiv.2210.10960)
  — Demonstrates that intermediate activations (h-space) in diffusion models carry semantic meaning. Early steps establish composition, middle steps form semantics, late steps refine detail. **Basis for: Denoising Archaeology tab.**

### Compositional Concept Algebra in Diffusion
- **Liu, N. et al. (2022).** "Compositional Visual Generation with Composable Diffusion Models." ECCV 2022 (Springer).
  DOI: [10.1007/978-3-031-19803-8_12](https://doi.org/10.1007/978-3-031-19803-8_12)
  — Mathematical composition of concepts in diffusion models. Demonstrates that score functions (and by extension, conditioning embeddings) can be algebraically combined. **Basis for: Concept Algebra tab.**

### Mapping: Paper → Latent Lab Tab

| Paper | Tab | Operation |
|-------|-----|-----------|
| Mikolov 2013 | Concept Algebra | A - B + C embedding arithmetic |
| Liu 2022 | Concept Algebra | Composable concept diffusion |
| Zou 2023 | Feature Probing | Representation reading + steering |
| Belinkov 2022 | Feature Probing | Probing what embeddings encode |
| Bau 2020 | Feature Probing | Rewriting specific features |
| Hertz 2022 | Attention Cartography | Cross-attention map analysis |
| Kwon 2023 | Denoising Archaeology | Semantic phases in denoising |

---

## Architecture

### Frontend: Tab Container

**File:** `public/ai4artsed-frontend/src/views/latent_lab.vue`

The Latent Lab is a lightweight shell that renders child components based on the chosen instrument:

The Latent Lab shell has three sub-labs (`image`, `textlab`, `crossmodal`), which since 2026-08-18
are the three group titles of the left column rather than a bar of their own. A fourth group stands
above them: the **Comparison Modes**, which moved into the lab as its first category and are
documented in `ARCHITECTURE PART 33 - Compare Hub.md`, Voices among them (**V 1.01**, 2026-08-27).
Their ids keep the `compare.` stem wherever the platform addresses them; only the parent moved.
The image lab wires seven instruments:

| Instrument | Component | Status | Purpose |
|-----|-----------|--------|---------|
| Denoising Archaeology | `latent_lab/denoising_archaeology.vue` | Implemented | Step-by-step denoising visualisation |
| Attention Cartography | `latent_lab/attention_cartography.vue` | **V 1.0** (VRAM-gated, ≥40 GB) | Token→Region attention heatmaps |
| Encoder Fusion | `surrealizer.vue` | Implemented | **CLIP-L inversion**, not a neutral mix (see below) |
| Dimension Explorer | `latent_lab/feature_probing.vue` | **V 1.1** (VRAM-gated, ≥40 GB) | Embedding dimension analysis + transfer |
| Concept Algebra | `latent_lab/concept_algebra.vue` | Implemented | Vector arithmetic (A - B + C) |
| Concurrent Conditioning | `latent_lab/composable_diffusion.vue` | Implemented | Per-concept score composition |
| Fusion Workbench | `latent_lab/fusion_workbench.vue` | Implemented | Three-axis parameter sweep |
| *Arcimboldo Mosaic* | `latent_lab/arcimboldo_mosaic.vue` | **Orphaned** — not wired | Attention-segmented photo mosaic |

**Encoder Fusion — mechanism correction.** The label “cross-encoder interpolation/mix” used in
earlier revisions of this document and in the whitepaper is **superseded**. CLIP-L and T5 are
effectively orthogonal in the shared dimensions (cos ≈ 0.03), so no neutral blend of two readings
exists; the operation is a **CLIP-L inversion** (the core turns anti-parallel). The red
deconstruction family hangs on the −CLIP component, not on turning toward T5.

Active tab persists in `localStorage`.

#### Encoder Fusion — the first instrument laid out under the band (2026-08-18)

Encoder Fusion is the first Latent Lab instrument rebuilt for the column frame. The band is the run,
in the form the flow gives it (`views/x2x_flow.vue`), down to its names and its symbols: the boxes
carry the flow's labels and the flow's glyphs.

| Node | What it carries |
|---|---|
| `x2xFlow.nCreate` | the six media glyphs (`MediumGlyph`) with `image` lit, and the model family under them. No click: SD3.5 makes images, so the choice the flow offers does not exist here |
| — | the triangle alone. The middle node **is** the run, so it carries no label and no button chrome |
| `x2xFlow.nOutput` | the produced image, filling the node (`.out-media`, as in the flow) |

Under the band stand **two** surfaces, not three columns. Columns that form one
functional unit are merged into one surface.

| Surface | Under | What it carries |
|---|---|---|
| the text | node one | `MediaInputBox chrome="bare" actions-above` — the symbols in their own row above the field, so the text has the whole column. Under ~75 estimated tokens a warning points at the perspectives |
| the setting | nodes two and three | the α axis across the full width, α itself, the field map (`SayableFieldMap chrome="bare"`) taking the height that is left, the two coefficients and the encoders' capacities as lines, and the three strategies (`ChipSelect`) beside the advanced fold |

The widths come from what the things need, not from the band's arithmetic: a prompt is a paragraph
and wants 45–75 characters to the line (≥ 360 px of text); the five marks want room for their
longest word (≈ 370 px); the map's labels collide under ≈ 350 px. At 1328 px of work area that is 429 / 878 (`1fr 2.0467fr`).

The band above them does **not** span the surfaces. Its geometry is the flow's, verbatim — `W = 1060`,
`H = 150`, `create {110,20,300,110}`, `gen {520,20,160,110}`, `output {790,20,160,110}`: left margin,
both gaps and right margin are the same 110, and the three nodes take 620 of 1060. The boxes in the
flow do not fill the column width, and the band matches that geometry exactly. The WORK surfaces carry **no**
`--flow-map-w`: as a page head that cap held this instrument at 1000 px on every screen — 111 px of
text width at any window size. The BAND keeps it: the sizes, the height above all, are part of the
template and are binding. The cap is what fixes the scale the nodes are drawn at
(1000 / 1060 = 0.9434, so a node is 104 px high wherever a band stands); without it the scale rides
the window and the same node comes out 196 px high at 1888 px. Measured at a 1600 px window,
`/x2x-flow` and `/surrealizer` identical: stage 1000 × 142, nodes 283 × 104 / 151 × 104 / 151 × 104
at x = 104 / 491 / 745.

Under both surfaces sits `OutputDrawer` — every finished run keeps a card of its own, so two settings
can be laid side by side. Since 2026-08-19 that card is the platform's (`FlowCard` with
`MediaCardFront` / `MediaCardBack`), the same one the flow throws its output into and Together and
Contesting carry, because the strip differs from those surfaces only in where a card stands. Its bar
holds the comparison key — α and strategy — and holding the card turns it to the record: prompt,
model sheet, config, seed, time. That is what the instrument teaches: the effect becomes
perceptible only through arrangement, in series and contrasts. The image therefore stands **once**: in the third node, and as a run in the
drawer. With the result column went its `MediaOutputBox`; it is back on every run's card since
2026-08-19, and with it favouriting, forwarding, download and print. Image analysis is on the card too, and needs no place of
its own on the surface any more: the button only dispatches
(`analysisEventStore.requestReflection`), the looking happens in the companion, and the companion can
take up a run by itself (`view_run` / `view_favorite`, `routes/chat_routes.py`). The five buttons lie OVER the picture
(`.action-toolbar` is absolutely placed, opacity 0.1, and comes up at 0.8 on hover or keyboard focus;
on a device without hover it stands at 0.8 permanently, `MediaOutputBox.vue`), so the card needs no
extra height for them.

See `Instrumenten-Flaechen im Latent Lab` in `docs/ELEMENT_STRUCTURE_REGISTRY.md` (the entry was
called `Instrumenten-Flaechen unter dem Band` until 2026-08-22, when the last of the four gave up its
band), and read the count of rebuilt instruments there rather than here — it changes with every
rebuild. The instruments still in their old form do not sit in ONE 900 px measure but in several:
`views/latent_lab/image_lab.vue`, `views/latent_lab/latent_text_lab.vue` and
`views/latent_lab/crossmodal_lab.vue` each carry their own, and Re-enactment (`views/cover_band.vue`)
carries none at all. Each leaves its own wrapper as it is rebuilt.

**The automatic T5 expansion is gone.** The T5 expansion rewrites the prompt destructively. The switch
“Prompt für T5 erweitern”, and with it the `expand_prompt` → `t5_prompt` path in
`schema_pipeline_routes.py`, are removed; what lengthens a text now comes from the interception
perspectives in the input box, visibly and in the field. `services/t5_expansion.py` stays — the
Fusion Workbench asks for the expansion itself (`/api/fusion_workbench/expand_t5`), where it is the
object of study rather than a second author.

### Backend: Diffusers-Based Introspection (until September 2026)

Until September 2026 all Latent Lab operations used the Diffusers backend (`diffusers_backend.py`) for direct tensor access; since the move to ComfyUI (below) the instruments run as ComfyUI graphs on the platform's own nodes (`comfyui_nodes/`). The pipeline definition (`latent_lab.json`) is type `passthrough` with `skip_stage2: true` — preserving the raw prompt for model analysis.

**Why Diffusers, not ComfyUI:**

| Aspect | ComfyUI | Diffusers |
|--------|---------|-----------|
| Text encoders | Accessed via workflow nodes, outputs opaque | Direct method calls (`_get_clip_prompt_embeds()`) |
| Attention maps | Not exposed between nodes | Custom processors (`AttentionCaptureProcessor`) hot-swappable at runtime |
| Embedding manipulation | Requires custom nodes for each operation | Standard PyTorch tensor ops |
| Denoising introspection | Hidden inside KSampler node | Programmable step-by-step loop |

ComfyUI is ideal for node-graph-based generation workflows. Diffusers provides the programmatic access required for model introspection.

**Since the move to ComfyUI (September 2026)** the same access goes through this platform's own nodes (`comfyui_nodes/`, see its README): the encoders per part (`AI4ArtsEdSD3Encode`), the attention read beside ComfyUI's own (`AI4ArtsEdAttentionCapture`), the working latent per step (`AI4ArtsEdDenoisingArchaeology`), and the text context of the joint blocks per block and step window (`AI4ArtsEdSD3Context*`). The Fusion Workbench's scheduled fusion, Decomposition's cells, the position probe and the delayed kick-in of the research scripts run on the last family, their graphs assembled in `devserver/my_app/services/latent_lab_context_graphs.py`; the research scripts under `devserver/testfiles/` post to `/api/fusion_workbench/<instrument>` on the DevServer, where they posted to the GPU service before. The table above records why the Diffusers twins were built.

**The text side (stage 5 of the move)** began with the three routes that read a vocabulary file and no model: the cut and the catalogue of the Tokenizer instrument and the window count a run asks before it starts. The node package answers them on ComfyUI's own HTTP server, off the queue (`comfyui_nodes/ai4artsed_comfyui/_tokenizer_routes.py`); the catalogue is the DevServer's table `devserver/config/tokenizer_catalogue.json`; the window count is measured with the tokenizer ComfyUI cuts the prompt with. The instruments that run a model (Bias Archaeology, the coreference test, Representation Engineering) still go through `text_client.py` to the GPU service.

---

## Implemented Tools

### 1. Attention Cartography

**Question:** "Which prompt tokens influence which image regions?"

**Backend:** `DiffusersImageGenerator.generate_image_with_attention()` (diffusers_backend.py:560-752)

**Mechanism:**
1. Custom `AttentionCaptureProcessor` replaces SD3.5's efficient SDPA with manual softmax attention
2. During generation, captures text→image cross-attention submatrix `[image_tokens, text_tokens]` at configurable layers (default: 3, 9, 17) and timesteps
3. Attention maps averaged across heads, truncated to actual word token columns
4. Pre-tokenizes prompt with CLIP-L tokenizer to group sub-tokens into words

**Key Files:**
- `gpu_service/services/attention_processors_sd3.py` — `AttentionMapStore`, `AttentionCaptureProcessor`, `install_attention_capture()`, `restore_attention_processors()`
- `devserver/schemas/configs/output/attention_cartography_diffusers.json`
- **ComfyUI (since 2026-09-14):** `comfyui_nodes/ai4artsed_attention_capture.py` (`AI4ArtsEdAttentionCapture` patches the chosen joint blocks with a block replacement whose `optimized_attention_override` reads softmax(QK^T/sqrt(d)) beside ComfyUI's own attention; `AI4ArtsEdAttentionMaps` writes maps and tokens to a JSON file after the sampler), `devserver/schemas/chunks/output_image_attention_cartography_comfyui.py`, `devserver/schemas/configs/output/attention_cartography.json`. The twin's record, and beside it `text_positions` (the length of the joint text sequence, which the chunk strips); ComfyUI's joint sequence is text first, the readout stores [image, text] as before, sums over batch entries and heads in float32 and divides by their count.

**Frontend:** Interactive canvas overlay with token selection chips, timestep slider, layer toggle, heatmap opacity control.

**Data Volume Optimization:** Token column truncation + head averaging reduces attention data from ~300MB to ~10MB per generation.

### 2. Dimension Explorer (built as Feature Probing) — **V 1.1**, 2026-09-28

**Question:** "Which embedding dimensions encode which semantic differences?"

**What V 1.1 is.** The instrument is called Dimension
Explorer since 2026-09-27; the file, the config ID, the tab key, the i18n keys
and the source stored with runs and favourites keep `feature_probing`, and the
old address leads to the new one. Both runs start from the frame's bar: ▶ 1
measures and makes prompt A's picture, ▶ 2 carries the chosen ranks of B into A.
Three pictures stand at one seed, left to right: prompt A, A with B's
dimensions, prompt B. ▶ 2 makes prompt B's picture first when none stands for
the current prompt B, steps, CFG and negative prompt, then the mix; after that
it makes only the mix. Prompt B's picture is B's own conditioning (the probe
without `transfer_dims`, B sent as `prompt`), so it passes Stage 1 as a prompt
of its own. A blocked run of prompt B stops the mix, which carries B's
dimensions, and keeps ▶ 2 dimmed until prompt B or a setting changes. ▶ 1
measures on all four encoder choices at once: four more `AI4ArtsEdSD3Probe`
nodes read the same two encodes and feed nothing, and the chunk returns their
lists as `by_encoder`. A change of encoder switches the list and starts no run;
▶ 2 writes into the encoder the field shows. The rank range opens at 13–1156
and stays as set across new prompts, new runs and a reload (sessionStorage);
a range reaching past a list (CLIP-L 768, CLIP-G 1280) ends with it.

**Open at V 1.1.** The Diffusers twin answers for the chosen encoder only; on
that path a change of encoder needs ▶ 1 again.

**Backend:** ComfyUI, `AI4ArtsEdSD3Probe` in `comfyui_nodes/ai4artsed_sd3_conditioning.py`, driven by `devserver/schemas/chunks/output_image_feature_probing_comfyui.py`. The Diffusers twin `DiffusersImageGenerator.generate_image_with_probing()` (`gpu_service/services/diffusers_backend.py`) stands until the demolition stage of the move to ComfyUI.

**Bilder und Zahlen der beiden Wege gehören nicht in einen Vergleich.** Vier
Unterschiede stehen zwischen ihnen, jeder für sich klein und alle vier bekannt:
das Fenster (ComfyUI misst über die Positionen, die der Prompt selbst füllt, der
GPU-Dienst schneidet CLIP bei 77 und füllt T5 auf 512 auf), der leere
Negativprompt (Nullen gegen die Kodierung des leeren Strings), der pooled-Vektor
von CLIP-L (unprojiziert gegen projiziert) und der Sampler-Fahrplan
(euler/normal gegen `FlowMatchEulerDiscreteScheduler`). Bei gleichem Startwert
kommen deshalb zwei verschiedene Bilder heraus, und die Balken der
Dimensionsdifferenzen ruhen auf verschieden vielen Positionen.

**Two-Phase Architecture:**

**Phase 1 — Analysis** (`transfer_dims=None`):
1. Encode prompts A and B with selected text encoder (CLIP-L/CLIP-G/T5-XXL/All);
   on the ComfyUI path the measurement runs on all four at once (`by_encoder`)
2. Compute per-dimension absolute difference (averaged across token positions)
3. Sort all dimensions by magnitude (no arbitrary cutoff)
4. Generate reference image with embed_a
5. Return image + probing analysis (diff_per_dim, top_dims, L2 distance)

**Phase 2 — Transfer** (`transfer_dims` provided):
1. Copy selected dimensions from embed_b into embed_a
2. Compose full SD3.5 embedding for modified generation
3. Generate image with same seed for side-by-side comparison

**Key Files:**
- `gpu_service/services/embedding_analyzer.py` — `compute_dimension_differences()`, `apply_dimension_transfer()`
  (die gleichnamige Datei unter `devserver/my_app/services/` ist stillgelegt und hat keinen Importeur)
- `devserver/schemas/configs/output/feature_probing.json` (ComfyUI, what the surface calls)
- `devserver/schemas/configs/output/feature_probing_diffusers.json` (the twin)

**Frontend:** Two prompts, encoder chips, the rank list of dimensions with up to four rank ranges, three pictures at one seed (A, the mix, B).

---

## Relationship to Hallucinator

The Hallucinator (`/surrealizer`) is architecturally related but remains a **separate feature**:

| Aspect | Hallucinator | Latent Lab |
|--------|-------------|------------|
| Purpose | Creative tool (produce surreal images) | Research tool (understand model internals) |
| User experience | Single slider (alpha), quick iteration | Multi-step analysis, data visualization |
| Output | Finished images for artistic use | Visualizations, charts, heatmaps |
| Route | `/surrealizer` (standalone) | `/latent-lab` (tabbed container) |

Both bypass Stage 2 and, since the move to ComfyUI (September 2026), run as ComfyUI graphs on the same nodes (`comfyui_nodes/ai4artsed_sd3_conditioning.py`). Future consolidation is planned but not prioritized.

See: `ARCHITECTURE PART 25 — Explorative Vector-Based Workflows` for Hallucinator technical details.

---

## Part 28a: Research-Level Gating (never activated, removed 2026-10-10)

Until 2026-10-10 this section described a lock on the Canvas and the Latent Lab:
feature cards on the landing page with a `requiresAdvanced` flag, a router guard
on `meta.requiresAdvanced`, and a compliance dialog for the research level. The
guard, the dialog and the card states existed in the code; no route ever carried
the meta and no feature card ever carried the flag (`git log -S'requiresAdvanced: true'`
finds no commit), so the lock never held and every level reached both surfaces.
The dead path was removed with finding S-061 of the code review of 2026-10-10
(`docs/DEVELOPMENT_DECISIONS.md`, 2026-10-10): `router/index.ts` keeps no guard,
`views/LandingView.vue` no lock state, `components/ResearchComplianceDialog.vue`
is gone, and `stores/safetyLevel.ts` carries `level`, `loaded`, `resolved` and
`fetchLevel`. What protects the two surfaces is the checking the instruments run
themselves (the direct route's stage 1 and stage 3, the Canvas's stage 3 and its
picture check; see the route comments in `router/index.ts`). The lock on the two
surfaces was decided on 2026-02-11 (DEVELOPMENT_DECISIONS.md, decisions 2 and 3) and
never wired. Whether it is wired now is open. Wiring it needs a guard that reads a
route meta and a lock state for the cards on the landing page; neither exists since
2026-10-10.

---

## File Reference

### Frontend
| File | Purpose |
|------|---------|
| `views/latent_lab.vue` | Page frame + the left column that chooses the instrument |
| `views/latent_lab/attention_cartography.vue` | Attention heatmaps |
| `views/latent_lab/feature_probing.vue` | Dimension analysis + transfer |
| `views/latent_lab/concept_algebra.vue` | Vector arithmetic (A - B + C) |
| `stores/safetyLevel.ts` | Safety level store (level, loaded, resolved, fetchLevel) |

### Backend
| File | Purpose |
|------|---------|
| `services/diffusers_backend.py` | `generate_image_with_attention()`, `generate_image_with_probing()`, `generate_image_with_algebra()` |
| `services/attention_processors_sd3.py` | Custom attention capture |
| `services/embedding_analyzer.py` | Dimension difference + transfer + concept algebra |
| `devserver/my_app/routes/fusion_workbench_routes.py` | Fusion Workbench: `generate`, `expand_t5`, and the research routes `decomposition`, `position_probe`, `delayed_kickin`, `delayed_kickin_cumulative` (`generate` and the four research routes are ComfyUI graphs since 2026-09-14, run through `own_loop.run_blocking`; the research routes answer at the research level only; `expand_t5` runs `services/t5_expansion.py`, a text call without a graph) |
| `devserver/my_app/services/latent_lab_context_graphs.py` | The graphs those routes submit: step bands, layer bands, stream slices, and the `AI4ArtsEdSD3Context*` nodes (`comfyui_nodes/ai4artsed_sd3_context.py`) per cell, window or block |
| `routes/settings_routes.py` | `/api/settings/safety-level` endpoint |
| `config.py` | `DEFAULT_SAFETY_LEVEL`, `SAFETY_FILTERS` |

### Configs
| File | Purpose |
|------|---------|
| `schemas/pipelines/latent_lab.json` | Passthrough pipeline (skip Stage 2) |
| `schemas/configs/interception/latent_lab.json` | UI metadata (icon, category) |
| `schemas/configs/output/attention_cartography_diffusers.json` | Attention Cartography output config (Diffusers twin) |
| `schemas/configs/output/attention_cartography.json` | Attention Cartography output config (ComfyUI, what the surface runs) |
| `schemas/configs/output/feature_probing_diffusers.json` | Feature Probing output config |
| `schemas/configs/output/concept_algebra_diffusers.json` | Concept Algebra output config |
| `schemas/configs/output/denoising_archaeology_diffusers.json` | Denoising Archaeology output config |
| `schemas/chunks/output_image_concept_algebra_diffusers.py` | Concept Algebra Python chunk |

---

## 3. Denoising Archaeology

### 3. Denoising Archaeology

**Question:** "How does noise become an image? What emerges at which step?"

**Scientific Foundation:** Kwon, M. et al. (2023). "Diffusion Models Already Have a Semantic
Latent Space." ICLR 2023. DOI: 10.48550/arXiv.2210.10960
— Shows that intermediate activations (h-space) in diffusion models carry semantic meaning.
Early steps establish composition, middle steps form semantics, late steps refine detail.

**Backend:** Python chunk `output_image_denoising_archaeology_diffusers.py` →
`DiffusersImageGenerator.generate_image_with_archaeology()` (diffusers_backend.py)

**Mechanism:**
1. Standard SD3.5 generation with `callback_on_step_end` at every step
2. At each callback: VAE-decode current latents to 512×512 JPEG (quality 70) thumbnail
3. After generation: collect all step thumbnails + full-resolution final PNG
4. Return as structured dict via Python chunk's `execute()` → dict return path

**Three Educational Phases:**
| Phase | Steps (of 25) | Description | Color |
|-------|---------------|-------------|-------|
| Composition | 1–8 | Global structure, color distribution, layout | #FF9800 (orange) |
| Semantics | 9–17 | Objects become recognizable, shapes crystallize | #00BCD4 (cyan) |
| Detail | 18–25 | Textures, edges, fine patterns | #4CAF50 (green) |

**Key Files:**
- `devserver/schemas/chunks/output_image_denoising_archaeology_diffusers.py` — Python chunk
- `devserver/schemas/configs/output/denoising_archaeology_diffusers.json` — Output config
- `devserver/my_app/services/diffusers_backend.py` — `generate_image_with_archaeology()`
- `public/ai4artsed-frontend/src/views/latent_lab/denoising_archaeology.vue` — Frontend

**Frontend:** Prompt input → Generate → Filmstrip of 25 step thumbnails + timeline slider +
full-size viewer with phase indicator badge. Phase markers (Composition/Semantics/Detail)
along the slider.

**Performance:** 25 VAE decodes × ~50ms = +1.25s overhead. 25 thumbnails × ~80KB +
final PNG ~1.5MB = ~3.5MB total response.

## 4. Concept Algebra

**Question:** "What happens when you apply word2vec-style vector arithmetic to image generation embeddings?"

**Scientific Foundation:** Mikolov, T. et al. (2013). "Distributed Representations of Words and Phrases and their Compositionality." NeurIPS. DOI: 10.48550/arXiv.1310.4546
— Demonstrated that embedding spaces encode semantic relationships as linear directions: vec("King") − vec("Man") + vec("Woman") ≈ vec("Queen").

Liu, N. et al. (2022). "Compositional Visual Generation with Composable Diffusion Models." ECCV. DOI: 10.1007/978-3-031-19803-8_12
— Extended algebraic composition to diffusion model conditioning.

**Backend:** `DiffusersImageGenerator.generate_image_with_algebra()` (diffusers_backend.py)

**Mechanism:**
1. Encode three prompts (A, B, C) with selected text encoder(s)
2. Compute: embed_result = embed_A − scale_sub × embed_B + scale_add × embed_C
3. Same arithmetic on pooled embeddings
4. Generate reference image with embed_A (same seed)
5. Generate result image with embed_result

**Key Files:**
- `devserver/schemas/chunks/output_image_concept_algebra_diffusers.py` — Python chunk
- `devserver/schemas/configs/output/concept_algebra_diffusers.json` — Output config
- `gpu_service/services/diffusers_backend.py` — `generate_image_with_algebra()`
- `gpu_service/services/embedding_analyzer.py` — `apply_concept_algebra()`
- `public/ai4artsed-frontend/src/views/latent_lab/concept_algebra.vue` — Frontend

**Frontend:** Three-prompt input (A = base, B = subtract, C = add), encoder selector (All/CLIP-L/CLIP-G/T5), formula visualization (A − B + C = ?), side-by-side comparison (reference vs. result), L2 distance display, scale controls for subtraction/addition intensity.


---

## 5. Mean Images — **V 1.0**

**Question:** what does an image model produce when the same thing is asked of it
many times over — and what stays when the single pictures are laid on top of one
another?

**Where the words come from.** „Mean images" is Hito Steyerl's CRITIQUE of what
generative models produce (Steyerl 2025): pictures out of correlated averages, in
which social patterns come out as normality. Turning that back on the models as a
MEASUREMENT — making the average itself and looking at it — is this platform's,
and the instrument is named after her term for what it shows.

**The raster.** One row per image model, two columns:

- `seedFixed` — one seed held, the TEXT varied. A language model writes as many
  English variants of the prompt as the set size says, same content in other
  words.
- `promptFixed` — the text held, the SEEDS varied.

The two columns share their first picture: the first variant is the prompt
itself, on the first seed, and it stands in both sets rather than being computed
twice.

**Three readings per cell**, switched for the whole raster at once
(`View = 'images' | 'mean' | 'relief'`): the contact sheet of the single
pictures, the mean, and the relief — the mean with its local contrast lifted, so
that what survives the averaging can be seen at all.

**The mean before the decoder.** Where every run of a set kept its final latent —
the two SD 3.5 rows do — the latents are averaged and the average is decoded ONCE
(`POST /api/latent-lab/mean-images/overlay`). A latent mean keeps the local
sharpness a pixel mean washes out. Since 08.09.2026 the two SD 3.5 rows keep
their latent through the platform's node `AI4ArtsEdKeepLatent`, and since
14.09.2026 the mean is decoded in ComfyUI: `services/latent_decoder.py` hands
the averaged latent to ComfyUI as a file, and `AI4ArtsEdLoadKeptLatent` reads it
back under the checkpoint that made the set. A row without a latent path has
the pixel mean, and every cell says which of the two it shows. This is
NOT a choice on the surface: it follows from the row.

**A press completes the raster rather than starting it over** (2026-09-05). If
the material is unchanged — the English text, the variants, the seed list, the
set size, the automatic-seed flag — and cells are missing, only the missing ones
are made. A cell counts as made when it holds a picture OR a refusal: a failure
is tried again, because a card that was taken answers differently a minute later;
a refusal is not, because it is a verdict on this model, this seed and this text.
A cell whose mean rests on three of five pictures is not made and is laid again
with all five. Any other change makes the press a fresh run.

**What V 1.0 fixed rather than offered.**

- The set size is a slider up to the route's own ceiling, 50 per cell
  (`MAX_PER_CELL`, `routes/mean_images_routes.py`); under two there is nothing to
  average.
- Two columns, and no third axis. What varies is either the wording or the seed,
  because a cell that varies both says nothing about either.
- The kind of mean follows from the row, as above.
- The star on a cell is a FAVOURITE and is set by hand only. Nothing on this
  surface marks itself.

**Open at V 1.0.**

- The pixel mean of the ComfyUI rows is unverified against a reference
  implementation.
- Kept latents are never cleaned up; neither is what a decode leaves in ComfyUI
  (one `.npy` in `input/`, one PNG in `output/`, until the next ComfyUI start).
- Whether a single-picture decode should be delayed is an open question.

**Key files:**
- `devserver/my_app/routes/mean_images_routes.py` — variants, overlay, record
- `devserver/my_app/services/latent_decoder.py` — the decode of a mean, in ComfyUI
- `comfyui_nodes/ai4artsed_keep_latent.py` — the node that keeps a latent and the node that reads one back
- `devserver/my_app/services/latent_lab_recorder.py` — the raster as one record
- `public/ai4artsed-frontend/src/views/latent_lab/mean_images.vue` — the surface
- `public/ai4artsed-frontend/src/composables/useRasterRun.ts` — the sequential press

---

## Python Chunk Dict-Return Extension (Generic)

**Motivation:** `_execute_python_chunk()` (backend_router.py) originally only supported
`bytes` returns from `execute()`. The router guessed the media type from the chunk's
filename prefix (`output_music_*` → audio, else → raw bytes). This doesn't scale for
chunks that return structured data (multiple images, analysis results, metadata).

**Extension:** If `execute()` returns a `dict`, the router uses it directly:
- `dict['content_marker']` → `BackendResponse.content` (route dispatch key)
- Remaining dict entries → spread into `BackendResponse.metadata`
- `chunk_type: "python"` added automatically

**Backwards compatible:** Chunks returning `bytes` work unchanged.

**Location:** `devserver/schemas/engine/backend_router.py`, method `_execute_python_chunk()`,
after `result = await module.execute(**parameters)`.

**Example (Denoising Archaeology):**
```python
# In chunk execute():
return {
    'content_marker': 'diffusers_archaeology_generated',
    'image_data': base64_png,
    'archaeology_data': {'step_images': [...], 'total_steps': 25, 'seed': 42}
}
# Router creates: BackendResponse(content='diffusers_archaeology_generated', metadata={...})
```

**Future benefit:** Any Python chunk can return structured output. HeartMuLa could
eventually migrate from name-based detection to dict returns.

---

## Latent Text Lab — Dekonstruktive LLM-Introspektion

### Overview

The Latent Text Lab (`textlab` tab inside `/latent-lab`) extends the deconstructive paradigm from image models to large language models. Where the image-side tools (Attention Cartography, Feature Probing, etc.) expose the internals of Stable Diffusion 3.5, the Text Lab exposes the internals of decoder-only LLMs (LLaMA, GPT-2, Falcon, etc.).

**Key Question:** "What biases, directions, and structures are encoded in a language model's weights?"

The Text Lab does not produce finished text outputs — it runs controlled experiments that make invisible model behavior visible.

| Instrument | Component | Status | Purpose |
|-----|-----------|--------|---------|
| Representation Engineering | `latent_lab/representation_engineering.vue` | **V 1.1** (2026-08-26) | One direction read off contrast pairs, added to the middle decoder layer while the model writes |
| Bias Archaeology 1 | `latent_lab/bias_archaeology.vue` | Implemented | Undecidable questions from the BBQ set, answered per model |
| Bias Archaeology 2 | `latent_lab/coreference_test.vue` | Implemented | Which noun a pronoun is taken to mean, pair by pair |
| System Prompts | `compare/system_prompt_comparison.vue` | Implemented | The same prompt under different system prompts |

### Scientific Foundation (Text-Side)

Three additional research lines complement the image-side foundation:

#### Representation Engineering (Text Domain)
- **Zou, A. et al. (2023).** "Representation Engineering: A Top-Down Approach to AI Transparency." arXiv.
  DOI: [10.48550/arXiv.2310.01405](https://doi.org/10.48550/arXiv.2310.01405)
  — Concept directions in activation space via contrast pairs, read by an uncentered SVD over the normalised pair differences (Appendix C.1). Forward-hook manipulation steers generation without retraining. **Basis for: Tab 1 (Representation Engineering), reading AND manipulation.**

- **Li, K. et al. (2023).** "Inference-Time Intervention: Eliciting Truthful Answers from a Language Model." NeurIPS 2023.
  DOI: [10.48550/arXiv.2306.03341](https://doi.org/10.48550/arXiv.2306.03341)
  — Same family, different operation: a probe per attention head and a shift on the selected heads only. **NOT the basis for Tab 1** — the manipulation there is Zou et al.'s single direction over the whole hidden state (see Tab 1 below). Left the surface's reference list on 2026-08-24.

#### Probing & Comparative Archaeology
- **Belinkov, Y. (2022).** "Probing Classifiers: Promises, Shortcomings, and Advances." Computational Linguistics (MIT Press).
  DOI: [10.1162/coli_a_00422](https://doi.org/10.1162/coli_a_00422)
  — Layer-wise probing of what information neural representations encode. **Basis for: Tab 2 (Comparative Model Archaeology).**

- **Olsson, C. et al. (2022).** "In-Context Learning and Induction Heads." Anthropic Research.
  DOI: [10.48550/arXiv.2209.11895](https://doi.org/10.48550/arXiv.2209.11895)
  — Induction heads and mechanistic interpretability across model scales. **Basis for: Tab 2 (CKA comparison, attention analysis).**

#### Bias and Monosemanticity
- **Bricken, T. et al. (2023).** "Towards Monosemanticity: Decomposing Language Models With Dictionary Learning." Anthropic Research.
  — Individual neurons can encode interpretable features; systematic probing reveals latent biases. **Basis for: Tab 3 (Bias Archaeology).**

#### Mapping: Paper → Text Lab Tab

| Paper | Tab | Operation |
|-------|-----|-----------|
| Zou 2023 | Representation Engineering | Concept direction extraction via contrast pairs, and the forward-hook manipulation of generation |
| Belinkov 2022 | Comparative Model Archaeology | Layer-wise representation probing |
| Olsson 2022 | Comparative Model Archaeology | CKA similarity, attention pattern analysis |
| Bricken 2023 | Bias Archaeology | Systematic bias detection via token manipulation |

### Architecture

#### Data Flow

```
Frontend (the Text Lab views)
    │
    │ POST /api/text/*
    ▼
DevServer text_routes.py
    ├── services/text_presets.py   the model rows (config/text_presets.json)
    ├── services/text_probes.py    one prompt of a node per reading
    │       ▼
    │   ComfyUI: ai4artsed_llm_option_scores, ai4artsed_llm_rep_engineering
    │       (comfyui_nodes/ai4artsed_comfyui/_text_probes.py; the model is
    │        loaded by ComfyUI under its memory management, _local_llm)
    └── services/text_client.py    the tokenizer doors, ComfyUI's HTTP routes
                                   (comfyui_nodes/ai4artsed_comfyui/_tokenizer_routes.py)
```

Since stage 5 of the move to ComfyUI the readings run on ComfyUI; the GPU service's text station (`routes/text_routes.py`, `services/text_backend.py`, `tokenizer_service.py`, its copies of `bbq_corpus.py` and `winobias_corpus.py`) was struck in stage 8, nothing called it any more. This mirrors the architecture of the image-side Latent Lab tools, where Diffusers runs in the GPU Service.

**Why not the 4-Stage Pipeline?** The Text Lab bypasses the standard orchestration pipeline (Stages 1–4) entirely. Like all Latent Lab tools, it requires unmanipulated access to model internals. Safety interception (Stage 2) or prompt translation (Stage 1) would destroy the experimental controls.

#### Model Management

The model a reading runs on is loaded by ComfyUI itself (`comfyui_nodes/ai4artsed_comfyui/_local_llm.py`), under ComfyUI's memory management, which moves language and diffusion models on and off the card as one allocator; every prompt the DevServer queues there takes the gate's remote lease (`services/comfyui_ws_client.py`, PART 40). The quantization ladder and the `VRAMBackend` protocol of the former TextBackend went with it in stage 8.

### Endpoints

The endpoints are the DevServer's (`devserver/my_app/routes/text_routes.py`); the GPU service's copy of them was struck in stage 8. The last column names the service function behind each.

| Endpoint | Method | Purpose | Service function |
|----------|--------|---------|------------------|
| `/api/text/presets` | GET | the model rows | `text_presets.listing()` |
| `/api/text/tokenize` | POST | a text cut into tokens | `TextClient.tokenize()` (ComfyUI) |
| `/api/text/tokenizers` | GET | which tokenizers this machine has | `TextClient.tokenizer_facts()` (ComfyUI) |
| `/api/text/encoder-rows` | POST | which piece stands in which row at CLIP and T5 | `TextClient.encoder_rows()` (ComfyUI) |
| `/api/text/rep-engineering` | POST | Representation Engineering | `text_probes.rep_engineering()` |
| `/api/text/bias-probe` | POST | Bias Archaeology | `text_probes.bias_probe()` |
| `/api/text/bbq-probe` | POST | BBQ | `text_probes.bbq_probe()` |
| `/api/text/bbq-overview` | GET | what is in the benchmark | `text_probes.bbq_overview()` |
| `/api/text/bbq-sample` | GET | a fresh draw of questions for one run | `text_probes.bbq_sample()` |
| `/api/text/bbq-record` | POST | keep one finished model series | `bbq_runs.record()` |
| `/api/text/bbq-stats` | GET | the platform's own history of the bias score | `bbq_runs.summary()` |
| `/api/text/bias-corpus` | GET | the pairs one run walks | `text_probes.bias_corpus()` |

**Note (2026-10-10):** the DevServer proxies that no surface called (`models`, `load`, `unload`, `embedding`, `embedding/pair`, `interpolate`, `attention`, `contrast-control`, `generate`, `generate/stream`, `variations`, `layers`, `interpret`) were removed with their client methods; the table lists what the frontend reaches.

### Tab 1: Representation Engineering (Zou 2023) — **V 1.1**, 2026-08-26

**Question:** "Can we find interpretable concept directions in activation space and use them to steer generation?"

**Surface (`latent_lab/representation_engineering.vue`).** Left column: the model
as a row of chips, a drop-down of ready-made pair sets, three contrast pairs
(three is the ceiling), the fan of differences, the strength axis, the test
prompt, the explanation box with the research basis in it. Right column: one row
per press, three columns per row, newest on top, and the two columns scroll for
themselves. Before the first press the row stands there dimmed with its three
headings and the settings it would run with.

**Mechanism:**

1. **Direction Finding** — the user writes contrast pairs, each differing in one
   thing. For every pair:
   - the last-token hidden state at the target layer is taken for each sentence,
     and the pair contributes `pos_hidden - neg_hidden`
   - the differences are unit-normalised and decomposed by an **uncentered SVD**
     (Zou et al., Appendix C.1 — the same computation as feeding every difference
     in both orientations; centering would subtract exactly what the pairs share).
     `Vh[0]` is the direction
   - the SIGN is laid on the mean of the differences, so the direction points
     towards the upper sentences
   - it is scaled by `mean(|d · direction|)`, the distance the pairs themselves
     travel along it — which is what makes α a count of pair-differences
   - returned per pair: `agreement` (cosine to the direction) and the coordinates
     in the plane of the first two singular vectors (`plane_x`, `plane_y`), plus
     `plane_share` and `explained_variance` for the whole reading

2. **Manipulation** — one press, one reading, three generations, one seed:
   - a forward hook on `decoder_layers[layer_idx - 1]` adds `α · direction_raw`
     to that layer's output at every token
   - the three columns are `−α`, `0`, `+α`; the middle one is the model left alone
   - the sampling temperature is fixed at the backend default (0.7) and is not
     offered: a second reason a text can come out different is the reason nobody
     could rule out

**What V 1.0 fixed rather than offered.** The **target layer** is the middle of
the stack and has no control (`target_layer: null` → the backend takes the middle
of whatever stack the chosen model has; 18 for Qwen3-4B). Early layers still hold
the words themselves, the last ones already hold the next word, and the middle is
where a claim stands as a claim — so the middle is the setting that produces
something legible, and the others are settings that waste a run. The strength axis
runs 0.5–3 and rests at 1.5, which tips the answer on the first press.

**What V 1.1 brought** (2026-08-26). The version is named for the **ready-made
pair sets**, which is what turns the surface from one axis into several: a
drop-down above the fields fills all three pairs at once (an axis is read from
the three together, so half a set reads half an axis), and the fields stay
writable. Three sets stand there — a fact against its plain opposite; the Party's
three slogans from *Nineteen Eighty-Four*, each against the plain predicate it
overturns; and, one level deeper, a claim against what would settle it. The
SENTENCES are never translated and therefore live in the Vue file as `PAIR_SETS`
rather than in the language files: they go to the model as they stand, and a
translated pair reads a different axis. What is translated is the name of a set.

A set is worth what its three differences are DIFFERENT, and that is measurable
on the surface itself: a pair that repeats another pair's construction lands on
top of it (measured at Qwen3-14B, layer 20: two such pairs at 0.7781 agreement,
0.7° apart), and the set then reads ONE direction out of what should have been
three. Measured angles of the three sets as they stand, same model and layer:
23/28/−54° (facts), 0.4/45/−56° (Orwell), 79/−22/3° (claim against evidence).

Four more things came with it:

- **The run ends.** The test text goes to the model as a raw completion, so an
  instruct model has no place to put its end token and a legible generation ran
  to the platform ceiling of 65,536 tokens — over half an hour, with the surface
  silent and every further press queued invisibly behind it on the card's single
  slot. This instrument is therefore the ONE place on the platform that runs
  under a hard length limit, as an explicit exception, with the
  reason taken from the first two paragraphs of Zou et al.: the unit of analysis
  is the representational space, and the text of a cell is the READOUT of a shift
  in it. Two numbers, so that no sentence breaks mid-word: the run closes at the
  first sentence end after 160 tokens, and 256 ends the run that writes one
  sentence forever (`REPENG_SOFT_TOKENS` / `REPENG_HARD_TOKENS`).
- **Each column lands on its own.** The three generations are three requests that
  go out together, and the seed is drawn on the surface and travels with all
  three — it used to come back from the first answer and be handed to the other
  two, which forced them into a queue.
- **The model choice is a row of chips** instead of a drop-down, with what the
  model asks of the card beside its name. What that costs: the native
  `<option disabled>` blocked a model that will not fit, and `ChipSelect` has no
  per-chip block.
- **The fan shows the arrow that agrees.** The common arrow is drawn first so the
  pair arrows lie on top of it; a number that would land on a neighbour's steps
  one notch further out along its own ray.

**Not Li et al. (ITI).** Inference-Time Intervention trains a probe on each
ATTENTION HEAD, keeps the heads that separate, and shifts only those, each along
its own probe direction. What runs here is Zou et al.'s reading vector alone: one
direction over the whole hidden state, added to the output of one decoder layer.
No head is probed and none is selected, so the citation left the surface on
2026-08-24.

**What the fan shows.** Three differences stand at three pairwise angles, and
three rays from one point on a flat sheet have two free parameters — so the
drawing is a projection onto the plane the reading itself picks out, not a
hand-made arrangement. All arrows are the same length; a length would state a
property of the drawing. Measured on Qwen3-4B, layer 18, with the three default
pairs: agreements 0.685 / 0.650 / 0.569 (46.8° / 49.5° / 55.3°),
`explained_variance` 40.5 %, `plane_share` 71.35 %.

**What a run shows.** With the three default pairs the answer tips in the
**`+α` column**, not the one against: on "The capital of Germany is" the model
answers *Paris* there, while the middle column says Berlin. The shared direction
of three pairs carries the CONTENT of the upper sentences, not an abstract
truthfulness — which is the finding the instrument is for.

**Architecture-Aware Layer Access:**
`_get_decoder_layers(model)` handles different LLM architectures:
- LLaMA/Mistral: `model.model.layers`
- GPT-2: `model.transformer.h`
- Falcon: `model.transformer.h`

**Bug Fix:** Hidden states have N+1 entries (including input embedding) but decoder layers have N entries. Hook index must use `layer_idx - 1`.

### Tab 2: Comparative Model Archaeology (Belinkov 2022 + Olsson 2022)

**Question:** "How do two different models represent the same information internally?"

**Mechanism:**

1. Load two models simultaneously (Model A = primary, Model B = loaded separately)
2. Feed same prompt through both
3. Compute **Linear CKA** (Centered Kernel Alignment) similarity matrix between all layer pairs:
   - Subsample to max 32 layers per model for tractability
   - CKA measures representational similarity independent of dimensionality
4. Extract attention patterns and layer-wise statistics (L2 norm, mean, std) from both
5. Generate text from both with shared seed for behavioral comparison

**Frontend:** CKA heatmap rendered on `<canvas>` with interactive tooltip (hover shows exact CKA value per layer pair). Side-by-side generation comparison.

### Tab 3: Bias Archaeology (Zou 2023 + Bricken 2023)

**Question:** "What happens when we systematically suppress or boost specific token categories?"

**Preset Experiments:**

| Type | Manipulation | What It Reveals |
|------|-------------|-----------------|
| Gender | Suppress all gendered pronouns (he/she/his/her/him/herself/himself) | Model's default gender assumptions |
| Sentiment | Boost positive OR negative words separately | Strength of sentiment encoding |
| Domain | Boost scientific OR poetic vocabulary | Register shift patterns |
| Custom | User-defined boost/suppress token lists | Open-ended bias probing |

**Mechanism:**

1. Generate baseline samples (no manipulation, multiple seeds)
2. For each group: resolve token IDs (bare + space-prefixed + capitalized variants via `_resolve_token_ids()`)
3. Apply additive logit manipulation during generation:
   - Boost: `logits[:, token_id] += factor`
   - Suppress: `logits[:, token_id] = -inf`
4. Generate manipulated samples with same seeds as baseline
5. Return structured result: `{baseline: [...], groups: [{group_name, mode, tokens, samples}]}`

**Bug Fix:** Multiplicative boost (`logits *= factor`) caused softmax collapse → switched to additive (`logits += factor`).

**Token Resolution:** BPE tokenizers encode `" he"` and `"he"` as different token IDs. `_resolve_token_ids()` resolves bare, space-prefixed (`" he"`), and capitalized (`"He"`, `" He"`) variants to ensure complete coverage.

### LLM Interpretation (removed 2026-10-10)

A DevServer-only endpoint `POST /api/text/interpret` was built to have a language model explain bias results to the 13 to 17 year old audience; no surface ever called it (its prompt builder returned the empty string), so the route and its builder were removed with the other uncalled text proxies.

### Frontend: `latent_text_lab.vue`

**Location:** `public/ai4artsed-frontend/src/views/latent_lab/latent_text_lab.vue`

**Host Integration (2026-08-18):**
`latent_lab.vue` owns the choice of instrument and renders `LatentTextLab` for the three instruments
of that group, handing the active one in as the prop `tab`. There is no tab bar any more, on this page
or in the three lab files: the fifteen instruments stand in the left column of the shared page frame
(`assets/shell.css`, `components/canvas/ModulePalette.vue`), under one group title per lab. The chosen
instrument persists in `localStorage('latent_lab_instrument')`; the two older keys
(`latent_lab_tab`, `latent_lab_image_tab`) are read once on first load and then removed.

**Shared Model Panel:**
All three instruments of this lab share a single model management panel (top of the surface). Loading a model makes it available across them. Model B (for comparison) is loaded separately within the comparison instrument.

**Tab Structure:**

| Tab | Component Section | Key Refs |
|-----|------------------|----------|
| Representation Engineering | `activeTab === 'repeng'` | `contrastPairs`, `repResult`, `repGenResult` |
| Model Comparison | `activeTab === 'compare'` | `cmpResult`, `loadedModelB`, `ckaCanvas` |
| Bias Archaeology | `activeTab === 'bias'` | `biasResult`, `biasInterpretation`, `biasInterpreting` |

**CKA Heatmap:** Rendered directly on `<canvas>` via `drawCkaHeatmap()`. Cell color intensity = CKA value^0.7. Interactive tooltip on mousemove shows exact layer pair + CKA value.

**Interpretation Box:** Automatically triggered after bias results arrive (`interpretBiasResults()` called in `runBiasProbe()`). Shows loading spinner → interpretation text → or error. Styled with subtle blue border to distinguish from raw results.

---

## Updated File Reference

### Frontend — Image-Side Latent Lab
| File | Purpose |
|------|---------|
| `views/latent_lab.vue` | Page frame + the left column (15 instruments in 3 groups) |
| `views/latent_lab/attention_cartography.vue` | Attention heatmaps |
| `views/latent_lab/feature_probing.vue` | Dimension analysis + transfer |
| `views/latent_lab/concept_algebra.vue` | Vector arithmetic (A - B + C) |
| `views/latent_lab/denoising_archaeology.vue` | Step-by-step denoising |
| `stores/safetyLevel.ts` | Safety level store (level, loaded, resolved, fetchLevel) |

### Frontend — Latent Text Lab
| File | Purpose |
|------|---------|
| `views/latent_lab/latent_text_lab.vue` | All 3 tabs + model management + CKA heatmap |

### Backend — Image-Side Latent Lab
| File | Purpose |
|------|---------|
| `gpu_service/services/diffusers_backend.py` | `generate_image_with_attention()`, `generate_image_with_probing()`, `generate_image_with_algebra()`, `generate_image_with_archaeology()` |
| `gpu_service/services/attention_processors_sd3.py` | Custom attention capture |
| `gpu_service/services/embedding_analyzer.py` | Dimension difference + transfer + concept algebra |
| `devserver/my_app/routes/fusion_workbench_routes.py` | Fusion Workbench: `generate`, `expand_t5`, and the research routes `decomposition`, `position_probe`, `delayed_kickin`, `delayed_kickin_cumulative` (`generate` and the four research routes are ComfyUI graphs since 2026-09-14, run through `own_loop.run_blocking`; the research routes answer at the research level only; `expand_t5` runs `services/t5_expansion.py`, a text call without a graph) |
| `devserver/my_app/services/latent_lab_context_graphs.py` | The graphs those routes submit: step bands, layer bands, stream slices, and the `AI4ArtsEdSD3Context*` nodes (`comfyui_nodes/ai4artsed_sd3_context.py`) per cell, window or block |

### Backend — Latent Text Lab (DevServer proxy layer)
| File | Purpose |
|------|---------|
| `devserver/my_app/routes/text_routes.py` | the Text Lab's routes |
| `devserver/my_app/services/text_probes.py` | the readings: one prompt of a node of the platform's package on ComfyUI |
| `devserver/my_app/services/text_presets.py` | the model rows (`config/text_presets.json`) |
| `devserver/my_app/services/text_client.py` | the tokenizer doors, asked of ComfyUI's HTTP routes |

### Backend — Latent Text Lab (ComfyUI execution)
| File | Purpose |
|------|---------|
| `comfyui_nodes/ai4artsed_comfyui/_text_probes.py` | the option scores and Representation Engineering on a local model |
| `comfyui_nodes/ai4artsed_comfyui/_tokenizer_routes.py`, `_tokenizers.py` | the tokenizer doors |

### Configs
| File | Purpose |
|------|---------|
| `schemas/pipelines/latent_lab.json` | Passthrough pipeline (skip Stage 2) |
| `schemas/configs/interception/latent_lab.json` | UI metadata (icon, category) |
| `schemas/configs/output/attention_cartography_diffusers.json` | Attention Cartography output config (Diffusers twin) |
| `schemas/configs/output/attention_cartography.json` | Attention Cartography output config (ComfyUI, what the surface runs) |
| `schemas/configs/output/feature_probing_diffusers.json` | Feature Probing output config |
| `schemas/configs/output/concept_algebra_diffusers.json` | Concept Algebra output config |
| `schemas/configs/output/denoising_archaeology_diffusers.json` | Denoising Archaeology output config |
| `schemas/chunks/output_image_concept_algebra_diffusers.py` | Concept Algebra Python chunk |

---

## Research Data Export (LatentLabRecorder)

### Problem

Canvas records research data via `CanvasRecorder` / `LivePipelineRecorder` because it runs through the 4-Stage Orchestrator — natural recording chokepoints exist. The Latent Lab bypasses this flow entirely: 11 tool types across 3 backend services with direct API calls. There is no backend chokepoint for a recorder.

### Solution: Frontend-Primary Hybrid

The frontend knows the full context (parameters, tab, tool type). After each generation, it POSTs to a lightweight backend endpoint which writes to disk.

**Phase 1** (current): Write to `exports/json/` — same folder structure as Canvas, always active.
**Phase 2** (future): QDA-compatible research format in `exports/research/` for analysis software.

### Architecture

```
┌─────────────────────────────────────┐
│  Vue Component (e.g. denoising)     │
│  useLatentLabRecorder('tool_name')  │
│                                     │
│  onMounted → isRecording = true     │
│  generate() → record({params, ...}) │  ←── Lazy start: the sitting is
│    → returns the RUN's id           │      opened on the first record()
│  onUnmounted → endSession()         │
└─────────────┬───────────────────────┘
              │ POST /api/latent-lab/record/{start,save,end}
              ▼
┌─────────────────────────────────────┐
│  LatentLabRecorder (Python)         │
│  - One instance per open tab        │
│  - record() writes ONE RUN FOLDER   │
│  - Writes params → prompting_process│
│  - Writes parts  → prompting_process│
│  - Writes outputs → final/          │
│  - metadata.json compatible with    │
│    LivePipelineRecorder/Canvas      │
└─────────────────────────────────────┘
              │
              ▼
exports/json/YYYY-MM-DD/device_id/
  run_<timestamp>_<hash>/
    metadata.json
    final/
      01_output_image.png
    prompting_process/
      001_parameters.json
      002_step_01.jpg  (denoising steps)
      002_step_02.jpg
```

### Lazy Start

Run folders are only created when the first `record()` call happens. Navigating between Latent Lab tabs without generating creates no empty folders.

### Sitting vs. Run (2026-08-21)

A **sitting** is one open instrument: it starts on the first `record()`, ends when
the view goes away, and is NOT an address. A **run** is one generation, and it is
what the platform addresses everywhere else — the run card carries its id,
favouriting stores it, restoring reads it back. `record()` therefore writes one
run folder per generation and returns that run's id; each run carries the sitting
it was made in (`session_id`, `generation`), so a session can still be
reassembled.

Until 2026-08-21 a whole sitting was one folder. Nothing could point INTO it, so
the Ablage stored the pipeline's own run instead — which holds the finished
picture and neither the parameters nor the sequence. `build_instrument_object()`
refuses to serve a pre-split sitting folder as a run (more than one
`latent_lab_params` entity): merging several generations into one sequence would
be an answer the data does not support.

### The instrument object (what the Ablage gives back)

```
GET /api/latent-lab/run/<run_id>            → the run as an object
GET /api/latent-lab/run/<run_id>/part/<i>   → one stored part
GET /api/latent-lab/session/<id>/runs       → this sitting's runs, for the strip
POST /api/latent-lab/run/<id>/output/<i>    → set the PLATE of a run again
GET /api/favorites/<run_id>/restore         → the same object under `instrument`
```

```json
{
  "run_id": "...", "tool": "denoising_archaeology",
  "session_id": "lab_...", "generation": 2,
  "parameters": { "prompt": "...", "seed": 123, "backbone": "sd35" },
  "results":    { "total_steps": 25, "scheduler_order": 1 },
  "parts":   [ { "index": 0, "kind": "step",
                 "url": "/api/latent-lab/run/<id>/part/0",
                 "meta": { "step": 1, "second": false } } ],
  "outputs": [ { "type": "image", "url": "/api/media/image/<id>/0" } ]
}
```

The storage guarantees the FRAME — tool, parameters, results, ordered parts,
outputs. What a part MEANS is instrument-specific and travels in that part's
`meta`; nothing between the two ends reads it. An instrument takes back only runs
whose `tool` is its own (`denoising_archaeology.vue`, watcher on
`favoritesStore.pendingRestoreData`), and a view must NOT clear a restore that is
not addressed to it.

### metadata.json

```json
{
  "run_id": "run_1771664748800_abc123",
  "timestamp": "2026-02-21T10:05:48",
  "type": "latent_lab",
  "latent_lab_tool": "denoising_archaeology",
  "session_id": "lab_1771664740000_ab12cd",
  "generation": 2,
  "device_id": "38db259e-...",
  "user_id": "anonymous",
  "parameters": { "prompt": "...", "seed": 123456789 },
  "results": { "total_steps": 25, "scheduler_order": 1 },
  "entities": [
    { "sequence": 1, "type": "latent_lab_params", "filename": "prompting_process/001_parameters.json" },
    { "sequence": 2, "type": "latent_lab_step", "filename": "prompting_process/002_step_01.jpg",
      "metadata": { "step_index": 0, "format": "jpg", "step": 1, "second": false } },
    { "sequence": 3, "type": "output_image", "filename": "03_output_image.png" }
  ]
}
```

**A PLATE is an output image an instrument may set again.** Where the picture a
run is SHOWN by is the instrument's own reading of it — Attention Cartography
draws a map over its render, and which map that is depends on the words, the
depth and the step the surface stands at — the reading is recorded as the run's
FIRST image and carries `metadata: { "plate": "reading", "reading": {...} }`.
The render stays behind it as a further output; nothing the model made is
traded away. `POST /api/latent-lab/run/<id>/output/<i>` sets such a picture
again (when the run is kept, from the reading then standing) and refuses
everything else: another instrument, the render, another device, bytes that are
not the recorded format. Picture and `reading` are written as one — the picture
goes back if the record cannot follow it, because a map whose reading is
unrecorded cannot be interpreted afterwards, and the attention maps themselves
are ~17 MB a run and are not kept.

Compatible with `SessionExportView.vue` — Latent Lab runs appear alongside Canvas runs.

### Integration per Tool

| Tool | Generation Functions | Recorded Data |
|------|---------------------|---------------|
| Denoising Archaeology | `generate()` | params + final PNG + all step JPGs; since 2026-09-22 written by the direct endpoint into the sitting the request names (`services/denoising_archaeology_record.py`), `generate()` records only where the server refused |
| Concept Algebra | `compute()` | params + reference + result images |
| Feature Probing | `analyze()`, `transfer()` | params + original/modified images |
| Attention Cartography | `generate()` | params + PLATE + output image |
| Crossmodal Lab | `runSynth()`, `runMMAudio()`, `runGuidance()` | params + audio WAV |
| Latent Text Lab | `findDirection()`, `runRepGeneration()`, `runComparison()`, `runBiasProbe()` | params + result metadata |
| Surrealizer | `executeWorkflow()` | params only (image in pipeline recorder) |

### Files

| File | Purpose |
|------|---------|
| `devserver/my_app/services/latent_lab_recorder.py` | LatentLabRecorder class + registry |
| `devserver/my_app/routes/latent_lab_recorder_routes.py` | Flask endpoints: record start/save/end, run + part |
| `public/.../composables/useLatentLabRecorder.ts` | Vue composable + the `InstrumentRun` shape |
| `devserver/my_app/routes/favorites_routes.py` | Attaches `instrument` to a restore |

---

**Document Status:** Active (2026-02-22)
**Maintainer:** AI4ArtsEd Development Team
**Last Updated:** LatentLabRecorder research data export
