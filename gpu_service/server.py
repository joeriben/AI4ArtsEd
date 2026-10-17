#!/usr/bin/env python3
"""
AI4ArtsEd GPU Service — Shared Diffusers + HeartMuLa Inference

Standalone server that handles all GPU-intensive model inference.
Both dev (17802) and prod (17801) backends call this via HTTP REST.

Port: 17803 (configurable via GPU_SERVICE_PORT env var)
"""

import logging
import sys
import os
import threading

# Configure logging before importing app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gpu_service")

# Ensure gpu_service directory is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from waitress import serve
from app import create_app
from config import HOST, PORT, THREADS


def warm_diffusers_in_background():
    """Pay for the diffusers import while nobody is waiting on it.

    `from diffusers import StableDiffusion3Pipeline` is what is_available()
    runs, and the first time in a process it costs 2.5-7 s (measured
    2026-08-26 over 21 runs; the spread is transformers and torchao competing
    for CPU). A caller with a ten-second read budget can lose that race right
    after a restart, and what it reports then is "diffusers is not installed
    here" - a sentence about the installation, produced by a stopwatch.

    Three things this costs, all measured on 2026-08-26, none of them guessed:

    * ~407 MB RSS for the life of the process, on every machine - including one
      that only ever serves text and checking routes. torch itself (639 MB) was
      unconditional as well when this was measured, through the stable audio
      routes of that time; since stage 8 no route imports it at module level.
    * A CUDA CONTEXT, contrary to what an earlier version of this comment
      claimed: diffusers pulls in bitsandbytes, after which
      torch.cuda.is_initialized() is True and the process holds /dev/nvidia*.
      It allocates NO VRAM (memory_allocated and memory_reserved stay 0, and
      the PID never appears in nvidia-smi --query-compute-apps), and
      /api/health opens the same handles anyway through the VRAM monitor.
    * Under a saturated service this thread starves at the GIL: after 45 s of
      back-to-back requests it had loaded 2434 of 5169 modules and had not
      finished. It still helped - the first real caller arrived 71.4 s in with
      the thread against 83.9 s without - but it does not deliver in the state
      it was written for.

    It lives here rather than in create_app() because it is process work, and
    the factory is also built by tests and tools that have no use for 400 MB.
    """
    def _warm():
        try:
            from diffusers import StableDiffusion3Pipeline  # noqa: F401
            logger.info("[GPU-SERVICE] diffusers imported ahead of the first caller")
        except Exception as e:  # noqa: BLE001
            # A missing diffusers stays a question is_available() answers, and
            # the backend already says so at ERROR. The service serves
            # everything else regardless - which is exactly what a module-level
            # import would have taken away.
            logger.info("[GPU-SERVICE] diffusers stayed cold: %s: %s",
                        type(e).__name__, e)

    threading.Thread(target=_warm, name="diffusers-warmup", daemon=True).start()


def start_llm_engine():
    """Build the LLM backend before the first request, not on it.

    Three things have to happen before anything is served, and all three are
    process work rather than request work:

      * the coordinator learns that this backend exists and which PIDs belong to
        it, so a child spawned later is never counted as a foreign GPU user;
      * the orphan scan ends whatever an earlier run of this service left
        behind — a service killed hard leaves its children holding the card, and
        the state file is the only record of who they were;
      * SIGTERM, SIGINT and a plain exit are wired to end the children. systemd
        kills the whole control group anyway, so this is the first line rather
        than the only one, but a manual run has no second line at all.

    A failure here is logged and not fatal: the rest of the service serves, and
    a load that cannot happen refuses with its own reason rather than being
    pre-empted by a dead process.
    """
    try:
        from services.llm_child_backend import get_llm_backend
        backend = get_llm_backend()
    except Exception as e:  # noqa: BLE001
        logger.error("[GPU-SERVICE] LLM engine did not come up: %s: %s",
                     type(e).__name__, e)
        _install_ending(None)
        return

    # `llama-server --version` opens the CUDA device on this build. Asked here,
    # once, so that /api/llm/health can answer from the cache instead of taking
    # a GPU context while a model is loading on the same card.
    probe_build = getattr(backend, "probe_build", None)
    if callable(probe_build):
        try:
            build = probe_build()
            if build:
                logger.info("[GPU-SERVICE] llama-server build: %s", build)
        except Exception as e:  # noqa: BLE001
            logger.warning("[GPU-SERVICE] Could not read the llama-server version: %s", e)

    terminate_all = getattr(backend, "terminate_all", None)
    if not callable(terminate_all):
        # The in-process engine has no children to end; it dies with this
        # process, which is exactly the property the child engine exists to lose.
        terminate_all = None
    _install_ending(terminate_all)


def _install_ending(terminate_all):
    """Wire SIGTERM, SIGINT and a plain exit to what ends with this process,
    in this order: the plant-wide leases go back to the DevServer's gate — a
    hold that no longer exists must not keep the card's turn until the
    reaper there finds its heartbeat gone (services/gpu_admission.py) — and
    then the llama-server children are ended, where there are any."""
    def _end(reason: str) -> None:
        try:
            from services.gpu_admission import release_upstream_leases
            release_upstream_leases(reason)
        except Exception as e:  # noqa: BLE001
            logger.error("[GPU-SERVICE] Giving the plant-wide leases back on %s failed: %s",
                         reason, e)
        if terminate_all is not None:
            terminate_all(reason)

    try:
        from services.llm_child import install_shutdown_hooks
        install_shutdown_hooks(_end)
        logger.info("[GPU-SERVICE] On shutdown the plant-wide leases go back%s",
                    " and the LLM children are ended" if terminate_all else "")
    except Exception as e:  # noqa: BLE001
        logger.error("[GPU-SERVICE] Could not install the shutdown hooks: %s", e)


def main():
    app = create_app()
    start_llm_engine()
    warm_diffusers_in_background()

    # Page-cache warming (services/page_cache_warmer.py) deliberately stays
    # unstarted here. It was built on 2026-08-26 and taken back out the same
    # day: the saving is a factor of one, while a warm running next to a
    # loading job costs that job a factor of 5.03 on the same disk. The
    # measurements are in that module's docstring - read them before wiring
    # this back in.

    print(f"=== AI4ArtsEd GPU Service ===")
    print(f"Starting on http://{HOST}:{PORT}")
    print(f"Using {THREADS} threads")
    print(f"Endpoints:")
    print(f"  POST /api/diffusers/generate")
    print(f"  POST /api/diffusers/generate/fusion")
    print(f"  POST /api/diffusers/generate/attention")
    print(f"  POST /api/diffusers/generate/probing")
    print(f"  POST /api/diffusers/generate/algebra")
    print(f"  POST /api/diffusers/generate/archaeology")
    print(f"  GET  /api/health")
    print(f"Press Ctrl+C to stop")
    print()

    serve(
        app,
        host=HOST,
        port=PORT,
        threads=THREADS,
        url_scheme='http',
        channel_timeout=600,  # 10 min for long generations
    )


if __name__ == "__main__":
    main()
