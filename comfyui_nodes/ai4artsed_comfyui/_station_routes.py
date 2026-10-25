"""
The media stations, answered on ComfyUI's HTTP server.

    GET /ai4artsed/stations   -> {station: {library, installed, error}}

One line per station of the package (Stable Audio 3, ImageBind, MMAudio,
HeartMuLa, Hunyuan3D, the media readers): whether its library imports in
ComfyUI's venv, and which model folders it lists. The DevServer's settings
page reads it for the backend status, and the cross-aesthetic surface asks
it which of its ways are there. Off the queue, like the tokenizer routes:
an import check and a directory listing, nothing on the card.
"""
import asyncio
import importlib
import logging
import sys
import threading
import time

from aiohttp import web

logger = logging.getLogger(__name__)

# station -> (the library an import proves, the package module that lists its folders)
STATIONS = {
    "stable_audio": ("stable_audio_tools", "_stable_audio"),
    "imagebind": ("imagebind", "_imagebind"),
    "mmaudio": ("mmaudio", "_mmaudio"),
    "heartmula": ("heartlib", "_heartmula"),
    "hunyuan3d": ("hy3dgen", "_hunyuan3d"),
    "media_reading": ("transformers", "_media_reading"),
}

_library_checks = {}


def _library(name: str):
    """Whether the library imports, remembered: an import that succeeded
    stays succeeded, and one that failed is retried at the next call, so an
    install while ComfyUI runs is seen."""
    if _library_checks.get(name) is True:
        return True, ""
    try:
        importlib.import_module(name)
    except Exception as e:
        return False, f"{name}: {e}"
    _library_checks[name] = True
    return True, ""


def stations():
    out = {}
    for station, (library, module_name) in STATIONS.items():
        ok, error = _library(library)
        installed = []
        try:
            module = importlib.import_module(f"{__package__}.{module_name}")
            installed = module.installed_dirs()
        except Exception as e:
            error = error or f"{module_name}: {e}"
        out[station] = {"library": ok, "installed": installed, "error": error}
    return out


def _warm():
    """The six libraries imported once at start, on a thread of their own,
    so that the first request finds the imports done: 4.5 s for all six in
    ComfyUI's venv (measured 2026-09-14), against the DevServer's read cap
    on the request."""
    started = time.time()
    try:
        report = stations()
    except Exception as e:
        logger.warning(f"[AI4ArtsEd stations] warming the stations failed: {e!r}")
        return
    faults = {s: r["error"] for s, r in report.items() if r["error"]}
    logger.info(f"[AI4ArtsEd stations] libraries imported in {time.time() - started:.1f} s"
                + (f"; faults: {faults}" if faults else ""))


def register(routes):
    @routes.get("/ai4artsed/stations")
    async def stations_route(_request):
        loop = asyncio.get_running_loop()
        try:
            return web.json_response(await loop.run_in_executor(None, stations))
        except Exception as e:
            logger.error(f"[AI4ArtsEd stations] failed: {e}")
            return web.json_response({"error": f"stations failed: {e}"}, status=500)


def install():
    """Register the route on the running PromptServer; False where there is
    none (the server is taken from sys.modules, the way _tokenizer_routes
    takes it)."""
    server = sys.modules.get("server")
    instance = getattr(getattr(server, "PromptServer", None), "instance", None)
    routes = getattr(instance, "routes", None)
    if routes is None:
        return False
    try:
        register(routes)
    except Exception as e:
        logger.error(f"[AI4ArtsEd stations] the route stays unregistered: {e}")
        return False
    threading.Thread(target=_warm, name="ai4artsed-stations-warm", daemon=True).start()
    return True
