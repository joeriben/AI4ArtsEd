# AI4ArtsEd DevServer - Quick Installation Guide

> ⚠️ **DEPRECATED** (as of 2026-05-17)
>
> This document references outdated architecture: Ollama as LLM provider (now
> in-process `llama-cpp-python`), `/opt/ai4artsed/` paths (now a single
> `~/ai/ai4artsed_development/` directory), and the dev/prod two-directory split
> (abolished).
>
> **For fresh installs, use** [`UBUNTU_SERVER_FRESH_INSTALL.md`](UBUNTU_SERVER_FRESH_INSTALL.md).
>
> The content below is retained only for historical context.

---

**Complete installation in 55-100 minutes** depending on whether you can transfer models from an existing installation.

---

## Prerequisites (Do This First! ⚡)

### 1. Get API Keys
**Required:** OpenRouter API key
```
https://openrouter.ai/keys
```

**Optional:** OpenAI API key (only needed for GPT-Image-1 output config)
```
https://platform.openai.com/api-keys
```

### 2. Check System Requirements
```bash
cd /opt/ai4artsed/ai4artsed_webserver
./check_prerequisites.sh
```

**Minimum Requirements:**
- 🖥️ **CPU:** 8+ cores
- 🧠 **RAM:** 16GB (32GB recommended)
- 🎮 **GPU:** NVIDIA Blackwell only — RTX 5090 (32 GB) or RTX PRO 6000
  Blackwell. Compute capability 12.0; the 4090 and everything older is out
- 💾 **Disk:** 350GB free space
- 🐍 **Python:** 3.11+
- 📦 **Node.js:** v20+
- 🔌 **CUDA:** 13.0+

---

## Installation Options

### 🚀 Option A: With Model Transfer (55-65 min) **RECOMMENDED**
Use this if you have another machine with AI4ArtsEd already installed.

### 📥 Option B: Fresh Download (80-100 min)
Use this for first-time installation or remote servers.

---

## Option A: Quick Install with Model Transfer 🚀

**Time: ~55-65 minutes**

### Step 1: Install System Dependencies (5 min)

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install -y \
  git curl wget \
  python3 python3-pip python3-venv \
  build-essential \
  libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev libgirepository1.0-dev \
  nodejs npm rsync
```

**Fedora:**
```bash
sudo dnf install -y \
  git curl wget \
  python3 python3-pip \
  gcc make \
  cairo-devel pango-devel libjpeg-devel giflib-devel gobject-introspection-devel \
  nodejs npm rsync
```

---

### Step 2: Install Ollama + Models (20 min)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama

# Download models (~29GB)
ollama pull gpt-OSS:20b
ollama pull llama3.2-vision:latest

# Verify
ollama list
```

---

### Step 3: Install SwarmUI (10 min)

```bash
# Create installation directory
cd /opt && sudo mkdir -p ai4artsed && sudo chown $USER:$USER ai4artsed
cd ai4artsed

# Clone and install SwarmUI
git clone https://github.com/mcmonkeyprojects/SwarmUI.git SwarmUI
cd SwarmUI
./install-linux.sh

# Test (then Ctrl+C after "Server started" message)
./launch-linux.sh
```

---

### Step 4: Transfer Models from Source Server (10-15 min)

**Setup SSH keys (if not already done):**
```bash
ssh-keygen -t ed25519 -C "ai4artsed-transfer"
ssh-copy-id ai4artsed@SOURCE_SERVER
ssh ai4artsed@SOURCE_SERVER "echo 'SSH OK'"
```

**Transfer models:**
```bash
cd /opt/ai4artsed/ai4artsed_webserver
./transfer_models.sh --source ai4artsed@SOURCE_SERVER
```

This transfers ~48GB over LAN (much faster than downloading from internet!).

---

### Step 5: Clone AI4ArtsEd Repository (2 min)

```bash
cd /opt/ai4artsed
git clone https://github.com/joerissenbenjamin/ai4artsed_webserver.git
cd ai4artsed_webserver
```

---

### Step 6: Run Setup Script (8 min)

```bash
./setup.sh
```

This creates Python venv, installs dependencies, and builds frontend.

---

### Step 7: Install ComfyUI Custom Nodes (3 min)

```bash
./install_comfyui_nodes.sh
```

---

### Step 8: Configure Application (5 min)

**Edit config.py:**
```bash
nano devserver/config.py
```

**Update these lines:**
```python
# Lines 298-299: Paths
SWARMUI_BASE_PATH = "/opt/ai4artsed/SwarmUI"
COMFYUI_BASE_PATH = "/opt/ai4artsed/SwarmUI/dlbackend/ComfyUI"

# Line 67: Port
PORT = 17801

# Lines 35, 61: UI mode and safety
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
  "openrouter": "sk-or-v1-YOUR_KEY_HERE",
  "openai": "sk-proj-YOUR_KEY_HERE",
  "openai_org_id": "org-YOUR_ORG_HERE"
}
```

**Secure the file:**
```bash
chmod 600 devserver/api_keys.json
```

---

### Step 9: Start Services (2 min)

**Terminal 1 - SwarmUI:**
```bash
cd /opt/ai4artsed/SwarmUI
./launch-linux.sh
```

**Terminal 2 - Backend:**
```bash
cd /opt/ai4artsed/ai4artsed_webserver/devserver
source ../venv/bin/activate
python3 server.py
```

---

### Step 10: Verify Installation (5 min)

```bash
# Check services
curl http://localhost:7801/API/GetNewSession  # SwarmUI
curl http://localhost:17801/                   # Backend

# Open browser
xdg-open http://localhost:17801
```

**✅ Done! Total: ~55-65 minutes**

---

## Option B: Fresh Installation with Downloads 📥

**Time: ~80-100 minutes**

Follow Steps 1-3 from Option A, then:

### Step 4B: Download AI Models (45-60 min)

```bash
cd /opt/ai4artsed/ai4artsed_webserver
./download_models.sh
```

This downloads ~48GB from HuggingFace.

**Continue with Steps 5-10 from Option A.**

**✅ Done! Total: ~80-100 minutes**

---

## Production Deployment (Optional)

### Set up Systemd Services

**Create SwarmUI service:**
```bash
sudo nano /etc/systemd/system/ai4artsed-swarmui.service
```

```ini
[Unit]
Description=AI4ArtsEd SwarmUI
After=network.target ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/ai4artsed/SwarmUI
Environment="PATH=/opt/ai4artsed/SwarmUI/venv/bin:/usr/bin:/bin"
ExecStart=/opt/ai4artsed/SwarmUI/launch-linux.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Create Backend service:**
```bash
sudo nano /etc/systemd/system/ai4artsed-backend.service
```

```ini
[Unit]
Description=AI4ArtsEd Backend
After=network.target ai4artsed-swarmui.service
Requires=ai4artsed-swarmui.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/ai4artsed/ai4artsed_webserver/devserver
Environment="PATH=/opt/ai4artsed/ai4artsed_webserver/venv/bin:/usr/bin:/bin"
ExecStart=/opt/ai4artsed/ai4artsed_webserver/venv/bin/python3 server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable ai4artsed-swarmui ai4artsed-backend
sudo systemctl start ai4artsed-swarmui ai4artsed-backend
```

---

## Troubleshooting

### Services won't start
```bash
# Check logs
sudo journalctl -u ai4artsed-swarmui -f
sudo journalctl -u ai4artsed-backend -f
```

### Port already in use
```bash
sudo lsof -i :7801
sudo lsof -i :17801
# Kill process if needed
sudo kill -9 $(sudo lsof -t -i:17801)
```

### Models not found
```bash
# Verify models exist
ls -lh /opt/ai4artsed/SwarmUI/Models/Stable-Diffusion/OfficialStableDiffusion/
ls -lh /opt/ai4artsed/SwarmUI/dlbackend/ComfyUI/models/clip/

# Re-download if needed
cd /opt/ai4artsed/ai4artsed_webserver
./download_models.sh
```

### GPU not detected
```bash
nvidia-smi
# Should show GPU info

# If not, install NVIDIA drivers:
# Ubuntu: sudo ubuntu-drivers autoinstall && sudo reboot
# Fedora: sudo dnf install akmod-nvidia && sudo reboot
```

---

## Next Steps

- **Full Documentation:** [INSTALLATION.md](INSTALLATION.md)
- **Configuration Guide:** [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md)
- **Model Transfer Details:** [MODEL_TRANSFER.md](MODEL_TRANSFER.md)
- **System Requirements:** [SYSTEM_REQUIREMENTS.md](SYSTEM_REQUIREMENTS.md)

---

## Timing Breakdown

### Option A (With Transfer):
| Step | Time |
|------|------|
| System Dependencies | 5 min |
| Ollama + Models | 20 min |
| SwarmUI | 10 min |
| **Model Transfer** | **10-15 min** |
| App Setup | 15 min |
| Configuration | 5 min |
| **Total** | **55-65 min** ⚡ |

### Option B (Fresh Download):
| Step | Time |
|------|------|
| System Dependencies | 5 min |
| Ollama + Models | 20 min |
| SwarmUI | 10 min |
| **Model Download** | **45-60 min** |
| App Setup | 15 min |
| Configuration | 5 min |
| **Total** | **80-100 min** |

---

## Getting Help

- **GitHub Issues:** https://github.com/joerissenbenjamin/ai4artsed_webserver/issues
- **Documentation:** [docs/installation/](.)
- **Project Website:** https://ai4artsed.org

---

**Last Updated:** 2025-01-27
