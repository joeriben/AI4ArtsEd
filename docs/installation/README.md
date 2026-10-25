# AI4ArtsEd — Installation Documentation

This directory holds installation and configuration docs. **For a fresh install,
start here:**

## 👉 Primary Guide

**[UBUNTU_SERVER_FRESH_INSTALL.md](UBUNTU_SERVER_FRESH_INSTALL.md)** — Canonical
fresh-install procedure for an Ubuntu 26.04 LTS Server (headless). Covers Phase 0
(prep on old server) through Phase 10 (fitting the Blackwell card), including
rsync-based model transfer and cloudflared tunnel migration. The platform runs on
Blackwell (`sm_120`) alone — the 4090 phases are how an old box gets there, not a
second supported target.

---

## Supporting Documents (current)

| Document | Purpose |
|----------|---------|
| [SYSTEM_REQUIREMENTS.md](SYSTEM_REQUIREMENTS.md) | Hardware spec, OS compatibility, system packages |
| [SOFTWARE_VERSIONS.md](SOFTWARE_VERSIONS.md) | Pinned versions (Python 3.13, CUDA 13, Node 20) |
| [MODELS_REQUIRED.md](MODELS_REQUIRED.md) | Inventory of model files (sizes + sources) |
| [MODEL_TRANSFER.md](MODEL_TRANSFER.md) | rsync recipe between servers |
| [COMFYUI_NODES_HELPER.md](COMFYUI_NODES_HELPER.md) | ComfyUI custom_nodes reference |

## Authoritative under `/deployment/`

| File | Purpose |
|------|---------|
| [`deployment/AGENT_INSTALL_INSTRUCTIONS.md`](../../deployment/AGENT_INSTALL_INSTRUCTIONS.md) | Phase-by-phase Python install (Coding Agent oriented) |
| [`deployment/INSTALL_GUIDE.md`](../../deployment/INSTALL_GUIDE.md) | System packages + PyTorch nightly stack |
| `deployment/requirements-torch.txt` | PyTorch nightly pins (cu130, same-date constraint) |
| `deployment/requirements-git.txt` | heartlib / mmaudio / imagebind commits |
| `deployment/requirements-spacy.txt` | NER model URLs (DSGVO/GDPR) |

## Future Architecture Plan

**[CURRENT_DEPLOYMENT_PLAN.md](CURRENT_DEPLOYMENT_PLAN.md)** (2026-04-21, not yet
implemented) — Multi-tier installer with hardware profiles B/C/E and workspace
separation. Read this before changing installer scripts.

---

## Archive — Deprecated Documents

The following docs are retained for historical context only. They reference stale
architecture: Ollama as LLM provider (replaced by in-process `llama-cpp-python`),
`/opt/ai4artsed/` paths (replaced by single `~/ai/ai4artsed_development/` directory),
execution modes eco/fast (removed), and the dev/prod two-directory
split (abolished).

Each carries a DEPRECATED banner at the top.

- [QUICKSTART.md](QUICKSTART.md) — old quick-install guide
- [INSTALLATION.md](INSTALLATION.md) — old step-by-step
- [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) — old config reference
- [PC2_INSTALLATION.md](PC2_INSTALLATION.md) — old PC2-specific install
- [OFFLINE_INSTALL_MEDIUM.md](OFFLINE_INSTALL_MEDIUM.md) — old offline-medium install
- [`../../README_INSTALL.md`](../../README_INSTALL.md) — old repo-root install summary

Do **not** follow these. They will mislead you on stack details that have since changed.
