"""
HeartMuLa backend factory: the one place that hands out the client of the
platform's HeartMuLa node on ComfyUI (my_app/services/heartmula_client.py).

Usage:
    backend = get_heartmula_backend()
    if await backend.is_available():
        audio_bytes = await backend.generate_music(
            lyrics="[Verse] Hello world...",
            tags="pop, upbeat, male vocal"
        )
"""

import logging

logger = logging.getLogger(__name__)


# Singleton instance — the client of the platform's node on ComfyUI
_backend = None


def get_heartmula_backend():
    """
    Get HeartMuLa backend (the node on ComfyUI).

    Returns a HeartMuLaClient that runs the platform's node ai4artsed_heartmula
    on ComfyUI (until stage 6 of the move to ComfyUI it called the GPU
    service over HTTP). Callers: backend_router.py, the chunk files and the
    workshop preload in settings_routes.py.
    """
    global _backend
    if _backend is None:
        from my_app.services.heartmula_client import HeartMuLaClient
        _backend = HeartMuLaClient()
    return _backend


