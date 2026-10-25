#!/bin/bash
# AI4ArtsEd - Automated ComfyUI Custom Nodes Installation
# Installs the optional ComfyUI custom nodes used by AI4ArtsEd.
#
# Architecture: AI4ArtsEd uses a single-directory layout. ComfyUI lives at
#   <repo>/dlbackend/ComfyUI/
# Its custom_nodes/ and venv/ are under that path.
#
# Override the target by exporting COMFYUI_PATH before running:
#   COMFYUI_PATH=/some/other/ComfyUI ./install_comfyui_nodes.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Resolve repo root from this script's location, then default ComfyUI path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMFYUI_PATH="${COMFYUI_PATH:-${SCRIPT_DIR}/dlbackend/ComfyUI}"

echo -e "${BLUE}=== AI4ArtsEd - ComfyUI Custom Nodes Installer ===${NC}"
echo ""
echo "ComfyUI path: $COMFYUI_PATH"
echo ""

if [ ! -d "$COMFYUI_PATH" ]; then
    echo -e "${RED}[✗]${NC} ComfyUI not found at: $COMFYUI_PATH"
    echo ""
    echo "Clone ComfyUI first (e.g. from inside the repo root):"
    echo "  ${BLUE}git clone https://github.com/comfyanonymous/ComfyUI.git dlbackend/ComfyUI${NC}"
    echo "Or override the target with: COMFYUI_PATH=/path/to/ComfyUI"
    exit 1
fi

CUSTOM_NODES_DIR="$COMFYUI_PATH/custom_nodes"
if [ ! -d "$CUSTOM_NODES_DIR" ]; then
    echo -e "${RED}[✗]${NC} ComfyUI custom_nodes directory not found"
    echo "Expected: $CUSTOM_NODES_DIR"
    exit 1
fi

echo -e "${GREEN}[✓]${NC} ComfyUI custom_nodes directory found"
echo ""

cd "$CUSTOM_NODES_DIR"

# ComfyUI's own venv, and no other. The node package pins transformers 5
# (comfyui_nodes/ai4artsed_comfyui/requirements.txt); the DevServer's venv is
# pinned to 4.57 and refuses every other version
# (scripts/validate_transformers_runtime.py), so a fallback into it broke the
# environment it was meant to spare and the next update.sh with it (S-022,
# until 2026-10-10). Like install_comfyui_media_libs.sh: no ComfyUI venv, no run.
if [ ! -f "$COMFYUI_PATH/venv/bin/activate" ]; then
    echo -e "${RED}[✗]${NC} no venv at $COMFYUI_PATH/venv (create ComfyUI's venv first)"
    exit 1
fi
echo -e "${BLUE}[Activating]${NC} virtual environment: $COMFYUI_PATH/venv"
# shellcheck disable=SC1091
source "$COMFYUI_PATH/venv/bin/activate"
echo -e "${GREEN}[✓]${NC} Virtual environment activated"
echo ""

# Step 0: the ComfyUI this venv belongs to has to build FLUX.2's tokenizer
# without transformers' MistralConverter. requirements.txt of ai4artsed_comfyui
# asks for transformers >= 5.17 (its reason stands there), and a ComfyUI from
# before 2026-08-11 builds the Mistral-3 tokenizer of FLUX.2 in
# comfy/text_encoders/flux.py through transformers' MistralConverter, whose
# constructor in 5.17.0 requires a vocab_file that the call does not pass.
# FLUX.2 ran daily on transformers 5.2.0; on the day the venv went to 5.17.0
# on a ComfyUI of 2026-02-26, every FLUX.2 run ended in CLIPLoader with
# "MistralConverter.__init__() missing 1 required positional argument:
# 'vocab_file'". Upstream commit
# bbb4b04caa37b4608db32163899fdda148a041e5 ("Don't depend on transformers for
# mistral and llama tokenizers", #15503, 2026-08-11, first release v0.32.0)
# removes that import. Checked on the files, not on git ancestry: a cherry-pick
# of that commit or an unpacked copy of ComfyUI carries the fix without carrying
# the commit. The check reads the import or the call outside a comment, so a
# comment that still names the class does not refuse a ComfyUI that has the
# fix; it vouches for FLUX.2's tokenizer alone. What ran on the same venv after
# the fix, and what did not, stands in the log entry.
TE_DIR="$COMFYUI_PATH/comfy/text_encoders"
if [ ! -r "$TE_DIR/flux.py" ]; then
    echo -e "${RED}[✗]${NC} $TE_DIR/flux.py is missing or unreadable; this check reads it."
    echo "    FLUX.2's text encoder lives there in every ComfyUI that runs FLUX.2."
    exit 1
fi
set +e
MISTRAL_HIT="$(grep -rlE --include='*.py' '^[^#]*(MistralConverter[[:space:]]*\(|import[^#]*MistralConverter)' "$TE_DIR")"
MISTRAL_RC=$?
set -e
if [ "$MISTRAL_RC" -gt 1 ]; then
    echo -e "${RED}[✗]${NC} Could not read $TE_DIR (grep exit $MISTRAL_RC); this check reads every .py file in it."
    exit 1
fi
if [ "$MISTRAL_RC" -eq 0 ]; then
    if [ -e "$COMFYUI_PATH/.git" ]; then
        COMFYUI_REV="$(git -C "$COMFYUI_PATH" log -1 --format='%h of %cs' 2>/dev/null || echo "git clone, revision unreadable")"
        COMFYUI_FIX="git -C \"$COMFYUI_PATH\" pull --ff-only"
    else
        COMFYUI_REV="unpacked copy, no git"
        COMFYUI_FIX="replace $COMFYUI_PATH by an unpacked ComfyUI v0.32.0 or later"
    fi
    echo -e "${RED}[✗]${NC} This ComfyUI ($COMFYUI_REV) imports or calls transformers' MistralConverter"
    echo "    to build FLUX.2's tokenizer:"
    echo "$MISTRAL_HIT" | sed 's/^/        /'
    echo "    transformers 5.17 (requirements.txt of ai4artsed_comfyui asks for >= 5.17) requires a"
    echo "    vocab_file that this call does not pass: every FLUX.2 run fails in CLIPLoader with"
    echo "    \"MistralConverter.__init__() missing 1 required positional argument: 'vocab_file'\"."
    echo "    Update ComfyUI to v0.32.0 or later (upstream commit bbb4b04c, 2026-08-11):"
    echo "        $COMFYUI_FIX"
    echo "    then re-run this script."
    exit 1
fi
echo -e "${GREEN}[✓]${NC} $TE_DIR builds FLUX.2's tokenizer without transformers' MistralConverter"
echo ""

# Step 1: this repo's own nodes
#
# A node is a single .py file, or a package: a directory with an __init__.py.
# The package ai4artsed_comfyui/ is the fork, taken on 2026-09-12, of
# github.com/joeriben/ai4artsed_comfyui_nodes, which this script cloned into
# custom_nodes/ until that day. The clone read its keys from a key file of its
# own; the fork reads the platform's (devserver/config/llm_providers.json). An
# existing clone at custom_nodes/ai4artsed_comfyui is a real directory of the
# same name and is reported below, not replaced: move it out of custom_nodes/,
# then re-run. This step comes first: a clone or pip failure in the foreign
# packages below stops the script (set -e) and must not leave these out.
echo -e "${BLUE}[1/2]${NC} Linking AI4ArtsEd's own nodes from this repo..."
OWN_NODES_DIR="$SCRIPT_DIR/comfyui_nodes"
if [ ! -d "$OWN_NODES_DIR" ]; then
    echo -e "${RED}[✗]${NC} $OWN_NODES_DIR is missing — the own nodes cannot be installed."
    echo "    ComfyUI rejects a workflow using a node it does not have, at submit time."
    exit 1
fi

OWN_NODES_LINKED=0
OWN_NODES_FOUND=0
OWN_NODES_BLOCKED=0
for node_source in "$OWN_NODES_DIR"/*.py "$OWN_NODES_DIR"/*/; do
    [ -e "$node_source" ] || continue
    node_source="${node_source%/}"
    # A directory without an __init__.py is no package (__pycache__, notes).
    if [ -d "$node_source" ] && [ ! -f "$node_source/__init__.py" ]; then
        continue
    fi
    OWN_NODES_FOUND=$((OWN_NODES_FOUND + 1))
    node_name="$(basename "$node_source")"
    node_target="$CUSTOM_NODES_DIR/$node_name"
    if [ -e "$node_target" ] && [ ! -L "$node_target" ]; then
        if [ -d "$node_target" ]; then
            what="a directory"
        else
            what="a real file"
        fi
        echo -e "${RED}[✗]${NC} $node_name is $what in custom_nodes — left untouched, and"
        echo "    the node from this repo is therefore NOT installed. Move it out of"
        echo "    custom_nodes/ (ComfyUI loads every directory in there, whatever its"
        echo "    name, unless it ends in .disabled), then re-run."
        OWN_NODES_BLOCKED=$((OWN_NODES_BLOCKED + 1))
        continue
    fi
    ln -sfn "$node_source" "$node_target"
    echo -e "${GREEN}[✓]${NC} $node_name -> $node_source"
    OWN_NODES_LINKED=$((OWN_NODES_LINKED + 1))
    # What the package needs beyond ComfyUI's own requirements, into the venv
    # ComfyUI runs in (accelerate: loading an FP8 language model).
    if [ -f "$node_source/requirements.txt" ]; then
        if pip install -r "$node_source/requirements.txt"; then
            echo -e "${GREEN}[✓]${NC} $node_name requirements installed"
        else
            echo -e "${RED}[✗]${NC} $node_name requirements failed to install ($node_source/requirements.txt)"
            OWN_NODES_BLOCKED=$((OWN_NODES_BLOCKED + 1))
        fi
    fi
done

if [ "$OWN_NODES_FOUND" -eq 0 ]; then
    echo -e "${YELLOW}[⚠]${NC} No node sources found in $OWN_NODES_DIR"
elif [ "$OWN_NODES_BLOCKED" -gt 0 ]; then
    # Reporting success here is what stage 0.4 exists to stop: ComfyUI rejects a
    # workflow using a node it does not have, and the run ends at the door.
    echo -e "${RED}[✗]${NC} $OWN_NODES_BLOCKED of $OWN_NODES_FOUND own node(s) could not be installed"
    exit 1
else
    echo -e "${GREEN}[✓]${NC} $OWN_NODES_LINKED own node(s) linked"
fi
echo ""

# The media stations of the package (Stable Audio 3, ImageBind, MMAudio,
# HeartMuLa, Hunyuan3D, the media readers) need libraries pip cannot take from
# a requirements file alone: install_comfyui_media_libs.sh installs them into
# the same venv, from their pinned commits, and builds Hunyuan3D's CUDA
# extension. Without them the nodes register and each station reports its
# library missing on GET /ai4artsed/stations.
if [ "${SKIP_MEDIA_LIBS:-0}" = "1" ]; then
    echo -e "${YELLOW}[⚠]${NC} SKIP_MEDIA_LIBS=1: media station libraries left out"
elif COMFYUI_PATH="$COMFYUI_PATH" "$SCRIPT_DIR/install_comfyui_media_libs.sh"; then
    echo -e "${GREEN}[✓]${NC} media station libraries installed"
else
    echo -e "${RED}[✗]${NC} media station libraries failed to install (install_comfyui_media_libs.sh)"
    exit 1
fi
echo ""

# Step 2: ComfyUI-LTXVideo
echo -e "${BLUE}[2/2]${NC} Installing ComfyUI-LTXVideo (video generation)..."
if [ -d "ComfyUI-LTXVideo" ]; then
    echo -e "${YELLOW}[⚠]${NC} ComfyUI-LTXVideo already exists, updating..."
    cd ComfyUI-LTXVideo
    git pull
    cd ..
else
    git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git
fi

cd ComfyUI-LTXVideo
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}[✓]${NC} ComfyUI-LTXVideo installed"
else
    echo -e "${YELLOW}[⚠]${NC} No requirements.txt found, skipping dependencies"
fi
cd ..
echo ""

# comfyui-sound-lab was cloned here as step 3 until 2026-10-10. No chunk of
# the platform names a node of that package (the one ACE-Step chunk ran on
# ComfyUI's own AceStep nodes); retired with the ACE-Step configs (S-010).

deactivate

echo ""
echo -e "${GREEN}[✓]${NC} All custom nodes installed!"
echo ""
echo "Installed nodes:"
ls -1 "$CUSTOM_NODES_DIR" | grep -E "ComfyUI-LTXVideo" || true
ls -1 "$OWN_NODES_DIR" | grep -v -E "README|__pycache__" | sed "s/^/  (from this repo) /" || true
echo ""
echo "Next steps:"
echo "  1. Restart the AI4ArtsEd backend (which auto-starts ComfyUI)"
echo "  2. Verify nodes load: tail the ComfyUI log on first request"
echo ""
