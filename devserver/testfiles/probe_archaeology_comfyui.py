#!/usr/bin/env python3
"""
Probe: does SD3.5-Large run the Denoising Archaeology under ComfyUI's memory
management on a card where the Diffusers path forces Medium?

Runs the same prompt through both output configs and reports wall time, frame
count and the peak VRAM ComfyUI reports while the run is in flight.

Run on the GPU host (DevServer, GPU service and ComfyUI must be up):

    python devserver/testfiles/probe_archaeology_comfyui.py

Both configs run SD3.5-Large on every card since 2026-09-18 (latent_lab_model.py);
the override AI4ARTSED_LATENT_LAB_MODEL that this probe once needed is gone.
"""

import argparse
import os
import threading
import time

import requests

DEVSERVER = os.environ.get("AI4ARTSED_DEVSERVER_URL", "http://127.0.0.1:17802")
COMFYUI = os.environ.get("AI4ARTSED_COMFYUI_URL", "http://127.0.0.1:17804")

PROMPT = "a house by the lake at dawn, mist over the water"


class VramSampler(threading.Thread):
    """Polls ComfyUI /system_stats and keeps the highest VRAM figure seen."""

    def __init__(self, interval=1.0):
        super().__init__(daemon=True)
        self.interval = interval
        self.peak_mb = 0.0
        self.total_mb = 0.0
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                stats = requests.get(f"{COMFYUI}/system_stats", timeout=5).json()
                for dev in stats.get("devices", []):
                    total = dev.get("vram_total", 0) / (1024 ** 2)
                    free = dev.get("vram_free", 0) / (1024 ** 2)
                    self.total_mb = max(self.total_mb, total)
                    self.peak_mb = max(self.peak_mb, total - free)
            except Exception:
                pass
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
        self.join(timeout=3)


def run_config(output_config, steps, seed):
    sampler = VramSampler()
    sampler.start()
    started = time.time()
    try:
        response = requests.post(
            f"{DEVSERVER}/api/schema/pipeline/direct",  # /legacy, its alias, went 2026-10-10
            json={
                "prompt": PROMPT,
                "output_config": output_config,
                "seed": seed,
                "negative_prompt": "",
                "steps": steps,
                "cfg": 4.5,
            },
            timeout=(10, None),
        )
    finally:
        sampler.stop()
    elapsed = time.time() - started

    ok = response.status_code == 200 and response.json().get("status") == "success"
    arch = response.json().get("archaeology_data") or {} if ok else {}
    return {
        "config": output_config,
        "ok": ok,
        "seconds": elapsed,
        "frames": len(arch.get("step_images", [])),
        "total_steps": arch.get("total_steps"),
        "seed": arch.get("seed"),
        "peak_vram_mb": sampler.peak_mb,
        "total_vram_mb": sampler.total_mb,
        "error": None if ok else response.text[:300],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--seed", type=int, default=123456789)
    parser.add_argument("--configs", nargs="+",
                        default=["denoising_archaeology_comfyui",
                                 "denoising_archaeology_diffusers"])
    args = parser.parse_args()

    print(f"prompt: {PROMPT!r}, steps={args.steps}, seed={args.seed}\n")

    for config in args.configs:
        result = run_config(config, args.steps, args.seed)
        status = "ok" if result["ok"] else "FAILED"
        print(f"{config:38s} {status:7s} {result['seconds']:6.1f}s  "
              f"frames={result['frames']:3d}/{result['total_steps']}  "
              f"peak VRAM {result['peak_vram_mb']:.0f} of {result['total_vram_mb']:.0f} MB")
        if result["error"]:
            print(f"    {result['error']}")


if __name__ == "__main__":
    main()
