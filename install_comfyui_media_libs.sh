#!/bin/bash
# AI4ArtsEd - The libraries of the media stations, into ComfyUI's venv
#
# Stage 6 of the move to ComfyUI: Stable Audio 3, ImageBind,
# MMAudio, HeartMuLa and Hunyuan3D run as nodes of the platform's package
# (comfyui_nodes/ai4artsed_comfyui), so their libraries have to be where ComfyUI
# runs. install_comfyui_nodes.sh calls this after it linked the package; it can
# be run on its own after a fresh ComfyUI venv.
#
#   1. comfyui_nodes/ai4artsed_comfyui/requirements-media.txt (pip, pinned)
#   2. stable-audio-tools, heartlib, MMAudio, ImageBind (+ pytorchvideo), hy3dgen:
#      from their git commits, --no-deps, because each pins a torch of its own
#      and would replace ComfyUI's. stable-audio-tools also declares
#      python <3.11, a stale cap (its deps run on 3.13), hence
#      --ignore-requires-python for that one.
#   3. custom_rasterizer, Hunyuan3D 2's CUDA extension, built against the
#      venv's torch (needs nvcc; CUDA_HOME and TORCH_CUDA_ARCH_LIST below).
#   4. An import of every library, which is what the package's stations check.
#
# Idempotent: pip leaves what is installed at the pinned version alone.
#
#   COMFYUI_PATH          <repo>/dlbackend/ComfyUI by default
#   HEARTLIB_DIR          a local heartlib clone to install instead of the commit
#                         (docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md §3.5
#                         clones it into <repo>/heartlib; used when present)
#   CUDA_HOME             /usr/local/cuda-13.0 by default
#   TORCH_CUDA_ARCH_LIST  "12.0" by default (RTX 5090 / RTX PRO 6000)
#   SKIP_RASTERIZER=1     leave the CUDA extension out (no nvcc on this machine)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMFYUI_PATH="${COMFYUI_PATH:-${SCRIPT_DIR}/dlbackend/ComfyUI}"
PKG="$SCRIPT_DIR/comfyui_nodes/ai4artsed_comfyui"
PY="$COMFYUI_PATH/venv/bin/python"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda-13.0}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-12.0}"

# The commits deployment/requirements-git.txt names for the DevServer's venv.
HEARTLIB_REF="ef0c33b8143680f70c78ec148fbceeec53d6151e"
MMAUDIO_REF="8e060ccf1f4171ca58ffed549975ea92d7b80165"
IMAGEBIND_REF="53680b02d7e37b19b124fa37bae4b6c98c38f5be"
PYTORCHVIDEO_REF="6cdc929315aab1b5674b6dcf73b16ec99147735f"
# stable-audio-tools at the commit the platform's Stable Audio 3 station ran on.
STABLE_AUDIO_TOOLS_REF="3241adba4fc2a85cf5b29d9eb68d42f40a28e820"
# hy3dgen from PyPI; its custom_rasterizer from the Hunyuan3D-2 repository at the
# commit the platform's Hunyuan3D station was built against on 2026-09-14
# (docs/installation/UBUNTU_SERVER_FRESH_INSTALL.md §3.6 builds the same one).
HY3DGEN_VERSION="2.0.2"
HUNYUAN3D_REF="f8db63096c8282cb27354314d896feba5ba6ff8a"

echo -e "${BLUE}=== AI4ArtsEd - media station libraries for ComfyUI ===${NC}"
if [ ! -x "$PY" ]; then
    echo -e "${RED}[✗]${NC} no venv at $COMFYUI_PATH/venv (create ComfyUI's venv first)"
    exit 1
fi
echo "venv: $COMFYUI_PATH/venv"

echo -e "${BLUE}[1/4]${NC} pinned packages (requirements-media.txt)"
"$PY" -m pip install -r "$PKG/requirements-media.txt"

echo -e "${BLUE}[2/4]${NC} the libraries from their commits (--no-deps)"
"$PY" -m pip install --no-deps --ignore-requires-python \
    "git+https://github.com/Stability-AI/stable-audio-tools@${STABLE_AUDIO_TOOLS_REF}#egg=stable-audio-tools"
if [ -n "$HEARTLIB_DIR" ] && [ -f "$HEARTLIB_DIR/pyproject.toml" ]; then
    "$PY" -m pip install --no-deps -e "$HEARTLIB_DIR"
elif [ -f "$SCRIPT_DIR/heartlib/pyproject.toml" ]; then
    "$PY" -m pip install --no-deps -e "$SCRIPT_DIR/heartlib"
else
    "$PY" -m pip install --no-deps "git+https://github.com/HeartMuLa/heartlib.git@${HEARTLIB_REF}#egg=heartlib"
fi
"$PY" -m pip install --no-deps "git+https://github.com/hkchengrex/MMAudio@${MMAUDIO_REF}#egg=mmaudio"
"$PY" -m pip install --no-deps "git+https://github.com/facebookresearch/pytorchvideo.git@${PYTORCHVIDEO_REF}#egg=pytorchvideo"
"$PY" -m pip install --no-deps "git+https://github.com/facebookresearch/ImageBind@${IMAGEBIND_REF}#egg=imagebind"
"$PY" -m pip install --no-deps "hy3dgen==${HY3DGEN_VERSION}"

echo -e "${BLUE}[3/4]${NC} custom_rasterizer (Hunyuan3D 2, CUDA extension)"
if [ "${SKIP_RASTERIZER:-0}" = "1" ]; then
    echo "skipped (SKIP_RASTERIZER=1): the Hunyuan3D station stays unavailable"
elif "$PY" -c "import torch, custom_rasterizer" 2>/dev/null; then
    echo "already built"
else
    if [ ! -x "$CUDA_HOME/bin/nvcc" ]; then
        echo -e "${RED}[✗]${NC} no nvcc at $CUDA_HOME/bin (set CUDA_HOME, or SKIP_RASTERIZER=1)"
        exit 1
    fi
    BUILD_DIR="$(mktemp -d)"
    trap 'rm -rf "$BUILD_DIR"' EXIT
    git clone --filter=blob:none --no-checkout https://github.com/Tencent/Hunyuan3D-2.git "$BUILD_DIR/Hunyuan3D-2"
    git -C "$BUILD_DIR/Hunyuan3D-2" checkout --quiet "$HUNYUAN3D_REF"
    ( cd "$BUILD_DIR/Hunyuan3D-2/hy3dgen/texgen/custom_rasterizer" && \
      PATH="$CUDA_HOME/bin:$PATH" MAX_JOBS="${MAX_JOBS:-8}" "$PY" -m pip install --no-build-isolation . )
fi

echo -e "${BLUE}[4/4]${NC} import check"
"$PY" - <<'PY'
import importlib
import torch  # noqa: F401  (custom_rasterizer needs torch's libraries loaded first)
failed = []
for name in ("stable_audio_tools", "heartlib", "mmaudio", "imagebind", "muq", "hy3dgen",
             "custom_rasterizer", "librosa", "qwen_vl_utils"):
    try:
        importlib.import_module(name)
        print(f"  ok   {name}")
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        failed.append(name)
raise SystemExit(1 if failed else 0)
PY
echo -e "${GREEN}[✓]${NC} the media station libraries are in ComfyUI's venv; restart ComfyUI"
