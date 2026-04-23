# Trashy – Central Knowledge Base for User Answers

Single reference Trashy can quote to explain workflows, configs, media outputs, and the four-stage architecture to end users (teachers, kids). Keep it short, accurate, and easy to update when flows change.

---

## 1) Architecture in 6 lines (answer-ready)
- **Four Stages:** (1) Safety & translation → (2) Transformation/interception → (3) Safety & media safety → (4) Output/media generation.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L8-L119】
- **Pipelines, not code:** Every task runs through a named pipeline (e.g., `text_transformation`, `single_text_media_generation`).【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L8-L119】
- **Configs steer behavior:** Config files define context, style, output media, and backend route; nothing is hardcoded in code.
- **Backend-agnostic:** Same config works locally (Ollama/ComfyUI) or in cloud (OpenRouter) via `meta.backend`.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L32-L119】
- **UI follows pipeline metadata:** `pipeline_type`, `pipeline_stage`, and `input_requirements` tell the frontend how many text/image inputs to show.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L123-L199】
- **Pedagogy lives in context:** The `context` field encodes learning goals, cultural framing, and artistic attitude—sometimes multi-page.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L95-L125】

---

## 2) Pipeline quick-reference (names, purpose, I/O, examples)
| Pipeline | Purpose | Inputs | Typical outputs | Example configs / notes |
| --- | --- | --- | --- | --- |
| **text_transformation** | Transform text by style/attitude/structure before any media step | 1 text (+ optional context bubble) | Transformed text or stringified JSON | `overdrive.json`, `surrealization.json` (dual-encoder prep), `bauhaus.json`, `splitandcombinelinear.json`.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L8-L31】【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L70-L125】 |
| **single_text_media_generation** | Generate media from one prompt | 1 text | Image/Audio/Music/Video | `sd35_large.json`, `flux1.json`, `dalle.json`, `stable_audio.json`; backend chosen via `meta.backend`.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L32-L74】 |
| **dual_text_media_generation** | Generate media from two prompts (e.g., tags + lyrics) | 2 texts | Music (WAV) | `acestep_standard.json` with `input_mapping` to ComfyUI nodes (`tags_node`, `lyrics_node`).【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L62-L89】 |
| **image_text_media_generation** | Modify/generate image with image + text | 1 image + 1 text | Modified image | Inpainting/Image2Image; e.g., `inpainting_sd35.json` (planned). Pipeline exists; configs rolling out.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L95-L118】 |
| **Vector fusion (split & combine)** | Show vector-level blending of two prompts | 2 texts | 4 images: Original (concatenated), Vector-Fused (embedding blend), Element 1, Element 2 | Workflow sends each element separately; vector-fused image is a mathematical interpolation of CLIP embeddings.【F:docs/handover_split_and_combine_20251214_FINAL.md†L38-L60】【F:docs/handover_split_and_combine_20251214_FINAL.md†L238-L241】 |

**Media Trashy may list:** Images (SD3.5, Flux1, DALL-E), Audio/Music (Stable Audio, AceStep). Video is planned—state the status if asked.

---

## 3) Stage-2 essentials (how Trashy explains it)
- **Why it matters:** Stage 2 is the creative/pedagogical core that reframes inputs before any media is made.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L23-L44】
- **Architectural room for complexity:** Loops, branches, multi-chunk chains, and multiple outputs are supported even if many configs use a single chunk.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L48-L96】
- **Output formats:** Plain text or stringified JSON (e.g., `part_a/part_b` splits); DevServer parses the string at the edges.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L66-L96】
- **Context drives pedagogy:** Context can be short (Overdrive) or detailed frameworks; it encodes attitude, prohibitions, and language tone.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L95-L125】
- **Backend transparency:** Same config runs in eco (local) or fast (cloud); safety is handled in Stages 1 & 3.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L127-L159】
- **Output optimization:** DevServer can append backend-specific optimization guidance (e.g., SD3.5 dual-encoder hints) via config override, without editing the original config.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L163-L210】

---

## 3.1) Stage-2 config catalog (full list, answer-ready)
**Trashy should know every Stage-2 config by name, intent, and status (including placeholders). Use this as the authoritative lookup.**

| Config name | Intent / transformation | Notes & status |
| --- | --- | --- |
| `analog_photography_1870s.json` | Reframes prompts as 1870s daguerreotype plans with material constraints and metallic surface aesthetics. | Defaults to image output; highlight historic optics and darkroom references.【1a35c9†L1】 |
| `analog_photography_1970s.json` | Reimagines prompts as 1970s Leica/Kodachrome photo plans with optical grain and chemical contrast control. | Defaults to image output; stress optical, not digital, treatment.【1a35c9†L2】 |
| `analogue_copy.json` | Translates prompts into analog duplication aesthetics (signal decay, transport artefacts, generational loss). | Emphasize media texture drift across copies.【1a35c9†L3】 |
| `bauhaus.json` | Deconstructs inputs into Bauhaus functionalism (form follows function, geometric reduction, industrial palette). | No “in the style of” phrasing; one-paragraph output.【1a35c9†L4】 |
| `clichéfilter_v2.json` | Removes clichéd visual conventions while keeping media type and semantics. | Use as de-biasing stylistic scrub.【1a35c9†L5】 |
| `confucianliterati.json` | Rewrites scenes into Confucian literati painting grammar with spatial ethics and inscription rules. | Cite perspective rules and ink/brush ethics; keep ≥30% Analects allusions.【1a35c9†L6】 |
| `de-biaser.json` | Rewrites prompts from deprivileged/global-south viewpoints to counter western/consumer/gender bias. | Forbid othering/Orientalism; same output language as input.【1a35c9†L7】 |
| `digital_photography.json` | Recasts prompts as early mobile (iPhone 3 era) photo plans with sensor noise, compression, and spontaneous framing. | Keep immediacy; default image output.【1a35c9†L8】 |
| `displaced_world.json` | Responds from a damaged-logic world to foreground absurdity and fragility of meaning. | Tone may be playful or sober; keep INPUT central.【1a35c9†L9】 |
| `expressionism.json` | Turns prompts into intense, critical, expressive responses across sensory modes. | Emphasize tensions and social rupture.【1a35c9†L10】 |
| `hunkydoryharmonizer.json` | Child-safe harmonizer that removes horror/menace motifs from visual prompts. | Use when kid-appropriate output is needed.【1a35c9†L11】 |
| `image_transformation.json` | Placeholder config (no context); reserved for generic image transformations. | State that it is currently empty/for future use.【1a35c9†L12】 |
| `jugendsprache.json` | Rewrites text into modern UK youth slang without formality. | Text-only transformation.【1a35c9†L13】 |
| `overdrive.json` | Extreme exaggeration of all input elements—amplifies to grotesque levels. | High-intensity; works across image/audio/video outputs.【1a35c9†L14】 |
| `p5js_simplifier.json` | Converts scene descriptions into ordered layer lists with primitive shapes for creative coding. | Output is structured BACKGROUND/MIDGROUND/FOREGROUND list; same language as input.【1a35c9†L15】 |
| `partial_elimination.json` | Placeholder config (empty context). | Flag as inactive/awaiting content.【1a35c9†L16】 |
| `piglatin.json` | Converts every word to Pig Latin; no extra text. | Pure linguistic transformation.【1a35c9†L17】 |
| `planetarizer.json` | Rewrites consumerist prompts toward ecological/Anthropocene-aware framing. | Avoids nature clichés and othering; keeps input language.【1a35c9†L18】 |
| `relational_inquiry.json` | Shifts attention to relations/thresholds rather than objects, favoring openness and process. | Avoids fixed hierarchies or final resolutions.【1a35c9†L19】 |
| `renaissance.json` | Plans works as Renaissance art with order, proportion, and dignitas across painting/sculpture/architecture. | Uses geometric composition and chiaroscuro without naming theory.【1a35c9†L20】 |
| `split_and_combine.json` | Placeholder config (empty context). | Note inactivity; often paired with vector-fusion demos.【1a35c9†L21】 |
| `stable-diffusion_3.5_tellastory.json` | Turns prompts into short narrative inspirations before media. | For storytelling tone-shaping; text output.【1a35c9†L22】 |
| `stillepost.json` | Translates text to target language with no commentary. | Pure translation; text output only.【1a35c9†L23】 |
| `surrealizer.json` | Legacy Surrealizer that routes prompts directly to a T5/CLIP ComfyUI workflow (bypasses Stage 2 transformation). | Mention as legacy; media output via ComfyUI.【1a35c9†L24】 |
| `technicaldrawing.json` | Rewrites prompts into unemotional engineering-manual language for mechanical assemblies. | Precision-focused, text output.【1a35c9†L25】 |
| `theopposite.json` | Produces diametrical opposites for all entities and relations (spatial/visual/semantic). | Use for contrastive prompts.【1a35c9†L26】 |
| `user_defined.json` | Placeholder config (empty context). | Reserved for ad-hoc or future definitions.【1a35c9†L27】 |

---

## 4) Ready-to-speak workflow briefs
**A) Text transformation (`text_transformation`, Stage 2)**
- **Intent:** Change style/attitude/structure before media generation.
- **How to phrase it:** “I reshape your text with a chosen attitude—e.g., Overdrive exaggeration, Bauhaus reduction, or Surrealization prep—before we optionally create media from it.”
- **Key configs:**
  - `overdrive.json` → maximal exaggeration.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L101-L109】
  - `surrealization.json` → prepares dual-encoder prompts for SD3.5 (T5 semantics + CLIP visuals with alpha blend).【F:docs/sessions/SESSION_48_SUMMARY.md†L13-L58】
  - `splitandcombinelinear.json` → returns JSON with `part_a` (essentials) and `part_b` (rest) as a string.【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L76-L96】

**B) Surrealization dual-encoder image flow (Stage 2 → Stage 4)**
- **Intent:** Fuse semantic and visual vectors before SD3.5 image generation.
- **How to phrase it:** “Your prompt is optimized twice—once for deep meaning (T5) and once for visual tokens (CLIP). We blend them with an alpha slider and feed both into SD3.5 for dreamlike, uncanny images.”
- **Process:** User prompt → T5 optimization (up to 250 words) → CLIP optimization (token-weighted, ~50 words) → alpha blending → ComfyUI image render.【F:docs/sessions/SESSION_48_SUMMARY.md†L29-L58】

**C) Single-prompt media (`single_text_media_generation`, Stage 4)**
- **Intent:** Create media directly from one prompt.
- **How to phrase it:** “Give one prompt; the system picks the backend (local ComfyUI or cloud OpenRouter) and renders the medium.”
- **Configs:** Images: `sd35_large.json`, `flux1.json`, `dalle.json`; Audio/Music: `stable_audio.json`.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L32-L74】

**D) Two-prompt music (`dual_text_media_generation`, Stage 4)**
- **Intent:** Music from two texts (tags + lyrics), typical AceStep flow.
- **How to phrase it:** “One field for style/instruments, one for lyrics; the engine maps them to ComfyUI nodes and outputs a WAV.”
- **Config:** `acestep_standard.json` with `input_mapping` for `tags_node` and `lyrics_node`.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L62-L89】

**E) Image + text (`image_text_media_generation`, Stage 4)**
- **Intent:** Modify an image with a text prompt (inpainting / image2image).
- **How to phrase it:** “Upload an image, add instructions, and the inpainting workflow applies the change.”
- **Status:** Pipeline ready; configs like `inpainting_sd35.json` are being rolled out—state availability clearly.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L95-L118】

**F) Vector fusion showcase (split & combine)**
- **Intent:** Demonstrate vector-level blending vs. simple concatenation.
- **How to phrase it:** “We render four images: the straightforward combined prompt, a true vector-fused hybrid, and each element alone—so you can see how embeddings interpolate.”
- **Mechanics:** Two separate text inputs are injected directly; vector-fused output mathematically interpolates CLIP embeddings (no prompt concatenation).【F:docs/handover_split_and_combine_20251214_FINAL.md†L38-L60】【F:docs/handover_split_and_combine_20251214_FINAL.md†L238-L241】

---

## 5) How Trashy should answer questions
- Name the pipeline and at least one config (e.g., “text_transformation with surrealization.json”).
- State purpose, inputs, outputs, and backend options (local vs. cloud) in one or two sentences.
- Clarify media type and status (e.g., “Video is planned; currently inactive”).
- Mention UI expectations: number of text fields/image uploads from `input_requirements`.【F:docs/ARCHITECTURE PART 04 - Pipeline-Types.md†L123-L199】
- Cite the pedagogical stance from `context` briefly (attitude, prohibitions, tone).【F:docs/ARCHITECTURE PART 20 - Stage2-Pipeline-Capabilities.md†L95-L125】
- Be transparent about gaps: “Feature planned/not active yet.”
- Close with a clarifying ask (age group, medium, time budget) to tailor guidance.

---

## 6) Maintenance checklist (keep Trashy current)
- Add new configs to the table (name, purpose, inputs, output, backend notes).
- Update media/backends with status (active/beta/planned).
- Surface new context highlights if a config adds strict pedagogy or long-form guidance.
- Adjust UI notes if `input_requirements` or labels change.
- Stamp date + short change note at the end when updating.

---

*Last updated: please add date and summary on next change.*
