"""Which Stable Audio 3 model this card runs -- one machine-local decision.

SA3 ships three downloadable variants (large is API-only): medium (1.4B DiT,
music and SFX), small-music (0.459B) and small-sfx (0.6B). The policy
(user-specified, 2026-06; gpu_service/services/stable_audio_model.py until
stage 6 of the move to ComfyUI) is not "does medium fit":
medium is ~9 GB resident and fits a 24 GB card. It is co-residency headroom
on the shared card: below the threshold the card also hosts SD3.5, the
language models, Hunyuan3D, so SA3 stays small; above it, medium is
affordable and covers BOTH kinds, music and sfx. Below the threshold each
kind uses its dedicated small variant.

The threshold and the aliases stand in config/local_media_weights.json
(stable_audio block); the card is read from ComfyUI through the one place
that asks (services/gpu_card), the way the Latent Lab resolver reads it.

Tier resolution order:
  1. Env override AI4ARTSED_STABLE_AUDIO_MODEL=medium|small  -> forced tier
  2. The card's VRAM via gpu_card.total_vram_gb()            -> >= threshold: medium
  3. An unreadable card raises CardUnreadable: the caller is told, rather than
     handed a model that was never chosen for this card.

Memoized per process (thread-safe).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from my_app.services import local_media_weights

logger = logging.getLogger(__name__)

_ENV_VAR = "AI4ARTSED_STABLE_AUDIO_MODEL"
_KINDS = ("music", "sfx")

_medium_tier: Optional[bool] = None
_lock = threading.Lock()


def alias(kind: str = "music") -> str:
    """The alias of the SA3 model for this card and content kind.

    kind="music" -> medium (tier) or small-music (below threshold)
    kind="sfx"   -> medium (tier) or small-sfx   (below threshold)
    """
    if kind not in _KINDS:
        raise ValueError(f"Unknown kind {kind!r} (expected one of {_KINDS})")
    policy = local_media_weights.stable_audio_policy()
    if _resolve_medium_tier(float(policy["medium_min_vram_gb"])):
        return policy["medium"]
    return policy["small"][kind]


def dir_name(kind: str = "music") -> str:
    """The folder name the node ai4artsed_stable_audio is given for this
    card and kind."""
    return local_media_weights.dir_name(alias(kind))


def reset_cache() -> None:
    """Clear the memoized tier decision. Intended for tests only."""
    global _medium_tier
    with _lock:
        _medium_tier = None


def _resolve_medium_tier(min_medium_vram_gb: float) -> bool:
    """True -> medium for both kinds; False -> the small variants. Memoized."""
    global _medium_tier
    if _medium_tier is not None:
        return _medium_tier
    # Asked outside the lock: the lock is module-wide, and an HTTP request
    # held under it would stop every other thread that needs the answer.
    answer = _detect_medium_tier(min_medium_vram_gb)
    with _lock:
        if _medium_tier is None:
            _medium_tier = answer
        return _medium_tier


def _vram_gb() -> float:
    """The card's memory from gpu_card, on whichever thread this is called:
    a Flask thread has no loop and reads directly; an async caller (the
    stable_audio chunk) already runs a loop, and asyncio.run inside one
    raises, so the reading is taken on a thread of its own."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from my_app.services.gpu_card import read_sync
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return read_sync().total_vram_gb
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(read_sync).result().total_vram_gb


def _detect_medium_tier(min_medium_vram_gb: float) -> bool:
    env_value = os.environ.get(_ENV_VAR, "").strip().lower()
    if env_value == "medium":
        logger.info("[SA3-MODEL] %s=medium -> medium tier", _ENV_VAR)
        return True
    if env_value == "large":
        logger.warning("[SA3-MODEL] %s=large is API-only (no downloadable weights) "
                       "-> medium tier (top local tier)", _ENV_VAR)
        return True
    if env_value in ("small", "small-music", "small_music", "small-sfx", "small_sfx"):
        logger.info("[SA3-MODEL] %s=%s -> small tier", _ENV_VAR, env_value)
        return False
    if env_value:
        logger.warning("[SA3-MODEL] Unknown %s value %r -- ignoring, falling back to VRAM detection",
                       _ENV_VAR, env_value)

    vram_gb = _vram_gb()
    if vram_gb >= min_medium_vram_gb:
        logger.info("[SA3-MODEL] Detected %.1f GB VRAM >= %.0f GB threshold -> medium tier",
                    vram_gb, min_medium_vram_gb)
        return True
    logger.info("[SA3-MODEL] Detected %.1f GB VRAM < %.0f GB threshold -> small tier",
                vram_gb, min_medium_vram_gb)
    return False
