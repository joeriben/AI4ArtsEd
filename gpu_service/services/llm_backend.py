"""
LLM Backend — Local LLM inference via llama-cpp-python (in-process).

Runs small GGUF models (safety, DSGVO, VLM) directly
in the GPU Service process with full VRAM coordinator integration.

NO LONGER THE DEFAULT ENGINE. /api/llm/* is served by supervised llama-server
children (services/llm_child_backend.py) unless LLM_ENGINE=inprocess selects
this one. What runs here shares its process with every content check on the
platform, so a model that aborts on load or crashes on an image takes all of
them with it; that is the whole reason the children exist. What stays here
regardless is the MODEL_CONFIGS registry below, which describes the models
rather than the engine, and which both engines read.

Models:
- qwen3:1.7b — DSGVO verification, text tasks
- llama-guard3:1b — Stage 3 safety (Llama Guard S1-S13)
- qwen3-vl:2b — VLM safety checks (image classification, workshop-validated)
- qwen3-vl:4b — larger VLM for Compare Hub Image Understanding tab
"""

import gc
import logging
import os
import struct
import threading
import time
from typing import Optional, List, Dict, Any

from services.repetition_guard import RepetitionGuard

logger = logging.getLogger(__name__)


def _own_process_vram_mb() -> Optional[float]:
    """This process's GPU memory per NVML, or None. Whole process, not per model."""
    try:
        from services.vram_coordinator import get_vram_coordinator
        return get_vram_coordinator().get_own_process_vram_mb()
    except Exception:
        return None

# Model definitions: alias → config
# MODEL_DIR follows the AI_TOOLS_BASE convention from gpu_service/config.py:
# default is repo-nested (<repo>/llama-server-models), overridable via env.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(
    os.environ.get("AI_TOOLS_BASE", _REPO_ROOT),
    "llama-server-models",
)

# A vision model's image encoder allocates its compute buffer on the FIRST image
# it is given, long after the weights are on the card. Read off the journal on
# 2026-08-29: 4728.07 MiB for the 316-tensor mmproj (the 2B and the 4B) and
# 4769.39 MiB for the 352-tensor one (the 8B and the 32B). The two figures barely
# differ because llama.cpp sizes the buffer from its own warmup encode at
# 1472x1472, and that dominates everything the model's size contributes — so
# this is a flat surcharge, not a fraction of the weights, and one number covers
# all four entries.
#
# It has to be budgeted at load time, because llama.cpp discards the return value
# of ggml_backend_sched_reserve (upstream ggml-org/llama.cpp#23422, fix PR #27855
# unmerged). With no room left for the buffer the reservation fails in silence,
# the context still reports itself ready, and the first encode dereferences a
# null buffer: SIGSEGV, taking down the whole service and every content check
# running in it. Four such crashes stand in the journal. A load refused for want
# of room is recoverable; that segfault is not.
#
# WHAT THIS NUMBER IS, AND WHAT IT IS NOT. It is what the coordinator RESERVES
# before a vision load, so the room is spoken for while the encoder is built. It
# is not a check: an estimate cannot tell anyone whether the buffer was really
# produced. On the child engine that question is answered by the child's own log
# — llama.cpp prints `alloc_compute_meta: ... compute buffer size = N MiB` only
# when the reserve returned a buffer — and a vision child that never printed it
# is killed and refused (services/llm_child.py). In THIS in-process engine no
# such line can be observed, so here the estimate is all there is, which is why
# the eleven crashes happened here and not there.
#
# THE FIGURE. Measured on this platform's card (RTX PRO 6000, llama.cpp 59d8402,
# per-PID nvidia-smi, 2026-09-02), as the growth from a loaded model to one that
# has encoded an image. Three of the four vision entries below were measured —
# qwen3-vl:2b, :8b and :32b, in that order in each row. qwen3-vl:4b was NOT
# measured; it sits between the 2b and the 8b in weights and in projector size,
# and the figure is read as covering it, which is an inference and not a
# measurement:
#
#                    2b     8b     32b
#     1024x1024     +66 /  +74 / +160 MB
#     2048x2048    +488 / +550 / +686 MB
#     4096x3072    +488 / +550 / +686 MB
#     6000x4000    +488 / +550 / +686 MB
#
# It stops growing above 2048x2048 because the image-token count is capped at
# eight batches of n_tokens_batch = 512. 1024 MB therefore covers the largest
# encoder this platform runs, at any image size, with room to spare. The 5000 it
# replaces was a guess made before anything was measured, and it was not a safe
# one: five gigabytes reserved per vision load is five gigabytes of evictions
# that never needed to happen.
VLM_VISION_COMPUTE_MB = 1024


def _builds_vision_handler(config: Dict[str, Any]) -> bool:
    """True exactly when loading this config constructs an image encoder.

    One helper for three decisions that must never drift apart: whether the
    surcharge above is added, whether the warmup below runs, and whether
    _load_model_locked builds a chat handler at all. Asking for an mmproj_path
    instead would charge a future entry that carries one with some other handler
    for a tower it never builds — and a tower built under a handler this
    function did not recognise would go unbudgeted, which is the crash.
    """
    return config.get("chat_handler") == "qwen25vl"


def _sensor_can_read_the_card(coordinator: Any) -> bool:
    """True when the coordinator's free-VRAM figure rests on a sensor at all.

    Weaker than the coordinator's has_authoritative_reading(), and the two are
    kept apart on purpose. A text model refused on a free reading of 0 — which
    is what get_free_vram_mb() returns when neither NVML nor torch answers —
    would stop every content check on the platform without a shortfall
    existing, so a text load goes ahead when nothing can read the card. A
    vision load does the opposite: see _load_model_locked.
    """
    try:
        if coordinator.has_authoritative_reading():
            return True
    except Exception:
        pass
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


class ModelLoadRefused(RuntimeError):
    """A model could not be loaded, and the message says why.

    Distinct from an inference error: nothing was generated, nothing was on the
    card, and the cause — no room, no file, a failed warmup — is already known
    here. Callers that turn this into an HTTP answer send 503 rather than 500,
    because the request was never begun.
    """


# ── Context window and VRAM budget, read from the model file ────────────
#
# A context window is a property of the weights. Written into this table it
# becomes a property of this table, and a model that answers nothing because
# 4096 stood in its line reports a limit of the platform as a limit of the
# model. On a platform built for research that is a falsified reading, not a
# configuration detail. The system-prompt comparison once returned nothing for
# a preset of 5,500 tokens: eleven entries stood at 4096 while their own files
# declare between 8,192 and 393,216.
#
# So `n_ctx` is None below and filled from the file, and the room it costs is
# computed from the same file rather than estimated by hand — the coordinator
# is only ever right about memory it was told about. A model whose
# full window the card cannot serve is refused with the figure in the reason;
# a model nobody wants to pay that for leaves the table, as Phi 3.5 Mini did
# (48 GB of cache for 3.8B of weights, having no grouped-query
# attention). Neither is a window that got quietly made smaller.
#
# The `estimated_vram_mb` written into the entries below is what the installer
# has to go on BEFORE a download. From the first resolve onward the computed
# figure stands in its place, and that is the one the coordinator is given.

_GGUF_TYPE_SIZE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_GGUF_STRUCT = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?",
                10: "Q", 11: "q", 12: "d"}
_GGUF_WANTED = (".context_length", ".block_count", ".attention.head_count_kv",
                ".attention.head_count", ".embedding_length", ".attention.key_length",
                ".attention.value_length", ".attention.sliding_window",
                ".attention.sliding_window_pattern")
_gguf_cache: Dict[str, Dict[str, Any]] = {}
_resolve_lock = threading.Lock()

# Which layers of an architecture hold a full-length cache when the file
# declares a sliding window. llama.cpp fixes this per architecture in code, not
# in the file: `hparams.set_swa_pattern(n)` marks every layer but each n-th as
# sliding (llama.cpp, src/llama-model.cpp). Reading the window out of the file
# and then charging every layer for it over-reserves by an order of magnitude —
# Gemma 3 declares 1024 against a context of 131072 — and an over-reservation
# is not harmless here: it drives the coordinator through its eviction chain
# and asks ComfyUI to drop a checkpoint for room nobody needs.
# A file that declares the period itself (attention.sliding_window_pattern) is
# read; this table covers the architectures that leave it out. One that
# declares a sliding window and appears in neither is charged in full: too much
# room is a wasted grant, too little is the OOM this service already knows.
_SWA_PATTERN = {"gemma3": 6}

# llama.cpp pads the sliding cache to a multiple of 256 and holds one micro
# batch beyond the window itself (src/llama-kv-cache-iswa.cpp). The micro batch
# is the one the child is spawned with, taken from there rather than copied.
_SWA_PAD = 256
from services.llm_child import UBATCH_SIZE as _UBATCH  # noqa: E402


def _gguf_metadata(path: str) -> Dict[str, Any]:
    """The architecture numbers this service needs, read from the GGUF file.

    Only the header is walked, and every value that is not wanted is skipped by
    seeking past it. Cached per path, size and mtime: a re-downloaded file is a
    different file and is read again.
    """
    stat = os.stat(path)
    key = f"{path}:{stat.st_mtime_ns}:{stat.st_size}"
    hit = _gguf_cache.get(key)
    if hit is not None:
        return hit

    def _u(f, fmt, size):
        return struct.unpack("<" + fmt, f.read(size))[0]

    def _string(f):
        return f.read(_u(f, "Q", 8)).decode("utf-8", "replace")

    def _skip(f, vtype):
        if vtype == 8:                      # string
            f.seek(_u(f, "Q", 8), 1)
        elif vtype == 9:                    # array
            etype = _u(f, "I", 4)
            count = _u(f, "Q", 8)
            if etype == 8:
                for _ in range(count):
                    f.seek(_u(f, "Q", 8), 1)
            elif etype == 9:
                for _ in range(count):
                    _skip(f, 9)
            else:
                f.seek(_GGUF_TYPE_SIZE[etype] * count, 1)
        else:
            f.seek(_GGUF_TYPE_SIZE[vtype], 1)

    def _read(f, vtype):
        """A wanted value. An array of numbers comes back as its largest entry.

        A per-layer array is a real shape for head_count_kv — llama.cpp asks
        n_embd_k_gqa(i) layer by layer. The largest entry is what a layer can
        cost, so budgeting every layer at it is the safe reading of the file.
        """
        if vtype == 8:
            return _string(f)
        if vtype == 9:
            etype = _u(f, "I", 4)
            count = _u(f, "Q", 8)
            if etype in (8, 9):
                f.seek(-12, 1)
                _skip(f, 9)
                return None
            values = [_u(f, _GGUF_STRUCT[etype], _GGUF_TYPE_SIZE[etype])
                      for _ in range(count)]
            return max(values) if values else None
        value = _u(f, _GGUF_STRUCT[vtype], _GGUF_TYPE_SIZE[vtype])
        # A bool is an int to Python, and `int(True)` is 1: a file that wrote a
        # window as type 7 would spawn a child with a window of one token.
        return None if vtype == 7 else value

    raw: Dict[str, Any] = {}
    architecture = None
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError(f"not a GGUF file: {path}")
        version = _u(f, "I", 4)
        if version < 2 or version > 0xFFFF:
            # v1 wrote its lengths as u32, and a version that large is a file
            # written the other way round. Nothing here ships either, and
            # guessing at one is worse than saying so.
            raise ValueError(f"GGUF version {version} is not read here: {path}")
        _u(f, "Q", 8)                       # tensor count
        for _ in range(_u(f, "Q", 8)):      # key/value count
            name = _string(f)
            vtype = _u(f, "I", 4)
            if vtype != 9 and vtype not in _GGUF_TYPE_SIZE and vtype != 8:
                raise ValueError(f"{os.path.basename(path)} uses value type "
                                 f"{vtype}, which this reader does not know")
            if name == "general.architecture":
                architecture = _read(f, vtype)
            elif name.endswith(_GGUF_WANTED):
                value = _read(f, vtype)
                if isinstance(value, int):
                    raw[name] = value
            else:
                _skip(f, vtype)

    # The keys are prefixed with the architecture, and an architecture name may
    # carry a dot of its own ("qwen3.5"), so the prefix is stripped by name and
    # not at the first dot.
    out: Dict[str, Any] = {"architecture": architecture}
    prefix = f"{architecture}." if architecture else ""
    for name, value in raw.items():
        out[name[len(prefix):] if prefix and name.startswith(prefix) else name] = value

    # llama.cpp reads head_count_kv as optional and falls back to head_count —
    # a multi-head model that leaves it out is a valid file, and refusing it
    # would take a model off the platform over a key it never had to write.
    if "attention.head_count_kv" not in out and "attention.head_count" in out:
        out["attention.head_count_kv"] = out["attention.head_count"]

    missing = [k for k in ("context_length", "block_count", "attention.head_count_kv",
                           "attention.head_count", "embedding_length") if k not in out]
    if missing:
        raise ValueError(f"{os.path.basename(path)} declares no {', '.join(missing)}")
    _gguf_cache[key] = out
    return out


def kv_cache_mb(path: str, n_ctx: int) -> float:
    """What a KV cache of n_ctx tokens costs this model, in MB.

    Key and value are charged at the head sizes the FILE declares. Deriving
    them as embedding_length / head_count is only right where the file leaves
    them out: Qwen 3.5 4B declares 256 where that division gives 160, and the
    budget was 12 GB short on exactly that difference.

    An UPPER bound, and a loose one. Measured on 2026-09-09: Qwen 3.5 9B at its
    full 262144-token window holds 14.5 GB in total, of which about 9 GB is
    cache, where this returns 32 GB. What llama.cpp allocates for a served
    context is smaller than the arithmetic of layers x heads x window, and by
    how much has not been read off this build yet. The child engine does not
    rest on this figure — it asks the coordinator for load_floor_mb and lets
    --fit size the rest — so the bound is used where erring high is harmless:
    the in-process engine, which must name a window at load, and the listing
    a download decision is made from.
    """
    m = _gguf_metadata(path)
    fallback = m["embedding_length"] // m["attention.head_count"]
    k_dim = m.get("attention.key_length", fallback)
    v_dim = m.get("attention.value_length", fallback)
    kv_heads = m["attention.head_count_kv"]
    layers = m["block_count"]
    per_token_per_layer = kv_heads * (k_dim + v_dim) * 2      # f16, llama.cpp default

    swa = m.get("attention.sliding_window")
    pattern = (m.get("attention.sliding_window_pattern")
               or _SWA_PATTERN.get(m.get("architecture") or ""))
    if swa and swa < n_ctx and pattern:
        sliding_len = min(n_ctx, swa + _UBATCH)
        sliding_len = -(-sliding_len // _SWA_PAD) * _SWA_PAD
        full_layers = layers // pattern
        tokens = full_layers * n_ctx + (layers - full_layers) * sliding_len
    else:
        tokens = layers * n_ctx
    return tokens * per_token_per_layer / (1024 * 1024)


def compute_buffer_mb(path: str, n_ctx: int) -> float:
    """Room for llama.cpp's compute buffers, on top of weights and cache.

    With flash attention the attention scores never land in memory as a whole
    and a flat allowance covers what is left. Without it llama.cpp materialises
    [n_kv x n_ubatch x n_head] in f32, which at a 131k window is gigabytes, and
    a flat allowance is the case this file's own segfault comment describes.
    The child engine spawns with `-fa auto`; the in-process engine builds its
    Llama without flash attention, so it pays for the scores.
    """
    flat = 512.0
    if os.environ.get("LLM_ENGINE", "child").strip().lower() != "inprocess":
        return flat
    m = _gguf_metadata(path)
    scores = n_ctx * _UBATCH * m["attention.head_count"] * 4 / (1024 * 1024)
    return flat + scores


def resolve_window(alias: str) -> None:
    """Fill in n_ctx and estimated_vram_mb for one model, from its own file.

    Idempotent per file: a model whose GGUF is replaced is read again, and a
    model that is not on disk yet keeps its None until the load that follows
    its download.
    """
    config = MODEL_CONFIGS.get(alias)
    if not config:
        return
    path = config["model_path"]
    try:
        stat = os.stat(path)
    except OSError:
        return
    stamp = f"{stat.st_mtime_ns}:{stat.st_size}"
    if config.get("_window_from") == stamp or config.get("_window_failed_from") == stamp:
        return
    try:
        n_ctx = int(_gguf_metadata(path)["context_length"])
        # A vision model's projector is a second file, and it goes on the card
        # with the weights: llama.cpp offloads the mmproj unless it is told not
        # to, and this service never tells it not to.
        weights_mb = stat.st_size / (1024 * 1024)
        mmproj = config.get("mmproj_path")
        if mmproj and os.path.exists(mmproj):
            weights_mb += os.path.getsize(mmproj) / (1024 * 1024)
        budget = weights_mb + kv_cache_mb(path, n_ctx) + compute_buffer_mb(path, n_ctx)
    except Exception as e:  # noqa: BLE001
        if config.get("_window_failed_from") != stamp:
            config["_window_failed_from"] = stamp
            logger.error("[LLM] %s declares no readable window (%s) — it stays "
                         "unresolved and a load of it will say so", alias, e)
        return
    with _resolve_lock:
        # The budget is published BEFORE the window, and the window is what the
        # early return above tests. The other order lets a second thread see a
        # resolved model and read the budget that belongs to the old window.
        config["estimated_vram_mb"] = int(round(budget))
        config["n_ctx"] = n_ctx
        config["_window_from"] = stamp
    logger.info("[LLM] %s: window %d tokens from its own file, %d MB budgeted",
                alias, n_ctx, config["estimated_vram_mb"])


# llama.cpp will not size a fitted context below this (--fit-ctx default).
FIT_MIN_CTX = 4096


def load_floor_mb(config: Dict[str, Any]) -> Optional[float]:
    """The least room a child needs: weights, projector, buffers, smallest cache.

    The child engine spawns with `--fit on` and no `-c`, so llama.cpp takes the
    model's own window and shrinks the cache it allocates to what the device
    can give, never below --fit-ctx. What the coordinator has to guarantee is
    therefore this floor and not the whole window; the room the child actually
    took is re-read from NVML once it stands.
    """
    path = config.get("model_path", "")
    if not path or not os.path.exists(path):
        return None
    try:
        weights_mb = os.path.getsize(path) / (1024 * 1024)
        mmproj = config.get("mmproj_path")
        if mmproj and os.path.exists(mmproj):
            weights_mb += os.path.getsize(mmproj) / (1024 * 1024)
        return (weights_mb + kv_cache_mb(path, FIT_MIN_CTX)
                + compute_buffer_mb(path, FIT_MIN_CTX))
    except Exception:  # noqa: BLE001
        return None


def _budget_breakdown(config: Dict[str, Any], estimated_mb: float) -> str:
    """What the refused number is made of, for the sentence that reports it.

    Weights, cache and buffer are three different reasons to need room and lead
    to three different answers; one figure called "weights" for all of them
    sent the reader after the wrong thing.
    """
    path = config.get("model_path", "")
    n_ctx = config.get("n_ctx")
    try:
        weights_mb = os.path.getsize(path) / (1024 * 1024)
        mmproj = config.get("mmproj_path")
        if mmproj and os.path.exists(mmproj):
            weights_mb += os.path.getsize(mmproj) / (1024 * 1024)
        cache_mb = kv_cache_mb(path, int(n_ctx))
        buffer_mb = compute_buffer_mb(path, int(n_ctx))
    except Exception:  # noqa: BLE001
        return f"{estimated_mb:.0f}MB, not broken down"
    parts = [f"{weights_mb:.0f}MB weights",
             f"{cache_mb:.0f}MB cache for {int(n_ctx)} tokens",
             f"{buffer_mb:.0f}MB compute buffers"]
    vision_mb = estimated_mb - (weights_mb + cache_mb + buffer_mb)
    if vision_mb > 1:
        parts.append(f"{vision_mb:.0f}MB vision compute buffer")
    return " + ".join(parts)


def resolve_all_windows() -> None:
    """Resolve every entry whose file is already on disk."""
    for alias in MODEL_CONFIGS:
        resolve_window(alias)


MODEL_CONFIGS = {
    # ── Chat-capable models (appear in Compare Hub) ──────────────────────
    "qwen3:1.7b": {
        "model_path": os.path.join(MODEL_DIR, "Qwen3-1.7B-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 2000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Qwen 3 1.7B",
        "hf_repo_id": "Qwen/Qwen3-1.7B-GGUF",
        "hf_filename": "Qwen3-1.7B-Q8_0.gguf",
        "approx_download_mb": 1749,
    },
    "qwen3:4b": {
        "model_path": os.path.join(MODEL_DIR, "Qwen3-4B-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 4500,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Qwen 3 4B",
        "hf_repo_id": "Qwen/Qwen3-4B-GGUF",
        "hf_filename": "Qwen3-4B-Q8_0.gguf",
        "approx_download_mb": 4082,
    },
    "gemma-3-4b": {
        "model_path": os.path.join(MODEL_DIR, "gemma-3-4b-it-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 5000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Gemma 3 4B",
        "hf_repo_id": "unsloth/gemma-3-4b-it-GGUF",
        "hf_filename": "gemma-3-4b-it-Q8_0.gguf",
        "approx_download_mb": 3939,
    },
    "smollm3:3b": {
        "model_path": os.path.join(MODEL_DIR, "SmolLM3-3B-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 3500,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "SmolLM 3 3B",
        "hf_repo_id": "ggml-org/SmolLM3-3B-GGUF",
        "hf_filename": "SmolLM3-Q8_0.gguf",
        "approx_download_mb": 3280,
    },
    "qwen3.5:4b": {
        "model_path": os.path.join(MODEL_DIR, "Qwen3.5-4B-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 4800,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Qwen 3.5 4B",
        "hf_repo_id": "bartowski/Qwen_Qwen3.5-4B-GGUF",
        "hf_filename": "Qwen_Qwen3.5-4B-Q8_0.gguf",
        "approx_download_mb": 4490,
    },
    "llama3.2:3b": {
        "model_path": os.path.join(MODEL_DIR, "Llama-3.2-3B-Instruct-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 3800,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Llama 3.2 3B",
        "hf_repo_id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "hf_filename": "Llama-3.2-3B-Instruct-Q8_0.gguf",
        "approx_download_mb": 3422,
    },
    "ministral3:3b": {
        "model_path": os.path.join(MODEL_DIR, "Ministral-3-3B-Instruct-2512-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 4000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Ministral 3 3B",
        "hf_repo_id": "mistralai/Ministral-3-3B-Instruct-2512-GGUF",
        "hf_filename": "Ministral-3-3B-Instruct-2512-Q8_0.gguf",
        "approx_download_mb": 3652,
    },
    "eurollm:1.7b": {
        "model_path": os.path.join(MODEL_DIR, "EuroLLM-1.7B-Instruct-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 2000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "EuroLLM 1.7B",
        "hf_repo_id": "QuantFactory/EuroLLM-1.7B-Instruct-GGUF",
        "hf_filename": "EuroLLM-1.7B-Instruct.Q8_0.gguf",
        "approx_download_mb": 1764,
    },
    "granite3.1:2b": {
        "model_path": os.path.join(MODEL_DIR, "granite-3.1-2b-instruct-Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 3000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Granite 3.1 2B",
        "hf_repo_id": "lmstudio-community/granite-3.1-2b-instruct-GGUF",
        "hf_filename": "granite-3.1-2b-instruct-Q8_0.gguf",
        "approx_download_mb": 2694,
    },
    # ── Utility models (safety, VLM — not for Compare Hub) ──────────────
    "llama-guard3:1b": {
        "model_path": os.path.join(MODEL_DIR, "Llama-Guard-3-1B.Q8_0.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 1800,
        "chat_handler": None,
        "chat_capable": False,
        "display_name": "Llama Guard 3 1B",
        "hf_repo_id": "QuantFactory/Llama-Guard-3-1B-GGUF",
        "hf_filename": "Llama-Guard-3-1B.Q8_0.gguf",
        "approx_download_mb": 1526,
    },
    # REASONING. This model's GGUF chat template asks for `enable_thinking` and
    # treats it as false when nothing sets it, which is why the in-process
    # engine — which passed nothing — never saw a thought from it. The child
    # engine sets it: the spawn line carries `--reasoning on`, so every template
    # that supports thinking does it, and `--reasoning-format none` leaves the
    # block in `content` where the platform's own </think> partition finds it.
    # A deliberate choice for the roles this alias carries (interception, the
    # safety readings, persona), not a default anybody inherited.
    "qwen3.5:9b": {
        "model_path": os.path.join(MODEL_DIR, "Qwen3.5-9B-Q4_K_M.gguf"),
        # The pipeline roles (interception, safety, persona) carry long
        # instructions; at 4096, where this table put every model until
        # 2026-09-09, a reading frame already ran out.
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 9000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Qwen 3.5 9B",
        "hf_repo_id": "unsloth/Qwen3.5-9B-GGUF",
        "hf_filename": "Qwen3.5-9B-Q4_K_M.gguf",
        "approx_download_mb": 5680,
    },
    "qwen3.5:27b": {
        "model_path": os.path.join(MODEL_DIR, "Qwen3.5-27B-Q4_K_M.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 21000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Qwen 3.5 27B",
        "hf_repo_id": "unsloth/Qwen3.5-27B-GGUF",
        "hf_filename": "Qwen3.5-27B-Q4_K_M.gguf",
        "approx_download_mb": 16740,
    },
    "devstral:24b": {
        "model_path": os.path.join(MODEL_DIR, "Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 18000,
        "chat_handler": None,
        "chat_capable": True,
        "display_name": "Devstral Small 2 24B",
        "hf_repo_id": "unsloth/Devstral-Small-2-24B-Instruct-2512-GGUF",
        "hf_filename": "Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf",
        "approx_download_mb": 14330,
    },
    "qwen3-vl:2b": {
        "model_path": os.path.join(MODEL_DIR, "qwen3-vl-2b", "Qwen3-VL-2B-Instruct-Q4_K_M.gguf"),
        "mmproj_path": os.path.join(MODEL_DIR, "qwen3-vl-2b", "mmproj-F16.gguf"),
        # A reading frame is a long instruction — the structural one is ~1200
        # tokens — and it arrives together with an image's tokens. At 4096
        # llama_decode returned 1 and the reading failed outright (measured
        # 2026-08-12).
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 3600,
        "chat_handler": "qwen25vl",  # Qwen25VLChatHandler works for qwen3-vl too
        "chat_capable": False,
        "vlm_capable": True,
        "display_name": "Qwen 3 VL 2B",
        "hf_repo_id": "unsloth/Qwen3-VL-2B-Instruct-GGUF",
        "hf_filename": "Qwen3-VL-2B-Instruct-Q4_K_M.gguf",
        "hf_mmproj_filename": "mmproj-F16.gguf",
        "approx_download_mb": 1837,  # 1056 + 781
    },
    # The platform's one safety classifier: text, image, and text with image.
    # It answers a single yes/no question about a document, against a policy
    # given as plain language in the same request, and the score is read off
    # the yes/no logits of the first generated token (services/llm_child_backend
    # .classify). One model where there were three -- a text guard that had to
    # have its input cut into 2400-byte windows, a describer whose verdict was
    # spoken by a cloud model, and a general model on the name question.
    #
    # Converted from mistralai/Shieldstral-1.0-3B with the pinned llama.cpp
    # clone: Q8_0 weights and an F16 projector, because a guard that reads a
    # child's picture is the last place to save a gigabyte on.
    "shieldstral:3b": {
        "model_path": os.path.join(MODEL_DIR, "shieldstral-3b", "Shieldstral-1.0-3B-Q8_0.gguf"),
        "mmproj_path": os.path.join(MODEL_DIR, "shieldstral-3b", "mmproj-F16.gguf"),
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 9100,
        "chat_handler": None,
        "chat_capable": False,
        "vlm_capable": True,
        "classifier": True,
        "display_name": "Shieldstral 1.0 3B",
        "hf_repo_id": "mistralai/Shieldstral-1.0-3B",
        "hf_filename": "Shieldstral-1.0-3B-Q8_0.gguf",
        "hf_mmproj_filename": "mmproj-F16.gguf",
        "approx_download_mb": 4283,  # 3483 + 800
    },
    "qwen3-vl:4b": {
        "model_path": os.path.join(MODEL_DIR, "qwen3-vl-4b", "Qwen3-VL-4B-Instruct-Q4_K_M.gguf"),
        "mmproj_path": os.path.join(MODEL_DIR, "qwen3-vl-4b", "mmproj-F16.gguf"),
        # A reading frame is a long instruction — the structural one is ~1200
        # tokens — and it arrives together with an image's tokens. At 4096
        # llama_decode returned 1 and the reading failed outright (measured
        # 2026-08-12).
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 5800,
        "chat_handler": "qwen25vl",  # Qwen25VLChatHandler works for qwen3-vl
        "chat_capable": False,
        "vlm_capable": True,
        "display_name": "Qwen 3 VL 4B",
        "hf_repo_id": "unsloth/Qwen3-VL-4B-Instruct-GGUF",
        "hf_filename": "Qwen3-VL-4B-Instruct-Q4_K_M.gguf",
        "hf_mmproj_filename": "mmproj-F16.gguf",
        "approx_download_mb": 3178,  # 2381 + 797
    },
    "qwen3-vl:8b": {
        "model_path": os.path.join(MODEL_DIR, "qwen3-vl-8b", "Qwen3-VL-8B-Instruct-Q4_K_M.gguf"),
        "mmproj_path": os.path.join(MODEL_DIR, "qwen3-vl-8b", "mmproj-F16.gguf"),
        # Same reason as the two smaller ones: a reading frame is a long
        # instruction and arrives together with an image's tokens.
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        "estimated_vram_mb": 8500,
        "chat_handler": "qwen25vl",  # Qwen25VLChatHandler works for qwen3-vl
        "chat_capable": False,
        "vlm_capable": True,
        "display_name": "Qwen 3 VL 8B",
        "hf_repo_id": "unsloth/Qwen3-VL-8B-Instruct-GGUF",
        "hf_filename": "Qwen3-VL-8B-Instruct-Q4_K_M.gguf",
        "hf_mmproj_filename": "mmproj-F16.gguf",
        "approx_download_mb": 5900,  # 4795 + 1105
    },
    "qwen3-vl:32b": {
        "model_path": os.path.join(MODEL_DIR, "qwen3-vl-32b", "Qwen3-VL-32B-Instruct-Q4_K_M.gguf"),
        "mmproj_path": os.path.join(MODEL_DIR, "qwen3-vl-32b", "mmproj-F16.gguf"),
        # Same reason as the smaller ones: a reading frame is a long instruction
        # and arrives together with an image's tokens.
        "n_ctx": None,  # from the file; see resolve_window
        "n_gpu_layers": -1,
        # Weights are 19.8 GB; the cache and the working memory come on top,
        # both computed from the file.
        "estimated_vram_mb": 26000,
        "chat_handler": "qwen25vl",  # Qwen25VLChatHandler works for qwen3-vl
        "chat_capable": False,
        "vlm_capable": True,
        "display_name": "Qwen 3 VL 32B",
        "hf_repo_id": "unsloth/Qwen3-VL-32B-Instruct-GGUF",
        "hf_filename": "Qwen3-VL-32B-Instruct-Q4_K_M.gguf",
        "hf_mmproj_filename": "mmproj-F16.gguf",
        "approx_download_mb": 20960,  # 19760 + 1200
    },
}

# Aliases for backward compatibility with legacy model names
MODEL_ALIASES = {
    "llama-guard3:latest": "llama-guard3:1b",
}

# Read once at import for every model already on disk. A model the installer
# fetches later is resolved by the load that follows its download.
resolve_all_windows()


class LLMBackend:
    """
    In-process LLM inference with VRAM coordinator integration.

    Each model is a separate llama_cpp.Llama instance.
    Models are loaded lazily on first use.
    """

    def __init__(self):
        self._models: Dict[str, Any] = {}  # alias → Llama instance
        self._model_vram_mb: Dict[str, float] = {}
        self._model_last_used: Dict[str, float] = {}
        self._model_in_use: Dict[str, int] = {}
        # A VLM's vision tower lives in a context the chat handler owns, not the
        # Llama. Keeping the handler is what makes that context releasable; see
        # _unload_model.
        self._model_handlers: Dict[str, Any] = {}
        self._load_lock = threading.Lock()
        # Per-alias inference lock: llama_cpp.Llama is NOT reentrant per instance.
        # Concurrent create_chat_completion / create_completion on the same Llama
        # corrupts CUDA / KV-cache state and segfaults the whole process.
        self._inference_locks: Dict[str, threading.Lock] = {}
        self._inference_locks_guard = threading.Lock()

        self._register_with_coordinator()
        logger.info("[LLM] Initialized: in-process llama-cpp-python backend")

    def _get_inference_lock(self, alias: str) -> threading.Lock:
        """Lazily create and return a per-alias inference lock."""
        lock = self._inference_locks.get(alias)
        if lock is not None:
            return lock
        with self._inference_locks_guard:
            lock = self._inference_locks.get(alias)
            if lock is None:
                lock = threading.Lock()
                self._inference_locks[alias] = lock
            return lock

    def _register_with_coordinator(self):
        """Register with VRAM coordinator for cross-backend eviction."""
        try:
            from services.vram_coordinator import get_vram_coordinator
            coordinator = get_vram_coordinator()
            coordinator.register_backend(self)
            logger.info("[LLM] Registered with VRAM coordinator")
        except Exception as e:
            logger.warning(f"[LLM] Failed to register with VRAM coordinator: {e}")

    # =========================================================================
    # VRAMBackend Protocol Implementation
    # =========================================================================

    def get_backend_id(self) -> str:
        return "llm"

    def get_registered_models(self) -> List[Dict[str, Any]]:
        from services.vram_coordinator import EvictionPriority
        return [
            {
                "model_id": mid,
                "vram_mb": self._model_vram_mb.get(mid, 0),
                "priority": EvictionPriority.LOW,  # LLMs are cheap to reload
                "last_used": self._model_last_used.get(mid, 0),
                "in_use": self._model_in_use.get(mid, 0),
            }
            for mid in list(self._models)  # an unload must not break the iteration
        ]

    def evict_model(self, model_id: str) -> bool:
        """Evict a specific model (called by coordinator)."""
        return self._unload_model(model_id)

    # =========================================================================
    # Model Loading / Unloading
    # =========================================================================

    def _resolve_alias(self, model: str) -> str:
        """Resolve model alias to canonical name."""
        model = model.replace("local/", "") if model.startswith("local/") else model
        return MODEL_ALIASES.get(model, model)

    def _load_model(self, model_alias: str) -> tuple:
        """Load a model into GPU memory. Returns (ok, reason).

        reason is None on success and a sentence on every failure path. It
        travels back with the call instead of being deposited in shared state:
        two threads loading two aliases would otherwise read each other's
        failure, and a reason left lying around outlives the attempt that
        produced it.
        """
        from llama_cpp import Llama

        config = MODEL_CONFIGS.get(model_alias)
        if not config:
            logger.error(f"[LLM] Unknown model: {model_alias}")
            return False, f"unknown model {model_alias}"

        if not os.path.exists(config["model_path"]):
            logger.error(f"[LLM] Model file not found: {config['model_path']}")
            return False, f"model file not found: {config['model_path']}"

        # A model downloaded — or replaced — after this module was imported is
        # resolved here.
        resolve_window(model_alias)
        if config.get("n_ctx") is None:
            reason = (f"{model_alias} was not loaded: its file declares no context "
                      f"length, and this service does not invent one")
            logger.error(f"[LLM] {reason}")
            return False, reason

        with self._load_lock:
            if model_alias in self._models:
                return True, None  # Already loaded

            # Request VRAM from coordinator. estimated_vram_mb budgets the
            # weights and the KV cache; a vision model needs room for its image
            # encoder's compute buffer on top, and a card that fits the weights
            # and nothing else is exactly where the segfault above happened.
            estimated_mb = config["estimated_vram_mb"]
            if _builds_vision_handler(config):
                estimated_mb += VLM_VISION_COMPUTE_MB

            # Loading a checking model is a large allocation like any other — up
            # to 26 GB — and doing it next to a 30 GB image model is exactly how
            # the card ran dry. So take the plant-wide slot for the load. But
            # only briefly: this model is what checks what children see, and it
            # must never wait out a video render. If the slot is not free within
            # a few seconds, the load goes ahead unserialized, as it always did,
            # and says so.
            import contextlib
            try:
                # Outside the inner try: if this import ever fails, GpuBusy in
                # the except clause below would be an unbound name — the same
                # class of error this file already produced once.
                from services.gpu_admission import get_gpu_admission, GpuBusy
                from services.vram_coordinator import EvictionPriority as _EP
            except Exception as e:
                logger.warning(f"[LLM] Could not consult the GPU gate: {e}")
                return self._load_model_locked(model_alias, config, estimated_mb)
            with contextlib.ExitStack() as _gate:
                _gate_lease = None
                try:
                    _gate_lease = _gate.enter_context(get_gpu_admission().slot(
                        "llm-load", model_alias, 0, _EP.NORMAL, timeout_s=5.0))
                except GpuBusy:
                    logger.warning("[LLM] Loading %s without the GPU slot — the card is "
                                   "busy and a content check must not queue behind a render",
                                   model_alias)
                except Exception as e:
                    logger.warning(f"[LLM] Could not consult the GPU gate: {e}")

                ok, reason = self._load_model_locked(model_alias, config, estimated_mb)
                if not ok and _gate_lease is not None:
                    # _load_model_locked reports failure by returning False —
                    # the slot never sees an exception, and an unmarked failed
                    # load entered the llm-load bucket as a valid duration.
                    _gate_lease.failed = True
                return ok, reason

    def _load_model_locked(self, model_alias: str, config: dict, estimated_mb: float) -> tuple:
        """The load itself, with _load_lock already held by _load_model.

        Returns (ok, reason), reason None only on success.

        A vision model and a text model are answered differently when the
        coordinator does not deliver, and the asymmetry is the whole point.

        A VISION model is loaded only against a reading that can see the other
        processes on the card. Without NVML, get_free_vram_mb() is this
        process's own torch figure: it does not see ComfyUI, so a grant given
        against it says nothing about the room that will be there when the image
        encoder asks for its buffer. llama.cpp does not report that failed
        reservation, and the first encode dereferences a null buffer — SIGSEGV,
        taking every content check in the process with it. So a missing sensor,
        a refusal, or a coordinator that cannot be consulted at all each end the
        load here. A refused check is recoverable; that crash is not. The warmup
        below therefore only ever runs where both the sensor and the grant said
        yes.

        A TEXT model keeps the older behaviour, because the failure it risks is
        an ordinary allocation error the process survives. A refusal from a
        coordinator that can still read the card is a measurement and is
        honoured. An exception, or a refusal from a coordinator whose sensors
        are all gone, says nothing about the card — free VRAM reads as 0 there
        and every request would be refused — so the load proceeds as it always
        did and says so, rather than letting a fault in the measuring apparatus
        stop the platform.
        """
        from llama_cpp import Llama

        builds_vision = _builds_vision_handler(config)

        def _blind_refusal(detail: str) -> str:
            return (
                f"{model_alias} carries an image encoder and free VRAM cannot be "
                f"verified against the other processes on this card ({detail}). "
                f"Loading it blind would risk the encoder finding no room for its "
                f"compute buffer, which llama.cpp does not report and this service "
                f"does not survive, so the load is refused instead."
            )

        coordinator = None
        reservation = None
        try:
            from services.vram_coordinator import get_vram_coordinator, EvictionPriority
            coordinator = get_vram_coordinator()
        except Exception as e:
            logger.warning(f"[LLM] VRAM coordinator unavailable: {e}")
            if builds_vision:
                reason = _blind_refusal(f"the coordinator could not be consulted: {e}")
                logger.error(f"[LLM] {reason}")
                return False, reason

        if coordinator is not None:
            # Asked before the request, so that a refusal on this ground never
            # leaves a reservation standing.
            authoritative = False
            try:
                authoritative = coordinator.has_authoritative_reading()
            except Exception as e:
                logger.warning(f"[LLM] Could not check the VRAM sensor: {e}")
            if builds_vision and not authoritative:
                reason = _blind_refusal("NVML is not answering")
                logger.error(f"[LLM] {reason}")
                return False, reason

            granted, shortfall = True, None
            try:
                granted, shortfall, reservation = coordinator.request_vram_detailed(
                    "llm", estimated_mb, EvictionPriority.NORMAL, hold=True)
            except Exception as e:
                logger.warning(f"[LLM] VRAM coordinator request failed: {e}")
                if builds_vision:
                    reason = _blind_refusal(f"the request itself failed: {e}")
                    logger.error(f"[LLM] {reason}")
                    return False, reason

            if not granted:
                # A refused vision model is refused, full stop — it reached this
                # line only because the authoritative reading was there, and a
                # measured shortfall is exactly the case the refusal exists for.
                # The sensor question belongs to the text path alone, which is
                # allowed to proceed when nothing can read the card.
                if builds_vision or _sensor_can_read_the_card(coordinator):
                    breakdown = _budget_breakdown(config, estimated_mb)
                    # What the eviction chain actually did — including whether
                    # ComfyUI was asked at all. Claiming it was asked when a held
                    # slot or a closed port stopped the chain sends the reader
                    # after the wrong thing.
                    reason = (
                        f"VRAM shortfall for {model_alias}: needed {estimated_mb:.0f}MB "
                        f"({breakdown}) — {shortfall or 'no detail recorded'}"
                    )
                    logger.error(f"[LLM] {reason}")
                    return False, reason
                logger.warning(
                    "[LLM] Coordinator reports no room for %s, but nothing can read the "
                    "card right now — loading anyway rather than stopping the checks",
                    model_alias
                )

        logger.info(f"[LLM] Loading {model_alias} from {config['model_path']}...")

        # Everything from here to the registration is one attempt, and every way
        # it can end badly frees what it built. A model that reaches its warmup
        # and then falls over a line of bookkeeping used to leave weights and a
        # ~5GB encoder buffer on the card with nothing pointing at them: no
        # eviction can reach what was never registered.
        llm = None
        chat_handler = None
        try:
            import torch
            vram_before = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0

            # Build chat handler for VLM models
            if builds_vision:
                from llama_cpp.llama_chat_format import Qwen25VLChatHandler
                mmproj = config.get("mmproj_path", "")
                if not os.path.exists(mmproj):
                    logger.error(f"[LLM] mmproj not found: {mmproj}")
                    return False, f"mmproj not found for {model_alias}: {mmproj}"
                chat_handler = Qwen25VLChatHandler(clip_model_path=mmproj)
                logger.info(f"[LLM] VLM chat handler created: Qwen25VLChatHandler")

            llm = Llama(
                model_path=config["model_path"],
                n_ctx=config["n_ctx"],
                n_gpu_layers=config["n_gpu_layers"],
                chat_handler=chat_handler,
                verbose=False,
            )

            # The encoder's compute buffer is left to be allocated by the
            # first real image. A warmup used to force it here, so that the
            # room this load reserved was taken while it still stood — but on
            # this llama-cpp build only the FIRST image reading of a loaded
            # vision model comes back undamaged; every later one is served from
            # a context that still carries the reading before it. The warmup
            # spent that one clean reading on a 64x64 test picture, and every
            # reading a participant asked for arrived damaged. The surcharge in
            # the request above stands and remains the protection against the
            # crash; measured on 2026-09-01.

            vram_after = torch.cuda.memory_allocated(0) if torch.cuda.is_available() else 0
            actual_vram_mb = (vram_after - vram_before) / (1024 * 1024)

            # torch measures its own allocator, and llama.cpp allocates outside
            # it — so for these models the delta is 0 and the estimate is what
            # the ledger carries. That estimate is now the honest one: the
            # warmup above has put weights AND encoder buffer on the card, which
            # is exactly the sum that was requested. Before the warmup it named
            # room that nothing had taken yet.
            vram_mb = actual_vram_mb if actual_vram_mb > 0 else estimated_mb

            self._models[model_alias] = llm
            self._model_handlers[model_alias] = chat_handler
            self._model_vram_mb[model_alias] = vram_mb
            self._model_last_used[model_alias] = time.time()
            self._model_in_use[model_alias] = 0

            logger.info(f"[LLM] Loaded {model_alias} (VRAM: {vram_mb:.0f}MB)")
            return True, None

        except Exception as e:
            logger.error(f"[LLM] Failed to load {model_alias}: {e}")
            import traceback
            traceback.print_exc()
            if model_alias in self._models:
                # Registration already happened, so the model is reachable for
                # eviction and a caller may be holding it. Freeing it here would
                # pull it out from under them; the load itself stands.
                return True, None
            self._discard_failed_load(llm, chat_handler)
            return False, f"llama-cpp could not load {model_alias}: {e}"

        finally:
            # The promise ends with the attempt, whichever way it went: on
            # success the memory is on the card and NVML counts it, on failure
            # nothing was taken. Holding it any longer would make the card look
            # fuller than it is for the rest of the reservation's life.
            if reservation is not None and coordinator is not None:
                try:
                    coordinator.release_reservation(reservation)
                except Exception as e:
                    logger.warning(f"[LLM] Could not release the VRAM reservation: {e}")

    def _discard_failed_load(self, llm: Any, chat_handler: Any) -> None:
        """Give back a model that was built but never registered.

        Nothing here is in self._models yet, so no eviction can reach it and
        dropping the references would leave weights and vision context on the
        card until the process ends — measured on 2026-08-18 as 5876-5900MB per
        cycle for a VLM. Handler first: its context holds a pointer into the
        model. Both steps are best-effort, because the load is failing either
        way and the reason for that must not be replaced by a cleanup error.
        """
        try:
            if chat_handler is not None:
                self._release_vision_context(chat_handler)
        except Exception as e:
            logger.warning(f"[LLM] Vision context of a failed load stays on the card: {e}")
        try:
            if llm is not None:
                llm.close()
        except Exception as e:
            logger.warning(f"[LLM] Weights of a failed load stay on the card: {e}")
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    @staticmethod
    def _release_vision_context(handler: Any) -> None:
        """
        Free a VLM chat handler's vision context.

        llama-cpp-python 0.3.19 gives Llava15ChatHandler -- and the Qwen25VL
        handler derived from it -- no close(), no __exit__ and no __del__. The
        mtmd context it builds on first image use is reachable only through the
        ExitStack the handler keeps, and nothing ever closes that stack. Runs
        BEFORE the llama model is freed: the context holds a pointer into it.

        This is hygiene, not the cure for the leak below -- a text-only VLM run,
        where no mtmd context is ever built, leaked just as much.
        """
        stack = getattr(handler, "_exit_stack", None)
        if stack is None:
            logger.warning(
                "[LLM] Chat handler without _exit_stack -- vision context stays on the card; "
                "llama-cpp-python changed shape and _release_vision_context has to follow"
            )
            return
        stack.close()

    def _unload_model(self, model_alias: str) -> bool:
        """
        Unload a model and free its GPU memory. False if busy, absent or broken.

        Dropping the reference does not free a vision model. Measured against
        this same code on 2026-08-18, SD3.5 resident, three cycles each: every
        load/unload of qwen3-vl:8b left 5876-5900 MB on the card, with an image
        and without one, cumulative until the process died -- while the registry
        reported the model as unloaded. A text-only model of the same generation
        returned everything. Closing explicitly returns it all (residue 0-4 MB).

        Freeing explicitly instead of dropping the reference and hoping means the
        memory must provably be idle: llama.cpp is not reentrant, and pulling a
        model out from under a running generation takes the process down and
        every safety check with it. The per-alias inference lock is that proof --
        callers hold it from the moment they get the model until their generation
        ends. It is taken without blocking, so this never waits on a generation
        while the coordinator holds its own lock.

        Takes no load lock, and must not: the loaders hold theirs across
        coordinator.request_vram(), and the coordinator calls evict_model with
        its request lock held. Taking the load lock here would close that cycle
        and wedge the service. Every other backend's evict_model does without one
        for the same reason.
        """
        if model_alias not in self._models:
            return False

        lock = self._get_inference_lock(model_alias)
        if not lock.acquire(blocking=False):
            logger.info(f"[LLM] Not unloading {model_alias}: generation in flight")
            return False

        try:
            import torch

            vram_before = _own_process_vram_mb()

            llm = self._models.get(model_alias)
            handler = self._model_handlers.get(model_alias)
            try:
                if handler is not None:
                    self._release_vision_context(handler)
                if llm is not None:
                    llm.close()
            finally:
                # However the freeing went, a half-freed model must not stay
                # reachable, and the coordinator must stop counting it.
                self._models.pop(model_alias, None)
                self._model_handlers.pop(model_alias, None)
                self._model_vram_mb.pop(model_alias, None)
                self._model_last_used.pop(model_alias, None)
                self._model_in_use.pop(model_alias, None)
                llm = handler = None

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            vram_after = _own_process_vram_mb()
            returned = (
                vram_before - vram_after
                if vram_before is not None and vram_after is not None
                else None
            )
            # The reading covers the whole process, so it is worth printing only
            # when it says something. Memory that does not come back is what this
            # service had no way of noticing.
            if returned is not None and returned > 0:
                logger.info(
                    f"[LLM] Unloaded {model_alias} (process VRAM fell by {returned:.0f}MB — "
                    f"whole process, not this model alone)"
                )
            else:
                logger.info(f"[LLM] Unloaded {model_alias}")
            return True
        except Exception as e:
            logger.error(f"[LLM] Error unloading {model_alias}: {e}")
            return False
        finally:
            lock.release()

    def _get_model(self, model: str) -> tuple:
        """Get a loaded model, loading it on demand. Returns (llm, reason).

        reason is None when llm is not None, and says what went wrong otherwise.
        """
        alias = self._resolve_alias(model)
        if alias not in self._models:
            ok, reason = self._load_model(alias)
            if not ok:
                return None, reason
        llm = self._models.get(alias)
        if llm is None:
            # Loaded and gone again: an eviction ran between the two lines. Rare,
            # and it must not surface as a reasonless failure.
            return None, f"{alias} was evicted between its load and its use"
        # Only a model that is actually there gets a fresh timestamp. Stamping
        # first put an evicted alias back at the head of the LRU order, where it
        # protected models that are still loaded from being chosen instead.
        self._model_last_used[alias] = time.time()
        return llm, None

    # =========================================================================
    # Inference
    # =========================================================================

    def chat(self, model: str, messages: list, images: Optional[list] = None,
             temperature: float = 0.7, max_tokens: Optional[int] = None,
             repetition_penalty: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Chat completion (OpenAI-compatible message format).

        For VLM: images should be base64 strings, injected into the first user message
        as OpenAI-style image_url content parts.

        Generated through chat_stream() and joined here, so a blocking caller
        gets what a streaming one gets: the repetition stop, and a
        finish_reason saying how the answer ended -- "stop", "length" (the
        context ran out) or "repetition". A caller for whom a stopped answer is
        unusable has to read it; the image safety check does.
        """
        try:
            pieces = []
            finish_reason = "stop"
            for kind, value in self.chat_stream(
                model=model,
                messages=messages,
                images=images,
                temperature=temperature,
                max_tokens=max_tokens,
                repetition_penalty=repetition_penalty,
            ):
                if kind == "token":
                    pieces.append(value)
                else:
                    finish_reason = value or "stop"

            text = "".join(pieces).strip()
            thinking = None
            # A reasoning model's chat template opens <think> in the PROMPT, so
            # what comes back carries the closing tag alone: everything before
            # it is the model thinking to itself, the answer follows. Qwen 3.5
            # writes 2.6k characters of that before two sentences of answer
            # (measured 2026-08-16), and without this split all of it stood in
            # the answer. The paired form is covered by the same partition.
            if "</think>" in text:
                head, _, tail = text.partition("</think>")
                thinking = head.replace("<think>", "").strip() or None
                text = tail.strip()
            elif "<think>" in text:
                # The block was opened and never closed: the generation ended
                # inside the reasoning, at the context ceiling or under the
                # repetition guard. Everything after the opener is thinking and
                # stays thinking -- passed on as `content` it stood on the
                # surface as the answer, with the platform's own instructions
                # quoted back inside it (measured on the language model
                # comparison, Qwen 4b, 2026-09-06). What is left is what the
                # model wrote BEFORE it began, which is usually nothing, and an
                # empty answer is what a run that never finished one is.
                head, _, tail = text.partition("<think>")
                thinking = tail.strip() or None
                text = head.strip()

            return {
                "content": text,
                "thinking": thinking,
                "tool_calls": None,
                "finish_reason": finish_reason,
            }
        except ModelLoadRefused:
            # Passed through with its reason intact. None here would tell the
            # route "inference failed" for a model that was never on the card.
            raise
        except Exception as e:
            logger.error(f"[LLM] Chat failed ({model}): {e}")
            return None

    def chat_stream(self, model: str, messages: list, images: Optional[list] = None,
                    temperature: float = 0.7, max_tokens: Optional[int] = None,
                    repetition_penalty: Optional[float] = None):
        """Chat completion handed out while it is still being written.

        Same call as chat(), only the answer arrives in pieces instead of after
        the last token. Yields ("token", str) for every content delta and, as
        the last item, ("finish", reason) -- "stop" when the model came to its
        own end, "length" when it ran into the context ceiling, "repetition"
        when it began to loop and was stopped for it (see repetition_guard).
        Without that last item a caller cannot tell a finished reading from a
        cut one. Raises on a model that cannot be loaded and on a generation
        that breaks off, so the caller can say which of the two happened.
        """
        alias = self._resolve_alias(model)
        # Held from before the model is fetched until the generation ends: an
        # unload frees for real now, and a pointer taken before the lock would
        # leave exactly the window in which an eviction frees what this thread
        # is about to use. Releasing is the generator's job, in the finally
        # below -- a plain Lock, so an abandoned generator finalised on another
        # thread can still release it.
        lock = self._get_inference_lock(alias)
        lock.acquire()
        try:
            llm, load_reason = self._get_model(alias)
        except BaseException:
            lock.release()
            raise
        if llm is None:
            lock.release()
            raise ModelLoadRefused(f"model {alias} could not be loaded: {load_reason}")

        self._model_in_use[alias] = self._model_in_use.get(alias, 0) + 1
        try:
            final_messages = self._build_messages_with_images(messages, images)

            kwargs = {
                "messages": final_messages,
                "max_tokens": max_tokens,  # None -> run to the context ceiling
                "temperature": temperature,
                "stream": True,
            }
            if repetition_penalty is not None:
                kwargs["repeat_penalty"] = repetition_penalty

            # A second inference on the same model would interleave with this
            # one, which is why the lock stays held. Closing the generator
            # releases it early; a consumer that vanishes without anyone closing
            # it lets the generation run to the model's own ceiling first, as an
            # uninterrupted chat() would.
            finish_reason = None
            guard = RepetitionGuard()
            chunks = llm.create_chat_completion(**kwargs)
            try:
                for chunk in chunks:
                    choice = chunk.get("choices", [{}])[0]
                    piece = choice.get("delta", {}).get("content")
                    if piece:
                        yield ("token", piece)
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
                    if piece and guard.feed(piece):
                        # Closing llama-cpp's generator is what ends the
                        # generation; without it the model writes on into a
                        # buffer nobody reads.
                        chunks.close()
                        finish_reason = "repetition"
                        logger.info(
                            f"[LLM] {alias} repeated {guard.describe()} "
                            f"and was stopped"
                        )
                        break
            except Exception as e:
                # llama_decode returning 1 means the KV cache has no slot left:
                # the context is full. A model that writes until it runs out of
                # room has reached its ceiling, which is a way of ending, not a
                # broken generation -- the text stands and the caller is told
                # where it stops. Every other code is a real error and goes up
                # as one.
                if "llama_decode returned 1" not in str(e):
                    raise
                logger.info(f"[LLM] {alias} filled its context; reading ends there")
                finish_reason = "length"
            yield ("finish", finish_reason or "stop")
        finally:
            self._model_in_use[alias] = max(0, self._model_in_use.get(alias, 1) - 1)
            lock.release()

    def generate(self, model: str, prompt: str,
                 temperature: float = 0.7, max_tokens: Optional[int] = None,
                 repetition_penalty: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Raw text completion."""
        alias = self._resolve_alias(model)
        lock = self._get_inference_lock(alias)   # see chat_stream: held across the span
        lock.acquire()
        try:
            llm, load_reason = self._get_model(alias)
        except BaseException:
            lock.release()
            raise
        if llm is None:
            lock.release()
            # Raised, not returned as None: a load that never happened is not a
            # generation that came back empty, and the caller — the safety check
            # among them — has to be able to tell those apart. Errors from the
            # generation itself, below, still return None as before.
            raise ModelLoadRefused(f"model {alias} could not be loaded: {load_reason}")

        self._model_in_use[alias] = self._model_in_use.get(alias, 0) + 1
        try:
            kwargs = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            if repetition_penalty is not None:
                kwargs["repeat_penalty"] = repetition_penalty

            # Streamed for the same reason chat() is: a completion that has
            # begun to repeat itself is stopped instead of run to the ceiling.
            pieces = []
            finish_reason = "stop"
            guard = RepetitionGuard()
            chunks = llm.create_completion(**kwargs)
            for chunk in chunks:
                choice = chunk.get("choices", [{}])[0]
                piece = choice.get("text")
                if piece:
                    pieces.append(piece)
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
                if piece and guard.feed(piece):
                    chunks.close()
                    finish_reason = "repetition"
                    logger.info(
                        f"[LLM] {alias} repeated {guard.describe()} "
                        f"and was stopped"
                    )
                    break

            return {
                "response": "".join(pieces).strip(),
                "thinking": None,
                "finish_reason": finish_reason,
            }
        except Exception as e:
            logger.error(f"[LLM] Generate failed ({alias}): {e}")
            return None
        finally:
            self._model_in_use[alias] = max(0, self._model_in_use.get(alias, 1) - 1)
            lock.release()

    def _build_messages_with_images(self, messages: list, images: Optional[list] = None) -> list:
        """Convert images to OpenAI multimodal content format."""
        if not images:
            return messages

        result = []
        images_injected = False
        for msg in messages:
            m = dict(msg)
            if not images_injected and m.get("role") == "user":
                text_content = m.get("content", "")
                content_parts = [{"type": "text", "text": text_content}]
                for img_b64 in images:
                    if not img_b64.startswith("data:"):
                        img_b64 = f"data:image/jpeg;base64,{img_b64}"
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": img_b64}
                    })
                m["content"] = content_parts
                images_injected = True
            result.append(m)
        return result

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """List loaded models for status endpoint."""
        return [
            {
                "id": mid,
                "vram_mb": self._model_vram_mb.get(mid, 0),
                "in_use": self._model_in_use.get(mid, 0),
                "last_used": self._model_last_used.get(mid, 0),
            }
            for mid in self._models
        ]

    def get_available_models(self) -> List[str]:
        """List the model aliases whose files lie on disk.

        Availability is meant literally here. This list feeds the model-role
        pickers in the settings and the canvas dropdowns, and those carry no
        availability flag of their own -- a registered but undownloaded alias
        would arrive there as a selectable option that fails at load time. The
        Compare Hub lists (get_chat_models / get_vlm_models) report every
        registered alias together with its own availability flag and are
        deliberately not filtered here.
        """
        def _on_disk(config: Dict[str, Any]) -> bool:
            if not os.path.exists(config["model_path"]):
                return False
            mmproj = config.get("mmproj_path")
            return os.path.exists(mmproj) if mmproj else True

        all_models = [alias for alias, config in MODEL_CONFIGS.items() if _on_disk(config)]
        all_models.extend(
            alias for alias, target in MODEL_ALIASES.items()
            if target in MODEL_CONFIGS and _on_disk(MODEL_CONFIGS[target])
        )
        return all_models

    def get_chat_models(self) -> List[Dict[str, Any]]:
        """List chat-capable models with availability info for Compare Hub."""
        result = []
        for alias, config in MODEL_CONFIGS.items():
            if not config.get("chat_capable", False):
                continue
            result.append({
                "id": alias,
                "display_name": config.get("display_name", alias),
                "available": os.path.exists(config["model_path"]),
                "estimated_vram_mb": config.get("estimated_vram_mb", 0),
                "installable": bool(config.get("hf_repo_id")),
                "approx_download_mb": config.get("approx_download_mb", 0),
            })
        return result

    def get_vlm_models(self) -> List[Dict[str, Any]]:
        """List VLM-capable models with availability info for Compare Hub."""
        result = []
        for alias, config in MODEL_CONFIGS.items():
            if not config.get("vlm_capable", False):
                continue
            model_ok = os.path.exists(config["model_path"])
            mmproj_ok = os.path.exists(config.get("mmproj_path", ""))
            result.append({
                "id": alias,
                "display_name": config.get("display_name", alias),
                "available": model_ok and mmproj_ok,
                "estimated_vram_mb": config.get("estimated_vram_mb", 0),
                "installable": bool(config.get("hf_repo_id")),
                "approx_download_mb": config.get("approx_download_mb", 0),
            })
        return result

    def is_available(self) -> bool:
        """Check if llama-cpp-python is importable."""
        try:
            import llama_cpp
            return True
        except ImportError:
            return False

    def unload(self, model: str, force: bool = False) -> bool:
        """Take a model off the card. The route calls this on both engines.

        `force` has no meaning here and is refused rather than faked: the
        in-process engine frees by calling close() on a live Llama, and doing
        that under a running generation takes the whole process down. The
        per-alias inference lock is the only proof that it is idle, and there is
        nothing an operator could sensibly override about it. On the child
        engine force is real — there the busy model is another process.
        """
        if force:
            logger.warning("[LLM] force unload is not available in-process: "
                           "freeing %s under a running generation would take the "
                           "service down; waiting for the generation instead", model)
        return self._unload_model(self._resolve_alias(model))

    def get_engine_info(self) -> Dict[str, Any]:
        """What /api/llm/health reports about this engine."""
        return {"backend": "llama-cpp-python"}


# =========================================================================
# Singleton
# =========================================================================

_backend: Optional[LLMBackend] = None


def get_llm_backend() -> LLMBackend:
    """Get or create the LLM backend singleton."""
    global _backend
    if _backend is None:
        _backend = LLMBackend()
    return _backend
