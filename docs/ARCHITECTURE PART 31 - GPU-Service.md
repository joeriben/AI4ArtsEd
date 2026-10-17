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
│   ├── mmaudio_routes.py
│   ├── cross_aesthetic_routes.py
│   ├── llm_routes.py              # the safety classifier's door (/api/llm/classify)
│   └── health_routes.py
├── services/
│   ├── diffusers_backend.py       # SD3.5, Flux2 image generation
│   ├── mmaudio_backend.py         # Video/Image-to-Audio (MMAudio)
│   ├── imagebind_backend.py       # ImageBind embedding extraction
│   ├── stable_audio_backend.py    # Stable Audio 3 (loaded for the Latent Audio Synth)
│   ├── stable_audio_model.py      # which Stable Audio 3 checkpoint this card runs
│   ├── cross_aesthetic_backend.py # Cross-aesthetic generation
│   ├── llm_backend.py, llm_child.py, llm_child_backend.py   # the supervised llama-server children
│   ├── gpu_admission.py           # the service's own gate, leasing the DevServer's
│   ├── vram_coordinator.py        # Cross-backend VRAM management
│   └── attention_processors_sd3.py, embedding_analyzer.py
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
| CLIP Vision | `openai/clip-vit-large-patch14` | `~/.cache/huggingface/` | ~0.6 GB |

HeartMuLa and Hunyuan3D-2 are no stations of this service any more (stage 8);
their weights are folders under ComfyUI's `models/` tree, named by the table
`devserver/config/local_media_weights.json`.

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
| `MMAUDIO_REPO` | `{AI_TOOLS_BASE}/MMAudio` | MMAudio repo path |
| `LLM_ENGINE` | `child` | Which engine serves `/api/llm/*`: `child` (one supervised `llama-server` per model) or `inprocess` (llama-cpp-python, the rollback) |
| `LLAMA_SERVER_BIN` | `{AI_TOOLS_BASE}/llama.cpp/build/bin/llama-server` | The `llama-server` binary, built from the pinned llama.cpp clone |
| `LLM_CHILD_STATE_DIR` | `~/.cache/ai4artsed/gpu-service-{port}` | Holds `llm_children.json`. Must be absolute and outside the working tree — checked where it is used, so a bad value costs the LLM engine and nothing else |

### Sibling repo dependencies (editable installs)

These repos must be installed as editable packages in the shared venv:

| Repo / Package | Install command | Required by |
|----------------|----------------|-------------|
| `~/ai/MMAudio` | `pip install -e ~/ai/MMAudio` | MMAudio backend |
| `~/ai/ImageBind` | `pip install -e ~/ai/ImageBind` | ImageBind backend |

HeartMuLa, Hunyuan3D-2 and the media readers run as nodes of the platform's
ComfyUI package since stage 6 of the move to ComfyUI (PART 08); their stations
here, and the routes `/api/heartmula/*`, `/api/hunyuan3d/*`, `/api/analysis/*`,
`/api/stable_audio/*` and `/api/gpu/*`, were struck in stage 8.

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

### NVML Watchdog

The coordinator uses NVML (`pynvml`) for real GPU visibility beyond PyTorch's own tensors. This detects foreign GPU processes (Ollama, ComfyUI, SwarmUI zombies) and provides accurate `get_free_vram_mb()` that accounts for all VRAM consumers. Dynamic thresholds adapt to Ollama model loads and ComfyUI state. Port blacklist (7801, 7821, 8188) detects SwarmUI zombies. Kill endpoint (`POST /api/health/kill-foreign`) with safety rails. See Part 27 for full details.

### Configuration (VRAM Watchdog)

| Variable | Default | Purpose |
|----------|---------|---------|
| `VRAM_USE_NVML` | `true` | Enable NVML real GPU visibility |
| `VRAM_FOREIGN_OVERHEAD_MB` | `2048` | Baseline foreign VRAM budget (CUDA contexts, driver) |
| `VRAM_BLACKLISTED_PORTS` | `[7801, 7821, 8188]` | SwarmUI ports — triggers warning on detection |
| `COMFYUI_PORT` | `17804` | Expected ComfyUI port (tolerated) |

---

## Media Analysis (media -> text)

Since stage 6 of the move to ComfyUI a reading is one prompt of the node
`ai4artsed_media_reading` (`comfyui_nodes/ai4artsed_comfyui/_media_reading.py`),
queued and tracked by `devserver/my_app/services/media_analysis_client.py`; the
GPU service's `/api/analysis/*` station and `services/media_analysis_backend.py`
were struck in stage 8. Which reader answers which task, what each is told, and
the label list of the ranking are the `reading` block of
`devserver/config/local_media_weights.json` (`services/local_media_weights.py`):

| Task | Reader (its alias in the table) | Weights (`repo`) |
|---|---|---|
| `audio` | MiDashengLM 7B (`midashenglm:7b`) | `mispeech/midashenglm-7b` |
| `image`, `video` | Qwen3-VL 8B Instruct (`local/qwen3-vl:8b`, an entry of the language-model table) | `Qwen/Qwen3-VL-8B-Instruct` |
| `lyrics` | HeartTranscriptor (`hearttranscriptor`) | `HeartMuLa/HeartTranscriptor-oss` |
| `music_tags` | CLAP, music and speech (`clap-music-speech`) | `laion/larger_clap_music_and_speech` |

**Weights.** Folders under ComfyUI's `models/` tree: the station's folder
(`stations.media_reading.folder` in the same table) for the readers, `models/llm`
for a `local/` alias, each named by the `dir` of its entry.

**What these outputs are not.** Measured on a room recording:

- `lyrics` on input with no words in it does not return nothing. It returns a
  short, fluent, confident sentence. Room noise produced "1. No triggerpull is
  required."; digital silence produced "you".
- `music_tags` has no abstain — cosine similarity always yields an order, so
  near-silence still ranks as `pop song` with a positive score. A result is
  always "best match inside the list that was passed", never "what this is".
- `audio` is strongly prompt-sensitive, and the defaults were corrected once
  this was measured. Told to write a "rich, flowing description" it produced
  one, inventing a paragraph of instruments that were not in the recording.
  Under the restrained default it names what is there and answers "There is
  nothing." to room noise. What survives the restraint: an instrument that is
  not present, and gender attribution to a voice — that one persisted even
  under an explicit instruction not to describe the person, so do not put it
  on screen over recordings of children.

Any UI showing these has to carry that, or it presents guessing as hearing.
The one page that does show them — Cover Band, PART 38 — carries it as its
subject rather than as a disclaimer.

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

DevServer calls the GPU service via `DiffusersClient`, an HTTP client with the async method signatures of the original in-process backend — zero changes to callers. The music, 3D, Stable Audio and media-reading clients prompt the platform's ComfyUI nodes since stage 6 of the move to ComfyUI, and `TextClient` asks ComfyUI's tokenizer routes since stage 5 (each module's docstring says so).

**Fallback:** If the GPU service is down, `is_available()` returns False and the DevServer falls back to ComfyUI/SwarmUI for media generation (see Part 08: Backend Routing).

### LLM and VLM Inference — in the GPU Service (supervised `llama-server` children)

Local text and vision inference runs **under** the GPU service: one `llama-server` process per model alias, spawned by the service, measured per PID through NVML, reserved for before it starts, and ended by the service. Ollama is gone from the runtime; what is left of the name is a legacy value the backend router still accepts and a one-off script under `devserver/scripts/`.

```
DevServer ──→ safety_classifier ──→ GPU Service :17803  /api/llm/classify
                                  │
                                  ├──→ llama-server  127.0.0.1:17810   (qwen3-vl:8b)
                                  ├──→ llama-server  127.0.0.1:17811   (qwen3:4b)
                                  └──→ …                                one per alias
```

A child is **not** a peer process. Ollama was one — it had its own residency policy and decided on its own what stayed on the card. A child that this service spawns, measures, reserves for and terminates leaves the VRAM coordinator the single authority over what is resident: the relationship the platform already has with ComfyUI, with the service as parent instead of as neighbour.

Weights are GGUF files under `<repo>/llama-server-models/` (`MODEL_DIR` in `gpu_service/services/llm_backend.py`, redirectable with `AI_TOOLS_BASE`). An alias is offered only when its files lie on disk; a VLM alias needs its `mmproj` file as well, so a half-finished download shows up as *not installed* rather than as a broken model. `MODEL_CONFIGS` in the same file remains the registry — the child engine reads it unchanged and honours every field (`n_gpu_layers: -1` becomes `-ngl all`).

**Why a process boundary.** Three failure classes, and only the first was ever within reach of a better estimate. *A crash* — eleven SIGSEGVs stand in the journal between 2026-08-15 and 2026-08-29, and in all but one of them `encoding image slice` is the last line the service wrote; each killed every content check that was running at that moment. In a child it costs one alias. *Bookkeeping* — the Python chat handler advanced its token count over image positions without writing the ids back, which is what damaged every second image reading; `llama-server` does its own multimodal bookkeeping. *Capability* — a GGUF that aborts on load, or a model whose template the Python handlers did not know, was simply excluded; now it costs a child.

| File | Purpose |
|---|---|
| `gpu_service/services/llm_child.py` | the process side: spawn line, readiness, ownership, state file, reaper, orphan scan (`SupervisedChild`, `ChildSupervisor`) |
| `gpu_service/services/llm_child_backend.py` | the engine: inference contracts, SSE, VRAM bookkeeping, the public surface the routes call |
| `gpu_service/services/llm_backend.py` | the registry (`MODEL_CONFIGS`, `MODEL_ALIASES`, `ModelLoadRefused`) — and the older in-process engine, still selectable |

#### The spawn line

```
llama-server -m <model_path> [--mmproj <mmproj_path>] -c <n_ctx> -n -1 -ngl <all|N> -np 1
  --slots -b 512 -ub 512 --fit off --no-context-shift --jinja --reasoning-format none
  --reasoning on --reasoning-budget -1
  -cram 0 --no-webui --host 127.0.0.1 --port <port> --alias <alias> -to 2592000
```

Built by `build_argv()`, which is pure so a test can assert it flag by flag.

| Flag | Why |
|---|---|
| `-c` / `-ngl` / `--mmproj` | straight from `MODEL_CONFIGS`; `n_gpu_layers: -1` is this build's `all` |
| `-n -1` | no output cap. Explicit **because** it is the default: llama.cpp reads `LLAMA_ARG_N_PREDICT` for every flag absent from the command line, so an ambient environment variable could otherwise cap every answer the platform produces without appearing anywhere |
| `-np 1` | one slot. Two requests for the same alias queue inside the child instead of interleaving on one context |
| `--slots` | the per-slot endpoint the platform reads to see whether a cancelled request really let go. Written out so a changed default cannot take it away silently |
| `-b 512 -ub 512` | as the in-process engine ran them |
| `--fit off` | `--fit` adjusts *unset* arguments to fit the card and is on by default. Nothing here is unset — this is the guard if `-c` is ever dropped |
| `--no-context-shift` | a reading that reaches the ceiling must **end** there and say so, rather than silently drop its own beginning |
| `--jinja` | each model's own GGUF template, instead of the seven hardcoded chat formats the Python handlers offered |
| `--reasoning-format none` | thoughts stay in `content`, so the `</think>` partition the platform already does still applies |
| `--reasoning on` | the switch itself, and the only one: it sets `enable_reasoning = 1` **and** the template default `enable_thinking = "true"` (`common/arg.cpp:3066`), and the server then thinks for every template that supports it (`server-context.cpp:899-900`). Without it the decision falls to whatever each GGUF's own template does when the variable is undefined — and the model this platform runs its pipeline roles on defaults to no thinking at all, which is why the in-process engine never saw a thought from it |
| `--reasoning-budget -1` | no bound on the thinking itself. The build's default, written out for the same reason as `-n -1`: it is read from `LLAMA_ARG_THINK_BUDGET` when absent, and a `0` there would end every thought at its first token without appearing in the spawn line |
| `-cram 0` | the host-RAM prompt cache reserves 8 GiB **per instance**; with one instance per alias that is real memory for a cache this platform does not use |
| `--no-webui` | nothing here serves a browser |
| `--host 127.0.0.1` | never on the network, whatever the service itself binds to |
| `-to` | the child's own socket read/write timeout, 600 s by default. Set to 30 days, because a long reading is an ordinary event here and cpp-httplib does not read `0` as "no timeout" |

The child's environment is this service's, **minus every `LLAMA_ARG_*` and `LLAMA_API_KEY`** — llama.cpp reads those for any flag missing from the command line, so an ambient value would reach into a child's sampling, its context size or its authentication without appearing in the spawn line the log prints. Added instead: `AI4ARTSED_LLM_CHILD=<parent pid>:<alias>`, the ownership marker. `stdout` and `stderr` go to one pipe; a daemon reader thread per child keeps the last 200 lines for error messages and forwards every line to the journal as `[LLM-CHILD <alias>] …`, so the child's own output is in the service log rather than in a place nobody looks.

Ports come from a range derived from this service's own port — `LLM_CHILD_PORT_BASE = GPU_SERVICE_PORT + 7`, 40 of them, so **17810–17849** for the default 17803. Two GPU services on one box therefore start from different offsets. A port is bind-probed (without `SO_REUSEADDR`, so one in `TIME_WAIT` is passed over) before a child is given it; a child that loses the race between the probe and its own bind is started once more on the next port, and refused after that.

#### Readiness, and its two bounds

`GET /health` on the child every 250 ms until it answers 200. Four things can end the wait badly, and the refusal says which: the process exited (exit code plus its last 20 lines), nothing moved for the stall bound, the whole attempt outlasted the ceiling, or the vision buffer never appeared.

The two time bounds do different work and neither replaces the other.

* **`LLM_CHILD_STALL_S` (180 s)** asks whether anything is happening at all. Four signals answer it, and the load is left alone while any of them moves: bytes off the child's pipe (llama.cpp writes its load bar as dots with no newline, so a line counter stands still for the slowest phase), the finished-line count, the bytes `/proc/<pid>/io` says the process has read from disk (compared in whole MiB, because the readiness polls themselves add a few dozen bytes four times a second), and its own per-PID NVML figure (asked once per second, since enumerating walks every process on the card). This is a liveness bound on the supervisor, never a budget for a model call.
* **`LLM_CHILD_LOAD_CEILING_S` (900 s)** is the wall clock of one attempt, whatever progress it shows. A child that writes a line every second and never becomes healthy would otherwise hold the plant-wide load lock — and with it every content check on the platform — forever.

At readiness the child is booked with one NVML reading taken on the spot, so a fresh child is never listed at 0 MB and an eviction never takes it for free.

#### The vision rails — four refusals, none of them an estimate

The crash class came from a silent failure upstream: the image encoder's compute buffer is reserved with a return value llama.cpp discards, so a failed reserve leaves the server reporting itself ready and the first image dereferences a null buffer. Four rails stand in front of that, and they act at different moments:

1. **The coordinator could not be consulted** → a vision load is refused. Loading a 9 GB model blind and finding out afterwards is the case this exists to prevent.
2. **NVML is not authoritative** (`has_authoritative_reading()` is false) → refused, same reason.
3. **The VRAM request itself raised** → refused.
4. **The child reported itself ready without ever logging its compute buffer** → killed and refused. The installed build prints `alloc_compute_meta: CUDA0 compute buffer size = N MiB` only when the buffer was really produced; the reader thread sets the flag as the line goes past, and readiness allows it two more seconds to arrive (`/health` answers the moment the language model is up, and the projector is built right after). This is the check that needs no estimate at all.

`VLM_VISION_COMPUTE_MB` (1024) is the **reservation** across the load — the room held from the coordinator's grant until the encoder has its buffers. It is not what the encoder is admitted on. The figure is measured, not estimated: on an RTX PRO 6000 (build `59d8402`, per-PID `nvidia-smi`, 2026-09-02) a fed encoder grows the process by +488 MB (`qwen3-vl:2b`), +550 MB (`:8b`) and +686 MB (`:32b`) — three of the four VLM aliases; `qwen3-vl:4b` was not measured and is taken to sit inside that range, which is an inference — and stops growing above 2048x2048 because the image-token count is capped at eight batches of `n_tokens_batch = 512`. The 5000 it replaces was a guess made before anything was measured, and five gigabytes per vision load is five gigabytes of evictions that never needed to happen.

#### The warm-up — the encoder is fed before the room is given back

The compute-buffer line a vision child is admitted on covers the reserve llama.cpp does at **load**. It does not cover what the encoder allocates when it is first **fed**, which is the several hundred megabytes above. Until the load-time warm-up existed, that allocation happened on a reader's request: outside any reservation, on a card that may have filled with a render in the meantime, through the same discarded return value.

So `start()` hands a newly ready vision child one 2048x2048 image — built in code (a diagonal grey pattern, ~22 KB), never an asset an install could be missing — and reads exactly one frame before letting the stream go. The image is encoded during prefill, so the buffers exist by the time the first token comes back; nothing is capped, the child was simply not read any further. The child is `READY` and counted as in use for the duration, so the reaper's child-level clock covers a warm-up that wedges, and no read timeout is involved anywhere — the warm-up carries a progress bound of its own instead (`LLM_CHILD_WARMUP_STALL_S`, 60 s), because it holds the plant-wide load lock while it waits. When that bound is reached the socket is shut down rather than closed: closing a streaming response from the waiting thread takes the reader's own buffer lock and the bound would hang inside its own escape hatch (`unblock_stream`). The load line then carries what it cost:

```
[LLM] <alias> is ready on port <port> (PID <pid>) — image encoder warmed at 2048x2048: <before>MB -> <after>MB (+<grown>MB) in <seconds>s
```

An image that takes the child down refuses the load — that is precisely what the first reader's image would have done. A warm-up that fails against a living child is asked once more, while the room is still reserved; if the second attempt fails too the child is killed and the load refused. There is no third state: a `READY` vision child whose encoder buffers were never allocated is booked at a figure that does not exist, and the first reader's image would ask for those 500–700 MB outside any reservation, through the one allocation llama.cpp does not report the failure of. A refused load is recoverable, that is not. A measured shortfall refuses a vision load unconditionally; on the text path a shortfall reported by a coordinator whose sensors are all gone is not a measurement, and the load goes ahead and says so, because the alternative is that every content check on the platform stops.

#### Ownership, and what survives a restart

A PID alone is not an identity — the number is reused, and killing a stranger that inherited one is exactly the accident this must not have. `owns()` requires all three: the PID is alive, it was born at the moment we recorded (field 22 of `/proc/<pid>/stat`), and `/proc/<pid>/environ` carries the whole marker `<parent pid>:<alias>` as one string. Matching the alias alone would accept a second GPU service's child for the same model.

Registration happens **immediately after `Popen`**, before readiness — so the whole load window is covered, and NVML's view of a child reading 20 GB off disk never reads as "foreign".

`llm_children.json` under `LLM_CHILD_STATE_DIR` (default `~/.cache/ai4artsed/gpu-service-<port>/`) records alias, PID, starttime and port per child plus the PID of the service that spawned them. It is written on every registry change, by replace rather than truncate-and-write, and read exactly once — at startup, by the orphan scan, which SIGTERMs each entry that passes all of `owns()` against the *recorded* parent PID, re-checks ownership immediately before any SIGKILL, and leaves everything else alone with a log line saying so. The directory is **checked where it is used**, not at config import: it must be absolute and outside the working tree (the file names the PIDs and ports of this machine and has no business in a repository), and a bad value costs the LLM engine while image generation, the safety chain and the health endpoint go on serving.

#### Termination, and the reaper

`SIGTERM` → poll ≤ 3 s → `SIGKILL` → poll ≤ 2 s → NVML poll ≤ 2 s for the PID to stop being listed. About seven seconds for the worst child, one or two for a healthy one, and short on purpose: an eviction runs inside the coordinator's request lock, which every other load on the platform waits behind, and the coordinator re-reads free VRAM after each child it ends. Termination returns true only when the process is gone **and** the card no longer carries it — a process being reaped and its memory coming back are not the same moment, and a ledger that believed the first would hand the room out twice.

The refcount check and the removal are one critical section. Split in two, a request arriving between them would be handed a child that is already being killed. `unload(alias, force=True)` skips the busy check and nothing else — the operator's escape hatch for a wedged child whose refcount never came back.

Shutdown signals every child first and collects afterwards against one shared 20 s deadline, so a service with four children does not spend four times the termination bound inside systemd's stop timeout. A survivor is logged with its PID and handed to the **reaper** thread (every 5 s), which also notices children that ended by themselves: while a crashed child stands in the registry the coordinator believes its memory is booked and the next request is handed a port nothing listens on. The reaper reaps with `poll()` rather than trusting `kill(pid, 0)` — an unreaped zombie answers that signal — unregisters the PID, and rewrites the state file.

**A dead child never reaches a request, and a silent one does not keep its memory.** `acquire()` collects the exit status before handing a child out; a corpse is detached inside the same critical section, its memory waited for (the NVML-gone bound, outside the lock) and the coordinator's enumeration cache dropped, so the load that follows asks for room against a card that has already let the memory go. The attempt that met the death gets its record (exit code and last lines → 500); a record is consumed only by that attempt and is dropped as soon as a live child is handed out or a new one registers. The reaper settles crashed children the same way. A READY child with a request in flight is judged by the progress of its slot, never by a read timeout: frames arriving on any stream, the child's work lines (`prompt processing progress`/`done`, `slice encoded in`, `decoded (batch`) and the decode counter from `GET /slots` — a status probe with a short read timeout, the only read timeout in this engine, because `/slots` is answered by the same main loop that generates, so its silence is the evidence. None of the three moving for `LLM_CHILD_STALL_S` ends the child through the ordinary termination path with the reason recorded; the in-flight request's error body names it, and the next request spawns anew. A request that is receiving frames is never cut, and an arriving request is not progress (every arrival writes a log line, which is why the load-time line counter is not one of the three). With two or more streams in flight on one child, each stream also carries its own clock: a stream whose frames stopped for the bound while the slot moved on to another request is a finished answer nobody drains — that request alone is closed (its refcount returns, its error says this service ended it and the child is still serving) and the child stays; a stream without frames yet is waiting for the slot and is exempt. The state file is written from sequence-numbered snapshots outside `state_lock`; a snapshot older than one already on disk is dropped rather than written over it.

`server.py` builds the backend before `serve()`, so all of this is process work rather than request work: the coordinator learns which PIDs belong to this backend, the orphan scan runs, `llama-server --version` is asked once and cached for `/api/llm/health` (it opens the CUDA device on this build, which is harmless at startup and emphatically not something to do while a model is loading), and SIGTERM, SIGINT and a plain exit are wired to end the children. systemd kills the whole control group anyway; a manual run has no second line at all.

#### The ledger

Each child is booked by what NVML **measured** for its PID, from one enumeration per collection pass offered to the backends through the `VRAMBackend` protocol. Three states, and they mean three different things:

| What NVML says | What the ledger does |
|---|---|
| no reading at all (NVML threw, or is not configured) | keep the last figure — a drop to 0 here would invite an eviction to believe the card is empty |
| the PID is listed without a memory figure (`usedGpuMemory` is `None`) | keep the last figure and say so; `None` is "no figure", never zero |
| the PID is absent | the child is gone. Not a memory figure at all — the reaper takes it out of the registry |

The process enumeration is cached for ~1 s. Readiness polls per child while it waits for a load, and again while it waits for a termination; without the cache that is several full walks of the card per second for a figure that cannot have changed between two of them.

#### Bounds and constants

Not env-overridable; `gpu_service/config.py` and `services/llm_child.py`.

| Constant | Value | What it bounds |
|---|---|---|
| `LLM_CHILD_PORT_BASE` / `_COUNT` | `GPU_SERVICE_PORT + 7`, 40 | 17810–17849 for the default 17803; derived, so two GPU services on one box do not collide |
| `LLM_CHILD_STALL_S` | 180 s | while loading: no progress on any of the four signals while `/health` still refuses → killed and refused. Under a request in flight: no slot progress (frames, work lines, the `/slots` decode counter) → ended, the reason in the error body |
| `LLM_CHILD_LOAD_CEILING_S` | 900 s | the wall clock of ONE load attempt, however much progress it shows |
| `LLM_CHILD_SOCKET_TIMEOUT_S` | 2 592 000 s (30 days) | the child's own `-to`; a long reading is an ordinary event and `0` does not disable it in cpp-httplib |
| `VLM_VISION_COMPUTE_MB` | 1024 | the reservation held across a vision load — measured (+488 to +686 MB on `qwen3-vl:2b`, `:8b`, `:32b`; `:4b` not measured), not what the encoder is admitted on |
| `VISION_WARMUP_PX` | 2048 | the warm-up image's edge, at the size where the image-token count stops growing |
| `LLM_CHILD_WARMUP_STALL_S` | 60 s | no progress while the warm-up image is being encoded → the child is killed and the load refused. Short because the plant-wide load lock is held meanwhile; the measured encode is 2.2–3.5 s |
| readiness / NVML / vision-grace polls | 250 ms / 1 s / 2 s | `/health`, the per-PID figure, the wait for the compute-buffer line |
| `TERM_WAIT_S` / `KILL_WAIT_S` / `NVML_GONE_WAIT_S` | 3 s / 2 s / 2 s | SIGTERM, SIGKILL, and the card giving the memory back |
| `TERMINATE_ALL_BOUND_S` / reaper interval | 20 s / 5 s | the shutdown sweep; how often ended children are noticed |

#### Endpoints

| Endpoint | What it does |
|---|---|
| `GET /api/llm/models` | the aliases whose files are on disk, plus what is loaded right now — each loaded entry additionally carries `pid`, `port` and `state` |
| `POST /api/llm/unload` | end a child. Optional `force` skips the busy check; a refusal answers **409**, because a model reported as unloaded while it still sits on the card is how the card fills up |
| `GET /api/llm/health` | `status`, plus `backend` (`"llama-server"`), the `binary` and its `build` string — a wrong or missing llama.cpp build is the one deployment fault that makes every model on this service unavailable at once |

Request and response shapes are otherwise byte-compatible with the in-process engine; `pid`/`port`/`state`, `force` and the two `/health` fields are additive.

Every failure answers with its real cause and a status code that says which class it was:

| Failure | Status | Body |
|---|---|---|
| load refused (no room, missing file, child never became ready, vision buffer absent) | 503 | the reason, with the free-VRAM figure or the child's exit code and last lines |
| the child answered 503 (still loading) | 503 | the child's own message |
| the child refused the request (bad request, prompt longer than `n_ctx`) | 500 | `<alias>: <message> (HTTP <code>)` |
| the child died mid-answer, or the stream ended without its terminator | 500 | `<alias>'s server … (exit -11): <last lines>` |

Up to 1200 characters travel, because those last lines **are** the diagnosis and `LLMClient._body_reason` puts them in the DevServer log. On the streaming route all three classes arrive as an error *event* rather than a status code — the response has already begun — and the event never replaces the tokens that came before it, so a refused load (which raises on the first iteration, before any token) stays distinguishable from a generation that broke off midway.

#### The engine switch

`LLM_ENGINE` selects which engine `get_llm_backend()` builds, and exactly one is ever constructed:

* `child` (default) — supervised `llama-server` processes, everything above.
* `inprocess` — the older llama-cpp-python engine in `services/llm_backend.py`, kept as the rollback while the child engine is under measurement. It logs a warning saying that a model crash takes the service with it, and `force` on `/api/llm/unload` is refused there rather than faked: freeing a model under a running generation would take the process down.

A spelling that is neither is **refused**, not fallen back on — a typo that quietly selects the default would hide which engine is running, and the two differ in exactly the property that matters.

What holds on this path:

- The DevServer reaches it **only** through `LLMClient` (`devserver/my_app/services/llm_client.py`). A raw `requests.post` to `:17803/api/llm/*` from a route is forbidden — the safety checks, the DSGVO check, the VLM safety check and the Compare Hub's readings all go through that one client.
- **No output cap, anywhere on the path:** `max_tokens` is left out of the payload unless a caller gave one, `-n -1` is on the child's command line, and every `LLAMA_ARG_*` is stripped from its environment so nothing can put one back. And no read timeout: `LLM_TIMEOUT = (10, None)` (config.py) on the DevServer side, connect-only on the service→child side, and the child's own `-to` set to 30 days.
- **Fail-closed.** Every failure is an error with the real cause and status code. A stream that ends without the child's terminator raises rather than reporting `finish_reason: "stop"` — the image safety check reads that field, and would otherwise pass a truncated reading as a finished one. A `finish_reason` or `stop_type` this build does not use today maps to `"length"`, never to `"stop"`.
- **The coordinator stays the single residency authority.** Children are booked by their measured figure, evicted through `evict_model` (refused while a request is in flight), ended first by `emergency_reclaim_foreign`, and invisible to kill-foreign as foreign — that route refuses an owned PID by name and points at `unload force`. See Part 27.
- **One slot, no queue for inference.** A load takes the admission slot (`llm-load`) with a 5 s deadline and goes ahead unserialised rather than waiting — a content check must not queue behind a video render. Inference itself takes no slot: the child holds one slot of its own (`-np 1`), so two requests for the same alias queue there. See Part 40.
- A model that fills its context ends with `finish_reason: "length"`, not with an error — `--no-context-shift` makes the child stop and say so. A prompt longer than `n_ctx` is an HTTP error from the child and is surfaced as one.
- Images travel as `image_url` data URLs whose MIME is sniffed from the bytes, and `cache_prompt: false` is sent whenever images are present: reusing a cached prefix across two readings is precisely the shape the damaged second reading had.

GPU Service therefore handles media inference (Diffusers, MMAudio, Cross-Aesthetic with the Stable Audio synth) **and** the local LLM/VLM station; the Latent Text Lab's station went with stage 8 of the move to ComfyUI (2026-10-10).

**Note:** Blender headless rendering runs as a subprocess in the **DevServer** (not GPU Service), because Eevee uses OpenGL (not CUDA). See `devserver/my_app/services/blender_service.py`.

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
| `devserver/my_app/services/heartmula_client.py` | one prompt of the node `ai4artsed_heartmula`, run by ComfyUI (stage 6) |
| `devserver/my_app/services/stable_audio_client.py` | one prompt of the node `ai4artsed_stable_audio`, run by ComfyUI (stage 6) |
| `devserver/my_app/services/hunyuan3d_client.py` | one prompt of the node `ai4artsed_hunyuan3d`, run by ComfyUI (stage 6) |
| `devserver/my_app/services/text_client.py` | the tokenizer doors of the Latent Text Lab, asked of ComfyUI's HTTP routes (stage 5) |
| `devserver/my_app/services/llm_client.py` | the DevServer's local language models, one prompt of the node `ai4artsed_local_llm`, run by ComfyUI (stage 3) |
| `devserver/my_app/services/llm_backend.py` | LLM client singleton factory (`get_llm_backend()`) |

---

**Document Status:** Active (2026-03-06)
**Maintainer:** AI4ArtsEd Development Team
