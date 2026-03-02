# ARCHITECTURE PART 24 - ComfyUI Integration

**Created:** 2026-01-18
**Updated:** 2026-03-03 (SwarmUI removed, standalone ComfyUI)
**Status:** Production Ready

---

## Overview

ComfyUI serves as AI4ArtsEd's workflow-based image generation backend, providing access to Stable Diffusion and other models via WebSocket API. It runs as a standalone embedded process managed by the DevServer.

**Note:** SwarmUI was previously used as middleware (Sessions 113-120) but has been fully removed. ComfyUI now runs directly.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AI4ArtsEd DevServer                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌───────────────────┐    ┌────────────────────┐   │
│  │   Backend    │───▶│  ComfyUI Manager  │───▶│  Health Checks     │   │
│  │   Router     │    │   (Singleton)     │    │  (Port 17804)      │   │
│  └──────────────┘    └───────────────────┘    └────────────────────┘   │
│         │                     │                         │               │
│         │                     │ Auto-Start              │ Polling       │
│         ▼                     ▼                         ▼               │
│  ┌──────────────┐    ┌───────────────────┐    ┌────────────────────┐   │
│  │  WS Client   │    │  2_start_comfyui  │    │  ComfyUI Process   │   │
│  │  (submit +   │    │  (startup script) │    │  (Port 17804)      │   │
│  │   track)     │    └───────────────────┘    └────────────────────┘   │
│  └──────────────┘                                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Port Schema

| Port  | Service          | Purpose                    |
|-------|------------------|----------------------------|
| 17801 | DevServer (prod) | Production backend         |
| 17802 | DevServer (dev)  | Development backend        |
| 17803 | GPU Service      | Diffusers/HeartMuLa        |
| 17804 | ComfyUI          | Workflow-based generation  |

---

## ComfyUI Manager Service

**Location:** `devserver/my_app/services/comfyui_manager.py`

Manages ComfyUI lifecycle: startup, health checks, auto-recovery.

```python
class ComfyUIManager:
    """Singleton with lazy initialization."""

    async def ensure_comfyui_available(self) -> bool:
        """Main entry point. Guarantees ComfyUI is running."""
        if await self.is_healthy():
            return True
        return await self._start_comfyui()

    async def is_healthy(self) -> bool:
        """Check via GET /system_stats on port 17804."""
```

---

## WebSocket Client

**Location:** `devserver/my_app/services/comfyui_ws_client.py`

Primary integration point. Provides:
- Real-time progress tracking via WebSocket
- Denoising preview images
- Workflow submission and result download
- Image upload for img2img workflows

```
DevServer ──WebSocket──▶ ComfyUI (ws://127.0.0.1:17804/ws)
         ──HTTP GET────▶ ComfyUI (/history, /view, /system_stats)
         ──HTTP POST───▶ ComfyUI (/prompt, /upload/image)
```

---

## ComfyUI Installation

ComfyUI is installed as a standalone instance in `dlbackend/ComfyUI/` within the project directory. It has its own Python venv.

```
ai4artsed_development/
├── dlbackend/
│   └── ComfyUI/           # Standalone ComfyUI installation
│       ├── main.py
│       ├── venv/           # ComfyUI's own Python environment
│       └── models/         # Shared model directory
│           ├── checkpoints/
│           ├── clip/
│           └── loras/
└── 2_start_comfyui.sh      # Startup script
```

---

## Auto-Recovery

The ComfyUI Manager automatically starts ComfyUI when needed:

1. Backend Router calls `ensure_comfyui_available()` before any ComfyUI operation
2. Manager checks health via `GET /system_stats`
3. If unhealthy, executes `2_start_comfyui.sh`
4. Polls health endpoint until ready (timeout: 120s)

Configuration in `config.py`:
- `COMFYUI_AUTO_START` (default: true)
- `COMFYUI_STARTUP_TIMEOUT` (default: 120s)
- `COMFYUI_HEALTH_CHECK_INTERVAL` (default: 2.0s)
