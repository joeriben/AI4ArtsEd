# AI4ArtsEd — Required AI Models

Complete inventory of all AI models used by the platform.
**Updated:** 2026-10-01

> Architecture note: the local language and image-reading models are safetensors
> snapshots under ComfyUI's `models/llm/` and are run by ComfyUI itself through the
> platform's node `ai4artsed_local_llm` (stage 3 of the move to ComfyUI,
> 2026-09-12). The earlier Ollama path is dead code. The safety classifier is the
> exception: since 2026-09-24 the GPU service runs it as a `llama-server` child
> from the GGUF store `llama-server-models/` (see "Safety classifier" below).
>
> Since stage 6 (2026-09-14) the same holds for the media stations: the weights of
> Stable Audio 3, ImageBind, MMAudio, HeartMuLa, Hunyuan3D 2 and the media readers
> are folders under ComfyUI's `models/<station>/`, run by the platform's node
> package and installed by `./download_media_models.sh` from one table,
> `devserver/config/local_media_weights.json` (section 1a). Sections 2 to 4 describe
> the paths the GPU service read them from; they stay until stage 8 takes that
> service down.

---

## Overview

| Category | Size | Purpose |
|----------|------|---------|
| **Local language models** (`<repo>/dlbackend/ComfyUI/models/llm/`) | ~232 GB if every alias in the table is kept locally | Stage 1–3 LLM, image reading, Compare Hub |
| **Safety classifier** (`<repo>/llama-server-models/shieldstral-3b/`) | 4.2 GB | Every safety check of prompts, images and person names |
| **HuggingFace cache** (`~/.cache/huggingface/hub/`) | ~119 GB | Diffusers image and video generation, encoders (auto-downloaded on first use) |
| **HuggingFace text models** (`~/.cache/huggingface/hub/`) | ~215 GB | Bias Archaeology 1 + 2 / Latent Text Lab |
| **ComfyUI models** (`<repo>/dlbackend/ComfyUI/models/`) | ~450 GB | ComfyUI generation pipeline |
| **Media stations** (`<repo>/dlbackend/ComfyUI/models/<station>/`) | ~105 GB for every alias of the table, plus ~16 GB in the HF cache | Stable Audio 3, ImageBind, MMAudio, HeartMuLa, Hunyuan3D 2, the media readers (section 1a) |
| **GPU Service Weights** (`gpu_service/weights/`, `ext_weights/`) | ~6 GB | MMAudio, the GPU service's copy (section 4; until stage 8) |
| **HeartMuLa** (`~/ai/heartlib/ckpt/`) | ~21 GB | Music generation checkpoint, the GPU service's copy (section 3; until stage 8) |
| **Speech synthesis** (`~/.cache/supertonic3/`, HF cache, `~/ai/piper/`) | ~10 GB | Four text-to-speech systems: the platform's voice and three heard against it |
| **Total** (worst case, all models present) | **~700 GB** | |

A minimal install with one chat model + the safety classifier + an image reader + only
the configs you actually plan to run is far smaller (typically 50–200 GB).

**None of this belongs in the repository.** Every model and every third-party
technology on this list is fetched — by a script, by the Settings UI, or on
first use — and lives outside the working tree. That holds regardless of size
or licence: what can be downloaded is downloaded, never vendored.

---

## 1. Local language and image-reading models (ComfyUI, `models/llm/`)

**Where the store is.** `<repo>/dlbackend/ComfyUI/models/llm/`, one folder per
Hugging Face repository, named as the repository with `/` written as `--`
(`Qwen/Qwen3-1.7B` → `Qwen--Qwen3-1.7B`). The folder is registered with ComfyUI
under the model type `llm` by the platform's own node package
(`comfyui_nodes/ai4artsed_comfyui/_local_llm.py`), so an `extra_model_paths.yaml`
entry for `llm` moves it like any other model type. The directory is gitignored;
nothing here belongs in the repository.

Every model is a safetensors snapshot (the repository as published, minus what the
table's `ignore` names) and is loaded by ComfyUI itself, under its memory
management, through the node `ai4artsed_local_llm` (stage 3 of the move to
ComfyUI). The DevServer queues one prompt of that node for every local chat and image reading
(`devserver/my_app/services/llm_client.py`); the safety checks go to the GPU service
instead (see "Safety classifier" below). Where the maker publishes
an FP8 checkpoint of a model above ~20 B parameters, that is the one in the table
(a 27 B model is 55.6 GB in BF16 and 30.9 GB in FP8); everything smaller is the BF16
release. Loading an FP8 checkpoint needs `accelerate` in ComfyUI's venv
(`comfyui_nodes/ai4artsed_comfyui/requirements.txt`, installed by
`install_comfyui_nodes.sh` when the package is linked); a card below compute
capability 8.9 gets the weights dequantised to BF16 by transformers, at BF16 size.

The table below is the whole of `devserver/config/local_llm_weights.json`, which is
the single source of truth: an alias that is not there cannot be installed or run,
and a new one added there appears in the Settings UI installer and in the model
lists by itself. **The third column is the folder ComfyUI lists.**

### Chat-capable models (Compare Hub, Stage 1–3 LLM, interception)

| Alias | HuggingFace repo | Folder under `models/llm/` | Size | Notes |
|-------|------------------|----------------------------|-----:|-------|
| `qwen3.8:27b` | `Qwen/Qwen3.8-27B-FP8` | `Qwen--Qwen3.8-27B-FP8` | 30.9 GB | reads images |
| `qwen3.5:27b` | `Qwen/Qwen3.5-27B-FP8` | `Qwen--Qwen3.5-27B-FP8` | 30.9 GB | reads images |
| `qwen3.5:9b` | `Qwen/Qwen3.5-9B` | `Qwen--Qwen3.5-9B` | 19.3 GB | reads images |
| `qwen3.5:4b` | `Qwen/Qwen3.5-4B` | `Qwen--Qwen3.5-4B` | 9.3 GB | reads images |
| `qwen3:4b` | `Qwen/Qwen3-4B` | `Qwen--Qwen3-4B` | 8.0 GB |  |
| `qwen3:1.7b` | `Qwen/Qwen3-1.7B` | `Qwen--Qwen3-1.7B` | 4.1 GB |  |
| `devstral:24b` | `mistralai/Devstral-Small-2-24B-Instruct-2512` | `mistralai--Devstral-Small-2-24B-Instruct-2512` | 25.8 GB | reads images |
| `ministral3:3b` | `mistralai/Ministral-3-3B-Instruct-2512` | `mistralai--Ministral-3-3B-Instruct-2512` | 4.7 GB | reads images |
| `gemma-3-4b` | `google/gemma-3-4b-it` | `google--gemma-3-4b-it` | 8.6 GB | gated: needs `HF_TOKEN`; reads images |
| `smollm3:3b` | `HuggingFaceTB/SmolLM3-3B` | `HuggingFaceTB--SmolLM3-3B` | 6.2 GB |  |
| `llama3.2:3b` | `meta-llama/Llama-3.2-3B-Instruct` | `meta-llama--Llama-3.2-3B-Instruct` | 6.4 GB | gated: needs `HF_TOKEN` |
| `eurollm:1.7b` | `utter-project/EuroLLM-1.7B-Instruct` | `utter-project--EuroLLM-1.7B-Instruct` | 3.3 GB |  |
| `granite3.1:2b` | `ibm-granite/granite-3.1-2b-instruct` | `ibm-granite--granite-3.1-2b-instruct` | 5.1 GB |  |

### Utility models (image reading, not exposed in Compare Hub)

| Alias | HuggingFace repo | Folder under `models/llm/` | Size | Notes |
|-------|------------------|----------------------------|-----:|-------|
| `qwen3-vl:32b` | `Qwen/Qwen3-VL-32B-Instruct-FP8` | `Qwen--Qwen3-VL-32B-Instruct-FP8` | 35.5 GB | reads images |
| `qwen3-vl:8b` | `Qwen/Qwen3-VL-8B-Instruct` | `Qwen--Qwen3-VL-8B-Instruct` | 17.5 GB | reads images |
| `qwen3-vl:4b` | `Qwen/Qwen3-VL-4B-Instruct` | `Qwen--Qwen3-VL-4B-Instruct` | 8.9 GB | reads images |
| `qwen3-vl:2b` | `Qwen/Qwen3-VL-2B-Instruct` | `Qwen--Qwen3-VL-2B-Instruct` | 4.3 GB | reads images |
| `llama-guard3:1b` | `meta-llama/Llama-Guard-3-1B` | `meta-llama--Llama-Guard-3-1B` | 3.0 GB | gated: needs `HF_TOKEN` |

`llama-guard3:latest` is a second name for `llama-guard3:1b` (the table's `aliases`).
`llama-guard3:1b` was the safety model until 2026-09-24; no check asks it any more.
All entries together are 232 GB; a working install holds a few of them.

### Safety classifier (GPU service, not in this table)

Every check of prompts, images and person names asks one model, `SAFETY_MODEL` =
`shieldstral:3b`: Shieldstral 1.0 3B (`mistralai/Shieldstral-1.0-3B`), a Q8_0 GGUF
plus its image projector `mmproj-F16.gguf`, 4.2 GB together. ComfyUI does not run
it. The GPU service starts it as a `llama-server` child from
`<repo>/llama-server-models/shieldstral-3b/` (registry entry in
`gpu_service/services/llm_backend.py`). Without the two files every check comes
back without a verdict and the run is blocked.

The Hugging Face repository holds the model as safetensors only; the two GGUF files
were converted from it with the pinned llama.cpp clone (comment on the registry
entry; the pinned revision is in [`SOFTWARE_VERSIONS.md`](SOFTWARE_VERSIONS.md)). The
GPU service's installer therefore cannot fetch them: its download of
`Shieldstral-1.0-3B-Q8_0.gguf` ends in "Entry Not Found". Copy the folder from an
installation that has it. `SAFETY_MODEL` itself is set on the settings page, section
"Local Safety Model".

### Installing

Three ways, all reading the same table:

- **Settings UI**: the Install button next to a local model in the model lists
  (`POST /api/chat/install`, progress streamed).
- **Script**: `./download_llm_models.sh` installs every local model a model role of
  the settings names, and the model the look at images runs on (`qwen3-vl:4b`, or
  `RESONA_VIEW_VLM_MODEL`); `./download_llm_models.sh qwen3:1.7b llama-guard3:1b`
  the aliases given. Idempotent; an interrupted download resumes.
- **By hand**: `huggingface-cli download <repo> --local-dir
  dlbackend/ComfyUI/models/llm/<folder>` with the folder from the third column.

The download is staged beside the destination (`.incoming-<folder>`) and renamed
into place when the snapshot is whole, so a folder under `models/llm/` either holds
a model or is absent; a snapshot counts as installed when `config.json`, every shard
its index names and no `.incomplete` part are what the folder holds
(`comfyui_nodes/ai4artsed_comfyui/_snapshot.py`, read by both sides). ComfyUI lists
a new folder at its next validation; no restart. A gated repository (Gemma, Llama)
needs a Hugging Face account that accepted the model's licence and its token as
`HF_TOKEN` in the DevServer's environment.

### Minimum set for production (safety-relevant)

A working production deploy needs at least:

- One chat-capable model that is set as the default for Stages 1–3 (e.g. `qwen3:4b`)
- `llama-guard3:1b` (Stage 1/3 content filtering, fail-closed safety gate)
- `qwen3-vl:2b` (post-generation image safety check, kids/youth)

All other aliases are optional and can be installed on demand.

---

## 1a. Media stations (ComfyUI, `models/<station>/`)

Since stage 6 of the move to ComfyUI (2026-09-14) the weights of the media stations
live under `<repo>/dlbackend/ComfyUI/models/<station>/<folder>/` and are run by
ComfyUI itself through the platform's node package
(`comfyui_nodes/ai4artsed_comfyui/`, one node per station, under ComfyUI's memory
management); the DevServer queues one prompt of the station's node for every
generation and every reading. The station folders are registered with ComfyUI by
the package (`_card.py`), so an `extra_model_paths.yaml` entry moves them like any
other model type. Which alias is which source, which folder it lands in and which
files make the folder whole is ONE table, `devserver/config/local_media_weights.json`:
the nodes, the installer and the backend status of the settings page read it, and
the third column below is the folder ComfyUI lists.

| Alias | Station | Folder under `models/<station>/` | Source | Size | Notes |
|-------|---------|----------------------------------|--------|-----:|-------|
| `stable-audio-3-medium` | `stable_audio` | `stabilityai--stable-audio-3-medium` | `stabilityai/stable-audio-3-medium` | 10.4 GB | gated: needs `HF_TOKEN`; the tier on a card with 50 GB or more |
| `stable-audio-3-small-music` | `stable_audio` | `stabilityai--stable-audio-3-small-music` | `stabilityai/stable-audio-3-small-music` | 3.5 GB | gated; the music tier below 50 GB |
| `stable-audio-3-small-sfx` | `stable_audio` | `stabilityai--stable-audio-3-small-sfx` | `stabilityai/stable-audio-3-small-sfx` | 3.5 GB | gated; the sound-effects tier below 50 GB |
| `imagebind-huge` | `imagebind` | `imagebind_huge` | `https://dl.fbaipublicfiles.com/imagebind/imagebind_huge.pth` | 4.8 GB | |
| `mmaudio-large-44k-v2` | `mmaudio` | `large_44k_v2` | three files of `hkchengrex/MMAudio` (`weights/mmaudio_large_44k_v2.pth`, `ext_weights/v1-44.pth`, `ext_weights/synchformer_state_dict.pth`) | 6.3 GB | plus `apple/DFN5B-CLIP-ViT-H-14-384` (7.9 GB) in the HF cache |
| `heartmula-3b` | `heartmula` | `heartmula-3b` | `HeartMuLa/HeartMuLaGen` into the folder, `HeartMuLa/HeartMuLa-RL-oss-3B-20260123` into `HeartMuLa-oss-3B/`, `HeartMuLa/HeartCodec-oss-20260123` into `HeartCodec-oss/` | 22.4 GB | plus `OpenMuQ/MuQ-MuLan-large`, `OpenMuQ/MuQ-large-msd-iter`, `xlm-roberta-base` (~7.6 GB) in the HF cache |
| `hunyuan3d-2` | `hunyuan3d` | `tencent--Hunyuan3D-2` | `tencent/Hunyuan3D-2`, the shape, delight and paint models; the fast and turbo variants and the `.ckpt` copies left out | 14.4 GB | `rembg` fetches its `u2net.onnx` (176 MB) into `~/.u2net` on the first background removal |
| `midashenglm:7b` | `media_reading` | `mispeech--midashenglm-7b` | `mispeech/midashenglm-7b` | 33.2 GB | the audio describer; ships its own modeling code (`trust_remote_code`, declared in the table) |
| `hearttranscriptor` | `media_reading` | `HeartMuLa--HeartTranscriptor-oss` | `HeartMuLa/HeartTranscriptor-oss` | 3.1 GB | the lyrics transcriber |
| `muq-mulan` | `media_reading` | `OpenMuQ--MuQ-MuLan-large` | `OpenMuQ/MuQ-MuLan-large` | 2.7 GB | a music tagger; plus `OpenMuQ/MuQ-large-msd-iter` and `xlm-roberta-base` in the HF cache (the same two HeartMuLa needs) |
| `clap-music-speech` | `media_reading` | `laion--larger_clap_music_and_speech` | `laion/larger_clap_music_and_speech` | 0.8 GB | the music tagger the reading block names for `music_tags`; `muq-mulan` on request |

Every alias together is 105 GB under `models/`, plus ~16 GB of repositories the
station libraries load by name from the Hugging Face cache (the table's `cached`;
the installer fetches them as well, so a fresh installation runs without a download
on first use). The image and video readers are language models of section 1
(`qwen3-vl:8b`; the table's reading block names them with the `local/` prefix).

### Installing

- **Script**: `./download_media_models.sh` installs every alias of the table;
  `./download_media_models.sh heartmula-3b clap-music-speech` the aliases given;
  `./download_media_models.sh media_reading` every alias of a station. Idempotent;
  an interrupted download is taken up again: the files that were finished stay,
  the file that was in flight is fetched again (a URL from the byte it stopped at,
  a repository file rewritten from Hugging Face's chunk cache).
- **By hand**: a Hugging Face repository with `huggingface-cli download <repo>
  --local-dir dlbackend/ComfyUI/models/<station>/<folder>`, the folder from the third
  column; the ImageBind checkpoint with `wget` into `models/imagebind/imagebind_huge/`;
  MMAudio's three files at their repository paths under `models/mmaudio/large_44k_v2/`;
  HeartMuLa's three repositories into `heartmula-3b/`, `heartmula-3b/HeartMuLa-oss-3B/`
  and `heartmula-3b/HeartCodec-oss/`. An installation that ran the GPU service can
  link the folders it has (`~/.cache/huggingface/hub/models--<repo>/snapshots/<hash>`,
  `heartlib/ckpt`, `gpu_service/weights`) instead of downloading again.

The download is staged beside the destination (`.incoming-<folder>`) and renamed
into place when the folder is whole, so a folder under `models/<station>/` either
holds a model or is absent. Whether a folder is whole is decided once, in the node
package (`comfyui_nodes/ai4artsed_comfyui/_whole.py`, per station: every file the
station's library reads is there, and no `.incomplete` part lies under what it
reads); the installer, the settings page and the node itself run that one test.
ComfyUI lists a new folder at its next validation; no restart. The Stable Audio 3 repositories are gated: a Hugging Face
account that accepted the licence, its token as `HF_TOKEN`.

The libraries behind the stations (stable-audio-tools, heartlib, MMAudio, ImageBind,
hy3dgen with its CUDA extension `custom_rasterizer`, MuQ) go into ComfyUI's venv with
`./install_comfyui_media_libs.sh`, which `install_comfyui_nodes.sh` runs after
linking the package; the pinned packages are
`comfyui_nodes/ai4artsed_comfyui/requirements-media.txt`, the git commits the same
ones `deployment/requirements-git.txt` names for the DevServer's venv.

---

## 2. HuggingFace Diffusers cache (GPU Service)

Used by the GPU Service (`gpu_service/services/diffusers_backend.py`).
Stored at `~/.cache/huggingface/hub/` (content-addressable, directly portable).

Override the cache location with `DIFFUSERS_CACHE_DIR` (env var) — by default,
HuggingFace's standard cache is used.

### Image Generation

| Model | HF ID | Size | Purpose |
|-------|-------|------|---------|
| SD 3.5 Large | `stabilityai/stable-diffusion-3.5-large` | 26 GB | Primary image generation |
| SD 3.5 Large Turbo | `stabilityai/stable-diffusion-3.5-large-turbo` | 55 GB | Fast image generation |

### Video Generation

| Model | HF ID | Size | Purpose |
|-------|-------|------|---------|
| Wan 2.2 TI2V 5B | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | 32 GB | Text/image-to-video |

### Encoders / Utility

| Model | HF ID | Size | Purpose |
|-------|-------|------|---------|
| CLIP ViT-L/14 | `openai/clip-vit-large-patch14` | 1.6 GB | Cross-aesthetic, Hallucinator fusion |
| DFN5B CLIP ViT-H-14 | `apple/DFN5B-CLIP-ViT-H-14-384` | 3.7 GB | Cross-aesthetic generation |
| BigVGAN v2 44kHz | `nvidia/bigvgan_v2_44khz_128band_512x` | 467 MB | Audio vocoder |

### HF Cache Portability

The HuggingFace cache is directly portable between machines:
1. Copy `~/.cache/huggingface/hub/models--org--name/` directories
2. Place at the same path on the target machine
3. `from_pretrained()` finds cached models automatically (sha256-based blob storage)

---

## 2b. HuggingFace text models (Latent Text Lab)

Used by the Latent Text Lab's probes (`devserver/my_app/services/text_probes.py`,
run as nodes of the platform's package on ComfyUI since stage 8 of the move;
the GPU service's text backend went on 2026-10-10) for Bias Archaeology 1 and 2
and Representation Engineering. These need direct logit access via HuggingFace
transformers — a GGUF station cannot give them that.
Stored at `~/.cache/huggingface/hub/`.

```bash
./download_textlab_models.sh                 # all three scenarios, ~215 GB
SCENARIOS=mixed ./download_textlab_models.sh # one of them
```

The script reads the list from `devserver/config/text_presets.json`, which is
also where the surface gets it from — there is no second copy to drift.

The two instruments offer **four lineups**, built out of three scenarios in the
config:

### "small models" — four makers, 2B to 4B

| Model | HF ID | Size (bf16) |
|-------|-------|-------------|
| Gemma 2 2B      | `google/gemma-2-2b-it`             | ~5 GB |
| Llama 3.2 3B    | `meta-llama/Llama-3.2-3B-Instruct` | ~6 GB |
| Qwen3 1.7B      | `Qwen/Qwen3-1.7B`                  | ~4 GB |
| Qwen3 4B        | `Qwen/Qwen3-4B`                    | ~8 GB |

### "large models" — five makers, 7B to 12B

| Model | HF ID | Size (bf16) |
|-------|-------|-------------|
| OLMo 2 7B          | `allenai/OLMo-2-1124-7B-Instruct`    | ~14 GB |
| OLMo 3 7B          | `allenai/Olmo-3-7B-Instruct`         | ~14 GB |
| Nemotron Nano 9B   | `nvidia/NVIDIA-Nemotron-Nano-9B-v2`  | ~18 GB |
| DeepSeek 7B        | `deepseek-ai/deepseek-llm-7b-chat`   | ~14 GB |
| Mistral NeMo 12B   | `mistralai/Mistral-Nemo-Instruct-2407` | ~25 GB |

### "model family" — one family across its sizes

| Model | HF ID | Size (bf16) |
|-------|-------|-------------|
| Qwen3 1.7B | `Qwen/Qwen3-1.7B` | ~4 GB |
| Qwen3 4B   | `Qwen/Qwen3-4B`   | ~8 GB |
| Qwen3 8B   | `Qwen/Qwen3-8B`   | ~16 GB |
| Qwen3 14B  | `Qwen/Qwen3-14B`  | ~28 GB |

### "model over time" — one family, one size, five generations

The only lineup made of BASE models: over five generations the instruction tuning
is what changed most and most unevenly, so the base model is the closer thing to
"the same model, later".

| Model | HF ID | Size (bf16) |
|-------|-------|-------------|
| Qwen 7B (08/2023)    | `Qwen/Qwen-7B`    | ~15 GB |
| Qwen1.5 7B (02/2024) | `Qwen/Qwen1.5-7B` | ~15 GB |
| Qwen2 7B (06/2024)   | `Qwen/Qwen2-7B`   | ~15 GB |
| Qwen2.5 7B (09/2024) | `Qwen/Qwen2.5-7B` | ~15 GB |
| Qwen3 8B (04/2025)   | `Qwen/Qwen3-8B`   | ~16 GB |

**Total unique: 16 repositories, ~215 GB bf16** (Qwen3 4B and 8B each stand in two
lineups and are fetched once).

### Two repositories need something beyond the script

`meta-llama/Llama-3.2-3B-Instruct` is **gated** — accept its licence once in a
browser, then make a token available (`hf auth login`, or export `HF_TOKEN`).
Without it that one repo fails and the rest still download.

`Qwen/Qwen-7B` (08/2023) ships **its own loading code**: transformers refuses to
build it unless the service is allowed to execute the Python file that comes with
the repo (`trust_remote_code`). Downloading is harmless, nothing is executed by
the script — but until that is decided, a run over "model over time" stops at
this first model. The four later Qwen generations need nothing of the kind; from
Qwen1.5 on the architecture is part of transformers itself.

### Why pre-download at all

Nothing is broken at startup without it: the text backend fetches a model on
first use. But that fetch then sits inside the HTTP request, and behind a tunnel
with a request limit (Cloudflare cuts at 100 s) the run breaks instead of
waiting. A model that fails to load ends the whole run — the models after it in
the lineup are not asked.

The VRAM coordinator handles loading and eviction at runtime — only one Latent Lab
model is loaded at a time.

---

## 3. HeartMuLa (Music Generation)

> The GPU service's path. Since stage 6 the platform runs HeartMuLa on ComfyUI from
> `dlbackend/ComfyUI/models/heartmula/heartmula-3b/` (section 1a,
> `./download_media_models.sh heartmula-3b`); what follows fills the path the GPU
> service reads until stage 8.

heartlib is a separate git repository that holds both the Python package and the
checkpoint directory. Clone to `~/ai/heartlib/`, then install the Python package
editable into the AI4ArtsEd venv.

### Step 1 — Clone the heartlib repo

```bash
git clone https://github.com/HeartMuLa/heartlib.git ~/ai/heartlib
```

### Step 2 — Install the package editable (no deps)

The `--no-deps` flag is mandatory: heartlib pins its own torch version, which would
clobber the cu130 nightly stack.

```bash
~/ai/ai4artsed_development/venv/bin/python -m pip install --no-deps -e ~/ai/heartlib
```

### Step 3 — Download the checkpoints (~21 GB)

These are HuggingFace model repos, not part of the github clone:

```bash
mkdir -p ~/ai/heartlib/ckpt
cd ~/ai/heartlib

# RL-tuned version (recommended — better tag adherence):
huggingface-cli download HeartMuLa/HeartMuLa-RL-oss-3B-20260123 \
    --local-dir ./ckpt/HeartMuLa-oss-3B
huggingface-cli download HeartMuLa/HeartCodec-oss-20260123 \
    --local-dir ./ckpt/HeartCodec-oss

# Or original release (smaller download, weaker tag adherence):
# huggingface-cli download HeartMuLa/HeartMuLa-oss-3B   --local-dir ./ckpt/HeartMuLa-oss-3B
# huggingface-cli download HeartMuLa/HeartCodec-oss     --local-dir ./ckpt/HeartCodec-oss
```

### Resulting layout

```
~/ai/heartlib/
├── src/heartlib/                        (Python package code)
└── ckpt/
    ├── HeartMuLa-oss-3B/
    │   └── model-0000{1-4}-of-00004.safetensors   (≈14.7 GB)
    ├── HeartCodec-oss/
    │   └── model-0000{1-2}-of-00002.safetensors   (≈6.2 GB)
    └── tokenizer.json                              (8.7 MB)
```

**Critical runtime notes:**
- Vocab/codebook mismatch: MuLa vocab=8197, codec codebook=8192 → clamp fix in
  `flow_matching.py:75`.
- DO NOT wrap `self._pipeline()` in `torch.autocast`. heartlib handles autocast
  internally for MuLa; the codec needs float32.

---

## 4. GPU Service Weights (MMAudio)

> The GPU service's path. Since stage 6 the platform runs MMAudio on ComfyUI from
> `dlbackend/ComfyUI/models/mmaudio/large_44k_v2/` (section 1a,
> `./download_media_models.sh mmaudio-large-44k-v2`); what follows is the path the
> GPU service reads until stage 8.

Stored in `gpu_service/weights/` and `gpu_service/ext_weights/`.

| File | Size | Purpose |
|------|------|---------|
| `weights/mmaudio_large_44k_v2.pth` | 3.9 GB | MMAudio main model |
| `ext_weights/v1-44.pth` | 1.2 GB | Visual encoder |
| `ext_weights/synchformer_state_dict.pth` | 907 MB | Sync model |
| **Total** | **~6 GB** | |

These are downloaded automatically by the MMAudio installer in the upstream repo. On
a fresh install, they appear on first use of a video→audio configuration.

---

## 4b. Speech Synthesis (three systems)

Three synthesisers, none of them in this repository, all of them downloaded.
They are not interchangeable and they are not ranked. The platform speaks with
Supertonic 3. The other two are in Compare → Voices because they are asked for
a voice in different ways, and the difference is the question that mode puts:
VoxCPM2 is asked in words, inside the sentence itself; Piper cannot be asked at
all, and is installed because it is the only one of the three with a voice for
every platform language.

Qwen3-TTS stood in the middle column until 2026-08-12, when a transformers
upgrade in the platform's environment broke it and the technology was removed.
VoxCPM2 took its place — in its own environment, precisely so that the same
thing cannot happen again.

| | Supertonic 3 | VoxCPM2 | Piper |
|---|---|---|---|
| Role | **the platform's voice** | material for study | the only voice for Hebrew |
| Runs on | CPU, in-process | GPU, **separate process** | CPU, **separate process** |
| Lives in | `~/.cache/supertonic3/` | `~/ai/voxcpm/` + HF cache | `~/ai/piper/` |
| Size | ~400 MB | ~4.7 GB weights + ~5.9 GB own venv | ~1.4 GB (15 voices) |
| VRAM | none | ~8 GB while the worker lives | none |
| Platform languages | 9 of 10 (no Hebrew) | 8 of 10 (no Bulgarian, no Ukrainian) | **10 of 10** |
| Emotion | none at all | the speaker described in words, inside the text | none at all |
| Continues past the text? | no | **yes** | no |
| Fetch with | auto, on first use | `./download_voxcpm.sh` | `./download_piper.sh` |
| Off switch | `SUPERTONIC_ENABLED=false` | `VOXCPM_ENABLED=false` | `PIPER_ENABLED=false` |

Everything a text-to-speech model does here is verbatim: the input is the
utterance, not a prompt, and nothing on the way rewrites, optimises or
translates it.

### Supertonic 3 — the platform's voice

```bash
# No download step. The `supertonic` package fetches supertonic-3 into
# ~/.cache/supertonic3 on first use (auto_download=True).
```

Non-autoregressive (flow matching plus a speech autoencoder), so it cannot
continue past the text it was handed — which is why it was chosen. Ten preset
voices, five labelled male and five female; the platform never speaks as one
of them but as a mixture, and the five mixtures live in `config.SUPERTONIC_VOICES`.
Runs on four CPU threads on purpose: the GPU stays free for image and video.

Origin of the recorded voices: **not disclosed** by the publisher, consent of
the recorded speakers unknown.

### VoxCPM2 — the one that is asked in words

```bash
./download_voxcpm.sh       # own venv + weights, idempotent
```

Its own virtual environment at `~/ai/voxcpm`, and that is not a preference:
`voxcpm` pins `datasets<4` and `gradio>=6` against the platform's 4.5.0 and
5.50.0, so installing it alongside would move both under everything else that
uses them. Qwen3-TTS was lost to exactly that class of move.

Tokenizer-free diffusion autoregressive, 2 B parameters, 48 kHz out, 30
languages by its model card — eight of the platform's ten; Bulgarian and
Ukrainian are answered with an English rendering of the same sentence, and
Russian is deliberately not offered in Ukrainian's place.

The voice is asked for in words, and the words go **inside the text**:

```
(A young woman, gentle and sweet voice)Guten Tag.
```

so the model itself decides which part of the string is an instruction and
which part is what to say. Left empty, nothing is asked and it reads the
delivery off the sentence. Autoregressive: it **can carry on past the sentence
it was handed**, which is why the output config is restricted to
adult/research.

It runs as a worker on port 17805 (`./2_start_voxcpm.sh`), started by the
platform on demand — about 25 seconds to load, against 0.3 seconds to speak,
which is why it stays resident rather than starting per utterance. A caller has
to name it (`system: "voxcpm"`).

It can also clone a voice from a few seconds of recording. **That is not
reachable from this platform** — no parameter in the chunk, the backend or the
worker leads to it.

Origin of the recorded voices: **not disclosed** ("2M+ hours multilingual
speech", no source named), consent unknown.

### Piper — every language, and a named dataset per voice

```bash
./download_piper.sh        # own venv + 14 voices, ~1.3 GB, idempotent
```

Installed into `~/ai/piper/` — `venv/` for the code, `models/` for the voices —
and called as a subprocess. Its own environment keeps its onnxruntime and
espeak-ng data from colliding with the platform's. Paths are overridable with
`PIPER_BIN` and `PIPER_MODEL_DIR`; both default to exactly the above.

VITS with a duration predictor, ~0.03–0.4 s per sentence on the CPU. Code is
GPL-3.0-or-later (OHF-Voice/piper1-gpl); the voices carry their own licences,
listed below.

The only synthesiser here with a voice for **every** platform language. Where
the catalogue holds several regional voices for one language, several are
installed — one per language would make this platform decide, silently and
once, that Spanish is Spain. Where it holds one, that is worth hearing too.

| Voice | Language | Dataset | Licence |
|---|---|---|---|
| `ar_JO-kareem-medium` | Arabic (Jordan) — the only Arabic voice there is | arabicttstrain | see dataset |
| `bg_BG-dimitar-medium` | Bulgarian | OHF-Voice/voice-datasets | CC0 |
| `de_DE-mls-medium` | German — 236 corpus speakers, the only German voice here above 16 kHz | Multilingual LibriSpeech, openslr 94 | CC BY 4.0 |
| `en_US-lessac-high` | English (US) — a base voice many other Piper voices were retrained from | Blizzard 2013 Lessac | see dataset |
| `en_GB-cori-high` | English (GB) | LibriVox | public domain |
| `es_ES-davefx-medium` | Spanish (Spain) | OHF-Voice/voice-datasets | CC0 |
| `es_MX-claude-high` | Spanish (Mexico) | HirCoir Piper-TTS-Spanish | Apache-2.0 |
| `es_AR-daniela-high` | Spanish (Argentina) | openslr 61 | CC BY-SA 4.0 |
| `fr_FR-siwis-medium` | French | SIWIS, Edinburgh datashare | CC BY 4.0 |
| `he_IL-saspeech-medium` | Hebrew — **the only Hebrew voice on this platform** | SASPEECH gold standard, openslr 134 | see dataset |
| `ko_KR-kss-medium` | Korean | KSS | CC BY-NC-SA 4.0 |
| `tr_TR-dfki-medium` | Turkish | DFKI ot-data | CC BY-NC-SA 4.0 |
| `uk_UA-tetiana-high` | Ukrainian | egorsmkv/ukrainian-tts-datasets | Apache-2.0 |
| `uk_UA-mykyta-high` | Ukrainian | the same | Apache-2.0 |

Dataset and licence are quoted from each voice's own `MODEL_CARD`, read
2026-08-10. Two of them are non-commercial (Korean, Turkish); that is no
obstacle to this platform's own licence, but it belongs in view before anything
built from them is passed on.

Ukrainian is worth a note of its own: the other two synthesisers have no
Ukrainian at all and answer it in English, and Russian is never offered in its
place. Piper has three high-quality Ukrainian voices; two are installed.

To add a language or a further voice, extend `VOICES` in `download_piper.sh`
with its path under `rhasspy/piper-voices` and re-run. The platform reports
what it finds on disk — nothing has to be registered anywhere else.

---

## 5. ComfyUI Models

Stored at `<repo>/dlbackend/ComfyUI/models/` (i.e. inside the AI4ArtsEd
single-directory layout, NOT a separate SwarmUI installation).

Used by ComfyUI for every output configuration that routes through ComfyUI — which
on workshop / school PCs is the **only** generation path (no Diffusers GPU service
there). On the main production server, ComfyUI also serves as the fallback when the
Diffusers GPU service is unavailable.

> Deployment principle: the ComfyUI path MUST work standalone, without the Diffusers
> GPU service and without the HuggingFace cache. All checkpoint, CLIP, VAE, T5 files
> must therefore be present as independent files inside `dlbackend/ComfyUI/models/`,
> not symlinked into `~/.cache/huggingface/`.

### checkpoints/ (~164 GB)

| File | Size |
|------|------|
| `Flux1/flux2-dev.safetensors` | 61 GB |
| `Flux1/flux2_dev_fp8mixed.safetensors` | 34 GB |
| `OfficialStableDiffusion/sd3.5_large.safetensors` | 16 GB |
| `ltxv-13b-0.9.7-distilled-fp8.safetensors` | 15 GB |
| `ace_step_v1_3.5b.safetensors` | 7.2 GB |

### clip/ (~125 GB)

| File | Size |
|------|------|
| `mistral_3_small_flux2_bf16.safetensors` | 34 GB |
| `mistral_3_small_flux2_fp8.safetensors` | 17 GB |
| `qwen_image_official/.../qwen_2.5_vl_7b.safetensors` | 16 GB |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | 8.8 GB |
| `qwen_3_4b.safetensors` | 7.5 GB |
| `t5xxl_fp16.safetensors` | 9.8 GB |
| `t5xxl_enconly.safetensors` | 4.6 GB |
| `clip_g.safetensors` | 1.3 GB |
| `clip_l.safetensors` | 235 MB |
| (+ smaller) | |

### diffusion_models/ (~118 GB)

| File | Size |
|------|------|
| `qwen_image_official/.../qwen_image_bf16.safetensors` | 39 GB |
| `qwen_image_fp8_e4m3fn.safetensors` | 20 GB |
| `qwen_image_edit_2511_fp8mixed.safetensors` | 20 GB |
| `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | 14 GB |
| `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` | 14 GB |
| `wan2.2_ti2v_5B_fp16.safetensors` | 9.4 GB |

### vae/ (~5.4 GB)

| File | Size |
|------|------|
| `LTXV/ltxv_vae.safetensors` | 2.4 GB |
| `wan2.2_vae.safetensors` | 1.4 GB |
| `diffusion_pytorch_model.safetensors` (Stable Audio codec) | 596 MB |
| `Flux/flux2-vae.safetensors` | 321 MB |
| `wan_2.1_vae.safetensors` | 243 MB |

### loras/ (~9.8 GB)

| File | Size |
|------|------|
| `wan2.2_*_lightx2v_4steps_lora_*.safetensors` (4 files) | 4.8 GB |
| `Qwen-Image-Edit-Lightning-*.safetensors` (2 files) | 1.6 GB |
| `sd35_solarization*.safetensors` (5 files) | 1.6 GB |
| `sd3.5-large_cooked_negatives*.safetensors` (5 files) | 1.6 GB |
| `flux2_berthe_morisot.safetensors` | 373 MB |

### Flux 2 — canonical sources

The ComfyUI-ready Flux 2 components are repackaged by Comfy-Org at
[`Comfy-Org/flux2-dev`](https://huggingface.co/Comfy-Org/flux2-dev) under
`split_files/`. The four files below can be pulled automatically by
`./download_flux2.sh` from the repo root.

| File | Source | Notes |
|------|--------|-------|
| `clip/mistral_3_small_flux2_fp8.safetensors` | [Comfy-Org/flux2-dev](https://huggingface.co/Comfy-Org/flux2-dev/blob/main/split_files/text_encoders/mistral_3_small_flux2_fp8.safetensors) | The variant for the smaller card (RTX 5090) |
| `clip/mistral_3_small_flux2_bf16.safetensors` | [Comfy-Org/flux2-dev](https://huggingface.co/Comfy-Org/flux2-dev/blob/main/split_files/text_encoders/mistral_3_small_flux2_bf16.safetensors) | Full precision; needs ≥48 GB GPU |
| `checkpoints/Flux1/flux2_dev_fp8mixed.safetensors` | [Comfy-Org/flux2-dev](https://huggingface.co/Comfy-Org/flux2-dev/blob/main/split_files/diffusion_models/flux2_dev_fp8mixed.safetensors) | The ComfyUI workflow default |
| `vae/Flux/flux2-vae.safetensors` | [Comfy-Org/flux2-dev](https://huggingface.co/Comfy-Org/flux2-dev/blob/main/split_files/vae/flux2-vae.safetensors) | Required by all Flux 2 workflows |

The remaining Flux files listed in the tables above are **not** in
`Comfy-Org/flux2-dev` and must be procured separately:

- `checkpoints/Flux1/flux2-dev.safetensors` (61 GB BF16 full checkpoint):
  comes from [`black-forest-labs/FLUX.2-dev`](https://huggingface.co/black-forest-labs/FLUX.2-dev)
  (full Diffusers repo, ~166 GB). Only needed if you intentionally run
  the BF16 path on a Blackwell-class GPU.
- `clip/mistral_3_small_flux2.safetensors` (12 GB, FP16 variant):
  not published in `Comfy-Org/flux2-dev`. FP8 and BF16 above cover all
  production paths; FP16 is a custom convert for niche workflows.
- `loras/flux2_berthe_morisot.safetensors`: workshop-specific LoRA,
  no canonical public source.

### Video generation — COMPLETE model set (all three video configs)

The platform ships three ComfyUI video output configs. Each is driven by a
workflow chunk in `devserver/schemas/chunks/`, and every loader filename below
is taken **verbatim** from those chunks — it must match on disk exactly.

> **Strict availability filter.** The frontend shows a video config only when
> `/api/models/availability` reports it as exactly `true`. The backend
> (`model_availability_service.py`) marks a ComfyUI config unavailable if **any**
> loader filename in its workflow chunk is missing from ComfyUI's `/object_info`.
> A single missing auxiliary file silently removes the whole config from the
> media picker. See the Troubleshooting note at the end of this section.

**`ltx_video`** — chunk `output_video_ltx.json`:

| File | Target path (under `dlbackend/ComfyUI/models/`) | Size | Canonical source |
|------|--------------------------------------------------|------|------------------|
| `ltxv-13b-0.9.7-distilled-fp8.safetensors` | `checkpoints/` | 15 GB | `Lightricks/LTX-Video` |
| `t5xxl_enconly.safetensors` | `clip/` | 4.6 GB | bundled with SD3.5 — see `clip/` inventory above |

> **Note.** The LTX chunk (`output_video_ltx.json` → `CLIPLoader`) loads the
> encoder-only `t5xxl_enconly.safetensors`; SD3.5's graphs load
> `t5xxl_fp16.safetensors`. Both files hold the same 220 encoder tensors, in
> F8_E4M3 and in float16, and `download_models.sh` fetches both. SD3.5 reads
> the float16 file because the Diffusers path this platform ran until the move
> to ComfyUI loaded `text_encoder_3` in float16, so every SD3.5 picture made
> before that move was conditioned by those weights.
> The weights match byte for byte; the arithmetic still differs, because ComfyUI
> computes the text encoders in float32.

**`wan22_t2v_video_fast`** — chunk `output_video_wan22_t2v_fast.json`:

| File | Target path (under `dlbackend/ComfyUI/models/`) | Size | Canonical source |
|------|--------------------------------------------------|------|------------------|
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `clip/` | 6.2 GB | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` → `split_files/text_encoders/` |
| `wan_2.1_vae.safetensors` | `vae/` | 0.25 GB | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` → `split_files/vae/` |
| `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors` | `diffusion_models/` | 13.3 GB | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` → `split_files/diffusion_models/` |
| `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors` | `diffusion_models/` | 13.3 GB | (same) |
| `wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors` | `loras/` | 1.1 GB | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` → `split_files/loras/` |
| `wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors` | `loras/` | 1.1 GB | (same) |

**`wan22_i2v_video`** — chunk `output_video_wan22_i2v.json`:

| File | Target path (under `dlbackend/ComfyUI/models/`) | Size | Canonical source |
|------|--------------------------------------------------|------|------------------|
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `clip/` | 6.2 GB | (shared with t2v above) |
| `wan_2.1_vae.safetensors` | `vae/` | 0.25 GB | (shared with t2v above) |
| `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` | `diffusion_models/` | 13.3 GB | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` → `split_files/diffusion_models/` |
| `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | `diffusion_models/` | 13.3 GB | (same) |
| `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors` | `loras/` | 1.1 GB | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` → `split_files/loras/` |
| `wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors` | `loras/` | 1.1 GB | (same) |

> **`wan_2.1_vae.safetensors` is NOT `wan2.2_vae.safetensors`.** The Wan 2.2 14B
> t2v/i2v configs use **`wan_2.1_vae.safetensors`** — the Wan 2.1 VAE, reused
> unchanged by the Wan 2.2 14B family. `wan2.2_vae.safetensors` is the VAE for
> the *5B TI2V* model (a different, Diffusers-path model) and is **not** a
> substitute. A box that has only `wan2.2_vae.safetensors` will silently lose
> both Wan 14B video configs.
>
> **`t2v` vs `i2v` LoRA filenames differ.** The text-to-video LoRAs carry
> `v1.1` in the name; the image-to-video LoRAs carry `v1`. They are not
> interchangeable — copy both pairs.

All Comfy-Org Wan files are pulled from a single repo,
[`Comfy-Org/Wan_2.2_ComfyUI_Repackaged`](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged),
under `split_files/`. Direct-download URL pattern:
`https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/<subdir>/<file>`.

#### Troubleshooting — "video options missing from the media picker"

If a video option does not appear even though the heavy models are present, a
loader file is missing from ComfyUI:

```bash
# What files does ComfyUI actually see?
curl -s http://127.0.0.1:17804/object_info | python3 -m json.tool | less

# Force the backend to re-scan and report per-config availability
curl -s 'http://127.0.0.1:17801/api/models/availability?force_refresh=true' \
    | python3 -m json.tool
```

Cross-check the missing filename against the chunk's loader names, place the
file in the correct `dlbackend/ComfyUI/models/<subdir>/`, restart ComfyUI, and
re-query availability with `force_refresh=true`.

### Fresh-install: minimum core for ComfyUI

`download_models.sh` (in the repo root) pulls the SD3.5 / CLIP / LTX core
**and the complete Wan 2.2 14B video stack** (~110 GB total) directly into
`<repo>/dlbackend/ComfyUI/models/`. After it finishes, all three video output
configs (`ltx_video`, `wan22_t2v_video_fast`, `wan22_i2v_video`) have every
file they need. For Flux 2, run `./download_flux2.sh` (adds ~70 GB). Everything
else (Qwen Image, ACE-Step, decorative LoRAs, Wan 2.2 TI2V-5B) is downloaded
manually based on which output_configs you plan to enable.

---

## 6. Python Dependencies

See `requirements.txt`, `deployment/requirements-torch.txt`,
`deployment/requirements-git.txt`, and `deployment/requirements-spacy.txt` for the
full pinned lists. Key packages:

| Package | Version | Purpose |
|---------|---------|---------|
| `torch` | 2.11.0.dev (nightly, cu130) | GPU compute (Blackwell `sm_120`) |
| `diffusers` | 0.36.0 | HuggingFace image/video/audio generation |
| `transformers` | 4.57.0 | Text encoders |
| `llama-cpp-python` | 0.3.19 (built with `CMAKE_ARGS="-DGGML_CUDA=on"`) | In-process LLM/VLM inference |
| `spacy` | 3.8.11 | NER for DSGVO check |
| `de_core_news_lg` | 3.8.0 | German NER model |
| `xx_ent_wiki_sm` | 3.8.0 | Multilingual NER model |

```bash
# PyTorch install (cu130 nightly):
pip install -r deployment/requirements-torch.txt

# SpaCy models:
pip install -r deployment/requirements-spacy.txt
```

Only these 2 SpaCy models are needed. Adding more causes cross-language false
positives.

---

## 7. Cloud API Models (no local storage)

Accessed via API; only API keys stored locally in `devserver/*.key` (gitignored).
Configured per provider — none is required to run the platform (local
`llama-cpp-python` provides the LLM path when no cloud key is set).

### Providers and their key files

| Provider   | Key file                   | Region |
|------------|----------------------------|--------|
| Mistral    | `devserver/mistral.key`    | EU     |
| IONOS      | `devserver/ionos.key`      | EU     |
| Mammouth   | `devserver/mammouth.key`   | EU     |
| OpenAI     | `devserver/openai.key`     | US     |
| Anthropic  | `devserver/anthropic.key`  | US     |
| OpenRouter | `devserver/openrouter.key` | US     |

Which provider is active, which model each role uses and whether the provider counts as
DSGVO-conformant all come from `devserver/hardware_matrix.json` (`llm_presets`), settable
in the Settings UI. `devserver/config.py` holds no provider list and no model per
provider.

There is **no hardcoded fallback**. If a request to the configured model fails, it fails
as that request -- no substitute model answers in its place. The one fallback the
platform has is the chat chain in `my_app/routes/chat_routes.py`
(`build_model_candidate_chain`): it too reads `hardware_matrix.json`, tries the
configured provider's own `chat_fallback_models` first, and only reaches another provider
if that provider has a key present and does not weaken the active provider's DSGVO
status.

Per project rule: API keys live in `*.key` files only — **never** inside JSON. All
`*.key` filenames are already in `.gitignore`.
