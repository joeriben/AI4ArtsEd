# AI4ArtsEd — Supervised Installation (Agent Instructions)

You are supervising the installation of the AI4ArtsEd platform on a new machine.
Follow these steps exactly. Verify each step before proceeding to the next.

## Context

AI4ArtsEd is a pedagogical media generation platform. It requires:
- Python 3.13
- CUDA 13.0 (Blackwell GPUs) or CUDA 12.1+ (Ampere/Ada)
- Multiple GPU backends (Diffusers, HeartMuLa, Hunyuan3D-2, MMAudio)
- SpaCy NER models for DSGVO/GDPR safety checks
- One CUDA extension that must be compiled from source (custom_rasterizer)

## Pre-Flight Checks

Before starting, verify:
```bash
python3.13 --version      # Must be 3.13.x
nvcc --version             # CUDA compiler — needed for custom_rasterizer
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

### Verify Phase 2
```bash
python -c "
import flask, diffusers, transformers, spacy, hy3dgen
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

## Common Issues Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CUDA error: no kernel image` | Wrong CUDA arch | Set `TORCH_CUDA_ARCH_LIST` |
| `libc10.so not found` | torch not imported before CUDA ext | Always `import torch` first |
| `ModuleNotFoundError: heartlib` | Installed with deps, torch conflict | Reinstall with `--no-deps` |
| `spacy.load() fails` | Models not installed | Run `pip install -r deployment/requirements-spacy.txt` |
| `pymeshlab` build fail | Missing system OpenGL/Mesa libs | Install `mesa-libGL-devel` (Fedora) or `libgl1-mesa-dev` (Ubuntu) |
| `weasyprint` fails | Missing cairo/pango | Install system cairo + pango dev packages |
| Mixed torch nightly dates | CUDA crashes at runtime | Uninstall all torch pkgs, reinstall from `requirements-torch.txt` |
