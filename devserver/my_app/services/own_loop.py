"""
A coroutine run to its end from a synchronous route.

`asyncio.run` leaves the thread it ran on without a current event loop, and the
thread serving a synchronous route is that thread (in a test run, the process's
main one). So the coroutine runs on a pool thread of its own, which keeps the
loop it made to itself. That thread starts with an EMPTY context and is handed
a COPY of the caller's: the run id and the output config the gate labels a
generation with (services/generation_abort.py), and the holder that says which
model the run is at (services/streaming_response.py, `note_dispatch`).

Two routes run one ComfyUI graph this way: the latent mean's decode
(routes/mean_images_routes.py) and the embedding research series
(routes/fusion_workbench_routes.py). Since 2026-10-10 the availability
checks (routes/config_routes.py, settings_routes.py) and the Text Lab's
calls to ComfyUI (routes/text_routes.py) come through here too; each built a
loop of its own on the request thread before, and left it closed there.
"""

import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor


def run_blocking(coroutine):
    """The coroutine's result, or its exception, from a thread of its own."""
    context = contextvars.copy_context()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: context.run(asyncio.run, coroutine)).result()
