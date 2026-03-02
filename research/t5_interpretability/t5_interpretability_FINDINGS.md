# T5 Audio-Semantic Interpretability: Research Findings

## Project Summary

This research investigated how T5-Base organizes semantic knowledge about sound in its 768-dimensional embedding space, and whether that structure can be exploited to build a controllable audio synthesizer ("Latent Audio Synth") through Stable Audio's text-to-audio diffusion pipeline.

**Approach**: Train a Sparse Autoencoder (SAE) on T5 activations from ~392K audio-related prompts, decompose 768 entangled dimensions into 6,144 monosemantic features, then sonify them by injecting SAE decoder vectors into Stable Audio's conditioning pathway.

**Core question**: Can we manipulate T5 embeddings directly to control audio generation?

**Answer**: Not via vector arithmetic (injection), but yes via interpolation between natural T5 outputs (LERP). The LERP approach recovers 80-90% of the text-prompt effect and produces monotonic acoustic gradients — a viable basis for a text-pole mixing board.

---

## 1. SAE Training: TopK Collapse and the L1 Solution

### Problem

The initial SAE used TopK sparsity (Anthropic's "Towards Monosemanticity" recipe): only the top-k activations survive per forward pass, all others are zeroed. With 392K training samples and 16x expansion (12,288 features, k=64), this produced **99.3% dead features** — only 86 of 12,288 features ever activated.

TopK creates a winner-take-all dynamic: early winners accumulate gradient, losers receive zero gradient and never recover. Neuron resampling (periodically reinitializing dead features from high-loss examples) was attempted but failed: features stayed alive only while resampling was active, then collapsed back to 99%+ dead within 5 epochs of stopping.

### Solution

Switched to ReLU activation with L1 sparsity penalty during training, TopK only at inference for clean sparse codes:

- **Training**: `features = ReLU(encoder(x))`, loss = MSE + lambda * L1(features)
- **Inference**: `features = TopK(ReLU(encoder(x)), k=64)`

L1 provides continuous gradient to all features (proportional to activation magnitude), preventing the winner-take-all collapse. Combined with reduced expansion (8x instead of 16x, yielding 6,144 features) and L1 warmup (10 epochs MSE-only, then linear ramp to full L1 coefficient):

| Metric | TopK (failed) | L1+ReLU (final) |
|---|---|---|
| Dead features | 99.3% | 0.0% (1 of 6,144) |
| Alive features | 86 | 6,143 |
| MSE per dimension | — | 0.000010 |
| L0 at inference (TopK@64) | — | 64.0 |

**Takeaway**: For SAEs trained on relatively small, domain-specific corpora (~400K samples), L1 sparsity with ReLU is more robust than TopK. The Anthropic TopK recipe was developed for billions of tokens from language model residual streams — a different data regime.

---

## 2. Cultural Distance Geometry

### Method

15 musical traditions (Ukrainian, Yoruba, Gamelan, Arabic, Jewish, Franconian, African American, Romani, Japanese, Korean, Hindustani, Tuvan, Aboriginal Australian, Flamenco, Electronic), each represented by 250 structurally identical prompts. Encoded through T5, projected into SAE feature space, tradition centroids computed.

### Results

**Permutation test**: p = 0.001 (1,000 permutations). The pairwise cosine distances between tradition centroids are significantly non-random. T5 does encode culturally distinguishable representations for these 15 traditions.

**Closest pairs** (cosine distance in SAE feature space):
- Japanese <-> Korean: 0.082
- Korean <-> Ukrainian: 0.085
- Arabic <-> Korean: 0.086

**Most distant pairs**:
- Electronic <-> Japanese: 0.317
- Electronic <-> Hindustani: 0.313
- Electronic <-> Gamelan: 0.293

Electronic music is maximally distant from all acoustic traditions — consistent with its fundamentally different vocabulary (synthesis terms vs. instrument names).

**Discriminative features**: 265 SAE features account for 90% of between-tradition variance (out of 6,144 total). Cultural encoding is distributed across many features, not concentrated in a few.

### Default-Encoding Bias

Distance of bare "music" centroid to each tradition centroid:

| Tradition | Distance to "music" | Interpretation |
|---|---|---|
| Romani | 0.569 (closest) | Most "default-like" |
| African American | 0.571 | |
| Jewish | 0.594 | |
| Franconian | 0.615 | |
| ... | | |
| Japanese | 0.681 (furthest) | Least "default-like" |

**Critical caveat**: This reflects T5's English-language training corpus, not musicological significance. "Romani music" likely co-occurs with common English music vocabulary (violin, guitar, rhythm, melody) more than "Japanese music" does (which requires specialized terms like shakuhachi, gagaku, shamisen). The finding measures **lexical proximity in training data**, not cultural importance or representativeness.

---

## 3. Individual Feature Interpretation: Unvalidated

The SAE analysis identified 1,073 alive features (at TopK@64 inference) and generated top-activating prompts for each. Example:

> **Feature #1058** (max |r| = 0.297): Top prompts include Balinese gamelan vocal interjections, Hindustani tanpura, and high-arousal exclamations.

These interpretations are **post-hoc correlational labels**, not causal descriptions. The top-activating prompts share surface vocabulary (specific instrument names, cultural labels) that may or may not reflect a coherent acoustic concept encoded in the feature.

**Validation attempt via sonification**: Activating Feature #1058 at various strengths produced ~0.5s percussive sounds with no identifiable connection to Balinese music or any other specific acoustic quality. The interpretation did not survive causal testing.

**Status**: Individual feature semantics remain unvalidated. The feature atlas is useful as a hypothesis-generating tool, not as a ground-truth map.

---

## 4. Sonification Experiments: The Conditioning Bottleneck

### Experiment A: SAE Feature Sonification

**Method**: Encode neutral prompt "sound" through T5, add scaled SAE decoder column vectors (strengths -2 to +2), generate audio via Stable Audio's embedding-conditioned endpoint.

**Result**: 250 files generated (50 features x 5 strengths). No perceptible systematic variation across strength levels. All outputs sound similar — short percussive textures regardless of which feature or strength is applied.

### Experiment B: Binary Contrast Sonification

**Method**: Encode "sound smooth" and "sound harsh" through T5, compute difference vector, inject at 7 strength levels (-3 to +3) into neutral "sound" embedding.

**Result**: 90 files generated (10 contrasts x 7 strengths + 20 references). No perceptible pattern across injection strengths. Notably, strength +0.0 (pure neutral embedding) always produces a similar knocking sound regardless of contrast direction.

However, the 20 reference files generated via direct text prompts ("sound smooth", "sound harsh", etc.) **do** sound different from each other. "sound rhythmic" in particular produces clearly rhythmic audio.

### Experiment C: Statistical Validation (N=100 per condition)

To overcome single-seed randomness, generated 100 samples each (seeds 0-99) for two conditions and extracted 11 acoustic features via librosa (onset density, spectral centroid, RMS energy, spectral flatness, zero crossing rate, tempo, spectral bandwidth, spectral flux). Welch's t-test, Cohen's d, and Mann-Whitney U computed per feature.

**Condition: "sound rhythmic" vs "sound sustained"**

#### Text Prompts (Experiment C1)

| Acoustic Feature | Cohen's d | p-value |
|---|---|---|
| spectral_centroid_std | **+2.882** | 6.9 x 10^-45 |
| spectral_flatness_mean | **+2.280** | 4.2 x 10^-31 |
| rms_mean | **-1.949** | 1.5 x 10^-26 |
| spectral_flux_std | **+1.635** | 6.0 x 10^-22 |
| onset_density | **-1.343** | 2.7 x 10^-16 |
| rms_std | **+1.073** | 2.1 x 10^-12 |

6 of 11 features show highly significant differences (p < 0.001). Cohen's d values up to 2.88 (d > 0.8 is conventionally "large"). Text prompts produce **massively** distinguishable audio across seeds.

#### Embedding Injection (Experiment C2)

Same semantic contrast (rhythmic vs sustained), but applied via T5 difference vector injection instead of text prompts:

| Acoustic Feature | Cohen's d | p-value |
|---|---|---|
| onset_density | **-0.834** | 2.0 x 10^-8 |
| spectral_flatness_mean | **+0.526** | 3.3 x 10^-4 |
| spectral_flux_std | **+0.419** | 3.6 x 10^-3 |

3 of 11 features significant. Largest effect: d = 0.83 (medium-to-large).

#### Direct Comparison

| Feature | Text d | Injection d | Signal Retention |
|---|---|---|---|
| spectral_centroid_std | +2.882 | +0.181 | 6% |
| spectral_flatness_mean | +2.280 | +0.526 | 23% |
| rms_mean | -1.949 | +0.214 | 11% (wrong direction) |
| spectral_flux_std | +1.635 | +0.419 | 26% |
| onset_density | -1.343 | -0.834 | 62% |
| rms_std | +1.073 | +0.038 | 4% |

**Key findings**:

1. Embedding injection is **not zero-effect** — 3 features reach statistical significance with N=100. But the effect is invisible at the single-sample level (unhearable).

2. Signal retention is **5-25%** for most features. The strongest injection effect (onset_density, d=0.83) is weaker than the weakest significant text-prompt effect (rms_std, d=1.07).

3. **Direction reversal**: rms_mean shows opposite sign under injection vs text prompts (+0.21 vs -1.95), indicating partial distortion of semantic content during embedding manipulation.

#### LERP Interpolation (Experiment C3)

Instead of injecting a difference vector into a neutral embedding, interpolate linearly between two natural T5 outputs: `emb = (1-t) * T5("sound sustained") + t * T5("sound rhythmic")`, with t in {0.0, 0.25, 0.5, 0.75, 1.0}. Both endpoints are natural T5 outputs — the interpolation stays close to Stable Audio's learned conditioning distribution.

N=100 per position, 500 samples total.

**Extreme comparison** (t=0.0 vs t=1.0):

| Acoustic Feature | Cohen's d | p-value |
|---|---|---|
| spectral_centroid_std | **+2.434** | 9.2 x 10^-41 |
| spectral_flatness_mean | **+1.860** | 3.3 x 10^-28 |
| rms_std | **+1.404** | 7.4 x 10^-19 |
| spectral_flux_std | **+1.348** | 7.8 x 10^-18 |
| onset_density | **-1.169** | 3.5 x 10^-13 |
| rms_mean | **-1.112** | 1.6 x 10^-12 |

6 of 11 features highly significant (p < 0.001). Same 6 features as the text-prompt experiment.

**Gradient analysis** (Pearson correlation between LERP position t and acoustic feature, N=500):

| Feature | Pearson r | p-value | t=0.00 | t=0.25 | t=0.50 | t=0.75 | t=1.00 |
|---|---|---|---|---|---|---|---|
| spectral_centroid_std | +0.631 | 7.5 x 10^-57 | 738 | 1393 | 1884 | 2276 | 2566 |
| spectral_flatness_mean | +0.544 | 6.2 x 10^-40 | 0.04 | 0.09 | 0.15 | 0.18 | 0.20 |
| spectral_flux_std | +0.520 | 5.8 x 10^-36 | 23.0 | 18.0 | 21.5 | 51.8 | 55.4 |
| rms_std | +0.509 | 2.8 x 10^-34 | 0.05 | 0.05 | 0.05 | 0.12 | 0.12 |
| onset_density | -0.361 | 7.7 x 10^-17 | 9.0 | 5.4 | 4.3 | 4.4 | 4.6 |
| rms_mean | -0.295 | 1.8 x 10^-11 | 0.28 | 0.13 | 0.07 | 0.15 | 0.13 |

8 of 11 features show significant monotonic trends. Intermediate LERP positions produce intermediate acoustic features.

#### Full Comparison Across Methods

| Feature | Text d | Injection d | LERP d | LERP/Text |
|---|---|---|---|---|
| spectral_centroid_std | +2.882 | +0.181 | +2.434 | **84%** |
| spectral_flatness_mean | +2.280 | +0.526 | +1.860 | **82%** |
| rms_std | +1.073 | +0.038 | +1.404 | **131%** |
| spectral_flux_std | +1.635 | +0.419 | +1.348 | **83%** |
| onset_density | -1.343 | -0.834 | -1.169 | **87%** |
| rms_mean | -1.949 | +0.214 | -1.112 | **57%** |

LERP recovers **57-131%** of the text-prompt effect (median ~84%), compared to injection's 5-25%. All effect directions match the text-prompt baseline. The rms_mean direction reversal observed in injection (wrong sign) is corrected in LERP.

#### Multi-Axis Additive LERP (Experiment C4)

Tests whether 3 LERP axes combined additively preserve individual effects.

**Design**: 2³ factorial — 3 axes (rhythmic↔sustained, bright↔dark, smooth↔harsh), each at 2 levels, 8 conditions, N=50 per condition = 400 samples total.

**Combination method**: `emb = neutral + (pole1 - neutral) + (pole2 - neutral) + (pole3 - neutral)`, where each pole is the T5 embedding of the selected axis endpoint.

**All three axes show significant main effects on different acoustic dimensions:**

| Axis | Strongest Feature | Cohen's d | p-value |
|---|---|---|---|
| rhythmic↔sustained | spectral_centroid_std | +1.022 | 7.9 x 10^-22 |
| bright↔dark | spectral_bandwidth_mean | +1.145 | 4.9 x 10^-26 |
| smooth↔harsh | rms_mean | -1.737 | 2.2 x 10^-47 |

The axes affect *different* acoustic features — rhythmic controls spectral variation, bright controls bandwidth, smooth controls energy. This is the prerequisite for independent control.

**However, signal degradation is substantial.** The rhythmic↔sustained axis loses ~60-65% of its single-axis effect:

| Feature | LERP (1 axis) d | Multi (3 axes) d | Retention |
|---|---|---|---|
| spectral_centroid_std | +2.434 | +1.022 | **35%** |
| spectral_flatness_mean | +1.860 | +0.821 | **36%** |
| spectral_flux_std | +1.348 | +0.646 | **40%** |
| onset_density | -1.169 | -0.306 | **23%** |

**Axis interaction**: The rhythmic axis effect varies by context — spectral_centroid_std d ranges from +0.36 (when others = dark+smooth) to +1.94 (when others = bright+smooth). The axes are not independent; they interact.

#### Complete Method Comparison

| Method | Signal Retention | Monotonic? | Multi-axis? |
|---|---|---|---|
| Text prompts | 100% (reference) | n/a | n/a |
| LERP (1 axis) | **84%** | Yes (r=0.63) | n/a |
| **Additive LERP (3 axes)** | **35%** | Yes | Yes, but degraded |
| Embedding injection | 6% | Not tested | Not tested |

---

## 5. Diagnosis: Why Injection Fails, LERP Succeeds, and Multi-Axis Degrades

Stable Audio's conditioning pathway is trained end-to-end: tokenizer -> T5 -> cross-attention -> diffusion. The cross-attention layers learn to attend to embedding patterns that T5 naturally produces.

**Injection fails** (5-25% signal retention): Adding difference vectors or SAE decoder columns to an embedding creates out-of-distribution inputs. The resulting point in embedding space doesn't look like anything T5 would naturally produce. Cross-attention largely ignores it.

**LERP succeeds** (80-90% signal retention): Both interpolation endpoints are natural T5 outputs. Linear interpolation between two in-distribution points stays close to the learned manifold. Cross-attention responds to the blended embedding almost as strongly as to a pure text-prompted one.

This is not a flaw in the SAE or in T5's representations. T5 does encode semantically meaningful structure (the cultural distance analysis confirms this). The constraint is that Stable Audio only responds to embeddings that lie on or near the manifold of natural T5 outputs.

**Multi-axis degrades** (35% signal retention): Adding 3 deltas simultaneously pushes the combined embedding away from the T5 manifold. Not as catastrophically as raw injection (the deltas are smaller and better-behaved), but the cumulative displacement is enough to lose ~65% of each axis's effect. The axes also interact — the effect of one axis depends on the position of the others.

**Implication**: Single-axis LERP works well. Multi-axis additive combination works but degrades. A learned projection (bridge model) that maps multi-slider configurations back onto the T5 manifold could recover the lost signal.

---

## 6. Cultural Drift: Perceptual Axes Carry Cultural Baggage

### Method

For 21 semantic axes across three levels (8 perceptual, 7 cultural-contextual, 6 critical), computed LERP positions in mean-pooled T5 embedding space and measured cosine distance to the 15 tradition centroids (computed from the probing corpus). No audio generation — pure embedding-space analysis.

This connects the LERP sonification findings with the cultural distance analysis: when you move a "perceptual" slider, does the embedding also drift toward specific cultural traditions?

### Key Findings

#### "traditional ↔ modern": Ukrainian = most "traditional"

| Tradition | Drift toward "traditional" |
|---|---|
| Ukrainian | -0.071 (strongest) |
| Arabic | -0.060 |
| Korean | -0.057 |
| African American | -0.002 (near zero) |
| Electronic | +0.013 (only tradition receding) |

T5 strongly associates "traditional" with Eastern European and Middle Eastern music. African American traditions (Blues, Gospel, Jazz — among the oldest living American traditions) show essentially no drift toward "traditional." This reveals how English-language discourse codes "traditional" as geographically non-Western.

#### "improvised ↔ composed": Not aligned with high/low culture

| Tradition | Drift toward "improvised" |
|---|---|
| Hindustani | -0.146 (strongest) |
| Flamenco | -0.140 |
| Electronic | -0.130 |
| Ukrainian | -0.100 (weakest) |

Hindustani and Flamenco drift strongly toward "improvised" — consistent with their performance traditions. But Electronic also drifts strongly, breaking the expected "improvised = non-Western" pattern. The axis differentiates, but not along Eurocentric high-culture lines.

#### "complex ↔ simple": No Eurocentrism detected

Minimal differentiation across all 15 traditions (max drift: Tuvan -0.020 toward "complex," Aboriginal Australian +0.015 toward "simple"). T5 does **not** associate "complex" preferentially with European art music. This null finding is notable.

#### "beautiful ↔ ugly": East Asian bias

| Tradition | Drift toward "beautiful" |
|---|---|
| Korean | -0.059 (strongest) |
| Romani | -0.058 |
| Franconian | -0.055 |
| Yoruba | -0.028 (weakest) |

Small spread (0.03), but consistent: East Asian and European traditions closer to "beautiful," West African furthest. Reflects aesthetic norms encoded in English-language training data.

#### "music ↔ noise": Who counts as music?

| Tradition | Drift toward "music" |
|---|---|
| Romani | -0.132 (closest to "music") |
| Jewish | -0.124 |
| African American | -0.122 |
| Tuvan | -0.076 (furthest from "music") |
| Aboriginal Australian | -0.078 |

Tuvan throat singing and Aboriginal Australian music are the most "noise-like" in T5's embedding space. This is consistent with the Default-Encoding Bias finding from Section 2. Traditions using non-standard vocal techniques or unfamiliar timbres are encoded further from the "music" concept.

#### "professional ↔ amateur": Electronic = professional, African American = amateur

| Tradition | Drift toward "professional" |
|---|---|
| Electronic | -0.040 (most "professional") |
| Gamelan | -0.031 |
| African American | +0.003 (only tradition drifting toward "amateur") |

African American music is the **only** tradition that drifts (slightly) toward "amateur." This is a measurable bias in T5's embedding space, reflecting historical patterns of delegitimization in English-language music discourse.

#### "ceremonial ↔ everyday": Strong differentiator

This axis produces the largest cultural drift of any axis tested. All traditions drift toward "ceremonial," but the spread is large:

| Tradition | Drift toward "ceremonial" |
|---|---|
| Flamenco | -0.197 (strongest) |
| Arabic | -0.196 |
| Hindustani | -0.195 |
| Electronic | -0.100 (weakest) |

#### Confounding pattern: tonal ↔ noisy dominates

The "tonal ↔ noisy" axis produces the strongest cultural drift of any axis for **every single tradition** (drift magnitudes 0.26–0.32). This is the most culturally loaded "perceptual" axis: moving toward "tonal" simultaneously pulls toward all music traditions, with Flamenco (-0.321) and African American (-0.315) leading. The axis is not purely perceptual — it encodes the culturally constructed boundary between music and non-music.

### Pedagogical Implications

The drift analysis reveals three categories of axes:

1. **Culturally neutral**: "loud ↔ quiet" (max drift 0.027), "complex ↔ simple" (max drift 0.020). These axes change sound quality without significant cultural side effects. Safe for purely aesthetic exploration.

2. **Culturally biased**: "traditional ↔ modern," "professional ↔ amateur," "beautiful ↔ ugly." These carry measurable cultural associations that could be made visible to learners: "When you move this slider, the model also moves toward/away from these traditions."

3. **Culturally constitutive**: "tonal ↔ noisy," "music ↔ noise." These axes don't just carry bias — they reproduce the boundary definitions of what counts as music. The strongest finding: "tonal" is not a neutral perceptual descriptor but a culturally loaded category that pulls toward specific traditions.

A pedagogical interface could display the cultural drift alongside the sound output: "You moved 'tonal ↔ noisy' to 0.7. This also moved the embedding 0.28 closer to Flamenco and 0.23 closer to Aboriginal Australian." Making the confounding visible turns a bias into a learning opportunity.

---

## 7. Three-Level Taxonomy: Empirical Validation (21 Axes)

### Method

The drift analysis (Section 6) classified axes into three pedagogical categories based on embedding-space cultural drift magnitude: **neutral** (safe for aesthetic exploration), **biased** (drift should be shown to learners), and **constitutive** (reproduces music/non-music boundaries). This classification was based on drift analysis alone — no audio was generated.

To test whether these categories predict *acoustic* behavior, all 21 semantic axes were sonified via LERP interpolation. 8 perceptual axes, 8 cultural-contextual axes, and 5 critical axes, each at 5 LERP positions (t = 0.0, 0.25, 0.5, 0.75, 1.0). The 6 axes from the initial taxonomy study used N=50 per position (250 per axis); the 15 expansion axes used N=30 per position (150 per axis). Total: 3,750 audio samples. 11 acoustic features extracted per sample via librosa.

### Per-Axis Results

| Axis | Level | Max |d| | Sig (p<.05) | Top Feature | Gradient r |
|---|---|---|---|---|---|
| tonal↔noisy | perceptual | 4.806 | 8/11 | rms_mean | +0.767 |
| rhythmic↔sustained | perceptual | 2.604 | 7/11 | spectral_centroid_std | +0.639 |
| ceremonial↔everyday | cultural | 2.391 | 9/11 | onset_density | -0.441 |
| improvised↔composed | cultural | 2.109 | 9/11 | onset_density | +0.562 |
| music↔noise | critical | 2.058 | 10/11 | spectral_centroid_mean | -0.545 |
| acoustic↔electronic | cultural | 2.013 | 7/11 | spectral_flatness_mean | -0.487 |
| complex↔simple | critical | 1.914 | 6/11 | onset_density | -0.570 |
| sacred↔secular | cultural | 1.756 | 7/11 | onset_density | -0.518 |
| refined↔raw | critical | 1.735 | 7/11 | spectral_flatness_mean | -0.497 |
| solo↔ensemble | cultural | 1.593 | 1/11 | onset_density | +0.486 |
| bright↔dark | perceptual | 1.281 | 5/11 | spectral_centroid_mean | +0.427 |
| traditional↔modern | cultural | 1.213 | 5/11 | spectral_bandwidth_mean | -0.355 |
| beautiful↔ugly | critical | 1.097 | 3/11 | zcr_mean | +0.357 |
| loud↔quiet | perceptual | 1.024 | 8/11 | spectral_flux_std | +0.325 |
| professional↔amateur | cultural | 0.965 | 6/11 | onset_density | -0.315 |
| smooth↔harsh | perceptual | 0.810 | 7/11 | rms_std | -0.299 |
| fast↔slow | perceptual | 0.800 | 3/11 | spectral_flux_std | +0.291 |
| close↔distant | perceptual | 0.758 | 2/11 | onset_density | -0.238 |
| dense↔sparse | perceptual | 0.735 | 2/11 | rms_std | -0.296 |
| vocal↔instrumental | cultural | 0.673 | 3/11 | spectral_flux_mean | -0.212 |
| authentic↔fusion | critical | 0.649 | 2/11 | spectral_bandwidth_mean | -0.230 |

All 21 axes produce statistically significant acoustic effects. The weakest axis (authentic↔fusion, d=0.649) still qualifies as a "medium" effect by conventional thresholds (d > 0.5).

### Aggregation by Level

| Level | N axes | Mean max |d| | Mean sig features | Mean |gradient r| |
|---|---|---|---|---|
| perceptual | 8 | 1.602 | 5.2/11 | 0.410 |
| cultural | 8 | 1.589 | 5.9/11 | 0.422 |
| critical | 5 | 1.491 | 5.6/11 | 0.440 |

The three levels produce **comparable** mean acoustic effects. This contradicts the hypothesis that constitutive axes would produce stronger acoustic effects than neutral axes. When classified by the original drift-based taxonomy:

| Drift-based level | N axes | Mean max |d| |
|---|---|---|
| constitutive | 3 | 2.866 |
| neutral | 4 | 1.108 |
| biased | 5 | 1.136 |

Constitutive axes (tonal↔noisy, music↔noise, refined↔raw) do produce the strongest effects. But this is driven by tonal↔noisy (d=4.806) — an outlier. Neutral and biased axes are indistinguishable in acoustic effect magnitude.

### Drift-Acoustic Correlation

Does embedding-space cultural drift magnitude predict acoustic effect size?

- **Pearson r = +0.688** (p = 0.0006, N = 21)
- **Spearman ρ = +0.314** (p = 0.17, N = 21)

The Pearson correlation is high and significant. The Spearman rank correlation is not. This divergence reveals that the linear relationship is driven by a few high-leverage points — primarily tonal↔noisy (drift = 0.321, d = 4.806) and ceremonial↔everyday (drift = 0.197, d = 2.391). Remove these two outliers and the Pearson correlation weakens substantially.

**Interpretation**: There is a trend — axes with more cultural baggage in embedding space tend to produce stronger acoustic effects — but it is not a robust rank-order relationship. The trend is real for the extremes (constitutive axes dominate both drift and acoustic effect) but noisy for the middle range.

### Effect Profile Correlation Matrix (Selected Clusters)

The 21×21 matrix of Cohen's d profiles (11 features per axis) reveals axis clusters that share acoustic fingerprints:

**Strongly correlated pairs** (|r| > 0.8):
- dense↔sparse ↔ smooth↔harsh: r = +0.92 (both control spectral density/energy)
- fast↔slow ↔ smooth↔harsh: r = -0.91 (fast ≈ harsh, slow ≈ smooth)
- sacred↔secular ↔ ceremonial↔everyday: r = +0.87 (overlapping cultural categories)
- sacred↔secular ↔ beautiful↔ugly: r = +0.83 (aesthetic and sacral overlap)
- smooth↔harsh ↔ vocal↔instrumental: r = +0.85 (vocal ≈ smooth)
- professional↔amateur ↔ rhythmic↔sustained: r = +0.83 (professional ≈ rhythmic)

**Key pattern**: Perceptual axes cluster with each other through shared acoustic mechanisms (energy, spectral shape). Cultural axes cluster through shared semantic associations in T5's training data. Cross-level clusters (e.g., professional↔amateur ↔ rhythmic↔sustained) reveal how cultural categories encode implicit perceptual expectations.

### Within-Level vs Between-Level Similarity

Do axes within the same level produce similar acoustic effects?

| Comparison | Mean r | Std | N pairs |
|---|---|---|---|
| Within perceptual | -0.084 | 0.517 | 28 |
| Within cultural | -0.079 | 0.433 | 28 |
| Within critical | -0.058 | 0.303 | 10 |
| **Between levels** | +0.031 | 0.399 | 144 |

Within-level correlations are **not higher** than between-level correlations. The three-level taxonomy does not capture acoustic groupings — axes within the same level are no more similar to each other than to axes in other levels. The taxonomy is useful for *pedagogical* categorization (how to present axes to learners) but does not reflect *acoustic* structure.

### Acoustic Feature Profiles by Level

Each level tends to engage different acoustic features:

- **Perceptual**: rms_mean (mean |d| = 1.021), spectral_centroid_std (0.876), spectral_bandwidth_mean (0.806) — energy and spectral shape
- **Cultural**: onset_density (1.243), spectral_centroid_std (0.959), spectral_flux_std (0.791) — temporal structure and spectral variation
- **Critical**: spectral_flux_mean (0.939), zcr_mean (0.910), spectral_centroid_mean (0.866) — spectral character and noise content

This suggests that perceptual axes operate primarily through energy/loudness dimensions, cultural axes through rhythmic/temporal dimensions, and critical axes through timbral/noise dimensions — consistent with the semantic content of each category.

---

## 8. What Survives Scrutiny

| Finding | Status | Evidence |
|---|---|---|
| SAE training: L1+ReLU > TopK for small corpora | **Confirmed** | 0% vs 99.3% dead features |
| Cultural distances are non-random | **Confirmed** | Permutation test p=0.001 |
| Cultural encoding is distributed (~265 features) | **Confirmed** | Variance analysis |
| Default-bias reflects training corpus vocabulary | **Plausible** | But confounded by probing template vocabulary |
| Individual SAE feature semantics | **Unvalidated** | Sonification failed to provide causal evidence |
| Text prompts produce distinguishable audio | **Confirmed** | d=2.88, N=100, p<10^-44 |
| Embedding injection has measurable but weak effect | **Confirmed** | d=0.83, N=100, p<10^-7, ~5-25% signal retention |
| LERP between T5 outputs recovers ~84% of text effect | **Confirmed** | d=2.43, N=100, p<10^-40, monotonic gradient |
| LERP produces monotonic acoustic gradients | **Confirmed** | Pearson r up to 0.63, 8/11 features significant |
| Multi-axis additive LERP (3 axes) | **Partially confirmed** | Each axis significant, but 35% retention per axis |
| Multi-axis axes affect different features | **Confirmed** | rhythmic→spectral variation, bright→bandwidth, smooth→energy |
| Multi-axis axes are independent | **Rejected** | Axis effects depend on context (d ranges 0.36–1.94) |
| Perceptual axes carry cultural drift | **Confirmed** | 21 axes measured, "tonal↔noisy" strongest (drift 0.26–0.32) |
| "complex↔simple" shows Eurocentrism | **Rejected** | Near-zero differentiation across all 15 traditions |
| "professional↔amateur" shows bias | **Confirmed** | African American = only tradition drifting toward "amateur" |
| "music↔noise" reproduces exclusion | **Confirmed** | Tuvan/Aboriginal furthest from "music" (consistent with default bias) |
| Latent Audio Synth via embedding injection | **Not viable** | Effect too weak for perceptual control |
| Latent Audio Synth via single-axis LERP | **Viable** | 84% signal retention, monotonic control |
| Latent Audio Synth via multi-axis additive LERP | **Marginal** | 35% retention; usable but needs bridge model for full signal |
| All 21 axes produce LERP effects | **Confirmed** | Weakest: authentic↔fusion d=0.649 (medium effect); 3,750 samples |
| 3-level taxonomy predicts acoustic effect size | **Partially confirmed** | Constitutive (mean d=2.87) >> neutral (1.11) ≈ biased (1.14) |
| Drift-acoustic correlation (N=21) | **Partially confirmed** | Pearson r=0.688 (p<0.001) but Spearman ρ=0.314 (p=0.17); driven by outliers |
| Axes within same level share acoustic profiles | **Rejected** | Within-level r ≈ between-level r ≈ 0; no acoustic clustering by taxonomy |
| Perceptual/cultural/critical affect different features | **Confirmed** | Perceptual → energy, cultural → temporal, critical → timbral |

---

## 9. Implications for a Pedagogical Audio Interface

The original vision — SAE feature sliders directly manipulating embeddings — is not viable. LERP interpolation between text-encoded poles recovers 84% of the text-prompt effect for a single axis, but degrades to ~35% when 3 axes are combined additively. A functional multi-axis synth requires either accepting the degradation or training a bridge model.

### Architecture Options

#### Option A: Single-Axis LERP (validated, 84% signal)

One slider per session, switching between axis pairs. Simple, no interaction effects, strong signal. Limited expressivity — users control one dimension at a time.

#### Option B: Additive Multi-Axis (validated, ~35% signal per axis)

N sliders, each backed by a text-pole pair. Combination: neutral + Σ deltas. Effects are significant but degraded, and axes interact. Still usable for coarse control — d=1.02 is a "large" effect by convention, even at 35% retention. The smooth↔harsh axis retains d=1.74 even in multi-axis context.

Example axes (all validated in multi-axis context):
- "sound rhythmic" <-> "sound sustained" (d=1.02, spectral variation)
- "sound bright" <-> "sound dark" (d=1.15, bandwidth)
- "sound smooth" <-> "sound harsh" (d=1.74, energy)

#### Option C: Bridge Model (not yet implemented)

A small learned network (MLP or VAE) that maps slider positions → valid T5 embedding. Trained on (text prompt, T5 embedding) pairs with annotations for each axis dimension. The network learns the non-linear manifold geometry and projects arbitrary slider combinations back onto it.

Training data: ~10K text prompts with annotated properties, encoded through T5. Architecture: small MLP (N slider inputs → 768d embedding), loss = reconstruction + distributional regularization (output must be "T5-like").

This would potentially recover the full 84% signal per axis even with multiple axes, while eliminating interaction effects.

### Resolved Questions

1. **Multi-axis interaction**: Additive combination degrades to ~35% signal per axis. The embedding drifts from the T5 manifold, but not catastrophically — all axes remain significant.

2. **Axis orthogonality**: **Rejected.** Axes interact — the rhythmic axis effect varies from d=0.36 to d=1.94 depending on other axes' positions. Independent control requires a bridge model.

3. **Perceptual threshold**: Not yet tested. Statistical significance (d=1.02 in multi-axis) suggests the effects should be audible, but needs human evaluation.

4. **Pole selection**: The three tested axes affect different acoustic dimensions, confirming that diverse poles produce diverse control. Systematic screening of more pairs would identify optimal axes.

### Abandoned Paths

1. **SAE feature injection**: 5-25% signal retention. Analytically useful, operationally not actionable.

2. **Difference vector injection**: Same problem — out-of-distribution.

3. **Cross-attention fine-tuning**: Would require retraining Stable Audio, high cost, unnecessary given LERP viability.

---

## 10. Experimental Details

| Parameter | Value |
|---|---|
| Corpus size | 392,268 prompts (388K bulk + 3.9K probing) |
| T5 model | google-t5/t5-base (110M params) |
| Activation shape | [392,268 x 768], mean-pooled over non-padding tokens |
| SAE architecture | ReLU + L1 training, TopK@64 inference |
| SAE expansion | 8x (768 -> 6,144 features) |
| SAE alive features | 6,143 / 6,144 (99.98%) |
| Audio model | Stable Audio (via GPU service, port 17803) |
| Audio parameters | 5s duration, 100 steps, CFG 7.0 |
| Statistical tests | Welch's t-test, Cohen's d, Mann-Whitney U |
| Samples per condition | N=100 (seeds 0-99); LERP: N=100 x 5 positions; Multi-axis: N=50 x 8 conditions; 21-axis: N=30-50 x 5 positions |
| Acoustic features | 11 (librosa: onset density, spectral centroid mean/std, RMS mean/std, spectral flatness, ZCR, tempo, spectral bandwidth, spectral flux mean/std) |

### Scripts

| Script | Purpose |
|---|---|
| `build_corpus.py` | Phase 1a: Download AudioCaps, MusicCaps, WavCaps |
| `build_probing_corpus.py` | Phase 1b: Generate structured probing prompts |
| `encode_corpus.py` | Phase 2: T5 batch encoding |
| `dimension_atlas.py` | Phase 3: Per-dimension clustering |
| `train_sae.py` | Phase 4: SAE training (L1+ReLU) |
| `analyze_features.py` | Phase 5: Feature interpretation |
| `sonify_features.py` | Phase 6: SAE feature sonification |
| `cultural_analysis.py` | Phase 7: Cultural distance geometry |
| `sonify_binary_contrasts.py` | Validation: Binary contrast injection |
| `statistical_sonification_test.py` | Validation: Text-prompt statistics (N=100) |
| `statistical_embedding_injection_test.py` | Validation: Injection statistics (N=100) |
| `statistical_lerp_test.py` | Validation: LERP interpolation statistics (N=500) |
| `statistical_multiaxis_test.py` | Validation: Multi-axis factorial test (N=400) |
| `cultural_drift_analysis.py` | Cultural drift per axis (21 axes x 15 traditions) |
| `statistical_threelevel_test.py` | 3-level taxonomy sonification (6 initial axes, N=50/pos) |
| `statistical_remaining_axes.py` | 15 expansion axes sonification (N=30/pos) |
| `analyze_threelevel.py` | Comprehensive 21-axis cross-analysis |

### Data

All outputs in `research/t5_interpretability/data/` (gitignored). Key files:

- `corpus.json` (392K entries)
- `activations_pooled.pt` ([392268, 768], 575 MB)
- `sae_weights.pt` (L1 SAE, 37 MB)
- `feature_atlas.json` + `feature_atlas_report.md`
- `cultural_analysis_report.md`
- `statistical_test/statistical_report.md` (text-prompt results)
- `statistical_injection_test/statistical_report.md` (injection results)
- `sonification/` (250 WAV, SAE features)
- `sonification_binary/` (90 WAV, binary contrasts)
- `statistical_test/` (200 WAV, text-prompt experiment)
- `statistical_injection_test/` (200 WAV, injection experiment)
- `statistical_lerp_test/` (500 WAV, LERP gradient experiment)
- `statistical_multiaxis_test/` (400 WAV, multi-axis factorial experiment)
- `cultural_drift/cultural_drift_report.md` (21 axes x 15 traditions drift analysis)
- `statistical_threelevel_test/` (3,750 WAV, 21 axes x 5 positions x N=30-50)
- `statistical_threelevel_test/comprehensive_report.md` (21-axis cross-analysis)
- `statistical_threelevel_test/statistical_report.md` (per-axis detail, 6 initial axes)
