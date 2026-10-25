# AI4ArtsEd DevServer - System Requirements

Complete list of all system-level dependencies required for AI4ArtsEd DevServer.

> ⚠️ **Partially stale (as of 2026-05-21).** This document still references the
> retired SwarmUI/Ollama stack, `/opt/ai4artsed/` paths, and ports 7801/7821.
> The **hardware** numbers below remain valid, but for the current directory
> layout, install steps and ports use the canonical guide
> [`UBUNTU_SERVER_FRESH_INSTALL.md`](UBUNTU_SERVER_FRESH_INSTALL.md). The actual
> layout is a **single repo directory** with the external tools
> (`heartlib`, `dlbackend`, `llama-server-models`, `MMAudio`, `kohya_ss_new`,
> `triton_models`) plus `venv` **nested inside the repo root** (commit
> `f0519bd1`) — not `/opt/` and not siblings of the repo.

## Table of Contents
1. [Hardware Requirements](#hardware-requirements)
2. [Operating System](#operating-system)
3. [System Packages by OS](#system-packages-by-os)
4. [NVIDIA Drivers](#nvidia-drivers)
5. [Node.js Requirements](#nodejs-requirements)
6. [Network Requirements](#network-requirements)
7. [Disk Space Breakdown](#disk-space-breakdown)

---

## Hardware Requirements

### Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 8 cores | 16+ cores |
| **RAM** | 16GB | 32GB+ |
| **GPU** | NVIDIA RTX 5090 (Blackwell, `sm_120`) | NVIDIA RTX PRO 6000 Blackwell (`sm_120`) |
| **Disk** | 350GB free (SSD) | 500GB+ free (NVMe SSD) |
| **Network** | 100 Mbps | 1 Gbps |

### GPU Requirements

**NVIDIA GPU is REQUIRED** - No CPU-only mode available.

**Supported GPUs:** NVIDIA Blackwell, compute capability 12.0 (`sm_120`) — and
nothing else. `nvidia-smi --query-gpu=compute_cap --format=csv,noheader` must print
`12.0`.

- NVIDIA RTX PRO 6000 Blackwell ✅ the platform's development card
- NVIDIA RTX 5090 ✅ the smaller of the two supported cards

Earlier architectures (Ada, Ampere, and everything before them) are out of the current
deployment: `llama-server` is built for `sm_120`, and the VRAM figures the GPU service
budgets with were measured on these cards.

**Not Supported:**
- AMD GPUs (No ROCm support)
- Intel Arc GPUs
- Apple M1/M2/M3 (No Metal support)
- Integrated graphics

**CUDA Version:** 13.0 or higher required — the platform's torch stack is the
`cu130` nightly and `llama-server` is built against the CUDA 13 toolkit.

---

## Operating System

### Supported Distributions

| Distribution | Version | Status |
|--------------|---------|--------|
| **Ubuntu** | 22.04 LTS | ✅ Tested |
| **Ubuntu** | 24.04 LTS | ✅ Supported |
| **Fedora** | 38, 39, 40 | ✅ Tested (40) |
| **Arch Linux** | Rolling | ✅ Supported |
| **Debian** | 12 (Bookworm) | ✅ Should work |

### Not Supported

- Windows (WSL2 not tested)
- macOS
- CentOS/RHEL (outdated Python)
- Older Ubuntu versions (< 22.04)

---

## System Packages by OS

### Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install all dependencies
sudo apt install -y \
  git \
  curl \
  wget \
  python3.13 \
  python3-pip \
  python3-venv \
  build-essential \
  libcairo2-dev \
  libpango1.0-dev \
  libjpeg-dev \
  libgif-dev \
  libgirepository1.0-dev \
  nodejs \
  npm

# Verify Python
python3 --version
# Expected: Python 3.13.x (or 3.11+)

# Verify Node.js
node --version
# Expected: v20.x or v22.x

npm --version
# Expected: 9.x or 10.x
```

### Fedora

```bash
# Install all dependencies
sudo dnf install -y \
  git \
  curl \
  wget \
  python3.13 \
  python3-pip \
  gcc \
  make \
  cairo-devel \
  pango-devel \
  libjpeg-devel \
  giflib-devel \
  gobject-introspection-devel \
  nodejs \
  npm

# Verify installations
python3 --version
node --version
npm --version

# Fedora starts Intel's thermal daemon by default. Its adaptive mode follows the
# mainboard's firmware thermal table and clamps the CPU to 400 MHz for seconds at
# a time under load (measured 2026-09-17). Required — see INSTALLATION.md,
# System Dependencies → Fedora.
sudo systemctl mask --now thermald
```

### Arch Linux

```bash
# Install all dependencies
sudo pacman -S --needed \
  git \
  curl \
  wget \
  python \
  python-pip \
  base-devel \
  cairo \
  pango \
  libjpeg-turbo \
  giflib \
  gobject-introspection \
  nodejs \
  npm

# Verify installations
python --version
node --version
npm --version
```

---

## NVIDIA Drivers

### Ubuntu/Debian

**Recommended Method - Official NVIDIA Repository:**

```bash
# Add NVIDIA package repository
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update

# Install NVIDIA driver (recommended version)
sudo apt install -y nvidia-driver-535

# Reboot required
sudo reboot

# After reboot, verify
nvidia-smi
```

**Alternative - Ubuntu's Driver Tool:**

```bash
# List available drivers
ubuntu-drivers devices

# Install recommended driver
sudo ubuntu-drivers autoinstall

# Reboot
sudo reboot
```

**Official Guide:** https://ubuntu.com/server/docs/nvidia-drivers-installation

### Fedora

**Using RPM Fusion:**

```bash
# Enable RPM Fusion repositories
sudo dnf install -y \
  https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
  https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm

# Update package cache
sudo dnf makecache

# Install NVIDIA driver
sudo dnf install -y akmod-nvidia xorg-x11-drv-nvidia-cuda

# Wait for kernel module to build (5-10 minutes)
sudo modinfo -F version nvidia

# Reboot
sudo reboot

# After reboot, verify
nvidia-smi
```

**Official Guide:** https://rpmfusion.org/Howto/NVIDIA

### Arch Linux

```bash
# Install NVIDIA driver and CUDA
sudo pacman -S nvidia nvidia-utils cuda

# Load kernel module
sudo modprobe nvidia

# Verify
nvidia-smi
```

**Official Guide:** https://wiki.archlinux.org/title/NVIDIA

### Verify CUDA Version

```bash
nvidia-smi | grep "CUDA Version"
```

**Expected Output:**
```
| NVIDIA-SMI 595.58.03    Driver Version: 595.58.03    CUDA Version: 13.0   |
```

**CUDA 13.0 or higher required.**

---

## Node.js Requirements

### Required Version

- **Node.js:** v20.19.0+ OR v22.12.0+
- **npm:** 9.x or 10.x

### Frontend Stack

The AI4ArtsEd frontend is built with:

| Technology | Version | Purpose |
|------------|---------|---------|
| **Vue.js** | 3.5.22 | Frontend framework (Composition API) |
| **Vite** | 7.1.11 | Build tool and dev server |
| **TypeScript** | 5.9.0 | Type-safe JavaScript |
| **Pinia** | 3.0.3 | State management |
| **Vue Router** | 4.6.3 | Routing |
| **Vue i18n** | 9.14.5 | Internationalization (DE/EN) |
| **Axios** | 1.13.2 | HTTP client |

**Additional Dev Dependencies:**
- Vitest (3.2.4) - Unit testing
- Playwright (1.56.1) - E2E testing
- ESLint (9.37.0) - Code linting

### Install Node.js (if not available via package manager)

**Using NodeSource Repository (Ubuntu/Debian):**

```bash
# Download and run NodeSource setup script
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -

# Install Node.js
sudo apt install -y nodejs

# Verify
node --version
npm --version
```

**Using nvm (Node Version Manager) - Any Linux:**

```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Reload shell
source ~/.bashrc

# Install Node.js 22
nvm install 22

# Use Node.js 22
nvm use 22

# Verify
node --version
npm --version
```

---

## Network Requirements

### Ports Used

| Port | Service | Purpose | External Access |
|------|---------|---------|-----------------|
| **11434** | Ollama | Local LLM inference | No (localhost only) |
| **7801** | SwarmUI | Image/video generation API | No (localhost only) |
| **7821** | ComfyUI | Advanced workflow execution | No (localhost only) |
| **17801** | Backend | Flask application (production) | Yes (via Cloudflare Tunnel) |
| **17802** | Backend | Flask application (development) | No (dev only) |
| **5173** | Frontend | Vite dev server (development) | No (dev only) |

### Firewall Configuration

**Production (using Cloudflare Tunnel):**
```bash
# No ports need to be opened - Cloudflare Tunnel handles external access
# All services run on localhost
```

**Development (local testing):**
```bash
# Allow port 17802 (backend dev) - optional
sudo ufw allow 17802/tcp

# Allow port 5173 (frontend dev) - optional
sudo ufw allow 5173/tcp
```

### Internet Requirements

**During Installation:**
- Stable connection for ~100GB downloads
- Download speed: 100 Mbps recommended (30 Mbps minimum)

**During Operation:**
- Required for cloud LLM access (OpenRouter API)
- Required for model downloads (if using new models)
- Not required for local LLM inference (Ollama)

---

## SwarmUI Requirements

### Version Information

- **SwarmUI:** Latest from main branch (tested with commit 4c00e2a from 2025-11-22)
- **Repository:** https://github.com/mcmonkeyprojects/SwarmUI
- **Integrated ComfyUI:** Automatically installed by SwarmUI

### SwarmUI Features Used

- REST API on port 7801
- Integrated ComfyUI backend on port 7821
- Model path resolution (OfficialStableDiffusion prefix)
- Direct image generation endpoint
- ComfyUI workflow passthrough

---

## Disk Space Breakdown

### Installation Space Requirements

| Component | Size | Notes |
|-----------|------|-------|
| **System Packages** | ~500MB | Python, Node.js, build tools |
| **Ollama** | ~100MB | Application only |
| **Ollama Models** | ~29GB | gpt-OSS:20b (21GB) + llama3.2-vision (8GB) |
| **SwarmUI** | ~2GB | Application + dependencies |
| **SD3.5 Large** | ~16GB | Main image generation model |
| **CLIP Encoders** | ~16GB | clip_l + clip_g + t5xxl_fp16 (9.8GB, SD3.5) + t5xxl_enconly (4.6GB, LTX-Video) |
| **LTX-Video** | ~15GB | Video generation model (FP8) |
| **T5 for LTX** | — | the same `t5xxl_enconly`, already counted under CLIP Encoders |
| **ComfyUI Custom Nodes** | ~500MB | Custom node dependencies |
| **AI4ArtsEd Application** | ~500MB | Backend + frontend |
| **Node Modules** | ~500MB | Frontend dependencies |
| **Exports (generated)** | Variable | User-generated content |

**Total:** ~80GB (minimum, without the Wan 2.2 video stack)

**Recommended:** 120GB+ to account for:
- Python package caches (~5GB)
- npm caches (~5GB)
- Temporary files during generation (~10GB)
- User exports (~20GB+)
- Future model updates

### Partition Recommendations

> The `/opt/ai4artsed/` + SwarmUI layout below is **retired**. The current layout
> is a single git repo (e.g. `~/ai/ai4artsed_development/`) with all external
> tools nested inside it — see `UBUNTU_SERVER_FRESH_INSTALL.md` Phase 2. The disk
> totals above predate the Wan 2.2 / Flux 2 video and image models; a full
> production install today is several hundred GB (see `MODELS_REQUIRED.md`).

**Current layout (nested-tools, commit `f0519bd1`):**
```
<repo root>/                # the cloned git repo — also the AI_TOOLS_BASE root
├── venv/                   Python virtual environment
├── dlbackend/ComfyUI/      ComfyUI backend + models/ tree (largest: video/image checkpoints)
├── heartlib/ckpt/          HeartMuLa music checkpoint (~21 GB)
├── llama-server-models/    LLM/VLM GGUF files
├── MMAudio/                MMAudio repo (video-to-audio)
├── kohya_ss_new/           LoRA training workspace
└── triton_models/          Triton model repository
```
The HuggingFace Diffusers cache lives separately under `~/.cache/huggingface/hub/`.

**File System:**
- **Recommended:** ext4, xfs, btrfs
- **Avoid:** NTFS (Windows), FAT32 (file size limits)

**SSD vs HDD:**
- **SSD Required for:** Model loading, image generation (10x faster)
- **HDD Acceptable for:** Exports, logs (sequential writes)

---

## Python Version Details

### Required: Python 3.11+

**Tested Versions:**
- Python 3.13.x ✅ Recommended
- Python 3.12.x ✅ Supported
- Python 3.11.x ✅ Minimum

**Not Supported:**
- Python 3.10 or older
- Python 2.x

### Python Packages (from requirements.txt)

```
Flask==3.0.0
Flask-CORS==4.0.0
waitress==2.1.2
requests==2.31.0
aiohttp==3.13.2
python-dotenv==1.0.0
weasyprint==60.2
python-docx==1.1.0
lxml==5.1.0
```

**Special Dependencies (installed by packages):**
- cairo, pango (for weasyprint PDF generation)
- libxml2, libxslt (for lxml XML processing)

---

## Verification Commands

### Check All Requirements

```bash
# OS Version
cat /etc/os-release | grep PRETTY_NAME

# Disk Space
df -h / | tail -1

# RAM
free -h | grep Mem

# CPU Cores
nproc

# GPU
nvidia-smi

# CUDA Version
nvidia-smi | grep "CUDA Version"

# Python
python3 --version

# Node.js
node --version

# npm
npm --version

# Git
git --version

# Check ports available
sudo lsof -i :7801,7821,11434,17801 || echo "All ports available"
```

### Expected Output Summary

```
OS: Ubuntu 22.04.3 LTS
Disk: 500G available
RAM: 32Gi total
CPU: 16 cores
GPU: NVIDIA RTX 5090 (32607MiB VRAM)
CUDA: 13.0
Python: 3.13.1
Node: v22.12.0
npm: 10.9.0
Git: 2.34.1
Ports: All available
```

---

## Performance Notes

### Typical Generation Times

With RTX 5090:
- **Image (SD3.5 Large):** 10-30 seconds (768x768)
- **Video (LTX-Video):** 5-15 seconds (768x512, 6 steps)
- **Text transformation:** 2-5 seconds (cloud LLM)


### Optimization Tips

**For Faster Performance:**
- Use NVMe SSD for models
- Increase VRAM by closing unnecessary GPU applications
- Use FP8 quantized models (already configured)
- Enable model caching in SwarmUI

**For Lower VRAM Usage:**
- Use smaller models (trade-off: quality)
- Reduce batch size (already optimized)
- Enable model unloading in config.py

---

## Troubleshooting System Requirements

### Python 3.13 Not Available

**Ubuntu 22.04:**
```bash
# Add deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13 python3.13-venv python3.13-dev
```

**Fedora:**
```bash
# Python 3.13 available in Fedora 40+
sudo dnf install python3.13
```

### NVIDIA Driver Issues

**Check kernel module:**
```bash
lsmod | grep nvidia
# Should show nvidia modules loaded
```

**Rebuild DKMS modules:**
```bash
# Ubuntu/Debian
sudo dkms autoinstall

# Fedora
sudo akmods --force
```

**Check secure boot:**
```bash
mokutil --sb-state
# If enabled, you may need to disable or sign NVIDIA modules
```

### Port Conflicts

**Find what's using a port:**
```bash
sudo lsof -i :7801
# Shows process using port 7801
```

**Kill process:**
```bash
sudo kill -9 $(sudo lsof -t -i:7801)
```

---

## Next Steps

After verifying system requirements, proceed to:
- [INSTALLATION.md](INSTALLATION.md) - Complete installation guide

---

## References

- Ubuntu NVIDIA Drivers: https://ubuntu.com/server/docs/nvidia-drivers-installation
- Fedora RPM Fusion: https://rpmfusion.org/Howto/NVIDIA
- Arch NVIDIA Wiki: https://wiki.archlinux.org/title/NVIDIA
- Node.js Downloads: https://nodejs.org/
- Python Downloads: https://www.python.org/downloads/
