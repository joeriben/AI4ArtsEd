#!/usr/bin/env python3
"""
Measure per-model working VRAM on the current GPU.

For each workshop catalog model:
  1. Clear the GPU (unload all backends + ComfyUI free).
  2. Settle for a few seconds, record baseline VRAM.
  3. Trigger the model's preload path (gpu_service load OR ComfyUI fake-run).
  4. Record peak VRAM during/after the load.
  5. working_vram_gb = max(peak - baseline, 0), rounded.
  6. Unload, settle, move on.

Results are merged into devserver/config/gpu_model_footprints.json under the
detected GPU's name. Models whose load times out or fails get fits=false.

Usage:
  cd <repo>
  python -m devserver.scripts.measure_workshop_footprints \\
      [--models sd35_large,heartmula] \\
      [--devserver-url http://localhost:17802] \\
      [--settle-seconds 3] \\
      [--per-model-timeout 240]

The script talks to the devserver's existing /api/settings/workshop/{preload,
clear-all} endpoints and the gpu_service /api/diffusers/gpu_info, so all of
those must be running. Total runtime is dominated by the ComfyUI fake-runs
(~30-90s per heavy model + offload setup).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("measure_workshop_footprints")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FOOTPRINTS_FILE = REPO_ROOT / "devserver" / "config" / "gpu_model_footprints.json"


def load_footprints() -> dict:
    with open(FOOTPRINTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_footprints(data: dict) -> None:
    with open(FOOTPRINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def gpu_info(gpu_service_url: str) -> dict:
    """Pull GPU info from gpu_service /api/health — uses nvidia-smi-derived totals
    via the vram_coordinator, which sees ALL GPU processes (diffusers, heartmula,
    stable_audio, ComfyUI, foreign). The /api/diffusers/gpu_info endpoint only
    sees the diffusers process and would miss heartmula/stable_audio/ComfyUI loads.
    """
    resp = requests.get(f"{gpu_service_url}/api/health", timeout=5)
    resp.raise_for_status()
    return resp.json() or {}


def used_vram_gb(info: dict) -> float:
    coord = info.get("vram_coordinator") or {}
    gpu = info.get("gpu") or {}
    total_mb = float(gpu.get("total_vram_gb", 0)) * 1024
    free_mb = float(coord.get("free_mb", 0))
    return max(0.0, (total_mb - free_mb) / 1024)


def coordinator_signature(info: dict) -> dict:
    """Return a dict that captures, separately, what each accounting path tracks:
      - registered_models: {(backend, model): vram_mb} from vram_coordinator.loaded_models
      - foreign_mb: vram_coordinator.foreign_vram_mb (ComfyUI + other non-gpu-service procs)
    This bypasses PyTorch allocator caching distortions: gpu_service models are
    measured via their coordinator-registered vram_mb; ComfyUI models are
    measured via the foreign_mb delta (since they aren't registered in
    loaded_models but do show up in the foreign-process VRAM tally).
    """
    coord = info.get("vram_coordinator") or {}
    registered = {
        (m.get("backend", ""), m.get("model", "")): int(m.get("vram_mb", 0))
        for m in coord.get("loaded_models", [])
    }
    foreign_mb = float(coord.get("foreign_vram_mb", 0))
    return {"registered": registered, "foreign_mb": foreign_mb}


def delta_for_path(
    before: dict, after: dict, execution_path: str
) -> tuple[Optional[float], list[str]]:
    """Return (working_vram_gb, notes) for the given execution path.

    gpu_service path: take the NEW entries in loaded_models, sum their vram_mb.
    comfyui    path: take the increase in foreign_vram_mb (ComfyUI residency).
    """
    notes: list[str] = []
    if execution_path == "gpu_service":
        before_keys = set(before["registered"].keys())
        new = {k: v for k, v in after["registered"].items() if k not in before_keys}
        if not new:
            notes.append("no new registered models after gpu_service load")
            return None, notes
        for (backend, model), mb in new.items():
            notes.append(f"new gpu_service entry: {backend}/{model} = {mb} MB")
        total_mb = sum(new.values())
        return round(total_mb / 1024, 1), notes
    if execution_path == "comfyui":
        delta_mb = max(0.0, after["foreign_mb"] - before["foreign_mb"])
        notes.append(
            f"foreign_vram delta = {after['foreign_mb']:.0f} - {before['foreign_mb']:.0f}"
            f" = {delta_mb:.0f} MB"
        )
        gb = delta_mb / 1024
        rounded = round(gb, 1) if gb < 10 else round(gb)
        return rounded, notes
    return None, [f"unknown execution_path: {execution_path}"]


def clear_all(devserver_url: str) -> None:
    requests.post(f"{devserver_url}/api/settings/workshop/clear-all", timeout=60)


def preload_via_chunk(comfyui_url: str, chunk_path: Path, timeout: int) -> tuple[bool, Optional[str]]:
    """Submit a ComfyUI chunk's workflow directly (bypassing the workshop preload map).

    Used for sd35_large on small GPUs where the workshop preload routes through
    gpu_service (which OOMs at 28 GB on a 24 GB card) but real generation uses
    the ComfyUI fallback path. Measuring against the fallback chunk gives the
    correct working VRAM number for what the user actually experiences.
    """
    import copy
    try:
        with open(chunk_path, "r", encoding="utf-8") as f:
            chunk_data = json.load(f)
    except Exception as e:
        return False, f"chunk load failed: {e}"
    workflow = copy.deepcopy(chunk_data.get("workflow") or {})
    if not workflow:
        return False, "chunk has no workflow"
    # Tiny-cost overrides mirroring _build_comfyui_preload_workflow in settings_routes.py
    for node in workflow.values():
        ct = node.get("class_type", "")
        inputs = node.setdefault("inputs", {})
        if ct == "EmptyLatentImage" or ct == "EmptySD3LatentImage":
            inputs["width"] = 128
            inputs["height"] = 128
            inputs["batch_size"] = 1
        if ct in ("KSampler", "KSamplerAdvanced"):
            inputs["steps"] = 1
        if ct == "CLIPTextEncode" and isinstance(inputs.get("text"), str):
            inputs["text"] = "preload"
    try:
        resp = requests.post(
            f"{comfyui_url}/prompt",
            json={"prompt": workflow, "client_id": "footprint_measure"},
            timeout=30,
        )
        if not resp.ok:
            return False, f"ComfyUI HTTP {resp.status_code}: {resp.text[:200]}"
        prompt_id = (resp.json() or {}).get("prompt_id")
        if not prompt_id:
            return False, "no prompt_id from ComfyUI"
    except Exception as e:
        return False, f"submit failed: {e}"
    # Poll history
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        try:
            h = requests.get(f"{comfyui_url}/history/{prompt_id}", timeout=10).json()
        except Exception:
            continue
        if prompt_id in h:
            status_info = h[prompt_id].get("status", {})
            if status_info.get("completed") or status_info.get("status_str") == "success":
                return True, None
            if status_info.get("status_str") == "error":
                return False, "ComfyUI execution error"
    return False, f"ComfyUI timeout ({timeout}s)"


def preload_one(devserver_url: str, model_id: str, timeout: int) -> tuple[bool, Optional[str]]:
    """Run the workshop preload SSE stream for a single model. Returns (success, error)."""
    try:
        with requests.post(
            f"{devserver_url}/api/settings/workshop/preload",
            json={"models": [model_id]},
            stream=True,
            timeout=timeout,
        ) as resp:
            if not resp.ok:
                return False, f"HTTP {resp.status_code}"
            event_type = ""
            buffer = ""
            for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
                if not chunk:
                    continue
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        try:
                            payload = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        if event_type == "model_complete":
                            return True, None
                        if event_type == "model_error":
                            return False, str(payload.get("error", "unknown"))
                        if event_type == "done":
                            return False, "done without completion"
        return False, "stream ended"
    except requests.Timeout:
        return False, f"timeout ({timeout}s)"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def measure_model(
    model_id: str,
    execution_path: str,
    devserver_url: str,
    gpu_service_url: str,
    settle_seconds: float,
    per_model_timeout: int,
    via_chunk: Optional[str] = None,
    comfyui_url: Optional[str] = None,
) -> dict:
    """Measure a single model. Returns {"working_vram_gb", "fits", "execution_path", "error"?}.

    Uses path-specific accounting (see delta_for_path) instead of nvidia-smi free-mb
    deltas, which are distorted by PyTorch's caching allocator.
    """
    logger.info("--- %s [%s] ---", model_id, execution_path)

    # 1. clear, settle, record baseline signature
    clear_all(devserver_url)
    time.sleep(settle_seconds)
    before = coordinator_signature(gpu_info(gpu_service_url))
    logger.info(
        "[%s] baseline: %d registered models, foreign=%.0f MB",
        model_id, len(before["registered"]), before["foreign_mb"],
    )

    # 2. preload + capture signature
    if via_chunk and comfyui_url:
        chunks_dir = REPO_ROOT / "devserver" / "schemas" / "chunks"
        chunk_path = chunks_dir / f"{via_chunk}.json"
        ok, err = preload_via_chunk(comfyui_url, chunk_path, timeout=per_model_timeout)
        # When measured via a ComfyUI chunk the load shows up as foreign_vram,
        # not in registered loaded_models — force the accounting path accordingly.
        accounting_path = "comfyui"
    else:
        ok, err = preload_one(devserver_url, model_id, timeout=per_model_timeout)
        accounting_path = execution_path
    time.sleep(settle_seconds)
    after = coordinator_signature(gpu_info(gpu_service_url))

    # 3. compute delta, then cleanup
    working_gb, notes = delta_for_path(before, after, accounting_path)
    for n in notes:
        logger.info("[%s] %s", model_id, n)

    clear_all(devserver_url)
    time.sleep(settle_seconds)

    # When a chunk override was used, persist the path that actually serviced the load.
    stored_path = "comfyui" if via_chunk else execution_path

    if not ok:
        logger.warning("[%s] preload failed (%s); marking fits=false", model_id, err)
        return {
            "working_vram_gb": None,
            "fits": False,
            "execution_path": stored_path,
            "error": err,
        }

    if working_gb is None or working_gb <= 0:
        logger.warning(
            "[%s] could not extract a positive working_vram from coordinator signature; "
            "preload reported success but no incremental VRAM was observed.",
            model_id,
        )
        return {
            "working_vram_gb": None,
            "fits": True,
            "execution_path": stored_path,
            "error": "no vram delta observed",
        }

    logger.info("[%s] working = %s GB", model_id, working_gb)
    return {
        "working_vram_gb": working_gb,
        "fits": True,
        "execution_path": execution_path,
    }


def execution_path_for(model_id: str) -> Optional[str]:
    """Mirror of _WORKSHOP_LOAD_MAP routing (gpu_service vs comfyui vs cloud)."""
    gpu_service = {"heartmula", "stable_audio"}
    # sd35_large loads through a ComfyUI chunk since stage 4 of the move.
    comfyui = {"sd35_large", "flux2", "wan22_t2v", "wan22_i2v", "ltx_video", "acestep",
               "qwen_t2i", "qwen_i2i", "qwen_multi"}
    if model_id in gpu_service:
        return "gpu_service"
    if model_id in comfyui:
        return "comfyui"
    return "cloud"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--devserver-url", default="http://localhost:17802")
    parser.add_argument("--gpu-service-url", default="http://localhost:17803")
    parser.add_argument("--settle-seconds", type=float, default=3.0,
                        help="Wait time after clear/load before VRAM read.")
    parser.add_argument("--per-model-timeout", type=int, default=240,
                        help="Per-model preload timeout in seconds.")
    parser.add_argument("--models", default="",
                        help="Comma-separated subset (default: all preloadable models in the catalog).")
    parser.add_argument("--via-chunk", default="",
                        help="model_id=chunk_name overrides. Comma-separated. Submits the named "
                             "ComfyUI chunk directly instead of using the workshop preload map. "
                             "Example: --via-chunk sd35_large=output_image_sd35_large (forces the "
                             "ComfyUI fallback path for sd35_large on small GPUs).")
    parser.add_argument("--comfyui-url", default="http://127.0.0.1:17804",
                        help="ComfyUI base URL for --via-chunk submissions.")
    args = parser.parse_args()

    if not FOOTPRINTS_FILE.exists():
        logger.error("footprints file missing: %s", FOOTPRINTS_FILE)
        return 1

    footprints = load_footprints()
    catalog_ids = [m["id"] for m in footprints.get("models", []) if m.get("preloadable")]
    via_chunk_map: dict[str, str] = {}
    if args.via_chunk:
        for pair in args.via_chunk.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            mid, chunk = pair.split("=", 1)
            via_chunk_map[mid.strip()] = chunk.strip()

    if args.models:
        wanted = [m.strip() for m in args.models.split(",") if m.strip()]
        unknown = [m for m in wanted if m not in catalog_ids]
        if unknown:
            logger.error("unknown model id(s): %s", unknown)
            return 1
        model_ids = wanted
    else:
        model_ids = catalog_ids

    health = gpu_info(args.gpu_service_url)
    gpu = health.get("gpu") or {}
    gpu_name = gpu.get("gpu_name", "")
    total_vram = gpu.get("total_vram_gb", 0)
    if not gpu_name:
        logger.error("could not detect GPU via %s", args.gpu_service_url)
        return 1
    logger.info("detected GPU: %s (%.1f GB total)", gpu_name, total_vram)

    by_gpu = footprints.setdefault("footprints", {}).setdefault(
        gpu_name,
        {
            "total_vram_gb": round(total_vram),
            "measured_at": None,
            "measurement_notes": "Measured by scripts/measure_workshop_footprints.py",
            "by_model": {},
        },
    )
    by_gpu["total_vram_gb"] = round(total_vram)
    by_gpu.setdefault("by_model", {})

    for mid in model_ids:
        path = execution_path_for(mid)
        if path == "cloud":
            by_gpu["by_model"][mid] = {
                "working_vram_gb": 0,
                "fits": True,
                "execution_path": "cloud",
            }
            logger.info("[%s] cloud model — no measurement needed", mid)
            continue

        chunk_override = via_chunk_map.get(mid)
        result = measure_model(
            mid,
            path,
            args.devserver_url,
            args.gpu_service_url,
            args.settle_seconds,
            args.per_model_timeout,
            via_chunk=chunk_override,
            comfyui_url=args.comfyui_url if chunk_override else None,
        )
        by_gpu["by_model"][mid] = result

        # Persist after every model so a crash doesn't lose previous results
        from datetime import date
        by_gpu["measured_at"] = date.today().isoformat()
        save_footprints(footprints)

    logger.info("done. results saved to %s", FOOTPRINTS_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
