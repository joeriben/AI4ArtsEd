"""
What ComfyUI holds on the card, answered on ComfyUI's HTTP server.

    GET /ai4artsed/card   -> {free_mb, total_mb, loaded_models: [{model, vram_mb, size_mb, in_use}]}

One line per model ComfyUI keeps resident: its own (a diffusion model, a text
encoder, a VAE — named by the class of the module, numbered when two share
it) and the platform's stations' (named station:key, the way the station
built it). `vram_mb` is what of the model is on the card right now,
`size_mb` the whole model, `in_use` whether a prompt is executing and the
model is one it uses — ComfyUI marks a model as used at load and clears the
mark only when it frees memory, so on an idle card the mark alone would call
every model of the last run busy. The memory figures are ComfyUI's own
reading of the device it computes on.

The DevServer's gate reads it for the settings page and the workshop
companion (services/gpu_gate.py, since stage 7 of the move to ComfyUI; until
then the GPU service listed the models it held itself). Off the queue, like
the station routes: a walk over a list, nothing on the card.
"""
import asyncio
import logging
import sys

from aiohttp import web

logger = logging.getLogger(__name__)


def _station_name(patcher, module) -> str:
    """station:key when a station of this package built the model, else ''."""
    try:
        from . import _card
    except Exception:
        return ""
    for registry in getattr(_card, "_registries", ()):
        for key in registry.keys():
            held = registry.peek(key)
            if held is None:
                continue
            if held.patcher is patcher or held.module is module:
                return f"{registry.name}:{key}"
    return ""


def _a_prompt_is_executing() -> bool:
    """Whether ComfyUI's queue has a prompt running right now."""
    server = sys.modules.get("server")
    instance = getattr(getattr(server, "PromptServer", None), "instance", None)
    queue = getattr(instance, "prompt_queue", None)
    return bool(getattr(queue, "currently_running", None))


def card():
    import comfy.model_management as mm
    device = mm.get_torch_device()
    out = {
        "free_mb": round(mm.get_free_memory(device) / (1024 * 1024), 1),
        "total_mb": round(mm.get_total_memory(device) / (1024 * 1024), 1),
        "loaded_models": [],
    }
    running = _a_prompt_is_executing()
    rows = []
    # A copy: the prompt worker appends to and pops from the list while a
    # request walks it.
    for loaded in list(mm.current_loaded_models):
        try:
            patcher = loaded.model
            if patcher is None:
                continue          # the weak reference is gone; the entry is on its way out
            if getattr(loaded, "device", device) != device:
                continue          # kept on the CPU (a text encoder under --lowvram): none of it is on the card
            module = getattr(patcher, "model", None)
            name = _station_name(patcher, module) or type(module).__name__
            rows.append((name, id(patcher), {
                "model": name,
                "vram_mb": round(loaded.model_loaded_memory() / (1024 * 1024), 1),
                "size_mb": round(loaded.model_memory() / (1024 * 1024), 1),
                "in_use": running and bool(getattr(loaded, "currently_used", False)),
            }))
        except Exception as e:  # noqa: BLE001 — one entry must not hide the others
            rows.append((f"unreadable ({e})", 0, {"model": f"unreadable ({e})", "vram_mb": 0.0,
                                                  "size_mb": 0.0, "in_use": False}))
    # Two SD3 checkpoints resident are two lines that must not read alike: a
    # reader keys its rows by the name. The number follows the object, not
    # the place in the list — ComfyUI moves the model it just used to the
    # front, and a number that followed the place would swap the two lines
    # from one poll to the next.
    by_name = {}
    for name, ident, _row in rows:
        by_name.setdefault(name, []).append(ident)
    for name, ident, row in rows:
        idents = sorted(by_name[name])
        if len(idents) > 1:
            n = idents.index(ident) + 1
            if n > 1:
                row["model"] = f"{name} #{n}"
        out["loaded_models"].append(row)
    return out


def register(routes):
    @routes.get("/ai4artsed/card")
    async def card_route(_request):
        loop = asyncio.get_running_loop()
        try:
            return web.json_response(await loop.run_in_executor(None, card))
        except Exception as e:
            logger.error(f"[AI4ArtsEd card] failed: {e}")
            return web.json_response({"error": f"card failed: {e}"}, status=500)


def install():
    """Register the route on the running PromptServer; False where there is
    none (the server is taken from sys.modules, the way _station_routes
    takes it)."""
    server = sys.modules.get("server")
    instance = getattr(getattr(server, "PromptServer", None), "instance", None)
    routes = getattr(instance, "routes", None)
    if routes is None:
        return False
    try:
        register(routes)
    except Exception as e:
        logger.error(f"[AI4ArtsEd card] the route stays unregistered: {e}")
        return False
    return True
