# TODO: Workshop Replay Evaluation

## Task
Run `simulate_workshop_260305.py` at 1x speed against production (port 17801) and evaluate whether the Session 249 fixes improved performance vs. the real workshop baseline.

## Context
- Session 249 implemented 3 fixes based on Workshop 05.03.2026 analysis:
  1. **ComfyUI queue depth guard** (COMFYUI_MAX_QUEUE_DEPTH=8) in backend_router.py
  2. **T5 tokenizer inference lock** (_inference_lock) in diffusers_backend.py
  3. **GPU service threads** 4 -> 16 in gpu_service/config.py
- Fixes committed in `eb24ab6`
- Workshop baseline: 72-74% success, 22% timeouts, 8.6% safety blocks

## What to do

1. **Ensure clean ComfyUI state** — restart ComfyUI before running so VRAM is clean (previous run had 30GB VRAM occupied by other models, skewing results)

2. **Run the simulation at 1x speed** (NEVER use --fast, the whole point is matching real workshop timing):
   ```bash
   python devserver/testfiles/simulate_workshop_260305.py --speed 1 --port 17801
   ```
   Takes ~35-40 min total (31 min send phase + response wait).

3. **Analyze results** — compare with workshop baseline table in the script output

4. **Check production server terminal** during the run for backend error details (the script now shows full error messages, fixed truncation from `[:60]`)

## Previous run results (dirty VRAM state, not conclusive)
- 66% success (vs 72-74% baseline)
- 5% timeouts (vs 22% — improvement)
- 29% backend errors (vs ~5% — regression, likely due to dirty VRAM state with 30GB occupied)
- 0% queue rejections (queue guard never triggered)
- 0% safety blocks (expected — simulation prompts don't trigger safety)
- Success latency: avg 9.1s, min 6.2s, max 31.9s (fast when it works)

## Key question
The 17 backend errors (all exactly 300s timeout on qwen_img2img) need explanation. With 96GB VRAM and a VRAM manager, model swaps should not cause this. Full error messages from the production terminal are needed.

## Script location
`devserver/testfiles/simulate_workshop_260305.py`

## Technical report
`docs/technical_reports/2026-03-05_workshop_performance.md`
