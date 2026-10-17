"""Resona's fourth Other: the machine she runs on.

Live material-energetic self-situatedness for the workshop companion — the
server's GPU identity, its current draw / temperature / utilisation / VRAM, the
models resident right now, and the running cost expressed in the SAME energy
formulas the platform's sustainability animations use, so the platform speaks one
voice. Assembled into a plain-fact "GIVEN MACHINE" block, sibling to the
GIVEN NOW / GIVEN LIBRARY notes in chat_routes.build_system_prompt.

Honesty contract (the "no hardware/model claims without a source" rule): every
number here is read live from nvidia-smi and the VRAM coordinator. Nothing is
simulated or invented; an unreadable field simply drops its line, and if
nothing is readable the whole block is empty. The disposition for USING these
facts (only when they bear on a choice, never as self-report) lives in
RESONA_CORE_PROMPT — this module only supplies the facts.

Energy model — mirrors public/ai4artsed-frontend/src/composables/
useAnimationProgress.ts so the figures match the edutainment minigames exactly:
    Wh per second   = watts / 3600
    g CO2 per second = (Wh/s / 1000) * CO2_PER_KWH_GRAMS
    tree            : a tree reabsorbs TREE_G_CO2_PER_HOUR grams per hour
CO2_PER_KWH_GRAMS = 400 is the German-grid average also hardcoded in
settings_routes.get_gpu_realtime and documented in
docs/ARCHITECTURE PART 15 - Key-Design-Decisions.md.
"""

import logging
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Energy assumptions — kept identical to the frontend energy model so the
# platform speaks one voice. German electricity grid average (~2024).
CO2_PER_KWH_GRAMS = 400
TREE_G_CO2_PER_HOUR = 2.51

# Short cache so the per-request prompt build stays cheap. This is honest
# situatedness, not a real-time meter (the frontend itself polls only ~2s).
_CACHE_TTL_S = 6.0
_cache_value: Optional[str] = None
_cache_at: float = -1e9


def _read_nvidia_smi() -> Optional[dict]:
    """Live GPU stats via nvidia-smi. Mirrors the read in
    settings_routes.get_gpu_realtime (same query, same 5s timeout).
    Returns None when unavailable."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,power.draw,power.limit,temperature.gpu,"
                "utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(", ")]
        if len(parts) < 7:
            return None

        def _num(raw, cast):
            return cast(float(raw)) if raw not in ("[N/A]", "N/A", "") else None

        return {
            "gpu_name": parts[0] or None,
            "power_draw_watts": _num(parts[1], float),
            "power_limit_watts": _num(parts[2], float),
            "temperature_celsius": _num(parts[3], int),
            "utilization_percent": _num(parts[4], int),
            "memory_used_mb": _num(parts[5], int),
            "memory_total_mb": _num(parts[6], int),
        }
    except Exception as e:
        logger.info("[RESONA-HW] nvidia-smi read skipped: %s", e)
        return None


def read_gpu_power() -> Optional[dict]:
    """The card's current draw and its power limit, for callers that need an
    energy estimate rather than the whole block. None when unreadable."""
    smi = _read_nvidia_smi()
    if not smi:
        return None
    return {
        "draw_watts": smi.get("power_draw_watts"),
        "limit_watts": smi.get("power_limit_watts"),
    }


def _read_loaded_models() -> Optional[list]:
    """Models resident in VRAM right now: what ComfyUI holds, read through
    the gate (services/gpu_gate.py, since stage 7 of the move to ComfyUI).
    None when ComfyUI could not be asked, in which case the block omits the
    line rather than guessing."""
    try:
        from my_app.services.gpu_gate import get_gpu_gate
        # On the prompt's path: a ComfyUI that takes longer than this is
        # left out of the block, not waited for.
        status = get_gpu_gate().vram_status(card_timeout=(2, 3))
        if not (status.get("comfyui") or {}).get("reachable"):
            return None
        models = status.get("loaded_models")
        if not isinstance(models, list):
            return None
        # The models, as ComfyUI lists them. The list also carries the other
        # processes on the card as the driver sees them (source "driver"),
        # named by their command lines; those are for the settings page, not
        # for a prompt that leaves this machine.
        return [m for m in models if m.get("source") == "card"]
    except Exception as e:
        logger.info("[RESONA-HW] resident models skipped: %s", e)
        return None


def _gb(mb) -> Optional[float]:
    try:
        return round(float(mb) / 1024.0, 1)
    except Exception:
        return None


def _compose(smi: Optional[dict], models: Optional[list]) -> str:
    if not smi:
        return ""  # nothing readable -> the block stays silent

    lines = []

    # Identity
    name = smi.get("gpu_name")
    tot_gb = _gb(smi.get("memory_total_mb"))
    if name and tot_gb:
        lines.append(f"- {name}, {tot_gb:g} GB VRAM.")
    elif name:
        lines.append(f"- {name}.")

    # Right now
    now_bits = []
    draw = smi.get("power_draw_watts")
    limit = smi.get("power_limit_watts")
    if draw is not None and limit:
        now_bits.append(f"drawing {draw:.0f} W of {limit:.0f} W")
    elif draw is not None:
        now_bits.append(f"drawing {draw:.0f} W")
    temp = smi.get("temperature_celsius")
    if temp is not None:
        now_bits.append(f"{temp} °C")
    util = smi.get("utilization_percent")
    if util is not None:
        now_bits.append(f"{util}% busy")
    used_gb = _gb(smi.get("memory_used_mb"))
    if used_gb is not None and tot_gb:
        now_bits.append(f"{used_gb:g}/{tot_gb:g} GB VRAM in use")
    if now_bits:
        lines.append("- right now: " + ", ".join(now_bits) + ".")

    # Models resident right now (this is what "mixing models" looks like)
    if models is not None:
        if models:
            parts = []
            for m in models:
                label = m.get("model") or m.get("backend") or "unknown"
                mvram = _gb(m.get("vram_mb"))
                parts.append(f"{label} ({mvram:g} GB)" if mvram else str(label))
            lines.append("- resident right now: " + ", ".join(parts) + ".")
        else:
            lines.append("- resident right now: nothing loaded.")

    # Running cost, in the platform's own energy terms — only from a real draw.
    if draw is not None and draw > 0:
        wh_min = draw / 60.0
        co2_min = (wh_min / 1000.0) * CO2_PER_KWH_GRAMS
        tree_min = co2_min * 60.0 / TREE_G_CO2_PER_HOUR
        lines.append(
            f"- at ~{draw:.0f} W that is ≈ {wh_min:.1f} Wh/min "
            f"≈ {co2_min:.2f} g CO₂/min "
            f"(factor {CO2_PER_KWH_GRAMS} g/kWh, German-grid assumption); "
            f"a tree reabsorbs that in ≈ {tree_min:.0f} min."
        )

    if not lines:
        return ""
    return (
        "GIVEN MACHINE (the server this runs on, read live just now):\n"
        + "\n".join(lines)
    )


def build_hardware_context() -> str:
    """The GIVEN MACHINE block string. '' on any problem. Short-TTL cached so
    it costs nothing on rapid consecutive turns."""
    global _cache_value, _cache_at
    now = time.monotonic()
    if _cache_value is not None and (now - _cache_at) < _CACHE_TTL_S:
        return _cache_value
    try:
        block = _compose(_read_nvidia_smi(), _read_loaded_models())
    except Exception as e:
        logger.info("[RESONA-HW] hardware context failed: %s", e)
        block = ""
    _cache_value = block
    _cache_at = now
    return block
