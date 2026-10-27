# AI4ArtsEd DevServer - Software Versions Reference

Quick reference for all software versions and repository URLs used in AI4ArtsEd DevServer.

## Core Application

### Backend (Python/Flask)
- **Python:** 3.11+ (tested with 3.13)
- **Flask:** 3.0.0
- **Flask-CORS:** 4.0.0
- **waitress:** 2.1.2 (WSGI server)
- **requests:** 2.31.0
- **aiohttp:** 3.13.2
- **python-dotenv:** 1.0.0
- **weasyprint:** 60.2 (PDF export)
- **python-docx:** 1.1.0 (DOCX export)
- **lxml:** 5.1.0 (XML processing)

**Repository:** https://github.com/joerissenbenjamin/ai4artsed_webserver

---

### Frontend (Vue/TypeScript)
- **Vue.js:** 3.5.22 (Composition API)
- **Vite:** 7.1.11 (Build tool)
- **TypeScript:** 5.9.0
- **Pinia:** 3.0.3 (State management)
- **Vue Router:** 4.6.3
- **Vue i18n:** 9.14.5 (Internationalization)
- **Axios:** 1.13.2 (HTTP client)
- **Vitest:** 3.2.4 (Testing)
- **Playwright:** 1.56.1 (E2E testing)

**Location:** `public/ai4artsed-frontend/`

---

## External Services

### llama.cpp / `llama-server` (Local LLM/VLM inference)

The GPU Service runs every LLM and VLM call in a supervised `llama-server` child
process (`LLM_ENGINE=child`, the default in `gpu_service/config.py`). The binary is
built from a pinned clone on the machine itself; no wheel and no package manager
provides it.

| Component | Pinned version / commit | Where it lives | How it is checked |
|-----------|-------------------------|----------------|-------------------|
| llama.cpp / `llama-server` | commit `59d8402` (2026-03-27), from `https://github.com/ggml-org/llama.cpp.git` | `<AI_TOOLS_BASE>/llama.cpp/`, binary at `build/bin/llama-server`. `AI_TOOLS_BASE` defaults to the repo root, so: `<repo>/llama.cpp/build/bin/llama-server`. Dev box (Fedora): repo-root symlink to `<AI_TOOLS_BASE>/llama.cpp` | `llama-server --version` prints `version: 1 (59d8402)`; `check_prerequisites.sh` step 7 probes the configured path |

**Build:** CUDA, `Release`, target `llama-server`, and
`-DCMAKE_CUDA_ARCHITECTURES=120` (Blackwell — RTX PRO 6000 and RTX 5090, the two cards
the platform runs). A binary built for one architecture does not run on another. Full
commands: Phase 3.4 of
[`UBUNTU_SERVER_FRESH_INSTALL.md`](UBUNTU_SERVER_FRESH_INSTALL.md).

**Why the commit is pinned:** the spawn line uses `--jinja`, `--reasoning-format`,
`--reasoning`, `--reasoning-budget`, `-cram`, `-to`, `--no-webui`, `--fit`, `-np`,
`--no-context-shift` and `--mmproj`. All are present in `59d8402`; older checkouts
reject `--fit` and `-cram`, and `--reasoning` (the on/off switch, as against
`--reasoning-budget`, which only sizes the thinking) is newer still.

**Override:** `LLAMA_SERVER_BIN` (full path to the binary) and `AI_TOOLS_BASE` (the
tools root). Set consistently for every entry point — start scripts and systemd units
alike.

### Where the other pins live

| Pinned in | Covers |
|-----------|--------|
| `requirements.txt` | Main Python dependencies, including `llama-cpp-python==0.3.19` — needed only for `LLM_ENGINE=inprocess`; whether it is dropped is an open decision |
| `deployment/requirements-torch.txt` | PyTorch nightly `cu130` stack (all packages must share one nightly date) |
| `deployment/requirements-git.txt` | heartlib / mmaudio / imagebind commits |
| `deployment/requirements-spacy.txt` | SpaCy NER model wheels |
| `public/ai4artsed-frontend/package-lock.json` | Frontend dependency tree |
| `dlbackend/ComfyUI/` (git checkout, not pinned) | ComfyUI backend + custom nodes; the installed state is whatever `git -C dlbackend/ComfyUI log -1` reports. Floor: v0.41.0, the first release that loads FLUX 3 (`output_image_flux3`). Since v0.38.0 ComfyUI's `requirements.txt` no longer lists `torchaudio`; install it next to it (see `UBUNTU_SERVER_FRESH_INSTALL.md`, Phase 5) |

---

### Ollama (Local LLM)

> **Obsolete.** Ollama is not installed any more — see the llama.cpp entry above. This
> section is retained for historical context only.

- **Version:** Latest stable
- **Installation:** `curl -fsSL https://ollama.com/install.sh | sh`
- **Port:** 11434
- **Website:** https://ollama.com

**Required Models:**
- `gpt-OSS:20b` (~21GB) - Safety checks, translation
- `llama3.2-vision:latest` (~8GB) - Image analysis

---

### SwarmUI (Image/Video Generation)
- **Repository:** https://github.com/mcmonkeyprojects/SwarmUI
- **Version:** Latest from main branch
  - Tested: commit `4c00e2a` (2025-11-22)
- **API Port:** 7801
- **ComfyUI Port:** 7821 (integrated)

**Installation:**
```bash
git clone https://github.com/mcmonkeyprojects/SwarmUI.git
cd SwarmUI
./install-linux.sh
```

---

## ComfyUI Custom Nodes

### 1. ComfyUI-LTXVideo
**Purpose:** Video generation (LTX-Video model support)

- **Repository:** https://github.com/Lightricks/ComfyUI-LTXVideo
- **Version:** Latest from main
- **Required:** Yes (for video output)

**Installation:**
```bash
cd SwarmUI/dlbackend/ComfyUI/custom_nodes
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git
cd ComfyUI-LTXVideo
pip install -r requirements.txt
```

---

### 2. ai4artsed_comfyui
**Purpose:** Custom pedagogical nodes for AI4ArtsEd workflows

- **Repository:** this repository, `comfyui_nodes/ai4artsed_comfyui/` (forked on 2026-09-12 from https://github.com/joeriben/ai4artsed_comfyui_nodes, which stays a ComfyUI-only package)
- **Version:** 0.7
- **License:** EUPL-1.2
- **Author:** Prof. Dr. Benjamin Jörissen
- **Required:** Yes (core functionality)

**Nodes Provided:**
- `ai4artsed_openrouter_key` - Secure API key management
- `ai4artsed_t5_clip_fusion` - Conditioning blending
- `ai4artsed_prompt_interception` - Prompt Interception via an LLM
- `ai4artsed_switch_promptsafety` - Safety filters
- `ai4artsed_image_analysis` - Vision LLM analysis
- Additional text/random generators

**Dependencies:**
- `ollama` (Python client)
- `requests`

**Installation:** linked from this repository by `install_comfyui_nodes.sh`
(step 1/2), never cloned. API keys come from the DevServer's key directory
(`devserver/openrouter.key`); the package keeps none of its own.

---

### comfyui-sound-lab (until 2026-10-10)
Cloned by `install_comfyui_nodes.sh` as its third step until 2026-10-10. No
chunk of the platform names a node of that package; it went with the ACE-Step
configs (S-010 of the code review of 2026-10-10).

---

## AI Models

### Stable Diffusion 3.5 Large
- **Source:** https://huggingface.co/stabilityai/stable-diffusion-3.5-large
- **Model File:** `sd3.5_large.safetensors` (15.9GB)
- **License:** Stability AI Community License

### CLIP Text Encoders
- **clip_g.safetensors** (1.3GB)
  - Source: https://huggingface.co/stabilityai/stable-diffusion-3.5-large
- **t5xxl_fp16.safetensors** (9.8GB)
  - Source: https://huggingface.co/comfyanonymous/flux_text_encoders
  - Used by: SD3.5 (the Diffusers path loaded text_encoder_3 in float16)
- **t5xxl_enconly.safetensors** (4.6GB)
  - Source: https://huggingface.co/stabilityai/stable-diffusion-3.5-large
  - Used by: LTX-Video (the same 220 encoder tensors in F8_E4M3)

### LTX-Video
- **Source:** https://huggingface.co/Lightricks/LTX-Video
- **Model File:** `ltxv-13b-0.9.7-distilled-fp8.safetensors` (14.8GB)
- **Version:** 0.9.7 (distilled, FP8 quantized)
- **License:** Apache 2.0

---

## System Requirements

### Operating System
- **Supported:**
  - Ubuntu 22.04+ (LTS recommended)
  - Fedora 38, 39, 40
  - Arch Linux (rolling)
- **Tested:** Ubuntu 22.04, Fedora 40

### Node.js
- **Required Version:** v20.19.0+ OR v22.12.0+
- **npm:** 9.x or 10.x

### NVIDIA Drivers
- **CUDA Version:** 13.0
- **Driver Version:** ≥570.x (Blackwell support)
- **GPU:** NVIDIA Blackwell, compute capability 12.0 (`sm_120`) — RTX PRO 6000
  Blackwell or RTX 5090. Earlier architectures are out of the current deployment.

---

## Build Tools

### Python Build Dependencies (Ubuntu/Debian)
```
build-essential
libcairo2-dev
libpango1.0-dev
libjpeg-dev
libgif-dev
libgirepository1.0-dev
```

### Python Build Dependencies (Fedora)
```
gcc
make
cairo-devel
pango-devel
libjpeg-devel
giflib-devel
gobject-introspection-devel
```

---

## Version Verification Commands

```bash
# Python
python3 --version
pip list | grep -E "Flask|waitress|weasyprint"

# Node.js / Frontend
node --version
npm --version
cd public/ai4artsed-frontend && npm list vue vite pinia

# llama.cpp / llama-server (from the repo root)
llama.cpp/build/bin/llama-server --version
git -C llama.cpp rev-parse --short HEAD

# Ollama (obsolete — no longer installed)
ollama --version
ollama list

# SwarmUI
cd /path/to/SwarmUI && git log -1 --format="%h %cd" --date=short

# NVIDIA
nvidia-smi
nvidia-smi | grep "CUDA Version"

# Custom Nodes
ls -la SwarmUI/dlbackend/ComfyUI/custom_nodes/
```

---

## API Services (External)

### OpenRouter
- **Website:** https://openrouter.ai
- **API Docs:** https://openrouter.ai/docs
- **Get API Key:** https://openrouter.ai/keys
- **Cost:** Pay-per-use, ~$0.001-0.01 per request

**Models Used:**
- `anthropic/claude-haiku-4.5` - Fast, cheap ($0.003/1M tokens)
- `anthropic/claude-sonnet-4.5` - High-quality ($0.03/1M tokens)
- `google/gemini-2.5-flash-lite` - Very fast, multimodal
- `mistralai/mistral-nemo` - Alternative fast model

### OpenAI (Optional)
- **Website:** https://platform.openai.com
- **Get API Key:** https://platform.openai.com/api-keys
- **Only needed for:** GPT-Image-1 or DALL-E output configs (not default)

---

## Port Usage

| Port | Service | Purpose |
|------|---------|---------|
| 17810–17849 | llama-server children | One process per loaded LLM/VLM alias (GPU service port + 7, 40 ports, loopback only) |
| 11434 | Ollama | Obsolete — no longer installed |
| 7801 | SwarmUI | Image/video generation API |
| 7821 | ComfyUI | Advanced workflows (integrated with SwarmUI) |
| 17801 | Backend | Flask application (production) |
| 17802 | Backend | Flask application (development) |
| 5173 | Frontend | Vite dev server (development only) |

---

## Update Strategy

### Application Updates
```bash
cd /path/to/ai4artsed_webserver
git pull origin main
./update.sh
```

### Ollama Model Updates
```bash
ollama pull gpt-OSS:20b
ollama pull llama3.2-vision:latest
```

### SwarmUI Updates
```bash
cd /path/to/SwarmUI
git pull origin main
./install-linux.sh  # Re-run installer if dependencies changed
```

### Custom Node Updates
```bash
cd SwarmUI/dlbackend/ComfyUI/custom_nodes/ai4artsed_comfyui
git pull origin main
pip install -r requirements.txt --upgrade
```

---

## License Information

### AI4ArtsEd Components
- **ai4artsed_webserver:** EUPL-1.2
- **ai4artsed_comfyui:** EUPL-1.2

### Third-Party Components
- **SwarmUI:** MIT License
- **ComfyUI:** GPL-3.0
- **Vue.js:** MIT License
- **Flask:** BSD-3-Clause
- **Ollama:** MIT License
- **LTX-Video:** Apache 2.0
- **Stable Diffusion 3.5:** Stability AI Community License

---

## Documentation

- **Installation Guide:** [INSTALLATION.md](INSTALLATION.md)
- **System Requirements:** [SYSTEM_REQUIREMENTS.md](SYSTEM_REQUIREMENTS.md)
- **Model Requirements:** [MODELS_REQUIRED.md](MODELS_REQUIRED.md)
- **Configuration Guide:** [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md)

---

**Last Updated:** 2025-01-27
**Documentation Version:** 1.0.1
