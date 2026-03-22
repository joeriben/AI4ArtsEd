# AI4ArtsEd — Installation Guide

Generated: 2026-03-22 | Python 3.13 | CUDA 13.0 | Blackwell GPU

## Prerequisites

### System Packages (Fedora/RHEL)
```bash
sudo dnf install cairo-devel pango-devel libjpeg-turbo-devel giflib-devel \
    gobject-introspection-devel gcc gcc-c++ cmake ninja-build \
    ffmpeg blender
```

### System Packages (Ubuntu/Debian)
```bash
sudo apt install libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev \
    libgirepository1.0-dev build-essential cmake ninja-build \
    ffmpeg blender
```

### CUDA Toolkit
CUDA 13.0+ must be installed system-wide for Blackwell GPUs (sm_120).
For older GPUs (Ampere/Ada), CUDA 12.1+ suffices.

---

## Installation Steps

### Step 1: Create Virtual Environment
```bash
python3.13 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### Step 2: Install PyTorch Nightly Stack
```bash
pip install -r deployment/requirements-torch.txt
```

**CRITICAL**: All torch packages MUST be from the same nightly date (20260203).
Even 1 day difference causes CUDA crashes on Blackwell GPUs.

Verify:
```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# Expected: 2.11.0.dev20260203+cu130 True
```

### Step 3: Install Main Requirements
```bash
pip install -r requirements.txt
```

### Step 4: Install Git-Based Packages
```bash
pip install -r deployment/requirements-git.txt
```

Note: `heartlib` uses `--no-deps` to avoid it pulling in its own pinned torch
version which conflicts with our nightly build.

### Step 5: Build custom_rasterizer (Hunyuan3D-2 CUDA Extension)
```bash
# Clone Hunyuan3D-2 (only need the custom_rasterizer subdirectory)
git clone --depth 1 https://github.com/Tencent/Hunyuan3D-2.git /tmp/Hunyuan3D-2

# Build and install the CUDA rasterizer
cd /tmp/Hunyuan3D-2/hy3dgen/texgen/custom_rasterizer
pip install .

# Verify
python -c "import torch; import custom_rasterizer; print('OK')"

# Cleanup
rm -rf /tmp/Hunyuan3D-2
```

This compiles `rasterizer_gpu.cu` into a Python extension. Requires:
- CUDA toolkit (nvcc)
- gcc/g++ compatible with your CUDA version
- ninja (for parallel compilation)

### Step 6: Install SpaCy Models
```bash
pip install -r deployment/requirements-spacy.txt
```

### Step 7: Verify Installation
```bash
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'GPU: {torch.cuda.get_device_name(0)}')

import diffusers; print(f'Diffusers: {diffusers.__version__}')
import transformers; print(f'Transformers: {transformers.__version__}')
import hy3dgen; print('hy3dgen: OK')
import custom_rasterizer; print('custom_rasterizer: OK')
import heartlib; print('heartlib: OK')
import mmaudio; print('MMAudio: OK')
import imagebind; print('ImageBind: OK')
import spacy; print(f'SpaCy: {spacy.__version__}')
nlp_de = spacy.load('de_core_news_lg'); print('SpaCy de model: OK')
nlp_xx = spacy.load('xx_ent_wiki_sm'); print('SpaCy xx model: OK')
print('All checks passed.')
"
```

---

## Model Files

Model checkpoints are NOT managed by pip. They must be placed manually:

| Model | Location | Source |
|-------|----------|--------|
| SD3.5 Large | `ComfyUI/models/checkpoints/sd3.5_large.safetensors` | HuggingFace (stabilityai) |
| Hunyuan3D-2 | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/` | Auto-downloaded on first use |
| HeartMuLa | Configured path in `user_settings.json` | Local checkpoint |
| MMAudio | Auto-downloaded | HuggingFace |
| Stable Audio | Auto-downloaded | HuggingFace |
| Qwen2-VL | Managed by Ollama | `ollama pull qwen3-vl:2b` |

---

## Troubleshooting

### custom_rasterizer build fails
- Ensure `nvcc --version` matches your CUDA toolkit
- Ensure `ninja` is installed (`pip install ninja` or system package)
- On CUDA 13.0: may need `TORCH_CUDA_ARCH_LIST="12.0"` environment variable

### PyTorch CUDA crash on startup
- Verify ALL torch packages are from the same nightly date
- Check: `python -c "import torch; print(torch.__version__)"` — must show `+cu130`
- If mixed versions: `pip uninstall torch torchaudio torchvision torchao -y` and reinstall from `requirements-torch.txt`

### heartlib import fails
- Must be installed with `--no-deps` to avoid torch version conflict
- Verify: `pip show heartlib` should show the editable install path

### SpaCy model loading fails
- Models must be installed separately from SpaCy itself
- Verify: `python -m spacy validate`
