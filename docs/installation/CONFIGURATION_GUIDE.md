# AI4ArtsEd DevServer - Configuration Guide

> ⚠️ **DEPRECATED** (as of 2026-05-17)
>
> This document references `/opt/ai4artsed/ai4artsed_webserver/devserver/` paths
> that no longer reflect the actual layout (`~/ai/ai4artsed_development/devserver/`),
> and references `api_keys.json` which is forbidden by project rule (API keys MUST
> live in `*.key` files per the global CLAUDE.md guard rule). Model selection
> guidance assumes Ollama, which has been replaced by in-process
> `llama-cpp-python`.
>
> **For fresh installs, see** [`UBUNTU_SERVER_FRESH_INSTALL.md`](UBUNTU_SERVER_FRESH_INSTALL.md).
> Configuration specifics now live in `devserver/user_settings.json` (model
> assignments, safety level, language).
>
> The content below is retained only for historical context.

---

Complete guide to configuring AI4ArtsEd DevServer for your environment.

## Table of Contents
1. [Overview](#overview)
2. [Main Configuration (config.py)](#main-configuration-configpy)
3. [API Keys (api_keys.json)](#api-keys-api_keysjson)
4. [Environment Variables (.env)](#environment-variables-env)
5. [UI Modes](#ui-modes)
6. [Safety Levels](#safety-levels)
7. [Model Configuration](#model-configuration)
8. [Port Configuration](#port-configuration)
9. [Path Configuration](#path-configuration)
10. [Advanced Settings](#advanced-settings)

---

## Overview

AI4ArtsEd DevServer uses three configuration sources:

1. **config.py** - Main configuration file (Python)
2. **api_keys.json** - API keys for external services (JSON, gitignored)
3. **.env** - Environment variable overrides (optional, gitignored)

**Priority:** `.env` > `api_keys.json` > `config.py` defaults

---

## Main Configuration (config.py)

Location: `/opt/ai4artsed/ai4artsed_webserver/devserver/config.py`

### Essential Settings to Update

```python
# ============================================================================
# MAIN CONFIGURATION - ADMIN: CHANGE THESE SETTINGS
# ============================================================================

# 1. USER INTERFACE MODE
# Controls interface complexity based on target age group
UI_MODE = "youth"  # Options: "kids", "youth", "expert"

# 2. SAFETY LEVEL (Content Filtering)
# Controls what content is blocked in generated images/media
DEFAULT_SAFETY_LEVEL = "youth"  # Options: "kids", "youth", "adult", "off"

# 3. SERVER SETTINGS
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 17801      # Production: 17801, Development: 17802
THREADS = 8       # Number of worker threads

# 4. LANGUAGE
DEFAULT_LANGUAGE = "de"  # "de" (German) or "en" (English)
```

### UI Mode Details

| Mode | Target Age | Features |
|------|-----------|----------|
| **kids** (8-12) | Elementary school | Simple, separated phases with minimal technical details |
| **youth** (13-17) | Secondary school | Educational flow with pipeline visualization (💡→📝→🎨→🖼️→✅) |
| **expert** | Teachers/Developers | Full debug mode with metadata, JSON outputs, timing data |

**Example:**
```python
# For elementary school students
UI_MODE = "kids"

# For secondary school students (default)
UI_MODE = "youth"

# For teachers and developers
UI_MODE = "expert"
```

---

## API Keys (api_keys.json)

Location: `/opt/ai4artsed/ai4artsed_webserver/devserver/api_keys.json`

### Template

```json
{
  "openrouter": "sk-or-v1-YOUR_KEY_HERE",
  "openai": "sk-proj-YOUR_KEY_HERE",
  "openai_org_id": "org-YOUR_ORG_HERE"
}
```

### Required API Keys

#### OpenRouter (REQUIRED)

**Purpose:** Cloud LLM access (Claude, Gemini, Mistral)

**Get Key:**
1. Visit https://openrouter.ai/keys
2. Sign up/Login
3. Create new API key
4. Copy key (starts with `sk-or-v1-`)

**Used For:**
- Fast cloud inference (Claude Haiku, Gemini Flash)
- Stage 1: Translation
- Stage 2: Prompt interception
- Stage 3: Safety checks

**Cost:** Pay-per-use, typically $0.001-0.01 per request
- Average session (5 generations): ~$0.05-0.20

**Example:**
```json
{
  "openrouter": "sk-or-v1-abc123def456ghi789..."
}
```

#### OpenAI (OPTIONAL)

**Purpose:** GPT-Image-1 or DALL-E generation (if using those output configs)

**Get Key:**
1. Visit https://platform.openai.com/api-keys
2. Sign up/Login
3. Create new API key
4. Copy key (starts with `sk-proj-`)
5. Also copy Organization ID (starts with `org-`)

**Used For:**
- Output config: `gpt5_image.json` (if enabled)
- Alternative image generation

**Cost:** Pay-per-use
- GPT-Image-1: ~$0.04 per image

**Example:**
```json
{
  "openrouter": "sk-or-v1-...",
  "openai": "sk-proj-xyz789abc123...",
  "openai_org_id": "org-def456ghi789..."
}
```

### File Permissions

```bash
# Secure API keys file (read/write only for owner)
chmod 600 /opt/ai4artsed/ai4artsed_webserver/devserver/api_keys.json
```

---

## Environment Variables (.env)

Location: `/opt/ai4artsed/ai4artsed_webserver/devserver/.env` (optional)

### Template

```bash
# LLM Provider Configuration
LLM_PROVIDER=ollama
OLLAMA_API_BASE_URL=http://localhost:11434
LMSTUDIO_API_BASE_URL=http://localhost:1234

# AI Service Paths
SWARMUI_PATH=/opt/ai4artsed/SwarmUI
COMFYUI_PATH=/opt/ai4artsed/SwarmUI/dlbackend/ComfyUI

# API Keys (alternative to api_keys.json)
OPENROUTER_API_KEY=sk-or-v1-...
OPENAI_API_KEY=sk-proj-...
OPENAI_ORG_ID=org-...

# Server Configuration
PORT=17801
HOST=0.0.0.0
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here
```

### Priority

**.env overrides config.py defaults:**
```python
# In config.py:
OLLAMA_API_BASE_URL = os.environ.get("OLLAMA_API_BASE_URL", "http://localhost:11434")
#                      ^^^^^^^^^^^^^^^^ Checks .env first  ^^^^^^^^^^^^^^^^^^^^^^ Fallback default
```

---

## UI Modes

### Kids Mode (ages 8-12)

**Purpose:** Simplified interface for elementary school students

**Features:**
- Simple, separated phases: Transform → See result → Choose medium → Generate
- Minimal technical details
- Clear visual feedback: "⚙️ KI arbeitet..."
- Focus on creative output, not process

**Use Case:** Elementary art classes, younger students

**Configuration:**
```python
UI_MODE = "kids"
DEFAULT_SAFETY_LEVEL = "kids"  # Maximum content filtering
```

---

### Youth Mode (ages 13-17) **[DEFAULT]**

**Purpose:** Educational interface for secondary school students

**Features:**
- Educational flow with pipeline visualization: 💡→📝→🎨→🖼️→✅
- Shows HOW AI processes work (transparency)
- Promotes technical understanding
- Balance between simplicity and detail

**Use Case:** Secondary school art/media classes, teenagers

**Configuration:**
```python
UI_MODE = "youth"  # Default
DEFAULT_SAFETY_LEVEL = "youth"  # Moderate content filtering
```

---

### Expert Mode (teachers/developers)

**Purpose:** Full debug mode for analysis and development

**Features:**
- Complete transparency: all metadata visible
- JSON outputs for each stage
- Timing data (ms per stage)
- Error details and debug info
- Pipeline execution logs

**Use Case:** Teachers analyzing pedagogy, developers debugging

**Configuration:**
```python
UI_MODE = "expert"
DEFAULT_SAFETY_LEVEL = "off"  # No filtering (or "adult")
```

---

## Safety Levels

### Overview

Safety levels control **content filtering** in generated images/media. This is **separate** from UI mode.

| Level | Target | Blocks |
|-------|--------|--------|
| **kids** | Ages 8-12 | Violence, horror, scary, sexual, explicit content |
| **youth** | Ages 13-17 | Explicit sexual, extreme violence, self-harm |
| **adult** | 18+ | Only illegal content (§86a StGB - Nazi symbols, etc.) |
| **off** | Development | No automatic blocking (testing only) |

### Kids (Maximum Filtering)

**Blocks:**
- Violence, death, corpses
- Horror, scary themes
- Sexual content
- Disturbing imagery

**Use For:** Elementary school (ages 8-12)

**Configuration:**
```python
DEFAULT_SAFETY_LEVEL = "kids"
```

**Negative Terms Added:**
```python
["violence", "death", "horror", "scary", "sexual", "nude", "nsfw", ...]
```

---

### Youth (Moderate Filtering)

**Blocks:**
- Explicit sexual content
- Extreme violence
- Self-harm content

**Allows:**
- Mild scary themes (educational)
- Educational anatomy
- Artistic themes

**Use For:** Secondary school (ages 13-17)

**Configuration:**
```python
DEFAULT_SAFETY_LEVEL = "youth"  # Default
```

**Negative Terms Added:**
```python
["explicit", "hardcore", "pornographic", "self-harm", "suicide", ...]
```

---

### Adult (Minimal Filtering)

**Blocks:**
- Only illegal content under German law (§86a StGB)
- Nazi symbols, terrorist organizations
- Child-related explicit content

**Allows:**
- Artistic nudity
- Mature themes
- Educational content

**Use For:** Art education (18+), professional contexts

**Configuration:**
```python
DEFAULT_SAFETY_LEVEL = "adult"
```

---

### Off (No Filtering)

**Blocks:** Nothing (no automatic filtering)

**Use For:** Development, testing only

**⚠️ WARNING:** Do NOT use for student access!

**Configuration:**
```python
DEFAULT_SAFETY_LEVEL = "off"
```

---

## Model Configuration

### Per-Stage LLM Selection

AI4ArtsEd uses different models for different pipeline stages for optimal performance/cost.

**Configuration (lines 87-102 in config.py):**

```python
# Base Models
LOCAL_DEFAULT_MODEL = "gpt-OSS:20b"  # Local Ollama model
LOCAL_VISION_MODEL = "local/llama3.2-vision:latest"
REMOTE_FAST_MODEL = "openrouter/anthropic/claude-haiku-4.5"  # Fast cloud
REMOTE_ADVANCED_MODEL = "openrouter/anthropic/claude-sonnet-4.5"  # High-quality

# Stage-Specific Models
STAGE1_TEXT_MODEL = REMOTE_FAST_MODEL  # Translation (simple)
STAGE1_VISION_MODEL = LOCAL_VISION_MODEL  # Image analysis
STAGE2_INTERCEPTION_MODEL = REMOTE_FAST_MODEL  # Prompt transformation (complex)
STAGE3_MODEL = REMOTE_FAST_MODEL  # Safety validation (simple)
```

### Model Selection Strategy

| Task | Model | Reason |
|------|-------|--------|
| **Stage 1 Translation** | Claude Haiku 4.5 | Fast, accurate, cheap |
| **Stage 1 Image Analysis** | Llama 3.2 Vision (local) | Free, privacy, sufficient quality |
| **Stage 2 Interception** | Claude Haiku 4.5 | Complex reasoning, fast |
| **Stage 3 Safety** | Claude Haiku 4.5 | Reliable content filtering |
| **Stage 4 Image Gen** | SD3.5 Large | High quality, local |
| **Stage 4 Video Gen** | LTX-Video FP8 | Fast, efficient |

### Available Model Options

**Local (Ollama):**
```python
"local/gpt-OSS:20b"  # Safety, translation
"local/llama3.2-vision:latest"  # Vision tasks
```

**Remote (OpenRouter):**
```python
"openrouter/anthropic/claude-haiku-4.5"  # Fast, cheap
"openrouter/anthropic/claude-sonnet-4.5"  # High-quality
"openrouter/google/gemini-2.5-flash-lite"  # Very fast, multimodal
"openrouter/mistralai/mistral-nemo"  # Alternative fast model
```

### Cost Optimization

**Minimize costs:**
```python
# Use local models where possible
STAGE1_TEXT_MODEL = LOCAL_DEFAULT_MODEL  # Free (Ollama)
STAGE2_INTERCEPTION_MODEL = REMOTE_FAST_MODEL  # Cheapest cloud ($0.003/1M tokens)
STAGE3_MODEL = LOCAL_DEFAULT_MODEL  # Free (Ollama)
```

**Maximize quality:**
```python
# Use best models
STAGE1_TEXT_MODEL = REMOTE_FAST_MODEL  # Claude Haiku
STAGE2_INTERCEPTION_MODEL = REMOTE_ADVANCED_MODEL  # Claude Sonnet ($0.03/1M tokens)
STAGE3_MODEL = REMOTE_FAST_MODEL  # Claude Haiku
```

---

## Port Configuration

### Default Ports

| Service | Port | Mode | Access |
|---------|------|------|--------|
| **Backend** | 17801 | Production | External (via tunnel) |
| **Backend** | 17802 | Development | Local only |
| **Frontend** | 5173 | Development | Local only |
| **SwarmUI** | 7801 | Both | Local only |
| **ComfyUI** | 7821 | Both | Local only |
| **Ollama** | 11434 | Both | Local only |

### Change Backend Port

**Option 1: Edit config.py**
```python
# Line 67
PORT = 17801  # Change to your desired port
```

**Option 2: Environment variable**
```bash
# In .env
PORT=18000
```

**Option 3: Command line**
```bash
PORT=18000 python3 server.py
```

### Change SwarmUI Port

Edit SwarmUI's settings (not AI4ArtsEd config):
```bash
nano /opt/ai4artsed/SwarmUI/Data/Settings.fds
```

Update `SWARMUI_API_PORT` in config.py to match.

---

## Path Configuration

### SwarmUI and ComfyUI Paths

**Lines 298-299 in config.py:**
```python
SWARMUI_BASE_PATH = os.environ.get("SWARMUI_PATH", "/opt/ai4artsed/SwarmUI")
COMFYUI_BASE_PATH = os.environ.get("COMFYUI_PATH", "/opt/ai4artsed/SwarmUI/dlbackend/ComfyUI")
```

### Update for Your Installation

**If installed at different location:**
```python
SWARMUI_BASE_PATH = os.environ.get("SWARMUI_PATH", "/home/user/SwarmUI")
COMFYUI_BASE_PATH = os.environ.get("SWARMUI_PATH", "/home/user/SwarmUI/dlbackend/ComfyUI")
```

**Or use .env:**
```bash
SWARMUI_PATH=/home/user/SwarmUI
COMFYUI_PATH=/home/user/SwarmUI/dlbackend/ComfyUI
```

### Exports Directory

**Auto-created at:**
```
/opt/ai4artsed/ai4artsed_webserver/exports/
```

**Change location (config.py line 124):**
```python
EXPORTS_DIR = BASE_DIR / "exports"  # Relative to repo root
# Or absolute path:
EXPORTS_DIR = Path("/mnt/storage/ai4artsed_exports")
```

---

## Advanced Settings

### Feature Flags

**config.py lines 139-144:**
```python
# Enable/disable validation pipeline (Stage 3)
ENABLE_VALIDATION_PIPELINE = True

# Skip translation (keep prompts in original language)
NO_TRANSLATE = False

```

### Request Timeouts

**config.py lines 287-291:**
```python
OLLAMA_TIMEOUT = 90  # Seconds for Ollama requests
COMFYUI_TIMEOUT = 480  # Seconds for ComfyUI workflows (8 minutes)
POLLING_TIMEOUT = 15  # Seconds between polls
```

### Logging Configuration

**config.py lines 284-285:**
```python
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
```

**Change log level:**
```python
LOG_LEVEL = "DEBUG"  # For detailed logs
```

**Or via .env:**
```bash
LOG_LEVEL=DEBUG
```

### Translation System

**Custom translation prompt (config.py lines 147-160):**
```python
TRANSLATION_PROMPT = """Translate the following text to English. CRITICAL RULES:
1. Preserve ALL brackets exactly as they appear: (), [], {{}}, and especially triple brackets ((()))
2. Do NOT remove or modify any brackets or parentheses
3. Translate with maximal semantic preservation
4. Do not translate proper names, ritual terms, or material names
5. Do not paraphrase, interpret, or summarize
6. If text is already in English, return it unchanged!

Text to translate:

{text}"""
```

### Model Path Resolution

**config.py lines 294-295:**
```python
ENABLE_MODEL_PATH_RESOLUTION = True  # Resolve SwarmUI model prefixes
MODEL_RESOLUTION_FALLBACK = True  # Fallback to original name if resolution fails
```

**Purpose:** Converts SwarmUI's `OfficialStableDiffusion/model.safetensors` format to actual paths.

---

## Configuration Examples

### Example 1: Elementary School (Kids Mode)

```python
# config.py
UI_MODE = "kids"
DEFAULT_SAFETY_LEVEL = "kids"
PORT = 17801
HOST = "0.0.0.0"
DEFAULT_LANGUAGE = "de"

# Use free local models where possible
STAGE1_TEXT_MODEL = LOCAL_DEFAULT_MODEL  # Free Ollama
STAGE3_MODEL = LOCAL_DEFAULT_MODEL  # Free Ollama
```

### Example 2: Secondary School (Youth Mode - Default)

```python
# config.py
UI_MODE = "youth"  # Educational with pipeline viz
DEFAULT_SAFETY_LEVEL = "youth"
PORT = 17801
DEFAULT_LANGUAGE = "de"

# Balance of speed and quality
STAGE1_TEXT_MODEL = REMOTE_FAST_MODEL  # Claude Haiku
STAGE2_INTERCEPTION_MODEL = REMOTE_FAST_MODEL
STAGE3_MODEL = REMOTE_FAST_MODEL
```

### Example 3: Art University (Adult Mode)

```python
# config.py
UI_MODE = "expert"  # Full debug info
DEFAULT_SAFETY_LEVEL = "adult"  # Minimal filtering
PORT = 17801
DEFAULT_LANGUAGE = "en"  # English for university

# High-quality models
STAGE2_INTERCEPTION_MODEL = REMOTE_ADVANCED_MODEL  # Claude Sonnet
```

### Example 4: Development/Testing

```python
# config.py
UI_MODE = "expert"
DEFAULT_SAFETY_LEVEL = "off"  # No filtering
PORT = 17802  # Dev port
LOG_LEVEL = "DEBUG"  # Detailed logs

# Use local models for free testing
STAGE1_TEXT_MODEL = LOCAL_DEFAULT_MODEL
STAGE2_INTERCEPTION_MODEL = LOCAL_DEFAULT_MODEL
STAGE3_MODEL = LOCAL_DEFAULT_MODEL
```

---

## Verification

### Test Configuration

```bash
cd /opt/ai4artsed/ai4artsed_webserver/devserver

# Activate venv
source ../venv/bin/activate

# Test import config
python3 -c "import config; print('Config loaded successfully')"
```

### Check Paths

```bash
# Verify SwarmUI path
python3 -c "import config; print(f'SwarmUI: {config.SWARMUI_BASE_PATH}')"

# Verify ComfyUI path
python3 -c "import config; print(f'ComfyUI: {config.COMFYUI_BASE_PATH}')"
```

### Check API Keys

```bash
# Verify API keys file exists
ls -la /opt/ai4artsed/ai4artsed_webserver/devserver/api_keys.json

# Check permissions
stat /opt/ai4artsed/ai4artsed_webserver/devserver/api_keys.json | grep Access
# Should show: -rw------- (600)
```

---

## Troubleshooting

### "API key not found"

**Check api_keys.json:**
```bash
cat /opt/ai4artsed/ai4artsed_webserver/devserver/api_keys.json
```

**Verify JSON format:**
```bash
python3 -c "import json; json.load(open('api_keys.json'))" && echo "Valid JSON" || echo "Invalid JSON"
```

### "SwarmUI connection failed"

**Check path:**
```python
import config
print(config.SWARMUI_BASE_PATH)
```

**Verify SwarmUI directory exists:**
```bash
ls -la /opt/ai4artsed/SwarmUI
```

**Check SwarmUI is running:**
```bash
curl http://localhost:7801/API/GetNewSession
```

### "Model not found"

**Check model path resolution:**
```python
import config
print(f"Model path resolution: {config.ENABLE_MODEL_PATH_RESOLUTION}")
```

**Verify models exist:**
```bash
ls -lh /opt/ai4artsed/SwarmUI/Models/Stable-Diffusion/OfficialStableDiffusion/
```

---

## Next Steps

- Return to [INSTALLATION.md](INSTALLATION.md) to complete setup
- See [SYSTEM_REQUIREMENTS.md](SYSTEM_REQUIREMENTS.md) for system dependencies
- See [MODELS_REQUIRED.md](MODELS_REQUIRED.md) for model downloads

---

## Additional Resources

- **OpenRouter Documentation:** https://openrouter.ai/docs
- **Ollama Model Library:** https://ollama.com/library
- **SwarmUI Configuration:** See SwarmUI's own documentation
