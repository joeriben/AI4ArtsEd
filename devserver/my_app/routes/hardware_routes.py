"""
Hardware API Routes — per-GPU model footprints and capabilities.

Single source of truth for the workshop catalog + per-GPU working-VRAM
measurements. Its frontend reader went with the workshop planning page;
the data and the endpoint stay for the callers they were meant for
(latent lab capability checks, backend dashboards, planner tools).

Data lives in devserver/config/gpu_model_footprints.json. New measurements
are produced by tools/measure_workshop_footprints.py.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Blueprint, jsonify


logger = logging.getLogger(__name__)

hardware_bp = Blueprint('hardware', __name__, url_prefix='/api/hardware')

_FOOTPRINTS_FILE = (
    Path(__file__).parent.parent.parent / "config" / "gpu_model_footprints.json"
)


def _load_footprints() -> dict:
    try:
        with open(_FOOTPRINTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"[HARDWARE] {_FOOTPRINTS_FILE} not found")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"[HARDWARE] Invalid JSON in {_FOOTPRINTS_FILE}: {e}")
        return {}


def _detect_gpu() -> dict:
    """Return {'name': str, 'total_vram_gb': float} for the active GPU.

    Asked of ComfyUI through `gpu_card`, the one reader on this platform. It
    used to ask the GPU service, which is being taken down; the number is the
    same one either way (both divide the driver's byte count by 1024**3).

    An empty dict on failure: this route draws a table, and a table that says
    nothing was measured is a true statement about a card nobody could read.
    """
    from my_app.services import gpu_card
    try:
        card = gpu_card.read_sync()
    except Exception as e:
        logger.warning(f"[HARDWARE] GPU detection failed: {e}")
        return {}
    return {"name": card.name, "total_vram_gb": card.total_vram_gb}


# How far the card's own reading may sit from the family's, before the family
# is refused. A board is not exactly the size its family is written down as —
# the driver reports 94.97 GiB where the file says 96 — but it is close.
_FAMILY_SIZE_TOLERANCE = 0.05


def _footprints_for(gpu_name: str, footprints: dict, total_vram_gb: float = 0.0) -> dict:
    """The measured footprints for this card, matched by family.

    The file keys on the family ("NVIDIA RTX PRO 6000 Blackwell"), the driver
    reports the board ("NVIDIA RTX PRO 6000 Blackwell Workstation Edition").
    An exact lookup therefore missed on the development card and answered that
    NOTHING had been measured, for a card the file holds a full set of readings
    for.

    So: the exact key, else the longest family the name continues. Two things
    keep that from claiming too much.

    A family is only continued at a word boundary, so "RTX 4090M" is not an
    "RTX 4090". And the size has to agree: "NVIDIA GeForce RTX 4090 Laptop GPU"
    IS a continuation of "NVIDIA GeForce RTX 4090" and has 16 GB against the
    family's 24 — it would have been handed nine measurements taken on a card
    with half again as much memory, and told that a 22 GB model fits. Where the
    reading disagrees with the family by more than a twentieth, the family is
    refused and the route says nothing was measured, which is true.
    """
    by_gpu = footprints.get("footprints", {})
    if gpu_name in by_gpu:
        return by_gpu[gpu_name]
    low = str(gpu_name or "").lower()
    if not low:
        return {}
    hits = [k for k in by_gpu
            if low == str(k).lower() or low.startswith(str(k).lower() + " ")]
    if not hits:
        return {}
    best = max(hits, key=len)
    family = by_gpu[best]
    written = family.get("total_vram_gb") or 0
    if written and total_vram_gb:
        off = abs(total_vram_gb - written) / written
        if off > _FAMILY_SIZE_TOLERANCE:
            logger.warning(
                "[HARDWARE] %r continues %r, but reads %.1f GiB against the "
                "family's %s — not taking its measurements",
                gpu_name, best, total_vram_gb, written)
            return {}
    logger.info("[HARDWARE] %r read as %r for the footprint table", gpu_name, best)
    return family


@hardware_bp.route('/model_footprints', methods=['GET'])
def get_model_footprints():
    """Return the workshop model catalog + per-model working-VRAM for the active GPU.

    Response shape:
      {
        "gpu": {"name": "...", "total_vram_gb": N, "matched": true/false},
        "models": [ { id, name, media_type, publisher, cloud_region,
                      preloadable, note, shared_with?, shared_vram_gb?,
                      working_vram_gb, fits, execution_path, measured } ],
        "safety_baseline_gb": N,
        "safety_models": [ { name, vram_gb } ],
        "comfyui_overhead_gb": N,
        "measured_at": "..." | null
      }

    Models without a footprint entry for the active GPU get working_vram_gb=null,
    fits=null, measured=false — the frontend can render them as 'unknown'.
    """
    footprints = _load_footprints()
    if not footprints:
        return jsonify({"error": "footprints file unavailable"}), 500

    gpu = _detect_gpu()
    gpu_name = gpu.get("name", "")
    by_gpu = _footprints_for(gpu_name, footprints, gpu.get("total_vram_gb", 0.0))
    matched = bool(by_gpu)
    by_model = by_gpu.get("by_model", {})

    models_out = []
    for entry in footprints.get("models", []):
        mid = entry["id"]
        fp = by_model.get(mid)
        models_out.append({
            **entry,
            "working_vram_gb": fp["working_vram_gb"] if fp else None,
            "fits": fp["fits"] if fp else None,
            "execution_path": fp["execution_path"] if fp else None,
            "measured": fp is not None,
        })

    return jsonify({
        "gpu": {
            "name": gpu_name,
            # The card's own reading, or nothing. The family's written size
            # describes the family, not the board in this machine.
            "total_vram_gb": gpu.get("total_vram_gb", 0),
            "matched": matched,
        },
        "models": models_out,
        "safety_baseline_gb": footprints.get("safety_baseline_gb", 5.5),
        "safety_models": footprints.get("safety_models", []),
        "comfyui_overhead_gb": footprints.get("comfyui_overhead_gb", 0.6),
        "measured_at": by_gpu.get("measured_at"),
        "measurement_notes": by_gpu.get("measurement_notes"),
    }), 200
