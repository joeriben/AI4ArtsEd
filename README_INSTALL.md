# AI4ArtsEd DevServer - Installation

> ⚠️ **DEPRECATED** (as of 2026-05-17)
>
> This document references outdated architecture: Ollama as LLM provider (replaced
> by in-process `llama-cpp-python`), `/opt/ai4artsed/` paths (replaced by a single
> `~/ai/ai4artsed_development/` directory), and the dev/prod two-directory split
> (abolished — production mode is selected via `PORT` env var).
>
> **For fresh installs, use** [`docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md`](docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md).
>
> The content below is retained only for historical context.

---

Quick installation guide for deploying AI4ArtsEd DevServer on production Linux servers.

---

## 🚀 Quick Start for Impatient Users

**Want the fastest installation?** → [docs/installation/QUICKSTART.md](docs/installation/QUICKSTART.md)

**55-65 minutes** with model transfer or **80-100 minutes** fresh download.

---

## Prerequisites (Do This First!)

### 1. Get API Keys ⚡

**Required:**
- **OpenRouter API Key:** https://openrouter.ai/keys

**Optional:**
- **OpenAI API Key:** https://platform.openai.com/api-keys (only for GPT-Image-1)

### 2. Check System Requirements

```bash
# Run prerequisites checker
cd /opt/ai4artsed/ai4artsed_webserver
./check_prerequisites.sh
```

This checks: GPU, CUDA, disk space, RAM, Python, Node.js, ports, and internet.

---

## Installation Options

### Option A: With Model Transfer (Fastest 🚀)
If you have another machine with AI4ArtsEd already installed:
```bash
./transfer_models.sh --source ai4artsed@SOURCE_SERVER
```
**Time:** 10-15 minutes (LAN transfer) instead of 45-60 minutes (download)

### Option B: Fresh Download
For first-time installations:
```bash
./download_models.sh
```
**Time:** 45-60 minutes (downloads from HuggingFace)

---

## Quick Start

```bash
# 1. Check system requirements
./check_prerequisites.sh

# 2. Install system dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install -y \
  git curl wget rsync \
  python3 python3-pip python3-venv \
  build-essential \
  libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev libgirepository1.0-dev \
  nodejs npm

# Note: python3 installs Python 3.11+ (sufficient, 3.13 not required)

# 3. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gpt-OSS:20b
ollama pull llama3.2-vision:latest

# 4. Install SwarmUI (in separate directory)
cd /opt && sudo mkdir -p ai4artsed && sudo chown $USER:$USER ai4artsed
cd ai4artsed
git clone https://github.com/mcmonkeyprojects/SwarmUI.git SwarmUI
cd SwarmUI && ./install-linux.sh

# 5. Clone AI4ArtsEd repository
cd /opt/ai4artsed
git clone https://github.com/joerissenbenjamin/ai4artsed_webserver.git
cd ai4artsed_webserver

# 6. Run setup script
./setup.sh

# 7. Install ComfyUI custom nodes (automated)
./install_comfyui_nodes.sh
# Or with custom path: SWARMUI_PATH=/path/to/SwarmUI ./install_comfyui_nodes.sh

# 8. Download or Transfer Models (~48GB)
# Option A: Transfer from existing installation (FAST!)
./transfer_models.sh --source ai4artsed@SOURCE_SERVER

# Option B: Download from HuggingFace
./download_models.sh

# 9. Configure
nano devserver/config.py         # Update paths
nano devserver/api_keys.json     # Add API keys (from prerequisites!)

# 10. Start services
cd devserver
source ../venv/bin/activate
python3 server.py
```

---

## 📚 Complete Documentation

**⚡ Quick Start (55-100 min):** [docs/installation/QUICKSTART.md](docs/installation/QUICKSTART.md)
**📖 Full Installation Guide:** [docs/installation/INSTALLATION.md](docs/installation/INSTALLATION.md)
**🔄 Model Transfer Guide:** [docs/installation/MODEL_TRANSFER.md](docs/installation/MODEL_TRANSFER.md)

### Installation Documentation

All installation documentation is located in [`docs/installation/`](docs/installation/):

| Document | Description |
|----------|-------------|
| **[README.md](docs/installation/README.md)** | Documentation overview and navigation |
| **[SYSTEM_REQUIREMENTS.md](docs/installation/SYSTEM_REQUIREMENTS.md)** | Complete system requirements and dependencies |
| **[MODELS_REQUIRED.md](docs/installation/MODELS_REQUIRED.md)** | AI models list with download links (~77GB) |
| **[INSTALLATION.md](docs/installation/INSTALLATION.md)** | Step-by-step installation guide |
| **[CONFIGURATION_GUIDE.md](docs/installation/CONFIGURATION_GUIDE.md)** | Complete configuration reference |

---

## System Requirements

### Minimum Hardware
- **OS:** Ubuntu 22.04+, Fedora 38+, or Arch Linux
- **CPU:** 8+ cores
- **RAM:** 16GB minimum (32GB recommended)
- **GPU:** NVIDIA Blackwell only (`sm_120`): RTX 5090 (32 GB) or RTX PRO 6000
  Blackwell. The RTX 4090 was deprecated on 2026-08-11
- **Disk:** 350GB free space (SSD recommended)
- **CUDA:** Version 13.0+

### What Gets Installed
- **Ollama + Models:** ~29GB (local LLM inference)
- **SwarmUI + ComfyUI:** ~2GB (image/video generation backend)
- **AI Models:** ~48GB (SD3.5, LTX-Video, CLIP encoders)
- **AI4ArtsEd App:** ~1GB (backend + frontend)
- **Total:** ~80GB

### Installation Time
- **Fast (1 Gbps):** ~20 minutes
- **Typical (100 Mbps):** ~90 minutes
- **Slow (10 Mbps):** ~8-12 hours

*Most time spent downloading models.*

---

## Helper Scripts

Five scripts are provided to simplify installation and updates:

### check_prerequisites.sh - System Requirements Checker
**Run before installation:**
```bash
./check_prerequisites.sh
```

**What it checks:**
- Disk space (350GB+ required)
- RAM (16GB+ required)
- GPU and VRAM
- CUDA version
- Python and Node.js versions
- Required ports availability
- Internet connectivity

---

### transfer_models.sh - Fast Model Transfer
**Transfer models from existing installation:**
```bash
./transfer_models.sh --source ai4artsed@SOURCE_SERVER
```

**What it does:**
- Transfers AI models over LAN (much faster than download!)
- Verifies checksums after transfer
- Creates required symlinks
- **Time:** 10-15 minutes (LAN) vs 45-60 minutes (download)

**See:** [docs/installation/MODEL_TRANSFER.md](docs/installation/MODEL_TRANSFER.md)

---

### download_models.sh - Model Downloader
**Download models from HuggingFace:**
```bash
./download_models.sh
```

**What it does:**
- Downloads all required AI models (~48GB)
- Idempotent (skip existing files, safe to re-run)
- Creates required symlinks
- **Time:** 45-60 minutes on 100Mbps

---

### setup.sh - Initial Setup
**Run once after cloning repository:**
```bash
./setup.sh
```

**What it does:**
- Creates Python virtual environment
- Installs Python dependencies
- Creates exports directories
- Builds frontend production bundle

---

### update.sh - Update System
**Run to update to latest version:**
```bash
./update.sh
```

**What it does:**
- Pulls latest code from git
- Updates Python dependencies
- Rebuilds frontend
- Restarts systemd services (if configured)

---

## Installation Steps (Detailed)

### 1. Check System Requirements
```bash
# Verify prerequisites
nvidia-smi                    # Should show a Blackwell GPU + CUDA 13.0+
df -h /                       # Should show 350GB+ free
free -h                       # Should show 16GB+ RAM
python3 --version             # Should show Python 3.11+
node --version                # Should show Node.js v20+
```

**If any check fails, see:** [docs/installation/SYSTEM_REQUIREMENTS.md](docs/installation/SYSTEM_REQUIREMENTS.md)

---

### 2. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y \
  git curl wget \
  python3.13 python3-pip python3-venv \
  build-essential \
  libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev libgirepository1.0-dev \
  nodejs npm
```

**Fedora:**
```bash
sudo dnf install -y \
  git curl wget \
  python3.13 python3-pip \
  gcc make \
  cairo-devel pango-devel libjpeg-devel giflib-devel gobject-introspection-devel \
  nodejs npm
```

**Arch Linux:**
```bash
sudo pacman -S --needed \
  git curl wget \
  python python-pip \
  base-devel \
  cairo pango libjpeg-turbo giflib gobject-introspection \
  nodejs npm
```

**NVIDIA Drivers:** See [docs/installation/SYSTEM_REQUIREMENTS.md#nvidia-drivers](docs/installation/SYSTEM_REQUIREMENTS.md#nvidia-drivers)

---

### 3. Install Ollama + Models

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama

# Download models (~29GB, takes 15-25 minutes)
ollama pull gpt-OSS:20b              # ~21GB - Safety checks, translation
ollama pull llama3.2-vision:latest   # ~8GB - Image analysis

# Verify
ollama list
```

---

### 4. Install SwarmUI

```bash
# Create installation directory
cd /opt && sudo mkdir -p ai4artsed && sudo chown $USER:$USER ai4artsed
cd ai4artsed

# Clone and install SwarmUI
git clone https://github.com/mcmonkeyprojects/SwarmUI.git SwarmUI
cd SwarmUI
./install-linux.sh  # Takes 5-10 minutes

# Test start (then exit with Ctrl+C)
./launch-linux.sh
```

---

### 5. Install ComfyUI Custom Nodes

```bash
cd /opt/ai4artsed/SwarmUI/dlbackend/ComfyUI/custom_nodes
source ../../venv/bin/activate

# LTX-Video (video generation)
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git
cd ComfyUI-LTXVideo && pip install -r requirements.txt && cd ..

# AI4ArtsEd's own nodes live in this repository (comfyui_nodes/): link them, do not clone.
# $REPO is this repository's checkout; the nodes read their API keys from devserver/ through it.
ln -sfnT "$REPO/comfyui_nodes/ai4artsed_comfyui" ai4artsed_comfyui

# Sound Lab (audio generation)
git clone https://github.com/MixLabPro/comfyui-sound-lab.git
cd comfyui-sound-lab && pip install -r requirements.txt || echo "Optional dependencies failed" && cd ..

deactivate
```

---

### 6. Download AI Models (~48GB)

**Download script provided in docs:**
See [docs/installation/MODELS_REQUIRED.md](docs/installation/MODELS_REQUIRED.md#download-scripts)

**Manual download:**
```bash
# SD3.5 Large (16GB)
mkdir -p /opt/ai4artsed/SwarmUI/Models/Stable-Diffusion/OfficialStableDiffusion
cd /opt/ai4artsed/SwarmUI/Models/Stable-Diffusion/OfficialStableDiffusion
wget https://huggingface.co/stabilityai/stable-diffusion-3.5-large/resolve/main/sd3.5_large.safetensors

# CLIP encoders (6GB) — t5xxl_enconly is shared by SD3.5 and the LTX-Video chunk
cd /opt/ai4artsed/SwarmUI/dlbackend/ComfyUI/models/clip
wget https://huggingface.co/stabilityai/stable-diffusion-3.5-large/resolve/main/clip_g.safetensors
wget https://huggingface.co/stabilityai/stable-diffusion-3.5-large/resolve/main/t5xxl_enconly.safetensors

# LTX-Video (15GB) — reuses the t5xxl_enconly encoder downloaded above
cd /opt/ai4artsed/SwarmUI/dlbackend/ComfyUI/models/checkpoints
wget https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltxv-13b-0.9.7-distilled-fp8.safetensors

# Create symlink
cd /opt/ai4artsed/SwarmUI/dlbackend/ComfyUI/models/checkpoints
ln -s ../../../Models/Stable-Diffusion/OfficialStableDiffusion OfficialStableDiffusion
```

**Estimated time:** 30-60 minutes on 100Mbps connection

---

### 7. Clone AI4ArtsEd Repository

```bash
cd /opt/ai4artsed
git clone https://github.com/joerissenbenjamin/ai4artsed_webserver.git
cd ai4artsed_webserver
```

---

### 8. Run Setup Script

```bash
./setup.sh
```

**This will:**
- Create Python virtual environment
- Install Python dependencies (Flask, waitress, etc.)
- Create exports directories
- Install Node.js dependencies
- Build frontend production bundle

**Takes:** 5-10 minutes

---

### 9. Configure Application

**Edit main configuration:**
```bash
nano devserver/config.py
```

**Update these lines:**
```python
# Lines 298-299: Update paths
SWARMUI_BASE_PATH = "/opt/ai4artsed/SwarmUI"
COMFYUI_BASE_PATH = "/opt/ai4artsed/SwarmUI/dlbackend/ComfyUI"

# Line 67: Production port
PORT = 17801

# Lines 35, 61: UI mode and safety level
UI_MODE = "youth"  # Options: "kids", "youth", "expert"
DEFAULT_SAFETY_LEVEL = "youth"  # Options: "kids", "youth", "adult", "off"
```

**Create API keys file:**
```bash
nano devserver/api_keys.json
```

**Content:**
```json
{
  "openrouter": "sk-or-v1-YOUR_OPENROUTER_KEY_HERE",
  "openai": "sk-proj-YOUR_OPENAI_KEY_HERE",
  "openai_org_id": "org-YOUR_ORG_HERE"
}
```

**Get API keys:**
- **OpenRouter (required):** https://openrouter.ai/keys
- **OpenAI (optional):** https://platform.openai.com/api-keys

**Secure the file:**
```bash
chmod 600 devserver/api_keys.json
```

**For complete configuration options, see:**
[docs/installation/CONFIGURATION_GUIDE.md](docs/installation/CONFIGURATION_GUIDE.md)

---

### 10. Start Services

**Option A: Manual (Development)**
```bash
# Terminal 1: SwarmUI
cd /opt/ai4artsed/SwarmUI
./launch-linux.sh

# Terminal 2: Backend
cd /opt/ai4artsed/ai4artsed_webserver/devserver
source ../venv/bin/activate
python3 server.py
```

**Option B: Systemd (Production)**

See [docs/installation/INSTALLATION.md#service-setup-optional](docs/installation/INSTALLATION.md#service-setup-optional) for systemd service configuration.

---

### 11. Verify Installation

```bash
# Check all services running
curl http://localhost:11434/api/tags                  # Ollama
curl http://localhost:7801/API/GetNewSession          # SwarmUI
curl http://localhost:17801/                          # Backend

# Access web interface
# Open browser: http://localhost:17801
```

**Expected:** AI4ArtsEd web interface loads with language selection (Deutsch/English)

---

## Troubleshooting

### Common Issues

**"Port already in use"**
```bash
# Check what's using the port
sudo lsof -i :17801

# Kill process if needed
sudo kill -9 $(sudo lsof -t -i:17801)
```

**"Model not found"**
```bash
# Verify models exist
ls -lh /opt/ai4artsed/SwarmUI/Models/Stable-Diffusion/OfficialStableDiffusion/sd3.5_large.safetensors
ls -lh /opt/ai4artsed/SwarmUI/dlbackend/ComfyUI/models/clip/

# Check symlink
ls -l /opt/ai4artsed/SwarmUI/dlbackend/ComfyUI/models/checkpoints/OfficialStableDiffusion
```

**"SwarmUI connection failed"**
```bash
# Check SwarmUI is running
curl http://localhost:7801/API/GetNewSession

# Check config.py paths
cd /opt/ai4artsed/ai4artsed_webserver/devserver
grep SWARMUI_BASE_PATH config.py
```

**For complete troubleshooting, see:**
[docs/installation/INSTALLATION.md#troubleshooting](docs/installation/INSTALLATION.md#troubleshooting)

---

## Updating

To update to the latest version:

```bash
cd /opt/ai4artsed/ai4artsed_webserver
./update.sh
```

This will:
- Pull latest code from git
- Update Python dependencies
- Rebuild frontend
- Restart systemd services (if configured)

---

## Production Deployment

For production deployment with systemd services, Cloudflare Tunnel, and advanced configuration:

**See:** [docs/installation/INSTALLATION.md](docs/installation/INSTALLATION.md)

---

## Getting Help

- **Complete Documentation:** [docs/installation/](docs/installation/)
- **GitHub Issues:** https://github.com/joerissenbenjamin/ai4artsed_webserver/issues
- **Project Website:** https://ai4artsed.org

---

## License

See [LICENSE](LICENSE) file for details.

---

## Credits

**AI4ArtsEd DevServer**
- **Author:** Prof. Dr. Benjamin Jörissen
- **Institution:** Friedrich-Alexander-Universität Erlangen-Nürnberg
- **License:** EUPL-1.2

**Third-Party Components:**
- SwarmUI (mcmonkeyprojects)
- ComfyUI (comfyanonymous)
- Ollama (ollama.ai)
- Stable Diffusion 3.5 (Stability AI)
- LTX-Video (Lightricks)
