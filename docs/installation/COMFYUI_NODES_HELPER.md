# ComfyUI Custom Nodes Installation Helper

`install_comfyui_nodes.sh` puts the platform's own ComfyUI nodes and the one
foreign package the chunks need into the ComfyUI under `dlbackend/ComfyUI`.

## Quick Start

```bash
cd <repo>
./install_comfyui_nodes.sh
```

Or with a ComfyUI elsewhere:

```bash
COMFYUI_PATH=/path/to/ComfyUI ./install_comfyui_nodes.sh
```

## What This Script Does

1. **ai4artsed_comfyui**: this repository's own nodes (`comfyui_nodes/ai4artsed_comfyui/`,
   since 2026-09-12 a fork of `joeriben/ai4artsed_comfyui_nodes`), linked into
   `custom_nodes/` and their `requirements.txt` installed into ComfyUI's venv; then
   `install_comfyui_media_libs.sh` for the libraries of the media stations (skip
   with `SKIP_MEDIA_LIBS=1`).
2. **ComfyUI-LTXVideo**: video generation, cloned or updated.

Before step 1 the script reads `comfy/text_encoders/flux.py` of the ComfyUI it was
given: a ComfyUI from before v0.32.0 builds FLUX.2's tokenizer through
transformers' `MistralConverter`, which the node package's transformers 5.17 no
longer satisfies; such a ComfyUI is refused with the upstream commit to update to.

`comfyui-sound-lab` was a third step until 2026-10-10. No chunk names a node of that
package; it went with the ACE-Step configs (S-010 of the code review of
2026-10-10).

## Prerequisites

1. ComfyUI under `<repo>/dlbackend/ComfyUI` (or `COMFYUI_PATH`), see
   [INSTALLATION.md](INSTALLATION.md)
2. ComfyUI's own venv at `$COMFYUI_PATH/venv`. The script installs into that venv
   and no other: the node package pins transformers 5, the DevServer's venv is
   pinned to 4.57 (`scripts/validate_transformers_runtime.py`), and a fallback into
   the DevServer's venv broke it (S-022, until 2026-10-10). Without ComfyUI's venv
   the script stops.

## Output

```
=== AI4ArtsEd - ComfyUI Custom Nodes Installer ===

ComfyUI path: <repo>/dlbackend/ComfyUI

[✓] ComfyUI custom_nodes directory found

[Activating] virtual environment: <repo>/dlbackend/ComfyUI/venv
[✓] Virtual environment activated

[✓] <repo>/dlbackend/ComfyUI/comfy/text_encoders builds FLUX.2's tokenizer without transformers' MistralConverter

[1/2] Linking AI4ArtsEd's own nodes from this repo...
[✓] ai4artsed_comfyui -> <repo>/comfyui_nodes/ai4artsed_comfyui
[✓] ai4artsed_comfyui requirements installed
[✓] 1 own node(s) linked
[✓] media station libraries installed

[2/2] Installing ComfyUI-LTXVideo (video generation)...
[✓] ComfyUI-LTXVideo installed

[✓] All custom nodes installed!
```

## Behavior Details

### Node Paths

```
$COMFYUI_PATH/custom_nodes/
├── ComfyUI-LTXVideo/
└── ai4artsed_comfyui -> <repo>/comfyui_nodes/ai4artsed_comfyui   (a link, not a clone)
```

### Update Logic

The own nodes are re-linked on every run (`ln -sfn`). A real directory of the
same name in `custom_nodes/` (a clone from before 2026-09-12) is left in place
and reported, and the script exits 1: move it out of `custom_nodes/`, re-run.

If ComfyUI-LTXVideo already exists the script runs `git pull` and reinstalls its
dependencies; otherwise it clones it.

### Dependency Installation

Into ComfyUI's venv: the own package's `requirements.txt`, the media station
libraries (`install_comfyui_media_libs.sh`, pinned commits, Hunyuan3D's CUDA
extension), ComfyUI-LTXVideo's `requirements.txt`. A failing install stops the
script (`set -e`): a node that is not installed makes ComfyUI reject every workflow
that uses it, at submit time.

## Troubleshooting

### ai4artsed_comfyui is a directory in custom_nodes

**Error:**
```
[✗] ai4artsed_comfyui is a directory in custom_nodes — left untouched, and
    the node from this repo is therefore NOT installed. Move it out of
    custom_nodes/ (ComfyUI loads every directory in there, whatever its
    name, unless it ends in .disabled), then re-run.
```

**Cause:** a clone of `joeriben/ai4artsed_comfyui_nodes` from before 2026-09-12,
when this script still cloned that repository. The clone reads an
`openrouter.key` of its own; the fork in this repository reads the platform's
keys (`devserver/config/llm_providers.json`).

**Solution:**
```bash
# out of custom_nodes/ entirely: ComfyUI loads every directory in there
mv dlbackend/ComfyUI/custom_nodes/ai4artsed_comfyui ~/ai4artsed_comfyui.clone-until-2026-09-12
./install_comfyui_nodes.sh
# then restart ComfyUI
```

### ComfyUI not found

**Error:**
```
[✗] ComfyUI not found at: <repo>/dlbackend/ComfyUI
```

**Solution:** clone ComfyUI into `dlbackend/ComfyUI` (see INSTALLATION.md), or
name it: `COMFYUI_PATH=/path/to/ComfyUI ./install_comfyui_nodes.sh`.

### no venv at .../ComfyUI/venv

**Error:**
```
[✗] no venv at <repo>/dlbackend/ComfyUI/venv (create ComfyUI's venv first)
```

**Solution:** create ComfyUI's venv first (INSTALLATION.md, the ComfyUI step); the
script does not install into any other venv.

### This ComfyUI imports or calls transformers' MistralConverter

**Error:** the script names the file and the upstream commit.

**Solution:** `git -C dlbackend/ComfyUI pull --ff-only` to v0.32.0 or later (or
replace an unpacked copy), then re-run.

## Next Steps After Installation

1. Restart ComfyUI (`sudo systemctl restart ai4artsed-comfyui` where the units of
   `setup_lab6000_supervision.sh` are installed; otherwise the DevServer starts it
   with `COMFYUI_AUTO_START`).
2. Download the models: `./download_models.sh` (see
   [INSTALLATION.md](INSTALLATION.md)).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFYUI_PATH` | `<repo>/dlbackend/ComfyUI` | The ComfyUI to install into |
| `SKIP_MEDIA_LIBS` | unset | `1` leaves the media station libraries out |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success: every node installed |
| 1 | ComfyUI, its `custom_nodes/`, its venv or FLUX.2's tokenizer fix missing; an own node blocked; an install failed |

---

**For detailed installation instructions, see:** [INSTALLATION.md](INSTALLATION.md)
