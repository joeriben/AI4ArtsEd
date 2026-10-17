# DevServer Architecture

**Part 30: Latent Audio Synth — Embedding-Space Synthesis with Dimension Explorer**

---

## Overview

The Latent Audio Synth operates directly in the **768-dimensional prompt-conditioning space** of Stable Audio. Instead of generating audio from text prompts, it exposes the intermediate embedding layer as a manipulatable control surface — enabling interpolation, extrapolation, magnitude scaling, noise injection, and per-dimension offset control.

**Which encoder.** Since the SA1 → SA3 migration that space belongs to SA3-medium’s **t5gemma**
conditioner (`google/t5gemma-b-b-ul2`, 256 token slots, output dim 768), reached through
stable-audio-tools — **not** to the standalone t5-base of the SA1 path. The dimensionality is
unchanged, so the 768-drawbar canvas survives structurally; every derived VALUE (PCA fit, axis
strengths, SAE feature atlas, per-axis effect sizes) is encoder-bound and has to be re-derived.
Re-measurement of the two load-bearing claims:
`docs/analysis/NACHMESSUNG_latent_audio_synth_sa3_2026-08-05.md`.

**Key Principle:** Conditioning embeddings are continuous feature vectors, not opaque blobs. Operations on them are composable and produce audibly distinct results.

**Architecture Pattern:** GPU Service (Backend) > REST API > Vue Frontend > Web Audio API

**Analogy:** The Dimension Explorer treats the 768 conditioning dimensions as **semantic drawbars** — like partials in an additive synthesizer or drawbars on a Hammond organ. The spectral strip UI follows the Vital/Serum spectral editor paradigm: direct manipulation by painting on bars.

---

## Architecture

### Data Flow: User Input to Audio Output

```
[Prompt A] ─┐                                    ┌─ [WAV bytes]
             ├─ t5gemma ───┐                     │
[Prompt B] ─┘              ├─ Manipulate ─ Generate ─ base64 ─┐
                           │   - interpolate                   │
[Alpha, Magnitude,         │   - scale magnitude               │
 Noise, Offsets] ──────────┘   - inject noise          [Frontend]
                               - apply dim offsets       │
                                                         ├─ Looper (Web Audio)
                               [Embedding Stats] ───────┤   - crossfade
                                - all_activations        │   - loop optimize
                                - sort_mode              │   - OLA pitch shift
                                                         │   - pitch cache
                               [MIDI] ──────────────────┤
                                - CC → synth params      │
                                - Note → transpose       │
                                                         └─ Canvas (spectral strip)
                                                              - 768 bars
                                                              - click+drag offsets
                                                              - undo/redo
```

### Embedding Manipulation Pipeline

Operations are applied **sequentially** (order matters):

1. **Interpolation/Extrapolation**: `result = (1-alpha) * emb_a + alpha * emb_b`
   - `alpha=0.5` = midpoint blend, `alpha>1.0` or `<0.0` = extrapolation
2. **Magnitude Scaling**: `result = result * magnitude`
3. **Noise Injection**: `result = result + randn_like(result) * noise_sigma`
   - Seeded independently (`seed + 1`) for reproducibility
4. **Per-Dimension Offsets**: `result[:, :, dim_idx] += offset_value`
   - Applied uniformly across all sequence positions
   - **Measured status (2026-08-05, SA3/t5gemma).** This additive step is what the Dimension
     Explorer’s ABSOLUTE mode performs. On the SA1 path it was near-inert (5–25 % signal
     retention); on the shipped SA3 path it is **effective**: injecting ±(emb_a − emb_b) into the
     neutral embedding retains **94 %** of the pole contrast measured as CLAP projection onto the
     intended text axis (d +2.073 vs +2.211), and produces a *larger* raw acoustic change than the
     poles themselves (onset_density d −4.63 vs −2.20). The attention mask is not a factor.
     The SA1 diagnosis (“the model only responds near the manifold of natural encoder outputs”)
     does not hold here. Protocol and limits:
     `docs/analysis/NACHMESSUNG_latent_audio_synth_sa3_2026-08-05.md`.
   - The RELATIVE mode is a per-dimension interpolation between two natural encodings; it is
     monotone in t, the half span delivering 56 % of the pole effect.

### Diff-Based Dimension Sorting (Feature Probing)

When two prompts are provided, `_compute_stats()` computes:
```python
diff = emb_a.mean(dim=0) - emb_b.mean(dim=0)  # [768]
sort_order = diff.abs().argsort(descending=True)
```

Dimensions are sorted by **discriminative power** — which features most distinguish the two concepts. The canvas shows the most distinctive dimensions first (left side), making it immediately visible which dimensions encode the semantic difference between the prompts.

Single-prompt fallback: sort by activation magnitude.

---

## Implementation

### Backend: GPU Service

#### `CrossmodalLabBackend.synth()` (cross_aesthetic_backend.py)

```python
async def synth(
    prompt_a: str,
    prompt_b: Optional[str] = None,
    alpha: float = 0.5,
    magnitude: float = 1.0,
    noise_sigma: float = 0.0,
    dimension_offsets: Optional[Dict[int, float]] = None,
    duration_seconds: float = 1.0,
    steps: int = 20,
    cfg_scale: float = 3.5,
    seed: int = -1,
) -> Optional[Dict]
```

**Steps:**
1. Encode prompt(s) via `StableAudioGenerator.encode_prompt()` → `[1, seq, 768]`
2. `_manipulate_embedding()` → apply interpolation, magnitude, noise, offsets
3. Merge attention masks: `torch.maximum(mask_a, mask_b)`
4. `_compute_stats(result_emb, emb_a, emb_b)` → activation stats for canvas
5. `StableAudioGenerator.generate_from_embeddings()` → WAV bytes
6. Return `{audio_bytes, embedding_stats, generation_time_ms, seed}`

#### `_compute_stats()` Return Format

```python
{
    "mean": float,
    "std": float,
    "top_dimensions": [{"dim": int, "value": float}, ...],  # Top 10, backward compat
    "all_activations": [{"dim": int, "value": float}, ...],  # All 768, signed, sorted
    "sort_mode": "diff" | "magnitude"
}
```

#### API Endpoint

`POST /api/cross_aesthetic/synth` — Request/response passes through `gpu_service/routes/cross_aesthetic_routes.py`. The `dimension_offsets` dict arrives with string keys from JSON; the backend converts to int on application.

### Frontend: Synth Tab Layout

The synth tab in `crossmodal_lab.vue` is organized top-to-bottom:

1. **Prompts** — Prompt A (required) + Prompt B (optional, for interpolation)
2. **Sliders** — Alpha (-2..3), Magnitude (0.1..5), Noise (0..1)
3. **Parameters** — Duration, Steps, CFG, Seed. A press of Generate takes its seed from the platform's seed automatic (`composables/useSeedAutomatic.ts`, since 2026-10-03): the same seed after a change, a new one when nothing changed, a typed one as typed, and the seed goes into the field. An imported preset that carries a seed of 0 or above gives the next run that seed. The regeneration in time with the beat takes the number in the field.
4. **Action Row** — Generate, Loop toggle, Stop, Play
5. **Dimension Explorer** (open by default)
6. **Looper Widget** (always visible, disabled state when no audio)
7. **MIDI Section** (collapsed by default)

### Dimension Explorer: Canvas Spectral Strip

**Rendering** (`drawSpectralStrip()`):
- Single `<canvas>` element, 120px tall, full width
- **Zero-line** at vertical center
- **768 bars**, each `containerWidth / 768` pixels wide
- Positive activations extend **upward**, negative **downward**
- Bar height: `abs(value) / maxActivation * halfHeight`
- **Activation layer**: muted green `rgba(76, 175, 80, 0.35)`
- **Offset overlay**: bright green `rgba(102, 187, 106, 0.8)`, extends from activation endpoint
- Redraws via `watch(embeddingStats)` and after any offset change

**Interaction** (Vital-style spectral painting):
- **Click+drag vertically** = set offset (-3 to +3, mapped from cursor y-position)
- **Drag horizontally** = paint offset across multiple bars in one stroke
- **Right-click** = clear offset for that dimension
- **Touch events** mirror mouse behavior

**Undo/Redo:**
- History stack (max 50 snapshots), one entry per paint stroke (mousedown→mouseup)
- `Ctrl+Z` = undo, `Ctrl+Shift+Z` / `Ctrl+Y` = redo
- Buttons in controls row (disabled when stack empty)
- Reset-all also pushes to undo stack (reversible)

### Audio Looper (`useAudioLooper.ts`)

The looper is a Web Audio API playback engine with advanced loop processing:

**Loop Processing Pipeline** (applied to buffer, not at playback time):
1. **Cross-Correlation Optimization** — Finds optimal `loopEnd` where waveform end matches waveform start (512-sample window, 2000-sample search radius)
2. **Circular Crossfade** — Equal-power sin/cos blend of tail INTO head region
3. **Shorten** — Move `loopEnd` back by crossfade length

Result: `AudioBufferSourceNode.loop` wraps imperceptibly because the head region already contains the blended tail audio.

**OLA Pitch Shift:**
- Grain size 2048 samples, 75% overlap, Hann window
- Time-stretch via different analysis/synthesis hop ratios, then resample
- Result: pitch change without tempo change

**Pitch Cache:**
- Pre-computes OLA-shifted buffers for -36 to +24 semitones (61 buffers)
- Built asynchronously: one semitone per `setTimeout(fn, 0)`, center-outward order
- MIDI lookup: `pitchCache.get(semitones)` → instant buffer swap (<1ms)
- Invalidated on: new audio, loop bounds change, optimize/normalize toggle

**Equal-Power Crossfade** (source switching):
- Pre-computed sin/cos curves (256 samples)
- Fade-out: `linearRampToValueAtTime(0)` on old gain node
- Fade-in: `setValueCurveAtTime(fadeInCurve)` on new gain node
- Seamless audio transition when regenerating during playback

**Transpose Modes:**
- **Rate mode**: `source.playbackRate = 2^(semitones/12)` — instant, changes tempo
- **Pitch mode**: OLA pitch shift via cache — instant if cached, preserves tempo

### MIDI Integration (`useWebMidi.ts`)

**CC Mappings** (defined in crossmodal_lab.vue):
| CC | Parameter | Range |
|---|---|---|
| CC1 | Alpha | -2.0 to 3.0 |
| CC2 | Magnitude | 0.1 to 5.0 |
| CC3 | Noise | 0.0 to 1.0 |
| CC64 | Loop toggle | >0.5 = on |

**Note Handling:**
- Reference note: C3 (MIDI 60) = 0 semitones
- Every note-on: `looper.setTranspose(note - 60)` (always, instant via cache)
- Generation: only if `synthFingerprint() !== lastSynthFingerprint` (prevents redundant GPU calls)

**Fingerprint** includes all synth params + `dimensionOffsets` → CC knob turns or offset painting triggers regeneration on next note, but repeated notes at same pitch don't.

---

## Performance

| Operation | Latency |
|---|---|
| Prompt encoding (t5gemma) | ~50-100ms per prompt |
| Embedding Manipulation | <1ms |
| Stable Audio Generation (20 steps, 1s) | ~1.2-1.5s |
| Canvas Redraw (768 bars) | ~2-5ms |
| Audio Decode (Web Audio) | ~20-50ms |
| Loop Processing (xcorr + crossfade) | ~30-80ms |
| OLA Pitch Shift (1 semitone) | ~50-200ms |
| Pitch Cache Build (61 semitones) | ~3-5s async |
| Transpose (cached) | <1ms |

**VRAM:** Stable Audio pipeline ~4GB (float16), per-generation ~200-500MB.

---

## File Reference

| File | Role | Lines |
|---|---|---|
| `gpu_service/services/cross_aesthetic_backend.py` | Embedding manipulation + stats | ~255 |
| `gpu_service/services/stable_audio_backend.py` | Prompt encoding + Stable Audio generation | ~803 |
| `gpu_service/routes/cross_aesthetic_routes.py` | REST endpoint `/api/cross_aesthetic/synth` | ~147 |
| `public/.../views/latent_lab/crossmodal_lab.vue` | Full synth UI + canvas + MIDI | ~1950 |
| `public/.../composables/useAudioLooper.ts` | Web Audio looper + OLA + pitch cache | ~590 |
| `public/.../composables/useWebMidi.ts` | Web MIDI API wrapper | ~143 |
| `public/.../src/i18n.ts` | DE + EN translations (`latentLab.crossmodal.synth.*`) | — |

---

## Design Decisions

### Why Canvas, Not DOM Elements?

768 bars with interactive painting (continuous mousemove updates) would cause significant DOM thrashing. A single `<canvas>` with imperative drawing is ~10x faster and avoids layout recalculation.

### Why Diff-Based Sorting?

Random dimension ordering (by index) produces a visually meaningless distribution. Magnitude sorting shows "what's loudest" but not "what matters for the blend." Diff-based sorting answers the most useful question: **which dimensions change most between my two prompts?** — these are the drawbars worth pulling.

### Why OLA Instead of Phase Vocoder?

OLA is simpler, has fewer artifacts for short loops (0.5-2s), and is fast enough when cached. Phase vocoder would preserve spectral detail better for longer audio but adds ~3x complexity and latency.

### Why Pre-Processing Crossfade Instead of Playback-Time?

`AudioBufferSourceNode.loop` has no built-in crossfade API. Playback-time crossfading would require two overlapping sources per loop iteration. Pre-processing the buffer (blending tail into head) gives zero-cost looping via the native loop mechanism.

---

**Document Status:** Active (2026-02-16)
**Maintainer:** AI4ArtsEd Development Team
**Last Updated:** Session — Dimension Explorer implementation
