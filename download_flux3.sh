#!/bin/bash
# AI4ArtsEd DevServer - FLUX 3 Image Klein Component Downloader
#
# Downloads the ComfyUI-ready FLUX 3 Image Klein components into
# <ComfyUI>/models/. The image model and its text encoder come from Black
# Forest Labs' own repackaging, black-forest-labs/flux-3-image-klein-comfy.
# That repository is GATED: the Hugging Face account behind the token
# (`hf auth login`, or HF_TOKEN in the environment) has to have accepted the
# FLUX Kommunity License on the model page first.
#
# Default (what the output config `flux3` loads):
#   diffusion_models/flux3-image-klein-bf16.safetensors   11.1 GB  (distilled checkpoint)
#   text_encoders/qwen3vl_4b_bf16.safetensors              8.9 GB  (Qwen3-VL-4B-Instruct)
#   vae/Flux/flux2-vae.safetensors                         0.3 GB  (only if missing)
#       FLUX 3 decodes with FLUX.2's VAE, and the flux3 chunk loads the file
#       the flux2 chunk loads. Where it is missing, this script fetches it
#       from Comfy-Org/flux2-dev, as download_flux2.sh does.
# Optional:
#   --base        diffusion_models/flux3-image-klein-base-bf16.safetensors  11.1 GB
#                 (undistilled, 50 steps, cfg 3.5; no output config uses it)
#   --upsampler   text_encoders/qwen3.5_9b_flux3_prompt_upsampler_bf16.safetensors 18.8 GB
#                 (BFL's prompt upsampler; no output config uses it)
#
# ComfyUI loads the files from version 0.41.0 on (native FLUX 3 support,
# Comfy-Org/ComfyUI#17064). The download runs with the platform venv's
# huggingface_hub, as download_media_models.sh does (VENV to point elsewhere).
#
# A target that already holds the size Hugging Face lists for its file is
# skipped. A target of another size, or a link that leads nowhere, stops that
# file and stays as it is. Files are fetched into <ComfyUI>/models/.incoming-flux3/,
# checked against the SHA-256 Hugging Face lists for them, and only then moved
# to their place; where the target folder lies on another disk, through a
# temporary name beside the target. A file that fails the check is deleted.
# One run at a time: a second run while one is going stops at once.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
COMFYUI_PATH="${COMFYUI_PATH:-${SCRIPT_DIR}/dlbackend/ComfyUI}"
VENV="${VENV:-${SCRIPT_DIR}/venv}"
PY="${VENV}/bin/python"
BFL="black-forest-labs/flux-3-image-klein-comfy"

# Each entry: <repository>|<path in the repository>|<path under models/>
FILES=(
    "${BFL}|diffusion_models/flux3-image-klein-bf16.safetensors|diffusion_models/flux3-image-klein-bf16.safetensors"
    "${BFL}|text_encoders/qwen3vl_4b_bf16.safetensors|text_encoders/qwen3vl_4b_bf16.safetensors"
)
for arg in "$@"; do
    case "$arg" in
        --base)      FILES+=("${BFL}|diffusion_models/flux3-image-klein-base-bf16.safetensors|diffusion_models/flux3-image-klein-base-bf16.safetensors") ;;
        --upsampler) FILES+=("${BFL}|text_encoders/qwen3.5_9b_flux3_prompt_upsampler_bf16.safetensors|text_encoders/qwen3.5_9b_flux3_prompt_upsampler_bf16.safetensors") ;;
        *) echo -e "${RED}Unknown option:${NC} $arg (known: --base, --upsampler)"; exit 1 ;;
    esac
done
FILES+=("Comfy-Org/flux2-dev|split_files/vae/flux2-vae.safetensors|vae/Flux/flux2-vae.safetensors")

echo -e "${BLUE}=== AI4ArtsEd FLUX 3 Image Klein Component Downloader ===${NC}"
echo ""
echo "ComfyUI path: $COMFYUI_PATH"
echo ""

if [ ! -x "$PY" ]; then
    echo -e "${RED}✗${NC} No platform venv at ${VENV} (its huggingface_hub does the download)."
    echo "Create it first (docs/installation/INSTALLATION.md), or set VENV to one that has huggingface_hub."
    exit 1
fi

if [ ! -d "$COMFYUI_PATH" ]; then
    echo -e "${YELLOW}Warning:${NC} ComfyUI directory not found at $COMFYUI_PATH"
    echo "Creating it now. If you intended a different path, set COMFYUI_PATH and re-run."
    mkdir -p "$COMFYUI_PATH"
fi
mkdir -p "$COMFYUI_PATH/models"

VERSION=$("$PY" -I -c 'import sys; sys.path.insert(0, sys.argv[1]); import comfyui_version as v; print(v.__version__)' "$COMFYUI_PATH" 2>/dev/null || echo "unknown")
if ! "$PY" -I -c 'import sys; v = sys.argv[1].split("."); sys.exit(0 if len(v) >= 2 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (0, 41) else 1)' "$VERSION"; then
    echo -e "${YELLOW}Warning:${NC} ComfyUI at ${COMFYUI_PATH} reports version ${VERSION}; FLUX 3 needs >= 0.41.0."
    echo "The files download anyway; ComfyUI loads them once it is at that version."
    echo ""
fi

STATUS=0
"$PY" -I - "$COMFYUI_PATH/models" "${FILES[@]}" <<'PYEOF' || STATUS=$?
import errno, fcntl, hashlib, os, shutil, sys
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import GatedRepoError

LOCKED = 3
models, entries = sys.argv[1], sys.argv[2:]
stage = os.path.join(models, ".incoming-flux3")
hf_dir = os.path.join(stage, ".cache", "huggingface")
os.makedirs(stage, exist_ok=True)
lock_path = os.path.join(stage, ".run.lock")
lock = open(lock_path, "w")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print(f"✗ Another run of download_flux3.sh holds {lock_path}; this one stops.")
    sys.exit(LOCKED)


def cause(e):
    lines = str(e).splitlines()
    return f"{type(e).__name__}: {lines[0] if lines else ''}"


def no_access(repo, e):
    print(f"✗ No access to {repo}: {cause(e)}")
    print(f"  Accept the FLUX Kommunity License on https://huggingface.co/{repo} with the Hugging Face")
    print("  account whose token this machine uses (`hf auth login`, or HF_TOKEN), then run again.")
    sys.exit(1)


fetched = []  # paths in the repositories that this run asked hf_hub_download for


def clear_stage():
    # The download's bookkeeping for the files of this run, then the folders
    # of the stage that are left empty, then the stage if only the lock is left.
    for src in fetched:
        for suffix in (".metadata", ".lock"):
            p = os.path.join(hf_dir, "download", *src.split("/")) + suffix
            if os.path.exists(p):
                os.remove(p)
    if not any(files for _, _, files in os.walk(os.path.join(hf_dir, "download"))):
        gitignore = os.path.join(hf_dir, ".gitignore")
        if os.path.exists(gitignore):
            os.remove(gitignore)
    for root, _, _ in os.walk(stage, topdown=False):
        if root != stage and not os.listdir(root):
            os.rmdir(root)
    if os.listdir(stage) == [".run.lock"]:
        os.remove(lock_path)
        os.rmdir(stage)


def place(path, target):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    try:
        os.replace(path, target)
        return
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
    # The target folder lies on another disk: the copy goes under a temporary
    # name beside the target, and only the whole file gets the target's name.
    tmp = target + ".incoming-flux3"
    try:
        shutil.copyfile(path, tmp)
        with open(tmp, "rb") as fh:
            os.fsync(fh.fileno())
        if os.path.getsize(tmp) != os.path.getsize(path):
            raise OSError(f"copy to {tmp} is {os.path.getsize(tmp)} bytes, the download {os.path.getsize(path)}")
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    os.remove(path)


by_repo = {}
for entry in entries:
    repo, src, dst = entry.split("|")
    by_repo.setdefault(repo, []).append((src, dst, os.path.join(models, dst)))

ok = True
try:
    for repo, files in by_repo.items():
        try:
            info = HfApi().model_info(repo, files_metadata=True)
        except GatedRepoError as e:
            no_access(repo, e)
        except Exception as e:
            if all(os.path.isfile(t) and os.path.getsize(t) > 0 for _, _, t in files):
                for _, dst, _ in files:
                    print(f"✓ In place, size not checked ({repo}: {cause(e)}): {dst}")
            else:
                print(f"✗ {repo}: {cause(e)}")
                ok = False
            continue
        listed = {s.rfilename: s for s in info.siblings}
        for src, dst, target in files:
            s = listed.get(src)
            if s is None or s.lfs is None:
                print(f"✗ {repo} at {info.sha} lists no file {src}")
                ok = False
                continue
            if os.path.lexists(target):
                if not os.path.exists(target):
                    print(f"✗ {dst} is a link that leads nowhere; left as it is. Remove it and run again.")
                    ok = False
                elif os.path.getsize(target) != s.lfs.size:
                    print(f"✗ {dst} holds {os.path.getsize(target)} bytes, {repo} lists {s.lfs.size}; left as it is. Remove it and run again.")
                    ok = False
                else:
                    print(f"✓ Already in place, skipping: {dst}")
                continue
            print(f"Downloading: {repo}/{src}", flush=True)
            fetched.append(src)
            try:
                path = hf_hub_download(repo, src, revision=info.sha, local_dir=stage)
            except GatedRepoError as e:
                no_access(repo, e)
            except Exception as e:
                print(f"✗ Download failed: {src} ({cause(e)})")
                ok = False
                continue
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for block in iter(lambda: fh.read(1 << 24), b""):
                    h.update(block)
            if h.hexdigest() != s.lfs.sha256:
                os.remove(path)
                print(f"✗ SHA-256 mismatch, file deleted: {src} (listed {s.lfs.sha256}, got {h.hexdigest()})")
                ok = False
                continue
            try:
                place(path, target)
            except Exception as e:
                print(f"✗ Could not move {src} to {dst} ({cause(e)})")
                ok = False
                continue
            print(f"✓ Downloaded and checked: {dst}", flush=True)
finally:
    clear_stage()
sys.exit(0 if ok else 1)
PYEOF

if [ "$STATUS" -eq 3 ]; then
    exit 1
fi

echo ""
echo "==================================="
echo -e "${BLUE}Verification:${NC}"
echo "==================================="
MODELS_OK=true
for entry in "${FILES[@]}"; do
    dst="${entry##*|}"
    check_model "${COMFYUI_PATH}/models/$dst" "$dst"
done
echo ""
if $MODELS_OK && [ "$STATUS" -eq 0 ]; then
    echo -e "${GREEN}=== Download Complete! ===${NC}"
    echo "See docs/installation/MODELS_REQUIRED.md for the full model inventory."
else
    echo -e "${RED}=== Download Failed ===${NC}"
    echo "See the lines marked ✗ above; files already in place are skipped when this script runs again."
    exit 1
fi
