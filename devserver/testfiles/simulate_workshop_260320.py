#!/usr/bin/env python3
"""
Workshop Load Replay — 2026-03-20

Replays the 104 Stage-4 generations from the third workshop (youth safety level)
with the original two-phase timing pattern:
  Phase 1 (15:14-15:55): sd35_large dominant (structured geometric exercises)
  Phase 2 (16:57-17:51): qwen_img2img dominant (photo transformation)
  ~1h pause between phases.

7 generating devices, 2 browsing-only. Youth safety level throughout.
97% success rate in original workshop (0 technical errors, 3 correct safety blocks).

Extracted from: Teilprotokoll 20 3 2026 backend.txt
Prompts are the ORIGINAL user inputs extracted from [CHUNK-CONTEXT] and [STAGE4-GEN] log lines.

Usage:
    python simulate_workshop_260320.py [--port 17802] [--fast] [--dry-run] [--max-gap 15]

    --port PORT       Backend port (default: 17802 = development)
    --fast            Run at 4x speed
    --dry-run         Print timing without sending requests
    --no-image        Skip img2img/i2v (use sd35_large fallback)
    --max-gap SECONDS Cap inter-request idle gaps (default: 15s, 0=no cap)

HOW THIS SCRIPT WAS CREATED (for future sessions creating similar scripts):
    1. Parse the backend log for [STAGE4-GEN] lines to get timestamps + output_configs:
       grep "[STAGE4-GEN] Executing generation with config" backend.txt
    2. Compute offsets from first timestamp (15:14:32.285)
    3. Extract ORIGINAL prompts: for passthrough configs (qwen_img2img, wan22_i2v_video,
       qwen_2511_multi) use the STAGE4-GEN prompt directly. For intercepted configs
       (sd35_large, gemini_3_pro_image) search backwards in [CHUNK-CONTEXT] input_text
       lines for the German original (skip JSON/English interception output).
    4. Two-phase structure: Phase 1 = sd35_large, Phase 2 = qwen_img2img
    5. 7 generating devices — clusters <1s checked (none exceed 7 concurrent)
    6. Post-workshop entries (after 18:00, "Shaking hands" tests) excluded
    7. wan22_i2v_video is IMAGE-to-video — needs input_image like qwen_img2img!
"""

import argparse
import asyncio
import aiohttp
import os
import time
import sys
from dataclasses import dataclass
from typing import Optional

# Force line-buffered output (critical when stdout is redirected to a file)
import functools
print = functools.partial(print, flush=True)  # type: ignore[assignment]


# --- Workshop replay data (extracted from backend log 2026-03-20) ---
# Format: (seconds_offset_from_start, output_config, original_prompt)
# Offset 0 = 15:14:32.285 (first Stage 4 generation)
# 104 entries = all Stage 4 requests during workshop (excl. post-18:00 testing)
# Prompts are ORIGINAL user inputs from the backend log (not synthetic).
#
# Config distribution (lt. Report 20.03):
#   sd35_large:         45 (GPU Service/Diffusers)
#   qwen_img2img:       47 (ComfyUI) — needs input_image
#   qwen_2511_multi:     7 (ComfyUI) — needs input_image1/2/3
#   wan22_i2v_video:     3 (ComfyUI) — needs input_image (Image-to-Video!)
#   gemini_3_pro_image:  2 (Cloud API)
#
# Two-phase pattern:
#   Phase 1 (15:14-15:55): sd35_large + 2x gemini — structured geometric exercises
#   ~1h pause (15:55-16:57)
#   Phase 2 (16:57-17:51): qwen_img2img dominant — photo transformation + creative iteration

WORKSHOP_REQUESTS = [
    # === Phase 1: Structured exercises (15:14-15:55) ===
    (      0.0, "gemini_3_pro_image", "Eine Familie am Essenstisch \u2013 heute Abend in der K\u00fcche"),
    (   1554.0, "sd35_large", "papier in einen kreis gerissen"),
    (   1690.8, "sd35_large", "Eine Katze auf dem Baum"),
    (   1690.8, "sd35_large", "Eine Katze auf dem Baum"),
    (   1691.8, "sd35_large", "Eine Katze auf dem Baum"),
    (   1692.6, "sd35_large", "Eine Katze auf dem Baum"),
    (   1729.6, "sd35_large", "Eine Katze auf dem Baum"),
    (   1732.3, "sd35_large", "papier in einen kreis gerissen"),
    (   1732.4, "sd35_large", "Zeichne eine Kugel die im Wasser liegt"),
    (   1811.1, "sd35_large", "Zeichne ein Viereck auf wei\u00dfen Hintergrund"),
    (   1839.1, "sd35_large", "Forme eine Kugel"),
    (   1847.6, "sd35_large", "Forme eine Kugel"),
    (   1869.0, "sd35_large", "Zeichne ein Viereck auf wei\u00dfen Hintergrund"),
    (   1874.5, "sd35_large", "Zeichne ein Viereck auf wei\u00dfen Hintergrund"),
    (   1936.2, "sd35_large", "Zeichne ein Viereck auf wei\u00dfen Hintergrund"),
    (   1989.7, "sd35_large", "Zeichne ein Viereck auf wei\u00dfen Hintergrund"),
    (   2029.9, "sd35_large", "Zeichne ein Viereck auf wei\u00dfen Hintergrund"),
    (   2037.6, "sd35_large", "Zeichne ein Viereck auf wei\u00dfen Hintergrund"),
    (   2040.1, "sd35_large", "Zeichne ein Viereck auf wei\u00dfen Hintergrund"),
    (   2120.4, "sd35_large", "Forme einen wei\u00dfen Kreis"),
    (   2128.3, "sd35_large", "Forme einen wei\u00dfen Kreis"),
    (   2171.5, "sd35_large", "Forme einen wei\u00dfen Kreis aus Papier"),
    (   2181.3, "sd35_large", "Forme einen wei\u00dfen Kreis aus Papier"),
    (   2181.4, "sd35_large", "Forme einen wei\u00dfen Kreis aus Papier"),
    (   2270.6, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2297.6, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2323.2, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2330.9, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2342.2, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2342.3, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2342.4, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2344.2, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2344.3, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2348.7, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2353.6, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2356.0, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2362.6, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2365.0, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2370.4, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2387.0, "sd35_large", "Zeichne eine Kugel die \u00fcber dem Wasser schwebt"),
    (   2422.2, "gemini_3_pro_image", "Ein einzelnes rotes Viereck schwebt mittig im Bild, von oben betrachtet, perfekt zentriert auf wei\u00dfe"),

    # === ~1h PAUSE (15:55 - 16:57) ===

    # --- Phase 2 start: Abstract art (sd35_large, 16:57-17:00) ---
    (   6182.2, "sd35_large", "abstraktes bild mit schwarzer f\u00e4rbe auf wei\u00dfem Papier"),
    (   6200.9, "sd35_large", "abstraktes bild mit schwarzer f\u00e4rbe auf wei\u00dfem Papier"),
    (   6212.5, "sd35_large", "abstraktes bild mit schwarzer f\u00e4rbe auf wei\u00dfem Papier"),
    (   6315.3, "sd35_large", "abstraktes bild mit schwarzer f\u00e4rbe auf wei\u00dfem Papier"),
    (   6315.3, "sd35_large", "abstraktes bild mit schwarzer f\u00e4rbe auf wei\u00dfem Papier"),
    (   6332.1, "sd35_large", "abstraktes bild mit schwarzer f\u00e4rbe auf wei\u00dfem Papier"),

    # === Phase 2: Photo transformation (17:27-17:51) ===
    (   7971.1, "qwen_img2img", "Es soll besser werden..."),
    (   8012.7, "qwen_img2img", "Nutzte diese Feder f\u00fcr den Puffer von einen Zug...."),
    (   8026.7, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Rolle von dem Klopapier, wie auf dem Foto...."),
    (   8055.8, "wan22_i2v_video", "Es soll besser aus sehen wie ein Kleider B\u00fcgel"),
    (   8059.0, "qwen_img2img", "Zeichne die Hand echt und gebe ihr einen Ring der soll rosa sein als Hintergrund soll ein Fluss sein..."),
    (   8076.8, "qwen_img2img", "Nutzte das silberne Objekt im Bild als Trampolingfeder..."),
    (   8106.9, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto...."),
    (   8158.1, "qwen_img2img", "Es soll besser aus sehen wie ein Kleider B\u00fcgel"),
    (   8186.6, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Rolle von dem Klopapier, wie auf dem Foto...."),
    (   8215.2, "qwen_img2img", "Zeichne die Hand blau und gelb gebe ihr ein Ring und als Hintergrund rosa die Hand soll magisch und ..."),
    (   8252.1, "qwen_img2img", "Es soll besser aus sehen wie ein Kleider B\u00fcgel"),
    (   8262.3, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto...."),
    (   8290.3, "qwen_img2img", "Es soll besser aus sehen wie ein Kleider B\u00fcgel ohne kleider"),
    (   8291.3, "qwen_img2img", "Zeichne die Hand als Hund kombiniere es"),
    (   8323.3, "qwen_img2img", "Lege das Objekt auf einen alten Holztisch..."),
    (   8357.7, "qwen_img2img", "Kombiniere die hant zu einem Hund aber Sachen bleiben nur gleich zwar andere Farbe"),
    (   8392.0, "qwen_img2img", "Es soll besser aus sehen wie ein Kleider B\u00fcgel ohne kleider"),
    (   8415.9, "qwen_img2img", "Lege das Objekt auf einen Laptop."),
    (   8442.5, "qwen_img2img", "Es soll besser aus sehen wie ein Kleider B\u00fcgel ohne kleider"),
    (   8470.0, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto. Es sol..."),
    (   8500.0, "qwen_img2img", "Zeichne einen Finger weg und stelle ein Hund auf die Hand der \u00fcber die Hand guckt"),
    (   8533.4, "qwen_img2img", "Verwandle das Bild in den Boden einer Tanz-Fl\u00e4che"),
    (   8541.5, "qwen_img2img", "Ein einzelner Kleiderb\u00fcgel aus Metall, freigestellt auf wei\u00dfem Hintergrund, ohne Kleidung, klare Lin..."),
    (   8571.5, "qwen_img2img", "Zeichne einen Finger weg und stelle ein Hund auf die Hand der \u00fcber die Hand guckt"),
    (   8574.3, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto. Es sol..."),
    (   8585.0, "qwen_img2img", "Lege das Objekt auf einen Laptop."),
    (   8593.1, "qwen_img2img", "Ein einzelner Kleiderb\u00fcgel aus Metall, freigestellt auf wei\u00dfem Hintergrund, ohne Kleidung, klare Lin..."),
    (   8602.6, "qwen_img2img", "Zeichne einen Finger weg und stelle ein Hund auf die Hand der \u00fcber die Hand guckt"),
    (   8624.5, "qwen_img2img", "Mache es so, dass es den kompletten Boden der Tanzfl\u00e4che einnimmt ..."),
    (   8660.4, "qwen_img2img", "Zeichne der Hand nur 5 Finger ..."),
    (   8664.6, "qwen_img2img", "Ein einzelner Kleiderb\u00fcgel aus Metall, freigestellt auf wei\u00dfem Hintergrund, ohne Kleid, klare Linien..."),
    (   8665.8, "qwen_img2img", "Lege das Objekt auf einen pinken Laptop."),
    (   8665.9, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto. Ein M\u00e4..."),
    (   8682.4, "qwen_img2img", "Mache es gr\u00f6\u00dfer dass es den kompletten Boden einnimmt ..."),
    (   8717.0, "qwen_img2img", "Zeichne der Hand nur 5 Finger und an der Hand soll sich ein Hund hochkrabeln ..."),
    (   8750.1, "qwen_img2img", "Zeichne der Hand nur 5 Finger und an der Hand soll sich ein Hund hochkrabeln und der Hund soll braun..."),
    (   8798.0, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto. Ein M\u00e4..."),
    (   8801.4, "qwen_img2img", "Zeichne der Hand nur 5 Finger und an der Hand soll sich ein Hund hochkrabeln und der Hund soll braun..."),
    (   8856.4, "qwen_img2img", "Zeichne der Hand nur 5 Finger und an der Hand soll sich ein Hund hochkrabeln und der Hund soll braun..."),
    (   8861.7, "qwen_img2img", "Verwandle es in den Boden einer Tanzfl\u00e4che. Es soll den ganzen Raum-Boden einnehmen. Es soll Discoli..."),
    (   8897.8, "qwen_img2img", "Ein Auto soll gegen dieses Objekt fahren und kaputt gehen...."),
    (   8903.6, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto. Ein Ma..."),
    (   8932.5, "qwen_img2img", "Z\u00fcnde dieses Objekt an..."),
    (   9010.5, "qwen_2511_multi", "Kombiniere die drei Bilder ..."),
    (   9016.2, "qwen_2511_multi", "Verwandle das Objekt in den Boden einer Tanzfl\u00e4che. Es muss den ganzen Raum-Boden einnehmen. Es muss..."),
    (   9054.3, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto. Ein M\u00e4..."),
    (   9065.0, "qwen_img2img", "Lege das brennende Objeke auf ein Blumenstuhl..."),
    (   9067.2, "qwen_2511_multi", "Zeichne die Bilder zusammen in eins mit eis ..."),
    (   9116.6, "qwen_img2img", "Male einen Regenschirm aus dem Stoff und der Papierrolle von dem Klopapier, wie auf dem Foto. Ein M\u00e4..."),
    (   9132.1, "qwen_2511_multi", "Zeichne die Bilder zusammen in eins mit eis zeichne nur 1 bild"),
    (   9141.5, "qwen_img2img", "Ein einzelner Kleiderb\u00fcgel aus Metall, freigestellt auf wei\u00dfem Hintergrund, ohne Kleid, klare Linien..."),
    (   9148.2, "qwen_2511_multi", "Verwandle das Objekt in den Boden einer Tanzfl\u00e4che. Es muss den ganzen Boden des Raumes einnehmen. E..."),
    (   9154.2, "qwen_img2img", "Mach den Hintergrund einen einfachen blauen Hintergrund..."),
    (   9233.7, "wan22_i2v_video", "Ein einzelner Kleiderb\u00fcgel aus Metall, freigestellt auf wei\u00dfem Hintergrund, ohne Kleid, klare Linien..."),
    (   9243.9, "qwen_2511_multi", "Zeichne die Bilder zusammen in eins mit eis zeichne nur 1 bild es sollen keine v\u00f6gel sondern das Tie..."),
    (   9367.4, "qwen_2511_multi", "Zeichne die Bilder zusammen in eins mit eis zeichne nur 1 bild es sollen keine V\u00f6gel sein"),
    (   9376.5, "wan22_i2v_video", "Ein einzelner Kleiderb\u00fcgel aus Metall, freigestellt auf wei\u00dfem Hintergrund, ohne Kleid, klare Linien..."),
]

assert len(WORKSHOP_REQUESTS) == 104, f"Expected 104 requests, got {len(WORKSHOP_REQUESTS)}"


# --- Configs that need img2img input ---
# wan22_i2v_video is IMAGE-to-video — it needs input_image just like qwen_img2img!
IMG2IMG_CONFIGS = {"qwen_img2img", "wan22_i2v_video"}
# qwen_2511_multi uses input_image1/2/3 (from device history), not input_image
MULTI_IMG_CONFIGS = {"qwen_2511_multi"}


def compute_adjusted_offsets(max_gap: float) -> list[float]:
    """Cap inter-request gaps at max_gap seconds while preserving burst timing.

    Gaps > drain_threshold are marked as drain points (returned separately).
    At drain points the simulation waits for all pending requests to finish,
    then continues immediately — no artificial waiting.
    """
    if max_gap <= 0:
        return [offset for offset, _, _ in WORKSHOP_REQUESTS]

    adjusted = [0.0]
    for i in range(1, len(WORKSHOP_REQUESTS)):
        raw_gap = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0]
        capped_gap = min(raw_gap, max_gap)
        adjusted.append(adjusted[-1] + capped_gap)
    return adjusted


def find_drain_points(drain_threshold: float) -> set[int]:
    """Find indices where the original gap is large enough to drain the queue.

    At these points, instead of waiting max_gap seconds, the simulation
    drains all pending requests and continues immediately.
    """
    drain_at: set[int] = set()
    for i in range(1, len(WORKSHOP_REQUESTS)):
        raw_gap = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0]
        if raw_gap >= drain_threshold:
            drain_at.add(i)
    return drain_at


@dataclass
class RequestResult:
    index: int
    config: str
    prompt: str
    status: str  # success, error, timeout, blocked
    duration_ms: float
    error: Optional[str] = None
    queue_rejected: bool = False


async def upload_test_image(session: aiohttp.ClientSession, base_url: str, image_path: str) -> Optional[str]:
    """Upload a test image and return its path for img2img use."""
    if not os.path.exists(image_path):
        print(f"  WARNING: Test image not found: {image_path}")
        return None

    url = f"{base_url}/api/media/upload/image"
    data = aiohttp.FormData()
    data.add_field("file", open(image_path, "rb"), filename="loadtest_input.png", content_type="image/png")

    try:
        async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                result = await resp.json()
                path = result.get("image_path", "")
                print(f"  Uploaded test image: {path}")
                return path
            else:
                print(f"  WARNING: Image upload failed ({resp.status})")
                return None
    except Exception as e:
        print(f"  WARNING: Image upload error: {e}")
        return None


async def send_request(
    session: aiohttp.ClientSession,
    base_url: str,
    index: int,
    config: str,
    prompt: str,
    device_id: str,
    no_image: bool = False,
    input_image_path: Optional[str] = None,
) -> RequestResult:
    """Send a single generation request via SSE and wait for completion."""
    start = time.monotonic()

    # For img2img/i2v without an actual image, fall back to sd35_large (t2i)
    effective_config = config
    if config in IMG2IMG_CONFIGS and (no_image or not input_image_path):
        effective_config = "sd35_large"

    params = {
        "output_config": effective_config,
        "input_text": prompt,
        "prompt": prompt,
        "enable_streaming": "true",
        "device_id": device_id,
    }

    # Add input_image for single img2img and i2v configs
    if effective_config in IMG2IMG_CONFIGS and input_image_path:
        params["input_image"] = input_image_path

    # Add input_image1/2/3 for multi-image configs (same image 3x for load test)
    if effective_config in MULTI_IMG_CONFIGS and input_image_path:
        params["input_image1"] = input_image_path
        params["input_image2"] = input_image_path
        params["input_image3"] = input_image_path

    url = f"{base_url}/api/schema/pipeline/generation"

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            status = "unknown"
            error = None
            queue_rejected = False
            current_event = ""

            # SSE format: "event: <type>\ndata: <json>\n\n"
            # Must track event type across lines
            async for line in resp.content:
                text = line.decode("utf-8", errors="replace").strip()

                if not text:
                    current_event = ""
                    continue

                if text.startswith("event:"):
                    current_event = text[6:].strip()
                    continue

                if text.startswith(":"):
                    continue  # SSE comment / heartbeat

                if not text.startswith("data:"):
                    continue

                data_str = text[5:].strip()
                if not data_str:
                    continue

                try:
                    import json
                    data = json.loads(data_str)
                except Exception:
                    continue

                event_type = current_event or data.get("type", "")

                if event_type == "complete":
                    media_status = data.get("status", "")
                    media = data.get("media_output", {})
                    if media_status == "error" or (isinstance(media, dict) and media.get("status") == "error"):
                        status = "error"
                        error = media.get("error") or data.get("message", "unknown")
                        if "queue full" in (error or "").lower():
                            queue_rejected = True
                    else:
                        status = "success"
                    break

                elif event_type == "blocked":
                    status = "blocked"
                    error = data.get("reason", "safety")
                    break

                elif event_type == "error":
                    status = "error"
                    error = data.get("message", "unknown")
                    if "queue full" in (error or "").lower():
                        queue_rejected = True
                    break

                current_event = ""

            duration = (time.monotonic() - start) * 1000
            return RequestResult(index, effective_config, prompt, status, duration, error, queue_rejected)

    except asyncio.TimeoutError:
        duration = (time.monotonic() - start) * 1000
        return RequestResult(index, effective_config, prompt, "timeout", duration, "Client timeout (600s)")
    except Exception as e:
        duration = (time.monotonic() - start) * 1000
        return RequestResult(index, effective_config, prompt, "error", duration, str(e))


async def run_simulation(port: int, speed: float, dry_run: bool, no_image: bool, image_path: str, max_gap: float = 0, drain_threshold: float = 60.0):
    base_url = f"http://localhost:{port}"
    adjusted = compute_adjusted_offsets(max_gap)
    drain_points = find_drain_points(drain_threshold)
    original_duration = WORKSHOP_REQUESTS[-1][0]
    adjusted_duration = adjusted[-1]
    saved = original_duration - adjusted_duration

    print(f"{'='*70}")
    print(f"  Workshop Load Replay \u2014 2026-03-20")
    print(f"  Target: {base_url}")
    print(f"  Speed:  {speed}x")
    print(f"  Max gap: {max_gap}s" + (f"  (saves {saved:.0f}s -> {adjusted_duration/speed:.0f}s at {speed}x)" if max_gap > 0 and saved > 0 else "  (disabled)" if max_gap <= 0 else ""))
    print(f"  Drain:  gaps >{drain_threshold:.0f}s -> drain queue, then continue ({len(drain_points)} drain points)")
    print(f"  Mode:   {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Image:  {'skip (t2i only)' if no_image else f'img2img/i2v with {image_path}'}")
    print(f"  Requests: {len(WORKSHOP_REQUESTS)}")
    print(f"{'='*70}")
    print()

    # Config distribution
    from collections import Counter
    configs = Counter(c for _, c, _ in WORKSHOP_REQUESTS)
    print(f"  Config distribution:")
    for cfg, cnt in configs.most_common():
        print(f"    {cfg:30s} {cnt:3d}")
    print()

    if dry_run:
        print("Timing preview (no requests sent):")
        for i, ((_offset, config, prompt), adj_offset) in enumerate(zip(WORKSHOP_REQUESTS, adjusted)):
            t = adj_offset / speed
            gap_orig = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0] if i > 0 else 0
            gap_adj = adjusted[i] - adjusted[i - 1] if i > 0 else 0
            capped = " (capped)" if gap_orig != gap_adj else ""
            print(f"  T+{t:7.1f}s  {config:25s}  {prompt[:50]}{capped}")
        print(f"\nOriginal duration: {original_duration/speed:.0f}s  |  Adjusted: {adjusted_duration/speed:.0f}s  |  Saved: {saved/speed:.0f}s")
        return

    # Check server reachability
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    print(f"ERROR: Server returned {resp.status}")
                    return
        except Exception as e:
            print(f"ERROR: Cannot reach {base_url}: {e}")
            return

    print(f"Server reachable.")

    # Check ComfyUI reachability (needed for qwen_img2img, wan22_i2v_video, qwen_2511_multi)
    comfyui_needed = any(c in ("qwen_img2img", "wan22_i2v_video", "qwen_2511_multi") for _, c, _ in WORKSHOP_REQUESTS)
    if comfyui_needed:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:17804/system_stats", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        print(f"ComfyUI reachable (port 17804).")
                    else:
                        print(f"WARNING: ComfyUI returned {resp.status} — ComfyUI configs may fail")
        except Exception:
            print(f"WARNING: ComfyUI not reachable on port 17804 — ComfyUI configs may fail")
            print(f"  DevServer COMFYUI-MANAGER may auto-start it, but first requests could fail.")

    # Upload test image for img2img and i2v
    input_image_ref = None
    if not no_image:
        async with aiohttp.ClientSession() as session:
            input_image_ref = await upload_test_image(session, base_url, image_path)
            if not input_image_ref:
                print("  Falling back to t2i only (no image uploaded)")
                no_image = True

    print(f"Starting replay...\n")

    # Device pool: 7 devices, each can only run 1 generation at a time.
    # Like real workshop — each iPad waits for its result before submitting again.
    N_DEVICES = 7
    device_locks: list[asyncio.Lock] = [asyncio.Lock() for _ in range(N_DEVICES)]
    device_ids = [f"loadtest_{d}" for d in range(N_DEVICES)]
    results: list[RequestResult] = []
    results_lock = asyncio.Lock()
    tasks: list[asyncio.Task] = []
    sim_start = time.monotonic()

    async def send_with_device(session, i, config, prompt, adj_offset):
        """Acquire a free device, wait for timing, send request, release device."""
        # Wait until the right moment first
        target_time = adj_offset / speed
        now = time.monotonic() - sim_start
        wait = target_time - now
        if wait > 0:
            await asyncio.sleep(wait)

        # Find a free device (round-robin preference, take first available)
        preferred = i % N_DEVICES
        device_idx = None

        # Try preferred device first (non-blocking)
        if not device_locks[preferred].locked():
            device_idx = preferred
        else:
            # Try all others
            for d in range(N_DEVICES):
                if not device_locks[d].locked():
                    device_idx = d
                    break

        # If all busy, wait for preferred device
        if device_idx is None:
            device_idx = preferred

        async with device_locks[device_idx]:
            elapsed = time.monotonic() - sim_start
            print(f"[T+{elapsed:7.1f}s] #{i+1:3d} SEND  dev{device_idx}  {config:20s}  {prompt[:45]}")

            result = await send_request(
                session, base_url, i, config, prompt,
                device_ids[device_idx], no_image, input_image_ref
            )
            async with results_lock:
                results.append(result)

    async with aiohttp.ClientSession() as session:
        for i, ((_offset, config, prompt), adj_offset) in enumerate(zip(WORKSHOP_REQUESTS, adjusted)):
            # Drain point: long original pause — wait for all pending, then reset clock
            if i in drain_points and tasks:
                raw_gap = WORKSHOP_REQUESTS[i][0] - WORKSHOP_REQUESTS[i - 1][0]
                elapsed = time.monotonic() - sim_start
                print(f"\n[T+{elapsed:7.1f}s] --- DRAIN POINT (original gap {raw_gap:.0f}s) — waiting for {sum(1 for t in tasks if not t.done())} pending... ---")
                await asyncio.gather(*tasks)
                # Reset the clock: adjust all remaining offsets relative to now
                drain_base = time.monotonic() - sim_start
                for j in range(i, len(adjusted)):
                    adjusted[j] = drain_base + (adjusted[j] - adjusted[i])
                elapsed = time.monotonic() - sim_start
                print(f"[T+{elapsed:7.1f}s] --- DRAIN COMPLETE — continuing immediately ---\n")

            task = asyncio.create_task(
                send_with_device(session, i, config, prompt, adjusted[i])
            )
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

    # Sort results by index
    results.sort(key=lambda r: r.index)

    # --- Report ---
    total_time = time.monotonic() - sim_start
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}\n")

    success = [r for r in results if r.status == "success"]
    blocked = [r for r in results if r.status == "blocked"]
    errors = [r for r in results if r.status == "error"]
    timeouts = [r for r in results if r.status == "timeout"]
    queue_rej = [r for r in results if r.queue_rejected]

    print(f"  Total requests:     {len(results)}")
    print(f"  Success:            {len(success)} ({100*len(success)/len(results):.0f}%)")
    print(f"  Blocked (safety):   {len(blocked)} ({100*len(blocked)/len(results):.0f}%)")
    print(f"  Errors:             {len(errors)} ({100*len(errors)/len(results):.0f}%)")
    print(f"  Timeouts:           {len(timeouts)} ({100*len(timeouts)/len(results):.0f}%)")
    print(f"  Queue rejected:     {len(queue_rej)} ({100*len(queue_rej)/len(results):.0f}%)")
    print()

    if success:
        durations = [r.duration_ms for r in success]
        print(f"  Success latency:")
        print(f"    Min:    {min(durations)/1000:.1f}s")
        print(f"    Median: {sorted(durations)[len(durations)//2]/1000:.1f}s")
        print(f"    Max:    {max(durations)/1000:.1f}s")
        print(f"    Avg:    {sum(durations)/len(durations)/1000:.1f}s")
    print()

    # Per-config breakdown
    config_results: dict[str, list[RequestResult]] = {}
    for r in results:
        config_results.setdefault(r.config, []).append(r)

    print(f"  Per-config breakdown:")
    for cfg in sorted(config_results.keys()):
        cfg_list = config_results[cfg]
        cfg_success = sum(1 for r in cfg_list if r.status == "success")
        cfg_durations = [r.duration_ms for r in cfg_list if r.status == "success"]
        avg_s = f"{sum(cfg_durations)/len(cfg_durations)/1000:.1f}s" if cfg_durations else "-"
        print(f"    {cfg:25s}  {cfg_success}/{len(cfg_list)} success  avg={avg_s}")
    print()

    print(f"  Wall time: {total_time:.0f}s")
    print()

    # Print errors
    if errors:
        print(f"  Error details:")
        for r in errors:
            tag = " [QUEUE FULL]" if r.queue_rejected else ""
            print(f"    #{r.index+1:3d} {r.config:25s} {r.duration_ms/1000:.1f}s  {tag}")
            print(f"         {r.error}")
        print()

    if timeouts:
        print(f"  Timeout details:")
        for r in timeouts:
            print(f"    #{r.index+1:3d} {r.config:25s} {r.duration_ms/1000:.0f}s  {r.error}")
        print()

    # Compare with workshop baseline
    print(f"  Workshop baseline (2026-03-20):")
    print(f"    Success rate: 97%    (this run: {100*len(success)/len(results):.0f}%)")
    print(f"    Tech errors:  0      (this run: {len(errors)})")
    print(f"    Timeouts:     0      (this run: {len(timeouts)})")
    print(f"    Safety blocks: 2.8%  (this run: {100*len(blocked)/len(results):.0f}%)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Workshop Load Replay \u2014 2026-03-20")
    parser.add_argument("--port", type=int, default=17802, help="Backend port (default: 17802)")
    parser.add_argument("--fast", action="store_true", help="4x speed")
    parser.add_argument("--dry-run", action="store_true", help="Print timing only, no requests")
    parser.add_argument("--no-image", action="store_true", help="Skip img2img/i2v, use sd35_large fallback")
    parser.add_argument("--speed", type=float, default=None, help="Custom speed multiplier")
    parser.add_argument("--image", type=str,
                        default="/home/joerissen/Pictures/Flux2_randomPrompt_ClaudeSonnet4.5/ComfyUI_00591_.png",
                        help="Test image for img2img/i2v")
    parser.add_argument("--max-gap", type=float, default=15.0,
                        help="Cap idle gaps between requests in seconds (default: 15, 0=no cap)")
    parser.add_argument("--drain-threshold", type=float, default=60.0,
                        help="Original gaps longer than this trigger a queue drain (default: 60s)")
    args = parser.parse_args()

    speed = args.speed or (4.0 if args.fast else 1.0)
    asyncio.run(run_simulation(args.port, speed, args.dry_run, args.no_image, args.image, args.max_gap, args.drain_threshold))


if __name__ == "__main__":
    main()
