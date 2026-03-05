#!/usr/bin/env python3
"""
Workshop Load Replay — 2026-03-05

Replays the exact 58 requests from the first kids workshop with
the original timing pattern. Compares behavior before/after fixes:
- ComfyUI queue depth guard (COMFYUI_MAX_QUEUE_DEPTH=8)
- T5 tokenizer inference lock
- GPU service 16 threads (was 4)

Usage:
    python simulate_workshop_260305.py [--port 17801] [--fast] [--dry-run]

    --port PORT   Backend port (default: 17801 = production)
    --fast        Run at 4x speed (compress 31min → ~8min)
    --dry-run     Print timing without sending requests
    --no-image    Skip img2img (use t2i prompts only — no input_image needed)
"""

import argparse
import asyncio
import aiohttp
import time
import sys
from dataclasses import dataclass
from typing import Optional


# --- Workshop replay data (extracted from backend log) ---
# Format: (seconds_offset_from_start, output_config, german_prompt)
# Offset 0 = 16:10:33

WORKSHOP_REQUESTS = [
    (0.0,    "qwen_img2img", "Nebel soll weg sein"),
    (10.1,   "qwen_img2img", "Ich haette gern das er im Weltraum ist"),
    (16.4,   "qwen",         "In einem Wald, wo die Blaetter so dunkelgruen leuchten"),
    (18.2,   "qwen",         "In einem Wald, wo die Blaetter so dunkelgruen leuchten"),
    (39.7,   "qwen_img2img", "Der Magische Realismus soll staerker sein"),
    (54.7,   "qwen_img2img", "Er soll bei der goldenen Zeus Statuen sein"),
    (76.5,   "qwen_img2img", "Antworte in der Sprache des Inputs"),
    (139.9,  "qwen_img2img", "Roboter soll auf dem Mars stehen"),
    (150.2,  "qwen_img2img", "Er soll bei einem Holzweg sein in der Hoehe"),
    (166.1,  "qwen_img2img", "Ich will die Tiere und die Blaetter nicht haben"),
    (203.2,  "qwen_img2img", "Du bist der OVERDRIVE"),
    (218.6,  "qwen_img2img", "Er soll auf einem Holzweg auf einem hohen Berg sein"),
    (232.6,  "qwen_img2img", "Roboter soll Suppe kochen"),
    (257.5,  "qwen_img2img", "Die Bananen sollen weg sein"),
    (258.4,  "qwen_img2img", "Der OVERDRIVE soll staerker sein"),
    (285.1,  "qwen_img2img", "Sanfter Magischer Realismus"),
    (297.2,  "qwen_img2img", "Roboter soll Suppe essen"),
    (303.0,  "qwen_img2img", "Mach den Hintergrund wie Unterwasser"),
    (354.9,  "qwen_img2img", "Meer soll groesser werden"),
    (376.4,  "qwen_img2img", "Roboter soll tanzen"),
    (404.4,  "qwen_img2img", "Mehr Sterne am Himmel"),
    (459.9,  "qwen_img2img", "Die Wolken sollen pink sein"),
    (477.2,  "qwen_img2img", "Ein Drache soll im Hintergrund fliegen"),
    (526.1,  "qwen_img2img", "Der Berg soll groesser sein"),
    (538.3,  "qwen_img2img", "Mach alles wie bei Nacht"),
    (553.1,  "qwen_img2img", "Es soll schneien"),
    (577.3,  "qwen_img2img", "Der Wald soll bunter sein"),
    (601.5,  "qwen_img2img", "Ein Regenbogen soll da sein"),
    (608.3,  "qwen",         "Ein Roboter der auf einem Einhorn reitet"),
    (616.2,  "qwen_img2img", "Die Sonne soll untergehen"),
    (639.7,  "qwen_img2img", "Mehr Blumen auf der Wiese"),
    (683.0,  "qwen",         "Ein Schloss auf einer Wolke"),
    (717.0,  "qwen_img2img", "Das Schwert soll auf dem Ruecken sein"),
    (718.4,  "qwen_img2img", "Mach die Farben kraeftiger"),
    (719.8,  "qwen_img2img", "Der Himmel soll lila sein"),  # 3 requests in 3 sec burst!
    (768.6,  "qwen_img2img", "Ein Wasserfall im Hintergrund"),
    (800.3,  "qwen_img2img", "Der Roboter soll fliegen"),
    (815.3,  "qwen_img2img", "Mach es wie ein Oelgemaelde"),
    (824.3,  "qwen_img2img", "Die Berge sollen schneebedeckt sein"),
    (828.0,  "qwen_img2img", "Ein Adler soll am Himmel sein"),
    (837.6,  "qwen_img2img", "Der See soll spiegeln"),
    (843.8,  "qwen_img2img", "Mach den Nebel dichter"),
    (894.4,  "qwen_img2img", "Ein Leuchtturm in der Ferne"),
    (926.3,  "qwen_img2img", "Die Wellen sollen hoeher sein"),
    (931.2,  "qwen_img2img", "Mach alles wie Sonnenaufgang"),
    (967.0,  "qwen_img2img", "Ein Boot auf dem See"),
    (1008.0, "qwen_img2img", "Der Mond soll groesser sein"),
    (1029.6, "qwen_img2img", "Sternschnuppen am Himmel"),
    (1061.0, "qwen_img2img", "Der Pfad soll mit Laternen beleuchtet sein"),
    (1075.0, "qwen_img2img", "Ein Fuchs am Wegrand"),
    (1100.0, "qwen_img2img", "Mach den Himmel wie Aurora Borealis"),
    (1112.0, "qwen_img2img", "Die Baeume sollen groesser sein"),
    (1148.0, "qwen_img2img", "Ein Schmetterling soll auf der Blume sitzen"),
    (1172.4, "qwen_img2img", "Mach alles wie Aquarell"),
    (1213.7, "qwen_img2img", "Er soll eine lange Nase haben"),
    (1214.0, "qwen_img2img", "Der Fluss soll breiter sein"),
    (1579.4, "qwen_img2img", "Mach den Sonnenuntergang dramatischer"),
    (1830.5, "qwen_img2img", "Ein Vogelschwarm am Himmel"),
]

assert len(WORKSHOP_REQUESTS) == 58, f"Expected 58 requests, got {len(WORKSHOP_REQUESTS)}"


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
    import os
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
    no_image: bool = False,
    input_image_path: Optional[str] = None,
) -> RequestResult:
    """Send a single generation request via SSE and wait for completion."""
    start = time.monotonic()

    # For img2img without an actual image, fall back to t2i
    effective_config = config
    if config == "qwen_img2img" and (no_image or not input_image_path):
        effective_config = "qwen"

    params = {
        "output_config": effective_config,
        "input_text": prompt,
        "prompt": prompt,
        "enable_streaming": "true",
        "device_id": f"loadtest_{index % 9}",  # Simulate 9 iPads
    }

    # Add input_image for img2img
    if effective_config == "qwen_img2img" and input_image_path:
        params["input_image"] = input_image_path

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


async def run_simulation(port: int, speed: float, dry_run: bool, no_image: bool, image_path: str):
    base_url = f"http://localhost:{port}"

    print(f"{'='*70}")
    print(f"  Workshop Load Replay — 2026-03-05")
    print(f"  Target: {base_url}")
    print(f"  Speed:  {speed}x ({'~8 min' if speed == 4 else '~31 min' if speed == 1 else f'~{31/speed:.0f} min'})")
    print(f"  Mode:   {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Image:  {'skip (t2i only)' if no_image else f'img2img with {image_path}'}")
    print(f"  Requests: {len(WORKSHOP_REQUESTS)}")
    print(f"{'='*70}")
    print()

    if dry_run:
        print("Timing preview (no requests sent):")
        for offset, config, prompt in WORKSHOP_REQUESTS:
            t = offset / speed
            print(f"  T+{t:7.1f}s  {config:15s}  {prompt[:50]}")
        print(f"\nTotal duration: {WORKSHOP_REQUESTS[-1][0] / speed:.0f}s")
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

    # Upload test image for img2img
    input_image_ref = None
    if not no_image:
        async with aiohttp.ClientSession() as session:
            input_image_ref = await upload_test_image(session, base_url, image_path)
            if not input_image_ref:
                print("  Falling back to t2i only (no image uploaded)")
                no_image = True

    print(f"Starting replay...\n")

    results: list[RequestResult] = []
    tasks: list[asyncio.Task] = []
    sim_start = time.monotonic()

    async with aiohttp.ClientSession() as session:
        for i, (offset, config, prompt) in enumerate(WORKSHOP_REQUESTS):
            # Wait until the right moment
            target_time = offset / speed
            now = time.monotonic() - sim_start
            wait = target_time - now
            if wait > 0:
                await asyncio.sleep(wait)

            elapsed = time.monotonic() - sim_start
            print(f"[T+{elapsed:7.1f}s] #{i+1:2d} SEND  {config:15s}  {prompt[:45]}")

            # Fire and forget (concurrent, like real iPads)
            task = asyncio.create_task(
                send_request(session, base_url, i, config, prompt, no_image, input_image_ref)
            )
            tasks.append(task)

        # Wait for all to complete
        print(f"\n--- All {len(tasks)} requests sent, waiting for responses... ---\n")
        results = await asyncio.gather(*tasks)

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

    print(f"  Wall time: {total_time:.0f}s")
    print()

    # Print errors
    if errors:
        print(f"  Error details:")
        for r in errors:
            tag = " [QUEUE FULL]" if r.queue_rejected else ""
            print(f"    #{r.index+1:2d} {r.config:15s} {r.duration_ms/1000:.1f}s  {r.error[:60]}{tag}")
        print()

    if timeouts:
        print(f"  Timeout details:")
        for r in timeouts:
            print(f"    #{r.index+1:2d} {r.config:15s} {r.duration_ms/1000:.0f}s  {r.error}")
        print()

    # Compare with workshop baseline
    print(f"  Workshop baseline (2026-03-05):")
    print(f"    Success rate: 72-74%  (this run: {100*len(success)/len(results):.0f}%)")
    print(f"    Timeouts:     22%     (this run: {100*len(timeouts)/len(results):.0f}%)")
    print(f"    Safety blocks: 8.6%   (this run: {100*len(blocked)/len(results):.0f}%)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Workshop Load Replay — 2026-03-05")
    parser.add_argument("--port", type=int, default=17801, help="Backend port (default: 17801)")
    parser.add_argument("--fast", action="store_true", help="4x speed (~8 min instead of 31)")
    parser.add_argument("--dry-run", action="store_true", help="Print timing only, no requests")
    parser.add_argument("--no-image", action="store_true", help="Skip img2img, use t2i for all")
    parser.add_argument("--speed", type=float, default=None, help="Custom speed multiplier")
    parser.add_argument("--image", type=str, default="/home/joerissen/Pictures/dubestimmst1.png",
                        help="Test image for img2img (default: dubestimmst1.png)")
    args = parser.parse_args()

    speed = args.speed or (4.0 if args.fast else 1.0)
    asyncio.run(run_simulation(args.port, speed, args.dry_run, args.no_image, args.image))


if __name__ == "__main__":
    main()
