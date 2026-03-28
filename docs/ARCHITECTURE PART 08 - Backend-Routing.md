# DevServer Architecture

**Part 8: Backend Routing**

---

## ⚠️ PARTIALLY DEPRECATED (Session 65 - 2025-11-23)

**The execution_mode system described in this document is OBSOLETE.**

**What changed:** The execution_mode parameter ('eco', 'fast', 'local', 'remote') has been REMOVED. Model selection is now centralized in `devserver/config.py`.

**Migration:** See `ARCHITECTURE PART 01 - Section 2: Model Selection Architecture` for current implementation.

**Backend routing patterns (Local LLM, ComfyUI, OpenRouter) remain valid.**

> **Session 292 (2026-03-28):** Ollama replaced by in-process llama-cpp-python in GPU Service.
> `BackendType.OLLAMA` → `BackendType.LOCAL_LLM`. VLM Proxy deleted. All LLM calls route through
> GPU Service `/api/llm/*` endpoints. See DEVELOPMENT_DECISIONS.md for rationale.

---


### Backend Types

| Backend | Type | Use Cases | Authentication | DSGVO |
|---------|------|-----------|----------------|-------|
| **Local LLM** | Local | Text transformation, translation, safety | None (local) | ✅ Compliant |
| **ComfyUI** | Local | Image/Audio/Video generation | None (local) | ✅ Compliant |
| **HeartMuLa** | Local | Music generation (lyrics + tags → MP3) | None (local) | ✅ Compliant |
| **Hunyuan3D** | Local | 3D mesh generation (text → GLB) | None (local) | ✅ Compliant |
| **Blender** | Local | 3D mesh rendering (GLB → PNG thumbnail) | None (local) | ✅ Compliant |
| **OpenRouter** | Cloud | Fast text/image tasks | API Key required | ❌ Non-compliant |
| **OpenAI** | Cloud | GPT-5 Image, Sora2 Video (future) | API Key required | ⚠️ Enterprise only |

---

### Backend-Registry & Fallback Pattern (Session 163)

**Principle:** Direct backends (Diffusers, HeartMuLa, StableAudio) ALWAYS fall back to ComfyUI if unavailable.

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    backends.yaml                             │
│  (Central config: enabled, VRAM requirements, priorities)    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  BackendRegistry                             │
│  is_enabled() → is_available() → get_preferred_backend()    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  backend_router.py                           │
│  _process_stable_audio_chunk():                             │
│    1. Check registry.is_enabled("stable_audio")             │
│    2. Check backend.is_available() (GPU, packages)          │
│    3. Generate via Diffusers                                 │
│    4. ON ANY FAILURE → _process_workflow_chunk() (ComfyUI)  │
└─────────────────────────────────────────────────────────────┘
```

#### Fallback Triggers

Direct backends fall back to ComfyUI when:
1. **Disabled in config:** `backends.yaml` has `enabled: false`
2. **Missing packages:** Required Python packages not installed
3. **Insufficient VRAM:** GPU memory below `min_vram_gb` threshold
4. **Generation failure:** Any exception during inference
5. **Empty result:** Backend returns None/empty

#### Configuration

**File:** `devserver/config/backends.yaml`

```yaml
backends:
  stable_audio:
    enabled: true
    media_types: [audio]
    requirements:
      min_vram_gb: 8
      packages: [diffusers]
    config:
      torch_dtype: float16

settings:
  fallback_to_comfyui: true  # Global fallback enable
```

#### Code Pattern (MANDATORY for all direct backends)

**Generic Fallback Method:** `BackendRouter._fallback_to_comfyui()`

```python
async def _fallback_to_comfyui(self, chunk, chunk_name, prompt, parameters, reason):
    """
    Generic fallback - loads meta.fallback_chunk and executes via ComfyUI.
    Returns error if no fallback_chunk defined.
    """
    fallback_chunk_name = chunk.get('meta', {}).get('fallback_chunk')
    if not fallback_chunk_name:
        return BackendResponse(success=False, error="No fallback_chunk defined")

    fallback_chunk = self._load_output_chunk(fallback_chunk_name)
    return await self._process_workflow_chunk(fallback_chunk_name, prompt, parameters, fallback_chunk)
```

**Backend Implementation Pattern:**

```python
async def _process_xxx_chunk(self, chunk_name, prompt, parameters, chunk):
    try:
        # 1. Check enabled
        if not registry.is_enabled("xxx"):
            return await self._fallback_to_comfyui(chunk, chunk_name, prompt, parameters, "Backend disabled")

        # 2. Check available
        if not await backend.is_available():
            return await self._fallback_to_comfyui(chunk, chunk_name, prompt, parameters, "Not available")

        # 3. Generate
        result = await backend.generate(...)

        # 4. Check result
        if not result:
            return await self._fallback_to_comfyui(chunk, chunk_name, prompt, parameters, "Empty result")

        return BackendResponse(success=True, ...)

    except Exception as e:
        # 5. Any error → fallback
        return await self._fallback_to_comfyui(chunk, chunk_name, prompt, parameters, f"Error: {e}")
```

**Chunk Requirement:**

Direct backend chunks MUST define `meta.fallback_chunk`:

```json
{
  "name": "output_audio_stableaudio_diffusers",
  "backend_type": "stable_audio",
  "meta": {
    "fallback_chunk": "output_audio_stableaudio"
  }
}
```

#### Priority Chain

When multiple backends support a media type, the registry returns the first available:

```yaml
priorities:
  audio:
    - stable_audio   # Try Diffusers first
    - comfyui        # Fallback to ComfyUI workflow
```

#### Benefits

1. **Resilience:** System always works (ComfyUI as universal fallback)
2. **Performance:** Direct backends faster when available
3. **Workshop-friendly:** Just edit `backends.yaml`, no code changes
4. **VRAM-aware:** Auto-disable high-VRAM backends on low-memory GPUs

---

#### Model Availability Detection (Session 176)

**Problem:** Frontend Vue components check model availability before showing model selection. Previously only ComfyUI was checked — when SwarmUI was down, ALL models appeared unavailable, even Diffusers-based ones.

**Solution:** `ModelAvailabilityService` checks each backend independently.

**Endpoint:** `GET /api/models/availability`

**File:** `devserver/my_app/services/model_availability_service.py`

**Routing by `backend_type` (config's `meta.backend_type`):**

| backend_type | Check Method | Source |
|---|---|---|
| `diffusers` | GPU service `GET /api/diffusers/available` | Port 17803 |
| `heartmula` | GPU service `GET /api/heartmula/available` | Port 17803 |
| `comfyui` / `comfyui_legacy` / `None` | ComfyUI `/object_info` model scan | Port 7821 |
| `openai`, `openrouter`, `config_model` | Always available | Cloud/code-based |

**Caching:** Both ComfyUI and GPU service results cached with 5-minute TTL (class-level dicts, shared across request-scoped instances). `?force_refresh=true` invalidates both caches.

**Response:**
```json
{
  "status": "success",
  "availability": {"flux2_diffusers": true, "sd35_large": true, "flux2": false},
  "comfyui_reachable": false,
  "gpu_service_reachable": true
}
```

**Frontend:** `text_transformation.vue` and `image_transformation.vue` filter model bubbles by `availability[config_id] === true`. No frontend logic changes needed — correct filtering is automatic.

**IMPORTANT:** Every output config MUST have `meta.backend_type` set. Configs without it default to ComfyUI check, which may be wrong at runtime.

---

#### HeartMuLa Backend (Session 156-157)

**Model:** HeartMuLa 3B (heartlib), LLM + Audio Codec architecture
**Location:** `devserver/my_app/services/heartmula_backend.py` (singleton)
**Checkpoint:** `~/ai_tools/heartlib/ckpt/` (HeartMuLa-oss-3B + HeartCodec-oss)
**VRAM:** ~12-16GB (bfloat16 for MuLa, float32 for Codec)
**Config:** `devserver/config.py` → `HEARTMULA_ENABLED`, `HEARTMULA_MODEL_PATH`, `HEARTMULA_DEVICE`

**Execution Path (Python-Chunk Pattern):**
```
Frontend custom_placeholders: { TEXT_1, TEXT_2, temperature, topk, cfg_scale, max_audio_length_ms }
  → schema_pipeline_routes.py: custom_params.update(custom_placeholders)
  → chunk_builder.py: parameters.update(custom_placeholders)
  → output_music_heartmula.py: execute(TEXT_1=lyrics, TEXT_2=tags, ...)
  → heartmula_backend.py: generate_music(lyrics, tags, ...) → MP3 bytes
```

**Tag System:** 8 dimensions (comma-separated, no spaces, underscores for multi-word):
Genre (0.95), Timbre (0.5), Gender (0.375), Mood (0.325), Instrument (0.25), Scene (0.2), Region (0.125), Topic (0.1)

**Generation Parameters:**
| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| temperature | 1.0 | 0.1–2.0 | Creativity/randomness |
| topk | 70 | 10–200 | Token diversity |
| cfg_scale | 3.0 | 0.5–5.0 | Tag adherence strength |
| max_audio_length_ms | 240000 | 30000–240000 | Audio duration |

**Performance Notes:**
- `torch.autocast("cuda", bfloat16)` enables fused RMS-norm kernels
- `torch.compile()` incompatible with heartlib (crashes on batch)
- GPU utilization ~50% is expected (autoregressive LLM inference, batch=1)
- `channel_timeout=600` in server.py for long generation requests

---

### ~~Execution Mode System: eco vs fast~~ [DEPRECATED - Session 65]

**⚠️ THIS SECTION IS OBSOLETE:** The execution_mode parameter system was completely removed in Session 65 (2025-11-23). Model selection is now handled centrally via constants in `devserver/config.py` (STAGE1_MODEL, STAGE2_INTERCEPTION_MODEL, etc.). See ARCHITECTURE PART 01 - Section 2 for current implementation.

**Historical documentation (for reference only):**

The DevServer ~~implements~~ **implemented** a simple **two-mode execution system** that ~~determines~~ **determined** whether tasks run locally or remotely:

| Mode | Priority | Backends | Cost | Speed | DSGVO |
|------|----------|----------|------|-------|-------|
| **eco** | Local resources | Ollama, ComfyUI | Free | Slower | ✅ Compliant |
| **fast** | Cloud APIs | OpenRouter, OpenAI | Paid | Faster | ⚠️ Depends on provider |

**Mode Selection Logic:**
1. **User Switch (Frontend):** User can toggle eco/fast mode in UI
2. **Server Default (server.config.py):** Fallback if no user preference
3. **Config Override (optional):** Specific configs can force eco mode (e.g., DSGVO-sensitive tasks)

---

### Routing Logic Details

#### 1. Text Transformation (LLM Tasks)

**eco mode:**
```python
Backend: Ollama (local)
Models: mistral-nemo, llama3.2, gemma2, qwen2.5-translator
Cost: Free
DSGVO: Compliant (all data stays local)
```

**fast mode:**
```python
Backend: OpenRouter (cloud) - or configured alternative
Models: claude-3.5-haiku, gemini-2.5-pro, mistral-nemo (cloud)
Cost: ~$0.10-0.18 per 1M tokens
DSGVO: Depends on provider (OpenRouter: non-compliant)

Note: Cloud provider is configured in server.config.py
      Administrator decides which services to use based on DSGVO research
```

---

#### 2. Media Generation (Image/Audio/Music/Video)

**2a. Image Generation**

**eco mode:**
```python
Backend: ComfyUI (local)
Models:
  - Stable Diffusion 3.5 Large (default)
  - Flux1 Development
  - SD1.5 / SDXL (legacy)
Cost: Free (GPU usage)
Quality: High (full control over parameters)
Speed: ~20-60 seconds per image
DSGVO: Compliant
```

**fast mode:**
```python
Backend: OpenRouter (cloud)
Model: GPT-5 Image (via OpenRouter or direct OpenAI)
Cost: TBD (GPT-5 pricing not yet public)
Quality: TBD
Speed: ~5-15 seconds per image
DSGVO: Non-compliant (OpenRouter) or Enterprise-only (OpenAI direct)

Status: Planned, not yet implemented
```

---

**2b. Audio Generation (Sound Effects, Ambience)**

**eco mode:**
```python
Backend: ComfyUI (local)
Model: Stable Audio Open
Input: Single text prompt (e.g., "ocean waves crashing")
Output: Audio file (47 seconds, WAV)
Cost: Free
DSGVO: Compliant
```

**fast mode:**
```python
Backend: Not yet implemented
Model: TBD (no suitable OpenRouter audio model available)
Status: Placeholder for future implementation

Note: OpenRouter does not currently offer audio generation APIs
```

---

**2c. Music Generation (with Tags + Lyrics)**

**eco mode:**
```python
Backend: ComfyUI (local)
Model: AceStep (ace_step_v1_3.5b.safetensors)
Input:
  - Prompt 1 (Tags): "upbeat, electronic, 120bpm"
  - Prompt 2 (Lyrics): "Dancing through the night..."
Output: Music file (47 seconds, WAV)
Cost: Free
DSGVO: Compliant
```

**fast mode:**
```python
Backend: Not yet implemented
Model: TBD (Suno AI? Udio? via OpenRouter or direct API)
Status: Placeholder for future implementation

Note: Music generation with lyrics is rare in cloud APIs
```

---

**2d. Video Generation (Future)**

**eco mode:**
```python
Backend: ComfyUI (local)
Model: TBD (AnimateDiff? Stable Video Diffusion?)
Cost: Free (but GPU-intensive)
Speed: Very slow (minutes per video)
DSGVO: Compliant
Status: Not yet implemented
```

**fast mode:**
```python
Backend: OpenAI (direct API)
Model: Sora2
Cost: Per-second pricing (e.g., $0.10-0.50 per second of video)
Speed: Fast (seconds to low-resolution, minutes to high-res)
DSGVO: Enterprise-only
Status: Planned, not yet implemented
```

---

### ~~Backend Selection Algorithm~~ [DEPRECATED - Session 65]

**⚠️ THIS ALGORITHM IS OBSOLETE:** The execution_mode-based routing described below was removed in Session 65. Model selection is now centralized in `devserver/config.py`. Backend routing still exists but is determined by model constants, not execution_mode parameter.

**Historical documentation (for reference only):**

**Step 1: Determine Task Type**
```python
if pipeline == "text_transformation":
    task_category = "LLM"
elif pipeline in ["single_text_media_generation", "dual_text_media_generation"]:
    task_category = "MEDIA_GENERATION"
    media_type = config.media_preferences.default_output  # "image", "audio", "music", "video"
```

**Step 2: Check Execution Mode**
```python
# Priority order:
execution_mode = (
    user_preference_from_frontend  # User toggled eco/fast switch
    or config.meta.get("force_eco")  # Config forces eco mode (DSGVO)
    or server_config.DEFAULT_EXECUTION_MODE  # Server default (usually "eco")
)
```

**Step 3: Route to Backend**
```python
if task_category == "LLM":
    if execution_mode == "eco":
        backend = "ollama"
        model = model_selector.get_local_model(task_type)
    elif execution_mode == "fast":
        # Use cloud service configured in server.config.py
        backend = server_config.LLM_SERVICES["cloud"]["provider"]  # "openrouter"
        model = model_selector.get_cloud_model(task_type)

elif task_category == "MEDIA_GENERATION":
    if execution_mode == "eco":
        backend = "comfyui"
        workflow = get_comfyui_workflow(media_type, config.meta.model)
    elif execution_mode == "fast":
        # Check if remote service is configured for this media type
        remote_service = server_config.REMOTE_SERVICES.get(media_type)

        if remote_service and remote_service["provider"]:
            backend = remote_service["provider"]
            model = remote_service["model"]
        else:
            # Fallback to local if no remote service configured
            backend = "comfyui"
            workflow = get_comfyui_workflow(media_type, config.meta.model)
```

**Step 4: Execute**
```python
result = backend_router.execute(
    backend=backend,
    model=model,
    workflow=workflow,
    input_data=processed_input,
    config_params=config.parameters
)
```

---

### ~~Remote Service Configuration (server.config.py)~~ [DEPRECATED - Session 65]

**⚠️ THIS CONFIGURATION PATTERN IS OBSOLETE:** The execution_mode-based service selection was removed in Session 65. Model/service selection is now handled via constants in `devserver/config.py`, not via execution_mode switching.

**Historical documentation (for reference only):**

The server ~~maintains~~ **maintained** centralized configuration for remote services:

```python
# server.config.py

# Default execution mode (eco = local, fast = cloud) [DEPRECATED]
DEFAULT_EXECUTION_MODE = "eco"

# Remote service endpoints (used when execution_mode == "fast") [DEPRECATED]
REMOTE_SERVICES = {
    "image": {
        "provider": "openrouter",  # or "openai" for direct GPT-5 access
        "model": "gpt-5-image",  # Placeholder - not yet available
        "api_key": os.getenv("OPENROUTER_API_KEY"),
        "fallback_to_local": True  # Use ComfyUI if API fails
    },
    "audio": {
        "provider": None,  # No cloud provider yet
        "fallback_to_local": True
    },
    "music": {
        "provider": None,  # No cloud provider yet (Suno? Udio?)
        "fallback_to_local": True
    },
    "video": {
        "provider": "openai",  # Sora2 via OpenAI direct API
        "model": "sora-2",  # Placeholder
        "api_key": os.getenv("OPENAI_API_KEY"),
        "cost_per_second": 0.20,  # Estimated
        "fallback_to_local": False  # No local video generation yet
    }
}

# LLM Services
LLM_SERVICES = {
    "local": {
        "provider": "ollama",
        "base_url": "http://localhost:11434"
    },
    "cloud": {
        "provider": "openrouter",
        "api_key": os.getenv("OPENROUTER_API_KEY"),
        "base_url": "https://openrouter.ai/api/v1"
    }
}
```

---

### DSGVO Considerations

**Current Status:**
- ✅ **eco mode:** Fully DSGVO-compliant (all data stays local)
- ❌ **fast mode (OpenRouter):** Non-compliant (data routed through US/UK servers)

**Administrator Responsibilities:**
- Research and select DSGVO-compliant cloud providers for fast mode
- Update `server.config.py` with compliant services
- Potential EU-based alternatives:
  - Mistral AI (direct API, France-based)
  - DeepL (for translation, Germany-based)
  - OpenAI Enterprise (with DSGVO BAA, expensive)
  - Self-hosted Ollama on EU servers (slower than cloud, compliant)

**Implementation Options:**
1. **Default eco mode:** Keep all educational workshops on local processing
2. **Dual configuration:** Separate server.config.py for research vs workshop environments
3. **Config-level override:** Add `meta.force_eco = true` for sensitive workflows

**Current Default:**
- eco mode for all operations
- fast mode available but requires explicit activation + DSGVO review

---

### SwarmUI/ComfyUI Auto-Recovery

**Added:** Session 113 (2026-01-11)

**Problem:** DevServer crashed when SwarmUI/ComfyUI backend was not running, displaying connection errors to users.

**Solution:** Automatic lifecycle management via SwarmUI Manager service.

#### Architecture

**Service:** `devserver/my_app/services/swarmui_manager.py`
**Pattern:** Singleton with lazy initialization (on-demand)

**Key Features:**
1. **Automatic Detection:** Health checks on ports 7801 (SwarmUI REST API) and 7821 (ComfyUI backend)
2. **On-Demand Startup:** Only starts SwarmUI when actually needed (lazy initialization)
3. **Crash Recovery:** Handles both startup scenarios AND runtime crashes
4. **Race-Condition Safe:** asyncio.Lock with double-check pattern prevents duplicate startups
5. **Configurable:** Environment variables for timeout, polling interval, enable/disable

#### Integration Points

**BackendRouter** (`backend_router.py`):
- Constructor: Initializes SwarmUI Manager singleton (line 150)
- Text2Image: Auto-start before generation (line 550)
- Workflow Submission: Auto-start before workflow (line 684)
- Image Upload (single): Auto-start before upload (line 893)
- Image Upload (multi): Auto-start before batch upload (line 941)

**LegacyWorkflowService** (`legacy_workflow_service.py`):
- Workflow Execution: Auto-start before submission (line 95)

#### Configuration

**File:** `devserver/config.py`

```python
SWARMUI_AUTO_START = os.environ.get("SWARMUI_AUTO_START", "true").lower() == "true"
SWARMUI_STARTUP_TIMEOUT = int(os.environ.get("SWARMUI_STARTUP_TIMEOUT", "120"))  # seconds
SWARMUI_HEALTH_CHECK_INTERVAL = float(os.environ.get("SWARMUI_HEALTH_CHECK_INTERVAL", "2.0"))  # seconds
```

**Environment Overrides:**
```bash
export SWARMUI_AUTO_START=false          # Disable for testing
export SWARMUI_STARTUP_TIMEOUT=180       # Increase timeout
export SWARMUI_HEALTH_CHECK_INTERVAL=1.0 # Poll more frequently
```

#### Startup Behavior

**Typical Sequence:**
1. User triggers image generation (e.g., sd35_large config)
2. BackendRouter calls `swarmui_manager.ensure_swarmui_available()`
3. Manager detects SwarmUI is not running (health check fails)
4. Manager executes `2_start_swarmui.sh` via subprocess
5. Manager polls health endpoints every 2 seconds
6. After ~45 seconds: SwarmUI is ready
7. Image generation proceeds normally

**Startup Time:** 30-60 seconds (depends on hardware)
**User Experience:** Frontend shows "processing" spinner during auto-start

#### Browser Tab Prevention

**Problem:** SwarmUI opens browser tab on startup, hiding the frontend.

**Solution:** Command-line override in startup script:
```bash
./launch-linux.sh --launch_mode none
```

**Why This Works:**
- SwarmUI supports `--launch_mode` command-line argument (Program.cs)
- Overrides `LaunchMode: web` setting in SwarmUI's Settings.fds
- Works on ANY SwarmUI installation (no settings file modification needed)
- Portable solution for third-party installations

#### Benefits

1. **Independence:** DevServer starts without requiring SwarmUI to be running
2. **Resilience:** Automatic recovery from SwarmUI crashes during operation
3. **User Experience:** No manual intervention needed, no hidden browser tabs
4. **Performance:** Lazy initialization - only starts when media generation requested
5. **Safety:** Race-condition proof via double-check locking pattern
6. **Flexibility:** Configurable timeout and polling intervals
7. **Portability:** Works with any SwarmUI installation

#### Error Handling

**Script Not Found:**
```
[SWARMUI-MANAGER] Startup script not found: /path/to/2_start_swarmui.sh
[SWARMUI-MANAGER] Please start SwarmUI manually
```

**Timeout (120s):**
```
[SWARMUI-MANAGER] Timeout after 120s
[SWARMUI-MANAGER] Check SwarmUI logs for startup issues
```

**Auto-Start Disabled:**
```
[SWARMUI-MANAGER] Auto-start disabled, SwarmUI not available
```

#### Design Rationale

**Why Lazy (On-Demand) vs. Eager (Startup)?**
- ✅ Faster DevServer startup (no 60s SwarmUI wait)
- ✅ Handles runtime crashes (not just startup)
- ✅ Only loads when needed (user might not use media generation)
- ✅ Better separation of concerns

**Why Not Check at DevServer Startup?**
- User might not need media generation in this session
- SwarmUI could crash during operation (eager check doesn't help)
- Adds unnecessary 60-second delay to every DevServer restart
- Lazy approach handles all scenarios with better UX

#### Documentation

**Detailed Architecture:** See `ARCHITECTURE PART 07 - Engine-Modules.md` Section 12
**Development Log:** Session 113 (2026-01-11)
**Commit:** `bbe04d8` - feat(swarmui): Add auto-recovery with SwarmUI Manager service

---

### LoRA Injection for Image Generation

**Added:** Session 114 (2026-01-11)

**Purpose:** Automatically inject LoRA (Low-Rank Adaptation) models into ComfyUI workflows for personalized image generation (e.g., face LoRAs, style LoRAs).

#### Architecture

**Location:** `devserver/schemas/engine/backend_router.py`
**Method:** `_inject_lora_nodes(workflow, loras)`

**Key Features:**
1. **Dynamic Injection:** LoRA nodes inserted at runtime, no workflow template changes needed
2. **Chaining:** Multiple LoRAs chain in sequence: Checkpoint → LoRA1 → LoRA2 → KSampler
3. **Auto-Connection:** Finds CheckpointLoader and model consumers, updates connections automatically
4. **SD3.5 Support:** Handles DualCLIPLoader for SD3.5 workflows

#### Data Flow

```
Stage 4 Request
     ↓
_process_output_chunk()
     ↓
if LORA_TRIGGERS:  → Use workflow mode (not simple API)
     ↓
_process_workflow_chunk()
     ↓
workflow = chunk.get('workflow')
     ↓
if LORA_TRIGGERS:
    workflow = _inject_lora_nodes(workflow, LORA_TRIGGERS)
     ↓
Submit to SwarmUI/ComfyUI
```

#### Configuration

**Current:** Connected to Interception Configs (implemented Session 116)

Each interception config can define LoRAs in its `meta` section:
```json
{
  "name": "cooked_negatives",
  "meta": {
    "loras": [
      {"name": "sd3.5-large_cooked_negatives.safetensors", "strength": 0.6}
    ]
  }
}
```

The `/generation` endpoint extracts LoRAs from the selected interception config and passes them to Stage 4.

#### LoRA Strength Tuning (Session 117)

**Critical Finding:** LoRA strength dramatically affects prompt adherence.

| Strength | Effect | Prompt Adherence |
|----------|--------|------------------|
| 0.8-1.0 | Style dominates completely | ❌ Prompt ignored |
| 0.5-0.7 | **Sweet spot** - visible style | ✅ Prompt preserved |
| 0.3-0.5 | Style barely visible | ✅ Full prompt adherence |

**Recommendation:** Start with 0.6 and adjust per-LoRA. Strong style LoRAs (like Cooked Negatives) may need lower values (0.5-0.6), while subtle LoRAs can use higher values (0.7-0.8).

**Per-Config Calibration Required:** Each interception config should test its LoRA strength individually, as LoRA intensity varies significantly between models.

#### Workflow Modification

**Before Injection:**
```
Node 5 (CheckpointLoaderSimple) → Node 8 (KSampler)
```

**After Injection:**
```
Node 5 (CheckpointLoaderSimple)
     ↓
Node 12 (LoraLoader: anime_style)
     ↓
Node 13 (LoraLoader: bejo_face)
     ↓
Node 8 (KSampler)
```

#### Routing Behavior

When `LORA_TRIGGERS` is configured:
- Images use **workflow mode** (not SwarmUI Text2Image API)
- Enables full ComfyUI node manipulation
- Slightly slower but supports advanced features

```python
if LORA_TRIGGERS:
    return await self._process_workflow_chunk(...)
else:
    return await self._process_image_chunk_simple(...)
```

#### Documentation

**Development Log:** Session 114 (2026-01-11)

---

### LoRA Training Studio

**Added:** Session 115 (2026-01-13)

**Purpose:** Train custom LoRA models (styles, faces) directly from the DevServer UI using Kohya SS.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      LoRA Training Studio                        │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (TrainingView.vue)                                     │
│  ├── Project Name + Trigger Word input                          │
│  ├── Image Upload (drag & drop, axios with 5min timeout)        │
│  ├── VRAM Check Dialog (before training)                        │
│  └── Real-time Log Viewer (SSE stream)                          │
├─────────────────────────────────────────────────────────────────┤
│  Backend Routes (training_routes.py)                             │
│  ├── POST /api/training/start      → Start training             │
│  ├── POST /api/training/stop       → Stop training              │
│  ├── GET  /api/training/status     → Current status             │
│  ├── GET  /api/training/events     → SSE log stream             │
│  ├── POST /api/training/delete     → GDPR file deletion         │
│  ├── GET  /api/training/check-vram → GPU memory status          │
│  └── POST /api/training/clear-vram → Unload ComfyUI/Ollama      │
├─────────────────────────────────────────────────────────────────┤
│  Training Service (training_service.py)                          │
│  ├── VRAM detection (nvidia-smi)                                │
│  ├── Auto-config based on available VRAM                        │
│  ├── TOML config generation                                     │
│  └── Kohya SS subprocess management                             │
└─────────────────────────────────────────────────────────────────┘
```

#### Path Configuration (config.py)

All training paths are configurable via environment variables:

| Variable | Default (relative to _AI_TOOLS_BASE) | Purpose |
|----------|--------------------------------------|---------|
| `KOHYA_DIR` | `./kohya_ss_new` | Kohya SS installation |
| `LORA_OUTPUT_DIR` | `./SwarmUI/Models/loras` | Output directory |
| `TRAINING_DATASET_DIR` | `$KOHYA_DIR/dataset` | Training images |
| `TRAINING_LOG_DIR` | `$KOHYA_DIR/logs` | Training logs |

Model paths (SD3.5 Large):
- `SD35_LARGE_MODEL_PATH` → `./SwarmUI/Models/Stable-Diffusion/OfficialStableDiffusion/sd3.5_large.safetensors`
- `CLIP_L_PATH`, `CLIP_G_PATH`, `T5XXL_PATH` → `./SwarmUI/Models/clip/`

#### Output Naming Convention

Each model-specific config generator adds its own prefix:

| Model | Method | Output Prefix | Example |
|-------|--------|---------------|---------|
| SD3.5 Large | `_generate_sd35_config()` | `sd35_` | `sd35_projectname.safetensors` |
| (Future) Flux | `_generate_flux_config()` | `flux_` | `flux_projectname.safetensors` |

#### VRAM Management

**Problem:** Training SD3.5 Large requires ~50GB VRAM. If ComfyUI/Ollama models are loaded, training fails with OOM.

**Solution:** Pre-training VRAM check with clearing option:

1. `GET /api/training/check-vram` returns:
   ```json
   {
     "total_gb": 95.0,
     "used_gb": 44.0,
     "free_gb": 51.0,
     "can_train": true,
     "min_required_gb": 50
   }
   ```

2. If `can_train: false`, user can click "Clear VRAM":
   - `POST /api/training/clear-vram` unloads:
     - ComfyUI: `POST http://127.0.0.1:7821/free`
     - Ollama: `POST /api/generate` with `keep_alive: 0`

#### WiFi Upload Reliability

**Problem:** Training uploads (10-50 images) failed over WiFi due to browser timeout.

**Solution:** Replace `fetch()` with `axios` using 5-minute timeout and progress tracking:

```typescript
const uploadClient = axios.create({
  baseURL: API_BASE,
  timeout: 300000, // 5 minutes
});

// With progress callback
onUploadProgress: (progressEvent) => {
  const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
  // Update UI
}
```

#### Documentation

**Development Log:** Session 115 (2026-01-13)

---

## Code Generation Output (Session 152 - 2026-01-31)

### Overview

Code generation is a special output type where the LLM generates executable code that runs in the browser. Unlike binary media (image/audio/video), no ComfyUI workflow is executed.

### Supported Frameworks

| Framework | Media Type | Language | Execution | Use Case |
|-----------|------------|----------|-----------|----------|
| **p5.js** | `code` | JavaScript | Browser Canvas | Generative graphics |
| **Tone.js** | `code` | JavaScript | Web Audio API | Browser-based music synthesis |

### Architecture Pattern

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Stage 2        │    │  Stage 4        │    │  Frontend       │
│  Interception   │───▶│  LLM Generation │───▶│  Browser Exec   │
│  (Listifier/    │    │  (Claude via    │    │  (iframe with   │
│   Composer)     │    │   OpenRouter)   │    │   p5.js/Tone.js)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Key Differences from Binary Media:**

1. **Chunk Type:** `text_passthrough` (not `output_chunk`)
2. **Backend:** `openrouter` (LLM), not `comfyui`
3. **Template:** `{{PREVIOUS_OUTPUT}}` - passes Stage 2 output directly
4. **Storage:** JSON entity (not binary file)
5. **Playback:** Browser-side execution (not server-side rendering)

### Schema Structure

**Output Chunk (text_passthrough):**
```json
{
  "name": "output_code_tonejs",
  "type": "text_passthrough",
  "backend_type": "vue_tonejs",
  "media_type": "code",
  "template": "{{PREVIOUS_OUTPUT}}"
}
```

**Output Config:**
```json
{
  "pipeline": "single_text_media_generation",
  "parameters": {
    "OUTPUT_CHUNK": "output_code_tonejs"
  },
  "meta": {
    "backend": "openrouter",
    "backend_type": "openrouter",
    "language": "javascript",
    "framework": "tonejs"
  }
}
```

### Media Type Detection

In `schema_pipeline_routes.py`, code output is detected by config name:

```python
if 'code' in output_config.lower() or 'p5js' in output_config.lower() or 'tonejs' in output_config.lower():
    media_type = 'code'
```

### Entity Storage

Code is saved as a JSON entity (not binary file):

```python
saved_filename = recorder.save_entity(
    entity_type='tonejs',  # or 'p5'
    content=output_value.encode('utf-8'),
    metadata={'format': 'js', 'framework': 'tonejs'}
)
```

### API Routes

- `/api/media/p5/<run_id>` - Serve p5.js code
- `/api/media/tonejs/<run_id>` - Serve Tone.js code

### Third-Party Libraries (CDN)

Both libraries are loaded via CDN in the frontend iframe:

- **p5.js** v1.7.0 - LGPL-2.1 - `https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.7.0/p5.min.js`
- **Tone.js** v14.8.49 - MIT - `https://cdnjs.cloudflare.com/ajax/libs/tone/14.8.49/Tone.js`

License documentation: `public/ai4artsed-frontend/THIRD_PARTY_CREDITS.md`

---

