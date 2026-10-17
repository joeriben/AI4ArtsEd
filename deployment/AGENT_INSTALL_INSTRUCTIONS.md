# AI4ArtsEd — Supervised Installation (Agent Instructions)

You are supervising the installation of the AI4ArtsEd platform on a new machine.
Follow these steps exactly. Verify each step before proceeding to the next.

> **For a full operator-oriented Ubuntu 26.04 LTS Server walkthrough** (system
> packages, rsync model transfer, cloudflared migration, systemd, GPU swap), see
> [`docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md`](../docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md).
> This document focuses on the Python-environment build steps.

## Context

AI4ArtsEd is a pedagogical media generation platform. It requires:
- Python 3.13
- CUDA 13.0+ and a Blackwell GPU (`sm_120`) — the only supported architecture
- Multiple GPU backends (Diffusers, HeartMuLa, Hunyuan3D-2, MMAudio)
- SpaCy NER models for DSGVO/GDPR safety checks
- One CUDA extension that must be compiled from source (custom_rasterizer)
- `llama-server`, built with CUDA from a pinned llama.cpp clone (LLM/VLM inference runs
  in supervised child processes — `LLM_ENGINE=child` is the default; replaces the former
  Ollama path)
- `llama-cpp-python` with CUDA — only for the older in-process engine (`LLM_ENGINE=inprocess`)

## OS Prerequisites

### Ubuntu 26.04 LTS Server (headless — primary target)

```bash
sudo apt install -y \
    build-essential cmake ninja-build git rsync curl wget \
    libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev libgirepository1.0-dev \
    ffmpeg blender libxi6 libxrender1 libxfixes3 \
    python3.13 python3.13-venv python3.13-dev python3-pip
```

Node.js 20+ from NodeSource (`curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs`).

CUDA 13 + driver ≥570.x from NVIDIA's official repo. If the `ubuntu2604` repo is
not yet published, use the `ubuntu2404` repo (ABI-compatible).

### Fedora / RHEL

```bash
sudo dnf install -y \
    cairo-devel pango-devel libjpeg-turbo-devel giflib-devel gobject-introspection-devel \
    gcc gcc-c++ cmake ninja-build ffmpeg blender
```

## Pre-Flight Checks

Before starting, verify:
```bash
python3.13 --version      # Must be 3.13.x
nvcc --version             # CUDA compiler — needed for custom_rasterizer and llama-server
cmake --version            # Build system for llama.cpp
nvidia-smi                 # GPU visible and driver loaded
gcc --version              # C compiler for CUDA extensions
ninja --version            # Parallel build system (optional but 10x faster)
blender --version          # Headless renderer for 3D thumbnails
ffmpeg -version            # Video/audio processing
```

If any of these fail, install the missing system dependency FIRST.
Do NOT proceed without a working CUDA toolkit (nvcc).

## Phase 1: Virtual Environment + PyTorch

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

Install PyTorch nightly:
```bash
pip install -r deployment/requirements-torch.txt
```

### Verify Phase 1
```bash
python -c "
import torch
assert 'cu130' in torch.__version__ or 'cu121' in torch.__version__, f'Wrong CUDA variant: {torch.__version__}'
assert torch.cuda.is_available(), 'CUDA not available'
print(f'OK: {torch.__version__} on {torch.cuda.get_device_name(0)}')
"
```

**STOP if this fails.** Fix CUDA/driver issues before continuing.

## Phase 2: Main Dependencies

```bash
pip install -r requirements.txt
```

Expected: ~200 packages. Watch for:
- Build failures in `pymeshlab`, `opencv-python` → need system libs
- Version conflicts → report exact error, do NOT use `--force-reinstall`

### Phase 2b: llama-server CUDA build (CRITICAL — the LLM/VLM engine)

LLM and VLM inference runs in supervised `llama-server` child processes
(`LLM_ENGINE=child`, the default in `gpu_service/config.py`). The binary is not a
Python package — build it from the pinned llama.cpp clone, inside the repo root
(`llama.cpp/` is gitignored). Operator walkthrough with the per-card notes: Phase 3.4
of [`UBUNTU_SERVER_FRESH_INSTALL.md`](../docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md);
the pin itself: [`SOFTWARE_VERSIONS.md`](../docs/installation/SOFTWARE_VERSIONS.md).

```bash
git clone https://github.com/ggml-org/llama.cpp.git ./llama.cpp
git -C ./llama.cpp checkout 59d8402
```

The commit is pinned because the spawn line uses `--jinja`, `--reasoning-format`,
`-cram`, `-to`, `--no-webui`, `--fit`, `-np`, `--no-context-shift` and `--mmproj`;
older checkouts reject `--fit` and `-cram`.

`CMAKE_CUDA_ARCHITECTURES=120` — one build, for Blackwell (`sm_120`: RTX 5090, RTX PRO
6000 Blackwell), the only architecture this platform supports. A binary built for another
architecture starts and then fails on the first token with `CUDA error: no kernel image`,
so the number is not a tuning knob:

```bash
cmake -S ./llama.cpp -B ./llama.cpp/build -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120
cmake --build ./llama.cpp/build --target llama-server -j "$(nproc)"
```

Because every supported box is Blackwell, this binary can be copied between them.

Verify — this is the probe `check_prerequisites.sh` runs as step 7:
```bash
./llama.cpp/build/bin/llama-server --version
```

Expected: `version: 1 (59d8402)`.

**STOP if this fails.** Without the binary the GPU service cannot start the LLM engine,
and every local LLM/VLM call fails.

`LLAMA_SERVER_BIN` overrides the path; it defaults to
`<AI_TOOLS_BASE>/llama.cpp/build/bin/llama-server`, with `AI_TOOLS_BASE` defaulting to
the repo root. Set either one consistently for every entry point — start scripts and
systemd units alike.

### Phase 2c: llama-cpp-python CUDA rebuild (only for `LLM_ENGINE=inprocess`)

`requirements.txt` pins `llama-cpp-python==0.3.19`, and pip installs the prebuilt
**CPU-only** wheel. That wheel is only used by the older in-process engine
(`LLM_ENGINE=inprocess`); under the default `child` engine it is unused and this phase
can be skipped. Whether the dependency is dropped altogether is an open decision. To
run or fall back to `inprocess`, rebuild from source:

```bash
pip uninstall -y llama-cpp-python
CMAKE_ARGS="-DGGML_CUDA=on" pip install --no-binary llama-cpp-python llama-cpp-python==0.3.19
```

Verify the CUDA shared object was built:
```bash
python -c "
import sys, os, llama_cpp
lib = os.path.join(os.path.dirname(llama_cpp.__file__), 'lib', 'libggml-cuda.so')
assert os.path.exists(lib), f'CUDA build missing: {lib}'
print('llama-cpp-python CUDA: OK')
"
```

### Verify Phase 2
```bash
python -c "
import flask, diffusers, transformers, spacy, hy3dgen
from llama_cpp import Llama
print('Phase 2: OK')
"
```

## Phase 3: Git-Based Packages

```bash
pip install -r deployment/requirements-git.txt
```

**Important**: `heartlib` uses `--no-deps`. If pip complains about `--no-deps`
in a requirements file, install it manually:
```bash
pip install --no-deps -e "git+https://github.com/HeartMuLa/heartlib.git@ef0c33b8143680f70c78ec148fbceeec53d6151e#egg=heartlib"
pip install -e "git+https://github.com/hkchengrex/MMAudio@8e060ccf1f4171ca58ffed549975ea92d7b80165#egg=mmaudio"
pip install -e "git+https://github.com/facebookresearch/ImageBind@53680b02d7e37b19b124fa37bae4b6c98c38f5be#egg=imagebind"
pip install "git+https://github.com/facebookresearch/pytorchvideo.git@6cdc929315aab1b5674b6dcf73b16ec99147735f"
```

### Verify Phase 3
```bash
python -c "
import heartlib, mmaudio, imagebind, pytorchvideo
print('Phase 3: OK')
"
```

## Phase 4: custom_rasterizer (CUDA Compilation)

This is the most error-prone step. The custom_rasterizer is a CUDA extension
from the Hunyuan3D-2 repository that must be compiled locally.

```bash
git clone --depth 1 https://github.com/Tencent/Hunyuan3D-2.git /tmp/Hunyuan3D-2
cd /tmp/Hunyuan3D-2/hy3dgen/texgen/custom_rasterizer
pip install .
```

### If compilation fails:

1. **"nvcc not found"**: Set `CUDA_HOME=/usr/local/cuda` (or wherever CUDA is installed)
2. **"unsupported GPU architecture"**: Set `TORCH_CUDA_ARCH_LIST="12.0"` (for Blackwell)
   or `TORCH_CUDA_ARCH_LIST="8.9"` (for Ada Lovelace)
3. **"gcc version not supported"**: CUDA has gcc version limits. Check NVIDIA docs for compatible gcc.
4. **Falls back to CPU-only build**: Ensure `torch.cuda.is_available()` returns True in the venv

### Verify Phase 4
```bash
python -c "
import torch  # must import torch first (loads CUDA libs)
import custom_rasterizer
print('Phase 4: OK')
"
```

Note: `import custom_rasterizer` without `import torch` first will fail with
`libc10.so: cannot open shared object file` — this is expected, not an error.

## Phase 5: SpaCy Models

```bash
pip install -r deployment/requirements-spacy.txt
```

### Verify Phase 5
```bash
python -c "
import spacy
nlp_de = spacy.load('de_core_news_lg')
nlp_xx = spacy.load('xx_ent_wiki_sm')
# Quick NER test
doc = nlp_de('Angela Merkel war in Berlin.')
names = [ent.text for ent in doc.ents if ent.label_ == 'PER']
assert 'Angela Merkel' in names, f'NER failed, got: {names}'
print('Phase 5: OK')
"
```

## Phase 6: Full Verification

Run the comprehensive check:
```bash
python -c "
import sys
print(f'Python: {sys.version}')

import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()} ({torch.cuda.get_device_name(0)})')
print(f'VRAM: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB')

# Core
import flask, diffusers, transformers, accelerate, safetensors
print('Core stack: OK')

# GPU backends
import hy3dgen, custom_rasterizer
print('Hunyuan3D-2: OK')

import heartlib
print('HeartMuLa: OK')

import mmaudio
print('MMAudio: OK')

import imagebind
print('ImageBind: OK')

# LLM (in-process engine, LLM_ENGINE=inprocess — the child engine needs no import)
from llama_cpp import Llama
print('llama-cpp-python: OK')

# Safety
import spacy
spacy.load('de_core_news_lg')
spacy.load('xx_ent_wiki_sm')
print('SpaCy NER: OK')

# Export
import weasyprint
print('WeasyPrint (PDF): OK')

print()
print('=== ALL CHECKS PASSED ===')
"
```

The default LLM/VLM engine is a binary, not an import — check it separately:
```bash
./llama.cpp/build/bin/llama-server --version
```

Or run the whole prerequisite sweep, which probes the configured path (step 7):
```bash
./check_prerequisites.sh
```

## Common Issues Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CUDA error: no kernel image` | Built for another architecture | torch: set `TORCH_CUDA_ARCH_LIST`. `llama-server`: rebuild with `-DCMAKE_CUDA_ARCHITECTURES=120` (Blackwell, the only supported one) |
| `libc10.so not found` | torch not imported before CUDA ext | Always `import torch` first |
| `ModuleNotFoundError: heartlib` | Installed with deps, torch conflict | Reinstall with `--no-deps` |
| `spacy.load() fails` | Models not installed | Run `pip install -r deployment/requirements-spacy.txt` |
| `pymeshlab` build fail | Missing system OpenGL/Mesa libs | Install `mesa-libGL-devel` (Fedora) or `libgl1-mesa-dev` (Ubuntu) |
| `weasyprint` fails | Missing cairo/pango | Install system cairo + pango dev packages |
| Mixed torch nightly dates | CUDA crashes at runtime | Uninstall all torch pkgs, reinstall from `requirements-torch.txt` |
| `llama-server` not found; GPU service refuses the LLM engine | Binary not built, or `LLAMA_SERVER_BIN`/`AI_TOOLS_BASE` points elsewhere | Build per Phase 2b; `./check_prerequisites.sh` step 7 prints the path it probed |
| `llama-server: error: invalid argument: --fit` (or `-cram`) | llama.cpp checkout older than the pin | `git -C llama.cpp checkout 59d8402`, rebuild per Phase 2b |
| llama-cpp-python falls back to CPU | Prebuilt wheel without CUDA | Only matters for `LLM_ENGINE=inprocess` — rebuild per Phase 2c with `CMAKE_ARGS="-DGGML_CUDA=on" --no-binary` |
| `LLAMA_SERVER_URL` / port 11434 referenced | Vestigial Ollama config | Ignore — Ollama is dead code. The real llama-servers are this service's own children on 17810–17849 |
