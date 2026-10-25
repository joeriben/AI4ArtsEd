"""Reading the next model off the disk while the card is busy with this one.

Weights go from the file straight onto the card: diffusers maps them
(`low_cpu_mem_usage=True` + safetensors), so there is no CPU copy to prepare.
What CAN be prepared is the kernel's PAGE CACHE, and that costs no VRAM at all.
It runs beside a running generation without taking a byte the card needs -
which is why this exists where speculative VRAM prefetch stays off (see
GPU_ADMISSION_PREFETCH in config.py for the three reasons that one is switched
off; none of them apply here, because nothing is allocated).

WHY THIS IS BUILT AND LEFT UNSTARTED. The premise turned out to be wrong, and
the measurement that made it look right was an error of mine. Fedora machine,
Crucial T700 (PCIe Gen5), 2026-08-26, paired cold runs on the same file:

    mmap page faults in the real load order    2832 MiB/s
    sequential read of the same file, cold     2645 MiB/s

A factor of ONE. An earlier run of this same test reported a factor of fifteen,
and that number was an artifact of the test: it mapped with MADV_RANDOM, which
switches read-ahead off. safetensors maps with MADV_NORMAL and the faults run
FORWARD within each tensor, so fault-around and the read-ahead ramp both apply
and a fault-driven load reaches sequential speed. Of the 111 s cold penalty on
wan2.2, the disk accounts for 12.4 s; the rest is model initialisation, fp8
handling and the transfer to the card.

The cost, by contrast, is real, and it lands at the worst possible moment. The
advice fires within 5 s of a run being admitted - i.e. during that run's own
loading phase - and a concurrent sequential read drops its fault-driven load
from 3324 to 660 MiB/s. Factor 5.03, on exactly the line the waiting person
depends on. Across 607 runs in 9 days, 5 offered an occasion worth warming.

So server.py leaves this out of the service start. What is kept is the
machinery and the measurements: resident_fraction() answers what a file's page
cache actually holds, warm() is the reference implementation for whoever
returns to this on a different disk, and the numbers above save them the
detour. The lever that DOES work already runs: affinity ordering in the
admission gate keeps the model resident - wan2.2 at 132.1 s cold against 21.0 s
warm over 94 runs.

(posix_fadvise(WILLNEED) is no route to this either: 0.1 % resident after 24 s,
because the kernel caps read-ahead. Measured on this platform 2026-08-18.)

TWO TRAPS, both shaping what is below:

  1. `MemAvailable` barely responds to this work at all, and no threshold on
     it changes that. Measured 2026-08-26: reading 33.02 GiB moved
     `MemAvailable` by 0.03 GiB - upward - while 21.6 GiB of OTHER processes'
     page cache was evicted to make the room (`pgsteal_file`), and swap was
     never touched (`pswpout` 0.0 MiB). So the reserve below catches FOREIGN
     pressure of the kind that takes real memory, and the swap check catches a
     machine already short of it. Cache displacement, which is what this work
     actually causes, stays invisible to both - one of the reasons the thread
     stays out of the service start rather than getting a third threshold.
  2. Warming must not evict the cache of the model about to be loaded again.
     What actually protects that is the kernel's own lists - pages read once
     land on the inactive list and go first, while the running model's pages
     are active. The swap check is the backstop for when even that fails.

WHAT STAYS is measured, not assumed: a 2 GiB file came out 100 % resident, a
9.6 GiB one 25.8 %. Every warm therefore reports what it actually kept rather
than what it read.

Nothing here decides against a fixed assumption about this machine: every bound
is read from /proc/meminfo when it is needed. Another deployment has other
numbers, and the RAM recommendation belongs in docs/installation.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_LIBC = None                     # resolved once; see _libc()
# mincore marks a resident page by setting the low bit; the rest is undefined.
# This maps every odd byte to 1 and every even one to 0, so counting is one
# pass in C instead of eight million iterations in Python.
_RESIDENT_TABLE = bytes((1 if i & 1 else 0) for i in range(256))

BLOCK = 8 * 1024 * 1024          # the read size every rate above was measured at
CHECK_EVERY = 32 * BLOCK         # re-read /proc/meminfo every 256 MiB
ALREADY_WARM = 0.90              # resident fraction above which reading is pointless
SWAP_SLACK = 256 * 1024 * 1024   # swap growth beyond this means something is being pushed out
WEIGHT_SUFFIXES = (".safetensors", ".bin", ".gguf", ".pt", ".pth", ".ckpt")


def _meminfo() -> Dict[str, int]:
    """Bytes, keyed as /proc/meminfo names them."""
    out: Dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r") as fh:
            for line in fh:
                name, _, rest = line.partition(":")
                parts = rest.split()
                if parts:
                    out[name] = int(parts[0]) * 1024
    except OSError:
        pass
    return out


def _reserve_bytes(mem: Dict[str, int]) -> int:
    """What has to stay available no matter what this reads.

    A tenth of the machine, and never below 4 GB. Derived here rather than
    configured, because a number written down once is a number about the
    machine it was written on.
    """
    total = mem.get("MemTotal", 0)
    return max(4 * 1024 ** 3, int(total * 0.10))


def _libc():
    """The C library, bound once.

    ctypes.util.find_library("c") runs `/sbin/ldconfig -p` as a SUBPROCESS on
    every call - 1.3 ms and one fork each, which was the entire cost of asking
    about a small file, and eighteen process starts per pass over a nine-shard
    snapshot. Inside a service that holds a CUDA context and 64 request
    threads, that is a bad way to ask a question that has one answer.
    """
    global _LIBC
    if _LIBC is not None:
        return _LIBC if _LIBC is not False else None
    import ctypes
    import ctypes.util
    try:
        name = ctypes.util.find_library("c")
        if not name:
            _LIBC = False
            return None
        libc = ctypes.CDLL(name, use_errno=True)
        libc.mmap.restype = ctypes.c_void_p
        libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.c_int64]
        libc.munmap.restype = ctypes.c_int
        libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        libc.mincore.restype = ctypes.c_int
        libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p]
    except (OSError, AttributeError):
        _LIBC = False
        return None
    _LIBC = libc
    return libc


def resident_fraction(path: Path) -> Optional[float]:
    """How much of this file the kernel already holds, from mincore(2).

    A stopwatch was the obvious way and the wrong one: a file measured at
    2.1 GiB/s here was fully cached, while a fast NVMe reaches that cold. Any
    threshold on a rate is a statement about one machine's disk and would be
    wrong on the next. mincore answers the actual question, page by page.

    The mapping is made through libc rather than Python's mmap, which hands out
    its address only for a writable buffer - and this file is opened read-only
    on purpose. Nothing is read through the mapping; it exists so the kernel
    has an address range to answer about.

    None where the kernel has no answer (another platform, an unreadable file).
    The caller then reads, which is the harmless direction.
    """
    import ctypes
    import ctypes.util
    import mmap as _mmap

    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0:
        return None

    libc = _libc()
    if libc is None:
        return None

    # MAP_SHARED, and the choice is not cosmetic: since the 2019 hardening of
    # mincore (CVE-2019-5489), a PRIVATE file mapping reports only the pages
    # this process has faulted in, so a fully cached file comes back as 0 %.
    # A shared mapping answers about the page cache itself, which is the
    # question. Nothing is written through it - the mapping is read-only.
    PROT_READ, MAP_SHARED, MAP_FAILED = 1, 1, ctypes.c_void_p(-1).value
    page = _mmap.PAGESIZE
    pages = (size + page - 1) // page

    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return None
    addr = None
    try:
        addr = libc.mmap(None, size, PROT_READ, MAP_SHARED, fd, 0)
        if not addr or addr == MAP_FAILED:
            return None
        vec = ctypes.create_string_buffer(pages)
        if libc.mincore(ctypes.c_void_p(addr), ctypes.c_size_t(size), vec) != 0:
            return None
        # Counted through translate/count rather than a Python loop: over a
        # 33 GiB file that is 8.4 million pages, and the loop took 2.39 s per
        # call - inside a service process, twice per file per pass, which
        # pushed the p95 of an unrelated HTTP route from 0.5 to 38 ms.
        return vec.raw[:pages].translate(_RESIDENT_TABLE).count(b"\x01") / pages
    finally:
        if addr and addr != MAP_FAILED:
            libc.munmap(ctypes.c_void_p(addr), size)
        os.close(fd)


def resolve_files(kind: str, model_id: str) -> Tuple[List[Path], str]:
    """The files this lease will read, or nothing plus the reason why not.

    A miss here is harmless - the run simply loads from disk as it always did.
    That is the whole difference to VRAM prefetch, where a wrong guess empties
    the card: reading the wrong bytes costs I/O and nothing else. So this
    resolves what it can resolve with certainty and says so when it cannot,
    rather than guessing at a mapping.
    """
    family = (kind or "").split("-")[0]

    if family == "comfyui":
        # The gate's model_id IS the path below one of the model directories -
        # 'OfficialStableDiffusion/sd15.safetensors', 'Flux1/flux2_dev_fp8mixed
        # .safetensors'. Read off seven days of real leases, not assumed.
        try:
            from config import COMFYUI_MODELS_DIR
        except Exception:
            return [], "no ComfyUI models directory configured"
        # Where ComfyUI actually keeps weights. Looking only in checkpoints/
        # missed the two most used models on this platform: qwen_image_edit
        # (166 runs) and wan2.2 (93) live in diffusion_models/, their text
        # encoders in clip/. Read off the real directory, not assumed.
        roots = [Path(COMFYUI_MODELS_DIR) / d for d in
                 ("checkpoints", "diffusion_models", "unet", "clip", "vae")]
        # Everything that touches the id is inside: it arrives over HTTP, and
        # two shapes were found that get PAST an `except OSError` around the
        # resolve alone - a null byte makes pathlib raise ValueError, and a
        # component over 255 bytes survives resolve() and raises ENAMETOOLONG
        # in is_file(). Both used to leave this function by exception, which
        # the caller then logged once every five seconds.
        outside = False
        try:
            for root_dir in roots:
                if not root_dir.is_dir():
                    continue
                target = (root_dir / model_id).resolve()
                root = root_dir.resolve()
                if root != target and root not in target.parents:
                    # A model id stays inside the directory it names, or it
                    # resolves to nothing. It arrives over HTTP.
                    outside = True
                    continue
                if target.is_file():
                    return [target], ""
        except (OSError, ValueError) as e:
            return [], f"unusable model id ({type(e).__name__})"
        if outside:
            return [], "model id points outside the model directories"
        return [], f"no weights at {model_id}"

    if family in ("diffusers", "text"):
        try:
            from huggingface_hub import snapshot_download
            snapshot = Path(snapshot_download(model_id, local_files_only=True))
        except Exception as e:  # noqa: BLE001 - hub raises several unrelated types
            return [], f"not in the local hub cache ({type(e).__name__})"
        files = [p for p in sorted(snapshot.rglob("*"))
                 if p.suffix in WEIGHT_SUFFIXES and p.is_file()]
        if not files:
            return [], f"no weight files under {snapshot.name}"
        return files, ""

    # llm (GGUF through llama-cpp), voxcpm, trainings: each keeps its weights
    # its own way, and a mapping nobody verified would read the wrong bytes.
    return [], f"no known file mapping for kind '{kind}'"


def warm(paths: List[Path], should_stop=None) -> Dict[str, object]:
    """Read the files into the page cache, and stop early for good reasons.

    A file the kernel already holds is skipped without a read; what remains is
    read in full. Stops on any of: the caller says so, or memory got tight.
    """
    stats: Dict[str, object] = {"bytes": 0, "seconds": 0.0, "files": 0,
                                "skipped": 0, "stopped": "", "already_warm": False,
                                "resident_after": None}
    started = time.perf_counter()
    buf = bytearray(BLOCK)
    view = memoryview(buf)

    for path in paths:
        if should_stop is not None and should_stop():
            stats["stopped"] = "no longer wanted"
            break
        mem = _meminfo()
        reserve = _reserve_bytes(mem)
        swap_free_at_start = mem.get("SwapFree", 0)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if mem.get("MemAvailable", 0) - size < reserve:
            # `continue`, not `break`: one file too large for the moment says
            # nothing about the smaller ones behind it, and a break here meant
            # that a single big entry early in the list cancelled the whole
            # snapshot.
            stats["stopped"] = "not enough memory to spare for one file"
            continue

        held = resident_fraction(path)
        if held is not None and held >= ALREADY_WARM:
            stats["already_warm"] = True
            stats["skipped"] = int(stats["skipped"]) + 1
            continue

        since_check = 0
        try:
            with open(path, "rb", buffering=0) as fh:
                while True:
                    got = fh.readinto(view)
                    if not got:
                        break
                    since_check += got
                    stats["bytes"] = int(stats["bytes"]) + got

                    if since_check >= CHECK_EVERY:
                        since_check = 0
                        if should_stop is not None and should_stop():
                            stats["stopped"] = "no longer wanted"
                            break
                        now_mem = _meminfo()
                        if now_mem.get("MemAvailable", 0) < reserve:
                            stats["stopped"] = "memory got tight"
                            break
                        # The check that actually responds to THIS work: pages
                        # leaving for swap mean something is being displaced.
                        if swap_free_at_start and \
                                now_mem.get("SwapFree", 0) < swap_free_at_start - SWAP_SLACK:
                            stats["stopped"] = "the machine started swapping"
                            break
        except OSError as e:
            logger.info("[PAGE-WARM] %s stopped: %s", path.name, e)
            continue

        if stats["stopped"]:
            break
        stats["files"] = int(stats["files"]) + 1

    stats["seconds"] = round(time.perf_counter() - started, 2)

    # What actually stayed. Reading is one thing and keeping is another: under
    # memory pressure the kernel drops pages behind the reader, and a log line
    # that reports only the bytes read would claim a warm cache that is not
    # there. Measured on this platform 2026-08-26: a 2.6 GiB file read straight
    # through came out at 42.7 % resident.
    if not stats["bytes"]:
        # Nothing was read, so there is nothing to weigh - and the caller is
        # usually here because the waiter just got admitted and is loading.
        # A residency pass over nine shards costs 0.18 s of CPU, and that is
        # the worst moment to spend it.
        return stats

    held_total = held_kept = 0
    for path in paths:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        frac = resident_fraction(path)
        if frac is None:
            continue
        held_total += size
        held_kept += int(size * frac)
    if held_total:
        stats["resident_after"] = round(held_kept / held_total, 3)
    return stats


def _human(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(n) < 1024 or unit == "GiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GiB"


def warm_loop(interval_s: float = 5.0, should_stop=None) -> None:
    """Ask the gate what comes next, and read it off the disk. Quietly.

    Quietly matters: this runs on every service and finds something to do only
    when a queue has formed behind a different model. A line per attempt would
    bury the log, so a model that cannot be resolved says so ONCE and stays
    silent until the reason changes.
    """
    try:
        from services.gpu_admission import get_gpu_admission
        gate = get_gpu_admission()
    except Exception as e:  # noqa: BLE001
        logger.warning("[PAGE-WARM] no gate to ask (%s: %s) - not reading ahead",
                       type(e).__name__, e)
        return

    said: Dict[str, str] = {}
    # Each waiting model is read ONCE for each job that holds the card, and the
    # set is cleared when the card changes hands. A timer was the first shape
    # and the wrong one: a machine under memory pressure keeps only part of
    # what it reads (25.8 % of 9.6 GiB, measured), so the residency check never
    # says "done", and a ten-minute video run had this thread read the same
    # 33 GiB five times over - a few hundred MiB/s of background load on the
    # disk the running job reads from, for as long as it ran.
    warmed_for: Optional[str] = None
    warmed: set = set()

    while not (should_stop is not None and should_stop()):
        time.sleep(interval_s)
        try:
            recommended = gate.page_cache_advice().get("recommended")
            if not recommended:
                continue
            key = str(recommended["affinity_key"])
            active = str(recommended.get("active_id") or "")
            if active != warmed_for:
                warmed_for = active
                warmed = set()
            if key in warmed:
                continue
            # Marked before anything can go wrong with it: an id that cannot be
            # resolved gets one line, not one line every five seconds.
            warmed.add(key)
            files, why = resolve_files(str(recommended["kind"]),
                                       str(recommended["model_id"]))
            if not files:
                if said.get(key) != why:
                    said[key] = why
                    logger.info("[PAGE-WARM] %s stays cold: %s",
                                recommended["model_id"], why)
                continue
            said.pop(key, None)

            if not gate.page_warm_claim(key):
                continue
            try:
                waiting = gate.page_warm_still_wanted
                stats = warm(files, should_stop=lambda: not waiting(key))
            finally:
                gate.page_warm_done(key)

            read = float(stats["bytes"])
            secs = float(stats["seconds"])
            if stats["already_warm"] and not read:
                logger.info("[PAGE-WARM] %s was already in memory (%d file(s))",
                            recommended["model_id"], int(stats["skipped"]))
            elif read:
                rate = read / max(1e-6, secs)
                kept = stats["resident_after"]
                logger.info("[PAGE-WARM] %s: %s in %.1fs (%s/s), %s in memory now%s",
                            recommended["model_id"], _human(read), secs,
                            _human(rate),
                            "share unknown" if kept is None else f"{float(kept) * 100:.0f}%",
                            f" - stopped: {stats['stopped']}" if stats["stopped"] else "")
        except Exception as e:  # noqa: BLE001 - reading ahead must never end the service
            logger.warning("[PAGE-WARM] round failed (%s: %s)", type(e).__name__, e)
        except BaseException as e:
            # Anything that is not an Exception ends this thread for the life
            # of the process. It leaves saying so, rather than falling silent.
            logger.warning("[PAGE-WARM] reader stopping (%s)", type(e).__name__)
            raise


def start_page_cache_warming() -> bool:
    """Start the reader, unless this deployment switched it off."""
    import threading
    try:
        from config import GPU_PAGE_CACHE_WARM
    except Exception:
        GPU_PAGE_CACHE_WARM = True
    if not GPU_PAGE_CACHE_WARM:
        logger.info("[PAGE-WARM] switched off (GPU_PAGE_CACHE_WARM)")
        return False
    threading.Thread(target=warm_loop, name="page-cache-warmer",
                     daemon=True).start()
    logger.info("[PAGE-WARM] reading the next queued model off the disk while "
                "the card works - no VRAM involved")
    return True
