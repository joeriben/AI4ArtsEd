# Architecture Part 34: Generation Tracker

## Overview

The Generation Tracker is a server-side system that tracks active Stage 4 generations per device. It provides three capabilities:

1. **Queue Transparency**: SSE events inform clients how many generations are running ahead of them.
2. **Per-Device Lock**: Max 1 active generation per `device_id`. Prevents multi-tab spam.
3. **Cancel**: Users can abort running generations, including actual GPU interruption for ComfyUI.

Combined with the frontend **Navigation Lock** (mode-selector links disabled during generation) and the **GenerationButton** (disabled during execution), this creates a three-layer protection system.

## Server-Side Components

### Generation Tracker (`schema_pipeline_routes.py`)

Module-level state, analogous to the existing `_seed_state` pattern:

```python
_generation_tracker_lock = threading.Lock()
_active_generations: dict = {}      # device_id -> {run_id, ts, output_config, comfyui_prompt_id}
_cancelled_generations: set = set() # device_ids with pending cancel
_GENERATION_TRACKER_TTL = 1800      # 30min (> GPU_SERVICE_TIMEOUT_VIDEO=1500s)
```

### Helper Functions

- `_try_acquire_generation(device_id, run_id, output_config) -> (bool, int)`: Atomically checks and registers. Returns `(success, queue_ahead)`. Evicts stale entries (TTL).
- `_release_generation(device_id)`: Removes from tracker + cancel set. Idempotent.
- `_get_active_count() -> int`: Current number of active generations.
- `_is_cancelled(device_id) -> bool`: Check cancel flag.
- `_set_comfyui_prompt_id(device_id, prompt_id)`: Store ComfyUI job ID for cancel support.

### REST Endpoints

- `GET /api/schema/pipeline/generation-active?device_id=X`: Pre-check. Returns `{active, output_config, queue_total}`.
- `POST /api/schema/pipeline/generation-cancel`: Sets cancel flag. For ComfyUI jobs, calls `cancel_job(prompt_id)`.

### SSE Events

- `queue_position`: `{position, active}` — emitted before Stage 4 start and periodically (~5s) during progress loops.
- `cancelled`: `{run_id, stage}` — emitted when cancel flag detected. Stage is `pre_generation`, `during_generation`, or `post_generation`.
- `error` with `code: 'device_busy'`: Emitted when device already has active generation.

### Cancel Flow

```
User clicks "Cancel previous generation" (Tab 2)
  -> POST /pipeline/generation-cancel {device_id}
  -> Server sets _cancelled_generations.add(device_id)
  -> If ComfyUI: calls cancel_job(prompt_id) -> actual GPU interrupt
  -> Progress loop in Tab 1 detects _is_cancelled(device_id)
  -> Emits SSE 'cancelled' event
  -> return -> finally -> _release_generation(device_id)
  -> Tab 2 re-checks generation-active -> active: false -> button enabled
```

### Cancel Check Points

1. **Between Stage 3 and Stage 4**: Prevents GPU start entirely.
2. **During progress loop** (~1-5s interval): Stops streaming, GPU may continue (Diffusers) or actually stop (ComfyUI).
3. **After GPU result, before VLM safety check**: Saves the VLM API call.

### ComfyUI Cancel Support

The `prompt_id` flows from ComfyUI submission back to the tracker:

```
comfyui_ws_client.submit_and_track()
  -> _submit_workflow() returns prompt_id
  -> on_progress callback receives special "submitted" event with prompt_id
  -> Progress loop in schema_pipeline_routes detects event_type == 'submitted'
  -> _set_comfyui_prompt_id(device_id, prompt_id)
```

On cancel, the endpoint calls `client.cancel_job(prompt_id)` which:
- Interrupts the job if currently running
- Removes from queue if pending

### Critical: `generation_acquired` Flag

The SSE generator function has a `finally` block that always runs (even on `return` from generator). Without the `generation_acquired` flag, a `device_busy` rejection would release the RUNNING generation's lock in the finally block.

```python
generation_acquired = False
try:
    success, ahead = _try_acquire_generation(device_id, run_id, output_config)
    if not success:
        yield error event
        return  # finally still runs!
    generation_acquired = True
    # ... Stage 4 ...
finally:
    if generation_acquired:  # Only release if WE acquired it
        _release_generation(device_id)
```

## Frontend Components

### generationLockStore (`stores/generationLock.ts`)

Pinia store with single `isGenerating` ref. Set by `useGenerationStream` on `executeWithStreaming()` start, cleared on every exit path (complete, error, cancelled, blocked).

### Navigation Lock (`App.vue`)

All mode-selector `router-link` elements receive:
- `:class="{ locked: generationLock.isGenerating }"` — grays out (opacity 0.2)
- `@click="guardGenerating"` — `e.preventDefault()` when locked

Follows the existing `guardAdvanced` / `locked` pattern for kids mode.

### GenerationButton Props

| Prop | Type | Purpose |
|------|------|---------|
| `queuePosition` | number | Queue transparency display |
| `deviceBusy` | boolean | Pre-check result |
| `preChecking` | boolean | REST check in progress |

Button states: `preChecking` (pulse `. . .`) -> `deviceBusy` (red "Cancel previous") -> `executing` (normal) -> idle.

### deviceBusy Auto-Clear

`checkDeviceActive()` starts a 3s polling interval while `deviceBusy === true`. Stops automatically when backend returns `active: false`. Prevents stale "Cancel" button after generation completes.

## Compare Views / ai_persona

These views intentionally fire parallel generations. Per-slot device_id suffixes prevent lock conflicts:
- model_comparison: `${deviceId}_cmp${i}`
- language_comparison: `${deviceId}_cmp${i}`
- ai_persona: `${deviceId}_persona${Date.now()}`

## Related Architecture Parts

- **Part 29**: Safety System (Stage 3/4 checks that cancel can skip)
- **Part 31**: GPU Service (Diffusers CUDA limitations on cancel)
- **Part 33**: Compare Hub (parallel generation pattern)
