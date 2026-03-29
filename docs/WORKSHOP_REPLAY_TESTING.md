# Workshop Replay Testing

## Purpose

Workshop replay scripts reproduce the exact load pattern of a real workshop session against the dev or production server. They verify that backend changes (model swaps, infrastructure migrations, etc.) don't break anything under realistic conditions.

## Scripts

Located in `devserver/testfiles/simulate_workshop_YYMMDD.py`:

| Script | Date | Requests | Key configs |
|--------|------|----------|-------------|
| `simulate_workshop_260305.py` | 05.03.2026 | ~59 | sd35_large, qwen_img2img |
| `simulate_workshop_260306.py` | 06.03.2026 | ~80 | sd35_large, qwen_img2img, gemini |
| `simulate_workshop_260319.py` | 19.03.2026 | ~90 | sd35_large, qwen_img2img, qwen_2511_multi |
| `simulate_workshop_260320.py` | 20.03.2026 | 104 | sd35_large, qwen_img2img, qwen_2511_multi, wan22_i2v_video |
| `simulate_workshop_260327.py` | 27.03.2026 | 53 | sd35_large, qwen_img2img, qwen_2511_multi, flux2, wan22_i2v_video, hunyuan3d_text_to_3d |

## How to run

```bash
# Standard run (default, correct for all stress tests):
python devserver/testfiles/simulate_workshop_260327.py

# Dry run (shows timing, sends nothing):
python devserver/testfiles/simulate_workshop_260327.py --dry-run

# Without img2img (all image configs fall back to sd35_large):
python devserver/testfiles/simulate_workshop_260327.py --no-image

# Against production:
python devserver/testfiles/simulate_workshop_260327.py --port 17801
```

## CRITICAL RULES for creating/running replay scripts

### 1. ORIGINAL PROMPTS ONLY

Every prompt in the script MUST come from the actual backend log. Sources:
- **RECORDER export files** (`exports/json/YYYY-MM-DD/{device}/{run}/`): `001_input.txt` (original input), `01_generation_prompt.txt` (for persona-generated)
- **Backend log** `[CHUNK-CONTEXT] input_text:` lines (for intercepted configs, find the German original BEFORE Stage 2)
- **Backend log** `[STAGE4-GEN]` lines (for passthrough configs like qwen_img2img, the prompt IS the original)

NEVER invent synthetic prompts.

### 2. REAL TIMING with queue drain

- Gaps between requests are preserved exactly as in the workshop
- Large gaps (> `max-gap`, default 15s) are capped, BUT the queue is drained first (wait for all pending requests to finish, then continue immediately)
- This matches real workshop behavior: during pauses, pending generations complete before new ones arrive
- Bursts (gaps < max-gap) run through without draining — just like in the real workshop
- NEVER use speed multipliers (4x etc.) — they distort the load pattern and make the test meaningless

### 3. VERIFY ALL BACKENDS BEFORE RUNNING

The script checks automatically, but verify manually if in doubt:
- **DevServer**: `curl http://localhost:17802/health`
- **GPU Service**: `curl http://localhost:17803/api/health`
- **ComfyUI**: `curl http://127.0.0.1:17804/system_stats`

### 4. CHECK EVERY CONFIG'S INPUT REQUIREMENTS

Read the output config JSON to understand what each config needs:
- `qwen_img2img`: needs `input_image`
- `wan22_i2v_video`: needs `input_image` (Image-to-Video!)
- `qwen_2511_multi`: needs `input_image1`, `input_image2`, `input_image3`
- `sd35_large`, `flux2`, `hunyuan3d_text_to_3d`: text-only

### 5. DEVICE POOL

Scripts simulate 7 devices (matching real workshop iPad count). Each device can only run one generation at a time — a device lock prevents concurrent requests from the same device, just like a real iPad waiting for its result.

## How to create a new replay script

1. Get the backend log: `~/Documents/AI4ArtsEd_technische_Protokolle/ai4artsed_production/Teilprotokoll DD M YYYY backend.txt`
2. Count STAGE4-GEN entries: `grep -c "STAGE4-GEN.*Executing generation with config" log.txt`
3. Get config distribution: `grep "STAGE4-GEN.*Executing generation" log.txt | sed "s/.*config '\([^']*\)'.*/\1/" | sort | uniq -c | sort -rn`
4. Extract full prompts from RECORDER exports (NOT from truncated log lines)
5. Compute time offsets from the first STAGE4-GEN timestamp
6. For intercepted configs (sd35_large, flux2 when not persona): find the German original from `[CHUNK-CONTEXT] input_text:` BEFORE the interception pipeline
7. For persona-generated configs (flux2 from Trashy): use the `01_generation_prompt.txt` from RECORDER — the English prompt IS the original
8. Follow the template structure from the most recent existing script

## Log locations

- Backend logs: `~/Documents/AI4ArtsEd_technische_Protokolle/ai4artsed_production/`
- RECORDER exports: `/run/media/joerissen/production/ai4artsed_production/exports/json/YYYY-MM-DD/`
- Technical reports: `docs/technical_reports/`
