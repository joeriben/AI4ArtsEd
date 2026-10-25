"""
Latent Lab Capability Resolver — gates VRAM-heavy Latent Lab tools off cards
that physically cannot fit them alongside the workshop-platform baseline
(the image model + Llama-Guard + Qwen-VL co-resident; ≈ 20-22 GB measured with
SD3.5-Medium, and the Latent Lab runs SD3.5-Large on every card since 2026-09-18).

Policy: Some Latent-Lab tools have a peak VRAM cost that exceeds what's
available on consumer cards even after the resident model footprint:

  - Attention Cartography: stores cross-attention maps GPU-resident. With
    default capture parameters (3 layers × 25 steps × ~235 MB each) the peak
    exceeds 17 GB on top of the resident pipeline — won't fit on 4090 (24 GB)
    or 5090 (32 GB) at workshop-platform baseline.

  - Feature Probing "all" mode on the DIFFUSERS path: encodes both prompts
    through all 3 encoders (CLIP-L, CLIP-G, T5-XXL). T5-XXL activation memory at
    max_sequence_length=512 + multiple passes is borderline on 5090, OOM on
    4090. The ComfyUI path of the same instrument carries no gate: it runs T5 at
    the prompt's own length under ComfyUI's partial loading, and its config asks
    for 12 GB where the Diffusers config asks for 30.

Resolution order:
1. Env override AI4ARTSED_FORCE_HEAVY_LATENT_LAB=true → all caps enabled
2. GPU VRAM via ComfyUI /system_stats               → ≥40 GB → enabled
3. Detection failure                                  → disabled (conservative)

The 40 GB threshold excludes 4090 (24 GB) and 5090 (32 GB) while admitting
the RTX PRO 6000 Blackwell (96 GB). It is intentionally above 32 GB because
the structural problem on consumer cards is not capacity alone — it's
capacity AFTER the resident workshop-platform baseline.

A reading that succeeded is memoized per process (thread-safe);
a failed detection is held for one minute only, so a service that comes
back is noticed without a restart.

CALLERS:
  - output_image_attention_cartography_diffusers.py (gate)
  - output_image_attention_cartography_comfyui.py (gate, as the twin)
  - output_image_feature_probing_diffusers.py (gate)
  - /api/latent_lab/capabilities endpoint (frontend tab-greyout)

  output_image_feature_probing_comfyui.py does NOT gate — see above.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_MIN_HEAVY_VRAM_GB = 40.0
_ENV_VAR = "AI4ARTSED_FORCE_HEAVY_LATENT_LAB"

_HEAVY_TOOLS = ("attention_cartography", "feature_probing")

_resolved: Optional[dict] = None
_lock = threading.Lock()

# How long a FAILED reading stays in force. Two costs sit either side of this
# number and both were paid at some point:
#   0     - every caller pays the full read budget again. A hanging GPU service
#           turned one ten-second wait into one per question; six instruments
#           ask eight times, and each page load held a waitress thread.
#   forever - the state before 2026-08-26: one hiccup and the Latent Lab said
#           "no attention cartography on this card" until the next restart,
#           with nothing in the tree able to clear it.
# A minute is short enough that a service coming back is noticed within one,
# and long enough that a burst of questions asks once. A successful reading
# still holds for the life of the process.
_FAILED_MEMO_S = 60.0
_failed: Optional[dict] = None
_failed_until: float = 0.0


async def get_latent_lab_capabilities() -> dict:
    """Return {tool_id: bool} for VRAM-gated Latent-Lab tools.

    Also includes diagnostic fields the frontend uses for tooltip text:
      - total_vram_gb: detected total VRAM (or None if detection failed)
      - threshold_gb: the gate threshold
      - forced: True iff the env override is active
    """
    global _resolved, _failed, _failed_until
    if _resolved is not None:
        return _resolved
    if _failed is not None and time.monotonic() < _failed_until:
        return _failed

    # The reading happens OUTSIDE the lock. A module-wide lock held across a
    # request to the GPU service stops every other thread asking the same
    # question, and the Latent Lab page asks it on load - one slow answer would
    # hold the whole surface. Two threads arriving together may both ask; one
    # spare question is the cheaper of the two costs.
    answer, certain = await _resolve()

    with _lock:
        if certain:
            if _resolved is None:
                if _failed is not None:
                    logger.info("[LATENT-LAB-CAPS] card readable again → %s",
                                "heavy tools enabled" if answer.get(_HEAVY_TOOLS[0])
                                else "heavy tools disabled")
                _resolved = answer
                _failed = None
                _failed_until = 0.0
            return _resolved
        if _resolved is not None:
            # A reading that succeeded outranks a later failure: the card did
            # not change, only the way to ask it did.
            return _resolved
        _failed = answer
        _failed_until = time.monotonic() + _FAILED_MEMO_S
        return answer


def reset_cache() -> None:
    """Clear the memoized result. Intended for tests only."""
    global _resolved, _failed, _failed_until
    with _lock:
        _resolved = None
        _failed = None
        _failed_until = 0.0


async def _resolve() -> tuple:
    """The capabilities, and whether they rest on a reading that succeeded.

    The second element decides whether the answer is worth remembering. False
    means the card was never read - the caller is handed the conservative
    answer for this one request, and the next request asks again.
    """
    forced = os.environ.get(_ENV_VAR, "").strip().lower() in ("true", "1", "yes")
    if forced:
        logger.info("[LATENT-LAB-CAPS] %s=true → all heavy tools enabled", _ENV_VAR)
        return {
            **{tool: True for tool in _HEAVY_TOOLS},
            "total_vram_gb": None,
            "threshold_gb": _MIN_HEAVY_VRAM_GB,
            "forced": True,
        }, True

    # Read from ComfyUI, through the one place that asks (services/gpu_card.py).
    try:
        from my_app.services.gpu_card import total_vram_gb, CardUnreadable
        vram_gb = await total_vram_gb()
    except CardUnreadable as e:
        logger.warning("[LATENT-LAB-CAPS] %s → heavy tools disabled", e)
        return {
            **{tool: False for tool in _HEAVY_TOOLS},
            "total_vram_gb": None,
            "threshold_gb": _MIN_HEAVY_VRAM_GB,
            "forced": False,
        }, False

    enabled = vram_gb >= _MIN_HEAVY_VRAM_GB
    logger.info(
        "[LATENT-LAB-CAPS] Detected %.1f GB VRAM %s %.0f GB threshold → heavy tools %s",
        vram_gb, "≥" if enabled else "<", _MIN_HEAVY_VRAM_GB,
        "enabled" if enabled else "disabled",
    )
    return {
        **{tool: enabled for tool in _HEAVY_TOOLS},
        "total_vram_gb": vram_gb,
        "threshold_gb": _MIN_HEAVY_VRAM_GB,
        "forced": False,
    }, True
