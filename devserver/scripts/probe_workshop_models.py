#!/usr/bin/env python3
"""
Workshop catalog probe — runs each workshop-catalog model through the real
Stage-1-through-4 pipeline (`/api/schema/pipeline/generation`) on whichever
GPU the devserver is bound to. Sequential, one model at a time, recording
success/failure/observed routing per model.

Goal: answer "which models actually run end-to-end on this card, and via
which backend" without trusting any of the static catalog assumptions.

Usage:
  cd <repo>
  python -m devserver.scripts.probe_workshop_models \\
      [--port 17801] \\
      [--models sd35_large,flux2] \\
      [--per-model-timeout 240]

Outputs a JSON probe report next to the script:
  devserver/scripts/probe_workshop_models.report.json
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("probe_workshop_models")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_FILE = REPO_ROOT / "devserver" / "scripts" / "probe_workshop_models.report.json"


# Workshop catalog id → (output_config, modality)
# output_config matches a *.json file in devserver/schemas/configs/output/
# modality = "text" | "img2img" | "multi"
CATALOG_TO_PROBE = [
    ("sd35_large",   "sd35_large",            "text"),
    ("flux2",        "flux2",                 "text"),
    ("qwen_i2i",     "qwen_img2img",          "img2img"),
    ("qwen_multi",   "qwen_2511_multi",       "multi"),
    ("wan22_t2v",    "wan22_t2v_video_fast",  "text"),
    ("wan22_i2v",    "wan22_i2v_video",       "img2img"),
    ("ltx_video",    "ltx_video",             "text"),
    ("heartmula",    "heartmula_standard",    "text"),
    ("stable_audio", "stableaudio_open",      "text"),
    ("gemini_3_pro", "gemini_3_pro_image",    "text"),
]


def make_test_image(side: int = 256) -> bytes:
    """Return a small PNG suitable for img2img upload — generated in-process to avoid disk deps."""
    # 1x1 RGBA white repeated via PIL if available; else a tiny pre-baked PNG.
    try:
        from PIL import Image  # type: ignore
        img = Image.new("RGB", (side, side), color=(180, 200, 220))
        # tiny gradient so it's not pure solid (img2img may behave oddly with flat input)
        for x in range(side):
            for y in range(side):
                if (x + y) % 32 < 4:
                    img.putpixel((x, y), (240, 240, 240))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        # Fallback: 1x1 white PNG
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        )


def upload_test_image(base_url: str) -> Optional[str]:
    png = make_test_image(256)
    try:
        resp = requests.post(
            f"{base_url}/api/media/upload/image",
            files={"file": ("probe_input.png", png, "image/png")},
            timeout=30,
        )
        if not resp.ok:
            logger.warning("upload failed HTTP %d: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json() or {}
        return data.get("image_path")
    except Exception as e:
        logger.warning("upload exception: %s", e)
        return None


def probe(
    base_url: str,
    catalog_id: str,
    output_config: str,
    modality: str,
    image_path: Optional[str],
    per_model_timeout: int,
) -> dict:
    """Fire one Stage 1-4 pipeline run, parse SSE stream, return a result dict."""
    prompt = "Eine ruhige Berglandschaft im Morgennebel mit einem stillen See im Vordergrund"
    params: dict = {
        "output_config": output_config,
        "input_text": prompt,
        "prompt": prompt,
        "enable_streaming": "true",
        "device_id": f"probe_{catalog_id}",
    }
    if modality == "img2img":
        if not image_path:
            return {
                "status": "skipped",
                "reason": "img2img modality but no image uploaded",
            }
        params["input_image"] = image_path
    elif modality == "multi":
        if not image_path:
            return {
                "status": "skipped",
                "reason": "multi modality but no image uploaded",
            }
        params["input_image1"] = image_path
        params["input_image2"] = image_path
        params["input_image3"] = image_path

    url = f"{base_url}/api/schema/pipeline/generation"
    logger.info("[%s → %s/%s] firing pipeline...", catalog_id, output_config, modality)

    start = time.monotonic()
    events: list[str] = []
    stage_log: list[str] = []
    final_status = "unknown"
    error_msg: Optional[str] = None
    media_format: Optional[str] = None

    try:
        with requests.get(url, params=params, stream=True, timeout=per_model_timeout) as resp:
            if not resp.ok:
                return {
                    "status": "http_error",
                    "http": resp.status_code,
                    "body": resp.text[:500],
                    "duration_s": round(time.monotonic() - start, 1),
                }
            current_event = ""
            for raw in resp.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                if raw == "":
                    current_event = ""
                    continue
                if raw.startswith(":"):
                    continue  # heartbeat
                if raw.startswith("event:"):
                    current_event = raw[6:].strip()
                    continue
                if raw.startswith("data:"):
                    body = raw[5:].strip()
                    if not body:
                        continue
                    try:
                        payload = json.loads(body)
                    except json.JSONDecodeError:
                        continue
                    et = current_event or payload.get("type", "")
                    if et:
                        events.append(et)
                    # stage_start / stage_complete log
                    if et in ("stage_start", "stage_complete", "stage_error"):
                        stage = payload.get("stage") or payload.get("stage_name") or ""
                        if stage:
                            stage_log.append(f"{et}:{stage}")
                    if et == "complete":
                        media = payload.get("media_output") or {}
                        ms = (
                            payload.get("status")
                            or (media.get("status") if isinstance(media, dict) else None)
                            or "success"
                        )
                        if ms == "error":
                            final_status = "error"
                            error_msg = (
                                (media.get("error") if isinstance(media, dict) else None)
                                or payload.get("message")
                                or payload.get("error")
                                or "unknown"
                            )
                        else:
                            final_status = "success"
                            media_format = (
                                (media.get("format") or media.get("mime_type"))
                                if isinstance(media, dict)
                                else None
                            )
                        break
                    if et == "blocked":
                        final_status = "blocked_safety"
                        error_msg = payload.get("reason", "safety")
                        break
                    if et == "error":
                        final_status = "error"
                        error_msg = payload.get("message") or payload.get("error") or "unknown"
                        break
    except requests.Timeout:
        return {
            "status": "client_timeout",
            "duration_s": round(time.monotonic() - start, 1),
            "events_seen": events,
            "stage_log": stage_log,
        }
    except Exception as e:
        return {
            "status": "client_exception",
            "error": f"{type(e).__name__}: {e}",
            "duration_s": round(time.monotonic() - start, 1),
            "events_seen": events,
            "stage_log": stage_log,
        }

    return {
        "status": final_status,
        "duration_s": round(time.monotonic() - start, 1),
        "events_seen": events,
        "stage_log": stage_log,
        "error": error_msg,
        "media_format": media_format,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=17801)
    parser.add_argument("--models", default="",
                        help="Comma-separated workshop-catalog IDs to probe (default: all).")
    parser.add_argument("--per-model-timeout", type=int, default=300,
                        help="Per-model SSE wait timeout in seconds.")
    args = parser.parse_args()

    base_url = f"http://localhost:{args.port}"
    selected = set(s.strip() for s in args.models.split(",") if s.strip())
    probes = [p for p in CATALOG_TO_PROBE if not selected or p[0] in selected]
    if not probes:
        logger.error("no probes selected")
        return 1

    # Reachability
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        if not resp.ok:
            logger.warning("/health HTTP %d", resp.status_code)
    except Exception as e:
        logger.error("devserver unreachable at %s: %s", base_url, e)
        return 1

    # Upload test image once (re-used across probes)
    needs_image = any(modality in ("img2img", "multi") for _, _, modality in probes)
    image_path = upload_test_image(base_url) if needs_image else None
    if needs_image and not image_path:
        logger.warning("image upload failed — img2img/multi probes will be skipped")

    report: dict = {
        "probe_date": date.today().isoformat(),
        "devserver_url": base_url,
        "image_uploaded": bool(image_path),
        "results": {},
    }

    # GPU snapshot at probe start
    try:
        h = requests.get("http://localhost:17803/api/health", timeout=5).json()
        report["gpu"] = {
            "name": h.get("gpu", {}).get("gpu_name"),
            "total_vram_gb": h.get("gpu", {}).get("total_vram_gb"),
        }
    except Exception:
        report["gpu"] = None

    for catalog_id, output_config, modality in probes:
        result = probe(
            base_url,
            catalog_id,
            output_config,
            modality,
            image_path,
            args.per_model_timeout,
        )
        report["results"][catalog_id] = {
            "output_config": output_config,
            "modality": modality,
            **result,
        }
        # Save after every probe so a crash doesn't lose progress
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
        logger.info(
            "[%s] %s in %.1fs%s",
            catalog_id,
            result.get("status"),
            result.get("duration_s", 0),
            f"  ({result.get('error')[:120]})" if result.get("error") else "",
        )

    logger.info("done. report saved to %s", REPORT_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
