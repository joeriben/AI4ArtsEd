"""
How big the card is — asked of ComfyUI.

Three places used to ask this, each with its own request to the GPU service and
its own way of dealing with an answer that failed to arrive: the Latent Lab
model resolver (which silently chose the smaller model), the Latent Lab
capability gate (which closed) and the hardware route (which answered with an
empty dict). One question, three askers, three failure directions.

The move to ComfyUI is what makes consolidating it necessary rather than merely
tidy: the DevServer is to stop reaching for the card through the GPU service at
all, and a question asked in three places moves in three places. So it is asked
here, once, of `GET /system_stats` — which ComfyUI answers whether or not any
model is loaded, and which reports the same number the GPU service did (both
divide the driver's byte count by 1024³: 94.97 for the RTX PRO 6000, measured
2026-09-07).

The unit is GiB. The platform has always written `total_vram_gb` and always
meant GiB, and every threshold in the code (24, 32, 40, 50) is set against that
reading — so the name stays and the docstring says what it is.
"""

import asyncio
import logging
import re
import threading
import time
from typing import NamedTuple, Optional

logger = logging.getLogger(__name__)

# A card is not resized while the server runs, so a reading that succeeded is
# kept for the life of the process. A reading that failed is held for a minute
# only, so that a ComfyUI which comes back is noticed without a restart — the
# same rule both Latent Lab services already applied to their own answers.
_FAILED_HOLD_S = 60.0

# A plain threading lock, not an asyncio one: this module is called from
# several event loops (routes create their own per request), and an asyncio
# primitive built in one loop and awaited in another raises. The section it
# guards assigns two module globals and awaits nothing.
_lock = threading.Lock()
_reading: Optional["Card"] = None
_failed_until: float = 0.0


class Card(NamedTuple):
    """What one reading of /system_stats says about the card."""
    name: str
    total_vram_gb: float


class CardUnreadable(RuntimeError):
    """The card's size could not be established.

    Raised rather than answered with a number, because every caller that gets a
    number acts on it — picks a model, opens or closes an instrument — and a
    guess handed out here is a decision made silently on the caller's behalf.
    """


async def read() -> Card:
    """The card's name and total memory, or raise CardUnreadable.

    Cached: a successful reading for the life of the process, a failure for a
    minute.
    """
    global _reading, _failed_until

    if _reading is not None:
        return _reading
    if time.monotonic() < _failed_until:
        raise CardUnreadable(
            "ComfyUI did not report the card less than a minute ago; "
            "not asking again yet"
        )

    # Asked outside the lock: this lock is module-wide, and an HTTP request held
    # under it would stop every other caller that needs the number.
    try:
        card = await _ask_comfyui()
    except CardUnreadable:
        with _lock:
            if _reading is None:
                _failed_until = time.monotonic() + _FAILED_HOLD_S
        raise

    with _lock:
        if _reading is None:
            _reading = card
            _failed_until = 0.0
            logger.info("[GPU-CARD] ComfyUI reports %s, %.2f GiB",
                        card.name or "an unnamed card", card.total_vram_gb)
        return _reading


async def total_vram_gb() -> float:
    """The card's total memory in GiB, or raise CardUnreadable."""
    return (await read()).total_vram_gb


def read_sync() -> Card:
    """`read()` for a caller that has no event loop — a Flask route.

    Flask serves these on plain threads, so there is no running loop to clash
    with. A caller that DOES have one awaits `read()` instead; calling this
    from inside a loop is an error asyncio itself reports.
    """
    return asyncio.run(read())


# ComfyUI decorates the device name with the index it computes on and the
# allocator it uses, exactly once and in this shape (model_management.py:
# "{} {} : {}".format(device, get_device_name(device), allocator_backend)):
#
#   cuda:0 NVIDIA RTX PRO 6000 Blackwell Workstation Edition : cudaMallocAsync
#
# Neither belongs to the card, and both would have to be carried by every
# reader that compares the name against anything. One decoration, so one
# substitution each — repeating them would eat a second " : " out of a name
# that happened to carry one. The allocator may be empty (ComfyUI writes ""
# when torch will not name it), so the tail is stripped with or without it.
_DEVICE_INDEX = re.compile(r"^\s*cuda:\d+\s+")
_DEVICE_ALLOCATOR = re.compile(r"\s+:\s*\S*\s*$")


def _trim_device_name(raw: str) -> str:
    return _DEVICE_ALLOCATOR.sub("", _DEVICE_INDEX.sub("", str(raw or ""))).strip()


async def _ask_comfyui() -> Card:
    import aiohttp
    from config import COMFYUI_URL

    url = f"{COMFYUI_URL}/system_stats"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                # Connect only. A read limit on a service that answers this
                # endpoint from a busy event loop turns a slow answer into a
                # missing one, and the platform forbids read limits on service
                # calls for exactly that reason.
                timeout=aiohttp.ClientTimeout(sock_connect=10),
            ) as response:
                if response.status != 200:
                    body = (await response.text())[:300]
                    raise CardUnreadable(
                        f"ComfyUI answered /system_stats with HTTP "
                        f"{response.status}: {body}"
                    )
                data = await response.json()
    except CardUnreadable:
        raise
    except Exception as e:
        raise CardUnreadable(f"ComfyUI is not answering {url} ({type(e).__name__}: {e})") from e

    devices = (data or {}).get("devices")
    if not isinstance(devices, list) or not devices:
        raise CardUnreadable(f"ComfyUI named no device in /system_stats: {data!r}"[:400])

    # The first CUDA device, which is the one ComfyUI itself computes on. A
    # machine with two cards would need the whole list; this platform has one,
    # and picking silently among several would be the guess this module exists
    # to avoid.
    total = devices[0].get("vram_total")
    if not isinstance(total, (int, float)) or total <= 0:
        raise CardUnreadable(
            f"ComfyUI reported no usable vram_total: {devices[0]!r}"[:400]
        )
    return Card(name=_trim_device_name(devices[0].get("name")),
                total_vram_gb=float(total) / (1024 ** 3))


def reset_cache() -> None:
    """Forget the reading — for tests, and whenever ComfyUI is restarted.

    Under the lock: a reading already on its way back would otherwise be
    written after this, and the forgotten card would come straight back.

    A restarted ComfyUI is the one way the answer changes while the DevServer
    runs — a different CUDA_VISIBLE_DEVICES, another card. `comfyui_manager`
    calls this when it starts one, which is why the reading is otherwise kept
    for the life of the process rather than re-asked on a timer.
    """
    global _reading, _failed_until
    with _lock:
        _reading = None
        _failed_until = 0.0
