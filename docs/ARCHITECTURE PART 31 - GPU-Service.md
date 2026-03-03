# DevServer Architecture

**Part 31: GPU Service — Standalone Inference Server**

---

## Overview

The GPU Service (`gpu_service/`) is a standalone Flask/Waitress process on **port 17803** that handles all local GPU inference. Both dev (17802) and prod (17801) backends call it via HTTP REST. It runs from a shared venv — no separate virtual environment needed.

**Key Principle:** One GPU service serves all environments. Model weights live in the GPU service directory, not per-environment.

---

## Directory Structure

```
gpu_service/
├── app.py              # Flask app factory
├── config.py           # All configuration (models, paths, env vars)
├── server.py           # Waitress entry point
├── routes/
│   ├── diffusers_routes.py
│   ├── heartmula_routes.py
│   ├── mmaudio_routes.py
│   ├── imagebind_routes.py
│   ├── stable_audio_routes.py
│   ├── cross_aesthetic_routes.py
│   └── text_routes.py
├── services/
│   ├── diffusers_backend.py       # SD3.5, Flux2 image generation
│   ├── heartmula_backend.py       # Music generation (HeartMuLa 3B)
│   ├── mmaudio_backend.py         # Video/Image-to-Audio (MMAudio)
│   ├── imagebind_backend.py       # ImageBind embedding extraction
│   ├── stable_audio_backend.py    # Stable Audio Open
│   ├── cross_aesthetic_backend.py # Cross-aesthetic generation
│   ├── text_backend.py            # LLM introspection (Latent Text Lab)
│   ├── vram_coordinator.py        # Cross-backend VRAM management
│   └── attention_processors_sd3.py
├── weights/            # MMAudio model weights (NOT in git)
├── ext_weights/        # MMAudio auxiliary weights (NOT in git)
└── .checkpoints/       # ImageBind checkpoint (NOT in git)
```

---

## Model Weight Locations (CRITICAL for Deployment)

### Why weights live inside `gpu_service/`

MMAudio and ImageBind use **relative paths** (`./weights/`, `./ext_weights/`, `./.checkpoints/`) hardcoded in their upstream library code. The GPU service startup script (`2_start_gpu_service.sh`) sets the CWD to `gpu_service/` before launching Python. This means all relative paths resolve from there.

These paths **cannot be configured** without patching the upstream libraries.

### Weight inventory

| Directory | Library | File | Size | Source |
|-----------|---------|------|------|--------|
| `weights/` | MMAudio | `mmaudio_large_44k_v2.pth` | 3.9 GB | HuggingFace: `hkchengrex/MMAudio` |
| `ext_weights/` | MMAudio | `v1-44.pth` | 1.2 GB | HuggingFace: `hkchengrex/MMAudio` |
| `ext_weights/` | MMAudio | `synchformer_state_dict.pth` | 0.9 GB | GitHub: `hkchengrex/MMAudio` releases |
| `.checkpoints/` | ImageBind | `imagebind_huge.pth` | 4.5 GB | Meta: `dl.fbaipublicfiles.com` |

**Total: ~10.5 GB**

### Auto-download behavior

Both libraries attempt to download weights automatically on first use if they are missing:

- **MMAudio**: `model_config.download_if_needed()` in `mmaudio/utils/download_utils.py` checks MD5 hash and downloads from HuggingFace/GitHub if missing.
- **ImageBind**: `imagebind_model.imagebind_huge(pretrained=True)` in `imagebind/models/imagebind_model.py` downloads via `torch.hub.download_url_to_file()` if `.checkpoints/imagebind_huge.pth` is missing.

This means a fresh deployment will auto-download ~10.5 GB on first GPU service request that uses MMAudio or ImageBind. On a school network, this may take considerable time.

### Other model weights (NOT in `gpu_service/`)

These models are loaded via HuggingFace `from_pretrained()` and cached in `~/.cache/huggingface/`:

| Backend | Model | Cache Location | Size |
|---------|-------|----------------|------|
| Diffusers | SD3.5 Large | `~/.cache/huggingface/` | ~16 GB |
| Diffusers | Flux 2 Dev | `~/.cache/huggingface/` | ~106 GB (BF16 on disk, loaded as FP8+INT8) |
| Stable Audio | `stabilityai/stable-audio-open-1.0` | `~/.cache/huggingface/` | ~2.6 GB |
| CLIP Vision | `openai/clip-vit-large-patch14` | `~/.cache/huggingface/` | ~0.6 GB |
| HeartMuLa | HeartMuLa-oss-3B | `~/ai/heartlib/ckpt/` | ~12 GB |

### Deployment: external drive / production copy

When deploying to a separate directory (e.g., `/run/media/.../ai4artsed_production/`), the `gpu_service/` weight directories will be empty because they are gitignored. Options:

1. **Let auto-download handle it** — First start downloads ~10.5 GB. Simple but slow.
2. **Copy the weight files** — Copy `weights/`, `ext_weights/`, `.checkpoints/` from dev to production.
3. **Symlink** — Create symlinks from the production `gpu_service/{weights,ext_weights,.checkpoints}` to the dev copy (only works if both are on the same filesystem or the source is always mounted).

**Recommended for same-machine deployments:** Option 3 (symlinks) avoids 10.5 GB duplication.

**Recommended for external drive / different machine:** Option 1 (auto-download) or Option 2 (copy). Auto-download is simplest for amateur admins — it "just works" on first start, with no manual steps beyond waiting.

---

## Configuration

**File:** `gpu_service/config.py`

All settings use environment variables with sensible defaults. The `_AI_TOOLS_BASE` variable (default: `~/ai`) is the root for locating sibling repos (MMAudio, heartlib, ImageBind).

### Key variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GPU_SERVICE_PORT` | `17803` | Service port |
| `AI_TOOLS_BASE` | `~/ai` | Root for sibling repos |
| `DIFFUSERS_ENABLED` | `true` | Enable Diffusers backends |
| `DIFFUSERS_FLUX2_QUANTIZE` | `fp8` | Flux 2 quantization: `fp8` (FP8 transformer + INT8 text encoder, ~24GB peak) or `bf16` (~62GB with CPU offload) |
| `HEARTMULA_ENABLED` | `true` | Enable HeartMuLa music |
| `HEARTMULA_MODEL_PATH` | `{AI_TOOLS_BASE}/heartlib/ckpt` | HeartMuLa checkpoint |
| `STABLE_AUDIO_ENABLED` | `true` | Enable Stable Audio |
| `MMAUDIO_ENABLED` | `true` | Enable MMAudio |
| `MMAUDIO_REPO` | `{AI_TOOLS_BASE}/MMAudio` | MMAudio repo path |
| `IMAGEBIND_ENABLED` | `true` | Enable ImageBind |
| `CROSS_AESTHETIC_ENABLED` | `true` | Enable cross-aesthetic |
| `TEXT_ENABLED` | `true` | Enable Latent Text Lab |

### Sibling repo dependencies (editable installs)

These repos must be installed as editable packages in the shared venv:

| Repo | Install command | Required by |
|------|----------------|-------------|
| `~/ai/MMAudio` | `pip install -e ~/ai/MMAudio` | MMAudio backend |
| `~/ai/ImageBind` | `pip install -e ~/ai/ImageBind` | ImageBind backend |
| `~/ai/heartlib` | `pip install --no-deps -e ~/ai/heartlib` | HeartMuLa backend |

---

## Startup

**Script:** `2_start_gpu_service.sh`

```bash
cd "$SCRIPT_DIR/gpu_service"          # CWD = gpu_service/ (required for relative weight paths)
"$SCRIPT_DIR/venv/bin/python" server.py  # Uses shared venv
```

The `cd gpu_service` is critical — MMAudio and ImageBind resolve weight paths relative to CWD.

---

## VRAM Management

The GPU service uses a `VRAMCoordinator` (singleton) that manages VRAM across all backends. Each backend implements the `VRAMBackend` protocol:

- `get_registered_models()` → list of models with VRAM, priority, last_used, in_use
- `evict_model(model_id)` → release specific model's VRAM
- `get_backend_id()` → unique identifier

When a backend needs VRAM, the coordinator evicts the lowest-priority loaded backend. See Part 27 for the Diffusers-specific LRU cache details.

### NVML Watchdog (Session 244)

The coordinator uses NVML (`pynvml`) for real GPU visibility beyond PyTorch's own tensors. This detects foreign GPU processes (Ollama, ComfyUI, SwarmUI zombies) and provides accurate `get_free_vram_mb()` that accounts for all VRAM consumers. Dynamic thresholds adapt to Ollama model loads and ComfyUI state. Port blacklist (7801, 7821, 8188) detects SwarmUI zombies. Kill endpoint (`POST /api/health/kill-foreign`) with safety rails. See Part 27 for full details.

### Configuration (VRAM Watchdog)

| Variable | Default | Purpose |
|----------|---------|---------|
| `VRAM_USE_NVML` | `true` | Enable NVML real GPU visibility |
| `VRAM_FOREIGN_OVERHEAD_MB` | `2048` | Baseline foreign VRAM budget (CUDA contexts, driver) |
| `VRAM_BLACKLISTED_PORTS` | `[7801, 7821, 8188]` | SwarmUI ports — triggers warning on detection |
| `OLLAMA_API_URL` | `http://localhost:11434` | Ollama API for model inventory |
| `COMFYUI_PORT` | `17804` | Expected ComfyUI port (tolerated) |

---

## Relationship to DevServer

```
┌──────────────────┐     HTTP REST      ┌──────────────────┐
│    DevServer     │ ──────────────────▶ │   GPU Service    │
│  (port 17801/02) │                     │   (port 17803)   │
│                  │                     │                  │
│  Orchestration   │                     │  Inference only  │
│  Safety checks   │                     │  No business     │
│  i18n, pedagogy  │                     │  logic           │
│  Pipeline exec   │                     │                  │
└──────────────────┘                     └──────────────────┘
```

DevServer calls the GPU service via HTTP clients (`DiffusersClient`, `HeartMuLaClient`, `TextClient`, etc.) that have identical async method signatures to the original in-process backends — zero changes to callers.

**Fallback:** If the GPU service is down, `is_available()` returns False and the DevServer falls back to ComfyUI/SwarmUI for media generation (see Part 08: Backend Routing).

### LLM Inference — Ollama Direct (NOT GPU Service)

**Session 218:** LLM inference goes **directly to Ollama** via `LLMClient`, NOT through GPU Service. Session 217 attempted to route all LLM inference through GPU Service (HuggingFace Transformers), but Ollama model names (e.g. `qwen3:32b`) are incompatible with HF `AutoTokenizer.from_pretrained()`, causing cascading failures. The GPU Service LLM code was removed entirely.

```
DevServer ──→ LLMClient ──→ Ollama :11434  (GGUF, direct)
```

GPU Service handles **media inference only** (Diffusers, HeartMuLa, Stable Audio, MMAudio, Cross-Aesthetic, Latent Text Lab).

---

## Files

| File | Purpose |
|------|---------|
| `gpu_service/config.py` | All configuration |
| `gpu_service/server.py` | Waitress entry point |
| `gpu_service/app.py` | Flask app + route registration |
| `gpu_service/services/vram_coordinator.py` | Cross-backend VRAM management |
| `2_start_gpu_service.sh` | Startup script (sets CWD) |
| `devserver/config.py` | `GPU_SERVICE_URL`, `GPU_SERVICE_TIMEOUT_*` (per-operation) |
| `devserver/my_app/services/diffusers_client.py` | HTTP client (drop-in for DiffusersImageGenerator) |
| `devserver/my_app/services/heartmula_client.py` | HTTP client (drop-in for HeartMuLaBackend) |
| `devserver/my_app/services/stable_audio_client.py` | HTTP client (Stable Audio) |
| `devserver/my_app/services/text_client.py` | HTTP client (Latent Text Lab) |
| `devserver/my_app/services/llm_client.py` | Ollama-direct LLM client (NOT GPU Service) |
| `devserver/my_app/services/llm_backend.py` | LLM client singleton factory |

---

**Document Status:** Active (2026-03-03, Session 244)
**Maintainer:** AI4ArtsEd Development Team
