# DevServer Architecture

**Part 27: VRAM Management & GPU Model Cache**

---

## Overview

The Diffusers backend manages GPU-accelerated image generation models (SD3.5 Large, SD3.5 Turbo, future video models) that each consume 24-28GB VRAM. In workshop scenarios with ~10 concurrent users, participants switch between models frequently. This architecture provides:

1. **Multi-Model GPU Cache** — Multiple models cached on GPU, evicted via LRU when VRAM is needed
2. **LRU Eviction** — Least-recently-used models are fully deleted to free VRAM for new loads
3. **Reference Counting** — Models in active use are never evicted mid-inference

---

## History

**Original design:** Three-tier memory hierarchy (GPU VRAM → CPU RAM → Disk) with CPU offloading inspired by ComfyUI. Added `device_map="balanced"` and `enable_model_cpu_offload()` for Flux2.

**Simplified (2026-02-14):** CPU offloading layer removed. `pipe.to("cpu")` / `pipe.to("cuda")` round-trips caused pipeline state corruption (stale accelerate hooks, wrong device placement). The `device_map="balanced"` code path (added for Flux2) never worked. The 16GB RAM reserve check (`DIFFUSERS_RAM_RESERVE_AFTER_OFFLOAD_MB`) silently prevented model loading. Startup preloading removed — first request cold-loads, subsequent requests reuse GPU cache.

**Current design:** Models are either on GPU (in `_pipelines` dict) or not loaded. Eviction = full `del` + `torch.cuda.empty_cache()`. Next use reloads from disk (~10s).

---

## Architecture

### Component Diagram

```
┌────────────────────────────────────────────────────────────┐
│               DiffusersImageGenerator                       │
│                                                             │
│  State:                                                     │
│  ├── _pipelines: Dict[model_id → pipeline]    (GPU only)   │
│  ├── _model_last_used: Dict[model_id → timestamp]          │
│  ├── _model_vram_mb: Dict[model_id → measured MB]          │
│  ├── _model_in_use: Dict[model_id → refcount]              │
│  └── _load_lock: threading.Lock                             │
│                                                             │
│  Methods:                                                   │
│  ├── _load_model_sync()      ← all loading goes through    │
│  ├── _ensure_vram_available() ← evict LRU (full delete)    │
│  ├── load_model()            ← async wrapper                │
│  ├── unload_model()          ← hard unload                  │
│  └── generate_image()        ← refcount guarded             │
└────────────────────────────────────────────────────────────┘
```

### Data Flow: Model Loading

```
Request for model_id X
         │
         ▼
    _load_model_sync(X)
         │
    ┌────┴────┐
    │ Acquire │
    │  _load  │
    │  _lock  │
    └────┬────┘
         │
    X in _pipelines? ──yes──▶ Update last_used, return (instant)
         │
         │ no (cold load from disk)
         ▼
    _ensure_vram_available(inf)  ← evict all evictable models
         │
    PipelineClass.from_pretrained()   ← ~10s from disk
    pipe.to("cuda")
    enable_attention_slicing()
         │
    Measure VRAM delta
    Store in _model_vram_mb[X]
         │
    _pipelines[X] = pipe
    _model_last_used[X] = now
         │
    Release _load_lock
```

### Data Flow: VRAM Eviction

```
_ensure_vram_available()
         │
    Free VRAM >= target? ──yes──▶ return (nothing to do)
         │ no
         ▼
    Find LRU model in _pipelines
    where _model_in_use[id] <= 0
         │
    ┌────┴────┐
    │ Found?  │──no──▶ Log warning, return (all in-use)
    └────┬────┘
         │ yes
         ▼
    del _pipelines[evict_id]     ← full delete
    Clean up tracking dicts
    torch.cuda.empty_cache()
         │
    Log: [DIFFUSERS] Evicted {id} ({freed}MB VRAM freed)
         │
    Repeat check (free VRAM >= target?)
```

### Data Flow: Image Generation (Refcount Guard)

```
generate_image(model_id=X)
         │
    Ensure model loaded (load_model)
         │
    _model_in_use[X] += 1   ← protects from eviction
         │
    try:
    │   pipe = _pipelines[X]
    │   result = pipe(prompt, ...)
    │   return PNG bytes
    finally:
    │   _model_in_use[X] -= 1   ← releases protection
```

---

## Configuration

**File:** `gpu_service/config.py` (the DevServer's copy of the constant had no reader and was struck in stage 8)

| Setting | Default | Description |
|---------|---------|-------------|
| `DIFFUSERS_VRAM_RESERVE_MB` | `3072` | Minimum free VRAM (MB) to keep for inference overhead (latents, VAE, scheduler). |

---

## Feature Probing Error Propagation

`generate_image_with_probing()` returns `{'error': '...'}` dicts instead of `None` on failure. This ensures the actual exception message reaches the frontend via `BackendResponse.error` instead of the opaque "Backend error: None".

Three failure points return structured errors:
1. Model loading failure → `{'error': 'Model loading failed for {model_id}'}`
2. Missing encoder methods → `{'error': 'Pipeline missing _get_clip_prompt_embeds or _get_t5_prompt_embeds'}`
3. Any exception during generation → `{'error': str(e)}`

---

## Model VRAM Measurements

VRAM usage is measured empirically (delta of `torch.cuda.memory_allocated()` before and after loading), **not** from chunk metadata.

| Model | Pipeline Class | Measured VRAM (fp16) |
|-------|---------------|---------------------|
| SD3.5 Large | StableDiffusion3Pipeline | ~28 GB |
| SD3.5 Turbo | StableDiffusion3Pipeline | ~28 GB |

---

## Workshop Scenario: Model Switching

```
Time  User     Action                     GPU VRAM
──────────────────────────────────────────────────────
0:00  -        Server started             (empty)
0:15  Alice    Generate (SD3.5-large)     Loading from disk (~10s)
0:25  Alice    ...                        SD3.5-large (28GB)       ← cached
0:30  Alice    Generate (SD3.5-large)     SD3.5-large (28GB)       instant (cached)
0:45  Bob      Generate (SD3.5-turbo)     Evict large, load turbo (~10s)
0:55  Bob      ...                        SD3.5-turbo (28GB)       ← cached
1:00  Alice    Generate (SD3.5-large)     Evict turbo, load large (~10s)
```

**Trade-off:** Without CPU offloading, every model switch is ~10s (disk reload). This is acceptable because:
- Most workshops use a single model
- CPU offloading caused pipeline corruption bugs that made the system unreliable
- Reliability > speed for educational contexts

---

## Failsafe Analysis

| Scenario | Risk | Mitigation |
|----------|------|------------|
| **Eviction during active generation** | Model deleted mid-inference → crash | `_model_in_use` refcount. Eviction skips models with refcount > 0. |
| **All models in-use, need VRAM for new model** | Cannot evict, cannot load | Load attempt proceeds (may OOM). Exception caught, returns error. Active generations continue. |
| **Concurrent requests for different models** | Race condition | `_load_lock` serializes all load/evict operations. |
| **CUDA OOM during loading** | GPU state corruption | Caught in `_load_model_sync()`. `empty_cache()` in error path. Returns `False`. |
| **Model not downloaded yet (first run)** | Downloads from HuggingFace | `from_pretrained()` handles download. May take minutes but runs in thread. |

### Concurrency Invariants

1. **Loading is serialized**: `_load_lock` ensures exactly one load/evict operation at a time
2. **Eviction is safe**: A model with `_model_in_use[id] > 0` is never evicted
3. **Refcount is balanced**: `try/finally` ensures decrement even on generation errors
4. **No deadlock**: `_load_lock` is the only lock. `generate_image()` never acquires it.

---

## Files

| File | Purpose |
|------|---------|
| `gpu_service/config.py` | `DIFFUSERS_VRAM_RESERVE_MB` |
| `gpu_service/services/diffusers_backend.py` | GPU cache, LRU eviction, refcount |

---

## Removed Components

These were part of the original three-tier design and have been removed:

| Component | Why removed |
|-----------|-------------|
| `_offload_to_cpu()` | `pipe.to("cpu")` + `pipe.to("cuda")` corrupts pipeline state |
| `_move_to_gpu()` | No CPU→GPU moves without CPU offloading |
| `_model_device` dict | Models are either in `_pipelines` (on GPU) or not loaded |
| `_get_available_ram_mb()` | No RAM checks needed |
| `enable_cpu_offload` parameter | Flux2 never worked with `device_map="balanced"` |
| `DIFFUSERS_RAM_RESERVE_AFTER_OFFLOAD_MB` | 16GB RAM check silently prevented model loading |
| `DIFFUSERS_PRELOAD_MODELS` + warmup thread | First request cold-loads, subsequent reuse cache |

---

## NVML Watchdog — Real GPU Visibility

### Problem

`torch.cuda.memory_allocated()` only sees PyTorch's own tensors. Foreign GPU processes (Ollama, ComfyUI, SwarmUI zombies) are invisible. On the RTX 6000 Blackwell (96GB), zombie SwarmUI instances regularly consume 25-52 GB, causing:
- `get_free_vram_mb()` overestimates free VRAM (reports 90 GB when 40 GB is actually free)
- Large model loads (Wan 2.2 = 40 GB) OOM
- Ollama falls back to CPU inference (slow safety checks)
- No warnings — silent degradation

### Solution: NVML + Dynamic Thresholds

The `VRAMCoordinator` now uses NVIDIA Management Library (NVML) via `pynvml` for real GPU visibility:

```
┌─────────────────────────────────────────────┐
│  VRAMCoordinator                            │
│                                             │
│  NVML Layer:                                │
│  ├── _get_nvml_memory_info()  ← real GPU    │
│  ├── _get_expected_foreign_vram_mb()        │
│  │     └── Ollama /api/ps + ComfyUI port    │
│  ├── _check_foreign_processes()             │
│  │     └── actual vs expected threshold     │
│  ├── _check_blacklisted_ports()             │
│  │     └── 7801, 7821, 8188 = SwarmUI       │
│  ├── _owned_labels()                        │
│  │     └── PIDs this service SPAWNED        │
│  │        (the llama-server children)       │
│  └── _nvml_snapshot()                       │
│        └── one enumeration, cached ~1 s     │
│                                             │
│  PyTorch Layer (original):                  │
│  ├── _collect_all_models()                  │
│  ├── _do_eviction()                         │
│  └── request_vram()                         │
└─────────────────────────────────────────────┘
```

### Owned GPU Processes — the `llama-server` Children

Since the LLM/VLM engine runs one supervised `llama-server` process per model alias (Part 31), this service's own models live **outside** this PID. NVML reports them like any stranger, and without a correction the coordinator would count 20 GB of its own checking model as somebody else's, warn about it on every load, and offer it to kill-foreign.

**The registry, never the command line.** `register_owned(pid, starttime, label, confirm)` is asserted by whoever spawned the process. Ownership is never inferred from a port, a model path or a command line — each of those can belong to a different process a moment later, and a PID is reused within hours on a busy box. It holds only while the registering backend confirms that the same process is still there (alive, born at the recorded moment, still carrying its ownership marker). An entry that cannot be confirmed is dropped on the spot, so a child that died between two NVML reads stops being an exception to the foreign rule at once.

**What changes in the enumeration.** An owned PID is marked `foreign: false, owned: true` with its `label`, and its real `cmdline` is kept alongside, so the log still says which process the label belongs to. `_process_tag()` prints the label instead of `[FOREIGN]`. `foreign_mb` **excludes** owned children — they already stand in `loaded_models`, and counting them twice is what made the foreign-VRAM threshold fire on the platform's own loads. `_check_foreign_processes()` skips them.

**One enumeration, cached ~1 s.** `_nvml_snapshot(max_age_s)` serves the callers that ask often and can live with a figure a moment old: the per-PID reading, `_collect_all_models()`, `get_status()`. The child supervisor polls one child through a load and again through a termination, several times a second, for a figure that cannot have changed between two of those calls — without the cache each of those polls walks every process on the card. The callers that must be current — the sensor-health check, free VRAM, the foreign-process check, the emergency path — call `_get_nvml_memory_info()` directly and refresh the cache in passing.

**Per-PID, not per-process.** `get_process_vram_mb(pid)` is the honest reading for a model that llama.cpp allocates outside the torch allocator, in a process that is not this one; `torch.cuda.memory_allocated()` can answer for neither. `None` covers three things and each of them is "no figure": the PID holds nothing, NVML is mute, or NVML lists the process without being able to attribute its memory (`vram_unknown`). What it never covers is zero — a resident model reported as 0 MB is room this coordinator would hand out twice.

### Dynamic Expected Threshold

Rather than a static "foreign VRAM budget," the expected threshold **adapts automatically**:

| Component | Method | Adapts when... |
|-----------|--------|----------------|
| Ollama models | `GET /api/ps` → sum `size_vram` | Safety models load/unload (kids↔adult) |
| ComfyUI | Port `COMFYUI_PORT` (17804) listening → +1024 MB | ComfyUI starts/stops |
| Overhead | `VRAM_FOREIGN_OVERHEAD_MB` (2048 MB) | Fixed (CUDA contexts, driver, display) |

When `actual_foreign > expected_foreign`, the coordinator logs warnings with PIDs, cmdlines, and VRAM per process.

### Port Blacklist

Ports 7801, 7821, 8188 are SwarmUI ports that must NEVER be active. Detection via `socket.connect_ex()` (<1ms). Active blacklisted ports are:
- Logged with full PID/cmdline identification (via `psutil`)
- Exposed in `/api/health/vram` response
- Killable via `POST /api/health/kill-foreign` (with safety rails)

### Kill Endpoint Safety Rails

`POST /api/health/kill-foreign {"pid": N}` validates before killing:
1. PID must NOT be our own process
2. PID must NOT be a **child of this service**. An owned PID is refused (403) with a sentence naming what it is: killing a model process behind the coordinator's back leaves that model standing in the ledger, and the next request is handed a port nothing listens on. The way to end one is `POST /api/llm/unload` with `{"force": true}`, which takes it out of the ledger too. This rail is checked *before* the foreign-list rail, because a child would otherwise be refused with "not a foreign GPU process" — true, and useless
3. PID must be in NVML's foreign GPU process list
4. PID must NOT be expected ComfyUI on `COMFYUI_PORT`
5. SIGTERM → 2s grace → SIGKILL escalation

### Fail-Open Design

Every NVML component fails open:
- `nvidia-ml-py` missing → PyTorch fallback (blind but functional)
- NVML query fails → PyTorch fallback
- Ollama unreachable → assume 0 expected Ollama VRAM
- `/proc/{pid}/cmdline` read fails → `"(unknown)"`
- Port check fails → assume port clear
- Owned-PID confirmation fails or raises → the PID stops counting as ours. This one fails toward **visible**, not toward silence: an unconfirmable child becomes foreign again, is warned about, and can be killed — the opposite direction would hide a stranger behind our label

### Configuration

**File:** `gpu_service/config.py`

| Setting | Default | Description |
|---------|---------|-------------|
| `VRAM_USE_NVML` | `true` | Enable NVML real GPU visibility |
| `VRAM_FOREIGN_OVERHEAD_MB` | `2048` | Expected baseline foreign VRAM (CUDA contexts, driver, display) |
| `VRAM_BLACKLISTED_PORTS` | `[7801, 7821, 8188]` | SwarmUI ports — detection triggers warning |
| `OLLAMA_API_URL` | `http://localhost:11434` | Ollama API for `/api/ps` model inventory |
| `COMFYUI_PORT` | `17804` | Expected ComfyUI port (tolerated, not killed) |

### `/api/health/vram` Extended Response

```json
{
  "free_mb": 42000,
  "total_mb": 97887,
  "nvml_available": true,
  "nvml_free_mb": 42000,
  "nvml_used_mb": 55887,
  "foreign_vram_mb": 60350,
  "expected_foreign_vram_mb": 8200,
  "gpu_processes": [
    {"pid": 493620, "vram_mb": 2312, "vram_unknown": false, "foreign": true,
     "owned": false, "label": "", "cmdline": "dotnet SwarmUI.dll --port 7801"},
    {"pid": 482447, "vram_mb": 550, "vram_unknown": false, "foreign": true,
     "owned": false, "label": "", "cmdline": "python main.py --port 17804"},
    {"pid": 511903, "vram_mb": 9840, "vram_unknown": false, "foreign": false,
     "owned": true, "label": "llm child — qwen3-vl:8b",
     "cmdline": "llama-server -m .../Qwen3-VL-8B-Q8_0.gguf --mmproj ... --port 17810"}
  ],
  "blacklisted_ports": [],
  "registered_backends": ["diffusers", "heartmula"],
  "loaded_models": [],
  "eviction_in_progress": false
}
```

`owned` and `label` are additive. An entry with `owned: true` is one of this service's own `llama-server` children: neither this process nor a stranger, and a reader who cannot tell those apart has no way to see whose the memory is. `foreign_vram_mb` counts strangers only — an owned child is already listed under `loaded_models`. `vram_unknown: true` means NVML listed the process but could not attribute its memory; that is *not* 0 MB, and the ledger keeps the last figure rather than reading it as an empty card. The whole answer comes from **one** NVML enumeration — the model collection takes it and the process list reads the same one back out of the cache, so the two halves of a status page cannot disagree about which processes are on the card.

### Emergency Reclaim — Owned Children First

`emergency_reclaim_foreign()` runs on runtime **sensor loss**, to put the card back into a state torch can measure: afterwards this process is meant to be the only GPU user. The `llama-server` children are the permanent exception to that sentence, so they are ended first, through `terminate_owned()` and the terminator each backend registered (`register_owned_terminator`). A reclaim that left them standing would leave exactly the blind spot it was called to remove — torch cannot see them, and the sensor that could is the one that just went. They are also the cheapest thing on the card to lose: the next request spawns one again.

Order: **owned children** → `forget_resident()` on the admission gate (Part 40) → hard restart of ComfyUI's systemd unit if it is listening → SIGKILL for blacklisted-port PIDs that NVML actually reports as GPU users. Backends inside *this* process are not touched here — they are this process; the gate clears them by restarting itself while idle.

### Cross-Process ComfyUI Eviction

When internal backend eviction isn't enough, `_try_comfyui_eviction()` asks ComfyUI to release VRAM via `POST /free {"unload_models": true, "free_memory": true}` as a **last resort**.

**Design:**
- **Last resort only**: Called after all internal eviction fails (or `inf` request with <50% VRAM free)
- **All-or-nothing**: ComfyUI's API only supports "unload everything" — no selective model unload
- **NVML-verified**: Measures actual VRAM delta (polls up to 5s). CUDA memory return can be slow (~10s for 22 GB), but the subsequent model load gives enough time
- **Fail-open**: ComfyUI unreachable → skip, return 0. Never blocks eviction
- **Asymmetric**: GPU service can evict ComfyUI, not vice versa — the coordinator is the VRAM authority

---

## Relationship to Other Components

- **Backend Registry** (Part 8): VRAM management is internal to `DiffusersImageGenerator`. The registry's `min_vram_gb` gate is a coarse check; the VRAM manager provides fine-grained runtime control.
- **SwarmUI Manager** (Part 8): Orthogonal. SwarmUI manages ComfyUI process lifecycle; VRAM manager handles Diffusers pipeline objects. The NVML watchdog detects SwarmUI zombies on blacklisted ports.
- **LoRA Training** (Part 23): Training requires ~50GB VRAM. All cached models should be unloaded before training.

---

## Design Rationale

**Why full delete instead of CPU offloading?**
CPU offloading (`pipe.to("cpu")` / `pipe.to("cuda")`) caused pipeline state corruption — stale accelerate hooks, components on wrong devices, suppressed warnings hiding real errors. The ~1s reload benefit wasn't worth the reliability cost in educational contexts.

**Why measure VRAM empirically?**
Chunk metadata `gpu_vram_mb` values are inaccurate (SD3.5: claims 8GB, uses 28GB). Only `torch.cuda.memory_allocated()` deltas are reliable.

**Why `threading.Lock` instead of `asyncio.Lock`?**
`_load_model_sync()` runs via `asyncio.to_thread()` — real OS threads. `asyncio.Lock` doesn't work across threads.

---
