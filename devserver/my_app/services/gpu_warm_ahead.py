"""
Warming the next model while the current one is still working.

The gate lets one heavy operation allocate at a time, and that is what keeps
the card from running dry. It also means a model swap is dead time for
everybody in line: the run that needs a different model starts by loading it,
measured at 110 s for SD3.5 Large, while the card is otherwise idle.

That time can be spent earlier. While a run is working, the model the NEXT run
needs can be brought onto the card beside it — if it demonstrably fits.

Everything about "demonstrably" lives in the gate, not here:
  - the footprint must have been MEASURED on real runs, never taken from the
    declared table, which is where the guesses that emptied the card came from,
  - free memory must cover it with room to spare on top,
  - the running operation must have enough time left for the load to finish,
  - the VRAM sensor must be answering, and the gate must not be degraded.

This worker only asks "is there something to warm?" and then does the warming,
because the two ways to warm a model live here: a diffusers model is a request
to the GPU service, a ComfyUI model is a tiny workflow. The arithmetic stays
with the gate, which lives in this process since stage 7 of the move to
ComfyUI (gpu_gate.py): the advice, the claim and its release are calls.

Nothing here is essential. Every failure is logged and the loop goes on; the
worst case is that a model is loaded when its turn comes, exactly as before.
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

_CHUNKS_DIR = Path(__file__).resolve().parents[2] / "schemas" / "chunks"

_IDLE_POLL_S = 20.0     # nothing running: ask rarely
_BUSY_POLL_S = 8.0      # something running: ask often enough to be useful
_CONNECT_TIMEOUT = 5

_worker: Optional[threading.Thread] = None
_worker_lock = threading.Lock()
_checkpoint_to_chunk: Optional[Dict[str, str]] = None


def _base_url() -> str:
    from config import GPU_SERVICE_URL
    return GPU_SERVICE_URL.rstrip("/")


def _build_checkpoint_index() -> Dict[str, str]:
    """checkpoint file -> the chunk that loads it.

    The gate names a model by the file its workflow loads, because that is
    what ComfyUI keeps resident. To warm it again, the workflow that loads it
    has to be found. Sorted, so the mapping is the same on every start.
    """
    from my_app.services.comfyui_ws_client import _checkpoint_of
    index: Dict[str, str] = {}
    try:
        for path in sorted(_CHUNKS_DIR.glob("*.json")):
            try:
                chunk = json.loads(path.read_text())
            except Exception:
                continue
            wf = chunk.get("workflow")
            if not wf:
                continue
            ckpt = _checkpoint_of(wf)
            if not ckpt or ckpt == "comfyui":
                continue
            # Five chunks load sd3.5_large; alphabetical order would pick a
            # legacy research pipeline to warm it with. Prefer the plain
            # output chunk, and among those the simplest graph.
            cand = (0 if path.stem.startswith("output_") else 1,
                    0 if "img2img" not in path.stem else 1,
                    len(wf), path.stem)
            prev = index.get(ckpt)
            if prev is None or cand < prev[0]:
                index[ckpt] = (cand, path.stem)
    except Exception as e:
        logger.warning("[WARM-AHEAD] Could not index chunks: %s", e)
    return index


def _chunk_for(checkpoint: str) -> Optional[str]:
    global _checkpoint_to_chunk
    if _checkpoint_to_chunk is None:
        _checkpoint_to_chunk = _build_checkpoint_index()
    hit = _checkpoint_to_chunk.get(checkpoint)
    return hit[1] if hit else None


def _warm_comfyui(model_id: str) -> bool:
    """Run the smallest workflow that loads this checkpoint."""
    chunk_name = _chunk_for(model_id)
    if not chunk_name:
        logger.debug("[WARM-AHEAD] No chunk loads %s — nothing to warm", model_id)
        return False
    from my_app.routes.settings_routes import _build_comfyui_preload_workflow
    from my_app.services.comfyui_service import ComfyUIService
    workflow = _build_comfyui_preload_workflow(chunk_name)
    if not workflow:
        return False
    from my_app.services.comfyui_ws_client import ComfyUISubmitError
    comfy = ComfyUIService()
    try:
        prompt_id = comfy.submit_workflow(workflow)
    except ComfyUISubmitError as e:
        # Warming ahead is a courtesy; nobody is waiting on this one. The
        # reason still goes in the log, because a warm that keeps failing is
        # the same missing checkpoint that a run will hit next.
        logger.info("[WARM-AHEAD] %s not warmed: %s", model_id, e)
        return False
    logger.info("[WARM-AHEAD] Warming %s via %s (job %s)", model_id, chunk_name, prompt_id)
    # Wait for it, so the claim is held for as long as the card is busy with it.
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(3)
        try:
            if (comfy.get_queue_status() or {}).get("total", 0) == 0:
                break
        except Exception:
            break
    return True


def _warm_diffusers(model_id: str) -> bool:
    """Ask the GPU service to load it beside the running operation.

    The service re-checks with the gate before it does; a stale recommendation
    is refused there, not trusted here.
    """
    resp = requests.post(
        f"{_base_url()}/api/diffusers/load",
        json={"model_id": model_id, "prefetch": True},
        timeout=(_CONNECT_TIMEOUT, None),
    )
    if resp.status_code == 409:
        logger.debug("[WARM-AHEAD] GPU service declined: %s", resp.text[:120])
        return False
    resp.raise_for_status()
    logger.info("[WARM-AHEAD] Warmed %s beside the running operation", model_id)
    return True


def _claim(model_id: str) -> bool:
    from my_app.services.gpu_gate import get_gpu_gate
    return bool(get_gpu_gate().prefetch_claim(model_id))


def _release(model_id: str) -> None:
    from my_app.services.gpu_gate import get_gpu_gate
    try:
        get_gpu_gate().prefetch_done(model_id)
    except Exception:
        pass


def _loop() -> None:
    delay = _IDLE_POLL_S
    while True:
        time.sleep(delay)
        delay = _IDLE_POLL_S
        try:
            from my_app.services.gpu_gate import get_gpu_gate
            advice = get_gpu_gate().prefetch_advice() or {}
            rec = advice.get("recommended")
            if not rec:
                continue
            delay = _BUSY_POLL_S
            model_id = rec.get("model_id") or ""
            source = rec.get("source")
            if not model_id:
                continue

            if source == "remote":
                # ComfyUI: claim first, because the warm-up is a real job on the
                # card and nothing else may start a second one meanwhile.
                if not _claim(model_id):
                    continue
                try:
                    _warm_comfyui(model_id)
                finally:
                    _release(model_id)
            else:
                # diffusers: the service claims it itself inside the guarded route.
                _warm_diffusers(model_id)
        except Exception as e:
            logger.warning("[WARM-AHEAD] %s", e)


def start_warm_ahead_worker() -> None:
    """Start the warm-ahead loop once. Safe to call repeatedly."""
    global _worker
    try:
        from config import GPU_WARM_AHEAD
    except Exception:
        GPU_WARM_AHEAD = True
    if not GPU_WARM_AHEAD:
        logger.info("[WARM-AHEAD] Disabled by configuration")
        return
    with _worker_lock:
        if _worker is not None and _worker.is_alive():
            return
        _worker = threading.Thread(target=_loop, name="gpu-warm-ahead", daemon=True)
        _worker.start()
        logger.info("[WARM-AHEAD] Worker started — the next model is warmed while "
                    "the current one works, whenever the gate says there is measured room")
