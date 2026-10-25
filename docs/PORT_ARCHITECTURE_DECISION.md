# Port Architecture Decision

**Document Type:** Architecture Decision Record
**Date:** 2025-12-15 (original), 2026-03-03 (updated: SwarmUI removed)
**Status:** RESOLVED

---

## Port Schema

| Port  | Service          | Purpose                         |
|-------|------------------|---------------------------------|
| 17801 | DevServer (prod) | Production backend              |
| 17802 | DevServer (dev)  | Development backend             |
| 17803 | GPU Service      | Diffusers, HeartMuLa inference  |
| 17804 | ComfyUI          | Workflow-based generation       |
| 11434 | Ollama           | Local LLM inference             |

All ports in the **178xx** range are AI4ArtsEd-specific, avoiding conflicts with standard service ports (e.g. ComfyUI default 8188, Ollama default 11434).

---

## History

**2025-12-15:** Original decision evaluated SwarmUI (port 7801) as "single front door" proxying ComfyUI (port 7821). This was implemented and worked but added unnecessary middleware complexity.

**2026-01-xx:** SwarmUI replaced by standalone ComfyUI installation (`dlbackend/ComfyUI/`). Port 7821 was kept as a legacy artifact from SwarmUI's internal port assignment.

**2026-03-03:** Full SwarmUI cleanup. Port changed from 7821 to 17804 (consistent with AI4ArtsEd port schema). All SwarmUI code, config, and documentation removed.

---

## Current Architecture

ComfyUI runs as a standalone embedded process:
- Started via `2_start_comfyui.sh`
- Managed by `ComfyUIManager` (auto-start, health checks)
- Connected via WebSocket (`comfyui_ws_client.py`)
- Models stored in `dlbackend/ComfyUI/models/`

See: `docs/ARCHITECTURE PART 24 - ComfyUI-Integration.md` for full details.
