# AI4ArtsEd — Fresh Install on Ubuntu 26.04 LTS Server (Headless)

**Status**: Canonical installation guide (Mai 2026). Supersedes:
QUICKSTART.md, INSTALLATION.md, CONFIGURATION_GUIDE.md, PC2_INSTALLATION.md,
OFFLINE_INSTALL_MEDIUM.md, README_INSTALL.md.

**Hardware**: NVIDIA Blackwell (compute capability 12.0, `sm_120`) — RTX PRO 6000
Blackwell or RTX 5090. Earlier architectures are out of the current deployment: the
platform is built, tested and run on `sm_120` only. `nvidia-smi
--query-gpu=compute_cap --format=csv,noheader` must print `12.0` before anything below
is worth starting; `./check_prerequisites.sh` checks it too.

The two supported cards differ in VRAM by a wide margin, and that difference — not the
architecture — decides which output configs fit (Phase 7).

**Audience**: A coding agent (or operator) performing the install via SSH on a freshly
installed Ubuntu 26.04 LTS Server (no desktop).

**Two paths covered**:
- **A — Fresh install**: First-time setup. Models are downloaded from HuggingFace,
  API keys are obtained from the respective providers, configuration is built from
  scratch.
- **B — Migration**: Replacing an existing production server. Models, configuration,
  API keys, and cloudflared credentials are copied from the old server via rsync.

Both paths share Phases 1–3, 5, 6, 8 (services). They diverge in Phase 0 (migration
only), Phase 4 (models), and Phase 7 (configuration + API keys).

---

## Architecture Overview (verify before installing)

| Component       | Port      | Process                       | Started by                                  |
|-----------------|-----------|-------------------------------|---------------------------------------------|
| DevServer       | 17801     | `devserver/server.py`         | `ai4artsed-backend.service` (systemd)       |
| GPU Service     | 17803     | `gpu_service/server.py`       | `ai4artsed-gpu.service` (systemd)           |
| ComfyUI         | 17804     | `dlbackend/ComfyUI/main.py`   | Auto-started by DevServer on first request  |
| Cloudflared     | —         | `cloudflared tunnel run`      | `cloudflared.service` (systemd)             |
| Frontend (Vite) | dev only  | n/a in prod                   | In prod, built `dist/` is served by backend |

**LLM inference**: supervised `llama-server` child processes, one per model alias,
spawned and owned by the GPU Service (`LLM_ENGINE=child`, the default). The binary is
built from a pinned llama.cpp clone in Phase 3.4 — it is not installed by pip. The
older in-process `llama-cpp-python` engine stays selectable with `LLM_ENGINE=inprocess`
and reads the same GGUF store. Ollama is **dead code** — do not install.

**Single-directory layout**: one repo directory holds everything. The historical
`/opt/ai4artsed/` two-directory split (dev + prod) is abolished. Production mode is
selected by environment variable (`PORT=17801`), not by a separate directory.

**Nested-tools layout** (commit `f0519bd1`, 2026-05-18): the external AI tools are
**nested inside the repo root**, the same convention as `dlbackend/ComfyUI`. They are
**not** siblings of the repo. Seven nested tool directories plus the venv live
directly under the repo root:

```
<repo root>/                      (e.g. ~/AI4ArtsEd  — the cloned git repo)
├── venv/                         Python virtual environment (gitignored)
├── dlbackend/ComfyUI/            ComfyUI backend + its models/ tree
├── heartlib/                     HeartMuLa: git clone + ckpt/ checkpoint dir
├── llama.cpp/                    llama.cpp clone + build/bin/llama-server
├── llama-server-models/          LLM/VLM GGUF files
├── MMAudio/                      MMAudio repo (video-to-audio)
├── kohya_ss_new/                 LoRA training workspace
└── triton_models/                Triton model repository
```

These seven dirs are listed in `.gitignore` so the upstream trees / large model stores
are never accidentally committed. `MMAudio`, `kohya_ss_new` and `triton_models` are
created on demand by the steps / services that use them; `heartlib`, `dlbackend`,
`llama.cpp` and `llama-server-models` are cloned/created during install. The
`llama.cpp` rule is written `/llama.cpp` without a trailing slash, so it also covers
the case where a dev box puts a symlink there instead of a clone.

**`AI_TOOLS_BASE`** is the single environment variable that locates these tools. Both
services (`devserver/config.py`, `gpu_service/config.py`) derive `_SERVER_BASE` from
their own `__file__` and **default `_AI_TOOLS_BASE` to the repo root** — so the nested
layout works with **no env var set**. Override `AI_TOOLS_BASE` only when the tools must
live elsewhere (a separate storage partition, or a dev box that deliberately keeps them
as siblings — see Phase 2). When set, it cascades to `MMAUDIO_REPO`, `KOHYA_DIR`
and the GGUF `MODEL_DIR`.

---

## Phase 0 — Prepare the Old Server (Migration only — skip for fresh install)

Run on the **existing production server** (the one being replaced):

```bash
# 1. Inventory of API key files (do NOT commit these)
ls -la ~/ai/ai4artsed_development/devserver/*.key

# 2. Inventory of cloudflared credentials
ls /etc/cloudflared/ ~/.cloudflared/ 2>/dev/null

# 3. Snapshot user_settings.json (in case of accidental change)
cp ~/ai/ai4artsed_development/devserver/user_settings.json /tmp/user_settings.json.backup

# 4. List ComfyUI custom_nodes (for verification after migration)
ls ~/ai/ai4artsed_development/dlbackend/ComfyUI/custom_nodes/

# 5. Confirm current model directory sizes (so rsync progress is meaningful).
#    Adjust paths if the old server used the pre-f0519bd1 siblings layout
#    (~/ai/heartlib, ~/ai/llama-server-models as siblings of the repo).
du -sh ~/ai/ai4artsed_development/llama-server-models/ \
       ~/ai/ai4artsed_development/dlbackend/ComfyUI/models/ \
       ~/ai/ai4artsed_development/heartlib/ckpt/ \
       ~/.cache/huggingface/hub/
```

Decisions to make:
- **Cloudflared tunnel**: keep the existing tunnel-id (DNS unchanged → public hostname
  preserved) or create a new tunnel? Recommended: keep the tunnel-id.
- **Linux username on the new server**: matching the old server's username avoids
  rewriting absolute paths in `user_settings.json` and systemd units. Otherwise, plan
  to update absolute paths after Phase 4.

---

## Phase 1 — Ubuntu Base System

### 1.1 Install Ubuntu 26.04 LTS Server

Install the **Server edition** (no desktop). During the installer:
- Enable OpenSSH server.
- Create a regular Linux user. **For migrations**: use the same username as on the
  old server so absolute paths in `user_settings.json` and systemd units resolve
  unchanged.
- Static IP recommended (simpler cloudflared and SSH setup).

### 1.2 Update + system packages

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
    build-essential cmake ninja-build git rsync curl wget \
    libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev \
    libgirepository1.0-dev \
    ffmpeg blender \
    python3.13 python3.13-venv python3.13-dev python3-pip

# Headless Blender needs these even though no display is used (libpath resolution)
sudo apt install -y libxi6 libxrender1 libxfixes3
```

Verify:
```bash
python3.13 --version    # 3.13.x
blender -b --version    # runs in background mode
ffmpeg -version
```

Ubuntu Server does not install `thermald`. If `systemctl is-active thermald`
reports `active` (desktop installs on Intel hardware do), disable it:
`sudo systemctl mask --now thermald`. What it does to the CPU is described in
INSTALLATION.md, System Dependencies → Fedora.

### 1.3 Node.js 20+ (for frontend build)

Ubuntu default may lag. Use NodeSource:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version    # v20.x or later
```

### 1.4 NVIDIA driver + CUDA 13.0

**Driver requirement**: must support Blackwell (`sm_120`). Use NVIDIA's official
driver ≥570.x.

```bash
# Check Ubuntu 26.04 has its own NVIDIA repo:
#   https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2604/x86_64/
# If 26.04 repo is not yet published, use the ubuntu2404 repo (ABI-compatible):

# Example (verify URL at install time):
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2604/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install -y cuda-toolkit-13-0 nvidia-open
```

Verify:
```bash
nvidia-smi              # shows the installed Blackwell card
nvcc --version          # 13.0
```

Reboot if the driver was freshly installed.

### 1.5 cuDNN 9.x (matching CUDA 13)

```bash
sudo apt install -y cudnn9-cuda-13
```

### 1.6 Firewall (optional but recommended)

Bind all services to localhost; expose nothing externally except via cloudflared:
```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw enable
```

---

## Phase 2 — Repository + Layout

The external AI tools are **nested inside the repo root** (commit `f0519bd1`), not
placed as siblings of it. Clone the repo, then create the nested tool directories
**inside** the clone.

```bash
mkdir -p ~/ai
cd ~/ai

git clone https://github.com/<org>/ai4artsed_development.git
cd ai4artsed_development
git checkout main      # production branch

# Nested tool directories live INSIDE the repo root (same convention as
# dlbackend/ComfyUI). llama.cpp is cloned and built in Phase 3.4; heartlib is
# cloned in Phase 3.5; llama-server-models is populated in Phase 4.
# MMAudio / kohya_ss_new / triton_models are created on demand by the steps
# and services that use them.
mkdir -p ./llama-server-models
```

Resulting layout (repo root = `~/ai/ai4artsed_development/`):
```
~/ai/ai4artsed_development/      (this repo, main branch — also the AI_TOOLS_BASE root)
├── venv/                        (created in Phase 3.1)
├── dlbackend/ComfyUI/           (ComfyUI backend, Phase 5)
├── heartlib/                    (cloned in Phase 3.5; ckpt/ populated in Phase 4)
├── llama.cpp/                   (cloned + CUDA-built in Phase 3.4)
├── llama-server-models/         (GGUF target — populated in Phase 4)
├── MMAudio/                     (created on demand by the MMAudio install / first use)
├── kohya_ss_new/                (created on demand by LoRA-training features)
└── triton_models/               (created on demand by the Triton model store)
```

All seven tool dirs are in `.gitignore`, so cloning the repo never drags in (or
commits) the large upstream trees.

### `AI_TOOLS_BASE` — when to set it

Both services default `_AI_TOOLS_BASE` to the **repo root** (`_SERVER_BASE`,
derived from each service's own `__file__`). With the nested layout above, the
install needs **no `AI_TOOLS_BASE` env var at all** — every downstream path
(`MMAUDIO_REPO`, `KOHYA_DIR`, `LLAMA_SERVER_BIN`, GGUF `MODEL_DIR`) resolves under
the repo automatically.

Set `AI_TOOLS_BASE` explicitly **only** when the tools must live outside the repo:

- **External storage partition** — models on a separate disk:
  `export AI_TOOLS_BASE=/mnt/models` and create the six tool dirs under that path
  instead of inside the repo.
- **Dev box keeping tools as siblings** — a developer machine that intentionally
  shares one tool tree across several repo checkouts. There, point `AI_TOOLS_BASE`
  at the shared parent, e.g. add to the dev start step (the dev-only Phase-4
  / `4_start_*` start scripts):
  `export AI_TOOLS_BASE=~/ai` so `heartlib`, `llama-server-models`, etc. are
  found one level above the repo. This is the only supported reason to revive the
  old "siblings of the repo" arrangement.

If `AI_TOOLS_BASE` is set, it must be exported **consistently** for every entry
point (manual start scripts AND systemd units) — a partial override silently
splits model paths. The current `install_systemd_services.sh` deliberately writes
**no** `Environment=AI_TOOLS_BASE` line, so the units inherit the repo-root
default; keep it that way unless you are deploying the external-partition variant.

---

## Phase 3 — Python venv + Dependencies

### 3.1 Create venv

```bash
cd ~/ai/ai4artsed_development
python3.13 -m venv venv

# Always use direct python path — pyenv may interfere with venv/bin/pip
./venv/bin/python -m pip install --upgrade pip
```

### 3.2 PyTorch nightly cu130 stack (must be first)

```bash
./venv/bin/python -m pip install -r deployment/requirements-torch.txt
```

**Critical**: All torch packages must be the SAME nightly date (currently
`20260203+cu130`). Even 1 day mismatch causes CUDA crashes on Blackwell.

Verify:
```bash
./venv/bin/python -c "
import torch
assert 'cu130' in torch.__version__, f'Wrong CUDA variant: {torch.__version__}'
assert torch.cuda.is_available()
print(f'OK: {torch.__version__} on {torch.cuda.get_device_name(0)}')
"
```

### 3.3 Main requirements

```bash
./venv/bin/python -m pip install -r requirements.txt
```

Expected: ~200 packages, several minutes. Watch for build failures on `pymeshlab`,
`opencv-python` (missing system libs — should not happen given Phase 1.2).

### 3.4 llama.cpp / `llama-server` CUDA build (CRITICAL — the LLM/VLM engine)

The GPU Service runs every LLM and VLM call in a supervised `llama-server` child
process (`LLM_ENGINE=child`, the default in `gpu_service/config.py`). The binary comes
from a llama.cpp clone built with CUDA on this machine; no wheel and no package
manager provides it. Without it, the GPU Service cannot start the LLM engine, and
every local LLM/VLM call — Stage 1-3, the DSGVO check, the image safety reading —
fails.

**Upgrading an existing server**: this step is new. A machine installed before the
child engine has no `llama-server` at all, so the build has to happen there *before*
the code that defaults to `LLM_ENGINE=child` is deployed — and it has to happen on that
machine, because the binary is architecture-specific and cannot be copied from a box
that was built for another card.

**Pinned commit: `59d8402` (2026-03-27)** — recorded in
[`SOFTWARE_VERSIONS.md`](SOFTWARE_VERSIONS.md). The pin is load-bearing: the spawn line
passes `--jinja`, `--reasoning-format`, `--reasoning`, `--reasoning-budget`, `-cram`,
`-to`, `--no-webui`, `--fit`, `-np`, `--no-context-shift` and `--mmproj`, and an older
checkout rejects `--fit` and `-cram`.

Clone into the repo root (nested-tools layout, Phase 2 — `llama.cpp/` is gitignored):

```bash
git clone https://github.com/ggml-org/llama.cpp.git ~/ai/ai4artsed_development/llama.cpp
```

```bash
git -C ~/ai/ai4artsed_development/llama.cpp checkout 59d8402
```

Configure the build. `CMAKE_CUDA_ARCHITECTURES=120` is Blackwell, which is what the
platform runs. A binary built for one architecture does not run on another, so it
cannot be copied from a box that was built for a different card:

```bash
cmake -S ~/ai/ai4artsed_development/llama.cpp -B ~/ai/ai4artsed_development/llama.cpp/build -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120
```

```bash
cmake --build ~/ai/ai4artsed_development/llama.cpp/build --target llama-server -j "$(nproc)"
```

Verify — this is also what `check_prerequisites.sh` probes:

```bash
~/ai/ai4artsed_development/llama.cpp/build/bin/llama-server --version
```

Expected for the pinned commit:
```
version: 1 (59d8402)
```

**Where the binary is looked up**: `LLAMA_SERVER_BIN` defaults to
`<AI_TOOLS_BASE>/llama.cpp/build/bin/llama-server`, and `AI_TOOLS_BASE` defaults to the
repo root (Phase 2) — the path built above. Build elsewhere only together with the
external-partition variant, and then set `LLAMA_SERVER_BIN` to the binary. A dev box
that shares one llama.cpp tree across checkouts puts a symlink at the repo root
instead of a clone (this is what the Fedora dev box does):

```bash
ln -s <AI_TOOLS_BASE>/llama.cpp ~/ai/ai4artsed_development/llama.cpp
```

**Runtime paths that follow from this** (defaults are correct — listed so they are not
a surprise later): the children listen on loopback from `GPU_SERVICE_PORT + 7` upwards,
40 ports — 17810–17849 for the default 17803. The child registry `llm_children.json`
is written to `LLM_CHILD_STATE_DIR`, default `~/.cache/ai4artsed/gpu-service-<port>/`;
it records PIDs and model paths of this machine, and the service refuses the LLM engine
when that directory resolves inside the working tree.

**The `llama-cpp-python` leftover**: `requirements.txt` still pins
`llama-cpp-python==0.3.19`, installed by 3.3. It is needed **only** for the older
in-process engine (`LLM_ENGINE=inprocess`); whether the dependency is dropped is an open
decision. For `LLM_ENGINE=child` the CPU-only wheel from 3.3 is harmless and this step
can be skipped. If you intend to run or fall back to `inprocess`, force a from-source
CUDA build, which overrides that wheel:

```bash
./venv/bin/python -m pip uninstall -y llama-cpp-python
```

```bash
CMAKE_ARGS="-DGGML_CUDA=on" ./venv/bin/python -m pip install --no-binary llama-cpp-python llama-cpp-python==0.3.19
```

Verify `libggml-cuda.so` was built:
```bash
ls venv/lib/python3.13/site-packages/llama_cpp/lib/libggml-cuda.so
```

### 3.5 Git-based editable installs (heartlib, mmaudio, imagebind)

> Since stage 6 of the move to ComfyUI the media stations run on ComfyUI, so the same libraries have to be in
> ComfyUI's venv as well: `./install_comfyui_media_libs.sh` puts them there (pinned
> packages, the git commits below, Hunyuan3D's `custom_rasterizer`), and
> `install_comfyui_nodes.sh` runs it after linking the package. What follows fills
> the DevServer's venv, which the GPU service imports until stage 8.

`heartlib` must be cloned manually first so its checkpoint directory
(`<repo>/heartlib/ckpt/`, populated in Phase 4) lives at the stable path the GPU
service resolves by default (`_AI_TOOLS_BASE / heartlib / ckpt`, where
`_AI_TOOLS_BASE` is the repo root). The remaining packages (`mmaudio`, `imagebind`)
are installed via `requirements-git.txt`.

```bash
# 1. Clone heartlib INSIDE the repo root (nested-tools layout, Phase 2), then
#    install editable WITHOUT its deps (heartlib pins its own torch which would
#    clobber the cu130 nightly).
cd ~/ai/ai4artsed_development
git clone https://github.com/HeartMuLa/heartlib.git ./heartlib
./venv/bin/python -m pip install --no-deps -e ./heartlib

# 2. Remaining git installs (mmaudio, imagebind, etc.)
./venv/bin/python -m pip install -r deployment/requirements-git.txt
```

> If you deploy the external-partition or dev-box variant (Phase 2,
> `AI_TOOLS_BASE` set), clone `heartlib` into `$AI_TOOLS_BASE/heartlib` instead of
> `./heartlib`, and pass that path to `pip install -e`.

If `requirements-git.txt` still contains a `heartlib` entry, the second step is a
no-op for heartlib (already installed editable) and proceeds with the other packages.
Refer to `deployment/AGENT_INSTALL_INSTRUCTIONS.md` Phase 3 if pip rejects mixed
flag combinations.

### 3.6 custom_rasterizer (Hunyuan3D-2 CUDA extension)

```bash
git clone --filter=blob:none --no-checkout https://github.com/Tencent/Hunyuan3D-2.git /tmp/Hunyuan3D-2
git -C /tmp/Hunyuan3D-2 checkout f8db63096c8282cb27354314d896feba5ba6ff8a   # HUNYUAN3D_REF of install_comfyui_media_libs.sh
cd /tmp/Hunyuan3D-2/hy3dgen/texgen/custom_rasterizer
~/ai/ai4artsed_development/venv/bin/python -m pip install .
cd ~/ai/ai4artsed_development
rm -rf /tmp/Hunyuan3D-2
```

If compile fails with "unsupported GPU architecture": set
`TORCH_CUDA_ARCH_LIST="12.0"` (Blackwell).

### 3.7 SpaCy NER models

```bash
./venv/bin/python -m pip install -r deployment/requirements-spacy.txt
```

### 3.8 Phase 3 verification

```bash
./venv/bin/python -c "
import torch
print(f'PyTorch: {torch.__version__} / CUDA: {torch.cuda.is_available()}')
print(f'GPU: {torch.cuda.get_device_name(0)}')

import flask, diffusers, transformers, spacy, hy3dgen, custom_rasterizer
import heartlib, mmaudio, imagebind
print('Core + GPU backends: OK')

from llama_cpp import Llama
print('llama-cpp-python: OK')

spacy.load('de_core_news_lg')
spacy.load('xx_ent_wiki_sm')
print('SpaCy NER: OK')

print('=== Phase 3 complete ===')
"
```

---

## Phase 4 — Model Acquisition

Choose **Path A** (fresh install, download from HuggingFace) or **Path B** (migration,
rsync from old server). Same target directories either way.

Required directories (the nested-tools layout from Phase 2 — all under the repo
root, here `~/ai/ai4artsed_development/`):
```
~/ai/ai4artsed_development/llama-server-models/            # GGUF files (LLM/VLM)
~/ai/ai4artsed_development/dlbackend/ComfyUI/models/       # diffusion checkpoints, CLIP, VAE
~/ai/ai4artsed_development/heartlib/ckpt/                  # HeartMuLa music checkpoint
~/.cache/huggingface/hub/                                  # Diffusers auto-download cache (HOME, not repo)
```

Approximate disk usage when fully populated: ~16 GB (GGUFs) + ~450 GB (ComfyUI) +
~21 GB (HeartMuLa) + ~129 GB (HF cache) ≈ **~616 GB**.

### Path A — Fresh download (first-time install)

The canonical inventory of every checkpoint and its HuggingFace source is
[`MODELS_REQUIRED.md`](MODELS_REQUIRED.md). The summary below is the install order.

**4.A.1 ComfyUI core + video checkpoints (~110 GB)**

```bash
cd ~/ai/ai4artsed_development
./download_models.sh
```

Downloads SD3.5 Large, CLIP-G / T5-XXL, LTX-Video **and the complete Wan 2.2 14B
video stack** (both t2v + i2v UNET pairs, the 4 LightX2V LoRAs, the umt5 text
encoder, and `wan_2.1_vae.safetensors`) into
`dlbackend/ComfyUI/models/{checkpoints,clip,diffusion_models,vae,loras}/`. The script
is idempotent — re-running skips files that already exist. After it finishes, all
three video output configs (`ltx_video`, `wan22_t2v_video_fast`, `wan22_i2v_video`)
have every file they need.

> If a video option later goes missing from the media picker, a loader file is
> absent from ComfyUI — see the "video options missing" troubleshooting note in
> Section 5 of `MODELS_REQUIRED.md` (diagnose via
> `/api/models/availability?force_refresh=true`).

For Flux 2, run `./download_flux2.sh` (~70 GB). For the full ComfyUI inventory
(Qwen Image, Wan 2.2 TI2V-5B, Hunyuan3D, etc.) see Section 5 of
`MODELS_REQUIRED.md`.

**4.A.2 LLM / VLM GGUFs (~16 GB minimum)**

The exact GGUFs needed depend on what `user_settings.json` references after Phase 7.
The single source of truth for filenames is `MODEL_CONFIGS` in
`gpu_service/services/llm_backend.py`; see Section 1 of `MODELS_REQUIRED.md` for the
full alias-to-HuggingFace mapping. Minimum production set:

```bash
cd ~/ai/ai4artsed_development/llama-server-models

# Default Stage 1/2 chat model (~1 GB)
huggingface-cli download bartowski/Qwen3-1.7B-GGUF \
    Qwen3-1.7B-Q4_K_M.gguf --local-dir .

# Safety judge — Llama Guard 3 1B (~1 GB) — REQUIRED for kids/youth safety
huggingface-cli download bartowski/Llama-Guard-3-1B-GGUF \
    Llama-Guard-3-1B-Q4_K_M.gguf --local-dir .

# VLM for post-generation image safety (~1.5 GB)
mkdir -p qwen3-vl-2b && cd qwen3-vl-2b
huggingface-cli download bartowski/Qwen3-VL-2B-Instruct-GGUF \
    Qwen3-VL-2B-Instruct-Q4_K_M.gguf mmproj-F16.gguf --local-dir .
cd ..
```

**4.A.3 HeartMuLa music generation (~21 GB)** — *skip if music generation disabled*

> Since stage 6 the platform runs HeartMuLa on ComfyUI from
> `dlbackend/ComfyUI/models/heartmula/heartmula-3b/`:
> `./download_media_models.sh heartmula-3b` installs it there
> (`MODELS_REQUIRED.md` section 1a). The commands below fill the path the GPU
> service reads until stage 8.

heartlib (the Python package) was installed editable in Phase 3.5. Now download the
checkpoint into the cloned tree:

```bash
# RL-tuned variant — recommended (better tag adherence)
huggingface-cli download HeartMuLa/HeartMuLa-RL-oss-3B-20260123 \
    --local-dir ~/ai/ai4artsed_development/heartlib/ckpt/HeartMuLa-oss-3B

# Audio codec (required by HeartMuLa)
huggingface-cli download HeartMuLa/HeartCodec-oss-20260123 \
    --local-dir ~/ai/ai4artsed_development/heartlib/ckpt/HeartCodec-oss
```

To skip music generation entirely, disable music output configs in
`user_settings.json` after first boot.

**4.A.4 The media stations (~105 GB, plus ~16 GB in the HF cache)**

Stable Audio 3, ImageBind, MMAudio, Hunyuan3D 2 and the media readers run on
ComfyUI since stage 6, from `dlbackend/ComfyUI/models/<station>/`:

```bash
cd ~/ai/ai4artsed_development
./download_media_models.sh                 # every alias of the table
./download_media_models.sh media_reading   # or one station, or aliases by name
```

The table is `devserver/config/local_media_weights.json`, the inventory
`MODELS_REQUIRED.md` section 1a. The Stable Audio 3 repositories are gated
(`HF_TOKEN`). ComfyUI lists a new folder at its next validation; no restart.

**4.A.5 Auto-downloaded on first use**

Smaller Diffusers checkpoints of the GPU service and most SpaCy / transformers
utility models stream to `~/.cache/huggingface/hub/` on first use. No manual step
required — but the first request that touches each model will be slow.

### Path B — Migration via rsync (replacing an existing server)

Run **on the new server**, pulling from the old. Replace `OLD_HOST` with the LAN
hostname or IP of the old server, and `OLD_USER` with its Linux username:

```bash
OLD=OLD_USER@OLD_HOST
# Adjust if the old server used a different repo path than ~/ai/ai4artsed_development.
# The nested-tools layout means llama-server-models/ and heartlib/ live INSIDE the repo.
REPO=~/ai/ai4artsed_development
OLD_REPO='~/ai/ai4artsed_development'

# 1. LLM GGUFs (~16 GB) — nested under the repo
mkdir -p "$REPO/llama-server-models"
rsync -avz --progress \
    "$OLD":"$OLD_REPO/llama-server-models/" \
    "$REPO/llama-server-models/"

# 2. ComfyUI checkpoints (~450 GB — the longest leg)
mkdir -p "$REPO/dlbackend/ComfyUI/models"
rsync -avz --progress --exclude='__pycache__' \
    "$OLD":"$OLD_REPO/dlbackend/ComfyUI/models/" \
    "$REPO/dlbackend/ComfyUI/models/"

# 3. HeartMuLa checkpoints (~21 GB) — nested under the repo
mkdir -p "$REPO/heartlib/ckpt"
rsync -avz --progress \
    "$OLD":"$OLD_REPO/heartlib/ckpt/" \
    "$REPO/heartlib/ckpt/"

# 4. HuggingFace cache (~129 GB — content-addressable, preserve exactly).
#    The HF cache lives under $HOME, NOT inside the repo.
mkdir -p ~/.cache/huggingface/hub
rsync -avz --progress \
    "$OLD":~/.cache/huggingface/hub/ \
    ~/.cache/huggingface/hub/

# 5. ComfyUI custom_nodes
#    ai4artsed_comfyui stays behind: on the old server it is a clone with a
#    key file of its own; the installer links this repository's fork (Phase 5).
rsync -avz --progress --exclude='__pycache__' --exclude='.git' \
    --exclude='ai4artsed_comfyui' \
    "$OLD":"$OLD_REPO/dlbackend/ComfyUI/custom_nodes/" \
    "$REPO/dlbackend/ComfyUI/custom_nodes/"

# 6. user_settings.json + API key files (tiny, sensitive)
rsync -avz \
    "$OLD":"$OLD_REPO/devserver/user_settings.json" \
    "$REPO/devserver/"
rsync -avz \
    "$OLD":"$OLD_REPO/devserver/"'*.key' \
    "$REPO/devserver/"
```

> If the old server still used the pre-`f0519bd1` siblings layout
> (`~/ai/heartlib`, `~/ai/llama-server-models` as siblings of the repo), point the
> `$OLD_REPO/...` source paths in steps 1 and 3 at `~/ai/heartlib` and
> `~/ai/llama-server-models` for that pull only — the **target** paths stay nested
> under `$REPO`.

Verify sizes after migration:
```bash
du -sh "$REPO/llama-server-models" \
       "$REPO/dlbackend/ComfyUI/models" \
       "$REPO/heartlib/ckpt" \
       ~/.cache/huggingface/hub
```

---

## Phase 5 — ComfyUI Setup

ComfyUI has its **own venv** at `dlbackend/ComfyUI/venv` (separate from the main
project venv). Models were already rsync'd in Phase 4. Verify ComfyUI source exists:

```bash
ls ~/ai/ai4artsed_development/dlbackend/ComfyUI/main.py
```

If not (fresh install rather than full repo clone):
```bash
cd ~/ai/ai4artsed_development/dlbackend
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python3.13 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

Custom nodes: the foreign packages were rsync'd in Phase 4 step 5; the own
nodes are linked by the installer, which also installs missing Python
dependencies:
```bash
~/ai/ai4artsed_development/install_comfyui_nodes.sh
ls -la ~/ai/ai4artsed_development/dlbackend/ComfyUI/custom_nodes/
# expected: ai4artsed_comfyui -> .../comfyui_nodes/ai4artsed_comfyui (a link),
#           ComfyUI-LTXVideo, websocket_image_save.py, ...
```

---

## Phase 6 — Frontend Build

```bash
cd ~/ai/ai4artsed_development/public/ai4artsed-frontend
npm install                # uses package-lock.json
npm run type-check         # vue-tsc — must pass before build
npm run build              # produces dist/
ls dist/index.html         # verify
```

The backend serves `dist/` in production mode (no separate frontend server needed).

---

## Phase 7 — Configuration & API Keys

Two configuration artefacts are required:

1. **`devserver/user_settings.json`** — model assignments, default safety level, language,
   admin metadata. Editable from the in-app Settings UI once the backend runs.
2. **`devserver/*.key` files** — one file per API provider. Per the project's absolute
   rule, API keys live in `*.key` files only, **never** inside JSON. All `*.key`
   filenames are already in `.gitignore`.

### Path A — Fresh install (build configuration from scratch)

**7.A.1 Seed `user_settings.json`**

A starter `user_settings.json` is created automatically on first backend boot from the
defaults in `devserver/config.py` (`_SETTINGS_DEFAULTS`). All values can be edited
afterwards via the in-app Settings UI (admin password protected).

To pre-set values before first boot, create the file by hand. Inspect
`_SETTINGS_DEFAULTS` in `devserver/config.py` for the exact schema (safety level,
default language, model assignments per stage, etc.).

**7.A.2 Obtain API keys (each user must register independently)**

The platform supports six external LLM/cloud providers plus a local-only LLM path.
All providers are optional — the system still runs with zero cloud keys configured,
falling back to local `llama-cpp-python` for LLM inference. Add keys only for the
providers you want to use:

| Provider     | Key file                       | Region | DSGVO/GDPR | Sign-up URL                       |
|--------------|--------------------------------|--------|------------|-----------------------------------|
| Mistral      | `devserver/mistral.key`        | EU     | Compliant  | https://console.mistral.ai/       |
| IONOS        | `devserver/ionos.key`          | EU     | Compliant  | https://cloud.ionos.com/          |
| Mammouth     | `devserver/mammouth.key`       | EU     | Compliant  | https://mammouth.ai/              |
| OpenAI       | `devserver/openai.key`         | US     | Not        | https://platform.openai.com/      |
| Anthropic    | `devserver/anthropic.key`      | US     | Not        | https://console.anthropic.com/    |
| OpenRouter   | `devserver/openrouter.key`     | US     | Not        | https://eu.openrouter.ai/ (the platform reaches the EU host; the key's workspace permits no other) |

Each `*.key` file contains the raw API key on a single line (comment lines starting
with `#` are tolerated):

```bash
cd ~/ai/ai4artsed_development/devserver
echo "sk-..." > mistral.key
chmod 600 mistral.key                     # restrict read access
```

Recommended baseline for an educational deployment with DSGVO/GDPR concerns: configure
Mistral (and optionally Mammouth + IONOS) only. US-region providers can be added later
through the Settings UI if a workshop has explicit consent.

**7.A.3 Admin password for the Settings UI**

A separate file `devserver/settings_password.key` stores the **hash** of the admin
password used to unlock the Settings UI. It is **not** a third-party API key. The file
is created automatically when the admin sets a password through the UI for the first
time. No manual creation is required.

### Path B — Migration (configuration was rsync'd in Phase 4)

`user_settings.json`, all `*.key` files and `settings_password.key` were copied in
Phase 4 step 6. Verify:

```bash
ls -la ~/ai/ai4artsed_development/devserver/*.key
ls -la ~/ai/ai4artsed_development/devserver/user_settings.json
```

If absolute paths inside `user_settings.json` reference the old server's username,
update them now:

```bash
# Example: rewrite /home/old_user → /home/new_user
sed -i 's#/home/OLD_USER/#/home/NEW_USER/#g' \
    ~/ai/ai4artsed_development/devserver/user_settings.json
```

### 7.1 GPU-specific config

If `gpu_service/config.py` hardcodes VRAM expectations that exceed the currently
installed GPU (typical case: a profile inherited from the RTX PRO 6000 box, now running
on the much smaller RTX 5090), lower the limits before starting services:

```bash
grep -n "VRAM\|GB\|96" ~/ai/ai4artsed_development/gpu_service/config.py | head -20
```

Likely candidates: `VRAM_RESERVE_MB`, max-VRAM caps in output_configs. On a later card
upgrade (RTX 5090 → RTX PRO 6000, Phase 10), revert the change.

### 7.2 Output configs that won't fit on the smaller card

Image/video configs that demand more VRAM than the installed card has (e.g. Flux 2 BF16
~55 GB, Wan 2.1 BF16 ~39 GB) may OOM on an RTX 5090. Either:
- Disable those configs temporarily (set `enabled: false` in the output_config JSON), or
- Defer testing those configs until the larger card is installed (Phase 10).

SD 3.5 Large is not on that list: `diffusers_backend.py` compares the estimated peak
against the physical card before loading and switches to `enable_model_cpu_offload()`
when it does not fit (`_load_model_locked`, "exceeds GPU capacity — loading with CPU
offload"). SD 3.5 Large, and every smaller config, runs on the RTX 5090 unchanged.

---

## Phase 8 — systemd + Cloudflared

### 8.1 Install services

```bash
cd ~/ai/ai4artsed_development
sudo ./install_systemd_services.sh
```

This creates:
- `cloudflared.service` (only if `/etc/cloudflared/config.yml` exists — see 8.2)
- `ai4artsed-gpu.service` (port 17803)
- `ai4artsed-backend.service` (port 17801)

**Note**: ComfyUI is **not** installed as a systemd service. The DevServer auto-starts
ComfyUI on first request (see `COMFYUI_AUTO_START` in `devserver/config.py`).

### 8.2 Cloudflared tunnel (optional, but recommended for public hostname)

The platform runs perfectly without cloudflared — services bind to localhost and can
be reached via SSH tunneling. Cloudflared is the production path for exposing the
frontend over a fixed public hostname without opening inbound firewall ports.

For background on cloudflared itself, Cloudflare's official docs are the
canonical reference.

**Path A — Fresh tunnel (first-time install)**

```bash
# 1. Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
    -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# 2. Authenticate (opens a Cloudflare browser flow — copy the URL, open it on your
#    workstation, log in to your Cloudflare account, select the target zone)
cloudflared tunnel login

# 3. Create a named tunnel
cloudflared tunnel create ai4artsed-prod

# 4. Route DNS to the tunnel (replace example.org with your zone)
cloudflared tunnel route dns ai4artsed-prod ai4artsed.example.org

# 5. Write /etc/cloudflared/config.yml
sudo tee /etc/cloudflared/config.yml > /dev/null <<EOF
tunnel: <TUNNEL_UUID_FROM_STEP_3>
credentials-file: /root/.cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: ai4artsed.example.org
    service: http://localhost:17801
  - service: http_status:404
EOF

# 6. Move credentials so root (systemd's cloudflared user) can read them
sudo mkdir -p /root/.cloudflared
sudo mv ~/.cloudflared/<TUNNEL_UUID>.json /root/.cloudflared/
sudo chown -R root:root /etc/cloudflared /root/.cloudflared
```

**Path B — Migrate existing tunnel from an old server**

Before starting cloudflared on the new server, **stop it on the old server**
(otherwise dual-binding to the same tunnel-id will conflict):

```bash
ssh OLD "sudo systemctl stop cloudflared"
```

Copy credentials and config:
```bash
sudo mkdir -p /etc/cloudflared
sudo rsync -av OLD:/etc/cloudflared/ /etc/cloudflared/
sudo rsync -av OLD:~/.cloudflared/ ~/.cloudflared/   # may not exist on all setups
sudo chown -R root:root /etc/cloudflared
sudo cat /etc/cloudflared/config.yml   # verify tunnel UUID + credentials path
```

DNS is unchanged because the tunnel-id is unchanged — the existing public hostname
keeps working.

**Either path: re-run the systemd installer so it picks up the now-present config**:
```bash
sudo ./install_systemd_services.sh
```

### 8.3 Start services

```bash
sudo systemctl start ai4artsed-gpu
sudo systemctl start ai4artsed-backend
sudo systemctl start cloudflared

sudo systemctl status ai4artsed-gpu ai4artsed-backend cloudflared
```

---

## Phase 9 — Smoke Tests (Headless)

### 9.1 Local (CLI, via SSH)

```bash
# Backend live
curl http://localhost:17801/api/models/availability | head

# GPU service live
curl http://localhost:17803/system_stats

# ComfyUI starts on first call — trigger by making a request
# (Backend will auto-spawn it; allow 30–60 s for first start)
sleep 5
curl http://localhost:17804/system_stats
```

### 9.2 Remote (Browser on workstation)

**Option A — via the public cloudflared hostname** (preferred):
- Open the production URL in a browser
- Run a simple text pipeline (kids safety level, trivial prompt) → verify Stages 1–3
- Run an image pipeline using `sd35_large` config → verify Stage 4 + VLM safety
- Run a music pipeline (HeartMuLa) → verify GPU service heavy-load

**Option B — via SSH tunnel** (if cloudflared not yet migrated):
```bash
# On the workstation:
ssh -L 17801:localhost:17801 USER@NEW_SERVER
# Then browse to http://localhost:17801 on the workstation
```

### 9.3 Decommission the old server (Migration only — skip for fresh install)

Once Phase 9.2 succeeds on the new server:
```bash
ssh OLD "sudo systemctl disable --now ai4artsed-backend ai4artsed-gpu cloudflared"
```
Leave the old server intact for a few days in case rollback is needed. Do not delete
its model directories until you have confirmed the new server through at least one
full workshop or equivalent stress test.

---

## Phase 10 — GPU Swap (Optional — only if upgrading the GPU later)

Skip this phase entirely if the GPU installed during Phase 1 is the one you intend to
keep. Applies to installations that started on the smaller Blackwell card (RTX 5090)
and later upgrade to the larger one (RTX PRO 6000 Blackwell).

Only proceed after Phase 9 is green on the current GPU.

```bash
# 1. Stop everything cleanly
sudo systemctl stop ai4artsed-backend ai4artsed-gpu cloudflared

# 2. Power off, swap GPU, power on
sudo shutdown -h now
# (physical swap)

# 3. After boot:
nvidia-smi   # confirm "NVIDIA RTX PRO 6000 Blackwell" with 96 GB

# 4. Restore VRAM-aggressive config (reverse of 7.1)
#    Re-enable output_configs that were disabled in 7.2

# 5. Restart services
sudo systemctl start ai4artsed-gpu ai4artsed-backend cloudflared

# 6. Repeat Phase 9 smoke tests, including the heavy configs (Flux 2, Wan 2.1)
```

**No Python rebuild required**: both cards are `sm_120`, and PyTorch nightly cu130
supports it. Within Blackwell the swap is a driver-level change only, and `llama-server`
does not have to be rebuilt either — a binary built with
`-DCMAKE_CUDA_ARCHITECTURES=120` runs on both.

---

## Troubleshooting Reference

| Symptom                                  | Cause                                    | Fix                                              |
|------------------------------------------|------------------------------------------|--------------------------------------------------|
| `CUDA error: no kernel image`            | torch built for wrong arch               | Set `TORCH_CUDA_ARCH_LIST="12.0"`, rebuild       |
| `libc10.so not found` on import          | torch not imported before CUDA ext       | `import torch` first in test scripts             |
| `ModuleNotFoundError: heartlib`          | Installed with deps; torch conflicts     | Reinstall with `--no-deps`                       |
| GPU service refuses the LLM engine, "llama-server not found" | Binary not built, or `AI_TOOLS_BASE`/`LLAMA_SERVER_BIN` points elsewhere | Build per Phase 3.4; `./check_prerequisites.sh` prints the path it probed |
| `llama-server: error: invalid argument: --fit` (or `-cram`) | llama.cpp checkout older than the pin | `git -C llama.cpp checkout 59d8402`, rebuild (Phase 3.4) |
| `CUDA error: no kernel image` from a child | `llama-server` built for another architecture | Rebuild with `-DCMAKE_CUDA_ARCHITECTURES=120` (Phase 3.4) |
| llama-cpp-python falls back to CPU (`LLM_ENGINE=inprocess` only) | Prebuilt wheel without CUDA | Rebuild per Phase 3.4 with `CMAKE_ARGS`          |
| Backend can't reach GPU service          | gpu service not yet up                   | `systemctl status ai4artsed-gpu`, check journal  |
| ComfyUI fails to start                   | venv missing inside `dlbackend/ComfyUI/` | Recreate per Phase 5                             |
| Cloudflared "tunnel already running"     | Old server still running tunnel          | Stop old server's cloudflared first              |
| OOM on Flux/Wan on the RTX 5090          | VRAM too tight for big configs          | Disable those configs (Phase 7.2) until swap     |
| `import torch` works but `cuda.is_available()=False` after GPU swap | Driver/CUDA mismatch | Reinstall NVIDIA driver matching CUDA 13.0       |
| "Model path not found" for HeartMuLa / GGUFs / MMAudio | Tools cloned as siblings, not nested; or stale `AI_TOOLS_BASE` | Nest the six tool dirs inside the repo root (Phase 2), OR set `AI_TOOLS_BASE` consistently for all entry points |
| Video option missing from media picker  | Loader file absent from ComfyUI (strict availability filter) | See Section 5 troubleshooting in `MODELS_REQUIRED.md`; diagnose via `/api/models/availability?force_refresh=true` |

---

## Source-of-Truth References

| File                                                  | Authoritative for                       |
|-------------------------------------------------------|------------------------------------------|
| `deployment/AGENT_INSTALL_INSTRUCTIONS.md`            | Phase-by-phase Python install (Phases 1–6 there ≈ 3.2–3.7 here) |
| `deployment/requirements-torch.txt`                   | PyTorch nightly pins                     |
| `deployment/requirements-git.txt`                     | heartlib / mmaudio / imagebind commits   |
| `deployment/requirements-spacy.txt`                   | NER model URLs                           |
| `requirements.txt`                                    | Main Python deps                         |
| `install_systemd_services.sh`                         | systemd unit definitions                 |
| `devserver/config.py`                                 | DevServer defaults (PORT, ComfyUI auto-start) |
| `gpu_service/config.py`                               | GPU service limits, model paths          |
| `docs/ARCHITECTURE_REQUIREMENTS.md`                   | Disk layout, model directory conventions |
| `docs/installation/SYSTEM_REQUIREMENTS.md`            | Hardware spec (current)                  |
| `docs/installation/SOFTWARE_VERSIONS.md`              | Pinned versions (current)                |

---

## What This Doc Replaces

The following docs are **deprecated** and retained only for historical context. They
contain stale references to Ollama, `/opt/ai4artsed/` paths, removed execution modes
(eco/fast), or the abandoned dev/prod directory split:

- `README_INSTALL.md` (repo root)
- `docs/installation/QUICKSTART.md`
- `docs/installation/INSTALLATION.md`
- `docs/installation/CONFIGURATION_GUIDE.md`
- `docs/installation/PC2_INSTALLATION.md`
- `docs/installation/OFFLINE_INSTALL_MEDIUM.md`

Each carries a DEPRECATED header pointing here.
