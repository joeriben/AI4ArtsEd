# Stage 2 LLM Model Comparison — 2026-03-21

## Executive Summary

Systematic evaluation of 9 LLM alternatives to Claude Sonnet 4.6 for Stage 2 (Prompt Interception). Tested across 8 difficult configs (Round 1) and all 32 text_transformation configs (Round 2, Gemini 3 Flash only). ~450 API calls total via Mammouth.

**Recommendation**: Current configuration (Sonnet 4.6) is optimal for quality. Gemini 3 Flash is the strongest alternative (100% reliable, 2.7x faster, ~85-90% quality). However, the primary cost driver is Trashy on Opus — not Stage 2. Splitting CHAT_HELPER_MODEL (Sonnet) from PERSONA_MODEL (Opus) saves more than any Stage 2 switch.

## Models Tested

| Model | Provider | Reliability | Avg Latency | Cost vs Sonnet |
|---|---|---|---|---|
| **Claude Sonnet 4.6** | Mammouth | 100% (24/24) | 13.1s | 1x (baseline) |
| **Gemini 3 Flash** | Mammouth | **100% (24/24)** | **3.3s** | ~5x cheaper |
| **Claude Haiku 4.5** | Mammouth | 100% (24/24) | 7.3s | ~3.75x cheaper |
| DeepSeek V3.2 | Mammouth | 100% (24/24) | 11.5s | ~5x cheaper |
| Llama 4 Maverick | Mammouth | 100% (24/24) | 5.6s | ~5x cheaper |
| DeepSeek R1 | Mammouth | 92% (22/24) | 8.6s | ~5x cheaper |
| GPT-5-mini | Mammouth | 71% (17/24) | 10.9s | — |
| GLM-5 | Mammouth | 83% (20/24) | 31.8s | ~5x cheaper |
| Kimi-2.5 | Mammouth | 67% (16/24) | 19.2s | ~5x cheaper |

## Disqualified (Reliability)

- **GLM-5**: 504 Gateway Timeouts, extremely slow (31.8s avg)
- **Kimi-2.5**: 33% null-content failure rate
- **GPT-5-mini**: 29% error rate (400 errors + empty outputs)
- **DeepSeek R1**: Truncated outputs (Hoelderlin: 8 words)

## Quality Analysis — Critical Configs

### Hoelderlin (Material Collision with Poetry)
The hardest test — requires genuine poetic fusion, not description.

- **Sonnet 4.6**: Rewrites Hoelderlin's verse meter with input woven in. Brilliant.
- **DeepSeek V3.2**: Best non-Sonnet result — actually continues the poem ("Geh! hinaus, Freund!")
- **Llama 4 Maverick**: Clever inversion ("Komm! ins Trockene, Freund!") but short
- **Gemini 3 Flash**: Describes the poem's themes. Competent but no collision.
- **Haiku 4.5**: Wrote a Wikipedia article about the water cycle. Total failure.

### Mad World (Genuine Dada vs. Conventional Satire)
- **Sonnet 4.6**: "Die Stille ist das Rechteck, in das kein Pfeil zeigt." Genuine absurdism.
- **Gemini 3 Flash**: "heraus fällt eine Kette unbeschrifteter Aktenordner" — surprisingly good Dada
- **DeepSeek V3.2**: Good absurdist imagery
- **Haiku 4.5**: Conventional satire, not genuine absurdism

### Sensitive (Aesthetic Form Selection)
Config requires choosing and naming an aesthetic form of expression.
- **Sonnet 4.6**: Chose haiku poetry form (meta-appropriate), named it
- **Gemini 3 Flash**: Chose "Bewegungsskizze", named it — correct
- **Haiku 4.5**: Wrote prose essay, did not name a form — constraint violation

### Language Matching
- **Llama 4 Maverick**: Responds in French for English inputs — disqualified
- **Sonnet/Haiku/Gemini**: Tend toward German when context is bilingual (config infrastructure issue, not model failure)
- **Sonnet confucianliterati**: Responds in Japanese/Chinese — dense cultural context overwhelms language instruction

## Gemini 3 Flash — Full Comparison (32 Configs)

Round 2: All 32 text_transformation configs, 3 prompts each (2x EN + 1x multilingual), Sonnet vs Gemini.

**Result**: 96/96 success on both sides. Zero errors.

| Metric | Sonnet 4.6 | Gemini 3 Flash |
|---|---|---|
| Success rate | 100% | 100% |
| Avg latency | 9.0s | **3.3s** |
| Avg speedup | — | **2.7x faster** |

Per-config speedups range from 1.0x (theopposite — trivial) to 4.4x (planetarizer — complex).

Quality is close to Sonnet for structured configs (Bauhaus, Daguerreotype, Planetarizer, Photography). Falls short on poetic collision (Hoelderlin) and meta-cognitive form selection (Sensitive).

## Cost Analysis

The primary cost driver is **NOT Stage 2** but **Trashy (Chat Helper)**:

| Call | Model | Est. Cost/Generation |
|---|---|---|
| **Trashy Auto-Comment** | Opus 4.6 | ~$0.025 |
| **Trashy Chat** (per message) | Opus 4.6 | ~$0.040 |
| Stage 2 Interception | Sonnet 4.6 | ~$0.007 |
| Stage 3 Safety (kids/youth) | Sonnet 4.6 | ~$0.003 |

**Action taken**: Split `CHAT_HELPER_MODEL` (now Sonnet) from `PERSONA_MODEL` (Opus only for persona mode). Saves ~60% of chat costs.

## Actions Taken (This Session)

1. **PERSONA_MODEL split**: `CHAT_HELPER_MODEL` → Sonnet, new `PERSONA_MODEL` → Opus (only for persona_mode)
2. **STAGE1_VISION_MODEL removed**: Dead code — never called in pipeline, removed from config/UI/types
3. **IMAGE_ANALYSIS_MODEL**: Default changed from qwen3-vl:32b to qwen3-vl:2b (VRAM conflict with GPU service)
4. **Settings UI labels**: Renamed from internal stage numbers to functional names (Translation Model, Transformation Model, etc.)

## Raw Data

Test scripts and full JSON/Markdown results:
- `devserver/tests/stage2_model_comparison.py` — Round 1 (9 models, 8 configs)
- `devserver/tests/stage2_gemini_full_comparison.py` — Round 2 (Gemini vs Sonnet, 32 configs)
- `devserver/tests/results/stage2_comparison_20260321_110000.json` — Haiku/GLM/Kimi results
- `devserver/tests/results/stage2_comparison_20260321_114651.json` — GPT-5-mini/Gemini/DeepSeek/Llama results
- `devserver/tests/results/gemini_full_20260321_122211.json` — Full 32-config Gemini comparison
- Markdown reports (.md) alongside each JSON

## Next Steps (Planned)

- **VLM Image Analysis Compare**: New compare tab — multiple local VLMs (qwen3-vl 2b/4b/32b, llama-vision) describe same image with selectable analysis perspectives (Free, Neutral, Safety, Panofsky, Imdahl, Critical). Plan approved, implementation pending.
