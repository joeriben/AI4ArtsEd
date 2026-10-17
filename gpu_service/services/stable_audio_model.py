"""
Stable Audio 3 Model Resolver — single source of truth for SA3 variant selection.

SA3 ships three *downloadable* variants (large is API-only, no weights published):
  - stable-audio-3-medium      (1.4B DiT, music + SFX)  — top local tier
  - stable-audio-3-small-music (0.459B)                 — small music tier
  - stable-audio-3-small-sfx   (0.6B)                   — small SFX tier

Per-machine policy (user-specified, 2026-06):
  - RTX 6000 (96 GB)  → medium  (for BOTH music and SFX — medium covers both)
  - RTX 4090 (24 GB)  → small   (music → small-music, SFX → small-sfx)
  - RTX 5090 (32 GB)  → undecided → treated as below threshold → small

The decision is NOT "does medium fit" — medium is only ~9 GB resident and fits a 4090.
It is co-residency headroom on the SHARED gpu_service GPU: below the threshold the card
must also host SD3.5 / LLMs / Hunyuan3D / etc., so SA3 stays small; above it, medium is
affordable. This mirrors the Latent Lab resolver's 50 GB cutoff (see
devserver/my_app/services/latent_lab_model.py) for the same co-residency reason.

The tier (medium vs small) is ONE machine-local decision shared by music and SFX:
on the medium tier BOTH use SA3 medium (a single music+SFX model); below the threshold
each kind falls back to its dedicated small variant (small-music / small-sfx). This is
the user's explicit instruction ("rtx6000 medium für beide, music und sfx").

WHY THIS LIVES IN gpu_service (and latent_lab_model.py lives in devserver):
SA3 is a single resident model loaded *inside* gpu_service and never swapped per request,
so the variant is a load-time, machine-local decision — resolved here against torch.cuda
directly (no HTTP). SD3.5, by contrast, is swapped per request by the diffusers backend,
so its resolver lives devserver-side and asks gpu_service over HTTP.

Tier resolution order:
  1. Env override AI4ARTSED_STABLE_AUDIO_MODEL=medium|small  → forced tier
  2. GPU VRAM via torch.cuda                                 → >= 50 GB → medium tier
  3. Detection failure / no CUDA                             → small tier (conservative)

Result is memoized per process (thread-safe).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

SA3_MEDIUM = "stabilityai/stable-audio-3-medium"
SA3_SMALL_MUSIC = "stabilityai/stable-audio-3-small-music"
SA3_SMALL_SFX = "stabilityai/stable-audio-3-small-sfx"

_MIN_MEDIUM_VRAM_GB = 50.0
_ENV_VAR = "AI4ARTSED_STABLE_AUDIO_MODEL"

_medium_tier: Optional[bool] = None
_lock = threading.Lock()


def get_stable_audio_model_id(kind: str = "music") -> str:
    """Return the SA3 model ID appropriate for this GPU and content kind.

    The medium-vs-small *tier* is a single machine-local decision (VRAM-tiered,
    memoized). On the medium tier both kinds use SA3 medium (one music+SFX model);
    below the threshold each kind uses its dedicated small variant.

    kind="music" → medium (tier) or small-music (below threshold)
    kind="sfx"   → medium (tier) or small-sfx   (below threshold)
    """
    if kind not in ("music", "sfx"):
        raise ValueError(f"Unknown kind {kind!r} (expected 'music' or 'sfx')")

    if _resolve_medium_tier():
        return SA3_MEDIUM  # medium is a single model covering BOTH music and SFX
    return SA3_SMALL_SFX if kind == "sfx" else SA3_SMALL_MUSIC


def reset_cache() -> None:
    """Clear the memoized tier decision. Intended for tests only."""
    global _medium_tier
    with _lock:
        _medium_tier = None


def _resolve_medium_tier() -> bool:
    """True → use SA3 medium for both kinds; False → use the small variants. Memoized."""
    global _medium_tier
    if _medium_tier is not None:
        return _medium_tier
    with _lock:
        if _medium_tier is not None:
            return _medium_tier
        _medium_tier = _detect_medium_tier()
        return _medium_tier


def _detect_medium_tier() -> bool:
    env_value = os.environ.get(_ENV_VAR, "").strip().lower()
    if env_value == "medium":
        logger.info("[SA3-MODEL] %s=medium → medium tier", _ENV_VAR)
        return True
    if env_value == "large":
        logger.warning(
            "[SA3-MODEL] %s=large is API-only (no downloadable weights) → medium tier "
            "(top local tier)", _ENV_VAR,
        )
        return True
    if env_value in ("small", "small-music", "small_music", "small-sfx", "small_sfx"):
        logger.info("[SA3-MODEL] %s=%s → small tier", _ENV_VAR, env_value)
        return False
    if env_value:
        logger.warning(
            "[SA3-MODEL] Unknown %s value %r — ignoring, falling back to VRAM detection",
            _ENV_VAR, env_value,
        )

    try:
        import torch
        if not torch.cuda.is_available():
            logger.warning(
                "[SA3-MODEL] CUDA unavailable → small tier (conservative fallback)"
            )
            return False
        props = torch.cuda.get_device_properties(0)
        vram_gb = props.total_memory / (1024 ** 3)
    except Exception as e:
        logger.warning(
            "[SA3-MODEL] VRAM detection failed (%s) → small tier (conservative fallback)",
            type(e).__name__,
        )
        return False

    if vram_gb >= _MIN_MEDIUM_VRAM_GB:
        logger.info(
            "[SA3-MODEL] Detected %.1f GB VRAM >= %.0f GB threshold → medium tier",
            vram_gb, _MIN_MEDIUM_VRAM_GB,
        )
        return True

    logger.info(
        "[SA3-MODEL] Detected %.1f GB VRAM < %.0f GB threshold → small tier",
        vram_gb, _MIN_MEDIUM_VRAM_GB,
    )
    return False
